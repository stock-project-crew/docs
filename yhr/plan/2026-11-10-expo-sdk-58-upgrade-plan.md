# Expo SDK 58 업그레이드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기능을 바꾸지 않고 앱을 Expo SDK 58로 올려, App Store판 Expo Go(58.0.5, SDK 58만 지원)에서 실기기로 열리게 한다.

**Architecture:** 코드 구조는 그대로 둔다. `npx expo install expo@^58.0.0 --fix`로 SDK 58이 정한 버전표에 패키지를 맞추고, 그 결과로 깨지는 타입 · 설정 · 테스트만 최소로 고친다. 중간 SDK(55 · 56 · 57)는 거치지 않는다. 그 버전의 Expo Go가 스토어에 없어 실기기 확인을 할 수 없고, `--fix`는 목표 SDK의 버전표만 보기 때문이다. 원인을 가를 수 없는 실패가 나오면 그때 한 단계씩 나눠 올린다.

**Tech Stack:** React Native 0.88 · Expo SDK 58 · React 19.3 · TypeScript 6.0 · React Navigation 7 · TanStack Query 5 · expo-notifications · expo-secure-store · jest-expo 58 · React Native Testing Library 14

**근거:** Expo 공식 업그레이드 안내 [SDK 55](https://expo.dev/changelog/sdk-55) · [SDK 56](https://expo.dev/changelog/sdk-56) · [SDK 57](https://expo.dev/changelog/sdk-57) · [SDK 58](https://expo.dev/changelog/sdk-58), `expo/expo` 저장소 `sdk-58` 브랜치의 `packages/expo/bundledNativeModules.json`.

## Global Constraints

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어. 커밋 접두어 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **커밋 · 푸시는 사용자가 요청할 때만 한다.**
- 작업 위치는 `.worktrees/front-end-sdk58`(브랜치 `chore/expo-sdk-58`)다. `front-end` 본 트리는 건드리지 않는다.
- **패키지 버전을 손으로 고르지 않는다.** `npx expo install`과 `npx expo install --fix`만 쓴다. SDK 버전표에 없는 패키지가 어긋나면 고르지 말고 보고한다.
- **기능 · 화면 · 문구를 바꾸지 않는다.** 업그레이드로 동작이 달라지면 고치기 전에 멈추고 보고한다.
- 개발 빌드(EAS Build · Xcode)로 가지 않는다. 필요해 보이면 이유와 함께 보고한다.
- iOS 날짜 칸(`src/ui/DateField.tsx`)의 동작을 바꾸지 않는다. datetimepicker 9로 동작이 달라지면 보고한다.
- 실기기에서 **알림을 저장하거나 알림 권한 창에 답하지 않는다.** 통합테스트 AL1-14가 "권한이 아직 정해지지 않은" 상태를 쓴다.
- Metro를 공인 IP로 여는 일은 승인을 받고, 끝나면 바로 닫는다.
- 각 태스크는 `npx jest`와 `npx tsc --noEmit`이 통과해야 다음으로 간다. 둘은 DB를 쓰지 않으므로 묻지 않고 돌린다.
- 주석은 히스토리 없이 최신 사실만 쓰고, 문서 절 번호를 지칭하지 않는다. 검증하지 않은 것은 단정하지 않는다.
- 통합테스트 문서(`docs/yhr/test/`)는 고치지 않는다. 영향받는 케이스 ID와 바뀐 동작만 보고한다.

## Review Focus

1. **iOS 날짜 칸** — datetimepicker가 8.4.4에서 9.2.1로 바뀐다. 깨지는 변경으로 표시된 것은 Android의 `positiveButtonLabel` · `negativeButtonLabel` · `neutralButtonLabel` 삭제뿐이고 앱은 쓰지 않는다. iOS에는 "재활용될 때 내부 선택 상태가 남는 문제" 수정이 들어 있다. → Task 3 · Task 6에서 동작을 본다. 달라지면 보고만 한다.
2. **앞화면 알림 배너 억제** — SDK 58의 expo-notifications는 "핸들러가 따로 말하지 않으면 앞화면 알림을 보인다"로 기본값이 바뀌었다. `src/push/notifications.ts`의 핸들러가 `shouldShowBanner` · `shouldShowList`를 `false`로 명시하므로 동작은 그대로여야 한다. → Task 3에서 핸들러 테스트가 통과하는지 본다.
3. **웹 번들** — `expo` 58은 `@expo/metro-runtime`을 peer로 요구한다. 지금은 따로 설치돼 있지 않다. → Task 1 · Task 4에서 `expo install`이나 `expo-doctor`가 요구하면 `npx expo install @expo/metro-runtime`으로 넣고, Task 5에서 웹이 뜨는지 본다.
4. **TypeScript 6** — SDK 56부터 TypeScript가 6.0으로 오른다. `tsconfig.json`의 `baseUrl` · `paths`(`@/` 별칭)와 jest 전역 타입이 그대로 잡히는지, RN 0.87부터 바뀐 ref 타입(`useRef<TextInput>` 등)이 통과하는지 본다. → Task 2.
5. **첫 실행에서만 나는 jest 흔들림** — SDK 54 기준선에서 캐시가 없는 첫 실행에서만 3건이 실패하고 이어진 네 번은 모두 통과했다. 실패 내용은 기록하지 못했다. → Task 1에서 캐시를 지운 첫 실행을 `--json`으로 남겨 같은 현상인지 가른다.

---

## 파일 구조

**front-end** (`.worktrees/front-end-sdk58`, 브랜치 `chore/expo-sdk-58`)

| 파일 | 바뀌는 까닭 |
|---|---|
| `package.json` · `package-lock.json` | `expo install --fix`가 SDK 58 버전표로 맞춘다 |
| `tsconfig.json` | TypeScript 6에서 깨지는 설정이 있을 때만 |
| `app.json` | `expo-doctor`가 SDK 58에서 지원하지 않는 설정을 지적할 때만 |
| `src/**` | RN 0.88 · React 19.3 타입 오류가 날 때 그 자리만 |
| `jest.config.js` · `jest.setup.js` | jest-expo 58 preset 변화로 필요할 때만 |

**docs** — Task 7에서 승인받은 목록만

| 파일 | 고칠 곳 |
|---|---|
| `yhr/guide/2026-10-17-app-run-guide.md` | 준비물의 Expo Go · SDK 문장 |
| `yhr/plan/2026-08-17-frontend-portfolio-app-plan.md` 외 SDK 54를 적은 계획서 | Tech Stack 줄, "SDK 54를 올리지 않는다" 규칙, SDK 54 기준의 설치 안내 |

---

## 기준선 (SDK 54)

`e1dfa6f`에서 `npm ci` 직후 잰 값이다.

| 항목 | 결과 |
|---|---|
| 조합 | expo 54.0.36 · react-native 0.81.5 · react 19.1.0 · jest-expo 54.0.17 · datetimepicker 8.4.4 · Node v26.4.0 · npm 11.17.0 |
| `npx jest` | 657 통과 · 1 건너뜀(`fixtureKeys`) · 스냅샷 0. 캐시가 없는 첫 실행만 3건 실패 |
| `npx tsc --noEmit` | 오류 없음 |
| `npx expo-doctor` | 2건 실패. 하나는 `expo`(~54.0.37) · `jest-expo`(~54.0.18) 패치 어긋남 |

## SDK 58 목표 조합

`bundledNativeModules.json`(sdk-58)과 SDK 58 템플릿 기준이다. 최종 값은 `expo install --fix`가 정한다.

| 패키지 | SDK 54 | SDK 58 |
|---|---|---|
| expo | 54.0.36 | 58.0.x |
| react-native | 0.81.5 | 0.88.1 |
| react · react-dom | 19.1.0 | 19.3.0 |
| @types/react | ~19.1.10 | ~19.3.0 |
| typescript | ~5.9.2 | ~6.0.3 |
| jest-expo | ~54.0.17 | ~58.0.14 |
| expo-notifications | ~0.32.17 | ~58.1.8 |
| expo-asset · constants · font · linear-gradient · secure-store · status-bar | 12 ~ 18 | ~58.0.x |
| @react-native-community/datetimepicker | 8.4.4 | 9.2.1 |
| react-native-screens | ~4.16.0 | ~4.30.1 |
| react-native-safe-area-context | ~5.6.0 | ~5.11.1 |
| react-native-web | ^0.21.2 | ~0.21.4 |
| @expo/vector-icons | ^15.0.3 | ^15.0.2 |

React Navigation 7 · TanStack Query 5 · RNTL 14는 SDK 버전표에 없다. peer 요구(`react >= 18.2` · `>= 19`)가 React 19.3을 받아들이므로 그대로 둔다.

---

### Task 1: SDK 58로 패키지를 맞춘다

- [ ] **Step 1: 버전표에 맞춘다**

```bash
cd .worktrees/front-end-sdk58
npx expo install expo@^58.0.0 --fix
```

출력과 `git diff package.json`을 기록한다. 버전표에 없는 패키지에 대한 경고나 peer 충돌이 나오면 멈추고 보고한다.

- [ ] **Step 2: 남은 어긋남을 맞춘다**

```bash
npx expo install --fix
npx expo install --check
```

기대: `Dependencies are up to date`. `@expo/metro-runtime`을 요구하면 `npx expo install @expo/metro-runtime`으로 넣는다.

- [ ] **Step 3: 캐시를 지운 첫 실행을 기록한다**

```bash
npx jest --clearCache
npx jest --json --outputFile=<스크래치>/sdk58-first.json
npx jest
npx tsc --noEmit
```

실패를 원인별로 나눈다: (a) 타입 · 설정 → Task 2, (b) 테스트 렌더러 · preset → Task 3, (c) 첫 실행 흔들림 → 두 번째 실행에서 사라지는지로 가른다.

### Task 2: TypeScript 6과 RN 0.88 타입 오류를 고친다

- [ ] **Step 1: 오류를 모은다** — `npx tsc --noEmit` 출력을 파일별로 묶는다.
- [ ] **Step 2: 설정 오류를 고친다** — `baseUrl` 지원 중단, `types` 기본값 변화처럼 `tsconfig.json`으로 풀리는 것은 `tsconfig.json`에서 고친다. `ignoreDeprecations`로 덮지 않는다.
- [ ] **Step 3: 코드 타입 오류를 고친다** — ref 타입처럼 RN 0.88의 엄격한 타입 API에서 나는 오류는 그 자리만 고친다. 런타임 동작이 바뀌는 수정이 필요하면 멈추고 보고한다. `react-native-legacy-deep-imports` 같은 임시 우회는 쓰지 않는다.
- [ ] **Step 4: 확인** — `npx tsc --noEmit` 오류 0, `npx jest` 통과.

### Task 3: jest 실패와 골든 차이를 하나씩 확인한다

- [ ] **Step 1: 실패를 목록으로 만든다** — 실패마다 테스트 이름, 기대와 실제, 원인을 적는다.
- [ ] **Step 2: 원인을 가른다**
  - 테스트 도구 쪽(jest-expo 58 preset, 렌더러, 모의 객체 모양)이면 테스트 설정이나 대역을 고친다. 단언은 바꾸지 않는다.
  - 화면 · 문구 · 동작이 실제로 달라진 것이면 **멈추고 보고한다.**
- [ ] **Step 3: Review Focus 1 · 2를 본다** — `DateField` 테스트와 알림 핸들러 테스트가 단언을 바꾸지 않고 통과하는지 확인한다.
- [ ] **Step 4: 확인** — `npx jest`가 기준선과 같은 657 통과 · 1 건너뜀이고, `npx tsc --noEmit`이 통과한다. 건수가 달라지면 까닭을 적는다.

### Task 4: `expo-doctor` 경고를 0으로 만든다

- [ ] **Step 1:** `npx expo-doctor`
- [ ] **Step 2:** 지적마다 고친다. 버전 어긋남은 `npx expo install --fix`로, `app.json`의 지원하지 않는 설정은 SDK 58 안내에 따라 지운다. 앱 동작에 닿는 설정이면 보고하고 결정을 받는다.
- [ ] **Step 3: 확인** — `npx expo-doctor`가 모든 점검을 통과하고, `npx jest` · `npx tsc --noEmit`도 통과한다.

### Task 5: 웹에서 확인한다

전제: 로컬 백엔드가 `localhost:8080`에서 떠 있다. 떠 있지 않으면 사용자에게 기동을 부탁한다.

- [ ] **Step 1:** 본 트리 `front-end/.env`를 worktree로 복사한다. 이 파일은 git이 추적하지 않는다. 그 뒤 `npx expo start --web`으로 `localhost:8081`을 연다.
- [ ] **Step 2:** 로그인 → 요약 · 종목 · 비중 · 계좌 · 손익 · 알림 탭을 차례로 열고, 탭마다 콘솔 오류와 실패한 네트워크 요청을 기록한다. 알림을 저장하지 않는다.
- [ ] **Step 3:** SDK 54(`front-end` 본 트리)와 같은 화면인지 눈으로 비교한다. 달라진 곳은 스크린샷으로 남겨 보고한다.
- [ ] **Step 4:** Metro를 끈다.

### Task 6: 실기기에서 확인한다

- [ ] **Step 1:** 공인 IP로 Metro를 여는 방법(호스트 이름과 포트 개방)을 사용자에게 설명하고 승인을 받는다.
- [ ] **Step 2:** 사용자에게 Expo Go 58로 접속을 부탁한다. 로그인과 각 탭 이동까지만 본다. **알림 권한 창이 뜨면 답하지 않고 닫지도 않는다.** 권한 확인과 푸시 확인은 테스트 트랙이 한다.
- [ ] **Step 3:** 날짜 칸이 있는 화면은 열어 보기만 하고 저장하지 않는다. SDK 54와 달라 보이면 보고한다.
- [ ] **Step 4:** Metro와 포트 개방을 바로 닫는다. 닫은 것을 확인한다.

### Task 7: SDK 54를 전제로 적은 문서를 고친다

- [ ] **Step 1:** `docs/yhr/`에서 `docs/yhr/test/`를 뺀 범위에 `SDK 54` · `Expo Go 상한` · `올리지 않는다`를 검색해 고칠 목록과 바꿀 문구를 표로 보여 주고 승인을 받는다. 그 문장을 참조하는 절도 함께 올린다.
- [ ] **Step 2:** 승인받은 문구로 고친다. 히스토리를 남기지 않고 원래 그랬던 것처럼 쓴다.

### Task 8: 머지 직전에 다시 확인한다

- [ ] **Step 1:** `git fetch` 후 최신 `origin/main`에 리베이스한다. `package-lock.json`이 충돌하면 `package.json`을 먼저 정리하고 `npx expo install --fix`로 lock을 다시 만든다.
- [ ] **Step 2:** `npm ci` → `npx jest` → `npx tsc --noEmit` → `npx expo-doctor` → Task 5 웹 확인을 다시 한다.
- [ ] **Step 3:** 사용자가 요청하면 커밋한다. 다른 앱 작업(07 · 08 · 12 · 13)은 이 브랜치가 머지된 뒤 최신 main에 리베이스하고 `npm ci`로 다시 설치해야 한다는 점을 함께 알린다.

---

## 완료 보고

- 올린 뒤의 조합(`expo` · `react-native` · `react` · `jest-expo`와 바뀐 라이브러리)
- 바뀐 파일, `npx jest` · `npx tsc --noEmit` 결과, `npx expo-doctor` 결과
- 웹 · 실기기 확인 결과
- 동작이 달라진 곳과 영향받는 통합테스트 케이스 ID. 실기기 케이스 AL1-14 · AL1-13 · AL3-04 ~ AL3-07 · AL7-02 ⑤ · C2-08이 다시 열리는지 포함
