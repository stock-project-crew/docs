# 매수·매도 타이밍 알림 — 프론트엔드 구현 계획 ③ (알림 탭과 새 알림 흐름)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

- **작성일**: 2026-10-11
- **대상 저장소**: `front-end/` (Task 1~14) · `back-end/` (Task 0, 격리 worktree에서만)
- **근거 스펙**: [`2026-07-12-buy-sell-timing-alert-spec.md`](../specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md) — 특히 §11 API 계약 · §12 화면 · §15 화면 상태 전수
- **정보 구조**: [`app-information-architecture.md`](../specs/app-information-architecture.md) — 6탭 · 화면 목록 · 배지 · 푸시를 눌렀을 때 · 첫 화면 · 공통 이름
- **와이어플로우**: [`wireflow.png`](../specs/buy-sell-timing-alert/wireflow.png)
- **이어지는 계획**: ① 규칙과 조회 API([`2026-10-11-alert-backend-rules-plan.md`](./2026-10-11-alert-backend-rules-plan.md), back-end main에 있음) · ② 평가·발송·울린 알림 API(다른 세션이 진행 중)

**Goal:** 6번째 탭 `알림`과 그 아래 화면들(알림 상세 · 울린 알림 · 울린 알림 상세 · 새 알림 흐름 다섯 단계)이 ①의 실제 API와 ②의 계약(§11)으로 동작하고, iOS에서 푸시 권한·기기 등록·푸시를 눌러 여는 길이 선다.

**Architecture:** 기존 front-end 관례를 그대로 쓴다 — 서버 상태는 TanStack Query, 화면 이동은 React Navigation(native-stack + bottom-tabs), 색은 `useTheme()` 토큰, 봉투는 `ScreenFrame`. 알림 목록·울린 알림 목록은 포트폴리오와 같은 봉투라 `envelope/`를 넓혀 재사용한다. 새 알림 흐름은 루트 스택 위의 모달 안에 중첩 스택으로 두고, 작성 중인 초안은 그 모달 범위의 Context + `useReducer`에 둔다(앱 전역 상태는 지금처럼 인증 하나뿐이다). 문장·현재값·검증 오류는 모두 서버의 미리보기 응답에서 받고, 프론트는 초안 ↔ 요청 JSON 변환과 입력 칸 규칙만 순수 함수로 갖는다.

**Tech Stack:** React Native 0.81.5 · Expo SDK 54 · React 19.1 · TypeScript 5.9(strict) · React Navigation 7 · TanStack Query v5 · expo-secure-store · expo-notifications · expo-constants · Jest(jest-expo) + React Native Testing Library 14. 백엔드(Task 0): Spring Boot · MyBatis · JUnit 5.

**Spec:** `docs/yhr/specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md` · `docs/yhr/specs/app-information-architecture.md`

## Global Constraints

- **Expo SDK 54 고정.** App Store판 Expo Go가 54까지만 받는다. 패키지는 항상 `npx expo install <pkg>`로 넣는다.
- **설치 · 서버 기동 · 푸시 발송 · 병합 · DB 쓰기는 먼저 사용자 승인을 받는다.** 이 계획에서 해당하는 단계에는 `⛔ 승인` 표시가 있다. 승인 없이 넘어가지 않는다.
- **백엔드 코드는 격리 worktree에서만 고친다.** `back-end/` 원래 경로에서는 다른 세션(계획 ②)이 작업 중이다. Task 0은 `superpowers:using-git-worktrees`로 만든 worktree에서 하고, main 병합은 승인을 받는다.
- **front-end는 `feat/alert-tab` 브랜치에서 한다.** 계획 ②는 front-end를 건드리지 않는다.
- **원격 푸시는 iOS만.** Expo Go Android는 SDK 53부터 원격 푸시가 없다(§9.6). Android는 토큰을 등록하지 않고 알림 탭에 `Android에서는 앱 안에서만 알림을 확인할 수 있어요`를 띄운다.
- **서버가 완성한 문장은 그대로 낸다.** `summary.short` · `summary.sentence` · `current.header` · `current.result_text` · `current.conditions[].text` · 발화 `title` · `body` · `lines` · notice `message` · 오류 `message` · `fields[].message`. 프론트가 조건 문장을 만들지 않는다(§12.1).
- **색 리터럴은 `src/design/theme.ts`에만 적는다.** 배지 전용 색은 `badge: '#7C3AED'`(보라)이고 증감색(빨강·파랑)·상태 배지색(초록·노랑·회색)과 겹치지 않는다(§12.6).
- **숫자·날짜 문자열은 `src/format/`을 거친다.** `Intl`·`toLocaleString`을 쓰지 않는다. 서버 시각은 `+09:00` 오프셋 문자열을 글자 그대로 잘라 쓴다.
- **응답 타입의 필드 이름은 서버 그대로 snake_case.**
- **화면 문구는 스펙 §12.7 표의 글자 그대로.** 탭 라벨 `알림`, 헤더 이름은 IA §6.1 표를 따른다.
- **자격증명을 코드·로그·저장소에 넣지 않는다.** Expo 푸시 토큰을 로그에 남기지 않는다. EAS `projectId`는 비밀이 아니라 `app.json`에 들어간다(사용자가 `eas init`으로 만든다).
- **주석과 문서에는 최신 사실만.** "이전에는 ~했다" 같은 경과를 적지 않는다. 검증하지 않은 것을 단정하지 않는다.
- **커밋은 Conventional Commits, 태스크마다 1커밋.** 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`를 붙인다.
- **`docs/hhj` · `docs/jdh` · `docs/team-architecture-agreement.md`는 근거로 인용하지 않는다.**

## Review Focus

1. **늦게 도착한 미리보기 응답이 새 입력의 결과를 덮는다** — 빠르게 고친 뒤 앞 요청이 늦게 오면 문장 상자가 옛 조건을 보여 준다. 미리보기는 요청 JSON을 쿼리 키로 갈라 마지막 입력의 응답만 그린다. → Task 3 `usePreview` 테스트.
2. **본문 없는 204 응답을 "연결에 실패했어요"로 보인다** — 끄기·다시 켜기·삭제가 204다. 지금 `request()`는 `json()` 실패를 `NetworkError`로 바꾼다. → Task 1 테스트.
3. **수정 왕복에서 조건이 바뀐다** — 상세의 `trigger_spec`을 초안으로 풀었다가 다시 요청으로 묶을 때 `indicator_params`가 생기거나, 손실 수익률의 부호가 뒤집히거나, 만료일이 하루 밀린다. → Task 8 왕복 테스트.
4. **미국 종가 기준일이 하루 밀린다** — 미국 종가의 `as_of`는 한국 시각으로 다음 날 새벽이다(`2026-09-27T05:00:00+09:00`). 글자를 그대로 자르면 `미국 9/27 종가`가 된다. → Task 4 테스트.
5. **계획 ②가 아직 없는 동안 알림 탭이 깨진다** — `/alert-events/unread-count`가 404면 탭 배지는 숨고, 알림 탭·알림 상세는 그대로 동작해야 한다. → Task 5 테스트.

---

# Part A — 배경

## A.1 도달점

웹(`http://localhost:8081`)과 iOS 실기기 Expo Go에서 아래가 된다.

```
 1. 아래 탭이 여섯 개다 — 요약 · 종목 · 비중 · 계좌 · 손익 · 알림
 2. 알림이 없으면 `아직 걸어 둔 알림이 없어요` + [＋ 첫 알림 만들기]
 3. ＋ 새 알림 → 대상 종목: 검색어가 없으면 보유 종목(가나다순), `삼성` 입력 0.3초 뒤 검색 결과
 4. 삼성전자 → 조건 선택: 직접 조건 만들기 + 프리셋 9종. 수급 프리셋은 미국 종목에서 `국내 종목만`
 5. 가격 도달 → 가격 칸이 직전 종가(63,010)로 채워지고 아래에 `9/25 종가 기준`
 6. 칸을 바꾸고 0.5초 뒤 문장 상자와 현재값 상자가 바뀐다
 7. 다음 → 공통 설정: `지금 이미 조건을 충족하고 있어 곧 알림이 와요`(충족 중이면)
 8. 저장 → (iOS, 권한 미정이면 안내 시트) → 알림 상세가 열리고 현재값 상자가 보인다
 9. 알림 상세의 감시 토글을 끄면 상태 배지가 `꺼짐`, 다시 켜면 `감시 중`
10. 수정 → 값이 채워진 프리셋 입력에서 시작, 종목은 바꿀 수 없다
11. 알림 삭제 → `이 알림을 삭제할까요? 울린 기록은 남아요` → 목록에서 사라진다
12. 직접 조건 만들기 → RSI(14) ≥ 70, 3일 연속 → 문장 `종가 기준으로 RSI(14)가 3일 연속 70 이상이면 알려요`
13. (계획 ② 이후) 울린 알림 전체 → 목록 · 모두 읽음 · 행 → 울린 알림 상세 · 탭 배지 숫자
14. (iOS, 계획 ② 이후) 푸시를 누르면 알림 탭 위에 울린 알림 상세가 열리고 뒤로 가면 알림 탭
```

## A.2 계획 ①의 실제 동작 (코드에서 확인한 것)

| 항목 | 실제 동작 |
|---|---|
| 미리보기 | 형 오류가 있어도 `200`. `valid:false` · `errors[]{path,code,message}`. 트리거가 컴파일되지 않으면 `summary`·`current`가 **null** |
| 저장 | `400` `{error:{code:'INVALID_ALERT', message:'조건을 확인해 주세요', fields:[…]}}`. 성공은 `201 {alert_id}`(만들기) · `200 {alert_id}`(수정) |
| 끄기 · 다시 켜기 · 삭제 | `204` 본문 없음. 다시 켜기는 만료된 알림에만 `{expires_at}`(null이면 무기한)가 필수, 없으면 `400` `fields[0].path = 'expires_at'` |
| 없는 것 · 남의 것 | `404` `ALERT_NOT_FOUND` · `DEVICE_NOT_FOUND`(메시지 `알림을 찾을 수 없어요` 등) |
| 카탈로그 | 지표에 `category`(`시세`·`기술지표`·`수급`·`내 보유`)와 `transform_ranges`(변형별 n 범위). 프리셋 `param_schema[]`는 `{key, kind: 'int'|'decimal'|'choice', min, max, default, choices, required}` |
| 수익률 도달 | 손실은 `pct`를 **음수**로 보낸다. 카탈로그 기본값은 `10` 하나 |
| RSI 구간 | 카탈로그 기본 `level`은 70. 과매도를 고르면 프론트가 30으로 바꾼다 |
| 시각 | 모든 시각이 `+09:00` 오프셋 |
| 수정 | 상세의 `trigger_spec`을 그대로 다시 보내도 된다(`lag`가 없다) |
| 알림 목록 봉투 | `as_of`는 평가된 알림이 없으면 null. `notices`는 ①에서 빈 배열(`MARKET_DATA_DELAYED`는 ②) |
| 검증 경로 | `name` · `cadence` · `notify_mode` · `cooldown_min` · `expires_at` · `instrument_id` · `trigger_spec.params.<key>` · `trigger_spec.conditions[i].left…` · `.op` · `.right…` · `.modifier…` |
| 로컬 CORS | `/alerts/**`(GET·POST·PUT·DELETE) · `/instruments`(GET) · `/devices/**`(POST·DELETE) |

## A.3 계획 ②에 기대는 것과 ②에 넘길 요청

이 계획의 울린 알림 화면들은 스펙 §11의 계약대로 만들고, 테스트는 그 계약 모양의 픽스처로 돈다. ②가 main에 들어오기 전에는 아래 경로가 404이며, 화면은 그때도 깨지지 않는다(Review Focus 5).

| 경로 | 쓰는 곳 |
|---|---|
| `GET /alert-events?alert_id=&cursor=&limit=` | 울린 알림 |
| `GET /alert-events/{id}` · `POST /alert-events/{id}/read` | 울린 알림 상세 |
| `POST /alert-events/read-all` | 울린 알림 `모두 읽음` |
| `GET /alert-events/unread-count` | 탭 배지 |
| `GET /alerts`의 `unread` · `last_fired_at` · `notices[MARKET_DATA_DELAYED]` | 알림 탭 |

로컬 CORS의 `/alert-events/**`(GET·POST)는 계획 ②의 Task 14가 연다.

**②에 넘길 요청** (이 계획의 실행자가 사용자에게 전달한다. ②의 파일을 직접 고치지 않는다)

- `GET /alert-events/{id}` 응답(②의 `EventDetailDto`)에 목록 행(`EventRowDto`)과 같은 `cadence` · `market`을 최상위에 싣는다. 지금 모양에는 `market`이 어디에도 없어(`EventInstrumentDto`는 `id` · `label`뿐) 미국 종목 발화의 기준 표기(`미국 9/26 종가 기준`)를 만들 수 없다. 프론트는 둘을 옵셔널로 받고, 없으면 `alert.cadence`와 국내 표기로 그린다.

## A.4 이 계획이 정하는 것

스펙과 IA가 구현 계획에 넘긴 것, 그리고 기존 코드에 관례가 없어 여기서 정한 것.

| 항목 | 결정 | 근거 |
|---|---|---|
| 앱 URL 스킴 (§9.3 · IA §4.1) | **두지 않는다.** 푸시 응답 리스너가 `data.event_id`를 받아 네비게이션으로 연다 | 푸시 말고 앱 밖에서 화면을 여는 길이 v1에 없다. 스킴은 외부 링크가 생길 때 정한다 |
| 초안 상태 | 모달 범위의 Context + `useReducer` | 앱 전역 상태는 인증 하나뿐인 관례. 흐름이 한 번의 저장으로 끝난다 |
| 배지 전용 색 | `badge: '#7C3AED'` | 사용자 결정. 증감색·상태 배지색과 겹치지 않는다 |
| 상태 배지 색 | 감시 중 초록 · 조건 충족 중 노랑 · 나머지 회색 | §12.6 |
| 직전 종가 | `GET /instruments` 행의 `last_close` · `last_close_on` (Task 0) | 사용자 결정. 미리보기는 가격이 비면 현재값을 계산하지 않는다 |
| `다음` · `저장` 버튼 | 화면 아래 고정 버튼 | 두 버튼이 같은 자리. 와이어플로우의 헤더 오른쪽 `다음`과 다르다 |
| 닫기 | 첫 단계 헤더 왼쪽 `닫기` + iOS 쓸어내리기. 작성 중이면 `usePreventRemove`로 묻는다 | §12.5 |
| 앞에 떠 있을 때 온 푸시 | 시스템 배너를 끄고 앱 안 배너를 5초 띄운다 | IA §4.2 |
| 닫은 배너 기억 | kvStore(기기 SecureStore · 웹 localStorage) | 새 패키지 없이 토큰 저장과 같은 자리 |
| 종목 상세 `알림 걸기` | 이번 범위 밖. 흐름이 `EditorStart.instrument`로 종목이 정해진 시작을 받는다 | 사용자 결정. 종목 상세 화면이 아직 없다 |
| `울린 알림 전체 →` | 알림 0건·미확인 0건인 빈 상태에서도 보인다 | 사용자 결정. IA §2.3 "항상 보인다". 알림을 모두 지워도 울린 기록은 남는다(§6.8) |
| 앱 안 배너와 푸시 처리 자리 | 루트 스택 옆(화면 밖) | 어느 스택 화면·모달 위에서든 배너가 보여야 한다. 푸시로 열 때 `navigate(…, { pop: true })`로 탭 묶음이 두 벌이 되지 않게 한다 |
| 백엔드 테스트 DB (Task 0) | 전용 DB `portfolio_test_last_close` (`TEST_DB_URL`) | 사용자 결정. 기본 `portfolio_test`는 계획 ② 세션과 함께 쓴다 |

## A.5 파일 구조

```
front-end/src/
├── api/
│   ├── client.ts                 (수정) apiPost·apiPut·apiDelete, 204, ApiError.fields
│   ├── types.ts                  (수정) Envelope.as_of nullable, EmptyReason 2개, FieldError
│   ├── alertTypes.ts             (신규) 알림·울린 알림·카탈로그·종목 검색·기기 응답 타입
│   ├── alertEndpoints.ts         (신규) 알림 경로와 파라미터 이름
│   └── queries/
│       ├── keys.ts               (수정) 알림 쿼리 키
│       ├── alertInvalidation.ts  (신규) 바꾸는 요청 뒤 무효화할 키 묶음
│       ├── useAlerts.ts · useAlert.ts · useAlertCatalog.ts · useInstruments.ts
│       ├── useAlertEvents.ts · useUnreadCount.ts · usePreview.ts · useAlertActions.ts
├── app/
│   ├── App.tsx                   (수정) 알림 수신 리스너 시작
│   └── navigation/
│       ├── types.ts              (수정) alerts 탭, alert · alert-events · alert-event · alert-editor
│       ├── RootStack.tsx         (수정) 위 네 화면 + 그 옆의 PushRouter
│       └── Tabs.tsx              (수정) 알림 탭 + 배지
├── auth/
│   ├── AuthContext.tsx           (수정) 로그아웃 때 기기 해제, 로그인 실패 때 대기 중인 푸시 버림
│   └── tokenStore.ts             (수정) 저장소를 storage/kvStore로 뽑아 씀
├── storage/kvStore.ts            (신규) 기기: SecureStore / 웹: localStorage
├── design/theme.ts               (수정) badge · 상태 배지 색
├── envelope/                     (수정) as_of null, 빈 상태 2개, 화면 키 2개, header 슬롯
├── format/
│   ├── alertTime.ts              (신규) 기준 표기 · 울린 시각
│   └── number.ts                 (수정) formatKrwReading (= 1,000억원)
├── ui/
│   ├── ConfirmSheet.tsx          (신규) 두 버튼 확인 시트
│   ├── DateField.tsx             (신규) PeriodControl의 날짜 칸을 공용으로
│   └── PeriodControl.tsx         (수정) DateField를 가져다 씀
├── push/
│   ├── config.ts                 (신규) pushCapable · easProjectId
│   ├── notifications.ts          (신규) expo-notifications를 아는 유일한 파일
│   ├── pushInbox.ts              (신규) 푸시 열기 대기열 · 도착 알림 (순수)
│   ├── device.ts                 (신규) 기기 등록·해제와 device_id 보관
│   ├── gate.ts                   (신규) 저장 전 권한 시트 판단 · 허용 · 설정 열기
│   ├── usePushBanners.ts         (신규) 권한 거부 · Android 배너의 상태
│   ├── PushBanners.tsx           (신규) 위 두 배너
│   ├── PushRouter.tsx            (신규) 푸시 → 화면 이동, 앞에 떠 있을 때 앱 안 배너, 배지 갱신
│   └── InAppBanner.tsx           (신규)
├── screens/
│   ├── alerts/                   알림 탭 · 알림 상세 · 울린 알림 · 울린 알림 상세와 그 부품
│   └── alertEditor/              새 알림 흐름 (모달 중첩 스택)
├── fixtures/alerts.ts            (신규) §11 계약 모양의 응답
└── testing/
    ├── serveRoutes.ts            (신규) 경로별 fetch 대역
    └── notificationsMock.ts      (신규) expo-notifications 대역
```

`api/types.ts`에 알림 타입을 더하지 않고 `alertTypes.ts`로 나누는 것은 포트폴리오 타입이 이미 340줄이고, 두 기능이 공유하는 것이 봉투·Notice·FieldError뿐이기 때문이다.

---

# Part B — 태스크

### Task 0: 백엔드 — 종목 검색 행에 직전 종가 (격리 worktree)

가격 도달의 가격 칸을 직전 종가로 미리 채우려면(§12.5.3) 종목을 고를 때 그 값이 있어야 한다. `GET /instruments` 행에 `last_close` · `last_close_on`을 더한다.

**Files:**
- Modify: `back-end/src/main/java/com/stockproject/portfolio/alert/store/InstrumentSearchRow.java`
- Modify: `back-end/src/main/java/com/stockproject/portfolio/alert/store/InstrumentSearchMapper.java`
- Modify: `back-end/src/main/java/com/stockproject/portfolio/alert/api/dto/InstrumentSearchResponse.java`
- Modify: `back-end/src/main/java/com/stockproject/portfolio/alert/service/InstrumentSearchService.java`
- Test: `back-end/src/test/java/com/stockproject/portfolio/alert/api/InstrumentSearchApiTest.java`
- Modify (docs 저장소): `docs/yhr/specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md` §11.1 · §11.3

**Interfaces:**
- Produces: `GET /instruments` 행 `{ id, label, symbol, market, held, last_close: number | null, last_close_on: 'YYYY-MM-DD' | null }`. Task 3의 `InstrumentRow`가 이 모양을 받는다.

- [ ] **Step 1: 격리 worktree를 만든다**

`superpowers:using-git-worktrees` 스킬을 따른다. 원래 경로 `back-end/`에서 브랜치를 바꾸거나 파일을 고치지 않는다.

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project/back-end
git fetch origin
git worktree add ../back-end-last-close -b feat/instrument-last-close origin/main
cd ../back-end-last-close
```

이후 이 태스크의 모든 명령은 `back-end-last-close/`에서 실행한다.

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`InstrumentSearchApiTest`에 메서드를 더한다. 클래스의 `@Sql`은 포트폴리오 샘플만 넣으므로, 일봉이 필요한 이 테스트는 메서드 단위 `@Sql`로 두 파일을 함께 넣는다(메서드 단위가 클래스 단위를 대신한다). `setUp`의 종목 삽입은 `@Sql` 뒤에 돈다.

```java
    /** 가격 도달의 가격 칸을 채우는 값 (§12.5.3). 최신 일봉의 종가와 그 거래일이다. */
    @Test
    @Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
    void 검색_행에_직전_종가와_그_날짜를_싣는다() throws Exception {
        JsonNode samsung = search("q=005930").get(0);
        assertThat(samsung.get("last_close").decimalValue()).isEqualByComparingTo("63010");
        assertThat(samsung.get("last_close_on").asText()).isEqualTo("2026-09-25");

        JsonNode apple = search("q=AAPL").get(0);
        assertThat(apple.get("last_close").decimalValue()).isEqualByComparingTo("230.1");

        // NAVER는 9/25 봉이 없다 — 가진 봉 중 가장 최근 것이다.
        JsonNode naver = search("q=NAVER").get(0);
        assertThat(naver.get("last_close").decimalValue()).isEqualByComparingTo("200000");
        assertThat(naver.get("last_close_on").asText()).isEqualTo("2026-09-24");
    }

    @Test
    void 일봉이_없는_종목은_직전_종가가_null이다() throws Exception {
        JsonNode sdi = search("q=006400").get(0);
        assertThat(sdi.get("last_close").isNull()).isTrue();
        assertThat(sdi.get("last_close_on").isNull()).isTrue();
    }

    @Test
    @Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
    void 보유_종목_구역에도_직전_종가를_싣는다() throws Exception {
        JsonNode rows = search("held=true");
        JsonNode samsung = null;
        for (JsonNode r : rows) if (r.get("label").asText().equals("삼성전자")) samsung = r;
        assertThat(samsung).isNotNull();
        assertThat(samsung.get("last_close").decimalValue()).isEqualByComparingTo("63010");
    }
```

`import org.springframework.test.context.jdbc.Sql;`은 이미 있다.

- [ ] **Step 3: ⛔ 승인 — 전용 테스트 DB를 만든다**

백엔드 테스트는 DB에 쓴다(`@Sql`의 TRUNCATE·INSERT). 기본 테스트 DB `portfolio_test`는 계획 ② 세션도 함께 쓰므로, 이 태스크는 전용 DB `portfolio_test_last_close`에서 돈다. 테스트 설정(`src/test/resources/application-test.yaml`)이 `TEST_DB_URL`로 주소를 바꿀 수 있고, Flyway가 빈 DB에 이 worktree의 마이그레이션(`db/migration` · `db/external`)을 적용한다. 그래서 계획 ②의 마이그레이션은 들어가지 않는다.

사용자에게 묻는다: "로컬 Postgres 컨테이너(`db`)에 테스트 전용 DB `portfolio_test_last_close`를 하나 만들까요? 이 태스크의 백엔드 테스트만 그 DB를 씁니다." 승인을 받은 뒤에만 실행한다.

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project/back-end-last-close
docker compose ps db                    # 떠 있지 않으면 멈추고 사용자에게 묻는다(기동도 승인 대상)
docker compose exec -T db createdb -U portfolio portfolio_test_last_close
```

Expected: 오류 없이 끝난다. 이미 있으면 `already exists`가 나온다 — 그대로 쓴다.

- [ ] **Step 4: 테스트가 실패하는지 본다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_last_close?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.api.InstrumentSearchApiTest'`
Expected: 새 세 테스트가 FAIL — `last_close` 필드가 없어 `NullPointerException`(get이 null).

- [ ] **Step 5: 행·매퍼·응답·서비스를 고친다**

`InstrumentSearchRow.java`:

```java
package com.stockproject.portfolio.alert.store;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;

/** 종목 검색 결과 한 행. lastClose는 최신 수정주가 일봉의 종가이고, 일봉이 없으면 null이다. */
public record InstrumentSearchRow(UUID id, String label, String symbol, String market, boolean held,
                                  BigDecimal lastClose, LocalDate lastCloseOn) { }
```

`InstrumentSearchMapper.java` — 두 SELECT에 같은 LATERAL 조인을 붙인다. 열 별칭(`last_close` · `last_close_on`)은 레코드 필드 이름에 맞춘다 — MyBatis가 생성자 인자를 이름으로 매핑한다(`application.yaml`의 `arg-name-based-constructor-auto-mapping: true` · `map-underscore-to-camel-case: true`).

```java
    /** 종목마다 가장 최근 일봉 하나. (instrument_id, date) 기본키를 거꾸로 읽는다. */
    String LAST_CLOSE = """
             LEFT JOIN LATERAL (
                SELECT p.close, p.date FROM adjusted_price_daily p
                 WHERE p.instrument_id = i.instrument_id
                 ORDER BY p.date DESC LIMIT 1
             ) lc ON true
            """;

    @Select(HELD + """
            SELECT i.instrument_id AS id, i.name AS label, i.symbol, i.market, h.instrument_id IS NOT NULL AS held,
                   lc.close AS last_close, lc.date AS last_close_on
              FROM instrument i LEFT JOIN held h USING (instrument_id)
            """ + LAST_CLOSE + """
             WHERE i.asset_class <> 'CASH' AND i.delisted_on IS NULL
               AND (i.name ILIKE '%' || #{pattern} || '%' ESCAPE '\\'
                    OR i.symbol ILIKE '%' || #{pattern} || '%' ESCAPE '\\')
             ORDER BY CASE WHEN upper(i.symbol) = upper(#{q}) THEN 0
                           WHEN i.name ILIKE #{pattern} || '%' ESCAPE '\\' THEN 1
                           ELSE 2 END,
                      i.name COLLATE "C", i.instrument_id
             LIMIT #{limit}
            """)
    List<InstrumentSearchRow> search(@Param("scope") UserScope scope, @Param("q") String q,
                                     @Param("pattern") String pattern, @Param("limit") int limit);

    @Select(HELD + """
            SELECT i.instrument_id AS id, i.name AS label, i.symbol, i.market, true AS held,
                   lc.close AS last_close, lc.date AS last_close_on
              FROM instrument i JOIN held h USING (instrument_id)
            """ + LAST_CLOSE + """
             WHERE i.asset_class <> 'CASH' AND i.delisted_on IS NULL
             ORDER BY i.name COLLATE "C", i.instrument_id
            """)
    List<InstrumentSearchRow> held(@Param("scope") UserScope scope);
```

클래스 주석 끝에 한 줄을 더한다: `직전 종가는 그 종목의 가장 최근 일봉이다 — 가격 도달의 가격 칸을 채운다(§12.5.3).`

`InstrumentSearchResponse.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

/** GET /instruments (§11.3). last_close는 최신 일봉의 종가, 일봉이 없으면 null이다. */
public record InstrumentSearchResponse(List<Row> rows) {

    public record Row(UUID id, String label, String symbol, String market, boolean held,
                      BigDecimal lastClose, LocalDate lastCloseOn) { }
}
```

`InstrumentSearchService.search`의 매핑:

```java
        return new InstrumentSearchResponse(rows.stream()
                .map(r -> new InstrumentSearchResponse.Row(r.id(), r.label(), r.symbol(), r.market(), r.held(),
                        r.lastClose(), r.lastCloseOn()))
                .toList());
```

- [ ] **Step 6: 테스트가 통과하는지 본다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_last_close?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.api.InstrumentSearchApiTest'`
Expected: PASS (기존 테스트 포함 전부).

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_last_close?currentSchema=app,data' ./gradlew test`
Expected: PASS. 실패가 있으면 이 변경과 무관한지 가린다 — 같은 DB에서 `git stash` 후 같은 테스트를 돌려 main 코드에서도 실패하면 무관한 실패로 보고하고, 이 변경 뒤에만 실패하면 고친다. 원래 경로의 `portfolio_test`로는 돌리지 않는다.

- [ ] **Step 7: 스펙에 필드를 적는다 (docs 저장소)**

`docs/yhr/specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md` §11.1의 `GET /instruments` 문단 끝(`미국 종목의 label은 종목 마스터의 이름이다.` 뒤)에 문장을 더한다.

```
`last_close`는 그 종목의 가장 최근 수정주가 일봉의 종가이고 `last_close_on`은 그 거래일이다. 일봉이 없으면 둘 다 null이다. 새 알림의 가격 도달 칸을 채우는 데 쓴다(§12.5.3).
```

§11.3의 `GET /instruments?q=삼성` 예시 행을 고친다.

```json
// GET /instruments?q=삼성
{ "rows": [ { "id": "…", "label": "삼성전자", "symbol": "005930",
              "market": "KR", "held": true,
              "last_close": 63010, "last_close_on": "2026-09-25" } ] }
```

- [ ] **Step 8: 커밋한다 (두 저장소)**

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project/back-end-last-close
git add src/main/java/com/stockproject/portfolio/alert/store/InstrumentSearchRow.java \
        src/main/java/com/stockproject/portfolio/alert/store/InstrumentSearchMapper.java \
        src/main/java/com/stockproject/portfolio/alert/api/dto/InstrumentSearchResponse.java \
        src/main/java/com/stockproject/portfolio/alert/service/InstrumentSearchService.java \
        src/test/java/com/stockproject/portfolio/alert/api/InstrumentSearchApiTest.java
git commit -m "feat: 종목 검색 행에 직전 종가와 그 거래일을 싣는다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"

cd /Users/yhr/Dev/workspace/personal/stock-project/docs
git add yhr/specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md
git commit -m "docs: 종목 검색 응답에 직전 종가를 적는다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

docs 저장소는 다른 세션도 커밋한다. 이 파일만 스테이징한다.

- [ ] **Step 9: ⛔ 승인 — 병합**

사용자에게 묻는다: "`feat/instrument-last-close`(커밋 1개)를 back-end main에 병합할까요? 원래 경로에서 계획 ②가 진행 중이라, 병합은 그 세션의 작업 트리를 건드리지 않는 방식(`git -C back-end-last-close push origin feat/instrument-last-close` 후 PR, 또는 사용자가 정한 방식)으로 합니다." 답을 받기 전에는 병합하지 않는다. 프론트 태스크는 병합을 기다리지 않는다 — `last_close`가 없으면 가격 칸이 빈 채로 열린다.

---

### Task 1: 통신층 — 바꾸는 요청, 204, 칸별 오류

**Files:**
- Modify: `front-end/src/api/client.ts`
- Modify: `front-end/src/api/types.ts` (`FieldError`, `ApiErrorBody.error.fields`)
- Test: `front-end/src/__tests__/client.test.ts`

**Interfaces:**
- Produces:
  - `apiPost<T>(path: string, body?: unknown): Promise<T>`
  - `apiPut<T>(path: string, body: unknown): Promise<T>`
  - `apiDelete(path: string): Promise<void>`
  - `ApiError.fields: FieldError[]` (없으면 `[]`)
  - `type FieldError = { path: string; code: string; message: string }` (`@/api/types`)
  - 204 응답은 `undefined`로 풀린다.

- [ ] **Step 0: 브랜치를 만든다**

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project/front-end
git status --short          # 비어 있어야 한다
git switch -c feat/alert-tab
```

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`client.test.ts`의 import에 `apiDelete`, `apiPost`, `apiPut`을 더하고 파일 끝에 붙인다.

```ts
describe('바꾸는 요청', () => {
  it('POST는 본문을 JSON으로 싣고 토큰을 붙인다', async () => {
    setAccessToken('tok');
    const calls = stubFetch(() => jsonResponse(201, { alert_id: 'a1' }));

    await expect(apiPost('/alerts', { name: '삼성전자 7만원' })).resolves.toEqual({ alert_id: 'a1' });

    expect(calls[0].url).toBe(`${BASE}/alerts`);
    expect(calls[0].init.method).toBe('POST');
    expect(calls[0].init.body).toBe(JSON.stringify({ name: '삼성전자 7만원' }));
    const headers = calls[0].init.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers.Authorization).toBe('Bearer tok');
  });

  it('본문이 없는 POST에는 Content-Type도 본문도 없다', async () => {
    const calls = stubFetch(() => new Response(null, { status: 204 }));

    await apiPost('/alerts/a1/pause');

    expect(calls[0].init.body).toBeUndefined();
    expect((calls[0].init.headers as Record<string, string>)['Content-Type']).toBeUndefined();
  });

  it('PUT은 경로와 본문을 그대로 보낸다', async () => {
    const calls = stubFetch(() => jsonResponse(200, { alert_id: 'a1' }));

    await apiPut('/alerts/a1', { name: 'x' });

    expect(calls[0].url).toBe(`${BASE}/alerts/a1`);
    expect(calls[0].init.method).toBe('PUT');
  });

  /** Review Focus 2 — 끄기·다시 켜기·삭제는 본문 없이 204로 답한다. */
  it('204는 본문 없이 성공이다', async () => {
    stubFetch(() => new Response(null, { status: 204 }));

    await expect(apiPost('/alerts/a1/resume')).resolves.toBeUndefined();
    await expect(apiDelete('/alerts/a1')).resolves.toBeUndefined();
  });

  it('DELETE는 DELETE로 나간다', async () => {
    const calls = stubFetch(() => new Response(null, { status: 204 }));

    await apiDelete('/devices/d1');

    expect(calls[0].url).toBe(`${BASE}/devices/d1`);
    expect(calls[0].init.method).toBe('DELETE');
  });

  it('400 INVALID_ALERT의 칸별 오류를 싣는다', async () => {
    const fields = [{ path: 'name', code: 'REQUIRED', message: '이름을 입력해 주세요' }];
    stubFetch(() =>
      jsonResponse(400, { error: { code: 'INVALID_ALERT', message: '조건을 확인해 주세요', fields } }),
    );

    const error = await apiPost('/alerts', {}).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe('INVALID_ALERT');
    expect((error as ApiError).message).toBe('조건을 확인해 주세요');
    expect((error as ApiError).fields).toEqual(fields);
  });

  it('칸별 오류가 없는 오류는 빈 목록이다', async () => {
    stubFetch(() =>
      jsonResponse(404, { error: { code: 'ALERT_NOT_FOUND', message: '알림을 찾을 수 없어요' } }),
    );

    const error = (await apiDelete('/alerts/x').catch((e: unknown) => e)) as ApiError;

    expect(error.status).toBe(404);
    expect(error.fields).toEqual([]);
  });
});
```

- [ ] **Step 2: 테스트가 실패하는지 본다**

Run: `npx jest src/__tests__/client.test.ts`
Expected: FAIL — `apiPost is not a function` 등.

- [ ] **Step 3: 구현한다**

`api/types.ts`의 오류 절을 바꾼다.

```ts
/* ── 오류 ─────────────────────────────────────────────────────────── */

/** 칸 하나의 검증 오류. `path`는 요청 JSON의 경로다 — `trigger_spec.params.price`. */
export type FieldError = {
  path: string;
  code: string;
  /** 서버가 완성한 문장. 그 칸 아래에 그대로 낸다. */
  message: string;
};

/** 400 · 401 · 403 · 404 · 500 응답의 본문. */
export type ApiErrorBody = {
  error: {
    code: string;
    /** 서버가 완성한 한국어 문장. 화면에 그대로 낸다. */
    message: string;
    /** 알림 저장의 400 `INVALID_ALERT`에만 실린다. */
    fields?: FieldError[];
  };
};
```

`api/client.ts`:

1. import를 `import type { ApiErrorBody, FieldError, LoginResponse } from '@/api/types';`로 바꾼다.
2. `ApiError`에 `fields`를 더한다.

```ts
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  /** 칸별 검증 오류. 알림 저장의 400만 싣고, 그 밖에는 빈 목록이다. */
  readonly fields: FieldError[];

  constructor(status: number, code: string, message: string, fields: FieldError[] = []) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}
```

3. `request()`에서 `if (!response.ok) throw await toError(path, response);` 바로 아래에 넣는다.

```ts
  // 끄기·다시 켜기·삭제는 본문 없이 답한다. 읽을 본문이 없는 것은 실패가 아니다.
  if (response.status === 204) return undefined as T;
```

4. `toError()`의 마지막 줄을 바꾼다.

```ts
  return new ApiError(response.status, code, message, body?.error.fields ?? []);
```

5. `apiGet` 아래에 더한다.

```ts
/** 본문이 있으면 JSON으로 싣는다. 없으면 Content-Type도 붙이지 않는다. */
function send<T>(method: 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return send<T>('POST', path, body);
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return send<T>('PUT', path, body);
}

export function apiDelete(path: string): Promise<void> {
  return send<void>('DELETE', path);
}
```

- [ ] **Step 4: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest src/__tests__/client.test.ts && npx tsc --noEmit`
Expected: PASS, 타입 오류 없음.

- [ ] **Step 5: 커밋한다**

```bash
git add src/api/client.ts src/api/types.ts src/__tests__/client.test.ts
git commit -m "feat: 바꾸는 요청과 본문 없는 응답, 칸별 검증 오류를 다룬다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 봉투 넓히기 — 기준 시점 없음, 빈 상태 2개, 알림 화면 키

§11.2 끝의 "앱의 봉투 처리에 더할 것"을 그대로 한다.

**Files:**
- Modify: `front-end/src/api/types.ts` (`Envelope.as_of`, `EmptyReason`)
- Modify: `front-end/src/envelope/AsOfBanner.tsx` (`prefix`)
- Modify: `front-end/src/envelope/ScreenFrame.tsx` (`header` · `asOfPrefix`, `as_of` null)
- Modify: `front-end/src/envelope/EmptyState.tsx`
- Modify: `front-end/src/envelope/notices.ts`
- Test: `front-end/src/__tests__/envelope.test.tsx`

**Interfaces:**
- Produces:
  - `Envelope<T>.as_of: string | null`
  - `EmptyReason`에 `'NO_ALERTS' | 'NO_EVENTS'`
  - `ScreenKey`에 `'alerts' | 'alert-events'`
  - `ScreenFrame` 새 props: `header?: ReactNode`(기준 줄보다 위), `asOfPrefix?: string`(기본 `기준`)
  - `AsOfBanner` 새 prop: `prefix?: string`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`envelope.test.tsx` 끝에 붙인다(필요한 import: `Text` from `react-native`, `screen` from `@testing-library/react-native`, `ScreenFrame`, `isVisibleOn`, `renderScreen` — 이미 있는 것은 다시 넣지 않는다).

```tsx
describe('알림 화면을 위한 봉투', () => {
  const delayed = {
    code: 'MARKET_DATA_DELAYED',
    severity: 'warn' as const,
    message: '국내 장중 시세가 10:05 이후 들어오지 않았어요',
    params: {},
  };

  it('기준 시점이 없으면 기준 줄을 숨기고 경고는 그린다', async () => {
    await renderScreen(
      <ScreenFrame
        screen="alerts"
        envelope={{ as_of: null, data: {}, empty_reason: null, notices: [delayed] }}
      >
        <Text>본문</Text>
      </ScreenFrame>,
    );

    expect(screen.queryByText(/^기준 /)).toBeNull();
    expect(screen.getByText(`⚠ ${delayed.message}`)).toBeTruthy();
    expect(screen.getByText('본문')).toBeTruthy();
  });

  it('기준 줄의 머리말을 바꿀 수 있다', async () => {
    await renderScreen(
      <ScreenFrame
        screen="alerts"
        asOfPrefix="최근 평가"
        envelope={{ as_of: '2026-09-26T10:15:00+09:00', data: {}, empty_reason: null, notices: [] }}
      >
        <Text>본문</Text>
      </ScreenFrame>,
    );

    expect(screen.getByText('최근 평가 2026-09-26 10:15')).toBeTruthy();
  });

  it('머리 줄은 빈 상태에서도 보인다', async () => {
    await renderScreen(
      <ScreenFrame
        screen="alerts"
        header={<Text>알림 머리</Text>}
        envelope={{ as_of: null, data: {}, empty_reason: 'NO_ALERTS', notices: [] }}
      >
        <Text>본문</Text>
      </ScreenFrame>,
    );

    expect(screen.getByText('알림 머리')).toBeTruthy();
    expect(screen.getByText('아직 걸어 둔 알림이 없어요')).toBeTruthy();
    expect(screen.getByText('가격·지표·수급 조건을 걸어 두면 충족될 때 알려 드려요')).toBeTruthy();
    expect(screen.queryByText('본문')).toBeNull();
  });

  it('울린 알림이 없다는 빈 상태', async () => {
    await renderScreen(
      <ScreenFrame
        screen="alert-events"
        envelope={{ as_of: null, data: {}, empty_reason: 'NO_EVENTS', notices: [] }}
      >
        <Text>본문</Text>
      </ScreenFrame>,
    );

    expect(screen.getByText('아직 울린 알림이 없어요')).toBeTruthy();
  });

  it('데이터 지연 안내는 알림 두 화면만 그린다', () => {
    expect(isVisibleOn('alerts', 'MARKET_DATA_DELAYED')).toBe(true);
    expect(isVisibleOn('alert-events', 'MARKET_DATA_DELAYED')).toBe(true);
    expect(isVisibleOn('summary', 'MARKET_DATA_DELAYED')).toBe(false);
  });
});
```

- [ ] **Step 2: 테스트가 실패하는지 본다**

Run: `npx jest src/__tests__/envelope.test.tsx`
Expected: FAIL — `'alerts'`가 `ScreenKey`가 아니라는 타입 오류는 jest가 잡지 않으므로, 실패 메시지는 `BY_SCREEN[screen] is undefined`(isVisibleOn) 또는 텍스트를 찾지 못함.

- [ ] **Step 3: 구현한다**

`api/types.ts`:

```ts
export type Envelope<T> = {
  /**
   * 집계 기준 시각. `2026-07-27T15:30:00+09:00`
   * 기준 시점이 없는 응답(평가된 알림이 하나도 없는 알림 목록)은 null이다.
   */
  as_of: string | null;
  data: T;
  /** 값이 있으면 `data`가 비어 있는 이유다. 오류가 아니라 정상 응답이다. */
  empty_reason: EmptyReason | null;
  notices: Notice[];
};
```

```ts
export type EmptyReason =
  | 'NO_ACCOUNTS'
  | 'NO_HOLDINGS'
  | 'NO_MATCH_FILTER'
  | 'NO_TRADES_IN_PERIOD'
  | 'ALL_UNAVAILABLE'
  | 'NO_ALERTS'
  | 'NO_EVENTS';
```

`envelope/EmptyState.tsx` — `MESSAGE`와 `SUBTEXT`에 더한다.

```ts
const MESSAGE: Record<EmptyReason, string> = {
  NO_ACCOUNTS: '연동된 계좌가 없어요',
  NO_HOLDINGS: '보유 중인 종목이 없어요',
  NO_MATCH_FILTER: '조건에 맞는 종목이 없어요',
  NO_TRADES_IN_PERIOD: '이 기간에 거래가 없어요',
  ALL_UNAVAILABLE: '자료를 가져오지 못했어요',
  NO_ALERTS: '아직 걸어 둔 알림이 없어요',
  NO_EVENTS: '아직 울린 알림이 없어요',
};
```

```ts
const SUBTEXT: Partial<Record<EmptyReason, string>> = {
  NO_ACCOUNTS: '계좌 연동은 준비 중입니다',
  NO_ALERTS: '가격·지표·수급 조건을 걸어 두면 충족될 때 알려 드려요',
};
```

`envelope/notices.ts`:

```ts
export type ScreenKey =
  | 'summary'
  | 'positions'
  | 'allocation'
  | 'accounts'
  | 'realized-pnl'
  | 'asset-change'
  | 'alerts'
  | 'alert-events';
```

`BY_SCREEN`에 두 줄을 더한다. 환율 안내(`ALWAYS`)는 넣지 않는다 — 알림 화면에는 원화로 환산한 금액이 없다.

```ts
  /** 사용자 알림이 기다리는 시세가 늦을 때. 알림 두 목록만 그린다(§7.4). */
  alerts: ['MARKET_DATA_DELAYED'],
  'alert-events': ['MARKET_DATA_DELAYED'],
```

`envelope/AsOfBanner.tsx` — props에 `prefix = '기준'`을 더하고 첫 줄을 바꾼다.

```tsx
export function AsOfBanner({
  asOf,
  prefix = '기준',
  captions,
  refreshing = false,
  onRefresh,
}: {
  asOf: string;
  /** 기준 시각 앞의 말. 알림 목록은 `최근 평가`다. */
  prefix?: string;
  /** 배너 둘째 줄에 이어 붙일 안내. 서버가 완성한 문장을 그대로 낸다. */
  captions: Notice[];
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
```

```tsx
        <Text style={[type.micro, { color: palette.textMuted }]}>
          {prefix} {formatAsOf(asOf)}
        </Text>
```

`envelope/ScreenFrame.tsx` — props에 둘을 더한다.

```tsx
  /** 기준 줄보다 위에 놓는 머리. 빈 상태·로딩·오류에서도 남는다. */
  header?: ReactNode;
  /** 기준 줄의 머리말. 기본은 `기준`. */
  asOfPrefix?: string;
```

렌더를 바꾼다.

```tsx
  return (
    <SafeAreaView
      edges={topInset ? ['top'] : []}
      style={[styles.screen, { backgroundColor: palette.bg }]}
    >
      {header}
      {envelope && (
        <>
          {/* 기준 시점이 없는 응답은 기준 줄을 그리지 않는다. 경고는 그대로 쌓는다. */}
          {envelope.as_of && (
            <AsOfBanner
              asOf={envelope.as_of}
              prefix={asOfPrefix}
              captions={captionNotices(screen, envelope.notices)}
              refreshing={refreshing}
              onRefresh={onRefresh}
            />
          )}
          <NoticeList notices={bannerNotices(screen, envelope.notices)} />
        </>
      )}
      {aboveContent}
      <View style={styles.body}>{body}</View>
    </SafeAreaView>
  );
```

- [ ] **Step 4: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest && npx tsc --noEmit`
Expected: 전부 PASS. `as_of`가 nullable이 되어 다른 화면에서 타입 오류가 나면 그 자리는 `ScreenFrame`뿐이어야 한다(Grep으로 `\.as_of` 사용처를 확인했다).

- [ ] **Step 5: 커밋한다**

```bash
git add src/api/types.ts src/envelope src/__tests__/envelope.test.tsx
git commit -m "feat: 봉투가 기준 시점 없음과 알림 화면의 빈 상태·안내를 다룬다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---
### Task 3: 알림 API — 타입 · 경로 · 쿼리 훅 · 픽스처

**Files:**
- Create: `front-end/src/api/alertTypes.ts`
- Create: `front-end/src/api/alertEndpoints.ts`
- Modify: `front-end/src/api/queries/keys.ts`
- Create: `front-end/src/api/queries/alertInvalidation.ts`
- Create: `front-end/src/api/queries/useAlerts.ts` · `useAlert.ts` · `useAlertCatalog.ts` · `useInstruments.ts` · `useAlertEvents.ts` · `useUnreadCount.ts` · `usePreview.ts` · `useAlertActions.ts`
- Create: `front-end/src/fixtures/alerts.ts`
- Create: `front-end/src/testing/serveRoutes.ts`
- Test: `front-end/src/__tests__/alertApi.test.tsx`

**Interfaces:**
- Consumes: `apiGet` · `apiPost` · `apiPut` · `apiDelete` · `Envelope` · `FieldError` (Task 1·2)
- Produces (뒤 태스크가 이 이름을 그대로 쓴다):
  - 타입: `Market` · `Cadence` · `NotifyMode` · `AlertStatus` · `Truth` · `UnknownReason` · `TriggerType` · `OperatorKey` · `WindowFnKey` · `Transform` · `Operand` · `Right` · `Modifier` · `Condition` · `ComposableSpec` · `PresetSpec` · `AlertRequest` · `PreviewRequest` · `AlertInstrument` · `AlertCard` · `UnreadEvent` · `AlertListData` · `AlertsResponse` · `RecentEvent` · `AlertDetail` · `Summary` · `CurrentLine` · `Current` · `PreviewResponse` · `AlertIdResponse` · `CatalogIndicator` · `CatalogPreset` · `PresetParam` · `CatalogTransform` · `CatalogOperator` · `AlertCatalog` · `InstrumentRow` · `InstrumentSearchResponse` · `AlertEventRow` · `AlertEventsResponse` · `AlertEventDetail` · `UnreadCountResponse` · `DeviceResponse`
  - 경로 함수: `fetchAlerts()` · `fetchAlert(id)` · `fetchAlertCatalog()` · `searchInstruments(q, held)` · `previewAlert(req)` · `createAlert(req)` · `updateAlert(id, req)` · `deleteAlert(id)` · `pauseAlert(id)` · `resumeAlert(id, expiresAt?)` · `fetchAlertEvents({ alertId?, cursor? })` · `fetchAlertEvent(id)` · `markEventRead(id)` · `markAllEventsRead()` · `fetchUnreadCount()` · `registerDeviceToken(token, platform)` · `unregisterDeviceId(id)`
  - 훅: `useAlerts()` → `{ envelope, loading, refreshing, error, refetch }` · `useAlert(id)` → `UseQueryResult<AlertDetail>` · `useAlertCatalog()` → `UseQueryResult<AlertCatalog>` · `useInstruments(q, held)` · `useAlertEvents(alertId?)` → `{ envelope, rows, loading, refreshing, error, refetch, fetchMore, hasMore }` · `useAlertEvent(id)` · `useUnreadCount()` → `number` · `usePreview(request, { debounceMs? })` → `{ preview, pending, error, refetch }` · `useAlertActions(alertId)` → `{ pause, resume, remove }`(각각 `UseMutationResult`)
  - 무효화: `invalidateAlertData(queryClient)` · `forgetAlert(queryClient, alertId)`
  - 테스트: `serveRoutes(routes: Route[]): Call[]`
  - 픽스처: `alertsFixture` · `alertsEmptyFixture` · `alertsEmptyWithUnreadFixture` · `presetDetailFixture` · `composableDetailFixture` · `expiredDetailFixture` · `catalogFixture` · `previewFixture` · `previewInvalidFixture` · `instrumentsFixture` · `heldFixture` · `eventsFixture` · `eventsEmptyFixture` · `eventDetailFixture` · `deletedEventDetailFixture`

- [ ] **Step 1: 응답 타입을 쓴다**

`front-end/src/api/alertTypes.ts`:

```ts
import type { Envelope } from '@/api/types';

/**
 * 알림 API의 요청·응답 모양 (알림 스펙 §11). 필드 이름은 서버 그대로 snake_case다.
 *
 * 포트폴리오 타입과 나눠 둔다. 두 기능이 함께 쓰는 것은 봉투·안내·칸별 오류뿐이다.
 */

export type Market = 'KR' | 'US';
export type Cadence = 'INTRADAY' | 'CLOSE';
export type NotifyMode = 'EDGE_REARM' | 'ONE_SHOT' | 'COOLDOWN';
export type AlertStatus = 'ACTIVE' | 'PAUSED' | 'ENDED' | 'EXPIRED';
export type Truth = 'TRUE' | 'FALSE' | 'UNKNOWN';
export type TriggerType = 'COMPOSABLE' | 'PRESET';
export type UnknownReason =
  | 'DATA_MISSING'
  | 'INSUFFICIENT_HISTORY'
  | 'NO_TRADE'
  | 'PRICE_ADJUSTMENT_SUSPECTED'
  | 'NOT_HELD'
  | 'INSTRUMENT_UNKNOWN';
export type OperatorKey = 'gte' | 'lte' | 'gt' | 'lt' | 'crosses_above' | 'crosses_below';
export type WindowFnKey = 'max' | 'min' | 'avg' | 'sum';

/* ── 조건 (trigger_spec) ──────────────────────────────────────────── */

/** 사용자가 만드는 조건에는 `lag`를 싣지 않는다. 서버가 정한다(§4.2). */
export type Transform =
  | { type: 'identity' }
  | { type: 'window'; fn: WindowFnKey; n: number | null }
  | { type: 'delta'; n: number | null }
  | { type: 'pct'; n: number | null };

export type Operand = {
  indicator: string;
  /** 파라미터가 없는 지표(가격 등)는 키 자체가 없다. */
  indicator_params?: Record<string, number | null>;
  transform: Transform;
};

export type Right = { const: number | null } | Operand;

export type Modifier = { streak: number | null } | { persist_min: number | null } | null;

export type Condition = { left: Operand; op: OperatorKey; right: Right; modifier: Modifier };

export type ComposableSpec = { conditions: Condition[] };

export type PresetSpec = { preset_key: string; params: Record<string, number | string | null> };

/** POST /alerts · PUT /alerts/{id}. 숫자 칸이 비었으면 null을 보내 서버가 칸별 오류로 답하게 한다. */
export type AlertRequest = {
  instrument_id: string;
  name: string;
  cadence: Cadence;
  notify_mode: NotifyMode;
  cooldown_min: number | null;
  /** null이면 무기한. 날짜 칸이 형식에 맞지 않으면 그 글자를 그대로 보내 서버가 경로와 함께 거절한다. */
  expires_at: string | null;
  trigger_type: TriggerType;
  trigger_spec: ComposableSpec | PresetSpec;
};

/** 수정 중이거나 상세의 현재값 상자를 부를 때는 `alert_id`를 싣는다(§6.7 · §12.4). */
export type PreviewRequest = AlertRequest & { alert_id?: string };

/* ── 목록 · 상세 ──────────────────────────────────────────────────── */

/** 종목 마스터에서 사라진 종목이면 label·market이 null이다. */
export type AlertInstrument = { id: string; label: string | null; market: Market | null };

export type AlertCard = {
  alert_id: string;
  name: string;
  instrument: AlertInstrument;
  cadence: Cadence;
  notify_mode: NotifyMode;
  status: AlertStatus;
  summary: { short: string };
  /** 아직 평가 전이면 null. */
  last_result: Truth | null;
  unknown_reason: UnknownReason | null;
  evaluated_as_of: string | null;
  last_fired_at: string | null;
};

export type UnreadEvent = {
  event_id: string;
  title: string;
  cadence: Cadence;
  market: Market;
  as_of: string;
  fired_at: string;
  alert_deleted: boolean;
};

export type AlertListData = {
  rows: AlertCard[];
  /** 새로 울린 알림 블록. 최대 3건. */
  unread: UnreadEvent[];
  /** 블록에 다 싣지 못한 미확인 건수. */
  unread_more: number;
};

export type AlertsResponse = Envelope<AlertListData>;

export type RecentEvent = { event_id: string; title: string; as_of: string; read: boolean };

export type Summary = { short: string; sentence: string };

export type AlertDetail = {
  alert_id: string;
  name: string;
  instrument: AlertInstrument;
  cadence: Cadence;
  notify_mode: NotifyMode;
  cooldown_min: number | null;
  expires_at: string | null;
  status: AlertStatus;
  trigger_type: TriggerType;
  trigger_spec: ComposableSpec | PresetSpec;
  summary: Summary;
  last_result: Truth | null;
  unknown_reason: UnknownReason | null;
  evaluated_as_of: string | null;
  /** 최근 5건. 전체는 GET /alert-events?alert_id= */
  recent_events: RecentEvent[];
};

/* ── 미리보기 ─────────────────────────────────────────────────────── */

export type CurrentLine = { result: Truth; unknown_reason: UnknownReason | null; text: string };

/** 현재값 상자. 머리(`header`)와 결과 줄(`result_text`)은 서버가 완성한다. */
export type Current = {
  result: Truth;
  as_of: string | null;
  header: string;
  result_text: string;
  conditions: CurrentLine[];
};

/** 형 오류가 있어도 200이다. 트리거를 컴파일할 수 없으면 summary·current가 null이다. */
export type PreviewResponse = {
  valid: boolean;
  errors: { path: string; code: string; message: string }[];
  summary: Summary | null;
  current: Current | null;
  already_satisfied: boolean;
  duplicate_of: string | null;
};

export type AlertIdResponse = { alert_id: string };

/* ── 카탈로그 ─────────────────────────────────────────────────────── */

export type CatalogIndicator = {
  key: string;
  label: string;
  /** `시세` · `기술지표` · `수급` · `내 보유` */
  category: string;
  unit: 'price' | 'krw' | 'percent' | 'shares' | 'ratio' | 'index';
  params: { key: string; default: number; min: number; max: number }[];
  intraday_left: boolean;
  markets: Market[];
  allowed_transforms: Transform['type'][];
  /** 변형별 n 범위. `identity`는 없다. */
  transform_ranges: Partial<Record<Exclude<Transform['type'], 'identity'>, { min: number; max: number }>>;
  allowed_operators: OperatorKey[];
  scope: 'market' | 'user';
  deprecated: boolean;
};

export type PresetParam = {
  key: string;
  kind: 'int' | 'decimal' | 'choice';
  min: number | null;
  max: number | null;
  /** 선택 칸은 문자열, 숫자 칸은 숫자. 가격 도달의 가격처럼 기본값이 없으면 null. */
  default: number | string | null;
  choices: string[];
  required: boolean;
};

export type CatalogPreset = {
  key: string;
  label: string;
  cadences: Cadence[];
  markets: Market[];
  scope: 'market' | 'user';
  param_schema: PresetParam[];
};

export type CatalogTransform = { key: Transform['type']; label: string; fns: { key: WindowFnKey; label: string }[] };
export type CatalogOperator = { key: OperatorKey; symbol: string; word: string };

export type AlertCatalog = {
  indicators: CatalogIndicator[];
  presets: CatalogPreset[];
  transforms: CatalogTransform[];
  operators: CatalogOperator[];
};

/* ── 종목 검색 ────────────────────────────────────────────────────── */

export type InstrumentRow = {
  id: string;
  label: string;
  symbol: string;
  market: Market;
  held: boolean;
  /** 최신 일봉 종가와 그 거래일. 일봉이 없거나 서버가 아직 싣지 않으면 없다. */
  last_close?: number | null;
  last_close_on?: string | null;
};

export type InstrumentSearchResponse = { rows: InstrumentRow[] };

/* ── 울린 알림 (계획 ②의 계약, §11.3) ─────────────────────────────── */

export type AlertEventRow = {
  event_id: string;
  alert_id: string;
  title: string;
  body: string;
  cadence: Cadence;
  market: Market;
  as_of: string;
  fired_at: string;
  read: boolean;
  alert_deleted: boolean;
};

export type AlertEventsResponse = Envelope<{ rows: AlertEventRow[]; next_cursor: string | null }>;

export type AlertEventDetail = {
  event_id: string;
  title: string;
  body: string;
  /** 울린 이유 상자의 줄. 조건마다 하나. */
  lines: string[];
  as_of: string;
  fired_at: string;
  observed: Record<string, unknown>;
  read_at: string | null;
  /** 목록 행과 같은 평가 시점·시장. 응답에 없으면 화면이 `alert.cadence`와 국내 표기로 그린다. */
  cadence?: Cadence;
  market?: Market;
  alert: {
    alert_id: string;
    name: string;
    cadence: Cadence;
    notify_mode: NotifyMode;
    status: AlertStatus;
    last_result: Truth | null;
    unknown_reason: UnknownReason | null;
    deleted: boolean;
    instrument: { id: string; label: string | null };
  };
};

export type UnreadCountResponse = { count: number };

export type DeviceResponse = { device_id: string };
```

- [ ] **Step 2: 경로 함수를 쓴다**

`front-end/src/api/alertEndpoints.ts`:

```ts
import { apiDelete, apiGet, apiPost, apiPut } from '@/api/client';
import type {
  AlertCatalog,
  AlertDetail,
  AlertEventDetail,
  AlertEventsResponse,
  AlertIdResponse,
  AlertRequest,
  AlertsResponse,
  DeviceResponse,
  InstrumentSearchResponse,
  PreviewRequest,
  PreviewResponse,
  UnreadCountResponse,
} from '@/api/alertTypes';

/**
 * 알림 기능이 부르는 경로. 경로와 파라미터 이름을 여기에만 적는다.
 * 사용자 ID는 어디에도 싣지 않는다 — 누구의 알림인지는 토큰이 정한다(§11.1).
 */

export function fetchAlerts(): Promise<AlertsResponse> {
  return apiGet<AlertsResponse>('/alerts');
}

export function fetchAlert(alertId: string): Promise<AlertDetail> {
  return apiGet<AlertDetail>(`/alerts/${alertId}`);
}

export function fetchAlertCatalog(): Promise<AlertCatalog> {
  return apiGet<AlertCatalog>('/alerts/catalog');
}

/** 검색어가 없으면 `held=true`로 보유 종목 구역을 받는다(§12.5.1). */
export function searchInstruments(q: string, held: boolean): Promise<InstrumentSearchResponse> {
  return apiGet<InstrumentSearchResponse>('/instruments', {
    q: q === '' ? undefined : q,
    held: held ? 'true' : undefined,
  });
}

export function previewAlert(request: PreviewRequest): Promise<PreviewResponse> {
  return apiPost<PreviewResponse>('/alerts/preview', request);
}

export function createAlert(request: AlertRequest): Promise<AlertIdResponse> {
  return apiPost<AlertIdResponse>('/alerts', request);
}

export function updateAlert(alertId: string, request: AlertRequest): Promise<AlertIdResponse> {
  return apiPut<AlertIdResponse>(`/alerts/${alertId}`, request);
}

export function deleteAlert(alertId: string): Promise<void> {
  return apiDelete(`/alerts/${alertId}`);
}

export function pauseAlert(alertId: string): Promise<void> {
  return apiPost<void>(`/alerts/${alertId}/pause`);
}

/**
 * 만료된 알림은 새 유효기간이 필수다(null이면 무기한). 끝난 알림은 본문 없이 보낸다.
 * `undefined`와 `null`을 가른다 — null은 "무기한으로 다시 켠다"는 값이다.
 */
export function resumeAlert(alertId: string, expiresAt?: string | null): Promise<void> {
  return apiPost<void>(
    `/alerts/${alertId}/resume`,
    expiresAt === undefined ? undefined : { expires_at: expiresAt },
  );
}

const EVENTS_PAGE = 20;

export function fetchAlertEvents(query: { alertId?: string; cursor?: string }): Promise<AlertEventsResponse> {
  return apiGet<AlertEventsResponse>('/alert-events', {
    alert_id: query.alertId,
    cursor: query.cursor,
    limit: EVENTS_PAGE,
  });
}

export function fetchAlertEvent(eventId: string): Promise<AlertEventDetail> {
  return apiGet<AlertEventDetail>(`/alert-events/${eventId}`);
}

export function markEventRead(eventId: string): Promise<void> {
  return apiPost<void>(`/alert-events/${eventId}/read`);
}

export function markAllEventsRead(): Promise<void> {
  return apiPost<void>('/alert-events/read-all');
}

export function fetchUnreadCount(): Promise<UnreadCountResponse> {
  return apiGet<UnreadCountResponse>('/alert-events/unread-count');
}

export function registerDeviceToken(token: string, platform: 'IOS' | 'ANDROID'): Promise<DeviceResponse> {
  return apiPost<DeviceResponse>('/devices', { expo_push_token: token, platform });
}

export function unregisterDeviceId(deviceId: string): Promise<void> {
  return apiDelete(`/devices/${deviceId}`);
}
```

- [ ] **Step 3: 쿼리 키와 무효화 묶음을 쓴다**

`api/queries/keys.ts`의 `keys` 객체 끝에 더한다.

```ts
  alerts: ['alerts'] as const,
  alert: (alertId: string) => ['alert', alertId] as const,
  alertCatalog: ['alert-catalog'] as const,
  instruments: (q: string, held: boolean) => ['instruments', { q, held }] as const,
  /** 요청 JSON 문자열을 그대로 키로 쓴다 — 입력이 바뀌면 다른 쿼리다. */
  alertPreview: (serialized: string | null) => ['alert-preview', serialized] as const,
  alertEvents: (alertId: string | null) => ['alert-events', { alertId }] as const,
  alertEvent: (eventId: string) => ['alert-event', eventId] as const,
  unreadCount: ['unread-count'] as const,
```

`api/queries/alertInvalidation.ts`:

```ts
import type { QueryClient } from '@tanstack/react-query';

import { keys } from '@/api/queries/keys';

/**
 * 알림을 바꾸거나 울린 알림을 읽은 뒤 다시 받을 것들.
 *
 * 한 번의 변경이 여러 화면에 걸친다 — 끄기 하나가 카드의 배지, 상세의 토글,
 * 울린 알림 상세의 `이 알림 끄기` 버튼을 함께 바꾼다. 화면마다 골라 무효화하면
 * 한 곳을 빠뜨린다.
 */
export function invalidateAlertData(queryClient: QueryClient): void {
  for (const queryKey of [
    keys.alerts,
    ['alert'],
    ['alert-events'],
    ['alert-event'],
    keys.unreadCount,
    ['alert-preview'],
  ]) {
    void queryClient.invalidateQueries({ queryKey });
  }
}

/**
 * 지운 알림의 상세와 미리보기를 캐시에서 걷어낸다.
 * 무효화하면 아직 떠 있는 상세 화면이 다시 받다가 404를 그리고 닫힌다.
 */
export function forgetAlert(queryClient: QueryClient, alertId: string): void {
  queryClient.removeQueries({ queryKey: keys.alert(alertId) });
  queryClient.removeQueries({ queryKey: ['alert-preview'] });
  for (const queryKey of [keys.alerts, ['alert-events'], ['alert-event'], keys.unreadCount]) {
    void queryClient.invalidateQueries({ queryKey });
  }
}
```

- [ ] **Step 4: 조회 훅을 쓴다**

`api/queries/useAlerts.ts`:

```ts
import { useQuery } from '@tanstack/react-query';

import { fetchAlerts } from '@/api/alertEndpoints';
import { keys } from '@/api/queries/keys';

/** 알림 탭. 규칙 목록과 새로 울린 알림 블록이 한 응답에 온다(§11.2). */
export function useAlerts() {
  const query = useQuery({ queryKey: keys.alerts, queryFn: fetchAlerts });
  return {
    envelope: query.data ?? null,
    loading: query.isPending,
    refreshing: query.isFetching && Boolean(query.data),
    error: query.error ?? undefined,
    refetch: () => void query.refetch(),
  };
}
```

`api/queries/useAlert.ts`:

```ts
import { useQuery } from '@tanstack/react-query';

import { fetchAlert } from '@/api/alertEndpoints';
import { keys } from '@/api/queries/keys';

/** 알림 상세. 수정 화면도 이 응답의 trigger_spec으로 칸을 채운다. */
export function useAlert(alertId: string) {
  return useQuery({ queryKey: keys.alert(alertId), queryFn: () => fetchAlert(alertId) });
}
```

`api/queries/useAlertCatalog.ts`:

```ts
import { useQuery } from '@tanstack/react-query';

import { fetchAlertCatalog } from '@/api/alertEndpoints';
import { keys } from '@/api/queries/keys';

/**
 * 지표·변형·연산자·프리셋. 코드 상수라 한 세션 동안 바뀌지 않는다.
 * 폼을 열 때마다 받으면 조건 선택이 뜨는 순간 비어 보인다.
 */
const ONE_HOUR = 60 * 60 * 1000;

export function useAlertCatalog() {
  return useQuery({ queryKey: keys.alertCatalog, queryFn: fetchAlertCatalog, staleTime: ONE_HOUR });
}
```

`api/queries/useInstruments.ts`:

```ts
import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { searchInstruments } from '@/api/alertEndpoints';
import { keys } from '@/api/queries/keys';

/**
 * 종목 검색. 검색어는 화면이 0.3초 가라앉힌 뒤 넘긴다(§12.5.1).
 * 새 결과가 올 때까지 앞 결과를 둔다 — 글자마다 목록이 비었다 차면 손가락이 헛짚는다.
 */
export function useInstruments(q: string, held: boolean) {
  return useQuery({
    queryKey: keys.instruments(q, held),
    queryFn: () => searchInstruments(q, held),
    placeholderData: keepPreviousData,
  });
}
```

`api/queries/useUnreadCount.ts`:

```ts
import { useQuery } from '@tanstack/react-query';

import { fetchUnreadCount } from '@/api/alertEndpoints';
import { keys } from '@/api/queries/keys';

/**
 * 탭 배지의 수. 받지 못하면 0으로 친다 — 배지는 보조 신호라 오류 화면을 띄울 자리가 없고,
 * 울린 알림 API가 아직 없는 서버(404)에서도 탭이 그대로 동작해야 한다.
 */
export function useUnreadCount(): number {
  const query = useQuery({ queryKey: keys.unreadCount, queryFn: fetchUnreadCount, retry: false });
  return query.data?.count ?? 0;
}
```

`api/queries/useAlertEvents.ts`:

```ts
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';

import { fetchAlertEvent, fetchAlertEvents } from '@/api/alertEndpoints';
import { keys } from '@/api/queries/keys';

/**
 * 울린 알림 목록. 커서로 이어 받는다(§11.3). 알림 상세의 `전체 →`로 오면 그 알림만 거른다.
 * 봉투(기준 시점·안내·빈 상태)는 첫 쪽의 것을 쓴다.
 */
export function useAlertEvents(alertId?: string) {
  const query = useInfiniteQuery({
    queryKey: keys.alertEvents(alertId ?? null),
    queryFn: ({ pageParam }) => fetchAlertEvents({ alertId, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.data.next_cursor ?? undefined,
  });
  const pages = query.data?.pages ?? [];
  return {
    envelope: pages[0] ?? null,
    rows: pages.flatMap((page) => page.data.rows),
    loading: query.isPending,
    refreshing: query.isRefetching,
    error: query.error ?? undefined,
    refetch: () => void query.refetch(),
    hasMore: query.hasNextPage,
    fetchMore: () => {
      if (query.hasNextPage && !query.isFetchingNextPage) void query.fetchNextPage();
    },
  };
}

export function useAlertEvent(eventId: string) {
  return useQuery({ queryKey: keys.alertEvent(eventId), queryFn: () => fetchAlertEvent(eventId) });
}
```

`api/queries/usePreview.ts`:

```ts
import { useEffect, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { previewAlert } from '@/api/alertEndpoints';
import type { PreviewRequest } from '@/api/alertTypes';
import { keys } from '@/api/queries/keys';

/**
 * 저장 전 초안 하나로 문장 · 지금 값 · 검증 오류 · 이미 충족 · 중복을 받는다(§11.3).
 *
 * 입력이 0.5초 멈춘 뒤에 부른다(§12.8). 요청 JSON을 키로 쓰므로, 앞 입력의 응답이
 * 늦게 와도 지금 입력의 자리를 덮지 못한다. 새 응답이 올 때까지 앞 응답을 그대로 둔다 —
 * 글자마다 상자가 비었다 차면 읽던 줄을 잃는다.
 *
 * 알림 상세는 `debounceMs: 0`으로 열자마자 부른다.
 */
export function usePreview(request: PreviewRequest | null, options?: { debounceMs?: number }) {
  const debounceMs = options?.debounceMs ?? 500;
  const serialized = request === null ? null : JSON.stringify(request);
  const [settled, setSettled] = useState<string | null>(debounceMs === 0 ? serialized : null);

  useEffect(() => {
    if (debounceMs === 0) {
      setSettled(serialized);
      return;
    }
    const timer = setTimeout(() => setSettled(serialized), debounceMs);
    return () => clearTimeout(timer);
  }, [serialized, debounceMs]);

  const query = useQuery({
    queryKey: keys.alertPreview(settled),
    queryFn: () => previewAlert(JSON.parse(settled as string) as PreviewRequest),
    enabled: settled !== null,
    placeholderData: keepPreviousData,
    staleTime: 0,
  });

  return {
    preview: query.data ?? null,
    /** 입력이 아직 가라앉지 않았거나 응답을 기다리는 중. */
    pending: settled !== serialized || query.isFetching,
    error: query.error ?? undefined,
    refetch: () => void query.refetch(),
  };
}
```

`api/queries/useAlertActions.ts`:

```ts
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { deleteAlert, pauseAlert, resumeAlert } from '@/api/alertEndpoints';
import { forgetAlert, invalidateAlertData } from '@/api/queries/alertInvalidation';

/** 카드·상세·울린 알림 상세가 함께 쓰는 알림 하나의 상태 전환. */
export function useAlertActions(alertId: string) {
  const queryClient = useQueryClient();
  const refresh = () => invalidateAlertData(queryClient);

  return {
    pause: useMutation({ mutationFn: () => pauseAlert(alertId), onSuccess: refresh }),
    /** 만료된 알림은 새 유효기간을 넘긴다(null은 무기한). 끝난 알림은 인자 없이 부른다. */
    resume: useMutation({
      mutationFn: (expiresAt?: string | null) => resumeAlert(alertId, expiresAt),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: () => deleteAlert(alertId),
      onSuccess: () => forgetAlert(queryClient, alertId),
    }),
  };
}
```

- [ ] **Step 5: 경로별 fetch 대역을 쓴다**

`front-end/src/testing/serveRoutes.ts`:

```ts
/**
 * 경로마다 정해진 응답을 돌려주는 fetch 대역. 부른 요청을 순서대로 기록한다.
 * 맞는 경로가 없으면 404 — 아직 없는 서버 경로(계획 ②)를 흉내 내는 데도 쓴다.
 * 앱 코드는 이 파일을 쓰지 않는다.
 */

const BASE = 'http://api.test:8080';

export type Route = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  /** 쿼리스트링을 뺀 경로. 정규식이면 test로 맞춘다. */
  path: string | RegExp;
  status?: number;
  /** 함수면 요청 본문을 받아 응답 본문을 만든다. */
  body?: unknown | ((requestBody: unknown, url: string) => unknown);
  /** 응답을 늦출 때 쓴다. 이 약속이 풀릴 때 응답한다. */
  wait?: (requestBody: unknown) => Promise<void>;
};

/** `auth`는 실린 Authorization 헤더. 로그아웃 때 토큰이 살아 있는 동안 기기를 지웠는지 본다. */
export type Call = { method: string; url: string; path: string; body: unknown; auth?: string };

export function serveRoutes(routes: Route[]): Call[] {
  const calls: Call[] = [];
  global.fetch = jest.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET';
    const path = url.replace(BASE, '').split('?')[0];
    const requestBody = typeof init.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined;
    const auth = (init.headers as Record<string, string> | undefined)?.Authorization;
    calls.push({ method, url, path, body: requestBody, auth });

    const route = routes.find(
      (r) =>
        (r.method ?? 'GET') === method &&
        (typeof r.path === 'string' ? r.path === path : r.path.test(path)),
    );
    if (!route) {
      return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: '없는 경로예요' } }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    if (route.wait) await route.wait(requestBody);
    const status = route.status ?? 200;
    if (status === 204) return new Response(null, { status: 204 });
    const body = typeof route.body === 'function' ? route.body(requestBody, url) : route.body;
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
  }) as unknown as typeof fetch;
  return calls;
}
```

- [ ] **Step 6: 픽스처를 쓴다**

`front-end/src/fixtures/alerts.ts`. 계획 ①의 실제 DTO와 §11 계약을 옮긴 것이다. Task 14에서 로컬 서버 응답과 대조한다.

```ts
import type {
  AlertCatalog,
  AlertDetail,
  AlertEventDetail,
  AlertEventsResponse,
  AlertsResponse,
  CatalogIndicator,
  InstrumentSearchResponse,
  PreviewResponse,
} from '@/api/alertTypes';

/**
 * 알림 화면 테스트의 입력. 계획 ①의 실제 응답 모양(DTO)과 계획 ②의 계약(스펙 §11)을 옮겼다.
 * 앱 코드는 이 파일을 쓰지 않는다.
 */

export const SAMSUNG = { id: '10000000-0000-0000-0000-000000000001', label: '삼성전자', market: 'KR' as const };
export const APPLE = { id: '10000000-0000-0000-0000-000000000004', label: '애플', market: 'US' as const };

export const alertsFixture: AlertsResponse = {
  as_of: '2026-09-26T10:15:00+09:00',
  data: {
    rows: [
      {
        alert_id: 'a-satisfied',
        name: '삼성전자 7만원',
        instrument: SAMSUNG,
        cadence: 'INTRADAY',
        notify_mode: 'EDGE_REARM',
        status: 'ACTIVE',
        summary: { short: '장중 · 현재가 ≥ 70,000원' },
        last_result: 'TRUE',
        unknown_reason: null,
        evaluated_as_of: '2026-09-26T10:15:00+09:00',
        last_fired_at: '2026-09-26T08:15:00+09:00',
      },
      {
        alert_id: 'a-unknown',
        name: 'SK하이닉스 박스권',
        instrument: { id: 'i-hynix', label: 'SK하이닉스', market: 'KR' },
        cadence: 'CLOSE',
        notify_mode: 'EDGE_REARM',
        status: 'ACTIVE',
        summary: { short: '종가 · 20일 박스권(폭 15% 이내) 상단 돌파' },
        last_result: 'UNKNOWN',
        unknown_reason: 'INSUFFICIENT_HISTORY',
        evaluated_as_of: '2026-09-25T15:30:00+09:00',
        last_fired_at: null,
      },
      {
        alert_id: 'a-paused',
        name: '애플 급등',
        instrument: APPLE,
        cadence: 'INTRADAY',
        notify_mode: 'EDGE_REARM',
        status: 'PAUSED',
        summary: { short: '미국 장중 · 5% 이상 상승' },
        last_result: 'FALSE',
        unknown_reason: null,
        evaluated_as_of: null,
        last_fired_at: null,
      },
      {
        alert_id: 'a-ended',
        name: 'NAVER 18만원',
        instrument: { id: 'i-naver', label: 'NAVER', market: 'KR' },
        cadence: 'INTRADAY',
        notify_mode: 'ONE_SHOT',
        status: 'ENDED',
        summary: { short: '장중 · 현재가 ≤ 180,000원' },
        last_result: 'TRUE',
        unknown_reason: null,
        evaluated_as_of: '2026-09-24T13:05:00+09:00',
        last_fired_at: '2026-09-24T13:05:12+09:00',
      },
      {
        alert_id: 'a-expired',
        name: '삼성전자 RSI',
        instrument: SAMSUNG,
        cadence: 'CLOSE',
        notify_mode: 'EDGE_REARM',
        status: 'EXPIRED',
        summary: { short: '종가 · RSI(14) 70 이상 진입' },
        last_result: 'FALSE',
        unknown_reason: null,
        evaluated_as_of: '2026-09-20T15:30:00+09:00',
        last_fired_at: null,
      },
    ],
    unread: [
      {
        event_id: 'e-1',
        title: '삼성전자 · 가격 도달',
        cadence: 'INTRADAY',
        market: 'KR',
        as_of: '2026-09-26T10:15:00+09:00',
        fired_at: '2026-09-26T10:15:41+09:00',
        alert_deleted: false,
      },
      {
        event_id: 'e-2',
        title: '카카오 · RSI 과매수',
        cadence: 'CLOSE',
        market: 'KR',
        as_of: '2026-09-26T15:30:00+09:00',
        fired_at: '2026-09-26T16:02:10+09:00',
        alert_deleted: true,
      },
      {
        event_id: 'e-3',
        title: '애플 · 급등락',
        cadence: 'CLOSE',
        market: 'US',
        as_of: '2026-09-27T05:00:00+09:00',
        fired_at: '2026-09-27T05:03:00+09:00',
        alert_deleted: false,
      },
    ],
    unread_more: 2,
  },
  empty_reason: null,
  notices: [
    {
      code: 'MARKET_DATA_DELAYED',
      severity: 'warn',
      message: '국내 장중 시세가 10:05 이후 들어오지 않았어요',
      params: { market: 'KR', kind: 'INTRADAY_QUOTE', last_done: '2026-09-26T10:05:00+09:00' },
    },
  ],
};

export const alertsEmptyFixture: AlertsResponse = {
  as_of: null,
  data: { rows: [], unread: [], unread_more: 0 },
  empty_reason: 'NO_ALERTS',
  notices: [],
};

/** 알림을 다 지웠지만 지운 알림의 미확인 발화가 남은 경우(§12.7). */
export const alertsEmptyWithUnreadFixture: AlertsResponse = {
  ...alertsEmptyFixture,
  data: { rows: [], unread: [alertsFixture.data.unread[1]], unread_more: 0 },
};

export const presetDetailFixture: AlertDetail = {
  alert_id: 'a-satisfied',
  name: '삼성전자 7만원',
  instrument: SAMSUNG,
  cadence: 'INTRADAY',
  notify_mode: 'EDGE_REARM',
  cooldown_min: null,
  expires_at: null,
  status: 'ACTIVE',
  trigger_type: 'PRESET',
  trigger_spec: { preset_key: 'price_reach', params: { direction: 'up', price: 70000 } },
  summary: { short: '장중 · 현재가 ≥ 70,000원', sentence: '장중에 현재가가 70,000원 이상이면 알려요' },
  last_result: 'TRUE',
  unknown_reason: null,
  evaluated_as_of: '2026-09-26T10:20:00+09:00',
  recent_events: [
    { event_id: 'e-1', title: '삼성전자 · 가격 도달', as_of: '2026-09-26T10:15:00+09:00', read: false },
    { event_id: 'e-0', title: '삼성전자 · 가격 도달', as_of: '2026-09-25T09:42:00+09:00', read: true },
  ],
};

/** 스펙 §13.5 — 장중, 직전 20일 최고 고가 돌파 10분 유지, 60분마다 다시, 연말까지. */
export const composableDetailFixture: AlertDetail = {
  alert_id: 'a-composable',
  name: '삼성전자 20일 고점 돌파',
  instrument: SAMSUNG,
  cadence: 'INTRADAY',
  notify_mode: 'COOLDOWN',
  cooldown_min: 60,
  expires_at: '2026-12-31T23:59:59+09:00',
  status: 'PAUSED',
  trigger_type: 'COMPOSABLE',
  trigger_spec: {
    conditions: [
      {
        left: { indicator: 'price', transform: { type: 'identity' } },
        op: 'gt',
        right: { indicator: 'high', transform: { type: 'window', fn: 'max', n: 20 } },
        modifier: { persist_min: 10 },
      },
      {
        left: { indicator: 'volume_ratio', indicator_params: { n: 20 }, transform: { type: 'identity' } },
        op: 'gte',
        right: { const: 2 },
        modifier: null,
      },
    ],
  },
  summary: {
    short: '장중 · 현재가 > 직전 20일 최고 고가 10분 유지 그리고 거래량 배수(20일) ≥ 2배',
    sentence: '장중에 현재가가 직전 20일 최고 고가 초과가 10분 이상 유지되고, 거래량 배수(20일)가 2배 이상이면 알려요',
  },
  last_result: null,
  unknown_reason: null,
  evaluated_as_of: null,
  recent_events: [],
};

export const expiredDetailFixture: AlertDetail = {
  ...presetDetailFixture,
  alert_id: 'a-expired',
  status: 'EXPIRED',
  expires_at: '2026-09-20T23:59:59+09:00',
  recent_events: [],
};

/** 지표 한 줄을 서버 모양으로. 변형 범위는 허용 변형에서 identity를 뺀 것마다 붙는다. */
function indicator(
  key: string,
  label: string,
  category: string,
  unit: CatalogIndicator['unit'],
  params: CatalogIndicator['params'],
  intradayLeft: boolean,
  markets: CatalogIndicator['markets'],
  transforms: [CatalogIndicator['allowed_transforms'][number], number, number][],
  operators: CatalogIndicator['allowed_operators'],
  scope: CatalogIndicator['scope'],
): CatalogIndicator {
  return {
    key,
    label,
    category,
    unit,
    params,
    intraday_left: intradayLeft,
    markets,
    allowed_transforms: transforms.map(([type]) => type),
    transform_ranges: Object.fromEntries(
      transforms.filter(([type]) => type !== 'identity').map(([type, min, max]) => [type, { min, max }]),
    ),
    allowed_operators: operators,
    scope,
    deprecated: false,
  };
}

const ALL_OPS: CatalogIndicator['allowed_operators'] = ['gte', 'lte', 'gt', 'lt', 'crosses_above', 'crosses_below'];
const COMPARE: CatalogIndicator['allowed_operators'] = ['gte', 'lte', 'gt', 'lt'];
const BOTH: CatalogIndicator['markets'] = ['KR', 'US'];
const FULL: [CatalogIndicator['allowed_transforms'][number], number, number][] = [
  ['identity', 0, 0],
  ['window', 1, 120],
  ['delta', 1, 120],
  ['pct', 1, 120],
];
const N = (d: number, min: number, max: number) => [{ key: 'n', default: d, min, max }];

export const catalogFixture: AlertCatalog = {
  indicators: [
    indicator('price', '가격', '시세', 'price', [], true, BOTH, FULL, ALL_OPS, 'market'),
    indicator('change_pct', '등락률', '시세', 'percent', [], true, BOTH, FULL, ALL_OPS, 'market'),
    indicator('volume', '거래량', '시세', 'shares', [], true, BOTH, FULL, ALL_OPS, 'market'),
    indicator('volume_ratio', '거래량 배수', '시세', 'ratio', N(20, 5, 120), true, BOTH, FULL, ALL_OPS, 'market'),
    indicator('high', '고가', '시세', 'price', [], false, BOTH, FULL, ALL_OPS, 'market'),
    indicator('low', '저가', '시세', 'price', [], false, BOTH, FULL, ALL_OPS, 'market'),
    indicator('range_pct', '가격 폭', '기술지표', 'percent', N(20, 5, 120), false, BOTH,
      [['identity', 0, 0], ['delta', 1, 120]], ALL_OPS, 'market'),
    indicator('sma', '이동평균', '기술지표', 'price', N(20, 2, 120), false, BOTH, FULL, ALL_OPS, 'market'),
    indicator('rsi', 'RSI', '기술지표', 'index', N(14, 2, 30), false, BOTH,
      [['identity', 0, 0], ['delta', 1, 5]], ALL_OPS, 'market'),
    indicator('disparity', '이격도', '기술지표', 'percent', N(20, 2, 120), false, BOTH,
      [['identity', 0, 0], ['delta', 1, 120]], ALL_OPS, 'market'),
    indicator('foreign_net_buy', '외국인 순매수', '수급', 'krw', [], false, ['KR'],
      [['identity', 0, 0], ['delta', 1, 5], ['window', 1, 10]], ALL_OPS, 'market'),
    indicator('institution_net_buy', '기관 순매수', '수급', 'krw', [], false, ['KR'],
      [['identity', 0, 0], ['delta', 1, 5], ['window', 1, 10]], ALL_OPS, 'market'),
    indicator('unrealized_pnl_pct', '평가손익률', '내 보유', 'percent', [], false, BOTH,
      [['identity', 0, 0]], COMPARE, 'user'),
    indicator('weight_pct', '비중', '내 보유', 'percent', [], false, BOTH, [['identity', 0, 0]], COMPARE, 'user'),
  ],
  presets: [
    {
      key: 'price_reach', label: '가격 도달', cadences: ['INTRADAY', 'CLOSE'], markets: BOTH, scope: 'market',
      param_schema: [
        { key: 'direction', kind: 'choice', min: null, max: null, default: 'up', choices: ['up', 'down'], required: false },
        { key: 'price', kind: 'decimal', min: 0.0001, max: 100000000, default: null, choices: [], required: true },
      ],
    },
    {
      key: 'change_move', label: '급등락', cadences: ['INTRADAY', 'CLOSE'], markets: BOTH, scope: 'market',
      param_schema: [
        { key: 'direction', kind: 'choice', min: null, max: null, default: 'up', choices: ['up', 'down'], required: false },
        { key: 'pct', kind: 'decimal', min: 0.1, max: 30, default: 5, choices: [], required: false },
      ],
    },
    {
      key: 'volume_surge', label: '거래량 급증', cadences: ['INTRADAY', 'CLOSE'], markets: BOTH, scope: 'market',
      param_schema: [
        { key: 'n', kind: 'int', min: 5, max: 120, default: 20, choices: [], required: false },
        { key: 'multiple', kind: 'decimal', min: 1.1, max: 50, default: 3, choices: [], required: false },
      ],
    },
    {
      key: 'ma_cross', label: '골든·데드크로스', cadences: ['CLOSE'], markets: BOTH, scope: 'market',
      param_schema: [
        { key: 'direction', kind: 'choice', min: null, max: null, default: 'golden', choices: ['golden', 'dead'], required: false },
        { key: 'short', kind: 'int', min: 2, max: 120, default: 5, choices: [], required: false },
        { key: 'long', kind: 'int', min: 2, max: 120, default: 20, choices: [], required: false },
      ],
    },
    {
      key: 'rsi_zone', label: 'RSI 과매수·과매도', cadences: ['CLOSE'], markets: BOTH, scope: 'market',
      param_schema: [
        { key: 'zone', kind: 'choice', min: null, max: null, default: 'overbought', choices: ['overbought', 'oversold'], required: false },
        { key: 'level', kind: 'decimal', min: 1, max: 99, default: 70, choices: [], required: false },
        { key: 'n', kind: 'int', min: 2, max: 30, default: 14, choices: [], required: false },
      ],
    },
    {
      key: 'box_breakout', label: '박스권 돌파', cadences: ['CLOSE'], markets: BOTH, scope: 'market',
      param_schema: [
        { key: 'window_days', kind: 'int', min: 5, max: 120, default: 20, choices: [], required: false },
        { key: 'max_range_pct', kind: 'decimal', min: 1, max: 100, default: 15, choices: [], required: false },
        { key: 'direction', kind: 'choice', min: null, max: null, default: 'up', choices: ['up', 'down'], required: false },
      ],
    },
    {
      key: 'investor_streak', label: '외국인·기관 연속 순매수', cadences: ['CLOSE'], markets: ['KR'], scope: 'market',
      param_schema: [
        { key: 'investor', kind: 'choice', min: null, max: null, default: 'foreign', choices: ['foreign', 'institution'], required: false },
        { key: 'side', kind: 'choice', min: null, max: null, default: 'buy', choices: ['buy', 'sell'], required: false },
        { key: 'days', kind: 'int', min: 1, max: 20, default: 3, choices: [], required: false },
      ],
    },
    {
      key: 'investor_turn', label: '외국인·기관 순매수 전환', cadences: ['CLOSE'], markets: ['KR'], scope: 'market',
      param_schema: [
        { key: 'investor', kind: 'choice', min: null, max: null, default: 'foreign', choices: ['foreign', 'institution'], required: false },
        { key: 'side', kind: 'choice', min: null, max: null, default: 'buy', choices: ['buy', 'sell'], required: false },
      ],
    },
    {
      key: 'pnl_reach', label: '수익률 도달', cadences: ['CLOSE'], markets: BOTH, scope: 'user',
      param_schema: [
        { key: 'direction', kind: 'choice', min: null, max: null, default: 'profit', choices: ['profit', 'loss'], required: false },
        { key: 'pct', kind: 'decimal', min: -1000, max: 1000, default: 10, choices: [], required: false },
      ],
    },
  ],
  transforms: [
    { key: 'identity', label: '그대로', fns: [] },
    {
      key: 'window',
      label: '최근 N일',
      fns: [
        { key: 'max', label: '최고' },
        { key: 'min', label: '최저' },
        { key: 'avg', label: '평균' },
        { key: 'sum', label: '합계' },
      ],
    },
    { key: 'delta', label: 'N일 전 대비 변화', fns: [] },
    { key: 'pct', label: 'N일 전 대비 변화율', fns: [] },
  ],
  operators: [
    { key: 'gte', symbol: '≥', word: '이상' },
    { key: 'lte', symbol: '≤', word: '이하' },
    { key: 'gt', symbol: '>', word: '초과' },
    { key: 'lt', symbol: '<', word: '미만' },
    { key: 'crosses_above', symbol: '상향 돌파', word: '상향 돌파하면' },
    { key: 'crosses_below', symbol: '하향 이탈', word: '하향 이탈하면' },
  ],
};

export const previewFixture: PreviewResponse = {
  valid: true,
  errors: [],
  summary: { short: '장중 · 현재가 ≥ 63,010원', sentence: '장중에 현재가가 63,010원 이상이면 알려요' },
  current: {
    result: 'TRUE',
    as_of: '2026-09-25T15:30:00+09:00',
    header: '9/25 종가 기준',
    result_text: '충족하고 있어요',
    conditions: [{ result: 'TRUE', unknown_reason: null, text: '현재가 63,010원 ≥ 63,010원' }],
  },
  already_satisfied: true,
  duplicate_of: null,
};

export const previewInvalidFixture: PreviewResponse = {
  valid: false,
  errors: [{ path: 'trigger_spec.params.price', code: 'REQUIRED', message: '가격을 입력해 주세요' }],
  summary: null,
  current: null,
  already_satisfied: false,
  duplicate_of: null,
};

export const heldFixture: InstrumentSearchResponse = {
  rows: [
    { id: 'i-naver', label: 'NAVER', symbol: '035420', market: 'KR', held: true, last_close: 200000, last_close_on: '2026-09-24' },
    { id: SAMSUNG.id, label: '삼성전자', symbol: '005930', market: 'KR', held: true, last_close: 63010, last_close_on: '2026-09-25' },
    { id: APPLE.id, label: '애플', symbol: 'AAPL', market: 'US', held: true, last_close: 230.1, last_close_on: '2026-09-25' },
  ],
};

export const instrumentsFixture: InstrumentSearchResponse = {
  rows: [
    { id: 'i-sdi', label: '삼성SDI', symbol: '006400', market: 'KR', held: false, last_close: null, last_close_on: null },
    { id: SAMSUNG.id, label: '삼성전자', symbol: '005930', market: 'KR', held: true, last_close: 63010, last_close_on: '2026-09-25' },
  ],
};

export const eventsFixture: AlertEventsResponse = {
  as_of: '2026-09-26T10:15:00+09:00',
  data: {
    rows: [
      {
        event_id: 'e-1', alert_id: 'a-satisfied', title: '삼성전자 · 가격 도달',
        body: '현재가 70,200원 ≥ 70,000원 · 10:15 기준', cadence: 'INTRADAY', market: 'KR',
        as_of: '2026-09-26T10:15:00+09:00', fired_at: '2026-09-26T10:15:41+09:00', read: false, alert_deleted: false,
      },
      {
        event_id: 'e-9', alert_id: 'a-gone', title: 'LG에너지솔루션 · 급등락',
        body: '등락률 −6.1% ≤ −5% · 9/20 종가 기준', cadence: 'CLOSE', market: 'KR',
        as_of: '2026-09-20T15:30:00+09:00', fired_at: '2026-09-20T16:05:00+09:00', read: true, alert_deleted: true,
      },
    ],
    next_cursor: 'cursor-2',
  },
  empty_reason: null,
  notices: [],
};

export const eventsEmptyFixture: AlertEventsResponse = {
  as_of: null,
  data: { rows: [], next_cursor: null },
  empty_reason: 'NO_EVENTS',
  notices: [],
};

export const eventDetailFixture: AlertEventDetail = {
  event_id: 'e-1',
  title: '삼성전자 · 가격 도달',
  body: '현재가 70,200원 ≥ 70,000원 · 10:15 기준',
  lines: ['현재가 70,200원 ≥ 70,000원'],
  as_of: '2026-09-26T10:15:00+09:00',
  fired_at: '2026-09-26T10:15:41+09:00',
  observed: { price: 70200, threshold: 70000 },
  read_at: null,
  cadence: 'INTRADAY',
  market: 'KR',
  alert: {
    alert_id: 'a-satisfied',
    name: '삼성전자 7만원',
    cadence: 'INTRADAY',
    notify_mode: 'EDGE_REARM',
    status: 'ACTIVE',
    last_result: 'FALSE',
    unknown_reason: null,
    deleted: false,
    instrument: { id: SAMSUNG.id, label: '삼성전자' },
  },
};

export const deletedEventDetailFixture: AlertEventDetail = {
  ...eventDetailFixture,
  event_id: 'e-9',
  read_at: '2026-09-21T09:00:00+09:00',
  alert: { ...eventDetailFixture.alert, alert_id: 'a-gone', deleted: true },
};
```

- [ ] **Step 7: 실패하는 테스트를 쓴다**

`front-end/src/__tests__/alertApi.test.tsx`:

```tsx
import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react-native';

import { setAccessToken } from '@/api/client';
import { resumeAlert, searchInstruments } from '@/api/alertEndpoints';
import type { PreviewRequest, PreviewResponse } from '@/api/alertTypes';
import { usePreview } from '@/api/queries/usePreview';
import { useUnreadCount } from '@/api/queries/useUnreadCount';
import { previewFixture } from '@/fixtures/alerts';
import { serveRoutes } from '@/testing/serveRoutes';

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

/** 이름만 다른 초안. 미리보기 응답이 어느 요청의 것인지 짧은 형으로 돌려받아 가른다. */
function draft(name: string): PreviewRequest {
  return {
    instrument_id: 'i-1',
    name,
    cadence: 'CLOSE',
    notify_mode: 'EDGE_REARM',
    cooldown_min: null,
    expires_at: null,
    trigger_type: 'PRESET',
    trigger_spec: { preset_key: 'price_reach', params: { direction: 'up', price: 1 } },
  };
}

function echo(requestBody: unknown): PreviewResponse {
  const name = (requestBody as PreviewRequest).name;
  return { ...previewFixture, summary: { short: name, sentence: name } };
}

beforeEach(() => setAccessToken('tok'));
afterEach(() => setAccessToken(null));

describe('경로', () => {
  it('검색어가 없으면 보유 종목 구역을 받는다', async () => {
    const calls = serveRoutes([{ path: '/instruments', body: { rows: [] } }]);
    await searchInstruments('', true);
    await searchInstruments('삼성', false);
    expect(calls[0].url).toBe('http://api.test:8080/instruments?held=true');
    expect(calls[1].url).toBe(`http://api.test:8080/instruments?q=${encodeURIComponent('삼성')}`);
  });

  it('다시 켜기는 만료된 알림에만 유효기간을 싣는다 — null은 무기한이다', async () => {
    const calls = serveRoutes([{ method: 'POST', path: '/alerts/a1/resume', status: 204 }]);
    await resumeAlert('a1');
    await resumeAlert('a1', null);
    expect(calls[0].body).toBeUndefined();
    expect(calls[1].body).toEqual({ expires_at: null });
  });
});

describe('usePreview', () => {
  it('입력이 가라앉은 뒤 마지막 초안만 보낸다', async () => {
    const calls = serveRoutes([{ method: 'POST', path: '/alerts/preview', body: echo }]);

    const { result, rerender } = await renderHook(
      ({ request }: { request: PreviewRequest }) => usePreview(request, { debounceMs: 30 }),
      { wrapper, initialProps: { request: draft('A') } },
    );
    await rerender({ request: draft('AB') });

    await waitFor(() => expect(result.current.preview?.summary?.short).toBe('AB'));
    expect(calls.filter((c) => c.path === '/alerts/preview')).toHaveLength(1);
  });

  /** Review Focus 1 — 앞 요청이 늦게 와도 지금 입력의 결과를 덮지 못한다. */
  it('늦게 도착한 앞 응답이 새 결과를 덮지 않는다', async () => {
    const gates: Record<string, () => void> = {};
    serveRoutes([
      {
        method: 'POST',
        path: '/alerts/preview',
        body: echo,
        wait: (requestBody) =>
          new Promise<void>((resolve) => {
            gates[(requestBody as PreviewRequest).name] = resolve;
          }),
      },
    ]);

    const { result, rerender } = await renderHook(
      ({ request }: { request: PreviewRequest }) => usePreview(request, { debounceMs: 0 }),
      { wrapper, initialProps: { request: draft('A') } },
    );
    await waitFor(() => expect(gates.A).toBeDefined());
    await rerender({ request: draft('B') });
    await waitFor(() => expect(gates.B).toBeDefined());

    await act(async () => gates.B());
    await waitFor(() => expect(result.current.preview?.summary?.short).toBe('B'));
    await act(async () => gates.A());

    expect(result.current.preview?.summary?.short).toBe('B');
  });

  it('초안이 없으면 부르지 않는다', async () => {
    const calls = serveRoutes([]);
    const { result } = await renderHook(() => usePreview(null, { debounceMs: 0 }), { wrapper });
    await act(async () => undefined);
    expect(calls).toHaveLength(0);
    expect(result.current.preview).toBeNull();
  });
});

describe('useUnreadCount', () => {
  it('서버가 준 수를 쓴다', async () => {
    serveRoutes([{ path: '/alert-events/unread-count', body: { count: 3 } }]);
    const { result } = await renderHook(() => useUnreadCount(), { wrapper });
    await waitFor(() => expect(result.current).toBe(3));
  });

  it('경로가 없으면(404) 0이다', async () => {
    serveRoutes([]);
    const { result } = await renderHook(() => useUnreadCount(), { wrapper });
    await act(async () => undefined);
    expect(result.current).toBe(0);
  });
});
```

- [ ] **Step 8: 테스트가 실패하는지 본다**

Step 7을 Step 1~6보다 먼저 쓴 경우: Run: `npx jest src/__tests__/alertApi.test.tsx` → Expected: FAIL `Cannot find module '@/api/alertEndpoints'`. 이미 구현을 썼다면 Step 9로 간다.

- [ ] **Step 9: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest src/__tests__/alertApi.test.tsx && npx tsc --noEmit`
Expected: PASS. `catalogFixture`의 `transform_ranges`가 `Object.fromEntries`로 넓혀져 타입 오류가 나면 `as CatalogIndicator['transform_ranges']`로 단언한다.

- [ ] **Step 10: 커밋한다**

```bash
git add src/api src/fixtures/alerts.ts src/testing/serveRoutes.ts src/__tests__/alertApi.test.tsx
git commit -m "feat: 알림 API의 타입·경로·조회 훅과 계약 모양 픽스처를 둔다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 표기와 공용 부품 — 기준 표기 · 울린 시각 · 상태 배지 · 확인 시트 · 날짜 칸

**Files:**
- Create: `front-end/src/format/alertTime.ts`
- Modify: `front-end/src/format/number.ts` (`formatKrwReading`)
- Modify: `front-end/src/design/theme.ts` (배지·상태 배지 색)
- Create: `front-end/src/screens/alerts/status.ts` · `labels.ts` · `expiry.ts`
- Create: `front-end/src/screens/alerts/StatusBadge.tsx` · `ExpirySheet.tsx`
- Create: `front-end/src/ui/ConfirmSheet.tsx` · `front-end/src/ui/TextButton.tsx` · `front-end/src/ui/DateField.tsx`
- Modify: `front-end/src/ui/PeriodControl.tsx` (DateField를 가져다 씀)
- Test: `front-end/src/__tests__/alertFormat.test.tsx`

**Interfaces:**
- Consumes: `Cadence` · `Market` · `UnknownReason` · `AlertStatus` · `Truth` (Task 3)
- Produces:
  - `basisLabel(asOf: string | null | undefined, cadence: Cadence, market: Market | null | undefined, opts?: { withDate?: boolean }): string` — `10:15` · `9/26 10:15` · `9/26 종가` · `미국 장중 · 02:15` · `미국 9/26 종가`
  - `firedAtLabel(firedAt: string, now?: Date): string` — `방금` · `N분 전` · `N시간 전` · `9/24 13:05`
  - `clockLabel(iso: string): string` — `10:15:41`
  - `formatKrwReading(v: number | null | undefined): string` — `= 1,000억원`
  - `statusOf(a: StatusInput): { label: string; tone: 'watching' | 'satisfied' | 'muted' }`, `type StatusInput = { status: AlertStatus; last_result: Truth | null; unknown_reason: UnknownReason | null }`
  - `cadenceLabel(c)` · `notifyModeLabel(mode, cooldownMin)` · `expiryLabel(expiresAt)`
  - `type ExpiryChoice = 'NONE' | '1W' | '1M' | '3M' | 'DATE'` · `EXPIRY_CHOICES` · `expiresAtFor(choice, date, now): string | null`
  - `<StatusBadge alert={StatusInput} />` · `<ExpirySheet visible busy onClose onConfirm(expiresAt: string | null) />`
  - `<ConfirmSheet visible title message? confirmLabel cancelLabel? busy? onConfirm onCancel />` · `<TextButton label onPress disabled? accessibilityLabel? />` · `<DateField label value onChange min? max? />`
  - 팔레트: `badge` · `onBadge` · `statusWatchingBg` · `statusWatchingText` · `statusSatisfiedBg` · `statusSatisfiedText`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`front-end/src/__tests__/alertFormat.test.tsx`:

```tsx
import { fireEvent, screen } from '@testing-library/react-native';

import { basisLabel, clockLabel, firedAtLabel } from '@/format/alertTime';
import { formatKrwReading } from '@/format/number';
import { expiresAtFor } from '@/screens/alerts/expiry';
import { expiryLabel, notifyModeLabel } from '@/screens/alerts/labels';
import { statusOf } from '@/screens/alerts/status';
import { renderScreen } from '@/testing/renderScreen';
import { ConfirmSheet } from '@/ui/ConfirmSheet';

describe('basisLabel — 데이터 시점 표기 (§12.6)', () => {
  it('국내 장중은 시각, 날짜를 붙일 수도 있다', () => {
    expect(basisLabel('2026-09-26T10:15:00+09:00', 'INTRADAY', 'KR')).toBe('10:15');
    expect(basisLabel('2026-09-26T10:15:00+09:00', 'INTRADAY', 'KR', { withDate: true })).toBe('9/26 10:15');
  });

  it('국내 종가는 거래일', () => {
    expect(basisLabel('2026-09-26T15:30:00+09:00', 'CLOSE', 'KR')).toBe('9/26 종가');
  });

  it('미국 장중은 한국 시각', () => {
    expect(basisLabel('2026-09-27T02:15:00+09:00', 'INTRADAY', 'US')).toBe('미국 장중 · 02:15');
  });

  /** Review Focus 4 — 미국 종가의 as_of는 한국 시각으로 다음 날 새벽이다. */
  it('미국 종가는 미국 거래일이다', () => {
    expect(basisLabel('2026-09-27T05:00:00+09:00', 'CLOSE', 'US')).toBe('미국 9/26 종가');
    // 서머타임이 끝난 뒤에는 06:00이다.
    expect(basisLabel('2026-12-01T06:00:00+09:00', 'CLOSE', 'US')).toBe('미국 11/30 종가');
  });

  it('값이 없으면 대시', () => {
    expect(basisLabel(null, 'CLOSE', 'KR')).toBe('—');
  });
});

describe('firedAtLabel — 울린 시각 (§12.6)', () => {
  const now = new Date('2026-09-26T12:15:41+09:00');

  it('24시간 안은 얼마 전', () => {
    expect(firedAtLabel('2026-09-26T12:15:21+09:00', now)).toBe('방금');
    expect(firedAtLabel('2026-09-26T11:45:41+09:00', now)).toBe('30분 전');
    expect(firedAtLabel('2026-09-26T10:15:41+09:00', now)).toBe('2시간 전');
  });

  it('그 밖은 날짜와 시각', () => {
    expect(firedAtLabel('2026-09-24T13:05:12+09:00', now)).toBe('9/24 13:05');
  });

  it('초까지 적는 시각', () => {
    expect(clockLabel('2026-09-26T10:15:41+09:00')).toBe('10:15:41');
  });
});

describe('formatKrwReading — 수급 금액 읽기용 환산', () => {
  it.each([
    [100_000_000_000, '= 1,000억원'],
    [150_000_000, '= 1.5억원'],
    [-300_000_000, '= −3억원'],
    [45_000_000, '= 4,500만원'],
    [5_000, '= 5,000원'],
  ])('%p → %s', (v, text) => {
    expect(formatKrwReading(v)).toBe(text);
  });
});

describe('statusOf — 카드 문구 (§6.5)', () => {
  const base = { last_result: null, unknown_reason: null } as const;

  it.each([
    [{ ...base, status: 'ACTIVE', last_result: 'TRUE' }, '조건 충족 중', 'satisfied'],
    [{ ...base, status: 'ACTIVE', last_result: 'FALSE' }, '감시 중', 'watching'],
    [{ ...base, status: 'ACTIVE' }, '감시 중', 'watching'],
    [{ ...base, status: 'ACTIVE', last_result: 'UNKNOWN', unknown_reason: 'NO_TRADE' }, '확인 불가 · 거래 없음', 'muted'],
    [{ ...base, status: 'PAUSED', last_result: 'TRUE' }, '꺼짐', 'muted'],
    [{ ...base, status: 'ENDED' }, '울린 뒤 종료', 'muted'],
    [{ ...base, status: 'EXPIRED' }, '만료', 'muted'],
  ] as const)('%o → %s', (input, label, tone) => {
    expect(statusOf(input)).toEqual({ label, tone });
  });
});

describe('공통 설정 문구', () => {
  it('알림 방식과 유효기간', () => {
    expect(notifyModeLabel('EDGE_REARM', null)).toBe('돌파할 때마다');
    expect(notifyModeLabel('ONE_SHOT', null)).toBe('한 번만');
    expect(notifyModeLabel('COOLDOWN', 60)).toBe('60분마다 다시');
    expect(expiryLabel(null)).toBe('무기한');
    expect(expiryLabel('2026-12-31T23:59:59+09:00')).toBe('2026-12-31까지');
  });
});

describe('expiresAtFor — 유효기간 선택지를 시각으로', () => {
  // 한국 시각 2026-10-11 12:00
  const now = new Date('2026-10-11T03:00:00Z');

  it.each([
    ['NONE', '', null],
    ['1W', '', '2026-10-18T12:00:00+09:00'],
    ['1M', '', '2026-11-11T12:00:00+09:00'],
    ['3M', '', '2027-01-11T12:00:00+09:00'],
    ['DATE', '2026-12-31', '2026-12-31T23:59:59+09:00'],
  ] as const)('%s %s → %s', (choice, date, expected) => {
    expect(expiresAtFor(choice, date, now)).toBe(expected);
  });

  it('형식에 맞지 않는 날짜는 글자 그대로 보내 서버가 칸 오류로 답하게 한다', () => {
    expect(expiresAtFor('DATE', '2026-13', now)).toBe('2026-13');
  });
});

describe('ConfirmSheet', () => {
  it('두 버튼이 각자의 동작을 부른다', async () => {
    const onConfirm = jest.fn();
    const onCancel = jest.fn();
    await renderScreen(
      <ConfirmSheet
        visible
        title="이 알림을 삭제할까요?"
        message="울린 기록은 남아요"
        confirmLabel="삭제"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );

    expect(screen.getByText('울린 기록은 남아요')).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: '삭제' }));
    await fireEvent.press(screen.getByRole('button', { name: '취소' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: 테스트가 실패하는지 본다**

Run: `npx jest src/__tests__/alertFormat.test.tsx`
Expected: FAIL — `Cannot find module '@/format/alertTime'`.

- [ ] **Step 3: 표기 함수를 쓴다**

`front-end/src/format/alertTime.ts`:

```ts
import type { Cadence, Market } from '@/api/alertTypes';
import { EM_DASH } from '@/format/number';

/**
 * 알림의 시각 표기 (§12.6). 서버 시각은 `+09:00` 오프셋 문자열이고, 글자 그대로 잘라
 * 한국 시각으로 읽는다. 예외는 미국 종가의 거래일 하나다(아래).
 */

const STAMP = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/;

function parts(iso: string) {
  const m = STAMP.exec(iso);
  if (!m) return null;
  return { month: Number(m[2]), day: Number(m[3]), hh: m[4], mm: m[5], ss: m[6] ?? '00' };
}

/**
 * 미국 종목의 거래일.
 *
 * 미국 종가의 데이터 시점은 미국 장 마감(16:00 ET)이고, 한국 시각으로는 다음 날 05:00·06:00이다.
 * 글자를 자르면 하루 밀린다. 장 마감은 UTC로 같은 날 20:00·21:00이므로 UTC 날짜가 미국 거래일이다.
 */
function usTradingDay(iso: string): { month: number; day: number } | null {
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return null;
  const utc = new Date(ms);
  return { month: utc.getUTCMonth() + 1, day: utc.getUTCDate() };
}

/**
 * 데이터 시점 표기. 뒤에 `기준`을 붙이는 것은 쓰는 쪽이다 — 새로 울린 알림 블록은 붙이지 않는다.
 * 장중은 `10:15`, 종가는 `9/26 종가`, 미국은 앞에 `미국`을 단다.
 */
export function basisLabel(
  asOf: string | null | undefined,
  cadence: Cadence,
  market: Market | null | undefined,
  opts?: { withDate?: boolean },
): string {
  if (!asOf) return EM_DASH;
  const p = parts(asOf);
  if (!p) return EM_DASH;
  const us = market === 'US';

  if (cadence === 'CLOSE') {
    if (!us) return `${p.month}/${p.day} 종가`;
    const day = usTradingDay(asOf);
    return day ? `미국 ${day.month}/${day.day} 종가` : EM_DASH;
  }

  const clock = opts?.withDate ? `${p.month}/${p.day} ${p.hh}:${p.mm}` : `${p.hh}:${p.mm}`;
  return us ? `미국 장중 · ${clock}` : clock;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** 울린 시각. 24시간 안이면 `2시간 전`, 그 밖은 `9/24 13:05`. 1분이 안 되면 `방금`. */
export function firedAtLabel(firedAt: string, now: Date = new Date()): string {
  const ms = Date.parse(firedAt);
  const diff = now.getTime() - ms;
  if (!Number.isNaN(ms) && diff >= 0 && diff < DAY) {
    if (diff < MINUTE) return '방금';
    if (diff < HOUR) return `${Math.floor(diff / MINUTE)}분 전`;
    return `${Math.floor(diff / HOUR)}시간 전`;
  }
  const p = parts(firedAt);
  return p ? `${p.month}/${p.day} ${p.hh}:${p.mm}` : EM_DASH;
}

/** 초까지 적는 시각 — 울린 알림 상세의 `10:15:41 울림`. */
export function clockLabel(iso: string): string {
  const p = parts(iso);
  return p ? `${p.hh}:${p.mm}:${p.ss}` : EM_DASH;
}
```

`format/number.ts` 끝에 더한다.

```ts
/** 소수 첫째 자리까지, 떨어지면 정수로 — `1.5` · `1,000`. */
function upToOneDecimal(v: number): string {
  const { text } = roundToFixed(v, 1);
  const trimmed = text.endsWith('.0') ? text.slice(0, -2) : text;
  return withGrouping(trimmed);
}

/**
 * 원 단위로 입력한 큰 금액을 읽기 쉽게 다시 적는다 — `= 1,000억원`, `= 4,500만원`.
 * 수급 금액 입력칸 아래에 둔다(§12.5.4). 입력칸 자체는 원 단위 그대로다.
 */
export function formatKrwReading(v: number | null | undefined): string {
  if (isNil(v)) return EM_DASH;
  const abs = Math.abs(v);
  const sign = v < 0 ? MINUS : '';
  if (abs >= 100_000_000) return `= ${sign}${upToOneDecimal(abs / 100_000_000)}억원`;
  if (abs >= 10_000) return `= ${sign}${upToOneDecimal(abs / 10_000)}만원`;
  return `= ${formatKrw(v, { suffix: true })}`;
}
```

- [ ] **Step 4: 색 토큰을 더한다**

`design/theme.ts`의 `light`에서 `chart` 앞에 넣는다.

```ts
  /**
   * 탭 배지와 미확인 점. 빨강은 상승으로, 앱 강조색은 하락 파랑과 가까워 하락으로 읽힌다.
   * 그래서 증감색·상태 배지색과 겹치지 않는 배지 전용 색을 둔다(알림 스펙 §12.6).
   */
  badge: '#7C3AED',
  onBadge: '#FFFFFF',
  /** 알림 상태 배지. 감시 중은 초록, 조건 충족 중은 노랑. 나머지는 surface·textMuted를 쓴다. */
  statusWatchingBg: '#E7F6EC',
  statusWatchingText: '#1B7F3B',
  statusSatisfiedBg: '#FFF4CC',
  statusSatisfiedText: '#7A5B00',
```

- [ ] **Step 5: 상태·문구·유효기간 함수를 쓴다**

`front-end/src/screens/alerts/status.ts`:

```ts
import type { AlertStatus, Truth, UnknownReason } from '@/api/alertTypes';

/** 카드·상세·울린 알림 상세의 상태 배지 문구 (§6.5 · §7.2). */

export type StatusInput = {
  status: AlertStatus;
  last_result: Truth | null;
  unknown_reason: UnknownReason | null;
};

export type StatusTone = 'watching' | 'satisfied' | 'muted';

const REASON: Record<UnknownReason, string> = {
  DATA_MISSING: '데이터 없음',
  INSUFFICIENT_HISTORY: '이력 부족',
  NO_TRADE: '거래 없음',
  PRICE_ADJUSTMENT_SUSPECTED: '가격 보정 대기',
  NOT_HELD: '미보유',
  INSTRUMENT_UNKNOWN: '종목 정보 없음',
};

export function statusOf(alert: StatusInput): { label: string; tone: StatusTone } {
  switch (alert.status) {
    case 'PAUSED':
      return { label: '꺼짐', tone: 'muted' };
    case 'ENDED':
      return { label: '울린 뒤 종료', tone: 'muted' };
    case 'EXPIRED':
      return { label: '만료', tone: 'muted' };
    case 'ACTIVE':
      if (alert.last_result === 'TRUE') return { label: '조건 충족 중', tone: 'satisfied' };
      if (alert.last_result === 'UNKNOWN') {
        const reason = alert.unknown_reason ? REASON[alert.unknown_reason] : null;
        return { label: reason ? `확인 불가 · ${reason}` : '확인 불가', tone: 'muted' };
      }
      return { label: '감시 중', tone: 'watching' };
  }
}
```

`front-end/src/screens/alerts/labels.ts`:

```ts
import type { Cadence, NotifyMode } from '@/api/alertTypes';
import { formatDate } from '@/format/date';

/** 알림 상세의 속성 줄 문구 (§12.4 · IA §6.2). */

export function cadenceLabel(cadence: Cadence): string {
  return cadence === 'INTRADAY' ? '장중' : '종가';
}

export function notifyModeLabel(mode: NotifyMode, cooldownMin: number | null): string {
  if (mode === 'ONE_SHOT') return '한 번만';
  if (mode === 'COOLDOWN') return `${cooldownMin ?? ''}분마다 다시`;
  return '돌파할 때마다';
}

export function expiryLabel(expiresAt: string | null): string {
  return expiresAt ? `${formatDate(expiresAt)}까지` : '무기한';
}
```

`front-end/src/screens/alerts/expiry.ts`:

```ts
/**
 * 유효기간 선택지 (§12.5.5). 공통 설정과 만료된 알림의 `다시 켜기` 시트가 함께 쓴다.
 * 시각은 한국 시각 `+09:00`로 만든다 — 서버 응답과 같은 모양이라 화면이 같은 규칙으로 읽는다.
 */

export type ExpiryChoice = 'NONE' | '1W' | '1M' | '3M' | 'DATE';

export const EXPIRY_CHOICES: { value: ExpiryChoice; label: string }[] = [
  { value: 'NONE', label: '무기한' },
  { value: '1W', label: '1주' },
  { value: '1M', label: '1개월' },
  { value: '3M', label: '3개월' },
  { value: 'DATE', label: '날짜 지정' },
];

const KST = 9 * 60 * 60 * 1000;
const DAY = 24 * 60 * 60 * 1000;
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

/** 한국 시각의 벽시계를 UTC 필드로 들고 있는 Date를 `+09:00` 문자열로. */
function kstIso(wall: Date): string {
  return (
    `${wall.getUTCFullYear()}-${pad(wall.getUTCMonth() + 1)}-${pad(wall.getUTCDate())}` +
    `T${pad(wall.getUTCHours())}:${pad(wall.getUTCMinutes())}:${pad(wall.getUTCSeconds())}+09:00`
  );
}

/**
 * 선택지를 `expires_at` 값으로. 무기한은 null.
 * 날짜 지정은 그날 끝(23:59:59)까지다. 형식에 맞지 않는 날짜는 글자 그대로 돌려줘
 * 서버가 `expires_at` 칸 오류로 답하게 한다 — 조용히 무기한으로 바꾸지 않는다.
 */
export function expiresAtFor(choice: ExpiryChoice, date: string, now: Date): string | null {
  const wall = new Date(now.getTime() + KST);
  switch (choice) {
    case 'NONE':
      return null;
    case '1W':
      return kstIso(new Date(wall.getTime() + 7 * DAY));
    case '1M':
    case '3M': {
      const months = choice === '1M' ? 1 : 3;
      const next = new Date(wall.getTime());
      next.setUTCMonth(next.getUTCMonth() + months);
      return kstIso(next);
    }
    case 'DATE':
      return DATE_ONLY.test(date) ? `${date}T23:59:59+09:00` : date;
  }
}
```

- [ ] **Step 6: 공용 부품을 쓴다**

`front-end/src/ui/TextButton.tsx`:

```tsx
import { Pressable, StyleSheet, Text } from 'react-native';

import { useTheme } from '@/design/theme';
import { size, space } from '@/design/tokens';
import { type } from '@/design/typography';

/** 글자만 있는 버튼. `전체 →` · `수정` · `다시 켜기`처럼 자리를 적게 차지해야 하는 곳에 쓴다. */
export function TextButton({
  label,
  onPress,
  disabled = false,
  accessibilityLabel,
  tone = 'primary',
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  accessibilityLabel?: string;
  /** 지우기처럼 되돌릴 수 없는 동작은 오류색. */
  tone?: 'primary' | 'danger';
}) {
  const palette = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      hitSlop={(size.tap - 20) / 2}
      style={({ pressed }) => [styles.button, (pressed || disabled) && styles.dim]}
    >
      <Text style={[type.label, { color: tone === 'danger' ? palette.errorText : palette.primary }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: { paddingVertical: space.xs },
  dim: { opacity: 0.5 },
});
```

`front-end/src/ui/ConfirmSheet.tsx`:

```tsx
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '@/design/theme';
import { radius, screenPadding, size, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { Button } from '@/ui/Button';

/**
 * 두 갈래 확인. 삭제 확인 · 작성 중인 알림 버리기 · 평가 시점 전환 · 푸시 권한 안내가 쓴다.
 *
 * 시스템 대화상자(Alert.alert)를 쓰지 않는다 — 웹에서 그려지지 않고, 문구와 버튼 배치를
 * 앱의 다른 시트와 맞출 수 없다.
 */
export function ConfirmSheet({
  visible,
  title,
  message,
  confirmLabel,
  cancelLabel = '취소',
  busy = false,
  onConfirm,
  onCancel,
}: {
  visible: boolean;
  title: string;
  message?: string;
  confirmLabel: string;
  cancelLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const palette = useTheme();

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onCancel}>
      <Pressable
        accessibilityLabel="닫기"
        style={[styles.backdrop, { backgroundColor: palette.scrim }]}
        onPress={onCancel}
      />
      <View style={[styles.sheet, { backgroundColor: palette.bg }]}>
        <Text style={[type.title, { color: palette.text }]}>{title}</Text>
        {message && (
          <Text style={[type.body, styles.message, { color: palette.textMuted }]}>{message}</Text>
        )}
        <View style={styles.actions}>
          <Button label={confirmLabel} onPress={onConfirm} loading={busy} />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={cancelLabel}
            onPress={onCancel}
            style={styles.cancel}
          >
            <Text style={[type.body, { color: palette.textMuted }]}>{cancelLabel}</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1 },
  sheet: {
    borderTopLeftRadius: radius.card,
    borderTopRightRadius: radius.card,
    paddingHorizontal: screenPadding,
    paddingTop: space.xl,
    paddingBottom: space.xxl,
  },
  message: { marginTop: space.sm },
  actions: { marginTop: space.xl },
  cancel: { height: size.tap, alignItems: 'center', justifyContent: 'center', marginTop: space.sm },
});
```

`front-end/src/ui/DateField.tsx` — `PeriodControl.tsx`의 `DateField` 함수와 `styles.field`를 옮기고 `min`을 더한다. `fromIso` · `toIso`는 `@/ui/period`에서 가져온다.

```tsx
import { useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, TextInput } from 'react-native';
import DateTimePicker from '@react-native-community/datetimepicker';

import { useTheme } from '@/design/theme';
import { radius, size, space } from '@/design/tokens';
import { numeric, type } from '@/design/typography';
import { fromIso, toIso } from '@/ui/period';

/**
 * 날짜 한 칸 (`YYYY-MM-DD`).
 *
 * 기기에서는 눌러서 시스템 피커를 연다. 웹에는 그 피커가 없어(모듈이 아무것도
 * 그리지 않는다) 글자로 직접 친다 — 개발을 브라우저에서 하므로 빈 칸으로 둘 수 없다.
 */
export function DateField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: string;
  /** 고를 수 있는 첫날. 유효기간처럼 미래만 뜻이 있는 칸이 준다. */
  min?: string;
  /** 고를 수 있는 마지막 날. 기간 조회처럼 과거만 뜻이 있는 칸이 준다. */
  max?: string;
  onChange: (next: string) => void;
}) {
  const palette = useTheme();
  const [open, setOpen] = useState(false);

  const box = [styles.field, { borderColor: palette.border, backgroundColor: palette.surface }];

  if (Platform.OS === 'web') {
    return (
      <TextInput
        accessibilityLabel={label}
        value={value}
        placeholder="YYYY-MM-DD"
        placeholderTextColor={palette.textMuted}
        onChangeText={onChange}
        style={[...box, type.body, numeric, { color: palette.text }]}
      />
    );
  }

  return (
    <>
      <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={() => setOpen(true)} style={box}>
        <Text style={[type.body, numeric, { color: value ? palette.text : palette.textMuted }]}>
          {value || 'YYYY-MM-DD'}
        </Text>
      </Pressable>

      {open && (
        <DateTimePicker
          value={fromIso(value) ?? fromIso(min) ?? new Date()}
          mode="date"
          minimumDate={fromIso(min) ?? undefined}
          maximumDate={fromIso(max) ?? undefined}
          onChange={(_event, picked) => {
            setOpen(false);
            if (picked) onChange(toIso(picked));
          }}
        />
      )}
    </>
  );
}

const styles = StyleSheet.create({
  field: {
    flex: 1,
    height: size.chip,
    borderWidth: 1,
    borderRadius: radius.button,
    paddingHorizontal: space.md,
    justifyContent: 'center',
  },
});
```

`PeriodControl.tsx`에서 `DateField` 함수와 `styles.field`를 지우고 `import { DateField } from '@/ui/DateField';`를 더한다. 쓰던 자리는 그대로 `max={...}`를 넘긴다. 쓰지 않게 된 import(`DateTimePicker`, `Platform`, `TextInput`, `fromIso`, `toIso` 중 남은 사용처가 없는 것)를 지운다. 기존 `controls.test.tsx` · `realizedPnl.test.tsx`가 그대로 통과해야 한다.

`front-end/src/screens/alerts/StatusBadge.tsx`:

```tsx
import { StyleSheet, Text } from 'react-native';

import { useTheme } from '@/design/theme';
import { space } from '@/design/tokens';
import { type } from '@/design/typography';
import { type StatusInput, statusOf } from '@/screens/alerts/status';

/**
 * 알림 상태 배지. 증감색을 쓰지 않는다(§12.6).
 * 자르지 않는다 — 카드에서 말줄임하는 것은 종목명과 조건이고, 상태는 끝까지 읽혀야 한다.
 */
export function StatusBadge({ alert }: { alert: StatusInput }) {
  const palette = useTheme();
  const { label, tone } = statusOf(alert);
  const [bg, fg] =
    tone === 'watching'
      ? [palette.statusWatchingBg, palette.statusWatchingText]
      : tone === 'satisfied'
        ? [palette.statusSatisfiedBg, palette.statusSatisfiedText]
        : [palette.surface, palette.textMuted];

  return (
    <Text style={[type.micro, styles.badge, { backgroundColor: bg, color: fg }]}>
      {tone === 'muted' ? label : `● ${label}`}
    </Text>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexShrink: 0,
    borderRadius: 10,
    paddingHorizontal: space.sm,
    paddingVertical: 2,
    overflow: 'hidden',
  },
});
```

`front-end/src/screens/alerts/ExpirySheet.tsx`:

```tsx
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { space } from '@/design/tokens';
import { EXPIRY_CHOICES, type ExpiryChoice, expiresAtFor } from '@/screens/alerts/expiry';
import { BottomSheet } from '@/ui/BottomSheet';
import { Button } from '@/ui/Button';
import { Chip } from '@/ui/Chip';
import { DateField } from '@/ui/DateField';
import { todayIso } from '@/ui/period';

/** 만료된 알림을 다시 켤 때 새 유효기간을 고르는 시트 (§12.2 · §6.5). */
export function ExpirySheet({
  visible,
  busy,
  onClose,
  onConfirm,
}: {
  visible: boolean;
  busy: boolean;
  onClose: () => void;
  /** null이면 무기한. */
  onConfirm: (expiresAt: string | null) => void;
}) {
  const [choice, setChoice] = useState<ExpiryChoice>('NONE');
  const [date, setDate] = useState('');

  return (
    <BottomSheet visible={visible} title="유효기간" onClose={onClose}>
      <View style={styles.chips}>
        {EXPIRY_CHOICES.map((option) => (
          <Chip
            key={option.value}
            label={option.label}
            selected={option.value === choice}
            onPress={() => setChoice(option.value)}
          />
        ))}
      </View>
      {choice === 'DATE' && (
        <View style={styles.date}>
          <DateField label="만료 날짜" value={date} min={todayIso()} onChange={setDate} />
        </View>
      )}
      <View style={styles.action}>
        <Button
          label="다시 켜기"
          loading={busy}
          onPress={() => onConfirm(expiresAtFor(choice, date, new Date()))}
        />
      </View>
    </BottomSheet>
  );
}

const styles = StyleSheet.create({
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  date: { flexDirection: 'row', marginTop: space.md },
  action: { marginTop: space.lg },
});
```

- [ ] **Step 7: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest && npx tsc --noEmit`
Expected: 전부 PASS(기존 기간 컨트롤 테스트 포함).

- [ ] **Step 8: 커밋한다**

```bash
git add src/format src/design/theme.ts src/screens/alerts src/ui src/__tests__/alertFormat.test.tsx
git commit -m "feat: 알림의 시각·상태 표기와 확인 시트·날짜 칸을 둔다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 알림 탭 — 카드 목록 · 새로 울린 알림 블록 · 빈 상태 · 탭 배지

**Files:**
- Modify: `front-end/src/app/navigation/types.ts`
- Modify: `front-end/src/app/navigation/Tabs.tsx`
- Create: `front-end/src/screens/alerts/AlertsScreen.tsx`
- Create: `front-end/src/screens/alerts/AlertCard.tsx`
- Create: `front-end/src/screens/alerts/UnreadBlock.tsx`
- Test: `front-end/src/__tests__/alertsTab.test.tsx`

**Interfaces:**
- Consumes: `useAlerts` · `useUnreadCount` · `useAlertActions` (Task 3), `StatusBadge` · `ExpirySheet` · `TextButton` · `basisLabel` · `firedAtLabel` (Task 4), `ScreenFrame`의 `header` · `asOfPrefix` (Task 2)
- Produces:
  - `TabParamList.alerts: undefined`
  - `RootStackParamList`에 `alert: { alertId: string }` · `'alert-events': { alertId?: string } | undefined` · `'alert-event': { eventId: string }` · `'alert-editor': EditorStart`
  - `type EditorInstrument = { id: string; label: string; market: Market; held: boolean; lastClose: number | null; lastCloseOn: string | null }`
  - `type EditorStart = { mode: 'new'; instrument?: EditorInstrument } | { mode: 'edit'; alertId: string }`
  - `<AlertsScreen />` — 이 화면이 다른 화면을 여는 이름은 위 네 개다. 그 화면들의 등록은 Task 6·7·9가 한다.
  - `<AlertsScreen />`의 `aboveContent` 맨 앞 자리에 Task 12가 `<PushBanners />`를 꽂는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`front-end/src/__tests__/alertsTab.test.tsx`:

```tsx
import { NavigationContainer } from '@react-navigation/native';
import { fireEvent, screen, waitFor } from '@testing-library/react-native';

import { setAccessToken } from '@/api/client';
import { Tabs } from '@/app/navigation/Tabs';
import { goldenAssetChange, goldenSummary } from '@/fixtures/golden';
import {
  alertsEmptyFixture,
  alertsEmptyWithUnreadFixture,
  alertsFixture,
} from '@/fixtures/alerts';
import { AlertsScreen } from '@/screens/alerts/AlertsScreen';
import { renderWithNavigation } from '@/testing/renderWithNavigation';
import { renderWithQuery } from '@/testing/renderWithQuery';
import { type Route, serveRoutes } from '@/testing/serveRoutes';

const STACK = ['alert', 'alert-events', 'alert-event', 'alert-editor'];

beforeEach(() => setAccessToken('tok'));
afterEach(() => setAccessToken(null));

async function renderAlerts(routes: Route[]) {
  const calls = serveRoutes(routes);
  const moves: { name: string; params: unknown }[] = [];
  await renderWithNavigation(<AlertsScreen />, {
    others: STACK,
    onNavigate: (name, params) => moves.push({ name, params }),
  });
  return { calls, moves };
}

describe('알림 탭 — 카드와 블록', () => {
  it('카드 상태 6종 중 다섯과 조건 짧은 형을 그린다', async () => {
    await renderAlerts([{ path: '/alerts', body: alertsFixture }]);
    await waitFor(() => expect(screen.getByText('장중 · 현재가 ≥ 70,000원')).toBeTruthy());

    expect(screen.getByText('● 조건 충족 중')).toBeTruthy();
    expect(screen.getByText('확인 불가 · 이력 부족')).toBeTruthy();
    expect(screen.getByText('꺼짐')).toBeTruthy();
    expect(screen.getByText('울린 뒤 종료')).toBeTruthy();
    expect(screen.getByText('만료')).toBeTruthy();
    expect(screen.getByText('내 알림')).toBeTruthy();
  });

  it('새로 울린 알림은 제목과 기준 표기, 넘친 건수', async () => {
    await renderAlerts([{ path: '/alerts', body: alertsFixture }]);
    await waitFor(() => expect(screen.getByText('울린 알림 전체')).toBeTruthy());

    expect(screen.getByText('새로 울린 알림 3')).toBeTruthy();
    expect(screen.getByText('삼성전자 · 가격 도달 · 10:15')).toBeTruthy();
    expect(screen.getByText('카카오 · RSI 과매수 · 9/26 종가')).toBeTruthy();
    expect(screen.getByText('애플 · 급등락 · 미국 9/26 종가')).toBeTruthy();
    expect(screen.getByText('외 2건 →')).toBeTruthy();
  });

  it('데이터 지연 안내와 최근 평가 시각', async () => {
    await renderAlerts([{ path: '/alerts', body: alertsFixture }]);
    await waitFor(() => expect(screen.getByText('최근 평가 2026-09-26 10:15')).toBeTruthy());
    expect(screen.getByText('⚠ 국내 장중 시세가 10:05 이후 들어오지 않았어요')).toBeTruthy();
  });

  it('줄을 누르면 알맞은 화면으로 간다', async () => {
    const { moves } = await renderAlerts([{ path: '/alerts', body: alertsFixture }]);
    await waitFor(() => expect(screen.getByText('울린 알림 전체')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '삼성전자 · 가격 도달' }));
    expect(moves.at(-1)).toEqual({ name: 'alert-event', params: { eventId: 'e-1' } });

    await fireEvent.press(screen.getByText('외 2건 →'));
    expect(moves.at(-1)?.name).toBe('alert-events');

    await fireEvent.press(screen.getByRole('button', { name: '애플 애플 급등' }));
    expect(moves.at(-1)).toEqual({ name: 'alert', params: { alertId: 'a-paused' } });

    await fireEvent.press(screen.getByRole('button', { name: '＋ 새 알림' }));
    expect(moves.at(-1)).toEqual({ name: 'alert-editor', params: { mode: 'new' } });
  });
});

describe('알림 탭 — 빈 상태', () => {
  it('알림도 미확인 발화도 없으면 온보딩 — 지난 이력으로 가는 줄은 남는다', async () => {
    const { moves } = await renderAlerts([{ path: '/alerts', body: alertsEmptyFixture }]);
    await waitFor(() => expect(screen.getByText('아직 걸어 둔 알림이 없어요')).toBeTruthy());

    expect(screen.getByText('울린 알림 전체')).toBeTruthy();
    expect(screen.queryByText(/새로 울린 알림/)).toBeNull();
    await fireEvent.press(screen.getByRole('button', { name: '＋ 첫 알림 만들기' }));
    expect(moves.at(-1)).toEqual({ name: 'alert-editor', params: { mode: 'new' } });
  });

  it('알림이 없어도 지운 알림의 미확인 발화가 있으면 새로 울린 알림을 둔다', async () => {
    await renderAlerts([{ path: '/alerts', body: alertsEmptyWithUnreadFixture }]);
    await waitFor(() => expect(screen.getByText('아직 걸어 둔 알림이 없어요')).toBeTruthy());

    expect(screen.getByText('울린 알림 전체')).toBeTruthy();
    expect(screen.getByText('카카오 · RSI 과매수 · 9/26 종가')).toBeTruthy();
  });
});

describe('알림 탭 — 카드에서 끄고 켜기', () => {
  it('꺼진 알림의 토글을 켜면 다시 켜기를 부르고 목록을 다시 받는다', async () => {
    const { calls } = await renderAlerts([
      { path: '/alerts', body: alertsFixture },
      { method: 'POST', path: '/alerts/a-paused/resume', status: 204 },
    ]);
    await waitFor(() => expect(screen.getByText('꺼짐')).toBeTruthy());

    await fireEvent.press(screen.getByRole('switch', { name: '애플 급등 감시' }));

    await waitFor(() =>
      expect(calls.filter((c) => c.method === 'GET' && c.path === '/alerts')).toHaveLength(2),
    );
    const resume = calls.find((c) => c.path === '/alerts/a-paused/resume');
    expect(resume?.body).toBeUndefined();
  });

  it('만료된 알림은 유효기간을 골라 다시 켠다', async () => {
    const { calls } = await renderAlerts([
      { path: '/alerts', body: alertsFixture },
      { method: 'POST', path: '/alerts/a-expired/resume', status: 204 },
    ]);
    await waitFor(() => expect(screen.getByText('만료')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '삼성전자 RSI 다시 켜기' }));
    await fireEvent.press(screen.getByRole('button', { name: '다시 켜기' }));

    await waitFor(() =>
      expect(calls.find((c) => c.path === '/alerts/a-expired/resume')?.body).toEqual({ expires_at: null }),
    );
  });
});

describe('탭 배지', () => {
  const summaryRoutes: Route[] = [
    { path: '/portfolio/views/summary', body: goldenSummary },
    { path: '/portfolio/views/asset-change', body: goldenAssetChange },
  ];

  it('미확인 발화 수를 알림 탭에 단다', async () => {
    serveRoutes([...summaryRoutes, { path: '/alert-events/unread-count', body: { count: 3 } }]);
    await renderWithQuery(
      <NavigationContainer>
        <Tabs />
      </NavigationContainer>,
    );
    await waitFor(() => expect(screen.getByText('3')).toBeTruthy());
    expect(screen.getByText('알림')).toBeTruthy();
  });

  /** Review Focus 5 — 울린 알림 API가 아직 없는 서버. */
  it('배지 수를 받지 못하면 배지 없이 탭이 선다', async () => {
    serveRoutes(summaryRoutes);
    await renderWithQuery(
      <NavigationContainer>
        <Tabs />
      </NavigationContainer>,
    );
    await waitFor(() => expect(screen.getByText('총자산')).toBeTruthy());
    expect(screen.getByText('알림')).toBeTruthy();
    expect(screen.queryByText('3')).toBeNull();
  });
});
```

- [ ] **Step 2: 테스트가 실패하는지 본다**

Run: `npx jest src/__tests__/alertsTab.test.tsx`
Expected: FAIL — `Cannot find module '@/screens/alerts/AlertsScreen'`.

- [ ] **Step 3: 네비게이션 타입을 넓힌다**

`app/navigation/types.ts`:

```ts
import type { NavigatorScreenParams } from '@react-navigation/native';

import type { Market } from '@/api/alertTypes';
import type { PeriodValue } from '@/ui/period';

/**
 * 탭 이름.
 *
 * 자산 변화는 탭이 아니다. 요약의 `더보기 →`와 실현손익 하단 링크에서 들어가는
 * 스택 화면이라 탭바 자리를 차지하지 않는다.
 */
export type TabParamList = {
  summary: undefined;
  /** 어느 계좌만 볼지. 계좌별 화면의 행에서 계좌 하나를 걸고 들어온다. */
  positions: { account?: string[] } | undefined;
  /** 어느 축으로 열지. 요약의 `비중 →`이 시장 축을 지정해 들어온다. */
  allocation: { axis?: string } | undefined;
  accounts: undefined;
  /** 어느 기간으로 열지. 자산 변화의 `실현손익 뷰 →`가 그 화면의 기간을 들고 온다. */
  'realized-pnl': { period?: PeriodValue } | undefined;
  alerts: undefined;
};

/** 새 알림 흐름을 종목이 정해진 채로 열 때 넘기는 종목. 종목 상세가 생기면 그 화면이 넘긴다. */
export type EditorInstrument = {
  id: string;
  label: string;
  market: Market;
  held: boolean;
  /** 가격 도달의 가격 칸을 채우는 직전 종가와 그 거래일. 모르면 null. */
  lastClose: number | null;
  lastCloseOn: string | null;
};

/**
 * 새 알림 흐름을 어디서 시작하나 (IA §2.2).
 * `＋ 새 알림`은 종목 선택부터, 종목이 정해져 있으면 조건 선택부터, 수정은 입력 화면부터다.
 */
export type EditorStart =
  | { mode: 'new'; instrument?: EditorInstrument }
  | { mode: 'edit'; alertId: string };

/** 탭 묶음 위에 얹히는 화면들. */
export type RootStackParamList = {
  tabs: NavigatorScreenParams<TabParamList> | undefined;
  /** 어느 기간을 보러 왔는지. 없으면 이번 달로 연다. */
  'asset-change': PeriodValue | undefined;
  alert: { alertId: string };
  /** 알림 상세의 `전체 →`로 오면 그 알림의 발화만 본다. */
  'alert-events': { alertId?: string } | undefined;
  'alert-event': { eventId: string };
  /** 모달. 닫으면 들어온 자리로, 저장하면 알림 상세로 간다. */
  'alert-editor': EditorStart;
};
```

- [ ] **Step 4: 카드와 블록을 쓴다**

`front-end/src/screens/alerts/AlertCard.tsx`:

```tsx
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { AlertCard as AlertCardData } from '@/api/alertTypes';
import { useAlertActions } from '@/api/queries/useAlertActions';
import { useTheme } from '@/design/theme';
import { screenPadding, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { messageOf } from '@/envelope/ErrorState';
import { firedAtLabel } from '@/format/alertTime';
import { ExpirySheet } from '@/screens/alerts/ExpirySheet';
import { StatusBadge } from '@/screens/alerts/StatusBadge';
import { Badge } from '@/ui/Badge';
import { TextButton } from '@/ui/TextButton';
import { Toggle } from '@/ui/Toggle';

/**
 * 내 알림 카드 한 장 (§12.2).
 *
 * 1줄 종목명 · 시장 · 상태 / 2줄 조건 짧은 형 / 3줄 알림 이름 · 최근 울림.
 * 현재값을 두지 않는다 — 목록 전체를 계속 갱신해야 한다. 삭제도 여기서 하지 않는다 —
 * 밀어서 지우는 동작은 실수가 잦아 상세에서 확인을 거친다.
 */
export function AlertCard({ alert, onPress }: { alert: AlertCardData; onPress: () => void }) {
  const palette = useTheme();
  const { pause, resume } = useAlertActions(alert.alert_id);
  const [expiryOpen, setExpiryOpen] = useState(false);
  const busy = pause.isPending || resume.isPending;
  const failure = pause.error ?? resume.error;
  const instrumentLabel = alert.instrument.label ?? '종목 정보 없음';
  const third = alert.last_fired_at
    ? `${alert.name} · 최근 울림 ${firedAtLabel(alert.last_fired_at)}`
    : alert.name;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${instrumentLabel} ${alert.name}`}
      onPress={onPress}
      style={({ pressed }) => [styles.card, { borderBottomColor: palette.border }, pressed && styles.pressed]}
    >
      <View style={styles.body}>
        <View style={styles.titleRow}>
          <Text numberOfLines={1} style={[type.body, styles.title, { color: palette.text }]}>
            {instrumentLabel}
          </Text>
          {alert.instrument.market && <Badge label={alert.instrument.market} />}
          <View style={styles.spacer} />
          <StatusBadge alert={alert} />
        </View>
        <Text numberOfLines={1} style={[type.label, styles.line, { color: palette.text }]}>
          {alert.summary.short}
        </Text>
        <Text numberOfLines={1} style={[type.caption, styles.line, { color: palette.textMuted }]}>
          {third}
        </Text>
        {failure && (
          <Text style={[type.caption, styles.line, { color: palette.errorText }]}>{messageOf(failure)}</Text>
        )}
      </View>

      <View style={styles.side}>
        {(alert.status === 'ACTIVE' || alert.status === 'PAUSED') && (
          <Toggle
            value={alert.status === 'ACTIVE'}
            disabled={busy}
            accessibilityLabel={`${alert.name} 감시`}
            onChange={(on) => (on ? resume.mutate(undefined) : pause.mutate())}
          />
        )}
        {alert.status === 'ENDED' && (
          <TextButton
            label="다시 켜기"
            accessibilityLabel={`${alert.name} 다시 켜기`}
            disabled={busy}
            onPress={() => resume.mutate(undefined)}
          />
        )}
        {alert.status === 'EXPIRED' && (
          <TextButton
            label="다시 켜기"
            accessibilityLabel={`${alert.name} 다시 켜기`}
            disabled={busy}
            onPress={() => setExpiryOpen(true)}
          />
        )}
      </View>

      <ExpirySheet
        visible={expiryOpen}
        busy={resume.isPending}
        onClose={() => setExpiryOpen(false)}
        onConfirm={(expiresAt) => resume.mutate(expiresAt, { onSuccess: () => setExpiryOpen(false) })}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: screenPadding,
    paddingVertical: space.md,
    borderBottomWidth: 1,
  },
  pressed: { opacity: 0.7 },
  body: { flex: 1, minWidth: 0 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
  title: { flexShrink: 1, fontWeight: '600' },
  spacer: { flex: 1 },
  line: { marginTop: 2 },
  side: { marginLeft: space.md, alignItems: 'flex-end', justifyContent: 'center' },
});
```

`front-end/src/screens/alerts/UnreadBlock.tsx`:

```tsx
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { AlertListData } from '@/api/alertTypes';
import { useTheme } from '@/design/theme';
import { screenPadding, size, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { basisLabel } from '@/format/alertTime';

/**
 * 알림 탭 위쪽 — `울린 알림 전체 →`와 새로 울린 알림 (IA §2.3).
 *
 * `울린 알림 전체`는 항상 보인다(IA §2.3). 지난 이력으로 가는 길이 이 줄 하나뿐이고,
 * 알림을 모두 지운 사용자에게도 울린 기록은 남는다(§6.8).
 * 새로 울린 알림은 최대 3건이고 넘치면 `외 N건 →`. 블록이 내 알림을 화면 밖으로 밀지 않게 한다.
 */
export function UnreadBlock({
  data,
  onOpenAll,
  onOpenEvent,
}: {
  data: AlertListData;
  onOpenAll: () => void;
  onOpenEvent: (eventId: string) => void;
}) {
  const palette = useTheme();

  return (
    <View style={styles.block}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="울린 알림 전체"
        onPress={onOpenAll}
        style={[styles.allRow, { backgroundColor: palette.surface }]}
      >
        <Text style={[type.label, { color: palette.text }]}>울린 알림 전체</Text>
        <Text style={[type.label, { color: palette.textMuted }]}>→</Text>
      </Pressable>

      {data.unread.length > 0 && (
        <View style={styles.unread}>
          <Text style={[type.caption, styles.heading, { color: palette.textMuted }]}>
            새로 울린 알림 {data.unread.length}
          </Text>
          {data.unread.map((event) => (
            <Pressable
              key={event.event_id}
              accessibilityRole="button"
              accessibilityLabel={event.title}
              onPress={() => onOpenEvent(event.event_id)}
              style={[styles.eventRow, { borderColor: palette.border }]}
            >
              <View style={[styles.dot, { backgroundColor: palette.badge }]} />
              <Text numberOfLines={1} style={[type.label, styles.eventText, { color: palette.text }]}>
                {event.title} · {basisLabel(event.as_of, event.cadence, event.market)}
              </Text>
              <Text style={[type.label, { color: palette.textMuted }]}>›</Text>
            </Pressable>
          ))}
          {data.unread_more > 0 && (
            <Pressable accessibilityRole="button" onPress={onOpenAll} style={styles.more}>
              <Text style={[type.caption, { color: palette.primary }]}>외 {data.unread_more}건 →</Text>
            </Pressable>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  block: { paddingHorizontal: screenPadding, paddingTop: space.md },
  allRow: {
    height: size.tap,
    borderRadius: 8,
    paddingHorizontal: space.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  unread: { marginTop: space.md },
  heading: { marginBottom: space.xs },
  eventRow: {
    minHeight: size.tap,
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: space.md,
    marginBottom: space.xs,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
  },
  dot: { width: 6, height: 6, borderRadius: 3 },
  eventText: { flex: 1 },
  more: { paddingVertical: space.xs },
});
```

- [ ] **Step 5: 화면을 쓴다**

`front-end/src/screens/alerts/AlertsScreen.tsx`:

```tsx
import { useNavigation } from '@react-navigation/native';
import type { NavigationProp } from '@react-navigation/native';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { useAlerts } from '@/api/queries/useAlerts';
import type { RootStackParamList } from '@/app/navigation/types';
import { useTheme } from '@/design/theme';
import { screenPadding, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { ScreenFrame } from '@/envelope/ScreenFrame';
import { AlertCard } from '@/screens/alerts/AlertCard';
import { UnreadBlock } from '@/screens/alerts/UnreadBlock';
import { Button } from '@/ui/Button';
import { Skeleton } from '@/ui/Skeleton';

/**
 * 알림 탭 루트 — 무엇을 걸어 뒀고 지금 어떤 상태인가 (§12.2 · IA §2.3).
 *
 * 규칙(내 알림)과 사건(울린 알림)을 한 화면에 둔다. 배지를 보고 들어온 사용자가
 * 무엇이 울렸는지 보고, 같은 자리에서 그 규칙을 관리한다.
 * 카드 순서는 서버가 정한다 — 조건 충족 중 → 감시 중 → 확인 불가 → 꺼짐 → 울린 뒤 종료 → 만료.
 * 탭을 여는 것만으로 읽음 처리하지 않는다. 제목만 본 것이지 내용을 본 것이 아니다(IA §3).
 */
export function AlertsScreen() {
  const palette = useTheme();
  const navigation = useNavigation<NavigationProp<RootStackParamList>>();
  const { envelope, loading, refreshing, error, refetch } = useAlerts();
  const data = envelope?.data;

  const openEditor = () => navigation.navigate('alert-editor', { mode: 'new' });
  const openAllEvents = () => navigation.navigate('alert-events', undefined);

  return (
    <ScreenFrame
      screen="alerts"
      asOfPrefix="최근 평가"
      envelope={envelope}
      loading={loading}
      error={error}
      onRetry={refetch}
      skeleton={<AlertsSkeleton />}
      header={
        <View style={styles.header}>
          <Text style={[type.title, { color: palette.text }]}>알림</Text>
          <Pressable accessibilityRole="button" accessibilityLabel="＋ 새 알림" onPress={openEditor} hitSlop={space.md}>
            <Text style={[type.label, { color: palette.primary }]}>＋ 새 알림</Text>
          </Pressable>
        </View>
      }
      aboveContent={
        data && (
          <UnreadBlock
            data={data}
            onOpenAll={openAllEvents}
            onOpenEvent={(eventId) => navigation.navigate('alert-event', { eventId })}
          />
        )
      }
      emptyAction={<Button label="＋ 첫 알림 만들기" onPress={openEditor} />}
    >
      {data && (
        <FlatList
          data={data.rows}
          keyExtractor={(row) => row.alert_id}
          ListHeaderComponent={
            <Text style={[type.caption, styles.section, { color: palette.textMuted }]}>내 알림</Text>
          }
          renderItem={({ item }) => (
            <AlertCard alert={item} onPress={() => navigation.navigate('alert', { alertId: item.alert_id })} />
          )}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refetch} />}
        />
      )}
    </ScreenFrame>
  );
}

function AlertsSkeleton() {
  return (
    <View style={styles.skeleton}>
      {[0, 1, 2].map((index) => (
        <Skeleton key={index} width="100%" height={72} style={styles.skeletonRow} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: screenPadding,
    paddingVertical: space.md,
  },
  section: { paddingHorizontal: screenPadding, paddingTop: space.lg, paddingBottom: space.xs },
  skeleton: { paddingHorizontal: screenPadding, paddingTop: space.md },
  skeletonRow: { marginBottom: space.md },
});
```

- [ ] **Step 6: 탭과 배지를 단다**

`app/navigation/Tabs.tsx`:

```tsx
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';

import { useUnreadCount } from '@/api/queries/useUnreadCount';
import type { TabParamList } from '@/app/navigation/types';
import { useTheme } from '@/design/theme';
import { type } from '@/design/typography';
import { AccountsScreen } from '@/screens/accounts/AccountsScreen';
import { AlertsScreen } from '@/screens/alerts/AlertsScreen';
import { AllocationScreen } from '@/screens/allocation/AllocationScreen';
import { PositionsScreen } from '@/screens/positions/PositionsScreen';
import { RealizedPnlScreen } from '@/screens/realizedPnl/RealizedPnlScreen';
import { SummaryScreen } from '@/screens/summary/SummaryScreen';

const Tab = createBottomTabNavigator<TabParamList>();

/** 배지 글자. 0이면 배지를 달지 않는다 — 갈 곳 없는 점은 불안만 준다(IA §3). */
function badgeText(count: number): number | string | undefined {
  if (count <= 0) return undefined;
  return count > 99 ? '99+' : count;
}

/**
 * 아래 탭 여섯 개.
 *
 * 아이콘 없이 두 글자 텍스트만 쓴다. 여섯 개가 한 줄에 들어간다(IA §2.1).
 *
 * 알림 탭의 숫자는 미확인 발화 수다. 누르면 새로 울린 알림 블록이 맨 위에 있다.
 * 계좌 탭에는 아직 점을 찍지 않는다. 점은 재인증·계좌 연동 화면과 함께 들어간다(IA §3).
 */
export function Tabs() {
  const palette = useTheme();
  const unread = useUnreadCount();

  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: palette.primary,
        tabBarInactiveTintColor: palette.textMuted,
        tabBarLabelStyle: type.caption,
        tabBarStyle: { backgroundColor: palette.bg, borderTopColor: palette.border },
        tabBarIcon: () => null,
      }}
    >
      <Tab.Screen name="summary" component={SummaryScreen} options={{ title: '요약' }} />
      <Tab.Screen name="positions" component={PositionsScreen} options={{ title: '종목' }} />
      <Tab.Screen name="allocation" component={AllocationScreen} options={{ title: '비중' }} />
      <Tab.Screen name="accounts" component={AccountsScreen} options={{ title: '계좌' }} />
      <Tab.Screen name="realized-pnl" component={RealizedPnlScreen} options={{ title: '손익' }} />
      <Tab.Screen
        name="alerts"
        component={AlertsScreen}
        options={{
          title: '알림',
          tabBarBadge: badgeText(unread),
          tabBarBadgeStyle: { backgroundColor: palette.badge, color: palette.onBadge },
        }}
      />
    </Tab.Navigator>
  );
}
```

- [ ] **Step 7: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest && npx tsc --noEmit`
Expected: 전부 PASS. 기존 `navigation.test.tsx`·`accounts.test.tsx`가 `Tabs`를 그릴 때 `/alert-events/unread-count`에 대역이 없어 404를 받는다 — 배지가 0으로 떨어지고 테스트는 그대로 통과해야 한다.

- [ ] **Step 8: 커밋한다**

```bash
git add src/app/navigation src/screens/alerts src/__tests__/alertsTab.test.tsx
git commit -m "feat: 알림 탭에 내 알림 카드와 새로 울린 알림, 탭 배지를 둔다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: 알림 상세 — 현재값 상자 · 끄기·다시 켜기 · 삭제 확인 · 수정 진입

**Files:**
- Create: `front-end/src/screens/alerts/detailPreview.ts`
- Create: `front-end/src/screens/alerts/PreviewBoxes.tsx` (`SentenceBox` · `CurrentBox`)
- Create: `front-end/src/screens/alerts/AlertDetailScreen.tsx`
- Modify: `front-end/src/app/navigation/RootStack.tsx` (`alert` 등록)
- Create: `front-end/src/testing/renderWithStack.tsx`
- Test: `front-end/src/__tests__/alertDetail.test.tsx`

**Interfaces:**
- Consumes: `useAlert` · `usePreview` · `useAlertActions` (Task 3), `StatusBadge` · `ExpirySheet` · `ConfirmSheet` · `TextButton` · `cadenceLabel` · `notifyModeLabel` · `expiryLabel` · `basisLabel` (Task 4)
- Produces:
  - `detailToPreview(detail: AlertDetail): PreviewRequest`
  - `<SentenceBox sentence={string | null | undefined} pending={boolean} />` · `<CurrentBox current={Current | null | undefined} pending={boolean} />` — Task 10·11이 폼에서 그대로 쓴다.
  - `renderWithStack(name, Component, params, options?: { others?: string[]; onNavigate?: (name, params) => void })` — 뒤로 갈 자리(`__home`)를 깔고 그 위에 화면을 연다. 렌더가 끝나기를 기다려(RNTL 14의 `render`는 Promise다) 결과에 `navigation`(컨테이너 ref)을 더해 돌려준다.

- [ ] **Step 1: 테스트용 스택 감싸개를 쓴다**

`front-end/src/testing/renderWithStack.tsx`:

```tsx
import type { ComponentType } from 'react';
import { NavigationContainer, createNavigationContainerRef } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

/**
 * 스택 화면 하나를 그린다. 그 아래에 `__home`을 깔아 두어 뒤로 가기가 닿을 곳이 있다.
 * 화면이 다른 화면을 열거나 닫으면 맨 위 화면의 이름과 파라미터가 onNavigate에 남는다.
 * 돌려주는 `navigation`으로 테스트가 뒤로 가기를 직접 부른다 — 헤더 버튼은 테스트 렌더러에
 * 그려진다고 기대하지 않는다.
 * 앱 코드는 이 파일을 쓰지 않는다.
 */

const METRICS = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 47, left: 0, right: 0, bottom: 34 },
};

function Empty() {
  return null;
}

export async function renderWithStack(
  name: string,
  component: ComponentType,
  params: object | undefined,
  options?: { others?: string[]; onNavigate?: (name: string, params: unknown) => void },
) {
  const Stack = createNativeStackNavigator();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const navigation = createNavigationContainerRef();

  const rendered = await render(
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider initialMetrics={METRICS}>
        <NavigationContainer
          ref={navigation}
          initialState={{ index: 1, routes: [{ name: '__home' }, { name, params }] }}
          onStateChange={(state) => {
            const route = state?.routes[state.index ?? 0];
            if (route) options?.onNavigate?.(route.name, route.params);
          }}
        >
          <Stack.Navigator>
            <Stack.Screen name="__home" component={Empty} />
            <Stack.Screen name={name} component={component} />
            {(options?.others ?? []).map((other) => (
              <Stack.Screen key={other} name={other} component={Empty} />
            ))}
          </Stack.Navigator>
        </NavigationContainer>
      </SafeAreaProvider>
    </QueryClientProvider>,
  );
  return { ...rendered, navigation };
}
```

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`front-end/src/__tests__/alertDetail.test.tsx`:

```tsx
import { fireEvent, screen, waitFor } from '@testing-library/react-native';

import { setAccessToken } from '@/api/client';
import {
  composableDetailFixture,
  expiredDetailFixture,
  presetDetailFixture,
  previewFixture,
} from '@/fixtures/alerts';
import { AlertDetailScreen } from '@/screens/alerts/AlertDetailScreen';
import { detailToPreview } from '@/screens/alerts/detailPreview';
import { renderWithStack } from '@/testing/renderWithStack';
import { type Route, serveRoutes } from '@/testing/serveRoutes';

const OTHERS = ['alert-events', 'alert-event', 'alert-editor'];

beforeEach(() => setAccessToken('tok'));
afterEach(() => setAccessToken(null));

async function open(alertId: string, routes: Route[]) {
  const calls = serveRoutes([{ method: 'POST', path: '/alerts/preview', body: previewFixture }, ...routes]);
  const moves: { name: string; params: unknown }[] = [];
  await renderWithStack('alert', AlertDetailScreen, { alertId }, {
    others: OTHERS,
    onNavigate: (name, params) => moves.push({ name, params }),
  });
  return { calls, moves };
}

describe('detailToPreview', () => {
  it('상세를 그대로 미리보기 요청으로 — alert_id를 싣는다', () => {
    expect(detailToPreview(presetDetailFixture)).toEqual({
      instrument_id: presetDetailFixture.instrument.id,
      name: '삼성전자 7만원',
      cadence: 'INTRADAY',
      notify_mode: 'EDGE_REARM',
      cooldown_min: null,
      expires_at: null,
      trigger_type: 'PRESET',
      trigger_spec: presetDetailFixture.trigger_spec,
      alert_id: 'a-satisfied',
    });
  });
});

describe('알림 상세', () => {
  it('머리 · 문장 · 현재값 상자 · 속성 · 최근 울린 알림', async () => {
    const { calls } = await open('a-satisfied', [{ path: '/alerts/a-satisfied', body: presetDetailFixture }]);
    await waitFor(() => expect(screen.getByText('장중에 현재가가 70,000원 이상이면 알려요')).toBeTruthy());

    expect(screen.getByText('삼성전자')).toBeTruthy();
    expect(screen.getByText('● 조건 충족 중')).toBeTruthy();
    expect(screen.getByText('삼성전자 7만원')).toBeTruthy();
    await waitFor(() => expect(screen.getByText('9/25 종가 기준')).toBeTruthy());
    expect(screen.getByText('현재가 63,010원 ≥ 63,010원')).toBeTruthy();
    expect(screen.getByText('→ 충족하고 있어요')).toBeTruthy();
    expect(screen.getByText('장중')).toBeTruthy();
    expect(screen.getByText('돌파할 때마다')).toBeTruthy();
    expect(screen.getByText('무기한')).toBeTruthy();
    expect(screen.getByText('9/26 10:15 · 삼성전자 · 가격 도달')).toBeTruthy();

    const preview = calls.find((c) => c.path === '/alerts/preview');
    expect((preview?.body as { alert_id: string }).alert_id).toBe('a-satisfied');
  });

  it('울린 적 없고 꺼진 알림 — 토글을 켜면 다시 켜기', async () => {
    const { calls } = await open('a-composable', [
      { path: '/alerts/a-composable', body: composableDetailFixture },
      { method: 'POST', path: '/alerts/a-composable/resume', status: 204 },
    ]);
    await waitFor(() => expect(screen.getByText('아직 울리지 않았어요')).toBeTruthy());
    expect(screen.getByText('꺼짐')).toBeTruthy();
    expect(screen.getByText('60분마다 다시')).toBeTruthy();
    expect(screen.getByText('2026-12-31까지')).toBeTruthy();

    await fireEvent.press(screen.getByRole('switch', { name: '감시' }));
    await waitFor(() => expect(calls.some((c) => c.path === '/alerts/a-composable/resume')).toBe(true));
  });

  it('만료된 알림은 유효기간을 골라 다시 켠다', async () => {
    const { calls } = await open('a-expired', [
      { path: '/alerts/a-expired', body: expiredDetailFixture },
      { method: 'POST', path: '/alerts/a-expired/resume', status: 204 },
    ]);
    await waitFor(() => expect(screen.getByText('만료')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '알림 다시 켜기' }));
    await fireEvent.press(screen.getByRole('button', { name: '다시 켜기' }));

    await waitFor(() =>
      expect(calls.find((c) => c.path === '/alerts/a-expired/resume')?.body).toEqual({ expires_at: null }),
    );
  });

  it('삭제는 확인을 거쳐 지우고 들어온 자리로 돌아간다', async () => {
    const { calls, moves } = await open('a-satisfied', [
      { path: '/alerts/a-satisfied', body: presetDetailFixture },
      { method: 'DELETE', path: '/alerts/a-satisfied', status: 204 },
    ]);
    await waitFor(() => expect(screen.getByText('알림 삭제')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '알림 삭제' }));
    expect(screen.getByText('이 알림을 삭제할까요?')).toBeTruthy();
    expect(screen.getByText('울린 기록은 남아요')).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: '삭제' }));

    await waitFor(() => expect(moves.at(-1)?.name).toBe('__home'));
    expect(calls.some((c) => c.method === 'DELETE' && c.path === '/alerts/a-satisfied')).toBe(true);
  });

  it('수정과 전체 →', async () => {
    const { moves } = await open('a-satisfied', [{ path: '/alerts/a-satisfied', body: presetDetailFixture }]);
    await waitFor(() => expect(screen.getByText('수정')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '전체 →' }));
    expect(moves.at(-1)).toEqual({ name: 'alert-events', params: { alertId: 'a-satisfied' } });
  });

  it('수정을 누르면 값이 채워진 흐름을 연다', async () => {
    const { moves } = await open('a-satisfied', [{ path: '/alerts/a-satisfied', body: presetDetailFixture }]);
    await waitFor(() => expect(screen.getByText('수정')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '수정' }));
    expect(moves.at(-1)).toEqual({ name: 'alert-editor', params: { mode: 'edit', alertId: 'a-satisfied' } });
  });

  it('없거나 남의 알림이면 서버 문장을 낸다', async () => {
    await open('x', [
      { path: '/alerts/x', status: 404, body: { error: { code: 'ALERT_NOT_FOUND', message: '알림을 찾을 수 없어요' } } },
    ]);
    await waitFor(() => expect(screen.getByText('알림을 찾을 수 없어요')).toBeTruthy());
  });
});
```

- [ ] **Step 3: 테스트가 실패하는지 본다**

Run: `npx jest src/__tests__/alertDetail.test.tsx`
Expected: FAIL — `Cannot find module '@/screens/alerts/AlertDetailScreen'`.

- [ ] **Step 4: 미리보기 요청 변환과 상자를 쓴다**

`front-end/src/screens/alerts/detailPreview.ts`:

```ts
import type { AlertDetail, PreviewRequest } from '@/api/alertTypes';

/**
 * 알림 상세의 현재값 상자를 채우는 미리보기 요청 (§12.4).
 *
 * 평가 상태에는 결과만 저장하므로 조건별 값을 보이려면 화면을 열 때 미리보기를 부른다.
 * `alert_id`를 실어 수정 규칙(보유를 묻지 않음 · 자기 자신은 중복이 아님)을 적용한다.
 * 저장된 trigger_spec에는 `lag`가 없어 그대로 보내도 된다.
 */
export function detailToPreview(detail: AlertDetail): PreviewRequest {
  return {
    instrument_id: detail.instrument.id,
    name: detail.name,
    cadence: detail.cadence,
    notify_mode: detail.notify_mode,
    cooldown_min: detail.cooldown_min,
    expires_at: detail.expires_at,
    trigger_type: detail.trigger_type,
    trigger_spec: detail.trigger_spec,
    alert_id: detail.alert_id,
  };
}
```

`front-end/src/screens/alerts/PreviewBoxes.tsx`:

```tsx
import { StyleSheet, Text, View } from 'react-native';

import type { Current, Truth } from '@/api/alertTypes';
import { useTheme } from '@/design/theme';
import { radius, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { Skeleton } from '@/ui/Skeleton';

/**
 * 미리보기 응답을 그리는 두 상자. 알림 상세와 폼(프리셋 입력 · 조건 만들기)이 함께 쓴다.
 * 문장도, 머리도, 줄도, 결과 줄도 서버가 완성한 것을 그대로 낸다(§12.1 · §12.5.4).
 *
 * 새 응답을 기다리는 동안 앞 내용을 흐리게 둔다. 비웠다 채우면 읽던 줄을 잃는다.
 */

export function SentenceBox({ sentence, pending }: { sentence: string | null | undefined; pending: boolean }) {
  const palette = useTheme();
  if (!sentence) return pending ? <Skeleton width="100%" height={52} style={styles.gap} /> : null;
  return (
    <View
      accessibilityLabel="조건 문장"
      style={[styles.box, styles.gap, { backgroundColor: palette.surface, borderColor: palette.border }, pending && styles.stale]}
    >
      <Text style={[type.body, { color: palette.text }]}>{sentence}</Text>
    </View>
  );
}

const MARK: Record<Truth, string> = { TRUE: '✓', FALSE: '✕', UNKNOWN: '?' };

/**
 * 현재값 상자. 조건마다 한 줄(`✓` · `✕` · `?`), 맨 아래 알림 전체 결과.
 * "왜 아직 안 울리지?"에 답하고, 감이 없는 지표의 기준값을 정하게 돕고,
 * 평가할 수 없는 조건을 저장 전에 알린다.
 */
export function CurrentBox({ current, pending }: { current: Current | null | undefined; pending: boolean }) {
  const palette = useTheme();
  if (!current) return pending ? <Skeleton width="100%" height={88} style={styles.gap} /> : null;
  return (
    <View
      accessibilityLabel="현재값"
      style={[styles.box, styles.gap, { borderColor: palette.border }, pending && styles.stale]}
    >
      <Text style={[type.micro, { color: palette.textMuted }]}>{current.header}</Text>
      {current.conditions.map((line, index) => (
        <View key={index} style={styles.line}>
          <Text style={[type.label, styles.mark, { color: palette.textMuted }]}>{MARK[line.result]}</Text>
          <Text style={[type.label, styles.text, { color: palette.text }]}>{line.text}</Text>
        </View>
      ))}
      <Text style={[type.label, styles.result, { color: palette.text }]}>→ {current.result_text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  box: { borderWidth: 1, borderRadius: radius.card, padding: space.md },
  gap: { marginTop: space.md },
  stale: { opacity: 0.5 },
  line: { flexDirection: 'row', marginTop: space.xs },
  mark: { width: 18 },
  text: { flex: 1 },
  result: { marginTop: space.sm, fontWeight: '600' },
});
```

- [ ] **Step 5: 화면을 쓴다**

`front-end/src/screens/alerts/AlertDetailScreen.tsx`:

```tsx
import { useCallback, useRef, useState } from 'react';
import { useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';
import type { NavigationProp, RouteProp } from '@react-navigation/native';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';

import type { AlertDetail } from '@/api/alertTypes';
import { useAlert } from '@/api/queries/useAlert';
import { useAlertActions } from '@/api/queries/useAlertActions';
import { usePreview } from '@/api/queries/usePreview';
import type { RootStackParamList } from '@/app/navigation/types';
import { useTheme } from '@/design/theme';
import { screenPadding, size, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { ErrorState, messageOf } from '@/envelope/ErrorState';
import { basisLabel } from '@/format/alertTime';
import { formatAsOf } from '@/format/date';
import { detailToPreview } from '@/screens/alerts/detailPreview';
import { ExpirySheet } from '@/screens/alerts/ExpirySheet';
import { cadenceLabel, expiryLabel, notifyModeLabel } from '@/screens/alerts/labels';
import { CurrentBox, SentenceBox } from '@/screens/alerts/PreviewBoxes';
import { StatusBadge } from '@/screens/alerts/StatusBadge';
import { Badge } from '@/ui/Badge';
import { Button } from '@/ui/Button';
import { ConfirmSheet } from '@/ui/ConfirmSheet';
import { Skeleton } from '@/ui/Skeleton';
import { TextButton } from '@/ui/TextButton';
import { Toggle } from '@/ui/Toggle';

/**
 * 이 알림은 무엇을 보고 있고, 지금 어디쯤인가 (§12.4).
 *
 * 현재값은 열 때, 다시 돌아올 때, 당겨서 새로 고칠 때 받는다. 자동 갱신은 없다 —
 * 장중 데이터는 5분 단위라 자주 바뀌지 않고, 충족되면 푸시가 알린다(§12.8).
 */
export function AlertDetailScreen() {
  const route = useRoute<RouteProp<RootStackParamList, 'alert'>>();
  const { alertId } = route.params;
  const detail = useAlert(alertId);
  const preview = usePreview(detail.data ? detailToPreview(detail.data) : null, { debounceMs: 0 });

  const refresh = useRef(() => undefined as void);
  refresh.current = () => {
    void detail.refetch();
    preview.refetch();
  };
  // 처음 열 때는 위 두 조회가 이미 부른다. 다른 화면에서 돌아올 때만 다시 받는다.
  const firstFocus = useRef(true);
  useFocusEffect(
    useCallback(() => {
      if (firstFocus.current) {
        firstFocus.current = false;
        return;
      }
      refresh.current();
    }, []),
  );

  if (detail.isPending) return <DetailSkeleton />;
  if (detail.isError) return <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />;

  return (
    <DetailBody
      alert={detail.data}
      preview={preview}
      refreshing={detail.isRefetching}
      onRefresh={() => refresh.current()}
    />
  );
}

function DetailBody({
  alert,
  preview,
  refreshing,
  onRefresh,
}: {
  alert: AlertDetail;
  preview: ReturnType<typeof usePreview>;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const palette = useTheme();
  const navigation = useNavigation<NavigationProp<RootStackParamList>>();
  const { pause, resume, remove } = useAlertActions(alert.alert_id);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [expiryOpen, setExpiryOpen] = useState(false);
  const failure = pause.error ?? resume.error ?? remove.error;

  return (
    <ScrollView
      style={{ backgroundColor: palette.bg }}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <View style={styles.head}>
        <Text numberOfLines={1} style={[type.title, styles.headTitle, { color: palette.text }]}>
          {alert.instrument.label ?? '종목 정보 없음'}
        </Text>
        {alert.instrument.market && <Badge label={alert.instrument.market} />}
        <View style={styles.spacer} />
        <StatusBadge alert={alert} />
        <TextButton
          label="수정"
          onPress={() => navigation.navigate('alert-editor', { mode: 'edit', alertId: alert.alert_id })}
        />
      </View>
      <Text style={[type.body, { color: palette.textMuted }]}>{alert.name}</Text>

      <SentenceBox sentence={alert.summary.sentence} pending={false} />
      <Text style={[type.micro, styles.help, { color: palette.textMuted }]}>
        {'기간의 "일"은 그 종목이 거래된 날로 세요. 휴장일과 거래정지일은 빼요.'}
      </Text>
      <CurrentBox current={preview.preview?.current} pending={preview.pending} />

      <View style={styles.props}>
        <PropRow label="평가 시점" value={cadenceLabel(alert.cadence)} />
        <PropRow label="알림 방식" value={notifyModeLabel(alert.notify_mode, alert.cooldown_min)} />
        <PropRow label="유효기간" value={expiryLabel(alert.expires_at)} />
        <PropRow
          label="마지막 평가"
          value={alert.evaluated_as_of ? formatAsOf(alert.evaluated_as_of) : '아직 평가 전이에요'}
        />
      </View>

      <View style={styles.sectionHead}>
        <Text style={[type.label, { color: palette.text }]}>최근 울린 알림</Text>
        <TextButton
          label="전체 →"
          onPress={() => navigation.navigate('alert-events', { alertId: alert.alert_id })}
        />
      </View>
      {alert.recent_events.length === 0 ? (
        <Text style={[type.caption, { color: palette.textMuted }]}>아직 울리지 않았어요</Text>
      ) : (
        alert.recent_events.map((event) => (
          <Pressable
            key={event.event_id}
            accessibilityRole="button"
            onPress={() => navigation.navigate('alert-event', { eventId: event.event_id })}
            style={[styles.eventRow, { borderBottomColor: palette.border }]}
          >
            {!event.read && <View style={[styles.dot, { backgroundColor: palette.badge }]} />}
            <Text numberOfLines={1} style={[type.label, styles.eventText, { color: palette.text }]}>
              {basisLabel(event.as_of, alert.cadence, alert.instrument.market, { withDate: true })} · {event.title}
            </Text>
            <Text style={[type.label, { color: palette.textMuted }]}>›</Text>
          </Pressable>
        ))
      )}

      <View style={styles.control}>
        {(alert.status === 'ACTIVE' || alert.status === 'PAUSED') && (
          <View style={styles.toggleRow}>
            <Text style={[type.body, { color: palette.text }]}>감시</Text>
            <Toggle
              value={alert.status === 'ACTIVE'}
              disabled={pause.isPending || resume.isPending}
              accessibilityLabel="감시"
              onChange={(on) => (on ? resume.mutate(undefined) : pause.mutate())}
            />
          </View>
        )}
        {alert.status === 'ENDED' && (
          <Button label="다시 켜기" loading={resume.isPending} onPress={() => resume.mutate(undefined)} />
        )}
        {alert.status === 'EXPIRED' && (
          <TextButton label="다시 켜기" accessibilityLabel="알림 다시 켜기" onPress={() => setExpiryOpen(true)} />
        )}
        {failure && <Text style={[type.caption, { color: palette.errorText }]}>{messageOf(failure)}</Text>}
      </View>

      <View style={styles.delete}>
        <TextButton label="알림 삭제" tone="danger" onPress={() => setConfirmDelete(true)} />
      </View>

      <ConfirmSheet
        visible={confirmDelete}
        title="이 알림을 삭제할까요?"
        message="울린 기록은 남아요"
        confirmLabel="삭제"
        busy={remove.isPending}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() =>
          remove.mutate(undefined, {
            onSuccess: () => {
              setConfirmDelete(false);
              navigation.goBack();
            },
          })
        }
      />
      <ExpirySheet
        visible={expiryOpen}
        busy={resume.isPending}
        onClose={() => setExpiryOpen(false)}
        onConfirm={(expiresAt) => resume.mutate(expiresAt, { onSuccess: () => setExpiryOpen(false) })}
      />
    </ScrollView>
  );
}

function PropRow({ label, value }: { label: string; value: string }) {
  const palette = useTheme();
  return (
    <View style={[styles.propRow, { borderBottomColor: palette.border }]}>
      <Text style={[type.label, { color: palette.textMuted }]}>{label}</Text>
      <Text style={[type.label, { color: palette.text }]}>{value}</Text>
    </View>
  );
}

function DetailSkeleton() {
  return (
    <View style={styles.content}>
      <Skeleton width="60%" height={26} />
      <Skeleton width="100%" height={52} style={styles.skeletonGap} />
      <Skeleton width="100%" height={88} style={styles.skeletonGap} />
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: screenPadding, paddingVertical: space.lg },
  head: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  headTitle: { flexShrink: 1 },
  spacer: { flex: 1 },
  help: { marginTop: space.xs },
  props: { marginTop: space.lg },
  propRow: {
    minHeight: size.tap,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
  },
  sectionHead: {
    marginTop: space.xl,
    marginBottom: space.xs,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  eventRow: { minHeight: size.tap, flexDirection: 'row', alignItems: 'center', gap: space.sm, borderBottomWidth: 1 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  eventText: { flex: 1 },
  control: { marginTop: space.xl, gap: space.sm },
  toggleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  delete: { marginTop: space.xl, alignItems: 'center' },
  skeletonGap: { marginTop: space.md },
});
```

- [ ] **Step 6: 루트 스택에 등록한다**

`app/navigation/RootStack.tsx`의 `asset-change` 아래에 더하고, import와 주석을 맞춘다.

```tsx
import { AlertDetailScreen } from '@/screens/alerts/AlertDetailScreen';
```

```tsx
      <Stack.Screen name="alert" component={AlertDetailScreen} options={{ title: '알림 상세' }} />
```

컴포넌트 주석의 첫 줄을 `탭 여섯과, 그 위에 얹히는 화면들.`로 바꾸고, 자산 변화 문단 아래에 한 문단을 더한다.

```
 * 알림의 상세 화면들(알림 상세 · 울린 알림 · 울린 알림 상세)도 같은 이유로 스택이다.
 * 푸시로 열 때는 탭을 알림으로 바꾼 뒤 그 위에 쌓는다 — 뒤로 가면 알림 탭이다(IA §4.1).
```

- [ ] **Step 7: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest src/__tests__/alertDetail.test.tsx && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 8: 커밋한다**

```bash
git add src/screens/alerts src/app/navigation/RootStack.tsx src/testing/renderWithStack.tsx src/__tests__/alertDetail.test.tsx
git commit -m "feat: 알림 상세에 현재값 상자와 끄기·다시 켜기·삭제를 둔다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 울린 알림 · 울린 알림 상세 (계획 ②의 계약)

**Files:**
- Create: `front-end/src/screens/alerts/AlertEventsScreen.tsx`
- Create: `front-end/src/screens/alerts/AlertEventScreen.tsx`
- Modify: `front-end/src/app/navigation/RootStack.tsx` (`alert-events` · `alert-event` 등록)
- Test: `front-end/src/__tests__/alertEvents.test.tsx`

**Interfaces:**
- Consumes: `useAlertEvents` · `useAlertEvent` · `markEventRead` · `markAllEventsRead` · `useAlertActions` · `invalidateAlertData` · `keys` (Task 3), `basisLabel` · `clockLabel` · `firedAtLabel` · `StatusBadge` · `TextButton` (Task 4), `renderWithStack` (Task 6)
- Produces: `<AlertEventsScreen />` · `<AlertEventScreen />`. Task 12의 푸시 라우터가 `navigate('alert-event', { eventId })`로 연다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`front-end/src/__tests__/alertEvents.test.tsx`:

```tsx
import { fireEvent, screen, waitFor } from '@testing-library/react-native';

import { setAccessToken } from '@/api/client';
import {
  deletedEventDetailFixture,
  eventDetailFixture,
  eventsEmptyFixture,
  eventsFixture,
} from '@/fixtures/alerts';
import { AlertEventScreen } from '@/screens/alerts/AlertEventScreen';
import { AlertEventsScreen } from '@/screens/alerts/AlertEventsScreen';
import { renderWithStack } from '@/testing/renderWithStack';
import { type Route, serveRoutes } from '@/testing/serveRoutes';

beforeEach(() => setAccessToken('tok'));
afterEach(() => setAccessToken(null));

async function openList(params: object | undefined, routes: Route[]) {
  const calls = serveRoutes(routes);
  const moves: { name: string; params: unknown }[] = [];
  await renderWithStack('alert-events', AlertEventsScreen, params, {
    others: ['alert-event'],
    onNavigate: (name, p) => moves.push({ name, params: p }),
  });
  return { calls, moves };
}

async function openEvent(eventId: string, routes: Route[]) {
  const calls = serveRoutes(routes);
  const moves: { name: string; params: unknown }[] = [];
  await renderWithStack('alert-event', AlertEventScreen, { eventId }, {
    others: ['alert'],
    onNavigate: (name, p) => moves.push({ name, params: p }),
  });
  return { calls, moves };
}

describe('울린 알림', () => {
  it('행 — 제목 · 본문 · 삭제된 알림 표시', async () => {
    await openList(undefined, [{ path: '/alert-events', body: eventsFixture }]);
    await waitFor(() => expect(screen.getByText('삼성전자 · 가격 도달')).toBeTruthy());

    expect(screen.getByText('현재가 70,200원 ≥ 70,000원 · 10:15 기준')).toBeTruthy();
    expect(screen.getByText('LG에너지솔루션 · 급등락')).toBeTruthy();
    expect(screen.getByText('삭제된 알림')).toBeTruthy();
    expect(screen.getByText('9/20 16:05')).toBeTruthy();
  });

  it('알림 상세의 전체 →로 오면 그 알림으로 거른다', async () => {
    const { calls } = await openList({ alertId: 'a-satisfied' }, [{ path: '/alert-events', body: eventsFixture }]);
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(calls[0].url).toContain('alert_id=a-satisfied');
  });

  it('모두 읽음은 읽음 처리 뒤 목록을 다시 받는다', async () => {
    const { calls } = await openList(undefined, [
      { path: '/alert-events', body: eventsFixture },
      { method: 'POST', path: '/alert-events/read-all', status: 204 },
    ]);
    await waitFor(() => expect(screen.getByText('모두 읽음')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '모두 읽음' }));

    await waitFor(() =>
      expect(calls.filter((c) => c.method === 'GET' && c.path === '/alert-events')).toHaveLength(2),
    );
  });

  it('끝에 닿으면 다음 쪽을 커서로 받는다', async () => {
    const { calls } = await openList(undefined, [{ path: '/alert-events', body: eventsFixture }]);
    await waitFor(() => expect(screen.getByText('삼성전자 · 가격 도달')).toBeTruthy());

    fireEvent(screen.getByTestId('alert-events-list'), 'onEndReached');

    await waitFor(() => expect(calls.some((c) => c.url.includes('cursor=cursor-2'))).toBe(true));
  });

  it('행을 누르면 울린 알림 상세', async () => {
    const { moves } = await openList(undefined, [{ path: '/alert-events', body: eventsFixture }]);
    await waitFor(() => expect(screen.getByText('삼성전자 · 가격 도달')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '삼성전자 · 가격 도달' }));
    expect(moves.at(-1)).toEqual({ name: 'alert-event', params: { eventId: 'e-1' } });
  });

  it('빈 상태', async () => {
    await openList(undefined, [{ path: '/alert-events', body: eventsEmptyFixture }]);
    await waitFor(() => expect(screen.getByText('아직 울린 알림이 없어요')).toBeTruthy());
  });
});

describe('울린 알림 상세', () => {
  it('울린 당시 문구와 이 알림, 열면 읽음 처리', async () => {
    const { calls } = await openEvent('e-1', [
      { path: '/alert-events/e-1', body: eventDetailFixture },
      { method: 'POST', path: '/alert-events/e-1/read', status: 204 },
    ]);
    await waitFor(() => expect(screen.getByText('삼성전자 · 가격 도달')).toBeTruthy());

    expect(screen.getByText('9/26 10:15 기준 · 10:15:41 울림')).toBeTruthy();
    expect(screen.getByText('현재가 70,200원 ≥ 70,000원')).toBeTruthy();
    expect(screen.getByText('삼성전자 7만원')).toBeTruthy();
    expect(screen.getByText('● 감시 중')).toBeTruthy();
    await waitFor(() =>
      expect(calls.filter((c) => c.path === '/alert-events/e-1/read')).toHaveLength(1),
    );
  });

  it('이 알림 끄기와 알림 보기', async () => {
    const { calls, moves } = await openEvent('e-1', [
      { path: '/alert-events/e-1', body: eventDetailFixture },
      { method: 'POST', path: '/alert-events/e-1/read', status: 204 },
      { method: 'POST', path: '/alerts/a-satisfied/pause', status: 204 },
    ]);
    await waitFor(() => expect(screen.getByText('이 알림 끄기')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '이 알림 끄기' }));
    await waitFor(() => expect(calls.some((c) => c.path === '/alerts/a-satisfied/pause')).toBe(true));

    await fireEvent.press(screen.getByRole('button', { name: '알림 보기 →' }));
    expect(moves.at(-1)).toEqual({ name: 'alert', params: { alertId: 'a-satisfied' } });
  });

  it('삭제된 알림의 발화는 알림 보기와 끄기를 숨기고, 이미 읽었으면 다시 읽지 않는다', async () => {
    const { calls } = await openEvent('e-9', [{ path: '/alert-events/e-9', body: deletedEventDetailFixture }]);
    await waitFor(() => expect(screen.getByText('삭제된 알림')).toBeTruthy());

    expect(screen.queryByText('알림 보기 →')).toBeNull();
    expect(screen.queryByText('이 알림 끄기')).toBeNull();
    expect(calls.some((c) => c.path.endsWith('/read'))).toBe(false);
  });

  it('다른 계정이거나 없는 발화', async () => {
    await openEvent('nope', [
      { path: '/alert-events/nope', status: 404, body: { error: { code: 'EVENT_NOT_FOUND', message: '울린 알림을 찾을 수 없어요' } } },
    ]);
    await waitFor(() => expect(screen.getByText('찾을 수 없는 알림이에요')).toBeTruthy());
  });
});
```

- [ ] **Step 2: 테스트가 실패하는지 본다**

Run: `npx jest src/__tests__/alertEvents.test.tsx`
Expected: FAIL — `Cannot find module '@/screens/alerts/AlertEventScreen'`.

- [ ] **Step 3: 목록 화면을 쓴다**

`front-end/src/screens/alerts/AlertEventsScreen.tsx`:

```tsx
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NavigationProp, RouteProp } from '@react-navigation/native';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { markAllEventsRead } from '@/api/alertEndpoints';
import type { AlertEventRow } from '@/api/alertTypes';
import { invalidateAlertData } from '@/api/queries/alertInvalidation';
import { useAlertEvents } from '@/api/queries/useAlertEvents';
import type { RootStackParamList } from '@/app/navigation/types';
import { useTheme } from '@/design/theme';
import { screenPadding, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { ScreenFrame } from '@/envelope/ScreenFrame';
import { firedAtLabel } from '@/format/alertTime';
import { Badge } from '@/ui/Badge';
import { Skeleton } from '@/ui/Skeleton';
import { TextButton } from '@/ui/TextButton';

/**
 * 울린 알림 (§12.3). 데이터 시점 내림차순이고 날짜로 묶지 않는다.
 * 삭제된 알림의 발화도 그대로 보인다 — 받은 푸시를 눌렀을 때 내용이 사라져 있으면
 * 무엇이 울렸는지 알 방법이 없다(§6.8).
 */
export function AlertEventsScreen() {
  const route = useRoute<RouteProp<RootStackParamList, 'alert-events'>>();
  const navigation = useNavigation<NavigationProp<RootStackParamList>>();
  const alertId = route.params?.alertId;
  const events = useAlertEvents(alertId);
  const queryClient = useQueryClient();
  const readAll = useMutation({
    mutationFn: markAllEventsRead,
    onSuccess: () => invalidateAlertData(queryClient),
  });
  const palette = useTheme();

  return (
    <ScreenFrame
      screen="alert-events"
      topInset={false}
      asOfPrefix="최근 평가"
      envelope={events.envelope}
      loading={events.loading}
      error={events.error}
      onRetry={events.refetch}
      skeleton={<EventsSkeleton />}
      header={
        <View style={styles.header}>
          <TextButton
            label="모두 읽음"
            disabled={readAll.isPending || !events.rows.some((row) => !row.read)}
            onPress={() => readAll.mutate()}
          />
        </View>
      }
    >
      <FlatList
        testID="alert-events-list"
        data={events.rows}
        keyExtractor={(row) => row.event_id}
        renderItem={({ item }) => (
          <EventRow event={item} onPress={() => navigation.navigate('alert-event', { eventId: item.event_id })} />
        )}
        onEndReached={events.fetchMore}
        onEndReachedThreshold={0.5}
        refreshControl={<RefreshControl refreshing={events.refreshing} onRefresh={events.refetch} />}
        style={{ backgroundColor: palette.bg }}
      />
    </ScreenFrame>
  );
}

/** 1줄 제목 · 미확인 점 / 2줄 본문 / 3줄 시각 · 삭제된 알림. */
function EventRow({ event, onPress }: { event: AlertEventRow; onPress: () => void }) {
  const palette = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={event.title}
      onPress={onPress}
      style={[styles.row, { borderBottomColor: palette.border }]}
    >
      <View style={styles.titleRow}>
        {!event.read && <View style={[styles.dot, { backgroundColor: palette.badge }]} />}
        <Text numberOfLines={1} style={[type.body, styles.title, { color: palette.text }]}>
          {event.title}
        </Text>
      </View>
      <Text numberOfLines={1} style={[type.label, styles.line, { color: palette.text }]}>
        {event.body}
      </Text>
      <View style={styles.metaRow}>
        <Text style={[type.caption, { color: palette.textMuted }]}>{firedAtLabel(event.fired_at)}</Text>
        {event.alert_deleted && <Badge label="삭제된 알림" />}
      </View>
    </Pressable>
  );
}

function EventsSkeleton() {
  return (
    <View style={styles.skeleton}>
      {[0, 1, 2, 3].map((index) => (
        <Skeleton key={index} width="100%" height={64} style={styles.skeletonRow} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', justifyContent: 'flex-end', paddingHorizontal: screenPadding, paddingTop: space.sm },
  row: { paddingHorizontal: screenPadding, paddingVertical: space.md, borderBottomWidth: 1 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  title: { flex: 1, fontWeight: '600' },
  dot: { width: 6, height: 6, borderRadius: 3 },
  line: { marginTop: 2 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, marginTop: 2 },
  skeleton: { paddingHorizontal: screenPadding, paddingTop: space.md },
  skeletonRow: { marginBottom: space.md },
});
```

- [ ] **Step 4: 상세 화면을 쓴다**

`front-end/src/screens/alerts/AlertEventScreen.tsx`:

```tsx
import { useEffect } from 'react';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NavigationProp, RouteProp } from '@react-navigation/native';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { ApiError } from '@/api/client';
import { markEventRead } from '@/api/alertEndpoints';
import type { AlertEventDetail } from '@/api/alertTypes';
import { keys } from '@/api/queries/keys';
import { useAlertActions } from '@/api/queries/useAlertActions';
import { useAlertEvent } from '@/api/queries/useAlertEvents';
import type { RootStackParamList } from '@/app/navigation/types';
import { useTheme } from '@/design/theme';
import { radius, screenPadding, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { ErrorState, messageOf } from '@/envelope/ErrorState';
import { basisLabel, clockLabel } from '@/format/alertTime';
import { StatusBadge } from '@/screens/alerts/StatusBadge';
import { Badge } from '@/ui/Badge';
import { Button } from '@/ui/Button';
import { Skeleton } from '@/ui/Skeleton';
import { TextButton } from '@/ui/TextButton';

/**
 * 무엇이, 왜 울렸나 (§12.3).
 *
 * 울린 당시의 문구만 보여 준다. 알림이 뒤에 수정돼도 그때 울린 이유는 바뀌지 않는다.
 * 지금 값을 두지 않는다 — 두 시점의 값이 나란히 있으면 어느 쪽이 울린 이유인지 헷갈린다.
 * 열면 읽음 처리한다. 알림 탭을 여는 것만으로는 읽음이 아니다(IA §3).
 */
export function AlertEventScreen() {
  const route = useRoute<RouteProp<RootStackParamList, 'alert-event'>>();
  const { eventId } = route.params;
  const event = useAlertEvent(eventId);
  const queryClient = useQueryClient();
  const read = useMutation({
    mutationFn: () => markEventRead(eventId),
    onSuccess: () => {
      for (const queryKey of [keys.alerts, ['alert-events'], keys.unreadCount]) {
        void queryClient.invalidateQueries({ queryKey });
      }
    },
  });

  const unread = event.data?.read_at === null;
  useEffect(() => {
    if (unread && read.isIdle) read.mutate();
  }, [unread, read]);

  if (event.isPending) return <EventSkeleton />;
  if (event.isError) {
    // 다른 계정으로 로그인했거나 없는 발화. 남의 것과 없는 것을 서버가 가르지 않는다(§11.4).
    if (event.error instanceof ApiError && event.error.status === 404) return <NotFound />;
    return <ErrorState error={event.error} onRetry={() => void event.refetch()} />;
  }
  return <EventBody event={event.data} />;
}

function EventBody({ event }: { event: AlertEventDetail }) {
  const palette = useTheme();
  const navigation = useNavigation<NavigationProp<RootStackParamList>>();
  const { pause } = useAlertActions(event.alert.alert_id);
  // 상세 응답에 cadence·market이 없으면 알림의 평가 시점과 국내 표기로 그린다(계획 A.3).
  const stamp = `${basisLabel(event.as_of, event.cadence ?? event.alert.cadence, event.market ?? 'KR', { withDate: true })} 기준 · ${clockLabel(event.fired_at)} 울림`;

  return (
    <ScrollView style={{ backgroundColor: palette.bg }} contentContainerStyle={styles.content}>
      <Text style={[type.title, { color: palette.text }]}>{event.title}</Text>
      <Text style={[type.caption, styles.stamp, { color: palette.textMuted }]}>{stamp}</Text>

      <View style={[styles.reason, { backgroundColor: palette.statusWatchingBg }]}>
        <Text style={[type.micro, { color: palette.statusWatchingText }]}>울린 이유</Text>
        {event.lines.map((line, index) => (
          <Text key={index} style={[type.body, styles.reasonLine, { color: palette.text }]}>
            {line}
          </Text>
        ))}
      </View>

      <Text style={[type.caption, styles.sectionLabel, { color: palette.textMuted }]}>이 알림</Text>
      <View style={[styles.alertRow, { borderBottomColor: palette.border }]}>
        <Text numberOfLines={1} style={[type.body, styles.alertName, { color: palette.text }]}>
          {event.alert.name}
        </Text>
        {event.alert.deleted ? <Badge label="삭제된 알림" /> : <StatusBadge alert={event.alert} />}
      </View>

      {!event.alert.deleted && (
        <View style={styles.actions}>
          <Button
            label="알림 보기 →"
            onPress={() => navigation.navigate('alert', { alertId: event.alert.alert_id })}
          />
          {event.alert.status === 'ACTIVE' && (
            <View style={styles.pause}>
              <TextButton label="이 알림 끄기" disabled={pause.isPending} onPress={() => pause.mutate()} />
            </View>
          )}
          {pause.error && (
            <Text style={[type.caption, { color: palette.errorText }]}>{messageOf(pause.error)}</Text>
          )}
        </View>
      )}
    </ScrollView>
  );
}

function NotFound() {
  const palette = useTheme();
  return (
    <View style={styles.notFound}>
      <Text style={[type.body, { color: palette.text }]}>찾을 수 없는 알림이에요</Text>
    </View>
  );
}

function EventSkeleton() {
  return (
    <View style={styles.content}>
      <Skeleton width="70%" height={26} />
      <Skeleton width="100%" height={72} style={styles.reasonSkeleton} />
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: screenPadding, paddingVertical: space.lg },
  stamp: { marginTop: space.xs },
  reason: { marginTop: space.lg, borderRadius: radius.card, padding: space.md },
  reasonLine: { marginTop: space.xs, fontWeight: '600' },
  sectionLabel: { marginTop: space.xl },
  alertRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingVertical: space.md, borderBottomWidth: 1 },
  alertName: { flex: 1 },
  actions: { marginTop: space.xl, gap: space.md },
  pause: { alignItems: 'center' },
  notFound: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  reasonSkeleton: { marginTop: space.lg },
});
```

- [ ] **Step 5: 루트 스택에 등록한다**

`RootStack.tsx`에 import 둘과 화면 둘을 더한다. 헤더 이름은 IA §6.1 그대로 둘 다 `울린 알림`이다.

```tsx
import { AlertEventScreen } from '@/screens/alerts/AlertEventScreen';
import { AlertEventsScreen } from '@/screens/alerts/AlertEventsScreen';
```

```tsx
      <Stack.Screen name="alert-events" component={AlertEventsScreen} options={{ title: '울린 알림' }} />
      <Stack.Screen name="alert-event" component={AlertEventScreen} options={{ title: '울린 알림' }} />
```

- [ ] **Step 6: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest src/__tests__/alertEvents.test.tsx && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 7: 커밋한다**

```bash
git add src/screens/alerts src/app/navigation/RootStack.tsx src/__tests__/alertEvents.test.tsx
git commit -m "feat: 울린 알림 목록과 상세를 계약대로 그린다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: 새 알림 초안 — 상태 · 요청 변환 · 입력 칸 규칙 (순수 함수)

화면 없이 초안의 모든 규칙을 먼저 세운다. Task 9~13의 화면은 이 모듈의 액션을 보내고 결과를 그리기만 한다.

**Files:**
- Create: `front-end/src/screens/alertEditor/draft.ts`
- Create: `front-end/src/screens/alertEditor/presetFields.ts`
- Create: `front-end/src/screens/alertEditor/composable.ts`
- Create: `front-end/src/screens/alertEditor/fieldErrors.ts`
- Test: `front-end/src/__tests__/editorDraft.test.ts`

**Interfaces:**
- Consumes: 알림 타입 (Task 3), `EditorInstrument` (Task 5), `ExpiryChoice` · `expiresAtFor` (Task 4)
- Produces:
  - 타입: `TransformDraft` · `OperandDraft` · `RightDraft` · `ConditionDraft` · `Draft` · `DraftAction`
  - `MAX_CONDITIONS = 5` · `NAME_MAX = 40`
  - `newDraft(instrument?: EditorInstrument): Draft` · `draftFromDetail(detail: AlertDetail): Draft`
  - `draftReducer(draft: Draft, action: DraftAction): Draft`
  - `draftToRequest(draft, catalog, now): AlertRequest | null` · `draftToPreview(draft, catalog, now): PreviewRequest | null`
  - `defaultName(draft, catalog): string` · `effectiveName(draft, catalog): string`
  - `emptyOperand()` · `emptyCondition()` · `operandFor(indicator)` · `presetDefaults(preset, instrument)` · `toNumber(text)` · `isPresetSpec(spec)`
  - `fitCondition(c, cadence, catalog)` · `cadenceChangeClears(draft, cadence, catalog)`
  - `presetFields.ts`: `fieldSpec(presetKey, paramKey): FieldSpec` · `periodChips(param): number[]` · `presetAvailability(preset, instrument): Availability`
  - `composable.ts`: `CATEGORY_ORDER` · `type Availability` · `indicatorAvailability(indicator, ctx)` · `scopeInUse(conditions, except, catalog)` · `transformChoices(indicator, cadence, side, catalog)` · `unitSuffix(unit, market)` · `constUnit(left, transform, market)` · `showModifier(condition, catalog)` · `withOperator(condition, op)` · `withLeft(condition, indicator)` · `findIndicator(catalog, key)`
  - `fieldErrors.ts`: `errorAt(errors, path)` · `errorUnder(errors, prefix)` · `errorsOutside(errors, prefixes)`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`front-end/src/__tests__/editorDraft.test.ts`:

```ts
import type { AlertDetail } from '@/api/alertTypes';
import type { EditorInstrument } from '@/app/navigation/types';
import { catalogFixture, composableDetailFixture, presetDetailFixture } from '@/fixtures/alerts';
import {
  type ConditionDraft,
  type Draft,
  cadenceChangeClears,
  defaultName,
  draftFromDetail,
  draftReducer,
  draftToPreview,
  draftToRequest,
  emptyCondition,
  newDraft,
  operandFor,
  presetDefaults,
  toNumber,
} from '@/screens/alertEditor/draft';
import {
  constUnit,
  indicatorAvailability,
  scopeInUse,
  showModifier,
  transformChoices,
  withLeft,
  withOperator,
} from '@/screens/alertEditor/composable';
import { errorAt, errorUnder, errorsOutside } from '@/screens/alertEditor/fieldErrors';
import { fieldSpec, periodChips, presetAvailability } from '@/screens/alertEditor/presetFields';

const catalog = catalogFixture;
const now = new Date('2026-10-11T03:00:00Z');
const preset = (key: string) => catalog.presets.find((p) => p.key === key)!;
const indicator = (key: string) => catalog.indicators.find((i) => i.key === key)!;

const SAMSUNG: EditorInstrument = {
  id: 'i-samsung', label: '삼성전자', market: 'KR', held: true, lastClose: 63010, lastCloseOn: '2026-09-25',
};
const APPLE: EditorInstrument = { ...SAMSUNG, id: 'i-apple', label: '애플', market: 'US', lastClose: 230.1 };
const SDI: EditorInstrument = { ...SAMSUNG, id: 'i-sdi', label: '삼성SDI', held: false, lastClose: null, lastCloseOn: null };

function run(draft: Draft, ...actions: Parameters<typeof draftReducer>[1][]): Draft {
  return actions.reduce(draftReducer, draft);
}

describe('toNumber', () => {
  it.each([
    ['63,010', 63010],
    ['−5', -5],
    [' 1.5 ', 1.5],
    ['', null],
    ['abc', null],
  ])('%p → %p', (text, n) => {
    expect(toNumber(text)).toBe(n);
  });
});

describe('프리셋 고르기', () => {
  it('가격 도달은 직전 종가로 가격을 채우고 장중이 기본이다', () => {
    const draft = run(newDraft(SAMSUNG), { type: 'preset', preset: preset('price_reach') });
    expect(draft.params).toEqual({ direction: 'up', price: '63010' });
    expect(draft.cadence).toBe('INTRADAY');
    expect(draft.triggerType).toBe('PRESET');
    expect(draft.dirty).toBe(true);
  });

  it('직전 종가를 모르면 가격 칸은 비어 있다', () => {
    expect(presetDefaults(preset('price_reach'), SDI)).toEqual({ direction: 'up', price: '' });
  });

  it('종가 전용 프리셋은 종가, 다시 알림 간격은 장중에만 있으니 되돌린다', () => {
    const draft = run(
      newDraft(SAMSUNG),
      { type: 'preset', preset: preset('price_reach') },
      { type: 'notify-mode', mode: 'COOLDOWN' },
      { type: 'preset', preset: preset('rsi_zone') },
    );
    expect(draft.cadence).toBe('CLOSE');
    expect(draft.notifyMode).toBe('EDGE_REARM');
  });

  it('같은 프리셋을 다시 고르면 입력을 지우지 않는다', () => {
    const draft = run(
      newDraft(SAMSUNG),
      { type: 'preset', preset: preset('change_move') },
      { type: 'param', key: 'pct', value: '7' },
      { type: 'preset', preset: preset('change_move') },
    );
    expect(draft.params.pct).toBe('7');
  });

  it('RSI 과매도를 고르면 기준을 30으로, 과매수면 70으로', () => {
    const draft = run(newDraft(SAMSUNG), { type: 'preset', preset: preset('rsi_zone') }, { type: 'param', key: 'zone', value: 'oversold' });
    expect(draft.params.level).toBe('30');
    expect(run(draft, { type: 'param', key: 'zone', value: 'overbought' }).params.level).toBe('70');
  });

  it('수익률 도달의 손실은 음수로 보낸다 — 칸에는 크기만 둔다', () => {
    const draft = run(newDraft(SAMSUNG), { type: 'preset', preset: preset('pnl_reach') }, { type: 'param', key: 'direction', value: 'loss' });
    expect(draft.params.pct).toBe('10');
    const request = draftToRequest(draft, catalog, now)!;
    expect(request.trigger_spec).toEqual({ preset_key: 'pnl_reach', params: { direction: 'loss', pct: -10 } });

    const profit = run(draft, { type: 'param', key: 'direction', value: 'profit' });
    expect(draftToRequest(profit, catalog, now)!.trigger_spec).toEqual({
      preset_key: 'pnl_reach',
      params: { direction: 'profit', pct: 10 },
    });
  });

  it('빈 숫자 칸은 null로 보내 서버가 그 칸에 오류를 단다', () => {
    const draft = run(newDraft(SDI), { type: 'preset', preset: preset('price_reach') });
    expect(draftToRequest(draft, catalog, now)!.trigger_spec).toEqual({
      preset_key: 'price_reach',
      params: { direction: 'up', price: null },
    });
  });

  it('종목을 바꾸면 고른 조건을 버린다', () => {
    const draft = run(newDraft(SAMSUNG), { type: 'preset', preset: preset('price_reach') }, { type: 'instrument', instrument: APPLE });
    expect(draft.triggerType).toBeNull();
    expect(draft.params).toEqual({});
  });
});

describe('기본 이름과 요청', () => {
  it('프리셋은 종목명 + 프리셋 라벨, 조립형은 종목명 + 첫 조건의 지표', () => {
    const presetDraft = run(newDraft(SAMSUNG), { type: 'preset', preset: preset('price_reach') });
    expect(defaultName(presetDraft, catalog)).toBe('삼성전자 가격 도달');

    const composable = run(newDraft(SAMSUNG), { type: 'composable' }, {
      type: 'condition', index: 0, condition: { ...emptyCondition(), left: operandFor(indicator('rsi')) },
    });
    expect(defaultName(composable, catalog)).toBe('삼성전자 RSI');
  });

  it('이름을 고치면 그 이름을 쓴다', () => {
    const draft = run(newDraft(SAMSUNG), { type: 'preset', preset: preset('price_reach') }, { type: 'name', value: '삼성 7만' });
    expect(draftToRequest(draft, catalog, now)!.name).toBe('삼성 7만');
  });

  it('종목이나 조건 종류가 없으면 요청을 만들지 않는다', () => {
    expect(draftToRequest(newDraft(), catalog, now)).toBeNull();
    expect(draftToRequest(newDraft(SAMSUNG), catalog, now)).toBeNull();
  });

  it('공통 설정 — 간격은 다시 알림일 때만, 유효기간은 선택지대로', () => {
    const draft = run(
      newDraft(SAMSUNG),
      { type: 'preset', preset: preset('price_reach') },
      { type: 'notify-mode', mode: 'COOLDOWN' },
      { type: 'cooldown', value: '30' },
      { type: 'expiry', choice: '1W' },
    );
    const request = draftToRequest(draft, catalog, now)!;
    expect(request.notify_mode).toBe('COOLDOWN');
    expect(request.cooldown_min).toBe(30);
    expect(request.expires_at).toBe('2026-10-18T12:00:00+09:00');

    const edge = run(draft, { type: 'notify-mode', mode: 'EDGE_REARM' });
    expect(draftToRequest(edge, catalog, now)!.cooldown_min).toBeNull();
  });
});

describe('조립형 조건', () => {
  const rsi3: ConditionDraft = {
    left: operandFor(indicator('rsi')),
    op: 'gte',
    right: { kind: 'const', value: '70' },
    modifier: '3',
  };

  it('스펙 §13.1 모양으로 보낸다 — lag는 싣지 않는다', () => {
    const draft = run(newDraft(SAMSUNG), { type: 'composable' }, { type: 'condition', index: 0, condition: rsi3 });
    expect(draftToRequest(draft, catalog, now)!.trigger_spec).toEqual({
      conditions: [
        {
          left: { indicator: 'rsi', indicator_params: { n: 14 }, transform: { type: 'identity' } },
          op: 'gte',
          right: { const: 70 },
          modifier: { streak: 3 },
        },
      ],
    });
  });

  it('조건은 1~5개', () => {
    let draft = run(newDraft(SAMSUNG), { type: 'composable' });
    for (let i = 0; i < 10; i++) draft = draftReducer(draft, { type: 'add-condition' });
    expect(draft.conditions).toHaveLength(5);
    for (let i = 0; i < 10; i++) draft = draftReducer(draft, { type: 'remove-condition', index: 0 });
    expect(draft.conditions).toHaveLength(1);
  });

  it('장중으로 바꾸면 장중 왼쪽에 올 수 없는 지표와 유지 칸을 비운다', () => {
    const draft = run(newDraft(SAMSUNG), { type: 'composable' }, { type: 'condition', index: 0, condition: rsi3 });
    expect(cadenceChangeClears(draft, 'INTRADAY', catalog)).toBe(true);

    const intraday = draftReducer(draft, { type: 'cadence', cadence: 'INTRADAY', catalog });
    expect(intraday.conditions[0].left.indicator).toBeNull();
    expect(intraday.conditions[0].modifier).toBe('');
    expect(intraday.conditions[0].right).toEqual({ kind: 'const', value: '70' });
  });

  it('맞는 조건뿐이면 확인 없이 바꾼다', () => {
    const price: ConditionDraft = { ...emptyCondition(), left: operandFor(indicator('price')), right: { kind: 'const', value: '70000' } };
    const draft = run(newDraft(SAMSUNG), { type: 'composable' }, { type: 'condition', index: 0, condition: price });
    expect(cadenceChangeClears(draft, 'INTRADAY', catalog)).toBe(false);
  });

  it('교차를 고르면 기준값이 지표가 되고 유지 칸을 숨긴다', () => {
    const crossed = withOperator(rsi3, 'crosses_above');
    expect(crossed.right.kind).toBe('operand');
    expect(crossed.modifier).toBe('');
    expect(showModifier(crossed, catalog)).toBe(false);
    expect(showModifier(rsi3, catalog)).toBe(true);
  });

  it('보유 지표는 교차·유지를 쓰지 않는다', () => {
    const pnl = withLeft({ ...rsi3, op: 'crosses_above' }, indicator('unrealized_pnl_pct'));
    expect(pnl.op).toBe('gte');
    expect(pnl.modifier).toBe('');
    expect(showModifier(pnl, catalog)).toBe(false);
  });

  it('지표를 쓸 수 없는 이유', () => {
    const ctx = { cadence: 'CLOSE' as const, market: 'KR' as const, held: true, side: 'left' as const, otherScope: null };
    expect(indicatorAvailability(indicator('foreign_net_buy'), { ...ctx, market: 'US' })).toEqual({ enabled: false, reason: '국내 종목만' });
    expect(indicatorAvailability(indicator('weight_pct'), { ...ctx, held: false })).toEqual({ enabled: false, reason: '보유 종목만' });
    expect(indicatorAvailability(indicator('rsi'), { ...ctx, cadence: 'INTRADAY' })).toEqual({ enabled: false, reason: '종가에만 계산돼요' });
    expect(indicatorAvailability(indicator('rsi'), { ...ctx, cadence: 'INTRADAY', side: 'right' })).toEqual({ enabled: true });
    expect(indicatorAvailability(indicator('weight_pct'), { ...ctx, otherScope: 'market' })).toEqual({
      enabled: false,
      reason: '다른 지표와 함께 쓸 수 없어요',
    });
  });

  it('지금 고르는 칸을 뺀 나머지 지표의 범위', () => {
    const conditions = [rsi3, { ...emptyCondition(), left: operandFor(indicator('weight_pct')) }];
    expect(scopeInUse(conditions, { index: 1, side: 'left' }, catalog)).toBe('market');
    expect(scopeInUse([rsi3], { index: 0, side: 'left' }, catalog)).toBeNull();
  });

  it('변형 선택지 — 장중 왼쪽은 그대로뿐, 수급은 최근 N일 네 가지', () => {
    expect(transformChoices(indicator('price'), 'INTRADAY', 'left', catalog).map((c) => c.label)).toEqual(['그대로']);
    expect(transformChoices(indicator('foreign_net_buy'), 'CLOSE', 'left', catalog).map((c) => c.label)).toEqual([
      '그대로',
      'N일 전 대비 변화',
      '최근 N일 최고',
      '최근 N일 최저',
      '최근 N일 평균',
      '최근 N일 합계',
    ]);
  });

  it('상수 칸의 단위', () => {
    expect(constUnit(indicator('price'), { type: 'identity' }, 'KR')).toBe('원');
    expect(constUnit(indicator('price'), { type: 'identity' }, 'US')).toBe('$');
    expect(constUnit(indicator('price'), { type: 'pct', n: '5' }, 'KR')).toBe('%');
    expect(constUnit(indicator('volume_ratio'), { type: 'identity' }, 'KR')).toBe('배');
    expect(constUnit(null, { type: 'identity' }, 'KR')).toBe('');
  });
});

describe('수정 왕복 — Review Focus 3', () => {
  it('조립형: 상세의 spec·간격·만료일이 그대로 돌아간다', () => {
    const draft = draftFromDetail(composableDetailFixture);
    expect(draft.dirty).toBe(false);
    expect(draft.mode).toBe('edit');

    const request = draftToRequest(draft, catalog, now)!;
    expect(request).toEqual({
      instrument_id: composableDetailFixture.instrument.id,
      name: composableDetailFixture.name,
      cadence: 'INTRADAY',
      notify_mode: 'COOLDOWN',
      cooldown_min: 60,
      expires_at: '2026-12-31T23:59:59+09:00',
      trigger_type: 'COMPOSABLE',
      trigger_spec: composableDetailFixture.trigger_spec,
    });
  });

  it('손대지 않은 유효기간은 저장된 시각 그대로, 고치면 새로 계산한다', () => {
    const weekly: AlertDetail = { ...presetDetailFixture, expires_at: '2026-10-18T12:00:00+09:00' };
    const draft = draftFromDetail(weekly);
    expect(draftToRequest(draft, catalog, now)!.expires_at).toBe('2026-10-18T12:00:00+09:00');

    const changed = draftReducer(draft, { type: 'expiry-date', value: '2026-10-20' });
    expect(draftToRequest(changed, catalog, now)!.expires_at).toBe('2026-10-20T23:59:59+09:00');
  });

  it('프리셋: 가격과 방향', () => {
    const request = draftToRequest(draftFromDetail(presetDetailFixture), catalog, now)!;
    expect(request.trigger_spec).toEqual(presetDetailFixture.trigger_spec);
    expect(request.expires_at).toBeNull();
  });

  it('프리셋: 손실 수익률의 부호', () => {
    const loss: AlertDetail = {
      ...presetDetailFixture,
      cadence: 'CLOSE',
      trigger_spec: { preset_key: 'pnl_reach', params: { direction: 'loss', pct: -10 } },
    };
    const draft = draftFromDetail(loss);
    expect(draft.params.pct).toBe('10');
    expect(draftToRequest(draft, catalog, now)!.trigger_spec).toEqual(loss.trigger_spec);
  });

  it('수정 중인 미리보기는 alert_id를 싣는다', () => {
    expect(draftToPreview(draftFromDetail(presetDetailFixture), catalog, now)!.alert_id).toBe('a-satisfied');
    const fresh = run(newDraft(SAMSUNG), { type: 'preset', preset: preset('price_reach') });
    expect('alert_id' in draftToPreview(fresh, catalog, now)!).toBe(false);
  });
});

describe('프리셋 입력 칸', () => {
  it('라벨 · 선택지 이름 · 단위', () => {
    expect(fieldSpec('price_reach', 'direction').choices).toEqual({ up: '이상', down: '이하' });
    expect(fieldSpec('price_reach', 'price').unit?.('US')).toBe('$');
    expect(fieldSpec('pnl_reach', 'direction').choices).toEqual({ profit: '수익', loss: '손실' });
    expect(fieldSpec('모르는_프리셋', 'x').label).toBe('x');
  });

  it('기간 칩은 범위 안의 값만', () => {
    const window = preset('box_breakout').param_schema[0];
    expect(periodChips(window)).toEqual([5, 20, 60, 120]);
    expect(periodChips({ ...window, max: 30 })).toEqual([5, 20]);
  });

  it('쓸 수 없는 프리셋은 숨기지 않고 사유를 단다', () => {
    expect(presetAvailability(preset('investor_streak'), APPLE)).toEqual({ enabled: false, reason: '국내 종목만' });
    expect(presetAvailability(preset('pnl_reach'), SDI)).toEqual({ enabled: false, reason: '보유 종목만' });
    expect(presetAvailability(preset('price_reach'), APPLE)).toEqual({ enabled: true });
  });
});

describe('칸별 오류', () => {
  const errors = [
    { path: 'trigger_spec.params.price', code: 'REQUIRED', message: '가격을 입력해 주세요' },
    { path: 'trigger_spec.conditions[0].right.const', code: 'REQUIRED', message: '기준값을 입력해 주세요' },
    { path: 'instrument_id', code: 'NOT_HELD', message: '보유한 종목에만 걸 수 있어요' },
  ];

  it('정확한 경로, 아래 경로, 그 밖', () => {
    expect(errorAt(errors, 'trigger_spec.params.price')).toBe('가격을 입력해 주세요');
    expect(errorUnder(errors, 'trigger_spec.conditions[0].right')).toBe('기준값을 입력해 주세요');
    expect(errorUnder(errors, 'trigger_spec.conditions[1]')).toBeUndefined();
    expect(errorsOutside(errors, ['trigger_spec.params', 'trigger_spec.conditions']).map((e) => e.path)).toEqual([
      'instrument_id',
    ]);
  });
});
```

- [ ] **Step 2: 테스트가 실패하는지 본다**

Run: `npx jest src/__tests__/editorDraft.test.ts`
Expected: FAIL — `Cannot find module '@/screens/alertEditor/draft'`.

- [ ] **Step 3: 초안 모듈을 쓴다**

`front-end/src/screens/alertEditor/draft.ts`:

```ts
import type {
  AlertCatalog,
  AlertDetail,
  AlertRequest,
  Cadence,
  CatalogIndicator,
  CatalogPreset,
  ComposableSpec,
  Condition,
  Modifier,
  NotifyMode,
  Operand,
  OperatorKey,
  PresetSpec,
  PreviewRequest,
  Transform,
  TriggerType,
  WindowFnKey,
} from '@/api/alertTypes';
import type { EditorInstrument } from '@/app/navigation/types';
import { type ExpiryChoice, expiresAtFor } from '@/screens/alerts/expiry';

/**
 * 새 알림 흐름의 초안.
 *
 * 숫자 칸은 사용자가 친 글자 그대로 들고 있다가 요청을 만들 때 숫자로 바꾼다.
 * 칸이 비었거나 숫자가 아니면 null을 보내 서버가 그 칸의 경로로 오류를 돌려주게 한다 —
 * 검증 규칙은 서버 한 곳에 있다(§14). 프론트는 서버 규칙을 다시 쓰지 않는다.
 */

export type DraftInstrument = EditorInstrument;

export type TransformDraft =
  | { type: 'identity' }
  | { type: 'window'; fn: WindowFnKey; n: string }
  | { type: 'delta'; n: string }
  | { type: 'pct'; n: string };

export type OperandDraft = {
  /** 아직 고르지 않았으면 null. */
  indicator: string | null;
  params: Record<string, string>;
  transform: TransformDraft;
};

export type RightDraft = { kind: 'const'; value: string } | { kind: 'operand'; operand: OperandDraft };

export type ConditionDraft = {
  left: OperandDraft;
  op: OperatorKey;
  right: RightDraft;
  /** 유지 칸. 종가는 N일 연속, 장중은 N분 유지 — 뜻은 평가 시점이 정한다. 빈 글자면 없음. */
  modifier: string;
};

export type Draft = {
  mode: 'new' | 'edit';
  alertId: string | null;
  instrument: DraftInstrument | null;
  triggerType: TriggerType | null;
  presetKey: string | null;
  params: Record<string, string>;
  cadence: Cadence;
  conditions: ConditionDraft[];
  notifyMode: NotifyMode;
  cooldownMin: string;
  expiry: ExpiryChoice;
  /** 날짜 지정일 때 `YYYY-MM-DD`. */
  expiryDate: string;
  /**
   * 수정으로 열었을 때 저장돼 있던 만료 시각. 유효기간을 건드리지 않으면 이 값을 그대로 보낸다 —
   * 1주·1개월로 만든 만료(예: 12:00)가 날짜 지정의 23:59:59로 바뀌지 않게 한다.
   */
  keptExpiresAt: string | null;
  name: string;
  /** 사용자가 이름 칸을 건드렸는가. 건드리기 전에는 기본 이름을 따라간다. */
  nameTouched: boolean;
  /** 처음 연 뒤 바뀐 것이 있는가. 닫을 때 버릴지 묻는 기준이다. */
  dirty: boolean;
};

export type DraftAction =
  | { type: 'instrument'; instrument: DraftInstrument }
  | { type: 'preset'; preset: CatalogPreset }
  | { type: 'composable' }
  | { type: 'param'; key: string; value: string }
  | { type: 'cadence'; cadence: Cadence; catalog: AlertCatalog }
  | { type: 'condition'; index: number; condition: ConditionDraft }
  | { type: 'add-condition' }
  | { type: 'remove-condition'; index: number }
  | { type: 'notify-mode'; mode: NotifyMode }
  | { type: 'cooldown'; value: string }
  | { type: 'expiry'; choice: ExpiryChoice }
  | { type: 'expiry-date'; value: string }
  | { type: 'name'; value: string };

export const MAX_CONDITIONS = 5;
export const NAME_MAX = 40;
const DEFAULT_COOLDOWN = '60';

/** 칸의 글자를 숫자로. 천 단위 쉼표와 U+2212 빼기를 받아 준다. 비었거나 숫자가 아니면 null. */
export function toNumber(text: string): number | null {
  const normalized = text.trim().replace(/,/g, '').replace(/−/g, '-');
  if (normalized === '') return null;
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}

function text(n: number | null | undefined): string {
  return n === null || n === undefined ? '' : String(n);
}

export function isPresetSpec(spec: ComposableSpec | PresetSpec): spec is PresetSpec {
  return 'preset_key' in spec;
}

export function emptyOperand(): OperandDraft {
  return { indicator: null, params: {}, transform: { type: 'identity' } };
}

export function emptyCondition(): ConditionDraft {
  return { left: emptyOperand(), op: 'gte', right: { kind: 'const', value: '' }, modifier: '' };
}

/** 지표를 고르면 그 지표의 기본 파라미터로 채운다. */
export function operandFor(indicator: CatalogIndicator): OperandDraft {
  return {
    indicator: indicator.key,
    params: Object.fromEntries(indicator.params.map((p) => [p.key, String(p.default)])),
    transform: { type: 'identity' },
  };
}

export function newDraft(instrument?: DraftInstrument): Draft {
  return {
    mode: 'new',
    alertId: null,
    instrument: instrument ?? null,
    triggerType: null,
    presetKey: null,
    params: {},
    cadence: 'CLOSE',
    conditions: [],
    notifyMode: 'EDGE_REARM',
    cooldownMin: DEFAULT_COOLDOWN,
    expiry: 'NONE',
    expiryDate: '',
    keptExpiresAt: null,
    name: '',
    nameTouched: false,
    dirty: false,
  };
}

/**
 * 프리셋 입력 칸의 처음 값. 카탈로그 기본값을 쓰고, 가격 도달의 가격만 직전 종가로 채운다(§12.5.3).
 * 사용자는 대개 지금 가격에서 조금 위·아래를 넣는다.
 */
export function presetDefaults(preset: CatalogPreset, instrument: DraftInstrument | null): Record<string, string> {
  return Object.fromEntries(
    preset.param_schema.map((param) => {
      if (preset.key === 'price_reach' && param.key === 'price') {
        return [param.key, instrument?.lastClose != null ? String(instrument.lastClose) : ''];
      }
      return [param.key, param.default === null ? '' : String(param.default)];
    }),
  );
}

/** 수익률 도달의 손실은 음수로 보낸다. 칸에는 크기만 둔다. */
function isLossPct(presetKey: string | null, key: string, params: Record<string, string>): boolean {
  return presetKey === 'pnl_reach' && key === 'pct' && params.direction === 'loss';
}

function transformDraft(t: Transform): TransformDraft {
  switch (t.type) {
    case 'identity':
      return { type: 'identity' };
    case 'window':
      return { type: 'window', fn: t.fn, n: text(t.n) };
    case 'delta':
      return { type: 'delta', n: text(t.n) };
    case 'pct':
      return { type: 'pct', n: text(t.n) };
  }
}

function operandDraft(o: Operand): OperandDraft {
  return {
    indicator: o.indicator,
    params: Object.fromEntries(Object.entries(o.indicator_params ?? {}).map(([k, v]) => [k, text(v)])),
    transform: transformDraft(o.transform),
  };
}

function modifierText(m: Modifier): string {
  if (m === null) return '';
  return 'streak' in m ? text(m.streak) : text(m.persist_min);
}

function conditionDraft(c: Condition): ConditionDraft {
  return {
    left: operandDraft(c.left),
    op: c.op,
    right: 'const' in c.right ? { kind: 'const', value: text(c.right.const) } : { kind: 'operand', operand: operandDraft(c.right) },
    modifier: modifierText(c.modifier),
  };
}

/**
 * 수정 화면의 처음 초안. 상세의 trigger_spec을 그대로 푼다 — 저장된 spec에는 `lag`가 없다.
 * 종목은 바꿀 수 없으므로 보유 여부를 묻지 않는다(수정은 보유를 검사하지 않는다, §14.1).
 */
export function draftFromDetail(detail: AlertDetail): Draft {
  const base = newDraft({
    id: detail.instrument.id,
    label: detail.instrument.label ?? '',
    market: detail.instrument.market ?? 'KR',
    held: true,
    lastClose: null,
    lastCloseOn: null,
  });
  const common: Draft = {
    ...base,
    mode: 'edit',
    alertId: detail.alert_id,
    triggerType: detail.trigger_type,
    cadence: detail.cadence,
    notifyMode: detail.notify_mode,
    cooldownMin: detail.cooldown_min === null ? DEFAULT_COOLDOWN : String(detail.cooldown_min),
    expiry: detail.expires_at ? 'DATE' : 'NONE',
    expiryDate: detail.expires_at ? detail.expires_at.slice(0, 10) : '',
    keptExpiresAt: detail.expires_at,
    name: detail.name,
    nameTouched: true,
  };
  const spec = detail.trigger_spec;
  if (isPresetSpec(spec)) {
    return {
      ...common,
      presetKey: spec.preset_key,
      params: Object.fromEntries(
        Object.entries(spec.params).map(([key, value]) => {
          if (spec.preset_key === 'pnl_reach' && key === 'pct' && typeof value === 'number') {
            return [key, String(Math.abs(value))];
          }
          return [key, value === null ? '' : String(value)];
        }),
      ),
    };
  }
  return { ...common, conditions: spec.conditions.map(conditionDraft) };
}

/**
 * 평가 시점을 바꿀 때 맞지 않게 되는 칸을 비운다(§12.5.4).
 * 장중 왼쪽에는 장중 지표의 `그대로`만 온다. 유지 칸은 뜻이 바뀐다(N일 연속 ↔ N분 유지).
 */
export function fitCondition(c: ConditionDraft, cadence: Cadence, catalog: AlertCatalog): ConditionDraft {
  let next = c;
  if (cadence === 'INTRADAY') {
    const left = catalog.indicators.find((i) => i.key === c.left.indicator);
    if (left && !left.intraday_left) next = { ...next, left: emptyOperand() };
    else if (next.left.transform.type !== 'identity') {
      next = { ...next, left: { ...next.left, transform: { type: 'identity' } } };
    }
  }
  if (next.modifier !== '') next = { ...next, modifier: '' };
  return next;
}

/** 이 평가 시점으로 바꾸면 비워지는 칸이 있는가. 있으면 화면이 먼저 묻는다. */
export function cadenceChangeClears(draft: Draft, cadence: Cadence, catalog: AlertCatalog): boolean {
  if (draft.triggerType !== 'COMPOSABLE' || draft.cadence === cadence) return false;
  return draft.conditions.some((c) => fitCondition(c, cadence, catalog) !== c);
}

/** 종가 알림에는 `N분마다 다시`가 없다(§6.2). */
function withCadence(draft: Draft, cadence: Cadence): Draft {
  return {
    ...draft,
    cadence,
    notifyMode: cadence === 'CLOSE' && draft.notifyMode === 'COOLDOWN' ? 'EDGE_REARM' : draft.notifyMode,
  };
}

function applyParam(presetKey: string | null, params: Record<string, string>, key: string, value: string) {
  const next = { ...params, [key]: value };
  // 과매도를 고르면 기준 기본값이 30이다. 카탈로그 기본값은 과매수의 70 하나뿐이다.
  if (presetKey === 'rsi_zone' && key === 'zone') next.level = value === 'oversold' ? '30' : '70';
  return next;
}

function apply(draft: Draft, action: DraftAction): Draft {
  switch (action.type) {
    case 'instrument':
      if (draft.instrument?.id === action.instrument.id) return { ...draft, instrument: action.instrument };
      // 종목이 바뀌면 가격 기준값·통화·쓸 수 있는 지표가 달라진다. 고른 조건을 버린다.
      return { ...draft, instrument: action.instrument, triggerType: null, presetKey: null, params: {}, conditions: [] };
    case 'preset': {
      if (draft.triggerType === 'PRESET' && draft.presetKey === action.preset.key) return draft;
      // 장중·종가 겸용 프리셋은 장중이 기본이다 — "바로 알고 싶은" 조건이다(§12.5.3).
      const cadence: Cadence = action.preset.cadences.includes('INTRADAY') ? 'INTRADAY' : 'CLOSE';
      return withCadence(
        {
          ...draft,
          triggerType: 'PRESET',
          presetKey: action.preset.key,
          params: presetDefaults(action.preset, draft.instrument),
          conditions: [],
        },
        cadence,
      );
    }
    case 'composable':
      if (draft.triggerType === 'COMPOSABLE') return draft;
      return withCadence(
        { ...draft, triggerType: 'COMPOSABLE', presetKey: null, params: {}, conditions: [emptyCondition()] },
        'CLOSE',
      );
    case 'param':
      return { ...draft, params: applyParam(draft.presetKey, draft.params, action.key, action.value) };
    case 'cadence': {
      if (draft.cadence === action.cadence) return draft;
      const conditions =
        draft.triggerType === 'COMPOSABLE'
          ? draft.conditions.map((c) => fitCondition(c, action.cadence, action.catalog))
          : draft.conditions;
      return withCadence({ ...draft, conditions }, action.cadence);
    }
    case 'condition':
      return { ...draft, conditions: draft.conditions.map((c, i) => (i === action.index ? action.condition : c)) };
    case 'add-condition':
      if (draft.conditions.length >= MAX_CONDITIONS) return draft;
      return { ...draft, conditions: [...draft.conditions, emptyCondition()] };
    case 'remove-condition':
      if (draft.conditions.length <= 1) return draft;
      return { ...draft, conditions: draft.conditions.filter((_, i) => i !== action.index) };
    case 'notify-mode':
      return { ...draft, notifyMode: action.mode };
    case 'cooldown':
      return { ...draft, cooldownMin: action.value };
    case 'expiry':
      return { ...draft, expiry: action.choice, keptExpiresAt: null };
    case 'expiry-date':
      return { ...draft, expiryDate: action.value, keptExpiresAt: null };
    case 'name':
      return { ...draft, name: action.value, nameTouched: true };
  }
}

export function draftReducer(draft: Draft, action: DraftAction): Draft {
  const next = apply(draft, action);
  return next === draft ? draft : { ...next, dirty: true };
}

/** 기본 이름 — 프리셋은 `종목명 + 프리셋 라벨`, 조립형은 `종목명 + 첫 조건의 지표`(§12.5.5). */
export function defaultName(draft: Draft, catalog: AlertCatalog): string {
  const label = draft.instrument?.label ?? '';
  let what = '';
  if (draft.triggerType === 'PRESET') {
    what = catalog.presets.find((p) => p.key === draft.presetKey)?.label ?? '';
  } else if (draft.triggerType === 'COMPOSABLE') {
    const key = draft.conditions[0]?.left.indicator;
    what = catalog.indicators.find((i) => i.key === key)?.label ?? '';
  }
  return [label, what].filter(Boolean).join(' ').slice(0, NAME_MAX);
}

export function effectiveName(draft: Draft, catalog: AlertCatalog): string {
  return draft.nameTouched ? draft.name : defaultName(draft, catalog);
}

function transformOut(t: TransformDraft): Transform {
  switch (t.type) {
    case 'identity':
      return { type: 'identity' };
    case 'window':
      return { type: 'window', fn: t.fn, n: toNumber(t.n) };
    case 'delta':
      return { type: 'delta', n: toNumber(t.n) };
    case 'pct':
      return { type: 'pct', n: toNumber(t.n) };
  }
}

/** `lag`는 싣지 않는다. 서버가 컴파일할 때 맞은편을 보고 정한다(§4.2). */
function operandOut(o: OperandDraft): Operand {
  const operand: Operand = { indicator: o.indicator ?? '', transform: transformOut(o.transform) };
  const entries = Object.entries(o.params);
  if (entries.length > 0) {
    operand.indicator_params = Object.fromEntries(entries.map(([k, v]) => [k, toNumber(v)]));
  }
  return operand;
}

function modifierOut(textValue: string, cadence: Cadence): Modifier {
  if (textValue.trim() === '') return null;
  const n = toNumber(textValue);
  return cadence === 'CLOSE' ? { streak: n } : { persist_min: n };
}

function conditionOut(c: ConditionDraft, cadence: Cadence): Condition {
  return {
    left: operandOut(c.left),
    op: c.op,
    right: c.right.kind === 'const' ? { const: toNumber(c.right.value) } : operandOut(c.right.operand),
    modifier: modifierOut(c.modifier, cadence),
  };
}

function presetOut(draft: Draft, catalog: AlertCatalog): PresetSpec {
  const preset = catalog.presets.find((p) => p.key === draft.presetKey);
  const params: Record<string, number | string | null> = {};
  for (const param of preset?.param_schema ?? []) {
    const raw = draft.params[param.key] ?? '';
    if (param.kind === 'choice') {
      params[param.key] = raw === '' ? null : raw;
      continue;
    }
    const n = toNumber(raw);
    params[param.key] = n !== null && isLossPct(draft.presetKey, param.key, draft.params) ? -Math.abs(n) : n;
  }
  return { preset_key: draft.presetKey ?? '', params };
}

/**
 * 초안을 저장 요청으로. 종목이나 조건 종류를 아직 고르지 않았으면 null.
 * `now`는 유효기간 선택지(1주·1개월·3개월)를 시각으로 바꾸는 기준이다.
 */
export function draftToRequest(draft: Draft, catalog: AlertCatalog, now: Date): AlertRequest | null {
  if (!draft.instrument || !draft.triggerType) return null;
  return {
    instrument_id: draft.instrument.id,
    name: effectiveName(draft, catalog),
    cadence: draft.cadence,
    notify_mode: draft.notifyMode,
    cooldown_min: draft.notifyMode === 'COOLDOWN' ? toNumber(draft.cooldownMin) : null,
    expires_at: draft.keptExpiresAt ?? expiresAtFor(draft.expiry, draft.expiryDate, now),
    trigger_type: draft.triggerType,
    trigger_spec:
      draft.triggerType === 'PRESET'
        ? presetOut(draft, catalog)
        : { conditions: draft.conditions.map((c) => conditionOut(c, draft.cadence)) },
  };
}

/** 미리보기 요청. 수정 중이면 `alert_id`를 실어 자기 자신을 중복 검사에서 뺀다(§6.7). */
export function draftToPreview(draft: Draft, catalog: AlertCatalog, now: Date): PreviewRequest | null {
  const request = draftToRequest(draft, catalog, now);
  if (!request) return null;
  return draft.alertId ? { ...request, alert_id: draft.alertId } : request;
}
```

- [ ] **Step 4: 프리셋 칸 정의를 쓴다**

`front-end/src/screens/alertEditor/presetFields.ts`:

```ts
import type { CatalogPreset, Market, PresetParam } from '@/api/alertTypes';
import type { EditorInstrument } from '@/app/navigation/types';

/**
 * 프리셋 입력 칸의 라벨 · 선택지 이름 · 단위 (§12.5.3).
 *
 * 카탈로그는 칸의 키·종류·범위·기본값만 준다. 화면 문구는 여기 있다.
 * 모르는 프리셋이나 칸이 와도 키 이름으로 그려 화면이 깨지지 않는다.
 */

export type FieldSpec = {
  label: string;
  choices?: Record<string, string>;
  unit?: (market: Market) => string;
  /** 기간 칸 — 값 칩(5 · 20 · 60 · 120)과 직접 입력. */
  period?: boolean;
};

const price = (market: Market) => (market === 'US' ? '$' : '원');
const fixed = (unit: string) => () => unit;

const DIRECTION_UP_DOWN = { up: '이상', down: '이하' };
const INVESTOR = { foreign: '외국인', institution: '기관' };

const FIELDS: Record<string, Record<string, FieldSpec>> = {
  price_reach: {
    direction: { label: '방향', choices: DIRECTION_UP_DOWN },
    price: { label: '가격', unit: price },
  },
  change_move: {
    direction: { label: '방향', choices: { up: '오르면', down: '내리면' } },
    pct: { label: '등락률', unit: fixed('%') },
  },
  volume_surge: {
    n: { label: '비교 기간', unit: fixed('일'), period: true },
    multiple: { label: '배수', unit: fixed('배') },
  },
  ma_cross: {
    direction: { label: '종류', choices: { golden: '골든', dead: '데드' } },
    short: { label: '짧은 선', unit: fixed('일'), period: true },
    long: { label: '긴 선', unit: fixed('일'), period: true },
  },
  rsi_zone: {
    zone: { label: '구간', choices: { overbought: '과매수', oversold: '과매도' } },
    level: { label: '기준' },
    n: { label: '기간', unit: fixed('일'), period: true },
  },
  box_breakout: {
    window_days: { label: '관찰 기간', unit: fixed('일'), period: true },
    max_range_pct: { label: '최대 폭', unit: fixed('%') },
    direction: { label: '방향', choices: { up: '상단 돌파', down: '하단 이탈' } },
  },
  investor_streak: {
    investor: { label: '주체', choices: INVESTOR },
    side: { label: '방향', choices: { buy: '순매수', sell: '순매도' } },
    days: { label: '일수', unit: fixed('일') },
  },
  investor_turn: {
    investor: { label: '주체', choices: INVESTOR },
    side: { label: '방향', choices: { buy: '순매수로', sell: '순매도로' } },
  },
  pnl_reach: {
    direction: { label: '방향', choices: { profit: '수익', loss: '손실' } },
    pct: { label: '수익률', unit: fixed('%') },
  },
};

export function fieldSpec(presetKey: string, paramKey: string): FieldSpec {
  return FIELDS[presetKey]?.[paramKey] ?? { label: paramKey };
}

const PERIOD_CHIPS = [5, 20, 60, 120];

/** 기간 칸의 값 칩. 카탈로그 범위 밖의 값은 뺀다. */
export function periodChips(param: PresetParam): number[] {
  return PERIOD_CHIPS.filter((n) => (param.min === null || n >= param.min) && (param.max === null || n <= param.max));
}

export type Availability = { enabled: true } | { enabled: false; reason: string };

/**
 * 쓸 수 없는 프리셋은 숨기지 않고 비활성 + 사유 한 줄로 둔다(§12.5.2).
 * 미국 종목의 수급 프리셋 `국내 종목만`, 보유하지 않은 종목의 수익률 도달 `보유 종목만`.
 */
export function presetAvailability(preset: CatalogPreset, instrument: EditorInstrument): Availability {
  if (!preset.markets.includes(instrument.market)) {
    return { enabled: false, reason: preset.markets.length === 1 && preset.markets[0] === 'KR' ? '국내 종목만' : '이 종목에는 쓸 수 없어요' };
  }
  if (preset.scope === 'user' && !instrument.held) return { enabled: false, reason: '보유 종목만' };
  return { enabled: true };
}
```

- [ ] **Step 5: 조립형 칸 규칙을 쓴다**

`front-end/src/screens/alertEditor/composable.ts`:

```ts
import type {
  AlertCatalog,
  Cadence,
  CatalogIndicator,
  Market,
  OperatorKey,
  WindowFnKey,
} from '@/api/alertTypes';
import type { Availability } from '@/screens/alertEditor/presetFields';
import { type ConditionDraft, type TransformDraft, emptyOperand } from '@/screens/alertEditor/draft';

export type { Availability } from '@/screens/alertEditor/presetFields';

/**
 * 조건 만들기의 칸 규칙 (§12.5.4). 말이 안 되는 조합을 고르기 전에 막는다 —
 * 서버 검증(§14.2)이 마지막 관문이고, 여기서는 고를 수 없는 것을 비활성으로 보이는 일만 한다.
 */

/** 지표 시트의 묶음 순서. 카탈로그에 이 밖의 묶음이 오면 뒤에 붙인다. */
export const CATEGORY_ORDER = ['시세', '기술지표', '수급', '내 보유'];

export function findIndicator(catalog: AlertCatalog, key: string | null): CatalogIndicator | null {
  return catalog.indicators.find((i) => i.key === key) ?? null;
}

export type IndicatorContext = {
  cadence: Cadence;
  market: Market;
  held: boolean;
  side: 'left' | 'right';
  /** 이 칸을 뺀 나머지 지표의 범위. 시장 지표와 보유 지표는 한 알림에 섞지 않는다(§5.1). */
  otherScope: 'market' | 'user' | null;
};

export function indicatorAvailability(indicator: CatalogIndicator, ctx: IndicatorContext): Availability {
  if (!indicator.markets.includes(ctx.market)) {
    return {
      enabled: false,
      reason: indicator.markets.length === 1 && indicator.markets[0] === 'KR' ? '국내 종목만' : '이 종목에는 쓸 수 없어요',
    };
  }
  if (indicator.scope === 'user' && !ctx.held) return { enabled: false, reason: '보유 종목만' };
  // 장중 알림의 왼쪽은 장중 지표뿐이다. 오른쪽에는 어제까지 확정된 값이 올 수 있다(§3.1).
  if (ctx.side === 'left' && ctx.cadence === 'INTRADAY' && !indicator.intraday_left) {
    return { enabled: false, reason: '종가에만 계산돼요' };
  }
  if (ctx.otherScope !== null && ctx.otherScope !== indicator.scope) {
    return { enabled: false, reason: '다른 지표와 함께 쓸 수 없어요' };
  }
  return { enabled: true };
}

export function scopeInUse(
  conditions: ConditionDraft[],
  except: { index: number; side: 'left' | 'right' },
  catalog: AlertCatalog,
): 'market' | 'user' | null {
  for (let i = 0; i < conditions.length; i++) {
    const c = conditions[i];
    const sides: ['left' | 'right', string | null][] = [
      ['left', c.left.indicator],
      ['right', c.right.kind === 'operand' ? c.right.operand.indicator : null],
    ];
    for (const [side, key] of sides) {
      if (i === except.index && side === except.side) continue;
      const indicator = findIndicator(catalog, key);
      if (indicator) return indicator.scope;
    }
  }
  return null;
}

export type TransformChoice = { label: string; transform: TransformDraft };

/**
 * 변형 선택지(§12.5.4) — `그대로` · `최근 N일 최고/최저/평균/합계` · `N일 전 대비 변화` · `N일 전 대비 변화율`.
 * 순서는 지표의 허용 변형 순서를 따르고, 장중 알림의 왼쪽은 `그대로`뿐이다.
 * 오늘을 넣을지는 고르지 않는다. 서버가 맞은편을 보고 정한다(§4.2).
 */
export function transformChoices(
  indicator: CatalogIndicator,
  cadence: Cadence,
  side: 'left' | 'right',
  catalog: AlertCatalog,
): TransformChoice[] {
  const types = side === 'left' && cadence === 'INTRADAY' ? (['identity'] as const) : indicator.allowed_transforms;
  const choices: TransformChoice[] = [];
  for (const type of types) {
    const entry = catalog.transforms.find((t) => t.key === type);
    if (type === 'identity') choices.push({ label: entry?.label ?? '그대로', transform: { type: 'identity' } });
    else if (type === 'window') {
      for (const fn of entry?.fns ?? []) {
        choices.push({ label: `최근 N일 ${fn.label}`, transform: { type: 'window', fn: fn.key as WindowFnKey, n: '5' } });
      }
    } else choices.push({ label: entry?.label ?? type, transform: { type, n: '5' } });
  }
  return choices;
}

/** 같은 선택지인가 — N은 따지지 않는다. */
export function sameTransform(a: TransformDraft, b: TransformDraft): boolean {
  if (a.type !== b.type) return false;
  return a.type !== 'window' || b.type !== 'window' || a.fn === b.fn;
}

export function unitSuffix(unit: CatalogIndicator['unit'], market: Market): string {
  switch (unit) {
    case 'price':
      return market === 'US' ? '$' : '원';
    case 'krw':
      return '원';
    case 'percent':
      return '%';
    case 'ratio':
      return '배';
    case 'shares':
      return '주';
    case 'index':
      return '';
  }
}

/** 상수 기준값 칸의 단위. 변화율은 퍼센트이고 나머지 변형은 지표 단위 그대로다(§14.2). */
export function constUnit(left: CatalogIndicator | null, transform: TransformDraft, market: Market): string {
  if (!left) return '';
  return transform.type === 'pct' ? '%' : unitSuffix(left.unit, market);
}

function isCross(op: OperatorKey): boolean {
  return op === 'crosses_above' || op === 'crosses_below';
}

/** 유지 칸은 교차 연산자와 보유 지표에서 숨긴다 — 한 시점의 사건이거나 하루 한 벌의 값이다. */
export function showModifier(condition: ConditionDraft, catalog: AlertCatalog): boolean {
  if (isCross(condition.op)) return false;
  return findIndicator(catalog, condition.left.indicator)?.scope !== 'user';
}

/** 교차는 지표끼리만 견준다(§5.2). 상수였으면 지표 칸으로 바꾸고 유지 칸을 비운다. */
export function withOperator(condition: ConditionDraft, op: OperatorKey): ConditionDraft {
  if (!isCross(op)) return { ...condition, op };
  return {
    ...condition,
    op,
    right: condition.right.kind === 'const' ? { kind: 'operand', operand: emptyOperand() } : condition.right,
    modifier: '',
  };
}

/** 왼쪽 지표를 바꾼다. 그 지표가 받지 않는 연산자는 `≥`로, 보유 지표면 유지 칸을 비운다. */
export function withLeft(condition: ConditionDraft, indicator: CatalogIndicator): ConditionDraft {
  const params = Object.fromEntries(indicator.params.map((p) => [p.key, String(p.default)]));
  let next: ConditionDraft = { ...condition, left: { indicator: indicator.key, params, transform: { type: 'identity' } } };
  if (!indicator.allowed_operators.includes(next.op)) {
    next = { ...next, op: 'gte', right: next.right.kind === 'operand' && isCross(condition.op) ? { kind: 'const', value: '' } : next.right };
  }
  if (indicator.scope === 'user') next = { ...next, modifier: '' };
  return next;
}
```

`withLeft`의 연산자 되돌림은 교차였을 때만 기준값을 상수 칸으로 돌린다. 교차가 아니던 지표 비교는 그대로 둔다.

- [ ] **Step 6: 칸별 오류 찾기를 쓴다**

`front-end/src/screens/alertEditor/fieldErrors.ts`:

```ts
import type { FieldError } from '@/api/types';

/**
 * 서버 오류의 `path`로 칸을 찾는다(§11.4). 폼은 그 칸 아래에 `message`를 그대로 띄운다.
 * 칸에 붙지 않는 오류는 화면 아래에 모아 보인다 — 숨기면 저장이 왜 안 되는지 알 수 없다.
 */

function isUnder(path: string, prefix: string): boolean {
  return path === prefix || path.startsWith(`${prefix}.`) || path.startsWith(`${prefix}[`);
}

export function errorAt(errors: FieldError[], path: string): string | undefined {
  return errors.find((e) => e.path === path)?.message;
}

export function errorUnder(errors: FieldError[], prefix: string): string | undefined {
  return errors.find((e) => isUnder(e.path, prefix))?.message;
}

export function errorsOutside(errors: FieldError[], prefixes: string[]): FieldError[] {
  return errors.filter((e) => !prefixes.some((prefix) => isUnder(e.path, prefix)));
}
```

`PreviewResponse.errors`의 원소 타입을 `FieldError`로 맞춘다 — `alertTypes.ts`에서 `errors: FieldError[]`로 바꾸고 `import type { Envelope, FieldError } from '@/api/types';`로 가져온다.

- [ ] **Step 7: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest src/__tests__/editorDraft.test.ts && npx tsc --noEmit`
Expected: PASS. `composable.ts`와 `draft.ts`가 서로를 import하지 않는다 — `composable.ts`가 `draft.ts`를 가져오기만 한다(순환이 생기면 `emptyOperand`를 `draft.ts`에 두고 `composable.ts`만 그것을 가져오는지 확인한다).

- [ ] **Step 8: 커밋한다**

```bash
git add src/screens/alertEditor src/api/alertTypes.ts src/__tests__/editorDraft.test.ts
git commit -m "feat: 새 알림 초안의 상태와 요청 변환, 입력 칸 규칙을 둔다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: 새 알림 흐름의 뼈대 — 모달 · 초안 컨텍스트 · 종목 선택 · 조건 선택

**Files:**
- Create: `front-end/src/screens/alertEditor/types.ts`
- Create: `front-end/src/screens/alertEditor/EditorContext.tsx`
- Create: `front-end/src/screens/alertEditor/useDebounced.ts`
- Create: `front-end/src/screens/alertEditor/AlertEditorNavigator.tsx`
- Create: `front-end/src/screens/alertEditor/InstrumentStep.tsx`
- Create: `front-end/src/screens/alertEditor/TriggerStep.tsx`
- Modify: `front-end/src/app/navigation/RootStack.tsx` (`alert-editor` 모달 등록)
- Create: `front-end/src/testing/openEditor.tsx`
- Test: `front-end/src/__tests__/alertEditorFlow.test.tsx`

**Interfaces:**
- Consumes: `Draft` · `DraftAction` · `draftReducer` · `newDraft` · `draftFromDetail` · `draftToPreview` · `presetAvailability` (Task 8), `useAlertCatalog` · `useInstruments` · `usePreview` · `fetchAlert` · `keys` (Task 3), `ConfirmSheet` · `TextButton` (Task 4), `renderWithStack` (Task 6)
- Produces:
  - `type EditorParamList = { instrument: undefined; trigger: undefined; preset: undefined; composable: undefined; settings: undefined }`
  - `<EditorProvider initial catalog>` · `useEditor(): { draft, dispatch, catalog, openedAt, finished, finish(alertId) }` · `useDraftPreview()` (= `usePreview(draftToPreview(draft, catalog, openedAt))`)
  - `useDebounced<T>(value: T, ms: number): T`
  - 테스트: `openEditor(start: EditorStart, routes?: Route[]): Promise<{ calls, moves, navigation }>`, `searchRoute`
  - `<AlertEditorNavigator />` — 이 태스크는 `instrument` · `trigger` 두 단계만 등록한다. `preset`(Task 10) · `composable`(Task 11) · `settings`(Task 13)는 그 태스크가 같은 `Stack.Navigator`에 한 줄씩 더한다.
  - `finish(alertId)`를 부르면: 새 알림은 모달을 알림 상세로 바꾸고(`replace('alert')`), 수정은 모달을 닫아 들어온 알림 상세로 돌아간다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`front-end/src/testing/openEditor.tsx` — Task 10·11·13의 테스트도 이것으로 흐름을 연다.

```tsx
import type { EditorStart } from '@/app/navigation/types';
import { catalogFixture, heldFixture, instrumentsFixture } from '@/fixtures/alerts';
import { AlertEditorNavigator } from '@/screens/alertEditor/AlertEditorNavigator';
import { renderWithStack } from '@/testing/renderWithStack';
import { type Route, serveRoutes } from '@/testing/serveRoutes';

/**
 * 새 알림 흐름을 연다. 카탈로그와 종목 검색 대역을 늘 깔고, 테스트가 준 경로가 그보다 먼저 답한다.
 * 앱 코드는 이 파일을 쓰지 않는다.
 */

export const searchRoute: Route = {
  path: '/instruments',
  body: (_body, url) => (url.includes('held=true') ? heldFixture : instrumentsFixture),
};

export async function openEditor(start: EditorStart, routes: Route[] = []) {
  // 테스트가 준 경로를 앞에 둔다. 먼저 맞는 경로가 답하므로 기본 대역을 덮어쓸 수 있다.
  const calls = serveRoutes([...routes, { path: '/alerts/catalog', body: catalogFixture }, searchRoute]);
  const moves: { name: string; params: unknown }[] = [];
  const { navigation } = await renderWithStack('alert-editor', AlertEditorNavigator, start, {
    others: ['alert'],
    onNavigate: (name, params) => moves.push({ name, params }),
  });
  return { calls, moves, navigation };
}
```

`front-end/src/__tests__/alertEditorFlow.test.tsx`:

```tsx
import { StackActions } from '@react-navigation/native';
import { act, fireEvent, screen, waitFor } from '@testing-library/react-native';

import { setAccessToken } from '@/api/client';
import { catalogFixture } from '@/fixtures/alerts';
import { openEditor } from '@/testing/openEditor';

beforeEach(() => setAccessToken('tok'));
afterEach(() => setAccessToken(null));

describe('대상 종목', () => {
  it('검색어가 없으면 보유 종목 구역, 입력이 멈추면 검색 결과', async () => {
    const { calls } = await openEditor({ mode: 'new' });
    await waitFor(() => expect(screen.getByText('보유 종목')).toBeTruthy());
    expect(screen.getByText('NAVER')).toBeTruthy();

    await fireEvent.changeText(screen.getByLabelText('종목 검색'), '삼성');

    // 라벨은 디바운스가 끝나는 순간 바뀌고 행은 응답이 와야 바뀐다(앞 결과를 들고 있다).
    await waitFor(() => expect(screen.getByText('삼성SDI')).toBeTruthy());
    expect(screen.getByText('검색 결과')).toBeTruthy();
    expect(screen.getAllByText('보유').length).toBeGreaterThan(0);
    expect(calls.some((c) => c.url.includes(`q=${encodeURIComponent('삼성')}`))).toBe(true);
  });

  it('보유 종목이 없으면 검색을 권한다', async () => {
    await openEditor({ mode: 'new' }, [{ path: '/instruments', body: { rows: [] } }]);
    await waitFor(() => expect(screen.getByText('종목명이나 종목코드로 검색하세요')).toBeTruthy());
  });

  it('종목을 고르면 조건 선택 — 직접 만들기와 프리셋 9종', async () => {
    await openEditor({ mode: 'new' });
    await waitFor(() => expect(screen.getByText('삼성전자')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '삼성전자' }));

    await waitFor(() => expect(screen.getByText('＋ 직접 조건 만들기')).toBeTruthy());
    for (const label of catalogFixture.presets.map((p) => p.label)) {
      expect(screen.getByText(label)).toBeTruthy();
    }
    expect(screen.getAllByText('장중·종가')).toHaveLength(3);
  });
});

describe('조건 선택', () => {
  it('미국 종목의 수급 프리셋은 비활성 + 국내 종목만', async () => {
    await openEditor({
      mode: 'new',
      instrument: { id: 'i-apple', label: '애플', market: 'US', held: true, lastClose: 230.1, lastCloseOn: '2026-09-25' },
    });
    await waitFor(() => expect(screen.getByText('＋ 직접 조건 만들기')).toBeTruthy());

    expect(screen.getAllByText('국내 종목만')).toHaveLength(2);
    expect(screen.getByRole('button', { name: '외국인·기관 연속 순매수' }).props.accessibilityState.disabled).toBe(true);
  });

  it('보유하지 않은 종목의 수익률 도달은 보유 종목만', async () => {
    await openEditor({
      mode: 'new',
      instrument: { id: 'i-sdi', label: '삼성SDI', market: 'KR', held: false, lastClose: null, lastCloseOn: null },
    });
    await waitFor(() => expect(screen.getByText('보유 종목만')).toBeTruthy());
  });
});

describe('닫기', () => {
  /*
   * 모달을 걷어내는 루트 동작으로 확인한다. 컨테이너의 goBack은 모달 안 스택이 먼저 받아
   * 한 단계 뒤로 갈 뿐이고, v7의 navigate는 다른 이름이면 새로 쌓을 뿐이라 둘 다 가드가 돌지 않는다.
   * popTo는 그 아래 라우트까지 걷어내므로 모달이 제거된다 — 헤더의 `닫기`·iOS 쓸어내리기와 같은 제거다.
   */
  const leave = (navigation: Awaited<ReturnType<typeof openEditor>>['navigation']) =>
    act(async () => navigation.dispatch(StackActions.popTo('__home')));

  it('손대지 않았으면 묻지 않고 닫는다', async () => {
    const { moves, navigation } = await openEditor({ mode: 'new' });
    await waitFor(() => expect(screen.getByText('보유 종목')).toBeTruthy());

    await leave(navigation);

    await waitFor(() => expect(moves.at(-1)?.name).toBe('__home'));
    expect(screen.queryByText('작성 중인 알림을 버릴까요?')).toBeNull();
  });

  it('작성 중이면 버릴지 묻고, 계속 쓰면 남는다', async () => {
    const { moves, navigation } = await openEditor({ mode: 'new' });
    await waitFor(() => expect(screen.getByText('삼성전자')).toBeTruthy());
    await fireEvent.press(screen.getByRole('button', { name: '삼성전자' }));
    await waitFor(() => expect(screen.getByText('＋ 직접 조건 만들기')).toBeTruthy());

    await leave(navigation);
    await waitFor(() => expect(screen.getByText('작성 중인 알림을 버릴까요?')).toBeTruthy());
    await fireEvent.press(screen.getByRole('button', { name: '계속 쓰기' }));
    expect(moves.some((m) => m.name === '__home')).toBe(false);

    await leave(navigation);
    await waitFor(() => expect(screen.getByText('작성 중인 알림을 버릴까요?')).toBeTruthy());
    await fireEvent.press(screen.getByRole('button', { name: '버리기' }));
    await waitFor(() => expect(moves.at(-1)?.name).toBe('__home'));
  });
});
```

- [ ] **Step 2: 테스트가 실패하는지 본다**

Run: `npx jest src/__tests__/alertEditorFlow.test.tsx`
Expected: FAIL — `Cannot find module '@/screens/alertEditor/AlertEditorNavigator'`.

- [ ] **Step 3: 컨텍스트와 도우미를 쓴다**

`front-end/src/screens/alertEditor/types.ts`:

```ts
/** 새 알림 흐름 안의 단계 (IA §6.1). */
export type EditorParamList = {
  instrument: undefined;
  trigger: undefined;
  preset: undefined;
  composable: undefined;
  settings: undefined;
};
```

`front-end/src/screens/alertEditor/useDebounced.ts`:

```ts
import { useEffect, useState } from 'react';

/** 값이 `ms` 동안 바뀌지 않으면 그 값을 내놓는다. 종목 검색이 0.3초를 쓴다(§12.5.1). */
export function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}
```

`front-end/src/screens/alertEditor/EditorContext.tsx`:

```tsx
import { createContext, useContext, useMemo, useReducer, useState } from 'react';
import type { Dispatch, ReactNode } from 'react';

import type { AlertCatalog } from '@/api/alertTypes';
import { usePreview } from '@/api/queries/usePreview';
import { type Draft, type DraftAction, draftReducer, draftToPreview } from '@/screens/alertEditor/draft';

/**
 * 새 알림 흐름의 초안. 모달이 열려 있는 동안만 산다 — 닫으면 버린다.
 *
 * 앱 전역 상태에 두지 않는다. 흐름 전체가 한 번의 저장으로 끝나는 작업이고(IA §2.2),
 * 다섯 단계가 한 초안을 함께 고친다. 그래서 모달 범위의 Context 하나로 충분하다.
 */

type EditorValue = {
  draft: Draft;
  dispatch: Dispatch<DraftAction>;
  catalog: AlertCatalog;
  /**
   * 흐름을 연 시각. 미리보기 요청의 유효기간(1주·1개월·3개월)을 이 시각으로 계산한다 —
   * 매번 지금 시각을 쓰면 요청 JSON이 렌더마다 달라져 미리보기를 끝없이 다시 부른다.
   */
  openedAt: Date;
  /** 저장을 마친 알림 ID. 정해지면 흐름이 닫힌다. */
  finished: string | null;
  finish: (alertId: string) => void;
};

const EditorContext = createContext<EditorValue | null>(null);

export function EditorProvider({
  initial,
  catalog,
  children,
}: {
  initial: Draft;
  catalog: AlertCatalog;
  children: ReactNode;
}) {
  const [draft, dispatch] = useReducer(draftReducer, initial);
  const [openedAt] = useState(() => new Date());
  const [finished, setFinished] = useState<string | null>(null);

  const value = useMemo<EditorValue>(
    () => ({ draft, dispatch, catalog, openedAt, finished, finish: setFinished }),
    [draft, catalog, openedAt, finished],
  );

  return <EditorContext.Provider value={value}>{children}</EditorContext.Provider>;
}

export function useEditor(): EditorValue {
  const value = useContext(EditorContext);
  if (!value) throw new Error('useEditor는 EditorProvider 안에서만 쓸 수 있다');
  return value;
}

/** 지금 초안의 미리보기. 단계마다 부르지만 요청이 같으면 같은 쿼리라 한 번만 나간다. */
export function useDraftPreview() {
  const { draft, catalog, openedAt } = useEditor();
  return usePreview(draftToPreview(draft, catalog, openedAt));
}
```

- [ ] **Step 4: 두 단계를 쓴다**

`front-end/src/screens/alertEditor/InstrumentStep.tsx`:

```tsx
import { useState } from 'react';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';

import type { InstrumentRow } from '@/api/alertTypes';
import { useInstruments } from '@/api/queries/useInstruments';
import { useTheme } from '@/design/theme';
import { screenPadding, size, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { ErrorState } from '@/envelope/ErrorState';
import { useEditor } from '@/screens/alertEditor/EditorContext';
import type { EditorParamList } from '@/screens/alertEditor/types';
import { useDebounced } from '@/screens/alertEditor/useDebounced';
import { Badge } from '@/ui/Badge';
import { Skeleton } from '@/ui/Skeleton';
import { TextField } from '@/ui/TextField';

/**
 * 대상 종목 — 전 종목 검색 (§12.5.1 · IA §2.4).
 *
 * 검색어가 없으면 보유 종목 구역(가나다순)이다. 보유 종목을 검색 결과 앞으로 당기지 않고
 * 배지만 붙인다 — 화면에 보이지 않는 기준으로 정렬하면 순서가 무작위로 보인다.
 * 순서는 서버가 정한다.
 */
export function InstrumentStep() {
  const { dispatch } = useEditor();
  const navigation = useNavigation<NativeStackNavigationProp<EditorParamList>>();
  const palette = useTheme();
  const [text, setText] = useState('');
  const q = useDebounced(text.trim(), 300);
  const held = q === '';
  const result = useInstruments(q, held);
  const rows = result.data?.rows ?? [];

  const choose = (row: InstrumentRow) => {
    dispatch({
      type: 'instrument',
      instrument: {
        id: row.id,
        label: row.label,
        market: row.market,
        held: row.held,
        lastClose: row.last_close ?? null,
        lastCloseOn: row.last_close_on ?? null,
      },
    });
    navigation.navigate('trigger');
  };

  const body = (() => {
    if (result.isPending) {
      return [0, 1, 2].map((index) => <Skeleton key={index} width="100%" height={48} style={styles.skeleton} />);
    }
    if (result.isError) return <ErrorState error={result.error} onRetry={() => void result.refetch()} />;
    if (rows.length === 0) {
      return (
        <Text style={[type.body, styles.empty, { color: palette.textMuted }]}>
          {held ? '종목명이나 종목코드로 검색하세요' : '검색 결과가 없어요'}
        </Text>
      );
    }
    return (
      <FlatList
        data={rows}
        keyExtractor={(row) => row.id}
        keyboardShouldPersistTaps="handled"
        renderItem={({ item }) => <InstrumentItem row={item} onPress={() => choose(item)} />}
      />
    );
  })();

  return (
    <View style={[styles.screen, { backgroundColor: palette.bg }]}>
      <View style={styles.search}>
        <TextField
          label="종목 검색"
          placeholder="종목명이나 종목코드"
          value={text}
          onChangeText={setText}
          autoCorrect={false}
          autoCapitalize="none"
          returnKeyType="search"
        />
      </View>
      <Text style={[type.caption, styles.section, { color: palette.textMuted }]}>
        {held ? '보유 종목' : '검색 결과'}
      </Text>
      <View style={styles.body}>{body}</View>
    </View>
  );
}

/** `종목명 · 종목코드 · 시장 배지 · 보유 배지`. 미국 종목은 영문명과 티커다. */
function InstrumentItem({ row, onPress }: { row: InstrumentRow; onPress: () => void }) {
  const palette = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={row.label}
      onPress={onPress}
      style={[styles.row, { borderBottomColor: palette.border }]}
    >
      <Text numberOfLines={1} style={[type.body, styles.label, { color: palette.text }]}>
        {row.label}
      </Text>
      <Text style={[type.caption, { color: palette.textMuted }]}>{row.symbol}</Text>
      <Badge label={row.market} />
      {row.held && <Badge label="보유" />}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  search: { paddingHorizontal: screenPadding, paddingTop: space.md },
  section: { paddingHorizontal: screenPadding, paddingBottom: space.xs },
  body: { flex: 1 },
  empty: { paddingHorizontal: screenPadding, paddingTop: space.lg },
  skeleton: { marginHorizontal: screenPadding, marginBottom: space.sm },
  row: {
    minHeight: size.row,
    paddingHorizontal: screenPadding,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    borderBottomWidth: 1,
  },
  label: { flexShrink: 1 },
});
```

`front-end/src/screens/alertEditor/TriggerStep.tsx`:

```tsx
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '@/design/theme';
import { radius, screenPadding, size, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { useEditor } from '@/screens/alertEditor/EditorContext';
import { presetAvailability } from '@/screens/alertEditor/presetFields';
import type { EditorParamList } from '@/screens/alertEditor/types';

/**
 * 조건 선택 (§12.5.2). 맨 위에 직접 만들기, 그 아래 프리셋 카드.
 * 쓸 수 없는 프리셋은 숨기지 않고 비활성 + 사유 한 줄 — 왜 없는지 모르면 찾아 헤맨다.
 * 카드의 칩은 평가 시점이다(`장중·종가` · `종가`).
 */
export function TriggerStep() {
  const { draft, dispatch, catalog } = useEditor();
  const navigation = useNavigation<NativeStackNavigationProp<EditorParamList>>();
  const palette = useTheme();
  const instrument = draft.instrument;
  if (!instrument) return null;

  return (
    <ScrollView style={{ backgroundColor: palette.bg }} contentContainerStyle={styles.content}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="＋ 직접 조건 만들기"
        onPress={() => {
          dispatch({ type: 'composable' });
          navigation.navigate('composable');
        }}
        style={[styles.card, { borderColor: palette.primary, backgroundColor: palette.surface }]}
      >
        <Text style={[type.body, styles.strong, { color: palette.primary }]}>＋ 직접 조건 만들기</Text>
      </Pressable>

      <Text style={[type.caption, styles.section, { color: palette.textMuted }]}>프리셋</Text>
      {catalog.presets.map((preset) => {
        const availability = presetAvailability(preset, instrument);
        return (
          <Pressable
            key={preset.key}
            accessibilityRole="button"
            accessibilityLabel={preset.label}
            accessibilityState={{ disabled: !availability.enabled }}
            disabled={!availability.enabled}
            onPress={() => {
              dispatch({ type: 'preset', preset });
              navigation.navigate('preset');
            }}
            style={[styles.card, { borderColor: palette.border }, !availability.enabled && styles.disabled]}
          >
            <View style={styles.cardText}>
              <Text style={[type.body, { color: palette.text }]}>{preset.label}</Text>
              {!availability.enabled && (
                <Text style={[type.caption, { color: palette.textMuted }]}>{availability.reason}</Text>
              )}
            </View>
            <Text style={[type.micro, styles.chip, { color: palette.textMuted, backgroundColor: palette.surface }]}>
              {preset.cadences.includes('INTRADAY') ? '장중·종가' : '종가'}
            </Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { paddingHorizontal: screenPadding, paddingVertical: space.lg },
  card: {
    minHeight: size.row,
    borderWidth: 1,
    borderRadius: radius.card,
    paddingHorizontal: space.base,
    marginBottom: space.sm,
    flexDirection: 'row',
    alignItems: 'center',
  },
  strong: { fontWeight: '600' },
  section: { marginTop: space.md, marginBottom: space.xs },
  cardText: { flex: 1, paddingVertical: space.sm },
  chip: { borderRadius: 10, paddingHorizontal: space.sm, paddingVertical: 2, overflow: 'hidden' },
  disabled: { opacity: 0.5 },
});
```

- [ ] **Step 5: 모달 내비게이터를 쓴다**

`front-end/src/screens/alertEditor/AlertEditorNavigator.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { usePreventRemove, useNavigation, useRoute } from '@react-navigation/native';
import type { NavigationAction, RouteProp } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { fetchAlert } from '@/api/alertEndpoints';
import { keys } from '@/api/queries/keys';
import { useAlertCatalog } from '@/api/queries/useAlertCatalog';
import type { RootStackParamList } from '@/app/navigation/types';
import { useTheme } from '@/design/theme';
import { ErrorState } from '@/envelope/ErrorState';
import { EditorProvider, useEditor } from '@/screens/alertEditor/EditorContext';
import { InstrumentStep } from '@/screens/alertEditor/InstrumentStep';
import { TriggerStep } from '@/screens/alertEditor/TriggerStep';
import { draftFromDetail, newDraft } from '@/screens/alertEditor/draft';
import type { EditorParamList } from '@/screens/alertEditor/types';
import { ConfirmSheet } from '@/ui/ConfirmSheet';
import { TextButton } from '@/ui/TextButton';

const Stack = createNativeStackNavigator<EditorParamList>();

/**
 * 새 알림 흐름 — 루트 스택 위의 모달 (IA §2.2).
 *
 * 들어온 곳에 따라 첫 단계가 다르다 — `＋ 새 알림`은 종목 선택, 종목이 정해져 있으면 조건 선택,
 * 수정은 프리셋 입력 또는 조건 만들기(값이 채워진 채). 닫으면 들어온 자리로 돌아가고,
 * 저장하면 알림 상세가 열린다.
 */
export function AlertEditorNavigator() {
  const route = useRoute<RouteProp<RootStackParamList, 'alert-editor'>>();
  const start = route.params;
  const editId = start.mode === 'edit' ? start.alertId : null;
  const catalog = useAlertCatalog();
  // 수정은 알림 상세에서 들어오므로 대개 캐시에 이미 있다.
  const detail = useQuery({
    queryKey: keys.alert(editId ?? ''),
    queryFn: () => fetchAlert(editId as string),
    enabled: editId !== null,
  });
  const palette = useTheme();

  if (catalog.isPending || (editId !== null && detail.isPending)) {
    return (
      <View style={[styles.loading, { backgroundColor: palette.bg }]}>
        <ActivityIndicator color={palette.primary} />
      </View>
    );
  }
  if (catalog.isError) return <ErrorState error={catalog.error} onRetry={() => void catalog.refetch()} />;
  if (editId !== null && detail.isError) {
    return <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />;
  }

  const initial =
    editId !== null && detail.data
      ? draftFromDetail(detail.data)
      : newDraft(start.mode === 'new' ? start.instrument : undefined);
  const firstStep: keyof EditorParamList =
    start.mode === 'edit'
      ? initial.triggerType === 'PRESET'
        ? 'preset'
        : 'composable'
      : start.instrument
        ? 'trigger'
        : 'instrument';

  return (
    <EditorProvider initial={initial} catalog={catalog.data}>
      <EditorStack firstStep={firstStep} />
    </EditorProvider>
  );
}

function EditorStack({ firstStep }: { firstStep: keyof EditorParamList }) {
  const { draft, finished } = useEditor();
  const rootNavigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const palette = useTheme();
  const [leaving, setLeaving] = useState<NavigationAction | null>(null);

  // 작성 중에 닫으면 먼저 묻는다(§12.5). 저장을 마친 뒤의 이동은 막지 않는다.
  usePreventRemove(draft.dirty && finished === null, ({ data }) => setLeaving(data.action));

  // 새 알림은 모달을 그 알림의 상세로 바꾸고, 수정은 모달을 닫아 들어온 상세로 돌아간다.
  useEffect(() => {
    if (finished === null) return;
    if (draft.mode === 'edit') rootNavigation.goBack();
    else rootNavigation.replace('alert', { alertId: finished });
  }, [finished, draft.mode, rootNavigation]);

  return (
    <>
      <Stack.Navigator
        initialRouteName={firstStep}
        screenOptions={({ route }) => ({
          headerTintColor: palette.text,
          headerStyle: { backgroundColor: palette.bg },
          contentStyle: { backgroundColor: palette.bg },
          headerLeft:
            route.name === firstStep
              ? () => <TextButton label="닫기" onPress={() => rootNavigation.goBack()} />
              : undefined,
        })}
      >
        <Stack.Screen name="instrument" component={InstrumentStep} options={{ title: '대상 종목' }} />
        <Stack.Screen name="trigger" component={TriggerStep} options={{ title: '조건 선택' }} />
      </Stack.Navigator>

      <ConfirmSheet
        visible={leaving !== null}
        title="작성 중인 알림을 버릴까요?"
        confirmLabel="버리기"
        cancelLabel="계속 쓰기"
        onCancel={() => setLeaving(null)}
        onConfirm={() => {
          const action = leaving;
          setLeaving(null);
          if (action) rootNavigation.dispatch(action);
        }}
      />
    </>
  );
}

const styles = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
```

- [ ] **Step 6: 루트 스택에 모달로 등록한다**

`RootStack.tsx`:

```tsx
import { AlertEditorNavigator } from '@/screens/alertEditor/AlertEditorNavigator';
```

```tsx
      <Stack.Screen
        name="alert-editor"
        component={AlertEditorNavigator}
        options={{ presentation: 'modal', headerShown: false }}
      />
```

- [ ] **Step 7: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest src/__tests__/alertEditorFlow.test.tsx && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 8: 커밋한다**

```bash
git add src/screens/alertEditor src/app/navigation/RootStack.tsx src/testing/openEditor.tsx src/__tests__/alertEditorFlow.test.tsx
git commit -m "feat: 새 알림 흐름을 모달로 열고 종목·조건을 고른다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: 프리셋 입력 — 칸 · 직전 종가 · 문장 상자 · 현재값 상자

**Files:**
- Modify: `front-end/src/ui/TextField.tsx` (`suffix`)
- Modify: `front-end/src/format/alertTime.ts` (`dayLabel`)
- Create: `front-end/src/screens/alertEditor/NumberField.tsx`
- Create: `front-end/src/screens/alertEditor/StepFooter.tsx`
- Create: `front-end/src/screens/alertEditor/PresetStep.tsx`
- Modify: `front-end/src/screens/alertEditor/AlertEditorNavigator.tsx` (`preset` 등록)
- Test: `front-end/src/__tests__/alertPresetForm.test.tsx`

**Interfaces:**
- Consumes: `useEditor` · `useDraftPreview` · `openEditor` (Task 9), `fieldSpec` · `periodChips` · `errorAt` · `errorsOutside` (Task 8), `SentenceBox` · `CurrentBox` (Task 6)
- Produces:
  - `TextField`의 `suffix?: string` (입력칸 오른쪽 단위)
  - `dayLabel(date: string): string` — `2026-09-25` → `9/25`
  - `<NumberField label value onChange unit? note? error? accessibilityLabel? />`
  - `<StepFooter label disabled onPress />` — 화면 아래 고정 버튼(`다음` · `저장`)
  - `<PreviewFailure error onRetry />` — 미리보기를 받지 못했을 때의 문구와 `다시 시도`
  - `canProceed(preview, pending): boolean` (`StepFooter.tsx`에서 export) — 조건 칸(`trigger_spec…` · `cadence`)에 오류가 없고 응답을 기다리지 않을 때만 다음으로 간다
  - `<PresetStep />`

`다음`은 헤더 오른쪽이 아니라 화면 아래 고정 버튼으로 둔다. 공통 설정의 `저장`과 같은 자리라 손가락이 같은 곳을 누르고, 테스트 렌더러가 네이티브 헤더를 그리는지에 기대지 않는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`front-end/src/__tests__/alertPresetForm.test.tsx`:

```tsx
import { fireEvent, screen, waitFor } from '@testing-library/react-native';

import type { PreviewRequest } from '@/api/alertTypes';
import { setAccessToken } from '@/api/client';
import type { EditorInstrument } from '@/app/navigation/types';
import { presetDetailFixture, previewFixture, previewInvalidFixture } from '@/fixtures/alerts';
import { dayLabel } from '@/format/alertTime';
import { openEditor } from '@/testing/openEditor';
import type { Route } from '@/testing/serveRoutes';

const SAMSUNG: EditorInstrument = {
  id: '10000000-0000-0000-0000-000000000001',
  label: '삼성전자',
  market: 'KR',
  held: true,
  lastClose: 63010,
  lastCloseOn: '2026-09-25',
};

const preview = (body: unknown = previewFixture): Route => ({ method: 'POST', path: '/alerts/preview', body });

function lastPreview(calls: Awaited<ReturnType<typeof openEditor>>['calls']): PreviewRequest {
  return calls.filter((c) => c.path === '/alerts/preview').at(-1)!.body as PreviewRequest;
}

beforeEach(() => setAccessToken('tok'));
afterEach(() => setAccessToken(null));

async function choosePreset(label: string, routes: Route[] = [preview()]) {
  const opened = await openEditor({ mode: 'new', instrument: SAMSUNG }, routes);
  await waitFor(() => expect(screen.getByText(label)).toBeTruthy());
  await fireEvent.press(screen.getByRole('button', { name: label }));
  return opened;
}

it('dayLabel', () => {
  expect(dayLabel('2026-09-25')).toBe('9/25');
});

describe('프리셋 입력', () => {
  it('가격 도달 — 직전 종가로 채우고, 0.5초 뒤 문장과 현재값을 그린다', async () => {
    const { calls } = await choosePreset('가격 도달');
    await waitFor(() => expect(screen.getByLabelText('가격').props.value).toBe('63010'));

    await waitFor(() => expect(screen.getByText('장중에 현재가가 63,010원 이상이면 알려요')).toBeTruthy());
    // 칸 아래의 기준일과 현재값 상자의 머리가 같은 글이다.
    expect(screen.getAllByText('9/25 종가 기준')).toHaveLength(2);
    expect(screen.getByText('→ 충족하고 있어요')).toBeTruthy();

    const body = lastPreview(calls);
    expect(body.cadence).toBe('INTRADAY');
    expect(body.name).toBe('삼성전자 가격 도달');
    expect(body.trigger_spec).toEqual({ preset_key: 'price_reach', params: { direction: 'up', price: 63010 } });
    expect(screen.getByRole('button', { name: '다음' }).props.accessibilityState.disabled).toBe(false);
  });

  it('칸을 고치면 멈춘 뒤의 값으로 다시 부른다', async () => {
    const { calls } = await choosePreset('가격 도달');
    await waitFor(() => expect(screen.getByLabelText('가격')).toBeTruthy());

    await fireEvent.changeText(screen.getByLabelText('가격'), '7');
    await fireEvent.changeText(screen.getByLabelText('가격'), '70000');

    await waitFor(() => {
      const body = lastPreview(calls);
      expect((body.trigger_spec as { params: { price: number } }).params.price).toBe(70000);
    });
    expect(
      calls.filter((c) => c.path === '/alerts/preview').some(
        (c) => (c.body as PreviewRequest & { trigger_spec: { params: { price: number } } }).trigger_spec.params.price === 7,
      ),
    ).toBe(false);
  });

  it('서버가 돌려준 칸 오류를 그 칸 아래에 두고 다음을 막는다', async () => {
    await choosePreset('가격 도달', [preview(previewInvalidFixture)]);
    await waitFor(() => expect(screen.getByText('가격을 입력해 주세요')).toBeTruthy());
    expect(screen.getByRole('button', { name: '다음' }).props.accessibilityState.disabled).toBe(true);
  });

  it('미리보기를 받지 못하면 이유와 다시 시도를 보인다', async () => {
    const { calls } = await choosePreset('가격 도달', [
      { method: 'POST', path: '/alerts/preview', status: 500, body: { error: { code: 'INTERNAL', message: '잠시 후 다시 시도해 주세요' } } },
    ]);
    await waitFor(() => expect(screen.getByText('잠시 후 다시 시도해 주세요')).toBeTruthy());
    expect(screen.getByRole('button', { name: '다음' }).props.accessibilityState.disabled).toBe(true);
    const before = calls.filter((c) => c.path === '/alerts/preview').length;

    await fireEvent.press(screen.getByRole('button', { name: '다시 시도' }));

    await waitFor(() => expect(calls.filter((c) => c.path === '/alerts/preview').length).toBe(before + 1));
  });

  it('종가로 바꾸면 하루 한 번이라고 알린다', async () => {
    const { calls } = await choosePreset('가격 도달');
    await waitFor(() => expect(screen.getByRole('tab', { name: '종가' })).toBeTruthy());

    await fireEvent.press(screen.getByRole('tab', { name: '종가' }));

    expect(screen.getByText('장 마감 뒤 하루 한 번 확인해요')).toBeTruthy();
    await waitFor(() => expect(lastPreview(calls).cadence).toBe('CLOSE'));
  });

  it('종가 전용 프리셋 — RSI 과매도를 고르면 기준이 30', async () => {
    await choosePreset('RSI 과매수·과매도');
    await waitFor(() => expect(screen.getByText('이 프리셋은 종가로만 평가해요')).toBeTruthy());
    expect(screen.getByLabelText('기준').props.value).toBe('70');

    await fireEvent.press(screen.getByRole('button', { name: '과매도' }));

    expect(screen.getByLabelText('기준').props.value).toBe('30');
  });

  it('기간 칸은 값 칩과 직접 입력', async () => {
    await choosePreset('박스권 돌파');
    await waitFor(() => expect(screen.getByRole('button', { name: '60일' })).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '60일' }));

    expect(screen.getByLabelText('관찰 기간').props.value).toBe('60');
  });

  it('수정으로 열면 저장된 값으로 채우고 alert_id를 싣는다', async () => {
    const { calls } = await openEditor({ mode: 'edit', alertId: 'a-satisfied' }, [
      { path: '/alerts/a-satisfied', body: presetDetailFixture },
      preview(),
    ]);
    await waitFor(() => expect(screen.getByLabelText('가격').props.value).toBe('70000'));
    await waitFor(() => expect(lastPreview(calls).alert_id).toBe('a-satisfied'));
  });
});
```

- [ ] **Step 2: 테스트가 실패하는지 본다**

Run: `npx jest src/__tests__/alertPresetForm.test.tsx`
Expected: FAIL — `dayLabel is not a function` 또는 `가격 도달`을 눌러도 갈 화면(`preset`)이 없어 `가격` 칸을 찾지 못함.

- [ ] **Step 3: 칸 부품을 쓴다**

`format/alertTime.ts` 끝에 더한다.

```ts
/** `2026-09-25` → `9/25`. 가격 칸 아래의 `9/25 종가 기준`에 쓴다. */
export function dayLabel(date: string): string {
  const m = /^\d{4}-(\d{2})-(\d{2})/.exec(date);
  return m ? `${Number(m[1])}/${Number(m[2])}` : EM_DASH;
}
```

`ui/TextField.tsx` — props 타입에 `suffix?: string`을 더하고(`/** 입력칸 오른쪽에 붙는 단위. `원` · `%` · `일`. */`), 구조 분해에 `suffix`를 넣고, `<TextInput … />` 바로 뒤(비밀번호 버튼 앞)에 넣는다.

```tsx
        {suffix ? (
          <Text style={[type.body, styles.suffix, { color: palette.textMuted }]}>{suffix}</Text>
        ) : null}
```

```ts
  suffix: { marginLeft: space.sm },
```

`front-end/src/screens/alertEditor/NumberField.tsx`:

```tsx
import { Platform, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '@/design/theme';
import { type } from '@/design/typography';
import { TextField } from '@/ui/TextField';

/**
 * 단위가 붙은 숫자 칸. 아래에 기준일이나 읽기용 환산을 한 줄 둘 수 있다.
 * iOS 숫자 패드에는 빼기가 없어 숫자·구두점 자판을 쓴다 — 등락률 기준값은 음수일 수 있다.
 */
export function NumberField({
  label,
  value,
  onChange,
  unit,
  note,
  error,
  accessibilityLabel,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  unit?: string;
  /** 칸 아래 한 줄. `9/25 종가 기준` · `= 1,000억원`. */
  note?: string;
  error?: string;
  /** 같은 라벨의 칸이 여럿인 화면(조건 만들기)에서 칸을 가른다. */
  accessibilityLabel?: string;
}) {
  const palette = useTheme();
  return (
    <View>
      <TextField
        label={label}
        accessibilityLabel={accessibilityLabel ?? label}
        value={value}
        onChangeText={onChange}
        suffix={unit}
        error={error}
        keyboardType={Platform.OS === 'ios' ? 'numbers-and-punctuation' : 'numeric'}
        autoCorrect={false}
      />
      {note ? <Text style={[type.caption, styles.note, { color: palette.textMuted }]}>{note}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  note: { marginBottom: 8 },
});
```

`TextField`는 `accessibilityLabel={label}`을 먼저 두고 `{...inputProps}`를 뒤에 펼치므로, 넘긴 `accessibilityLabel`이 이긴다.

`front-end/src/screens/alertEditor/StepFooter.tsx`:

```tsx
import { StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import type { PreviewResponse } from '@/api/alertTypes';
import { useTheme } from '@/design/theme';
import { radius, screenPadding, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { messageOf } from '@/envelope/ErrorState';
import { Button } from '@/ui/Button';
import { TextButton } from '@/ui/TextButton';

/** 단계 아래에 고정된 주 버튼. `다음`과 `저장`이 같은 자리에 있다. */
export function StepFooter({
  label,
  disabled = false,
  loading = false,
  onPress,
}: {
  label: string;
  disabled?: boolean;
  loading?: boolean;
  onPress: () => void;
}) {
  const palette = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View
      style={[
        styles.footer,
        { borderTopColor: palette.border, backgroundColor: palette.bg, paddingBottom: space.md + insets.bottom },
      ]}
    >
      <Button label={label} disabled={disabled} loading={loading} onPress={onPress} />
    </View>
  );
}

/**
 * 조건 단계에서 다음으로 가도 되는가. 미리보기가 조건 칸(`trigger_spec…` · `cadence`)에
 * 오류를 달지 않았고, 지금 입력의 응답을 기다리는 중이 아닐 때다.
 * 공통 설정 칸의 오류(이름 등)는 다음 단계에서 고친다.
 */
export function canProceed(preview: PreviewResponse | null, pending: boolean): boolean {
  if (pending || !preview) return false;
  return !preview.errors.some((e) => e.path === 'cadence' || e.path.startsWith('trigger_spec'));
}

/**
 * 미리보기를 받지 못했을 때(서버 오류 · 닿지 못함). 문장 상자가 비고 `다음`이 잠긴 이유를 보이고
 * 다시 부를 길을 준다. 형 오류는 여기가 아니다 — 그것은 200 응답의 `errors`로 칸 아래에 붙는다.
 */
export function PreviewFailure({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const palette = useTheme();
  if (!error) return null;
  return (
    <View style={[styles.failure, { backgroundColor: palette.errorBg }]}>
      <Text style={[type.caption, styles.failureText, { color: palette.errorText }]}>{messageOf(error)}</Text>
      <TextButton label="다시 시도" onPress={onRetry} />
    </View>
  );
}

const styles = StyleSheet.create({
  footer: { paddingHorizontal: screenPadding, paddingTop: space.md, borderTopWidth: 1 },
  failure: {
    marginTop: space.md,
    borderRadius: radius.button,
    padding: space.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
  },
  failureText: { flex: 1 },
});
```

- [ ] **Step 4: 프리셋 입력 화면을 쓴다**

`front-end/src/screens/alertEditor/PresetStep.tsx`:

```tsx
import { useLayoutEffect } from 'react';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import type { Cadence, CatalogPreset, Market, PresetParam } from '@/api/alertTypes';
import { useTheme } from '@/design/theme';
import { screenPadding, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { dayLabel } from '@/format/alertTime';
import { CurrentBox, SentenceBox } from '@/screens/alerts/PreviewBoxes';
import { useDraftPreview, useEditor } from '@/screens/alertEditor/EditorContext';
import { errorAt, errorsOutside } from '@/screens/alertEditor/fieldErrors';
import { NumberField } from '@/screens/alertEditor/NumberField';
import { fieldSpec, periodChips } from '@/screens/alertEditor/presetFields';
import { PreviewFailure, StepFooter, canProceed } from '@/screens/alertEditor/StepFooter';
import type { EditorParamList } from '@/screens/alertEditor/types';
import { Chip } from '@/ui/Chip';
import { SegmentedControl } from '@/ui/SegmentedControl';

const CADENCES = [
  { value: 'INTRADAY', label: '장중' },
  { value: 'CLOSE', label: '종가' },
];

/** 이 화면이 칸 아래에 그리는 오류의 경로. 나머지는 화면 아래에 모은다. */
const PLACED = ['trigger_spec.params', 'cadence', 'name', 'notify_mode', 'cooldown_min', 'expires_at'];

/**
 * 프리셋 입력 (§12.5.3). 칸은 카탈로그의 `param_schema` 순서대로 그린다.
 * 폼 아래에 문장 상자와 현재값 상자를 두고, 입력이 0.5초 멈추면 다시 받는다(§12.8).
 */
export function PresetStep() {
  const { draft, dispatch, catalog } = useEditor();
  const navigation = useNavigation<NativeStackNavigationProp<EditorParamList>>();
  const palette = useTheme();
  const { preview, pending, error, refetch } = useDraftPreview();
  const preset = catalog.presets.find((p) => p.key === draft.presetKey);

  useLayoutEffect(() => {
    navigation.setOptions({ title: preset?.label ?? '프리셋' });
  }, [navigation, preset]);

  if (!preset || !draft.instrument) return null;
  const errors = preview?.errors ?? [];
  const both = preset.cadences.length > 1;
  const instrument = draft.instrument;

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        {both ? (
          <SegmentedControl
            accessibilityLabel="평가 시점"
            segments={CADENCES}
            value={draft.cadence}
            onChange={(cadence) => dispatch({ type: 'cadence', cadence: cadence as Cadence, catalog })}
          />
        ) : (
          <Text style={[type.caption, { color: palette.textMuted }]}>이 프리셋은 종가로만 평가해요</Text>
        )}
        {both && draft.cadence === 'CLOSE' && (
          <Text style={[type.caption, styles.hint, { color: palette.textMuted }]}>장 마감 뒤 하루 한 번 확인해요</Text>
        )}
        {errorAt(errors, 'cadence') && (
          <Text style={[type.caption, { color: palette.errorText }]}>{errorAt(errors, 'cadence')}</Text>
        )}

        <View style={styles.fields}>
          {preset.param_schema.map((param) => (
            <PresetParamField
              key={param.key}
              preset={preset}
              param={param}
              market={instrument.market}
              value={draft.params[param.key] ?? ''}
              error={errorAt(errors, `trigger_spec.params.${param.key}`)}
              note={
                preset.key === 'price_reach' && param.key === 'price' && instrument.lastCloseOn
                  ? `${dayLabel(instrument.lastCloseOn)} 종가 기준`
                  : undefined
              }
              onChange={(value) => dispatch({ type: 'param', key: param.key, value })}
            />
          ))}
        </View>

        {errorsOutside(errors, PLACED).map((e) => (
          <Text key={e.path} style={[type.caption, styles.loose, { color: palette.errorText }]}>
            {e.message}
          </Text>
        ))}

        <PreviewFailure error={error} onRetry={refetch} />
        <SentenceBox sentence={preview?.summary?.sentence} pending={pending} />
        <CurrentBox current={preview?.current} pending={pending} />
      </ScrollView>
      <StepFooter label="다음" disabled={!canProceed(preview, pending)} onPress={() => navigation.navigate('settings')} />
    </View>
  );
}

function PresetParamField({
  preset,
  param,
  market,
  value,
  error,
  note,
  onChange,
}: {
  preset: CatalogPreset;
  param: PresetParam;
  market: Market;
  value: string;
  error?: string;
  note?: string;
  onChange: (value: string) => void;
}) {
  const palette = useTheme();
  const spec = fieldSpec(preset.key, param.key);

  // 두 갈래 선택은 칩 두 개다.
  if (param.kind === 'choice') {
    return (
      <View style={styles.field}>
        <Text style={[type.label, { color: palette.text }]}>{spec.label}</Text>
        <View style={styles.chips}>
          {param.choices.map((choice) => (
            <Chip
              key={choice}
              label={spec.choices?.[choice] ?? choice}
              selected={value === choice}
              onPress={() => onChange(choice)}
            />
          ))}
        </View>
        {error && <Text style={[type.caption, { color: palette.errorText }]}>{error}</Text>}
      </View>
    );
  }

  // 기간은 값 칩 + 직접 입력, 숫자는 단위가 붙은 입력칸이다.
  const chips = spec.period ? periodChips(param) : [];
  return (
    <View style={styles.field}>
      {chips.length > 0 && (
        <View style={[styles.chips, styles.periodChips]}>
          {chips.map((n) => (
            <Chip key={n} label={`${n}일`} selected={value === String(n)} onPress={() => onChange(String(n))} />
          ))}
        </View>
      )}
      <NumberField
        label={spec.label}
        value={value}
        unit={spec.unit?.(market)}
        note={note}
        error={error}
        onChange={onChange}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: { paddingHorizontal: screenPadding, paddingVertical: space.lg },
  hint: { marginTop: space.xs },
  fields: { marginTop: space.lg },
  field: { marginBottom: space.md },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, marginTop: space.sm },
  periodChips: { marginBottom: space.sm },
  loose: { marginTop: space.xs },
});
```

- [ ] **Step 5: 흐름에 등록한다**

`AlertEditorNavigator.tsx`에 import를 더하고 `trigger` 아래에 한 줄을 넣는다. 제목은 화면이 프리셋 라벨로 바꾼다.

```tsx
import { PresetStep } from '@/screens/alertEditor/PresetStep';
```

```tsx
        <Stack.Screen name="preset" component={PresetStep} options={{ title: '프리셋' }} />
```

- [ ] **Step 6: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest src/__tests__/alertPresetForm.test.tsx && npx jest && npx tsc --noEmit`
Expected: PASS(기존 로그인 화면 테스트 포함 — `TextField`에 칸이 하나 늘었을 뿐 기존 동작은 같다).

- [ ] **Step 7: 커밋한다**

```bash
git add src/ui/TextField.tsx src/format/alertTime.ts src/screens/alertEditor src/__tests__/alertPresetForm.test.tsx
git commit -m "feat: 프리셋 입력에서 칸을 채우고 문장과 현재값을 미리 본다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: 조건 만들기 — 지표 시트 · 변형 · 연산자 · 기준값 · 유지 · 평가 시점 전환

**Files:**
- Create: `front-end/src/screens/alertEditor/IndicatorSheet.tsx`
- Create: `front-end/src/screens/alertEditor/OperandEditor.tsx`
- Create: `front-end/src/screens/alertEditor/ConditionBox.tsx`
- Create: `front-end/src/screens/alertEditor/ComposableStep.tsx`
- Modify: `front-end/src/screens/alertEditor/AlertEditorNavigator.tsx` (`composable` 등록)
- Test: `front-end/src/__tests__/alertComposable.test.tsx`

**Interfaces:**
- Consumes: `composable.ts` 전부 · `operandFor` · `emptyOperand` · `toNumber` · `cadenceChangeClears` · `MAX_CONDITIONS` (Task 8), `useEditor` · `useDraftPreview` (Task 9), `NumberField` · `StepFooter` · `canProceed` (Task 10), `SentenceBox` · `CurrentBox` (Task 6), `ConfirmSheet` · `TextButton` · `formatKrwReading` (Task 4)
- Produces: `<ComposableStep />`. 칸의 접근성 라벨은 `조건 {i} 지표` · `조건 {i} 기간` · `조건 {i} N` · `조건 {i} 기준값` · `조건 {i} 비교 지표` · `조건 {i} 유지` · `조건 {i} 지우기`다(i는 1부터).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`front-end/src/__tests__/alertComposable.test.tsx`:

```tsx
import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import type { ComposableSpec, PreviewRequest } from '@/api/alertTypes';
import { setAccessToken } from '@/api/client';
import type { EditorInstrument } from '@/app/navigation/types';
import { composableDetailFixture, previewFixture } from '@/fixtures/alerts';
import { openEditor } from '@/testing/openEditor';
import type { Route } from '@/testing/serveRoutes';

const SAMSUNG: EditorInstrument = {
  id: '10000000-0000-0000-0000-000000000001', label: '삼성전자', market: 'KR', held: true, lastClose: 63010, lastCloseOn: '2026-09-25',
};
const APPLE: EditorInstrument = { ...SAMSUNG, id: 'i-apple', label: '애플', market: 'US' };

const SENTENCE = '종가 기준으로 RSI(14)가 3일 연속 70 이상이면 알려요';
const preview = (body: unknown = { ...previewFixture, summary: { short: '', sentence: SENTENCE } }): Route => ({
  method: 'POST',
  path: '/alerts/preview',
  body,
});

function conditionsSent(calls: Awaited<ReturnType<typeof openEditor>>['calls']) {
  const body = calls.filter((c) => c.path === '/alerts/preview').at(-1)?.body as PreviewRequest | undefined;
  return (body?.trigger_spec as ComposableSpec | undefined)?.conditions;
}

beforeEach(() => setAccessToken('tok'));
afterEach(() => setAccessToken(null));

async function openComposable(instrument: EditorInstrument = SAMSUNG, routes: Route[] = [preview()]) {
  const opened = await openEditor({ mode: 'new', instrument }, routes);
  await waitFor(() => expect(screen.getByText('＋ 직접 조건 만들기')).toBeTruthy());
  await fireEvent.press(screen.getByRole('button', { name: '＋ 직접 조건 만들기' }));
  await waitFor(() => expect(screen.getByText('평가 시점 · 이 알림 전체')).toBeTruthy());
  return opened;
}

async function pickIndicator(slot: string, label: string) {
  await fireEvent.press(screen.getByRole('button', { name: slot }));
  await fireEvent.press(screen.getByRole('button', { name: label }));
}

describe('조건 만들기', () => {
  it('RSI(14) ≥ 70, 3일 연속 — 스펙 §13.1 모양으로 미리본다', async () => {
    const { calls } = await openComposable();

    await pickIndicator('조건 1 지표', 'RSI');
    await fireEvent.changeText(screen.getByLabelText('조건 1 기준값'), '70');
    await fireEvent.changeText(screen.getByLabelText('조건 1 유지'), '3');

    await waitFor(() => expect(screen.getByText(SENTENCE)).toBeTruthy());
    await waitFor(() =>
      expect(conditionsSent(calls)).toEqual([
        {
          left: { indicator: 'rsi', indicator_params: { n: 14 }, transform: { type: 'identity' } },
          op: 'gte',
          right: { const: 70 },
          modifier: { streak: 3 },
        },
      ]),
    );
  });

  it('장중으로 바꾸면 맞지 않는 칸을 비울지 먼저 묻는다', async () => {
    await openComposable();
    await pickIndicator('조건 1 지표', 'RSI');

    await fireEvent.press(screen.getByRole('tab', { name: '장중' }));
    expect(screen.getByText('장중으로 바꾸면 맞지 않는 조건이 초기화돼요')).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: '바꾸기' }));

    expect(within(screen.getByRole('button', { name: '조건 1 지표' })).getByText('지표 고르기')).toBeTruthy();
    expect(screen.queryByLabelText('조건 1 유지')).toBeTruthy();
    expect(screen.getByText('분 이상 유지')).toBeTruthy();
  });

  it('장중 알림의 왼쪽에는 종가 지표를 고를 수 없다', async () => {
    await openComposable();
    await fireEvent.press(screen.getByRole('tab', { name: '장중' }));

    await fireEvent.press(screen.getByRole('button', { name: '조건 1 지표' }));

    expect(screen.getByRole('button', { name: 'RSI' }).props.accessibilityState.disabled).toBe(true);
    expect(screen.getAllByText('종가에만 계산돼요').length).toBeGreaterThan(0);
  });

  it('미국 종목에서 수급 지표는 국내 종목만', async () => {
    await openComposable(APPLE);
    await fireEvent.press(screen.getByRole('button', { name: '조건 1 지표' }));
    expect(screen.getAllByText('국내 종목만')).toHaveLength(2);
  });

  it('수급 금액은 원으로 입력하고 아래에 읽기용 환산을 보인다', async () => {
    await openComposable();
    await pickIndicator('조건 1 지표', '외국인 순매수');

    await fireEvent.changeText(screen.getByLabelText('조건 1 기준값'), '100000000000');

    expect(screen.getByText('= 1,000억원')).toBeTruthy();
  });

  it('교차를 고르면 기준값이 지표가 되고 유지 칸이 사라진다', async () => {
    await openComposable();
    await pickIndicator('조건 1 지표', '이동평균');

    await fireEvent.press(screen.getByRole('button', { name: '연산자 상향 돌파하면' }));

    expect(screen.getByRole('button', { name: '조건 1 비교 지표' })).toBeTruthy();
    expect(screen.queryByLabelText('조건 1 유지')).toBeNull();
  });

  it('조건은 다섯 개까지, 둘 이상이면 지울 수 있다', async () => {
    await openComposable();
    expect(screen.queryByRole('button', { name: '조건 1 지우기' })).toBeNull();

    for (let i = 0; i < 4; i++) await fireEvent.press(screen.getByRole('button', { name: '＋ 조건 추가 (AND)' }));

    expect(screen.getByText('조건 5')).toBeTruthy();
    expect(screen.queryByRole('button', { name: '＋ 조건 추가 (AND)' })).toBeNull();
    await fireEvent.press(screen.getByRole('button', { name: '조건 5 지우기' }));
    expect(screen.getByRole('button', { name: '＋ 조건 추가 (AND)' })).toBeTruthy();
  });

  it('미리보기의 칸 오류를 그 칸 아래에', async () => {
    await openComposable(SAMSUNG, [
      preview({
        ...previewFixture,
        valid: false,
        errors: [{ path: 'trigger_spec.conditions[0].right.const', code: 'REQUIRED', message: '기준값을 입력해 주세요' }],
      }),
    ]);
    await waitFor(() => expect(screen.getByText('기준값을 입력해 주세요')).toBeTruthy());
    expect(screen.getByRole('button', { name: '다음' }).props.accessibilityState.disabled).toBe(true);
  });

  it('수정으로 열면 저장된 조건으로 채운다', async () => {
    await openEditor({ mode: 'edit', alertId: 'a-composable' }, [
      { path: '/alerts/a-composable', body: composableDetailFixture },
      preview(),
    ]);
    await waitFor(() => expect(screen.getByText('조건 2')).toBeTruthy());

    expect(screen.getByRole('tab', { name: '장중' }).props.accessibilityState.selected).toBe(true);
    expect(screen.getByLabelText('조건 1 유지').props.value).toBe('10');
    expect(within(screen.getByRole('button', { name: '조건 1 비교 지표' })).getByText('고가')).toBeTruthy();
    expect(screen.getByLabelText('조건 1 N').props.value).toBe('20');
    expect(screen.getByLabelText('조건 2 기준값').props.value).toBe('2');
  });
});
```

- [ ] **Step 2: 테스트가 실패하는지 본다**

Run: `npx jest src/__tests__/alertComposable.test.tsx`
Expected: FAIL — `평가 시점 · 이 알림 전체`를 찾지 못함(`composable` 단계가 없다).

- [ ] **Step 3: 지표 시트를 쓴다**

`front-end/src/screens/alertEditor/IndicatorSheet.tsx`:

```tsx
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import type { AlertCatalog, CatalogIndicator } from '@/api/alertTypes';
import { useTheme } from '@/design/theme';
import { size, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { CATEGORY_ORDER, type IndicatorContext, indicatorAvailability } from '@/screens/alertEditor/composable';
import { BottomSheet } from '@/ui/BottomSheet';

/**
 * 지표 고르기 (§12.5.4). 묶음은 `시세 · 기술지표 · 수급 · 내 보유`.
 * 쓸 수 없는 지표는 비활성 + 사유 한 줄. 장중 알림의 오른쪽을 고를 때는 머리에
 * `어제까지 확정된 값`을 둔다 — 오른쪽 지표는 직전 거래일까지의 일봉으로 계산된다(§3.1).
 */
export function IndicatorSheet({
  visible,
  catalog,
  context,
  onClose,
  onPick,
}: {
  visible: boolean;
  catalog: AlertCatalog;
  context: IndicatorContext;
  onClose: () => void;
  onPick: (indicator: CatalogIndicator) => void;
}) {
  const palette = useTheme();
  const live = catalog.indicators.filter((i) => !i.deprecated);
  const categories = [
    ...CATEGORY_ORDER,
    ...live.map((i) => i.category).filter((c, idx, all) => !CATEGORY_ORDER.includes(c) && all.indexOf(c) === idx),
  ];
  const title = context.side === 'right' && context.cadence === 'INTRADAY' ? '어제까지 확정된 값' : '지표';

  return (
    <BottomSheet visible={visible} title={title} onClose={onClose}>
      <ScrollView style={styles.list}>
        {categories.map((category) => {
          const items = live.filter((i) => i.category === category);
          if (items.length === 0) return null;
          return (
            <View key={category} style={styles.group}>
              <Text style={[type.caption, { color: palette.textMuted }]}>{category}</Text>
              {items.map((indicator) => {
                const availability = indicatorAvailability(indicator, context);
                return (
                  <Pressable
                    key={indicator.key}
                    accessibilityRole="button"
                    accessibilityLabel={indicator.label}
                    accessibilityState={{ disabled: !availability.enabled }}
                    disabled={!availability.enabled}
                    onPress={() => onPick(indicator)}
                    style={[styles.item, { borderBottomColor: palette.border }, !availability.enabled && styles.disabled]}
                  >
                    <Text style={[type.body, { color: palette.text }]}>{indicator.label}</Text>
                    {!availability.enabled && (
                      <Text style={[type.caption, { color: palette.textMuted }]}>{availability.reason}</Text>
                    )}
                  </Pressable>
                );
              })}
            </View>
          );
        })}
      </ScrollView>
    </BottomSheet>
  );
}

const styles = StyleSheet.create({
  list: { maxHeight: 440 },
  group: { marginBottom: space.md },
  item: { minHeight: size.tap, justifyContent: 'center', borderBottomWidth: 1, paddingVertical: space.xs },
  disabled: { opacity: 0.5 },
});
```

- [ ] **Step 4: 피연산자 편집 부품을 쓴다**

`front-end/src/screens/alertEditor/OperandEditor.tsx`:

```tsx
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { AlertCatalog, Cadence, CatalogIndicator } from '@/api/alertTypes';
import { useTheme } from '@/design/theme';
import { radius, size, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { sameTransform, transformChoices } from '@/screens/alertEditor/composable';
import type { OperandDraft, TransformDraft } from '@/screens/alertEditor/draft';
import { NumberField } from '@/screens/alertEditor/NumberField';
import { Chip } from '@/ui/Chip';

/**
 * 피연산자 하나 — 지표 · 지표 파라미터 · 변형 (§4.2 Operand).
 * 지표는 시트에서 고르고(`onPick`), 파라미터와 변형은 이 자리에서 고친다.
 */
export function OperandEditor({
  slot,
  label,
  operand,
  indicator,
  cadence,
  side,
  catalog,
  error,
  onPick,
  onChange,
}: {
  /** 접근성 라벨의 앞부분 — `조건 1`. */
  slot: string;
  label: string;
  operand: OperandDraft;
  indicator: CatalogIndicator | null;
  cadence: Cadence;
  side: 'left' | 'right';
  catalog: AlertCatalog;
  error?: string;
  onPick: () => void;
  onChange: (next: OperandDraft) => void;
}) {
  const palette = useTheme();
  const choices = indicator ? transformChoices(indicator, cadence, side, catalog) : [];
  const transform = operand.transform;
  const range = indicator && transform.type !== 'identity' ? indicator.transform_ranges[transform.type] : undefined;

  const setTransform = (next: TransformDraft) => {
    // N은 앞 변형의 값을 이어 쓴다. 최고 → 평균처럼 함수만 바꿀 때 다시 치지 않게 한다.
    const n = transform.type === 'identity' ? null : transform.n;
    onChange({ ...operand, transform: next.type === 'identity' || n === null ? next : { ...next, n } });
  };

  return (
    <View style={styles.operand}>
      <Text style={[type.label, { color: palette.text }]}>{label}</Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${slot} ${label}`}
        onPress={onPick}
        style={[styles.picker, { borderColor: error ? palette.errorText : palette.border, backgroundColor: palette.surface }]}
      >
        <Text style={[type.body, { color: indicator ? palette.text : palette.textMuted }]}>
          {indicator ? indicator.label : '지표 고르기'}
        </Text>
        <Text style={[type.body, { color: palette.textMuted }]}>▾</Text>
      </Pressable>

      {indicator?.params.map((param) => (
        <NumberField
          key={param.key}
          label={param.key === 'n' ? `기간 (${param.min}~${param.max})` : param.key}
          accessibilityLabel={`${slot} ${param.key === 'n' ? '기간' : param.key}`}
          value={operand.params[param.key] ?? ''}
          unit="일"
          onChange={(value) => onChange({ ...operand, params: { ...operand.params, [param.key]: value } })}
        />
      ))}

      {choices.length > 1 && (
        <View style={styles.chips}>
          {choices.map((choice) => (
            <Chip
              key={choice.label}
              label={choice.label}
              selected={sameTransform(transform, choice.transform)}
              onPress={() => setTransform(choice.transform)}
            />
          ))}
        </View>
      )}
      {transform.type !== 'identity' && (
        <NumberField
          label={range ? `N (${range.min}~${range.max})` : 'N'}
          accessibilityLabel={`${slot} N`}
          value={transform.n}
          unit="일"
          onChange={(n) => onChange({ ...operand, transform: { ...transform, n } })}
        />
      )}
      {error && <Text style={[type.caption, { color: palette.errorText }]}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  operand: { marginTop: space.sm },
  picker: {
    height: size.field,
    borderWidth: 1,
    borderRadius: radius.button,
    paddingHorizontal: space.base,
    marginTop: space.sm,
    marginBottom: space.sm,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, marginBottom: space.sm },
});
```

- [ ] **Step 5: 조건 상자를 쓴다**

`front-end/src/screens/alertEditor/ConditionBox.tsx`:

```tsx
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import type { FieldError } from '@/api/types';
import type { AlertCatalog, Cadence, Market } from '@/api/alertTypes';
import { useTheme } from '@/design/theme';
import { radius, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { formatKrwReading } from '@/format/number';
import {
  constUnit,
  findIndicator,
  scopeInUse,
  showModifier,
  withLeft,
  withOperator,
} from '@/screens/alertEditor/composable';
import { type ConditionDraft, emptyOperand, operandFor, toNumber } from '@/screens/alertEditor/draft';
import { errorAt, errorUnder } from '@/screens/alertEditor/fieldErrors';
import { IndicatorSheet } from '@/screens/alertEditor/IndicatorSheet';
import { NumberField } from '@/screens/alertEditor/NumberField';
import { OperandEditor } from '@/screens/alertEditor/OperandEditor';
import { Chip } from '@/ui/Chip';
import { SegmentedControl } from '@/ui/SegmentedControl';
import { TextButton } from '@/ui/TextButton';

const RIGHT_KINDS = [
  { value: 'const', label: '상수' },
  { value: 'operand', label: '지표' },
];

/** 조건 상자 하나 — 지표 · 변형 · 연산자 · 기준값 · 유지 방식 (§12.5.4 · §12.9.1). */
export function ConditionBox({
  index,
  condition,
  conditions,
  cadence,
  market,
  held,
  catalog,
  errors,
  removable,
  onChange,
  onRemove,
}: {
  index: number;
  condition: ConditionDraft;
  /** 다른 조건이 쓰는 지표의 범위를 보려고 받는다. */
  conditions: ConditionDraft[];
  cadence: Cadence;
  market: Market;
  held: boolean;
  catalog: AlertCatalog;
  errors: FieldError[];
  removable: boolean;
  onChange: (next: ConditionDraft) => void;
  onRemove: () => void;
}) {
  const palette = useTheme();
  const [sheet, setSheet] = useState<'left' | 'right' | null>(null);
  const slot = `조건 ${index + 1}`;
  const prefix = `trigger_spec.conditions[${index}]`;
  const left = findIndicator(catalog, condition.left.indicator);
  const right = condition.right.kind === 'operand' ? findIndicator(catalog, condition.right.operand.indicator) : null;
  const operators = left ? catalog.operators.filter((o) => left.allowed_operators.includes(o.key)) : catalog.operators;
  const crossing = condition.op === 'crosses_above' || condition.op === 'crosses_below';
  const constValue = condition.right.kind === 'const' ? condition.right.value : '';

  return (
    <View style={[styles.box, { borderColor: palette.border }]}>
      <View style={styles.head}>
        <Text style={[type.label, { color: palette.text }]}>{slot}</Text>
        {removable && <TextButton label="✕" accessibilityLabel={`${slot} 지우기`} onPress={onRemove} />}
      </View>

      <OperandEditor
        slot={slot}
        label="지표"
        side="left"
        operand={condition.left}
        indicator={left}
        cadence={cadence}
        catalog={catalog}
        error={errorUnder(errors, `${prefix}.left`)}
        onPick={() => setSheet('left')}
        onChange={(next) => onChange({ ...condition, left: next })}
      />

      <Text style={[type.label, styles.label, { color: palette.text }]}>연산자</Text>
      <View style={styles.chips}>
        {operators.map((op) => (
          <Chip
            key={op.key}
            label={op.symbol}
            accessibilityLabel={`연산자 ${op.word}`}
            selected={condition.op === op.key}
            onPress={() => onChange(withOperator(condition, op.key))}
          />
        ))}
      </View>
      {errorAt(errors, `${prefix}.op`) && (
        <Text style={[type.caption, { color: palette.errorText }]}>{errorAt(errors, `${prefix}.op`)}</Text>
      )}

      <Text style={[type.label, styles.label, { color: palette.text }]}>기준값</Text>
      {/* 교차는 지표끼리만 견준다. 상수 칸을 내놓지 않는다(§5.2). */}
      {!crossing && (
        <SegmentedControl
          accessibilityLabel={`${slot} 기준값 종류`}
          segments={RIGHT_KINDS}
          value={condition.right.kind}
          onChange={(kind) =>
            onChange({
              ...condition,
              right: kind === 'const' ? { kind: 'const', value: '' } : { kind: 'operand', operand: emptyOperand() },
            })
          }
        />
      )}
      {condition.right.kind === 'const' ? (
        <View style={styles.label}>
          <NumberField
            label="값"
            accessibilityLabel={`${slot} 기준값`}
            value={constValue}
            unit={constUnit(left, condition.left.transform, market)}
            note={left?.unit === 'krw' && toNumber(constValue) !== null ? formatKrwReading(toNumber(constValue)) : undefined}
            error={errorUnder(errors, `${prefix}.right`)}
            onChange={(value) => onChange({ ...condition, right: { kind: 'const', value } })}
          />
        </View>
      ) : (
        <OperandEditor
          slot={slot}
          label="비교 지표"
          side="right"
          operand={condition.right.operand}
          indicator={right}
          cadence={cadence}
          catalog={catalog}
          error={errorUnder(errors, `${prefix}.right`)}
          onPick={() => setSheet('right')}
          onChange={(next) => onChange({ ...condition, right: { kind: 'operand', operand: next } })}
        />
      )}

      {showModifier(condition, catalog) && (
        <NumberField
          label="유지 방식"
          accessibilityLabel={`${slot} 유지`}
          value={condition.modifier}
          unit={cadence === 'CLOSE' ? '일 연속' : '분 이상 유지'}
          error={errorUnder(errors, `${prefix}.modifier`)}
          onChange={(modifier) => onChange({ ...condition, modifier })}
        />
      )}

      <IndicatorSheet
        visible={sheet !== null}
        catalog={catalog}
        context={{
          cadence,
          market,
          held,
          side: sheet ?? 'left',
          otherScope: scopeInUse(conditions, { index, side: sheet ?? 'left' }, catalog),
        }}
        onClose={() => setSheet(null)}
        onPick={(indicator) => {
          onChange(
            sheet === 'left'
              ? withLeft(condition, indicator)
              : { ...condition, right: { kind: 'operand', operand: operandFor(indicator) } },
          );
          setSheet(null);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  box: { borderWidth: 1, borderRadius: radius.card, padding: space.md, marginTop: space.md },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  label: { marginTop: space.md },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, marginTop: space.sm },
});
```

- [ ] **Step 6: 단계 화면을 쓴다**

`front-end/src/screens/alertEditor/ComposableStep.tsx`:

```tsx
import { useState } from 'react';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import type { Cadence } from '@/api/alertTypes';
import { useTheme } from '@/design/theme';
import { screenPadding, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { CurrentBox, SentenceBox } from '@/screens/alerts/PreviewBoxes';
import { ConditionBox } from '@/screens/alertEditor/ConditionBox';
import { MAX_CONDITIONS, cadenceChangeClears } from '@/screens/alertEditor/draft';
import { useDraftPreview, useEditor } from '@/screens/alertEditor/EditorContext';
import { errorAt, errorsOutside } from '@/screens/alertEditor/fieldErrors';
import { PreviewFailure, StepFooter, canProceed } from '@/screens/alertEditor/StepFooter';
import type { EditorParamList } from '@/screens/alertEditor/types';
import { ConfirmSheet } from '@/ui/ConfirmSheet';
import { SegmentedControl } from '@/ui/SegmentedControl';
import { TextButton } from '@/ui/TextButton';

const CADENCES = [
  { value: 'INTRADAY', label: '장중' },
  { value: 'CLOSE', label: '종가' },
];

/** `장중으로` · `종가로` — 받침에 따라 조사가 다르다. */
const TO: Record<Cadence, string> = { INTRADAY: '장중으로', CLOSE: '종가로' };

const PLACED = ['trigger_spec.conditions', 'cadence', 'name', 'notify_mode', 'cooldown_min', 'expires_at'];

/**
 * 직접 조건 만들기 (§12.5.4). 조건 상자는 AND로 묶이고 최대 5개다.
 * 평가 시점은 알림 전체에 하나다. 바꾸면 맞지 않는 칸이 생길 때만 먼저 묻는다.
 */
export function ComposableStep() {
  const { draft, dispatch, catalog } = useEditor();
  const navigation = useNavigation<NativeStackNavigationProp<EditorParamList>>();
  const palette = useTheme();
  const { preview, pending, error, refetch } = useDraftPreview();
  const [asking, setAsking] = useState<Cadence | null>(null);
  const instrument = draft.instrument;
  if (!instrument) return null;
  const errors = preview?.errors ?? [];

  const changeCadence = (next: Cadence) => {
    if (next === draft.cadence) return;
    if (cadenceChangeClears(draft, next, catalog)) setAsking(next);
    else dispatch({ type: 'cadence', cadence: next, catalog });
  };

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={[type.caption, styles.caption, { color: palette.textMuted }]}>평가 시점 · 이 알림 전체</Text>
        <SegmentedControl
          accessibilityLabel="평가 시점"
          segments={CADENCES}
          value={draft.cadence}
          onChange={(value) => changeCadence(value as Cadence)}
        />
        {errorAt(errors, 'cadence') && (
          <Text style={[type.caption, { color: palette.errorText }]}>{errorAt(errors, 'cadence')}</Text>
        )}

        {draft.conditions.map((condition, index) => (
          <ConditionBox
            key={index}
            index={index}
            condition={condition}
            conditions={draft.conditions}
            cadence={draft.cadence}
            market={instrument.market}
            held={instrument.held}
            catalog={catalog}
            errors={errors}
            removable={draft.conditions.length > 1}
            onChange={(next) => dispatch({ type: 'condition', index, condition: next })}
            onRemove={() => dispatch({ type: 'remove-condition', index })}
          />
        ))}

        {draft.conditions.length < MAX_CONDITIONS && (
          <View style={styles.add}>
            <TextButton label="＋ 조건 추가 (AND)" onPress={() => dispatch({ type: 'add-condition' })} />
          </View>
        )}

        {errorsOutside(errors, PLACED).map((e) => (
          <Text key={e.path} style={[type.caption, { color: palette.errorText }]}>
            {e.message}
          </Text>
        ))}

        <PreviewFailure error={error} onRetry={refetch} />
        <SentenceBox sentence={preview?.summary?.sentence} pending={pending} />
        <CurrentBox current={preview?.current} pending={pending} />
      </ScrollView>
      <StepFooter label="다음" disabled={!canProceed(preview, pending)} onPress={() => navigation.navigate('settings')} />

      <ConfirmSheet
        visible={asking !== null}
        title={asking ? `${TO[asking]} 바꾸면 맞지 않는 조건이 초기화돼요` : ''}
        confirmLabel="바꾸기"
        onCancel={() => setAsking(null)}
        onConfirm={() => {
          if (asking) dispatch({ type: 'cadence', cadence: asking, catalog });
          setAsking(null);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: { paddingHorizontal: screenPadding, paddingVertical: space.lg },
  caption: { marginBottom: space.xs },
  add: { alignItems: 'center', marginTop: space.md },
});
```

조건 상자의 `key`가 위치(`index`)인 것은 조건에 따로 ID가 없어서다. 가운데 상자를 지우면 뒤 상자들이 한 칸씩 당겨지며 각 상자의 시트 열림 상태(`sheet`)가 옆 상자로 옮겨갈 수 있다 — 시트는 지우기 버튼을 누르는 순간 닫혀 있으므로 보이는 문제는 없다.

- [ ] **Step 7: 흐름에 등록한다**

`AlertEditorNavigator.tsx`:

```tsx
import { ComposableStep } from '@/screens/alertEditor/ComposableStep';
```

```tsx
        <Stack.Screen name="composable" component={ComposableStep} options={{ title: '직접 조건 만들기' }} />
```

- [ ] **Step 8: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest src/__tests__/alertComposable.test.tsx && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 9: 커밋한다**

```bash
git add src/screens/alertEditor src/__tests__/alertComposable.test.tsx
git commit -m "feat: 지표·변형·연산자·기준값·유지로 조건을 직접 만든다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: 푸시 — 권한 · 기기 등록·해제 · 푸시로 열기 · 앱 안 배너 · 안내 배너

**Files:**
- Modify: `front-end/package.json` · `package-lock.json` (⛔ 승인 후 `npx expo install`)
- Create: `front-end/src/storage/kvStore.ts`
- Modify: `front-end/src/auth/tokenStore.ts` (저장소를 kvStore에서 가져옴)
- Create: `front-end/src/push/config.ts` · `notifications.ts` · `pushInbox.ts` · `device.ts` · `gate.ts` · `usePushBanners.ts`
- Create: `front-end/src/push/PushRouter.tsx` · `InAppBanner.tsx` · `PushBanners.tsx`
- Modify: `front-end/src/app/App.tsx` (리스너 시작)
- Modify: `front-end/src/app/navigation/RootStack.tsx` (`PushRouter`)
- Modify: `front-end/src/auth/AuthContext.tsx` (로그아웃 때 기기 해제, 로그인 실패 때 대기 중인 푸시 버림)
- Modify: `front-end/src/screens/alerts/AlertsScreen.tsx` (`PushBanners`)
- Create: `front-end/src/testing/notificationsMock.ts`
- Modify: `front-end/jest.setup.js`
- Test: `front-end/src/__tests__/push.test.tsx`

**Interfaces:**
- Consumes: `registerDeviceToken` · `unregisterDeviceId` · `invalidateAlertData` · `keys` (Task 3), `RootStack` · `alert-event` (Task 7)
- Produces:
  - `pushCapable(): boolean` · `isAndroid(): boolean` · `easProjectId(): string | null` (`@/push/config`)
  - `type PermissionState = 'undetermined' | 'denied' | 'granted' | 'unsupported'` · `permissionState()` · `requestPermission()` · `expoPushToken(projectId)` · `startNotificationListeners(): () => void` (`@/push/notifications`)
  - `deliverOpen(eventId)` · `subscribeOpens(fn): () => void` · `discardPendingOpen()` · `deliverArrival(arrival)` · `subscribeArrivals(fn): () => void` · `resetPushInbox()` · `type Arrival = { eventId: string; title: string; body: string }` (`@/push/pushInbox`)
  - `registerThisDevice(): Promise<void>` · `unregisterThisDevice(): Promise<void>` (`@/push/device`)
  - `type GateSheet = 'ask' | 'settings' | null` · `gateBeforeSave(): Promise<GateSheet>` · `allowPush(): Promise<void>` · `openPushSettings(): void` (`@/push/gate`) — Task 13이 저장 버튼에서 쓴다.
  - `kvStore` (`@/storage/kvStore`) — `setItemAsync` · `getItemAsync` · `deleteItemAsync`
  - 테스트: `notificationState` · `emitResponse(eventId, identifier?)` · `emitReceived(arrival)` · `resetNotifications()` (`@/testing/notificationsMock`)

- [ ] **Step 1: ⛔ 승인 — 패키지 설치**

사용자에게 묻는다: "`npx expo install expo-notifications expo-constants`로 두 패키지를 넣을까요? SDK 54에 맞는 버전을 고릅니다." 승인을 받은 뒤에만 실행한다.

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project/front-end
npx expo install expo-notifications expo-constants
git diff --stat package.json
```

Expected: `package.json`의 dependencies에 두 줄이 더해지고 버전이 `~`로 고정된다. `expo` 버전은 바뀌지 않는다(`^54.0.0` 그대로). 바뀌었으면 멈추고 보고한다.

설치한 버전의 타입으로 이 태스크가 쓰는 API를 확인한다. 이름이나 필드가 다르면 Step 6의 `notifications.ts`를 설치된 타입에 맞추고 그 차이를 보고한다.

```bash
grep -n "getLastNotificationResponseAsync\|addNotificationResponseReceivedListener\|addNotificationReceivedListener\|getExpoPushTokenAsync" node_modules/expo-notifications/build/index.d.ts
grep -rn "shouldShowBanner\|shouldShowList\|shouldShowAlert" node_modules/expo-notifications/build/Notifications.types.d.ts
```

`app.json`에는 손대지 않는다. `extra.eas.projectId`는 사용자가 `eas init`으로 넣는다(Task 14).

- [ ] **Step 2: 테스트 대역을 둔다**

`front-end/src/testing/notificationsMock.ts`:

```ts
/**
 * 테스트에서 expo-notifications 대신 쓰는 대역. jest.setup.js가 모든 테스트에 꽂는다.
 * 권한 상태와 마지막 응답을 테스트가 정하고, 푸시 응답·도착을 흉내 낸다.
 * 앱 코드는 이 파일을 쓰지 않는다.
 */

type Permission = 'undetermined' | 'denied' | 'granted';

export const notificationState = {
  permission: 'undetermined' as Permission,
  /** 권한 창에서 사용자가 고를 답. */
  answer: 'granted' as Permission,
  lastResponse: null as unknown,
  requested: 0,
};

const responseListeners = new Set<(response: unknown) => void>();
const receivedListeners = new Set<(notification: unknown) => void>();

function result() {
  const status = notificationState.permission;
  return { status, granted: status === 'granted', canAskAgain: status !== 'denied', expires: 'never' };
}

function notification(eventId: string, identifier: string, title = '', body = '') {
  return { request: { identifier, content: { title, body, data: { event_id: eventId } } } };
}

export async function getPermissionsAsync() {
  return result();
}

export async function requestPermissionsAsync() {
  notificationState.requested += 1;
  if (notificationState.permission === 'undetermined') notificationState.permission = notificationState.answer;
  return result();
}

export async function getExpoPushTokenAsync() {
  return { type: 'expo', data: 'ExponentPushToken[test]' };
}

export function setNotificationHandler() {}

export function addNotificationResponseReceivedListener(listener: (response: unknown) => void) {
  responseListeners.add(listener);
  return { remove: () => responseListeners.delete(listener) };
}

export function addNotificationReceivedListener(listener: (notification: unknown) => void) {
  receivedListeners.add(listener);
  return { remove: () => receivedListeners.delete(listener) };
}

export async function getLastNotificationResponseAsync() {
  return notificationState.lastResponse;
}

/** 사용자가 푸시를 누른 것. */
export function emitResponse(eventId: string, identifier = `n-${eventId}`) {
  const response = { notification: notification(eventId, identifier), actionIdentifier: 'default' };
  for (const listener of responseListeners) listener(response);
}

/** 앱이 앞에 떠 있을 때 푸시가 온 것. */
export function emitReceived(arrival: { eventId: string; title: string; body: string }) {
  const n = notification(arrival.eventId, `n-${arrival.eventId}`, arrival.title, arrival.body);
  for (const listener of receivedListeners) listener(n);
}

/** 앱이 꺼져 있던 동안 누른 푸시 — 실행 직후 마지막 응답으로 읽힌다. */
export function setColdStartResponse(eventId: string, identifier = `n-${eventId}`) {
  notificationState.lastResponse = { notification: notification(eventId, identifier), actionIdentifier: 'default' };
}

export function resetNotifications() {
  notificationState.permission = 'undetermined';
  notificationState.answer = 'granted';
  notificationState.lastResponse = null;
  notificationState.requested = 0;
  responseListeners.clear();
  receivedListeners.clear();
}
```

`front-end/jest.setup.js` 끝에 더한다.

```js
// 원격 푸시 모듈은 네이티브 쪽이 없어 테스트에서 그대로 쓸 수 없다. 모든 테스트에 대역을 꽂는다.
jest.mock('expo-notifications', () => require('./src/testing/notificationsMock'));
```

- [ ] **Step 3: 실패하는 테스트를 쓴다**

`front-end/src/__tests__/push.test.tsx`:

```tsx
import { useState } from 'react';
import { Pressable, Text } from 'react-native';
import { NavigationContainer, createNavigationContainerRef } from '@react-navigation/native';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { setAccessToken } from '@/api/client';
import { RootStack } from '@/app/navigation/RootStack';
import type { RootStackParamList } from '@/app/navigation/types';
import { AuthProvider, useAuth } from '@/auth/AuthContext';
import { alertsFixture, eventDetailFixture, presetDetailFixture, previewFixture } from '@/fixtures/alerts';
import { goldenAssetChange, goldenSummary } from '@/fixtures/golden';
import { easProjectId, isAndroid, pushCapable } from '@/push/config';
import { registerThisDevice } from '@/push/device';
import { gateBeforeSave } from '@/push/gate';
import { startNotificationListeners } from '@/push/notifications';
import { deliverArrival, deliverOpen, resetPushInbox, subscribeOpens } from '@/push/pushInbox';
import { AlertsScreen } from '@/screens/alerts/AlertsScreen';
import {
  emitResponse,
  notificationState,
  resetNotifications,
  setColdStartResponse,
} from '@/testing/notificationsMock';
import { renderWithNavigation } from '@/testing/renderWithNavigation';
import { storedItems } from '@/testing/secureStoreMock';
import { type Route, serveRoutes } from '@/testing/serveRoutes';

jest.mock('expo-secure-store', () => require('@/testing/secureStoreMock'));
jest.mock('@/push/config', () => ({
  pushCapable: jest.fn(() => true),
  isAndroid: jest.fn(() => false),
  easProjectId: jest.fn(() => 'project-test'),
}));

const METRICS = {
  frame: { x: 0, y: 0, width: 390, height: 844 },
  insets: { top: 47, left: 0, right: 0, bottom: 34 },
};

const appRoutes: Route[] = [
  { path: '/portfolio/views/summary', body: goldenSummary },
  { path: '/portfolio/views/asset-change', body: goldenAssetChange },
  { path: '/alerts', body: alertsFixture },
  { path: '/alert-events/unread-count', body: { count: 1 } },
  { path: '/alert-events/e-1', body: eventDetailFixture },
  { method: 'POST', path: '/alert-events/e-1/read', status: 204 },
  { method: 'POST', path: '/devices', body: { device_id: 'dev-1' } },
  { method: 'DELETE', path: '/devices/dev-1', status: 204 },
];

async function renderApp() {
  const navigation = createNavigationContainerRef<RootStackParamList>();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  await render(
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider initialMetrics={METRICS}>
        <NavigationContainer ref={navigation}>
          <RootStack />
        </NavigationContainer>
      </SafeAreaProvider>
    </QueryClientProvider>,
  );
  return navigation;
}

beforeEach(() => {
  setAccessToken('tok');
  resetNotifications();
  resetPushInbox();
  storedItems.clear();
  jest.mocked(pushCapable).mockReturnValue(true);
  jest.mocked(isAndroid).mockReturnValue(false);
  jest.mocked(easProjectId).mockReturnValue('project-test');
});
afterEach(() => setAccessToken(null));

describe('푸시 대기열', () => {
  it('받을 화면이 아직 없으면 맡아 두었다가 한 번만 넘긴다', () => {
    deliverOpen('e-1');
    const first = jest.fn();
    const second = jest.fn();

    const off = subscribeOpens(first);
    off();
    subscribeOpens(second);

    expect(first).toHaveBeenCalledWith('e-1');
    expect(second).not.toHaveBeenCalled();
  });

  it('버리면 넘기지 않는다', () => {
    deliverOpen('e-1');
    resetPushInbox();
    const fn = jest.fn();
    subscribeOpens(fn);
    expect(fn).not.toHaveBeenCalled();
  });

  it('누른 푸시와 꺼진 동안 누른 푸시를 같은 응답은 한 번만 넘긴다', async () => {
    setColdStartResponse('e-cold');
    const opened = jest.fn();
    const off = subscribeOpens(opened);

    const stop = startNotificationListeners();
    await act(async () => undefined);
    emitResponse('e-cold');
    emitResponse('e-2');
    stop();
    off();

    expect(opened.mock.calls).toEqual([['e-cold'], ['e-2']]);
  });
});

describe('푸시를 누르면 (IA §4)', () => {
  it('탭을 알림으로 바꾸고 그 위에 울린 알림 상세를 쌓는다 — 뒤로 가면 알림 탭', async () => {
    serveRoutes(appRoutes);
    deliverOpen('e-1');

    const navigation = await renderApp();

    await waitFor(() => expect(navigation.getCurrentRoute()?.name).toBe('alert-event'));
    expect(navigation.getCurrentRoute()?.params).toEqual({ eventId: 'e-1' });
    await act(async () => navigation.goBack());
    await waitFor(() => expect(navigation.getCurrentRoute()?.name).toBe('alerts'));
  });

  it('다른 화면이 위에 떠 있어도 탭 묶음은 하나다', async () => {
    serveRoutes([...appRoutes, { path: '/alerts/a-satisfied', body: presetDetailFixture }, { method: 'POST', path: '/alerts/preview', body: previewFixture }]);
    const navigation = await renderApp();
    await waitFor(() => expect(screen.getByText('총자산')).toBeTruthy());
    await act(async () => navigation.navigate('alert', { alertId: 'a-satisfied' }));

    await act(async () => deliverOpen('e-1'));

    await waitFor(() => expect(navigation.getCurrentRoute()?.name).toBe('alert-event'));
    expect(navigation.getRootState().routes.map((route) => route.name)).toEqual(['tabs', 'alert-event']);
  });

  it('앞에 떠 있을 때는 화면을 옮기지 않고 앱 안 배너를 띄운다. 배너를 누르면 상세', async () => {
    const calls = serveRoutes(appRoutes);
    const navigation = await renderApp();
    await waitFor(() => expect(screen.getByText('총자산')).toBeTruthy());
    const before = calls.filter((c) => c.path === '/alert-events/unread-count').length;

    await act(async () => deliverArrival({ eventId: 'e-1', title: '삼성전자 · 가격 도달', body: '현재가 70,200원 ≥ 70,000원 · 10:15 기준' }));

    expect(navigation.getCurrentRoute()?.name).toBe('summary');
    expect(screen.getByText('삼성전자 · 가격 도달')).toBeTruthy();
    await waitFor(() =>
      expect(calls.filter((c) => c.path === '/alert-events/unread-count').length).toBeGreaterThan(before),
    );

    await fireEvent.press(screen.getByRole('button', { name: '삼성전자 · 가격 도달 열기' }));
    await waitFor(() => expect(navigation.getCurrentRoute()?.name).toBe('alert-event'));
  });
});

describe('기기 등록', () => {
  it('권한이 있으면 토큰을 등록하고 device_id를 보관한다', async () => {
    notificationState.permission = 'granted';
    const calls = serveRoutes(appRoutes);

    await registerThisDevice();

    const post = calls.find((c) => c.method === 'POST' && c.path === '/devices');
    expect(post?.body).toEqual({ expo_push_token: 'ExponentPushToken[test]', platform: 'IOS' });
    expect(storedItems.get('alerts.device_id')).toBe('dev-1');
  });

  it.each([
    ['권한이 없다', () => (notificationState.permission = 'undetermined')],
    ['EAS 프로젝트가 없다', () => jest.mocked(easProjectId).mockReturnValue(null)],
    ['원격 푸시가 없는 플랫폼이다', () => jest.mocked(pushCapable).mockReturnValue(false)],
  ])('%s — 등록하지 않는다', async (_case, arrange) => {
    notificationState.permission = 'granted';
    arrange();
    const calls = serveRoutes(appRoutes);

    await registerThisDevice();

    expect(calls.some((c) => c.path === '/devices')).toBe(false);
  });

  it('로그아웃은 토큰이 살아 있을 때 기기를 지우고 끝난다', async () => {
    storedItems.set('portfolio.access_token', 'tok-live');
    storedItems.set('portfolio.expires_at', '2099-01-01T00:00:00+09:00');
    storedItems.set('alerts.device_id', 'dev-1');
    const calls = serveRoutes(appRoutes);

    function LogoutProbe() {
      const { status, logout } = useAuth();
      return (
        <Pressable accessibilityRole="button" accessibilityLabel="로그아웃" onPress={logout}>
          <Text>{status}</Text>
        </Pressable>
      );
    }
    await render(
      <AuthProvider>
        <LogoutProbe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText('authenticated')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '로그아웃' }));

    await waitFor(() => expect(screen.getByText('unauthenticated')).toBeTruthy());
    const del = calls.find((c) => c.method === 'DELETE' && c.path === '/devices/dev-1');
    expect(del?.auth).toBe('Bearer tok-live');
    expect(storedItems.has('alerts.device_id')).toBe(false);
  });

  it('기기 해제가 401을 받아도 만료가 아니라 그냥 로그아웃이다', async () => {
    storedItems.set('portfolio.access_token', 'tok-live');
    storedItems.set('portfolio.expires_at', '2099-01-01T00:00:00+09:00');
    storedItems.set('alerts.device_id', 'dev-1');
    serveRoutes([
      { method: 'DELETE', path: '/devices/dev-1', status: 401, body: { error: { code: 'UNAUTHENTICATED', message: '다시 로그인해 주세요' } } },
    ]);

    function LogoutProbe() {
      const { status, sessionExpired, logout } = useAuth();
      return (
        <Pressable accessibilityRole="button" accessibilityLabel="로그아웃" onPress={logout}>
          <Text>{`${status} ${sessionExpired ? '만료' : '정상'}`}</Text>
        </Pressable>
      );
    }
    await render(
      <AuthProvider>
        <LogoutProbe />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByText('authenticated 정상')).toBeTruthy());

    await fireEvent.press(screen.getByRole('button', { name: '로그아웃' }));

    await waitFor(() => expect(screen.getByText('unauthenticated 정상')).toBeTruthy());
  });

  it('로그인에 실패하면 맡아 둔 푸시를 버린다', async () => {
    serveRoutes([
      { method: 'POST', path: '/auth/login', status: 401, body: { error: { code: 'INVALID_CREDENTIALS', message: '이메일 또는 비밀번호가 맞지 않아요' } } },
    ]);
    deliverOpen('e-1');

    function LoginProbe() {
      const { login } = useAuth();
      const [done, setDone] = useState(false);
      return (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="로그인"
          onPress={() => void login('a@a.com', 'x').catch(() => setDone(true))}
        >
          <Text>{done ? '실패' : '대기'}</Text>
        </Pressable>
      );
    }
    await render(
      <AuthProvider>
        <LoginProbe />
      </AuthProvider>,
    );
    await fireEvent.press(screen.getByRole('button', { name: '로그인' }));
    await waitFor(() => expect(screen.getByText('실패')).toBeTruthy());

    const fn = jest.fn();
    subscribeOpens(fn);
    expect(fn).not.toHaveBeenCalled();
  });
});

describe('저장 전 권한 판단 (§12.7)', () => {
  it.each([
    ['undetermined', 'ask'],
    ['denied', 'settings'],
    ['granted', null],
  ] as const)('%s → %s', async (permission, sheet) => {
    notificationState.permission = permission;
    await expect(gateBeforeSave()).resolves.toBe(sheet);
  });

  it('원격 푸시가 없는 플랫폼은 묻지 않는다', async () => {
    jest.mocked(pushCapable).mockReturnValue(false);
    await expect(gateBeforeSave()).resolves.toBeNull();
  });
});

describe('알림 탭의 안내 배너 (§12.7)', () => {
  it('권한 거부 배너는 닫으면 이 기기에서 다시 보이지 않는다', async () => {
    notificationState.permission = 'denied';
    serveRoutes(appRoutes);
    await renderWithNavigation(<AlertsScreen />, { others: ['alert', 'alert-events', 'alert-event', 'alert-editor'] });

    await waitFor(() => expect(screen.getByText('알림 권한이 꺼져 있어 앱 안에서만 볼 수 있어요')).toBeTruthy());
    await fireEvent.press(screen.getByRole('button', { name: '권한 안내 닫기' }));

    expect(screen.queryByText('알림 권한이 꺼져 있어 앱 안에서만 볼 수 있어요')).toBeNull();
    expect(storedItems.get('alerts.banner.permission_dismissed')).toBe('1');
  });

  it('Android 안내', async () => {
    jest.mocked(pushCapable).mockReturnValue(false);
    jest.mocked(isAndroid).mockReturnValue(true);
    serveRoutes(appRoutes);
    await renderWithNavigation(<AlertsScreen />, { others: ['alert', 'alert-events', 'alert-event', 'alert-editor'] });

    await waitFor(() =>
      expect(screen.getByText('Android에서는 앱 안에서만 알림을 확인할 수 있어요')).toBeTruthy(),
    );
  });
});
```

- [ ] **Step 4: 테스트가 실패하는지 본다**

Run: `npx jest src/__tests__/push.test.tsx`
Expected: FAIL — `Cannot find module '@/push/config'`.

- [ ] **Step 5: 저장소를 공용으로 뽑는다**

`front-end/src/storage/kvStore.ts`:

```ts
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

/**
 * 앱을 껐다 켜도 남는 작은 값의 자리.
 *
 * 기기에서는 iOS Keychain · 안드로이드 Keystore를 쓴다.
 * 브라우저에는 그 저장소가 없어 localStorage로 간다 — 잠금장치가 없는 자리다.
 * 웹은 개발 중 화면과 응답을 함께 보는 경로일 뿐이고 배포하지 않는다.
 */
function webStore() {
  return {
    setItemAsync: async (key: string, value: string) => {
      globalThis.localStorage?.setItem(key, value);
    },
    getItemAsync: async (key: string) => globalThis.localStorage?.getItem(key) ?? null,
    deleteItemAsync: async (key: string) => {
      globalThis.localStorage?.removeItem(key);
    },
  };
}

export const kvStore = Platform.OS === 'web' ? webStore() : SecureStore;
```

`auth/tokenStore.ts`에서 `Platform` · `SecureStore` import와 `webStore()` · `const store = …`를 지우고 `import { kvStore as store } from '@/storage/kvStore';`로 바꾼다. 파일 머리 주석의 저장소 설명 문단은 kvStore로 옮겨졌으므로 `토큰을 앱을 껐다 켜도 남는 자리(kvStore)에 넣고 뺀다.`와 `비밀번호는 어디에도 저장하지 않는다.` 두 줄만 남긴다. 기존 `login.test.tsx` · `session.test.ts`가 그대로 통과해야 한다.

- [ ] **Step 6: 푸시 모듈을 쓴다**

`front-end/src/push/config.ts`:

```ts
import Constants from 'expo-constants';
import { Platform } from 'react-native';

/**
 * 원격 푸시를 받을 수 있는 플랫폼인가. v1은 iOS뿐이다(§9.6) —
 * Expo Go는 SDK 53부터 Android에서 원격 푸시를 지원하지 않는다.
 */
export function pushCapable(): boolean {
  return Platform.OS === 'ios';
}

export function isAndroid(): boolean {
  return Platform.OS === 'android';
}

/**
 * EAS 프로젝트 ID. Expo 푸시 토큰을 받는 데 필요하다. `eas init`이 app.json의
 * `extra.eas.projectId`에 넣는다. 없으면 기기를 등록하지 않는다 — 알림은 앱 안 목록과 배지로 남는다.
 */
export function easProjectId(): string | null {
  const id: unknown = Constants.expoConfig?.extra?.eas?.projectId;
  return typeof id === 'string' && id !== '' ? id : null;
}
```

`front-end/src/push/pushInbox.ts`:

```ts
/**
 * 푸시와 화면 사이의 우편함. expo-notifications를 모른다.
 *
 * 누른 푸시는 받을 화면(탭 묶음)이 그려진 뒤에야 열 수 있다. 로그인 전에 받은 `event_id`는
 * 네비게이션 바깥인 여기에 맡겨 두었다가, 탭 묶음이 그려지면 한 번 넘기고 버린다(IA §4.2).
 */

export type Arrival = { eventId: string; title: string; body: string };

let pending: string | null = null;
let opener: ((eventId: string) => void) | null = null;
const arrivalListeners = new Set<(arrival: Arrival) => void>();

export function deliverOpen(eventId: string): void {
  if (opener) opener(eventId);
  else pending = eventId;
}

export function subscribeOpens(fn: (eventId: string) => void): () => void {
  opener = fn;
  if (pending !== null) {
    const eventId = pending;
    pending = null;
    fn(eventId);
  }
  return () => {
    if (opener === fn) opener = null;
  };
}

/** 로그인에 실패하거나 로그아웃하면 맡아 둔 것을 버린다. */
export function discardPendingOpen(): void {
  pending = null;
}

export function deliverArrival(arrival: Arrival): void {
  for (const listener of arrivalListeners) listener(arrival);
}

export function subscribeArrivals(fn: (arrival: Arrival) => void): () => void {
  arrivalListeners.add(fn);
  return () => {
    arrivalListeners.delete(fn);
  };
}

/** 우편함을 비운다 — 맡아 둔 것 · 받는 화면 · 도착 리스너 모두. 테스트 사이에 상태가 새지 않게 한다. */
export function resetPushInbox(): void {
  pending = null;
  opener = null;
  arrivalListeners.clear();
}
```

`front-end/src/push/notifications.ts`:

```ts
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { pushCapable } from '@/push/config';
import { deliverArrival, deliverOpen } from '@/push/pushInbox';

/**
 * expo-notifications를 아는 유일한 파일. 권한 · 토큰 · 수신 리스너를 감싼다.
 * 푸시 페이로드의 `data`에는 `event_id`만 있다(§9.3).
 */

export type PermissionState = 'undetermined' | 'denied' | 'granted' | 'unsupported';

// 앞에 떠 있을 때는 시스템 배너를 띄우지 않는다. 앱 안 배너가 대신한다(IA §4.2).
if (Platform.OS !== 'web') {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: false,
      shouldShowList: false,
      shouldPlaySound: false,
      shouldSetBadge: false,
    }),
  });
}

function toState(result: { granted: boolean; status: string }): PermissionState {
  if (result.granted) return 'granted';
  return result.status === 'denied' ? 'denied' : 'undetermined';
}

export async function permissionState(): Promise<PermissionState> {
  if (!pushCapable()) return 'unsupported';
  return toState(await Notifications.getPermissionsAsync());
}

/** 시스템 권한 창을 띄운다. iOS는 한 번 거절하면 다시 뜨지 않으므로 안내 시트의 `허용하기`에서만 부른다. */
export async function requestPermission(): Promise<PermissionState> {
  if (!pushCapable()) return 'unsupported';
  return toState(await Notifications.requestPermissionsAsync());
}

export async function expoPushToken(projectId: string): Promise<string> {
  return (await Notifications.getExpoPushTokenAsync({ projectId })).data;
}

function eventIdOf(notification: Notifications.Notification): string | null {
  const id = notification.request.content.data?.event_id;
  return typeof id === 'string' ? id : null;
}

/**
 * 푸시를 누른 것과 앞에 떠 있을 때 온 것을 우편함으로 넘긴다. 앱이 켜질 때 한 번 부른다.
 * 앱이 꺼져 있던 동안 누른 푸시는 실행 직후의 마지막 응답으로 읽는다. 같은 응답이 리스너로도
 * 다시 올 수 있어 식별자로 한 번만 넘긴다.
 */
export function startNotificationListeners(): () => void {
  if (Platform.OS === 'web') return () => undefined;
  let handled: string | null = null;

  const open = (response: Notifications.NotificationResponse) => {
    const key = response.notification.request.identifier;
    if (key === handled) return;
    handled = key;
    const eventId = eventIdOf(response.notification);
    if (eventId) deliverOpen(eventId);
  };

  void Notifications.getLastNotificationResponseAsync().then((response) => {
    if (response) open(response);
  });
  const opened = Notifications.addNotificationResponseReceivedListener(open);
  const received = Notifications.addNotificationReceivedListener((notification) => {
    const eventId = eventIdOf(notification);
    if (!eventId) return;
    deliverArrival({
      eventId,
      title: notification.request.content.title ?? '',
      body: notification.request.content.body ?? '',
    });
  });

  return () => {
    opened.remove();
    received.remove();
  };
}
```

`front-end/src/push/device.ts`:

```ts
import { Platform } from 'react-native';

import { registerDeviceToken, unregisterDeviceId } from '@/api/alertEndpoints';
import { easProjectId, pushCapable } from '@/push/config';
import { expoPushToken, permissionState } from '@/push/notifications';
import { kvStore } from '@/storage/kvStore';

const KEY_DEVICE = 'alerts.device_id';

/**
 * 이 기기를 푸시 수신 기기로 등록하고 받은 `device_id`를 보관한다(§9.2).
 * 앱이 켜질 때마다 다시 등록해 토큰 교체를 따라간다.
 * 조건이 맞지 않거나 실패하면 조용히 넘어간다 — 발화는 앱 안 목록과 배지로 반드시 보인다(§9.5).
 * 푸시 토큰은 로그에 남기지 않는다.
 */
export async function registerThisDevice(): Promise<void> {
  if (!pushCapable()) return;
  const projectId = easProjectId();
  if (!projectId) return;
  try {
    if ((await permissionState()) !== 'granted') return;
    const token = await expoPushToken(projectId);
    const { device_id } = await registerDeviceToken(token, Platform.OS === 'ios' ? 'IOS' : 'ANDROID');
    await kvStore.setItemAsync(KEY_DEVICE, device_id);
  } catch {
    // 다음 실행에서 다시 시도한다.
  }
}

/**
 * 로그아웃할 때 이 기기의 등록을 지운다 — 공용 기기에서 로그아웃한 사람의 알림이 오면 안 된다(§9.2).
 * 서버에 이미 없으면(404) 그대로 끝낸다. 저장소를 읽지 못해도 로그아웃을 막지 않는다.
 */
export async function unregisterThisDevice(): Promise<void> {
  try {
    const deviceId = await kvStore.getItemAsync(KEY_DEVICE);
    if (deviceId) await unregisterDeviceId(deviceId).catch(() => undefined);
    await kvStore.deleteItemAsync(KEY_DEVICE);
  } catch {
    // 로그아웃은 계속된다.
  }
}
```

`front-end/src/push/gate.ts`:

```ts
import { Linking } from 'react-native';

import { registerThisDevice } from '@/push/device';
import { permissionState, requestPermission } from '@/push/notifications';

/**
 * 알림을 저장하기 전의 권한 안내 (§9.2 · §12.7).
 *
 * 로그인 직후에 묻지 않는다 — 알림을 만들지 않은 사용자에게는 권한을 줄 이유가 보이지 않는다.
 * 시스템 창보다 안내 시트를 먼저 띄운다. iOS 시스템 창은 한 번 거절하면 다시 뜨지 않는다.
 */

export type GateSheet = 'ask' | 'settings' | null;

export async function gateBeforeSave(): Promise<GateSheet> {
  try {
    const state = await permissionState();
    if (state === 'undetermined') return 'ask';
    if (state === 'denied') return 'settings';
    return null;
  } catch {
    return null;
  }
}

/** 안내 시트의 `허용하기`. 허용되면 곧바로 기기를 등록한다. */
export async function allowPush(): Promise<void> {
  try {
    if ((await requestPermission()) === 'granted') await registerThisDevice();
  } catch {
    // 권한 창이 실패해도 저장은 계속된다.
  }
}

export function openPushSettings(): void {
  void Linking.openSettings().catch(() => undefined);
}
```

`front-end/src/push/usePushBanners.ts`:

```ts
import { useCallback, useEffect, useState } from 'react';
import { AppState } from 'react-native';

import { isAndroid } from '@/push/config';
import { type PermissionState, permissionState } from '@/push/notifications';
import { kvStore } from '@/storage/kvStore';

const KEY = {
  permission: 'alerts.banner.permission_dismissed',
  android: 'alerts.banner.android_dismissed',
} as const;

type Kind = keyof typeof KEY;

/**
 * 알림 탭 위의 두 안내 — 권한 거부와 Android (§12.7).
 * 닫으면 그 기기에서는 다시 보이지 않는다. 설정에서 돌아오면 권한을 다시 읽는다.
 * 닫았는지 읽기 전에는 띄우지 않는다 — 떴다가 사라지면 깜빡인다.
 */
export function usePushBanners() {
  const [permission, setPermission] = useState<PermissionState | null>(null);
  const [dismissed, setDismissed] = useState<Record<Kind, boolean> | null>(null);

  const refresh = useCallback(() => {
    void permissionState()
      .then(setPermission)
      .catch(() => setPermission(null));
  }, []);

  useEffect(() => {
    refresh();
    void Promise.all([kvStore.getItemAsync(KEY.permission), kvStore.getItemAsync(KEY.android)])
      .then(([p, a]) => setDismissed({ permission: p === '1', android: a === '1' }))
      .catch(() => setDismissed({ permission: false, android: false }));
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') refresh();
    });
    return () => subscription.remove();
  }, [refresh]);

  const dismiss = (kind: Kind) => {
    setDismissed((current) => ({ permission: current?.permission ?? false, android: current?.android ?? false, [kind]: true }));
    void kvStore.setItemAsync(KEY[kind], '1').catch(() => undefined);
  };

  return {
    permissionDenied: permission === 'denied' && dismissed?.permission === false,
    android: isAndroid() && dismissed?.android === false,
    dismiss,
  };
}
```

`front-end/src/push/PushBanners.tsx`:

```tsx
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useTheme } from '@/design/theme';
import { radius, screenPadding, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { openPushSettings } from '@/push/gate';
import { usePushBanners } from '@/push/usePushBanners';

/**
 * 권한 거부 → Android 순으로 쌓는다. 데이터 지연 안내는 그 위에 봉투가 그린다(§12.7).
 */
export function PushBanners() {
  const { permissionDenied, android, dismiss } = usePushBanners();
  if (!permissionDenied && !android) return null;
  return (
    <View style={styles.list}>
      {permissionDenied && (
        <Banner
          message="알림 권한이 꺼져 있어 앱 안에서만 볼 수 있어요"
          actions={[
            { label: '설정 열기', accessibilityLabel: '설정 열기', onPress: openPushSettings },
            { label: '닫기', accessibilityLabel: '권한 안내 닫기', onPress: () => dismiss('permission') },
          ]}
        />
      )}
      {android && (
        <Banner
          message="Android에서는 앱 안에서만 알림을 확인할 수 있어요"
          actions={[{ label: '닫기', accessibilityLabel: 'Android 안내 닫기', onPress: () => dismiss('android') }]}
        />
      )}
    </View>
  );
}

function Banner({
  message,
  actions,
}: {
  message: string;
  actions: { label: string; accessibilityLabel: string; onPress: () => void }[];
}) {
  const palette = useTheme();
  return (
    <View style={[styles.banner, { backgroundColor: palette.warnBg }]}>
      <Text style={[type.caption, styles.message, { color: palette.warnText }]}>{message}</Text>
      {actions.map((action) => (
        <Pressable
          key={action.label}
          accessibilityRole="button"
          accessibilityLabel={action.accessibilityLabel}
          onPress={action.onPress}
          hitSlop={space.sm}
        >
          <Text style={[type.caption, styles.action, { color: palette.warnText }]}>{action.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { paddingHorizontal: screenPadding, paddingTop: space.sm },
  banner: {
    borderRadius: radius.button,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    marginBottom: space.xs,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
  },
  message: { flex: 1 },
  action: { fontWeight: '600' },
});
```

`front-end/src/push/InAppBanner.tsx`:

```tsx
import { useEffect, useRef } from 'react';
import { Pressable, StyleSheet, Text } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useTheme } from '@/design/theme';
import { radius, screenPadding, space } from '@/design/tokens';
import { type } from '@/design/typography';
import type { Arrival } from '@/push/pushInbox';

const SHOW_FOR = 5000;

/** 앱이 앞에 떠 있을 때 온 푸시. 화면을 옮기지 않고 위에 잠깐 띄운다. 누르면 울린 알림 상세(IA §4.2). */
export function InAppBanner({
  arrival,
  onPress,
  onDismiss,
}: {
  arrival: Arrival;
  onPress: () => void;
  onDismiss: () => void;
}) {
  const palette = useTheme();
  const insets = useSafeAreaInsets();
  const dismiss = useRef(onDismiss);
  dismiss.current = onDismiss;

  useEffect(() => {
    const timer = setTimeout(() => dismiss.current(), SHOW_FOR);
    return () => clearTimeout(timer);
  }, [arrival]);

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${arrival.title} 열기`}
      onPress={onPress}
      style={[styles.banner, { top: insets.top + space.sm, backgroundColor: palette.bg, borderColor: palette.border }]}
    >
      <Text style={[type.label, styles.title, { color: palette.text }]}>{arrival.title}</Text>
      <Text numberOfLines={2} style={[type.caption, { color: palette.textMuted }]}>
        {arrival.body}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  banner: {
    position: 'absolute',
    left: screenPadding,
    right: screenPadding,
    borderWidth: 1,
    borderRadius: radius.card,
    padding: space.md,
  },
  title: { fontWeight: '600' },
});
```

`front-end/src/push/PushRouter.tsx`:

```tsx
import { useCallback, useEffect, useState } from 'react';
import { useNavigation } from '@react-navigation/native';
import type { NavigationProp } from '@react-navigation/native';
import { useQueryClient } from '@tanstack/react-query';
import { AppState } from 'react-native';

import { invalidateAlertData } from '@/api/queries/alertInvalidation';
import { keys } from '@/api/queries/keys';
import type { RootStackParamList } from '@/app/navigation/types';
import { registerThisDevice } from '@/push/device';
import { InAppBanner } from '@/push/InAppBanner';
import { type Arrival, subscribeArrivals, subscribeOpens } from '@/push/pushInbox';

/**
 * 루트 스택 옆에 사는 푸시 처리. 루트 스택이 그려졌다는 것은 로그인했고 화면을 열 수 있다는 뜻이다.
 *
 * - 누른 푸시: 탭을 알림으로 바꾼 뒤 그 위에 울린 알림 상세를 쌓는다. 탭을 먼저 바꿔 두지 않으면
 *   뒤로 갈 때 직전 탭으로 돌아간다(IA §4.1). 로그인 전에 맡아 둔 것도 여기서 한 번 연다.
 * - 앞에 떠 있을 때 온 푸시: 화면을 옮기지 않고 앱 안 배너를 띄우고 배지를 다시 받는다.
 * - 앱이 앞으로 올 때 배지 수를 다시 받는다(IA §3).
 * - 앱이 켜질 때마다 기기를 다시 등록한다(§9.2).
 */
export function PushRouter() {
  const navigation = useNavigation<NavigationProp<RootStackParamList>>();
  const queryClient = useQueryClient();
  const [arrival, setArrival] = useState<Arrival | null>(null);

  // 위에 다른 화면(알림 상세·모달·다른 울린 알림)이 떠 있어도 탭 묶음까지 걷어낸 뒤 쌓는다.
  // v7의 navigate는 이름이 다르면 새로 쌓으므로 pop을 준다 — 없으면 탭 묶음이 두 벌이 된다.
  const open = useCallback(
    (eventId: string) => {
      navigation.navigate('tabs', { screen: 'alerts' }, { pop: true });
      navigation.navigate('alert-event', { eventId });
    },
    [navigation],
  );

  useEffect(() => subscribeOpens(open), [open]);

  useEffect(
    () =>
      subscribeArrivals((next) => {
        invalidateAlertData(queryClient);
        setArrival(next);
      }),
    [queryClient],
  );

  useEffect(() => {
    void registerThisDevice();
  }, []);

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') void queryClient.invalidateQueries({ queryKey: keys.unreadCount });
    });
    return () => subscription.remove();
  }, [queryClient]);

  const dismiss = useCallback(() => setArrival(null), []);

  if (!arrival) return null;
  return (
    <InAppBanner
      arrival={arrival}
      onDismiss={dismiss}
      onPress={() => {
        setArrival(null);
        open(arrival.eventId);
      }}
    />
  );
}
```

- [ ] **Step 7: 앱에 잇는다**

`app/navigation/RootStack.tsx` — `PushRouter`를 루트 스택 내비게이터 옆(화면 밖)에 둔다. 앱 안 배너가 어느 스택 화면·모달 위에서든 보여야 하고(IA §4.2), 루트 스택은 로그인한 뒤에만 그려지므로 "열 수 있는 때"와 같다. 파일 전체가 아래와 같아진다(Task 6·7·9가 더한 줄 포함).

```tsx
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import type { RootStackParamList } from '@/app/navigation/types';
import { Tabs } from '@/app/navigation/Tabs';
import { useTheme } from '@/design/theme';
import { PushRouter } from '@/push/PushRouter';
import { AlertEditorNavigator } from '@/screens/alertEditor/AlertEditorNavigator';
import { AlertDetailScreen } from '@/screens/alerts/AlertDetailScreen';
import { AlertEventScreen } from '@/screens/alerts/AlertEventScreen';
import { AlertEventsScreen } from '@/screens/alerts/AlertEventsScreen';
import { AssetChangeScreen } from '@/screens/assetChange/AssetChangeScreen';

const Stack = createNativeStackNavigator<RootStackParamList>();

/**
 * 탭 여섯과, 그 위에 얹히는 화면들.
 *
 * 자산 변화를 탭으로 두지 않는 것은 그 화면이 답하는 질문이 "지금 얼마인가"가 아니라
 * "요약에서 본 저 증감이 무엇이었나"이기 때문이다. 물음이 생긴 자리에서 들어가고
 * 뒤로 가기로 그 자리로 돌아가는 편이 짧다.
 *
 * 알림의 상세 화면들(알림 상세 · 울린 알림 · 울린 알림 상세)도 같은 이유로 스택이다.
 * 푸시로 열 때는 탭을 알림으로 바꾼 뒤 그 위에 쌓는다 — 뒤로 가면 알림 탭이다(IA §4.1).
 *
 * 푸시 처리(PushRouter)는 루트 스택 옆에 산다. 앱 안 배너가 어느 화면 위에서든 보이고,
 * 루트 스택이 그려졌다는 것이 로그인했다는 뜻이다.
 */
export function RootStack() {
  const palette = useTheme();

  return (
    <>
      <Stack.Navigator
        screenOptions={{
          headerTintColor: palette.text,
          headerStyle: { backgroundColor: palette.bg },
          contentStyle: { backgroundColor: palette.bg },
        }}
      >
        <Stack.Screen name="tabs" component={Tabs} options={{ headerShown: false }} />
        <Stack.Screen name="asset-change" component={AssetChangeScreen} options={{ title: '자산 변화' }} />
        <Stack.Screen name="alert" component={AlertDetailScreen} options={{ title: '알림 상세' }} />
        <Stack.Screen name="alert-events" component={AlertEventsScreen} options={{ title: '울린 알림' }} />
        <Stack.Screen name="alert-event" component={AlertEventScreen} options={{ title: '울린 알림' }} />
        <Stack.Screen
          name="alert-editor"
          component={AlertEditorNavigator}
          options={{ presentation: 'modal', headerShown: false }}
        />
      </Stack.Navigator>
      <PushRouter />
    </>
  );
}
```

`PushRouter`는 화면 밖이라 `useNavigation()`이 컨테이너(루트) 내비게이션을 돌려준다(React Navigation 7은 화면 밖에서 컨테이너를 돌려준다 — `@react-navigation/core/src/useNavigation.tsx`). 그래서 `navigate('tabs', …)` · `navigate('alert-event', …)`가 루트 스택에 바로 닿는다. 탭 묶음(`Tabs.tsx`)은 바꾸지 않는다.

`app/App.tsx` — import에 `useEffect`(`react`)와 `startNotificationListeners`(`@/push/notifications`)를 더하고 `App` 함수 첫 줄에 넣는다.

```tsx
export default function App() {
  // 푸시를 누른 것과 앞에 떠 있을 때 온 것을 받는다. 로그인 전에 누른 푸시도 여기서 받아 맡아 둔다.
  useEffect(() => startNotificationListeners(), []);
```

`auth/AuthContext.tsx`:

```ts
import { unregisterThisDevice } from '@/push/device';
import { discardPendingOpen } from '@/push/pushInbox';
```

`login`의 첫 줄을 바꾼다.

```ts
  const login = useCallback(async (nextEmail: string, password: string) => {
    let response: Awaited<ReturnType<typeof requestLogin>>;
    try {
      response = await requestLogin(nextEmail, password);
    } catch (error) {
      // 로그인 전에 누른 푸시는 로그인에 성공했을 때만 연다(IA §4.2).
      discardPendingOpen();
      throw error;
    }
    const { access_token, expires_at } = response;
```

`logout`을 바꾼다.

```ts
  // 공용 기기에서 로그아웃한 사람의 알림이 오면 안 된다. 토큰이 살아 있을 때 기기 등록을 지운다(§9.2).
  // 그 요청이 401을 받아도 "세션이 만료됐어요"가 아니라 그냥 로그아웃이다 — 그동안 만료 처리를 떼어 둔다.
  // 서버에 닿지 못하면 등록이 서버에 남는다. 다음 사람이 이 기기에서 로그인해 등록하면 그 사람에게 옮겨진다(§14.5).
  const logout = useCallback(() => {
    discardPendingOpen();
    setUnauthenticatedHandler(null);
    void unregisterThisDevice().finally(() => {
      endSession(false);
      setUnauthenticatedHandler(() => endSession(true));
    });
  }, [endSession]);
```

401로 밀려나는 경로(`setUnauthenticatedHandler`)는 기기를 지우지 않는다 — 토큰이 이미 죽어 서버가 받지 않는다. 같은 사람이 다시 로그인하면 등록이 그 사람에게 그대로 이어진다.

`screens/alerts/AlertsScreen.tsx` — `aboveContent`를 바꾼다. 권한 거부·Android 안내는 데이터 지연(봉투가 그림) 아래, 새로 울린 알림 위다.

```tsx
import { PushBanners } from '@/push/PushBanners';
```

```tsx
      aboveContent={
        <>
          <PushBanners />
          {data && (
            <UnreadBlock
              data={data}
              onOpenAll={openAllEvents}
              onOpenEvent={(eventId) => navigation.navigate('alert-event', { eventId })}
            />
          )}
        </>
      }
```

- [ ] **Step 8: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest && npx tsc --noEmit`
Expected: 전부 PASS. `Notifications.Notification`의 `content.data` 타입이 `Record<string, unknown>`이 아니라서 `event_id` 접근이 막히면 `(notification.request.content.data as Record<string, unknown> | undefined)?.event_id`로 읽는다.

- [ ] **Step 9: 커밋한다**

```bash
git add package.json package-lock.json jest.setup.js src/storage src/auth src/push src/app src/screens/alerts/AlertsScreen.tsx src/testing/notificationsMock.ts src/__tests__/push.test.tsx
git commit -m "feat: 푸시 권한·기기 등록과 푸시로 울린 알림 열기를 둔다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: 공통 설정과 저장 — 알림 방식 · 유효기간 · 이름 · 경고 · 권한 시트 · 저장 실패

**Files:**
- Create: `front-end/src/screens/alertEditor/SettingsStep.tsx`
- Modify: `front-end/src/screens/alertEditor/AlertEditorNavigator.tsx` (`settings` 등록)
- Test: `front-end/src/__tests__/alertSettings.test.tsx`

**Interfaces:**
- Consumes: `useEditor` · `useDraftPreview` · `openEditor` (Task 9), `draftToRequest` · `effectiveName` · `NAME_MAX` · `errorAt` · `errorsOutside` (Task 8), `createAlert` · `updateAlert` · `invalidateAlertData` (Task 3), `gateBeforeSave` · `allowPush` · `openPushSettings` (Task 12), `StepFooter` · `NumberField` (Task 10), `EXPIRY_CHOICES` · `ConfirmSheet` · `DateField` (Task 4)
- Produces: `<SettingsStep />`. 저장에 성공하면 `finish(alert_id)`를 불러 흐름을 닫는다(Task 9의 동작).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`front-end/src/__tests__/alertSettings.test.tsx`:

```tsx
import { Linking } from 'react-native';
import { fireEvent, screen, waitFor } from '@testing-library/react-native';

import type { AlertRequest } from '@/api/alertTypes';
import { setAccessToken } from '@/api/client';
import type { EditorInstrument } from '@/app/navigation/types';
import { presetDetailFixture, previewFixture } from '@/fixtures/alerts';
import { notificationState, resetNotifications } from '@/testing/notificationsMock';
import { openEditor } from '@/testing/openEditor';
import { storedItems } from '@/testing/secureStoreMock';
import type { Route } from '@/testing/serveRoutes';

jest.mock('expo-secure-store', () => require('@/testing/secureStoreMock'));
jest.mock('@/push/config', () => ({
  pushCapable: jest.fn(() => true),
  isAndroid: jest.fn(() => false),
  easProjectId: jest.fn(() => 'project-test'),
}));

const SAMSUNG: EditorInstrument = {
  id: '10000000-0000-0000-0000-000000000001', label: '삼성전자', market: 'KR', held: true, lastClose: 63010, lastCloseOn: '2026-09-25',
};

const preview = (body: unknown = previewFixture): Route => ({ method: 'POST', path: '/alerts/preview', body });
const created: Route = { method: 'POST', path: '/alerts', status: 201, body: { alert_id: 'a-new' } };
const device: Route = { method: 'POST', path: '/devices', body: { device_id: 'dev-1' } };

beforeEach(() => {
  setAccessToken('tok');
  resetNotifications();
  storedItems.clear();
  notificationState.permission = 'granted';
});
afterEach(() => setAccessToken(null));

/** 삼성전자 · 가격 도달까지 고르고 공통 설정으로 간다. */
async function toSettings(routes: Route[] = [preview(), created, device]) {
  const opened = await openEditor({ mode: 'new', instrument: SAMSUNG }, routes);
  await waitFor(() => expect(screen.getByText('가격 도달')).toBeTruthy());
  await fireEvent.press(screen.getByRole('button', { name: '가격 도달' }));
  await waitFor(() =>
    expect(screen.getByRole('button', { name: '다음' }).props.accessibilityState.disabled).toBe(false),
  );
  await fireEvent.press(screen.getByRole('button', { name: '다음' }));
  await waitFor(() => expect(screen.getByText('알림 방식')).toBeTruthy());
  return opened;
}

function savedBody(calls: Awaited<ReturnType<typeof openEditor>>['calls']): AlertRequest | undefined {
  return calls.find((c) => c.path === '/alerts' && (c.method === 'POST' || c.method === 'PUT'))?.body as
    | AlertRequest
    | undefined;
}

describe('공통 설정', () => {
  it('장중 알림은 세 가지 알림 방식, 다시 알림을 고르면 간격 칸', async () => {
    await toSettings();

    expect(screen.getByRole('radio', { name: '돌파할 때마다' }).props.accessibilityState.checked).toBe(true);
    expect(screen.getByRole('radio', { name: '한 번만' })).toBeTruthy();
    await fireEvent.press(screen.getByRole('radio', { name: 'N분마다 다시' }));
    expect(screen.getByLabelText('다시 알림 간격').props.value).toBe('60');
  });

  it('기본 이름과 이미 충족 중 경고', async () => {
    await toSettings();
    expect(screen.getByLabelText('알림 이름').props.value).toBe('삼성전자 가격 도달');
    await waitFor(() => expect(screen.getByText('지금 이미 조건을 충족하고 있어 곧 알림이 와요')).toBeTruthy());
  });

  it('같은 조건의 알림이 있으면 알린다 — 저장은 막지 않는다', async () => {
    await toSettings([preview({ ...previewFixture, already_satisfied: false, duplicate_of: 'a-other' }), created]);
    await waitFor(() => expect(screen.getByText('같은 조건의 알림이 이미 있어요')).toBeTruthy());
    expect(screen.getByRole('button', { name: '저장' }).props.accessibilityState.disabled).toBe(false);
  });

  it('저장하면 그 알림의 상세로 간다', async () => {
    const { calls, moves } = await toSettings();
    await fireEvent.press(screen.getByRole('radio', { name: '한 번만' }));
    await fireEvent.press(screen.getByRole('button', { name: '1주' }));

    await fireEvent.press(screen.getByRole('button', { name: '저장' }));

    await waitFor(() => expect(moves.at(-1)).toEqual({ name: 'alert', params: { alertId: 'a-new' } }));
    const body = savedBody(calls)!;
    expect(body.instrument_id).toBe(SAMSUNG.id);
    expect(body.name).toBe('삼성전자 가격 도달');
    expect(body.notify_mode).toBe('ONE_SHOT');
    expect(body.cooldown_min).toBeNull();
    expect(body.expires_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00$/);
    expect(body.trigger_spec).toEqual({ preset_key: 'price_reach', params: { direction: 'up', price: 63010 } });
    // 권한이 이미 있으면 시트 없이 저장한다.
    expect(screen.queryByText('울릴 때 바로 받으려면 알림을 허용해 주세요')).toBeNull();
  });

  it('검증 실패는 그 칸 아래에, 앞 단계의 칸은 모아서 보인다', async () => {
    await toSettings([
      preview(),
      {
        method: 'POST',
        path: '/alerts',
        status: 400,
        body: {
          error: {
            code: 'INVALID_ALERT',
            message: '조건을 확인해 주세요',
            fields: [
              { path: 'name', code: 'OUT_OF_RANGE', message: '이름은 40자까지예요' },
              { path: 'trigger_spec.params.price', code: 'REQUIRED', message: '가격을 입력해 주세요' },
            ],
          },
        },
      },
    ]);

    await fireEvent.press(screen.getByRole('button', { name: '저장' }));

    await waitFor(() => expect(screen.getByText('이름은 40자까지예요')).toBeTruthy());
    expect(screen.getByText('앞 단계의 조건을 확인해 주세요')).toBeTruthy();
    expect(screen.getByText('가격을 입력해 주세요')).toBeTruthy();
  });

  it('닿지 못하면 문구를 보이고 다시 누를 수 있다', async () => {
    await toSettings([preview()]);
    const realFetch = global.fetch;
    global.fetch = jest.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/alerts') && init?.method === 'POST') throw new TypeError('Network request failed');
      return realFetch(url, init);
    }) as unknown as typeof fetch;

    await fireEvent.press(screen.getByRole('button', { name: '저장' }));

    await waitFor(() => expect(screen.getByText('연결에 실패했어요. 잠시 후 다시 시도해 주세요')).toBeTruthy());
    expect(screen.getByRole('button', { name: '저장' }).props.accessibilityState.disabled).toBe(false);
  });
});

describe('저장 전 푸시 권한 (§12.7)', () => {
  it('권한이 정해지지 않았으면 안내 시트 → 허용하기 → 기기 등록 → 저장', async () => {
    notificationState.permission = 'undetermined';
    const { calls, moves } = await toSettings();

    await fireEvent.press(screen.getByRole('button', { name: '저장' }));
    await waitFor(() => expect(screen.getByText('울릴 때 바로 받으려면 알림을 허용해 주세요')).toBeTruthy());
    await fireEvent.press(screen.getByRole('button', { name: '허용하기' }));

    await waitFor(() => expect(moves.at(-1)?.name).toBe('alert'));
    expect(notificationState.requested).toBe(1);
    const order = calls.map((c) => `${c.method} ${c.path}`);
    expect(order.indexOf('POST /devices')).toBeLessThan(order.indexOf('POST /alerts'));
  });

  it('나중에를 눌러도 저장한다', async () => {
    notificationState.permission = 'undetermined';
    const { moves } = await toSettings();

    await fireEvent.press(screen.getByRole('button', { name: '저장' }));
    await waitFor(() => expect(screen.getByText('울릴 때 바로 받으려면 알림을 허용해 주세요')).toBeTruthy());
    await fireEvent.press(screen.getByRole('button', { name: '나중에' }));

    await waitFor(() => expect(moves.at(-1)?.name).toBe('alert'));
    expect(notificationState.requested).toBe(0);
  });

  it('거부 상태면 설정 열기 시트', async () => {
    notificationState.permission = 'denied';
    const openSettings = jest.spyOn(Linking, 'openSettings').mockResolvedValue(undefined);
    const { moves } = await toSettings();

    await fireEvent.press(screen.getByRole('button', { name: '저장' }));
    await waitFor(() => expect(screen.getByText('알림 권한이 꺼져 있어요')).toBeTruthy());
    await fireEvent.press(screen.getByRole('button', { name: '설정 열기' }));

    expect(openSettings).toHaveBeenCalled();
    await waitFor(() => expect(moves.at(-1)?.name).toBe('alert'));
  });
});

describe('수정 저장', () => {
  it('PUT으로 보내고 흐름을 닫아 들어온 자리로 돌아간다', async () => {
    const { calls, moves } = await openEditor({ mode: 'edit', alertId: 'a-satisfied' }, [
      { path: '/alerts/a-satisfied', body: presetDetailFixture },
      preview(),
      { method: 'PUT', path: '/alerts/a-satisfied', body: { alert_id: 'a-satisfied' } },
    ]);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: '다음' }).props.accessibilityState.disabled).toBe(false),
    );
    await fireEvent.press(screen.getByRole('button', { name: '다음' }));
    await waitFor(() => expect(screen.getByLabelText('알림 이름').props.value).toBe('삼성전자 7만원'));

    await fireEvent.press(screen.getByRole('button', { name: '저장' }));

    await waitFor(() => expect(moves.at(-1)?.name).toBe('__home'));
    const put = calls.find((c) => c.method === 'PUT');
    expect((put?.body as AlertRequest).trigger_spec).toEqual(presetDetailFixture.trigger_spec);
  });
});
```

- [ ] **Step 2: 테스트가 실패하는지 본다**

Run: `npx jest src/__tests__/alertSettings.test.tsx`
Expected: FAIL — `다음`을 눌러도 `settings` 단계가 없어 `알림 방식`을 찾지 못함.

- [ ] **Step 3: 화면을 쓴다**

`front-end/src/screens/alertEditor/SettingsStep.tsx`:

```tsx
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { createAlert, updateAlert } from '@/api/alertEndpoints';
import type { NotifyMode } from '@/api/alertTypes';
import { ApiError } from '@/api/client';
import { invalidateAlertData } from '@/api/queries/alertInvalidation';
import { useTheme } from '@/design/theme';
import { radius, screenPadding, size, space } from '@/design/tokens';
import { type } from '@/design/typography';
import { messageOf } from '@/envelope/ErrorState';
import { type GateSheet, allowPush, gateBeforeSave, openPushSettings } from '@/push/gate';
import { EXPIRY_CHOICES } from '@/screens/alerts/expiry';
import { NAME_MAX, draftToRequest, effectiveName } from '@/screens/alertEditor/draft';
import { useDraftPreview, useEditor } from '@/screens/alertEditor/EditorContext';
import { errorAt, errorsOutside } from '@/screens/alertEditor/fieldErrors';
import { NumberField } from '@/screens/alertEditor/NumberField';
import { StepFooter } from '@/screens/alertEditor/StepFooter';
import { Chip } from '@/ui/Chip';
import { ConfirmSheet } from '@/ui/ConfirmSheet';
import { DateField } from '@/ui/DateField';
import { todayIso } from '@/ui/period';
import { TextField } from '@/ui/TextField';

/** 이 화면이 칸 아래에 그리는 오류. 나머지는 앞 단계의 것이라 위에 모은다. */
const OWN = ['notify_mode', 'cooldown_min', 'expires_at', 'name'];

/**
 * 공통 설정 (§12.5.5) — 알림 방식 · 유효기간 · 이름, 그리고 저장.
 *
 * 저장 전에 OS 권한이 정해지지 않았으면 안내 시트, 거부 상태면 설정 열기 시트를 띄운다.
 * 어느 답을 골라도 저장은 한다 — 권한이 없어도 발화는 앱 안 목록과 배지로 남는다(§9.5).
 */
export function SettingsStep() {
  const { draft, dispatch, catalog, finish } = useEditor();
  const palette = useTheme();
  const queryClient = useQueryClient();
  const { preview } = useDraftPreview();
  const [sheet, setSheet] = useState<GateSheet>(null);

  const save = useMutation({
    mutationFn: async () => {
      const request = draftToRequest(draft, catalog, new Date());
      if (!request) throw new Error('종목과 조건을 먼저 골라 주세요');
      return draft.mode === 'edit' && draft.alertId ? updateAlert(draft.alertId, request) : createAlert(request);
    },
    onSuccess: ({ alert_id }) => {
      invalidateAlertData(queryClient);
      finish(alert_id);
    },
  });

  // 저장이 칸별 오류로 거절되면 그것을, 아니면 미리보기의 오류를 칸 아래에 둔다.
  const rejected = save.error instanceof ApiError && save.error.fields.length > 0 ? save.error.fields : null;
  const errors = rejected ?? preview?.errors ?? [];
  const elsewhere = errorsOutside(errors, OWN);
  const failure = save.error && !rejected ? messageOf(save.error) : null;

  const modes: { value: NotifyMode; label: string }[] = [
    { value: 'EDGE_REARM', label: '돌파할 때마다' },
    { value: 'ONE_SHOT', label: '한 번만' },
    // 종가 알림은 하루 한 번 평가되므로 분 단위 억제가 뜻이 없다(§6.2).
    ...(draft.cadence === 'INTRADAY' ? [{ value: 'COOLDOWN' as const, label: 'N분마다 다시' }] : []),
  ];

  const onSave = async () => {
    const next = await gateBeforeSave();
    if (next) setSheet(next);
    else save.mutate();
  };

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        {elsewhere.length > 0 && (
          <View style={[styles.box, { backgroundColor: palette.errorBg }]}>
            <Text style={[type.label, { color: palette.errorText }]}>앞 단계의 조건을 확인해 주세요</Text>
            {elsewhere.map((e) => (
              <Text key={e.path} style={[type.caption, { color: palette.errorText }]}>
                {e.message}
              </Text>
            ))}
          </View>
        )}

        <Text style={[type.label, styles.heading, { color: palette.text }]}>알림 방식</Text>
        {modes.map((mode) => (
          <Radio
            key={mode.value}
            label={mode.label}
            checked={draft.notifyMode === mode.value}
            onPress={() => dispatch({ type: 'notify-mode', mode: mode.value })}
          />
        ))}
        {draft.notifyMode === 'COOLDOWN' && (
          <NumberField
            label="간격"
            accessibilityLabel="다시 알림 간격"
            value={draft.cooldownMin}
            unit="분"
            error={errorAt(errors, 'cooldown_min')}
            onChange={(value) => dispatch({ type: 'cooldown', value })}
          />
        )}
        {errorAt(errors, 'notify_mode') && (
          <Text style={[type.caption, { color: palette.errorText }]}>{errorAt(errors, 'notify_mode')}</Text>
        )}

        <Text style={[type.label, styles.heading, { color: palette.text }]}>유효기간</Text>
        <View style={styles.chips}>
          {EXPIRY_CHOICES.map((choice) => (
            <Chip
              key={choice.value}
              label={choice.label}
              selected={draft.expiry === choice.value}
              onPress={() => dispatch({ type: 'expiry', choice: choice.value })}
            />
          ))}
        </View>
        {draft.expiry === 'DATE' && (
          <View style={styles.date}>
            <DateField
              label="만료 날짜"
              value={draft.expiryDate}
              min={todayIso()}
              onChange={(value) => dispatch({ type: 'expiry-date', value })}
            />
          </View>
        )}
        {errorAt(errors, 'expires_at') && (
          <Text style={[type.caption, { color: palette.errorText }]}>{errorAt(errors, 'expires_at')}</Text>
        )}

        <View style={styles.heading}>
          <TextField
            label="알림 이름"
            value={effectiveName(draft, catalog)}
            maxLength={NAME_MAX}
            error={errorAt(errors, 'name')}
            onChangeText={(value) => dispatch({ type: 'name', value })}
          />
        </View>

        {preview?.already_satisfied && <Warn text="지금 이미 조건을 충족하고 있어 곧 알림이 와요" />}
        {preview?.duplicate_of && <Warn text="같은 조건의 알림이 이미 있어요" />}
        {failure && <Text style={[type.caption, styles.failure, { color: palette.errorText }]}>{failure}</Text>}
      </ScrollView>

      <StepFooter label="저장" loading={save.isPending} onPress={() => void onSave()} />

      <ConfirmSheet
        visible={sheet === 'ask'}
        title="울릴 때 바로 받으려면 알림을 허용해 주세요"
        confirmLabel="허용하기"
        cancelLabel="나중에"
        onConfirm={() => {
          setSheet(null);
          void allowPush().finally(() => save.mutate());
        }}
        onCancel={() => {
          setSheet(null);
          save.mutate();
        }}
      />
      <ConfirmSheet
        visible={sheet === 'settings'}
        title="알림 권한이 꺼져 있어요"
        confirmLabel="설정 열기"
        cancelLabel="나중에"
        onConfirm={() => {
          setSheet(null);
          openPushSettings();
          save.mutate();
        }}
        onCancel={() => {
          setSheet(null);
          save.mutate();
        }}
      />
    </View>
  );
}

function Radio({ label, checked, onPress }: { label: string; checked: boolean; onPress: () => void }) {
  const palette = useTheme();
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityLabel={label}
      accessibilityState={{ checked }}
      onPress={onPress}
      style={styles.radio}
    >
      <View style={[styles.dot, { borderColor: checked ? palette.primary : palette.border }]}>
        {checked && <View style={[styles.dotInner, { backgroundColor: palette.primary }]} />}
      </View>
      <Text style={[type.body, { color: palette.text }]}>{label}</Text>
    </Pressable>
  );
}

function Warn({ text }: { text: string }) {
  const palette = useTheme();
  return (
    <View style={[styles.box, { backgroundColor: palette.warnBg }]}>
      <Text style={[type.caption, { color: palette.warnText }]}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: { paddingHorizontal: screenPadding, paddingVertical: space.lg },
  heading: { marginTop: space.lg },
  radio: { minHeight: size.tap, flexDirection: 'row', alignItems: 'center', gap: space.sm },
  dot: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  dotInner: { width: 10, height: 10, borderRadius: 5 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, marginTop: space.sm },
  date: { flexDirection: 'row', marginTop: space.md },
  box: { borderRadius: radius.button, padding: space.md, marginTop: space.md, gap: space.xs },
  failure: { marginTop: space.md },
});
```

- [ ] **Step 4: 흐름에 등록한다**

`AlertEditorNavigator.tsx`:

```tsx
import { SettingsStep } from '@/screens/alertEditor/SettingsStep';
```

```tsx
        <Stack.Screen name="settings" component={SettingsStep} options={{ title: '공통 설정' }} />
```

- [ ] **Step 5: 테스트와 타입 검사가 통과하는지 본다**

Run: `npx jest && npx tsc --noEmit`
Expected: 전부 PASS.

- [ ] **Step 6: 커밋한다**

```bash
git add src/screens/alertEditor src/__tests__/alertSettings.test.tsx
git commit -m "feat: 공통 설정을 고르고 권한을 안내한 뒤 알림을 저장한다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 14: README · 실제 서버 대조 · 브라우저 확인 · iOS 실기기 확인 목록

**Files:**
- Modify: `front-end/README.md`
- Create: `front-end/scripts/compare-alert-shapes.mjs` (응답 모양 대조. 키만 비교하고 값은 남기지 않는다)
- Create: `front-end/scripts/alert-fixture-keys.json` (아래 테스트가 픽스처에서 뽑아 적는다)
- Test: `front-end/src/__tests__/fixtureKeys.test.ts`

**Interfaces:**
- Consumes: 앞 태스크 전부
- Produces: README의 알림 절, 대조 스크립트, 사용자에게 넘기는 실기기 확인 목록

- [ ] **Step 1: README를 고친다**

머리 문단을 지금 앱에 맞게 바꾼다(여섯 탭 · 알림). 기존 문장 구조와 말투를 따른다.

```markdown
# front-end

포트폴리오 종합 관리와 매수·매도 타이밍 알림 — 프론트엔드

아래 탭은 여섯 개다 — 요약 · 종목 · 비중 · 계좌 · 손익 · 알림.
포트폴리오 다섯 탭과 그 위의 자산 변화는 백엔드 조회 계층의 실제 응답으로 동작한다.
알림 탭에서는 내 알림과 새로 울린 알림을 보고, `＋ 새 알림`으로 종목 → 조건 → 공통 설정을 거쳐 알림을 만든다.
```

`설계 스펙` · `구현 계획` 줄에 알림 문서를 더한다.

```markdown
- **설계 스펙**: [docs 저장소](https://github.com/stock-project-crew/docs) `yhr/specs/portfolio-management/2026-07-28-portfolio-management-spec.md` · `yhr/specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md` · `yhr/specs/app-information-architecture.md`
- **구현 계획**: 같은 저장소 `yhr/plan/2026-08-17-frontend-portfolio-app-plan.md` · `yhr/plan/2026-08-30-frontend-remaining-views-plan.md` · `yhr/plan/2026-10-11-frontend-alert-plan.md`
```

`스택` 절의 라이브러리 줄에 `expo-notifications · expo-constants`를 더한다.

`검사` 절 아래에 절을 더한다.

~~~markdown
## 알림 푸시

원격 푸시는 iOS만 받는다. Expo Go는 SDK 53부터 Android에서 원격 푸시를 지원하지 않는다.
Android에서는 울린 알림을 앱 안 목록과 탭 배지로만 보고, 알림 탭에 그 안내가 뜬다.

푸시 토큰을 받으려면 EAS 프로젝트 ID가 `app.json`의 `extra.eas.projectId`에 있어야 한다.
없으면 앱은 기기를 등록하지 않고, 나머지는 그대로 동작한다.

```bash
npx eas-cli@latest login
npx eas-cli@latest init      # app.json에 extra.eas.projectId를 넣는다
```

권한은 첫 알림을 저장할 때 묻는다. 로그인 직후에는 묻지 않는다.
푸시를 누르면 알림 탭 위에 울린 알림 상세가 열리고, 뒤로 가면 알림 탭이다.

울린 알림 목록·상세·배지는 백엔드의 울린 알림 API(`/alert-events`)가 있어야 채워진다.
그 경로가 없는 서버에서는 배지가 뜨지 않을 뿐 나머지 화면은 그대로다.
~~~

`구조` 절의 트리에 `push/`와 `storage/`를 더하고 `screens/` 줄에 `alerts · alertEditor`를 더한다.

```
├── push/         푸시 권한 · 기기 등록 · 푸시를 눌렀을 때 여는 곳
├── storage/      앱을 껐다 켜도 남는 작은 값의 자리 (토큰 · 기기 ID · 닫은 배너)
```

- [ ] **Step 2: 응답 모양 대조 스크립트를 쓴다**

픽스처가 실제 서버와 같은 모양인지 키로만 대조한다. 값은 출력하지 않는다 — 계좌·종목 정보가 로그에 남지 않게 한다. 토큰은 환경 변수로 받고 파일에 쓰지 않는다.

`front-end/scripts/compare-alert-shapes.mjs`:

```js
// 실제 서버 응답과 테스트 픽스처의 키 모양을 견준다. 값은 출력하지 않는다.
// 쓰는 법: API=http://localhost:8080 TOKEN=… node scripts/compare-alert-shapes.mjs
// 픽스처 쪽 키 목록은 같은 이름의 JSON(scripts/alert-fixture-keys.json)에서 읽는다.

const api = process.env.API;
const token = process.env.TOKEN;
if (!api || !token) {
  console.error('API와 TOKEN 환경 변수가 필요하다');
  process.exit(2);
}

/** 객체의 키 경로를 모은다. 배열은 첫 원소만 본다. */
function shape(value, prefix = '') {
  if (Array.isArray(value)) return value.length === 0 ? [`${prefix}[]`] : shape(value[0], `${prefix}[]`);
  if (value === null || typeof value !== 'object') return [prefix];
  return Object.keys(value).flatMap((key) => shape(value[key], prefix ? `${prefix}.${key}` : key));
}

async function get(path, init) {
  const response = await fetch(`${api}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  return { status: response.status, body: await response.json().catch(() => null) };
}

const expected = JSON.parse(await (await import('node:fs/promises')).readFile(new URL('./alert-fixture-keys.json', import.meta.url), 'utf8'));
let failed = false;
for (const [name, request] of Object.entries(expected.requests)) {
  const { status, body } = await get(request.path, request.init);
  const actualKeys = shape(body);
  const actual = new Set(actualKeys);
  // 서버 쪽 배열이 비었으면 그 원소의 키는 견줄 수 없다. 모자란 키로 세지 않고 따로 알린다.
  const emptyArrays = actualKeys.filter((key) => key.endsWith('[]'));
  const unchecked = expected.keys[name].filter((key) => emptyArrays.some((prefix) => key.startsWith(`${prefix}.`)));
  const missing = expected.keys[name].filter((key) => !actual.has(key) && !unchecked.includes(key));
  console.log(`${name}: HTTP ${status}, 픽스처에만 있는 키 ${missing.length}개, 빈 배열이라 견주지 못한 키 ${unchecked.length}개`);
  for (const key of missing) console.log(`  - ${key}`);
  for (const prefix of new Set(unchecked.map((key) => key.slice(0, key.indexOf('[]') + 2)))) console.log(`  (빈 배열) ${prefix}`);
  if (missing.length > 0) failed = true;
}
process.exit(failed ? 1 : 0);
```

키 목록 `front-end/scripts/alert-fixture-keys.json`은 손으로 쓰지 않고 픽스처에서 뽑는다. 한 번만 돌리는 jest 테스트로 만든다 — `src/__tests__/fixtureKeys.test.ts`:

```ts
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  alertsFixture,
  catalogFixture,
  instrumentsFixture,
  presetDetailFixture,
  previewFixture,
} from '@/fixtures/alerts';

/** 픽스처의 키 모양을 scripts/alert-fixture-keys.json으로 적는다. 실제 서버 대조(Task 14)가 읽는다. */
function shape(value: unknown, prefix = ''): string[] {
  if (Array.isArray(value)) return value.length === 0 ? [`${prefix}[]`] : shape(value[0], `${prefix}[]`);
  if (value === null || typeof value !== 'object') return [prefix];
  return Object.keys(value).flatMap((key) =>
    shape((value as Record<string, unknown>)[key], prefix ? `${prefix}.${key}` : key),
  );
}

// 저장소의 파일을 쓰므로 평소 `npm test`에서는 건너뛴다. 대조 전에 `WRITE_FIXTURE_KEYS=1`로 한 번 돌린다.
const writeKeys = process.env.WRITE_FIXTURE_KEYS === '1' ? it : it.skip;

writeKeys('픽스처 키 목록을 적는다', () => {
  const previewBody = {
    instrument_id: '10000000-0000-0000-0000-000000000001',
    name: '대조',
    cadence: 'INTRADAY',
    notify_mode: 'EDGE_REARM',
    cooldown_min: null,
    expires_at: null,
    trigger_type: 'PRESET',
    trigger_spec: { preset_key: 'price_reach', params: { direction: 'up', price: 63010 } },
  };
  const out = {
    requests: {
      alerts: { path: '/alerts' },
      catalog: { path: '/alerts/catalog' },
      instruments: { path: `/instruments?q=${encodeURIComponent('삼성')}` },
      preview: { path: '/alerts/preview', init: { method: 'POST', body: JSON.stringify(previewBody) } },
    },
    keys: {
      alerts: shape(alertsFixture).filter((k) => !k.startsWith('data.unread') && !k.startsWith('notices')),
      catalog: shape(catalogFixture),
      instruments: shape(instrumentsFixture),
      preview: shape(previewFixture),
    },
    detail: shape(presetDetailFixture),
  };
  writeFileSync(join(__dirname, '../../scripts/alert-fixture-keys.json'), `${JSON.stringify(out, null, 2)}\n`);
  expect(out.keys.catalog.length).toBeGreaterThan(0);
});
```

`unread`와 `notices`는 계획 ②가 채우는 자리라 ①만 있는 서버에서는 빈 배열이다 — 대조에서 뺀다.

키 목록을 만든다.

```bash
WRITE_FIXTURE_KEYS=1 npx jest src/__tests__/fixtureKeys.test.ts
git diff --stat scripts/alert-fixture-keys.json
```

- [ ] **Step 3: 정적 검사를 돌린다**

Run: `npx tsc --noEmit && npm test`
Expected: 전부 PASS. 테스트 수와 소요 시간을 보고에 적는다.

- [ ] **Step 4: ⛔ 승인 — 로컬 서버 기동과 대조**

사용자에게 묻는다: "로컬에서 DB와 백엔드를 띄워 실제 응답과 대조하고 브라우저로 화면을 확인할까요? `back-end` 원래 경로는 계획 ② 세션이 쓰고 있으니, 띄우는 것은 Task 0의 worktree(`back-end-last-close`)에서 하겠습니다. DB 컨테이너가 이미 떠 있으면 그것을 씁니다. 샘플 데이터 적재(`sample_alert_market.sql`)는 DB 쓰기라 따로 묻겠습니다."

승인을 받으면:

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project/back-end-last-close
docker compose ps                     # db가 이미 떠 있는지 본다
./gradlew bootRun --args='--spring.profiles.active=local'    # run_in_background
```

토큰은 로그인 응답에서 받아 셸 변수로만 쓴다. 파일·커밋에 남기지 않는다.

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"yhr@a.com","password":"local-dev-password"}' | node -e 'process.stdin.on("data",d=>console.log(JSON.parse(d).access_token))')
cd /Users/yhr/Dev/workspace/personal/stock-project/front-end
API=http://localhost:8080 TOKEN="$TOKEN" node scripts/compare-alert-shapes.mjs
```

Expected: 네 요청 모두 `픽스처에만 있는 키 0개`. 키가 모자라면 픽스처를 실제 모양에 맞추고(앱 타입도 함께), 고친 이유를 커밋 메시지에 적는다. `instruments`의 `last_close` 두 키는 Task 0이 반영되지 않은 서버라면 모자라는 것이 맞다 — 그 경우 그렇게 보고한다.

샘플 DB에는 사용자 알림이 없어(`sample_alert_market.sql`이 `alert`를 비운다) `/alerts`의 `data.rows[]`가 빈 배열로 온다. 그 원소의 키는 `빈 배열이라 견주지 못한 키`로 따로 나온다. 카드 행까지 견주려면 브라우저 확인(Step 5)에서 알림을 하나 만든 뒤(그 자체가 앱의 DB 쓰기다) 이 스크립트를 한 번 더 돌린다.

- [ ] **Step 5: ⛔ 승인 — 브라우저 확인**

`claude-in-chrome` 스킬을 따른다. 사용자에게 Expo 웹 서버(`npx expo start --web`, 포트 8081) 기동 승인을 받는다. 새 탭에서 `http://localhost:8081`을 열고 A.1 도달점 1~12를 차례로 확인한다. 각 항목의 결과(됨 / 안 됨 + 본 것)를 표로 보고한다. 13·14는 계획 ② 이후 항목이라 "확인 불가 — ② 미병합"으로 적는다. 확인이 끝나면 띄운 서버를 내린다.

- [ ] **Step 6: 사용자에게 넘기는 iOS 실기기 확인 목록**

실기기 확인은 사용자가 한다. 아래를 그대로 전달한다.

```
준비
  1. `! npx eas-cli@latest login` → `! npx eas-cli@latest init` (app.json에 projectId가 들어간다. 이 변경은 커밋해도 된다 — 비밀이 아니다)
  2. .env의 EXPO_PUBLIC_API_BASE_URL이 개발 머신 LAN IP인지 확인
  3. `npx expo start` → iPhone Expo Go로 QR

확인
  [ ] 아래 탭이 여섯 개이고 한 줄에 들어간다 (글자가 잘리지 않는다)
  [ ] 알림 탭 → ＋ 새 알림 → 삼성 검색 → 삼성전자 → 가격 도달 → 가격 칸이 직전 종가로 채워져 있다
  [ ] 가격을 고치면 0.5초 뒤 문장·현재값이 바뀐다 (자판이 숫자·구두점이고 빼기를 칠 수 있다)
  [ ] 다음 → 저장 → "울릴 때 바로 받으려면 알림을 허용해 주세요" → 허용하기 → 시스템 권한 창 → 허용
  [ ] 저장 뒤 알림 상세가 열리고, 뒤로 가면 알림 탭이다
  [ ] 수정 → 값이 채워져 있다 → 저장 → 알림 상세로 돌아온다
  [ ] 작성 중에 모달을 아래로 쓸어내리면 "작성 중인 알림을 버릴까요?"가 뜬다
  [ ] 설정 앱에서 알림 권한을 끄고 돌아오면 알림 탭 위에 권한 거부 배너가 뜬다, 닫으면 다시 안 뜬다
  [ ] 날짜 지정 유효기간에서 시스템 날짜 피커가 뜨고 오늘 이전은 고를 수 없다
(계획 ② 이후)
  [ ] 조건을 충족시키면 잠금 화면에 푸시가 오고 본문에 계좌 정보가 없다
  [ ] 앱을 완전히 끈 상태에서 푸시를 누르면 알림 탭 위에 울린 알림 상세가 열린다
  [ ] 앱이 앞에 있을 때 푸시가 오면 화면이 옮겨지지 않고 위에 배너가 뜬다
  [ ] 탭 배지 숫자가 보라색이다
```

- [ ] **Step 7: 커밋한다**

```bash
git add README.md scripts src/__tests__/fixtureKeys.test.ts
git commit -m "docs: 알림 탭과 푸시 준비를 README에 적고 응답 모양 대조를 둔다" \
           -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 8: ⛔ 승인 — 브랜치 마무리**

`superpowers:finishing-a-development-branch`를 따른다. 병합·푸시·PR은 사용자가 고른 방식으로, 승인을 받은 뒤에만 한다. Task 0의 백엔드 브랜치 병합 여부(Step 9)와 계획 ②에 넘길 요청(A.3)을 함께 다시 알린다.

---

# Part C — 스펙 대응표

| 스펙 · IA | 태스크 |
|---|---|
| §11.1 엔드포인트 전부 | 3 |
| §11.2 봉투 재사용 · `as_of` null · `NO_ALERTS`/`NO_EVENTS` · `MARKET_DATA_DELAYED` | 2 · 5 · 7 |
| §11.3 미리보기 200 + errors · 저장 400 fields | 1 · 3 · 10 · 11 · 13 |
| §11.4 404 같은 응답 | 6 · 7 |
| §12.1 서버 문장 그대로 | 5 · 6 · 7 · 10 · 11 |
| §12.2 카드 · 정렬(서버) · 토글/다시 켜기 · 블록 3건 + 외 N건 | 5 |
| §12.3 울린 알림 · 상세 · 모두 읽음 · 삭제된 알림 | 7 |
| §12.4 알림 상세 · 현재값 상자(alert_id) · 삭제 확인 · 수정 | 6 · 9 |
| §12.5 닫을 때 확인 · 수정 시 종목·종류 고정 | 9 |
| §12.5.1 종목 선택 0.3초 · 보유 구역 · 배지 | 9 |
| §12.5.2 조건 선택 · 비활성 + 사유 | 9 |
| §12.5.3 프리셋 입력 · 직전 종가 · 장중 기본 · 종가 한 줄 | 0 · 8 · 10 |
| §12.5.4 조건 만들기 · 시트 · 변형 · 기준값 · 유지 · 5개 · 전환 확인 | 8 · 11 |
| §12.5.5 공통 설정 · 경고 · 권한 시트 | 13 |
| §12.6 표시 규칙 · 배지 전용색 · 상태 배지색 | 4 · 5 |
| §12.7 문구 전부 · 배너 순서 · 닫음 | 2 · 5 · 6 · 12 · 13 |
| §12.8 현재값 갱신 시점 | 3 · 6 · 10 |
| §15 화면 상태 전수 | 5 · 6 · 7 · 9 · 10 · 11 · 13 |
| §9.2 권한 · 등록 · 재등록 · 로그아웃 해제 | 12 |
| §9.6 iOS만 · Android 안내 | 12 |
| IA §2.1 여섯 탭 · §2.2 화면과 진입 · §3 배지 · §4 푸시 · §5 첫 화면(요약 그대로) | 5 · 6 · 7 · 9 · 12 |
| IA §2.5 종목 상세 `알림 걸기` | 범위 밖 — 종목 상세 화면이 아직 없다. 흐름은 `EditorStart.instrument`로 종목이 정해진 시작을 받는다(5 · 9) |
