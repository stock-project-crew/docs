# 매수·매도 타이밍 알림 — 백엔드 구현 계획 ① 알림 규칙과 조회

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

- **작성일**: 2026-10-11
- **대상 저장소**: `back-end/` (github.com/stock-project-crew/back-end)
- **근거 스펙**: [알림 스펙](../specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md) · [앱 정보 구조](../specs/app-information-architecture.md) · [데이터 요구사항](../specs/data-requirements.md) · [설계 공유 및 합의](../meetings/2026-09-27-buy-sell-timing-alert-design-review.md)
- **이어지는 계획**: ② 평가 런타임과 전달(평가기·발화 기록·발송기·울린 알림 API) · ③ 프론트 알림 탭과 흐름. 이 계획은 그 둘이 기대는 규칙·저장·조회를 만든다.
- **스펙 수정 금지**: 이 계획은 스펙을 인용만 한다. 스펙과 다르게 구현해야 할 사정이 생기면 코드를 바꾸지 말고 멈춰서 보고한다.

**Goal:** 로그인한 사용자가 알림을 만들고·고치고·끄고·지우고, 만들기 전에 미리보기로 조건 문장과 현재값(조건별 ✓/✕/?)을 받는다. 알림 목록·상세·카탈로그·종목 검색·기기 등록 API가 스펙 §11대로 응답한다. 데이터팀 테이블은 로컬·테스트 전용 미러로 대신한다.

**Architecture:** 규칙의 해석·계산은 프레임워크를 모르는 순수 패키지에 둔다 — 카탈로그(코드 상수) → 트리거 해석 → 검증 → 컴파일(프리셋 전개·`lag` 결정·`spec_hash`) → 지표 계산 → 3값 조건 평가 → 문장 생성. 이 순수 계층을 ②의 평가기가 그대로 다시 쓴다. 바깥 층은 기존 관례를 따른다 — MyBatis 매퍼가 미러와 알림 테이블을 읽고 쓰고, 서비스가 순서를 지키고, 컨트롤러는 서비스만 부른다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · Gradle (Kotlin DSL) · PostgreSQL 16 · Flyway(평문 SQL) · MyBatis(ORM 없음) · Spring Security + JWT · JUnit 5 + AssertJ + ArchUnit

---

## Global Constraints

이 절의 규칙은 모든 태스크의 요구사항에 암묵적으로 포함된다.

- **Java 21, Spring Boot 3.4.5, PostgreSQL 16.** 새 라이브러리를 들이지 않는다. 필요한 것은 전부 기존 의존성(`spring-boot-starter-web` · `validation` · `security` · `mybatis-spring-boot-starter` · `flyway` · `jackson`)에 있다.
- **JSON 필드명은 snake_case.** `spring.jackson.property-naming-strategy: SNAKE_CASE`가 전역으로 걸려 있다. record 컴포넌트는 camelCase로 쓰면 응답이 snake_case로 나간다.
- **사용자 ID를 요청에서 받지 않는다.** 컨트롤러는 `UserScope` 파라미터로만 사용자를 안다(`ArchitectureRulesTest.핸들러가_사용자_ID를_요청으로_받지_않는다`).
- **남의 것과 없는 것을 구분하지 않는다.** 남의 알림·기기 ID와 없는 ID는 똑같이 `404`이고 같은 `error.code`를 쓴다(스펙 §11.4).
- **금액·지표 계산은 `BigDecimal`만 쓴다.** `double`·`float`를 쓰지 않는다. 나눗셈은 `MathContext.DECIMAL64`로 한다.
- **컨트롤러는 매퍼·리포지토리를 직접 부르지 않는다**(`ArchitectureRulesTest.컨트롤러가_저장소를_직접_부르지_않는다`). `..api..` 패키지에 두는 모든 클래스가 이 규칙을 받는다.
- **알림의 순수 패키지(`alert.catalog` · `alert.spec` · `alert.compile` · `alert.indicator` · `alert.evaluation` · `alert.sentence`)는 Spring · MyBatis · Jakarta에 의존하지 않는다.** Task 14가 ArchUnit으로 강제한다.
- **마이그레이션 번호는 `db/migration`과 `db/external`을 통틀어 하나의 순열이다.** 지금 V1(migration) · V2 · V3(external)이 있다. 이 계획은 V4(migration) · V5(external)를 만든다.
- **데이터팀 소유 테이블은 `db/external`의 미러로만 만든다.** 운영 프로필은 `db/migration`만 적용한다(`application.yaml`). 물리 이름이 미결(데이터 요구사항 N1)이므로 테이블 이름은 `alert.data`의 매퍼에만 쓴다.
- **비율 성격 컬럼을 스키마에 만들지 않는다**(`MigrationLintTest`). 금지어: `_pct` · `_ratio` · `_rate_of_return` · `weight` · `yield` · `_percent`.
- **자격증명을 코드·로그·저장소에 두지 않는다.** 푸시 토큰을 로그에 원문으로 남기지 않는다(스펙 §9.7).
- **주석과 문서는 최신 사실만 쓴다.** "예전에는", "~로 바꿨다" 같은 히스토리 문구를 쓰지 않고, 검증하지 않은 것을 단정하지 않는다.
- **테스트는 `portfolio_test` DB에서 돈다**(`src/test/resources/application-test.yaml`). 로컬 DB는 `docker compose up -d db`로 띄운다. 기동은 사람이 한다 — 실행자가 DB를 직접 띄우지 않는다.
- **커밋 메시지는 한국어, 접두는 기존 관례(`feat:` · `fix:` · `test:` · `docs:`)를 따른다.** 끝에 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`를 붙인다.

## Review Focus

스펙이 직접 말하지 않지만 사람이 실제로 부딪힐 입력 다섯 가지. 각 줄의 테스트는 해당 태스크에 들어 있다.

1. **데이터가 아직 없는 종목에 미리보기를 부른다**(신규 상장, 완료 신호 없음, 캘린더 비어 있음) → `500`이 아니라 `current.conditions[].result = UNKNOWN`과 사유(`INSUFFICIENT_HISTORY` · `DATA_MISSING`)가 온다. — Task 10
2. **형이 틀린 요청 본문**(`"n": "abc"`, `"conditions": {}`, 모르는 `type`, 조립형에 `lag`) → `400 INVALID_ALERT`와 정확한 `fields[].path`가 오고, 미리보기는 `200`에 `valid: false`가 온다. — Task 3 · Task 10
3. **다른 사용자의 알림 ID**로 조회·수정·삭제·끄기·다시 켜기·미리보기(`alert_id`) → 전부 없는 ID와 같은 `404 ALERT_NOT_FOUND`. 미리보기는 중복 검사에서 남의 알림을 세지 않는다. — Task 11 · Task 12
4. **검색어에 `%`·`_`·공백만·40자를 넘는 문자열** → 와일드카드로 해석되지 않고, 빈 검색어는 빈 목록(보유 구역 요청이 아니면), 결과 순서는 DB 정렬 설정과 무관하게 같다. — Task 13
5. **이미 다른 사용자에게 등록된 푸시 토큰을 다시 등록**한다(같은 기기에서 계정을 바꿈) → 새 행을 만들거나 `500`이 나지 않고 그 행이 지금 사용자로 옮겨진다. — Task 13

---

# 부록 A — 구현이 정하는 것

스펙이 정하지 않았거나 구현 수준까지 내려가지 않은 것을 여기서 정한다. 태스크는 이 부록을 근거로 인용한다.

## A.1 도달점과 범위

| 들어간다 | 들어가지 않는다 (계획 ②·③ 또는 그 밖) |
|---|---|
| 알림 테이블(`alert` · `alert_state` · `alert_event` · `push_device` · `alert_watchlist`) | `alert_delivery` · `snapshot_run` — ②가 만든다 |
| 데이터 테이블 미러 5개와 `instrument` 미러 컬럼 보강 | 데이터팀의 실제 테이블 · 운영 클러스터의 미러 |
| 카탈로그 · 트리거 해석 · 검증 · 컴파일 · 지표 계산 · 3값 조건 평가 · 문장 생성 | 엣지 판정 · 발화 · 따라잡기 · 만료 전이 — ② |
| `POST /alerts/preview` · 알림 CRUD · `pause` · `resume` · `GET /alerts` · `GET /alerts/{id}` | `GET /alert-events*` · 배지 수 · `MARKET_DATA_DELAYED` notice — ② |
| `GET /alerts/catalog` · `GET /instruments` · `POST/DELETE /devices` | Expo Push 발송 · 영수증 — ② |
| 로컬 CORS · 데이터팀 읽기 역할의 `push_device` 제외 | 종목 상세 화면 · `GET /portfolio/instruments/{id}` |

`GET /alerts`의 `unread` · `last_fired_at`과 `GET /alerts/{id}`의 `recent_events`는 `alert_event`를 읽는다. ① 안에서는 그 테이블이 비어 있어 빈 값이 나오고, ②가 행을 채우면 그대로 나온다.

## A.2 패키지

앱의 루트 패키지는 `com.stockproject.portfolio`다(서비스 이름 `portfolio-api`). 알림은 그 아래 `alert`에 모은다.

| 패키지 | 책임 | 프레임워크 |
|---|---|---|
| `alert.catalog` | 지표·변형·연산자·프리셋 상수 (§5) | 없음 |
| `alert.spec` | 트리거 모델 — 조건·피연산자·변형·유지 조건 (§4.2 · §4.3) | 없음 |
| `alert.compile` | 프리셋 전개, `lag` 결정, 필요 봉 수, `spec_hash` (§4.2 · §5.3 · §5.4 · §6.6) | 없음 |
| `alert.indicator` | 봉 계열과 지표 값 (§5.1) | 없음 |
| `alert.evaluation` | 한 데이터 시점의 3값 조건 평가와 확인 불가 사유 (§6.1 · §7) | 없음 |
| `alert.sentence` | 조건 문장 · 관측값 줄 · 머리 · 결과 줄 · 숫자 표기 (§12.1 · §12.6) | 없음 |
| `alert.validation` | JSON 해석과 검증 — 경로가 붙은 오류 (§14) | Jackson만 |
| `alert.data` | 미러·포트폴리오 테이블 읽기, 평가 입력 조립 | MyBatis · Spring |
| `alert.store` | 알림·상태·기기·대상 종목 읽기·쓰기 | MyBatis · Spring |
| `alert.service` | 미리보기·명령·조회·카탈로그·검색·기기 | Spring |
| `alert.api` | 컨트롤러와 DTO | Spring |

순수 패키지를 따로 두는 이유는 ②의 평가기가 같은 계산을 써야 하기 때문이다. 미리보기와 평가가 다른 코드로 계산하면 "미리보기에서는 ✓인데 울리지 않는" 일이 생긴다.

## A.3 시각

- `Clock` 빈을 하나 둔다(`Asia/Seoul`). "지금"이 필요한 코드는 전부 이 빈을 주입받는다. 테스트는 `@MockitoBean`이 아니라 `@TestConfiguration`의 고정 `Clock`으로 바꾼다.
- 시장 시간대: KR `Asia/Seoul`, US `America/New_York`. 거래일은 그 시장의 현지 날짜다(데이터 요구사항 §2.4).

## A.4 JSON 저장

`alert.trigger_spec` · `alert_event.lines` · `alert_event.observed`는 `jsonb`다. 타입 핸들러를 두지 않고 SQL에서 바꾼다 — 쓸 때 `CAST(#{json} AS jsonb)`, 읽을 때 `trigger_spec::text`. 서비스는 문자열과 `JsonNode`를 오간다. 핸들러 하나를 위해 `type-handlers-package` 구성을 넓히지 않기 위해서다.

## A.5 미리보기의 데이터 시점

스펙 §12.5.4 · §12.8을 구현 수준으로 내린다.

| 알림 | 기준 | 머리 |
|---|---|---|
| `CLOSE` | 그 알림이 기다리는 데이터 종류(§5.4)가 모두 `DONE`인 가장 최근 거래일 | `9/26 종가 기준` · `미국 9/26 종가 기준` |
| `INTRADAY`, 그 종목의 장중 스냅샷이 허용 지연 안에 있음 | 그 시장의 가장 최근 `INTRADAY_QUOTE` `DONE` | `지금 · 10:15 기준` · `미국 장중 · 02:15 기준` |
| `INTRADAY`, 스냅샷 없음 또는 허용 지연 초과 | 가장 최근 `DAILY_BAR` `DONE` 거래일의 종가 | `9/26 종가 기준` |
| 사용자 상태 지표 | 그 사용자의 가장 최근 `is_final = true` 보유 스냅샷 `as_of` | `9/26 종가 기준` |

- **일봉 기준으로 장중 알림을 미리볼 때 `persist_min`은 비교만 평가한다.** 지속 시간은 당일 스냅샷이 있어야 정해지는데 그 기준에는 스냅샷이 없다. 관측값 줄에 지속을 쓰지 않는다. 저장한 뒤 장중 평가가 지속을 판정한다.
- **완료 신호가 하나도 없으면** 그 조건은 `UNKNOWN(DATA_MISSING)`이고 머리는 `데이터 없음`이다.
- 미리보기의 `as_of`는 위 기준 시점이다(종가는 `close_at`, 장중은 `snapshot_at`).

## A.6 데이터 누락일과 거래정지일 (스펙 §7.2)

| 날 | 판정 | 계열 |
|---|---|---|
| 거래정지일 | 그 시장의 그날 `DAILY_BAR`가 `DONE`인데 그 종목 봉이 없음 | 빠진다. 연속을 끊지도 잇지도 않는다 |
| 데이터 누락일 | 캘린더상 거래일인데 그 시장의 그날 `DAILY_BAR` `DONE`이 없음 | 빠진다. 단 연속·교차 구간에 있으면 `UNKNOWN(DATA_MISSING)` |
| 현재 봉 없음 | 평가 거래일에 그 종목 봉이 없음 | `UNKNOWN(NO_TRADE)` |

캘린더(`dim_market_calendar`)에 그 구간의 행이 없으면 월~금을 거래일로 본다(데이터 요구사항 §4.2 "평일 근사").

연속·교차 구간은 현재 봉부터 `streak − 1`개의 앞 봉까지(교차는 직전 1봉까지)의 날짜 범위다. 그 범위 안에 데이터 누락일이 하나라도 있으면 `UNKNOWN(DATA_MISSING)`이다.

## A.7 수정주가 미반영 의심 (스펙 §7.3)

국내 종목에서, 그 조건이 읽는 봉 범위 안의 어떤 봉 `j`(계열의 첫 봉 제외)가 `|close[j] / close[j−1] − 1| > 0.30`이면 `UNKNOWN(PRICE_ADJUSTMENT_SUSPECTED)`다. 계열의 첫 봉을 빼는 것은 신규 상장 첫날의 제한폭이 달라서다. 미국 종목에는 판정을 두지 않는다.

## A.8 오류 응답

- **검증 실패**: `400`과 `{ "error": { "code": "INVALID_ALERT", "message": "조건을 확인해 주세요", "fields": [ { "path", "code", "message" } ] } }`. 기존 `ApiError`는 `fields`가 없으므로 따로 `InvalidAlertError` record를 둔다. 기존 오류 응답에 `"fields": null`이 생기지 않게 하기 위해서다(`default-property-inclusion: always`).
- **없음**: 기존 `RequestRejected(code, message, notFound = true)`를 쓴다 — `ALERT_NOT_FOUND` · `DEVICE_NOT_FOUND`.
- **상태 전환 불가**: `400 INVALID_STATUS_TRANSITION`(예: 꺼진 알림을 다시 끄기).

검증 오류 코드:

| code | 뜻 |
|---|---|
| `REQUIRED` | 필수 값 없음 |
| `INVALID_TYPE` | 형이 틀림(숫자 자리에 문자열 등) |
| `INVALID_VALUE` | 열거형 밖의 값 |
| `OUT_OF_RANGE` | 범위 밖 |
| `UNKNOWN_INSTRUMENT` | 종목 마스터에 없음·예수금·상장폐지 |
| `MARKET_NOT_SUPPORTED` | 종목 시장에서 쓸 수 없는 지표·프리셋 |
| `CADENCE_NOT_ALLOWED` | 평가 시점에서 쓸 수 없는 지표·변형·유지 조건·발화 방식 |
| `TRANSFORM_NOT_ALLOWED` | 지표가 허용하지 않는 변형 |
| `OPERATOR_NOT_ALLOWED` | 지표가 허용하지 않는 연산자 |
| `UNIT_MISMATCH` | 두 피연산자의 단위가 다름 |
| `MODIFIER_NOT_ALLOWED` | 교차·사용자 상태 지표에 유지 조건, 평가 시점과 맞지 않는 유지 조건 |
| `SCOPE_MIXED` | 사용자 상태 지표와 시장 지표를 한 알림에 섞음 |
| `NOT_HELD` | 생성 시 보유하지 않은 종목에 사용자 상태 조건 |
| `LAG_NOT_ALLOWED` | 조립형 요청에 `lag` |
| `IMMUTABLE` | 수정에서 종목·트리거 종류를 바꿈 |
| `PAST` | 과거 시각의 유효기간 |

## A.9 숫자 계산

- 지표 값은 `BigDecimal`이고 나눗셈은 `MathContext.DECIMAL64`.
- 비교는 계산값 그대로 한다. 반올림은 문장에 쓸 때만 한다(§12.6).
- RSI는 Wilder 평활: 계산 창의 첫 `n`개 변화로 평균 상승·하락을 시작하고, 이후 `avg = (avg × (n−1) + 이번 값) / n`. 평균 하락이 0이면 100.

## A.10 정렬 기준의 결정성

- 종목 검색과 보유 구역의 가나다순은 `ORDER BY name COLLATE "C"`로 한다. DB 기본 정렬 설정과 무관하게 Latin이 한글보다 앞서고 한글은 가나다 순이 된다(§12.5.1).
- 알림 목록은 상태 순 → 최근 울린 순(`fired_at` 내림차순, 없으면 뒤) → 만든 순(내림차순) → `alert_id`.

## A.11 실행자가 하지 않는 것

- DB·서버를 띄우지 않는다. 테스트가 DB를 요구하면 사람에게 `docker compose up -d db`를 요청하고 기다린다.
- 운영 클러스터·k8s에 적용하지 않는다. 매니페스트 파일만 고친다(Task 1).
- 스펙·데이터 요구사항·회의 문서를 고치지 않는다.

---

# 태스크

## 파일 구조

```
src/main/java/com/stockproject/portfolio/
  support/ClockConfig.java                                                           Task 1
  alert/
    catalog/   Cadence · NotifyMode · AlertStatus · Unit · DataKind · Scope · OperatorKey ·
               TransformType · WindowFn · ParamSpec · TransformRule · IndicatorKey · Indicator ·
               PresetKey · PresetParam · Preset · AlertCatalog                       Task 2
    spec/      Operand · Transform · Right · Modifier · Condition · TriggerSpec · AlertDraft  Task 3
    validation/FieldError · ParseResult · AlertRequestParser                          Task 3
               AlertValidator · InstrumentFacts · ExistingAlert · InvalidAlertException Task 5
               TriggerSpecWriter                                                     Task 11
    compile/   CompiledTrigger · Compiler · RequiredBars · SpecHash                  Task 4
               DataNeeds                                                             Task 7
    indicator/ Bar · FlowBar · Snapshot · Holding · Series · IndicatorCalculator     Task 6
    evaluation/Truth · UnknownReason · Basis · EvaluationInput · ConditionResult ·
               EvaluationResult · ConditionEvaluator                                 Task 7
    sentence/  Josa · Numbers · OperandNames · Summary · Line · SentenceWriter       Task 8
    data/      InstrumentRow · CalendarDay · MarketDataMapper · HoldingMapper ·
               MarketDataRepository · HoldingReader · EvaluationInputFactory         Task 9
    store/     AlertRow · AlertMapper · AlertStore                                   Task 10 · 11
               WatchlistMapper                                                       Task 11
               AlertQueryMapper · AlertListRow · UnreadEventRow · RecentEventRow     Task 12
               InstrumentSearchMapper · InstrumentSearchRow · PushDeviceMapper       Task 13
    service/   AlertTimes · AlertPreviewService                                      Task 10
               AlertCommandService                                                   Task 11
               AlertQueryService                                                     Task 12
               AlertCatalogService · InstrumentSearchService · DeviceService         Task 13
    api/       AlertController · AlertExceptionHandler · dto/*                       Task 10 ~ 12
               AlertCatalogController · InstrumentController · DeviceController      Task 13
  auth/LocalCorsConfig.java                                                          Task 14
src/main/resources/
  db/migration/V4__alert_tables.sql                                                  Task 1
  db/external/V5__alert_market_data_mirror.sql                                       Task 1
  db/sample/sample_alert_market.sql                                                  Task 9
src/test/java/com/stockproject/portfolio/
  alert/AlertSchemaTest · AlertApiClient · FixedClockConfig                          Task 1 · 10
  alert/<패키지별 단위 테스트> · alert/api/*ApiTest                                     Task 2 ~ 14
k8s/dataeng-reader-job.yaml                                                          Task 1
docs/decisions.md                                                                    Task 14
```

매퍼는 모두 어노테이션(`@Select` 등)으로 쓴다. 쿼리가 짧고 동적 SQL이 없어서다 — 기존 `SnapshotCalendarMapper`와 같은 방식이다.

---

## Task 1: 기반 — 시각, 알림 테이블, 데이터 미러, 계약 테스트

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/support/ClockConfig.java`
- Create: `src/main/resources/db/migration/V4__alert_tables.sql`
- Create: `src/main/resources/db/external/V5__alert_market_data_mirror.sql`
- Modify: `src/test/java/com/stockproject/portfolio/query/SchemaContractTest.java`
- Create: `src/test/java/com/stockproject/portfolio/alert/AlertSchemaTest.java`
- Modify: `k8s/dataeng-reader-job.yaml`

**Interfaces:**
- Produces: `Clock` 빈(`Asia/Seoul`). 테이블 `alert` · `alert_state` · `alert_event` · `push_device` · `alert_watchlist`(public). 미러 `dim_market_calendar` · `adjusted_price_daily` · `investor_flow_daily` · `intraday_quote` · `market_data_run`, `instrument.sector_source` · `instrument.delisted_on`.

- [ ] **Step 1: 실패하는 스키마 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/AlertSchemaTest.java`:

```java
package com.stockproject.portfolio.alert;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** 알림 테이블과 데이터 미러의 컬럼 계약. 스펙 §10.1 · 데이터 요구사항 §4 · §5. */
@SpringBootTest
@ActiveProfiles("test")
class AlertSchemaTest {

    @Autowired JdbcClient jdbc;

    @Test
    void 알림_테이블의_컬럼이_스펙과_같다() {
        assertThat(columnsOf("alert")).containsExactly(
                "alert_id", "cadence", "cooldown_min", "created_at", "deleted_at", "expires_at",
                "instrument_id", "name", "notify_mode", "spec_version", "status",
                "trigger_spec", "trigger_type", "updated_at", "user_id");
        assertThat(columnsOf("alert_state")).containsExactly(
                "alert_id", "evaluated_as_of", "last_known_result", "last_result",
                "spec_hash", "unknown_reason", "version");
        assertThat(columnsOf("alert_event")).containsExactly(
                "alert_id", "as_of", "body", "event_id", "fired_at", "lines", "observed",
                "read_at", "title");
        assertThat(columnsOf("push_device")).containsExactly(
                "created_at", "device_id", "expo_push_token", "last_seen_at", "platform", "user_id");
        assertThat(columnsOf("alert_watchlist")).containsExactly("instrument", "intraday", "market")
                .isNotNull();
    }

    @Test
    void 데이터_미러의_컬럼이_데이터_요구사항과_같다() {
        assertThat(columnsOf("dim_market_calendar")).containsExactly(
                "close_at", "date", "is_trading_day", "market", "next_trading_day",
                "open_at", "prev_trading_day");
        assertThat(columnsOf("adjusted_price_daily")).containsExactly(
                "adj_factor", "close", "date", "high", "instrument_id", "low", "open", "volume");
        assertThat(columnsOf("investor_flow_daily")).containsExactly(
                "date", "foreign_net_buy_krw", "institution_net_buy_krw", "instrument_id");
        assertThat(columnsOf("intraday_quote")).containsExactly(
                "cum_volume", "instrument_id", "price", "snapshot_at");
        assertThat(columnsOf("market_data_run")).containsExactly(
                "as_of", "finished_at", "kind", "market", "state");
    }

    @Test
    void 쿨다운은_장중_알림에만_있다() {
        assertThatThrownBy(() -> jdbc.sql("""
                INSERT INTO alert (alert_id, user_id, instrument_id, name, cadence, notify_mode,
                    cooldown_min, status, trigger_type, trigger_spec, spec_version, created_at, updated_at)
                VALUES (gen_random_uuid(), '40000000-0000-0000-0000-000000000001', gen_random_uuid(),
                    '테스트', 'CLOSE', 'COOLDOWN', 30, 'ACTIVE', 'COMPOSABLE', '{}'::jsonb, 1, now(), now())
                """).update()).hasMessageContaining("alert_cooldown_intraday_only");
    }

    @Test
    void 한_알림은_한_데이터_시점에_한_번만_울린다() {
        List<String> unique = jdbc.sql("""
                SELECT pg_get_constraintdef(oid) FROM pg_constraint
                 WHERE conrelid = 'alert_event'::regclass AND contype = 'u'
                """).query(String.class).list();
        assertThat(unique).containsExactly("UNIQUE (alert_id, as_of)");
    }

    private List<String> columnsOf(String table) {
        return jdbc.sql("""
                SELECT column_name FROM information_schema.columns
                 WHERE table_schema = 'public' AND table_name = :t ORDER BY column_name
                """).param("t", table).query(String.class).list();
    }
}
```

`alert_watchlist`의 기대값은 일부러 틀리게 두었다(`instrument`) — 다음 단계에서 실패를 본 뒤 Step 4에서 바로잡는다.

- [ ] **Step 2: 실패를 확인한다**

DB가 떠 있지 않으면 사람에게 `docker compose up -d db`를 요청하고 기다린다.

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.AlertSchemaTest'`
Expected: FAIL — 테이블이 없어 `columnsOf("alert")`가 빈 목록을 돌려준다.

- [ ] **Step 3: 시각 빈과 마이그레이션을 쓴다**

`src/main/java/com/stockproject/portfolio/support/ClockConfig.java`:

```java
package com.stockproject.portfolio.support;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;
import java.time.ZoneId;

/**
 * "지금"의 출처. 유효기간·허용 지연·기기 마지막 확인 시각이 모두 이 시계를 본다.
 * 테스트는 고정 시계로 바꿔 날짜에 따라 결과가 달라지지 않게 한다.
 */
@Configuration
public class ClockConfig {

    @Bean
    Clock clock(@Value("${portfolio.zone}") String zone) {
        return Clock.system(ZoneId.of(zone));
    }
}
```

`src/main/resources/db/migration/V4__alert_tables.sql`:

```sql
-- 매수·매도 타이밍 알림의 백엔드 소유 테이블.
-- 소유권 축은 alert.user_id 하나다. 알림은 보유하지 않은 종목에도 걸려 계좌를 거칠 수 없다.
-- 상태·발화 행은 alert_id를 거쳐 소유자가 정해진다.

CREATE TABLE alert (
    alert_id      uuid        PRIMARY KEY,
    user_id       uuid        NOT NULL REFERENCES app_user (id),
    instrument_id uuid        NOT NULL,
    name          text        NOT NULL,
    cadence       text        NOT NULL,
    notify_mode   text        NOT NULL,
    cooldown_min  integer,
    expires_at    timestamptz,
    status        text        NOT NULL,
    trigger_type  text        NOT NULL,
    trigger_spec  jsonb       NOT NULL,
    spec_version  integer     NOT NULL,
    created_at    timestamptz NOT NULL,
    updated_at    timestamptz NOT NULL,
    deleted_at    timestamptz,
    CONSTRAINT alert_name_length     CHECK (char_length(btrim(name)) BETWEEN 1 AND 40),
    CONSTRAINT alert_cadence         CHECK (cadence IN ('INTRADAY', 'CLOSE')),
    CONSTRAINT alert_notify_mode     CHECK (notify_mode IN ('EDGE_REARM', 'ONE_SHOT', 'COOLDOWN')),
    CONSTRAINT alert_status          CHECK (status IN ('ACTIVE', 'PAUSED', 'ENDED', 'EXPIRED')),
    CONSTRAINT alert_trigger_type    CHECK (trigger_type IN ('COMPOSABLE', 'PRESET')),
    CONSTRAINT alert_cooldown_pair   CHECK ((notify_mode = 'COOLDOWN') = (cooldown_min IS NOT NULL)),
    CONSTRAINT alert_cooldown_range  CHECK (cooldown_min IS NULL OR cooldown_min BETWEEN 5 AND 1440),
    CONSTRAINT alert_cooldown_intraday_only CHECK (notify_mode <> 'COOLDOWN' OR cadence = 'INTRADAY')
);

CREATE INDEX idx_alert_user ON alert (user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_alert_active_instrument ON alert (instrument_id, cadence)
    WHERE status = 'ACTIVE' AND deleted_at IS NULL;

COMMENT ON COLUMN alert.instrument_id IS
  '데이터팀 소유 instrument 참조. 팀 간 배포 순서를 묶지 않으려고 FK를 걸지 않는다';
COMMENT ON COLUMN alert.trigger_spec IS
  '조립형은 lag 없이 저장한다. lag는 평가와 미리보기에서 컴파일할 때만 정해진다';
COMMENT ON COLUMN alert.deleted_at IS
  '소프트 삭제. 삭제된 알림은 평가·목록·중복 검사에서 빠지고, 발화 기록은 남는다';

CREATE TABLE alert_state (
    alert_id          uuid        PRIMARY KEY REFERENCES alert (alert_id),
    last_result       text,
    last_known_result text        NOT NULL,
    unknown_reason    text,
    evaluated_as_of   timestamptz,
    spec_hash         text        NOT NULL,
    version           integer     NOT NULL DEFAULT 0,
    CONSTRAINT alert_state_last_result  CHECK (last_result IS NULL OR last_result IN ('TRUE', 'FALSE', 'UNKNOWN')),
    CONSTRAINT alert_state_known_result CHECK (last_known_result IN ('TRUE', 'FALSE')),
    CONSTRAINT alert_state_reason       CHECK (unknown_reason IS NULL OR unknown_reason IN
        ('DATA_MISSING', 'INSUFFICIENT_HISTORY', 'NO_TRADE', 'PRICE_ADJUSTMENT_SUSPECTED',
         'NOT_HELD', 'INSTRUMENT_UNKNOWN'))
);

COMMENT ON COLUMN alert_state.version IS
  '사용자 변경과 만료 전이마다 1씩 오른다. 평가 결과는 읽을 때의 version과 같을 때만 반영된다';
COMMENT ON COLUMN alert_state.evaluated_as_of IS
  '마지막으로 평가한 데이터 시점. 생성·다시 켜기·수정 시 비운다. 비어 있으면 최신 DONE 시점 하나만 평가한다';

CREATE TABLE alert_event (
    event_id uuid        PRIMARY KEY,
    alert_id uuid        NOT NULL REFERENCES alert (alert_id),
    as_of    timestamptz NOT NULL,
    fired_at timestamptz NOT NULL,
    title    text        NOT NULL,
    body     text        NOT NULL,
    lines    jsonb       NOT NULL,
    observed jsonb       NOT NULL,
    read_at  timestamptz,
    CONSTRAINT alert_event_once_per_point UNIQUE (alert_id, as_of)
);

CREATE INDEX idx_alert_event_alert_fired ON alert_event (alert_id, fired_at DESC);
CREATE INDEX idx_alert_event_unread ON alert_event (alert_id) WHERE read_at IS NULL;

COMMENT ON COLUMN alert_event.lines IS
  '조건별 관측값 문장 배열. 울린 알림 상세의 울린 이유 상자가 줄마다 그린다';

CREATE TABLE push_device (
    device_id       uuid        PRIMARY KEY,
    user_id         uuid        NOT NULL REFERENCES app_user (id),
    expo_push_token text        NOT NULL UNIQUE,
    platform        text        NOT NULL,
    created_at      timestamptz NOT NULL,
    last_seen_at    timestamptz NOT NULL,
    CONSTRAINT push_device_platform CHECK (platform IN ('IOS', 'ANDROID'))
);

CREATE INDEX idx_push_device_user ON push_device (user_id);

COMMENT ON COLUMN push_device.user_id IS
  '지금 이 기기로 로그인한 사용자. 같은 토큰을 다른 사용자가 등록하면 그 사용자로 옮긴다';

CREATE TABLE alert_watchlist (
    instrument_id uuid    PRIMARY KEY,
    market        text    NOT NULL,
    intraday      boolean NOT NULL,
    CONSTRAINT alert_watchlist_market CHECK (market IN ('KR', 'US'))
);

COMMENT ON TABLE alert_watchlist IS
  '삭제되지 않은 ACTIVE 알림이 걸린 종목. 데이터는 intraday = true인 종목의 장중 스냅샷을 만든다. 사용자 정보를 담지 않는다';
```

`src/main/resources/db/external/V5__alert_market_data_mirror.sql`:

```sql
-- 데이터팀 소유 테이블의 로컬·테스트 전용 미러. 운영 프로필은 이 파일을 적용하지 않는다.
-- 컬럼과 타입은 데이터 요구사항 문서(docs/yhr/specs/data-requirements.md) §4 · §5를 따른다.
-- 물리 이름은 미결이다(N1). 바뀌면 이 파일과 매퍼 XML만 고친다.

ALTER TABLE instrument ADD COLUMN IF NOT EXISTS sector_source text;
ALTER TABLE instrument ADD COLUMN IF NOT EXISTS delisted_on  date;

CREATE TABLE IF NOT EXISTS dim_market_calendar (
    market           text        NOT NULL CHECK (market IN ('KR', 'US')),
    date             date        NOT NULL,
    is_trading_day   boolean     NOT NULL,
    prev_trading_day date        NOT NULL,
    next_trading_day date        NOT NULL,
    open_at          timestamptz,
    close_at         timestamptz,
    PRIMARY KEY (market, date)
);

CREATE TABLE IF NOT EXISTS adjusted_price_daily (
    instrument_id uuid           NOT NULL,
    date          date           NOT NULL,
    open          numeric(20, 4) NOT NULL,
    high          numeric(20, 4) NOT NULL,
    low           numeric(20, 4) NOT NULL,
    close         numeric(20, 4) NOT NULL,
    volume        numeric(20, 4) NOT NULL,
    adj_factor    numeric(18, 8) NOT NULL,
    PRIMARY KEY (instrument_id, date)
);

CREATE TABLE IF NOT EXISTS investor_flow_daily (
    instrument_id           uuid           NOT NULL,
    date                    date           NOT NULL,
    foreign_net_buy_krw     numeric(20, 0) NOT NULL,
    institution_net_buy_krw numeric(20, 0) NOT NULL,
    PRIMARY KEY (instrument_id, date)
);

CREATE TABLE IF NOT EXISTS intraday_quote (
    instrument_id uuid           NOT NULL,
    snapshot_at   timestamptz    NOT NULL,
    price         numeric(20, 4) NOT NULL,
    cum_volume    numeric(20, 0) NOT NULL,
    PRIMARY KEY (instrument_id, snapshot_at)
);

CREATE INDEX IF NOT EXISTS idx_intraday_quote_snapshot ON intraday_quote (snapshot_at);

CREATE TABLE IF NOT EXISTS market_data_run (
    market      text        NOT NULL CHECK (market IN ('KR', 'US')),
    kind        text        NOT NULL CHECK (kind IN ('INTRADAY_QUOTE', 'DAILY_BAR', 'DAILY_FLOW')),
    as_of       timestamptz NOT NULL,
    state       text        NOT NULL CHECK (state IN ('RUNNING', 'DONE', 'FAILED')),
    finished_at timestamptz,
    PRIMARY KEY (market, kind, as_of)
);
```

- [ ] **Step 4: 테스트의 일부러 틀린 기대값을 바로잡는다**

`AlertSchemaTest.알림_테이블의_컬럼이_스펙과_같다`의 마지막 단언을 다음으로 바꾼다.

```java
        assertThat(columnsOf("alert_watchlist")).containsExactly("instrument_id", "intraday", "market");
```

- [ ] **Step 5: 기존 계약 테스트를 알림 테이블에 맞춘다**

`src/test/java/com/stockproject/portfolio/query/SchemaContractTest.java`에서 두 테스트를 바꾼다.

```java
    /** 데이터팀 소유 instrument의 컬럼 계약. 축과 종목 검색이 전부 이 테이블에서 온다. */
    @Test
    void instrument_컬럼_계약이_유지된다() {
        assertThat(columnsOf("instrument")).containsExactly(
                "asset_class", "currency", "delisted_on", "instrument_id", "is_leveraged",
                "isin", "market", "name", "sector", "sector_source", "symbol");
    }
```

```java
    /**
     * 소유 표시는 테이블마다 하나다. 포트폴리오의 소유권 축은 계좌이고, 알림과 푸시 기기는
     * 계좌를 거치지 않고 사용자에게 직접 속한다 — 알림은 보유하지 않은 종목에도 걸리고,
     * 기기는 계좌와 무관하다. 그 밖의 테이블에 user_id를 복사하지 않는다.
     */
    @Test
    void 사용자_컬럼은_계좌_알림_기기에만_있다() {
        assertThat(jdbc.sql("""
                SELECT table_name FROM information_schema.columns
                 WHERE table_schema = 'public' AND column_name = 'user_id'
                 ORDER BY table_name
                """).query(String.class).list()).containsExactly("account", "alert", "push_device");
    }
```

기존 `소유권_축이_account에만_있다()` 메서드는 지운다(위 메서드가 대신한다).

- [ ] **Step 6: 데이터팀 읽기 역할에서 푸시 기기를 뺀다**

`k8s/dataeng-reader-job.yaml`의 `grant.sql` 끝에 붙인다.

```sql
    -- 푸시 토큰은 기기에 알림을 보낼 수 있는 자격이다. 분석에 쓸 데가 없다.
    REVOKE ALL ON push_device FROM dataeng_reader;
```

- [ ] **Step 7: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.AlertSchemaTest' --tests 'com.stockproject.portfolio.query.SchemaContractTest' --tests 'com.stockproject.portfolio.MigrationLintTest'`
Expected: PASS (3개 클래스 전부)

- [ ] **Step 8: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/support/ClockConfig.java \
        src/main/resources/db/migration/V4__alert_tables.sql \
        src/main/resources/db/external/V5__alert_market_data_mirror.sql \
        src/test/java/com/stockproject/portfolio/alert/AlertSchemaTest.java \
        src/test/java/com/stockproject/portfolio/query/SchemaContractTest.java \
        k8s/dataeng-reader-job.yaml
git commit -m "feat: 알림 테이블과 데이터 미러를 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 카탈로그 — 지표·변형·연산자·프리셋

스펙 §5.1 · §5.2 · §5.3 · §12.5.3의 표를 코드 상수로 옮긴다.

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/catalog/` 아래 `Cadence.java` · `NotifyMode.java` · `AlertStatus.java` · `Unit.java` · `DataKind.java` · `Scope.java` · `OperatorKey.java` · `TransformType.java` · `WindowFn.java` · `ParamSpec.java` · `TransformRule.java` · `IndicatorKey.java` · `Indicator.java` · `PresetKey.java` · `PresetParam.java` · `Preset.java` · `AlertCatalog.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/catalog/AlertCatalogTest.java`

**Interfaces:**
- Consumes: `com.stockproject.portfolio.domain.Market`(`KR` · `US`, 기존).
- Produces:
  - `enum Cadence { INTRADAY, CLOSE }` · `enum NotifyMode { EDGE_REARM, ONE_SHOT, COOLDOWN }` · `enum AlertStatus { ACTIVE, PAUSED, ENDED, EXPIRED }`
  - `enum Unit { PRICE, KRW, PERCENT, SHARES, RATIO, INDEX }` — `key()`는 소문자
  - `enum DataKind { INTRADAY_QUOTE, DAILY_BAR, DAILY_FLOW, PORTFOLIO_SNAPSHOT }` · `enum Scope { MARKET, USER }`
  - `enum OperatorKey { GTE, LTE, GT, LT, CROSSES_ABOVE, CROSSES_BELOW }` — `key()`(`gte`…), `isCross()`, `symbol()`(`≥`…), `word()`(`이상`…)
  - `enum TransformType { IDENTITY, WINDOW, DELTA, PCT }` · `enum WindowFn { MAX, MIN, AVG, SUM }` — 둘 다 `key()` 소문자, `of(String)`은 없으면 `null`
  - `record ParamSpec(String key, int defaultValue, int min, int max)`
  - `record TransformRule(TransformType type, int nMin, int nMax)`
  - `enum IndicatorKey` 14값 — `key()`, `of(String)`(없으면 `null`)
  - `record Indicator(IndicatorKey key, String label, String category, Unit unit, List<ParamSpec> params, boolean intradayLeft, Set<Market> markets, List<TransformRule> transforms, Set<OperatorKey> operators, Scope scope, Set<DataKind> requires)` — `TransformRule rule(TransformType)`(없으면 `null`), `int paramOrDefault(Map<String,Integer>, String)`
  - `enum PresetKey` 9값 — `key()`, `of(String)`
  - `record PresetParam(String key, Kind kind, BigDecimal min, BigDecimal max, BigDecimal defaultNumber, List<String> choices, String defaultChoice, boolean required)` + `enum Kind { INT, DECIMAL, CHOICE }`
  - `record Preset(PresetKey key, String label, Set<Cadence> cadences, Set<Market> markets, Scope scope, List<PresetParam> params)`
  - `final class AlertCatalog` — `indicators()`, `indicator(IndicatorKey)`, `presets()`, `preset(PresetKey)`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/catalog/AlertCatalogTest.java`:

```java
package com.stockproject.portfolio.alert.catalog;

import com.stockproject.portfolio.domain.Market;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/** 스펙 §5.1 · §5.3의 표가 코드 상수와 같은지. */
class AlertCatalogTest {

    @Test
    void 지표는_열네_개다() {
        assertThat(AlertCatalog.indicators()).hasSize(14);
        assertThat(AlertCatalog.indicators()).extracting(i -> i.key().key()).containsExactly(
                "price", "change_pct", "volume", "volume_ratio", "high", "low", "range_pct",
                "sma", "rsi", "disparity", "foreign_net_buy", "institution_net_buy",
                "unrealized_pnl_pct", "weight_pct");
    }

    @Test
    void 장중_왼쪽에_올_수_있는_지표는_네_개다() {
        assertThat(AlertCatalog.indicators()).filteredOn(Indicator::intradayLeft)
                .extracting(i -> i.key().key())
                .containsExactly("price", "change_pct", "volume", "volume_ratio");
    }

    @Test
    void 지표의_단위가_스펙_표와_같다() {
        assertThat(unit(IndicatorKey.PRICE)).isEqualTo(Unit.PRICE);
        assertThat(unit(IndicatorKey.CHANGE_PCT)).isEqualTo(Unit.PERCENT);
        assertThat(unit(IndicatorKey.VOLUME)).isEqualTo(Unit.SHARES);
        assertThat(unit(IndicatorKey.VOLUME_RATIO)).isEqualTo(Unit.RATIO);
        assertThat(unit(IndicatorKey.RANGE_PCT)).isEqualTo(Unit.PERCENT);
        assertThat(unit(IndicatorKey.SMA)).isEqualTo(Unit.PRICE);
        assertThat(unit(IndicatorKey.RSI)).isEqualTo(Unit.INDEX);
        assertThat(unit(IndicatorKey.DISPARITY)).isEqualTo(Unit.PERCENT);
        assertThat(unit(IndicatorKey.FOREIGN_NET_BUY)).isEqualTo(Unit.KRW);
        assertThat(unit(IndicatorKey.WEIGHT_PCT)).isEqualTo(Unit.PERCENT);
    }

    @Test
    void 수급은_국내만_사용자_상태는_사용자_범위다() {
        assertThat(AlertCatalog.indicator(IndicatorKey.FOREIGN_NET_BUY).markets()).containsOnly(Market.KR);
        assertThat(AlertCatalog.indicator(IndicatorKey.UNREALIZED_PNL_PCT).scope()).isEqualTo(Scope.USER);
        assertThat(AlertCatalog.indicator(IndicatorKey.UNREALIZED_PNL_PCT).requires())
                .containsOnly(DataKind.PORTFOLIO_SNAPSHOT);
    }

    /** 수급과 RSI의 변형 상한은 필요 이력이 데이터 요구를 넘지 않게 하기 위해서다(§5.1). */
    @Test
    void 변형_허용_범위가_스펙_표와_같다() {
        Indicator rsi = AlertCatalog.indicator(IndicatorKey.RSI);
        assertThat(rsi.rule(TransformType.DELTA).nMax()).isEqualTo(5);
        assertThat(rsi.rule(TransformType.WINDOW)).isNull();

        Indicator flow = AlertCatalog.indicator(IndicatorKey.FOREIGN_NET_BUY);
        assertThat(flow.rule(TransformType.WINDOW).nMax()).isEqualTo(10);
        assertThat(flow.rule(TransformType.PCT)).isNull();

        Indicator price = AlertCatalog.indicator(IndicatorKey.PRICE);
        assertThat(price.rule(TransformType.WINDOW).nMax()).isEqualTo(120);

        assertThat(AlertCatalog.indicator(IndicatorKey.WEIGHT_PCT).transforms())
                .extracting(TransformRule::type).containsExactly(TransformType.IDENTITY);
    }

    @Test
    void 사용자_상태_지표에는_교차_연산자가_없다() {
        assertThat(AlertCatalog.indicator(IndicatorKey.UNREALIZED_PNL_PCT).operators())
                .containsOnly(OperatorKey.GTE, OperatorKey.LTE, OperatorKey.GT, OperatorKey.LT);
    }

    @Test
    void 지표_파라미터의_기본값과_범위() {
        Indicator rsi = AlertCatalog.indicator(IndicatorKey.RSI);
        assertThat(rsi.params()).containsExactly(new ParamSpec("n", 14, 2, 30));
        assertThat(rsi.paramOrDefault(Map.of(), "n")).isEqualTo(14);
        assertThat(rsi.paramOrDefault(Map.of("n", 9), "n")).isEqualTo(9);
        assertThat(AlertCatalog.indicator(IndicatorKey.VOLUME_RATIO).params())
                .containsExactly(new ParamSpec("n", 20, 5, 120));
    }

    @Test
    void 프리셋은_아홉_개이고_평가_시점이_스펙_표와_같다() {
        assertThat(AlertCatalog.presets()).hasSize(9);
        assertThat(AlertCatalog.preset(PresetKey.PRICE_REACH).cadences())
                .containsOnly(Cadence.INTRADAY, Cadence.CLOSE);
        assertThat(AlertCatalog.preset(PresetKey.BOX_BREAKOUT).cadences()).containsOnly(Cadence.CLOSE);
        assertThat(AlertCatalog.preset(PresetKey.INVESTOR_TURN).markets()).containsOnly(Market.KR);
        assertThat(AlertCatalog.preset(PresetKey.PNL_REACH).scope()).isEqualTo(Scope.USER);
    }

    @Test
    void 연속_순매수_일수는_1에서_20이다() {
        PresetParam days = AlertCatalog.preset(PresetKey.INVESTOR_STREAK).params().stream()
                .filter(p -> p.key().equals("days")).findFirst().orElseThrow();
        assertThat(days.min()).isEqualByComparingTo("1");
        assertThat(days.max()).isEqualByComparingTo("20");
        assertThat(days.defaultNumber()).isEqualByComparingTo("3");
    }

    private static Unit unit(IndicatorKey key) { return AlertCatalog.indicator(key).unit(); }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.catalog.AlertCatalogTest'`
Expected: FAIL — 컴파일 오류(`AlertCatalog` 없음)

- [ ] **Step 3: 열거형을 쓴다**

`Cadence.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/** 평가 시점 (스펙 §3.1). */
public enum Cadence {
    INTRADAY, CLOSE;

    public static Cadence of(String value) {
        for (Cadence c : values()) if (c.name().equals(value)) return c;
        return null;
    }
}
```

`NotifyMode.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/** 발화 방식 (스펙 §6.2). 쿨다운은 장중 알림에만 있다. */
public enum NotifyMode {
    EDGE_REARM, ONE_SHOT, COOLDOWN;

    public static NotifyMode of(String value) {
        for (NotifyMode m : values()) if (m.name().equals(value)) return m;
        return null;
    }
}
```

`AlertStatus.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/** 알림 상태 (스펙 §6.5). 목록 정렬 순서는 §12.2가 정한다 — sortOrder(). */
public enum AlertStatus {
    ACTIVE, PAUSED, ENDED, EXPIRED;

    public static AlertStatus of(String value) {
        for (AlertStatus s : values()) if (s.name().equals(value)) return s;
        return null;
    }
}
```

`Unit.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/**
 * 지표의 단위. 두 피연산자를 비교하려면 단위가 같아야 한다(스펙 §14.2).
 * RSI는 다른 지표와 비교되지 않게 INDEX로 따로 둔다.
 */
public enum Unit {
    PRICE, KRW, PERCENT, SHARES, RATIO, INDEX;

    public String key() { return name().toLowerCase(); }
}
```

`DataKind.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/** 지표가 기다리는 데이터 종류 (스펙 §5.4). 앞의 셋은 데이터, 마지막은 백엔드 소유다. */
public enum DataKind { INTRADAY_QUOTE, DAILY_BAR, DAILY_FLOW, PORTFOLIO_SNAPSHOT }
```

`Scope.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/** 시장 데이터에서 오는 지표인가, 사용자의 보유 스냅샷에서 오는 지표인가. */
public enum Scope { MARKET, USER }
```

`OperatorKey.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/** 연산자 (스펙 §5.2). 문장의 두 문체가 쓰는 표기를 함께 갖는다(§12.1). */
public enum OperatorKey {
    GTE("gte", "≥", "이상"),
    LTE("lte", "≤", "이하"),
    GT("gt", ">", "초과"),
    LT("lt", "<", "미만"),
    CROSSES_ABOVE("crosses_above", "상향 돌파", "상향 돌파하면"),
    CROSSES_BELOW("crosses_below", "하향 이탈", "하향 이탈하면");

    private final String key;
    private final String symbol;
    private final String word;

    OperatorKey(String key, String symbol, String word) {
        this.key = key;
        this.symbol = symbol;
        this.word = word;
    }

    public String key() { return key; }
    public String symbol() { return symbol; }
    public String word() { return word; }
    public boolean isCross() { return this == CROSSES_ABOVE || this == CROSSES_BELOW; }

    public static OperatorKey of(String key) {
        for (OperatorKey o : values()) if (o.key.equals(key)) return o;
        return null;
    }
}
```

`TransformType.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/** 변형 (스펙 §4.2). */
public enum TransformType {
    IDENTITY, WINDOW, DELTA, PCT;

    public String key() { return name().toLowerCase(); }

    public static TransformType of(String key) {
        for (TransformType t : values()) if (t.key().equals(key)) return t;
        return null;
    }
}
```

`WindowFn.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/** 윈도우 집계 함수. 화면 이름은 최고·최저·평균·합계다(§12.5.4). */
public enum WindowFn {
    MAX("최고"), MIN("최저"), AVG("평균"), SUM("합계");

    private final String label;

    WindowFn(String label) { this.label = label; }

    public String key() { return name().toLowerCase(); }
    public String label() { return label; }

    public static WindowFn of(String key) {
        for (WindowFn f : values()) if (f.key().equals(key)) return f;
        return null;
    }
}
```

`ParamSpec.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/** 지표 자체 파라미터. 지금은 기간 n 하나뿐이다. */
public record ParamSpec(String key, int defaultValue, int min, int max) { }
```

`TransformRule.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/** 지표가 허용하는 변형 하나와 그 n의 범위. IDENTITY는 n이 없어 0~0이다. */
public record TransformRule(TransformType type, int nMin, int nMax) {

    public static TransformRule identity() { return new TransformRule(TransformType.IDENTITY, 0, 0); }
}
```

`IndicatorKey.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/** 지표 키 (스펙 §5.1). JSON 필드명과 같은 snake_case다. */
public enum IndicatorKey {
    PRICE("price"),
    CHANGE_PCT("change_pct"),
    VOLUME("volume"),
    VOLUME_RATIO("volume_ratio"),
    HIGH("high"),
    LOW("low"),
    RANGE_PCT("range_pct"),
    SMA("sma"),
    RSI("rsi"),
    DISPARITY("disparity"),
    FOREIGN_NET_BUY("foreign_net_buy"),
    INSTITUTION_NET_BUY("institution_net_buy"),
    UNREALIZED_PNL_PCT("unrealized_pnl_pct"),
    WEIGHT_PCT("weight_pct");

    private final String key;

    IndicatorKey(String key) { this.key = key; }

    public String key() { return key; }

    public static IndicatorKey of(String key) {
        for (IndicatorKey k : values()) if (k.key.equals(key)) return k;
        return null;
    }
}
```

`PresetKey.java`:

```java
package com.stockproject.portfolio.alert.catalog;

/** 프리셋 키 (스펙 §5.3). */
public enum PresetKey {
    PRICE_REACH("price_reach"),
    CHANGE_MOVE("change_move"),
    VOLUME_SURGE("volume_surge"),
    MA_CROSS("ma_cross"),
    RSI_ZONE("rsi_zone"),
    BOX_BREAKOUT("box_breakout"),
    INVESTOR_STREAK("investor_streak"),
    INVESTOR_TURN("investor_turn"),
    PNL_REACH("pnl_reach");

    private final String key;

    PresetKey(String key) { this.key = key; }

    public String key() { return key; }

    public static PresetKey of(String key) {
        for (PresetKey k : values()) if (k.key.equals(key)) return k;
        return null;
    }
}
```

- [ ] **Step 4: 지표·프리셋 레코드와 카탈로그를 쓴다**

`Indicator.java`:

```java
package com.stockproject.portfolio.alert.catalog;

import com.stockproject.portfolio.domain.Market;

import java.util.List;
import java.util.Map;
import java.util.Set;

/** 지표 하나 (스펙 §5.1). 필요 봉 수 계산은 compile.RequiredBars가 한다. */
public record Indicator(IndicatorKey key, String label, String category, Unit unit,
                        List<ParamSpec> params, boolean intradayLeft, Set<Market> markets,
                        List<TransformRule> transforms, Set<OperatorKey> operators,
                        Scope scope, Set<DataKind> requires) {

    public TransformRule rule(TransformType type) {
        for (TransformRule r : transforms) if (r.type() == type) return r;
        return null;
    }

    public ParamSpec param(String name) {
        for (ParamSpec p : params) if (p.key().equals(name)) return p;
        return null;
    }

    public int paramOrDefault(Map<String, Integer> given, String name) {
        Integer value = given == null ? null : given.get(name);
        if (value != null) return value;
        ParamSpec spec = param(name);
        if (spec == null) throw new IllegalArgumentException(key.key() + "에는 " + name + " 파라미터가 없다");
        return spec.defaultValue();
    }
}
```

`PresetParam.java`:

```java
package com.stockproject.portfolio.alert.catalog;

import java.math.BigDecimal;
import java.util.List;

/**
 * 프리셋 입력 칸 하나 (스펙 §12.5.3). 숫자 칸은 범위를, 선택 칸은 선택지를 갖는다.
 * 기본값이 없는 칸(가격 도달의 가격)은 required다 — 화면이 직전 종가로 채운다.
 */
public record PresetParam(String key, Kind kind, BigDecimal min, BigDecimal max,
                          BigDecimal defaultNumber, List<String> choices, String defaultChoice,
                          boolean required) {

    public enum Kind { INT, DECIMAL, CHOICE }

    public static PresetParam integer(String key, int min, int max, int defaultValue) {
        return new PresetParam(key, Kind.INT, BigDecimal.valueOf(min), BigDecimal.valueOf(max),
                BigDecimal.valueOf(defaultValue), List.of(), null, false);
    }

    public static PresetParam decimal(String key, String min, String max, String defaultValue) {
        return new PresetParam(key, Kind.DECIMAL, new BigDecimal(min), new BigDecimal(max),
                defaultValue == null ? null : new BigDecimal(defaultValue), List.of(), null,
                defaultValue == null);
    }

    public static PresetParam choice(String key, List<String> choices, String defaultChoice) {
        return new PresetParam(key, Kind.CHOICE, null, null, null, choices, defaultChoice, false);
    }
}
```

`Preset.java`:

```java
package com.stockproject.portfolio.alert.catalog;

import com.stockproject.portfolio.domain.Market;

import java.util.List;
import java.util.Set;

/** 프리셋 하나 (스펙 §5.3). v1 프리셋은 전부 템플릿이라 전개 규칙은 compile.Compiler에 있다. */
public record Preset(PresetKey key, String label, Set<Cadence> cadences, Set<Market> markets,
                     Scope scope, List<PresetParam> params) {

    public PresetParam param(String name) {
        for (PresetParam p : params) if (p.key().equals(name)) return p;
        return null;
    }
}
```

`AlertCatalog.java`:

```java
package com.stockproject.portfolio.alert.catalog;

import com.stockproject.portfolio.domain.Market;

import java.util.EnumMap;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static com.stockproject.portfolio.alert.catalog.OperatorKey.*;

/**
 * 알림 카탈로그 (스펙 §5). 코드 상수다 — 지표를 늘리는 일은 계산 코드를 함께 쓰는 일이라
 * 배포가 어차피 필요하고, 운영자가 런타임에 지표를 더할 일이 없다.
 */
public final class AlertCatalog {

    private AlertCatalog() { }

    private static final Set<Market> BOTH = EnumSet.of(Market.KR, Market.US);
    private static final Set<Market> KR = EnumSet.of(Market.KR);
    private static final Set<OperatorKey> ALL_OPERATORS = EnumSet.allOf(OperatorKey.class);
    private static final Set<OperatorKey> COMPARE_ONLY = EnumSet.of(GTE, LTE, GT, LT);

    private static final List<TransformRule> FULL = List.of(
            TransformRule.identity(),
            new TransformRule(TransformType.WINDOW, 1, 120),
            new TransformRule(TransformType.DELTA, 1, 120),
            new TransformRule(TransformType.PCT, 1, 120));
    private static final List<TransformRule> IDENTITY_DELTA = List.of(
            TransformRule.identity(), new TransformRule(TransformType.DELTA, 1, 120));
    private static final List<TransformRule> RSI_TRANSFORMS = List.of(
            TransformRule.identity(), new TransformRule(TransformType.DELTA, 1, 5));
    private static final List<TransformRule> FLOW_TRANSFORMS = List.of(
            TransformRule.identity(),
            new TransformRule(TransformType.DELTA, 1, 5),
            new TransformRule(TransformType.WINDOW, 1, 10));
    private static final List<TransformRule> IDENTITY_ONLY = List.of(TransformRule.identity());

    private static final Set<DataKind> BAR = EnumSet.of(DataKind.DAILY_BAR);
    private static final Set<DataKind> QUOTE_BAR = EnumSet.of(DataKind.INTRADAY_QUOTE, DataKind.DAILY_BAR);
    private static final Set<DataKind> FLOW = EnumSet.of(DataKind.DAILY_FLOW);
    private static final Set<DataKind> SNAPSHOT = EnumSet.of(DataKind.PORTFOLIO_SNAPSHOT);

    private static final List<ParamSpec> NO_PARAMS = List.of();

    private static final List<Indicator> INDICATORS = List.of(
            new Indicator(IndicatorKey.PRICE, "가격", "시세", Unit.PRICE, NO_PARAMS, true, BOTH,
                    FULL, ALL_OPERATORS, Scope.MARKET, QUOTE_BAR),
            new Indicator(IndicatorKey.CHANGE_PCT, "등락률", "시세", Unit.PERCENT, NO_PARAMS, true, BOTH,
                    FULL, ALL_OPERATORS, Scope.MARKET, QUOTE_BAR),
            new Indicator(IndicatorKey.VOLUME, "거래량", "시세", Unit.SHARES, NO_PARAMS, true, BOTH,
                    FULL, ALL_OPERATORS, Scope.MARKET, QUOTE_BAR),
            new Indicator(IndicatorKey.VOLUME_RATIO, "거래량 배수", "시세", Unit.RATIO,
                    List.of(new ParamSpec("n", 20, 5, 120)), true, BOTH,
                    FULL, ALL_OPERATORS, Scope.MARKET, QUOTE_BAR),
            new Indicator(IndicatorKey.HIGH, "고가", "시세", Unit.PRICE, NO_PARAMS, false, BOTH,
                    FULL, ALL_OPERATORS, Scope.MARKET, BAR),
            new Indicator(IndicatorKey.LOW, "저가", "시세", Unit.PRICE, NO_PARAMS, false, BOTH,
                    FULL, ALL_OPERATORS, Scope.MARKET, BAR),
            new Indicator(IndicatorKey.RANGE_PCT, "가격 폭", "기술지표", Unit.PERCENT,
                    List.of(new ParamSpec("n", 20, 5, 120)), false, BOTH,
                    IDENTITY_DELTA, ALL_OPERATORS, Scope.MARKET, BAR),
            new Indicator(IndicatorKey.SMA, "이동평균", "기술지표", Unit.PRICE,
                    List.of(new ParamSpec("n", 20, 2, 120)), false, BOTH,
                    FULL, ALL_OPERATORS, Scope.MARKET, BAR),
            new Indicator(IndicatorKey.RSI, "RSI", "기술지표", Unit.INDEX,
                    List.of(new ParamSpec("n", 14, 2, 30)), false, BOTH,
                    RSI_TRANSFORMS, ALL_OPERATORS, Scope.MARKET, BAR),
            new Indicator(IndicatorKey.DISPARITY, "이격도", "기술지표", Unit.PERCENT,
                    List.of(new ParamSpec("n", 20, 2, 120)), false, BOTH,
                    IDENTITY_DELTA, ALL_OPERATORS, Scope.MARKET, BAR),
            new Indicator(IndicatorKey.FOREIGN_NET_BUY, "외국인 순매수", "수급", Unit.KRW, NO_PARAMS,
                    false, KR, FLOW_TRANSFORMS, ALL_OPERATORS, Scope.MARKET, FLOW),
            new Indicator(IndicatorKey.INSTITUTION_NET_BUY, "기관 순매수", "수급", Unit.KRW, NO_PARAMS,
                    false, KR, FLOW_TRANSFORMS, ALL_OPERATORS, Scope.MARKET, FLOW),
            new Indicator(IndicatorKey.UNREALIZED_PNL_PCT, "평가손익률", "내 보유", Unit.PERCENT,
                    NO_PARAMS, false, BOTH, IDENTITY_ONLY, COMPARE_ONLY, Scope.USER, SNAPSHOT),
            new Indicator(IndicatorKey.WEIGHT_PCT, "비중", "내 보유", Unit.PERCENT,
                    NO_PARAMS, false, BOTH, IDENTITY_ONLY, COMPARE_ONLY, Scope.USER, SNAPSHOT));

    private static final Set<Cadence> BOTH_CADENCES = EnumSet.of(Cadence.INTRADAY, Cadence.CLOSE);
    private static final Set<Cadence> CLOSE_ONLY = EnumSet.of(Cadence.CLOSE);

    private static final List<Preset> PRESETS = List.of(
            new Preset(PresetKey.PRICE_REACH, "가격 도달", BOTH_CADENCES, BOTH, Scope.MARKET, List.of(
                    PresetParam.choice("direction", List.of("up", "down"), "up"),
                    PresetParam.decimal("price", "0.0001", "100000000", null))),
            new Preset(PresetKey.CHANGE_MOVE, "급등락", BOTH_CADENCES, BOTH, Scope.MARKET, List.of(
                    PresetParam.choice("direction", List.of("up", "down"), "up"),
                    PresetParam.decimal("pct", "0.1", "30", "5"))),
            new Preset(PresetKey.VOLUME_SURGE, "거래량 급증", BOTH_CADENCES, BOTH, Scope.MARKET, List.of(
                    PresetParam.integer("n", 5, 120, 20),
                    PresetParam.decimal("multiple", "1.1", "50", "3"))),
            new Preset(PresetKey.MA_CROSS, "골든·데드크로스", CLOSE_ONLY, BOTH, Scope.MARKET, List.of(
                    PresetParam.choice("direction", List.of("golden", "dead"), "golden"),
                    PresetParam.integer("short", 2, 120, 5),
                    PresetParam.integer("long", 2, 120, 20))),
            new Preset(PresetKey.RSI_ZONE, "RSI 과매수·과매도", CLOSE_ONLY, BOTH, Scope.MARKET, List.of(
                    PresetParam.choice("zone", List.of("overbought", "oversold"), "overbought"),
                    PresetParam.decimal("level", "1", "99", "70"),
                    PresetParam.integer("n", 2, 30, 14))),
            new Preset(PresetKey.BOX_BREAKOUT, "박스권 돌파", CLOSE_ONLY, BOTH, Scope.MARKET, List.of(
                    PresetParam.integer("window_days", 5, 120, 20),
                    PresetParam.decimal("max_range_pct", "1", "100", "15"),
                    PresetParam.choice("direction", List.of("up", "down"), "up"))),
            new Preset(PresetKey.INVESTOR_STREAK, "외국인·기관 연속 순매수", CLOSE_ONLY, KR, Scope.MARKET, List.of(
                    PresetParam.choice("investor", List.of("foreign", "institution"), "foreign"),
                    PresetParam.choice("side", List.of("buy", "sell"), "buy"),
                    PresetParam.integer("days", 1, 20, 3))),
            new Preset(PresetKey.INVESTOR_TURN, "외국인·기관 순매수 전환", CLOSE_ONLY, KR, Scope.MARKET, List.of(
                    PresetParam.choice("investor", List.of("foreign", "institution"), "foreign"),
                    PresetParam.choice("side", List.of("buy", "sell"), "buy"))),
            new Preset(PresetKey.PNL_REACH, "수익률 도달", CLOSE_ONLY, BOTH, Scope.USER, List.of(
                    PresetParam.choice("direction", List.of("profit", "loss"), "profit"),
                    PresetParam.decimal("pct", "0.1", "1000", "10"))));

    private static final Map<IndicatorKey, Indicator> BY_INDICATOR = new EnumMap<>(IndicatorKey.class);
    private static final Map<PresetKey, Preset> BY_PRESET = new EnumMap<>(PresetKey.class);

    static {
        for (Indicator i : INDICATORS) BY_INDICATOR.put(i.key(), i);
        for (Preset p : PRESETS) BY_PRESET.put(p.key(), p);
    }

    public static List<Indicator> indicators() { return INDICATORS; }
    public static Indicator indicator(IndicatorKey key) { return BY_INDICATOR.get(key); }
    public static List<Preset> presets() { return PRESETS; }
    public static Preset preset(PresetKey key) { return BY_PRESET.get(key); }
}
```

`price_reach.price`의 최솟값과 최댓값은 종목 통화의 가격이 가질 수 있는 넓은 범위다. 현실적인 가격 판단은 사용자 몫이다.

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.catalog.AlertCatalogTest'`
Expected: PASS

- [ ] **Step 6: 기존 아키텍처 규칙도 통과하는지 확인한다**

`ArchitectureRulesTest.카탈로그는_도메인_밖으로_나가지_않는다`는 `..catalog..` 전체에 걸린다. `alert.catalog`도 Spring에 의존하지 않아야 한다.

Run: `./gradlew test --tests 'com.stockproject.portfolio.ArchitectureRulesTest'`
Expected: PASS

- [ ] **Step 7: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/catalog \
        src/test/java/com/stockproject/portfolio/alert/catalog
git commit -m "feat: 알림 카탈로그를 코드 상수로 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 트리거 모델과 요청 해석 — 경로가 붙은 오류

요청 JSON을 `AlertDraft`로 옮긴다. 형이 틀리거나 빠진 값은 예외가 아니라 `FieldError` 목록으로 돌려준다 — 미리보기는 오류가 있어도 `200`으로 `errors`를 싣고(스펙 §11.3), 저장은 `400 INVALID_ALERT`로 같은 목록을 싣는다.

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/spec/` 아래 `Operand.java` · `Transform.java` · `Right.java` · `Modifier.java` · `Condition.java` · `TriggerSpec.java` · `AlertDraft.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/validation/` 아래 `FieldError.java` · `ParseResult.java` · `AlertRequestParser.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/validation/AlertRequestParserTest.java`

**Interfaces:**
- Consumes: Task 2의 `IndicatorKey` · `OperatorKey` · `TransformType` · `WindowFn` · `PresetKey` · `Cadence` · `NotifyMode` · `AlertCatalog` · `PresetParam`.
- Produces:
  - `record Operand(IndicatorKey indicator, Map<String,Integer> params, Transform transform)` — `params`는 비어 있을 수 있다(기본값은 카탈로그).
  - `sealed interface Transform` — `Identity()` · `Window(WindowFn fn, int n, Integer lag)` · `Delta(int n)` · `Pct(int n)`, 공통 `TransformType type()`. `Window.lag`는 요청에서 `null`이고 컴파일러가 정한다.
  - `record Right(BigDecimal constant, Operand operand)` — `Right.constant(BigDecimal)`, `Right.operand(Operand)`, `boolean isConstant()`.
  - `sealed interface Modifier` — `Streak(int n)` · `PersistMin(int minutes)`.
  - `record Condition(Operand left, OperatorKey op, Right right, Modifier modifier)` — `modifier`는 `null` 가능.
  - `sealed interface TriggerSpec` — `Composable(List<Condition> conditions)` · `PresetTrigger(PresetKey key, Map<String,Object> params)`(숫자는 `BigDecimal`, 선택은 `String`).
  - `record AlertDraft(UUID instrumentId, String name, Cadence cadence, NotifyMode notifyMode, Integer cooldownMin, OffsetDateTime expiresAt, TriggerSpec trigger)`
  - `record FieldError(String path, String code, String message)`
  - `record ParseResult(AlertDraft draft, List<FieldError> errors, UUID alertId)` — `draft`는 형 오류가 있으면 `null`. `alertId`는 미리보기 본문의 `alert_id`.
  - `final class AlertRequestParser` — `static ParseResult parse(JsonNode body)`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/validation/AlertRequestParserTest.java`:

```java
package com.stockproject.portfolio.alert.validation;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.NotifyMode;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.catalog.PresetKey;
import com.stockproject.portfolio.alert.catalog.WindowFn;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Transform;
import com.stockproject.portfolio.alert.spec.TriggerSpec;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

class AlertRequestParserTest {

    private static final ObjectMapper JSON = new ObjectMapper();

    @Test
    void 조립형_요청을_모델로_옮긴다() throws Exception {
        ParseResult result = AlertRequestParser.parse(json("""
                { "instrument_id": "10000000-0000-0000-0000-000000000001",
                  "name": "삼성전자 20일 고점 돌파",
                  "cadence": "INTRADAY", "notify_mode": "COOLDOWN", "cooldown_min": 60,
                  "trigger_type": "COMPOSABLE",
                  "trigger_spec": { "conditions": [ {
                    "left":  { "indicator": "price", "transform": { "type": "identity" } },
                    "op": "gt",
                    "right": { "indicator": "high", "transform": { "type": "window", "fn": "max", "n": 20 } },
                    "modifier": { "persist_min": 10 } } ] } }
                """));

        assertThat(result.errors()).isEmpty();
        assertThat(result.draft().cadence()).isEqualTo(Cadence.INTRADAY);
        assertThat(result.draft().notifyMode()).isEqualTo(NotifyMode.COOLDOWN);
        assertThat(result.draft().cooldownMin()).isEqualTo(60);

        Condition c = ((TriggerSpec.Composable) result.draft().trigger()).conditions().get(0);
        assertThat(c.left().indicator()).isEqualTo(IndicatorKey.PRICE);
        assertThat(c.op()).isEqualTo(OperatorKey.GT);
        assertThat(c.right().operand().transform())
                .isEqualTo(new Transform.Window(WindowFn.MAX, 20, null));
        assertThat(c.modifier()).isEqualTo(new Modifier.PersistMin(10));
    }

    @Test
    void 선택_필드의_기본값을_채운다() throws Exception {
        ParseResult result = AlertRequestParser.parse(json("""
                { "instrument_id": "10000000-0000-0000-0000-000000000001", "name": "카카오 RSI",
                  "cadence": "CLOSE", "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "rsi_zone",
                                    "params": { "zone": "overbought", "level": 70, "n": 14 } } }
                """));

        assertThat(result.errors()).isEmpty();
        assertThat(result.draft().notifyMode()).isEqualTo(NotifyMode.EDGE_REARM);
        assertThat(result.draft().cooldownMin()).isNull();
        assertThat(result.draft().expiresAt()).isNull();
        TriggerSpec.PresetTrigger preset = (TriggerSpec.PresetTrigger) result.draft().trigger();
        assertThat(preset.key()).isEqualTo(PresetKey.RSI_ZONE);
        assertThat(preset.params().get("zone")).isEqualTo("overbought");
        assertThat((BigDecimal) preset.params().get("level")).isEqualByComparingTo("70");
    }

    @Test
    void 형이_틀리면_경로와_함께_오류를_돌려준다() throws Exception {
        ParseResult result = AlertRequestParser.parse(json("""
                { "instrument_id": "not-a-uuid", "name": "x", "cadence": "WEEKLY",
                  "trigger_type": "COMPOSABLE",
                  "trigger_spec": { "conditions": [ {
                    "left": { "indicator": "rsi", "indicator_params": { "n": "abc" },
                              "transform": { "type": "identity" } },
                    "op": "gte", "right": { "const": "칠십" } } ] } }
                """));

        assertThat(result.draft()).isNull();
        assertThat(result.errors()).extracting(FieldError::path, FieldError::code).containsExactly(
                org.assertj.core.groups.Tuple.tuple("instrument_id", "INVALID_TYPE"),
                org.assertj.core.groups.Tuple.tuple("cadence", "INVALID_VALUE"),
                org.assertj.core.groups.Tuple.tuple("trigger_spec.conditions[0].left.indicator_params.n", "INVALID_TYPE"),
                org.assertj.core.groups.Tuple.tuple("trigger_spec.conditions[0].right.const", "INVALID_TYPE"));
    }

    @Test
    void 조립형_요청에_lag가_있으면_거부한다() throws Exception {
        ParseResult result = AlertRequestParser.parse(json("""
                { "instrument_id": "10000000-0000-0000-0000-000000000001", "name": "x",
                  "cadence": "CLOSE", "trigger_type": "COMPOSABLE",
                  "trigger_spec": { "conditions": [ {
                    "left": { "indicator": "price", "transform": { "type": "identity" } },
                    "op": "gt",
                    "right": { "indicator": "high",
                               "transform": { "type": "window", "fn": "max", "n": 20, "lag": 1 } } } ] } }
                """));

        assertThat(result.errors()).extracting(FieldError::path, FieldError::code).containsExactly(
                org.assertj.core.groups.Tuple.tuple("trigger_spec.conditions[0].right.transform.lag", "LAG_NOT_ALLOWED"));
    }

    @Test
    void 조건_목록이_배열이_아니면_거부한다() throws Exception {
        ParseResult result = AlertRequestParser.parse(json("""
                { "instrument_id": "10000000-0000-0000-0000-000000000001", "name": "x",
                  "cadence": "CLOSE", "trigger_type": "COMPOSABLE", "trigger_spec": { "conditions": {} } }
                """));

        assertThat(result.errors()).extracting(FieldError::path, FieldError::code).containsExactly(
                org.assertj.core.groups.Tuple.tuple("trigger_spec.conditions", "INVALID_TYPE"));
    }

    @Test
    void 미리보기의_alert_id를_읽는다() throws Exception {
        ParseResult result = AlertRequestParser.parse(json("""
                { "alert_id": "50000000-0000-0000-0000-000000000001",
                  "instrument_id": "10000000-0000-0000-0000-000000000001", "name": "x",
                  "cadence": "CLOSE", "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "price_reach",
                                    "params": { "direction": "up", "price": 70000 } } }
                """));

        assertThat(result.alertId()).hasToString("50000000-0000-0000-0000-000000000001");
    }

    @Test
    void 유효기간을_시각으로_읽는다() throws Exception {
        ParseResult result = AlertRequestParser.parse(json("""
                { "instrument_id": "10000000-0000-0000-0000-000000000001", "name": "x",
                  "cadence": "CLOSE", "expires_at": "2026-12-31T15:30:00+09:00",
                  "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "price_reach",
                                    "params": { "direction": "up", "price": 70000 } } }
                """));

        assertThat(result.draft().expiresAt()).hasToString("2026-12-31T15:30+09:00");
    }

    private static JsonNode json(String text) throws Exception { return JSON.readTree(text); }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.validation.AlertRequestParserTest'`
Expected: FAIL — 컴파일 오류

- [ ] **Step 3: 모델을 쓴다**

`alert/spec/Operand.java`:

```java
package com.stockproject.portfolio.alert.spec;

import com.stockproject.portfolio.alert.catalog.IndicatorKey;

import java.util.Map;

/** 지표 + 지표 파라미터 + 변형 (스펙 §4.2). 파라미터가 비어 있으면 카탈로그 기본값을 쓴다. */
public record Operand(IndicatorKey indicator, Map<String, Integer> params, Transform transform) {

    public Operand {
        params = params == null ? Map.of() : Map.copyOf(params);
    }

    public Operand withTransform(Transform next) { return new Operand(indicator, params, next); }
}
```

`alert/spec/Transform.java`:

```java
package com.stockproject.portfolio.alert.spec;

import com.stockproject.portfolio.alert.catalog.TransformType;
import com.stockproject.portfolio.alert.catalog.WindowFn;

/**
 * 변형 (스펙 §4.2). Window.lag는 사용자가 만든 조건의 요청에서 null이고,
 * 컴파일러가 맞은편을 보고 0 또는 1로 정한다(§4.2). 프리셋은 직접 정한다.
 */
public sealed interface Transform {

    TransformType type();

    record Identity() implements Transform {
        public TransformType type() { return TransformType.IDENTITY; }
    }

    record Window(WindowFn fn, int n, Integer lag) implements Transform {
        public TransformType type() { return TransformType.WINDOW; }
        public Window withLag(int value) { return new Window(fn, n, value); }
        public int lagOrZero() { return lag == null ? 0 : lag; }
    }

    record Delta(int n) implements Transform {
        public TransformType type() { return TransformType.DELTA; }
    }

    record Pct(int n) implements Transform {
        public TransformType type() { return TransformType.PCT; }
    }
}
```

`alert/spec/Right.java`:

```java
package com.stockproject.portfolio.alert.spec;

import java.math.BigDecimal;

/** 비교의 오른쪽 — 상수이거나 다른 피연산자다. 둘 중 정확히 하나만 있다. */
public record Right(BigDecimal constant, Operand operand) {

    public Right {
        if ((constant == null) == (operand == null)) {
            throw new IllegalArgumentException("상수와 피연산자 중 정확히 하나여야 한다");
        }
    }

    public static Right constant(BigDecimal value) { return new Right(value, null); }
    public static Right operand(Operand operand) { return new Right(null, operand); }
    public boolean isConstant() { return constant != null; }
}
```

`alert/spec/Modifier.java`:

```java
package com.stockproject.portfolio.alert.spec;

/** 유지 조건 (스펙 §4.2). 종가 알림은 연속 N일, 장중 알림은 N분 지속만 쓴다. */
public sealed interface Modifier {
    record Streak(int n) implements Modifier { }
    record PersistMin(int minutes) implements Modifier { }
}
```

`alert/spec/Condition.java`:

```java
package com.stockproject.portfolio.alert.spec;

import com.stockproject.portfolio.alert.catalog.OperatorKey;

/** 조건 하나. 알림의 조건들은 AND로 묶인다(스펙 §6.1). modifier는 없을 수 있다. */
public record Condition(Operand left, OperatorKey op, Right right, Modifier modifier) { }
```

`alert/spec/TriggerSpec.java`:

```java
package com.stockproject.portfolio.alert.spec;

import com.stockproject.portfolio.alert.catalog.PresetKey;

import java.util.List;
import java.util.Map;

/**
 * 트리거 (스펙 §4.2 · §4.3). 프리셋은 preset_key와 params 그대로 두고,
 * 평가할 때 컴파일한다 — 수정 화면이 프리셋 폼을 다시 열 수 있게 하기 위해서다.
 * params의 숫자는 BigDecimal, 선택은 String이다.
 */
public sealed interface TriggerSpec {

    String typeName();

    record Composable(List<Condition> conditions) implements TriggerSpec {
        public Composable { conditions = List.copyOf(conditions); }
        public String typeName() { return "COMPOSABLE"; }
    }

    record PresetTrigger(PresetKey key, Map<String, Object> params) implements TriggerSpec {
        public PresetTrigger { params = Map.copyOf(params); }
        public String typeName() { return "PRESET"; }
    }
}
```

`alert/spec/AlertDraft.java`:

```java
package com.stockproject.portfolio.alert.spec;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.NotifyMode;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 저장·미리보기 요청 하나. 해석만 끝난 상태이고 검증은 AlertValidator가 한다. */
public record AlertDraft(UUID instrumentId, String name, Cadence cadence, NotifyMode notifyMode,
                         Integer cooldownMin, OffsetDateTime expiresAt, TriggerSpec trigger) { }
```

- [ ] **Step 4: 해석기를 쓴다**

`alert/validation/FieldError.java`:

```java
package com.stockproject.portfolio.alert.validation;

/**
 * 입력 칸 하나의 오류. path는 요청 JSON 경로라 폼이 그 칸 아래에 message를 그대로 띄운다
 * (스펙 §11.4).
 */
public record FieldError(String path, String code, String message) { }
```

`alert/validation/ParseResult.java`:

```java
package com.stockproject.portfolio.alert.validation;

import com.stockproject.portfolio.alert.spec.AlertDraft;

import java.util.List;
import java.util.UUID;

/** 해석 결과. 형 오류가 하나라도 있으면 draft는 null이다 — 검증으로 넘길 모양이 아니다. */
public record ParseResult(AlertDraft draft, List<FieldError> errors, UUID alertId) {

    public boolean ok() { return draft != null && errors.isEmpty(); }
}
```

`alert/validation/AlertRequestParser.java`:

```java
package com.stockproject.portfolio.alert.validation;

import com.fasterxml.jackson.databind.JsonNode;
import com.stockproject.portfolio.alert.catalog.AlertCatalog;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.NotifyMode;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.catalog.Preset;
import com.stockproject.portfolio.alert.catalog.PresetKey;
import com.stockproject.portfolio.alert.catalog.PresetParam;
import com.stockproject.portfolio.alert.catalog.TransformType;
import com.stockproject.portfolio.alert.catalog.WindowFn;
import com.stockproject.portfolio.alert.spec.AlertDraft;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Right;
import com.stockproject.portfolio.alert.spec.Transform;
import com.stockproject.portfolio.alert.spec.TriggerSpec;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 요청 JSON을 AlertDraft로 옮긴다. 범위·조합 규칙은 보지 않는다 — 그것은 AlertValidator 몫이다.
 * 여기서는 "모양"만 본다: 있어야 할 값이 있는가, 형이 맞는가, 열거형 안의 값인가.
 */
public final class AlertRequestParser {

    private AlertRequestParser() { }

    public static ParseResult parse(JsonNode body) {
        List<FieldError> errors = new ArrayList<>();
        if (body == null || !body.isObject()) {
            errors.add(new FieldError("", "INVALID_TYPE", "요청 본문이 객체가 아니에요"));
            return new ParseResult(null, errors, null);
        }

        UUID alertId = optionalUuid(body, "alert_id", errors);
        UUID instrumentId = requiredUuid(body, "instrument_id", errors);
        String name = requiredText(body, "name", errors);
        Cadence cadence = requiredEnum(body, "cadence", Cadence::of, errors);
        NotifyMode mode = body.hasNonNull("notify_mode")
                ? requiredEnum(body, "notify_mode", NotifyMode::of, errors) : NotifyMode.EDGE_REARM;
        Integer cooldown = optionalInt(body, "cooldown_min", "cooldown_min", errors);
        OffsetDateTime expiresAt = optionalTime(body, "expires_at", errors);
        TriggerSpec trigger = trigger(body, errors);

        if (!errors.isEmpty()) return new ParseResult(null, errors, alertId);
        return new ParseResult(
                new AlertDraft(instrumentId, name, cadence, mode, cooldown, expiresAt, trigger),
                List.of(), alertId);
    }

    // ---- 트리거 ----------------------------------------------------------

    private static TriggerSpec trigger(JsonNode body, List<FieldError> errors) {
        String type = requiredText(body, "trigger_type", errors);
        JsonNode spec = body.get("trigger_spec");
        if (spec == null || !spec.isObject()) {
            errors.add(new FieldError("trigger_spec", spec == null ? "REQUIRED" : "INVALID_TYPE",
                    "조건을 입력해 주세요"));
            return null;
        }
        if (type == null) return null;
        return switch (type) {
            case "COMPOSABLE" -> composable(spec, errors);
            case "PRESET" -> preset(spec, errors);
            default -> {
                errors.add(new FieldError("trigger_type", "INVALID_VALUE", "알 수 없는 조건 종류예요"));
                yield null;
            }
        };
    }

    private static TriggerSpec composable(JsonNode spec, List<FieldError> errors) {
        JsonNode list = spec.get("conditions");
        String path = "trigger_spec.conditions";
        if (list == null) {
            errors.add(new FieldError(path, "REQUIRED", "조건을 하나 이상 넣어 주세요"));
            return null;
        }
        if (!list.isArray()) {
            errors.add(new FieldError(path, "INVALID_TYPE", "조건 목록이 배열이 아니에요"));
            return null;
        }
        List<Condition> conditions = new ArrayList<>();
        for (int i = 0; i < list.size(); i++) {
            Condition c = condition(list.get(i), path + "[" + i + "]", errors);
            if (c != null) conditions.add(c);
        }
        return new TriggerSpec.Composable(conditions);
    }

    private static Condition condition(JsonNode node, String path, List<FieldError> errors) {
        if (!node.isObject()) {
            errors.add(new FieldError(path, "INVALID_TYPE", "조건이 객체가 아니에요"));
            return null;
        }
        Operand left = operand(node.get("left"), path + ".left", errors, true);
        OperatorKey op = requiredEnum(node, "op", OperatorKey::of, errors, path + ".op");
        Right right = right(node.get("right"), path + ".right", errors);
        Modifier modifier = modifier(node.get("modifier"), path + ".modifier", errors);
        if (left == null || op == null || right == null) return null;
        return new Condition(left, op, right, modifier);
    }

    private static Right right(JsonNode node, String path, List<FieldError> errors) {
        if (node == null || node.isNull()) {
            errors.add(new FieldError(path, "REQUIRED", "기준값을 입력해 주세요"));
            return null;
        }
        if (node.has("const")) {
            JsonNode value = node.get("const");
            if (!value.isNumber()) {
                errors.add(new FieldError(path + ".const", "INVALID_TYPE", "기준값은 숫자여야 해요"));
                return null;
            }
            return Right.constant(value.decimalValue());
        }
        Operand operand = operand(node, path, errors, true);
        return operand == null ? null : Right.operand(operand);
    }

    private static Operand operand(JsonNode node, String path, List<FieldError> errors,
                                   boolean rejectLag) {
        if (node == null || !node.isObject()) {
            errors.add(new FieldError(path, node == null ? "REQUIRED" : "INVALID_TYPE", "지표를 골라 주세요"));
            return null;
        }
        IndicatorKey indicator = requiredEnum(node, "indicator", IndicatorKey::of, errors, path + ".indicator");
        Map<String, Integer> params = new LinkedHashMap<>();
        JsonNode p = node.get("indicator_params");
        if (p != null && !p.isNull()) {
            if (!p.isObject()) {
                errors.add(new FieldError(path + ".indicator_params", "INVALID_TYPE", "지표 설정이 객체가 아니에요"));
            } else {
                Iterator<Map.Entry<String, JsonNode>> it = p.fields();
                while (it.hasNext()) {
                    Map.Entry<String, JsonNode> e = it.next();
                    if (!e.getValue().canConvertToInt() || !e.getValue().isIntegralNumber()) {
                        errors.add(new FieldError(path + ".indicator_params." + e.getKey(),
                                "INVALID_TYPE", "기간은 정수여야 해요"));
                    } else {
                        params.put(e.getKey(), e.getValue().intValue());
                    }
                }
            }
        }
        Transform transform = transform(node.get("transform"), path + ".transform", errors, rejectLag);
        if (indicator == null || transform == null) return null;
        return new Operand(indicator, params, transform);
    }

    private static Transform transform(JsonNode node, String path, List<FieldError> errors,
                                       boolean rejectLag) {
        if (node == null || node.isNull()) return new Transform.Identity();
        if (!node.isObject()) {
            errors.add(new FieldError(path, "INVALID_TYPE", "변형이 객체가 아니에요"));
            return null;
        }
        TransformType type = requiredEnum(node, "type", TransformType::of, errors, path + ".type");
        if (type == null) return null;
        if (node.has("lag") && rejectLag) {
            errors.add(new FieldError(path + ".lag", "LAG_NOT_ALLOWED",
                    "오늘 포함 여부는 서버가 정해요"));
            return null;
        }
        return switch (type) {
            case IDENTITY -> new Transform.Identity();
            case WINDOW -> {
                WindowFn fn = requiredEnum(node, "fn", WindowFn::of, errors, path + ".fn");
                Integer n = requiredInt(node, "n", path + ".n", errors);
                yield fn == null || n == null ? null : new Transform.Window(fn, n, null);
            }
            case DELTA -> {
                Integer n = requiredInt(node, "n", path + ".n", errors);
                yield n == null ? null : new Transform.Delta(n);
            }
            case PCT -> {
                Integer n = requiredInt(node, "n", path + ".n", errors);
                yield n == null ? null : new Transform.Pct(n);
            }
        };
    }

    private static Modifier modifier(JsonNode node, String path, List<FieldError> errors) {
        if (node == null || node.isNull()) return null;
        if (!node.isObject()) {
            errors.add(new FieldError(path, "INVALID_TYPE", "유지 방식이 객체가 아니에요"));
            return null;
        }
        if (node.has("streak")) {
            Integer n = requiredInt(node, "streak", path + ".streak", errors);
            return n == null ? null : new Modifier.Streak(n);
        }
        if (node.has("persist_min")) {
            Integer n = requiredInt(node, "persist_min", path + ".persist_min", errors);
            return n == null ? null : new Modifier.PersistMin(n);
        }
        errors.add(new FieldError(path, "INVALID_VALUE", "알 수 없는 유지 방식이에요"));
        return null;
    }

    private static TriggerSpec preset(JsonNode spec, List<FieldError> errors) {
        PresetKey key = requiredEnum(spec, "preset_key", PresetKey::of, errors, "trigger_spec.preset_key");
        if (key == null) return null;
        Preset preset = AlertCatalog.preset(key);
        JsonNode params = spec.get("params");
        if (params != null && !params.isNull() && !params.isObject()) {
            errors.add(new FieldError("trigger_spec.params", "INVALID_TYPE", "프리셋 입력이 객체가 아니에요"));
            return null;
        }
        Map<String, Object> values = new LinkedHashMap<>();
        for (PresetParam param : preset.params()) {
            String path = "trigger_spec.params." + param.key();
            JsonNode value = params == null ? null : params.get(param.key());
            if (value == null || value.isNull()) continue;   // 기본값 채우기와 필수 검사는 검증이 한다
            switch (param.kind()) {
                case INT -> {
                    if (!value.isIntegralNumber()) errors.add(new FieldError(path, "INVALID_TYPE", "정수여야 해요"));
                    else values.put(param.key(), value.decimalValue());
                }
                case DECIMAL -> {
                    if (!value.isNumber()) errors.add(new FieldError(path, "INVALID_TYPE", "숫자여야 해요"));
                    else values.put(param.key(), value.decimalValue());
                }
                case CHOICE -> {
                    if (!value.isTextual()) errors.add(new FieldError(path, "INVALID_TYPE", "선택값이 아니에요"));
                    else values.put(param.key(), value.asText());
                }
            }
        }
        return new TriggerSpec.PresetTrigger(key, values);
    }

    // ---- 값 읽기 ----------------------------------------------------------

    private interface Lookup<T> { T of(String text); }

    private static <T> T requiredEnum(JsonNode node, String field, Lookup<T> lookup, List<FieldError> errors) {
        return requiredEnum(node, field, lookup, errors, field);
    }

    private static <T> T requiredEnum(JsonNode node, String field, Lookup<T> lookup,
                                      List<FieldError> errors, String path) {
        JsonNode value = node.get(field);
        if (value == null || value.isNull()) {
            errors.add(new FieldError(path, "REQUIRED", "값을 골라 주세요"));
            return null;
        }
        T found = value.isTextual() ? lookup.of(value.asText()) : null;
        if (found == null) errors.add(new FieldError(path, "INVALID_VALUE", "알 수 없는 값이에요"));
        return found;
    }

    private static String requiredText(JsonNode node, String field, List<FieldError> errors) {
        JsonNode value = node.get(field);
        if (value == null || value.isNull()) {
            errors.add(new FieldError(field, "REQUIRED", "값을 입력해 주세요"));
            return null;
        }
        if (!value.isTextual()) {
            errors.add(new FieldError(field, "INVALID_TYPE", "문자열이어야 해요"));
            return null;
        }
        return value.asText();
    }

    private static UUID requiredUuid(JsonNode node, String field, List<FieldError> errors) {
        JsonNode value = node.get(field);
        if (value == null || value.isNull()) {
            errors.add(new FieldError(field, "REQUIRED", "종목을 골라 주세요"));
            return null;
        }
        return uuid(value, field, errors);
    }

    private static UUID optionalUuid(JsonNode node, String field, List<FieldError> errors) {
        JsonNode value = node.get(field);
        return value == null || value.isNull() ? null : uuid(value, field, errors);
    }

    private static UUID uuid(JsonNode value, String field, List<FieldError> errors) {
        try {
            if (value.isTextual()) return UUID.fromString(value.asText());
        } catch (IllegalArgumentException ignored) {
            // 아래에서 오류로 남긴다
        }
        errors.add(new FieldError(field, "INVALID_TYPE", "식별자 형식이 아니에요"));
        return null;
    }

    private static Integer requiredInt(JsonNode node, String field, String path, List<FieldError> errors) {
        JsonNode value = node.get(field);
        if (value == null || value.isNull()) {
            errors.add(new FieldError(path, "REQUIRED", "값을 입력해 주세요"));
            return null;
        }
        if (!value.isIntegralNumber() || !value.canConvertToInt()) {
            errors.add(new FieldError(path, "INVALID_TYPE", "정수여야 해요"));
            return null;
        }
        return value.intValue();
    }

    private static Integer optionalInt(JsonNode node, String field, String path, List<FieldError> errors) {
        JsonNode value = node.get(field);
        return value == null || value.isNull() ? null : requiredInt(node, field, path, errors);
    }

    private static OffsetDateTime optionalTime(JsonNode node, String field, List<FieldError> errors) {
        JsonNode value = node.get(field);
        if (value == null || value.isNull()) return null;
        try {
            if (value.isTextual()) return OffsetDateTime.parse(value.asText());
        } catch (DateTimeParseException ignored) {
            // 아래에서 오류로 남긴다
        }
        errors.add(new FieldError(field, "INVALID_TYPE", "시각 형식이 아니에요"));
        return null;
    }
}
```

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.validation.AlertRequestParserTest'`
Expected: PASS

- [ ] **Step 6: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/spec \
        src/main/java/com/stockproject/portfolio/alert/validation \
        src/test/java/com/stockproject/portfolio/alert/validation
git commit -m "feat: 알림 요청을 해석하고 형 오류를 경로와 함께 돌려준다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 컴파일러 — 프리셋 전개, `lag` 결정, 필요 봉 수, `spec_hash`

Task 5(검증)가 프리셋의 컴파일 결과를 검증하므로 컴파일러를 먼저 만든다.

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/compile/` 아래 `CompiledTrigger.java` · `Compiler.java` · `RequiredBars.java` · `SpecHash.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/compile/CompilerTest.java` · `RequiredBarsTest.java`

**Interfaces:**
- Consumes: Task 2 카탈로그, Task 3 모델.
- Produces:
  - `record CompiledTrigger(List<Condition> conditions, PresetKey preset, Map<String,Object> presetParams)` — 조립형이면 `preset == null`. `presetParams`는 기본값을 채운 전체 값.
  - `final class Compiler` — `static CompiledTrigger compile(TriggerSpec trigger, Cadence cadence)`. 모든 `Transform.Window`의 `lag`가 채워져 나온다. `static Map<String,Object> withDefaults(PresetKey, Map<String,Object>)`.
  - `final class RequiredBars` — `static int of(Condition)`: 판정에 필요한 봉 수(현재 봉 포함, §5.4). `static int toRead(Condition)`: RSI의 계산 창을 반영해 읽을 봉 수.
  - `final class SpecHash` — `static String of(CompiledTrigger, Cadence)`: SHA-256 16진수 64자.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/compile/CompilerTest.java`:

```java
package com.stockproject.portfolio.alert.compile;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.catalog.PresetKey;
import com.stockproject.portfolio.alert.catalog.WindowFn;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Right;
import com.stockproject.portfolio.alert.spec.Transform;
import com.stockproject.portfolio.alert.spec.TriggerSpec;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class CompilerTest {

    private static final Transform ID = new Transform.Identity();

    /** 맞은편이 오늘 값이면 오늘을 뺀다(§4.2). 순서와 무관하다. */
    @Test
    void 종가_알림에서_맞은편이_오늘_값이면_윈도우는_오늘을_뺀다() {
        Condition c = new Condition(op(IndicatorKey.PRICE, ID), OperatorKey.GT,
                Right.operand(op(IndicatorKey.HIGH, new Transform.Window(WindowFn.MAX, 20, null))), null);
        Condition flipped = new Condition(op(IndicatorKey.HIGH, new Transform.Window(WindowFn.MAX, 20, null)),
                OperatorKey.LT, Right.operand(op(IndicatorKey.PRICE, ID)), null);

        assertThat(lagOfRight(compile(Cadence.CLOSE, c))).isEqualTo(1);
        assertThat(((Transform.Window) compile(Cadence.CLOSE, flipped).left().transform()).lag()).isEqualTo(1);
    }

    @Test
    void 윈도우끼리는_양쪽_다_오늘을_넣는다() {
        Condition c = new Condition(
                op(IndicatorKey.FOREIGN_NET_BUY, new Transform.Window(WindowFn.SUM, 5, null)), OperatorKey.GT,
                Right.operand(op(IndicatorKey.INSTITUTION_NET_BUY, new Transform.Window(WindowFn.SUM, 5, null))), null);
        Condition compiled = compile(Cadence.CLOSE, c);

        assertThat(((Transform.Window) compiled.left().transform()).lag()).isZero();
        assertThat(lagOfRight(compiled)).isZero();
    }

    @Test
    void 상수와_견주는_윈도우는_오늘을_넣는다() {
        Condition c = new Condition(
                op(IndicatorKey.FOREIGN_NET_BUY, new Transform.Window(WindowFn.SUM, 5, null)), OperatorKey.GTE,
                Right.constant(new BigDecimal("100000000000")), null);

        assertThat(((Transform.Window) compile(Cadence.CLOSE, c).left().transform()).lag()).isZero();
    }

    /** 장중 알림의 이력 피연산자는 현재 봉이 이미 직전 거래일이라 lag 0이다(§4.2). */
    @Test
    void 장중_알림의_윈도우는_lag_0이다() {
        Condition c = new Condition(op(IndicatorKey.PRICE, ID), OperatorKey.GT,
                Right.operand(op(IndicatorKey.HIGH, new Transform.Window(WindowFn.MAX, 20, null))), null);

        assertThat(lagOfRight(compile(Cadence.INTRADAY, c))).isZero();
    }

    @Test
    void 박스권_돌파는_폭_조건과_직전_최고가_돌파로_전개된다() {
        CompiledTrigger compiled = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.BOX_BREAKOUT,
                Map.of("window_days", new BigDecimal("20"), "max_range_pct", new BigDecimal("15"),
                        "direction", "up")), Cadence.CLOSE);

        assertThat(compiled.preset()).isEqualTo(PresetKey.BOX_BREAKOUT);
        assertThat(compiled.conditions()).containsExactly(
                new Condition(new Operand(IndicatorKey.RANGE_PCT, Map.of("n", 20), ID), OperatorKey.LTE,
                        Right.constant(new BigDecimal("15")), null),
                new Condition(new Operand(IndicatorKey.PRICE, Map.of(), ID), OperatorKey.GT,
                        Right.operand(new Operand(IndicatorKey.HIGH, Map.of(),
                                new Transform.Window(WindowFn.MAX, 20, 1))), null));
    }

    /** 순매수 전환은 "오늘 순매수이고 어제는 아니었다"로 컴파일한다(§5.3). */
    @Test
    void 순매수_전환은_어제_값을_따로_본다() {
        CompiledTrigger compiled = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.INVESTOR_TURN,
                Map.of("investor", "foreign", "side", "buy")), Cadence.CLOSE);

        assertThat(compiled.conditions()).containsExactly(
                new Condition(new Operand(IndicatorKey.FOREIGN_NET_BUY, Map.of(), ID), OperatorKey.GT,
                        Right.constant(BigDecimal.ZERO), null),
                new Condition(new Operand(IndicatorKey.FOREIGN_NET_BUY, Map.of(),
                        new Transform.Window(WindowFn.MAX, 1, 1)), OperatorKey.LTE,
                        Right.constant(BigDecimal.ZERO), null));
    }

    @Test
    void 연속_순매도는_음수_연속이다() {
        CompiledTrigger compiled = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.INVESTOR_STREAK,
                Map.of("investor", "institution", "side", "sell", "days", new BigDecimal("5"))), Cadence.CLOSE);

        assertThat(compiled.conditions()).containsExactly(
                new Condition(new Operand(IndicatorKey.INSTITUTION_NET_BUY, Map.of(), ID), OperatorKey.LT,
                        Right.constant(BigDecimal.ZERO), new Modifier.Streak(5)));
    }

    @Test
    void 프리셋의_빠진_값은_기본값으로_채운다() {
        CompiledTrigger compiled = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.RSI_ZONE,
                Map.of()), Cadence.CLOSE);

        assertThat(compiled.presetParams()).containsEntry("zone", "overbought");
        assertThat(compiled.conditions()).containsExactly(
                new Condition(new Operand(IndicatorKey.RSI, Map.of("n", 14), ID), OperatorKey.GTE,
                        Right.constant(new BigDecimal("70")), null));
    }

    @Test
    void 과매도의_기준값_기본은_30이다() {
        CompiledTrigger compiled = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.RSI_ZONE,
                Map.of("zone", "oversold")), Cadence.CLOSE);

        assertThat(compiled.conditions()).containsExactly(
                new Condition(new Operand(IndicatorKey.RSI, Map.of("n", 14), ID), OperatorKey.LTE,
                        Right.constant(new BigDecimal("30")), null));
    }

    @Test
    void 수익률_도달의_손실은_음수_기준이다() {
        CompiledTrigger compiled = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.PNL_REACH,
                Map.of("direction", "loss", "pct", new BigDecimal("10"))), Cadence.CLOSE);

        assertThat(compiled.conditions()).containsExactly(
                new Condition(new Operand(IndicatorKey.UNREALIZED_PNL_PCT, Map.of(), ID), OperatorKey.LTE,
                        Right.constant(new BigDecimal("-10")), null));
    }

    @Test
    void 같은_조건이면_프리셋이든_조립형이든_해시가_같다() {
        CompiledTrigger preset = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.PRICE_REACH,
                Map.of("direction", "up", "price", new BigDecimal("70000"))), Cadence.INTRADAY);
        CompiledTrigger composable = Compiler.compile(new TriggerSpec.Composable(List.of(
                new Condition(op(IndicatorKey.PRICE, ID), OperatorKey.GTE,
                        Right.constant(new BigDecimal("70000.00")), null))), Cadence.INTRADAY);

        assertThat(SpecHash.of(preset, Cadence.INTRADAY)).isEqualTo(SpecHash.of(composable, Cadence.INTRADAY))
                .hasSize(64);
        assertThat(SpecHash.of(preset, Cadence.CLOSE)).isNotEqualTo(SpecHash.of(preset, Cadence.INTRADAY));
    }

    private static Condition compile(Cadence cadence, Condition c) {
        return Compiler.compile(new TriggerSpec.Composable(List.of(c)), cadence).conditions().get(0);
    }

    private static int lagOfRight(Condition c) {
        return ((Transform.Window) c.right().operand().transform()).lag();
    }

    private static Operand op(IndicatorKey key, Transform t) { return new Operand(key, Map.of(), t); }
}
```

`src/test/java/com/stockproject/portfolio/alert/compile/RequiredBarsTest.java`:

```java
package com.stockproject.portfolio.alert.compile;

import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.catalog.WindowFn;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Right;
import com.stockproject.portfolio.alert.spec.Transform;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/** 필요 봉 수는 현재 봉을 포함해 센다(§5.4). */
class RequiredBarsTest {

    @Test
    void 지표별_필요_봉_수() {
        assertThat(RequiredBars.of(cmp(op(IndicatorKey.PRICE, Map.of())))).isEqualTo(1);
        assertThat(RequiredBars.of(cmp(op(IndicatorKey.CHANGE_PCT, Map.of())))).isEqualTo(2);
        assertThat(RequiredBars.of(cmp(op(IndicatorKey.VOLUME_RATIO, Map.of("n", 20))))).isEqualTo(21);
        assertThat(RequiredBars.of(cmp(op(IndicatorKey.RANGE_PCT, Map.of("n", 20))))).isEqualTo(21);
        assertThat(RequiredBars.of(cmp(op(IndicatorKey.SMA, Map.of("n", 120))))).isEqualTo(120);
        assertThat(RequiredBars.of(cmp(op(IndicatorKey.RSI, Map.of("n", 14))))).isEqualTo(15);
    }

    @Test
    void 변형과_교차와_연속을_더한다() {
        Operand window = new Operand(IndicatorKey.HIGH, Map.of(), new Transform.Window(WindowFn.MAX, 20, 1));
        Condition c = new Condition(op(IndicatorKey.PRICE, Map.of()), OperatorKey.GT, Right.operand(window), null);
        assertThat(RequiredBars.of(c)).isEqualTo(1 + 19 + 1);

        Operand delta = new Operand(IndicatorKey.SMA, Map.of("n", 5), new Transform.Delta(3));
        Condition cross = new Condition(delta, OperatorKey.CROSSES_ABOVE,
                Right.operand(op(IndicatorKey.SMA, Map.of("n", 20))), null);
        assertThat(RequiredBars.of(cross)).isEqualTo(Math.max(5 + 3, 20) + 1);

        Condition streak = new Condition(op(IndicatorKey.RSI, Map.of("n", 14)), OperatorKey.GTE,
                Right.constant(new BigDecimal("70")), new Modifier.Streak(3));
        assertThat(RequiredBars.of(streak)).isEqualTo(15 + 2);
    }

    /** 읽는 봉 수의 최대는 274다 — RSI 계산 창 250 + 변화량 5 + 연속 19(§5.4). */
    @Test
    void RSI는_계산_창만큼_읽는다() {
        Condition worst = new Condition(new Operand(IndicatorKey.RSI, Map.of("n", 30), new Transform.Delta(5)),
                OperatorKey.GTE, Right.constant(BigDecimal.ONE), new Modifier.Streak(20));
        assertThat(RequiredBars.toRead(worst)).isEqualTo(274);
        assertThat(RequiredBars.of(worst)).isEqualTo(31 + 5 + 19);
    }

    @Test
    void 수급의_최대_필요_봉_수는_30이다() {
        Operand window = new Operand(IndicatorKey.FOREIGN_NET_BUY, Map.of(), new Transform.Window(WindowFn.SUM, 10, 1));
        Condition c = new Condition(window, OperatorKey.LT,
                Right.operand(new Operand(IndicatorKey.FOREIGN_NET_BUY, Map.of(), new Transform.Identity())),
                new Modifier.Streak(20));
        assertThat(RequiredBars.of(c)).isEqualTo(30);
    }

    private static Condition cmp(Operand left) {
        return new Condition(left, OperatorKey.GTE, Right.constant(BigDecimal.ONE), null);
    }

    private static Operand op(IndicatorKey key, Map<String, Integer> params) {
        return new Operand(key, params, new Transform.Identity());
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.compile.*'`
Expected: FAIL — 컴파일 오류

- [ ] **Step 3: 컴파일러를 쓴다**

`alert/compile/CompiledTrigger.java`:

```java
package com.stockproject.portfolio.alert.compile;

import com.stockproject.portfolio.alert.catalog.PresetKey;
import com.stockproject.portfolio.alert.spec.Condition;

import java.util.List;
import java.util.Map;

/**
 * 평가할 수 있는 모양의 트리거. 모든 윈도우의 lag가 정해져 있다.
 * 프리셋이면 원래 키와 기본값까지 채운 파라미터를 함께 갖는다 — 문장 생성이 프리셋 틀을 쓴다.
 */
public record CompiledTrigger(List<Condition> conditions, PresetKey preset, Map<String, Object> presetParams) {

    public CompiledTrigger {
        conditions = List.copyOf(conditions);
        presetParams = presetParams == null ? Map.of() : Map.copyOf(presetParams);
    }
}
```

`alert/compile/Compiler.java`:

```java
package com.stockproject.portfolio.alert.compile;

import com.stockproject.portfolio.alert.catalog.AlertCatalog;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.catalog.PresetKey;
import com.stockproject.portfolio.alert.catalog.PresetParam;
import com.stockproject.portfolio.alert.catalog.WindowFn;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Right;
import com.stockproject.portfolio.alert.spec.Transform;
import com.stockproject.portfolio.alert.spec.TriggerSpec;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 트리거를 평가할 수 있는 모양으로 만든다.
 *
 * <p>프리셋은 스펙 §5.3 표대로 조립형 조건으로 전개한다. 사용자가 만든 조립형 조건은
 * 윈도우의 오늘 포함 여부(lag)를 맞은편으로 정한다(§4.2):
 * 맞은편이 오늘 값(지표 그대로·변화량·변화율)이면 오늘을 빼고(lag 1),
 * 다른 윈도우이거나 상수이면 오늘을 넣는다(lag 0). 장중 알림의 이력 피연산자는
 * 현재 봉이 이미 직전 거래일이라 lag 0이다.</p>
 */
public final class Compiler {

    private Compiler() { }

    private static final Transform ID = new Transform.Identity();

    public static CompiledTrigger compile(TriggerSpec trigger, Cadence cadence) {
        return switch (trigger) {
            case TriggerSpec.Composable c ->
                    new CompiledTrigger(c.conditions().stream().map(x -> resolveLag(x, cadence)).toList(), null, null);
            case TriggerSpec.PresetTrigger p -> {
                Map<String, Object> params = withDefaults(p.key(), p.params());
                yield new CompiledTrigger(expand(p.key(), params), p.key(), params);
            }
        };
    }

    public static Map<String, Object> withDefaults(PresetKey key, Map<String, Object> given) {
        Map<String, Object> out = new LinkedHashMap<>();
        for (PresetParam param : AlertCatalog.preset(key).params()) {
            Object value = given.get(param.key());
            if (value == null) {
                value = param.kind() == PresetParam.Kind.CHOICE ? param.defaultChoice() : param.defaultNumber();
            }
            if (value != null) out.put(param.key(), value);
        }
        // RSI 구간의 기준값 기본은 구간에 따라 다르다 — 과매수 70, 과매도 30 (§5.3)
        if (key == PresetKey.RSI_ZONE && given.get("level") == null && "oversold".equals(out.get("zone"))) {
            out.put("level", new BigDecimal("30"));
        }
        return out;
    }

    // ---- lag 결정 ------------------------------------------------------------

    private static Condition resolveLag(Condition c, Cadence cadence) {
        if (c.right().isConstant()) {
            return new Condition(lag(c.left(), 0), c.op(), c.right(), c.modifier());
        }
        Operand left = c.left();
        Operand right = c.right().operand();
        int leftLag = lagAgainst(right, cadence);
        int rightLag = lagAgainst(left, cadence);
        return new Condition(lag(left, leftLag), c.op(), Right.operand(lag(right, rightLag)), c.modifier());
    }

    /** 이 피연산자가 윈도우일 때, 맞은편(opposite)을 보고 정한 lag. */
    private static int lagAgainst(Operand opposite, Cadence cadence) {
        if (cadence == Cadence.INTRADAY) return 0;
        return opposite.transform() instanceof Transform.Window ? 0 : 1;
    }

    private static Operand lag(Operand operand, int value) {
        if (operand.transform() instanceof Transform.Window w) return operand.withTransform(w.withLag(value));
        return operand;
    }

    // ---- 프리셋 전개 (§5.3) --------------------------------------------------

    private static List<Condition> expand(PresetKey key, Map<String, Object> p) {
        List<Condition> out = new ArrayList<>();
        switch (key) {
            case PRICE_REACH -> out.add(compare(op(IndicatorKey.PRICE), up(p) ? OperatorKey.GTE : OperatorKey.LTE,
                    num(p, "price")));
            case CHANGE_MOVE -> out.add(compare(op(IndicatorKey.CHANGE_PCT),
                    up(p) ? OperatorKey.GTE : OperatorKey.LTE, up(p) ? num(p, "pct") : num(p, "pct").negate()));
            case VOLUME_SURGE -> out.add(compare(op(IndicatorKey.VOLUME_RATIO, "n", integer(p, "n")),
                    OperatorKey.GTE, num(p, "multiple")));
            case MA_CROSS -> out.add(new Condition(op(IndicatorKey.SMA, "n", integer(p, "short")),
                    "golden".equals(p.get("direction")) ? OperatorKey.CROSSES_ABOVE : OperatorKey.CROSSES_BELOW,
                    Right.operand(op(IndicatorKey.SMA, "n", integer(p, "long"))), null));
            case RSI_ZONE -> out.add(compare(op(IndicatorKey.RSI, "n", integer(p, "n")),
                    "overbought".equals(p.get("zone")) ? OperatorKey.GTE : OperatorKey.LTE, num(p, "level")));
            case BOX_BREAKOUT -> {
                int n = integer(p, "window_days");
                out.add(compare(op(IndicatorKey.RANGE_PCT, "n", n), OperatorKey.LTE, num(p, "max_range_pct")));
                boolean upward = up(p);
                Operand edge = new Operand(upward ? IndicatorKey.HIGH : IndicatorKey.LOW, Map.of(),
                        new Transform.Window(upward ? WindowFn.MAX : WindowFn.MIN, n, 1));
                out.add(new Condition(op(IndicatorKey.PRICE), upward ? OperatorKey.GT : OperatorKey.LT,
                        Right.operand(edge), null));
            }
            case INVESTOR_STREAK -> out.add(new Condition(op(investor(p)), buy(p) ? OperatorKey.GT : OperatorKey.LT,
                    Right.constant(BigDecimal.ZERO), new Modifier.Streak(integer(p, "days"))));
            case INVESTOR_TURN -> {
                IndicatorKey who = investor(p);
                boolean buy = buy(p);
                out.add(compare(op(who), buy ? OperatorKey.GT : OperatorKey.LT, BigDecimal.ZERO));
                Operand yesterday = new Operand(who, Map.of(),
                        new Transform.Window(buy ? WindowFn.MAX : WindowFn.MIN, 1, 1));
                out.add(compare(yesterday, buy ? OperatorKey.LTE : OperatorKey.GTE, BigDecimal.ZERO));
            }
            case PNL_REACH -> {
                boolean profit = "profit".equals(p.get("direction"));
                out.add(compare(op(IndicatorKey.UNREALIZED_PNL_PCT), profit ? OperatorKey.GTE : OperatorKey.LTE,
                        profit ? num(p, "pct") : num(p, "pct").negate()));
            }
        }
        return out;
    }

    private static Condition compare(Operand left, OperatorKey op, BigDecimal value) {
        return new Condition(left, op, Right.constant(value), null);
    }

    private static Operand op(IndicatorKey key) { return new Operand(key, Map.of(), ID); }

    private static Operand op(IndicatorKey key, String param, int value) {
        return new Operand(key, Map.of(param, value), ID);
    }

    private static boolean up(Map<String, Object> p) { return "up".equals(p.get("direction")); }
    private static boolean buy(Map<String, Object> p) { return "buy".equals(p.get("side")); }

    private static IndicatorKey investor(Map<String, Object> p) {
        return "institution".equals(p.get("investor")) ? IndicatorKey.INSTITUTION_NET_BUY : IndicatorKey.FOREIGN_NET_BUY;
    }

    private static BigDecimal num(Map<String, Object> p, String key) { return (BigDecimal) p.get(key); }
    private static int integer(Map<String, Object> p, String key) { return ((BigDecimal) p.get(key)).intValueExact(); }
}
```

`alert/compile/RequiredBars.java`:

```java
package com.stockproject.portfolio.alert.compile;

import com.stockproject.portfolio.alert.catalog.AlertCatalog;
import com.stockproject.portfolio.alert.catalog.Indicator;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.Scope;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Transform;

/**
 * 조건 하나가 필요로 하는 봉 수 (스펙 §5.4). 현재 봉을 포함해 센다.
 *
 * <pre>
 * 피연산자 = history(params) + 변형분(window: n − 1 + lag · delta·pct: n) + 교차 1
 * 조건     = 피연산자별 최댓값 + (streak − 1)
 * </pre>
 *
 * 판정 기준(of)과 읽을 양(toRead)이 다른 것은 RSI뿐이다 — 판정은 n+1봉이면 되지만
 * 같은 데이터에서 같은 값이 나오도록 250봉 계산 창을 읽는다(§5.1).
 */
public final class RequiredBars {

    private RequiredBars() { }

    public static final int RSI_WINDOW = 250;

    public static int of(Condition c) { return count(c, false); }

    public static int toRead(Condition c) { return count(c, true); }

    private static int count(Condition c, boolean reading) {
        int cross = c.op().isCross() ? 1 : 0;
        int left = operand(c.left(), reading) + cross;
        int right = c.right().isConstant() ? 0 : operand(c.right().operand(), reading) + cross;
        int streak = c.modifier() instanceof Modifier.Streak s ? s.n() - 1 : 0;
        return Math.max(left, right) + streak;
    }

    private static int operand(Operand o, boolean reading) {
        Indicator indicator = AlertCatalog.indicator(o.indicator());
        if (indicator.scope() == Scope.USER) return 0;
        int history = history(o, reading);
        return history + switch (o.transform()) {
            case Transform.Identity i -> 0;
            case Transform.Window w -> w.n() - 1 + w.lagOrZero();
            case Transform.Delta d -> d.n();
            case Transform.Pct p -> p.n();
        };
    }

    private static int history(Operand o, boolean reading) {
        Indicator indicator = AlertCatalog.indicator(o.indicator());
        IndicatorKey key = o.indicator();
        return switch (key) {
            case PRICE, VOLUME, HIGH, LOW, FOREIGN_NET_BUY, INSTITUTION_NET_BUY -> 1;
            case CHANGE_PCT -> 2;
            case VOLUME_RATIO, RANGE_PCT -> indicator.paramOrDefault(o.params(), "n") + 1;
            case SMA, DISPARITY -> indicator.paramOrDefault(o.params(), "n");
            case RSI -> reading ? RSI_WINDOW : indicator.paramOrDefault(o.params(), "n") + 1;
            case UNREALIZED_PNL_PCT, WEIGHT_PCT -> 0;
        };
    }
}
```

`alert/compile/SpecHash.java`:

```java
package com.stockproject.portfolio.alert.compile;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Transform;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.TreeMap;

/**
 * 컴파일한 조건과 평가 시점의 해시 (스펙 §6.6 · §6.7).
 *
 * <p>정규형은 조건 순서를 그대로 두고, 숫자는 꼬리 0을 떼고(70000 = 70000.00),
 * 파라미터는 이름순으로 쓴다. 프리셋으로 만든 것과 조립형으로 만든 것도 컴파일 결과가 같으면
 * 같은 해시가 나와 중복 경고가 성립한다.</p>
 */
public final class SpecHash {

    private SpecHash() { }

    public static String of(CompiledTrigger trigger, Cadence cadence) {
        StringBuilder sb = new StringBuilder(cadence.name());
        for (Condition c : trigger.conditions()) {
            sb.append('|').append(operand(c.left())).append(' ').append(c.op().key()).append(' ');
            sb.append(c.right().isConstant()
                    ? "const:" + c.right().constant().stripTrailingZeros().toPlainString()
                    : operand(c.right().operand()));
            sb.append(' ').append(switch (c.modifier()) {
                case null -> "-";
                case Modifier.Streak s -> "streak:" + s.n();
                case Modifier.PersistMin p -> "persist:" + p.minutes();
            });
        }
        return sha256(sb.toString());
    }

    private static String operand(Operand o) {
        return o.indicator().key() + new TreeMap<>(o.params()) + ":" + switch (o.transform()) {
            case Transform.Identity i -> "identity";
            case Transform.Window w -> "window:" + w.fn().key() + ":" + w.n() + ":" + w.lagOrZero();
            case Transform.Delta d -> "delta:" + d.n();
            case Transform.Pct p -> "pct:" + p.n();
        };
    }

    private static String sha256(String text) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
```

`switch`의 `case null`은 Java 21 패턴 매칭 문법이다.

- [ ] **Step 4: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.compile.*'`
Expected: PASS

- [ ] **Step 5: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/compile \
        src/test/java/com/stockproject/portfolio/alert/compile
git commit -m "feat: 프리셋 전개와 오늘 포함 규칙, 필요 봉 수, 조건 해시를 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 검증 — 스펙 §14를 한 곳에서

미리보기와 저장이 같은 규칙을 쓴다(§14). 검증기는 순수 함수다. 종목 정보와 "지금"은 호출하는 쪽이 넘긴다.

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/validation/` 아래 `InstrumentFacts.java` · `ExistingAlert.java` · `InvalidAlertException.java` · `AlertValidator.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/validation/AlertValidatorTest.java`

**Interfaces:**
- Consumes: Task 2 카탈로그, Task 3 `AlertDraft` · `FieldError`, Task 4 `Compiler.compile` · `Compiler.withDefaults`.
- Produces:
  - `record InstrumentFacts(Market market, String assetClass, boolean delisted, boolean held)` — `held`는 최신 확정 스냅샷에서 보유 중인가. 종목이 없으면 호출하는 쪽이 `null`을 넘긴다.
  - `record ExistingAlert(UUID instrumentId, String triggerType)` — 수정·수정 중 미리보기에서 원래 알림. 생성이면 `null`.
  - `final class InvalidAlertException extends RuntimeException` — `List<FieldError> fields()`.
  - `final class AlertValidator` — `static List<FieldError> validate(AlertDraft draft, InstrumentFacts instrument, ExistingAlert existing, OffsetDateTime now)`, `static void requireValid(...)`(같은 인자, 오류가 있으면 `InvalidAlertException`).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/validation/AlertValidatorTest.java`:

```java
package com.stockproject.portfolio.alert.validation;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.NotifyMode;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.catalog.PresetKey;
import com.stockproject.portfolio.alert.catalog.WindowFn;
import com.stockproject.portfolio.alert.spec.AlertDraft;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Right;
import com.stockproject.portfolio.alert.spec.Transform;
import com.stockproject.portfolio.alert.spec.TriggerSpec;
import com.stockproject.portfolio.domain.Market;
import org.assertj.core.groups.Tuple;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.groups.Tuple.tuple;

class AlertValidatorTest {

    private static final UUID SAMSUNG = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-27T10:00:00+09:00");
    private static final InstrumentFacts KR_HELD = new InstrumentFacts(Market.KR, "STOCK", false, true);
    private static final InstrumentFacts KR_NOT_HELD = new InstrumentFacts(Market.KR, "STOCK", false, false);
    private static final InstrumentFacts US_HELD = new InstrumentFacts(Market.US, "STOCK", false, true);
    private static final Transform ID = new Transform.Identity();

    @Test
    void 올바른_조립형_알림은_오류가_없다() {
        AlertDraft draft = composable(Cadence.INTRADAY, new Condition(op(IndicatorKey.PRICE, ID), OperatorKey.GT,
                Right.operand(op(IndicatorKey.HIGH, new Transform.Window(WindowFn.MAX, 20, null))),
                new Modifier.PersistMin(10)));

        assertThat(AlertValidator.validate(draft, KR_HELD, null, NOW)).isEmpty();
    }

    @Test
    void 봉투_규칙() {
        AlertDraft draft = new AlertDraft(SAMSUNG, "   ", Cadence.CLOSE, NotifyMode.COOLDOWN, 3,
                NOW.minusMinutes(1), priceReach());

        assertThat(codes(AlertValidator.validate(draft, KR_HELD, null, NOW))).containsExactly(
                tuple("name", "REQUIRED"),
                tuple("notify_mode", "CADENCE_NOT_ALLOWED"),
                tuple("cooldown_min", "OUT_OF_RANGE"),
                tuple("expires_at", "PAST"));
    }

    @Test
    void 이름은_40자까지다() {
        AlertDraft ok = new AlertDraft(SAMSUNG, "가".repeat(40), Cadence.CLOSE, NotifyMode.EDGE_REARM,
                null, null, priceReach());
        AlertDraft tooLong = new AlertDraft(SAMSUNG, "가".repeat(41), Cadence.CLOSE, NotifyMode.EDGE_REARM,
                null, null, priceReach());

        assertThat(AlertValidator.validate(ok, KR_HELD, null, NOW)).isEmpty();
        assertThat(codes(AlertValidator.validate(tooLong, KR_HELD, null, NOW)))
                .containsExactly(tuple("name", "OUT_OF_RANGE"));
    }

    @Test
    void 쿨다운이_아닌데_쿨다운_분이_있으면_거부한다() {
        AlertDraft draft = new AlertDraft(SAMSUNG, "x", Cadence.INTRADAY, NotifyMode.EDGE_REARM, 30,
                null, priceReach());

        assertThat(codes(AlertValidator.validate(draft, KR_HELD, null, NOW)))
                .containsExactly(tuple("cooldown_min", "INVALID_VALUE"));
    }

    @Test
    void 없는_종목_예수금_상장폐지는_같은_오류다() {
        AlertDraft draft = new AlertDraft(SAMSUNG, "x", Cadence.CLOSE, NotifyMode.EDGE_REARM, null, null, priceReach());

        assertThat(codes(AlertValidator.validate(draft, null, null, NOW)))
                .containsExactly(tuple("instrument_id", "UNKNOWN_INSTRUMENT"));
        assertThat(codes(AlertValidator.validate(draft, new InstrumentFacts(Market.KR, "CASH", false, true), null, NOW)))
                .containsExactly(tuple("instrument_id", "UNKNOWN_INSTRUMENT"));
        assertThat(codes(AlertValidator.validate(draft, new InstrumentFacts(Market.KR, "STOCK", true, false), null, NOW)))
                .containsExactly(tuple("instrument_id", "UNKNOWN_INSTRUMENT"));
    }

    @Test
    void 조건은_1개에서_5개다() {
        Condition c = new Condition(op(IndicatorKey.PRICE, ID), OperatorKey.GTE, Right.constant(BigDecimal.ONE), null);

        assertThat(codes(AlertValidator.validate(composable(Cadence.CLOSE), KR_HELD, null, NOW)))
                .containsExactly(tuple("trigger_spec.conditions", "OUT_OF_RANGE"));
        assertThat(codes(AlertValidator.validate(composable(Cadence.CLOSE, Collections.nCopies(6, c)
                .toArray(Condition[]::new)), KR_HELD, null, NOW)))
                .containsExactly(tuple("trigger_spec.conditions", "OUT_OF_RANGE"));
    }

    @Test
    void 지표_파라미터와_변형의_범위() {
        Condition c = new Condition(
                new Operand(IndicatorKey.RSI, Map.of("n", 31), new Transform.Window(WindowFn.MAX, 5, null)),
                OperatorKey.GTE, Right.constant(new BigDecimal("70")), null);
        Condition d = new Condition(
                new Operand(IndicatorKey.SMA, Map.of("m", 5), new Transform.Delta(121)),
                OperatorKey.GTE, Right.constant(BigDecimal.ONE), null);

        assertThat(codes(AlertValidator.validate(composable(Cadence.CLOSE, c, d), KR_HELD, null, NOW))).containsExactly(
                tuple("trigger_spec.conditions[0].left.indicator_params.n", "OUT_OF_RANGE"),
                tuple("trigger_spec.conditions[0].left.transform", "TRANSFORM_NOT_ALLOWED"),
                tuple("trigger_spec.conditions[1].left.indicator_params.m", "INVALID_VALUE"),
                tuple("trigger_spec.conditions[1].left.transform.n", "OUT_OF_RANGE"));
    }

    @Test
    void 수급_윈도우는_10봉까지다() {
        Condition c = new Condition(
                new Operand(IndicatorKey.FOREIGN_NET_BUY, Map.of(), new Transform.Window(WindowFn.SUM, 11, null)),
                OperatorKey.GTE, Right.constant(BigDecimal.ONE), null);

        assertThat(codes(AlertValidator.validate(composable(Cadence.CLOSE, c), KR_HELD, null, NOW)))
                .containsExactly(tuple("trigger_spec.conditions[0].left.transform.n", "OUT_OF_RANGE"));
    }

    @Test
    void 국내_전용_지표는_미국_종목에_쓸_수_없다() {
        Condition c = new Condition(op(IndicatorKey.FOREIGN_NET_BUY, ID), OperatorKey.GT,
                Right.constant(BigDecimal.ZERO), null);

        assertThat(codes(AlertValidator.validate(composable(Cadence.CLOSE, c), US_HELD, null, NOW)))
                .containsExactly(tuple("trigger_spec.conditions[0].left.indicator", "MARKET_NOT_SUPPORTED"));
    }

    /** 단위는 변형 뒤의 단위다 — pct는 percent(§14.2). */
    @Test
    void 두_피연산자의_단위가_달라야_거부한다() {
        Condition bad = new Condition(op(IndicatorKey.PRICE, ID), OperatorKey.GT,
                Right.operand(op(IndicatorKey.VOLUME, ID)), null);
        Condition ok = new Condition(op(IndicatorKey.PRICE, new Transform.Pct(5)), OperatorKey.GT,
                Right.operand(op(IndicatorKey.CHANGE_PCT, ID)), null);

        assertThat(codes(AlertValidator.validate(composable(Cadence.CLOSE, bad, ok), KR_HELD, null, NOW)))
                .containsExactly(tuple("trigger_spec.conditions[0].right", "UNIT_MISMATCH"));
    }

    @Test
    void 교차는_지표와_견주고_유지_조건을_붙일_수_없다() {
        Condition constant = new Condition(op(IndicatorKey.PRICE, ID), OperatorKey.CROSSES_ABOVE,
                Right.constant(BigDecimal.ONE), null);
        Condition withStreak = new Condition(sma(5), OperatorKey.CROSSES_ABOVE,
                Right.operand(sma(20)), new Modifier.Streak(2));

        assertThat(codes(AlertValidator.validate(composable(Cadence.CLOSE, constant, withStreak), KR_HELD, null, NOW)))
                .containsExactly(
                        tuple("trigger_spec.conditions[0].right", "OPERATOR_NOT_ALLOWED"),
                        tuple("trigger_spec.conditions[1].modifier", "MODIFIER_NOT_ALLOWED"));
    }

    @Test
    void 장중_알림의_왼쪽은_장중_지표_그대로다() {
        Condition sma = new Condition(sma(5), OperatorKey.GT, Right.constant(BigDecimal.ONE), null);
        Condition windowed = new Condition(op(IndicatorKey.PRICE, new Transform.Delta(1)), OperatorKey.GT,
                Right.constant(BigDecimal.ONE), null);

        assertThat(codes(AlertValidator.validate(composable(Cadence.INTRADAY, sma, windowed), KR_HELD, null, NOW)))
                .containsExactly(
                        tuple("trigger_spec.conditions[0].left.indicator", "CADENCE_NOT_ALLOWED"),
                        tuple("trigger_spec.conditions[1].left.transform", "CADENCE_NOT_ALLOWED"));
    }

    @Test
    void 유지_조건은_평가_시점에_맞아야_한다() {
        Condition persistOnClose = new Condition(op(IndicatorKey.PRICE, ID), OperatorKey.GT,
                Right.constant(BigDecimal.ONE), new Modifier.PersistMin(10));
        Condition longStreak = new Condition(op(IndicatorKey.PRICE, ID), OperatorKey.GT,
                Right.constant(BigDecimal.ONE), new Modifier.Streak(21));
        assertThat(codes(AlertValidator.validate(composable(Cadence.CLOSE, persistOnClose, longStreak),
                KR_HELD, null, NOW))).containsExactly(
                tuple("trigger_spec.conditions[0].modifier", "MODIFIER_NOT_ALLOWED"),
                tuple("trigger_spec.conditions[1].modifier.streak", "OUT_OF_RANGE"));

        Condition shortPersist = new Condition(op(IndicatorKey.PRICE, ID), OperatorKey.GT,
                Right.constant(BigDecimal.ONE), new Modifier.PersistMin(4));
        assertThat(codes(AlertValidator.validate(composable(Cadence.INTRADAY, shortPersist), KR_HELD, null, NOW)))
                .containsExactly(tuple("trigger_spec.conditions[0].modifier.persist_min", "OUT_OF_RANGE"));
    }

    @Test
    void 사용자_상태_지표의_규칙() {
        Condition pnl = new Condition(op(IndicatorKey.UNREALIZED_PNL_PCT, ID), OperatorKey.GTE,
                Right.constant(BigDecimal.TEN), new Modifier.Streak(2));
        Condition price = new Condition(op(IndicatorKey.PRICE, ID), OperatorKey.GT, Right.constant(BigDecimal.ONE), null);

        assertThat(codes(AlertValidator.validate(composable(Cadence.CLOSE, pnl, price), KR_HELD, null, NOW)))
                .containsExactly(
                        tuple("trigger_spec.conditions[0].modifier", "MODIFIER_NOT_ALLOWED"),
                        tuple("trigger_spec", "SCOPE_MIXED"));
    }

    /** 보유는 만들 때만 묻는다 — 수정·다시 켜기는 묻지 않는다(§14.1). */
    @Test
    void 사용자_상태_조건은_만들_때_보유해야_한다() {
        AlertDraft draft = new AlertDraft(SAMSUNG, "x", Cadence.CLOSE, NotifyMode.EDGE_REARM, null, null,
                new TriggerSpec.PresetTrigger(PresetKey.PNL_REACH, Map.of("pct", BigDecimal.TEN)));

        assertThat(codes(AlertValidator.validate(draft, KR_NOT_HELD, null, NOW)))
                .containsExactly(tuple("instrument_id", "NOT_HELD"));
        assertThat(AlertValidator.validate(draft, KR_NOT_HELD, new ExistingAlert(SAMSUNG, "PRESET"), NOW)).isEmpty();
    }

    @Test
    void 사용자_상태_조건은_종가_알림만이다() {
        AlertDraft draft = new AlertDraft(SAMSUNG, "x", Cadence.INTRADAY, NotifyMode.EDGE_REARM, null, null,
                new TriggerSpec.Composable(List.of(new Condition(op(IndicatorKey.WEIGHT_PCT, ID), OperatorKey.GTE,
                        Right.constant(BigDecimal.TEN), null))));

        assertThat(codes(AlertValidator.validate(draft, KR_HELD, null, NOW))).containsExactly(
                tuple("trigger_spec.conditions[0].left.indicator", "CADENCE_NOT_ALLOWED"));
    }

    @Test
    void 프리셋의_평가_시점_시장_파라미터() {
        AlertDraft intradayBox = new AlertDraft(SAMSUNG, "x", Cadence.INTRADAY, NotifyMode.EDGE_REARM, null, null,
                new TriggerSpec.PresetTrigger(PresetKey.BOX_BREAKOUT, Map.of()));
        assertThat(codes(AlertValidator.validate(intradayBox, KR_HELD, null, NOW)))
                .containsExactly(tuple("cadence", "CADENCE_NOT_ALLOWED"));

        AlertDraft usFlow = new AlertDraft(SAMSUNG, "x", Cadence.CLOSE, NotifyMode.EDGE_REARM, null, null,
                new TriggerSpec.PresetTrigger(PresetKey.INVESTOR_TURN, Map.of()));
        assertThat(codes(AlertValidator.validate(usFlow, US_HELD, null, NOW)))
                .containsExactly(tuple("trigger_spec.preset_key", "MARKET_NOT_SUPPORTED"));

        AlertDraft badParams = new AlertDraft(SAMSUNG, "x", Cadence.CLOSE, NotifyMode.EDGE_REARM, null, null,
                new TriggerSpec.PresetTrigger(PresetKey.PRICE_REACH, Map.of("direction", "sideways")));
        assertThat(codes(AlertValidator.validate(badParams, KR_HELD, null, NOW))).containsExactly(
                tuple("trigger_spec.params.direction", "INVALID_VALUE"),
                tuple("trigger_spec.params.price", "REQUIRED"));

        AlertDraft streak = new AlertDraft(SAMSUNG, "x", Cadence.CLOSE, NotifyMode.EDGE_REARM, null, null,
                new TriggerSpec.PresetTrigger(PresetKey.INVESTOR_STREAK, Map.of("days", new BigDecimal("21"))));
        assertThat(codes(AlertValidator.validate(streak, KR_HELD, null, NOW)))
                .containsExactly(tuple("trigger_spec.params.days", "OUT_OF_RANGE"));
    }

    @Test
    void 수정에서는_종목과_트리거_종류를_바꿀_수_없다() {
        AlertDraft draft = new AlertDraft(SAMSUNG, "x", Cadence.CLOSE, NotifyMode.EDGE_REARM, null, null, priceReach());
        ExistingAlert other = new ExistingAlert(UUID.fromString("10000000-0000-0000-0000-000000000002"), "COMPOSABLE");

        assertThat(codes(AlertValidator.validate(draft, KR_HELD, other, NOW))).containsExactly(
                tuple("instrument_id", "IMMUTABLE"),
                tuple("trigger_type", "IMMUTABLE"));
    }

    @Test
    void 오류가_있으면_예외로_돌려준다() {
        AlertDraft draft = new AlertDraft(SAMSUNG, "", Cadence.CLOSE, NotifyMode.EDGE_REARM, null, null, priceReach());

        assertThatThrownBy(() -> AlertValidator.requireValid(draft, KR_HELD, null, NOW))
                .isInstanceOfSatisfying(InvalidAlertException.class,
                        e -> assertThat(e.fields()).extracting(FieldError::path).containsExactly("name"));
    }

    private static TriggerSpec priceReach() {
        return new TriggerSpec.PresetTrigger(PresetKey.PRICE_REACH,
                Map.of("direction", "up", "price", new BigDecimal("70000")));
    }

    private static AlertDraft composable(Cadence cadence, Condition... conditions) {
        return new AlertDraft(SAMSUNG, "x", cadence, NotifyMode.EDGE_REARM, null, null,
                new TriggerSpec.Composable(List.of(conditions)));
    }

    private static Operand op(IndicatorKey key, Transform t) { return new Operand(key, Map.of(), t); }

    private static Operand sma(int n) { return new Operand(IndicatorKey.SMA, Map.of("n", n), ID); }

    private static List<Tuple> codes(List<FieldError> errors) {
        return errors.stream().map(e -> tuple(e.path(), e.code())).toList();
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.validation.AlertValidatorTest'`
Expected: FAIL — 컴파일 오류

- [ ] **Step 3: 포트와 예외를 쓴다**

`alert/validation/InstrumentFacts.java`:

```java
package com.stockproject.portfolio.alert.validation;

import com.stockproject.portfolio.domain.Market;

/**
 * 검증이 종목에 대해 알아야 하는 것. held는 최신 확정 스냅샷에서 이 사용자가 보유 중인가다.
 * 종목 마스터에 없으면 호출하는 쪽이 null을 넘긴다.
 */
public record InstrumentFacts(Market market, String assetClass, boolean delisted, boolean held) {

    public boolean alertable() { return !"CASH".equals(assetClass) && !delisted; }
}
```

`alert/validation/ExistingAlert.java`:

```java
package com.stockproject.portfolio.alert.validation;

import java.util.UUID;

/** 수정 대상 알림의 바꿀 수 없는 값. 생성이면 없다(null). */
public record ExistingAlert(UUID instrumentId, String triggerType) { }
```

`alert/validation/InvalidAlertException.java`:

```java
package com.stockproject.portfolio.alert.validation;

import java.util.List;

/** 저장 검증 실패. API가 400 INVALID_ALERT와 fields로 옮긴다(스펙 §11.4). */
public final class InvalidAlertException extends RuntimeException {

    private final List<FieldError> fields;

    public InvalidAlertException(List<FieldError> fields) {
        super("알림 검증 실패: " + fields.size() + "건");
        this.fields = List.copyOf(fields);
    }

    public List<FieldError> fields() { return fields; }
}
```

- [ ] **Step 4: 검증기를 쓴다**

`alert/validation/AlertValidator.java`:

```java
package com.stockproject.portfolio.alert.validation;

import com.stockproject.portfolio.alert.catalog.AlertCatalog;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.Indicator;
import com.stockproject.portfolio.alert.catalog.NotifyMode;
import com.stockproject.portfolio.alert.catalog.ParamSpec;
import com.stockproject.portfolio.alert.catalog.Preset;
import com.stockproject.portfolio.alert.catalog.PresetParam;
import com.stockproject.portfolio.alert.catalog.Scope;
import com.stockproject.portfolio.alert.catalog.TransformRule;
import com.stockproject.portfolio.alert.catalog.TransformType;
import com.stockproject.portfolio.alert.catalog.Unit;
import com.stockproject.portfolio.alert.compile.Compiler;
import com.stockproject.portfolio.alert.spec.AlertDraft;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Transform;
import com.stockproject.portfolio.alert.spec.TriggerSpec;
import com.stockproject.portfolio.domain.Market;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 저장 전 관문 (스펙 §14). 미리보기와 저장이 같은 규칙을 쓴다.
 *
 * <p>오류는 첫 오류에서 멈추지 않고 모은다 — 폼이 칸마다 한 번에 띄운다.
 * 프리셋은 입력 칸을 검사한 뒤 컴파일 결과에 조립형 규칙을 적용하고,
 * 거기서 나온 오류는 사용자가 고칠 칸이 없으므로 trigger_spec에 단다.</p>
 */
public final class AlertValidator {

    private AlertValidator() { }

    private static final int NAME_MAX = 40;
    private static final int CONDITIONS_MAX = 5;
    private static final int COOLDOWN_MIN = 5;
    private static final int COOLDOWN_MAX = 1440;
    private static final int PERSIST_MIN = 5;
    private static final int PERSIST_MAX = 60;
    private static final int STREAK_MIN = 1;
    private static final int STREAK_MAX = 20;

    public static void requireValid(AlertDraft draft, InstrumentFacts instrument, ExistingAlert existing,
                                    OffsetDateTime now) {
        List<FieldError> errors = validate(draft, instrument, existing, now);
        if (!errors.isEmpty()) throw new InvalidAlertException(errors);
    }

    public static List<FieldError> validate(AlertDraft draft, InstrumentFacts instrument, ExistingAlert existing,
                                            OffsetDateTime now) {
        List<FieldError> errors = new ArrayList<>();
        envelope(draft, instrument, existing, now, errors);

        Market market = instrument != null && instrument.alertable() ? instrument.market() : null;
        boolean userScope = switch (draft.trigger()) {
            case TriggerSpec.Composable c -> composable(c.conditions(), draft.cadence(), market,
                    "trigger_spec", false, errors);
            case TriggerSpec.PresetTrigger p -> preset(p, draft.cadence(), market, errors);
        };

        if (userScope && existing == null && market != null && !instrument.held()) {
            errors.add(new FieldError("instrument_id", "NOT_HELD", "보유한 종목에만 걸 수 있어요"));
        }
        return errors;
    }

    // ---- 봉투 (§14.1) ----------------------------------------------------------

    private static void envelope(AlertDraft d, InstrumentFacts instrument, ExistingAlert existing,
                                 OffsetDateTime now, List<FieldError> errors) {
        if (instrument == null || !instrument.alertable()) {
            errors.add(new FieldError("instrument_id", "UNKNOWN_INSTRUMENT", "알림을 걸 수 없는 종목이에요"));
        }
        if (existing != null) {
            if (!existing.instrumentId().equals(d.instrumentId())) {
                errors.add(new FieldError("instrument_id", "IMMUTABLE", "종목은 바꿀 수 없어요"));
            }
            if (!existing.triggerType().equals(d.trigger().typeName())) {
                errors.add(new FieldError("trigger_type", "IMMUTABLE", "조건 종류는 바꿀 수 없어요"));
            }
        }

        String name = d.name().strip();
        if (name.isEmpty()) {
            errors.add(new FieldError("name", "REQUIRED", "이름을 입력해 주세요"));
        } else if (name.codePointCount(0, name.length()) > NAME_MAX) {
            errors.add(new FieldError("name", "OUT_OF_RANGE", "이름은 40자까지예요"));
        }

        if (d.notifyMode() == NotifyMode.COOLDOWN) {
            if (d.cadence() != Cadence.INTRADAY) {
                errors.add(new FieldError("notify_mode", "CADENCE_NOT_ALLOWED", "다시 알림 간격은 장중 알림에만 있어요"));
            }
            if (d.cooldownMin() == null) {
                errors.add(new FieldError("cooldown_min", "REQUIRED", "간격을 골라 주세요"));
            } else if (d.cooldownMin() < COOLDOWN_MIN || d.cooldownMin() > COOLDOWN_MAX) {
                errors.add(new FieldError("cooldown_min", "OUT_OF_RANGE", "간격은 5분에서 24시간 사이예요"));
            }
        } else if (d.cooldownMin() != null) {
            errors.add(new FieldError("cooldown_min", "INVALID_VALUE", "간격은 다시 알림 간격을 고를 때만 정해요"));
        }

        if (d.expiresAt() != null && !d.expiresAt().isAfter(now)) {
            errors.add(new FieldError("expires_at", "PAST", "지난 시각은 고를 수 없어요"));
        }
    }

    // ---- 조립형 (§14.2) ---------------------------------------------------------

    /** 조건들을 검사하고, 사용자 상태 지표를 쓰는지 돌려준다. compiled면 오류를 trigger_spec에 단다. */
    private static boolean composable(List<Condition> conditions, Cadence cadence, Market market,
                                      String root, boolean compiled, List<FieldError> errors) {
        String listPath = root + ".conditions";
        if (conditions.isEmpty() || conditions.size() > CONDITIONS_MAX) {
            errors.add(new FieldError(compiled ? root : listPath, "OUT_OF_RANGE", "조건은 1개에서 5개까지예요"));
            return false;
        }
        Set<Scope> scopes = EnumSet.noneOf(Scope.class);
        for (int i = 0; i < conditions.size(); i++) {
            String path = compiled ? root : listPath + "[" + i + "]";
            condition(conditions.get(i), cadence, market, path, compiled, scopes, errors);
        }
        if (scopes.size() > 1) {
            errors.add(new FieldError(root, "SCOPE_MIXED", "내 보유 조건과 시세 조건은 함께 쓸 수 없어요"));
        }
        return scopes.contains(Scope.USER);
    }

    private static void condition(Condition c, Cadence cadence, Market market, String path, boolean compiled,
                                  Set<Scope> scopes, List<FieldError> errors) {
        Indicator left = AlertCatalog.indicator(c.left().indicator());
        scopes.add(left.scope());
        operand(c.left(), market, cadence, sub(path, ".left", compiled), compiled, errors);

        if (cadence == Cadence.INTRADAY && left.scope() == Scope.MARKET) {
            if (!left.intradayLeft()) {
                errors.add(new FieldError(sub(path, ".left.indicator", compiled), "CADENCE_NOT_ALLOWED",
                        "장중 알림에서는 가격·등락률·거래량·거래량 배수만 볼 수 있어요"));
            } else if (!(c.left().transform() instanceof Transform.Identity)) {
                errors.add(new FieldError(sub(path, ".left.transform", compiled), "CADENCE_NOT_ALLOWED",
                        "장중 알림의 왼쪽은 지표 그대로만 쓸 수 있어요"));
            }
        }

        boolean opAllowed = left.operators().contains(c.op());
        if (!c.right().isConstant()) {
            Indicator right = AlertCatalog.indicator(c.right().operand().indicator());
            scopes.add(right.scope());
            operand(c.right().operand(), market, cadence, sub(path, ".right", compiled), compiled, errors);
            opAllowed &= right.operators().contains(c.op());
            if (unitOf(c.left()) != unitOf(c.right().operand())) {
                errors.add(new FieldError(sub(path, ".right", compiled), "UNIT_MISMATCH",
                        "단위가 다른 값끼리는 견줄 수 없어요"));
            }
        }
        if (!opAllowed) {
            errors.add(new FieldError(sub(path, ".op", compiled), "OPERATOR_NOT_ALLOWED", "이 지표에 쓸 수 없는 비교예요"));
        } else if (c.op().isCross() && c.right().isConstant()) {
            errors.add(new FieldError(sub(path, ".right", compiled), "OPERATOR_NOT_ALLOWED",
                    "돌파·이탈은 다른 지표와 견줄 때만 써요"));
        }

        modifier(c, left, cadence, sub(path, ".modifier", compiled), errors);
    }

    private static void modifier(Condition c, Indicator left, Cadence cadence, String path,
                                 List<FieldError> errors) {
        if (c.modifier() == null) return;
        boolean user = left.scope() == Scope.USER || (!c.right().isConstant()
                && AlertCatalog.indicator(c.right().operand().indicator()).scope() == Scope.USER);
        if (c.op().isCross() || user) {
            errors.add(new FieldError(path, "MODIFIER_NOT_ALLOWED", "이 조건에는 유지 조건을 붙일 수 없어요"));
            return;
        }
        switch (c.modifier()) {
            case Modifier.Streak s -> {
                if (cadence != Cadence.CLOSE) {
                    errors.add(new FieldError(path, "MODIFIER_NOT_ALLOWED", "장중 알림에는 연속 N일을 쓸 수 없어요"));
                } else if (s.n() < STREAK_MIN || s.n() > STREAK_MAX) {
                    errors.add(new FieldError(path + ".streak", "OUT_OF_RANGE", "연속 일수는 1일에서 20일 사이예요"));
                }
            }
            case Modifier.PersistMin p -> {
                if (cadence != Cadence.INTRADAY) {
                    errors.add(new FieldError(path, "MODIFIER_NOT_ALLOWED", "종가 알림에는 N분 지속을 쓸 수 없어요"));
                } else if (p.minutes() < PERSIST_MIN || p.minutes() > PERSIST_MAX) {
                    errors.add(new FieldError(path + ".persist_min", "OUT_OF_RANGE", "지속 시간은 5분에서 60분 사이예요"));
                }
            }
        }
    }

    private static void operand(Operand o, Market market, Cadence cadence, String path, boolean compiled,
                                List<FieldError> errors) {
        Indicator indicator = AlertCatalog.indicator(o.indicator());
        if (market != null && !indicator.markets().contains(market)) {
            errors.add(new FieldError(sub(path, ".indicator", compiled), "MARKET_NOT_SUPPORTED",
                    "이 종목의 시장에서는 쓸 수 없는 지표예요"));
        }
        if (indicator.scope() == Scope.USER && cadence != Cadence.CLOSE) {
            errors.add(new FieldError(sub(path, ".indicator", compiled), "CADENCE_NOT_ALLOWED",
                    "내 보유 조건은 종가 알림에만 쓸 수 있어요"));
        }
        for (Map.Entry<String, Integer> e : o.params().entrySet()) {
            ParamSpec spec = indicator.param(e.getKey());
            String paramPath = sub(path, ".indicator_params." + e.getKey(), compiled);
            if (spec == null) {
                errors.add(new FieldError(paramPath, "INVALID_VALUE", "이 지표에 없는 설정이에요"));
            } else if (e.getValue() < spec.min() || e.getValue() > spec.max()) {
                errors.add(new FieldError(paramPath, "OUT_OF_RANGE",
                        "기간은 " + spec.min() + "에서 " + spec.max() + " 사이예요"));
            }
        }
        TransformRule rule = indicator.rule(o.transform().type());
        if (rule == null) {
            errors.add(new FieldError(sub(path, ".transform", compiled), "TRANSFORM_NOT_ALLOWED",
                    "이 지표에 쓸 수 없는 변형이에요"));
            return;
        }
        int n = switch (o.transform()) {
            case Transform.Identity i -> 0;
            case Transform.Window w -> w.n();
            case Transform.Delta d -> d.n();
            case Transform.Pct p -> p.n();
        };
        if (n < rule.nMin() || n > rule.nMax()) {
            errors.add(new FieldError(sub(path, ".transform.n", compiled), "OUT_OF_RANGE",
                    "기간은 " + rule.nMin() + "에서 " + rule.nMax() + " 사이예요"));
        }
    }

    /** 변형 뒤의 단위 (§14.2) — pct는 percent, 나머지는 지표 단위 그대로. */
    private static Unit unitOf(Operand o) {
        return o.transform().type() == TransformType.PCT ? Unit.PERCENT : AlertCatalog.indicator(o.indicator()).unit();
    }

    private static String sub(String path, String suffix, boolean compiled) {
        return compiled ? path : path + suffix;
    }

    // ---- 프리셋 (§14.3) ---------------------------------------------------------

    private static boolean preset(TriggerSpec.PresetTrigger p, Cadence cadence, Market market,
                                  List<FieldError> errors) {
        Preset preset = AlertCatalog.preset(p.key());
        int before = errors.size();
        if (!preset.cadences().contains(cadence)) {
            errors.add(new FieldError("cadence", "CADENCE_NOT_ALLOWED", "이 조건은 종가 알림으로만 쓸 수 있어요"));
        }
        if (market != null && !preset.markets().contains(market)) {
            errors.add(new FieldError("trigger_spec.preset_key", "MARKET_NOT_SUPPORTED",
                    "이 종목의 시장에서는 쓸 수 없는 조건이에요"));
        }

        for (PresetParam param : preset.params()) {
            String path = "trigger_spec.params." + param.key();
            Object value = p.params().get(param.key());
            if (value == null) {
                if (param.required()) errors.add(new FieldError(path, "REQUIRED", "값을 입력해 주세요"));
                continue;
            }
            if (param.kind() == PresetParam.Kind.CHOICE) {
                if (!param.choices().contains(value)) {
                    errors.add(new FieldError(path, "INVALID_VALUE", "고를 수 없는 값이에요"));
                }
                continue;
            }
            BigDecimal number = (BigDecimal) value;
            if (number.compareTo(param.min()) < 0 || number.compareTo(param.max()) > 0) {
                errors.add(new FieldError(path, "OUT_OF_RANGE",
                        param.min().toPlainString() + "에서 " + param.max().toPlainString() + " 사이로 입력해 주세요"));
            }
        }
        boolean user = preset.scope() == Scope.USER;
        if (errors.size() > before) return user;

        // 입력이 맞으면 컴파일 결과에 조립형 규칙을 적용한다(§14.3)
        List<Condition> compiled = Compiler.compile(p, cadence).conditions();
        composable(compiled, cadence, market, "trigger_spec", true, errors);
        return user;
    }
}
```

`Compiler.compile`은 필수 값이 빠진 프리셋을 컴파일하지 못한다(가격 도달의 가격). 그래서 프리셋 자체의 검사(평가 시점·시장·입력 칸)를 통과했을 때만 부른다 — 통과하지 못했는데 컴파일 결과까지 검사하면 같은 원인이 `trigger_spec`에 한 번 더 붙는다. 사용자 상태 지표의 장중 검사도 같은 이유로 한 번만 단다.

- [ ] **Step 5: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.validation.*'`
Expected: PASS

- [ ] **Step 6: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/validation \
        src/test/java/com/stockproject/portfolio/alert/validation
git commit -m "feat: 알림 검증 규칙을 한 곳에 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 지표 계산 — 봉 계열 위의 순수 함수

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/indicator/` 아래 `Bar.java` · `FlowBar.java` · `Snapshot.java` · `Holding.java` · `Series.java` · `IndicatorCalculator.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/indicator/SeriesFixtures.java` · `IndicatorCalculatorTest.java`

**Interfaces:**
- Consumes: Task 2 카탈로그, Task 3 `Operand` · `Transform`, Task 4 `RequiredBars.RSI_WINDOW`.
- Produces:
  - `record Bar(LocalDate date, BigDecimal open, BigDecimal high, BigDecimal low, BigDecimal close, BigDecimal volume)`
  - `record FlowBar(LocalDate date, BigDecimal foreign, BigDecimal institution)`
  - `record Snapshot(OffsetDateTime at, BigDecimal price, BigDecimal cumVolume)`
  - `record Holding(BigDecimal unrealizedPnlPct, BigDecimal weightPct, boolean carriedForward)`
  - `record Series(List<Bar> bars, List<FlowBar> flows, List<Snapshot> snapshots, Holding holding)` — 전부 날짜·시각 오름차순. 종가 알림은 마지막 봉이 현재 봉이다. 장중 알림은 마지막 봉이 직전 거래 봉이고, `snapshots`가 그날의 장중 스냅샷이다. `Series.empty()`.
  - `final class IndicatorCalculator` — `static BigDecimal value(Operand o, Series s, Cadence cadence, int shift)`. `shift`는 현재 시점에서 몇 시점 앞인가(연속·교차). 계산할 봉이 모자라면 `null`.
  - 테스트 픽스처 `SeriesFixtures`(public) — Task 7 테스트도 쓴다.

- [ ] **Step 1: 테스트 픽스처를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/indicator/SeriesFixtures.java`:

```java
package com.stockproject.portfolio.alert.indicator;

import java.math.BigDecimal;
import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;

/** 평일을 거래일로 세는 봉 계열 픽스처. day(0)은 2026-06-01(월)이다. */
public final class SeriesFixtures {

    private SeriesFixtures() { }

    public static final LocalDate START = LocalDate.of(2026, 6, 1);

    public static LocalDate day(int index) {
        LocalDate d = START;
        int seen = 0;
        while (true) {
            if (d.getDayOfWeek() != DayOfWeek.SATURDAY && d.getDayOfWeek() != DayOfWeek.SUNDAY) {
                if (seen == index) return d;
                seen++;
            }
            d = d.plusDays(1);
        }
    }

    /** 종가만 정한 봉들. 시가·고가·저가는 종가와 같고 거래량은 1000이다. */
    public static List<Bar> closes(String... closes) {
        List<Bar> out = new ArrayList<>();
        for (int i = 0; i < closes.length; i++) {
            BigDecimal c = new BigDecimal(closes[i]);
            out.add(new Bar(day(i), c, c, c, c, new BigDecimal("1000")));
        }
        return out;
    }

    /** 종가 100에 거래량만 정한 봉들. */
    public static List<Bar> volumes(String... volumes) {
        List<Bar> out = new ArrayList<>();
        BigDecimal c = new BigDecimal("100");
        for (int i = 0; i < volumes.length; i++) {
            out.add(new Bar(day(i), c, c, c, c, new BigDecimal(volumes[i])));
        }
        return out;
    }

    /** 고가·저가를 정한 봉들. 종가는 (고가 + 저가) / 2다. */
    public static List<Bar> highLows(String[] highs, String[] lows) {
        List<Bar> out = new ArrayList<>();
        for (int i = 0; i < highs.length; i++) {
            BigDecimal h = new BigDecimal(highs[i]);
            BigDecimal l = new BigDecimal(lows[i]);
            BigDecimal c = h.add(l).divide(BigDecimal.TWO);
            out.add(new Bar(day(i), c, h, l, c, new BigDecimal("1000")));
        }
        return out;
    }

    /** 같은 종가가 count봉 이어진다. */
    public static List<Bar> flat(int count, String close) {
        String[] values = new String[count];
        java.util.Arrays.fill(values, close);
        return closes(values);
    }

    public static List<FlowBar> foreign(String... values) {
        List<FlowBar> out = new ArrayList<>();
        for (int i = 0; i < values.length; i++) {
            out.add(new FlowBar(day(i), new BigDecimal(values[i]), BigDecimal.ZERO));
        }
        return out;
    }

    public static Snapshot snapshot(String time, String price, String cumVolume) {
        return new Snapshot(OffsetDateTime.parse("2026-09-28T" + time + ":00+09:00"),
                new BigDecimal(price), new BigDecimal(cumVolume));
    }

    public static Series daily(List<Bar> bars) { return new Series(bars, List.of(), List.of(), null); }
}
```

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/indicator/IndicatorCalculatorTest.java`:

```java
package com.stockproject.portfolio.alert.indicator;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.WindowFn;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Transform;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import static com.stockproject.portfolio.alert.indicator.SeriesFixtures.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

class IndicatorCalculatorTest {

    private static final Transform ID = new Transform.Identity();

    @Test
    void 가격_등락률_거래량() {
        Series s = daily(closes("100", "110"));

        assertThat(close(IndicatorKey.PRICE, s)).isEqualByComparingTo("110");
        assertThat(close(IndicatorKey.CHANGE_PCT, s)).isEqualByComparingTo("10");
        assertThat(close(IndicatorKey.VOLUME, s)).isEqualByComparingTo("1000");
    }

    @Test
    void 거래량_배수는_직전_n봉_평균_대비다() {
        Series s = daily(volumes("100", "100", "100", "100", "100", "300"));

        assertThat(value(new Operand(IndicatorKey.VOLUME_RATIO, Map.of("n", 5), ID), s, Cadence.CLOSE))
                .isEqualByComparingTo("3");
    }

    @Test
    void 가격_폭은_현재_봉을_뺀_직전_n봉이다() {
        Series s = daily(highLows(new String[] {"110", "105", "108", "200"}, new String[] {"100", "95", "99", "1"}));

        assertThat(value(new Operand(IndicatorKey.RANGE_PCT, Map.of("n", 3), ID), s, Cadence.CLOSE).doubleValue())
                .isCloseTo(15.789, within(0.001));
    }

    @Test
    void 이동평균과_이격도() {
        Series s = daily(closes("10", "20", "30", "40"));

        assertThat(value(new Operand(IndicatorKey.SMA, Map.of("n", 3), ID), s, Cadence.CLOSE))
                .isEqualByComparingTo("30");
        assertThat(value(new Operand(IndicatorKey.DISPARITY, Map.of("n", 3), ID), s, Cadence.CLOSE).doubleValue())
                .isCloseTo(133.333, within(0.001));
    }

    /** Wilder 평활 (계획 A.9). 기대값은 같은 정의로 따로 계산했다. */
    @Test
    void RSI는_Wilder_평활이다() {
        List<Bar> bars = closes("44.34", "44.09", "44.15", "43.61", "44.33", "44.83", "45.10", "45.42",
                "45.84", "46.08", "45.89", "46.03", "45.61", "46.28", "46.28", "46.00");
        Operand rsi = new Operand(IndicatorKey.RSI, Map.of("n", 14), ID);

        assertThat(value(rsi, daily(bars.subList(0, 15)), Cadence.CLOSE).doubleValue()).isCloseTo(70.464, within(0.001));
        assertThat(value(rsi, daily(bars), Cadence.CLOSE).doubleValue()).isCloseTo(66.250, within(0.001));
        assertThat(IndicatorCalculator.value(rsi, daily(bars), Cadence.CLOSE, 1).doubleValue())
                .isCloseTo(70.464, within(0.001));
        assertThat(value(rsi, daily(bars.subList(0, 14)), Cadence.CLOSE)).isNull();
    }

    @Test
    void 오르기만_하면_RSI는_100이다() {
        assertThat(value(new Operand(IndicatorKey.RSI, Map.of("n", 2), ID), daily(closes("1", "2", "3")), Cadence.CLOSE))
                .isEqualByComparingTo("100");
    }

    @Test
    void 윈도우의_lag은_끝을_당긴다() {
        Series s = daily(highLows(new String[] {"10", "30", "20", "40"}, new String[] {"1", "1", "1", "1"}));

        assertThat(value(new Operand(IndicatorKey.HIGH, Map.of(), new Transform.Window(WindowFn.MAX, 3, 1)), s,
                Cadence.CLOSE)).isEqualByComparingTo("30");
        assertThat(value(new Operand(IndicatorKey.HIGH, Map.of(), new Transform.Window(WindowFn.MAX, 3, 0)), s,
                Cadence.CLOSE)).isEqualByComparingTo("40");
        assertThat(value(new Operand(IndicatorKey.LOW, Map.of(), new Transform.Window(WindowFn.AVG, 4, 0)), s,
                Cadence.CLOSE)).isEqualByComparingTo("1");
    }

    @Test
    void 변화량과_변화율() {
        Series s = daily(closes("10", "20", "35"));

        assertThat(value(new Operand(IndicatorKey.PRICE, Map.of(), new Transform.Delta(2)), s, Cadence.CLOSE))
                .isEqualByComparingTo("25");
        assertThat(value(new Operand(IndicatorKey.PRICE, Map.of(), new Transform.Pct(1)), s, Cadence.CLOSE))
                .isEqualByComparingTo("75");
    }

    @Test
    void shift는_앞_봉의_값이다() {
        Series s = daily(closes("10", "20", "35"));

        assertThat(IndicatorCalculator.value(new Operand(IndicatorKey.PRICE, Map.of(), ID), s, Cadence.CLOSE, 1))
                .isEqualByComparingTo("20");
    }

    @Test
    void 봉이_모자라면_null이다() {
        Series s = daily(closes("10", "20", "30"));

        assertThat(value(new Operand(IndicatorKey.SMA, Map.of("n", 5), ID), s, Cadence.CLOSE)).isNull();
        assertThat(value(new Operand(IndicatorKey.CHANGE_PCT, Map.of(), ID), daily(closes("10")), Cadence.CLOSE)).isNull();
        assertThat(value(new Operand(IndicatorKey.PRICE, Map.of(), ID), Series.empty(), Cadence.CLOSE)).isNull();
    }

    /** 장중 알림: 장중 지표 그대로는 스냅샷에서, 나머지는 직전 거래일까지의 봉에서 온다(§3.1). */
    @Test
    void 장중_값은_스냅샷에서_이력은_직전_봉까지에서_온다() {
        Series s = new Series(volumes("200", "200", "200", "200", "200"), List.of(),
                List.of(snapshot("10:00", "103", "300"), snapshot("10:05", "105", "600")), null);

        assertThat(intraday(IndicatorKey.PRICE, s, 0)).isEqualByComparingTo("105");
        assertThat(intraday(IndicatorKey.PRICE, s, 1)).isEqualByComparingTo("103");
        assertThat(intraday(IndicatorKey.VOLUME, s, 0)).isEqualByComparingTo("600");
        assertThat(intraday(IndicatorKey.CHANGE_PCT, s, 0)).isEqualByComparingTo("5");
        assertThat(IndicatorCalculator.value(new Operand(IndicatorKey.VOLUME_RATIO, Map.of("n", 5), ID), s,
                Cadence.INTRADAY, 0)).isEqualByComparingTo("3");
        assertThat(IndicatorCalculator.value(
                new Operand(IndicatorKey.PRICE, Map.of(), new Transform.Window(WindowFn.MAX, 5, 0)), s,
                Cadence.INTRADAY, 1)).isEqualByComparingTo("100");
    }

    @Test
    void 수급은_수급_계열에서_온다() {
        Series s = new Series(closes("1"), foreign("10", "-20", "30"), List.of(), null);

        assertThat(close(IndicatorKey.FOREIGN_NET_BUY, s)).isEqualByComparingTo("30");
        assertThat(close(IndicatorKey.INSTITUTION_NET_BUY, s)).isEqualByComparingTo("0");
        assertThat(value(new Operand(IndicatorKey.FOREIGN_NET_BUY, Map.of(), new Transform.Window(WindowFn.SUM, 3, 0)),
                s, Cadence.CLOSE)).isEqualByComparingTo("20");
    }

    @Test
    void 사용자_상태_지표는_보유_스냅샷에서_온다() {
        Series held = new Series(List.of(), List.of(), List.of(),
                new Holding(new BigDecimal("12.5"), new BigDecimal("30.1"), false));

        assertThat(close(IndicatorKey.UNREALIZED_PNL_PCT, held)).isEqualByComparingTo("12.5");
        assertThat(close(IndicatorKey.WEIGHT_PCT, held)).isEqualByComparingTo("30.1");
        assertThat(close(IndicatorKey.WEIGHT_PCT, Series.empty())).isNull();
    }

    private static BigDecimal close(IndicatorKey key, Series s) {
        return value(new Operand(key, Map.of(), ID), s, Cadence.CLOSE);
    }

    private static BigDecimal intraday(IndicatorKey key, Series s, int shift) {
        return IndicatorCalculator.value(new Operand(key, Map.of(), ID), s, Cadence.INTRADAY, shift);
    }

    private static BigDecimal value(Operand o, Series s, Cadence cadence) {
        return IndicatorCalculator.value(o, s, cadence, 0);
    }
}
```

- [ ] **Step 3: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.indicator.*'`
Expected: FAIL — 컴파일 오류

- [ ] **Step 4: 계열 레코드를 쓴다**

`alert/indicator/Bar.java`:

```java
package com.stockproject.portfolio.alert.indicator;

import java.math.BigDecimal;
import java.time.LocalDate;

/** 수정주가 일봉 하나. 날짜는 그 종목 시장의 현지 거래일이다. */
public record Bar(LocalDate date, BigDecimal open, BigDecimal high, BigDecimal low, BigDecimal close,
                  BigDecimal volume) { }
```

`alert/indicator/FlowBar.java`:

```java
package com.stockproject.portfolio.alert.indicator;

import java.math.BigDecimal;
import java.time.LocalDate;

/** 하루의 투자자별 순매수 금액(원). */
public record FlowBar(LocalDate date, BigDecimal foreign, BigDecimal institution) { }
```

`alert/indicator/Snapshot.java`:

```java
package com.stockproject.portfolio.alert.indicator;

import java.math.BigDecimal;
import java.time.OffsetDateTime;

/** 장중 스냅샷 하나 — 현재가와 당일 누적 거래량. */
public record Snapshot(OffsetDateTime at, BigDecimal price, BigDecimal cumVolume) { }
```

`alert/indicator/Holding.java`:

```java
package com.stockproject.portfolio.alert.indicator;

import java.math.BigDecimal;

/**
 * 확정 보유 스냅샷의 그 종목 한 행 (스펙 §5.1). 모든 계좌를 합산한 값이다.
 * carriedForward는 그 종목의 행 중 하나라도 이월값인가다 — 그러면 그날 값이 아니다(§7.2).
 */
public record Holding(BigDecimal unrealizedPnlPct, BigDecimal weightPct, boolean carriedForward) { }
```

`alert/indicator/Series.java`:

```java
package com.stockproject.portfolio.alert.indicator;

import java.util.List;

/**
 * 한 종목의 평가 입력 계열. 모두 오름차순이다.
 *
 * <p>계열은 있는 봉으로 만든다(스펙 §7.2) — 거래정지일과 데이터 누락일은 들어 있지 않다.
 * 종가 알림은 마지막 봉이 평가 거래일의 봉이다. 장중 알림은 마지막 봉이 직전 거래 봉이고
 * snapshots가 그날의 장중 스냅샷이다. holding은 사용자 상태 지표를 쓸 때만 있다.</p>
 */
public record Series(List<Bar> bars, List<FlowBar> flows, List<Snapshot> snapshots, Holding holding) {

    public Series {
        bars = List.copyOf(bars);
        flows = List.copyOf(flows);
        snapshots = List.copyOf(snapshots);
    }

    public static Series empty() { return new Series(List.of(), List.of(), List.of(), null); }

    public Bar lastBar() { return bars.isEmpty() ? null : bars.get(bars.size() - 1); }

    public FlowBar lastFlow() { return flows.isEmpty() ? null : flows.get(flows.size() - 1); }
}
```

- [ ] **Step 5: 계산기를 쓴다**

`alert/indicator/IndicatorCalculator.java`:

```java
package com.stockproject.portfolio.alert.indicator;

import com.stockproject.portfolio.alert.catalog.AlertCatalog;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.Indicator;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.Scope;
import com.stockproject.portfolio.alert.catalog.WindowFn;
import com.stockproject.portfolio.alert.compile.RequiredBars;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Transform;

import java.math.BigDecimal;
import java.math.MathContext;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;

/**
 * 피연산자 값 (스펙 §5.1 · §4.2). 비교는 계산값 그대로 하고 반올림은 문장에서만 한다.
 *
 * <p>시점 t는 계열의 위치다. 종가 알림은 t = 마지막 봉 − shift.
 * 장중 알림에서 장중 지표 그대로(intraday_left · identity)는 스냅샷[마지막 − shift]이고,
 * 그 밖의 피연산자는 직전 거래일까지 확정된 이력이라 shift와 무관하게 마지막 봉에서 계산한다.</p>
 *
 * <p>계산할 봉이 모자라면 null을 돌려준다. 평가기가 INSUFFICIENT_HISTORY로 옮긴다.
 * 나눗셈의 분모가 0이어도 null이다 — 값이 정의되지 않는다.</p>
 */
public final class IndicatorCalculator {

    private IndicatorCalculator() { }

    private static final MathContext MC = MathContext.DECIMAL64;
    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);

    public static BigDecimal value(Operand o, Series s, Cadence cadence, int shift) {
        Indicator indicator = AlertCatalog.indicator(o.indicator());
        if (indicator.scope() == Scope.USER) {
            return shift == 0 && s.holding() != null ? user(o.indicator(), s.holding()) : null;
        }
        if (cadence == Cadence.INTRADAY && isLive(o)) return live(o, s, shift);

        int size = isFlow(o.indicator()) ? s.flows().size() : s.bars().size();
        int t = size - 1 - (cadence == Cadence.INTRADAY ? 0 : shift);
        return transformed(o, s, t);
    }

    /** 장중 알림에서 스냅샷으로 계산하는 피연산자인가 — 장중 지표 그대로(§3.1). */
    public static boolean isLive(Operand o) {
        return AlertCatalog.indicator(o.indicator()).intradayLeft() && o.transform() instanceof Transform.Identity;
    }

    public static boolean isFlow(IndicatorKey key) {
        return key == IndicatorKey.FOREIGN_NET_BUY || key == IndicatorKey.INSTITUTION_NET_BUY;
    }

    // ---- 변형 -------------------------------------------------------------------

    private static BigDecimal transformed(Operand o, Series s, int t) {
        Function<Integer, BigDecimal> f = i -> base(o, s, i);
        return switch (o.transform()) {
            case Transform.Identity i -> f.apply(t);
            case Transform.Window w -> window(f, t - w.lagOrZero(), w.n(), w.fn());
            case Transform.Delta d -> {
                BigDecimal now = f.apply(t);
                BigDecimal then = f.apply(t - d.n());
                yield now == null || then == null ? null : now.subtract(then);
            }
            case Transform.Pct p -> pct(f.apply(t), f.apply(t - p.n()));
        };
    }

    private static BigDecimal window(Function<Integer, BigDecimal> f, int end, int n, WindowFn fn) {
        if (end - n + 1 < 0) return null;
        List<BigDecimal> values = new ArrayList<>(n);
        for (int i = end - n + 1; i <= end; i++) {
            BigDecimal v = f.apply(i);
            if (v == null) return null;
            values.add(v);
        }
        return switch (fn) {
            case MAX -> values.stream().reduce(BigDecimal::max).orElseThrow();
            case MIN -> values.stream().reduce(BigDecimal::min).orElseThrow();
            case SUM -> sum(values);
            case AVG -> sum(values).divide(BigDecimal.valueOf(n), MC);
        };
    }

    // ---- 지표 그대로 (봉 계열) -----------------------------------------------------

    private static BigDecimal base(Operand o, Series s, int t) {
        if (t < 0) return null;
        if (isFlow(o.indicator())) {
            if (t >= s.flows().size()) return null;
            FlowBar f = s.flows().get(t);
            return o.indicator() == IndicatorKey.FOREIGN_NET_BUY ? f.foreign() : f.institution();
        }
        List<Bar> bars = s.bars();
        if (t >= bars.size()) return null;
        Indicator indicator = AlertCatalog.indicator(o.indicator());
        return switch (o.indicator()) {
            case PRICE -> bars.get(t).close();
            case VOLUME -> bars.get(t).volume();
            case HIGH -> bars.get(t).high();
            case LOW -> bars.get(t).low();
            case CHANGE_PCT -> t < 1 ? null : pct(bars.get(t).close(), bars.get(t - 1).close());
            case VOLUME_RATIO -> {
                int n = indicator.paramOrDefault(o.params(), "n");
                BigDecimal avg = average(bars, t - n, t - 1, Bar::volume);
                yield avg == null ? null : divide(bars.get(t).volume(), avg);
            }
            case RANGE_PCT -> {
                int n = indicator.paramOrDefault(o.params(), "n");
                if (t - n < 0) yield null;
                BigDecimal high = bars.get(t - n).high();
                BigDecimal low = bars.get(t - n).low();
                for (int i = t - n + 1; i <= t - 1; i++) {
                    high = high.max(bars.get(i).high());
                    low = low.min(bars.get(i).low());
                }
                BigDecimal ratio = divide(high.subtract(low), low);
                yield ratio == null ? null : ratio.multiply(HUNDRED);
            }
            case SMA -> average(bars, t - indicator.paramOrDefault(o.params(), "n") + 1, t, Bar::close);
            case DISPARITY -> {
                BigDecimal sma = average(bars, t - indicator.paramOrDefault(o.params(), "n") + 1, t, Bar::close);
                BigDecimal ratio = sma == null ? null : divide(bars.get(t).close(), sma);
                yield ratio == null ? null : ratio.multiply(HUNDRED);
            }
            case RSI -> rsi(bars, t, indicator.paramOrDefault(o.params(), "n"));
            case FOREIGN_NET_BUY, INSTITUTION_NET_BUY, UNREALIZED_PNL_PCT, WEIGHT_PCT ->
                    throw new IllegalStateException(o.indicator() + "는 봉 계열 지표가 아니다");
        };
    }

    /**
     * Wilder RSI (계획 A.9). t에서 끝나는 최대 250봉 창 위에서 계산한다.
     * 창의 첫 n개 변화로 평균 상승·하락을 시작하고 이후 avg = (avg × (n−1) + x) / n.
     */
    private static BigDecimal rsi(List<Bar> bars, int t, int n) {
        int start = Math.max(0, t - RequiredBars.RSI_WINDOW + 1);
        if (t - start < n) return null;
        BigDecimal gain = BigDecimal.ZERO;
        BigDecimal loss = BigDecimal.ZERO;
        for (int i = start + 1; i <= start + n; i++) {
            BigDecimal change = bars.get(i).close().subtract(bars.get(i - 1).close());
            gain = gain.add(change.max(BigDecimal.ZERO));
            loss = loss.add(change.negate().max(BigDecimal.ZERO));
        }
        BigDecimal size = BigDecimal.valueOf(n);
        BigDecimal avgGain = gain.divide(size, MC);
        BigDecimal avgLoss = loss.divide(size, MC);
        BigDecimal keep = BigDecimal.valueOf(n - 1L);
        for (int i = start + n + 1; i <= t; i++) {
            BigDecimal change = bars.get(i).close().subtract(bars.get(i - 1).close());
            avgGain = avgGain.multiply(keep).add(change.max(BigDecimal.ZERO)).divide(size, MC);
            avgLoss = avgLoss.multiply(keep).add(change.negate().max(BigDecimal.ZERO)).divide(size, MC);
        }
        if (avgLoss.signum() == 0) return HUNDRED;
        BigDecimal rs = avgGain.divide(avgLoss, MC);
        return HUNDRED.subtract(HUNDRED.divide(BigDecimal.ONE.add(rs), MC));
    }

    // ---- 장중 값 ----------------------------------------------------------------

    private static BigDecimal live(Operand o, Series s, int shift) {
        int i = s.snapshots().size() - 1 - shift;
        if (i < 0) return null;
        Snapshot snap = s.snapshots().get(i);
        List<Bar> bars = s.bars();
        return switch (o.indicator()) {
            case PRICE -> snap.price();
            case VOLUME -> snap.cumVolume();
            case CHANGE_PCT -> bars.isEmpty() ? null : pct(snap.price(), s.lastBar().close());
            case VOLUME_RATIO -> {
                int n = AlertCatalog.indicator(o.indicator()).paramOrDefault(o.params(), "n");
                BigDecimal avg = average(bars, bars.size() - n, bars.size() - 1, Bar::volume);
                yield avg == null ? null : divide(snap.cumVolume(), avg);
            }
            default -> throw new IllegalStateException(o.indicator() + "는 장중 지표가 아니다");
        };
    }

    private static BigDecimal user(IndicatorKey key, Holding h) {
        return key == IndicatorKey.UNREALIZED_PNL_PCT ? h.unrealizedPnlPct() : h.weightPct();
    }

    // ---- 산술 -------------------------------------------------------------------

    private static BigDecimal average(List<Bar> bars, int from, int to, Function<Bar, BigDecimal> field) {
        if (from < 0 || to >= bars.size() || from > to) return null;
        BigDecimal total = BigDecimal.ZERO;
        for (int i = from; i <= to; i++) total = total.add(field.apply(bars.get(i)));
        return total.divide(BigDecimal.valueOf(to - from + 1L), MC);
    }

    private static BigDecimal pct(BigDecimal now, BigDecimal then) {
        BigDecimal ratio = now == null ? null : divide(now, then);
        return ratio == null ? null : ratio.subtract(BigDecimal.ONE).multiply(HUNDRED);
    }

    private static BigDecimal divide(BigDecimal a, BigDecimal b) {
        return b == null || b.signum() == 0 ? null : a.divide(b, MC);
    }

    private static BigDecimal sum(List<BigDecimal> values) {
        return values.stream().reduce(BigDecimal.ZERO, BigDecimal::add);
    }
}
```

- [ ] **Step 6: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.indicator.*'`
Expected: PASS

- [ ] **Step 7: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/indicator \
        src/test/java/com/stockproject/portfolio/alert/indicator
git commit -m "feat: 알림 지표를 봉 계열 위의 순수 함수로 계산한다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: 3값 평가 — 한 데이터 시점의 조건 결과와 확인 불가 사유

미리보기의 현재값 상자와 ②의 평가기가 이 코드 하나를 쓴다. 엣지·발화는 여기서 다루지 않는다(②).

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/compile/DataNeeds.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/evaluation/` 아래 `Truth.java` · `UnknownReason.java` · `Basis.java` · `EvaluationInput.java` · `ConditionResult.java` · `EvaluationResult.java` · `ConditionEvaluator.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/compile/DataNeedsTest.java` · `src/test/java/com/stockproject/portfolio/alert/evaluation/ConditionEvaluatorTest.java`

**Interfaces:**
- Consumes: Task 4 `CompiledTrigger` · `RequiredBars`, Task 6 `Series` · `IndicatorCalculator` · `SeriesFixtures`(테스트).
- Produces:
  - `final class DataNeeds` (`compile`) — `static Set<DataKind> of(Operand, Cadence)` · `of(Condition, Cadence)` · `of(CompiledTrigger, Cadence)`. 그 알림이 기다리는 데이터 종류(§5.4 · §7.1).
  - `enum Truth { TRUE, FALSE, UNKNOWN }` — `static Truth of(boolean)`.
  - `enum UnknownReason` 6값 — `label()`(카드 문구 §7.2).
  - `enum Basis { DAILY, INTRADAY }` — 평가가 일봉 기준인가 장중 스냅샷 기준인가.
  - `record EvaluationInput(Cadence cadence, Basis basis, Market market, LocalDate date, OffsetDateTime asOf, Series series, Set<DataKind> notDone, Set<LocalDate> missingDays, boolean instrumentKnown, Duration allowedGap)` — `date`는 평가 거래일(장중이면 스냅샷의 현지 날짜), `notDone`은 이 시점에 `DONE`이 아닌 데이터 종류, `missingDays`는 읽은 범위의 데이터 누락일(계획 A.6). `static EvaluationInput noData(Cadence, Market)` — 완료 신호가 하나도 없을 때.
  - `record ConditionResult(Truth truth, UnknownReason reason, BigDecimal left, BigDecimal right, Integer progress)` — `progress`는 연속이면 이어진 봉 수, 지속이면 이어진 분.
  - `record EvaluationResult(Truth truth, UnknownReason reason, OffsetDateTime asOf, Basis basis, List<ConditionResult> conditions)`
  - `final class ConditionEvaluator` — `static EvaluationResult evaluate(CompiledTrigger, EvaluationInput)` · `static ConditionResult evaluate(Condition, EvaluationInput)`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/compile/DataNeedsTest.java`:

```java
package com.stockproject.portfolio.alert.compile;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.DataKind;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.WindowFn;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Transform;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/** 평가 시점마다 기다리는 데이터가 다르다 (§3.1 · §5.4). */
class DataNeedsTest {

    private static final Transform ID = new Transform.Identity();

    @Test
    void 종가_알림의_시세_지표는_일봉만_기다린다() {
        assertThat(DataNeeds.of(op(IndicatorKey.PRICE, ID), Cadence.CLOSE)).containsOnly(DataKind.DAILY_BAR);
        assertThat(DataNeeds.of(op(IndicatorKey.FOREIGN_NET_BUY, ID), Cadence.CLOSE)).containsOnly(DataKind.DAILY_FLOW);
        assertThat(DataNeeds.of(op(IndicatorKey.WEIGHT_PCT, ID), Cadence.CLOSE))
                .containsOnly(DataKind.PORTFOLIO_SNAPSHOT);
    }

    @Test
    void 장중_알림의_가격은_스냅샷만_등락률은_직전_일봉도_기다린다() {
        assertThat(DataNeeds.of(op(IndicatorKey.PRICE, ID), Cadence.INTRADAY)).containsOnly(DataKind.INTRADAY_QUOTE);
        assertThat(DataNeeds.of(op(IndicatorKey.CHANGE_PCT, ID), Cadence.INTRADAY))
                .containsOnly(DataKind.INTRADAY_QUOTE, DataKind.DAILY_BAR);
        assertThat(DataNeeds.of(op(IndicatorKey.HIGH, new Transform.Window(WindowFn.MAX, 20, 0)), Cadence.INTRADAY))
                .containsOnly(DataKind.DAILY_BAR);
    }

    private static Operand op(IndicatorKey key, Transform t) { return new Operand(key, Map.of(), t); }
}
```

`src/test/java/com/stockproject/portfolio/alert/evaluation/ConditionEvaluatorTest.java`:

```java
package com.stockproject.portfolio.alert.evaluation;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.DataKind;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.indicator.Bar;
import com.stockproject.portfolio.alert.indicator.Holding;
import com.stockproject.portfolio.alert.indicator.Series;
import com.stockproject.portfolio.alert.indicator.Snapshot;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Right;
import com.stockproject.portfolio.alert.spec.Transform;
import com.stockproject.portfolio.domain.Market;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static com.stockproject.portfolio.alert.indicator.SeriesFixtures.*;
import static org.assertj.core.api.Assertions.assertThat;

class ConditionEvaluatorTest {

    private static final Transform ID = new Transform.Identity();
    private static final Operand PRICE = new Operand(IndicatorKey.PRICE, Map.of(), ID);

    @Test
    void 비교_결과와_양쪽_값을_돌려준다() {
        ConditionResult r = ConditionEvaluator.evaluate(gte(PRICE, "100", null), close(closes("90", "105"), 1));

        assertThat(r.truth()).isEqualTo(Truth.TRUE);
        assertThat(r.left()).isEqualByComparingTo("105");
        assertThat(r.right()).isEqualByComparingTo("100");
        assertThat(ConditionEvaluator.evaluate(gte(PRICE, "106", null), close(closes("90", "105"), 1)).truth())
                .isEqualTo(Truth.FALSE);
    }

    /** AND는 FALSE 우선, 그다음 UNKNOWN (§6.1). */
    @Test
    void AND는_거짓이_먼저다() {
        Condition sma = gte(new Operand(IndicatorKey.SMA, Map.of("n", 20), ID), "1", null);
        EvaluationInput in = close(closes("90", "105"), 1);

        EvaluationResult falseWins = ConditionEvaluator.evaluate(trigger(gte(PRICE, "200", null), sma), in);
        assertThat(falseWins.truth()).isEqualTo(Truth.FALSE);
        assertThat(falseWins.reason()).isNull();

        EvaluationResult unknown = ConditionEvaluator.evaluate(trigger(gte(PRICE, "100", null), sma), in);
        assertThat(unknown.truth()).isEqualTo(Truth.UNKNOWN);
        assertThat(unknown.reason()).isEqualTo(UnknownReason.INSUFFICIENT_HISTORY);
        assertThat(unknown.conditions()).extracting(ConditionResult::truth).containsExactly(Truth.TRUE, Truth.UNKNOWN);
    }

    @Test
    void 연속은_현재_봉부터_N봉이_모두_참이어야_한다() {
        ConditionResult held = ConditionEvaluator.evaluate(gte(PRICE, "100", new Modifier.Streak(3)),
                close(closes("90", "101", "102", "103"), 3));
        assertThat(held.truth()).isEqualTo(Truth.TRUE);
        assertThat(held.progress()).isEqualTo(3);

        ConditionResult broken = ConditionEvaluator.evaluate(gte(PRICE, "100", new Modifier.Streak(3)),
                close(closes("101", "90", "102"), 2));
        assertThat(broken.truth()).isEqualTo(Truth.FALSE);
        assertThat(broken.progress()).isEqualTo(1);
    }

    /** 거래정지일은 계열에서 빠지고 연속을 끊지도 잇지도 않는다 (§7.2). */
    @Test
    void 거래정지일은_건너뛴다() {
        List<Bar> bars = new ArrayList<>(closes("101", "102", "999", "103"));
        bars.remove(2);   // day(2)에 거래가 없었다 — 그 시장의 일봉은 DONE이다
        EvaluationInput in = input(Cadence.CLOSE, Basis.DAILY, Market.KR, day(3),
                new Series(bars, List.of(), List.of(), null), Set.of(), Set.of());

        assertThat(ConditionEvaluator.evaluate(gte(PRICE, "100", new Modifier.Streak(3)), in).truth())
                .isEqualTo(Truth.TRUE);
    }

    @Test
    void 연속_구간_안의_데이터_누락일은_확인_불가다() {
        List<Bar> bars = new ArrayList<>(closes("101", "102", "999", "103"));
        bars.remove(2);
        Series s = new Series(bars, List.of(), List.of(), null);

        EvaluationInput inside = input(Cadence.CLOSE, Basis.DAILY, Market.KR, day(3), s, Set.of(), Set.of(day(2)));
        ConditionResult r = ConditionEvaluator.evaluate(gte(PRICE, "100", new Modifier.Streak(3)), inside);
        assertThat(r.truth()).isEqualTo(Truth.UNKNOWN);
        assertThat(r.reason()).isEqualTo(UnknownReason.DATA_MISSING);

        // 연속 2봉도 day(1)·day(3)에 걸쳐 누락일 day(2)를 품는다
        assertThat(ConditionEvaluator.evaluate(gte(PRICE, "100", new Modifier.Streak(2)), inside).reason())
                .isEqualTo(UnknownReason.DATA_MISSING);
        // 유지 조건이 없으면 누락일은 계열에서 빠질 뿐이다
        assertThat(ConditionEvaluator.evaluate(gte(PRICE, "100", null), inside).truth()).isEqualTo(Truth.TRUE);
    }

    @Test
    void 현재_봉이_없으면_거래_없음이다() {
        EvaluationInput in = input(Cadence.CLOSE, Basis.DAILY, Market.KR, day(2),
                daily(closes("100", "101")), Set.of(), Set.of());

        assertThat(ConditionEvaluator.evaluate(gte(PRICE, "1", null), in).reason()).isEqualTo(UnknownReason.NO_TRADE);
    }

    @Test
    void 국내_종목의_30퍼센트_변동은_가격_보정_대기다() {
        Condition sma = gte(new Operand(IndicatorKey.SMA, Map.of("n", 3), ID), "1", null);
        List<Bar> bars = closes("100", "100", "50", "50");

        assertThat(ConditionEvaluator.evaluate(sma, close(bars, 3)).reason())
                .isEqualTo(UnknownReason.PRICE_ADJUSTMENT_SUSPECTED);
        assertThat(ConditionEvaluator.evaluate(sma, input(Cadence.CLOSE, Basis.DAILY, Market.US, day(3),
                daily(bars), Set.of(), Set.of())).truth()).isEqualTo(Truth.TRUE);
        // 읽는 범위(현재 봉 1개) 밖의 변동은 보지 않는다
        assertThat(ConditionEvaluator.evaluate(gte(PRICE, "1", null), close(bars, 3)).truth()).isEqualTo(Truth.TRUE);
    }

    @Test
    void 상향_돌파는_직전에_아래였고_지금_위다() {
        Condition cross = new Condition(PRICE, OperatorKey.CROSSES_ABOVE,
                Right.operand(new Operand(IndicatorKey.SMA, Map.of("n", 2), ID)), null);

        // 어제 95 < 이평 97.5, 오늘 110 > 이평 102.5
        assertThat(ConditionEvaluator.evaluate(cross, close(closes("100", "100", "95", "110"), 3)).truth())
                .isEqualTo(Truth.TRUE);
        // 어제 이미 위였다(105 > 102.5)
        assertThat(ConditionEvaluator.evaluate(cross, close(closes("100", "100", "105", "110"), 3)).truth())
                .isEqualTo(Truth.FALSE);
    }

    @Test
    void 지속은_참인_스냅샷이_이어진_시간이다() {
        Series s = intraday(snapshot("10:00", "105", "1"), snapshot("10:05", "106", "1"), snapshot("10:10", "107", "1"));

        ConditionResult ten = ConditionEvaluator.evaluate(gte(PRICE, "100", new Modifier.PersistMin(10)),
                live(s, Market.KR));
        assertThat(ten.truth()).isEqualTo(Truth.TRUE);
        assertThat(ten.progress()).isEqualTo(10);

        assertThat(ConditionEvaluator.evaluate(gte(PRICE, "100", new Modifier.PersistMin(15)), live(s, Market.KR))
                .truth()).isEqualTo(Truth.FALSE);
    }

    @Test
    void 지속_구간에_허용_지연을_넘는_공백이_있으면_확인_불가다() {
        Series s = intraday(snapshot("10:00", "105", "1"), snapshot("10:15", "106", "1"));

        ConditionResult r = ConditionEvaluator.evaluate(gte(PRICE, "100", new Modifier.PersistMin(15)), live(s, Market.KR));
        assertThat(r.truth()).isEqualTo(Truth.UNKNOWN);
        assertThat(r.reason()).isEqualTo(UnknownReason.DATA_MISSING);
        // 미국은 허용 지연이 20분이라 같은 간격이 공백이 아니다
        assertThat(ConditionEvaluator.evaluate(gte(PRICE, "100", new Modifier.PersistMin(15)), live(s, Market.US))
                .truth()).isEqualTo(Truth.TRUE);
    }

    /** 일봉 기준으로 장중 알림을 미리볼 때 지속은 비교만 평가한다 (계획 A.5). */
    @Test
    void 일봉_기준의_지속은_비교만_본다() {
        Series s = intraday(snapshot("15:30", "105", "1"));
        EvaluationInput in = input(Cadence.INTRADAY, Basis.DAILY, Market.KR, day(0), s, Set.of(), Set.of());

        ConditionResult r = ConditionEvaluator.evaluate(gte(PRICE, "100", new Modifier.PersistMin(30)), in);
        assertThat(r.truth()).isEqualTo(Truth.TRUE);
        assertThat(r.progress()).isNull();
    }

    @Test
    void 사용자_상태_조건() {
        Condition pnl = gte(new Operand(IndicatorKey.UNREALIZED_PNL_PCT, Map.of(), ID), "10", null);

        assertThat(ConditionEvaluator.evaluate(pnl, holding(null)).reason()).isEqualTo(UnknownReason.NOT_HELD);
        assertThat(ConditionEvaluator.evaluate(pnl, holding(new Holding(new BigDecimal("12"), BigDecimal.ONE, true)))
                .reason()).isEqualTo(UnknownReason.DATA_MISSING);
        assertThat(ConditionEvaluator.evaluate(pnl, holding(new Holding(new BigDecimal("12"), BigDecimal.ONE, false)))
                .truth()).isEqualTo(Truth.TRUE);
    }

    @Test
    void 기다리는_데이터가_DONE이_아니면_데이터_없음이다() {
        Condition flow = gte(new Operand(IndicatorKey.FOREIGN_NET_BUY, Map.of(), ID), "0", null);
        EvaluationInput in = input(Cadence.CLOSE, Basis.DAILY, Market.KR, day(1), daily(closes("100", "101")),
                Set.of(DataKind.DAILY_FLOW), Set.of());

        assertThat(ConditionEvaluator.evaluate(flow, in).reason()).isEqualTo(UnknownReason.DATA_MISSING);
        assertThat(ConditionEvaluator.evaluate(gte(PRICE, "1", null), in).truth()).isEqualTo(Truth.TRUE);
    }

    /** 장중 평가에 필요한 직전 거래일 일봉이 DONE이 아니면 등락률은 확인 불가, 가격은 평가한다 (§3.1). */
    @Test
    void 장중_등락률은_직전_일봉을_기다린다() {
        Series s = new Series(closes("100"), List.of(), List.of(snapshot("10:00", "105", "1")), null);
        EvaluationInput in = input(Cadence.INTRADAY, Basis.INTRADAY, Market.KR, day(1), s,
                Set.of(DataKind.DAILY_BAR), Set.of());

        assertThat(ConditionEvaluator.evaluate(gte(new Operand(IndicatorKey.CHANGE_PCT, Map.of(), ID), "1", null), in)
                .reason()).isEqualTo(UnknownReason.DATA_MISSING);
        assertThat(ConditionEvaluator.evaluate(gte(PRICE, "100", null), in).truth()).isEqualTo(Truth.TRUE);
    }

    @Test
    void 종목을_모르면_종목_정보_없음이다() {
        EvaluationInput in = new EvaluationInput(Cadence.CLOSE, Basis.DAILY, Market.KR, day(0), null,
                Series.empty(), Set.of(), Set.of(), false, Duration.ofMinutes(10));

        assertThat(ConditionEvaluator.evaluate(gte(PRICE, "1", null), in).reason())
                .isEqualTo(UnknownReason.INSTRUMENT_UNKNOWN);
    }

    @Test
    void 완료_신호가_없으면_전부_데이터_없음이다() {
        EvaluationResult r = ConditionEvaluator.evaluate(trigger(gte(PRICE, "1", null)),
                EvaluationInput.noData(Cadence.CLOSE, Market.KR));

        assertThat(r.truth()).isEqualTo(Truth.UNKNOWN);
        assertThat(r.reason()).isEqualTo(UnknownReason.DATA_MISSING);
        assertThat(r.asOf()).isNull();
    }

    // ---- 도우미 ----------------------------------------------------------------

    private static Condition gte(Operand left, String value, Modifier modifier) {
        return new Condition(left, OperatorKey.GTE, Right.constant(new BigDecimal(value)), modifier);
    }

    private static CompiledTrigger trigger(Condition... conditions) {
        return new CompiledTrigger(List.of(conditions), null, null);
    }

    /** 국내 종가 알림, 평가 거래일 = day(lastIndex). */
    private static EvaluationInput close(List<Bar> bars, int lastIndex) {
        return input(Cadence.CLOSE, Basis.DAILY, Market.KR, day(lastIndex), daily(bars), Set.of(), Set.of());
    }

    private static EvaluationInput live(Series s, Market market) {
        return input(Cadence.INTRADAY, Basis.INTRADAY, market, day(0), s, Set.of(), Set.of());
    }

    private static EvaluationInput holding(Holding h) {
        return input(Cadence.CLOSE, Basis.DAILY, Market.KR, day(0), new Series(List.of(), List.of(), List.of(), h),
                Set.of(), Set.of());
    }

    private static Series intraday(Snapshot... snapshots) {
        return new Series(closes("100"), List.of(), List.of(snapshots), null);
    }

    private static EvaluationInput input(Cadence cadence, Basis basis, Market market, LocalDate date, Series s,
                                         Set<DataKind> notDone, Set<LocalDate> missing) {
        Duration gap = market == Market.KR ? Duration.ofMinutes(10) : Duration.ofMinutes(20);
        return new EvaluationInput(cadence, basis, market, date, OffsetDateTime.parse("2026-09-28T15:30:00+09:00"),
                s, notDone, missing, true, gap);
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.evaluation.*' --tests 'com.stockproject.portfolio.alert.compile.DataNeedsTest'`
Expected: FAIL — 컴파일 오류

- [ ] **Step 3: 기다리는 데이터를 유도한다**

`alert/compile/DataNeeds.java`:

```java
package com.stockproject.portfolio.alert.compile;

import com.stockproject.portfolio.alert.catalog.AlertCatalog;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.DataKind;
import com.stockproject.portfolio.alert.catalog.Indicator;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.Scope;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Transform;

import java.util.EnumSet;
import java.util.Set;

/**
 * 알림이 기다리는 데이터 종류 (스펙 §5.4 · §7.1). 평가 시점에 따라 다르다 —
 * 장중 알림의 가격은 스냅샷만, 등락률·거래량 배수는 직전 거래일 일봉도,
 * 이력 피연산자는 일봉만 기다린다(§3.1).
 */
public final class DataNeeds {

    private DataNeeds() { }

    public static Set<DataKind> of(CompiledTrigger trigger, Cadence cadence) {
        Set<DataKind> out = EnumSet.noneOf(DataKind.class);
        for (Condition c : trigger.conditions()) out.addAll(of(c, cadence));
        return out;
    }

    public static Set<DataKind> of(Condition c, Cadence cadence) {
        Set<DataKind> out = EnumSet.noneOf(DataKind.class);
        out.addAll(of(c.left(), cadence));
        if (!c.right().isConstant()) out.addAll(of(c.right().operand(), cadence));
        return out;
    }

    public static Set<DataKind> of(Operand o, Cadence cadence) {
        Indicator indicator = AlertCatalog.indicator(o.indicator());
        if (indicator.scope() == Scope.USER) return EnumSet.of(DataKind.PORTFOLIO_SNAPSHOT);
        if (o.indicator() == IndicatorKey.FOREIGN_NET_BUY || o.indicator() == IndicatorKey.INSTITUTION_NET_BUY) {
            return EnumSet.of(DataKind.DAILY_FLOW);
        }
        boolean live = cadence == Cadence.INTRADAY && indicator.intradayLeft()
                && o.transform() instanceof Transform.Identity;
        if (!live) return EnumSet.of(DataKind.DAILY_BAR);
        return switch (o.indicator()) {
            case PRICE, VOLUME -> EnumSet.of(DataKind.INTRADAY_QUOTE);
            default -> EnumSet.of(DataKind.INTRADAY_QUOTE, DataKind.DAILY_BAR);
        };
    }
}
```

- [ ] **Step 4: 평가 타입을 쓴다**

`alert/evaluation/Truth.java`:

```java
package com.stockproject.portfolio.alert.evaluation;

/** 조건 하나의 결과 (스펙 §6.1). */
public enum Truth {
    TRUE, FALSE, UNKNOWN;

    public static Truth of(boolean value) { return value ? TRUE : FALSE; }
}
```

`alert/evaluation/UnknownReason.java`:

```java
package com.stockproject.portfolio.alert.evaluation;

/** 확인 불가 사유와 카드 문구 (스펙 §7.2). */
public enum UnknownReason {
    DATA_MISSING("데이터 없음"),
    INSUFFICIENT_HISTORY("이력 부족"),
    NO_TRADE("거래 없음"),
    PRICE_ADJUSTMENT_SUSPECTED("가격 보정 대기"),
    NOT_HELD("미보유"),
    INSTRUMENT_UNKNOWN("종목 정보 없음");

    private final String label;

    UnknownReason(String label) { this.label = label; }

    public String label() { return label; }
}
```

`alert/evaluation/Basis.java`:

```java
package com.stockproject.portfolio.alert.evaluation;

/**
 * 평가가 무엇을 기준으로 했는가. 종가 알림은 늘 DAILY다. 장중 알림은 장중 스냅샷이 있으면
 * INTRADAY, 미리보기에서 스냅샷이 없으면 가장 최근 종가를 스냅샷 하나로 삼은 DAILY다(계획 A.5).
 */
public enum Basis { DAILY, INTRADAY }
```

`alert/evaluation/EvaluationInput.java`:

```java
package com.stockproject.portfolio.alert.evaluation;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.DataKind;
import com.stockproject.portfolio.alert.indicator.Series;
import com.stockproject.portfolio.domain.Market;

import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.EnumSet;
import java.util.Set;

/**
 * 한 알림을 한 데이터 시점에서 평가하는 데 필요한 전부.
 *
 * @param date        평가 거래일. 종가 알림은 현재 봉이 이 날짜여야 한다. 장중이면 스냅샷의 현지 날짜다
 * @param asOf        데이터 시점 — 종가는 close_at, 장중은 snapshot_at. 완료 신호가 없으면 null
 * @param notDone     이 시점에 DONE이 아닌 데이터 종류 (§7.1)
 * @param missingDays 읽은 범위 안의 데이터 누락일 (계획 A.6)
 * @param allowedGap  장중 스냅샷의 허용 지연 — 국내 10분, 미국 20분 (§16.2)
 */
public record EvaluationInput(Cadence cadence, Basis basis, Market market, LocalDate date, OffsetDateTime asOf,
                              Series series, Set<DataKind> notDone, Set<LocalDate> missingDays,
                              boolean instrumentKnown, Duration allowedGap) {

    public EvaluationInput {
        notDone = notDone.isEmpty() ? Set.of() : EnumSet.copyOf(notDone);
        missingDays = Set.copyOf(missingDays);
    }

    public static Duration allowedGap(Market market) {
        return market == Market.US ? Duration.ofMinutes(20) : Duration.ofMinutes(10);
    }

    /** 그 시장에 완료 신호가 하나도 없다 — 모든 조건이 DATA_MISSING이다. */
    public static EvaluationInput noData(Cadence cadence, Market market) {
        return new EvaluationInput(cadence, cadence == Cadence.INTRADAY ? Basis.INTRADAY : Basis.DAILY, market,
                null, null, Series.empty(), EnumSet.allOf(DataKind.class), Set.of(), true, allowedGap(market));
    }
}
```

`alert/evaluation/ConditionResult.java`:

```java
package com.stockproject.portfolio.alert.evaluation;

import java.math.BigDecimal;

/**
 * 조건 하나의 평가. left · right는 현재 시점의 양쪽 값(계산할 수 없으면 null)이고,
 * progress는 연속이면 현재 봉부터 이어진 참 봉 수, 지속이면 이어진 분이다.
 */
public record ConditionResult(Truth truth, UnknownReason reason, BigDecimal left, BigDecimal right,
                              Integer progress) {

    public static ConditionResult unknown(UnknownReason reason) {
        return new ConditionResult(Truth.UNKNOWN, reason, null, null, null);
    }
}
```

`alert/evaluation/EvaluationResult.java`:

```java
package com.stockproject.portfolio.alert.evaluation;

import java.time.OffsetDateTime;
import java.util.List;

/** 알림 하나의 평가. reason은 truth가 UNKNOWN일 때 첫 확인 불가 조건의 사유다. */
public record EvaluationResult(Truth truth, UnknownReason reason, OffsetDateTime asOf, Basis basis,
                               List<ConditionResult> conditions) {

    public EvaluationResult {
        conditions = List.copyOf(conditions);
    }
}
```

- [ ] **Step 5: 평가기를 쓴다**

`alert/evaluation/ConditionEvaluator.java`:

```java
package com.stockproject.portfolio.alert.evaluation;

import com.stockproject.portfolio.alert.catalog.AlertCatalog;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.DataKind;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.catalog.Scope;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.compile.DataNeeds;
import com.stockproject.portfolio.alert.compile.RequiredBars;
import com.stockproject.portfolio.alert.indicator.Bar;
import com.stockproject.portfolio.alert.indicator.FlowBar;
import com.stockproject.portfolio.alert.indicator.IndicatorCalculator;
import com.stockproject.portfolio.alert.indicator.Series;
import com.stockproject.portfolio.alert.indicator.Snapshot;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.domain.Market;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

/**
 * 한 데이터 시점의 3값 평가 (스펙 §6.1 · §7).
 *
 * <p>조건마다 확인 불가를 먼저 가린다 — 종목 없음, 기다리는 데이터가 DONE이 아님,
 * 현재 값의 부재(거래 없음·미보유·이월값), 연속·교차 구간의 데이터 누락일,
 * 국내 ±30% 변동. 그 뒤에 값을 계산하고, 계산할 봉이 모자라면 이력 부족이다.</p>
 */
public final class ConditionEvaluator {

    private ConditionEvaluator() { }

    private static final BigDecimal ADJUSTMENT_LIMIT = new BigDecimal("0.30");

    public static EvaluationResult evaluate(CompiledTrigger trigger, EvaluationInput in) {
        List<ConditionResult> results = new ArrayList<>();
        for (Condition c : trigger.conditions()) results.add(evaluate(c, in));

        Truth truth = Truth.TRUE;
        UnknownReason reason = null;
        for (ConditionResult r : results) {
            if (r.truth() == Truth.FALSE) {
                truth = Truth.FALSE;
                reason = null;
                break;
            }
            if (r.truth() == Truth.UNKNOWN && truth == Truth.TRUE) {
                truth = Truth.UNKNOWN;
                reason = r.reason();
            }
        }
        return new EvaluationResult(truth, reason, in.asOf(), in.basis(), results);
    }

    public static ConditionResult evaluate(Condition c, EvaluationInput in) {
        if (!in.instrumentKnown()) return ConditionResult.unknown(UnknownReason.INSTRUMENT_UNKNOWN);

        List<Operand> operands = c.right().isConstant() ? List.of(c.left()) : List.of(c.left(), c.right().operand());
        for (Operand o : operands) {
            for (DataKind kind : DataNeeds.of(o, in.cadence())) {
                if (in.notDone().contains(kind)) return ConditionResult.unknown(UnknownReason.DATA_MISSING);
            }
        }
        for (Operand o : operands) {
            UnknownReason absent = absent(o, in);
            if (absent != null) return ConditionResult.unknown(absent);
        }
        if (spansMissingDay(c, operands, in)) return ConditionResult.unknown(UnknownReason.DATA_MISSING);
        if (adjustmentSuspected(c, operands, in)) {
            return ConditionResult.unknown(UnknownReason.PRICE_ADJUSTMENT_SUSPECTED);
        }

        if (c.op().isCross()) return cross(c, in);
        return switch (c.modifier()) {
            case null -> plain(c, in);
            case Modifier.Streak s -> streak(c, s.n(), in);
            case Modifier.PersistMin p -> in.basis() == Basis.INTRADAY ? persist(c, p.minutes(), in) : plain(c, in);
        };
    }

    // ---- 확인 불가 판정 -----------------------------------------------------------

    /** 현재 값이 있어야 할 자리에 없는가 (§7.2). */
    private static UnknownReason absent(Operand o, EvaluationInput in) {
        Series s = in.series();
        if (AlertCatalog.indicator(o.indicator()).scope() == Scope.USER) {
            if (s.holding() == null) return UnknownReason.NOT_HELD;
            return s.holding().carriedForward() ? UnknownReason.DATA_MISSING : null;
        }
        if (in.cadence() == Cadence.INTRADAY) {
            return IndicatorCalculator.isLive(o) && s.snapshots().isEmpty() ? UnknownReason.NO_TRADE : null;
        }
        LocalDate current = IndicatorCalculator.isFlow(o.indicator())
                ? (s.lastFlow() == null ? null : s.lastFlow().date())
                : (s.lastBar() == null ? null : s.lastBar().date());
        return current == null || !current.equals(in.date()) ? UnknownReason.NO_TRADE : null;
    }

    /**
     * 연속·교차 구간 — 현재 봉부터 streak − 1개 앞 봉까지, 교차는 직전 1봉까지 — 안에
     * 데이터 누락일이 있는가 (§7.2, 계획 A.6). 종가 알림에만 있다.
     */
    private static boolean spansMissingDay(Condition c, List<Operand> operands, EvaluationInput in) {
        if (in.cadence() != Cadence.CLOSE || in.missingDays().isEmpty()) return false;
        int span = c.op().isCross() ? 1 : c.modifier() instanceof Modifier.Streak s ? s.n() - 1 : 0;
        if (span == 0) return false;
        for (Operand o : operands) {
            List<LocalDate> dates = IndicatorCalculator.isFlow(o.indicator())
                    ? in.series().flows().stream().map(FlowBar::date).toList()
                    : in.series().bars().stream().map(Bar::date).toList();
            int startIndex = dates.size() - 1 - span;
            if (startIndex < 0) continue;   // 이력 부족으로 판정된다
            LocalDate start = dates.get(startIndex);
            for (LocalDate missing : in.missingDays()) {
                if (missing.isAfter(start) && missing.isBefore(in.date())) return true;
            }
        }
        return false;
    }

    /** 국내 종목에서 그 조건이 읽는 봉 범위 안에 하루 ±30%를 넘는 변동이 있는가 (§7.3, 계획 A.7). */
    private static boolean adjustmentSuspected(Condition c, List<Operand> operands, EvaluationInput in) {
        if (in.market() != Market.KR) return false;
        boolean readsBars = operands.stream().anyMatch(o ->
                AlertCatalog.indicator(o.indicator()).scope() == Scope.MARKET
                        && !IndicatorCalculator.isFlow(o.indicator())
                        && !(in.cadence() == Cadence.INTRADAY && IndicatorCalculator.isLive(o)));
        if (!readsBars) return false;
        List<Bar> bars = in.series().bars();
        int from = Math.max(1, bars.size() - RequiredBars.toRead(c));
        for (int j = from; j < bars.size(); j++) {
            BigDecimal prev = bars.get(j - 1).close();
            if (prev.signum() == 0) continue;
            BigDecimal move = bars.get(j).close().divide(prev, java.math.MathContext.DECIMAL64)
                    .subtract(BigDecimal.ONE).abs();
            if (move.compareTo(ADJUSTMENT_LIMIT) > 0) return true;
        }
        return false;
    }

    // ---- 값 비교 ----------------------------------------------------------------

    private static ConditionResult plain(Condition c, EvaluationInput in) {
        BigDecimal l = left(c, in, 0);
        BigDecimal r = right(c, in, 0);
        if (l == null || r == null) {
            return new ConditionResult(Truth.UNKNOWN, UnknownReason.INSUFFICIENT_HISTORY, l, r, null);
        }
        return new ConditionResult(Truth.of(compare(c.op(), l, r)), null, l, r, null);
    }

    /** 직전 시점과 이번 시점의 두 값을 견준다. 장중은 같은 날 직전 스냅샷이 직전 시점이다(§5.2). */
    private static ConditionResult cross(Condition c, EvaluationInput in) {
        BigDecimal l0 = left(c, in, 0);
        BigDecimal r0 = right(c, in, 0);
        BigDecimal l1 = left(c, in, 1);
        BigDecimal r1 = right(c, in, 1);
        if (l0 == null || r0 == null || l1 == null || r1 == null) {
            return new ConditionResult(Truth.UNKNOWN, UnknownReason.INSUFFICIENT_HISTORY, l0, r0, null);
        }
        boolean crossed = c.op() == OperatorKey.CROSSES_ABOVE
                ? l1.compareTo(r1) <= 0 && l0.compareTo(r0) > 0
                : l1.compareTo(r1) >= 0 && l0.compareTo(r0) < 0;
        return new ConditionResult(Truth.of(crossed), null, l0, r0, null);
    }

    /** 현재 봉부터 n봉이 모두 참이어야 한다. 하나라도 거짓이면 거짓이 먼저다. */
    private static ConditionResult streak(Condition c, int n, EvaluationInput in) {
        boolean anyFalse = false;
        boolean anyUnknown = false;
        int run = 0;
        boolean running = true;
        for (int k = 0; k < n; k++) {
            BigDecimal l = left(c, in, k);
            BigDecimal r = right(c, in, k);
            if (l == null || r == null) {
                anyUnknown = true;
                running = false;
                continue;
            }
            boolean ok = compare(c.op(), l, r);
            if (!ok) anyFalse = true;
            if (ok && running) run++;
            else running = false;
        }
        BigDecimal l0 = left(c, in, 0);
        BigDecimal r0 = right(c, in, 0);
        if (anyFalse) return new ConditionResult(Truth.FALSE, null, l0, r0, run);
        if (anyUnknown) return new ConditionResult(Truth.UNKNOWN, UnknownReason.INSUFFICIENT_HISTORY, l0, r0, run);
        return new ConditionResult(Truth.TRUE, null, l0, r0, run);
    }

    /**
     * 참인 스냅샷이 끊김 없이 이어진 구간의 시작부터 현재까지가 N분 이상이면 참 (§4.2).
     * 구간을 현재에서 거슬러 오르며 N분에 닿으면 멈춘다 — 그보다 앞의 공백은 판정에 쓰이지 않는다.
     * 닿기 전에 허용 지연을 넘는 공백이나 계산할 수 없는 스냅샷을 만나면 확인 불가다.
     */
    private static ConditionResult persist(Condition c, int minutes, EvaluationInput in) {
        List<Snapshot> snaps = in.series().snapshots();
        BigDecimal l0 = left(c, in, 0);
        BigDecimal r0 = right(c, in, 0);
        if (l0 == null || r0 == null) {
            return new ConditionResult(Truth.UNKNOWN, UnknownReason.INSUFFICIENT_HISTORY, l0, r0, null);
        }
        if (!compare(c.op(), l0, r0)) return new ConditionResult(Truth.FALSE, null, l0, r0, 0);

        Snapshot current = snaps.get(snaps.size() - 1);
        Snapshot start = current;
        for (int k = 1; k < snaps.size(); k++) {
            if (elapsed(start, current) >= minutes) break;
            Snapshot earlier = snaps.get(snaps.size() - 1 - k);
            if (Duration.between(earlier.at(), start.at()).compareTo(in.allowedGap()) > 0) {
                return new ConditionResult(Truth.UNKNOWN, UnknownReason.DATA_MISSING, l0, r0, null);
            }
            BigDecimal l = left(c, in, k);
            BigDecimal r = right(c, in, k);
            if (l == null || r == null) {
                return new ConditionResult(Truth.UNKNOWN, UnknownReason.INSUFFICIENT_HISTORY, l0, r0, null);
            }
            if (!compare(c.op(), l, r)) break;
            start = earlier;
        }
        int held = elapsed(start, current);
        return new ConditionResult(Truth.of(held >= minutes), null, l0, r0, held);
    }

    private static int elapsed(Snapshot from, Snapshot to) {
        return (int) Duration.between(from.at(), to.at()).toMinutes();
    }

    private static BigDecimal left(Condition c, EvaluationInput in, int shift) {
        return IndicatorCalculator.value(c.left(), in.series(), in.cadence(), shift);
    }

    private static BigDecimal right(Condition c, EvaluationInput in, int shift) {
        return c.right().isConstant()
                ? c.right().constant()
                : IndicatorCalculator.value(c.right().operand(), in.series(), in.cadence(), shift);
    }

    private static boolean compare(OperatorKey op, BigDecimal l, BigDecimal r) {
        int cmp = l.compareTo(r);
        return switch (op) {
            case GTE -> cmp >= 0;
            case LTE -> cmp <= 0;
            case GT -> cmp > 0;
            case LT -> cmp < 0;
            case CROSSES_ABOVE, CROSSES_BELOW -> throw new IllegalArgumentException("교차는 cross()에서 다룬다");
        };
    }
}
```

- [ ] **Step 6: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.evaluation.*' --tests 'com.stockproject.portfolio.alert.compile.*'`
Expected: PASS

- [ ] **Step 7: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/compile/DataNeeds.java \
        src/main/java/com/stockproject/portfolio/alert/evaluation \
        src/test/java/com/stockproject/portfolio/alert/compile/DataNeedsTest.java \
        src/test/java/com/stockproject/portfolio/alert/evaluation
git commit -m "feat: 알림 조건을 3값으로 평가하고 확인 불가 사유를 가린다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 문장 — 짧은 형 · 문장형 · 관측값 줄 · 머리

문장은 모두 서버가 만든다(§12.1). 미리보기·목록·상세가 이 클래스를 쓰고, ②의 발화 문구도 같은 관측값 줄을 쓴다.

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/sentence/` 아래 `Josa.java` · `Numbers.java` · `OperandNames.java` · `Summary.java` · `Line.java` · `SentenceWriter.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/sentence/NumbersTest.java` · `SentenceWriterTest.java`

**Interfaces:**
- Consumes: Task 4 `CompiledTrigger` · `RequiredBars`, Task 6 `Series` · `IndicatorCalculator.isLive` · `isFlow`, Task 7 평가 타입.
- Produces:
  - `final class Josa` — `static String iGa(String word)`(이/가를 붙인 말), `static String eulReul(String word)`.
  - `final class Numbers` — `static String observed(BigDecimal, Unit, Market, boolean signed)` · `static String threshold(BigDecimal, Unit, Market)` · `static String money(BigDecimal, boolean signed)` · `static String date(LocalDate)`(`9/26`) · `static String time(OffsetDateTime)`(한국 시간 `10:15`).
  - `final class OperandNames` — `static String name(Operand, Cadence)` · `static Unit displayUnit(Operand)` · `static boolean signed(Operand)`.
  - `record Summary(String shortText, String sentence)`
  - `record Line(Truth result, UnknownReason reason, String text)`
  - `final class SentenceWriter` — `static Summary summary(CompiledTrigger, Cadence, Market)` · `static List<Line> lines(CompiledTrigger, EvaluationResult, EvaluationInput)` · `static String asOfLabel(CompiledTrigger, EvaluationResult, EvaluationInput)`(`10:15 기준` · `9/26 종가 기준` …, ②의 본문 끝) · `static String header(CompiledTrigger, EvaluationResult, EvaluationInput)` · `static String resultText(Truth)`.

머리 문구는 §12.8을 따른다 — 장중 값이면 `지금 · 10:15 기준`, 일봉 값이면 `9/26 종가 기준`. 프리셋의 짧은 형은 §12.1의 프리셋 문장 틀을 따른다(`RSI(14) 70 이상 진입`).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/sentence/NumbersTest.java`:

```java
package com.stockproject.portfolio.alert.sentence;

import com.stockproject.portfolio.alert.catalog.Unit;
import com.stockproject.portfolio.domain.Market;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;

import static org.assertj.core.api.Assertions.assertThat;

/** 표시 규칙 (스펙 §12.6). */
class NumbersTest {

    @Test
    void 가격() {
        assertThat(Numbers.observed(new BigDecimal("70200.4"), Unit.PRICE, Market.KR, false)).isEqualTo("70,200원");
        assertThat(Numbers.observed(new BigDecimal("612.3"), Unit.PRICE, Market.US, false)).isEqualTo("$612.30");
        assertThat(Numbers.threshold(new BigDecimal("70000"), Unit.PRICE, Market.KR)).isEqualTo("70,000원");
        assertThat(Numbers.threshold(new BigDecimal("1500"), Unit.PRICE, Market.US)).isEqualTo("$1,500.00");
    }

    @Test
    void 퍼센트는_관측값에만_부호를_붙인다() {
        assertThat(Numbers.observed(new BigDecimal("5.44"), Unit.PERCENT, Market.KR, true)).isEqualTo("+5.4%");
        assertThat(Numbers.observed(new BigDecimal("-10"), Unit.PERCENT, Market.KR, true)).isEqualTo("−10.0%");
        assertThat(Numbers.observed(new BigDecimal("11.24"), Unit.PERCENT, Market.KR, false)).isEqualTo("11.2%");
        assertThat(Numbers.threshold(new BigDecimal("5.0"), Unit.PERCENT, Market.KR)).isEqualTo("5%");
        assertThat(Numbers.threshold(new BigDecimal("-10"), Unit.PERCENT, Market.KR)).isEqualTo("−10%");
    }

    @Test
    void 거래량_배수_지수() {
        assertThat(Numbers.observed(new BigDecimal("1234567"), Unit.SHARES, Market.KR, false)).isEqualTo("1,234,567주");
        assertThat(Numbers.observed(new BigDecimal("3.36"), Unit.RATIO, Market.KR, false)).isEqualTo("3.4배");
        assertThat(Numbers.threshold(new BigDecimal("3"), Unit.RATIO, Market.KR)).isEqualTo("3배");
        assertThat(Numbers.observed(new BigDecimal("71.26"), Unit.INDEX, Market.KR, false)).isEqualTo("71.3");
        assertThat(Numbers.threshold(new BigDecimal("70"), Unit.INDEX, Market.KR)).isEqualTo("70");
    }

    @Test
    void 수급_금액은_억_만_단위다() {
        assertThat(Numbers.money(new BigDecimal("31200000000"), true)).isEqualTo("+312억원");
        assertThat(Numbers.money(new BigDecimal("-45000000"), true)).isEqualTo("−4,500만원");
        assertThat(Numbers.money(new BigDecimal("100000000000"), false)).isEqualTo("1,000억원");
        assertThat(Numbers.money(new BigDecimal("9000"), true)).isEqualTo("+9,000원");
        assertThat(Numbers.observed(null, Unit.PRICE, Market.KR, false)).isEqualTo("—");
    }

    @Test
    void 날짜와_시각() {
        assertThat(Numbers.date(LocalDate.of(2026, 9, 26))).isEqualTo("9/26");
        assertThat(Numbers.time(OffsetDateTime.parse("2026-09-26T13:15:00-04:00"))).isEqualTo("02:15");
    }
}
```

`src/test/java/com/stockproject/portfolio/alert/sentence/SentenceWriterTest.java`:

```java
package com.stockproject.portfolio.alert.sentence;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.catalog.PresetKey;
import com.stockproject.portfolio.alert.catalog.WindowFn;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.compile.Compiler;
import com.stockproject.portfolio.alert.evaluation.Basis;
import com.stockproject.portfolio.alert.evaluation.ConditionResult;
import com.stockproject.portfolio.alert.evaluation.EvaluationInput;
import com.stockproject.portfolio.alert.evaluation.EvaluationResult;
import com.stockproject.portfolio.alert.evaluation.Truth;
import com.stockproject.portfolio.alert.evaluation.UnknownReason;
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

import static com.stockproject.portfolio.alert.indicator.SeriesFixtures.closes;
import static org.assertj.core.api.Assertions.assertThat;

class SentenceWriterTest {

    private static final Transform ID = new Transform.Identity();

    // ---- 조립형 요약 (§12.1 · §13) ----------------------------------------------

    @Test
    void 연속_조건의_두_문체() {
        Summary s = composable(Cadence.CLOSE, Market.KR, new Condition(
                new Operand(IndicatorKey.RSI, Map.of("n", 14), ID), OperatorKey.GTE,
                Right.constant(new BigDecimal("70")), new Modifier.Streak(3)));

        assertThat(s.shortText()).isEqualTo("종가 · RSI(14) 3일 연속 ≥ 70");
        assertThat(s.sentence()).isEqualTo("종가 기준으로 RSI(14)가 3일 연속 70 이상이면 알려요");
    }

    @Test
    void 장중_지속_조건과_직전_윈도우() {
        Summary s = composable(Cadence.INTRADAY, Market.KR, new Condition(
                new Operand(IndicatorKey.PRICE, Map.of(), ID), OperatorKey.GT,
                Right.operand(new Operand(IndicatorKey.HIGH, Map.of(), new Transform.Window(WindowFn.MAX, 20, null))),
                new Modifier.PersistMin(10)));

        assertThat(s.shortText()).isEqualTo("장중 · 현재가 > 직전 20일 최고 고가 10분 유지");
        assertThat(s.sentence()).isEqualTo("장중에 현재가가 직전 20일 최고 고가 초과인 상태가 10분 이상 유지되면 알려요");
    }

    @Test
    void 두_조건은_그리고와_이고로_잇는다() {
        Summary s = composable(Cadence.CLOSE, Market.KR,
                new Condition(sma(5), OperatorKey.GT, Right.operand(sma(20)), null),
                new Condition(new Operand(IndicatorKey.VOLUME_RATIO, Map.of("n", 20), ID), OperatorKey.GTE,
                        Right.constant(new BigDecimal("2")), null));

        assertThat(s.shortText()).isEqualTo("종가 · 5일 이동평균 > 20일 이동평균 그리고 거래량 배수(20일) ≥ 2배");
        assertThat(s.sentence()).isEqualTo(
                "종가 기준으로 5일 이동평균이 20일 이동평균 초과이고, 거래량 배수(20일)가 2배 이상이면 알려요");
    }

    @Test
    void 최근_윈도우와_교차와_미국() {
        Summary flow = composable(Cadence.CLOSE, Market.KR, new Condition(
                new Operand(IndicatorKey.FOREIGN_NET_BUY, Map.of(), new Transform.Window(WindowFn.SUM, 5, null)),
                OperatorKey.GTE, Right.constant(new BigDecimal("100000000000")), null));
        assertThat(flow.shortText()).isEqualTo("종가 · 최근 5일 외국인 순매수 합계 ≥ 1,000억원");

        Summary cross = composable(Cadence.CLOSE, Market.US,
                new Condition(sma(5), OperatorKey.CROSSES_ABOVE, Right.operand(sma(20)), null));
        assertThat(cross.shortText()).isEqualTo("미국 종가 · 5일 이동평균이 20일 이동평균 상향 돌파");
        assertThat(cross.sentence()).isEqualTo("종가 기준으로 5일 이동평균이 20일 이동평균을 상향 돌파하면 알려요");
    }

    // ---- 프리셋 요약 (§12.1 표) --------------------------------------------------

    @Test
    void 프리셋은_전용_문장이다() {
        assertThat(preset(PresetKey.PRICE_REACH, Cadence.INTRADAY, Market.KR,
                Map.of("direction", "up", "price", new BigDecimal("70000"))))
                .isEqualTo(new Summary("장중 · 현재가 ≥ 70,000원", "장중에 현재가가 70,000원 이상이면 알려요"));
        assertThat(preset(PresetKey.CHANGE_MOVE, Cadence.INTRADAY, Market.KR, Map.of()).shortText())
                .isEqualTo("장중 · 5% 이상 상승");
        assertThat(preset(PresetKey.VOLUME_SURGE, Cadence.CLOSE, Market.KR, Map.of()).shortText())
                .isEqualTo("종가 · 거래량 20일 평균의 3배 이상");
        assertThat(preset(PresetKey.MA_CROSS, Cadence.CLOSE, Market.KR, Map.of()).shortText())
                .isEqualTo("종가 · 5일선이 20일선 상향 돌파");
        assertThat(preset(PresetKey.RSI_ZONE, Cadence.CLOSE, Market.KR, Map.of()))
                .isEqualTo(new Summary("종가 · RSI(14) 70 이상 진입", "종가 기준으로 RSI(14)가 70 이상이면 알려요"));
        assertThat(preset(PresetKey.BOX_BREAKOUT, Cadence.CLOSE, Market.KR, Map.of()).shortText())
                .isEqualTo("종가 · 20일 박스권(폭 15% 이내) 상단 돌파");
        assertThat(preset(PresetKey.INVESTOR_STREAK, Cadence.CLOSE, Market.KR, Map.of()).shortText())
                .isEqualTo("종가 · 외국인 3일 연속 순매수");
        assertThat(preset(PresetKey.INVESTOR_TURN, Cadence.CLOSE, Market.KR, Map.of("side", "sell")).shortText())
                .isEqualTo("종가 · 외국인 순매도 전환");
        assertThat(preset(PresetKey.PNL_REACH, Cadence.CLOSE, Market.US, Map.of("direction", "loss")))
                .isEqualTo(new Summary("종가 · 손실 10% 도달", "종가 기준으로 평가손익률이 −10% 이하이면 알려요"));
    }

    // ---- 관측값 줄 · 머리 · 결과 줄 -----------------------------------------------

    @Test
    void 조립형은_조건마다_관측값_줄이다() {
        CompiledTrigger t = Compiler.compile(new TriggerSpec.Composable(List.of(
                new Condition(sma(5), OperatorKey.GT, Right.operand(sma(20)), null),
                new Condition(new Operand(IndicatorKey.RSI, Map.of("n", 14), ID), OperatorKey.GTE,
                        Right.constant(new BigDecimal("70")), new Modifier.Streak(3)))), Cadence.CLOSE);
        EvaluationResult r = result(Truth.UNKNOWN, UnknownReason.INSUFFICIENT_HISTORY,
                new ConditionResult(Truth.TRUE, null, new BigDecimal("72100"), new BigDecimal("70850"), null),
                new ConditionResult(Truth.UNKNOWN, UnknownReason.INSUFFICIENT_HISTORY, null, null, null));
        EvaluationInput in = close(Market.KR, 8);

        assertThat(SentenceWriter.lines(t, r, in)).containsExactly(
                new Line(Truth.TRUE, null, "5일 이동평균 72,100원 > 20일 이동평균 70,850원"),
                new Line(Truth.UNKNOWN, UnknownReason.INSUFFICIENT_HISTORY, "RSI(14) — 이력 부족 (17일 필요, 8일뿐)"));
        assertThat(SentenceWriter.header(t, r, in)).isEqualTo("9/26 종가 기준");
        assertThat(SentenceWriter.resultText(r.truth())).isEqualTo("확인할 수 없어요");
    }

    @Test
    void 연속_관측값에는_진행_상황을_붙인다() {
        CompiledTrigger t = Compiler.compile(new TriggerSpec.Composable(List.of(new Condition(
                new Operand(IndicatorKey.RSI, Map.of("n", 14), ID), OperatorKey.GTE,
                Right.constant(new BigDecimal("70")), new Modifier.Streak(3)))), Cadence.CLOSE);
        EvaluationResult r = result(Truth.TRUE, null,
                new ConditionResult(Truth.TRUE, null, new BigDecimal("71.26"), new BigDecimal("70"), 3));

        assertThat(SentenceWriter.lines(t, r, close(Market.KR, 300))).extracting(Line::text)
                .containsExactly("RSI(14) 71.3 ≥ 70 · 3일째");
    }

    @Test
    void 프리셋은_관측값_줄_하나다() {
        CompiledTrigger box = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.BOX_BREAKOUT, Map.of()),
                Cadence.CLOSE);
        EvaluationResult r = result(Truth.TRUE, null,
                new ConditionResult(Truth.TRUE, null, new BigDecimal("11.24"), new BigDecimal("15"), null),
                new ConditionResult(Truth.TRUE, null, new BigDecimal("72100"), new BigDecimal("71800"), null));
        assertThat(SentenceWriter.lines(box, r, close(Market.KR, 300))).containsExactly(new Line(Truth.TRUE, null,
                "종가 72,100원 > 직전 20일 최고 고가 71,800원 (폭 11.2%)"));

        CompiledTrigger turn = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.INVESTOR_TURN, Map.of()),
                Cadence.CLOSE);
        EvaluationResult turned = result(Truth.TRUE, null,
                new ConditionResult(Truth.TRUE, null, new BigDecimal("31200000000"), BigDecimal.ZERO, null),
                new ConditionResult(Truth.TRUE, null, new BigDecimal("-4500000000"), BigDecimal.ZERO, null));
        assertThat(SentenceWriter.lines(turn, turned, close(Market.KR, 300))).extracting(Line::text)
                .containsExactly("외국인 +312억원 (어제 −45억원)");

        CompiledTrigger streak = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.INVESTOR_STREAK, Map.of()),
                Cadence.CLOSE);
        EvaluationResult streaking = result(Truth.TRUE, null,
                new ConditionResult(Truth.TRUE, null, new BigDecimal("31200000000"), BigDecimal.ZERO, 3));
        assertThat(SentenceWriter.lines(streak, streaking, close(Market.KR, 300))).extracting(Line::text)
                .containsExactly("외국인 +312억원 · 3일째");

        CompiledTrigger pnl = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.PNL_REACH,
                Map.of("direction", "loss")), Cadence.CLOSE);
        EvaluationResult unknown = result(Truth.UNKNOWN, UnknownReason.NOT_HELD,
                ConditionResult.unknown(UnknownReason.NOT_HELD));
        assertThat(SentenceWriter.lines(pnl, unknown, close(Market.KR, 300))).containsExactly(
                new Line(Truth.UNKNOWN, UnknownReason.NOT_HELD, "손실 10% 도달 — 미보유"));
    }

    @Test
    void 머리는_기준과_시장을_드러낸다() {
        CompiledTrigger price = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.PRICE_REACH,
                Map.of("direction", "up", "price", new BigDecimal("70000"))), Cadence.INTRADAY);
        EvaluationResult r = result(Truth.FALSE, null,
                new ConditionResult(Truth.FALSE, null, new BigDecimal("69000"), new BigDecimal("70000"), null));

        OffsetDateTime kst = OffsetDateTime.parse("2026-09-26T10:15:00+09:00");
        assertThat(SentenceWriter.header(price, withAsOf(r, kst), live(Market.KR, kst))).isEqualTo("지금 · 10:15 기준");
        assertThat(SentenceWriter.asOfLabel(price, withAsOf(r, kst), live(Market.KR, kst))).isEqualTo("10:15 기준");

        OffsetDateTime us = OffsetDateTime.parse("2026-09-27T02:15:00+09:00");
        assertThat(SentenceWriter.header(price, withAsOf(r, us), live(Market.US, us)))
                .isEqualTo("미국 장중 · 02:15 기준");
        assertThat(SentenceWriter.header(price, r, close(Market.US, 300))).isEqualTo("미국 9/26 종가 기준");

        EvaluationResult none = new EvaluationResult(Truth.UNKNOWN, UnknownReason.DATA_MISSING, null, Basis.DAILY,
                List.of(ConditionResult.unknown(UnknownReason.DATA_MISSING)));
        assertThat(SentenceWriter.header(price, none, EvaluationInput.noData(Cadence.CLOSE, Market.KR)))
                .isEqualTo("데이터 없음");
        assertThat(SentenceWriter.resultText(Truth.TRUE)).isEqualTo("충족하고 있어요");
        assertThat(SentenceWriter.resultText(Truth.FALSE)).isEqualTo("아직 충족하지 않아요");
    }

    // ---- 도우미 ----------------------------------------------------------------

    private static Operand sma(int n) { return new Operand(IndicatorKey.SMA, Map.of("n", n), ID); }

    private static Summary composable(Cadence cadence, Market market, Condition... conditions) {
        return SentenceWriter.summary(Compiler.compile(new TriggerSpec.Composable(List.of(conditions)), cadence),
                cadence, market);
    }

    private static Summary preset(PresetKey key, Cadence cadence, Market market, Map<String, Object> params) {
        return SentenceWriter.summary(Compiler.compile(new TriggerSpec.PresetTrigger(key, params), cadence),
                cadence, market);
    }

    private static EvaluationResult result(Truth truth, UnknownReason reason, ConditionResult... conditions) {
        return new EvaluationResult(truth, reason, OffsetDateTime.parse("2026-09-26T15:30:00+09:00"), Basis.DAILY,
                List.of(conditions));
    }

    private static EvaluationResult withAsOf(EvaluationResult r, OffsetDateTime asOf) {
        return new EvaluationResult(r.truth(), r.reason(), asOf, Basis.INTRADAY, r.conditions());
    }

    /** 2026-09-26 종가 평가. 봉은 bars개다. */
    private static EvaluationInput close(Market market, int bars) {
        String[] values = new String[bars];
        java.util.Arrays.fill(values, "100");
        return new EvaluationInput(Cadence.CLOSE, Basis.DAILY, market, LocalDate.of(2026, 9, 26),
                OffsetDateTime.parse("2026-09-26T15:30:00+09:00"),
                new Series(closes(values), List.of(), List.of(), null), Set.of(), Set.of(), true,
                Duration.ofMinutes(10));
    }

    private static EvaluationInput live(Market market, OffsetDateTime at) {
        return new EvaluationInput(Cadence.INTRADAY, Basis.INTRADAY, market, at.toLocalDate(), at, Series.empty(),
                Set.of(), Set.of(), true, EvaluationInput.allowedGap(market));
    }
}
```

`RSI(14)` 3일 연속의 필요 봉 수는 15 + 2 = 17이다(§5.4).

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.sentence.*'`
Expected: FAIL — 컴파일 오류

- [ ] **Step 3: 조사와 숫자 표기를 쓴다**

`alert/sentence/Josa.java`:

```java
package com.stockproject.portfolio.alert.sentence;

/**
 * 받침에 따라 이/가 · 을/를을 붙인다. 괄호로 끝나면 괄호 안을 읽지 않으므로 괄호 앞 글자를 본다
 * (거래량 배수(20일)가 · RSI(14)가). 숫자와 Latin 문자는 읽는 소리로 판정한다
 * (0 영, 1 일, 3 삼, 6 육, 7 칠, 8 팔 · L M N R은 받침이 있다).
 */
public final class Josa {

    private Josa() { }

    public static String iGa(String word) { return word + (hasBatchim(word) ? "이" : "가"); }

    public static String eulReul(String word) { return word + (hasBatchim(word) ? "을" : "를"); }

    static boolean hasBatchim(String word) {
        int i = word.length() - 1;
        if (word.charAt(i) == ')' && word.lastIndexOf('(') > 0) i = word.lastIndexOf('(') - 1;
        while (i > 0 && word.charAt(i) == ' ') i--;
        char c = word.charAt(i);
        if (c >= '가' && c <= '힣') return (c - '가') % 28 != 0;
        if (c >= '0' && c <= '9') return "013678".indexOf(c) >= 0;
        if (Character.isLetter(c)) return "LMNRlmnr".indexOf(c) >= 0;
        return false;
    }
}
```

`alert/sentence/Numbers.java`:

```java
package com.stockproject.portfolio.alert.sentence;

import com.stockproject.portfolio.alert.catalog.Unit;
import com.stockproject.portfolio.domain.Market;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.text.DecimalFormat;
import java.text.DecimalFormatSymbols;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Locale;

/**
 * 숫자·날짜 표기 (스펙 §12.6). 관측값은 정해진 자릿수로 반올림하고, 조건의 기준값은
 * 사용자가 넣은 값 그대로(꼬리 0만 떼고) 쓴다. 음수 부호는 −(U+2212)다.
 */
public final class Numbers {

    private Numbers() { }

    private static final String MINUS = "−";
    private static final BigDecimal EOK = new BigDecimal("100000000");
    private static final BigDecimal MAN = new BigDecimal("10000");
    private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");
    private static final DateTimeFormatter TIME = DateTimeFormatter.ofPattern("HH:mm");

    public static String observed(BigDecimal value, Unit unit, Market market, boolean signed) {
        if (value == null) return "—";
        return switch (unit) {
            case PRICE -> market == Market.US ? "$" + grouped(value, 2) : grouped(value, 0) + "원";
            case PERCENT -> sign(value, signed) + grouped(value.abs(), 1) + "%";
            case SHARES -> sign(value, signed) + grouped(value.abs(), 0) + "주";
            case RATIO -> grouped(value, 1) + "배";
            case INDEX -> sign(value, signed) + grouped(value.abs(), 1);
            case KRW -> money(value, signed);
        };
    }

    public static String threshold(BigDecimal value, Unit unit, Market market) {
        return switch (unit) {
            case PRICE -> market == Market.US ? "$" + grouped(value, 2) : plain(value) + "원";
            case PERCENT -> plain(value) + "%";
            case SHARES -> plain(value) + "주";
            case RATIO -> plain(value) + "배";
            case INDEX -> plain(value);
            case KRW -> money(value, false);
        };
    }

    /** 억·만 단위 금액. 1억 이상은 억, 1만 이상은 만 단위로 반올림한다. */
    public static String money(BigDecimal value, boolean signed) {
        BigDecimal abs = value.abs();
        String body;
        if (abs.compareTo(EOK) >= 0) body = grouped(abs.divide(EOK), 0) + "억원";
        else if (abs.compareTo(MAN) >= 0) body = grouped(abs.divide(MAN), 0) + "만원";
        else body = grouped(abs, 0) + "원";
        String prefix = value.signum() < 0 ? MINUS : signed && value.signum() > 0 ? "+" : "";
        return prefix + body;
    }

    public static String date(LocalDate date) { return date.getMonthValue() + "/" + date.getDayOfMonth(); }

    /** 한국 시간의 시:분. 미국 장중 시각도 한국 시간으로 쓴다(§12.6). */
    public static String time(OffsetDateTime at) { return at.atZoneSameInstant(SEOUL).format(TIME); }

    private static String sign(BigDecimal value, boolean signed) {
        if (value.signum() < 0) return MINUS;
        return signed && value.signum() > 0 ? "+" : "";
    }

    /** 기준값: 꼬리 0을 떼고 천 단위를 묶는다. 음수는 −. */
    private static String plain(BigDecimal value) {
        BigDecimal abs = value.abs().stripTrailingZeros();
        String body = grouped(abs, Math.max(0, abs.scale()));
        return (value.signum() < 0 ? MINUS : "") + body;
    }

    private static String grouped(BigDecimal value, int scale) {
        DecimalFormat format = new DecimalFormat(scale == 0 ? "#,##0" : "#,##0." + "0".repeat(scale),
                DecimalFormatSymbols.getInstance(Locale.ROOT));
        format.setRoundingMode(RoundingMode.HALF_UP);
        String text = format.format(value.setScale(scale, RoundingMode.HALF_UP));
        return text.startsWith("-") ? MINUS + text.substring(1) : text;
    }
}
```

- [ ] **Step 4: 피연산자 이름을 쓴다**

`alert/sentence/OperandNames.java`:

```java
package com.stockproject.portfolio.alert.sentence;

import com.stockproject.portfolio.alert.catalog.AlertCatalog;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.Unit;
import com.stockproject.portfolio.alert.catalog.WindowFn;
import com.stockproject.portfolio.alert.indicator.IndicatorCalculator;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Transform;

/**
 * 피연산자의 이름 조각 (스펙 §12.1 조각 표).
 * 윈도우는 오늘을 뺐으면 직전, 넣었으면 최근이다. 장중 알림의 이력 피연산자는 lag 0이어도
 * 현재 봉이 이미 직전 거래일이라 직전이다(§4.2).
 */
public final class OperandNames {

    private OperandNames() { }

    public static String name(Operand o, Cadence cadence) {
        boolean live = cadence == Cadence.INTRADAY && IndicatorCalculator.isLive(o);
        String base = base(o, live);
        return switch (o.transform()) {
            case Transform.Identity i -> base;
            case Transform.Window w -> {
                String when = w.lagOrZero() == 1 || cadence == Cadence.INTRADAY ? "직전" : "최근";
                yield w.fn() == WindowFn.MAX || w.fn() == WindowFn.MIN
                        ? when + " " + w.n() + "일 " + w.fn().label() + " " + base
                        : when + " " + w.n() + "일 " + base + " " + w.fn().label();
            }
            case Transform.Delta d -> d.n() + "일 전 대비 " + base + " 변화";
            case Transform.Pct p -> p.n() + "일 전 대비 " + base + " 변화율";
        };
    }

    /** 표시 단위. 변화율은 퍼센트, 이격도는 RSI처럼 수치만 쓴다(§12.6). */
    public static Unit displayUnit(Operand o) {
        if (o.transform() instanceof Transform.Pct) return Unit.PERCENT;
        if (o.indicator() == IndicatorKey.DISPARITY) return Unit.INDEX;
        return AlertCatalog.indicator(o.indicator()).unit();
    }

    /** 관측값에 부호를 붙이는가 — 등락률·수익률·순매수 금액·변화량·변화율(§12.6). */
    public static boolean signed(Operand o) {
        if (o.transform() instanceof Transform.Delta || o.transform() instanceof Transform.Pct) return true;
        return switch (o.indicator()) {
            case CHANGE_PCT, UNREALIZED_PNL_PCT, FOREIGN_NET_BUY, INSTITUTION_NET_BUY -> true;
            default -> false;
        };
    }

    private static String base(Operand o, boolean live) {
        var indicator = AlertCatalog.indicator(o.indicator());
        return switch (o.indicator()) {
            case PRICE -> live ? "현재가" : "종가";
            case VOLUME -> live ? "오늘 거래량" : "거래량";
            case VOLUME_RATIO -> "거래량 배수(" + indicator.paramOrDefault(o.params(), "n") + "일)";
            case RANGE_PCT -> "가격 폭(" + indicator.paramOrDefault(o.params(), "n") + "일)";
            case SMA -> indicator.paramOrDefault(o.params(), "n") + "일 이동평균";
            case RSI -> "RSI(" + indicator.paramOrDefault(o.params(), "n") + ")";
            case DISPARITY -> "이격도(" + indicator.paramOrDefault(o.params(), "n") + ")";
            case CHANGE_PCT, HIGH, LOW, FOREIGN_NET_BUY, INSTITUTION_NET_BUY, UNREALIZED_PNL_PCT, WEIGHT_PCT ->
                    indicator.label();
        };
    }
}
```

`alert/sentence/Summary.java`:

```java
package com.stockproject.portfolio.alert.sentence;

/** 조건 문장의 두 문체 (스펙 §12.1). 짧은 형은 카드·푸시, 문장형은 상세·폼. */
public record Summary(String shortText, String sentence) { }
```

`alert/sentence/Line.java`:

```java
package com.stockproject.portfolio.alert.sentence;

import com.stockproject.portfolio.alert.evaluation.Truth;
import com.stockproject.portfolio.alert.evaluation.UnknownReason;

/** 현재값 상자 · 울린 이유 상자의 한 줄 — ✓ · ✕ · ? 와 관측값 문장. */
public record Line(Truth result, UnknownReason reason, String text) { }
```

- [ ] **Step 5: 문장 생성기를 쓴다**

`alert/sentence/SentenceWriter.java`:

```java
package com.stockproject.portfolio.alert.sentence;

import com.stockproject.portfolio.alert.catalog.AlertCatalog;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.catalog.PresetKey;
import com.stockproject.portfolio.alert.catalog.Scope;
import com.stockproject.portfolio.alert.catalog.Unit;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.compile.RequiredBars;
import com.stockproject.portfolio.alert.evaluation.Basis;
import com.stockproject.portfolio.alert.evaluation.ConditionResult;
import com.stockproject.portfolio.alert.evaluation.EvaluationInput;
import com.stockproject.portfolio.alert.evaluation.EvaluationResult;
import com.stockproject.portfolio.alert.evaluation.Truth;
import com.stockproject.portfolio.alert.evaluation.UnknownReason;
import com.stockproject.portfolio.alert.indicator.IndicatorCalculator;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.domain.Market;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 조건 문장 · 관측값 줄 · 머리 (스펙 §12.1 · §12.5.4 · §12.8).
 *
 * <p>조립형은 조각 규칙으로 조건마다 만든다. 프리셋은 프리셋 문장 틀을 쓰고, 관측값도 한 줄이다 —
 * 컴파일한 조건을 풀어 쓰면 프리셋을 고른 의도가 사라진다(§12.1).</p>
 */
public final class SentenceWriter {

    private SentenceWriter() { }

    // ---- 요약 -------------------------------------------------------------------

    public static Summary summary(CompiledTrigger t, Cadence cadence, Market market) {
        Market shown = shownMarket(t, market);
        String shortPrefix = (shown == Market.US ? "미국 " : "") + (cadence == Cadence.INTRADAY ? "장중 · " : "종가 · ");
        String sentencePrefix = cadence == Cadence.INTRADAY ? "장중에 " : "종가 기준으로 ";
        if (t.preset() != null) {
            return new Summary(shortPrefix + presetShort(t, cadence, market),
                    sentencePrefix + presetSentence(t, cadence, market) + " 알려요");
        }
        List<String> shorts = new ArrayList<>();
        List<String> clauses = new ArrayList<>();
        List<Condition> conditions = t.conditions();
        for (int i = 0; i < conditions.size(); i++) {
            shorts.add(conditionShort(conditions.get(i), cadence, market));
            clauses.add(clause(conditions.get(i), cadence, market, i == conditions.size() - 1));
        }
        return new Summary(shortPrefix + String.join(" 그리고 ", shorts),
                sentencePrefix + String.join(", ", clauses) + " 알려요");
    }

    private static String conditionShort(Condition c, Cadence cadence, Market market) {
        String left = OperandNames.name(c.left(), cadence);
        String right = rightText(c, cadence, market);
        if (c.op().isCross()) return Josa.iGa(left) + " " + right + " " + c.op().symbol();
        String streak = c.modifier() instanceof Modifier.Streak s ? s.n() + "일 연속 " : "";
        String persist = c.modifier() instanceof Modifier.PersistMin p ? " " + p.minutes() + "분 유지" : "";
        return left + " " + streak + c.op().symbol() + " " + right + persist;
    }

    /** 문장형의 절 하나. 마지막 절은 "…이면", 그 앞은 "…이고"로 끝난다(§12.1). */
    private static String clause(Condition c, Cadence cadence, Market market, boolean last) {
        String left = Josa.iGa(OperandNames.name(c.left(), cadence));
        String right = rightText(c, cadence, market);
        if (c.op().isCross()) {
            String verb = c.op() == OperatorKey.CROSSES_ABOVE ? "상향 돌파" : "하향 이탈";
            return left + " " + Josa.eulReul(right) + " " + verb + (last ? "하면" : "하고");
        }
        if (c.modifier() instanceof Modifier.PersistMin p) {
            return left + " " + right + " " + c.op().word() + "인 상태가 " + p.minutes() + "분 이상 유지"
                    + (last ? "되면" : "되고");
        }
        String streak = c.modifier() instanceof Modifier.Streak s ? s.n() + "일 연속 " : "";
        return left + " " + streak + right + " " + c.op().word() + (last ? "이면" : "이고");
    }

    private static String rightText(Condition c, Cadence cadence, Market market) {
        if (!c.right().isConstant()) return OperandNames.name(c.right().operand(), cadence);
        return Numbers.threshold(c.right().constant(), OperandNames.displayUnit(c.left()), market);
    }

    // ---- 프리셋 문장 틀 (§12.1 표) ----------------------------------------------

    private static String presetShort(CompiledTrigger t, Cadence cadence, Market market) {
        Map<String, Object> p = t.presetParams();
        return switch (t.preset()) {
            case PRICE_REACH -> conditionShort(t.conditions().get(0), cadence, market);
            case CHANGE_MOVE -> Numbers.threshold(num(p, "pct"), Unit.PERCENT, market) + " 이상 "
                    + ("up".equals(p.get("direction")) ? "상승" : "하락");
            case VOLUME_SURGE -> "거래량 " + num(p, "n").intValue() + "일 평균의 "
                    + Numbers.threshold(num(p, "multiple"), Unit.RATIO, market) + " 이상";
            case MA_CROSS -> num(p, "short").intValue() + "일선이 " + num(p, "long").intValue() + "일선 "
                    + ("golden".equals(p.get("direction")) ? "상향 돌파" : "하향 이탈");
            case RSI_ZONE -> "RSI(" + num(p, "n").intValue() + ") " + Numbers.threshold(num(p, "level"), Unit.INDEX, market)
                    + ("overbought".equals(p.get("zone")) ? " 이상 진입" : " 이하 진입");
            case BOX_BREAKOUT -> num(p, "window_days").intValue() + "일 박스권(폭 "
                    + Numbers.threshold(num(p, "max_range_pct"), Unit.PERCENT, market) + " 이내) "
                    + ("up".equals(p.get("direction")) ? "상단 돌파" : "하단 이탈");
            case INVESTOR_STREAK -> investor(p) + " " + num(p, "days").intValue() + "일 연속 " + side(p);
            case INVESTOR_TURN -> investor(p) + " " + side(p) + " 전환";
            case PNL_REACH -> ("profit".equals(p.get("direction")) ? "수익 " : "손실 ")
                    + Numbers.threshold(num(p, "pct"), Unit.PERCENT, market) + " 도달";
        };
    }

    private static String presetSentence(CompiledTrigger t, Cadence cadence, Market market) {
        Map<String, Object> p = t.presetParams();
        return switch (t.preset()) {
            case PRICE_REACH, RSI_ZONE, PNL_REACH -> clause(t.conditions().get(0), cadence, market, true);
            case CHANGE_MOVE -> Numbers.threshold(num(p, "pct"), Unit.PERCENT, market) + " 이상 "
                    + ("up".equals(p.get("direction")) ? "오르면" : "내리면");
            case VOLUME_SURGE -> (cadence == Cadence.INTRADAY ? "오늘 거래량이 " : "거래량이 ")
                    + num(p, "n").intValue() + "일 평균의 " + Numbers.threshold(num(p, "multiple"), Unit.RATIO, market)
                    + " 이상이면";
            case MA_CROSS -> num(p, "short").intValue() + "일선이 " + num(p, "long").intValue() + "일선을 "
                    + ("golden".equals(p.get("direction")) ? "상향 돌파하면" : "하향 이탈하면");
            case BOX_BREAKOUT -> num(p, "window_days").intValue() + "일 박스권(폭 "
                    + Numbers.threshold(num(p, "max_range_pct"), Unit.PERCENT, market) + " 이내)을 "
                    + ("up".equals(p.get("direction")) ? "상단 돌파하면" : "하단 이탈하면");
            case INVESTOR_STREAK -> Josa.iGa(investor(p)) + " " + num(p, "days").intValue() + "일 연속 "
                    + side(p) + "하면";
            case INVESTOR_TURN -> Josa.iGa(investor(p)) + " " + side(p) + "로 돌아서면";
        };
    }

    // ---- 관측값 줄 (§12.1 · §12.5.4) --------------------------------------------

    public static List<Line> lines(CompiledTrigger t, EvaluationResult r, EvaluationInput in) {
        Market market = in.market();
        if (t.preset() != null) {
            String text = r.truth() == Truth.UNKNOWN
                    ? presetShort(t, in.cadence(), market) + " — " + r.reason().label()
                    : presetObserved(t, r.conditions(), in.cadence(), market);
            return List.of(new Line(r.truth(), r.reason(), text));
        }
        List<Line> out = new ArrayList<>();
        for (int i = 0; i < t.conditions().size(); i++) {
            Condition c = t.conditions().get(i);
            ConditionResult cr = r.conditions().get(i);
            String text = cr.truth() == Truth.UNKNOWN
                    ? OperandNames.name(c.left(), in.cadence()) + " — " + unknownText(c, cr.reason(), in)
                    : observed(c, cr, in.cadence(), market);
            out.add(new Line(cr.truth(), cr.reason(), text));
        }
        return out;
    }

    private static String observed(Condition c, ConditionResult r, Cadence cadence, Market market) {
        String left = OperandNames.name(c.left(), cadence) + " " + value(c.left(), r.left(), market);
        String right = c.right().isConstant()
                ? Numbers.threshold(c.right().constant(), OperandNames.displayUnit(c.left()), market)
                : OperandNames.name(c.right().operand(), cadence) + " " + value(c.right().operand(), r.right(), market);
        if (c.op().isCross()) return Josa.iGa(left) + " " + right + " " + c.op().symbol();
        String progress = switch (c.modifier()) {
            case null -> "";
            case Modifier.Streak s -> r.progress() == null || r.progress() == 0 ? "" : " · " + r.progress() + "일째";
            case Modifier.PersistMin p -> r.progress() == null || r.progress() == 0 ? "" : " · " + r.progress() + "분째";
        };
        return left + " " + c.op().symbol() + " " + right + progress;
    }

    private static String presetObserved(CompiledTrigger t, List<ConditionResult> rs, Cadence cadence, Market market) {
        Map<String, Object> p = t.presetParams();
        ConditionResult first = rs.get(0);
        return switch (t.preset()) {
            case PRICE_REACH, CHANGE_MOVE, RSI_ZONE, PNL_REACH ->
                    observed(t.conditions().get(0), first, cadence, market);
            case VOLUME_SURGE -> (cadence == Cadence.INTRADAY ? "오늘 거래량 " : "거래량 ") + num(p, "n").intValue()
                    + "일 평균의 " + Numbers.observed(first.left(), Unit.RATIO, market, false) + " ≥ "
                    + Numbers.threshold(num(p, "multiple"), Unit.RATIO, market);
            case MA_CROSS -> Josa.iGa(num(p, "short").intValue() + "일선 "
                    + Numbers.observed(first.left(), Unit.PRICE, market, false)) + " "
                    + num(p, "long").intValue() + "일선 " + Numbers.observed(first.right(), Unit.PRICE, market, false)
                    + ("golden".equals(p.get("direction")) ? " 상향 돌파" : " 하향 이탈");
            case BOX_BREAKOUT -> {
                Condition edge = t.conditions().get(1);
                ConditionResult edgeResult = rs.get(1);
                yield "종가 " + Numbers.observed(edgeResult.left(), Unit.PRICE, market, false) + " "
                        + edge.op().symbol() + " " + OperandNames.name(edge.right().operand(), cadence) + " "
                        + Numbers.observed(edgeResult.right(), Unit.PRICE, market, false)
                        + " (폭 " + Numbers.observed(first.left(), Unit.PERCENT, market, false) + ")";
            }
            case INVESTOR_STREAK -> investor(p) + " " + Numbers.money(orZero(first.left()), true)
                    + (first.progress() == null || first.progress() == 0 ? "" : " · " + first.progress() + "일째");
            case INVESTOR_TURN -> investor(p) + " " + Numbers.money(orZero(first.left()), true)
                    + " (어제 " + Numbers.money(orZero(rs.get(1).left()), true) + ")";
        };
    }

    private static String unknownText(Condition c, UnknownReason reason, EvaluationInput in) {
        if (reason != UnknownReason.INSUFFICIENT_HISTORY) return reason.label();
        int needed = RequiredBars.of(c);
        boolean flow = IndicatorCalculator.isFlow(c.left().indicator())
                || (!c.right().isConstant() && IndicatorCalculator.isFlow(c.right().operand().indicator()));
        int available = flow ? in.series().flows().size() : in.series().bars().size();
        return available < needed ? reason.label() + " (" + needed + "일 필요, " + available + "일뿐)" : reason.label();
    }

    private static String value(Operand o, BigDecimal v, Market market) {
        return Numbers.observed(v, OperandNames.displayUnit(o), market, OperandNames.signed(o));
    }

    // ---- 머리 · 결과 줄 (§12.5.4 · §12.6 · §12.8) --------------------------------

    /** 데이터 시점 표기. ②의 발화 본문 끝에도 쓴다(§6.9). */
    public static String asOfLabel(CompiledTrigger t, EvaluationResult r, EvaluationInput in) {
        if (r.asOf() == null) return "데이터 없음";
        Market shown = shownMarket(t, in.market());
        if (r.basis() == Basis.INTRADAY) {
            return (shown == Market.US ? "미국 장중 · " : "") + Numbers.time(r.asOf()) + " 기준";
        }
        return (shown == Market.US ? "미국 " : "") + Numbers.date(in.date()) + " 종가 기준";
    }

    public static String header(CompiledTrigger t, EvaluationResult r, EvaluationInput in) {
        String label = asOfLabel(t, r, in);
        boolean kstLive = r.asOf() != null && r.basis() == Basis.INTRADAY && shownMarket(t, in.market()) != Market.US;
        return kstLive ? "지금 · " + label : label;
    }

    public static String resultText(Truth truth) {
        return switch (truth) {
            case TRUE -> "충족하고 있어요";
            case FALSE -> "아직 충족하지 않아요";
            case UNKNOWN -> "확인할 수 없어요";
        };
    }

    // ---- 조각 -------------------------------------------------------------------

    /** 사용자 상태 지표의 데이터 시점은 국내 영업일의 보유 스냅샷이라 미국 표기를 쓰지 않는다(§7.1). */
    private static Market shownMarket(CompiledTrigger t, Market market) {
        boolean user = t.conditions().stream()
                .anyMatch(c -> AlertCatalog.indicator(c.left().indicator()).scope() == Scope.USER);
        return user ? Market.KR : market;
    }

    private static String investor(Map<String, Object> p) {
        return "institution".equals(p.get("investor")) ? "기관" : "외국인";
    }

    private static String side(Map<String, Object> p) { return "buy".equals(p.get("side")) ? "순매수" : "순매도"; }

    private static BigDecimal num(Map<String, Object> p, String key) { return (BigDecimal) p.get(key); }

    private static BigDecimal orZero(BigDecimal v) { return v == null ? BigDecimal.ZERO : v; }
}
```

- [ ] **Step 6: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.sentence.*'`
Expected: PASS

- [ ] **Step 7: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/sentence \
        src/test/java/com/stockproject/portfolio/alert/sentence
git commit -m "feat: 알림 조건 문장과 관측값 줄을 서버가 만든다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: 데이터 읽기 — 미러 테이블과 보유 스냅샷으로 평가 입력 만들기

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/data/` 아래 `InstrumentRow.java` · `CalendarDay.java` · `MarketDataMapper.java` · `HoldingMapper.java` · `MarketDataRepository.java` · `HoldingReader.java` · `EvaluationInputFactory.java`
- Create: `src/main/resources/db/sample/sample_alert_market.sql`
- Test: `src/test/java/com/stockproject/portfolio/alert/data/EvaluationInputFactoryTest.java`

**Interfaces:**
- Consumes: Task 1 미러 테이블, Task 4 `CompiledTrigger` · `DataNeeds`(Task 7), Task 6 `Bar` · `FlowBar` · `Snapshot` · `Holding` · `Series`, Task 7 `EvaluationInput` · `Basis`, 기존 `AggregateQueryRepository` · `Derived` · `AxisKey.INSTRUMENT` · `Lens.DIRECT` · `LineFilter.NONE` · `UserScope`.
- Produces:
  - `record InstrumentRow(UUID instrumentId, String symbol, String name, String assetClass, String market, String currency, LocalDate delistedOn)` — `Market marketEnum()`, `boolean alertable()`(예수금·상장폐지 아님).
  - `record CalendarDay(LocalDate date, boolean isTradingDay, LocalDate prevTradingDay, OffsetDateTime closeAt)`
  - `MarketDataRepository` — `Optional<InstrumentRow> instrument(UUID)` · `List<Bar> bars(UUID, LocalDate to, int limit)`(오름차순) · `List<FlowBar> flows(UUID, LocalDate to, int limit)` · `List<Snapshot> snapshots(UUID, Market, LocalDate tradingDate, OffsetDateTime to)` · `Optional<LocalDate> latestDoneDate(Market, DataKind)` · `Optional<OffsetDateTime> latestDoneAt(Market, DataKind)` · `Set<LocalDate> doneDates(Market, DataKind, LocalDate from, LocalDate to)` · `List<LocalDate> tradingDays(Market, LocalDate from, LocalDate to)` · `LocalDate prevTradingDay(Market, LocalDate)` · `OffsetDateTime closeAt(Market, LocalDate)` · `static ZoneId zone(Market)`.
  - `HoldingReader` — `Optional<LocalDate> latestFinal(UserScope)` · `Holding holding(UserScope, LocalDate asOf, InstrumentRow)`(보유하지 않으면 `null`) · `boolean held(UserScope, InstrumentRow)`.
  - `EvaluationInputFactory` — `EvaluationInput forPreview(UserScope, InstrumentRow instrument, CompiledTrigger, Cadence)`(`instrument`가 `null`이면 종목 없음).
  - `sample_alert_market.sql` — 아래 표의 픽스처. Task 10~14의 API 테스트가 `sample_portfolio.sql` 다음에 적용한다.

| 종목 | 시세 픽스처 | 쓰는 곳 |
|---|---|---|
| 삼성전자 `…0001` (KR) | 일봉 2025-08-01 ~ 2026-09-25 평일 301봉, 종가 `60000 + 10·i`(마지막 63,010) · 수급 30일(외국인 +10억, 기관 −5억) · 9/28 장중 스냅샷 10:00 ~ 10:15 | 정상 평가 |
| SK하이닉스 `…0002` (KR) | 일봉 2026-09-15 ~ 09-25 9봉 | 이력 부족 |
| NAVER `…0003` (KR) | 일봉 2025-08-01 ~ 2026-09-24 (9/25 없음) | 거래 없음 |
| 애플 `…0004` (US) | 일봉 301봉, 종가 `200 + 0.1·i`(마지막 230.10) | 미국 |

캘린더는 2025-08-01 ~ 2026-10-30의 평일을 거래일로 둔다(KR 마감 15:30, US 마감 16:00 뉴욕). 완료 신호는 KR `DAILY_BAR`·`DAILY_FLOW`와 US `DAILY_BAR`가 9/25까지 거래일마다 `DONE`이고, KR `INTRADAY_QUOTE`가 9/28 10:00 ~ 10:15에 5분마다 `DONE`이다.

- [ ] **Step 1: 샘플 데이터를 쓴다**

`src/main/resources/db/sample/sample_alert_market.sql`:

```sql
BEGIN;

-- 알림 픽스처. sample_portfolio.sql 다음에 적용한다 — 종목은 그 파일이 만든다.
TRUNCATE alert_event, alert_state, alert, push_device, alert_watchlist,
         market_data_run, intraday_quote, investor_flow_daily, adjusted_price_daily, dim_market_calendar;

-- 평일을 거래일로 둔 캘린더. 마감 시각은 시장 현지 시각이다.
INSERT INTO dim_market_calendar (market, date, is_trading_day, prev_trading_day, next_trading_day, open_at, close_at)
SELECT m.market, d::date, extract(isodow FROM d) < 6,
       (SELECT max(p::date) FROM generate_series(d - interval '7 day', d - interval '1 day', interval '1 day') p
         WHERE extract(isodow FROM p) < 6),
       (SELECT min(n::date) FROM generate_series(d + interval '1 day', d + interval '7 day', interval '1 day') n
         WHERE extract(isodow FROM n) < 6),
       CASE WHEN extract(isodow FROM d) < 6
            THEN (d::date + m.open_time) AT TIME ZONE m.zone END,
       CASE WHEN extract(isodow FROM d) < 6
            THEN (d::date + m.close_time) AT TIME ZONE m.zone END
  FROM generate_series('2025-08-01'::date, '2026-10-30'::date, interval '1 day') d
 CROSS JOIN (VALUES ('KR', 'Asia/Seoul', time '09:00', time '15:30'),
                    ('US', 'America/New_York', time '09:30', time '16:00')) AS m(market, zone, open_time, close_time);

-- 삼성전자: 301봉, 종가 60000 + 10·i (2026-09-25 = 63,010)
INSERT INTO adjusted_price_daily (instrument_id, date, open, high, low, close, volume, adj_factor)
SELECT '10000000-0000-0000-0000-000000000001', d, 60000 + 10 * i, 60000 + 10 * i + 500,
       60000 + 10 * i - 500, 60000 + 10 * i, 1000000, 1
  FROM (SELECT d::date AS d, row_number() OVER (ORDER BY d) AS i
          FROM generate_series('2025-08-01'::date, '2026-09-25'::date, interval '1 day') d
         WHERE extract(isodow FROM d) < 6) days;

-- SK하이닉스: 9봉뿐이다 (이력 부족)
INSERT INTO adjusted_price_daily (instrument_id, date, open, high, low, close, volume, adj_factor)
SELECT '10000000-0000-0000-0000-000000000002', d, 100000 + 1000 * i, 100000 + 1000 * i,
       100000 + 1000 * i, 100000 + 1000 * i, 500000, 1
  FROM (SELECT d::date AS d, row_number() OVER (ORDER BY d) AS i
          FROM generate_series('2026-09-15'::date, '2026-09-25'::date, interval '1 day') d
         WHERE extract(isodow FROM d) < 6) days;

-- NAVER: 9/25 봉이 없다 (그 시장의 일봉은 DONE — 거래 없음)
INSERT INTO adjusted_price_daily (instrument_id, date, open, high, low, close, volume, adj_factor)
SELECT '10000000-0000-0000-0000-000000000003', d, 200000, 200000, 200000, 200000, 300000, 1
  FROM generate_series('2025-08-01'::date, '2026-09-24'::date, interval '1 day') d
 WHERE extract(isodow FROM d) < 6;

-- 애플: 301봉, 종가 200 + 0.1·i (2026-09-25 = 230.10)
INSERT INTO adjusted_price_daily (instrument_id, date, open, high, low, close, volume, adj_factor)
SELECT '10000000-0000-0000-0000-000000000004', d, 200 + 0.1 * i, 200 + 0.1 * i + 1, 200 + 0.1 * i - 1,
       200 + 0.1 * i, 50000000, 1
  FROM (SELECT d::date AS d, row_number() OVER (ORDER BY d) AS i
          FROM generate_series('2025-08-01'::date, '2026-09-25'::date, interval '1 day') d
         WHERE extract(isodow FROM d) < 6) days;

-- 삼성전자 수급 30거래일: 외국인 +10억, 기관 −5억
INSERT INTO investor_flow_daily (instrument_id, date, foreign_net_buy_krw, institution_net_buy_krw)
SELECT '10000000-0000-0000-0000-000000000001', d, 1000000000, -500000000
  FROM (SELECT d::date AS d FROM generate_series('2026-08-01'::date, '2026-09-25'::date, interval '1 day') d
         WHERE extract(isodow FROM d) < 6 ORDER BY d DESC LIMIT 30) days;

-- 삼성전자 9/28 장중 스냅샷
INSERT INTO intraday_quote (instrument_id, snapshot_at, price, cum_volume) VALUES
 ('10000000-0000-0000-0000-000000000001', '2026-09-28T10:00:00+09', 63100, 200000),
 ('10000000-0000-0000-0000-000000000001', '2026-09-28T10:05:00+09', 63200, 260000),
 ('10000000-0000-0000-0000-000000000001', '2026-09-28T10:10:00+09', 63300, 310000),
 ('10000000-0000-0000-0000-000000000001', '2026-09-28T10:15:00+09', 63500, 380000);

-- 완료 신호. 일별 신호의 as_of는 그 거래일의 close_at이다(데이터 요구사항 §4.2).
INSERT INTO market_data_run (market, kind, as_of, state, finished_at)
SELECT c.market, k.kind, c.close_at, 'DONE', c.close_at + interval '30 minute'
  FROM dim_market_calendar c
 CROSS JOIN (VALUES ('DAILY_BAR'), ('DAILY_FLOW')) AS k(kind)
 WHERE c.is_trading_day AND c.date <= '2026-09-25'
   AND (c.market = 'KR' OR k.kind = 'DAILY_BAR');

INSERT INTO market_data_run (market, kind, as_of, state, finished_at) VALUES
 ('KR', 'INTRADAY_QUOTE', '2026-09-28T10:00:00+09', 'DONE', '2026-09-28T10:00:40+09'),
 ('KR', 'INTRADAY_QUOTE', '2026-09-28T10:05:00+09', 'DONE', '2026-09-28T10:05:40+09'),
 ('KR', 'INTRADAY_QUOTE', '2026-09-28T10:10:00+09', 'DONE', '2026-09-28T10:10:40+09'),
 ('KR', 'INTRADAY_QUOTE', '2026-09-28T10:15:00+09', 'DONE', '2026-09-28T10:15:40+09');

COMMIT;
```

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/data/EvaluationInputFactoryTest.java`:

```java
package com.stockproject.portfolio.alert.data;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.IndicatorKey;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.catalog.PresetKey;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.compile.Compiler;
import com.stockproject.portfolio.alert.evaluation.Basis;
import com.stockproject.portfolio.alert.evaluation.ConditionEvaluator;
import com.stockproject.portfolio.alert.evaluation.EvaluationInput;
import com.stockproject.portfolio.alert.evaluation.Truth;
import com.stockproject.portfolio.alert.evaluation.UnknownReason;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Right;
import com.stockproject.portfolio.alert.spec.Transform;
import com.stockproject.portfolio.alert.spec.TriggerSpec;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.domain.Market;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class EvaluationInputFactoryTest {

    private static final UserScope YHR = new UserScope(UUID.fromString("40000000-0000-0000-0000-000000000001"));
    private static final UserScope JDH = new UserScope(UUID.fromString("40000000-0000-0000-0000-000000000002"));
    private static final UUID SAMSUNG = id(1);
    private static final UUID HYNIX = id(2);
    private static final UUID NAVER = id(3);
    private static final UUID APPLE = id(4);

    @Autowired MarketDataRepository market;
    @Autowired HoldingReader holdings;
    @Autowired JdbcClient jdbc;

    @Test
    void 종가_알림은_기다리는_데이터가_모두_DONE인_최근_거래일이다() {
        EvaluationInput in = factory("2026-09-28T10:20:00+09:00").forPreview(YHR, row(SAMSUNG), priceAbove("1"),
                Cadence.CLOSE);

        assertThat(in.basis()).isEqualTo(Basis.DAILY);
        assertThat(in.date()).isEqualTo(LocalDate.of(2026, 9, 25));
        assertThat(in.asOf()).isAtSameInstantAs(OffsetDateTime.parse("2026-09-25T15:30:00+09:00"));
        assertThat(in.series().bars()).hasSize(300);
        assertThat(in.series().lastBar().close()).isEqualByComparingTo("63010");
        assertThat(in.notDone()).isEmpty();
        assertThat(in.missingDays()).isEmpty();
    }

    @Test
    void 장중_스냅샷이_허용_지연_안이면_장중_기준이다() {
        EvaluationInput in = factory("2026-09-28T10:20:00+09:00").forPreview(YHR, row(SAMSUNG), priceAbove("1"),
                Cadence.INTRADAY);

        assertThat(in.basis()).isEqualTo(Basis.INTRADAY);
        assertThat(in.asOf()).isAtSameInstantAs(OffsetDateTime.parse("2026-09-28T10:15:00+09:00"));
        assertThat(in.series().snapshots()).hasSize(4);
        assertThat(in.series().lastBar().date()).isEqualTo(LocalDate.of(2026, 9, 25));
        assertThat(ConditionEvaluator.evaluate(priceAbove("63400"), in).truth()).isEqualTo(Truth.TRUE);
    }

    /** 스냅샷이 낡았으면 가장 최근 종가를 스냅샷 하나로 삼는다 (계획 A.5). */
    @Test
    void 장중_스냅샷이_낡았으면_종가_기준이다() {
        EvaluationInput in = factory("2026-09-28T11:00:00+09:00").forPreview(YHR, row(SAMSUNG), priceAbove("1"),
                Cadence.INTRADAY);

        assertThat(in.basis()).isEqualTo(Basis.DAILY);
        assertThat(in.date()).isEqualTo(LocalDate.of(2026, 9, 25));
        assertThat(in.series().snapshots()).singleElement()
                .satisfies(s -> assertThat(s.price()).isEqualByComparingTo("63010"));
        assertThat(in.series().lastBar().date()).isEqualTo(LocalDate.of(2026, 9, 24));
    }

    @Test
    void 봉이_적으면_이력_부족_현재_봉이_없으면_거래_없음이다() {
        CompiledTrigger rsi = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.RSI_ZONE, Map.of()),
                Cadence.CLOSE);
        Factory f = factory("2026-09-28T10:20:00+09:00");

        assertThat(ConditionEvaluator.evaluate(rsi, f.forPreview(YHR, row(HYNIX), rsi, Cadence.CLOSE)).reason())
                .isEqualTo(UnknownReason.INSUFFICIENT_HISTORY);
        assertThat(ConditionEvaluator.evaluate(rsi, f.forPreview(YHR, row(NAVER), rsi, Cadence.CLOSE)).reason())
                .isEqualTo(UnknownReason.NO_TRADE);
    }

    @Test
    void 미국_종목의_거래일은_미국_현지_날짜다() {
        EvaluationInput in = factory("2026-09-28T10:20:00+09:00").forPreview(YHR, row(APPLE), priceAbove("1"),
                Cadence.CLOSE);

        assertThat(in.market()).isEqualTo(Market.US);
        assertThat(in.date()).isEqualTo(LocalDate.of(2026, 9, 25));
        assertThat(in.asOf()).isAtSameInstantAs(OffsetDateTime.parse("2026-09-25T16:00:00-04:00"));
        assertThat(in.series().lastBar().close()).isEqualByComparingTo("230.1");
    }

    @Test
    void 완료_신호가_없으면_데이터_없음이다() {
        jdbc.sql("DELETE FROM market_data_run WHERE market = 'US'").update();

        EvaluationInput in = factory("2026-09-28T10:20:00+09:00").forPreview(YHR, row(APPLE), priceAbove("1"),
                Cadence.CLOSE);

        assertThat(in.asOf()).isNull();
        assertThat(ConditionEvaluator.evaluate(priceAbove("1"), in).reason()).isEqualTo(UnknownReason.DATA_MISSING);
    }

    @Test
    void 신호가_빠진_거래일은_데이터_누락일이다() {
        jdbc.sql("""
                DELETE FROM market_data_run
                 WHERE market = 'KR' AND kind = 'DAILY_BAR' AND as_of = '2026-09-23T15:30:00+09'
                """).update();

        EvaluationInput in = factory("2026-09-28T10:20:00+09:00").forPreview(YHR, row(SAMSUNG), priceAbove("1"),
                Cadence.CLOSE);

        assertThat(in.missingDays()).containsExactly(LocalDate.of(2026, 9, 23));
        assertThat(in.series().bars()).extracting(b -> b.date()).doesNotContain(LocalDate.of(2026, 9, 23));
        Condition streak = new Condition(price(), OperatorKey.GTE, Right.constant(BigDecimal.ONE), new Modifier.Streak(3));
        assertThat(ConditionEvaluator.evaluate(streak, in).reason()).isEqualTo(UnknownReason.DATA_MISSING);
    }

    @Test
    void 기다리지_않는_데이터가_늦어도_평가한다() {
        jdbc.sql("""
                DELETE FROM market_data_run
                 WHERE market = 'KR' AND kind = 'DAILY_FLOW' AND as_of >= '2026-09-24T00:00:00+09'
                """).update();
        Factory f = factory("2026-09-28T10:20:00+09:00");

        assertThat(f.forPreview(YHR, row(SAMSUNG), priceAbove("1"), Cadence.CLOSE).date())
                .isEqualTo(LocalDate.of(2026, 9, 25));
        CompiledTrigger flow = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.INVESTOR_TURN, Map.of()),
                Cadence.CLOSE);
        assertThat(f.forPreview(YHR, row(SAMSUNG), flow, Cadence.CLOSE).date()).isEqualTo(LocalDate.of(2026, 9, 23));
    }

    /** 평가손익률은 포트폴리오 종목 화면과 같은 값이다 — 07-24 확정 스냅샷, 1,040,000 ÷ 12,000,000. */
    @Test
    void 사용자_상태_지표는_최신_확정_스냅샷에서_온다() {
        CompiledTrigger pnl = Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.PNL_REACH, Map.of()),
                Cadence.CLOSE);
        Factory f = factory("2026-09-28T10:20:00+09:00");

        EvaluationInput in = f.forPreview(YHR, row(SAMSUNG), pnl, Cadence.CLOSE);
        assertThat(in.date()).isEqualTo(LocalDate.of(2026, 7, 24));
        assertThat(in.market()).isEqualTo(Market.KR);
        assertThat(in.series().holding().unrealizedPnlPct()).isEqualByComparingTo("8.7");
        assertThat(in.series().holding().carriedForward()).isFalse();

        assertThat(ConditionEvaluator.evaluate(pnl, f.forPreview(JDH, row(NAVER), pnl, Cadence.CLOSE)).reason())
                .isEqualTo(UnknownReason.NOT_HELD);
        assertThat(holdings.held(YHR, row(SAMSUNG))).isTrue();
        assertThat(holdings.held(JDH, row(NAVER))).isFalse();
    }

    @Test
    void 종목이_없으면_종목_정보_없음이다() {
        EvaluationInput in = factory("2026-09-28T10:20:00+09:00").forPreview(YHR, null, priceAbove("1"),
                Cadence.CLOSE);

        assertThat(ConditionEvaluator.evaluate(priceAbove("1"), in).reason())
                .isEqualTo(UnknownReason.INSTRUMENT_UNKNOWN);
    }

    // ---- 도우미 ----------------------------------------------------------------

    private interface Factory {
        EvaluationInput forPreview(UserScope scope, InstrumentRow row, CompiledTrigger t, Cadence cadence);

        default EvaluationInput forPreview(UserScope scope, InstrumentRow row, Condition c, Cadence cadence) {
            return forPreview(scope, row, new CompiledTrigger(List.of(c), null, null), cadence);
        }
    }

    private Factory factory(String now) {
        Clock clock = Clock.fixed(Instant.from(OffsetDateTime.parse(now)), ZoneId.of("Asia/Seoul"));
        EvaluationInputFactory real = new EvaluationInputFactory(market, holdings, clock);
        return real::forPreview;
    }

    private InstrumentRow row(UUID id) { return market.instrument(id).orElseThrow(); }

    private static Condition priceAbove(String value) {
        return new Condition(price(), OperatorKey.GTE, Right.constant(new BigDecimal(value)), null);
    }

    private static Operand price() { return new Operand(IndicatorKey.PRICE, Map.of(), new Transform.Identity()); }

    private static UUID id(int n) { return UUID.fromString("10000000-0000-0000-0000-00000000000" + n); }
}
```

테스트의 `Factory`는 시계를 바꿔 끼운 팩토리다. `Condition` 하나를 넘기는 호출은 기본 메서드가 `CompiledTrigger`로 감싼다.

- [ ] **Step 3: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.data.EvaluationInputFactoryTest'`
Expected: FAIL — 컴파일 오류

- [ ] **Step 4: 행과 매퍼를 쓴다**

`alert/data/InstrumentRow.java`:

```java
package com.stockproject.portfolio.alert.data;

import com.stockproject.portfolio.domain.Market;

import java.time.LocalDate;
import java.util.UUID;

/** 종목 마스터 한 행 (데이터팀 소유 instrument). */
public record InstrumentRow(UUID instrumentId, String symbol, String name, String assetClass, String market,
                            String currency, LocalDate delistedOn) {

    public Market marketEnum() { return Market.valueOf(market); }

    /** 알림을 걸 수 있는가 — 예수금 의사종목과 상장폐지 종목은 아니다(§14.1). */
    public boolean alertable() { return !"CASH".equals(assetClass) && delistedOn == null; }
}
```

`alert/data/CalendarDay.java`:

```java
package com.stockproject.portfolio.alert.data;

import java.time.LocalDate;
import java.time.OffsetDateTime;

/** 시장 캘린더 하루 (데이터 요구사항 §4.2). */
public record CalendarDay(LocalDate date, boolean isTradingDay, LocalDate prevTradingDay, OffsetDateTime closeAt) { }
```

`alert/data/MarketDataMapper.java`:

```java
package com.stockproject.portfolio.alert.data;

import com.stockproject.portfolio.alert.indicator.Bar;
import com.stockproject.portfolio.alert.indicator.FlowBar;
import com.stockproject.portfolio.alert.indicator.Snapshot;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 데이터팀 소유 시세 테이블 읽기. 물리 이름이 정해지면(데이터 요구사항 N1) 이 파일만 고친다.
 * 봉은 최근 것부터 limit개를 읽는다 — 오름차순으로 바꾸는 것은 저장소가 한다.
 */
@Mapper
public interface MarketDataMapper {

    @Select("""
            SELECT instrument_id, symbol, name, asset_class, market, currency, delisted_on
              FROM instrument WHERE instrument_id = #{id}
            """)
    InstrumentRow instrument(@Param("id") UUID id);

    @Select("""
            SELECT date, open, high, low, close, volume FROM adjusted_price_daily
             WHERE instrument_id = #{id} AND date <= #{to}
             ORDER BY date DESC LIMIT #{limit}
            """)
    List<Bar> barsDesc(@Param("id") UUID id, @Param("to") LocalDate to, @Param("limit") int limit);

    @Select("""
            SELECT date, foreign_net_buy_krw AS "foreign", institution_net_buy_krw AS institution
              FROM investor_flow_daily
             WHERE instrument_id = #{id} AND date <= #{to}
             ORDER BY date DESC LIMIT #{limit}
            """)
    List<FlowBar> flowsDesc(@Param("id") UUID id, @Param("to") LocalDate to, @Param("limit") int limit);

    @Select("""
            SELECT snapshot_at AS "at", price, cum_volume FROM intraday_quote
             WHERE instrument_id = #{id} AND snapshot_at >= #{from} AND snapshot_at <= #{to}
             ORDER BY snapshot_at
            """)
    List<Snapshot> snapshots(@Param("id") UUID id, @Param("from") OffsetDateTime from,
                             @Param("to") OffsetDateTime to);

    @Select("""
            SELECT max(as_of) FROM market_data_run
             WHERE market = #{market} AND kind = #{kind} AND state = 'DONE'
            """)
    OffsetDateTime latestDone(@Param("market") String market, @Param("kind") String kind);

    @Select("""
            SELECT as_of FROM market_data_run
             WHERE market = #{market} AND kind = #{kind} AND state = 'DONE'
               AND as_of >= #{from} AND as_of < #{to}
            """)
    List<OffsetDateTime> doneBetween(@Param("market") String market, @Param("kind") String kind,
                                     @Param("from") OffsetDateTime from, @Param("to") OffsetDateTime to);

    @Select("""
            SELECT date, is_trading_day, prev_trading_day, close_at FROM dim_market_calendar
             WHERE market = #{market} AND date BETWEEN #{from} AND #{to}
             ORDER BY date
            """)
    List<CalendarDay> calendar(@Param("market") String market, @Param("from") LocalDate from,
                               @Param("to") LocalDate to);
}
```

`alert/data/HoldingMapper.java`:

```java
package com.stockproject.portfolio.alert.data;

import com.stockproject.portfolio.auth.UserScope;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDate;
import java.util.UUID;

/** 사용자 상태 지표의 재료 — 최신 확정 스냅샷과 그 종목 행의 이월 여부 (§5.1 · §7.2). */
@Mapper
public interface HoldingMapper {

    @Select("""
            SELECT max(pl.as_of) FROM position_line pl JOIN account a USING (account_id)
             WHERE a.user_id = #{scope.userId} AND pl.is_final
            """)
    LocalDate latestFinalAsOf(@Param("scope") UserScope scope);

    /** 그 종목 행 중 하나라도 이월값인가. 행이 없으면(보유하지 않음) null이다. */
    @Select("""
            SELECT bool_or(pl.is_carried_forward) FROM position_line pl JOIN account a USING (account_id)
             WHERE a.user_id = #{scope.userId} AND pl.as_of = #{asOf}
               AND pl.instrument_id = #{instrumentId} AND pl.quantity > 0
            """)
    Boolean carriedForward(@Param("scope") UserScope scope, @Param("asOf") LocalDate asOf,
                           @Param("instrumentId") UUID instrumentId);
}
```

- [ ] **Step 5: 저장소와 보유 읽기를 쓴다**

`alert/data/MarketDataRepository.java`:

```java
package com.stockproject.portfolio.alert.data;

import com.stockproject.portfolio.alert.catalog.DataKind;
import com.stockproject.portfolio.alert.indicator.Bar;
import com.stockproject.portfolio.alert.indicator.FlowBar;
import com.stockproject.portfolio.alert.indicator.Snapshot;
import com.stockproject.portfolio.domain.Market;
import org.springframework.stereotype.Repository;

import java.time.DayOfWeek;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/**
 * 시세 미러 읽기와 시장 시간 계산.
 *
 * <p>거래일은 그 시장의 현지 날짜다(데이터 요구사항 §2.4). 일별 완료 신호의 as_of는 그 거래일의
 * close_at이라, 현지 시간대로 바꾼 날짜가 곧 거래일이다. 캘린더에 그 구간의 행이 없으면
 * 월~금을 거래일로 본다(계획 A.6).</p>
 */
@Repository
public class MarketDataRepository {

    private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");
    private static final ZoneId NEW_YORK = ZoneId.of("America/New_York");

    private final MarketDataMapper mapper;

    public MarketDataRepository(MarketDataMapper mapper) { this.mapper = mapper; }

    public static ZoneId zone(Market market) { return market == Market.US ? NEW_YORK : SEOUL; }

    public Optional<InstrumentRow> instrument(UUID id) { return Optional.ofNullable(mapper.instrument(id)); }

    public List<Bar> bars(UUID id, LocalDate to, int limit) {
        List<Bar> bars = new ArrayList<>(mapper.barsDesc(id, to, limit));
        Collections.reverse(bars);
        return bars;
    }

    public List<FlowBar> flows(UUID id, LocalDate to, int limit) {
        List<FlowBar> flows = new ArrayList<>(mapper.flowsDesc(id, to, limit));
        Collections.reverse(flows);
        return flows;
    }

    /** 그 거래일(시장 현지 날짜) 시작부터 to까지의 장중 스냅샷. */
    public List<Snapshot> snapshots(UUID id, Market market, LocalDate tradingDate, OffsetDateTime to) {
        OffsetDateTime from = tradingDate.atStartOfDay(zone(market)).toOffsetDateTime();
        return mapper.snapshots(id, from, to);
    }

    public Optional<OffsetDateTime> latestDoneAt(Market market, DataKind kind) {
        return Optional.ofNullable(mapper.latestDone(market.name(), kind.name()));
    }

    public Optional<LocalDate> latestDoneDate(Market market, DataKind kind) {
        return latestDoneAt(market, kind).map(at -> at.atZoneSameInstant(zone(market)).toLocalDate());
    }

    public Set<LocalDate> doneDates(Market market, DataKind kind, LocalDate from, LocalDate to) {
        OffsetDateTime start = from.atStartOfDay(zone(market)).toOffsetDateTime();
        OffsetDateTime end = to.plusDays(1).atStartOfDay(zone(market)).toOffsetDateTime();
        Set<LocalDate> dates = new HashSet<>();
        for (OffsetDateTime at : mapper.doneBetween(market.name(), kind.name(), start, end)) {
            dates.add(at.atZoneSameInstant(zone(market)).toLocalDate());
        }
        return dates;
    }

    public List<LocalDate> tradingDays(Market market, LocalDate from, LocalDate to) {
        List<CalendarDay> days = mapper.calendar(market.name(), from, to);
        if (days.isEmpty()) return weekdays(from, to);
        return days.stream().filter(CalendarDay::isTradingDay).map(CalendarDay::date).toList();
    }

    public LocalDate prevTradingDay(Market market, LocalDate date) {
        List<CalendarDay> days = mapper.calendar(market.name(), date, date);
        if (!days.isEmpty()) return days.get(0).prevTradingDay();
        LocalDate d = date.minusDays(1);
        while (isWeekend(d)) d = d.minusDays(1);
        return d;
    }

    /** 종가의 데이터 시점은 캘린더의 close_at에서만 읽는다(§7.1). 행이 없을 때만 정규 마감으로 근사한다. */
    public OffsetDateTime closeAt(Market market, LocalDate date) {
        List<CalendarDay> days = mapper.calendar(market.name(), date, date);
        if (!days.isEmpty() && days.get(0).closeAt() != null) return days.get(0).closeAt();
        LocalTime close = market == Market.US ? LocalTime.of(16, 0) : LocalTime.of(15, 30);
        return date.atTime(close).atZone(zone(market)).toOffsetDateTime();
    }

    private static List<LocalDate> weekdays(LocalDate from, LocalDate to) {
        List<LocalDate> out = new ArrayList<>();
        for (LocalDate d = from; !d.isAfter(to); d = d.plusDays(1)) if (!isWeekend(d)) out.add(d);
        return out;
    }

    private static boolean isWeekend(LocalDate d) {
        return d.getDayOfWeek() == DayOfWeek.SATURDAY || d.getDayOfWeek() == DayOfWeek.SUNDAY;
    }
}
```

`alert/data/HoldingReader.java`:

```java
package com.stockproject.portfolio.alert.data;

import com.stockproject.portfolio.alert.indicator.Holding;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.catalog.AxisKey;
import com.stockproject.portfolio.catalog.Lens;
import com.stockproject.portfolio.domain.group.Aggregation;
import com.stockproject.portfolio.domain.group.Derived;
import com.stockproject.portfolio.domain.group.GroupNode;
import com.stockproject.portfolio.query.LineFilter;
import com.stockproject.portfolio.query.aggregate.AggregateQueryRepository;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * 사용자 상태 지표 (스펙 §5.1). 포트폴리오 종목 화면과 같은 값이어야 하므로 같은 집계를 쓴다 —
 * 모든 계좌를 합산한 종목 한 행의 평가손익률과, 예수금을 포함한 총자산 대비 비중이다.
 * 종목 축의 키는 화면과 같이 종목코드다.
 */
@Component
public class HoldingReader {

    private final HoldingMapper mapper;
    private final AggregateQueryRepository aggregates;

    public HoldingReader(HoldingMapper mapper, AggregateQueryRepository aggregates) {
        this.mapper = mapper;
        this.aggregates = aggregates;
    }

    public Optional<LocalDate> latestFinal(UserScope scope) {
        return Optional.ofNullable(mapper.latestFinalAsOf(scope));
    }

    /** 최신 확정 스냅샷에서 보유 중인가 — 생성 검증의 NOT_HELD (§14.1). */
    public boolean held(UserScope scope, InstrumentRow instrument) {
        return latestFinal(scope)
                .map(asOf -> mapper.carriedForward(scope, asOf, instrument.instrumentId()) != null)
                .orElse(false);
    }

    /** 그 스냅샷의 그 종목 한 행. 보유하지 않으면 null이다. */
    public Holding holding(UserScope scope, LocalDate asOf, InstrumentRow instrument) {
        Boolean carried = mapper.carriedForward(scope, asOf, instrument.instrumentId());
        if (carried == null) return null;
        Aggregation aggregation = aggregates.aggregate(scope, asOf, List.of(AxisKey.INSTRUMENT), Lens.DIRECT,
                LineFilter.NONE);
        for (GroupNode row : aggregation.rows()) {
            if (row.key().key().equals(instrument.symbol())) {
                return new Holding(Derived.unrealizedPnlPct(row.measures()),
                        Derived.weightPct(row.measures(), aggregation.weightDenominator()), carried);
            }
        }
        return null;
    }
}
```

- [ ] **Step 6: 평가 입력 조립을 쓴다**

`alert/data/EvaluationInputFactory.java`:

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

/**
 * 미리보기의 평가 입력 (계획 A.5 · A.6).
 *
 * <p>종가 알림은 기다리는 데이터 종류가 모두 DONE인 가장 최근 거래일에서 평가한다. 종류마다
 * 최신 DONE 거래일을 구하고 그중 가장 이른 날을 고른다. 그날 DONE이 아닌 종류는 notDone이 된다
 * — 그 뒤 거래일의 같은 종류가 DONE이 됐다면 그날의 데이터는 오지 않는 것으로 본다(§7.1).</p>
 *
 * <p>장중 알림은 그 시장의 최신 INTRADAY_QUOTE가 허용 지연 안이고 그 종목의 스냅샷이 있으면
 * 장중 기준이다. 아니면 가장 최근 DAILY_BAR 거래일의 종가를 스냅샷 하나로 삼은 일봉 기준이다 —
 * 그 종가가 장중 값의 자리에 오고, 이력은 그 전날까지다.</p>
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

    public EvaluationInput forPreview(UserScope scope, InstrumentRow instrument, CompiledTrigger trigger,
                                      Cadence cadence) {
        if (instrument == null) {
            return new EvaluationInput(cadence, Basis.DAILY, Market.KR, null, null, Series.empty(), Set.of(),
                    Set.of(), false, EvaluationInput.allowedGap(Market.KR));
        }
        if (usesUserScope(trigger)) return userScope(scope, instrument, cadence);
        Set<DataKind> needs = DataNeeds.of(trigger, cadence);
        if (needs.isEmpty()) return EvaluationInput.noData(cadence, instrument.marketEnum());   // 평가할 조건이 없다
        return cadence == Cadence.INTRADAY ? intraday(instrument, needs) : close(instrument, needs);
    }

    // ---- 종가 ------------------------------------------------------------------

    private EvaluationInput close(InstrumentRow instrument, Set<DataKind> needs) {
        Market m = instrument.marketEnum();
        LocalDate date = null;
        for (DataKind kind : needs) {
            Optional<LocalDate> latest = market.latestDoneDate(m, kind);
            if (latest.isEmpty()) return EvaluationInput.noData(Cadence.CLOSE, m);
            if (date == null || latest.get().isBefore(date)) date = latest.get();
        }
        Set<DataKind> notDone = EnumSet.noneOf(DataKind.class);
        for (DataKind kind : needs) {
            if (!market.doneDates(m, kind, date, date).contains(date)) notDone.add(kind);
        }
        List<Bar> bars = market.bars(instrument.instrumentId(), date, BAR_LIMIT);
        List<FlowBar> flows = needs.contains(DataKind.DAILY_FLOW)
                ? market.flows(instrument.instrumentId(), date, FLOW_LIMIT) : List.of();

        // 데이터 누락일은 계열에서 빠진다 — 그날 행이 일부 들어와 있어도 DONE이 아니면 쓰지 않는다(§7.2)
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

    /** from ~ to의 거래일 중 그 종류의 DONE이 없는 날 — 데이터 누락일 (계획 A.6). */
    private Set<LocalDate> missingDays(Market m, DataKind kind, LocalDate from, LocalDate to) {
        Set<LocalDate> done = market.doneDates(m, kind, from, to);
        Set<LocalDate> missing = new HashSet<>();
        for (LocalDate d : market.tradingDays(m, from, to)) if (!done.contains(d)) missing.add(d);
        return missing;
    }

    // ---- 장중 ------------------------------------------------------------------

    private EvaluationInput intraday(InstrumentRow instrument, Set<DataKind> needs) {
        Market m = instrument.marketEnum();
        Duration gap = EvaluationInput.allowedGap(m);
        OffsetDateTime now = OffsetDateTime.now(clock);

        Optional<OffsetDateTime> quote = market.latestDoneAt(m, DataKind.INTRADAY_QUOTE);
        if (quote.isPresent() && Duration.between(quote.get(), now).compareTo(gap) <= 0) {
            LocalDate today = quote.get().atZoneSameInstant(MarketDataRepository.zone(m)).toLocalDate();
            List<Snapshot> snaps = market.snapshots(instrument.instrumentId(), m, today, quote.get());
            if (!snaps.isEmpty()) {
                LocalDate prev = market.prevTradingDay(m, today);
                Set<DataKind> notDone = EnumSet.noneOf(DataKind.class);
                if (needs.contains(DataKind.DAILY_BAR)
                        && !market.doneDates(m, DataKind.DAILY_BAR, prev, prev).contains(prev)) {
                    notDone.add(DataKind.DAILY_BAR);
                }
                List<Bar> history = market.bars(instrument.instrumentId(), prev, BAR_LIMIT);
                return new EvaluationInput(Cadence.INTRADAY, Basis.INTRADAY, m, today,
                        snaps.get(snaps.size() - 1).at(), new Series(history, List.of(), snaps, null), notDone,
                        Set.of(), true, gap);
            }
        }
        return intradayFromClose(instrument, m, gap);
    }

    private EvaluationInput intradayFromClose(InstrumentRow instrument, Market m, Duration gap) {
        Optional<LocalDate> latest = market.latestDoneDate(m, DataKind.DAILY_BAR);
        if (latest.isEmpty()) return EvaluationInput.noData(Cadence.INTRADAY, m);
        LocalDate date = latest.get();
        OffsetDateTime closeAt = market.closeAt(m, date);
        List<Bar> bars = market.bars(instrument.instrumentId(), date, BAR_LIMIT + 1);
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

    // ---- 사용자 상태 ------------------------------------------------------------

    /** 데이터 시점은 국내 영업일의 확정 스냅샷이라 시장은 KR로 둔다(§7.1). */
    private EvaluationInput userScope(UserScope scope, InstrumentRow instrument, Cadence cadence) {
        Optional<LocalDate> asOf = holdings.latestFinal(scope);
        if (asOf.isEmpty()) return EvaluationInput.noData(cadence, Market.KR);
        Holding holding = holdings.holding(scope, asOf.get(), instrument);
        return new EvaluationInput(cadence, Basis.DAILY, Market.KR, asOf.get(),
                market.closeAt(Market.KR, asOf.get()), new Series(List.of(), List.of(), List.of(), holding),
                Set.of(), Set.of(), true, EvaluationInput.allowedGap(Market.KR));
    }

    private static boolean usesUserScope(CompiledTrigger trigger) {
        return trigger.conditions().stream()
                .anyMatch(c -> AlertCatalog.indicator(c.left().indicator()).scope() == Scope.USER);
    }
}
```

- [ ] **Step 7: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.data.EvaluationInputFactoryTest'`
Expected: PASS

- [ ] **Step 8: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/data \
        src/main/resources/db/sample/sample_alert_market.sql \
        src/test/java/com/stockproject/portfolio/alert/data
git commit -m "feat: 시세 미러와 보유 스냅샷으로 알림 평가 입력을 만든다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: `POST /alerts/preview` — 검증 · 지금 값 · 충족 여부 · 중복을 한 번에

**Files:**
- Create: `src/test/java/com/stockproject/portfolio/alert/AlertApiClient.java` · `FixedClockConfig.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/store/AlertRow.java` · `AlertMapper.java` · `AlertStore.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/service/AlertTimes.java` · `AlertPreviewService.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/api/AlertController.java` · `AlertExceptionHandler.java` · `dto/PreviewResponse.java` · `dto/SummaryDto.java` · `dto/CurrentDto.java` · `dto/LineDto.java` · `dto/InvalidAlertError.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/api/AlertPreviewApiTest.java`

**Interfaces:**
- Consumes: Task 3 해석기, Task 5 검증기, Task 4 컴파일러 · `SpecHash`, Task 7 평가기, Task 8 문장, Task 9 `MarketDataRepository` · `HoldingReader` · `EvaluationInputFactory` · 샘플 데이터.
- Produces:
  - 테스트 지원: `AlertApiClient(MockMvc, ObjectMapper)` — `Response get/post/put/delete(String path, String user[, String body])`, `record Response(int status, JsonNode body)`. `FixedClockConfig` — `@Primary Clock` 2026-09-28T10:20+09:00.
  - `record AlertRow(UUID alertId, UUID userId, UUID instrumentId, String name, String cadence, String notifyMode, Integer cooldownMin, OffsetDateTime expiresAt, String status, String triggerType, String triggerSpec, int specVersion, OffsetDateTime createdAt, OffsetDateTime updatedAt, String lastResult, String unknownReason, OffsetDateTime evaluatedAsOf, String specHash, int version)` — 삭제되지 않은 알림과 그 상태 한 행.
  - `AlertStore` — `Optional<AlertRow> findOwned(UserScope, UUID alertId)`(남의 것·삭제된 것은 빈 값) · `Optional<UUID> duplicateOf(UserScope, UUID instrumentId, Cadence, String specHash, UUID excludeAlertId)`.
  - `AlertTimes.kst(OffsetDateTime)` — 응답의 시각을 한국 시간 오프셋으로.
  - `AlertPreviewService.preview(UserScope, JsonNode) → PreviewResponse`.
  - `record PreviewResponse(boolean valid, List<FieldError> errors, SummaryDto summary, CurrentDto current, boolean alreadySatisfied, UUID duplicateOf)` · `record SummaryDto(@JsonProperty("short") String shortText, String sentence)` · `record CurrentDto(Truth result, OffsetDateTime asOf, String header, String resultText, List<LineDto> conditions)` · `record LineDto(Truth result, UnknownReason unknownReason, String text)` · `record InvalidAlertError(Detail error)`(`Detail(code, message, fields)`).
  - `AlertExceptionHandler` — `InvalidAlertException` → `400 INVALID_ALERT`.

미리보기의 `current`는 계산할 수 있는 만큼 채운다(§11.3 · §12.4).

| 상황 | `current` |
|---|---|
| 요청 본문의 형이 틀림 | `null` |
| 프리셋인데 `cadence`·`trigger_spec.*`에 오류 | `null` (컴파일할 수 없다) |
| 조립형인데 `trigger_spec` · `trigger_spec.conditions`에 오류(조건 수 · 범위 섞임) | `null` |
| 조립형의 일부 조건에 오류 | 그 조건 줄은 `UNKNOWN` · 사유 없음 · `<지표> — 입력을 확인해 주세요`. 나머지는 평가한다. 전체 결과는 거짓이 있으면 `FALSE`, 아니면 `UNKNOWN` |
| 그 밖의 오류(이름 · 만료 · 미보유 · 종목 · 수정 불가) | 그대로 계산한다 |

- [ ] **Step 1: 테스트 지원 클래스를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/FixedClockConfig.java`:

```java
package com.stockproject.portfolio.alert;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;

/** 알림 API 테스트의 "지금" — 2026-09-28(월) 10:20, 국내 장중 스냅샷 10:15의 5분 뒤다. */
@TestConfiguration
public class FixedClockConfig {

    public static final Instant NOW = Instant.parse("2026-09-28T01:20:00Z");

    @Bean
    @Primary
    Clock fixedClock() {
        return Clock.fixed(NOW, ZoneId.of("Asia/Seoul"));
    }
}
```

`src/test/java/com/stockproject/portfolio/alert/AlertApiClient.java`:

```java
package com.stockproject.portfolio.alert;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;

/** 알림 API 테스트용 호출기. 사용자 이름으로 로그인하고 토큰을 붙인다. */
public class AlertApiClient {

    private static final String PASSWORD = "local-dev-password";

    public record Response(int status, JsonNode body) { }

    private final MockMvc mockMvc;
    private final ObjectMapper json;
    private final Map<String, String> tokens = new HashMap<>();

    public AlertApiClient(MockMvc mockMvc, ObjectMapper json) {
        this.mockMvc = mockMvc;
        this.json = json;
    }

    public Response get(String path, String user) throws Exception { return call(get(path), user, null); }
    public Response post(String path, String user, String body) throws Exception { return call(post(path), user, body); }
    public Response put(String path, String user, String body) throws Exception { return call(put(path), user, body); }
    public Response delete(String path, String user) throws Exception { return call(delete(path), user, null); }

    private Response call(MockHttpServletRequestBuilder request, String user, String body) throws Exception {
        request.header("Authorization", "Bearer " + token(user));
        if (body != null) request.contentType(MediaType.APPLICATION_JSON).content(body);
        MockHttpServletResponse response = mockMvc.perform(request).andReturn().getResponse();
        String text = response.getContentAsString(StandardCharsets.UTF_8);
        return new Response(response.getStatus(), text.isEmpty() ? null : json.readTree(text));
    }

    private String token(String user) throws Exception {
        String cached = tokens.get(user);
        if (cached != null) return cached;
        String body = mockMvc.perform(post("/auth/login").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\": \"%s@a.com\", \"password\": \"%s\"}".formatted(user, PASSWORD)))
                .andReturn().getResponse().getContentAsString();
        String token = json.readTree(body).get("access_token").asText();
        tokens.put(user, token);
        return token;
    }
}
```

로그인 응답은 `TokenResponse(accessToken, expiresAt)`라 JSON 필드는 `access_token`이다.

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/api/AlertPreviewApiTest.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.AlertApiClient;
import com.stockproject.portfolio.alert.AlertApiClient.Response;
import com.stockproject.portfolio.alert.FixedClockConfig;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.catalog.PresetKey;
import com.stockproject.portfolio.alert.compile.Compiler;
import com.stockproject.portfolio.alert.compile.SpecHash;
import com.stockproject.portfolio.alert.spec.TriggerSpec;
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

import java.math.BigDecimal;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

/** 미리보기 (스펙 §11.3 · §12.5.4 · §12.8). */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(FixedClockConfig.class)
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class AlertPreviewApiTest {

    static final String SAMSUNG = "10000000-0000-0000-0000-000000000001";
    static final String HYNIX = "10000000-0000-0000-0000-000000000002";
    static final String NAVER = "10000000-0000-0000-0000-000000000003";
    static final String APPLE = "10000000-0000-0000-0000-000000000004";

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;
    AlertApiClient api;

    @BeforeEach
    void setUp() { api = new AlertApiClient(mockMvc, json); }

    @Test
    void 장중_가격_도달의_지금_값과_이미_충족() throws Exception {
        JsonNode body = preview("yhr", priceReach(SAMSUNG, "INTRADAY", 63400)).body();

        assertThat(body.get("valid").asBoolean()).isTrue();
        assertThat(body.get("errors")).isEmpty();
        assertThat(body.get("summary").get("short").asText()).isEqualTo("장중 · 현재가 ≥ 63,400원");
        assertThat(body.get("summary").get("sentence").asText()).isEqualTo("장중에 현재가가 63,400원 이상이면 알려요");
        JsonNode current = body.get("current");
        assertThat(current.get("result").asText()).isEqualTo("TRUE");
        assertThat(current.get("as_of").asText()).isEqualTo("2026-09-28T10:15:00+09:00");
        assertThat(current.get("header").asText()).isEqualTo("지금 · 10:15 기준");
        assertThat(current.get("result_text").asText()).isEqualTo("충족하고 있어요");
        assertThat(current.get("conditions").get(0).get("text").asText()).isEqualTo("현재가 63,500원 ≥ 63,400원");
        assertThat(body.get("already_satisfied").asBoolean()).isTrue();
        assertThat(body.get("duplicate_of").isNull()).isTrue();
    }

    /** Review Focus 1 — 데이터가 모자란 종목도 500이 아니라 확인 불가와 사유다. */
    @Test
    void 봉이_모자란_종목은_이력_부족이다() throws Exception {
        JsonNode current = preview("yhr", rsi(HYNIX, 14)).body().get("current");

        assertThat(current.get("result").asText()).isEqualTo("UNKNOWN");
        assertThat(current.get("header").asText()).isEqualTo("9/25 종가 기준");
        assertThat(current.get("result_text").asText()).isEqualTo("확인할 수 없어요");
        JsonNode line = current.get("conditions").get(0);
        assertThat(line.get("result").asText()).isEqualTo("UNKNOWN");
        assertThat(line.get("unknown_reason").asText()).isEqualTo("INSUFFICIENT_HISTORY");
        assertThat(line.get("text").asText()).isEqualTo("RSI(14) — 이력 부족 (15일 필요, 9일뿐)");
    }

    /** Review Focus 1 — 완료 신호가 하나도 없는 시장. */
    @Test
    void 완료_신호가_없으면_데이터_없음이다() throws Exception {
        jdbc.sql("DELETE FROM market_data_run WHERE market = 'US'").update();

        JsonNode current = preview("yhr", priceReach(APPLE, "CLOSE", 1)).body().get("current");

        assertThat(current.get("as_of").isNull()).isTrue();
        assertThat(current.get("header").asText()).isEqualTo("데이터 없음");
        assertThat(current.get("conditions").get(0).get("unknown_reason").asText()).isEqualTo("DATA_MISSING");
    }

    /** Review Focus 2 — 형이 틀린 본문은 200에 valid: false와 경로. */
    @Test
    void 형이_틀린_본문은_경로가_붙은_오류다() throws Exception {
        Response r = preview("yhr", """
                { "instrument_id": "%s", "name": "x", "cadence": "CLOSE", "trigger_type": "COMPOSABLE",
                  "trigger_spec": { "conditions": [ { "left": { "indicator": "rsi",
                    "indicator_params": { "n": "abc" } }, "op": "gte", "right": { "const": 70 } } ] } }
                """.formatted(SAMSUNG));

        assertThat(r.status()).isEqualTo(200);
        assertThat(r.body().get("valid").asBoolean()).isFalse();
        assertThat(r.body().get("errors").get(0).get("path").asText())
                .isEqualTo("trigger_spec.conditions[0].left.indicator_params.n");
        assertThat(r.body().get("errors").get(0).get("code").asText()).isEqualTo("INVALID_TYPE");
        assertThat(r.body().get("current").isNull()).isTrue();
    }

    @Test
    void 이름이_비어도_지금_값은_계산한다() throws Exception {
        JsonNode body = preview("yhr", rsi(SAMSUNG, 14).replace("\"name\": \"RSI\"", "\"name\": \" \"")).body();

        assertThat(body.get("valid").asBoolean()).isFalse();
        assertThat(body.get("errors").get(0).get("path").asText()).isEqualTo("name");
        assertThat(body.get("current").get("conditions").get(0).get("result").asText()).isEqualTo("TRUE");
    }

    @Test
    void 오류가_있는_조건만_빼고_평가한다() throws Exception {
        JsonNode body = preview("yhr", """
                { "instrument_id": "%s", "name": "x", "cadence": "CLOSE", "trigger_type": "COMPOSABLE",
                  "trigger_spec": { "conditions": [
                    { "left": { "indicator": "rsi", "indicator_params": { "n": 31 } }, "op": "gte", "right": { "const": 70 } },
                    { "left": { "indicator": "price" }, "op": "gte", "right": { "const": 1 } } ] } }
                """.formatted(SAMSUNG)).body();

        JsonNode current = body.get("current");
        assertThat(current.get("result").asText()).isEqualTo("UNKNOWN");
        assertThat(current.get("conditions").get(0).get("text").asText()).isEqualTo("RSI(31) — 입력을 확인해 주세요");
        assertThat(current.get("conditions").get(0).get("unknown_reason").isNull()).isTrue();
        assertThat(current.get("conditions").get(1).get("text").asText()).isEqualTo("종가 63,010원 ≥ 1원");
    }

    @Test
    void 미보유_종목의_수익률_도달은_오류이지만_지금_값을_보인다() throws Exception {
        JsonNode body = preview("jdh", """
                { "instrument_id": "%s", "name": "x", "cadence": "CLOSE", "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "pnl_reach", "params": {} } }
                """.formatted(NAVER)).body();

        assertThat(body.get("errors").get(0).get("code").asText()).isEqualTo("NOT_HELD");
        assertThat(body.get("current").get("conditions").get(0).get("text").asText())
                .isEqualTo("수익 10% 도달 — 미보유");
    }

    @Test
    void 같은_조건의_활성_알림이_있으면_중복을_알린다() throws Exception {
        UUID mine = insertAlert("40000000-0000-0000-0000-000000000001", SAMSUNG, "INTRADAY", 63400);
        insertAlert("40000000-0000-0000-0000-000000000002", SAMSUNG, "INTRADAY", 63400);

        assertThat(preview("yhr", priceReach(SAMSUNG, "INTRADAY", 63400)).body().get("duplicate_of").asText())
                .isEqualTo(mine.toString());
        assertThat(preview("yhr", priceReach(SAMSUNG, "CLOSE", 63400)).body().get("duplicate_of").isNull()).isTrue();

        String editing = priceReach(SAMSUNG, "INTRADAY", 63400).replaceFirst("\\{", "{ \"alert_id\": \"" + mine + "\",");
        assertThat(preview("yhr", editing).body().get("duplicate_of").isNull()).isTrue();
    }

    /** Review Focus 3 — 남의 알림 ID를 실은 미리보기는 없는 ID와 같다. */
    @Test
    void 남의_알림_ID로는_미리볼_수_없다() throws Exception {
        UUID others = insertAlert("40000000-0000-0000-0000-000000000002", SAMSUNG, "INTRADAY", 63400);
        String editing = priceReach(SAMSUNG, "INTRADAY", 63400).replaceFirst("\\{", "{ \"alert_id\": \"" + others + "\",");

        Response r = preview("yhr", editing);
        assertThat(r.status()).isEqualTo(404);
        assertThat(r.body().get("error").get("code").asText()).isEqualTo("ALERT_NOT_FOUND");
    }

    // ---- 도우미 ----------------------------------------------------------------

    private Response preview(String user, String body) throws Exception {
        return api.post("/alerts/preview", user, body);
    }

    static String priceReach(String instrument, String cadence, long price) {
        return """
                { "instrument_id": "%s", "name": "가격", "cadence": "%s", "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "price_reach", "params": { "direction": "up", "price": %d } } }
                """.formatted(instrument, cadence, price);
    }

    static String rsi(String instrument, int n) {
        return """
                { "instrument_id": "%s", "name": "RSI", "cadence": "CLOSE", "trigger_type": "COMPOSABLE",
                  "trigger_spec": { "conditions": [ { "left": { "indicator": "rsi", "indicator_params": { "n": %d } },
                    "op": "gte", "right": { "const": 1 } } ] } }
                """.formatted(instrument, n);
    }

    private UUID insertAlert(String userId, String instrument, String cadence, long price) {
        UUID id = UUID.randomUUID();
        Cadence c = Cadence.valueOf(cadence);
        String hash = SpecHash.of(Compiler.compile(new TriggerSpec.PresetTrigger(PresetKey.PRICE_REACH,
                Map.of("direction", "up", "price", BigDecimal.valueOf(price))), c), c);
        jdbc.sql("""
                INSERT INTO alert (alert_id, user_id, instrument_id, name, cadence, notify_mode, status,
                    trigger_type, trigger_spec, spec_version, created_at, updated_at)
                VALUES (:id, :user::uuid, :instrument::uuid, '기존', :cadence, 'EDGE_REARM', 'ACTIVE', 'PRESET',
                    '{"preset_key": "price_reach", "params": {"direction": "up", "price": 1}}'::jsonb, 1, now(), now())
                """).param("id", id).param("user", userId).param("instrument", instrument)
                .param("cadence", cadence).update();
        jdbc.sql("INSERT INTO alert_state (alert_id, last_known_result, spec_hash) VALUES (:id, 'FALSE', :hash)")
                .param("id", id).param("hash", hash).update();
        return id;
    }
}
```

`rsi(SAMSUNG, 14)`는 기준 1 이상이라 RSI가 계산되기만 하면 참이다. 같은 값이 오르기만 하는 계열이라 RSI는 100이다.

- [ ] **Step 3: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.api.AlertPreviewApiTest'`
Expected: FAIL — `/alerts/preview`가 없어 404

- [ ] **Step 4: 알림 읽기를 쓴다**

`alert/store/AlertRow.java`:

```java
package com.stockproject.portfolio.alert.store;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 삭제되지 않은 알림 한 행과 그 평가 상태. trigger_spec은 JSON 문자열이다(계획 A.4). */
public record AlertRow(UUID alertId, UUID userId, UUID instrumentId, String name, String cadence,
                       String notifyMode, Integer cooldownMin, OffsetDateTime expiresAt, String status,
                       String triggerType, String triggerSpec, int specVersion, OffsetDateTime createdAt,
                       OffsetDateTime updatedAt, String lastResult, String unknownReason,
                       OffsetDateTime evaluatedAsOf, String specHash, int version) { }
```

`alert/store/AlertMapper.java`:

```java
package com.stockproject.portfolio.alert.store;

import com.stockproject.portfolio.auth.UserScope;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.UUID;

/** 알림과 평가 상태. 모든 조회는 인증 주체의 user_id로 스코프된다(§14.5). */
@Mapper
public interface AlertMapper {

    String COLUMNS = """
            a.alert_id, a.user_id, a.instrument_id, a.name, a.cadence, a.notify_mode, a.cooldown_min,
            a.expires_at, a.status, a.trigger_type, a.trigger_spec::text AS trigger_spec, a.spec_version,
            a.created_at, a.updated_at, s.last_result, s.unknown_reason, s.evaluated_as_of, s.spec_hash, s.version
            """;

    @Select("SELECT " + COLUMNS + """
              FROM alert a JOIN alert_state s USING (alert_id)
             WHERE a.alert_id = #{alertId} AND a.user_id = #{scope.userId} AND a.deleted_at IS NULL
            """)
    AlertRow findOwned(@Param("scope") UserScope scope, @Param("alertId") UUID alertId);

    @Select("""
            SELECT a.alert_id FROM alert a JOIN alert_state s USING (alert_id)
             WHERE a.user_id = #{scope.userId} AND a.instrument_id = #{instrumentId}
               AND a.cadence = #{cadence} AND a.status = 'ACTIVE' AND a.deleted_at IS NULL
               AND s.spec_hash = #{specHash}
               AND (#{exclude}::uuid IS NULL OR a.alert_id <> #{exclude}::uuid)
             ORDER BY a.created_at, a.alert_id
             LIMIT 1
            """)
    UUID duplicateOf(@Param("scope") UserScope scope, @Param("instrumentId") UUID instrumentId,
                     @Param("cadence") String cadence, @Param("specHash") String specHash,
                     @Param("exclude") UUID exclude);
}
```

`alert/store/AlertStore.java`:

```java
package com.stockproject.portfolio.alert.store;

import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.auth.UserScope;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

/** 알림 저장소. 남의 알림과 없는 알림을 구분하지 않는다 — 둘 다 빈 값이다(§11.4). */
@Repository
public class AlertStore {

    private final AlertMapper mapper;

    public AlertStore(AlertMapper mapper) { this.mapper = mapper; }

    public Optional<AlertRow> findOwned(UserScope scope, UUID alertId) {
        return Optional.ofNullable(mapper.findOwned(scope, alertId));
    }

    /** 같은 종목 · 같은 평가 시점 · 같은 조건 해시의 활성 알림 (§6.7). */
    public Optional<UUID> duplicateOf(UserScope scope, UUID instrumentId, Cadence cadence, String specHash,
                                      UUID excludeAlertId) {
        return Optional.ofNullable(mapper.duplicateOf(scope, instrumentId, cadence.name(), specHash, excludeAlertId));
    }
}
```

- [ ] **Step 5: 응답 타입과 오류 처리를 쓴다**

`alert/api/dto/SummaryDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/** 조건 문장 (§12.1). short는 자바 예약어라 필드 이름만 바꾼다. */
public record SummaryDto(@JsonProperty("short") String shortText, String sentence) { }
```

`alert/api/dto/LineDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import com.stockproject.portfolio.alert.evaluation.Truth;
import com.stockproject.portfolio.alert.evaluation.UnknownReason;

/** 현재값 상자의 한 줄 (§12.5.4). */
public record LineDto(Truth result, UnknownReason unknownReason, String text) { }
```

`alert/api/dto/CurrentDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import com.stockproject.portfolio.alert.evaluation.Truth;

import java.time.OffsetDateTime;
import java.util.List;

/** 현재값 상자 (§11.3). header와 result_text는 서버가 완성한다. */
public record CurrentDto(Truth result, OffsetDateTime asOf, String header, String resultText,
                         List<LineDto> conditions) { }
```

`alert/api/dto/PreviewResponse.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import com.stockproject.portfolio.alert.validation.FieldError;

import java.util.List;
import java.util.UUID;

/** POST /alerts/preview 응답 (§11.3). 검증 오류가 있어도 200이다. */
public record PreviewResponse(boolean valid, List<FieldError> errors, SummaryDto summary, CurrentDto current,
                              boolean alreadySatisfied, UUID duplicateOf) { }
```

`alert/api/dto/InvalidAlertError.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import com.stockproject.portfolio.alert.validation.FieldError;

import java.util.List;

/**
 * 저장 검증 실패 응답 (§11.4). 기존 ApiError에 fields를 더하지 않는 것은
 * 다른 오류 응답에 "fields": null이 생기지 않게 하기 위해서다(계획 A.8).
 */
public record InvalidAlertError(Detail error) {

    public record Detail(String code, String message, List<FieldError> fields) { }

    public static InvalidAlertError of(List<FieldError> fields) {
        return new InvalidAlertError(new Detail("INVALID_ALERT", "조건을 확인해 주세요", fields));
    }
}
```

`alert/api/AlertExceptionHandler.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.stockproject.portfolio.alert.api.dto.InvalidAlertError;
import com.stockproject.portfolio.alert.validation.InvalidAlertException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/** 알림 저장 검증 실패를 칸별 오류로 옮긴다. 나머지 오류는 ApiExceptionHandler가 맡는다. */
@RestControllerAdvice
public class AlertExceptionHandler {

    @ExceptionHandler(InvalidAlertException.class)
    public ResponseEntity<InvalidAlertError> invalidAlert(InvalidAlertException e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(InvalidAlertError.of(e.fields()));
    }
}
```

- [ ] **Step 6: 미리보기 서비스와 컨트롤러를 쓴다**

`alert/service/AlertTimes.java`:

```java
package com.stockproject.portfolio.alert.service;

import java.time.OffsetDateTime;
import java.time.ZoneId;

/** 응답의 시각은 한국 시간 오프셋으로 쓴다. DB가 돌려주는 timestamptz는 UTC 오프셋으로 온다. */
public final class AlertTimes {

    private AlertTimes() { }

    private static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");

    public static OffsetDateTime kst(OffsetDateTime at) {
        return at == null ? null : at.atZoneSameInstant(SEOUL).toOffsetDateTime();
    }
}
```

`alert/service/AlertPreviewService.java`:

```java
package com.stockproject.portfolio.alert.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.stockproject.portfolio.alert.api.dto.CurrentDto;
import com.stockproject.portfolio.alert.api.dto.LineDto;
import com.stockproject.portfolio.alert.api.dto.PreviewResponse;
import com.stockproject.portfolio.alert.api.dto.SummaryDto;
import com.stockproject.portfolio.alert.compile.CompiledTrigger;
import com.stockproject.portfolio.alert.compile.Compiler;
import com.stockproject.portfolio.alert.compile.SpecHash;
import com.stockproject.portfolio.alert.data.EvaluationInputFactory;
import com.stockproject.portfolio.alert.data.HoldingReader;
import com.stockproject.portfolio.alert.data.InstrumentRow;
import com.stockproject.portfolio.alert.data.MarketDataRepository;
import com.stockproject.portfolio.alert.evaluation.ConditionEvaluator;
import com.stockproject.portfolio.alert.evaluation.EvaluationInput;
import com.stockproject.portfolio.alert.evaluation.EvaluationResult;
import com.stockproject.portfolio.alert.evaluation.Truth;
import com.stockproject.portfolio.alert.sentence.Line;
import com.stockproject.portfolio.alert.sentence.OperandNames;
import com.stockproject.portfolio.alert.sentence.SentenceWriter;
import com.stockproject.portfolio.alert.sentence.Summary;
import com.stockproject.portfolio.alert.spec.AlertDraft;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.TriggerSpec;
import com.stockproject.portfolio.alert.store.AlertStore;
import com.stockproject.portfolio.alert.validation.AlertRequestParser;
import com.stockproject.portfolio.alert.validation.AlertValidator;
import com.stockproject.portfolio.alert.validation.ExistingAlert;
import com.stockproject.portfolio.alert.validation.FieldError;
import com.stockproject.portfolio.alert.validation.InstrumentFacts;
import com.stockproject.portfolio.alert.validation.ParseResult;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.domain.Market;
import com.stockproject.portfolio.validation.RequestRejected;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * 저장 전 초안 하나로 검증 오류 · 지금 값 · 지금 충족 여부 · 중복을 한 번에 돌려준다 (§11.3).
 * 검증 오류가 있어도 계산할 수 있는 조건의 지금 값은 채운다 — 입력 중인 폼의 상태이지
 * 요청의 실패가 아니다. 알림 상세의 현재값 상자도 alert_id를 실어 이 경로를 쓴다(§12.4).
 */
@Service
public class AlertPreviewService {

    private final MarketDataRepository market;
    private final HoldingReader holdings;
    private final EvaluationInputFactory inputs;
    private final AlertStore alerts;
    private final Clock clock;

    public AlertPreviewService(MarketDataRepository market, HoldingReader holdings, EvaluationInputFactory inputs,
                               AlertStore alerts, Clock clock) {
        this.market = market;
        this.holdings = holdings;
        this.inputs = inputs;
        this.alerts = alerts;
        this.clock = clock;
    }

    public PreviewResponse preview(UserScope scope, JsonNode body) {
        ParseResult parsed = AlertRequestParser.parse(body);
        ExistingAlert existing = parsed.alertId() == null ? null : alerts.findOwned(scope, parsed.alertId())
                .map(a -> new ExistingAlert(a.instrumentId(), a.triggerType()))
                .orElseThrow(() -> new RequestRejected("ALERT_NOT_FOUND", "알림을 찾을 수 없어요", true));
        if (!parsed.ok()) return new PreviewResponse(false, parsed.errors(), null, null, false, null);

        AlertDraft draft = parsed.draft();
        InstrumentRow instrument = market.instrument(draft.instrumentId()).orElse(null);
        InstrumentFacts facts = instrument == null ? null : new InstrumentFacts(instrument.marketEnum(),
                instrument.assetClass(), instrument.delistedOn() != null, holdings.held(scope, instrument));
        List<FieldError> errors = AlertValidator.validate(draft, facts, existing, OffsetDateTime.now(clock));
        Market shown = instrument == null ? Market.KR : instrument.marketEnum();

        if (!compilable(draft.trigger(), errors)) {
            return new PreviewResponse(errors.isEmpty(), errors, null, null, false, null);
        }
        CompiledTrigger compiled = Compiler.compile(draft.trigger(), draft.cadence());
        Summary summary = SentenceWriter.summary(compiled, draft.cadence(), shown);
        CurrentDto current = current(scope, instrument, compiled, draft, errors);
        UUID duplicate = alerts.duplicateOf(scope, draft.instrumentId(), draft.cadence(),
                SpecHash.of(compiled, draft.cadence()), parsed.alertId()).orElse(null);

        return new PreviewResponse(errors.isEmpty(), errors, new SummaryDto(summary.shortText(), summary.sentence()),
                current, current != null && current.result() == Truth.TRUE, duplicate);
    }

    /** 프리셋은 입력 칸이 맞아야, 조립형은 조건 목록 자체가 맞아야 컴파일할 수 있다. */
    private static boolean compilable(TriggerSpec trigger, List<FieldError> errors) {
        return switch (trigger) {
            case TriggerSpec.PresetTrigger p -> errors.stream()
                    .noneMatch(e -> e.path().startsWith("trigger_spec") || e.path().equals("cadence"));
            case TriggerSpec.Composable c -> errors.stream()
                    .noneMatch(e -> e.path().equals("trigger_spec") || e.path().equals("trigger_spec.conditions"));
        };
    }

    private CurrentDto current(UserScope scope, InstrumentRow instrument, CompiledTrigger compiled, AlertDraft draft,
                               List<FieldError> errors) {
        List<Integer> broken = new ArrayList<>();
        if (compiled.preset() == null) {
            for (int i = 0; i < compiled.conditions().size(); i++) {
                String prefix = "trigger_spec.conditions[" + i + "]";
                if (errors.stream().anyMatch(e -> e.path().startsWith(prefix))) broken.add(i);
            }
        }
        List<Condition> healthy = new ArrayList<>();
        for (int i = 0; i < compiled.conditions().size(); i++) {
            if (!broken.contains(i)) healthy.add(compiled.conditions().get(i));
        }
        CompiledTrigger evaluated = new CompiledTrigger(healthy, compiled.preset(), compiled.presetParams());
        EvaluationInput input = inputs.forPreview(scope, instrument, evaluated, draft.cadence());
        EvaluationResult result = ConditionEvaluator.evaluate(evaluated, input);
        List<Line> lines = SentenceWriter.lines(evaluated, result, input);

        List<LineDto> out = new ArrayList<>();
        int next = 0;
        for (int i = 0; i < (compiled.preset() == null ? compiled.conditions().size() : lines.size()); i++) {
            if (broken.contains(i)) {
                String name = OperandNames.name(compiled.conditions().get(i).left(), draft.cadence());
                out.add(new LineDto(Truth.UNKNOWN, null, name + " — 입력을 확인해 주세요"));
            } else {
                Line line = lines.get(next++);
                out.add(new LineDto(line.result(), line.reason(), line.text()));
            }
        }
        Truth truth = result.truth();
        if (!broken.isEmpty() && truth == Truth.TRUE) truth = Truth.UNKNOWN;
        return new CurrentDto(truth, AlertTimes.kst(result.asOf()), SentenceWriter.header(evaluated, result, input),
                SentenceWriter.resultText(truth), out);
    }
}
```

`alert/api/AlertController.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.stockproject.portfolio.alert.api.dto.PreviewResponse;
import com.stockproject.portfolio.alert.service.AlertPreviewService;
import com.stockproject.portfolio.auth.UserScope;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 알림 규칙 (스펙 §11.1). 본문을 JsonNode로 받는 것은 형이 틀린 값도 경로가 붙은 오류로
 * 돌려주기 위해서다 — 레코드로 바로 받으면 Jackson이 첫 오류에서 멈춘다.
 */
@RestController
@RequestMapping("/alerts")
public class AlertController {

    private final AlertPreviewService preview;

    public AlertController(AlertPreviewService preview) {
        this.preview = preview;
    }

    @PostMapping("/preview")
    public PreviewResponse preview(UserScope scope, @RequestBody JsonNode body) {
        return preview.preview(scope, body);
    }
}
```

- [ ] **Step 7: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.api.AlertPreviewApiTest'`
Expected: PASS

- [ ] **Step 8: 아키텍처 규칙도 통과하는지 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.ArchitectureRulesTest'`
Expected: PASS — `alert.api`가 매퍼·저장소를 직접 부르지 않는다.

- [ ] **Step 9: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert/store src/main/java/com/stockproject/portfolio/alert/service \
        src/main/java/com/stockproject/portfolio/alert/api \
        src/test/java/com/stockproject/portfolio/alert/AlertApiClient.java \
        src/test/java/com/stockproject/portfolio/alert/FixedClockConfig.java \
        src/test/java/com/stockproject/portfolio/alert/api/AlertPreviewApiTest.java
git commit -m "feat: 알림 미리보기 API를 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: 만들기 · 수정 · 삭제 · 끄기 · 다시 켜기

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/validation/TriggerSpecWriter.java`
- Modify: `src/main/java/com/stockproject/portfolio/alert/validation/AlertRequestParser.java` (`stored` 추가)
- Modify: `src/main/java/com/stockproject/portfolio/alert/store/AlertMapper.java` · `AlertStore.java` (쓰기 메서드 추가)
- Create: `src/main/java/com/stockproject/portfolio/alert/store/WatchlistMapper.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/service/AlertCommandService.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/api/dto/AlertIdResponse.java`
- Modify: `src/main/java/com/stockproject/portfolio/alert/api/AlertController.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/validation/TriggerSpecWriterTest.java` · `src/test/java/com/stockproject/portfolio/alert/api/AlertCommandApiTest.java`

**Interfaces:**
- Consumes: Task 10의 `AlertStore` · `AlertRow` · `AlertApiClient` · `FixedClockConfig` · 샘플 데이터, Task 3 · 4 · 5.
- Produces:
  - `TriggerSpecWriter.write(TriggerSpec) → ObjectNode` — 저장 모양. 조립형은 `lag`이 없고 변형이 늘 명시된다.
  - `AlertRequestParser.stored(String triggerType, JsonNode spec) → TriggerSpec` — 저장된 모양을 다시 읽는다.
  - `AlertStore` 쓰기 — `insert(UserScope, UUID alertId, AlertDraft, String triggerSpecJson, String specHash, OffsetDateTime now)` · `update(UUID alertId, AlertDraft, String triggerSpecJson, String specHash, OffsetDateTime now)` · `softDelete(UUID alertId, OffsetDateTime now)` · `changeStatus(UUID alertId, AlertStatus status, OffsetDateTime expiresAt, boolean setExpiresAt, OffsetDateTime now)` · `resetState(UUID alertId, String specHash)` · `bumpVersion(UUID alertId)` · `refreshWatchlist(UUID instrumentId)`.
  - `AlertCommandService` — `UUID create(UserScope, JsonNode)` · `UUID update(UserScope, UUID, JsonNode)` · `void delete(UserScope, UUID)` · `void pause(UserScope, UUID)` · `void resume(UserScope, UUID, JsonNode body)`.
  - `record AlertIdResponse(UUID alertId)`.
  - 응답: `POST /alerts` → `201 {alert_id}` · `PUT /alerts/{id}` → `200 {alert_id}` · `DELETE` · `pause` · `resume` → `204`.

상태 전환표:

| 요청 | 지금 상태 | 결과 |
|---|---|---|
| `pause` | `ACTIVE` | `PAUSED`, `version + 1` |
| `pause` | 그 밖 | `400 INVALID_STATUS_TRANSITION` |
| `resume` | `PAUSED` · `ENDED` | `ACTIVE`, 상태 초기화(§6.3) |
| `resume` | `EXPIRED` | 본문에 `expires_at` 키가 있어야 한다(`null`이면 무기한). 없으면 `400 INVALID_ALERT`(`expires_at` · `REQUIRED`), 지난 시각이면 `PAST` |
| `resume` | `ACTIVE` | `400 INVALID_STATUS_TRANSITION` |

상태 초기화 = 엣지 기준 `FALSE`, `last_result` · `unknown_reason` · `evaluated_as_of` 비움, 새 `spec_hash`, `version + 1`. 수정 · 다시 켜기가 초기화하고, 생성은 같은 값으로 시작한다(`version` 0). 끄기 · 삭제는 `version`만 올린다. 알림이 생기거나 상태가 바뀌거나 삭제되면 그 종목의 `alert_watchlist` 행을 같은 트랜잭션에서 다시 계산한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/validation/TriggerSpecWriterTest.java`:

```java
package com.stockproject.portfolio.alert.validation;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/** 저장 모양은 해석한 모델에서 다시 쓴다 — 모르는 필드가 섞이지 않고, 기본값이 명시된다. */
class TriggerSpecWriterTest {

    private static final ObjectMapper JSON = new ObjectMapper();

    @Test
    void 조립형은_변형을_명시하고_모르는_필드를_버린다() throws Exception {
        ParseResult parsed = AlertRequestParser.parse(JSON.readTree("""
                { "instrument_id": "10000000-0000-0000-0000-000000000001", "name": "x", "cadence": "CLOSE",
                  "trigger_type": "COMPOSABLE", "trigger_spec": { "extra": 1, "conditions": [
                    { "left": { "indicator": "sma", "indicator_params": { "n": 5 } }, "op": "gt",
                      "right": { "indicator": "high", "transform": { "type": "window", "fn": "max", "n": 20 } },
                      "modifier": { "streak": 2 } } ] } }
                """));

        assertThat(TriggerSpecWriter.write(parsed.draft().trigger())).isEqualTo(JSON.readTree("""
                { "conditions": [ {
                    "left": { "indicator": "sma", "indicator_params": { "n": 5 }, "transform": { "type": "identity" } },
                    "op": "gt",
                    "right": { "indicator": "high", "indicator_params": {},
                               "transform": { "type": "window", "fn": "max", "n": 20 } },
                    "modifier": { "streak": 2 } } ] }
                """));
    }

    @Test
    void 프리셋은_받은_입력을_그대로_쓴다() throws Exception {
        ParseResult parsed = AlertRequestParser.parse(JSON.readTree("""
                { "instrument_id": "10000000-0000-0000-0000-000000000001", "name": "x", "cadence": "CLOSE",
                  "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "rsi_zone", "params": { "zone": "oversold", "level": 25.5 } } }
                """));

        assertThat(TriggerSpecWriter.write(parsed.draft().trigger()).toString())
                .isEqualTo("{\"preset_key\":\"rsi_zone\",\"params\":{\"level\":25.5,\"zone\":\"oversold\"}}");
    }

    @Test
    void 저장된_모양을_다시_읽는다() throws Exception {
        ParseResult parsed = AlertRequestParser.parse(JSON.readTree("""
                { "instrument_id": "10000000-0000-0000-0000-000000000001", "name": "x", "cadence": "CLOSE",
                  "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "rsi_zone", "params": { "zone": "oversold", "level": 25.5 } } }
                """));
        var written = TriggerSpecWriter.write(parsed.draft().trigger());

        assertThat(AlertRequestParser.stored("PRESET", JSON.readTree(written.toString())))
                .isEqualTo(parsed.draft().trigger());
    }

    @Test
    void 상수와_유지_조건이_없는_조건() throws Exception {
        ParseResult parsed = AlertRequestParser.parse(JSON.readTree("""
                { "instrument_id": "10000000-0000-0000-0000-000000000001", "name": "x", "cadence": "INTRADAY",
                  "trigger_type": "COMPOSABLE", "trigger_spec": { "conditions": [
                    { "left": { "indicator": "price" }, "op": "gte", "right": { "const": 70000 } } ] } }
                """));

        assertThat(TriggerSpecWriter.write(parsed.draft().trigger()).toString()).isEqualTo(
                "{\"conditions\":[{\"left\":{\"indicator\":\"price\",\"indicator_params\":{},"
                        + "\"transform\":{\"type\":\"identity\"}},\"op\":\"gte\",\"right\":{\"const\":70000},"
                        + "\"modifier\":null}]}");
    }
}
```

`src/test/java/com/stockproject/portfolio/alert/api/AlertCommandApiTest.java`:

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

import java.util.Map;
import java.util.UUID;

import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.SAMSUNG;
import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.NAVER;
import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.priceReach;
import static org.assertj.core.api.Assertions.assertThat;

/** 알림 명령 (스펙 §6.3 · §6.5 · §6.8 · §14). */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(FixedClockConfig.class)
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class AlertCommandApiTest {

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;
    AlertApiClient api;

    @BeforeEach
    void setUp() { api = new AlertApiClient(mockMvc, json); }

    @Test
    void 만들면_감시_중이고_엣지_기준은_거짓에서_시작한다() throws Exception {
        Response r = api.post("/alerts", "yhr", priceReach(SAMSUNG, "INTRADAY", 70000));

        assertThat(r.status()).isEqualTo(201);
        UUID id = UUID.fromString(r.body().get("alert_id").asText());
        Map<String, Object> row = row(id);
        assertThat(row).containsEntry("status", "ACTIVE").containsEntry("spec_version", 1)
                .containsEntry("last_known_result", "FALSE").containsEntry("version", 0);
        assertThat(row.get("last_result")).isNull();
        assertThat(row.get("evaluated_as_of")).isNull();
        assertThat((String) row.get("spec_hash")).hasSize(64);
        assertThat(watchlist()).containsEntry(UUID.fromString(SAMSUNG), true);
    }

    /** Review Focus 2 — 저장은 같은 오류를 400으로 돌려준다. */
    @Test
    void 검증에_실패하면_칸별_오류다() throws Exception {
        Response r = api.post("/alerts", "yhr", """
                { "instrument_id": "%s", "name": "x", "cadence": "CLOSE", "notify_mode": "COOLDOWN",
                  "cooldown_min": 30, "trigger_type": "COMPOSABLE",
                  "trigger_spec": { "conditions": [ { "left": { "indicator": "price" }, "op": "gte",
                    "right": { "const": 1 }, "modifier": { "persist_min": 10 } } ] } }
                """.formatted(SAMSUNG));

        assertThat(r.status()).isEqualTo(400);
        JsonNode error = r.body().get("error");
        assertThat(error.get("code").asText()).isEqualTo("INVALID_ALERT");
        assertThat(error.get("fields")).extracting(f -> f.get("path").asText() + ":" + f.get("code").asText())
                .containsExactly("notify_mode:CADENCE_NOT_ALLOWED",
                        "trigger_spec.conditions[0].modifier:MODIFIER_NOT_ALLOWED");
        assertThat(jdbc.sql("SELECT count(*) FROM alert").query(Long.class).single()).isZero();
    }

    @Test
    void 형이_틀린_본문도_칸별_오류다() throws Exception {
        Response r = api.post("/alerts", "yhr", """
                { "instrument_id": "%s", "name": "x", "cadence": "CLOSE", "trigger_type": "COMPOSABLE",
                  "trigger_spec": { "conditions": {} } }
                """.formatted(SAMSUNG));

        assertThat(r.status()).isEqualTo(400);
        assertThat(r.body().get("error").get("fields").get(0).get("path").asText()).isEqualTo("trigger_spec.conditions");
    }

    @Test
    void 보유하지_않은_종목에_수익률_조건은_만들_수_없다() throws Exception {
        Response r = api.post("/alerts", "jdh", """
                { "instrument_id": "%s", "name": "x", "cadence": "CLOSE", "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "pnl_reach", "params": {} } }
                """.formatted(NAVER));

        assertThat(r.status()).isEqualTo(400);
        assertThat(r.body().get("error").get("fields").get(0).get("code").asText()).isEqualTo("NOT_HELD");
    }

    @Test
    void 수정하면_상태를_다시_기준_잡는다() throws Exception {
        UUID id = create("yhr", priceReach(SAMSUNG, "INTRADAY", 70000));
        jdbc.sql("""
                UPDATE alert_state SET last_known_result = 'TRUE', last_result = 'TRUE',
                       evaluated_as_of = now() WHERE alert_id = :id
                """).param("id", id).update();
        String before = (String) row(id).get("spec_hash");

        Response r = api.put("/alerts/" + id, "yhr", priceReach(SAMSUNG, "CLOSE", 71000));

        assertThat(r.status()).isEqualTo(200);
        Map<String, Object> row = row(id);
        assertThat(row).containsEntry("cadence", "CLOSE").containsEntry("last_known_result", "FALSE")
                .containsEntry("version", 1);
        assertThat(row.get("last_result")).isNull();
        assertThat(row.get("evaluated_as_of")).isNull();
        assertThat(row.get("spec_hash")).isNotEqualTo(before);
        assertThat(watchlist()).containsEntry(UUID.fromString(SAMSUNG), false);
    }

    @Test
    void 수정에서_종목을_바꿀_수_없다() throws Exception {
        UUID id = create("yhr", priceReach(SAMSUNG, "INTRADAY", 70000));

        Response r = api.put("/alerts/" + id, "yhr", priceReach(NAVER, "INTRADAY", 70000));

        assertThat(r.status()).isEqualTo(400);
        assertThat(r.body().get("error").get("fields").get(0).get("code").asText()).isEqualTo("IMMUTABLE");
    }

    /** Review Focus 3 — 남의 알림은 없는 알림과 같은 404다. */
    @Test
    void 남의_알림은_고치지도_지우지도_끄지도_못한다() throws Exception {
        UUID others = create("jdh", priceReach(SAMSUNG, "INTRADAY", 70000));

        for (Response r : new Response[] {
                api.put("/alerts/" + others, "yhr", priceReach(SAMSUNG, "INTRADAY", 1)),
                api.delete("/alerts/" + others, "yhr"),
                api.post("/alerts/" + others + "/pause", "yhr", null),
                api.post("/alerts/" + others + "/resume", "yhr", "{}"),
                api.delete("/alerts/" + UUID.randomUUID(), "yhr")}) {
            assertThat(r.status()).isEqualTo(404);
            assertThat(r.body().get("error").get("code").asText()).isEqualTo("ALERT_NOT_FOUND");
        }
        assertThat(row(others)).containsEntry("status", "ACTIVE");
    }

    @Test
    void 지우면_기록은_남고_대상_종목에서_빠진다() throws Exception {
        UUID id = create("yhr", priceReach(SAMSUNG, "INTRADAY", 70000));
        jdbc.sql("""
                INSERT INTO alert_event (event_id, alert_id, as_of, fired_at, title, body, lines, observed)
                VALUES (gen_random_uuid(), :id, now(), now(), '삼성전자 · 가격 도달', '본문', '[]', '{}')
                """).param("id", id).update();

        assertThat(api.delete("/alerts/" + id, "yhr").status()).isEqualTo(204);

        assertThat(jdbc.sql("SELECT deleted_at IS NOT NULL FROM alert WHERE alert_id = :id").param("id", id)
                .query(Boolean.class).single()).isTrue();
        assertThat(jdbc.sql("SELECT count(*) FROM alert_event WHERE alert_id = :id").param("id", id)
                .query(Long.class).single()).isEqualTo(1);
        assertThat(watchlist()).doesNotContainKey(UUID.fromString(SAMSUNG));
        assertThat(api.put("/alerts/" + id, "yhr", priceReach(SAMSUNG, "INTRADAY", 1)).status()).isEqualTo(404);
    }

    @Test
    void 끄고_다시_켠다() throws Exception {
        UUID id = create("yhr", priceReach(SAMSUNG, "INTRADAY", 70000));

        assertThat(api.post("/alerts/" + id + "/pause", "yhr", null).status()).isEqualTo(204);
        assertThat(row(id)).containsEntry("status", "PAUSED").containsEntry("version", 1);
        assertThat(watchlist()).doesNotContainKey(UUID.fromString(SAMSUNG));

        Response again = api.post("/alerts/" + id + "/pause", "yhr", null);
        assertThat(again.status()).isEqualTo(400);
        assertThat(again.body().get("error").get("code").asText()).isEqualTo("INVALID_STATUS_TRANSITION");

        assertThat(api.post("/alerts/" + id + "/resume", "yhr", null).status()).isEqualTo(204);
        assertThat(row(id)).containsEntry("status", "ACTIVE").containsEntry("version", 2)
                .containsEntry("last_known_result", "FALSE");
        assertThat(watchlist()).containsKey(UUID.fromString(SAMSUNG));
    }

    @Test
    void 만료된_알림은_새_유효기간과_함께_다시_켠다() throws Exception {
        UUID id = create("yhr", priceReach(SAMSUNG, "INTRADAY", 70000));
        jdbc.sql("UPDATE alert SET status = 'EXPIRED', expires_at = '2026-09-01T00:00:00+09' WHERE alert_id = :id")
                .param("id", id).update();

        Response missing = api.post("/alerts/" + id + "/resume", "yhr", "{}");
        assertThat(missing.status()).isEqualTo(400);
        assertThat(missing.body().get("error").get("fields").get(0).get("path").asText()).isEqualTo("expires_at");
        assertThat(missing.body().get("error").get("fields").get(0).get("code").asText()).isEqualTo("REQUIRED");

        Response past = api.post("/alerts/" + id + "/resume", "yhr", "{\"expires_at\": \"2026-09-27T00:00:00+09:00\"}");
        assertThat(past.body().get("error").get("fields").get(0).get("code").asText()).isEqualTo("PAST");

        assertThat(api.post("/alerts/" + id + "/resume", "yhr", "{\"expires_at\": null}").status()).isEqualTo(204);
        assertThat(row(id)).containsEntry("status", "ACTIVE");
        assertThat(row(id).get("expires_at")).isNull();
    }

    @Test
    void 울린_뒤_종료된_알림을_다시_켠다() throws Exception {
        UUID id = create("yhr", priceReach(SAMSUNG, "INTRADAY", 70000));
        jdbc.sql("UPDATE alert SET status = 'ENDED' WHERE alert_id = :id").param("id", id).update();

        assertThat(api.post("/alerts/" + id + "/resume", "yhr", null).status()).isEqualTo(204);
        assertThat(row(id)).containsEntry("status", "ACTIVE");
    }

    // ---- 도우미 ----------------------------------------------------------------

    private UUID create(String user, String body) throws Exception {
        Response r = api.post("/alerts", user, body);
        assertThat(r.status()).isEqualTo(201);
        return UUID.fromString(r.body().get("alert_id").asText());
    }

    private Map<String, Object> row(UUID id) {
        return jdbc.sql("""
                SELECT a.status, a.cadence, a.spec_version, a.expires_at, s.last_result, s.last_known_result,
                       s.evaluated_as_of, s.spec_hash, s.version
                  FROM alert a JOIN alert_state s USING (alert_id) WHERE a.alert_id = :id
                """).param("id", id).query().singleRow();
    }

    private Map<UUID, Boolean> watchlist() {
        return jdbc.sql("SELECT instrument_id, intraday FROM alert_watchlist")
                .query((rs, i) -> Map.entry(rs.getObject("instrument_id", UUID.class), rs.getBoolean("intraday")))
                .list().stream().collect(java.util.stream.Collectors.toMap(Map.Entry::getKey, Map.Entry::getValue));
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.validation.TriggerSpecWriterTest' --tests 'com.stockproject.portfolio.alert.api.AlertCommandApiTest'`
Expected: FAIL — 컴파일 오류(`TriggerSpecWriter` 없음)

- [ ] **Step 3: 저장 모양을 쓴다**

`alert/validation/TriggerSpecWriter.java`:

```java
package com.stockproject.portfolio.alert.validation;

import com.fasterxml.jackson.databind.node.JsonNodeFactory;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.stockproject.portfolio.alert.spec.Condition;
import com.stockproject.portfolio.alert.spec.Modifier;
import com.stockproject.portfolio.alert.spec.Operand;
import com.stockproject.portfolio.alert.spec.Transform;
import com.stockproject.portfolio.alert.spec.TriggerSpec;

import java.math.BigDecimal;
import java.util.Map;
import java.util.TreeMap;

/**
 * trigger_spec의 저장 모양. 요청 원문이 아니라 해석한 모델에서 다시 쓴다 — 모르는 필드가 섞이지
 * 않고, 변형이 늘 명시된다. 조립형에는 lag이 없다(§4.2). 수정 화면이 받은 spec을 그대로 다시
 * 보내도 거부되지 않는 모양이다.
 */
public final class TriggerSpecWriter {

    private TriggerSpecWriter() { }

    private static final JsonNodeFactory F = JsonNodeFactory.instance;

    public static ObjectNode write(TriggerSpec trigger) {
        ObjectNode out = F.objectNode();
        switch (trigger) {
            case TriggerSpec.Composable c -> {
                var list = out.putArray("conditions");
                for (Condition condition : c.conditions()) list.add(condition(condition));
            }
            case TriggerSpec.PresetTrigger p -> {
                out.put("preset_key", p.key().key());
                ObjectNode params = out.putObject("params");
                for (Map.Entry<String, Object> e : new TreeMap<>(p.params()).entrySet()) {
                    if (e.getValue() instanceof BigDecimal n) params.put(e.getKey(), n);
                    else params.put(e.getKey(), (String) e.getValue());
                }
            }
        }
        return out;
    }

    private static ObjectNode condition(Condition c) {
        ObjectNode out = F.objectNode();
        out.set("left", operand(c.left()));
        out.put("op", c.op().key());
        if (c.right().isConstant()) out.putObject("right").put("const", c.right().constant());
        else out.set("right", operand(c.right().operand()));
        switch (c.modifier()) {
            case null -> out.putNull("modifier");
            case Modifier.Streak s -> out.putObject("modifier").put("streak", s.n());
            case Modifier.PersistMin p -> out.putObject("modifier").put("persist_min", p.minutes());
        }
        return out;
    }

    private static ObjectNode operand(Operand o) {
        ObjectNode out = F.objectNode();
        out.put("indicator", o.indicator().key());
        ObjectNode params = out.putObject("indicator_params");
        new TreeMap<>(o.params()).forEach(params::put);
        ObjectNode t = out.putObject("transform");
        t.put("type", o.transform().type().key());
        switch (o.transform()) {
            case Transform.Identity i -> { }
            case Transform.Window w -> t.put("fn", w.fn().key()).put("n", w.n());
            case Transform.Delta d -> t.put("n", d.n());
            case Transform.Pct p -> t.put("n", p.n());
        }
        return out;
    }
}
```

`TreeMap`으로 키 순서를 고정한다. 프리셋 입력의 키 순서가 요청마다 달라도 같은 JSON이 저장된다.

`alert/validation/AlertRequestParser.java`에 저장된 모양을 다시 읽는 메서드를 더한다(`import com.fasterxml.jackson.databind.node.JsonNodeFactory;` · `com.fasterxml.jackson.databind.node.ObjectNode;` 추가). 다시 켜기의 해시와 Task 12의 상세·목록 문장이 쓴다.

```java
    /** 저장된 trigger_spec을 모델로 옮긴다. 저장 전에 검증을 통과한 값이라 오류가 있으면 버그다. */
    public static TriggerSpec stored(String triggerType, JsonNode spec) {
        ObjectNode body = JsonNodeFactory.instance.objectNode();
        body.put("trigger_type", triggerType);
        body.set("trigger_spec", spec);
        List<FieldError> errors = new ArrayList<>();
        TriggerSpec trigger = trigger(body, errors);
        if (!errors.isEmpty()) throw new IllegalStateException("저장된 trigger_spec을 읽을 수 없다: " + errors);
        return trigger;
    }
```

- [ ] **Step 4: 쓰기 쿼리를 더한다**

`alert/store/AlertMapper.java`에 다음 메서드를 더한다(`import org.apache.ibatis.annotations.Insert;` · `Update` · `java.time.OffsetDateTime` 추가).

```java
    @Insert("""
            INSERT INTO alert (alert_id, user_id, instrument_id, name, cadence, notify_mode, cooldown_min,
                               expires_at, status, trigger_type, trigger_spec, spec_version, created_at, updated_at)
            VALUES (#{alertId}, #{scope.userId}, #{instrumentId}, #{name}, #{cadence}, #{notifyMode}, #{cooldownMin},
                    #{expiresAt}, 'ACTIVE', #{triggerType}, CAST(#{triggerSpec} AS jsonb), #{specVersion}, #{now}, #{now})
            """)
    void insertAlert(@Param("scope") UserScope scope, @Param("alertId") UUID alertId,
                     @Param("instrumentId") UUID instrumentId, @Param("name") String name,
                     @Param("cadence") String cadence, @Param("notifyMode") String notifyMode,
                     @Param("cooldownMin") Integer cooldownMin, @Param("expiresAt") OffsetDateTime expiresAt,
                     @Param("triggerType") String triggerType, @Param("triggerSpec") String triggerSpec,
                     @Param("specVersion") int specVersion, @Param("now") OffsetDateTime now);

    @Insert("""
            INSERT INTO alert_state (alert_id, last_known_result, spec_hash, version)
            VALUES (#{alertId}, 'FALSE', #{specHash}, 0)
            """)
    void insertState(@Param("alertId") UUID alertId, @Param("specHash") String specHash);

    @Update("""
            UPDATE alert SET name = #{name}, cadence = #{cadence}, notify_mode = #{notifyMode},
                   cooldown_min = #{cooldownMin}, expires_at = #{expiresAt},
                   trigger_spec = CAST(#{triggerSpec} AS jsonb), spec_version = #{specVersion}, updated_at = #{now}
             WHERE alert_id = #{alertId}
            """)
    void updateAlert(@Param("alertId") UUID alertId, @Param("name") String name, @Param("cadence") String cadence,
                     @Param("notifyMode") String notifyMode, @Param("cooldownMin") Integer cooldownMin,
                     @Param("expiresAt") OffsetDateTime expiresAt, @Param("triggerSpec") String triggerSpec,
                     @Param("specVersion") int specVersion, @Param("now") OffsetDateTime now);

    /** 엣지 기준을 거짓으로, 평가 시점을 비우고, 새 해시와 버전으로 (§6.3 · §6.6). */
    @Update("""
            UPDATE alert_state SET last_result = NULL, last_known_result = 'FALSE', unknown_reason = NULL,
                   evaluated_as_of = NULL, spec_hash = #{specHash}, version = version + 1
             WHERE alert_id = #{alertId}
            """)
    void resetState(@Param("alertId") UUID alertId, @Param("specHash") String specHash);

    @Update("UPDATE alert_state SET version = version + 1 WHERE alert_id = #{alertId}")
    void bumpVersion(@Param("alertId") UUID alertId);

    @Update("UPDATE alert SET deleted_at = #{now}, updated_at = #{now} WHERE alert_id = #{alertId}")
    void softDelete(@Param("alertId") UUID alertId, @Param("now") OffsetDateTime now);

    @Update("""
            UPDATE alert SET status = #{status}, updated_at = #{now},
                   expires_at = CASE WHEN #{setExpiresAt} THEN #{expiresAt}::timestamptz ELSE expires_at END
             WHERE alert_id = #{alertId}
            """)
    void changeStatus(@Param("alertId") UUID alertId, @Param("status") String status,
                      @Param("expiresAt") OffsetDateTime expiresAt, @Param("setExpiresAt") boolean setExpiresAt,
                      @Param("now") OffsetDateTime now);
```

`src/main/java/com/stockproject/portfolio/alert/store/WatchlistMapper.java`:

```java
package com.stockproject.portfolio.alert.store;

import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.UUID;

/**
 * 알림 대상 종목 (데이터 요구사항 §7.1). 삭제되지 않은 ACTIVE 알림이 하나 이상 걸린 종목이고,
 * 장중 알림이 있으면 intraday다. 사용자 정보를 담지 않는다.
 */
@Mapper
public interface WatchlistMapper {

    @Delete("DELETE FROM alert_watchlist WHERE instrument_id = #{instrumentId}")
    void delete(@Param("instrumentId") UUID instrumentId);

    @Insert("""
            INSERT INTO alert_watchlist (instrument_id, market, intraday)
            SELECT a.instrument_id, i.market, bool_or(a.cadence = 'INTRADAY')
              FROM alert a JOIN instrument i USING (instrument_id)
             WHERE a.instrument_id = #{instrumentId} AND a.status = 'ACTIVE' AND a.deleted_at IS NULL
             GROUP BY a.instrument_id, i.market
            """)
    void insertIfWatched(@Param("instrumentId") UUID instrumentId);
}
```

`alert/store/AlertStore.java`를 다음으로 바꾼다.

```java
package com.stockproject.portfolio.alert.store;

import com.stockproject.portfolio.alert.catalog.AlertStatus;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.spec.AlertDraft;
import com.stockproject.portfolio.auth.UserScope;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

/** 알림 저장소. 남의 알림과 없는 알림을 구분하지 않는다 — 둘 다 빈 값이다(§11.4). */
@Repository
public class AlertStore {

    /** trigger_spec의 포맷 버전 (§5.5). 서버가 정하고 요청에서 받지 않는다. */
    public static final int SPEC_VERSION = 1;

    private final AlertMapper mapper;
    private final WatchlistMapper watchlist;

    public AlertStore(AlertMapper mapper, WatchlistMapper watchlist) {
        this.mapper = mapper;
        this.watchlist = watchlist;
    }

    public Optional<AlertRow> findOwned(UserScope scope, UUID alertId) {
        return Optional.ofNullable(mapper.findOwned(scope, alertId));
    }

    /** 같은 종목 · 같은 평가 시점 · 같은 조건 해시의 활성 알림 (§6.7). */
    public Optional<UUID> duplicateOf(UserScope scope, UUID instrumentId, Cadence cadence, String specHash,
                                      UUID excludeAlertId) {
        return Optional.ofNullable(mapper.duplicateOf(scope, instrumentId, cadence.name(), specHash, excludeAlertId));
    }

    public void insert(UserScope scope, UUID alertId, AlertDraft d, String triggerSpecJson, String specHash,
                       OffsetDateTime now) {
        mapper.insertAlert(scope, alertId, d.instrumentId(), d.name().strip(), d.cadence().name(),
                d.notifyMode().name(), d.cooldownMin(), d.expiresAt(), d.trigger().typeName(), triggerSpecJson,
                SPEC_VERSION, now);
        mapper.insertState(alertId, specHash);
    }

    public void update(UUID alertId, AlertDraft d, String triggerSpecJson, String specHash, OffsetDateTime now) {
        mapper.updateAlert(alertId, d.name().strip(), d.cadence().name(), d.notifyMode().name(), d.cooldownMin(),
                d.expiresAt(), triggerSpecJson, SPEC_VERSION, now);
        mapper.resetState(alertId, specHash);
    }

    public void resetState(UUID alertId, String specHash) { mapper.resetState(alertId, specHash); }

    public void bumpVersion(UUID alertId) { mapper.bumpVersion(alertId); }

    public void softDelete(UUID alertId, OffsetDateTime now) { mapper.softDelete(alertId, now); }

    public void changeStatus(UUID alertId, AlertStatus status, OffsetDateTime expiresAt, boolean setExpiresAt,
                             OffsetDateTime now) {
        mapper.changeStatus(alertId, status.name(), expiresAt, setExpiresAt, now);
    }

    /** 그 종목의 대상 종목 행을 다시 계산한다. 알림을 바꾸는 트랜잭션 안에서 부른다. */
    public void refreshWatchlist(UUID instrumentId) {
        watchlist.delete(instrumentId);
        watchlist.insertIfWatched(instrumentId);
    }
}
```

- [ ] **Step 5: 명령 서비스와 컨트롤러를 쓴다**

`alert/service/AlertCommandService.java`:

```java
package com.stockproject.portfolio.alert.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.catalog.AlertStatus;
import com.stockproject.portfolio.alert.catalog.Cadence;
import com.stockproject.portfolio.alert.compile.Compiler;
import com.stockproject.portfolio.alert.compile.SpecHash;
import com.stockproject.portfolio.alert.data.HoldingReader;
import com.stockproject.portfolio.alert.data.InstrumentRow;
import com.stockproject.portfolio.alert.data.MarketDataRepository;
import com.stockproject.portfolio.alert.spec.AlertDraft;
import com.stockproject.portfolio.alert.spec.TriggerSpec;
import com.stockproject.portfolio.alert.store.AlertRow;
import com.stockproject.portfolio.alert.store.AlertStore;
import com.stockproject.portfolio.alert.validation.AlertRequestParser;
import com.stockproject.portfolio.alert.validation.AlertValidator;
import com.stockproject.portfolio.alert.validation.ExistingAlert;
import com.stockproject.portfolio.alert.validation.FieldError;
import com.stockproject.portfolio.alert.validation.InstrumentFacts;
import com.stockproject.portfolio.alert.validation.InvalidAlertException;
import com.stockproject.portfolio.alert.validation.ParseResult;
import com.stockproject.portfolio.alert.validation.TriggerSpecWriter;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.validation.RequestRejected;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.List;
import java.util.UUID;

/**
 * 알림을 바꾸는 요청 (스펙 §6.3 · §6.5 · §6.8). 사용자 변경은 같은 트랜잭션에서 version을 올린다 —
 * 평가기가 읽은 뒤 사용자가 바꾼 알림에 옛 결과가 반영되지 않게 하기 위해서다(§14.4).
 */
@Service
public class AlertCommandService {

    private final AlertStore alerts;
    private final MarketDataRepository market;
    private final HoldingReader holdings;
    private final ObjectMapper json;
    private final Clock clock;

    public AlertCommandService(AlertStore alerts, MarketDataRepository market, HoldingReader holdings,
                               ObjectMapper json, Clock clock) {
        this.alerts = alerts;
        this.market = market;
        this.holdings = holdings;
        this.json = json;
        this.clock = clock;
    }

    @Transactional
    public UUID create(UserScope scope, JsonNode body) {
        AlertDraft draft = validDraft(scope, body, null);
        UUID id = UUID.randomUUID();
        alerts.insert(scope, id, draft, TriggerSpecWriter.write(draft.trigger()).toString(), hash(draft), now());
        alerts.refreshWatchlist(draft.instrumentId());
        return id;
    }

    @Transactional
    public UUID update(UserScope scope, UUID alertId, JsonNode body) {
        AlertRow row = owned(scope, alertId);
        AlertDraft draft = validDraft(scope, body, new ExistingAlert(row.instrumentId(), row.triggerType()));
        alerts.update(alertId, draft, TriggerSpecWriter.write(draft.trigger()).toString(), hash(draft), now());
        alerts.refreshWatchlist(row.instrumentId());
        return alertId;
    }

    @Transactional
    public void delete(UserScope scope, UUID alertId) {
        AlertRow row = owned(scope, alertId);
        alerts.softDelete(alertId, now());
        alerts.bumpVersion(alertId);
        alerts.refreshWatchlist(row.instrumentId());
    }

    @Transactional
    public void pause(UserScope scope, UUID alertId) {
        AlertRow row = owned(scope, alertId);
        if (!AlertStatus.ACTIVE.name().equals(row.status())) throw invalidTransition();
        alerts.changeStatus(alertId, AlertStatus.PAUSED, null, false, now());
        alerts.bumpVersion(alertId);
        alerts.refreshWatchlist(row.instrumentId());
    }

    /** 다시 켜기. 만료된 알림은 새 유효기간(null이면 무기한)을 함께 받는다(§6.5). */
    @Transactional
    public void resume(UserScope scope, UUID alertId, JsonNode body) {
        AlertRow row = owned(scope, alertId);
        AlertStatus status = AlertStatus.of(row.status());
        if (status == AlertStatus.ACTIVE) throw invalidTransition();

        boolean expired = status == AlertStatus.EXPIRED;
        OffsetDateTime expiresAt = expired ? newExpiry(body) : null;
        alerts.changeStatus(alertId, AlertStatus.ACTIVE, expiresAt, expired, now());
        alerts.resetState(alertId, hash(row));
        alerts.refreshWatchlist(row.instrumentId());
    }

    // ---- 도우미 ----------------------------------------------------------------

    private AlertDraft validDraft(UserScope scope, JsonNode body, ExistingAlert existing) {
        ParseResult parsed = AlertRequestParser.parse(body);
        if (!parsed.ok()) throw new InvalidAlertException(parsed.errors());
        AlertDraft draft = parsed.draft();
        InstrumentRow instrument = market.instrument(draft.instrumentId()).orElse(null);
        InstrumentFacts facts = instrument == null ? null : new InstrumentFacts(instrument.marketEnum(),
                instrument.assetClass(), instrument.delistedOn() != null,
                existing == null && holdings.held(scope, instrument));
        AlertValidator.requireValid(draft, facts, existing, now());
        return draft;
    }

    private OffsetDateTime newExpiry(JsonNode body) {
        if (body == null || !body.has("expires_at")) {
            throw new InvalidAlertException(List.of(new FieldError("expires_at", "REQUIRED", "유효기간을 골라 주세요")));
        }
        JsonNode value = body.get("expires_at");
        if (value.isNull()) return null;
        OffsetDateTime at;
        try {
            at = OffsetDateTime.parse(value.asText());
        } catch (DateTimeParseException e) {
            throw new InvalidAlertException(List.of(new FieldError("expires_at", "INVALID_TYPE", "시각 형식이 아니에요")));
        }
        if (!at.isAfter(now())) {
            throw new InvalidAlertException(List.of(new FieldError("expires_at", "PAST", "지난 시각은 고를 수 없어요")));
        }
        return at;
    }

    private AlertRow owned(UserScope scope, UUID alertId) {
        return alerts.findOwned(scope, alertId)
                .orElseThrow(() -> new RequestRejected("ALERT_NOT_FOUND", "알림을 찾을 수 없어요", true));
    }

    private static RequestRejected invalidTransition() {
        return new RequestRejected("INVALID_STATUS_TRANSITION", "지금 상태에서는 할 수 없어요");
    }

    private static String hash(AlertDraft d) {
        return SpecHash.of(Compiler.compile(d.trigger(), d.cadence()), d.cadence());
    }

    /** 저장된 알림의 지금 코드 기준 해시. 템플릿이 바뀌었으면 여기서 새 해시가 된다(§6.6). */
    private String hash(AlertRow row) {
        try {
            Cadence cadence = Cadence.valueOf(row.cadence());
            TriggerSpec trigger = AlertRequestParser.stored(row.triggerType(), json.readTree(row.triggerSpec()));
            return SpecHash.of(Compiler.compile(trigger, cadence), cadence);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("저장된 trigger_spec이 JSON이 아니다: " + row.alertId(), e);
        }
    }

    private OffsetDateTime now() { return OffsetDateTime.now(clock); }
}
```

수정에서 `held`를 묻지 않는 것은 보유 검사가 생성에만 있기 때문이다(§14.1). 검증기는 `existing`이 있으면 보유를 보지 않지만, 쓸데없는 조회를 하지 않으려고 여기서도 건너뛴다.

`alert/api/dto/AlertIdResponse.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.util.UUID;

/** 만들기·수정의 응답. 저장 뒤 화면은 알림 상세를 다시 받는다(§12.5.5). */
public record AlertIdResponse(UUID alertId) { }
```

`alert/api/AlertController.java`를 다음으로 바꾼다.

```java
package com.stockproject.portfolio.alert.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.stockproject.portfolio.alert.api.dto.AlertIdResponse;
import com.stockproject.portfolio.alert.api.dto.PreviewResponse;
import com.stockproject.portfolio.alert.service.AlertCommandService;
import com.stockproject.portfolio.alert.service.AlertPreviewService;
import com.stockproject.portfolio.auth.UserScope;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

/**
 * 알림 규칙 (스펙 §11.1). 본문을 JsonNode로 받는 것은 형이 틀린 값도 경로가 붙은 오류로
 * 돌려주기 위해서다 — 레코드로 바로 받으면 Jackson이 첫 오류에서 멈춘다.
 */
@RestController
@RequestMapping("/alerts")
public class AlertController {

    private final AlertPreviewService preview;
    private final AlertCommandService commands;

    public AlertController(AlertPreviewService preview, AlertCommandService commands) {
        this.preview = preview;
        this.commands = commands;
    }

    @PostMapping("/preview")
    public PreviewResponse preview(UserScope scope, @RequestBody JsonNode body) {
        return preview.preview(scope, body);
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public AlertIdResponse create(UserScope scope, @RequestBody JsonNode body) {
        return new AlertIdResponse(commands.create(scope, body));
    }

    @PutMapping("/{alertId}")
    public AlertIdResponse update(UserScope scope, @PathVariable UUID alertId, @RequestBody JsonNode body) {
        return new AlertIdResponse(commands.update(scope, alertId, body));
    }

    @DeleteMapping("/{alertId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(UserScope scope, @PathVariable UUID alertId) {
        commands.delete(scope, alertId);
    }

    @PostMapping("/{alertId}/pause")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void pause(UserScope scope, @PathVariable UUID alertId) {
        commands.pause(scope, alertId);
    }

    @PostMapping("/{alertId}/resume")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void resume(UserScope scope, @PathVariable UUID alertId,
                       @RequestBody(required = false) JsonNode body) {
        commands.resume(scope, alertId, body);
    }
}
```

- [ ] **Step 6: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.*'`
Expected: PASS

- [ ] **Step 7: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert \
        src/test/java/com/stockproject/portfolio/alert/validation/TriggerSpecWriterTest.java \
        src/test/java/com/stockproject/portfolio/alert/api/AlertCommandApiTest.java
git commit -m "feat: 알림 만들기·수정·삭제·끄기·다시 켜기를 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: `GET /alerts` · `GET /alerts/{id}`

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/store/AlertQueryMapper.java` · `AlertListRow.java` · `UnreadEventRow.java` · `RecentEventRow.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/service/AlertQueryService.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/api/dto/` 아래 `InstrumentDto.java` · `ShortSummaryDto.java` · `AlertCardDto.java` · `UnreadDto.java` · `AlertListData.java` · `RecentEventDto.java` · `AlertDetailDto.java`
- Modify: `src/main/java/com/stockproject/portfolio/alert/api/AlertController.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/api/AlertQueryApiTest.java`

**Interfaces:**
- Consumes: Task 11의 `AlertRequestParser.stored` · `AlertStore.findOwned`, Task 8 `SentenceWriter.summary`, 기존 `Envelope`.
- Produces:
  - `AlertQueryService` — `Envelope<AlertListData> list(UserScope)` · `AlertDetailDto detail(UserScope, UUID)`.
  - 목록 봉투: `as_of`는 이 사용자 알림의 `evaluated_as_of` 최댓값(없으면 `null`), `empty_reason`은 알림이 없으면 `NO_ALERTS`, `notices`는 빈 목록(`MARKET_DATA_DELAYED`는 ②).
  - `record AlertListData(List<AlertCardDto> rows, List<UnreadDto> unread, int unreadMore)`
  - `record AlertCardDto(UUID alertId, String name, InstrumentDto instrument, String cadence, String notifyMode, String status, ShortSummaryDto summary, String lastResult, String unknownReason, OffsetDateTime evaluatedAsOf, OffsetDateTime lastFiredAt)`
  - `record UnreadDto(UUID eventId, String title, String cadence, String market, OffsetDateTime asOf, OffsetDateTime firedAt, boolean alertDeleted)`
  - `record AlertDetailDto(UUID alertId, String name, InstrumentDto instrument, String cadence, String notifyMode, Integer cooldownMin, OffsetDateTime expiresAt, String status, String triggerType, JsonNode triggerSpec, SummaryDto summary, String lastResult, String unknownReason, OffsetDateTime evaluatedAsOf, List<RecentEventDto> recentEvents)`
  - `record RecentEventDto(UUID eventId, String title, OffsetDateTime asOf, boolean read)` · `record InstrumentDto(UUID id, String label, String market)` · `record ShortSummaryDto(@JsonProperty("short") String shortText)`

정렬(§12.2, 계획 A.10): 조건 충족 중(`ACTIVE` · `TRUE`) → 감시 중(`ACTIVE` · `FALSE` 또는 평가 전) → 확인 불가(`ACTIVE` · `UNKNOWN`) → 꺼짐 → 울린 뒤 종료 → 만료, 같은 상태 안에서 최근 울린 순(울린 적 없으면 뒤) → 만든 순(최근 먼저) → `alert_id`. 미확인 발화는 삭제된 알림의 것도 포함해 데이터 시점 내림차순 3건, 넘친 수는 `unread_more`다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/api/AlertQueryApiTest.java`:

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

import java.util.UUID;

import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.SAMSUNG;
import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.priceReach;
import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.rsi;
import static org.assertj.core.api.Assertions.assertThat;

/** 알림 목록과 상세 (스펙 §11.2 · §11.3 · §12.2 · §12.4). */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(FixedClockConfig.class)
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class AlertQueryApiTest {

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;
    AlertApiClient api;

    @BeforeEach
    void setUp() { api = new AlertApiClient(mockMvc, json); }

    @Test
    void 알림이_없으면_빈_상태_사유다() throws Exception {
        JsonNode body = api.get("/alerts", "test_empty").body();

        assertThat(body.get("as_of").isNull()).isTrue();
        assertThat(body.get("data").get("rows")).isEmpty();
        assertThat(body.get("data").get("unread")).isEmpty();
        assertThat(body.get("data").get("unread_more").asInt()).isZero();
        assertThat(body.get("empty_reason").asText()).isEqualTo("NO_ALERTS");
        assertThat(body.get("notices")).isEmpty();
    }

    @Test
    void 카드는_상태_순_그다음_최근_울린_순이다() throws Exception {
        UUID watchingOld = create(priceReach(SAMSUNG, "INTRADAY", 70000));
        UUID paused = create(priceReach(SAMSUNG, "INTRADAY", 71000));
        UUID unknown = create(priceReach(SAMSUNG, "INTRADAY", 72000));
        UUID satisfied = create(priceReach(SAMSUNG, "INTRADAY", 73000));
        UUID ended = create(priceReach(SAMSUNG, "INTRADAY", 74000));
        UUID expired = create(priceReach(SAMSUNG, "INTRADAY", 75000));
        UUID watchingFired = create(priceReach(SAMSUNG, "INTRADAY", 76000));
        UUID watchingNew = create(priceReach(SAMSUNG, "INTRADAY", 77000));

        state(satisfied, "TRUE", null);
        state(unknown, "UNKNOWN", "NO_TRADE");
        jdbc.sql("UPDATE alert SET status = 'PAUSED' WHERE alert_id = :id").param("id", paused).update();
        jdbc.sql("UPDATE alert SET status = 'ENDED' WHERE alert_id = :id").param("id", ended).update();
        jdbc.sql("UPDATE alert SET status = 'EXPIRED' WHERE alert_id = :id").param("id", expired).update();
        jdbc.sql("UPDATE alert SET created_at = created_at - interval '1 day' WHERE alert_id = :id")
                .param("id", watchingOld).update();
        event(watchingFired, "2026-09-28T10:15:00+09", null);

        JsonNode rows = api.get("/alerts", "yhr").body().get("data").get("rows");

        assertThat(rows).extracting(r -> UUID.fromString(r.get("alert_id").asText())).containsExactly(
                satisfied, watchingFired, watchingNew, watchingOld, unknown, paused, ended, expired);
        JsonNode first = rows.get(0);
        assertThat(first.get("instrument").get("label").asText()).isEqualTo("삼성전자");
        assertThat(first.get("instrument").get("market").asText()).isEqualTo("KR");
        assertThat(first.get("summary").get("short").asText()).isEqualTo("장중 · 현재가 ≥ 73,000원");
        assertThat(first.get("summary").has("sentence")).isFalse();
        assertThat(rows.get(1).get("last_fired_at").asText()).startsWith("2026-09-28T10:15:");
        assertThat(rows.get(4).get("unknown_reason").asText()).isEqualTo("NO_TRADE");
    }

    @Test
    void 봉투의_기준_시점은_가장_최근_평가_시점이다() throws Exception {
        UUID a = create(priceReach(SAMSUNG, "INTRADAY", 70000));
        UUID b = create(priceReach(SAMSUNG, "INTRADAY", 71000));
        jdbc.sql("UPDATE alert_state SET evaluated_as_of = '2026-09-28T10:10:00+09' WHERE alert_id = :id")
                .param("id", a).update();
        jdbc.sql("UPDATE alert_state SET evaluated_as_of = '2026-09-28T10:15:00+09' WHERE alert_id = :id")
                .param("id", b).update();

        assertThat(api.get("/alerts", "yhr").body().get("as_of").asText()).isEqualTo("2026-09-28T10:15:00+09:00");
    }

    @Test
    void 새로_울린_알림은_세_건까지이고_삭제된_알림의_것도_보인다() throws Exception {
        UUID kept = create(priceReach(SAMSUNG, "INTRADAY", 70000));
        UUID removed = create(priceReach(SAMSUNG, "CLOSE", 70000));
        event(kept, "2026-09-24T15:30:00+09", null);
        event(kept, "2026-09-25T15:30:00+09", null);
        event(removed, "2026-09-26T15:30:00+09", null);
        event(kept, "2026-09-27T15:30:00+09", null);
        event(kept, "2026-09-28T10:15:00+09", null);
        event(kept, "2026-09-28T10:00:00+09", "2026-09-28T10:05:00+09");
        api.delete("/alerts/" + removed, "yhr");

        JsonNode data = api.get("/alerts", "yhr").body().get("data");

        assertThat(data.get("unread")).hasSize(3);
        assertThat(data.get("unread").get(0).get("as_of").asText()).isEqualTo("2026-09-28T10:15:00+09:00");
        assertThat(data.get("unread").get(2).get("as_of").asText()).isEqualTo("2026-09-26T15:30:00+09:00");
        assertThat(data.get("unread").get(2).get("alert_deleted").asBoolean()).isTrue();
        assertThat(data.get("unread").get(2).get("cadence").asText()).isEqualTo("CLOSE");
        assertThat(data.get("unread").get(0).get("market").asText()).isEqualTo("KR");
        assertThat(data.get("unread_more").asInt()).isEqualTo(2);
    }

    /** Review Focus 3 — 남의 알림은 목록에 없고 상세는 404다. */
    @Test
    void 남의_알림은_보이지_않는다() throws Exception {
        UUID others = UUID.fromString(api.post("/alerts", "jdh", priceReach(SAMSUNG, "INTRADAY", 70000))
                .body().get("alert_id").asText());
        event(others, "2026-09-28T10:15:00+09", null);

        JsonNode data = api.get("/alerts", "yhr").body().get("data");
        assertThat(data.get("rows")).isEmpty();
        assertThat(data.get("unread")).isEmpty();

        Response detail = api.get("/alerts/" + others, "yhr");
        assertThat(detail.status()).isEqualTo(404);
        assertThat(detail.body().get("error").get("code").asText()).isEqualTo("ALERT_NOT_FOUND");
    }

    @Test
    void 상세는_저장된_조건과_두_문체와_최근_다섯_건이다() throws Exception {
        UUID id = create(rsi(SAMSUNG, 14));
        for (int day = 21; day <= 26; day++) event(id, "2026-09-%dT15:30:00+09".formatted(day), null);
        jdbc.sql("UPDATE alert_event SET read_at = now() WHERE alert_id = :id AND as_of < '2026-09-25'")
                .param("id", id).update();

        JsonNode body = api.get("/alerts/" + id, "yhr").body();

        assertThat(body.get("trigger_type").asText()).isEqualTo("COMPOSABLE");
        assertThat(body.get("trigger_spec").get("conditions").get(0).get("left").get("indicator").asText())
                .isEqualTo("rsi");
        assertThat(body.get("trigger_spec").get("conditions").get(0).get("left").get("transform").has("lag")).isFalse();
        assertThat(body.get("summary").get("short").asText()).isEqualTo("종가 · RSI(14) ≥ 1");
        assertThat(body.get("summary").get("sentence").asText()).isEqualTo("종가 기준으로 RSI(14)가 1 이상이면 알려요");
        assertThat(body.get("status").asText()).isEqualTo("ACTIVE");
        assertThat(body.get("last_result").isNull()).isTrue();
        JsonNode recent = body.get("recent_events");
        assertThat(recent).hasSize(5);
        assertThat(recent.get(0).get("as_of").asText()).isEqualTo("2026-09-26T15:30:00+09:00");
        assertThat(recent.get(0).get("read").asBoolean()).isFalse();
        assertThat(recent.get(4).get("read").asBoolean()).isTrue();
    }

    @Test
    void 삭제된_알림의_상세는_없다() throws Exception {
        UUID id = create(priceReach(SAMSUNG, "INTRADAY", 70000));
        api.delete("/alerts/" + id, "yhr");

        assertThat(api.get("/alerts/" + id, "yhr").status()).isEqualTo(404);
    }

    // ---- 도우미 ----------------------------------------------------------------

    private UUID create(String body) throws Exception {
        Response r = api.post("/alerts", "yhr", body);
        assertThat(r.status()).isEqualTo(201);
        return UUID.fromString(r.body().get("alert_id").asText());
    }

    private void state(UUID id, String result, String reason) {
        jdbc.sql("UPDATE alert_state SET last_result = :r, unknown_reason = :reason WHERE alert_id = :id")
                .param("r", result).param("reason", reason).param("id", id).update();
    }

    private void event(UUID alertId, String asOf, String readAt) {
        jdbc.sql("""
                INSERT INTO alert_event (event_id, alert_id, as_of, fired_at, title, body, lines, observed, read_at)
                VALUES (gen_random_uuid(), :alert, :asOf::timestamptz, :asOf::timestamptz + interval '40 second',
                        '삼성전자 · 가격 도달', '본문', '[]', '{}', :readAt::timestamptz)
                """).param("alert", alertId).param("asOf", asOf).param("readAt", readAt).update();
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.api.AlertQueryApiTest'`
Expected: FAIL — `GET /alerts`가 없어 405 또는 404

- [ ] **Step 3: 조회 쿼리를 쓴다**

`alert/store/AlertListRow.java`:

```java
package com.stockproject.portfolio.alert.store;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 목록 카드 한 행 — 알림 · 상태 · 종목 표시명 · 최근 울림. */
public record AlertListRow(UUID alertId, UUID instrumentId, String name, String cadence, String notifyMode,
                           String status, String triggerType, String triggerSpec, String lastResult,
                           String unknownReason, OffsetDateTime evaluatedAsOf, String instrumentLabel,
                           String instrumentMarket, OffsetDateTime lastFiredAt) { }
```

`alert/store/UnreadEventRow.java`:

```java
package com.stockproject.portfolio.alert.store;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 새로 울린 알림 블록의 한 줄 (§11.2). 기준 표기는 cadence와 market으로 화면이 정한다. */
public record UnreadEventRow(UUID eventId, String title, String cadence, String market, OffsetDateTime asOf,
                             OffsetDateTime firedAt, boolean alertDeleted) { }
```

`alert/store/RecentEventRow.java`:

```java
package com.stockproject.portfolio.alert.store;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 알림 상세의 최근 울린 알림 한 줄. */
public record RecentEventRow(UUID eventId, String title, OffsetDateTime asOf, boolean read) { }
```

`alert/store/AlertQueryMapper.java`:

```java
package com.stockproject.portfolio.alert.store;

import com.stockproject.portfolio.auth.UserScope;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** 알림 탭의 읽기. 정렬은 서버가 정한다(§12.2, 계획 A.10). */
@Mapper
public interface AlertQueryMapper {

    @Select("""
            SELECT a.alert_id, a.instrument_id, a.name, a.cadence, a.notify_mode, a.status, a.trigger_type,
                   a.trigger_spec::text AS trigger_spec, s.last_result, s.unknown_reason, s.evaluated_as_of,
                   i.name AS instrument_label, i.market AS instrument_market,
                   (SELECT max(e.fired_at) FROM alert_event e WHERE e.alert_id = a.alert_id) AS last_fired_at
              FROM alert a
              JOIN alert_state s USING (alert_id)
              LEFT JOIN instrument i USING (instrument_id)
             WHERE a.user_id = #{scope.userId} AND a.deleted_at IS NULL
             ORDER BY CASE WHEN a.status = 'ACTIVE' AND s.last_result = 'TRUE' THEN 0
                           WHEN a.status = 'ACTIVE' AND s.last_result = 'UNKNOWN' THEN 2
                           WHEN a.status = 'ACTIVE' THEN 1
                           WHEN a.status = 'PAUSED' THEN 3
                           WHEN a.status = 'ENDED' THEN 4
                           ELSE 5 END,
                      last_fired_at DESC NULLS LAST, a.created_at DESC, a.alert_id
            """)
    List<AlertListRow> list(@Param("scope") UserScope scope);

    @Select("""
            SELECT max(s.evaluated_as_of) FROM alert a JOIN alert_state s USING (alert_id)
             WHERE a.user_id = #{scope.userId} AND a.deleted_at IS NULL
            """)
    OffsetDateTime latestEvaluatedAsOf(@Param("scope") UserScope scope);

    /** 미확인 발화. 삭제된 알림의 발화도 남아 보인다(§6.8). */
    @Select("""
            SELECT e.event_id, e.title, a.cadence, i.market, e.as_of, e.fired_at,
                   a.deleted_at IS NOT NULL AS alert_deleted
              FROM alert_event e
              JOIN alert a USING (alert_id)
              LEFT JOIN instrument i USING (instrument_id)
             WHERE a.user_id = #{scope.userId} AND e.read_at IS NULL
             ORDER BY e.as_of DESC, e.event_id
             LIMIT #{limit}
            """)
    List<UnreadEventRow> unread(@Param("scope") UserScope scope, @Param("limit") int limit);

    @Select("""
            SELECT count(*) FROM alert_event e JOIN alert a USING (alert_id)
             WHERE a.user_id = #{scope.userId} AND e.read_at IS NULL
            """)
    int unreadCount(@Param("scope") UserScope scope);

    @Select("""
            SELECT e.event_id, e.title, e.as_of, e.read_at IS NOT NULL AS read
              FROM alert_event e
             WHERE e.alert_id = #{alertId}
             ORDER BY e.as_of DESC, e.event_id
             LIMIT #{limit}
            """)
    List<RecentEventRow> recentEvents(@Param("alertId") UUID alertId, @Param("limit") int limit);

    /** 알림 상세의 종목 표시명과 시장. 종목 마스터에 없으면 null이다. */
    @Select("SELECT name AS label, market FROM instrument WHERE instrument_id = #{id}")
    InstrumentLabel instrument(@Param("id") UUID id);

    record InstrumentLabel(String label, String market) { }
}
```

- [ ] **Step 4: 응답 타입을 쓴다**

`alert/api/dto/InstrumentDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.util.UUID;

/** 알림이 걸린 종목. label은 종목 마스터의 이름이다(미국 종목은 영문명). */
public record InstrumentDto(UUID id, String label, String market) { }
```

`alert/api/dto/ShortSummaryDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/** 목록은 짧은 형만 싣는다(§11.2). */
public record ShortSummaryDto(@JsonProperty("short") String shortText) { }
```

`alert/api/dto/AlertCardDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 알림 카드 (§11.2 · §12.2). */
public record AlertCardDto(UUID alertId, String name, InstrumentDto instrument, String cadence, String notifyMode,
                           String status, ShortSummaryDto summary, String lastResult, String unknownReason,
                           OffsetDateTime evaluatedAsOf, OffsetDateTime lastFiredAt) { }
```

`alert/api/dto/UnreadDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 새로 울린 알림 블록의 한 줄 (§11.2). */
public record UnreadDto(UUID eventId, String title, String cadence, String market, OffsetDateTime asOf,
                        OffsetDateTime firedAt, boolean alertDeleted) { }
```

`alert/api/dto/AlertListData.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.util.List;

/** GET /alerts 봉투의 data (§11.2). */
public record AlertListData(List<AlertCardDto> rows, List<UnreadDto> unread, int unreadMore) { }
```

`alert/api/dto/RecentEventDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 알림 상세의 최근 울린 알림 (§11.3). */
public record RecentEventDto(UUID eventId, String title, OffsetDateTime asOf, boolean read) { }
```

`alert/api/dto/AlertDetailDto.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import com.fasterxml.jackson.databind.JsonNode;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 알림 상세 (§11.3). trigger_spec을 싣는 것은 수정 화면이 프리셋 입력·조건 만들기를
 * 값이 채워진 채 열기 때문이다.
 */
public record AlertDetailDto(UUID alertId, String name, InstrumentDto instrument, String cadence, String notifyMode,
                             Integer cooldownMin, OffsetDateTime expiresAt, String status, String triggerType,
                             JsonNode triggerSpec, SummaryDto summary, String lastResult, String unknownReason,
                             OffsetDateTime evaluatedAsOf, List<RecentEventDto> recentEvents) { }
```

- [ ] **Step 5: 조회 서비스를 쓴다**

`alert/service/AlertQueryService.java`:

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
import com.stockproject.portfolio.alert.compile.Compiler;
import com.stockproject.portfolio.alert.sentence.SentenceWriter;
import com.stockproject.portfolio.alert.sentence.Summary;
import com.stockproject.portfolio.alert.store.AlertListRow;
import com.stockproject.portfolio.alert.store.AlertQueryMapper;
import com.stockproject.portfolio.alert.store.AlertRow;
import com.stockproject.portfolio.alert.store.AlertStore;
import com.stockproject.portfolio.alert.validation.AlertRequestParser;
import com.stockproject.portfolio.api.dto.Envelope;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.domain.Market;
import com.stockproject.portfolio.validation.RequestRejected;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

/** 알림 탭과 알림 상세의 읽기 (§11.2 · §11.3). 조건 문장은 읽을 때마다 지금 코드로 만든다. */
@Service
public class AlertQueryService {

    static final int UNREAD_LIMIT = 3;
    static final int RECENT_LIMIT = 5;

    private final AlertQueryMapper queries;
    private final AlertStore alerts;
    private final ObjectMapper json;

    public AlertQueryService(AlertQueryMapper queries, AlertStore alerts, ObjectMapper json) {
        this.queries = queries;
        this.alerts = alerts;
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
                new AlertListData(rows, unread, more), rows.isEmpty() ? "NO_ALERTS" : null, List.of());
    }

    public AlertDetailDto detail(UserScope scope, UUID alertId) {
        AlertRow a = alerts.findOwned(scope, alertId)
                .orElseThrow(() -> new RequestRejected("ALERT_NOT_FOUND", "알림을 찾을 수 없어요", true));
        AlertQueryMapper.InstrumentLabel instrument = queries.instrument(a.instrumentId());
        String label = instrument == null ? null : instrument.label();
        String market = instrument == null ? null : instrument.market();
        Summary summary = summary(a.triggerType(), a.triggerSpec(), a.cadence(), market);
        List<RecentEventDto> recent = queries.recentEvents(alertId, RECENT_LIMIT).stream()
                .map(e -> new RecentEventDto(e.eventId(), e.title(), AlertTimes.kst(e.asOf()), e.read()))
                .toList();
        return new AlertDetailDto(a.alertId(), a.name(), new InstrumentDto(a.instrumentId(), label, market),
                a.cadence(), a.notifyMode(), a.cooldownMin(), AlertTimes.kst(a.expiresAt()), a.status(),
                a.triggerType(), read(a.triggerSpec()), new SummaryDto(summary.shortText(), summary.sentence()),
                a.lastResult(), a.unknownReason(), AlertTimes.kst(a.evaluatedAsOf()), recent);
    }

    private AlertCardDto card(AlertListRow r) {
        Summary summary = summary(r.triggerType(), r.triggerSpec(), r.cadence(), r.instrumentMarket());
        return new AlertCardDto(r.alertId(), r.name(),
                new InstrumentDto(r.instrumentId(), r.instrumentLabel(), r.instrumentMarket()), r.cadence(),
                r.notifyMode(), r.status(), new ShortSummaryDto(summary.shortText()), r.lastResult(),
                r.unknownReason(), AlertTimes.kst(r.evaluatedAsOf()), AlertTimes.kst(r.lastFiredAt()));
    }

    private Summary summary(String triggerType, String triggerSpec, String cadence, String market) {
        Cadence c = Cadence.valueOf(cadence);
        return SentenceWriter.summary(Compiler.compile(AlertRequestParser.stored(triggerType, read(triggerSpec)), c),
                c, market == null ? Market.KR : Market.valueOf(market));
    }

    private JsonNode read(String text) {
        try {
            return json.readTree(text);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("저장된 trigger_spec이 JSON이 아니다", e);
        }
    }
}
```

- [ ] **Step 6: 컨트롤러에 두 경로를 더한다**

`AlertController`에 `AlertQueryService queries`를 생성자로 받고 다음을 더한다(`import org.springframework.web.bind.annotation.GetMapping;` · `com.stockproject.portfolio.api.dto.Envelope;` · `dto.AlertListData` · `dto.AlertDetailDto` 추가).

```java
    @GetMapping
    public Envelope<AlertListData> list(UserScope scope) {
        return queries.list(scope);
    }

    @GetMapping("/{alertId}")
    public AlertDetailDto detail(UserScope scope, @PathVariable UUID alertId) {
        return queries.detail(scope, alertId);
    }
```

`/alerts/catalog`(Task 13)는 `/{alertId}`보다 구체적인 경로라 Spring이 먼저 고른다. `{alertId}`가 UUID로 바뀌지 않는 문자열이면 `400`이다.

- [ ] **Step 7: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.api.*'`
Expected: PASS

- [ ] **Step 8: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert \
        src/test/java/com/stockproject/portfolio/alert/api/AlertQueryApiTest.java
git commit -m "feat: 알림 목록과 상세 조회를 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: `GET /alerts/catalog` · `GET /instruments` · `POST/DELETE /devices`

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/alert/service/AlertCatalogService.java` · `InstrumentSearchService.java` · `DeviceService.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/store/InstrumentSearchMapper.java` · `InstrumentSearchRow.java` · `PushDeviceMapper.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/api/AlertCatalogController.java` · `InstrumentController.java` · `DeviceController.java`
- Create: `src/main/java/com/stockproject/portfolio/alert/api/dto/` 아래 `CatalogResponse.java` · `InstrumentSearchResponse.java` · `DeviceRequest.java` · `DeviceResponse.java`
- Test: `src/test/java/com/stockproject/portfolio/alert/api/AlertCatalogApiTest.java` · `InstrumentSearchApiTest.java` · `DeviceApiTest.java`

**Interfaces:**
- Consumes: Task 2 카탈로그, Task 10 `AlertApiClient` · `FixedClockConfig`.
- Produces:
  - `GET /alerts/catalog` → `CatalogResponse(indicators, presets, transforms, operators)`. 지표는 §11.3 발췌의 필드에 `category`와 `transform_ranges`(변형별 n 범위)를 더한다 — 바텀시트 묶음과 n 입력칸의 상한에 쓴다.
  - `GET /instruments?q=&held=` → `InstrumentSearchResponse(rows)`, 행은 `{id, label, symbol, market, held}`.
  - `POST /devices` `{expo_push_token, platform}` → `200 {device_id}`. `DELETE /devices/{id}` → `204`. 남의 기기와 없는 기기는 `404 DEVICE_NOT_FOUND`. 형식이 틀리면 `400 INVALID_DEVICE`.

종목 검색 규칙 (§11.1 · §12.5.1, 계획 A.10):

| 요청 | 결과 |
|---|---|
| `q`가 비었거나 공백뿐, `held=true` | 보유 종목 구역 — 최신 확정 스냅샷의 보유 종목, `name COLLATE "C"` 순 |
| `q`가 비었거나 공백뿐, 그 밖 | 빈 목록 |
| `q`가 있음 | 이름·종목코드 부분 일치(대소문자 무시). `%` · `_` · `\`는 글자 그대로. 정렬은 종목코드 완전 일치 → 이름이 검색어로 시작 → 그 밖, 각 단계 안에서 `name COLLATE "C"` → `instrument_id`. 최대 30건 |
| 항상 | 예수금(`CASH`)과 상장폐지 종목은 내리지 않는다. `held`는 최신 확정 스냅샷에 그 종목이 있는가 |

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`src/test/java/com/stockproject/portfolio/alert/api/AlertCatalogApiTest.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.AlertApiClient;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** 카탈로그 (스펙 §5 · §11.3). 폼이 고를 수 있는 것과 범위를 서버가 알려 준다. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AlertCatalogApiTest {

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    AlertApiClient api;

    @BeforeEach
    void setUp() { api = new AlertApiClient(mockMvc, json); }

    @Test
    void 지표는_범위와_허용_조합을_싣는다() throws Exception {
        JsonNode body = api.get("/alerts/catalog", "yhr").body();

        assertThat(body.get("indicators")).hasSize(14);
        JsonNode rsi = find(body.get("indicators"), "rsi");
        assertThat(rsi.get("label").asText()).isEqualTo("RSI");
        assertThat(rsi.get("category").asText()).isEqualTo("기술지표");
        assertThat(rsi.get("unit").asText()).isEqualTo("index");
        assertThat(rsi.get("params").get(0).get("default").asInt()).isEqualTo(14);
        assertThat(rsi.get("params").get(0).get("max").asInt()).isEqualTo(30);
        assertThat(rsi.get("intraday_left").asBoolean()).isFalse();
        assertThat(rsi.get("allowed_transforms")).extracting(JsonNode::asText).containsExactly("identity", "delta");
        assertThat(rsi.get("transform_ranges").get("delta").get("max").asInt()).isEqualTo(5);
        assertThat(rsi.get("allowed_operators")).hasSize(6);
        assertThat(rsi.get("scope").asText()).isEqualTo("market");
        assertThat(rsi.get("deprecated").asBoolean()).isFalse();
        assertThat(rsi.get("markets")).extracting(JsonNode::asText).containsExactly("KR", "US");

        JsonNode weight = find(body.get("indicators"), "weight_pct");
        assertThat(weight.get("scope").asText()).isEqualTo("user");
        assertThat(weight.get("allowed_operators")).hasSize(4);
        assertThat(find(body.get("indicators"), "foreign_net_buy").get("transform_ranges").get("window").get("max")
                .asInt()).isEqualTo(10);
    }

    @Test
    void 프리셋은_입력_칸_정의를_싣는다() throws Exception {
        JsonNode presets = api.get("/alerts/catalog", "yhr").body().get("presets");

        assertThat(presets).hasSize(9);
        JsonNode rsi = find(presets, "rsi_zone");
        assertThat(rsi.get("cadences")).extracting(JsonNode::asText).containsExactly("CLOSE");
        JsonNode level = rsi.get("param_schema").get(1);
        assertThat(level.get("key").asText()).isEqualTo("level");
        assertThat(level.get("kind").asText()).isEqualTo("decimal");
        assertThat(level.get("default").decimalValue()).isEqualByComparingTo("70");
        JsonNode price = find(presets, "price_reach").get("param_schema").get(1);
        assertThat(price.get("required").asBoolean()).isTrue();
        assertThat(price.get("default").isNull()).isTrue();
        assertThat(find(presets, "investor_turn").get("markets")).extracting(JsonNode::asText).containsExactly("KR");
        assertThat(find(presets, "pnl_reach").get("scope").asText()).isEqualTo("user");
    }

    @Test
    void 변형과_연산자의_화면_이름() throws Exception {
        JsonNode body = api.get("/alerts/catalog", "yhr").body();

        assertThat(body.get("transforms")).extracting(t -> t.get("key").asText())
                .containsExactly("identity", "window", "delta", "pct");
        assertThat(body.get("transforms").get(1).get("fns")).extracting(f -> f.get("label").asText())
                .containsExactly("최고", "최저", "평균", "합계");
        assertThat(body.get("operators").get(0).get("symbol").asText()).isEqualTo("≥");
        assertThat(body.get("operators").get(0).get("word").asText()).isEqualTo("이상");
    }

    @Test
    void 토큰이_없으면_401이다() throws Exception {
        mockMvc.perform(get("/alerts/catalog")).andExpect(status().isUnauthorized());
    }

    private static JsonNode find(JsonNode list, String key) {
        for (JsonNode n : list) if (n.get("key").asText().equals(key)) return n;
        throw new AssertionError(key + " 없음");
    }
}
```

`src/test/java/com/stockproject/portfolio/alert/api/InstrumentSearchApiTest.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.AlertApiClient;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.web.servlet.MockMvc;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

/** 종목 검색 (스펙 §11.1 · §12.5.1). */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Sql("classpath:db/sample/sample_portfolio.sql")
class InstrumentSearchApiTest {

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;
    AlertApiClient api;

    @BeforeEach
    void setUp() {
        api = new AlertApiClient(mockMvc, json);
        jdbc.sql("""
                INSERT INTO instrument (instrument_id, isin, symbol, name, asset_class, market, currency, sector,
                                        is_leveraged, delisted_on) VALUES
                 ('10000000-0000-0000-0000-000000000101', NULL, '006400', '삼성SDI', 'STOCK', 'KR', 'KRW', NULL, false, NULL),
                 ('10000000-0000-0000-0000-000000000102', NULL, '005935', '삼성전자우', 'STOCK', 'KR', 'KRW', NULL, false, NULL),
                 ('10000000-0000-0000-0000-000000000103', NULL, '010140', '삼성중공업', 'STOCK', 'KR', 'KRW', NULL, false, '2026-01-02'),
                 ('10000000-0000-0000-0000-000000000104', NULL, 'PCT1', '100%테스트', 'STOCK', 'KR', 'KRW', NULL, false, NULL),
                 ('10000000-0000-0000-0000-000000000105', NULL, 'UND1', 'A_B', 'STOCK', 'US', 'USD', NULL, false, NULL)
                """).update();
    }

    @Test
    void 이름이_검색어로_시작하는_종목을_가나다순으로() throws Exception {
        JsonNode rows = search("q=" + enc("삼성"));

        assertThat(rows).extracting(r -> r.get("label").asText()).containsExactly("삼성SDI", "삼성전자", "삼성전자우");
        assertThat(rows.get(1).get("held").asBoolean()).isTrue();
        assertThat(rows.get(0).get("held").asBoolean()).isFalse();
        assertThat(rows.get(1).get("symbol").asText()).isEqualTo("005930");
        assertThat(rows.get(1).get("market").asText()).isEqualTo("KR");
    }

    @Test
    void 종목코드_완전_일치가_먼저다() throws Exception {
        assertThat(search("q=005930")).extracting(r -> r.get("label").asText()).containsExactly("삼성전자");
        assertThat(search("q=0059")).extracting(r -> r.get("label").asText()).containsExactly("삼성전자", "삼성전자우");
        assertThat(search("q=aapl")).extracting(r -> r.get("symbol").asText()).containsExactly("AAPL");
    }

    /** Review Focus 4 — 와일드카드 문자는 글자 그대로다. */
    @Test
    void 퍼센트와_밑줄은_와일드카드가_아니다() throws Exception {
        assertThat(search("q=" + enc("%"))).extracting(r -> r.get("label").asText()).containsExactly("100%테스트");
        assertThat(search("q=" + enc("_"))).extracting(r -> r.get("label").asText()).containsExactly("A_B");
    }

    @Test
    void 빈_검색어와_긴_검색어() throws Exception {
        assertThat(search("q=" + enc("   "))).isEmpty();
        assertThat(search("q=")).isEmpty();
        assertThat(search("q=" + enc("가".repeat(41)))).isEmpty();
    }

    @Test
    void 예수금과_상장폐지_종목은_내리지_않는다() throws Exception {
        assertThat(search("q=" + enc("예수금"))).isEmpty();
        assertThat(search("q=" + enc("중공업"))).isEmpty();
    }

    @Test
    void 보유_종목_구역은_가나다순이다() throws Exception {
        JsonNode rows = search("held=true");

        assertThat(rows).extracting(r -> r.get("label").asText()).containsExactly(
                "NAVER", "SK하이닉스", "TIGER 미국나스닥100", "마이크로소프트", "삼성전자", "애플");
        assertThat(rows).allSatisfy(r -> assertThat(r.get("held").asBoolean()).isTrue());
        assertThat(api.get("/instruments?held=true", "test_empty").body().get("rows")).isEmpty();
    }

    private JsonNode search(String query) throws Exception {
        return api.get("/instruments?" + query, "yhr").body().get("rows");
    }

    private static String enc(String s) { return URLEncoder.encode(s, StandardCharsets.UTF_8); }
}
```

`src/test/java/com/stockproject/portfolio/alert/api/DeviceApiTest.java`:

```java
package com.stockproject.portfolio.alert.api;

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

import static org.assertj.core.api.Assertions.assertThat;

/** 푸시 수신 기기 (스펙 §9.2 · §14.5). 토큰 값은 문서·로그에 남기지 않는다 — 여기서는 가짜다. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(FixedClockConfig.class)
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class DeviceApiTest {

    private static final String TOKEN = "{\"expo_push_token\": \"ExponentPushToken[test-device-1]\", \"platform\": \"IOS\"}";

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    @Autowired JdbcClient jdbc;
    AlertApiClient api;

    @BeforeEach
    void setUp() { api = new AlertApiClient(mockMvc, json); }

    @Test
    void 같은_토큰을_다시_등록하면_같은_기기다() throws Exception {
        String first = api.post("/devices", "yhr", TOKEN).body().get("device_id").asText();
        String second = api.post("/devices", "yhr", TOKEN).body().get("device_id").asText();

        assertThat(second).isEqualTo(first);
        assertThat(count()).isEqualTo(1);
    }

    /** Review Focus 5 — 같은 기기에서 계정을 바꾸면 그 기기가 새 사용자로 옮겨진다. */
    @Test
    void 다른_사용자가_같은_토큰을_등록하면_옮긴다() throws Exception {
        String first = api.post("/devices", "yhr", TOKEN).body().get("device_id").asText();
        Response moved = api.post("/devices", "jdh", TOKEN);

        assertThat(moved.status()).isEqualTo(200);
        assertThat(moved.body().get("device_id").asText()).isEqualTo(first);
        assertThat(count()).isEqualTo(1);
        assertThat(jdbc.sql("SELECT user_id::text FROM push_device").query(String.class).single())
                .isEqualTo("40000000-0000-0000-0000-000000000002");
    }

    @Test
    void 남의_기기는_지울_수_없다() throws Exception {
        String id = api.post("/devices", "jdh", TOKEN).body().get("device_id").asText();

        Response others = api.delete("/devices/" + id, "yhr");
        assertThat(others.status()).isEqualTo(404);
        assertThat(others.body().get("error").get("code").asText()).isEqualTo("DEVICE_NOT_FOUND");

        assertThat(api.delete("/devices/" + id, "jdh").status()).isEqualTo(204);
        assertThat(api.delete("/devices/" + id, "jdh").status()).isEqualTo(404);
    }

    @Test
    void 형식이_틀리면_거부한다() throws Exception {
        Response platform = api.post("/devices", "yhr",
                "{\"expo_push_token\": \"ExponentPushToken[x]\", \"platform\": \"WEB\"}");
        assertThat(platform.status()).isEqualTo(400);
        assertThat(platform.body().get("error").get("code").asText()).isEqualTo("INVALID_DEVICE");

        assertThat(api.post("/devices", "yhr", "{\"expo_push_token\": \" \", \"platform\": \"IOS\"}").status())
                .isEqualTo(400);
        assertThat(count()).isZero();
    }

    private long count() {
        return jdbc.sql("SELECT count(*) FROM push_device").query(Long.class).single();
    }
}
```

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.api.AlertCatalogApiTest' --tests 'com.stockproject.portfolio.alert.api.InstrumentSearchApiTest' --tests 'com.stockproject.portfolio.alert.api.DeviceApiTest'`
Expected: FAIL — 경로가 없다

- [ ] **Step 3: 카탈로그 응답을 쓴다**

`alert/api/dto/CatalogResponse.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

/** GET /alerts/catalog (§11.3). 폼이 고를 수 있는 것과 범위. */
public record CatalogResponse(List<IndicatorDto> indicators, List<PresetDto> presets,
                              List<TransformDto> transforms, List<OperatorDto> operators) {

    public record IndicatorDto(String key, String label, String category, String unit, List<ParamDto> params,
                               boolean intradayLeft, List<String> markets, List<String> allowedTransforms,
                               Map<String, RangeDto> transformRanges, List<String> allowedOperators,
                               String scope, boolean deprecated) { }

    public record ParamDto(String key, @JsonProperty("default") int defaultValue, int min, int max) { }

    public record RangeDto(int min, int max) { }

    public record PresetDto(String key, String label, List<String> cadences, List<String> markets, String scope,
                            List<PresetParamDto> paramSchema) { }

    public record PresetParamDto(String key, String kind, Object min, Object max,
                                 @JsonProperty("default") Object defaultValue, List<String> choices,
                                 boolean required) { }

    public record TransformDto(String key, String label, List<FnDto> fns) { }

    public record FnDto(String key, String label) { }

    public record OperatorDto(String key, String symbol, String word) { }
}
```

`alert/service/AlertCatalogService.java`:

```java
package com.stockproject.portfolio.alert.service;

import com.stockproject.portfolio.alert.api.dto.CatalogResponse;
import com.stockproject.portfolio.alert.api.dto.CatalogResponse.FnDto;
import com.stockproject.portfolio.alert.api.dto.CatalogResponse.IndicatorDto;
import com.stockproject.portfolio.alert.api.dto.CatalogResponse.OperatorDto;
import com.stockproject.portfolio.alert.api.dto.CatalogResponse.ParamDto;
import com.stockproject.portfolio.alert.api.dto.CatalogResponse.PresetDto;
import com.stockproject.portfolio.alert.api.dto.CatalogResponse.PresetParamDto;
import com.stockproject.portfolio.alert.api.dto.CatalogResponse.RangeDto;
import com.stockproject.portfolio.alert.api.dto.CatalogResponse.TransformDto;
import com.stockproject.portfolio.alert.catalog.AlertCatalog;
import com.stockproject.portfolio.alert.catalog.Indicator;
import com.stockproject.portfolio.alert.catalog.OperatorKey;
import com.stockproject.portfolio.alert.catalog.Preset;
import com.stockproject.portfolio.alert.catalog.PresetParam;
import com.stockproject.portfolio.alert.catalog.TransformRule;
import com.stockproject.portfolio.alert.catalog.TransformType;
import com.stockproject.portfolio.alert.catalog.WindowFn;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 카탈로그 상수를 응답 모양으로 옮긴다. 상수라 한 번 만들어 둔다. v1에 폐기된 항목은 없다(§5.5). */
@Service
public class AlertCatalogService {

    private final CatalogResponse response = build();

    public CatalogResponse catalog() { return response; }

    private static CatalogResponse build() {
        List<IndicatorDto> indicators = AlertCatalog.indicators().stream().map(AlertCatalogService::indicator).toList();
        List<PresetDto> presets = AlertCatalog.presets().stream().map(AlertCatalogService::preset).toList();
        List<FnDto> fns = Arrays.stream(WindowFn.values()).map(f -> new FnDto(f.key(), f.label())).toList();
        List<TransformDto> transforms = List.of(
                new TransformDto("identity", "그대로", List.of()),
                new TransformDto("window", "최근 N일", fns),
                new TransformDto("delta", "N일 전 대비 변화", List.of()),
                new TransformDto("pct", "N일 전 대비 변화율", List.of()));
        List<OperatorDto> operators = Arrays.stream(OperatorKey.values())
                .map(o -> new OperatorDto(o.key(), o.symbol(), o.word())).toList();
        return new CatalogResponse(indicators, presets, transforms, operators);
    }

    private static IndicatorDto indicator(Indicator i) {
        Map<String, RangeDto> ranges = new LinkedHashMap<>();
        for (TransformRule r : i.transforms()) {
            if (r.type() != TransformType.IDENTITY) ranges.put(r.type().key(), new RangeDto(r.nMin(), r.nMax()));
        }
        return new IndicatorDto(i.key().key(), i.label(), i.category(), i.unit().key(),
                i.params().stream().map(p -> new ParamDto(p.key(), p.defaultValue(), p.min(), p.max())).toList(),
                i.intradayLeft(), i.markets().stream().map(Enum::name).toList(),
                i.transforms().stream().map(t -> t.type().key()).toList(), ranges,
                i.operators().stream().map(OperatorKey::key).toList(), i.scope().name().toLowerCase(), false);
    }

    private static PresetDto preset(Preset p) {
        return new PresetDto(p.key().key(), p.label(), p.cadences().stream().map(Enum::name).toList(),
                p.markets().stream().map(Enum::name).toList(), p.scope().name().toLowerCase(),
                p.params().stream().map(AlertCatalogService::param).toList());
    }

    private static PresetParamDto param(PresetParam p) {
        Object defaultValue = p.kind() == PresetParam.Kind.CHOICE ? p.defaultChoice() : p.defaultNumber();
        return new PresetParamDto(p.key(), p.kind().name().toLowerCase(), p.min(), p.max(), defaultValue,
                p.choices(), p.required());
    }
}
```

`OperatorKey.values()`의 순서가 `gte`부터라 연산자 목록의 첫 항목이 `≥ · 이상`이다. `EnumSet`의 순회 순서도 선언 순서라 `markets`는 `KR, US`다.

`alert/api/AlertCatalogController.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.stockproject.portfolio.alert.api.dto.CatalogResponse;
import com.stockproject.portfolio.alert.service.AlertCatalogService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/** 알림 카탈로그. 폼이 고를 수 있는 지표·변형·연산자·프리셋과 범위 (§5). */
@RestController
public class AlertCatalogController {

    private final AlertCatalogService catalog;

    public AlertCatalogController(AlertCatalogService catalog) { this.catalog = catalog; }

    @GetMapping("/alerts/catalog")
    public CatalogResponse catalog() { return catalog.catalog(); }
}
```

- [ ] **Step 4: 종목 검색을 쓴다**

`alert/store/InstrumentSearchRow.java`:

```java
package com.stockproject.portfolio.alert.store;

import java.util.UUID;

/** 종목 검색 결과 한 행. */
public record InstrumentSearchRow(UUID id, String label, String symbol, String market, boolean held) { }
```

`alert/store/InstrumentSearchMapper.java`:

```java
package com.stockproject.portfolio.alert.store;

import com.stockproject.portfolio.auth.UserScope;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

/**
 * 앱 공통 종목 검색 (§11.1). 가나다순은 COLLATE "C"로 한다 — DB 기본 정렬 설정과 무관하게
 * Latin이 한글보다 앞서고 한글은 가나다 순이다(계획 A.10). pattern은 %·_·\를 이스케이프한 검색어다.
 */
@Mapper
public interface InstrumentSearchMapper {

    String HELD = """
            WITH latest AS (
                SELECT max(pl.as_of) AS as_of FROM position_line pl JOIN account a USING (account_id)
                 WHERE a.user_id = #{scope.userId} AND pl.is_final
            ), held AS (
                SELECT DISTINCT pl.instrument_id FROM position_line pl JOIN account a USING (account_id)
                 WHERE a.user_id = #{scope.userId} AND pl.as_of = (SELECT as_of FROM latest) AND pl.quantity > 0
            )
            """;

    @Select(HELD + """
            SELECT i.instrument_id AS id, i.name AS label, i.symbol, i.market, h.instrument_id IS NOT NULL AS held
              FROM instrument i LEFT JOIN held h USING (instrument_id)
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
            SELECT i.instrument_id AS id, i.name AS label, i.symbol, i.market, true AS held
              FROM instrument i JOIN held h USING (instrument_id)
             WHERE i.asset_class <> 'CASH' AND i.delisted_on IS NULL
             ORDER BY i.name COLLATE "C", i.instrument_id
            """)
    List<InstrumentSearchRow> held(@Param("scope") UserScope scope);
}
```

`alert/api/dto/InstrumentSearchResponse.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.util.List;
import java.util.UUID;

/** GET /instruments (§11.3). */
public record InstrumentSearchResponse(List<Row> rows) {

    public record Row(UUID id, String label, String symbol, String market, boolean held) { }
}
```

`alert/service/InstrumentSearchService.java`:

```java
package com.stockproject.portfolio.alert.service;

import com.stockproject.portfolio.alert.api.dto.InstrumentSearchResponse;
import com.stockproject.portfolio.alert.store.InstrumentSearchMapper;
import com.stockproject.portfolio.alert.store.InstrumentSearchRow;
import com.stockproject.portfolio.auth.UserScope;
import org.springframework.stereotype.Service;

import java.util.List;

/** 종목 고르기 (§12.5.1). 검색어가 없으면 보유 종목 구역이거나 빈 목록이다. */
@Service
public class InstrumentSearchService {

    static final int LIMIT = 30;

    private final InstrumentSearchMapper mapper;

    public InstrumentSearchService(InstrumentSearchMapper mapper) { this.mapper = mapper; }

    public InstrumentSearchResponse search(UserScope scope, String q, boolean heldOnly) {
        String query = q == null ? "" : q.strip();
        List<InstrumentSearchRow> rows;
        if (query.isEmpty()) rows = heldOnly ? mapper.held(scope) : List.of();
        else rows = mapper.search(scope, query, escape(query), LIMIT);
        return new InstrumentSearchResponse(rows.stream()
                .map(r -> new InstrumentSearchResponse.Row(r.id(), r.label(), r.symbol(), r.market(), r.held()))
                .toList());
    }

    /** LIKE 패턴의 특수 문자를 글자 그대로로 — 이스케이프 문자 자신을 먼저 바꾼다. */
    static String escape(String q) {
        return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
    }
}
```

`alert/api/InstrumentController.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.stockproject.portfolio.alert.api.dto.InstrumentSearchResponse;
import com.stockproject.portfolio.alert.service.InstrumentSearchService;
import com.stockproject.portfolio.auth.UserScope;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** 앱 공통 종목 검색 (§11.1). 알림 전용이 아니다. */
@RestController
public class InstrumentController {

    private final InstrumentSearchService search;

    public InstrumentController(InstrumentSearchService search) { this.search = search; }

    @GetMapping("/instruments")
    public InstrumentSearchResponse search(UserScope scope, @RequestParam(required = false) String q,
                                           @RequestParam(defaultValue = "false") boolean held) {
        return search.search(scope, q, held);
    }
}
```

- [ ] **Step 5: 푸시 기기를 쓴다**

`alert/store/PushDeviceMapper.java`:

```java
package com.stockproject.portfolio.alert.store;

import com.stockproject.portfolio.auth.UserScope;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.OffsetDateTime;
import java.util.UUID;

/** 푸시 수신 기기 (§9.2). 토큰이 이미 있으면 지금 사용자로 옮긴다(§14.5). */
@Mapper
public interface PushDeviceMapper {

    @Select("""
            INSERT INTO push_device (device_id, user_id, expo_push_token, platform, created_at, last_seen_at)
            VALUES (#{deviceId}, #{scope.userId}, #{token}, #{platform}, #{now}, #{now})
            ON CONFLICT (expo_push_token) DO UPDATE
               SET user_id = EXCLUDED.user_id, platform = EXCLUDED.platform, last_seen_at = EXCLUDED.last_seen_at
            RETURNING device_id
            """)
    @Options(flushCache = Options.FlushCachePolicy.TRUE)
    UUID upsert(@Param("scope") UserScope scope, @Param("deviceId") UUID deviceId, @Param("token") String token,
                @Param("platform") String platform, @Param("now") OffsetDateTime now);

    @Delete("DELETE FROM push_device WHERE device_id = #{deviceId} AND user_id = #{scope.userId}")
    int delete(@Param("scope") UserScope scope, @Param("deviceId") UUID deviceId);
}
```

`alert/api/dto/DeviceRequest.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

/** POST /devices 본문 (§11.3). */
public record DeviceRequest(String expoPushToken, String platform) { }
```

`alert/api/dto/DeviceResponse.java`:

```java
package com.stockproject.portfolio.alert.api.dto;

import java.util.UUID;

/** 기기 등록 응답. 로그아웃할 때 이 ID로 지운다. */
public record DeviceResponse(UUID deviceId) { }
```

`alert/service/DeviceService.java`:

```java
package com.stockproject.portfolio.alert.service;

import com.stockproject.portfolio.alert.store.PushDeviceMapper;
import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.validation.RequestRejected;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.OffsetDateTime;
import java.util.Set;
import java.util.UUID;

/** 푸시 수신 기기. 토큰은 기기에 알림을 보낼 수 있는 자격이라 로그에 남기지 않는다. */
@Service
public class DeviceService {

    private static final Set<String> PLATFORMS = Set.of("IOS", "ANDROID");
    private static final int TOKEN_MAX = 200;

    private final PushDeviceMapper mapper;
    private final Clock clock;

    public DeviceService(PushDeviceMapper mapper, Clock clock) {
        this.mapper = mapper;
        this.clock = clock;
    }

    public UUID register(UserScope scope, String token, String platform) {
        if (token == null || token.isBlank() || token.length() > TOKEN_MAX || !PLATFORMS.contains(platform)) {
            throw new RequestRejected("INVALID_DEVICE", "기기 정보를 확인해 주세요");
        }
        return mapper.upsert(scope, UUID.randomUUID(), token.strip(), platform, OffsetDateTime.now(clock));
    }

    public void unregister(UserScope scope, UUID deviceId) {
        if (mapper.delete(scope, deviceId) == 0) {
            throw new RequestRejected("DEVICE_NOT_FOUND", "기기를 찾을 수 없어요", true);
        }
    }
}
```

`alert/api/DeviceController.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.stockproject.portfolio.alert.api.dto.DeviceRequest;
import com.stockproject.portfolio.alert.api.dto.DeviceResponse;
import com.stockproject.portfolio.alert.service.DeviceService;
import com.stockproject.portfolio.auth.UserScope;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

/** 푸시 수신 기기 등록·해제 (§9.2). */
@RestController
@RequestMapping("/devices")
public class DeviceController {

    private final DeviceService devices;

    public DeviceController(DeviceService devices) { this.devices = devices; }

    @PostMapping
    public DeviceResponse register(UserScope scope, @RequestBody DeviceRequest body) {
        return new DeviceResponse(devices.register(scope, body.expoPushToken(), body.platform()));
    }

    @DeleteMapping("/{deviceId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void unregister(UserScope scope, @PathVariable UUID deviceId) {
        devices.unregister(scope, deviceId);
    }
}
```

- [ ] **Step 6: 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.alert.api.*'`
Expected: PASS

- [ ] **Step 7: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/alert \
        src/test/java/com/stockproject/portfolio/alert/api/AlertCatalogApiTest.java \
        src/test/java/com/stockproject/portfolio/alert/api/InstrumentSearchApiTest.java \
        src/test/java/com/stockproject/portfolio/alert/api/DeviceApiTest.java
git commit -m "feat: 알림 카탈로그·종목 검색·푸시 기기 API를 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: 로컬 CORS · 아키텍처 규칙 · 결정 기록 · 끝에서 끝 흐름

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/auth/LocalCorsConfig.java`
- Modify: `src/test/java/com/stockproject/portfolio/auth/LocalCorsTest.java`
- Modify: `src/test/java/com/stockproject/portfolio/ArchitectureRulesTest.java`
- Modify: `docs/decisions.md`
- Test: `src/test/java/com/stockproject/portfolio/alert/api/AlertFlowApiTest.java`

**Interfaces:**
- Consumes: Task 10~13의 경로 전부.
- Produces: 로컬 프로파일에서 `/alerts/**`(GET · POST · PUT · DELETE) · `/instruments`(GET) · `/devices/**`(POST · DELETE) preflight 허용. 순수 알림 패키지의 프레임워크 독립을 ArchUnit으로 강제.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`LocalCorsTest`의 클래스 주석 둘째 문단을 바꾼다.

```java
 * <p>여는 범위가 좁다는 것까지 확인한다 — 출처 하나, 앱이 부르는 경로만, 메서드는 경로가 쓰는 것만.</p>
```

그리고 다음 테스트를 더한다.

```java
    @Test
    void 알림_명령_preflight를_허용한다() throws Exception {
        mockMvc.perform(options("/alerts/50000000-0000-0000-0000-000000000001")
                        .header("Origin", ORIGIN)
                        .header("Access-Control-Request-Method", "PUT")
                        .header("Access-Control-Request-Headers", "Authorization, Content-Type"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", ORIGIN))
                .andExpect(header().string("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE"));
    }

    @Test
    void 종목_검색과_기기_preflight를_허용한다() throws Exception {
        mockMvc.perform(options("/instruments")
                        .header("Origin", ORIGIN)
                        .header("Access-Control-Request-Method", "GET")
                        .header("Access-Control-Request-Headers", "Authorization"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Methods", "GET"));
        mockMvc.perform(options("/devices/60000000-0000-0000-0000-000000000001")
                        .header("Origin", ORIGIN)
                        .header("Access-Control-Request-Method", "DELETE")
                        .header("Access-Control-Request-Headers", "Authorization"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Methods", "POST,DELETE"));
    }

    @Test
    void 종목_검색은_조회만_연다() throws Exception {
        mockMvc.perform(options("/instruments")
                        .header("Origin", ORIGIN)
                        .header("Access-Control-Request-Method", "POST"))
                .andExpect(status().isForbidden());
    }
```

`ArchitectureRulesTest`에 규칙을 더한다.

```java
    /**
     * 알림의 순수 계산은 프레임워크도 저장소도 모른다.
     *
     * <p>미리보기와 평가기가 같은 코드로 계산해야 "미리보기에서는 ✓인데 울리지 않는" 일이 없다.
     * 계산이 Spring이나 매퍼에 묶이면 평가기가 그 코드를 그대로 가져다 쓸 수 없다.</p>
     */
    @Test
    void 알림의_순수_계산은_프레임워크와_저장소에_의존하지_않는다() {
        ArchRule rule = noClasses()
                .that().resideInAnyPackage("..alert.catalog..", "..alert.spec..", "..alert.compile..",
                        "..alert.indicator..", "..alert.evaluation..", "..alert.sentence..")
                .should().dependOnClassesThat()
                .resideInAnyPackage("org.springframework..", "org.apache.ibatis..", "jakarta..",
                        "com.fasterxml.jackson..", "..alert.data..", "..alert.store..", "..alert.service..",
                        "..alert.api..", "..alert.validation..")
                .because("미리보기와 평가기가 같은 계산을 쓴다");
        rule.check(classes);
    }
```

`src/test/java/com/stockproject/portfolio/alert/api/AlertFlowApiTest.java`:

```java
package com.stockproject.portfolio.alert.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.alert.AlertApiClient;
import com.stockproject.portfolio.alert.FixedClockConfig;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.web.servlet.MockMvc;

import static com.stockproject.portfolio.alert.api.AlertPreviewApiTest.SAMSUNG;
import static org.assertj.core.api.Assertions.assertThat;

/** 새 알림 흐름 (§12.5) 전체 — 종목 고르기 → 미리보기 → 저장 → 목록 → 상세 → 수정 → 끄기 → 삭제. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(FixedClockConfig.class)
@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})
class AlertFlowApiTest {

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;

    @Test
    void 새_알림을_만들고_고치고_지운다() throws Exception {
        AlertApiClient api = new AlertApiClient(mockMvc, json);

        JsonNode found = api.get("/instruments?q=005930", "yhr").body().get("rows").get(0);
        String instrument = found.get("id").asText();
        assertThat(found.get("held").asBoolean()).isTrue();

        String draft = """
                { "instrument_id": "%s", "name": "삼성전자 박스권", "cadence": "CLOSE", "trigger_type": "PRESET",
                  "trigger_spec": { "preset_key": "box_breakout", "params": { "window_days": 20 } } }
                """.formatted(instrument);
        JsonNode preview = api.post("/alerts/preview", "yhr", draft).body();
        assertThat(preview.get("valid").asBoolean()).isTrue();
        assertThat(preview.get("summary").get("short").asText()).isEqualTo("종가 · 20일 박스권(폭 15% 이내) 상단 돌파");
        assertThat(preview.get("current").get("header").asText()).isEqualTo("9/25 종가 기준");

        String id = api.post("/alerts", "yhr", draft).body().get("alert_id").asText();
        assertThat(api.post("/alerts/preview", "yhr", draft).body().get("duplicate_of").asText()).isEqualTo(id);

        JsonNode card = api.get("/alerts", "yhr").body().get("data").get("rows").get(0);
        assertThat(card.get("alert_id").asText()).isEqualTo(id);
        assertThat(card.get("summary").get("short").asText()).isEqualTo("종가 · 20일 박스권(폭 15% 이내) 상단 돌파");

        JsonNode detail = api.get("/alerts/" + id, "yhr").body();
        assertThat(detail.get("trigger_spec").get("params").get("window_days").asInt()).isEqualTo(20);

        String edited = """
                { "instrument_id": "%s", "name": "삼성전자 박스권", "cadence": "CLOSE", "trigger_type": "PRESET",
                  "trigger_spec": %s }
                """.formatted(instrument, detail.get("trigger_spec").toString().replace("\"window_days\":20",
                "\"window_days\":60"));
        assertThat(api.put("/alerts/" + id, "yhr", edited).status()).isEqualTo(200);
        assertThat(api.get("/alerts/" + id, "yhr").body().get("summary").get("short").asText())
                .isEqualTo("종가 · 60일 박스권(폭 15% 이내) 상단 돌파");

        assertThat(api.post("/alerts/" + id + "/pause", "yhr", null).status()).isEqualTo(204);
        assertThat(api.get("/alerts/" + id, "yhr").body().get("status").asText()).isEqualTo("PAUSED");

        assertThat(api.delete("/alerts/" + id, "yhr").status()).isEqualTo(204);
        assertThat(api.get("/alerts", "yhr").body().get("empty_reason").asText()).isEqualTo("NO_ALERTS");
    }
}
```

수정 화면이 받은 `trigger_spec`을 그대로 다시 보내도 거부되지 않는다는 것(§4.2)을 이 흐름이 함께 확인한다.

- [ ] **Step 2: 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.auth.LocalCorsTest' --tests 'com.stockproject.portfolio.ArchitectureRulesTest' --tests 'com.stockproject.portfolio.alert.api.AlertFlowApiTest'`
Expected: `LocalCorsTest`의 새 테스트 셋이 FAIL(403), 나머지는 PASS. 아키텍처 규칙이 실패하면 순수 패키지가 금지 패키지를 import한 곳을 고친다.

- [ ] **Step 3: 로컬 CORS를 넓힌다**

`LocalCorsConfig`를 다음으로 바꾼다.

```java
package com.stockproject.portfolio.auth;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

/**
 * 브라우저에서 화면과 실제 응답을 함께 보기 위한 출처 허용. 로컬 전용이다.
 *
 * <p>여는 범위는 앱이 실제로 부르는 경로와 그 경로가 쓰는 메서드뿐이다 — 로그인, 포트폴리오 조회,
 * 알림, 종목 검색, 푸시 기기. 나머지 경로는 등록하지 않았고, 등록하지 않은 경로의 preflight는 거절된다.</p>
 *
 * <p>토큰을 헤더로 보내고 쿠키를 쓰지 않으므로 자격 증명은 허용하지 않는다. 이 빈이 없는
 * 프로파일에서는 CORS 필터가 아예 붙지 않는다 — {@link SecurityConfig}.</p>
 */
@Configuration
@Profile("local")
class LocalCorsConfig {

    /** 프론트 개발 서버. 포트나 호스트 표기가 다르면 브라우저는 다른 출처로 본다. */
    private static final String DEV_SERVER = "http://localhost:8081";

    /** Authorization은 조회에, Content-Type은 JSON 본문에 필요하다. 둘 다 preflight를 부른다. */
    private static final List<String> HEADERS = List.of("Authorization", "Content-Type");

    @Bean
    UrlBasedCorsConfigurationSource corsConfigurationSource() {
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/auth/login", allowing("POST"));
        source.registerCorsConfiguration("/portfolio/**", allowing("GET"));
        source.registerCorsConfiguration("/alerts/**", allowing("GET", "POST", "PUT", "DELETE"));
        source.registerCorsConfiguration("/instruments", allowing("GET"));
        source.registerCorsConfiguration("/devices/**", allowing("POST", "DELETE"));
        return source;
    }

    private static CorsConfiguration allowing(String... methods) {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOrigins(List.of(DEV_SERVER));
        config.setAllowedMethods(List.of(methods));
        config.setAllowedHeaders(HEADERS);
        return config;
    }
}
```

`/alerts/**`와 `/devices/**`는 `/alerts` · `/devices` 자체도 덮는다.

- [ ] **Step 4: 결정 기록을 고친다**

`docs/decisions.md`의 "브라우저 출처 허용(CORS)" 절에서 첫 항목을 바꾼다.

```markdown
- **여는 범위는 앱이 실제로 부르는 경로와 그 경로가 쓰는 메서드뿐이다** — `POST /auth/login`,
  `GET /portfolio/**`, `/alerts/**`(GET · POST · PUT · DELETE), `GET /instruments`,
  `/devices/**`(POST · DELETE). 등록하지 않은 경로의 preflight는 거절된다.
- **허용 헤더는 `Authorization`과 `Content-Type`.** 요청에 토큰을 싣고 본문이 JSON이라
  둘 다 preflight를 부른다. 나머지는 브라우저의 안전 목록으로 지나간다.
```

(기존의 "허용 헤더는 … 조회에 토큰을 싣고 로그인 본문이 JSON이라" 항목을 위 둘째 항목으로 바꾼다.)

"인덱스 · 보관 기간 · 파티셔닝" 절 앞에 다음 두 절을 더한다.

```markdown
## 알림 계산 — 순수 패키지 하나를 미리보기와 평가기가 함께 쓴다

알림의 카탈로그 · 트리거 모델 · 컴파일 · 지표 계산 · 3값 평가 · 문장은 Spring과 MyBatis를 모르는
패키지(`alert.catalog` · `spec` · `compile` · `indicator` · `evaluation` · `sentence`)에 있다.
미리보기 API와 평가기가 이 코드를 그대로 부른다.

미리보기와 평가기가 각자 계산하면 "미리보기에서는 ✓인데 울리지 않는" 일이 생긴다. 사용자는 그
차이를 버그로만 읽는다. 순수 패키지가 프레임워크에 기대지 않는다는 것은 `ArchitectureRulesTest`가
강제한다.

**감수하는 것**: 미리보기는 데이터 읽기(`alert.data`)를 거쳐 입력을 모으고, 평가기는 같은 입력을
여러 알림에 나눠 쓴다. 입력을 모으는 코드는 둘이 다를 수 있다 — 계산이 같으면 결과가 같다.

## 알림 trigger_spec — JSONB, 타입 핸들러 없이

`alert.trigger_spec`은 종류마다 모양이 달라 JSONB다(알림 스펙 §4.4). MyBatis 타입 핸들러를 두지
않고 SQL에서 바꾼다 — 쓸 때 `CAST(#{json} AS jsonb)`, 읽을 때 `trigger_spec::text`. 핸들러 하나를
위해 `type-handlers-package` 구성을 넓히지 않기 위해서다.

저장하는 JSON은 요청 원문이 아니라 해석한 모델을 다시 쓴 것이다(`TriggerSpecWriter`). 모르는 필드가
섞이지 않고, 조립형에는 `lag`이 없다 — `lag`은 평가와 미리보기에서 컴파일할 때만 정해진다.

**되돌리는 조건**: JSONB 컬럼이 셋을 넘거나 JSON 안을 조건으로 조회해야 하면 타입 핸들러를 둔다.
```

- [ ] **Step 5: 전체 테스트를 돌린다**

Run: `./gradlew test`
Expected: PASS — 기존 포트폴리오 테스트 포함 전부.

실패하는 기존 테스트가 있으면 알림 픽스처가 원인인지 먼저 본다. `sample_alert_market.sql`은 알림 테이블과 미러만 비우고, `sample_portfolio.sql`이 지우는 테이블은 건드리지 않는다.

- [ ] **Step 6: 커밋한다**

```bash
git add src/main/java/com/stockproject/portfolio/auth/LocalCorsConfig.java \
        src/test/java/com/stockproject/portfolio/auth/LocalCorsTest.java \
        src/test/java/com/stockproject/portfolio/ArchitectureRulesTest.java \
        src/test/java/com/stockproject/portfolio/alert/api/AlertFlowApiTest.java \
        docs/decisions.md
git commit -m "feat: 알림 경로의 로컬 CORS와 순수 계산 규칙을 둔다

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
