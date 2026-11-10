# 종목 상세 설계 — `GET /portfolio/instruments/{id}`와 `instrument-detail` 화면

[포트폴리오 스펙](2026-07-28-portfolio-management-spec.md) §2.10의 종목 상세를 백엔드와 앱에 구현하는 설계다. 스펙이 정한 것(무엇을 보여 주나)은 다시 적지 않고, 스펙이 열어 둔 것(응답의 모양, 보유하지 않은 종목의 동작, 문구, 거래내역의 범위)을 정한다. 스펙 본문에 담긴 곳은 [§7](#7-스펙과의-관계)에 모았다. 스펙과 이 문서가 다르면 스펙이 맞다.

| 근거 | 위치 |
|---|---|
| 화면 · 진입 · 상태 | 스펙 §2.5(하위) · §2.10 · §10 · 와이어플로우 P13 · [앱 정보 구조](../app-information-architecture.md) §2.2 · §2.5 |
| 원가 기준 두 가지 · 등급 · `ca_unknown` | 스펙 §4.1 · §4.3 · §4.4 · §4.5 |
| 스코프 · 봉투 · 오류 | 스펙 §3.8 · §8.2 · §8.5 · §8.6 · §8.8 · §9.3 |
| 평단 · 등급의 저장 모양 | [평단 계산 설계](2026-10-29-position-basis-design.md) · 마이그레이션 `V13__position_basis.sql` |
| 거래 · 기업행위 원천 | 데이터 미러 `V12__trade_ca_mirror.sql` |

## 1. 범위

**만든다**

- 백엔드: `GET /portfolio/instruments/{id}`.
- 백엔드: 종목별 응답(`GET /portfolio/views/positions`)의 행에 `instrument_id`를 싣는다. 앱이 상세를 열 키다.
- 앱: `instrument-detail` 스택 화면, 종목별 행 누름, 화면의 `알림 걸기` → 종목이 채워진 새 알림 흐름.
- 백엔드: 알림 쪽 "보유 중" 판정을 포트폴리오 화면과 같은 스냅샷으로 맞추고, 확정 전 보유를 확인 불가 사유 `AWAITING_FINAL`로 판정한다(§3.8). 앱: 그 사유의 카드 문구.

**만들지 않는다**

- 종목 상세 안의 필터 · 기간 선택 · 페이지 나누기. 거래내역은 전 기간을 한 번에 내린다(§3.4).
- 종목별 화면 외의 진입 경로(알림 상세 → 종목 상세 등). 응답은 어느 진입에서도 성립하게 만들지만(§3.6) 이번에 진입을 늘리지 않는다.
- 등급 재판정. 등급과 `ca_unknown`은 평단 계산 배치가 저장한 값을 그대로 읽는다(스펙 §4.4 "판정 시점을 고정한다").
- 거래내역 · 기업행위 원천의 변경. 데이터팀 테이블은 읽기만 한다.

## 2. 데이터 현황과 전제

| 재료 | 그레인 | 이 화면에서 쓰는 것 | 전제 |
|---|---|---|---|
| `position_line` | (as_of, 계좌, 종목) | 보유 요약 · 계좌별 분해 | 종목별 화면과 **같은 `as_of`**(그 사용자의 최신 스냅샷)를 쓴다. 연동을 해제한 계좌는 뺀다 — 종목별 화면과 같은 스코프 조각 |
| `position_basis` | (계좌, 종목) | 계좌별 등급 · 확보 시작일 · `ca_unknown` | **계좌마다 한 행**이다. 수량이 0이면 행이 없다. `UNAVAILABLE` · `CONFLICT`이면 `avg_cost_*`가 비어 있다. 평단 계산이 아직 돌지 않은 계좌도 행이 없다 |
| `realized_pnl_line` | 매도 체결 1건 | 실현손익 목록과 합계 | 계좌 소유로 스코프한다. 연동을 해제한 계좌의 행도 포함한다 — 실현손익 뷰와 같다 |
| `data.cln_trade` | 체결 1건 | 거래내역 | `account_ref`로 계좌에 붙인다. `instrument_id`가 있다. 해제한 계좌의 체결도 포함한다 |
| `data.corporate_action` | (종목, ex_date, type) | 기업행위 이력 | 종목 단위라 스코프와 무관하다 |
| `instrument` | 종목 | 이름 · 시장 · 통화 · 자산군 · 상장폐지일 | 마스터는 사용자 공용이다 |
| `adjusted_price_daily` | (종목, 날짜) | 직전 종가 · 거래일 | `알림 걸기`가 가격 칸을 채우는 값. 종목 검색(`GET /instruments`)과 같은 규칙(가장 최근 일봉) |

**`realized_pnl_line`과 `cln_trade`는 따로 읽는다.** 운영에서는 실현손익 행이 체결에서 만들어지므로 `trade_id`가 맞물리지만, 로컬 샘플(`sample_portfolio.sql`)은 `cln_trade`를 비운 채 실현손익 행만 둔다. 두 목록을 `trade_id`로 엮어 한쪽을 다른 쪽에 종속시키면 체결이 없는 실현손익이 화면에서 사라진다. 응답도 두 블록으로 낸다(§3.3 · §3.4).

**`position_basis`의 SEEDED 사유는 `seed_permanent`로 정해진다.** `seed_permanent = true`이면 `NOT_TRADED`, 아니면 `LATE_COVERAGE`이고 그때만 `coverage_start_at`이 있다. 실현손익 행의 `seed_reason`과 같은 규칙이다.

## 3. API 계약

### 3.1 요청과 실패

```
GET /portfolio/instruments/{id}
Authorization: Bearer <token>
```

| 상황 | 응답 |
|---|---|
| `{id}`가 UUID가 아니다 | `404` `INSTRUMENT_NOT_FOUND` |
| 종목 마스터에 없다 | `404` `INSTRUMENT_NOT_FOUND` |
| 예수금 의사종목(`asset_class = CASH`) | `404` `INSTRUMENT_NOT_FOUND` |
| 마스터에 있으나 내 보유 · 체결 · 실현손익이 없다 | `200`, 아래 §3.6 |
| 토큰 없음 · 만료 | `401` `UNAUTHENTICATED`(공통) |

`403`은 쓰지 않는다. 종목 마스터는 공용이라 종목 ID가 있다는 사실은 숨길 정보가 아니고, 응답의 나머지는 전부 내 계좌로 스코프된다. 오류 본문은 `{ "error": { "code", "message" } }`(스펙 §8.6)다.

### 3.2 응답

스펙 §8.2 봉투를 그대로 쓴다. `as_of`는 보유 블록이 쓴 스냅샷의 배너 시각이다(다른 뷰와 같은 `BannerAsOf`). 스냅샷이 하나도 없으면 다른 뷰처럼 최신 시각 규칙을 따른다.

로컬 샘플(`yhr@a.com`, 삼성전자)의 응답이다.

```json
{
  "as_of": "2026-07-27T15:30:00+09:00",
  "data": {
    "instrument": {
      "id": "10000000-0000-0000-0000-000000000001",
      "symbol": "005930", "label": "삼성전자",
      "market": "KR", "currency": "KRW",
      "delisted_on": null,
      "last_close": 71200, "last_close_on": "2026-07-27"
    },
    "position": {
      "quantity": 200, "avg_cost": 60000,
      "cost_amount_krw": 12000000, "market_value_krw": 14240000,
      "unrealized_pnl_krw": 2240000, "unrealized_pnl_pct": 18.7
    },
    "by_account": [
      { "account_id": "20000000-0000-0000-0000-000000000001",
        "label": "한국투자 위탁", "account_type": "GENERAL",
        "quantity": 200, "avg_cost": 60000,
        "market_value_krw": 14240000,
        "is_carried_forward": false, "source_as_of": "2026-07-27T15:30:00+09:00",
        "basis": null }
    ],
    "realized": {
      "total": { "realized_pnl_krw": 277000, "excluded_account_count": 0 },
      "rows": [
        { "trade_id": "T-0002", "account_id": "20000000-0000-0000-0000-000000000001",
          "account_label": "한국투자 위탁",
          "sold_at": "2026-05-12", "quantity": 5,
          "sell_amount_krw": 700000, "cost_basis_krw": 500000,
          "realized_pnl_krw": 198000, "grade": "VERIFIED", "ca_unknown": false },
        { "trade_id": "T-0001", "account_id": "20000000-0000-0000-0000-000000000001",
          "account_label": "한국투자 위탁",
          "sold_at": "2026-03-02", "quantity": 3,
          "sell_amount_krw": 400000, "cost_basis_krw": 320000,
          "realized_pnl_krw": 79000, "grade": "SEEDED",
          "seed_reason": "LATE_COVERAGE", "coverage_start_at": "2026-01-01",
          "ca_unknown": false }
      ]
    },
    "trades": [],
    "corporate_actions": []
  },
  "empty_reason": null,
  "notices": []
}
```

`last_close` 값은 예시다. 샘플의 실제 값은 백엔드 골든 응답(§5.1)이 정한다.

### 3.3 필드

**`instrument`**

| 필드 | 출처 | 비고 |
|---|---|---|
| `id` · `symbol` · `label` · `market` · `currency` | `instrument` | `label`은 `name`. `market`은 `KR` · `US`, `currency`는 `KRW` · `USD` |
| `delisted_on` | `instrument.delisted_on` | 값이 있으면 앱이 `알림 걸기`를 두지 않는다(§4.5) |
| `last_close` · `last_close_on` | 그 종목의 가장 최근 `adjusted_price_daily` | 없으면 둘 다 `null` |

**`position`** — 그 `as_of`의 연동 유효 계좌 라인을 합산한다. 라인이 없으면 `position = null`. 집계 전에 종목별 응답과 같은 라인 불변식 검사(`PositionLineInvariants.validate`)를 돈다 — 종목별이 정합성 오류로 실패하는 날 상세만 숫자를 보여 주지 않게.

| 필드 | 계산 | 비고 |
|---|---|---|
| `quantity` | `Σ quantity` | |
| `avg_cost` | `Σ cost_amount_local ÷ Σ quantity` | 현지 통화. 종목별 응답의 `avg_cost`와 같은 식 · 같은 반올림(통화 소수 자릿수, HALF_UP)이라 PF10-01이 두 값을 비교한다 |
| `cost_amount_krw` · `market_value_krw` | `Σ` | |
| `unrealized_pnl_krw` | `market_value_krw − cost_amount_krw` | |
| `unrealized_pnl_pct` | `unrealized_pnl_krw ÷ cost_amount_krw × 100` | 종목별 응답과 같은 반올림. 분모가 0이면 `null` |
| `market_value_local` · `cost_amount_local` | `Σ` | **외화 종목에만** 싣는다. 원화 종목은 키가 없다 — 종목별 응답의 단일 통화 규칙과 같다 |

비율과 평단은 합산 후에 계산한다(스펙 §1.5 · §9.2). 종목별 응답의 집계 코드를 그대로 쓰거나 같은 식을 쓰고, 두 값이 같다는 것을 테스트가 확인한다(§5.1).

**`by_account[]`** — 위 라인을 계좌별로. 정렬은 `market_value_krw` 내림차순, 같으면 `account_id` 오름차순.

| 필드 | 계산 |
|---|---|
| `account_id` · `label` · `account_type` | `account` |
| `quantity` · `avg_cost` · `market_value_krw` | 그 계좌 라인. `avg_cost = cost_amount_local ÷ quantity`, 반올림은 `position.avg_cost`와 같다 |
| `market_value_local` | 외화 종목에만 |
| `is_carried_forward` · `source_as_of` | 그 계좌 라인의 `position_line.is_carried_forward` · `source_as_of`. `source_as_of`는 서울 오프셋(`+09:00`)을 붙인 ISO 시각이다. 수집이 실패해 직전 값을 이어 쓴 계좌는 화면 기준 시각보다 이른 값을 갖는다 |
| `basis` | 그 (계좌, 종목)의 `position_basis`. 행이 없으면 `null` |

`basis`의 모양:

```json
{ "grade": "SEEDED", "seed_reason": "LATE_COVERAGE",
  "coverage_start_at": "2026-01-01", "ca_unknown": false }
```

| 필드 | 출처 |
|---|---|
| `grade` | `position_basis.grade` — `VERIFIED` · `SEEDED` · `UNAVAILABLE` · `CONFLICT` |
| `seed_reason` | `SEEDED`일 때만. `seed_permanent`이면 `NOT_TRADED`, 아니면 `LATE_COVERAGE` |
| `coverage_start_at` | `LATE_COVERAGE`일 때만 |
| `ca_unknown` | `position_basis.ca_unknown` |

`seed_reason` · `coverage_start_at`은 값이 없으면 키를 뺀다 — 실현손익 뷰의 체결 노드와 같다.

`Σ by_account.quantity = position.quantity`가 항상 성립한다(PF10-02).

**`realized`** — 그 종목의 `realized_pnl_line` 전부(전 기간), 내 계좌 소유분.

| 필드 | 규칙 |
|---|---|
| `rows[]` | `grade`가 `VERIFIED` · `SEEDED`인 행. 정렬은 매도 시각 내림차순, 같으면 `trade_id` 오름차순 |
| `rows[].*` | 실현손익 뷰의 체결 노드와 같은 이름 · 규칙(`trade_id` · `sold_at` · `quantity` · `sell_amount_krw` · `cost_basis_krw` · `realized_pnl_krw` · `grade` · `seed_reason` · `coverage_start_at`)에 `account_id` · `account_label` · `ca_unknown`을 더한다. `sold_at`은 서울 날짜(`YYYY-MM-DD`)다. `account_label`은 `account.label`이다 — 이미 다 판 계좌와 연동을 해제한 계좌는 `by_account`에 없어 앱이 이름을 다른 데서 찾을 수 없다 |
| `total.realized_pnl_krw` | `Σ rows.realized_pnl_krw`. 행이 없으면 `0` |
| `total.excluded_account_count` | `UNAVAILABLE` · `CONFLICT` 매도가 있는 계좌 수 |

`UNAVAILABLE` · `CONFLICT` 매도는 실현손익 뷰와 같이 목록과 합계에서 빼고 계좌 수만 센다(스펙 §9.3). 손익을 계산하지 못한 행이라 보여 줄 금액이 없다.

외화 종목의 실현손익도 원화로만 싣는다. 원화 실현손익은 매입일 · 매도일 환율이 달라 현지 통화 손익과 비례하지 않는다(스펙 §4.3).

**`trades[]`** — 그 종목의 `cln_trade` 전부(전 기간), 내 계좌(`account.account_ref`)의 것. 정렬은 `executed_at` 내림차순, 같으면 `trade_id` 오름차순.

| 필드 | 출처 |
|---|---|
| `trade_id` · `account_id` · `side` · `quantity` · `price` · `fee` · `tax` · `currency` | `cln_trade` · `account` |
| `account_label` | `account.label`. 실현손익 행과 같은 이유로 싣는다 |
| `executed_at` | 체결 시각. 서울 오프셋(`+09:00`)을 붙인 ISO 시각 |
| `executed_on` | 체결일. `executed_at`을 서울 시각으로 바꾼 날짜(`YYYY-MM-DD`) — 실현손익의 `sold_at`과 같은 규칙. 화면은 이 값을 쓰고 날짜를 직접 계산하지 않는다 |

`price`는 현지 통화 단가다. 원화 환산은 싣지 않는다 — 체결의 단위는 현지 통화이고, 원화는 실현손익에서 이미 보인다.

**`corporate_actions[]`** — 그 종목의 `data.corporate_action` 전부. 정렬은 `ex_date` 내림차순. 필드는 `type` · `ratio` · `ex_date`.

### 3.4 거래내역의 범위

전 기간을 페이지 없이 내린다. 개인 계좌에서 한 종목의 체결 수는 작고, 상세에서 필요한 질문은 "이 종목을 언제 얼마에 사고팔았나"라 기간을 자르면 그 답의 일부가 사라진다. 응답이 커지는 계좌가 생기면 그때 커서를 붙인다(§6).

### 3.5 notices

| code | 조건 | 문구 |
|---|---|---|
| `FX_APPLIED` | 외화 종목이라 원화 환산 환율이 있다 | 다른 뷰와 같은 문구 규칙. 환율은 **이 종목의 라인**에 쓰인 것만 모은다 — 그날 전체 라인으로 모으면 원화 종목 상세에 달러 환율 안내가 붙는다 |
| `FX_STALE` | 이 종목의 라인 환율이 폴백 한도를 넘었다 | 다른 뷰와 같은 문구 규칙. 대상은 위와 같이 이 종목의 라인 |
| `CA_UNKNOWN` | `by_account[].basis.ca_unknown`, 또는 그 종목의 `realized_pnl_line.ca_unknown`(목록에서 뺀 `UNAVAILABLE` · `CONFLICT` 행 포함)이 하나라도 참 — 실현손익 뷰와 같은 범위 | `기업행위 이력을 확인하지 못해 실현손익이 다를 수 있습니다`, `params.instrument_ids = [이 종목]`, `severity = warn` |

`CA_UNKNOWN`의 문구는 실현손익 뷰의 것(`N개 종목은 …`)과 다르다. 종목 하나를 보는 화면이라 개수를 세지 않는다. `code`는 같으므로 앱의 분기는 하나다.

`SEEDED_ROWS` · `EXCLUDED_ACCOUNTS`는 싣지 않는다. 두 사실은 실현손익 영역 안에서 말한다(§4.2). `STALE_ACCOUNTS` · `SYNC_IN_PROGRESS`도 싣지 않는다. 앱은 두 안내를 계좌 탭에서만 그린다. 이 종목을 가진 계좌가 이월된 사실은 `by_account[].is_carried_forward`로 그 계좌 줄에서 말한다(§4.2).

앱의 안내 배치표(`notices.ts`의 `BY_SCREEN`)에 `instrument-detail` 화면을 더하고, 그 화면이 그리는 코드는 `FX_APPLIED` · `FX_STALE` · `CA_UNKNOWN`이다.

### 3.6 보유하지 않은 종목, 남과 함께 가진 종목

- 응답의 모든 블록은 인증 주체의 계좌로 스코프된다. 같은 종목을 다른 사용자가 가져도 그 계좌의 라인 · 체결 · 실현손익은 어디에도 나타나지 않는다(N-51).
- 지금 보유하지 않으면 `position = null`, `by_account = []`. 과거에 팔았던 종목이면 `realized` · `trades`는 그대로 채운다.
- 보유도, 체결도, 실현손익도 없으면 `position = null`이고 목록이 모두 빈다. `instrument` 블록은 채운다 — 앱이 머리글과 `알림 걸기`를 그릴 수 있게.
- `empty_reason`은 이 응답에서 늘 `null`이다. 이 응답은 행 목록이 아니라 종목 한 개의 서술이라, 비는 것은 화면 전체가 아니라 영역 하나씩이고 각 영역이 그 상태를 말한다(§4.2 · §4.3). 앱의 공통 빈 상태(본문 전체를 바꾸는 분기)를 타지 않는다.

### 3.7 종목별 응답에 더하는 `instrument_id`

`GET /portfolio/views/positions`의 행에 `instrument_id`(UUID 문자열)를 싣는다.

| 행 | `instrument_id` |
|---|---|
| `lens = DIRECT`의 종목 행 | 있음 |
| `lens = DIRECT`의 예수금 행 | **키 없음** |
| `lens = LOOK_THROUGH`의 모든 행 | **키 없음** |

앱은 "`instrument_id`가 있는 행만 누를 수 있다"는 규칙 하나로 판단한다. 예수금과 렌즈를 앱이 따로 가려내지 않는다. 다른 뷰의 응답은 바뀌지 않는다.

### 3.8 "보유 중"의 기준 — 포트폴리오 화면과 알림을 맞춘다

"이 종목을 지금 갖고 있나"는 앱 어디서나 같은 판정 하나를 쓴다: 날짜는 **그 사용자의 최신 스냅샷**(`SnapshotCalendarRepository.latestAsOf`, 확정 전 포함, 종목별 화면이 쓰는 `as_of`)이고, 그 날짜에 연동 중인(`DISCONNECTED`가 아닌) 계좌에 수량이 0보다 큰 그 종목의 라인이 있으면 보유다. 이 판정은 한 곳(질의 조각 하나)에 두고 아래 세 곳이 공유한다. 종목 상세의 `position`, 종목 검색(`GET /instruments`)의 `held`, 알림 생성 · 미리보기의 보유 확인(`NOT_HELD` 거절)이 모두 이 기준이다.

**알림의 평가는 바꾸지 않는다.** 사용자 상태 지표(수익률 · 비중)는 그 거래일의 확정 스냅샷으로 판정한다(알림 스펙 §5.1). 같은 날 판정이 장중 동기화마다 달라지면 안 되기 때문이다. 바꾸는 것은 "만들 수 있나"를 묻는 보유 확인뿐이다.

기준을 나누지 않는 이유:

- 확정 스냅샷으로 보유를 확인하면 오늘 산 종목은 화면에 보유로 보이는데 수익률 알림을 만들 수 없고, 오늘 판 종목은 화면에 없는데 수익률 알림이 만들어진다.
- 보유 확인을 느슨하게 해도 잃는 것이 없다. 보유하지 않은 날의 알림은 `미보유`로 남을 뿐 무효가 되지 않고, 다시 사면 평가가 이어진다(알림 스펙 §7.2). 장중 라인이 저녁 확정에서 사라지면 그 알림은 그날부터 `미보유`다.
- 오늘 산 종목으로 만든 수익률 알림의 첫 판정은 그날 저녁 확정 스냅샷이 생긴 뒤다.

바꾸는 곳:

| 코드 | 지금 | 바꾼 뒤 |
|---|---|---|
| `HoldingReader.held` (알림 생성 · 미리보기의 보유 확인) | 최신 확정 스냅샷 | 위 공유 판정 |
| `InstrumentSearchMapper`의 `HELD` 조각 (검색 `held` · 보유 종목 구역) | `is_final`인 최신 `as_of` | 위 공유 판정 |
| `HoldingReader.latestFinal` (평가 입력 · 미리보기의 현재값) | 최신 확정 스냅샷 | 그대로 |

**확정 전 보유의 판정 — `AWAITING_FINAL`.** 오늘 산 종목은 보유 확인을 통과하지만 평가가 읽는 확정 스냅샷에는 아직 없다. 이 상태를 `미보유`라고 하지 않고 확인 불가 사유 하나로 따로 둔다.

| 코드 | 판정 | 카드 문구 | 미리보기 줄 문구 |
|---|---|---|---|
| `AWAITING_FINAL` | 사용자 상태 조건인데 그 거래일 확정 스냅샷의 연동 중인 계좌에 그 종목이 없고, 위 공유 판정으로는 보유 중이다 | `오늘 저녁 첫 판정` | `{조건 이름} — 오늘 저녁 확정 후 첫 판정을 해요` |

- 판정은 평가기(`ConditionEvaluator`)가 한다. 지금 `holding == null`이면 `NOT_HELD`를 내는 자리에서, 공유 판정으로 보유 중이면 `AWAITING_FINAL`을 낸다. 미리보기와 저장된 알림의 평가가 같은 평가기를 거치므로 편집기의 현재값 상자와 알림 카드가 같은 말을 한다.
- 결과는 `UNKNOWN`이라 발화하지 않는다. 그날 저녁 확정 스냅샷이 생기면 그 거래일을 평가해 실제 결과로 바뀐다.
- 카드는 `확인 불가 · …` 꼴이 아니라 `오늘 저녁 첫 판정`만 쓰고, 색은 감시 중과 같다. 잘못된 상태가 아니라 판정을 기다리는 상태다.
- `alert_state.unknown_reason`의 CHECK 제약에 값을 더하는 마이그레이션이 필요하다(origin/main의 다음 빈 번호).
- 앱은 확인 불가 사유 타입(`UnknownReason`)과 카드 상태 문구에 이 값을 더한다.

**미리보기에서 보유 확인이 실패한 경우.** `NOT_HELD` 검증 오류(오늘 판 종목 등)가 난 미리보기는 `current = null`로 내린다. 저장할 수 없는 알림의 현재값, 특히 확정 스냅샷에 남은 어제 수익률을 오류와 함께 보이지 않는다. 앱은 `current = null`이면 현재값 상자를 그리지 않는다.

미리보기를 장중 값으로 계산하지 않는 것은, 미리보기에는 충족으로 보였는데 저녁 판정에서 울리지 않는 일을 만들지 않기 위해서다.

**배포 순서 전제.** 앱의 `알림 걸기`(§4.5)는 이 변경이 운영 백엔드에 들어간 뒤에만 맞게 동작한다. 앱이 먼저 나가면 오늘 산 종목에서 편집기가 켜 준 `수익률 도달`을 저장이 `NOT_HELD`로 거절한다. 그래서 앱 브랜치는 백엔드 브랜치가 main에 머지되고 배포된 뒤에 머지한다.

## 4. 화면

### 4.1 진입과 머리글

- 종목별 행을 누르면 루트 스택에 `instrument-detail`이 쌓인다. 파라미터는 `{ instrumentId, label }`이다. `label`은 응답이 오기 전 머리글 제목에 쓴다.
- 머리글 제목은 종목명이다. 뒤로 가면 종목 탭으로 돌아가며 필터 · 정렬 · 렌즈가 그대로다.
- 상단에는 다른 화면과 같은 as-of 배너와 notices 줄이 있다(스펙 §2.3).

### 4.2 영역 순서

```
삼성전자 [국내]                                ← 머리글
기준 07-27 15:30 · 새로고침
⚠ 기업행위 이력을 확인하지 못해 실현손익이 다를 수 있습니다   ← CA_UNKNOWN일 때만

14,240,000원                                   ← 보유 요약
+2,240,000 (+18.7%)
200주 · 평단 60,000

계좌별
한국투자 위탁           200주 · 평단 60,000   14,240,000원

실현손익                               +277,000원
취득원가 기준이 달라 위 평단과 맞지 않아요
2026-05-12 매도 5주   700,000원          +198,000
2026-03-02 매도 3주 [추정] 400,000원      +79,000

거래내역
이 종목의 거래내역이 아직 없어요

기업행위
(없으면 영역 자체를 그리지 않는다)

[ 알림 걸기 ]
```

**보유 요약**

- 1줄은 평가금액(외화는 현지 통화 병기), 2줄은 평가손익(금액 · %, 색은 종목별과 같은 규칙), 3줄은 수량 · 평단.
- `position = null`이면 보유 요약 자리에 `지금 보유하지 않은 종목이에요`라고 쓰고 계좌별 영역을 그리지 않는다.

**계좌별**

- 계좌마다 한 줄: 계좌 표시명, 수량 · 평단, 평가금액.
- `is_carried_forward`이면 계좌 표시명 옆에 `07-24 기준`처럼 그 계좌 값의 날짜를 작게 붙인다(`source_as_of`의 서울 날짜). 계좌별 화면의 이월 배지와 같은 말이다. 배너의 기준 시각보다 이른 값을 오늘 값으로 읽지 않게 하는 표시이고, 계좌 단위 사실이라 화면 위 안내가 아니라 그 계좌 줄에서 말한다.
- 등급 배지를 이 줄에 달지 않는다. 이 평단은 잔고 기준이라 등급과 관계가 없고, 옆에 `추정`이 붙으면 잔고 평단이 추정치로 읽힌다.

**실현손익**

- 머리 줄은 `total.realized_pnl_krw`(색은 부호 규칙). 그 아래는 원가 기준 표기 → `미포함 계좌 N개` 순서다.
- 머리 줄 아래에 **원가 기준 표기** `취득원가 기준이 달라 위 평단과 맞지 않아요`. 실현손익 행이 하나라도 있고 `position`이 있으면 붙인다(스펙 §2.10 · §4.1). `position = null`이면 화면에 평단이 없어 붙이지 않는다.
- **계좌별 원가 근거 줄**: 지금 보유 중인 수량을 앞으로 팔 때 실현손익이 어떻게 계산될지를 계좌마다 말한다. `by_account[]` 중 `basis.grade`가 `VERIFIED`가 아닌 계좌마다 한 줄을 두고, 입력은 `by_account`뿐이다. 이미 실현된 매도의 근거는 매도 행의 배지가 말하므로, 이 줄은 화면에 보이는 실현손익 숫자를 수식하지 않는다는 것이 문구에 드러나야 한다. 형식은 `{계좌 표시명} · {배지} — {설명}`이고, 배지는 실현손익 화면의 `GradeBadge` 라벨(`추정` · `거래내역 없음` · `수량 확인 중`)을 쓴다.
  - `SEEDED` + `LATE_COVERAGE`: `한국투자 위탁 · 추정 — 이 계좌에서 팔면 손익이 추정치로 계산돼요. 거래내역이 1월 1일부터 있어요`
  - `SEEDED` + `NOT_TRADED`: `… · 추정 — 이 계좌에서 팔면 손익이 추정치로 계산돼요. 매매 없이 입고된 종목이에요`
  - `UNAVAILABLE`: `… · 거래내역 없음 — 이 계좌에서 팔면 손익을 계산하지 못해요`
  - `CONFLICT`: `… · 수량 확인 중 — 거래내역이 아직 도착하지 않았을 수 있어요. 그동안 판 손익은 계산하지 못해요`
  - 이 줄은 실현손익 행이 없어도 둔다. 지금 보유분의 원가가 추정이라는 사실은 팔기 전에 알아야 뜻이 있다.
  - `basis = null`: 줄을 두지 않는다. 평단 계산 결과가 없는 것은 등급이 아니므로 지어내지 않는다.
  - 이미 다 판 계좌는 `by_account`에 없으므로 근거 줄이 없다. 그 계좌 매도의 근거는 매도 행의 배지가 말한다.
- 매도 행: 매도일(`sold_at`) · 수량 · 매도금액 · 실현손익, 등급이 `SEEDED`이면 `추정` 배지. 배지를 누르면 실현손익 화면의 `tradeHelp`와 같은 설명을 보여 준다.
- `excluded_account_count > 0`이면 합계 바로 아래에 `미포함 계좌 N개`(실현손익 화면과 같은 위치 규칙).
- 행이 하나도 없고 `excluded_account_count > 0`이면 머리 줄에 금액을 쓰지 않고 `—`를 둔다. `0원`으로 쓰면 손익이 0이었다고 읽힌다.
- 실현손익 행이 없고 미포함 계좌도 없으면 머리 줄에 금액을 쓰지 않고 영역 안에 `이 종목에서 확정한 손익이 아직 없어요`를 쓴다. 원가 기준 표기는 붙이지 않는다.

**거래내역**

- 체결마다 한 줄: 체결일(`executed_on`) · `매수`/`매도` · 수량 · 단가(현지 통화) · 계좌 표시명(`account_label`). 응답의 `trades`와 `realized.rows`에 나온 `account_id`가 하나뿐이면 체결 줄과 매도 행 모두 계좌명을 생략한다.
- 비면 영역 안에 `이 종목의 거래내역이 아직 없어요`.

**기업행위**

- 이력이 있으면 `ex_date` · 종류(`분할` · `유상증자` · `합병`) · 비율. 비율은 `1주 → 2주`처럼 행위 전후 주식 수로 쓴다(`ratio`가 행위 후 ÷ 행위 전). `ratio`가 1보다 작으면 `2주 → 1주`처럼 뒤쪽을 1주로 둔다. 수는 소수 넷째 자리까지, 끝의 0은 지운다.
- 이력이 없으면 영역을 그리지 않는다. 이력을 확인하지 못한 경우는 상단 `CA_UNKNOWN` 줄이 말한다.

### 4.3 상태

| 상태(스펙 §10) | 판정 | 화면 |
|---|---|---|
| default | 응답 성공 | 위 순서 |
| 거래내역 없음 | `trades = []` | 거래내역 영역에 `이 종목의 거래내역이 아직 없어요`. 다른 영역은 그대로 |
| 기업행위 경고 | `notices`에 `CA_UNKNOWN` | 배너 아래 경고 줄(서버 `message` 그대로) |
| 로딩 | 첫 응답 전 | 다른 화면과 같은 스켈레톤 |
| 오류 | `404` | `종목을 찾을 수 없어요`와 뒤로 가기만. 다시 시도는 두지 않는다 |
| 오류 | 그 밖 | 공통 `ErrorState`(다시 시도) |

`401`은 공통 처리로 로그인으로 돌아간다(스펙 §10).

### 4.4 날짜와 통화 표시

- 이 화면의 날짜(매도일 · 체결일 · 기업행위 `ex_date`)는 연도를 포함해 `2026-03-11`처럼 쓴다. 전 기간 목록이라 월 · 일만 쓰면 해가 다른 거래가 같은 날로 보인다. 이월 계좌의 `07-24 기준`은 계좌별 화면과 같은 형식을 쓴다.

- 외화 종목은 보유 요약 · 계좌별의 평가금액에 현지 통화를 병기하고, 평단 · 단가는 현지 통화로 쓴다(스펙 §3.7).
- 실현손익은 원화만 쓴다(§3.3).

### 4.5 `알림 걸기`

- 화면 맨 아래 버튼. 누르면 `alert-editor`를 `{ mode: 'new', instrument }`로 연다. 종목 선택을 거치지 않고 조건 선택부터 시작한다(앱 정보 구조 §2.5).
- 넘기는 `EditorInstrument`: `id = instrument.id`, `label`, `market`, `held = position !== null`, `lastClose = instrument.last_close`, `lastCloseOn = instrument.last_close_on`. `held`가 참이면 편집기의 `수익률 도달`이 활성이다(X1-03). 알림 생성의 보유 확인이 같은 스냅샷을 보므로(§3.8) 편집기가 켜 준 조건을 저장이 거절하지 않는다.
- `instrument.delisted_on`이 있으면 버튼을 두지 않는다. 상장폐지 종목은 종목 검색에도 나오지 않아 알림 대상이 아니다.
- 버튼은 응답이 온 뒤에만 그린다. 로딩 중에는 `held` · 직전 종가를 몰라 편집기를 틀리게 채운다.

### 4.6 종목별 행의 누름

- 행에 `instrument_id`가 있으면 `Pressable`로 그린다. 손을 대면 바탕색이 바뀌고(계좌별 화면의 계좌 행과 같은 `palette.surface`), 화면 낭독기는 `{종목명} 상세 보기` 버튼으로 읽는다.
- `instrument_id`가 없는 행(예수금, 렌즈를 켠 모든 행)은 지금처럼 `View`다. 눌러도 반응이 없다.
- 행 끝에 화살표를 두지 않는다. 1줄 오른쪽이 평가금액이라 화살표가 폭을 먹으면 종목명이 먼저 잘리고, 계좌 행과 규칙이 갈린다.
- 렌즈 토글 옆 도움말(앱 문구 `LENS_HELP`) 끝에 한 줄을 더한다: `ETF 분해 모드에서는 종목 상세를 열 수 없어요`. 토글 라벨(`ETF 분해 모드`)과 같은 말을 쓴다. 켜기 전에도 보이는 설명이라, 누를 수 없게 된다는 것을 켜기 전에 알 수 있다.

### 4.7 새로고침

as-of 배너의 새로고침은 이 화면의 응답만 다시 받는다(스펙 §2.3). 계좌 동기화를 일으키지 않는다.

## 5. 테스트

### 5.1 백엔드

| 테스트 | 확인 | 케이스 |
|---|---|---|
| 보유 요약 | 샘플 삼성전자의 수량 · 평단 · 평가 · 손익이 §3.2와 같다 | PF10-01 |
| 종목별과 일치 | 같은 사용자 · 같은 `as_of`에서 `position.quantity` · `avg_cost`가 종목별 응답의 그 행과 같다 | PF10-01 |
| 분해 합 | `Σ by_account.quantity = position.quantity`. 두 계좌에 나눠 가진 종목을 주입해서도 확인한다 | PF10-02 |
| 거래내역 | 주입한 체결이 건수 · 필드 · 정렬대로 나온다. 남의 계좌 체결은 나오지 않는다 | PF10-03 · N-51 |
| 거래내역 없음 | `cln_trade`가 비면 `trades = []`, `empty_reason = null` | PF10-04 |
| 실현손익 | 샘플의 `T-0001` · `T-0002`가 나오고 합계가 277,000. `UNAVAILABLE` 행은 목록 · 합계에서 빠지고 `excluded_account_count`에 잡힌다 | PF10-05 |
| 계좌별 basis | `SEEDED`(`LATE_COVERAGE` · `NOT_TRADED` 각각) · `UNAVAILABLE` · 행 없음을 주입해 `basis` 모양을 확인한다 | PF10-06 |
| 이월 계좌 | 수집이 실패해 이월된 계좌의 `by_account` 줄에 `is_carried_forward = true`와 그 라인의 `source_as_of`가 실린다 | — |
| `CA_UNKNOWN` | basis 또는 매도 행(목록에서 뺀 행 포함)의 `ca_unknown`이 참이면 notice가 실리고, 모두 거짓이면 없다 | PF10-07 |
| 스코프 | `yhr@a.com`과 `jdh@a.com`이 함께 가진 삼성전자에서 yhr 응답에 jdh 계좌가 하나도 없다 | N-51 |
| 보유하지 않은 종목 | 판 종목은 `position = null` · 실현손익 있음. 아무것도 없는 종목은 목록이 모두 비고 `instrument`는 채워지며 `empty_reason = null` | — |
| 404 | 없는 UUID · UUID가 아닌 문자열 · 예수금 의사종목 | — |
| 종목별 `instrument_id` | DIRECT 종목 행에만 있고 예수금 행 · 렌즈 응답에는 키가 없다 | PF10-01 |
| 보유 기준 | 확정 전 라인에만 있는 종목(오늘 산 종목)으로 수익률 알림을 만들면 성공하고, 검색 `held`가 참이다. 확정 라인에는 있고 최신 라인에는 없는 종목(오늘 판 종목)은 `NOT_HELD`로 거절되고 `held`가 거짓이다. 평가 입력은 여전히 확정 스냅샷을 읽는다 | X1-03 |
| 확정 전 보유 | 확정 라인에는 없고 최신 라인에만 있는 종목의 수익률 알림은 평가 결과가 `UNKNOWN` · `AWAITING_FINAL`이고 발화하지 않는다. 미리보기 현재값의 그 줄이 `… — 오늘 저녁 확정 후 첫 판정을 해요`다. 저녁 확정 라인이 생기면 실제 결과로 바뀐다. 오늘 판 종목의 미리보기는 `NOT_HELD` 오류와 함께 `current = null` | — |
| 골든 | 샘플 삼성전자 응답을 `instrument-detail.json`으로 내보낸다(기존 `SixViewGoldenTest`와 같은 방식). 종목별 골든도 `instrument_id`가 붙은 모양으로 갱신된다 | — |

DB를 쓰는 테스트는 브랜치 전용 테스트 DB에서 돌린다.

### 5.2 앱

| 테스트 | 확인 | 케이스 |
|---|---|---|
| 행 누름 | `instrument_id`가 있는 행을 누르면 `instrument-detail`이 `{instrumentId, label}`로 열린다. 예수금 행 · 렌즈 행은 버튼이 아니다. 기존 `행을 눌러도 아무 일이 없다`는 이 규칙으로 바뀐다 | PF10-01 |
| 렌즈 도움말 | 토글 도움말에 `ETF 분해 모드에서는 종목 상세를 열 수 없어요`가 보인다 | — |
| default | 픽스처로 보유 요약 · 계좌별 · 실현손익(원가 기준 표기 포함) · 거래내역을 그린다 | PF10-01 · 02 · 03 · 05 |
| 거래내역 없음 | `trades = []`에서 `이 종목의 거래내역이 아직 없어요` | PF10-04 |
| 계좌별 원가 근거 | `SEEDED` basis에서 `추정`과 시작일 문구(`이 계좌에서 팔면 …`), `UNAVAILABLE` · `CONFLICT` 문구, `null`이면 줄 없음. 실현손익 행이 없어도 줄이 있다 | PF10-06 |
| 이월 계좌 | `is_carried_forward` 계좌 줄에 `07-24 기준`이 붙고, 아닌 계좌에는 없다 | — |
| 기업행위 경고 | `CA_UNKNOWN` notice가 배너 아래 경고 줄로 보인다 | PF10-07 |
| 보유하지 않은 종목 | `position = null`에서 보유하지 않은 종목 문구, 계좌별 영역 없음 | — |
| 404 | `종목을 찾을 수 없어요` | — |
| 알림 걸기 | 누르면 `alert-editor`가 `{mode: 'new', instrument}`로 열리고 `held` · 직전 종가가 응답과 같다. 상장폐지면 버튼이 없다 | X1-03 |
| 외화 | 미국 종목 픽스처에서 현지 통화 병기 | — |
| 확정 전 보유 카드 | `last_result = UNKNOWN` · `unknown_reason = AWAITING_FINAL`인 알림 카드 상태가 `오늘 저녁 첫 판정`이고 감시 중과 같은 색이다 | — |

**픽스처.** 백엔드와 앱이 동시에 구현되므로 앱은 처음에 이 문서 §3.2 · §3.3의 모양대로 손으로 쓴 픽스처(`src/fixtures/instrumentDetail.ts`)로 시작한다. 백엔드가 main에 들어온 뒤 골든 `instrument-detail.json`과 갱신된 `positions.json`으로 바꾸고, 다른 골든처럼 구조를 검사해 받는다. 앱 브랜치는 백엔드 다음에 머지한다(§3.8 배포 순서 전제).

## 6. 미결 · 후속

- 거래내역이 많은 계좌가 생기면 `trades`에 커서를 붙인다. 그때 정렬 키(`executed_at`, `trade_id`)를 커서로 쓴다.
- 알림 상세 등 다른 화면에서 종목 상세로 들어오는 경로. 응답은 이미 보유와 무관하게 성립한다.
- `position_basis.evaluated_as_of`가 보유 요약의 `as_of`보다 늦거나 이르면 계좌별 원가 근거가 다른 날의 판정일 수 있다. 지금은 표시하지 않는다. 문제가 되면 판정일을 함께 싣는다.

## 7. 스펙과의 관계

이 설계가 정한 것 중 화면과 계약의 뼈대는 스펙 본문에도 있다. 세부(필드별 계산 · 정렬 · 테스트)는 이 문서에만 있다.

| 스펙 위치 | 담긴 것 |
|---|---|
| 포트폴리오 §2.5 · §8.3 | 종목별 행의 `instrument_id`, 그것이 있는 행만 누를 수 있다는 규칙, 렌즈 도움말 문장 |
| 포트폴리오 §2.8 · §3.7 | 실현손익은 원화만 쓴다 |
| 포트폴리오 §2.10 | 화면의 영역, 원가 기준 표기, 계좌별 원가 근거 줄, 전 기간 범위, 보유하지 않은 종목, `알림 걸기` |
| 포트폴리오 §8.2 · §8.5 | `CA_UNKNOWN`이 종목 상세에도 실린다는 것, 응답 모양과 규칙, 404 |
| 포트폴리오 §10 | 종목 상세의 상태 |
| 알림 §6.5 · §7.2 · §7.4 | 확인 불가 사유 `AWAITING_FINAL`과 카드 문구 `오늘 저녁 첫 판정` |
| 알림 §11.1 · §14.1 | 종목 검색 `held`와 생성 검증의 보유 확인이 최신 스냅샷(확정 전 포함) 기준. 평가 기준(§5.1)은 확정 스냅샷 |
| 알림 미리보기 절(§11.3) | 현재값은 평가와 같은 데이터, `NOT_HELD` 오류면 `current = null` |

통합테스트 문서는 테스트 트랙이 고친다. 이 설계로 기대가 바뀌는 케이스는 다음과 같고, 구현이 끝날 때 바뀐 동작과 함께 넘긴다.

| 케이스 | 바뀌는 것 |
|---|---|
| PF10-01 | 종목별 행에 `instrument_id`가 생기고 그 행이 버튼이 된다 |
| PF10-03 · PF10-04 | 거래내역이 `trades[]`이고 체결일은 `executed_on` |
| PF10-05 | 실현손익이 `realized.rows[]` · `realized.total`. 원가 기준 표기는 보유 중일 때만 |
| PF10-06 | `basis`가 최상위가 아니라 `by_account[].basis`. 배지는 계좌 행이 아니라 실현손익 영역의 계좌별 원가 근거 줄 |
| PF10-07 | `basis.ca_unknown`은 `by_account[].basis.ca_unknown`, 화면 경고는 종목 상세 응답의 `CA_UNKNOWN` notice. "`CA_UNKNOWN`은 실현손익 응답에만 실린다"는 비고가 바뀐다 |
| N-51 | 판정 필드 이름(`by_account` · `trades`)은 같고 `realized.rows`가 더해진다 |
| X1-03 · 알림 생성 `NOT_HELD` · 검색 `held`를 다루는 케이스 | 보유 기준이 "최신 확정 스냅샷"에서 "최신 스냅샷"으로. 샘플 데이터에서는 결과가 같다 |
| 알림 미리보기 현재값 · 확인 불가 사유 · 카드 상태 문구를 다루는 케이스 | `NOT_HELD` 오류일 때 `current = null`. 오늘 산 종목은 `AWAITING_FINAL` — 카드 `오늘 저녁 첫 판정`, 미리보기 줄 `… — 오늘 저녁 확정 후 첫 판정을 해요` |
