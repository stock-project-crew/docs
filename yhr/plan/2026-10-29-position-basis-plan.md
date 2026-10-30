# 평단 · 실현손익 생성기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 확정된 날마다 계좌 × 종목의 평단 · 등급을 `position_basis`에, 매도 체결마다 실현손익을 `realized_pnl_line`에 쓰고, 실현손익 화면이 추정 사유와 기업행위 경고를 보여 주게 한다.

**Architecture:** DB를 모르는 순수 계산기 `BasisCalculator`가 계좌 × 종목 하나의 입력으로 상태 한 행과 매도 결과들을 낸다. `BasisBuilder`가 `SnapshotJobs`의 다섯 번째 단계로 돌며 날짜 · 계좌를 고르고, 계좌마다 트랜잭션 하나로 읽고 쓴다. 응답과 프론트는 새 컬럼을 그대로 싣고 보여 준다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · MyBatis · Flyway · PostgreSQL 16 · JUnit 5 · AssertJ / React Native(Expo 54) · TypeScript · jest-expo

**Spec:** [평단 · 실현손익 생성기 설계](../specs/portfolio-management/2026-10-29-position-basis-design.md) — 이 계획의 §번호는 그 문서의 절이다. 상위 근거는 [포트폴리오 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md).

## Global Constraints

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어. 커밋 접두어 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **커밋 · 푸시는 사용자가 요청할 때만 한다.** 아래 각 태스크의 커밋 단계는 요청을 받은 뒤 실행한다.
- 주석 · 문서는 히스토리 없이 최신 사실만 쓴다. 검증하지 않은 것은 단정하지 않는다.
- 자격증명 · 계좌번호를 코드 · 로그 · 저장소에 넣지 않는다. 로그에는 `account_id`만 남긴다.
- 운영 DB에 쓰지 않는다. 읽기 전용 확인만 한다.
- 스펙을 고치지 않는다. 구현 중 스펙과 설계가 어긋난다고 보이면 멈추고 보고한다.
- 마이그레이션 번호는 `V12`(미러, `db/external`) · `V13`(`db/migration`). 착수 시 origin/main에 V12 · V13이 생겼으면 다음 빈 번호로 옮긴다.
- DB를 쓰는 테스트는 전용 DB `portfolio_test_basis`에서만 돈다: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_basis?currentSchema=app,data' ./gradlew test --rerun-tasks`. 공유 `portfolio_test`에서 돌리지 않는다. DB 없는 단위 테스트는 승인 없이 돌린다.
- 테스트 메서드 이름은 기존처럼 한국어 문장(`void 같은_날을_두_번_돌려도_결과가_같다()`).
- 내부 계산은 `BigDecimal` 소수 10자리 `HALF_UP`, 저장할 때 컬럼 자리수로 `HALF_UP`.

## Review Focus

1. **주문 시각이 같은 매수 · 매도** — 같은 `executed_at`이면 매수를 먼저 접어 거짓 `CONFLICT`가 나지 않아야 한다(L = 0, 매도를 먼저 접으면 도중 −5). → Task 2 `같은_시각의_매수_매도는_매수를_먼저_접는다`.
2. **`ex_date = covered_from`** — 이력 첫날의 무상증자가 시작 수량 S에 한 번만 적용돼야 한다(S는 행위 전 단위). 시드 되돌리기도 한 번만 되돌린다. → Task 2 `이력_첫날의_분할은_시작_수량에_적용한다`, Task 3 #18.
3. **수량 0 체결** — 취소 · 미체결 주문이 수량 0으로 와도 매도 행을 만들지 않고 판정에 영향이 없어야 한다. → Task 2 `수량_0_체결은_무시한다`.
4. **생성기를 켜기 전에 다 판 종목** — 라인이 한 번도 없고 체결만 있는 종목도 매도 행이 생기고(시드가 필요하면 `UNAVAILABLE`) `position_basis` 행은 없어야 한다. → Task 5 `라인_없이_체결만_있는_종목은_매도_행만_남는다`.
5. **해제 후 재연동한 계좌** — 같은 `account_id`로 돌아오면 마지막 `basis_build` 다음 확정일부터 이어 가고, 해제 기간의 실현손익 행은 그대로여야 한다. → Task 5 `재연동한_계좌는_마지막_기록_다음_날부터_잇는다`.

---

## 파일 구조

**back-end** (`.worktrees/back-end-position-basis`)

| 파일 | 책임 |
|---|---|
| `src/main/resources/db/external/V12__trade_ca_mirror.sql` | `data` 네 표 미러 |
| `src/main/resources/db/migration/V13__position_basis.sql` | `position_basis` · `basis_build` · `realized_pnl_line` 변경 |
| `src/main/java/com/stockproject/portfolio/basis/BasisInput.java` 외 입력 레코드 | 계산기 입력 |
| `.../basis/BasisResult.java` · `BasisState.java` · `SellResult.java` · `SeedReason.java` | 계산기 출력 |
| `.../basis/BasisCalculator.java` | §5 전체 |
| `.../basis/SellWritePolicy.java` | §5.6 쓰기 판단(순수) |
| `.../basis/BasisMapper.java` · `BasisWriteMapper.java` | 읽기 · 쓰기 |
| `.../basis/BasisBuilder.java` | §4 잡 |
| `.../snapshot/SnapshotJobs.java` · `SnapshotRuntimeConfig.java` · `src/main/resources/application.yaml` | 다섯 번째 단계와 `portfolio.basis.enabled` |
| `.../query/RealizedPnlRow.java` · `mapper/RealizedPnlMapper.xml` · `api/dto/RealizedPnlData.java` · `view/RealizedPnlViewService.java` · `view/assembly/NoticeCollector.java` | 응답 |
| `src/main/resources/db/sample/sample_portfolio.sql` · `src/test/resources/golden/realized-pnl.json` | 샘플 · 골든 |
| `src/test/java/com/stockproject/portfolio/basis/*` | 단위 · 통합 테스트, `BasisFixture` · `BasisTestConfig` |

**front-end** (`.worktrees/front-end-position-basis`)

| 파일 | 책임 |
|---|---|
| `src/api/types.ts` | `RealizedPnlTrade` 필드 |
| `src/screens/realizedPnl/GradeBadge.tsx` | 사유별 문구 선택 `tradeHelp` · `rowHelp` |
| `src/format/date.ts` | "M월 D일" 포매터 `formatKoreanMonthDay` |
| `src/screens/realizedPnl/PnlRow.tsx` · `TradeList.tsx` | 체결 배지 누름 |
| `src/fixtures/golden/realized-pnl.json` | 골든 |
| `src/__tests__/realizedPnl.test.tsx` · `src/__tests__/gradeHelp.test.ts` · `src/__tests__/format.test.ts` | 테스트 |

---

### Task 0: 작업 공간과 전용 DB

**Files:** 없음(머신 상태 변경)

- [ ] **Step 1: 만들 것을 사용자에게 알리고 진행한다.** 두 worktree · 전용 DB · `npm ci` · 로컬 Postgres 컨테이너 기동(꺼져 있으면)은 승인을 받았다.

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project
git -C back-end fetch origin
git -C back-end worktree add -b feat/position-basis ../.worktrees/back-end-position-basis origin/main
git -C front-end fetch origin
git -C front-end worktree add -b feat/seed-reason-badge ../.worktrees/front-end-position-basis origin/main
```

- [ ] **Step 2: 전용 DB를 만든다.** 공유 `portfolio_test`가 있는 로컬 컨테이너에 `CREATE DATABASE portfolio_test_basis` 후 `app` · `data` 스키마를 기존 테스트 DB와 같은 방법으로 만든다(`2026-10-14-test-environment-setup.md`).
- [ ] **Step 3: 기준선.** back-end worktree에서 Global Constraints의 테스트 명령. Expected: 모든 테스트 통과(변경 전 origin/main). front-end worktree에서 `npm ci && npm test`. Expected: 통과.

---

### Task 1: 마이그레이션과 스키마 계약

**Files:**
- Create: `src/main/resources/db/external/V12__trade_ca_mirror.sql`, `src/main/resources/db/migration/V13__position_basis.sql`
- Modify: `src/test/java/com/stockproject/portfolio/query/SchemaContractTest.java`, `src/test/java/com/stockproject/portfolio/SchemaSmokeTest.java`, `src/test/java/com/stockproject/portfolio/account/AccountFixture.java`, `src/test/java/com/stockproject/portfolio/snapshot/SnapshotFixture.java`, `src/main/resources/db/sample/sample_portfolio.sql`, `src/test/java/com/stockproject/portfolio/api/RealizedPnlApiTest.java`(`insertTrade`의 INSERT)

**Interfaces:**
- Produces: §3.3의 표 · 컬럼 · CHECK 그대로. `realized_pnl_line` 새 컬럼 `seed_reason` · `coverage_start_at` · `evaluated_as_of` · `position_closed` · `ca_unknown`.

- [ ] **Step 1: 실패하는 계약 테스트** — `SchemaContractTest`에 추가:

```java
@Test void 미러_네_표_컬럼_계약() { /* data.cln_trade 12컬럼 · cln_trade_coverage 6 · corporate_action 4 · ca_coverage 5 이름이 ddl.py와 같다 */ }
@Test void position_basis는_SEEDED에만_시드_평단을_받는다() {
    // grade='VERIFIED', seed_avg_price=1000 삽입 → DataIntegrityViolationException
    // grade='SEEDED', seed_avg_price=NULL 삽입 → DataIntegrityViolationException
}
@Test void position_basis는_영구_추정을_SEEDED에만_허용한다() { /* VERIFIED + seed_permanent=true → 거부 */ }
@Test void position_basis는_수량_0을_거부한다() { /* evaluated_qty=0 → 거부 */ }
@Test void basis_build는_사유_없는_SKIPPED를_거부한다() { /* outcome='SKIPPED', reason=NULL → 거부; outcome='BUILT', reason='CARRIED' → 거부 */ }
@Test void 실현손익_원가는_VERIFIED_SEEDED에서_필수다() {
    // grade='VERIFIED', cost_basis_local=NULL → 거부
    // grade='CONFLICT', 원가·손익 4개 NULL → 통과
}
@Test void 실현손익_추정_사유는_SEEDED에만_있다() {
    // grade='VERIFIED', seed_reason='NOT_TRADED' → 거부
    // seed_reason='LATE_COVERAGE', coverage_start_at=NULL → 거부
    // grade='SEEDED', seed_reason=NULL → 통과(마이그레이션 전 행)
}
@Test void 기존_실현손익_행을_채워_마이그레이션한다() {
    // sample_portfolio 적재 뒤: 모든 행 evaluated_as_of = (sold_at AT TIME ZONE 'Asia/Seoul')::date,
    // position_closed true, ca_unknown false, SEEDED 행의 seed_reason은 NULL이 아니어도 된다(샘플은 채움)
}
```

`사용자_컬럼은_계좌_알림_기기_동기화에만_있다`의 기대 목록은 그대로 둔다(새 표에 `user_id` 없음). `범위_밖_테이블은_없고_동기화_표는_있다`는 `doesNotContain("position_basis")`를 `contains("position_basis", "basis_build", "sync_run", "sync_run_account")`로 뒤집고, 메서드 이름 · 주석에서 "position_basis는 범위 밖" 문장을 지운다(이름 예: `백엔드_소유_표가_있다`).

- [ ] **Step 2: 실행해 실패 확인** — `TEST_DB_URL=… ./gradlew test --tests '*SchemaContractTest' --rerun-tasks`. Expected: 새 테스트 FAIL(relation does not exist).
- [ ] **Step 3: 마이그레이션 작성.** V12는 dataeng `reverse_etl/ddl.py`의 네 `CREATE TABLE IF NOT EXISTS`와 인덱스를 그대로, 머리 주석은 V7 형식. V13은 §3.3 DDL에 더해:
  - `realized_pnl_line` 원가 · 손익 4컬럼 `DROP NOT NULL`, CHECK `(grade NOT IN ('VERIFIED','SEEDED')) OR (넷 다 NOT NULL)`
  - CHECK `seed_reason IS NULL OR grade = 'SEEDED'`, `seed_reason IS DISTINCT FROM 'LATE_COVERAGE' OR coverage_start_at IS NOT NULL`
  - 새 NOT NULL 컬럼은 nullable로 추가 → 기존 행을 설계 §3.3 표대로 `UPDATE`(`evaluated_as_of = (sold_at AT TIME ZONE 'Asia/Seoul')::date`, `position_closed = true`, `ca_unknown = false`) → `SET NOT NULL`. 기본값은 남기지 않는다
  - `COMMENT ON COLUMN realized_pnl_line.grade` §3.3 문구, `position_basis` · `basis_build` 표 주석
  - 인덱스 `basis_build (account_id, as_of DESC)`
- [ ] **Step 4: 픽스처 갱신.** `AccountFixture` · `SnapshotFixture`의 TRUNCATE에 `position_basis, basis_build`를 더한다. `sample_portfolio.sql`의 TRUNCATE에 같은 둘을 더하고 `realized_pnl_line` INSERT에 `evaluated_as_of`(각 행 `sold_at`의 날짜), `position_closed`(true), `ca_unknown`(false), SEEDED 행이면 `seed_reason 'LATE_COVERAGE'` · `coverage_start_at DATE '2026-01-01'`을 채운다. `RealizedPnlApiTest.insertTrade`의 INSERT에 `evaluated_as_of DATE '2026-04-01'`, `position_closed true`, `ca_unknown false`를 더한다.
- [ ] **Step 5: 기존 행 마이그레이션 확인** — 전용 DB를 V11까지만 올린 사본(`portfolio_test_basis_mig`, 승인 범위의 전용 DB)에 `sample_portfolio.sql`의 V11 시점 INSERT를 넣고 V13까지 올려 실패 없이 끝나는지 본다. 끝나면 그 DB를 지운다.
- [ ] **Step 6: 전체 테스트 통과 확인** — Global Constraints 명령. Expected: 전부 PASS.
- [ ] **Step 7: 커밋(요청 시)** — `feat: 평단 상태 · 처리 기록 표를 만들고 실현손익 행에 산출 근거 컬럼을 더한다`

---

### Task 2: 계산기 — 접기 · 시작 수량 · 등급

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/basis/{BasisInput,Trade,Side,CorporateAction,CaType,TradeCoverage,CaCoverage,LineSnapshot,FxTable,PreviousBasis,BasisResult,BasisState,SellResult,SeedReason,BasisCalculator}.java`
- Test: `src/test/java/com/stockproject/portfolio/basis/BasisCalculatorGradeTest.java`

**Interfaces:**
- Produces:

```java
public enum Side { BUY, SELL }
public enum CaType { SPLIT, RIGHTS, MERGER }
public enum SeedReason { LATE_COVERAGE, NOT_TRADED }
public record Trade(String tradeId, Side side, BigDecimal quantity, BigDecimal price,
                    BigDecimal fee, BigDecimal tax, OffsetDateTime executedAt, LocalDate tradeDate) { }
public record CorporateAction(CaType type, BigDecimal ratio, LocalDate exDate) { }
public record TradeCoverage(LocalDate coveredFrom, LocalDate coveredTo, boolean definitive) { }
public record CaCoverage(LocalDate coveredFrom, LocalDate coveredTo, boolean covered) { }
public record LineSnapshot(LocalDate asOf, BigDecimal quantity, BigDecimal costAmountLocal, boolean carriedForward) { }
@FunctionalInterface public interface FxTable { BigDecimal rateOn(LocalDate date); FxTable KRW = d -> BigDecimal.ONE; }
public record PreviousBasis(Grade grade, BigDecimal openingQty) { }
public record BasisInput(LocalDate asOf, boolean marketCovered, BigDecimal balanceQty,
                         Optional<TradeCoverage> coverage, List<Trade> trades,
                         List<CorporateAction> actions, Optional<CaCoverage> caCoverage,
                         List<LineSnapshot> lines, Optional<PreviousBasis> previous, FxTable fx) { }
public record BasisState(LocalDate evaluatedAsOf, BigDecimal evaluatedQty,
                         BigDecimal avgCostLocal, BigDecimal avgCostKrw, LocalDate coverageStartAt,
                         BigDecimal openingQty, BigDecimal seedAvgPrice, Grade grade,
                         boolean seedPermanent, boolean caUnknown) { }
public record SellResult(String tradeId, OffsetDateTime soldAt, BigDecimal quantity,
                         BigDecimal sellAmountLocal, BigDecimal costBasisLocal,
                         BigDecimal sellAmountKrw, BigDecimal costBasisKrw, BigDecimal feeTax,
                         BigDecimal realizedPnlLocal, BigDecimal realizedPnlKrw, Grade grade,
                         SeedReason seedReason, LocalDate coverageStartAt,
                         boolean positionClosed, boolean caUnknown) { }
/** state는 L = 0이면 비어 있다. grade · openingQty는 L = 0이어도 판정값이다(§5.4 표의 등급 · opening_qty).
 *  wholeInstrument는 §5.4의 1~3번 판정, demoted는 강등. */
public record BasisResult(Grade grade, BigDecimal openingQty, Optional<BasisState> state,
                          List<SellResult> sells, boolean wholeInstrument, boolean demoted) { }
public final class BasisCalculator { public BasisResult calculate(BasisInput in) { … } }
```

`marketCovered`는 부르는 쪽이 정한다(지금 KRW 종목만 참). 원가 · 손익이 없는 행은 해당 필드가 `null`이다.

- [ ] **Step 1: 실패하는 테스트** — 설계 §7.1의 #3 · #6 · #7 · #10 · #12 · #16과 Review Focus 1~3. 입력 빌더는 테스트 안의 작은 도우미로 둔다. 핵심 단언:

```java
@Test void 무상증자_단주는_내림해도_VERIFIED다() {          // #3
    var r = calc(buy("t1", 3, 1000), split("1.5", "2026-10-20"), L(4));
    assertThat(r.grade()).isEqualTo(Grade.VERIFIED);
    assertThat(r.openingQty()).isEqualByComparingTo("0");
}
@Test void 잔고보다_많이_사면_CONFLICT다() { /* #6: opening_qty -5 */ }
@Test void 도중에_음수가_되면_CONFLICT다() { /* #7: sell 10 → buy 10, L=0 → state 없음, r.grade() CONFLICT, r.openingQty() -10, wholeInstrument, sells 전부 CONFLICT */ }
@Test void 합병은_수량을_바꾸지_않고_경고만_세운다() { /* #10 VERIFIED, caUnknown true */ }
@Test void 같은_CONFLICT가_이어지면_강등한다() { /* #12 세 갈래: prev(CONFLICT,-5)→UNAVAILABLE demoted; prev(UNAVAILABLE,-5)→UNAVAILABLE; prev(CONFLICT,-5), 이번 -3→CONFLICT */ }
@Test void 잔고에_닿는_시작_수량이_없으면_CONFLICT다() { /* #16: buy 3 → 1.5 → L=5, r.openingQty() -0.66666667 */ }
@Test void 같은_시각의_매수_매도는_매수를_먼저_접는다() { /* buy 5 와 sell 5 같은 executedAt, sell의 tradeId가 앞서도 L=0 → r.grade() VERIFIED, openingQty 0. 매도 먼저면 도중 −5로 CONFLICT가 났을 입력 */ }
@Test void 이력_첫날의_분할은_시작_수량에_적용한다() { /* coveredFrom=ex_date=10-20, 매매 없음, 10-20 라인 20주 · 10000, L=20, ratio 2 → SEEDED, opening 10(두 번 적용하면 S=5) */ }
@Test void 수량_0_체결은_무시한다() { /* buy 10, sell 0, L=10 → VERIFIED, sells 비어 있음 */ }
@Test void 시장을_덮지_않으면_UNAVAILABLE이다() { /* marketCovered=false → UNAVAILABLE, opening = L */ }
@Test void 체결_이력이_없으면_UNAVAILABLE이다() { /* coverage 비어 있음 */ }
```

- [ ] **Step 2: 실패 확인** — `./gradlew test --tests '*BasisCalculatorGradeTest'`(DB 없음). Expected: 컴파일 실패.
- [ ] **Step 3: 구현.** 접기는 §5.2 표, 기업행위는 `ex_date`가 [`covered_from`, D]인 것만 그날 체결보다 먼저. 정렬 키는 `(executedAt, side == BUY ? 0 : 1, tradeId)`. 시작 수량 탐색:

```
lo = 0, hi = L + Σ매도(수량)
f(S)가 L 이상이 되는 가장 작은 S를 이분 탐색
f(S) == L 이고 S에서 접는 도중 수량 ≥ 0  → S 확정
그 밖 → CONFLICT. opening = min(L − f(0), 0에서 접을 때 최저 수량, f(S) > L이면 L − f(S))
        각 값은 그 값이 생긴 시점까지 적용된 SPLIT ratio의 곱으로 나눠 시작 시점 단위로
        (L − f(·)는 구간 전체 ratio 곱, 최저 수량은 그 지점까지의 곱). 결과는 8자리 HALF_UP
```

  강등은 §5.4: `previous`가 (CONFLICT 또는 openingQty < 0인 UNAVAILABLE)이고 이번 CONFLICT의 opening이 8자리 반올림 값으로 같으면 UNAVAILABLE, `demoted = true`.
- [ ] **Step 4: 통과 확인** — 같은 명령. Expected: PASS.
- [ ] **Step 5: 커밋(요청 시)** — `feat: 체결 · 기업행위를 접어 시작 수량과 등급을 판정한다`

---

### Task 3: 계산기 — 구간 · 시드 · 금액 · 기업행위 경고

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/basis/BasisCalculator.java`
- Test: `src/test/java/com/stockproject/portfolio/basis/BasisCalculatorAmountTest.java`

**Interfaces:**
- Consumes: Task 2의 레코드 전부.
- Produces: `SellResult`의 금액 · `positionClosed` · `seedReason` · `coverageStartAt` · `caUnknown`, `BasisState`의 평단 · `seedAvgPrice` · `seedPermanent`.

- [ ] **Step 1: 실패하는 테스트** — 설계 §7.1의 #1 · #2 · #3(평단 666.6667) · #4 · #5 · #8 · #9 · #11 · #13 · #14 · #15 · #17 · #18. 값은 설계 표 그대로 `isEqualByComparingTo`로 단언한다. 예:

```java
@Test void 수수료를_원가에_넣고_비례해_뺀다() {               // #1
    var r = calc(buy("t1", 10, 1000, 15), buy("t2", 10, 1300, 20), sell("t3", 5, 1500, 10, 15), L(15));
    var s = r.sells().get(0);
    assertThat(s.costBasisLocal()).isEqualByComparingTo("5758.75");
    assertThat(s.realizedPnlLocal()).isEqualByComparingTo("1716.25");
    assertThat(s.costBasisKrw()).isEqualByComparingTo("5759");
    assertThat(s.realizedPnlKrw()).isEqualByComparingTo("1716");
    assertThat(r.state().get().avgCostLocal()).isEqualByComparingTo("1151.75");
}
@Test void 이력_안_라인에서_매수를_되돌려_시드한다() { /* #4: coveredFrom 03-02, 03-02 buy 5@1300 fee 10, line(03-02, 15주, cost 18500), 03-03 sell 6@1400, L=9 → SEEDED, opening 10, seedAvgPrice 1200, LATE_COVERAGE, coverageStartAt 03-02, 원가 7404, 손익 996, 평단 1234 */ }
@Test void 무상증자_단주는_내림해도_평단이_맞다() { /* #3: avgCostLocal 666.6667 */ }
@Test void 이력이_첫_체결까지_닿으면_영구_추정이다() { /* #5: NOT_TRADED, seedPermanent */ }
@Test void 청산하면_다음_구간은_VERIFIED다() { /* #8 */ }
@Test void 외화는_매수일_매도일_환율로_환산한다() { /* #9: marketCovered=true, fx 10-16→1300, 10-20→1350 */ }
@Test void 기업행위_확인_범위_밖이면_경고한다() { /* #11 세 경우 + 범위 안 거짓 */ }
@Test void 시드_라인이_없으면_첫_구간만_UNAVAILABLE이다() { /* #13 */ }
@Test void 매도를_되돌려_시드한다() { /* #14: seedAvgPrice 1100, 원가 4400, 손익 1600, 평단 1180 */ }
@Test void 수량이_다르거나_이월인_라인은_건너뛴다() { /* #15 두 갈래 모두 seedAvgPrice 1100 */ }
@Test void 분할을_되돌려_시드한다() { /* #17: seedAvgPrice 1000, avgCostLocal 500 */ }
@Test void 이력_첫날의_분할은_한_번만_되돌린다() { /* #18: opening 10, seedAvgPrice 1000 */ }
```

- [ ] **Step 2: 실패 확인** — `./gradlew test --tests '*BasisCalculatorAmountTest'`. Expected: FAIL.
- [ ] **Step 3: 구현.** 구간 · 시드 · 금액은 §5.5, `ca_unknown`은 §5.7. 시드는 §5.5의 출발 라인(`lines` 중 이월이 아닌 것; `LineSnapshot`에 `boolean carriedForward`를 더한다)에서 §5.5 되돌리기 표대로 거꾸로 접고 ÷ S. 되돌릴 때 수량은 앞으로 접은 값을 다시 쓴다. 원화 총액은 매수마다 `fx.rateOn(tradeDate)`, 시드는 `fx.rateOn(coveredFrom)`.
- [ ] **Step 4: 통과 확인** — Task 2 · 3 테스트 둘 다. Expected: PASS.
- [ ] **Step 5: 커밋(요청 시)** — `feat: 포지션 구간마다 매도 원가 · 실현손익과 기업행위 경고를 계산한다`

---

### Task 4: 실현손익 행 쓰기 판단

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/basis/SellWritePolicy.java`, `ExistingSell.java`
- Test: `src/test/java/com/stockproject/portfolio/basis/SellWritePolicyTest.java`

**Interfaces:**
- Consumes: `BasisResult`, `SellResult`.
- Produces:

```java
public record ExistingSell(String tradeId, boolean positionClosed) { }
public final class SellWritePolicy {
    /** 이번에 upsert할 매도들. 반환하지 않은 매도는 건드리지 않는다. */
    public static List<SellResult> toWrite(BasisResult result, Map<String, ExistingSell> existing) { … }
}
```

- [ ] **Step 1: 실패하는 테스트** — 설계 §5.6 표 한 줄마다 하나:
  - `닫힌_기존_행은_쓰지_않는다`
  - `닫힌_구간의_새_매도는_넣는다`
  - `열린_구간_매도는_덮어쓴다`
  - `열려_있던_행이_이번에_닫히면_덮어쓰고_닫는다`(결과의 `positionClosed` true)
  - `종목_전체_CONFLICT면_닫히지_않은_행을_덮어쓴다`
  - `강등이면_새_매도만_넣는다`
- [ ] **Step 2: 실패 확인 → Step 3: 구현 → Step 4: 통과 확인** — `./gradlew test --tests '*SellWritePolicyTest'`.
- [ ] **Step 5: 커밋(요청 시)** — `feat: 다시 계산할 때 덮어쓸 실현손익 행과 고정할 행을 가린다`

---

### Task 5: 잡 — 날짜 · 계좌 고르기와 쓰기

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/basis/{BasisMapper,BasisWriteMapper,BasisBuilder,BasisTarget}.java`, `src/main/resources/mapper/BasisMapper.xml`(쿼리가 길면)
- Test: `src/test/java/com/stockproject/portfolio/basis/{BasisFixture,BasisTestConfig,BasisBuilderTest}.java`

**Interfaces:**
- Consumes: `BasisCalculator.calculate`, `SellWritePolicy.toWrite`, `PositionWriteMapper.lockDateShared(LocalDate)` · `lockAccount(UUID)`.
- Produces:

```java
public record BasisTarget(UUID accountId, String accountRef, String linkState, boolean carriedForward) { }
@Component public class BasisBuilder {
    /** 이번 회차에 BUILT 또는 SKIPPED로 기록한 (계좌, 날짜) 수. */
    public int buildOnce() { … }
}
```

`BasisMapper`: `List<LocalDate> snapshotDatesAfter(LocalDate after)`(null이면 최신 하나), `Optional<LocalDate> lastBuilt(UUID accountId)`, `List<BasisTarget> targets(LocalDate asOf)`, `boolean built(UUID accountId, LocalDate asOf)`, 입력 읽기(`trades` · `tradeCoverage` · `actions` · `caCoverage` · `lines` · `fxRates` · `currentBasis` · `existingSells`). `BasisWriteMapper`: `deleteBasis(UUID accountId)`, `insertBasis(...)`, `upsertSell(...)`, `insertBuild(UUID accountId, LocalDate asOf, String outcome, String reason, OffsetDateTime builtAt)`.

- [ ] **Step 1: 픽스처** — `BasisFixture`는 `SnapshotFixture`를 감싸 확정 라인 · `snapshot_run` · `data.cln_trade` · `cln_trade_coverage` · `corporate_action` · `ca_coverage` · `fx_rate`를 직접 쓴다. `reset()`은 `SnapshotFixture.reset()` 뒤 미러 네 표와 `position_basis` · `basis_build`를 비운다. 계좌 참조는 `ar_a` 같은 가짜 값.
- [ ] **Step 2: 실패하는 통합 테스트** — `@SpringBootTest @ActiveProfiles("test") @Import(BasisTestConfig.class)`:
  - `확정되지_않은_날은_처리하지_않는다`
  - `첫_실행은_최신_확정일_하나만_처리한다`
  - `뒤로_가지_않는다`(10-14 BUILT 뒤 10-13 `snapshot_run`을 넣어도 처리 안 함)
  - `이월_계좌는_CARRIED로_건너뛰고_상태를_둔다`
  - `해제_계좌는_DISCONNECTED로_건너뛰고_과거_행을_둔다`
  - `체결_이력이_늦으면_다음_확정일까지_기록하지_않는다`(D+1 `snapshot_run` 뒤 `TRADES_BEHIND`)
  - `체결_이력이_없는_계좌는_UNAVAILABLE로_BUILT한다`
  - `같은_날을_두_번_돌려도_결과가_같다`
  - `열린_구간_행은_덮어쓰고_닫힌_행은_둔다`(이틀에 걸친 시나리오, 둘째 날 늦게 온 매수)
  - `CONFLICT가_이틀_이어지면_강등하고_첫날_행은_둔다`
  - `라인_없이_체결만_있는_종목은_매도_행만_남는다`(Review Focus 4)
  - `재연동한_계좌는_마지막_기록_다음_날부터_잇는다`(Review Focus 5)
  - `한_계좌가_실패해도_다른_계좌는_처리된다`(`FinalizerTest`의 `test_fail_b`와 같은 방식으로 `position_basis`에 특정 `account_id` INSERT를 막는 트리거를 테스트 안에서 만들고 지운다. `BasisFixture.reset()`이 `DROP TRIGGER IF EXISTS`)
  - `수량이_0이_된_종목은_평단_행이_지워진다`(첫날 L=10 → 둘째 날 전량 매도 L=0 → `position_basis`에 그 종목 없음, 매도 행은 남음)
- [ ] **Step 3: 실패 확인** — `TEST_DB_URL=… ./gradlew test --tests '*BasisBuilderTest' --rerun-tasks`. Expected: FAIL.
- [ ] **Step 4: 구현.** §4.1 · §4.2 · §4.3. 계좌마다 `TransactionTemplate` 하나: `lockDateShared(D)` → `lockAccount` → `built` 확인 → 건너뛰기 판정 → 종목마다 계산 → `deleteBasis` · `insertBasis` · `upsertSell` · `insertBuild`. 실패는 `log.warn("평단 계산 실패 계좌={} 날짜={} 사유={}", accountId, D, Failures.describe(e))` 후 그 계좌의 남은 날짜를 이번 회차에서 멈춘다. `marketCovered = instrument.currency == KRW`. 환율은 기존 `BalanceMapper`처럼 `currency_pair = 'USD/KRW' AND rate_type = 'BASE'`.
- [ ] **Step 5: 통과 확인** — 같은 명령. Expected: PASS.
- [ ] **Step 6: 커밋(요청 시)** — `feat: 확정된 날마다 계좌별로 평단 상태와 실현손익을 다시 계산한다`

---

### Task 6: 스냅샷 회차에 연결과 동시성

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/snapshot/SnapshotJobs.java`, `SnapshotRuntimeConfig.java`, `src/main/resources/application.yaml`, `README.md`(런타임 스위치 목록)
- Test: `src/test/java/com/stockproject/portfolio/snapshot/SnapshotJobsTest.java`, `src/test/java/com/stockproject/portfolio/snapshot/SnapshotRuntimeConfigTest.java`, `src/test/java/com/stockproject/portfolio/basis/BasisConcurrencyTest.java`

**Interfaces:**
- Consumes: `BasisBuilder.buildOnce()`.
- Produces: `SnapshotJobs(CredentialFiller, RunProcessor, Finalizer, SyncCloser, BasisBuilder, boolean basisEnabled)`. `application.yaml`에 `portfolio.basis.enabled: ${BASIS_ENABLED:false}`. `SnapshotRuntimeConfig`가 `@Value("${portfolio.basis.enabled:false}")`로 받아 넘긴다.

- [ ] **Step 1: 실패하는 테스트**
  - `SnapshotJobsTest`: `동기화_닫기가_실패해도_평단_계산은_돈다`, 순서 검증에 `basis.buildOnce()`를 마지막으로 추가, `평단_스위치가_꺼지면_다섯째_단계만_건너뛴다`(1~4단계는 호출, `buildOnce` 호출 없음).
  - `SnapshotRuntimeConfigTest`: runner에 `.withBean(BasisBuilder.class, () -> mock(BasisBuilder.class))`를 더하고, `평단_스위치는_기본_꺼짐이다`.
  - `BasisConcurrencyTest`: `두_스레드가_같은_날을_처리해도_기록은_한_건이다`(`SnapshotConcurrencyTest`와 같은 `CountDownLatch` 방식). `basis_build` 1행, `position_basis` 한 벌, `realized_pnl_line` 중복 없음.
- [ ] **Step 2: 실패 확인 → Step 3: 구현**(`if (basisEnabled) stage("평단 · 손익 계산", basis::buildOnce)`, 클래스 주석의 순서 문장에 "켜져 있으면 평단 · 손익을 다시 계산한다"를 잇는다. README의 런타임 스위치 목록에 `BASIS_ENABLED`를 더한다) **→ Step 4: 통과 확인.**
- [ ] **Step 5: 커밋(요청 시)** — `feat: 보유 스냅샷 회차의 다섯 번째 단계로 평단 · 손익 계산을 붙인다`

---

### Task 7: 실현손익 응답과 `CA_UNKNOWN`

**Files:**
- Modify: `src/main/resources/mapper/RealizedPnlMapper.xml`, `src/main/java/com/stockproject/portfolio/query/RealizedPnlRow.java`, `src/main/java/com/stockproject/portfolio/api/dto/RealizedPnlData.java`, `src/main/java/com/stockproject/portfolio/view/RealizedPnlViewService.java`, `src/main/java/com/stockproject/portfolio/view/assembly/NoticeCollector.java`, `src/main/resources/db/sample/sample_portfolio.sql`, `src/test/resources/golden/realized-pnl.json`
- Test: `src/test/java/com/stockproject/portfolio/api/RealizedPnlApiTest.java`, `src/test/java/com/stockproject/portfolio/view/assembly/NoticeCollectorTest.java`, `src/test/java/com/stockproject/portfolio/UserScopeIsolationTest.java`

**Interfaces:**
- Produces: `TradeNode(..., String grade, @JsonInclude(NON_NULL) String seedReason, @JsonInclude(NON_NULL) LocalDate coverageStartAt)` → JSON `seed_reason` · `coverage_start_at`. `RealizedPnlRow`에 `SeedReason seedReason, LocalDate coverageStartAt, boolean caUnknown`. `AssemblyContext.Builder.caUnknownInstruments(List<String>)`(필드와 setter를 새로 더한다).

- [ ] **Step 1: 샘플에 사례를 넣는다.** `sample_portfolio.sql`에 yhr의 올해 매도 중 하나를 `ca_unknown = true`로, `CONFLICT` 행 하나(원가 · 손익 NULL)를 더한다. 그 결과 `UserScopeIsolationTest`의 `count("realized_pnl_line")` 기대값은 4 → 5, `RealizedPnlApiTest.믿을_수_없는_체결은_합계에서_빠지고_그_사실을_알린다`의 `EXCLUDED_ACCOUNTS` count는 샘플 `CONFLICT` 행의 계좌가 `T-9001`과 같으면 1, 다르면 2다. 샘플 행의 계좌를 정한 뒤 두 기대값을 고친다.
- [ ] **Step 2: 실패하는 테스트**
  - `RealizedPnlApiTest`: `추정_체결에_사유와_시작일이_실린다`(SEEDED 체결 노드 `seed_reason == "LATE_COVERAGE"`, `coverage_start_at == "2026-01-01"`, VERIFIED 노드에는 두 키 없음), `기업행위_미확인_종목이_있으면_CA_UNKNOWN을_붙인다`(`params.instrument_ids`에 그 종목 id), `원가_없는_행은_합계와_목록에서_빠진다`(샘플 `CONFLICT` 행만으로: 합계 불변, `EXCLUDED_ACCOUNTS` count 1).
  - `NoticeCollectorTest`: `기업행위_미확인_종목_수를_문구에_쓴다` — message `"1개 종목은 기업행위 이력을 확인하지 못해 손익이 다를 수 있습니다"`, `severity` `warn`. 빈 목록이면 null.
- [ ] **Step 3: 실패 확인 → Step 4: 구현.** `NoticeCollector`의 `case CA_UNKNOWN`을 `caUnknown(context)`로 분리하고 `PRICE_LAG_MARKET`만 null로 남긴다. 주석의 "아래 둘은"을 하나로 고친다. `params` 키는 `instrument_ids`. `RealizedPnlViewService`는 기간 안 전체 행(합계 포함 여부와 무관) 중 `caUnknown` 행의 `instrumentId`를 중복 없이 넘긴다.
- [ ] **Step 5: 골든 갱신.** `SixViewGoldenTest`에는 자동 갱신이 없다. 실패 메시지의 실제 응답을 보고 `golden/realized-pnl.json`을 손으로 고친 뒤, 차이가 새 키 · 새 행 · notice뿐인지 `git diff`로 확인한다.
- [ ] **Step 6: 전체 테스트 통과 확인** — Global Constraints 명령.
- [ ] **Step 7: 커밋(요청 시)** — `feat: 실현손익 체결에 추정 사유와 이력 시작일을 싣고 기업행위 미확인을 알린다`

---

### Task 8: 프론트 — 사유별 배지 설명

**Files:**
- Modify: `src/api/types.ts`, `src/format/date.ts`, `src/screens/realizedPnl/GradeBadge.tsx`, `src/screens/realizedPnl/PnlRow.tsx`, `src/screens/realizedPnl/TradeList.tsx`, `src/fixtures/golden/realized-pnl.json`
- Test: `src/__tests__/gradeHelp.test.ts`(새), `src/__tests__/realizedPnl.test.tsx`, `src/__tests__/format.test.ts`

**Interfaces:**
- Consumes: Task 7의 JSON 키 `seed_reason` · `coverage_start_at`.
- Produces:

```ts
export type SeedReason = 'LATE_COVERAGE' | 'NOT_TRADED';
// RealizedPnlTrade에 추가
seed_reason?: SeedReason;
coverage_start_at?: string;
// GradeBadge.tsx
export function tradeHelp(trade: RealizedPnlTrade): string | undefined;
export function rowHelp(row: RealizedPnlRow): string | undefined;
// format/date.ts — '2026-01-01' → '1월 1일', 잘못된 값 → EM_DASH
export function formatKoreanMonthDay(iso: string | null | undefined): string;
```

- [ ] **Step 1: 실패하는 테스트** — `gradeHelp.test.ts`, 문구는 설계 §6.2 그대로:

```ts
it('매매 없이 입고', () => expect(tradeHelp(t({ grade: 'SEEDED', seed_reason: 'NOT_TRADED' })))
  .toBe('매매 없이 입고된 종목이라, 잔고 평단으로 취득원가를 추정했어요'));
it('이력 늦게 확보', () => expect(tradeHelp(t({ grade: 'SEEDED', seed_reason: 'LATE_COVERAGE', coverage_start_at: '2026-01-01' })))
  .toBe('거래내역이 1월 1일부터 확보돼, 그 전에 산 수량은 잔고 평단으로 추정했어요. 더 이른 거래내역이 들어오면 바뀔 수 있어요'));
it('종목 노드 사유가 같으면 그 문구', …);
it('종목 노드 사유가 갈리면 펼쳐 보라는 문구', () => … .toBe('계좌마다 추정한 이유가 달라요. 펼쳐서 체결별로 확인하세요'));
it('사유 필드가 없으면 지금 고정 문구', () => … .toBe(GRADE_HELP.SEEDED));
```

  `realizedPnl.test.tsx`: `체결 배지를 누르면 그 체결의 설명이 열린다`. `format.test.ts`: `formatKoreanMonthDay('2026-01-01') === '1월 1일'`, `('2026-10-29') === '10월 29일'`, `(null) === EM_DASH`.
- [ ] **Step 2: 실패 확인** — `npm test -- gradeHelp realizedPnl`. Expected: FAIL.
- [ ] **Step 3: 구현.** 날짜는 `formatKoreanMonthDay`. 기존 `formatMonthDay`("01-01" 형식, 계좌 연동 화면이 씀)는 바꾸지 않는다. `MIXED` · `UNAVAILABLE` · `CONFLICT`는 기존 `GRADE_HELP`. 종목 노드 `SEEDED`는 체결들의 (사유, 시작일)이 하나면 `tradeHelp`, 여럿이면 갈림 문구. `TradeList`는 체결별 열림 상태를 두고 `TooltipBody`로 보여 준다. `GradeBadge.tsx` 머리 주석의 "테이블이 없어" 문장을 사유 필드 기준으로 고친다.
- [ ] **Step 4: 골든 복사** — back-end Task 7의 `golden/realized-pnl.json`을 `src/fixtures/golden/realized-pnl.json`에 그대로 복사.
- [ ] **Step 5: 통과 확인** — `npm test`. Expected: 전부 PASS. `npx tsc --noEmit`도 오류 없음.
- [ ] **Step 6: 커밋(요청 시)** — `feat: 추정 배지 설명을 체결별 사유와 이력 시작일로 보여 준다`

---

### Task 9: 마무리 확인

- [ ] **Step 1: rebase** — 두 worktree에서 `git fetch origin && git rebase origin/main`. 충돌이 나면 Global Constraints의 마이그레이션 번호 규칙과 TRUNCATE 목록부터 본다.
- [ ] **Step 2: 전체 테스트** — back-end Global Constraints 명령, front-end `npm test`. Expected: 전부 PASS. 결과를 그대로 보고한다.
- [ ] **Step 3: CI 확인** — `build-and-push.yml`은 `postgres:16-alpine` 서비스로 `./gradlew test`를 돈다. 새 테스트가 별도 설정 없이 그 경로에 드는지(테스트 프로필, 전용 DB 이름에 기대지 않는지) 확인한다.
- [ ] **Step 4: 운영 읽기 확인(읽기 전용, 승인됨)** — 운영 앱 DB 계정이 `data.cln_trade` · `data.cln_trade_coverage` · `data.corporate_action` · `data.ca_coverage` · `data.fx_rate`를 SELECT할 수 있는지 `has_table_privilege`로, `realized_pnl_line` 행 수를 본다. 권한이 없으면 필요한 조치를 보고한다(직접 바꾸지 않는다). 머지돼도 `BASIS_ENABLED`가 없으면 다섯 번째 단계는 돌지 않는다. 켜는 매니페스트 변경 · 배포는 따로 승인받는다.
- [ ] **Step 5: 보고** — 바꾼 파일, 테스트 결과, 설계 §10 스펙 반영 후보 목록, 남은 데이터 쪽 의존(설계 §9)을 정리한다. 푸시 · PR은 요청이 있을 때만.
