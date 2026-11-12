# 종가 평가와 시장별 가격 기준일 안내 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 보유 스냅샷의 종목 평가금액을 그 시장 마지막 거래일 종가로 내고 그 날짜를 라인에 저장한다. 화면 기준일보다 이른 종가이거나 종가로 평가하지 못한 종목이 있으면 `PRICE_LAG_MARKET` 안내로 알리고, 앱이 배너 캡션으로 그린다.

**Architecture:** 생성기(`snapshot/`)는 `cln_balance`에 데이터팀 뷰 `balance_close_valuation`을 PK로 붙여 읽고, `close_value`를 현지 평가금액으로, `close_date`를 `position_line.price_as_of`로 쓴다. 이월은 원본의 `price_as_of`를 그대로 옮긴다. 조회 계층은 화면 필터를 건 보유 라인에서 시장마다 가장 이른 `price_as_of`와 시세 종목 수를 구해 `AssemblyContext`에 싣고, `NoticeCollector`가 판정해 문장을 완성한다. 앱은 `notices.ts`의 화면 목록 넷에 코드를 더한다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · MyBatis · Flyway · PostgreSQL 16 · JUnit 5 · AssertJ / React Native(Expo 58) · TypeScript · jest-expo

**Spec:** [포트폴리오 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) §5.4 · §7.4 · §8.2 · §9.1, [생성기 설계](../specs/portfolio-management/2026-10-15-position-line-builder-design.md) §4.1 · §4.4 · §5.3 · §5.4 · §5.6 · §6.3, [데이터 요구사항](../specs/data-requirements.md) §6.5 `balance_close_valuation`. 뷰 정의 원본은 `dataeng` origin/main `reverse_etl/ddl.py`다.

## Global Constraints

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어. 커밋 접두어 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **커밋 · 푸시는 사용자가 요청할 때만 한다.** 각 태스크의 커밋 단계는 요청을 받은 뒤 실행한다.
- 주석은 히스토리 없이 최신 사실만 쓰고, 문서 절 번호(§ · SG-)를 지칭하지 않고 주석만으로 이해되게 쓴다. 검증하지 않은 것은 단정하지 않는다.
- 운영 DB에 쓰지 않는다. 구현 중 스펙 · 설계와 코드가 어긋나면 멈추고 보고한다. `dataeng/`과 통합테스트 문서(`docs/yhr/test/`)는 고치지 않는다.
- 마이그레이션 번호: `V20__position_line_price_as_of.sql`(`db/migration`) · `V21__balance_close_valuation_mirror.sql`(`db/external`). 머지 직전 origin/main에 같은 번호가 생겼으면 다음 빈 번호로 옮기고 전용 DB를 새로 만들어 다시 돌린다(DB를 지우거나 만드는 일은 승인을 받는다).
- DB를 쓰는 테스트는 전용 DB에서만 돈다: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_price_lag?currentSchema=app,data' ./gradlew test --rerun-tasks` (특정 클래스는 `--tests '<FQCN>'` 추가). 공유 `portfolio_test`에서 돌리지 않는다. DB 테스트는 돌리기 전에 사용자에게 묻는다. DB 없는 단위 테스트는 묻지 않는다.
- 테스트 메서드 이름은 기존처럼 한국어 문장.
- 앱: Expo SDK 58. 끝에 `npx jest` · `npx tsc --noEmit` 통과.
- main 푸시는 곧 운영 배포이고 `db/migration`의 V20이 운영에 적용된다. `db/external`(V21)은 운영 프로필이 적용하지 않는다.

## Review Focus

1. **미매칭 종목이 영구 실패가 되는 것** — 뷰는 `instrument`와 내부 조인이라 미매칭 종목은 `close_value`가 비어 있다. `UNMATCHED_INSTRUMENT`(재시도)가 `INVARIANT`(재시도 없음)보다 먼저여야 한다. → Task 2 `미매칭_종목은_평가금액이_비어도_재시도_실패다`.
2. **이월이 날짜를 잃는 것** — 잠정 이월 · 확정 이월 · 이후 날짜 이월 셋 다 `price_as_of`를 옮겨야 한다. → Task 3 `이월은_종가_날짜를_그대로_옮긴다`(세 경로).
3. **이월 계좌 하나가 시장 전체 날짜를 끌어내리는 것** — 이월 아닌 라인이 있으면 이월 라인을 빼고, 전부 이월이면 이월 라인으로 판정한다. → Task 4 `이월_라인은_날짜에서_빠진다` · `전부_이월이면_이월_라인으로_판정한다`.
4. **알릴 필요 없는 종가 문장** — 날짜가 화면 기준일과 같고 시세 종목만 있으면 시세 문장만 낸다. 둘 다 없으면 그 시장을 싣지 않는다. → Task 5 `날짜가_같으면_시세_문장만_낸다`.
5. **필터와 다른 대상을 세는 것** — 국내 시장만 고른 화면에 미국 안내가 붙지 않는다. → Task 4 `시장_필터가_안내_대상을_좁힌다`.
6. **운영에 뷰가 없는 채로 배포되는 것** — 생성기가 매 회차 오류로 확정이 멈춘다. → Task 9의 머지 전 확인.

---

## 파일 구조

**back-end** (`.worktrees/back-end-price-lag`, 브랜치 `feat/price-lag-market`)

| 파일 | 책임 |
|---|---|
| `src/main/resources/db/migration/V20__position_line_price_as_of.sql` (신규) | `position_line.price_as_of date NULL` |
| `src/main/resources/db/external/V21__balance_close_valuation_mirror.sql` (신규) | `data.balance_close_valuation` 뷰 미러 |
| `.../snapshot/BalanceMapper.java` · `BalanceRow.java` | 뷰를 붙여 `close_value` · `close_date`를 읽는다 |
| `.../snapshot/Line.java` · `LineCalculator.java` · `PositionWriteMapper.java` | `priceAsOf` 컬럼, 평가금액 · 판정 순서 |
| `src/main/resources/db/sample/sample_portfolio.sql` · `sample_lookthrough.sql` · `sample_split.sql` | 샘플 라인의 `price_as_of` |
| `.../query/aggregate/MarketPriceMapper.java` (신규) · `src/main/resources/mapper/MarketPriceMapper.xml` (신규) · `.../query/MarketPriceAsOf.java` (신규) | 시장별 가격 기준일 · 시세 종목 수 |
| `.../view/assembly/AssemblyContext.java` · `NoticeCollector.java` · `.../view/SnapshotViewService.java` | 판정 재료 · 판정 · 문장 |
| `src/test/resources/golden/*.json` | 바뀐 골든 |
| `src/test/java/.../snapshot/LineCalculatorTest.java` · `LineInvariantsTest.java` · `RunProcessor*Test` · `FinalizerTest.java` · `query/SchemaContractTest.java` · `query/aggregate/MarketPriceMapperTest.java`(신규) · `view/assembly/NoticeCollectorTest.java` | 테스트 |

**front-end** (`.worktrees/front-end-price-lag`, 브랜치 `feat/price-lag-market`)

| 파일 | 책임 |
|---|---|
| `src/envelope/notices.ts` | `PRICE_LAG_MARKET`을 요약 · 종목별 · 비중 · 계좌별 목록에 |
| `src/__tests__/notices.test.ts` · `src/__tests__/envelope.test.tsx` | 배치 · 캡션 순서 |

## 픽스처 수치 (Task 1이 샘플에 넣고 이후 태스크가 단언한다)

샘플의 화면 기준일은 `2026-07-27`(월), 직전 스냅샷은 `2026-07-24`(금)이다. 미국 직전 거래일은 각각 07-24 · 07-23이다.

| 라인 | `price_as_of` |
|---|---|
| 07-27 국내 종목 · 국내 ETF(이월 아님) | `2026-07-27` |
| 07-27 계좌1 AAPL · 계좌7 AAPL(이월 아님) | `2026-07-24` |
| 07-27 계좌4 MSFT(07-24에서 이월) | `2026-07-23` |
| 07-24 국내 종목 · 국내 ETF | `2026-07-24` |
| 07-24 미국 종목 | `2026-07-23` |
| `CASH` 라인 전부 | null |

그러면 yhr(계좌1~4)의 현재 스냅샷 화면에는 `PRICE_LAG_MARKET` 하나가 붙는다 — `markets: [{market: "US", price_as_of: "2026-07-24", quote_count: 0}]`, 문장 `미국 종목은 07-24 종가 기준이에요`. 계좌4만 고르면 미국 라인이 전부 이월이라 `price_as_of: "2026-07-23"`, 문장 `미국 종목은 07-23 종가 기준이에요`. jdh(계좌5 · 6, 국내만) 화면에는 안내가 없고, hhj(계좌7, AAPL) 화면에는 US 07-24 안내가 붙는다. 두 사용자의 안내 목록 전체를 비교하는 테스트는 없다.

`sample_split.sql`은 계좌2(NAVER · KRW 예수금)의 07-24 라인을 07-23으로 복사한다. 거기서는 `CASE WHEN price_as_of IS NULL THEN NULL ELSE DATE '2026-07-23' END`로 NAVER `2026-07-23`, 예수금 null이 된다.

---

### Task 0: 작업 공간과 전용 DB

- [ ] 최신 origin/main에서 worktree 둘을 만든다(이름은 위 파일 구조). 만들기 전에 이름을 알리고 승인을 받는다.
- [ ] `portfolio_test_price_lag` DB를 만든다(승인 필요). 앱 worktree의 `npm ci`도 승인을 받고 돌린다.
- [ ] 바꾸기 전 기준선: 백엔드 전체 테스트(전용 DB, 승인 후)와 앱 `npx jest` · `npx tsc --noEmit`이 통과하는지 확인한다. 실패가 있으면 이 작업과 무관한지 보고한다.

### Task 1: 마이그레이션 · 뷰 미러 · 샘플

**Files:** `V20__position_line_price_as_of.sql` · `V21__balance_close_valuation_mirror.sql` · `sample_portfolio.sql` · `sample_lookthrough.sql` · `sample_split.sql` · `SchemaContractTest.java`

- [ ] **Step 1: 실패하는 테스트.** `SchemaContractTest`에 둘을 더한다.
  - `position_line에_종가_날짜_컬럼이_있다`: `price_as_of`가 `date`이고 null 허용.
  - `종가_평가_뷰의_컬럼이_데이터_계약과_같다`: 기존 도우미 `columnsOf`는 이름순이므로 기대값도 이름순으로 둔다 — `account_ref, close_date, close_price, close_value, currency, instrument_id, market_value, quantity, source_as_of, valuation_basis`.
  - 전용 DB에서 돌려(승인 후) 둘 다 실패하는 것을 확인한다.
- [ ] **Step 2:** V20 — `ALTER TABLE position_line ADD COLUMN price_as_of date;` 주석: 평가에 쓴 종가의 날짜, 종가가 없어 원천 평가금액을 썼거나 예수금이면 비어 있다, 이 컬럼보다 먼저 만든 라인은 비어 있다.
- [ ] **Step 3:** V21 — 데이터 DDL의 `CREATE OR REPLACE VIEW data.balance_close_valuation AS ...`를 그대로 옮긴다. 파일 머리 주석은 V7처럼 "데이터팀 소유 뷰의 로컬 · 테스트 전용 미러, 운영 프로필은 적용하지 않는다, 정의는 데이터 DDL과 같게 둔다"로 쓴다.
- [ ] **Step 4:** 샘플 세 파일의 `position_line` INSERT에 `price_as_of`를 위 픽스처 수치대로 넣는다. `sample_portfolio.sql`의 07-24 `INSERT … SELECT`는 `instrument.market`으로 갈라 국내 `2026-07-24` · 미국 `2026-07-23` · `CASH` null을 넣는다. `sample_split.sql`은 위 픽스처 수치 절의 `CASE` 식으로 넣는다.
- [ ] **Step 5:** `SchemaContractTest`를 전용 DB에서 돌린다(승인 후). 통과.
- [ ] **Step 6: 커밋**(요청 시) `feat: 보유 라인에 종가 날짜 컬럼과 종가 평가 뷰 미러를 더한다`

### Task 2: 생성기가 종가로 평가한다

**Files:** `BalanceRow.java` · `BalanceMapper.java` · `Line.java` · `LineCalculator.java` · `PositionWriteMapper.java` · `LineCalculatorTest.java` · `LineInvariantsTest.java`

- [ ] **Step 1: 실패하는 단위 테스트**(`LineCalculatorTest`, DB 없음).
  - `종가가_있으면_종가로_평가하고_날짜를_남긴다`: `close_value = 4,388.0000` · `close_date = 07-24`인 USD 행 → `market_value_local = 4388.0000`, `market_value_krw = local × fx` HALF_UP, `price_as_of = 2026-07-24`.
  - `종가가_없으면_원천_평가금액이고_날짜가_비어_있다`: `close_value = market_value`, `close_date = null` → 원천 값 · `price_as_of` null.
  - `예수금_라인은_종가_날짜가_없다`.
  - `미매칭_종목은_평가금액이_비어도_재시도_실패다`: `instrument_id`가 마스터에 없고 `close_value` null → `UNMATCHED_INSTRUMENT`.
  - `매칭된_종목의_평가금액이_비면_계산_실패다`: 마스터에 있는데 `close_value` null → `INVARIANT`.
- [ ] **Step 2: 구현.**
  - `BalanceRow`에 `closeValue` · `closeDate`를 더한다.
  - `BalanceMapper.balances`: `FROM cln_balance b LEFT JOIN balance_close_valuation v ON v.account_ref = b.account_ref AND v.instrument_id = b.instrument_id AND v.source_as_of = b.source_as_of`. 뷰에도 `quantity` · `market_value` · `currency` · `instrument_id` · `account_ref` · `source_as_of`가 있으므로 기존 SELECT · WHERE · ORDER BY 컬럼에 모두 `b.`를 붙이고 `v.close_value, v.close_date`를 더한다. 주석: 원천 평가금액은 조회 시각의 시세라 수집 시각에 따라 미국 종목이 프리마켓 · 장중 가격이 되므로, 평가금액은 그 시장 마지막 거래일 종가로 낸 값을 붙여 읽는다.
  - `Line`에 `LocalDate priceAsOf`(`fxAsOf` 다음)를 더하고 `carriedTo`가 그대로 옮긴다.
  - `LineCalculator`: 원천 NOT NULL 검사(수량 · 평단 · 원천 평가금액 · 통화) → 수량 0 거름 → 미매칭 → `closeValue` null이면 `INVARIANT` → 환율 순서. 평가금액은 `closeValue`, 날짜는 `closeDate`. 예수금 행은 `priceAsOf` null.
  - `PositionWriteMapper.lines` · `insert`에 `price_as_of`를 더한다.
  - `LineInvariantsTest` 등 `new Line(...)`을 쓰는 테스트를 새 생성자에 맞춘다.
  - `LineCalculatorTest`의 기존 `new BalanceRow(...)`는 `closeValue = marketValue`, `closeDate = null`로 맞춘다. 그대로 두면 `closeValue`가 비어 새 `INVARIANT`에 걸린다. `종목_행의_수치나_통화가_null이면_INVARIANT`의 `market_value` null 행은 `closeValue`도 비운다.
- [ ] **Step 3:** 단위 테스트 통과(묻지 않고 돌린다).
- [ ] **Step 4: 커밋**(요청 시) `feat: 보유 라인을 그 시장 마지막 거래일 종가로 평가한다`

### Task 3: 실행 처리 · 확정 · 이월의 통합 확인

**Files:** `SnapshotFixture.java` · `RunProcessor*Test` · `FinalizerTest.java`

- [ ] **Step 1: 확인 테스트**(전용 DB, 승인 후). Task 2 구현으로 통과해야 하는 통합 확인이다.
  - `SnapshotFixture` 준비:
    - `reset()`의 TRUNCATE 목록에 `adjusted_price_daily`를 더한다. 다른 샘플이 남긴 AAPL · 삼성전자 일봉이 "종가가 없는 날"에 섞이지 않게 한다.
    - US 캘린더 행(`close_at` 포함)과 일봉을 심는 도우미를 더한다. `prev_trading_day` · `next_trading_day`(NOT NULL)를 계산해 넣고, 수집 시각에서 15일 안의 날짜로 깐다(뷰가 그 범위만 본다).
    - `lines()`의 SELECT에 `price_as_of` · `market_value_local`을 더한다. 기존 사용처는 키로 읽기만 해서 깨지지 않는다.
    - 기존 KR 캘린더 행은 `close_at` 없이 심으므로 기존 테스트는 뷰가 `KIS`로 대신해 값이 바뀌지 않는다.
  - 수치: 수집 `2026-11-10T23:00+09:00`(화). US 캘린더 11-06(금) · 11-09(월) 거래일, `close_at`은 각 날 16:00 EST(= 다음 날 06:00 KST). 11-07 · 11-08은 비거래일. 일봉 AAPL 11-09 종가 `350.69`, `adj_factor = 1`. 잔고 AAPL 10주, 원천 평가금액 `3517.0000`(프리마켓 351.70).
  - `종가가_있는_날은_종가로_라인을_만든다`: 라인 `market_value_local = 3506.9000`, `price_as_of = 2026-11-09`.
  - `종가가_없는_날은_원천_평가금액으로_라인을_만든다`: 11-09 일봉을 심지 않으면 `market_value_local = 3517.0000`, `price_as_of` null.
  - `이월은_종가_날짜를_그대로_옮긴다`: 원본 라인은 위 종가를 심은 날 생성기로 만든다(raw INSERT를 쓰는 기존 테스트에 얹는 경우는 INSERT에 `price_as_of`를 넣는다). 잠정 이월(같은 사용자의 다른 계좌), 이 계좌의 이후 날짜, 확정 이월 세 경로에서 이월 라인의 `price_as_of`가 원본과 같다.
- [ ] **Step 2:** 실패하면 그 경로를 고친다. 지금 이월 세 경로(`RunProcessor.carrySiblings` · `carryToLaterDates`, `Finalizer.finalizeAccount`)는 모두 `Line.carriedTo`를 거친다.
- [ ] **Step 3:** `snapshot` 패키지 테스트 전체를 전용 DB에서 돌린다(승인 후).
- [ ] **Step 4: 커밋**(요청 시) `test: 종가 평가와 이월의 종가 날짜를 통합으로 확인한다`

### Task 4: 시장별 가격 기준일 조회

**Files:** `MarketPriceAsOf.java` · `MarketPriceMapper.java` · `MarketPriceMapper.xml` · `MarketPriceMapperTest.java`

- [ ] **Step 1: 실패하는 테스트**(전용 DB, `sample_portfolio.sql`, 승인 후).
  - `시장마다_가장_이른_종가_날짜와_시세_종목_수를_낸다`: yhr 07-27 → `[KR 2026-07-27 0, US 2026-07-24 0]`(시장 코드 오름차순).
  - `이월_라인은_날짜에서_빠진다`: 위 결과에서 계좌4 MSFT(07-23)가 US 날짜를 끌어내리지 않는다.
  - `전부_이월이면_이월_라인으로_판정한다`: 계좌4만 고르면 `US 2026-07-23`.
  - `시세_종목은_서로_다른_종목으로_센다`: 계좌2에 AAPL 07-27 라인(`price_as_of` null)을 더하고 계좌1 AAPL의 `price_as_of`를 null로 바꾸면 `US quote_count = 1`, `price_as_of` null(계좌4 MSFT는 이월이라 빠진다).
  - `시장_필터가_안내_대상을_좁힌다`: 시장 KR만 고르면 US 행이 없다.
  - `예수금과_연동_해제_계좌는_세지_않는다`: 기본 결과의 `quote_count = 0`이 예수금(`price_as_of` null)을 세지 않았다는 증거다. 계좌1을 해제하면 `[KR 2026-07-27 0, US 2026-07-23 0]`(남은 미국 라인이 계좌4 이월뿐).
  - `다른_사용자의_라인은_세지_않는다`: jdh는 `[KR 2026-07-27 0]`만, hhj는 `[US 2026-07-24 0]`만.
- [ ] **Step 2: 구현.** `MarketPriceAsOf(String market, LocalDate priceAsOf, int quoteCount)`. 매퍼 `@Param`은 `scope` · `asOf` · `filter`. 질의는 화면과 같은 대상을 세도록 필터를 `com.stockproject.portfolio.query.aggregate.AggregateMapper.filters` 조각(전체 이름, 별칭 `acct` · `i`)으로 건다. 이 조각은 null 검사가 없으므로 필터가 없을 때 `LineFilter.NONE`을 넘긴다. 범위 · 대상 조건은 조인 조건에 둬 `filters`의 `<where>`와 겹치지 않게 한다.
  - 대상(조인 조건): 그 날짜 · 그 사용자 · 연동 해제 아님 · `i.asset_class <> 'CASH'` · `pl.quantity > 0`.
  - 시장마다 `bool_and(is_carried_forward)`를 구해, 이월 아닌 라인이 있으면 이월 라인을 뺀다.
  - `min(price_as_of)` · `count(DISTINCT instrument_id) FILTER (WHERE price_as_of IS NULL)`, `GROUP BY market ORDER BY market`.
  - 매퍼 주석: 이월 라인을 빼는 이유(한 계좌가 며칠 전 값으로 이월돼 있다고 시장 전체를 그 날짜로 말하면 나머지 종목에 틀린 말이 된다).
- [ ] **Step 3:** 테스트 통과(전용 DB).
- [ ] **Step 4: 커밋**(요청 시) `feat: 화면 대상 보유 라인의 시장별 종가 날짜와 시세 종목 수를 읽는다`

### Task 5: 안내 판정과 문장

**Files:** `AssemblyContext.java` · `NoticeCollector.java` · `NoticeCollectorTest.java`

- [ ] **Step 1: 실패하는 단위 테스트**(`NoticeCollectorTest`, DB 없음). 화면 기준일 07-27.
  - `미국_종가가_이르면_날짜로_알린다`: `[US 07-24 0]` → `severity = info`, 문장 `미국 종목은 07-24 종가 기준이에요`, `params.markets = [{market: US, price_as_of: 2026-07-24, quote_count: 0}]`.
  - `날짜와_시세를_함께_알린다`: `[US 07-24 1]` → `미국 종목은 07-24 종가 기준이에요 · 미국 1개 종목은 수집 시각 시세예요`.
  - `전부_시세면_시세_문장만_낸다`: `[US null 3]` → `미국 3개 종목은 수집 시각 시세예요`, `price_as_of` null.
  - `날짜가_같으면_시세_문장만_낸다`: `[KR 07-27 1]` → `국내 1개 종목은 수집 시각 시세예요`, `params.markets[0].price_as_of = 2026-07-27`(종가로 평가한 라인이 있으므로 null이 아니다).
  - `날짜가_같고_시세가_없으면_싣지_않는다`: `[KR 07-27 0]` → 안내 없음.
  - `두_시장을_한_문장으로_잇는다`: `[KR 07-27 1, US 07-24 0]` → `국내 1개 종목은 수집 시각 시세예요 · 미국 종목은 07-24 종가 기준이에요`, `markets`에 둘 다.
  - `알릴_시장만_싣는다`: `[KR 07-27 0, US 07-24 0]` → `markets`에 US만.
  - `기준일이_없으면_내지_않는다`: 빈 스냅샷(`asOf` null).
  - `안내_순서는_선언_순서다`: `FX_APPLIED` · `SYNC_IN_PROGRESS` · `ALREADY_FINAL`과 함께면 `SYNC_IN_PROGRESS` 뒤, `ALREADY_FINAL` 앞.
- [ ] **Step 2: 구현.**
  - `AssemblyContext`의 `priceAsOfByMarket`을 `List<MarketPriceAsOf> marketPrices`로 바꾸고 빌더 `marketPrices(List)`를 더한다.
  - `NoticeCollector`: `PRICE_LAG_MARKET -> priceLagMarket(context)`. 56행의 "아직 재료가 없다" 주석을 지운다. 시장 이름은 `KR` → `국내`, `US` → `미국`, 그 밖은 코드 그대로. 날짜는 `MM-dd`. 종가 문장은 `priceAsOf`가 기준일보다 이를 때만, 시세 문장은 `quoteCount > 0`일 때만. 시장마다 종가 문장 → 시세 문장 순으로 만들고 ` · `로 잇는다.
  - 메서드 주석: 시세 종목 수를 함께 말하는 이유(대부분 종가인데 일부만 시세일 때 "종가 기준"이라고만 하면 그 종목에는 틀린 말이 된다).
- [ ] **Step 3:** 단위 테스트 통과.
- [ ] **Step 4: 커밋**(요청 시) `feat: 시장별 가격 기준일 안내를 판정한다`

### Task 6: 스냅샷 뷰 넷에 싣기와 골든

**Files:** `SnapshotViewService.java` · `src/test/resources/golden/*.json` · 골든 · API 테스트

- [ ] **Step 1:** `SnapshotViewService` 생성자에 `MarketPriceMapper`를 주입하고, `collectNotices`에서 `.marketPrices(...)`를 채운다(필터는 그 화면의 `LineFilter`). 빈 스냅샷 경로(`emptyEnvelope`)는 채우지 않는다. 이 서비스를 손으로 생성하는 테스트는 없다.
- [ ] **Step 2:** 골든 테스트를 전용 DB에서 돌린다(승인 후). 예상 변경: `summary` · `positions` · `positions-lookthrough` · `allocation-sector` · `allocation-sector-lookthrough` · `accounts`의 `notices` 맨 뒤(선언 순서상 `SYNC_IN_PROGRESS` 다음, `ALREADY_FINAL` 앞)에 위 픽스처 수치의 `PRICE_LAG_MARKET`이 하나 붙는다. 그 밖의 차이(금액 · 행 · 다른 안내)가 나오면 멈추고 보고한다.
- [ ] **Step 3:** 골든 파일을 손으로 고친다. 바뀐 파일과 이유("미국 직전 거래일 종가 기준 안내가 새로 실린다")를 보고에 적는다.
- [ ] **Step 4:** `FX_APPLIED`를 단언하는 다른 API 테스트(`DisconnectedAccountViewTest` · `InstrumentDetailApiTest` · `SnapshotViewApiTest`)는 기대 변경이 없어야 한다. 목록 전체를 비교하는 것은 종목 상세뿐이고 종목 상세는 이 안내를 싣지 않는다. 바뀌면 멈추고 보고한다.
- [ ] **Step 5:** 백엔드 전체 테스트를 전용 DB에서 돌린다(승인 후).
- [ ] **Step 6: 커밋**(요청 시) `feat: 현재 스냅샷 화면에 시장별 가격 기준일 안내를 싣는다`

### Task 7: 앱

**Files:** `src/envelope/notices.ts` · `src/__tests__/notices.test.ts` · `src/__tests__/envelope.test.tsx`

- [ ] **Step 1: 실패하는 테스트.**
  - `notices.test.ts`: `it('가격 기준일 안내는 스냅샷 네 화면의 캡션이다')` — `placement('PRICE_LAG_MARKET', 'info')`의 caption이 `['summary', 'positions', 'allocation', 'accounts']`, banner는 `[]`.
  - `envelope.test.tsx`: 종목별 화면 캡션이 `FX_APPLIED` 문장 ` · ` `PRICE_LAG_MARKET` 문장 순서로 이어진다(서버가 내린 순서).
- [ ] **Step 2:** `notices.ts`에 스냅샷 화면 공통 목록을 두고 `PRICE_LAG_MARKET`을 넣어 네 화면에 펼친다. 주석: 미국 종목 값이 화면 기준일보다 이른 종가라는 것을 알려 주는 단서라 금액을 보여 주는 스냅샷 화면이면 어디서든 그린다, 자산 변화 · 실현손익 응답에는 서버가 싣지 않는다.
- [ ] **Step 3:** `npx jest` · `npx tsc --noEmit` 통과.
- [ ] **Step 4: 커밋**(요청 시) `feat: 시장별 가격 기준일 안내를 스냅샷 화면 캡션으로 그린다`

### Task 8: 스펙 대조 리뷰

- [ ] 독립 리뷰어 서브에이전트로 이 브랜치의 백엔드 · 앱 변경을 스펙 · 설계와 대조한다. 고칠 것은 반영하고, 결정이 필요한 것만 사용자에게 묻는다.

### Task 9: 머지 전 확인

- [ ] **운영 뷰 확인(읽기만, 승인 후):** 운영 앱 DB에 `data.balance_close_valuation`이 있고 백엔드 계정이 `SELECT`할 수 있는지(`has_table_privilege`), 컬럼 목록이 미러(V21)와 같은지 읽는다. 운영 프로필은 미러를 적용하지 않아 테스트가 이 차이를 잡지 못한다. 클러스터 가동 시간은 사용자에게 묻는다. 없으면 머지하지 않고 데이터팀 요청으로 정리한다.
- [ ] 최신 origin/main에 리베이스(문서 · 백엔드 · 앱). 마이그레이션 번호가 겹치면 옮기고 전용 DB를 새로 만들어 다시 돌린다(승인 후). 앱은 리베이스 뒤 `npm ci`(승인 후).
- [ ] 백엔드 전체 테스트(전용 DB) · 앱 `npx jest` · `npx tsc --noEmit` 통과.
- [ ] 머지는 사용자가 요청할 때 한다.

## 끝나면 보고할 것

- 바뀐 파일 · 테스트 결과 · 바뀐 골든과 이유 · 남은 것.
- 영향받는 통합테스트(테스트 트랙이 고친다):
  - PF5-07: 유보에서 돌릴 수 있게 된다. 기대 결과의 `params`는 `markets: [{market, price_as_of, quote_count}]`이고 `price_as_of`는 라인에 저장된 종가 날짜다. 문구는 `미국 종목은 MM-dd 종가 기준이에요`, 자리는 요약 · 종목별 · 비중 · 계좌별 배너 캡션이다.
  - 테스트 설계 PF5 시나리오 ⑤: `PRICE_LAG_MARKET`이 실제로 실린다.
  - 케이스 문서 역추적표 "근사 중에는 `PRICE_LAG_MARKET`을 끈다": 이제 캘린더가 없으면 뷰가 날짜를 정하지 못해 원천 평가금액으로 평가되고, 안내가 그 종목을 수집 시각 시세로 알린다.
  - 바뀐 동작: 미국 종목 평가금액 · 평가손익이 KIS 앱 화면 값(조회 시각 시세)과 다를 수 있다. KIS 앱과 금액을 대조하는 케이스가 있으면 기대가 바뀐다.
  - 바뀐 동작: 배포 전에 만든 라인(배포 날의 현재 스냅샷, 그 라인을 이월 중인 계좌)은 `price_as_of`가 비어 있어, 다음 스냅샷까지 "국내 N개 · 미국 M개 종목은 수집 시각 시세예요"가 뜬다. 이월 계좌는 이월이 이어지는 동안 계속 뜬다.
  - 바뀐 동작: 국내 장중에 수집한 잔고가 있으면 국내 종목이 전 거래일 종가로 평가되고 "국내 종목은 MM-dd 종가 기준이에요"가 붙는다. 지금 수집 일정(23:00)에서는 생기지 않는다.
  - SG-43은 미결로 남는다(화면 기준일과 미국 종가 날짜의 어긋남 자체는 그대로이고, 안내로 알린다).
