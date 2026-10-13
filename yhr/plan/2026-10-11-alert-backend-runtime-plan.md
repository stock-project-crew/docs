# 매수·매도 타이밍 알림 — 백엔드 구현 계획 ② 평가 런타임과 전달

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

- **작성일**: 2026-10-11
- **대상 저장소**: `back-end/` (github.com/stock-project-crew/back-end), `main` 위에서 git worktree로 작업한다
- **근거 스펙**: [알림 스펙](../specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md) §3 · §6 ~ §9 · §11 · §14.4 · [데이터 요구사항](../specs/data-requirements.md) · [앱 정보 구조](../specs/app-information-architecture.md)
- **앞선 계획**: [① 알림 규칙과 조회](./2026-10-11-alert-backend-rules-plan.md). ①의 코드는 `main`에 있고, 이 계획은 코드를 기준으로 쓴다. ①의 문서와 코드가 다르면 코드가 맞다.
- **스펙 수정 금지**: 이 계획은 스펙을 인용만 한다. 스펙과 다르게 구현해야 할 사정이 생기면 코드를 바꾸지 말고 멈춰서 보고한다.

**Goal:** 완료 신호(`market_data_run` · `snapshot_run`)가 쌓이면 1분 안에 알림이 평가되고, 조건이 엣지에서 참이 되면 발화가 한 번만 기록되어 iOS 기기에 Expo Push로 간다. 사용자는 울린 알림 목록·상세·읽음·배지 API와 목록 위의 데이터 지연 안내를 받는다.

**Architecture:** 평가기 · 발송기 · 영수증 확인기는 `portfolio-api` 안의 `@Scheduled` 작업이고 모든 복제본에서 돈다(스펙 §8.1). 중복을 막는 것은 잠금이 아니라 데이터다 — 기대 버전과 직전 평가 시점을 조건으로 건 상태 갱신, `UNIQUE (alert_id, as_of)`, `FOR UPDATE SKIP LOCKED`. 계산은 ①의 순수 패키지를 그대로 쓰고, 평가 입력은 미리보기와 평가기가 같은 "시점 하나의 입력" 메서드로 만든다. 발화 판정(`FiringRule`)과 발화 문구(`EventText`)도 순수 패키지에 둔다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · Gradle (Kotlin DSL) · PostgreSQL 16 · Flyway(평문 SQL) · MyBatis(ORM 없음) · Spring `RestClient` · Spring Scheduling · JUnit 5 + AssertJ + ArchUnit + `MockRestServiceServer`

**Spec:** `docs/yhr/specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md` — 실행자는 이 계획과 스펙을 함께 읽는다.

---

## Global Constraints

이 절의 규칙은 모든 태스크의 요구사항에 암묵적으로 포함된다.

- **Java 21, Spring Boot 3.4.5, PostgreSQL 16.** 새 라이브러리를 들이지 않는다. HTTP 호출은 `spring-boot-starter-web`의 `RestClient`, 스케줄은 Spring의 `@Scheduled`, 테스트의 가짜 HTTP 서버는 `spring-test`의 `MockRestServiceServer`를 쓴다.
- **스키마는 둘이다.** 백엔드 소유 테이블과 Flyway 이력은 `app`, 데이터팀 소유 미러는 `data`에 있고 탐색 경로는 `app,data`다. `db/migration`의 새 마이그레이션은 스키마 없이 쓰면 `app`에 생긴다. `db/external` 미러는 `data.`를 명시한다. psql로 직접 적재하는 SQL은 맨 앞에 `SET search_path = app, data;`를 둔다.
- **마이그레이션 번호는 `db/migration`과 `db/external`을 통틀어 하나의 순열이다.** 지금 V5까지 있다. 이 계획은 V6(`db/migration`) 하나를 만든다.
- **테스트 DB는 `portfolio_alert_test`다.** DB를 쓰는 테스트는 `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data'`를 환경변수로 주고 돌린다. DB를 쓰지 않는 테스트 클래스만 고른 명령(Task 2 · 3 · 4 · 9의 확인)은 변수 없이 적었다 — 붙여도 결과는 같다.
- **JSON 필드명은 snake_case.** `spring.jackson.property-naming-strategy: SNAKE_CASE`가 전역으로 걸려 있다. record 컴포넌트는 camelCase로 쓴다.
- **사용자 ID를 요청에서 받지 않는다.** 컨트롤러는 `UserScope` 파라미터로만 사용자를 안다.
- **남의 것과 없는 것을 구분하지 않는다.** 남의 발화 ID와 없는 ID는 똑같이 `404 EVENT_NOT_FOUND`다(스펙 §11.4).
- **지표·금액 계산은 `BigDecimal`만 쓴다.** `double`·`float`를 쓰지 않는다.
- **컨트롤러는 매퍼·리포지토리를 직접 부르지 않는다**(`ArchitectureRulesTest`).
- **순수 패키지(`alert.catalog` · `spec` · `compile` · `indicator` · `evaluation` · `sentence`)는 Spring · MyBatis · Jakarta · Jackson에 의존하지 않는다**(`ArchitectureRulesTest`).
- **비율 성격 컬럼을 스키마에 만들지 않는다**(`MigrationLintTest`). 금지어: `_pct` · `_ratio` · `_rate_of_return` · `weight` · `yield` · `_percent`.
- **자격증명을 코드·로그·저장소에 두지 않는다.** Expo 푸시 접근 토큰은 Secret에서 환경변수로만 들어온다. 푸시 토큰(`ExponentPushToken[…]`)을 로그에 남기지 않는다 — 로그에는 `event_id` · `device_id`만 쓴다(스펙 §9.7).
- **주석과 문서는 최신 사실만 쓴다.** "예전에는", "~로 바꿨다" 같은 히스토리 문구를 쓰지 않고, 검증하지 않은 것을 단정하지 않는다.
- **커밋 메시지는 한국어, 접두는 기존 관례(`feat:` · `fix:` · `test:` · `docs:` · `chore:`)를 따른다.** 끝에 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`를 붙인다.

## Review Focus

스펙이 직접 말하지 않지만 사람이 실제로 부딪힐 입력 다섯 가지. 각 줄의 테스트는 해당 태스크에 들어 있다.

1. **평가기가 며칠 멈췄다가 다시 돈다** → 종가 알림은 밀린 거래일을 날짜 순서대로 평가하고, 발화 본문에 그날의 기준일(`9/24 종가 기준`)이 들어간다. 장중 알림은 최신 스냅샷 하나만 보고, 그것도 허용 지연을 넘었으면 평가하지 않는다. — Task 7
2. **두 복제본이 같은 알림을 동시에 평가하거나, 평가 도중 사용자가 알림을 끈다** → 발화는 한 번이고, 끈 알림은 평가 중이던 결과로 울리지 않는다. — Task 6
3. **로그아웃 없이 다른 사용자가 같은 폰으로 로그인하거나, 기기가 지워졌거나, Expo가 `DeviceNotRegistered`를 돌려준다** → 이전 사용자의 대기 푸시는 새 사용자에게 나가지 않고, 지운 기기의 행은 사라지며, 같은 묶음의 다른 행은 그대로 처리된다. 푸시가 오래 꺼져 있다 켜져도 지난 장중 푸시가 몰려 나가지 않는다. 발화 기록과 배지는 남는다. — Task 10
4. **저장된 조건 하나가 지금 코드로 읽히지 않는다**(카탈로그에서 키가 빠진 배포 등) → `GET /alerts`·`GET /alerts/{id}`는 `200`이고 그 카드만 `조건을 읽을 수 없어요`로 보이며, 평가기는 그 알림만 건너뛰고 나머지를 평가한다. — Task 7 · Task 13
5. **다른 사용자의 발화 ID로 상세·읽음 처리를 하거나, 손으로 만든 `cursor`·`limit`·`alert_id`를 보낸다** → `404 EVENT_NOT_FOUND` · `404 ALERT_NOT_FOUND` 또는 `400 INVALID_PARAMETER`이고 `500`이 나지 않는다. — Task 12

---

# 부록 A — 구현이 정하는 것

스펙이 정하지 않았거나 구현 수준까지 내려가지 않은 것을 여기서 정한다. 태스크는 이 부록을 근거로 인용한다.

## A.1 도달점과 범위

| 들어간다 | 들어가지 않는다 |
|---|---|
| `alert_delivery` · `snapshot_run` 테이블(V6)과 `snapshot_run` 기록 창구 | 포트폴리오 EOD 스냅샷 생성(포트폴리오 스펙 §3.6 1단계) 자체 — 아직 백엔드에 없다. 생기면 그 배치가 끝에서 `SnapshotRunRecorder.record`를 부른다 |
| 평가기: 만료 전이, 시점 고르기(종가 따라잡기 · 장중 최신 하나 · 보유 스냅샷), 엣지 발화, 해시 불일치 재기준, 발화 기록, 기기별 발송 행 | 평가 결과 구간의 기록(스펙 §7.4 · §17) |
| 발송기 · 영수증 확인기 · 기기 정리(Expo Push, iOS만) | Android 푸시(스펙 §9.6 · §17), 방해 금지 시간대 |
| `GET /alert-events` · `GET /alert-events/{id}` · `POST /alert-events/{id}/read` · `POST /alert-events/read-all` · `GET /alert-events/unread-count` | 앱 화면(계획 ③) |
| `GET /alerts` · `GET /alert-events`의 `MARKET_DATA_DELAYED` notice, 깨진 조건의 카드 | 운영 클러스터에서 푸시를 켜는 일(A.13) |
| ①이 넘긴 네 가지(A.12) | |

## A.2 패키지

①의 패키지(`alert.catalog` · `spec` · `compile` · `indicator` · `evaluation` · `sentence` · `validation` · `data` · `store` · `service` · `api`)에 둘을 더한다.

| 패키지 | 책임 | 프레임워크 |
|---|---|---|
| `alert.runtime` | 평가기 — 시점 고르기, 평가, 반영 트랜잭션, 스케줄 | Spring |
| `alert.delivery` | 발송기 · 영수증 확인기 · Expo 게이트웨이 | Spring · `RestClient` |

새 순수 클래스: `alert.evaluation.FiringRule` · `FiringDecision`(발화 판정), `alert.sentence.EventText`(발화 문구). 평가기와 테스트가 같은 판정을 쓴다.

## A.3 실행 형태

| 작업 | 클래스 | 주기 (`fixedDelay`) | 첫 실행 |
|---|---|---|---|
| 평가기 | `EvaluationRunner.tick()` | 1분 | 기동 10초 뒤 |
| 발송기 | `DeliveryDispatcher.dispatchOnce()` (100건 묶음이 꽉 차면 이어서) | 5초 | 기동 15초 뒤 |
| 영수증 확인기 | `ReceiptChecker.checkOnce()` | 5분 | 기동 1분 뒤 |

- 세 작업은 `AlertJobs`의 `@Scheduled` 메서드다. `AlertRuntimeConfig`가 `@EnableScheduling`과 함께 `portfolio.alert.runtime.enabled`(기본 `true`)일 때만 `AlertJobs`를 만든다. 테스트 프로필은 `false`로 두고 테스트가 세 메서드를 직접 부른다. 스펙 §8.4의 "API 파드에서는 프로필로 스케줄을 끈다"도 이 값이다.
- 스케줄 스레드는 3개다(`spring.task.scheduling.pool.size: 3`). 하나면 평가 한 번이 발송을 붙잡는다.
- 종료 신호를 받으면 진행 중인 작업을 20초까지 기다린다(`spring.task.scheduling.shutdown`). 끊겨도 트랜잭션이 롤백될 뿐 상태는 데이터에 있다(스펙 §8.3).
- 푸시는 `portfolio.alert.push.enabled`(기본 `false`, 환경변수 `EXPO_PUSH_ENABLED`)가 `true`일 때만 Expo로 나간다. 꺼져 있으면 발송 행은 `PENDING`으로 남고, 켜졌을 때 발송 기한(A.9)이 지난 행은 보내지 않고 끝낸다 — 발화 기록과 배지는 그대로다(스펙 §9.3 "발송 실패는 발화를 취소하지 않는다"와 같은 원리).

## A.4 평가 시점 고르기

평가기는 주기마다 만료 전이를 먼저 하고(A.7), `ACTIVE`이고 삭제되지 않은 알림을 하나씩 본다. 알림마다 평가할 시점 목록을 고르고 앞에서부터 평가·반영한다.

| 알림 | `evaluated_as_of`가 비었을 때 | 이미 감시 중일 때 |
|---|---|---|
| 종가 · 시장 지표 | 기다리는 종류(§5.4)마다 최신 `DONE` 거래일을 구하고 그중 가장 이른 날 하나(`latestCloseDate`, 미리보기와 같은 규칙) | `evaluated_as_of`의 다음 거래일부터 그날까지의 거래일 전부, 날짜 순서 |
| 종가 · 사용자 상태 지표 | `snapshot_run`의 최신 `as_of` 하나 | 다음 국내 거래일부터 최신 `as_of`까지의 국내 거래일 전부. `snapshot_run` 행이 없는 날은 `PORTFOLIO_SNAPSHOT`이 `DONE`이 아닌 것으로 평가한다(→ `DATA_MISSING`) |
| 장중 | 그 시장의 최신 `INTRADAY_QUOTE` `DONE` 하나. 지금보다 허용 지연(국내 10분 · 미국 20분)을 넘게 오래됐으면 평가하지 않는다 | 같다. 그 시점이 `evaluated_as_of`보다 늦을 때만 |

- 따라잡기 사이의 거래일 D에 어떤 종류가 `DONE`이 아니어도 평가한다. 그 종류의 최신 `DONE`이 D보다 뒤이므로 D의 데이터는 오지 않는 것으로 본다(스펙 §7.1). 그 종류에 기대는 조건이 `DATA_MISSING`이 된다.
- 한 주기에 한 알림이 평가하는 시점은 최대 20개다(`EvaluationRunner.CATCH_UP_PER_TICK`). 나머지는 다음 주기에 이어진다. 날짜 순서는 주기를 넘어서도 지켜진다 — 다음 주기는 앞 주기가 반영한 `evaluated_as_of`에서 시작한다.
- 종목 마스터에 종목이 없으면 시장을 KR로 보고 시점을 고른 뒤 `UNKNOWN(INSTRUMENT_UNKNOWN)`을 기록한다. 카드가 `확인 불가 · 종목 정보 없음`을 보이게 하기 위해서다. 시장을 알 수 없으므로 미국 종목의 장중 알림은 국내 장 시간에만 이 사유가 기록된다.
- 같은 주기 안에서 (종목, 평가 시점, 기다리는 종류, 데이터 시점, 사용자 상태면 사용자)가 같은 입력은 한 번만 읽는다(스펙 §8.1 "대상 종목의 이력을 한 번씩 읽고").
- 저장된 조건을 읽을 수 없으면(`StoredTriggers.compile`이 빈 값) 그 알림을 건너뛰고 `alert_id`만 경고 로그에 남긴다. 상태는 바꾸지 않는다.
- 만료 전이(A.7)가 실패해도 그 주기의 평가는 이어간다. 실패는 경고 로그로 남고 다음 주기에 다시 옮긴다.
- 미리보기의 장중 기준은 평가기와 같은 시점이다 — 시장의 최신 `INTRADAY_QUOTE` `DONE`이 허용 지연 안이고 그 시각에 그 종목의 스냅샷이 있을 때만 장중 기준이고, 아니면 ① A.5의 종가 기준이다. 종가 기준으로 보이는 경우 평가기는 그 시각에서 `NO_TRADE`를 기록할 수 있다 — 미리보기의 종가 기준은 "지금 볼 수 있는 가장 최근 값"을 보여 주는 표시이고, 두 시점이 다르다.

## A.5 반영 조건

스펙 §8.2 ①의 조건부 갱신을 이렇게 쓴다.

```sql
UPDATE alert_state
   SET last_result = :result, last_known_result = :known, unknown_reason = :reason,
       evaluated_as_of = :as_of, spec_hash = :hash
 WHERE alert_id = :id
   AND version = :version
   AND evaluated_as_of IS NOT DISTINCT FROM :prev
   AND (evaluated_as_of IS NULL OR evaluated_as_of < :as_of)
   AND EXISTS (SELECT 1 FROM alert a WHERE a.alert_id = alert_state.alert_id
                 AND (a.expires_at IS NULL OR a.expires_at > :now))
```

- `:version`은 알림 규칙과 같은 SELECT에서 읽은 값이다(스펙 §14.4).
- `:prev`는 평가기가 이 시점을 고를 때 본 `evaluated_as_of`다(따라잡기면 바로 앞 시점). 스펙의 `evaluated_as_of < :as_of`에 더해 이 조건을 거는 것은, 같은 알림을 두 복제본이 따라잡을 때 늦은 쪽이 낡은 엣지 기준으로 뒤 시점을 반영하지 못하게 하기 위해서다. 스펙의 조건을 모두 포함하므로 스펙이 허용하지 않는 반영은 없다.
- 마지막 조건은 주기 도중에 유효기간이 지난 알림을 반영하지 않기 위해서다 — 만료는 실제 시각으로 판정한다(스펙 §3.3). 다음 주기의 만료 전이가 그 알림을 옮긴다.
- `:hash`는 지금 코드의 해시다. 단, 해시가 다르고 결과가 `UNKNOWN`이면 상태의 해시를 그대로 둔다(A.6).
- 갱신된 행이 0이면 그 알림의 이번 주기를 멈춘다(`Outcome.LOST`). 다음 주기가 새 상태에서 다시 시작한다.

## A.6 발화 판정

| 경우 | 발화 | 새 엣지 기준 |
|---|---|---|
| 결과 `UNKNOWN` | 아니다 | 그대로 |
| 조건 해시 ≠ 상태의 해시 (스펙 §6.6), 결과 `TRUE`·`FALSE` | 아니다 | 이번 결과. 상태의 해시를 새 해시로 바꾼다 |
| 조건 해시 ≠ 상태의 해시, 결과 `UNKNOWN` | 아니다 | 그대로. 상태의 해시도 그대로 둔다 — 확정 결과가 나오는 평가에서 기준과 해시를 함께 바꾼다 |
| `EDGE_REARM` · `ONE_SHOT`, 결과 `TRUE` | 엣지 기준이 `FALSE`일 때 | `TRUE` |
| `COOLDOWN`, 결과 `TRUE` | 엣지 기준이 `FALSE`이거나, 마지막 발화의 `as_of` + `cooldown_min`분 ≤ 이번 `as_of` | `TRUE` |
| 결과 `FALSE` | 아니다 | `FALSE` |

- 쿨다운의 경계: 마지막 발화의 `as_of` + N분과 이번 `as_of`가 같으면 울린다("N분이 지남"에 그 순간을 넣는다).
- 쿨다운에서 엣지 기준이 `TRUE`인데 발화 기록이 없으면(해시 재기준으로 `TRUE`가 된 직후) 울리지 않는다. "마지막 발화부터 N분"의 기준이 없기 때문이다. 다음에 거짓으로 내려갔다 참이 되면 울린다.
- 발화하면 같은 트랜잭션에서 `alert_event`를 `ON CONFLICT ON CONSTRAINT alert_event_once_per_point DO NOTHING`으로 넣는다. 들어가지 않았으면(같은 시점이 이미 울림, 스펙 §8.2 ②) 발송 행을 만들지 않고 `ONE_SHOT`도 끝내지 않는다 — 상태 반영만 남는다.
- `ONE_SHOT`이 울리면 같은 트랜잭션에서 `status = 'ENDED'`, `version + 1`, 대상 종목 갱신을 한다. 버전을 올리는 것은 다른 복제본이 같은 알림의 뒤 시점을 반영하지 못하게 하기 위해서다.
- **잠금 순서는 모든 트랜잭션이 `alert` → `alert_state` → 대상 종목 advisory lock이다.** 사용자 변경(①의 `AlertCommandService`)과 만료가 이 순서다. 평가 반영은 `alert` 행을 바꾸지 않으면 `alert_state`부터 잠가도 겹칠 일이 없지만, `ONE_SHOT`은 끝낼 때 `alert`를 바꾸므로 반영 전에 `SELECT … FROM alert … FOR NO KEY UPDATE`로 `alert` 행을 먼저 잡는다. 그러지 않으면 끄기·삭제·수정·만료와 교착한다.

## A.7 만료

- 주기마다 평가보다 먼저, 실제 시각으로 판정한다(스펙 §3.3). `status IN ('ACTIVE','PAUSED') AND deleted_at IS NULL AND expires_at <= now`인 알림을 한 트랜잭션에서 `EXPIRED`로 옮기고 `version + 1`, 대상 종목을 갱신한다. `UPDATE … RETURNING`이라 두 복제본이 동시에 돌아도 한 알림은 한쪽만 옮긴다.
- 만료된 알림은 그 주기의 평가 대상(`ACTIVE`)에 들지 않으므로 밀린 거래일도 평가하지 않는다. 주기 도중에 유효기간이 지난 알림은 반영 조건(A.5)이 막는다.

## A.8 발화 기록

| 필드 | 값 |
|---|---|
| `title` | 프리셋: `종목명 · 프리셋 라벨`, 조립형: `종목명 · 알림 이름` (스펙 §6.9). 파라미터로 갈래를 고른 프리셋은 고른 갈래의 이름을 라벨로 쓴다(아래 표) — 스펙 §6.9의 예시 `카카오 · RSI 과매수`와 같다 |
| `lines` | `SentenceWriter.lines`의 문장 배열(JSON 문자열 배열) — 미리보기의 현재값 상자와 같은 줄이다 |
| `body` | `lines`를 ` · `로 잇고 ` · ` + `SentenceWriter.asOfLabel`을 붙인다. 예: `현재가 70,200원 ≥ 70,000원 · 10:15 기준` · `RSI(14) 71.3 ≥ 70 · 3일째 · 9/26 종가 기준` |
| `observed` | `{ "conditions": [ { "left": 70200, "right": 70000, "progress": null } ] }` — 조건마다 판정에 쓴 양쪽 값과 진행 상황. 숫자는 꼬리 0을 뗀다(DB `numeric(20,4)`의 `63010.0000` → `63010`). 계산할 수 없던 값은 `null`. 스펙 §10.1 · §11.3의 `{ "price", "threshold" }`는 예시이고 이 모양이 계약이다 — 계획 ③(앱)에 넘긴다 |
| `as_of` | 평가한 데이터 시점(종가는 `close_at`, 장중은 `snapshot_at`) |
| `fired_at` | 반영 트랜잭션의 지금 시각 |

| 프리셋 | 갈래 | 제목의 라벨 |
|---|---|---|
| `rsi_zone` | `zone` | `RSI 과매수` · `RSI 과매도` |
| `ma_cross` | `direction` | `골든크로스` · `데드크로스` |
| `box_breakout` | `direction` | `박스권 상단 돌파` · `박스권 하단 이탈` |
| `change_move` | `direction` | `급등` · `급락` |
| `investor_streak` | `investor` · `side` | `외국인 연속 순매수` · `기관 연속 순매도` 등 |
| `investor_turn` | `investor` · `side` | `외국인 순매수 전환` · `기관 순매도 전환` 등 |
| `price_reach` · `volume_surge` · `pnl_reach` | — | 카탈로그 라벨 그대로 (`가격 도달` · `거래량 급증` · `수익률 도달`) |

## A.9 발송

**대상 기기**: 발화한 알림의 사용자의 `platform = 'IOS'` 기기 전부. 기기가 없으면 발송 행이 없다(스펙 §9.5 · §9.6).

**페이로드**: `{ "to", "title", "body", "sound": "default", "data": { "event_id" } }`. `sound`는 iOS에서 기본 알림음을 울리게 한다(스펙 §9.3의 페이로드에 더한 필드).

**Expo 사실** (docs.expo.dev "Sending notifications with Expo's Push API", 2026-10-11 확인)

| 항목 | 값 |
|---|---|
| 전송 | `POST https://exp.host/--/api/v2/push/send`, 요청당 최대 100건, 응답 `data[]`가 요청 순서대로 티켓 |
| 영수증 | `POST https://exp.host/--/api/v2/push/getReceipts` `{ "ids": [...] }`, 요청당 최대 1000건, 응답 `data`가 티켓 id → 영수증 |
| 영수증 시점 | 보낸 뒤 15분에 묻기를 권장, 24시간 뒤 지워진다 |
| 접근 토큰 | 프로젝트에 향상된 보안을 켰을 때만 필요. `Authorization: Bearer <token>` |
| 오류 | `DeviceNotRegistered`(그 토큰으로 더 보내지 않는다) · `MessageTooBig` · `MessageRateExceeded`(지수 백오프로 재시도) · `MismatchSenderId` · `InvalidCredentials`. HTTP 429 · 5xx는 재시도, 그 밖의 4xx는 재시도하지 않는다 |

**발송 행의 상태** — 스펙 §10.1의 `PENDING` · `SENT` · `FAILED`에 `SENDING`을, 컬럼에 `sent_at`을 더한다(A.14).

| state | `next_attempt_at`의 뜻 | 들어오는 경로 |
|---|---|---|
| `PENDING` | 다음 전송 시각 | 발화(평가 트랜잭션), 재시도 |
| `SENDING` | 임대가 끝나는 시각(집은 시각 + 2분) | 발송기가 집음 |
| `SENT` | 영수증을 물을 시각(`sent_at` + 15분, 아직 없으면 15분씩 미룸) | 티켓 `ok` |
| `FAILED` | — | 아래 표 |

**발송기 한 번** — Expo 호출을 DB 트랜잭션 밖에서 한다. 보낸 뒤 커밋이 실패해 묶음 전체가 다시 나가는 일을 막고, Expo가 느려도 행 잠금과 DB 연결을 쥐고 있지 않기 위해서다.

1. **집기 트랜잭션**
   - 기한이 지난 대기 행을 끝낸다: `PENDING`·`SENDING`이고 발화 `fired_at`부터 장중 알림은 30분, 종가 알림은 12시간이 지났으면 `FAILED`(`EXPIRED`). 지난 시각의 장중 값이 지금 가격으로 오해되지 않게 하기 위해서다(스펙 §3.3과 같은 이유). 푸시가 꺼져 있던 동안이나 장애 동안 쌓인 행도 여기서 끝난다. 발화 기록과 배지는 남는다.
   - 소유자가 바뀐 행을 끝낸다: 기기의 지금 사용자(`push_device.user_id`)가 발화한 알림의 사용자와 다르면 `FAILED`(`OWNER_CHANGED`). 같은 토큰을 다른 사용자가 등록하면 기기가 그 사용자로 옮겨지기 때문이다(스펙 §9.2 · §14.5).
   - 임대가 끝났는데 시도 횟수를 다 쓴 `SENDING`을 끝낸다: `FAILED`(`LEASE_EXPIRED`).
   - `PENDING`이거나 임대가 끝난 `SENDING`이고, `next_attempt_at <= now`, 시도 횟수가 남은 행을 `next_attempt_at` 순으로 100건 `FOR UPDATE OF d SKIP LOCKED`로 집는다(스펙 §8.2 ④). 기기의 사용자와 알림의 사용자가 같은 행만 집는다.
   - 집은 행을 `SENDING`, `attempts + 1`, `next_attempt_at` = 지금 + 2분으로 바꾸고 커밋한다.
2. **전송** — 트랜잭션 밖에서 Expo로 보낸다. 시간 제한은 연결 5초, 읽기 15초다(`spring.http.client.connect-timeout` · `read-timeout`).
3. **기록 트랜잭션** — 행마다 "아직 `SENDING`이고 `attempts`가 집을 때 쓴 값 그대로"일 때만 쓴다. 그 사이 로그아웃으로 행이 지워졌거나 다른 복제본이 다시 집었으면 건드리지 않는다.

| 결과 | 처리 |
|---|---|
| 티켓 `ok` | `SENT`, `expo_ticket_id` = 티켓 id, `sent_at` = 지금, `next_attempt_at` = 지금 + 15분 |
| 티켓 `DeviceNotRegistered` | `FAILED`(`DeviceNotRegistered`), 그 기기를 지울 목록에 넣는다 |
| 티켓 `MessageRateExceeded`, HTTP 429 · 5xx · 연결 실패 · 시간 초과 | 시도 횟수가 남았으면 `PENDING`, `next_attempt_at` = 지금 + 30초 × 2^(attempts − 1) (30초 · 1분 · 2분 · 4분). 5번째 시도였으면 `FAILED` |
| 그 밖의 티켓 오류, 그 밖의 4xx, 티켓 수가 메시지 수와 다름 | `FAILED`, `last_error` = 오류 코드 |

4. **기기 정리** — 기록 트랜잭션이 커밋된 뒤, 지울 기기를 하나씩 따로 지운다(문장 하나가 곧 트랜잭션). 발송 행은 `ON DELETE CASCADE`로 함께 지워진다. 결과 기록과 기기 삭제를 한 트랜잭션에 두면 발송기와 영수증 확인기가 같은 기기를 지우다 교착할 수 있다.

- 요청 자체가 실패하면(HTTP 429 · 5xx · 연결 실패) 그 묶음을 위 표대로 쓰고 0을 돌려준다. 스케줄 작업이 "100건이 꽉 차면 이어서 보내기"를 멈춘다 — 장애 중에 대기열 전체의 시도 횟수를 한 번에 쓰지 않게 하기 위해서다.
- 기록 트랜잭션은 일시적인 잠금·교착 실패면 3번까지 다시 실행한다. 기록 갱신이 모두 "아직 `SENDING`이고 집을 때의 `attempts` 그대로" 조건을 걸어 같은 내용을 두 번 써도 결과가 같다.
- 같은 푸시가 두 번 갈 수 있는 경우: Expo가 받았는데 결과를 기록하지 못했을 때(파드가 죽었거나 기록 트랜잭션이 끝내 실패 — 임대가 끝난 뒤 다시 집힌다), 그리고 Expo가 받은 뒤 읽기 시간 초과가 났을 때(재시도 간격 뒤 다시 보낸다).
- 다른 발송기가 임대 중인 `SENDING` 행은 기한 만료·소유자 변경 정리에서 건드리지 않는다. 그 발송기의 기록이 결과를 쓴다.
- 묶음의 티켓 중 하나라도 `MessageRateExceeded`면 요청 실패와 같이 0을 돌려준다.
- `last_error`에는 Expo 오류 코드나 `HTTP 503` 같은 짧은 사유만 넣는다. 토큰이나 응답 본문을 넣지 않는다.

**영수증 확인기**: `SENT`이고 `expo_ticket_id`가 있고 `next_attempt_at <= now`인 행을 1000건 읽는다(잠그지 않는다 — 두 복제본이 같은 티켓을 물어도 결과 기록이 같다). 트랜잭션 밖에서 묻고, 결과를 한 트랜잭션에 쓰고, 커밋 뒤 기기를 지운다.

| 영수증 | 처리 |
|---|---|
| `ok` | `expo_ticket_id`를 비운다 |
| `DeviceNotRegistered` | `FAILED`(`DeviceNotRegistered`), `expo_ticket_id`를 비우고 그 기기를 지울 목록에 넣는다 |
| 그 밖의 오류 | `FAILED`, `last_error` = 오류 코드, `expo_ticket_id`를 비운다 |
| 아직 없음 | `sent_at` + 24시간이 지났으면 `expo_ticket_id`를 비운다(영수증이 지워졌다). 아니면 `next_attempt_at` = 지금 + 15분 |
| 조회 자체가 실패 | 아무것도 바꾸지 않는다. 다음 주기에 다시 묻는다 |

## A.10 `snapshot_run`

- 포트폴리오 EOD 스냅샷 생성이 그 `as_of`의 전 계좌를 마친 뒤 `SnapshotRunRecorder.record(asOf)`를 부른다(스펙 §7.1 · 포트폴리오 스펙 §3.6). 같은 날을 다시 부르면 첫 기록이 남는다(`ON CONFLICT DO NOTHING`).
- 그 배치가 아직 없으므로 로컬·테스트는 `db/sample/sample_alert_market.sql`이 확정 스냅샷 날짜(2026-07-24)의 행을 넣는다.
- 미리보기는 계속 사용자의 최신 확정 스냅샷(`is_final`)을 본다(① A.5). `snapshot_run`은 평가기의 신호다.

## A.11 울린 알림 API

| 항목 | 정한 것 |
|---|---|
| 정렬 | `as_of` 내림차순, 같으면 `event_id` 내림차순 — 커서가 두 값을 함께 비교하므로 둘 다 내림차순이다. ①의 `unread` · `recent_events`는 같은 `as_of` 안에서 `event_id` 오름차순인데, 같은 시점의 여러 발화 사이 순서만 다르다 |
| `limit` | 기본 20, 1 ~ 50. 밖이면 `400 INVALID_PARAMETER` |
| `cursor` | 마지막 행의 `as_of`와 `event_id`를 `<ISO 시각>|<uuid>`로 이어 base64url(패딩 없음)로 쓴 불투명 문자열. 해석할 수 없으면 `400 INVALID_PARAMETER` |
| `alert_id` | 그 알림의 발화만. 남의 알림이거나 없는 알림이면 `404 ALERT_NOT_FOUND`(스펙 §11.4와 같은 규칙). 삭제된 내 알림은 찾은 것으로 보고 그 발화를 보여 준다(§6.8). 형식이 틀리면 `400 INVALID_PARAMETER` |
| 봉투 | `as_of`는 `GET /alerts`와 같다(이 사용자의 최신 `evaluated_as_of`). `empty_reason`은 첫 쪽이 비었을 때 `NO_EVENTS`. `notices`는 A.12의 지연 안내 |
| `POST /alert-events/{id}/read` | `204`. 이미 읽었으면 처음 읽은 시각을 유지한다. 남의 것·없는 것은 `404 EVENT_NOT_FOUND` |
| `POST /alert-events/read-all` | `204`. 이 사용자의 미확인 발화 전부 |
| 상세의 `alert` | 삭제된 알림도 채운다(`deleted: true`) — 스펙 §6.8 |

## A.12 `MARKET_DATA_DELAYED` · ①이 넘긴 것

**지연 판정** — 사용자의 `ACTIVE`이고 삭제되지 않은 알림이 기다리는 (시장, 종류)마다 본다. `PORTFOLIO_SNAPSHOT`은 시장 데이터가 아니라 보지 않는다.

| 종류 | 기대 시각 | 지연 |
|---|---|---|
| `INTRADAY_QUOTE` | 오늘(시장 현지)이 거래일이고 지금이 `open_at` ~ `close_at` 사이일 때만 본다. 기준 = 마지막 `DONE`(오늘 `open_at` 이후일 때) 또는 `open_at`. 기대 시각 = 기준 + 허용 지연 | 지금 > 기대 시각 |
| `DAILY_BAR` (KR) | 거래일 D의 다음 날 00:00 KST (스펙 §16.2 "장 마감 후 당일 중") | 기대 시각이 지난 가장 최근 거래일 D에 대해, 최신 `DONE` 거래일 < D |
| `DAILY_BAR` (US) | 다음 미국 거래일의 `open_at` | 같다 |
| `DAILY_FLOW` (KR) | 다음 국내 거래일의 `open_at` | 같다 |

캘린더에 행이 없으면 월~금을 거래일로, 개장·마감을 KR 09:00 ~ 15:30 · US 09:30 ~ 16:00 현지 시각으로 본다(① A.6의 평일 근사와 같다).

| 종류 | `message` (마지막 `DONE`이 있을 때 / 없거나 오늘 개장 전일 때) |
|---|---|
| `INTRADAY_QUOTE` | `국내 장중 시세가 10:05 이후 들어오지 않았어요` / `국내 장중 시세가 아직 들어오지 않았어요` (미국은 `미국`, 시각은 한국 시간) |
| `DAILY_BAR` | `국내 일봉이 9/25 이후 들어오지 않았어요` / `국내 일봉이 아직 들어오지 않았어요` (날짜는 그 시장의 거래일) |
| `DAILY_FLOW` | `국내 수급이 9/25 이후 들어오지 않았어요` / `국내 수급이 아직 들어오지 않았어요` |

`severity`는 `warn`, `params`는 `{ "market", "kind", "last_done" }`(`last_done`은 한국 시간 오프셋의 시각, 없으면 `null`). 순서는 KR → US, 그 안에서 `INTRADAY_QUOTE` → `DAILY_BAR` → `DAILY_FLOW`.

**①이 넘긴 것**

| # | 넘긴 것 | 처리 | 태스크 |
|---|---|---|---|
| 1 | 장중 교차에서 같은 날 직전 스냅샷이 없을 때의 사유 | `DATA_MISSING`. 직전 스냅샷과의 간격이 허용 지연을 넘을 때도 같다(N분 지속과 같은 규칙). 장중 기준(`basis = INTRADAY`)일 때만 보고, 미리보기의 종가 기준에는 ①의 동작(`INSUFFICIENT_HISTORY`)이 남는다 | 2 |
| 2 | 분모가 0이라 계산할 수 없는 값 | `NO_TRADE`. 계산기가 "봉이 모자람"(`null`)과 "값이 정의되지 않음"(`IndicatorCalculator.Undefined`)을 구분한다 | 2 |
| 3 | 장중 기준의 이력 봉이 누락일 필터를 거치지 않음 | 장중 이력도 종가와 같은 `historyBars`로 누락일을 뺀다. 미리보기와 평가기가 같은 `intradayAt`을 쓴다 | 5 · 8 |
| 4 | 저장된 조건 하나가 깨지면 `GET /alerts` 전체가 실패 | `StoredTriggers.compile`이 빈 값을 돌려주고, 목록·상세는 `조건을 읽을 수 없어요` 문장으로, 평가기는 건너뛴다 | 5 · 7 · 13 |
| — | 미리보기와 평가기가 같은 입력으로 같은 결과를 낸다 | 동등성 테스트 | 8 |

## A.13 실행자가 하지 않는 것

- DB·서버를 띄우지 않는다. 테스트가 DB를 요구하면 사람에게 `docker compose up -d db`와 `portfolio_alert_test` 데이터베이스 준비를 요청하고 기다린다.
- 운영 클러스터·k8s에 적용하지 않는다. `k8s/deployment.yaml`은 파일만 고치고, 푸시는 `EXPO_PUSH_ENABLED: "false"`로 둔다. 운영에서 켜는 것(Secret 생성, 값을 `true`로, 클러스터에서 `exp.host`로 나가는 통신 확인)은 사람이 한다.
- 실제 Expo 서버로 보내지 않는다. 테스트는 가짜 게이트웨이와 `MockRestServiceServer`만 쓴다.
- 스펙·데이터 요구사항·앱 정보 구조 문서를 고치지 않는다.
- 병합하지 않는다. 브랜치를 푸시하거나 PR을 만드는 것도 사람에게 묻는다.

## A.14 스펙과 다르거나 스펙 밖에서 정한 것

| 정한 것 | 스펙과의 관계 | 근거 |
|---|---|---|
| `alert_delivery.state`에 `SENDING`, 컬럼 `sent_at` | §10.1 표에 없는 값·컬럼을 더한다 | Expo 호출을 트랜잭션 밖으로 빼려면 집은 상태가 필요하다. 영수증 보관 기간은 보낸 시각부터다(A.9) |
| 발송 기한(장중 30분 · 종가 12시간) | §9.3이 정하지 않은 운영값 | 지난 시각의 값이 지금 값으로 오해되지 않게 한다(§3.3과 같은 이유) |
| 발송 행을 `platform = 'IOS'`로만 만든다 | §9.6은 "개발 빌드로 바꾸면 서버 변경 없이 Android가 열린다"고 한다 — 이 필터가 있으면 `insertDeliveries`의 조건 한 줄을 바꿔야 한다 | v1 범위를 iOS로 정했다. Android 토큰이 잘못 등록돼도 발송하지 않는다 |
| 롤링 배포 중 옛 파드와 새 파드가 함께 돌면 해시 재기준이 오갈 수 있다 | §6.6은 배포 뒤 한 번의 재기준을 뜻한다 | 템플릿·업캐스팅을 바꾸는 배포가 드물다. 그런 배포는 공존 시간 동안 엣지를 놓칠 수 있음을 감수한다. 잦아지면 상태에 평가기 코드 버전을 함께 두고 낮은 버전이 반영하지 않게 한다 |
| 장중 허용 지연 판정에 여유를 두지 않는다 | §3.3 · §16.2 그대로 | 데이터가 허용 지연 끝 무렵에 도착하면 평가 주기(1분) 안에 버려질 수 있다. 장중 평가는 종목 스냅샷 시각과 신호 `as_of`가 같다는 데이터 요구사항 N3(미결)에 기댄다 |
| 미리보기의 장중 기준이 없을 때 종가로 대신 보여 준다 | ① A.5 그대로 | A.4의 마지막 글머리 |

---

# 태스크

## 파일 구조

```
src/main/java/com/stockproject/portfolio/alert/
  indicator/IndicatorCalculator.java            (수정) 분모 0 → Undefined                Task 2
  evaluation/ConditionEvaluator.java            (수정) Undefined → NO_TRADE, 장중 교차    Task 2
  evaluation/FiringRule · FiringDecision                                                  Task 3
  sentence/EventText                                                                      Task 4
  data/EvaluationInputFactory.java              (수정) 시점 하나의 입력                   Task 5
  data/SnapshotRunMapper                                                                  Task 5
  data/CalendarDay · MarketDataMapper · MarketDataRepository (수정) 개장 시각·다음 거래일  Task 13
  validation/StoredTriggers                                                               Task 5
  service/SnapshotRunRecorder                                                             Task 5
  store/RuntimeMapper · RuntimeAlertRow · ExpiredAlert · AlertRuntimeStore                Task 6
  runtime/Target · Outcome · Applied · AlertRuntimeWriter                                 Task 6
  runtime/Point · EvaluationRunner                                                        Task 7
  delivery/PushProperties · PushMessage · PushTicket · PushReceipt · PushFailure ·
           PushGateway · ExpoPushGateway                                                  Task 9
  store/DeliveryMapper · PendingDelivery · SentDelivery                                   Task 10
  delivery/DeliveryDispatcher · ReceiptChecker                                            Task 10
  runtime/AlertRuntimeConfig · AlertJobs                                                  Task 11
  store/AlertEventMapper · EventListRow · EventDetailRow                                  Task 12
  service/EventCursor · AlertEventService                                                 Task 12
  api/AlertEventController · dto/EventListData · EventRowDto · EventDetailDto ·
      EventAlertDto · EventInstrumentDto · UnreadCountDto                                 Task 12
  store/AlertQueryMapper.java                   (수정) 활성 알림의 조건                   Task 13
  service/MarketDelayNotices · AlertQueryService (수정)                                   Task 13
  auth/LocalCorsConfig.java                     (수정) /alert-events                      Task 14
src/main/resources/
  db/migration/V6__alert_runtime.sql                                                      Task 1
  db/sample/sample_alert_market.sql             (수정)                                    Task 1
  application.yaml                              (수정)                                    Task 11
src/test/resources/application-test.yaml        (수정)                                    Task 11
src/test/java/com/stockproject/portfolio/
  alert/AlertSchemaTest.java                    (수정)                                    Task 1
  alert/indicator/IndicatorCalculatorTest · alert/evaluation/ConditionEvaluatorTest (수정) Task 2
  alert/evaluation/FiringRuleTest                                                         Task 3
  alert/sentence/EventTextTest                                                            Task 4
  alert/data/EvaluationInputFactoryTest (수정) · alert/data/SnapshotRunRecorderTest ·
  alert/validation/StoredTriggersTest                                                     Task 5
  alert/runtime/RuntimeFixtures · AlertRuntimeWriterTest                                  Task 6
  alert/runtime/EvaluationRunnerTest                                                      Task 7
  alert/runtime/PreviewEvaluatorParityTest                                                Task 8
  alert/delivery/ExpoPushGatewayTest                                                      Task 9
  alert/delivery/FakePushGateway · DeliveryFixtures · DeliveryDispatcherTest ·
                 ReceiptCheckerTest                                                       Task 10
  alert/runtime/AlertRuntimeConfigTest · alert/delivery/HttpClientTimeoutTest             Task 11
  alert/api/AlertEventApiTest                                                             Task 12
  alert/api/MarketDelayApiTest · alert/api/AlertQueryApiTest (수정)                       Task 13
  alert/api/AlertRuntimeFlowTest · ArchitectureRulesTest (수정) · auth/LocalCorsTest (수정) Task 14
k8s/deployment.yaml                                                                       Task 11
docs/decisions.md                                                                         Task 14
```

매퍼는 ①과 같이 모두 어노테이션(`@Select` 등)으로 쓴다. 동적 SQL이 필요한 자리는 `#{x}::type IS NULL OR …`로 쓴다(①의 `duplicateOf`와 같은 방식).

---
## Task 1: 발송 행과 보유 스냅샷 신호 테이블

**Files:**
- Create: `src/main/resources/db/migration/V6__alert_runtime.sql`
- Modify: `src/main/resources/db/sample/sample_alert_market.sql`
- Modify: `src/test/java/com/stockproject/portfolio/alert/AlertSchemaTest.java`

**Interfaces:**
- Produces: 테이블 `app.alert_delivery(event_id, device_id, state, attempts, next_attempt_at, expo_ticket_id, sent_at, last_error)`(state는 `PENDING` · `SENDING` · `SENT` · `FAILED`, 부록 A.9) · `app.snapshot_run(as_of, finished_at)`. 샘플 SQL이 `snapshot_run`에 `2026-07-24`를 넣는다.

- [ ] **Step 1: 실패하는 스키마 테스트를 쓴다**

`AlertSchemaTest`에 메서드 셋을 더한다(클래스 안, 기존 `columnsOf(String schema, String table)` 도우미를 쓴다).

```java
    @Test
    void 발송_행과_보유_스냅샷_신호의_컬럼이_스펙과_같다() {
        assertThat(columnsOf("app", "alert_delivery")).containsExactly(
                "attempts", "device_id", "event_id", "expo_ticket_id", "last_error", "next_attempt_at", "sent_at",
                "state");
        assertThat(columnsOf("app", "snapshot_run")).containsExactly("as_of", "finished_at");
    }

    @Test
    void 기기를_지우면_그_기기의_발송_행도_지워진다() {
        List<String> fks = jdbc.sql("""
                SELECT pg_get_constraintdef(oid) FROM pg_constraint
                 WHERE conrelid = 'app.alert_delivery'::regclass AND contype = 'f'
                 ORDER BY 1
                """).query(String.class).list();
        assertThat(fks).containsExactly(
                "FOREIGN KEY (device_id) REFERENCES push_device(device_id) ON DELETE CASCADE",
                "FOREIGN KEY (event_id) REFERENCES alert_event(event_id)");
    }

    @Test
    void 발송_상태는_네_값뿐이다() {
        assertThatThrownBy(() -> jdbc.sql("""
                INSERT INTO alert_delivery (event_id, device_id, state, attempts, next_attempt_at)
                VALUES (gen_random_uuid(), gen_random_uuid(), 'QUEUED', 0, now())
                """).update()).hasMessageContaining("alert_delivery_state");
    }
```

`assertThatThrownBy`·`List` import가 없으면 더한다(`import static org.assertj.core.api.Assertions.assertThatThrownBy;` · `import java.util.List;`).

- [ ] **Step 2: 실패를 확인한다**

DB가 떠 있지 않으면 사람에게 `docker compose up -d db`를 요청하고 기다린다.

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.AlertSchemaTest'`
Expected: FAIL — `alert_delivery`의 컬럼 목록이 비어 있다.

- [ ] **Step 3: 마이그레이션을 쓴다**

`src/main/resources/db/migration/V6__alert_runtime.sql`:

```sql
-- 알림 평가 런타임과 전달의 백엔드 소유 테이블 (알림 스펙 §9 · §10.1).

-- 기기별 발송. 한 발화를 기기마다 보내고 기기마다 성공·실패가 갈린다.
-- 기기를 지우면 그 기기의 발송 행도 지운다 — 발화 기록은 alert_event에 남는다.
CREATE TABLE alert_delivery (
    event_id        uuid        NOT NULL REFERENCES alert_event (event_id),
    device_id       uuid        NOT NULL REFERENCES push_device (device_id) ON DELETE CASCADE,
    state           text        NOT NULL,
    attempts        integer     NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL,
    expo_ticket_id  text,
    sent_at         timestamptz,
    last_error      text,
    PRIMARY KEY (event_id, device_id),
    CONSTRAINT alert_delivery_state CHECK (state IN ('PENDING', 'SENDING', 'SENT', 'FAILED'))
);

CREATE INDEX idx_alert_delivery_pending ON alert_delivery (next_attempt_at) WHERE state IN ('PENDING', 'SENDING');
CREATE INDEX idx_alert_delivery_receipt ON alert_delivery (next_attempt_at)
    WHERE state = 'SENT' AND expo_ticket_id IS NOT NULL;
CREATE INDEX idx_alert_delivery_device ON alert_delivery (device_id);

COMMENT ON COLUMN alert_delivery.state IS
  'SENDING은 발송기가 집어 Expo로 보내는 중이다. Expo 호출을 트랜잭션 밖에서 하므로 집은 상태를 따로 둔다';
COMMENT ON COLUMN alert_delivery.next_attempt_at IS
  'PENDING이면 다음 전송 시각, SENDING이면 임대가 끝나는 시각, SENT이면 전달 영수증을 물을 시각이다';
COMMENT ON COLUMN alert_delivery.sent_at IS
  'Expo가 접수한 시각. 영수증 보관 기간(24시간)을 이 시각부터 잰다';
COMMENT ON COLUMN alert_delivery.expo_ticket_id IS
  '영수증을 물을 Expo 접수 티켓. 영수증을 받았거나 Expo의 보관 기간(24시간)이 지나면 비운다';
COMMENT ON COLUMN alert_delivery.last_error IS
  'Expo 오류 코드나 HTTP 상태 같은 짧은 사유. 푸시 토큰과 응답 본문을 넣지 않는다';

-- 보유 스냅샷 완료 신호. 사용자 상태 지표 알림의 평가 신호다.
CREATE TABLE snapshot_run (
    as_of       date        PRIMARY KEY,
    finished_at timestamptz NOT NULL
);

COMMENT ON TABLE snapshot_run IS
  '포트폴리오 EOD 스냅샷 생성이 그 as_of의 전 계좌를 마치면 한 행을 쓴다. 같은 날을 다시 쓰면 첫 기록이 남는다';

-- 울린 알림 목록과 쿨다운 판정이 알림별 최신 발화를 데이터 시점 순으로 읽는다.
CREATE INDEX idx_alert_event_alert_as_of ON alert_event (alert_id, as_of DESC);

-- 평가기가 주기마다 만료할 알림을 찾는다.
CREATE INDEX idx_alert_expiring ON alert (expires_at)
    WHERE status IN ('ACTIVE', 'PAUSED') AND deleted_at IS NULL AND expires_at IS NOT NULL;
```

- [ ] **Step 4: 샘플 SQL에 새 테이블을 넣는다**

`src/main/resources/db/sample/sample_alert_market.sql`의 `TRUNCATE` 문을 다음으로 바꾼다.

```sql
TRUNCATE alert_delivery, alert_event, alert_state, alert, push_device, alert_watchlist, snapshot_run,
         market_data_run, intraday_quote, investor_flow_daily, adjusted_price_daily, dim_market_calendar;
```

같은 파일의 `COMMIT;` 바로 앞에 붙인다.

```sql
-- 보유 스냅샷 완료 신호. sample_portfolio.sql의 확정 스냅샷(2026-07-24)이 전 계좌에 대해 끝났다.
INSERT INTO snapshot_run (as_of, finished_at) VALUES ('2026-07-24', '2026-07-24T18:00:00+09');
```

- [ ] **Step 5: 통과를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.AlertSchemaTest' --tests 'com.stockproject.portfolio.MigrationLintTest' --tests 'com.stockproject.portfolio.query.SchemaContractTest'`
Expected: PASS (3개 클래스 전부)

- [ ] **Step 6: 커밋한다**

```bash
git add src/main/resources/db/migration/V6__alert_runtime.sql \
        src/main/resources/db/sample/sample_alert_market.sql \
        src/test/java/com/stockproject/portfolio/alert/AlertSchemaTest.java
git commit -m "feat: 기기별 발송 행과 보유 스냅샷 신호 테이블을 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 계산 보강 — 분모 0은 거래 없음, 장중 교차의 직전 스냅샷

①이 넘긴 1 · 2(부록 A.12).

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/alert/indicator/IndicatorCalculator.java`
- Modify: `src/main/java/com/stockproject/portfolio/alert/evaluation/ConditionEvaluator.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/indicator/IndicatorCalculatorTest.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/evaluation/ConditionEvaluatorTest.java`

**Interfaces:**
- Produces: `IndicatorCalculator.Undefined` (public static final class, `RuntimeException`) — `IndicatorCalculator.value`가 분모 0을 만나면 던진다. `ConditionEvaluator.evaluate`는 이것을 `UNKNOWN(NO_TRADE)`로 옮긴다. 장중 교차의 직전 스냅샷이 없거나 멀면 `UNKNOWN(DATA_MISSING)`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`IndicatorCalculatorTest`에 더한다(`import static org.assertj.core.api.Assertions.assertThatThrownBy;`가 없으면 더한다).

```java
    /** 분모가 0이면 값이 정의되지 않는다 — 봉이 모자란 것(null)과 구분한다. */
    @Test
    void 분모가_0이면_값이_정의되지_않는다() {
        assertThatThrownBy(() -> value(new Operand(IndicatorKey.VOLUME_RATIO, Map.of("n", 2), ID),
                daily(volumes("0", "0", "100")), Cadence.CLOSE))
                .isInstanceOf(IndicatorCalculator.Undefined.class);
        assertThatThrownBy(() -> value(new Operand(IndicatorKey.VOLUME, Map.of(), new Transform.Pct(1)),
                daily(volumes("0", "100")), Cadence.CLOSE))
                .isInstanceOf(IndicatorCalculator.Undefined.class);
    }
```

`ConditionEvaluatorTest`에 더한다.

```java
    /** 분모가 0이면 거래 없음이다 — 실제로 생기는 경우는 거래량 0인 봉이다 (계획 ② A.12). */
    @Test
    void 분모가_0이면_거래_없음이다() {
        Condition ratio = gte(new Operand(IndicatorKey.VOLUME_RATIO, Map.of("n", 2), ID), "1", null);
        Condition growth = gte(new Operand(IndicatorKey.VOLUME, Map.of(), new Transform.Pct(1)), "10", null);

        assertThat(ConditionEvaluator.evaluate(ratio, close(volumes("0", "0", "100"), 2)).reason())
                .isEqualTo(UnknownReason.NO_TRADE);
        assertThat(ConditionEvaluator.evaluate(growth, close(volumes("0", "100"), 1)).reason())
                .isEqualTo(UnknownReason.NO_TRADE);
        assertThat(ConditionEvaluator.evaluate(ratio, close(volumes("100", "100", "300"), 2)).truth())
                .isEqualTo(Truth.TRUE);
    }

    /** 장중 교차는 같은 날 직전 스냅샷과 견준다. 없거나 허용 지연보다 멀면 데이터 없음이다 (§5.2, 계획 ② A.12). */
    @Test
    void 장중_교차의_직전_스냅샷이_없거나_멀면_데이터_없음이다() {
        Condition cross = new Condition(PRICE, OperatorKey.CROSSES_ABOVE,
                Right.operand(new Operand(IndicatorKey.SMA, Map.of("n", 2), ID)), null);
        Series first = new Series(closes("100", "100"), List.of(), List.of(snapshot("09:00", "105", "1")), null);
        Series far = new Series(closes("100", "100"), List.of(),
                List.of(snapshot("09:00", "95", "1"), snapshot("09:30", "105", "2")), null);
        Series near = new Series(closes("100", "100"), List.of(),
                List.of(snapshot("09:00", "95", "1"), snapshot("09:05", "105", "2")), null);

        assertThat(ConditionEvaluator.evaluate(cross, live(first, Market.KR)).reason())
                .isEqualTo(UnknownReason.DATA_MISSING);
        assertThat(ConditionEvaluator.evaluate(cross, live(far, Market.KR)).reason())
                .isEqualTo(UnknownReason.DATA_MISSING);
        assertThat(ConditionEvaluator.evaluate(cross, live(near, Market.KR)).truth()).isEqualTo(Truth.TRUE);
    }

    /** 미리보기가 종가를 스냅샷 하나로 대신 보여 줄 때(Basis.DAILY)는 이 검사를 하지 않는다 — ①의 이력 부족 그대로다. */
    @Test
    void 일봉_기준의_장중_교차는_직전_스냅샷을_따지지_않는다() {
        Condition cross = new Condition(PRICE, OperatorKey.CROSSES_ABOVE,
                Right.operand(new Operand(IndicatorKey.SMA, Map.of("n", 2), ID)), null);
        Series s = new Series(closes("100", "100"), List.of(), List.of(snapshot("15:30", "105", "1")), null);
        EvaluationInput in = input(Cadence.INTRADAY, Basis.DAILY, Market.KR, day(2), s, Set.of(), Set.of());

        assertThat(ConditionEvaluator.evaluate(cross, in).reason()).isEqualTo(UnknownReason.INSUFFICIENT_HISTORY);
    }
```

두 테스트 클래스는 `SeriesFixtures.*`를 이미 static import한다(`volumes` · `closes` · `snapshot` · `daily`). `Transform` · `Series` · `List` import가 없으면 더한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.indicator.IndicatorCalculatorTest' --tests 'com.stockproject.portfolio.alert.evaluation.ConditionEvaluatorTest'`
Expected: FAIL — `IndicatorCalculator.Undefined`가 없어 컴파일 오류.

(이 두 클래스는 DB를 쓰지 않아 `TEST_DB_URL` 없이 돈다.)

- [ ] **Step 3: 계산기가 분모 0을 구분하게 한다**

`IndicatorCalculator.java`에서:

클래스 Javadoc의 둘째 문단을 바꾼다.

```java
 * <p>계산할 봉이 모자라면 null을 돌려준다. 평가기가 INSUFFICIENT_HISTORY로 옮긴다.
 * 나눗셈의 분모가 0이면 Undefined를 던진다 — 값이 정의되지 않는다. 평가기가 NO_TRADE로 옮긴다
 * (실제로 생기는 경우는 거래량 0인 봉이다).</p>
```

클래스 안 맨 위(`private IndicatorCalculator() { }` 아래)에 더한다.

```java
    /** 분모가 0이라 값이 정의되지 않는다. 스택을 남기지 않는다 — 판정의 한 갈래이지 오류가 아니다. */
    public static final class Undefined extends RuntimeException {
        Undefined() { super(null, null, false, false); }
    }
```

`divide`를 바꾼다.

```java
    private static BigDecimal divide(BigDecimal a, BigDecimal b) {
        if (b == null) return null;
        if (b.signum() == 0) throw new Undefined();
        return a.divide(b, MC);
    }
```

- [ ] **Step 4: 평가기가 거래 없음과 장중 교차를 가린다**

`ConditionEvaluator.java`에서 `evaluate(Condition c, EvaluationInput in)`의 마지막 부분(`if (c.op().isCross()) return cross(c, in);`부터 `switch` 끝까지)을 바꾼다.

```java
        try {
            if (c.op().isCross()) return cross(c, in);
            return switch (c.modifier()) {
                case null -> plain(c, in);
                case Modifier.Streak s -> streak(c, s.n(), in);
                case Modifier.PersistMin p -> in.basis() == Basis.INTRADAY ? persist(c, p.minutes(), in) : plain(c, in);
            };
        } catch (IndicatorCalculator.Undefined e) {
            return ConditionResult.unknown(UnknownReason.NO_TRADE);
        }
```

`cross` 메서드 맨 앞에 더한다.

```java
        if (in.basis() == Basis.INTRADAY && !hasPreviousSnapshot(in)) {
            return ConditionResult.unknown(UnknownReason.DATA_MISSING);
        }
```

`cross` 아래에 도우미를 더한다.

```java
    /**
     * 장중 교차의 직전 시점은 같은 날 직전 스냅샷이다(§5.2). 없거나, 현재 스냅샷과의 간격이 허용 지연을
     * 넘으면 그 사이 값을 모른다 — N분 지속의 공백과 같은 규칙이다(§4.2). 장중 기준일 때만 본다.
     */
    private static boolean hasPreviousSnapshot(EvaluationInput in) {
        List<Snapshot> snaps = in.series().snapshots();
        if (snaps.size() < 2) return false;
        Snapshot current = snaps.get(snaps.size() - 1);
        Snapshot previous = snaps.get(snaps.size() - 2);
        return Duration.between(previous.at(), current.at()).compareTo(in.allowedGap()) <= 0;
    }
```

클래스 Javadoc의 문단을 바꾼다.

```java
 * <p>조건마다 확인 불가를 먼저 가린다 — 종목 없음, 기다리는 데이터가 DONE이 아님,
 * 현재 값의 부재(거래 없음·미보유·이월값), 연속·교차 구간의 데이터 누락일,
 * 국내 ±30% 변동. 그 뒤에 값을 계산한다. 계산할 봉이 모자라면 이력 부족, 분모가 0이면 거래 없음,
 * 장중 교차의 같은 날 직전 스냅샷이 없으면 데이터 없음이다.</p>
```

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.indicator.*' --tests 'com.stockproject.portfolio.alert.evaluation.*' --tests 'com.stockproject.portfolio.alert.sentence.*'`
Expected: PASS (기존 테스트 포함 전부)

- [ ] **Step 6: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/indicator/IndicatorCalculator.java \
        src/main/java/com/stockproject/portfolio/alert/evaluation/ConditionEvaluator.java \
        src/test/java/com/stockproject/portfolio/alert/indicator/IndicatorCalculatorTest.java \
        src/test/java/com/stockproject/portfolio/alert/evaluation/ConditionEvaluatorTest.java
git commit -m "fix: 분모가 0인 값은 거래 없음, 장중 교차의 직전 스냅샷이 없으면 데이터 없음으로 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 발화 판정 — 엣지 · 한 번만 · 쿨다운 · 해시 재기준

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/evaluation/FiringDecision.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/evaluation/FiringRule.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/evaluation/FiringRuleTest.java`

**Interfaces:**
- Consumes: `EvaluationResult(Truth truth, UnknownReason reason, OffsetDateTime asOf, Basis basis, List<ConditionResult> conditions)` · `NotifyMode`
- Produces: `FiringRule.decide(NotifyMode mode, Integer cooldownMin, Truth lastKnown, boolean hashMatches, EvaluationResult result, OffsetDateTime lastFiredAsOf) → FiringDecision(boolean fire, Truth lastKnown)`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/evaluation/FiringRuleTest.java`:

```java
package com.stockproject.portfolio.alert.evaluation;

import com.stockproject.portfolio.alert.catalog.NotifyMode;
import org.junit.jupiter.api.Test;

import java.time.OffsetDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** 발화 판정 (스펙 §6.2 · §6.6, 계획 ② A.6). */
class FiringRuleTest {

    private static final OffsetDateTime T0 = OffsetDateTime.parse("2026-09-28T10:00:00+09:00");

    @Test
    void 엣지_기준이_거짓이고_참이면_울린다() {
        for (NotifyMode mode : List.of(NotifyMode.EDGE_REARM, NotifyMode.ONE_SHOT)) {
            FiringDecision d = FiringRule.decide(mode, null, Truth.FALSE, true, result(Truth.TRUE, T0), null);
            assertThat(d.fire()).isTrue();
            assertThat(d.lastKnown()).isEqualTo(Truth.TRUE);
        }
    }

    @Test
    void 참이_이어지면_울리지_않는다() {
        FiringDecision d = FiringRule.decide(NotifyMode.EDGE_REARM, null, Truth.TRUE, true, result(Truth.TRUE, T0), null);
        assertThat(d.fire()).isFalse();
        assertThat(d.lastKnown()).isEqualTo(Truth.TRUE);
    }

    @Test
    void 거짓으로_내려가면_다음_참에_다시_울린다() {
        Truth known = Truth.FALSE;
        known = step(known, Truth.TRUE, true);
        known = step(known, Truth.FALSE, false);
        step(known, Truth.TRUE, true);
    }

    /** 참 → 확인 불가 → 참은 울리지 않고, 거짓 → 확인 불가 → 참은 울린다 (§6.2). */
    @Test
    void 확인_불가는_울리지_않고_기준도_바꾸지_않는다() {
        Truth known = step(Truth.TRUE, Truth.UNKNOWN, false);
        assertThat(known).isEqualTo(Truth.TRUE);
        step(known, Truth.TRUE, false);

        known = step(Truth.FALSE, Truth.UNKNOWN, false);
        assertThat(known).isEqualTo(Truth.FALSE);
        step(known, Truth.TRUE, true);
    }

    @Test
    void 쿨다운은_마지막_발화의_데이터_시점부터_N분이_지나면_다시_울린다() {
        OffsetDateTime lastFired = T0;
        assertThat(FiringRule.decide(NotifyMode.COOLDOWN, 30, Truth.TRUE, true,
                result(Truth.TRUE, T0.plusMinutes(25)), lastFired).fire()).isFalse();
        assertThat(FiringRule.decide(NotifyMode.COOLDOWN, 30, Truth.TRUE, true,
                result(Truth.TRUE, T0.plusMinutes(30)), lastFired).fire()).isTrue();
        assertThat(FiringRule.decide(NotifyMode.COOLDOWN, 30, Truth.FALSE, true,
                result(Truth.TRUE, T0.plusMinutes(5)), lastFired).fire()).isTrue();
    }

    @Test
    void 쿨다운에서_발화_기록이_없고_기준이_참이면_울리지_않는다() {
        assertThat(FiringRule.decide(NotifyMode.COOLDOWN, 30, Truth.TRUE, true,
                result(Truth.TRUE, T0), null).fire()).isFalse();
    }

    /** 템플릿·업캐스팅이 바뀐 배포 뒤에는 울리지 않고 이번 결과로 기준을 잡는다 (§6.6). */
    @Test
    void 해시가_다르면_울리지_않고_기준만_잡는다() {
        FiringDecision t = FiringRule.decide(NotifyMode.EDGE_REARM, null, Truth.FALSE, false, result(Truth.TRUE, T0), null);
        assertThat(t.fire()).isFalse();
        assertThat(t.lastKnown()).isEqualTo(Truth.TRUE);

        FiringDecision u = FiringRule.decide(NotifyMode.EDGE_REARM, null, Truth.FALSE, false, result(Truth.UNKNOWN, T0), null);
        assertThat(u.fire()).isFalse();
        assertThat(u.lastKnown()).isEqualTo(Truth.FALSE);
    }

    @Test
    void 엣지_기준은_참이나_거짓이어야_한다() {
        assertThatThrownBy(() -> FiringRule.decide(NotifyMode.EDGE_REARM, null, Truth.UNKNOWN, true,
                result(Truth.TRUE, T0), null)).isInstanceOf(IllegalArgumentException.class);
    }

    private static Truth step(Truth known, Truth now, boolean expectFire) {
        FiringDecision d = FiringRule.decide(NotifyMode.EDGE_REARM, null, known, true, result(now, T0), null);
        assertThat(d.fire()).as("%s → %s", known, now).isEqualTo(expectFire);
        return d.lastKnown();
    }

    private static EvaluationResult result(Truth truth, OffsetDateTime asOf) {
        UnknownReason reason = truth == Truth.UNKNOWN ? UnknownReason.DATA_MISSING : null;
        return new EvaluationResult(truth, reason, asOf, Basis.INTRADAY, List.of());
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.evaluation.FiringRuleTest'`
Expected: FAIL — `FiringRule`이 없어 컴파일 오류.

- [ ] **Step 3: 판정을 쓴다**

`src/main/java/com/stockproject/portfolio/alert/evaluation/FiringDecision.java`:

```java
package com.stockproject.portfolio.alert.evaluation;

/** 발화 판정의 결과. lastKnown은 반영할 새 엣지 기준(TRUE 또는 FALSE)이다. */
public record FiringDecision(boolean fire, Truth lastKnown) { }
```

`src/main/java/com/stockproject/portfolio/alert/evaluation/FiringRule.java`:

```java
package com.stockproject.portfolio.alert.evaluation;

import com.stockproject.portfolio.alert.catalog.NotifyMode;

import java.time.OffsetDateTime;

/**
 * 발화 판정 (스펙 §6.2 · §6.6, 계획 ② A.6).
 *
 * <p>확인 불가는 울리지 않고 엣지 기준도 바꾸지 않는다 — 데이터 공백이 재발화를 일으키지도 막지도 않는다.
 * 조건 해시가 상태의 해시와 다르면 템플릿·업캐스팅이 바뀐 배포 뒤다. 울리지 않고 이번 결과로 기준만 잡는다 —
 * 배포 한 번에 알림이 일제히 울리지 않게 하기 위해서다.</p>
 *
 * <p>쿨다운은 엣지 기준이 거짓이거나 마지막 발화의 데이터 시점부터 N분이 지났을 때 울린다.
 * 발화 기록이 없으면 "마지막 발화부터"의 기준이 없어 엣지로만 판정한다.</p>
 */
public final class FiringRule {

    private FiringRule() { }

    /**
     * @param lastKnown     지금 엣지 기준 — TRUE 또는 FALSE
     * @param hashMatches   이번에 컴파일한 조건의 해시가 상태의 해시와 같은가
     * @param lastFiredAsOf 그 알림의 마지막 발화 데이터 시점. 쿨다운에만 쓴다
     */
    public static FiringDecision decide(NotifyMode mode, Integer cooldownMin, Truth lastKnown, boolean hashMatches,
                                        EvaluationResult result, OffsetDateTime lastFiredAsOf) {
        if (lastKnown == Truth.UNKNOWN) throw new IllegalArgumentException("엣지 기준은 참이나 거짓이다");
        Truth known = result.truth() == Truth.UNKNOWN ? lastKnown : result.truth();
        if (!hashMatches || result.truth() != Truth.TRUE) return new FiringDecision(false, known);

        boolean edge = lastKnown == Truth.FALSE;
        boolean fire = switch (mode) {
            case EDGE_REARM, ONE_SHOT -> edge;
            case COOLDOWN -> edge || cooledDown(cooldownMin, result.asOf(), lastFiredAsOf);
        };
        return new FiringDecision(fire, known);
    }

    private static boolean cooledDown(Integer cooldownMin, OffsetDateTime asOf, OffsetDateTime lastFiredAsOf) {
        if (cooldownMin == null || lastFiredAsOf == null) return false;
        return !asOf.isBefore(lastFiredAsOf.plusMinutes(cooldownMin));
    }
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.evaluation.FiringRuleTest'`
Expected: PASS

- [ ] **Step 5: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/evaluation/FiringDecision.java \
        src/main/java/com/stockproject/portfolio/alert/evaluation/FiringRule.java \
        src/test/java/com/stockproject/portfolio/alert/evaluation/FiringRuleTest.java
git commit -m "feat: 엣지 발화와 쿨다운, 해시 재기준을 판정한다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 발화 문구 — 제목 · 본문 · 관측값

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/sentence/EventText.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/sentence/EventTextTest.java`

**Interfaces:**
- Consumes: `SentenceWriter.lines(CompiledTrigger, EvaluationResult, EvaluationInput) → List<Line>` · `SentenceWriter.asOfLabel(CompiledTrigger, EvaluationResult, EvaluationInput) → String` · `AlertCatalog.preset(PresetKey).label()`
- Produces: `EventText(String title, String body, List<String> lines)`, `EventText.of(String instrumentName, String alertName, CompiledTrigger t, EvaluationResult r, EvaluationInput in)`, `EventText.title(String instrumentName, String alertName, CompiledTrigger t) → String`, `EventText.observed(EvaluationResult r) → Map<String, Object>`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/sentence/EventTextTest.java`:

```java
package com.stockproject.portfolio.alert.sentence;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.catalog.PresetKey;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.compile.Compiler;
import com.stockproject.portfolio.alert.evaluation.Basis;
import com.stockproject.portfolio.alert.evaluation.ConditionResult;
import com.stockproject.portfolio.alert.evaluation.EvaluationInput;
import com.stockproject.portfolio.alert.evaluation.EvaluationResult;
import com.stockproject.portfolio.alert.evaluation.Truth;
import com.stockproject.portfolio.alert.indicator.Series;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Right;
import com.stockproject.portfolio.alert.spec.Transform;
import com.stockproject.portfolio.alert.spec.TriggerSpec;
import com.stockproject.portfolio.domain.Market;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

/** 발화 문구 (스펙 §6.9 · §12.1, 계획 ② A.8). 기대 문구는 스펙의 예시 그대로다. */
class EventTextTest {

    @Test
    void 프리셋_장중_발화는_현재가와_시각을_쓴다() {
        CompiledTrigger t = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.PRICE_REACH,
                Map.of("direction", "up", "price", new BigDecimal("70000"))), Cadence.INTRADAY);
        OffsetDateTime asOf = OffsetDateTime.parse("2026-09-26T10:15:00+09:00");
        EvaluationResult r = new EvaluationResult(Truth.TRUE, null, asOf, Basis.INTRADAY,
                List.of(new ConditionResult(Truth.TRUE, null, new BigDecimal("70200"), new BigDecimal("70000"), null)));

        EventText text = EventText.of("삼성전자", "삼성전자 7만원", t, r,
                input(Cadence.INTRADAY, Basis.INTRADAY, Market.KR, LocalDate.of(2026, 9, 26), asOf));

        assertThat(text.title()).isEqualTo("삼성전자 · 가격 도달");
        assertThat(text.lines()).containsExactly("현재가 70,200원 ≥ 70,000원");
        assertThat(text.body()).isEqualTo("현재가 70,200원 ≥ 70,000원 · 10:15 기준");
    }

    @Test
    void 조립형_종가_발화는_알림_이름과_진행_상황과_기준일을_쓴다() {
        Condition rsi = new Condition(new Operand(IndicatorKey.RSI, Map.of("n", 14), new Transform.Identity()),
                OperatorKey.GTE, Right.constant(new BigDecimal("70")), new Modifier.Streak(3));
        CompiledTrigger t = Compiler.compile(new TriggerSpec.Composable(List.of(rsi)), Cadence.CLOSE);
        OffsetDateTime asOf = OffsetDateTime.parse("2026-09-26T15:30:00+09:00");
        EvaluationResult r = new EvaluationResult(Truth.TRUE, null, asOf, Basis.DAILY,
                List.of(new ConditionResult(Truth.TRUE, null, new BigDecimal("71.3"), new BigDecimal("70"), 3)));

        EventText text = EventText.of("카카오", "카카오 RSI 과열 지속", t, r,
                input(Cadence.CLOSE, Basis.DAILY, Market.KR, LocalDate.of(2026, 9, 26), asOf));

        assertThat(text.title()).isEqualTo("카카오 · 카카오 RSI 과열 지속");
        assertThat(text.body()).isEqualTo("RSI(14) 71.3 ≥ 70 · 3일째 · 9/26 종가 기준");
    }

    @Test
    void 미국_종가_발화는_미국_거래일로_쓴다() {
        CompiledTrigger t = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.PRICE_REACH,
                Map.of("direction", "up", "price", new BigDecimal("200"))), Cadence.CLOSE);
        OffsetDateTime asOf = OffsetDateTime.parse("2026-09-25T16:00:00-04:00");
        EvaluationResult r = new EvaluationResult(Truth.TRUE, null, asOf, Basis.DAILY,
                List.of(new ConditionResult(Truth.TRUE, null, new BigDecimal("230.1"), new BigDecimal("200"), null)));

        EventText text = EventText.of("애플", "애플", t, r,
                input(Cadence.CLOSE, Basis.DAILY, Market.US, LocalDate.of(2026, 9, 25), asOf));

        assertThat(text.title()).isEqualTo("애플 · 가격 도달");
        assertThat(text.body()).isEqualTo("종가 $230.10 ≥ $200.00 · 미국 9/25 종가 기준");
    }

    @Test
    void 종목명을_모르면_라벨만_쓴다() {
        CompiledTrigger t = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.PRICE_REACH,
                Map.of("direction", "up", "price", new BigDecimal("1"))), Cadence.CLOSE);
        OffsetDateTime asOf = OffsetDateTime.parse("2026-09-25T15:30:00+09:00");
        EvaluationResult r = new EvaluationResult(Truth.TRUE, null, asOf, Basis.DAILY,
                List.of(new ConditionResult(Truth.TRUE, null, BigDecimal.TEN, BigDecimal.ONE, null)));

        EventText text = EventText.of(null, "x", t, r,
                input(Cadence.CLOSE, Basis.DAILY, Market.KR, LocalDate.of(2026, 9, 25), asOf));

        assertThat(text.title()).isEqualTo("가격 도달");
    }

    /** 파라미터로 갈래를 고른 프리셋은 고른 갈래의 이름이 제목이다 — 스펙 §6.9의 예시 `카카오 · RSI 과매수` (계획 ② A.8). */
    @Test
    void 프리셋_제목은_고른_갈래의_이름이다() {
        assertThat(EventText.title("카카오", "x", preset(PresetKey.RSI_ZONE, Map.of("zone", "overbought"))))
                .isEqualTo("카카오 · RSI 과매수");
        assertThat(EventText.title("카카오", "x", preset(PresetKey.RSI_ZONE,
                Map.of("zone", "oversold", "level", new BigDecimal("30"))))).isEqualTo("카카오 · RSI 과매도");
        assertThat(EventText.title("NAVER", "x", preset(PresetKey.MA_CROSS, Map.of("direction", "dead"))))
                .isEqualTo("NAVER · 데드크로스");
        assertThat(EventText.title("NAVER", "x", preset(PresetKey.BOX_BREAKOUT, Map.of("direction", "up"))))
                .isEqualTo("NAVER · 박스권 상단 돌파");
        assertThat(EventText.title("NAVER", "x", preset(PresetKey.CHANGE_MOVE,
                Map.of("direction", "down", "pct", new BigDecimal("5"))))).isEqualTo("NAVER · 급락");
        assertThat(EventText.title("삼성전자", "x", preset(PresetKey.INVESTOR_STREAK,
                Map.of("investor", "institution", "side", "sell")))).isEqualTo("삼성전자 · 기관 연속 순매도");
        assertThat(EventText.title("삼성전자", "x", preset(PresetKey.INVESTOR_TURN,
                Map.of("investor", "foreign", "side", "buy")))).isEqualTo("삼성전자 · 외국인 순매수 전환");
        assertThat(EventText.title("삼성전자", "x", preset(PresetKey.VOLUME_SURGE, Map.of())))
                .isEqualTo("삼성전자 · 거래량 급증");
    }

    @Test
    void 관측값은_조건마다_양쪽_값과_진행_상황이다() {
        EvaluationResult r = new EvaluationResult(Truth.TRUE, null, OffsetDateTime.parse("2026-09-26T15:30:00+09:00"),
                Basis.DAILY, List.of(
                        new ConditionResult(Truth.TRUE, null, new BigDecimal("71.30"), new BigDecimal("70"), 3),
                        new ConditionResult(Truth.TRUE, null, new BigDecimal("63010.0000"), null, null)));

        Map<String, Object> observed = EventText.observed(r);

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> conditions = (List<Map<String, Object>>) observed.get("conditions");
        assertThat(conditions).hasSize(2);
        assertThat(conditions.get(0)).containsEntry("left", new BigDecimal("71.3"))
                .containsEntry("right", new BigDecimal("70")).containsEntry("progress", 3);
        assertThat(conditions.get(1)).containsEntry("left", new BigDecimal("63010"))
                .containsEntry("right", null).containsEntry("progress", null);
    }

    private static CompiledTrigger preset(PresetKey key, Map<String, Object> params) {
        return Compiler.compile(new TriggerSpec.PresetTrigger(key, params), Cadence.CLOSE);
    }

    private static EvaluationInput input(Cadence cadence, Basis basis, Market market, LocalDate date,
                                         OffsetDateTime asOf) {
        return new EvaluationInput(cadence, basis, market, date, asOf, Series.empty(), Set.of(), Set.of(), true,
                Duration.ofMinutes(market == Market.US ? 20 : 10));
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.sentence.EventTextTest'`
Expected: FAIL — `EventText`가 없어 컴파일 오류.

- [ ] **Step 3: 문구를 쓴다**

`src/main/java/com/stockproject/portfolio/alert/sentence/EventText.java`:

```java
package com.stockproject.portfolio.alert.sentence;

import com.stockproject.portfolio.alert.catalog.AlertCatalog;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.evaluation.ConditionResult;
import com.stockproject.portfolio.alert.evaluation.EvaluationInput;
import com.stockproject.portfolio.alert.evaluation.EvaluationResult;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 발화 문구 (스펙 §6.9, 계획 ② A.8). 발화 시점에 완성해 저장한다 — 알림을 나중에 고치거나 지워도
 * 그때 울린 내용은 바뀌지 않는다.
 *
 * <p>제목은 프리셋이면 종목명 · 프리셋 라벨(갈래를 고른 프리셋은 그 갈래의 이름), 조립형이면 종목명 · 알림 이름이다.
 * 본문은 조건별 관측값 줄을
 * " · "로 잇고 끝에 데이터 시점을 붙인다 — 밀린 종가를 따라잡아 울려도 기준일이 문구에 있다.
 * 줄은 미리보기의 현재값 상자와 같은 SentenceWriter.lines에서 온다. 계좌 정보는 넣지 않는다.</p>
 */
public record EventText(String title, String body, List<String> lines) {

    public EventText {
        lines = List.copyOf(lines);
    }

    public static EventText of(String instrumentName, String alertName, CompiledTrigger t, EvaluationResult r,
                               EvaluationInput in) {
        List<String> lines = SentenceWriter.lines(t, r, in).stream().map(Line::text).toList();
        String body = String.join(" · ", lines) + " · " + SentenceWriter.asOfLabel(t, r, in);
        return new EventText(title(instrumentName, alertName, t), body, lines);
    }

    public static String title(String instrumentName, String alertName, CompiledTrigger t) {
        String label = t.preset() != null ? presetLabel(t) : alertName;
        return instrumentName == null ? label : instrumentName + " · " + label;
    }

    /** 파라미터로 갈래를 고른 프리셋은 고른 갈래의 이름을 쓴다 — 스펙 §6.9 예시의 `RSI 과매수` (계획 ② A.8). */
    private static String presetLabel(CompiledTrigger t) {
        Map<String, Object> p = t.presetParams();
        return switch (t.preset()) {
            case RSI_ZONE -> "overbought".equals(p.get("zone")) ? "RSI 과매수" : "RSI 과매도";
            case MA_CROSS -> "golden".equals(p.get("direction")) ? "골든크로스" : "데드크로스";
            case BOX_BREAKOUT -> "up".equals(p.get("direction")) ? "박스권 상단 돌파" : "박스권 하단 이탈";
            case CHANGE_MOVE -> "up".equals(p.get("direction")) ? "급등" : "급락";
            case INVESTOR_STREAK -> investor(p) + " 연속 " + side(p);
            case INVESTOR_TURN -> investor(p) + " " + side(p) + " 전환";
            case PRICE_REACH, VOLUME_SURGE, PNL_REACH -> AlertCatalog.preset(t.preset()).label();
        };
    }

    private static String investor(Map<String, Object> p) {
        return "institution".equals(p.get("investor")) ? "기관" : "외국인";
    }

    private static String side(Map<String, Object> p) { return "buy".equals(p.get("side")) ? "순매수" : "순매도"; }

    /** 판정에 쓴 값 — 조건마다 양쪽 값과 진행 상황. 숫자는 꼬리 0을 뗀다. 계산할 수 없던 값은 null이다. */
    public static Map<String, Object> observed(EvaluationResult r) {
        List<Map<String, Object>> conditions = new ArrayList<>();
        for (ConditionResult c : r.conditions()) {
            Map<String, Object> one = new LinkedHashMap<>();
            one.put("left", plain(c.left()));
            one.put("right", plain(c.right()));
            one.put("progress", c.progress());
            conditions.add(one);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("conditions", conditions);
        return out;
    }

    /** 63010.0000 → 63010. 지수 표기(7E+4)가 JSON에 나가지 않게 평문으로 다시 만든다. */
    private static BigDecimal plain(BigDecimal v) {
        return v == null ? null : new BigDecimal(v.stripTrailingZeros().toPlainString());
    }
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.sentence.*'`
Expected: PASS

기대 문구가 다르게 나오면 `SentenceWriter`를 고치지 말고 멈춰서 보고한다 — 기대 문구는 스펙 §6.9 · §12.1의 예시이고, 다르면 ①의 문장 규칙과 스펙 사이의 어긋남이다.

- [ ] **Step 5: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/sentence/EventText.java \
        src/test/java/com/stockproject/portfolio/alert/sentence/EventTextTest.java
git commit -m "feat: 발화 제목·본문·관측값을 서버가 만든다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---
## Task 5: 평가 입력을 시점 하나로 — 미리보기와 평가기가 같은 메서드를 쓴다

①이 넘긴 3 · 4의 바탕(부록 A.12). 평가기가 쓸 시점별 입력, `snapshot_run` 읽기·기록, 저장된 조건의 안전한 컴파일을 둔다.

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/alert/data/EvaluationInputFactory.java` (전체 교체)
- Create: `src/main/java/com/stockproject/portfolio/alert/data/SnapshotRunMapper.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/service/SnapshotRunRecorder.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/validation/StoredTriggers.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/data/EvaluationInputFactoryTest.java` (추가)
- Test: `src/test/java/com/stockproject/portfolio/alert/data/SnapshotRunRecorderTest.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/validation/StoredTriggersTest.java`

**Interfaces:**
- Consumes: `MarketDataRepository`(①) — `bars` · `flows` · `snapshots` · `latestDoneAt` · `latestDoneDate` · `earliestDoneDate` · `doneDates` · `tradingDays` · `prevTradingDay` · `closeAt` · `zone`; `HoldingReader.holding(UserScope, LocalDate, InstrumentRow)`
- Produces:
  - `EvaluationInputFactory.forPreview(UserScope, InstrumentRow, CompiledTrigger, Cadence) → EvaluationInput` (동작은 ①과 같고 장중 이력의 누락일만 뺀다)
  - `EvaluationInputFactory.latestCloseDate(Market, Set<DataKind>) → Optional<LocalDate>`
  - `EvaluationInputFactory.closeAt(InstrumentRow, Set<DataKind> needs, LocalDate date) → EvaluationInput`
  - `EvaluationInputFactory.intradayAt(InstrumentRow, Set<DataKind> needs, OffsetDateTime asOf) → EvaluationInput`
  - `EvaluationInputFactory.userAt(UserScope, InstrumentRow, Cadence, LocalDate date, Set<DataKind> notDone) → EvaluationInput`
  - `static EvaluationInputFactory.unknownInstrument(Cadence, LocalDate date, OffsetDateTime asOf) → EvaluationInput`
  - `static EvaluationInputFactory.usesUserScope(CompiledTrigger) → boolean`
  - `SnapshotRunMapper.latest() → LocalDate` · `between(LocalDate from, LocalDate to) → List<LocalDate>` · `insert(LocalDate asOf, OffsetDateTime finishedAt) → int`
  - `SnapshotRunRecorder.record(LocalDate asOf)`
  - `StoredTriggers.compile(ObjectMapper json, String triggerType, String triggerSpec, Cadence cadence) → Optional<CompiledTrigger>`

- [ ] **Step 1: 실패하는 테스트를 쓴다 — 저장된 조건**

`src/test/java/com/stockproject/portfolio/alert/validation/StoredTriggersTest.java`:

```java
package com.stockproject.portfolio.alert.validation;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.catalog.Cadence;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/** 저장된 조건 하나가 지금 코드로 읽히지 않아도 목록·평가 전체가 멈추지 않는다 (계획 ② A.12 #4). */
class StoredTriggersTest {

    private final ObjectMapper json = new ObjectMapper();

    @Test
    void 저장된_프리셋을_컴파일한다() {
        assertThat(StoredTriggers.compile(json, "PRESET",
                "{\"preset_key\": \"price_reach\", \"params\": {\"direction\": \"up\", \"price\": 70000}}",
                Cadence.CLOSE)).isPresent();
    }

    @Test
    void 읽을_수_없으면_빈_값이다() {
        assertThat(StoredTriggers.compile(json, "PRESET", "{\"preset_key\": \"gone\", \"params\": {}}",
                Cadence.CLOSE)).isEmpty();
        assertThat(StoredTriggers.compile(json, "COMPOSABLE",
                "{\"conditions\": [{\"left\": {\"indicator\": \"gone\"}, \"op\": \"gte\", \"right\": {\"const\": 1}}]}",
                Cadence.CLOSE)).isEmpty();
        assertThat(StoredTriggers.compile(json, "PRESET", "{", Cadence.CLOSE)).isEmpty();
    }
}
```

- [ ] **Step 2: 실패하는 테스트를 쓴다 — 보유 스냅샷 신호**

`src/test/java/com/stockproject/portfolio/alert/data/SnapshotRunRecorderTest.java`:

```java
package com.stockproject.portfolio.alert.data;

import com.stockproject.portfolio.alert.FixedClockConfig;
import com.stockproject.portfolio.alert.service.SnapshotRunRecorder;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;

/** 보유 스냅샷 완료 신호 (스펙 §7.1 · §10.1, 계획 ② A.10). */
@SpringBootTest
@ActiveProfiles("test")
@Import(FixedClockConfig.class)
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class SnapshotRunRecorderTest {

    @Autowired SnapshotRunRecorder recorder;
    @Autowired SnapshotRunMapper mapper;
    @Autowired JdbcClient jdbc;

    @Test
    void 기록하면_평가기가_읽는_신호가_생긴다() {
        recorder.record(LocalDate.of(2026, 7, 27));

        assertThat(mapper.latest()).isEqualTo(LocalDate.of(2026, 7, 27));
        assertThat(mapper.between(LocalDate.of(2026, 7, 1), LocalDate.of(2026, 7, 31)))
                .containsExactly(LocalDate.of(2026, 7, 24), LocalDate.of(2026, 7, 27));
        assertThat(finishedAt(LocalDate.of(2026, 7, 27)))
                .isAtSameInstantAs(FixedClockConfig.NOW.atOffset(ZoneOffset.UTC));
    }

    @Test
    void 같은_날을_다시_기록하면_첫_기록이_남는다() {
        recorder.record(LocalDate.of(2026, 7, 24));

        assertThat(finishedAt(LocalDate.of(2026, 7, 24)))
                .isAtSameInstantAs(OffsetDateTime.parse("2026-07-24T18:00:00+09:00"));
    }

    private OffsetDateTime finishedAt(LocalDate asOf) {
        return jdbc.sql("SELECT finished_at FROM snapshot_run WHERE as_of = :d").param("d", asOf)
                .query(OffsetDateTime.class).single();
    }
}
```

- [ ] **Step 3: 실패하는 테스트를 쓴다 — 시점 하나의 입력**

`EvaluationInputFactoryTest`에 테스트 넷과 도우미 하나를 더한다. import가 없으면 더한다: `com.stockproject.portfolio.alert.catalog.DataKind` · `com.stockproject.portfolio.alert.indicator.Bar` · `java.util.EnumSet` · `java.util.Set`.

```java
    /** 장중 이력도 종가와 같이 데이터 누락일의 봉을 뺀다 (계획 ② A.12 #3). */
    @Test
    void 장중_이력도_데이터_누락일을_뺀다() {
        jdbc.sql("""
                DELETE FROM market_data_run
                 WHERE market = 'KR' AND kind = 'DAILY_BAR' AND as_of = '2026-09-23T15:30:00+09'
                """).update();

        EvaluationInput in = factory("2026-09-28T10:20:00+09:00").forPreview(YHR, row(SAMSUNG), priceAbove("1"),
                Cadence.INTRADAY);

        assertThat(in.basis()).isEqualTo(Basis.INTRADAY);
        assertThat(in.series().bars()).extracting(Bar::date)
                .doesNotContain(LocalDate.of(2026, 9, 23))
                .contains(LocalDate.of(2026, 9, 22), LocalDate.of(2026, 9, 24), LocalDate.of(2026, 9, 25));
    }

    /** 미리보기는 평가기와 같은 시점(시장 신호 시각)만 장중 기준으로 쓴다. 그 시각에 종목 스냅샷이 없으면 종가 기준이다. */
    @Test
    void 미리보기는_시장_신호_시각에_종목_스냅샷이_없으면_종가_기준이다() {
        jdbc.sql("""
                DELETE FROM intraday_quote
                 WHERE instrument_id = '10000000-0000-0000-0000-000000000001'
                   AND snapshot_at = '2026-09-28T10:15:00+09'
                """).update();

        EvaluationInput in = factory("2026-09-28T10:20:00+09:00").forPreview(YHR, row(SAMSUNG), priceAbove("1"),
                Cadence.INTRADAY);

        assertThat(in.basis()).isEqualTo(Basis.DAILY);
        assertThat(in.date()).isEqualTo(LocalDate.of(2026, 9, 25));
    }

    /** 평가기는 시장 신호의 시각에서 평가한다. 그 시각에 그 종목의 스냅샷이 없으면 지금 값이 없다. */
    @Test
    void 장중_시점에_그_종목의_스냅샷이_없으면_지금_값이_없다() {
        EvaluationInputFactory f = real("2026-09-28T10:20:00+09:00");
        Set<DataKind> needs = EnumSet.of(DataKind.INTRADAY_QUOTE);

        OffsetDateTime between = OffsetDateTime.parse("2026-09-28T10:12:00+09:00");
        EvaluationInput missing = f.intradayAt(row(SAMSUNG), needs, between);
        assertThat(missing.series().snapshots()).isEmpty();
        assertThat(missing.asOf()).isAtSameInstantAs(between);
        assertThat(ConditionEvaluator.evaluate(priceAbove("1"), missing).reason()).isEqualTo(UnknownReason.NO_TRADE);

        EvaluationInput at = f.intradayAt(row(SAMSUNG), needs, OffsetDateTime.parse("2026-09-28T10:10:00+09:00"));
        assertThat(at.series().snapshots()).hasSize(3);
        assertThat(ConditionEvaluator.evaluate(priceAbove("63300"), at).truth()).isEqualTo(Truth.TRUE);
    }

    @Test
    void 종가_시점의_입력은_그날_DONE이_아닌_종류를_표시한다() {
        jdbc.sql("""
                DELETE FROM market_data_run
                 WHERE market = 'KR' AND kind = 'DAILY_FLOW' AND as_of = '2026-09-25T15:30:00+09'
                """).update();
        EvaluationInputFactory f = real("2026-09-28T10:20:00+09:00");
        Set<DataKind> both = EnumSet.of(DataKind.DAILY_BAR, DataKind.DAILY_FLOW);

        EvaluationInput in = f.closeAt(row(SAMSUNG), both, LocalDate.of(2026, 9, 25));

        assertThat(in.notDone()).containsExactly(DataKind.DAILY_FLOW);
        assertThat(in.asOf()).isAtSameInstantAs(OffsetDateTime.parse("2026-09-25T15:30:00+09:00"));
        assertThat(f.latestCloseDate(Market.KR, both)).contains(LocalDate.of(2026, 9, 24));
        assertThat(f.latestCloseDate(Market.KR, EnumSet.of(DataKind.DAILY_BAR))).contains(LocalDate.of(2026, 9, 25));
    }

    @Test
    void 사용자_상태_시점의_신호가_없으면_데이터_없음이다() {
        CompiledTrigger pnl = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.PNL_REACH, Map.of()),
                Cadence.CLOSE);
        EvaluationInputFactory f = real("2026-09-28T10:20:00+09:00");
        LocalDate asOf = LocalDate.of(2026, 7, 24);

        EvaluationInput waiting = f.userAt(YHR, row(SAMSUNG), Cadence.CLOSE, asOf, EnumSet.of(DataKind.PORTFOLIO_SNAPSHOT));
        EvaluationInput done = f.userAt(YHR, row(SAMSUNG), Cadence.CLOSE, asOf, Set.of());

        assertThat(ConditionEvaluator.evaluate(pnl, waiting).reason()).isEqualTo(UnknownReason.DATA_MISSING);
        assertThat(ConditionEvaluator.evaluate(pnl, done).truth()).isNotEqualTo(Truth.UNKNOWN);
        assertThat(done.asOf()).isAtSameInstantAs(OffsetDateTime.parse("2026-07-24T15:30:00+09:00"));
    }
```

도우미 구역(`factory(String now)` 아래)에 더한다.

```java
    private EvaluationInputFactory real(String now) {
        Clock clock = Clock.fixed(Instant.from(OffsetDateTime.parse(now)), ZoneId.of("Asia/Seoul"));
        return new EvaluationInputFactory(market, holdings, clock);
    }
```

- [ ] **Step 4: 실패를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.data.*' --tests 'com.stockproject.portfolio.alert.validation.StoredTriggersTest'`
Expected: FAIL — `StoredTriggers` · `SnapshotRunRecorder` · `intradayAt` 등이 없어 컴파일 오류.

- [ ] **Step 5: 저장된 조건 컴파일을 쓴다**

`src/main/java/com/stockproject/portfolio/alert/validation/StoredTriggers.java`:

```java
package com.stockproject.portfolio.alert.validation;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.compile.Compiler;

import java.util.Optional;

/**
 * 저장된 trigger_spec을 지금 코드로 컴파일한다. 저장 전에 검증을 통과한 값이지만, 카탈로그에서 키가 빠진
 * 배포처럼 지금 코드가 읽지 못할 수 있다. 그때는 빈 값을 돌려준다 — 알림 하나 때문에 목록·평가 전체가
 * 멈추지 않게 하기 위해서다. 부르는 쪽이 alert_id를 로그에 남긴다.
 */
public final class StoredTriggers {

    private StoredTriggers() { }

    public static Optional<CompiledTrigger> compile(ObjectMapper json, String triggerType, String triggerSpec,
                                                    Cadence cadence) {
        try {
            return Optional.of(Compiler.compile(AlertRequestParser.stored(triggerType, json.readTree(triggerSpec)),
                    cadence));
        } catch (JsonProcessingException | RuntimeException e) {
            return Optional.empty();
        }
    }
}
```

- [ ] **Step 6: 보유 스냅샷 신호를 쓴다**

`src/main/java/com/stockproject/portfolio/alert/data/SnapshotRunMapper.java`:

```java
package com.stockproject.portfolio.alert.data;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;

/** 보유 스냅샷 완료 신호 (스펙 §7.1 · §10.1). 사용자 상태 지표 알림의 평가 신호다. */
@Mapper
public interface SnapshotRunMapper {

    @Select("SELECT max(as_of) FROM snapshot_run")
    LocalDate latest();

    @Select("SELECT as_of FROM snapshot_run WHERE as_of BETWEEN #{from} AND #{to} ORDER BY as_of")
    List<LocalDate> between(@Param("from") LocalDate from, @Param("to") LocalDate to);

    /** 같은 날을 다시 쓰면 첫 기록이 남는다. */
    @Insert("""
            INSERT INTO snapshot_run (as_of, finished_at) VALUES (#{asOf}, #{finishedAt})
            ON CONFLICT (as_of) DO NOTHING
            """)
    int insert(@Param("asOf") LocalDate asOf, @Param("finishedAt") OffsetDateTime finishedAt);
}
```

`src/main/java/com/stockproject/portfolio/alert/service/SnapshotRunRecorder.java`:

```java
package com.stockproject.portfolio.alert.service;

import com.stockproject.portfolio.alert.data.SnapshotRunMapper;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.LocalDate;
import java.time.OffsetDateTime;

/**
 * 보유 스냅샷 완료 신호를 남기는 창구 (스펙 §7.1, 계획 ② A.10). 포트폴리오 EOD 스냅샷 생성
 * (포트폴리오 스펙 §3.6 1단계)이 그 as_of의 전 계좌를 마친 뒤 부른다.
 */
@Service
public class SnapshotRunRecorder {

    private final SnapshotRunMapper mapper;
    private final Clock clock;

    public SnapshotRunRecorder(SnapshotRunMapper mapper, Clock clock) {
        this.mapper = mapper;
        this.clock = clock;
    }

    public void record(LocalDate asOf) {
        mapper.insert(asOf, OffsetDateTime.now(clock));
    }
}
```

- [ ] **Step 7: 평가 입력을 시점 하나로 나눈다**

`src/main/java/com/stockproject/portfolio/alert/data/EvaluationInputFactory.java`를 통째로 바꾼다.

```java
package com.stockproject.portfolio.alert.data;

import com.stockproject.portfolio.alert.catalog.AlertCatalog;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.DataKind;
import com.stockproject.portfolio.alert.catalog.Scope;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.compile.DataNeeds;
import com.stockproject.portfolio.alert.evaluation.Basis;
import com.stockproject.portfolio.alert.evaluation.EvaluationInput;
import com.stockproject.portfolio.alert.indicator.Bar;
import com.stockproject.portfolio.alert.indicator.FlowBar;
import com.stockproject.portfolio.alert.indicator.Holding;
import com.stockproject.portfolio.alert.indicator.Series;
import com.stockproject.portfolio.alert.indicator.Snapshot;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.domain.Market;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.EnumSet;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/**
 * 평가 입력. 미리보기와 평가기가 같은 메서드로 데이터 시점 하나의 입력을 만든다 — 같은 시점이면 같은 입력이고,
 * 같은 입력이면 순수 계산이 같은 결과를 낸다(결정 기록 "알림 계산").
 *
 * <p>시점 하나의 입력은 셋이다 — 종가는 closeAt(거래일), 장중은 intradayAt(스냅샷 시각), 사용자 상태는
 * userAt(스냅샷 기준일). 미리보기는 그 시점을 계획 ① A.5대로 고르고, 평가기는 계획 ② A.4대로 고른다.</p>
 *
 * <p>계열은 있는 봉으로 만든다(스펙 §7.2). 데이터 누락일 — 거래일인데 그 시장·종류의 DONE이 없는 날 — 의
 * 봉은 일부 적재돼 있어도 쓰지 않는다. 종가와 장중이 같다.</p>
 */
@Component
public class EvaluationInputFactory {

    /** 읽는 봉 수의 최대는 274다(§5.4). 데이터가 보장하는 300봉을 읽는다. */
    static final int BAR_LIMIT = 300;
    /** 수급의 최대 필요 봉 수는 30이다(§5.1). */
    static final int FLOW_LIMIT = 30;

    private final MarketDataRepository market;
    private final HoldingReader holdings;
    private final Clock clock;

    public EvaluationInputFactory(MarketDataRepository market, HoldingReader holdings, Clock clock) {
        this.market = market;
        this.holdings = holdings;
        this.clock = clock;
    }

    // ---- 미리보기 (계획 ① A.5) ---------------------------------------------------

    public EvaluationInput forPreview(UserScope scope, InstrumentRow instrument, CompiledTrigger trigger,
                                      Cadence cadence) {
        if (instrument == null) return unknownInstrument(cadence, null, null);
        if (usesUserScope(trigger)) {
            Optional<LocalDate> asOf = holdings.latestFinal(scope);
            if (asOf.isEmpty()) return EvaluationInput.noData(cadence, Market.KR);
            return userAt(scope, instrument, cadence, asOf.get(), Set.of());
        }
        Market m = instrument.marketEnum();
        Set<DataKind> needs = DataNeeds.of(trigger, cadence);
        if (needs.isEmpty()) return EvaluationInput.noData(cadence, m);   // 평가할 조건이 없다
        if (cadence == Cadence.INTRADAY) return intradayPreview(instrument, needs);
        return latestCloseDate(m, needs)
                .map(date -> closeAt(instrument, needs, date))
                .orElseGet(() -> EvaluationInput.noData(Cadence.CLOSE, m));
    }

    /**
     * 시장의 최신 장중 신호가 허용 지연 안이고 그 시각에 그 종목의 스냅샷이 있으면 그 시각 — 평가기가 평가하는
     * 시점과 같다(계획 ② A.4). 아니면 가장 최근 DAILY_BAR 거래일의 종가를 스냅샷 하나로 삼은 일봉 기준이다 —
     * 시장 신호가 최신이어도 거래정지 종목은 그 시각의 스냅샷이 없다.
     */
    private EvaluationInput intradayPreview(InstrumentRow instrument, Set<DataKind> needs) {
        Market m = instrument.marketEnum();
        Duration gap = EvaluationInput.allowedGap(m);
        OffsetDateTime now = OffsetDateTime.now(clock);
        Optional<OffsetDateTime> quote = market.latestDoneAt(m, DataKind.INTRADAY_QUOTE);
        if (quote.isPresent() && Duration.between(quote.get(), now).compareTo(gap) <= 0) {
            LocalDate today = quote.get().atZoneSameInstant(MarketDataRepository.zone(m)).toLocalDate();
            List<Snapshot> snaps = market.snapshots(instrument.instrumentId(), m, today, quote.get());
            if (!snaps.isEmpty() && snaps.get(snaps.size() - 1).at().isEqual(quote.get())) {
                return intradayAt(instrument, needs, quote.get());
            }
        }
        return intradayFromClose(instrument, m, gap);
    }

    private EvaluationInput intradayFromClose(InstrumentRow instrument, Market m, Duration gap) {
        Optional<LocalDate> latest = market.latestDoneDate(m, DataKind.DAILY_BAR);
        if (latest.isEmpty()) return EvaluationInput.noData(Cadence.INTRADAY, m);
        LocalDate date = latest.get();
        OffsetDateTime closeAt = market.closeAt(m, date);
        List<Bar> bars = historyBars(m, instrument.instrumentId(), date, BAR_LIMIT + 1);
        Bar last = bars.isEmpty() ? null : bars.get(bars.size() - 1);
        List<Snapshot> snapshot = List.of();
        List<Bar> history = bars;
        if (last != null && last.date().equals(date)) {
            snapshot = List.of(new Snapshot(closeAt, last.close(), last.volume()));
            history = bars.subList(0, bars.size() - 1);
        }
        return new EvaluationInput(Cadence.INTRADAY, Basis.DAILY, m, date, closeAt,
                new Series(history, List.of(), snapshot, null), Set.of(), Set.of(), true, gap);
    }

    // ---- 시점 하나의 입력 ----------------------------------------------------------

    /** 기다리는 종류마다 최신 DONE 거래일을 구하고 그중 가장 이른 날. 한 종류라도 DONE이 없으면 빈 값이다. */
    public Optional<LocalDate> latestCloseDate(Market m, Set<DataKind> needs) {
        LocalDate date = null;
        for (DataKind kind : needs) {
            Optional<LocalDate> latest = market.latestDoneDate(m, kind);
            if (latest.isEmpty()) return Optional.empty();
            if (date == null || latest.get().isBefore(date)) date = latest.get();
        }
        return Optional.ofNullable(date);
    }

    /**
     * 종가 알림의 거래일 date. 그날 DONE이 아닌 종류는 notDone이 된다 — 그 뒤 거래일의 같은 종류가
     * DONE이 됐다면 그날의 데이터는 오지 않는 것으로 본다(§7.1).
     */
    public EvaluationInput closeAt(InstrumentRow instrument, Set<DataKind> needs, LocalDate date) {
        Market m = instrument.marketEnum();
        Set<DataKind> notDone = EnumSet.noneOf(DataKind.class);
        for (DataKind kind : needs) {
            if (!market.doneDates(m, kind, date, date).contains(date)) notDone.add(kind);
        }
        List<Bar> bars = market.bars(instrument.instrumentId(), date, BAR_LIMIT);
        List<FlowBar> flows = needs.contains(DataKind.DAILY_FLOW)
                ? market.flows(instrument.instrumentId(), date, FLOW_LIMIT) : List.of();

        Set<LocalDate> missingBars = bars.isEmpty() ? Set.of()
                : missingDays(m, DataKind.DAILY_BAR, bars.get(0).date(), date);
        Set<LocalDate> missingFlows = flows.isEmpty() ? Set.of()
                : missingDays(m, DataKind.DAILY_FLOW, flows.get(0).date(), date);
        Series series = new Series(
                bars.stream().filter(b -> !missingBars.contains(b.date())).toList(),
                flows.stream().filter(f -> !missingFlows.contains(f.date())).toList(), List.of(), null);
        Set<LocalDate> missing = new HashSet<>(missingBars);
        missing.addAll(missingFlows);
        return new EvaluationInput(Cadence.CLOSE, Basis.DAILY, m, date, market.closeAt(m, date), series, notDone,
                missing, true, EvaluationInput.allowedGap(m));
    }

    /**
     * 장중 알림의 스냅샷 시각 asOf. 그 종목의 그날 스냅샷을 asOf까지 읽는다. asOf의 스냅샷이 없으면 지금 값이
     * 없다 — 앞선 스냅샷을 지금 값으로 쓰지 않는다(거래 없음). 이력은 직전 거래일까지이고 누락일을 뺀다.
     */
    public EvaluationInput intradayAt(InstrumentRow instrument, Set<DataKind> needs, OffsetDateTime asOf) {
        Market m = instrument.marketEnum();
        LocalDate today = asOf.atZoneSameInstant(MarketDataRepository.zone(m)).toLocalDate();
        List<Snapshot> snaps = market.snapshots(instrument.instrumentId(), m, today, asOf);
        if (!snaps.isEmpty() && !snaps.get(snaps.size() - 1).at().isEqual(asOf)) snaps = List.of();

        LocalDate prev = market.prevTradingDay(m, today);
        Set<DataKind> notDone = EnumSet.noneOf(DataKind.class);
        if (needs.contains(DataKind.DAILY_BAR)
                && !market.doneDates(m, DataKind.DAILY_BAR, prev, prev).contains(prev)) {
            notDone.add(DataKind.DAILY_BAR);
        }
        List<Bar> history = historyBars(m, instrument.instrumentId(), prev, BAR_LIMIT);
        return new EvaluationInput(Cadence.INTRADAY, Basis.INTRADAY, m, today, asOf,
                new Series(history, List.of(), snaps, null), notDone, Set.of(), true, EvaluationInput.allowedGap(m));
    }

    /**
     * 사용자 상태 지표의 스냅샷 기준일 date. 데이터 시점은 국내 영업일의 확정 스냅샷이라 시장은 KR이다(§7.1).
     * notDone은 부르는 쪽이 정한다 — 평가기는 snapshot_run이 없는 날에 PORTFOLIO_SNAPSHOT을 넣는다.
     */
    public EvaluationInput userAt(UserScope scope, InstrumentRow instrument, Cadence cadence, LocalDate date,
                                  Set<DataKind> notDone) {
        Holding holding = holdings.holding(scope, date, instrument);
        return new EvaluationInput(cadence, Basis.DAILY, Market.KR, date, market.closeAt(Market.KR, date),
                new Series(List.of(), List.of(), List.of(), holding), notDone, Set.of(), true,
                EvaluationInput.allowedGap(Market.KR));
    }

    /** 종목 마스터에 없는 종목. 모든 조건이 INSTRUMENT_UNKNOWN이다. 평가기는 시점을 함께 준다(계획 ② A.4). */
    public static EvaluationInput unknownInstrument(Cadence cadence, LocalDate date, OffsetDateTime asOf) {
        return new EvaluationInput(cadence, cadence == Cadence.INTRADAY ? Basis.INTRADAY : Basis.DAILY, Market.KR,
                date, asOf, Series.empty(), Set.of(), Set.of(), false, EvaluationInput.allowedGap(Market.KR));
    }

    public static boolean usesUserScope(CompiledTrigger trigger) {
        return trigger.conditions().stream()
                .anyMatch(c -> AlertCatalog.indicator(c.left().indicator()).scope() == Scope.USER);
    }

    // ---- 계열 ------------------------------------------------------------------

    /** to까지의 일봉에서 데이터 누락일을 뺀다. */
    private List<Bar> historyBars(Market m, UUID instrumentId, LocalDate to, int limit) {
        List<Bar> bars = market.bars(instrumentId, to, limit);
        if (bars.isEmpty()) return bars;
        Set<LocalDate> missing = missingDays(m, DataKind.DAILY_BAR, bars.get(0).date(), to);
        return bars.stream().filter(b -> !missing.contains(b.date())).toList();
    }

    /**
     * from ~ to의 거래일 중 그 종류의 DONE이 없는 날 — 데이터 누락일 (계획 ① A.6).
     * 완료 신호는 파이프라인이 돌기 시작한 날부터 쌓이므로, 그 종류의 첫 DONE 거래일 전의 날은
     * 누락일로 보지 않는다. DONE이 하나도 없으면 누락일도 없다.
     */
    private Set<LocalDate> missingDays(Market m, DataKind kind, LocalDate from, LocalDate to) {
        Optional<LocalDate> earliest = market.earliestDoneDate(m, kind);
        if (earliest.isEmpty()) return Set.of();
        LocalDate start = earliest.get().isAfter(from) ? earliest.get() : from;
        if (start.isAfter(to)) return Set.of();
        Set<LocalDate> done = market.doneDates(m, kind, start, to);
        Set<LocalDate> missing = new HashSet<>();
        for (LocalDate d : market.tradingDays(m, start, to)) if (!done.contains(d)) missing.add(d);
        return missing;
    }
}
```

- [ ] **Step 8: 통과를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.*'`
Expected: PASS (①의 미리보기 테스트 포함 전부 — 미리보기의 동작은 장중 이력의 누락일을 빼는 것만 다르다)

- [ ] **Step 9: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/data/EvaluationInputFactory.java \
        src/main/java/com/stockproject/portfolio/alert/data/SnapshotRunMapper.java \
        src/main/java/com/stockproject/portfolio/alert/service/SnapshotRunRecorder.java \
        src/main/java/com/stockproject/portfolio/alert/validation/StoredTriggers.java \
        src/test/java/com/stockproject/portfolio/alert/data/EvaluationInputFactoryTest.java \
        src/test/java/com/stockproject/portfolio/alert/data/SnapshotRunRecorderTest.java \
        src/test/java/com/stockproject/portfolio/alert/validation/StoredTriggersTest.java
git commit -m "feat: 평가 입력을 데이터 시점 하나로 나누고 보유 스냅샷 신호를 둔다

장중 이력도 데이터 누락일의 봉을 뺀다. 저장된 조건을 읽지 못하면 빈 값을 돌려준다.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---
## Task 6: 평가 반영 — 조건부 갱신 · 발화 기록 · 발송 행 · 한 번만 알림 종료 · 만료

스펙 §8.2 ① ~ ③과 §14.4를 한 트랜잭션 단위로 만든다(부록 A.5 ~ A.8).

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/store/RuntimeAlertRow.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/store/ExpiredAlert.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/store/RuntimeMapper.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/store/AlertRuntimeStore.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/runtime/Target.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/runtime/Outcome.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/runtime/Applied.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/runtime/AlertRuntimeWriter.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/runtime/RuntimeFixtures.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/runtime/AlertRuntimeWriterTest.java`

**Interfaces:**
- Consumes: `FiringRule.decide(...)`(Task 3) · `EventText.of(...)` · `EventText.observed(...)`(Task 4) · `AlertStore.bumpVersion(UUID)` · `AlertStore.refreshWatchlist(UUID)`(①) · `SpecHash.of(CompiledTrigger, Cadence)`(①)
- Produces:
  - `RuntimeAlertRow(UUID alertId, UUID userId, UUID instrumentId, String name, String cadence, String notifyMode, Integer cooldownMin, String triggerType, String triggerSpec, String lastKnownResult, OffsetDateTime evaluatedAsOf, String specHash, int version)`
  - `ExpiredAlert(UUID alertId, UUID instrumentId)`
  - `AlertRuntimeStore.candidates() → List<RuntimeAlertRow>`
  - `Target(RuntimeAlertRow row, CompiledTrigger trigger, String specHash, String instrumentName, Truth lastKnown, String storedHash, OffsetDateTime evaluatedAsOf)`, `Target.of(RuntimeAlertRow, CompiledTrigger, Cadence, String instrumentName)`, `Target.after(Truth lastKnown, String storedHash, OffsetDateTime asOf)`
  - `enum Outcome { APPLIED, FIRED, ENDED, LOST }` · `Applied(Outcome outcome, Target next)`
  - `AlertRuntimeWriter.apply(Target, EvaluationInput, EvaluationResult) → Applied` (`@Transactional`)
  - `AlertRuntimeWriter.expire(OffsetDateTime now) → List<ExpiredAlert>` (`@Transactional`)

- [ ] **Step 1: 테스트 도우미를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/runtime/RuntimeFixtures.java`:

```java
package com.stockproject.portfolio.alert.runtime;

import com.stockproject.portfolio.auth.UserScope;

import java.util.UUID;

/**
 * 평가기 테스트의 픽스처. 알림은 API와 같은 AlertCommandService로 만든다 — 상태 행과 대상 종목이 함께 생긴다.
 * 시세는 sample_alert_market.sql이다: 국내 일봉 DONE은 2026-09-25(금)까지, 삼성전자 종가는 9/22 62,980 ·
 * 9/23 62,990 · 9/24 63,000 · 9/25 63,010, 9/28 장중 스냅샷은 10:00 ~ 10:15(63,100 ~ 63,500)이다.
 */
final class RuntimeFixtures {

    private RuntimeFixtures() { }

    static final UserScope YHR = new UserScope(UUID.fromString("40000000-0000-0000-0000-000000000001"));
    static final UserScope JDH = new UserScope(UUID.fromString("40000000-0000-0000-0000-000000000002"));
    static final String SAMSUNG = "10000000-0000-0000-0000-000000000001";
    static final String HYNIX = "10000000-0000-0000-0000-000000000002";
    static final String APPLE = "10000000-0000-0000-0000-000000000004";

    /** 가격 도달(상향). cooldownMin은 COOLDOWN일 때만 준다. */
    static String priceReach(String instrument, String cadence, String notifyMode, Integer cooldownMin, String price) {
        return """
                { "instrument_id": "%s", "name": "가격", "cadence": "%s", "notify_mode": "%s", "cooldown_min": %s,
                  "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "price_reach", "params": { "direction": "up", "price": %s } } }
                """.formatted(instrument, cadence, notifyMode, cooldownMin == null ? "null" : cooldownMin, price);
    }

    static String closeAbove(String price) { return priceReach(SAMSUNG, "CLOSE", "EDGE_REARM", null, price); }

    /** 수익률 도달(수익). 사용자 상태 지표 알림이다. */
    static String pnlReach(String instrument, String pct) {
        return """
                { "instrument_id": "%s", "name": "수익률", "cadence": "CLOSE", "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "pnl_reach", "params": { "direction": "profit", "pct": %s } } }
                """.formatted(instrument, pct);
    }
}
```

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/runtime/AlertRuntimeWriterTest.java`:

```java
package com.stockproject.portfolio.alert.runtime;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.FixedClockConfig;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.compile.DataNeeds;
import com.stockproject.portfolio.alert.data.EvaluationInputFactory;
import com.stockproject.portfolio.alert.data.InstrumentRow;
import com.stockproject.portfolio.alert.data.MarketDataRepository;
import com.stockproject.portfolio.alert.evaluation.Basis;
import com.stockproject.portfolio.alert.evaluation.ConditionEvaluator;
import com.stockproject.portfolio.alert.evaluation.ConditionResult;
import com.stockproject.portfolio.alert.evaluation.EvaluationInput;
import com.stockproject.portfolio.alert.evaluation.EvaluationResult;
import com.stockproject.portfolio.alert.evaluation.Truth;
import com.stockproject.portfolio.alert.evaluation.UnknownReason;
import com.stockproject.portfolio.alert.service.AlertCommandService;
import com.stockproject.portfolio.alert.service.DeviceService;
import com.stockproject.portfolio.alert.store.AlertRuntimeStore;
import com.stockproject.portfolio.alert.store.ExpiredAlert;
import com.stockproject.portfolio.alert.store.RuntimeAlertRow;
import com.stockproject.portfolio.alert.validation.StoredTriggers;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import static com.stockproject.portfolio.alert.runtime.RuntimeFixtures.*;
import static org.assertj.core.api.Assertions.assertThat;

/** 평가 한 번의 반영 (스펙 §8.2 · §14.4, 계획 ② A.5 ~ A.8). */
@SpringBootTest
@ActiveProfiles("test")
@Import(FixedClockConfig.class)
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class AlertRuntimeWriterTest {

    private static final OffsetDateTime CLOSE_9_25 = OffsetDateTime.parse("2026-09-25T15:30:00+09:00");

    @Autowired AlertCommandService commands;
    @Autowired DeviceService devices;
    @Autowired AlertRuntimeStore store;
    @Autowired AlertRuntimeWriter writer;
    @Autowired EvaluationInputFactory inputs;
    @Autowired MarketDataRepository market;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;
    @Autowired TransactionTemplate tx;

    @Test
    void 참이_되면_발화를_기록하고_iOS_기기마다_발송_행을_만든다() throws Exception {
        UUID id = create(closeAbove("1"));
        devices.register(YHR, "ExponentPushToken[yhr-ios]", "IOS");
        devices.register(YHR, "ExponentPushToken[yhr-android]", "ANDROID");
        devices.register(JDH, "ExponentPushToken[jdh-ios]", "IOS");

        Applied applied = apply(target(id));

        assertThat(applied.outcome()).isEqualTo(Outcome.FIRED);
        assertThat(applied.next().evaluatedAsOf()).isAtSameInstantAs(CLOSE_9_25);
        assertThat(jdbc.sql("SELECT title FROM alert_event WHERE alert_id = :id").param("id", id)
                .query(String.class).single()).isEqualTo("삼성전자 · 가격 도달");
        assertThat(jdbc.sql("SELECT body FROM alert_event WHERE alert_id = :id").param("id", id)
                .query(String.class).single()).isEqualTo("종가 63,010원 ≥ 1원 · 9/25 종가 기준");
        assertThat(jdbc.sql("SELECT lines::text FROM alert_event WHERE alert_id = :id").param("id", id)
                .query(String.class).single()).isEqualTo("[\"종가 63,010원 ≥ 1원\"]");
        assertThat(jdbc.sql("""
                SELECT p.expo_push_token FROM alert_delivery d JOIN push_device p USING (device_id)
                 WHERE d.state = 'PENDING' AND d.attempts = 0
                """).query(String.class).list()).containsExactly("ExponentPushToken[yhr-ios]");
        assertThat(stateOf(id, "last_result")).isEqualTo("TRUE");
        assertThat(stateOf(id, "last_known_result")).isEqualTo("TRUE");
    }

    @Test
    void 읽은_뒤_사용자가_바꾼_알림에는_반영하지_않는다() throws Exception {
        UUID id = create(closeAbove("1"));
        Target stale = target(id);
        commands.pause(YHR, id);

        assertThat(apply(stale).outcome()).isEqualTo(Outcome.LOST);
        assertThat(events(id)).isZero();
        assertThat(stateOf(id, "last_result")).isNull();
    }

    @Test
    void 다른_복제본이_먼저_반영했으면_진다() throws Exception {
        UUID id = create(closeAbove("1"));
        Target first = target(id);
        Target second = target(id);

        assertThat(apply(first).outcome()).isEqualTo(Outcome.FIRED);
        assertThat(apply(second).outcome()).isEqualTo(Outcome.LOST);
        assertThat(events(id)).isEqualTo(1);
    }

    /** 다시 켠 직후 같은 데이터 시점을 다시 평가하면 그 시점은 이미 울린 것으로 본다 (§8.2 ②). */
    @Test
    void 같은_시점이_이미_울렸으면_상태만_반영한다() throws Exception {
        UUID id = create(closeAbove("1"));
        devices.register(YHR, "ExponentPushToken[yhr-ios]", "IOS");
        apply(target(id));
        jdbc.sql("""
                UPDATE alert_state SET evaluated_as_of = NULL, last_known_result = 'FALSE', version = version + 1
                 WHERE alert_id = :id
                """).param("id", id).update();

        Applied again = apply(target(id));

        assertThat(again.outcome()).isEqualTo(Outcome.APPLIED);
        assertThat(events(id)).isEqualTo(1);
        assertThat(jdbc.sql("SELECT count(*) FROM alert_delivery").query(Integer.class).single()).isEqualTo(1);
        assertThat(stateOf(id, "last_known_result")).isEqualTo("TRUE");
    }

    @Test
    void 한_번만_알림은_울리면_끝나고_대상_종목에서_빠진다() throws Exception {
        UUID id = create(priceReach(SAMSUNG, "CLOSE", "ONE_SHOT", null, "1"));

        assertThat(apply(target(id)).outcome()).isEqualTo(Outcome.ENDED);
        assertThat(jdbc.sql("SELECT status FROM alert WHERE alert_id = :id").param("id", id)
                .query(String.class).single()).isEqualTo("ENDED");
        assertThat(stateOf(id, "version")).isEqualTo("1");
        assertThat(jdbc.sql("SELECT count(*) FROM alert_watchlist").query(Integer.class).single()).isZero();
    }

    /** 배포 뒤 첫 평가가 확인 불가면 기준을 잡지 못했다 — 옛 해시를 두어 다음 확정 결과에서 울리지 않고 잡는다 (§6.6). */
    @Test
    void 해시가_다를_때_확인_불가면_옛_해시를_둔다() throws Exception {
        UUID id = create(closeAbove("1"));
        jdbc.sql("UPDATE alert_state SET spec_hash = 'before-deploy' WHERE alert_id = :id").param("id", id).update();
        Target t = target(id);
        EvaluationResult unknown = new EvaluationResult(Truth.UNKNOWN, UnknownReason.DATA_MISSING,
                OffsetDateTime.parse("2026-09-24T15:30:00+09:00"), Basis.DAILY,
                List.of(ConditionResult.unknown(UnknownReason.DATA_MISSING)));

        Applied first = writer.apply(t, inputAt(t, LocalDate.of(2026, 9, 24)), unknown);

        assertThat(first.outcome()).isEqualTo(Outcome.APPLIED);
        assertThat(stateOf(id, "spec_hash")).isEqualTo("before-deploy");

        Applied second = apply(first.next());   // 9/25 종가 63,010 ≥ 1 — 참

        assertThat(second.outcome()).isEqualTo(Outcome.APPLIED);
        assertThat(events(id)).isZero();
        assertThat(stateOf(id, "last_known_result")).isEqualTo("TRUE");
        assertThat(stateOf(id, "spec_hash")).isEqualTo(t.specHash());
    }

    /** 만료는 실제 시각으로 판정한다 — 주기 도중에 유효기간이 지난 알림은 반영하지 않는다 (§3.3, 계획 ② A.5). */
    @Test
    void 반영_직전에_유효기간이_지났으면_반영하지_않는다() throws Exception {
        UUID id = create(closeAbove("1"));
        Target t = target(id);
        jdbc.sql("UPDATE alert SET expires_at = '2026-09-28T10:00:00+09' WHERE alert_id = :id").param("id", id).update();

        assertThat(apply(t).outcome()).isEqualTo(Outcome.LOST);
        assertThat(events(id)).isZero();
    }

    /**
     * 한 번만 알림은 알림 행을 먼저 잡는다 — 끄기·삭제·수정·만료와 같은 잠금 순서(alert → alert_state)라
     * 교착하지 않는다 (계획 ② A.6). 다른 알림은 알림 행을 바꾸지 않아 기다리지 않는다.
     */
    @Test
    void 한_번만_알림의_반영은_알림_행이_풀릴_때까지_기다린다() throws Exception {
        UUID id = create(priceReach(SAMSUNG, "CLOSE", "ONE_SHOT", null, "1"));
        Target t = target(id);
        CountDownLatch locked = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        Thread user = new Thread(() -> tx.executeWithoutResult(s -> {
            jdbc.sql("SELECT alert_id FROM alert WHERE alert_id = :id FOR NO KEY UPDATE").param("id", id)
                    .query(UUID.class).single();
            locked.countDown();
            await(release);
        }));
        user.start();
        assertThat(locked.await(10, TimeUnit.SECONDS)).isTrue();

        CompletableFuture<Applied> applying = CompletableFuture.supplyAsync(() -> apply(t));
        Thread.sleep(500);
        assertThat(applying).isNotDone();

        release.countDown();
        user.join();
        assertThat(applying.get(10, TimeUnit.SECONDS).outcome()).isEqualTo(Outcome.ENDED);
    }

    @Test
    void 만료는_켜진_알림과_꺼진_알림을_옮기고_버전을_올린다() throws Exception {
        UUID active = create(closeAbove("1"));
        UUID paused = create(closeAbove("2"));
        UUID later = create(closeAbove("3"));
        commands.pause(YHR, paused);
        jdbc.sql("UPDATE alert SET expires_at = '2026-09-28T10:00:00+09' WHERE alert_id IN (:a, :b)")
                .param("a", active).param("b", paused).update();
        jdbc.sql("UPDATE alert SET expires_at = '2026-10-28T10:00:00+09' WHERE alert_id = :c")
                .param("c", later).update();

        List<ExpiredAlert> expired = writer.expire(FixedClockConfig.NOW.atOffset(java.time.ZoneOffset.UTC));

        assertThat(expired).extracting(ExpiredAlert::alertId).containsExactlyInAnyOrder(active, paused);
        assertThat(statusOf(active)).isEqualTo("EXPIRED");
        assertThat(statusOf(paused)).isEqualTo("EXPIRED");
        assertThat(statusOf(later)).isEqualTo("ACTIVE");
        assertThat(stateOf(active, "version")).isEqualTo("1");
        assertThat(stateOf(paused, "version")).isEqualTo("2");
        assertThat(jdbc.sql("SELECT count(*) FROM alert_watchlist").query(Integer.class).single()).isEqualTo(1);
    }

    // ---- 도우미 ----------------------------------------------------------------

    private UUID create(String body) throws Exception { return commands.create(YHR, json.readTree(body)); }

    private Target target(UUID alertId) {
        RuntimeAlertRow row = store.candidates().stream().filter(r -> r.alertId().equals(alertId))
                .findFirst().orElseThrow();
        Cadence cadence = Cadence.valueOf(row.cadence());
        CompiledTrigger trigger = StoredTriggers.compile(json, row.triggerType(), row.triggerSpec(), cadence)
                .orElseThrow();
        return Target.of(row, trigger, cadence, "삼성전자");
    }

    /** 삼성전자 2026-09-25 종가 시점에서 평가하고 반영한다. */
    private Applied apply(Target t) {
        EvaluationInput in = inputAt(t, LocalDate.of(2026, 9, 25));
        return writer.apply(t, in, ConditionEvaluator.evaluate(t.trigger(), in));
    }

    private EvaluationInput inputAt(Target t, LocalDate date) {
        InstrumentRow samsung = market.instrument(UUID.fromString(SAMSUNG)).orElseThrow();
        return inputs.closeAt(samsung, DataNeeds.of(t.trigger(), Cadence.CLOSE), date);
    }

    private static void await(CountDownLatch latch) {
        try {
            latch.await(10, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private int events(UUID id) {
        return jdbc.sql("SELECT count(*) FROM alert_event WHERE alert_id = :id").param("id", id)
                .query(Integer.class).single();
    }

    private String stateOf(UUID id, String column) {
        return jdbc.sql("SELECT " + column + "::text FROM alert_state WHERE alert_id = :id").param("id", id)
                .query(String.class).optional().orElse(null);
    }

    private String statusOf(UUID id) {
        return jdbc.sql("SELECT status FROM alert WHERE alert_id = :id").param("id", id).query(String.class).single();
    }
}
```

`stateOf`는 값이 SQL `NULL`이면 `null`을 돌려준다(`query(String.class).optional()`은 단일 NULL 값을 빈 값으로 본다).

- [ ] **Step 3: 실패를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.runtime.AlertRuntimeWriterTest'`
Expected: FAIL — `AlertRuntimeWriter` 등이 없어 컴파일 오류.

- [ ] **Step 4: 저장소를 쓴다**

`src/main/java/com/stockproject/portfolio/alert/store/RuntimeAlertRow.java`:

```java
package com.stockproject.portfolio.alert.store;

import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 평가 대상 알림 한 행. 규칙과 평가 상태(version 포함)를 한 SELECT에서 읽는다 — 따로 읽으면 그 사이 커밋된
 * 수정의 새 version을 들고 옛 규칙의 결과를 반영할 수 있다(스펙 §8.2 · §14.4).
 */
public record RuntimeAlertRow(UUID alertId, UUID userId, UUID instrumentId, String name, String cadence,
                              String notifyMode, Integer cooldownMin, String triggerType, String triggerSpec,
                              String lastKnownResult, OffsetDateTime evaluatedAsOf, String specHash, int version) { }
```

`src/main/java/com/stockproject/portfolio/alert/store/ExpiredAlert.java`:

```java
package com.stockproject.portfolio.alert.store;

import java.util.UUID;

/** 이번 주기에 만료로 옮긴 알림. */
public record ExpiredAlert(UUID alertId, UUID instrumentId) { }
```

`src/main/java/com/stockproject/portfolio/alert/store/RuntimeMapper.java`:

```java
package com.stockproject.portfolio.alert.store;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** 평가기의 읽기·쓰기 (스펙 §8.2, 계획 ② A.5 ~ A.7). 사용자 요청 경로가 아니라 스코프가 없다. */
@Mapper
public interface RuntimeMapper {

    @Select("""
            SELECT a.alert_id, a.user_id, a.instrument_id, a.name, a.cadence, a.notify_mode, a.cooldown_min,
                   a.trigger_type, a.trigger_spec::text AS trigger_spec,
                   s.last_known_result, s.evaluated_as_of, s.spec_hash, s.version
              FROM alert a JOIN alert_state s USING (alert_id)
             WHERE a.status = 'ACTIVE' AND a.deleted_at IS NULL
             ORDER BY a.instrument_id, a.cadence, a.alert_id
            """)
    List<RuntimeAlertRow> candidates();

    /** 실제 시각으로 만료를 판정한다. RETURNING이라 두 복제본이 동시에 돌아도 한 알림은 한쪽만 옮긴다. */
    @Select("""
            UPDATE alert SET status = 'EXPIRED', updated_at = #{now}
             WHERE status IN ('ACTIVE', 'PAUSED') AND deleted_at IS NULL AND expires_at <= #{now}
            RETURNING alert_id, instrument_id
            """)
    @Options(flushCache = Options.FlushCachePolicy.TRUE)
    List<ExpiredAlert> expire(@Param("now") OffsetDateTime now);

    /**
     * 읽을 때의 version이 그대로이고, 읽을 때 본 evaluated_as_of가 그대로이며, 데이터 시점이 앞으로 가고,
     * 유효기간이 지나지 않았을 때만 반영한다(계획 ② A.5). 바뀐 행 수를 돌려준다 — 0이면 진 것이다.
     */
    @Update("""
            UPDATE alert_state
               SET last_result = #{lastResult}, last_known_result = #{lastKnown}, unknown_reason = #{reason},
                   evaluated_as_of = #{asOf}, spec_hash = #{specHash}
             WHERE alert_id = #{alertId} AND version = #{version}
               AND evaluated_as_of IS NOT DISTINCT FROM #{prev}::timestamptz
               AND (evaluated_as_of IS NULL OR evaluated_as_of < #{asOf})
               AND EXISTS (SELECT 1 FROM alert a WHERE a.alert_id = alert_state.alert_id
                             AND (a.expires_at IS NULL OR a.expires_at > #{now}))
            """)
    int applyState(@Param("alertId") UUID alertId, @Param("lastResult") String lastResult,
                   @Param("lastKnown") String lastKnown, @Param("reason") String reason,
                   @Param("asOf") OffsetDateTime asOf, @Param("specHash") String specHash,
                   @Param("version") int version, @Param("prev") OffsetDateTime prev,
                   @Param("now") OffsetDateTime now);

    /**
     * 알림 행을 먼저 잡는다. 사용자 변경과 만료가 alert → alert_state 순서로 잠그므로, alert를 바꿀 반영(한 번만
     * 알림의 종료)도 같은 순서를 따른다(계획 ② A.6).
     */
    @Select("SELECT alert_id FROM alert WHERE alert_id = #{alertId} FOR NO KEY UPDATE")
    UUID lockAlert(@Param("alertId") UUID alertId);

    @Select("SELECT max(as_of) FROM alert_event WHERE alert_id = #{alertId}")
    OffsetDateTime lastFiredAsOf(@Param("alertId") UUID alertId);

    /** 한 알림은 한 데이터 시점에 최대 한 번 발화한다. 이미 있으면 넣지 않고 0을 돌려준다(§8.2 ②). */
    @Insert("""
            INSERT INTO alert_event (event_id, alert_id, as_of, fired_at, title, body, lines, observed)
            VALUES (#{eventId}, #{alertId}, #{asOf}, #{firedAt}, #{title}, #{body},
                    CAST(#{lines} AS jsonb), CAST(#{observed} AS jsonb))
            ON CONFLICT ON CONSTRAINT alert_event_once_per_point DO NOTHING
            """)
    int insertEvent(@Param("eventId") UUID eventId, @Param("alertId") UUID alertId,
                    @Param("asOf") OffsetDateTime asOf, @Param("firedAt") OffsetDateTime firedAt,
                    @Param("title") String title, @Param("body") String body,
                    @Param("lines") String lines, @Param("observed") String observed);

    /** v1 푸시는 iOS에서만 동작한다(§9.6). 기기가 없으면 행이 없다 — 발화 기록과 배지는 남는다(§9.5). */
    @Insert("""
            INSERT INTO alert_delivery (event_id, device_id, state, attempts, next_attempt_at)
            SELECT #{eventId}, device_id, 'PENDING', 0, #{now} FROM push_device
             WHERE user_id = #{userId} AND platform = 'IOS'
            """)
    int insertDeliveries(@Param("eventId") UUID eventId, @Param("userId") UUID userId,
                         @Param("now") OffsetDateTime now);

    @Update("UPDATE alert SET status = 'ENDED', updated_at = #{now} WHERE alert_id = #{alertId} AND status = 'ACTIVE'")
    int endOneShot(@Param("alertId") UUID alertId, @Param("now") OffsetDateTime now);
}
```

`src/main/java/com/stockproject/portfolio/alert/store/AlertRuntimeStore.java`:

```java
package com.stockproject.portfolio.alert.store;

import com.stockproject.portfolio.alert.evaluation.EvaluationResult;
import com.stockproject.portfolio.alert.evaluation.Truth;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** 평가기의 저장소. 트랜잭션은 부르는 쪽(AlertRuntimeWriter)이 건다. */
@Repository
public class AlertRuntimeStore {

    private final RuntimeMapper mapper;
    private final AlertStore alerts;

    public AlertRuntimeStore(RuntimeMapper mapper, AlertStore alerts) {
        this.mapper = mapper;
        this.alerts = alerts;
    }

    public List<RuntimeAlertRow> candidates() { return mapper.candidates(); }

    public List<ExpiredAlert> expire(OffsetDateTime now) { return mapper.expire(now); }

    /** 반영했으면 true. false면 다른 복제본이나 사용자 변경에 졌거나 유효기간이 지났다. */
    public boolean applyState(UUID alertId, EvaluationResult r, Truth lastKnown, String specHash, int version,
                              OffsetDateTime prev, OffsetDateTime now) {
        return mapper.applyState(alertId, r.truth().name(), lastKnown.name(),
                r.reason() == null ? null : r.reason().name(), r.asOf(), specHash, version, prev, now) == 1;
    }

    public void lockAlert(UUID alertId) { mapper.lockAlert(alertId); }

    public OffsetDateTime lastFiredAsOf(UUID alertId) { return mapper.lastFiredAsOf(alertId); }

    /** 넣었으면 true. false면 같은 데이터 시점의 발화가 이미 있다. */
    public boolean insertEvent(UUID eventId, UUID alertId, OffsetDateTime asOf, OffsetDateTime firedAt,
                               String title, String body, String linesJson, String observedJson) {
        return mapper.insertEvent(eventId, alertId, asOf, firedAt, title, body, linesJson, observedJson) == 1;
    }

    public void insertDeliveries(UUID eventId, UUID userId, OffsetDateTime now) {
        mapper.insertDeliveries(eventId, userId, now);
    }

    /** 한 번만 알림을 끝낸다. 버전을 올려 다른 복제본이 뒤 시점을 반영하지 못하게 한다(계획 ② A.6). */
    public void endOneShot(UUID alertId, UUID instrumentId, OffsetDateTime now) {
        mapper.endOneShot(alertId, now);
        alerts.bumpVersion(alertId);
        alerts.refreshWatchlist(instrumentId);
    }

    public void bumpVersion(UUID alertId) { alerts.bumpVersion(alertId); }

    public void refreshWatchlist(UUID instrumentId) { alerts.refreshWatchlist(instrumentId); }
}
```

- [ ] **Step 5: 반영 트랜잭션을 쓴다**

`src/main/java/com/stockproject/portfolio/alert/runtime/Target.java`:

```java
package com.stockproject.portfolio.alert.runtime;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.compile.SpecHash;
import com.stockproject.portfolio.alert.evaluation.Truth;
import com.stockproject.portfolio.alert.store.RuntimeAlertRow;

import java.time.OffsetDateTime;

/**
 * 평가 중인 알림. 한 주기에 여러 시점을 따라잡으면 앞 시점의 반영 결과(엣지 기준 · 해시 · 평가 시점)를
 * 이어받는다. version은 읽을 때의 값 그대로다 — 평가는 version을 바꾸지 않는다.
 *
 * @param specHash   지금 코드로 컴파일한 조건의 해시
 * @param storedHash 상태 행의 해시. specHash와 다르면 발화 없이 기준을 다시 잡는다(§6.6)
 */
public record Target(RuntimeAlertRow row, CompiledTrigger trigger, String specHash, String instrumentName,
                     Truth lastKnown, String storedHash, OffsetDateTime evaluatedAsOf) {

    public static Target of(RuntimeAlertRow row, CompiledTrigger trigger, Cadence cadence, String instrumentName) {
        return new Target(row, trigger, SpecHash.of(trigger, cadence), instrumentName,
                Truth.valueOf(row.lastKnownResult()), row.specHash(), row.evaluatedAsOf());
    }

    /** 반영한 뒤의 알림. storedHash는 상태에 쓴 해시다 — 해시가 다르고 결과가 확인 불가면 옛 해시 그대로다(계획 ② A.6). */
    public Target after(Truth known, String storedHash, OffsetDateTime asOf) {
        return new Target(row, trigger, specHash, instrumentName, known, storedHash, asOf);
    }
}
```

`src/main/java/com/stockproject/portfolio/alert/runtime/Outcome.java`:

```java
package com.stockproject.portfolio.alert.runtime;

/**
 * 반영 한 번의 결과. LOST는 다른 복제본이나 사용자 변경에 진 것이고, ENDED는 한 번만 알림이 울려 끝난 것이다.
 * 둘 다 그 알림의 이번 주기를 멈춘다.
 */
public enum Outcome { APPLIED, FIRED, ENDED, LOST }
```

`src/main/java/com/stockproject/portfolio/alert/runtime/Applied.java`:

```java
package com.stockproject.portfolio.alert.runtime;

/** 반영 결과와 다음 시점을 평가할 때 쓸 알림. LOST면 next는 반영 전 그대로다. */
public record Applied(Outcome outcome, Target next) { }
```

`src/main/java/com/stockproject/portfolio/alert/runtime/AlertRuntimeWriter.java`:

```java
package com.stockproject.portfolio.alert.runtime;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.catalog.NotifyMode;
import com.stockproject.portfolio.alert.evaluation.EvaluationInput;
import com.stockproject.portfolio.alert.evaluation.EvaluationResult;
import com.stockproject.portfolio.alert.evaluation.FiringDecision;
import com.stockproject.portfolio.alert.evaluation.FiringRule;
import com.stockproject.portfolio.alert.evaluation.Truth;
import com.stockproject.portfolio.alert.sentence.EventText;
import com.stockproject.portfolio.alert.store.AlertRuntimeStore;
import com.stockproject.portfolio.alert.store.ExpiredAlert;
import com.stockproject.portfolio.alert.store.RuntimeAlertRow;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 평가기의 트랜잭션 (스펙 §8.2 · §14.4). 상태 갱신 · 발화 기록 · 기기별 발송 행 · 한 번만 알림의 종료가
 * 한 트랜잭션이다 — 발화했는데 기록이 없거나, 기록했는데 상태가 그대로인 경우가 생기지 않는다.
 * 상태 행의 잠금이 같은 알림을 반영하려는 다른 복제본을 줄 세운다. 한 번만 알림은 끝낼 때 alert 행을 바꾸므로
 * 알림 행을 먼저 잡는다 — 사용자 변경·만료와 같은 잠금 순서(alert → alert_state)다.
 */
@Service
public class AlertRuntimeWriter {

    private final AlertRuntimeStore store;
    private final ObjectMapper json;
    private final Clock clock;

    public AlertRuntimeWriter(AlertRuntimeStore store, ObjectMapper json, Clock clock) {
        this.store = store;
        this.json = json;
        this.clock = clock;
    }

    @Transactional
    public Applied apply(Target t, EvaluationInput in, EvaluationResult r) {
        RuntimeAlertRow a = t.row();
        NotifyMode mode = NotifyMode.valueOf(a.notifyMode());
        OffsetDateTime now = OffsetDateTime.now(clock);
        if (mode == NotifyMode.ONE_SHOT) store.lockAlert(a.alertId());   // 잠금 순서 alert → alert_state (A.6)

        OffsetDateTime lastFired = mode == NotifyMode.COOLDOWN ? store.lastFiredAsOf(a.alertId()) : null;
        boolean hashMatches = t.specHash().equals(t.storedHash());
        FiringDecision d = FiringRule.decide(mode, a.cooldownMin(), t.lastKnown(), hashMatches, r, lastFired);
        // 해시가 다르고 결과가 확인 불가면 기준을 잡지 못했다 — 옛 해시를 두어 다음 확정 결과에서 다시 잡게 한다(§6.6)
        String hash = !hashMatches && r.truth() == Truth.UNKNOWN ? t.storedHash() : t.specHash();

        if (!store.applyState(a.alertId(), r, d.lastKnown(), hash, a.version(), t.evaluatedAsOf(), now)) {
            return new Applied(Outcome.LOST, t);
        }
        Target next = t.after(d.lastKnown(), hash, r.asOf());
        if (!d.fire()) return new Applied(Outcome.APPLIED, next);

        EventText text = EventText.of(t.instrumentName(), a.name(), t.trigger(), r, in);
        UUID eventId = UUID.randomUUID();
        if (!store.insertEvent(eventId, a.alertId(), r.asOf(), now, text.title(), text.body(),
                write(text.lines()), write(EventText.observed(r)))) {
            return new Applied(Outcome.APPLIED, next);   // 같은 데이터 시점이 이미 울렸다 (§8.2 ②)
        }
        store.insertDeliveries(eventId, a.userId(), now);
        if (mode == NotifyMode.ONE_SHOT) {
            store.endOneShot(a.alertId(), a.instrumentId(), now);
            return new Applied(Outcome.ENDED, next);
        }
        return new Applied(Outcome.FIRED, next);
    }

    /** 만료 전이 (계획 ② A.7). 사용자 변경과 같이 version을 올리고 대상 종목을 갱신한다. */
    @Transactional
    public List<ExpiredAlert> expire(OffsetDateTime now) {
        List<ExpiredAlert> expired = store.expire(now);
        for (ExpiredAlert e : expired) store.bumpVersion(e.alertId());
        expired.stream().map(ExpiredAlert::instrumentId).distinct().forEach(store::refreshWatchlist);
        return expired;
    }

    private String write(Object value) {
        try {
            return json.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("발화 기록을 JSON으로 쓸 수 없다", e);
        }
    }
}
```

- [ ] **Step 6: 통과를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.runtime.AlertRuntimeWriterTest'`
Expected: PASS

- [ ] **Step 7: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/store/RuntimeAlertRow.java \
        src/main/java/com/stockproject/portfolio/alert/store/ExpiredAlert.java \
        src/main/java/com/stockproject/portfolio/alert/store/RuntimeMapper.java \
        src/main/java/com/stockproject/portfolio/alert/store/AlertRuntimeStore.java \
        src/main/java/com/stockproject/portfolio/alert/runtime/Target.java \
        src/main/java/com/stockproject/portfolio/alert/runtime/Outcome.java \
        src/main/java/com/stockproject/portfolio/alert/runtime/Applied.java \
        src/main/java/com/stockproject/portfolio/alert/runtime/AlertRuntimeWriter.java \
        src/test/java/com/stockproject/portfolio/alert/runtime/RuntimeFixtures.java \
        src/test/java/com/stockproject/portfolio/alert/runtime/AlertRuntimeWriterTest.java
git commit -m "feat: 평가 결과를 조건부로 반영하고 발화·발송 행·한 번만 알림 종료를 한 트랜잭션에 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---
## Task 7: 평가기 — 시점 고르기 · 따라잡기 · 장중 최신 하나 · 만료 먼저

스펙 §3.3 · §6.3 · §8.1 · §8.3과 부록 A.4 · A.7.

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/runtime/Point.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/runtime/EvaluationRunner.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/runtime/EvaluationRunnerTest.java`

**Interfaces:**
- Consumes: `AlertRuntimeStore.candidates()` · `AlertRuntimeWriter.apply(...)` · `AlertRuntimeWriter.expire(OffsetDateTime)`(Task 6) · `EvaluationInputFactory.latestCloseDate/closeAt/intradayAt/userAt/unknownInstrument/usesUserScope`(Task 5) · `SnapshotRunMapper.latest/between`(Task 5) · `StoredTriggers.compile`(Task 5) · `MarketDataRepository.instrument/latestDoneAt/tradingDays/closeAt/zone`(①)
- Produces: `EvaluationRunner.tick()` — 한 주기. `EvaluationRunner.CATCH_UP_PER_TICK = 20`. 생성자 `EvaluationRunner(AlertRuntimeStore, AlertRuntimeWriter, EvaluationInputFactory, MarketDataRepository, SnapshotRunMapper, ObjectMapper, Clock)`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/runtime/EvaluationRunnerTest.java`:

```java
package com.stockproject.portfolio.alert.runtime;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.FixedClockConfig;
import com.stockproject.portfolio.alert.data.EvaluationInputFactory;
import com.stockproject.portfolio.alert.data.MarketDataRepository;
import com.stockproject.portfolio.alert.data.SnapshotRunMapper;
import com.stockproject.portfolio.alert.service.AlertCommandService;
import com.stockproject.portfolio.alert.store.AlertRuntimeStore;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;

import java.time.Clock;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.UUID;

import static com.stockproject.portfolio.alert.runtime.RuntimeFixtures.*;
import static org.assertj.core.api.Assertions.assertThat;

/** 평가기 (스펙 §3.3 · §6.3 · §8.1, 계획 ② A.4 · A.7). 시세는 RuntimeFixtures의 설명을 본다. */
@SpringBootTest
@ActiveProfiles("test")
@Import(FixedClockConfig.class)
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class EvaluationRunnerTest {

    private static final String AT_10_20 = "2026-09-28T10:20:00+09:00";

    @Autowired AlertCommandService commands;
    @Autowired AlertRuntimeStore store;
    @Autowired AlertRuntimeWriter writer;
    @Autowired EvaluationInputFactory inputs;
    @Autowired MarketDataRepository market;
    @Autowired SnapshotRunMapper snapshotRuns;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;

    /** 새로 만든 알림은 기다리는 데이터의 최신 DONE 시점 하나만 평가한다 (§6.3). */
    @Test
    void 새_종가_알림은_최신_DONE_시점_하나에서_평가한다() throws Exception {
        UUID id = create(closeAbove("1"));

        runner(AT_10_20).tick();

        assertThat(evaluatedAsOf(id)).isAtSameInstantAs(OffsetDateTime.parse("2026-09-25T15:30:00+09:00"));
        assertThat(bodies(id)).containsExactly("종가 63,010원 ≥ 1원 · 9/25 종가 기준");
    }

    @Test
    void 이미_평가한_시점은_다시_평가하지_않는다() throws Exception {
        UUID id = create(closeAbove("1"));
        runner(AT_10_20).tick();
        jdbc.sql("UPDATE alert_state SET last_result = 'UNKNOWN', unknown_reason = 'DATA_MISSING' WHERE alert_id = :id")
                .param("id", id).update();

        runner(AT_10_20).tick();

        assertThat(lastResult(id)).isEqualTo("UNKNOWN");
        assertThat(bodies(id)).hasSize(1);
    }

    /** 감시 중이던 종가 알림은 밀린 거래일을 날짜 순서대로 모두 평가하고, 발화 문구에 기준일을 넣는다 (§3.3). */
    @Test
    void 밀린_거래일은_날짜_순서대로_평가하고_기준일을_문구에_넣는다() throws Exception {
        UUID id = create(closeAbove("62995"));
        watchingSince(id, "2026-09-22T15:30:00+09");

        runner(AT_10_20).tick();

        // 9/23 62,990 거짓 → 9/24 63,000 참(울림) → 9/25 63,010 참(이어짐)
        assertThat(bodies(id)).containsExactly("종가 63,000원 ≥ 62,995원 · 9/24 종가 기준");
        assertThat(evaluatedAsOf(id)).isAtSameInstantAs(OffsetDateTime.parse("2026-09-25T15:30:00+09:00"));
        assertThat(lastKnown(id)).isEqualTo("TRUE");
    }

    @Test
    void 한_주기에_따라잡는_시점은_스무_개까지다() throws Exception {
        UUID id = create(closeAbove("1"));
        watchingSince(id, "2026-08-03T15:30:00+09");

        runner(AT_10_20).tick();

        // 8/4 ~ 8/31의 평일 20일
        assertThat(evaluatedAsOf(id)).isAtSameInstantAs(OffsetDateTime.parse("2026-08-31T15:30:00+09:00"));
        runner(AT_10_20).tick();
        assertThat(evaluatedAsOf(id)).isAtSameInstantAs(OffsetDateTime.parse("2026-09-25T15:30:00+09:00"));
    }

    /** 장중은 가장 최근 스냅샷 하나만 평가한다 (§3.3). */
    @Test
    void 장중은_최신_스냅샷_하나만_평가한다() throws Exception {
        UUID id = create(priceReach(SAMSUNG, "INTRADAY", "EDGE_REARM", null, "63000"));

        runner(AT_10_20).tick();

        assertThat(evaluatedAsOf(id)).isAtSameInstantAs(OffsetDateTime.parse("2026-09-28T10:15:00+09:00"));
        assertThat(bodies(id)).containsExactly("현재가 63,500원 ≥ 63,000원 · 10:15 기준");
    }

    @Test
    void 허용_지연을_넘은_장중_스냅샷은_평가하지_않는다() throws Exception {
        UUID id = create(priceReach(SAMSUNG, "INTRADAY", "EDGE_REARM", null, "63000"));

        runner("2026-09-28T10:26:00+09:00").tick();

        assertThat(evaluatedAsOf(id)).isNull();
        assertThat(bodies(id)).isEmpty();
    }

    @Test
    void 쿨다운은_마지막_발화부터_N분이_지나면_다시_울린다() throws Exception {
        UUID five = create(priceReach(SAMSUNG, "INTRADAY", "COOLDOWN", 5, "63000"));
        UUID ten = create(priceReach(SAMSUNG, "INTRADAY", "COOLDOWN", 10, "63000"));
        runner(AT_10_20).tick();
        jdbc.sql("""
                INSERT INTO intraday_quote (instrument_id, snapshot_at, price, cum_volume)
                VALUES ('10000000-0000-0000-0000-000000000001', '2026-09-28T10:20:00+09', 63600, 420000)
                """).update();
        jdbc.sql("""
                INSERT INTO market_data_run (market, kind, as_of, state, finished_at)
                VALUES ('KR', 'INTRADAY_QUOTE', '2026-09-28T10:20:00+09', 'DONE', '2026-09-28T10:20:40+09')
                """).update();

        runner("2026-09-28T10:22:00+09:00").tick();

        assertThat(bodies(five)).containsExactly(
                "현재가 63,600원 ≥ 63,000원 · 10:20 기준", "현재가 63,500원 ≥ 63,000원 · 10:15 기준");
        assertThat(bodies(ten)).containsExactly("현재가 63,500원 ≥ 63,000원 · 10:15 기준");
    }

    /** 템플릿·업캐스팅이 바뀐 배포 뒤의 첫 평가 (§6.6). */
    @Test
    void 해시가_다르면_울리지_않고_기준을_다시_잡는다() throws Exception {
        UUID id = create(closeAbove("1"));
        String hash = jdbc.sql("SELECT spec_hash FROM alert_state WHERE alert_id = :id").param("id", id)
                .query(String.class).single();
        jdbc.sql("UPDATE alert_state SET spec_hash = 'before-deploy' WHERE alert_id = :id").param("id", id).update();

        runner(AT_10_20).tick();

        assertThat(bodies(id)).isEmpty();
        assertThat(lastKnown(id)).isEqualTo("TRUE");
        assertThat(jdbc.sql("SELECT spec_hash FROM alert_state WHERE alert_id = :id").param("id", id)
                .query(String.class).single()).isEqualTo(hash);
    }

    /** 만료는 실제 시각으로 판정하고, 만료된 알림은 밀린 거래일도 평가하지 않는다 (§3.3). */
    @Test
    void 만료된_알림은_밀린_거래일도_평가하지_않는다() throws Exception {
        UUID id = create(closeAbove("1"));
        watchingSince(id, "2026-09-22T15:30:00+09");
        jdbc.sql("UPDATE alert SET expires_at = '2026-09-28T09:00:00+09' WHERE alert_id = :id").param("id", id).update();

        runner(AT_10_20).tick();

        assertThat(jdbc.sql("SELECT status FROM alert WHERE alert_id = :id").param("id", id)
                .query(String.class).single()).isEqualTo("EXPIRED");
        assertThat(evaluatedAsOf(id)).isAtSameInstantAs(OffsetDateTime.parse("2026-09-22T15:30:00+09:00"));
        assertThat(bodies(id)).isEmpty();
    }

    @Test
    void 사용자_상태_알림은_보유_스냅샷_신호에서_평가한다() throws Exception {
        UUID id = create(pnlReach(SAMSUNG, "5"));   // yhr의 삼성전자 평가손익률은 7/24에 +8.7%다

        runner(AT_10_20).tick();

        assertThat(evaluatedAsOf(id)).isAtSameInstantAs(OffsetDateTime.parse("2026-07-24T15:30:00+09:00"));
        assertThat(bodies(id)).singleElement().asString().endsWith(" · 7/24 종가 기준");
    }

    @Test
    void 보유_스냅샷_신호가_없으면_사용자_상태_알림을_평가하지_않는다() throws Exception {
        jdbc.sql("DELETE FROM snapshot_run").update();
        UUID id = create(pnlReach(SAMSUNG, "5"));

        runner(AT_10_20).tick();

        assertThat(evaluatedAsOf(id)).isNull();
    }

    /** 저장된 조건 하나가 지금 코드로 읽히지 않아도 다른 알림은 평가한다 (계획 ② A.12 #4). */
    @Test
    void 깨진_조건은_건너뛰고_다른_알림은_평가한다() throws Exception {
        UUID good = create(closeAbove("1"));
        UUID broken = create(closeAbove("2"));
        jdbc.sql("UPDATE alert SET trigger_spec = '{\"preset_key\": \"gone\", \"params\": {}}' WHERE alert_id = :id")
                .param("id", broken).update();

        runner(AT_10_20).tick();

        assertThat(evaluatedAsOf(good)).isNotNull();
        assertThat(evaluatedAsOf(broken)).isNull();
    }

    /** 어떤 날의 데이터가 끝내 DONE이 되지 않으면 그날은 데이터 없음으로 넘기고 이어간다 (§7.1). */
    @Test
    void 끝내_오지_않은_데이터는_그날을_데이터_없음으로_넘긴다() throws Exception {
        UUID id = create(closeAbove("62995"));
        watchingSince(id, "2026-09-22T15:30:00+09");
        jdbc.sql("""
                DELETE FROM market_data_run
                 WHERE market = 'KR' AND kind = 'DAILY_BAR' AND as_of = '2026-09-24T15:30:00+09'
                """).update();

        runner(AT_10_20).tick();

        // 9/23 거짓 → 9/24 데이터 없음(기준은 거짓 그대로) → 9/25 참(울림)
        assertThat(bodies(id)).containsExactly("종가 63,010원 ≥ 62,995원 · 9/25 종가 기준");
        assertThat(evaluatedAsOf(id)).isAtSameInstantAs(OffsetDateTime.parse("2026-09-25T15:30:00+09:00"));
    }

    /** 장중 알림의 이력 피연산자는 직전 거래일 일봉이 DONE이어야 계산한다 (§3.1). */
    @Test
    void 장중_평가는_직전_거래일_일봉이_DONE이_아니면_데이터_없음이다() throws Exception {
        UUID id = create("""
                { "instrument_id": "%s", "name": "급등", "cadence": "INTRADAY", "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "change_move", "params": { "direction": "up", "pct": 1 } } }
                """.formatted(SAMSUNG));
        jdbc.sql("""
                DELETE FROM market_data_run
                 WHERE market = 'KR' AND kind = 'DAILY_BAR' AND as_of = '2026-09-25T15:30:00+09'
                """).update();

        runner(AT_10_20).tick();

        assertThat(lastResult(id)).isEqualTo("UNKNOWN");
        assertThat(jdbc.sql("SELECT unknown_reason FROM alert_state WHERE alert_id = :id").param("id", id)
                .query(String.class).single()).isEqualTo("DATA_MISSING");
        assertThat(evaluatedAsOf(id)).isAtSameInstantAs(OffsetDateTime.parse("2026-09-28T10:15:00+09:00"));
    }

    @Test
    void 삭제된_알림은_평가하지_않는다() throws Exception {
        UUID id = create(closeAbove("1"));
        commands.delete(YHR, id);

        runner(AT_10_20).tick();

        assertThat(evaluatedAsOf(id)).isNull();
        assertThat(bodies(id)).isEmpty();
    }

    /** 미국 장중 시세의 허용 지연은 20분이다 (§16.2). */
    @Test
    void 미국_장중은_허용_지연이_20분이다() throws Exception {
        UUID id = create(priceReach(APPLE, "INTRADAY", "EDGE_REARM", null, "200"));
        jdbc.sql("""
                INSERT INTO intraday_quote (instrument_id, snapshot_at, price, cum_volume)
                VALUES ('10000000-0000-0000-0000-000000000004', '2026-09-28T10:00:00-04', 231, 1000000)
                """).update();
        jdbc.sql("""
                INSERT INTO market_data_run (market, kind, as_of, state, finished_at)
                VALUES ('US', 'INTRADAY_QUOTE', '2026-09-28T10:00:00-04', 'DONE', '2026-09-28T10:01:00-04')
                """).update();

        runner("2026-09-28T10:21:00-04:00").tick();
        assertThat(evaluatedAsOf(id)).isNull();

        runner("2026-09-28T10:19:00-04:00").tick();
        assertThat(evaluatedAsOf(id)).isAtSameInstantAs(OffsetDateTime.parse("2026-09-28T10:00:00-04:00"));
    }

    /** N분 지속은 평가기에서도 그날 스냅샷이 참으로 이어진 구간으로 판정한다 (§4.2). 10:00 ~ 10:15가 모두 참이다. */
    @Test
    void N분_지속은_그날_스냅샷으로_판정한다() throws Exception {
        UUID ten = create(persistAbove("63000", 10));
        UUID thirty = create(persistAbove("63000", 30));

        runner(AT_10_20).tick();

        assertThat(bodies(ten)).containsExactly("현재가 63,500원 ≥ 63,000원 · 15분째 · 10:15 기준");
        assertThat(bodies(thirty)).isEmpty();
        assertThat(lastResult(thirty)).isEqualTo("FALSE");
    }

    @Test
    void 종목_마스터에_없는_종목은_종목_정보_없음이다() throws Exception {
        UUID id = create(closeAbove("1"));
        jdbc.sql("UPDATE alert SET instrument_id = '19999999-0000-0000-0000-000000000000' WHERE alert_id = :id")
                .param("id", id).update();

        runner(AT_10_20).tick();

        assertThat(lastResult(id)).isEqualTo("UNKNOWN");
        assertThat(jdbc.sql("SELECT unknown_reason FROM alert_state WHERE alert_id = :id").param("id", id)
                .query(String.class).single()).isEqualTo("INSTRUMENT_UNKNOWN");
        assertThat(evaluatedAsOf(id)).isAtSameInstantAs(OffsetDateTime.parse("2026-09-25T15:30:00+09:00"));
    }

    // ---- 도우미 ----------------------------------------------------------------

    private EvaluationRunner runner(String now) {
        Clock clock = Clock.fixed(Instant.from(OffsetDateTime.parse(now)), ZoneId.of("Asia/Seoul"));
        return new EvaluationRunner(store, writer, inputs, market, snapshotRuns, json, clock);
    }

    private UUID create(String body) throws Exception { return commands.create(YHR, json.readTree(body)); }

    private static String persistAbove(String price, int minutes) {
        return """
                { "instrument_id": "%s", "name": "지속", "cadence": "INTRADAY", "trigger_type": "COMPOSABLE",
                  "trigger_spec": { "conditions": [ { "left": { "indicator": "price" }, "op": "gte",
                    "right": { "const": %s }, "modifier": { "persist_min": %d } } ] } }
                """.formatted(SAMSUNG, price, minutes);
    }

    /** 이미 감시 중이던 알림으로 만든다 — 그 시점까지 평가했고 엣지 기준은 거짓이다. */
    private void watchingSince(UUID id, String evaluatedAsOf) {
        jdbc.sql("""
                UPDATE alert_state SET evaluated_as_of = CAST(:at AS timestamptz), last_result = 'FALSE',
                       last_known_result = 'FALSE'
                 WHERE alert_id = :id
                """).param("at", evaluatedAsOf).param("id", id).update();
    }

    private OffsetDateTime evaluatedAsOf(UUID id) {
        return jdbc.sql("SELECT evaluated_as_of FROM alert_state WHERE alert_id = :id").param("id", id)
                .query(OffsetDateTime.class).optional().orElse(null);
    }

    private String lastResult(UUID id) {
        return jdbc.sql("SELECT last_result FROM alert_state WHERE alert_id = :id").param("id", id)
                .query(String.class).optional().orElse(null);
    }

    private String lastKnown(UUID id) {
        return jdbc.sql("SELECT last_known_result FROM alert_state WHERE alert_id = :id").param("id", id)
                .query(String.class).single();
    }

    /** 그 알림의 발화 본문, 데이터 시점 내림차순. */
    private List<String> bodies(UUID id) {
        return jdbc.sql("SELECT body FROM alert_event WHERE alert_id = :id ORDER BY as_of DESC").param("id", id)
                .query(String.class).list();
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.runtime.EvaluationRunnerTest'`
Expected: FAIL — `EvaluationRunner`가 없어 컴파일 오류.

- [ ] **Step 3: 시점을 쓴다**

`src/main/java/com/stockproject/portfolio/alert/runtime/Point.java`:

```java
package com.stockproject.portfolio.alert.runtime;

import java.time.LocalDate;
import java.time.OffsetDateTime;

/** 평가할 데이터 시점 하나 (계획 ② A.4). */
public sealed interface Point {

    /** 종가 알림의 거래일(시장 현지 날짜). */
    record Close(LocalDate date) implements Point { }

    /** 장중 알림의 스냅샷 시각 — 그 시장 INTRADAY_QUOTE 신호의 as_of. */
    record Intraday(OffsetDateTime at) implements Point { }

    /** 사용자 상태 지표의 보유 스냅샷 기준일. done은 그날 snapshot_run이 있는가다. */
    record Holding(LocalDate date, boolean done) implements Point { }
}
```

- [ ] **Step 4: 평가기를 쓴다**

`src/main/java/com/stockproject/portfolio/alert/runtime/EvaluationRunner.java`:

```java
package com.stockproject.portfolio.alert.runtime;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.DataKind;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.compile.DataNeeds;
import com.stockproject.portfolio.alert.data.EvaluationInputFactory;
import com.stockproject.portfolio.alert.data.InstrumentRow;
import com.stockproject.portfolio.alert.data.MarketDataRepository;
import com.stockproject.portfolio.alert.data.SnapshotRunMapper;
import com.stockproject.portfolio.alert.evaluation.ConditionEvaluator;
import com.stockproject.portfolio.alert.evaluation.EvaluationInput;
import com.stockproject.portfolio.alert.store.AlertRuntimeStore;
import com.stockproject.portfolio.alert.store.RuntimeAlertRow;
import com.stockproject.portfolio.alert.validation.StoredTriggers;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.domain.Market;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/**
 * 평가기 (스펙 §8.1, 계획 ② A.4). 주기마다 만료를 먼저 옮기고, ACTIVE이고 삭제되지 않은 알림마다 평가할 시점을
 * 골라 앞에서부터 평가·반영한다. 신호를 처리했는지는 따로 기록하지 않는다 — 알림마다의 evaluated_as_of가 그
 * 기록이라, 신호가 온 뒤에 만든 알림도 다음 주기에 평가된다. 메모리에 들고 있는 상태가 없어 재시작해도 이어간다.
 */
@Component
public class EvaluationRunner {

    private static final Logger log = LoggerFactory.getLogger(EvaluationRunner.class);

    /** 한 주기에 한 알림이 평가하는 시점의 상한. 나머지는 다음 주기에 이어진다. */
    static final int CATCH_UP_PER_TICK = 20;

    private final AlertRuntimeStore store;
    private final AlertRuntimeWriter writer;
    private final EvaluationInputFactory inputs;
    private final MarketDataRepository market;
    private final SnapshotRunMapper snapshotRuns;
    private final ObjectMapper json;
    private final Clock clock;

    public EvaluationRunner(AlertRuntimeStore store, AlertRuntimeWriter writer, EvaluationInputFactory inputs,
                            MarketDataRepository market, SnapshotRunMapper snapshotRuns, ObjectMapper json,
                            Clock clock) {
        this.store = store;
        this.writer = writer;
        this.inputs = inputs;
        this.market = market;
        this.snapshotRuns = snapshotRuns;
        this.json = json;
        this.clock = clock;
    }

    /** 한 주기. 만료 전이나 알림 하나의 실패가 나머지를 막지 않는다. */
    public void tick() {
        OffsetDateTime now = OffsetDateTime.now(clock);
        try {
            writer.expire(now);
        } catch (RuntimeException e) {
            log.warn("만료 전이 실패 — 이번 주기의 평가는 이어간다", e);
        }
        TickCache cache = new TickCache();
        for (RuntimeAlertRow row : store.candidates()) {
            try {
                evaluate(row, now, cache);
            } catch (RuntimeException e) {
                log.warn("알림 평가 실패 alert_id={}", row.alertId(), e);
            }
        }
    }

    private void evaluate(RuntimeAlertRow row, OffsetDateTime now, TickCache cache) {
        Cadence cadence = Cadence.valueOf(row.cadence());
        Optional<CompiledTrigger> compiled = StoredTriggers.compile(json, row.triggerType(), row.triggerSpec(), cadence);
        if (compiled.isEmpty()) {
            log.warn("저장된 조건을 읽을 수 없어 평가하지 않는다 alert_id={}", row.alertId());
            return;
        }
        CompiledTrigger trigger = compiled.get();
        InstrumentRow instrument = cache.instruments
                .computeIfAbsent(row.instrumentId(), market::instrument).orElse(null);
        Market m = instrument == null ? Market.KR : instrument.marketEnum();
        Set<DataKind> needs = DataNeeds.of(trigger, cadence);

        Target t = Target.of(row, trigger, cadence, instrument == null ? null : instrument.name());
        for (Point p : points(trigger, cadence, m, needs, row.evaluatedAsOf(), now)) {
            InputKey key = new InputKey(row.instrumentId(), p instanceof Point.Holding ? row.userId() : null,
                    cadence, needs, p);
            EvaluationInput in = cache.inputs.computeIfAbsent(key, k -> input(p, instrument, cadence, needs, row));
            Applied applied = writer.apply(t, in, ConditionEvaluator.evaluate(trigger, in));
            if (applied.outcome() == Outcome.LOST || applied.outcome() == Outcome.ENDED) return;
            t = applied.next();
        }
    }

    // ---- 시점 고르기 (계획 ② A.4) --------------------------------------------------

    private List<Point> points(CompiledTrigger trigger, Cadence cadence, Market m, Set<DataKind> needs,
                               OffsetDateTime evaluated, OffsetDateTime now) {
        if (EvaluationInputFactory.usesUserScope(trigger)) return holdingPoints(evaluated);
        if (needs.isEmpty()) return List.of();
        if (cadence == Cadence.INTRADAY) return intradayPoint(m, evaluated, now);

        Optional<LocalDate> target = inputs.latestCloseDate(m, needs);
        if (target.isEmpty()) return List.of();
        if (evaluated == null) return List.of(new Point.Close(target.get()));   // §6.3 — 최신 시점 하나
        LocalDate from = localDate(evaluated, m).plusDays(1);
        if (from.isAfter(target.get())) return List.of();
        return market.tradingDays(m, from, target.get()).stream().limit(CATCH_UP_PER_TICK)
                .<Point>map(Point.Close::new).toList();
    }

    /** 장중은 가장 최근 스냅샷 하나. 허용 지연을 넘었으면 평가하지 않는다 — 지난 시각의 발화가 지금 가격으로 오해된다(§3.3). */
    private List<Point> intradayPoint(Market m, OffsetDateTime evaluated, OffsetDateTime now) {
        Optional<OffsetDateTime> quote = market.latestDoneAt(m, DataKind.INTRADAY_QUOTE);
        if (quote.isEmpty()) return List.of();
        if (Duration.between(quote.get(), now).compareTo(EvaluationInput.allowedGap(m)) > 0) return List.of();
        if (evaluated != null && !evaluated.isBefore(quote.get())) return List.of();
        return List.of(new Point.Intraday(quote.get()));
    }

    /** 사용자 상태 지표는 snapshot_run이 신호다. 행이 없는 국내 거래일은 PORTFOLIO_SNAPSHOT 없이 평가한다. */
    private List<Point> holdingPoints(OffsetDateTime evaluated) {
        LocalDate latest = snapshotRuns.latest();
        if (latest == null) return List.of();
        if (evaluated == null) return List.of(new Point.Holding(latest, true));
        LocalDate from = localDate(evaluated, Market.KR).plusDays(1);
        if (from.isAfter(latest)) return List.of();
        Set<LocalDate> done = Set.copyOf(snapshotRuns.between(from, latest));
        return market.tradingDays(Market.KR, from, latest).stream().limit(CATCH_UP_PER_TICK)
                .<Point>map(d -> new Point.Holding(d, done.contains(d))).toList();
    }

    // ---- 입력 -------------------------------------------------------------------

    private EvaluationInput input(Point p, InstrumentRow instrument, Cadence cadence, Set<DataKind> needs,
                                  RuntimeAlertRow row) {
        return switch (p) {
            case Point.Close c -> instrument == null
                    ? EvaluationInputFactory.unknownInstrument(cadence, c.date(), market.closeAt(Market.KR, c.date()))
                    : inputs.closeAt(instrument, needs, c.date());
            case Point.Intraday i -> instrument == null
                    ? EvaluationInputFactory.unknownInstrument(cadence, localDate(i.at(), Market.KR), i.at())
                    : inputs.intradayAt(instrument, needs, i.at());
            case Point.Holding h -> instrument == null
                    ? EvaluationInputFactory.unknownInstrument(cadence, h.date(), market.closeAt(Market.KR, h.date()))
                    : inputs.userAt(new UserScope(row.userId()), instrument, cadence, h.date(),
                            h.done() ? Set.of() : EnumSet.of(DataKind.PORTFOLIO_SNAPSHOT));
        };
    }

    private static LocalDate localDate(OffsetDateTime at, Market m) {
        return at.atZoneSameInstant(MarketDataRepository.zone(m)).toLocalDate();
    }

    /** 같은 주기 안에서 같은 입력은 한 번만 읽는다(스펙 §8.1). 사용자 상태 입력만 사용자에 따라 다르다. */
    private record InputKey(UUID instrumentId, UUID userId, Cadence cadence, Set<DataKind> needs, Point point) { }

    private static final class TickCache {
        final Map<UUID, Optional<InstrumentRow>> instruments = new HashMap<>();
        final Map<InputKey, EvaluationInput> inputs = new HashMap<>();
    }
}
```

- [ ] **Step 5: 통과를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.runtime.*'`
Expected: PASS

- [ ] **Step 6: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/runtime/Point.java \
        src/main/java/com/stockproject/portfolio/alert/runtime/EvaluationRunner.java \
        src/test/java/com/stockproject/portfolio/alert/runtime/EvaluationRunnerTest.java
git commit -m "feat: 평가기가 밀린 종가를 따라잡고 장중은 최신 스냅샷 하나만 평가한다

만료를 평가보다 먼저 옮기고, 읽을 수 없는 조건은 그 알림만 건너뛴다.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---
## Task 8: 미리보기와 평가기가 같은 결과를 낸다

①이 넘긴 요구(부록 A.12 마지막 줄). 같은 알림을 미리보기 API로 보고, 평가기로 한 주기 돌린 뒤 상태와 발화를 견준다. 새 제품 코드는 없다 — 어긋나면 그것이 버그다.

**Files:**
- Test: `src/test/java/com/stockproject/portfolio/alert/runtime/PreviewEvaluatorParityTest.java`

**Interfaces:**
- Consumes: `POST /alerts` · `POST /alerts/preview`(①) · `EvaluationRunner.tick()`(Task 7) · `AlertApiClient`(① 테스트 도우미)

- [ ] **Step 1: 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/runtime/PreviewEvaluatorParityTest.java`:

```java
package com.stockproject.portfolio.alert.runtime;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.AlertApiClient;
import com.stockproject.portfolio.alert.FixedClockConfig;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.web.servlet.MockMvc;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 미리보기에서 ✓인데 울리지 않는 일이 없어야 한다 (결정 기록 "알림 계산", 계획 ② A.12).
 * 지금(2026-09-28 10:20) 미리보기가 고른 데이터 시점과 평가기가 고른 시점이 같고, 그 시점의 결과·사유·관측값 줄이 같다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(FixedClockConfig.class)
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class PreviewEvaluatorParityTest {

    private static final String SAMSUNG = "10000000-0000-0000-0000-000000000001";
    private static final String HYNIX = "10000000-0000-0000-0000-000000000002";
    private static final String NAVER = "10000000-0000-0000-0000-000000000003";
    private static final String APPLE = "10000000-0000-0000-0000-000000000004";

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;
    @Autowired EvaluationRunner runner;
    AlertApiClient api;

    @BeforeEach
    void setUp() { api = new AlertApiClient(mockMvc, json); }

    static Stream<String> alerts() {
        return Stream.of(
                preset(SAMSUNG, "CLOSE", "price_reach", "{ \"direction\": \"up\", \"price\": 63000 }"),
                preset(SAMSUNG, "INTRADAY", "price_reach", "{ \"direction\": \"up\", \"price\": 63400 }"),
                preset(SAMSUNG, "INTRADAY", "volume_surge", "{ \"n\": 20, \"multiple\": 3 }"),
                preset(SAMSUNG, "CLOSE", "ma_cross", "{ \"short\": 5, \"long\": 20, \"direction\": \"golden\" }"),
                preset(SAMSUNG, "CLOSE", "box_breakout",
                        "{ \"window_days\": 20, \"max_range_pct\": 15, \"direction\": \"up\" }"),
                preset(SAMSUNG, "CLOSE", "investor_streak",
                        "{ \"investor\": \"foreign\", \"side\": \"buy\", \"days\": 3 }"),
                preset(SAMSUNG, "CLOSE", "pnl_reach", "{ \"direction\": \"profit\", \"pct\": 5 }"),
                preset(NAVER, "CLOSE", "price_reach", "{ \"direction\": \"up\", \"price\": 1 }"),
                preset(APPLE, "CLOSE", "price_reach", "{ \"direction\": \"up\", \"price\": 200 }"),
                rsi(SAMSUNG, 14, 70),
                rsi(HYNIX, 14, 70));
    }

    @ParameterizedTest
    @MethodSource("alerts")
    void 미리보기와_평가기의_결과가_같다(String body) throws Exception {
        JsonNode current = api.post("/alerts/preview", "yhr", body).body().get("current");
        UUID id = UUID.fromString(api.post("/alerts", "yhr", body).body().get("alert_id").asText());

        runner.tick();

        assertThat(stateText(id, "last_result")).isEqualTo(current.get("result").asText());
        assertThat(stateText(id, "unknown_reason")).isEqualTo(firstUnknownReason(current));
        OffsetDateTime evaluated = jdbc.sql("SELECT evaluated_as_of FROM alert_state WHERE alert_id = :id")
                .param("id", id).query(OffsetDateTime.class).single();
        assertThat(OffsetDateTime.parse(current.get("as_of").asText())).isAtSameInstantAs(evaluated);

        if ("TRUE".equals(current.get("result").asText())) {
            String lines = jdbc.sql("SELECT lines::text FROM alert_event WHERE alert_id = :id").param("id", id)
                    .query(String.class).single();
            assertThat(json.readTree(lines)).isEqualTo(json.valueToTree(texts(current)));
        }
    }

    // ---- 도우미 ----------------------------------------------------------------

    private String stateText(UUID id, String column) {
        return jdbc.sql("SELECT " + column + " FROM alert_state WHERE alert_id = :id").param("id", id)
                .query(String.class).optional().orElse(null);
    }

    private static String firstUnknownReason(JsonNode current) {
        for (JsonNode line : current.get("conditions")) {
            if (!line.get("unknown_reason").isNull()) return line.get("unknown_reason").asText();
        }
        return null;
    }

    private static List<String> texts(JsonNode current) {
        List<String> out = new ArrayList<>();
        for (JsonNode line : current.get("conditions")) out.add(line.get("text").asText());
        return out;
    }

    private static String preset(String instrument, String cadence, String key, String params) {
        return """
                { "instrument_id": "%s", "name": "동등성", "cadence": "%s", "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "%s", "params": %s } }
                """.formatted(instrument, cadence, key, params);
    }

    private static String rsi(String instrument, int n, int level) {
        return """
                { "instrument_id": "%s", "name": "RSI", "cadence": "CLOSE", "trigger_type": "COMPOSABLE",
                  "trigger_spec": { "conditions": [ { "left": { "indicator": "rsi", "indicator_params": { "n": %d } },
                    "op": "gte", "right": { "const": %d } } ] } }
                """.formatted(instrument, n, level);
    }
}
```

`@ParameterizedTest`는 `spring-boot-starter-test`의 `junit-jupiter-params`에 있다.

- [ ] **Step 2: 통과를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.runtime.PreviewEvaluatorParityTest'`
Expected: PASS (11개 경우 전부)

어긋나는 경우가 나오면 superpowers:systematic-debugging으로 원인을 찾는다. 순수 계산(`ConditionEvaluator` · `SentenceWriter`)은 둘이 같은 코드라 원인이 아니다 — 두 경로가 고른 데이터 시점이나 입력(`EvaluationInputFactory`의 메서드 선택)을 먼저 본다. 고치는 곳이 스펙과 다른 동작을 요구하면 멈춰서 보고한다.

- [ ] **Step 3: 커밋한다**

```bash
git add src/test/java/com/stockproject/portfolio/alert/runtime/PreviewEvaluatorParityTest.java
git commit -m "test: 미리보기와 평가기가 같은 시점에서 같은 결과를 내는지 본다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---
## Task 9: Expo 게이트웨이

부록 A.9의 Expo 사실을 코드로 옮긴다. 실제 Expo 서버에 보내지 않는다 — 테스트는 `MockRestServiceServer`로 한다.

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/delivery/PushProperties.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/delivery/PushMessage.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/delivery/PushTicket.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/delivery/PushReceipt.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/delivery/PushFailure.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/delivery/PushGateway.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/delivery/ExpoPushGateway.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/delivery/ExpoPushGatewayTest.java`

**Interfaces:**
- Produces:
  - `PushProperties(boolean enabled, String expoUrl, String accessToken)` — `@ConfigurationProperties("portfolio.alert.push")`, `expoUrl` 기본 `https://exp.host`
  - `PushMessage(String to, String title, String body, UUID eventId)` — `toString()`에 토큰이 없다
  - `PushTicket(String id, String error)` · `PushTicket.ok(String id)` · `PushTicket.error(String code)` · `ok()`
  - `PushReceipt(String error)` · `PushReceipt.OK` · `PushReceipt.error(String code)` · `ok()`
  - `PushFailure(boolean retryable, String reason)` (`RuntimeException`) · `retryable()` · `reason()`
  - `PushGateway.send(List<PushMessage>) → List<PushTicket>` (요청 순서대로) · `PushGateway.receipts(List<String> ticketIds) → Map<String, PushReceipt>` · 상수 `PushGateway.DEVICE_NOT_REGISTERED = "DeviceNotRegistered"` · `PushGateway.RATE_EXCEEDED = "MessageRateExceeded"`
  - `ExpoPushGateway(RestClient.Builder, PushProperties)` (`@Component`)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/delivery/ExpoPushGatewayTest.java`:

```java
package com.stockproject.portfolio.alert.delivery;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.test.web.client.ResponseCreator;
import org.springframework.web.client.RestClient;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.headerDoesNotExist;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withBadRequest;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withServerError;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

/** Expo Push API 호출 (스펙 §9.3 · §9.4, 계획 ② A.9). */
class ExpoPushGatewayTest {

    private static final UUID EVENT = UUID.fromString("70000000-0000-0000-0000-000000000001");

    @Test
    void 보낸_순서대로_티켓을_받는다() {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("https://exp.host/--/api/v2/push/send"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE))
                .andExpect(headerDoesNotExist(HttpHeaders.AUTHORIZATION))
                .andExpect(jsonPath("$[0].to").value("ExponentPushToken[a]"))
                .andExpect(jsonPath("$[0].title").value("삼성전자 · 가격 도달"))
                .andExpect(jsonPath("$[0].body").value("현재가 70,200원 ≥ 70,000원 · 10:15 기준"))
                .andExpect(jsonPath("$[0].sound").value("default"))
                .andExpect(jsonPath("$[0].data.event_id").value(EVENT.toString()))
                .andExpect(jsonPath("$[1].to").value("ExponentPushToken[b]"))
                .andRespond(withSuccess("""
                        { "data": [ { "status": "ok", "id": "ticket-1" },
                                    { "status": "error", "message": "not registered",
                                      "details": { "error": "DeviceNotRegistered" } } ] }
                        """, MediaType.APPLICATION_JSON));

        List<PushTicket> tickets = gateway(builder, null).send(List.of(
                message("ExponentPushToken[a]"), message("ExponentPushToken[b]")));

        assertThat(tickets).containsExactly(PushTicket.ok("ticket-1"), PushTicket.error("DeviceNotRegistered"));
        server.verify();
    }

    @Test
    void 접근_토큰이_있으면_붙인다() {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("https://exp.host/--/api/v2/push/send"))
                .andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer expo-secret"))
                .andRespond(withSuccess("{ \"data\": [ { \"status\": \"ok\", \"id\": \"t\" } ] }",
                        MediaType.APPLICATION_JSON));

        gateway(builder, "expo-secret").send(List.of(message("ExponentPushToken[a]")));

        server.verify();
    }

    @Test
    void 요청_한도_초과와_서버_오류만_다시_보낼_수_있다() {
        assertThat(failureOf(withStatus(HttpStatus.TOO_MANY_REQUESTS)).retryable()).isTrue();
        assertThat(failureOf(withServerError()).retryable()).isTrue();
        PushFailure badRequest = failureOf(withBadRequest());
        assertThat(badRequest.retryable()).isFalse();
        assertThat(badRequest.reason()).isEqualTo("HTTP 400");
    }

    @Test
    void 영수증을_티켓별로_받는다() {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("https://exp.host/--/api/v2/push/getReceipts"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(jsonPath("$.ids[0]").value("t-1"))
                .andExpect(jsonPath("$.ids[1]").value("t-2"))
                .andRespond(withSuccess("""
                        { "data": { "t-1": { "status": "ok" },
                                    "t-2": { "status": "error", "details": { "error": "MessageTooBig" } } } }
                        """, MediaType.APPLICATION_JSON));

        Map<String, PushReceipt> receipts = gateway(builder, null).receipts(List.of("t-1", "t-2", "t-3"));

        assertThat(receipts).containsOnly(Map.entry("t-1", PushReceipt.OK),
                Map.entry("t-2", PushReceipt.error("MessageTooBig")));
        server.verify();
    }

    @Test
    void 메시지를_문자열로_바꿔도_푸시_토큰이_드러나지_않는다() {
        assertThat(message("ExponentPushToken[secret]").toString()).doesNotContain("secret");
    }

    // ---- 도우미 ----------------------------------------------------------------

    private static PushFailure failureOf(ResponseCreator response) {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("https://exp.host/--/api/v2/push/send")).andRespond(response);
        ExpoPushGateway gateway = gateway(builder, null);
        Throwable thrown = catchThrowable(() -> gateway.send(List.of(message("ExponentPushToken[a]"))));
        assertThat(thrown).isInstanceOf(PushFailure.class);
        return (PushFailure) thrown;
    }

    private static ExpoPushGateway gateway(RestClient.Builder builder, String accessToken) {
        return new ExpoPushGateway(builder, new PushProperties(true, null, accessToken));
    }

    private static PushMessage message(String token) {
        return new PushMessage(token, "삼성전자 · 가격 도달", "현재가 70,200원 ≥ 70,000원 · 10:15 기준", EVENT);
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.delivery.ExpoPushGatewayTest'`
Expected: FAIL — `ExpoPushGateway` 등이 없어 컴파일 오류.

- [ ] **Step 3: 값 타입을 쓴다**

`src/main/java/com/stockproject/portfolio/alert/delivery/PushProperties.java`:

```java
package com.stockproject.portfolio.alert.delivery;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 푸시 발송 설정 (계획 ② A.3 · A.9). enabled가 false면 발송기와 영수증 확인기가 아무것도 보내지 않는다.
 * accessToken은 Expo 프로젝트에 향상된 보안을 켰을 때만 필요하고, Secret에서 환경변수로만 들어온다.
 */
@ConfigurationProperties("portfolio.alert.push")
public record PushProperties(boolean enabled, String expoUrl, String accessToken) {

    public PushProperties {
        if (expoUrl == null || expoUrl.isBlank()) expoUrl = "https://exp.host";
    }
}
```

`src/main/java/com/stockproject/portfolio/alert/delivery/PushMessage.java`:

```java
package com.stockproject.portfolio.alert.delivery;

import java.util.UUID;

/** 기기 하나로 보낼 푸시. to는 Expo 푸시 토큰이라 문자열로 바꿀 때 빼낸다 — 로그에 원문을 남기지 않는다(§9.7). */
public record PushMessage(String to, String title, String body, UUID eventId) {

    @Override
    public String toString() {
        return "PushMessage[eventId=" + eventId + "]";
    }
}
```

`src/main/java/com/stockproject/portfolio/alert/delivery/PushTicket.java`:

```java
package com.stockproject.portfolio.alert.delivery;

/** Expo 접수 티켓. 성공이면 id, 실패면 error(Expo 오류 코드)가 있다. */
public record PushTicket(String id, String error) {

    public static PushTicket ok(String id) { return new PushTicket(id, null); }

    public static PushTicket error(String code) { return new PushTicket(null, code); }

    public boolean ok() { return error == null; }
}
```

`src/main/java/com/stockproject/portfolio/alert/delivery/PushReceipt.java`:

```java
package com.stockproject.portfolio.alert.delivery;

/** Expo 전달 영수증. 실패면 error(Expo 오류 코드)가 있다. */
public record PushReceipt(String error) {

    public static final PushReceipt OK = new PushReceipt(null);

    public static PushReceipt error(String code) { return new PushReceipt(code); }

    public boolean ok() { return error == null; }
}
```

`src/main/java/com/stockproject/portfolio/alert/delivery/PushFailure.java`:

```java
package com.stockproject.portfolio.alert.delivery;

/** 요청 자체의 실패. reason은 HTTP 상태나 Expo 오류 코드 같은 짧은 사유다 — 응답 본문을 담지 않는다. */
public class PushFailure extends RuntimeException {

    private final boolean retryable;
    private final String reason;

    public PushFailure(boolean retryable, String reason) {
        super(reason);
        this.retryable = retryable;
        this.reason = reason;
    }

    public boolean retryable() { return retryable; }

    public String reason() { return reason; }
}
```

`src/main/java/com/stockproject/portfolio/alert/delivery/PushGateway.java`:

```java
package com.stockproject.portfolio.alert.delivery;

import java.util.List;
import java.util.Map;

/** 푸시 발송 서비스. 발송기와 영수증 확인기는 이 경계만 안다 — 테스트는 가짜로 바꾼다. */
public interface PushGateway {

    /** 그 토큰은 더 이상 그 기기에 닿지 않는다. 기기를 지운다. */
    String DEVICE_NOT_REGISTERED = "DeviceNotRegistered";
    /** 기기 하나에 너무 자주 보냈다. 간격을 늘려 다시 보낸다. */
    String RATE_EXCEEDED = "MessageRateExceeded";

    /** 요청 순서대로 티켓을 돌려준다. 요청 자체가 실패하면 PushFailure를 던진다. 한 번에 최대 100건이다. */
    List<PushTicket> send(List<PushMessage> messages);

    /** 티켓 id → 영수증. 아직 영수증이 없는 티켓은 결과에 없다. 한 번에 최대 1000건이다. */
    Map<String, PushReceipt> receipts(List<String> ticketIds);
}
```

- [ ] **Step 4: Expo 게이트웨이를 쓴다**

`src/main/java/com/stockproject/portfolio/alert/delivery/ExpoPushGateway.java`:

```java
package com.stockproject.portfolio.alert.delivery;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Expo Push API (docs.expo.dev "Sending notifications with Expo's Push API", 계획 ② A.9).
 * HTTP 429 · 5xx · 연결 실패 · 시간 초과는 다시 보낼 수 있는 실패, 그 밖의 4xx는 다시 보내도 소용없는 실패다.
 * 시간 제한은 Boot가 만드는 RestClient.Builder에 설정으로 건다(spring.http.client.connect-timeout · read-timeout).
 */
@Component
public class ExpoPushGateway implements PushGateway {

    static final String SEND = "/--/api/v2/push/send";
    static final String RECEIPTS = "/--/api/v2/push/getReceipts";

    private final RestClient http;

    public ExpoPushGateway(RestClient.Builder builder, PushProperties props) {
        RestClient.Builder b = builder.baseUrl(props.expoUrl())
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE);
        if (props.accessToken() != null && !props.accessToken().isBlank()) {
            b = b.defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + props.accessToken());
        }
        this.http = b.build();
    }

    @Override
    public List<PushTicket> send(List<PushMessage> messages) {
        JsonNode response = post(SEND, messages.stream().map(ExpoPushGateway::payload).toList());
        JsonNode data = response.path("data");
        if (!data.isArray() || data.size() != messages.size()) throw requestFailure(response);
        List<PushTicket> tickets = new ArrayList<>(data.size());
        for (JsonNode ticket : data) {
            tickets.add("ok".equals(ticket.path("status").asText())
                    ? PushTicket.ok(ticket.path("id").asText())
                    : PushTicket.error(errorCode(ticket)));
        }
        return tickets;
    }

    @Override
    public Map<String, PushReceipt> receipts(List<String> ticketIds) {
        JsonNode response = post(RECEIPTS, Map.of("ids", ticketIds));
        JsonNode data = response.path("data");
        if (!data.isObject()) throw requestFailure(response);
        Map<String, PushReceipt> out = new HashMap<>();
        data.fields().forEachRemaining(e -> out.put(e.getKey(),
                "ok".equals(e.getValue().path("status").asText()) ? PushReceipt.OK
                        : PushReceipt.error(errorCode(e.getValue()))));
        return out;
    }

    /** 스펙 §9.3의 페이로드에 iOS 기본 알림음을 더한다. data에는 event_id만 싣는다. */
    private static Map<String, Object> payload(PushMessage m) {
        Map<String, Object> p = new LinkedHashMap<>();
        p.put("to", m.to());
        p.put("title", m.title());
        p.put("body", m.body());
        p.put("sound", "default");
        p.put("data", Map.of("event_id", m.eventId().toString()));
        return p;
    }

    private JsonNode post(String path, Object body) {
        try {
            return http.post().uri(path).contentType(MediaType.APPLICATION_JSON).body(body)
                    .exchange((request, response) -> {
                        int status = response.getStatusCode().value();
                        if (status == 429 || status >= 500) throw new PushFailure(true, "HTTP " + status);
                        if (status >= 400) throw new PushFailure(false, "HTTP " + status);
                        return response.bodyTo(JsonNode.class);
                    });
        } catch (RestClientException e) {
            throw new PushFailure(true, "연결 실패");
        }
    }

    /** 응답이 data 없이 errors만 담았다. 요청 한도 초과만 다시 보낼 수 있다. */
    private static PushFailure requestFailure(JsonNode response) {
        String code = response.path("errors").path(0).path("code").asText(null);
        return new PushFailure("TOO_MANY_REQUESTS".equals(code), code == null ? "응답 형식 오류" : code);
    }

    private static String errorCode(JsonNode result) {
        return result.path("details").path("error").asText("UNKNOWN");
    }
}
```

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.delivery.ExpoPushGatewayTest'`
Expected: PASS

- [ ] **Step 6: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/delivery/ \
        src/test/java/com/stockproject/portfolio/alert/delivery/ExpoPushGatewayTest.java
git commit -m "feat: Expo Push API로 보내고 영수증을 묻는 게이트웨이를 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: 발송기 · 영수증 확인기 · 기기 정리

스펙 §8.2 ④ · §9.2 · §9.3 · §9.4와 부록 A.9. Expo 호출은 DB 트랜잭션 밖에서 한다.

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/store/PendingDelivery.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/store/SentDelivery.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/store/DeliveryMapper.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/delivery/DeliveryDispatcher.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/delivery/ReceiptChecker.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/delivery/FakePushGateway.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/delivery/DeliveryFixtures.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/delivery/DeliveryDispatcherTest.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/delivery/ReceiptCheckerTest.java`

**Interfaces:**
- Consumes: `PushGateway` · `PushProperties` · `PushMessage` · `PushTicket` · `PushReceipt` · `PushFailure`(Task 9). `TransactionTemplate`(Spring Boot 자동 구성).
- Produces:
  - `DeliveryDispatcher(DeliveryMapper, PushGateway, PushProperties, TransactionTemplate, Clock)` · `dispatchOnce() → int`(집은 행 수, 요청 자체가 실패하면 0) · `DeliveryDispatcher.BATCH = 100` · `static Duration backoff(int attempts)`
  - `ReceiptChecker(DeliveryMapper, PushGateway, PushProperties, TransactionTemplate, Clock)` · `checkOnce() → int`

- [ ] **Step 1: 가짜 게이트웨이와 픽스처를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/delivery/FakePushGateway.java`:

```java
package com.stockproject.portfolio.alert.delivery;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

/**
 * 테스트의 푸시 서비스. 기본은 모든 메시지를 받아 "ticket-<event_id>" 티켓을 주고, 영수증은 아직 없다.
 * 호출이 DB 트랜잭션 안에서 왔는지도 적는다 — Expo 호출은 트랜잭션 밖이어야 한다(계획 ② A.9).
 */
public class FakePushGateway implements PushGateway {

    public final List<List<PushMessage>> sent = new ArrayList<>();
    public final List<List<String>> asked = new ArrayList<>();
    public final List<Boolean> calledInTransaction = new ArrayList<>();
    public Function<PushMessage, PushTicket> onSend;
    public Function<String, PushReceipt> onReceipt;
    public PushFailure failure;

    public FakePushGateway() { reset(); }

    public void reset() {
        sent.clear();
        asked.clear();
        calledInTransaction.clear();
        onSend = m -> PushTicket.ok("ticket-" + m.eventId());
        onReceipt = id -> null;
        failure = null;
    }

    @Override
    public List<PushTicket> send(List<PushMessage> messages) {
        calledInTransaction.add(TransactionSynchronizationManager.isActualTransactionActive());
        sent.add(List.copyOf(messages));
        if (failure != null) throw failure;
        return messages.stream().map(onSend).toList();
    }

    @Override
    public Map<String, PushReceipt> receipts(List<String> ticketIds) {
        calledInTransaction.add(TransactionSynchronizationManager.isActualTransactionActive());
        asked.add(List.copyOf(ticketIds));
        if (failure != null) throw failure;
        Map<String, PushReceipt> out = new HashMap<>();
        for (String id : ticketIds) {
            PushReceipt r = onReceipt.apply(id);
            if (r != null) out.put(id, r);
        }
        return out;
    }

    @TestConfiguration
    public static class Config {
        @Bean
        @Primary
        FakePushGateway fakePushGateway() { return new FakePushGateway(); }
    }
}
```

`src/test/java/com/stockproject/portfolio/alert/delivery/DeliveryFixtures.java`:

```java
package com.stockproject.portfolio.alert.delivery;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.service.AlertCommandService;
import com.stockproject.portfolio.alert.service.DeviceService;
import com.stockproject.portfolio.auth.UserScope;
import org.springframework.jdbc.core.simple.JdbcClient;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 발송 테스트의 발화·기기·발송 행. 발화는 평가기를 거치지 않고 바로 넣는다. 지금은 2026-09-28 10:20이다. */
final class DeliveryFixtures {

    static final UserScope YHR = new UserScope(UUID.fromString("40000000-0000-0000-0000-000000000001"));
    static final UserScope JDH = new UserScope(UUID.fromString("40000000-0000-0000-0000-000000000002"));
    static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-28T10:20:00+09:00");

    private final AlertCommandService commands;
    private final DeviceService devices;
    private final ObjectMapper json;
    private final JdbcClient jdbc;

    DeliveryFixtures(AlertCommandService commands, DeviceService devices, ObjectMapper json, JdbcClient jdbc) {
        this.commands = commands;
        this.devices = devices;
        this.json = json;
        this.jdbc = jdbc;
    }

    /** 종가 알림의 발화. 발송 기한은 fired_at + 12시간이다. */
    UUID event(String firedAt) throws Exception { return event("CLOSE", firedAt); }

    /** 장중 알림의 발화. 발송 기한은 fired_at + 30분이다. */
    UUID intradayEvent(String firedAt) throws Exception { return event("INTRADAY", firedAt); }

    private UUID event(String cadence, String firedAt) throws Exception {
        UUID alertId = commands.create(YHR, json.readTree("""
                { "instrument_id": "10000000-0000-0000-0000-000000000001", "name": "가격", "cadence": "%s",
                  "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "price_reach", "params": { "direction": "up", "price": 1 } } }
                """.formatted(cadence)));
        UUID eventId = UUID.randomUUID();
        jdbc.sql("""
                INSERT INTO alert_event (event_id, alert_id, as_of, fired_at, title, body, lines, observed)
                VALUES (:e, :a, '2026-09-25T15:30:00+09', CAST(:f AS timestamptz), '삼성전자 · 가격 도달',
                        '종가 63,010원 ≥ 1원 · 9/25 종가 기준', '["종가 63,010원 ≥ 1원"]', '{"conditions": []}')
                """).param("e", eventId).param("a", alertId).param("f", firedAt).update();
        return eventId;
    }

    UUID device(String token) { return devices.register(YHR, token, "IOS"); }

    void pending(UUID eventId, UUID deviceId, int attempts, String nextAttemptAt) {
        jdbc.sql("""
                INSERT INTO alert_delivery (event_id, device_id, state, attempts, next_attempt_at)
                VALUES (:e, :d, 'PENDING', :n, CAST(:at AS timestamptz))
                """).param("e", eventId).param("d", deviceId).param("n", attempts).param("at", nextAttemptAt).update();
    }

    /** 다른 발송기가 집어 보내는 중인 행. leaseUntil이 지나면 다시 집을 수 있다. */
    void sending(UUID eventId, UUID deviceId, int attempts, String leaseUntil) {
        jdbc.sql("""
                INSERT INTO alert_delivery (event_id, device_id, state, attempts, next_attempt_at)
                VALUES (:e, :d, 'SENDING', :n, CAST(:at AS timestamptz))
                """).param("e", eventId).param("d", deviceId).param("n", attempts).param("at", leaseUntil).update();
    }

    void sent(UUID eventId, UUID deviceId, String ticket, String sentAt, String receiptAt) {
        jdbc.sql("""
                INSERT INTO alert_delivery (event_id, device_id, state, attempts, next_attempt_at, expo_ticket_id, sent_at)
                VALUES (:e, :d, 'SENT', 1, CAST(:at AS timestamptz), :t, CAST(:sentAt AS timestamptz))
                """).param("e", eventId).param("d", deviceId).param("at", receiptAt).param("t", ticket)
                .param("sentAt", sentAt).update();
    }

    String column(UUID eventId, UUID deviceId, String column) {
        return jdbc.sql("SELECT " + column + "::text FROM alert_delivery WHERE event_id = :e AND device_id = :d")
                .param("e", eventId).param("d", deviceId).query(String.class).optional().orElse(null);
    }

    OffsetDateTime time(UUID eventId, UUID deviceId, String column) {
        return jdbc.sql("SELECT " + column + " FROM alert_delivery WHERE event_id = :e AND device_id = :d")
                .param("e", eventId).param("d", deviceId).query(OffsetDateTime.class).optional().orElse(null);
    }

    int deliveries() { return jdbc.sql("SELECT count(*) FROM alert_delivery").query(Integer.class).single(); }

    boolean deviceExists(UUID deviceId) {
        return jdbc.sql("SELECT count(*) FROM push_device WHERE device_id = :d").param("d", deviceId)
                .query(Integer.class).single() == 1;
    }
}
```

- [ ] **Step 2: 실패하는 발송기 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/delivery/DeliveryDispatcherTest.java`:

```java
package com.stockproject.portfolio.alert.delivery;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.FixedClockConfig;
import com.stockproject.portfolio.alert.service.AlertCommandService;
import com.stockproject.portfolio.alert.service.DeviceService;
import com.stockproject.portfolio.alert.store.DeliveryMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Clock;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import static com.stockproject.portfolio.alert.delivery.DeliveryFixtures.JDH;
import static com.stockproject.portfolio.alert.delivery.DeliveryFixtures.NOW;
import static org.assertj.core.api.Assertions.assertThat;

/** 발송기 (스펙 §8.2 ④ · §9.2 · §9.3, 계획 ② A.9). 지금은 2026-09-28 10:20이다. */
@SpringBootTest(properties = "portfolio.alert.push.enabled=true")
@ActiveProfiles("test")
@Import({FixedClockConfig.class, FakePushGateway.Config.class})
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class DeliveryDispatcherTest {

    private static final String DUE = "2026-09-28T10:00:00+09";
    private static final String FIRED = "2026-09-28T10:00:00+09";

    @Autowired DeliveryDispatcher dispatcher;
    @Autowired DeliveryMapper mapper;
    @Autowired FakePushGateway gateway;
    @Autowired AlertCommandService commands;
    @Autowired DeviceService devices;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;
    @Autowired TransactionTemplate tx;
    @Autowired Clock clock;
    DeliveryFixtures f;

    @BeforeEach
    void setUp() {
        gateway.reset();
        f = new DeliveryFixtures(commands, devices, json, jdbc);
    }

    @Test
    void 대기_행을_트랜잭션_밖에서_보내고_영수증을_물을_시각을_적는다() throws Exception {
        UUID event = f.event(FIRED);
        UUID a = f.device("ExponentPushToken[a]");
        UUID b = f.device("ExponentPushToken[b]");
        f.pending(event, a, 0, DUE);
        f.pending(event, b, 0, DUE);

        assertThat(dispatcher.dispatchOnce()).isEqualTo(2);

        assertThat(gateway.calledInTransaction).containsExactly(false);
        assertThat(gateway.sent).singleElement().satisfies(batch -> {
            assertThat(batch).extracting(PushMessage::to)
                    .containsExactlyInAnyOrder("ExponentPushToken[a]", "ExponentPushToken[b]");
            assertThat(batch).extracting(PushMessage::title).containsOnly("삼성전자 · 가격 도달");
            assertThat(batch).extracting(PushMessage::eventId).containsOnly(event);
        });
        for (UUID device : new UUID[] {a, b}) {
            assertThat(f.column(event, device, "state")).isEqualTo("SENT");
            assertThat(f.column(event, device, "attempts")).isEqualTo("1");
            assertThat(f.column(event, device, "expo_ticket_id")).isEqualTo("ticket-" + event);
            assertThat(f.time(event, device, "sent_at")).isAtSameInstantAs(NOW);
            assertThat(f.time(event, device, "next_attempt_at")).isAtSameInstantAs(NOW.plusMinutes(15));
        }
    }

    @Test
    void 기기_미등록이면_결과를_쓴_뒤_기기를_지우고_같은_묶음의_다른_행은_보낸다() throws Exception {
        UUID event = f.event(FIRED);
        UUID gone = f.device("ExponentPushToken[gone]");
        UUID alive = f.device("ExponentPushToken[alive]");
        f.pending(event, gone, 0, DUE);
        f.pending(event, alive, 0, DUE);
        gateway.onSend = m -> m.to().equals("ExponentPushToken[gone]")
                ? PushTicket.error(PushGateway.DEVICE_NOT_REGISTERED) : PushTicket.ok("t-" + m.eventId());

        dispatcher.dispatchOnce();

        assertThat(f.deviceExists(gone)).isFalse();
        assertThat(f.column(event, gone, "state")).isNull();
        assertThat(f.column(event, alive, "state")).isEqualTo("SENT");
        assertThat(jdbc.sql("SELECT count(*) FROM alert_event").query(Integer.class).single()).isEqualTo(1);
    }

    @Test
    void 일시_실패는_간격을_늘려_다시_보내고_다섯_번째_시도에서_끝내며_이어_보내지_않는다() throws Exception {
        UUID event = f.event(FIRED);
        UUID first = f.device("ExponentPushToken[first]");
        UUID last = f.device("ExponentPushToken[last]");
        f.pending(event, first, 0, DUE);
        f.pending(event, last, 4, DUE);
        gateway.failure = new PushFailure(true, "HTTP 503");

        assertThat(dispatcher.dispatchOnce()).isZero();

        assertThat(f.column(event, first, "state")).isEqualTo("PENDING");
        assertThat(f.column(event, first, "attempts")).isEqualTo("1");
        assertThat(f.column(event, first, "last_error")).isEqualTo("HTTP 503");
        assertThat(f.time(event, first, "next_attempt_at")).isAtSameInstantAs(NOW.plusSeconds(30));
        assertThat(f.column(event, last, "state")).isEqualTo("FAILED");
        assertThat(f.column(event, last, "attempts")).isEqualTo("5");
        assertThat(DeliveryDispatcher.backoff(1)).hasSeconds(30);
        assertThat(DeliveryDispatcher.backoff(4)).hasMinutes(4);
    }

    @Test
    void 다시_보내도_소용없는_실패는_바로_끝낸다() throws Exception {
        UUID event = f.event(FIRED);
        UUID device = f.device("ExponentPushToken[a]");
        f.pending(event, device, 0, DUE);
        gateway.onSend = m -> PushTicket.error("InvalidCredentials");

        dispatcher.dispatchOnce();

        assertThat(f.column(event, device, "state")).isEqualTo("FAILED");
        assertThat(f.column(event, device, "last_error")).isEqualTo("InvalidCredentials");
    }

    /** 지난 시각의 장중 값이 지금 가격으로 오해되지 않게 한다 — 장중 30분, 종가 12시간 (계획 ② A.9). */
    @Test
    void 발송_기한이_지난_대기_행은_보내지_않고_끝낸다() throws Exception {
        UUID staleIntraday = f.intradayEvent("2026-09-28T09:40:00+09");
        UUID freshIntraday = f.intradayEvent("2026-09-28T10:00:00+09");
        UUID staleClose = f.event("2026-09-27T21:00:00+09");
        UUID device = f.device("ExponentPushToken[a]");
        f.pending(staleIntraday, device, 0, DUE);
        f.pending(freshIntraday, device, 0, DUE);
        f.pending(staleClose, device, 0, DUE);

        dispatcher.dispatchOnce();

        assertThat(f.column(staleIntraday, device, "state")).isEqualTo("FAILED");
        assertThat(f.column(staleIntraday, device, "last_error")).isEqualTo("EXPIRED");
        assertThat(f.column(staleClose, device, "last_error")).isEqualTo("EXPIRED");
        assertThat(f.column(freshIntraday, device, "state")).isEqualTo("SENT");
        assertThat(gateway.sent).singleElement().satisfies(batch ->
                assertThat(batch).extracting(PushMessage::eventId).containsExactly(freshIntraday));
    }

    /** 공용 기기에서 로그아웃하지 못한 사람의 푸시가 다음 사람에게 가면 안 된다 (§9.2 · §14.5). */
    @Test
    void 기기가_다른_사용자에게_옮겨졌으면_이전_사용자의_푸시를_보내지_않는다() throws Exception {
        UUID event = f.event(FIRED);
        UUID device = f.device("ExponentPushToken[shared]");
        f.pending(event, device, 0, DUE);
        assertThat(devices.register(JDH, "ExponentPushToken[shared]", "IOS")).isEqualTo(device);

        assertThat(dispatcher.dispatchOnce()).isZero();

        assertThat(gateway.sent).isEmpty();
        assertThat(f.column(event, device, "state")).isEqualTo("FAILED");
        assertThat(f.column(event, device, "last_error")).isEqualTo("OWNER_CHANGED");
    }

    /** 집은 뒤 결과를 쓰기 전에 파드가 죽으면 임대가 끝난 뒤 다시 보낸다. 임대 중인 행은 건너뛴다. */
    @Test
    void 임대가_끝난_전송_중_행은_다시_보내고_임대_중이면_건너뛴다() throws Exception {
        UUID event = f.event(FIRED);
        UUID abandoned = f.device("ExponentPushToken[abandoned]");
        UUID inFlight = f.device("ExponentPushToken[in-flight]");
        f.sending(event, abandoned, 1, "2026-09-28T10:10:00+09");
        f.sending(event, inFlight, 1, "2026-09-28T10:21:00+09");

        assertThat(dispatcher.dispatchOnce()).isEqualTo(1);

        assertThat(f.column(event, abandoned, "state")).isEqualTo("SENT");
        assertThat(f.column(event, abandoned, "attempts")).isEqualTo("2");
        assertThat(f.column(event, inFlight, "state")).isEqualTo("SENDING");
    }

    @Test
    void 다음_시도_시각이_오지_않은_행은_집지_않는다() throws Exception {
        UUID event = f.event(FIRED);
        f.pending(event, f.device("ExponentPushToken[a]"), 1, "2026-09-28T10:30:00+09");

        assertThat(dispatcher.dispatchOnce()).isZero();
        assertThat(gateway.sent).isEmpty();
    }

    @Test
    void 다른_복제본이_집고_있는_행은_건너뛴다() throws Exception {
        UUID event = f.event(FIRED);
        f.pending(event, f.device("ExponentPushToken[a]"), 0, DUE);
        CountDownLatch locked = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        Thread other = new Thread(() -> tx.executeWithoutResult(s -> {
            mapper.lockDue(NOW, 5, DeliveryDispatcher.BATCH);
            locked.countDown();
            try {
                release.await(10, TimeUnit.SECONDS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }));
        other.start();
        assertThat(locked.await(10, TimeUnit.SECONDS)).isTrue();

        assertThat(dispatcher.dispatchOnce()).isZero();

        release.countDown();
        other.join();
    }

    @Test
    void 꺼져_있으면_보내지_않는다() throws Exception {
        UUID event = f.event(FIRED);
        f.pending(event, f.device("ExponentPushToken[a]"), 0, DUE);
        DeliveryDispatcher off = new DeliveryDispatcher(mapper, gateway, new PushProperties(false, null, null), tx, clock);

        assertThat(off.dispatchOnce()).isZero();
        assertThat(gateway.sent).isEmpty();
        assertThat(f.deliveries()).isEqualTo(1);
    }
}
```

- [ ] **Step 3: 실패하는 영수증 확인기 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/delivery/ReceiptCheckerTest.java`:

```java
package com.stockproject.portfolio.alert.delivery;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.FixedClockConfig;
import com.stockproject.portfolio.alert.service.AlertCommandService;
import com.stockproject.portfolio.alert.service.DeviceService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

import static com.stockproject.portfolio.alert.delivery.DeliveryFixtures.NOW;
import static org.assertj.core.api.Assertions.assertThat;

/** 영수증 확인기 (스펙 §9.4, 계획 ② A.9). 지금은 2026-09-28 10:20이다. */
@SpringBootTest(properties = "portfolio.alert.push.enabled=true")
@ActiveProfiles("test")
@Import({FixedClockConfig.class, FakePushGateway.Config.class})
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class ReceiptCheckerTest {

    private static final String SENT_AT = "2026-09-28T10:00:00+09";
    private static final String DUE = "2026-09-28T10:15:00+09";

    @Autowired ReceiptChecker checker;
    @Autowired FakePushGateway gateway;
    @Autowired AlertCommandService commands;
    @Autowired DeviceService devices;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;
    DeliveryFixtures f;
    UUID event;
    UUID device;

    @BeforeEach
    void setUp() throws Exception {
        gateway.reset();
        f = new DeliveryFixtures(commands, devices, json, jdbc);
        event = f.event("2026-09-28T09:59:00+09");
        device = f.device("ExponentPushToken[a]");
    }

    @Test
    void 정상_영수증이면_티켓을_비운다() {
        f.sent(event, device, "t-1", SENT_AT, DUE);
        gateway.onReceipt = id -> PushReceipt.OK;

        assertThat(checker.checkOnce()).isEqualTo(1);

        assertThat(gateway.asked).containsExactly(List.of("t-1"));
        assertThat(gateway.calledInTransaction).containsExactly(false);
        assertThat(f.column(event, device, "state")).isEqualTo("SENT");
        assertThat(f.column(event, device, "expo_ticket_id")).isNull();
    }

    @Test
    void 기기_미등록_영수증이면_결과를_쓴_뒤_기기를_지운다() {
        f.sent(event, device, "t-1", SENT_AT, DUE);
        gateway.onReceipt = id -> PushReceipt.error(PushGateway.DEVICE_NOT_REGISTERED);

        checker.checkOnce();

        assertThat(f.deviceExists(device)).isFalse();
        assertThat(f.deliveries()).isZero();
    }

    @Test
    void 그_밖의_오류_영수증이면_실패로_적는다() {
        f.sent(event, device, "t-1", SENT_AT, DUE);
        gateway.onReceipt = id -> PushReceipt.error("MessageTooBig");

        checker.checkOnce();

        assertThat(f.column(event, device, "state")).isEqualTo("FAILED");
        assertThat(f.column(event, device, "last_error")).isEqualTo("MessageTooBig");
        assertThat(f.column(event, device, "expo_ticket_id")).isNull();
    }

    @Test
    void 영수증이_아직_없으면_15분_뒤에_다시_묻는다() {
        f.sent(event, device, "t-1", SENT_AT, DUE);

        checker.checkOnce();

        assertThat(f.column(event, device, "expo_ticket_id")).isEqualTo("t-1");
        assertThat(f.time(event, device, "next_attempt_at")).isAtSameInstantAs(NOW.plusMinutes(15));
    }

    /** Expo는 영수증을 보낸 뒤 24시간 보관한다 — 발화 시각이 아니라 보낸 시각으로 잰다. */
    @Test
    void 보낸_지_24시간이_지나도_영수증이_없으면_그만_묻는다() throws Exception {
        UUID old = f.event("2026-09-26T09:00:00+09");
        UUID other = f.device("ExponentPushToken[b]");
        f.sent(old, other, "t-old", "2026-09-27T09:00:00+09", DUE);
        UUID late = f.event("2026-09-26T09:00:00+09");
        UUID third = f.device("ExponentPushToken[c]");
        f.sent(late, third, "t-late", "2026-09-28T09:00:00+09", DUE);

        checker.checkOnce();

        assertThat(f.column(old, other, "expo_ticket_id")).isNull();
        assertThat(f.column(old, other, "state")).isEqualTo("SENT");
        assertThat(f.column(late, third, "expo_ticket_id")).isEqualTo("t-late");
    }

    @Test
    void 조회가_실패하면_아무것도_바꾸지_않는다() {
        f.sent(event, device, "t-1", SENT_AT, DUE);
        gateway.failure = new PushFailure(true, "HTTP 503");

        assertThat(checker.checkOnce()).isZero();

        assertThat(f.column(event, device, "expo_ticket_id")).isEqualTo("t-1");
        assertThat(f.time(event, device, "next_attempt_at"))
                .isAtSameInstantAs(OffsetDateTime.parse("2026-09-28T10:15:00+09:00"));
    }

    @Test
    void 물을_시각이_오지_않은_티켓은_묻지_않는다() {
        f.sent(event, device, "t-1", SENT_AT, "2026-09-28T10:30:00+09");

        assertThat(checker.checkOnce()).isZero();
        assertThat(gateway.asked).isEmpty();
    }
}
```

- [ ] **Step 4: 실패를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.delivery.*'`
Expected: FAIL — `DeliveryDispatcher` 등이 없어 컴파일 오류.

- [ ] **Step 5: 발송 행 저장소를 쓴다**

`src/main/java/com/stockproject/portfolio/alert/store/PendingDelivery.java`:

```java
package com.stockproject.portfolio.alert.store;

import java.util.UUID;

/**
 * 보낼 발송 행. attempts는 집기 전의 시도 횟수다 — 집으면 하나 오른다.
 * token은 Expo 푸시 토큰이라 문자열로 바꿀 때 빼낸다(§9.7).
 */
public record PendingDelivery(UUID eventId, UUID deviceId, int attempts, String token, String title, String body) {

    @Override
    public String toString() {
        return "PendingDelivery[eventId=" + eventId + ", deviceId=" + deviceId + ", attempts=" + attempts + "]";
    }
}
```

`src/main/java/com/stockproject/portfolio/alert/store/SentDelivery.java`:

```java
package com.stockproject.portfolio.alert.store;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 영수증을 물을 발송 행. sentAt으로 Expo의 영수증 보관 기간(보낸 뒤 24시간)을 판정한다. */
public record SentDelivery(UUID eventId, UUID deviceId, String ticketId, OffsetDateTime sentAt) { }
```

`src/main/java/com/stockproject/portfolio/alert/store/DeliveryMapper.java`:

```java
package com.stockproject.portfolio.alert.store;

import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 기기별 발송 행 (스펙 §9, 계획 ② A.9). 집을 때 FOR UPDATE SKIP LOCKED로 잠그고 SENDING으로 바꿔 커밋한다 —
 * 한 발송 행은 한 복제본만 처리한다(§8.2 ④). 결과는 "아직 SENDING이고 집을 때의 attempts 그대로"일 때만 쓴다.
 */
@Mapper
public interface DeliveryMapper {

    /** 발송 기한이 지난 대기 행을 끝낸다 — 장중 발화와 종가 발화의 기한이 다르다. */
    @Update("""
            UPDATE alert_delivery d SET state = 'FAILED', last_error = 'EXPIRED'
              FROM alert_event e JOIN alert a ON a.alert_id = e.alert_id
             WHERE e.event_id = d.event_id AND d.state IN ('PENDING', 'SENDING')
               AND e.fired_at < CASE WHEN a.cadence = 'INTRADAY' THEN #{intradayCutoff}::timestamptz
                                     ELSE #{closeCutoff}::timestamptz END
            """)
    int expireStale(@Param("intradayCutoff") OffsetDateTime intradayCutoff,
                    @Param("closeCutoff") OffsetDateTime closeCutoff);

    /** 기기가 다른 사용자에게 옮겨졌으면 이전 사용자의 대기 행을 보내지 않는다(§9.2 · §14.5). */
    @Update("""
            UPDATE alert_delivery d SET state = 'FAILED', last_error = 'OWNER_CHANGED'
              FROM push_device p, alert_event e, alert a
             WHERE p.device_id = d.device_id AND e.event_id = d.event_id AND a.alert_id = e.alert_id
               AND d.state IN ('PENDING', 'SENDING') AND p.user_id <> a.user_id
            """)
    int failOwnerChanged();

    /** 임대가 끝났는데 시도 횟수를 다 쓴 전송 중 행. */
    @Update("""
            UPDATE alert_delivery SET state = 'FAILED', last_error = 'LEASE_EXPIRED'
             WHERE state = 'SENDING' AND next_attempt_at <= #{now} AND attempts >= #{maxAttempts}
            """)
    int failAbandoned(@Param("now") OffsetDateTime now, @Param("maxAttempts") int maxAttempts);

    /** 대기 행과 임대가 끝난 전송 중 행. 기기의 지금 사용자와 알림의 사용자가 같은 행만 집는다. */
    @Select("""
            SELECT d.event_id, d.device_id, d.attempts, p.expo_push_token AS token, e.title, e.body
              FROM alert_delivery d
              JOIN push_device p ON p.device_id = d.device_id
              JOIN alert_event e ON e.event_id = d.event_id
              JOIN alert a ON a.alert_id = e.alert_id AND a.user_id = p.user_id
             WHERE d.state IN ('PENDING', 'SENDING') AND d.next_attempt_at <= #{now}
               AND d.attempts < #{maxAttempts}
             ORDER BY d.next_attempt_at, d.event_id, d.device_id
             LIMIT #{limit}
               FOR UPDATE OF d SKIP LOCKED
            """)
    List<PendingDelivery> lockDue(@Param("now") OffsetDateTime now, @Param("maxAttempts") int maxAttempts,
                                  @Param("limit") int limit);

    @Update("""
            UPDATE alert_delivery SET state = 'SENDING', attempts = attempts + 1, next_attempt_at = #{leaseUntil}
             WHERE event_id = #{eventId} AND device_id = #{deviceId}
            """)
    void markSending(@Param("eventId") UUID eventId, @Param("deviceId") UUID deviceId,
                     @Param("leaseUntil") OffsetDateTime leaseUntil);

    /** 보냈다. SENT의 next_attempt_at은 영수증을 물을 시각이다. */
    @Update("""
            UPDATE alert_delivery
               SET state = 'SENT', expo_ticket_id = #{ticketId}, sent_at = #{now},
                   next_attempt_at = #{receiptAt}, last_error = NULL
             WHERE event_id = #{eventId} AND device_id = #{deviceId}
               AND state = 'SENDING' AND attempts = #{attempts}
            """)
    int markSent(@Param("eventId") UUID eventId, @Param("deviceId") UUID deviceId, @Param("attempts") int attempts,
                 @Param("ticketId") String ticketId, @Param("now") OffsetDateTime now,
                 @Param("receiptAt") OffsetDateTime receiptAt);

    @Update("""
            UPDATE alert_delivery SET state = 'PENDING', next_attempt_at = #{nextAt}, last_error = #{error}
             WHERE event_id = #{eventId} AND device_id = #{deviceId}
               AND state = 'SENDING' AND attempts = #{attempts}
            """)
    int retry(@Param("eventId") UUID eventId, @Param("deviceId") UUID deviceId, @Param("attempts") int attempts,
              @Param("nextAt") OffsetDateTime nextAt, @Param("error") String error);

    @Update("""
            UPDATE alert_delivery SET state = 'FAILED', last_error = #{error}
             WHERE event_id = #{eventId} AND device_id = #{deviceId}
               AND state = 'SENDING' AND attempts = #{attempts}
            """)
    int failSending(@Param("eventId") UUID eventId, @Param("deviceId") UUID deviceId,
                    @Param("attempts") int attempts, @Param("error") String error);

    /** 그 토큰은 더 이상 기기에 닿지 않는다. 그 기기의 발송 행은 ON DELETE CASCADE로 함께 지워진다. */
    @Delete("DELETE FROM push_device WHERE device_id = #{deviceId}")
    int deleteDevice(@Param("deviceId") UUID deviceId);

    /** 잠그지 않는다 — 두 복제본이 같은 티켓을 물어도 결과 기록이 같다. */
    @Select("""
            SELECT event_id, device_id, expo_ticket_id AS ticket_id, sent_at FROM alert_delivery
             WHERE state = 'SENT' AND expo_ticket_id IS NOT NULL AND next_attempt_at <= #{now}
             ORDER BY next_attempt_at, event_id, device_id
             LIMIT #{limit}
            """)
    List<SentDelivery> receiptsDue(@Param("now") OffsetDateTime now, @Param("limit") int limit);

    @Update("""
            UPDATE alert_delivery SET expo_ticket_id = NULL
             WHERE event_id = #{eventId} AND device_id = #{deviceId} AND expo_ticket_id = #{ticketId}
            """)
    int clearTicket(@Param("eventId") UUID eventId, @Param("deviceId") UUID deviceId,
                    @Param("ticketId") String ticketId);

    @Update("""
            UPDATE alert_delivery SET next_attempt_at = #{nextAt}
             WHERE event_id = #{eventId} AND device_id = #{deviceId} AND expo_ticket_id = #{ticketId}
            """)
    int postponeReceipt(@Param("eventId") UUID eventId, @Param("deviceId") UUID deviceId,
                        @Param("ticketId") String ticketId, @Param("nextAt") OffsetDateTime nextAt);

    @Update("""
            UPDATE alert_delivery SET state = 'FAILED', last_error = #{error}, expo_ticket_id = NULL
             WHERE event_id = #{eventId} AND device_id = #{deviceId} AND expo_ticket_id = #{ticketId}
            """)
    int failReceipt(@Param("eventId") UUID eventId, @Param("deviceId") UUID deviceId,
                    @Param("ticketId") String ticketId, @Param("error") String error);
}
```

- [ ] **Step 6: 발송기를 쓴다**

`src/main/java/com/stockproject/portfolio/alert/delivery/DeliveryDispatcher.java`:

```java
package com.stockproject.portfolio.alert.delivery;

import com.stockproject.portfolio.alert.store.DeliveryMapper;
import com.stockproject.portfolio.alert.store.PendingDelivery;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Clock;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * 발송기 (스펙 §9.3, 계획 ② A.9). 집기 트랜잭션 → 트랜잭션 밖에서 Expo 전송 → 기록 트랜잭션 → 기기 정리.
 * Expo가 받은 뒤 커밋이 실패해 묶음 전체가 다시 나가는 일이 없고, Expo가 느려도 행 잠금과 DB 연결을 쥐지 않는다.
 * 발송 실패는 발화를 취소하지 않는다 — 발화 기록과 배지는 그대로다.
 */
@Component
public class DeliveryDispatcher {

    private static final Logger log = LoggerFactory.getLogger(DeliveryDispatcher.class);

    /** Expo가 한 요청에 받는 최대 메시지 수. */
    public static final int BATCH = 100;
    static final int MAX_ATTEMPTS = 5;
    /** 집은 행의 임대. 전송 시간 제한(연결 5초 + 읽기 15초)보다 넉넉하다. */
    static final Duration LEASE = Duration.ofMinutes(2);
    /** Expo는 보낸 뒤 15분에 영수증을 묻기를 권장한다. */
    static final Duration RECEIPT_DELAY = Duration.ofMinutes(15);
    static final Duration INTRADAY_DEADLINE = Duration.ofMinutes(30);
    static final Duration CLOSE_DEADLINE = Duration.ofHours(12);

    private final DeliveryMapper mapper;
    private final PushGateway gateway;
    private final PushProperties props;
    private final TransactionTemplate tx;
    private final Clock clock;

    public DeliveryDispatcher(DeliveryMapper mapper, PushGateway gateway, PushProperties props,
                              TransactionTemplate tx, Clock clock) {
        this.mapper = mapper;
        this.gateway = gateway;
        this.props = props;
        this.tx = tx;
        this.clock = clock;
    }

    /**
     * 한 묶음을 보낸다. 집은 행 수를 돌려준다 — BATCH와 같으면 남은 행이 더 있을 수 있다.
     * 요청 자체가 실패하면 0을 돌려줘 이어 보내기를 멈춘다 — 장애 중에 대기열 전체의 시도 횟수를 쓰지 않는다.
     */
    public int dispatchOnce() {
        if (!props.enabled()) return 0;
        OffsetDateTime now = OffsetDateTime.now(clock);
        List<PendingDelivery> batch = tx.execute(s -> claim(now));
        if (batch == null || batch.isEmpty()) return 0;

        List<PushTicket> tickets = List.of();
        PushFailure failure = null;
        try {
            tickets = gateway.send(batch.stream()
                    .map(d -> new PushMessage(d.token(), d.title(), d.body(), d.eventId())).toList());
        } catch (PushFailure f) {
            failure = f;
            log.warn("푸시 전송 실패 {}건 사유={}", batch.size(), f.reason());
        }

        List<UUID> unregistered = new ArrayList<>();
        List<PushTicket> results = tickets;
        PushFailure requestFailure = failure;
        tx.executeWithoutResult(s -> record(batch, results, requestFailure, OffsetDateTime.now(clock), unregistered));
        unregistered.forEach(this::deleteDevice);
        return failure == null ? batch.size() : 0;
    }

    private List<PendingDelivery> claim(OffsetDateTime now) {
        mapper.expireStale(now.minus(INTRADAY_DEADLINE), now.minus(CLOSE_DEADLINE));
        mapper.failOwnerChanged();
        mapper.failAbandoned(now, MAX_ATTEMPTS);
        List<PendingDelivery> due = mapper.lockDue(now, MAX_ATTEMPTS, BATCH);
        for (PendingDelivery d : due) mapper.markSending(d.eventId(), d.deviceId(), now.plus(LEASE));
        return due;
    }

    private void record(List<PendingDelivery> batch, List<PushTicket> tickets, PushFailure failure,
                        OffsetDateTime now, List<UUID> unregistered) {
        for (int i = 0; i < batch.size(); i++) {
            PendingDelivery d = batch.get(i);
            int attempts = d.attempts() + 1;
            if (failure != null) {
                retryOrFail(d, attempts, failure.reason(), failure.retryable(), now);
                continue;
            }
            PushTicket t = tickets.get(i);
            if (t.ok()) {
                mapper.markSent(d.eventId(), d.deviceId(), attempts, t.id(), now, now.plus(RECEIPT_DELAY));
            } else if (PushGateway.DEVICE_NOT_REGISTERED.equals(t.error())) {
                mapper.failSending(d.eventId(), d.deviceId(), attempts, t.error());
                unregistered.add(d.deviceId());
            } else {
                retryOrFail(d, attempts, t.error(), PushGateway.RATE_EXCEEDED.equals(t.error()), now);
            }
        }
    }

    private void retryOrFail(PendingDelivery d, int attempts, String reason, boolean retryable, OffsetDateTime now) {
        if (!retryable || attempts >= MAX_ATTEMPTS) {
            mapper.failSending(d.eventId(), d.deviceId(), attempts, reason);
        } else {
            mapper.retry(d.eventId(), d.deviceId(), attempts, now.plus(backoff(attempts)), reason);
        }
    }

    /**
     * 기록이 커밋된 뒤 하나씩 지운다(문장 하나가 곧 트랜잭션). 기록과 한 트랜잭션에 두면 발송기와 영수증 확인기가
     * 같은 기기를 지우다 교착할 수 있다.
     */
    private void deleteDevice(UUID deviceId) {
        try {
            mapper.deleteDevice(deviceId);
            log.info("등록이 풀린 기기를 지웠다 device_id={}", deviceId);
        } catch (RuntimeException e) {
            log.warn("등록이 풀린 기기를 지우지 못했다 device_id={}", deviceId, e);
        }
    }

    /** 30초 · 1분 · 2분 · 4분 (계획 ② A.9). */
    static Duration backoff(int attempts) {
        return Duration.ofSeconds(30L << (attempts - 1));
    }
}
```

- [ ] **Step 7: 영수증 확인기를 쓴다**

`src/main/java/com/stockproject/portfolio/alert/delivery/ReceiptChecker.java`:

```java
package com.stockproject.portfolio.alert.delivery;

import com.stockproject.portfolio.alert.store.DeliveryMapper;
import com.stockproject.portfolio.alert.store.SentDelivery;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

import java.time.Clock;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 영수증 확인기 (스펙 §9.4, 계획 ② A.9). 보낸 푸시의 실제 전달 결과를 트랜잭션 밖에서 묻고, 결과를 한 트랜잭션에
 * 쓴 뒤 등록이 풀린 기기를 지운다. Expo는 영수증을 보낸 뒤 24시간 보관한다.
 */
@Component
public class ReceiptChecker {

    private static final Logger log = LoggerFactory.getLogger(ReceiptChecker.class);

    /** Expo가 한 요청에 받는 최대 티켓 수. */
    static final int BATCH = 1000;
    static final Duration RETRY = Duration.ofMinutes(15);
    static final Duration RETENTION = Duration.ofHours(24);

    private final DeliveryMapper mapper;
    private final PushGateway gateway;
    private final PushProperties props;
    private final TransactionTemplate tx;
    private final Clock clock;

    public ReceiptChecker(DeliveryMapper mapper, PushGateway gateway, PushProperties props, TransactionTemplate tx,
                          Clock clock) {
        this.mapper = mapper;
        this.gateway = gateway;
        this.props = props;
        this.tx = tx;
        this.clock = clock;
    }

    /** 물은 행 수를 돌려준다. 조회 자체가 실패하면 아무것도 바꾸지 않고 0을 돌려준다. */
    public int checkOnce() {
        if (!props.enabled()) return 0;
        OffsetDateTime now = OffsetDateTime.now(clock);
        List<SentDelivery> due = mapper.receiptsDue(now, BATCH);
        if (due.isEmpty()) return 0;

        Map<String, PushReceipt> receipts;
        try {
            receipts = gateway.receipts(due.stream().map(SentDelivery::ticketId).toList());
        } catch (PushFailure f) {
            log.warn("푸시 영수증 조회 실패 {}건 사유={}", due.size(), f.reason());
            return 0;
        }

        List<UUID> unregistered = new ArrayList<>();
        tx.executeWithoutResult(s -> {
            for (SentDelivery d : due) {
                PushReceipt r = receipts.get(d.ticketId());
                if (r == null) {
                    if (now.isAfter(d.sentAt().plus(RETENTION))) mapper.clearTicket(d.eventId(), d.deviceId(), d.ticketId());
                    else mapper.postponeReceipt(d.eventId(), d.deviceId(), d.ticketId(), now.plus(RETRY));
                } else if (r.ok()) {
                    mapper.clearTicket(d.eventId(), d.deviceId(), d.ticketId());
                } else {
                    mapper.failReceipt(d.eventId(), d.deviceId(), d.ticketId(), r.error());
                    if (PushGateway.DEVICE_NOT_REGISTERED.equals(r.error())) unregistered.add(d.deviceId());
                }
            }
        });
        for (UUID deviceId : unregistered) {
            try {
                mapper.deleteDevice(deviceId);
                log.info("등록이 풀린 기기를 지웠다 device_id={}", deviceId);
            } catch (RuntimeException e) {
                log.warn("등록이 풀린 기기를 지우지 못했다 device_id={}", deviceId, e);
            }
        }
        return due.size();
    }
}
```

- [ ] **Step 8: 통과를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.delivery.*'`
Expected: PASS

- [ ] **Step 9: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/store/PendingDelivery.java \
        src/main/java/com/stockproject/portfolio/alert/store/SentDelivery.java \
        src/main/java/com/stockproject/portfolio/alert/store/DeliveryMapper.java \
        src/main/java/com/stockproject/portfolio/alert/delivery/DeliveryDispatcher.java \
        src/main/java/com/stockproject/portfolio/alert/delivery/ReceiptChecker.java \
        src/test/java/com/stockproject/portfolio/alert/delivery/
git commit -m "feat: 발송 행을 집어 트랜잭션 밖에서 보내고 영수증으로 기기를 정리한다

기한이 지났거나 기기 소유자가 바뀐 대기 행은 보내지 않는다.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: 스케줄과 설정 — 앱 안의 세 작업

스펙 §8.1 · §8.4와 부록 A.3.

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/runtime/AlertJobs.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/runtime/AlertRuntimeConfig.java`
- Modify: `src/main/resources/application.yaml`
- Modify: `src/test/resources/application-test.yaml`
- Modify: `k8s/deployment.yaml`
- Test: `src/test/java/com/stockproject/portfolio/alert/runtime/AlertRuntimeConfigTest.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/delivery/HttpClientTimeoutTest.java`

**Interfaces:**
- Consumes: `EvaluationRunner.tick()`(Task 7) · `DeliveryDispatcher.dispatchOnce()` · `DeliveryDispatcher.BATCH` · `ReceiptChecker.checkOnce()`(Task 10)
- Produces: 설정 키 `portfolio.alert.runtime.enabled`(기본 `true`) · `portfolio.alert.push.enabled`(기본 `false`) · `portfolio.alert.push.expo-url` · `portfolio.alert.push.access-token` · `spring.http.client.connect-timeout`(5s) · `spring.http.client.read-timeout`(15s). 환경변수 `ALERT_RUNTIME_ENABLED` · `EXPO_PUSH_ENABLED` · `EXPO_ACCESS_TOKEN`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/runtime/AlertRuntimeConfigTest.java`:

```java
package com.stockproject.portfolio.alert.runtime;

import com.stockproject.portfolio.alert.delivery.DeliveryDispatcher;
import com.stockproject.portfolio.alert.delivery.ReceiptChecker;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/** 평가기·발송기·영수증 확인기는 앱 안의 스케줄 작업이고 설정으로 끈다 (스펙 §8.1 · §8.4, 계획 ② A.3). */
class AlertRuntimeConfigTest {

    private final ApplicationContextRunner context = new ApplicationContextRunner()
            .withUserConfiguration(AlertRuntimeConfig.class)
            .withBean(EvaluationRunner.class, () -> mock(EvaluationRunner.class))
            .withBean(DeliveryDispatcher.class, () -> mock(DeliveryDispatcher.class))
            .withBean(ReceiptChecker.class, () -> mock(ReceiptChecker.class));

    @Test
    void 기본으로_스케줄_작업을_둔다() {
        context.run(ctx -> assertThat(ctx).hasSingleBean(AlertJobs.class));
    }

    @Test
    void 끄면_스케줄_작업을_두지_않는다() {
        context.withPropertyValues("portfolio.alert.runtime.enabled=false")
                .run(ctx -> assertThat(ctx).doesNotHaveBean(AlertJobs.class));
    }

    @Test
    void 발송기는_묶음이_꽉_차면_이어서_보낸다() {
        DeliveryDispatcher dispatcher = mock(DeliveryDispatcher.class);
        when(dispatcher.dispatchOnce()).thenReturn(DeliveryDispatcher.BATCH, DeliveryDispatcher.BATCH, 3);

        new AlertJobs(mock(EvaluationRunner.class), dispatcher, mock(ReceiptChecker.class)).dispatch();

        verify(dispatcher, times(3)).dispatchOnce();
    }
}
```

`src/test/java/com/stockproject/portfolio/alert/delivery/HttpClientTimeoutTest.java`:

```java
package com.stockproject.portfolio.alert.delivery;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.http.client.ClientHttpRequestFactorySettings;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Expo 호출의 시간 제한 (계획 ② A.9). Boot 3.4의 spring.http.client.* 가 이 설정 빈을 거쳐
 * RestClient.Builder에 걸린다(RestClientBuilderConfigurer).
 */
@SpringBootTest
@ActiveProfiles("test")
class HttpClientTimeoutTest {

    @Autowired ClientHttpRequestFactorySettings settings;

    @Test
    void Expo_호출에_연결_5초_읽기_15초_제한이_걸린다() {
        assertThat(settings.connectTimeout()).isEqualTo(Duration.ofSeconds(5));
        assertThat(settings.readTimeout()).isEqualTo(Duration.ofSeconds(15));
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.runtime.AlertRuntimeConfigTest' --tests 'com.stockproject.portfolio.alert.delivery.HttpClientTimeoutTest'`
Expected: FAIL — `AlertJobs`가 없어 컴파일 오류(고친 뒤에는 시간 제한이 null이라 `HttpClientTimeoutTest`가 실패한다).

- [ ] **Step 3: 스케줄 작업을 쓴다**

`src/main/java/com/stockproject/portfolio/alert/runtime/AlertJobs.java`:

```java
package com.stockproject.portfolio.alert.runtime;

import com.stockproject.portfolio.alert.delivery.DeliveryDispatcher;
import com.stockproject.portfolio.alert.delivery.ReceiptChecker;
import org.springframework.scheduling.annotation.Scheduled;

/**
 * 평가기 · 발송기 · 영수증 확인기 (스펙 §8.1, 계획 ② A.3). 모든 복제본에서 돈다 — 중복 방지는 잠금이 아니라
 * 데이터에 있다(§8.2). 주기는 끝난 뒤부터 센다(fixedDelay). 한 번이 길어져도 겹쳐 돌지 않는다.
 */
public class AlertJobs {

    private final EvaluationRunner runner;
    private final DeliveryDispatcher dispatcher;
    private final ReceiptChecker receipts;

    public AlertJobs(EvaluationRunner runner, DeliveryDispatcher dispatcher, ReceiptChecker receipts) {
        this.runner = runner;
        this.dispatcher = dispatcher;
        this.receipts = receipts;
    }

    @Scheduled(fixedDelayString = "PT1M", initialDelayString = "PT10S")
    public void evaluate() {
        runner.tick();
    }

    /** 한 묶음이 꽉 차면 남은 행이 있을 수 있어 이어서 보낸다. */
    @Scheduled(fixedDelayString = "PT5S", initialDelayString = "PT15S")
    public void dispatch() {
        while (dispatcher.dispatchOnce() == DeliveryDispatcher.BATCH) {
            // 다음 묶음
        }
    }

    @Scheduled(fixedDelayString = "PT5M", initialDelayString = "PT1M")
    public void receipts() {
        receipts.checkOnce();
    }
}
```

`src/main/java/com/stockproject/portfolio/alert/runtime/AlertRuntimeConfig.java`:

```java
package com.stockproject.portfolio.alert.runtime;

import com.stockproject.portfolio.alert.delivery.DeliveryDispatcher;
import com.stockproject.portfolio.alert.delivery.ReceiptChecker;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 알림 런타임을 이 파드에서 돌릴지. 끄면 이 파드는 API만 한다 — 평가가 API 응답을 늦추면 같은 이미지를
 * 런타임만 켠 워커로 따로 띄우고 API 파드에서는 끈다(스펙 §8.4). 테스트는 끄고 작업을 직접 부른다.
 */
@Configuration(proxyBeanMethods = false)
@EnableScheduling
@ConditionalOnProperty(name = "portfolio.alert.runtime.enabled", havingValue = "true", matchIfMissing = true)
public class AlertRuntimeConfig {

    @Bean
    AlertJobs alertJobs(EvaluationRunner runner, DeliveryDispatcher dispatcher, ReceiptChecker receipts) {
        return new AlertJobs(runner, dispatcher, receipts);
    }
}
```

- [ ] **Step 4: 설정을 더한다**

`src/main/resources/application.yaml`의 `spring:` 아래(`lifecycle:` 다음)에 더한다.

```yaml
  http:
    client:
      # Expo 호출의 시간 제한. Boot가 만드는 RestClient.Builder에 걸린다 — 응답이 멈춰도 발송 스레드가 서지 않는다.
      connect-timeout: 5s
      read-timeout: 15s
  task:
    scheduling:
      # 평가기 · 발송기 · 영수증 확인기가 서로를 붙잡지 않게 셋을 둔다.
      pool:
        size: 3
      shutdown:
        # 종료 신호에 진행 중인 작업을 기다린다. 끊겨도 트랜잭션이 롤백될 뿐 상태는 데이터에 있다.
        await-termination: true
        await-termination-period: 20s
```

같은 파일의 `portfolio:` 아래(`auth:` 블록 다음)에 더한다.

```yaml
  alert:
    runtime:
      # 평가기 · 발송기 · 영수증 확인기. 끄면 이 파드는 API만 한다(알림 스펙 §8.4).
      enabled: ${ALERT_RUNTIME_ENABLED:true}
    push:
      # 켜야 Expo로 보낸다. 꺼져 있으면 발송 행이 PENDING으로 남고 발화 기록과 배지는 그대로다.
      enabled: ${EXPO_PUSH_ENABLED:false}
      expo-url: https://exp.host
      # Expo 프로젝트에 향상된 보안을 켰을 때만 필요하다. 값은 Secret에서 환경변수로만 들어온다.
      access-token: ${EXPO_ACCESS_TOKEN:}
```

`src/test/resources/application-test.yaml` 끝에 더한다.

```yaml
portfolio:
  alert:
    runtime:
      # 테스트가 평가기·발송기를 직접 부른다. 스케줄이 돌면 다른 테스트의 데이터를 바꾼다.
      enabled: false
```

`k8s/deployment.yaml`의 컨테이너 `env:` 목록 끝(`JWT_SECRET` 항목 다음)에 더한다.

```yaml
            # 알림 푸시. 켜는 것은 사람이 한다 — Expo 접근 토큰이 필요하면 Secret에 넣고, 클러스터에서
            # exp.host로 나가는 통신을 확인한 뒤 "true"로 바꾼다.
            - name: EXPO_PUSH_ENABLED
              value: "false"
            - name: EXPO_ACCESS_TOKEN
              valueFrom:
                secretKeyRef:
                  name: portfolio-api
                  key: EXPO_ACCESS_TOKEN
                  optional: true
```

- [ ] **Step 5: 통과를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.*'`
Expected: PASS — 테스트 프로필에서는 스케줄이 돌지 않아 다른 테스트가 흔들리지 않는다.

- [ ] **Step 6: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/runtime/AlertJobs.java \
        src/main/java/com/stockproject/portfolio/alert/runtime/AlertRuntimeConfig.java \
        src/main/resources/application.yaml \
        src/test/resources/application-test.yaml \
        src/test/java/com/stockproject/portfolio/alert/runtime/AlertRuntimeConfigTest.java \
        src/test/java/com/stockproject/portfolio/alert/delivery/HttpClientTimeoutTest.java \
        k8s/deployment.yaml
git commit -m "feat: 평가기·발송기·영수증 확인기를 앱 안의 스케줄 작업으로 돌린다

푸시는 설정으로 켜고, 운영 매니페스트는 꺼 둔 채로 둔다.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: 울린 알림 API

스펙 §11.1 · §11.2 · §11.3 · §12.3과 부록 A.11.

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/store/EventListRow.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/store/EventDetailRow.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/store/AlertEventMapper.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/service/EventCursor.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/service/AlertEventService.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/api/AlertEventController.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/api/dto/EventListData.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/api/dto/EventRowDto.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/api/dto/EventDetailDto.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/api/dto/EventAlertDto.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/api/dto/EventInstrumentDto.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/api/dto/UnreadCountDto.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/api/AlertEventApiTest.java`

**Interfaces:**
- Consumes: `AlertQueryMapper.latestEvaluatedAsOf(UserScope)` · `AlertQueryMapper.unreadCount(UserScope)`(①) · `AlertTimes.kst(OffsetDateTime)`(①) · `Envelope`(①)
- Produces:
  - `GET /alert-events?alert_id=&cursor=&limit=` → `Envelope<EventListData>`. 남의 `alert_id`·없는 `alert_id`는 `404 ALERT_NOT_FOUND`
  - `GET /alert-events/{id}` → `EventDetailDto` · `POST /alert-events/{id}/read` → `204` · `POST /alert-events/read-all` → `204` · `GET /alert-events/unread-count` → `{ "count" }`
  - `AlertEventService(AlertEventMapper, AlertQueryMapper, ObjectMapper, Clock)` — Task 13이 생성자에 `MarketDelayNotices`를 더한다

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/api/AlertEventApiTest.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.AlertApiClient;
import com.stockproject.portfolio.alert.AlertApiClient.Response;
import com.stockproject.portfolio.alert.FixedClockConfig;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.web.servlet.MockMvc;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.SAMSUNG;
import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.priceReach;
import static org.assertj.core.api.Assertions.assertThat;

/** 울린 알림 (스펙 §11.1 ~ §11.3 · §12.3, 계획 ② A.11). 지금은 2026-09-28 10:20이다. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(FixedClockConfig.class)
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class AlertEventApiTest {

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;
    AlertApiClient api;

    @BeforeEach
    void setUp() { api = new AlertApiClient(mockMvc, json); }

    @Test
    void 목록은_데이터_시점_내림차순이고_다음_쪽을_커서로_넘긴다() throws Exception {
        UUID alert = create("yhr", priceReach(SAMSUNG, "CLOSE", 1));
        event(alert, "2026-09-23T15:30:00+09");
        event(alert, "2026-09-25T15:30:00+09");
        event(alert, "2026-09-24T15:30:00+09");

        JsonNode first = api.get("/alert-events?limit=2", "yhr").body();

        assertThat(asOfs(first)).containsExactly("2026-09-25T15:30:00+09:00", "2026-09-24T15:30:00+09:00");
        JsonNode row = first.get("data").get("rows").get(0);
        assertThat(row.get("alert_id").asText()).isEqualTo(alert.toString());
        assertThat(row.get("title").asText()).isEqualTo("삼성전자 · 가격 도달");
        assertThat(row.get("body").asText()).isEqualTo("종가 63,010원 ≥ 1원 · 9/25 종가 기준");
        assertThat(row.get("cadence").asText()).isEqualTo("CLOSE");
        assertThat(row.get("market").asText()).isEqualTo("KR");
        assertThat(row.get("fired_at").asText()).isEqualTo("2026-09-28T10:00:00+09:00");
        assertThat(row.get("read").asBoolean()).isFalse();
        assertThat(row.get("alert_deleted").asBoolean()).isFalse();
        assertThat(first.get("empty_reason").isNull()).isTrue();

        String cursor = first.get("data").get("next_cursor").asText();
        JsonNode second = api.get("/alert-events?limit=2&cursor=" + cursor, "yhr").body();
        assertThat(asOfs(second)).containsExactly("2026-09-23T15:30:00+09:00");
        assertThat(second.get("data").get("next_cursor").isNull()).isTrue();
    }

    @Test
    void 알림으로_거를_수_있고_남의_알림이나_없는_알림이면_404다() throws Exception {
        UUID mine = create("yhr", priceReach(SAMSUNG, "CLOSE", 1));
        UUID other = create("yhr", priceReach(SAMSUNG, "CLOSE", 2));
        event(mine, "2026-09-24T15:30:00+09");
        event(other, "2026-09-25T15:30:00+09");

        JsonNode filtered = api.get("/alert-events?alert_id=" + mine, "yhr").body();
        assertThat(asOfs(filtered)).containsExactly("2026-09-24T15:30:00+09:00");

        for (Response r : List.of(api.get("/alert-events?alert_id=" + mine, "jdh"),
                api.get("/alert-events?alert_id=" + UUID.randomUUID(), "yhr"))) {
            assertThat(r.status()).isEqualTo(404);
            assertThat(r.body().get("error").get("code").asText()).isEqualTo("ALERT_NOT_FOUND");
        }

        assertThat(api.delete("/alerts/" + mine, "yhr").status()).isEqualTo(204);
        assertThat(asOfs(api.get("/alert-events?alert_id=" + mine, "yhr").body()))
                .containsExactly("2026-09-24T15:30:00+09:00");
    }

    @Test
    void 울린_알림이_없으면_빈_상태_사유다() throws Exception {
        JsonNode body = api.get("/alert-events", "test_empty").body();

        assertThat(body.get("as_of").isNull()).isTrue();
        assertThat(body.get("data").get("rows")).isEmpty();
        assertThat(body.get("data").get("next_cursor").isNull()).isTrue();
        assertThat(body.get("empty_reason").asText()).isEqualTo("NO_EVENTS");
        assertThat(body.get("notices")).isEmpty();
    }

    @Test
    void 잘못된_목록_요청은_400이다() throws Exception {
        for (String query : List.of("limit=0", "limit=51", "limit=abc", "cursor=@@@", "cursor=bm90LWEtY3Vyc29y",
                "alert_id=not-a-uuid")) {
            Response r = api.get("/alert-events?" + query, "yhr");
            assertThat(r.status()).as(query).isEqualTo(400);
            assertThat(r.body().get("error").get("code").asText()).as(query).isEqualTo("INVALID_PARAMETER");
        }
    }

    @Test
    void 상세는_울린_이유와_알림의_지금_상태를_준다() throws Exception {
        UUID alert = create("yhr", priceReach(SAMSUNG, "CLOSE", 1));
        UUID event = event(alert, "2026-09-25T15:30:00+09");

        JsonNode body = api.get("/alert-events/" + event, "yhr").body();

        assertThat(body.get("event_id").asText()).isEqualTo(event.toString());
        assertThat(body.get("lines")).hasSize(1);
        assertThat(body.get("lines").get(0).asText()).isEqualTo("종가 63,010원 ≥ 1원");
        assertThat(body.get("observed").get("conditions").get(0).get("left").decimalValue())
                .isEqualByComparingTo("63010");
        assertThat(body.get("as_of").asText()).isEqualTo("2026-09-25T15:30:00+09:00");
        assertThat(body.get("read_at").isNull()).isTrue();
        JsonNode a = body.get("alert");
        assertThat(a.get("alert_id").asText()).isEqualTo(alert.toString());
        assertThat(a.get("name").asText()).isEqualTo("가격");
        assertThat(a.get("cadence").asText()).isEqualTo("CLOSE");
        assertThat(a.get("notify_mode").asText()).isEqualTo("EDGE_REARM");
        assertThat(a.get("status").asText()).isEqualTo("ACTIVE");
        assertThat(a.get("deleted").asBoolean()).isFalse();
        assertThat(a.get("instrument").get("label").asText()).isEqualTo("삼성전자");
    }

    /** 이미 받은 푸시를 눌렀을 때 내용이 사라져 있으면 무엇이 울렸는지 알 방법이 없다 (§6.8). */
    @Test
    void 삭제된_알림의_발화도_보인다() throws Exception {
        UUID alert = create("yhr", priceReach(SAMSUNG, "CLOSE", 1));
        UUID event = event(alert, "2026-09-25T15:30:00+09");
        assertThat(api.delete("/alerts/" + alert, "yhr").status()).isEqualTo(204);

        assertThat(api.get("/alert-events", "yhr").body().get("data").get("rows").get(0)
                .get("alert_deleted").asBoolean()).isTrue();
        assertThat(api.get("/alert-events/" + event, "yhr").body().get("alert").get("deleted").asBoolean()).isTrue();
    }

    @Test
    void 남의_발화는_없는_발화와_같은_404다() throws Exception {
        UUID alert = create("yhr", priceReach(SAMSUNG, "CLOSE", 1));
        UUID event = event(alert, "2026-09-25T15:30:00+09");

        for (Response r : List.of(api.get("/alert-events/" + event, "jdh"),
                api.get("/alert-events/" + UUID.randomUUID(), "yhr"),
                api.post("/alert-events/" + event + "/read", "jdh", null))) {
            assertThat(r.status()).isEqualTo(404);
            assertThat(r.body().get("error").get("code").asText()).isEqualTo("EVENT_NOT_FOUND");
        }
        assertThat(api.get("/alert-events/unread-count", "yhr").body().get("count").asInt()).isEqualTo(1);
    }

    @Test
    void 읽음_처리와_미확인_배지() throws Exception {
        UUID alert = create("yhr", priceReach(SAMSUNG, "CLOSE", 1));
        UUID first = event(alert, "2026-09-23T15:30:00+09");
        event(alert, "2026-09-24T15:30:00+09");
        event(alert, "2026-09-25T15:30:00+09");
        assertThat(api.get("/alert-events/unread-count", "yhr").body().get("count").asInt()).isEqualTo(3);

        assertThat(api.post("/alert-events/" + first + "/read", "yhr", null).status()).isEqualTo(204);
        String readAt = api.get("/alert-events/" + first, "yhr").body().get("read_at").asText();
        assertThat(readAt).isEqualTo("2026-09-28T10:20:00+09:00");
        assertThat(api.get("/alert-events/unread-count", "yhr").body().get("count").asInt()).isEqualTo(2);

        jdbc.sql("UPDATE alert_event SET read_at = '2026-09-28T10:05:00+09' WHERE event_id = :id")
                .param("id", first).update();
        api.post("/alert-events/" + first + "/read", "yhr", null);
        assertThat(api.get("/alert-events/" + first, "yhr").body().get("read_at").asText())
                .isEqualTo("2026-09-28T10:05:00+09:00");

        assertThat(api.post("/alert-events/read-all", "yhr", null).status()).isEqualTo(204);
        assertThat(api.get("/alert-events/unread-count", "yhr").body().get("count").asInt()).isZero();
        assertThat(api.get("/alerts", "yhr").body().get("data").get("unread")).isEmpty();
    }

    // ---- 도우미 ----------------------------------------------------------------

    private UUID create(String user, String body) throws Exception {
        Response r = api.post("/alerts", user, body);
        assertThat(r.status()).isEqualTo(201);
        return UUID.fromString(r.body().get("alert_id").asText());
    }

    /** 평가기를 거치지 않고 발화를 넣는다. 기록 시각은 10:00이다. */
    private UUID event(UUID alertId, String asOf) {
        UUID id = UUID.randomUUID();
        jdbc.sql("""
                INSERT INTO alert_event (event_id, alert_id, as_of, fired_at, title, body, lines, observed)
                VALUES (:e, :a, CAST(:asOf AS timestamptz), '2026-09-28T10:00:00+09', '삼성전자 · 가격 도달',
                        '종가 63,010원 ≥ 1원 · 9/25 종가 기준', '["종가 63,010원 ≥ 1원"]',
                        '{"conditions": [{"left": 63010, "right": 1, "progress": null}]}')
                """).param("e", id).param("a", alertId).param("asOf", asOf).update();
        return id;
    }

    private static List<String> asOfs(JsonNode envelope) {
        List<String> out = new ArrayList<>();
        for (JsonNode row : envelope.get("data").get("rows")) out.add(row.get("as_of").asText());
        return out;
    }
}
```

`cursor=bm90LWEtY3Vyc29y`는 `not-a-cursor`의 base64url이다 — 해석은 되지만 모양이 틀린 커서다.

- [ ] **Step 2: 실패를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.api.AlertEventApiTest'`
Expected: FAIL — 경로가 없어 404, 또는 컴파일 오류.

- [ ] **Step 3: 읽기 행과 매퍼를 쓴다**

`src/main/java/com/stockproject/portfolio/alert/store/EventListRow.java`:

```java
package com.stockproject.portfolio.alert.store;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 울린 알림 목록의 한 행. market은 종목 마스터에 종목이 없으면 null이다. */
public record EventListRow(UUID eventId, UUID alertId, String title, String body, String cadence, String market,
                           OffsetDateTime asOf, OffsetDateTime firedAt, boolean read, boolean alertDeleted) { }
```

`src/main/java/com/stockproject/portfolio/alert/store/EventDetailRow.java`:

```java
package com.stockproject.portfolio.alert.store;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 울린 알림 상세 — 발화 그대로와 그 알림의 지금 상태. lines · observed는 JSON 문자열이다(계획 ① A.4). */
public record EventDetailRow(UUID eventId, String title, String body, String lines, OffsetDateTime asOf,
                             OffsetDateTime firedAt, String observed, OffsetDateTime readAt, UUID alertId,
                             String alertName, String cadence, String notifyMode, String status,
                             String lastResult, String unknownReason, boolean alertDeleted, UUID instrumentId,
                             String instrumentLabel) { }
```

`src/main/java/com/stockproject/portfolio/alert/store/AlertEventMapper.java`:

```java
package com.stockproject.portfolio.alert.store;

import com.stockproject.portfolio.auth.UserScope;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 울린 알림 (스펙 §11.3, 계획 ② A.11). 모든 조회·변경은 alert.user_id로 스코프된다 — 발화의 소유자는
 * 그 알림의 소유자다. 삭제된 알림의 발화도 남아 보인다(§6.8).
 */
@Mapper
public interface AlertEventMapper {

    @Select("""
            SELECT e.event_id, e.alert_id, e.title, e.body, a.cadence, i.market, e.as_of, e.fired_at,
                   e.read_at IS NOT NULL AS read, a.deleted_at IS NOT NULL AS alert_deleted
              FROM alert_event e
              JOIN alert a ON a.alert_id = e.alert_id
              LEFT JOIN instrument i ON i.instrument_id = a.instrument_id
             WHERE a.user_id = #{scope.userId}
               AND (#{alertId}::uuid IS NULL OR e.alert_id = #{alertId}::uuid)
               AND (#{afterAsOf}::timestamptz IS NULL
                    OR (e.as_of, e.event_id) < (#{afterAsOf}::timestamptz, #{afterId}::uuid))
             ORDER BY e.as_of DESC, e.event_id DESC
             LIMIT #{limit}
            """)
    List<EventListRow> page(@Param("scope") UserScope scope, @Param("alertId") UUID alertId,
                            @Param("afterAsOf") OffsetDateTime afterAsOf, @Param("afterId") UUID afterId,
                            @Param("limit") int limit);

    /** 내 알림인가. 삭제된 알림도 내 것이다 — 그 발화는 남아 보인다(§6.8). */
    @Select("SELECT EXISTS (SELECT 1 FROM alert WHERE alert_id = #{alertId} AND user_id = #{scope.userId})")
    boolean ownsAlert(@Param("scope") UserScope scope, @Param("alertId") UUID alertId);

    @Select("""
            SELECT e.event_id, e.title, e.body, e.lines::text AS lines, e.as_of, e.fired_at,
                   e.observed::text AS observed, e.read_at,
                   a.alert_id, a.name AS alert_name, a.cadence, a.notify_mode, a.status,
                   s.last_result, s.unknown_reason, a.deleted_at IS NOT NULL AS alert_deleted,
                   a.instrument_id, i.name AS instrument_label
              FROM alert_event e
              JOIN alert a ON a.alert_id = e.alert_id
              JOIN alert_state s ON s.alert_id = a.alert_id
              LEFT JOIN instrument i ON i.instrument_id = a.instrument_id
             WHERE e.event_id = #{eventId} AND a.user_id = #{scope.userId}
            """)
    EventDetailRow detail(@Param("scope") UserScope scope, @Param("eventId") UUID eventId);

    /** 처음 읽은 시각을 유지한다. 남의 발화·없는 발화면 0이다. */
    @Update("""
            UPDATE alert_event e SET read_at = COALESCE(e.read_at, #{now})
              FROM alert a
             WHERE a.alert_id = e.alert_id AND a.user_id = #{scope.userId} AND e.event_id = #{eventId}
            """)
    int markRead(@Param("scope") UserScope scope, @Param("eventId") UUID eventId, @Param("now") OffsetDateTime now);

    @Update("""
            UPDATE alert_event e SET read_at = #{now}
              FROM alert a
             WHERE a.alert_id = e.alert_id AND a.user_id = #{scope.userId} AND e.read_at IS NULL
            """)
    int markAllRead(@Param("scope") UserScope scope, @Param("now") OffsetDateTime now);
}
```

- [ ] **Step 4: 응답 모양을 쓴다**

`src/main/java/com/stockproject/portfolio/alert/api/dto/EventListData.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.util.List;

/** GET /alert-events 봉투의 data (§11.3). next_cursor가 null이면 마지막 쪽이다. */
public record EventListData(List<EventRowDto> rows, String nextCursor) { }
```

`src/main/java/com/stockproject/portfolio/alert/api/dto/EventRowDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 울린 알림 목록의 한 줄 (§11.3 · §12.3). */
public record EventRowDto(UUID eventId, UUID alertId, String title, String body, String cadence, String market,
                          OffsetDateTime asOf, OffsetDateTime firedAt, boolean read, boolean alertDeleted) { }
```

`src/main/java/com/stockproject/portfolio/alert/api/dto/EventInstrumentDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.util.UUID;

/** 울린 알림 상세의 종목. label은 종목 마스터에 없으면 null이다. */
public record EventInstrumentDto(UUID id, String label) { }
```

`src/main/java/com/stockproject/portfolio/alert/api/dto/EventAlertDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.util.UUID;

/** 울린 알림 상세의 "이 알림" — 지금 상태다. 화면은 deleted면 알림 보기·끄기를 숨긴다(§12.3). */
public record EventAlertDto(UUID alertId, String name, String cadence, String notifyMode, String status,
                            String lastResult, String unknownReason, boolean deleted,
                            EventInstrumentDto instrument) { }
```

`src/main/java/com/stockproject/portfolio/alert/api/dto/EventDetailDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import com.fasterxml.jackson.databind.JsonNode;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** GET /alert-events/{id} (§11.3). 울린 당시의 문구만 담는다 — 지금 값은 알림 상세가 답한다(§12.3). */
public record EventDetailDto(UUID eventId, String title, String body, List<String> lines, OffsetDateTime asOf,
                             OffsetDateTime firedAt, JsonNode observed, OffsetDateTime readAt,
                             EventAlertDto alert) { }
```

`src/main/java/com/stockproject/portfolio/alert/api/dto/UnreadCountDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

/** 탭 배지 (§11.3). */
public record UnreadCountDto(int count) { }
```

- [ ] **Step 5: 커서와 서비스를 쓴다**

`src/main/java/com/stockproject/portfolio/alert/service/EventCursor.java`:

```java
package com.stockproject.portfolio.alert.service;

import com.stockproject.portfolio.validation.RequestRejected;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Base64;
import java.util.UUID;

/**
 * 울린 알림 목록의 다음 쪽 위치 (계획 ② A.11). 마지막 행의 데이터 시점과 발화 ID를 이은 불투명 문자열이다 —
 * 같은 시점의 발화가 여럿이어도 쪽 경계에서 빠지거나 겹치지 않는다.
 */
final class EventCursor {

    private EventCursor() { }

    record Position(OffsetDateTime asOf, UUID eventId) { }

    static String encode(OffsetDateTime asOf, UUID eventId) {
        String raw = asOf.toInstant() + "|" + eventId;
        return Base64.getUrlEncoder().withoutPadding().encodeToString(raw.getBytes(StandardCharsets.UTF_8));
    }

    static Position decode(String cursor) {
        try {
            String raw = new String(Base64.getUrlDecoder().decode(cursor), StandardCharsets.UTF_8);
            int bar = raw.indexOf('|');
            if (bar < 0) throw invalid();
            return new Position(OffsetDateTime.ofInstant(Instant.parse(raw.substring(0, bar)), ZoneOffset.UTC),
                    UUID.fromString(raw.substring(bar + 1)));
        } catch (IllegalArgumentException | java.time.format.DateTimeParseException e) {
            throw invalid();
        }
    }

    private static RequestRejected invalid() {
        return new RequestRejected("INVALID_PARAMETER", "목록 위치가 올바르지 않아요");
    }
}
```

`src/main/java/com/stockproject/portfolio/alert/service/AlertEventService.java`:

```java
package com.stockproject.portfolio.alert.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.api.dto.EventAlertDto;
import com.stockproject.portfolio.alert.api.dto.EventDetailDto;
import com.stockproject.portfolio.alert.api.dto.EventInstrumentDto;
import com.stockproject.portfolio.alert.api.dto.EventListData;
import com.stockproject.portfolio.alert.api.dto.EventRowDto;
import com.stockproject.portfolio.alert.api.dto.UnreadCountDto;
import com.stockproject.portfolio.alert.store.AlertEventMapper;
import com.stockproject.portfolio.alert.store.AlertQueryMapper;
import com.stockproject.portfolio.alert.store.EventDetailRow;
import com.stockproject.portfolio.alert.store.EventListRow;
import com.stockproject.portfolio.api.dto.Envelope;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.validation.RequestRejected;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** 울린 알림의 읽기와 읽음 처리 (스펙 §11, 계획 ② A.11). 남의 발화와 없는 발화를 구분하지 않는다. */
@Service
public class AlertEventService {

    static final int DEFAULT_LIMIT = 20;
    static final int MAX_LIMIT = 50;

    private final AlertEventMapper events;
    private final AlertQueryMapper queries;
    private final ObjectMapper json;
    private final Clock clock;

    public AlertEventService(AlertEventMapper events, AlertQueryMapper queries, ObjectMapper json, Clock clock) {
        this.events = events;
        this.queries = queries;
        this.json = json;
        this.clock = clock;
    }

    /** alertId는 그 알림의 발화만. 남의 알림이거나 없는 알림이면 404다(§11.4). 삭제된 내 알림은 찾은 것으로 본다(§6.8). */
    public Envelope<EventListData> list(UserScope scope, String alertId, String cursor, String limit) {
        UUID alert = alertId == null ? null : uuid(alertId);
        if (alert != null && !events.ownsAlert(scope, alert)) {
            throw new RequestRejected("ALERT_NOT_FOUND", "알림을 찾을 수 없어요", true);
        }
        int size = limit(limit);
        EventCursor.Position after = cursor == null ? null : EventCursor.decode(cursor);
        List<EventListRow> rows = events.page(scope, alert, after == null ? null : after.asOf(),
                after == null ? null : after.eventId(), size + 1);

        boolean more = rows.size() > size;
        List<EventListRow> page = more ? rows.subList(0, size) : rows;
        EventListRow last = page.isEmpty() ? null : page.get(page.size() - 1);
        String next = more ? EventCursor.encode(last.asOf(), last.eventId()) : null;
        List<EventRowDto> dtos = page.stream().map(r -> new EventRowDto(r.eventId(), r.alertId(), r.title(), r.body(),
                r.cadence(), r.market(), AlertTimes.kst(r.asOf()), AlertTimes.kst(r.firedAt()), r.read(),
                r.alertDeleted())).toList();
        String empty = dtos.isEmpty() && cursor == null ? "NO_EVENTS" : null;
        return new Envelope<>(AlertTimes.kst(queries.latestEvaluatedAsOf(scope)), new EventListData(dtos, next),
                empty, List.of());
    }

    public EventDetailDto detail(UserScope scope, UUID eventId) {
        EventDetailRow r = events.detail(scope, eventId);
        if (r == null) throw notFound();
        return new EventDetailDto(r.eventId(), r.title(), r.body(), lines(r.lines()), AlertTimes.kst(r.asOf()),
                AlertTimes.kst(r.firedAt()), tree(r.observed()), AlertTimes.kst(r.readAt()),
                new EventAlertDto(r.alertId(), r.alertName(), r.cadence(), r.notifyMode(), r.status(), r.lastResult(),
                        r.unknownReason(), r.alertDeleted(), new EventInstrumentDto(r.instrumentId(), r.instrumentLabel())));
    }

    public void markRead(UserScope scope, UUID eventId) {
        if (events.markRead(scope, eventId, OffsetDateTime.now(clock)) == 0) throw notFound();
    }

    public void markAllRead(UserScope scope) {
        events.markAllRead(scope, OffsetDateTime.now(clock));
    }

    public UnreadCountDto unreadCount(UserScope scope) {
        return new UnreadCountDto(queries.unreadCount(scope));
    }

    // ---- 도우미 ----------------------------------------------------------------

    private static UUID uuid(String value) {
        try {
            return UUID.fromString(value);
        } catch (IllegalArgumentException e) {
            throw invalidParameter();
        }
    }

    private static int limit(String value) {
        if (value == null) return DEFAULT_LIMIT;
        try {
            int n = Integer.parseInt(value);
            if (n < 1 || n > MAX_LIMIT) throw invalidParameter();
            return n;
        } catch (NumberFormatException e) {
            throw invalidParameter();
        }
    }

    private List<String> lines(String text) {
        try {
            return json.readValue(text, new TypeReference<List<String>>() { });
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("발화의 lines가 문자열 배열이 아니다", e);
        }
    }

    private JsonNode tree(String text) {
        try {
            return json.readTree(text);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("발화의 observed가 JSON이 아니다", e);
        }
    }

    private static RequestRejected invalidParameter() {
        return new RequestRejected("INVALID_PARAMETER", "목록 요청을 확인해 주세요");
    }

    private static RequestRejected notFound() {
        return new RequestRejected("EVENT_NOT_FOUND", "울린 알림을 찾을 수 없어요", true);
    }
}
```

- [ ] **Step 6: 컨트롤러를 쓴다**

`src/main/java/com/stockproject/portfolio/alert/api/AlertEventController.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.stockproject.portfolio.alert.api.dto.EventDetailDto;
import com.stockproject.portfolio.alert.api.dto.EventListData;
import com.stockproject.portfolio.alert.api.dto.UnreadCountDto;
import com.stockproject.portfolio.alert.service.AlertEventService;
import com.stockproject.portfolio.api.dto.Envelope;
import com.stockproject.portfolio.auth.UserScope;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

/**
 * 울린 알림 (스펙 §11.1). 쿼리 값은 문자열로 받아 서비스가 해석한다 — 형이 틀린 값도 같은
 * INVALID_PARAMETER 오류 본문으로 돌려주기 위해서다.
 */
@RestController
@RequestMapping("/alert-events")
public class AlertEventController {

    private final AlertEventService events;

    public AlertEventController(AlertEventService events) { this.events = events; }

    @GetMapping
    public Envelope<EventListData> list(UserScope scope,
                                        @RequestParam(name = "alert_id", required = false) String alertId,
                                        @RequestParam(name = "cursor", required = false) String cursor,
                                        @RequestParam(name = "limit", required = false) String limit) {
        return events.list(scope, alertId, cursor, limit);
    }

    @GetMapping("/unread-count")
    public UnreadCountDto unreadCount(UserScope scope) {
        return events.unreadCount(scope);
    }

    @GetMapping("/{eventId}")
    public EventDetailDto detail(UserScope scope, @PathVariable UUID eventId) {
        return events.detail(scope, eventId);
    }

    @PostMapping("/{eventId}/read")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void read(UserScope scope, @PathVariable UUID eventId) {
        events.markRead(scope, eventId);
    }

    @PostMapping("/read-all")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void readAll(UserScope scope) {
        events.markAllRead(scope);
    }
}
```

- [ ] **Step 7: 통과를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.api.*' --tests 'com.stockproject.portfolio.ArchitectureRulesTest'`
Expected: PASS

- [ ] **Step 8: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/store/EventListRow.java \
        src/main/java/com/stockproject/portfolio/alert/store/EventDetailRow.java \
        src/main/java/com/stockproject/portfolio/alert/store/AlertEventMapper.java \
        src/main/java/com/stockproject/portfolio/alert/service/EventCursor.java \
        src/main/java/com/stockproject/portfolio/alert/service/AlertEventService.java \
        src/main/java/com/stockproject/portfolio/alert/api/AlertEventController.java \
        src/main/java/com/stockproject/portfolio/alert/api/dto/EventListData.java \
        src/main/java/com/stockproject/portfolio/alert/api/dto/EventRowDto.java \
        src/main/java/com/stockproject/portfolio/alert/api/dto/EventDetailDto.java \
        src/main/java/com/stockproject/portfolio/alert/api/dto/EventAlertDto.java \
        src/main/java/com/stockproject/portfolio/alert/api/dto/EventInstrumentDto.java \
        src/main/java/com/stockproject/portfolio/alert/api/dto/UnreadCountDto.java \
        src/test/java/com/stockproject/portfolio/alert/api/AlertEventApiTest.java
git commit -m "feat: 울린 알림 목록·상세·읽음 처리·배지 API를 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---
## Task 13: `MARKET_DATA_DELAYED` 안내와 깨진 조건의 카드

스펙 §7.4 · §11.2와 부록 A.12. ①이 넘긴 4(목록 전체 실패)를 함께 막는다.

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/alert/data/CalendarDay.java`
- Modify: `src/main/java/com/stockproject/portfolio/alert/data/MarketDataMapper.java`
- Modify: `src/main/java/com/stockproject/portfolio/alert/data/MarketDataRepository.java`
- Modify: `src/main/java/com/stockproject/portfolio/alert/store/AlertQueryMapper.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/service/MarketDelayNotices.java`
- Modify: `src/main/java/com/stockproject/portfolio/alert/service/AlertQueryService.java` (전체 교체)
- Modify: `src/main/java/com/stockproject/portfolio/alert/service/AlertEventService.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/api/MarketDelayApiTest.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/api/AlertQueryApiTest.java` (추가)

**Interfaces:**
- Consumes: `StoredTriggers.compile`(Task 5) · `DataNeeds.of(CompiledTrigger, Cadence)` · `Numbers.time(OffsetDateTime)` · `Numbers.date(LocalDate)`(①)
- Produces:
  - `CalendarDay(LocalDate date, boolean isTradingDay, LocalDate prevTradingDay, LocalDate nextTradingDay, OffsetDateTime openAt, OffsetDateTime closeAt)`
  - `MarketDataRepository.openAt(Market, LocalDate) → OffsetDateTime` · `isTradingDay(Market, LocalDate) → boolean` · `nextTradingDay(Market, LocalDate) → LocalDate`
  - `AlertQueryMapper.activeTriggers(UserScope) → List<AlertQueryMapper.ActiveTriggerRow>` · `record ActiveTriggerRow(String cadence, String triggerType, String triggerSpec, String market)`
  - `MarketDelayNotices.forUser(UserScope) → List<NoticeDto>` · 생성자 `MarketDelayNotices(AlertQueryMapper, MarketDataRepository, ObjectMapper, Clock)`
  - `AlertQueryService.UNREADABLE = "조건을 읽을 수 없어요"`

- [ ] **Step 1: 실패하는 테스트를 쓴다 — 지연 안내**

`src/test/java/com/stockproject/portfolio/alert/api/MarketDelayApiTest.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.AlertApiClient;
import com.stockproject.portfolio.alert.FixedClockConfig;
import com.stockproject.portfolio.alert.data.MarketDataRepository;
import com.stockproject.portfolio.alert.service.MarketDelayNotices;
import com.stockproject.portfolio.alert.store.AlertQueryMapper;
import com.stockproject.portfolio.api.dto.NoticeDto;
import com.stockproject.portfolio.auth.UserScope;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Clock;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.UUID;

import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.SAMSUNG;
import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.priceReach;
import static org.assertj.core.api.Assertions.assertThat;

/**
 * 데이터 지연 안내 (스펙 §7.4 · §11.2, 계획 ② A.12). 시세는 sample_alert_market.sql — 일봉·수급 DONE은
 * 9/25(금)까지, 국내 장중 DONE은 9/28 10:00 ~ 10:15다.
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(FixedClockConfig.class)
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class MarketDelayApiTest {

    private static final UserScope YHR = new UserScope(UUID.fromString("40000000-0000-0000-0000-000000000001"));
    private static final String APPLE = "10000000-0000-0000-0000-000000000004";

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;
    @Autowired AlertQueryMapper queries;
    @Autowired MarketDataRepository market;
    AlertApiClient api;

    @BeforeEach
    void setUp() { api = new AlertApiClient(mockMvc, json); }

    /** 지금 10:20, 마지막 장중 신호 10:05 — 기대 시각 10:15를 넘었다. 스펙 §11.2의 예시 그대로다. */
    @Test
    void 장중_시세가_늦으면_목록_위에_안내한다() throws Exception {
        create(priceReach(SAMSUNG, "INTRADAY", 70000));
        jdbc.sql("DELETE FROM market_data_run WHERE kind = 'INTRADAY_QUOTE' AND as_of > '2026-09-28T10:05:00+09'")
                .update();

        for (String path : List.of("/alerts", "/alert-events")) {
            JsonNode notices = api.get(path, "yhr").body().get("notices");
            assertThat(notices).as(path).hasSize(1);
            JsonNode n = notices.get(0);
            assertThat(n.get("code").asText()).isEqualTo("MARKET_DATA_DELAYED");
            assertThat(n.get("severity").asText()).isEqualTo("warn");
            assertThat(n.get("message").asText()).isEqualTo("국내 장중 시세가 10:05 이후 들어오지 않았어요");
            assertThat(n.get("params").get("market").asText()).isEqualTo("KR");
            assertThat(n.get("params").get("kind").asText()).isEqualTo("INTRADAY_QUOTE");
            assertThat(n.get("params").get("last_done").asText()).isEqualTo("2026-09-28T10:05:00+09:00");
        }
    }

    @Test
    void 제때_들어오면_안내하지_않는다() throws Exception {
        create(priceReach(SAMSUNG, "INTRADAY", 70000));
        create(priceReach(SAMSUNG, "CLOSE", 70000));

        assertThat(api.get("/alerts", "yhr").body().get("notices")).isEmpty();
    }

    @Test
    void 꺼진_알림이_기다리는_데이터는_보지_않는다() throws Exception {
        UUID id = create(priceReach(SAMSUNG, "INTRADAY", 70000));
        jdbc.sql("DELETE FROM market_data_run WHERE kind = 'INTRADAY_QUOTE' AND as_of > '2026-09-28T10:05:00+09'")
                .update();
        assertThat(api.post("/alerts/" + id + "/pause", "yhr", null).status()).isEqualTo(204);

        assertThat(api.get("/alerts", "yhr").body().get("notices")).isEmpty();
    }

    @Test
    void 장_시간_밖에는_장중_시세를_보지_않는다() throws Exception {
        create(priceReach(SAMSUNG, "INTRADAY", 70000));

        assertThat(notices("2026-09-28T16:00:00+09:00")).isEmpty();
    }

    @Test
    void 장중_시세가_오늘_하나도_없으면_아직이라고_쓴다() throws Exception {
        create(priceReach(SAMSUNG, "INTRADAY", 70000));
        jdbc.sql("DELETE FROM market_data_run WHERE kind = 'INTRADAY_QUOTE'").update();

        assertThat(notices("2026-09-28T09:05:00+09:00")).isEmpty();
        assertThat(notices("2026-09-28T09:15:00+09:00")).extracting(NoticeDto::message)
                .containsExactly("국내 장중 시세가 아직 들어오지 않았어요");
    }

    /** 국내 일봉은 장 마감 후 당일 중에 와야 한다 — 9/28 일봉은 9/29 00:00까지다. */
    @Test
    void 국내_일봉이_늦으면_안내한다() throws Exception {
        create(priceReach(SAMSUNG, "CLOSE", 70000));

        assertThat(notices("2026-09-28T23:00:00+09:00")).isEmpty();
        assertThat(notices("2026-09-29T01:00:00+09:00")).extracting(NoticeDto::message)
                .containsExactly("국내 일봉이 9/25 이후 들어오지 않았어요");
    }

    /** 미국 일봉은 다음 미국 장 개장 전에 와야 한다 — 9/28 일봉은 9/29 09:30(뉴욕)까지다. */
    @Test
    void 미국_일봉이_늦으면_안내한다() throws Exception {
        create(priceReach(APPLE, "CLOSE", 300));

        assertThat(notices("2026-09-29T22:00:00+09:00")).isEmpty();
        assertThat(notices("2026-09-29T23:00:00+09:00")).extracting(NoticeDto::message)
                .containsExactly("미국 일봉이 9/25 이후 들어오지 않았어요");
    }

    /** 수급 확정치는 다음 국내 영업일 개장 전에 와야 한다 — 9/28 수급은 9/29 09:00까지다. */
    @Test
    void 수급이_늦으면_안내한다() throws Exception {
        create("""
                { "instrument_id": "%s", "name": "외국인", "cadence": "CLOSE", "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "investor_streak",
                                    "params": { "investor": "foreign", "side": "buy", "days": 3 } } }
                """.formatted(SAMSUNG));

        assertThat(notices("2026-09-29T08:50:00+09:00")).isEmpty();
        assertThat(notices("2026-09-29T09:10:00+09:00")).extracting(NoticeDto::message)
                .containsExactly("국내 수급이 9/25 이후 들어오지 않았어요");
    }

    // ---- 도우미 ----------------------------------------------------------------

    private List<NoticeDto> notices(String now) {
        Clock clock = Clock.fixed(Instant.from(OffsetDateTime.parse(now)), ZoneId.of("Asia/Seoul"));
        return new MarketDelayNotices(queries, market, json, clock).forUser(YHR);
    }

    private UUID create(String body) throws Exception {
        return UUID.fromString(api.post("/alerts", "yhr", body).body().get("alert_id").asText());
    }
}
```

- [ ] **Step 2: 실패하는 테스트를 쓴다 — 깨진 조건의 카드**

`AlertQueryApiTest`에 더한다. 이 클래스의 기존 `create(String body)` 도우미(알림을 만들고 ID를 돌려준다), `api` · `jdbc` 필드, `AlertApiClient.Response` import를 쓴다.

```java
    /** 저장된 조건 하나가 지금 코드로 읽히지 않아도 목록과 상세는 200이다 (계획 ② A.12 #4). */
    @Test
    void 읽을_수_없는_조건은_그_카드만_문구로_보인다() throws Exception {
        UUID good = create(priceReach(SAMSUNG, "INTRADAY", 70000));
        UUID broken = create(priceReach(SAMSUNG, "INTRADAY", 71000));
        jdbc.sql("UPDATE alert SET trigger_spec = '{\"preset_key\": \"gone\", \"params\": {}}' WHERE alert_id = :id")
                .param("id", broken).update();

        Response list = api.get("/alerts", "yhr");

        assertThat(list.status()).isEqualTo(200);
        for (JsonNode card : list.body().get("data").get("rows")) {
            String expected = card.get("alert_id").asText().equals(broken.toString())
                    ? "조건을 읽을 수 없어요" : "장중 · 현재가 ≥ 70,000원";
            assertThat(card.get("summary").get("short").asText()).isEqualTo(expected);
        }
        Response detail = api.get("/alerts/" + broken, "yhr");
        assertThat(detail.status()).isEqualTo(200);
        assertThat(detail.body().get("summary").get("sentence").asText()).isEqualTo("조건을 읽을 수 없어요");
        assertThat(api.get("/alerts/" + good, "yhr").status()).isEqualTo(200);
    }
```

- [ ] **Step 3: 실패를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.api.MarketDelayApiTest' --tests 'com.stockproject.portfolio.alert.api.AlertQueryApiTest'`
Expected: FAIL — `MarketDelayNotices`가 없어 컴파일 오류.

- [ ] **Step 4: 캘린더에 개장 시각과 다음 거래일을 더한다**

`src/main/java/com/stockproject/portfolio/alert/data/CalendarDay.java`를 바꾼다.

```java
package com.stockproject.portfolio.alert.data;

import java.time.LocalDate;
import java.time.OffsetDateTime;

/** 시장 캘린더 하루 (데이터 요구사항 §4.2). 휴장일은 openAt · closeAt이 null일 수 있다. */
public record CalendarDay(LocalDate date, boolean isTradingDay, LocalDate prevTradingDay, LocalDate nextTradingDay,
                          OffsetDateTime openAt, OffsetDateTime closeAt) { }
```

`MarketDataMapper.calendar`의 SELECT 목록을 바꾼다.

```java
    @Select("""
            SELECT date, is_trading_day, prev_trading_day, next_trading_day, open_at, close_at
              FROM dim_market_calendar
             WHERE market = #{market} AND date BETWEEN #{from} AND #{to}
             ORDER BY date
            """)
    List<CalendarDay> calendar(@Param("market") String market, @Param("from") LocalDate from,
                               @Param("to") LocalDate to);
```

`MarketDataRepository`의 `closeAt` 아래에 더한다.

```java
    /** 그날의 개장 시각. 캘린더에 없으면 정규 개장(KR 09:00 · US 09:30 현지)으로 근사한다. */
    public OffsetDateTime openAt(Market market, LocalDate date) {
        List<CalendarDay> days = mapper.calendar(market.name(), date, date);
        if (!days.isEmpty() && days.get(0).openAt() != null) return days.get(0).openAt();
        LocalTime open = market == Market.US ? LocalTime.of(9, 30) : LocalTime.of(9, 0);
        return date.atTime(open).atZone(zone(market)).toOffsetDateTime();
    }

    public boolean isTradingDay(Market market, LocalDate date) {
        List<CalendarDay> days = mapper.calendar(market.name(), date, date);
        return days.isEmpty() ? !isWeekend(date) : days.get(0).isTradingDay();
    }

    public LocalDate nextTradingDay(Market market, LocalDate date) {
        List<CalendarDay> days = mapper.calendar(market.name(), date, date);
        if (!days.isEmpty()) return days.get(0).nextTradingDay();
        LocalDate d = date.plusDays(1);
        while (isWeekend(d)) d = d.plusDays(1);
        return d;
    }
```

- [ ] **Step 5: 활성 알림의 조건을 읽는다**

`AlertQueryMapper`의 `InstrumentLabel` 레코드 위에 더한다.

```java
    /** 지연 안내가 볼 활성 알림의 조건과 종목 시장. 종목 마스터에 없으면 market이 null이다. */
    @Select("""
            SELECT a.cadence, a.trigger_type, a.trigger_spec::text AS trigger_spec, i.market
              FROM alert a LEFT JOIN instrument i USING (instrument_id)
             WHERE a.user_id = #{scope.userId} AND a.status = 'ACTIVE' AND a.deleted_at IS NULL
            """)
    List<ActiveTriggerRow> activeTriggers(@Param("scope") UserScope scope);

    record ActiveTriggerRow(String cadence, String triggerType, String triggerSpec, String market) { }
```

- [ ] **Step 6: 지연 판정을 쓴다**

`src/main/java/com/stockproject/portfolio/alert/service/MarketDelayNotices.java`:

```java
package com.stockproject.portfolio.alert.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.DataKind;
import com.stockproject.portfolio.alert.compile.DataNeeds;
import com.stockproject.portfolio.alert.data.MarketDataRepository;
import com.stockproject.portfolio.alert.evaluation.EvaluationInput;
import com.stockproject.portfolio.alert.sentence.Numbers;
import com.stockproject.portfolio.alert.store.AlertQueryMapper;
import com.stockproject.portfolio.alert.validation.StoredTriggers;
import com.stockproject.portfolio.api.dto.NoticeDto;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.domain.Market;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.EnumSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * MARKET_DATA_DELAYED (스펙 §7.4, 계획 ② A.12). 사용자의 활성 알림이 기다리는 (시장, 종류)마다 최신 DONE이
 * 기대 시각보다 늦었는가를 본다. 보유 스냅샷은 시장 데이터가 아니라 보지 않는다.
 */
@Service
public class MarketDelayNotices {

    static final String CODE = "MARKET_DATA_DELAYED";
    private static final List<DataKind> ORDER = List.of(DataKind.INTRADAY_QUOTE, DataKind.DAILY_BAR, DataKind.DAILY_FLOW);
    /** 기대 시각이 지난 거래일을 이만큼 거슬러 찾는다 — 연휴를 넉넉히 넘는다. */
    private static final int LOOKBACK_DAYS = 14;

    private final AlertQueryMapper queries;
    private final MarketDataRepository market;
    private final ObjectMapper json;
    private final Clock clock;

    public MarketDelayNotices(AlertQueryMapper queries, MarketDataRepository market, ObjectMapper json, Clock clock) {
        this.queries = queries;
        this.market = market;
        this.json = json;
        this.clock = clock;
    }

    public List<NoticeDto> forUser(UserScope scope) {
        Map<Market, Set<DataKind>> waits = new EnumMap<>(Market.class);
        for (AlertQueryMapper.ActiveTriggerRow r : queries.activeTriggers(scope)) {
            if (r.market() == null) continue;
            Cadence cadence = Cadence.valueOf(r.cadence());
            StoredTriggers.compile(json, r.triggerType(), r.triggerSpec(), cadence).ifPresent(t ->
                    waits.computeIfAbsent(Market.valueOf(r.market()), m -> EnumSet.noneOf(DataKind.class))
                            .addAll(DataNeeds.of(t, cadence)));
        }
        OffsetDateTime now = OffsetDateTime.now(clock);
        List<NoticeDto> out = new ArrayList<>();
        for (Market m : List.of(Market.KR, Market.US)) {
            Set<DataKind> kinds = waits.getOrDefault(m, Set.of());
            for (DataKind kind : ORDER) {
                if (!kinds.contains(kind)) continue;
                Optional<NoticeDto> notice = kind == DataKind.INTRADAY_QUOTE ? intraday(m, now) : daily(m, kind, now);
                notice.ifPresent(out::add);
            }
        }
        return out;
    }

    /** 장 시간 안에서만 본다. 기준은 오늘 개장 뒤의 마지막 DONE, 없으면 개장 시각이다. */
    private Optional<NoticeDto> intraday(Market m, OffsetDateTime now) {
        LocalDate today = now.atZoneSameInstant(MarketDataRepository.zone(m)).toLocalDate();
        if (!market.isTradingDay(m, today)) return Optional.empty();
        OffsetDateTime open = market.openAt(m, today);
        OffsetDateTime close = market.closeAt(m, today);
        if (now.isBefore(open) || now.isAfter(close)) return Optional.empty();

        OffsetDateTime last = market.latestDoneAt(m, DataKind.INTRADAY_QUOTE).orElse(null);
        boolean fromToday = last != null && !last.isBefore(open);
        OffsetDateTime base = fromToday ? last : open;
        if (!now.isAfter(base.plus(EvaluationInput.allowedGap(m)))) return Optional.empty();
        String message = label(m) + " 장중 시세가 "
                + (fromToday ? Numbers.time(last) + " 이후 들어오지 않았어요" : "아직 들어오지 않았어요");
        return Optional.of(notice(m, DataKind.INTRADAY_QUOTE, message, last));
    }

    /** 기대 시각이 지난 가장 최근 거래일 D에 대해 최신 DONE 거래일이 D보다 이르면 늦은 것이다. */
    private Optional<NoticeDto> daily(Market m, DataKind kind, OffsetDateTime now) {
        LocalDate due = latestDueDay(m, kind, now);
        if (due == null) return Optional.empty();
        Optional<LocalDate> done = market.latestDoneDate(m, kind);
        if (done.isPresent() && !done.get().isBefore(due)) return Optional.empty();
        String what = kind == DataKind.DAILY_BAR ? " 일봉이 " : " 수급이 ";
        String message = label(m) + what
                + done.map(d -> Numbers.date(d) + " 이후 들어오지 않았어요").orElse("아직 들어오지 않았어요");
        return Optional.of(notice(m, kind, message, market.latestDoneAt(m, kind).orElse(null)));
    }

    private LocalDate latestDueDay(Market m, DataKind kind, OffsetDateTime now) {
        LocalDate d = now.atZoneSameInstant(MarketDataRepository.zone(m)).toLocalDate();
        for (int i = 0; i < LOOKBACK_DAYS; i++) {
            if (market.isTradingDay(m, d) && !now.isBefore(deadline(m, kind, d))) return d;
            d = d.minusDays(1);
        }
        return null;
    }

    /** 스펙 §16.2의 도착 시점 — 국내 일봉은 당일 중, 미국 일봉은 다음 미국 장 개장 전, 수급은 다음 국내 영업일 개장 전. */
    private OffsetDateTime deadline(Market m, DataKind kind, LocalDate d) {
        if (kind == DataKind.DAILY_BAR && m == Market.KR) {
            return d.plusDays(1).atStartOfDay(MarketDataRepository.zone(m)).toOffsetDateTime();
        }
        return market.openAt(m, market.nextTradingDay(m, d));
    }

    private static NoticeDto notice(Market m, DataKind kind, String message, OffsetDateTime lastDone) {
        Map<String, Object> params = new LinkedHashMap<>();
        params.put("market", m.name());
        params.put("kind", kind.name());
        params.put("last_done", AlertTimes.kst(lastDone));
        return new NoticeDto(CODE, "warn", message, params);
    }

    private static String label(Market m) { return m == Market.US ? "미국" : "국내"; }
}
```

- [ ] **Step 7: 목록과 상세가 안내를 싣고 깨진 조건을 견딘다**

`src/main/java/com/stockproject/portfolio/alert/service/AlertQueryService.java`를 통째로 바꾼다.

```java
package com.stockproject.portfolio.alert.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.api.dto.AlertCardDto;
import com.stockproject.portfolio.alert.api.dto.AlertDetailDto;
import com.stockproject.portfolio.alert.api.dto.AlertListData;
import com.stockproject.portfolio.alert.api.dto.InstrumentDto;
import com.stockproject.portfolio.alert.api.dto.RecentEventDto;
import com.stockproject.portfolio.alert.api.dto.ShortSummaryDto;
import com.stockproject.portfolio.alert.api.dto.SummaryDto;
import com.stockproject.portfolio.alert.api.dto.UnreadDto;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.sentence.SentenceWriter;
import com.stockproject.portfolio.alert.sentence.Summary;
import com.stockproject.portfolio.alert.store.AlertListRow;
import com.stockproject.portfolio.alert.store.AlertQueryMapper;
import com.stockproject.portfolio.alert.store.AlertRow;
import com.stockproject.portfolio.alert.store.AlertStore;
import com.stockproject.portfolio.alert.validation.StoredTriggers;
import com.stockproject.portfolio.api.dto.Envelope;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.domain.Market;
import com.stockproject.portfolio.validation.RequestRejected;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

/**
 * 알림 탭과 알림 상세의 읽기 (§11.2 · §11.3). 조건 문장은 읽을 때마다 지금 코드로 만든다.
 * 저장된 조건을 지금 코드가 읽지 못하면 그 알림만 UNREADABLE 문장으로 보인다 — 목록 전체가 실패하지 않는다.
 */
@Service
public class AlertQueryService {

    private static final Logger log = LoggerFactory.getLogger(AlertQueryService.class);

    static final int UNREAD_LIMIT = 3;
    static final int RECENT_LIMIT = 5;
    public static final String UNREADABLE = "조건을 읽을 수 없어요";

    private final AlertQueryMapper queries;
    private final AlertStore alerts;
    private final MarketDelayNotices notices;
    private final ObjectMapper json;

    public AlertQueryService(AlertQueryMapper queries, AlertStore alerts, MarketDelayNotices notices,
                             ObjectMapper json) {
        this.queries = queries;
        this.alerts = alerts;
        this.notices = notices;
        this.json = json;
    }

    public Envelope<AlertListData> list(UserScope scope) {
        List<AlertCardDto> rows = queries.list(scope).stream().map(this::card).toList();
        List<UnreadDto> unread = queries.unread(scope, UNREAD_LIMIT).stream()
                .map(e -> new UnreadDto(e.eventId(), e.title(), e.cadence(), e.market(), AlertTimes.kst(e.asOf()),
                        AlertTimes.kst(e.firedAt()), e.alertDeleted()))
                .toList();
        int more = Math.max(0, queries.unreadCount(scope) - unread.size());
        return new Envelope<>(AlertTimes.kst(queries.latestEvaluatedAsOf(scope)),
                new AlertListData(rows, unread, more), rows.isEmpty() ? "NO_ALERTS" : null, notices.forUser(scope));
    }

    public AlertDetailDto detail(UserScope scope, UUID alertId) {
        AlertRow a = alerts.findOwned(scope, alertId)
                .orElseThrow(() -> new RequestRejected("ALERT_NOT_FOUND", "알림을 찾을 수 없어요", true));
        AlertQueryMapper.InstrumentLabel instrument = queries.instrument(a.instrumentId());
        String label = instrument == null ? null : instrument.label();
        String market = instrument == null ? null : instrument.market();
        Summary summary = summary(a.alertId(), a.triggerType(), a.triggerSpec(), a.cadence(), market);
        List<RecentEventDto> recent = queries.recentEvents(alertId, RECENT_LIMIT).stream()
                .map(e -> new RecentEventDto(e.eventId(), e.title(), AlertTimes.kst(e.asOf()), e.read()))
                .toList();
        return new AlertDetailDto(a.alertId(), a.name(), new InstrumentDto(a.instrumentId(), label, market),
                a.cadence(), a.notifyMode(), a.cooldownMin(), AlertTimes.kst(a.expiresAt()), a.status(),
                a.triggerType(), read(a.triggerSpec()), new SummaryDto(summary.shortText(), summary.sentence()),
                a.lastResult(), a.unknownReason(), AlertTimes.kst(a.evaluatedAsOf()), recent);
    }

    private AlertCardDto card(AlertListRow r) {
        Summary summary = summary(r.alertId(), r.triggerType(), r.triggerSpec(), r.cadence(), r.instrumentMarket());
        return new AlertCardDto(r.alertId(), r.name(),
                new InstrumentDto(r.instrumentId(), r.instrumentLabel(), r.instrumentMarket()), r.cadence(),
                r.notifyMode(), r.status(), new ShortSummaryDto(summary.shortText()), r.lastResult(),
                r.unknownReason(), AlertTimes.kst(r.evaluatedAsOf()), AlertTimes.kst(r.lastFiredAt()));
    }

    private Summary summary(UUID alertId, String triggerType, String triggerSpec, String cadence, String market) {
        Cadence c = Cadence.valueOf(cadence);
        return StoredTriggers.compile(json, triggerType, triggerSpec, c)
                .map(t -> SentenceWriter.summary(t, c, market == null ? Market.KR : Market.valueOf(market)))
                .orElseGet(() -> {
                    log.warn("저장된 조건을 읽을 수 없다 alert_id={}", alertId);
                    return new Summary(UNREADABLE, UNREADABLE);
                });
    }

    /** jsonb에서 읽은 문자열이라 늘 JSON이다. 수정 화면이 받은 그대로 다시 보낸다(§11.3). */
    private JsonNode read(String text) {
        try {
            return json.readTree(text);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("저장된 trigger_spec이 JSON이 아니다", e);
        }
    }
}
```

`AlertEventService`에 안내를 싣는다. 필드와 생성자를 바꾸고 `list`의 마지막 `List.of()`를 `notices.forUser(scope)`로 바꾼다.

```java
    private final AlertEventMapper events;
    private final AlertQueryMapper queries;
    private final MarketDelayNotices notices;
    private final ObjectMapper json;
    private final Clock clock;

    public AlertEventService(AlertEventMapper events, AlertQueryMapper queries, MarketDelayNotices notices,
                             ObjectMapper json, Clock clock) {
        this.events = events;
        this.queries = queries;
        this.notices = notices;
        this.json = json;
        this.clock = clock;
    }
```

```java
        return new Envelope<>(AlertTimes.kst(queries.latestEvaluatedAsOf(scope)), new EventListData(dtos, next),
                empty, notices.forUser(scope));
```

- [ ] **Step 8: 통과를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.alert.*'`
Expected: PASS — ①의 `AlertQueryApiTest.알림이_없으면_빈_상태_사유다`의 `notices` 빈 배열도 그대로다(알림이 없으면 기다리는 데이터도 없다).

- [ ] **Step 9: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/data/CalendarDay.java \
        src/main/java/com/stockproject/portfolio/alert/data/MarketDataMapper.java \
        src/main/java/com/stockproject/portfolio/alert/data/MarketDataRepository.java \
        src/main/java/com/stockproject/portfolio/alert/store/AlertQueryMapper.java \
        src/main/java/com/stockproject/portfolio/alert/service/MarketDelayNotices.java \
        src/main/java/com/stockproject/portfolio/alert/service/AlertQueryService.java \
        src/main/java/com/stockproject/portfolio/alert/service/AlertEventService.java \
        src/test/java/com/stockproject/portfolio/alert/api/MarketDelayApiTest.java \
        src/test/java/com/stockproject/portfolio/alert/api/AlertQueryApiTest.java
git commit -m "feat: 알림이 기다리는 시장 데이터가 늦으면 목록 위에 안내하고 깨진 조건은 그 카드만 문구로 보인다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---
## Task 14: 로컬 CORS · 아키텍처 규칙 · 결정 기록 · 끝에서 끝 흐름

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/auth/LocalCorsConfig.java`
- Modify: `src/test/java/com/stockproject/portfolio/auth/LocalCorsTest.java`
- Modify: `src/test/java/com/stockproject/portfolio/ArchitectureRulesTest.java`
- Create: `src/test/java/com/stockproject/portfolio/alert/api/AlertRuntimeFlowTest.java`
- Modify: `docs/decisions.md`

**Interfaces:**
- Consumes: 앞 태스크 전부 — `EvaluationRunner.tick()` · `DeliveryDispatcher.dispatchOnce()` · `FakePushGateway` · `/alert-events*`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`LocalCorsTest`에 더한다.

```java
    @Test
    void 울린_알림_preflight를_허용한다() throws Exception {
        mockMvc.perform(options("/alert-events/read-all")
                        .header("Origin", ORIGIN)
                        .header("Access-Control-Request-Method", "POST")
                        .header("Access-Control-Request-Headers", "Authorization"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", ORIGIN))
                .andExpect(header().string("Access-Control-Allow-Methods", "GET,POST"));
    }
```

`ArchitectureRulesTest`에 더한다(클래스의 `classes` 필드와 `noClasses` static import를 쓴다).

```java
    /** 평가기와 발송기는 요청 경로와 무관하게 돈다. 컨트롤러·응답 모양이 바뀌어도 런타임이 흔들리지 않는다. */
    @Test
    void 알림_런타임은_API_계층에_의존하지_않는다() {
        noClasses().that().resideInAnyPackage("..alert.runtime..", "..alert.delivery..")
                .should().dependOnClassesThat().resideInAnyPackage("..alert.api..", "..portfolio.api..")
                .because("평가와 발송은 화면 계층을 모른다")
                .check(classes);
    }
```

`src/test/java/com/stockproject/portfolio/alert/api/AlertRuntimeFlowTest.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.AlertApiClient;
import com.stockproject.portfolio.alert.FixedClockConfig;
import com.stockproject.portfolio.alert.delivery.DeliveryDispatcher;
import com.stockproject.portfolio.alert.delivery.FakePushGateway;
import com.stockproject.portfolio.alert.delivery.PushMessage;
import com.stockproject.portfolio.alert.runtime.EvaluationRunner;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.web.servlet.MockMvc;

import java.util.UUID;

import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.SAMSUNG;
import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.priceReach;
import static org.assertj.core.api.Assertions.assertThat;

/** 알림을 걸고 → 평가되고 → 푸시가 나가고 → 앱이 읽는다 (스펙 §9.1). 지금은 2026-09-28 10:20이다. */
@SpringBootTest(properties = "portfolio.alert.push.enabled=true")
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import({FixedClockConfig.class, FakePushGateway.Config.class})
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class AlertRuntimeFlowTest {

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    @Autowired EvaluationRunner runner;
    @Autowired DeliveryDispatcher dispatcher;
    @Autowired FakePushGateway gateway;
    AlertApiClient api;

    @BeforeEach
    void setUp() {
        api = new AlertApiClient(mockMvc, json);
        gateway.reset();
    }

    @Test
    void 조건이_충족되면_기록되고_iOS로_보내지고_앱에서_읽는다() throws Exception {
        assertThat(api.post("/devices", "yhr",
                "{ \"expo_push_token\": \"ExponentPushToken[yhr]\", \"platform\": \"IOS\" }").status()).isEqualTo(200);
        UUID alert = UUID.fromString(api.post("/alerts", "yhr", priceReach(SAMSUNG, "INTRADAY", 63000)).body()
                .get("alert_id").asText());

        runner.tick();
        assertThat(dispatcher.dispatchOnce()).isEqualTo(1);

        PushMessage pushed = gateway.sent.get(0).get(0);
        assertThat(pushed.to()).isEqualTo("ExponentPushToken[yhr]");
        assertThat(pushed.title()).isEqualTo("삼성전자 · 가격 도달");
        assertThat(pushed.body()).isEqualTo("현재가 63,500원 ≥ 63,000원 · 10:15 기준");

        JsonNode list = api.get("/alerts", "yhr").body();
        JsonNode card = list.get("data").get("rows").get(0);
        assertThat(card.get("last_result").asText()).isEqualTo("TRUE");
        assertThat(card.get("last_fired_at").isNull()).isFalse();
        assertThat(list.get("as_of").asText()).isEqualTo("2026-09-28T10:15:00+09:00");
        assertThat(list.get("data").get("unread").get(0).get("event_id").asText())
                .isEqualTo(pushed.eventId().toString());
        assertThat(api.get("/alerts/" + alert, "yhr").body().get("recent_events")).hasSize(1);
        assertThat(api.get("/alert-events/unread-count", "yhr").body().get("count").asInt()).isEqualTo(1);

        assertThat(api.get("/alert-events/" + pushed.eventId(), "yhr").body().get("body").asText())
                .isEqualTo(pushed.body());
        assertThat(api.post("/alert-events/" + pushed.eventId() + "/read", "yhr", null).status()).isEqualTo(204);
        assertThat(api.get("/alert-events/unread-count", "yhr").body().get("count").asInt()).isZero();

        runner.tick();
        assertThat(dispatcher.dispatchOnce()).isZero();   // 같은 시점은 다시 평가하지 않고, 참이 이어지면 울리지 않는다
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test --tests 'com.stockproject.portfolio.auth.LocalCorsTest' --tests 'com.stockproject.portfolio.ArchitectureRulesTest' --tests 'com.stockproject.portfolio.alert.api.AlertRuntimeFlowTest'`
Expected: `LocalCorsTest.울린_알림_preflight를_허용한다`만 FAIL(403) — 나머지는 앞 태스크로 이미 통과한다. 아키텍처 규칙이 실패하면 그 의존을 고친다(규칙을 고치지 않는다).

- [ ] **Step 3: 로컬 CORS에 울린 알림을 연다**

`LocalCorsConfig.corsConfigurationSource()`에서 `/devices/**` 줄 다음에 더한다.

```java
        source.registerCorsConfiguration("/alert-events/**", allowing("GET", "POST"));
```

클래스 Javadoc의 첫 문단을 바꾼다.

```java
 * <p>여는 범위는 앱이 실제로 부르는 경로와 그 경로가 쓰는 메서드뿐이다 — 로그인, 포트폴리오 조회,
 * 알림, 울린 알림, 종목 검색, 푸시 기기. 나머지 경로는 등록하지 않았고, 등록하지 않은 경로의 preflight는 거절된다.</p>
```

- [ ] **Step 4: 결정 기록을 더한다**

`docs/decisions.md`의 `## 알림 trigger_spec — JSONB, 타입 핸들러 없이` 절 다음(`## 인덱스 · 보관 기간 · 파티셔닝` 앞)에 더한다.

```markdown
## 알림 런타임 — 앱 안의 스케줄 작업, 중복 방지는 데이터로

평가기 · 발송기 · 영수증 확인기는 `portfolio-api` 안의 `@Scheduled` 작업이고 모든 복제본에서 돈다(알림 스펙
§8.1). 리더 선출과 분산 잠금을 두지 않는다. 평가 결과는 읽을 때의 `version`과 직전 `evaluated_as_of`를 조건으로
건 갱신으로만 반영되고, 발화는 `UNIQUE (alert_id, as_of)`, 발송 행은 `FOR UPDATE SKIP LOCKED`로 한 복제본만
집는다. 이 성질은 복제본 수와 무관하게 성립한다.

미리보기와 평가기는 데이터 시점 하나의 입력을 같은 메서드(`EvaluationInputFactory.closeAt` · `intradayAt` ·
`userAt`)로 만든다. 같은 시점이면 같은 결과가 나오는 것은 `PreviewEvaluatorParityTest`가 지킨다.

잠금 순서는 모든 트랜잭션이 `alert` → `alert_state` → 대상 종목 advisory lock이다. 한 번만 알림은 끝낼 때
`alert`를 바꾸므로 반영 전에 `alert` 행을 먼저 잡는다.

**감수하는 것**: 복제본마다 같은 알림을 읽고 계산한다. 반영에서 진 쪽의 계산은 버려진다. 템플릿·업캐스팅을
바꾸는 롤링 배포에서는 옛 파드와 새 파드가 함께 도는 동안 해시 재기준이 오가며 엣지를 놓칠 수 있다.

**되돌리는 조건**: 평가 한 번이 주기(1분)의 절반을 넘기거나 API 응답이 평가 주기에 맞춰 느려지면, 같은 이미지를
`ALERT_RUNTIME_ENABLED=true`인 워커 Deployment로 띄우고 API 파드에서는 `false`로 끈다(알림 스펙 §8.4).
코드는 바뀌지 않는다.

## 알림 푸시 — Expo Push API, 발송 대기는 테이블로

발화는 `alert_event`, 기기별 발송은 `alert_delivery` 행이다. 평가 트랜잭션이 발화와 발송 행을 함께 쓰고,
발송기가 그 행을 집어 Expo Push API로 보낸다. 메시지 브로커를 두지 않는다 — DB 커밋과 발행을 한 번에
성공시킬 수 없어 결국 같은 대기 테이블이 필요하다(알림 스펙 §9.1). HTTP 호출은 `RestClient`로 하고 Expo의
서버 SDK를 들이지 않는다. 호출 둘(전송 · 영수증)뿐이라 SDK가 줄여 줄 코드가 없다.

Expo 호출은 DB 트랜잭션 밖에서 한다. 발송기는 행을 `SENDING`과 임대 시각으로 바꿔 커밋한 뒤 보내고, 결과를
짧은 트랜잭션으로 쓴다. 등록이 풀린 기기는 그 커밋 뒤에 따로 지운다. 기한이 지난 대기 행(장중 30분 · 종가
12시간)과 기기 소유자가 바뀐 행은 보내지 않는다. 발송 행은 iOS 기기에만 만든다.

푸시는 `EXPO_PUSH_ENABLED`가 `true`일 때만 나간다. 꺼져 있어도 발화 기록과 배지는 남는다.

**감수하는 것**: Expo가 받았는데 결과를 기록하지 못하면(파드가 죽었거나 기록이 거듭 실패) 임대가 끝난 뒤, Expo가
받은 뒤 읽기 시간 초과가 나면 재시도 간격 뒤에 같은 푸시가 한 번 더 간다.
재시도 간격과 상한, 발송 기한은 이쪽이 정한 값이다(30초부터 두 배씩, 5번째 시도에서 끝). 발송 행을 지우지
않아 쌓인다. Android 푸시를 열 때는 발송 행의 iOS 조건을 바꿔야 한다.

**되돌리는 조건**: 발화를 푸시 말고 다른 소비자도 읽어야 하면 `alert_event`에서 내보내는 발행을 더한다.
`alert_delivery`가 1,000만 행을 넘으면 끝난 행(`SENT`이고 티켓이 빈 행, `FAILED`)의 보관 기간을 정한다.
```

- [ ] **Step 5: 전체 테스트를 돌린다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_alert_test?currentSchema=app,data' ./gradlew test`
Expected: PASS (포트폴리오 테스트 포함 전부)

- [ ] **Step 6: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/auth/LocalCorsConfig.java \
        src/test/java/com/stockproject/portfolio/auth/LocalCorsTest.java \
        src/test/java/com/stockproject/portfolio/ArchitectureRulesTest.java \
        src/test/java/com/stockproject/portfolio/alert/api/AlertRuntimeFlowTest.java \
        docs/decisions.md
git commit -m "docs: 알림 런타임과 푸시 발송의 결정을 기록하고 울린 알림 경로를 로컬 CORS에 연다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

# 마무리

- 모든 태스크가 끝나면 superpowers:finishing-a-development-branch를 따른다. 병합 · 푸시 · PR은 사람에게 묻고 승인을 받은 뒤에 한다(부록 A.13).
- 운영에서 푸시를 켜는 일(Secret · `EXPO_PUSH_ENABLED` · 클러스터에서 `exp.host`로 나가는 통신)은 이 계획 밖이고 사람이 한다.
- 포트폴리오 EOD 스냅샷 생성이 생기면 그 배치의 끝에서 `SnapshotRunRecorder.record(asOf)`를 부른다(부록 A.10).
