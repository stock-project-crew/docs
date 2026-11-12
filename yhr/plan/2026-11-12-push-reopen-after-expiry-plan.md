# 세션이 끝난 뒤 누른 푸시 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 앱이 뒤에 있는 동안 세션이 끝난 뒤 누른 푸시도 로그인 뒤 그 울린 알림 상세를 연다. 로그인에 실패해도 맡아 둔 푸시를 버리지 않는다.

**Architecture:** 푸시 우편함(`src/push/pushInbox.ts`)이 "받는 쪽에 바로 넘겼지만 상세가 아직 결과를 그리지 않은 것"을 표(ticket) 하나로 기억한다. 울린 알림 상세는 그려질 때 자기 `event_id`의 표를 받아 두고, 조회 결과(성공 또는 `404`)를 그리거나 화면을 떠날 때 자기 표만 지운다. 갱신이 거절돼 세션이 끝날 때(인증 컨텍스트의 만료 처리) 남은 기억을 다시 맡겨 두면, 로그인 뒤 탭 묶음이 그려질 때 기존 경로로 열린다. 로그인 실패는 맡아 둔 것을 버리지 않고, 로그아웃만 버린다.

**Tech Stack:** React Native · Expo SDK 58 · React Navigation 7 · TanStack Query · TypeScript · jest-expo

**Spec:** [앱 정보 구조](../specs/app-information-architecture.md) §4.2(앱 상태별 동작) — Task 5가 고친다. 인증 동작은 [인증 세션 설계](../specs/portfolio-management/2026-11-11-auth-session-design.md)와 [포트폴리오 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) §8.8.

## Global Constraints

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어. 커밋 접두어 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **커밋 · 푸시는 사용자가 요청할 때만 한다.**
- 주석은 히스토리 없이 최신 사실만 쓰고, 문서 절 번호(`IA §4.2` 등)를 넣지 않는다. 고치는 주석에 있던 절 지칭은 풀어 쓴다.
- 작업 위치: 앱 `.worktrees/front-end-push-date-field`(브랜치 `fix/push-reopen-date-field`), docs `.worktrees/docs-alert-push-date`(브랜치 `docs/alert-push-date`).
- `sessionEpoch` · `logout` · `releaseOnLogout` · 앞으로 올 때의 로그아웃 재시도와 기기 재등록을 깨지 않는다. `logout.test.tsx` · `refresh.test.tsx` · `login.test.tsx` · `push.test.tsx`가 계속 통과해야 한다.
- 앱이 완전히 꺼진 상태의 푸시 동작(콜드 스타트)은 바꾸지 않는다. 로그인 실패 규칙(Task 4)만 예외다.
- 다른 계정으로 로그인해 남은 푸시를 열면 지금처럼 `찾을 수 없는 알림이에요`를 보인다(사용자 결정).
- 끝에 `npx jest` · `npx tsc --noEmit` 통과.

## Review Focus

1. **상세를 이미 본 뒤에 세션이 끝남** — 로그인 뒤 그 상세가 다시 열리면 안 된다. → Task 3 `상세를 본 뒤 세션이 끝나면 로그인 뒤 다시 열지 않는다`.
2. **앱 안 배너를 눌러 연 상세** — 앞에 떠 있을 때 온 푸시의 배너도 같은 경로로 넘겨야 세션 만료에서 잃지 않는다. → Task 2 `배너를 눌러도 우편함을 거쳐 연다`.
3. **상세가 뜨기 전에 사용자가 떠남(연결 오류 뒤 뒤로 가기)** — 나중에 다른 화면에서 세션이 끝나도 옛 푸시를 다시 열지 않는다. → Task 2 `넘긴 뒤 상세를 떠나면 다시 맡지 않는다`.
4. **작성 중인 알림 위에서 누른 푸시를 저장으로 접음** — 열지 않기로 한 것을 세션 만료 뒤 열면 안 된다. → Task 2 `저장으로 접은 푸시는 다시 맡지 않는다`.
5. **조회 중인 상세 위로 같은 푸시가 다시 옴** — 옛 상세가 걷히며 새로 넘긴 기억을 지우면, 그 뒤 세션이 끝날 때 잃는다. 기억을 `event_id`가 아니라 표로 맞춰 막는다. → Task 2 `옛 화면이 걷혀도 새로 넘긴 것은 남는다`.

다른 계정으로 로그인해 여는 경우(`찾을 수 없는 알림이에요`)는 Task 3 `다른 계정으로 로그인하면 찾을 수 없는 알림이다`가 맡는다.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `src/push/pushInbox.ts` | 넘긴 것 기억 · 다시 맡기 · 버리기 |
| `src/push/PushRouter.tsx` | 배너도 우편함을 거친다, 저장으로 접으면 기억을 지운다 |
| `src/screens/alerts/AlertEventScreen.tsx` | 결과를 그리거나 떠나면 기억을 지운다 |
| `src/auth/AuthContext.tsx` | 만료 처리에서 다시 맡김, 로그인 실패에 버리지 않음 |
| `src/testing/serveRoutes.ts` | 토큰별로 401을 주는 대역(`serveGuarded`)을 공용으로 |
| `src/__tests__/refresh.test.tsx` | 공용 `serveGuarded`를 쓴다 |
| `src/__tests__/push.test.tsx` | 우편함 단위 · 로그인 실패 규칙 |
| `src/__tests__/pushSession.test.tsx` (신규) | 실제 인증 컨텍스트로 재현 |
| docs `yhr/specs/app-information-architecture.md` | §4.2 |

---

### Task 1: 토큰별 401 대역을 공용으로 옮긴다

**Files:**
- Modify: `src/testing/serveRoutes.ts`
- Modify: `src/__tests__/refresh.test.tsx`

**Interfaces:**
- Produces: `serveGuarded(routes: Route[], guarded: string[], acceptedToken: string): Call[]` — `guarded` 경로는 `Bearer <acceptedToken>`을 실었을 때만 `routes`대로 답하고, 그 밖의 토큰에는 `401 UNAUTHENTICATED`로 답한다. 401 본문 상수 `unauthorized`도 함께 내보낸다.

- [ ] **Step 1: `refresh.test.tsx`의 `serveGuarded`와 `unauthorized`를 `serveRoutes.ts`로 옮긴다.** 동작은 바꾸지 않는다.
- [ ] **Step 2: 테스트**

Run: `npx jest src/__tests__/refresh.test.tsx`
Expected: PASS(옮기기 전과 같은 수)

- [ ] **Step 3: 커밋** — `test: 토큰별로 401을 주는 대역을 공용으로 옮긴다`

### Task 2: 우편함이 넘긴 것을 기억하고 다시 맡는다

**Files:**
- Modify: `src/push/pushInbox.ts`
- Modify: `src/push/PushRouter.tsx`
- Modify: `src/screens/alerts/AlertEventScreen.tsx`
- Test: `src/__tests__/push.test.tsx`

**Interfaces:**
- Produces (`pushInbox.ts`):
  - `type OpenTicket = { readonly eventId: string }` — 넘길 때마다 새로 만드는 객체. 같은 `event_id`라도 넘긴 차례마다 다르다.
  - `deliverOpen(eventId: string): void` — 받는 쪽이 있으면 새 표를 "넘긴 것"으로 기억한 뒤 넘긴다. 없으면 지금처럼 맡는다.
  - `subscribeOpens(fn)` — 맡아 둔 것을 넘길 때는 **기억하지 않는다**. 앱이 꺼진 상태에서 누른 푸시(콜드 스타트)의 동작을 바꾸지 않기 위해서다.
  - `claimOpen(eventId: string): OpenTicket | null` — 기억한 표의 `eventId`가 같으면 그 표를 돌려준다. 상세가 그려질 때 한 번 부른다.
  - `settleOpen(ticket: OpenTicket | null): void` — 기억한 것이 바로 그 표면 지운다. 다른 표면 아무것도 하지 않는다.
  - `requeueUnsettledOpen(): void` — 기억한 표가 있으면 그 `eventId`를 맡아 두고(`pending`) 기억을 지운다.
  - `discardPendingOpen(): void` — 맡아 둔 것과 기억한 것을 모두 지운다.
  - `resetPushInbox()`는 기억도 지운다.

- [ ] **Step 1: 실패하는 단위 테스트를 `푸시 대기열` describe에 더한다**

```tsx
it('넘긴 뒤 결과가 그려지기 전에 세션이 끝나면 다시 맡는다', () => {
  const first = jest.fn();
  const off = subscribeOpens(first);
  deliverOpen('e-1');
  off();
  requeueUnsettledOpen();
  const next = jest.fn();
  subscribeOpens(next);
  expect(next).toHaveBeenCalledWith('e-1');
});

it('결과가 그려진 뒤에는 다시 맡지 않는다', () => {
  const off = subscribeOpens(jest.fn());
  deliverOpen('e-1');
  settleOpen(claimOpen('e-1'));
  off();
  requeueUnsettledOpen();
  const next = jest.fn();
  subscribeOpens(next);
  expect(next).not.toHaveBeenCalled();
});

it('버리면 넘긴 것도 다시 맡지 않는다', () => {
  const off = subscribeOpens(jest.fn());
  deliverOpen('e-1');
  off();
  discardPendingOpen();
  requeueUnsettledOpen();
  const next = jest.fn();
  subscribeOpens(next);
  expect(next).not.toHaveBeenCalled();
});

it('옛 화면이 걷혀도 새로 넘긴 것은 남는다', () => {
  const off = subscribeOpens(jest.fn());
  deliverOpen('e-1');
  const old = claimOpen('e-1');
  deliverOpen('e-1');
  settleOpen(old);
  off();
  requeueUnsettledOpen();
  const next = jest.fn();
  subscribeOpens(next);
  expect(next).toHaveBeenCalledWith('e-1');
});

it('맡아 둔 것을 넘길 때는 기억하지 않는다 — 콜드 스타트 동작은 그대로다', () => {
  deliverOpen('e-1');
  const off = subscribeOpens(jest.fn());
  off();
  requeueUnsettledOpen();
  const next = jest.fn();
  subscribeOpens(next);
  expect(next).not.toHaveBeenCalled();
});
```

화면 테스트 공통(기존 `renderApp()` 사용):
- `serveRoutes`는 처음 맞는 경로를 쓴다. `appRoutes`에 `/alert-events/e-1`의 200이 있으므로, 덮어쓸 경로는 **`appRoutes`보다 앞에** 둔다.
- `deliverOpen`은 그린 뒤 탭이 보이면(`총자산`) `act` 안에서 부른다. 그리기 전에 부르면 맡아 두는 경로를 타서, 기억이 생기지 않아 검증이 비게 된다.
- 응답을 붙잡을 때는 `refresh.test.tsx`의 `gate()` 같은 열 수 있는 약속을 쓰고 테스트 끝에 푼다.

화면 테스트:
- `넘긴 뒤 상세를 떠나면 다시 맡지 않는다`: `/alert-events/e-1`을 `networkError`로 두고 `deliverOpen('e-1')` → 연결 오류가 보이면 `navigation.goBack()` → `requeueUnsettledOpen()` → 새 `subscribeOpens(fn)`의 `fn`이 불리지 않는다.
- `배너를 눌러도 우편함을 거쳐 연다`: `deliverArrival({ eventId: 'e-1', … })` → 배너를 누른다 → 상세가 열리기 전에 막기 위해 `/alert-events/e-1`을 `wait`로 붙잡고, `requeueUnsettledOpen()` 뒤 새 구독자가 `'e-1'`을 받는다.
- `저장으로 접은 푸시는 다시 맡지 않는다`: 기존 `계속 쓰다 저장하면 저장 결과 화면을 그대로 두고 상세를 가로채지 않는다`의 끝에 `requeueUnsettledOpen()` 뒤 새 구독자가 불리지 않는다는 단언을 더한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `npx jest src/__tests__/push.test.tsx`
Expected: 새 테스트 FAIL(`settleOpen` · `requeueUnsettledOpen`이 없음)

- [ ] **Step 3: 구현한다**
  - `pushInbox.ts`: 모듈 변수 `handed: string | null`. 위 Interfaces대로. 파일 머리 주석은 "누른 푸시는 받을 화면(탭 묶음)이 그려진 뒤에야 열 수 있다. 로그인 전에 받은 `event_id`는 네비게이션 바깥인 여기에 맡겨 두었다가, 탭 묶음이 그려지면 한 번 넘긴다. 넘긴 것은 울린 알림 상세가 결과를 그릴 때까지 기억한다. 그 사이 세션이 끝나 탭 묶음이 걷히면 다시 맡아 두어 로그인 뒤에 연다."로 바꾼다. `discardPendingOpen` 위 주석은 "로그아웃하면 맡아 둔 것과 넘긴 것을 버린다. 다른 사람이 이어 로그인할 수 있기 때문이다."
  - `PushRouter.tsx`: 배너의 `onPress`는 `open(arrival.eventId)` 대신 `deliverOpen(arrival.eventId)`(받는 쪽이 `open`이므로 같은 화면이 열린다). 작성 중 모달을 저장으로 접어 열지 않는 분기(`routes[...]?.name === 'alert'`)에서 `settleOpen(claimOpen(eventId))`를 부른다(열지 않기로 했으므로 기억을 지운다).
  - `AlertEventScreen.tsx`: 처음 그려질 때 `claimOpen(eventId)`로 표를 받아 `useRef`에 둔다. `event.data`가 있고 받는 중이 아니거나(`!event.isFetching`) 오류가 `404`이면 `settleOpen(표)`. 앞서 본 상세가 캐시에 남아 있으면 다시 받는 동안은 결과로 치지 않는다 — 그 조회가 401로 세션을 끝낼 수 있다. 화면이 사라질 때(effect 정리)도 `settleOpen(표)`. 자기 표만 지우므로 같은 푸시가 다시 와 옛 화면이 걷혀도 새로 넘긴 것은 남는다. 세션 만료로 걷힐 때는 인증 컨텍스트가 먼저 다시 맡기므로(조회가 오류를 던지기 전에 만료 처리를 부른다) 정리에서 지워도 맡아 둔 것은 남는다. 이 두 가지를 주석으로 적는다.

- [ ] **Step 4: 테스트가 통과하는지 본다**

Run: `npx jest src/__tests__/push.test.tsx`
Expected: PASS

- [ ] **Step 5: 커밋** — `fix: 넘긴 푸시를 상세가 결과를 그릴 때까지 기억한다`

### Task 3: 세션 만료 때 넘긴 푸시를 다시 맡긴다 (D-40)

**Files:**
- Modify: `src/auth/AuthContext.tsx`
- Test: `src/__tests__/pushSession.test.tsx` (신규)

**Interfaces:**
- Consumes: Task 1 `serveGuarded`, Task 2 `requeueUnsettledOpen` · `deliverOpen`, `renderAppWithAuth`, `seedStoredSession`.

테스트 파일 공통: `jest.mock('expo-secure-store', …)`, `@/push/config`는 `pushCapable: false`(기기 등록이 섞이지 않게), `beforeEach`에서 `storedItems.clear()` · `resetClientState()` · `setUnauthenticatedHandler(null)` · `resetPushInbox()` · `resetDeviceState()`. 앱 경로는 요약 · 자산 변화 · 계좌별(`/portfolio/views/accounts`) · `/alerts` · `/alert-events/unread-count` · `POST /alert-events/e-1/read`. `SESSION_EXPIRED = 'ⓘ 로그인이 만료되었어요. 다시 로그인해 주세요'`(앞의 `ⓘ `까지 맞춘다). `renderAppWithAuth`는 네비게이션 ref를 주지 않으므로 상세가 열린 것은 `getByText(eventDetailFixture.title)`로 본다. 테스트 중간에 `serveGuarded`를 다시 부르면 호출 기록이 두 배열로 나뉜다. 순서 확인은 배열마다 따로 한다. `/alert-events/e-1`만 `serveGuarded`로 `tok-b`에서만 통과시킨다. 저장 세션은 `tok-a`(만료 시각은 살아 있음 — 서버만 그 토큰을 받지 않는 상황).

- [ ] **Step 1: 재현 테스트를 쓴다 (원인 확인)**

```tsx
it('뒤에 있던 앱에서 세션이 끝난 뒤 누른 푸시는 로그인 뒤 그 울린 알림 상세를 연다', async () => {
  seedStoredSession({ token: 'tok-a', refreshToken: 'ref-a' });
  serveGuarded([...appRoutes, { path: '/alert-events/e-1', body: eventDetailFixture },
    { method: 'POST', path: '/auth/refresh', status: 401, body: unauthorized }], ['/alert-events/e-1'], 'tok-b');
  await renderAppWithAuth();
  await waitFor(() => expect(screen.getByText('내 자산')).toBeTruthy());

  await act(async () => deliverOpen('e-1'));
  await waitFor(() => expect(screen.getByText(SESSION_EXPIRED)).toBeTruthy());

  serveGuarded([...appRoutes, { path: '/alert-events/e-1', body: eventDetailFixture },
    { method: 'POST', path: '/auth/login', body: { access_token: 'tok-b', expires_at: LIVE, refresh_token: 'ref-b' } }],
    ['/alert-events/e-1'], 'tok-b');
  await fireEvent.changeText(screen.getByLabelText('비밀번호'), 'pw');
  await fireEvent.press(screen.getByRole('button', { name: '로그인' }));

  await waitFor(() => expect(screen.getByText(eventDetailFixture.title)).toBeTruthy());
});
```

로그인 화면은 마지막 이메일이 채워져 있어 비밀번호만 넣는다.

- [ ] **Step 2: 실패를 확인하고 원인을 적는다**

Run: `npx jest src/__tests__/pushSession.test.tsx`
Expected: FAIL — 로그인 뒤 요약(`내 자산`)이 보이고 상세가 열리지 않는다. 원인이 "상세 조회 401 → 갱신 거절 → 만료 처리로 탭 묶음이 걷히며 넘긴 `event_id`를 잃음"인지 호출 기록으로 확인해 적는다. 첫 배열은 `/alert-events/e-1`(tok-a, 401) → `/auth/refresh`(401), 둘째 배열에는 로그인 뒤 `/alert-events/e-1` 호출이 없어야 한다. 원인이 다르면 멈추고 보고한다.

- [ ] **Step 3: 나머지 기대를 테스트로 쓴다**

- `접근 토큰만 만료된 뒤 누른 푸시는 로그인 화면 없이 상세를 연다`: 갱신이 `tok-b` 쌍으로 200 → 상세 제목이 보이고, 끝에서 `queryByText(SESSION_EXPIRED)`가 없으며 `/auth/login` 호출이 없다. 고치기 전에도 통과하는 동작 고정 테스트다.
- `상세를 본 뒤 세션이 끝나면 로그인 뒤 다시 열지 않는다`: `/alert-events/e-1`은 `tok-a`로도 통과 → 상세가 보인 채로 `serveGuarded`를 다시 불러 요약을 `tok-b`만 받게 하고 갱신 401 → `act` 안에서 `apiGet('/portfolio/views/summary').catch(() => undefined)`로 만료를 일으킨다(뒤로 가면 화면을 떠나서 지운 것이 되어 시험하려는 것이 달라진다) → 로그인 → 요약이 보이고 로그인 뒤 `/alert-events/e-1` 호출이 없다.
- `앞서 본 상세가 캐시에 남아 있어도 다시 받다 세션이 끝나면 로그인 뒤 연다`: `renderAppWithAuth(queryClient)`로 `staleTime: 0` · `gcTime: Infinity` 클라이언트에 상세를 미리 넣고 Step 1과 같은 흐름. 끝에 `queryClient.clear()`(타이머가 남아 jest가 끝나지 않는 것을 막는다). `renderAppWithAuth`가 클라이언트를 받게 고친다.
- `찾을 수 없는 알림을 본 뒤 세션이 끝나면 로그인 뒤 다시 열지 않는다`: `상세를 본 뒤 …`와 같은 흐름을 `404`로.
- `다른 계정으로 로그인하면 찾을 수 없는 알림이다`: Step 1과 같은데 로그인 뒤 `/alert-events/e-1`이 `404` → `찾을 수 없는 알림이에요`.

- [ ] **Step 4: 구현한다**

`AuthContext.tsx`에 만료 처리 하나를 둔다: `const expire = useCallback(() => { requeueUnsettledOpen(); endSession(true); }, [endSession]);` 이것을 만료 처리를 꽂는 두 곳(부팅 뒤의 `setUnauthenticatedHandler`와 `logout`의 `finally`)에서 같이 쓴다. 주석: "조회 도중 세션이 끝나면 어느 화면에 있든 로그인으로 돌아간다. 열고 있던 푸시가 있으면 다시 맡겨 두어 로그인 뒤에 연다."

- [ ] **Step 5: 테스트**

Run: `npx jest src/__tests__/pushSession.test.tsx src/__tests__/refresh.test.tsx src/__tests__/logout.test.tsx src/__tests__/login.test.tsx`
Expected: PASS

- [ ] **Step 6: 커밋** — `fix: 세션이 끝나 밀려난 푸시를 로그인 뒤에 연다`

### Task 4: 로그인에 실패해도 맡아 둔 푸시를 버리지 않는다

**Files:**
- Modify: `src/auth/AuthContext.tsx` (`login`의 catch)
- Test: `src/__tests__/push.test.tsx`

- [ ] **Step 1: 테스트를 바꾼다**

`로그인에 실패하면 맡아 둔 푸시를 버린다`를 `로그인에 실패해도 맡아 둔 푸시를 남겨 둔다`로 바꾼다. 같은 흐름 끝에 `subscribeOpens(fn)`의 `fn`이 `'e-1'`로 불린다. 같은 `LoginProbe` 방식으로 `로그아웃하면 맡아 둔 푸시를 버린다`를 더한다(`deliverOpen('e-1')` → `logout()` → 새 구독자가 불리지 않는다).

- [ ] **Step 2: 실패를 확인한다** — Run: `npx jest src/__tests__/push.test.tsx` / Expected: 바꾼 테스트 FAIL, 로그아웃 테스트 PASS

- [ ] **Step 3: `login`의 catch에서 `discardPendingOpen()`을 뺀다.** catch는 오류를 그대로 던지므로 `try/catch`를 걷고 `await requestLogin(...)`만 둔다. 함수 위에 주석: "로그인 전에 누른 푸시는 로그인에 실패해도 남겨 두고, 성공하면 탭 묶음이 그려질 때 연다. 비밀번호를 한 번 잘못 넣었다고 보려던 화면을 잃지 않게 한다. 버리는 것은 로그아웃뿐이다."

- [ ] **Step 4: 테스트** — Run: `npx jest && npx tsc --noEmit` / Expected: 모두 PASS

- [ ] **Step 5: 커밋** — `fix: 로그인에 실패해도 누른 푸시를 남겨 둔다`

### Task 5: 앱 정보 구조 §4.2를 고친다

**Files:**
- Modify: docs `yhr/specs/app-information-architecture.md`

- [ ] **Step 1: 표의 `뒤에 있음` 행을 셋으로 나눈다**

```markdown
| 뒤에 있음 · 인증됨 | 푸시를 누르면 울린 알림 상세 |
| 뒤에 있음 · 접근 토큰 만료 | 로그인 화면 없이 갱신한 뒤 울린 알림 상세 |
| 뒤에 있음 · 세션 만료 | 로그인 화면. **`event_id`를 기억해 두었다가 로그인 뒤에 연다** |
```

- [ ] **Step 2: 표 아래 문단을 바꾼다**

"인증 상태에 따라 앱은 로그인 화면과 탭 묶음 중 하나만 그린다. 그래서 로그인 전에 받은 `event_id`는 네비게이션 바깥에 보관했다가, 탭 묶음이 그려진 직후 한 번 연다. 연 울린 알림 상세가 결과를 그리기 전에 세션이 끝나면 그 `event_id`를 다시 보관해 로그인 뒤에 연다. 로그인에 실패해도 버리지 않고, 로그아웃하면 버린다."

- [ ] **Step 3: 참조 확인** — Run: `grep -rn "로그인에 실패하거나" yhr/specs` / Expected: 출력 없음

- [ ] **Step 4: 커밋** — `docs: 뒤에 있던 앱의 세션 만료 뒤 푸시와 로그인 실패 규칙을 정한다`

### Task 6: 실기기 확인 (사용자)

로컬 백엔드를 `PORTFOLIO_AUTH_ACCESS_TTL=PT2M PORTFOLIO_AUTH_IDLE_TTL=PT5M EXPO_PUSH_ENABLED=true`로 띄운다. **띄우기 전에 승인을 받는다.** 앱 `.env`의 API 주소는 개발 머신의 LAN IP다.

- [ ] C2-08(세션 만료): 로그인 → 앱을 뒤에 둠 → 5분 넘게 기다린 뒤 푸시를 누름 → 만료 배너가 있는 로그인 화면 → 로그인 → 그 울린 알림 상세가 열리고 읽음 처리됨
- [ ] 접근 토큰만 만료: 같은 설정에서 2분 넘고 5분 안에 누름 → 로그인 화면 없이 상세
- [ ] 로그인 실패 뒤 성공: 세션 만료 흐름에서 비밀번호를 한 번 틀린 뒤 맞게 넣음 → 상세가 열림
