# 수동 동기화 화면 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 계좌 탭에 `지금 동기화`(전 계좌)와 동기화 카드를 두어, 요청 직후의 다음 수집 예정과 수집 뒤의 결과(완료 · 부분 실패 · 전체 실패)를 보인다.

**Architecture:** 카드에 보일 실행 id는 계좌별 뷰의 `SYNC_IN_PROGRESS` notice가 주고, 없으면 `kvStore`에 남긴 마지막 실행 id다. `GET /sync/{run_id}`를 `useSyncRun`이 부르고, 탭 포커스 · 앱 복귀 · 새로고침 때와 `RUNNING`인 동안 60초마다 다시 묻는다. 앱이 켜진 동안 한 실행이 닫힌 것을 처음 보면 `invalidateAccountLinkData`로 포트폴리오 조회 전체를 한 번 다시 받는다. 실행 상태 판정은 `api/syncRun.ts`, 문구 규칙은 `screens/accounts/syncCopy.ts`에 순수 함수로 모은다.

**Tech Stack:** React Native 0.81 · Expo SDK 54 · TanStack Query 5 · React Navigation 7 · jest-expo · Testing Library(RNTL 14)

**Spec:** [`docs/yhr/specs/portfolio-management/2026-10-18-account-link-screen-design.md`](../specs/portfolio-management/2026-10-18-account-link-screen-design.md) (이하 "설계") §1 · §2.2 · §3.5 · §6 · §7 · §8의 5 ~ 8. 서버 계약은 [`2026-10-17-manual-sync-design.md`](../specs/portfolio-management/2026-10-17-manual-sync-design.md)(이하 "동기화 설계") §2.1 · §4, 상위 스펙은 [`2026-07-28-portfolio-management-spec.md`](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) §2.3 · §7.6 · §10.

**작업 위치:** `/Users/yhr/Dev/workspace/personal/stock-project/front-end`, 브랜치 `feat/manual-sync-screen`(`origin/main`에서 딴다). 경로는 `front-end/src/` 기준이다. 백엔드는 바꾸지 않는다 — 웹 출처 허용(`WebOriginCorsConfig`)에 `/sync` · `/sync/*`가 이미 있다.

## Global Constraints

- 스펙 · 설계를 고치지 않는다. 막히거나 설계가 틀렸다고 보면 멈추고 보고한다. 백엔드 응답이 동기화 설계 §4와 어긋나 보여도 보고한다.
- 패키지를 설치하지 않는다. Expo SDK를 올리지 않는다(Expo Go 상한 54).
- 개발 서버 · 시뮬레이터 · 백엔드 기동, 운영 서버로의 동기화 요청은 사용자 승인 후에 한다.
- 테스트 먼저. 실패를 눈으로 확인한 뒤 구현한다. 태스크 끝마다 `npx jest`와 `npx tsc --noEmit`이 통과한다.
- 커밋은 사용자가 요청할 때만 한다. 각 태스크의 커밋 단계는 "요청받았을 때 이 메시지로"라는 뜻이다. 메시지는 한국어, 접두 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝에 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- 주석은 히스토리 없이 최신 사실만. 검증하지 않은 것을 단정하지 않는다. 밀도와 어조는 `screens/accounts` · `screens/accountLink`를 따른다.
- 픽스처의 id · 라벨은 가짜 값만 쓴다. 실제 계좌번호 · 앱키를 어디에도 넣지 않는다.
- 서버 오류 문구는 `ApiError.message`를 그대로 쓰고, 네트워크 오류는 `NetworkError`의 문구를 쓴다.
- 문구는 설계 §3.5 표 그대로 쓴다. 이 계획이 옮긴 문구도 설계와 다르면 설계가 맞다.
- `kvStore` 키는 `sync.last_run_id` 하나다. 읽기 · 쓰기 실패는 삼킨다(`usePushBanners`와 같다).
- 층 방향: `api/`는 `screens/`를 import하지 않는다.
- 테스트에서 만드는 `QueryClient`는 `retry: false`를 준다(`renderWithStack`은 이미 준다).
- `docs/hhj/` · `docs/jdh/` · `docs/team-architecture-agreement.md`를 근거로 쓰지 않는다.

## Review Focus

1. **앱을 새로 켰는데 실행은 이미 닫혔다** — notice가 없고 저장한 id만 있다. 카드가 결과로 보이고, 그 실행으로 한 번 무효화한다(설계 §6.3). → Task 4 `앱을 다시 켜도 닫힌 결과가 보인다`.
2. **다른 사용자로 다시 로그인했다** — 저장한 id의 조회가 `403 FORBIDDEN_SYNC_RUN`. 카드 없이 id가 지워지고 오류 문구가 보이면 안 된다. → Task 4.
3. **실행이 닫히는 순간을 화면이 본다** — 무효화가 정확히 한 번 일어나고, 무효화로 다시 받은 뷰에 notice가 없어도 카드가 남아야 한다(notice id를 상태에 먼저 반영해 둔다). 저장소 쓰기가 실패해도 같다. → Task 4.
4. **카드가 없다** — 새로고침 · 탭 복귀 · 앱 복귀가 `/sync/…`를 부르지 않는다. TanStack 5의 `refetch()`는 `enabled: false`를 무시하므로 훅이 막는다. 저장소 읽기가 `undefined`로 풀려도 같다(secure-store 대역이 없는 기존 테스트). → Task 3 · Task 4 Step 4.
5. **계좌 탭을 떠나 있거나 앱이 뒤에 있다** — 60초 조회가 멈춘다. 탭은 마운트된 채 남으므로 `useIsFocused`가 거짓일 때 주기를 끈다. → Task 5.

---

## 파일 구조

| 파일 | 책임 | 태스크 |
|---|---|---|
| `api/types.ts` | `SyncAccepted` · `SyncRunAccount` · `SyncRun` | 1 |
| `api/endpoints.ts` | `requestSync` · `fetchSyncRun` | 1 |
| `api/queries/keys.ts` | `syncRun(runId)` | 1 |
| `api/syncRun.ts` | `isRunOpen` (생성) | 1 |
| `fixtures/syncRun.ts` | `GET /sync/{run_id}` 손 픽스처 · 동기화 notice (생성) | 1 |
| `envelope/notices.ts` | 두 코드를 `accounts` · `SCREEN_PLACED`에 | 2 |
| `screens/accounts/syncCopy.ts` | 제목 · 둘째 줄 · 계좌 줄 문구, notice에서 실행 id 읽기 (생성) | 2 |
| `screens/accounts/lastSyncRun.ts` | `kvStore`의 마지막 실행 id (생성) | 3 |
| `api/queries/useSyncRun.ts` | 실행 조회 · 주기 · 닫힌 실행 무효화 (생성) | 3 |
| `screens/accounts/useSyncCard.ts` | 보일 실행 고르기 · 저장 · `403` · `닫기` · 요청 · 포커스 · 앱 상태 (생성) | 4 · 5 |
| `screens/accounts/SyncCard.tsx` | 카드 그리기 (생성) | 4 |
| `screens/accounts/AccountsScreen.tsx` | 카드 · `지금 동기화` 배치, 새로고침 | 4 |

---

## Task 0: 브랜치

- [ ] **Step 1:** `git -C front-end fetch origin && git -C front-end switch -c feat/manual-sync-screen origin/main`
- [ ] **Step 2:** `cd front-end && npx jest && npx tsc --noEmit` — 시작점이 통과하는지 본다. 실패하면 멈추고 보고한다.

---

## Task 1: API 층 — 타입 · 요청 · 키 · 실행 판정 · 픽스처

**Files:**
- Modify: `api/types.ts`, `api/endpoints.ts`, `api/queries/keys.ts`
- Create: `api/syncRun.ts`, `fixtures/syncRun.ts`
- Test: `__tests__/syncApi.test.ts` (생성)

**Interfaces:**
- Produces:
  ```ts
  // types.ts — 설계 §6.1 그대로. state · failure_reason은 string
  export type SyncAccepted = { run_id: string; message: string };
  export type SyncRunAccount = { account_id: string; label: string; state: string; as_of: string | null; failure_reason: string | null };
  export type SyncRun = { run_id: string; state: string; started_at: string; finished_at: string | null; failure_reason: string | null; accounts: SyncRunAccount[] };
  // endpoints.ts
  export function requestSync(): Promise<SyncAccepted>            // apiPost('/sync', {}) — 전 계좌
  export function fetchSyncRun(runId: string): Promise<SyncRun>   // apiGet(`/sync/${encodeURIComponent(runId)}`)
  // keys.ts
  syncRun: (runId: string) => ['sync-run', runId] as const
  // api/syncRun.ts — 설계 §3.5 · §6.2: RUNNING만 열림. 모르는 값은 닫힘으로 본다(제목만 syncCopy가 RUNNING처럼 고른다)
  export function isRunOpen(run: SyncRun): boolean                // run.state === 'RUNNING'
  // fixtures/syncRun.ts — 모두 SyncRun 타입으로 선언해 tsc가 모양을 본다
  export const SYNC_RUN_ID: string                // '90000000-0000-0000-0000-000000000001' 꼴 가짜 uuid
  export const OTHER_RUN_ID: string               // '90000000-0000-0000-0000-000000000002'
  export const runningRun: SyncRun                // 실행 RUNNING, 계좌 RUNNING 2개
  export const doneRun: SyncRun                   // DONE, finished_at '2026-10-29T23:41:00+09:00', 계좌 DONE as_of '2026-10-29' 하나 · DONE as_of null 하나
  export const partialRun: SyncRun                // PARTIAL, 계좌 DONE 하나 · FAILED(SOURCE_TIMEOUT) 하나 · REAUTH_REQUIRED 하나
  export const timedOutRun: SyncRun               // FAILED, failure_reason PICKUP_TIMEOUT, 계좌 FAILED · PICKUP_TIMEOUT
  export function syncNotices(runId: string, opts?: { alreadyFinal?: boolean }): Notice[]
  // SYNC_IN_PROGRESS: severity info, message '동기화 요청을 받았습니다 · 다음 수집 10-29(목) 23:00',
  //   params { sync_run_id: runId, next_pickup_at: '2026-10-29T23:00:00+09:00' }
  // ALREADY_FINAL(옵션): severity info, message '10-26 값은 이미 확정되어 다시 수집해도 바뀌지 않습니다',
  //   params { as_of: '2026-10-26', finalized_at: '2026-10-27T08:00:00+09:00' }
  ```
  모양은 백엔드 `sync/dto/SyncRunResponse` · `SyncAccountDto` · `SyncAcceptedResponse`(origin/main)와 대 본다. 응답 필드는 snake_case, 시각은 `+09:00` 오프셋 문자열, `as_of`는 `YYYY-MM-DD`다.

- [ ] **Step 1: 실패하는 테스트를 쓴다** — `syncApi.test.ts`, `serveRoutes`로:
  ```ts
  it('지금 동기화는 본문 {}로 POST /sync다', /* status 202 body { run_id, message } → 결과의 run_id · calls[0] { method: 'POST', path: '/sync', body: {} } */);
  it('실행 조회는 GET /sync/{run_id}다', /* body runningRun → state 'RUNNING' · calls[0].path `/sync/${SYNC_RUN_ID}` */);
  it('실행 키는 실행마다 다르다', () => expect(keys.syncRun('a')).toEqual(['sync-run', 'a']));
  it('RUNNING만 열린 실행이다', /* isRunOpen(runningRun) true · doneRun · partialRun · timedOutRun false · { ...runningRun, state: 'QUEUED' } false */);
  ```
- [ ] **Step 2:** `npx jest src/__tests__/syncApi.test.ts` — FAIL(없는 export).
- [ ] **Step 3: 구현한다.**
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` — PASS.
- [ ] **Step 5: 커밋** — `feat: 수동 동기화 요청 · 실행 조회 타입과 요청을 더한다`

---

## Task 2: notice 자리와 문구 규칙

**Files:**
- Modify: `envelope/notices.ts`
- Create: `screens/accounts/syncCopy.ts`
- Test: `__tests__/notices.test.ts`, `__tests__/syncCopy.test.ts` (생성)

**Interfaces:**
- Consumes: `SyncRun` · `SyncRunAccount` · `isRunOpen` · 픽스처 (Task 1)
- Produces:
  ```ts
  // notices.ts — BY_SCREEN.accounts에 'SYNC_IN_PROGRESS', 'ALREADY_FINAL'을 더하고 둘 다 SCREEN_PLACED에 둔다.
  // SCREEN_PLACED 위 주석에 "동기화 두 안내는 계좌 탭의 동기화 카드가 그린다"는 이유를 한 줄 더한다.

  // syncCopy.ts
  export type Tone = 'muted' | 'warn';
  export const SYNC_REQUESTED = '동기화 요청을 받았어요';
  export function noticeRunId(notices: Notice[]): string | null           // SYNC_IN_PROGRESS의 params.sync_run_id가 빈 문자열이 아닌 문자열일 때만
  export function syncHeadline(run: SyncRun | null, notices: Notice[]): { title: string; tone: Tone; sub: string | null }
  export function syncAccountLine(account: SyncRunAccount): { text: string; tone: Tone }
  ```
  - 문구 · 색은 설계 §3.5의 두 표다. `run`이 null(첫 조회 중)이거나 `state`가 `RUNNING` · 모르는 값이면 열린 실행의 제목을 고른다. 모르는 값이면 둘째 줄은 null이다(설계 표 "모르는 값 | `RUNNING`과 같다 | —").
  - 시각 · 날짜는 글자 그대로 자른다. `finished_at` → `MM-DD HH:mm`, `as_of` → `MM-DD`(`format/date.ts`의 `formatMonthDay`와 같은 방식. 새 함수가 필요하면 `format/date.ts`에 둔다).
  - `RUNNING` 실행의 `ALREADY_FINAL` 둘째 줄은 notice `message` 그대로다. 닫힌 실행에서는 보지 않는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**
  - `notices.test.ts`
    ```ts
    it('동기화 두 안내는 계좌별만 받고 캡션 · 줄로 쌓지 않는다', /* SCREENS 전부: isVisibleOn(s, code)는 s === 'accounts'일 때만 참 · captionNotices('accounts', [두 안내]) 빈 배열 · bannerNotices 빈 배열 */);
    ```
  - `syncCopy.test.ts` — 설계 §3.5 두 표의 행마다 하나씩:
    ```ts
    expect(syncHeadline(runningRun, syncNotices(SYNC_RUN_ID))).toEqual({ title: '동기화 요청을 받았습니다 · 다음 수집 10-29(목) 23:00', tone: 'muted', sub: null });
    expect(syncHeadline(runningRun, syncNotices(SYNC_RUN_ID, { alreadyFinal: true })).sub).toBe('10-26 값은 이미 확정되어 다시 수집해도 바뀌지 않습니다');
    expect(syncHeadline(runningRun, []).title).toBe('동기화 요청을 받았어요');
    expect(syncHeadline(null, []).title).toBe('동기화 요청을 받았어요');
    expect(syncHeadline(doneRun, syncNotices(SYNC_RUN_ID, { alreadyFinal: true }))).toEqual({ title: '동기화 완료 · 10-29 23:41', tone: 'muted', sub: null });
    expect(syncHeadline(partialRun, [])).toEqual({ title: '일부 계좌를 동기화하지 못했어요', tone: 'warn', sub: '실패한 계좌는 이전 값으로 총자산에 들어가요' });
    expect(syncHeadline(timedOutRun, [])).toEqual({ title: '동기화하지 못했어요', tone: 'warn', sub: '요청 뒤 4일 안에 수집되지 않았어요' });
    expect(syncHeadline({ ...timedOutRun, failure_reason: null }, []).sub).toBeNull();
    expect(syncHeadline({ ...runningRun, state: 'QUEUED' }, syncNotices(SYNC_RUN_ID, { alreadyFinal: true }))).toEqual({ title: '동기화 요청을 받았습니다 · 다음 수집 10-29(목) 23:00', tone: 'muted', sub: null });
    // 계좌 줄 — 픽스처의 계좌를 쓴다
    expect(syncAccountLine(runningRun.accounts[0])).toEqual({ text: '수집 대기', tone: 'muted' });
    expect(syncAccountLine(doneRun.accounts[0]).text).toBe('완료 · 10-29 기준');
    expect(syncAccountLine(doneRun.accounts[1]).text).toBe('완료');                  // as_of null
    expect(syncAccountLine(timedOutRun.accounts[0])).toEqual({ text: '수집되지 않았어요', tone: 'warn' });
    expect(syncAccountLine(partialRun.accounts[1])).toEqual({ text: '수집 실패', tone: 'warn' });
    expect(syncAccountLine(partialRun.accounts[2])).toEqual({ text: '재인증 필요', tone: 'warn' });
    expect(syncAccountLine({ ...runningRun.accounts[0], state: 'WHATEVER' })).toEqual({ text: '수집 대기', tone: 'muted' });
    expect(noticeRunId(syncNotices('r-1'))).toBe('r-1');
    expect(noticeRunId([{ code: 'SYNC_IN_PROGRESS', severity: 'info', message: '', params: { sync_run_id: 1 } }])).toBeNull();
    expect(noticeRunId([])).toBeNull();
    ```
- [ ] **Step 2:** 두 파일을 돌려 FAIL을 본다.
- [ ] **Step 3: 구현한다.**
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` — PASS. 기존 `notices.test.ts`는 코드별 자리만 보므로 깨지지 않는 것이 정상이다.
- [ ] **Step 5: 커밋** — `feat: 동기화 안내를 계좌별 화면에만 두고 동기화 카드 문구를 정한다`

---

## Task 3: 마지막 실행 id와 실행 조회 훅

**Files:**
- Create: `screens/accounts/lastSyncRun.ts`, `api/queries/useSyncRun.ts`
- Test: `__tests__/syncRun.test.tsx` (생성) — `jest.mock('expo-secure-store', () => require('@/testing/secureStoreMock'))`, 매 테스트 `storedItems.clear()`. 훅은 `renderHook`에 `QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })` wrapper(`accountLinkApi.test.tsx`와 같다).

**Interfaces:**
- Consumes: `fetchSyncRun` · `keys.syncRun` · `isRunOpen` (Task 1), `invalidateAccountLinkData`
- Produces:
  ```ts
  // lastSyncRun.ts — kvStore 'sync.last_run_id'. 실패는 삼킨다
  export function loadLastSyncRunId(): Promise<string | null>   // 빈 문자열이 아닌 문자열이 아니면(undefined 포함) null
  export function saveLastSyncRunId(runId: string): Promise<void>
  export function clearLastSyncRunId(): Promise<void>

  // useSyncRun.ts
  export function useSyncRun(runId: string | null, opts: { polling: boolean }): {
    run: SyncRun | null;          // 조회한 값
    loading: boolean;             // runId가 있고 첫 조회 중
    error: unknown;               // 마지막 조회 오류(없으면 undefined)
    refetch: () => void;          // runId가 없으면 아무것도 하지 않는다
  }
  ```
  - `useQuery({ queryKey: keys.syncRun(runId ?? ''), queryFn: () => fetchSyncRun(runId!), enabled: !!runId, staleTime: 0, refetchInterval: (query) => opts.polling && (!query.state.data || isRunOpen(query.state.data)) ? 60_000 : false })`. 값이 아직 없으면(첫 조회 오류) 주기를 이어 간다(설계 §6.2).
  - `refetch`는 `if (runId) void query.refetch()`. TanStack 5의 `refetch()`는 `enabled: false`여도 부르기 때문이다.
  - 닫힌 실행 무효화(설계 §6.3): 받은 값이 닫힘(`!isRunOpen`)이고 그 `run_id`로 아직 무효화하지 않았으면 `invalidateAccountLinkData(queryClient)`를 부르고 기억한다. 처음부터 닫힌 값도 같다. 기억은 "앱이 켜진 동안"이라 `QueryClient`마다 하나다: 모듈의 `WeakMap<QueryClient, Set<string>>`. 앱에는 클라이언트가 하나고 테스트는 테스트마다 새로 만든다.
  - `403`도 `error`로 돌려준다. 지우는 판단은 Task 4(`useSyncCard`)가 한다.
  - 주기 계산에 쓰는 `polling`은 Task 5가 넘긴다. 이 태스크의 테스트는 `polling: true`로 본다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**
  ```ts
  it('마지막 실행 id를 저장 · 읽기 · 지우기 한다', /* save('r-1') → load 'r-1' → storedItems.get('sync.last_run_id') 'r-1' → clear → null */);
  it('저장소가 실패하거나 값이 문자열이 아니면 읽기는 null이다', /* jest.spyOn(kvStore, 'getItemAsync').mockRejectedValueOnce(new Error()) → null · mockResolvedValueOnce(undefined as never) → null · '' → null */);
  it('runId가 없으면 부르지 않고 refetch도 부르지 않는다', /* renderHook(useSyncRun(null, …)) → result.current.refetch() → fetch 0회 */);
  it('열린 실행은 60초마다 다시 묻는다', /* jest.useFakeTimers · runningRun → 60초 진행 → GET 2회 */);
  it('닫힌 실행은 다시 묻지 않는다', /* doneRun → 120초 진행 → GET 1회 */);
  it('첫 조회가 실패하면 60초 뒤 다시 묻는다', /* 500 → 60초 → GET 2회 */);
  it('열림에서 닫힘으로 바뀌면 포트폴리오 조회 전체를 한 번 무효화한다', /* 첫 응답 runningRun, 둘째 doneRun · spyOn(queryClient, 'invalidateQueries') → ['summary'] 호출 1회 · rerender · 다음 refetch 뒤에도 1회 */);
  it('처음부터 닫힌 실행이어도 한 번 무효화한다', /* doneRun → ['summary'] 1회 · refetch 뒤에도 1회 */);
  it('같은 클라이언트에서 같은 실행을 다시 그려도 무효화하지 않는다', /* 한 클라이언트로 renderHook 두 번(unmount 뒤 다시) → 1회 */);
  ```
  가짜 타이머에서 `waitFor`가 멈추면 `await act(async () => { jest.advanceTimersByTime(60_000); })`로 진행한다. 저장소에 아직 `jest.useFakeTimers`를 쓰는 테스트가 없으니, 막히면 실제 타이머와 `refetchInterval` 값 단언(옵션을 읽는 방식)으로 바꾸고 그 사실을 보고에 적는다.
- [ ] **Step 2:** FAIL을 본다.
- [ ] **Step 3: 구현한다.**
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` — PASS.
- [ ] **Step 5: 커밋** — `feat: 동기화 실행을 조회하고 닫힌 실행을 처음 보면 포트폴리오 조회를 다시 받는다`

---

## Task 4: 계좌 탭 — 동기화 카드와 지금 동기화

**Files:**
- Create: `screens/accounts/useSyncCard.ts`, `screens/accounts/SyncCard.tsx`
- Modify: `screens/accounts/AccountsScreen.tsx`
- Test: `__tests__/syncCard.test.tsx` (생성), `__tests__/accounts.test.tsx`(기존 단언이 깨지는 곳만)

**Interfaces:**
- Consumes: Task 1 ~ 3 전부
- Produces:
  ```ts
  // useSyncCard.ts
  export function useSyncCard(notices: Notice[], opts: { polling: boolean }): {
    runId: string | null;                     // 카드에 보일 실행
    run: SyncRun | null; loading: boolean; failedToLoad: boolean;   // failedToLoad: 403 밖의 조회 오류
    dismiss: () => void;                      // 닫힌 실행에서만 부른다. 저장한 id를 지운다
    request: () => void;                      // POST /sync
    requesting: boolean;
    requestError: string | null;              // 버튼 아래 한 줄
    clearRequestError: () => void;            // Task 5가 탭을 떠날 때 부른다
    refetch: () => void;                      // useSyncRun의 refetch
  }
  // SyncCard.tsx
  export function SyncCard(props: { notices: Notice[]; card: ReturnType<typeof useSyncCard> }): ReactElement | null
  ```
  - 상태 `storedId`: 마운트 때 `loadLastSyncRunId()`로 읽는다. 보일 실행 = `noticeRunId(notices) ?? storedId`.
  - notice id 반영: 첫 읽기가 끝난 뒤, notice id가 있고 `storedId`와 다르면 **먼저 `storedId`를 notice id로 바꾸고** `saveLastSyncRunId`를 부른다(결과를 기다리지 않는다). 효과의 의존성은 notice id와 첫 읽기 완료 여부다. 그래서 저장소 쓰기가 실패해도, 닫힌 뒤 뷰에서 notice가 사라져도 카드가 남는다.
  - 조회 오류가 `ApiError`이고 `status === 403`이면 `storedId`를 null로, 저장소도 지운다. 카드도 오류 문구도 없다.
  - `request`: 제출 핸들러가 `requestSync()`를 직접 부른다(`useMutation` 없이, 설계 §2.2). 보내는 동안 다시 부르면 무시한다. 시작할 때 `requestError`를 비운다. `202`면 `storedId`를 `run_id`로 바꾸고 `saveLastSyncRunId`, `accounts` · `account-links`를 무효화한다. 실패면 `ApiError.message`, `NetworkError`면 그 문구, 그 밖의 예외는 `요청을 처리하지 못했어요`.
  - `dismiss`: `storedId`를 null로, 저장소를 지운다.
  - `SyncCard`: `runId`가 null이면 null. 제목 · 둘째 줄 · 계좌 줄(설계 §3.5, `syncCopy`), `run`이 있고 `!isRunOpen(run)`이면 `닫기`(`TextButton`), 첫 조회 중이면 제목만, `failedToLoad`면 제목 아래 `진행 상태를 불러오지 못했어요`. 색은 `tone`으로 `palette.textMuted` · `palette.warnText`(`LinkedAccountRow`의 상태 줄과 같다). 카드 틀은 `ui/Card`.
  - `AccountsScreen`: 목록 맨 아래와 `emptyAction`에 `[SyncCard, 지금 동기화 Button(loading=requesting), requestError 줄, 계좌 연동 관리 Button]`을 같은 순서로 둔다. `envelope.empty_reason === 'NO_ACCOUNTS'`이면 `지금 동기화`와 오류 줄을 두지 않는다(카드는 둔다). `onRefresh`는 계좌별 뷰와 `card.refetch`를 함께 부른다. 머리 주석의 "지금 동기화도 이 버튼 옆에 들어온다" 문장을 지금의 사실로 바꾼다. 이 태스크는 `polling: true`를 넘기고 Task 5가 바꾼다.

- [ ] **Step 1: 실패하는 테스트를 쓴다** — `syncCard.test.tsx`.
  - 그리기: `renderWithStack('accounts', AccountsScreen, undefined, { others: ['positions', 'account-link'] })`. 돌려받는 `queryClient`에 `jest.spyOn(queryClient, 'invalidateQueries')`를 건다. `jest.mock('expo-secure-store', () => require('@/testing/secureStoreMock'))`, 매 테스트 `storedItems.clear()`.
  - 응답: `serveRoutes`로 `/portfolio/views/accounts` · `POST /sync` · `/^\/sync\//`. 뷰는 `goldenAccounts`에 `syncNotices(...)`를 더한 사본, 빈 상태는 기존 `accounts.test.tsx`의 빈 봉투 모양에 `empty_reason` · `notices`를 준 것. 응답을 바꿔 가며 주려면 `body`를 함수로 둔다.
  - 네트워크 오류: `serveRoutes` 뒤에 `const served = global.fetch; global.fetch = jest.fn((url, init) => init?.method === 'POST' && String(url).endsWith('/sync') ? Promise.reject(new TypeError('Network request failed')) : served(url, init)) as typeof fetch`(`accountLink.test.tsx`의 감싸기와 같다).
  - 새로고침: `AsOfBanner`의 `새로고침` 버튼(`getByRole('button', { name: '새로고침' })`, `summary.test.tsx`와 같다)을 누른다.
  ```ts
  it('목록 아래에 지금 동기화와 계좌 연동 관리가 있다');
  it('첫 수집 전(NO_HOLDINGS)에도 지금 동기화가 있다');
  it('계좌가 없으면(NO_ACCOUNTS) 지금 동기화가 없다', /* 계좌 연동 관리는 있다 */);
  it('지금 동기화를 누르면 POST /sync를 보내고 계좌별 뷰와 연동 목록을 무효화해 카드가 뜬다', /* POST 202 → invalidateQueries에 ['accounts'] · ['account-links'] → 두 번째 뷰 응답의 notice로 '동기화 요청을 받았습니다 · 다음 수집 10-29(목) 23:00' · '수집 대기' · storedItems 'sync.last_run_id' */);
  it('보내는 동안 다시 눌러도 한 번만 보낸다', /* Route.wait로 응답을 붙잡고 두 번 누름 → POST 1회 */);
  it('요청이 실패하면 버튼 아래 서버 문구를 보이고 다시 누르면 지운다', /* 409 { error: { code: 'NO_ACCOUNTS', message: '동기화할 계좌가 없습니다' } } */);
  it('닿지 못하면 연결 실패 문구를 보인다', /* '연결에 실패했어요. 잠시 후 다시 시도해 주세요' */);
  it('notice의 실행 id로 카드가 뜨고 그 id를 저장한다', /* 저장 비어 있음 · 빈 상태(NO_HOLDINGS) 포함 */);
  it('notice의 실행 id가 저장한 id와 다르면 notice의 id로 바꾼다', /* storedItems에 OTHER_RUN_ID → notice SYNC_RUN_ID → GET /sync/SYNC_RUN_ID · 저장값 SYNC_RUN_ID */);
  it('앱을 다시 켜도 저장한 id로 닫힌 결과가 보인다', /* storedItems.set('sync.last_run_id', id) · 뷰에 notice 없음 · GET partialRun → '일부 계좌를 동기화하지 못했어요' · '수집 실패' · '재인증 필요' · ['summary'] 무효화 1회 */);
  it('닫기를 누르면 저장한 id를 지우고 카드가 사라진다');
  it('실행 조회가 403이면 id를 지우고 카드를 그리지 않는다', /* 오류 문구도 없다 */);
  it('실행 조회가 실패하면 진행 상태를 불러오지 못했다고 한다', /* 500 */);
  it('열린 실행이 닫히는 것을 보면 무효화하고 카드는 결과로 남는다', /* GET 첫 runningRun, 새로고침 뒤 doneRun · 뷰 두 번째 응답은 notice 없음 → '동기화 완료 · 10-29 23:41' · ['summary'] 1회 */);
  it('저장소 쓰기가 실패해도 닫힌 뒤 카드가 남는다', /* jest.spyOn(kvStore, 'setItemAsync').mockRejectedValue(new Error()) · 위와 같은 흐름 */);
  it('카드가 없으면 새로고침해도 /sync를 부르지 않는다', /* notice 없음 · 저장 없음 → 새로고침 → /sync 경로 호출 0 */);
  ```
- [ ] **Step 2:** FAIL을 본다.
- [ ] **Step 3: 구현한다.**
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` — PASS. 계좌별 화면을 그리는 기존 테스트(`accounts` · `accountTabDot` · `accountLinkFlow` · `navigation` 등)는 secure-store 대역이 없어 저장소 읽기가 `undefined`로 풀릴 수 있고, fetch 대역은 `/sync`를 모른다. notice가 없으면 `/sync/…`를 부르지 않아야 한다(Task 3의 정규화 · `enabled` · `refetch` 막기). 깨지면 그 원인부터 본다.
- [ ] **Step 5: 커밋** — `feat: 계좌 탭에 지금 동기화와 동기화 카드를 둔다`

---

## Task 5: 조회 주기 — 탭 포커스 · 앱 복귀

**Files:**
- Modify: `screens/accounts/useSyncCard.ts`(포커스 · 앱 상태를 여기에 모은다), `screens/accounts/AccountsScreen.tsx`(`polling` 인자를 뺀다)
- Test: `__tests__/syncCard.test.tsx`

**Interfaces:**
- `useSyncCard(notices)`로 인자를 줄이고, 안에서 `polling = useIsFocused() && appActive`를 계산해 `useSyncRun`에 넘긴다.
- `appActive` 시작값은 `AppState.currentState !== 'background' && AppState.currentState !== 'inactive'`(앞에 있지 않다는 확증이 있을 때만 끈다. RN jest 대역의 `currentState`는 함수라 테스트에서는 참으로 시작한다). `AppState.addEventListener('change', …)`로 갱신하고, `'active'`로 돌아오면 `refetch()`.
- 탭에 다시 들어올 때 `refetch()`(`useFocusEffect`, 첫 포커스는 건너뛴다 — `AlertDetailScreen`과 같다). 탭을 떠날 때(정리 함수) `clearRequestError()`(설계 §2.2).

- [ ] **Step 1: 실패하는 테스트를 쓴다** — Task 4의 `renderWithStack` 그리기를 그대로 쓴다. 다른 화면에 갔다 오기는 돌려받은 `navigation`으로 `navigate('account-link')` → `goBack()`(`alertDetail.test.tsx`의 `다른 화면에서 돌아올 때만 다시 받는다`와 같다). 앱 상태는 `jest.spyOn(AppState, 'addEventListener')`로 리스너를 잡아 `'background'` · `'active'`를 흘린다. 주기는 가짜 타이머(Task 3에서 실제 타이머로 바꿨으면 같은 방식).
  ```ts
  it('열린 실행은 화면이 보이고 앱이 앞에 있을 때만 60초마다 다시 묻는다', /* 60초 → GET +1 · 'background' → 120초 → 그대로 · 'active' → 즉시 +1 */);
  it('다른 화면에 가 있으면 다시 묻지 않고, 돌아오면 묻는다');
  it('닫힌 실행은 돌아와도 주기 조회를 하지 않는다', /* 돌아올 때 한 번 묻는 것은 괜찮다 — 주기만 본다 */);
  it('요청 실패 문구는 다른 화면에 갔다 오면 사라진다');
  ```
- [ ] **Step 2:** FAIL을 본다.
- [ ] **Step 3: 구현한다.**
- [ ] **Step 4:** `npx jest && npx tsc --noEmit` — PASS.
- [ ] **Step 5: 커밋** — `feat: 동기화 진행 조회를 계좌 탭이 보이고 앱이 앞에 있을 때만 돌린다`

---

## Task 6: 문서 맞추기

구현이 main에 들어간 뒤 테스트 문서에서 "구현이 없다"는 동기화 유보를 걷는다. 문서를 고치기 전에 무엇을 바꿀지 사용자에게 먼저 설명한다.

- [ ] **Step 1:** 통합테스트 설계(`docs/yhr/test/2026-10-16-test-design.md`) §2.4 반영 대기 · §3.1 전제 구현 · §8 범위 제외 · 유보의 "수동 동기화의 화면" 행을 지우고, PF3 `데이터` 칸의 "⑧은 유보(§2.4)"를 뺀다.
- [ ] **Step 2:** 테스트 케이스(`docs/yhr/test/2026-10-28-test-cases.md`)의 PF3-05 · PF3-18 · PF3-19 · PF3-20에서 결과 `유보`와 비고 "구현되지 않았다(설계 §2.4)"를 걷는다. 결과를 무엇으로 둘지(`미실행` 등)는 그 문서의 범례를 따른다.
- [ ] **Step 3: 커밋** — `docs: 수동 동기화 화면이 들어가 테스트 문서의 유보를 걷는다`

---

## 실행 후 확인 (각각 사용자 승인 필요)

1. **로컬 백엔드 기동:** `back-end` main을 `local` 프로파일로 띄운다. 웹으로 보려면 `APP_WEB_ORIGINS`에 개발 서버 출처를 넣는다. 명령은 그때 `back-end/README` · 설정을 보고 정해 승인받는다.
2. **앱 기동:** Expo 웹 또는 시뮬레이터. `EXPO_PUBLIC_API_BASE_URL`이 로컬 백엔드를 가리키는지 확인한다.
3. **시나리오:** 계좌가 있는 로컬 사용자로 `지금 동기화` → 카드에 `동기화 요청을 받았습니다 · 다음 수집 …`과 계좌별 `수집 대기`. 로컬에는 수집기가 없어 실행이 닫히지 않는다. 닫힌 결과는 테스트로만 본다.
4. 운영 서버에 동기화 요청을 보내지 않는다.
