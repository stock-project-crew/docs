# 인증 정보 갱신 · 수집 안내 앱 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 연동한 계좌의 앱키 · 시크릿을 바꾸는 갱신 화면과, 서버가 판정한 수집 안내(인증 실패 · 연속 실패 · 갱신 뒤 확인 대기)를 계좌 탭 카드 · 계좌 행 배지 · 연동 목록 상태 줄 · 계좌 탭 점으로 보인다.

**Architecture:** 서버의 `collection_alert`(행)와 notice 셋(봉투)을 그대로 그린다. 안내 문장은 서버 `message`를 쓰고, 앱은 배지 · 상태 줄만 코드로 고른다. 갱신 폼은 등록 폼의 칸 · 검사 · 입력값 다루기를 공유하고, 계좌번호 · 실전/모의는 읽기 전용으로 보인다.

**Tech Stack:** React Native · Expo SDK 58 · TypeScript · TanStack Query · React Navigation · jest-expo · RNTL

**Spec:** [계좌 연동 · 동기화 화면 설계](../specs/portfolio-management/2026-10-18-account-link-screen-design.md) — 이 계획의 §번호는 그 문서의 절이다. 서버 계약은 [등록 · 해제 · 인증 정보 갱신 API 설계](../specs/portfolio-management/2026-10-16-account-link-api-design.md)(이하 API 설계) §3.3 · §3.5 · §3.6 · §3.7. 상위 근거는 [포트폴리오 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) §2.7 · §7.2 · §7.5 · §10과 [앱 정보 구조](../specs/app-information-architecture.md) §2.2 · §3 · §6.1. 화면 설계에서 이 기능이 걸친 절은 §1 · §2.1 · §2.2 · §3.1 · §3.4 · §3.6 · §3.7 · §3.8 · §4 · §5 · §6.1 · §6.3 · §6.4 · §7이다.

## Global Constraints

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어. 커밋 접두어 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **커밋 · 푸시는 사용자가 요청할 때만 한다.**
- 주석은 히스토리 없이 최신 사실만 쓰고, 문서 절 번호(§ · SG-)를 지칭하지 않고 주석만으로 이해되게 쓴다. 검증하지 않은 것은 단정하지 않는다.
- 스펙 · 설계를 고치지 않는다. 설계와 코드가 어긋나면 멈추고 보고한다.
- **SDK는 바꾸지 않는다.** "앱을 Expo SDK 58로 올린다"(14) 작업이 앱 작업 가운데 가장 먼저 main에 머지된다. 이 작업은 그 위로 리베이스하고 `npm ci`로 다시 설치한다. 14가 아직 머지되지 않았으면 최신 origin/main에서 시작하고 머지 전에 리베이스한다.
- **실기기 확인은 14가 머지된 뒤에만 한다.**
- 서버 계약(API 설계 §3.3 · §3.6 · §3.7)은 백엔드 작업이 동시에 만든다. 백엔드 골든이 나오기 전에는 설계의 모양대로 손으로 쓴 픽스처로 개발하고, 백엔드가 머지되면 골든을 그것으로 바꾼다. 백엔드가 먼저 머지된다.
- 자격증명 입력값 다루기(§5)를 지킨다. 앱키 · 시크릿은 컴포넌트 `useState`에만 두고 컨텍스트 · 네비게이션 파라미터 · `kvStore` · 쿼리 키 · mutation `variables`에 두지 않는다. 이 기능의 코드는 `console.*`를 부르지 않는다. 테스트는 `test-app-key` · `test-app-secret` · `00000000-01` 꼴만 쓴다.
- 끝에 `npx jest`와 `npx tsc --noEmit`이 통과해야 한다. 둘은 묻지 않고 돌린다.
- `src/envelope/notices.ts`는 "미국 종목의 가격 기준일 안내"(03) 작업도 고친다(main에 이미 들어가 있다). 나중에 머지하는 쪽이 최신 origin/main에 맞춰 리베이스한다.

## Review Focus

1. **카드 버튼이 갱신할 수 없는 계좌를 폼으로 보내지 않는다** — `account_ids`가 하나여도 그 계좌의 `account_number_masked`가 없으면 `account-link`로 간다. → Task 5 `가린_계좌번호가_없으면_목록으로_간다`.
2. **갱신 폼이 계좌번호를 입력받지 않는다** — 계좌번호 · 실전/모의는 읽기 전용, 요청 본문은 `app_key` · `app_secret` · `label` 셋뿐. → Task 7 `요청_본문은_세_필드뿐이다`.
3. **입력값 누출** — 갱신 성공 · 실패 뒤 query · mutation 캐시 · 네비게이션 상태 · `console` · 렌더 트리에 가짜 키가 없다. → Task 8.
4. **배지 우선순위** — 인증 실패만 `인증 실패 · MM-DD 기준`, 연속 실패는 날짜 배지 그대로. → Task 4.
5. **점** — `CREDENTIAL_UPDATED`만 있으면 꺼지고, 이월이면 이월로 켜진다. → Task 4.

---

## 파일 구조

**front-end** (`.worktrees/front-end-credential-refresh`, 브랜치 `feat/credential-refresh-screen`)

| 파일 | 책임 |
|---|---|
| `src/api/types.ts` | `CollectionAlert` · `LinkedAccount`와 `AccountRowData`의 새 필드 · `UpdateCredentialsRequest` |
| `src/api/endpoints.ts` | `updateAccountCredentials(accountId, body)` |
| `src/fixtures/accountLinks.ts` · `src/fixtures/golden/accounts.json`(사본) | 상태 줄 일곱 줄 · 수집 안내 셋 |
| `src/format/date.ts` | `formatPickup` — `MM-DD(요일) HH:mm` |
| `src/screens/accountLink/linkStatus.ts` | 상태 줄 표 |
| `src/screens/accounts/StateBadge.tsx` · `tabDot.ts` | 배지 · 점 |
| `src/envelope/notices.ts` | 세 code의 자리 |
| `src/screens/accounts/CollectionAlertCards.tsx` · `AccountsScreen.tsx` | 계좌 탭 수집 안내 카드 |
| `src/screens/accountLink/LinkedAccountRow.tsx` · `AccountLinkScreen.tsx` | `갱신` 버튼 |
| `src/screens/accountLink/form.ts` | 등록 · 갱신이 함께 쓰는 검사, 갱신 폼 상태 |
| `src/screens/accountLink/CredentialRefreshScreen.tsx` | 갱신 폼 화면 |
| `src/app/navigation/types.ts` · `RootStack.tsx` | `account-link/credentials` 경로 |

---

### Task 0: 작업 공간

**Files:** 없음(머신 상태 변경)

- [ ] **Step 1: 아래 명령을 사용자에게 보여 주고 승인받은 뒤 실행한다.**

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project
git -C front-end fetch origin
git -C front-end worktree add -b feat/credential-refresh-screen ../.worktrees/front-end-credential-refresh origin/main
cd .worktrees/front-end-credential-refresh && npm ci
```

- [ ] **Step 2: 기준선.** `npx jest && npx tsc --noEmit`. Expected: 통과.

---

### Task 1: 타입 · 엔드포인트 · 픽스처

**Files:**
- Modify: `src/api/types.ts` · `src/api/endpoints.ts` · `src/fixtures/accountLinks.ts`
- Create: `src/fixtures/golden/accounts-collection-alerts.json`(골든 `accounts.json`의 사본에 행 `collection_alert`와 notice 셋을 더한 것) · 빈 봉투 사본
- Test: `src/__tests__/accountLinkApi.test.tsx`

- [ ] **Step 1: 실패하는 테스트.** `updateAccountCredentials('id-1', body)`가 `PUT /accounts/id-1/credentials`에 본문 세 필드를 보내고 `204`를 받아 끝난다(`serveRoutes`). `204`의 빈 본문을 JSON으로 읽지 않는다.
- [ ] **Step 2: 구현.** 타입은 §6.1 그대로. `AccountRowData`에 `collection_alert: CollectionAlert | null`. `client.ts`의 `apiPut`을 쓰고, `204` 빈 본문을 다루는지 먼저 본다(`apiDelete`처럼 `void`로 받는다).
- [ ] **Step 3: 픽스처.**
  - `accountLinks.ts`는 §3.1 표의 일곱 줄을 담는다. `account_number_masked`는 값과 `null`을 하나 이상씩, `env`는 `REAL` · `DEMO` · `null`을 하나 이상씩 담는다. `AccountListResponse`로 받아 `tsc`가 모양을 본다.
  - 수집 안내 사본의 notice 문장 · `params`는 API 설계 §3.7 표를 따른다. 머리에 "백엔드 골든이 이 모양으로 나오면 그것으로 바꾼다"를 주석이 아니라 테스트 파일 쪽 설명으로 둔다(JSON에는 주석이 없다).
- [ ] **Step 4: 통과 확인.** `npx jest src/__tests__/accountLinkApi.test.tsx && npx tsc --noEmit`.
- [ ] **Step 5: 커밋(요청 시).** `feat: 인증 정보 갱신 요청과 수집 안내 타입을 더한다`

---

### Task 2: 다음 수집 시각 표기

**Files:**
- Modify: `src/format/date.ts`
- Test: `src/__tests__/format.test.ts`

- [ ] **Step 1: 실패하는 테스트.** `formatPickup('2026-11-13T23:00:00+09:00')` → `11-13(목) 23:00`. `null` · 빈 값 → 빈 문자열. 기기 시간대와 무관하다(서버 문자열의 날짜 · 시각을 그대로 쓰고, 요일은 그 날짜로 구한다).
- [ ] **Step 2: 구현 → 통과 확인.** 기존 `formatMonthDayTime`처럼 글자를 자르고, 요일만 `Date.UTC(y, m - 1, d)`의 `getUTCDay()`로 구한다.
- [ ] **Step 3: 커밋(요청 시).** `feat: 다음 수집 시각을 요일과 함께 적는다`

---

### Task 3: 연동 목록 상태 줄

**Files:**
- Modify: `src/screens/accountLink/linkStatus.ts`
- Test: `src/__tests__/linkStatus.test.ts`

- [ ] **Step 1: 실패하는 테스트.** §3.1 표의 일곱 줄 전부와 색 · 모르는 `collection_alert.code`는 없는 것으로 본다 · 모르는 `state` · 모르는 `link_state`.
- [ ] **Step 2: 구현.** `collection_alert.code`를 먼저 보고, 없으면 지금의 `link_state` × `last_collection.state` 분기로 간다. 함수 주석: "서버가 판정한 수집 안내가 먼저이고, 없으면 연동 상태와 최근 수집으로 고른다".
- [ ] **Step 3: 통과 확인 → 커밋(요청 시).** `feat: 연동 목록 상태 줄에 인증 실패 · 연속 실패 · 갱신 뒤 확인 대기를 보인다`

---

### Task 4: 계좌 행 배지와 계좌 탭 점

**Files:**
- Modify: `src/screens/accounts/StateBadge.tsx` · `src/screens/accounts/tabDot.ts`
- Test: `src/__tests__/accountTabDot.test.tsx` · 배지 테스트(없으면 `src/__tests__/stateBadge.test.ts`를 만든다)

- [ ] **Step 1: 실패하는 테스트.**
  - `badgeLabelOf`: §3.7 표 네 줄(`인증 실패 · 07-24 기준` · `인증 실패` · `07-24 기준` · 연동 상태).
  - `accountTabNeedsLook`: `STALE_ACCOUNTS` · `CREDENTIAL_INVALID` · `REPEATED_FAILURE` 중 하나면 참, `CREDENTIAL_UPDATED`만 있으면 거짓, 둘 다 있으면 참.
- [ ] **Step 2: 구현 → 통과 확인.** 점 주석: "낡은 계좌나 손봐야 할 계좌가 있으면 켠다. 갱신하고 다음 수집을 기다리는 것은 사용자가 이미 조치한 것이라 켜지 않는다".
- [ ] **Step 3: 커밋(요청 시).** `feat: 인증 실패 배지와 수집 안내로 켜지는 계좌 탭 점`

---

### Task 5: 계좌 탭 수집 안내 카드

**Files:**
- Modify: `src/envelope/notices.ts` · `src/screens/accounts/AccountsScreen.tsx`
- Create: `src/screens/accounts/CollectionAlertCards.tsx`
- Test: `src/__tests__/collectionAlertCards.test.tsx`(새 파일) · `src/__tests__/notices.test.ts`

- [ ] **Step 1: 실패하는 테스트.**
  - notice 자리: 세 code가 `SCREEN_PLACED`에 있고 `BY_SCREEN.accounts`에만 있다 · 계좌별 화면의 캡션 · 줄에 나오지 않는다 · 다른 화면은 버린다.
  - 카드: 세 code의 색 · 서버 `message` 그대로 · 버튼 유무 · 서버 순서로 쌓인다 · 목록 맨 위(합계 줄 위)에 있다 · `NO_HOLDINGS` 빈 상태 위에도 있다.
  - 버튼: `account_ids`가 하나이고 `['account-links']`의 그 계좌에 `account_number_masked`가 있으면 `account-link/credentials`(`{ accountId }`), 하나인데 가린 번호가 없으면 `account-link`(`가린_계좌번호가_없으면_목록으로_간다`), 여럿이면 `account-link`.
- [ ] **Step 2: 구현.** 카드는 `notices`에서 세 code만 골라 그린다. 버튼을 눌렀을 때 `['account-links']`가 캐시에 없으면 받아 온 뒤 정한다(받는 동안 버튼 로딩). 문구를 앱에서 조립하지 않는다. `notices.ts`의 `SCREEN_PLACED` 주석에 "수집 안내 셋은 계좌 탭의 수집 안내 카드가 그린다"를 더한다.
- [ ] **Step 3: 통과 확인 → 커밋(요청 시).** `feat: 계좌 탭 맨 위에 수집 안내 카드를 그린다`

---

### Task 6: 연동 목록의 `갱신`과 경로

**Files:**
- Modify: `src/screens/accountLink/LinkedAccountRow.tsx` · `src/screens/accountLink/AccountLinkScreen.tsx` · `src/app/navigation/types.ts` · `src/app/navigation/RootStack.tsx`
- Test: `src/__tests__/accountLink.test.tsx`

- [ ] **Step 1: 실패하는 테스트.** `account_number_masked`가 있는 행에만 `갱신`이 있다(접근성 라벨 `{라벨} 인증 정보 갱신`) · 누르면 `account-link/credentials`에 `{ accountId }` · 헤더 `인증 정보 갱신`.
- [ ] **Step 2: 구현.** 경로 타입 `'account-link/credentials': { accountId: string }` 주석: "인증 정보 갱신 폼. 계좌 id만 넘긴다 — 자격증명이 아니다". 첫 줄은 `라벨 · 갱신 · 해제`.
- [ ] **Step 3: 통과 확인 → 커밋(요청 시).** `feat: 연동 목록에서 인증 정보 갱신으로 들어간다`

---

### Task 7: 갱신 폼 화면

**Files:**
- Modify: `src/screens/accountLink/form.ts` · `src/screens/accountLink/AccountLinkFormScreen.tsx`(공유 칸으로 바꾸는 만큼만) · `src/api/queries/accountLinkInvalidation.ts`(그대로 쓰면 변경 없음)
- Create: `src/screens/accountLink/CredentialRefreshScreen.tsx`
- Test: `src/__tests__/credentialRefreshScreen.test.tsx`(새 파일) · `src/__tests__/accountLinkFormScreen.test.tsx`(공유로 바꾼 뒤에도 통과)

- [ ] **Step 1: 실패하는 단위 테스트(`form.ts`).** 갱신 폼 검사는 앱키 · 시크릿 · 라벨만 보고 등록과 같은 문구다 · 계좌번호를 보지 않는다 · 요청 본문 만들기가 공백을 지운 세 필드만 낸다(`요청_본문은_세_필드뿐이다`). 등록 검사(`validateLinkForm`)는 이 공유 검사를 써서 지금 결과 그대로다.
- [ ] **Step 2: 실패하는 화면 테스트.**
  - 칸: 앱키 · 시크릿 빈 칸 · 계좌번호 `****5678-01` 읽기 전용 · 실전/모의 읽기 전용(`env` null이면 줄 없음) · 라벨은 지금 값으로 채운 입력 칸 · 칸 아래 `갱신한 키는 다음 수집에서 확인돼요` · `http` 주소면 경고.
  - 가린 계좌번호가 없는 계좌: 폼 대신 `이 계좌는 아직 인증 정보를 갱신할 수 없어요`와 뒤로 가기.
  - 캐시에 없는 계좌: `['account-links']`를 받아 찾고, 없으면 `계좌를 찾을 수 없어요`.
  - 제출: 클라이언트 검사 문구 · 두 번 보내지 않음 · `204`면 `goBack()`과 `invalidateAccountLinkData` · 코드별 자리(§3.8 표: 폼 위 한 줄 / `403` · `409 ACCOUNT_DISCONNECTED`는 닫고 무효화) · 네트워크 오류 문구 · 실패 시 시크릿만 비움 · 보내는 동안 떠나면 화면에 반영하지 않되 성공이면 무효화.
- [ ] **Step 3: 구현.** 앱키 · 시크릿 칸은 등록 폼의 `TextField` 설정(§5.3)을 그대로 쓴다. 제출 핸들러가 `updateAccountCredentials`를 직접 부르고 `useMutation`을 쓰지 않는다(등록과 같다).
- [ ] **Step 4: 통과 확인 → 커밋(요청 시).** `feat: 인증 정보 갱신 폼 화면`

---

### Task 8: 누출 검사와 마무리

**Files:**
- Test: `src/__tests__/accountLinkFlow.test.tsx`(있는 누출 검사에 갱신 경로를 더한다)

- [ ] **Step 1: 테스트.** 갱신 성공 뒤와 실패(`503`) 뒤 각각: query 캐시 · mutation 캐시 · 네비게이션 루트 상태를 문자열로 바꿔도 가짜 앱키 · 시크릿이 없다 · `console.log` · `info` · `warn` · `error` · `debug`가 그 값으로 불리지 않는다 · 성공 뒤 렌더 트리에 값이 없다.
- [ ] **Step 2: 흐름 테스트.** 카드 `인증 정보 갱신` → 폼 → `204` → 계좌 탭으로 돌아와 카드가 `CREDENTIAL_UPDATED` 사본으로 바뀌어 보인다(무효화 뒤 다시 받은 응답을 그 사본으로 준다).
- [ ] **Step 3: 전체 확인.** `npx jest && npx tsc --noEmit`. Expected: 통과.
- [ ] **Step 4: 머지 직전.** 백엔드가 먼저 머지된 것을 확인하고, 백엔드 골든 `accounts.json`(행의 `collection_alert`)을 앱 골든에 반영한 뒤, 손으로 쓴 수집 안내 사본의 모양이 백엔드 응답과 같은지 본다. 다르면 멈추고 보고한다. 14가 머지됐으면 그 위로 리베이스하고 `npm ci` 뒤 다시 돌린다.
- [ ] **Step 5: 수동 확인(14 머지 뒤, 승인 후).** 로컬 백엔드를 `portfolio.credentials.store=memory`로 띄우고 가짜 키로 등록 → 갱신 → 해제를 한 번씩 해 본다. 서버 · 개발 서버를 띄우는 일이라 그때 승인을 받는다. 운영 서버에 실제 키를 넣지 않는다.
- [ ] **Step 6: 보고.** 바뀐 파일 · 테스트 결과 · 남은 것 · 영향받는 통합테스트 동작.

---

## 데이터팀 코드

앱은 실패 코드를 읽지 않는다. 서버가 판정한 `collection_alert.code`와 notice만 그린다. 데이터가 인증 실패 코드를 더 주어도 앱은 바뀌지 않는다.
