# 보유 스냅샷 생성기 설계 — `position_line` 1단계

[포트폴리오 스펙](2026-07-28-portfolio-management-spec.md) §3.6 1단계를 백엔드에 구현하는 설계다. 스펙이 정한 것(무엇을 만드나)은 다시 적지 않고, 스펙이 열어 둔 것(언제·어떻게 만드나)을 정한다. 스펙과 이 문서가 다르면 스펙이 맞다. 스펙 문구를 해석한 곳은 [§12](#12-스펙-반영-후보)에 모았다.

| 근거 | 위치 |
|---|---|
| 파이프라인 · 원화 환산 · 예수금 · 이월 · as-of · 검증 | 스펙 §3.6 · §5.2 · §5.3 · §5.4 · §7.2 · §7.3 · §7.4 · §9.1 |
| `collection_run` · `cln_balance` · `cln_deposit` · `fx_rate` 계약 | [데이터 요구사항](../data-requirements.md) §6.4 · §6.5 · §6.6 · §6.10 |
| `snapshot_run` | [알림 스펙](../buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md) §7.1 · §10.1 |
| 데이터 쪽 실제 구현과의 차이 | [계좌 파이프라인 대조](../../reviews/2026-10-15-portfolio-account-pipeline-gap.md) |

## 1. 범위

**만든다**

- `collection_run`의 계좌별 결과를 읽어 `position_line`을 쓰는 잡. EOD 일배치 행(`SCHEDULE`)과 수동 동기화 행(`USER`)을 같은 경로로 처리한다.
- 날짜를 확정하는 잡. 그 `as_of`의 대상 계좌가 모두 확정되면 `snapshot_run`에 한 행을 쓴다.
- EOD 행에 `credential_ref`를 채우는 잡.
- `collection_run` 결과에 따른 `account.link_state` 전이.
- `CollectionStatusPort`의 실제 구현(계좌별 뷰의 `last_collection`).
- 조회 시 검증 `accountsWithoutLine`의 판정 범위 조정(§6.1).
- 알림이 읽는 최신 확정 보유 스냅샷 날짜를 `snapshot_run`이 있는 날로 한정(§6.4).

**만들지 않는다**

- `position_basis` · `realized_pnl_line`(1.5 · 1.6단계).
- 수동 동기화 요청(`POST /sync` · `sync_run`)과 계좌 등록 · 해제 API. 이 생성기는 그 둘이 만든 `collection_run` 행과 `account` 행을 읽는다. 해제했던 계좌를 다시 연동하면 등록 API가 옛 `account` 행을 재사용한다(같은 `account_id`) — 생성기는 그 경우를 §6.1의 편입 규칙으로 다룬다.
- `/reauth`. `REAUTH_REQUIRED`에서 `CONNECTED`로 돌아가는 전이는 그쪽 몫이다.

## 2. 라인의 네 상태

(계좌, `as_of`)마다 라인 한 벌은 아래 넷 중 하나다. 한 벌은 늘 통째로 쓰고 지우므로 한 계좌 · 한 날짜 안에서 상태가 섞이지 않는다.

| 상태 | `is_final` | `is_carried_forward` | 만드는 곳 | 이후 |
|---|---|---|---|---|
| 없음 | — | — | — | 실행 처리나 확정이 채운다 |
| 잠정 실측 | `false` | `false` | `USER` `DONE` 실행 | 같은 날 다음 실행이 덮는다. 확정 때 그대로 확정으로 올린다 |
| 잠정 이월 | `false` | `true` | 같은 사용자의 다른 계좌가 그날 라인을 얻을 때(§5.6) | 같은 날 실행이 덮는다. 확정 때 직전 영업일 확정 라인으로 다시 이월한다 |
| 확정 | `true` | 둘 다 | `SCHEDULE` `DONE` 실행 · 확정 단계 | 바꾸지 않는다 |

잠정 이월이 있는 이유: 화면은 사용자의 가장 늦은 `as_of` 한 벌을 읽는다(`SnapshotCalendarMapper.latestAsOf`). 한 계좌만 새로고침해 그날 라인이 생기면 다른 계좌는 그날 라인이 없어 한 벌에서 빠진다 — 총자산이 그 계좌만큼 줄어 손실처럼 보인다(스펙 §7.3의 1). 다른 계좌의 직전 기준일 값을 그날로 복사해 두면 화면은 "새로고침한 계좌는 새 값, 나머지는 기준일 배지가 붙은 기존 값"이 된다.

## 3. 구성

```
SnapshotJobs (@Scheduled PT1M, 모든 복제본, 끄고 켤 수 있음)
 ├─ fillCredentials()  CredentialFiller  EOD 행에 credential_ref
 ├─ processRuns()      RunProcessor      끝난 collection_run 한 행씩 → 라인 · 연동 상태
 │                      ├─ LineCalculator  잔고 한 벌 → 라인 (순수)
 │                      └─ LineInvariants  쓰기 전 검사 (순수)
 └─ finalize()         Finalizer         날짜 순으로 확정 → 이월 · 승격 · snapshot_run
```

| 단위 | 하는 일 | 의존 |
|---|---|---|
| `SnapshotRuntimeConfig` | `portfolio.snapshot.runtime.enabled`가 `true`일 때만 `SnapshotJobs`를 등록한다. 기본 `false`. `@EnableScheduling`을 스스로 붙인다 — 지금은 `AlertRuntimeConfig`에만 있어 알림 런타임을 끄면 스케줄링이 꺼진다 | — |
| `SnapshotJobs` | 세 작업을 이 순서로 부른다 | 아래 셋 |
| `CredentialFiller` | §8 | `CollectionRunMapper` |
| `RunProcessor` | §5. 실행 한 행을 트랜잭션 하나로 처리한다 | `CollectionRunMapper` · `BalanceMapper` · `PositionWriteMapper` · `PositionBuildMapper` · `LineCalculator` · `LineInvariants` · `MarketDataMapper.calendar` |
| `LineCalculator` | §5.2~§5.5. DB를 모른다 | — |
| `LineInvariants` | §5.5. DB를 모른다 | — |
| `Finalizer` | §6 | `MarketDataMapper.calendar` · `PositionWriteMapper` · `PositionBuildMapper` · `SnapshotRunRecorder` |
| `CollectionRunStatusPort` | `CollectionStatusPort` 구현. `NoCollectionStatusPort`는 지운다(무조건 `@Component`라 둘이 되면 주입이 모호해진다) | `CollectionRunMapper` |

- 새 코드는 `com.stockproject.portfolio.snapshot` 아래에 둔다. 조회 계층(`query` · `view`)은 이 패키지를 모른다.
- 영업일 판정은 기존 `MarketDataMapper.calendar`(`dim_market_calendar`의 `is_trading_day` · `prev_trading_day` · `next_trading_day`)를 쓴다. `snapshot_run` 기록은 기존 `SnapshotRunRecorder`를 쓴다.
- 스케줄러 풀(`spring.task.scheduling.pool.size`)은 알림 잡 셋이 쓰는 3에서 4로 늘린다.
- 로그에는 `account_id` · `run_id`만 남긴다. `credential_ref` · `account_ref`를 담은 행 객체를 로그에 넘기지 않는다.

## 4. 입력과 새 표

### 4.1 읽는 표 (`data` 스키마, 데이터 소유)

| 표 | 쓰는 컬럼 | 쓰는 곳 |
|---|---|---|
| `collection_run` | 전부. 쓰기는 `credential_ref` 하나(§8) | 트리거 · 계좌별 뷰 |
| `cln_balance` | `account_ref` · `instrument_id` · `quantity` · `avg_price` · `market_value` · `currency` · `source_as_of` | 종목 행 |
| `cln_deposit` | `account_ref` · `currency` · `amount` · `source_as_of` | 예수금 행 · 잔고 시각 |
| `fx_rate` | `as_of` · `currency_pair` · `rate_type` · `rate` | 원화 환산. `USD/KRW` `BASE`만 쓴다 |
| `instrument` | `instrument_id` · `asset_class` · `currency` | 매칭 확인 · 예수금 의사종목 |
| `dim_market_calendar` | KR 행 | 영업일 · 직전 영업일 · 마감 |

SQL은 기존 매퍼처럼 스키마를 붙이지 않는다. 해석은 JDBC URL의 `currentSchema=app,data`가 한다.

### 4.2 로컬 · 테스트 미러 `V7__portfolio_collection_mirror.sql` (`db/external`)

`collection_run` · `cln_balance` · `cln_deposit` · `fx_rate`를 데이터 요구사항 §6.4 · §6.5 · §6.6 · §6.10의 컬럼 · 타입 · null 여부 · PK 그대로 `data.`에 만든다. `collection_run`의 `state` · `requested_by` CHECK도 같은 절의 값 목록을 쓴다. `instrument` · `dim_market_calendar`는 이미 미러가 있다(V2 · V5).

### 4.3 `V8__position_build.sql` (`db/migration`, 백엔드 소유)

실행을 처리한 기록과 확정 기록이다. 같은 실행을 두 번 처리하지 않게 하는 키이자, 라인이 왜 그렇게 됐는지를 남기는 로그다. 스펙의 표는 바꾸지 않는다.

```sql
CREATE TABLE position_build (
    build_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id      uuid UNIQUE,                 -- 확정 단계가 쓴 행은 null
    account_id  uuid        NOT NULL REFERENCES account (account_id),
    as_of       date        NOT NULL,
    outcome     text        NOT NULL CHECK (outcome IN ('BUILT', 'CARRIED', 'PROMOTED', 'SKIPPED')),
    reason      text        CHECK (reason IN (
                  'NO_BALANCE', 'STALE_BALANCE', 'UNMATCHED_INSTRUMENT', 'CASH_INSTRUMENT',
                  'FX_MISSING', 'CALENDAR_UNKNOWN',
                  'INVARIANT', 'OLDER_THAN_EXISTING', 'FINAL_EXISTS', 'NOT_TRADING_DAY',
                  'RUN_NOT_DONE', 'DISCONNECTED', 'DEADLINE')),
    attempts    int         NOT NULL DEFAULT 1,
    built_at    timestamptz NOT NULL,
    CHECK (outcome <> 'SKIPPED' OR reason IS NOT NULL),
    CHECK (run_id IS NOT NULL OR outcome IN ('CARRIED', 'PROMOTED'))
);

CREATE UNIQUE INDEX uq_position_build_finalize ON position_build (account_id, as_of)
    WHERE run_id IS NULL;
```

| `outcome` | `run_id` | 뜻 |
|---|---|---|
| `BUILT` | 있음 | 이 실행의 잔고로 라인을 썼다 |
| `SKIPPED` | 있음 | 라인을 바꾸지 않았다. 이유는 `reason` |
| `CARRIED` | null | 확정 단계가 직전 영업일 라인을 이월했다. 마감으로 확정했으면 `reason = 'DEADLINE'` |
| `PROMOTED` | null | 확정 단계가 잠정 실측을 확정으로 올렸다. 마감으로 확정했으면 `reason = 'DEADLINE'` |

**재시도할 수 있는 사유**: `NO_BALANCE` · `STALE_BALANCE` · `UNMATCHED_INSTRUMENT` · `CASH_INSTRUMENT` · `FX_MISSING` · `CALENDAR_UNKNOWN`. 데이터가 늦게 도착해 생길 수 있는 실패다. 이 사유로 남은 실행은 그 `as_of`가 확정되기 전까지 매 회차 다시 처리하고 `attempts`를 올린다. 나머지 사유는 최종이다.

확정 단계 행은 `ON CONFLICT (account_id, as_of) WHERE run_id IS NULL DO NOTHING`으로 넣는다. 행 수는 계좌 × 영업일 규모라 지우지 않는다.

## 5. 실행 처리 — `RunProcessor`

### 5.1 고르는 행과 처리 결과

**대상**: `account_ref`가 `account`에 있는 계좌의 실행 가운데 다음 둘 중 하나.

- `state`가 `DONE`(`silver_synced_at`이 채워짐) · `FAILED` · `REAUTH_REQUIRED`이고 `position_build`에 없다.
- `position_build`에 재시도할 수 있는 사유로 남아 있고, 그 `as_of`에 `snapshot_run`이 없다.

한 회차에 최대 `batch-size`행을 고른다. 처음 보는 실행을 재시도보다 먼저, 그 안에서는 `finished_at` 순이다 — 재시도로 남은 행이 많아도 새로 끝난 실행이 밀리지 않는다. `account`에 없는 `account_ref`의 행은 고르지 않는다 — 백엔드가 모르는 계좌다.

| 실행 결과 | `SCHEDULE` | `USER` |
|---|---|---|
| `DONE`, 빌드 성공 | 그 계좌 라인 교체, `is_final = true` → `BUILT` | 그 계좌 라인이 확정이면 `SKIPPED` `FINAL_EXISTS`. 아니면 교체, `is_final = false` → `BUILT` |
| `DONE`, 빌드 실패(§5.4) | `SKIPPED` + 사유. 라인을 건드리지 않는다 | 같다 |
| `FAILED` | `SKIPPED` `RUN_NOT_DONE` | 같다 |
| `REAUTH_REQUIRED` | `SKIPPED` `RUN_NOT_DONE` + 연동 상태 전이(§9) | 같다 |

`BUILT`이면 §5.6의 잠정 이월을 함께 쓴다.

**먼저 거르는 조건** (위 표보다 앞선다)

| 조건 | 결과 |
|---|---|
| 그 `as_of`에 `snapshot_run`이 있다(확정됨) | `SKIPPED` `FINAL_EXISTS`. 확정된 날은 바꾸지 않는다 |
| 캘린더에 그 `as_of`의 KR 행이 없다 | `SKIPPED` `CALENDAR_UNKNOWN`(재시도). 연동 상태 전이는 한다 |
| `as_of`가 KR 영업일이 아니다 | `SKIPPED` `NOT_TRADING_DAY`. 연동 상태 전이는 한다 |
| 계좌가 `DISCONNECTED` | `SKIPPED` `DISCONNECTED`. 라인도 연동 상태도 바꾸지 않는다 |
| 그 계좌의 그날 라인이 실측(이월 아님)이고 그 `source_as_of`가 이번 잔고 시각 `t`보다 늦다 | `SKIPPED` `OLDER_THAN_EXISTING`. 늦게 처리된 옛 실행이 새 값을 덮지 않게 한다. `SCHEDULE` 실행이 이렇게 끝나면 확정 단계가 그날의 더 새 잠정 실측을 승격한다 |

**이월은 여기서 확정하지 않는다.** 실행이 끝나는 순서는 날짜 순서를 보장하지 않으므로, 확정 이월은 날짜 순으로 도는 확정 단계(§6)가 한다.

`DONE`이면 계좌가 `DISCONNECTED`가 아닌 한 `account.last_synced_at`을 그 실행의 `finished_at`으로 올린다(더 늦을 때만). 위의 거르는 조건보다 먼저 한다 — 주말이나 확정된 날의 수동 동기화도 성공한 동기화다.

### 5.2 잔고 한 벌 고르기

- 잔고 시각 `t` = 그 계좌 `cln_deposit`의 `max(source_as_of)`. 그 실행의 `finished_at` 이하만 본다 — 뒤 실행이 쓴 값을 끌어오지 않는다.
- `source_as_of = t`인 `cln_deposit` 행 전부와 `cln_balance` 행 전부가 그 실행의 잔고다. 보유 종목이 없으면 `cln_balance` 행이 없을 수 있다.
- `t`를 예수금으로 정하는 이유: 예수금은 계좌마다 늘 한 행 이상 있다. 잔고 표 쪽으로 정하면 보유가 없는 계좌의 시각을 정할 수 없다.
- 이 고르기는 한 실행의 잔고와 예수금이 같은 `source_as_of`로 쓰인다는 전제에 기댄다. 지금 데이터 구현(`refine_cln_kis.py` `parse_balance`)은 두 표 모두 같은 응답의 `fetched_at`을 쓴다. 이 전제를 계약으로 굳혀 달라는 요청은 [대조 문서](../../reviews/2026-10-15-portfolio-account-pipeline-gap.md) §4의 1번에 있다. 전제가 깨져 잔고가 다른 시각에 쓰이면 그 실행의 보유 종목이 빠진 채로 만들어진다 — 이 생성기가 감지하지 못한다.
- 종목마다 최신 행을 고르지 않고 한 벌을 고르는 이유: 팔고 없어진 종목의 마지막 행이 계속 살아남는다.

### 5.3 종목 행과 예수금 행

**종목 행** (`cln_balance` 1행 → 라인 1행). 수량이 0인 행은 거른다.

| 컬럼 | 값 |
|---|---|
| `instrument_id` | `cln_balance.instrument_id` |
| `quantity` | `quantity` |
| `cost_amount_local` | `avg_price × quantity`, 소수 4자리 HALF_UP(스펙 §9.1 "잔고 평단 기준") |
| `market_value_local` | `market_value` |
| `fx_rate` · `fx_as_of` | `KRW`는 `1` · `as_of`. `USD`는 `fx_rate`에서 `currency_pair = 'USD/KRW'`, `rate_type = 'BASE'`, 날짜 ≤ `as_of`인 가장 최근 행의 `rate` · 그 날짜 |
| `cost_amount_krw` · `market_value_krw` | `local × fx_rate`를 정수로 HALF_UP. 반올림은 여기서 한 번뿐이다 |
| `source_as_of` | `t` |
| `is_carried_forward` | `false` |
| `is_final` | §5.1 표 |

통화는 `cln_balance.currency`를 쓴다. `fx_as_of < as_of`(폴백)는 실패가 아니다 — 기존 `FX_APPLIED` · `FX_STALE` notice가 알린다(스펙 §5.3).

**예수금 행** (`cln_deposit` 1행 → 라인 1행)

- 종목은 `instrument`에서 `asset_class = 'CASH' AND currency = cln_deposit.currency`인 행.
- `quantity` = `cost_amount_local` = `market_value_local` = `amount`. 환산은 종목 행과 같다. 원가와 평가금액이 같아야 하는 규칙(스펙 §5.2)을 계산이 그대로 만족한다.
- 금액이 0이어도 행을 만든다. 보유 종목도 예수금도 0인 계좌가 그날 라인 0개가 되지 않게 한다.

### 5.4 빌드 실패

하나라도 걸리면 라인을 쓰지 않고 그 사유를 `position_build.reason`에 남긴다.

| `reason` | 조건 | 재시도 |
|---|---|---|
| `NO_BALANCE` | `t`가 없다 — `DONE`인데 그 계좌의 예수금 행이 없다 | ✔ |
| `STALE_BALANCE` | `t`가 그 실행의 `requested_at`보다 이르다 — 이번 실행이 쓴 잔고가 아직 없다 | ✔ |
| `UNMATCHED_INSTRUMENT` | `cln_balance.instrument_id`가 null이거나 `instrument`에 없다 | ✔ |
| `CASH_INSTRUMENT` | 그 통화의 `CASH` 의사종목이 없거나 둘 이상이다 | ✔ |
| `FX_MISSING` | `KRW`가 아닌 행이 있는데 `as_of` 이하 환율 행이 하나도 없다 | ✔ |
| `INVARIANT` | §5.5 위반 | ✘ |

`STALE_BALANCE`가 막는 경우: 데이터 쪽 반영이 실패했는데 `silver_synced_at`이 찍히면(대조 문서 G5) 며칠 전 잔고가 이번 실행의 값처럼 이월 표시 없이 들어간다.

### 5.5 쓰기 전 검사 — `LineInvariants`

스펙 §9.1 팩트 정합성 가운데 라인 한 벌로 판정할 수 있는 것. 기존 `PositionLineInvariants`(조회 시 검사)와 같은 규칙을 쓰기 전에 한 번 더 건다.

- `(as_of, account_id, instrument_id)` 유일. 같은 종목이 두 행으로 오면 위반이다.
- `fx_rate` · `fx_as_of` 채워짐.
- `CASH` 행의 `cost_amount_krw = market_value_krw`.
- `is_carried_forward = true`이면 `source_as_of`의 KST 날짜 < `as_of`.

### 5.6 같은 사용자의 다른 계좌에 잠정 이월

`BUILT`로 계좌 X의 D 라인을 쓴 같은 트랜잭션에서, X의 소유자가 가진 다른 계좌 Y 가운데 다음을 모두 만족하는 계좌에 잠정 이월을 쓴다.

- `DISCONNECTED`가 아니다.
- 그 사용자의 직전 기준일에 라인이 있다.
- D에 라인이 없다.

그 사용자의 직전 기준일은 그 사용자의 계좌에 라인이 있는 날 가운데 D보다 이른 가장 늦은 날이다. 조회 시 검증(§6.1)과 화면의 전일 비교(`SnapshotCalendarMapper`)가 쓰는 기준과 같다. 그래서 D가 화면에 뜰 때 검증이 요구하는 계좌와 잠정 이월이 채운 계좌가 일치한다. 직전 영업일이 아직 확정되지 않아 라인이 없는 아침에도 그 전 기준일의 값으로 채워진다.

Y의 그 기준일 라인 한 벌을 D로 복사한다. `is_carried_forward = true`, `is_final = false`. 금액 · `fx_rate` · `fx_as_of` · `source_as_of`는 원본 그대로다(스펙 §7.3). 이 행은 Y의 그날 실행이 성공하면 덮이고, 확정 단계가 직전 영업일 확정 라인으로 다시 계산한다(§6.3). 해제했다 다시 연동한 계좌는 사용자의 직전 기준일에 라인이 없으므로 잠정 이월되지 않는다.

## 6. 확정 — `Finalizer`

### 6.1 대상 계좌

`as_of` D의 대상은 `DISCONNECTED`가 아닌 계좌 가운데 다음 하나를 만족하는 계좌다.

- D의 직전 영업일에 라인이 있다.
- D에 라인이 있다.
- D의 `SCHEDULE` 실행이 있다.

직전 영업일에 라인이 없는 계좌는 이월할 원본이 없다. 그날 실행이 성공해 라인이 생겨야 그날부터 편입된다 — 스펙 §5.4 "어느 날짜가 그 사용자에게 존재하는가는 계좌가 정한다". 해제했다 다시 연동한 계좌도 같다. 해제 기간에는 라인이 없으므로, 재연동 후 첫 수집이 실패해도 몇 달 전 보유가 오늘 값으로 이월되지 않는다. 자산 변화 화면에는 계좌 편입으로 잡힌다.

같은 이유로 조회 시 검증 `FactCheckMapper.accountsWithoutLine`을 "그 사용자의 직전 `as_of`에 라인이 있는데 D에 없는 계좌"로 좁힌다. 직전 `as_of`는 기존 `SnapshotCalendarMapper`가 쓰는 "그 사용자의 D보다 이른 가장 늦은 날"이다. 확정이 빠짐없이 돌면 직전 영업일과 같다([§12](#12-스펙-반영-후보) 1).

### 6.2 확정 후보와 조건

- **후보 날짜**: `snapshot_run`이 없는 KR 영업일 가운데 가장 이른 날. 범위는 `account`에 있는 계좌의 `collection_run` 가운데 가장 이른 `as_of`부터 **오늘(KST)까지**다. 그 날을 확정하지 못하면 그 뒤 날짜는 보지 않는다. 그래서 확정 이월의 원본은 늘 직전 영업일의 확정 라인이다. 백엔드가 며칠 멈췄다 돌아오면 이 순서로 따라잡는다.
- **마감**: D 다음 KR 영업일(`next_trading_day`)의 `portfolio.snapshot.finalize-at`(기본 `08:00`) KST. 캘린더에서 정할 수 없으면 확정하지 않고 경고 로그를 남긴다.
- **계좌가 확정 가능해지는 때** — 둘 중 하나.
  - D의 `SCHEDULE` 실행이 하나 이상 있고, 전부 `position_build`에 최종 사유(재시도 사유가 아님)로 처리됐다.
  - 마감이 지났고, 그 계좌의 D 실행 가운데 끝났는데(§5.1의 대상 조건) `position_build`에 아직 없는 것이 없다. 마감 직전에 끝난 실행이 처리되기 전에 이월로 덮이지 않게 한다. 재시도 사유로 남은 실행은 기다리지 않는다.
- **대상 계좌가 0개인 날**은 마감이 지나야 확정한다. 마감 전에 확정하면 그날 늦게 끝나는 첫 수집이 `FINAL_EXISTS`로 막혀 계좌가 편입되지 못한다.

### 6.3 계좌 확정

계좌마다 트랜잭션 하나. D 공유 잠금과 그 계좌 잠금을 잡은 뒤, D가 이미 확정됐거나 계좌가 `DISCONNECTED`면 아무것도 하지 않는다. 아니면 D의 라인을 본다.

| D의 라인 | 처리 | `position_build` |
|---|---|---|
| 확정 | 없음 — `SCHEDULE` `DONE`이 이미 썼다 | — |
| 잠정 실측 | `is_final = true`로 올린다. 그날 성공한 실측이 직전 성공 스냅샷이다 | `PROMOTED` |
| 잠정 이월 또는 없음 | 지우고, 직전 영업일 라인 한 벌을 D로 복사한다. `is_carried_forward = true`, `is_final = true`, 금액 · `fx_*` · `source_as_of`는 원본 그대로. 직전 영업일 라인이 없으면 아무것도 쓰지 않는다(편입 전) | `CARRIED` |

마감으로 확정했으면 `reason = 'DEADLINE'`.

한 계좌의 확정이 예외로 실패하면 그 계좌만 롤백하고 다음 계좌로 넘어간다. 그 날은 확정되지 않고 다음 회차에 다시 시도한다.

### 6.4 `as_of` 확정

대상 계좌가 모두 확정되면 `snapshot_run(D)`를 쓴다(`SnapshotRunRecorder`, `ON CONFLICT DO NOTHING`). 대상이 0개인 날도 마감 뒤에는 쓴다 — 알림 평가기가 그날을 "스냅샷 없음"으로 다루지 않게 한다.

**알림이 읽는 확정본**: 알림의 미리보기와 생성 검증(보유 여부)은 사용자의 가장 늦은 확정 스냅샷을 읽는다(`HoldingMapper.latestFinalAsOf`). `SCHEDULE` `DONE`은 날짜 확정 전에 그 계좌의 라인을 `is_final = true`로 쓰므로, `is_final`만 보면 일부 계좌만 확정된 날을 확정본으로 읽는다. 그래서 이 조회를 `snapshot_run`이 있는 날로 한정한다. 알림 평가기는 이미 `snapshot_run`을 신호로 쓴다.

**확정이 멈췄을 때**: 마감이 지났는데 D가 확정되지 않으면 매 회차 경고 로그에 D와 확정하지 못한 `account_id`를 남긴다. 한 날짜가 막히면 그 뒤 날짜와 전 사용자의 `snapshot_run`이 함께 멈추므로, 이 로그가 운영에서 볼 신호다.

## 7. 멱등성과 동시성

복제본 두 개가 매분 같은 잡을 돈다. 잠금은 항상 이 순서로 잡는다: **날짜 잠금 → 계좌 잠금(`account_id` 순)**.

| 트랜잭션 | 잠금 | 하는 일 |
|---|---|---|
| 실행 처리 | D 공유 advisory lock → 그 사용자의 계좌 전부 `FOR UPDATE` (`account_id` 순) | `snapshot_run(D)` 없음 확인 → `position_build` 기록 → 라인 교체 · 잠정 이월 → 연동 상태 전이 |
| 계좌 확정 | D 공유 advisory lock → 그 계좌 `FOR UPDATE` | D 라인 재확인 → 승격 · 이월 |
| 날짜 확정 | D 배타 advisory lock | 대상 계좌 전부 확정됐는지 확인 → `snapshot_run` |

- 날짜 확정이 배타 잠금이므로, `snapshot_run(D)` 확인과 라인 쓰기 사이에 다른 복제본이 D를 확정할 수 없다. 확정된 날의 라인은 바뀌지 않는다.
- 실행 처리가 사용자의 계좌 전부를 잠그는 것은 잠정 이월(§5.6)이 다른 계좌의 라인을 쓰기 때문이다. 같은 사용자의 두 실행이 서로 다른 계좌를 먼저 잡아 교착하지 않게 `account_id` 순으로 잡는다.
- 실행 처리는 계좌 잠금을 잡은 뒤 `position_build`에서 그 실행의 기록을 다시 읽는다. 최종 사유로 이미 있으면 다른 복제본이 처리한 것이므로 아무것도 하지 않는다. 기록은 `INSERT … ON CONFLICT (run_id) DO UPDATE`로 쓰고, 재시도면 `attempts`를 올린다. 계좌의 연동 상태도 잠근 뒤에 읽은 값으로 판정한다.
- 어느 단계에서 죽어도 트랜잭션이 함께 사라져 다음 회차가 같은 결과를 낸다.

## 8. EOD 행에 `credential_ref` 채우기 — `CredentialFiller`

데이터가 만든 EOD 행(`SCHEDULE`)은 `credential_ref`가 비어 있다. 이 컬럼만 백엔드가 쓴다(데이터 요구사항 §6.10).

```sql
UPDATE collection_run r
   SET credential_ref = a.credential_ref
  FROM account a
 WHERE r.account_ref = a.account_ref
   AND r.state = 'REQUESTED'
   AND r.credential_ref IS NULL
   AND a.credential_ref IS NOT NULL
   AND a.link_state IN ('CONNECTING', 'CONNECTED')
```

- 값은 `account.credential_ref` — 시크릿 매니저(SSM SecureString)의 파라미터 이름 — 를 그대로 복사한다. 자격증명 값은 다루지 않는다. 데이터 워커가 이 이름으로 `ssm:GetParameter`를 부른다.
- 이 잡이 쓸모 있으려면 데이터 워커가 `credential_ref`가 채워진 `REQUESTED`만 집어야 한다. 지금 워커는 비어 있는 행도 집어 즉시 `FAILED`로 끝낸다(대조 문서 §4의 6번). 반영 전까지 EOD 행은 대부분 `FAILED`로 끝나고 확정 단계가 이월한다.

## 9. 연동 상태와 `last_collection`

| 계기 | 전이 |
|---|---|
| `DONE` 실행 처리 | `CONNECTING` → `CONNECTED` |
| `REAUTH_REQUIRED` 실행 처리 | `CONNECTING` · `CONNECTED` → `REAUTH_REQUIRED` |
| 그 밖 | 바꾸지 않는다. `REAUTH_REQUIRED` → `CONNECTED`는 재인증 흐름이, `DISCONNECTED`는 해제가 정한다 |

전이는 그 실행이 그 계좌에서 `requested_at`이 가장 늦은 실행일 때만 한다. 재인증 뒤에 재인증 전 실행이 늦게 처리돼 상태가 되돌아가지 않게 한다.

수집 결과 자체는 저장하지 않는다. 계좌별 뷰의 `last_collection`은 `CollectionRunStatusPort`가 그 계좌의 `requested_at`이 가장 늦은 실행에서 `state` · `as_of` · `failure_reason`을 읽어 낸다(스펙 §7.2). `failure_reason`은 코드 모양(`^[A-Z][A-Z0-9_]{0,63}$`)일 때만 그대로 싣고 아니면 `UNKNOWN`으로 바꾼다. 데이터 쪽 실제 값은 지금 `"{예외타입}: {메시지}"` 같은 자유 문자열이라(대조 문서 §3) 원천 응답이나 내부 식별자가 사용자 응답으로 나갈 수 있다.

## 10. 설정과 켜기 전 확인

| 키 | 기본 | 뜻 |
|---|---|---|
| `portfolio.snapshot.runtime.enabled` | `false` | 잡을 등록할지 |
| `portfolio.snapshot.finalize-at` | `08:00` | 마감 시각(D 다음 KR 영업일, KST) |
| `portfolio.snapshot.batch-size` | `100` | 한 회차에 처리할 실행 수 |

기본을 끄는 이유: 운영 `data`에 `cln_*`가 없으면 켜는 즉시 매 회차 오류가 난다. 운영에서 켜는 것은 매니페스트 변경이며, 그 전에 운영 DB에서 읽기로 확인한다.

- §4.1의 표가 `data`에 있다.
- 백엔드 DB 계정이 그 표들을 `SELECT`할 수 있고, `collection_run.credential_ref`를 `UPDATE`할 수 있다(`has_table_privilege` · `has_column_privilege`).

## 11. 테스트

`test` 프로파일과 `portfolio_test` DB를 쓰고, CI(`build-and-push`)의 `postgres:16-alpine` 서비스에서 그대로 돈다. 잡은 테스트에서 끄고 `SnapshotJobs`의 메서드를 직접 부른다. 시각은 고정 시계를 주입한다. 확정 단계는 DB 전체를 보므로, 생성기 테스트는 공유 샘플(`sample_portfolio.sql`)을 쓰지 않고 자기 픽스처를 비우고 심는다.

**함께 고치는 기존 것**

- `SchemaContractTest.범위_밖_테이블을_만들지_않는다`: `cln_balance` · `cln_deposit` · `collection_run`을 목록에서 뺀다(V7 미러가 만든다). 같은 테스트에 네 미러 표의 컬럼 목록 단언을 더한다. 이 단언은 미러와 기대값을 둘 다 백엔드가 쓰므로 미러가 데이터 요구사항 문서에서 벗어나는 실수만 잡는다. 운영 데이터 스키마와의 차이는 §10의 켜기 전 확인이 잡는다.
- `sample_portfolio.sql`의 `TRUNCATE` 목록에 `position_build`를 더한다. `account`를 FK로 가리키는 표가 목록에 없으면 Postgres가 `TRUNCATE`를 거부한다.
- `sample_portfolio.sql`의 `TRUNCATE` 목록에 `collection_run` · `cln_balance` · `cln_deposit` · `fx_rate`도 넣는다. 수집 결과를 심는 테스트가 남긴 행이 샘플을 쓰는 화면 테스트(`last_collection: null`)에 섞이지 않게 한다.
- `PositionLineInvariantsTest`: 편입 전 계좌 · 재연동 계좌는 누락이 아니라는 사례를 더한다.
- 알림 `HoldingReader`: `snapshot_run`이 없는 날의 확정 라인은 최신 확정본으로 읽지 않는다.

**순수 단위**

- `LineCalculator`: KRW 행 · USD 행 · 환율 폴백 · 원화 반올림 경계(.5) · 예수금 0원 · 수량 0 행 거름 · `instrument_id` null · 실패 사유 각각.
- `LineInvariants`: 규칙마다 위반 사례 하나.
- 확정 판정: 대상 계좌 정의 · 마감 전후 · 캘린더 없음 · 대상 0개 · 오늘 이후 날짜 제외.
- `failure_reason` 걸러내기.

**통합 (실제 Postgres)**

| 시나리오 | 확인 |
|---|---|
| `SCHEDULE` `DONE` | 라인 값 · `is_final = true` · `source_as_of` · `snapshot_run` |
| `SCHEDULE` `FAILED`, 직전 영업일 라인 있음 | 확정 이월 — 금액 · `fx_*` · `source_as_of` 보존 |
| 계좌 A·B 중 A만 `USER` `DONE` | A 잠정 실측 + B 잠정 이월. `GET /portfolio/views/accounts`가 200이고 B에 기준일 배지 재료(`is_carried_forward`)가 있다 |
| 직전 영업일이 아직 확정 전인 아침에 A만 `USER` `DONE` | B는 그 전 기준일 값으로 잠정 이월되고 화면이 200 |
| 위 상태에서 그날 `SCHEDULE` 둘 다 `DONE` | 둘 다 새 값으로 확정 |
| 위 상태에서 A `SCHEDULE` `FAILED` · B `DONE` | A 승격, B 새 값 확정 |
| `SCHEDULE` `DONE` 뒤 같은 날 `USER` `DONE` | `FINAL_EXISTS`, 라인 불변 |
| 같은 날 두 `USER` 실행이 역순으로 처리됨 | `OLDER_THAN_EXISTING`, 새 값 유지 |
| 계좌 0개에서 첫 `SCHEDULE`이 저녁에 끝남 | 마감 전 확정되지 않고 첫 라인이 생긴다 |
| 첫 수집 계좌가 기존 계좌보다 늦게 끝남 | 그날 확정이 기다렸다가 둘 다 담는다 |
| 첫 수집 `FAILED` | 라인 없음, 마감 뒤 `snapshot_run` |
| 해제 → 몇 달 뒤 같은 행 재연동 → 첫 수집 `FAILED` | 옛 라인을 이월하지 않는다 |
| 실행 없이 마감 경과 | 대상 계좌 전부 이월 → `snapshot_run` |
| 마감이 지났는데 끝난 실행이 아직 처리되지 않음 | 그 실행을 처리한 뒤에 확정한다 |
| 다음 영업일을 캘린더에서 정할 수 없음 | 확정하지 않고 멈춘다 |
| D-1 미확정에서 D `SCHEDULE` `DONE` | D 라인은 쓰되 확정은 D-1 뒤 |
| 종목 미매칭 → 다음 회차에 매칭됨 | 재시도로 `BUILT`, `attempts = 2` |
| 잔고 시각 < `requested_at` | `STALE_BALANCE`, 라인 불변 |
| `REAUTH_REQUIRED` · 재인증 후 옛 `REAUTH_REQUIRED`가 늦게 처리됨 | 전이 · 되돌리지 않음 |
| `DISCONNECTED` 계좌 | 대상 아님 |
| 한 계좌 확정 중 예외 | 다른 계좌는 확정, 그 날은 미확정 |
| 같은 회차 두 번 · 두 스레드 동시 | 결과 동일 |
| 실행 처리와 날짜 확정을 동시에 | 확정된 날의 라인이 바뀌지 않는다(`CountDownLatch`로 겹침) |
| `credential_ref` 채우기 | `CONNECTING` · `CONNECTED`만, 이미 찬 행은 그대로 |
| `CollectionRunStatusPort` | 최신 실행을 고른다 |

기존 골든 파일은 바꾸지 않는다.

## 12. 스펙 반영 후보

스펙 문장은 고치지 않고 아래처럼 읽었다. 스펙에 반영할지는 따로 정한다.

1. **편입 시점** — §9.1 "연동이 유효한 모든 계좌는 해당 `as_of`에 라인 존재"를 "직전 영업일에 라인이 있었던 계좌"로 읽었다(§6.1). 첫 수집 전 계좌와 재연동 직후 계좌는 이월할 직전 라인이 없다.
2. **확정 전 수정** — §9.1 "당일 외의 `as_of` 행은 수정 불가"와 §5.4 "과거 `as_of` 행은 어느 경우에도 수정하지 않는다"를 "`snapshot_run`으로 확정되기 전에는 그 `as_of`의 행을 쓸 수 있다"로 읽었다. 자정을 넘겨 끝나는 EOD 수집(데이터 EOD는 23:00 KST 시작)과 다음 날 아침 마감 확정이 이 해석에 기댄다. 앞 날짜의 확정이 막히면 쓸 수 있는 기간이 그만큼 늘어난다. 확정 뒤에는 바꾸지 않는다.
3. **잠정 실측 승격** — §5.4 "EOD 배치만 `is_final = true`"와 §7.3 · §9.1 "최종 상태가 `DONE`이 아니면 이월"에서, 같은 날 수동 동기화로 얻은 실측을 직전 성공 스냅샷으로 보고 확정으로 올렸다(§6.3). 장중 시세가 그날 확정값이 되며 기준일 배지는 붙지 않는다. 그 계좌 행의 `source_as_of`는 그 시각을 담는다.
4. **잠정 이월** — §7.3의 이월을 확정 전 잠정 라인에도 적용했다(§5.6). 스펙은 이월을 실패 계좌에 대해서만 적었다.
5. **`credential_ref` "단기 참조"** — §7.7 · §11.2는 픽업 시 단기 참조를 넘긴다고 적었다. 이 설계는 계좌의 SSM 파라미터 이름을 그대로 복사한다(§8). 접근 범위는 워커 IAM 정책과 파라미터 경로(`/stock-project/accounts/*`)가 한정한다.
6. **잔고 한 벌** — 데이터 요구사항 §6.5 "백엔드는 최신 `source_as_of` 한 행만 쓴다"를 계좌 단위 한 벌로 읽었다(§5.2).
7. **재연동 시 계좌 행 재사용** — §7.1은 "`account_id`는 재등록 때 새 uuid가 나온다"고 적었지만 V1 스키마의 `account.account_ref`는 UNIQUE라 같은 계좌의 새 행을 넣을 수 없다. 등록 API가 옛 행을 재사용하기로 했다(§1).
8. **`position_build`** — 스펙 §5.1 표 목록에 없는 백엔드 내부 표를 더한다(§4.3).

## 13. 데이터 쪽 의존

이 생성기가 운영에서 라인을 만들려면 대조 문서 §4의 1~6번이 필요하다. 하나라도 빠지면 잡은 돌지만 결과가 이렇다.

| 빠진 것 | 결과 |
|---|---|
| `cln_balance` · `cln_deposit`가 `data`에 없음 | 잡을 켤 수 없다(§10) |
| `instrument_id` 매핑 | 보유 종목이 있는 계좌의 `DONE`이 마감까지 `UNMATCHED_INSTRUMENT`로 재시도하다 이월된다. 첫 라인이 없던 계좌는 편입되지 않는다 |
| 픽업 조건 · `as_of` 타입 | `collection_run`이 `FAILED`로 끝난다 → 이월 |
| `silver_synced_at` | 반영 전에 읽으면 `NO_BALANCE` · `STALE_BALANCE`로 재시도한다. 마감 전에 반영되면 정상 생성된다 |
| EOD를 KR 영업일로 | 비영업일 행은 `NOT_TRADING_DAY`로 건너뛰고, 빠진 영업일은 마감 이월로 채운다 |
| EOD 행이 없는 계좌(데이터 `dim_account` 갱신 정지) | 그날 확정이 다음 영업일 08:00 마감까지 밀린다. 금요일이면 월요일 08:00이다 |
