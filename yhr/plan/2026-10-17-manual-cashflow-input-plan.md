# 입출금 입력 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자가 입출금을 넣고 지우는 API(`/portfolio/cashflows`)와 앱의 입출금 화면을 만들고, 자산 변화의 넣은 돈 · 미입력 경고 · 와이어플로우를 거기에 잇는다.

**Architecture:** 백엔드는 `com.stockproject.portfolio.cashflow` 패키지에 요청 해석(`CashflowRequestParser`) · 검증(`CashflowValidator`) · 쓰기 매퍼 · 서비스를 두고, 컨트롤러는 `api`에 둔다. 자산 변화와 목록이 같은 "견준 두 잔고"를 쓰도록 `view/SnapshotPairResolver`로 떼어 낸다. 앱은 스택 화면 `cashflows`를 React Query 조회 · 변경 훅으로 그리고, 저장 · 삭제 뒤 `['cashflows']` · `['asset-change']`를 무효화한다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · MyBatis(애너테이션 매퍼 + XML) · PostgreSQL 16 · JUnit 5 · AssertJ · MockMvc / React Native 0.81 · Expo SDK 54 · TanStack Query 5 · React Navigation 7 · jest-expo · Testing Library / Python 3 + Pillow(와이어플로우)

**Spec:** [`docs/yhr/specs/portfolio-management/2026-10-16-manual-cashflow-input-design.md`](../specs/portfolio-management/2026-10-16-manual-cashflow-input-design.md) (이하 "설계"). 상위 스펙은 [`2026-07-28-portfolio-management-spec.md`](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md), 화면 구조는 [`app-information-architecture.md`](../specs/app-information-architecture.md).

작업 위치는 셋이다.

| 부분 | 저장소 · 위치 | 브랜치 |
|---|---|---|
| A. 백엔드 (Task 1~7) | worktree `/Users/yhr/Dev/workspace/personal/stock-project/.worktrees/back-end-manual-cashflow` — `back-end`의 `feat/position-line-builder`(`ae2a2a9`)에서 딴다 | `feat/manual-cashflow-input` |
| B. 앱 (Task 8~12) | `/Users/yhr/Dev/workspace/personal/stock-project/front-end` — `main`에서 딴다 | `feat/manual-cashflow-input` |
| C. 와이어플로우 (Task 13) | `/Users/yhr/Dev/workspace/personal/stock-project/docs` — `main` | `main` |

A의 경로는 worktree 루트 기준, B는 `front-end/` 기준, C는 `docs/` 기준이다.

## Global Constraints

- 스펙 · 설계 · IA를 고치지 않는다. 구현이 막히거나 설계가 틀렸다고 보면 멈추고 보고한다.
- worktree 생성, 서버 · DB · 시뮬레이터 기동, DB 쓰기는 사용자 승인 후에 한다. 운영 DB에 쓰지 않는다.
- `./gradlew test`는 다른 세션과 테스트 DB를 공유한다. **DB를 쓰는 테스트(`@SpringBootTest`)는 돌리기 전에 매번 사용자에게 묻는다.** Spring 컨텍스트 · DB를 띄우지 않는 단위 테스트 클래스만 `--tests`로 돌릴 때는 묻지 않는다 — 실행 전에 그 클래스가 DB에 닿지 않는지 확인하고, 하나라도 섞이면 묻는다.
- 마이그레이션을 쓰지 않는다. V9는 이 작업이 쓰지 않는다.
- 테스트 먼저. 실패를 눈으로 확인한 뒤 구현한다.
- 커밋은 사용자가 요청할 때만 한다. 각 태스크 끝의 커밋 단계는 "요청받았을 때 이 메시지로"라는 뜻이다. 메시지는 한국어, 접두 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝에 아래 두 줄.
  ```
  Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01QmLK3wbDUKJ4Zb9qhAqmZN
  ```
- 주석 · 문서는 히스토리 없이 최신 사실만. 검증하지 않은 것을 단정하지 않는다. 주석 밀도와 어조는 주변 코드(`view` · `query` · `screens/assetChange`)를 따른다.
- 계좌번호 · 자격증명을 코드 · 로그 · 테스트 데이터에 넣지 않는다.
- SQL은 스키마를 붙이지 않는다(`currentSchema=app,data`).
- 문구는 설계 그대로 쓴다. 경고 문구 셋은 `N개 계좌에 이 기간 입출금이 입력되지 않아 투자손익이 정확하지 않을 수 있어요` · `배당·수수료 내역이 확보되지 않아 투자손익이 정확하지 않을 수 있어요` · `N개 계좌에 입출금이 입력되지 않았고 배당·수수료 내역도 없어 투자손익이 정확하지 않을 수 있어요`.
- 금액은 1 이상의 정수, 15자리 이하. 메모는 100자 이하. 통화는 `KRW`만.
- 앱은 Expo SDK 54를 넘는 의존성을 들이지 않는다. 새 패키지를 설치하지 않는다.
- `docs/hhj/` · `docs/jdh/` · `docs/team-architecture-agreement.md`를 근거로 쓰지 않는다.

## Review Focus

1. **자정~오전 9시(KST)의 "오늘"** — 서버가 UTC 시계로 오늘을 정하면 한국 날짜로 오늘인 입출금이 "오늘 이후"로 거부된다. 사용자는 한국 날짜 기준 오늘을 넣을 수 있어야 한다. → Task 2에 `2026-07-31T15:30Z`(KST 08-01)에서 08-01을 받는 테스트.
2. **금액 칸에 `2,000,000원`을 붙여넣거나 `007`처럼 앞에 0을 친 경우** — 숫자만 남겨 `2000000` · `7`로 보내야 한다. → Task 9에 붙여넣기 테스트.
3. **화면을 연 뒤 다른 곳에서 그 계좌를 해제한 경우** — 저장하면 서버의 `occurred_on` 칸 오류가 날짜 칸 아래에 떠야 한다. → Task 9의 칸 오류 테스트가 그 문장으로 확인한다.
4. **마지막 한 건을 지운 경우** — 목록이 빈 문구로 바뀌고 머리줄 건수가 0이어야 한다. → Task 10에 삭제 후 빈 목록 테스트.
5. **필터 계좌가 해제된 계좌인 채로 들어온 경우** — 그 계좌가 미리 선택되고 `해제됨` 배지가 보여야 한다. → Task 9에 해제 계좌 진입 테스트.

---

## 파일 구조

**A. 백엔드** (`src/main/java/com/stockproject/portfolio/` 아래)

| 파일 | 책임 |
|---|---|
| `view/SnapshotPair.java` | 견준 두 잔고 값 (생성) |
| `view/SnapshotPairResolver.java` | 기간 → 견준 두 잔고 (생성) |
| `view/AssetChangeViewService.java` | 위 둘을 쓰고, 계좌별 입출금 미입력 수를 센다 (수정) |
| `cashflow/CashflowType.java` | `DEPOSIT` · `WITHDRAW` (생성) |
| `cashflow/CashflowFieldError.java` | 칸 오류 한 건 (생성) |
| `cashflow/CashflowDraft.java` | 해석된 생성 요청 (생성) |
| `cashflow/ParsedCashflow.java` | 해석 결과 (생성) |
| `cashflow/CashflowRequestParser.java` | `JsonNode` → 초안 + 모양 오류 (생성) |
| `cashflow/AccountLineRange.java` | 계좌의 첫 · 마지막 잔고 날짜 (생성) |
| `cashflow/CashflowValidator.java` | 금액 · 통화 · 메모 · 날짜 범위 (생성) |
| `cashflow/InvalidCashflowException.java` | 칸 오류 → 400 (생성) |
| `cashflow/CashflowRow.java` | 목록 한 행 (생성) |
| `cashflow/CashflowList.java` | 목록 + 견준 두 잔고 (생성) |
| `cashflow/ManualCashflowWriteMapper.java` | insert · list · deleteOwned · lineRange (생성) |
| `cashflow/ManualCashflowService.java` | 생성 · 목록 · 삭제 (생성) |
| `api/CashflowController.java` | `/portfolio/cashflows` (생성) |
| `api/dto/CashflowIdResponse.java` · `CashflowListResponse.java` · `InvalidCashflowError.java` | 응답 (생성) |
| `api/ApiExceptionHandler.java` | `InvalidCashflowException` 처리 (수정) |
| `query/ManualCashflowMapper.java` · `resources/mapper/ManualCashflowMapper.xml` | `accountsWithEntries` (수정) |
| `view/assembly/AssemblyContext.java` · `NoticeCollector.java` · `NoticeCode.java` | 입출금 미입력 경고 (수정) |

테스트(`src/test/java/com/stockproject/portfolio/` 아래): `view/SnapshotPairResolverTest` · `cashflow/CashflowRequestParserTest` · `cashflow/CashflowValidatorTest` · `cashflow/CashflowTestClock` · `cashflow/ManualCashflowWriteMapperTest` · `api/CashflowApiTest` · `api/CashflowAssetChangeFlowTest` (생성), `auth/ScopeSignatureTest` · `view/assembly/NoticeCollectorTest` · `api/AssetChangeApiTest` · `resources/golden/asset-change.json` (수정).

**B. 앱** (`src/` 아래)

| 파일 | 책임 |
|---|---|
| `api/types.ts` · `api/endpoints.ts` · `api/queries/keys.ts` | 입출금 타입 · 요청 · 캐시 키 (수정) |
| `api/queries/useCashflows.ts` · `useCashflowActions.ts` · `cashflowInvalidation.ts` | 조회 · 저장 · 삭제 · 무효화 (생성) |
| `screens/cashflows/form.ts` | 폼 상태 · 기본값 · 금액 정리 · 요청 변환 (생성) |
| `screens/cashflows/windowNote.ts` | 날짜가 넣은 돈 구간 밖인지 알리는 문구 (생성) |
| `screens/cashflows/AccountPickerSheet.tsx` | 계좌 하나 고르기 (생성) |
| `screens/cashflows/CashflowForm.tsx` | 입력 폼 (생성) |
| `screens/cashflows/CashflowList.tsx` | 기간 목록 · 삭제 (생성) |
| `screens/cashflows/CashflowsScreen.tsx` | 화면 (생성) |
| `app/navigation/types.ts` · `app/navigation/RootStack.tsx` | `cashflows` 라우트 (수정) |
| `screens/assetChange/FlowList.tsx` · `AssetChangeScreen.tsx` | `넣은 돈 입력 →` · 0원 그룹 (수정) |
| `fixtures/golden/asset-change.json` | 백엔드 골든과 같게 (수정) |

테스트(`src/__tests__/`): `cashflowApi.test.tsx` · `cashflowForm.test.ts` · `cashflows.test.tsx` · `cashflowFlow.test.tsx` (생성), `assetChange.test.tsx` (수정).

**C. 와이어플로우**: `yhr/specs/portfolio-management/wireflow_src.py` (수정) → `wireflow.png` · `wireflow.drawio` (재생성).

---

## A. 백엔드

### Task 0: worktree 준비 (사용자 승인 후)

- [ ] **Step 1: 경로를 알리고 승인받는다**

`/Users/yhr/Dev/workspace/personal/stock-project/.worktrees/back-end-manual-cashflow`에 `back-end`의 `ae2a2a9`에서 브랜치 `feat/manual-cashflow-input`을 딴 worktree를 만든다고 알린다. 승인 전에는 아무것도 만들지 않는다.

- [ ] **Step 2: 만든다**

```bash
git -C /Users/yhr/Dev/workspace/personal/stock-project/back-end worktree add \
  -b feat/manual-cashflow-input \
  /Users/yhr/Dev/workspace/personal/stock-project/.worktrees/back-end-manual-cashflow ae2a2a9
git -C /Users/yhr/Dev/workspace/personal/stock-project/.worktrees/back-end-manual-cashflow log --oneline -1
```

Expected: `ae2a2a9 fix: 이후 날짜 잠금의 대기 순환을 주석에 사실대로 적는다`

---

### Task 1: 견준 두 잔고 — `SnapshotPairResolver`

자산 변화 서비스 안에 있던 기초 · 기말 선택을 떼어 낸다. 목록 API(Task 5)와 미입력 판정(Task 7)이 같은 계산을 쓴다. 동작은 바뀌지 않는다.

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/view/SnapshotPair.java`
- Create: `src/main/java/com/stockproject/portfolio/view/SnapshotPairResolver.java`
- Modify: `src/main/java/com/stockproject/portfolio/view/AssetChangeViewService.java`
- Test: `src/test/java/com/stockproject/portfolio/view/SnapshotPairResolverTest.java`

**Interfaces:**
- Consumes: `SnapshotCalendarRepository.latestBefore` · `earliestOnOrAfter` · `latestOnOrBefore` (기존)
- Produces: `record SnapshotPair(LocalDate opening, LocalDate closing, boolean openingSubstituted)` + `boolean emptyWindow()`; `SnapshotPairResolver.resolve(UserScope scope, LocalDate from, LocalDate to): Optional<SnapshotPair>`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.view;

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

/**
 * 자산 변화가 견주는 두 잔고. 넣은 돈은 그 사이에서 센다.
 * 샘플: yhr의 계좌는 07-24 · 07-27에, hhj의 계좌는 07-27에만 잔고가 있다.
 */
@SpringBootTest
@ActiveProfiles("test")
@Sql("classpath:db/sample/sample_portfolio.sql")
class SnapshotPairResolverTest {

    private static final LocalDate JULY_1 = LocalDate.of(2026, 7, 1);
    private static final LocalDate JULY_31 = LocalDate.of(2026, 7, 31);

    @Autowired SnapshotPairResolver resolver;
    @Autowired JdbcClient jdbc;

    @Test
    void 기간_시작_전_잔고가_없으면_기간_안의_가장_이른_잔고로_대신한다() {
        SnapshotPair pair = resolver.resolve(scope("yhr"), JULY_1, JULY_31).orElseThrow();

        assertThat(pair.opening()).isEqualTo(LocalDate.of(2026, 7, 24));
        assertThat(pair.closing()).isEqualTo(LocalDate.of(2026, 7, 27));
        assertThat(pair.openingSubstituted()).isTrue();
        assertThat(pair.emptyWindow()).isFalse();
    }

    @Test
    void 기간_시작_전_잔고가_있으면_그것이_기초다() {
        SnapshotPair pair = resolver.resolve(scope("yhr"),
                LocalDate.of(2026, 8, 1), LocalDate.of(2026, 8, 31)).orElseThrow();

        assertThat(pair.opening()).isEqualTo(LocalDate.of(2026, 7, 27));
        assertThat(pair.closing()).isEqualTo(LocalDate.of(2026, 7, 27));
        assertThat(pair.openingSubstituted()).isFalse();
        assertThat(pair.emptyWindow()).isTrue();
    }

    @Test
    void 잔고가_하루뿐이면_구간이_빈다() {
        SnapshotPair pair = resolver.resolve(scope("hhj"), JULY_1, JULY_31).orElseThrow();

        assertThat(pair.opening()).isEqualTo(pair.closing());
        assertThat(pair.emptyWindow()).isTrue();
    }

    @Test
    void 기간_끝까지_잔고가_없으면_고르지_않는다() {
        assertThat(resolver.resolve(scope("yhr"),
                LocalDate.of(2026, 6, 1), LocalDate.of(2026, 6, 30))).isEmpty();
        assertThat(resolver.resolve(scope("test_empty"), JULY_1, JULY_31)).isEmpty();
    }

    private UserScope scope(String user) {
        return new UserScope(jdbc.sql("SELECT id FROM app_user WHERE email = :email")
                .param("email", user + "@a.com").query(UUID.class).single());
    }
}
```

- [ ] **Step 2: 실패를 확인한다** (사용자 승인 후)

Run: `./gradlew test --tests 'com.stockproject.portfolio.view.SnapshotPairResolverTest'`
Expected: 컴파일 실패 — `SnapshotPairResolver`가 없다.

- [ ] **Step 3: 구현한다**

`view/SnapshotPair.java`:

```java
package com.stockproject.portfolio.view;

import java.time.LocalDate;

/**
 * 기간을 견줄 두 잔고.
 *
 * <p>넣은 돈은 그 사이 {@code (opening, closing]}에서 센다. 기초 잔고 날짜의 입금은 이미 그
 * 잔고에 들어 있어서다.</p>
 *
 * @param openingSubstituted 기간 시작 전 잔고가 없어 기간 안의 가장 이른 잔고로 대신했는지
 */
public record SnapshotPair(LocalDate opening, LocalDate closing, boolean openingSubstituted) {

    /** 기초와 기말이 같은 날이면 그 사이에 들어갈 날이 없다. */
    public boolean emptyWindow() { return !opening.isBefore(closing); }
}
```

`view/SnapshotPairResolver.java`:

```java
package com.stockproject.portfolio.view;

import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.query.SnapshotCalendarRepository;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.Optional;

/**
 * 기간 [from, to]를 어느 두 잔고로 견줄지 고른다. 자산 변화와 입출금 목록이 함께 쓴다 —
 * 목록이 "이 기간에 들어간다"고 표시한 입출금이 자산 변화의 넣은 돈에 실제로 들어가야 한다.
 */
@Component
public class SnapshotPairResolver {

    private final SnapshotCalendarRepository calendar;

    public SnapshotPairResolver(SnapshotCalendarRepository calendar) { this.calendar = calendar; }

    /**
     * 기초는 기간 시작 직전의 잔고다. 그런 잔고가 없으면 기간 안의 가장 이른 잔고로 대신한다.
     * 기말은 기간 끝 이하의 가장 늦은 잔고다. 둘 중 하나라도 없으면 견줄 수 없다.
     */
    public Optional<SnapshotPair> resolve(UserScope scope, LocalDate from, LocalDate to) {
        Optional<LocalDate> before = calendar.latestBefore(scope, from);
        LocalDate opening = before.orElseGet(() -> calendar.earliestOnOrAfter(scope, from).orElse(null));
        LocalDate closing = calendar.latestOnOrBefore(scope, to).orElse(null);

        if (opening == null || closing == null) return Optional.empty();
        return Optional.of(new SnapshotPair(opening, closing, before.isEmpty()));
    }
}
```

`view/AssetChangeViewService.java` — 생성자에 `SnapshotPairResolver pairs`를 받아 필드로 두고, `render`의 기초 · 기말 선택을 바꾼다.

```java
    public Envelope<AssetChangeData> render(UserScope scope, String period,
                                            LocalDate from, LocalDate to, LineFilter filter) {
        List<AccountRow> ownedAccounts = accounts.findAll(scope);
        LocalDate reference = calendar.latestAsOf(scope).orElse(LocalDate.now(zone));
        Period resolved = periods.resolve(period, from, to, reference);

        // 기초 잔고가 없어 대신 잡았으면 실제로 언제부터 계산했는지 화면에 알린다.
        Optional<SnapshotPair> pair = pairs.resolve(scope, resolved.from(), resolved.to());
        if (pair.isEmpty()) return emptyEnvelope(scope, resolved, ownedAccounts);

        LocalDate openingAsOf = pair.get().opening();
        LocalDate closingAsOf = pair.get().closing();

        BigDecimal opening = calendar.totalAssetsKrwAt(scope, openingAsOf, filter);
        BigDecimal closing = calendar.totalAssetsKrwAt(scope, closingAsOf, filter);
```

이 아래(`AccountBoundary boundary = …`부터)는 그대로 두고, `notices.collect(context(…))`의 다섯째 인자만 바꾼다.

```java
                notices.collect(context(scope, reference, ownedAccounts, earnedCash,
                        pair.get().openingSubstituted() ? openingAsOf : null,
                        openingAsOf, closingAsOf)));
```

생성자 시그니처:

```java
    public AssetChangeViewService(AccountRepository accounts, SnapshotCalendarRepository calendar,
                                  SnapshotPairResolver pairs,
                                  SnapshotFactsMapper facts, ManualCashflowMapper manualCashflow,
                                  EarningsCashflowPort earningsCashflow, PeriodResolver periods,
                                  NoticeCollector notices, EmptyReasonResolver emptyReasons,
                                  BannerAsOf bannerAsOf,
                                  @Value("${portfolio.zone}") String zone) {
```

`Optional` import는 이미 있다.

- [ ] **Step 4: 통과와 기존 동작 보존을 확인한다** (사용자 승인 후)

Run: `./gradlew test --tests 'com.stockproject.portfolio.view.SnapshotPairResolverTest' --tests 'com.stockproject.portfolio.api.AssetChangeApiTest' --tests 'com.stockproject.portfolio.api.SixViewGoldenTest'`
Expected: PASS. 자산 변화 테스트와 골든이 그대로 통과해야 옮김이 맞다.

- [ ] **Step 5: 커밋 (요청받았을 때)**

```bash
git add src/main/java/com/stockproject/portfolio/view/SnapshotPair.java \
        src/main/java/com/stockproject/portfolio/view/SnapshotPairResolver.java \
        src/main/java/com/stockproject/portfolio/view/AssetChangeViewService.java \
        src/test/java/com/stockproject/portfolio/view/SnapshotPairResolverTest.java
git commit -m "feat: 자산 변화가 견주는 두 잔고를 따로 고르게 한다"
```

---

### Task 2: 요청 해석과 칸 검증 — `CashflowRequestParser` · `CashflowValidator`

DB 없이 도는 순수 단위다. 해석은 모양(있나 · 형이 맞나 · 열거 안인가)만, 검증은 범위(금액 · 통화 · 메모 · 날짜)를 본다.

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/cashflow/CashflowType.java`
- Create: `src/main/java/com/stockproject/portfolio/cashflow/CashflowFieldError.java`
- Create: `src/main/java/com/stockproject/portfolio/cashflow/CashflowDraft.java`
- Create: `src/main/java/com/stockproject/portfolio/cashflow/ParsedCashflow.java`
- Create: `src/main/java/com/stockproject/portfolio/cashflow/CashflowRequestParser.java`
- Create: `src/main/java/com/stockproject/portfolio/cashflow/AccountLineRange.java`
- Create: `src/main/java/com/stockproject/portfolio/cashflow/CashflowValidator.java`
- Create: `src/main/java/com/stockproject/portfolio/cashflow/InvalidCashflowException.java`
- Test: `src/test/java/com/stockproject/portfolio/cashflow/CashflowRequestParserTest.java`
- Test: `src/test/java/com/stockproject/portfolio/cashflow/CashflowValidatorTest.java`

**Interfaces:**
- Produces:
  - `enum CashflowType { DEPOSIT, WITHDRAW }`
  - `record CashflowFieldError(String path, String code, String message)`
  - `record CashflowDraft(UUID accountId, CashflowType type, BigDecimal amount, String currency, LocalDate occurredOn, String memo)`
  - `record ParsedCashflow(CashflowDraft draft, UUID accountId, List<CashflowFieldError> errors)` — `accountId`는 해석에 성공했으면 다른 칸이 틀려도 채운다(소유 확인이 칸 오류보다 먼저다)
  - `CashflowRequestParser.parse(JsonNode body): ParsedCashflow` (정적)
  - `record AccountLineRange(LocalDate firstAsOf, LocalDate lastAsOf)` + `AccountLineRange.NONE`
  - `CashflowValidator(Clock clock)` · `validate(CashflowDraft draft, AccountLineRange range, LinkState linkState): List<CashflowFieldError>`
  - `InvalidCashflowException(List<CashflowFieldError> fields)` · `fields()`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`CashflowRequestParserTest.java`:

```java
package com.stockproject.portfolio.cashflow;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** 요청 JSON의 모양만 본다. 범위는 CashflowValidator 몫이다. */
class CashflowRequestParserTest {

    private static final ObjectMapper JSON = new ObjectMapper();
    private static final String ACCOUNT = "20000000-0000-0000-0000-000000000001";

    @Test
    void 온전한_요청을_초안으로_옮긴다() throws Exception {
        ParsedCashflow parsed = CashflowRequestParser.parse(json("""
                {"account_id": "%s", "type": "DEPOSIT", "amount": 2000000,
                 "currency": "KRW", "occurred_on": "2026-07-25", "memo": "  월급 이체 "}
                """.formatted(ACCOUNT)));

        assertThat(parsed.errors()).isEmpty();
        assertThat(parsed.draft()).isEqualTo(new CashflowDraft(UUID.fromString(ACCOUNT),
                CashflowType.DEPOSIT, new BigDecimal("2000000"), "KRW",
                LocalDate.of(2026, 7, 25), "월급 이체"));
    }

    @Test
    void 통화를_빼면_원화이고_빈_메모는_없는_것이다() throws Exception {
        ParsedCashflow parsed = CashflowRequestParser.parse(json("""
                {"account_id": "%s", "type": "WITHDRAW", "amount": 1,
                 "occurred_on": "2026-07-25", "memo": "   "}
                """.formatted(ACCOUNT)));

        assertThat(parsed.draft().currency()).isEqualTo("KRW");
        assertThat(parsed.draft().memo()).isNull();
    }

    @Test
    void 틀린_칸을_모두_모은다() throws Exception {
        ParsedCashflow parsed = CashflowRequestParser.parse(json("""
                {"account_id": "abc", "type": "DEPOSITE", "amount": "2000000",
                 "currency": 1, "occurred_on": "2026-02-30", "memo": 3}
                """));

        assertThat(parsed.draft()).isNull();
        assertThat(parsed.errors()).extracting(CashflowFieldError::path)
                .containsExactly("account_id", "type", "amount", "currency", "occurred_on", "memo");
        assertThat(parsed.errors()).extracting(CashflowFieldError::message).containsExactly(
                "계좌 값이 올바르지 않아요", "입금·출금 중에서 골라 주세요", "금액을 숫자로 입력해 주세요",
                "통화 값이 올바르지 않아요", "날짜는 YYYY-MM-DD로 입력해 주세요", "메모는 글자로 입력해 주세요");
    }

    @Test
    void 빠진_필수_칸을_알린다() throws Exception {
        ParsedCashflow parsed = CashflowRequestParser.parse(json("{}"));

        assertThat(parsed.errors()).extracting(CashflowFieldError::path, CashflowFieldError::code)
                .containsExactly(
                        org.assertj.core.groups.Tuple.tuple("account_id", "REQUIRED"),
                        org.assertj.core.groups.Tuple.tuple("type", "INVALID_VALUE"),
                        org.assertj.core.groups.Tuple.tuple("amount", "INVALID_TYPE"),
                        org.assertj.core.groups.Tuple.tuple("occurred_on", "REQUIRED"));
    }

    /** 소유 확인이 칸 오류보다 먼저다. 계좌만 읽혔으면 다른 칸이 틀려도 계좌를 돌려준다. */
    @Test
    void 다른_칸이_틀려도_계좌는_돌려준다() throws Exception {
        ParsedCashflow parsed = CashflowRequestParser.parse(json("""
                {"account_id": "%s", "type": "X", "amount": 1, "occurred_on": "2026-07-25"}
                """.formatted(ACCOUNT)));

        assertThat(parsed.accountId()).isEqualTo(UUID.fromString(ACCOUNT));
        assertThat(parsed.errors()).extracting(CashflowFieldError::path).containsExactly("type");
    }

    @Test
    void 객체가_아니면_본문_오류다() throws Exception {
        ParsedCashflow parsed = CashflowRequestParser.parse(json("[]"));

        assertThat(parsed.errors()).extracting(CashflowFieldError::path, CashflowFieldError::code)
                .containsExactly(org.assertj.core.groups.Tuple.tuple("", "INVALID_TYPE"));
    }

    private static JsonNode json(String body) throws Exception { return JSON.readTree(body); }
}
```

`CashflowValidatorTest.java`:

```java
package com.stockproject.portfolio.cashflow;

import com.stockproject.portfolio.domain.LinkState;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** 금액 · 통화 · 메모 · 날짜 범위. 날짜 범위는 그 계좌의 잔고가 정한다(설계 §2.2). */
class CashflowValidatorTest {

    private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");
    /** 2026-07-31 12:00 KST. */
    private static final Clock JULY_31 = Clock.fixed(Instant.parse("2026-07-31T03:00:00Z"), SEOUL);
    private static final AccountLineRange JULY_24_TO_27 =
            new AccountLineRange(LocalDate.of(2026, 7, 24), LocalDate.of(2026, 7, 27));

    private final CashflowValidator validator = new CashflowValidator(JULY_31);

    @Test
    void 온전한_초안은_통과한다() {
        assertThat(validate(draft("2000000", "KRW", "2026-07-25", "월급"))).isEmpty();
    }

    @Test
    void 금액은_1원_이상의_정수이고_15자리까지다() {
        assertThat(codes(draft("0", "KRW", "2026-07-25", null))).containsExactly("amount:NOT_POSITIVE");
        assertThat(codes(draft("-1", "KRW", "2026-07-25", null))).containsExactly("amount:NOT_POSITIVE");
        assertThat(codes(draft("1.5", "KRW", "2026-07-25", null))).containsExactly("amount:NOT_INTEGER");
        assertThat(codes(draft("2000000.00", "KRW", "2026-07-25", null))).isEmpty();
        assertThat(codes(draft("999999999999999", "KRW", "2026-07-25", null))).isEmpty();
        assertThat(codes(draft("1000000000000000", "KRW", "2026-07-25", null)))
                .containsExactly("amount:TOO_LARGE");
    }

    @Test
    void 원화가_아니면_거부한다() {
        assertThat(validate(draft("1", "USD", "2026-07-25", null)))
                .containsExactly(new CashflowFieldError("currency", "UNSUPPORTED_CURRENCY",
                        "지금은 원화만 입력할 수 있어요"));
    }

    @Test
    void 메모는_100자까지다() {
        assertThat(codes(draft("1", "KRW", "2026-07-25", "가".repeat(100)))).isEmpty();
        assertThat(validate(draft("1", "KRW", "2026-07-25", "가".repeat(101))))
                .containsExactly(new CashflowFieldError("memo", "TOO_LONG", "메모는 100자까지 쓸 수 있어요"));
    }

    /** 첫 잔고 당일의 입금은 그 잔고에 이미 들어 있다. */
    @Test
    void 첫_잔고_다음_날부터_받는다() {
        assertThat(validate(draft("1", "KRW", "2026-07-24", null)))
                .containsExactly(new CashflowFieldError("occurred_on", "BEFORE_FIRST_SNAPSHOT",
                        "07-24 잔고 다음 날부터 입력할 수 있어요"));
        assertThat(codes(draft("1", "KRW", "2026-07-25", null))).isEmpty();
    }

    @Test
    void 오늘까지_받는다() {
        assertThat(codes(draft("1", "KRW", "2026-07-31", null))).isEmpty();
        assertThat(validate(draft("1", "KRW", "2026-08-01", null)))
                .containsExactly(new CashflowFieldError("occurred_on", "AFTER_TODAY",
                        "오늘 이후 날짜는 입력할 수 없어요"));
    }

    /** 서버 시계가 UTC로 하루 뒤처진 시각이어도 한국 날짜로 오늘이면 받는다. */
    @Test
    void 오늘은_한국_날짜다() {
        Clock earlyMorning = Clock.fixed(Instant.parse("2026-07-31T15:30:00Z"), SEOUL); // 08-01 00:30 KST
        CashflowValidator atDawn = new CashflowValidator(earlyMorning);

        assertThat(atDawn.validate(draft("1", "KRW", "2026-08-01", null), JULY_24_TO_27,
                LinkState.CONNECTED)).isEmpty();
        assertThat(atDawn.validate(draft("1", "KRW", "2026-08-02", null), JULY_24_TO_27,
                LinkState.CONNECTED)).extracting(CashflowFieldError::code).containsExactly("AFTER_TODAY");
    }

    @Test
    void 해제한_계좌는_마지막_잔고까지_받는다() {
        assertThat(validator.validate(draft("1", "KRW", "2026-07-27", null), JULY_24_TO_27,
                LinkState.DISCONNECTED)).isEmpty();
        assertThat(validator.validate(draft("1", "KRW", "2026-07-28", null), JULY_24_TO_27,
                LinkState.DISCONNECTED))
                .containsExactly(new CashflowFieldError("occurred_on", "AFTER_DISCONNECTED",
                        "연동을 해제한 계좌는 07-27까지만 입력할 수 있어요"));
    }

    @Test
    void 잔고가_없는_계좌는_받지_않는다() {
        assertThat(validator.validate(draft("1", "KRW", "2026-07-25", null), AccountLineRange.NONE,
                LinkState.CONNECTING))
                .containsExactly(new CashflowFieldError("account_id", "NO_SNAPSHOT",
                        "이 계좌는 아직 잔고가 없어 입력할 수 없어요"));
    }

    @Test
    void 틀린_칸을_모두_모은다() {
        assertThat(codes(draft("1.5", "USD", "2026-08-01", "가".repeat(101)))).containsExactly(
                "amount:NOT_INTEGER", "currency:UNSUPPORTED_CURRENCY", "memo:TOO_LONG",
                "occurred_on:AFTER_TODAY");
    }

    private List<CashflowFieldError> validate(CashflowDraft draft) {
        return validator.validate(draft, JULY_24_TO_27, LinkState.CONNECTED);
    }

    private List<String> codes(CashflowDraft draft) {
        return validate(draft).stream().map(e -> e.path() + ":" + e.code()).toList();
    }

    private static CashflowDraft draft(String amount, String currency, String occurredOn, String memo) {
        return new CashflowDraft(UUID.fromString("20000000-0000-0000-0000-000000000001"),
                CashflowType.DEPOSIT, new BigDecimal(amount), currency, LocalDate.parse(occurredOn), memo);
    }
}
```

- [ ] **Step 2: 실패를 확인한다** (DB 없는 단위 테스트 — 승인 불필요)

Run: `./gradlew test --tests 'com.stockproject.portfolio.cashflow.CashflowRequestParserTest' --tests 'com.stockproject.portfolio.cashflow.CashflowValidatorTest'`
Expected: 컴파일 실패 — `cashflow` 패키지 클래스가 없다.

- [ ] **Step 3: 구현한다**

`cashflow/CashflowType.java`:

```java
package com.stockproject.portfolio.cashflow;

/** 사용자가 넣는 현금흐름. 배당 · 수수료는 데이터팀 원장에서 오므로 여기 없다. */
public enum CashflowType { DEPOSIT, WITHDRAW }
```

`cashflow/CashflowFieldError.java`:

```java
package com.stockproject.portfolio.cashflow;

/** 입력 칸 하나의 오류. path는 요청 JSON 키라 폼이 그 칸 아래에 message를 그대로 띄운다. */
public record CashflowFieldError(String path, String code, String message) { }
```

`cashflow/CashflowDraft.java`:

```java
package com.stockproject.portfolio.cashflow;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;

/** 모양 검사를 통과한 생성 요청. 범위는 아직 보지 않았다. */
public record CashflowDraft(UUID accountId, CashflowType type, BigDecimal amount,
                            String currency, LocalDate occurredOn, String memo) { }
```

`cashflow/ParsedCashflow.java`:

```java
package com.stockproject.portfolio.cashflow;

import java.util.List;
import java.util.UUID;

/**
 * 요청 해석 결과. 오류가 있으면 draft는 null이다.
 *
 * @param accountId 계좌 칸만은 다른 칸이 틀려도 읽힌 대로 싣는다. 남의 계좌이면 칸 오류보다
 *                  403이 먼저 나가야 해서다.
 */
public record ParsedCashflow(CashflowDraft draft, UUID accountId, List<CashflowFieldError> errors) {

    public ParsedCashflow {
        errors = List.copyOf(errors);
    }
}
```

`cashflow/CashflowRequestParser.java`:

```java
package com.stockproject.portfolio.cashflow;

import com.fasterxml.jackson.databind.JsonNode;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * 요청 JSON을 CashflowDraft로 옮긴다. "모양"만 본다 — 있어야 할 값이 있는가, 형이 맞는가,
 * 열거 안의 값인가. 금액 범위 · 날짜 범위는 CashflowValidator가 본다.
 *
 * <p>Jackson 바인딩에 맡기지 않는 것은 유형 오타나 문자열 금액이 칸 정보 없는 400으로 끝나기
 * 때문이다. 폼은 어느 칸이 틀렸는지 알아야 그 아래에 문장을 띄운다.</p>
 */
public final class CashflowRequestParser {

    private CashflowRequestParser() { }

    public static ParsedCashflow parse(JsonNode body) {
        List<CashflowFieldError> errors = new ArrayList<>();
        if (body == null || !body.isObject()) {
            errors.add(new CashflowFieldError("", "INVALID_TYPE", "요청 본문이 객체가 아니에요"));
            return new ParsedCashflow(null, null, errors);
        }

        UUID accountId = accountId(body, errors);
        CashflowType type = type(body, errors);
        BigDecimal amount = amount(body, errors);
        String currency = currency(body, errors);
        LocalDate occurredOn = occurredOn(body, errors);
        String memo = memo(body, errors);

        if (!errors.isEmpty()) return new ParsedCashflow(null, accountId, errors);
        return new ParsedCashflow(new CashflowDraft(accountId, type, amount, currency, occurredOn, memo),
                accountId, errors);
    }

    private static UUID accountId(JsonNode body, List<CashflowFieldError> errors) {
        JsonNode node = body.get("account_id");
        if (node == null || node.isNull()) {
            errors.add(new CashflowFieldError("account_id", "REQUIRED", "계좌를 골라 주세요"));
            return null;
        }
        if (node.isTextual()) {
            try {
                return UUID.fromString(node.asText());
            } catch (IllegalArgumentException ignored) {
                // 아래에서 같은 오류로 알린다.
            }
        }
        errors.add(new CashflowFieldError("account_id", "INVALID_TYPE", "계좌 값이 올바르지 않아요"));
        return null;
    }

    private static CashflowType type(JsonNode body, List<CashflowFieldError> errors) {
        JsonNode node = body.get("type");
        if (node != null && node.isTextual()) {
            for (CashflowType type : CashflowType.values()) {
                if (type.name().equals(node.asText())) return type;
            }
        }
        errors.add(new CashflowFieldError("type", "INVALID_VALUE", "입금·출금 중에서 골라 주세요"));
        return null;
    }

    private static BigDecimal amount(JsonNode body, List<CashflowFieldError> errors) {
        JsonNode node = body.get("amount");
        if (node != null && node.isNumber()) return node.decimalValue();
        errors.add(new CashflowFieldError("amount", "INVALID_TYPE", "금액을 숫자로 입력해 주세요"));
        return null;
    }

    /** 빠지면 원화다. 바디에 칸을 두는 것은 다른 통화를 열 때 요청 모양을 바꾸지 않기 위해서다. */
    private static String currency(JsonNode body, List<CashflowFieldError> errors) {
        JsonNode node = body.get("currency");
        if (node == null || node.isNull()) return "KRW";
        if (node.isTextual()) return node.asText();
        errors.add(new CashflowFieldError("currency", "INVALID_TYPE", "통화 값이 올바르지 않아요"));
        return null;
    }

    private static LocalDate occurredOn(JsonNode body, List<CashflowFieldError> errors) {
        JsonNode node = body.get("occurred_on");
        if (node == null || node.isNull()) {
            errors.add(new CashflowFieldError("occurred_on", "REQUIRED", "날짜를 골라 주세요"));
            return null;
        }
        if (node.isTextual()) {
            try {
                return LocalDate.parse(node.asText());
            } catch (DateTimeParseException ignored) {
                // 아래에서 같은 오류로 알린다.
            }
        }
        errors.add(new CashflowFieldError("occurred_on", "INVALID_DATE", "날짜는 YYYY-MM-DD로 입력해 주세요"));
        return null;
    }

    /** 앞뒤 공백을 지운다. 지우고 남는 것이 없으면 메모가 없는 것이다. */
    private static String memo(JsonNode body, List<CashflowFieldError> errors) {
        JsonNode node = body.get("memo");
        if (node == null || node.isNull()) return null;
        if (!node.isTextual()) {
            errors.add(new CashflowFieldError("memo", "INVALID_TYPE", "메모는 글자로 입력해 주세요"));
            return null;
        }
        String trimmed = node.asText().strip();
        return trimmed.isEmpty() ? null : trimmed;
    }
}
```

`cashflow/AccountLineRange.java`:

```java
package com.stockproject.portfolio.cashflow;

import java.time.LocalDate;

/** 계좌의 첫 · 마지막 잔고 날짜. 잔고가 없으면 둘 다 null이다. */
public record AccountLineRange(LocalDate firstAsOf, LocalDate lastAsOf) {

    public static final AccountLineRange NONE = new AccountLineRange(null, null);
}
```

`cashflow/CashflowValidator.java`:

```java
package com.stockproject.portfolio.cashflow;

import com.stockproject.portfolio.domain.LinkState;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

/**
 * 입출금 한 건의 범위를 본다(설계 §2.2).
 *
 * <p>날짜 범위는 그 계좌의 잔고가 정한다. 첫 잔고보다 앞선 입출금은 그 잔고에 이미 들어 있고,
 * 계좌가 기간 중에 들어왔으면 첫 잔고 전체가 계좌 편입으로 세어진다 — 그 날짜의 입금을 받으면
 * 같은 돈이 두 번 들어간다. 해제한 계좌는 마지막 잔고 뒤로 라인이 없어, 그 뒤 날짜의 입출금은
 * 어느 잔고의 변화와도 짝이 맞지 않는다.</p>
 */
@Component
public class CashflowValidator {

    static final int MAX_AMOUNT_DIGITS = 15;
    static final int MAX_MEMO_LENGTH = 100;

    private static final DateTimeFormatter MONTH_DAY = DateTimeFormatter.ofPattern("MM-dd");

    /** 오늘을 정하는 시계. 시간대가 portfolio.zone이라 한국 날짜로 오늘이다. */
    private final Clock clock;

    public CashflowValidator(Clock clock) { this.clock = clock; }

    public List<CashflowFieldError> validate(CashflowDraft draft, AccountLineRange range,
                                             LinkState linkState) {
        List<CashflowFieldError> errors = new ArrayList<>();
        amount(draft.amount(), errors);
        if (!"KRW".equals(draft.currency())) {
            errors.add(new CashflowFieldError("currency", "UNSUPPORTED_CURRENCY", "지금은 원화만 입력할 수 있어요"));
        }
        if (draft.memo() != null && draft.memo().length() > MAX_MEMO_LENGTH) {
            errors.add(new CashflowFieldError("memo", "TOO_LONG", "메모는 100자까지 쓸 수 있어요"));
        }
        dateRange(draft.occurredOn(), range, linkState, errors);
        return List.copyOf(errors);
    }

    private static void amount(BigDecimal amount, List<CashflowFieldError> errors) {
        BigDecimal plain = amount.stripTrailingZeros();
        if (plain.scale() > 0) {
            errors.add(new CashflowFieldError("amount", "NOT_INTEGER", "원 단위 정수로 입력해 주세요"));
        } else if (plain.signum() <= 0) {
            errors.add(new CashflowFieldError("amount", "NOT_POSITIVE", "1원 이상 입력해 주세요"));
        } else if (plain.precision() - plain.scale() > MAX_AMOUNT_DIGITS) {
            errors.add(new CashflowFieldError("amount", "TOO_LARGE", "15자리까지 입력할 수 있어요"));
        }
    }

    private void dateRange(LocalDate occurredOn, AccountLineRange range, LinkState linkState,
                           List<CashflowFieldError> errors) {
        if (range.firstAsOf() == null) {
            errors.add(new CashflowFieldError("account_id", "NO_SNAPSHOT", "이 계좌는 아직 잔고가 없어 입력할 수 없어요"));
            return;
        }
        if (!occurredOn.isAfter(range.firstAsOf())) {
            errors.add(new CashflowFieldError("occurred_on", "BEFORE_FIRST_SNAPSHOT",
                    "%s 잔고 다음 날부터 입력할 수 있어요".formatted(MONTH_DAY.format(range.firstAsOf()))));
        } else if (occurredOn.isAfter(LocalDate.now(clock))) {
            errors.add(new CashflowFieldError("occurred_on", "AFTER_TODAY", "오늘 이후 날짜는 입력할 수 없어요"));
        } else if (linkState == LinkState.DISCONNECTED && occurredOn.isAfter(range.lastAsOf())) {
            errors.add(new CashflowFieldError("occurred_on", "AFTER_DISCONNECTED",
                    "연동을 해제한 계좌는 %s까지만 입력할 수 있어요".formatted(MONTH_DAY.format(range.lastAsOf()))));
        }
    }
}
```

`cashflow/InvalidCashflowException.java`:

```java
package com.stockproject.portfolio.cashflow;

import java.util.List;

/** 입출금 칸 검증 실패. ApiExceptionHandler가 칸별 오류 400으로 옮긴다. */
public class InvalidCashflowException extends RuntimeException {

    private final List<CashflowFieldError> fields;

    public InvalidCashflowException(List<CashflowFieldError> fields) {
        super("입출금 검증 실패: " + fields.size() + "건");
        this.fields = List.copyOf(fields);
    }

    public List<CashflowFieldError> fields() { return fields; }
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: Step 2와 같은 명령.
Expected: PASS.

- [ ] **Step 5: 커밋 (요청받았을 때)**

```bash
git add src/main/java/com/stockproject/portfolio/cashflow src/test/java/com/stockproject/portfolio/cashflow
git commit -m "feat: 입출금 요청을 칸별로 해석하고 범위를 검증한다"
```

---

### Task 3: 쓰기 매퍼 — `ManualCashflowWriteMapper`

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/cashflow/CashflowRow.java`
- Create: `src/main/java/com/stockproject/portfolio/cashflow/ManualCashflowWriteMapper.java`
- Modify: `src/test/java/com/stockproject/portfolio/auth/ScopeSignatureTest.java:27`
- Test: `src/test/java/com/stockproject/portfolio/cashflow/ManualCashflowWriteMapperTest.java`

**Interfaces:**
- Consumes: `CashflowDraft` · `CashflowType` · `AccountLineRange` (Task 2)
- Produces:
  - `record CashflowRow(UUID id, UUID accountId, String accountLabel, CashflowType type, BigDecimal amount, String currency, LocalDate occurredOn, String memo)`
  - `int insert(UserScope scope, UUID id, CashflowDraft draft)` — 본인 계좌가 아니면 0
  - `List<CashflowRow> list(UserScope scope, LocalDate from, LocalDate to, Set<UUID> accountIds)` — 양 끝 포함, 최근순
  - `int deleteOwned(UserScope scope, UUID id)`
  - `AccountLineRange lineRange(UserScope scope, UUID accountId)` — 라인이 없으면 null

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`ScopeSignatureTest.java`의 검사 범위에 `cashflow`를 더하고, 그 패키지 매퍼가 실제로 검사되는지 확인하는 단언을 넣는다.

```java
        JavaClasses classes = new ClassFileImporter()
                .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
                .importPackages("com.stockproject.portfolio.query", "com.stockproject.portfolio.cashflow");
```

`assertThat(mappers).isNotEmpty();` 다음 줄에:

```java
        // 사용자 소유 행을 쓰는 매퍼도 같은 규칙을 지킨다.
        assertThat(mappers).extracting(Class::getSimpleName).contains("ManualCashflowWriteMapper");
```

`ManualCashflowWriteMapperTest.java`:

```java
package com.stockproject.portfolio.cashflow;

import com.stockproject.portfolio.auth.UserScope;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** 쓰기 · 목록 · 삭제가 모두 SQL에서 스코프를 건다. 서비스가 빠뜨려도 남의 행에 닿지 않는다. */
@SpringBootTest
@ActiveProfiles("test")
@Sql("classpath:db/sample/sample_portfolio.sql")
class ManualCashflowWriteMapperTest {

    private static final UUID YHR_TRUST = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID JDH_TRUST = UUID.fromString("20000000-0000-0000-0000-000000000005");
    private static final UUID HHJ_TRUST = UUID.fromString("20000000-0000-0000-0000-000000000007");
    private static final UUID YHR_SAMPLE_ROW = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final LocalDate JULY_1 = LocalDate.of(2026, 7, 1);
    private static final LocalDate JULY_31 = LocalDate.of(2026, 7, 31);

    @Autowired ManualCashflowWriteMapper mapper;
    @Autowired JdbcClient jdbc;

    @Test
    void 본인_계좌에만_쓴다() {
        assertThat(mapper.insert(scope("yhr"), UUID.randomUUID(), draft(YHR_TRUST, "2026-07-25"))).isEqualTo(1);
        assertThat(mapper.insert(scope("yhr"), UUID.randomUUID(), draft(JDH_TRUST, "2026-07-25"))).isZero();
        assertThat(jdbc.sql("SELECT count(*) FROM manual_cashflow WHERE account_id = :id")
                .param("id", JDH_TRUST).query(Integer.class).single()).isEqualTo(1);
    }

    @Test
    void 목록은_양_끝을_포함하고_최근순이며_계좌_이름을_싣는다() {
        mapper.insert(scope("yhr"), UUID.randomUUID(), draft(YHR_TRUST, "2026-07-01"));
        mapper.insert(scope("yhr"), UUID.randomUUID(), draft(YHR_TRUST, "2026-07-25"));
        mapper.insert(scope("yhr"), UUID.randomUUID(), draft(YHR_TRUST, "2026-08-01"));

        List<CashflowRow> rows = mapper.list(scope("yhr"), JULY_1, JULY_31, Set.of());

        assertThat(rows).extracting(CashflowRow::occurredOn).containsExactly(
                LocalDate.of(2026, 7, 27), LocalDate.of(2026, 7, 25), JULY_1);
        CashflowRow sample = rows.get(0);
        assertThat(sample.id()).isEqualTo(YHR_SAMPLE_ROW);
        assertThat(sample.accountId()).isEqualTo(YHR_TRUST);
        assertThat(sample.accountLabel()).isEqualTo("한국투자 위탁");
        assertThat(sample.type()).isEqualTo(CashflowType.DEPOSIT);
        assertThat(sample.amount()).isEqualByComparingTo("2000000");
        assertThat(sample.currency()).isEqualTo("KRW");
        assertThat(sample.memo()).isEqualTo("월 적립");
    }

    @Test
    void 목록은_남의_행을_싣지_않고_계좌로_좁힌다() {
        assertThat(mapper.list(scope("jdh"), JULY_1, JULY_31, Set.of()))
                .extracting(CashflowRow::accountId).containsOnly(JDH_TRUST);
        assertThat(mapper.list(scope("yhr"), JULY_1, JULY_31,
                Set.of(UUID.fromString("20000000-0000-0000-0000-000000000002")))).isEmpty();
    }

    @Test
    void 남의_행은_지우지_못한다() {
        assertThat(mapper.deleteOwned(scope("jdh"), YHR_SAMPLE_ROW)).isZero();
        assertThat(mapper.deleteOwned(scope("yhr"), YHR_SAMPLE_ROW)).isEqualTo(1);
        assertThat(mapper.deleteOwned(scope("yhr"), YHR_SAMPLE_ROW)).isZero();
    }

    @Test
    void 계좌의_첫_마지막_잔고_날짜() {
        assertThat(mapper.lineRange(scope("yhr"), YHR_TRUST)).isEqualTo(
                new AccountLineRange(LocalDate.of(2026, 7, 24), LocalDate.of(2026, 7, 27)));
        assertThat(mapper.lineRange(scope("hhj"), HHJ_TRUST)).isEqualTo(
                new AccountLineRange(LocalDate.of(2026, 7, 27), LocalDate.of(2026, 7, 27)));
        AccountLineRange others = mapper.lineRange(scope("yhr"), JDH_TRUST);
        assertThat(others == null || others.firstAsOf() == null).isTrue();
    }

    private static CashflowDraft draft(UUID account, String occurredOn) {
        return new CashflowDraft(account, CashflowType.DEPOSIT, new BigDecimal("1000000"), "KRW",
                LocalDate.parse(occurredOn), null);
    }

    private UserScope scope(String user) {
        return new UserScope(jdbc.sql("SELECT id FROM app_user WHERE email = :email")
                .param("email", user + "@a.com").query(UUID.class).single());
    }
}
```

- [ ] **Step 2: 실패를 확인한다** (사용자 승인 후)

Run: `./gradlew test --tests 'com.stockproject.portfolio.cashflow.ManualCashflowWriteMapperTest' --tests 'com.stockproject.portfolio.auth.ScopeSignatureTest'`
Expected: 컴파일 실패 — `ManualCashflowWriteMapper` · `CashflowRow`가 없다.

- [ ] **Step 3: 구현한다**

`cashflow/CashflowRow.java`:

```java
package com.stockproject.portfolio.cashflow;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;

/** 입출금 목록 한 행. 계좌 이름을 함께 읽어 화면이 카탈로그를 다시 뒤지지 않게 한다. */
public record CashflowRow(UUID id, UUID accountId, String accountLabel, CashflowType type,
                          BigDecimal amount, String currency, LocalDate occurredOn, String memo) { }
```

`cashflow/ManualCashflowWriteMapper.java`:

```java
package com.stockproject.portfolio.cashflow;

import com.stockproject.portfolio.auth.UserScope;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDate;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * 사용자가 넣는 입출금의 쓰기 · 목록 · 삭제. 자산 변화가 쓰는 집계(query/ManualCashflowMapper)와
 * 나눠 둔다 — 조회 계층은 읽기만 한다.
 *
 * <p>모든 문장이 account.user_id로 스코프를 건다. 서비스가 소유를 먼저 확인하지만, 그 확인을
 * 빠뜨려도 남의 행에 닿지 않게 하는 마지막 자리가 여기다.</p>
 */
@Mapper
public interface ManualCashflowWriteMapper {

    /** 본인 계좌가 아니면 아무것도 쓰지 않고 0을 돌려준다. */
    @Insert("""
            INSERT INTO manual_cashflow (id, account_id, type, amount, currency, occurred_on, memo)
            SELECT #{id}, a.account_id, #{draft.type}, #{draft.amount}, #{draft.currency},
                   #{draft.occurredOn}, #{draft.memo}
              FROM account a
             WHERE a.account_id = #{draft.accountId} AND a.user_id = #{scope.userId}
            """)
    int insert(@Param("scope") UserScope scope, @Param("id") UUID id, @Param("draft") CashflowDraft draft);

    /** 기간 양 끝을 포함한다. 최근 날짜가 위, 같은 날이면 id순. */
    @Select("""
            <script>
            SELECT m.id, m.account_id, a.label AS account_label, m.type, m.amount, m.currency,
                   m.occurred_on, m.memo
              FROM manual_cashflow m
              JOIN account a ON a.account_id = m.account_id
             WHERE a.user_id = #{scope.userId}
               AND m.occurred_on BETWEEN #{from} AND #{to}
            <if test="accountIds != null and accountIds.size() > 0">
               AND m.account_id IN
               <foreach item="id" collection="accountIds" open="(" separator="," close=")">#{id}</foreach>
            </if>
             ORDER BY m.occurred_on DESC, m.id
            </script>
            """)
    List<CashflowRow> list(@Param("scope") UserScope scope, @Param("from") LocalDate from,
                           @Param("to") LocalDate to, @Param("accountIds") Set<UUID> accountIds);

    /** 지운 행 수. 남의 행과 없는 행은 똑같이 0이다. */
    @Delete("""
            DELETE FROM manual_cashflow m
             USING account a
             WHERE m.account_id = a.account_id
               AND a.user_id = #{scope.userId}
               AND m.id = #{id}
            """)
    int deleteOwned(@Param("scope") UserScope scope, @Param("id") UUID id);

    /** 그 계좌의 첫 · 마지막 잔고 날짜. 입출금 날짜 범위가 여기서 정해진다. */
    @Select("""
            SELECT min(pl.as_of) AS first_as_of, max(pl.as_of) AS last_as_of
              FROM position_line pl
              JOIN account a ON a.account_id = pl.account_id
             WHERE a.user_id = #{scope.userId} AND pl.account_id = #{accountId}
            """)
    AccountLineRange lineRange(@Param("scope") UserScope scope, @Param("accountId") UUID accountId);
}
```

- [ ] **Step 4: 통과를 확인한다** (사용자 승인 후)

Run: Step 2와 같은 명령.
Expected: PASS.

- [ ] **Step 5: 커밋 (요청받았을 때)**

```bash
git add src/main/java/com/stockproject/portfolio/cashflow/CashflowRow.java \
        src/main/java/com/stockproject/portfolio/cashflow/ManualCashflowWriteMapper.java \
        src/test/java/com/stockproject/portfolio/cashflow/ManualCashflowWriteMapperTest.java \
        src/test/java/com/stockproject/portfolio/auth/ScopeSignatureTest.java
git commit -m "feat: 입출금을 본인 계좌 범위 안에서만 쓰고 지우는 매퍼를 둔다"
```

---

### Task 4: 생성 API — `POST /portfolio/cashflows`

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/cashflow/ManualCashflowService.java`
- Create: `src/main/java/com/stockproject/portfolio/api/CashflowController.java`
- Create: `src/main/java/com/stockproject/portfolio/api/dto/CashflowIdResponse.java`
- Create: `src/main/java/com/stockproject/portfolio/api/dto/InvalidCashflowError.java`
- Modify: `src/main/java/com/stockproject/portfolio/api/ApiExceptionHandler.java`
- Create: `src/test/java/com/stockproject/portfolio/cashflow/CashflowTestClock.java`
- Test: `src/test/java/com/stockproject/portfolio/api/CashflowApiTest.java`

**Interfaces:**
- Consumes: `CashflowRequestParser.parse` · `CashflowValidator.validate` · `InvalidCashflowException` (Task 2), `ManualCashflowWriteMapper.insert` · `lineRange` (Task 3), `AccountOwnershipGuard.check(UserScope, Set<UUID>)` · `AccountRepository.findAll(UserScope)` (기존)
- Produces: `ManualCashflowService.create(UserScope scope, JsonNode body): UUID`; `CashflowController` 클래스(Task 5가 메서드를 더한다); `record CashflowIdResponse(UUID id)`; `InvalidCashflowError.of(List<CashflowFieldError>)`; 테스트 설정 `CashflowTestClock`(오늘 2026-07-31 KST)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`cashflow/CashflowTestClock.java` (테스트):

```java
package com.stockproject.portfolio.cashflow;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;

/** 입출금 테스트의 오늘. 샘플 잔고(07-24 · 07-27) 뒤의 날짜가 미래가 되지 않게 7월 말에 둔다. */
@TestConfiguration
public class CashflowTestClock {

    public static final Instant NOW = Instant.parse("2026-07-31T03:00:00Z");

    @Bean
    @Primary
    Clock cashflowClock() {
        return Clock.fixed(NOW, ZoneId.of("Asia/Seoul"));
    }
}
```

`api/CashflowApiTest.java` (Task 5가 이 파일에 목록 · 삭제 테스트를 더한다):

```java
package com.stockproject.portfolio.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.cashflow.CashflowTestClock;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/**
 * 입출금 입력 API. 넣은 돈은 사용자 입력에서만 온다(스펙 §9.1).
 * 샘플: yhr의 계좌 …001~…004는 07-24 · 07-27에 잔고가 있고, hhj의 …007은 07-27에만 있다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(CashflowTestClock.class)
@Sql("classpath:db/sample/sample_portfolio.sql")
class CashflowApiTest {

    static final String PASSWORD = "local-dev-password";
    static final String PATH = "/portfolio/cashflows";
    static final String YHR_TRUST = "20000000-0000-0000-0000-000000000001";
    static final String YHR_PENSION = "20000000-0000-0000-0000-000000000004";
    static final String JDH_TRUST = "20000000-0000-0000-0000-000000000005";
    static final String HHJ_TRUST = "20000000-0000-0000-0000-000000000007";

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;

    // --- 생성 ---------------------------------------------------------------

    @Test
    void 넣으면_201과_id를_돌려주고_그대로_저장한다() throws Exception {
        MvcResult result = postAs("yhr", """
                {"account_id": "%s", "type": "DEPOSIT", "amount": 1000000,
                 "occurred_on": "2026-07-25", "memo": " 월급 "}
                """.formatted(YHR_TRUST));

        assertThat(result.getResponse().getStatus()).isEqualTo(201);
        UUID id = UUID.fromString(body(result).get("id").asText());
        Map<String, Object> row = jdbc.sql("SELECT * FROM manual_cashflow WHERE id = :id")
                .param("id", id).query().singleRow();
        assertThat(row.get("account_id")).isEqualTo(UUID.fromString(YHR_TRUST));
        assertThat(row.get("type")).isEqualTo("DEPOSIT");
        assertThat(row.get("amount").toString()).isEqualTo("1000000");
        assertThat(row.get("currency")).isEqualTo("KRW");
        assertThat(row.get("occurred_on").toString()).isEqualTo("2026-07-25");
        assertThat(row.get("memo")).isEqualTo("월급");
    }

    @Test
    void 남의_계좌나_없는_계좌는_403이고_쓰지_않는다() throws Exception {
        for (String account : new String[]{JDH_TRUST, UUID.randomUUID().toString()}) {
            MvcResult result = postAs("yhr", valid(account, "2026-07-25"));

            assertThat(result.getResponse().getStatus()).as(account).isEqualTo(403);
            assertThat(errorCode(result)).isEqualTo("FORBIDDEN_ACCOUNT");
        }
        assertThat(count(JDH_TRUST)).isEqualTo(1);
    }

    /** 소유 확인이 칸 검증보다 먼저다. 칸 오류로 답하면 그 계좌가 있다는 사실이 새어 나간다. */
    @Test
    void 남의_계좌에_틀린_칸이_섞여도_403이다() throws Exception {
        MvcResult result = postAs("yhr", """
                {"account_id": "%s", "type": "X", "amount": "abc", "occurred_on": "2026-07-25"}
                """.formatted(JDH_TRUST));

        assertThat(result.getResponse().getStatus()).isEqualTo(403);
    }

    @Test
    void 모양이_틀리면_칸별_오류다() throws Exception {
        MvcResult result = postAs("yhr", """
                {"account_id": "%s", "type": "DEPOSITE", "amount": 1, "occurred_on": "2026-07-25"}
                """.formatted(YHR_TRUST));

        assertThat(result.getResponse().getStatus()).isEqualTo(400);
        JsonNode error = body(result).get("error");
        assertThat(error.get("code").asText()).isEqualTo("INVALID_CASHFLOW");
        assertThat(error.get("fields").get(0).get("path").asText()).isEqualTo("type");
        assertThat(error.get("fields").get(0).get("message").asText()).isEqualTo("입금·출금 중에서 골라 주세요");
    }

    @Test
    void 범위가_틀린_칸을_모두_알린다() throws Exception {
        MvcResult result = postAs("yhr", """
                {"account_id": "%s", "type": "DEPOSIT", "amount": 1.5, "currency": "USD",
                 "occurred_on": "2026-07-25", "memo": "%s"}
                """.formatted(YHR_TRUST, "가".repeat(101)));

        assertThat(result.getResponse().getStatus()).isEqualTo(400);
        assertThat(paths(result)).containsExactly("amount", "currency", "memo");
    }

    @Test
    void 날짜는_그_계좌의_첫_잔고_다음_날부터_오늘까지다() throws Exception {
        MvcResult firstDay = postAs("yhr", valid(YHR_TRUST, "2026-07-24"));
        assertThat(firstDay.getResponse().getStatus()).isEqualTo(400);
        assertThat(body(firstDay).get("error").get("fields").get(0).get("message").asText())
                .isEqualTo("07-24 잔고 다음 날부터 입력할 수 있어요");

        assertThat(postAs("yhr", valid(YHR_TRUST, "2026-08-01")).getResponse().getStatus()).isEqualTo(400);
        assertThat(postAs("yhr", valid(YHR_TRUST, "2026-07-31")).getResponse().getStatus()).isEqualTo(201);

        // 07-27에 연동을 시작한 계좌는 07-28부터다.
        assertThat(postAs("hhj", valid(HHJ_TRUST, "2026-07-27")).getResponse().getStatus()).isEqualTo(400);
        assertThat(postAs("hhj", valid(HHJ_TRUST, "2026-07-28")).getResponse().getStatus()).isEqualTo(201);
    }

    @Test
    void 해제한_계좌는_마지막_잔고까지_받는다() throws Exception {
        jdbc.sql("UPDATE account SET link_state = 'DISCONNECTED' WHERE account_id = :id")
                .param("id", UUID.fromString(YHR_PENSION)).update();

        assertThat(postAs("yhr", valid(YHR_PENSION, "2026-07-27")).getResponse().getStatus()).isEqualTo(201);

        MvcResult after = postAs("yhr", valid(YHR_PENSION, "2026-07-28"));
        assertThat(after.getResponse().getStatus()).isEqualTo(400);
        assertThat(body(after).get("error").get("fields").get(0).get("message").asText())
                .isEqualTo("연동을 해제한 계좌는 07-27까지만 입력할 수 있어요");
    }

    @Test
    void 잔고가_없는_계좌는_받지_않는다() throws Exception {
        UUID fresh = UUID.randomUUID();
        jdbc.sql("""
                INSERT INTO account (account_id, user_id, account_ref, broker, label, account_type,
                                     source, credential_ref, link_state, last_synced_at)
                SELECT :id, id, 'ar_test_fresh', '테스트증권', '새 계좌', 'GENERAL', 'KIS', NULL,
                       'CONNECTING', NULL
                  FROM app_user WHERE email = 'yhr@a.com'
                """).param("id", fresh).update();

        MvcResult result = postAs("yhr", valid(fresh.toString(), "2026-07-25"));

        assertThat(result.getResponse().getStatus()).isEqualTo(400);
        assertThat(paths(result)).containsExactly("account_id");
    }

    @Test
    void 토큰이_없으면_401이다() throws Exception {
        assertThat(mockMvc.perform(post(PATH).contentType(MediaType.APPLICATION_JSON)
                .content(valid(YHR_TRUST, "2026-07-25"))).andReturn().getResponse().getStatus()).isEqualTo(401);
    }

    // --- 요청 도우미 --------------------------------------------------------

    static String valid(String account, String occurredOn) {
        return """
                {"account_id": "%s", "type": "DEPOSIT", "amount": 1000000, "occurred_on": "%s"}
                """.formatted(account, occurredOn);
    }

    MvcResult postAs(String user, String content) throws Exception {
        return mockMvc.perform(post(PATH).header("Authorization", bearer(user))
                .contentType(MediaType.APPLICATION_JSON).content(content)).andReturn();
    }

    MvcResult getAs(String user, String query) throws Exception {
        return mockMvc.perform(get(PATH + query).header("Authorization", bearer(user))).andReturn();
    }

    MvcResult deleteAs(String user, String id) throws Exception {
        return mockMvc.perform(delete(PATH + "/" + id).header("Authorization", bearer(user))).andReturn();
    }

    JsonNode body(MvcResult result) throws Exception {
        return json.readTree(result.getResponse().getContentAsString(StandardCharsets.UTF_8));
    }

    String errorCode(MvcResult result) throws Exception {
        return body(result).get("error").get("code").asText();
    }

    java.util.List<String> paths(MvcResult result) throws Exception {
        java.util.List<String> paths = new java.util.ArrayList<>();
        for (JsonNode field : body(result).get("error").get("fields")) paths.add(field.get("path").asText());
        return paths;
    }

    int count(String account) {
        return jdbc.sql("SELECT count(*) FROM manual_cashflow WHERE account_id = :id")
                .param("id", UUID.fromString(account)).query(Integer.class).single();
    }

    String bearer(String user) throws Exception {
        String body = mockMvc.perform(post("/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email": "%s@a.com", "password": "%s"}
                                """.formatted(user, PASSWORD)))
                .andReturn().getResponse().getContentAsString();
        return "Bearer " + json.readTree(body).get("access_token").asText();
    }
}
```

- [ ] **Step 2: 실패를 확인한다** (사용자 승인 후)

Run: `./gradlew test --tests 'com.stockproject.portfolio.api.CashflowApiTest'`
Expected: FAIL — 경로가 없어 `POST /portfolio/cashflows`가 404(또는 405)다.

- [ ] **Step 3: 구현한다**

`cashflow/ManualCashflowService.java` (Task 5가 목록 · 삭제를 더한다):

```java
package com.stockproject.portfolio.cashflow;

import com.fasterxml.jackson.databind.JsonNode;
import com.stockproject.portfolio.auth.AccountOwnershipGuard;
import com.stockproject.portfolio.auth.ForbiddenAccountException;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.domain.LinkState;
import com.stockproject.portfolio.query.AccountRepository;
import com.stockproject.portfolio.query.AccountRow;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/**
 * 사용자가 넣는 입출금. 자산 변화의 "넣은 돈"이 여기서만 온다(스펙 §9.1).
 *
 * <p>순서는 해석 → 소유 확인 → 범위 검증이다. 남의 계좌이면 칸 오류보다 403이 먼저 나간다.
 * 날짜 범위는 그 계좌의 잔고를 읽어야 판정할 수 있어 소유가 확인된 뒤에 본다.</p>
 */
@Service
public class ManualCashflowService {

    private final ManualCashflowWriteMapper writes;
    private final AccountOwnershipGuard ownership;
    private final AccountRepository accounts;
    private final CashflowValidator validator;

    public ManualCashflowService(ManualCashflowWriteMapper writes, AccountOwnershipGuard ownership,
                                 AccountRepository accounts, CashflowValidator validator) {
        this.writes = writes;
        this.ownership = ownership;
        this.accounts = accounts;
        this.validator = validator;
    }

    @Transactional
    public UUID create(UserScope scope, JsonNode body) {
        ParsedCashflow parsed = CashflowRequestParser.parse(body);
        if (parsed.accountId() != null) ownership.check(scope, Set.of(parsed.accountId()));
        if (!parsed.errors().isEmpty()) throw new InvalidCashflowException(parsed.errors());

        CashflowDraft draft = parsed.draft();
        AccountLineRange range = Optional.ofNullable(writes.lineRange(scope, draft.accountId()))
                .orElse(AccountLineRange.NONE);
        List<CashflowFieldError> errors = validator.validate(draft, range, linkStateOf(scope, draft.accountId()));
        if (!errors.isEmpty()) throw new InvalidCashflowException(errors);

        UUID id = UUID.randomUUID();
        // 넣기는 본인 계좌에만 닿는다. 검사 뒤 계좌가 사라졌으면 0건이고, 없는 id를 돌려주지 않는다.
        if (writes.insert(scope, id, draft) != 1) throw new ForbiddenAccountException();
        return id;
    }

    private LinkState linkStateOf(UserScope scope, UUID accountId) {
        return accounts.findAll(scope).stream()
                .filter(account -> account.id().equals(accountId))
                .map(AccountRow::linkState)
                .findFirst()
                .orElseThrow(ForbiddenAccountException::new);
    }
}
```

`api/dto/CashflowIdResponse.java`:

```java
package com.stockproject.portfolio.api.dto;

import java.util.UUID;

/** 새로 만든 입출금의 id. 화면은 목록을 다시 받아 그리므로 이것만 돌려준다. */
public record CashflowIdResponse(UUID id) { }
```

`api/dto/InvalidCashflowError.java`:

```java
package com.stockproject.portfolio.api.dto;

import com.stockproject.portfolio.cashflow.CashflowFieldError;

import java.util.List;

/**
 * 입출금 저장 검증 실패. ApiError에 fields를 더하지 않는 것은 다른 오류 응답에
 * "fields": null이 생기지 않게 하기 위해서다.
 */
public record InvalidCashflowError(Detail error) {

    public record Detail(String code, String message, List<CashflowFieldError> fields) { }

    public static InvalidCashflowError of(List<CashflowFieldError> fields) {
        return new InvalidCashflowError(new Detail("INVALID_CASHFLOW", "입력을 확인해 주세요", fields));
    }
}
```

`api/CashflowController.java`:

```java
package com.stockproject.portfolio.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.stockproject.portfolio.api.dto.CashflowIdResponse;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.cashflow.ManualCashflowService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/** 사용자가 넣는 입출금. 자산 변화의 `넣은 돈` 행에서 들어오는 화면이 쓴다. */
@RestController
@RequestMapping("/portfolio/cashflows")
public class CashflowController {

    private final ManualCashflowService cashflows;

    public CashflowController(ManualCashflowService cashflows) { this.cashflows = cashflows; }

    /** 바디를 JsonNode로 받는다 — 틀린 칸을 칸별 오류로 돌려주려면 해석을 직접 해야 한다. */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public CashflowIdResponse create(UserScope scope, @RequestBody JsonNode body) {
        return new CashflowIdResponse(cashflows.create(scope, body));
    }
}
```

`api/ApiExceptionHandler.java`에 처리기를 더한다(import 둘: `com.stockproject.portfolio.api.dto.InvalidCashflowError` · `com.stockproject.portfolio.cashflow.InvalidCashflowException`).

```java
    @ExceptionHandler(InvalidCashflowException.class)
    public ResponseEntity<InvalidCashflowError> invalidCashflow(InvalidCashflowException e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(InvalidCashflowError.of(e.fields()));
    }
```

- [ ] **Step 4: 통과를 확인한다** (사용자 승인 후)

Run: `./gradlew test --tests 'com.stockproject.portfolio.api.CashflowApiTest' --tests 'com.stockproject.portfolio.ArchitectureRulesTest'`
Expected: PASS. 컨트롤러가 매퍼 · 저장소에 직접 닿지 않는 규칙도 통과한다.

- [ ] **Step 5: 커밋 (요청받았을 때)**

```bash
git add src/main/java/com/stockproject/portfolio/cashflow/ManualCashflowService.java \
        src/main/java/com/stockproject/portfolio/api/CashflowController.java \
        src/main/java/com/stockproject/portfolio/api/dto/CashflowIdResponse.java \
        src/main/java/com/stockproject/portfolio/api/dto/InvalidCashflowError.java \
        src/main/java/com/stockproject/portfolio/api/ApiExceptionHandler.java \
        src/test/java/com/stockproject/portfolio/cashflow/CashflowTestClock.java \
        src/test/java/com/stockproject/portfolio/api/CashflowApiTest.java
git commit -m "feat: 본인 계좌에 입출금을 넣는 API를 연다"
```

---

### Task 5: 목록 · 삭제 API — `GET` · `DELETE /portfolio/cashflows`

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/cashflow/CashflowList.java`
- Create: `src/main/java/com/stockproject/portfolio/api/dto/CashflowListResponse.java`
- Modify: `src/main/java/com/stockproject/portfolio/cashflow/ManualCashflowService.java`
- Modify: `src/main/java/com/stockproject/portfolio/api/CashflowController.java`
- Test: `src/test/java/com/stockproject/portfolio/api/CashflowApiTest.java` (테스트 추가)

**Interfaces:**
- Consumes: `SnapshotPairResolver.resolve` · `SnapshotPair` (Task 1), `ManualCashflowWriteMapper.list` · `deleteOwned` (Task 3), `RequestParams.lineFilter` (기존, `UNKNOWN_FILTER_VALUE`), `RequestRejected(code, message, notFound)` (기존)
- Produces: `record CashflowList(SnapshotPair pair, List<CashflowRow> rows)`; `ManualCashflowService.list(UserScope, String from, String to, Set<UUID> accountIds): CashflowList`; `ManualCashflowService.delete(UserScope, String id)`; 응답 `{ window: { after, through } | null, cashflows: [...] }`

- [ ] **Step 1: 실패하는 테스트를 더한다**

`CashflowApiTest`의 `// --- 요청 도우미` 위에:

```java
    // --- 목록 ---------------------------------------------------------------

    private static final String JULY = "?from=2026-07-01&to=2026-07-31";

    @Test
    void 목록은_기간의_행과_넣은_돈을_세는_구간을_싣는다() throws Exception {
        JsonNode body = body(getAs("yhr", JULY));

        assertThat(body.get("window").get("after").asText()).isEqualTo("2026-07-24");
        assertThat(body.get("window").get("through").asText()).isEqualTo("2026-07-27");
        JsonNode row = body.get("cashflows").get(0);
        assertThat(row.get("id").asText()).isEqualTo("30000000-0000-0000-0000-000000000001");
        assertThat(row.get("account_id").asText()).isEqualTo(YHR_TRUST);
        assertThat(row.get("account_label").asText()).isEqualTo("한국투자 위탁");
        assertThat(row.get("type").asText()).isEqualTo("DEPOSIT");
        assertThat(row.get("amount").asLong()).isEqualTo(2000000);
        assertThat(row.get("currency").asText()).isEqualTo("KRW");
        assertThat(row.get("occurred_on").asText()).isEqualTo("2026-07-27");
        assertThat(row.get("memo").asText()).isEqualTo("월 적립");
    }

    @Test
    void 목록은_최근순이다() throws Exception {
        postAs("yhr", valid(YHR_TRUST, "2026-07-25"));
        postAs("yhr", valid(YHR_TRUST, "2026-07-31"));

        JsonNode rows = body(getAs("yhr", JULY)).get("cashflows");

        assertThat(rows).extracting(row -> row.get("occurred_on").asText())
                .containsExactly("2026-07-31", "2026-07-27", "2026-07-25");
    }

    @Test
    void 구간이_비거나_잔고가_없으면_그대로_알린다() throws Exception {
        JsonNode hhj = body(getAs("hhj", JULY));
        assertThat(hhj.get("window").get("after").asText()).isEqualTo("2026-07-27");
        assertThat(hhj.get("window").get("through").asText()).isEqualTo("2026-07-27");
        assertThat(hhj.get("cashflows")).isEmpty();

        assertThat(body(getAs("test_empty", JULY)).get("window").isNull()).isTrue();
    }

    @Test
    void 목록에_남의_행이_섞이지_않는다() throws Exception {
        assertThat(body(getAs("jdh", JULY)).get("cashflows"))
                .extracting(row -> row.get("account_id").asText()).containsOnly(JDH_TRUST);
    }

    @Test
    void 목록_요청이_틀리면_거부한다() throws Exception {
        MvcResult others = getAs("yhr", JULY + "&account=" + JDH_TRUST);
        assertThat(others.getResponse().getStatus()).isEqualTo(403);
        assertThat(errorCode(others)).isEqualTo("FORBIDDEN_ACCOUNT");

        MvcResult notUuid = getAs("yhr", JULY + "&account=abc");
        assertThat(notUuid.getResponse().getStatus()).isEqualTo(400);
        assertThat(errorCode(notUuid)).isEqualTo("UNKNOWN_FILTER_VALUE");

        for (String query : new String[]{"?from=2026-07-31&to=2026-07-01", "?from=2026-07-01",
                                         "?from=2026-07-01&to=7월"}) {
            MvcResult result = getAs("yhr", query);
            assertThat(result.getResponse().getStatus()).as(query).isEqualTo(400);
            assertThat(errorCode(result)).as(query).isEqualTo("INVALID_PERIOD");
        }
    }

    // --- 삭제 ---------------------------------------------------------------

    @Test
    void 지우면_204이고_목록에서_빠진다() throws Exception {
        assertThat(deleteAs("yhr", "30000000-0000-0000-0000-000000000001").getResponse().getStatus())
                .isEqualTo(204);
        assertThat(body(getAs("yhr", JULY)).get("cashflows")).isEmpty();
    }

    /** 남의 행과 없는 행이 같은 답이어야 남의 행이 있는지 알 수 없다. */
    @Test
    void 남의_행과_없는_행은_같은_404다() throws Exception {
        MvcResult others = deleteAs("jdh", "30000000-0000-0000-0000-000000000001");
        MvcResult missing = deleteAs("jdh", UUID.randomUUID().toString());
        MvcResult garbage = deleteAs("jdh", "not-a-uuid");

        for (MvcResult result : new MvcResult[]{others, missing, garbage}) {
            assertThat(result.getResponse().getStatus()).isEqualTo(404);
            assertThat(errorCode(result)).isEqualTo("CASHFLOW_NOT_FOUND");
        }
        assertThat(others.getResponse().getContentAsString(StandardCharsets.UTF_8))
                .isEqualTo(missing.getResponse().getContentAsString(StandardCharsets.UTF_8));
        assertThat(count(YHR_TRUST)).isEqualTo(1);
    }

    @Test
    void 목록과_삭제도_토큰이_없으면_401이다() throws Exception {
        assertThat(mockMvc.perform(get(PATH + JULY)).andReturn().getResponse().getStatus()).isEqualTo(401);
        assertThat(mockMvc.perform(delete(PATH + "/30000000-0000-0000-0000-000000000001"))
                .andReturn().getResponse().getStatus()).isEqualTo(401);
    }
```

- [ ] **Step 2: 실패를 확인한다** (사용자 승인 후)

Run: `./gradlew test --tests 'com.stockproject.portfolio.api.CashflowApiTest'`
Expected: 새 테스트 FAIL — `GET` · `DELETE` 경로가 없다(405).

- [ ] **Step 3: 구현한다**

`cashflow/CashflowList.java`:

```java
package com.stockproject.portfolio.cashflow;

import com.stockproject.portfolio.view.SnapshotPair;

import java.util.List;

/**
 * 기간의 입출금과, 같은 기간 자산 변화가 넣은 돈을 세는 두 잔고.
 * 잔고가 없으면 pair가 null이다.
 */
public record CashflowList(SnapshotPair pair, List<CashflowRow> rows) {

    public CashflowList {
        rows = List.copyOf(rows);
    }
}
```

`ManualCashflowService`에 필드 · 생성자 인자 `SnapshotPairResolver pairs`를 더하고 메서드 둘을 붙인다(import: `com.stockproject.portfolio.validation.RequestRejected`, `com.stockproject.portfolio.view.SnapshotPairResolver`, `java.time.LocalDate`, `java.time.format.DateTimeParseException`).

```java
    /** 기간 양 끝을 포함한 입출금과, 같은 기간 자산 변화가 넣은 돈을 세는 두 잔고. */
    @Transactional(readOnly = true)
    public CashflowList list(UserScope scope, String from, String to, Set<UUID> accountIds) {
        LocalDate start = date(from);
        LocalDate end = date(to);
        if (start.isAfter(end)) {
            throw new RequestRejected("INVALID_PERIOD", "시작일이 종료일보다 늦어요");
        }
        ownership.check(scope, accountIds);

        return new CashflowList(pairs.resolve(scope, start, end).orElse(null),
                writes.list(scope, start, end, accountIds));
    }

    /** 남의 행 · 없는 행 · id 형식이 아닌 값은 모두 같은 404다. */
    @Transactional
    public void delete(UserScope scope, String id) {
        UUID uuid;
        try {
            uuid = UUID.fromString(id);
        } catch (IllegalArgumentException notUuid) {
            throw notFound();
        }
        if (writes.deleteOwned(scope, uuid) == 0) throw notFound();
    }

    private static LocalDate date(String value) {
        if (value == null) throw invalidPeriod();
        try {
            return LocalDate.parse(value);
        } catch (DateTimeParseException invalid) {
            throw invalidPeriod();
        }
    }

    private static RequestRejected invalidPeriod() {
        return new RequestRejected("INVALID_PERIOD", "기간(from · to)을 YYYY-MM-DD로 보내 주세요");
    }

    private static RequestRejected notFound() {
        return new RequestRejected("CASHFLOW_NOT_FOUND", "입출금 기록을 찾을 수 없어요", true);
    }
```

생성자:

```java
    public ManualCashflowService(ManualCashflowWriteMapper writes, AccountOwnershipGuard ownership,
                                 AccountRepository accounts, CashflowValidator validator,
                                 SnapshotPairResolver pairs) {
        this.writes = writes;
        this.ownership = ownership;
        this.accounts = accounts;
        this.validator = validator;
        this.pairs = pairs;
    }
```

`api/dto/CashflowListResponse.java`:

```java
package com.stockproject.portfolio.api.dto;

import com.stockproject.portfolio.cashflow.CashflowList;
import com.stockproject.portfolio.cashflow.CashflowRow;
import com.stockproject.portfolio.cashflow.CashflowType;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

/**
 * 입출금 목록. 뷰가 아니라 사용자가 넣은 기록이라 봉투(as_of · notices)를 쓰지 않는다.
 *
 * <p>window는 같은 기간 자산 변화가 넣은 돈을 세는 구간 (after, through]다. 이 밖의 행은 그
 * 기간 자산 변화에 들어가지 않고, 화면이 그 사실을 행 아래에 적는다.</p>
 */
public record CashflowListResponse(Window window, List<Item> cashflows) {

    public record Window(LocalDate after, LocalDate through) { }

    public record Item(UUID id, UUID accountId, String accountLabel, CashflowType type,
                       BigDecimal amount, String currency, LocalDate occurredOn, String memo) { }

    public static CashflowListResponse of(CashflowList list) {
        Window window = list.pair() == null ? null
                : new Window(list.pair().opening(), list.pair().closing());
        return new CashflowListResponse(window, list.rows().stream().map(CashflowListResponse::item).toList());
    }

    private static Item item(CashflowRow row) {
        return new Item(row.id(), row.accountId(), row.accountLabel(), row.type(), row.amount(),
                row.currency(), row.occurredOn(), row.memo());
    }
}
```

`CashflowController`에 두 메서드를 더한다(import: `CashflowListResponse`, `DeleteMapping`, `GetMapping`, `PathVariable`, `RequestParam`, `java.util.List`).

```java
    /** 기간은 문자열로 받아 서비스가 해석한다 — 형식 오류도 INVALID_PERIOD로 돌려주기 위해서다. */
    @GetMapping
    public CashflowListResponse list(UserScope scope,
                                     @RequestParam(required = false) String from,
                                     @RequestParam(required = false) String to,
                                     @RequestParam(required = false) List<String> account) {
        return CashflowListResponse.of(cashflows.list(scope, from, to,
                RequestParams.lineFilter(account, null, null, null).accountIds()));
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(UserScope scope, @PathVariable String id) {
        cashflows.delete(scope, id);
    }
```

- [ ] **Step 4: 통과를 확인한다** (사용자 승인 후)

Run: `./gradlew test --tests 'com.stockproject.portfolio.api.CashflowApiTest' --tests 'com.stockproject.portfolio.ArchitectureRulesTest'`
Expected: PASS.

- [ ] **Step 5: 커밋 (요청받았을 때)**

```bash
git add src/main/java/com/stockproject/portfolio/cashflow \
        src/main/java/com/stockproject/portfolio/api/CashflowController.java \
        src/main/java/com/stockproject/portfolio/api/dto/CashflowListResponse.java \
        src/test/java/com/stockproject/portfolio/api/CashflowApiTest.java
git commit -m "feat: 기간의 입출금과 넣은 돈을 세는 구간을 돌려주고 지울 수 있게 한다"
```

---

### Task 6: 끝단 — 넣은 입출금이 자산 변화에 들어간다

**Files:**
- Test: `src/test/java/com/stockproject/portfolio/api/CashflowAssetChangeFlowTest.java`

**Interfaces:**
- Consumes: `POST` · `GET` · `DELETE /portfolio/cashflows` (Task 4 · 5), `GET /portfolio/views/asset-change` (기존)

- [ ] **Step 1: 테스트를 쓴다**

```java
package com.stockproject.portfolio.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.cashflow.CashflowTestClock;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/**
 * 입출금을 넣고 지우면 같은 기간 자산 변화의 넣은 돈이 따라 움직인다.
 * yhr의 7월은 기초 07-24 · 기말 07-27이고 넣은 돈은 07-27 입금 2,000,000이다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(CashflowTestClock.class)
@Sql("classpath:db/sample/sample_portfolio.sql")
class CashflowAssetChangeFlowTest {

    private static final String JULY = "/portfolio/views/asset-change?period=CUSTOM&from=2026-07-01&to=2026-07-31";
    private static final String TRUST = "20000000-0000-0000-0000-000000000001";

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;

    @Test
    void 넣고_지우면_넣은_돈이_따라_움직인다() throws Exception {
        String token = bearer();
        JsonNode before = data(token);
        assertThat(before.get("deposited").decimalValue()).isEqualByComparingTo("2000000");
        BigDecimal pnlBefore = before.get("investment_pnl").get("total").decimalValue();

        List<String> created = new ArrayList<>();

        // 두 잔고 사이 입금 — 넣은 돈에 들어가고 투자손익이 그만큼 준다.
        created.add(create(token, "DEPOSIT", 1000000, "2026-07-25"));
        JsonNode afterDeposit = data(token);
        assertThat(afterDeposit.get("deposited").decimalValue()).isEqualByComparingTo("3000000");
        assertThat(amountOf(afterDeposit, "DEPOSIT")).isEqualByComparingTo("3000000");
        assertThat(afterDeposit.get("investment_pnl").get("total").decimalValue())
                .isEqualByComparingTo(pnlBefore.subtract(new BigDecimal("1000000")));
        assertIdentity(afterDeposit);

        // 출금은 넣은 돈을 줄이고 따로 한 줄이 된다.
        created.add(create(token, "WITHDRAW", 300000, "2026-07-26"));
        JsonNode afterWithdraw = data(token);
        assertThat(afterWithdraw.get("deposited").decimalValue()).isEqualByComparingTo("2700000");
        assertThat(amountOf(afterWithdraw, "WITHDRAW")).isEqualByComparingTo("-300000");
        assertIdentity(afterWithdraw);

        // 기말 잔고 뒤 날짜는 받되 이 기간에는 세지 않는다.
        created.add(create(token, "DEPOSIT", 500000, "2026-07-28"));
        assertThat(data(token).get("deposited").decimalValue()).isEqualByComparingTo("2700000");
        JsonNode list = body(mockMvc.perform(get("/portfolio/cashflows?from=2026-07-01&to=2026-07-31")
                .header("Authorization", token)).andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8));
        assertThat(list.get("window").get("through").asText()).isEqualTo("2026-07-27");
        assertThat(list.get("cashflows").get(0).get("occurred_on").asText()).isEqualTo("2026-07-28");

        // 모두 지우면 처음으로 돌아온다.
        for (String id : created) {
            assertThat(mockMvc.perform(delete("/portfolio/cashflows/" + id).header("Authorization", token))
                    .andReturn().getResponse().getStatus()).isEqualTo(204);
        }
        JsonNode restored = data(token);
        assertThat(restored.get("deposited").decimalValue()).isEqualByComparingTo("2000000");
        assertThat(restored.get("investment_pnl").get("total").decimalValue()).isEqualByComparingTo(pnlBefore);
    }

    private static void assertIdentity(JsonNode data) {
        assertThat(data.get("closing").decimalValue()).isEqualByComparingTo(
                data.get("opening").decimalValue()
                        .add(data.get("deposited").decimalValue())
                        .add(data.get("earned").decimalValue())
                        .add(data.get("account_included").decimalValue())
                        .subtract(data.get("account_excluded").decimalValue()));
    }

    private static BigDecimal amountOf(JsonNode data, String type) {
        for (JsonNode item : data.get("breakdown")) {
            if (item.get("type").asText().equals(type)) return item.get("amount").decimalValue();
        }
        throw new AssertionError("내역에 없다: " + type);
    }

    private String create(String token, String type, long amount, String occurredOn) throws Exception {
        String response = mockMvc.perform(post("/portfolio/cashflows").header("Authorization", token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"account_id": "%s", "type": "%s", "amount": %d, "occurred_on": "%s"}
                                """.formatted(TRUST, type, amount, occurredOn)))
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        return body(response).get("id").asText();
    }

    private JsonNode data(String token) throws Exception {
        return body(mockMvc.perform(get(JULY).header("Authorization", token)).andReturn()
                .getResponse().getContentAsString(StandardCharsets.UTF_8)).get("data");
    }

    private JsonNode body(String content) throws Exception { return json.readTree(content); }

    private String bearer() throws Exception {
        String body = mockMvc.perform(post("/auth/login").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\": \"yhr@a.com\", \"password\": \"local-dev-password\"}"))
                .andReturn().getResponse().getContentAsString();
        return "Bearer " + json.readTree(body).get("access_token").asText();
    }
}
```

- [ ] **Step 2: 돌린다** (사용자 승인 후)

Run: `./gradlew test --tests 'com.stockproject.portfolio.api.CashflowAssetChangeFlowTest'`
Expected: PASS. Task 4 · 5가 끝난 뒤라 바로 통과해야 한다. 실패하면 Task 1의 옮김이나 구간 계산이 어긋난 것이므로 멈추고 원인을 찾는다(superpowers:systematic-debugging).

- [ ] **Step 3: 커밋 (요청받았을 때)**

```bash
git add src/test/java/com/stockproject/portfolio/api/CashflowAssetChangeFlowTest.java
git commit -m "test: 넣고 지운 입출금이 자산 변화의 넣은 돈에 그대로 반영되는지 본다"
```

---

### Task 7: 계좌별 입출금 미입력 경고

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/query/ManualCashflowMapper.java`
- Modify: `src/main/resources/mapper/ManualCashflowMapper.xml`
- Modify: `src/main/java/com/stockproject/portfolio/query/SnapshotFactsMapper.java`
- Modify: `src/main/java/com/stockproject/portfolio/view/assembly/AssemblyContext.java`
- Modify: `src/main/java/com/stockproject/portfolio/view/assembly/NoticeCollector.java`
- Modify: `src/main/java/com/stockproject/portfolio/view/assembly/NoticeCode.java:27`
- Modify: `src/main/java/com/stockproject/portfolio/view/AssetChangeViewService.java`
- Modify: `src/test/resources/golden/asset-change.json`
- Test: `src/test/java/com/stockproject/portfolio/view/assembly/NoticeCollectorTest.java`
- Test: `src/test/java/com/stockproject/portfolio/api/AssetChangeApiTest.java`

**Interfaces:**
- Consumes: `SnapshotPair.emptyWindow()` (Task 1), `SnapshotFactsMapper.accountsAt(UserScope, LocalDate): List<UUID>` (기존)
- Produces: `ManualCashflowMapper.accountsWithEntries(UserScope scope, LocalDate exclusiveFrom, LocalDate inclusiveTo, LineFilter filter): List<UUID>`; `SnapshotFactsMapper.accountsLinedBefore(UserScope scope, LocalDate asOf): List<UUID>`; `AssemblyContext.manualUncoveredAccountCount()` + `Builder.manualCashflowUncovered(int)`; `CASHFLOW_UNCOVERED.params.manual_uncovered_account_count`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`NoticeCollectorTest`에 셋을 더한다.

```java
    /** 입출금은 계좌마다 사용자가 넣는다. 넣지 않은 계좌 수를 알린다. */
    @Test
    void 입출금을_넣지_않은_계좌를_알린다() {
        NoticeDto notice = find(collector.collect(AssemblyContext.builder(AS_OF)
                .manualCashflowUncovered(2).build()), "CASHFLOW_UNCOVERED");

        assertThat(notice.message())
                .isEqualTo("2개 계좌에 이 기간 입출금이 입력되지 않아 투자손익이 정확하지 않을 수 있어요");
        assertThat(notice.params())
                .containsEntry("types", List.of("DEPOSIT", "WITHDRAW"))
                .containsEntry("manual_uncovered_account_count", 2);
    }

    @Test
    void 배당_수수료와_입출금이_함께_빠지면_한_문장으로_알린다() {
        NoticeDto notice = find(collector.collect(AssemblyContext.builder(AS_OF)
                .uncoveredCashflow(List.of("DIVIDEND", "FEE", "TAX"), 4)
                .manualCashflowUncovered(3).build()), "CASHFLOW_UNCOVERED");

        assertThat(notice.message()).isEqualTo(
                "3개 계좌에 입출금이 입력되지 않았고 배당·수수료 내역도 없어 투자손익이 정확하지 않을 수 있어요");
        assertThat(notice.params())
                .containsEntry("types", List.of("DIVIDEND", "FEE", "TAX", "DEPOSIT", "WITHDRAW"))
                .containsEntry("account_count", 4)
                .containsEntry("manual_uncovered_account_count", 3);
    }

    @Test
    void 입출금이_모두_들어왔으면_배당_수수료만_알린다() {
        NoticeDto notice = find(collector.collect(AssemblyContext.builder(AS_OF)
                .uncoveredCashflow(List.of("DIVIDEND", "FEE", "TAX"), 4).build()), "CASHFLOW_UNCOVERED");

        assertThat(notice.message()).isEqualTo("배당·수수료 내역이 확보되지 않아 투자손익이 정확하지 않을 수 있어요");
        assertThat(notice.params()).containsEntry("types", List.of("DIVIDEND", "FEE", "TAX"))
                .containsEntry("manual_uncovered_account_count", 0);
    }
```

`AssetChangeApiTest` — 기존 `기간_경계와_미확보_내역을_알린다`의 마지막 단언을 바꾸고, 테스트 셋을 더한다.

```java
        assertThat(noticeParam(body, "CASHFLOW_UNCOVERED", "account_count").asInt()).isEqualTo(4);
        assertThat(noticeParam(body, "CASHFLOW_UNCOVERED", "types").toString())
                .isEqualTo("[\"DIVIDEND\",\"FEE\",\"TAX\",\"DEPOSIT\",\"WITHDRAW\"]");
        assertThat(noticeParam(body, "CASHFLOW_UNCOVERED", "manual_uncovered_account_count").asInt())
                .isEqualTo(3);
```

```java
    /** yhr의 네 계좌 중 …001에만 입출금이 있다. 하나를 더 넣으면 그만큼 준다. */
    @Test
    void 입출금을_넣지_않은_계좌를_센다() throws Exception {
        assertThat(noticeParam(fetch(JULY, "yhr"), "CASHFLOW_UNCOVERED",
                "manual_uncovered_account_count").asInt()).isEqualTo(3);

        jdbc.sql("""
                INSERT INTO manual_cashflow (id, account_id, type, amount, currency, occurred_on, memo)
                VALUES (gen_random_uuid(), '20000000-0000-0000-0000-000000000002',
                        'DEPOSIT', 100000, 'KRW', '2026-07-25', NULL)
                """).update();

        assertThat(noticeParam(fetch(JULY, "yhr"), "CASHFLOW_UNCOVERED",
                "manual_uncovered_account_count").asInt()).isEqualTo(2);
    }

    @Test
    void 계좌를_걸면_그_계좌들_안에서_센다() throws Exception {
        JsonNode body = fetch(JULY + "&account=20000000-0000-0000-0000-000000000001", "yhr");

        assertThat(noticeParam(body, "CASHFLOW_UNCOVERED", "manual_uncovered_account_count").asInt())
                .isZero();
        assertThat(noticeParam(body, "CASHFLOW_UNCOVERED", "types").toString())
                .isEqualTo("[\"DIVIDEND\",\"FEE\",\"TAX\"]");
    }

    /** 기초와 기말이 같은 날이면 어떤 입출금도 들어갈 수 없다. 넣으라고 알리지 않는다. */
    @Test
    void 넣은_돈을_세는_구간이_비면_입출금을_따지지_않는다() throws Exception {
        assertThat(noticeParam(fetch(JULY, "hhj"), "CASHFLOW_UNCOVERED", "types").toString())
                .isEqualTo("[\"DIVIDEND\",\"FEE\",\"TAX\"]");
    }

    /**
     * 기말 날에 처음 잔고가 생긴 계좌는 첫 잔고 다음 날부터만 입출금을 받으므로 이 구간에 넣을 날짜가 없다.
     * 세면 경고가 꺼지지 않는다.
     */
    @Test
    void 기말에_처음_잔고가_생긴_계좌는_세지_않는다() throws Exception {
        jdbc.sql("""
                DELETE FROM position_line
                 WHERE account_id = '20000000-0000-0000-0000-000000000003' AND as_of = '2026-07-24'
                """).update();

        assertThat(noticeParam(fetch(JULY, "yhr"), "CASHFLOW_UNCOVERED",
                "manual_uncovered_account_count").asInt()).isEqualTo(2);
    }

    /** 견줄 잔고가 없어 빈 응답이면 입출금을 넣으라고 알리지 않는다. */
    @Test
    void 빈_응답에는_입출금_미입력_경고가_없다() throws Exception {
        JsonNode body = fetch("/portfolio/views/asset-change?period=CUSTOM&from=2026-06-01&to=2026-06-30", "yhr");

        for (JsonNode notice : body.get("notices")) {
            if (notice.get("code").asText().equals("CASHFLOW_UNCOVERED")) {
                assertThat(notice.get("params").get("types").toString()).doesNotContain("DEPOSIT");
            }
        }
    }
```

- [ ] **Step 2: 실패를 확인한다** (사용자 승인 후)

Run: `./gradlew test --tests 'com.stockproject.portfolio.view.assembly.NoticeCollectorTest' --tests 'com.stockproject.portfolio.api.AssetChangeApiTest'`
Expected: 컴파일 실패 — `manualCashflowUncovered`가 없다.

- [ ] **Step 3: 구현한다**

`query/ManualCashflowMapper.java`에 메서드를 더한다.

```java
    /** 그 구간에 입출금이 한 건이라도 있는 계좌. 미입력 경고가 계좌 단위로 센다. */
    List<UUID> accountsWithEntries(@Param("scope") UserScope scope,
                                   @Param("from") LocalDate exclusiveFrom,
                                   @Param("to") LocalDate inclusiveTo,
                                   @Param("filter") LineFilter filter);
```

(import: `java.util.List`, `java.util.UUID`)

`mapper/ManualCashflowMapper.xml`의 `</mapper>` 앞에:

```xml
  <!-- 구간은 totalsBetween과 같다. 넣은 돈에 들어갈 수 있는 입력만 센다. -->
  <select id="accountsWithEntries" resultType="java.util.UUID">
    SELECT DISTINCT m.account_id
      FROM manual_cashflow m
      JOIN account a ON a.account_id = m.account_id
     WHERE a.user_id = #{scope.userId}
       AND m.occurred_on &gt;  #{from}
       AND m.occurred_on &lt;= #{to}
    <if test="filter != null and filter.accountIds.size() > 0">
       AND m.account_id IN
       <foreach item="id" collection="filter.accountIds" open="(" separator="," close=")">#{id}</foreach>
    </if>
  </select>
```

`query/SnapshotFactsMapper.java`의 `accountsAt` 바로 아래에:

```java
    /** 그날보다 앞선 잔고가 있는 계좌. 기말 날에 처음 잔고가 생긴 계좌를 미입력 경고에서 뺄 때 쓴다. */
    @Select("""
            SELECT DISTINCT pl.account_id
              FROM position_line pl JOIN account a USING (account_id)
             WHERE pl.as_of < #{asOf} AND a.user_id = #{scope.userId}
            """)
    List<java.util.UUID> accountsLinedBefore(@Param("scope") UserScope scope, @Param("asOf") LocalDate asOf);
```

`AssemblyContext` — 레코드 구성 요소에 `int manualUncoveredAccountCount`를 `cashflowUncoveredAccountCount` 바로 뒤에 더한다.

```java
        List<String> uncoveredCashflowTypes, int cashflowUncoveredAccountCount,
        int manualUncoveredAccountCount,
```

Builder에 필드와 메서드를 더하고 `build()`의 인자에도 같은 자리에 넣는다.

```java
        private int manualUncoveredAccountCount;
```

```java
        /** 넣은 돈을 세는 구간에 입출금이 한 건도 없는 계좌 수. */
        public Builder manualCashflowUncovered(int accountCount) {
            this.manualUncoveredAccountCount = accountCount;
            return this;
        }
```

```java
                    uncoveredCashflowTypes, cashflowUncoveredAccountCount,
                    manualUncoveredAccountCount,
```

`NoticeCollector.cashflowUncovered`를 바꾼다.

```java
    /**
     * 투자손익은 나머지 전부라, 빠진 현금흐름이 그만큼 섞인다. 배당 · 수수료는 원천이 주지 않은 것이고
     * 입출금은 사용자가 넣지 않은 것이라 문장이 다르다. 넣지 않은 것인지 정말 없었던 것인지는
     * 가를 수 없어 단정하지 않는다.
     */
    private NoticeDto cashflowUncovered(AssemblyContext context) {
        boolean earnings = !context.uncoveredCashflowTypes().isEmpty();
        int manual = context.manualUncoveredAccountCount();
        if (!earnings && manual == 0) return null;

        List<String> types = new ArrayList<>(context.uncoveredCashflowTypes());
        if (manual > 0) {
            types.add("DEPOSIT");
            types.add("WITHDRAW");
        }
        String message = !earnings
                ? "%d개 계좌에 이 기간 입출금이 입력되지 않아 투자손익이 정확하지 않을 수 있어요".formatted(manual)
                : manual == 0
                ? "배당·수수료 내역이 확보되지 않아 투자손익이 정확하지 않을 수 있어요"
                : "%d개 계좌에 입출금이 입력되지 않았고 배당·수수료 내역도 없어 투자손익이 정확하지 않을 수 있어요"
                        .formatted(manual);
        return notice(NoticeCode.CASHFLOW_UNCOVERED, message,
                params("types", types,
                        "account_count", context.cashflowUncoveredAccountCount(),
                        "manual_uncovered_account_count", manual));
    }
```

`NoticeCode.java:27`의 주석:

```java
    /** 배당·수수료 내역이나 입출금 입력이 빠져 투자손익이 정확하지 않을 수 있다. */
```

`AssetChangeViewService` — `context(…)`에 미입력 계좌 수를 넘긴다. `render`에서:

```java
        int manualUncovered = pair.get().emptyWindow() ? 0 : manualUncovered(scope, pair.get(), filter);
```

```java
                notices.collect(context(scope, reference, ownedAccounts, earnedCash, manualUncovered,
                        pair.get().openingSubstituted() ? openingAsOf : null,
                        openingAsOf, closingAsOf)));
```

`context`의 시그니처와 본문:

```java
    private AssemblyContext context(UserScope scope, LocalDate reference,
                                    List<AccountRow> ownedAccounts, EarningsCashflowTotals earnedCash,
                                    int manualUncovered,
                                    LocalDate actualFrom, LocalDate openingAsOf, LocalDate closingAsOf) {
        AssemblyContext.Builder context = AssemblyContext.builder(reference)
                .accounts(ownedAccounts)
                .uncoveredCashflow(uncoveredTypes(earnedCash),
                        uncoveredAccountCount(ownedAccounts, earnedCash))
                .manualCashflowUncovered(manualUncovered);
```

새 메서드:

```java
    /**
     * 기말 잔고에 있는 계좌 중, 넣은 돈을 세는 구간에 입출금이 한 건도 없는 계좌 수.
     * 기간 중에 빠진 계좌는 기말 잔고에 없어 세지 않는다. 계좌 필터를 걸었으면 그 안에서 센다.
     * 기말 날에 처음 잔고가 생긴 계좌도 세지 않는다 — 입출금은 첫 잔고 다음 날부터 받아 이 구간에 넣을 날짜가 없다.
     */
    private int manualUncovered(UserScope scope, SnapshotPair pair, LineFilter filter) {
        Set<UUID> accountsAtClosing = new LinkedHashSet<>(facts.accountsAt(scope, pair.closing()));
        accountsAtClosing.retainAll(facts.accountsLinedBefore(scope, pair.closing()));
        if (!filter.accountIds().isEmpty()) accountsAtClosing.retainAll(filter.accountIds());
        accountsAtClosing.removeAll(
                manualCashflow.accountsWithEntries(scope, pair.opening(), pair.closing(), filter));
        return accountsAtClosing.size();
    }
```

`src/test/resources/golden/asset-change.json`의 `CASHFLOW_UNCOVERED` 블록:

```json
  "notices" : [ {
    "code" : "CASHFLOW_UNCOVERED",
    "severity" : "warn",
    "message" : "3개 계좌에 입출금이 입력되지 않았고 배당·수수료 내역도 없어 투자손익이 정확하지 않을 수 있어요",
    "params" : {
      "types" : [ "DIVIDEND", "FEE", "TAX", "DEPOSIT", "WITHDRAW" ],
      "account_count" : 4,
      "manual_uncovered_account_count" : 3
    }
  }, {
```

- [ ] **Step 4: 통과를 확인한다** (사용자 승인 후)

Run: `./gradlew test --tests 'com.stockproject.portfolio.view.assembly.NoticeCollectorTest' --tests 'com.stockproject.portfolio.api.AssetChangeApiTest' --tests 'com.stockproject.portfolio.api.SixViewGoldenTest' --tests 'com.stockproject.portfolio.auth.ScopeSignatureTest'`
Expected: PASS.

- [ ] **Step 5: 백엔드 전체를 돌린다** (사용자 승인 후)

Run: `./gradlew test`
Expected: BUILD SUCCESSFUL. 실패가 있으면 출력 그대로 보고하고 멈춘다.

- [ ] **Step 6: 커밋 (요청받았을 때)**

```bash
git add src/main/java/com/stockproject/portfolio/query/ManualCashflowMapper.java \
        src/main/java/com/stockproject/portfolio/query/SnapshotFactsMapper.java \
        src/main/resources/mapper/ManualCashflowMapper.xml \
        src/main/java/com/stockproject/portfolio/view \
        src/test/java/com/stockproject/portfolio/view/assembly/NoticeCollectorTest.java \
        src/test/java/com/stockproject/portfolio/api/AssetChangeApiTest.java \
        src/test/resources/golden/asset-change.json
git commit -m "feat: 입출금을 넣지 않은 계좌 수를 자산 변화에 알린다"
```

---

## B. 앱

브랜치 준비: `git -C /Users/yhr/Dev/workspace/personal/stock-project/front-end switch -c feat/manual-cashflow-input main` (작업 트리가 깨끗한지 먼저 `git status`로 본다).

앱 테스트는 `npx jest <파일>`로 돌린다. 서버 · DB에 닿지 않으므로 승인 없이 돌린다.

### Task 8: 입출금 API 클라이언트 — 타입 · 요청 · 조회 · 변경

**Files:**
- Modify: `src/api/types.ts`
- Modify: `src/api/client.ts` (주석 한 줄)
- Modify: `src/api/endpoints.ts`
- Modify: `src/api/queries/keys.ts`
- Create: `src/api/queries/useCashflows.ts`
- Create: `src/api/queries/cashflowInvalidation.ts`
- Create: `src/api/queries/useCashflowActions.ts`
- Test: `src/__tests__/cashflowApi.test.tsx`

**Interfaces:**
- Consumes: `apiGet` · `apiPost` · `apiDelete` (기존 `api/client.ts`), 서버 응답 모양(Task 4 · 5)
- Produces:
  - 타입 `ManualCashflowType` · `CashflowEntry` · `CashflowWindow` · `CashflowListResponse` · `CashflowRequest`
  - `fetchCashflows(query: CashflowQuery): Promise<CashflowListResponse>` · `createCashflow(request: CashflowRequest): Promise<{ id: string }>` · `deleteCashflow(id: string): Promise<void>` · `type CashflowQuery = { from: string; to: string; account: string[] }`
  - `keys.cashflows(p: CashflowQuery)` → `['cashflows', p]`
  - `useCashflows(query): { list, loading, error, refetch }`
  - `invalidateCashflowData(queryClient)` — `['cashflows']` · `['asset-change']`
  - `useCashflowActions(): { save, remove }` — `useMutation` 둘

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```tsx
import { QueryClient } from '@tanstack/react-query';

import { setAccessToken } from '@/api/client';
import { createCashflow, deleteCashflow, fetchCashflows } from '@/api/endpoints';
import { invalidateCashflowData } from '@/api/queries/cashflowInvalidation';
import type { CashflowRequest } from '@/api/types';
import { serveRoutes } from '@/testing/serveRoutes';

beforeEach(() => setAccessToken('테스트-토큰'));
afterEach(() => setAccessToken(null));

const REQUEST: CashflowRequest = {
  account_id: '20000000-0000-0000-0000-000000000001',
  type: 'DEPOSIT',
  amount: 2000000,
  currency: 'KRW',
  occurred_on: '2026-07-25',
  memo: null,
};

describe('입출금 요청', () => {
  it('목록은 기간과 계좌를 싣고, 계좌는 같은 이름을 반복한다', async () => {
    const calls = serveRoutes([{ path: '/portfolio/cashflows', body: { window: null, cashflows: [] } }]);

    await fetchCashflows({ from: '2026-07-01', to: '2026-07-31', account: ['A', 'B'] });

    expect(calls[0].url).toBe(
      'http://api.test:8080/portfolio/cashflows?from=2026-07-01&to=2026-07-31&account=A&account=B',
    );
  });

  it('저장은 요청을 그대로 보내고 id를 돌려받는다', async () => {
    const calls = serveRoutes([
      { method: 'POST', path: '/portfolio/cashflows', status: 201, body: { id: 'new-id' } },
    ]);

    await expect(createCashflow(REQUEST)).resolves.toEqual({ id: 'new-id' });
    expect(calls[0].body).toEqual(REQUEST);
  });

  it('삭제는 그 id의 경로로 간다', async () => {
    const calls = serveRoutes([
      { method: 'DELETE', path: /^\/portfolio\/cashflows\/.+$/, status: 204 },
    ]);

    await deleteCashflow('c1');

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/portfolio/cashflows/c1' });
  });
});

describe('입출금을 바꾼 뒤', () => {
  it('목록과 자산 변화를 다시 받는다 — 요약도 자산 변화 조회를 쓴다', () => {
    const queryClient = new QueryClient();
    const spy = jest.spyOn(queryClient, 'invalidateQueries');

    invalidateCashflowData(queryClient);

    expect(spy.mock.calls.map(([filters]) => filters?.queryKey)).toEqual([
      ['cashflows'],
      ['asset-change'],
    ]);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `npx jest src/__tests__/cashflowApi.test.tsx`
Expected: FAIL — `createCashflow` 등이 없다(타입 오류 · undefined).

- [ ] **Step 3: 구현한다**

`src/api/types.ts` — `/* ── 오류 ── */` 묶음 앞에 둔다.

```ts
/* ── 입출금 입력 ──────────────────────────────────────────────────── */

/** 사용자가 넣는 현금흐름. 배당·수수료는 증권사 원장에서 오므로 여기 없다. */
export type ManualCashflowType = 'DEPOSIT' | 'WITHDRAW';

export type CashflowEntry = {
  id: string;
  account_id: string;
  account_label: string;
  type: ManualCashflowType;
  /** 양수. 출금도 양수로 오고 화면이 부호를 붙인다. */
  amount: number;
  currency: 'KRW';
  occurred_on: string;
  memo: string | null;
};

/**
 * 같은 기간 자산 변화가 넣은 돈을 세는 구간 `(after, through]`.
 * 이 밖의 입출금은 그 기간 자산 변화에 들어가지 않는다.
 */
export type CashflowWindow = { after: string; through: string };

/** 뷰가 아니라 사용자가 넣은 기록이라 봉투를 쓰지 않는다. 잔고가 없으면 `window`가 null이다. */
export type CashflowListResponse = {
  window: CashflowWindow | null;
  cashflows: CashflowEntry[];
};

/** 계좌를 고르지 않았으면 `account_id`가 null로 나가고 서버가 칸 오류로 답한다. */
export type CashflowRequest = {
  account_id: string | null;
  type: ManualCashflowType;
  amount: number;
  currency: 'KRW';
  occurred_on: string;
  memo: string | null;
};
```

같은 파일 `ApiErrorBody`의 `fields` 주석:

```ts
    /** 알림 저장의 `INVALID_ALERT`와 입출금 저장의 `INVALID_CASHFLOW`(400)에만 실린다. */
    fields?: FieldError[];
```

`src/api/client.ts`의 `ApiError.fields` 주석도 같은 사실로 맞춘다.

```ts
  /** 칸별 검증 오류. 알림 저장과 입출금 저장의 400만 싣고, 그 밖에는 빈 목록이다. */
  readonly fields: FieldError[];
```

`src/api/endpoints.ts` — import에 `apiDelete` · `apiPost` · `CashflowListResponse` · `CashflowRequest`를 더하고 끝에 붙인다.

```ts
export type CashflowQuery = {
  /** 양 끝을 포함한다. 자산 변화 응답의 `period`를 그대로 넘긴다. */
  from: string;
  to: string;
  account: string[];
};

export function fetchCashflows(query: CashflowQuery): Promise<CashflowListResponse> {
  return apiGet<CashflowListResponse>('/portfolio/cashflows', {
    from: query.from,
    to: query.to,
    account: query.account,
  });
}

export function createCashflow(request: CashflowRequest): Promise<{ id: string }> {
  return apiPost<{ id: string }>('/portfolio/cashflows', request);
}

export function deleteCashflow(id: string): Promise<void> {
  return apiDelete(`/portfolio/cashflows/${encodeURIComponent(id)}`);
}
```

`src/api/queries/keys.ts` — 타입 import와 키 하나:

```ts
import type { CashflowQuery } from '@/api/endpoints';
```

```ts
  cashflows: (p: CashflowQuery) => ['cashflows', p] as const,
```

`src/api/queries/useCashflows.ts`:

```ts
import { useQuery } from '@tanstack/react-query';

import { fetchCashflows } from '@/api/endpoints';
import type { CashflowQuery } from '@/api/endpoints';
import { keys } from '@/api/queries/keys';
import type { CashflowListResponse } from '@/api/types';

/** 보던 기간에 넣은 입출금과, 그 기간 자산 변화가 넣은 돈을 세는 구간. */
export function useCashflows(query: CashflowQuery) {
  const result = useQuery<CashflowListResponse>({
    queryKey: keys.cashflows(query),
    queryFn: () => fetchCashflows(query),
  });

  return {
    list: result.data ?? null,
    loading: result.isPending,
    error: result.error ?? undefined,
    refetch: () => void result.refetch(),
  };
}
```

`src/api/queries/cashflowInvalidation.ts`:

```ts
import type { QueryClient } from '@tanstack/react-query';

/**
 * 입출금을 넣거나 지운 뒤 다시 받을 것들. 자산 변화의 넣은 돈이 바뀌고, 요약도 같은
 * 자산 변화 조회를 쓰므로 함께 다시 받는다.
 */
export function invalidateCashflowData(queryClient: QueryClient): void {
  for (const queryKey of [['cashflows'], ['asset-change']]) {
    void queryClient.invalidateQueries({ queryKey });
  }
}
```

`src/api/queries/useCashflowActions.ts`:

```ts
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { createCashflow, deleteCashflow } from '@/api/endpoints';
import { invalidateCashflowData } from '@/api/queries/cashflowInvalidation';

/** 입출금 저장과 삭제. 어느 쪽이든 끝나면 목록과 자산 변화를 다시 받는다. */
export function useCashflowActions() {
  const queryClient = useQueryClient();
  const refresh = () => invalidateCashflowData(queryClient);

  return {
    save: useMutation({ mutationFn: createCashflow, onSuccess: refresh }),
    remove: useMutation({ mutationFn: deleteCashflow, onSuccess: refresh }),
  };
}
```

- [ ] **Step 4: 통과와 타입을 확인한다**

Run: `npx jest src/__tests__/cashflowApi.test.tsx && npx tsc --noEmit`
Expected: PASS, 타입 오류 없음.

- [ ] **Step 5: 커밋 (요청받았을 때)**

```bash
git add src/api src/__tests__/cashflowApi.test.tsx
git commit -m "feat: 입출금 목록 · 저장 · 삭제 요청과 캐시 무효화를 둔다"
```

---

### Task 9: 입출금 화면 — 입력 폼

**Files:**
- Create: `src/screens/cashflows/form.ts`
- Create: `src/screens/cashflows/windowNote.ts`
- Create: `src/screens/cashflows/AccountPickerSheet.tsx`
- Create: `src/screens/cashflows/CashflowForm.tsx`
- Create: `src/screens/cashflows/CashflowsScreen.tsx`
- Modify: `src/app/navigation/types.ts`
- Test: `src/__tests__/cashflowForm.test.ts`
- Test: `src/__tests__/cashflows.test.tsx`

**Interfaces:**
- Consumes: `useCashflows` · `useCashflowActions` (Task 8), `useCatalog` · `todayIso` · `errorAt` · `messageOf` · `ApiError` (기존)
- Produces:
  - `RootStackParamList['cashflows'] = { from: string; to: string; account?: string[] }`
  - `form.ts`: `type CashflowsParams` · `type FormState` · `initialForm(params, accounts, today)` · `digitsOf(text)` · `groupDigits(digits)` · `toRequest(form)`
  - `windowNote(date: string, window: CashflowWindow | null): string | null`
  - `CashflowsScreen` (Task 10이 목록을 붙이고, Task 11이 라우트에 등록한다)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/__tests__/cashflowForm.test.ts`:

```ts
import type { CatalogAccount } from '@/api/types';
import { digitsOf, groupDigits, initialForm, toRequest } from '@/screens/cashflows/form';
import { windowNote } from '@/screens/cashflows/windowNote';

const account = (id: string): CatalogAccount => ({
  account_id: id,
  broker: '한국투자증권',
  label: id,
  account_type: 'GENERAL',
  link_state: 'CONNECTED',
});

describe('금액 칸', () => {
  it('숫자만 남긴다 — 붙여넣은 쉼표와 단위를 버린다', () => {
    expect(digitsOf('2,000,000원')).toBe('2000000');
  });

  it('앞에 친 0을 버린다', () => {
    expect(digitsOf('007')).toBe('7');
    expect(digitsOf('0')).toBe('0');
    expect(digitsOf('')).toBe('');
  });

  it('15자리를 넘기지 않는다', () => {
    expect(digitsOf('1'.repeat(20))).toBe('1'.repeat(15));
  });

  it('천 단위로 끊어 보인다', () => {
    expect(groupDigits('2000000')).toBe('2,000,000');
    expect(groupDigits('')).toBe('');
  });
});

describe('처음 값', () => {
  const params = { from: '2026-07-01', to: '2026-07-31' };

  it('넘겨받은 계좌가 하나면 그 계좌다', () => {
    expect(initialForm({ ...params, account: ['B'] }, [account('A'), account('B')], '2026-10-17').accountId).toBe('B');
  });

  it('계좌가 하나뿐이면 그 계좌다', () => {
    expect(initialForm(params, [account('A')], '2026-10-17').accountId).toBe('A');
  });

  it('그 밖에는 비어 있다', () => {
    expect(initialForm(params, [account('A'), account('B')], '2026-10-17').accountId).toBeNull();
    expect(initialForm({ ...params, account: ['A', 'B'] }, [account('A'), account('B')], '2026-10-17').accountId).toBeNull();
  });

  it('날짜는 기간 끝과 오늘 중 이른 날이다', () => {
    expect(initialForm(params, [], '2026-10-17').date).toBe('2026-07-31');
    expect(initialForm({ from: '2026-10-01', to: '2026-10-31' }, [], '2026-10-17').date).toBe('2026-10-17');
  });
});

describe('보낼 값', () => {
  it('메모의 앞뒤 공백을 지우고 비면 null이다', () => {
    const form = { accountId: 'A', type: 'DEPOSIT' as const, amountDigits: '2000000', date: '2026-07-25', memo: '  ' };
    expect(toRequest(form)).toEqual({
      account_id: 'A', type: 'DEPOSIT', amount: 2000000, currency: 'KRW', occurred_on: '2026-07-25', memo: null,
    });
    expect(toRequest({ ...form, memo: ' 월급 ' }).memo).toBe('월급');
  });

  it('금액이 비면 0을 보내 서버가 칸 오류로 답하게 한다', () => {
    expect(toRequest({ accountId: null, type: 'WITHDRAW', amountDigits: '', date: '2026-07-25', memo: '' }))
      .toMatchObject({ account_id: null, type: 'WITHDRAW', amount: 0 });
  });
});

describe('넣은 돈 구간 안내', () => {
  const window = { after: '2026-07-24', through: '2026-07-27' };

  it('구간 안이면 안내가 없다', () => {
    expect(windowNote('2026-07-25', window)).toBeNull();
    expect(windowNote('2026-07-27', window)).toBeNull();
  });

  it('기말 잔고 뒤면 다음 잔고부터라고 한다', () => {
    expect(windowNote('2026-07-28', window)).toBe('07-27 잔고 이후라 다음 잔고부터 반영돼요');
  });

  it('기초 잔고 날짜 이하면 이미 들어간 돈이라고 한다', () => {
    expect(windowNote('2026-07-24', window)).toBe('07-24 잔고에 이미 들어간 돈이라 이 기간에는 세지 않아요');
    expect(windowNote('2026-07-03', window)).toBe('07-24 잔고에 이미 들어간 돈이라 이 기간에는 세지 않아요');
  });

  it('잔고가 없으면 말하지 않는다', () => {
    expect(windowNote('2026-07-25', null)).toBeNull();
  });
});
```

`src/__tests__/cashflows.test.tsx` (Task 10이 목록 테스트를 더한다):

```tsx
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import { setAccessToken } from '@/api/client';
import type { CashflowListResponse, CatalogAccount } from '@/api/types';
import { CashflowsScreen } from '@/screens/cashflows/CashflowsScreen';
import { renderWithStack } from '@/testing/renderWithStack';
import { type Call, type Route, serveRoutes } from '@/testing/serveRoutes';
import { todayIso } from '@/ui/period';

const TRUST: CatalogAccount = {
  account_id: '20000000-0000-0000-0000-000000000001',
  broker: '한국투자증권',
  label: '한국투자 위탁',
  account_type: 'GENERAL',
  link_state: 'CONNECTED',
};
const IRP: CatalogAccount = {
  account_id: '20000000-0000-0000-0000-000000000003',
  broker: '한국투자증권',
  label: '한국투자 IRP',
  account_type: 'PENSION',
  link_state: 'CONNECTED',
};
const PENSION_OFF: CatalogAccount = {
  account_id: '20000000-0000-0000-0000-000000000004',
  broker: '미래에셋증권',
  label: '미래에셋 연금',
  account_type: 'PENSION',
  link_state: 'DISCONNECTED',
};

const JULY = { from: '2026-07-01', to: '2026-07-31' };
const WINDOW = { after: '2026-07-24', through: '2026-07-27' };
const EMPTY: CashflowListResponse = { window: WINDOW, cashflows: [] };

type Options = {
  accounts?: CatalogAccount[];
  list?: Route;
  post?: Partial<Route>;
  del?: Partial<Route>;
};

function routes(options: Options = {}): Route[] {
  return [
    {
      path: '/portfolio/catalog',
      body: { axes: [], metrics: [], accounts: options.accounts ?? [TRUST, IRP, PENSION_OFF], views: [] },
    },
    options.list ?? { path: '/portfolio/cashflows', body: EMPTY },
    { method: 'POST', path: '/portfolio/cashflows', status: 201, body: { id: 'new-id' }, ...options.post },
    { method: 'DELETE', path: /^\/portfolio\/cashflows\/.+$/, status: 204, ...options.del },
  ];
}

async function open(params: object, options?: Options): Promise<Call[]> {
  const calls = serveRoutes(routes(options));
  await renderWithStack('cashflows', CashflowsScreen, params);
  await waitFor(() => expect(screen.getByRole('button', { name: '계좌 고르기' })).toBeTruthy());
  return calls;
}

const accountField = () => within(screen.getByRole('button', { name: '계좌 고르기' }));
const posts = (calls: Call[]) => calls.filter((call) => call.method === 'POST');
const listFetches = (calls: Call[]) =>
  calls.filter((call) => call.method === 'GET' && call.path === '/portfolio/cashflows');

beforeEach(() => setAccessToken('테스트-토큰'));
afterEach(() => setAccessToken(null));

describe('폼의 처음 값', () => {
  it('넘겨받은 계좌가 하나면 골라 둔다', async () => {
    await open({ ...JULY, account: [TRUST.account_id] });
    expect(accountField().getByText('한국투자 위탁')).toBeTruthy();
  });

  it('계좌가 하나뿐이면 골라 둔다', async () => {
    await open(JULY, { accounts: [TRUST] });
    expect(accountField().getByText('한국투자 위탁')).toBeTruthy();
  });

  it('그 밖에는 비워 둔다', async () => {
    await open(JULY);
    expect(accountField().getByText('계좌 선택')).toBeTruthy();
  });

  it('해제한 계좌로 들어오면 그 계좌에 해제됨을 단다', async () => {
    await open({ ...JULY, account: [PENSION_OFF.account_id] });
    expect(accountField().getByText('미래에셋 연금')).toBeTruthy();
    expect(accountField().getByText('해제됨')).toBeTruthy();
  });

  it('날짜는 기간 끝과 오늘 중 이른 날이다', async () => {
    await open(JULY);
    expect(within(screen.getByRole('button', { name: '날짜' })).getByText('2026-07-31')).toBeTruthy();
  });

  it('기간이 오늘을 넘으면 오늘이다', async () => {
    await open({ from: '2099-01-01', to: '2099-12-31' });
    expect(within(screen.getByRole('button', { name: '날짜' })).getByText(todayIso())).toBeTruthy();
  });
});

describe('계좌 고르기', () => {
  it('해제한 계좌는 맨 아래에 해제됨으로 나온다', async () => {
    await open(JULY, { accounts: [PENSION_OFF, TRUST, IRP] });

    await fireEvent.press(screen.getByRole('button', { name: '계좌 고르기' }));
    const names = screen.getAllByRole('radio').map((row) => row.props.accessibilityLabel);
    expect(names).toEqual(['한국투자 위탁', '한국투자 IRP', '미래에셋 연금']);

    await fireEvent.press(screen.getByRole('radio', { name: '한국투자 IRP' }));
    expect(accountField().getByText('한국투자 IRP')).toBeTruthy();
  });
});

describe('저장', () => {
  it('붙여넣은 금액을 숫자만 남겨 보낸다', async () => {
    const calls = await open({ ...JULY, account: [TRUST.account_id] });

    await fireEvent.changeText(screen.getByLabelText('금액'), '2,000,000원');
    expect(screen.getByLabelText('금액').props.value).toBe('2,000,000');
    await fireEvent.changeText(screen.getByLabelText('메모'), '  ');
    await fireEvent.press(screen.getByRole('button', { name: '저장' }));

    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    expect(posts(calls)[0].body).toEqual({
      account_id: TRUST.account_id,
      type: 'DEPOSIT',
      amount: 2000000,
      currency: 'KRW',
      occurred_on: '2026-07-31',
      memo: null,
    });
  });

  it('앞에 친 0은 버린다', async () => {
    await open({ ...JULY, account: [TRUST.account_id] });
    await fireEvent.changeText(screen.getByLabelText('금액'), '007');
    expect(screen.getByLabelText('금액').props.value).toBe('7');
  });

  it('출금을 고르면 출금으로 보낸다', async () => {
    const calls = await open({ ...JULY, account: [TRUST.account_id] });

    await fireEvent.press(screen.getByRole('tab', { name: '출금' }));
    await fireEvent.changeText(screen.getByLabelText('금액'), '300000');
    await fireEvent.press(screen.getByRole('button', { name: '저장' }));

    await waitFor(() => expect(posts(calls)).toHaveLength(1));
    expect(posts(calls)[0].body).toMatchObject({ type: 'WITHDRAW', amount: 300000 });
  });

  it('성공하면 금액과 메모만 비우고 목록을 다시 받는다', async () => {
    const calls = await open({ ...JULY, account: [TRUST.account_id] });
    const before = listFetches(calls).length;

    await fireEvent.changeText(screen.getByLabelText('금액'), '1000');
    await fireEvent.changeText(screen.getByLabelText('메모'), '월급');
    await fireEvent.press(screen.getByRole('button', { name: '저장' }));

    await waitFor(() => expect(screen.getByLabelText('금액').props.value).toBe(''));
    expect(screen.getByLabelText('메모').props.value).toBe('');
    expect(accountField().getByText('한국투자 위탁')).toBeTruthy();
    expect(within(screen.getByRole('button', { name: '날짜' })).getByText('2026-07-31')).toBeTruthy();
    await waitFor(() => expect(listFetches(calls).length).toBeGreaterThan(before));
  });

  it('저장 중에는 두 번 눌러도 한 번만 보낸다', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const calls = await open({ ...JULY, account: [TRUST.account_id] }, { post: { wait: () => gate } });

    await fireEvent.changeText(screen.getByLabelText('금액'), '1000');
    // 둘째 누름이 첫째 누름의 렌더보다 먼저 닿도록 기다리지 않고 겹쳐 부른다.
    const first = fireEvent.press(screen.getByRole('button', { name: '저장' }));
    const second = fireEvent.press(screen.getByRole('button', { name: '저장' }));
    await act(async () => {
      release();
    });
    await Promise.all([first, second]);

    await waitFor(() => expect(screen.getByLabelText('금액').props.value).toBe(''));
    expect(posts(calls)).toHaveLength(1);
  });

  it('칸 오류는 그 칸 아래에 서버 문장으로 나오고, 칸을 고치면 사라진다', async () => {
    const message = '연동을 해제한 계좌는 07-27까지만 입력할 수 있어요';
    await open({ ...JULY, account: [PENSION_OFF.account_id] }, {
      post: {
        status: 400,
        body: {
          error: {
            code: 'INVALID_CASHFLOW',
            message: '입력을 확인해 주세요',
            fields: [{ path: 'occurred_on', code: 'AFTER_DISCONNECTED', message }],
          },
        },
      },
    });

    await fireEvent.changeText(screen.getByLabelText('금액'), '1000');
    await fireEvent.press(screen.getByRole('button', { name: '저장' }));
    await waitFor(() => expect(screen.getByText(message)).toBeTruthy());

    await fireEvent.changeText(screen.getByLabelText('금액'), '2000');
    await waitFor(() => expect(screen.queryByText(message)).toBeNull());
  });

  it('계좌를 고르지 않으면 서버가 준 문장이 계좌 칸 아래에 나온다', async () => {
    const calls = await open(JULY, {
      post: {
        status: 400,
        body: {
          error: {
            code: 'INVALID_CASHFLOW',
            message: '입력을 확인해 주세요',
            fields: [{ path: 'account_id', code: 'REQUIRED', message: '계좌를 골라 주세요' }],
          },
        },
      },
    });

    await fireEvent.press(screen.getByRole('button', { name: '저장' }));

    await waitFor(() => expect(screen.getByText('계좌를 골라 주세요')).toBeTruthy());
    expect(posts(calls)[0].body).toMatchObject({ account_id: null });
  });

  it('칸에 붙지 않는 실패는 버튼 위 한 줄이다', async () => {
    await open({ ...JULY, account: [TRUST.account_id] }, {
      post: {
        status: 403,
        body: { error: { code: 'FORBIDDEN_ACCOUNT', message: '요청한 계좌 중 본인 소유가 아닌 것이 있습니다' } },
      },
    });

    await fireEvent.changeText(screen.getByLabelText('금액'), '1000');
    await fireEvent.press(screen.getByRole('button', { name: '저장' }));

    await waitFor(() =>
      expect(screen.getByText('요청한 계좌 중 본인 소유가 아닌 것이 있습니다')).toBeTruthy(),
    );
  });
});

describe('날짜 칸 안내', () => {
  it('기말 잔고 뒤 날짜면 다음 잔고부터 반영된다고 알린다', async () => {
    await open(JULY);
    expect(await screen.findByText('07-27 잔고 이후라 다음 잔고부터 반영돼요')).toBeTruthy();
  });
  // 안내가 없는 경우는 목록 머리줄이 그려진 뒤에야 확인할 수 있어 Task 10의 「날짜 칸 안내가 없는 경우」에 둔다.
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `npx jest src/__tests__/cashflowForm.test.ts src/__tests__/cashflows.test.tsx`
Expected: FAIL — `screens/cashflows` 모듈이 없다.

- [ ] **Step 3: 구현한다**

`src/app/navigation/types.ts`의 `RootStackParamList`에 `asset-change` 다음으로:

```ts
  /** 넣은 돈을 넣는 화면. 자산 변화가 보던 기간과 계좌를 넘긴다. */
  cashflows: { from: string; to: string; account?: string[] };
```

`src/screens/cashflows/form.ts`:

```ts
import type { CashflowRequest, CatalogAccount, ManualCashflowType } from '@/api/types';

/** 자산 변화가 넘기는 값. 기간은 그 화면 응답의 `period`이고 계좌는 그 화면의 필터다. */
export type CashflowsParams = { from: string; to: string; account?: string[] };

export type FormState = {
  accountId: string | null;
  type: ManualCashflowType;
  /** 숫자만. 화면에는 천 단위로 끊어 보인다. */
  amountDigits: string;
  date: string;
  memo: string;
};

/** 서버가 받는 금액 자릿수. 이보다 길게 치는 것은 오타다. */
const MAX_DIGITS = 15;

/**
 * 계좌는 정해진 경우에만 미리 고른다 — 필터가 계좌 하나였거나 계좌가 하나뿐일 때.
 * 엉뚱한 계좌에 조용히 들어가는 것보다 한 번 더 누르게 하는 편이 낫다.
 * 날짜는 보던 기간의 끝이되 오늘을 넘지 않는다. 지난달을 보다 왔으면 그 달 말일이다.
 */
export function initialForm(params: CashflowsParams, accounts: CatalogAccount[], today: string): FormState {
  const accountId =
    params.account?.length === 1
      ? params.account[0]
      : accounts.length === 1
        ? accounts[0].account_id
        : null;
  return {
    accountId,
    type: 'DEPOSIT',
    amountDigits: '',
    date: params.to < today ? params.to : today,
    memo: '',
  };
}

/** 붙여넣은 `2,000,000원`이나 앞에 친 0을 정리한다. */
export function digitsOf(text: string): string {
  return text.replace(/\D/g, '').replace(/^0+(?=\d)/, '').slice(0, MAX_DIGITS);
}

export function groupDigits(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/** 비어 있는 칸도 그대로 보낸다. 무엇이 틀렸는지는 서버가 칸별로 답한다. */
export function toRequest(form: FormState): CashflowRequest {
  const memo = form.memo.trim();
  return {
    account_id: form.accountId,
    type: form.type,
    amount: form.amountDigits === '' ? 0 : Number(form.amountDigits),
    currency: 'KRW',
    occurred_on: form.date,
    memo: memo === '' ? null : memo,
  };
}
```

`src/screens/cashflows/windowNote.ts`:

```ts
import type { CashflowWindow } from '@/api/types';
import { formatMonthDay } from '@/format/date';

/**
 * 그 날짜의 입출금이 보던 기간 자산 변화의 넣은 돈에 들어가지 않으면 그 이유. 들어가면 null.
 * 구간은 `(after, through]`다 — `after` 잔고에는 그날 입금이 이미 들어 있다.
 */
export function windowNote(date: string, window: CashflowWindow | null): string | null {
  if (!window) return null;
  if (date > window.through) {
    return `${formatMonthDay(window.through)} 잔고 이후라 다음 잔고부터 반영돼요`;
  }
  if (date <= window.after) {
    return `${formatMonthDay(window.after)} 잔고에 이미 들어간 돈이라 이 기간에는 세지 않아요`;
  }
  return null;
}
```

`src/screens/cashflows/AccountPickerSheet.tsx`:

```tsx
import { Pressable, StyleSheet, Text } from 'react-native';

import type { CatalogAccount } from '@/api/types';
import { useTheme } from '@/design/theme';
import { size, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { Badge } from '@/ui/Badge';
import { BottomSheet } from '@/ui/BottomSheet';

/**
 * 계좌 하나를 고른다. 해제한 계좌도 지난 기간의 넣은 돈을 고칠 수 있어 목록에 두되,
 * 먼저 눈에 띌 계좌는 아니라 맨 아래로 보낸다.
 */
export function AccountPickerSheet({
  visible,
  accounts,
  selected,
  onPick,
  onClose,
}: {
  visible: boolean;
  accounts: CatalogAccount[];
  selected: string | null;
  onPick: (accountId: string) => void;
  onClose: () => void;
}) {
  const palette = useTheme();
  const ordered = [
    ...accounts.filter((one) => one.link_state !== 'DISCONNECTED'),
    ...accounts.filter((one) => one.link_state === 'DISCONNECTED'),
  ];

  return (
    <BottomSheet visible={visible} title="계좌" onClose={onClose}>
      {ordered.map((account) => (
        <Pressable
          key={account.account_id}
          accessibilityRole="radio"
          accessibilityLabel={account.label}
          accessibilityState={{ selected: account.account_id === selected }}
          onPress={() => onPick(account.account_id)}
          style={[styles.row, { borderColor: palette.border }]}
        >
          <Text
            style={[
              type.body,
              { color: account.account_id === selected ? palette.primary : palette.text },
            ]}
          >
            {account.label}
          </Text>
          {account.link_state === 'DISCONNECTED' && <Badge label="해제됨" />}
        </Pressable>
      ))}
    </BottomSheet>
  );
}

const styles = StyleSheet.create({
  row: {
    minHeight: size.row,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
});
```

`src/screens/cashflows/CashflowForm.tsx`:

```tsx
import { useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ApiError } from '@/api/client';
import { useCashflowActions } from '@/api/queries/useCashflowActions';
import type { CashflowWindow, CatalogAccount, ManualCashflowType } from '@/api/types';
import { useTheme } from '@/design/theme';
import { radius, size, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { messageOf } from '@/envelope/ErrorState';
import { errorAt } from '@/screens/alertEditor/fieldErrors';
import { AccountPickerSheet } from '@/screens/cashflows/AccountPickerSheet';
import {
  type CashflowsParams,
  digitsOf,
  type FormState,
  groupDigits,
  initialForm,
  toRequest,
} from '@/screens/cashflows/form';
import { windowNote } from '@/screens/cashflows/windowNote';
import { Badge } from '@/ui/Badge';
import { Button } from '@/ui/Button';
import { DateField } from '@/ui/DateField';
import { SegmentedControl } from '@/ui/SegmentedControl';
import { TextField } from '@/ui/TextField';
import { todayIso } from '@/ui/period';

const TYPES = [
  { value: 'DEPOSIT', label: '입금' },
  { value: 'WITHDRAW', label: '출금' },
];

/**
 * 입출금 한 건을 넣는 폼.
 *
 * 범위 검증은 서버가 한다. 날짜 범위가 그 계좌의 잔고에 달려 있어, 화면이 같은 판단을 하려면
 * 잔고 날짜를 따로 받아야 하고 두 곳의 판단은 언젠가 어긋난다.
 */
export function CashflowForm({
  params,
  accounts,
  window,
}: {
  params: CashflowsParams;
  accounts: CatalogAccount[];
  window: CashflowWindow | null;
}) {
  const palette = useTheme();
  const { save } = useCashflowActions();
  const [form, setForm] = useState<FormState>(() => initialForm(params, accounts, todayIso()));
  const [picking, setPicking] = useState(false);
  // 누른 순간부터 응답까지 잠근다. 상태값은 다음 렌더에야 바뀌어 연달아 누른 두 번째를 막지 못한다.
  const busy = useRef(false);

  // 칸을 고치면 앞 저장의 거절 문구는 낡았다. 저장 중에는 건드리지 않는다.
  const change = (patch: Partial<FormState>) => {
    if (!busy.current && !save.isIdle) save.reset();
    setForm((current) => ({ ...current, ...patch }));
  };

  const submit = () => {
    if (busy.current) return;
    busy.current = true;
    save.mutate(toRequest(form), {
      // 같은 달에 여러 건을 연달아 넣기 쉽게 계좌·유형·날짜는 남긴다.
      onSuccess: () => setForm((current) => ({ ...current, amountDigits: '', memo: '' })),
      onSettled: () => {
        busy.current = false;
      },
    });
  };

  const fields = save.error instanceof ApiError ? save.error.fields : [];
  const failure = save.error && fields.length === 0 ? messageOf(save.error) : null;
  const account = accounts.find((one) => one.account_id === form.accountId);
  const note = windowNote(form.date, window);

  return (
    <View style={styles.form}>
      <Text style={[type.label, { color: palette.text }]}>계좌</Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="계좌 고르기"
        onPress={() => setPicking(true)}
        style={[styles.select, { borderColor: palette.border, backgroundColor: palette.surface }]}
      >
        <Text style={[type.body, { color: account ? palette.text : palette.textMuted }]}>
          {account ? account.label : '계좌 선택'}
        </Text>
        {account?.link_state === 'DISCONNECTED' && <Badge label="해제됨" />}
      </Pressable>
      <FieldMessage message={errorAt(fields, 'account_id')} />

      <View style={styles.gap}>
        <SegmentedControl
          accessibilityLabel="입출금 유형"
          segments={TYPES}
          value={form.type}
          onChange={(next) => change({ type: next as ManualCashflowType })}
        />
        <FieldMessage message={errorAt(fields, 'type')} />
      </View>

      <View style={styles.gap}>
        <TextField
          label="금액"
          suffix="원"
          keyboardType="number-pad"
          value={groupDigits(form.amountDigits)}
          onChangeText={(text) => change({ amountDigits: digitsOf(text) })}
          error={errorAt(fields, 'amount') ?? errorAt(fields, 'currency')}
        />
      </View>

      <View style={styles.gap}>
        <Text style={[type.label, { color: palette.text }]}>날짜</Text>
        <View style={styles.dateRow}>
          <DateField label="날짜" value={form.date} max={todayIso()} onChange={(date) => change({ date })} />
        </View>
        {note && <Text style={[type.caption, styles.note, { color: palette.textMuted }]}>{note}</Text>}
        <FieldMessage message={errorAt(fields, 'occurred_on')} />
      </View>

      <View style={styles.gap}>
        <TextField
          label="메모"
          placeholder="선택"
          value={form.memo}
          onChangeText={(memo) => change({ memo })}
          error={errorAt(fields, 'memo')}
        />
      </View>

      {failure && <Text style={[type.caption, styles.failure, { color: palette.errorText }]}>{failure}</Text>}
      <View style={styles.gap}>
        <Button label="저장" loading={save.isPending} onPress={submit} />
      </View>

      <AccountPickerSheet
        visible={picking}
        accounts={accounts}
        selected={form.accountId}
        onPick={(accountId) => {
          change({ accountId });
          setPicking(false);
        }}
        onClose={() => setPicking(false)}
      />
    </View>
  );
}

/** 서버가 그 칸에 붙인 문장. 다시 쓰지 않고 그대로 낸다. */
function FieldMessage({ message }: { message?: string }) {
  const palette = useTheme();
  if (!message) return null;
  return <Text style={[type.caption, styles.note, { color: palette.errorText }]}>{message}</Text>;
}

const styles = StyleSheet.create({
  form: { paddingTop: space.base },
  select: {
    height: size.field,
    marginTop: space.sm,
    borderWidth: 1,
    borderRadius: radius.button,
    paddingHorizontal: space.base,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  gap: { marginTop: space.base },
  dateRow: { flexDirection: 'row', marginTop: space.sm },
  note: { marginTop: space.xs },
  failure: { marginTop: space.base },
});
```

`src/screens/cashflows/CashflowsScreen.tsx`:

```tsx
import { useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import { ScrollView, StyleSheet } from 'react-native';

import { useCashflows } from '@/api/queries/useCashflows';
import { useCatalog } from '@/api/queries/useCatalog';
import type { RootStackParamList } from '@/app/navigation/types';
import { screenPadding, space } from '@/design/tokens';
import { ErrorState } from '@/envelope/ErrorState';
import { KeyboardScreen } from '@/screens/alertEditor/KeyboardScreen';
import { CashflowForm } from '@/screens/cashflows/CashflowForm';
import { Skeleton } from '@/ui/Skeleton';

/**
 * 넣은 돈을 넣는 화면. 자산 변화의 `넣은 돈` 행에서 들어오고 `‹`로 돌아간다.
 *
 * 응답에 봉투가 없어 ScreenFrame을 쓰지 않는다. 배너·경고가 붙을 자리가 없는 화면이다.
 * 숫자 키패드에는 닫는 키가 없어, 알림 편집 단계처럼 KeyboardScreen으로 저장 버튼을 키보드 위에 둔다.
 */
export function CashflowsScreen() {
  const route = useRoute<RouteProp<RootStackParamList, 'cashflows'>>();
  const params = route.params;
  const catalog = useCatalog();
  const cashflows = useCashflows({ from: params.from, to: params.to, account: params.account ?? [] });

  return (
    <KeyboardScreen>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.content}>
        {catalog.data ? (
          <CashflowForm params={params} accounts={catalog.data.accounts} window={cashflows.list?.window ?? null} />
        ) : catalog.error ? (
          <ErrorState error={catalog.error} onRetry={() => void catalog.refetch()} />
        ) : (
          <Skeleton width="100%" height={240} style={styles.skeleton} />
        )}
      </ScrollView>
    </KeyboardScreen>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: screenPadding, paddingBottom: space.xxl },
  skeleton: { marginTop: space.base },
});
```

- [ ] **Step 4: 통과와 타입을 확인한다**

Run: `npx jest src/__tests__/cashflowForm.test.ts src/__tests__/cashflows.test.tsx && npx tsc --noEmit`
Expected: PASS. `renderWithStack`이 화면을 이름으로 직접 그리므로 RootStack 등록(Task 11) 전에도 돈다.

- [ ] **Step 5: 커밋 (요청받았을 때)**

```bash
git add src/screens/cashflows src/app/navigation/types.ts \
        src/__tests__/cashflowForm.test.ts src/__tests__/cashflows.test.tsx
git commit -m "feat: 입출금을 넣는 폼을 만든다"
```

---

### Task 10: 입출금 화면 — 기간 목록과 삭제

**Files:**
- Create: `src/screens/cashflows/CashflowList.tsx`
- Modify: `src/screens/cashflows/CashflowsScreen.tsx`
- Test: `src/__tests__/cashflows.test.tsx` (테스트 추가)

**Interfaces:**
- Consumes: `useCashflowActions().remove` (Task 8), `windowNote` (Task 9), `CashflowsScreen` · 테스트 도우미 `open` · `routes` (Task 9)
- Produces: `CashflowList({ from, to, list, loading, error, onRetry })`

- [ ] **Step 1: 실패하는 테스트를 더한다**

`cashflows.test.tsx` 위쪽 import에 `import { formatSigned } from '@/format/number';`를 더하고, 파일 끝에:

```tsx
const LIST: CashflowListResponse = {
  window: WINDOW,
  cashflows: [
    { id: 'c3', account_id: TRUST.account_id, account_label: '한국투자 위탁', type: 'DEPOSIT',
      amount: 500000, currency: 'KRW', occurred_on: '2026-07-29', memo: null },
    { id: 'c2', account_id: IRP.account_id, account_label: '한국투자 IRP', type: 'WITHDRAW',
      amount: 300000, currency: 'KRW', occurred_on: '2026-07-26', memo: '생활비' },
    { id: 'c1', account_id: TRUST.account_id, account_label: '한국투자 위탁', type: 'DEPOSIT',
      amount: 2000000, currency: 'KRW', occurred_on: '2026-07-25', memo: null },
  ],
};

describe('기간 목록', () => {
  it('기간과 건수를 머리줄에 둔다', async () => {
    await open(JULY, { list: { path: '/portfolio/cashflows', body: LIST } });
    await waitFor(() => expect(screen.getByText('07-01 ~ 07-31 · 3건')).toBeTruthy());
  });

  it('입금은 +, 출금은 −로 그리고 메모는 둘째 줄이다', async () => {
    await open(JULY, { list: { path: '/portfolio/cashflows', body: LIST } });

    await waitFor(() => expect(screen.getByText(formatSigned(2000000))).toBeTruthy());
    expect(screen.getByText(formatSigned(-300000))).toBeTruthy();
    expect(screen.getByText('생활비')).toBeTruthy();
  });

  it('넣은 돈 구간 밖의 행에 그 이유를 적는다', async () => {
    // 폼의 날짜가 구간 안(07-27)이라 안내는 행에서만 나온다.
    await open({ from: '2026-07-01', to: '2026-07-27' }, { list: { path: '/portfolio/cashflows', body: LIST } });

    await waitFor(() =>
      expect(screen.getAllByText('07-27 잔고 이후라 다음 잔고부터 반영돼요')).toHaveLength(1),
    );
  });

  it('비어 있으면 그렇게 말한다', async () => {
    await open(JULY);
    await waitFor(() => expect(screen.getByText('이 기간에 입력한 입출금이 없어요')).toBeTruthy());
    expect(screen.getByText('07-01 ~ 07-31 · 0건')).toBeTruthy();
  });

  it('불러오는 동안 자리를 잡아 둔다', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await open(JULY, { list: { path: '/portfolio/cashflows', body: LIST, wait: () => gate } });

    expect(screen.getByTestId('cashflow-skeleton')).toBeTruthy();
    await act(async () => {
      release();
    });
    await waitFor(() => expect(screen.queryByTestId('cashflow-skeleton')).toBeNull());
  });

  it('불러오지 못하면 다시 시도할 수 있다', async () => {
    const listRoute: Route = {
      path: '/portfolio/cashflows',
      status: 500,
      body: { error: { code: 'INTERNAL', message: '잠시 후 다시 시도해 주세요' } },
    };
    await open(JULY, { list: listRoute });
    await waitFor(() => expect(screen.getByText('잠시 후 다시 시도해 주세요')).toBeTruthy());

    listRoute.status = 200;
    listRoute.body = LIST;
    await fireEvent.press(screen.getByRole('button', { name: '다시 시도' }));

    await waitFor(() => expect(screen.getByText('07-01 ~ 07-31 · 3건')).toBeTruthy());
  });
});

// 목록 응답이 오기 전에는 안내가 없으므로, 머리줄이 그려진 뒤에 없음을 본다.
describe('날짜 칸 안내가 없는 경우', () => {
  it('구간 안이면 알리지 않는다', async () => {
    await open({ from: '2026-07-01', to: '2026-07-27' });
    await screen.findByText('07-01 ~ 07-27 · 0건');
    expect(screen.queryByText(/잔고 이후라|이미 들어간 돈/)).toBeNull();
  });

  it('잔고가 없으면 알리지 않는다', async () => {
    await open(JULY, { list: { path: '/portfolio/cashflows', body: { window: null, cashflows: [] } } });
    await screen.findByText('07-01 ~ 07-31 · 0건');
    expect(screen.queryByText(/잔고 이후라|이미 들어간 돈/)).toBeNull();
  });
});

describe('삭제', () => {
  /** 지운 행을 빼고 돌려주는 목록. 삭제가 서버에 닿은 뒤의 재조회를 흉내 낸다. */
  function deletable(initial: CashflowListResponse) {
    let rows = initial.cashflows;
    return {
      list: { path: '/portfolio/cashflows', body: () => ({ window: initial.window, cashflows: rows }) } as Route,
      remove: (id: string) => {
        rows = rows.filter((row) => row.id !== id);
      },
    };
  }

  it('묻고 나서 지우고, 목록을 다시 받는다', async () => {
    const server = deletable(LIST);
    const calls = await open(JULY, { list: server.list });
    await waitFor(() => expect(screen.getByText(formatSigned(2000000))).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '07-25 입금 2,000,000원 지우기' }));
    expect(screen.getByText('07-25 입금 2,000,000원을 지울까요?')).toBeTruthy();

    server.remove('c1');
    await fireEvent.press(screen.getByRole('button', { name: '지우기' }));

    await waitFor(() => expect(screen.queryByText(formatSigned(2000000))).toBeNull());
    expect(calls.find((call) => call.method === 'DELETE')?.path).toBe('/portfolio/cashflows/c1');
  });

  it('마지막 한 건을 지우면 빈 문구와 0건이 된다', async () => {
    const server = deletable({ window: WINDOW, cashflows: [LIST.cashflows[2]] });
    await open(JULY, { list: server.list });
    await waitFor(() => expect(screen.getByText('07-01 ~ 07-31 · 1건')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '07-25 입금 2,000,000원 지우기' }));
    server.remove('c1');
    await fireEvent.press(screen.getByRole('button', { name: '지우기' }));

    await waitFor(() => expect(screen.getByText('이 기간에 입력한 입출금이 없어요')).toBeTruthy());
    expect(screen.getByText('07-01 ~ 07-31 · 0건')).toBeTruthy();
  });

  it('지우기를 두 번 눌러도 한 번만 보낸다', async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const server = deletable(LIST);
    const calls = await open(JULY, { list: server.list, del: { wait: () => gate } });
    await waitFor(() => expect(screen.getByText(formatSigned(2000000))).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '07-25 입금 2,000,000원 지우기' }));
    server.remove('c1');
    const first = fireEvent.press(screen.getByRole('button', { name: '지우기' }));
    const second = fireEvent.press(screen.getByRole('button', { name: '지우기' }));
    await act(async () => {
      release();
    });
    await Promise.all([first, second]);

    await waitFor(() => expect(screen.queryByText(formatSigned(2000000))).toBeNull());
    expect(calls.filter((call) => call.method === 'DELETE')).toHaveLength(1);
  });

  it('실패한 삭제의 문구는 다른 행의 확인 시트에 남지 않는다', async () => {
    const message = '입출금 기록을 찾을 수 없어요';
    await open(JULY, {
      list: { path: '/portfolio/cashflows', body: LIST },
      del: { status: 404, body: { error: { code: 'CASHFLOW_NOT_FOUND', message } } },
    });
    await waitFor(() => expect(screen.getByText(formatSigned(2000000))).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '07-25 입금 2,000,000원 지우기' }));
    await fireEvent.press(screen.getByRole('button', { name: '지우기' }));
    await waitFor(() => expect(screen.getByText(message)).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '취소' }));
    await fireEvent.press(screen.getByRole('button', { name: '07-26 출금 300,000원 지우기' }));
    expect(screen.getByText('07-26 출금 300,000원을 지울까요?')).toBeTruthy();
    expect(screen.queryByText(message)).toBeNull();
  });

  it('취소하면 지우지 않는다', async () => {
    const calls = await open(JULY, { list: { path: '/portfolio/cashflows', body: LIST } });
    await waitFor(() => expect(screen.getByText(formatSigned(2000000))).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '07-25 입금 2,000,000원 지우기' }));
    await fireEvent.press(screen.getByRole('button', { name: '취소' }));

    expect(calls.some((call) => call.method === 'DELETE')).toBe(false);
  });
});
```

- [ ] **Step 2: 실패를 확인한다**

Run: `npx jest src/__tests__/cashflows.test.tsx`
Expected: 새 테스트 FAIL — 머리줄 · 행이 없다.

- [ ] **Step 3: 구현한다**

`src/screens/cashflows/CashflowList.tsx`:

```tsx
import { useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useCashflowActions } from '@/api/queries/useCashflowActions';
import type { CashflowEntry, CashflowListResponse } from '@/api/types';
import { signColor, useTheme } from '@/design/theme';
import { space } from '@/design/tokens';
import { numeric, type } from '@/design/typography';
import { ErrorState, messageOf } from '@/envelope/ErrorState';
import { formatMonthDay } from '@/format/date';
import { formatKrw, formatSigned, signOf } from '@/format/number';
import { windowNote } from '@/screens/cashflows/windowNote';
import { ConfirmSheet } from '@/ui/ConfirmSheet';
import { Skeleton } from '@/ui/Skeleton';

const TYPE_LABEL = { DEPOSIT: '입금', WITHDRAW: '출금' } as const;

/** 출금은 넣은 돈을 줄이므로 음수로 그린다. 자산 변화 내역과 같은 부호다. */
function signedAmount(entry: CashflowEntry): number {
  return entry.type === 'DEPOSIT' ? entry.amount : -entry.amount;
}

/** `07-25 입금 2,000,000원` — 지우기 버튼 이름과 확인 문구가 같은 말을 쓴다. */
function nameOf(entry: CashflowEntry): string {
  return `${formatMonthDay(entry.occurred_on)} ${TYPE_LABEL[entry.type]} ${formatKrw(entry.amount)}원`;
}

/**
 * 보던 기간에 넣은 입출금. "방금 보던 기간에 무엇이 들어갔나"에 답하는 목록이라 기간 밖은 싣지 않는다.
 * 기간 안이어도 넣은 돈을 세는 구간 밖이면 그 이유를 행 아래에 적는다.
 */
export function CashflowList({
  from,
  to,
  list,
  loading,
  error,
  onRetry,
}: {
  from: string;
  to: string;
  list: CashflowListResponse | null;
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
}) {
  const palette = useTheme();
  const { remove } = useCashflowActions();
  const [asking, setAsking] = useState<CashflowEntry | null>(null);
  // 폼의 저장과 같은 이유로 ref로 잠근다. `remove.isPending`은 다음 렌더에야 버튼을 막는다.
  const busy = useRef(false);

  if (loading) {
    return (
      <View style={styles.list} testID="cashflow-skeleton">
        {[0, 1, 2].map((index) => (
          <Skeleton key={index} width="100%" height={22} style={styles.skeletonGap} />
        ))}
      </View>
    );
  }
  if (error || !list) return <ErrorState error={error} onRetry={onRetry} />;

  // 앞서 실패한 삭제의 문구가 다른 행의 확인 시트에 남지 않게 열 때도 비운다.
  const ask = (entry: CashflowEntry) => {
    remove.reset();
    setAsking(entry);
  };

  const close = () => {
    remove.reset();
    setAsking(null);
  };

  const confirm = () => {
    if (!asking || busy.current) return;
    busy.current = true;
    remove.mutate(asking.id, {
      onSuccess: () => setAsking(null),
      onSettled: () => {
        busy.current = false;
      },
    });
  };

  return (
    <View style={styles.list}>
      <Text style={[type.caption, { color: palette.textMuted }]}>
        {`${formatMonthDay(from)} ~ ${formatMonthDay(to)} · ${list.cashflows.length}건`}
      </Text>

      {list.cashflows.length === 0 && (
        <Text style={[type.body, styles.empty, { color: palette.textMuted }]}>이 기간에 입력한 입출금이 없어요</Text>
      )}

      {list.cashflows.map((entry) => {
        const outside = windowNote(entry.occurred_on, list.window);
        const amount = signedAmount(entry);
        return (
          <View key={entry.id} style={[styles.row, { borderColor: palette.border }]}>
            <View style={styles.line}>
              <Text style={[type.body, numeric, styles.date, { color: palette.textMuted }]}>
                {formatMonthDay(entry.occurred_on)}
              </Text>
              <Text style={[type.body, styles.kind, { color: palette.text }]}>{TYPE_LABEL[entry.type]}</Text>
              <Text style={[type.body, styles.account, { color: palette.text }]} numberOfLines={1}>
                {entry.account_label}
              </Text>
              <Text
                style={[
                  type.body,
                  numeric,
                  // 이 기간에 세지 않는 행은 흐리게 — 금액이 화면 위 넣은 돈과 맞지 않는 이유가 아래 줄에 있다.
                  { color: outside ? palette.textMuted : signColor(signOf(amount), palette) },
                ]}
              >
                {formatSigned(amount)}
              </Text>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`${nameOf(entry)} 지우기`}
                hitSlop={space.sm}
                onPress={() => ask(entry)}
                style={styles.remove}
              >
                <Text style={[type.body, { color: palette.textMuted }]}>✕</Text>
              </Pressable>
            </View>
            {entry.memo && <Text style={[type.caption, styles.sub, { color: palette.textMuted }]}>{entry.memo}</Text>}
            {outside && <Text style={[type.caption, styles.sub, { color: palette.textMuted }]}>{outside}</Text>}
          </View>
        );
      })}

      <ConfirmSheet
        visible={asking !== null}
        title={asking ? `${nameOf(asking)}을 지울까요?` : ''}
        message={remove.error ? messageOf(remove.error) : undefined}
        confirmLabel="지우기"
        busy={remove.isPending}
        onCancel={close}
        onConfirm={confirm}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  list: { marginTop: space.xl },
  skeletonGap: { marginTop: space.md },
  empty: { marginTop: space.base },
  row: { paddingVertical: space.md, borderBottomWidth: StyleSheet.hairlineWidth },
  line: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  date: { width: 48 },
  kind: { width: 36 },
  account: { flex: 1 },
  remove: { paddingLeft: space.sm },
  sub: { marginTop: space.xs, paddingLeft: 48 + space.sm },
});
```

`CashflowsScreen.tsx` — import에 `CashflowList`를 더하고, 폼 아래에 둔다.

```tsx
        <CashflowList
          from={params.from}
          to={params.to}
          list={cashflows.list}
          loading={cashflows.loading}
          error={cashflows.error}
          onRetry={cashflows.refetch}
        />
```

- [ ] **Step 4: 통과와 타입을 확인한다**

Run: `npx jest src/__tests__/cashflows.test.tsx && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 5: 커밋 (요청받았을 때)**

```bash
git add src/screens/cashflows src/__tests__/cashflows.test.tsx
git commit -m "feat: 보던 기간의 입출금을 보이고 지울 수 있게 한다"
```

---

### Task 11: 자산 변화에서 입출금으로 — 진입 · 0원 그룹 · 라우트 · 문구

**Files:**
- Modify: `src/screens/assetChange/FlowList.tsx`
- Modify: `src/screens/assetChange/AssetChangeScreen.tsx`
- Modify: `src/app/navigation/RootStack.tsx`
- Modify: `src/fixtures/golden/asset-change.json`
- Test: `src/__tests__/assetChange.test.tsx`

**Interfaces:**
- Consumes: `CashflowsScreen` · `RootStackParamList['cashflows']` (Task 9), 백엔드 골든의 새 경고 블록(Task 7)
- Produces: `FlowList({ data, onOpenCashflows })`; 스택 화면 `cashflows`(제목 `입출금`)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`assetChange.test.tsx`의 `나머지 경고 둘은 줄로 쌓인다`에서 첫 단언의 문구를 바꾼다.

```tsx
    expect(
      screen.getByText(
        '⚠ 3개 계좌에 입출금이 입력되지 않았고 배당·수수료 내역도 없어 투자손익이 정확하지 않을 수 있어요',
      ),
    ).toBeTruthy();
```

위쪽 `@testing-library/react-native` import에 `within`을 더하고, 파일 끝에 묶음을 더한다.

```tsx
describe('넣은 돈 입력으로 가기', () => {
  it('넣은 돈 입력 →이 보던 기간과 계좌를 들고 간다', async () => {
    serve();
    const seen: { name: string; params: unknown }[] = [];
    renderWithNavigation(<AssetChangeScreen />, {
      others: ['cashflows'],
      onNavigate: (name, params) => seen.push({ name, params }),
    });
    await waitFor(() => expect(screen.getByText('기초자산')).toBeTruthy());

    await fireEvent.press(screen.getByRole('link', { name: '넣은 돈 입력' }));

    await waitFor(() => expect(seen.at(-1)?.name).toBe('cashflows'));
    expect(seen.at(-1)?.params).toEqual({ from: '2026-07-01', to: '2026-07-31', account: [] });
  });

  it('링크는 그 줄만 감싸 그룹 합계와 항목 금액을 따로 읽게 둔다', async () => {
    await renderAssetChange(goldenAssetChange);

    const link = within(screen.getByRole('link', { name: '넣은 돈 입력' }));
    expect(link.queryByText('넣은 돈')).toBeNull();
    expect(link.queryByText('입금')).toBeNull();
  });

  it('넣은 돈이 0이어도 그룹과 입구가 남고, 0원 항목 줄은 없다', async () => {
    await renderAssetChange({
      ...goldenAssetChange,
      data: {
        ...goldenAssetChange.data,
        deposited: 0,
        breakdown: goldenAssetChange.data.breakdown.filter((item) => item.type !== 'DEPOSIT'),
      },
    });

    expect(screen.getByText('넣은 돈')).toBeTruthy();
    expect(screen.getByRole('link', { name: '넣은 돈 입력' })).toBeTruthy();
    expect(screen.queryByText('입금')).toBeNull();
    expect(screen.queryByText('출금')).toBeNull();
  });
});
```

`src/fixtures/golden/asset-change.json`의 `CASHFLOW_UNCOVERED` 블록을 백엔드 골든(Task 7)과 같게 바꾼다.

```json
  "notices" : [ {
    "code" : "CASHFLOW_UNCOVERED",
    "severity" : "warn",
    "message" : "3개 계좌에 입출금이 입력되지 않았고 배당·수수료 내역도 없어 투자손익이 정확하지 않을 수 있어요",
    "params" : {
      "types" : [ "DIVIDEND", "FEE", "TAX", "DEPOSIT", "WITHDRAW" ],
      "account_count" : 4,
      "manual_uncovered_account_count" : 3
    }
  }, {
```

- [ ] **Step 2: 실패를 확인한다**

Run: `npx jest src/__tests__/assetChange.test.tsx`
Expected: 새 묶음 FAIL — `넣은 돈 입력` 링크가 없다.

- [ ] **Step 3: 구현한다**

`FlowList.tsx` — import에 `Pressable`을 더하고, 시그니처와 넣은 돈 그룹을 바꾼다.

```tsx
export function FlowList({
  data,
  onOpenCashflows,
}: {
  data: AssetChangeData;
  /** 넣은 돈은 사용자가 넣는 값이라 이 그룹이 입력으로 가는 입구다. */
  onOpenCashflows: () => void;
}) {
```

`{deposits.length > 0 && ( <Group label="넣은 돈" …> … </Group> )}` 자리를 아래로 바꾼다.

```tsx
      {/*
        넣은 돈은 0이어도 남긴다. 아직 아무것도 넣지 않은 사용자에게 입구가 있어야 한다.
        0인 입금·출금 줄은 서버가 빼고 보낸다.
      */}
      <Group label="넣은 돈" total={data.deposited}>
        {/* 링크 줄만 누른다. 그룹째 감싸면 스크린리더가 링크 이름만 읽고 합계와 항목 금액을 건너뛴다. */}
        <Pressable accessibilityRole="link" accessibilityLabel="넣은 돈 입력" onPress={onOpenCashflows}>
          <Text style={[type.body, styles.link, { color: palette.primary }]}>넣은 돈 입력 →</Text>
        </Pressable>
        {deposits.map((one) => (
          <ItemRow
            key={one.code}
            label={LABEL[one.code]}
            amount={one.amount}
            scale={scale}
            color={signColor(signOf(one.amount), palette)}
          />
        ))}
      </Group>
```

`styles`에 `link: { marginTop: space.xs },`를 더한다.

`AssetChangeScreen.tsx`의 `<FlowList data={data} />`:

```tsx
          <FlowList
            data={data}
            // 보던 기간과 계좌로 연다. 목록이 같은 기간을 보여야 무엇이 넣은 돈에 들어갔는지 맞춰 볼 수 있다.
            onOpenCashflows={() =>
              navigation.navigate('cashflows', {
                from: data.period.from,
                to: data.period.to,
                account: accountIds,
              })
            }
          />
```

`RootStack.tsx` — import `CashflowsScreen`, `asset-change` 바로 다음에:

```tsx
        <Stack.Screen name="cashflows" component={CashflowsScreen} options={{ title: '입출금' }} />
```

`RootStack`의 머리 주석 둘째 문단 끝에 한 문장을 더한다: `입출금도 같다 — 자산 변화의 넣은 돈을 보다 생기는 질문이라 그 위에 쌓인다.`

- [ ] **Step 4: 통과와 앱 전체를 확인한다**

Run: `npx jest && npx tsc --noEmit`
Expected: 전부 PASS. `envelope.test.tsx` · `notices.test.ts`가 골든 문구를 단언하면 같은 문구로 바꾼다(문구 외의 단언은 바꾸지 않는다).

- [ ] **Step 5: 커밋 (요청받았을 때)**

```bash
git add src/screens/assetChange src/app/navigation/RootStack.tsx \
        src/fixtures/golden/asset-change.json src/__tests__/assetChange.test.tsx
git commit -m "feat: 자산 변화의 넣은 돈에서 입출금 화면으로 들어가게 한다"
```

---

### Task 12: 갱신 흐름 — 저장하고 돌아오면 자산 변화가 새 값을 그린다

**Files:**
- Test: `src/__tests__/cashflowFlow.test.tsx`

**Interfaces:**
- Consumes: `RootStack`(Task 11), `invalidateCashflowData`(Task 8)

- [ ] **Step 1: 테스트를 쓴다**

```tsx
import { createRef } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import type { NavigationContainerRef } from '@react-navigation/native';
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';

import { setAccessToken } from '@/api/client';
import type { AssetChangeResponse } from '@/api/types';
import { RootStack } from '@/app/navigation/RootStack';
import type { RootStackParamList } from '@/app/navigation/types';
import { goldenAssetChange, goldenSummary } from '@/fixtures/golden';
import { formatSigned } from '@/format/number';
import { renderWithQuery } from '@/testing/renderWithQuery';
import { serveRoutes } from '@/testing/serveRoutes';

const TRUST = {
  account_id: '20000000-0000-0000-0000-000000000001',
  broker: '한국투자증권',
  label: '한국투자 위탁',
  account_type: 'GENERAL',
  link_state: 'CONNECTED',
};

/** 1,000,000을 넣은 뒤의 자산 변화. 넣은 돈이 늘고 투자손익이 그만큼 준다. */
const AFTER: AssetChangeResponse = {
  ...goldenAssetChange,
  data: {
    ...goldenAssetChange.data,
    deposited: 3000000,
    earned: -1800000,
    breakdown: [
      { type: 'DEPOSIT', amount: 3000000 },
      { type: 'INVESTMENT_PNL', amount: -1800000 },
    ],
    investment_pnl: { ...goldenAssetChange.data.investment_pnl, total: -1800000 },
  },
};

beforeEach(() => setAccessToken('테스트-토큰'));
afterEach(() => setAccessToken(null));

it('입출금을 넣고 돌아오면 자산 변화가 다시 받아 새 넣은 돈을 그린다', async () => {
  let saved = false;
  const calls = serveRoutes([
    { path: '/portfolio/catalog', body: { axes: [], metrics: [], accounts: [TRUST], views: [] } },
    { path: '/portfolio/views/asset-change', body: () => (saved ? AFTER : goldenAssetChange) },
    { path: '/portfolio/cashflows', body: { window: { after: '2026-07-24', through: '2026-07-27' }, cashflows: [] } },
    {
      method: 'POST',
      path: '/portfolio/cashflows',
      status: 201,
      body: () => {
        saved = true;
        return { id: 'new-id' };
      },
    },
    // 요약 탭과 그 밖의 조회는 이 테스트의 관심이 아니다.
    { path: /.*/, body: goldenSummary },
    { method: 'POST', path: /.*/, body: {} },
  ]);
  const navigation = createRef<NavigationContainerRef<RootStackParamList>>();
  renderWithQuery(
    <NavigationContainer ref={navigation}>
      <RootStack />
    </NavigationContainer>,
  );
  await waitFor(() => expect(screen.getByText('총자산')).toBeTruthy());

  await act(async () => {
    navigation.current?.navigate('asset-change', { period: 'CUSTOM', from: '2026-07-01', to: '2026-07-31' });
  });
  await waitFor(() => expect(screen.getByText('기초자산')).toBeTruthy());

  await fireEvent.press(screen.getByRole('link', { name: '넣은 돈 입력' }));
  await waitFor(() => expect(screen.getByRole('button', { name: '계좌 고르기' })).toBeTruthy());

  const assetChangeFetches = () =>
    calls.filter((call) => call.path === '/portfolio/views/asset-change').length;
  const beforeSave = assetChangeFetches();

  await fireEvent.changeText(screen.getByLabelText('금액'), '1000000');
  await fireEvent.press(screen.getByRole('button', { name: '저장' }));
  await waitFor(() => expect(saved).toBe(true));

  // 헤더의 ‹ 는 네이티브가 그려 테스트에서 누를 수 없다. 그 버튼이 하는 일을 부른다.
  await act(async () => {
    navigation.current?.goBack();
  });

  // 새 넣은 돈은 저장 뒤에 다시 받은 응답에만 있다. 횟수는 그 재조회가 저장 때문에 났는지를 본다.
  await waitFor(() => expect(screen.getAllByText(formatSigned(3000000)).length).toBeGreaterThan(0));
  expect(assetChangeFetches()).toBeGreaterThan(beforeSave);
});
```

- [ ] **Step 2: 돌린다**

Run: `npx jest src/__tests__/cashflowFlow.test.tsx`
Expected: PASS. Task 8 · 11이 끝난 뒤라 바로 통과해야 한다. 실패하면 무효화 키나 라우트 등록을 의심하고 원인을 찾는다(superpowers:systematic-debugging).

- [ ] **Step 3: 커밋 (요청받았을 때)**

```bash
git add src/__tests__/cashflowFlow.test.tsx
git commit -m "test: 입출금을 넣고 돌아오면 자산 변화가 새 값을 그리는지 본다"
```

---

## C. 와이어플로우

### Task 13: 입출금 화면과 진입 흐름 — `wireflow_src.py`

**Files:**
- Modify: `yhr/specs/portfolio-management/wireflow_src.py`
- Regenerate: `yhr/specs/portfolio-management/wireflow.png` · `wireflow.drawio`

**Interfaces:**
- Consumes: 설계 §5.4의 배치 표

- [ ] **Step 1: 생성기가 도는지 먼저 본다**

Run: `cd /Users/yhr/Dev/workspace/personal/stock-project/docs && python3 -c "import PIL; print(PIL.__version__)"`
Expected: 버전이 찍힌다. `ModuleNotFoundError`면 멈추고 사용자에게 묻는다(패키지를 설치하지 않는다). `docs/.venv`가 있으면 `docs/.venv/bin/python`으로도 확인한다.

- [ ] **Step 2: 페이지 폭과 밴드 3 배치를 바꾼다**

```python
PGW, PGH = 3160, 2680
```

P12 실현손익 · P13 종목 상세의 `ph(` x를 한 칸씩 민다.

```python
x, y = ph(1160, B3, '실현손익', back=False, tab='손익')
```

```python
x, y = ph(1560, B3, '삼성전자', back=True, right='＋ 알림')
```

노트 둘:

```python
NX, NY, NW = 1960, B3, 520
```

```python
NX = 2540
```

- [ ] **Step 3: P11 자산 변화의 넣은 돈 그룹을 바꾼다**

넣은 돈은 늘어난 항목이라 스펙 §2.9대로 빨강(`UP`)으로 그린다. 앱 `FlowList`와 P14도 같은 색이다. 문장 상자의 `+600만원`과 `wf`의 넣은 돈 두 줄을 바꾼다.

```python
text(x + 14, y + 52, 120, 26, '+600만원', 15, UP, bold=True)
```

```python
      ('그룹', '넣은 돈', '+600만', UP, None, 0),
      ('항목', '＋ 입금', '+6,000,000', UP, '#F0A39C', .10),
```

`wf` 목록에서 `('항목', '－ 출금', '0', DIM, None, 0)` 줄을 지우고, `('그룹', '넣은 돈', '+600만', UP, None, 0)` 바로 다음에 링크 줄을 넣는다.

```python
      ('링크', '넣은 돈 입력 →', '', PRI, None, 0),
```

반복문의 `if kind == '그룹':` 앞에 링크 처리를 둔다.

```python
    if kind == '링크':
        text(x + 16, yy, 200, h, lb, 10, PRI, bold=True)
        yy += h
        continue
```

- [ ] **Step 4: P14 입출금을 그린다**

`# P12 실현손익` 바로 앞에:

```python
# P14 입출금
x, y = ph(760, B3, '입출금', back=True)
text(x, y + 4, 276, 16, '계좌', 10, MUT, bold=True)
rect(x, y + 24, 276, 36, '#FFFFFF', LINE, 1, arc=8)
text(x + 12, y + 24, 200, 36, '한국투자 위탁', 12, TXT)
text(x + 220, y + 24, 44, 36, '▽', 11, MUT, align='right')
rect(x, y + 70, 276, 32, PANEL, 'none', 1, arc=8)
rect(x + 2, y + 72, 136, 28, '#FFFFFF', LINE, 1, arc=6)
text(x + 2, y + 72, 136, 28, '입금', 11, PRI, align='center', bold=True)
text(x + 138, y + 72, 136, 28, '출금', 11, SUB, align='center')
text(x, y + 112, 276, 16, '금액', 10, MUT, bold=True)
rect(x, y + 132, 276, 36, '#FFFFFF', LINE, 1, arc=8)
text(x + 12, y + 132, 226, 36, '2,000,000', 12, TXT, align='right', bold=True)
text(x + 244, y + 132, 24, 36, '원', 11, MUT)
text(x, y + 178, 276, 16, '날짜', 10, MUT, bold=True)
rect(x, y + 198, 276, 36, '#FFFFFF', LINE, 1, arc=8)
text(x + 12, y + 198, 252, 36, '2026-07-15', 12, TXT)
text(x, y + 244, 276, 16, '메모', 10, MUT, bold=True)
rect(x, y + 264, 276, 36, '#FFFFFF', LINE, 1, arc=8)
text(x + 12, y + 264, 252, 36, '월급 이체', 12, SUB)
rect(x, y + 312, 276, 40, PRI, 'none', 1, arc=8)
text(x, y + 312, 276, 40, '저장', 13, '#FFFFFF', align='center', bold=True)
text(x, y + 366, 276, 16, '07-01 ~ 07-31 · 2건', 9, MUT, bold=True)
for i, (dt, tp, acc, v) in enumerate([('07-15', '입금', '한국투자 위탁', '+2,000,000'),
                                      ('07-03', '입금', '한국투자 IRP', '+4,000,000')]):
    yy = y + 386 + i * 32
    hr(x, yy, 276)
    text(x, yy + 5, 40, 22, dt, 10, MUT)
    text(x + 42, yy + 5, 32, 22, tp, 10, UP, bold=True)
    text(x + 76, yy + 5, 100, 22, acc, 10, SUB)
    text(x + 170, yy + 5, 88, 22, v, 11, UP, align='right', bold=True)
    text(x + 260, yy + 5, 16, 22, '×', 11, DIM, align='right')
mono(x, y + 458, 276, 'manual_cashflow · 넣은 돈은 여기서만 온다\n저장·삭제 → 자산 변화 재조회')
```

- [ ] **Step 5: 상태 전수 노트에 한 줄을 더한다**

`st` 목록에서 `('자산 변화', …)` 다음에:

```python
      ('입출금', '입력 없음 · 넣은 돈 구간 밖 날짜 · 해제된 계좌 · 칸별 저장 오류'),
```

- [ ] **Step 6: 엣지를 바꾼다**

밴드 2 → 3 엣지 셋을 바꾸고 하나를 더한다.

```python
edge([(560, B2 + 600), (560, 1485), (1310, 1485), (1310, B3)], '손익 탭', lseg=1)
edge([(960, B2 + 600), (960, 1455), (1710, 1455), (1710, B3)], '행 탭', lseg=1)
edge([(1310, B3 + 600), (1310, 2165), (510, 2165), (510, B3 + 600)],
     '이 기간 전체 투자손익 →', lseg=1)
edge([(660, B3 + 261), (760, B3 + 261)], '넣은 돈 입력')
```

`B3 + 261`은 P11의 `넣은 돈 입력 →` 줄 가운데다(헤더 65 + 칩 32 + 문장 상자 102 + 기초자산 26 + 넣은 돈 그룹 24 + 링크 줄 절반 12).

- [ ] **Step 7: 생성하고 눈으로 본다**

Run: `cd /Users/yhr/Dev/workspace/personal/stock-project/docs/yhr/specs/portfolio-management && python3 wireflow_src.py`
Expected: `shapes=… png=4740x4020` (폭 3160 × 1.5).

`wireflow.png`를 열어(Read 도구) 확인한다.
- P11 → P14 화살표가 `넣은 돈 입력 →` 줄 높이에 붙는다.
- `손익 탭` · `행 탭` 레인이 서로 · 다른 선과 겹치지 않고, `행 탭` 라벨이 밴드 2 프레임 하단과 떨어져 있다.
- `이 기간 전체 투자손익 →`이 P12 아래에서 P11로 돌아오고 P14를 가로지르는 선이 P14 프레임에 겹치지 않는다(레인 2165는 P14 하단 2110 아래다).
- 상태 전수 노트에 입출금 줄이 들어가고 상자를 넘지 않는다.
- P14가 다른 화면과 같은 문법(헤더 `‹` · 라벨 · mono 주석)으로 보인다.

어긋나면 좌표를 고쳐 다시 생성한다.

- [ ] **Step 8: 커밋 (요청받았을 때)**

`docs`는 `main`에서 바로 작업한다. 커밋을 요청받으면 그때 `main`에 둘지 브랜치를 딸지 사용자에게 묻는다.

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project/docs
git add yhr/specs/portfolio-management/wireflow_src.py \
        yhr/specs/portfolio-management/wireflow.png \
        yhr/specs/portfolio-management/wireflow.drawio
git commit -m "docs: 와이어플로우에 입출금 화면과 넣은 돈에서 들어가는 흐름을 그린다"
```

설계 문서와 이 계획서도 같은 저장소다. 사용자가 요청하면 따로 커밋한다.

```bash
git add yhr/specs/portfolio-management/2026-10-16-manual-cashflow-input-design.md \
        yhr/plan/2026-10-17-manual-cashflow-input-plan.md
git commit -m "docs: 입출금 입력 설계와 구현 계획을 적는다"
```

---

## 실행 후 확인 (각각 사용자 승인 필요)

1. **백엔드 전체 테스트** — worktree에서 `./gradlew test`. 실패하면 출력 그대로 보고한다.
2. **앱 전체 테스트** — `npx jest && npx tsc --noEmit`(승인 불필요).
3. **로컬 실제 확인** — 로컬 DB · 서버(worktree 브랜치) 기동과 Expo Go 실기기 실행은 승인 후에 한다.
   - 자산 변화 → `넣은 돈 입력 →` → 입금 저장 → `‹` → 넣은 돈 · 투자손익이 바뀐다.
   - 기말 잔고 뒤 날짜를 고르면 날짜 칸 아래 안내가 뜬다.
   - 삭제하면 원래 값으로 돌아온다.
   - iOS에서 금액 칸에 숫자 키패드가 떠 있을 때 메모 칸과 저장 버튼이 키보드에 가리지 않는다.
   - 로컬 DB에 쓴 행은 확인 뒤 앱에서 지운다. 운영 DB에는 쓰지 않는다.
4. **스펙 · IA 반영 후보 보고** — 설계 §7의 표를 그대로 사용자에게 보고한다. 본문은 고치지 않는다.
5. **병합 순서 위험 보고** — 기점 `ae2a2a9`의 `SecurityConfig`는 오류 디스패치(`/error`)를 열지 않는다. 그래서 바디가 비거나 JSON이 깨진 POST가 400이 아니라 401로 나가고, 앱은 401을 로그아웃으로 처리한다. 이 수정은 병행 브랜치 `feat/account-link-api`(`6b61080`)에 있다. MockMvc는 오류 디스패치를 거치지 않아 테스트로 드러나지 않는다. 이 브랜치를 그보다 먼저 병합하면 생기는 일로 보고한다.
