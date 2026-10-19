# 수동 동기화 `POST /sync` · `GET /sync/{run_id}` 설계

[포트폴리오 스펙](2026-07-28-portfolio-management-spec.md) §5.1 `sync_run` · §7.6 · §7.7 · §8.1 · §8.2 · §8.5의 수동 동기화를 백엔드에 구현하는 설계다. 스펙이 정한 것은 다시 적지 않고, 스펙이 열어 둔 것을 정한다. 스펙과 이 문서가 다르면 스펙이 맞다. 스펙 문구를 다르게 읽은 곳은 [§8](#8-스펙-해석)에 모았다.

| 근거 | 위치 |
|---|---|
| `sync_run` · 트리거 · 오케스트레이션 | 스펙 §5.1 · §7.6 · §7.7 |
| 확정과 잠정 · 이월 | 스펙 §5.4 · §7.3 · §9.1 |
| 엔드포인트 · notice · 응답 · 오류 · 인증 | 스펙 §8.1 · §8.2 · §8.5 · §8.6 · §8.8 · §9.3 |
| `collection_run` 계약 | [데이터 요구사항](../data-requirements.md) §6.10 |
| `USER` 실행을 처리하는 쪽 | [보유 스냅샷 생성기 설계](2026-10-15-position-line-builder-design.md) §5 · §6 |
| 계좌 행 · `linked_at` · 오류 처리 방식 | [KIS 계좌 등록 · 해제 API 설계](2026-10-16-account-link-api-design.md) §2.1 · §3.5 |

## 1. 범위

**만든다**

- `POST /sync` — 인증 주체의 전 계좌 또는 단일 계좌에 `USER` 수집 요청을 넣고 `sync_run`을 연다.
- `GET /sync/{run_id}` — 그 실행의 진행 상태와 계좌별 결과.
- 열린 실행을 닫는 단계. 보유 스냅샷 생성기의 회차에 붙는다(§5).
- 뷰 응답의 `SYNC_IN_PROGRESS` · `ALREADY_FINAL` notice.
- 마이그레이션: `sync_run` · `sync_run_account`.

**만들지 않는다**

- `POST /accounts/{id}/reauth`와 재인증 완료 트리거. KIS는 앱키 방식이라 재인증이 없다.
- 완료 푸시. 반영된 값은 뷰에 나타나고, 진행 상태는 `GET /sync/{run_id}`로 볼 수 있다. 화면이 폴링할지는 화면이 정한다.
- 데이터 쪽 변경(픽업 주기 등). 필요한 것은 §9에 적는다.
- `collection_run` · `position_line` 처리 규칙 변경. `RunProcessor` · `Finalizer` · `CredentialFiller`는 그대로 둔다.

## 2. 전제

### 2.1 `USER` 행은 다음 가동일 밤에 수집된다

`data.collection_run`의 `REQUESTED` 행을 집는 곳은 Airflow `collection_run_daily`의 `run_collection` 태스크 하나다. 이 DAG는 일 · 화 · 수 · 목 23:00(KST)에 돈다. `USER` 행도 그 실행에서 `SCHEDULE` 행과 함께 집힌다. 그래서 수동 동기화는 요청 즉시가 아니라 다음 가동일 밤에 수집된다. 이 설계는 그 지연을 숨기지 않고 응답 문장과 notice로 알린다(§4.1 · §4.4).

데이터 쪽 픽업이 빨라져도 이 설계는 바뀌지 않는다. 다음 픽업 시각을 설정값(§6)으로 두었으므로 그 값만 바꾼다.

요청 시점별로 라인에 생기는 일은 다음과 같다. `as_of`는 요청일이고, 그날 확정 마감은 다음 KR 영업일 08:00(`Finalizer.deadline`)이다.

| 요청 | 픽업 | 결과 |
|---|---|---|
| 화 · 수 · 목, 23:00 전 | 그날 23:00 | 같은 밤의 `SCHEDULE` 행이 확정 라인을 쓴다 |
| 금 | 일 23:00(마감 월 08:00 전) | 금요일 라인이 바뀐다. 같은 밤 `SCHEDULE`(`as_of` 금)이 확정한다 |
| 월 | 화 23:00(마감 화 08:00 후) | 그날이 이미 확정돼 `FINAL_EXISTS`. 라인 불변 |
| 토 · 일 | 일 23:00 또는 화 23:00 | 비영업일이라 `NOT_TRADING_DAY`. 라인 불변 |

라인이 바뀌지 않는 요청도 수집은 한다. `last_collection` · `last_synced_at` · 연동 상태 전이가 갱신된다(스펙 §5.4). 그런 요청은 `ALREADY_FINAL`로 알린다(§5.3).

### 2.2 `collection_run` 쓰기

백엔드가 `USER` 행을 넣을 때 쓰는 요청 컬럼은 `run_id` · `account_ref` · `requested_by` · `as_of` · `requested_at` · `credential_ref`다(데이터 요구사항 §6.10). `state`는 처음 값 `REQUESTED`를 직접 적는다. 표 기본값에 기대지 않는다. 그 뒤의 `state`와 진행 상태 컬럼은 데이터만 쓴다.

- 운영 앱 계정 `portfolio`는 `data.collection_run`에 `INSERT`할 수 있다(2026-10-17 운영 DB 읽기 조회로 확인).
- 데이터 워커는 `credential_ref`가 찬 행만 집는다. `POST /sync`가 계좌의 `credential_ref`를 같은 트랜잭션에서 넣는다. 계좌 값이 비어 있으면 비운 채 넣고, `CredentialFiller`가 계좌 값이 생긴 뒤에 채운다(`CONNECTING` · `CONNECTED` 계좌).
- 데이터는 `USER` 행을 만료시키지 않는다(`expire_stale_schedule`은 `SCHEDULE`만 본다). 그래서 실행이 영원히 열려 있지 않도록 백엔드가 시한을 둔다(§5.2).
- 같은 밤 같은 계좌의 `USER` · `SCHEDULE` 행은 한 `run_collection` 파드에서 차례로 처리되고, KIS 토큰은 파드 안 파일 캐시로 재사용된다. 앱키당 1분 1회 발급 제약에 걸리지 않는다.

### 2.3 운영에서 생성기가 꺼져 있다

`portfolio-api`의 `SNAPSHOT_RUNTIME_ENABLED`가 설정되지 않아 기본값 `false`로 돈다(2026-10-17 확인). 닫기 단계는 생성기와 같은 스위치로 돌므로(§5.1), 꺼져 있는 동안 운영의 실행은 저장상 열린 채 남는다. 그래서 읽는 쪽(`GET /sync/{run_id}` · 뷰 notice)도 시한을 직접 적용한다(§4.2 · §4.4) — 시한이 지난 실행은 저장 상태와 무관하게 닫힌 것으로 보인다. 스위치를 켜면 닫기 단계가 그 실행들을 같은 결과로 저장한다. `POST /sync`는 스위치와 무관하게 받는다 — 요청 행은 데이터 워커가 집는다. 생성기를 켜는 일은 이 설계 밖이다.

운영 `portfolio-api`는 복제본 2개다. 닫기 단계는 복제본마다 돈다.

## 3. 테이블

마이그레이션 하나로 두 표를 만든다. 번호는 main 병합 순서로 정한다.

### 3.1 `sync_run`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `run_id` | uuid PK | |
| `user_id` | uuid NOT NULL FK `app_user` | 발급한 사용자. 조회 범위의 기준(§8.1) |
| `account_id` | uuid null FK `account` | 단일 계좌 실행이면 그 계좌. 전체 실행은 null |
| `as_of` | date NOT NULL | 요청일(KST). 이 실행이 넣은 `collection_run.as_of`와 같다 |
| `started_at` | timestamptz NOT NULL | 요청을 받은 시각 |
| `finished_at` | timestamptz null | 닫은 시각 |
| `state` | text NOT NULL | CHECK `RUNNING` · `PARTIAL` · `DONE` · `FAILED` |
| `failure_reason` | text null | 실행 단위 사유. 값은 `PICKUP_TIMEOUT` 하나 |
| `already_final` | boolean NOT NULL | 이 요청이 라인을 바꾸지 못하는가(§5.3) |
| `finalized_at` | timestamptz null | `already_final`일 때 그날의 확정 시각 또는 확정 마감. 비영업일이면 null |

- CHECK: `state = 'RUNNING'`과 `finished_at IS NULL`이 함께 성립한다.
- 인덱스: `(user_id, started_at DESC) WHERE finished_at IS NULL` — 뷰마다 그 사용자의 열린 실행을 찾는다.
- 인덱스: `(started_at, run_id) WHERE finished_at IS NULL` — 닫기 단계가 열린 실행 전부를 이 순서로 훑는다(§5.2).
- 계좌 수집이 실패해 `PARTIAL` · `FAILED`가 된 실행은 `failure_reason`을 비운다. 계좌별 사유는 `sync_run_account`와 응답의 계좌 행에 있다.

### 3.2 `sync_run_account`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `sync_run_id` | uuid FK `sync_run` | |
| `account_id` | uuid FK `account` | |
| `collection_run_id` | uuid NOT NULL | `data.collection_run.run_id`. 여러 실행이 같은 값을 가리킬 수 있다(§4.1) |
| `final_state` | text null | 닫을 때 채운다. CHECK `DONE` · `FAILED` · `REAUTH_REQUIRED` |
| `final_as_of` | date null | 닫을 때의 계좌 기준일(§4.2). 그 계좌에 라인이 없으면 null |
| `final_failure_reason` | text null | 닫을 때의 계좌 사유 |

- PK `(sync_run_id, account_id)`. 인덱스 `(collection_run_id)`.
- `collection_run_id`에 FK를 걸지 않는다. `data.collection_run`은 데이터가 DDL을 적용하는 표라, FK를 걸면 운영에서 `REFERENCES` 권한과 두 팀 배포 순서가 묶인다.
- 실행이 열려 있는 동안 계좌별 결과는 저장하지 않고 `collection_run`과 `position_build`에서 도출한다(§4.2). 두 표는 데이터와 생성기가 쓰는 사실이라, 복사하면 같은 사실이 두 곳에 생긴다. 닫을 때만 굳힌다 — 닫힌 실행의 응답이 늦게 도착한 데이터로 바뀌지 않게.

## 4. API

### 4.1 `POST /sync` → `202`

**요청 본문**

```json
{ "account_id": "..." }
```

`account_id`가 있으면 그 계좌, 본문이 없거나 `account_id`가 null이면 인증 주체의 전 계좌가 대상이다.

**대상 계좌**

| 계좌 | 처리 |
|---|---|
| `CONNECTING` · `CONNECTED` · `REAUTH_REQUIRED` | 대상 |
| `DISCONNECTED`를 지정 | `409 ACCOUNT_DISCONNECTED` |
| 전체 실행에서 `DISCONNECTED` | 대상에서 뺀다 |
| 전체 실행인데 대상이 0개 | `409 NO_ACCOUNTS` |

**처리** — 트랜잭션 하나

1. 사용자의 계좌 행을 `account_id` 순으로 잠근다(`PositionWriteMapper.lockUserAccounts`와 같은 잠금). 같은 사용자의 동시 요청과 생성기 처리가 이 지점에서 줄을 선다.
2. 대상 계좌마다 열린 `USER` 행을 찾는다. 열린 행은 `account_ref`가 같고 `requested_by = 'USER'`, `as_of` = 요청일(KST), `state IN ('REQUESTED', 'RUNNING')`, `requested_at >= account.linked_at`(`linked_at`이 null이면 이 조건 없음)인 행이다. 여럿이면 `requested_at`이 가장 늦은 것을 쓴다.
3. 열린 행이 없는 계좌에만 새 `collection_run`을 넣는다: `run_id` 새 uuid, `requested_by = 'USER'`, `as_of` = 요청일(KST), `requested_at` = 지금, `credential_ref` = 계좌의 값.
4. `already_final` · `finalized_at`을 판정한다(§5.3).
5. `sync_run`(`RUNNING`)과 계좌마다 `sync_run_account`를 넣는다.

진행 중인 실행이 있어도 거절하지 않는다. 매번 새 `sync_run`을 만들고, 수집은 계좌 · 요청일 단위로 공유한다. 그래서 다시 눌러도 오류가 나지 않고, 일부 계좌만 진행 중일 때 전체를 눌러도 나머지 계좌가 빠지지 않으며, 같은 날의 요청이 같은 계좌를 두 번 수집하지 않는다.

공유는 `as_of`가 같을 때만 한다. 다른 날의 열린 행을 공유하면 그 행의 `as_of`로 라인이 처리되어, 요청일 기준의 안내(§4.1 응답 · §5.3)와 결과가 어긋난다. 그래서 날짜가 바뀌면 새 행을 넣고, 한 밤에 같은 계좌의 `USER` 행이 둘 집힐 수 있다. 같은 파드에서 차례로 처리되어 KIS 토큰을 재사용한다(§2.2). 남은 옛 행은 집힌 뒤 그날이 확정돼 있으면 `FINAL_EXISTS`로 끝난다.

열린 행이 `RUNNING`이면 그 수집은 요청 직전에 시작됐을 수 있다. 같은 밤의 수집이므로 그대로 공유한다.

**응답**

```json
// 202, Location: /sync/{run_id}
{ "run_id": "...", "message": "다음 수집(10-18(일) 23:00)에 반영됩니다" }
```

| `already_final` | `message` |
|---|---|
| false | `다음 수집({다음 픽업})에 반영됩니다` |
| true | `{as_of} 값은 이미 확정되어 바뀌지 않습니다. 계좌 상태만 다음 수집({다음 픽업})에 갱신됩니다` |

날짜는 `MM-dd`, 다음 픽업은 `MM-dd(요일) HH:mm`(KST)이다. 다음 픽업은 `portfolio.sync.pickup-cron`으로 지금 이후 첫 시각을 구한다(§6). 백엔드는 Airflow가 실제로 도는지 모르므로 이 값은 예정이다.

### 4.2 `GET /sync/{run_id}` → `200`

스펙 §8.5의 모양에 실행 단위 `failure_reason`을 더한다.

```json
{ "run_id": "...", "state": "PARTIAL", "started_at": "...", "finished_at": "...",
  "failure_reason": null,
  "accounts": [ { "account_id": "...", "label": "한국투자 위탁",
                  "state": "DONE", "as_of": "2026-10-16", "failure_reason": null },
                { "account_id": "...", "label": "한국투자 연금",
                  "state": "FAILED", "as_of": "2026-10-15", "failure_reason": "SOURCE_TIMEOUT" } ] }
```

`accounts[]`는 `sync_run_account`의 행 전부를 `account_id` 순으로 싣는다. 실행 뒤 해제된 계좌도 남는다.

**계좌 행 — 열린 실행**

| 필드 | 값 |
|---|---|
| `label` | `account.label`의 현재 값 |
| `state` | 아래 도출 규칙 |
| `as_of` | 그 계좌 값의 기준일. 사용자의 가장 늦은 `as_of` 라인에서 계좌별 뷰와 같은 신선도 규칙(`AccountFreshness`: 종목 중 가장 이른 `source_as_of`)으로 구한 시각의 KST 날짜. 그 계좌에 라인이 없으면 null |
| `failure_reason` | `collection_run.failure_reason`을 `FailureReasons.sanitize`로 거른 값 |

`state` 도출:

| `collection_run.state` | `position_build`(`run_id` = `collection_run_id`) | 계좌 `state` |
|---|---|---|
| `REQUESTED` · `RUNNING` | — | `RUNNING` |
| `DONE` | 기록 없음 | `RUNNING` |
| `DONE` | 기록 있음(결과 · 사유 무관) | `DONE` |
| `FAILED` | — | `FAILED` |
| `REAUTH_REQUIRED` | — | `REAUTH_REQUIRED` |
| 행이 없다 | — | `RUNNING` |

`DONE`인데 생성기 결과가 `FINAL_EXISTS` · `NOT_TRADING_DAY`이거나 재시도 사유로 남은 경우도 `DONE`이다. 수집은 성공했고, 라인이 바뀌지 않는 사정은 `as_of`와 `ALREADY_FINAL`이 말한다. 재시도 사유를 기다리면 끝이 정해지지 않는다.

**계좌 행 — 닫힌 실행**: `state` · `as_of` · `failure_reason`은 `sync_run_account.final_*`를 그대로 싣는다. `label`만 현재 값이다.

**시한이 지난 열린 실행**: 저장상 열려 있어도 `started_at + timeout` ≤ 지금이면 §5.2의 시한 규칙을 그 자리에서 적용해 응답한다. 닫기 단계가 같은 규칙으로 저장하므로 `state` · `finished_at` · `failure_reason`과 계좌 행의 `state` · `failure_reason`은 저장 전후가 같다. 계좌 `as_of`만 저장 전에는 그때의 기준일이다.

**거절**: 남의 실행, 없는 실행, UUID가 아닌 `run_id`는 모두 `403 FORBIDDEN_SYNC_RUN`이다. 계좌 API가 남의 계좌와 없는 계좌를 구분하지 않는 것과 같게, 실행이 있는지를 새지 않는다.

### 4.3 오류

오류 본문은 `{ "error": { "code", "message" } }`다(스펙 §8.6). 예외 메시지는 응답에도 로그에도 내보내지 않는다 — 제약 위반 메시지에 `account_ref` · `credential_ref` 값이 들어 있다.

| 상황 | 코드 | `error.code` |
|---|---|---|
| 토큰 없음 · 만료 | `401` | `UNAUTHENTICATED` |
| JSON 형식 오류 · `account_id` 자리에 문자열이 아닌 값 | `400` | `INVALID_REQUEST` |
| `account_id`가 남의 계좌 · 없는 계좌 · UUID가 아님 | `403` | `FORBIDDEN_ACCOUNT` |
| `account_id`가 `DISCONNECTED` | `409` | `ACCOUNT_DISCONNECTED` |
| 전체 실행인데 대상 계좌 0개 | `409` | `NO_ACCOUNTS` |
| `GET`의 `run_id`가 남의 것 · 없음 · UUID가 아님 | `403` | `FORBIDDEN_SYNC_RUN` |
| DB 오류 | `500` | `INTERNAL_ERROR` |

### 4.4 뷰 notice

봉투를 쓰는 뷰 전부(스냅샷 4개 · 실현손익 · 자산 변화)가 싣는다. 그 사용자의 열린 실행 중 `started_at + timeout` > 지금인 것에서 `started_at`이 가장 늦은 하나를 본다. 그런 실행이 없으면 둘 다 싣지 않는다 — 시한이 지난 실행은 닫힌 것으로 본다(§2.3).

스냅샷이 아직 없는 사용자에게도 싣는다(스펙 §8.6 "동기화 중이거나 스냅샷이 아직 없어도 `200`과 `notices`로 알린다"). 갓 등록한 계좌의 첫 동기화가 이 경우다. 스냅샷 뷰와 자산 변화 뷰의 빈 봉투 경로(`emptyEnvelope`)는 지금 notice를 비워 내리므로, 그 경로에도 이 두 notice를 싣는다. 다른 notice는 빈 봉투에 싣지 않는다 — 판정 재료가 스냅샷에서 온다.

| code | 조건 | `message` | `params` |
|---|---|---|---|
| `SYNC_IN_PROGRESS` | 열린 실행이 있다 | `동기화 요청을 받았습니다 · 다음 수집 {다음 픽업}` | `sync_run_id` · `next_pickup_at` |
| `ALREADY_FINAL` | 그 실행이 `already_final` | `{as_of} 값은 이미 확정되어 다시 수집해도 바뀌지 않습니다` | `as_of` · `finalized_at`(null 가능) |

순서와 심각도는 `NoticeCode` 선언을 따른다(둘 다 `info`).

`GET /accounts`의 `last_collection`은 `requested_at`이 가장 늦은 `collection_run`을 고르므로, 요청 직후부터 그 계좌의 `last_collection.state`가 `REQUESTED`로 보인다. 고칠 것은 없다.

## 5. 잡

### 5.1 생성기 회차에 붙인다

`SnapshotJobs.tick`(1분)의 단계를 다음 순서로 한다.

```
자격증명 채우기 → 실행 반영 → 날짜 확정 → 동기화 닫기
```

- 생성기가 같은 회차에 남긴 `position_build`를 곧바로 보고 닫는다.
- 스위치는 생성기와 같은 `portfolio.snapshot.runtime.enabled`다. 생성기 없이는 계좌가 `DONE`이 될 수 없다.
- 한 단계의 실패가 다음 단계를 건너뛰게 하지 않는다(기존 `stage`).

### 5.2 동기화 닫기

한 회차에 열린 `sync_run` 전부를 `(started_at, run_id)` 순으로 `portfolio.snapshot.batch-size`개씩 끝까지 훑는다. 아직 닫을 수 없는 실행이 앞에 많이 쌓여도 뒤의 실행이 밀리지 않는다.

실행마다 먼저 잠그지 않고 아래 표로 판정한다. 닫을 실행만 트랜잭션을 열어 `FOR UPDATE SKIP LOCKED`로 다시 잠그고, 다시 읽어 다시 판정한 뒤 쓴다. 잠그지 못했거나 이미 닫혔거나 다시 판정해 닫을 수 없으면 건너뛴다. 실행 행을 바꾸지 못하면 그 실행의 쓰기를 모두 되돌린다. 복제본이 동시에 돌아도 같은 실행을 두 번 닫지 않고, 한 실행의 실패가 다른 실행을 막지 않는다.

실행마다 계좌별 결과를 §4.2 규칙으로 도출한 뒤:

| 조건 | 처리 |
|---|---|
| `started_at + timeout` ≤ 지금 | 시한으로 닫는다. `finished_at = started_at + timeout`. `RUNNING` 계좌는 `FAILED` · `PICKUP_TIMEOUT`. 그런 계좌가 있었으면 실행 `failure_reason = 'PICKUP_TIMEOUT'`, 없었으면 null |
| 시한 전이고 모든 계좌가 `RUNNING`이 아니다 | 닫는다. `finished_at` = 지금, `failure_reason` null |
| 그 밖 | 그대로 둔다 |

시한이 지난 실행은 계좌가 모두 끝났어도 시한 규칙으로 닫는다. 읽는 쪽(§4.2)이 시한 뒤에 보여준 응답과 저장 결과가 어긋나지 않게 하려는 것이다.

닫을 때 실행 `state`는 `DONE` 계좌 수로 정한다: 전부면 `DONE`, 0이면 `FAILED`, 그 사이면 `PARTIAL`. `REAUTH_REQUIRED` 계좌는 `DONE`이 아니다. 계좌마다 `final_state` · `final_as_of` · `final_failure_reason`을 쓴다.

시한 판정(계좌 결과 도출 · 실행 상태 결정)은 닫기 단계와 읽는 쪽(§4.2 · §4.4)이 같은 코드를 쓴다. 그래야 닫기 단계가 늦게 돌아도 응답이 바뀌지 않는다.

시한이 지나 닫힌 뒤 그 `collection_run`이 끝나도 생성기는 평소대로 라인을 처리한다. 닫힌 실행의 응답만 바뀌지 않는다.

로그에는 `run_id`와 건수만 쓴다.

### 5.3 `already_final` 판정

`POST /sync`가 요청일 `D`에 대해 한 번 판정해 저장한다. 다음 중 하나라도 맞으면 참이다.

| 조건 | `finalized_at` |
|---|---|
| `D`가 KR 비영업일이거나 캘린더에 `D`가 없다 | null |
| `snapshot_run`에 `D`가 있다 | 그 `finished_at` |
| 대상 계좌의 `D` 라인이 모두 있고 모두 `is_final` | `D`의 확정 마감. 마감을 구할 수 없으면 null |
| 다음 픽업 시각 ≥ `D`의 확정 마감(`Finalizer.deadline`, `finalize-at` 사용) | `D`의 확정 마감 |

마감을 구할 수 없으면(다음 영업일을 모름) 마지막 조건은 거짓으로 보고, 라인 조건은 그대로 판정한다. 판정은 요청 시점의 예측이다 — 픽업 시각이 실제와 다르면 결과와 어긋날 수 있다.

## 6. 설정

| 키 | 기본값 | 쓰는 곳 |
|---|---|---|
| `portfolio.sync.pickup-cron` | `0 0 23 * * SUN,TUE,WED,THU` | 다음 픽업 시각(Spring `CronExpression`, Asia/Seoul). §4.1 문장 · §4.4 notice · §5.3 판정 |
| `portfolio.sync.timeout` | `PT96H` | §5.2 시한 |

시한 96시간은 가장 긴 픽업 간격(목 23:00 → 일 23:00, 72시간)에 수집 · 정제 · 반영 시간을 더하고 여유를 둔 값이다. 픽업 주기를 바꾸면 두 값을 함께 본다.

## 7. 테스트

DB를 쓰는 테스트는 실제 PostgreSQL에 Flyway로 이 마이그레이션까지 적용한 뒤 돈다. CI는 `postgres:16-alpine` 서비스로 `./gradlew test`를 돌린다. `data.collection_run` 등 데이터 소유 표는 기존 테스트 미러(`db/external`)를 쓴다. 기존 `SnapshotFixture` · `AccountFixture` · `MutableClock`을 쓴다.

**단위 (DB 없음)**

- 계좌 `state` 도출: §4.2 표의 각 행.
- 실행 `state`: 전부 `DONE` → `DONE`, 일부 → `PARTIAL`, 0 → `FAILED`, `REAUTH_REQUIRED`는 `DONE`으로 세지 않음, 시한 초과.
- 다음 픽업과 `already_final`: 고정 시계로 화 장중 → 거짓, 월 → 참(마감 화 08:00 < 픽업 화 23:00), 금 → 거짓(픽업 일 23:00 < 마감 월 08:00), 토 → 참 · `finalized_at` null, 다음 영업일 모름 → 마지막 조건 거짓.
- 문장: `POST` 응답 두 가지와 notice 두 가지의 날짜 · 요일 · 시각 표기.

**DB 통합**

- `POST /sync`
  - `202` · 본문 · `Location`. 넣은 `collection_run`의 `requested_by` · `as_of`(KST 요청일, 자정 전후) · `requested_at` · `credential_ref` · `state`.
  - 단일 계좌 / 전체 계좌. 전체 실행이 `DISCONNECTED`를 뺀다.
  - 거절: §4.3의 각 행.
  - 공유: 같은 계좌 두 번째 요청이 같은 `collection_run_id`를 가리킨다. A만 열린 상태에서 전체 요청 → A 공유 · B 새 행. `RUNNING` 행 공유. 끝난 행(`DONE` · `FAILED`)은 공유하지 않는다. `linked_at` 전에 생긴 열린 행은 공유하지 않는다. 요청일이 다른 열린 행(목 23시 이후 요청 → 금 요청)은 공유하지 않고 새 행을 넣는다.
  - `already_final`과 `finalized_at`이 §5.3대로 저장된다.
- `GET /sync/{run_id}`
  - §4.2 모양. 계좌 `as_of`가 이월 계좌에서 옛 날짜, 실측 계좌에서 새 날짜. 라인 없는 계좌는 null.
  - `failure_reason`이 코드가 아니면 `UNKNOWN`.
  - 남의 실행 · 없는 실행 · UUID 아님 → `403 FORBIDDEN_SYNC_RUN`.
  - 저장상 열린 실행이 시한을 넘기면 `PICKUP_TIMEOUT`으로 닫힌 응답이 나오고, 그 뒤 닫기 단계가 저장한 결과와 `state` · 계좌 행이 같다.
- 동기화 닫기(진짜 `RunProcessor`와 함께 돈다)
  - `USER` `DONE` → 생성기 처리 → 실행 `DONE`.
  - 한 계좌 `FAILED` → `PARTIAL`. 전부 `FAILED` → `FAILED`.
  - 생성기 결과 `FINAL_EXISTS` · 재시도 사유 → 계좌 `DONE`.
  - `MutableClock`으로 시한을 넘기면 `PICKUP_TIMEOUT`으로 닫힌다. 그 뒤 수집이 끝나도 `GET` 응답이 바뀌지 않는다.
  - 생성기 스위치가 꺼져 있으면 닫기도 돌지 않는다.
- 동시성
  - 같은 사용자의 `POST /sync` 두 개가 동시에 와도 계좌당 열린 `collection_run`이 하나다.
  - 닫기 단계 두 개가 동시에 돌아도 실행은 한 번 닫힌다.
- 뷰 notice
  - 열린 실행이 있으면 봉투를 쓰는 6개 뷰에 `SYNC_IN_PROGRESS`(`sync_run_id`)가 실린다. 여럿이면 가장 늦은 실행.
  - `already_final` 실행이면 `ALREADY_FINAL`이 함께 실린다.
  - 닫힌 실행이나 시한이 지난 열린 실행만 있으면 둘 다 없다. 남의 실행은 보지 않는다.
  - 스냅샷이 없는 사용자의 빈 봉투(스냅샷 뷰 · 자산 변화)에도 실린다.
- `SnapshotJobsTest`: 단계 순서에 동기화 닫기가 있고, 앞 단계가 실패해도 돈다.

## 8. 스펙 해석

1. **`sync_run.user_id`** — 스펙 §5.1의 컬럼 목록에 없다. §7.6 "`sync_run` 조회는 발급한 사용자에게만"을 지키려면 소유자가 필요한데, 전체 실행은 `account_id`가 null이라 계좌로 거슬러 찾을 수 없다. `as_of` · `already_final` · `finalized_at`도 같은 이유로 더한 구현 컬럼이다.
2. **계좌 행의 `as_of`** — 스펙 §8.5 예시에서 실패 계좌의 `as_of`가 이월된 날짜다. 이를 "그 계좌에서 지금 보이는 값의 기준일"로 읽었다. `collection_run.as_of`(요청일)는 한 실행 안에서 모든 계좌가 같고 실패해도 바뀌지 않아 정보가 없다.
3. **`POST /sync` 본문과 응답** — 스펙에 모양이 없다. 본문은 선택적 `account_id`, 응답은 `run_id` · `message`로 정했다. 스펙 §8.2의 "서버가 문장을 완성해 내린다"를 따른다.
4. **실행 단위 `failure_reason`** — 스펙 §8.5 예시에 없는 필드다. 시한 초과를 실행 단위로 말할 자리로 더했다. 계좌 행 모양은 그대로다.
5. **"완료 시 푸시/폴링"**(§7.6) — 폴링 경로(`GET /sync/{run_id}`)만 둔다.

## 9. 데이터 쪽 의존

| 항목 | 지금 | 영향 |
|---|---|---|
| `USER` 행 픽업 주기 | `collection_run_daily` 23:00(일 · 화 · 수 · 목) 안에서만 집힌다. 데이터 요구사항 Q1 미결 | 수동 동기화가 다음 가동일 밤에 수집된다(§2.1). 주기가 바뀌면 `pickup-cron`만 바꾼다 |
| `USER` 행 만료 | 없다 | 백엔드 시한(§5.2)이 실행을 닫는다. `collection_run` 행은 `REQUESTED`로 남는다 |
| `collection_run` 행 | 운영 `data.collection_run`이 0행이다(2026-10-17 조회). `collection_run_daily`는 켜져 있다 | 원인은 확인하지 않았다. EOD 행도 없는 상태라 이 설계와 무관하게 수집이 돌지 않는다 |
| 짧은 주기 픽업을 따로 둘 때 | — | `mark_synced`는 워커가 `collection_run_daily`에서만 돈다는 전제로 DONE 행을 일괄 표시한다. 픽업 DAG를 나누면 그 전제와 KIS 토큰 캐시(파드별 파일) 공유를 다시 봐야 한다 |
