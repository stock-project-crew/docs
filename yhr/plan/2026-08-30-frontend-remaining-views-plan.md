# 포트폴리오 종합 관리 — 프론트엔드 구현 계획 (2차: 비중 분석 · 계좌별 · 실현손익 · 자산 변화)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

- **작성일**: 2026-08-30
- **대상 저장소**: `front-end/` (github.com/stock-project-crew/front-end)
- **근거 스펙**: [`2026-07-28-portfolio-management-spec.md`](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md)
- **선행 계획**: [1차 — 로그인·요약·종목별](./2026-08-17-frontend-portfolio-app-plan.md) (완료)
- **스펙 수정 금지**: 이 계획은 스펙을 인용만 한다.
- **백엔드 수정 금지**: `back-end/`는 고치지 않는다. 필요하면 요청만 남긴다.

**Goal:** 탭 5개가 전부 실제 화면이 되고, 자산 변화까지 포함해 6개 뷰가 모두 동작한다. 화면 간 이동(계좌 → 종목, 요약 → 자산 변화, 실현손익 ↔ 자산 변화)이 연결되고, 기간·필터·축·렌즈 컨트롤이 서버 재조회로 이어진다.

**Architecture:** 1차에서 만든 봉투 처리 구조(`ScreenFrame` · `AsOfBanner` · `NoticeList` · `EmptyState` · `ErrorState`)를 그대로 쓴다. 이번에 새로 생기는 공용 부품은 **기간 컨트롤**과 **계좌 필터**뿐이고, 나머지는 화면별 조립이다. 차트 라이브러리는 쓰지 않는다 — 이번 4화면의 모든 시각 요소가 `View` 두 개로 그려진다.

**전제:** 1차 계획의 Task 1~8이 완료되어 `front-end/src/`에 `api` · `auth` · `design` · `envelope` · `format` · `ui` · `screens`가 서 있다. 이 문서는 그 구조·토큰·API 클라이언트를 **다시 설명하지 않는다.** 코드가 진실의 출처다.

---

## Global Constraints

1차 계획의 Global Constraints가 그대로 유효하다. 이번에 더해지는 것만 적는다.

- **기존 부품을 먼저 찾는다.** 새 컴포넌트를 만들기 전에 `src/ui/`와 `src/envelope/`에 같은 일을 하는 것이 있는지 본다. 종목별의 필터 시트·정렬 메뉴·말풍선은 이번 화면들이 그대로 쓴다.
- **차트 라이브러리를 쓰지 않는다.** `react-native-gifted-charts`와 `react-native-svg`는 Task 9에서 제거한다. 이번 4화면의 막대는 전부 `flex` 비율을 준 `View`다.
- **`data.group_by`로 분기한다.** 축·렌즈 같은 화면 상태가 아니라 **응답이 말하는 것**으로 분기한다. 축을 바꾼 직후 이전 응답이 남아 있는 순간에 잘못된 행에 배지가 붙지 않는다.
- **비율을 클라이언트가 계산하지 않는다.** 예외는 1차와 같다 — 금액 뺄셈(`closing − opening`)과 막대 길이 비율.
- **커밋은 Conventional Commits**, 태스크마다 1커밋.

---

# Part A — 배경

## A.1 도달점

실기기 Expo Go와 웹 브라우저(`http://localhost:8081`) 양쪽에서 아래가 된다.

```
 1. 비중 탭 → 섹터 축 5행 · 순위 막대 · 합계 58,000,000원
 2. 축을 시장으로 바꾸면 2행(국내 80.7 / 미국 19.3)으로 바뀐다
 3. 렌즈 ON → 경고 줄 `1개 ETF는 구성종목 데이터가 없어 분해하지 않았습니다`
 4. 계좌 탭 → 일반 2계좌 · 연금 2계좌, 소계 70.6% / 29.4%
 5. 미래에셋 연금 행에 [07-24 기준] 배지, 상단에 경고 줄
 6. 그룹 헤더를 탭하면 접히고 펴진다
 7. 계좌 행을 탭하면 종목 탭으로 가고 그 계좌 필터가 걸려 있다
 8. 손익 탭 → 올해 -28,000원 (-0.9%), 종목 2행
 9. 삼성전자 행을 펼치면 체결 2건, 03-02 체결에 [추정] 배지
10. 기간을 지정으로 바꾸면 날짜 두 칸이 열리고 적용하면 재조회된다
11. 요약의 `더보기 →` → 자산 변화. 문장 `자산이 120만원 늘었는데 200만원을 넣고 80만원을 잃었어요`
12. 손익 탭 하단 링크 → 같은 기간으로 자산 변화
```

## A.2 이번에 쓰는 기존 자산

| 필요한 것 | 있는 곳 |
|---|---|
| 봉투 처리(배너·경고·빈 상태·오류·로딩) | `src/envelope/ScreenFrame.tsx` |
| 화면별 notice 화이트리스트 | `src/envelope/notices.ts` — **이번에 4화면을 더한다** |
| 숫자·날짜 표기 | `src/format/number.ts` · `date.ts` |
| 색·간격·타이포 | `src/design/` — `useTheme()`으로만 색을 읽는다 |
| 버튼·칩·시트·토글·말풍선·배지·카드·스켈레톤 | `src/ui/` |
| API 클라이언트·401 전역 처리 | `src/api/client.ts` |
| 요청 함수와 쿼리 키 | `src/api/endpoints.ts` · `src/api/queries/keys.ts` |
| 필터 시트 | `src/screens/positions/FilterSheet.tsx` — **`src/ui/`로 올려 공용화한다** |
| 미분해 종목 판정 | `src/envelope/notices.ts`의 `undecomposedKeys()` · `isInstrumentGrain()` — 종목별이 이미 쓴다. 비중 분석이 그대로 재사용한다 |

## A.3 화면 사양

### A.3.1 `allocation` — 비중 분석

```
┌────────────────────────────────────────────┐
│ 기준 2026-07-27 15:30             ↻ 새로고침│
│ USD/KRW 1,400.00 적용 · 기준 2026-07-24     │
├────────────────────────────────────────────┤
│ [종목][ 섹터 ][시장][통화][자산군]           │  세그먼트 h44
│ [전체 계좌 ▾]                               │
│ 구성종목 기준으로 보기  ⓘ            ◯──   │
├────────────────────────────────────────────┤
│ 58,000,000원                        5개 그룹│
├────────────────────────────────────────────┤
│ ● 반도체                23,240,000원  40.1%│
│   ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬░░░░░░░░░░░░░░░░  2종목 │
├────────────────────────────────────────────┤
│ ● 소프트웨어            12,900,000원  22.2%│
│   ▬▬▬▬▬▬▬▬▬░░░░░░░░░░░░░░░░░░░░░░░  2종목 │
├────────────────────────────────────────────┤
│ ● 미분류  ⓘ             11,000,000원  19.0%│
│   ▬▬▬▬▬▬▬░░░░░░░░░░░░░░░░░░░░░░░░░  1종목 │
├────────────────────────────────────────────┤
│ ● IT서비스   6,160,000원 ($4,400)     10.6%│
│   ▬▬▬▬░░░░░░░░░░░░░░░░░░░░░░░░░░░░  1종목 │
├────────────────────────────────────────────┤
│ ● 현금                   4,700,000원   8.1%│
│   ▬▬▬░░░░░░░░░░░░░░░░░░░░░░░░░░░░░        │
└────────────────────────────────────────────┘
```

| 항목 | 결정 |
|---|---|
| 지표 | 평가금액 · 비중 · 종목수. **손익은 행에도 합계에도 두지 않는다** |
| 왜 | 이 화면의 질문은 쏠림이고, 렌즈를 켜면 손익이 사라져 행 모양이 바뀐다 |
| 차트 | 도넛 없음. 순위 막대 리스트만. 전체 100% 막대도 두지 않는다 |
| 왜 | 도넛은 같은 값을 두 번 그리고, 종목 축에서 조각이 수십 개가 되면 색으로 구분되지 않는다 |
| 축 전환 | 세그먼트. **카탈로그의 `enabled === true`인 축만** 그린다(지금 5개, 레버리지 제외) |
| 축 전환 중 | 스켈레톤으로 갈아치우지 않고 이전 리스트를 `opacity 0.4`로 유지 |
| 필터 | 계좌 · 계좌유형. 렌즈를 켜도 **비활성되는 필터가 없다**(계좌 계열만 있어서) |
| 행 순서 | 서버 순서 그대로. `OTHER`(기타)는 서버가 맨 끝에 둔다 |
| 행 탭 | 동작 없음 |
| `key === 'OTHER'` | 화면 라벨을 `기타`로 줄이고 `ⓘ` 탭 시 서버 `label` 전문을 말풍선으로. **문자열이 아니라 키로 분기한다** |
| 섹터 축 미분류 | `axis === 'sector'` && 렌즈 OFF && `UNCLASSIFIED` 행 존재 → 그 행에 `ⓘ`. 문구는 클라이언트가 만든다 |
| 종목수 | `instrument_count === 0`이면 비운다(`—`가 아니다) |
| 종목명 말줄임 | 축이 종목일 때 종목별과 같은 규칙(최대 160pt, 뒤쪽 `…`) |

### A.3.2 `accounts` — 계좌별

```
┌────────────────────────────────────────────┐
│ 기준 2026-07-27 15:30             ↻ 새로고침│
│ USD/KRW 1,400.00 적용 · 기준 2026-07-24     │
├────────────────────────────────────────────┤
│ ⚠ 1개 계좌가 07-24 기준입니다               │
├────────────────────────────────────────────┤
│ 58,000,000원                        4개 계좌│
├────────────────────────────────────────────┤
│ ▾ 일반                  40,960,000원  70.6%│
├────────────────────────────────────────────┤
│   한국투자 위탁         31,960,000원 (55.1%)│
│   예수금 2,560,000     +3,800,000 (+14.8%) │
├────────────────────────────────────────────┤
│   삼성증권               9,000,000원 (15.5%)│
│   예수금 1,000,000     -1,000,000 (-11.1%) │
├────────────────────────────────────────────┤
│ ▾ 연금                  17,040,000원  29.4%│
├────────────────────────────────────────────┤
│   한국투자 IRP          12,000,000원 (20.7%)│
│   예수금 1,000,000     +1,000,000 (+10.0%) │
├────────────────────────────────────────────┤
│   미래에셋 연금 [07-24 기준]                │
│                 5,040,000원 ($3,600) (8.7%)│
│   예수금 140,000         +700,000 (+16.7%) │
└────────────────────────────────────────────┘
```

| 항목 | 결정 |
|---|---|
| 구조 | 계좌유형 2그룹(`GENERAL` · `PENSION` 고정) → 계좌 행 |
| 접기 | **기본 펼침**, 헤더 탭으로 접고 편다. 접힘은 화면 로컬 상태이고 탭을 떠나면 초기화된다. 접힌 헤더에 경고 수를 표시하지 않는다 |
| 소계 | 그룹 헤더 오른쪽 — 금액과 비중 |
| 행 | 1줄 기관명·배지·계좌 총자산·비중 / 2줄 예수금·평가손익 |
| 배지가 있는 행 | 1줄이 두 단으로 접힌다(라벨+배지 / 금액) |
| 뺀 컬럼 | 계좌유형(그룹이 말함) · 마지막 동기화(값이 항상 `null`) · 유가증권 평가금액(유도됨) |
| 비중 | 분모는 전체 총자산. 계좌 4개와 그룹 2개가 각각 100% |
| 행 탭 | **종목 탭으로 이동 + 그 계좌 필터 적용** |
| 그룹 헤더 탭 | 접기·펴기 |
| `+ 계좌 연동` | 두지 않는다(연동 화면이 범위 밖) |
| 탭바 점 | 달지 않는다. 조치 경로가 생길 때 함께 |

**배지 규칙**

| 조건 | 배지 |
|---|---|
| `is_carried_forward === true` | `MM-DD 기준` — `source_as_of`를 포맷 |
| `link_state === 'REAUTH_REQUIRED'` | `재인증 필요` |
| `link_state === 'CONNECTING'` | `연동 중` |
| `link_state === 'DISCONNECTED'` | `연동 해제됨` |
| `link_state === 'CONNECTED'` && 이월 아님 | 배지 없음 |

`is_carried_forward`가 거짓이면 `source_as_of`를 표시하지 않는다 — 화면 `as_of`와 같아 할 말이 없다.

### A.3.3 `realized-pnl` — 실현손익

```
┌────────────────────────────────────────────┐
│ 기준 2026-07-27 15:30             ↻ 새로고침│
├────────────────────────────────────────────┤
│ [이번 달][지난달][ 올해 ][작년][지정]        │
│ [전체 계좌 ▾]                               │
├────────────────────────────────────────────┤
│  올해 실현손익                              │
│  -28,000원   -0.9%                         │  Hero 32
│  취득원가 3,120,000 기준                    │
│  1개 종목은 취득원가를 추정해 계산했습니다   │  캡션·경고색
├────────────────────────────────────────────┤
│ ▸ 삼성전자 [일부 추정]             +277,000│
│   최근 매도 05-12 · 매도 1,100,000  +33.8% │
├────────────────────────────────────────────┤
│ ▾ NAVER                            -305,000│
│   최근 매도 02-18 · 매도 2,000,000  -13.3% │
│  ┌───────────────────────────────────────┐ │
│  │ 02-18   10주               -305,000   │ │
│  │ 매도 2,000,000 · 원가 2,300,000       │ │
│  └───────────────────────────────────────┘ │
├────────────────────────────────────────────┤
│  이 기간 전체 투자손익 보기              → │
└────────────────────────────────────────────┘
```

| 항목 | 결정 |
|---|---|
| 히어로 | 기간 실현손익 금액·률 + `취득원가 N 기준` 캡션 |
| 히어로 아래 캡션 | `SEEDED_ROWS` · `EXCLUDED_ACCOUNTS`. 합계의 성질을 수식하므로 상단 경고 줄이 아니다 |
| 종목 행 2줄 | `최근 매도 MM-DD · 매도 N` + 손익률. **건수는 쓰지 않는다** — 펼치면 보인다 |
| 취득원가 | 펼침에만. `실현손익 = 매도금액 − 취득원가 − 비용`이라 유도되지 않지만 행의 답이 아니다 |
| 펼침 | 체결마다 매도일 · 수량 · 매도금액 · 취득원가 · 실현손익 · 등급 배지 |
| 기간 | 세그먼트 5개. `지정`이면 날짜 두 칸이 열린다 |
| 계좌 | 전체 / 일반 / 연금 / 개별. **유형은 그 유형의 계좌 ID들로 펼쳐 보낸다** — API에 `account_type`이 없다 |
| 정렬 컨트롤 | 없다. 서버 순서(손익 내림차순) |
| 하단 링크 | 같은 기간으로 `asset-change` |

**등급 배지**

| `grade` | 배지 | 탭 시 문구(고정) |
|---|---|---|
| `VERIFIED` | 없음 | — |
| `SEEDED` | `추정` | `취득원가를 추정해 계산했어요. 거래내역이 포지션 시작보다 늦게 확보됐거나, 매매 없이 입고된 종목이에요` |
| `MIXED` | `일부 추정` | `체결마다 취득원가의 근거가 달라요. 펼쳐서 체결별로 확인하세요` |
| `UNAVAILABLE` | `거래내역 없음` | `거래내역이 없어 손익을 계산하지 못했어요` |
| `CONFLICT` | `수량 확인 중` | `거래내역이 아직 도착하지 않았을 수 있어요` |

사유를 두 원인 중 하나로 특정하지 않는다. `position_basis` 테이블이 없어 확보 구간 시작일과 시드 출처를 알 수 없다.

### A.3.4 `asset-change` — 자산 변화

```
┌────────────────────────────────────────────┐
│ ‹  자산 변화                                │
│ [이번 달][지난달][올해][작년][지정]          │
│ [전체 계좌 ▾]                               │
│ 2026-07-01 ~ 2026-07-31 · 07-24부터 계산    │
├────────────────────────────────────────────┤
│ ⚠ 배당·수수료 내역이 확보되지 않아          │
│   투자손익에 섞여 있을 수 있어요             │
│ ⚠ 기간 경계 시점에 1개 계좌가 이월값입니다   │
├────────────────────────────────────────────┤
│  자산이 120만원 늘었는데                     │
│  200만원을 넣고 80만원을 잃었어요            │  Title 20
├────────────────────────────────────────────┤
│  기초자산                       56,800,000 │
│                                            │
│  넣은 돈                        +2,000,000 │
│    입금          ▏▬▬▬▬▬▬▬▬▬▬   +2,000,000 │
│                                            │
│  번 돈                            -800,000 │
│    투자손익  ▬▬▬▬▏                -800,000 │
│  ────────────────────────────────────────  │
│  기말자산                       58,000,000 │
├────────────────────────────────────────────┤
│  투자손익 -800,000원의 내역                 │
│  거래내역이 없어 확정·평가로 나누지 못했어요 │
└────────────────────────────────────────────┘
```

| 항목 | 결정 |
|---|---|
| 진입 | 탭이 아니다. 요약의 `더보기 →`와 실현손익 하단 링크로 들어오는 **스택 화면** |
| 문장 | 클라이언트가 조합. 금액은 **한글 축약**(`120만원`) — 문장형 답변에만 허용된 표기 |
| 막대 | **0 기준 좌우.** 스케일은 `max(|항목 금액|)`. 기초·기말은 숫자만 |
| 왜 | 기초자산 5,680만에 맞추면 200만 항목이 10pt 이하가 되어 보이지 않는다 |
| 색 | **증감만.** 늘어난 항목 빨강 / 줄어든 항목 파랑 / 계좌 편입·제외 회색 |
| 왜 | 출처 색(파랑=넣은 돈, 초록=번 돈)은 손실을 초록으로 칠하고, 앱 전체의 파랑=하락과 충돌한다 |
| 덩어리 구분 | 색이 아니라 그룹 헤더와 들여쓰기 |
| 0인 항목 | 서버가 `breakdown[]`에서 이미 뺀다. 클라이언트는 `account_included`·`account_excluded`가 0이면 그 행을 숨기고, 항목이 하나도 없는 그룹 헤더도 숨긴다 |
| 기간 표기 | 컨트롤 바로 아래. `PERIOD_TRUNCATED`를 이어 붙인다 |
| 분해 블록 | `split_available === false`면 `거래내역이 없어 확정·평가로 나누지 못했어요`. `true`면 확정·평가 두 줄과 `실현손익 뷰 →` |
| `넣은 돈` 행 탭 | 동작 없음(입출금 입력 화면이 범위 밖) |
| 계좌 필터 적용 시 | 각주 `다른 계좌에서 옮긴 돈도 입금으로 표시돼요` |

**문장 조합 규칙** — `Δ = closing − opening`, `D = deposited`, `E = earned`

| 조건 | 문장 |
|---|---|
| Δ>0, E<0 | `자산이 {Δ} 늘었는데 {D}를 넣고 {|E|}를 잃었어요` |
| Δ>0, E>0, D>0 | `자산이 {Δ} 늘었어요. {D}를 넣고 {E}를 벌었어요` |
| Δ>0, D=0 | `자산이 {Δ} 늘었어요. 전부 벌어서예요` |
| Δ<0, E<0 | `자산이 {|Δ|} 줄었어요. {|E|}를 잃었어요` |
| Δ<0, E>0 | `자산이 {|Δ|} 줄었는데 {E}를 벌었어요. {|D|}를 뺐거든요` |
| Δ=0 | `자산이 그대로예요. {D}를 넣고 {|E|}를 잃었어요` |

`D`와 `E`가 둘 다 0이면 둘째 줄을 붙이지 않는다.

## A.4 API 계약 (이번에 더해지는 것)

1차에서 정의한 `Envelope` · `Notice` · `EmptyReason` · `SnapshotViewData`는 그대로다.

```
GET /portfolio/views/allocation   ?axis=&lens=&account=&account_type=
GET /portfolio/views/accounts
GET /portfolio/views/realized-pnl ?period=&from=&to=&account=
GET /portfolio/views/asset-change ?period=&from=&to=&account=
```

`period`: `THIS_MONTH` · `LAST_MONTH` · `THIS_YEAR` · `LAST_YEAR` · `CUSTOM`(`from`·`to` 필수).
`realized-pnl`과 `asset-change`에 **`account_type` 파라미터가 없다.** 계좌유형 선택은 클라이언트가 계좌 ID 목록으로 펼친다.

### 비중 분석 행

`SnapshotViewData`의 `rows[]`를 그대로 쓰되 `instrument_count`가 채워진다. 렌즈 ON이면 `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct`가 빠진다(이 화면은 어차피 쓰지 않는다).

### 계좌별 행 (2단계 중첩)

```ts
type AccountGroupRow = {
  key: 'GENERAL' | 'PENSION';
  label: string;                  // "일반" · "연금"
  rows: AccountRow[];
  market_value_krw: number;
  deposit_krw: number;
  cost_amount_krw: number;
  unrealized_pnl_krw: number;
  unrealized_pnl_pct: number;
  weight_pct: number;
};

type AccountRow = {
  key: string;                    // account_id (uuid)
  label: string;                  // "한국투자 위탁"
  currency?: string;
  market_value_krw: number;       // 계좌 총자산 (예수금 포함)
  market_value_local?: number;
  deposit_krw: number;
  cost_amount_krw: number;
  cost_amount_local?: number;
  unrealized_pnl_krw: number;
  unrealized_pnl_pct: number;
  weight_pct: number;
  link_state: 'CONNECTED' | 'CONNECTING' | 'REAUTH_REQUIRED' | 'DISCONNECTED';
  last_collection: null;          // 항상 null — collection_run 계약 미합의
  last_synced_at: null;           // 항상 null — 동기화 기능 없음
  source_as_of: string;           // "2026-07-24"
  is_carried_forward: boolean;
};
```

그룹 노드에는 `source_as_of` · `is_carried_forward`가 **없다.**

### 실현손익

```ts
type RealizedPnlData = {
  period: { from: string; to: string };
  total: { realized_pnl_krw: number; cost_basis_krw: number; realized_pnl_pct: number };
  rows: {
    key: string; label: string;
    sell_amount_krw: number; cost_basis_krw: number;
    realized_pnl_krw: number; realized_pnl_pct: number;
    first_sold_at: string; last_sold_at: string;
    trade_count: number;
    grade: 'VERIFIED' | 'SEEDED' | 'UNAVAILABLE' | 'CONFLICT' | 'MIXED';
    rows: {
      trade_id: string; sold_at: string; quantity: number;
      sell_amount_krw: number; cost_basis_krw: number; realized_pnl_krw: number;
      grade: 'VERIFIED' | 'SEEDED' | 'UNAVAILABLE' | 'CONFLICT';
    }[];
  }[];
};
```

종목 노드만 `MIXED`를 가질 수 있다. 체결 노드는 4값이다.

### 자산 변화

```ts
type AssetChangeData = {
  period: { from: string; to: string };
  opening: number; closing: number;
  deposited: number; earned: number;
  account_included: number; account_excluded: number;
  breakdown: { type: 'DEPOSIT' | 'WITHDRAW' | 'DIVIDEND' | 'FEE_TAX' | 'INVESTMENT_PNL';
               amount: number }[];
  investment_pnl: { total: number; realized: number | null;
                    unrealized_change: number | null; split_available: boolean };
};
```

`breakdown[]`은 금액이 0인 유형을 담지 않는다. 표시 순서는 `DEPOSIT · WITHDRAW`(넣은 돈) → `INVESTMENT_PNL · DIVIDEND · FEE_TAX`(번 돈)로 **클라이언트가 정렬한다.**

### 항목 라벨

| `type` | 라벨 | 그룹 |
|---|---|---|
| `DEPOSIT` | 입금 | 넣은 돈 |
| `WITHDRAW` | 출금 | 넣은 돈 |
| `INVESTMENT_PNL` | 투자손익 | 번 돈 |
| `DIVIDEND` | 배당 | 번 돈 |
| `FEE_TAX` | 수수료·세금 | 번 돈 |
| — | 계좌 편입 / 계좌 제외 | 그룹 밖 |

## A.5 notice 배치 (`src/envelope/notices.ts` 확장)

| code | 그리는 화면 | 자리 |
|---|---|---|
| `FX_APPLIED` | 전 화면 | 배너 캡션 |
| `CONSTITUENT_AS_OF` | positions · allocation (렌즈 ON) | 배너 캡션 |
| `LENS_METRICS_OMITTED` | positions · allocation | ⓘ 말풍선 (줄로 그리지 않는다) |
| `CONSTITUENT_UNAVAILABLE` | positions · allocation | warn 줄 |
| `STALE_ACCOUNTS` · `REAUTH_REQUIRED` | **accounts** | warn 줄 |
| `SEEDED_ROWS` · `EXCLUDED_ACCOUNTS` | realized-pnl | **히어로 아래 캡션** (warn 줄이 아니다) |
| `CA_UNKNOWN` | realized-pnl | warn 줄 |
| `PERIOD_TRUNCATED` | asset-change | 기간 캡션에 이어 붙임 |
| `CASHFLOW_UNCOVERED` · `BOUNDARY_CARRIED_FORWARD` | asset-change | warn 줄 |

화이트리스트에 없는 코드는 조용히 버린다.

**`CONSTITUENT_UNAVAILABLE`의 `params.keys`** — 분해하지 못한 ETF의 종목 심볼 배열이다. `data.group_by`가 `["instrument"]`일 때만 행에 `미분해` 배지로 쓴다. 판정 함수 `undecomposedKeys()`와 `isInstrumentGrain()`이 `src/envelope/notices.ts`에 이미 있다 — 비중 분석은 축이 종목일 때 같은 함수를 부른다. 섹터·시장·통화·자산군 축에서는 행 키가 심볼이 아니고 한 행에 여러 종목이 묶여 있어 대응되지 않는다 — 경고 줄로만 쓴다.

## A.6 화면 상태 전수

| 화면 | 상태 |
|---|---|
| `allocation` | default / 로딩 / 축 전환 중(이전 리스트 흐리게) / 렌즈 ON / 구성종목 미확보 warn / 섹터 축 미분류 ⓘ / `NO_HOLDINGS` / `NO_MATCH_FILTER` / `NO_ACCOUNTS` / 조회 실패 |
| `accounts` | default / 로딩 / 그룹 접힘 / 이월 배지 / 재인증 배지 / 상단 warn / `NO_ACCOUNTS` / 조회 실패 |
| `realized-pnl` | default / 로딩 / 체결 펼침 / 추정 배지 / 혼합 배지 / 미포함 계좌 캡션 / 지정 기간 입력 / `NO_TRADES_IN_PERIOD` / `ALL_UNAVAILABLE` / `NO_ACCOUNTS` / 조회 실패 |
| `asset-change` | default / 로딩 / 손실 케이스 / 분해 생략 / 분해 표시 / 계좌 편입·제외 / `PERIOD_TRUNCATED` / 경고 2종 / 계좌 필터 각주 / 조회 실패 |

빈 상태 문구:

```
allocation      NO_HOLDINGS        보유 중인 자산이 없어요
                NO_MATCH_FILTER    조건에 맞는 자산이 없어요
accounts        NO_ACCOUNTS        연동된 계좌가 없어요
realized-pnl    NO_TRADES_IN_PERIOD 이 기간에 매도한 종목이 없어요
                ALL_UNAVAILABLE    거래내역이 확보된 계좌가 없어요
```

`NO_TRADES_IN_PERIOD`일 때도 기간·계좌 컨트롤은 그대로 남긴다. 다른 기간을 바로 눌러볼 수 있어야 한다.

## A.7 의존성 변경

```bash
npm uninstall react-native-gifted-charts react-native-svg
npx expo install @react-native-community/datetimepicker
```

- **차트 라이브러리 둘을 뺀다.** 도넛을 두지 않기로 했고 자산 변화 막대는 `View`로 그린다. 어느 화면도 import 하지 않는다.
- **날짜 피커를 넣는다.** `지정` 기간에 필요하다. `expo/bundledNativeModules.json`에 `@react-native-community/datetimepicker: 8.4.4`가 있어 **Expo Go에서 동작한다** — 개발 빌드가 필요 없다.

## A.8 환경 변화 (1차 이후)

| 항목 | 지금 값 |
|---|---|
| 로그인 계정 | **`yhr@a.com`** / `local-dev-password` (백엔드 `5e44f6a`에서 짧은 주소로 바뀜) |
| 웹 개발 | **가능하다.** 백엔드 `abdb811`이 `local` 프로파일에 한해 `http://localhost:8081` 출처를 허용한다(`POST /auth/login` · `GET /portfolio/**`) |
| 실기기 | 1차와 같다. `EXPO_PUBLIC_API_BASE_URL`에 LAN IP |

**웹을 개발 경로로 쓴다.** 레이아웃 확인이 실기기 없이 되므로 반복이 빨라진다. 다만 **최종 확인은 실기기로** 한다 — 폰트 렌더와 폭이 다르다.

## A.9 골든 픽스처 최신화

백엔드 골든이 세 번 바뀌었다. `src/fixtures/golden/`을 다시 복사해야 한다.

| 파일 | 변화 |
|---|---|
| `accounts.json` | 계좌 행에 `source_as_of` · `is_carried_forward` 추가 (백엔드 `60b4f9c`) |
| `allocation-sector-lookthrough.json` | `CONSTITUENT_UNAVAILABLE`의 `message`에서 금액이 빠지고 `params.keys` 추가 (백엔드 `ee49d9a`) |

나머지 다섯 파일은 그대로다. `positions.json`은 `lens=DIRECT`라 이 안내가 애초에 실리지 않는다.

---

# Part B — 새로 생기는 파일

```
src/
├── ui/
│   ├── FilterSheet.tsx          ← screens/positions/ 에서 올려 공용화
│   ├── SegmentedControl.tsx     축·기간 세그먼트
│   ├── PeriodControl.tsx        세그먼트 5개 + 지정 날짜 두 칸
│   └── ProportionBar.tsx        비중 막대 (0~100%)
├── api/
│   └── queries/
│       ├── useAllocation.ts
│       ├── useAccounts.ts
│       ├── useRealizedPnl.ts
│       └── useAssetChange.ts
├── app/navigation/
│   └── RootStack.tsx            Tabs + asset-change 스택
└── screens/
    ├── allocation/  AllocationScreen · AllocationRow · AxisSegments
    ├── accounts/    AccountsScreen · AccountGroup · AccountRow · StateBadge
    ├── realizedPnl/ RealizedPnlScreen · PnlRow · TradeList · GradeBadge
    └── assetChange/ AssetChangeScreen · Sentence · FlowList · FlowBar · SplitBlock
```

`AccountRow`는 계좌별 화면의 컴포넌트 이름이고 `api/types.ts`의 응답 타입과 이름이 겹친다. 타입 쪽을 `AccountRowData`로 두어 구분한다.

---

# Part C — 태스크

## Task 9: 정리 · 공용 부품 · 네비게이션 확장

**Files:**
- Modify: `package.json` · `src/envelope/notices.ts` · `src/app/Root.tsx` · `src/app/navigation/types.ts`
- Move: `src/screens/positions/FilterSheet.tsx` → `src/ui/FilterSheet.tsx`
- Create: `src/ui/SegmentedControl.tsx` · `src/ui/PeriodControl.tsx` · `src/ui/ProportionBar.tsx`
- Create: `src/app/navigation/RootStack.tsx`
- Modify: `src/fixtures/golden/*.json` (재복사)
- Test: `src/__tests__/period.test.ts` · `notices.test.ts`(확장)

**Interfaces:**
- Produces: `<PeriodControl value onChange />` — `realized-pnl`과 `asset-change`가 함께 쓴다.
- Produces: `RootStack` — 탭 위에 `asset-change`를 얹는다. 요약과 실현손익이 여기로 이동한다.
- Produces: 화이트리스트에 4화면 추가.

**완료 조건**
1. `react-native-gifted-charts` · `react-native-svg`가 `package.json`에서 사라지고 `npx tsc --noEmit`과 `npm test`가 통과한다. 두 패키지를 import 하는 코드가 없다.
2. `@react-native-community/datetimepicker`가 설치되고 실기기에서 피커가 뜬다.
3. `PeriodControl`이 프리셋 5개와 지정 날짜 두 칸을 제공하고, `시작 > 종료`면 `적용`이 비활성된다.
4. 종료일 상한이 기기 시계 오늘이다.
5. `RootStack`에서 `asset-change`로 push·pop이 된다(화면은 아직 `Placeholder`).
6. 골든 7개가 백엔드 원본과 같다.
7. 화이트리스트 테스트가 6개 화면을 모두 검증한다.

**검증 방법**
```bash
cd front-end
grep -rn "gifted-charts\|react-native-svg" src package.json   # 결과 없음
npx tsc --noEmit && npm test
for f in ../back-end/src/test/resources/golden/*.json; do
  diff "$f" "src/fixtures/golden/$(basename $f)" || echo "DIFF: $f"
done                                                          # 출력 없음
npx expo start --web                                          # 탭 전환 · 스택 push 확인
```

- [ ] **Step 1: 차트 라이브러리 제거** — import 여부를 먼저 grep으로 확인한 뒤 uninstall.
- [ ] **Step 2: 날짜 피커 설치**
- [ ] **Step 3: 골든 재복사** — `cp ../back-end/src/test/resources/golden/*.json src/fixtures/golden/`
- [ ] **Step 4: `FilterSheet` 공용화** — 계좌·계좌유형 그룹을 받을 수 있게 props를 넓힌다. 종목별의 사용처가 깨지지 않는지 테스트로 확인.
- [ ] **Step 5: `SegmentedControl` · `PeriodControl` · `ProportionBar`**
- [ ] **Step 6: `RootStack`** — `Root.tsx`가 `Tabs` 대신 `RootStack`을 렌더한다.
- [ ] **Step 7: `notices.ts` 확장** — A.5 표 그대로.
- [ ] **Step 8: 커밋** — `chore: 차트 라이브러리를 걷어내고 기간·필터 공용 부품을 세운다`

---

## Task 10: 비중 분석

**Files:**
- Create: `src/screens/allocation/*` · `src/api/queries/useAllocation.ts`
- Modify: `src/api/endpoints.ts` · `src/api/queries/keys.ts` · `src/api/types.ts` · `src/app/navigation/Tabs.tsx` · `src/screens/summary/SummaryScreen.tsx`
- Test: `src/__tests__/allocation.test.tsx`

**완료 조건**
1. 골든 `allocation-sector.json`으로 5행이 렌더되고 `반도체 23,240,000원 40.1% 2종목`이 화면에 나타난다.
2. 축 세그먼트가 카탈로그의 `enabled` 축만 그린다(레버리지 없음).
3. 축을 바꾸면 쿼리 키가 바뀌어 재조회되고, 전환 중 이전 리스트가 흐리게 유지된다.
4. 렌즈 ON에서 `CONSTITUENT_UNAVAILABLE`이 warn 줄로, `LENS_METRICS_OMITTED`가 ⓘ 말풍선으로 나타난다.
5. 손익이 화면 어디에도 없다.
6. `CASH` 행의 종목수 자리가 비어 있다.
7. 섹터 축 + 렌즈 OFF에서 `미분류` 행에 ⓘ가 붙고 탭하면 안내가 뜬다.
8. `key === 'OTHER'` 행이 오면 라벨이 `기타`로 줄고 ⓘ에 전문이 뜬다. 골든에는 이 행이 없으므로 **손으로 만든 픽스처**로 검증한다(골든 폴더가 아니라 테스트 파일 안에 둔다).
9. 축이 종목일 때 `undecomposedKeys()`로 `미분해` 배지가 붙는다.
10. **요약 화면의 `비중 →`이 비중 탭으로 이동한다**(시장 축을 선택한 상태). 1차에서 `준비 중입니다` 안내로 막아둔 자리다.

**검증 방법**
```bash
cd front-end
npm test -- allocation.test.tsx
npx tsc --noEmit
npx expo start --web     # 축 5개 전환 · 렌즈 토글
```

- [ ] Step 1: 타입·엔드포인트·쿼리 키
- [ ] Step 2: `AxisSegments` — 카탈로그에서 축 목록
- [ ] Step 3: `AllocationRow` — 2줄 + 비중 막대
- [ ] Step 4: `AllocationScreen` 조립
- [ ] Step 5: `OTHER` · `UNCLASSIFIED` 도움말 · 종목 축 `미분해` 배지
- [ ] Step 6: 요약의 `비중 →` 연결 (`SummaryScreen`의 준비 중 안내 제거)
- [ ] Step 7: 골든 렌더 테스트 + `OTHER` 픽스처
- [ ] Step 8: 커밋 — `feat: 비중 분석 화면을 그린다`

---

## Task 11: 계좌별

**Files:**
- Create: `src/screens/accounts/*` · `src/api/queries/useAccounts.ts`
- Modify: `src/api/types.ts` · `endpoints.ts` · `keys.ts` · `Tabs.tsx` · `src/screens/positions/PositionsScreen.tsx`(라우트 파라미터 수신)
- Test: `src/__tests__/accounts.test.tsx`

**완료 조건**
1. 골든 `accounts.json`으로 2그룹 4계좌가 렌더되고 소계가 `40,960,000원 70.6%` · `17,040,000원 29.4%`다.
2. 미래에셋 연금 행에만 `07-24 기준` 배지가 붙는다.
3. 그룹 헤더 탭으로 접히고 펴진다. 접힌 헤더에 경고 수를 표시하지 않는다.
4. 상단에 `1개 계좌가 07-24 기준입니다` warn 줄이 뜬다.
5. 계좌 행을 탭하면 종목 탭으로 이동하고 **그 계좌 필터가 적용된 상태**로 열린다. 필터 칩에 계좌명이 보인다.
6. `Σ 그룹 소계 = 58,000,000`이 요약 화면의 총자산과 같다.

**검증 방법**
```bash
cd front-end
npm test -- accounts.test.tsx
npx tsc --noEmit
npx expo start --web    # 계좌 → 종목 이동 후 필터 칩 확인
```

- [ ] Step 1: 중첩 응답 타입(`AccountGroupRow` · `AccountRowData`)
- [ ] Step 2: `AccountGroup`(헤더·접기) · `AccountRow` · `StateBadge`
- [ ] Step 3: 행 탭 → 종목 탭 이동. `TabParamList`에 `positions: { account?: string[] }` 추가
- [ ] Step 4: `PositionsScreen`이 라우트 파라미터를 초기 필터로 받는다
- [ ] Step 5: 골든 렌더 테스트
- [ ] Step 6: 커밋 — `feat: 계좌별 화면을 그린다`

---

## Task 12: 실현손익

**Files:**
- Create: `src/screens/realizedPnl/*` · `src/api/queries/useRealizedPnl.ts`
- Modify: `src/api/types.ts` · `endpoints.ts` · `keys.ts` · `Tabs.tsx`
- Test: `src/__tests__/realizedPnl.test.tsx`

**완료 조건**
1. 골든으로 히어로 `-28,000원 -0.9%`, 캡션 `취득원가 3,120,000 기준`, 종목 2행이 렌더된다.
2. 삼성전자 행에 `일부 추정` 배지, 펼치면 체결 2건이 나오고 03-02 체결에 `추정` 배지가 붙는다.
3. `SEEDED_ROWS` 문구가 히어로 아래 캡션에 있다(상단 warn 줄이 아니다).
4. 기간 세그먼트 5개가 동작하고 `지정`에서 날짜 두 칸이 열린다.
5. 계좌 필터에서 `연금`을 고르면 그 유형의 계좌 ID들이 `account` 파라미터로 나간다.
6. 하단 링크가 **같은 기간으로** 자산 변화를 연다.
7. 2줄에 건수를 쓰지 않고 `최근 매도 05-12 · 매도 1,100,000`으로 나온다.

**검증 방법**
```bash
cd front-end
npm test -- realizedPnl.test.tsx
npx tsc --noEmit
npx expo start --web
# 계좌유형 전개 확인 — 네트워크 탭에서 account 파라미터가 두 개 나가는지
```

- [ ] Step 1: 중첩 타입과 엔드포인트(`from`·`to` 포함)
- [ ] Step 2: `PnlRow` · `TradeList` · `GradeBadge`(고정 문구 말풍선)
- [ ] Step 3: 계좌유형 → 계좌 ID 전개
- [ ] Step 4: 히어로와 캡션
- [ ] Step 5: 골든 렌더 테스트
- [ ] Step 6: 커밋 — `feat: 실현손익 화면을 그린다`

---

## Task 13: 자산 변화

**Files:**
- Create: `src/screens/assetChange/*` · `src/api/queries/useAssetChange.ts`(1차의 요약용 조회를 확장)
- Modify: `src/app/navigation/RootStack.tsx` · `src/screens/summary/SummaryScreen.tsx`(`더보기 →` 연결)
- Test: `src/__tests__/assetChange.test.tsx` · `sentence.test.ts`

**완료 조건**
1. 골든으로 문장이 `자산이 120만원 늘었는데 200만원을 넣고 80만원을 잃었어요`로 나온다.
2. 문장 조합 6가지 분기가 단위 테스트로 고정된다.
3. 막대가 0 기준 좌우로 그려지고, 입금(+200만)이 투자손익(-80만)보다 2.5배 길다.
4. 색이 증감만 뜻한다 — 입금 빨강, 투자손익 파랑.
5. `account_included`·`account_excluded`가 0이라 그 행이 없다.
6. `split_available: false`라 분해 자리에 `거래내역이 없어 확정·평가로 나누지 못했어요`가 나온다.
7. `PERIOD_TRUNCATED`가 기간 캡션에 이어 붙고, 나머지 warn 2개가 경고 줄로 쌓인다.
8. 요약의 `더보기 →`와 실현손익 하단 링크가 이 화면을 연다. 뒤로 가기가 동작한다.
9. 차트 라이브러리를 쓰지 않는다.

**검증 방법**
```bash
cd front-end
npm test -- assetChange.test.tsx sentence.test.ts
npx tsc --noEmit
npx expo start --web
```

- [ ] Step 1: 문장 조합 순수 함수 + 테스트
- [ ] Step 2: `FlowBar`(0 기준 좌우) · `FlowList`(그룹·숨김 규칙)
- [ ] Step 3: `SplitBlock`
- [ ] Step 4: 스택 연결 두 곳
- [ ] Step 5: 골든 렌더 테스트
- [ ] Step 6: 커밋 — `feat: 자산 변화 화면을 그린다`

---

## Task 14: 통합 검증

**Files:**
- Modify: `front-end/README.md`
- Modify: 필요 시 각 화면(실기기 확인 결과 반영)

**완료 조건**
1. §A.1 도달점 1~12번이 **실기기에서** 재현되고 절차와 결과가 보고된다.
2. 웹에서도 같은 흐름이 동작한다(로그인 포함 — CORS 허용됨).
3. 화면 간 이동 4종이 상태를 잃지 않는다 — 계좌→종목(필터), 요약→자산변화, 손익→자산변화(기간), 자산변화→손익(기간).
4. 종목별 카드 1줄의 말줄임 발생 여부를 실기기에서 확인하고, 잦으면 비중을 2줄로 내린다(1차 계획 Task 8의 미결).
5. `npx tsc --noEmit`과 `npm test`가 통과한다.
6. README에 계정(`yhr@a.com`)과 웹 개발 경로가 반영된다.

**검증 방법**
```bash
cd front-end
npx tsc --noEmit && npm test
npx expo start        # 실기기
npx expo start --web  # 브라우저
```

- [ ] Step 1: 실기기 도달점 12개 확인
- [ ] Step 2: 웹 동작 확인
- [ ] Step 3: 화면 간 이동 4종
- [ ] Step 4: 종목별 카드 말줄임 판단
- [ ] Step 5: README 갱신
- [ ] Step 6: 커밋 — `docs: 6개 뷰 통합 검증 결과를 반영한다`

---

# Part D — 실행 순서와 남은 미결

## D.1 의존

```
Task 9 (정리·공용 부품)
  ├─ Task 10 (비중 분석)
  ├─ Task 11 (계좌별)
  ├─ Task 12 (실현손익) ─┐
  └─ Task 13 (자산 변화) ┘  ← 12·13은 PeriodControl을 공유한다. 12를 먼저
        └─ Task 14 (통합 검증)
```

Task 10·11은 서로 독립이라 순서가 자유롭다. 12와 13은 기간 컨트롤을 함께 쓰므로 12를 먼저 끝내고 13에서 다듬는다.

## D.2 남은 미결

| 항목 | 상태 |
|---|---|
| 앱 이름(`app.json`의 `name`·`slug`) | 미정. 현재 `front-end` |
| 탭바 `계좌` 점 표시 | 동기화 경로가 생길 때. 조치 없는 알림은 달지 않는다 |
| 종목 상세 · 계좌 연동 4화면 · 동기화 | 범위 밖. API·팀 합의 대기 |
| 입출금 입력 화면 | 범위 밖. 자산 변화의 `넣은 돈` 행이 갈 곳 |
| `position_basis` | 없다. 등급 사유를 두 원인으로 분기하지 못한다 |
| 다크모드 | `theme.dark` 팔레트 추가로 열린다 |
| Expo Go 유지 vs 개발 빌드 | 미결. 이번 범위는 Expo Go로 성립한다 |
| 와이어플로우 이미지 갱신 | 7화면 확정 반영 대기 |
