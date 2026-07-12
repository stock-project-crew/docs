# 매수·매도 타이밍 알림 (Buy/Sell Timing Alert) — 설계 스펙

- **버전**: v1 (2026-07-12)
- **상태**: 설계 합의 완료 → 구현 계획 착수 전
- **범위**: 조건 설정 UI/UX, 데이터 모델(DB 저장 구조), 발화 의미론, 평가 엔진 개념
- **비범위(이번 스펙에서 다루지 않음)**: 데이터 수급 방식(어디서 어떻게 시세·수급을 받는지), 실제 인프라/스케일링, 푸시 발송 채널 구현
- **관련 자료**: [`wireflow.drawio`](./wireflow.drawio) / [`wireflow.png`](./wireflow.png)

---

## 1. 개요

### 1.1 기능 요약
사용자가 사전에 **조건**을 설정해두면, 시스템이 실시간 데이터(시세·수급·보조지표 등)를 평가하다가 조건이 충족되는 순간 **앱 푸시**를 발송한다.

예시 조건:
- 가격이 특정 값에 도달
- 박스권 상단 돌파 / 하단 이탈
- 외국인 순매수 3일 연속 증가
- 레버리지 장기보유 괴리 경고

> 위 4개는 **예시**이며 지원 범위를 닫는 목록이 아니다. 실제 지원 범위는 §2의 3축 분해로 정의된다.

### 1.2 핵심 설계 방향 (하이브리드)
조건 생성을 두 방식으로 제공하고, **하나의 저장 구조로 통합**한다.

- **조립형(Composable)**: 사용자가 `지표 + 변형 + 연산자 + 기준값`을 AND로 조합해 직접 조건을 만든다.
- **프리셋(Preset)**: 미리 만들어둔 알림 유형(박스권 돌파, 외국인 추세, 괴리 경고 등)을 카드로 제공하고, 사용자는 파라미터만 채운다.

두 방식 모두 최종적으로 `trigger_type + trigger_spec(JSON)` 하나의 형태로 저장된다. → §3, §8.

### 1.3 용어 (Glossary)
| 용어 | 의미 |
|------|------|
| **Alert (봉투)** | 사용자가 만든 알림 1개 인스턴스. 대상·발화모드 등 공통 속성 + trigger를 가짐 |
| **Trigger** | 발화를 결정하는 조건 명세. `COMPOSABLE` 또는 `PRESET` |
| **Operand (피연산자)** | `지표 + 변형(transform)`으로 만들어지는 비교 대상 값 |
| **Transform (변형)** | 지표에 씌우는 함수. `identity / window / delta / pct` |
| **Modifier** | 조건을 감싸는 유지 조건. `streak(N봉 연속)` 또는 `persist(N분 지속)` |
| **Timeframe (평가 기준)** | 알림 전체에 적용되는 봉 단위(틱/분/일). 윈도우·연속의 단위를 결정 |
| **notify_mode (발화 방식)** | `EDGE_REARM / ONE_SHOT / COOLDOWN` |
| **armed** | 조건을 감시 중인 상태(직전 평가가 거짓) |

---

## 2. 조건 모델 — 3축 분해

모든 조립형 조건은 3개 축의 조합으로 표현된다.

### 축 1 — 관찰 대상 (Subject: 무엇을 보나)
- 시세계열: 가격, 거래량, 등락률
- 수급: 외국인/기관 순매수, 프로그램매매
- 보조지표: RSI, MACD, 이동평균, 볼린저 등
- 파생/펀더멘털: PER, 괴리율, 미결제약정 등
- **사용자 상태(user scope)**: 보유 포지션, 평단, 보유기간 — 시세 엔진이 아닌 사용자 상태에서 옴

### 축 2 — 시간 형태 (Temporal shape: 어떻게 보나)
| 단계 | 형태 | 조립형 빌더 표현 | 상태 저장 |
|------|------|-----------------|-----------|
| L0 | 현재값 스냅샷 | transform=identity | 무상태 |
| L1 | 윈도우 집계(최근 N봉 max/min/avg/sum) | transform=window | 링버퍼 |
| L2 | 변화량/변화율 | transform=delta / pct | 앵커값 |
| L3 | 교차(cross) | operator=crosses_above/below | 직전 관계 |
| L4 | 연속성(N봉 연속) | modifier=streak(N) | 연속 카운터 |
| L5 | 상태 전이(박스권 진입→이탈) | — (프리셋으로만 제공) | 상태 라벨 |

- **조립형 빌더 지원 범위 = L0 ~ L4.** L5(상태머신)는 조립형에 넣지 않고 **네이티브 프리셋**으로 제공.
- L1~L5는 전부 "직전 평가/과거 데이터"를 들고 있어야 함 → 평가 엔진은 **상태를 가진 평가기(stateful evaluator)**. §6.

### 축 3 — 비교 방식 (Comparison: 무엇과 견주나)
- 상수 기준값 (예: 가격 ≥ 70,000)
- 다른 Operand와 비교 (예: 5일선 > 20일선)
- 자기 과거와 비교 (예: 오늘 거래량 > 20일 평균 거래량)

---

## 3. 통합 데이터 모델

### 3.1 봉투 + 다형 트리거
봉투(Alert)는 공통·안정적이므로 **관계형 컬럼**으로, `trigger_spec`은 종류마다 모양이 달라 **JSON(JSONB)**으로 저장한다. (근거·부작용은 §3.4)

```
alerts (
  id            UUID PK,
  user_id       UUID,
  symbol        TEXT,           -- 대상 종목/자산
  name          TEXT,           -- 사용자 지정 라벨
  timeframe     TEXT,           -- 평가 기준: 'TICK' | 'M1' | 'M5' | 'D1' ...
  notify_mode   TEXT,           -- 'EDGE_REARM' | 'ONE_SHOT' | 'COOLDOWN'
  cooldown_min  INT NULL,       -- notify_mode=COOLDOWN 일 때만
  expires_at    TIMESTAMPTZ NULL,
  market_hours_only BOOLEAN DEFAULT true,
  enabled       BOOLEAN DEFAULT true,
  trigger_type  TEXT,           -- 'COMPOSABLE' | 'PRESET'
  trigger_spec  JSONB,          -- 다형 명세 (아래)
  spec_version  INT DEFAULT 1,
  indicators_used TEXT[] NULL,  -- (선택) 조회용 파생 인덱스
  created_at, updated_at
)
```

런타임 상태(직전 참/거짓, 연속 카운터, 마지막 발화시각 등)는 별도 테이블/스토어에 둔다. §6.3.

### 3.2 trigger_spec — COMPOSABLE
```
spec = {
  conditions: [                       // AND로 결합 (OR 미지원 — §11)
    {
      left:  { indicator, indicator_params, transform },   // Operand
      op:    "gte|lte|gt|lt|crosses_above|crosses_below",
      right: { const: <number> }  |  { indicator, indicator_params, transform },
      modifier: { streak: <N> } | { persist_min: <N> } | null
    }
  ]
}
```
- `Operand = 지표 + 지표파라미터 + 변형`. 지표 자체가 파라미터를 가짐(RSI 기간, 이동평균 기간 등).
- `transform`: `{type:"identity"}` | `{type:"window", fn:"max|min|avg|sum", n:<N>}` | `{type:"delta", n:<N>}` | `{type:"pct", n:<N>}`
- 윈도우/연속의 **N의 단위는 alerts.timeframe**을 따른다. (예: timeframe=D1 + streak:3 = "3일 연속")

### 3.3 trigger_spec — PRESET
```
spec = {
  preset_key: "box_breakout",
  params: { window_days: 20, direction: "up" }
}
```
프리셋은 2종:
| 종류 | 정체 | 평가 |
|------|------|------|
| **템플릿 프리셋** | 조립형 spec으로 컴파일 가능한 것 | 조립형 엔진 재사용 |
| **네이티브 프리셋** | 상태머신·다중신호 도메인 로직(박스권 L5, 괴리경고) | 전용 평가기 |

- **템플릿 프리셋은 평가 시점에 컴파일한다(옵션 B).** DB엔 `preset_key + params`를 그대로 저장.
  - 이유 ① 사용자가 "수정" 시 프리셋 폼이 다시 떠야 자연스러움(원본 정체성 보존). ② 템플릿 로직 개선 시 기존 알림도 자동 반영.

### 3.4 왜 spec을 JSON으로 두나 (근거와 부작용)
**근거**: ① spec은 평가 시 항상 통째로 로드됨(문서형 접근). ② 조립형·프리셋마다 모양이 제각각(정규화 시 EAV 안티패턴 또는 프리셋당 테이블 폭발). ③ 지표·프리셋 추가 시 스키마 마이그레이션 불필요.

**부작용과 대응**:
| 부작용 | 대응 |
|--------|------|
| DB가 무결성 미보장(오타·타입) | **앱 계층 스키마 검증**을 저장 전 필수 관문으로 (§9) |
| spec 내부 조회 어려움 | 자주 쓰는 조회축만 `indicators_used` 등으로 **밖으로 파생 저장** |
| spec 포맷 변경 관리 | `spec_version` + 코드 업캐스팅 |
| 카탈로그 참조 FK 부재 | 카탈로그 append-only 운영(폐기는 deprecated 플래그) |

---

## 4. 카탈로그 (메타데이터 레지스트리)

카탈로그는 ① 빌더 UI 동적 렌더, ② 저장 전 spec 검증, ③ 엔진에 필요 데이터 선언 을 동시에 해결한다.

### 4.1 지표 카탈로그
```
Indicator {
  key, label, category,
  value_type: "number",
  unit: "point" | "krw" | "percent" | "shares",
  params: [ {key, default} ],            // 지표 자체 파라미터 (RSI period 등)
  allowed_transforms: [...],             // 이 지표에 허용되는 변형
  allowed_operators: [...],              // 허용 연산자
  scope: "market" | "user",              // 시장데이터 vs 사용자상태
  data_requirements: [...]               // 데이터 "정의"만 (수급 방식은 비범위)
}
```
- `allowed_*`로 말이 안 되는 조합을 UI에서 원천 차단(예: "보유기간 crosses_above 20일선" 방지).
- `scope="user"` 지표(보유·평단·보유기간)는 보유 종목에서만 대상 선택 가능.

### 4.2 변형 / 연산자 카탈로그
```
Transform: identity | window{fn,n} | delta{n} | pct{n}
Operator:  gte, lte, gt, lt            (상수/Operand 비교)
         | crosses_above, crosses_below (Operand끼리)
```

### 4.3 프리셋 카탈로그
```
Preset {
  key, label,
  kind: "template" | "native",
  param_schema: { ... },                 // 파라미터 정의 + 기본값 + 제약
  compiles_to: <조립형 spec 생성기>,      // kind=template 일 때만
  scope, data_requirements
}
```

### 4.4 data_requirements의 용도
사용자 알림들의 `data_requirements` 합집합 = "이 사용자를 굴리려면 필요한 데이터 스트림 목록"이 자동 산출된다. (수급 설계는 비범위지만, 정의는 이 스펙에서 확보)

---

## 5. 발화 의미론 (Notification Semantics)

### 5.1 발화 방식 (알림별 옵션)
| notify_mode | 동작 |
|-------------|------|
| **EDGE_REARM** (기본) | 조건이 `거짓→참`으로 바뀌는 순간 1회 발화. 다시 `참→거짓`으로 내려갔다 올라오면 재발화 |
| **ONE_SHOT** | 한 번 발화하면 알림 자동 비활성 |
| **COOLDOWN(min)** | 발화 후 N분 억제, 이후 여전히 참이면 재발화 |

- 계속 참으로 유지되는 동안 매 틱 발화하는 스팸을 방지하기 위해 **엣지 트리거**가 기본.

### 5.2 부속 설정
- **expires_at**: 유효기간(없으면 무기한). 만료 시 자동 비활성.
- **market_hours_only**: 장중에만 평가. 시세·수급성 알림은 사실상 필수.

### 5.3 발화 후 후속 동작
발화 후 사용자는 상세 화면에서 **재무장(다시 감시)** 또는 **종료**를 선택. (ONE_SHOT은 자동 종료)

---

## 6. 평가 엔진 개념

> 구현 상세가 아닌 **개념/요구사항** 수준. 데이터 수급은 비범위.

### 6.1 평가기 레지스트리 (dispatch)
DB엔 모두 `{trigger_type, trigger_spec}`로 동일하게 저장되고, 평가할 때만 종류로 분기한다.
- `COMPOSABLE` → 범용 operand/operator 평가기 1개
- `PRESET/box_breakout` → 등록된 전용 평가기
- `PRESET/leverage_divergence` → 등록된 전용 평가기
- 템플릿 프리셋 → 평가 시점에 조립형 spec으로 컴파일 후 범용 평가기 사용

### 6.2 두 입력 → 하나의 스키마 (수렴)
```
프리셋 입력(preset_key+params) ─┐
                               ├─ 검증 → 정규화(trigger_type+trigger_spec, JSONB) → 레지스트리 dispatch
조립형 입력(문장 슬롯→conditions[]) ─┘
```

### 6.3 상태 저장 요구 (stateful)
L1~L5·EDGE_REARM 때문에 조건별로 다음을 들고 있어야 한다:
- 직전 평가 참/거짓 (엣지 판정, 교차 판정)
- 윈도우 링버퍼 / 앵커값
- 연속 카운터(streak), 지속 시작시각(persist)
- 마지막 발화시각(cooldown)
- 상태 라벨(네이티브 프리셋 상태머신)

---

## 7. UI ↔ trigger_spec 필드 매핑 (추적성)

### 7.1 조립형(COMPOSABLE)
| UI 요소 | trigger_spec 경로 | 검증 |
|---------|------------------|------|
| 평가 기준(timeframe) | `alerts.timeframe` | enum 목록 |
| 지표 드롭다운 | `conditions[i].left.indicator` | 카탈로그 존재 |
| 지표 파라미터 | `conditions[i].left.indicator_params` | 카탈로그 params |
| 변형 드롭다운 | `conditions[i].left.transform` | allowed_transforms |
| 연산자 | `conditions[i].op` | allowed_operators |
| 기준값(상수/지표 토글) | `conditions[i].right` | 상수=number, 지표=Operand |
| 유지 방식(modifier) | `conditions[i].modifier` | `{streak:N>=1}` 또는 `{persist_min:N>=1}` |
| ＋조건 추가(AND) | `conditions[]` 배열 push | 최소 1개 |
| 발화 방식 | `alerts.notify_mode` (+ `cooldown_min`) | enum |
| 유효기간 | `alerts.expires_at` | 미래 시각 |
| 평가 시간 | `alerts.market_hours_only` | boolean |
| 알림 이름 | `alerts.name` | 1~40자 |

### 7.2 프리셋(PRESET)
| UI 요소 | trigger_spec 경로 | 검증 |
|---------|------------------|------|
| (갤러리 카드 선택) | `alerts.trigger_type='PRESET'`, `spec.preset_key` | 카탈로그 존재 |
| 파라미터 폼 필드 | `spec.params.*` | 카탈로그 param_schema |
| (공통 footer) | §7.1의 발화방식/유효기간/시간/이름과 동일 | 동일 |

---

## 8. 실제 JSON 스니펫

### 8.1 조립형 — "일봉 기준, RSI가 3일 연속 70 이상"
```json
{
  "trigger_type": "COMPOSABLE",
  "spec_version": 1,
  "timeframe": "D1",
  "notify_mode": "EDGE_REARM",
  "market_hours_only": true,
  "trigger_spec": {
    "conditions": [
      {
        "left": { "indicator": "rsi", "indicator_params": { "period": 14 }, "transform": { "type": "identity" } },
        "op": "gte",
        "right": { "const": 70 },
        "modifier": { "streak": 3 }
      }
    ]
  }
}
```

### 8.2 조립형 — "외국인 순매수 3일 연속 증가" (연속 증가 = delta>0 + streak)
```json
{
  "trigger_type": "COMPOSABLE",
  "timeframe": "D1",
  "trigger_spec": {
    "conditions": [
      {
        "left": { "indicator": "foreign_net_buy", "transform": { "type": "delta", "n": 1 } },
        "op": "gt",
        "right": { "const": 0 },
        "modifier": { "streak": 3 }
      }
    ]
  }
}
```

### 8.3 프리셋 — "박스권 20일 상단 돌파"
```json
{
  "trigger_type": "PRESET",
  "timeframe": "D1",
  "notify_mode": "EDGE_REARM",
  "trigger_spec": {
    "preset_key": "box_breakout",
    "params": { "window_days": 20, "direction": "up" }
  }
}
```

### 8.4 조립형 — 두 지표 비교 + AND (예: "5일선 > 20일선 AND 거래량 > 20일평균")
```json
{
  "trigger_type": "COMPOSABLE",
  "timeframe": "D1",
  "trigger_spec": {
    "conditions": [
      {
        "left":  { "indicator": "sma", "indicator_params": { "period": 5 },  "transform": { "type": "identity" } },
        "op": "gt",
        "right": { "indicator": "sma", "indicator_params": { "period": 20 }, "transform": { "type": "identity" } },
        "modifier": null
      },
      {
        "left":  { "indicator": "volume", "transform": { "type": "identity" } },
        "op": "gt",
        "right": { "indicator": "volume", "transform": { "type": "window", "fn": "avg", "n": 20 } },
        "modifier": null
      }
    ]
  }
}
```

---

## 9. 검증 규칙

저장 전 **앱 계층에서 반드시 통과**해야 하는 규칙. JSON은 DB가 무결성을 보장하지 않으므로 이 관문이 사실상의 계약이다.

### 9.1 공통(봉투)
| 필드 | 규칙 |
|------|------|
| symbol | 존재하는 종목. user-scope 조건 포함 시 보유 종목이어야 함 |
| timeframe | enum 값 |
| notify_mode | enum. `COOLDOWN`이면 `cooldown_min >= 1` 필수 |
| expires_at | null 또는 현재 이후 |
| name | 1~40자, 공백만은 불가 |

### 9.2 조립형 조건
| 규칙 |
|------|
| `conditions` 최소 1개 |
| 각 `left.indicator`가 카탈로그에 존재 |
| `left.transform.type`이 해당 지표의 `allowed_transforms`에 포함 |
| `op`가 해당 지표의 `allowed_operators`에 포함 |
| `right.const`는 number(지표의 unit 범위 검토), `right`가 Operand면 동일 규칙 재귀 적용 |
| `crosses_*` 연산자는 `right`가 Operand여야 함(상수 교차 불가) |
| `modifier.streak >= 1` / `modifier.persist_min >= 1` |
| user-scope 지표와 market-scope 지표 혼용 시 정책 확인(초기: 허용) |

### 9.3 프리셋
| 규칙 |
|------|
| `preset_key`가 카탈로그에 존재 |
| `params`가 해당 프리셋 `param_schema`를 만족(필수·타입·범위) |

---

## 10. 화면 상태 전수 (State Matrix)

와이어플로우는 해피패스만 시각화한다. 아래는 화면별로 구현해야 할 상태 전수.

| 화면 | 상태 |
|------|------|
| 알림 목록 | default / **빈 목록(온보딩)** / 로딩 / 시세지연 배너 / 항목 상태(armed·fired·paused·expired) |
| 종목 선택 | default / 검색 결과 없음 / user-scope인데 **보유 종목 없음** |
| 트리거 갤러리 | default / 프리셋 로딩 |
| 프리셋 폼 | default / **필수 파라미터 미입력(인라인 에러)** / 저장 버튼 비활성 |
| 조립형 빌더 | default / **기준값 미입력·조건 0개(인라인 에러)** / 저장 버튼 비활성 / 실시간 프리뷰 로딩 |
| 공통 설정 | default / **저장 중** / **저장 실패·재시도** / 검증 실패 |
| 앱푸시 권한 | **미허용 배너 + 설정 유도/재요청** |
| 발화 후 | 푸시 도착 → 상세 → **재무장 / 종료** |
| 만료·중지 | 만료 표시 / **재활성화 복귀** |
| 중복·충돌 | 같은 종목+동일 조건 존재 시 경고 |

> 뒤로/취소/수정 이동은 각 화면 네비바의 `‹`로 일관 제공(별도 흐름선 없음).

---

## 11. 미결 / 향후 확장 (YAGNI 경계)

초기 범위에서 **의도적으로 제외**한 것들. 필요 시 확장.

- **OR / 불리언 트리**: 초기엔 AND 평탄 리스트만. OR는 "알림 2개"로 대체 가능. 트리 UI는 일반 사용자에게 과함.
- **혼합 timeframe**: 한 알림은 단일 timeframe(옵션 A). "일봉 RSI + 분봉 거래량" 혼합은 미지원 → 필요 시 프리셋/확장.
- **L5 상태머신의 조립형화**: 박스권 등 상태 전이는 네이티브 프리셋으로만. 조립형 빌더에 넣지 않음.
- **알림 공유/템플릿 마켓**, **백테스트(과거 데이터로 조건 검증)**: 후속 과제.

---

## 12. 다음 단계
1. 본 스펙 사용자 리뷰 → 확정
2. 구현 계획(writing-plans) 작성: 카탈로그 정의 → 스키마/마이그레이션 → 검증 계층 → 조립형 평가기 → 프리셋 평가기 → UI 빌더 → 발화/재무장 → 상태 화면
3. 데이터 수급 설계(별도 스펙)
