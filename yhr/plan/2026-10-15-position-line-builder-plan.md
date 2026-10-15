# 보유 스냅샷 생성기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `collection_run`의 계좌별 결과로 `position_line`을 만들고, 날짜를 확정해 `snapshot_run`을 쓰는 백엔드 잡을 만든다.

**Architecture:** `com.stockproject.portfolio.snapshot` 패키지에 순수 계산(`LineCalculator` · `LineInvariants`)과 DB 작업(`RunProcessor` · `Finalizer` · `CredentialFiller`)을 나눠 둔다. 세 작업은 `SnapshotJobs`가 PT1M마다 부르고, `portfolio.snapshot.runtime.enabled`로 끈다. 중복과 경쟁은 날짜 advisory lock과 계좌 행 잠금, `position_build` 기록으로 막는다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · MyBatis 3.0.4(애너테이션 매퍼) · Flyway · PostgreSQL 16 · JUnit 5 · AssertJ

**Spec:** [`docs/yhr/specs/portfolio-management/2026-10-15-position-line-builder-design.md`](../specs/portfolio-management/2026-10-15-position-line-builder-design.md) (이하 "설계"). 상위 스펙은 [`2026-07-28-portfolio-management-spec.md`](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md).

작업 저장소는 `back-end/`다. 아래 경로는 모두 `back-end/` 기준이다.

## Global Constraints

- 스펙과 설계를 고치지 않는다. 구현이 막히면 멈추고 보고한다.
- 테스트 먼저. 모든 테스트는 `./gradlew test`로 CI(`postgres:16-alpine`, `portfolio_test`)에서 돈다. 로컬은 `docker compose up -d db` 뒤 같은 명령. DB를 띄우는 것은 사용자 승인 후에 한다.
- 커밋은 사용자가 요청할 때만 한다. 각 태스크 끝의 커밋 단계는 "요청받았을 때 이 메시지로"라는 뜻이다. 메시지는 한국어, 접두 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝에 아래 두 줄.
  ```
  Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_012rF5kXv4Y7v1fv4hMvL8Tk
  ```
- 주석 · 문서는 히스토리 없이 최신 사실만. 검증하지 않은 것을 단정하지 않는다. 주석 밀도와 어조는 주변 코드(`alert/runtime` · `query`)를 따른다.
- 자격증명 · 계좌번호를 코드 · 로그 · 테스트 데이터에 넣지 않는다. 로그에는 `account_id` · `run_id`만. `credential_ref` 값은 테스트에서도 가짜 경로(`/stock-project/accounts/test/...`)만 쓴다.
- SQL은 스키마를 붙이지 않는다(`currentSchema=app,data`). 예외는 `db/external` 미러 DDL — `data.`를 명시한다.
- 마이그레이션 번호는 `db/migration`과 `db/external`을 통틀어 하나의 순열이다. 이번은 V7(external) · V8(migration).
- 금액 반올림은 `RoundingMode.HALF_UP`. 원화는 정수, 현지 통화는 소수 4자리.
- 운영 DB에 쓰지 않는다. 운영에서 잡을 켜는 것(매니페스트 변경)은 이 계획의 범위가 아니다.

## Review Focus

1. **운영 배포 직후 계좌별 화면이 500이 되는 경우** — `CollectionRunStatusPort`가 `collection_run`을 읽는데 운영 DB 계정에 `data.collection_run` SELECT 권한이 없으면 계좌별 뷰가 깨진다. 사용자는 화면이 그대로 뜨기를 기대한다. → Task 5에 "표가 비어 있으면 `last_collection`이 null" 테스트, Task 12의 배포 전 확인 항목에 권한 질의를 둔다.
2. **샘플 데이터로 띄운 로컬 개발 서버에서 잡을 켰을 때** — 샘플 계좌에는 `collection_run`이 없으므로 아무 날도 확정하지 않아야 한다(샘플 라인을 이월로 덮으면 안 된다). → Task 9에 "실행이 하나도 없으면 아무것도 쓰지 않는다" 테스트.
3. **`USD`도 `KRW`도 아닌 통화의 잔고** — 환율 계약은 `USD/KRW`뿐이다. 다른 통화가 오면 조용히 1로 환산하지 않고 그 계좌를 실패시켜야 한다. → Task 2에 `FX_MISSING` 테스트.
4. **캘린더에 날짜가 빠진 구간** — 빠진 날을 비영업일로 간주해 건너뛰면 그날 스냅샷이 영영 생기지 않는다. 확정을 멈추고 경고해야 한다. → Task 9에 "캘린더 공백에서 멈춤" 테스트.
5. **같은 사용자의 두 계좌 실행이 동시에 처리될 때의 교착** — 서로 다른 계좌를 먼저 잡으면 교착이 난다. 사용자는 둘 다 반영되기를 기대한다. → Task 11에 동시 처리 테스트.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `src/main/resources/db/external/V7__portfolio_collection_mirror.sql` | `collection_run` · `cln_balance` · `cln_deposit` · `fx_rate` 미러(로컬 · 테스트) |
| `src/main/resources/db/migration/V8__position_build.sql` | `position_build` |
| `src/main/resources/db/sample/sample_portfolio.sql` | `TRUNCATE` 목록에 `position_build` · 수집 결과 표 추가 |
| `src/main/java/.../snapshot/Line.java` | `position_line` 한 행 |
| `src/main/java/.../snapshot/BalanceRow.java` · `DepositRow.java` · `BalanceSet.java` · `FxQuote.java` · `Reference.java` | 계산 입력 |
| `src/main/java/.../snapshot/BuildReason.java` · `BuildOutcome.java` | `position_build`의 값 |
| `src/main/java/.../snapshot/Calculation.java` | 계산 결과(라인 또는 실패 사유) |
| `src/main/java/.../snapshot/LineCalculator.java` | 잔고 한 벌 → 라인(순수) |
| `src/main/java/.../snapshot/LineInvariants.java` | 쓰기 전 검사(순수) |
| `src/main/java/.../snapshot/RunRow.java` · `CollectionRunMapper.java` | 처리할 실행 고르기 · `credential_ref` 채우기 |
| `src/main/java/.../snapshot/BalanceMapper.java` | `cln_*` · `instrument` · `fx_rate` 읽기 |
| `src/main/java/.../snapshot/PositionWriteMapper.java` | 잠금 · 라인 쓰기 · 계좌 갱신 |
| `src/main/java/.../snapshot/PositionBuildMapper.java` · `ExistingBuild.java` | `position_build` |
| `src/main/java/.../snapshot/FinalizeMapper.java` · `TargetAccount.java` | 확정 대상 판정 |
| `src/main/java/.../snapshot/CredentialFiller.java` | 설계 §8 |
| `src/main/java/.../snapshot/RunProcessor.java` | 설계 §5 |
| `src/main/java/.../snapshot/Finalizer.java` | 설계 §6 |
| `src/main/java/.../snapshot/SnapshotProperties.java` | `portfolio.snapshot.*` |
| `src/main/java/.../snapshot/SnapshotJobs.java` · `SnapshotRuntimeConfig.java` | 스케줄 등록 |
| `src/main/java/.../query/CollectionRunStatusMapper.java` · `CollectionRunStatusPort.java` · `FailureReasons.java` | 계좌별 뷰 `last_collection` |
| `src/main/java/.../query/NoCollectionStatusPort.java` | 삭제 |
| `src/main/java/.../query/FactCheckMapper.java` | `accountsWithoutLine` 좁히기 |
| `src/main/java/.../alert/data/HoldingMapper.java` | 최신 확정 스냅샷을 `snapshot_run`이 있는 날로 한정 |
| `src/main/resources/application.yaml` | 스케줄러 풀 4, `portfolio.snapshot` 기본값 |
| `src/test/resources/application-test.yaml` | 스냅샷 런타임 끔 |
| `src/test/java/.../snapshot/SnapshotFixture.java` · `MutableClock.java` · `SnapshotTestConfig.java` | 테스트 픽스처 |
| `README.md` | "이 저장소에 없는 것" · 설정 갱신 |

`...`는 `com/stockproject/portfolio`.

---

### Task 1: 스키마 — 미러 V7 · `position_build` V8

**Files:**
- Create: `src/main/resources/db/external/V7__portfolio_collection_mirror.sql`
- Create: `src/main/resources/db/migration/V8__position_build.sql`
- Modify: `src/main/resources/db/sample/sample_portfolio.sql:9`
- Modify: `src/test/java/com/stockproject/portfolio/query/SchemaContractTest.java` (`범위_밖_테이블을_만들지_않는다` 와 새 테스트)

**Interfaces:**
- Produces: 표 `data.collection_run` · `data.cln_balance` · `data.cln_deposit` · `data.fx_rate` · `app.position_build`. 이후 모든 태스크가 쓴다.

- [ ] **Step 1: 실패하는 계약 테스트를 쓴다**

`SchemaContractTest`의 `범위_밖_테이블을_만들지_않는다`를 고치고 아래 테스트를 더한다.

```java
    /** 백엔드가 소유하지 않는 테이블을 만들지 않는다 — position_basis·sync_run은 범위 밖이다. */
    @Test
    void 범위_밖_테이블을_만들지_않는다() {
        List<String> tables = jdbc.sql("""
                SELECT table_name FROM information_schema.tables
                 WHERE table_schema IN ('app', 'data') AND table_type = 'BASE TABLE'
                """).query(String.class).list();

        assertThat(tables).doesNotContain("position_basis", "sync_run");
    }

    /**
     * 수집 결과 미러가 데이터 요구사항 §6.4 · §6.5 · §6.6 · §6.10의 컬럼을 그대로 갖는다.
     * 미러와 이 기대값을 둘 다 백엔드가 쓰므로, 운영 스키마와의 차이는 잡지 못한다 — 그것은 켜기 전 확인이 한다.
     */
    @Test
    void 수집_결과_미러_컬럼_계약() {
        assertThat(columnsOf("collection_run")).containsExactly(
                "account_ref", "as_of", "credential_ref", "failure_reason", "finished_at",
                "requested_at", "requested_by", "run_id", "silver_synced_at", "state");
        assertThat(columnsOf("cln_balance")).containsExactly(
                "account_ref", "avg_price", "currency", "ingest_id", "instrument_id", "isin",
                "market_value", "quantity", "source_as_of");
        assertThat(columnsOf("cln_deposit")).containsExactly(
                "account_ref", "amount", "currency", "source_as_of");
        assertThat(columnsOf("fx_rate")).containsExactly(
                "as_of", "currency_pair", "rate", "rate_type", "source");
    }

    /** 처리 기록은 확정 행에만 run_id가 없다. */
    @Test
    void position_build는_실행_없는_SKIPPED를_거부한다() {
        assertThatThrownBy(() -> jdbc.sql("""
                INSERT INTO position_build (run_id, account_id, as_of, outcome, reason, built_at)
                SELECT NULL, account_id, DATE '2026-10-13', 'SKIPPED', 'NO_BALANCE', now() FROM account LIMIT 1
                """).update())
                .isInstanceOf(org.springframework.dao.DataIntegrityViolationException.class);
    }
```

이 클래스에 `@Sql("classpath:db/sample/sample_portfolio.sql")`이 없으면 마지막 테스트에만 붙인다(계좌 한 행이 필요하다). `assertThatThrownBy` import를 더한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests '*SchemaContractTest'`
Expected: `수집_결과_미러_컬럼_계약` FAIL(표 없음), `position_build는_...` FAIL(relation "position_build" does not exist)

- [ ] **Step 3: V7 미러를 쓴다**

```sql
-- 데이터팀 소유 테이블의 로컬·테스트 전용 미러. 운영 프로필은 이 파일을 적용하지 않는다.
-- 컬럼과 타입은 데이터 요구사항 문서(docs/yhr/specs/data-requirements.md) §6.4 · §6.5 · §6.6 · §6.10을 따른다.

CREATE TABLE IF NOT EXISTS data.collection_run (
    run_id           uuid        PRIMARY KEY,
    account_ref      text        NOT NULL,
    requested_by     text        NOT NULL CHECK (requested_by IN ('SCHEDULE', 'USER')),
    as_of            date        NOT NULL,
    requested_at     timestamptz NOT NULL,
    credential_ref   text,
    state            text        NOT NULL CHECK (state IN
                       ('REQUESTED', 'RUNNING', 'DONE', 'FAILED', 'REAUTH_REQUIRED')),
    finished_at      timestamptz,
    failure_reason   text,
    silver_synced_at timestamptz
);

CREATE TABLE IF NOT EXISTS data.cln_balance (
    account_ref   text           NOT NULL,
    instrument_id uuid           NOT NULL,
    isin          text,
    quantity      numeric(20, 8) NOT NULL,
    avg_price     numeric(20, 4) NOT NULL,
    market_value  numeric(20, 4) NOT NULL,
    currency      text           NOT NULL,
    source_as_of  timestamptz    NOT NULL,
    ingest_id     text           NOT NULL,
    PRIMARY KEY (account_ref, instrument_id, source_as_of)
);

CREATE TABLE IF NOT EXISTS data.cln_deposit (
    account_ref  text           NOT NULL,
    currency     text           NOT NULL,
    amount       numeric(20, 4) NOT NULL,
    source_as_of timestamptz    NOT NULL,
    PRIMARY KEY (account_ref, currency, source_as_of)
);

CREATE TABLE IF NOT EXISTS data.fx_rate (
    as_of         date           NOT NULL,
    currency_pair text           NOT NULL,
    rate_type     text           NOT NULL,
    rate          numeric(18, 6) NOT NULL,
    source        text           NOT NULL,
    PRIMARY KEY (as_of, currency_pair, rate_type)
);
```

- [ ] **Step 4: V8 `position_build`를 쓴다**

```sql
-- 보유 스냅샷 생성기의 처리 기록 (보유 스냅샷 생성기 설계 §4.3).
-- 같은 수집 실행을 두 번 처리하지 않게 하는 키이자, 라인이 왜 그렇게 됐는지를 남기는 로그다.
CREATE TABLE position_build (
    build_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id      uuid UNIQUE,
    account_id  uuid        NOT NULL REFERENCES account (account_id),
    as_of       date        NOT NULL,
    outcome     text        NOT NULL CHECK (outcome IN ('BUILT', 'CARRIED', 'PROMOTED', 'SKIPPED')),
    reason      text        CHECK (reason IN (
                  'NO_BALANCE', 'STALE_BALANCE', 'UNMATCHED_INSTRUMENT', 'CASH_INSTRUMENT',
                  'FX_MISSING', 'CALENDAR_UNKNOWN',
                  'INVARIANT', 'OLDER_THAN_EXISTING', 'FINAL_EXISTS', 'NOT_TRADING_DAY',
                  'RUN_NOT_DONE', 'DISCONNECTED', 'DEADLINE')),
    attempts    integer     NOT NULL DEFAULT 1,
    built_at    timestamptz NOT NULL,
    CHECK (outcome <> 'SKIPPED' OR reason IS NOT NULL),
    CHECK (run_id IS NOT NULL OR outcome IN ('CARRIED', 'PROMOTED'))
);

-- 확정 단계는 계좌 · 날짜마다 한 번만 기록한다.
CREATE UNIQUE INDEX uq_position_build_finalize ON position_build (account_id, as_of)
    WHERE run_id IS NULL;

COMMENT ON COLUMN position_build.run_id IS
  'data.collection_run.run_id. 확정 단계(이월 · 승격)가 쓴 행은 비어 있다';
COMMENT ON COLUMN position_build.attempts IS
  '재시도할 수 있는 사유(데이터가 늦게 도착해 생기는 실패)로 다시 처리한 횟수를 포함한다';
```

- [ ] **Step 5: 샘플의 TRUNCATE에 새 표를 더한다**

`account`를 FK로 가리키는 `position_build`가 목록에 없으면 Postgres가 `TRUNCATE`를 거부한다. 수집 결과 표는 그것을 심는 테스트가 남긴 행이 샘플을 쓰는 화면 테스트(`last_collection: null`)에 섞이지 않게 함께 비운다. `sample_portfolio.sql` 9행:

```sql
TRUNCATE position_build, realized_pnl_line, manual_cashflow, position_line, account, instrument, etf_coverage,
         collection_run, cln_balance, cln_deposit, fx_rate;
```

- [ ] **Step 6: 통과를 확인한다**

Run: `./gradlew test --tests '*SchemaContractTest' --tests '*MigrationLintTest' --tests '*SnapshotViewApiTest'`
Expected: PASS

- [ ] **Step 7: 커밋**

```bash
git add src/main/resources/db src/test/java/com/stockproject/portfolio/query/SchemaContractTest.java
git commit -m "feat: 수집 결과 미러와 보유 스냅샷 처리 기록 표를 둔다"
```

---

### Task 2: 라인 계산 — `LineCalculator`

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/snapshot/{Line,BalanceRow,DepositRow,BalanceSet,FxQuote,Reference,BuildReason,BuildOutcome,Calculation,LineCalculator}.java`
- Test: `src/test/java/com/stockproject/portfolio/snapshot/LineCalculatorTest.java`

**Interfaces:**
- Produces:
  - `record Line(LocalDate asOf, UUID accountId, UUID instrumentId, BigDecimal quantity, BigDecimal costAmountLocal, BigDecimal marketValueLocal, BigDecimal costAmountKrw, BigDecimal marketValueKrw, BigDecimal fxRate, LocalDate fxAsOf, OffsetDateTime sourceAsOf, boolean carriedForward, boolean isFinal)` + `Line carriedTo(LocalDate day, boolean isFinal)`
  - `record BalanceRow(UUID instrumentId, BigDecimal quantity, BigDecimal avgPrice, BigDecimal marketValue, String currency)` — `instrumentId`는 null일 수 있다
  - `record DepositRow(String currency, BigDecimal amount)`
  - `record BalanceSet(OffsetDateTime sourceAsOf, List<BalanceRow> balances, List<DepositRow> deposits)`
  - `record FxQuote(BigDecimal rate, LocalDate asOf)`
  - `record Reference(Set<UUID> knownInstruments, Map<String, List<UUID>> cashInstruments, FxQuote usdKrw)` — `usdKrw`는 null일 수 있다
  - `enum BuildReason { NO_BALANCE, STALE_BALANCE, UNMATCHED_INSTRUMENT, CASH_INSTRUMENT, FX_MISSING, CALENDAR_UNKNOWN, INVARIANT, OLDER_THAN_EXISTING, FINAL_EXISTS, NOT_TRADING_DAY, RUN_NOT_DONE, DISCONNECTED, DEADLINE; boolean retriable(); static List<String> retriableNames(); }`
  - `enum BuildOutcome { BUILT, CARRIED, PROMOTED, SKIPPED }`
  - `sealed interface Calculation { record Lines(List<Line> lines) ; record Failed(BuildReason reason) }`
  - `LineCalculator.calculate(UUID accountId, LocalDate asOf, OffsetDateTime requestedAt, BalanceSet set, Reference ref, boolean isFinal) : Calculation` — `set`이 null이면 `NO_BALANCE`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.snapshot;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** 잔고 한 벌 → position_line (설계 §5.2 ~ §5.4). */
class LineCalculatorTest {

    static final UUID ACCOUNT  = UUID.fromString("30000000-0000-0000-0000-000000000001");
    static final UUID SAMSUNG  = UUID.fromString("10000000-0000-0000-0000-000000000001");
    static final UUID AAPL     = UUID.fromString("10000000-0000-0000-0000-000000000004");
    static final UUID CASH_KRW = UUID.fromString("10000000-0000-0000-0000-000000000007");
    static final UUID CASH_USD = UUID.fromString("10000000-0000-0000-0000-000000000008");
    static final LocalDate AS_OF = LocalDate.of(2026, 10, 13);
    static final OffsetDateTime REQUESTED = OffsetDateTime.parse("2026-10-13T23:00:00+09:00");
    static final OffsetDateTime T = OffsetDateTime.parse("2026-10-13T23:05:00+09:00");

    static final Reference REF = new Reference(
            Set.of(SAMSUNG, AAPL),
            Map.of("KRW", List.of(CASH_KRW), "USD", List.of(CASH_USD)),
            new FxQuote(new BigDecimal("1385.500000"), LocalDate.of(2026, 10, 12)));

    @Test
    void 원화_종목은_환율_1과_그날로_환산한다() {
        Calculation c = LineCalculator.calculate(ACCOUNT, AS_OF, REQUESTED, set(
                List.of(new BalanceRow(SAMSUNG, bd("10"), bd("61000.5"), bd("640000"), "KRW")),
                List.of(new DepositRow("KRW", bd("1000")))), REF, true);

        Line samsung = lines(c).get(0);
        assertThat(samsung.costAmountLocal()).isEqualByComparingTo("610005.0000");
        assertThat(samsung.costAmountKrw()).isEqualByComparingTo("610005");
        assertThat(samsung.marketValueKrw()).isEqualByComparingTo("640000");
        assertThat(samsung.fxRate()).isEqualByComparingTo("1");
        assertThat(samsung.fxAsOf()).isEqualTo(AS_OF);
        assertThat(samsung.sourceAsOf()).isEqualTo(T);
        assertThat(samsung.carriedForward()).isFalse();
        assertThat(samsung.isFinal()).isTrue();
    }

    @Test
    void 달러_종목은_그날_이하_최신_환율로_환산하고_원화는_한_번만_반올림한다() {
        Calculation c = LineCalculator.calculate(ACCOUNT, AS_OF, REQUESTED, set(
                List.of(new BalanceRow(AAPL, bd("3"), bd("200.1"), bd("690.3"), "USD")),
                List.of(new DepositRow("KRW", bd("0")))), REF, false);

        Line aapl = lines(c).get(0);
        assertThat(aapl.costAmountLocal()).isEqualByComparingTo("600.3000");
        // 600.3 × 1385.5 = 831715.65 → 831716, 690.3 × 1385.5 = 956410.65 → 956411
        assertThat(aapl.costAmountKrw()).isEqualByComparingTo("831716");
        assertThat(aapl.marketValueKrw()).isEqualByComparingTo("956411");
        assertThat(aapl.fxAsOf()).isEqualTo(LocalDate.of(2026, 10, 12));
        assertThat(aapl.isFinal()).isFalse();
    }

    @Test
    void 원화_반올림은_HALF_UP이다() {
        // 0.5 → 1, 2.5 → 3. HALF_EVEN이면 0과 2가 된다.
        Calculation c = LineCalculator.calculate(ACCOUNT, AS_OF, REQUESTED, set(
                List.of(new BalanceRow(AAPL, bd("1"), bd("0.0005"), bd("0.0025"), "USD")),
                List.of(new DepositRow("KRW", bd("0")))),
                new Reference(REF.knownInstruments(), REF.cashInstruments(), new FxQuote(new BigDecimal("1000"), AS_OF)), true);

        Line aapl = lines(c).get(0);
        assertThat(aapl.costAmountKrw()).isEqualByComparingTo("1");
        assertThat(aapl.marketValueKrw()).isEqualByComparingTo("3");
    }

    @Test
    void 예수금은_통화별_CASH_종목으로_원가와_평가금액이_같다_0원도_만든다() {
        Calculation c = LineCalculator.calculate(ACCOUNT, AS_OF, REQUESTED, set(List.of(),
                List.of(new DepositRow("KRW", bd("0")), new DepositRow("USD", bd("12.5")))), REF, true);

        List<Line> lines = lines(c);
        assertThat(lines).extracting(Line::instrumentId).containsExactly(CASH_KRW, CASH_USD);
        assertThat(lines.get(0).marketValueKrw()).isEqualByComparingTo("0");
        assertThat(lines.get(1).costAmountKrw()).isEqualByComparingTo(lines.get(1).marketValueKrw());
        assertThat(lines.get(1).quantity()).isEqualByComparingTo("12.5");
    }

    @Test
    void 수량_0인_종목_행은_거른다() {
        Calculation c = LineCalculator.calculate(ACCOUNT, AS_OF, REQUESTED, set(
                List.of(new BalanceRow(SAMSUNG, bd("0"), bd("61000"), bd("0"), "KRW")),
                List.of(new DepositRow("KRW", bd("1")))), REF, true);

        assertThat(lines(c)).extracting(Line::instrumentId).containsExactly(CASH_KRW);
    }

    @Test
    void 예수금이_없으면_NO_BALANCE() {
        assertThat(LineCalculator.calculate(ACCOUNT, AS_OF, REQUESTED, null, REF, true))
                .isEqualTo(new Calculation.Failed(BuildReason.NO_BALANCE));
    }

    @Test
    void 잔고_시각이_요청보다_이르면_STALE_BALANCE() {
        BalanceSet old = new BalanceSet(REQUESTED.minusDays(2), List.of(), List.of(new DepositRow("KRW", bd("1"))));
        assertThat(LineCalculator.calculate(ACCOUNT, AS_OF, REQUESTED, old, REF, true))
                .isEqualTo(new Calculation.Failed(BuildReason.STALE_BALANCE));
    }

    @Test
    void 종목_id가_없거나_마스터에_없으면_UNMATCHED_INSTRUMENT() {
        UUID unknown = UUID.fromString("10000000-0000-0000-0000-000000000099");
        for (UUID id : new UUID[]{null, unknown}) {
            Calculation c = LineCalculator.calculate(ACCOUNT, AS_OF, REQUESTED, set(
                    List.of(new BalanceRow(id, bd("1"), bd("1"), bd("1"), "KRW")),
                    List.of(new DepositRow("KRW", bd("1")))), REF, true);
            assertThat(c).isEqualTo(new Calculation.Failed(BuildReason.UNMATCHED_INSTRUMENT));
        }
    }

    @Test
    void CASH_종목이_없거나_둘이면_CASH_INSTRUMENT() {
        Reference none = new Reference(REF.knownInstruments(), Map.of(), REF.usdKrw());
        Reference two = new Reference(REF.knownInstruments(), Map.of("KRW", List.of(CASH_KRW, CASH_USD)), REF.usdKrw());
        for (Reference r : List.of(none, two)) {
            Calculation c = LineCalculator.calculate(ACCOUNT, AS_OF, REQUESTED,
                    set(List.of(), List.of(new DepositRow("KRW", bd("1")))), r, true);
            assertThat(c).isEqualTo(new Calculation.Failed(BuildReason.CASH_INSTRUMENT));
        }
    }

    @Test
    void 환율이_없거나_계약에_없는_통화면_FX_MISSING() {
        Reference noFx = new Reference(REF.knownInstruments(), REF.cashInstruments(), null);
        assertThat(LineCalculator.calculate(ACCOUNT, AS_OF, REQUESTED, set(
                List.of(new BalanceRow(AAPL, bd("1"), bd("1"), bd("1"), "USD")),
                List.of(new DepositRow("KRW", bd("1")))), noFx, true))
                .isEqualTo(new Calculation.Failed(BuildReason.FX_MISSING));

        assertThat(LineCalculator.calculate(ACCOUNT, AS_OF, REQUESTED, set(
                List.of(new BalanceRow(SAMSUNG, bd("1"), bd("1"), bd("1"), "JPY")),
                List.of(new DepositRow("KRW", bd("1")))), REF, true))
                .isEqualTo(new Calculation.Failed(BuildReason.FX_MISSING));
    }

    @Test
    void 재시도_사유는_데이터_지연으로_생기는_여섯이다() {
        assertThat(BuildReason.retriableNames()).containsExactlyInAnyOrder(
                "NO_BALANCE", "STALE_BALANCE", "UNMATCHED_INSTRUMENT", "CASH_INSTRUMENT",
                "FX_MISSING", "CALENDAR_UNKNOWN");
    }

    @Test
    void 이월은_금액과_원천_시각을_그대로_두고_날짜와_표시만_바꾼다() {
        Line src = lines(LineCalculator.calculate(ACCOUNT, AS_OF, REQUESTED, set(List.of(),
                List.of(new DepositRow("KRW", bd("5")))), REF, true)).get(0);

        Line carried = src.carriedTo(AS_OF.plusDays(1), false);

        assertThat(carried.asOf()).isEqualTo(AS_OF.plusDays(1));
        assertThat(carried.sourceAsOf()).isEqualTo(src.sourceAsOf());
        assertThat(carried.fxAsOf()).isEqualTo(src.fxAsOf());
        assertThat(carried.marketValueKrw()).isEqualByComparingTo(src.marketValueKrw());
        assertThat(carried.carriedForward()).isTrue();
        assertThat(carried.isFinal()).isFalse();
    }

    static BalanceSet set(List<BalanceRow> balances, List<DepositRow> deposits) {
        return new BalanceSet(T, balances, deposits);
    }

    static List<Line> lines(Calculation c) {
        assertThat(c).isInstanceOf(Calculation.Lines.class);
        return ((Calculation.Lines) c).lines();
    }

    static BigDecimal bd(String v) { return new BigDecimal(v); }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests '*LineCalculatorTest'`
Expected: 컴파일 실패(클래스 없음)

- [ ] **Step 3: 값 타입을 만든다**

`Line.java`

```java
package com.stockproject.portfolio.snapshot;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

/** position_line 한 행. 비율 컬럼을 두지 않는다 — 라인 단위로 더해지면 틀린 값이 된다. */
public record Line(LocalDate asOf, UUID accountId, UUID instrumentId, BigDecimal quantity,
                   BigDecimal costAmountLocal, BigDecimal marketValueLocal,
                   BigDecimal costAmountKrw, BigDecimal marketValueKrw,
                   BigDecimal fxRate, LocalDate fxAsOf, OffsetDateTime sourceAsOf,
                   boolean carriedForward, boolean isFinal) {

    /** 이월(스펙 §7.3). 금액 · 환율 · 원천 시각은 원본 그대로 두고 날짜와 표시만 바꾼다. */
    public Line carriedTo(LocalDate day, boolean toFinal) {
        return new Line(day, accountId, instrumentId, quantity, costAmountLocal, marketValueLocal,
                costAmountKrw, marketValueKrw, fxRate, fxAsOf, sourceAsOf, true, toFinal);
    }
}
```

나머지 값 타입:

```java
// BalanceRow.java
package com.stockproject.portfolio.snapshot;

import java.math.BigDecimal;
import java.util.UUID;

/** cln_balance 한 행. instrumentId는 데이터가 매칭하지 못하면 null로 온다. */
public record BalanceRow(UUID instrumentId, BigDecimal quantity, BigDecimal avgPrice,
                         BigDecimal marketValue, String currency) { }
```

```java
// DepositRow.java
package com.stockproject.portfolio.snapshot;

import java.math.BigDecimal;

/** cln_deposit 한 행. */
public record DepositRow(String currency, BigDecimal amount) { }
```

```java
// BalanceSet.java
package com.stockproject.portfolio.snapshot;

import java.time.OffsetDateTime;
import java.util.List;

/** 한 실행의 잔고 한 벌 — 같은 source_as_of의 잔고 · 예수금 전부 (설계 §5.2). */
public record BalanceSet(OffsetDateTime sourceAsOf, List<BalanceRow> balances, List<DepositRow> deposits) { }
```

```java
// FxQuote.java
package com.stockproject.portfolio.snapshot;

import java.math.BigDecimal;
import java.time.LocalDate;

/** USD/KRW BASE 환율 한 행. asOf가 스냅샷 날짜보다 이르면 폴백이다. */
public record FxQuote(BigDecimal rate, LocalDate asOf) { }
```

```java
// Reference.java
package com.stockproject.portfolio.snapshot;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 계산이 대조하는 마스터. knownInstruments는 이번 잔고의 종목 가운데 instrument에 있는 것,
 * cashInstruments는 통화별 CASH 의사종목, usdKrw는 그날 이하 최신 환율(없으면 null).
 */
public record Reference(Set<UUID> knownInstruments, Map<String, List<UUID>> cashInstruments, FxQuote usdKrw) { }
```

```java
// BuildOutcome.java
package com.stockproject.portfolio.snapshot;

/** position_build.outcome (설계 §4.3). */
public enum BuildOutcome { BUILT, CARRIED, PROMOTED, SKIPPED }
```

```java
// BuildReason.java
package com.stockproject.portfolio.snapshot;

import java.util.Arrays;
import java.util.List;

/** position_build.reason (설계 §4.3 · §5.4). 재시도할 수 있는 것은 데이터가 늦게 도착해 생기는 실패다. */
public enum BuildReason {
    NO_BALANCE(true), STALE_BALANCE(true), UNMATCHED_INSTRUMENT(true), CASH_INSTRUMENT(true),
    FX_MISSING(true), CALENDAR_UNKNOWN(true),
    INVARIANT(false), OLDER_THAN_EXISTING(false), FINAL_EXISTS(false), NOT_TRADING_DAY(false),
    RUN_NOT_DONE(false), DISCONNECTED(false), DEADLINE(false);

    private final boolean retriable;

    BuildReason(boolean retriable) { this.retriable = retriable; }

    public boolean retriable() { return retriable; }

    public static List<String> retriableNames() {
        return Arrays.stream(values()).filter(BuildReason::retriable).map(Enum::name).toList();
    }
}
```

```java
// Calculation.java
package com.stockproject.portfolio.snapshot;

import java.util.List;

/** 잔고 한 벌의 계산 결과 — 라인 한 벌이거나 실패 사유 하나다. */
public sealed interface Calculation {
    record Lines(List<Line> lines) implements Calculation { }
    record Failed(BuildReason reason) implements Calculation { }
}
```

- [ ] **Step 4: `LineCalculator`를 만든다**

```java
package com.stockproject.portfolio.snapshot;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * 잔고 한 벌을 position_line으로 바꾼다 (설계 §5.2 ~ §5.4, 스펙 §5.2 · §5.3).
 * 원화 환산은 라인에서 한 번만 반올림한다. 하나라도 걸리면 라인 없이 실패 사유만 낸다 — 계좌 단위로 이월된다.
 */
public final class LineCalculator {

    private static final int LOCAL_SCALE = 4;

    private LineCalculator() { }

    public static Calculation calculate(UUID accountId, LocalDate asOf, OffsetDateTime requestedAt,
                                        BalanceSet set, Reference ref, boolean isFinal) {
        if (set == null || set.deposits().isEmpty()) return new Calculation.Failed(BuildReason.NO_BALANCE);
        if (set.sourceAsOf().isBefore(requestedAt)) return new Calculation.Failed(BuildReason.STALE_BALANCE);

        List<Line> lines = new ArrayList<>();
        for (BalanceRow b : set.balances()) {
            if (b.quantity().signum() == 0) continue;
            if (b.instrumentId() == null || !ref.knownInstruments().contains(b.instrumentId())) {
                return new Calculation.Failed(BuildReason.UNMATCHED_INSTRUMENT);
            }
            FxQuote fx = fx(b.currency(), asOf, ref);
            if (fx == null) return new Calculation.Failed(BuildReason.FX_MISSING);
            BigDecimal cost = b.avgPrice().multiply(b.quantity()).setScale(LOCAL_SCALE, RoundingMode.HALF_UP);
            BigDecimal value = b.marketValue().setScale(LOCAL_SCALE, RoundingMode.HALF_UP);
            lines.add(line(asOf, accountId, b.instrumentId(), b.quantity(), cost, value, fx, set.sourceAsOf(), isFinal));
        }
        for (DepositRow d : set.deposits()) {
            List<UUID> cash = ref.cashInstruments().getOrDefault(d.currency(), List.of());
            if (cash.size() != 1) return new Calculation.Failed(BuildReason.CASH_INSTRUMENT);
            FxQuote fx = fx(d.currency(), asOf, ref);
            if (fx == null) return new Calculation.Failed(BuildReason.FX_MISSING);
            BigDecimal amount = d.amount().setScale(LOCAL_SCALE, RoundingMode.HALF_UP);
            lines.add(line(asOf, accountId, cash.get(0), d.amount(), amount, amount, fx, set.sourceAsOf(), isFinal));
        }
        return new Calculation.Lines(lines);
    }

    /** KRW는 1과 그날, USD는 그날 이하 최신 BASE. 계약에 없는 통화는 환산하지 않는다. */
    private static FxQuote fx(String currency, LocalDate asOf, Reference ref) {
        if ("KRW".equals(currency)) return new FxQuote(BigDecimal.ONE, asOf);
        if ("USD".equals(currency)) return ref.usdKrw();
        return null;
    }

    private static Line line(LocalDate asOf, UUID accountId, UUID instrumentId, BigDecimal quantity,
                             BigDecimal cost, BigDecimal value, FxQuote fx, OffsetDateTime sourceAsOf,
                             boolean isFinal) {
        return new Line(asOf, accountId, instrumentId, quantity, cost, value,
                krw(cost, fx), krw(value, fx), fx.rate(), fx.asOf(), sourceAsOf, false, isFinal);
    }

    private static BigDecimal krw(BigDecimal local, FxQuote fx) {
        return local.multiply(fx.rate()).setScale(0, RoundingMode.HALF_UP);
    }
}
```

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test --tests '*LineCalculatorTest'`
Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add src/main/java/com/stockproject/portfolio/snapshot src/test/java/com/stockproject/portfolio/snapshot
git commit -m "feat: 잔고 한 벌을 보유 라인으로 바꾸는 계산을 둔다"
```

---

### Task 3: 쓰기 전 검사 — `LineInvariants`

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/snapshot/LineInvariants.java`
- Test: `src/test/java/com/stockproject/portfolio/snapshot/LineInvariantsTest.java`

**Interfaces:**
- Consumes: `Line` (Task 2)
- Produces: `LineInvariants.violations(List<Line> lines, Set<UUID> cashInstrumentIds, ZoneId zone) : List<String>` — 빈 목록이면 통과

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.snapshot;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** 스펙 §9.1 팩트 정합성 가운데 라인 한 벌로 판정하는 것 (설계 §5.5). */
class LineInvariantsTest {

    static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");
    static final UUID ACCOUNT = UUID.fromString("30000000-0000-0000-0000-000000000001");
    static final UUID STOCK = UUID.fromString("10000000-0000-0000-0000-000000000001");
    static final UUID CASH = UUID.fromString("10000000-0000-0000-0000-000000000007");
    static final LocalDate DAY = LocalDate.of(2026, 10, 13);
    static final OffsetDateTime SAME_DAY = OffsetDateTime.parse("2026-10-13T23:00:00+09:00");

    @Test
    void 정상_한_벌은_통과한다() {
        assertThat(LineInvariants.violations(List.of(line(STOCK, "10", "12"), line(CASH, "5", "5")),
                Set.of(CASH), SEOUL)).isEmpty();
    }

    @Test
    void 같은_종목이_두_행이면_그레인_위반() {
        assertThat(LineInvariants.violations(List.of(line(STOCK, "1", "1"), line(STOCK, "2", "2")),
                Set.of(CASH), SEOUL)).containsExactly("그레인 유일성 위반");
    }

    @Test
    void 환율이_비면_위반() {
        Line l = line(STOCK, "1", "1");
        Line noFx = new Line(l.asOf(), l.accountId(), l.instrumentId(), l.quantity(), l.costAmountLocal(),
                l.marketValueLocal(), l.costAmountKrw(), l.marketValueKrw(), null, null, l.sourceAsOf(), false, true);
        assertThat(LineInvariants.violations(List.of(noFx), Set.of(CASH), SEOUL))
                .containsExactly("fx_rate·fx_as_of 누락");
    }

    @Test
    void CASH_원가와_평가금액이_다르면_위반() {
        assertThat(LineInvariants.violations(List.of(line(CASH, "5", "6")), Set.of(CASH), SEOUL))
                .containsExactly("CASH 행의 원가 ≠ 평가금액");
    }

    @Test
    void 이월인데_원천_시각이_그날이면_위반() {
        Line carried = line(STOCK, "1", "1").carriedTo(DAY, true);
        assertThat(LineInvariants.violations(List.of(carried), Set.of(CASH), SEOUL))
                .containsExactly("is_carried_forward인데 source_as_of >= as_of");
    }

    static Line line(UUID instrument, String costKrw, String valueKrw) {
        return new Line(DAY, ACCOUNT, instrument, BigDecimal.ONE, new BigDecimal(costKrw), new BigDecimal(valueKrw),
                new BigDecimal(costKrw), new BigDecimal(valueKrw), BigDecimal.ONE, DAY, SAME_DAY, false, true);
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests '*LineInvariantsTest'`
Expected: 컴파일 실패

- [ ] **Step 3: 구현한다**

```java
package com.stockproject.portfolio.snapshot;

import java.time.ZoneId;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * 쓰기 전 검사 (설계 §5.5). 조회 시 검사(PositionLineInvariants)와 같은 규칙을 라인 한 벌에 건다.
 * 메시지는 조회 시 검사와 같은 문구를 쓴다.
 */
public final class LineInvariants {

    private LineInvariants() { }

    public static List<String> violations(List<Line> lines, Set<UUID> cashInstrumentIds, ZoneId zone) {
        List<String> found = new ArrayList<>();
        Set<String> grain = new HashSet<>();
        boolean duplicated = false, missingFx = false, cashMismatch = false, notStale = false;
        for (Line l : lines) {
            duplicated |= !grain.add(l.asOf() + "/" + l.accountId() + "/" + l.instrumentId());
            missingFx |= l.fxRate() == null || l.fxAsOf() == null;
            cashMismatch |= cashInstrumentIds.contains(l.instrumentId())
                    && l.costAmountKrw().compareTo(l.marketValueKrw()) != 0;
            notStale |= l.carriedForward() && !l.sourceAsOf().atZoneSameInstant(zone).toLocalDate().isBefore(l.asOf());
        }
        if (duplicated) found.add("그레인 유일성 위반");
        if (missingFx) found.add("fx_rate·fx_as_of 누락");
        if (cashMismatch) found.add("CASH 행의 원가 ≠ 평가금액");
        if (notStale) found.add("is_carried_forward인데 source_as_of >= as_of");
        return found;
    }
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `./gradlew test --tests '*LineInvariantsTest'`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/main/java/com/stockproject/portfolio/snapshot/LineInvariants.java src/test/java/com/stockproject/portfolio/snapshot/LineInvariantsTest.java
git commit -m "feat: 보유 라인을 쓰기 전에 정합성을 검사한다"
```

---

### Task 4: 조회 시 검증 — 편입 전 계좌는 누락이 아니다

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/query/FactCheckMapper.java` (`accountsWithoutLine`)
- Test: `src/test/java/com/stockproject/portfolio/validation/PositionLineInvariantsTest.java`

**Interfaces:**
- Produces: `FactCheckMapper.accountsWithoutLine(UserScope, LocalDate)` — 시그니처 그대로, 판정만 "그 사용자의 직전 as_of에 라인이 있는데 D에 없는 계좌"(설계 §6.1)

- [ ] **Step 1: 실패하는 테스트를 더한다**

`PositionLineInvariantsTest`에 더한다. 샘플에서 미래에셋 연금(`MIRAE`)은 07-24에 라인이 있다.

```java
    /** 직전 as_of에 라인이 없던 계좌는 그날 아직 편입 전이다 (설계 §6.1). */
    @Test
    void 직전_as_of에_라인이_없던_계좌는_누락이_아니다() {
        jdbc.sql("DELETE FROM position_line WHERE account_id = :a").param("a", MIRAE).update();

        assertThatCode(() -> invariants.validate(YHR, AS_OF)).doesNotThrowAnyException();
    }

    /** 해제했다 다시 연동한 계좌도 같다 — 몇 달 전 라인은 직전 as_of의 라인이 아니다. */
    @Test
    void 오래전에만_라인이_있던_계좌도_누락이_아니다() {
        jdbc.sql("UPDATE position_line SET as_of = DATE '2026-03-02' WHERE account_id = :a AND as_of = DATE '2026-07-24'")
                .param("a", MIRAE).update();
        jdbc.sql("DELETE FROM position_line WHERE account_id = :a AND as_of = :d")
                .param("a", MIRAE).param("d", AS_OF).update();

        assertThatCode(() -> invariants.validate(YHR, AS_OF)).doesNotThrowAnyException();
    }
```

기존 `연동된_계좌에_라인이_없으면_거부한다`의 `deleteLines(MIRAE)`가 07-24 라인까지 지우는지 확인한다. 지운다면 그 테스트는 이제 통과하지 않아야 할 상황을 만든다 — 07-27 라인만 지우도록 고친다:

```java
    @Test
    void 연동된_계좌에_라인이_없으면_거부한다() {
        jdbc.sql("DELETE FROM position_line WHERE account_id = :a AND as_of = :d")
                .param("a", MIRAE).param("d", AS_OF).update();

        assertThatThrownBy(() -> invariants.validate(YHR, AS_OF))
                .isInstanceOf(FactInvariantViolation.class)
                .hasMessageContaining("라인 없음");
    }
```

`다른_사용자의_위반은_내_검증을_깨지_않는다`의 `deleteLines(KIWOOM)`도 같은 기준으로 07-27만 지우게 한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests '*PositionLineInvariantsTest'`
Expected: 새 두 테스트 FAIL("연동된 계좌에 라인 없음")

- [ ] **Step 3: 판정을 좁힌다**

```java
    /**
     * 그 사용자의 직전 as_of에 라인이 있던 계좌는 해당 as_of에도 라인이 있다 (설계 §6.1).
     * 직전 as_of에 없던 계좌 — 첫 수집 전이거나 해제 뒤 다시 연동한 계좌 — 는 첫 라인이 생긴 날부터 편입된다.
     */
    @Select("""
            SELECT count(*) FROM account a
             WHERE a.user_id = #{scope.userId} AND a.link_state <> 'DISCONNECTED'
               AND EXISTS (SELECT 1 FROM position_line prev
                            WHERE prev.account_id = a.account_id
                              AND prev.as_of = (SELECT max(p.as_of) FROM position_line p
                                                  JOIN account o USING (account_id)
                                                 WHERE o.user_id = #{scope.userId} AND p.as_of < #{asOf}))
               AND NOT EXISTS (SELECT 1 FROM position_line pl
                                WHERE pl.as_of = #{asOf} AND pl.account_id = a.account_id)
            """)
    int accountsWithoutLine(@Param("scope") UserScope scope, @Param("asOf") LocalDate asOf);
```

- [ ] **Step 4: 통과를 확인한다**

Run: `./gradlew test --tests '*PositionLineInvariantsTest' --tests '*SixViewGoldenTest' --tests '*SnapshotViewApiTest'`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/main/java/com/stockproject/portfolio/query/FactCheckMapper.java src/test/java/com/stockproject/portfolio/validation/PositionLineInvariantsTest.java
git commit -m "fix: 직전 기준일에 라인이 없던 계좌는 그날 누락으로 보지 않는다"
```

---

### Task 5: 계좌별 뷰 `last_collection` — `CollectionRunStatusPort`

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/query/CollectionRunStatusMapper.java`
- Create: `src/main/java/com/stockproject/portfolio/query/CollectionRunStatusPort.java`
- Create: `src/main/java/com/stockproject/portfolio/query/FailureReasons.java`
- Delete: `src/main/java/com/stockproject/portfolio/query/NoCollectionStatusPort.java`
- Test: `src/test/java/com/stockproject/portfolio/query/CollectionRunStatusPortTest.java` · `FailureReasonsTest.java`

**Interfaces:**
- Consumes: `CollectionStatus(String state, LocalDate asOf, String failureReason)`, `CollectionStatusPort`
- Produces: `CollectionRunStatusPort implements CollectionStatusPort`(`@Component`), `FailureReasons.sanitize(String) : String`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.query;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/** failure_reason은 코드 모양일 때만 응답에 싣는다 (설계 §9). */
class FailureReasonsTest {

    @Test
    void 코드_모양은_그대로_아니면_UNKNOWN() {
        assertThat(FailureReasons.sanitize("SCRAPE_TIMEOUT")).isEqualTo("SCRAPE_TIMEOUT");
        assertThat(FailureReasons.sanitize(null)).isNull();
        assertThat(FailureReasons.sanitize("KeyError: '/stock-project/accounts/x'")).isEqualTo("UNKNOWN");
        assertThat(FailureReasons.sanitize("UNKNOWN_BROKER: X")).isEqualTo("UNKNOWN");
        assertThat(FailureReasons.sanitize("A".repeat(65))).isEqualTo("UNKNOWN");
    }
}
```

```java
package com.stockproject.portfolio.query;

import com.stockproject.portfolio.auth.UserScope;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;

import java.time.LocalDate;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** 계좌별 최신 수집 실행 (스펙 §7.2). 수집 결과를 저장하지 않고 collection_run에서 파생한다. */
@SpringBootTest
@ActiveProfiles("test")
@Sql("classpath:db/sample/sample_portfolio.sql")
class CollectionRunStatusPortTest {

    static final UserScope YHR = new UserScope(UUID.fromString("40000000-0000-0000-0000-000000000001"));
    static final UUID KIS_GENERAL = UUID.fromString("20000000-0000-0000-0000-000000000001");

    @Autowired CollectionStatusPort port;
    @Autowired JdbcClient jdbc;

    @Test
    void 실행이_없으면_비어_있다() {
        jdbc.sql("TRUNCATE collection_run").update();
        assertThat(port.lastCollectionByAccount(YHR)).isEmpty();
    }

    @Test
    void 요청이_가장_늦은_실행을_고르고_사유를_걸러낸다() {
        jdbc.sql("TRUNCATE collection_run").update();
        run("ar_7f3a91c4", "2026-10-13T23:00:00+09", "2026-10-13", "DONE", null);
        run("ar_7f3a91c4", "2026-10-14T23:00:00+09", "2026-10-14", "FAILED", "KeyError: boom");
        run("ar_18d9b642", "2026-10-15T23:00:00+09", "2026-10-15", "DONE", null);   // 다른 사용자

        var result = port.lastCollectionByAccount(YHR);

        assertThat(result).containsOnlyKeys(KIS_GENERAL);
        assertThat(result.get(KIS_GENERAL))
                .isEqualTo(new CollectionStatus("FAILED", LocalDate.of(2026, 10, 14), "UNKNOWN"));
    }

    void run(String ref, String requestedAt, String asOf, String state, String reason) {
        jdbc.sql("""
                INSERT INTO collection_run (run_id, account_ref, requested_by, as_of, requested_at, state, failure_reason)
                VALUES (gen_random_uuid(), :ref, 'SCHEDULE', CAST(:asOf AS date), CAST(:at AS timestamptz), :state, :reason)
                """).param("ref", ref).param("asOf", asOf).param("at", requestedAt)
                .param("state", state).param("reason", reason).update();
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests '*FailureReasonsTest' --tests '*CollectionRunStatusPortTest'`
Expected: 컴파일 실패(`FailureReasons` 없음)

- [ ] **Step 3: 구현한다**

```java
package com.stockproject.portfolio.query;

import java.util.regex.Pattern;

/**
 * collection_run.failure_reason을 응답에 실을 모양으로 거른다. 계약은 코드(SCRAPE_TIMEOUT 등)지만
 * 데이터 쪽 실제 값은 예외 메시지일 수 있어, 원천 응답이나 내부 식별자가 사용자에게 나가지 않게 한다.
 */
public final class FailureReasons {

    private static final Pattern CODE = Pattern.compile("^[A-Z][A-Z0-9_]{0,63}$");

    private FailureReasons() { }

    public static String sanitize(String raw) {
        if (raw == null) return null;
        return CODE.matcher(raw).matches() ? raw : "UNKNOWN";
    }
}
```

```java
package com.stockproject.portfolio.query;

import com.stockproject.portfolio.auth.UserScope;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

/** 계좌마다 requested_at이 가장 늦은 collection_run. */
@Mapper
public interface CollectionRunStatusMapper {

    record Latest(UUID accountId, String state, LocalDate asOf, String failureReason) { }

    @Select("""
            SELECT DISTINCT ON (a.account_id) a.account_id, r.state, r.as_of, r.failure_reason
              FROM account a JOIN collection_run r ON r.account_ref = a.account_ref
             WHERE a.user_id = #{scope.userId}
             ORDER BY a.account_id, r.requested_at DESC
            """)
    List<Latest> latest(@Param("scope") UserScope scope);
}
```

```java
package com.stockproject.portfolio.query;

import com.stockproject.portfolio.auth.UserScope;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

/** 계좌별 뷰의 last_collection (스펙 §7.2). 그 계좌의 최신 실행에서 파생하고 저장하지 않는다. */
@Component
public class CollectionRunStatusPort implements CollectionStatusPort {

    private final CollectionRunStatusMapper mapper;

    public CollectionRunStatusPort(CollectionRunStatusMapper mapper) { this.mapper = mapper; }

    @Override
    public Map<UUID, CollectionStatus> lastCollectionByAccount(UserScope scope) {
        return mapper.latest(scope).stream().collect(Collectors.toMap(
                CollectionRunStatusMapper.Latest::accountId,
                l -> new CollectionStatus(l.state(), l.asOf(), FailureReasons.sanitize(l.failureReason()))));
    }
}
```

`NoCollectionStatusPort.java`를 지운다.

- [ ] **Step 4: 통과와 골든 불변을 확인한다**

Run: `./gradlew test --tests '*FailureReasonsTest' --tests '*CollectionRunStatusPortTest' --tests '*SixViewGoldenTest' --tests '*ArchitectureRulesTest'`
Expected: PASS. 골든의 `last_collection`은 샘플에 실행이 없어 그대로 `null`이다.

- [ ] **Step 5: 커밋**

```bash
git add -A src/main/java/com/stockproject/portfolio/query src/test/java/com/stockproject/portfolio/query
git commit -m "feat: 계좌별 화면의 최근 수집 상태를 collection_run에서 읽는다"
```

---

### Task 6: 테스트 픽스처 · `credential_ref` 채우기

**Files:**
- Create: `src/test/java/com/stockproject/portfolio/snapshot/MutableClock.java`
- Create: `src/test/java/com/stockproject/portfolio/snapshot/SnapshotTestConfig.java`
- Create: `src/test/java/com/stockproject/portfolio/snapshot/SnapshotFixture.java`
- Create: `src/main/java/com/stockproject/portfolio/snapshot/RunRow.java`
- Create: `src/main/java/com/stockproject/portfolio/snapshot/CollectionRunMapper.java`
- Create: `src/main/java/com/stockproject/portfolio/snapshot/CredentialFiller.java`
- Test: `src/test/java/com/stockproject/portfolio/snapshot/CredentialFillerTest.java`

**Interfaces:**
- Produces:
  - `MutableClock extends Clock` — `set(String isoOffsetDateTime)`
  - `SnapshotFixture` (테스트 전용, `SnapshotTestConfig`가 `@Import`): `reset()`, `calendar(LocalDate, LocalDate)`, `removeCalendarDay(String)`, `sourceAsOf(UUID, String) : Instant`, `lastSyncedAt(UUID) : OffsetDateTime`, `finalizeBuilds(UUID)`, `requested(...)`, `runNotSynced(...)`, `sql(String)`, `account(UUID id, UUID user, String ref, String linkState)`, `credential(UUID account, String ref)`, `run(String ref, String by, String asOf, String requestedAt, String state, String finishedAt) : UUID`, `deposit(String ref, String currency, String amount, String at)`, `balance(String ref, UUID instrument, String qty, String avg, String value, String currency, String at)`, `fx(String asOf, String rate)`, `lines(UUID account, String asOf) : List<Map<String,Object>>`, `snapshotRun(String asOf) : boolean`, `build(UUID runId) : Map<String,Object>`, `linkState(UUID account) : String`
  - `record RunRow(UUID runId, UUID accountId, UUID userId, String accountRef, String requestedBy, LocalDate asOf, OffsetDateTime requestedAt, String state, OffsetDateTime finishedAt)`
  - `CollectionRunMapper.fillCredentials() : int`, `pending(List<String> retriable, int limit) : List<RunRow>` (Task 7에서 쓴다)
  - `CredentialFiller.fillOnce() : int`

- [ ] **Step 1: 픽스처를 만든다**

```java
package com.stockproject.portfolio.snapshot;

import java.time.Clock;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneId;

/** 테스트가 "지금"을 옮긴다 — 마감 전후를 한 테스트 안에서 본다. */
public class MutableClock extends Clock {

    private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");
    private volatile Instant now = Instant.parse("2026-10-13T14:00:00Z");

    public void set(String isoOffsetDateTime) { now = OffsetDateTime.parse(isoOffsetDateTime).toInstant(); }

    @Override public ZoneId getZone() { return SEOUL; }
    @Override public Clock withZone(ZoneId zone) { return this; }
    @Override public Instant instant() { return now; }
}
```

```java
package com.stockproject.portfolio.snapshot;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;

/** 스냅샷 생성기 테스트의 시계와 픽스처. */
@TestConfiguration
@Import(SnapshotFixture.class)
public class SnapshotTestConfig {

    @Bean
    @Primary
    MutableClock mutableClock() { return new MutableClock(); }
}
```

```java
package com.stockproject.portfolio.snapshot;

import org.springframework.jdbc.core.simple.JdbcClient;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 스냅샷 생성기 테스트 데이터. 확정 단계가 DB 전체를 보므로 공유 샘플을 쓰지 않고 매번 비우고 심는다.
 * 사용자는 V1이 심은 팀원 계정을 쓴다. 자격증명 참조는 가짜 경로만 쓴다.
 */
public class SnapshotFixture {

    public static final UUID YHR = UUID.fromString("40000000-0000-0000-0000-000000000001");
    public static final UUID JDH = UUID.fromString("40000000-0000-0000-0000-000000000002");
    public static final UUID A = UUID.fromString("30000000-0000-0000-0000-00000000000a");
    public static final UUID B = UUID.fromString("30000000-0000-0000-0000-00000000000b");
    public static final UUID C = UUID.fromString("30000000-0000-0000-0000-00000000000c");
    public static final UUID SAMSUNG = UUID.fromString("10000000-0000-0000-0000-000000000001");
    public static final UUID AAPL = UUID.fromString("10000000-0000-0000-0000-000000000004");
    public static final UUID CASH_KRW = UUID.fromString("10000000-0000-0000-0000-000000000007");
    public static final UUID CASH_USD = UUID.fromString("10000000-0000-0000-0000-000000000008");

    /** 2026-10-09(한글날)과 주말은 휴장이다. */
    private static final Set<LocalDate> HOLIDAYS = Set.of(LocalDate.of(2026, 10, 9));

    private final JdbcClient jdbc;

    public SnapshotFixture(JdbcClient jdbc) { this.jdbc = jdbc; }

    public void reset() {
        // 확정 실패 격리 테스트의 트리거가 중단된 실행 때문에 남아 있으면 지운다.
        jdbc.sql("DROP TRIGGER IF EXISTS test_fail_b ON position_line").update();
        jdbc.sql("DROP FUNCTION IF EXISTS test_fail_b()").update();
        jdbc.sql("""
                TRUNCATE position_build, realized_pnl_line, manual_cashflow, position_line, account,
                         instrument, etf_coverage, snapshot_run, dim_market_calendar,
                         collection_run, cln_balance, cln_deposit, fx_rate
                """).update();
        jdbc.sql("""
                INSERT INTO instrument (instrument_id, isin, symbol, name, asset_class, market, currency, sector, is_leveraged) VALUES
                 ('10000000-0000-0000-0000-000000000001','KR7005930003','005930','삼성전자','STOCK','KR','KRW','반도체',false),
                 ('10000000-0000-0000-0000-000000000004','US0378331005','AAPL','애플','STOCK','US','USD','IT서비스',false),
                 ('10000000-0000-0000-0000-000000000007',NULL,'CASH-KRW','KRW 예수금','CASH','KR','KRW',NULL,NULL),
                 ('10000000-0000-0000-0000-000000000008',NULL,'CASH-USD','USD 예수금','CASH','US','USD',NULL,NULL)
                """).update();
        calendar(LocalDate.of(2026, 10, 1), LocalDate.of(2026, 10, 31));
    }

    /** KR 캘린더를 [from, to]에 깐다. 범위 양끝의 직전 · 다음 영업일도 맞게 계산한다. */
    public void calendar(LocalDate from, LocalDate to) {
        for (LocalDate d = from; !d.isAfter(to); d = d.plusDays(1)) {
            jdbc.sql("""
                    INSERT INTO dim_market_calendar (market, date, is_trading_day, prev_trading_day, next_trading_day)
                    VALUES ('KR', :d, :t, :p, :n)
                    """).param("d", d).param("t", trading(d)).param("p", step(d, -1)).param("n", step(d, 1)).update();
        }
    }

    public void removeCalendarDay(String day) {
        jdbc.sql("DELETE FROM dim_market_calendar WHERE market = 'KR' AND date = CAST(:d AS date)").param("d", day).update();
    }

    public void account(UUID id, UUID user, String ref, String linkState) {
        jdbc.sql("""
                INSERT INTO account (account_id, user_id, account_ref, broker, label, account_type, source, credential_ref, link_state)
                VALUES (:id, :user, :ref, '한국투자증권', :ref, 'GENERAL', 'KIS', :cred, :state)
                """).param("id", id).param("user", user).param("ref", ref)
                .param("cred", "/stock-project/accounts/test/" + ref).param("state", linkState).update();
    }

    public UUID run(String ref, String by, String asOf, String requestedAt, String state, String finishedAt) {
        UUID id = UUID.randomUUID();
        jdbc.sql("""
                INSERT INTO collection_run (run_id, account_ref, requested_by, as_of, requested_at, state,
                                            finished_at, silver_synced_at)
                VALUES (:id, :ref, :by, CAST(:asOf AS date), CAST(:req AS timestamptz), :state,
                        CAST(:fin AS timestamptz), CASE WHEN :state = 'DONE' THEN CAST(:fin AS timestamptz) END)
                """).param("id", id).param("ref", ref).param("by", by).param("asOf", asOf)
                .param("req", requestedAt).param("state", state).param("fin", finishedAt).update();
        return id;
    }

    /** DONE인데 반영 시각이 비어 있는 실행. */
    public UUID runNotSynced(String ref, String asOf, String requestedAt, String finishedAt) {
        UUID id = run(ref, "SCHEDULE", asOf, requestedAt, "DONE", finishedAt);
        jdbc.sql("UPDATE collection_run SET silver_synced_at = NULL WHERE run_id = :id").param("id", id).update();
        return id;
    }

    public UUID requested(String ref, String by, String asOf, String requestedAt) {
        UUID id = UUID.randomUUID();
        jdbc.sql("""
                INSERT INTO collection_run (run_id, account_ref, requested_by, as_of, requested_at, state)
                VALUES (:id, :ref, :by, CAST(:asOf AS date), CAST(:req AS timestamptz), 'REQUESTED')
                """).param("id", id).param("ref", ref).param("by", by).param("asOf", asOf).param("req", requestedAt).update();
        return id;
    }

    public void deposit(String ref, String currency, String amount, String at) {
        jdbc.sql("""
                INSERT INTO cln_deposit (account_ref, currency, amount, source_as_of)
                VALUES (:ref, :cur, CAST(:amt AS numeric), CAST(:at AS timestamptz))
                """).param("ref", ref).param("cur", currency).param("amt", amount).param("at", at).update();
    }

    public void balance(String ref, UUID instrument, String qty, String avg, String value, String currency, String at) {
        jdbc.sql("""
                INSERT INTO cln_balance (account_ref, instrument_id, quantity, avg_price, market_value, currency, source_as_of, ingest_id)
                VALUES (:ref, :i, CAST(:q AS numeric), CAST(:a AS numeric), CAST(:v AS numeric), :cur, CAST(:at AS timestamptz), 'test')
                """).param("ref", ref).param("i", instrument).param("q", qty).param("a", avg).param("v", value)
                .param("cur", currency).param("at", at).update();
    }

    public void fx(String asOf, String rate) {
        jdbc.sql("""
                INSERT INTO fx_rate (as_of, currency_pair, rate_type, rate, source)
                VALUES (CAST(:d AS date), 'USD/KRW', 'BASE', CAST(:r AS numeric), 'test')
                """).param("d", asOf).param("r", rate).update();
    }

    public List<Map<String, Object>> lines(UUID account, String asOf) {
        return jdbc.sql("""
                SELECT instrument_id, quantity, market_value_krw, source_as_of, is_carried_forward, is_final
                  FROM position_line WHERE account_id = :a AND as_of = CAST(:d AS date) ORDER BY instrument_id
                """).param("a", account).param("d", asOf).query().listOfRows();
    }

    /** 그 계좌 · 날짜 라인 한 벌의 원천 시각. 한 벌은 같은 시각을 갖는다. */
    public java.time.Instant sourceAsOf(UUID account, String asOf) {
        return jdbc.sql("SELECT DISTINCT source_as_of FROM position_line WHERE account_id = :a AND as_of = CAST(:d AS date)")
                .param("a", account).param("d", asOf).query(java.time.OffsetDateTime.class).single().toInstant();
    }

    public boolean snapshotRun(String asOf) {
        return jdbc.sql("SELECT count(*) FROM snapshot_run WHERE as_of = CAST(:d AS date)")
                .param("d", asOf).query(Integer.class).single() == 1;
    }

    public Map<String, Object> build(UUID runId) {
        return jdbc.sql("SELECT outcome, reason, attempts FROM position_build WHERE run_id = :id")
                .param("id", runId).query().singleRow();
    }

    public List<Map<String, Object>> finalizeBuilds(UUID account) {
        return jdbc.sql("SELECT as_of, outcome, reason FROM position_build WHERE account_id = :a AND run_id IS NULL ORDER BY as_of")
                .param("a", account).query().listOfRows();
    }

    public String linkState(UUID account) {
        return jdbc.sql("SELECT link_state FROM account WHERE account_id = :a").param("a", account).query(String.class).single();
    }

    public String credentialOf(UUID runId) {
        return jdbc.sql("SELECT credential_ref FROM collection_run WHERE run_id = :id").param("id", runId)
                .query(String.class).optional().orElse(null);
    }

    public void sql(String statement) { jdbc.sql(statement).update(); }

    private static boolean trading(LocalDate d) {
        return d.getDayOfWeek() != DayOfWeek.SATURDAY && d.getDayOfWeek() != DayOfWeek.SUNDAY && !HOLIDAYS.contains(d);
    }

    private static LocalDate step(LocalDate d, int dir) {
        LocalDate x = d.plusDays(dir);
        while (!trading(x)) x = x.plusDays(dir);
        return x;
    }
}
```

`SnapshotFixture`를 빈으로 쓰려면 `@Import`로 충분하다(생성자 주입).

- [ ] **Step 2: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.snapshot;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

import java.util.UUID;

import static com.stockproject.portfolio.snapshot.SnapshotFixture.*;
import static org.assertj.core.api.Assertions.assertThat;

/** EOD 행에 credential_ref를 채운다 (설계 §8). */
@SpringBootTest
@ActiveProfiles("test")
@Import(SnapshotTestConfig.class)
class CredentialFillerTest {

    @Autowired SnapshotFixture f;
    @Autowired CredentialFiller filler;

    @BeforeEach
    void setUp() { f.reset(); }

    @Test
    void 연동_중이거나_연동된_계좌의_빈_요청에만_채운다() {
        f.account(A, YHR, "ar_a", "CONNECTED");
        f.account(B, YHR, "ar_b", "CONNECTING");
        f.account(C, JDH, "ar_c", "REAUTH_REQUIRED");
        UUID a = f.requested("ar_a", "SCHEDULE", "2026-10-13", "2026-10-13T23:00:00+09");
        UUID b = f.requested("ar_b", "SCHEDULE", "2026-10-13", "2026-10-13T23:00:00+09");
        UUID c = f.requested("ar_c", "SCHEDULE", "2026-10-13", "2026-10-13T23:00:00+09");
        UUID unknown = f.requested("ar_x", "SCHEDULE", "2026-10-13", "2026-10-13T23:00:00+09");
        UUID done = f.run("ar_a", "SCHEDULE", "2026-10-12", "2026-10-12T23:00:00+09", "DONE", "2026-10-12T23:10:00+09");

        assertThat(filler.fillOnce()).isEqualTo(2);

        assertThat(f.credentialOf(a)).isEqualTo("/stock-project/accounts/test/ar_a");
        assertThat(f.credentialOf(b)).isEqualTo("/stock-project/accounts/test/ar_b");
        assertThat(f.credentialOf(c)).isNull();
        assertThat(f.credentialOf(unknown)).isNull();
        assertThat(f.credentialOf(done)).isNull();
    }

    @Test
    void 이미_찬_행은_건드리지_않는다() {
        f.account(A, YHR, "ar_a", "CONNECTED");
        UUID a = f.requested("ar_a", "USER", "2026-10-13", "2026-10-13T10:00:00+09");
        f.sql("UPDATE collection_run SET credential_ref = '/stock-project/accounts/test/other' WHERE run_id = '" + a + "'");

        assertThat(filler.fillOnce()).isZero();
        assertThat(f.credentialOf(a)).isEqualTo("/stock-project/accounts/test/other");
    }
}
```

- [ ] **Step 3: 실패를 확인한다**

Run: `./gradlew test --tests '*CredentialFillerTest'`
Expected: 컴파일 실패(`CredentialFiller` 없음)

- [ ] **Step 4: `RunRow` · `CollectionRunMapper` · `CredentialFiller`를 만든다**

```java
package com.stockproject.portfolio.snapshot;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 처리할 수집 실행 한 행과 그 계좌. credential_ref를 담지 않는다 — 로그에 행을 넘겨도 자격증명 참조가 새지 않는다.
 * 로그에는 runId · accountId만 쓴다. 계좌의 연동 상태는 담지 않는다 — 처리하는 쪽이 계좌를 잠근 뒤에 읽는다.
 */
public record RunRow(UUID runId, UUID accountId, UUID userId, String accountRef,
                     String requestedBy, LocalDate asOf, OffsetDateTime requestedAt, String state,
                     OffsetDateTime finishedAt) {

    public boolean scheduled() { return "SCHEDULE".equals(requestedBy); }
}
```

```java
package com.stockproject.portfolio.snapshot;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.List;

/** data.collection_run — 백엔드가 쓰는 컬럼은 credential_ref 하나다 (데이터 요구사항 §6.10). */
@Mapper
public interface CollectionRunMapper {

    /** EOD 행에 계좌의 시크릿 매니저 파라미터 이름을 복사한다. 자격증명 값은 다루지 않는다. */
    @Update("""
            UPDATE collection_run r
               SET credential_ref = a.credential_ref
              FROM account a
             WHERE r.account_ref = a.account_ref
               AND r.state = 'REQUESTED'
               AND r.credential_ref IS NULL
               AND a.credential_ref IS NOT NULL
               AND a.link_state IN ('CONNECTING', 'CONNECTED')
            """)
    int fillCredentials();

    /**
     * 처리할 실행 (설계 §5.1). 끝났고 아직 처리하지 않은 것, 또는 재시도 사유로 남았고 그날이 확정되지 않은 것.
     * 처음 보는 실행을 재시도보다 먼저 고른다 — 재시도 행이 배치를 채워 새로 끝난 실행이 밀리지 않게 한다.
     * 백엔드가 모르는 account_ref의 행은 고르지 않는다.
     */
    @Select("""
            <script>
            SELECT r.run_id, a.account_id, a.user_id, a.account_ref, r.requested_by,
                   r.as_of, r.requested_at, r.state, r.finished_at
              FROM collection_run r
              JOIN account a ON a.account_ref = r.account_ref
              LEFT JOIN position_build b ON b.run_id = r.run_id
             WHERE ((r.state = 'DONE' AND r.silver_synced_at IS NOT NULL) OR r.state IN ('FAILED', 'REAUTH_REQUIRED'))
               AND (b.run_id IS NULL
                    OR (b.outcome = 'SKIPPED'
                        AND b.reason IN <foreach collection="retriable" item="x" open="(" separator="," close=")">#{x}</foreach>
                        AND NOT EXISTS (SELECT 1 FROM snapshot_run s WHERE s.as_of = r.as_of)))
             ORDER BY (b.run_id IS NOT NULL), r.finished_at, r.run_id
             LIMIT #{limit}
            </script>
            """)
    List<RunRow> pending(@Param("retriable") List<String> retriable, @Param("limit") int limit);
}
```

```java
package com.stockproject.portfolio.snapshot;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * 데이터가 만든 EOD 행에 credential_ref를 채운다 (설계 §8). 데이터 워커가 이 값이 찬 REQUESTED만 집어야 쓸모가 있다.
 * 로그에는 건수만 쓴다.
 */
@Component
public class CredentialFiller {

    private static final Logger log = LoggerFactory.getLogger(CredentialFiller.class);

    private final CollectionRunMapper runs;

    public CredentialFiller(CollectionRunMapper runs) { this.runs = runs; }

    public int fillOnce() {
        int filled = runs.fillCredentials();
        if (filled > 0) log.info("수집 요청 {}건에 자격증명 참조를 채웠다", filled);
        return filled;
    }
}
```

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test --tests '*CredentialFillerTest'`
Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add src/main/java/com/stockproject/portfolio/snapshot src/test/java/com/stockproject/portfolio/snapshot
git commit -m "feat: EOD 수집 요청에 자격증명 참조를 채운다"
```

---

### Task 7: 실행 처리 — 라인 쓰기와 거르기

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/snapshot/{BalanceMapper,PositionWriteMapper,PositionBuildMapper,ExistingBuild,RunProcessor,SnapshotProperties}.java`
- Test: `src/test/java/com/stockproject/portfolio/snapshot/RunProcessorTest.java`

**Interfaces:**
- Consumes: Task 2 · 3 · 6의 타입, `MarketDataMapper.calendar(String market, LocalDate from, LocalDate to) : List<CalendarDay>`, `SnapshotRunMapper`
- Produces:
  - `record SnapshotProperties(LocalTime finalizeAt, int batchSize)` — `@ConfigurationProperties("portfolio.snapshot")`, 기본 `08:00` · `100`
  - `PositionWriteMapper`: `lockDateShared(LocalDate)`, `lockDateExclusive(LocalDate)`, `lockUserAccounts(UUID userId)`, `lockAccount(UUID accountId)`, `lines(UUID accountId, LocalDate asOf) : List<Line>`, `delete(UUID accountId, LocalDate asOf)`, `insert(Line)`, `promote(UUID accountId, LocalDate asOf)`, `touchLastSynced(UUID accountId, OffsetDateTime at)`, `linkState(UUID accountId) : String`, `userPreviousAsOf(UUID userId, LocalDate asOf) : LocalDate`, `markConnected(UUID accountId, String accountRef, OffsetDateTime requestedAt)`, `markReauthRequired(UUID accountId, String accountRef, OffsetDateTime requestedAt)`, `siblingsToCarry(UUID userId, UUID accountId, LocalDate asOf, LocalDate userPrev) : List<UUID>`, `snapshotRunExists(LocalDate) : boolean`
  - `PositionBuildMapper`: `existing(UUID runId) : ExistingBuild`, `record(UUID runId, UUID accountId, LocalDate asOf, String outcome, String reason, OffsetDateTime at)`, `recordFinalize(UUID accountId, LocalDate asOf, String outcome, String reason, OffsetDateTime at)`
  - `RunProcessor.processOnce() : int`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.snapshot;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

import java.util.Map;
import java.util.UUID;

import static com.stockproject.portfolio.snapshot.SnapshotFixture.*;
import static org.assertj.core.api.Assertions.assertThat;

/** 수집 실행 한 행의 처리 (설계 §5). */
@SpringBootTest
@ActiveProfiles("test")
@Import(SnapshotTestConfig.class)
class RunProcessorTest {

    static final String D = "2026-10-13";
    static final String T = "2026-10-13T23:05:00+09";

    @Autowired SnapshotFixture f;
    @Autowired RunProcessor processor;
    @Autowired MutableClock clock;

    @BeforeEach
    void setUp() {
        f.reset();
        clock.set("2026-10-13T23:30:00+09:00");
        f.account(A, YHR, "ar_a", "CONNECTED");
    }

    @Test
    void EOD_성공은_확정_라인을_쓴다() {
        f.deposit("ar_a", "KRW", "1000", T);
        f.balance("ar_a", SAMSUNG, "10", "60000", "640000", "KRW", T);
        UUID run = f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");

        assertThat(processor.processOnce()).isEqualTo(1);

        assertThat(f.lines(A, D)).hasSize(2).allSatisfy(l -> {
            assertThat(l.get("is_final")).isEqualTo(true);
            assertThat(l.get("is_carried_forward")).isEqualTo(false);
        });
        assertThat(f.build(run)).containsEntry("outcome", "BUILT");
        assertThat(processor.processOnce()).isZero();
    }

    @Test
    void 수동_성공은_잠정_라인을_쓰고_같은_날_확정이_있으면_건너뛴다() {
        f.deposit("ar_a", "KRW", "1000", T);
        f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        processor.processOnce();
        f.deposit("ar_a", "KRW", "2000", "2026-10-13T23:20:00+09");
        UUID user = f.run("ar_a", "USER", D, "2026-10-13T23:15:00+09", "DONE", "2026-10-13T23:21:00+09");

        processor.processOnce();

        assertThat(f.build(user)).containsEntry("reason", "FINAL_EXISTS");
        assertThat(f.lines(A, D)).singleElement().satisfies(l ->
                assertThat((java.math.BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("1000"));
    }

    @Test
    void 수동_성공은_is_final_false() {
        f.deposit("ar_a", "KRW", "1000", "2026-10-13T14:01:00+09");
        f.run("ar_a", "USER", D, "2026-10-13T14:00:00+09", "DONE", "2026-10-13T14:02:00+09");

        processor.processOnce();

        assertThat(f.lines(A, D)).singleElement().satisfies(l -> assertThat(l.get("is_final")).isEqualTo(false));
    }

    @Test
    void 실패는_라인을_건드리지_않고_RUN_NOT_DONE() {
        UUID run = f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "FAILED", "2026-10-13T23:10:00+09");

        processor.processOnce();

        assertThat(f.lines(A, D)).isEmpty();
        assertThat(f.build(run)).containsEntry("outcome", "SKIPPED").containsEntry("reason", "RUN_NOT_DONE");
    }

    @Test
    void 반영_전_DONE은_고르지_않는다() {
        f.runNotSynced("ar_a", D, "2026-10-13T23:00:00+09", "2026-10-13T23:10:00+09");
        assertThat(processor.processOnce()).isZero();
    }

    @Test
    void 비영업일은_NOT_TRADING_DAY() {
        UUID run = f.run("ar_a", "USER", "2026-10-10", "2026-10-10T10:00:00+09", "DONE", "2026-10-10T10:05:00+09");
        f.deposit("ar_a", "KRW", "1", "2026-10-10T10:01:00+09");

        processor.processOnce();

        assertThat(f.build(run)).containsEntry("reason", "NOT_TRADING_DAY");
        assertThat(f.lines(A, "2026-10-10")).isEmpty();
    }

    @Test
    void 캘린더에_없는_날은_CALENDAR_UNKNOWN으로_다시_시도한다() {
        f.removeCalendarDay(D);
        f.deposit("ar_a", "KRW", "1", T);
        UUID run = f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        processor.processOnce();
        assertThat(f.build(run)).containsEntry("reason", "CALENDAR_UNKNOWN");

        f.calendar(java.time.LocalDate.parse(D), java.time.LocalDate.parse(D));
        processor.processOnce();

        assertThat(f.build(run)).containsEntry("outcome", "BUILT").containsEntry("attempts", 2);
    }

    @Test
    void 해제된_계좌는_DISCONNECTED() {
        f.sql("UPDATE account SET link_state = 'DISCONNECTED'");
        f.deposit("ar_a", "KRW", "1", T);
        UUID run = f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");

        processor.processOnce();

        assertThat(f.build(run)).containsEntry("reason", "DISCONNECTED");
        assertThat(f.linkState(A)).isEqualTo("DISCONNECTED");
    }

    @Test
    void 확정된_날의_실행은_FINAL_EXISTS() {
        f.sql("INSERT INTO snapshot_run (as_of, finished_at) VALUES (DATE '2026-10-13', now())");
        f.deposit("ar_a", "KRW", "1", T);
        UUID run = f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");

        processor.processOnce();

        assertThat(f.build(run)).containsEntry("reason", "FINAL_EXISTS");
    }

    @Test
    void 종목_미매칭은_다음_회차에_다시_시도해_성공한다() {
        UUID later = UUID.fromString("10000000-0000-0000-0000-000000000099");
        f.deposit("ar_a", "KRW", "1", T);
        f.balance("ar_a", later, "1", "1", "1", "KRW", T);
        UUID run = f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        processor.processOnce();
        assertThat(f.build(run)).containsEntry("reason", "UNMATCHED_INSTRUMENT");

        f.sql("""
                INSERT INTO instrument (instrument_id, symbol, name, asset_class, market, currency)
                VALUES ('10000000-0000-0000-0000-000000000099','NEW','신규상장','STOCK','KR','KRW')
                """);
        processor.processOnce();

        assertThat(f.build(run)).containsEntry("outcome", "BUILT").containsEntry("attempts", 2);
    }

    @Test
    void 잔고가_요청보다_이르면_STALE_BALANCE() {
        f.deposit("ar_a", "KRW", "1", "2026-10-10T15:00:00+09");
        UUID run = f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");

        processor.processOnce();

        assertThat(f.build(run)).containsEntry("reason", "STALE_BALANCE");
        assertThat(f.lines(A, D)).isEmpty();
    }

    @Test
    void 뒤_실행이_쓴_잔고는_보지_않는다() {
        f.deposit("ar_a", "KRW", "1000", T);
        f.deposit("ar_a", "KRW", "9999", "2026-10-13T23:40:00+09");
        f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");

        processor.processOnce();

        assertThat(f.lines(A, D)).singleElement().satisfies(l ->
                assertThat((java.math.BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("1000"));
    }

    @Test
    void 연동_상태는_DONE이면_CONNECTED로_REAUTH면_재인증_필요로() {
        f.account(B, YHR, "ar_b", "CONNECTING");
        f.deposit("ar_b", "KRW", "1", T);
        f.run("ar_b", "USER", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "REAUTH_REQUIRED", "2026-10-13T23:01:00+09");

        processor.processOnce();

        assertThat(f.linkState(B)).isEqualTo("CONNECTED");
        assertThat(f.linkState(A)).isEqualTo("REAUTH_REQUIRED");
    }

    @Test
    void 옛_REAUTH_실행이_늦게_처리돼도_최신이_아니면_상태를_되돌리지_않는다() {
        f.run("ar_a", "SCHEDULE", "2026-10-12", "2026-10-12T23:00:00+09", "REAUTH_REQUIRED", "2026-10-13T23:20:00+09");
        f.requested("ar_a", "USER", D, "2026-10-13T10:00:00+09");

        processor.processOnce();

        assertThat(f.linkState(A)).isEqualTo("CONNECTED");
    }

    @Test
    void DONE이면_마지막_동기화_시각을_올린다() {
        f.deposit("ar_a", "KRW", "1", T);
        f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");

        processor.processOnce();

        assertThat(f.lastSyncedAt(A).toInstant())
                .isEqualTo(java.time.OffsetDateTime.parse("2026-10-13T23:10:00+09:00").toInstant());
    }

    @Test
    void 주말_수동_동기화도_마지막_동기화_시각을_올린다() {
        f.run("ar_a", "USER", "2026-10-10", "2026-10-10T10:00:00+09", "DONE", "2026-10-10T10:05:00+09");

        processor.processOnce();

        assertThat(f.lastSyncedAt(A).toInstant())
                .isEqualTo(java.time.OffsetDateTime.parse("2026-10-10T10:05:00+09:00").toInstant());
    }

    @Test
    void 처리하는_사이_해제된_계좌는_라인을_쓰지_않는다() {
        f.deposit("ar_a", "KRW", "1", T);
        UUID run = f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        f.sql("UPDATE account SET link_state = 'DISCONNECTED'");

        processor.processOnce();

        assertThat(f.build(run)).containsEntry("reason", "DISCONNECTED");
        assertThat(f.lines(A, D)).isEmpty();
    }
}
```

`SnapshotFixture`에 더한다:

```java
    public java.time.OffsetDateTime lastSyncedAt(UUID account) {
        return jdbc.sql("SELECT last_synced_at FROM account WHERE account_id = :a").param("a", account)
                .query(java.time.OffsetDateTime.class).single();
    }
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests '*RunProcessorTest'`
Expected: 컴파일 실패(`RunProcessor` 없음)

- [ ] **Step 3: 설정 · 매퍼를 만든다**

```java
package com.stockproject.portfolio.snapshot;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

import java.time.LocalTime;

/** 보유 스냅샷 생성기 설정 (설계 §10). 잡을 켜고 끄는 값은 SnapshotRuntimeConfig가 따로 본다. */
@ConfigurationProperties("portfolio.snapshot")
public record SnapshotProperties(@DefaultValue("08:00") LocalTime finalizeAt,
                                 @DefaultValue("100") int batchSize) { }
```

```java
package com.stockproject.portfolio.snapshot;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** 잔고 한 벌과 대조할 마스터 (설계 §4.1 · §5.2). data 스키마를 읽기만 한다. */
@Mapper
public interface BalanceMapper {

    record CashInstrument(UUID instrumentId, String currency) { }

    /** 잔고 시각 — 그 실행이 끝나기 전에 쓰인 예수금의 가장 늦은 원천 시각. */
    @Select("""
            SELECT max(source_as_of) FROM cln_deposit
             WHERE account_ref = #{accountRef} AND source_as_of <= #{finishedAt}
            """)
    OffsetDateTime depositTime(@Param("accountRef") String accountRef, @Param("finishedAt") OffsetDateTime finishedAt);

    @Select("""
            SELECT instrument_id, quantity, avg_price, market_value, currency FROM cln_balance
             WHERE account_ref = #{accountRef} AND source_as_of = #{at} ORDER BY instrument_id
            """)
    List<BalanceRow> balances(@Param("accountRef") String accountRef, @Param("at") OffsetDateTime at);

    @Select("""
            SELECT currency, amount FROM cln_deposit
             WHERE account_ref = #{accountRef} AND source_as_of = #{at} ORDER BY currency
            """)
    List<DepositRow> deposits(@Param("accountRef") String accountRef, @Param("at") OffsetDateTime at);

    @Select("""
            <script>
            SELECT instrument_id FROM instrument WHERE instrument_id IN
            <foreach collection="ids" item="id" open="(" separator="," close=")">#{id}</foreach>
            </script>
            """)
    List<UUID> existing(@Param("ids") List<UUID> ids);

    @Select("SELECT instrument_id, currency FROM instrument WHERE asset_class = 'CASH'")
    List<CashInstrument> cashInstruments();

    /** 그날 이하 최신 USD/KRW BASE (스펙 §5.3 폴백). */
    @Select("""
            SELECT rate, as_of FROM fx_rate
             WHERE currency_pair = 'USD/KRW' AND rate_type = 'BASE' AND as_of <= #{asOf}
             ORDER BY as_of DESC LIMIT 1
            """)
    FxQuote usdKrw(@Param("asOf") LocalDate asOf);
}
```

```java
package com.stockproject.portfolio.snapshot;

import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 보유 라인 쓰기와 잠금 (설계 §7). 잠금은 항상 날짜 → 계좌(account_id 순) 순서로 잡는다.
 * 날짜 잠금은 실행 처리 · 계좌 확정이 공유로, 날짜 확정이 배타로 잡는다 — 확정된 날의 라인이 바뀌지 않는다.
 */
@Mapper
public interface PositionWriteMapper {

    /** advisory lock 키의 첫 칸. 다른 advisory lock(hashtext 한 칸 키)과 겹치지 않게 두 칸 키를 쓴다. */
    int LOCK_SPACE = 0x534E4150;   // 'SNAP'

    @Select("SELECT pg_advisory_xact_lock_shared(" + LOCK_SPACE + ", #{asOf} - DATE '2000-01-01')::text")
    String lockDateShared(@Param("asOf") LocalDate asOf);

    @Select("SELECT pg_advisory_xact_lock(" + LOCK_SPACE + ", #{asOf} - DATE '2000-01-01')::text")
    String lockDateExclusive(@Param("asOf") LocalDate asOf);

    @Select("SELECT account_id FROM account WHERE user_id = #{userId} ORDER BY account_id FOR UPDATE")
    List<UUID> lockUserAccounts(@Param("userId") UUID userId);

    @Select("SELECT account_id FROM account WHERE account_id = #{accountId} FOR UPDATE")
    UUID lockAccount(@Param("accountId") UUID accountId);

    @Select("SELECT EXISTS (SELECT 1 FROM snapshot_run WHERE as_of = #{asOf})")
    boolean snapshotRunExists(@Param("asOf") LocalDate asOf);

    @Select("""
            SELECT as_of, account_id, instrument_id, quantity, cost_amount_local, market_value_local,
                   cost_amount_krw, market_value_krw, fx_rate, fx_as_of, source_as_of,
                   is_carried_forward AS carried_forward, is_final
              FROM position_line WHERE account_id = #{accountId} AND as_of = #{asOf}
             ORDER BY instrument_id
            """)
    List<Line> lines(@Param("accountId") UUID accountId, @Param("asOf") LocalDate asOf);

    @Delete("DELETE FROM position_line WHERE account_id = #{accountId} AND as_of = #{asOf}")
    int delete(@Param("accountId") UUID accountId, @Param("asOf") LocalDate asOf);

    @Insert("""
            INSERT INTO position_line (as_of, account_id, instrument_id, quantity, cost_amount_local,
                market_value_local, cost_amount_krw, market_value_krw, fx_rate, fx_as_of, source_as_of,
                is_carried_forward, is_final)
            VALUES (#{asOf}, #{accountId}, #{instrumentId}, #{quantity}, #{costAmountLocal},
                #{marketValueLocal}, #{costAmountKrw}, #{marketValueKrw}, #{fxRate}, #{fxAsOf}, #{sourceAsOf},
                #{carriedForward}, #{isFinal})
            """)
    int insert(Line line);

    @Update("UPDATE position_line SET is_final = true WHERE account_id = #{accountId} AND as_of = #{asOf}")
    int promote(@Param("accountId") UUID accountId, @Param("asOf") LocalDate asOf);

    @Select("SELECT link_state FROM account WHERE account_id = #{accountId}")
    String linkState(@Param("accountId") UUID accountId);

    /** 그 사용자의 직전 기준일 — 그 사용자의 계좌에 라인이 있는 날 가운데 asOf보다 이른 가장 늦은 날. */
    @Select("""
            SELECT max(p.as_of) FROM position_line p JOIN account a USING (account_id)
             WHERE a.user_id = #{userId} AND p.as_of < #{asOf}
            """)
    LocalDate userPreviousAsOf(@Param("userId") UUID userId, @Param("asOf") LocalDate asOf);

    @Update("""
            UPDATE account SET last_synced_at = #{at}
             WHERE account_id = #{accountId} AND (last_synced_at IS NULL OR last_synced_at < #{at})
            """)
    int touchLastSynced(@Param("accountId") UUID accountId, @Param("at") OffsetDateTime at);

    /** 그 계좌에서 요청이 가장 늦은 실행일 때만 옮긴다 (설계 §9). */
    @Update("""
            UPDATE account a SET link_state = 'CONNECTED'
             WHERE a.account_id = #{accountId} AND a.link_state = 'CONNECTING'
               AND NOT EXISTS (SELECT 1 FROM collection_run r
                                WHERE r.account_ref = #{accountRef} AND r.requested_at > #{requestedAt})
            """)
    int markConnected(@Param("accountId") UUID accountId, @Param("accountRef") String accountRef,
                      @Param("requestedAt") OffsetDateTime requestedAt);

    @Update("""
            UPDATE account a SET link_state = 'REAUTH_REQUIRED'
             WHERE a.account_id = #{accountId} AND a.link_state IN ('CONNECTING', 'CONNECTED')
               AND NOT EXISTS (SELECT 1 FROM collection_run r
                                WHERE r.account_ref = #{accountRef} AND r.requested_at > #{requestedAt})
            """)
    int markReauthRequired(@Param("accountId") UUID accountId, @Param("accountRef") String accountRef,
                           @Param("requestedAt") OffsetDateTime requestedAt);

    /**
     * 잠정 이월할 같은 사용자의 다른 계좌 (설계 §5.6). 기준은 사용자의 직전 기준일이다 — 조회 시 검증
     * (FactCheckMapper.accountsWithoutLine)이 요구하는 계좌와 같아야 화면이 뜬다.
     */
    @Select("""
            SELECT a.account_id FROM account a
             WHERE a.user_id = #{userId} AND a.account_id <> #{accountId} AND a.link_state <> 'DISCONNECTED'
               AND EXISTS (SELECT 1 FROM position_line p WHERE p.account_id = a.account_id AND p.as_of = #{userPrev})
               AND NOT EXISTS (SELECT 1 FROM position_line p WHERE p.account_id = a.account_id AND p.as_of = #{asOf})
             ORDER BY a.account_id
            """)
    List<UUID> siblingsToCarry(@Param("userId") UUID userId, @Param("accountId") UUID accountId,
                               @Param("asOf") LocalDate asOf, @Param("userPrev") LocalDate userPrev);
}
```

`#{asOf} - DATE '2000-01-01'`은 정수(일 수)다. `LocalDate` 파라미터가 `date`로 바인딩되는지 Step 5에서 함께 확인한다 — 오류가 나면 `CAST(#{asOf} AS date)`로 감싼다.

```java
package com.stockproject.portfolio.snapshot;

/** position_build에 이미 남은 처리 기록. 재시도 사유일 때만 다시 처리한다. */
public record ExistingBuild(String outcome, String reason) {

    public boolean finalOutcome() {
        return !("SKIPPED".equals(outcome) && reason != null && BuildReason.valueOf(reason).retriable());
    }
}
```

```java
package com.stockproject.portfolio.snapshot;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

/** 처리 기록 (설계 §4.3). */
@Mapper
public interface PositionBuildMapper {

    @Select("SELECT outcome, reason FROM position_build WHERE run_id = #{runId}")
    ExistingBuild existing(@Param("runId") UUID runId);

    /** 재시도면 결과를 바꾸고 attempts를 올린다. 호출자가 계좌 잠금 안에서 existing()을 먼저 확인한다. */
    @Insert("""
            INSERT INTO position_build (run_id, account_id, as_of, outcome, reason, built_at)
            VALUES (#{runId}, #{accountId}, #{asOf}, #{outcome}, #{reason}, #{at})
            ON CONFLICT (run_id) DO UPDATE
               SET outcome = EXCLUDED.outcome, reason = EXCLUDED.reason,
                   attempts = position_build.attempts + 1, built_at = EXCLUDED.built_at
            """)
    int record(@Param("runId") UUID runId, @Param("accountId") UUID accountId, @Param("asOf") LocalDate asOf,
               @Param("outcome") String outcome, @Param("reason") String reason, @Param("at") OffsetDateTime at);

    @Insert("""
            INSERT INTO position_build (run_id, account_id, as_of, outcome, reason, built_at)
            VALUES (NULL, #{accountId}, #{asOf}, #{outcome}, #{reason}, #{at})
            ON CONFLICT (account_id, as_of) WHERE run_id IS NULL DO NOTHING
            """)
    int recordFinalize(@Param("accountId") UUID accountId, @Param("asOf") LocalDate asOf,
                       @Param("outcome") String outcome, @Param("reason") String reason,
                       @Param("at") OffsetDateTime at);
}
```

- [ ] **Step 4: `RunProcessor`를 만든다 (잠정 이월 · 순서 역전은 Task 8)**

```java
package com.stockproject.portfolio.snapshot;

import com.stockproject.portfolio.alert.data.CalendarDay;
import com.stockproject.portfolio.alert.data.MarketDataMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Clock;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * 끝난 수집 실행 한 행을 처리한다 (설계 §5). 실행 하나가 트랜잭션 하나다 — 한 실행이 실패해도 다음 실행은 진행한다.
 * 확정 이월은 여기서 하지 않는다. 날짜 순서로 도는 Finalizer가 한다.
 */
@Component
public class RunProcessor {

    private static final Logger log = LoggerFactory.getLogger(RunProcessor.class);
    static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

    private final CollectionRunMapper runs;
    private final BalanceMapper balances;
    private final PositionWriteMapper positions;
    private final PositionBuildMapper builds;
    private final MarketDataMapper market;
    private final SnapshotProperties props;
    private final TransactionTemplate tx;
    private final Clock clock;

    public RunProcessor(CollectionRunMapper runs, BalanceMapper balances, PositionWriteMapper positions,
                        PositionBuildMapper builds, MarketDataMapper market, SnapshotProperties props,
                        TransactionTemplate tx, Clock clock) {
        this.runs = runs;
        this.balances = balances;
        this.positions = positions;
        this.builds = builds;
        this.market = market;
        this.props = props;
        this.tx = tx;
        this.clock = clock;
    }

    /** 한 회차. 처리한 실행 수를 돌려준다. */
    public int processOnce() {
        int done = 0;
        for (RunRow run : runs.pending(BuildReason.retriableNames(), props.batchSize())) {
            try {
                Boolean processed = tx.execute(s -> process(run));
                if (Boolean.TRUE.equals(processed)) done++;
            } catch (RuntimeException e) {
                log.warn("수집 실행 처리 실패 run={} account={} 사유={}", run.runId(), run.accountId(), e.getClass().getSimpleName());
            }
        }
        return done;
    }

    private boolean process(RunRow run) {
        positions.lockDateShared(run.asOf());
        positions.lockUserAccounts(run.userId());
        ExistingBuild existing = builds.existing(run.runId());
        if (existing != null && existing.finalOutcome()) return false;

        Decision d = decide(run, positions.linkState(run.accountId()));
        builds.record(run.runId(), run.accountId(), run.asOf(), d.outcome().name(),
                d.reason() == null ? null : d.reason().name(), OffsetDateTime.now(clock));
        return true;
    }

    private record Decision(BuildOutcome outcome, BuildReason reason) {
        static Decision skipped(BuildReason r) { return new Decision(BuildOutcome.SKIPPED, r); }
        static final Decision BUILT = new Decision(BuildOutcome.BUILT, null);
    }

    /** linkState는 계좌를 잠근 뒤에 읽은 값이다. */
    private Decision decide(RunRow run, String linkState) {
        if ("DISCONNECTED".equals(linkState)) return Decision.skipped(BuildReason.DISCONNECTED);
        transitionLinkState(run);
        if ("DONE".equals(run.state())) positions.touchLastSynced(run.accountId(), run.finishedAt());
        if (positions.snapshotRunExists(run.asOf())) return Decision.skipped(BuildReason.FINAL_EXISTS);

        CalendarDay day = calendarDay(run.asOf());
        if (day == null) return Decision.skipped(BuildReason.CALENDAR_UNKNOWN);
        if (!day.isTradingDay()) return Decision.skipped(BuildReason.NOT_TRADING_DAY);
        if (!"DONE".equals(run.state())) return Decision.skipped(BuildReason.RUN_NOT_DONE);

        List<Line> current = positions.lines(run.accountId(), run.asOf());
        if (!run.scheduled() && current.stream().anyMatch(Line::isFinal)) {
            return Decision.skipped(BuildReason.FINAL_EXISTS);
        }

        BalanceSet set = loadSet(run);
        Calculation calc = LineCalculator.calculate(run.accountId(), run.asOf(), run.requestedAt(), set,
                reference(set, run.asOf()), run.scheduled());
        if (calc instanceof Calculation.Failed f) return Decision.skipped(f.reason());
        List<Line> lines = ((Calculation.Lines) calc).lines();

        List<String> violations = LineInvariants.violations(lines, cashIds(), SEOUL);
        if (!violations.isEmpty()) {
            log.warn("쓰기 전 검사 위반 run={} account={} {}", run.runId(), run.accountId(), violations);
            return Decision.skipped(BuildReason.INVARIANT);
        }

        positions.delete(run.accountId(), run.asOf());
        lines.forEach(positions::insert);
        return Decision.BUILT;
    }

    private void transitionLinkState(RunRow run) {
        if ("DONE".equals(run.state())) positions.markConnected(run.accountId(), run.accountRef(), run.requestedAt());
        if ("REAUTH_REQUIRED".equals(run.state())) positions.markReauthRequired(run.accountId(), run.accountRef(), run.requestedAt());
    }

    private CalendarDay calendarDay(LocalDate day) {
        List<CalendarDay> rows = market.calendar("KR", day, day);
        return rows.isEmpty() ? null : rows.get(0);
    }

    private BalanceSet loadSet(RunRow run) {
        OffsetDateTime t = balances.depositTime(run.accountRef(), run.finishedAt());
        if (t == null) return null;
        return new BalanceSet(t, balances.balances(run.accountRef(), t), balances.deposits(run.accountRef(), t));
    }

    private Reference reference(BalanceSet set, LocalDate asOf) {
        List<UUID> ids = set == null ? List.of() : set.balances().stream()
                .map(BalanceRow::instrumentId).filter(java.util.Objects::nonNull).distinct().toList();
        Set<UUID> known = ids.isEmpty() ? Set.of() : new HashSet<>(balances.existing(ids));
        Map<String, List<UUID>> cash = balances.cashInstruments().stream().collect(Collectors.groupingBy(
                BalanceMapper.CashInstrument::currency,
                Collectors.mapping(BalanceMapper.CashInstrument::instrumentId, Collectors.toList())));
        return new Reference(known, cash, balances.usdKrw(asOf));
    }

    private Set<UUID> cashIds() {
        return balances.cashInstruments().stream().map(BalanceMapper.CashInstrument::instrumentId)
                .collect(Collectors.toSet());
    }
}
```

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test --tests '*RunProcessorTest'`
Expected: PASS. `SnapshotProperties` 빈은 `@ConfigurationPropertiesScan`(`PortfolioApplication`)이 등록한다.

- [ ] **Step 6: 커밋**

```bash
git add src/main/java/com/stockproject/portfolio/snapshot src/test/java/com/stockproject/portfolio/snapshot
git commit -m "feat: 끝난 수집 실행으로 보유 라인을 쓴다"
```

---

### Task 8: 실행 처리 — 같은 사용자 잠정 이월 · 순서 역전

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/snapshot/RunProcessor.java` (`decide`)
- Test: `src/test/java/com/stockproject/portfolio/snapshot/RunProcessorProvisionalTest.java`
- Test: `src/test/java/com/stockproject/portfolio/api/SnapshotBuilderAccountsViewTest.java`

**Interfaces:**
- Consumes: `PositionWriteMapper.siblingsToCarry` · `userPreviousAsOf`, `Line.carriedTo` (Task 2 · 7)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.snapshot;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

import java.math.BigDecimal;
import java.util.UUID;

import static com.stockproject.portfolio.snapshot.SnapshotFixture.*;
import static org.assertj.core.api.Assertions.assertThat;

/** 한 계좌만 그날 라인을 얻을 때 다른 계좌의 잠정 이월과, 순서가 뒤집힌 처리 (설계 §5.1 · §5.6). */
@SpringBootTest
@ActiveProfiles("test")
@Import(SnapshotTestConfig.class)
class RunProcessorProvisionalTest {

    static final String PREV = "2026-10-12";
    static final String D = "2026-10-13";

    @Autowired SnapshotFixture f;
    @Autowired RunProcessor processor;
    @Autowired MutableClock clock;

    @BeforeEach
    void setUp() {
        f.reset();
        clock.set("2026-10-13T14:30:00+09:00");
        f.account(A, YHR, "ar_a", "CONNECTED");
        f.account(B, YHR, "ar_b", "CONNECTED");
        f.account(C, JDH, "ar_c", "CONNECTED");
        // 10-12 확정본: 세 계좌 모두 예수금만
        for (String ref : new String[]{"ar_a", "ar_b", "ar_c"}) {
            f.deposit(ref, "KRW", "100", "2026-10-12T23:05:00+09");
            f.run(ref, "SCHEDULE", PREV, "2026-10-12T23:00:00+09", "DONE", "2026-10-12T23:10:00+09");
        }
        processor.processOnce();
        f.sql("INSERT INTO snapshot_run (as_of, finished_at) VALUES (DATE '2026-10-12', now())");
    }

    @Test
    void A만_새로고침하면_같은_사용자의_B는_잠정_이월되고_다른_사용자는_그대로다() {
        f.deposit("ar_a", "KRW", "500", "2026-10-13T14:01:00+09");
        f.run("ar_a", "USER", D, "2026-10-13T14:00:00+09", "DONE", "2026-10-13T14:02:00+09");

        processor.processOnce();

        assertThat(f.lines(A, D)).singleElement().satisfies(l -> {
            assertThat((BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("500");
            assertThat(l.get("is_carried_forward")).isEqualTo(false);
            assertThat(l.get("is_final")).isEqualTo(false);
        });
        assertThat(f.lines(B, D)).singleElement().satisfies(l -> {
            assertThat((BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("100");
            assertThat(l.get("is_carried_forward")).isEqualTo(true);
            assertThat(l.get("is_final")).isEqualTo(false);
        });
        assertThat(f.lines(C, D)).isEmpty();
    }

    @Test
    void 직전_영업일이_확정_전인_아침에도_그_전_기준일_값으로_잠정_이월한다() {
        // 10-13에는 라인이 없다(확정 전). 10-14 07:00에 A만 새로고침한다.
        clock.set("2026-10-14T07:00:00+09:00");
        f.deposit("ar_a", "KRW", "500", "2026-10-14T06:58:00+09");
        f.run("ar_a", "USER", "2026-10-14", "2026-10-14T06:55:00+09", "DONE", "2026-10-14T07:00:00+09");

        processor.processOnce();

        assertThat(f.lines(B, "2026-10-14")).singleElement().satisfies(l -> {
            assertThat((BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("100");
            assertThat(l.get("is_carried_forward")).isEqualTo(true);
        });
        assertThat(f.sourceAsOf(B, "2026-10-14"))
                .isEqualTo(java.time.OffsetDateTime.parse("2026-10-12T23:05:00+09:00").toInstant());
    }

    @Test
    void 잠정_이월된_B는_그날_B의_실행이_새_값으로_덮는다() {
        f.deposit("ar_a", "KRW", "500", "2026-10-13T14:01:00+09");
        f.run("ar_a", "USER", D, "2026-10-13T14:00:00+09", "DONE", "2026-10-13T14:02:00+09");
        processor.processOnce();

        f.deposit("ar_b", "KRW", "700", "2026-10-13T23:05:00+09");
        f.run("ar_b", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        processor.processOnce();

        assertThat(f.lines(B, D)).singleElement().satisfies(l -> {
            assertThat((BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("700");
            assertThat(l.get("is_carried_forward")).isEqualTo(false);
            assertThat(l.get("is_final")).isEqualTo(true);
        });
    }

    @Test
    void 해제된_계좌와_직전_기준일에_라인이_없는_계좌는_잠정_이월하지_않는다() {
        f.sql("UPDATE account SET link_state = 'DISCONNECTED' WHERE account_ref = 'ar_b'");
        UUID late = UUID.fromString("30000000-0000-0000-0000-0000000000dd");
        f.account(late, YHR, "ar_d", "CONNECTED");
        // 해제 전에만 라인이 있던(재연동한) 계좌
        f.sql("""
                INSERT INTO position_line (as_of, account_id, instrument_id, quantity, cost_amount_local, market_value_local,
                  cost_amount_krw, market_value_krw, fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
                VALUES (DATE '2026-10-01', '30000000-0000-0000-0000-0000000000dd', '10000000-0000-0000-0000-000000000007',
                  1, 1, 1, 1, 1, 1, DATE '2026-10-01', TIMESTAMPTZ '2026-10-01T15:30:00+09', false, true)
                """);
        f.deposit("ar_a", "KRW", "500", "2026-10-13T14:01:00+09");
        f.run("ar_a", "USER", D, "2026-10-13T14:00:00+09", "DONE", "2026-10-13T14:02:00+09");

        processor.processOnce();

        assertThat(f.lines(B, D)).isEmpty();
        assertThat(f.lines(late, D)).isEmpty();
    }

    @Test
    void 늦게_처리된_옛_실행은_새_값을_덮지_않는다() {
        f.deposit("ar_a", "KRW", "500", "2026-10-13T14:01:00+09");
        f.deposit("ar_a", "KRW", "900", "2026-10-13T15:01:00+09");
        f.run("ar_a", "USER", D, "2026-10-13T15:00:00+09", "DONE", "2026-10-13T15:02:00+09");
        processor.processOnce();

        UUID older = f.run("ar_a", "USER", D, "2026-10-13T14:00:00+09", "DONE", "2026-10-13T14:02:00+09");
        processor.processOnce();

        assertThat(f.build(older)).containsEntry("reason", "OLDER_THAN_EXISTING");
        assertThat(f.lines(A, D)).singleElement().satisfies(l ->
                assertThat((BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("900"));
    }
}
```

두 번째 실행은 14:02에 끝났으므로 14:01 잔고를 고른다. 그날 이미 15:01 실측이 있어 덮지 않는다.

끝단 테스트 — 잠정 이월이 있으면 계좌별 화면이 200이고 B에 기준일 재료가 실린다:

```java
package com.stockproject.portfolio.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.snapshot.MutableClock;
import com.stockproject.portfolio.snapshot.RunProcessor;
import com.stockproject.portfolio.snapshot.SnapshotFixture;
import com.stockproject.portfolio.snapshot.SnapshotTestConfig;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.nio.charset.StandardCharsets;

import static com.stockproject.portfolio.snapshot.SnapshotFixture.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/** 생성기가 만든 라인으로 계좌별 화면이 뜬다 — 한 계좌만 새로고침한 날에도 (설계 §2). */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(SnapshotTestConfig.class)
class SnapshotBuilderAccountsViewTest {

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    @Autowired SnapshotFixture f;
    @Autowired RunProcessor processor;
    @Autowired MutableClock clock;

    @Test
    void 한_계좌만_새로고침한_날_계좌별_화면이_뜨고_다른_계좌는_이월로_보인다() throws Exception {
        f.reset();
        clock.set("2026-10-13T14:30:00+09:00");
        f.account(A, YHR, "ar_a", "CONNECTED");
        f.account(B, YHR, "ar_b", "CONNECTED");
        for (String ref : new String[]{"ar_a", "ar_b"}) {
            f.deposit(ref, "KRW", "100", "2026-10-12T23:05:00+09");
            f.run(ref, "SCHEDULE", "2026-10-12", "2026-10-12T23:00:00+09", "DONE", "2026-10-12T23:10:00+09");
        }
        processor.processOnce();
        f.deposit("ar_a", "KRW", "500", "2026-10-13T14:01:00+09");
        f.run("ar_a", "USER", "2026-10-13", "2026-10-13T14:00:00+09", "DONE", "2026-10-13T14:02:00+09");
        processor.processOnce();

        var response = mockMvc.perform(get("/portfolio/views/accounts").header("Authorization", bearer("yhr")))
                .andReturn().getResponse();

        assertThat(response.getStatus()).isEqualTo(200);
        JsonNode body = json.readTree(response.getContentAsString(StandardCharsets.UTF_8));
        JsonNode accounts = body.get("data").get("rows").get(0).get("rows");
        JsonNode b = accounts.get(0).get("key").asText().equals(B.toString()) ? accounts.get(0) : accounts.get(1);
        assertThat(b.get("is_carried_forward").asBoolean()).isTrue();
        assertThat(b.get("last_collection").get("state").asText()).isEqualTo("DONE");
        assertThat(body.get("data").get("total").get("total_assets_krw").decimalValue()).isEqualByComparingTo("600");
    }

    @Test
    void 직전_영업일이_확정_전인_아침에_한_계좌만_새로고침해도_화면이_뜬다() throws Exception {
        f.reset();
        f.account(A, YHR, "ar_a", "CONNECTED");
        f.account(B, YHR, "ar_b", "CONNECTED");
        clock.set("2026-10-12T23:30:00+09:00");
        for (String ref : new String[]{"ar_a", "ar_b"}) {
            f.deposit(ref, "KRW", "100", "2026-10-12T23:05:00+09");
            f.run(ref, "SCHEDULE", "2026-10-12", "2026-10-12T23:00:00+09", "DONE", "2026-10-12T23:10:00+09");
        }
        processor.processOnce();
        clock.set("2026-10-14T07:00:00+09:00");    // 10-13은 라인 없이 마감 전
        f.deposit("ar_a", "KRW", "500", "2026-10-14T06:58:00+09");
        f.run("ar_a", "USER", "2026-10-14", "2026-10-14T06:55:00+09", "DONE", "2026-10-14T07:00:00+09");
        processor.processOnce();

        var response = mockMvc.perform(get("/portfolio/views/accounts").header("Authorization", bearer("yhr")))
                .andReturn().getResponse();

        assertThat(response.getStatus()).isEqualTo(200);
    }

    private String bearer(String user) throws Exception {
        String body = mockMvc.perform(post("/auth/login").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\": \"%s@a.com\", \"password\": \"local-dev-password\"}".formatted(user)))
                .andReturn().getResponse().getContentAsString();
        return "Bearer " + json.readTree(body).get("access_token").asText();
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests '*RunProcessorProvisionalTest' --tests '*SnapshotBuilderAccountsViewTest'`
Expected: 잠정 이월 테스트 FAIL(B 라인 없음), 순서 역전 FAIL(500으로 덮임), 끝단 FAIL(500 `FACT_INVARIANT_VIOLATED`)

- [ ] **Step 3: `decide`에 순서 역전과 잠정 이월을 넣는다**

`RunProcessor.decide`의 `calc` 실패 처리 다음, 검사 앞에 넣는다:

```java
        if (newerMeasuredExists(current, set)) {
            return Decision.skipped(BuildReason.OLDER_THAN_EXISTING);
        }
```

`positions.insert` 다음에 넣는다:

```java
        carrySiblings(run);
```

메서드:

```java
    /** 그날의 실측이 이번 잔고보다 새로우면 덮지 않는다 — 처리 순서가 실행 순서와 다를 수 있다. */
    private static boolean newerMeasuredExists(List<Line> current, BalanceSet set) {
        return current.stream().anyMatch(l -> !l.carriedForward() && l.sourceAsOf().isAfter(set.sourceAsOf()));
    }

    /**
     * 같은 사용자의 다른 계좌가 그날 라인이 없으면 사용자의 직전 기준일 라인을 잠정 이월한다 (설계 §5.6).
     * 그날 한 벌에서 계좌가 빠지면 총자산이 그만큼 줄어 손실처럼 보인다(스펙 §7.3). 기준을 조회 시 검증과
     * 같게 두므로, 직전 영업일이 아직 확정 전이어도 화면이 뜬다. 확정 단계가 직전 영업일 기준으로 다시 계산한다.
     */
    private void carrySiblings(RunRow run) {
        LocalDate userPrev = positions.userPreviousAsOf(run.userId(), run.asOf());
        if (userPrev == null) return;
        for (UUID sibling : positions.siblingsToCarry(run.userId(), run.accountId(), run.asOf(), userPrev)) {
            positions.lines(sibling, userPrev).forEach(l -> positions.insert(l.carriedTo(run.asOf(), false)));
        }
    }
```

`calc`가 `Lines`면 `set`은 null이 아니다 — 비어 있으면 `NO_BALANCE`가 먼저 걸린다.

- [ ] **Step 4: 통과를 확인한다**

Run: `./gradlew test --tests '*RunProcessor*' --tests '*SnapshotBuilderAccountsViewTest'`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/main/java/com/stockproject/portfolio/snapshot/RunProcessor.java src/test/java/com/stockproject/portfolio
git commit -m "feat: 한 계좌만 갱신된 날 같은 사용자의 다른 계좌를 잠정 이월한다"
```

---

### Task 9: 확정 — `Finalizer`

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/snapshot/FinalizeMapper.java`
- Create: `src/main/java/com/stockproject/portfolio/snapshot/TargetAccount.java`
- Create: `src/main/java/com/stockproject/portfolio/snapshot/Finalizer.java`
- Test: `src/test/java/com/stockproject/portfolio/snapshot/FinalizerTest.java`

**Interfaces:**
- Consumes: `PositionWriteMapper` · `PositionBuildMapper` (Task 7), `SnapshotRunRecorder.record(LocalDate)`, `SnapshotRunMapper.latest()`, `MarketDataMapper.calendar`
- Produces:
  - `record TargetAccount(UUID accountId, boolean settled, boolean unprocessed)`
  - `Finalizer.deadline(CalendarDay day, LocalTime at) : Optional<OffsetDateTime>` (패키지 공개 static)
  - `FinalizeMapper.earliestRunAsOf() : LocalDate`, `targets(LocalDate day, LocalDate prev, List<String> retriable) : List<TargetAccount>`, `blocking(LocalDate day, LocalDate prev, boolean pastDeadline, List<String> retriable) : int`
  - `Finalizer.finalizeOnce() : int` — 이번 회차에 확정한 날짜 수

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.snapshot;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;

import static com.stockproject.portfolio.snapshot.SnapshotFixture.*;
import static org.assertj.core.api.Assertions.assertThat;

/** 날짜 확정 (설계 §6). 마감 = 다음 KR 영업일 08:00 KST. 10-13(화)의 마감은 10-14 08:00이다. */
@SpringBootTest
@ActiveProfiles("test")
@Import(SnapshotTestConfig.class)
class FinalizerTest {

    static final String PREV = "2026-10-12";
    static final String D = "2026-10-13";

    @Autowired SnapshotFixture f;
    @Autowired RunProcessor processor;
    @Autowired Finalizer finalizer;
    @Autowired MutableClock clock;

    @BeforeEach
    void setUp() {
        f.reset();
        clock.set("2026-10-12T23:30:00+09:00");
    }

    /** 10-12에 A · B 확정본을 만든다. */
    void seedPrev() {
        f.account(A, YHR, "ar_a", "CONNECTED");
        f.account(B, YHR, "ar_b", "CONNECTED");
        for (String ref : new String[]{"ar_a", "ar_b"}) {
            f.deposit(ref, "KRW", "100", "2026-10-12T23:05:00+09");
            f.run(ref, "SCHEDULE", PREV, "2026-10-12T23:00:00+09", "DONE", "2026-10-12T23:10:00+09");
        }
        processor.processOnce();
        assertThat(finalizer.finalizeOnce()).isEqualTo(1);
        assertThat(f.snapshotRun(PREV)).isTrue();
    }

    @Test
    void 실행이_하나도_없으면_아무것도_쓰지_않는다() {
        f.account(A, YHR, "ar_a", "CONNECTED");
        f.sql("""
                INSERT INTO position_line (as_of, account_id, instrument_id, quantity, cost_amount_local, market_value_local,
                  cost_amount_krw, market_value_krw, fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
                VALUES (DATE '2026-10-12', '30000000-0000-0000-0000-00000000000a', '10000000-0000-0000-0000-000000000007',
                  1, 1, 1, 1, 1, 1, DATE '2026-10-12', TIMESTAMPTZ '2026-10-12T15:30:00+09', false, false)
                """);
        clock.set("2026-10-20T09:00:00+09:00");

        assertThat(finalizer.finalizeOnce()).isZero();
        assertThat(f.lines(A, D)).isEmpty();
    }

    @Test
    void EOD가_모두_끝나면_마감_전이라도_확정한다() {
        seedPrev();
        clock.set("2026-10-13T23:30:00+09:00");
        for (String ref : new String[]{"ar_a", "ar_b"}) {
            f.deposit(ref, "KRW", "200", "2026-10-13T23:05:00+09");
            f.run(ref, "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        }
        processor.processOnce();

        assertThat(finalizer.finalizeOnce()).isEqualTo(1);
        assertThat(f.snapshotRun(D)).isTrue();
    }

    @Test
    void EOD_실패는_직전_영업일_확정본을_이월한다() {
        seedPrev();
        clock.set("2026-10-13T23:30:00+09:00");
        f.deposit("ar_a", "KRW", "200", "2026-10-13T23:05:00+09");
        f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        f.run("ar_b", "SCHEDULE", D, "2026-10-13T23:00:00+09", "FAILED", "2026-10-13T23:10:00+09");
        processor.processOnce();

        finalizer.finalizeOnce();

        assertThat(f.lines(B, D)).singleElement().satisfies(l -> {
            assertThat((BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("100");
            assertThat(l.get("is_carried_forward")).isEqualTo(true);
            assertThat(l.get("is_final")).isEqualTo(true);
        });
        assertThat(f.sourceAsOf(B, D)).isEqualTo(OffsetDateTime.parse("2026-10-12T23:05:00+09:00").toInstant());
        assertThat(f.finalizeBuilds(B)).singleElement().satisfies(b -> {
            assertThat(b.get("outcome")).isEqualTo("CARRIED");
            assertThat(b.get("reason")).isNull();
        });
        assertThat(f.snapshotRun(D)).isTrue();
    }

    @Test
    void EOD_실패인데_같은_날_수동_실측이_있으면_승격한다() {
        seedPrev();
        clock.set("2026-10-13T14:30:00+09:00");
        f.deposit("ar_a", "KRW", "300", "2026-10-13T14:01:00+09");
        f.run("ar_a", "USER", D, "2026-10-13T14:00:00+09", "DONE", "2026-10-13T14:02:00+09");
        processor.processOnce();
        clock.set("2026-10-13T23:30:00+09:00");
        f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "FAILED", "2026-10-13T23:10:00+09");
        f.deposit("ar_b", "KRW", "200", "2026-10-13T23:05:00+09");
        f.run("ar_b", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        processor.processOnce();

        finalizer.finalizeOnce();

        assertThat(f.lines(A, D)).singleElement().satisfies(l -> {
            assertThat((BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("300");
            assertThat(l.get("is_carried_forward")).isEqualTo(false);
            assertThat(l.get("is_final")).isEqualTo(true);
        });
        assertThat(f.finalizeBuilds(A)).singleElement().satisfies(b -> assertThat(b.get("outcome")).isEqualTo("PROMOTED"));
    }

    @Test
    void 잠정_이월은_확정_때_직전_영업일_확정본으로_다시_만든다() {
        seedPrev();
        clock.set("2026-10-13T14:30:00+09:00");
        f.deposit("ar_a", "KRW", "300", "2026-10-13T14:01:00+09");
        f.run("ar_a", "USER", D, "2026-10-13T14:00:00+09", "DONE", "2026-10-13T14:02:00+09");
        processor.processOnce();     // B 잠정 이월

        clock.set("2026-10-14T08:00:00+09:00");   // 마감
        finalizer.finalizeOnce();

        assertThat(f.lines(B, D)).singleElement().satisfies(l -> {
            assertThat(l.get("is_carried_forward")).isEqualTo(true);
            assertThat(l.get("is_final")).isEqualTo(true);
        });
        assertThat(f.finalizeBuilds(B)).singleElement().satisfies(b -> {
            assertThat(b.get("outcome")).isEqualTo("CARRIED");
            assertThat(b.get("reason")).isEqualTo("DEADLINE");
        });
        assertThat(f.snapshotRun(D)).isTrue();
    }

    @Test
    void 잠정_이월은_확정_때_직전_영업일_확정본으로_다시_계산된다() {
        seedPrev();
        // 10-14 07:00: 10-13은 확정 전이고 라인이 없다. A만 새로고침 → B는 10-12 값(100)으로 잠정 이월
        clock.set("2026-10-14T07:00:00+09:00");
        f.deposit("ar_a", "KRW", "300", "2026-10-14T06:58:00+09");
        f.run("ar_a", "USER", "2026-10-14", "2026-10-14T06:55:00+09", "DONE", "2026-10-14T07:00:00+09");
        processor.processOnce();
        // 07:30: B의 10-13 EOD가 늦게 끝나 10-13 확정 라인(250)이 생긴다
        clock.set("2026-10-14T07:30:00+09:00");
        f.deposit("ar_b", "KRW", "250", "2026-10-13T23:05:00+09");
        f.run("ar_b", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-14T07:20:00+09");
        processor.processOnce();
        clock.set("2026-10-14T08:00:00+09:00");
        finalizer.finalizeOnce();                  // 10-13 확정

        clock.set("2026-10-15T08:00:00+09:00");
        finalizer.finalizeOnce();                  // 10-14 확정

        assertThat(f.lines(B, "2026-10-14")).singleElement().satisfies(l -> {
            assertThat((BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("250");
            assertThat(l.get("is_carried_forward")).isEqualTo(true);
            assertThat(l.get("is_final")).isEqualTo(true);
        });
        assertThat(f.lines(A, "2026-10-14")).singleElement().satisfies(l -> {
            assertThat((BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("300");
            assertThat(l.get("is_final")).isEqualTo(true);
        });
        assertThat(f.snapshotRun("2026-10-14")).isTrue();
    }

    @Test
    void 마감이_지났어도_끝난_실행이_처리되지_않았으면_기다린다() {
        seedPrev();
        clock.set("2026-10-14T08:30:00+09:00");
        f.deposit("ar_a", "KRW", "200", "2026-10-13T23:05:00+09");
        f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-14T08:10:00+09");

        assertThat(finalizer.finalizeOnce()).isZero();          // A의 끝난 실행이 아직 처리 전

        processor.processOnce();
        assertThat(finalizer.finalizeOnce()).isEqualTo(1);
        assertThat(f.lines(A, D)).singleElement().satisfies(l -> {
            assertThat((BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("200");
            assertThat(l.get("is_carried_forward")).isEqualTo(false);
        });
    }

    @Test
    void 해제된_계좌는_확정_대상이_아니다() {
        seedPrev();
        f.sql("UPDATE account SET link_state = 'DISCONNECTED' WHERE account_ref = 'ar_b'");
        clock.set("2026-10-14T08:00:00+09:00");

        assertThat(finalizer.finalizeOnce()).isEqualTo(1);
        assertThat(f.lines(B, D)).isEmpty();
        assertThat(f.lines(A, D)).singleElement().satisfies(l -> assertThat(l.get("is_carried_forward")).isEqualTo(true));
    }

    @Test
    void 실행이_없는_계좌는_마감까지_기다린다() {
        seedPrev();
        clock.set("2026-10-13T23:30:00+09:00");
        f.deposit("ar_a", "KRW", "200", "2026-10-13T23:05:00+09");
        f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        processor.processOnce();

        assertThat(finalizer.finalizeOnce()).isZero();
        assertThat(f.snapshotRun(D)).isFalse();

        clock.set("2026-10-14T07:59:59+09:00");
        assertThat(finalizer.finalizeOnce()).isZero();

        clock.set("2026-10-14T08:00:00+09:00");
        assertThat(finalizer.finalizeOnce()).isEqualTo(1);
        assertThat(f.lines(B, D)).singleElement().satisfies(l -> assertThat(l.get("is_carried_forward")).isEqualTo(true));
    }

    @Test
    void 첫_수집이_진행_중이면_기다렸다가_그날에_편입한다() {
        f.account(A, YHR, "ar_a", "CONNECTING");
        f.requested("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09");   // 첫 수집 진행 중
        clock.set("2026-10-13T23:01:00+09:00");
        assertThat(finalizer.finalizeOnce()).isZero();

        f.sql("UPDATE collection_run SET state = 'DONE', finished_at = TIMESTAMPTZ '2026-10-13T23:10:00+09', silver_synced_at = TIMESTAMPTZ '2026-10-13T23:10:00+09'");
        f.deposit("ar_a", "KRW", "100", "2026-10-13T23:05:00+09");
        processor.processOnce();
        finalizer.finalizeOnce();

        assertThat(f.lines(A, D)).singleElement().satisfies(l -> assertThat(l.get("is_final")).isEqualTo(true));
        assertThat(f.snapshotRun(D)).isTrue();
    }

    @Test
    void 첫_수집이_다른_계좌보다_늦게_끝나도_그날에_담긴다() {
        seedPrev();
        UUID late = UUID.fromString("30000000-0000-0000-0000-0000000000dd");
        f.account(late, YHR, "ar_d", "CONNECTING");
        clock.set("2026-10-13T23:30:00+09:00");
        for (String ref : new String[]{"ar_a", "ar_b"}) {
            f.deposit(ref, "KRW", "200", "2026-10-13T23:05:00+09");
            f.run(ref, "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        }
        f.requested("ar_d", "SCHEDULE", D, "2026-10-13T23:00:00+09");
        processor.processOnce();

        assertThat(finalizer.finalizeOnce()).isZero();

        f.sql("""
                UPDATE collection_run SET state = 'DONE', finished_at = TIMESTAMPTZ '2026-10-13T23:40:00+09',
                       silver_synced_at = TIMESTAMPTZ '2026-10-13T23:40:00+09'
                 WHERE account_ref = 'ar_d'
                """);
        f.deposit("ar_d", "KRW", "50", "2026-10-13T23:35:00+09");
        processor.processOnce();

        assertThat(finalizer.finalizeOnce()).isEqualTo(1);
        assertThat(f.lines(late, D)).singleElement().satisfies(l -> assertThat(l.get("is_final")).isEqualTo(true));
        assertThat(f.lines(A, D)).hasSize(1);
    }

    @Test
    void 첫_수집_실패는_라인_없이_확정하고_대상이_없는_날은_마감_뒤에_확정한다() {
        f.account(A, YHR, "ar_a", "CONNECTING");
        clock.set("2026-10-13T23:30:00+09:00");
        f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "FAILED", "2026-10-13T23:10:00+09");
        processor.processOnce();

        assertThat(finalizer.finalizeOnce()).isEqualTo(1);
        assertThat(f.lines(A, D)).isEmpty();
        assertThat(f.snapshotRun(D)).isTrue();

        // 10-14는 대상 계좌가 0개다 — 마감(10-15 08:00) 전에는 확정하지 않는다
        clock.set("2026-10-15T07:59:00+09:00");
        finalizer.finalizeOnce();
        assertThat(f.snapshotRun("2026-10-14")).isFalse();

        clock.set("2026-10-15T08:00:00+09:00");
        finalizer.finalizeOnce();
        assertThat(f.snapshotRun("2026-10-14")).isTrue();
    }

    @Test
    void 해제_후_재연동한_계좌의_첫_수집_실패는_옛_라인을_이월하지_않는다() {
        f.account(A, YHR, "ar_a", "CONNECTING");
        f.sql("""
                INSERT INTO position_line (as_of, account_id, instrument_id, quantity, cost_amount_local, market_value_local,
                  cost_amount_krw, market_value_krw, fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
                VALUES (DATE '2026-10-01', '30000000-0000-0000-0000-00000000000a', '10000000-0000-0000-0000-000000000001',
                  1, 1, 1, 1, 1, 1, DATE '2026-10-01', TIMESTAMPTZ '2026-10-01T15:30:00+09', false, true)
                """);
        clock.set("2026-10-13T23:30:00+09:00");
        f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "FAILED", "2026-10-13T23:10:00+09");
        processor.processOnce();

        finalizer.finalizeOnce();

        assertThat(f.lines(A, D)).isEmpty();
        assertThat(f.snapshotRun(D)).isTrue();
    }

    @Test
    void 한_계좌의_확정이_실패해도_다른_계좌는_확정하고_그날은_남긴다() {
        seedPrev();
        f.sql("""
                CREATE OR REPLACE FUNCTION test_fail_b() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                  IF NEW.account_id = '30000000-0000-0000-0000-00000000000b' AND NEW.is_final THEN
                    RAISE EXCEPTION 'test';
                  END IF;
                  RETURN NEW;
                END $$
                """);
        f.sql("CREATE TRIGGER test_fail_b BEFORE INSERT ON position_line FOR EACH ROW EXECUTE FUNCTION test_fail_b()");
        try {
            clock.set("2026-10-14T08:00:00+09:00");

            assertThat(finalizer.finalizeOnce()).isZero();

            assertThat(f.lines(A, D)).singleElement().satisfies(l -> assertThat(l.get("is_final")).isEqualTo(true));
            assertThat(f.lines(B, D)).isEmpty();
            assertThat(f.snapshotRun(D)).isFalse();
        } finally {
            f.sql("DROP TRIGGER test_fail_b ON position_line");
            f.sql("DROP FUNCTION test_fail_b()");
        }
        assertThat(finalizer.finalizeOnce()).isEqualTo(1);
    }

    @Test
    void 마감이_지나지_않은_다음_날은_확정하지_않는다() {
        seedPrev();
        clock.set("2026-10-14T09:00:00+09:00");   // 10-13 마감 경과, 10-14 마감(10-15 08:00) 전

        finalizer.finalizeOnce();

        assertThat(f.snapshotRun(D)).isTrue();
        assertThat(f.snapshotRun("2026-10-14")).isFalse();
        assertThat(f.snapshotRun("2026-10-15")).isFalse();
    }
}
```

클래스에 아래 테스트도 넣는다.

```java
    @Test
    void 캘린더_공백에서_확정을_멈춘다() {
        seedPrev();
        f.removeCalendarDay("2026-10-14");
        for (String ref : new String[]{"ar_a", "ar_b"}) {
            f.deposit(ref, "KRW", "300", "2026-10-15T23:05:00+09");
            f.run(ref, "SCHEDULE", "2026-10-15", "2026-10-15T23:00:00+09", "DONE", "2026-10-15T23:10:00+09");
        }
        clock.set("2026-10-15T23:30:00+09:00");
        processor.processOnce();

        finalizer.finalizeOnce();

        assertThat(f.snapshotRun(D)).isTrue();                 // 10-13은 10-14 행이 없어도 next_trading_day로 마감을 안다
        assertThat(f.snapshotRun("2026-10-15")).isFalse();     // 10-14가 비어 그 뒤로 가지 않는다
    }
```

마감 계산은 단위 테스트로 따로 본다. 미러의 `next_trading_day`는 NOT NULL이라 통합 테스트로는 빈 값을 만들 수 없다.

```java
package com.stockproject.portfolio.snapshot;

import com.stockproject.portfolio.alert.data.CalendarDay;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.time.LocalTime;
import java.time.OffsetDateTime;

import static org.assertj.core.api.Assertions.assertThat;

/** 마감 = 다음 KR 영업일의 finalize-at (설계 §6.2). */
class FinalizerDeadlineTest {

    @Test
    void 다음_영업일의_설정_시각이다() {
        CalendarDay fri = new CalendarDay(LocalDate.of(2026, 10, 16), true,
                LocalDate.of(2026, 10, 15), LocalDate.of(2026, 10, 19), null, null);

        assertThat(Finalizer.deadline(fri, LocalTime.of(8, 0)))
                .contains(OffsetDateTime.parse("2026-10-19T08:00:00+09:00"));
    }

    @Test
    void 다음_영업일을_모르면_마감도_없다() {
        CalendarDay end = new CalendarDay(LocalDate.of(2026, 12, 31), true, LocalDate.of(2026, 12, 30), null, null, null);

        assertThat(Finalizer.deadline(end, LocalTime.of(8, 0))).isEmpty();
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests '*FinalizerTest' --tests '*FinalizerDeadlineTest'`
Expected: 컴파일 실패(`Finalizer` 없음)

- [ ] **Step 3: 매퍼를 만든다**

```java
package com.stockproject.portfolio.snapshot;

import java.util.UUID;

/**
 * 그날 확정 대상 계좌. settled는 그날의 SCHEDULE 실행이 있고 전부 최종 처리됐다는 뜻이고,
 * unprocessed는 그날 실행 가운데 끝났는데 아직 한 번도 처리하지 않은 것이 있다는 뜻이다.
 */
public record TargetAccount(UUID accountId, boolean settled, boolean unprocessed) { }
```

```java
package com.stockproject.portfolio.snapshot;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDate;
import java.util.List;

/**
 * 확정 대상 판정 (설계 §6.1 · §6.2). 조각을 &lt;script&gt; 안에서 이어 붙이므로 부등호를 쓰지 않는다 — XML로 읽힌다.
 */
@Mapper
public interface FinalizeMapper {

    /** 대상 계좌: 해제되지 않았고, 직전 영업일 또는 그날 라인이 있거나 그날 SCHEDULE 실행이 있다. */
    String TARGET = """
            a.link_state != 'DISCONNECTED'
            AND (EXISTS (SELECT 1 FROM position_line p WHERE p.account_id = a.account_id AND p.as_of = #{prev})
                 OR EXISTS (SELECT 1 FROM position_line p WHERE p.account_id = a.account_id AND p.as_of = #{day})
                 OR EXISTS (SELECT 1 FROM collection_run r WHERE r.account_ref = a.account_ref
                               AND r.as_of = #{day} AND r.requested_by = 'SCHEDULE'))
            """;

    /** 그날 SCHEDULE 실행이 있고, 전부 최종 사유로 처리됐다. */
    String SETTLED = """
            (EXISTS (SELECT 1 FROM collection_run r WHERE r.account_ref = a.account_ref
                        AND r.as_of = #{day} AND r.requested_by = 'SCHEDULE')
             AND NOT EXISTS (SELECT 1 FROM collection_run r
                               LEFT JOIN position_build b ON b.run_id = r.run_id
                              WHERE r.account_ref = a.account_ref AND r.as_of = #{day} AND r.requested_by = 'SCHEDULE'
                                AND (b.run_id IS NULL
                                     OR (b.outcome = 'SKIPPED' AND b.reason IN
                                         <foreach collection="retriable" item="x" open="(" separator="," close=")">#{x}</foreach>))))
            """;

    /** 그날 실행 가운데 끝났는데(설계 §5.1의 대상 조건) 아직 한 번도 처리하지 않은 것이 있다. */
    String UNPROCESSED = """
            EXISTS (SELECT 1 FROM collection_run r
                      LEFT JOIN position_build b ON b.run_id = r.run_id
                     WHERE r.account_ref = a.account_ref AND r.as_of = #{day} AND b.run_id IS NULL
                       AND ((r.state = 'DONE' AND r.silver_synced_at IS NOT NULL)
                            OR r.state IN ('FAILED', 'REAUTH_REQUIRED')))
            """;

    /** 이월 · 승격할 것이 있는데 그날 확정 라인이 없다. */
    String UNFINISHED = """
            ((EXISTS (SELECT 1 FROM position_line p WHERE p.account_id = a.account_id AND p.as_of = #{prev})
              OR EXISTS (SELECT 1 FROM position_line p WHERE p.account_id = a.account_id AND p.as_of = #{day}))
             AND NOT EXISTS (SELECT 1 FROM position_line p
                              WHERE p.account_id = a.account_id AND p.as_of = #{day} AND p.is_final))
            """;

    /** 백엔드가 아는 계좌의 실행 가운데 가장 이른 기준일. 확정 후보 범위의 시작이다. */
    @Select("SELECT min(r.as_of) FROM collection_run r JOIN account a ON a.account_ref = r.account_ref")
    LocalDate earliestRunAsOf();

    @Select("<script>SELECT a.account_id, " + SETTLED + " AS settled, " + UNPROCESSED + " AS unprocessed"
            + " FROM account a WHERE " + TARGET + " ORDER BY a.account_id</script>")
    List<TargetAccount> targets(@Param("day") LocalDate day, @Param("prev") LocalDate prev,
                                @Param("retriable") List<String> retriable);

    /** 날짜 확정을 막는 대상 계좌 수 — 기다릴 실행이 남았거나 확정이 끝나지 않은 계좌. 날짜 배타 잠금 안에서 센다. */
    @Select("<script>SELECT count(*) FROM account a WHERE " + TARGET
            + " AND ((NOT " + SETTLED + " AND (NOT #{pastDeadline} OR " + UNPROCESSED + ")) OR " + UNFINISHED + ")</script>")
    int blocking(@Param("day") LocalDate day, @Param("prev") LocalDate prev,
                 @Param("pastDeadline") boolean pastDeadline, @Param("retriable") List<String> retriable);
}
```

- [ ] **Step 4: `Finalizer`를 만든다**

```java
package com.stockproject.portfolio.snapshot;

import com.stockproject.portfolio.alert.data.CalendarDay;
import com.stockproject.portfolio.alert.data.MarketDataMapper;
import com.stockproject.portfolio.alert.data.SnapshotRunMapper;
import com.stockproject.portfolio.alert.service.SnapshotRunRecorder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 날짜 확정 (설계 §6). 확정하지 않은 가장 이른 KR 영업일부터 오늘까지 순서대로 보고, 한 날을 확정하지 못하면 멈춘다.
 * 그래서 이월 원본은 늘 직전 영업일의 확정 라인이다. 계좌마다 트랜잭션 하나라 한 계좌의 실패가 다른 계좌를 막지 않는다.
 */
@Component
public class Finalizer {

    private static final Logger log = LoggerFactory.getLogger(Finalizer.class);
    private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

    private final FinalizeMapper finalize;
    private final PositionWriteMapper positions;
    private final PositionBuildMapper builds;
    private final SnapshotRunMapper snapshotRuns;
    private final SnapshotRunRecorder recorder;
    private final MarketDataMapper market;
    private final SnapshotProperties props;
    private final TransactionTemplate tx;
    private final Clock clock;

    public Finalizer(FinalizeMapper finalize, PositionWriteMapper positions, PositionBuildMapper builds,
                     SnapshotRunMapper snapshotRuns, SnapshotRunRecorder recorder, MarketDataMapper market,
                     SnapshotProperties props, TransactionTemplate tx, Clock clock) {
        this.finalize = finalize;
        this.positions = positions;
        this.builds = builds;
        this.snapshotRuns = snapshotRuns;
        this.recorder = recorder;
        this.market = market;
        this.props = props;
        this.tx = tx;
        this.clock = clock;
    }

    /** 이번 회차에 확정한 날짜 수. */
    public int finalizeOnce() {
        LocalDate start = finalize.earliestRunAsOf();
        if (start == null) return 0;
        LocalDate latest = snapshotRuns.latest();
        LocalDate from = latest != null && !latest.isBefore(start) ? latest.plusDays(1) : start;
        OffsetDateTime now = OffsetDateTime.now(clock);
        LocalDate today = now.atZoneSameInstant(SEOUL).toLocalDate();
        if (from.isAfter(today)) return 0;

        Map<LocalDate, CalendarDay> calendar = market.calendar("KR", from, today).stream()
                .collect(Collectors.toMap(CalendarDay::date, Function.identity()));
        int finalized = 0;
        for (LocalDate d = from; !d.isAfter(today); d = d.plusDays(1)) {
            CalendarDay day = calendar.get(d);
            if (day == null) {
                log.warn("KR 캘린더에 {}가 없어 확정을 멈춘다", d);
                return finalized;
            }
            if (!day.isTradingDay()) continue;
            if (!finalizeDay(day, now)) return finalized;
            finalized++;
        }
        return finalized;
    }

    /** 마감 = D 다음 KR 영업일의 finalize-at(KST). 다음 영업일을 모르면 마감도 없다. */
    static Optional<OffsetDateTime> deadline(CalendarDay day, LocalTime at) {
        if (day.nextTradingDay() == null) return Optional.empty();
        return Optional.of(day.nextTradingDay().atTime(at).atZone(SEOUL).toOffsetDateTime());
    }

    private boolean finalizeDay(CalendarDay day, OffsetDateTime now) {
        LocalDate d = day.date();
        LocalDate prev = day.prevTradingDay();
        Optional<OffsetDateTime> deadline = deadline(day, props.finalizeAt());
        if (deadline.isEmpty()) {
            log.warn("KR 캘린더에서 {}의 다음 영업일을 몰라 마감을 정할 수 없다", d);
            return false;
        }
        boolean pastDeadline = !now.isBefore(deadline.get());
        List<String> retriable = BuildReason.retriableNames();

        List<TargetAccount> targets = finalize.targets(d, prev, retriable);
        if (targets.isEmpty() && !pastDeadline) return false;

        List<UUID> failed = new ArrayList<>();
        for (TargetAccount t : targets) {
            if (!t.settled() && (!pastDeadline || t.unprocessed())) continue;
            boolean byDeadline = !t.settled();
            try {
                tx.executeWithoutResult(s -> finalizeAccount(t.accountId(), d, prev, byDeadline, now));
            } catch (RuntimeException e) {
                failed.add(t.accountId());
                log.warn("계좌 확정 실패 account={} as_of={} 사유={}", t.accountId(), d, e.getClass().getSimpleName());
            }
        }

        Boolean recorded = tx.execute(s -> {
            positions.lockDateExclusive(d);
            if (finalize.blocking(d, prev, pastDeadline, retriable) > 0) return false;
            recorder.record(d);
            return true;
        });
        if (!Boolean.TRUE.equals(recorded) && pastDeadline) {
            log.warn("마감이 지났는데 {}를 확정하지 못했다 실패 계좌={}", d, failed);
        }
        return Boolean.TRUE.equals(recorded);
    }

    /** 설계 §6.3. 잠근 뒤 그날의 확정 여부 · 연동 상태 · 라인을 다시 읽어 판정한다. */
    private void finalizeAccount(UUID accountId, LocalDate d, LocalDate prev, boolean byDeadline, OffsetDateTime now) {
        positions.lockDateShared(d);
        positions.lockAccount(accountId);
        if (positions.snapshotRunExists(d) || "DISCONNECTED".equals(positions.linkState(accountId))) return;
        List<Line> current = positions.lines(accountId, d);
        if (current.stream().anyMatch(Line::isFinal)) return;
        String reason = byDeadline ? BuildReason.DEADLINE.name() : null;

        if (!current.isEmpty() && current.stream().noneMatch(Line::carriedForward)) {
            positions.promote(accountId, d);
            builds.recordFinalize(accountId, d, BuildOutcome.PROMOTED.name(), reason, now);
            return;
        }
        positions.delete(accountId, d);
        List<Line> source = positions.lines(accountId, prev);
        if (source.isEmpty()) return;
        source.forEach(l -> positions.insert(l.carriedTo(d, true)));
        builds.recordFinalize(accountId, d, BuildOutcome.CARRIED.name(), reason, now);
    }
}
```

`SnapshotRunRecorder.record`는 자기 시계로 `now`를 찍는다. 같은 트랜잭션 안에서 부른다.

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test --tests '*Finalizer*' --tests '*RunProcessor*'`
Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add src/main/java/com/stockproject/portfolio/snapshot src/test/java/com/stockproject/portfolio/snapshot
git commit -m "feat: 날짜 순으로 보유 스냅샷을 확정하고 snapshot_run을 쓴다"
```

---

### Task 10: 알림이 읽는 최신 확정 스냅샷

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/alert/data/HoldingMapper.java` (`latestFinalAsOf`)
- Modify: `README.md` ("실행" 절의 샘플 적재)
- Test: `src/test/java/com/stockproject/portfolio/alert/data/HoldingReaderFinalTest.java`

**Interfaces:**
- Produces: `HoldingMapper.latestFinalAsOf(UserScope) : LocalDate` — 시그니처 그대로, `snapshot_run`이 있는 날만 (설계 §6.4)

`SCHEDULE` `DONE`은 날짜 확정 전에 그 계좌 라인을 `is_final = true`로 쓴다. `is_final`만 보면 일부 계좌만 확정된 날을 알림의 미리보기 · 생성 검증(보유 여부)이 확정본으로 읽는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

샘플에서 07-24는 확정 라인과 `snapshot_run`이 함께 있고, 07-27은 잠정 라인이다.

```java
package com.stockproject.portfolio.alert.data;

import com.stockproject.portfolio.auth.UserScope;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;

import java.time.LocalDate;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** 알림이 읽는 최신 확정 스냅샷은 snapshot_run이 있는 날이다 (보유 스냅샷 생성기 설계 §6.4). */
@SpringBootTest
@ActiveProfiles("test")
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class HoldingReaderFinalTest {

    static final UserScope YHR = new UserScope(UUID.fromString("40000000-0000-0000-0000-000000000001"));

    @Autowired HoldingReader holdings;
    @Autowired JdbcClient jdbc;

    @Test
    void 날짜_확정_전의_확정_라인은_최신_확정본이_아니다() {
        jdbc.sql("UPDATE position_line SET is_final = true WHERE as_of = DATE '2026-07-27' "
                + "AND account_id = '20000000-0000-0000-0000-000000000001'").update();

        assertThat(holdings.latestFinal(YHR)).contains(LocalDate.of(2026, 7, 24));

        jdbc.sql("INSERT INTO snapshot_run (as_of, finished_at) VALUES (DATE '2026-07-27', now())").update();

        assertThat(holdings.latestFinal(YHR)).contains(LocalDate.of(2026, 7, 27));
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests '*HoldingReaderFinalTest'`
Expected: FAIL — 첫 단언이 07-27을 받는다

- [ ] **Step 3: 조회를 한정한다**

```java
    /**
     * 최신 확정 스냅샷 — 그 사용자의 확정 라인이 있고 snapshot_run으로 날짜가 확정된 가장 늦은 날.
     * 확정 라인은 날짜 확정 전에도 계좌마다 먼저 생기므로 is_final만으로는 그날 한 벌이 다 찼는지 모른다.
     */
    @Select("""
            SELECT max(pl.as_of) FROM position_line pl JOIN account a USING (account_id)
             WHERE a.user_id = #{scope.userId} AND pl.is_final
               AND EXISTS (SELECT 1 FROM snapshot_run s WHERE s.as_of = pl.as_of)
            """)
    LocalDate latestFinalAsOf(@Param("scope") UserScope scope);
```

- [ ] **Step 4: README의 샘플 적재에 알림 샘플을 더한다**

"실행" 절의 샘플 적재 명령 아래에 더한다. 알림 샘플이 `snapshot_run`을 심으므로, 이것 없이 띄우면 알림의 보유 지표는 확정본이 없는 상태로 보인다.

~~~markdown
알림의 시장 데이터와 보유 스냅샷 확정 신호(`snapshot_run`)까지 보려면 이어서 적재한다:

```bash
docker compose exec -T db psql -U portfolio -d portfolio -f /sample/sample_alert_market.sql
```
~~~

`docker-compose.yml`이 `src/main/resources/db/sample`을 `/sample`로 마운트하므로 같은 경로로 적재된다.

- [ ] **Step 5: 통과와 기존 알림 테스트를 확인한다**

Run: `./gradlew test --tests '*HoldingReaderFinalTest' --tests '*EvaluationInputFactoryTest' --tests '*AlertPreviewApiTest' --tests '*AlertCommandApiTest'`
Expected: PASS. 기존 테스트는 두 샘플을 함께 적재해 07-24에 `snapshot_run`이 있다.

- [ ] **Step 6: 커밋**

```bash
git add src/main/java/com/stockproject/portfolio/alert/data/HoldingMapper.java src/test/java/com/stockproject/portfolio/alert/data/HoldingReaderFinalTest.java README.md
git commit -m "fix: 알림이 읽는 최신 확정 보유 스냅샷을 날짜가 확정된 날로 한정한다"
```

---

### Task 11: 동시성 — 두 복제본

**Files:**
- Test: `src/test/java/com/stockproject/portfolio/snapshot/SnapshotConcurrencyTest.java`
- Modify (테스트가 실패할 때만): `RunProcessor.java` · `Finalizer.java`

**Interfaces:**
- Consumes: `RunProcessor.processOnce()`, `Finalizer.finalizeOnce()`, `PositionWriteMapper.lockDateShared` · `lockUserAccounts`

- [ ] **Step 1: 테스트를 쓴다**

```java
package com.stockproject.portfolio.snapshot;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.support.TransactionTemplate;

import java.math.BigDecimal;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import static com.stockproject.portfolio.snapshot.SnapshotFixture.*;
import static org.assertj.core.api.Assertions.assertThat;

/** 복제본 두 개가 같은 회차를 동시에 돈다 (설계 §7). */
@SpringBootTest
@ActiveProfiles("test")
@Import(SnapshotTestConfig.class)
class SnapshotConcurrencyTest {

    static final String D = "2026-10-13";

    @Autowired SnapshotFixture f;
    @Autowired RunProcessor processor;
    @Autowired Finalizer finalizer;
    @Autowired PositionWriteMapper positions;
    @Autowired TransactionTemplate tx;
    @Autowired MutableClock clock;

    @BeforeEach
    void setUp() {
        f.reset();
        clock.set("2026-10-13T23:30:00+09:00");
        f.account(A, YHR, "ar_a", "CONNECTED");
        f.account(B, YHR, "ar_b", "CONNECTED");
    }

    @Test
    void 같은_회차를_동시에_두_번_돌려도_결과가_한_번과_같다() throws Exception {
        for (String ref : new String[]{"ar_a", "ar_b"}) {
            f.deposit(ref, "KRW", "100", "2026-10-13T23:05:00+09");
            f.run(ref, "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        }

        CompletableFuture<Integer> one = CompletableFuture.supplyAsync(processor::processOnce);
        CompletableFuture<Integer> two = CompletableFuture.supplyAsync(processor::processOnce);

        assertThat(one.get(30, TimeUnit.SECONDS) + two.get(30, TimeUnit.SECONDS)).isEqualTo(2);
        assertThat(f.lines(A, D)).hasSize(1);
        assertThat(f.lines(B, D)).hasSize(1);
    }

    /**
     * 두 계좌 모두 직전 라인이 있어, 한 실행의 처리는 다른 계좌에 잠정 이월을 쓰려 하고 다른 실행은 그 계좌의
     * 라인을 교체한다. 사용자 계좌 전체를 account_id 순으로 잠그지 않으면 키 충돌이나 교착으로 한 실행이 실패한다.
     */
    @Test
    void 같은_사용자의_두_계좌_실행을_동시에_처리해도_둘_다_한_번에_반영된다() throws Exception {
        for (String ref : new String[]{"ar_a", "ar_b"}) {
            f.deposit(ref, "KRW", "100", "2026-10-12T23:05:00+09");
            f.run(ref, "SCHEDULE", "2026-10-12", "2026-10-12T23:00:00+09", "DONE", "2026-10-12T23:10:00+09");
        }
        processor.processOnce();
        for (String ref : new String[]{"ar_a", "ar_b"}) {
            f.deposit(ref, "KRW", "200", "2026-10-13T23:05:00+09");
        }
        f.run("ar_a", "USER", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        f.run("ar_b", "USER", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:01+09");

        CompletableFuture<Integer> one = CompletableFuture.supplyAsync(processor::processOnce);
        CompletableFuture<Integer> two = CompletableFuture.supplyAsync(processor::processOnce);

        assertThat(one.get(30, TimeUnit.SECONDS) + two.get(30, TimeUnit.SECONDS)).isEqualTo(2);
        for (java.util.UUID account : new java.util.UUID[]{A, B}) {
            assertThat(f.lines(account, D)).singleElement().satisfies(l -> {
                assertThat((BigDecimal) l.get("market_value_krw")).isEqualByComparingTo("200");
                assertThat(l.get("is_carried_forward")).isEqualTo(false);
            });
        }
    }

    @Test
    void 날짜_확정은_진행_중인_실행_처리가_끝난_뒤에_일어난다() throws Exception {
        f.deposit("ar_a", "KRW", "100", "2026-10-13T23:05:00+09");
        f.run("ar_a", "SCHEDULE", D, "2026-10-13T23:00:00+09", "DONE", "2026-10-13T23:10:00+09");
        f.run("ar_b", "SCHEDULE", D, "2026-10-13T23:00:00+09", "FAILED", "2026-10-13T23:10:00+09");
        processor.processOnce();

        // 실행 처리 하나가 날짜 공유 잠금을 잡고 있는 동안 확정을 시도한다.
        CountDownLatch held = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        CompletableFuture<Void> holder = CompletableFuture.runAsync(() -> tx.executeWithoutResult(s -> {
            positions.lockDateShared(java.time.LocalDate.parse(D));
            held.countDown();
            try { release.await(10, TimeUnit.SECONDS); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        }));
        held.await(10, TimeUnit.SECONDS);
        CompletableFuture<Integer> finalizing = CompletableFuture.supplyAsync(finalizer::finalizeOnce);

        Thread.sleep(500);
        assertThat(f.snapshotRun(D)).isFalse();
        release.countDown();
        holder.get(10, TimeUnit.SECONDS);

        assertThat(finalizing.get(30, TimeUnit.SECONDS)).isEqualTo(1);
        assertThat(f.snapshotRun(D)).isTrue();

        // 확정 뒤에 늦게 끝난 B의 실행은 그날 라인을 바꾸지 않는다
        f.deposit("ar_b", "KRW", "999", "2026-10-13T23:50:00+09");
        java.util.UUID late = f.run("ar_b", "USER", D, "2026-10-13T23:45:00+09", "DONE", "2026-10-13T23:55:00+09");
        processor.processOnce();
        assertThat(f.build(late)).containsEntry("reason", "FINAL_EXISTS");
        assertThat(f.lines(B, D)).singleElement().satisfies(l -> assertThat(l.get("is_carried_forward")).isEqualTo(true));
    }
}
```

마지막 테스트의 대기는 계좌 확정 트랜잭션도 공유 잠금을 잡으므로(공유끼리는 막지 않는다) 날짜 확정 트랜잭션의 배타 잠금에서만 멈춘다.

- [ ] **Step 2: 돌려 본다**

Run: `./gradlew test --tests '*SnapshotConcurrencyTest'`
Expected: PASS. 실패하면 잠금 순서(날짜 → 계좌, `account_id` 순)가 `RunProcessor.process` · `Finalizer.finalizeAccount` · 날짜 확정 트랜잭션에서 지켜지는지부터 본다. 교착 예외(`CannotAcquireLockException`)가 나면 `processOnce`의 실행 단위 재시도로 감싸지 말고 잠금 순서를 고친다.

- [ ] **Step 3: 커밋**

```bash
git add src/test/java/com/stockproject/portfolio/snapshot/SnapshotConcurrencyTest.java
git commit -m "test: 두 복제본이 동시에 돌아도 보유 스냅샷이 한 번만 반영되는지 본다"
```

---

### Task 12: 잡 등록 · 설정 · 문서

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/snapshot/SnapshotJobs.java`
- Create: `src/main/java/com/stockproject/portfolio/snapshot/SnapshotRuntimeConfig.java`
- Modify: `src/main/resources/application.yaml` (`spring.task.scheduling.pool.size`, `portfolio.snapshot`)
- Modify: `src/test/resources/application-test.yaml`
- Modify: `README.md` ("이 저장소에 없는 것", 새 절 "보유 스냅샷 생성")
- Test: `src/test/java/com/stockproject/portfolio/snapshot/SnapshotRuntimeConfigTest.java`

**Interfaces:**
- Consumes: `CredentialFiller.fillOnce()`, `RunProcessor.processOnce()`, `Finalizer.finalizeOnce()`
- Produces: `SnapshotJobs.tick()`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.snapshot;

import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.task.TaskSchedulingAutoConfiguration;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

/** 스냅샷 잡은 켤 때만 등록되고, 알림 런타임과 무관하게 스케줄링을 켠다 (설계 §3 · §10). */
class SnapshotRuntimeConfigTest {

    private final ApplicationContextRunner runner = new ApplicationContextRunner()
            .withConfiguration(AutoConfigurations.of(TaskSchedulingAutoConfiguration.class))
            .withUserConfiguration(SnapshotRuntimeConfig.class)
            .withBean(CredentialFiller.class, () -> mock(CredentialFiller.class))
            .withBean(RunProcessor.class, () -> mock(RunProcessor.class))
            .withBean(Finalizer.class, () -> mock(Finalizer.class));

    @Test
    void 기본은_꺼져_있다() {
        runner.run(ctx -> assertThat(ctx).doesNotHaveBean(SnapshotJobs.class));
    }

    @Test
    void 켜면_잡과_스케줄링이_함께_등록된다() {
        runner.withPropertyValues("portfolio.snapshot.runtime.enabled=true").run(ctx -> {
            assertThat(ctx).hasSingleBean(SnapshotJobs.class);
            assertThat(ctx).hasBean("org.springframework.context.annotation.internalScheduledAnnotationProcessor");
        });
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests '*SnapshotRuntimeConfigTest'`
Expected: 컴파일 실패

- [ ] **Step 3: 구현한다**

```java
package com.stockproject.portfolio.snapshot;

import org.springframework.scheduling.annotation.Scheduled;

/**
 * 보유 스냅샷 생성기의 회차 (설계 §3). 모든 복제본에서 돈다 — 중복은 잠금과 처리 기록이 막는다.
 * 순서가 의미를 갖는다: 자격증명을 채우고, 끝난 실행을 반영하고, 날짜를 확정한다.
 */
public class SnapshotJobs {

    private final CredentialFiller credentials;
    private final RunProcessor processor;
    private final Finalizer finalizer;

    public SnapshotJobs(CredentialFiller credentials, RunProcessor processor, Finalizer finalizer) {
        this.credentials = credentials;
        this.processor = processor;
        this.finalizer = finalizer;
    }

    @Scheduled(fixedDelayString = "PT1M", initialDelayString = "PT20S")
    public void tick() {
        credentials.fillOnce();
        processor.processOnce();
        finalizer.finalizeOnce();
    }
}
```

```java
package com.stockproject.portfolio.snapshot;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 보유 스냅샷 생성기를 이 파드에서 돌릴지. 기본은 끔이다 — 운영 data 스키마에 cln_* 표가 생기고
 * 읽기 권한을 확인한 뒤 켠다(설계 §10). 알림 런타임을 꺼도 돌도록 스케줄링을 스스로 켠다.
 */
@Configuration(proxyBeanMethods = false)
@EnableScheduling
@ConditionalOnProperty(name = "portfolio.snapshot.runtime.enabled", havingValue = "true")
public class SnapshotRuntimeConfig {

    @Bean
    SnapshotJobs snapshotJobs(CredentialFiller credentials, RunProcessor processor, Finalizer finalizer) {
        return new SnapshotJobs(credentials, processor, finalizer);
    }
}
```

`application.yaml`:

```yaml
  task:
    scheduling:
      # 알림의 평가기 · 발송기 · 영수증 확인기와 보유 스냅샷 생성기가 서로를 붙잡지 않게 넷을 둔다.
      pool:
        size: 4
```

`portfolio:` 아래에 더한다:

```yaml
  snapshot:
    runtime:
      # 보유 스냅샷 생성기. 운영 data 스키마에 cln_*가 생기고 권한을 확인한 뒤 켠다.
      enabled: ${SNAPSHOT_RUNTIME_ENABLED:false}
    # 그날을 이월로 확정하는 마감. 다음 KR 영업일의 이 시각(KST)이다.
    finalize-at: "08:00"
    batch-size: 100
```

`application-test.yaml`의 `portfolio:` 아래에 더한다:

```yaml
  snapshot:
    runtime:
      # 테스트가 생성기를 직접 부른다. 스케줄이 돌면 다른 테스트의 데이터를 바꾼다.
      enabled: false
```

- [ ] **Step 4: README를 고친다**

"이 저장소에 없는 것"의 첫 줄을 바꾼다:

```markdown
- 등급 판정 · 실현손익 산출(`position_basis` · `realized_pnl_line`) — 실현손익 행은 사람이 넣는다
```

"계좌 연동 · 동기화" 줄은 그대로 둔다(등록 · 동기화 요청 API가 아직 없다). "## 테이블 소유 경계" 앞에 절을 더한다:

~~~markdown
## 보유 스냅샷 생성

데이터의 `collection_run`이 끝난 계좌의 `cln_balance` · `cln_deposit`으로 `position_line`을 쓰고,
그날의 계좌가 모두 확정되면 `snapshot_run`을 쓴다. 규칙은 [docs 저장소](https://github.com/stock-project-crew/docs)
`yhr/specs/portfolio-management/2026-10-15-position-line-builder-design.md`.

기본은 꺼져 있다. 켜려면 `SNAPSHOT_RUNTIME_ENABLED=true`. 운영에서 켜기 전에 앱 DB 계정으로 확인한다.

```sql
SELECT has_table_privilege('data.cln_balance', 'SELECT'),
       has_table_privilege('data.cln_deposit', 'SELECT'),
       has_table_privilege('data.fx_rate', 'SELECT'),
       has_table_privilege('data.collection_run', 'SELECT'),
       has_column_privilege('data.collection_run', 'credential_ref', 'UPDATE');
```

전부 `true`여야 한다. 표가 없으면 오류가 난다 — 그때는 켜지 않는다.

계좌별 화면의 `last_collection`은 잡을 켜지 않아도 `data.collection_run`을 읽는다. 이 이미지를 배포하기 전에
위 질의의 네 번째 값이 `true`인지 본다.
~~~

- [ ] **Step 5: 전체 테스트를 돌린다**

Run: `./gradlew test`
Expected: 전부 PASS

- [ ] **Step 6: 커밋**

```bash
git add src/main/java/com/stockproject/portfolio/snapshot src/main/resources/application.yaml src/test README.md
git commit -m "feat: 보유 스냅샷 생성기를 스케줄에 올리고 기본은 꺼 둔다"
```

---

## 실행 후 확인 (사용자 승인 필요)

- 로컬: `docker compose up -d db` → `./gradlew test` 전체 통과.
- 운영 배포 전: 운영 DB에서 Task 12 README의 권한 질의(읽기만). 결과에 따라 배포 여부를 사용자에게 묻는다.
- 운영에서 잡을 켜는 것은 데이터 쪽 조치(대조 문서 §4의 1~6번) 이후 별도 승인으로 한다.
