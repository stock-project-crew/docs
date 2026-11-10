# 배당 · 수수료 · 세금 원장 구현 계획

> **에이전트 작업자용:** 필수 하위 스킬 — superpowers:subagent-driven-development(권장) 또는 superpowers:executing-plans로 태스크 단위로 진행한다. 단계는 체크박스(`- [ ]`)로 추적한다.

**목표:** 자산 변화의 배당 · 수수료 · 세금을 데이터팀 원장(`data.cln_cashflow` · `data.cln_cashflow_coverage`)에서 읽어 "번 돈"에 넣고, 실제로 빠진 유형만 경고한다.

**구조:** 새 매퍼가 계좌별 구간(`span`)을 구해 그 안의 원장을 발생일 환율로 원화 환산 · 합산하고, 확보 판정 재료를 낸다. 새 포트 구현이 그것을 `EarningsCashflowTotals`로 모으고, 자산 변화 서비스는 계좌 필터를 넘겨 받은 값을 쓴다. 경고 문구는 `NoticeCollector`가 빠진 유형 이름으로 만든다.

**기술:** Spring Boot 3.4.5 · Java 21 · MyBatis(XML 매퍼) · Flyway · PostgreSQL 16 · JUnit 5 · AssertJ · Mockito. 앱은 React Native · jest-expo.

**설계:** [배당 · 수수료 · 세금 원장 설계](../specs/portfolio-management/2026-11-10-earnings-cashflow-design.md). 계획과 설계가 다르면 설계가 맞다.

## 공통 제약

- 작업 트리: 백엔드 `.worktrees/back-end-earnings-cashflow`(브랜치 `feat/earnings-cashflow`). 앱은 Task 5에서 `.worktrees/front-end-earnings-cashflow`를 만든다 — 만들기 전에 승인을 받는다.
- 코드 경로 접두 `src/main/java/com/stockproject/portfolio/`를 아래에서 `…/`로 줄인다.
- 마이그레이션 번호는 `V16`(시작 시 `origin/main`의 다음 빈 번호). 머지 직전에 `origin/main`을 다시 보고 겹치면 다시 매긴다.
- DB를 쓰는 테스트는 돌리기 전에 승인을 받는다. 브랜치 전용 DB에서 `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_earnings_cashflow?currentSchema=app,data' ./gradlew test --rerun-tasks`로 돌린다. DB 생성도 승인을 받는다. DB를 쓰지 않는 단위 테스트는 묻지 않고 돌린다.
- 원장은 `type IN ('DIVIDEND', 'FEE', 'TAX')`만 읽는다.
- 계좌별 구간: `[기초, 기말]` 안의 그 계좌 `position_line` `min(as_of)` · `max(as_of)`에 대해 `(min, max]`. `min < max`인 계좌만 판정 대상.
- 원장 날짜: `(occurred_at AT TIME ZONE #{zone})::date`, `zone`은 `portfolio.zone`(`Asia/Seoul`).
- 환율: `fx_rate`의 `currency_pair = 'USD/KRW'` · `rate_type = 'BASE'`. 발생일 이하 가장 최근 → 없으면 가장 이른 행 → 그것도 없으면 환산하지 않고 그 (계좌, 유형)을 미확보.
- 반올림: 원장 행마다 `round(amount × rate, 0)`(KRW는 `round(amount, 0)`) 후 합산.
- 부호: `dividend = Σ DIVIDEND`, `feeTax = −Σ (FEE + TAX)`.
- 문구 유형 이름: `DIVIDEND` → `배당`, `FEE` → `수수료`, `TAX` → `세금`, 이 순서로 `·`로 잇는다.
- 주석 · 커밋 메시지는 한국어. 주석에 문서 절(§ · SG- 등)을 쓰지 않는다. 커밋 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. 커밋은 사용자가 요청할 때만 한다 — 아래 "커밋" 단계는 요청을 받은 경우의 단위다.

## 검토 초점

태스크의 기본 테스트가 직접 겨누지 않지만 사용자를 물 가능성이 큰 입력이다. 각 줄의 테스트를 담당 태스크에 넣었다.

1. **한국 시간 자정 직전 · 직후의 원장 행** — `2026-07-24T23:59:59+09`는 07-24(기초 당일, 제외), `2026-07-24T15:00:00Z`(= 07-25 00:00 KST)는 07-25(포함). → Task 2 `한국_시간_날짜로_구간을_자른다`.
2. **같은 계좌의 같은 유형에 환산된 행과 환율 없는 USD 행이 섞임** — 환산된 행은 합계에 들고, 그 (계좌, 유형)은 미확보. → Task 3 `환산하지_못한_행이_있으면_그_유형은_미확보다`.
3. **남의 계좌 · 앱에 없는 `account_ref`의 원장 · 커버리지 행** — 합계와 판정에 들지 않는다. → Task 2 `남의_계좌와_모르는_계좌는_읽지_않는다`.
4. **계좌 필터에 기간 중 잔고가 하루뿐인 계좌만 있음** — 판정 대상이 없어 배당 · 수수료 쪽 경고가 없다. → Task 3 `판정_대상이_없으면_세_유형_모두_확보다`, Task 4 API 테스트.
5. **음수 수수료 · 양수 환급이 같은 기간에 있음** — `feeTax`는 순비용. → Task 2 `수수료와_세금은_부호를_뒤집어_순비용이_된다`.

---

### Task 1: 원장 미러 V16과 샘플 초기화

**파일:**
- 만듦: `src/main/resources/db/external/V16__cashflow_mirror.sql`
- 고침: `src/main/resources/db/sample/sample_portfolio.sql:9-10` (TRUNCATE 목록)
- 테스트: `src/test/java/com/stockproject/portfolio/query/CashflowMirrorTest.java`

**인터페이스:**
- 만듦: `data.cln_cashflow`, `data.cln_cashflow_coverage` — dataeng `reverse_etl/ddl.py` 201–229행과 컬럼 · 타입 · PK · CHECK가 같다.

- [ ] **Step 1: 실패하는 테스트**

`@SpringBootTest @ActiveProfiles("test") @Sql("classpath:db/sample/sample_portfolio.sql")`, `JdbcClient`로:
- `원장은_입출금_유형을_받지_않는다`: `INSERT INTO cln_cashflow(... type='DEPOSIT' ...)`가 `DataIntegrityViolationException`.
- `커버리지는_다섯_유형과_두_상태만_받는다`: `type='DEPOSIT', state='COVERED'`는 들어가고, `state='UNKNOWN'`은 예외.
- `샘플을_다시_깔면_원장이_비어_있다`: 원장 · 커버리지에 행을 넣은 뒤 샘플 SQL을 다시 실행(`ScriptUtils` 또는 `@Sql`을 두 번째 메서드에)하면 두 표가 0행.

- [ ] **Step 2: DB 테스트 승인 받기 → 브랜치 DB 만들기(승인) → 실행해 실패 확인**

`TEST_DB_URL=… ./gradlew test --rerun-tasks --tests '*CashflowMirrorTest'` → 표가 없어 실패.

- [ ] **Step 3: V16 작성, 샘플 TRUNCATE에 `cln_cashflow, cln_cashflow_coverage` 추가**

머리 주석은 `V12__trade_ca_mirror.sql`과 같은 두 줄 형식(로컬 · 테스트 전용 미러, `ddl.py` 정의를 따름). 샘플에 원장 행은 넣지 않는다 — 테스트가 필요한 행을 직접 넣는다.

- [ ] **Step 4: 실행해 통과 확인** — 같은 명령, PASS.

- [ ] **Step 5: 커밋** — `feat: 현금흐름 원장 두 표의 로컬·테스트 미러를 만든다`

---

### Task 2: 원장 매퍼

**파일:**
- 만듦: `…/query/EarningsCashflowMapper.java`, `src/main/resources/mapper/EarningsCashflowMapper.xml`
- 만듦: `…/query/EarningsLedgerRow.java`, `…/query/AccountCashflowTypeRow.java`
- 테스트: `src/test/java/com/stockproject/portfolio/query/EarningsCashflowMapperTest.java`

**인터페이스:**
- 소비: Task 1의 두 표.
- 만듦:
  ```java
  record EarningsLedgerRow(UUID accountId, String type, BigDecimal amountKrw, int unconverted) {}
  record AccountCashflowTypeRow(UUID accountId, String type) {}

  @Mapper interface EarningsCashflowMapper {
      List<UUID> judgedAccounts(@Param("scope") UserScope scope, @Param("opening") LocalDate opening,
                                @Param("closing") LocalDate closing, @Param("accountIds") Set<UUID> accountIds);
      List<EarningsLedgerRow> ledger(@Param("scope") UserScope scope, @Param("opening") LocalDate opening,
                                     @Param("closing") LocalDate closing, @Param("accountIds") Set<UUID> accountIds,
                                     @Param("zone") String zone);
      List<AccountCashflowTypeRow> covered(@Param("scope") UserScope scope, @Param("opening") LocalDate opening,
                                   @Param("closing") LocalDate closing, @Param("accountIds") Set<UUID> accountIds);
  }
  ```
  `ledger`는 (계좌, 유형)마다 한 행: `amountKrw`는 환산된 행의 반올림 합(부호 그대로), `unconverted`는 환율이 없어 뺀 행 수. `covered`는 판정 대상 계좌 중 `state = 'COVERED'`이고 유형이 세 유형인 행.

- [ ] **Step 1: 실패하는 테스트**

샘플 위에서 `yhr`(`40000000-…-0001`)의 계좌 `20000000-…-0001`(`ar_7f3a91c4`)을 주로 쓴다. 기초 `2026-07-24`, 기말 `2026-07-27`. 필요한 잔고 날짜는 테스트 안에서 `position_line` 행을 복사 · 삭제해 만든다(`AssetChangeApiTest`의 `copyLines` · `deleteLines`와 같은 방식).
- `기간_내내_있는_계좌는_기초_다음_날부터_기말까지_센다`: 07-24 · 07-25 · 07-27 배당 각 100 → 합 200(07-24 제외).
- `한국_시간_날짜로_구간을_자른다`: `2026-07-24T23:59:59+09` 100은 빠지고 `2026-07-24T15:00:00Z` 100은 든다.
- `기간_중_연동한_계좌는_첫_잔고_다음_날부터_센다`: 07-24 잔고를 지워 첫 잔고가 07-25인 계좌, 07-25 배당 100 · 07-26 배당 100 → 100.
- `기간_중_해제한_계좌는_마지막_잔고까지만_센다`: 07-27 잔고를 지우고 07-25 잔고를 만들어 마지막이 07-25, 07-26 배당 → 0.
- `잔고가_하루뿐인_계좌는_판정하지도_세지도_않는다`: `judgedAccounts`에 없고 `ledger`도 빈다. 07-27에만 잔고가 있는 계좌 `20000000-…-0007`(사용자 `40000000-…-0003`)을 쓴다.
- `기초와_기말이_같으면_대상이_없다`: `opening = closing = 2026-07-27` → 세 질의 모두 빈 목록.
- `수수료와_세금은_부호를_뒤집어_순비용이_된다`: 이 매퍼는 부호를 그대로 낸다 — `FEE` −300과 +100 → `amountKrw = -200`, `TAX` −50 → −50.
- `외화는_발생일_환율로_원_단위_반올림한다`: `fx_rate`에 07-24 1,380.5 · 07-26 1,390.25를 넣고 07-25 USD 10.05 → `round(10.05 × 1380.5) = 13874`, 07-26 USD 1 → 1390.
- `발생일_이전_환율이_없으면_가장_이른_환율을_쓴다`: 환율이 07-26 1,390뿐이고 07-25 USD 1 → 1390.
- `환율이_하나도_없으면_환산하지_않고_센다`: `fx_rate`를 비우고 USD 1 → 그 행은 `amountKrw = 0`, `unconverted = 1`.
- `입출금_유형이_아닌_세_유형만_판정한다`: 커버리지 `DEPOSIT = COVERED`는 `covered`에 없다.
- `남의_계좌와_모르는_계좌는_읽지_않는다`: `jdh` 계좌의 `account_ref`와 `ar_unknown` 원장 · 커버리지 행은 `yhr` 질의 결과에 없다.
- `계좌_필터가_비면_그_사용자의_계좌_전부다`, `계좌_필터가_있으면_그_계좌만이다`.

- [ ] **Step 2: DB 테스트 실행해 실패 확인** — `--tests '*EarningsCashflowMapperTest'`.

- [ ] **Step 3: 매퍼 작성**

세 질의가 공유하는 조각 `<sql id="span">`(`ManualCashflowMapper.xml` · `SnapshotCalendarMapper.accountBoundary`와 같은 계좌 필터 규칙):

```sql
SELECT pl.account_id, a.account_ref, min(pl.as_of) AS first_as_of, max(pl.as_of) AS last_as_of
  FROM position_line pl JOIN account a USING (account_id)
 WHERE a.user_id = #{scope.userId} AND pl.as_of BETWEEN #{opening} AND #{closing}
   [AND pl.account_id IN (#{accountIds})]   -- 비면 생략
 GROUP BY pl.account_id, a.account_ref
HAVING min(pl.as_of) < max(pl.as_of)
```

`ledger`는 `span`과 `cln_cashflow`를 `account_ref`로 잇고, 발생일 `d`가 `first_as_of < d <= last_as_of`인 행에 `LEFT JOIN LATERAL`로 `as_of <= d` 최근 환율, `coalesce`로 가장 이른 환율을 붙인다. KRW는 환율 1. `amount_krw = sum(round(amount * rate, 0)) FILTER (WHERE rate IS NOT NULL)`, `unconverted = count(*) FILTER (WHERE rate IS NULL)`.

- [ ] **Step 4: 실행해 통과 확인.**

- [ ] **Step 5: 커밋** — `feat: 계좌별 구간 안의 현금흐름 원장을 원화로 합산하는 매퍼를 둔다`

---

### Task 3: 원장 포트 구현과 포트 시그니처

**파일:**
- 만듦: `…/query/LedgerEarningsCashflowPort.java`
- 지움: `…/query/EmptyEarningsCashflowPort.java`
- 고침: `…/query/EarningsCashflowPort.java`, `…/query/EarningsCashflowTotals.java`
- 고침: `…/view/AssetChangeViewService.java:102-104` (호출부만 — 판정 쪽은 Task 4)
- 테스트: `src/test/java/com/stockproject/portfolio/query/LedgerEarningsCashflowPortTest.java` (매퍼를 Mockito로 대신하는 단위 테스트)

**인터페이스:**
- 소비: Task 2의 `EarningsCashflowMapper`.
- 만듦:
  ```java
  interface EarningsCashflowPort {
      EarningsCashflowTotals totalsBetween(UserScope scope, LocalDate opening, LocalDate closing,
                                           Set<UUID> accountFilter);
  }
  record EarningsCashflowTotals(BigDecimal dividend, BigDecimal feeTax,
                                Set<UUID> judgedAccountIds, Set<UUID> coveredAccountIds,
                                Set<EarningsCashflowType> coveredTypes) {
      Set<UUID> uncoveredAccountIds();   // judged − covered
  }
  ```
  `NONE` 상수는 지운다(쓰는 곳이 없어진다). `LedgerEarningsCashflowPort`는 `@Component`, 생성자에서 `@Value("${portfolio.zone}") String zone`을 받는다.

- [ ] **Step 1: 실패하는 테스트**

- `배당과_수수료_세금을_유형별로_모은다`: ledger `DIVIDEND` 1000 · `FEE` −300 · `TAX` −50 → `dividend = 1000`, `feeTax = 350`.
- `세_유형을_모두_확보한_계좌만_확보_계좌다`: 판정 A · B, covered A의 세 유형 · B의 `DIVIDEND` → `coveredAccountIds = {A}`, `coveredTypes = {DIVIDEND}`, `uncoveredAccountIds = {B}`.
- `환산하지_못한_행이_있으면_그_유형은_미확보다`: A가 세 유형 COVERED, ledger에 A `DIVIDEND` `amountKrw = 500`, `unconverted = 1` → `dividend = 500`, `coveredAccountIds = {}`, `coveredTypes = {FEE, TAX}`.
- `판정_대상이_없으면_세_유형_모두_확보다`: `judgedAccounts` 빈 목록 → `coveredTypes = {DIVIDEND, FEE, TAX}`, 금액 0, `ledger` · `covered`를 부르지 않는다.
- `KIS_계좌는_수수료_세금이_미확보다`: A의 covered가 `DIVIDEND`뿐 → `coveredTypes = {DIVIDEND}`.

- [ ] **Step 2: 실행해 실패 확인** — `./gradlew test --tests '*LedgerEarningsCashflowPortTest'` (DB 없음, 승인 불요).

- [ ] **Step 3: 구현.** 서비스 호출부는 `earningsCashflow.totalsBetween(scope, openingAsOf, closingAsOf, filter.accountIds())`로 바꾼다. `uncoveredAccountCount`는 이 태스크에서 `earnedCash.uncoveredAccountIds().size()`로 바꿔 컴파일만 맞춘다 — 테스트는 Task 4.

- [ ] **Step 4: 단위 테스트 통과 확인**, 그리고 `./gradlew compileTestJava`가 통과(다른 테스트가 `EmptyEarningsCashflowPort` · `NONE`을 쓰면 여기서 고친다).

- [ ] **Step 5: 커밋** — `feat: 현금흐름 원장을 읽는 포트로 빈 구현을 바꾼다`

---

### Task 4: 자산 변화의 판정과 경고 문구

**파일:**
- 고침: `…/view/AssetChangeViewService.java` (`uncoveredTypes` · `uncoveredAccountCount`, 연동 상태 거르기 제거)
- 고침: `…/view/assembly/NoticeCollector.java:139-159` (`cashflowUncovered`)
- 고침: `src/test/resources/golden/asset-change.json`
- 테스트: `src/test/java/com/stockproject/portfolio/view/assembly/NoticeCollectorTest.java`, `src/test/java/com/stockproject/portfolio/api/AssetChangeApiTest.java`

**인터페이스:**
- 소비: Task 3의 `EarningsCashflowTotals`.
- `AssemblyContext.uncoveredCashflow(List<String> types, int accountCount)`는 그대로 쓴다. `types`는 `DIVIDEND` · `FEE` · `TAX` 순서를 지킨다.

- [ ] **Step 1: 실패하는 단위 테스트 (`NoticeCollectorTest`)**

- `빠진_유형의_이름으로_알린다`: types `[FEE, TAX]`, 입출금 0 → `수수료·세금 내역이 확보되지 않아 투자손익이 정확하지 않을 수 있어요`.
- `세_유형이_모두_빠지면_모두_말한다`: `[DIVIDEND, FEE, TAX]` → `배당·수수료·세금 내역이 확보되지 않아 투자손익이 정확하지 않을 수 있어요`.
- `입출금과_함께_빠지면_한_문장으로_알린다`: `[FEE, TAX]`, 입출금 2 → `2개 계좌에 입출금이 입력되지 않았고 수수료·세금 내역도 없어 투자손익이 정확하지 않을 수 있어요`.
- 기존 `배당_수수료와_입출금이_함께_빠지면_한_문장으로_알린다` · `입출금이_모두_들어왔으면_배당_수수료만_알린다`의 기대 문구를 같은 규칙으로 고친다.

- [ ] **Step 2: 실행해 실패 확인** — `./gradlew test --tests '*NoticeCollectorTest'` (DB 없음).

- [ ] **Step 3: `NoticeCollector`에 유형 이름 잇기를 넣는다.** `입출금만` 문구는 그대로다.

- [ ] **Step 4: 단위 테스트 통과 확인.**

- [ ] **Step 5: 실패하는 API 테스트 (`AssetChangeApiTest`)** — 7월(`JULY`), 사용자 `yhr`, 기초 07-24 · 기말 07-27.

- `배당과_수수료는_번_돈에_들고_투자손익에서_빠진다`: 계좌 1에 07-25 `DIVIDEND` 120,000 · `FEE` −30,000 → `breakdown`에 `DIVIDEND 120000` · `FEE_TAX -30000`, `earned`는 원장을 넣기 전과 같고 `investment_pnl.total`은 그보다 90,000 작다.
- `편입_제외_계좌가_있어도_항등식이_맞는다`: 계좌 2의 07-27 잔고를 07-25로 복사하고 07-24 잔고를 지워 첫 잔고를 07-25로 만든다(기간 중 편입). 07-23 · 07-25 · 07-26 배당을 넣으면 07-26만 `DIVIDEND`에 들고, `opening + deposited + earned + included − excluded = closing`.
- `계좌를_걸면_그_계좌의_원장만_센다`: 계좌 1 · 2에 배당, `&account=20000000-…-0001` → 계좌 1 배당만.
- `확보한_유형은_경고에서_빠진다`: `yhr` 네 계좌 모두 `DIVIDEND = COVERED`, `FEE` · `TAX = UNAVAILABLE` → `params.types = ["FEE","TAX","DEPOSIT","WITHDRAW"]`, `params.account_count = 4`, 문구가 `수수료·세금`.
- `세_유형을_모두_확보하고_입출금만_빠지면_입출금_문구만_나온다`: 네 계좌 모두 세 유형 `COVERED` → `types = ["DEPOSIT","WITHDRAW"]`, 문구 `3개 계좌에 이 기간 입출금이 입력되지 않아 투자손익이 정확하지 않을 수 있어요`.
- `판정할_계좌가_없으면_배당_수수료_경고가_없다`: 계좌 `20000000-…-0007`의 사용자(잔고가 07-27 하루) 7월 → `CASHFLOW_UNCOVERED`가 없거나 `types`에 세 유형이 없다.
- `기간_경계와_미확보_내역을_알린다`: 원장 없이 `account_count`는 판정 대상 수(4)를 기대한다 — 실패하면 샘플의 07-24 · 07-27 잔고 계좌를 세어 기대값을 맞추고 그 근거를 주석에 적는다.

- [ ] **Step 6: DB 테스트 실행해 실패 확인** — `--tests '*AssetChangeApiTest'`.

- [ ] **Step 7: 서비스 판정 정리.** `uncoveredTypes`는 `coveredTypes`에 없는 유형을 `EarningsCashflowType` 순서로, `uncoveredAccountCount`는 `uncoveredAccountIds().size()`. `LinkState` 거르기와 import를 지운다.

- [ ] **Step 8: 골든 갱신.** `asset-change.json`의 `CASHFLOW_UNCOVERED.message`를 새 규칙의 값으로(샘플에 원장이 없으므로 세 유형 모두 빠짐 → `…입력되지 않았고 배당·수수료·세금 내역도 없어…`), `params`도 실제 응답과 맞춘다.

- [ ] **Step 9: 전체 테스트 통과 확인** — `TEST_DB_URL=… ./gradlew test --rerun-tasks` 전체 PASS.

- [ ] **Step 10: 커밋** — `feat: 자산 변화가 원장의 배당·수수료를 계좌별 구간으로 세고 빠진 유형만 알린다`

---

### Task 5: 앱 골든 픽스처 동기화

**파일:**
- 고침: `front-end/src/fixtures/golden/asset-change.json:32`
- 고침: `front-end/src/__tests__/assetChange.test.tsx:112,174`

- [ ] **Step 1: 승인 받고 최신 `origin/main`에서 `.worktrees/front-end-earnings-cashflow`(브랜치 `test/asset-change-golden-wording`) 만들기, `npm ci`.**
- [ ] **Step 2: 픽스처를 Task 4 골든의 해당 값으로 바꾸고 테스트의 기대 문구를 같은 값으로 고친다.** 112행 주석은 "배당·수수료·세금도 서버가 담지 않아 줄이 없다"로.
- [ ] **Step 3: `npx jest`와 `npx tsc --noEmit` 통과 확인.**
- [ ] **Step 4: 커밋** — `test: 자산 변화 골든의 미확보 경고 문구를 서버와 맞춘다`

---

## 끝날 때 보고

- 바뀐 파일, 테스트 결과, 남은 것(데이터 질문 N15 · N16 · N17, 스펙 §2.9 계좌유형 필터와 API의 차이).
- 영향받는 통합테스트 케이스(테스트 트랙에 보고, `docs/yhr/test/`는 고치지 않는다):
  - N-46: 원장 `DEPOSIT` 행은 표 CHECK가 받지 않는다. 기대 결과 "원장의 `DEPOSIT` 행은 넣은 돈에 들지 않는다"는 "넣을 수 없다"로 바뀐다. 배당 · 수수료 쪽은 자동화(`AssetChangeApiTest`)가 생겼다.
  - PF8-11: 원장 커버리지가 세 유형 `COVERED`인 데이터로 만들 수 있다. KIS 계좌만으로는 수수료 · 세금이 늘 미확보라 재현되지 않는다.
  - PF7-06 · D-22 · SG-08: `account_count`가 계좌 필터 안에서 센다.
  - 미확보 문구를 기대하는 케이스: 배당 · 수수료 쪽 문구가 빠진 유형 이름으로 바뀐다.
