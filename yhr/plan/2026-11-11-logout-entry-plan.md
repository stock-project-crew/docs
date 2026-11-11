# 로그아웃 자리 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 요약 제목 줄의 계정 아이콘 → 계정 시트 → `로그아웃`으로 로그아웃할 수 있게 한다. 기기 해제가 서버에 닿지 않아도 로그아웃은 막지 않고 따로 안내하지 않는다. 그때는 이 기기의 OS 푸시 수신을 끊고, 앱이 켜져 있는 동안 해제를 다시 보낸다.

**Architecture:** 앱만 고친다.
- 해제 · 등록의 순서와 상태는 `src/push/device.ts` 한 곳이 맡는다
  - 로그아웃마다 세대 번호를 올린다
  - 등록은 시작할 때의 세대와 토큰을 잡고 간다. 세대가 바뀌면 멈춘다
  - 해제 요청은 상한(3초)이 지나면 끊는다
- 다시 보낼 해제(해제 대기)는 메모리에만 둔다. 로그아웃한 사람의 토큰을 저장소에 남기지 않는다
- 해제 · 재시도 · 등록 요청은 잡아 둔 토큰을 직접 싣는다. `401`을 받아도 세션 만료 처리를 부르지 않는다
- OS 수신 끊기는 `expo-notifications`를 아는 유일한 파일인 `src/push/notifications.ts`에 둔다

**Tech Stack:** React Native(Expo 58) · TypeScript · jest-expo · @testing-library/react-native

**Spec:** [앱 정보 구조](../specs/app-information-architecture.md) §2.2 · §2.6 · §6.1, [알림 스펙](../specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md) §9.2

## Global Constraints

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어로 쓴다. 커밋 접두어는 `feat:` · `fix:` · `test:` · `docs:` · `chore:`이고, 끝줄은 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`이다.
- **커밋 · 푸시는 사용자가 요청할 때만 한다.**
- 주석은 히스토리 없이 최신 사실만 쓴다. 문서 절 번호를 지칭하지 않고, 주석만 읽어도 이해되게 쓴다. 검증하지 않은 것은 단정하지 않는다.
- 백엔드와 통합테스트 문서는 고치지 않는다.
- 작업 위치는 `.worktrees/front-end-logout`(브랜치 `feat/logout-entry`)다. 시작할 때 `npm ci`가 필요하다. 패키지 설치이므로 승인을 받은 뒤 한다.
- 끝에 `npx jest` · `npx tsc --noEmit`이 통과해야 한다.
- 13(울린 알림 정렬 · 만료 뒤 누른 푸시)도 `AuthContext.tsx` · `pushInbox.ts`를 고친다. `logout`에서 `discardPendingOpen()`을 부르는 자리와 순서는 바꾸지 않는다. 나중에 머지하는 쪽이 리베이스한다.

## 전제로 쓴 사실
- 백엔드 등록은 같은 Expo 토큰이면 누가 등록하든 기존 `device_id`를 그대로 돌려준다(`PushDeviceMapper.upsert`의 `ON CONFLICT (expo_push_token) … RETURNING device_id`). 해제는 자기 기기만 지운다. 다른 사람에게 옮겨진 기기면 `404`다.
- iOS에서 Expo 토큰을 받을 때마다 `registerForRemoteNotifications()`가 불린다(expo-notifications 58.1.8 `PushTokenModule.swift`). 그래서 OS 수신 끊기는 다음 등록 때 다시 켜진다.
- OS 수신 끊기(`unregisterForNotificationsAsync`)는 iOS에서 `unregisterForRemoteNotifications()`, Android에서 FCM `deleteToken()`을 부른다. 실패를 JS로 알려 주는 길은 확인하지 못했다.

## Review Focus

1. **상한이 지난 해제가 늦게 끝나도, 다음 로그인의 등록을 지우지 않는다.**
   - 보관한 `device_id`는 해제를 보내기 전에 저장소에서 지운다
   - 상한이 지나면 요청을 끊는다(`AbortController`)
   - 끊긴 요청은 그 뒤로 저장소를 건드리지 않는다
   - → Task 2 `상한이 지난 해제가 늦게 끝나도 다음 로그인이 저장한 기기를 지우지 않는다`
2. **로그아웃 전에 시작된 등록이 로그아웃 뒤에 요청을 보내지 않는다.** 등록은 매 await 뒤에 세대를 확인한다. 보내더라도 잡아 둔 토큰으로 보내고, `401`에 만료 안내를 띄우지 않는다. → Task 2 `로그아웃 전에 시작된 등록은 로그아웃 뒤에 요청을 보내지 않는다`
3. **재시도는 로그인 화면일 때만 돈다.** 해제 대기는 로그인이 아니라 등록이 성공했을 때 버린다. 로그인했는데 등록이 실패하면 대기가 남는다. 그 사람이 로그아웃한 뒤에 다시 보내며, 그 기기가 아직 앞사람 것일 때만 지워진다. → Task 3
4. **재시도가 `401`을 받아도 로그인 화면에 "세션이 만료됐어요"가 뜨지 않는다.** → Task 3
5. **로그아웃하면 이메일 칸이 처음부터 비어 있다.** 로그인 화면은 마운트할 때 이메일 상태를 읽는다. 그래서 `email`을 비우는 일은 `status`를 바꾸는 것과 같은 동기 구간에서 한다. → Task 4

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `src/api/client.ts` | `currentAccessToken()`. 주어진 토큰과 `AbortSignal`로 보내며 `401`에도 세션 만료 처리를 부르지 않는 `apiPostAs` · `apiDeleteAs` |
| `src/api/alertEndpoints.ts` | `registerDeviceTokenAs` · `unregisterDeviceIdAs` |
| `src/push/notifications.ts` | `stopRemotePush()`: OS 푸시 등록을 끊는다. 예외는 삼킨다 |
| `src/push/device.ts` | 세대 번호. `registerThisDevice()`(세대 · 토큰을 잡고, 진행 중인 해제를 기다림) · `releaseOnLogout(session)` · `retryPendingRelease()` |
| `src/auth/tokenStore.ts` | `clearLastEmail()` |
| `src/auth/AuthContext.tsx` | `logout`이 `releaseOnLogout`을 부르고 이메일을 비운다. 로그인 화면일 때 `AppState` `active`에서 재시도한다. 값을 내려 주는 `AuthValueProvider`를 따로 내보내 `AuthProvider`도 그것을 쓴다 |
| `src/screens/summary/SummaryScreen.tsx` · `AccountSheet.tsx`(신규) | 계정 아이콘(`person-circle-outline`, 접근성 이름 `계정`, 종 왼쪽)과 계정 시트(`ConfirmSheet`) |
| `src/testing/notificationsMock.ts` | `unregisterForNotificationsAsync`와 호출 기록 |
| `src/testing/renderWithNavigation.tsx` · `renderWithStack.tsx` · `src/__tests__/push.test.tsx`의 `renderApp` | 고정 값 `AuthValueProvider`로 감싼다. 요약을 그리는 기존 테스트가 깨지지 않게 하기 위해서다 |
| `src/testing/renderAppWithAuth.tsx`(신규) | 실제 `AuthProvider` + 앱 루트. 보안 저장소 대역에 세션을 심고 그린다 |
| `src/__tests__/logout.test.tsx`(신규) | 계정 시트 · 이메일 · 해제 결과 · 재시도 |
| `src/__tests__/push.test.tsx` | 임시 버튼 테스트 세 개를 실제 화면 경로로 옮긴다 |

## 동작 표

| 로그아웃할 때 | 해제 대기(메모리) | OS 수신 끊기 |
|---|---|---|
| 보관한 `device_id` 없음, 푸시 미지원 | 없음 | 안 함 |
| 보관한 `device_id` 없음, 권한 허용 | 없음 | 함 |
| `204` · `404` | 없음 | 안 함 |
| `401` | 없음(같은 토큰이라 다시 보내도 같다) | 함 |
| 네트워크 실패 · `5xx` · 3초 상한 초과 | 남김(`device_id` · 토큰 · 만료 시각) | 함 |

| 재시도(로그인 화면에서 앱이 앞으로 올 때) | 해제 대기 |
|---|---|
| 토큰이 이미 만료됨 | 보내지 않고 버린다 |
| `204` · `404` · `401` | 버린다 |
| 네트워크 실패 · `5xx` · 상한 초과 | 남긴다 |
| 로그인한 뒤 등록 성공 | 버린다 |
| 앱 종료 | 사라진다(메모리) |

로그인 화면에 따로 안내를 띄우지 않는다.

---

## Task 1: 테스트 도우미와 대역

- [ ] `AuthValueProvider`를 내보낸다. `AuthProvider`가 그것으로 값을 내려 주게 바꾼다(동작 변화 없음)
- [ ] 기존 도우미(`renderWithNavigation` · `renderWithStack` · `push.test.tsx`의 `renderApp`)를 고정 값 `AuthValueProvider`로 감싼다
- [ ] `renderAppWithAuth`를 만든다
- [ ] `notificationsMock`에 `unregisterForNotificationsAsync`와 호출 횟수를 더한다
- [ ] `npx jest`로 기존 테스트가 그대로 통과하는지 본다

## Task 2: 로그아웃 해제와 등록의 순서

- [ ] 실패하는 테스트를 쓴다(`logout.test.tsx`)
  - `해제가 404를 받으면 끝난 것으로 본다`
  - `해제가 401을 받으면 OS 수신을 끊고 다시 보내지 않는다`
  - `해제가 서버에 닿지 않으면 OS 수신을 끊고 대기를 남긴다`
  - `해제가 5xx를 받으면 OS 수신을 끊고 대기를 남긴다`
  - `상한이 지나면 요청을 끊고 OS 수신을 끊는다`
  - `상한이 지난 해제가 늦게 끝나도 다음 로그인이 저장한 기기를 지우지 않는다`
  - `로그아웃 전에 시작된 등록은 로그아웃 뒤에 요청을 보내지 않는다`
  - `등록한 적 없는 기기는 권한이 있으면 OS 수신만 끊는다`
  - `해제가 서버에 닿지 않아도 로그인 화면에 안내가 없다`
- [ ] 실패를 확인한다: `npx jest src/__tests__/logout.test.tsx`
- [ ] 구현한다
  - `apiPostAs` · `apiDeleteAs` · `currentAccessToken`
  - `stopRemotePush`
  - 세대 번호 · `releaseOnLogout`, 그리고 `registerThisDevice`의 세대 · 토큰 잡기
  - `logout`이 `releaseOnLogout`을 부르게 한다. 타입은 `() => void` 그대로다
- [ ] 통과를 확인한다

## Task 3: 해제 재시도

- [ ] 실패하는 테스트를 쓴다(`logout.test.tsx`)
  - `로그인 화면에서 앱이 앞으로 오면 대기 중인 해제를 그때의 토큰으로 다시 보낸다`
  - `재시도가 204를 받으면 다음에는 보내지 않는다`
  - `재시도가 서버에 닿지 않으면 다음에 다시 보낸다`
  - `재시도가 401을 받으면 대기를 버리고 만료 안내를 띄우지 않는다`
  - `토큰이 만료된 대기는 보내지 않고 버린다`
  - `로그인한 동안은 재시도하지 않는다`
  - `로그인 뒤 등록이 성공하면 대기를 버린다`
  - `진행 중인 재시도가 끝난 뒤에 등록한다`
- [ ] 실패를 확인한다
- [ ] `retryPendingRelease`와 `AuthProvider`의 `AppState` 구독을 구현한다(`status === 'unauthenticated'`일 때만)
- [ ] 통과를 확인한다

## Task 4: 계정 시트와 이메일

- [ ] 실패하는 테스트를 쓴다
  - `logout.test.tsx` `요약의 계정 아이콘을 누르면 로그인한 이메일과 로그아웃이 보인다`
  - `logout.test.tsx` `시트에서 취소하면 로그인한 채 요약에 남는다`
  - `logout.test.tsx` `시트에서 로그아웃하면 기기 해제 요청이 나가고 로그인 화면으로 간다`
  - `logout.test.tsx` `직접 로그아웃하면 로그인 칸의 이메일이 비어 있다`
  - `logout.test.tsx` `앱을 다시 켜도 로그아웃한 이메일이 채워지지 않는다`
  - `logout.test.tsx` `토큰 만료로 돌아오면 이메일이 채워져 있다`(기존 테스트가 이미 확인하면 그것을 쓴다)
  - `push.test.tsx`의 `로그아웃은 토큰이 살아 있을 때 기기를 지우고 끝난다` · `기기 해제가 401을 받아도 만료가 아니라 그냥 로그아웃이다` · `기기 해제 응답이 오지 않아도 상한이 지나면 로그아웃이 끝난다`: 기대는 유지한다. 누르는 곳만 `renderAppWithAuth`로 그린 실제 요약 화면 경로로 바꾸고 임시 버튼을 지운다
- [ ] 실패를 확인한다
- [ ] 구현한다
  - `AccountSheet`와 계정 아이콘
  - `clearLastEmail`
  - `logout`에서 `setEmail(null)`을 `endSession`과 같은 동기 구간에서 부른다
- [ ] 통과를 확인한다

## Task 5: 전체 확인과 실기기 확인

- [ ] `npx jest` · `npx tsc --noEmit`
- [ ] 바뀐 파일의 주석을 점검한다. 히스토리를 남기지 않았는지, 문서 절을 지칭하지 않았는지 본다
- [ ] 실기기 확인(아이폰 · Expo Go). 서버 기동과 로컬 DB 쓰기는 사용자 승인을 받은 뒤 한다
  1. 로그인하고 알림 권한을 허용해 기기를 등록한다 → 계정 아이콘 → 로그아웃
     - `push_device` 행이 사라지는지 본다
     - 그 사람의 알림을 울려도 푸시가 오지 않는지 본다(X2-07)
  2. 비행기 모드에서 로그아웃한다 → 비행기 모드를 끄고 그 사람의 알림을 울린다
     - 푸시가 오는지 본다. **OS 수신 끊기의 효과를 판정하는 단계다**
     - 앱을 뒤로 보냈다가 앞으로 가져오면 `push_device` 행이 사라지는지 본다
  3. 2 뒤에 같은 폰으로 같은 사람 · 다른 사람이 로그인한다
     - 기기가 다시 등록되는지, 푸시가 다시 오는지 본다
     - Expo 토큰이 바뀌었는지 기록한다
  4. Expo Go에서 OS 수신 끊기가 Expo Go의 다른 동작에 영향을 주는지 기록한다
- [ ] **판정**: 2에서 푸시가 온다면(OS 수신 끊기가 효과 없음) 멈추고 보고한다. 로그인 화면 안내를 둘지와 스펙 §2.6 · §9.2 문구를 다시 정한다
