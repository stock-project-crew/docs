# 계좌 연동 화면 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 계좌 탭에서 들어가는 연동 계좌 목록(`account-link`)과 KIS 등록 폼(`account-link/new`)을 만들고, 계좌 탭에 `계좌 연동 관리` 버튼과 점을 단다.

**Architecture:** `GET /accounts`는 봉투 없는 응답이라 `ScreenFrame` 없이 `useAccountLinks`로 그린다. 해제는 `useMutation`으로, 등록은 자격증명이 mutation 캐시에 남지 않게 제출 핸들러가 `linkAccount`를 직접 부른다. 등록 · 해제 뒤에는 `invalidateAccountLinkData`가 포트폴리오 조회 전체를 무효화한다. KIS 전용 규칙(상품코드 · 기본 라벨 · 칸 검사)은 `screens/accountLink/form.ts`에 모은다.

**Tech Stack:** React Native 0.81 · Expo SDK 54 · TanStack Query 5 · React Navigation 7 · jest-expo · Testing Library(RNTL 14)

**Spec:** [`docs/yhr/specs/portfolio-management/2026-10-18-account-link-screen-design.md`](../specs/portfolio-management/2026-10-18-account-link-screen-design.md) (이하 "설계"). 서버 계약은 [`2026-10-16-account-link-api-design.md`](../specs/portfolio-management/2026-10-16-account-link-api-design.md)(이하 "API 설계"), 상위 스펙은 [`2026-07-28-portfolio-management-spec.md`](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md), 화면 구조는 [`app-information-architecture.md`](../specs/app-information-architecture.md).

**작업 위치:** `/Users/yhr/Dev/workspace/personal/stock-project/front-end`, 브랜치 `feat/account-link`(`origin/main` `650b484`에서 딴다). 경로는 `front-end/src/` 기준이다(`__tests__/…`는 `src/__tests__/…`).

## Global Constraints

- 스펙 · 설계 · IA를 고치지 않는다. 막히거나 설계가 틀렸다고 보면 멈추고 보고한다.
- 패키지를 설치하지 않는다. Expo SDK를 올리지 않는다(Expo Go 상한 54).
- 개발 서버 · 시뮬레이터 · 백엔드 기동, 실제 등록 요청은 사용자 승인 후에 한다.
- 테스트 먼저. 실패를 눈으로 확인한 뒤 구현한다. 태스크 끝마다 `npx jest`와 `npx tsc --noEmit`이 통과한다.
- 커밋은 사용자가 요청할 때만 한다. 각 태스크의 커밋 단계는 "요청받았을 때 이 메시지로"라는 뜻이다. 메시지는 한국어, 접두 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝에 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- 주석은 히스토리 없이 최신 사실만. 검증하지 않은 것을 단정하지 않는다. 밀도와 어조는 `screens/cashflows` · `screens/accounts`를 따른다.
- 자격증명은 가짜 값만: 앱키 `test-app-key`, 시크릿 `test-app-secret`, 계좌번호 `00000000-01`(숫자 `0000000001`) 꼴. 실제 값을 코드 · 픽스처 · 테스트 · 로그에 넣지 않는다.
- 앱키 · 시크릿 · 계좌번호는 폼 컴포넌트의 `useState`에만 둔다. 컨텍스트 · 네비게이션 파라미터 · `kvStore` · SecureStore · 쿼리 키 · `useMutation`에 넣지 않는다. 이 기능 코드에 `console.*`를 두지 않는다(설계 §5).
- 서버 오류 문구는 `ApiError.message`를 그대로 쓰고, `code`로는 자리만 고른다(설계 §3.3).
- 문구는 설계 그대로 쓴다. 이 계획이 옮긴 문구도 설계와 다르면 설계가 맞다.
- `docs/hhj/` · `docs/jdh/` · `docs/team-architecture-agreement.md`를 근거로 쓰지 않는다.

## Review Focus

1. **계좌번호에 공백 · 하이픈이 섞인 값을 붙여 넣는다** (`1234 5678-01`) — 숫자 10자리만 남아 `12345678-01`로 보이고 `1234567801`로 나가야 한다. → Task 2 `accountDigits`, Task 5 붙여넣기 테스트.
2. **앱키 · 시크릿 끝에 줄바꿈이 붙어 들어온다** — 공백을 지운 값이 나가야 한다. → Task 2 `toLinkRequest`, Task 5 요청 본문 테스트.
3. **라벨이 이모지 · 한글로 정확히 30자** — 30자는 통과, 31자는 `30자 이내로 입력해 주세요`. → Task 2 경계 테스트.
4. **서버가 우리 오류 봉투가 아닌 본문으로 500을 준다** — 폼 위에 `요청을 처리하지 못했어요`. → Task 5(봉투 없는 JSON). JSON이 아닌 본문은 `client.test.ts`가 이미 본다.
5. **등록 응답 전에 뒤로 나간다** — 떠난 화면이 `goBack()`을 부르지 않아야 한다(부르면 실앱에서 `account-link`까지 걷혀 계좌 탭으로 튄다). 목록 · 뷰는 무효화된다. → Task 5.

---

## 파일 구조

| 파일 | 책임 | 태스크 |
|---|---|---|
| `api/types.ts` | `CollectionStatus` · `LinkedAccount` · `AccountListResponse` · `LinkAccountRequest` · `LinkAccountResponse` 추가, `AccountRowData.last_collection` 수정 | 1 |
| `api/endpoints.ts` | `fetchAccountLinks` · `linkAccount` · `unlinkAccount` | 1 |
| `api/queries/keys.ts` | `accountLinks` | 1 |
| `api/queries/useAccountLinks.ts` | 연동 계좌 목록 조회 (생성) | 1 |
| `api/queries/accountLinkInvalidation.ts` | 등록 · 해제 뒤 무효화 (생성) | 1 |
| `fixtures/accountLinks.ts` | `GET /accounts` 손 픽스처 (생성) | 1 |
| `screens/accountLink/form.ts` | 계좌번호 · 기본 라벨 · 칸 검사 · 요청 만들기 (생성) | 2 |
| `screens/accountLink/linkStatus.ts` | 상태 줄 · 상품 이름 (생성) | 2 |
| `ui/TextField.tsx` | 보기 버튼 접근성 문구를 받는다 | 3 |
| `ui/ConfirmSheet.tsx` | `error` 한 줄 | 3 |
| `api/queries/useUnlinkAccount.ts` | 해제 변경 훅 (생성) | 4 |
| `screens/accountLink/AccountLinkScreen.tsx` | 연동 계좌 목록 · 해제 시트 (생성) | 4 |
| `screens/accountLink/LinkedAccountRow.tsx` | 목록 한 줄 (생성) | 4 |
| `screens/accountLink/AccountLinkFormScreen.tsx` | KIS 등록 폼 (생성) | 5 |
| `app/navigation/types.ts` · `RootStack.tsx` | `account-link` · `account-link/new` 라우트 | 4 · 5 |
| `testing/renderWithStack.tsx` | `queryClient`도 돌려준다 | 4 |
| `screens/accounts/AccountsScreen.tsx` | `계좌 연동 관리` 버튼(빈 상태 포함) | 6 |
| `screens/accounts/tabDot.ts` | 계좌 탭 점 판정 (생성) | 6 |
| `envelope/EmptyState.tsx` · `envelope/ScreenFrame.tsx` | `NO_ACCOUNTS` 보조 문구 · 계좌 탭 예외 · `action` 주석 | 6 |
| `app/navigation/Tabs.tsx` | 계좌 탭 점 | 6 |

---

## Task 0: 브랜치

- [ ] **Step 1:** `git -C front-end fetch origin && git -C front-end switch -c feat/account-link 650b484`
- [ ] **Step 2:** `cd front-end && npx jest && npx tsc --noEmit` — 시작점이 통과하는지 본다. 실패하면 멈추고 보고한다.

---

## Task 1: API 층 — 타입 · 요청 · 조회 · 무효화 · 픽스처

**Files:**
- Modify: `api/types.ts`, `api/endpoints.ts`, `api/queries/keys.ts`
- Create: `api/queries/useAccountLinks.ts`, `api/queries/accountLinkInvalidation.ts`, `fixtures/accountLinks.ts`
- Test: `__tests__/accountLinkApi.test.tsx`

**Interfaces:**
- Produces:
  ```ts
  // api/types.ts
  export type CollectionStatus = { state: string; as_of: string; failure_reason: string | null };
  export type LinkedAccount = {
    account_id: string; broker: string; label: string;
    account_type: 'GENERAL' | 'PENSION'; source: string;
    link_state: AccountLinkState; last_synced_at: string | null;
    last_collection: CollectionStatus | null;
  };
  export type AccountListResponse = { accounts: LinkedAccount[] };
  export type LinkAccountRequest = { app_key: string; app_secret: string; account_number: string; label: string };
  export type LinkAccountResponse = { account_id: string; link_state: AccountLinkState; challenge: null };
  // AccountRowData.last_collection: CollectionStatus | null  (주석: 그 계좌의 최근 수집. 실행이 없으면 null)

  // api/endpoints.ts
  fetchAccountLinks(): Promise<AccountListResponse>            // GET /accounts
  linkAccount(request: LinkAccountRequest): Promise<LinkAccountResponse>   // POST /accounts
  unlinkAccount(accountId: string): Promise<void>              // DELETE /accounts/{encodeURIComponent(id)}

  // api/queries/keys.ts
  keys.accountLinks = ['account-links'] as const

  // api/queries/useAccountLinks.ts — useAccounts와 같은 모양
  useAccountLinks(): { accounts: LinkedAccount[] | null; loading: boolean; refreshing: boolean;
                       error: unknown | undefined; refetch: () => void }

  // api/queries/accountLinkInvalidation.ts
  invalidateAccountLinkData(queryClient: QueryClient): void

  // fixtures/accountLinks.ts
  accountLinksFixture: AccountListResponse      // 아래 다섯 계좌, 서버 정렬(account_type, label)
  emptyAccountLinks: AccountListResponse         // { accounts: [] }
  ```
- `accountLinksFixture` 계좌 (모두 `broker: '한국투자증권'`, `source: 'KIS'`, `last_synced_at: null`):

  | `account_id` | `label` | `account_type` | `link_state` | `last_collection` |
  |---|---|---|---|---|
  | `30000000-0000-0000-0000-000000000001` | 한국투자 위탁 | GENERAL | CONNECTED | `{ state: 'DONE', as_of: '2026-10-16', failure_reason: null }` |
  | `…0002` | 한국투자 위탁 2 | GENERAL | CONNECTED | `{ state: 'FAILED', as_of: '2026-10-16', failure_reason: 'SOURCE_API_ERROR' }` |
  | `…0003` | 한국투자 위탁 3 | GENERAL | REAUTH_REQUIRED | `null` |
  | `…0004` | 한국투자 연금저축 | PENSION | CONNECTING | `null` |
  | `…0005` | 한국투자 연금저축 2 | PENSION | CONNECTING | `{ state: 'FAILED', as_of: '2026-10-18', failure_reason: 'CREDENTIAL_UNREADABLE' }` |

  파일 머리 주석: 백엔드 골든이 없어 `AccountDto` · `CollectionStatus`를 보고 손으로 쓴 응답이라는 것, 앱 코드는 쓰지 않는다는 것.

- [ ] **Step 1: 실패하는 테스트를 쓴다** — `__tests__/accountLinkApi.test.tsx` (`serveRoutes`, `setAccessToken('테스트-토큰')`)

  ```ts
  it('연동 계좌 목록은 GET /accounts다', async () => {
    const calls = serveRoutes([{ path: '/accounts', body: accountLinksFixture }]);
    expect((await fetchAccountLinks()).accounts).toHaveLength(5);
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/accounts' });
  });
  it('등록은 본문을 그대로 POST /accounts로 보낸다', async () => {
    const calls = serveRoutes([{ method: 'POST', path: '/accounts', status: 202,
      body: { account_id: 'a-1', link_state: 'CONNECTING', challenge: null } }]);
    const request = { app_key: 'test-app-key', app_secret: 'test-app-secret', account_number: '0000000001', label: '생활비' };
    expect((await linkAccount(request)).link_state).toBe('CONNECTING');
    expect(calls[0].body).toEqual(request);
  });
  it('해제는 DELETE /accounts/{id}이고 204에 값이 없다', /* path '/accounts/30000000-0000-0000-0000-000000000001', status 204 → undefined */);
  it('등록 · 해제 뒤 포트폴리오 조회 전체를 무효화한다', () => {
    const queryClient = new QueryClient();
    const spy = jest.spyOn(queryClient, 'invalidateQueries');
    invalidateAccountLinkData(queryClient);
    expect(spy.mock.calls.map(([filters]) => filters?.queryKey)).toEqual([
      ['account-links'], ['accounts'], ['summary'], ['positions'], ['allocation'],
      ['realized-pnl'], ['asset-change'], ['cashflows'], ['catalog'],
    ]);
  });
  it('useAccountLinks가 목록을 준다', /* renderHook + QueryClientProvider, accounts[0].label === '한국투자 위탁' */);
  ```

- [ ] **Step 2:** `npx jest __tests__/accountLinkApi.test.tsx` — 가져올 이름이 없어 FAIL.
- [ ] **Step 3: 구현한다** — 위 Interfaces대로. `useAccountLinks`는 `useQuery({ queryKey: keys.accountLinks, queryFn: fetchAccountLinks })`, `accounts: query.data?.accounts ?? null`. 무효화 순서는 테스트의 순서.
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` — PASS. 골든 `accounts.json`의 `last_collection: null`이 새 타입에 맞는지 `fixtures/golden.ts`의 타입 대입이 검사한다.
- [ ] **Step 5: 커밋** — `feat: 연동 계좌 목록 조회와 등록 · 해제 요청을 둔다`

---

## Task 2: 순수 함수 — 계좌번호 · 라벨 · 칸 검사 · 상태 줄

**Files:**
- Create: `screens/accountLink/form.ts`, `screens/accountLink/linkStatus.ts`
- Test: `__tests__/accountLinkForm.test.ts`, `__tests__/linkStatus.test.ts`

**Interfaces:**
- Consumes: `LinkAccountRequest` · `LinkedAccount` (Task 1)
- Produces:
  ```ts
  // form.ts
  export type LinkForm = { appKey: string; appSecret: string; accountDigits: string; label: string; labelEdited: boolean };
  export type LinkFormField = 'appKey' | 'appSecret' | 'accountNumber' | 'label';
  export const emptyLinkForm: LinkForm;            // 모두 '' · labelEdited false
  export function accountDigits(input: string): string;          // 숫자만, 앞 10자리
  export function displayAccountNumber(digits: string): string;  // 9자리째부터 `12345678-0`
  export function defaultLabelFor(digits: string): string | null; // 10자리 · 01 → '한국투자 위탁', 22 → '한국투자 연금저축'
  export function withAccountInput(form: LinkForm, input: string): LinkForm;
  export function withLabel(form: LinkForm, label: string): LinkForm;  // labelEdited = true
  export function validateLinkForm(form: LinkForm): Partial<Record<LinkFormField, string>>;
  export function toLinkRequest(form: LinkForm): LinkAccountRequest;   // trim, account_number = 숫자 10자리

  // linkStatus.ts
  export function statusLine(account: LinkedAccount): { text: string; tone: 'muted' | 'warn' };
  export function productLabel(type: LinkedAccount['account_type']): string;  // GENERAL '위탁' · PENSION '연금저축'
  ```
- `withAccountInput` 라벨 규칙(설계 §4): `labelEdited`가 참이면 라벨을 건드리지 않는다. 거짓이면 라벨을 `defaultLabelFor(digits) ?? ''`로 둔다 — 미리 채운 값은 지금 계좌번호의 기본값일 때만 남는다(설계가 말하지 않는 10자리 미만 · 그 밖 상품코드의 경우, 구현 판단).
- 길이는 서버와 같은 단위로 센다(API 설계 §3.1 · `LinkCommand`): 앱키 · 시크릿은 `.length`(UTF-16) 1,024 이하, 라벨은 코드 포인트(`[...s].length`) 1 ~ 30.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

  `__tests__/accountLinkForm.test.ts`
  ```ts
  expect(accountDigits('1234 5678-01')).toBe('1234567801');
  expect(accountDigits('123456780199')).toBe('1234567801');
  expect(displayAccountNumber('12345678')).toBe('12345678');
  expect(displayAccountNumber('123456780')).toBe('12345678-0');
  expect(displayAccountNumber('1234567801')).toBe('12345678-01');
  expect(defaultLabelFor('0000000001')).toBe('한국투자 위탁');
  expect(defaultLabelFor('0000000022')).toBe('한국투자 연금저축');
  expect(defaultLabelFor('0000000029')).toBeNull();
  expect(defaultLabelFor('000000000')).toBeNull();
  // 라벨 미리 채우기
  const filled = withAccountInput(emptyLinkForm, '00000000-01');
  expect(filled.label).toBe('한국투자 위탁');
  expect(withAccountInput(filled, '0000000022').label).toBe('한국투자 연금저축');
  expect(withAccountInput(withLabel(filled, '생활비'), '0000000022').label).toBe('생활비');
  expect(withAccountInput(filled, '000000002').label).toBe('');
  expect(withAccountInput(filled, '0000000029').label).toBe('');
  // 칸 검사
  expect(validateLinkForm(emptyLinkForm)).toEqual({
    appKey: '앱키를 입력해 주세요', appSecret: '앱 시크릿을 입력해 주세요',
    accountNumber: '계좌번호 10자리를 입력해 주세요', label: '라벨을 입력해 주세요' });
  const ok = { appKey: 'k', appSecret: 's', accountDigits: '0000000001', label: '가', labelEdited: true };
  expect(validateLinkForm({ ...ok, appKey: 'x'.repeat(1025) }).appKey).toBe('1,024자 이내로 입력해 주세요');
  expect(validateLinkForm({ ...ok, appKey: ` ${'x'.repeat(1024)} ` })).toEqual({});
  expect(validateLinkForm({ ...ok, label: '😀'.repeat(30) })).toEqual({});
  expect(validateLinkForm({ ...ok, label: '가'.repeat(31) }).label).toBe('30자 이내로 입력해 주세요');
  expect(validateLinkForm({ ...ok, label: '   ' }).label).toBe('라벨을 입력해 주세요');
  // 오류 문구에 입력값이 없다
  expect(JSON.stringify(validateLinkForm({ ...ok, appKey: 'test-app-key'.repeat(100) }))).not.toContain('test-app-key');
  // 요청
  expect(toLinkRequest({ appKey: ' test-app-key\n', appSecret: 'test-app-secret\n', accountDigits: '0000000001', label: ' 생활비 ', labelEdited: true }))
    .toEqual({ app_key: 'test-app-key', app_secret: 'test-app-secret', account_number: '0000000001', label: '생활비' });
  ```

  `__tests__/linkStatus.test.ts` — `accountLinksFixture`의 다섯 계좌와 두 추가 사례:
  ```ts
  const [done, failed, reauth, connecting, firstFailed] = accountLinksFixture.accounts;
  expect(statusLine(done)).toEqual({ text: '연동됨', tone: 'muted' });
  expect(statusLine(failed)).toEqual({ text: '연동됨 · 10-16 수집 실패', tone: 'warn' });
  expect(statusLine(reauth)).toEqual({ text: '재인증 필요', tone: 'warn' });
  expect(statusLine(connecting)).toEqual({ text: '연동 중 · 다음 정기 수집 뒤 잔고가 반영돼요', tone: 'muted' });
  expect(statusLine(firstFailed)).toEqual({
    text: '첫 수집에 실패했어요. 앱키·계좌번호를 확인하고 해제한 뒤 다시 등록해 주세요', tone: 'warn' });
  // CONNECTING + DONE 은 연동 중, 모르는 state 는 link_state만으로
  expect(statusLine({ ...connecting, last_collection: { state: 'DONE', as_of: '2026-10-18', failure_reason: null } }).text)
    .toBe('연동 중 · 다음 정기 수집 뒤 잔고가 반영돼요');
  expect(statusLine({ ...done, last_collection: { state: 'SKIPPED', as_of: '2026-10-18', failure_reason: null } }).text).toBe('연동됨');
  expect(productLabel('GENERAL')).toBe('위탁');
  expect(productLabel('PENSION')).toBe('연금저축');
  ```
- [ ] **Step 2:** `npx jest __tests__/accountLinkForm.test.ts __tests__/linkStatus.test.ts` — FAIL.
- [ ] **Step 3: 구현한다** — 날짜는 `formatMonthDay`(`format/date.ts`)를 쓴다. `DISCONNECTED`는 `GET /accounts`에 오지 않지만 타입에 있으므로 계좌별 배지와 같은 `연동 해제됨` · muted로 둔다(설계 §3.1 표 밖, 구현 판단).
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` — PASS.
- [ ] **Step 5: 커밋** — `feat: 계좌 등록 폼 규칙과 연동 상태 줄을 둔다`

---

## Task 3: 공용 UI — `TextField` 보기 문구 · `ConfirmSheet` 오류 줄

**Files:**
- Modify: `ui/TextField.tsx`, `ui/ConfirmSheet.tsx`
- Test: `__tests__/controls.test.tsx` (기존 파일에 더한다)

**Interfaces:**
- Produces:
  ```ts
  TextFieldProps.revealLabels?: { show: string; hide: string }  // 기본 { show: '비밀번호 보기', hide: '비밀번호 가리기' }
  ConfirmSheet props: error?: string | null   // message 아래, palette.errorText, type.caption
  ```

- [ ] **Step 1: 실패하는 테스트를 쓴다**
  ```ts
  it('보기 버튼 문구를 바꿀 수 있다', async () => {
    await render(<TextField label="앱 시크릿" secure revealLabels={{ show: '시크릿 보기', hide: '시크릿 가리기' }} value="" onChangeText={() => {}} />);
    await fireEvent.press(screen.getByRole('button', { name: '시크릿 보기' }));
    expect(screen.getByRole('button', { name: '시크릿 가리기' })).toBeTruthy();
  });
  it('보기 버튼 기본 문구는 비밀번호다', /* revealLabels 없이 '비밀번호 보기' */);
  it('확인 시트에 오류 한 줄을 띄운다', /* <ConfirmSheet visible title="t" confirmLabel="해제" error="저장소 오류" …/> → getByText('저장소 오류') */);
  ```
- [ ] **Step 2:** `npx jest __tests__/controls.test.tsx` — FAIL.
- [ ] **Step 3: 구현한다.** `ConfirmSheet` 머리 주석의 쓰는 곳 목록에 계좌 해제를 더한다.
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` — PASS.
- [ ] **Step 5: 커밋** — `feat: 입력칸 보기 문구와 확인 시트 오류 줄을 받는다`

---

## Task 4: 연동 계좌 목록 화면과 해제

**Files:**
- Create: `api/queries/useUnlinkAccount.ts`, `screens/accountLink/AccountLinkScreen.tsx`, `screens/accountLink/LinkedAccountRow.tsx`
- Modify: `app/navigation/types.ts`, `app/navigation/RootStack.tsx`, `testing/renderWithStack.tsx`
- Test: `__tests__/accountLink.test.tsx`

**Interfaces:**
- Consumes: `useAccountLinks` · `unlinkAccount` · `invalidateAccountLinkData` · `accountLinksFixture` (Task 1), `statusLine` · `productLabel` (Task 2), `ConfirmSheet.error` (Task 3)
- Produces:
  ```ts
  // navigation/types.ts — RootStackParamList
  'account-link': undefined;
  'account-link/new': undefined;   // Task 5가 화면을 단다
  // RootStack: <Stack.Screen name="account-link" component={AccountLinkScreen} options={{ title: '계좌 연동' }} />
  // renderWithStack 반환값에 queryClient 추가: { ...rendered, navigation, queryClient }
  useUnlinkAccount(): UseMutationResult<void, unknown, string>   // onSettled → invalidateAccountLinkData
  export function AccountLinkScreen()   // 반환 타입은 기존 화면처럼 적지 않는다
  ```
- 행: 라벨(본문 굵게) · `TextButton` `해제`(`accessibilityLabel` `{라벨} 해제`, tone danger) / 둘째 줄 `{productLabel} · {statusLine.text}`. `tone: 'warn'`이면 상태 줄은 `palette.warnText`.
- 해제 시트: 제목 `{라벨} 연동을 해제할까요?`, 본문 `총자산에서 빠지고, 지난 기록은 자산 변화에 남아요. 다시 연동하려면 앱키를 다시 넣어야 해요`, 확인 `해제`. `busy={unlink.isPending}`. `403`이면 시트를 닫는다. 그 밖의 실패(503 · 네트워크 · 그 밖)는 시트를 두고 `messageOf(error)`를 `error`로 넘긴다. 성공하면 닫는다. 시트를 열 때와 닫을 때 `unlink.reset()`을 불러, 앞 계좌의 오류가 다음 시트에 남지 않게 한다.
- 로딩은 `Skeleton` 행, 오류는 `ErrorState`(재시도 = `refetch`), 빈 목록은 `연동된 계좌가 없어요`. 목록 아래 `Button` `＋ 계좌 추가` → `navigation.navigate('account-link/new')`. 화면이 스택 헤더 아래라 위쪽 안전 여백을 잡지 않는다.

- [ ] **Step 1: 테스트 도우미를 넓힌다** — `renderWithStack`이 만든 `queryClient`를 돌려주게 한다(기존 호출부는 그대로 통과).
- [ ] **Step 2: 실패하는 테스트를 쓴다** — `renderWithStack('account-link', AccountLinkScreen, undefined, { others: ['account-link/new'], onNavigate })`, `serveRoutes`. 해제 테스트는 `jest.spyOn(queryClient, 'invalidateQueries')`를 건다.
  ```ts
  it('계좌마다 라벨 · 상품 · 상태 줄을 보인다', async () => {
    // GET /accounts → accountLinksFixture
    expect(await screen.findByText('위탁 · 연동됨')).toBeTruthy();
    expect(screen.getByText('위탁 · 연동됨 · 10-16 수집 실패')).toBeTruthy();
    expect(screen.getByText('연금저축 · 연동 중 · 다음 정기 수집 뒤 잔고가 반영돼요')).toBeTruthy();
    expect(screen.getByText('연금저축 · 첫 수집에 실패했어요. 앱키·계좌번호를 확인하고 해제한 뒤 다시 등록해 주세요')).toBeTruthy();
  });
  it('빈 목록이면 안내와 추가 버튼', /* emptyAccountLinks → '연동된 계좌가 없어요' · '＋ 계좌 추가' */);
  it('조회가 실패하면 다시 시도할 수 있다', /* 첫 응답 500 → 재시도 누르면 GET 두 번 · 목록 */);
  it('＋ 계좌 추가는 등록 폼을 연다', /* onNavigate('account-link/new') */);
  it('해제를 확인하면 DELETE 뒤 목록을 다시 받는다', async () => {
    // GET /accounts, DELETE /^\/accounts\/.+$/ 204
    await fireEvent.press(await screen.findByRole('button', { name: '한국투자 위탁 해제' }));
    expect(screen.getByText('한국투자 위탁 연동을 해제할까요?')).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: '해제' }));
    await waitFor(() => expect(calls.filter((c) => c.method === 'GET' && c.path === '/accounts')).toHaveLength(2));
    expect(calls.find((c) => c.method === 'DELETE')?.path).toBe('/accounts/30000000-0000-0000-0000-000000000001');
    expect(screen.queryByText('한국투자 위탁 연동을 해제할까요?')).toBeNull();
    expect(spy.mock.calls.map(([f]) => f?.queryKey)).toEqual(expect.arrayContaining([['account-links'], ['accounts'], ['catalog']]));
  });
  it('해제 중에 두 번 눌러도 DELETE는 한 번', /* DELETE wait 경로 · 확인 두 번 · DELETE 1건 */);
  it('저장소 장애(503)면 시트에 서버 문구가 남는다', /* DELETE 503 { error: { code: 'CREDENTIAL_STORE_UNAVAILABLE', message: '계좌 자격증명 저장소에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요' } } → 시트 제목과 문구가 둘 다 보인다 */);
  it('서버에 닿지 못하면 시트에 연결 실패 문구', /* DELETE fetch reject → '연결에 실패했어요. 잠시 후 다시 시도해 주세요' */);
  it('실패 뒤 취소하고 다른 계좌를 열면 앞 오류가 없다', /* 503 → 취소 → '한국투자 위탁 2 해제' → 503 문구 없음 */);
  it('남의 계좌 · 이미 없는 계좌(403)면 시트를 닫고 목록을 다시 받는다', /* DELETE 403 FORBIDDEN_ACCOUNT → 시트 없음 · GET 두 번 · ['account-links'] 무효화 */);
  it('취소하면 요청하지 않는다', /* 취소 → DELETE 없음 */);
  ```
  누르는 이름은 `ConfirmSheet`의 확인 버튼 라벨 `해제`와 행 버튼 `{라벨} 해제`가 갈리게 한다.
- [ ] **Step 3:** `npx jest __tests__/accountLink.test.tsx` — FAIL.
- [ ] **Step 4: 구현한다** — 위 Interfaces · 문구대로. `RootStack` 머리 주석에 "계좌 연동은 계좌별 화면의 `계좌 연동 관리`에서 쌓인다"를 더한다.
- [ ] **Step 5:** `npx jest && npx tsc --noEmit` — PASS.
- [ ] **Step 6: 커밋** — `feat: 연동 계좌 목록과 해제 화면을 만든다`

---

## Task 5: 등록 폼 화면

**Files:**
- Create: `screens/accountLink/AccountLinkFormScreen.tsx`
- Modify: `app/navigation/RootStack.tsx`
- Test: `__tests__/accountLinkFormScreen.test.tsx`

**Interfaces:**
- Consumes: `linkAccount` · `invalidateAccountLinkData` (Task 1), `LinkForm` 함수들 (Task 2), `TextField.revealLabels` (Task 3), `renderWithStack().queryClient` (Task 4), `ApiError` · `messageOf`
- Produces:
  ```ts
  export function AccountLinkFormScreen()
  // RootStack: <Stack.Screen name="account-link/new" component={AccountLinkFormScreen} options={{ title: '한국투자증권 연동' }} />
  ```
- 바탕은 `KeyboardScreen`(`screens/alertEditor/KeyboardScreen.tsx`) 안의 `ScrollView`(`keyboardShouldPersistTaps="handled"`)다. 칸 넷과 버튼이 키보드에 가리지 않게 한다.
- 칸 순서와 라벨: `앱키` · `앱 시크릿`(secure, `revealLabels={{ show: '시크릿 보기', hide: '시크릿 가리기' }}`) · `계좌번호`(`keyboardType="number-pad"`, `value={displayAccountNumber(digits)}`, `onChangeText` → `withAccountInput`) · `라벨`(`onChangeText` → `withLabel`). 칸 아래 안내 `위탁(01)·연금저축(22) 계좌만 연동할 수 있어요`, 버튼 `연동하기`.
- 네 칸 공통: `autoCorrect={false}` `autoCapitalize="none"` `spellCheck={false}` `autoComplete="off"` `textContentType="none"` `importantForAutofill="no"`.
- 경고: `baseUrl()`이 `https://`로 시작하지 않으면 폼 위에 `암호화되지 않은 연결이에요. 같은 네트워크나 port-forward에서만 실제 키를 넣으세요`(`warnBg` · `warnText`).
- 제출: `validateLinkForm` 오류가 있으면 칸 오류만 보인다. 없으면 `useRef` 잠금과 `submitting` 상태(`Button loading`)를 켜고 `linkAccount(toLinkRequest(form))`. 잠금은 상태가 다음 렌더에야 바뀌어 연달아 누른 두 번째를 막지 못하기 때문이다(`CashflowForm`과 같다).
  - 성공: `invalidateAccountLinkData(queryClient)` 뒤, 화면이 아직 떠 있으면 `navigation.goBack()`.
  - 실패: 떠 있으면 `appSecret`을 `''`로 둔다. `ApiError`이고 `code === 'UNSUPPORTED_ACCOUNT_PRODUCT'`면 계좌번호 칸 오류, 그 밖은 폼 위 한 줄 `messageOf(error)`.
  - 떠났는지는 언마운트 때 내리는 `useRef` 플래그로 안다. 떠난 뒤 `goBack()`을 부르면 실앱에서 그 아래 `account-link`까지 걷힌다.
- 202 뒤 목록에 새 계좌가 `연동 중`으로 보이는 것은 이 태스크에서 `goBack`과 `['account-links']` 무효화로 확인한다. 목록이 무효화되면 다시 받는다는 것은 Task 4가 본다.
- 칸을 고치면 그 칸의 오류와 폼 위 오류를 지운다.

- [ ] **Step 1: 실패하는 테스트를 쓴다** — `renderWithStack('account-link/new', AccountLinkFormScreen, undefined, { onNavigate })`. 도우미 `fill({ appKey, appSecret, account, label? })`가 칸 라벨로 `fireEvent.changeText` 한다.
  ```ts
  it('비워 두고 누르면 네 칸 문구가 뜨고 요청하지 않는다', /* validateLinkForm 문구 넷 · POST 없음 */);
  it('계좌번호에 섞인 공백 · 하이픈을 지우고 하이픈을 그어 보인다', async () => {
    await fireEvent.changeText(screen.getByLabelText('계좌번호'), '0000 0000-01');
    expect(screen.getByLabelText('계좌번호').props.value).toBe('00000000-01');
    expect(screen.getByLabelText('라벨').props.value).toBe('한국투자 위탁');
  });
  it('고친 라벨은 계좌번호가 바뀌어도 그대로다', /* 라벨 '생활비' → 계좌번호 0000000022 → '생활비' */);
  it('공백을 지운 값을 보내고, 202면 목록으로 돌아가며 조회를 무효화한다', async () => {
    // POST /accounts 202, spy = jest.spyOn(queryClient, 'invalidateQueries')
    await fill({ appKey: ' test-app-key\n', appSecret: 'test-app-secret\n', account: '00000000-01', label: ' 생활비 ' });
    await fireEvent.press(screen.getByRole('button', { name: '연동하기' }));
    await waitFor(() => expect(onNavigate).toHaveBeenLastCalledWith('__home', undefined));
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      app_key: 'test-app-key', app_secret: 'test-app-secret', account_number: '0000000001', label: '생활비' });
    expect(spy).toHaveBeenCalledWith({ queryKey: ['account-links'] });
  });
  it('지원하지 않는 상품이면 계좌번호 칸 아래에 서버 문구, 시크릿만 비운다', async () => {
    // fill({ appKey: 'test-app-key', appSecret: 'test-app-secret', account: '00000000-29', label: '생활비' }) — 29는 기본 라벨이 없어 라벨을 직접 넣는다
    // POST 400 { code: 'UNSUPPORTED_ACCOUNT_PRODUCT', message: '지원하지 않는 계좌 상품입니다. 위탁(01)과 연금저축(22)만 등록할 수 있습니다' }
    expect(await screen.findByText('지원하지 않는 계좌 상품입니다. 위탁(01)과 연금저축(22)만 등록할 수 있습니다')).toBeTruthy();
    expect(screen.getByLabelText('앱 시크릿').props.value).toBe('');
    expect(screen.getByLabelText('앱키').props.value).toBe('test-app-key');
    expect(screen.getByLabelText('계좌번호').props.value).toBe('00000000-29');
  });
  it.each([
    [409, 'ACCOUNT_ALREADY_LINKED', '이미 연동된 계좌입니다'],
    [409, 'ACCOUNT_UNAVAILABLE', '이 계좌는 등록할 수 없습니다'],
    [503, 'CREDENTIAL_STORE_UNAVAILABLE', '계좌 자격증명 저장소에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요'],
  ])('%s %s는 폼 위에 서버 문구', /* 문구 보임 · 시크릿 '' · 화면 그대로 */);
  it('봉투 없는 500이면 요청을 처리하지 못했어요', /* body { message: 'x' } status 500 — serveRoutes는 본문을 JSON으로 싣는다 */);
  it('서버에 닿지 못하면 연결 실패 문구', /* fetch reject → '연결에 실패했어요. 잠시 후 다시 시도해 주세요' */);
  it('응답을 기다리는 동안 두 번 눌러도 한 번만 보낸다', /* wait 경로 · 두 번 press · POST 1건 */);
  it('응답 전에 떠나면 다시 뒤로 가지 않고 무효화는 한다', async () => {
    // wait 경로로 응답을 붙잡고 → 제출 → act(() => navigation.goBack()) → 풀기
    // spy가 ['account-links']로 불림 · navigation.getRootState().routes 이름이 ['__home'] · console.error가 불리지 않음
  });
  it('http 주소면 경고를 띄우고 https면 띄우지 않는다', /* process.env.EXPO_PUBLIC_API_BASE_URL를 바꿨다 되돌린다 */);
  it('시크릿 칸은 가려져 있다', /* getByLabelText('앱 시크릿').props.secureTextEntry === true · '시크릿 보기' 버튼 */);
  it('네 칸 모두 자동 수정 · 자동 완성을 끈다', /* 칸마다 props: autoCorrect false · autoCapitalize 'none' · spellCheck false · autoComplete 'off' · textContentType 'none' · importantForAutofill 'no' */);
  describe('자격증명이 남지 않는다', () => {
    const SECRETS = ['test-app-key', 'test-app-secret', '0000000001', '00000000-01'];
    // 각 경우: console.log/info/warn/error/debug spy
    it.each(['성공', '실패(409)'])('%s 뒤', async () => {
      const dump = JSON.stringify({
        queries: queryClient.getQueryCache().getAll().map((q) => ({ key: q.queryKey, data: q.state.data })),
        mutations: queryClient.getMutationCache().getAll().map((m) => m.state),
        navigation: navigation.getRootState(),
      });
      for (const secret of SECRETS) expect(dump).not.toContain(secret);
      for (const spy of consoleSpies) for (const call of spy.mock.calls)
        for (const secret of SECRETS) expect(JSON.stringify(call)).not.toContain(secret);
    });
    it('성공 뒤 화면에 값이 남지 않는다', /* queryByDisplayValue('test-app-key') · ('test-app-secret') 둘 다 null */);
  });
  ```
- [ ] **Step 2:** `npx jest __tests__/accountLinkFormScreen.test.tsx` — FAIL.
- [ ] **Step 3: 구현한다.** 머리 주석에 왜 `useMutation`을 쓰지 않는지(mutation 캐시가 요청 인자를 보관한다)와, 입력값이 이 컴포넌트 상태에만 산다는 것을 적는다.
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` — PASS. `grep -rn "console\." src/screens/accountLink src/api/queries/useAccountLinks.ts src/api/queries/useUnlinkAccount.ts src/api/queries/accountLinkInvalidation.ts` — 아무것도 나오지 않는다.
- [ ] **Step 5: 커밋** — `feat: 한국투자증권 계좌 등록 폼을 만든다`

---

## Task 6: 계좌 탭 — 진입 버튼 · 빈 상태 문구 · 점

**Files:**
- Modify: `screens/accounts/AccountsScreen.tsx`, `envelope/EmptyState.tsx`, `envelope/ScreenFrame.tsx`(주석), `app/navigation/Tabs.tsx`
- Create: `screens/accounts/tabDot.ts`
- Test: `__tests__/accounts.test.tsx`, `__tests__/envelope.test.tsx`, `__tests__/summary.test.tsx`(문구), `__tests__/accountTabDot.test.tsx`(생성)

**Interfaces:**
- Consumes: `account-link` 라우트 (Task 4)
- Produces:
  ```ts
  // tabDot.ts
  export function accountTabNeedsLook(envelope: AccountsResponse | null): boolean
  // notices에 STALE_ACCOUNTS 또는 REAUTH_REQUIRED가 있으면 참. notices만 읽는다
  ```
- `AccountsScreen`: `useNavigation<NavigationProp<TabParamList & RootStackParamList>>()`(요약 화면과 같다). 목록 `ScrollView`의 맨 아래(계좌 묶음 다음)와 `ScreenFrame`의 `emptyAction`에 `Button` `계좌 연동 관리` → `navigate('account-link')`. 머리 주석의 "`+ 계좌 연동` 버튼을 두지 않는다" 문단은 이 버튼의 사실로 바꾸고, 지금 동기화가 이 버튼 옆에 들어온다는 것(스펙 §2.3)을 적는다.
- `EmptyState`: `SUBTEXT.NO_ACCOUNTS` = `계좌 탭의 계좌 연동 관리에서 연동할 수 있어요`. 화면별 보조 문구 표 `SUBTEXT_BY_SCREEN: Partial<Record<ScreenKey, Partial<Record<EmptyReason, string | null>>>>`를 더해 `accounts: { NO_ACCOUNTS: null }`로 둔다. 표에 키가 있으면(`reason in table`) 그 값을 쓰고 `null`은 문구 없음이다 — `??`로 고르면 `null`이 기본 문구로 되돌아간다. 표 위 주석 "계좌 연동 화면이 아직 없어…"를 사실대로 고친다.
- `EmptyState`의 `action` · `ScreenFrame`의 `emptyAction` 주석("사용자가 스스로 되돌릴 수 있을 때만 — 필터 초기화")을 계좌 연동 진입도 담는 문장으로 고친다.
- `Tabs`: `useAccounts()`의 `envelope`로 `accountTabNeedsLook`이 참이면 계좌 탭에 `tabBarBadge: ''`, `tabBarBadgeStyle: { width: 8, height: 8, minWidth: 8, borderRadius: 4, paddingHorizontal: 0, lineHeight: 8, backgroundColor: palette.badge }`(배지가 스스로 넣는 `minWidth` · `paddingHorizontal` · `lineHeight`를 덮는다), `tabBarAccessibilityLabel: '계좌, 확인할 계좌 있음'`. 거짓이면 셋 다 `undefined`. 머리 주석의 "계좌 탭에는 아직 점을 찍지 않는다"를 조건의 사실로 바꾼다. 빈 문자열 배지가 점으로 그려지는지는 테스트 렌더러로 알 수 없어 실행 후 확인(아래)에서 본다. 주석에도 단정하지 않는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**
  - `accounts.test.tsx`
    ```ts
    it('총자산 아래 계좌 연동 관리가 연동 화면을 연다', /* onNavigate('account-link') — renderWithNavigation others에 'account-link' */);
    it('계좌가 없어도 계좌 연동 관리가 있고 보조 문구는 없다', /* empty_reason NO_ACCOUNTS 응답 → 버튼 있음 · '계좌 탭의 계좌 연동 관리에서 연동할 수 있어요' 없음 */);
    it('첫 수집 전(NO_HOLDINGS)에도 계좌 연동 관리가 있다');
    ```
  - `envelope.test.tsx:236` · `summary.test.tsx:161`의 `계좌 연동은 준비 중입니다`를 `계좌 탭의 계좌 연동 관리에서 연동할 수 있어요`로 바꾼다.
  - `accountTabDot.test.tsx`
    ```ts
    expect(accountTabNeedsLook(goldenAccounts)).toBe(true);                // STALE_ACCOUNTS 있음
    expect(accountTabNeedsLook({ ...goldenAccounts, notices: goldenAccounts.notices.filter((n) => n.code !== 'STALE_ACCOUNTS') })).toBe(false);
    expect(accountTabNeedsLook({ ...goldenAccounts, notices: [{ code: 'REAUTH_REQUIRED', severity: 'warn', message: '', params: {} }] })).toBe(true);
    expect(accountTabNeedsLook(null)).toBe(false);
    it('탭 바가 점을 달면 계좌 탭 접근성 이름이 바뀐다', /* Tabs를 렌더(serveRoutes: views/accounts → goldenAccounts, 그 밖 요약 · 알림 경로) → await findByLabelText('계좌, 확인할 계좌 있음') */);
    it('낡은 계좌가 없으면 점이 없다', /* STALE 뺀 응답 → 계좌별 조회가 끝난 뒤 queryByLabelText('계좌, 확인할 계좌 있음') null */);
    ```
- [ ] **Step 2:** 바꾼 테스트들을 돌려 FAIL을 본다.
- [ ] **Step 3: 구현한다.**
- [ ] **Step 4: 탭을 그리는 기존 테스트를 확인한다** — `npx jest`. 탭 바가 `/portfolio/views/accounts`를 부르게 되어 `navigation` · `push` · `alertsTab` · `assetChange` · `allocation` · `realizedPnl` · `cashflowFlow` · `accounts` 테스트에 요청이 하나 는다. 직접 짠 fetch 대역이 모르는 URL에 요약 응답을 주는 테스트(`navigation` · `assetChange` · `realizedPnl` · `allocation`)에서는 그 응답의 `STALE_ACCOUNTS`로 점이 켜지지만 해는 없다. 요청 수나 순서를 검사하다 깨진 테스트만, 그 테스트의 대역에 `/portfolio/views/accounts` → `goldenAccounts` 경로를 더해 고친다. 검사 대상 경로의 요청 수를 세는 단언(`/alerts` · `/portfolio/views/asset-change` 등)은 그대로 둔다.
- [ ] **Step 5:** `npx jest && npx tsc --noEmit` — PASS.
- [ ] **Step 6: 커밋** — `feat: 계좌 탭에 계좌 연동 관리와 확인할 계좌 점을 단다`

---

## 실행 후 확인 (각각 사용자 승인 필요)

1. **로컬 백엔드 기동:** `back-end` main을 `local` 프로파일, `portfolio.credentials.store=memory`로 띄운다. 띄우는 명령은 그때 `back-end/README` · 설정을 보고 정해 승인받는다.
2. **앱 기동:** Expo 웹 또는 시뮬레이터. `.env`의 `EXPO_PUBLIC_API_BASE_URL`이 로컬 백엔드를 가리키는지 확인한다(평문 HTTP라 폼 경고가 보여야 한다).
3. **시나리오:** 가짜 값(`test-app-key` · `test-app-secret` · `00000000-01` · 라벨 `생활비`)으로 등록 → 목록에 `연동 중`, 같은 번호로 다시 등록 → `이미 연동된 계좌입니다`, `00000000-29` → 계좌번호 칸 아래 서버 문구, 해제 → 목록에서 빠짐.
4. **점:** 이월 계좌가 있는 사용자로 탭 바의 점이 숫자 없이 작게 그려지는지 눈으로 본다. 그려지지 않으면 멈추고 보고한다.
5. 운영 서버에 등록 요청을 보내지 않는다. 스크린샷을 남기면 가짜 값만 보이는지 확인한다.
