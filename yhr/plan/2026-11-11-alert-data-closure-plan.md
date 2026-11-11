# 알림 데이터 닫힘 · 평가 소요 관측 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 운영자가 환경변수로 수급 · 장중 조건을 닫으면 카탈로그 · 검증 · 평가 · 조회 · 앱이 그 규칙대로 움직이고, 평가 한 번의 소요를 로그로 읽을 수 있게 한다.

**Architecture:** 스위치 두 개를 읽는 `DataClosure` 빈 하나가 "무엇이 닫혔나"와 "이 알림이 닫힘에 어떻게 걸리나(`AS_CLOSE` · `HELD`)"를 정한다. 카탈로그 · 검증기 · 평가기 · 조회 · 지연 안내가 모두 이 빈에 묻는다. 평가기는 `HELD`를 건너뛰며 `alert_state.held_since`를 남기고, `AS_CLOSE`는 종가로 컴파일해 판정하되 해시는 원래 평가 시점으로 구한다. 발화 행은 실제 평가 시점(`alert_event.cadence`)을 기록한다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · MyBatis · Flyway · PostgreSQL 16 · JUnit 5 · AssertJ / React Native(Expo 58) · TypeScript · jest-expo

**Spec:** [알림 스펙](../specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md) §5.6이 중심이다. 이 계획의 §번호는 그 문서의 절이다. 관련 절: §5.5 · §6.2 · §6.5 · §6.6 · §7.4 · §8.4 · §10.1 · §11.2 · §11.3 · §11.4 · §12.2 · §12.5 · §12.7 · §12.9 · §14.2 ~ §14.4 · §15. [데이터 요구사항](../specs/data-requirements.md) §5.2 · §5.3.

## Global Constraints

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어. 커밋 접두어 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **커밋 · 푸시는 사용자가 요청할 때만 한다.** 각 태스크의 커밋 단계는 요청을 받은 뒤 실행한다.
- 주석은 히스토리 없이 최신 사실만 쓰고, 문서 절 번호(§ · SG- · N-)를 지칭하지 않고 주석만으로 이해되게 쓴다. 검증하지 않은 것은 단정하지 않는다.
- 백엔드는 `alert/` 패키지와 `application.yaml` · `k8s/deployment.yaml` · 새 마이그레이션만 고친다. `snapshot/` · `dataeng/` · `docs/yhr/test/`는 고치지 않는다.
- 운영 DB에 쓰지 않는다. 구현 중 스펙과 코드가 어긋나면 멈추고 보고한다.
- 마이그레이션 번호는 `V18`(`db/migration`). 병합 직전 `origin/main`에 V18이 생겼으면 다음 빈 번호로 옮기고 전용 DB를 새로 만들어 다시 돈다(DB를 지우고 만드는 일은 승인을 받는다).
- DB를 쓰는 테스트는 전용 DB에서만 돈다: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_closure?currentSchema=app,data' ./gradlew test --rerun-tasks` (특정 클래스는 `--tests '<FQCN>'` 추가). DB 테스트는 돌리기 전에 사용자에게 묻는다. DB 없는 단위 테스트는 묻지 않는다.
- 테스트 메서드 이름은 기존처럼 한국어 문장.
- 매니페스트(`k8s/deployment.yaml`)는 커밋까지만 한다. 적용 · 배포는 따로 승인을 받는다.
- 앱: Expo SDK 58. 끝에 `npx jest` · `npx tsc --noEmit` 통과. 실기기 확인은 사용자 요청 시.

### 고정 값 (스펙 §5.6 · §12.7 그대로)

| 이름 | 값 |
|---|---|
| 환경변수 → 설정 | `ALERT_FLOW_ENABLED` → `portfolio.alert.data.flow-enabled`(기본 `true`) · `ALERT_INTRADAY_ENABLED` → `portfolio.alert.data.intraday-enabled`(기본 `true`) |
| 수급으로 닫히는 것 | 지표 `FOREIGN_NET_BUY` · `INSTITUTION_NET_BUY`, 프리셋 `INVESTOR_STREAK` · `INVESTOR_TURN` |
| 장중으로 닫히는 것 | `Cadence.INTRADAY` |
| 닫힌 장중 사유 | `지금은 장중 시세를 제공하지 않아요` |
| 닫힌 수급 사유 | `지금은 외국인·기관 매매 정보를 제공하지 않아요` |
| `AS_CLOSE` 문구 | `장중 시세를 제공하지 않는 동안 종가로 확인해요` |
| 수급 `HELD` 문구 | `외국인·기관 매매 정보를 제공하지 않는 동안 일시중지돼요` |
| `N분 지속` `HELD` 문구 | `장중 시세를 제공하지 않는 동안 일시중지돼요` |
| 상세에 덧붙이는 문구(앱) | `다시 제공되면 자동으로 이어져요` |
| `HELD` 배지(앱) | `일시중지`, 확인 불가와 같은 회색 |
| 필드 오류 | 코드 `DATA_UNAVAILABLE`, 문구 `지금은 고를 수 없는 조건이에요` |
| 소요 로그 | `평가 주기 elapsed_ms={} alerts={} points={} pod={}` — 30000ms 초과면 WARN, 아니면 INFO |

## Review Focus

1. **장중 중에 스위치를 닫고 재시작** — 그날 10:15 스냅샷까지 평가된 장중 알림이 그날 종가부터 평가되어야 한다. → Task 5 `장중_평가가_있던_날은_그날_종가부터_평가한다`.
2. **닫힌 동안 이미 있는 수급 알림의 이름만 바꾸는 수정** — 거부되면 사용자가 자기 알림을 못 고친다. → Task 3 `저장된_수급_지표는_수정에서_거부하지_않는다`.
3. **다시 열린 뒤 데이터팀이 지난 날짜 수급을 채움** — 몇 주 전 날짜로 울리면 안 된다. → Task 5 `다시_열린_뒤_held_since가_있으면_최신_시점_하나만_평가한다`.
4. **닫히기 직전 결과가 TRUE인 수급 알림** — 목록 맨 위 `조건 충족 중`이 아니라 `일시중지` 묶음에 있어야 한다. → Task 7 `HELD_알림은_직전_결과와_상관없이_확인_불가_묶음에_정렬된다`.
5. **닫힌 장중으로 프리셋 미리보기** — `cadence` 오류가 있어도 현재값 상자는 종가 기준으로 채워져야 한다(지금 `compilable`은 `cadence` 오류가 있으면 컴파일을 건너뛴다). → Task 3 `닫힌_장중_프리셋_미리보기는_오류와_함께_종가_현재값을_싣는다`.

---

## 파일 구조

**back-end** (`.worktrees/back-end-alert-closure`, 브랜치 `feat/alert-data-closure`)

| 파일 | 책임 |
|---|---|
| `alert/closure/DataClosure.java` (신규) | 스위치를 읽고 닫힘을 판정한다 |
| `alert/closure/Closure.java` (신규) | `record Closure(Kind kind, String message)`, `enum Kind { AS_CLOSE, HELD }` |
| `src/main/resources/application.yaml` | `portfolio.alert.data.*` |
| `alert/service/AlertCatalogService.java` · `alert/api/dto/CatalogResponse.java` | `available` · `unavailable_reason` · `cadence_options` |
| `alert/validation/AlertValidator.java` · `ExistingAlert.java` | `DATA_UNAVAILABLE`, 저장된 값과 견주기 |
| `alert/service/AlertCommandService.java` · `AlertPreviewService.java` | 검증 호출, 닫힌 동안의 현재값 |
| `src/main/resources/db/migration/V18__alert_data_closure.sql` (신규) | `alert_state.held_since` · `alert_event.cadence` |
| `alert/store/RuntimeMapper.java` · `RuntimeAlertRow.java` · `AlertRuntimeStore.java` · `AlertMapper.java` | `held_since` 읽기 · 쓰기 · 비우기, 발화 `cadence` |
| `alert/runtime/EvaluationRunner.java` · `Target.java` · `AlertRuntimeWriter.java` | `HELD` · `AS_CLOSE` · 재개 · 그날 종가 |
| `alert/runtime/TickReport.java` (신규) · `AlertJobs.java` | 소요 로그 |
| `alert/store/AlertQueryMapper.java` · `AlertEventMapper.java` · `AlertListRow.java` | 발화 `e.cadence`, 정렬용 `created_at` |
| `alert/service/AlertQueryService.java` · `alert/api/dto/AlertCardDto.java` · `AlertDetailDto.java` · `DataClosureDto.java` (신규) | `data_closure`, 정렬 |
| `alert/service/MarketDelayNotices.java` | 실제로 평가에 쓰는 컴파일로 기다리는 데이터를 센다 |
| `k8s/deployment.yaml` | 스위치 값 (Task 8) |

테스트: `alert/closure/DataClosureTest.java`(신규, 단위) · `alert/validation/AlertValidatorTest.java`(단위) · `alert/runtime/TickReportTest.java`(신규, 단위) · `alert/api/AlertCatalogApiTest.java` · `AlertCommandApiTest.java` · `AlertPreviewApiTest.java` · `alert/runtime/EvaluationRunnerTest.java` · `alert/api/AlertQueryApiTest.java` · `AlertEventApiTest.java` · `MarketDelayApiTest.java`(DB).

**front-end** (`.worktrees/front-end-alert-closure`, 브랜치 `feat/alert-data-closure`, 최신 `origin/main`에서)

| 파일 | 책임 |
|---|---|
| `src/api/alertTypes.ts` · `src/fixtures/alerts.ts` | 새 필드 타입 · 픽스처 |
| `src/screens/alerts/status.ts` · `AlertCard.tsx` · `AlertDetailScreen.tsx` | `일시중지` 배지 · 넷째 줄 · 상세 문구 |
| `src/ui/SegmentedControl.tsx` | 칸 비활성 |
| `src/screens/alertEditor/composable.ts` · `presetFields.ts` · `draft.ts` · `PresetStep.tsx` · `ComposableStep.tsx` · `EditorContext.tsx` | 닫힌 지표 · 프리셋 · 장중 비활성, 수정 중 저장된 값 허용, 프리셋 기본 평가 시점 |

---

### Task 0: 작업 공간과 전용 DB

- [ ] **Step 1:** 백엔드 worktree `.worktrees/back-end-alert-closure`가 최신 `origin/main`인지 본다: `git fetch && git log -1 origin/main`, 뒤처졌으면 `git rebase origin/main`.
- [ ] **Step 2:** 사용자 승인 뒤 로컬 PostgreSQL에 `portfolio_test_closure`를 만든다(기존 전용 DB와 같은 방식, 소유자 · 스키마 `app,data`).
- [ ] **Step 3:** 사용자 승인 뒤 `TEST_DB_URL=… ./gradlew test --rerun-tasks`가 바뀌기 전 상태에서 통과하는지 본다. Expected: BUILD SUCCESSFUL.

### Task 1: 스위치와 닫힘 판정

**Files:** Create `alert/closure/DataClosure.java` · `Closure.java`, Modify `application.yaml`, Test `alert/closure/DataClosureTest.java`

**Interfaces — Produces:**
- `DataClosure(@Value("${portfolio.alert.data.flow-enabled:true}") boolean flowEnabled, @Value("${portfolio.alert.data.intraday-enabled:true}") boolean intradayEnabled)` — `@Component`
- `static DataClosure open()` (둘 다 열림, 테스트용)
- `Optional<String> reason(IndicatorKey)` · `Optional<String> reason(PresetKey)` · `Optional<String> reason(Cadence)` — 닫혔으면 사유
- `Optional<Closure> of(CompiledTrigger trigger, Cadence cadence)` — 수급이 닫혔고 조건 어느 피연산자(왼쪽 · 오른쪽)에든 수급 지표가 있으면 `HELD`(수급 문구). 아니고 장중이 닫혔고 `cadence == INTRADAY`이면, 조건 하나라도 `Modifier.PersistMin`이면 `HELD`(`N분 지속` 문구), 아니면 `AS_CLOSE`. 그 밖은 빈 값.
- `String` 상수: `DATA_UNAVAILABLE_MESSAGE` 등 고정 값 표의 문구를 이 클래스에 모은다.

- [ ] **Step 1: 실패하는 테스트**
  - `둘_다_열려_있으면_아무것도_닫지_않는다` — `open().reason(Cadence.INTRADAY)`, `reason(IndicatorKey.FOREIGN_NET_BUY)`, `of(수급 프리셋 컴파일, CLOSE)` 모두 빈 값.
  - `수급을_닫으면_수급_지표와_프리셋에_사유가_붙는다` — `new DataClosure(false, true)`: 두 지표 · 두 프리셋의 `reason`이 `지금은 외국인·기관 매매 정보를 제공하지 않아요`, `PRICE` · `PRICE_REACH` · `INTRADAY`는 빈 값.
  - `수급을_닫으면_오른쪽에만_수급이_있어도_HELD다` — `price gte`가 아니라 `foreign_net_buy`를 오른쪽 피연산자로 쓴 조립형(CLOSE)이 `HELD` · 수급 문구.
  - `장중을_닫으면_장중_알림은_AS_CLOSE다` — `price_reach` INTRADAY 컴파일 → `AS_CLOSE` · `장중 시세를 제공하지 않는 동안 종가로 확인해요`. 같은 것을 CLOSE로 물으면 빈 값.
  - `장중을_닫으면_N분_지속이_있는_장중_알림은_HELD다` — `persist_min 10` 조건 → `HELD` · `장중 시세를 제공하지 않는 동안 일시중지돼요`.
- [ ] **Step 2:** `./gradlew test --tests '*DataClosureTest'` → FAIL(클래스 없음).
- [ ] **Step 3:** 구현. `application.yaml`에 `portfolio.alert.data.flow-enabled: ${ALERT_FLOW_ENABLED:true}` · `intraday-enabled: ${ALERT_INTRADAY_ENABLED:true}`를 `portfolio.alert.runtime` 옆에 둔다.
- [ ] **Step 4:** 같은 명령 → PASS.
- [ ] **Step 5: Commit** `feat: 수급 · 장중 조건을 닫는 스위치와 판정을 둔다`

### Task 2: 카탈로그 응답

**Files:** Modify `AlertCatalogService.java` · `CatalogResponse.java`, Test `AlertCatalogApiTest.java`(DB)

**Interfaces:**
- Consumes: `DataClosure.reason(...)`
- Produces: `IndicatorDto`와 `PresetDto` 끝에 `boolean available, String unavailableReason`. `CatalogResponse`에 `List<CadenceOptionDto> cadenceOptions`(transforms 앞), `record CadenceOptionDto(String key, boolean available, String unavailableReason)` — 순서 `INTRADAY`, `CLOSE`. `deprecated`는 그대로 `false`.
- 서비스는 생성자에서 `DataClosure`를 받아 한 번 만든다(스위치는 재시작해야 바뀐다).

- [ ] **Step 1: 실패하는 테스트** (`@TestPropertySource`로 스위치를 바꾼 중첩 클래스 둘)
  - `열려_있으면_모든_항목이_고를_수_있다` — 모든 지표 · 프리셋 `available == true`, `unavailable_reason == null`, `cadence_options`가 `[INTRADAY true, CLOSE true]`.
  - `수급을_닫으면_수급_항목만_닫히고_목록에_남는다` — `foreign_net_buy` · `institution_net_buy` · `investor_streak` · `investor_turn`이 목록에 있고 `available == false` · 수급 사유. 다른 항목은 `true`. 지표의 `deprecated`는 모두 `false`.
  - `장중을_닫으면_cadence_options의_INTRADAY만_닫힌다` — `INTRADAY` `available == false` · 장중 사유, `price_reach.cadences`는 `["INTRADAY","CLOSE"]` 그대로.
- [ ] **Step 2:** 사용자 승인 뒤 `--tests '*AlertCatalogApiTest'` → FAIL.
- [ ] **Step 3:** 구현.
- [ ] **Step 4:** 같은 명령 → PASS.
- [ ] **Step 5: Commit** `feat: 카탈로그가 닫힌 지표 · 프리셋 · 평가 시점을 사유와 함께 내린다`

### Task 3: 저장 검증과 미리보기

**Files:** Modify `AlertValidator.java` · `ExistingAlert.java` · `AlertCommandService.java` · `AlertPreviewService.java`, Test `AlertValidatorTest.java`(단위) · `AlertCommandApiTest.java` · `AlertPreviewApiTest.java`(DB)

**Interfaces:**
- `ExistingAlert(UUID instrumentId, String triggerType, Cadence cadence, TriggerSpec trigger)` — 두 호출부가 저장된 `cadence` · `trigger_spec`(`AlertRequestParser.stored`)을 채운다. `stored`가 예외를 던지면(읽을 수 없는 저장 spec) `trigger`는 null이고, 닫힘 판정은 "저장된 값 없음"으로 본다 — 지금처럼 수정이 500이 되지 않는다. `AlertPreviewService`는 생성자에 `ObjectMapper`를 더한다.
- `AlertValidator.validate(AlertDraft, InstrumentFacts, ExistingAlert, DataClosure, OffsetDateTime)` · `requireValid(같은 인자)` — 기존 호출부는 모두 넘긴다.
- 오류 위치: 지표는 그 피연산자의 `…indicator` 경로(조립형 `trigger_spec.conditions[i].left.indicator` · `.right.indicator`), 프리셋은 `trigger_spec.preset_key`, 장중은 `cadence`. 코드 `DATA_UNAVAILABLE`, 문구 `지금은 고를 수 없는 조건이에요`.
- 새로 넣는 것: 지표는 저장된 조립형 조건들의 지표 키 집합(왼쪽 · 오른쪽 피연산자 모두)에 없는 닫힌 지표, 프리셋은 저장된 `preset_key`와 다른 닫힌 프리셋, 장중은 저장된 `cadence`가 `INTRADAY`가 아닐 때. 생성(`existing == null`)이면 닫힌 것 전부.
- 프리셋은 키로만 본다 — 컴파일 결과의 수급 지표로 같은 오류를 또 달지 않는다.

- [ ] **Step 1: 실패하는 단위 테스트** (`AlertValidatorTest`)
  - `닫힌_수급_지표로_만들면_DATA_UNAVAILABLE이다` — 경로 `trigger_spec.conditions[0].left.indicator`.
  - `닫힌_수급_프리셋으로_만들면_preset_key에_DATA_UNAVAILABLE이다` — 오류는 그 하나뿐.
  - `닫힌_장중으로_만들면_cadence에_DATA_UNAVAILABLE이다` — 프리셋 · 조립형 각각.
  - `저장된_수급_지표는_수정에서_거부하지_않는다` — 저장 조건에 `foreign_net_buy`, 이름만 바꾼 초안 → 오류 없음.
  - `수정에서_새로_넣은_닫힌_지표는_거부한다` — 저장 조건은 `price`, 초안에 `institution_net_buy`를 더함 → 오류.
  - `저장된_오른쪽_피연산자의_수급_지표도_저장된_것으로_본다` — 저장 조건 `foreign_net_buy gte foreign_net_buy(window avg 5)`, 그대로 수정 → 오류 없음.
  - `저장_spec을_읽을_수_없으면_닫힌_것은_새로_넣은_것으로_본다` — `ExistingAlert.trigger == null`, 초안에 수급 지표 → 오류, 예외 없음.
  - `종가_알림을_장중으로_바꾸는_수정은_거부한다` · `장중_알림을_장중으로_둔_수정은_거부하지_않는다`.
- [ ] **Step 2:** `--tests '*AlertValidatorTest'` → FAIL.
- [ ] **Step 3:** 검증기 · 두 서비스 구현. 미리보기는:
  - `compilable`과 `current()`의 조건별 `broken` 판정(116 ~ 119행)이 `DATA_UNAVAILABLE` 오류는 무시한다 — 닫힌 지표 조건이 `입력을 확인해 주세요`로 보이지 않는다.
  - 장중이 닫혔고 초안이 `INTRADAY`면 현재값을 `Compiler.compile(trigger, CLOSE)`와 `CLOSE`로 계산한다(머리 `9/26 종가 기준`). 조건에 `PersistMin`이 있으면 `current`는 null.
  - 문장 상자 · 중복 판정은 초안의 평가 시점 그대로다.
- [ ] **Step 4:** 같은 명령 → PASS. 이어 사용자 승인 뒤 DB 테스트를 더한다:
  - `AlertCommandApiTest` `수급을_닫으면_수급_프리셋_생성이_400이다` — `INVALID_ALERT`, `fields[0].code == DATA_UNAVAILABLE`.
  - `AlertPreviewApiTest` `닫힌_장중_프리셋_미리보기는_오류와_함께_종가_현재값을_싣는다` — `errors`에 `cadence` `DATA_UNAVAILABLE`, `current.header`가 `… 종가 기준`.
  - `AlertPreviewApiTest` `닫힌_동안_N분_지속_장중_초안은_current가_없다`.
  - `AlertPreviewApiTest` `닫힌_수급_지표_조립형_미리보기는_마지막_거래일_값을_싣는다` — 조건의 `text`가 `입력을 확인해 주세요`가 아니다.
- [ ] **Step 5:** `--tests '*AlertCommandApiTest' --tests '*AlertPreviewApiTest'` → PASS.
- [ ] **Step 6: Commit** `feat: 닫힌 조건을 새로 넣는 저장을 거부하고 미리보기는 종가로 계산한다`

### Task 4: V18 — 일시중지 표시와 발화 평가 시점

**Files:** Create `db/migration/V18__alert_data_closure.sql`, Modify `RuntimeMapper.java` · `RuntimeAlertRow.java` · `AlertRuntimeStore.java` · `AlertMapper.java` · `AlertRuntimeWriter.java`, Test `EvaluationRunnerTest.java` · `AlertCommandApiTest.java` · `AlertSchemaTest.java`(DB). `RuntimeAlertRow`를 직접 만드는 테스트 픽스처(`RuntimeFixtures` 등)는 새 필드에 null을 넘긴다.

**Interfaces — Produces:**
- `alert_state.held_since timestamptz NULL`. `alert_event.cadence text NULL CHECK (cadence IN ('INTRADAY','CLOSE'))` — 기존 행은 `alert.cadence`로 채운다. NULL을 허용하는 것은 롤아웃 중 옛 파드의 발화 INSERT와 통합테스트 런북의 주입 SQL(`cadence` 없이 넣는다)이 깨지지 않게 하기 위해서다. 읽는 쪽은 `COALESCE(e.cadence, a.cadence)`. `MigrationLintTest` 규칙을 따른다.
- `RuntimeAlertRow`에 `OffsetDateTime heldSince`(끝), `RuntimeMapper.candidates()` SELECT에 `s.held_since`.
- `RuntimeMapper.markHeld(alertId, now)`: `UPDATE alert_state SET held_since = #{now} WHERE alert_id = #{alertId} AND held_since IS NULL`. `AlertRuntimeStore.markHeld(UUID, OffsetDateTime)`.
- `applyState`의 SET에 `held_since = NULL`을 더한다.
- `insertEvent`에 `cadence` 인자 — `AlertRuntimeWriter.apply`가 `in.cadence().name()`을 넘긴다.
- `AlertMapper` 75행의 상태 초기화(수정 · 다시 켜기)에 `held_since = NULL`.

- [ ] **Step 1: 실패하는 테스트**
  - `EvaluationRunnerTest` `발화는_입력의_평가_시점을_기록한다` — 종가 알림 발화 행의 `alert_event.cadence == 'CLOSE'`.
  - `AlertCommandApiTest` `수정하면_held_since를_비운다` — 픽스처로 `held_since`를 채운 뒤 PUT → null. `다시_켜면_held_since를_비운다` — 같은 픽스처로 resume → null.
  - `AlertSchemaTest` `알림_테이블의_컬럼이_스펙과_같다` — `alert_state`에 `held_since`, `alert_event`에 `cadence`를 이름순으로 더한다.
- [ ] **Step 2:** 사용자 승인 뒤 두 클래스 → FAIL.
- [ ] **Step 3:** 마이그레이션 · 매퍼 구현.
- [ ] **Step 4:** 같은 명령 → PASS. `MigrationLintTest`도 함께.
- [ ] **Step 5: Commit** `feat: 일시중지 시각과 발화의 평가 시점을 기록한다`

### Task 5: 평가기

**Files:** Modify `EvaluationRunner.java` · `Target.java`, Test `EvaluationRunnerTest.java`(DB)

**Interfaces:**
- Consumes: `DataClosure.of`, `AlertRuntimeStore.markHeld`, `RuntimeAlertRow.heldSince`
- `Target.of(RuntimeAlertRow, CompiledTrigger evalTrigger, String specHash, String instrumentName)` 오버로드 — `AS_CLOSE`는 판정용 트리거(종가 컴파일)와 원래 트리거 · 평가 시점으로 구한 `SpecHash.of(original, INTRADAY)`를 넘긴다.
- `EvaluationRunner` 생성자 끝에 `DataClosure`.
- 한 알림의 흐름: 저장 조건을 원래 평가 시점으로 컴파일 → `closure.of(...)`
  - `HELD` → `store.markHeld(alertId, now)` 후 끝(평가 · 상태 반영 없음).
  - `AS_CLOSE` → `StoredTriggers.compile(…, CLOSE)`로 판정 트리거, 평가 시점 `CLOSE`로 시점 · 입력 · 기다리는 데이터를 정한다.
  - 그 밖은 지금과 같다.
- 종가 시점 고르기: `evaluated`가 그 현지 날짜의 `close_at`보다 이르면(장중 스냅샷 시각 — 수집기는 `close_at` 전에만 돈다) 최신 확정 종가 하나만 고른다(`evaluated`가 null일 때와 같다). 아니면 다음 날부터 따라잡는다(지금 규칙). 종가 알림의 `evaluated_as_of`는 늘 `close_at`이라 결과가 바뀌지 않는다.
- `heldSince != null`이고 지금 `HELD`가 아니면(`AS_CLOSE`여도) `evaluated`를 null로 보고 최신 시점 하나를 고른다. 그 시점이 저장된 `evaluated_as_of` 이후가 아니면 고르지 않는다 — `applyState`가 지고(`evaluated_as_of < asOf`) `held_since`가 남아 주기마다 헛도는 것을 막는다. `applyState`의 `prev`는 저장된 `evaluated_as_of` 그대로다.

- [ ] **Step 1: 실패하는 테스트** (스위치를 바꾼 `@TestPropertySource` 중첩 클래스 또는 `DataClosure`를 직접 만든 러너)
  - `수급이_닫히면_수급_알림을_평가하지_않고_held_since만_쓴다` — `last_result` · `evaluated_as_of` · `last_known_result` 그대로, `held_since`가 now. 두 번째 주기에서 `held_since`가 바뀌지 않는다.
  - `장중이_닫히면_장중_알림을_종가로_평가하고_종가_기준으로_울린다` — 9/26 종가 ≥ 기준값 → 발화 1건, `body`가 `9/26 종가 기준`으로 끝나고 `alert_event.cadence == 'CLOSE'`. `spec_hash`는 INTRADAY 컴파일 해시 그대로.
  - `AS_CLOSE는_기준을_다시_잡지_않는다` — 직전 장중 `last_known_result = FALSE`, 종가 참 → 첫 종가 평가에서 울린다.
  - `장중_평가가_있던_날은_그날_종가부터_평가한다` — `evaluated_as_of = 9/26 10:15`, 9/26 일봉 DONE → 시점은 9/26 종가.
  - `장중에서_넘어간_첫_평가는_지난_거래일을_따라잡지_않는다` — `evaluated_as_of = 9/22 10:15`, 9/22 ~ 9/26 일봉 DONE, 9/23 종가만 참 → 평가한 시점은 9/26 하나, 발화 없음.
  - `N분_지속_장중_알림은_닫힌_동안_HELD다` — 평가 없음, `held_since` 기록.
  - `다시_열린_뒤_held_since가_있으면_최신_시점_하나만_평가한다` — `evaluated_as_of = 9/1 종가`, `held_since` 있음, 9/2 ~ 9/26 수급 DONE → 평가한 시점은 9/26 하나, 반영 뒤 `held_since` null.
  - `다시_열린_뒤_장중_알림은_가장_최근_스냅샷으로_돌아간다` — `evaluated_as_of = 9/26 15:30`(종가), 9/29 10:15 스냅샷 → 장중 평가.
  - `다시_열렸지만_새_시점이_없으면_held_since를_남기고_평가하지_않는다` — 최신 수급 DONE이 저장된 `evaluated_as_of`와 같다 → 평가한 시점 0, `held_since` 그대로.
  - `AS_CLOSE_COOLDOWN은_참인_동안_종가마다_울린다` — `cooldown_min = 60`, 9/25 · 9/26 종가 모두 참 → 발화 2건.
  - `AS_CLOSE_COOLDOWN은_두_종가_사이가_간격보다_짧으면_울리지_않는다` — `cooldown_min = 1440`, 9/25 종가 15:30 발화 뒤 9/26이 조기 폐장(캘린더 `close_at` 13:00) 참 → 9/26 발화 없음.
  - `AS_CLOSE_ONE_SHOT은_종가로_울린_뒤_끝난다` — `status = ENDED`.
- [ ] **Step 2:** 사용자 승인 뒤 `--tests '*EvaluationRunnerTest'` → FAIL.
- [ ] **Step 3:** 구현.
- [ ] **Step 4:** 같은 명령과 `*PreviewEvaluatorParityTest` → PASS.
- [ ] **Step 5: Commit** `feat: 닫힌 동안 수급 알림을 일시중지하고 장중 알림을 종가로 평가한다`

### Task 6: 평가 소요 로그

**Files:** Create `alert/runtime/TickReport.java`, Modify `EvaluationRunner.java` · `AlertJobs.java` · `AlertRuntimeConfig.java`, Test `TickReportTest.java`(단위) · `EvaluationRunnerTest.java` · `AlertRuntimeConfigTest.java`(생성자 인자 4개로 맞춘다. mock `tick()`의 null은 `evaluate()`가 로그 없이 넘긴다)

**Interfaces — Produces:**
- `record TickReport(long elapsedMs, int alerts, int points)` · `boolean slow()`(`elapsedMs > 30_000`) · `String line(String pod)` → `평가 주기 elapsed_ms=… alerts=… points=… pod=…`
- `EvaluationRunner.tick()`이 `TickReport`를 돌려준다. `alerts`는 `candidates()` 수, `points`는 평가한 시점 수(`HELD`는 0). 시간은 `System.nanoTime()` 차이.
- `AlertJobs(EvaluationRunner, DeliveryDispatcher, ReceiptChecker, String pod)` — `AlertRuntimeConfig`가 `System.getenv("HOSTNAME")`(없으면 `unknown`)을 넘긴다. `evaluate()`는 `slow()`면 `log.warn`, 아니면 `log.info`로 `line(pod)`를 남긴다.

- [ ] **Step 1: 실패하는 테스트**
  - `TickReportTest` `한_줄은_소요_대상_시점_파드를_담는다` — `new TickReport(1234, 5, 7).line("api-0")` == `평가 주기 elapsed_ms=1234 alerts=5 points=7 pod=api-0`.
  - `TickReportTest` `30초를_넘어야_느리다` — 30000 → false, 30001 → true.
  - `EvaluationRunnerTest` `주기는_대상_알림과_평가한_시점_수를_돌려준다`.
- [ ] **Step 2:** 단위 → FAIL, (승인 뒤) DB → FAIL.
- [ ] **Step 3:** 구현.
- [ ] **Step 4:** PASS.
- [ ] **Step 5: Commit** `feat: 평가 한 주기의 소요를 로그로 남긴다`

### Task 7: 조회 — 닫힘 표시 · 정렬 · 발화 기준 · 지연 안내

**Files:** Create `alert/api/dto/DataClosureDto.java`, Modify `AlertQueryService.java` · `AlertEventService.java` · `AlertCardDto.java` · `AlertDetailDto.java` · `RecentEventDto.java` · `EventDetailDto.java` · `AlertQueryMapper.java` · `AlertListRow.java` · `AlertEventMapper.java` · `MarketDelayNotices.java`, Test `AlertQueryApiTest.java` · `AlertEventApiTest.java` · `MarketDelayApiTest.java`(DB)

**Interfaces:**
- `record DataClosureDto(String kind, String message)`. `AlertCardDto`는 `lastFiredAt` 뒤, `AlertDetailDto`는 `evaluatedAsOf` 뒤에 `DataClosureDto dataClosure`. 닫힘은 `ACTIVE` · `PAUSED` 알림에만 싣는다(`ENDED` · `EXPIRED`는 null).
- 목록 정렬: SQL 정렬은 두고, 서비스가 `ACTIVE`이고 `HELD`인 행의 순위를 확인 불가(2)로 옮겨 다시 정렬한다. 같은 순위 안은 `last_fired_at` 내림차순(null 마지막) → `created_at` 내림차순 → `alert_id`. `AlertListRow`에 `createdAt`.
- 발화의 `cadence`는 `COALESCE(e.cadence, a.cadence)` — 미확인 발화(`AlertQueryMapper.unread`), 울린 알림 목록(`AlertEventMapper.page`), 울린 알림 상세(`AlertEventMapper.detail` → `EventDetailDto`에 `String cadence`), 알림 상세 최근 울림(`AlertQueryMapper.recentEvents` → `RecentEventDto`에 `String cadence`).
- 알림 행의 `evaluated_as_of`는 지금 앱이 날짜와 시각을 그대로 찍으므로(`formatAsOf`) 따로 고치지 않는다 — 종가로 평가된 값도 `9/26 15:30`으로 맞게 읽힌다.
- `MarketDelayNotices.forUser`: 알림마다 `closure.of` — `HELD`는 세지 않고, `AS_CLOSE`는 `DataNeeds.of(종가 컴파일, CLOSE)`로 센다.

- [ ] **Step 1: 실패하는 테스트**
  - `AlertQueryApiTest` `닫힌_동안_카드와_상세에_data_closure가_실린다` — 수급 알림 `{kind: HELD, message: 수급 문구}`, 장중 알림 `{kind: AS_CLOSE, …}`, 가격 종가 알림 null. 열려 있으면 모두 null.
  - `AlertQueryApiTest` `HELD_알림은_직전_결과와_상관없이_확인_불가_묶음에_정렬된다` — `last_result = TRUE`인 수급 알림이 `감시 중` 알림 뒤, `꺼짐` 알림 앞.
  - `AlertEventApiTest` `발화의_cadence는_발화_행의_값이다` — 알림은 INTRADAY, 발화 행 `cadence = CLOSE` → 목록 · 미확인 블록 · 울린 알림 상세 모두 `CLOSE`. `cadence`가 null인 행은 알림의 값.
  - `AlertQueryApiTest` `최근_울림의_cadence는_발화_행의_값이다`.
  - `MarketDelayApiTest` `장중이_닫히면_장중_지연_배너가_뜨지_않고_일봉_지연은_뜬다`.
  - `MarketDelayApiTest` `수급이_닫히면_수급_지연_배너가_뜨지_않는다`.
- [ ] **Step 2:** 사용자 승인 뒤 세 클래스 → FAIL.
- [ ] **Step 3:** 구현.
- [ ] **Step 4:** 같은 명령 → PASS.
- [ ] **Step 5: Commit** `feat: 알림 목록 · 상세에 데이터 닫힘을 싣고 일시중지 알림을 확인 불가 묶음에 둔다`

### Task 8: 매니페스트

**Files:** Modify `k8s/deployment.yaml`

- [ ] **Step 1:** 운영 `data.market_data_run`의 `DAILY_FLOW` · `INTRADAY_QUOTE` 적재 결과(읽기 전용 조회)를 사용자에게 보고하고, 두 스위치의 값을 정해 승인을 받는다.
- [ ] **Step 2:** `SNAPSHOT_RUNTIME_ENABLED` 근처에 `ALERT_FLOW_ENABLED` · `ALERT_INTRADAY_ENABLED`를 승인된 값으로 넣고, 각각 위에 끄는 뜻(그 데이터를 확보하지 못하는 동안 조건을 닫는다)을 한 줄 주석으로 둔다.
- [ ] **Step 3:** `kubectl apply --dry-run=client -f k8s/deployment.yaml` → `configured (dry run)` 또는 `created (dry run)`.
- [ ] **Step 4: Commit** `chore: 알림 데이터 닫힘 스위치 값을 매니페스트에 둔다` — 적용 · 배포는 하지 않는다.

### Task 9: 앱

**Files:** front-end 파일 구조 표, Test `src/__tests__/alertsTab.test.tsx` · `alertDetail.test.tsx` · `alertPresetForm.test.tsx` · `alertComposable.test.tsx` · `alertEditorFlow.test.tsx`

**Interfaces:**
- 타입: `CatalogIndicator` · `CatalogPreset`에 `available: boolean; unavailable_reason: string | null`. `AlertCatalog`에 `cadence_options: { key: Cadence; available: boolean; unavailable_reason: string | null }[]`. `AlertCard` · `AlertDetail`에 `data_closure: { kind: 'AS_CLOSE' | 'HELD'; message: string } | null`.
- `StatusInput`에 `data_closure`. `statusOf`: `ACTIVE`이고 `kind === 'HELD'`면 `{ label: '일시중지', tone: 'muted' }`(결과보다 먼저).
- `Segment`에 `disabled?: boolean`. 비활성 칸은 누를 수 없고 `accessibilityState.disabled`.
- 수정 중 허용 집합: `EditorContext`가 상세에서 연 수정이면 저장된 지표 키들 · `preset_key` · `cadence`를 `kept`로 들고, 닫힌 값이어도 `kept`에 있으면 고를 수 있다.
- `indicatorAvailability`: 기존 사유 판정 뒤, `!available && !kept`면 `{ enabled: false, reason: unavailable_reason }`. `presetAvailability`도 같은 방식.
- 장중 칸: 프리셋 입력 · 조건 만들기의 `INTRADAY`는 `cadence_options`가 닫았고 `kept`가 아니면 비활성, 칸 아래에 사유 한 줄.
- `draft.ts` 프리셋을 고를 때 기본 평가 시점: 프리셋이 `INTRADAY`를 허용하고 `cadence_options`의 `INTRADAY`가 열렸을 때만 `INTRADAY`. 액션을 `{ type: 'preset'; preset; catalog: AlertCatalog }`로 바꾸고 `TriggerStep.tsx`의 호출부도 넘긴다.
- `kept`는 `EditorProvider`가 `initial`(`draftFromDetail` 결과, `alertId != null`일 때)에서 한 번만 만든다: `{ indicators: Set<string>; presetKey: string | null; cadence: Cadence | null }`. 현재 초안에서 만들지 않는다 — 장중을 바꿨다 되돌리는 사이 허용이 사라진다. 생성이면 빈 값.
- 시그니처: `indicatorAvailability(indicator, ctx)`의 `IndicatorContext`에 `kept: Set<string>`, `presetAvailability(preset, instrument, kept: string | null)`, 장중 칸은 `intradayAvailability(catalog, kept: Cadence | null): Availability`(새 함수, `composable.ts`).
- 발화 기준 표기: `RecentEvent`에 `cadence?: Cadence`, 알림 상세 최근 울림은 `event.cadence ?? alert.cadence`로 `basisLabel`을 부른다(울린 알림 상세는 이미 `event.cadence ?? event.alert.cadence`).

- [ ] **Step 1:** 앱 worktree를 최신 `origin/main`에서 만들고 `npm ci`.
- [ ] **Step 2: 실패하는 테스트**
  - `alertsTab` `HELD_카드는_일시중지_배지와_넷째_줄_문구를_보인다` · `AS_CLOSE_카드는_결과_배지_그대로_넷째_줄_문구를_보인다`.
  - `alertDetail` `닫힘_문구_뒤에_다시_제공되면_자동으로_이어져요를_붙인다`.
  - `alertPresetForm` `장중이_닫히면_장중_칸이_비활성이고_사유가_보인다` · `장중이_닫히면_겸용_프리셋의_기본은_종가다`.
  - `alertComposable` `닫힌_수급_지표는_비활성이고_서버_사유를_보인다`.
  - `alertEditorFlow` `수정_중에는_저장된_닫힌_지표와_장중을_고를_수_있다` · `수정_중_장중을_종가로_바꿨다_되돌려도_장중을_고를_수_있다`.
  - `alertDetail` `최근_울림은_발화의_cadence로_기준을_표기한다`.
- [ ] **Step 3:** `npx jest` → 새 테스트 FAIL.
- [ ] **Step 4:** 구현. 기존 픽스처에 새 필드 기본값(`available: true`, `unavailable_reason: null`, `cadence_options` 둘 다 열림, `data_closure: null`)을 채운다.
- [ ] **Step 5:** `npx jest` · `npx tsc --noEmit` → PASS.
- [ ] **Step 6: Commit** `feat: 닫힌 조건을 비활성으로 보이고 일시중지 · 종가 확인 중 알림을 표시한다`

### Task 10: 마무리 확인

- [ ] **Step 1:** 백엔드: 사용자 승인 뒤 `TEST_DB_URL=… ./gradlew test --rerun-tasks` 전체 → BUILD SUCCESSFUL.
- [ ] **Step 2:** 앱: `npx jest` · `npx tsc --noEmit` → PASS.
- [ ] **Step 3:** 코드 리뷰(서브에이전트, 브랜치 전체). 지적 반영.
- [ ] **Step 4:** 머지 요청을 받으면 최신 `origin/main`으로 리베이스하고 V18 충돌을 확인한 뒤 1 · 2를 다시 돈다.
- [ ] **Step 5:** 보고: 바뀐 파일, 테스트 결과, 스위치 이름 · 기본값 · 끄고 켜는 법(`kubectl -n portfolio set env deployment/portfolio-api ALERT_INTRADAY_ENABLED=false`는 승인 뒤에만), 소요를 읽는 명령, 운영 적재 확인 결과, `alert_event.cadence`가 비어 있는 행은 알림의 값으로 읽는다는 것(런북 주입 SQL은 그대로 동작), 영향받는 통합테스트 케이스(N-95 · N-77, 그 밖에 알림 목록 정렬 · 울린 알림 기준 표기 · 카탈로그 응답 · 저장 검증 케이스).
