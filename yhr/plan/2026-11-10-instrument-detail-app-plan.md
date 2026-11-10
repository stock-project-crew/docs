# 종목 상세 앱 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 종목별 행을 누르면 `instrument-detail` 스택 화면이 열려 보유 요약 · 계좌별 · 실현손익 · 거래내역 · 기업행위를 보여 주고, `알림 걸기`가 그 종목이 채워진 새 알림 흐름을 연다. 알림 카드는 확정 전 보유(`AWAITING_FINAL`)를 `오늘 저녁 첫 판정`으로 보인다.

**Architecture:** 응답 타입을 `src/api/types.ts`에 두고, 호출 · 쿼리 훅 · 캐시 키는 기존 뷰와 같은 모양으로 더한다. 화면은 기존 `ScreenFrame`(as-of 배너 · 안내 · 로딩 · 오류) 안에 영역 컴포넌트 넷을 쌓고, 문구와 표시 판정은 순수 함수 파일 `present.ts` 한 곳에 모은다. 404만 `ScreenFrame` 앞에서 따로 그린다. 종목별 행은 `instrument_id`가 있을 때만 `Pressable`이다. 알림 쪽은 확인 불가 사유 타입과 카드 상태 문구에 값 하나를 더한다.

**Tech Stack:** React Native(Expo SDK 58) · TypeScript · React Navigation 7(native-stack) · TanStack Query · jest-expo · @testing-library/react-native

**Spec:** [종목 상세 설계](../specs/portfolio-management/2026-11-10-instrument-detail-design.md) — 이 계획의 §번호는 그 문서의 절이다. 상위 근거는 [포트폴리오 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) §2.10 · [앱 정보 구조](../specs/app-information-architecture.md) §2.5.

## Global Constraints

- 작업 위치: 최신 `origin/main`에서 새 worktree `/Users/yhr/Dev/workspace/personal/stock-project/.worktrees/front-end-instrument-detail`, 브랜치 `feat/instrument-detail-screen`. **만들기 전에 사용자 승인.** 만든 뒤의 `npm ci`도 패키지 설치라 승인 사항이다.
- SDK 58은 이미 main에 있다. 다른 작업과 겹치면 최신 `origin/main`에 리베이스하고 `npm ci`(승인 후)로 다시 설치한다.
- **머지 순서:** 이 브랜치는 백엔드 브랜치 `feat/instrument-detail`이 main에 머지 · 배포된 **뒤에** 머지한다(§3.8 배포 순서 전제 — 앱이 먼저 나가면 오늘 산 종목의 `수익률 도달`을 저장이 `NOT_HELD`로 거절한다). 구현은 동시에 한다.
- TDD. 완료 조건은 `npx jest`와 `npx tsc --noEmit` 통과. 테스트 이름은 기존처럼 한국어 문장.
- **커밋 · 푸시는 사용자가 요청할 때만.** 접두 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- 주석은 한국어, 히스토리 없이 최신 사실만, 문서 절 번호(§ · SG-)를 지칭하지 않고 주석만으로 이해되게, 검증하지 않은 것은 단정하지 않는다.
- 스펙 · 통합테스트 문서(`docs/yhr/test/`)를 고치지 않는다. 구현 중 설계와 코드가 어긋나면 멈추고 보고한다.
- 화면 문구는 설계 §4.2 ~ §4.5의 문장을 그대로 쓴다. 설계에 없는 문구를 새로 짓지 않는다(필요하면 멈추고 묻는다).
- 머지 전: 최신 `origin/main`에 리베이스하고 `npx jest && npx tsc --noEmit`를 다시 돌린다.

## Review Focus

1. **실현손익이 전부 미포함인 종목의 머리 줄** — 행이 없고 `excluded_account_count > 0`이면 `0원`이 아니라 `—`여야 한다. `0원`은 "손익이 0이었다"로 읽힌다. → Task 6 `미포함 계좌만 있으면 합계 자리가 대시다`.
2. **이월된 계좌의 값을 오늘 값으로 읽는 것** — 수집이 실패해 직전 값을 쓴 계좌 줄에만 `07-24 기준`이 붙고, 나머지 계좌에는 붙지 않아야 한다. → Task 5 `이월된 계좌 줄에만 그 값의 날짜가 붙는다`.
3. **`알림 걸기`가 틀린 종목 정보로 편집기를 여는 것** — 로딩 중 버튼이 보이면 `held` · 직전 종가를 모른 채 열린다. 상장폐지 종목엔 버튼이 없어야 한다. → Task 8 `응답 전에는 알림 걸기가 없다`, `상장폐지 종목에는 알림 걸기가 없다`, `알림 걸기는 응답의 보유 여부와 직전 종가로 편집기를 연다`.
4. **예수금 · 렌즈 행이 눌려 404나 빈 상세가 열리는 것** — `instrument_id`가 없는 행은 버튼이 아니어야 한다. → Task 9 `예수금 행은 눌리지 않는다`, `ETF 분해 모드의 행은 눌리지 않는다`.
5. **두 계좌에 걸친 체결에서 계좌명이 빠지는 것** — 생략 판정을 `trades`만 보고 하면, 체결은 한 계좌 · 매도 행은 다른 계좌일 때 이름이 빠져 한 계좌 일로 읽힌다. → Task 7 `체결과 매도 행을 합쳐 계좌가 둘이면 계좌명을 쓴다`.

---

## 파일 구조

**front-end** (`.worktrees/front-end-instrument-detail`, 브랜치 `feat/instrument-detail-screen`)

| 파일 | 책임 |
|---|---|
| `src/api/types.ts` | `Row.instrument_id?`, 종목 상세 응답 타입 |
| `src/api/endpoints.ts` · `src/api/queries/keys.ts` · `src/api/queries/useInstrumentDetail.ts`(신규) | 호출 · 캐시 키 · 훅(404 구분) |
| `src/envelope/notices.ts` | `ScreenKey`에 `'instrument-detail'`, 배치표 |
| `src/app/navigation/types.ts` · `RootStack.tsx` | 파라미터 · 화면 등록 · 머리글 제목 |
| `src/screens/instrumentDetail/InstrumentDetailScreen.tsx`(신규) | 프레임 · 404 · 스켈레톤 · 머리글 · `알림 걸기` |
| `src/screens/instrumentDetail/HoldingSection.tsx`(신규) | 보유 요약 · 계좌별 |
| `src/screens/instrumentDetail/RealizedSection.tsx`(신규) | 실현손익(원가 기준 표기 · 근거 줄 · 매도 행 · 미포함) |
| `src/screens/instrumentDetail/HistorySection.tsx`(신규) | 거래내역 · 기업행위 |
| `src/screens/instrumentDetail/present.ts`(신규) | 문구 · 표시 판정 순수 함수 |
| `src/screens/positions/PositionRow.tsx` · `PositionsScreen.tsx` | 행 누름 · `LENS_HELP` · `MARKET_LABEL` export |
| `src/api/alertTypes.ts` · `src/screens/alerts/status.ts` | 확인 불가 사유 `AWAITING_FINAL`과 그 카드 상태 |
| `src/fixtures/instrumentDetail.ts`(신규) | 손으로 쓴 픽스처와 변형(Task 11에서 골든 기반으로) |
| `src/fixtures/golden.ts` · `src/fixtures/golden/instrument-detail.json`(신규) · `positions.json` | 골든(Task 11) |
| `src/__tests__/instrumentDetail.test.tsx`(신규) · `instrumentDetailPresent.test.ts`(신규) · `notices.test.ts` · `positions.test.tsx` · `navigation.test.tsx` · `types.test.ts` · `alertFormat.test.tsx` · `alertsTab.test.tsx` | 테스트 |

재사용(새로 만들지 않는다): `ScreenFrame`(배너 · `NoticeList` · 스켈레톤 · `ErrorState`를 이미 분기), `AsOfBanner`(새로고침), `Badge`, `Button`, `Skeleton`, `TooltipBody`, `GradeBadge` · `GRADE_LABEL` · `tradeHelp`(`src/screens/realizedPnl/GradeBadge.tsx`), `formatKrw` · `formatLocal` · `formatSigned` · `formatPct` · `formatQuantity` · `signOf` · `EM_DASH`(`src/format/number.ts`), `formatDate`(매도일 · 체결일 · 기업행위 `ex_date`, 연도 포함) · `formatMonthDay`(이월 계좌의 `MM-DD 기준`만) · `formatKoreanMonthDay`(`src/format/date.ts`), `signColor`(`src/design/theme`), 테스트 도구 `renderWithStack` · `renderWithNavigation` · `serveRoutes`.

---

## 픽스처 (Task 1이 만들고 이후 태스크가 단언한다)

`src/fixtures/instrumentDetail.ts`. 상수 `SAMSUNG_ID = '10000000-0000-0000-0000-000000000001'`, `ACCOUNT_A = '20000000-0000-0000-0000-000000000001'`(`한국투자 위탁`), `ACCOUNT_B = '20000000-0000-0000-0000-000000000002'`(`국내주식`). 변형은 매번 새 객체를 돌려주는 함수다(테스트끼리 공유 객체를 고치지 않게).

| 이름 | 내용 |
|---|---|
| `samsungDetail()` | §3.2 그대로. `last_close 71200` · `last_close_on 2026-07-27`, `basis null`, `trades []`, `corporate_actions []`, `notices []` |
| `twoAccountDetail()` | 삼성전자 200주를 A 120주 · 평단 58,000 · 평가 8,544,000(`basis` SEEDED · LATE_COVERAGE · `2026-01-01`)과 B 80주 · 평단 63,000 · 평가 5,696,000(`is_carried_forward true`, `source_as_of 2026-07-24T15:30:00+09:00`, `basis` VERIFIED)으로. 합계는 §3.2와 같다. `trades`: `T-0003` A BUY 10주 71,200 `executed_on 2026-07-20`, `T-0002` A SELL 5주 140,000 `2026-05-12`. `realized`는 §3.2. `corporate_actions`: SPLIT · ratio 2 · `2026-04-01` |
| `withBasis(basis)` | `samsungDetail()`의 A 계좌 `basis`만 바꾼다 — NOT_TRADED · UNAVAILABLE · CONFLICT · null 테스트용 |
| `notHeldDetail()` | `position null`, `by_account []`, `realized` · `trades`는 `samsungDetail()` 그대로 |
| `nothingDetail()` | `position null`, 목록 전부 빈 배열, `total { 0, 0 }` |
| `allExcludedDetail()` | `samsungDetail()`에서 `realized.rows []`, `total { 0, excluded_account_count 1 }` |
| `caUnknownDetail()` | notices에 `{ code: 'CA_UNKNOWN', severity: 'warn', message: '기업행위 이력을 확인하지 못해 실현손익이 다를 수 있습니다', params: { instrument_ids: [SAMSUNG_ID] } }` |
| `usdDetail()` | 애플 `AAPL` · US · USD, 20주 · 평단 200 · 평가 6,160,000(현지 4,400) · 원가 5,400,000(현지 4,000), 계좌 A 한 줄(현지 4,400). `trades`: BUY 20주 · price 200 · USD. notices에 `FX_APPLIED`(info) |
| `delistedDetail()` | `samsungDetail()`에 `delisted_on '2026-08-01'` |
| `positionsWithInstrumentIds()` | `goldenPositions`의 `CASH-`로 시작하지 않는 행에 `instrument_id`를 붙인 사본. 삼성전자는 `SAMSUNG_ID`. Task 11에서 지운다 |

---

### Task 0: 작업 공간

**Files:** 없음(머신 상태 변경)

- [ ] **Step 1: 아래 명령을 사용자에게 보여 주고 승인받은 뒤 실행한다.**

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project
git -C front-end fetch origin
git -C front-end worktree add -b feat/instrument-detail-screen ../.worktrees/front-end-instrument-detail origin/main
cd .worktrees/front-end-instrument-detail && npm ci
```

- [ ] **Step 2: 기준선.** `npx jest && npx tsc --noEmit`. Expected: 통과.

---

### Task 1: 응답 타입과 손 픽스처

**Files:**
- Modify: `src/api/types.ts`
- Create: `src/fixtures/instrumentDetail.ts`
- Test: `npx tsc --noEmit`(픽스처의 타입 대입이 구조 검사다)

**Interfaces:**
- Produces (`src/api/types.ts`, 필드 이름은 응답 그대로 snake_case):
  - `Row.instrument_id?: string` — 주석: 종목별 응답의 직접 보유 종목 행에만 있다. 예수금 행과 ETF 분해 모드의 행에는 키가 없다.
  - `InstrumentInfo = { id; symbol; label: string; market: Market; currency: string; delisted_on: string | null; last_close: number | null; last_close_on: string | null }` — `Market`은 `import type { Market } from '@/api/alertTypes'`(타입 전용).
  - `InstrumentPosition = { quantity; avg_cost; cost_amount_krw; market_value_krw; unrealized_pnl_krw: number; unrealized_pnl_pct: number | null; market_value_local?: number; cost_amount_local?: number }` — 현지 금액은 외화 종목에만.
  - `PositionBasis = { grade: TradeGrade; seed_reason?: SeedReason; coverage_start_at?: string; ca_unknown: boolean }`
  - `InstrumentAccount = { account_id; label: string; account_type: 'GENERAL' | 'PENSION'; quantity; avg_cost; market_value_krw: number; market_value_local?: number; is_carried_forward: boolean; source_as_of: string; basis: PositionBasis | null }`
  - `InstrumentRealizedRow = RealizedPnlTrade & { account_id: string; account_label: string; ca_unknown: boolean }` — `RealizedPnlTrade`를 넓혀 `tradeHelp`를 그대로 받게 한다.
  - `InstrumentRealized = { total: { realized_pnl_krw: number; excluded_account_count: number }; rows: InstrumentRealizedRow[] }`
  - `InstrumentTrade = { trade_id; account_id; account_label: string; side: 'BUY' | 'SELL'; quantity; price; fee; tax: number; currency: string; executed_at: string; executed_on: string }`
  - `CorporateActionType = 'SPLIT' | 'RIGHTS' | 'MERGER'`, `CorporateAction = { type: CorporateActionType; ratio: number; ex_date: string }`
  - `InstrumentDetailData = { instrument: InstrumentInfo; position: InstrumentPosition | null; by_account: InstrumentAccount[]; realized: InstrumentRealized; trades: InstrumentTrade[]; corporate_actions: CorporateAction[] }`, `InstrumentDetailResponse = Envelope<InstrumentDetailData>`
- Produces: 위 "픽스처" 표의 함수와 상수.

- [ ] **Step 1: 실패 확인.** 픽스처 파일을 먼저 쓴다. `npx tsc --noEmit`. Expected: `InstrumentDetailResponse` 없음으로 실패.
- [ ] **Step 2: 타입 추가.** 위 시그니처대로. 타입 주석에 "`empty_reason`은 이 응답에서 늘 null이다 — 종목 하나의 서술이라 비는 것은 영역 하나씩이다"를 쓴다. 기존 `EditorInstrument` 주석의 "종목 상세가 생기면 그 화면이 넘긴다"는 "종목 상세가 넘긴다"로 고친다.
- [ ] **Step 3: 통과 확인.** `npx tsc --noEmit && npx jest`. Expected: 통과.
- [ ] **Step 4: 커밋(요청 시).** `feat: 종목 상세 응답 타입과 픽스처를 더한다`

---

### Task 2: 호출 · 캐시 키 · 쿼리 훅

**Files:**
- Modify: `src/api/endpoints.ts`, `src/api/queries/keys.ts`
- Create: `src/api/queries/useInstrumentDetail.ts`
- Test: `src/__tests__/instrumentDetail.test.tsx`(신규, 이 태스크는 `describe('요청')` 블록만)

**Interfaces:**
- Produces: `fetchInstrumentDetail(instrumentId: string): Promise<InstrumentDetailResponse>` — `apiGet(`/portfolio/instruments/${encodeURIComponent(instrumentId)}`)`. `keys.instrumentDetail: (instrumentId: string) => ['instrument-detail', instrumentId] as const`. `useInstrumentDetail(instrumentId: string): { envelope: InstrumentDetailResponse | null; loading: boolean; refreshing: boolean; error: unknown; notFound: boolean; refetch: () => void }` — `notFound = error instanceof ApiError && error.status === 404`(`AlertEventScreen`과 같은 판정). `placeholderData`를 두지 않는다 — 다른 종목의 숫자가 잠깐이라도 이 종목 머리글 아래 보이면 안 된다(훅 주석으로).
- `ApiError`는 앱 `QueryClient`에서 재시도하지 않으므로(`App.tsx`의 `retry`) 404가 곧바로 화면에 닿는다.

- [ ] **Step 1: 실패하는 테스트.** `serveRoutes([{ path: /^\/portfolio\/instruments\//, body: samsungDetail() }])`, 화면 대신 훅을 쓰는 작은 테스트 컴포넌트를 `renderWithStack`에 올린다.
  - `종목 ID 하나로 상세를 부른다`: 호출 한 번, `path === '/portfolio/instruments/10000000-0000-0000-0000-000000000001'`, 쿼리스트링 없음.
  - `404면 찾을 수 없음으로 구분한다`: `status 404`, 본문 `{ error: { code: 'INSTRUMENT_NOT_FOUND', message: '종목을 찾을 수 없습니다' } }` → `notFound true`.
  - `500은 찾을 수 없음이 아니다`: `status 500` → `notFound false`, `error`는 `ApiError`.
- [ ] **Step 2: 실행해 실패 확인.** `npx jest src/__tests__/instrumentDetail.test.tsx`. Expected: `fetchInstrumentDetail`/훅 없음으로 FAIL.
- [ ] **Step 3: 구현.** `usePositions`와 같은 반환 모양에 `notFound`를 더한다.
- [ ] **Step 4: 통과 확인.** 같은 명령. Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목 상세 조회와 404 구분을 더한다`

---

### Task 3: 안내 배치

**Files:**
- Modify: `src/envelope/notices.ts`
- Test: `src/__tests__/notices.test.ts`

**Interfaces:**
- Produces: `ScreenKey`에 `'instrument-detail'`. `BY_SCREEN['instrument-detail'] = [...ALWAYS, 'FX_STALE', 'CA_UNKNOWN']`. 표 주석: 이월 계좌는 계좌 줄이, 추정 · 미포함은 실현손익 영역이 말하므로 `STALE_ACCOUNTS` · `SEEDED_ROWS` · `EXCLUDED_ACCOUNTS`를 받지 않는다.

- [ ] **Step 1: 실패하는 테스트.** 기존 `SCREENS`(여섯 화면) 기대는 그대로 두고 새 `describe('종목 상세')`를 더한다.
  - `환율 안내는 캡션이다`: `captionNotices('instrument-detail', [FX_APPLIED info])` 1개, `bannerNotices` 0개.
  - `낡은 환율과 기업행위 경고는 경고 줄이다`: `FX_STALE` warn · `CA_UNKNOWN` warn 각각 `bannerNotices` 1개.
  - `계좌 · 실현손익 안내는 그리지 않는다`: `STALE_ACCOUNTS` · `SEEDED_ROWS` · `EXCLUDED_ACCOUNTS` · `SYNC_IN_PROGRESS`에서 `isVisibleOn('instrument-detail', code)`가 모두 false.
- [ ] **Step 2: 실행해 실패 확인.** `npx jest src/__tests__/notices.test.ts`. Expected: 타입 오류 또는 FAIL.
- [ ] **Step 3: 구현.**
- [ ] **Step 4: 통과 확인.** `npx jest src/__tests__/notices.test.ts && npx tsc --noEmit`. Expected: PASS. (`EmptyState`의 표는 `Partial`이라 고칠 것이 없다.)
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목 상세가 그릴 안내를 정한다`

---

### Task 4: 화면 뼈대 · 내비게이션 · 상태

**Files:**
- Modify: `src/app/navigation/types.ts`, `src/app/navigation/RootStack.tsx`, `src/screens/positions/PositionRow.tsx`(`MARKET_LABEL` export만)
- Create: `src/screens/instrumentDetail/InstrumentDetailScreen.tsx`
- Test: `src/__tests__/instrumentDetail.test.tsx`, `src/__tests__/navigation.test.tsx`

**Interfaces:**
- Produces: `RootStackParamList['instrument-detail'] = { instrumentId: string; label: string }`. `RootStack`에 `<Stack.Screen name="instrument-detail" component={InstrumentDetailScreen} options={({ route }) => ({ title: route.params.label })} />`. `InstrumentDetailScreen()`:
  - `notFound`면 `ScreenFrame` 없이 `종목을 찾을 수 없어요` 한 줄. 다시 시도 버튼 없음, 뒤로 가기는 스택 머리글이 맡는다.
  - 그 밖에는 `<ScreenFrame screen="instrument-detail" topInset={false} envelope loading refreshing error onRefresh={refetch} onRetry={refetch} skeleton={<DetailSkeleton />}>` 안에 `ScrollView`. `title` · `emptyAction`을 주지 않는다. 응답의 `empty_reason`은 늘 null이라 공통 빈 상태로 가지 않는다.
  - 응답이 오면 `navigation.setOptions({ title: instrument.label, headerTitle })` — `headerTitle`은 종목명 옆에 `Badge`(`MARKET_LABEL[market]`, `PositionRow`에서 export)를 둔다.
  - 이 태스크의 본문은 영역 자리만 둔다(Task 5 ~ 8이 채운다).

- [ ] **Step 1: 실패하는 테스트.** 헬퍼 `openDetail(body, opts?)` = `serveRoutes([{ path: /^\/portfolio\/instruments\//, status, body }])` 후 `renderWithStack('instrument-detail', InstrumentDetailScreen, { instrumentId: SAMSUNG_ID, label: '삼성전자' }, { others: ['alert-editor'], onNavigate })`.
  - `응답 전에는 스켈레톤만 있다`: `wait`로 응답을 붙잡고 `알림 걸기` · `계좌별` 없음.
  - `기준 시각과 새로고침이 있다`: `기준 2026-07-27 15:30`, 버튼 `새로고침`. 누르면 같은 경로 호출이 2번.
  - `기업행위 경고는 배너 아래 경고 줄이다`: `caUnknownDetail()` → `⚠ 기업행위 이력을 확인하지 못해 실현손익이 다를 수 있습니다`.
  - `404면 찾을 수 없다고만 한다`: `종목을 찾을 수 없어요`, `다시 시도` 버튼 없음.
  - `그 밖의 오류는 다시 시도를 둔다`: 500 · 메시지 `잠시 후 다시 시도해 주세요` → 그 문장과 `다시 시도`.
  - `아무것도 없는 종목도 공통 빈 상태로 가지 않는다`: `nothingDetail()` → `보유 중인 종목이 없어요` 없음, `거래내역` 머리 있음.
  - `navigation.test.tsx` `탭에서 종목 상세로 갔다가 돌아온다`: fetch 대역에 `/portfolio/instruments/` 분기를 더해 `samsungDetail()`. `navigate('instrument-detail', { instrumentId: SAMSUNG_ID, label: '삼성전자' })` → 현재 라우트 이름, `getCurrentOptions()?.title === '삼성전자'`, `goBack()` 후 `summary`.
- [ ] **Step 2: 실행해 실패 확인.** `npx jest src/__tests__/instrumentDetail.test.tsx src/__tests__/navigation.test.tsx`. Expected: FAIL.
- [ ] **Step 3: 구현.** 404 컴포넌트는 `AlertEventScreen`의 `NotFound`와 같은 모양. 스켈레톤은 `Skeleton` 세 개(요약 한 덩어리 · 줄 둘). 머리글 시장 배지는 테스트 렌더러가 머리글을 그린다고 기대하지 않으므로(`renderWithStack` 주석) 제목 문자열만 단언한다.
- [ ] **Step 4: 통과 확인.** 같은 명령 + `npx tsc --noEmit`. Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목 상세 화면을 스택에 올린다`

---

### Task 5: 보유 요약 · 계좌별

**Files:**
- Create: `src/screens/instrumentDetail/HoldingSection.tsx`, `src/screens/instrumentDetail/present.ts`
- Modify: `InstrumentDetailScreen.tsx`
- Test: `src/__tests__/instrumentDetail.test.tsx`, `src/__tests__/instrumentDetailPresent.test.ts`(신규)

**Interfaces:**
- Produces (`present.ts`): `unitPrice(value: number, currency: string): string` — KRW면 `formatKrw(value)`, 아니면 `formatLocal(value, currency, { fraction: 2 })`. `carriedLabel(account: InstrumentAccount): string | null` — `is_carried_forward`면 `` `${formatMonthDay(account.source_as_of)} 기준` ``(계좌별 화면 `StateBadge`와 같은 말), 아니면 null.
- Produces: `HoldingSection({ data }: { data: InstrumentDetailData })`.
  - `position`이 있으면 1줄 `formatKrw(market_value_krw, { suffix: true })` + 외화면 `` ` (${formatLocal(market_value_local, currency)})` ``, 2줄 `` `${formatSigned(pnl)} (${formatPct(pct, { signed: true })})` ``(색 `signColor(signOf(pnl))`), 3줄 `` `${formatQuantity(q)}주 · 평단 ${unitPrice(avg_cost, currency)}` ``. 이어 머리 `계좌별`과 계좌 줄: 표시명 · `carriedLabel`이면 `Badge` · 같은 수량 · 평단 문구 · 평가금액(외화 병기). 등급 배지는 달지 않는다.
  - `position === null`이면 `지금 보유하지 않은 종목이에요` 한 줄, `계좌별`을 그리지 않는다.

- [ ] **Step 1: 실패하는 테스트.**
  - `보유 요약이 평가 · 손익 · 수량과 평단을 보인다`: `samsungDetail()` → `14,240,000원`(요약 · 계좌 줄 두 곳이라 `getAllByText` 2), `+2,240,000 (+18.7%)`, `200주 · 평단 60,000`(2).
  - `계좌별은 계좌마다 한 줄이다`: `twoAccountDetail()` → `한국투자 위탁` · `120주 · 평단 58,000` · `8,544,000원`, `국내주식` · `80주 · 평단 63,000` · `5,696,000원`.
  - `이월된 계좌 줄에만 그 값의 날짜가 붙는다`(Review 2): `07-24 기준`이 정확히 1개이고 `국내주식` 줄(testID `detail-account-${account_id}`) 안에 있다. `한국투자 위탁` 줄에는 `기준` 글자가 없다.
  - `계좌 줄에 등급 배지가 없다`: `twoAccountDetail()`의 A(SEEDED) 줄 안에 `추정`이 없다.
  - `외화 종목은 현지 통화를 병기한다`: `usdDetail()` → `6,160,000원 ($4,400)`(2), `20주 · 평단 $200.00`(2), 배너 캡션에 FX_APPLIED 문장.
  - `보유하지 않은 종목은 요약 대신 한 줄이고 계좌별이 없다`: `notHeldDetail()` → `지금 보유하지 않은 종목이에요`, `계좌별` 없음.
  - `instrumentDetailPresent.test.ts`: `unitPrice(60000, 'KRW') === '60,000'`, `unitPrice(200, 'USD') === '$200.00'`, `carriedLabel` 이월 → `'07-24 기준'`, 아님 → null.
- [ ] **Step 2: 실행해 실패 확인.** `npx jest src/__tests__/instrumentDetail.test.tsx src/__tests__/instrumentDetailPresent.test.ts`. Expected: FAIL.
- [ ] **Step 3: 구현.** 줄 배치는 `PositionRow`의 규칙을 따른다 — 금액은 자르지 않고 이름이 줄어든다(`numberOfLines={1}`, `flexShrink`).
- [ ] **Step 4: 통과 확인.** Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목 상세에 보유 요약과 계좌별을 그린다`

---

### Task 6: 실현손익 영역

**Files:**
- Create: `src/screens/instrumentDetail/RealizedSection.tsx`
- Modify: `present.ts`, `InstrumentDetailScreen.tsx`
- Test: `instrumentDetail.test.tsx`, `instrumentDetailPresent.test.ts`

**Interfaces:**
- Produces (`present.ts`):
  - `COST_BASIS_NOTE = '취득원가 기준이 달라 위 평단과 맞지 않아요'`, `showCostBasisNote(data): boolean` — `realized.rows.length > 0 && position !== null`.
  - `realizedHeadline(realized: InstrumentRealized): string | null` — 행이 있으면 `formatSigned(total, { suffix: true })`, 행이 없고 `excluded_account_count > 0`이면 `EM_DASH`, 둘 다 없으면 null(머리 줄에 금액을 쓰지 않고 아래 빈 문구만 둔다).
  - `excludedLabel(count: number): string | null` — `count > 0`이면 `` `미포함 계좌 ${count}개` ``.
  - `REALIZED_EMPTY = '이 종목에서 확정한 손익이 아직 없어요'` — 행도 미포함도 없을 때.
  - `basisLine(account: InstrumentAccount): string | null` — `` `${label} · ${GRADE_LABEL[grade]} — ${설명}` ``. `basis === null` 또는 `VERIFIED`면 null. 설명:
    - SEEDED + LATE_COVERAGE: `` `이 계좌에서 팔면 손익이 추정치로 계산돼요. 거래내역이 ${formatKoreanMonthDay(coverage_start_at)}부터 있어요` ``
    - SEEDED + NOT_TRADED: `이 계좌에서 팔면 손익이 추정치로 계산돼요. 매매 없이 입고된 종목이에요`
    - UNAVAILABLE: `이 계좌에서 팔면 손익을 계산하지 못해요`
    - CONFLICT: `거래내역이 아직 도착하지 않았을 수 있어요. 그동안 판 손익은 계산하지 못해요`
    - SEEDED인데 사유나 시작일이 없으면 첫 문장만. 실현손익 화면의 `tradeHelp`가 같은 경우에 고정 문구로 물러나는 것과 같다.
- Produces: `RealizedSection({ data, showAccount }: { data: InstrumentDetailData; showAccount: boolean })`. 순서: 머리 `실현손익` + `realizedHeadline`(부호 색) → 원가 기준 표기 → `미포함 계좌 N개` → 근거 줄들(`by_account` 순서) → 빈 문구 또는 매도 행. 매도 행: `` `${formatDate(sold_at)} 매도 ${formatQuantity(quantity)}주` `` · `GradeBadge`(SEEDED만 그려진다, 누르면 `TooltipBody`에 `tradeHelp(row)`, `TradeList`와 같은 열림 상태 하나) · `formatKrw(sell_amount_krw, { suffix: true })` · `formatSigned(realized_pnl_krw)`(부호 색), `showAccount`면 아래 캡션 `account_label`. `showAccount` 판정은 Task 7이 만들고, 이 태스크에서는 화면이 `false`를 넘긴다.

- [ ] **Step 1: 실패하는 테스트.**
  - `실현손익 합계와 매도 행이 나온다`: `samsungDetail()` → `+277,000원`, `2026-05-12 매도 5주` · `700,000원` · `+198,000`, `2026-03-02 매도 3주` · `400,000원` · `+79,000`.
  - `보유 중이면 원가 기준 표기가 붙는다`: `취득원가 기준이 달라 위 평단과 맞지 않아요`.
  - `보유하지 않으면 원가 기준 표기가 없다`: `notHeldDetail()` → 없음, 매도 행은 그대로.
  - `추정 매도 행의 배지를 누르면 설명이 열린다`: `추정 설명` 버튼(1개, `2026-03-02` 행) 누름 → `거래내역이 1월 1일부터 확보돼, 그 전에 산 수량은 잔고 평단으로 추정했어요. 더 이른 거래내역이 들어오면 바뀔 수 있어요`. `2026-05-12` 행에는 배지가 없다.
  - `미포함 계좌만 있으면 합계 자리가 대시다`(Review 1): `allExcludedDetail()` → `—`와 `미포함 계좌 1개`, `0원` 없음, 원가 기준 표기 없음.
  - `확정한 손익이 없으면 영역 안에 그렇게 쓴다`: `nothingDetail()` → `이 종목에서 확정한 손익이 아직 없어요`, `0원` · `—` 없음.
  - `추정 원가 계좌는 근거 줄을 둔다`: `twoAccountDetail()` → `한국투자 위탁 · 추정 — 이 계좌에서 팔면 손익이 추정치로 계산돼요. 거래내역이 1월 1일부터 있어요`. B(VERIFIED)는 줄 없음.
  - `근거 줄은 실현손익이 없어도 있다`: `withBasis(UNAVAILABLE)`에서 `realized.rows = []`로 → `한국투자 위탁 · 거래내역 없음 — 이 계좌에서 팔면 손익을 계산하지 못해요`.
  - `instrumentDetailPresent.test.ts` `basisLine`: NOT_TRADED → `한국투자 위탁 · 추정 — 이 계좌에서 팔면 손익이 추정치로 계산돼요. 매매 없이 입고된 종목이에요`, CONFLICT → `한국투자 위탁 · 수량 확인 중 — 거래내역이 아직 도착하지 않았을 수 있어요. 그동안 판 손익은 계산하지 못해요`, `basis null` → null, VERIFIED → null. `realizedHeadline`의 세 경우, `excludedLabel(0) === null`.
- [ ] **Step 2: 실행해 실패 확인.** Expected: FAIL.
- [ ] **Step 3: 구현.** 근거 줄 위 주석: "지금 보유분을 앞으로 팔 때의 원가 근거다. 위 매도 행의 숫자를 수식하지 않는다 — 그것은 각 행의 배지가 말한다." 등급 라벨은 `GRADE_LABEL`을 import한다(문자열을 다시 쓰지 않는다).
- [ ] **Step 4: 통과 확인.** Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목 상세에 실현손익과 계좌별 원가 근거를 그린다`

---

### Task 7: 거래내역 · 기업행위 · 계좌명 생략

**Files:**
- Create: `src/screens/instrumentDetail/HistorySection.tsx`
- Modify: `present.ts`, `InstrumentDetailScreen.tsx`
- Test: `instrumentDetail.test.tsx`, `instrumentDetailPresent.test.ts`

**Interfaces:**
- Produces (`present.ts`): `showAccountNames(data): boolean` — `trades`와 `realized.rows`의 `account_id`를 합친 집합의 크기가 2 이상. `SIDE_LABEL: Record<'BUY' | 'SELL', string> = { BUY: '매수', SELL: '매도' }`. `TRADES_EMPTY = '이 종목의 거래내역이 아직 없어요'`. `CA_TYPE_LABEL: Record<CorporateActionType, string> = { SPLIT: '분할', RIGHTS: '유상증자', MERGER: '합병' }`. `ratioText(ratio: number): string` — `ratio >= 1`이면 `` `1주 → ${n(ratio)}주` ``, 아니면 `` `${n(1 / ratio)}주 → 1주` ``. `n`은 소수 넷째 자리까지 반올림하고 끝의 0과 소수점을 지운다(`formatQuantity`는 소수 둘째 자리 고정이라 쓰지 않는다).
- Produces: `HistorySection({ data, showAccount })`. 머리 `거래내역`, 체결 줄 `` `${formatDate(executed_on)} ${SIDE_LABEL[side]} ${formatQuantity(quantity)}주` `` · `unitPrice(price, trade.currency)` · `showAccount`면 캡션 `account_label`. 비면 `TRADES_EMPTY`. `corporate_actions`가 있을 때만 머리 `기업행위`와 줄 `formatDate(ex_date)` · `CA_TYPE_LABEL[type]` · `ratioText(ratio)`. 체결일은 `executed_on`만 쓰고 `executed_at`으로 날짜를 계산하지 않는다.
- 화면은 `const showAccount = showAccountNames(data)`를 `RealizedSection`과 `HistorySection`에 함께 넘긴다.

- [ ] **Step 1: 실패하는 테스트.**
  - `체결마다 날짜 · 매수매도 · 수량 · 단가가 나온다`: `twoAccountDetail()` → `2026-07-20 매수 10주` · `71,200`, `2026-05-12 매도 5주`(거래내역과 매도 행 두 곳, `getAllByText` 2) · `140,000`.
  - `거래내역이 없으면 영역 안에 그렇게 쓴다`: `samsungDetail()` → `이 종목의 거래내역이 아직 없어요`, 다른 영역(`+277,000원`)은 그대로.
  - `한 계좌뿐이면 계좌명을 쓰지 않는다`: `twoAccountDetail()`(체결 · 매도 모두 A) → 거래내역 · 실현손익 영역(testID `detail-history` · `detail-realized`) 안에서 `within(…).queryByText('한국투자 위탁')`이 null. 정확 일치로 단언한다 — 근거 줄 `한국투자 위탁 · 추정 — …`이 같은 영역에 있어 부분 일치(정규식)는 계좌명이 없어도 걸린다.
  - `체결과 매도 행을 합쳐 계좌가 둘이면 계좌명을 쓴다`(Review 5): `twoAccountDetail()`에서 `realized.rows[1].account_id = ACCOUNT_B`, `account_label '국내주식'` → `detail-realized` 안에 `getByText('국내주식')`과 `getByText('한국투자 위탁')`, `detail-history` 안에 `getByText('한국투자 위탁')` — 모두 정확 일치(근거 줄과 겹치지 않게).
  - `외화 체결 단가는 현지 통화다`: `usdDetail()` → `$200.00`.
  - `기업행위가 있으면 종류와 전후 주식 수가 나온다`: `twoAccountDetail()` → `2026-04-01` · `분할` · `1주 → 2주`.
  - `기업행위가 없으면 영역이 없다`: `samsungDetail()` → `기업행위` 없음.
  - `instrumentDetailPresent.test.ts`: `showAccountNames` 세 경우(빈 응답 false · 한 계좌 false · 체결 A + 매도 B true), `ratioText(2) === '1주 → 2주'`, `ratioText(0.5) === '2주 → 1주'`, `ratioText(1.5) === '1주 → 1.5주'`.
- [ ] **Step 2: 실행해 실패 확인.** Expected: FAIL.
- [ ] **Step 3: 구현.**
- [ ] **Step 4: 통과 확인.** Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목 상세에 거래내역과 기업행위를 그린다`

---

### Task 8: `알림 걸기`

**Files:**
- Modify: `present.ts`, `InstrumentDetailScreen.tsx`
- Test: `instrumentDetail.test.tsx`, `instrumentDetailPresent.test.ts`

**Interfaces:**
- Consumes: `EditorInstrument` · `EditorStart`(`src/app/navigation/types.ts`), `AlertEditorNavigator`가 `{ mode: 'new', instrument }`이면 조건 선택(`trigger`)부터 연다(기존 동작).
- Produces (`present.ts`): `editorInstrumentOf(data: InstrumentDetailData): EditorInstrument | null` — `delisted_on`이 있으면 null, 아니면 `{ id: instrument.id, label: instrument.label, market: instrument.market, held: data.position !== null, lastClose: instrument.last_close, lastCloseOn: instrument.last_close_on }`.
- 화면: 응답이 있고 `editorInstrumentOf`가 null이 아닐 때만 스크롤 맨 끝에 `<Button label="알림 걸기" onPress={() => navigation.navigate('alert-editor', { mode: 'new', instrument })} />`. 로딩 · 404 · 오류에는 없다.

- [ ] **Step 1: 실패하는 테스트.**
  - `알림 걸기는 응답의 보유 여부와 직전 종가로 편집기를 연다`(Review 3): `samsungDetail()` → 누름 → `moves`의 마지막이 `alert-editor`, params `{ mode: 'new', instrument: { id: SAMSUNG_ID, label: '삼성전자', market: 'KR', held: true, lastClose: <응답의 last_close>, lastCloseOn: <응답의 last_close_on> } }` — 기대값은 픽스처에서 읽는다(Task 11의 골든에서 직전 종가가 달라도 그대로 통과하게).
  - `보유하지 않은 종목은 held가 거짓이다`: `notHeldDetail()` → `held false`.
  - `응답 전에는 알림 걸기가 없다`(Review 3): 응답을 `wait`로 붙잡은 동안 `알림 걸기` 없음.
  - `상장폐지 종목에는 알림 걸기가 없다`(Review 3): `delistedDetail()` → 없음, 다른 영역은 그대로.
  - `instrumentDetailPresent.test.ts`: `editorInstrumentOf(delistedDetail().data) === null`, `usdDetail()`은 `market 'US'`.
- [ ] **Step 2: 실행해 실패 확인.** Expected: FAIL.
- [ ] **Step 3: 구현.** 버튼 위 주석: "응답이 온 뒤에만 그린다. 그 전에는 보유 여부와 직전 종가를 몰라 편집기를 틀리게 채운다. 상장폐지 종목은 알림 대상이 아니라 버튼이 없다."
- [ ] **Step 4: 통과 확인.** `npx jest src/__tests__/instrumentDetail.test.tsx src/__tests__/alertEditorFlow.test.tsx`. Expected: PASS(편집기 쪽 기존 `held` 테스트가 그대로 통과).
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목 상세의 알림 걸기가 종목이 채워진 새 알림을 연다`

---

### Task 9: 종목별 행 누름과 렌즈 도움말

**Files:**
- Modify: `src/screens/positions/PositionRow.tsx`, `src/screens/positions/PositionsScreen.tsx`
- Test: `src/__tests__/positions.test.tsx`

**Interfaces:**
- Produces: `PositionRow`에 `onPress?: () => void`. 있으면 `Pressable`(`accessibilityRole="button"`, `accessibilityLabel={`${row.label} 상세 보기`}`, 스타일 `({ pressed }) => [styles.row, undecomposed && …, pressed && { backgroundColor: palette.surface }]` — `AccountRow`와 같은 방식), 없으면 지금처럼 `View`. `testID`는 두 경우 모두 그대로. 끝 화살표는 두지 않는다. 파일 머리 주석의 "눌러도 아무 일이 없다…"를 "`instrument_id`가 있는 행만 누를 수 있고 종목 상세로 간다. 예수금 행과 ETF 분해 모드의 행에는 그 값이 없어 눌리지 않는다"로 바꾼다.
- `PositionsScreen`: `useNavigation<NavigationProp<RootStackParamList & TabParamList>>()`(실현손익 화면과 같은 방식)으로 `renderItem`이 `item.instrument_id`가 있을 때만 `onPress={() => navigation.navigate('instrument-detail', { instrumentId: item.instrument_id, label: item.label })}`. 예수금 · 렌즈를 화면이 따로 가리지 않는다. `LENS_HELP` 끝에 `' ETF 분해 모드에서는 종목 상세를 열 수 없어요'`(앞 문장과 공백 하나로 잇는다)를 더한다.

- [ ] **Step 1: 실패하는 테스트.** 이 태스크는 `positionsWithInstrumentIds()`로 응답한다(Task 11에서 `goldenPositions`로 바꾼다).
  - 기존 `행을 눌러도 아무 일이 없다`를 지우고 `종목 행을 누르면 종목 상세가 열린다`로 바꾼다: `renderWithNavigation(<PositionsScreen />, { others: ['instrument-detail'], onNavigate })`, `삼성전자 상세 보기` 버튼 누름 → `{ name: 'instrument-detail', params: { instrumentId: SAMSUNG_ID, label: '삼성전자' } }`.
  - `예수금 행은 눌리지 않는다`(Review 4): 버튼 이름 목록에 `KRW 예수금 상세 보기` · `USD 예수금 상세 보기`가 없다.
  - `ETF 분해 모드의 행은 눌리지 않는다`(Review 4): `goldenPositionsLookThrough`(키 없음) → 이름이 `상세 보기`로 끝나는 버튼이 0개.
  - `토글 설명`의 `눌러야 설명이 펼쳐지고…`에 `screen.getByText(/ETF 분해 모드에서는 종목 상세를 열 수 없어요/)`를 더한다.
- [ ] **Step 2: 실행해 실패 확인.** `npx jest src/__tests__/positions.test.tsx`. Expected: FAIL.
- [ ] **Step 3: 구현.**
- [ ] **Step 4: 통과 확인.** `npx jest && npx tsc --noEmit`. Expected: 통과(`allocation.test.tsx`의 렌즈 설명은 비중 화면 자체 문구라 영향 없음).
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목별 행을 누르면 종목 상세로 간다`

---

### Task 10: 알림 카드의 확정 전 보유 상태

**Files:**
- Modify: `src/api/alertTypes.ts`, `src/screens/alerts/status.ts`, `src/fixtures/alerts.ts`
- Test: `src/__tests__/alertFormat.test.tsx`(`statusOf — 카드 문구` 표), `src/__tests__/alertsTab.test.tsx`

**Interfaces:**
- Produces: `UnknownReason`에 `'AWAITING_FINAL'`. `statusOf`는 `status === 'ACTIVE'` · `last_result === 'UNKNOWN'` · `unknown_reason === 'AWAITING_FINAL'`이면 `{ label: '오늘 저녁 첫 판정', tone: 'watching' }`를 낸다(`확인 불가 · …` 꼴이 아니다). `REASON` 표는 `Record<Exclude<UnknownReason, 'AWAITING_FINAL'>, string>`으로 바꿔 이 사유가 표를 거치지 않는다는 것을 타입이 말하게 한다. 분기 위 주석: "오늘 산 종목은 저녁 확정 스냅샷이 생긴 뒤 첫 판정을 한다. 잘못된 상태가 아니라 기다리는 상태라 감시 중과 같은 색이다."
- `StatusBadge`는 고치지 않는다 — `watching`이면 이미 `● {label}`과 감시 중 색으로 그린다.
- 편집기 · 알림 상세의 현재값 상자(`src/screens/alerts/PreviewBoxes.tsx`의 `CurrentBox`)는 서버가 완성한 줄 문구(`… — 오늘 저녁 확정 후 첫 판정을 해요`)를 그대로 그리므로 앱 변경이 없다.
- 이 사유는 백엔드가 배포된 뒤에만 온다. 앱이 먼저 나가도 서버가 아직 이 값을 내지 않으므로 지금 타입에 없는 값이 화면에 닿는 일은 없다.

- [ ] **Step 1: 실패하는 테스트.**
  - `alertFormat.test.tsx`의 `statusOf — 카드 문구` 표에 한 줄: `{ ...base, status: 'ACTIVE', last_result: 'UNKNOWN', unknown_reason: 'AWAITING_FINAL' }` → `'오늘 저녁 첫 판정'`, `'watching'`.
  - `alertsTab.test.tsx` `확정 전 보유 알림 카드는 오늘 저녁 첫 판정이다`: `alertsFixture`를 복사해 한 카드를 `last_result 'UNKNOWN'` · `unknown_reason 'AWAITING_FINAL'`로 바꾼 응답 → `● 오늘 저녁 첫 판정`이 있고 `확인 불가 · ` 로 시작하는 그 카드 문구는 없다. (픽스처 변형이 여러 테스트에 쓰이면 `src/fixtures/alerts.ts`에 `awaitingFinalAlertsFixture`로 둔다.)
- [ ] **Step 2: 실행해 실패 확인.** `npx jest src/__tests__/alertFormat.test.tsx src/__tests__/alertsTab.test.tsx`. Expected: 타입 오류(`'AWAITING_FINAL'`이 `UnknownReason`에 없음) 또는 FAIL.
- [ ] **Step 3: 구현.**
- [ ] **Step 4: 통과 확인.** 같은 명령 + `npx tsc --noEmit`. Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 확정 전 보유 알림 카드를 오늘 저녁 첫 판정으로 보인다`

---

### Task 11: 백엔드 골든으로 바꾸기 (백엔드 `feat/instrument-detail`이 main에 머지된 뒤)

**Files:**
- Create: `src/fixtures/golden/instrument-detail.json`
- Modify: `src/fixtures/golden/positions.json`, `src/fixtures/golden.ts`, `src/fixtures/instrumentDetail.ts`, `src/__tests__/types.test.ts`, `positions.test.tsx`, `instrumentDetail.test.tsx`

**Interfaces:**
- Produces: `goldenInstrumentDetail: InstrumentDetailResponse` — 기존 골든과 같은 두 줄(`const instrumentDetailShape: AsJson<InstrumentDetailResponse> = instrumentDetailJson;` 후 단언). 필드가 빠지거나 이름이 바뀌면 이 대입에서 타입 오류가 난다.
- `samsungDetail()`은 `goldenInstrumentDetail`의 깊은 사본을 돌려준다. 다른 변형은 그것을 바탕으로 만든다. `positionsWithInstrumentIds()`를 지운다.

- [ ] **Step 1: 머지 확인.** `git -C /Users/yhr/Dev/workspace/personal/stock-project/back-end fetch origin && git -C …/back-end log origin/main --oneline -- src/test/resources/golden/instrument-detail.json`. Expected: 커밋이 있다. 없으면 멈추고 보고한다.
- [ ] **Step 2: 복사.** README의 방식(백엔드 골든의 복사본)을 따르되, 백엔드 작업 트리 상태와 무관하게 main의 것을 쓴다.

```bash
B=/Users/yhr/Dev/workspace/personal/stock-project/back-end
git -C $B show origin/main:src/test/resources/golden/instrument-detail.json > src/fixtures/golden/instrument-detail.json
git -C $B show origin/main:src/test/resources/golden/positions.json > src/fixtures/golden/positions.json
```

- [ ] **Step 3: 실패하는 테스트(`types.test.ts`).**
  - `종목 상세 — 계좌별 수량의 합이 보유 수량이다`: `goldenInstrumentDetail.data.position?.quantity === 200`, `Σ by_account.quantity === 200`, `realized.total.realized_pnl_krw === 277000`, `empty_reason === null`.
  - `종목별 — 직접 보유 종목 행에만 instrument_id가 있다`: 삼성전자 행 `instrument_id === SAMSUNG_ID`, `CASH-KRW` 행에 `'instrument_id' in row === false`.
- [ ] **Step 4: 실행해 실패 확인.** `npx tsc --noEmit && npx jest`. Expected: `golden.ts`에 export가 없어 실패. 골든 모양이 Task 1 타입과 다르면 여기서 타입 오류가 난다 — 그때는 타입을 맞추기 전에 설계 §3.2 · §3.3과 견줘 어느 쪽이 틀렸는지 보고한다.
- [ ] **Step 5: 구현.** `golden.ts`에 위 두 줄. `positions.test.tsx`는 `positionsWithInstrumentIds()` 대신 `goldenPositions`. `instrumentDetail.ts`의 바탕을 골든으로.
- [ ] **Step 6: 통과 확인.** `npx jest && npx tsc --noEmit`. Expected: 전부 통과. 단언값이 골든과 다르면 설계 §3.2(샘플 응답)와 견줘 원인을 보고한다 — 골든에 맞춰 단언을 고치지 않는다(`last_close`는 §3.2가 예시라고 했으므로 예외, Task 8 테스트는 이미 응답에서 읽는다).
- [ ] **Step 7: 커밋(요청 시).** `test: 종목 상세와 종목별 골든을 백엔드 응답으로 바꾼다`

---

### Task 12: 마무리와 끝 보고

- [ ] **Step 1:** 최신 `origin/main`에 리베이스(겹치면 `npm ci` 승인 후 재설치), `npx jest && npx tsc --noEmit`. Expected: 통과.
- [ ] **Step 2: 끝 보고.** 사용자에게 아래를 보고하고, 커밋 · 푸시 · PR은 요청받으면 진행한다(PR 본문에 "백엔드 `feat/instrument-detail` 머지 · 배포 뒤 머지"를 적는다).
  - 바뀐 파일(위 파일 구조 표 기준), 테스트 결과(통과 수 · 실패 0, `tsc` 결과).
  - 남은 것: 머리글 시장 배지의 실기기 확인(테스트 렌더러는 머리글을 그리지 않아 제목 문자열만 단언한다).
  - 영향받는 통합테스트 케이스(설계 §7 표): PF10-01(종목별 행에 `instrument_id`, 그 행이 버튼) · PF10-03 · PF10-04(`trades[]`, 체결일 `executed_on`) · PF10-05(`realized.rows[]` · `realized.total`, 원가 기준 표기는 보유 중일 때만) · PF10-06(`by_account[].basis`, 배지는 실현손익 영역의 근거 줄) · PF10-07(`CA_UNKNOWN`이 종목 상세 응답에도) · N-51(`realized.rows` 추가) · X1-03(`알림 걸기`의 `held`). 알림 미리보기 현재값 · 확인 불가 사유 · 카드 상태 문구 케이스(카드 `오늘 저녁 첫 판정` · 감시 중과 같은 색 — Task 10, 미리보기 줄 `… — 오늘 저녁 확정 후 첫 판정을 해요`와 `NOT_HELD` 오류의 `current = null`은 서버 문구를 그대로 그린다). 알림 생성 `NOT_HELD` · 검색 `held` 기준 변경은 백엔드 몫이라 앱 변경과 무관함을 함께 적는다.

---
