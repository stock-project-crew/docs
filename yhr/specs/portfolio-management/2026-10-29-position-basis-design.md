# 평단 · 실현손익 생성기 설계 — `position_basis` 1.5단계 · `realized_pnl_line` 1.6단계

[포트폴리오 스펙](2026-07-28-portfolio-management-spec.md) §3.6의 1.5 · 1.6단계를 백엔드에 구현하는 설계다. 스펙이 정한 것(무엇을 만드나)은 다시 적지 않고, 스펙이 열어 둔 것(언제 · 어떻게 만드나)을 정한다. 스펙과 이 문서가 다르면 스펙이 맞다. 스펙 문구를 해석한 곳은 [§10](#10-스펙-반영-후보)에 모았다.

| 근거 | 위치 |
|---|---|
| 파이프라인 · 평단 · 등급 · 표시 정책 | 스펙 §2.8 · §3.6 · §4.3 · §4.4 · §4.5 · §5.1 · §8.2 · §8.4 · §9.1 |
| `cln_trade` · `cln_trade_coverage` · `corporate_action` · `ca_coverage` 계약 | [데이터 요구사항](../data-requirements.md) §4.3 · §6.3 · §6.7 · §6.9 |
| 실제 DDL | dataeng `reverse_etl/ddl.py` |
| 1단계 생성기(잡 회차 · 잠금 · `snapshot_run`) | [보유 스냅샷 생성기 설계](2026-10-15-position-line-builder-design.md) |

## 1. 범위

**만든다**

- 확정된 날마다 계좌 × 종목의 평단 · 등급 상태를 다시 계산해 `position_basis`에 쓰는 잡.
- 같은 계산에서 매도 체결마다 실현손익을 `realized_pnl_line`에 쓰는 일.
- 실현손익 응답의 체결 노드에 추정 사유와 체결 이력 시작일을 싣는 일, `CA_UNKNOWN` notice.
- 프론트 실현손익 화면의 배지 설명을 사유별 문구로 바꾸는 일.

**만들지 않는다**

- 종목 상세 API(`GET /portfolio/instruments/{id}`, 스펙 §8.5)와 그 화면. 지금 백엔드와 프론트에 없고, `basis` 블록만이 아니라 보유 · 계좌별 · 체결 · 기업행위를 모두 새로 만드는 일이다. `position_basis`는 그 API가 읽을 수 있는 모양으로 둔다.
- 체결 이력 구간 중간의 미설명 수량 변동 대조(스펙 §4.4 마지막 문단). 기준일별 보유수량을 대조할 원천이 확정 라인뿐이고, 라인은 생성기를 켠 날부터만 있다.
- 해외(USD) 체결의 실제 판정. 데이터가 국내 체결만 수집한다(§9). 환율 계산 경로는 만들고 테스트로 고정한다(§5.5).
- 단주 대금의 실현손익. 무상증자로 생긴 소수 주식을 현금으로 받는 일은 체결로 오지 않는다(§5.2).

## 2. 구성

```
SnapshotJobs.tick()  (PT1M, 모든 복제본)
  1 자격증명 채우기   CredentialFiller
  2 실행 반영         RunProcessor
  3 날짜 확정         Finalizer
  4 동기화 닫기       SyncCloser
  5 평단 · 손익 계산  BasisBuilder        ← 이 설계
```

| 구성 요소 | 패키지 | 하는 일 |
|---|---|---|
| `BasisBuilder` | `portfolio.basis` | 처리할 날짜 · 계좌를 고르고, 입력을 읽고, 계좌마다 트랜잭션 하나로 쓴다 |
| `BasisCalculator` | `portfolio.basis` | 계좌 × 종목 하나의 입력으로 `position_basis` 한 행과 매도 행들을 낸다. DB를 모른다 |
| `BasisMapper` · `BasisWriteMapper` | `portfolio.basis` | 읽기 · 쓰기 |

다섯 번째 단계는 같은 회차에서 앞 단계가 확정한 날을 바로 처리한다. `SnapshotJobs`가 있을 때(`portfolio.snapshot.runtime.enabled`) 다섯 번째 단계만 따로 `portfolio.basis.enabled`로 켜고 끈다(§8). 한 단계의 실패는 다른 단계를 막지 않는다(기존 `stage()`).

## 3. 입력과 새 표

### 3.1 읽는 표

| 표 | 쓰는 컬럼 | 비고 |
|---|---|---|
| `position_line` | 확정 라인(`is_final`)의 `quantity` · `cost_amount_local` · `is_carried_forward` | 잔고 수량 L과 시드 평단의 원천 |
| `snapshot_run` | `as_of` | 날짜 확정 신호 |
| `data.cln_trade` | 전부 | `account_ref`로 `account`와 잇는다 |
| `data.cln_trade_coverage` | `covered_from` · `covered_to` · `is_definitive` | 계좌 단위 |
| `data.corporate_action` | `type` · `ratio` · `ex_date` | ratio는 행위 후 ÷ 행위 전 주식 수 |
| `data.ca_coverage` | `covered_from` · `covered_to` · `state` | 종목 단위 |
| `data.fx_rate` | 일별 환율 | USD 경로에서만 |
| `instrument` | `currency` | |

### 3.2 로컬 · 테스트 미러 `V12__trade_ca_mirror.sql` (`db/external`)

`data.cln_trade` · `data.cln_trade_coverage` · `data.corporate_action` · `data.ca_coverage`를 dataeng `reverse_etl/ddl.py`의 DDL 그대로 옮긴다. 운영 프로필은 `db/external`을 적용하지 않는다(V7과 같다). 데이터 요구사항 §6.3은 `ca_coverage.instrument_id`를 null 허용으로 적었지만 실제 DDL은 NOT NULL이며, 미러는 실제 DDL을 따른다.

### 3.3 `V13__position_basis.sql` (`db/migration`, 백엔드 소유)

**`position_basis`** — 스펙 §5.1 컬럼에 하나를 더한다.

```sql
CREATE TABLE position_basis (
    account_id       uuid           NOT NULL REFERENCES account (account_id),
    instrument_id    uuid           NOT NULL,
    evaluated_as_of  date           NOT NULL,
    evaluated_qty    numeric(20, 8) NOT NULL CHECK (evaluated_qty > 0),
    avg_cost_local   numeric(20, 4),
    avg_cost_krw     numeric(20, 4),
    coverage_start_at date,
    opening_qty      numeric(20, 8) NOT NULL,
    seed_avg_price   numeric(20, 4),
    grade            text           NOT NULL CHECK (grade IN
                       ('VERIFIED', 'SEEDED', 'UNAVAILABLE', 'CONFLICT')),
    seed_permanent   boolean        NOT NULL,
    ca_unknown       boolean        NOT NULL,
    PRIMARY KEY (account_id, instrument_id),
    CHECK ((grade = 'SEEDED') = (seed_avg_price IS NOT NULL)),
    CHECK (NOT seed_permanent OR grade = 'SEEDED'),
    CHECK ((grade IN ('VERIFIED', 'SEEDED')) = (avg_cost_local IS NOT NULL AND avg_cost_krw IS NOT NULL))
);
```

- 수량이 0인 종목은 행이 없다. 청산 리셋(스펙 §4.3)은 행을 지우는 것이다.
- `avg_cost_*`는 `UNAVAILABLE` · `CONFLICT`에서 비운다. 계산할 수 없는 값을 0으로 채우지 않는다.
- `seed_permanent`는 스펙 §4.4의 영구 `SEEDED` 판정 결과다. 판정은 배치에서만 하고 조회 시 다시 하지 않는다.

**`basis_build`** — 처리 기록. 같은 날 · 같은 계좌를 두 번 처리하지 않게 하는 키이자 왜 건너뛰었는지 남기는 로그다.

```sql
CREATE TABLE basis_build (
    account_id  uuid        NOT NULL REFERENCES account (account_id),
    as_of       date        NOT NULL,
    outcome     text        NOT NULL CHECK (outcome IN ('BUILT', 'SKIPPED')),
    reason      text        CHECK (reason IN ('CARRIED', 'DISCONNECTED', 'TRADES_BEHIND')),
    built_at    timestamptz NOT NULL,
    PRIMARY KEY (account_id, as_of),
    CHECK ((outcome = 'SKIPPED') = (reason IS NOT NULL))
);
```

**`realized_pnl_line` 변경**

| 변경 | 내용 | 이유 |
|---|---|---|
| `seed_reason text` 추가 | `LATE_COVERAGE` · `NOT_TRADED`. `grade = 'SEEDED'`일 때만 값이 있다. 계산기가 쓰는 `SEEDED` 행은 늘 채우고, CHECK는 이 마이그레이션 전에 있던 `SEEDED` 행을 위해 비어 있는 것을 허용한다 | 배지 설명이 두 원인 중 하나를 말한다(스펙 §4.5). 매도 시점 값이라 청산 때 지워지는 `position_basis`에 둘 수 없다 |
| `coverage_start_at date` 추가 | `LATE_COVERAGE`일 때 필수 | 배지 설명의 "확보 구간이면 시작일" |
| `evaluated_as_of date NOT NULL` 추가 | 이 행을 마지막으로 계산한 판정일 | 산출 시점을 남긴다 |
| `position_closed boolean NOT NULL` 추가 | 이 매도가 속한 포지션이 청산됐는지. 한 번 참이 되면 바꾸지 않는다 | 다시 계산할 때 덮어쓸 행을 가린다(§5.6). `CONFLICT`면 다시 계산해도 구간을 알 수 없어 행에 남긴다 |
| `ca_unknown boolean NOT NULL` 추가 | 그 매도의 포지션 구간이 기업행위 확인 범위 밖에 걸쳤는지 | 판 종목의 `position_basis`는 지워지므로 `CA_UNKNOWN` notice는 행에서 읽는다 |
| `cost_basis_local` · `cost_basis_krw` · `realized_pnl_local` · `realized_pnl_krw` null 허용 | `grade IN ('VERIFIED','SEEDED')`이면 넷 다 필수인 CHECK | `CONFLICT` · `UNAVAILABLE`은 원가를 계산할 수 없다(스펙 §4.4 "미제공"). 이 행은 `미포함 계좌 N개`를 세는 데 쓰인다 |
| `grade` 컬럼 주석 | "열린 포지션의 매도는 다시 계산할 때 금액과 함께 갱신하고, 청산된 포지션의 매도와 등급 강등 전 행은 고정한다" | §5.6 |

이미 행이 있는 DB(README 절차로 샘플을 넣은 로컬 DB 등)에서도 마이그레이션이 돌도록, NOT NULL 컬럼은 기존 행을 채운 뒤 제약을 건다. 새로 쓰는 행에는 기본값을 두지 않는다.

| 컬럼 | 기존 행에 채우는 값 |
|---|---|
| `evaluated_as_of` | `sold_at`의 서울 날짜 |
| `position_closed` | 참. 이 표를 다시 계산하는 쪽이 없던 때의 행이라 고정한다 |
| `ca_unknown` | 거짓 |
| `seed_reason` · `coverage_start_at` | 비움. 원인을 알 수 없는 행에 원인을 지어내지 않는다. 화면은 §6.2 마지막 줄의 고정 문구를 쓴다 |

테스트 픽스처(`sample_portfolio.sql` 등)의 삽입문은 새 컬럼을 채우도록 고친다.

## 4. 잡 — `BasisBuilder`

### 4.1 처리할 날짜와 계좌

- 대상 날짜는 `snapshot_run`이 있는 날뿐이다. 스펙 §4.4 "등급은 파이프라인 1단계 직후 배치에서만 판정"을 따른다.
- 대상 계좌는 그날 확정 라인이 있는 계좌다.
- 계좌마다 `basis_build`의 마지막 날보다 뒤의 확정일을 이른 순서로 처리한다. **뒤로 가지 않는다.** 옛 날짜를 나중에 처리하면 최신 판정이 옛 값으로 덮인다.
- `basis_build`가 하나도 없는 계좌는 그 계좌 `cln_trade_coverage.covered_to` 이하의 가장 최근 확정일부터 시작한다. 그런 날이 없거나 커버리지 행이 없으면 가장 최근 확정일부터다. 날마다 전량 재계산이라 시작일의 결과는 과거를 다 돌린 것과 같고, 다른 것은 `CONFLICT` 강등을 세는 연속 판정뿐이다. 가장 최근 확정일로만 시작하면 체결이 늘 하루 늦게 들어오는 계좌는 매 회차 `covered_to < D`로 기다리다 다음 확정일이 생기면 그날로 옮겨 가 시작하지 못한다.

### 4.2 계좌 하나의 처리

트랜잭션 하나로 한다.

1. 잠금 — 1단계와 같은 순서로 날짜 advisory lock(공유, `PositionWriteMapper`와 같은 키 공간) → `account FOR UPDATE`.
2. `basis_build(account, D)`가 있으면 끝낸다.
3. 건너뛰기 — `position_basis`와 `realized_pnl_line`은 그대로 둔다.

| 경우 | 기록 | 이유 |
|---|---|---|
| D 라인이 이월(`is_carried_forward`) | `SKIPPED CARRIED` | 잔고가 D 값이 아니라 체결과 대조할 수 없다 |
| 연동 해제 계좌 | `SKIPPED DISCONNECTED` | 현재 상태를 더 만들지 않는다. 과거 실현손익 행은 남는다 |
| `covered_to < D` | D+1이 확정될 때까지 기록 없이 매 회차 다시 본다. 그 뒤 `SKIPPED TRADES_BEHIND` | 체결이 같은 날 늦게 들어올 수 있다. 판정하면 거짓 `CONFLICT`가 남는다 |

4. 대상 종목 — 아래 셋의 합집합에서 `CASH`를 뺀다.
   - D 확정 라인의 종목
   - 체결 이력 구간에 체결이 있는 종목(그사이 청산한 종목 포함)
   - 지금 `position_basis`에 있는 종목
5. 종목마다 `BasisCalculator`로 계산한다(§5).
6. 쓰기 — 그 계좌의 `position_basis`를 지우고 다시 넣는다. `realized_pnl_line`은 §5.6대로 쓴다. `basis_build`에 `BUILT`를 남긴다.

`cln_trade_coverage` 행이 없는 계좌(IRP처럼 체결 조회가 막힌 계좌)는 건너뛰지 않는다. 모든 종목을 `UNAVAILABLE`로 판정하고 `BUILT`를 남긴다. 이력이 앞으로도 없을 수 있어 건너뛰면 영원히 판정되지 않는다.

### 4.3 실패

- 계좌 하나가 실패하면 그 트랜잭션만 되돌리고 다음 계좌로 간다. 기록이 없으니 다음 회차에 다시 시도한다.
- 계산 결과가 불변식을 어기면 예외로 그 계좌를 실패시키고 로그를 남긴다. 접은 끝 수량 ≠ L, `VERIFIED` · `SEEDED` 구간에서 수량이 음수 같은 경우다. 로그에 계좌번호를 남기지 않는다(`account_id`만).
- 앞 날짜가 계속 실패하면 그 계좌는 다음 날짜로 넘어가지 않는다. 뒤로 가지 않으므로(§4.1) 실패한 날을 넘기면 그날은 다시 처리되지 않는다. `SKIPPED`로 기록한 날은 처리가 끝난 날이라 넘어간다.

### 4.4 멱등성과 동시성

- `basis_build`의 PK가 처리 단위의 멱등 키다. 여러 복제본이 같은 계좌 · 날짜를 집으면 `FOR UPDATE`에서 하나가 기다렸다가 기록을 보고 끝낸다.
- `position_basis`는 통째로 바꾸고 `realized_pnl_line`은 `trade_id`로 upsert하므로, 같은 입력을 두 번 처리해도 결과가 같다.
- 1단계는 확정 라인을 바꾸지 않으므로(생성기 설계 §2) 읽는 동안 L이 바뀌지 않는다. 날짜 공유 잠금은 확정 단계와의 순서를 1단계 잠금 규칙에 맞추려는 것이다.

## 5. 계산 규칙 — `BasisCalculator`

계좌 × 종목 하나, 판정일 D.

### 5.1 입력

| 입력 | 범위 |
|---|---|
| 잔고 수량 L | D 확정 라인의 수량. 라인이 없으면 0 |
| 체결 | `trade_date`가 `covered_from` ~ D이고 수량이 0보다 큰 것. `executed_at` 순, 같으면 매수 먼저, 그다음 `trade_id` 순. 주문 시각이 같은 매수 · 매도에서 매도를 먼저 두면 거짓 `CONFLICT`가 난다. 스펙 §4.4의 `executed_at <= as_of`를 판정일 단위로 자른 것이다 |
| 기업행위 | `ex_date`가 [`covered_from`, D]인 행. `ex_date = covered_from`이면 시작 수량 S는 행위 전 단위다 |
| 체결 이력 구간 | `cln_trade_coverage` |
| 시드 평단의 출발 라인 | 그 계좌 × 종목의 확정 라인 중 이월이 아닌 것(§5.5) |

내부 계산은 소수 10자리로 하고, 계산기가 내는 값은 저장할 컬럼 자리수로 HALF_UP 반올림한다. 강등의 "같은 `opening_qty`"는 저장 자리수(8자리)로 반올림한 값끼리 비교한다.

### 5.2 앞으로 접기

수량과 **총 매입금액**(현지 통화 · 원화 둘)을 굴린다. 평단을 들고 가면 나눗셈 반올림이 쌓인다.

| 사건 | 수량 | 총 매입금액 |
|---|---|---|
| 매수 q @ p | + q | + q × p + 수수료 + 세금. 원화는 그 금액 × 매수일 환율 |
| 매도 q | − q | × (1 − q / 수량). 전량 매도면 남은 총액 전부가 원가 |
| `SPLIT` ratio | ⌊수량 × ratio⌋ | × ⌊수량 × ratio⌋ ÷ (수량 × ratio) |
| `MERGER` · `RIGHTS` | 그대로 | 그대로. `ca_unknown`만 세운다(§5.7) |

- 기업행위는 `ex_date` 그날의 체결보다 먼저 적용한다. `ex_date`는 권리락일이고, 그날 산 주식은 행위 뒤의 주식이다.
- `SPLIT`에서 내림을 하는 이유는 무상증자 비율이 1.5 같은 값이기 때문이다. 3주는 4.5주가 아니라 4주가 되고 0.5주는 단주 대금으로 받는다. 총액을 위처럼 줄이면 평단은 정확히 `평단 ÷ ratio`가 되어 스펙 §4.3 공식과 같다. 단주 대금은 체결로 오지 않아 실현손익에 잡지 않는다.

### 5.3 시작 수량 `opening_qty`

체결 이력 시작 시점에 이미 들고 있던 수량을 S, S에서 시작해 접은 끝 수량을 f(S)라 한다.

- 기업행위가 없으면 f(S) = S + Σ매수 − Σ매도라 S = L − Σ매수 + Σ매도이며, 스펙 §4.4 공식 그대로다. 좌변은 잔고 L이다.
- 내림이 끼면 식을 거꾸로 풀 수 없다. **f(S) = L이 되는 가장 작은 정수 S ≥ 0**을 찾는다. f는 S에 대해 줄지 않으므로 [0, L + Σ매도] 이분 탐색으로 정해진다. 지금 받는 `SPLIT` ratio는 1 이상이라 답은 이 범위 안에 있다.
  - 3주 매수 → 1.5배 무상증자 → 잔고 4주에서 공식을 그대로 쓰면 −0.33이 나와 거짓 `CONFLICT`가 된다. 탐색은 S = 0을 찾는다.
- 찾은 S에서 접는 도중 수량이 0 아래로 내려가면 S가 없는 것으로 본다(§5.4의 3번).
- 내림 때문에 f(S) < L < f(S + 1)이 되어 L에 닿는 S가 없을 수도 있다. 예: 3주 매수 → 1.5배 → L = 5이면 f(0) = 4, f(1) = 6이다. 증권사의 단주 처리가 내림과 다를 때 생긴다. 이것도 S가 없는 것으로 본다(§5.4의 3번).

### 5.4 등급 판정

위에서부터 처음 맞는 줄을 쓴다.

| # | 조건 | 등급 | `opening_qty` |
|---|---|---|---|
| 1 | 종목 통화가 KRW가 아님 | `UNAVAILABLE` — 체결 이력이 이 시장을 덮지 않는다 | L |
| 2 | 계좌의 `cln_trade_coverage` 행이 없음 | `UNAVAILABLE` | L |
| 3 | f(S) = L인 S가 없거나, 접는 도중 수량이 음수 | `CONFLICT` | 아래 셋 중 가장 작은 값. 늘 음수다 |
| 4 | S = 0 | `VERIFIED` | 0 |
| 5 | S > 0 | 첫 구간은 시드 평단이 있으면 `SEEDED`(`seed_permanent = is_definitive`), 없으면 `UNAVAILABLE` | S |

3번의 `opening_qty` 후보:
- L − f(0)
- 0에서 접을 때의 최저 수량
- L − f(S⁺). S⁺는 f(S⁺) > L인 가장 작은 S다. L에 닿지 못하는 경우에만 쓴다.

각 후보는 그 값이 생긴 시점까지 적용된 `SPLIT` ratio의 곱으로 나눠 시작 시점 단위로 되돌린다. L − f(·)는 D 시점 값이라 구간 안 모든 ratio의 곱으로, 최저 수량은 그 지점까지의 ratio 곱으로 나눈다. 앞의 예(3주 매수 → 1.5배, L = 5)에서는 (5 − 6) ÷ 1.5 = −0.66666667이다.

1 · 2 · 3번은 종목 전체의 판정이라 모든 구간에 같은 등급이 붙는다. 4 · 5번은 첫 구간의 등급이고, 이후 구간은 `VERIFIED`다(§5.5).

**강등** — 직전 `position_basis` 행이 `CONFLICT`이거나 강등된 `UNAVAILABLE`(`opening_qty < 0`인 `UNAVAILABLE`)이고, 이번 판정이 같은 `opening_qty`의 `CONFLICT`면 `UNAVAILABLE`로 둔다. 값이 바뀌면 `CONFLICT`부터 다시 센다. "직전"은 그 계좌의 직전 `BUILT` 판정이다. 사이에 `SKIPPED`인 날이 있어도 연속으로 센다. 건너뛴 날은 판정이 없었던 날이기 때문이다. 체결이 늦게 와서 생긴 일시 모순은 하루 뒤 체결이 오면 시작 수량이 바뀌므로, 같은 값이 두 번 이어진 것을 구조적 원인으로 본다. L = 0인 `CONFLICT`는 `position_basis` 행이 없어 강등하지 않는다. 그 매도 행은 합계에서 빠진 채 `미포함 계좌`에 남는다.

### 5.5 포지션 구간과 매도 금액

S에서 접으면서 수량이 0이 되는 지점마다 포지션을 끊는다(청산 리셋).

- 첫 구간의 등급은 §5.4를 따른다. `SEEDED`면 S × 시드 평단으로 총액을 시작한다. 이후 구간은 `VERIFIED`다(스펙 §4.3 "재매수는 새 포지션으로 `VERIFIED`").
- `position_basis.grade`는 **지금 열린 구간**의 등급이다. 첫 구간이 청산됐으면 S > 0이어도 `VERIFIED`이고 `seed_avg_price`는 비운다.
- 시드 평단은 체결 이력 안의 잔고 라인에서 체결을 거꾸로 되돌려 구한다. 체결 데이터가 없는 구간의 잔고는 쓰지 않는다. 그 구간에 수량을 바꾸지 않는 매매(예: 5주 매도 후 5주 매수)가 있었으면 평단만 바뀌어 있어, 수량이 맞아도 우연히 맞은 것인지 가릴 수 없기 때문이다.
  1. **출발 라인** — 날짜가 `covered_from` 이상이고 첫 구간이 청산되기 전(열려 있으면 D까지)이며 이월이 아닌 확정 라인 중 가장 이른 것. 그 라인 수량이 S에서 접은 그날 끝 수량과 다르면 건너뛰고 다음 라인을 본다. 없으면 시드가 없다(§5.4의 5번 `UNAVAILABLE`).
  2. **되돌리기** — 라인의 `cost_amount_local`(그날 체결 뒤의 총 매입금액)에서 출발해, `covered_from` ~ 라인 날짜의 사건을 늦은 것부터 거꾸로 되돌린다. 수량은 앞으로 접을 때의 값을 쓴다.

     | 거꾸로 만난 사건 | 총 매입금액 |
     |---|---|
     | 매수 q @ p | − q × p. 수수료 · 세금은 빼지 않는다 |
     | 매도 q | × (매도 전 수량 ÷ 매도 후 수량). 매도는 평단을 바꾸지 않는다 |
     | `SPLIT` ratio | × (행위 전 수량 × ratio) ÷ ⌊행위 전 수량 × ratio⌋. §5.2의 거꾸로다 |
     | `MERGER` · `RIGHTS` | 그대로 |

  3. 이력 시작 시점에 이른 총액 ÷ S가 시드 평단이다. `ex_date = covered_from`인 행위는 S가 행위 전 단위이므로 한 번만 되돌린다.
- 되돌리기는 KIS 잔고 평단이 수수료 · 세금을 넣지 않은 체결가의 이동평균이고, 매도로 바뀌지 않으며, `SPLIT` 뒤 총액을 위 비율로 맞춘다고 가정한다. 이 중 매수 쪽만 실측으로 확인했다(§9). 가정이 맞으면 시드 평단은 이력 시작 시점의 KIS 평단과 같고, 그래도 원천이 증권사 평단이라 등급은 `SEEDED`다(스펙 §4.3).
- 원화 시드 총액은 KRW 종목에서 현지 통화 총액과 같다.

매도 한 건:

```
cost_basis_local   = 5.2의 매도 원가
sell_amount_local  = q × p
fee_tax            = 수수료 + 세금
realized_pnl_local = sell_amount_local − cost_basis_local − fee_tax
sell_amount_krw    = round(sell_amount_local × 매도일 환율, 0)
cost_basis_krw     = round(원화 총 매입금액에서 같은 비율로 뺀 값, 0)
realized_pnl_krw   = sell_amount_krw − cost_basis_krw − round(fee_tax × 매도일 환율, 0)
```

환율은 `fx_rate`에서 그 날짜 이하 가장 최근 값이다. KRW는 1이다. USD 경로는 §5.4의 1번 때문에 운영에서 타지 않지만, 해외 체결이 들어오면 1번 조건만 바꾸면 되게 계산기 테스트로 고정한다.

`position_basis`의 `avg_cost_local` · `avg_cost_krw`는 열린 구간의 총 매입금액 ÷ L이다.

### 5.6 실현손익 행 쓰기

`realized_pnl_line`은 산출 시점 값이다. 스펙 §3.6 "재계산 범위에 드는 행만 갱신"과 §4.3 "청산 리셋이나 등급 강등 이후에도 과거 행을 소급 수정하지 않는다"를 함께 따르도록, 재계산 범위인 열린 포지션의 행만 갱신하고 범위를 벗어난 행은 고정한다(§10의 1번).

| 상황 | 동작 |
|---|---|
| 기존 행이 `position_closed` | 건드리지 않는다 |
| 기존 행이 닫히지 않았는데 이번 계산에서 청산된 구간에 듦 | 이번 계산값으로 덮어쓰고 `position_closed = true`로 바꾼다. 직전 판정까지 재계산 범위였으므로 갱신하고, 이 판정부터 고정한다 |
| 청산된 구간의 매도, 행 없음 | 그 구간의 계산값으로 넣는다. `position_closed = true` |
| 열린 구간의 매도 | 금액 · 등급 · 사유 · `ca_unknown` · `evaluated_as_of`를 함께 덮어쓴다 |
| 종목 전체 판정이 `CONFLICT` · `UNAVAILABLE`(§5.4의 1~3번) | 구간을 나눌 수 없다. 닫히지 않은 기존 행은 그 등급으로 덮어쓰고(원가 · 손익 null), 행이 없는 매도는 그 등급으로 넣는다 |
| 이번 판정이 강등 | 기존 행은 그대로 두고 행이 없는 매도만 `UNAVAILABLE`로 넣는다 |

- 금액과 등급은 늘 함께 움직인다. 한쪽만 바꾸면 "확인됨" 배지가 추정 금액에 붙는 경우가 생긴다.
- `seed_reason`은 `seed_permanent`면 `NOT_TRADED`, 아니면 `LATE_COVERAGE`다. `coverage_start_at`은 `covered_from`이다.
- 이번 계산에 나오지 않는 매도의 기존 행은 건드리지 않는다. 이력 시작일이 뒤로 밀려 구간 밖이 된 매도는 실제로 있었고 저장된 값은 그때 데이터로 맞게 계산한 것이라, 지우거나 합계에서 빼면 맞는 기록이 사라진다. 체결이 원천에서 지워져 생긴 행이면 데이터 쪽에서 고친다.
- 끝난 포지션에 체결이 늦게 오면 그 포지션의 매도는 고치지 않는다. 이 한계는 스펙 §3.6 "청산으로 리셋된 과거 구간은 재현하지 않는다"에서 온다.

### 5.7 `ca_unknown`

판정 구간은 포지션 구간의 시작일부터 D까지다. 매도 행이면 그 매도일까지다. 시작일은 첫 매수의 `trade_date`이고, 시드 구간이면 `covered_from`이다. 아래 중 하나면 참이다.

- 그 종목의 `ca_coverage` 행이 없다(지금 국내 ETF 전부와 국내 주식 일부).
- 행의 `state`가 `UNAVAILABLE`이다(지금 미국 전부).
- 판정 구간이 그 행의 `covered_from` ~ `covered_to`를 벗어난다. `ca_coverage`는 3년 창이라 3년 넘게 든 종목은 참이 된다.
- 판정 구간에 `MERGER` · `RIGHTS`가 있다.

출발 평단으로 쓰는 잔고 평단에는 시작일 이전의 기업행위가 이미 반영돼 있다고 보고, 시작일 이전 구간은 보지 않는다.

## 6. 응답과 화면

### 6.1 백엔드 — `GET /portfolio/realized-pnl`

- 체결 노드에 `seed_reason` · `coverage_start_at`을 더한다. 값이 없으면 싣지 않는다(`NON_NULL`).
- 종목 노드에는 더하지 않는다. 프론트가 체결 노드에서 판단한다.
- `CA_UNKNOWN` notice — 기간 안 매도 행 중 `ca_unknown`이 참인 행이 있으면 붙인다. `params`는 그 행들의 `instrument_id` 배열(스펙 §8.2), 문구는 "N개 종목은 기업행위 이력을 확인하지 못해 손익이 다를 수 있습니다". `AssemblyContext.caUnknownInstruments`를 채운다.
- 원가가 null인 행은 지금처럼 합계와 목록에서 빠지고 `EXCLUDED_ACCOUNTS`에만 센다. `RealizedPnlRow`의 원가 · 손익 필드가 null일 수 있다.
- 골든 응답 `golden/realized-pnl.json`을 백엔드 · 프론트 두 곳에서 같이 고친다.

### 6.2 프론트 — 실현손익 화면

- `RealizedPnlTrade`에 `seed_reason?` · `coverage_start_at?`.
- 체결 줄의 배지도 누르면 설명을 연다. 지금은 종목 줄 배지만 열린다.
- `SEEDED` 설명 문구:

| 경우 | 문구 |
|---|---|
| `NOT_TRADED` | 매매 없이 입고된 종목이라, 잔고 평단으로 취득원가를 추정했어요 |
| `LATE_COVERAGE` | 거래내역이 {M월 D일}부터 확보돼, 그 전에 산 수량은 잔고 평단으로 추정했어요. 더 이른 거래내역이 들어오면 바뀔 수 있어요 |
| 종목 노드, 체결들의 사유 · 시작일이 모두 같음 | 그 체결의 문구 |
| 종목 노드, 사유가 갈림 | 계좌마다 추정한 이유가 달라요. 펼쳐서 체결별로 확인하세요 |
| 필드가 없음 | 두 원인을 함께 말하는 지금 문구 |

- `NOT_TRADED`에는 "바뀔 수 있다"를 넣지 않는다(스펙 §4.4 "곧 해소될 수 있다는 뉘앙스를 뺀다").
- 마지막 줄은 필드를 싣지 않는 서버에 대한 대비다. `position_basis`가 있는 서버는 `SEEDED` 행에 늘 사유를 싣는다.

## 7. 테스트

### 7.1 계산기 단위 테스트 — `BasisCalculatorTest` (DB 없음)

값은 손으로 검산했다. 원화 종목이라 원화 값은 현지 통화 값을 반올림한 것이다.

| # | 입력 | 기대값 |
|---|---|---|
| 1 | 매수 10@1,000(수수료 15) · 매수 10@1,300(수수료 20) · 매도 5@1,500(수수료 10, 세금 15), L = 15 | `VERIFIED`. 총액 23,035, 매도 원가 5,758.75, 현지 손익 7,500 − 5,758.75 − 25 = 1,716.25. 원화 원가 5,759, 원화 손익 1,716. 남은 평단 17,276.25 ÷ 15 = 1,151.75 |
| 2 | 매수 10@100 → 2배 `SPLIT` → 매도 5@60, L = 15 | `VERIFIED`. 분할 후 20주 · 총액 1,000, 매도 원가 250, 손익 50 |
| 3 | 매수 3@1,000 → 1.5배 `SPLIT`, L = 4 | `VERIFIED`(공식 역산이면 −0.33). 총액 3,000 × 4 ÷ 4.5 = 2,666.6667, 평단 666.6667 |
| 4 | `covered_from` 3/2. 3/2 매수 5@1,300(수수료 10), 3/2 라인 15주 · 매입금액 18,500, 3/3 매도 6@1,400, L = 9, `is_definitive` 거짓 | `SEEDED`, S = 10, `LATE_COVERAGE`. 되돌리기 18,500 − 6,500 = 12,000, 시드 평단 1,200. 총액 12,000 + 6,510 = 18,510, 매도 원가 7,404, 손익 8,400 − 7,404 = 996. 남은 평단 11,106 ÷ 9 = 1,234 |
| 5 | 4와 같고 `is_definitive` 참 | `seed_permanent`, `NOT_TRADED` |
| 6 | 매수 10, L = 5 | `CONFLICT`, `opening_qty` −5 |
| 7 | 매도 10 → 매수 10, L = 0 | 양 끝은 0이지만 도중 −10이라 `CONFLICT`, `opening_qty` −10 |
| 8 | `covered_from` 3/2. 3/2 라인 10주 · 매입금액 12,000 → 3/3 매도 10@1,500 → 3/4 매수 5@1,600, L = 5 | 첫 매도 `SEEDED` · `position_closed`, 원가 12,000, 손익 3,000. `position_basis`는 `VERIFIED`, `opening_qty` 10, 평단 1,600, `seed_avg_price` 없음 |
| 9 | USD 매수 10@100(환율 1,300) · 매도 10@120(환율 1,350, 수수료 1) — 계산기의 시장 조건을 열고 | 현지 손익 1,200 − 1,000 − 1 = 199. 원화 매도 1,620,000, 원가 1,300,000, 비용 1,350, 손익 318,650. 조건을 닫으면 `UNAVAILABLE` |
| 10 | 매수 10 → `MERGER` → L = 10 | 수량 그대로, `VERIFIED`, `ca_unknown` 참 |
| 11 | `ca_coverage` 없음 / `UNAVAILABLE` / 시작일이 `covered_from` 앞 | 셋 다 `ca_unknown` 참. 구간 안이면 거짓 |
| 12 | 직전 `CONFLICT` −5 → 이번 −5 / 직전 강등 −5 → 이번 −5 / 직전 `CONFLICT` −5 → 이번 −3 | `UNAVAILABLE` / `UNAVAILABLE` 유지 / `CONFLICT` |
| 13 | 8과 같고 3/2 라인이 없음(라인은 D뿐) | 첫 매도 `UNAVAILABLE`(원가 null) · `position_closed`. `position_basis`는 `VERIFIED`, 평단 1,600 |
| 14 | `covered_from` 3/2. 3/2 매도 4@1,500, 3/2 라인 6주 · 매입금액 6,600, 3/3 매수 4@1,300, L = 10 | S = 10. 매도를 되돌려 6,600 × 10 ÷ 6 = 11,000, 시드 평단 1,100. 매도 원가 4,400, 손익 1,600. 남은 평단 (6,600 + 5,200) ÷ 10 = 1,180 |
| 15 | 14와 같고 3/2 라인이 8주 / 이월 라인 | 둘 다 3/2 라인을 건너뛰고 3/3 라인(10주 · 11,800)에서 되돌린다. 11,800 − 5,200 = 6,600, × 10 ÷ 6 = 11,000, 시드 평단 1,100 |
| 16 | 매수 3 → 1.5배 `SPLIT`, L = 5 | `CONFLICT`, `opening_qty` (5 − 6) ÷ 1.5 = −0.66666667 |
| 17 | `covered_from` 3/2, 그 전부터 보유. 3/3 2배 `SPLIT`, 3/3 라인 20주 · 매입금액 10,000, L = 20 | S = 10, `SEEDED`, 시드 평단 10,000 ÷ 10 = 1,000. `position_basis` 평단 500 |
| 18 | 17과 같고 `ex_date` = `covered_from` = 3/2, 3/2 라인 20주 · 10,000 | S = 10(행위 전 단위), 시드 평단 1,000. 행위는 한 번만 적용되어 끝 수량 20 |

### 7.2 통합 테스트 — 실제 Postgres

이 브랜치는 마이그레이션이 있어 전용 DB `portfolio_test_basis`에서 돌린다.

```
TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_basis?currentSchema=app,data' ./gradlew test --rerun-tasks
```

| 테스트 | 확인하는 것 |
|---|---|
| `BasisBuilderTest` | 처리 날짜 규칙(뒤로 가지 않음, 첫 실행은 최신 하루). 건너뛰기 셋과 `TRADES_BEHIND`가 D+1 확정 뒤 기록되는지. 이력 없는 계좌의 `UNAVAILABLE` `BUILT`. 같은 날 두 번 돌려도 결과가 같은지. §5.6의 덮어쓰기 · 고정 · 강등. 해제 계좌의 과거 행 유지 |
| `BasisConcurrencyTest` | 두 스레드가 같은 날 · 같은 계좌를 처리해도 `basis_build` 한 건, 행 한 벌인지(`SnapshotConcurrencyTest`와 같은 방식) |
| `SnapshotJobsTest` | 다섯 번째 단계가 돌고, 앞 단계 실패에 막히지 않는지 |
| `RealizedPnlApiTest` | 새 필드, `CA_UNKNOWN` notice, 원가 null 행이 합계 · 목록에서 빠지고 `EXCLUDED_ACCOUNTS`에 세이는지 |
| `SchemaContractTest` · `SchemaSmokeTest` | 새 표 · 컬럼 · CHECK |

- 픽스처는 1단계 테스트와 같은 방식이다. `test` 프로필, 고정 시계, 이 작업 전용 `BasisFixture`가 `data.*` 미러와 확정 라인 · `snapshot_run`을 직접 쓴다. `sample_portfolio`에 기대지 않는다.
- `AccountFixture` · `SnapshotFixture` · `sample_portfolio.sql`의 TRUNCATE 목록에 새 표를 더한다.
- 테스트 프로필은 `db/external`을 포함하므로 CI에서도 미러가 만들어진다.
- 마지막에 origin/main 위로 rebase하고 위 명령으로 전체 테스트를 다시 돌린다.

### 7.3 프론트

- jest로 배지 문구 선택 다섯 경우(§6.2 표)와 체결 배지 누름을 확인한다.
- 골든 응답 갱신 뒤 기존 실현손익 화면 테스트가 통과하는지 본다.

## 8. 설정과 켜기

- `portfolio.basis.enabled: ${BASIS_ENABLED:false}`. 참이면 `SnapshotJobs`가 다섯 번째 단계를 돌고, 거짓이면 그 단계만 건너뛴다. `SnapshotJobs`가 없으면(`portfolio.snapshot.runtime.enabled` 거짓) 의미가 없다.
- 기본값이 거짓이라 back-end를 main에 머지해 운영에 배포돼도 다섯 번째 단계는 돌지 않는다. 운영에서 켜기 전에 앱 DB 계정이 `data.cln_trade` · `data.cln_trade_coverage` · `data.corporate_action` · `data.ca_coverage`를 읽을 수 있는지 읽기 전용으로 확인한다. 켜는 것은 `k8s/deployment.yaml`에 `BASIS_ENABLED=true`를 넣는 배포다.
- 운영은 지금 `data.cln_trade` · `data.cln_trade_coverage`가 0행이다. 켜면 첫 실행은 모든 보유를 `UNAVAILABLE`로 판정하고, 실현손익 행은 생기지 않는다.

## 9. 데이터 쪽 의존

| 빠진 것 | 결과 |
|---|---|
| 액면분할 · 주식병합 미수집인데 국내 주식 `ca_coverage`는 `COVERED` | 그런 종목은 수량 · 평단이 틀린 채 `ca_unknown` 없이 `VERIFIED`가 된다. 백엔드가 감지할 수 없다. 데이터팀 확인 중 |
| `MERGER` 행이 합병하는 회사 종목에 합병당하는 회사 기준 비율로 옴 | 백엔드는 `MERGER`로 수량을 바꾸지 않고 `ca_unknown`만 세운다(§5.2) |
| 국내 ETF · 일부 국내 주식의 `ca_coverage` 행 없음 | 그 종목은 늘 `ca_unknown` |
| 해외 체결 미수집 | USD 종목은 늘 `UNAVAILABLE`(§5.4의 1번) |
| `is_definitive`가 참이 되려면 1회 백필이 필요 | 그 전까지 매매 없이 입고된 종목도 `LATE_COVERAGE`로 표시된다 |
| KIS 잔고에 무상증자 · 분할 신주가 잡히는 날이 확인되지 않음 | 계산은 `ex_date`에 수량을 바꾼다. 잔고가 그보다 늦게 늘면 그 사이 매일 `CONFLICT`가 나고 이틀째부터 `UNAVAILABLE`로 강등된다. 잔고가 늘어 맞으면 다음 판정이 정상으로 돌아오고 열린 포지션의 매도 행도 다시 계산된다(§5.6). 행위별 입고일을 받으면 그날 수량을 바꾸면 된다. 데이터팀 확인 중 |
| KIS 잔고 평단의 계산 방식이 일부만 확인됨 | 시드 평단 되돌리기(§5.5)의 가정 중 확인된 것은 위탁계좌에서 매수 수수료를 넣지 않고 매수 때 Σ체결금액 ÷ Σ수량이 된다는 것이다([KIS 가정 실측](../../verification/kis-portfolio-assumptions.md) §3). 매도 뒤 평단 불변, `SPLIT` 뒤 총액 유지, 퇴직연금 계좌의 같은 규칙은 확인하지 않았다. 다르면 `SEEDED` 평단이 틀린다 |
| 체결 없이 입고된 수량(같은 실측 §2-3) | 체결 이력 구간 안의 입고는 시작 수량 S에 흡수되고(§1의 미설명 변동 대조는 범위 밖), 시드 되돌리기는 입고 뒤 라인에서 출발한다. 그 종목의 시드 평단은 입고분이 섞인 값이다 |
| 수수료 · 세금이 빈 체결을 데이터가 버리고 이력 시작일을 다음 날로 옮김 | 시작일이 밀려 `VERIFIED`였던 열린 포지션이 `SEEDED`로 바뀔 수 있다. §5.6이 금액과 등급을 함께 바꾼다 |

## 10. 스펙 반영 후보

스펙 문장은 고치지 않고 아래처럼 읽었다. 스펙에 반영할지는 따로 정한다.

1. **실현손익 행 갱신 범위** — §3.6 "재계산 범위에 드는 행만 갱신"과 §4.3 · §9.1 "산출 시점 값이며 이후 갱신하지 않는다"를 "열린 포지션의 행은 금액과 등급을 함께 갱신하고, 청산된 포지션의 행과 강등 전 행은 고정한다"로 읽었다(§5.6).
2. **`position_basis.seed_permanent`** — §5.1 표에 없는 컬럼을 더한다. §4.4의 영구 `SEEDED` 판정을 배치에서 남길 자리가 없다.
3. **`realized_pnl_line` 컬럼** — `seed_reason` · `coverage_start_at` · `evaluated_as_of` · `position_closed` · `ca_unknown`을 더하고 원가 · 손익을 `VERIFIED` · `SEEDED`에서만 필수로 바꾼다(§3.3).
4. **응답 필드** — §8.4 체결 노드에 `seed_reason` · `coverage_start_at`을 더한다. §4.5 "배지 탭 시 두 원인 중 어느 쪽인지와 시작일"을 전달하려면 필요하다.
5. **`opening_qty` 계산** — §4.4 공식을 "f(S) = L인 가장 작은 정수 S"로 읽었다(§5.3). 기업행위가 없으면 공식과 같고, 무상증자 단주를 공식은 표현하지 못한다.
6. **도중 음수의 `CONFLICT`** — §4.4는 `opening_qty < 0`만 적었다. 양 끝은 맞는데 가진 것보다 많이 판 경우도 수량 모순으로 판정한다(§5.4의 3번).
7. **시드 평단의 출처** — §4.3은 "잔고 스냅샷의 평단"만 적었다. 체결 이력 안의 가장 이른 실제 수집 라인에서 체결을 거꾸로 되돌려 이력 시작 시점의 평단을 구하는 것으로 정했다(§5.5). 체결 데이터가 없는 구간의 잔고는 쓰지 않는다.
8. **강등의 "동일"** — §4.4 "다음 판정에서도 동일하게 재현"을 "연속한 두 판정의 `opening_qty`가 같음"으로 읽었다(§5.4).
9. **시장을 덮지 않는 체결 이력** — §4.4 "거래내역 미확보"를 계좌 단위 커버리지가 있어도 그 시장의 체결을 수집하지 않으면 미확보로 읽었다(§5.4의 1번).
10. **`MERGER` · `RIGHTS`** — §4.3은 기업행위를 `수량 × ratio`로 보정한다고 적었다. 이 둘은 받은 행의 의미가 보유 수량 보정과 맞지 않아 보정하지 않고 `ca_unknown`으로 알린다(§5.2).
11. **`ca_unknown` 판정 구간** — §4.4 "보유 기간"을 포지션 구간 시작일(시드 구간이면 이력 시작일)부터로 읽었다(§5.7).
12. **`basis_build`** — 스펙 §5.1 표 목록에 없는 백엔드 내부 표를 더한다(§3.3).
13. **배지 고정 문구** — §2.8의 고정 문구는 사유 필드가 없는 응답에서만 쓴다(§6.2).
