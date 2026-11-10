# 렌즈 분해 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `LOOK_THROUGH` 렌즈가 구성비중이 있는 ETF를 구성종목과 기타로 안분하고, 분해하지 못한 ETF는 그대로 남기며, 앱이 그 결과를 보여 주게 한다.

**Architecture:** `AggregateMapper.xml`의 `targetLine` 렌즈 분기를 "그대로 · 구성종목 · 기타" 세 갈래 `UNION ALL`로 바꾸고, 분해 판정과 비중은 공유 SQL 조각 `decomposableWeight` 하나가 정한다. 기타 라인은 원래 ETF에 `is_residual = true`로 묶여 축 SQL이 `OTHER`로 모은다. 응답 조립은 기존 정책 클래스에 플래그 두 개와 안내 두 개를 더한다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · MyBatis · Flyway · PostgreSQL 16 · JUnit 5 · AssertJ · Mockito / React Native(Expo 58) · TypeScript · jest-expo

**Spec:** [렌즈 분해 설계](../specs/portfolio-management/2026-11-04-look-through-design.md) — 이 계획의 §번호는 그 문서의 절이다. 상위 근거는 [포트폴리오 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md).

## Global Constraints

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어. 커밋 접두어 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **커밋 · 푸시는 사용자가 요청할 때만 한다.** 각 태스크의 커밋 단계는 요청을 받은 뒤 실행한다.
- 주석은 히스토리 없이 최신 사실만 쓰고, 문서 절 번호(§)를 지칭하지 않고 주석만으로 이해되게 쓴다. 검증하지 않은 것은 단정하지 않는다.
- 운영 DB에 쓰지 않는다. 스펙을 고치지 않는다. 구현 중 설계와 코드가 어긋나면 멈추고 보고한다.
- 마이그레이션 번호는 `V14`(미러, `db/external`). 병합 직전 origin/main에 V14가 생겼으면 다음 빈 번호로 옮긴다.
- DB를 쓰는 테스트는 전용 DB에서만 돈다: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_lens?currentSchema=app,data' ./gradlew test --rerun-tasks` (특정 클래스는 `--tests '<FQCN>'` 추가). 공유 `portfolio_test`에서 돌리지 않는다. DB 테스트는 돌리기 전에 사용자에게 묻는다. DB 없는 단위 테스트는 묻지 않는다.
- 테스트 메서드 이름은 기존처럼 한국어 문장.
- 앱: Expo SDK 58(스토어판 Expo Go에 맞춤). 끝에 `npx jest` · `npx tsc --noEmit` 통과.

## Review Focus

1. **같은 ETF를 한 사용자가 두 계좌에 가진 경우** — 내림은 라인(계좌 × ETF)마다 따로 해야 한다. 합친 뒤 내리면 끝전이 달라진다. → Task 3 `같은_ETF의_두_라인은_따로_내린다`.
2. **직접 보유와 경유분이 합쳐진 행의 수량 · 현지 금액** — 직접 AAPL 20주(4,400 USD) + 경유 16주(3,520 USD)가 한 행 36주 · 7,920 USD여야 하고, 경유분 종가가 없으면 행 수량 전체가 null이어야 한다. → Task 4 `합쳐진_행의_현지_금액은_두_몫의_합이다`, Task 5 `경유분_종가가_없으면_합쳐진_행_수량이_null이다`.
3. **계좌유형 필터를 건 렌즈 비중 화면의 미분해 안내** — 연금만 고르면 위탁 계좌의 KODEX 200이 안내에서 빠져야 한다. → Task 2 `계좌유형_필터가_미분해_집계를_좁힌다`.
4. **비중이 정확히 나뉘어 기타가 0인 ETF** — `기타 0원` 행이 생기지 않아야 한다. → Task 3 `기타가_0이면_기타_행이_없다`.
5. **기타가 있는 화면에서 이름순 · 평가금액순 정렬** — 기타는 언제나 맨 끝. → Task 9 `기타_행은_어느_정렬에서도_맨_끝이다`.

---

## 파일 구조

**back-end** (`.worktrees/back-end-look-through`, 브랜치 `feat/look-through`)

| 파일 | 책임 |
|---|---|
| `src/main/resources/db/external/V14__etf_constituent_mirror.sql` | `data.etf_constituent` 미러 |
| `src/main/resources/db/sample/sample_lookthrough.sql` (신규) · `sample_portfolio.sql` | 렌즈 덧씌움 픽스처 · 비우는 목록 |
| `src/main/resources/mapper/AggregateMapper.xml` | `decomposableWeight` · `targetLine` · `measures` · `totals` |
| `src/main/java/com/stockproject/portfolio/query/aggregate/AggregateMapper.java` · `LensTotals.java`(신규) | 총합 조회 |
| `.../query/aggregate/AxisSql.java` | 렌즈 영향 축의 `OTHER` 식 |
| `.../query/aggregate/AggregateRowDto.java` · `AggregateQueryRepository.java` · `domain/measure/MeasureBundle.java` | 미상 플래그 두 개 |
| `src/main/resources/mapper/EtfCoverageMapper.xml` · `.../query/aggregate/EtfCoverageMapper.java` · `DecomposedEtf.java`(신규) | 미분해 · 분해 집계, 렌즈 환율 |
| `.../validation/LensTotalsCheck.java` (신규) | 렌즈 총합 검증 |
| `.../query/SnapshotFactsMapper.java` | 심볼로 시장 배지 조회 |
| `.../view/SnapshotViewService.java` · `view/assembly/NoticeCollector.java` · `RowValuePolicy.java` · `CurrencyDisplayPolicy.java` · `FxAppliedMerge.java`(신규) | 응답 조립 |
| `src/test/resources/golden/allocation-sector-lookthrough.json` · `positions-lookthrough.json`(신규) | 렌즈 골든 |
| `src/test/java/com/stockproject/portfolio/query/aggregate/LensDecompositionTest.java`(신규) · `LensPreservationTest.java` · `AxisSqlTest.java` | 쿼리 테스트 |
| `src/test/java/com/stockproject/portfolio/api/LookThroughGoldenTest.java`(신규) · `SixViewGoldenTest.java` | 골든 |
| `src/test/java/com/stockproject/portfolio/validation/LensTotalsCheckTest.java` · `view/assembly/FxAppliedMergeTest.java`(신규) · `NoticeCollectorTest.java` · `RowValuePolicyTest.java` | 단위 |

**front-end** (`.worktrees/front-end-look-through`, 브랜치 `feat/look-through-screen`)

| 파일 | 책임 |
|---|---|
| `src/api/types.ts` | `Row.quantity` · `Row.instrument_count`를 `number \| null` |
| `src/screens/positions/PositionRow.tsx` · `sort.ts` · `PositionsScreen.tsx` | 기타 행 · 정렬 · 렌즈 설명 |
| `src/screens/allocation/AllocationScreen.tsx` | 미분류 · 렌즈 설명 |
| `src/fixtures/golden.ts` · `src/fixtures/golden/allocation-sector-lookthrough.json` · `positions-lookthrough.json` | 골든 |
| `src/__tests__/positions.test.tsx` · `allocation.test.tsx` · `envelope.test.tsx` · `sort.test.ts` | 테스트 |

---

## 픽스처 수치 (Task 1이 만들고 이후 태스크가 단언한다)

기준일 2026-07-27, 환율 USD/KRW 1,400. 133690은 COVERED, 구성비중 기준일 2026-07-24.

| 구성종목 | 비중 | yhr 연금 라인 평가 11,000,000 / 원가 10,000,000 | jdh 라인 평가 5,500,000 / 원가 5,000,000 | 환산수량(yhr) | 현지(yhr) |
|---|---|---|---|---|---|
| AAPL | 0.448 | 4,928,000 / 4,480,000 | 2,464,000 / 2,240,000 | 16 (220 × 1,400) | 3,520.0000 USD |
| MSFT | 0.294 | 3,234,000 / 2,940,000 | 1,617,000 / 1,470,000 | 6.6 (350 × 1,400) | 2,310.0000 USD |
| 005930 | 0.1424 | 1,566,400 / 1,424,000 | 783,200 / 712,000 | 22 (71,200) | 1,566,400 KRW |
| CASH-KRW | 0.05 | 기타로 | 기타로 | — | — |
| 기타 | | 1,271,600 / 1,156,000 | 635,800 / 578,000 | null | |

yhr 렌즈 종목 행(필터 없음, 응답 순서 = 평가금액 내림차순 · 기타 끝): 005930 15,806,400 · 222주 / AAPL 11,088,000 · 36주 · 7,920.0000 USD / 000660 9,000,000 / MSFT 8,134,000 · 16.6주 · 5,810.0000 USD / NAVER 8,000,000 / CASH-KRW 4,560,000 / 069500 2,000,000(미분해) / CASH-USD 140,000 / 기타 1,271,600. 합 60,000,000.

yhr 렌즈 섹터 행(응답 순서): 반도체 24,806,400(2종목) · 소프트웨어 16,134,000(2) · IT서비스 11,088,000(1, 7,920.0000 USD) · 현금 4,700,000(0) · 미분류 2,000,000(1) · 기타 1,271,600(null).

yhr 응답 합계(두 렌즈 동일): 총자산 60,000,000 · 유가증권 55,300,000 · 예수금 4,700,000 · 매입금액 50,600,000(예수금 제외) · 평가손익 4,700,000. `LensTotals`(예수금 포함 라인 합)는 평가 60,000,000 · 원가 55,300,000.

---

### Task 0: 작업 공간과 전용 DB

**Files:** 없음(머신 상태 변경)

- [ ] **Step 1: 아래 명령을 사용자에게 보여 주고 승인받은 뒤 실행한다.**

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project
git -C back-end fetch origin
git -C back-end worktree add -b feat/look-through ../.worktrees/back-end-look-through origin/main
git -C front-end fetch origin
git -C front-end worktree add -b feat/look-through-screen ../.worktrees/front-end-look-through origin/main
```

- [ ] **Step 2: 전용 DB를 만든다(같은 승인에 포함해 묻는다).** 로컬 Postgres 컨테이너에서 `CREATE DATABASE portfolio_test_lens OWNER portfolio`, 그 안에 `app` · `data` 스키마를 기존 테스트 DB와 같은 방법(`2026-10-14-test-environment-setup.md`)으로 만든다.
- [ ] **Step 3: 기준선.** back-end: Global Constraints의 테스트 명령(DB 테스트 승인 후). Expected: 전부 통과. front-end: `npm ci && npx jest && npx tsc --noEmit`. Expected: 통과.

---

### Task 1: V14 미러와 렌즈 픽스처

**Files:**
- Create: `src/main/resources/db/external/V14__etf_constituent_mirror.sql`, `src/main/resources/db/sample/sample_lookthrough.sql`
- Modify: `src/main/resources/db/sample/sample_portfolio.sql`
- Test: `src/test/java/com/stockproject/portfolio/query/aggregate/LensDecompositionTest.java`

**Interfaces:**
- Produces: 테이블 `data.etf_constituent(as_of date, etf_instrument_id uuid, underlying_instrument_id uuid, weight numeric(9,6))` PK `(as_of, etf_instrument_id, underlying_instrument_id)`, 모두 NOT NULL. 상수 `KODEX200 = 10000000-0000-0000-0000-000000000009`. 픽스처 수치는 위 표.

- [ ] **Step 1: 실패하는 테스트.** `LensDecompositionTest`를 `@SpringBootTest @ActiveProfiles("test") @Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_lookthrough.sql"})`로 만들고 첫 테스트를 둔다.

```java
@Test
void 덧씌움_픽스처가_적재된다() {
    assertThat(jdbc.sql("SELECT count(*) FROM etf_constituent WHERE etf_instrument_id = ?")
            .param(TIGER).query(Long.class).single()).isEqualTo(4L);
    assertThat(jdbc.sql("SELECT market_value_krw FROM position_line WHERE as_of = ? AND instrument_id = ?")
            .param(AS_OF).param(KODEX200).query(BigDecimal.class).single())
            .isEqualByComparingTo("2000000");
}
```

- [ ] **Step 2: 실행해 실패를 확인한다.** Expected: `relation "etf_constituent" does not exist` 또는 스크립트 없음.
- [ ] **Step 3: V14 미러.** 머리 주석은 `V3__etf_coverage_mirror.sql`의 관례를 따른다(데이터 소유 · 운영 미적용 · 인덱스는 운영 실행 계획을 보고 데이터에 요청). 인덱스 없음.
- [ ] **Step 4: `sample_portfolio.sql`.** TRUNCATE 목록에 `etf_constituent`를 더하고, `etf_coverage`를 비우는 이유 주석은 "덧씌움이 없으면 133690이 미분해다"로 고친다.
- [ ] **Step 5: `sample_lookthrough.sql`.** 머리 주석에 "sample_portfolio.sql 뒤에, 다른 샘플보다 마지막에 적용한다. 렌즈 골든은 이 데이터라 총자산이 DIRECT 골든과 다르다"를 쓴다. `SET search_path = app, data; BEGIN; … COMMIT;`
  - `instrument`: `069500` `KODEX 200` ETF KR KRW sector NULL `is_leveraged false`, isin `KR7069500007`, id `…0009`.
  - `position_line` 2026-07-27 · 07-24 각각 yhr 위탁(`…0001`) × 069500: 수량 50, 원가 1,800,000, 평가 2,000,000(로컬 = 원화), `fx_rate` 1, `fx_as_of` 그날, `source_as_of` 그날 15:30+09, `is_carried_forward false`, 07-27은 `is_final false`, 07-24는 `true`.
  - `etf_coverage`: 133690 · 069500 모두 `COVERED`, `as_of 2026-07-24`.
  - `etf_constituent` 2026-07-24: 133690 → AAPL 0.448 · MSFT 0.294 · 005930 0.1424 · CASH-KRW 0.05, 069500 → 005930 0 · 000660 0.
  - `fx_rate`: `2026-07-27` · `USD/KRW` · `BASE` · 1400 · `SAMPLE`.
  - `dim_market_calendar`: KR 07-24 · 07-27(close 15:30+09), US 07-24 · 07-27(close 16:00-04). 모두 거래일, prev/next는 실제 거래일. `ON CONFLICT (market, date) DO UPDATE`.
  - `adjusted_price_daily`: AAPL 07-24 close 220, MSFT 07-24 close 350, 005930 07-27 close 71200. open · high · low = close, volume 0, adj_factor 1. `ON CONFLICT (instrument_id, date) DO UPDATE`.
- [ ] **Step 6: 통과 확인.** `--tests '*LensDecompositionTest'`. Expected: PASS.
- [ ] **Step 7: 커밋(요청 시).** `chore: 구성비중 미러와 렌즈 샘플을 더한다`

---

### Task 2: 분해 판정 조각과 미분해 집계

**Files:**
- Modify: `src/main/resources/mapper/AggregateMapper.xml`, `src/main/resources/mapper/EtfCoverageMapper.xml`, `.../query/aggregate/EtfCoverageMapper.java`
- Create: `.../query/aggregate/DecomposedEtf.java`
- Test: `LensDecompositionTest.java`, `LensPreservationTest.java`

**Interfaces:**
- Produces: SQL 조각 `AggregateMapper.decomposableWeight` — 컬럼 `etf_instrument_id, underlying_instrument_id, as_of, weight, weight_sum`. `EtfCoverageMapper.decomposedAt(UserScope scope, LocalDate asOf, LineFilter filter): DecomposedEtf`. `record DecomposedEtf(LocalDate oldestAsOf, int count)` — 분해 대상이 없으면 `oldestAsOf == null`, `count == 0`. `undecomposedAt`의 시그니처는 그대로.

- [ ] **Step 1: 실패하는 테스트(`LensDecompositionTest`).** 헬퍼 `setCoverage(UUID etf, String state)`, `replaceConstituents(UUID etf, LocalDate asOf, Map<UUID, String> weights)`(그 ETF의 모든 행을 지우고 넣는다)를 둔다.

| 테스트 | 준비 | 단언 (`undecomposedAt(YHR, AS_OF, NONE)` / `decomposedAt(...)`) |
|---|---|---|
| `비중이_있는_COVERED_ETF만_분해_대상이다` | 픽스처 그대로 | 미분해 count 1 · 2,000,000 · keys `[069500]` / 분해 `oldestAsOf 2026-07-24` · count 1 |
| `UNAVAILABLE이면_남은_행이_있어도_미분해다` | 133690 `UNAVAILABLE` | 미분해 count 2 · 13,000,000 / 분해 count 0 · oldest null |
| `현금만_매칭된_ETF는_미분해다` | 133690 → CASH-KRW 0.05만 | 미분해 count 2 |
| `최신_기준일만_본다` | 133690에 07-17 · AAPL 0.9 추가, 07-24에 비중 0 행만 남김 | 미분해 count 2 (07-17로 물러나지 않음) |
| `마스터에_없는_종목만_있으면_미분해다` | 133690 → 임의 UUID 0.5만 | 미분해 count 2 |
| `계좌유형_필터가_미분해_집계를_좁힌다` | `LineFilter(Set.of(), Set.of(AccountType.PENSION), Set.of(), Set.of())` | 미분해 count 0 / 분해 count 1 |
| `분해_집계는_범위의_가장_오래된_기준일을_센다` | 133690의 07-24 행을 07-20으로 옮김 | 분해 `oldestAsOf 2026-07-20` · count 1 |

`LensPreservationTest`: `확보된_ETF는_미확보_분기에서_빠진다`를 지운다(분해 갈래가 생기면 사실이 아니다). 나머지 미분해 테스트는 그대로 통과해야 한다(덧씌움 없는 샘플).

- [ ] **Step 2: 실행해 실패를 확인한다.** Expected: `decomposedAt` 없음(컴파일 실패) 또는 COVERED · 비중 0인 069500이 분해 대상으로 세져 count 불일치.
- [ ] **Step 3: `decomposableWeight` 조각.** 조각 위 주석에 판정 규칙(COVERED · 최신 기준일은 거르기 전에 · 양수 비중 · 마스터에 있는 비현금)을 쓴다.

```xml
<sql id="decomposableWeight">
  SELECT ec.etf_instrument_id, ec.underlying_instrument_id, ec.as_of, ec.weight,
         sum(ec.weight) OVER (PARTITION BY ec.etf_instrument_id) AS weight_sum
    FROM etf_constituent ec
    JOIN etf_coverage cov ON cov.etf_instrument_id = ec.etf_instrument_id
                         AND cov.state = 'COVERED'
    JOIN instrument u ON u.instrument_id = ec.underlying_instrument_id
                     AND u.asset_class &lt;&gt; 'CASH'
   WHERE ec.weight &gt; 0
     AND ec.as_of = (SELECT max(x.as_of) FROM etf_constituent x
                      WHERE x.etf_instrument_id = ec.etf_instrument_id)
</sql>
```

- [ ] **Step 4: `EtfCoverageMapper.xml`.** `undecomposedAt`의 `NOT EXISTS (… etf_coverage …)`를 `NOT EXISTS (SELECT 1 FROM (<include refid="…AggregateMapper.decomposableWeight"/>) d WHERE d.etf_instrument_id = pl.instrument_id)`로 바꾸고, 계좌유형 필터 `AND owner.account_type IN (…)`를 `filter.accountTypes`가 있을 때 더한다. `decomposedAt`은 같은 범위 · 필터의 라인을 `(SELECT DISTINCT etf_instrument_id, as_of FROM (<조각>) d0) d`와 `d.etf_instrument_id = pl.instrument_id`로 조인해 `min(d.as_of)`와 `count(DISTINCT pl.instrument_id)`를 낸다.
- [ ] **Step 5: 통과 확인.** `--tests '*LensDecompositionTest' --tests '*LensPreservationTest'`. Expected: PASS.
- [ ] **Step 6: 커밋(요청 시).** `feat: 구성비중으로 분해할 수 있는 ETF를 한 조각에서 판정한다`

---

### Task 3: 구성종목 · 기타 갈래와 원화 안분

**Files:**
- Modify: `AggregateMapper.xml`, `AggregateMapper.java`, `AxisSql.java`
- Create: `.../query/aggregate/LensTotals.java`
- Test: `LensDecompositionTest.java`, `LensPreservationTest.java`, `AxisSqlTest.java`

**Interfaces:**
- Consumes: `decomposableWeight`(Task 2).
- Produces: `target_line` 컬럼에 `is_residual boolean` 추가(DIRECT는 `false`). `record LensTotals(BigDecimal marketValueKrw, BigDecimal costAmountKrw)`. `AggregateMapper.totals(UserScope scope, LocalDate asOf, Lens lens): LensTotals`가 `sumMarketValueKrw`를 대체한다. 렌즈 영향 축(`AxisKey.lensSensitive() == true`)의 키 · 라벨 식은 `CASE WHEN t.is_residual THEN 'OTHER' ELSE (<기존 식>) END` / 라벨은 `GroupKey.OTHER.label()`.

- [ ] **Step 1: 실패하는 테스트.** 표의 단언은 따로 적지 않으면 연금 계좌 필터 `withAccounts(KIS_IRP)`로 본다. 헬퍼 `instrumentRows(UserScope, LineFilter)` = `repository.aggregate(scope, AS_OF, List.of(AxisKey.INSTRUMENT), Lens.LOOK_THROUGH, filter)`의 key → `GroupNode` 맵. `setLine(UUID account, UUID instrument, String marketKrw, String costKrw)`(로컬도 같은 값으로).

| 테스트 | 준비 | 단언(평가 / 원가 원화) |
|---|---|---|
| `픽스처_라인을_비중대로_나눈다` | 그대로 | AAPL 4,928,000 / 4,480,000 · MSFT 3,234,000 / 2,940,000 · 005930 1,566,400 / 1,424,000 · OTHER 1,271,600 / 1,156,000 · 133690 키 없음 |
| `모자란_비중은_기타가_된다` | 133690 라인 1,000,000 / 900,000, 비중 AAPL 0.5 · MSFT 0.3 · CASH-KRW 0.15 | AAPL 500,000 / 450,000 · MSFT 300,000 / 270,000 · OTHER 200,000 / 180,000 |
| `내림_끝전은_기타가_된다` | 라인 1,000,001, 비중 같음 | AAPL 500,000 · MSFT 300,000 · OTHER 200,001 |
| `비중_합이_1을_넘으면_나눈다` | 라인 1,000,000, AAPL 0.6 · MSFT 0.402 | AAPL 598,802 · MSFT 401,197 · OTHER 1 |
| `비중_0_이하와_마스터에_없는_종목은_기타로_간다` | 픽스처 + NAVER 0 · 000660 −0.01 · 임의 UUID 0.1 | NAVER · 000660 키 없음(연금 필터), OTHER 1,271,600 그대로 |
| `기타가_0이면_기타_행이_없다` | 라인 1,000,000 / 900,000, 005930 1.0만 | 005930 1,000,000 / 900,000, OTHER 키 없음 |
| `같은_ETF의_두_라인은_따로_내린다` | 연금 133690 라인을 1,000,002 / 1,000,002로, yhr 위탁에 133690 라인 1,000,002 / 1,000,002 추가 | 필터 없이 OTHER 평가 231,204 (115,602 × 2), AAPL 7,056,000 (직접 6,160,000 + 448,000 × 2). 합친 뒤 내리면 231,202 · 7,056,001이 나와 구별된다 |
| `다른_사용자는_자기_라인만_나뉜다` | 그대로, JDH, 필터 없이 | AAPL 2,464,000 · MSFT 1,617,000 · 005930 7,903,200(직접 7,120,000 + 783,200) · OTHER 635,800 |
| `미분해_ETF는_그대로_남는다` | 그대로, 필터 없이 | 069500 2,000,000 |
| `미분해로_남은_ETF와_안내가_같다` | 그대로 · 133690 `UNAVAILABLE` 두 경우, 필터 없이 | 종목 축 행 중 자산군이 ETF인 키 집합 = `undecomposedAt(...).keys()` |
| `기타는_섹터_축에서도_한_행이다` | 섹터 축 | OTHER 1,271,600, `key().other()` 참, 마지막 행 |

`LensPreservationTest`는 `sumMarketValueKrw`를 `totals`로 바꾸고 평가 · 원가 둘 다 단언한다. 구조 검사 `렌즈_조각이_스코프를_한_곳에서_건다`는 `scopedLine` include가 여전히 2개(DIRECT 1 · 렌즈 1)이고 `FROM position_line`이 없음을 본다. 새 테스트 `덧씌움에서도_두_렌즈의_총합이_같다`: 메서드에 `@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_lookthrough.sql"})` — 두 파일을 다 적는다(메서드 `@Sql`은 클래스 것을 덮어쓴다). yhr 60,000,000 / 55,300,000, jdh 14,000,000 / 두 렌즈 같은 원가.

`AxisSqlTest`: `분류_축의_폴백이_식에_있다`의 INSTRUMENT 기대를 `"CASE WHEN t.is_residual THEN 'OTHER' ELSE (i.symbol) END"`로, ACCOUNT 키 식에는 `is_residual`이 없음을 더한다. `CASH_분리가_FILTER_절로_나타난다`가 세는 `FILTER (WHERE i.asset_class &lt;&gt; 'CASH')` 개수를 `instrumentCount` 변경에 맞춰 5로 고친다.

- [ ] **Step 2: 실행해 실패를 확인한다.** Expected: 133690 키가 남거나 AAPL 등이 없음.
- [ ] **Step 3: `targetLine` 렌즈 분기.** 갈래마다 계산 규칙을 주석으로 단다. 계산은 설계 §4.1 · §4.2 그대로다.

```sql
WITH dw AS (<include refid="decomposableWeight"/>),
     line AS (SELECT <include refid="targetLineColumns"/>, pl.source_as_of
              <include refid="scopedLine"/>),
     part AS (SELECT l.*, d.underlying_instrument_id,
                     d.weight / greatest(d.weight_sum, 1)                         AS w_eff,
                     floor(l.market_value_krw * d.weight / greatest(d.weight_sum, 1)) AS part_market_krw,
                     floor(l.cost_amount_krw  * d.weight / greatest(d.weight_sum, 1)) AS part_cost_krw
                FROM line l JOIN dw d ON d.etf_instrument_id = l.instrument_id)
SELECT <그대로 갈래: line 중 dw에 없는 것, is_residual false>
UNION ALL
SELECT <구성종목 갈래: part, instrument_id = underlying_instrument_id, 원화 = part_*_krw,
        수량 · 현지 금액은 이 태스크에서 NULL 자리만 두고 Task 4 · 5가 채운다, is_residual false>
UNION ALL
SELECT <기타 갈래: part를 (account_id, instrument_id)로 묶어 라인 원화 − sum(part_*_krw),
        수량 NULL, is_residual true, HAVING 평가 · 원가 기타 중 하나라도 0이 아님>
```

  이 태스크에서 구성종목 갈래의 `quantity` · `*_local`은 임시로 원화 값을 넣지 않고 `NULL`로 둔다. `measures`의 `instrumentCount`에 `AND NOT t.is_residual`을 더한다. `totals`는 `sum(market_value_krw)` · `sum(cost_amount_krw)`를 `coalesce(…, 0)`로 낸다.
- [ ] **Step 4: `AxisSql`.** `fragmentsOf`가 아니라 `keyExpr` · `labelExpr`가 렌즈 영향 축에 기타 식을 씌운다. 클래스 주석의 별칭 목록에 `t`(대상 라인)를 더한다.
- [ ] **Step 5: 통과 확인.** `--tests '*LensDecompositionTest' --tests '*LensPreservationTest' --tests '*AxisSqlTest' --tests '*SixViewGoldenTest'`. Expected: 앞 셋 PASS, `SixViewGoldenTest`의 렌즈 골든은 Task 8 전까지 실패할 수 있다 — 그 한 케이스만 실패인지 확인한다.
- [ ] **Step 6: 커밋(요청 시).** `feat: 렌즈가 ETF를 구성종목과 기타로 나눈다`

---

### Task 4: 현지 금액 · 환율 · 병기 판정

**Files:**
- Modify: `AggregateMapper.xml`, `AggregateRowDto.java`, `AggregateQueryRepository.java`, `MeasureBundle.java`, `CurrencyDisplayPolicy.java`, `EtfCoverageMapper.xml` · `EtfCoverageMapper.java`
- Create: `.../view/assembly/FxAppliedMerge.java`
- Test: `LensDecompositionTest.java`, `FxAppliedMergeTest.java`, `CurrencyDisplayPolicy`를 쓰는 기존 테스트

**Interfaces:**
- Produces: `MeasureBundle`에 `boolean quantityUnknown, boolean localUnknown` 두 컴포넌트를 끝에 더하고, 기존 5인자 생성자는 둘 다 `false`로 위임해 남긴다. `AggregateRowDto.quantityUnknown()` · `localUnknown()`(세터 매핑). `EtfCoverageMapper.lensFxRates(UserScope, LocalDate, LineFilter): List<AppliedFxRate>` — 렌즈에서 원화 ETF 안 달러 종목을 환산했을 때만 `("USD", rate, as_of)` 한 줄. `FxAppliedMerge.oldestPerPair(List<FxApplied> rates): List<FxApplied>` — 통화쌍마다 `fxAsOf`가 가장 이른 것 하나, 입력 첫 등장 순서 유지.

- [ ] **Step 1: 실패하는 테스트.**
  - `달러_구성종목은_환율로_현지_금액을_낸다`: 연금 필터, AAPL 현지 3,520.0000 · MSFT 2,310.0000, 005930 현지 1,566,400.
  - `합쳐진_행의_현지_금액은_두_몫의_합이다`: 필터 없이 AAPL `currencies().single() == USD`, 현지 7,920.0000, MSFT 5,810.0000.
  - `환율이_없으면_현지_금액이_미상이다`: `DELETE FROM fx_rate`, 연금 필터 AAPL `localUnknown()` 참, `CurrencyDisplayPolicy.localOf(...)` 비어 있음.
  - `달러_구성종목이_섞인_계좌는_병기하지_않는다`: 계좌 축 연금 계좌 행 `currencies()`가 `{KRW, USD}` — `localOf` 비어 있음.
  - `기타의_현지_금액은_ETF_통화로_나눈다`: 연금 필터 · 종목 축 OTHER 행 `currencies()`가 `{KRW}`이고 현지 평가 합이 1,271,600.
  - `렌즈_환율은_달러_구성종목이_있을_때만_나온다`: `lensFxRates(YHR, AS_OF, NONE)` = `[USD 1400 2026-07-27]`, 133690 `UNAVAILABLE`이면 빈 목록.
  - `FxAppliedMergeTest.통화쌍마다_가장_오래된_환율을_남긴다`: `[USD/KRW 1400 07-24, USD/KRW 1400 07-27]` → `[USD/KRW 1400 07-24]`.
- [ ] **Step 2: 실행해 실패를 확인한다.**
- [ ] **Step 3: 구현.** 렌즈 분기 앞 CTE에 `fx AS (SELECT rate, as_of FROM fx_rate WHERE currency_pair = 'USD/KRW' AND rate_type = 'BASE' AND as_of &lt;= #{asOf} ORDER BY as_of DESC LIMIT 1)`. 구성종목 · 기타 갈래가 `instrument`를 ETF(`ei`)와 구성종목(`u`)으로 조인해 설계 §4.3 표대로 `*_local`을 낸다(`fx`는 `LEFT JOIN fx ON true`). `measures`에 `bool_or(t.market_value_local IS NULL) AS localUnknown`. `AggregateQueryRepository.bundleOf`가 두 플래그를 옮긴다(`Boolean` null은 false). `CurrencyDisplayPolicy.localOf`는 `localUnknown`이면 빈 값.
- [ ] **Step 4: 통과 확인.** 새 테스트 + `--tests '*Currency*' --tests '*DerivedTest'`. Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 구성종목의 현지 금액을 그 종목 통화로 낸다`

---

### Task 5: 환산수량

**Files:**
- Modify: `AggregateMapper.xml`, `RowValuePolicy.java`
- Test: `LensDecompositionTest.java`, `RowValuePolicyTest.java`

**Interfaces:**
- Consumes: `fx` CTE(Task 4), `MeasureBundle.quantityUnknown()`.
- Produces: 구성종목 라인의 `quantity`. `RowValuePolicy`의 `QUANTITY`는 `node.key().other() || bundle.quantityUnknown()`이면 null, `INSTRUMENT_COUNT`는 `node.key().other()`이면 null.

- [ ] **Step 1: 실패하는 테스트.**
  - `구성종목을_종가로_환산한다`: 연금 필터 AAPL 16 · MSFT 6.6 · 005930 22 (`isEqualByComparingTo`).
  - `직접_보유와_경유분_수량을_더한다`: 필터 없이 005930 222 · AAPL 36 · MSFT 16.6.
  - `경유분_종가가_없으면_합쳐진_행_수량이_null이다`: `DELETE FROM adjusted_price_daily WHERE instrument_id = MSFT`, 필터 없이 MSFT `quantityUnknown()` 참. AAPL은 거짓.
  - `가격_기준일은_라인_시각에_마감한_마지막_거래일이다`: US 07-24 종가를 지우고 07-27 종가 230을 넣어도 AAPL 연금 몫은 미상(07-27 미국 마감이 라인 시각 뒤).
  - `RowValuePolicyTest.기타_행은_수량과_종목수가_null이다`: `GroupNode(GroupKey.OTHER, bundle)`의 행 지표에 `quantity` · `instrument_count` 키가 있고 값이 null.
  - `RowValuePolicyTest.수량_미상이면_null이다`: `quantityUnknown = true` 묶음 → `quantity` null.
- [ ] **Step 2: 실행해 실패를 확인한다.**
- [ ] **Step 3: 구현.** 구성종목 갈래에 `LEFT JOIN LATERAL (SELECT max(c.date) AS price_date FROM dim_market_calendar c WHERE c.market = u.market AND c.is_trading_day AND c.close_at &lt;= l.source_as_of) pd ON true`와 `LEFT JOIN adjusted_price_daily p ON p.instrument_id = u.instrument_id AND p.date = pd.price_date`. `quantity = CASE WHEN p.close IS NULL OR (u.currency &lt;&gt; 'KRW' AND fx.rate IS NULL) THEN NULL ELSE round(part_market_krw / (p.close * CASE WHEN u.currency = 'KRW' THEN 1 ELSE fx.rate END), 8) END`. `measures`에 `bool_or(t.quantity IS NULL AND NOT t.is_residual) AS quantityUnknown`.
- [ ] **Step 4: 통과 확인.** Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 구성종목 환산수량을 시장별 가격 기준일 종가로 낸다`

---

### Task 6: 렌즈 총합 검증

**Files:**
- Create: `.../validation/LensTotalsCheck.java`, `src/test/java/.../validation/LensTotalsCheckTest.java`
- Modify: `.../view/SnapshotViewService.java`

**Interfaces:**
- Consumes: `AggregateMapper.totals`(Task 3).
- Produces: `@Component LensTotalsCheck(AggregateMapper mapper)`, `void verify(UserScope scope, LocalDate asOf, Lens lens)` — `lens == DIRECT`면 아무것도 조회하지 않고 돌아간다. 렌즈면 두 렌즈의 `LensTotals`가 다를 때 `FactInvariantViolation(List.of("렌즈 전개 전후 총합 불일치 (평가 %s ≠ %s · 원가 %s ≠ %s)"))`. `SnapshotViewService.render`가 `invariants.validate` 바로 뒤에 언제나 부른다.

- [ ] **Step 1: 실패하는 단위 테스트(Mockito).**
  - `DIRECT면_조회하지_않는다`: `verifyNoInteractions(mapper)`.
  - `총합이_같으면_통과한다`: 두 렌즈 모두 `(60000000, 55300000)`.
  - `평가_총합이_다르면_실패한다`: LOOK_THROUGH `(59999999, 55300000)` → `FactInvariantViolation`, 메시지에 `59999999`.
  - `원가_총합이_다르면_실패한다`.
- [ ] **Step 2: 실행해 실패를 확인한다.** `./gradlew test --tests '*LensTotalsCheckTest'`(DB 없음). Expected: 컴파일 실패.
- [ ] **Step 3: 구현과 연결.**
- [ ] **Step 4: 통과 확인.** 단위 테스트 + `--tests '*SnapshotViewApiTest'`(DB). Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 렌즈 요청마다 전개 전후 총합을 맞춰 본다`

---

### Task 7: 안내 · 시장 배지

**Files:**
- Modify: `NoticeCollector.java`, `SnapshotViewService.java`, `SnapshotFactsMapper.java`
- Test: `NoticeCollectorTest.java`, `LensDecompositionTest.java` 또는 `SnapshotViewApiTest.java`

**Interfaces:**
- Consumes: `decomposedAt` · `lensFxRates`(Task 2 · 4), `FxAppliedMerge.oldestPerPair`.
- Produces: `SnapshotFactsMapper.badgesFor(List<String> symbols): List<InstrumentBadge>` — `@Select`에 `<script>` + `<foreach>`로 `SELECT symbol, market FROM instrument WHERE symbol IN (…)`(같은 매퍼의 기존 `<script>` 쿼리 관례를 따른다), 빈 목록이면 호출하지 않는다. 문구:
  - `CONSTITUENT_AS_OF`: `"구성비중 기준 %s".formatted(MONTH_DAY.format(oldest))`, params `oldest` · `count`.
  - `CONSTITUENT_UNAVAILABLE`: `"%d개 ETF는 구성종목으로 나누지 못해 그대로 표시했습니다"`, params 그대로.

- [ ] **Step 1: 실패하는 테스트.**
  - `NoticeCollectorTest`: 기존 미분해 문구 단언을 새 문구로. `구성비중_기준일을_알린다`: `constituents(2026-07-24, 1)` → 메시지 `구성비중 기준 07-24`, params `oldest 2026-07-24` · `count 1`. 분해 대상이 없으면(`constituents(null, 0)`) 없음.
  - API(덧씌움 `@Sql`): `/portfolio/views/positions?lens=LOOK_THROUGH`의 AAPL 행 `market` `US`, 005930 `KR`, OTHER 행에 `market` 키 없음. notices에 `CONSTITUENT_AS_OF`(`oldest` 2026-07-24), `CONSTITUENT_UNAVAILABLE`(keys `[069500]`), `FX_APPLIED`의 USD/KRW `fx_as_of` 2026-07-24. `/portfolio/views/summary` notices에 `CONSTITUENT_*` 없음.
- [ ] **Step 2: 실행해 실패를 확인한다.**
- [ ] **Step 3: 구현.** `collectNotices`가 렌즈일 때 `context.constituents(d.oldestAsOf(), d.count())`를 채우고, `fxApplied`에 `lensFxRates`를 더해 `FxAppliedMerge.oldestPerPair`로 합친다. `rowFields`는 `POSITIONS`이고 렌즈일 때 집계 결과 행 키(OTHER 제외)로 `badgesFor`를 부른다. `DIRECT`는 지금처럼 `instrumentBadges`.
- [ ] **Step 4: 통과 확인.** Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 렌즈 응답에 구성비중 기준일과 구성종목 시장을 싣는다`

---

### Task 8: 렌즈 골든

**Files:**
- Create: `src/test/java/.../api/LookThroughGoldenTest.java`, `src/test/resources/golden/positions-lookthrough.json`
- Modify: `src/test/resources/golden/allocation-sector-lookthrough.json`, `SixViewGoldenTest.java`

**Interfaces:**
- Produces: 골든 두 파일(앱이 복사한다).

- [ ] **Step 1: 테스트 옮기기.** `SixViewGoldenTest`의 렌즈 케이스를 지우고, `LookThroughGoldenTest`(`@Sql` 두 파일)에 `/portfolio/views/allocation?axis=sector&lens=LOOK_THROUGH` · `/portfolio/views/positions?lens=LOOK_THROUGH`를 `NON_EXTENSIBLE`로 비교한다. 클래스 주석에 "DIRECT 골든과 다른 데이터라 총자산이 60,000,000이다". 행 합 = 총자산 검사도 두 경로에 둔다.
- [ ] **Step 2: 골든 파일을 손으로 쓴다.** 기존 파일 모양을 따르고 값은 위 "픽스처 수치"에서 옮긴다. 행 순서와 합계는 "픽스처 수치"의 응답 순서 · 응답 합계를 따른다. 비중은 `market_value_krw ÷ 60,000,000`을 기존 반올림 규칙으로. 기타 행은 종목별 골든에서 `quantity: null`, 비중 골든에서 `instrument_count: null` — 그 화면의 행 지표에 없는 키는 넣지 않는다(비교가 `NON_EXTENSIBLE`). notices 순서는 `NoticeCode` 순서(FX_APPLIED → STALE_ACCOUNTS → CONSTITUENT_AS_OF → CONSTITUENT_UNAVAILABLE → LENS_METRICS_OMITTED).
- [ ] **Step 3: 실행해 비교한다.** Expected: PASS. 실패하면 차이가 손 계산 오류인지 구현 오류인지 가려 고친다 — 응답을 그대로 붙여 넣지 않는다.
- [ ] **Step 4: 전체 백엔드 테스트.** Global Constraints 명령. Expected: 전부 통과.
- [ ] **Step 5: 커밋(요청 시).** `test: 렌즈 골든을 분해된 응답으로 바꾼다`

---

### Task 9: 앱

**Files:**
- Modify: `src/api/types.ts`, `src/screens/positions/PositionRow.tsx`, `sort.ts`, `PositionsScreen.tsx`, `src/screens/allocation/AllocationScreen.tsx`, `src/fixtures/golden.ts`, `src/fixtures/golden/allocation-sector-lookthrough.json`
- Create: `src/fixtures/golden/positions-lookthrough.json`
- Test: `src/__tests__/positions.test.tsx`, `allocation.test.tsx`, `envelope.test.tsx`, `sort.test.ts`

**Interfaces:**
- Consumes: 백엔드 골든 두 파일(Task 8)을 그대로 복사.
- Produces: `goldenPositionsLookThrough: PositionsResponse`. 상수 `OTHER_KEY = 'OTHER'`를 `src/screens/positions/sort.ts`에서 export하고 `PositionRow`가 쓴다.

- [ ] **Step 1: 골든 복사와 타입.** 두 JSON을 복사하고 `golden.ts`에 `goldenPositionsLookThrough`를 기존 방식(`AsJson` 후 단언)으로 더한다. `Row.quantity?: number | null`, `Row.instrument_count?: number | null`.
- [ ] **Step 2: 실패하는 테스트.**
  - `sort.test.ts` `기타_행은_어느_정렬에서도_맨_끝이다`: OTHER(평가 최대 · 라벨 `기타…`)와 일반 행 둘을 네 정렬 키 모두에서 정렬 → 마지막이 OTHER.
  - `positions.test.tsx` 렌즈 블록(`goldenPositionsLookThrough`로 응답): 기타 행 이름 `기타`, 둘째 줄에 `ETF 안 현금과 찾지 못한 종목`, `환산 —주` 없음 · `미분해` 배지 1개(069500) · `환산 222주`(005930) · 구성종목 행 배지(AAPL · MSFT 행 안에 `미국`, 005930 행 안에 `국내`) · 기존 미분해 notice의 keys `133690` 기대는 `069500`으로.
  - `positions.test.tsx` `토글 설명`(지금 `/ETF를 안에 든 종목들로 쪼개서 봅니다/`를 찾는다): `구성종목을 확인할 수 있는 ETF만 안에 든 종목들로 쪼개서 봅니다.`와 `쪼개지 못한 ETF는 그대로 남습니다.`로 바꾼다.
  - `allocation.test.tsx`: 미분류 ⓘ가 DIRECT · 렌즈 모두에 있고 문구가 `업종 정보가 없거나 ETF처럼 하나의 업종으로 묶기 어려운 종목이에요.` · 렌즈 설명이 설계 §6.2 표의 문구 · 기존 133690 미분해 기대는 069500으로.
  - `envelope.test.tsx`: 옛 문구 `⚠ 1개 ETF는 구성종목 데이터가 없어 분해하지 않았습니다` 기대를 `⚠ 1개 ETF는 구성종목으로 나누지 못해 그대로 표시했습니다`로, 렌즈 골든의 캡션에 `구성비중 기준 07-24`.
- [ ] **Step 3: 실행해 실패를 확인한다.** `npx jest`. Expected: 위 테스트 FAIL.
- [ ] **Step 4: 구현.** `PositionRow`는 `row.key === OTHER_KEY`면 이름 `기타`, 배지 없음, 둘째 줄 `{formatPct(row.weight_pct)} · ETF 안 현금과 찾지 못한 종목`. `sortRows`는 OTHER를 떼어 정렬 뒤 끝에 붙인다. 도움말 문구는 설계 §6.2 표 그대로. `helpFor`의 미분류 조건에서 `lens === 'DIRECT'`를 뺀다.
- [ ] **Step 5: 통과 확인.** `npx jest && npx tsc --noEmit`. Expected: 통과.
- [ ] **Step 6: 커밋(요청 시).** `feat: 렌즈 화면이 기타 행과 분해 범위를 보여 준다`

---

### Task 10: 마무리 확인

- [ ] **Step 1:** back-end 전체 테스트(Global Constraints 명령), front-end `npx jest && npx tsc --noEmit`. Expected: 통과. origin/main에 V14가 생겼으면 번호를 옮기고 다시 돌린다.
- [ ] **Step 2: 실데이터 읽기 검증(운영 DB 읽기 전용, `pods/exec` 권한이 있을 때).** 아래를 보고 결과를 사용자에게 보고한다. 쓰기는 하지 않는다.
  - `decomposableWeight` 조각에 행이 있는 ETF 수, 그중 보유 ETF.
  - 사용자 범위에서 두 렌즈의 평가 · 원가 총합이 같은지.
  - 렌즈 집계 쿼리의 `EXPLAIN (ANALYZE, BUFFERS)` — `etf_constituent` 최신 기준일 조회가 순차 스캔이고 비용이 크면 `(etf_instrument_id, as_of)` 인덱스를 데이터에 요청할 후보로 보고한다.
- [ ] **Step 3:** 사용자에게 결과를 보고하고 커밋 · 푸시 · PR을 요청받으면 진행한다.
