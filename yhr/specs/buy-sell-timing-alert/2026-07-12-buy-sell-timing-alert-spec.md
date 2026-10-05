# 매수·매도 타이밍 알림 (Buy/Sell Timing Alert) — 설계 스펙

- **버전**: v1 (2026-09-27)
- **상태**: 팀 경계 합의 완료 → 구현 계획 착수 전
- **범위**: 조건 모델과 카탈로그, 평가 시점, 발화 의미론, 결측·지연 처리, 평가 런타임, 발화 전달(앱 푸시·앱 안 기록), 데이터 모델, API 계약, 검증 규칙, 화면 상태, 역할 분담과 데이터 요구사항
- **비범위(이번 스펙에서 다루지 않음)**: 시세·수급의 수집 방법(원천 선택, 기관별 제약, 수집 실패 복구), 인프라 스케일링, 앱 상태관리·디자인 시스템
- **관련 자료**: [`wireflow.drawio`](./wireflow.drawio) / [`wireflow.png`](./wireflow.png) / [`wireflow_src.py`](./wireflow_src.py)(두 산출물 생성기) · [앱 정보 구조](../app-information-architecture.md) · [포트폴리오 종합 관리 스펙](../portfolio-management/2026-07-28-portfolio-management-spec.md) · [설계 공유 및 합의 요청](../../meetings/2026-09-27-buy-sell-timing-alert-design-review.md)

---

## 1. 개요

### 1.1 기능 요약

사용자가 종목에 **조건**을 걸어두면, 시스템이 시세·수급·보조지표를 평가하다가 조건이 충족되는 순간 **발화**한다. 발화는 앱 안 기록으로 반드시 남고, 푸시를 받을 수 있는 기기에는 앱 푸시로도 전달된다(§9).

예시 조건:
- 가격이 특정 값에 도달
- 박스권 상단 돌파 / 하단 이탈
- 외국인 3일 연속 순매수
- 평가손익률 -10% 도달

> 위 4개는 **예시**이며 지원 범위를 닫는 목록이 아니다. 조건의 모양은 §2의 3축 분해로, v1이 지원하는 지표와 프리셋은 §5의 카탈로그로 정의된다.

알림 대상은 **보유 종목에 한정되지 않는다.** 종목 마스터에 있는 어떤 종목에도 걸 수 있으며, 보유 상태를 읽는 조건(§5.1 사용자 상태 지표)만 보유 종목에 걸린다. 그래서 알림의 소유는 계좌가 아니라 **사용자에게 직접** 속한다(§10.1).

### 1.2 핵심 설계 방향 (하이브리드)

조건 생성을 두 방식으로 제공하고, **하나의 저장 구조로 통합**한다.

- **조립형(Composable)**: 사용자가 `지표 + 변형 + 연산자 + 기준값`을 AND로 조합해 직접 조건을 만든다.
- **프리셋(Preset)**: 미리 만들어둔 알림 유형(가격 도달, 박스권 돌파, 외국인·기관 연속 순매수 등)을 카드로 제공하고, 사용자는 파라미터만 채운다.

두 방식 모두 `trigger_type + trigger_spec(JSON)` 하나의 형태로 저장된다(§4). v1 프리셋은 전부 조립형으로 컴파일되는 템플릿이라 평가기는 하나다(§5.3).

### 1.3 v1 범위

| 항목 | v1 |
|---|---|
| 시장 | 국내(KR) · 미국(US) |
| 평가 시점 | 국내·미국: 장중 · 종가 (§3) |
| 조건 생성 | 조립형 빌더 + 프리셋 9종 (§5.3) |
| 지표 | 시세 6 · 기술 4 · 수급 2 · 사용자 상태 2 (§5.1) |
| 전달 | 앱 안 기록(전 기기) + iOS 앱 푸시 (§9.6) |

### 1.4 용어 (Glossary)

| 용어 | 의미 |
|------|------|
| **알림 (alert)** | 사용자가 만든 규칙 1개. 대상 종목·평가 시점·발화 방식 등 공통 속성 + 트리거 |
| **발화 (fire)** | 알림의 조건이 충족되어 기록·전달이 일어난 사건. 화면 문구는 **울린 알림** |
| **트리거 (trigger)** | 발화를 결정하는 조건 명세. `COMPOSABLE` 또는 `PRESET` |
| **피연산자 (operand)** | `지표 + 지표 파라미터 + 변형`으로 만들어지는 비교 대상 값 |
| **변형 (transform)** | 지표에 씌우는 함수. `identity / window / delta / pct` |
| **유지 조건 (modifier)** | 조건을 감싸는 지속 조건. `streak(N거래일 연속)` 또는 `persist_min(N분 지속)` |
| **평가 시점 (cadence)** | 알림을 언제 평가하는가. `INTRADAY`(장중) 또는 `CLOSE`(종가) (§3) |
| **데이터 시점 (as_of)** | 한 번의 평가가 기준으로 삼는 데이터의 시점. 종가는 거래일, 장중은 스냅샷 시각 |
| **평가 결과** | `TRUE / FALSE / UNKNOWN`. `UNKNOWN`은 데이터가 없거나 믿을 수 없어 판정하지 않은 것 (§6.1) |
| **엣지 기준** | 발화 판정에 쓰는 직전의 확정 결과(`TRUE`/`FALSE`). `UNKNOWN`은 기준을 바꾸지 않는다 |
| **발화 방식 (notify_mode)** | `EDGE_REARM / ONE_SHOT / COOLDOWN` |
| **완료 신호** | "이 시장의 이 데이터가 이 시점까지 준비됐다"를 데이터가 남기는 행 (§7.1) |

---

## 2. 조건 모델 — 3축 분해

모든 조립형 조건은 3개 축의 조합으로 표현된다.

### 축 1 — 관찰 대상 (Subject: 무엇을 보나)
- 시세계열: 가격, 등락률, 거래량, 고가·저가
- 수급: 외국인·기관 순매수
- 보조지표: 이동평균, RSI, 이격도
- **사용자 상태(user scope)**: 이 종목의 평가손익률·비중 — 시세가 아니라 포트폴리오 보유 스냅샷에서 온다

v1 지표 목록은 §5.1.

### 축 2 — 시간 형태 (Temporal shape: 어떻게 보나)

| 단계 | 형태 | 조립형 빌더 표현 | 계산 방식 |
|------|------|-----------------|-----------|
| L0 | 현재값 | transform=identity | 그 데이터 시점의 값 |
| L1 | 윈도우 집계(최근 N봉 max/min/avg/sum) | transform=window | 이력 재계산 |
| L2 | 변화량/변화율 | transform=delta / pct | 이력 재계산 |
| L3 | 교차(cross) | operator=crosses_above/below | 직전 봉(또는 직전 스냅샷)과 함께 재계산 |
| L4 | 연속성 | modifier=streak(N) / persist_min(N) | 이력 재계산 (종가) · 당일 스냅샷 재계산 (장중) |
| L5 | 상태 전이 | — | v1에 없음. 네이티브 프리셋의 자리 (§5.3) |

**평가기는 매번 저장된 이력을 다시 읽어 계산한다.** 윈도우·변화량·교차·연속은 전부 시세 이력의 함수이므로, 알림마다 링버퍼나 연속 카운터를 들고 있을 이유가 없다. 알림마다 저장하는 상태는 엣지 기준과 마지막으로 평가한 데이터 시점뿐이다(§6.4). 그래서 재시작해도 복구할 것이 없고, 장 시작 시 예열도 필요 없다.

### 축 3 — 비교 방식 (Comparison: 무엇과 견주나)
- 상수 기준값 (예: 가격 ≥ 70,000)
- 다른 피연산자와 비교 (예: 5일 이동평균 > 20일 이동평균)
- 자기 과거와 비교 (예: 종가 > 직전 20일 최고가)

---

## 3. 평가 시점

### 3.1 두 평가 시점

| cadence | 평가하는 순간 | 데이터 시점 | 왼쪽 피연산자 | 오른쪽 피연산자 | 유지 조건 |
|---|---|---|---|---|---|
| `INTRADAY` (장중) | 장중 스냅샷 완료 신호마다 | 스냅샷 시각 | 장중 지표(§5.1)의 `identity` | 상수 · 장중 지표 · **직전 거래일까지 확정된** 종가 지표 | `persist_min`만 |
| `CLOSE` (종가) | 거래일 데이터 완료 신호가 모두 모였을 때 1회 | 거래일 | 카탈로그 전부 | 상수 · **같은 거래일까지 확정된** 종가 지표 | `streak`만 |

한 알림 안의 조건은 모두 같은 평가 시점을 쓴다.

**종가로만 뜻이 있는 지표는 종가로만 평가한다.** 이동평균·RSI·수급은 하루치가 끝나야 값이 정해진다. 형성 중인 봉으로 판정하면 알림이 울린 뒤 종가에서 조건이 성립하지 않는 일이 생긴다. 장중에 즉시 알아야 가치가 있는 가격·등락률·거래량만 장중 평가를 연다.

**장중 조건은 확정된 과거를 기준선으로 쓸 수 있다.** "현재가가 직전 20일 최고가를 넘음"은 왼쪽이 장중 가격, 오른쪽이 어제까지 확정된 윈도우 값이다. 두 값의 시점이 달라도 오른쪽이 이미 확정돼 있으므로 판정이 흔들리지 않는다.

평가는 평가 시점이 정한 순간에만 일어나므로 장 운영 시간을 따로 지정하는 설정이 없다. 장중 평가는 장중 스냅샷이 있을 때만, 종가 평가는 마감 데이터가 있을 때만 일어난다.

### 3.2 시장별 지원

| 시장 | INTRADAY | CLOSE |
|---|---|---|
| 국내(KR) | ○ | ○ |
| 미국(US) | ○ | ○ |

시장마다 장중 시세의 허용 지연이 다르다 — 국내 10분, 미국 20분(§16.2). 미국 장은 한국 시간으로 자정을 넘기므로, 미국 종목의 거래일과 "당일"은 미국 현지 날짜로 판정한다. 미국 종목의 가격 기준값은 종목 통화(USD)로 입력한다. 원화로 환산해 비교하지 않는다 — 환율 변동만으로 조건이 참이 되면 그 알림은 종목이 아니라 환율을 감시하게 된다.

### 3.3 가동 중단과 재개

평가기가 멈춰 있던 동안의 데이터는 평가 시점마다 다르게 다룬다.

| cadence | 재개 후 동작 | 근거 |
|---|---|---|
| `CLOSE` | 밀린 거래일을 **날짜 순서대로** 모두 평가한다. 발화 문구에 기준일을 넣는다(`9/26 종가 기준`) | "3거래일 연속" 같은 조건이 날짜를 건너뛰면 판정이 틀린다. 종가 조건의 발화는 하루 늦어도 뜻이 남는다 |
| `INTRADAY` | 가장 최근 스냅샷 하나만 평가한다. 그 스냅샷도 허용 지연(§16.2)을 넘었으면 평가하지 않는다 | "10시에 7만원을 넘었다"를 오후에 받으면 쓸모가 없고 지금 가격으로 오해된다 |

데이터 시점은 앞으로만 간다. 이미 평가한 데이터 시점보다 오래된 시점은 평가하지 않는다(§8.2).

---

## 4. 저장 구조

### 4.1 봉투 + 다형 트리거

봉투(알림)는 공통·안정적이므로 **관계형 컬럼**으로, `trigger_spec`은 종류마다 모양이 달라 **JSON(JSONB)**으로 저장한다. 컬럼 정의는 §10.1, 근거와 부작용은 §4.4.

평가 상태는 별도 테이블(`alert_state`)에 둔다(§6.4). 규칙과 상태는 바뀌는 주기와 쓰는 주체가 다르다 — 규칙은 사용자가, 상태는 평가기가 쓴다.

### 4.2 trigger_spec — COMPOSABLE

```
spec = {
  conditions: [                       // AND로 결합 (OR 미지원 — §17)
    {
      left:  { indicator, indicator_params, transform },   // Operand
      op:    "gte|lte|gt|lt|crosses_above|crosses_below",
      right: { const: <number> }  |  { indicator, indicator_params, transform },
      modifier: { streak: <N> } | { persist_min: <N> } | null
    }
  ]
}
```

- `Operand = 지표 + 지표 파라미터 + 변형`. 지표 자체가 파라미터를 가진다(RSI 기간, 이동평균 기간 등).
- `transform`: `{type:"identity"}` | `{type:"window", fn:"max|min|avg|sum", n:<N>, lag:<L>}` | `{type:"delta", n:<N>}` | `{type:"pct", n:<N>}`
- `window.lag`은 윈도우의 끝을 L봉 앞으로 당긴다. 기본값 0. `lag: 1`이면 오늘을 뺀 직전 N봉이다.
- 윈도우·변화량의 N은 **봉(거래일) 단위**다. `streak`의 N도 거래일, `persist_min`의 N은 분이다.
- 장중 알림의 오른쪽에 종가 지표를 쓰면, 그 값은 직전 거래일까지의 이력으로 계산된다(§3.1).

### 4.3 trigger_spec — PRESET

```
spec = {
  preset_key: "box_breakout",
  params: { window_days: 20, max_range_pct: 15, direction: "up" }
}
```

| 종류 | 정체 | 평가 |
|------|------|------|
| **템플릿 프리셋** | 조립형 spec으로 컴파일 가능한 것 | 조립형 평가기 재사용 |
| **네이티브 프리셋** | 조립형으로 표현되지 않는 상태 전이·다중 신호 로직 | 전용 평가기. v1에는 없다 |

- **템플릿 프리셋은 평가 시점에 컴파일한다.** DB엔 `preset_key + params`를 그대로 저장한다.
  - 이유 ① 사용자가 "수정"할 때 프리셋 폼이 다시 떠야 한다(원본 정체성 보존). ② 템플릿 로직을 개선하면 기존 알림에도 반영된다.
  - 컴파일 결과가 바뀌면 평가 상태를 발화 없이 다시 기준 잡는다(§6.6). 배포 한 번에 알림이 일제히 울리지 않게 하기 위해서다.

### 4.4 왜 spec을 JSON으로 두나 (근거와 부작용)

**근거**: ① spec은 평가 시 항상 통째로 로드된다(문서형 접근). ② 조립형·프리셋마다 모양이 제각각이다(정규화하면 EAV 안티패턴이나 프리셋당 테이블 폭발). ③ 지표·프리셋을 추가해도 스키마 마이그레이션이 필요 없다.

**부작용과 대응**:
| 부작용 | 대응 |
|--------|------|
| DB가 무결성을 보장하지 않음(오타·타입) | **앱 계층 스키마 검증**을 저장 전 필수 관문으로 (§14) |
| spec 내부 조회가 어려움 | 평가에 필요한 데이터 종류는 카탈로그에서 코드로 유도한다(§5.4). 조회용 파생 컬럼을 두지 않는다 |
| spec 포맷 변경 관리 | `spec_version` + 코드 업캐스팅 (§5.5) |
| 카탈로그 참조 FK 부재 | 카탈로그는 append-only로 운영하고 폐기는 `deprecated` 플래그로 한다 (§5.5) |

---

## 5. 카탈로그

카탈로그는 ① 빌더·프리셋 UI 동적 렌더, ② 저장 전 spec 검증, ③ 평가에 필요한 데이터 선언을 함께 해결한다.

**코드 상수로 둔다. DB 테이블이 아니다.** 지표를 하나 늘리는 일은 계산 코드를 함께 쓰는 일이라 배포가 어차피 필요하고, 운영자가 런타임에 지표를 추가할 일이 없다. 앱은 `GET /alerts/catalog`로 받아 그린다(§11.1). 앱이 목록을 하드코딩하면 지표 하나를 늘릴 때 앱 배포가 필요해진다.

### 5.1 지표 카탈로그

```
Indicator {
  key, label, category,
  unit: "price" | "krw" | "percent" | "shares" | "ratio",
  params: [ {key, default, min, max} ],   // 지표 자체 파라미터 (RSI period 등)
  intraday_left: bool,                     // 장중 알림의 왼쪽에 올 수 있는가
  markets: ["KR", "US"],
  allowed_transforms: [...],
  allowed_operators: [...],
  scope: "market" | "user",
  requires: [ 데이터 종류 ],               // §5.4
  history: (params) -> 필요 봉 수
}
```

| key | 라벨 | 파라미터 | 값 (장중 / 종가) | 장중 왼쪽 | 시장 | 필요 데이터 | 필요 이력 |
|---|---|---|---|---|---|---|---|
| `price` | 가격 | — | 현재가 / 종가 | ○ | KR · US | 장중 시세 / 일봉 | 0 |
| `change_pct` | 등락률 | — | 직전 거래일 종가 대비 % | ○ | KR · US | 장중 시세 + 일봉 / 일봉 | 1 |
| `volume` | 거래량 | — | 당일 누적 / 일 거래량 | ○ | KR · US | 장중 시세 / 일봉 | 0 |
| `volume_ratio` | 거래량 배수 | `n`=20 (5~120) | 당일(누적) 거래량 ÷ 직전 n거래일 평균 거래량 | ○ | KR · US | 장중 시세 + 일봉 / 일봉 | n |
| `high` · `low` | 고가 · 저가 | — | — / 일 고가·저가 | ✕ | KR · US | 일봉 | 0 |
| `range_pct` | 가격 폭 | `n`=20 (5~120) | — / 직전 n봉의 (최고 고가 − 최저 저가) ÷ 최저 저가 × 100 | ✕ | KR · US | 일봉 | n |
| `sma` | 이동평균 | `n`=20 (2~120) | — / 종가 n봉 단순평균 | ✕ | KR · US | 일봉 | n |
| `rsi` | RSI | `n`=14 (2~30) | — / Wilder 방식 | ✕ | KR · US | 일봉 | n+1 |
| `disparity` | 이격도 | `n`=20 (2~120) | — / 종가 ÷ n봉 이동평균 × 100 | ✕ | KR · US | 일봉 | n |
| `foreign_net_buy` | 외국인 순매수 | — | — / 순매수 금액(원) | ✕ | KR | 수급 | 0 |
| `institution_net_buy` | 기관 순매수 | — | — / 순매수 금액(원) | ✕ | KR | 수급 | 0 |
| `unrealized_pnl_pct` | 평가손익률 | — | — / 이 종목의 평가손익률 | ✕ | KR · US | 보유 스냅샷 | 0 |
| `weight_pct` | 비중 | — | — / 이 종목의 비중 | ✕ | KR · US | 보유 스냅샷 | 0 |

- `allowed_transforms`·`allowed_operators`로 말이 안 되는 조합을 UI에서 원천 차단한다. 사용자 상태 지표는 `identity`만, `range_pct`·`rsi`·`disparity`는 `identity`와 `delta`만 허용한다.
- 장중 알림의 왼쪽은 `intraday_left = ○`인 지표의 `identity`뿐이다. 오른쪽에 오는 종가 지표는 변형을 모두 쓸 수 있다.
- **RSI는 Wilder 평활을 `10 × n`봉(이력이 그보다 짧으면 있는 만큼, 최소 `n+1`봉) 위에서 계산한다.** Wilder 평활은 전체 이력에 의존하므로 계산 창을 고정해야 같은 데이터에서 같은 값이 나온다. 증권사 앱의 RSI와 소수점 아래에서 다를 수 있다.
- **사용자 상태 지표는 포트폴리오의 종목별 화면과 같은 값이다.** 모든 계좌를 합산한 그 종목 한 행의 `unrealized_pnl_pct`와 `weight_pct`이며, 비중의 분모는 예수금을 포함한 총자산이다(포트폴리오 스펙 §6.2). 기준은 그 거래일의 확정 스냅샷(`is_final = true`)이다.
- `scope = "user"` 지표를 쓰는 알림은 `CLOSE`만 가능하다. 보유 스냅샷이 하루 한 벌이기 때문이다.

### 5.2 변형 / 연산자 카탈로그

```
Transform: identity | window{fn, n, lag} | delta{n} | pct{n}
Operator:  gte, lte, gt, lt             (상수/Operand 비교)
         | crosses_above, crosses_below  (Operand끼리)
```

- `crosses_*`는 직전 데이터 시점의 두 값과 이번 두 값을 비교한다. `CLOSE`는 직전 거래일, `INTRADAY`는 같은 날 직전 스냅샷이 비교 대상이며, 같은 날 직전 스냅샷이 없으면 그 평가는 `UNKNOWN`이다.
- 상수와의 교차는 두지 않는다. "상수를 위로 넘는 순간"은 `gte`와 엣지 발화(§6.2)로 이미 표현된다.

### 5.3 프리셋 카탈로그

```
Preset {
  key, label,
  kind: "template" | "native",
  cadences: [...],                       // 허용 평가 시점
  markets: [...],
  param_schema: { ... },                 // 파라미터 정의 + 기본값 + 제약
  compiles_to: <조립형 spec 생성기>,      // kind=template 일 때만
  scope
}
```

v1 프리셋은 9종이며 모두 템플릿이다.

| key | 라벨 | 파라미터 | 평가 시점 | 컴파일 결과 |
|---|---|---|---|---|
| `price_reach` | 가격 도달 | `price` · `direction`(up/down) | 장중 · 종가 | `price gte price` / `price lte price` |
| `change_move` | 급등락 | `pct` · `direction` | 장중 · 종가 | `change_pct gte pct` / `change_pct lte −pct` |
| `volume_surge` | 거래량 급증 | `n`=20 · `multiple`=3 | 장중 · 종가 | `volume_ratio(n) gte multiple` |
| `ma_cross` | 골든·데드크로스 | `short`=5 · `long`=20 · `direction` | 종가 | `sma(short) crosses_above sma(long)` / `crosses_below` |
| `rsi_zone` | RSI 과매수·과매도 | `n`=14 · `zone`(overbought 70 / oversold 30) · `level` | 종가 | `rsi(n) gte level` / `rsi(n) lte level` |
| `box_breakout` | 박스권 돌파 | `window_days`=20 · `max_range_pct`=15 · `direction` | 종가 | `range_pct(window_days) lte max_range_pct` AND `price gt window(max, high, window_days, lag 1)` (up) / `price lt window(min, low, window_days, lag 1)` (down) |
| `investor_streak` | 외국인·기관 연속 순매수 | `investor`(foreign/institution) · `side`(buy/sell) · `days`=3 | 종가 | `<investor>_net_buy gt 0` + `streak: days` (sell은 `lt 0`) |
| `investor_turn` | 외국인·기관 순매수 전환 | `investor` · `side` | 종가 | `<investor>_net_buy gt 0` AND `<investor>_net_buy window(max, 1, lag 1) lte 0` (sell은 부호 반대) |
| `pnl_reach` | 수익률 도달 | `pct` · `direction` | 종가 | `unrealized_pnl_pct gte pct` / `lte pct` (보유 종목만) |

- **박스권은 "직전 n일이 좁은 폭 안에 있었고, 오늘 그 폭을 벗어났다"로 정의한다.** 폭 조건이 없으면 "n일 신고가"와 같아지고, 폭 조건이 박스의 존재를 뜻한다. 이 정의가 조립형으로 표현되므로 상태 라벨이 필요 없다.
- **순매수 전환은 "오늘 순매수이고 어제는 순매수가 아니었다"로 컴파일한다.** 엣지 발화만으로 표현하면 알림을 만든 첫날 이미 순매수인 종목이 "전환"으로 울린다. 어제의 부호를 조건에 넣으면 전환이 아닌 날에는 참이 되지 않는다.
- **연속 순매수는 순매수 금액이 매일 0보다 큰 것이다.** 순매수 금액이 매일 늘어나는 것(`delta > 0`)과 다르다.
- 네이티브 프리셋과 평가기 레지스트리는 카탈로그 모양(`kind`)에만 남는다. v1에 등록된 네이티브 평가기는 없다(§17).

### 5.4 필요 데이터의 유도

지표의 `requires`가 데이터 종류를 선언한다.

| 데이터 종류 | 뜻 | 소유 |
|---|---|---|
| `INTRADAY_QUOTE` | 장중 스냅샷(현재가·당일 누적 거래량) | 데이터 |
| `DAILY_BAR` | 수정주가 일봉 | 데이터 |
| `DAILY_FLOW` | 투자자별 순매수 | 데이터 |
| `PORTFOLIO_SNAPSHOT` | 확정 보유 스냅샷(`position_line.is_final`) | 백엔드 |

알림 하나가 필요로 하는 데이터 = 그 알림 모든 피연산자의 `requires` 합집합. 필요한 이력 길이 = 피연산자별 `history` 최댓값 + `window.lag` + `streak − 1`. 평가기는 이 두 값으로 무엇을 기다리고 몇 봉을 읽을지 정한다.

### 5.5 버전과 폐기

- **카탈로그는 append-only다.** 지표·프리셋을 지우지 않고 `deprecated`로 표시한다. 폐기된 항목은 새 알림에서 고를 수 없고, 기존 알림은 계속 평가된다.
- **`spec_version`은 `trigger_spec`의 포맷 버전이다.** 읽을 때 코드가 최신 버전으로 업캐스팅하고, 저장할 때 최신 버전으로 쓴다.
- **업캐스팅은 뜻을 바꾸지 않는다.** 계산이 달라지는 변경은 새 지표·프리셋 키로 추가한다. 템플릿의 컴파일 결과를 고치는 것은 예외이며, 그때는 평가 상태를 다시 기준 잡는다(§6.6).

---

## 6. 발화 의미론

### 6.1 평가 결과

조건 하나의 결과는 `TRUE / FALSE / UNKNOWN` 셋 중 하나다. `UNKNOWN`의 사유는 §7.2.

AND 결합은 다음 순서로 판정한다.

1. 하나라도 `FALSE`면 `FALSE`
2. 아니고 하나라도 `UNKNOWN`이면 `UNKNOWN`
3. 모두 `TRUE`면 `TRUE`

확정된 거짓 하나가 결론을 정하므로, 다른 조건의 데이터가 없어도 거짓은 거짓이다.

### 6.2 발화 방식

| notify_mode | 화면 문구 | 발화 조건 | 발화 후 |
|---|---|---|---|
| **EDGE_REARM** (기본) | 돌파할 때마다 | 결과가 `TRUE`이고 엣지 기준이 `FALSE` | 계속 감시. 거짓으로 내려갔다 다시 참이 되면 재발화 |
| **ONE_SHOT** | 한 번만 | EDGE_REARM과 같음 | `status = ENDED` |
| **COOLDOWN** | N분마다 다시 | 결과가 `TRUE`이고, 엣지 기준이 `FALSE`이거나 마지막 발화 후 `cooldown_min`분이 지남 | 계속 감시 |

- **COOLDOWN은 장중 알림에만 있다.** 종가 알림은 하루에 한 번 평가되므로 분 단위 억제가 뜻이 없다. 종가 알림의 발화 방식은 `돌파할 때마다` · `한 번만` 둘이다.
- 계속 참인 동안 평가마다 발화하는 것을 막기 위해 **엣지 발화**가 기본이다.
- **`UNKNOWN`은 발화하지 않고 엣지 기준도 바꾸지 않는다.** `참 → 확인 불가 → 참`은 발화하지 않고, `거짓 → 확인 불가 → 참`은 발화한다. 데이터 공백이 재발화를 일으키지도 막지도 않는다.

### 6.3 첫 평가

알림을 만들거나, 다시 켜거나, 수정하면 **엣지 기준을 `FALSE`로 두고 시작한다.** 그래서 이미 조건을 충족 중이면 첫 평가에서 발화한다.

이 사실을 저장 전에 알린다. 미리보기(`POST /alerts/preview`)가 지금 충족 여부를 돌려주고, 충족 중이면 공통 설정 화면이 `지금 이미 조건을 충족하고 있어 곧 알림이 와요`를 표시한다(§15). 알림을 만든 사용자는 현재 상태를 알고 싶어 하므로, 침묵하는 쪽보다 알리는 쪽이 낫다.

### 6.4 평가 상태

알림마다 `alert_state` 한 행에 다음만 저장한다.

| 필드 | 뜻 |
|---|---|
| `last_result` | 마지막 평가 결과 (`TRUE`/`FALSE`/`UNKNOWN`) |
| `last_known_result` | 엣지 기준 (`TRUE`/`FALSE`) |
| `unknown_reason` | `last_result = UNKNOWN`일 때 사유 코드 |
| `evaluated_as_of` | 마지막으로 평가한 데이터 시점. 중복 평가 방지의 기준 (§8.2) |
| `spec_hash` | 평가에 쓴 컴파일 결과의 해시 (§6.6) |

마지막 발화 시각은 저장하지 않는다. 발화 기록(`alert_event`)에서 구한다. 같은 사실을 두 곳에 두면 어긋날 자리가 생긴다.

### 6.5 알림 상태

| status | 뜻 | 들어오는 경로 |
|---|---|---|
| `ACTIVE` | 감시 중 | 생성 · 다시 켜기 |
| `PAUSED` | 사용자가 끔 | 끄기 |
| `ENDED` | 한 번만 알림이 발화해 끝남 | ONE_SHOT 발화 (발화와 같은 트랜잭션) |
| `EXPIRED` | 유효기간이 지남 | `expires_at` 경과 (`ACTIVE`·`PAUSED`에서) |

- `ENDED`·`EXPIRED`는 `다시 켜기`로 `ACTIVE`가 된다. `EXPIRED`는 이때 새 유효기간(또는 무기한)을 함께 받는다.
- **재무장이라는 별도 조작은 없다.** `EDGE_REARM`·`COOLDOWN`은 스스로 다시 감시하고, 한 번만 알림을 다시 쓰려면 `다시 켜기`를 한다.
- 평가 대상은 `ACTIVE`이고 삭제되지 않은 알림뿐이다.

**목록 카드 문구**는 상태와 마지막 평가 결과로 정한다.

| 조건 | 문구 |
|---|---|
| `ACTIVE` · `last_result = TRUE` | `조건 충족 중` |
| `ACTIVE` · `last_result = FALSE` 또는 평가 전 | `감시 중` |
| `ACTIVE` · `last_result = UNKNOWN` | `확인 불가 · <사유>` (§7.2) |
| `PAUSED` | `꺼짐` |
| `ENDED` | `발화 후 종료` |
| `EXPIRED` | `만료` |

카드 둘째 줄의 `최근 발화 · 2시간 전`은 그 알림의 가장 최근 발화에서 온다.

### 6.6 조건 모양이 바뀔 때

`spec_hash`는 템플릿을 컴파일하고 정규화한 조건과 평가 시점의 해시다.

| 바뀐 원인 | 처리 |
|---|---|
| 사용자가 알림을 수정 | 저장하는 트랜잭션에서 상태를 새로 만든다. 엣지 기준 `FALSE`, 새 해시 (§6.3) |
| 템플릿 로직·업캐스팅이 바뀜 | 평가기가 해시 불일치를 발견하면 **발화하지 않고** 이번 결과로 엣지 기준을 잡는다 |

사용자 수정은 저장 시점에 해시를 갱신하므로, 평가 시점의 불일치는 항상 코드 변경에서 온다. 두 경우가 해시만으로 갈린다.

### 6.7 중복 경고

같은 사용자에게 **같은 종목 · 같은 평가 시점 · 같은 `spec_hash`**를 가진 `ACTIVE` 알림이 있으면 미리보기가 경고를 돌려준다. 저장은 막지 않는다. 프리셋으로 만든 것과 조립형으로 만든 것도 컴파일 결과가 같으면 중복이다.

### 6.8 삭제

알림은 소프트 삭제한다(`deleted_at`). 삭제된 알림은 평가·목록·중복 검사에서 빠진다.

**발화 기록은 남는다.** 울린 알림 목록과 상세는 삭제된 알림의 발화를 `삭제된 알림` 표시와 함께 그대로 보여준다. 이미 받은 푸시를 눌렀을 때 내용이 사라져 있으면 무엇이 울렸는지 알 방법이 없다.

### 6.9 발화 문구

제목과 본문은 **발화 시점에 서버가 완성해 저장한다.** 나중에 알림을 수정·삭제해도 그때 울린 내용은 바뀌지 않는다.

```
제목  삼성전자 · 가격 도달
본문  현재가 70,200원 ≥ 70,000원 · 10:15 기준

제목  카카오 · RSI 과매수
본문  RSI(14) 71.3 ≥ 70 · 9/26 종가 기준
```

본문은 관측값과 데이터 시점을 반드시 담는다. 밀린 종가를 따라잡아 발화한 경우(§3.3)에도 기준일이 문구에 있어 오해가 없다. 계좌번호·금액 등 계좌 정보는 문구에 넣지 않는다. 푸시는 잠금 화면에 보인다.

---

## 7. 결측·지연

### 7.1 완료 신호

평가기는 데이터가 "왔다"는 것을 **완료 신호**로 안다. 데이터가 `market_data_run`에 한 행을 남기며, 그 행이 `DONE`이면 그 시장의 대상 종목 전체가 그 시점까지 준비됐다는 뜻이다(스키마는 §16.2).

```
market_data_run  ── 한 행 = (시장, 데이터 종류, 데이터 시점)

KR · INTRADAY_QUOTE · 2026-09-26 10:15   DONE
KR · DAILY_BAR      · 2026-09-26         DONE
KR · DAILY_FLOW     · 2026-09-26         RUNNING
```

- `INTRADAY` 알림은 그 시장의 새 `INTRADAY_QUOTE` 신호마다 평가한다.
- `CLOSE` 알림은 **자기에게 필요한 데이터 종류(§5.4)가 그 거래일에 모두 `DONE`일 때** 평가한다. 가격만 보는 알림은 수급 도착을 기다리지 않는다.
- `PORTFOLIO_SNAPSHOT`은 백엔드 안의 사실이다. 그 거래일의 `position_line`이 확정(`is_final`)되면 준비된 것으로 본다.
- 종류마다 신호를 나누는 것은 도착 시각이 다를 수 있어서다. 하나로 묶으면 가장 늦는 데이터가 모든 알림을 붙잡는다.

**영원히 오지 않는 데이터로 멈추지 않는다.** 어떤 거래일 D의 신호가 `DONE`이 되기 전에 다음 거래일의 같은 종류가 `DONE`이 되면, D는 그 데이터 없이 평가한다. 그 데이터에 의존하는 조건은 `UNKNOWN(DATA_MISSING)`이 된다.

### 7.2 확인 불가 사유

| 코드 | 판정 | 카드 문구 |
|---|---|---|
| `DATA_MISSING` | 필요한 데이터가 그 시점에 없음(§7.1), 또는 보유 스냅샷의 해당 종목 행이 이월값 | `데이터 없음` |
| `INSUFFICIENT_HISTORY` | 필요한 이력 길이(§5.4)보다 봉이 적음 — 신규 상장 등 | `이력 부족` |
| `NO_TRADE` | 영업일인데 그 종목 봉이 없음 — 거래정지 등 | `거래 없음` |
| `PRICE_ADJUSTMENT_SUSPECTED` | 수정주가 미반영 의심 (§7.3) | `가격 보정 대기` |
| `NOT_HELD` | 사용자 상태 조건인데 그 거래일 스냅샷에 그 종목이 없음 | `미보유` |
| `INSTRUMENT_UNKNOWN` | 종목 마스터에서 종목을 찾을 수 없음 | `종목 정보 없음` |

- **연속 N거래일은 영업일 캘린더로 센다.** 영업일인데 봉이 없으면 연속이 끊긴다. 모르는 날을 참으로 세지 않는다.
- **`NOT_HELD`는 알림을 무효로 만들지 않는다.** 다시 사면 그날부터 평가가 이어진다. 매도로 알림이 사라지면 재매수할 때마다 다시 만들어야 한다.
- 보유 스냅샷의 이월 행(`is_carried_forward`)은 낡은 시세라 평가손익률·비중이 그날 값이 아니다. 그 종목의 행 중 하나라도 이월값이면 `DATA_MISSING`이다.

### 7.3 수정주가 미반영 의심

액면분할·병합이 보정되지 않은 계열로 지표를 계산하면, 분할 당일 해당 종목의 이동평균 교차·거래량 급증·RSI가 한꺼번에 참이 된다.

**국내 종목은 하루 종가 변동이 ±30%(가격제한폭)를 넘는 봉이 계산 창 안에 있으면 그 평가를 `UNKNOWN(PRICE_ADJUSTMENT_SUSPECTED)`로 둔다.** 정상 거래로는 넘을 수 없는 폭이므로 보정되지 않은 기업행위의 증거다. 신규 상장 첫날은 제한폭이 달라 판정에서 뺀다. 데이터가 보정된 계열을 주면 평가기가 이력을 다시 읽으므로(§2) 저절로 풀린다.

미국 종목은 가격제한폭이 없어 이 판정을 두지 않는다. 수정주가 계열 제공이 그대로 요구사항이다(§16.2).

### 7.4 사용자에게 보이는 것

| 자리 | 표시 |
|---|---|
| 알림 카드 | `확인 불가 · <사유>` (§6.5) |
| 알림 목록 상단 | `MARKET_DATA_DELAYED` notice — 사용자 알림이 기다리는 데이터 종류의 최신 `DONE`이 캘린더상 기대 시각보다 늦을 때 |
| 발화 문구 | 데이터 시점 (§6.9) |

장중 스냅샷이 늦어 평가하지 못한 구간은 따로 기록하지 않는다. 기록할 수 있는 것은 "평가하지 못했다"뿐이며, 그 사이에 조건이 참이었는지는 알 수 없다.

---

## 8. 평가 런타임

### 8.1 실행 형태

평가기·발송기·영수증 확인기는 **백엔드 앱(`portfolio-api`) 안의 스케줄 작업**이다. 별도 앱이나 Deployment를 두지 않고, 모든 복제본에서 돈다.

| 작업 | 주기 | 하는 일 |
|---|---|---|
| 평가기 | 1분 | 처리하지 않은 완료 신호를 찾아, 그 시장·평가 시점의 `ACTIVE` 알림을 평가 |
| 발송기 | 수 초 | 발송 대기 행을 집어 Expo Push로 전송 (§9.3) |
| 영수증 확인기 | 수 분 | 보낸 푸시의 전달 영수증을 조회 (§9.4) |

평가기는 (시장, 평가 시점, 데이터 시점)마다 대상 종목의 이력을 한 번씩 읽고, 그 종목에 걸린 알림들을 함께 평가한다. 만료(`expires_at` 경과)도 이 작업이 `EXPIRED`로 옮긴다.

### 8.2 중복 방지 — 잠금이 아니라 데이터로

복제본 여럿이 같은 신호를 동시에 처리해도 발화는 한 번이다.

1. **평가 결과 반영은 조건부 갱신이다.**
   ```sql
   UPDATE alert_state SET ..., evaluated_as_of = :as_of
    WHERE alert_id = :id
      AND (evaluated_as_of IS NULL OR evaluated_as_of < :as_of)
   ```
   갱신된 행이 없으면 다른 복제본이 이미 처리한 것이므로 결과를 버린다.
2. **발화 기록은 `(alert_id, as_of)`가 유일하다.** 1을 통과한 뒤에도 같은 발화가 두 번 들어가지 못한다.
3. **상태 갱신 · 발화 기록 · 기기별 발송 행 · ONE_SHOT의 `ENDED` 전이는 한 트랜잭션이다.** 발화했는데 기록이 없거나, 기록했는데 상태가 그대로인 경우가 생기지 않는다.
4. **발송기는 대기 행을 `FOR UPDATE SKIP LOCKED`로 집는다.** 한 발송 행은 한 복제본만 처리한다.

리더 선출·분산 잠금·별도 라이브러리가 필요 없다. 복제본 수와 무관하게 성립하는 성질이기 때문이다.

### 8.3 재시작

메모리에 들고 있는 상태가 없다. 이력은 DB에 있고 알림 상태는 `alert_state`에 있으므로, 재시작하면 처리하지 않은 완료 신호부터 이어간다. 밀린 신호는 §3.3의 규칙을 따른다.

### 8.4 되돌리는 조건

평가 한 번이 주기(1분)의 절반을 넘기거나 API 응답이 평가 주기에 맞춰 느려지면, 같은 이미지를 다른 프로필로 띄워 스케줄 작업만 도는 워커 Deployment로 분리한다. 중복 방지가 데이터에 있으므로 코드는 바뀌지 않는다. API 파드에서는 프로필로 스케줄을 끈다.

---

## 9. 발화 전달

### 9.1 발화 기록이 이력이자 발송 대기열이다

```
평가기 ─(한 트랜잭션)─▶ alert_state 갱신 + alert_event 추가 + 기기마다 alert_delivery(PENDING)
발송기 ─▶ PENDING을 SKIP LOCKED로 집어 Expo Push 전송 ─▶ SENT / 재시도 / FAILED
영수증 ─▶ 전달 영수증 조회. 기기 미등록이면 push_device 삭제
앱     ─▶ alert_event를 읽어 울린 알림 목록 · 미확인 배지
```

`alert_event` 한 테이블이 **발화 이력 · 앱 안 알림 목록 · 미확인 배지 · 푸시 재시도의 원천**을 모두 떠받친다. 발화와 상태 갱신이 같은 DB 트랜잭션이므로 발화가 사라지거나 두 번 생기지 않는다.

메시지 브로커를 두지 않는다. 브로커로 발행하면 DB 커밋과 발행을 한 번에 성공시킬 수 없어 결국 같은 대기 테이블이 필요하고, 앱의 목록도 DB 테이블을 요구한다. 지금 소비자는 푸시 발송 하나뿐이다(§17).

### 9.2 푸시 수신 기기

- 앱은 **첫 알림을 저장할 때** 푸시 권한을 요청한다. 로그인 직후에 묻지 않는다 — 알림을 만들지 않은 사용자에게는 권한을 줄 이유가 보이지 않는다.
- 권한을 받으면 Expo 푸시 토큰을 `POST /devices`로 등록한다. 앱이 시작될 때마다 다시 등록해 토큰 교체를 따라간다. 토큰이 이미 다른 사용자에게 등록돼 있으면 지금 사용자로 옮긴다.
- **로그아웃하면 `DELETE /devices/{id}`로 등록을 지운다.** 공용 기기에서 로그아웃한 사람의 알림이 오면 안 된다.

### 9.3 발송

- 발송기는 대기 행을 모아 Expo Push API로 보낸다.
- 전송 실패는 지수 백오프로 재시도하고, 상한 횟수를 넘으면 `FAILED`로 끝낸다. 기기 미등록 응답은 재시도하지 않고 `push_device`를 지운다.
- 발송 실패는 발화를 취소하지 않는다. 발화 기록과 배지는 그대로 남는다.
- 재시도 간격·상한 횟수는 구현 계획에서 정하는 운영값이다.

**푸시 페이로드**

```json
{ "to": "ExponentPushToken[…]",
  "title": "삼성전자 · 가격 도달",
  "body": "현재가 70,200원 ≥ 70,000원 · 10:15 기준",
  "data": { "event_id": "…", "url": "…://alert-events/…" } }
```

앱이 푸시를 눌렀을 때 여는 곳과 앱 상태별 동작은 [앱 정보 구조](../app-information-architecture.md) §4가 정의한다.

### 9.4 영수증

Expo는 전송 요청에 접수 티켓을 주고, 실제 전달 결과는 나중에 영수증으로 준다. 영수증 확인기가 `expo_ticket_id`로 결과를 조회해, 기기 미등록이면 `push_device`를 지우고 전달 실패는 `alert_delivery`에 기록한다. 조회 시점과 보관 기간은 구현 계획에서 Expo 문서로 확인해 정한다.

### 9.5 권한 거부·기기 없음

기기가 하나도 없거나 권한을 거부한 사용자도 **발화 기록은 남는다.** 그러면 발송 행이 만들어지지 않을 뿐, 울린 알림 목록과 탭 배지로 반드시 보인다. 권한을 거부한 상태는 알림 탭 상단 배너로 알리고 설정 화면으로 유도한다(§15).

### 9.6 v1 플랫폼 제약

**v1의 앱 푸시는 iOS에서만 동작한다.** 앱은 Expo Go로 실기기 검증을 하는데, Expo Go는 SDK 53부터 Android에서 원격 푸시를 지원하지 않는다. 그래서 Android 기기는 토큰을 등록하지 않으며, 발화는 앱 안 목록과 배지로만 확인한다. 알림 탭에 `Android에서는 앱 안에서만 알림을 확인할 수 있어요`를 표시한다.

발송 경로(Expo Push)는 플랫폼과 무관하므로, 개발 빌드로 전환하면 서버 변경 없이 Android 푸시가 열린다(§17).

### 9.7 자격증명

Expo 푸시 접근 토큰은 코드·로그·저장소에 넣지 않고 Secret으로 주입한다. 푸시 토큰은 로그에 원문으로 남기지 않는다.

---

## 10. 데이터 모델

### 10.1 테이블 — 백엔드 소유

**`alert`** 알림

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `alert_id` | uuid PK | |
| `user_id` | uuid | 소유자 → `app_user.id`. **생성 후 바뀌지 않는다** |
| `instrument_id` | uuid | 데이터 소유 `instrument` 참조. 팀 간 배포 순서를 묶지 않으려고 FK를 걸지 않는다 |
| `name` | text | 사용자 지정 이름. 1~40자 |
| `cadence` | text | `INTRADAY` · `CLOSE` |
| `notify_mode` | text | `EDGE_REARM` · `ONE_SHOT` · `COOLDOWN` |
| `cooldown_min` | int null | `COOLDOWN`일 때만 |
| `expires_at` | timestamptz null | null이면 무기한 |
| `status` | text | `ACTIVE` · `PAUSED` · `ENDED` · `EXPIRED` |
| `trigger_type` | text | `COMPOSABLE` · `PRESET` |
| `trigger_spec` | jsonb | §4.2 · §4.3 |
| `spec_version` | int | §5.5 |
| `created_at` · `updated_at` | timestamptz | |
| `deleted_at` | timestamptz null | 소프트 삭제 (§6.8) |

**소유권 축은 `alert.user_id` 하나다.** 상태·발화·발송 행은 전부 `alert_id`를 거쳐 소유자가 정해진다. 포트폴리오의 소유권이 계좌에 있는 것과 다른 이유는 알림이 보유하지 않은 종목에도 걸려 계좌를 거칠 수 없어서다(§1.1). 한 사용자의 알림이 계좌 연동·해제와 무관하게 유지된다.

**`alert_state`** 평가 상태 — 알림과 1:1

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `alert_id` | uuid PK | |
| `last_result` | text null | `TRUE` · `FALSE` · `UNKNOWN`. 평가 전 null |
| `last_known_result` | text | `TRUE` · `FALSE`. 엣지 기준 |
| `unknown_reason` | text null | §7.2 코드 |
| `evaluated_as_of` | timestamptz null | 마지막으로 평가한 데이터 시점. 종가는 그 거래일의 시장 마감 시각으로 기록한다 |
| `spec_hash` | text | §6.6 |

**`alert_event`** 발화 — 이력이자 발송 대기열

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `event_id` | uuid PK | |
| `alert_id` | uuid | |
| `as_of` | timestamptz | 발화를 만든 데이터 시점 |
| `fired_at` | timestamptz | 기록 시각 |
| `title` · `body` | text | 발화 시점에 완성한 문구 (§6.9) |
| `observed` | jsonb | 판정에 쓴 값. 예: `{ "price": 70200, "threshold": 70000 }` |
| `read_at` | timestamptz null | 미확인 배지 |

UNIQUE `(alert_id, as_of)` — 한 알림은 한 데이터 시점에 최대 한 번 발화한다(§8.2).

**`alert_delivery`** 기기별 발송

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `event_id` · `device_id` | uuid | PK |
| `state` | text | `PENDING` · `SENT` · `FAILED` |
| `attempts` | int | |
| `next_attempt_at` | timestamptz | |
| `expo_ticket_id` | text null | 영수증 조회용 |
| `last_error` | text null | |

발화와 분리하는 것은 한 사용자가 기기를 여럿 가질 수 있어서다. 기기마다 성공·실패가 갈린다.

**`push_device`** 푸시 수신 기기

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `device_id` | uuid PK | |
| `user_id` | uuid | 지금 이 기기로 로그인한 사용자 |
| `expo_push_token` | text UNIQUE | |
| `platform` | text | `IOS` · `ANDROID` |
| `created_at` · `last_seen_at` | timestamptz | |

**`alert_watchlist`** 알림 대상 종목

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `instrument_id` | uuid PK | 삭제되지 않은 `ACTIVE` 알림이 걸린 종목 |
| `market` | text | |
| `intraday` | bool | 그 종목에 `INTRADAY` 알림이 있는가 |

알림이 생기거나 바뀔 때 백엔드가 갱신한다. 데이터는 `intraday = true`인 종목의 장중 스냅샷을 만들고, 미국 종목은 이 목록과 보유 종목의 일봉을 만든다(§16.2). 전 종목을 몇 분 간격으로 수집하는 것은 원천 호출 한도로 성립하지 않을 수 있고, 알림이 걸린 종목만 필요하다.

### 10.2 데이터 소유 테이블 (백엔드는 읽기만)

`instrument` · 수정주가 일봉 · 투자자별 순매수 · 장중 스냅샷 · `market_data_run` · `dim_market_calendar`. 컬럼과 제공 조건은 §16.2, 물리 테이블명은 데이터 팀 규약을 따른다.

장중 스냅샷은 레이크를 거치지 않고 앱 DB의 `data` 스키마에 직접 적재되어야 한다. 몇 분 단위 평가가 레이크 → 리버스ETL 경로의 지연을 견디지 못한다.

---

## 11. API 계약

### 11.1 엔드포인트

| 구분 | 경로 |
|---|---|
| 알림 | `GET /alerts` · `GET /alerts/{id}` · `POST /alerts` · `PUT /alerts/{id}` · `DELETE /alerts/{id}` |
| 상태 전환 | `POST /alerts/{id}/pause` · `POST /alerts/{id}/resume` |
| 미리보기 | `POST /alerts/preview` |
| 카탈로그 | `GET /alerts/catalog` |
| 종목 검색 | `GET /instruments?q=&held=` |
| 울린 알림 | `GET /alert-events` · `GET /alert-events/{id}` · `POST /alert-events/{id}/read` · `POST /alert-events/read-all` |
| 배지 | `GET /alert-events/unread-count` |
| 기기 | `POST /devices` · `DELETE /devices/{id}` |

인증은 포트폴리오와 같다(포트폴리오 스펙 §8.8). 전 엔드포인트가 토큰을 요구하고, 사용자 ID는 경로·쿼리·바디 어디에서도 받지 않는다.

`GET /instruments`는 알림 전용이 아니다. 종목을 고르는 모든 화면이 쓰는 앱 공통 검색이다. 응답 행의 `held`는 인증 주체의 최신 확정 스냅샷에 그 종목이 있는지다.

### 11.2 목록 응답 — 포트폴리오 봉투

`GET /alerts`와 `GET /alert-events`는 포트폴리오와 같은 봉투를 쓴다(포트폴리오 스펙 §8.2). 앱의 봉투 처리(배너·notices·빈 상태)를 그대로 재사용한다.

```json
// GET /alerts
{ "as_of": "2026-09-26T10:15:00+09:00",
  "data": {
    "rows": [
      { "alert_id": "…", "name": "삼성전자 7만원",
        "instrument": { "id": "…", "label": "삼성전자", "market": "KR" },
        "cadence": "INTRADAY", "notify_mode": "EDGE_REARM", "status": "ACTIVE",
        "summary": "현재가 ≥ 70,000원",
        "last_result": "UNKNOWN", "unknown_reason": "NO_TRADE",
        "evaluated_as_of": "2026-09-26T10:15:00+09:00",
        "last_fired_at": "2026-09-25T09:42:00+09:00" } ],
    "unread": [
      { "event_id": "…", "title": "카카오 · RSI 과매수",
        "as_of": "2026-09-25T15:30:00+09:00", "alert_deleted": false } ] },
  "empty_reason": null,
  "notices": [
    { "code": "MARKET_DATA_DELAYED", "severity": "warn",
      "message": "국내 장중 시세가 10:05 이후 들어오지 않았어요",
      "params": { "market": "KR", "kind": "INTRADAY_QUOTE",
                  "last_done": "2026-09-26T10:05:00+09:00" } } ] }
```

- `as_of`는 이 사용자의 알림이 평가된 가장 최근 데이터 시점이다. 평가된 알림이 없으면 null이다.
- `summary`는 서버가 완성한 조건 문장이다. `message`와 같은 원리로 앱은 그대로 출력한다.
- `unread`는 알림 탭 상단 `새로 울린 알림` 블록의 내용이다.
- `empty_reason`: `NO_ALERTS`(내 알림) · `NO_EVENTS`(울린 알림).
- notices: `MARKET_DATA_DELAYED` 하나. 발화 전달 실패는 notice가 아니다 — 발화 기록이 남아 사용자가 잃는 정보가 없다.

상세·생성·수정·미리보기·카탈로그는 봉투를 쓰지 않는다. 봉투는 "기준 시점이 있는 조회 결과"의 모양이다.

### 11.3 요청·응답

```json
// POST /alerts · PUT /alerts/{id}  (§13의 모양 그대로)
{ "instrument_id": "…", "name": "카카오 RSI 과열",
  "cadence": "CLOSE", "notify_mode": "EDGE_REARM", "cooldown_min": null,
  "expires_at": null,
  "trigger_type": "PRESET",
  "trigger_spec": { "preset_key": "rsi_zone",
                    "params": { "n": 14, "zone": "overbought", "level": 70 } } }
```

```json
// POST /alerts/preview  → 200
{ "valid": true,
  "errors": [],
  "current": { "result": "TRUE", "as_of": "2026-09-26T15:30:00+09:00",
               "observed": { "rsi": 71.3, "level": 70 } },
  "already_satisfied": true,
  "duplicate_of": null }
```

미리보기는 저장 전 초안 하나로 **검증 오류 · 지금 값 · 지금 충족 여부 · 중복**을 한 번에 돌려준다. 빌더와 프리셋 폼의 현재값 표시, 공통 설정의 "이미 충족 중" 경고, 중복 경고가 모두 이 응답에서 온다. 검증 오류는 저장 요청과 같은 규칙(§14)이며, 미리보기는 오류가 있어도 `200`으로 `errors`에 싣는다 — 입력 중인 폼의 상태이지 요청의 실패가 아니다.

```json
// GET /alert-events/{id}
{ "event_id": "…", "title": "삼성전자 · 가격 도달",
  "body": "현재가 70,200원 ≥ 70,000원 · 10:15 기준",
  "as_of": "2026-09-26T10:15:00+09:00", "fired_at": "2026-09-26T10:15:41+09:00",
  "observed": { "price": 70200, "threshold": 70000 },
  "read_at": "2026-09-26T10:20:03+09:00",
  "alert": { "alert_id": "…", "status": "ACTIVE", "deleted": false,
             "instrument": { "id": "…", "label": "삼성전자" } } }
```

```json
// GET /instruments?q=삼성
{ "rows": [ { "id": "…", "label": "삼성전자", "symbol": "005930",
              "market": "KR", "held": true } ] }
```

```json
// GET /alerts/catalog (발췌)
{ "indicators": [ { "key": "rsi", "label": "RSI", "unit": "ratio",
                    "params": [ { "key": "n", "default": 14, "min": 2, "max": 30 } ],
                    "intraday_left": false, "markets": ["KR", "US"],
                    "allowed_transforms": ["identity", "delta"],
                    "allowed_operators": ["gte", "lte", "gt", "lt", "crosses_above", "crosses_below"],
                    "scope": "market", "deprecated": false } ],
  "presets": [ { "key": "box_breakout", "label": "박스권 돌파", "cadences": ["CLOSE"],
                 "markets": ["KR", "US"], "param_schema": { … } } ],
  "transforms": [ … ], "operators": [ … ] }
```

### 11.4 오류

| 상황 | 코드 | `error.code` |
|---|---|---|
| 저장 검증 실패 | `400` | `INVALID_ALERT` + `fields[]` |
| 남의 알림이거나 없는 알림 | `404` | `ALERT_NOT_FOUND` |
| 남의 발화이거나 없는 발화 | `404` | `EVENT_NOT_FOUND` |
| 남의 기기이거나 없는 기기 | `404` | `DEVICE_NOT_FOUND` |
| 토큰 없음·만료 | `401` | `UNAUTHENTICATED` |

```json
{ "error": { "code": "INVALID_ALERT", "message": "조건을 확인해 주세요",
             "fields": [ { "path": "trigger_spec.conditions[0].modifier",
                           "code": "MODIFIER_NOT_ALLOWED",
                           "message": "종가 알림에는 N분 지속을 쓸 수 없어요" } ] } }
```

- `fields[].path`는 요청 JSON 경로다. 폼이 그 칸 아래에 `message`를 그대로 띄운다.
- **남의 것과 없는 것을 구분하지 않는다.** 구분하면 남의 알림 ID가 존재하는지가 응답 차이로 드러난다. 로그인 실패에서 이메일 유무를 구분하지 않는 것과 같은 원칙이다.

---

## 12. UI ↔ 모델 매핑

### 12.1 조립형(COMPOSABLE)

| UI 요소 | 모델 경로 | 검증 |
|---------|------------------|------|
| 대상 종목 | `alert.instrument_id` | 종목 마스터 존재 |
| 평가 시점(장중/종가) | `alert.cadence` | 종목 시장이 허용하는 값 (§3.2) |
| 지표 드롭다운 | `conditions[i].left.indicator` | 카탈로그 존재, 장중이면 `intraday_left` |
| 지표 파라미터 | `conditions[i].left.indicator_params` | 카탈로그 params 범위 |
| 변형 드롭다운 | `conditions[i].left.transform` | `allowed_transforms`, 장중이면 `identity` |
| 연산자 | `conditions[i].op` | `allowed_operators` |
| 기준값(상수/지표 토글) | `conditions[i].right` | 상수=number, 지표=Operand |
| 유지 방식 | `conditions[i].modifier` | 종가=`streak`, 장중=`persist_min` |
| ＋조건 추가(AND) | `conditions[]` 배열 push | 최소 1개 |
| 현재값 표시 | `POST /alerts/preview`의 `current` | — |
| 발화 방식 | `alert.notify_mode` (+ `cooldown_min`) | 쿨다운은 장중만 |
| 유효기간 | `alert.expires_at` | 미래 시각 |
| 알림 이름 | `alert.name` | 1~40자 |

### 12.2 프리셋(PRESET)

| UI 요소 | 모델 경로 | 검증 |
|---------|------------------|------|
| (조건 선택 카드) | `alert.trigger_type='PRESET'`, `spec.preset_key` | 카탈로그 존재, 종목 시장이 `markets`에 포함 |
| 평가 시점 | `alert.cadence` | 프리셋 `cadences`에 포함 |
| 파라미터 폼 필드 | `spec.params.*` | 카탈로그 `param_schema` |
| (공통 설정) | §12.1의 발화 방식·유효기간·이름과 동일 | 동일 |

### 12.3 목록·상세

| UI 요소 | 모델 경로 |
|---|---|
| 카드 상태 문구 | `status` + `last_result` + `unknown_reason` (§6.5) |
| 카드 조건 문장 | `summary` |
| 최근 발화 | `last_fired_at` |
| 새로 울린 알림 블록 | `data.unread` |
| 탭 배지 | `GET /alert-events/unread-count` |
| 데이터 지연 배너 | `MARKET_DATA_DELAYED` notice |
| 울린 알림 상세 | `alert_event` (`title` · `body` · `observed` · `as_of`) |

---

## 13. JSON 예시

### 13.1 조립형 — "일봉 기준, RSI가 3거래일 연속 70 이상"
```json
{
  "instrument_id": "…",
  "cadence": "CLOSE",
  "notify_mode": "EDGE_REARM",
  "trigger_type": "COMPOSABLE",
  "spec_version": 1,
  "trigger_spec": {
    "conditions": [
      {
        "left": { "indicator": "rsi", "indicator_params": { "n": 14 }, "transform": { "type": "identity" } },
        "op": "gte",
        "right": { "const": 70 },
        "modifier": { "streak": 3 }
      }
    ]
  }
}
```

### 13.2 조립형 — "외국인 3거래일 연속 순매수"
```json
{
  "cadence": "CLOSE",
  "trigger_type": "COMPOSABLE",
  "trigger_spec": {
    "conditions": [
      {
        "left": { "indicator": "foreign_net_buy", "transform": { "type": "identity" } },
        "op": "gt",
        "right": { "const": 0 },
        "modifier": { "streak": 3 }
      }
    ]
  }
}
```

### 13.3 프리셋 — "박스권 20일 상단 돌파"
```json
{
  "cadence": "CLOSE",
  "notify_mode": "EDGE_REARM",
  "trigger_type": "PRESET",
  "trigger_spec": {
    "preset_key": "box_breakout",
    "params": { "window_days": 20, "max_range_pct": 15, "direction": "up" }
  }
}
```

### 13.4 조립형 — 두 지표 비교 + AND (예: "5일선 > 20일선 AND 거래량 배수 ≥ 2")
```json
{
  "cadence": "CLOSE",
  "trigger_type": "COMPOSABLE",
  "trigger_spec": {
    "conditions": [
      {
        "left":  { "indicator": "sma", "indicator_params": { "n": 5 },  "transform": { "type": "identity" } },
        "op": "gt",
        "right": { "indicator": "sma", "indicator_params": { "n": 20 }, "transform": { "type": "identity" } },
        "modifier": null
      },
      {
        "left":  { "indicator": "volume_ratio", "indicator_params": { "n": 20 }, "transform": { "type": "identity" } },
        "op": "gte",
        "right": { "const": 2 },
        "modifier": null
      }
    ]
  }
}
```

### 13.5 조립형 — 장중 "현재가가 직전 20일 최고가를 넘고 10분 지속"
```json
{
  "cadence": "INTRADAY",
  "notify_mode": "COOLDOWN",
  "cooldown_min": 60,
  "trigger_type": "COMPOSABLE",
  "trigger_spec": {
    "conditions": [
      {
        "left":  { "indicator": "price", "transform": { "type": "identity" } },
        "op": "gt",
        "right": { "indicator": "high", "transform": { "type": "window", "fn": "max", "n": 20, "lag": 0 } },
        "modifier": { "persist_min": 10 }
      }
    ]
  }
}
```

장중 알림의 오른쪽 종가 지표는 직전 거래일까지의 이력으로 계산되므로(§3.1), 여기서 `lag: 0`인 20봉 윈도우는 오늘을 포함하지 않는다.

---

## 14. 검증 규칙

저장 전 **앱 계층에서 반드시 통과**해야 하는 규칙. JSON은 DB가 무결성을 보장하지 않으므로 이 관문이 사실상의 계약이다. 미리보기와 저장이 같은 규칙을 쓴다.

### 14.1 공통(봉투)

| 필드 | 규칙 |
|------|------|
| `instrument_id` | 종목 마스터에 존재 |
| `cadence` | enum |
| `notify_mode` | enum. `COOLDOWN`이면 `cadence = INTRADAY`이고 `cooldown_min >= 1` |
| `expires_at` | null 또는 현재 이후 |
| `name` | 1~40자, 공백만은 불가 |
| user-scope 지표 포함 | `cadence = CLOSE`이고, 저장 시점에 최신 확정 스냅샷에서 보유 중 |

### 14.2 조립형 조건

| 규칙 |
|------|
| `conditions` 최소 1개 |
| 각 `indicator`가 카탈로그에 존재하고 `deprecated`가 아님, 종목 시장이 지표 `markets`에 포함 |
| `indicator_params`가 카탈로그 범위 안 |
| `transform.type`이 지표의 `allowed_transforms`에 포함. `window.n` 1~120, `window.lag` 0~5, `delta.n`·`pct.n` 1~120 |
| `op`가 지표의 `allowed_operators`에 포함 |
| `right.const`는 number. `right`가 Operand면 같은 규칙을 재귀 적용 |
| `crosses_*` 연산자는 `right`가 Operand |
| `INTRADAY`: `left`는 `intraday_left` 지표의 `identity` |
| `INTRADAY`: `modifier`는 null 또는 `persist_min` 1~60 / `CLOSE`: null 또는 `streak` 1~20 |
| user-scope 지표와 market-scope 지표 혼용 허용 |

### 14.3 프리셋

| 규칙 |
|------|
| `preset_key`가 카탈로그에 존재하고 `deprecated`가 아님 |
| `cadence`가 프리셋 `cadences`에, 종목 시장이 `markets`에 포함 |
| `params`가 `param_schema`를 만족(필수·타입·범위) |
| 컴파일 결과가 §14.2를 통과 |

### 14.4 런타임 불변식

| 규칙 |
|------|
| 평가 대상은 `status = ACTIVE`이고 `deleted_at IS NULL`인 알림뿐 |
| `alert_state` 갱신은 `evaluated_as_of < :as_of`일 때만. 데이터 시점은 뒤로 가지 않는다 |
| `alert_event`는 `(alert_id, as_of)`마다 최대 1행 |
| 상태 갱신 · 발화 기록 · 발송 행 · `ENDED` 전이는 한 트랜잭션 |
| `UNKNOWN`은 발화하지 않고 `last_known_result`를 바꾸지 않는다 |
| AND 결합은 FALSE 우선, 그다음 UNKNOWN (§6.1) |
| 해시 불일치가 평가 시점에 발견되면 발화 없이 기준을 다시 잡는다 (§6.6) |
| 연속 거래일은 영업일 캘린더로 센다. 영업일에 봉이 없으면 연속이 끊긴다 |
| 오래된 장중 스냅샷(허용 지연 초과)은 평가하지 않는다 |

### 14.5 소유

| 규칙 |
|------|
| 모든 조회·변경은 인증 주체의 `user_id`로 스코프된다 |
| 남의 알림·발화·기기와 없는 것은 같은 `404`로 답한다 |
| `alert.user_id`는 생성 후 변경 불가 |
| 기기 등록 시 토큰이 다른 사용자에게 있으면 인증 주체로 옮긴다 |

---

## 15. 화면 상태 전수 (State Matrix)

와이어플로우는 해피패스만 시각화한다. 아래는 화면별로 구현해야 할 상태 전수다. 화면 이름과 진입 경로는 [앱 정보 구조](../app-information-architecture.md) §2.

| 화면 | 상태 |
|------|------|
| 알림 (탭 루트) | default / **빈 목록(온보딩)** / 로딩 / 새로 울린 알림 있음·없음 / 카드 상태 6종(§6.5) / **데이터 지연 배너** / **푸시 미허용 배너 + 설정 유도** / **Android 안내** |
| 울린 알림 | default / 빈 목록 / 삭제된 알림의 발화 / 모두 읽음 |
| 울린 알림 상세 | default / **삭제된 알림**(`알림 보기` 숨김) / **찾을 수 없음**(다른 계정·없는 발화) |
| 알림 상세 | default / 확인 불가 사유 / 종료·만료(`다시 켜기`) / 삭제 확인 |
| 종목 선택 | default(보유 종목 구역 + 검색) / 검색 결과 없음 / 보유 종목 없음 / 종목 마스터 비어 있음 |
| 조건 선택 | default / 카탈로그 로딩 / **종목 시장이 지원하지 않는 프리셋 비활성** / 보유하지 않은 종목의 수익률 도달 비활성 |
| 프리셋 입력 | default / **필수 파라미터 미입력(인라인 에러)** / 현재값 로딩·표시 / 저장 버튼 비활성 |
| 조건 만들기 | default / **기준값 미입력·조건 0개(인라인 에러)** / 장중·종가 전환 시 허용되지 않는 칸 초기화 / 현재값 로딩·표시 / 저장 버튼 비활성 |
| 공통 설정 | default / **이미 충족 중 경고** / **중복 경고** / 저장 중 / **저장 실패·재시도** / 검증 실패(`fields[]`) / 첫 저장 시 푸시 권한 요청 |

빈 상태는 `empty_reason`, 데이터 지연은 `notices`, 카드 상태는 행 필드로 표현한다(§11.2).

> 뒤로·취소·수정 이동은 각 화면 네비바의 `‹`로 일관 제공한다(별도 흐름선 없음).

---

## 16. 역할 분담

### 16.1 영역별

경계는 **"기관 고유성이 사라지는 지점"**이다. 원천마다 다른 응답을 흡수해 기관 중립적인 시세·수급 계열로 만드는 것까지가 데이터, 그 계열 위에 알림 규칙을 얹는 것이 백엔드다.

| 영역 | 데이터 | 백엔드 |
|---|---|---|
| 수집 | 일봉·수급·장중 시세 수집, 원천 장애 대응 | — |
| 참조 데이터 | 종목 마스터, 영업일 캘린더, **수정주가 보정** | 조인만 |
| 지표 계산 | — | 이동평균·RSI·이격도·윈도우·변화량·교차·연속 (§5) |
| 평가·발화 | — | 평가 시점 판정, 3값 평가, 엣지, 발화 기록 (§6 · §8) |
| 전달 | — | 기기 등록, Expo Push 발송·재시도·영수증 (§9) |
| 알림 대상 종목 | 목록의 종목만 장중 스냅샷 · 미국 일봉 | 목록 유지 (`alert_watchlist`) |

**지표는 백엔드가 계산한다.** 사용자가 기간을 고르므로(RSI 9·14, 이동평균 5·20·60) 미리 계산된 고정 메뉴로는 카탈로그가 성립하지 않고, 조립형의 윈도우·변화량은 어차피 백엔드가 계산해야 한다. 이동평균은 종가의 윈도우 평균이므로 계산을 한곳에 모은다.

**수정주가 보정은 데이터가 한다.** 기업행위 원천을 대조해 계열을 고치는 일은 기관 중립적인 참조 데이터 손질이고, 포트폴리오의 `corporate_action`·`ca_coverage`와 같은 원천을 쓴다.

### 16.2 데이터 요구사항

이 절이 데이터에 요구하는 것의 전부다. 각 항목은 **무엇이 · 어떤 모양으로 · 언제까지 필요하고 · 충족되지 않으면 기능이 어떻게 동작하는지**를 적는다. 원천과 수집 방법은 데이터가 정한다.

**① 종목 마스터 `instrument`**

| 항목 | 요구 |
|---|---|
| 필드 | `instrument_id` · `symbol` · `name` · `market` · `currency` (포트폴리오 스펙 §5.1과 같은 테이블) |
| 범위 | 국내 상장 주식·ETF 전체, 미국 NYSE·NASDAQ 상장 보통주·ETF |
| 갱신 | 거래일 1회 |
| 추가 요구 | 이름·종목코드 부분 일치 검색이 가능한 형태 |
| 충족 안 될 때 | 종목 선택 화면이 비고 알림을 만들 수 없다. 사라진 종목의 기존 알림은 `INSTRUMENT_UNKNOWN` |

**② 수정주가 일봉**

| 항목 | 요구 |
|---|---|
| 키 | `(instrument_id, date)` — `date`는 시장 현지 거래일 |
| 필드 | `open` · `high` · `low` · `close` · `volume` — **기업행위 보정 계열** |
| 시장 | KR · US — 미국은 보유 종목과 `alert_watchlist`의 종목 |
| 이력 | 종목마다 최소 **300거래일** (RSI 최대 기간 30 × 10, §5.1) |
| 시점 | KR: 장 마감 후 당일 중 / US: 미국 장 마감 후 다음 국내 영업일 개장 전 |
| 완료 신호 | 시장·거래일마다 `DAILY_BAR` |
| 충족 안 될 때 | 이력 부족 → `INSUFFICIENT_HISTORY` · 그날 누락 → 다음 거래일 신호가 오면 `DATA_MISSING`으로 넘어감 · 보정 누락(KR) → `PRICE_ADJUSTMENT_SUSPECTED` · 보정 누락(US) → **오발화 가능**, 판정 수단 없음 |

**③ 투자자별 순매수 (일별)**

| 항목 | 요구 |
|---|---|
| 키 | `(instrument_id, date)` |
| 필드 | `foreign_net_buy_krw` · `institution_net_buy_krw` — 순매수 금액(원), 순매도는 음수 |
| 시장 | KR |
| 기준 | **장 마감 후 확정치.** 장중 잠정치로 채우지 않는다 — 잠정치와 확정치의 부호가 갈리면 "연속 순매수"가 잘못 울린다 |
| 이력 | 최소 30거래일 (연속 일수 최대 20 + 전환 판정 1) |
| 시점 | 다음 국내 영업일 개장 전 |
| 완료 신호 | `DAILY_FLOW` |
| 충족 안 될 때 | 수급 조건이 있는 알림만 대기, 다음 거래일 신호가 오면 `DATA_MISSING`. 가격 알림은 영향 없음 |

**④ 장중 스냅샷**

| 항목 | 요구 |
|---|---|
| 키 | `(instrument_id, snapshot_at)` |
| 필드 | `price`(현재가) · `cum_volume`(당일 누적 거래량) |
| 시장 | KR · US |
| 대상 | 백엔드 `alert_watchlist`에서 `intraday = true`인 종목 (§10.1) |
| 주기 | 장중 **5분** 이하 |
| 적재 | **앱 DB `data` 스키마에 직접** — 레이크 경유 불가 (§10.2) |
| 보관 | 최소 당일분 — 미국은 현지 거래일 기준 (N분 지속 판정이 당일 스냅샷을 다시 읽는다) |
| 허용 지연 | 스냅샷 시각 기준 국내 **10분** · 미국 **20분**(15분 지연 시세 허용). 넘으면 백엔드가 평가하지 않는다 |
| 완료 신호 | 스냅샷 한 벌마다 `INTRADAY_QUOTE` |
| 충족 안 될 때 | 장중 알림이 평가되지 않고 `MARKET_DATA_DELAYED` 배너가 뜬다. 종가 알림은 영향 없음 |

**⑤ 완료 신호 `market_data_run`**

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `market` | text | `KR` · `US` |
| `kind` | text | `INTRADAY_QUOTE` · `DAILY_BAR` · `DAILY_FLOW` |
| `as_of` | timestamptz | 장중은 스냅샷 시각, 일별은 그 거래일의 시장 마감 시각 |
| `state` | text | `RUNNING` · `DONE` · `FAILED` |
| `finished_at` | timestamptz null | |

PK `(market, kind, as_of)`. 데이터가 쓰고 백엔드는 읽기만 한다. `DONE`은 그 시장의 대상 종목 전체가 그 시점까지 적재됐다는 뜻이다 — 일부만 적재된 상태에서 `DONE`을 쓰면 빠진 종목이 `NO_TRADE`로 오판된다.

**⑥ 영업일 캘린더 `dim_market_calendar`**

| 항목 | 요구 |
|---|---|
| 필드 | `market` · `date` · `is_trading_day` · `prev_trading_day` · `next_trading_day` · **`open_at` · `close_at`** |
| 범위 | KR · US, 과거 300거래일 ~ 향후 1년 |
| 공유 | 포트폴리오의 영업일 판정과 같은 테이블 |
| 충족 안 될 때 | 평일 근사로 동작하되 휴장일이 `NO_TRADE`로 판정되어 연속 조건이 끊긴다. 지연성 판정(`MARKET_DATA_DELAYED`)이 개장 지연일을 오판한다 |

`open_at`·`close_at`는 개장이 늦춰지는 날의 지연 판정과 종가 `as_of`에 필요하다.

### 16.3 팀 경계 인터페이스

| 산출물 | 제공 → 소비 | 합의가 필요한 것 |
|---|---|---|
| 종목 마스터 | 데이터 → 백엔드 | 포트폴리오와 같은 테이블. 검색 가능한 형태 · 미국 종목 범위 |
| 수정주가 일봉 | 데이터 → 백엔드 | 테이블명 · `instrument_id` 키 · 보정 계열 · 이력 길이 · 도착 시점 |
| 투자자별 순매수 | 데이터 → 백엔드 | 확정치 기준 · 금액 단위 · 도착 시점 |
| 장중 스냅샷 | 데이터 → 백엔드 | 앱 DB 직접 적재 · 주기 · 보관 |
| `alert_watchlist` | 백엔드 → 데이터 | 데이터에 읽기 권한 · 목록 반영 주기 |
| `market_data_run` | 데이터 → 백엔드 | 종류 · `DONE`의 의미(대상 전체 적재) · 백엔드 읽기 권한 |
| 영업일 캘린더 | 데이터 → 백엔드 | 개장·마감 시각 컬럼 · 범위 |
| Expo 푸시 접근 토큰 | 인프라 → 백엔드 | Secret 주입 · 클러스터에서 Expo 서버로 나가는 통신 |

테이블 소유: 백엔드는 `alert` · `alert_state` · `alert_event` · `alert_delivery` · `push_device` · `alert_watchlist`를, 데이터는 `instrument` · 수정주가 일봉 · 투자자별 순매수 · 장중 스냅샷 · `market_data_run` · `dim_market_calendar`를 소유한다.

**사용자는 백엔드 안에만 있다.** `alert_watchlist`는 종목 목록일 뿐 누가 알림을 걸었는지 담지 않는다. 데이터는 어느 종목을 수집할지만 알면 된다.

---

## 17. 미결 / 향후 확장 (YAGNI 경계)

초기 범위에서 **의도적으로 제외**한 것들.

- **OR / 불리언 트리**: AND 평탄 리스트만. OR는 "알림 2개"로 대체된다. 트리 UI는 일반 사용자에게 과하다.
- **피연산자 산술**: 두 지표의 비율·배수를 조건 안에서 계산하지 않는다. 자주 쓰이는 비율은 지표로 정의한다(`volume_ratio` · `disparity` · `range_pct`).
- **한 알림 안에 장중·종가 혼합**: 한 알림은 하나의 평가 시점. 장중 조건이 확정된 종가 값을 오른쪽에 쓰는 것으로 대부분의 수요가 충족된다(§3.1).
- **방해 금지 시간대**: 미국 장중 알림은 한국 시간 새벽에 울린다. 시간대별 푸시 억제를 두지 않는다 — 발화 기록은 남고 푸시만 늦출 대상이라 전달 계층에 붙이면 된다.
- **네이티브 프리셋(L5 상태 전이)**: v1 프리셋은 전부 템플릿이다. 조립형으로 표현되지 않는 프리셋이 생기면 평가기 레지스트리에 등록한다.
- **레버리지 장기보유 괴리 경고**: 레버리지 여부·배율·기초지수·보유 시작일이 필요하며 넷 모두 원천이 없다(포트폴리오 스펙 §1.2 레버리지 축도 미확보).
- **보유기간 지표**: 보유 시작일 원천이 없다. `position_basis.coverage_start_at`은 거래내역 확보 시작일이지 보유 시작일이 아니다.
- **ETF 구성종목 가중 합산 수급**: 국내 ETF 구성종목 확보에 종속된다(포트폴리오 설계 공유 안건 9).
- **MACD · 볼린저밴드 등 추가 기술지표**: 카탈로그에 지표를 더하는 일이며 스키마는 그대로다.
- **Android 앱 푸시**: 개발 빌드(expo-dev-client)로 전환하면 서버 변경 없이 열린다(§9.6).
- **메시지 브로커 발행**: 발화를 다른 시스템이 소비해야 할 때 `alert_event`에서 내보낸다(§9.1).
- **평가하지 못한 장중 구간의 기록**: 조건이 참이었는지 알 수 없어 기록할 내용이 없다(§7.4).
- **종목 선택의 최근 조회**: 기기별 저장소가 필요하다.
- **사용자당 알림 수 상한**: 두지 않는다. 평가 비용이 문제가 되면 도입한다.
- **알림 공유 · 템플릿 마켓 · 백테스트(과거 데이터로 조건 검증)**: 후속 과제.

---

## 18. 다음 단계

1. **팀 경계 합의** — §16.3 ([설계 공유 및 합의 요청](../../meetings/2026-09-27-buy-sell-timing-alert-design-review.md))
2. **구현 계획** — 카탈로그·컴파일러 → 스키마·마이그레이션 → 검증·미리보기 → 평가기(종가 → 장중) → 발화 기록·발송기 → API → 앱(알림 탭 → 새 알림 흐름 → 울린 알림 → 딥링크) → 상태 화면

구현 계획 단계에서 확정하는 것: 인덱스와 제약조건, 발송 재시도 간격·상한, 영수증 조회 시점, 장중 허용 지연·주기의 운영값, `spec_hash`의 정규화 규칙.
