# 투자손익 확정 · 평가 분해 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 자산 변화가 거래 원장으로 확정 손익을 셀 수 있는 기간에 투자손익을 `확정`(견준 구간에 판 체결의 실현손익)과 `평가`(나머지)로 나눠 낸다. 앱의 `실현손익 뷰 →`는 합계가 확정과 같아지는 기간 · 계좌로만 실현손익을 연다.

**Architecture:**
- 판정 재료는 새 매퍼 `InvestmentSplitMapper` 두 질의가 읽는다. 둘 다 배당 · 수수료 · 세금 판정과 같은 계좌별 구간 조각(`EarningsCashflowMapper.span`)을 쓴다.
- 나눌지, 두 몫이 얼마인지, 링크를 어느 기간으로 열지(또는 감출지)는 DB 없는 순수 클래스 `InvestmentSplit`이 정한다.
- `AssetChangeViewService.render`는 `REPEATABLE READ` 읽기 전용 트랜잭션으로 모든 질의를 한 시점에 묶는다.
- 앱은 응답의 `realized_period` · `realized_link_available`과 지금 계좌 필터로 링크를 만든다. 실현손익 화면은 받은 계좌로 필터를 건다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · MyBatis · PostgreSQL 16 · JUnit 5 · AssertJ / React Native(Expo 58) · TypeScript · jest-expo

**Spec:**
- [포트폴리오 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) §2.9 "확정 · 평가로 나눈다" · §8.4 `investment_pnl`
- [앱 정보 구조](../specs/app-information-architecture.md) §2 실현손익 들어오는 곳
- 판정 재료의 뜻: [평단 · 실현손익 생성기 설계](../specs/portfolio-management/2026-10-29-position-basis-design.md) §4.2 · §5.4

## 공통 제약

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어로 쓴다.
  - 커밋 접두어는 `feat:` · `fix:` · `test:` · `docs:` · `chore:`
  - 끝줄은 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`
- **커밋 · 푸시는 사용자가 요청할 때만 한다.** 각 태스크의 커밋 단계는 요청을 받은 뒤 실행한다.
- 주석 규칙
  - 히스토리 없이 최신 사실만 쓴다
  - 문서 절 번호(§ · SG-)를 지칭하지 않고, 주석만 읽어도 이해되게 쓴다
  - 검증하지 않은 것은 단정하지 않는다
- 운영 DB에 쓰지 않는다. 구현 중 스펙과 코드가 어긋나면 멈추고 보고한다.
- 다른 트랙의 코드는 고치지 않는다. 생성기(`basis/` 패키지)는 결과 표(`position_basis` · `realized_pnl_line` · `basis_build`)만 읽는다. 보유 스냅샷 생성기(`snapshot/`), `dataeng/`, 실현손익 매퍼의 시간대 고정값도 손대지 않는다.
- 마이그레이션은 없다.
- DB를 쓰는 테스트는 브랜치 전용 DB에서만 돈다.
  - `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_investment_split?currentSchema=app,data' ./gradlew test --rerun-tasks`
  - 특정 클래스만 돌릴 때는 `--tests '<FQCN>'`를 붙인다
  - 돌리기 전에 사용자에게 묻는다. DB 없는 단위 테스트는 묻지 않는다
- 테스트 메서드 이름은 기존처럼 한국어 문장으로 쓴다.
- MyBatis XML 안의 `<` · `<=` · `>` · `>=`는 기존 매퍼처럼 `&lt;` · `&gt;`로 이스케이프한다. 아래 SQL은 읽기 쉽게 이스케이프 전 모양으로 적었다.
- 앱은 Expo SDK 58이다. 끝에 `npx jest` · `npx tsc --noEmit`가 통과해야 한다.

## 검토 초점

1. **확정은 계좌마다 첫 잔고 다음 날 ~ 마지막 잔고로 센다.**
   - 기간 중 연동하거나 해제한 계좌는 투자손익에 그 계좌의 잔고 구간만 들어간다. 잔고가 하루뿐인 계좌는 0으로 들어간다
   - 확정이 이보다 넓게 세면 평가 몫이 그만큼 반대로 틀어진다
   - → Task 3 `매도는_계좌의_첫_잔고_다음_날부터_마지막_잔고까지_한국_날짜로_센다`
2. **"확정 0원"은 셀 수 있을 때만 나온다.**
   - 다섯 조건 중 하나라도 어긋나는 계좌가 있으면 전체가 `false`다: 커버리지 · 커버리지를 받은 뒤의 생성기 처리 · 원화 전용 · 양 끝 이월 없음 · 등급
   - 판정할 계좌가 하나도 없을 때도 `false`다
   - → Task 2의 `나누지_않는다` 묶음
3. **링크로 연 합계가 확정과 같다.**
   - 같은 기간 · 같은 필터로 실현손익 뷰가 합산할 체결 집합과 확정의 체결 집합을 견준다
   - 다르면 확정을 센 구간으로 다시 견준다. 그래도 다르면 링크를 감춘다
   - 생성기는 체결 커버리지 시작일부터 매도 줄을 쓴다(`BasisBuilder`가 `covered_from`부터 체결을 읽는다). 그래서 연동 전에 판 체결과, 잔고가 하루뿐인 계좌의 매도가 실제로 이 경우를 만든다
   - → Task 2 `어느_기간으로도_같은_체결을_셀_수_없으면_링크를_감춘다`, Task 5 `연동_날_판_체결이_있으면_나누되_링크를_감춘다`
4. **커버리지가 생성기 처리 뒤에 넓어지면 나누지 않는다.**
   - 생성기는 처리하던 때의 `covered_from`부터 체결을 읽는다
   - 그 뒤에 커버리지가 넓어지면, 다음 처리 전까지 넓어진 구간의 매도 줄이 없다
   - 그래서 `built_at >= computed_at`인 `BUILT`만 처리로 본다
   - → Task 3 `커버리지가_처리_뒤에_다시_계산됐으면_처리로_보지_않는다`
5. **기말이 확정 전이면 나누지 않는다.**
   - 생성기는 확정된 잔고만 처리하므로 확정 전 기말에는 `BUILT`가 생길 수 없다
   - 이번 달은 동기화를 마친 밤부터 다음 날 확정 · 생성기 처리까지 분해와 링크가 없다
   - 로컬 재현도 확정된 잔고 쌍으로만 한다(Task 4 덧씌움)
6. **한 응답 한 시점.**
   - `render`가 `REPEATABLE READ` 읽기 전용 트랜잭션이어야 투자손익 계산과 실현손익 합산이 같은 시점의 표를 본다
   - → Task 5 `응답_조회는_한_시점을_보는_읽기_전용_트랜잭션이다`
7. **앱이 이전 응답과 새 필터를 섞지 않는다.**
   - `useAssetChange`는 이전 응답을 자리표시로 남긴다
   - 그동안 링크를 누르면 이전 응답의 구간에 새 계좌가 실린다. 그래서 자리표시인 동안은 링크를 그리지 않는다
   - → Task 8 `이전_응답이_남아_있는_동안은_링크를_그리지_않는다`

---

## 파일 구조

**back-end** (`.worktrees/back-end-investment-split`, 브랜치 `feat/investment-pnl-split`)

| 파일 | 책임 |
|---|---|
| `src/main/java/com/stockproject/portfolio/api/dto/AssetChangeData.java` | `InvestmentPnl`에 `realizedPeriod` · `realizedLinkAvailable` |
| `src/main/java/com/stockproject/portfolio/view/InvestmentSplit.java` (신규) | 나눌지 · 두 몫 · 링크 판정(DB 없음) |
| `src/main/java/com/stockproject/portfolio/query/InvestmentSplitMapper.java` · `src/main/resources/mapper/InvestmentSplitMapper.xml` (신규) | 계좌별 판정 재료 · 구간 안 매도 |
| `src/main/java/com/stockproject/portfolio/query/SplitAccountRow.java` · `SpanSellRow.java` (신규) | 매퍼 행 |
| `src/main/java/com/stockproject/portfolio/view/AssetChangeViewService.java` | 분해 연결 · 트랜잭션 |
| `src/main/resources/db/sample/sample_split.sql` (신규) | 확정 · 평가로 나눠지는 덧씌움 |
| `src/test/resources/golden/asset-change.json` | 새 필드 두 개 |
| `src/test/java/com/stockproject/portfolio/view/InvestmentSplitTest.java` (신규) | 단위 |
| `src/test/java/com/stockproject/portfolio/query/InvestmentSplitMapperTest.java` (신규) | 매퍼(DB) |
| `src/test/java/com/stockproject/portfolio/api/InvestmentSplitApiTest.java` (신규) · `AssetChangeApiTest.java` | API(DB) |

**front-end** (`.worktrees/front-end-investment-split`, 브랜치 `feat/investment-pnl-split`)

| 파일 | 책임 |
|---|---|
| `src/api/types.ts` | `investment_pnl.realized_period` · `realized_link_available` |
| `src/fixtures/golden/asset-change.json` | 서버 골든과 같게 |
| `src/api/queries/useAssetChange.ts` | 자리표시 여부를 낸다 |
| `src/app/navigation/types.ts` | `'realized-pnl'`에 `account` |
| `src/screens/assetChange/AssetChangeScreen.tsx` · `SplitBlock.tsx` | 링크가 구간 · 계좌를 싣고, 열 수 없거나 자리표시면 감춘다 |
| `src/screens/realizedPnl/RealizedPnlScreen.tsx` | 받은 계좌로 필터를 건다 |
| `src/testing/renderWithNavigation.tsx` | 첫 라우트 파라미터 |
| `src/__tests__/assetChange.test.tsx` · `realizedPnl.test.tsx` | 테스트 |

---

## 픽스처 수치

**기본 샘플(`sample_portfolio.sql`)은 바꾸지 않는다.** 기존 테스트 · 골든 숫자는 그대로다.
- 이 샘플에는 체결 커버리지 행이 없고, 07-27 잔고는 확정 전이다
- 그래서 어느 기간 · 어느 계좌도 나눠지지 않는다(PF7-11 로컬 동작)

**덧씌움 `sample_split.sql`** — 기본 샘플 뒤에 얹는다.
- 사용자 `yhr`(`40000000-…-0001`)의 `국내주식` 계좌(`20000000-…-0002`, `ar_2b8e05da`)에만 넣는다
  - 2026-07-23 확정 잔고: 07-24 줄 복사(NAVER 40주 · 현금 1,000,000, `is_final = true`, 이월 아님)
  - 체결 커버리지: 2026-01-01 ~ 2026-07-24, `computed_at = 2026-07-24T23:30:00+09`
  - 생성기 처리 기록: 2026-07-24 `BUILT`, `built_at = 2026-07-24T23:40:00+09`

덧씌움 위에서 `yhr`가 보는 것:

| 요청 | 기초 · 기말 | 판정 대상 계좌 | 결과 |
|---|---|---|---|
| `CUSTOM 2026-07-01 ~ 2026-07-24` | 07-23(대체) · 07-24 | `국내주식`만. 다른 계좌는 07-24 하루뿐이라 대상이 아니고, 편입으로 들어간다 | 나눔. `total = 0` · `realized = 0` · `unrealized_change = 0`. 뷰 집합(7월) = 확정 집합 = ∅ → `realized_period = null` · `realized_link_available = true` |
| `CUSTOM 2026-01-01 ~ 2026-07-24` | 같음 | 같음 | 나눔. 뷰 집합 = {T-0001, T-0002, T-0003} ≠ ∅. 구간 07-24 ~ 07-24로는 ∅ = ∅ → `realized_period = { 2026-07-24, 2026-07-24 }` · 링크 있음 |
| `CUSTOM 2026-07-01 ~ 2026-07-31` | 07-23 · 07-27(확정 전) | `국내주식` 외 여럿 | 못 나눔(07-27 `BUILT` 없음 · 위탁 계좌 커버리지 없음 · 외화) |

- `국내주식`의 07-23 · 07-24 평가금액이 같아 투자손익은 0이다
- T-0003(02-18 `VERIFIED`)과 T-0004(04-01 `CONFLICT`)는 견준 구간 밖이다
- 뷰 집합에는 합계에 들어가는 `VERIFIED` · `SEEDED`만 든다. 그래서 T-0004는 들지 않는다

---

### Task 1: 응답 모양 — `realized_period` · `realized_link_available`

**파일:**
- 고침: `…/api/dto/AssetChangeData.java`
- 고침: `…/view/AssetChangeViewService.java`(생성자 호출 두 곳)
- 고침: `src/test/resources/golden/asset-change.json`

**인터페이스:**
```java
public record InvestmentPnl(BigDecimal total, BigDecimal realized, BigDecimal unrealizedChange,
                            boolean splitAvailable, PeriodDto realizedPeriod,
                            boolean realizedLinkAvailable) {}
```
- `PeriodDto`는 같은 파일의 기존 `PeriodDto(from, to)`를 쓴다
- 직렬화는 전역 `SNAKE_CASE` · `always` 설정을 따른다

- [ ] **Step 1: 실패하는 테스트** — 골든 `asset-change.json`의 `investment_pnl`에 `"realized_period" : null`, `"realized_link_available" : false`를 더한다. `SixViewGoldenTest`가 `NON_EXTENSIBLE`로 견주므로 응답에 필드가 없으면 깨진다.
- [ ] **Step 2: DB 테스트 실행해 실패 확인** — `--tests '*SixViewGoldenTest'`.
- [ ] **Step 3: 구현** — 레코드에 필드를 더한다. 서비스 두 곳(`render` · `emptyEnvelope`)은 `null` · `false`를 넘긴다.
- [ ] **Step 4: 통과 확인.**
- [ ] **Step 5: 커밋** — `feat: 자산 변화 응답에 확정을 센 구간과 실현손익 링크 여부 자리를 둔다`

---

### Task 2: 분해 판정 — `InvestmentSplit` (DB 없음)

**파일:**
- 만듦: `…/view/InvestmentSplit.java`, `…/query/SplitAccountRow.java`, `…/query/SpanSellRow.java`
- 테스트: `src/test/java/com/stockproject/portfolio/view/InvestmentSplitTest.java`

**인터페이스:**
```java
// query 패키지
public record SplitAccountRow(UUID accountId, boolean tradeCovered, boolean built,
                              boolean foreignHeld, boolean carriedBoundary) {}
public record SpanSellRow(String tradeId, Grade grade, BigDecimal realizedPnlKrw) {}

// view 패키지
final class InvestmentSplit {
    /**
     * accounts: 견준 구간에 잔고 구간이 있는 계좌 전부. sells: 그 구간 안에 판 체결 전부.
     * viewedInPeriod: 요청 기간 · 같은 필터로 실현손익 뷰가 합계에 넣을 체결.
     * viewedInWindow: 확정을 센 구간(기초 다음 날 ~ 기말) · 같은 필터로 실현손익 뷰가 합계에 넣을 체결.
     */
    static AssetChangeData.InvestmentPnl decide(BigDecimal total, List<SplitAccountRow> accounts,
                                                List<SpanSellRow> sells, Set<String> viewedInPeriod,
                                                Set<String> viewedInWindow,
                                                LocalDate opening, LocalDate closing) { … }
}
```

규칙:
1. `accounts`가 비면 나누지 않는다.
2. 한 계좌라도 다음 중 하나면 나누지 않는다: `!tradeCovered`, `!built`, `foreignHeld`, `carriedBoundary`.
3. 한 매도라도 등급이 `VERIFIED` · `SEEDED`가 아니면 나누지 않는다.
4. 나누지 않으면 `InvestmentPnl(total, null, null, false, null, false)`다.
5. 나누면 두 몫은 이렇다.
   - `realized = Σ realizedPnlKrw`
   - `unrealizedChange = total − realized`
6. 링크는 확정 체결 집합 `C`(`sells`의 체결 ID)로 정한다.
   - `C = viewedInPeriod`면 `realizedPeriod = null`, `realizedLinkAvailable = true`
   - 아니고 `C = viewedInWindow`면 `realizedPeriod = PeriodDto(opening + 1일, closing)`, `realizedLinkAvailable = true`
   - 그 밖이면 `realizedPeriod = null`, `realizedLinkAvailable = false`

- [ ] **Step 1: 실패하는 테스트**
  - `판정할_계좌가_없으면_나누지_않는다`
  - `체결_확보_구간이_덮지_않는_계좌가_하나라도_있으면_나누지_않는다`: 두 계좌 중 하나만 `tradeCovered = false`
  - `생성기가_처리하지_않은_계좌가_있으면_나누지_않는다`
  - `외화_종목을_가진_계좌가_있으면_나누지_않는다`
  - `구간_끝_잔고가_이월본인_계좌가_있으면_나누지_않는다`
  - `판정할_수_없는_매도가_있으면_나누지_않는다`: `UNAVAILABLE` 하나, `CONFLICT` 하나를 각각 넣어 본다
  - `나누지_않으면_두_몫과_구간을_비우고_링크도_없다`: `total`은 그대로다
  - `확정은_매도_실현손익_합이고_평가는_나머지다`: total −800,000, 매도 +120,000(`VERIFIED`) · −148,000(`SEEDED`) → realized −28,000, unrealized −772,000
  - `판_것이_없으면_확정은_0원이다`
  - `실현손익_뷰가_같은_체결을_세면_같은_기간으로_연다`
  - `같은_기간으로는_다르고_확정_구간으로는_같으면_그_구간으로_연다`: opening 07-24 · closing 07-27 → `2026-07-25 ~ 2026-07-27`
  - `어느_기간으로도_같은_체결을_셀_수_없으면_링크를_감춘다`: 두 뷰 집합 모두에 확정에 없는 체결이 있다. 분해(`split_available`)는 그대로 `true`다
- [ ] **Step 2: 실행해 실패 확인** — `./gradlew test --tests '*InvestmentSplitTest'`(DB 없음).
- [ ] **Step 3: 구현** — 위 규칙대로 쓴다. 클래스 주석에 두 가지를 풀어 쓴다.
  - 평가는 따로 구하지 않고 나머지로 둔다. 잔고 평단과 실현손익 원가는 출처가 달라, 따로 구하면 두 몫의 합이 투자손익과 어긋나고 그 차이를 설명할 수 없다
  - 링크를 감추는 경우가 있다. 연동 전에 판 체결처럼 투자손익에는 계좌 편입으로 들어간 매도를 실현손익 화면은 판 날짜로 세기 때문이다
- [ ] **Step 4: 통과 확인.**
- [ ] **Step 5: 커밋** — `feat: 투자손익을 확정과 평가로 나눌지와 실현손익 링크를 정하는 판정을 둔다`

---

### Task 3: 판정 재료 매퍼 — `InvestmentSplitMapper`

**파일:**
- 만듦: `…/query/InvestmentSplitMapper.java`, `src/main/resources/mapper/InvestmentSplitMapper.xml`
- 테스트: `src/test/java/com/stockproject/portfolio/query/InvestmentSplitMapperTest.java`

**인터페이스:**
```java
@Mapper interface InvestmentSplitMapper {
    List<SplitAccountRow> accounts(@Param("scope") UserScope scope, @Param("opening") LocalDate opening,
                                   @Param("closing") LocalDate closing, @Param("accountIds") Set<UUID> accountIds);
    List<SpanSellRow> sells(@Param("scope") UserScope scope, @Param("opening") LocalDate opening,
                            @Param("closing") LocalDate closing, @Param("accountIds") Set<UUID> accountIds,
                            @Param("zone") String zone);
}
```

- 두 질의 모두 `<include refid="com.stockproject.portfolio.query.EarningsCashflowMapper.span"/>`을 쓴다
  - 다른 namespace의 조각을 include하는 선례는 `EtfCoverageMapper.xml`에 있다
  - 이 조각은 계좌마다 `first_as_of` · `last_as_of`를 내고, 두 날이 같은 계좌는 뺀다

```sql
-- accounts
SELECT s.account_id,
       EXISTS (SELECT 1 FROM cln_trade_coverage c
                WHERE c.account_ref = s.account_ref
                  AND c.covered_from <= s.first_as_of + 1
                  AND c.covered_to   >= s.last_as_of)                       AS trade_covered,
       EXISTS (SELECT 1 FROM basis_build b JOIN cln_trade_coverage c ON c.account_ref = s.account_ref
                WHERE b.account_id = s.account_id
                  AND b.outcome = 'BUILT' AND b.as_of >= s.last_as_of
                  AND b.built_at >= c.computed_at)                          AS built,
       EXISTS (SELECT 1 FROM position_line p JOIN instrument i USING (instrument_id)
                WHERE p.account_id = s.account_id
                  AND p.as_of BETWEEN s.first_as_of AND s.last_as_of
                  AND i.currency <> 'KRW')                                  AS foreign_held,
       EXISTS (SELECT 1 FROM position_line p
                WHERE p.account_id = s.account_id
                  AND p.as_of IN (s.first_as_of, s.last_as_of)
                  AND p.is_carried_forward)                                 AS carried_boundary
  FROM (<span/>) s

-- sells
SELECT r.trade_id, r.grade, r.realized_pnl_krw
  FROM (<span/>) s JOIN realized_pnl_line r ON r.account_id = s.account_id
 WHERE (r.sold_at AT TIME ZONE #{zone})::date >  s.first_as_of
   AND (r.sold_at AT TIME ZONE #{zone})::date <= s.last_as_of
```

XML 주석에 각 판정이 무엇을 막는지 쓴다.
- **커버리지**: 커버리지가 없으면 판 체결이 줄로 오지 않아 0원처럼 보인다.
- **생성기 처리**
  - 생성기는 처리하던 때의 커버리지 시작일부터 체결을 읽는다. 그래서 커버리지가 그 뒤에 다시 계산됐으면 넓어진 구간의 매도 줄이 아직 없을 수 있다.
  - 생성기는 확정된 잔고만 처리하므로, 기말이 확정 전이면 이 판정이 거짓이다.
- **외화**: 해외 체결은 받지 않는다.
- **이월**: 양 끝이 이월본이면 그 잔고가 언제의 것인지 모른다.
- 확보 구간의 양 끝은 배당 · 수수료 · 세금의 `covered` 질의와 같은 규칙으로 본다.

- [ ] **Step 1: 실패하는 테스트** (기본 샘플 위. 필요한 행은 테스트 안에서 넣는다)
  - `계좌마다_확보_구간과_생성기_처리와_외화_보유와_이월을_판정한다`
    - `국내주식`에 커버리지와 07-27 `BUILT`(커버리지 계산 뒤)를 넣는다 → (true, true, false, false)
    - `위탁` → (false, false, true, false)
    - `연금저축` → 이월 true
  - `확보_구간이_첫_잔고_다음_날부터_마지막_잔고까지_덮어야_확보다`
    - `covered_from = 07-25`면 확보다
    - `07-26`이면 미확보다
    - `covered_to = 07-26`이면 미확보다
  - `건너뛴_처리는_처리로_보지_않는다`: 07-27 `SKIPPED`(`CARRIED`)만 있으면 false. 07-28 `BUILT`면 true
  - `커버리지가_처리_뒤에_다시_계산됐으면_처리로_보지_않는다`: `built_at < computed_at`이면 false
  - `외화_예수금도_외화_보유다`: `연금저축`의 MSFT 줄을 지워도 USD 현금 줄 때문에 true
  - `매도는_계좌의_첫_잔고_다음_날부터_마지막_잔고까지_한국_날짜로_센다`
    - `국내주식`에 네 매도를 넣는다: `2026-07-24T23:59:00+09`(빠짐), `2026-07-24T15:30:00Z`(서울 07-25, 듦), `2026-07-27T15:00:00+09`(듦), `2026-07-28T09:00:00+09`(빠짐)
  - `잔고가_하루뿐인_계좌는_대상이_아니다`: `hhj` 계좌 `…0007` → 두 질의 모두 빈 목록
  - `남의_계좌와_필터_밖_계좌는_읽지_않는다`
- [ ] **Step 2: DB 테스트 실행해 실패 확인** — `--tests '*InvestmentSplitMapperTest'`.
- [ ] **Step 3: 매퍼 작성.**
- [ ] **Step 4: 통과 확인.**
- [ ] **Step 5: 커밋** — `feat: 확정 · 평가 분해의 판정 재료와 구간 안 매도를 읽는 매퍼를 둔다`

---

### Task 4: 덧씌움 샘플 — `sample_split.sql`

**파일:**
- 만듦: `src/main/resources/db/sample/sample_split.sql`

**내용:** `sample_lookthrough.sql`과 같은 머리 모양으로 쓴다.
- 머리: `SET search_path = app, data;`, `BEGIN;` … `COMMIT;`
- 머리 주석에 쓸 것
  - 기본 샘플 뒤에 얹는다
  - 확정된 잔고 쌍으로 확정 · 평가가 나눠지는 계좌 하나를 재현한다
  - 기본 샘플의 07-27 잔고는 확정 전이라 생성기 처리 기록이 생길 수 없다. 그래서 07-23 · 07-24 쌍을 쓴다
- 넣는 행
```sql
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT '2026-07-23', account_id, instrument_id, quantity,
       cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
       fx_rate, '2026-07-23', '2026-07-23T15:30:00+09', false, true
  FROM position_line
 WHERE as_of = '2026-07-24' AND account_id = '20000000-0000-0000-0000-000000000002';

INSERT INTO cln_trade_coverage (account_ref, covered_from, covered_to, is_definitive, empty_streak, computed_at)
VALUES ('ar_2b8e05da', DATE '2026-01-01', DATE '2026-07-24', false, 0, '2026-07-24T23:30:00+09');

INSERT INTO basis_build (account_id, as_of, outcome, reason, built_at)
VALUES ('20000000-0000-0000-0000-000000000002', DATE '2026-07-24', 'BUILT', NULL, '2026-07-24T23:40:00+09');
```
- 기본 샘플의 `TRUNCATE` 목록에 `cln_trade_coverage`를 더한다. 그래야 덧씌움을 얹은 뒤 기본 샘플을 다시 부어도 행이 남지 않는다. 기본 샘플의 다른 내용은 바꾸지 않는다.
- 로컬은 `BASIS_ENABLED` 기본값이 false다. 그래서 생성기가 이 행을 보고 다시 계산하지 않는다.

- [ ] **Step 1: 덧씌움 작성, 기본 샘플 비우는 목록 수정.**
- [ ] **Step 2: DB 테스트로 회귀 확인** — `--tests '*AssetChangeApiTest' --tests '*SixViewGoldenTest' --tests '*UserScopeIsolationTest' --tests '*RealizedPnlApiTest'`. 숫자가 바뀌는 테스트가 없어야 한다.
- [ ] **Step 3: 커밋** — `test: 확정 · 평가로 나눠지는 덧씌움 샘플을 둔다`

---

### Task 5: 서비스 연결과 한 시점 조회

**파일:**
- 고침: `…/view/AssetChangeViewService.java`
- 만듦: `src/test/java/com/stockproject/portfolio/api/InvestmentSplitApiTest.java`. `@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_split.sql"})`을 단다
- 고침: `src/test/java/com/stockproject/portfolio/api/AssetChangeApiTest.java`(트랜잭션 테스트 하나)

**내용:**
- 생성자에 `InvestmentSplitMapper` · `RealizedPnlMapper`를 받는다.
- `render`에서 `investmentPnl`을 계산한 뒤 다음을 한다.
  ```java
  List<SplitAccountRow> splitAccounts = split.accounts(scope, openingAsOf, closingAsOf, filter.accountIds());
  List<SpanSellRow> sells = split.sells(scope, openingAsOf, closingAsOf, filter.accountIds(), zone.getId());
  Set<String> inPeriod = viewed(scope, resolved.from(), resolved.to(), filter);
  Set<String> inWindow = viewed(scope, openingAsOf.plusDays(1), closingAsOf, filter);
  InvestmentPnl pnl = InvestmentSplit.decide(investmentPnl, splitAccounts, sells, inPeriod, inWindow,
          openingAsOf, closingAsOf);
  ```
  - `viewed`는 `realized.findByPeriod(…)`에서 `includedInTotal`인 행의 `tradeId` 집합이다. 실현손익 화면과 같은 매퍼 · 같은 합계 포함 규칙을 쓰려는 것이다.
  - 기초와 기말이 같은 날이면 판정 대상 계좌가 없으므로 뷰 집합 질의를 건너뛴다.
- `render`에 `@Transactional(readOnly = true, isolation = Isolation.REPEATABLE_READ)`를 단다.
  - 주석: 한 응답의 질의가 모두 같은 시점의 표를 봐야 투자손익 · 확정 · 경고가 서로 맞는다. 기본 격리 수준에서는 질의마다 새 시점을 본다.
- `emptyEnvelope`는 그대로 `false`다.

- [ ] **Step 1: 실패하는 테스트** (`InvestmentSplitApiTest`)
  - `확정된_잔고_쌍이면_확정과_평가로_나눈다`
    - 요청: `CUSTOM 07-01 ~ 07-24`
    - 기대: `split_available = true`, `realized = 0`, `unrealized_change = 0`, `realized_period = null`, `realized_link_available = true`
  - `매도가_있으면_확정에_넣고_항등식은_그대로다`
    - `국내주식`에 `2026-07-24T10:00:00+09` `VERIFIED` 매도(실현 +50,000)를 넣는다
    - 기대: `realized = 50000`, `realized + unrealized_change = total`, 기말 = 기초 + 넣은 돈 + 번 돈 ± 편입 · 제외
    - 같은 기간의 `/portfolio/views/realized-pnl` 합계가 50,000이다
  - `실현손익_뷰가_같은_기간으로_다른_체결을_세면_확정_구간을_싣는다`
    - 요청: `CUSTOM 2026-01-01 ~ 2026-07-24`
    - 기대: `realized_period = { "from": "2026-07-24", "to": "2026-07-24" }`, 링크 있음
    - 그 구간으로 연 실현손익 합계가 `realized`와 같다
  - `연동_날_판_체결이_있으면_나누되_링크를_감춘다`
    - `위탁` 계좌(07-24 하루뿐이라 대상 아님)에 `2026-07-24T10:00:00+09` `VERIFIED` 매도를 넣는다
    - 요청: `CUSTOM 07-01 ~ 07-24`
    - 기대: `split_available = true`, `realized = 0`, `realized_link_available = false`, `realized_period = null`
  - `판정할_수_없는_매도가_끼면_나누지_않는다`: `국내주식`에 07-24 `CONFLICT` 매도를 넣는다 → `false`
  - `기말이_확정_전이면_나누지_않는다`: `CUSTOM 07-01 ~ 07-31`(기말 07-27) → `false`
  - `국내주식만_걸어도_기말이_확정_전이면_나누지_않는다`: 같은 기간, `account=…0002` → `false`
- [ ] **Step 2: 실패하는 테스트** (`AssetChangeApiTest`)
  - `응답_조회는_한_시점을_보는_읽기_전용_트랜잭션이다`: `render`의 `@Transactional`이 `readOnly = true` · `REPEATABLE_READ`인지 리플렉션으로 본다
  - 기존 `자산이_늘었는데_손실인_경우를_드러낸다`는 그대로 `false`여야 한다(PF7-11)
- [ ] **Step 3: DB 테스트 실행해 실패 확인** — `--tests '*InvestmentSplitApiTest' --tests '*AssetChangeApiTest'`.
- [ ] **Step 4: 구현.**
- [ ] **Step 5: 통과 확인.**
- [ ] **Step 6: 커밋** — `feat: 자산 변화가 거래 원장으로 셀 수 있는 기간에 투자손익을 확정과 평가로 나눈다`

---

### Task 6: 백엔드 전체 회귀

- [ ] **Step 1:** 전체를 돌린다(DB, 사전 승인): `TEST_DB_URL='…portfolio_test_investment_split…' ./gradlew test --rerun-tasks`.
- [ ] **Step 2:** 실패가 있으면 원인을 보고한다. 이 작업 때문이면 고친다.

---

### Task 7: 앱 타입과 골든

**파일:**
- 고침: `src/api/types.ts`, `src/fixtures/golden/asset-change.json`, `src/__tests__/assetChange.test.tsx`(`SPLIT` 픽스처)

**내용:**
- `investment_pnl`에 두 필드를 더한다
  - `realized_period: { from: string; to: string } | null;`
  - `realized_link_available: boolean;`
- 골든은 서버 골든과 바이트 단위로 같게 맞춘다.
- `SPLIT` 픽스처에 `realized_period: null` · `realized_link_available: true`를 더한다.

- [ ] **Step 1:** 타입을 먼저 바꾸고 `npx tsc --noEmit`이 픽스처에서 실패하는지 본다.
- [ ] **Step 2:** 골든 · 픽스처를 맞춘다. `npx tsc --noEmit` · `npx jest`가 통과해야 한다.
- [ ] **Step 3: 커밋** — `feat: 자산 변화 응답 타입에 확정 구간과 실현손익 링크 여부를 더한다`

---

### Task 8: `실현손익 뷰 →`가 구간과 계좌를 싣고, 열 수 없으면 감춘다

**파일:**
- 고침: `src/api/queries/useAssetChange.ts`, `src/app/navigation/types.ts`, `src/screens/assetChange/AssetChangeScreen.tsx`, `src/screens/assetChange/SplitBlock.tsx`
- 테스트: `src/__tests__/assetChange.test.tsx`

**인터페이스:**
```ts
// useAssetChange 반환값에 더한다
placeholder: result.isPlaceholderData,

// navigation/types.ts
'realized-pnl': { period?: PeriodValue; account?: string[] } | undefined;

// SplitBlock — onOpenRealized가 null이면 링크를 그리지 않는다
onOpenRealized: (() => void) | null;
```

링크:
```ts
const pnl = data.investment_pnl;
const canOpen = pnl.realized_link_available && !placeholder;
onOpenRealized={canOpen ? () => navigation.navigate('tabs', {
  screen: 'realized-pnl',
  params: {
    period: pnl.realized_period
      ? { period: 'CUSTOM', from: pnl.realized_period.from, to: pnl.realized_period.to }
      : period,
    account: accountIds,
  },
}) : null}
```
- `accountIds`는 이 화면이 요청에 쓰는 펼친 계좌 ID다. `넣은 돈 입력 →`과 같은 값이다.
- 주석으로 링크가 바뀌는 두 경우를 쓴다.
  - 확정을 센 구간이 따로 오면, 같은 기간으로는 실현손익 화면이 다른 체결을 센다는 뜻이다. 그 구간을 지정 기간으로 넘겨야 연 화면의 합계가 확정 줄과 같다.
  - 서버가 링크를 열 수 없다고 하거나 이전 응답이 남아 있는 동안에는 링크를 그리지 않는다.
- `TabParamList`의 `'realized-pnl'` 주석은 "기간과 계좌를 들고 온다"로 고친다.

- [ ] **Step 1: 실패하는 테스트**
  - 기존 `실현손익 뷰 →가 지금 기간을 들고 간다`의 기대를 `{ screen: 'realized-pnl', params: { period: { period: 'LAST_YEAR' }, account: [] } }`로 고친다
  - `실현손익 뷰 →가 걸어 둔 계좌를 들고 간다`: 필터 시트에서 계좌 하나를 고르고 새 응답이 온 뒤 누르면 `account: ['<그 계좌 ID>']`가 실린다. 고르는 절차는 `계좌를 걸면 옮긴 돈에 대한 각주가 붙는다`와 같게 한다
  - `확정을_센_구간이_따로_오면_그_구간을_지정_기간으로_넘긴다`: `SPLIT`에 `realized_period: { from: '2026-07-25', to: '2026-07-27' }`을 넣으면 `period: { period: 'CUSTOM', from: '2026-07-25', to: '2026-07-27' }`
  - `열_수_없다고_하면_확정과_평가만_보이고_링크는_없다`: `realized_link_available: false`면 `확정` · `평가` 줄은 있고 `실현손익 보기` 링크는 없다
  - `이전_응답이_남아_있는_동안은_링크를_그리지_않는다`: 필터를 바꾼 직후, 새 응답이 오기 전에는 링크가 없다. 응답을 늦게 돌려주는 `serve`를 쓴다
- [ ] **Step 2:** `npx jest src/__tests__/assetChange.test.tsx`로 실패를 확인한다.
- [ ] **Step 3: 구현.**
- [ ] **Step 4: 통과 확인.**
- [ ] **Step 5: 커밋** — `feat: 실현손익 뷰 링크가 확정을 센 구간과 계좌 필터를 들고 가고 열 수 없으면 감춘다`

---

### Task 9: 실현손익 화면이 받은 계좌로 연다

**파일:**
- 고침: `src/testing/renderWithNavigation.tsx`, `src/screens/realizedPnl/RealizedPnlScreen.tsx`
- 테스트: `src/__tests__/realizedPnl.test.tsx`

**내용:**
- `renderWithNavigation`에 `initialParams?: object` 옵션을 더한다. 테스트 대상 화면 라우트의 첫 파라미터로 넘긴다. 기존 호출은 바꾸지 않는다.
- 기간을 받는 기존 `useEffect` 옆에, `PositionsScreen`과 같은 방식으로 계좌용 효과를 둔다.
```ts
useEffect(() => {
  const requested = route.params?.account;
  if (!requested) return;
  setSelection({ account_type: [], account: requested });
  navigation.setParams({ account: undefined });
}, [route.params?.account, navigation]);
```
- 종목별 화면과 달리, 받은 값으로 선택 전체를 바꾼다. 빈 목록이 오면 필터를 푼다. 자산 변화가 전체 계좌로 보고 있었으면 실현손익도 전체여야 합계가 확정과 같다.

- [ ] **Step 1: 실패하는 테스트**
  - `자산 변화에서 넘어온 계좌로 걸어 연다`
    - `initialParams: { account: ['<CATALOG에 있는 계좌 ID>'] }`
    - 기대: 마지막 요청 URL에 `account=<그 ID>`가 붙고, 칩이 `계좌 1 ▾`
    - 첫 요청은 기본값으로 나갈 수 있으므로 마지막 요청으로 본다
  - `빈 계좌 목록으로 넘어오면 걸어 둔 필터를 푼다`
    - 계좌를 걸어 둔 상태에서 `account: []`로 다시 들어온다
    - 기대: 마지막 요청에 `account`가 없고, 칩이 `전체 계좌 ▾`
- [ ] **Step 2:** 실패를 확인한다.
- [ ] **Step 3: 구현.**
- [ ] **Step 4:** `npx jest` · `npx tsc --noEmit` 전체를 통과시킨다.
- [ ] **Step 5: 커밋** — `feat: 실현손익 화면이 자산 변화에서 넘어온 계좌 필터로 열린다`

---

## 끝날 때 보고

- 바뀐 파일(백엔드 · 앱 · 문서), 테스트 결과(전체 실행 결과 수치).
- 골든 `asset-change.json`이 바뀐 이유: `investment_pnl`에 `realized_period` · `realized_link_available` 필드가 생겼다. 기본 샘플 7월은 나눠지지 않아 값은 `null` · `false`이고, 다른 숫자는 그대로다.
- 남은 것
  - 두 잔고 사이에 사서 다 판 해외 종목은 확정 대신 평가에 섞인다(스펙에 적은 한계). KIS가 이때 외화 예수금 줄을 남기는지는 확인하지 않았다.
  - 청산된 포지션의 매도 줄은 생성기가 고정한다. 늦게 온 정정은 확정에 반영되지 않는다.
  - 실현손익 매퍼는 시간대를 `'Asia/Seoul'`로 고정했고, 이 작업의 매퍼는 설정값(`portfolio.zone`)을 쓴다. 지금은 같은 값이다.
  - 커버리지 계산 시각 조건 때문에 데이터팀 적재가 생성기 뒤에 돌면 분해가 하루씩 꺼질 수 있다. 실제 순서는 확인하지 않았다.
  - 이번 달 분해는 기말이 확정되고 생성기가 처리할 때까지(동기화 뒤 밤 ~ 다음 날 아침) 나오지 않는다.
- 영향받는 케이스 · 결함
  - **PF7-09**: 유보에서 돌릴 수 있다. 로컬은 기본 샘플에 `sample_split.sql`을 얹고, `yhr`가 지정 기간 07-01 ~ 07-24로 본다. 이때 링크가 같은 기간으로 열린다. 기대 결과의 `period=THIS_YEAR`는 테스트 트랙이 고쳐야 한다. 기본 샘플의 `올해`는 기말이 확정 전이라 나눠지지 않는다.
  - **PF7-11**: 기본 샘플 기준 동작이 그대로다. 문구도 같다.
  - **D-08**: 해결. 나눌 조건을 만족하는 기간에는 확정 · 평가와 링크가 그려진다. 운영 IRP는 커버리지가 없어 계속 나누지 않고, 이건 사실과 맞는 동작이다.
  - 새로 생길 수 있는 케이스
    - 계좌 필터를 들고 가는 링크
    - `realized_period`로 지정 기간을 여는 경우
    - 링크를 감추는 경우(연동 날 판 체결)
    - 기말이 확정 전이라 나누지 않는 경우
