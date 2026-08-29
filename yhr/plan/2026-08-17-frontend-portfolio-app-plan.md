# 포트폴리오 종합 관리 — 프론트엔드 구현 계획 (1차: 로그인 · 요약 · 종목별)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

- **작성일**: 2026-08-17
- **대상 저장소**: `front-end/` (github.com/stock-project-crew/front-end)
- **근거 스펙**: [`2026-07-28-portfolio-management-spec.md`](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) · [와이어플로우](../specs/portfolio-management/wireflow.png)
- **참고 계획**: [백엔드 조회 계층 계획](./2026-08-09-portfolio-query-layer-plan.md)
- **스펙 수정 금지**: 이 계획은 스펙을 인용만 한다. 스펙 파일을 고치지 않는다.
- **백엔드 수정 금지**: `back-end/`는 완료된 저장소다. CORS 등 서버 변경이 필요하면 코드를 고치지 말고 요청 사항으로 남긴다.

**Goal:** 실기기 Expo Go에서 로그인해 **요약**과 **종목별** 두 화면이 실제 백엔드 응답으로 동작한다. 토큰은 Keychain/Keystore에 저장되어 앱을 껐다 켜도 유지되고, 만료되면 로그인으로 되돌아온다. 필터·정렬·렌즈 전환이 서버 재조회로 이어지고, 빈 상태·경고·로딩이 화면마다 같은 모양으로 나온다.

**Architecture:** 6개 뷰가 **같은 응답 봉투**(`as_of` · `data` · `empty_reason` · `notices`)를 쓴다는 사실이 이 앱 구조의 축이다. 봉투를 다루는 층(배너 · 경고 · 빈 상태 · 로딩)을 화면 바깥에 한 번만 만들고, 화면은 `data`만 그린다. 서버 상태는 TanStack Query가 캐시하고, 클라이언트 상태는 인증 컨텍스트 하나뿐이며, 필터·정렬·렌즈는 화면 로컬 상태로 두고 쿼리 키에 실린다.

**Tech Stack:** React Native 0.81.5 · Expo SDK 54 · React 19.1 · TypeScript 5.9 (strict) · React Navigation · TanStack Query v5 · expo-secure-store · Jest(jest-expo) + React Native Testing Library

---

## Global Constraints

이 절의 규칙은 모든 태스크의 요구사항에 암묵적으로 포함된다.

- **Expo SDK 54를 올리지 않는다.** App Store 판 Expo Go가 54에서 멈춰 있어 그 위로 올리면 실기기가 앱을 거부한다. 패키지 설치는 항상 `npx expo install`을 쓴다 — SDK에 맞는 버전을 골라준다.
- **TypeScript strict.** `any`를 쓰지 않는다. API 응답 타입은 `src/api/types.ts` 한 곳에 정의하고 화면이 그 타입만 본다.
- **서버 문구를 그대로 출력한다.** `notices[].message`와 `error.message`는 클라이언트가 다시 쓰지 않는다. `code`로 아이콘·색·후속 동작만 분기한다(스펙 §8.2). 클라이언트가 만드는 문구는 §A.5.4의 목록이 전부다.
- **비율을 클라이언트가 계산하지 않는다.** 손익률·비중은 서버가 준 값을 그대로 쓴다(스펙 §1.5 · §3.2). 금액 뺄셈(`closing − opening`)만 예외로 허용한다 — 가산 가능한 값이다.
- **금액을 자르지 않는다.** 폭이 모자라면 종목명이 줄어들고, 숫자는 어떤 경우에도 말줄임하지 않는다.
- **화면은 `empty_reason`·`notices`·로딩·에러 네 상태를 직접 구현하지 않는다.** §B의 `envelope/` 컴포넌트에 위임한다.
- **하드코딩 금지 목록**: 필터 선택지 · 축 목록 · 렌즈 허용 여부. 전부 `GET /portfolio/catalog`가 내린다(스펙 §6.4).
- **커밋은 Conventional Commits**(`feat:` · `fix:` · `test:` · `chore:` · `docs:`), 태스크마다 1커밋.
- **머신 상태를 바꾸는 작업은 계획에 적힌 것만 한다.** 패키지 설치는 Task 1의 목록이 전부이고, 그 밖의 설치·SDK 변경·시뮬레이터 설치는 하지 않는다.

---

# Part A — 배경 (이 계획만 읽고 구현할 수 있게 옮겨 담은 것)

## A.1 도달점과 범위

**도달점.** 실기기 Expo Go에서 아래가 순서대로 된다.

```
1. 앱 실행 → 로그인 화면
2. yhr@a.com / local-dev-password 로 로그인 → 요약 화면
3. 요약: 총자산 58,000,000원 · 평가손익 +4,500,000 (+9.2%) · 타일 4개 ·
         이번 달 자산 +1,200,000원 · 자산 구성 막대(국내 80.7 / 미국 19.3)
4. 종목 탭 → 8행(종목 6 + 예수금 2)이 2줄 카드로 표시
5. 필터에서 미국만 선택 → 3행으로 줄고 합계도 함께 줄어든다
6. 정렬을 손익률순으로 바꾸면 순서가 바뀌고 예수금 행이 끝으로 간다
7. 렌즈 토글 ON → 2줄이 환산수량만 남고 시장·자산군 필터가 비활성된다
8. 앱을 강제 종료 후 재실행 → 로그인 화면 없이 요약으로 진입
9. SecureStore의 만료 시각을 지난 값으로 바꾸면 로그인 화면으로 돌아온다
```

**이번 범위는 화면 3개다.** 비중 분석 · 계좌별 · 실현손익 · 자산 변화 네 화면은 설계 논의가 끝난 뒤 이 문서에 단계를 덧붙인다. 다만 **자산 변화 API는 이번에 호출한다** — 요약의 `이번 달 자산` 금액이 거기서 온다.

| 화면 ID | 화면명 | 이번 범위 |
|---|---|---|
| `login` | 로그인 | ○ |
| `summary` | 요약 | ○ |
| `positions` | 종목별 | ○ |
| `allocation` | 비중 분석 | 탭 자리만 (준비 중 문구) |
| `accounts` | 계좌별 | 탭 자리만 |
| `realized-pnl` | 실현손익 | 탭 자리만 |
| `asset-change` | 자산 변화 | API만 호출, 화면은 다음 단계 |
| `instrument-detail` · `link-*` · `sync` | 종목 상세 · 계좌 연동 · 동기화 | ✕ 범위 밖 |

**범위 밖인 이유**: 종목 상세는 백엔드 API가 없고(`cln_trade`·`position_basis`·`corporate_action` 미확보), 계좌 연동 4화면은 `collection_run` 계약과 시크릿 관리가 팀 미합의이며, 회원가입·비밀번호 재설정은 사용자 행을 마이그레이션이 심으므로 경로 자체가 없다(스펙 §12).

**스파이크 산출물 `App.tsx`는 Task 1에서 삭제한다.** 툴체인 검증용이었고 `src/`가 그 자리를 대신한다.

## A.2 기술 선택과 근거

### A.2.1 네비게이션 — **React Navigation**

| 후보 | 판단 |
|---|---|
| **React Navigation** (`@react-navigation/native` + `native-stack` + `bottom-tabs`) | 채택 |
| Expo Router | 기각 |

Expo Router는 파일 경로가 곧 라우트인 방식이라 딥링크·웹 URL이 중요할 때 값을 한다. 이 앱은 **딥링크 요구가 없다** — 외부에서 특정 화면으로 들어올 경로가 없고, 브라우저는 개발 중에 화면을 보는 용도라 URL을 공유하거나 특정 화면으로 바로 들어갈 일이 없다(§A.7). 반면 이 앱의 루트는 `인증됨 ? 탭 : 로그인` 조건 분기 하나인데, React Navigation에서는 컴포넌트 조건부 렌더 한 줄이고 Expo Router에서는 라우트 그룹과 리다이렉트 규칙이 된다. 얻는 게 없는 쪽에 복잡도를 쓰지 않는다.

### A.2.2 서버 상태 — **TanStack Query v5**

6개 뷰가 전부 `GET` + 같은 봉투다. 화면마다 필요한 것이 로딩·에러·재조회·캐시로 동일하다.

| 후보 | 기각 사유 |
|---|---|
| `useEffect` + `useState` 직접 | 화면마다 로딩·에러·중복요청·재조회를 다시 짠다. 3화면에서 이미 세 벌이 생기고, 필터가 바뀔 때의 경합(늦게 도착한 이전 응답이 화면을 덮어쓰는 것) 처리를 각자 하게 된다 |
| Redux Toolkit Query | 스토어·슬라이스·프로바이더가 붙는데 **정작 전역 클라이언트 상태가 인증 하나뿐**이라 스토어의 나머지가 비어 있다 |
| SWR | RN에서 동작하지만 재시도·무효화 정책이 얕아 401 전역 처리와 필터 전환 시 이전 데이터 유지를 직접 짜야 한다 |

TanStack Query가 이 계획에서 실제로 쓰는 기능은 넷이다 — **쿼리 키로 필터 상태 반영**, `placeholderData`로 필터 전환 시 이전 값 유지(빈 화면 깜빡임 방지), `staleTime`으로 탭 전환 시 불필요한 재요청 억제, `refetch()`로 배너 새로고침. 그 이상은 쓰지 않는다.

### A.2.3 클라이언트 상태 — **Context 하나 + 화면 로컬 상태**

- **인증**: `AuthContext` — 토큰·만료시각·로그인/로그아웃 함수. 앱 전체가 본다.
- **필터·정렬·렌즈**: 화면 로컬 `useState`. 화면을 떠나면 사라지는 게 맞는 상태다.
- Zustand·Jotai·Redux를 넣지 않는다. 공유해야 할 클라이언트 상태가 인증뿐이다.

### A.2.4 스타일 — **StyleSheet + 토큰 객체**

NativeWind(Tailwind)를 기각한다. Babel 플러그인과 메트로 설정이 붙고 Expo Go에서 SDK 버전에 민감하다. 화면 3개에 그 체인을 들이는 대신, `src/design/tokens.ts`에서 값을 읽어 `StyleSheet.create`로 쓴다. 다크모드를 나중에 열 때 바뀌는 것은 토큰 파일 하나다(§A.5.6).

### A.2.5 차트 — **이번 범위에는 차트 라이브러리를 쓰지 않는다**

요약의 자산 구성은 100% 누적 막대이고, 이는 `flex` 비율을 준 `View` 두 개다. `react-native-gifted-charts`는 비중 분석 화면의 도넛에서 처음 쓰이고, `react-native-svg` 직접 사용은 자산 변화의 워터폴에서 시작한다. 둘 다 다음 단계다. **패키지는 이미 설치돼 있으므로 제거하지 않고 두되, 이번 태스크에서 import 하지 않는다.**

### A.2.6 테스트 — **jest-expo + React Native Testing Library**

두 종류만 쓴다.

1. **순수 함수 단위 테스트** — 포맷터, 정렬, notice 분류, 쿼리 키 조립. 값이 바로 있고 회귀가 잦은 자리다.
2. **골든 픽스처 렌더 테스트** — `back-end/src/test/resources/golden/*.json`을 복사해 넣고, 그 응답으로 화면이 예외 없이 렌더되며 핵심 숫자가 화면에 나타나는지 확인한다. 백엔드를 띄우지 않고도 8행 렌더·null 처리·빈 상태가 검증된다.

E2E(Detox·Maestro)는 넣지 않는다. 실기기 확인이 §A.1 도달점의 검증 수단이다.

## A.3 화면 사양

### A.3.1 `login` — 로그인

```
┌─────────────────────────────────────┐
│                                     │  상단 여백 = 화면 높이 × 0.15
│   로그인                             │  Title 20
│                                     │
│  ┌───────────────────────────────┐  │  ← 세션 만료로 돌아왔을 때만
│  │ ⓘ 로그인이 만료되었어요        │  │
│  └───────────────────────────────┘  │
│                                     │
│   이메일                             │  Label 14
│  ┌───────────────────────────────┐  │  h 52
│  │ yhr@a.com       │  │
│  └───────────────────────────────┘  │
│   이메일을 입력해 주세요              │  Caption 12 · 오류색
│                                     │
│   비밀번호                           │
│  ┌───────────────────────────────┐  │
│  │ ••••••••                  👁  │  │
│  └───────────────────────────────┘  │
│                                     │
│   ⚠ 이메일 또는 비밀번호가            │  ← 높이를 미리 잡아 둔다
│     올바르지 않습니다                 │
│  ┌───────────────────────────────┐  │
│  │           로그인               │  │  h 52
│  └───────────────────────────────┘  │
│                                     │
│   계정은 관리자가 발급합니다          │  Caption 12 · muted
└─────────────────────────────────────┘
```

| 항목 | 결정 |
|---|---|
| 배치 | 세로 중앙이 아니라 상단 1/3. 키보드가 올라올 때 요소가 움직이지 않는다 |
| 오류 영역 | 버튼 **위**에 높이를 미리 확보. 오류가 뜰 때 버튼이 밀리면 손가락이 빗나간다 |
| 버튼 | 항상 활성. 빈 값이면 눌렀을 때 필드 하단에 인라인 오류 |
| 서버 검증에 기대지 않는 이유 | `@Valid` 실패는 `ApiError` 봉투가 아닌 스프링 기본 400이라 꺼내 쓸 문장이 없다 |
| 키보드 | 이메일: `email-address` · 자동대문자 off · return → 비밀번호. 비밀번호: `secureTextEntry` · return → 제출 |
| 로딩 | 버튼이 스피너로 바뀌고 두 필드 비활성 |
| 성공 | 토큰 · `expires_at` · 이메일 저장 → `summary`. **비밀번호는 저장하지 않는다** |
| 재진입 | 저장된 이메일 프리필, 비밀번호에 포커스 |
| 없는 것 | 회원가입 · 비밀번호 찾기 · 로그인 유지 체크박스 · 소셜 로그인 |

**부팅 판정**: SecureStore에서 토큰과 `expires_at`을 읽어 **로컬에서 만료를 비교**한다. `GET /auth/me`를 부르지 않는다 — 갱신 토큰도 강제 로그아웃도 없는 무상태 JWT라(스펙 §8.8 · §12) 만료 전에 무효가 되는 경우는 서버 비밀키 교체뿐이고, 그건 첫 뷰 호출의 401이 전역 처리로 잡는다. 왕복 한 번을 아끼고 오프라인에서도 판정이 선다.

**만료 복귀**: 401을 받으면 토큰을 지우고 **루트를 로그인으로 전환**한다. 탭 트리는 언마운트되고, 재로그인 후에는 `summary`로 간다. 모달로 덮어 이전 화면을 보존하지 않는다 — 12시간 만에 돌아온 화면의 데이터는 어차피 낡아 재조회해야 한다.

### A.3.2 `summary` — 요약

```
┌──────────────────────────────────────────┐
│ 기준 2026-07-27 15:30           ↻ 새로고침│  Micro 11
│ USD/KRW 1,400.00 적용 · 기준 2026-07-24   │  info notice
├──────────────────────────────────────────┤
│  총자산                                   │  Label 14
│  58,000,000원                             │  Hero 32
│  +4,500,000 (+9.2%)                       │  Title 20 · 상승색
├──────────────────────────────────────────┤
│  ┌──────────────────┬──────────────────┐ │
│  │ 총매입금액        │ 직전 거래일 대비  │ │  Label 14 · muted
│  │ 48,800,000       │ +1,200,000       │ │  Title 20
│  │                  │ (+2.1%)          │ │  Body 16 · 등락색
│  ├──────────────────┼──────────────────┤ │
│  │ 현금비중          │ 계좌 · 종목      │ │
│  │ 8.1%             │ 4계좌 · 6종목    │ │
│  └──────────────────┴──────────────────┘ │
├──────────────────────────────────────────┤
│  이번 달 자산 +1,200,000원      더보기 → │  Body 16
├──────────────────────────────────────────┤
│  자산 구성                          비중 →│  Label 14
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░      │  h 12 · radius 6
│  ● 국내   46,800,000원             80.7% │  Body 16
│  ● 미국   11,200,000원 ($8,000)    19.3% │
└──────────────────────────────────────────┘
```

| 항목 | 결정 |
|---|---|
| 히어로 | 총자산 + 총평가손익(금액/률). 손익에 라벨을 붙이지 않는다 — 부호와 색으로 읽힌다 |
| 유가증권 평가금액 | **표시하지 않는다.** 총매입과 평가손익에서 유도되고, 회계 용어가 라벨로 읽히지 않는다 |
| 타일 4개 | 총매입금액 · 직전 거래일 대비 · 현금비중 · 계좌·종목 |
| 자산 변화 줄 | `이번 달 자산 +1,200,000원  더보기 →`. 금액은 `asset-change`의 `closing − opening` |
| 렌더 시점 | **두 응답(`summary`·`asset-change`)을 모두 받은 뒤 한 번에** 그린다. 그전에는 스켈레톤 |
| 미니차트 | 시장 축 고정(`mini_chart_axis=market`), 렌즈 `DIRECT` 고정. 축 토글·렌즈 토글 없음 |
| 차트 형식 | 100% 누적 막대. 조각이 둘뿐이라 도넛은 세로만 먹는다 |
| 예수금 | 시장 축에서는 해당 시장 안에 포함된다. 막대에 별도 현금 조각이 없는 것이 정상 |
| 지연 배너 | 여기에 두지 않는다. `STALE_ACCOUNTS`는 계좌별 화면 담당(§A.5.3) |
| `daily_change`가 null | 연동 첫날. 타일 값이 `—`가 된다 |

**세로 합계** 배너 56 + 히어로 130 + 타일 160 + 자산변화 52 + 구성 130 = 528pt. iPhone SE 가용 535pt에 들어간다.

### A.3.3 `positions` — 종목별

```
┌────────────────────────────────────────────┐
│ 기준 2026-07-27 15:30             ↻ 새로고침│
│ USD/KRW 1,400.00 적용 · 기준 2026-07-24     │
├────────────────────────────────────────────┤
│ [필터 2 ▾]  [평가금액순 ▾]                  │  h 36 칩
│ 한국투자 위탁 ✕   미국 ✕                    │  ← 선택이 있을 때만
│ 구성종목 기준으로 보기  ⓘ            ◯──   │
├────────────────────────────────────────────┤
│ 58,000,000원          +4,500,000 (+9.2%)   │  합계 · 필터 반영
├────────────────────────────────────────────┤
│ 삼성전자 [국내]        14,240,000원 (24.6%) │  Body 16
│ 200주 · 평단 60,000    +2,240,000 (+18.7%) │  Caption 12 / Body 14
├────────────────────────────────────────────┤
│ TIGER 미국나스…[국내]  11,000,000원 (19.0%) │  ← 종목명 말줄임
│ 100주 · 평단 100,000   +1,000,000 (+10.0%) │
├────────────────────────────────────────────┤
│ 애플 [미국]     6,160,000원 ($4,400)(10.6%) │
│ 20주 · 평단 $200.00      +560,000 (+10.0%) │
├────────────────────────────────────────────┤
│ KRW 예수금             4,560,000원 (7.9%)   │
│ —                                       —  │
└────────────────────────────────────────────┘
```

| 항목 | 결정 |
|---|---|
| 행 | 표가 아니라 **2줄 카드**. 높이 56pt |
| 1줄 | 종목명 · 시장 배지 · 평가금액(+현지통화) · 비중 |
| 2줄 | 수량 · 평단 / 평가손익(금액·률) |
| 빼는 것 | 현재가(지표 카탈로그에 없음) · 매입금액(= 평가금액 − 평가손익) |
| 예수금 행 | **남긴다.** 빼면 비중 합이 100%가 안 되고 합계가 `total_assets_krw`와 어긋난다. 원가·손익은 `—` |
| 합계 줄 | `total`을 그대로. 필터가 반영된 값이다. **종목수를 병기하지 않는다** — `instrument_count`(6)와 행 수(8)가 다르다 |
| 필터 | 계좌 · 시장 · 자산군, 전부 다중 선택. 선택지는 카탈로그에서 |
| 정렬 | 클라이언트가 한다. 평가금액순(기본) · 평가손익순 · 손익률순 · 이름순 |
| 정렬 규칙 | 내림차순(이름순만 오름차순). **`null`은 언제나 맨 끝** |
| 렌즈 ON | 2줄이 `환산 3.37주`만 남는다. 시장·자산군 필터 비활성 + 선택값 리셋. 손익 정렬 2종 비활성 |
| 렌즈 토글 이름 | `ETF 분해 모드` |
| 행 탭 | **동작 없음.** 종목 상세가 범위 밖이라 누를 곳이 없다. 눌리는 피드백도 주지 않는다 |
| 비중순 정렬 | 두지 않는다. 비중 = 평가금액 ÷ 총자산이라 평가금액순과 순서가 항상 같다 |

**필터 UI는 칩 하나에 3종을 담는다.** 칩 3개를 늘어놓지 않는 이유는 폭도 있지만, 렌즈 ON일 때 시장·자산군만 비활성되는 상황이 칩에서는 회색 칩 두 개로 남아 누를 수 있어 보이기 때문이다. 바텀시트 안에서는 그 두 그룹을 흐리게 하고 `구성종목 기준에서는 쓸 수 없어요` 한 줄을 붙이면 끝난다.

**렌즈 안내는 화면이 만든다.** 토글 라벨 옆 `ⓘ`는 토글 상태와 무관하게 늘 있고, 탭하면 토글 줄 아래에 설명이 펼쳐진다. 화면 위쪽에 상시 박스로 두지 않는다.

서버의 `LENS_METRICS_OMITTED`를 쓰지 않는 이유는 성격이 다르기 때문이다. 그것은 "방금 이 응답에서 어떤 값을 뺐다"는 사후 보고라 렌즈를 켠 응답에만 실린다. 스위치를 누르기 전에 무슨 일이 생길지 알리는 것은 화면의 몫이다. 설명은 아이콘 옆이 아니라 아래 전체 폭을 쓴다 — 옆에 띄우면 화면 오른쪽 끝에서 잘린다.

**종목명 말줄임**: 최대 폭 160pt(Body 16pt에서 한글 약 10자), 초과 시 뒤쪽 `…`. 1줄 고정. 폭 우선순위는 `금액·비중 블록 > 시장 배지 > 종목명`이다.

### A.3.4 탭바

5개 — 요약 · 종목 · 비중 · 계좌 · 손익. 자산 변화는 탭이 아니다(스펙 §2.2).

이번 범위에서 비중 · 계좌 · 손익 세 탭은 자리만 만들고 `준비 중입니다` 문구를 띄운다. 탭을 아예 빼면 나중에 탭바 레이아웃이 흔들리고, 사용자가 앱의 전체 모습을 알 수 없다.

`계좌` 탭 아이콘의 점 표시(캐리포워드·재인증 알림)는 계좌별 화면 논의에서 조치 경로와 함께 정한다. 이번 태스크에서는 점을 그리지 않는다.

## A.4 API 계약

### A.4.1 이번 범위가 부르는 엔드포인트

```
POST /auth/login                    { email, password } → { access_token, expires_at }
GET  /portfolio/catalog             필터 선택지
GET  /portfolio/views/summary       ?mini_chart_axis=market&mini_chart_lens=DIRECT
GET  /portfolio/views/positions     ?lens=&account=&market=&asset_class=
GET  /portfolio/views/asset-change  ?period=THIS_MONTH
```

- `POST /auth/login`을 뺀 전부가 `Authorization: Bearer <token>`을 요구한다.
- 사용자 ID는 어디에도 넣지 않는다. 스코프는 토큰에서만 온다(스펙 §3.8 · §8.8).
- 다중 값 필터는 같은 이름을 반복한다 — `?account=A&account=B`.
- `period` 허용값: `THIS_MONTH` · `LAST_MONTH` · `THIS_YEAR` · `LAST_YEAR` · `CUSTOM`(`from`·`to` 필수).

### A.4.2 응답 봉투

```ts
type Envelope<T> = {
  as_of: string;                 // "2026-07-27T15:30:00+09:00"
  data: T;
  empty_reason: EmptyReason | null;
  notices: Notice[];
};

type Notice = {
  code: string;
  severity: 'info' | 'warn' | 'error';
  message: string;               // 서버가 완성한 한국어 문장. 그대로 출력한다
  params: Record<string, unknown>;
};

type EmptyReason =
  | 'NO_ACCOUNTS' | 'NO_HOLDINGS' | 'NO_MATCH_FILTER'
  | 'NO_TRADES_IN_PERIOD' | 'ALL_UNAVAILABLE';
```

**빈 상태는 오류가 아니다.** HTTP 200에 `rows: []`와 `empty_reason`이 온다.

### A.4.3 스냅샷 뷰 데이터 (`summary` · `positions`)

```ts
type SnapshotViewData = {
  group_by: string[];            // summary: [] · positions: ["instrument"]
  lens: 'DIRECT' | 'LOOK_THROUGH';
  total: Total;
  rows: Row[];
  mini_chart?: MiniChart;        // summary만
};

type Total = {
  total_assets_krw: number;      // 예수금 포함
  securities_value_krw: number;  // 예수금 제외
  deposit_krw: number;
  cost_amount_krw: number;
  unrealized_pnl_krw: number;
  unrealized_pnl_pct: number;
  cash_ratio_pct: number;
  instrument_count: number;
  account_count: number;
  daily_change_krw?: number | null;   // summary만. 첫날은 null
  daily_change_pct?: number | null;
};

type Row = {
  key: string;                   // "005930" · "CASH-KRW"
  label: string;                 // "삼성전자" · "KRW 예수금"
  currency?: string;             // 단일 통화 행에만 ("USD")
  quantity?: number;
  avg_cost?: number | null;      // 예수금 행은 null
  market_value_krw: number;
  market_value_local?: number;   // 단일 통화 행에만
  cost_amount_krw?: number | null;
  cost_amount_local?: number;
  unrealized_pnl_krw?: number | null;
  unrealized_pnl_pct?: number | null;
  weight_pct: number;
  market?: string;               // "KR" · "US" — positions 행에만
};

type MiniChart = {
  group_by: string[];            // ["market"]
  lens: 'DIRECT' | 'LOOK_THROUGH';
  rows: { key: string; label: string; currency?: string;
          market_value_krw: number; market_value_local?: number;
          weight_pct: number }[];
};
```

**렌즈 ON이면 `rows[]`에서 `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct`가 사라진다.** `total`에는 남는다(총합 보존, 스펙 §3.4 · §6.2). 타입에서 이 세 필드가 옵셔널인 이유가 이것이다.

### A.4.4 자산 변화 데이터 (요약이 쓰는 부분)

```ts
type AssetChangeData = {
  period: { from: string; to: string };
  opening: number;
  closing: number;
  deposited: number;
  earned: number;
  account_included: number;
  account_excluded: number;
  breakdown: { type: 'DEPOSIT' | 'WITHDRAW' | 'DIVIDEND' | 'FEE_TAX' | 'INVESTMENT_PNL';
               amount: number }[];
  investment_pnl: { total: number; realized: number | null;
                    unrealized_change: number | null; split_available: boolean };
};
```

요약이 쓰는 것은 `closing − opening` 하나다. 나머지는 자산 변화 화면의 몫이다.

### A.4.5 카탈로그

```ts
type Catalog = {
  axes:    { key: string; label: string; lens_sensitive: boolean;
             enabled: boolean; applicable_views: string[] }[];
  metrics: { key: string; label: string; ... }[];
  views:   { view_key: string; axis_options: string[];
             filters: { DIRECT: string[]; LOOK_THROUGH: string[] };
             lens_policy: 'NONE' | 'OPTIONAL' | 'ALWAYS'; ... }[];
  accounts:{ account_id: string; broker: string; label: string;
             account_type: 'GENERAL' | 'PENSION'; link_state: string }[];
};
```

**필터 선택지를 여기서만 얻는다.** `views[view_key="positions"].filters.DIRECT`가 `DIRECT`에서 쓸 수 있는 필터 키 목록이고, `.LOOK_THROUGH`는 렌즈를 켰을 때의 목록이다. 계좌 값은 `accounts[]`가 전부다.

**시장·자산군의 선택 가능한 값은 카탈로그에 없다.** 실제 응답에서 값 목록이 오는 것은 `accounts[]`뿐이다. 시장(`KR`·`US`)과 자산군(`STOCK`·`ETF`·`CASH`)은 화면 상수로 둔다. 라벨은 `국내`·`미국` / `주식`·`ETF`·`현금`으로 화면이 붙인다. 서버가 값 목록을 내려주게 되면 그 상수를 지운다.

응답 행의 `market` 값을 모아 목록을 만드는 방법은 쓰지 않는다. 필터를 걸어 행이 줄면 선택지도 함께 줄어, 방금 고른 것을 되돌릴 수 없게 된다.

### A.4.6 오류

```ts
// 401 · 403 · 400 · 404 · 500
{ "error": { "code": "INVALID_CREDENTIALS", "message": "이메일 또는 비밀번호가 올바르지 않습니다" } }
```

| 상황 | 코드 | `error.code` | 클라이언트 동작 |
|---|---|---|---|
| 로그인 실패 | 401 | `INVALID_CREDENTIALS` | 로그인 화면 오류 영역에 `message` 출력 |
| 토큰 없음·만료·서명 불일치 | 401 | `UNAUTHENTICATED` | **전역 처리** — 토큰 삭제 후 로그인으로 |
| 남의 계좌 지정 | 403 | `FORBIDDEN_ACCOUNT` | 필터 초기화 후 재조회 |
| 잘못된 파라미터 | 400 | `INVALID_PERIOD` 등 | 화면 오류 상태 |

`POST /auth/login`의 401은 전역 처리 대상이 **아니다.** 로그인 화면에서 처리하고 로그인 화면으로 다시 보내지 않는다. 전역 인터셉터는 `/auth/login` 경로를 제외한다.

### A.4.7 골든 응답

`back-end/src/test/resources/golden/`의 7개 파일이 실제 응답이다. Task 1에서 `src/fixtures/golden/`으로 복사해 테스트 입력으로 쓴다. 이번 범위가 쓰는 것은 `summary.json` · `positions.json` · `asset-change.json` 셋이고, 나머지 넷은 다음 단계를 위해 함께 복사한다.

## A.5 표기 규칙

### A.5.1 숫자

| 항목 | 규칙 | 예 |
|---|---|---|
| 금액 | 원 단위 정수 · 천단위 콤마 | `58,000,000` |
| `원` 접미사 | 단독 노출·문장에만. 표·행 안에서는 생략 | `58,000,000원` / 타일은 `48,800,000` |
| 축약 | 기본은 전체 자릿수. **문장형 답변과 워터폴 막대 라벨에서만** 한글 축약 | `1,200만원` |
| 부호 | 손익·변화는 항상 `+`/`−`. 0은 부호 없이. 음수는 U+2212(`−`)이고 ASCII 하이픈이 아니다 | `+4,500,000` · `−1,000,000` · `0` |
| 화살표 | **쓰지 않는다.** 부호와 색으로 표현 | |
| 퍼센트 | 소수 1자리 고정 | `9.2%` · `80.7%` |
| 외화 | 괄호 병기. 행·범례는 정수, 단가만 소수 2자리 | `11,200,000원 ($8,000)` · `평단 $200.00` |
| null | `—` | |
| 정렬 | `fontVariant: ['tabular-nums']` | |

`▲`·`▼`를 쓰지 않는 이유 셋: 고정폭 숫자 대열에서 폭이 어긋나고, 화살표를 쓰면 부호를 생략하게 되어 방향이 색에만 걸리며, `U+25B2`는 안드로이드에서 글꼴 폴백이 걸려 크기·베이스라인이 iOS와 달라진다.

### A.5.2 색

```
상승 · 이익    빨강     #D32F2F
하락 · 손실    파랑     #1565C0
중립           본문색
```

국내 관행을 따른다. **자산 변화 화면은 이 체계를 쓰지 않는다** — 그 화면은 파랑이 "사용자가 넣은 돈", 초록이 "시장이 만든 돈"이라 등락 색과 충돌한다. 그 화면 논의에서 확정한다.

### A.5.3 notice 배치

| severity | 자리 | 모양 |
|---|---|---|
| `info` | as-of 배너 둘째 줄 | 아이콘 없음 · Micro 11 · muted. 여러 개면 ` · `로 잇는다 |
| `warn` | 배너 아래 · 콘텐츠 위 | ⚠ + 노란 배경 줄. 각각 한 줄씩 쌓되 3개 초과 시 접는다 |
| `error` | 같은 자리 | 빨간 배경 |

**화면별 표시 대상**을 화이트리스트로 정한다. 같은 notice가 여러 응답에 실려 오므로 어디서 그릴지가 정해져 있어야 한다.

| code | 그리는 화면 | 자리 |
|---|---|---|
| `FX_APPLIED` | 전 화면 | 배너 캡션 |
| `STALE_ACCOUNTS` · `REAUTH_REQUIRED` | 계좌별만 | (이번 범위에서는 그리지 않는다) |
| `CONSTITUENT_AS_OF` | 렌즈 ON 화면 | 배너 캡션 |
| `LENS_METRICS_OMITTED` | 그리지 않는다 | 같은 내용을 화면이 만든 ⓘ 설명이 대신한다 |
| `CONSTITUENT_UNAVAILABLE` | 렌즈 ON 화면 | warn 줄 |
| `SEEDED_ROWS` · `EXCLUDED_ACCOUNTS` · `CA_UNKNOWN` | 실현손익 | 다음 단계 |
| `CASHFLOW_UNCOVERED` · `PERIOD_TRUNCATED` · `BOUNDARY_CARRIED_FORWARD` | 자산 변화 | 다음 단계 |
| 그 외 | 표시하지 않는다 | |

화이트리스트에 없는 코드는 **조용히 버린다.** 서버가 코드를 늘려도 화면이 깨지지 않는다.

### A.5.4 클라이언트가 만드는 문구 (전부)

```
이메일을 입력해 주세요
비밀번호를 입력해 주세요
로그인이 만료되었어요. 다시 로그인해 주세요
연결에 실패했어요. 잠시 후 다시 시도해 주세요
새로고침 실패 · 다시 시도
연동된 계좌가 없어요 / 계좌 연동은 준비 중입니다
보유 중인 종목이 없어요
조건에 맞는 종목이 없어요
ETF 분해 모드에서는 쓸 수 없어요
ETF를 안에 든 종목들로 쪼개서 봅니다. 같은 종목을 여러 ETF로 나눠 갖고 있어도
한 줄로 합쳐 보입니다. 대신 ETF를 살 때 낸 돈을 조각마다 나눌 수 없어,
평단과 평가손익은 행에서 빠집니다
준비 중입니다
```

이 목록 밖의 문장은 전부 서버가 준 것이다.

### A.5.5 타이포 · 간격 · 크기

```
타이포   Hero 32/38 · Display 28/34 · Title 20/26 · Body 16/22
         Label 14/20 · Caption 12/16 · Micro 11/14
간격     4의 배수. 기본 단위 8 (4 · 8 · 12 · 16 · 20 · 24 · 32)
패딩     화면 좌우 20
높이     입력 필드 52 · 주 버튼 52 · 칩 36 · 최소 탭 영역 44 · 카드 행 56
반경     카드 12 · 칩 18 · 버튼 8 · 막대 6
```

### A.5.6 다크모드

**v1에서 지원하지 않는다.** `app.json`의 `userInterfaceStyle`이 `light`이고, 색이 상승·하락이라는 의미를 지고 있어 다크 팔레트를 만들려면 그 대비를 다시 검증해야 한다. 대신 **토큰을 `theme.light` 형태로 감싸 두어** 나중에 `theme.dark`를 더하는 것으로 끝나게 한다. 화면 코드는 `useTheme()`을 통해서만 색을 읽는다.

## A.6 화면 상태 전수

| 화면 | 상태 | 표현 |
|---|---|---|
| `login` | default | |
| | 입력 누락 | 필드 하단 인라인 오류 |
| | 인증 실패 | 버튼 위 오류 영역, 서버 `message` |
| | 로딩 | 버튼 스피너 + 필드 비활성 |
| | 세션 만료로 되돌아옴 | 상단 안내 배너 + 이메일 프리필 |
| | 네트워크 실패 | 오류 영역, 클라이언트 문구 |
| `summary` | default | |
| | 로딩 | 스켈레톤(히어로·타일·구성) |
| | 연동 계좌 없음 | `empty_reason = NO_ACCOUNTS` → 문구만. CTA 없음 |
| | 일간 변화 없음 | `daily_change_krw = null` → 타일에 `—` |
| | 조회 실패 | 오류 상태 + 다시 시도 버튼 |
| `positions` | default | |
| | 로딩 | 카드 스켈레톤 5행 |
| | 보유 종목 없음 | `NO_HOLDINGS` |
| | 필터 결과 없음 | `NO_MATCH_FILTER` + `필터 초기화` 버튼. 칩은 남긴다 |
| | 렌즈 ON | 2줄 축소 · 필터 2종 비활성 · 손익 정렬 비활성 · ⓘ 말풍선 |
| | 구성종목 미확보 | `CONSTITUENT_UNAVAILABLE` warn 줄 |
| | 조회 실패 | 오류 상태 + 다시 시도 |
| 전역 | 401 | 토큰 삭제 후 로그인으로 전환 |

**인증 만료는 화면별 상태가 아니다.** 401은 어느 화면에서든 같은 뜻이므로 전역 한 곳에서 처리한다(스펙 §10).

## A.7 개발 환경

### A.7.1 백엔드 띄우기

```bash
cd back-end
docker compose up -d db
./gradlew bootRun --args='--spring.profiles.active=local'
docker compose exec -T db psql -U portfolio -d portfolio -f /sample/sample_portfolio.sql
```

로그인 계정: `yhr@a.com` / `local-dev-password`

### A.7.2 API 주소

실기기 Expo Go는 개발 머신의 `localhost`에 닿지 못한다. **LAN IP를 쓴다.**

```bash
ipconfig getifaddr en0        # 예: 192.168.0.12
```

`.env`에 넣고 Expo가 `EXPO_PUBLIC_` 접두사 변수를 번들에 주입한다.

```
EXPO_PUBLIC_API_BASE_URL=http://192.168.0.12:8080
```

`.env`는 `.gitignore`에 넣고 `.env.example`을 커밋한다. 기기와 개발 머신이 같은 Wi-Fi에 있어야 한다.

### A.7.3 웹에서 실제 응답을 보려면

백엔드의 `local` 프로파일이 `http://localhost:8081` 출처를 허용한다 — `POST /auth/login`과 `GET /portfolio/**`, 헤더는 `Authorization`·`Content-Type`. 다른 프로파일에는 CORS 설정이 없다(백엔드 `docs/decisions.md`).

브라우저에서 붙으려면 두 가지가 더 필요하다.

- **주소는 정확히 `http://localhost:8081`이어야 한다.** 개발 서버 포트가 8081이 아니거나(이미 점유돼 8082로 뜨는 경우) `127.0.0.1`로 열면 다른 출처로 취급돼 막힌다. `EXPO_PUBLIC_API_BASE_URL`은 LAN IP 그대로 둔다 — CORS는 대상 호스트가 아니라 페이지의 출처를 보므로 기기와 브라우저가 설정 하나를 함께 쓴다.
- **토큰이 놓이는 자리가 웹에서 다르다.** `expo-secure-store`는 웹 구현이 비어 있어 `tokenStore`가 플랫폼으로 갈린다 — 기기는 Keychain·Keystore, 브라우저는 `localStorage`. 브라우저 쪽은 잠금장치가 없는 자리이고, 웹은 배포 대상이 아니다.

**지금 상태로 웹에서 되는 것은 골든 픽스처 레이아웃 확인이다.** 실제 데이터 확인은 실기기 Expo Go로 한다.

### A.7.4 알려진 위험

- **Node v26 · npm 11 vs Expo SDK 54(2025-09 기준)**. 의존성 설치나 메트로 번들에서 문제가 나면 이 격차를 먼저 의심한다.
- **Expo Go SDK 상한 54.** 패키지 설치는 `npx expo install`로만 한다.

---

# Part B — 파일 구조

```
front-end/
├── App.tsx                          ← 삭제 (스파이크 산출물)
├── index.ts                         ← src/app/App 을 등록하도록 수정
├── .env.example                     ← 추가
├── jest.config.js                   ← 추가
└── src/
    ├── app/
    │   ├── App.tsx                  QueryClientProvider · AuthProvider · Navigation
    │   ├── Root.tsx                 인증됨 ? Tabs : LoginScreen
    │   └── navigation/
    │       ├── Tabs.tsx             탭 5개
    │       └── types.ts             네비게이션 파라미터 타입
    ├── api/
    │   ├── client.ts                fetch 래퍼 · 토큰 주입 · 401 전역 처리
    │   ├── types.ts                 Envelope · Notice · Row · Total · Catalog …
    │   ├── endpoints.ts             경로와 쿼리스트링 조립
    │   └── queries/
    │       ├── keys.ts              쿼리 키 팩토리
    │       ├── useSummary.ts        summary + asset-change 동시 조회
    │       ├── usePositions.ts
    │       └── useCatalog.ts
    ├── auth/
    │   ├── AuthContext.tsx          토큰 상태 · login() · logout()
    │   ├── tokenStore.ts            expo-secure-store 읽기·쓰기·삭제
    │   └── session.ts               만료 판정
    ├── design/
    │   ├── tokens.ts                색 · 간격 · 반경 · 크기
    │   ├── typography.ts            7단 스케일
    │   └── theme.ts                 useTheme() · light 팔레트
    ├── format/
    │   ├── number.ts                금액 · 퍼센트 · 부호 · 축약 · null
    │   └── date.ts                  as-of · 기준일
    ├── ui/
    │   ├── Button.tsx  TextField.tsx  Card.tsx  Badge.tsx
    │   ├── Chip.tsx    BottomSheet.tsx  Toggle.tsx  Tooltip.tsx
    │   └── Skeleton.tsx
    ├── envelope/
    │   ├── ScreenFrame.tsx          배너 + 경고 + 본문/빈 상태/로딩/오류 분기
    │   ├── AsOfBanner.tsx           기준 시각 · 새로고침 · info notice
    │   ├── NoticeList.tsx           warn·error 줄 · 화이트리스트 필터
    │   ├── EmptyState.tsx           empty_reason → 문구
    │   └── ErrorState.tsx           조회 실패 · 다시 시도
    ├── screens/
    │   ├── login/LoginScreen.tsx
    │   ├── summary/                 SummaryScreen · HeroBlock · TileGrid · CompositionBar
    │   ├── positions/               PositionsScreen · PositionRow · FilterSheet · SortMenu
    │   └── placeholder/Placeholder.tsx   비중 · 계좌 · 손익 탭
    ├── fixtures/golden/*.json       백엔드 골든 7개 복사본
    └── __tests__/                   포맷터 · 정렬 · notice · 골든 렌더
```

**`ui/`와 `envelope/`의 차이**: `ui/`는 도메인을 모르는 시각 부품이고, `envelope/`는 이 API의 봉투 구조를 아는 부품이다. 화면은 둘 다 쓰지만 `ui/`는 다른 프로젝트에 옮겨도 동작하고 `envelope/`는 그렇지 않다.

**컴포넌트 추출 시점**: `ui/`의 부품은 **두 번째 사용처가 생길 때** 만든다. 미리 만들면 쓰이지 않을 props를 상상하게 된다. 다만 처음부터 `src/ui/`에 두어 두 번째 화면이 가져다 쓸 때 파일이 움직이지 않게 한다.

---

# Part C — 태스크

## Task 1: 스파이크 정리 · 프로젝트 뼈대 · 의존성

**Files:**
- Delete: `front-end/App.tsx`
- Modify: `front-end/index.ts` · `front-end/package.json` · `front-end/tsconfig.json` · `front-end/.gitignore` · `front-end/app.json`
- Create: `front-end/.env.example` · `front-end/jest.config.js`
- Create: `front-end/src/app/App.tsx` (빈 화면 · 다음 태스크에서 채운다)
- Create: `front-end/src/fixtures/golden/*.json` (7개 복사)

**Interfaces:**
- Produces: `src/` 디렉터리와 경로 별칭 `@/*`. 이후 모든 import가 이 별칭을 쓴다.
- Produces: 골든 픽스처 7개. 이후 모든 렌더 테스트의 입력.

**완료 조건**
1. `npx tsc --noEmit`이 오류 0으로 통과한다.
2. `npx expo start`로 번들이 만들어지고 실기기에서 빈 화면이 뜬다.
3. `npm test`가 실행되고(테스트 0개라도) 설정 오류가 없다.
4. `App.tsx`가 삭제되고 `index.ts`가 `src/app/App`을 등록한다.
5. 설치된 패키지 버전이 `package.json`에 기록되고 SDK 54와 호환된다.
6. 골든 7개가 `src/fixtures/golden/`에 있고 백엔드 원본과 내용이 같다.

**검증 방법**
```bash
cd front-end
npx tsc --noEmit                       # 오류 0
npm test -- --passWithNoTests          # 통과
diff <(cat src/fixtures/golden/summary.json) \
     ../back-end/src/test/resources/golden/summary.json   # 차이 없음
npx expo start                         # QR 스캔 → 실기기에 빈 화면
```

- [x] **Step 1: 스파이크 산출물 제거**

`App.tsx`를 삭제하고 `index.ts`를 고친다.

```ts
import { registerRootComponent } from 'expo';
import App from './src/app/App';

registerRootComponent(App);
```

- [x] **Step 2: 의존성 설치**

```bash
npx expo install @react-navigation/native @react-navigation/native-stack \
                 @react-navigation/bottom-tabs \
                 react-native-screens react-native-safe-area-context
npx expo install @tanstack/react-query
npm install --save-dev jest-expo jest @testing-library/react-native @types/jest
```

`npx expo install`은 SDK 54에 맞는 버전을 고른다. **설치 후 `package.json`에 박힌 버전을 커밋 메시지에 남긴다.** Node 26과 SDK 54의 격차로 설치가 실패하면 그 오류를 먼저 보고한다(§A.7.4).

- [x] **Step 3: 경로 별칭**

`tsconfig.json`:

```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  }
}
```

- [x] **Step 4: Jest 설정**

`jest.config.js`:

```js
module.exports = {
  preset: 'jest-expo',
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
  setupFilesAfterEnv: ['@testing-library/react-native/extend-expect'],
};
```

`package.json`의 `scripts`에 `"test": "jest"`를 더한다.

- [x] **Step 5: 환경 변수**

`.env.example`:

```
EXPO_PUBLIC_API_BASE_URL=http://192.168.0.12:8080
```

`.gitignore`에 `.env`를 더한다.

- [x] **Step 6: 골든 픽스처 복사**

```bash
mkdir -p src/fixtures/golden
cp ../back-end/src/test/resources/golden/*.json src/fixtures/golden/
```

- [x] **Step 7: 빈 App**

`src/app/App.tsx`에 `<View>` 하나만 두고 번들이 도는지 확인한다.

- [x] **Step 8: 커밋** — `chore: 스파이크를 걷어내고 src 구조와 개발 의존성을 세운다`

---

## Task 2: 디자인 토큰 · 타이포 · 포맷터

**Files:**
- Create: `src/design/tokens.ts` · `src/design/typography.ts` · `src/design/theme.ts`
- Create: `src/format/number.ts` · `src/format/date.ts`
- Test: `src/__tests__/format.test.ts`

**Interfaces:**
- Produces: `useTheme()` — 화면이 색을 읽는 유일한 경로.
- Produces: `formatKrw` · `formatSigned` · `formatPct` · `formatLocal` · `formatCompact` · `EM_DASH`.

**완료 조건**
1. §A.5.1의 표기 규칙이 전부 함수로 존재하고 테스트가 각 행을 하나씩 검증한다.
2. `null`·`undefined` 입력이 `—`를 반환한다.
3. 화면 코드가 색 리터럴을 직접 쓰지 못하도록 팔레트가 `theme.ts` 한 곳에만 있다.
4. `npx tsc --noEmit` 통과, `npm test` 통과.

**검증 방법**
```bash
cd front-end
npm test -- format.test.ts
npx tsc --noEmit
grep -rn "#[0-9A-Fa-f]\{6\}" src --include="*.tsx" | grep -v design/   # 결과 없음
```

- [x] **Step 1: 토큰**

```ts
// src/design/tokens.ts
export const space = { xs: 4, sm: 8, md: 12, base: 16, lg: 20, xl: 24, xxl: 32 } as const;
export const radius = { card: 12, chip: 18, button: 8, bar: 6 } as const;
export const size = { field: 52, button: 52, chip: 36, tap: 44, row: 56, bar: 12 } as const;
export const screenPadding = 20;
```

- [x] **Step 2: 타이포**

```ts
// src/design/typography.ts
export const type = {
  hero:    { fontSize: 32, lineHeight: 38, fontWeight: '700' },
  display: { fontSize: 28, lineHeight: 34, fontWeight: '700' },
  title:   { fontSize: 20, lineHeight: 26, fontWeight: '600' },
  body:    { fontSize: 16, lineHeight: 22, fontWeight: '400' },
  label:   { fontSize: 14, lineHeight: 20, fontWeight: '500' },
  caption: { fontSize: 12, lineHeight: 16, fontWeight: '400' },
  micro:   { fontSize: 11, lineHeight: 14, fontWeight: '400' },
} as const;

export const numeric = { fontVariant: ['tabular-nums'] } as const;
```

- [x] **Step 3: 테마**

```ts
// src/design/theme.ts
const light = {
  bg: '#FFFFFF', surface: '#F7F8FA', border: '#E5E7EB',
  text: '#111827', textMuted: '#6B7280',
  up: '#D32F2F', down: '#1565C0',
  primary: '#1F4FD8', onPrimary: '#FFFFFF',
  warnBg: '#FEF6E0', warnText: '#8A6100',
  errorBg: '#FDECEC', errorText: '#B3261E',
} as const;

export type Palette = typeof light;
export const useTheme = (): Palette => light;   // 다크모드를 열 때 이 함수만 바뀐다
```

- [x] **Step 4: 숫자 포맷터**

```ts
// src/format/number.ts
export const EM_DASH = '—';

export function formatKrw(v: number | null | undefined, opts?: { suffix?: boolean }): string
export function formatSigned(v: number | null | undefined): string     // +4,500,000 / -1,000,000 / 0
export function formatPct(v: number | null | undefined, opts?: { signed?: boolean }): string  // 9.2% / +9.2%
export function formatLocal(v: number | null | undefined, currency: string): string  // $8,000.00
export function formatCompact(v: number | null | undefined): string    // 1,200만원
export function signOf(v: number | null | undefined): 'up' | 'down' | 'flat'
```

- [x] **Step 5: 테스트**

§A.5.1 표의 각 행에 대응하는 케이스와 경계값(0 · null · 음수 · 소수 반올림)을 쓴다. 골든의 실값(`58000000` · `9.2` · `-11.1` · `8000.0`)을 그대로 입력으로 쓴다.

- [x] **Step 6: 커밋** — `feat: 디자인 토큰과 숫자 표기 규칙을 한 곳에 모은다`

---

## Task 3: API 클라이언트 · 토큰 저장 · 인증 컨텍스트

**Files:**
- Create: `src/api/types.ts` · `src/api/client.ts` · `src/api/endpoints.ts`
- Create: `src/api/queries/keys.ts` · `useCatalog.ts`
- Create: `src/auth/tokenStore.ts` · `src/auth/session.ts` · `src/auth/AuthContext.tsx`
- Test: `src/__tests__/session.test.ts` · `src/__tests__/client.test.ts`

**Interfaces:**
- Produces: `apiGet<T>(path, params)` · `login(email, password)` — 모든 화면의 데이터 진입점.
- Produces: `useAuth()` — `{ status, email, login, logout }`. `status`는 `loading | authenticated | unauthenticated`.
- Produces: 401 전역 처리. 뷰 요청이 401을 받으면 토큰을 지우고 `status`가 `unauthenticated`로 바뀐다.

**완료 조건**
1. §A.4의 타입이 전부 `types.ts`에 있고 골든 JSON이 그 타입으로 파싱된다(타입 테스트).
2. 토큰 저장·조회·삭제가 `expo-secure-store`로 동작한다.
3. 만료 판정이 로컬 `expires_at` 비교로 이뤄지고 `GET /auth/me`를 부르지 않는다.
4. 뷰 요청의 401은 로그아웃으로 이어지고, `POST /auth/login`의 401은 이어지지 않는다.
5. 다중 값 필터가 `?account=A&account=B`로 직렬화된다.

**검증 방법**
```bash
cd front-end
npm test -- session.test.ts client.test.ts
npx tsc --noEmit
# 백엔드를 띄운 상태에서 토큰 발급이 실제로 되는지 확인
curl -s -X POST http://localhost:8080/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"yhr@a.com","password":"local-dev-password"}'
# 기대: {"access_token":"eyJ...","expires_at":"..."}
```

- [x] **Step 1: 응답 타입** — §A.4.2 ~ A.4.6을 그대로 옮긴다.

- [x] **Step 2: 토큰 저장소**

```ts
// src/auth/tokenStore.ts
const KEY_TOKEN = 'portfolio.access_token';
const KEY_EXPIRES = 'portfolio.expires_at';
const KEY_EMAIL = 'portfolio.last_email';

export async function saveSession(token: string, expiresAt: string, email: string): Promise<void>
export async function loadSession(): Promise<{ token: string; expiresAt: string } | null>
export async function loadLastEmail(): Promise<string | null>
export async function clearSession(): Promise<void>   // 이메일은 남긴다
```

비밀번호는 어디에도 저장하지 않는다.

- [x] **Step 3: 만료 판정**

```ts
// src/auth/session.ts
export function isExpired(expiresAt: string, now: Date = new Date()): boolean
```

경계 케이스를 테스트로 고정한다 — 만료 1초 전/후, 잘못된 문자열은 만료로 간주.

- [x] **Step 4: API 클라이언트**

- 베이스 URL은 `process.env.EXPO_PUBLIC_API_BASE_URL`. 없으면 시작 시 명확히 실패한다.
- 토큰이 있으면 `Authorization: Bearer` 주입.
- 401이고 경로가 `/auth/login`이 아니면 `onUnauthenticated()` 콜백 호출 후 예외.
- `error.message`가 있으면 그 문장을 담은 `ApiError`를 던진다.
- 네트워크 실패는 `NetworkError`로 구분한다(문구가 다르다).

- [x] **Step 5: 인증 컨텍스트**

부팅 시 `loadSession()` → `isExpired()` 판정 → `status` 확정. `login()`은 `POST /auth/login` 후 저장, `logout()`은 `clearSession()` 후 상태 전환. 클라이언트의 `onUnauthenticated`를 `logout`에 연결한다.

- [x] **Step 6: 쿼리 키**

```ts
// src/api/queries/keys.ts
export const keys = {
  catalog: ['catalog'] as const,
  summary: ['summary'] as const,
  assetChange: (period: string) => ['asset-change', period] as const,
  positions: (p: { lens: string; account: string[]; market: string[]; assetClass: string[] }) =>
    ['positions', p] as const,
};
```

- [x] **Step 7: 커밋** — `feat: API 클라이언트와 토큰 세션을 만든다`

---

## Task 4: 네비게이션 · 로그인 화면

**Files:**
- Create: `src/app/Root.tsx` · `src/app/navigation/Tabs.tsx` · `src/app/navigation/types.ts`
- Create: `src/screens/login/LoginScreen.tsx`
- Create: `src/screens/placeholder/Placeholder.tsx`
- Create: `src/ui/Button.tsx` · `src/ui/TextField.tsx`
- Modify: `src/app/App.tsx`
- Test: `src/__tests__/login.test.tsx`

**Interfaces:**
- Produces: 루트 분기 `status === 'authenticated' ? <Tabs/> : <LoginScreen/>`.
- Produces: 탭 5개. 요약·종목은 다음 태스크에서 실제 화면으로 바뀌고, 나머지 셋은 `Placeholder`.

**완료 조건**
1. 실기기에서 로그인 → 탭 화면 진입 → 앱 재실행 시 로그인 화면을 건너뛴다.
2. 잘못된 비밀번호로 로그인하면 서버 문장 `이메일 또는 비밀번호가 올바르지 않습니다`가 오류 영역에 뜬다.
3. 빈 값으로 제출하면 필드 하단에 인라인 오류가 뜨고 요청이 나가지 않는다.
4. 로딩 중 버튼이 스피너로 바뀌고 필드가 비활성된다.
5. 백엔드를 끈 상태에서 제출하면 `연결에 실패했어요. 잠시 후 다시 시도해 주세요`가 뜬다.
6. 탭 5개가 보이고 비중·계좌·손익은 `준비 중입니다`를 보여준다.

**검증 방법**
```bash
cd front-end
npm test -- login.test.tsx
npx tsc --noEmit
npx expo start          # 실기기에서 §A.1 도달점의 1·2·8번 확인
```

실기기 확인 절차를 결과와 함께 보고한다 — 로그인 성공, 앱 강제 종료 후 재실행, 오류 문구 3종.

- [x] **Step 1: Button · TextField** — 이 화면에 필요한 props만 둔다. `variant`·`size` 같은 확장은 두 번째 사용처가 생길 때 더한다.
- [x] **Step 2: LoginScreen** — §A.3.1의 배치와 상태 6개.
- [x] **Step 3: Tabs · Placeholder**
- [x] **Step 4: Root · App** — Provider 순서는 `QueryClientProvider` → `AuthProvider` → `NavigationContainer`.
- [x] **Step 5: 테스트** — 빈 값 제출, 서버 401 문구 표시, 성공 시 콜백 호출.
- [x] **Step 6: 커밋** — `feat: 로그인 화면과 탭 네비게이션을 붙인다`

---

## Task 5: 봉투 컴포넌트

**Files:**
- Create: `src/envelope/ScreenFrame.tsx` · `AsOfBanner.tsx` · `NoticeList.tsx` · `EmptyState.tsx` · `ErrorState.tsx`
- Create: `src/ui/Skeleton.tsx`
- Test: `src/__tests__/envelope.test.tsx`

**Interfaces:**
- Produces: `<ScreenFrame envelope={...} screen="summary" onRefresh={...} loading skeleton={...}>` — 화면이 `data`만 그리게 하는 껍데기.

**완료 조건**
1. `info` notice가 배너 둘째 줄에 ` · `로 이어져 나온다.
2. `warn`·`error`가 배너 아래 줄로 쌓이고 3개를 넘으면 접힌다.
3. 화이트리스트(§A.5.3)에 없는 코드는 그리지 않는다 — 골든 `summary.json`의 `STALE_ACCOUNTS`가 요약 화면에서 **나타나지 않는다.**
4. `empty_reason`이 있으면 본문 대신 문구가 나온다.
5. 로딩이면 스켈레톤, 조회 실패면 `ErrorState`와 다시 시도 버튼.
6. `as_of`가 `기준 2026-07-27 15:30` 형식으로 나온다.

**검증 방법**
```bash
cd front-end
npm test -- envelope.test.tsx
npx tsc --noEmit
```

테스트는 골든 3개(`summary.json` · `positions.json` · `allocation-sector-lookthrough.json`)를 입력으로 쓴다. 마지막 것은 notice 4개짜리라 분류·화이트리스트가 한 번에 검증된다.

- [x] **Step 1: AsOfBanner** — 기준 시각 · 새로고침 버튼 · info notice 캡션. 새로고침 중에는 인라인 스피너로 바뀌고 본문은 이전 값을 유지한다.
- [x] **Step 2: NoticeList** — 화이트리스트 상수를 §A.5.3 표 그대로 둔다.
- [x] **Step 3: EmptyState** — `empty_reason` → 문구 매핑.
- [x] **Step 4: ErrorState** — `NetworkError`와 `ApiError`를 나눠 문구를 고른다.
- [x] **Step 5: ScreenFrame** — 위 넷과 스켈레톤의 분기 순서를 한 곳에 둔다: `loading → error → empty → 본문`.
- [x] **Step 6: 커밋** — `feat: 응답 봉투를 다루는 공통 화면 껍데기를 만든다`

---

## Task 6: 요약 화면

**Files:**
- Create: `src/screens/summary/SummaryScreen.tsx` · `HeroBlock.tsx` · `TileGrid.tsx` · `CompositionBar.tsx`
- Create: `src/api/queries/useSummary.ts`
- Create: `src/ui/Card.tsx`
- Test: `src/__tests__/summary.test.tsx`

**Interfaces:**
- Consumes: `ScreenFrame` · 포맷터 · 테마.
- Produces: `useSummary()` — `summary`와 `asset-change?period=THIS_MONTH`를 함께 조회하고 **둘 다 도착했을 때만** 데이터를 내준다.

**완료 조건**
1. 골든 `summary.json` + `asset-change.json`으로 렌더하면 §A.3.2의 값이 모두 화면에 나타난다 — `58,000,000원` · `+4,500,000` · `+9.2%` · `48,800,000` · `+1,200,000` · `8.1%` · `4계좌 · 6종목` · `80.7%` · `19.3%` · `$8,000`.
2. `이번 달 자산 +1,200,000원`이 `closing − opening`으로 계산된다.
3. 두 응답 중 하나라도 로딩이면 스켈레톤이 보이고 부분 렌더가 없다.
4. `daily_change_krw`가 `null`인 응답에서 타일이 `—`를 보여준다.
5. `empty_reason = NO_ACCOUNTS`이면 `연동된 계좌가 없어요`만 보이고 CTA 버튼이 없다.
6. `STALE_ACCOUNTS` notice가 화면에 없다.
7. 누적 막대의 두 조각 폭 비율이 `weight_pct`와 같다.
8. 실기기에서 실제 응답으로 위가 재현된다.

**검증 방법**
```bash
cd front-end
npm test -- summary.test.tsx
npx tsc --noEmit
npx expo start     # 실기기: 로그인 → 요약 화면의 숫자를 golden과 대조
```

- [x] **Step 1: useSummary** — `useQueries`로 둘을 함께 요청하고 `isPending`을 합친다.
- [x] **Step 2: HeroBlock · TileGrid · CompositionBar**
- [x] **Step 3: SummaryScreen 조립** — `ScreenFrame`에 얹는다.
- [x] **Step 4: 링크 동작** — `더보기 →`와 `비중 →`은 이번 범위에서 이동할 화면이 없다. **비활성 대신 `준비 중입니다` 안내를 띄운다**(Placeholder 탭과 같은 문구).
- [x] **Step 5: 골든 렌더 테스트**
- [x] **Step 6: 커밋** — `feat: 요약 화면을 그린다`

---

## Task 7: 종목별 화면

**Files:**
- Create: `src/screens/positions/PositionsScreen.tsx` · `PositionRow.tsx` · `FilterSheet.tsx` · `SortMenu.tsx` · `LensToggle.tsx`
- Create: `src/api/queries/usePositions.ts`
- Create: `src/ui/Chip.tsx` · `BottomSheet.tsx` · `Toggle.tsx` · `Tooltip.tsx` · `Badge.tsx`
- Create: `src/screens/positions/sort.ts`
- Test: `src/__tests__/positions.test.tsx` · `src/__tests__/sort.test.ts`

**Interfaces:**
- Consumes: `useCatalog()` — 필터 선택지.
- Produces: 정렬 함수 `sortRows(rows, key)` — 순수 함수라 단위 테스트로 고정한다.

**완료 조건**
1. 골든 `positions.json`으로 8행이 렌더되고 예수금 2행의 2줄이 `—`다.
2. 정렬 4종이 동작하고 `null`이 항상 끝으로 간다.
3. 필터 시트의 선택지가 카탈로그 응답에서 온다. 코드에 계좌·시장·자산군 값을 박지 않는다.
4. 필터를 걸면 쿼리 키가 바뀌어 재조회되고 합계 줄도 함께 바뀐다.
5. 렌즈 ON이면 2줄이 환산수량만 남고, 시장·자산군 필터가 비활성되며 선택값이 리셋되고, 손익 정렬 2종이 비활성된다.
6. `LENS_METRICS_OMITTED`가 ⓘ 말풍선으로만 나타난다.
7. `CONSTITUENT_UNAVAILABLE`이 warn 줄로 나타난다.
8. `NO_MATCH_FILTER`이면 `조건에 맞는 종목이 없어요`와 `필터 초기화` 버튼이 나오고 칩은 남는다.
9. 종목명이 160pt를 넘으면 뒤쪽이 말줄임되고 금액은 잘리지 않는다.
10. 실기기에서 실제 응답으로 1·2·4·5가 재현된다.

**검증 방법**
```bash
cd front-end
npm test -- positions.test.tsx sort.test.ts
npx tsc --noEmit
npx expo start     # 실기기: §A.1 도달점의 4·5·6·7번
# 카탈로그 응답 확인 — 필터 값 목록이 실제로 무엇인지 눈으로 본다
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/portfolio/catalog | head -60
```

- [x] **Step 1: 카탈로그 확인** — 실제 응답을 보고 §A.4.5의 미정 부분(시장·자산군 값 목록)을 확정한다. 카탈로그에 값이 있으면 그것을 쓰고, 없으면 화면 상수로 두되 그 사실을 코드 주석에 남긴다.
- [x] **Step 2: PositionRow** — 2줄 카드. 말줄임과 폭 우선순위.
- [x] **Step 3: sort.ts** — 순수 함수 + 테스트.
- [x] **Step 4: FilterSheet** — 다중 선택, 렌즈 상태에 따른 비활성.
- [x] **Step 5: LensToggle + Tooltip**
- [x] **Step 6: PositionsScreen 조립**
- [x] **Step 7: 골든 렌더 테스트**
- [x] **Step 8: 커밋** — `feat: 종목별 화면을 그린다`

---

## Task 8: 실기기 검증과 카드 레이아웃 확정

**Files:**
- Modify: `src/screens/positions/PositionRow.tsx` (필요 시)
- Modify: `docs/yhr/plan/2026-08-17-frontend-portfolio-app-plan.md` (확정 결과 반영)
- Create: `front-end/README.md` (실행 방법)

**완료 조건**
1. §A.1 도달점 1~9번이 실기기에서 전부 재현되고, 실행한 절차와 결과가 보고된다.
2. 종목별 카드의 1줄이 실제 데이터에서 어떻게 보이는지 확인하고, 말줄임이 잦으면 아래 순서로 조정한다.
   - 1안: 비중을 2줄 왼쪽으로 옮겨 이름 폭을 205pt로 넓힌다
   - 2안: 비중을 행에서 빼고 비중 분석 화면에 맡긴다
3. 요약 화면이 iPhone SE 크기에서 스크롤 없이 들어가는지 확인한다.
4. `README.md`에 백엔드 기동 · `.env` 설정 · `expo start` 절차가 적힌다.

**검증 방법**
```bash
cd front-end
npx tsc --noEmit && npm test
npx expo start
```

실기기 확인 항목을 하나씩 실행하고 **스크린샷 없이 텍스트로** 결과를 보고한다 — 어느 화면에서 무엇을 눌렀고 무엇이 나왔는지.

- [x] **Step 1: 도달점 1~9 순차 확인**
- [x] **Step 2: 카드 1줄 실측** — 가장 긴 라벨(`TIGER 미국나스닥100`)과 외화 행에서 말줄임 발생 여부
- [x] **Step 3: 조정 필요 시 1안 적용**
- [x] **Step 4: README**
- [x] **Step 5: 커밋** — `docs: 실기기 검증 결과를 반영하고 실행 절차를 적는다`

---

# Part D — 실행 순서와 남은 확인

## D.1 태스크 의존

```
Task 1 (뼈대)
  └─ Task 2 (토큰·포맷터)
       └─ Task 3 (API·인증)
            └─ Task 4 (네비·로그인)
                 └─ Task 5 (봉투)
                      ├─ Task 6 (요약)
                      └─ Task 7 (종목별)
                           └─ Task 8 (실기기 검증)
```

Task 6과 7은 병렬 가능하지만 `ui/` 부품을 서로 만들 수 있으므로 **6을 먼저 끝내고 7을 시작한다.** 7에서 `Card`·`Badge`를 두 번째로 쓰면서 props를 정리한다.

## D.2 착수 전 확인

1. **백엔드가 뜨는지** — §A.7.1 절차로 샘플 데이터까지 넣고 `curl`로 로그인 토큰을 받아본다.
2. **LAN IP와 기기 연결** — 개발 머신과 실기기가 같은 Wi-Fi에 있어야 한다.
3. **의존성 설치가 되는지** — Node 26 · npm 11과 SDK 54의 격차(§A.7.4). Task 1 Step 2에서 막히면 거기서 멈추고 보고한다.

## D.3 다음 단계

나머지 네 화면은 [2차 계획서](./2026-08-30-frontend-remaining-views-plan.md)가 다룬다.

- 비중 분석 · 계좌별 · 실현손익 · 자산 변화 (2차 계획서 Task 9~14)
- 계좌 탭 점 표시와 `STALE_ACCOUNTS` 표현 (계좌별 화면과 함께)
- `react-native-gifted-charts` 도넛(비중 분석) · `react-native-svg` 워터폴(자산 변화)
- 다크모드 — `theme.dark` 팔레트 추가
- 와이어플로우 이미지 갱신 (7화면 논의 완료 후 한 번에)

## D.4 이 계획이 다루지 않는 미결

| 항목 | 상태 |
|---|---|
| Expo Go 유지 vs 개발 빌드 전환 | 미결. 이번 범위는 Expo Go로 성립한다 |
| 웹에서 토큰 저장 | `localStorage`로 간다. 웹을 배포하게 되면 이 자리부터 다시 정한다(§A.7.3) |
| 앱 이름(`app.json`의 `name`·`slug`) | 미정. 현재 `front-end` |
| 계좌 탭 점 표시의 조치 경로 | 계좌별 화면 논의에서 확정 |
