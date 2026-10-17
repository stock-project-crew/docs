# 수동 동기화 `POST /sync` · `GET /sync/{run_id}` 구현 계획

> **에이전트 작업자에게:** 필수 하위 스킬 — superpowers:subagent-driven-development(권장) 또는 superpowers:executing-plans로 과제 단위로 구현한다. 단계는 체크박스(`- [ ]`)로 추적한다.

**목표:** 인증 주체의 전 계좌 또는 단일 계좌에 `USER` 수집 요청을 넣고 진행 상태(`sync_run`)를 보여주는 `POST /sync` · `GET /sync/{run_id}`, 열린 실행을 닫는 단계, 뷰 응답의 `SYNC_IN_PROGRESS` · `ALREADY_FINAL` notice를 만든다.

**구조:** 새 패키지 `com.stockproject.portfolio.sync`에 규칙(순수 계산) · 매퍼 · 서비스 · 닫기 단계 · 컨트롤러를 둔다. 닫기 단계는 보유 스냅샷 생성기의 회차(`SnapshotJobs.tick`) 끝에 붙는다. 뷰 notice는 기존 `AssemblyContext`의 동기화 자리를 `OpenSync` 하나로 바꿔 채운다.

**기술:** Java 21 · Spring Boot 3.4.5 · MyBatis 애너테이션 매퍼 · Flyway · PostgreSQL 16 · Spring `CronExpression` · JUnit 5 · AssertJ · Mockito · MockMvc

**설계:** [`docs/yhr/specs/portfolio-management/2026-10-17-manual-sync-design.md`](../specs/portfolio-management/2026-10-17-manual-sync-design.md). 계획과 설계가 다르면 설계가 맞다. 둘 다 읽는다.

## 전역 제약

- 작업 위치: worktree `/Users/yhr/Dev/workspace/personal/stock-project/.worktrees/back-end-sync`, 브랜치 `feat/manual-sync`(기준 `origin/main` `b9e7768`). 이 계획의 모든 경로는 이 worktree 기준이다.
- DB를 쓰는 테스트(`@SpringBootTest`, `./gradlew test` 전체 포함)는 실행 전에 사용자에게 묻는다. 로컬 `portfolio_test` DB를 다른 세션과 공유한다. DB를 쓰지 않는 단위 테스트는 묻지 않고 돌린다.
- 커밋은 사용자가 요청할 때만 한다. 메시지는 한국어, 접두는 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝에 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`를 단다.
- 마이그레이션 파일은 `V10__sync_run.sql`이다. 다른 백엔드 세션도 V10을 쓴다. main에 먼저 들어가는 쪽이 V10을 갖고, 나중 쪽이 병합 직전에 번호를 다시 매긴다.
- `RunProcessor` · `Finalizer`의 동작, `CredentialFiller`를 바꾸지 않는다. 기존 코드에서 접근 제한자를 여는 것은 둘뿐이다: `Finalizer.deadline`, `Failures`와 `Failures.describe`(`public`).
- 상태 · 사유 값은 문자열이다(기존 `RunRow.state()`와 같다): 계좌 `RUNNING` · `DONE` · `FAILED` · `REAUTH_REQUIRED`, 실행 `RUNNING` · `PARTIAL` · `DONE` · `FAILED`, 실행 사유 `PICKUP_TIMEOUT`.
- 오류 본문은 `ApiError`(`{"error":{"code","message"}}`)이고 `message`는 고정 문구다. 예외 메시지는 응답에도 로그에도 내보내지 않는다.
- 로그에는 `run_id` · `account_id`와 건수 · 예외 클래스 · SQLState만 쓴다. `account_ref` · `credential_ref`는 쓰지 않는다.
- 응답 필드는 snake_case다. Jackson 전역 설정이 처리하므로 DTO에 애너테이션을 달지 않는다.
- 시간 기준은 Asia/Seoul이다. "지금"은 주입된 `Clock`에서 읽는다(테스트는 `SnapshotTestConfig`의 `MutableClock`). `MutableClock`은 캐시된 컨텍스트에서 테스트끼리 공유되므로, DB 테스트는 매 `@BeforeEach`에서 `clock.set(...)`으로 시각을 직접 맞춘다.
- 구조 검사 테스트(`ArchitectureRulesTest` · `ScopeSignatureTest`)는 `sync` 패키지를 훑지 않는다. `SyncMapper`의 사용자 범위는 각 과제의 "남의 것" 테스트만 지킨다.
- 주석 · 문서는 히스토리 없이 현재 사실만 쓴다. 확인하지 않은 것은 단정하지 않는다.

## 검토 초점

과제의 기본 테스트가 겨누지 않지만 실제 사용에서 먼저 터질 입력과 조건이다. 각 줄의 테스트는 해당 과제에 넣었다.

1. **KST 자정 직후의 요청.** UTC로는 전날이다. `as_of`는 KST 날짜여야 한다 → Task 4 `자정_직후_요청은_KST_날짜로_넣는다`.
2. **본문 없이, `Content-Type` 없이 보낸 `POST /sync`.** 전체 동기화로 받아야 하고 `401` · `415`가 아니어야 한다 → Task 4 `본문과_Content_Type이_없어도_전체_계좌로_받는다`.
3. **이상한 본문(`{"account_id": 123}`, `[]`, `{"account_id": null}`).** 앞의 둘은 `400 INVALID_REQUEST`, 마지막은 전체 동기화다 → Task 4 `account_id가_문자열이_아니면_400` · `account_id가_null이면_전체`.
4. **`credential_ref`가 아직 빈 계좌.** 요청은 받고 행은 `credential_ref` null로 들어가야 한다(`CredentialFiller`가 채운다) → Task 4 `자격증명_참조가_없는_계좌도_받는다`.
5. **요청 뒤 해제한 계좌.** `GET`이 그 계좌 행을 계속 싣고 라벨을 보여줘야 한다 → Task 5 `실행_뒤_해제한_계좌도_싣는다`.

## 파일 구조

| 파일 | 책임 |
|---|---|
| `src/main/resources/db/migration/V10__sync_run.sql` | `sync_run` · `sync_run_account` |
| `sync/SyncProperties.java` | `portfolio.sync.*` 설정 |
| `sync/PickupSchedule.java` | 다음 픽업 시각 |
| `sync/SyncRules.java` · `AccountProgress` · `AccountResult` · `Closing` | 계좌 · 실행 상태 도출, 닫기 판정(순수) |
| `sync/Finality.java` | `already_final` 판정(순수) |
| `sync/SyncMessages.java` | 응답 · notice 문장 |
| `sync/OpenSync.java` | 뷰 notice 재료 |
| `sync/SyncMapper.java` · `SyncTarget` · `SyncRunRow` · `SyncAccountRow` | 쓰기 · 읽기 SQL과 행 |
| `sync/SyncService.java` | 요청 · 조회 · 열린 실행 |
| `sync/SyncCloser.java` | 닫기 단계 |
| `sync/SyncController.java` · `SyncExceptionHandler.java` · `SyncRejected.java` | HTTP와 오류 |
| `sync/dto/SyncAcceptedResponse.java` · `SyncRunResponse.java` · `SyncAccountDto.java` | 응답 본문 |
| 수정: `snapshot/SnapshotJobs.java` · `SnapshotRuntimeConfig.java` · `Finalizer.java` · `Failures.java` | 닫기 단계 연결, `deadline` · `describe` 공개 |
| 수정: `view/assembly/AssemblyContext.java` · `NoticeCollector.java` | `OpenSync` 자리와 두 notice |
| 수정: `view/SnapshotViewService.java` · `AssetChangeViewService.java` · `RealizedPnlViewService.java` | notice 재료 채우기, 빈 봉투 경로 포함 |
| 수정: `application.yaml` | `portfolio.sync` 기본값 |
| 수정(테스트): `AccountFixture` · `SnapshotFixture` · `db/sample/sample_portfolio.sql` | `TRUNCATE` 목록에 새 표 |
| 수정(테스트): `query/SchemaContractTest.java` · `SchemaSmokeTest.java` | 새 표의 계약 |

경로 앞의 `sync/` 등은 `src/main/java/com/stockproject/portfolio/`(테스트는 `src/test/java/com/stockproject/portfolio/`)다.

---

### Task 0: worktree와 기준선

- [ ] **Step 1: 사용자에게 worktree 생성 승인을 받는다** — 경로 `/Users/yhr/Dev/workspace/personal/stock-project/.worktrees/back-end-sync`, 브랜치 `feat/manual-sync`, 기준 `origin/main`.
- [ ] **Step 2: 만든다**

```bash
git -C /Users/yhr/Dev/workspace/personal/stock-project/back-end fetch
git -C /Users/yhr/Dev/workspace/personal/stock-project/back-end worktree add \
  /Users/yhr/Dev/workspace/personal/stock-project/.worktrees/back-end-sync -b feat/manual-sync origin/main
```

Expected: `HEAD is now at b9e7768`(또는 그 뒤의 main). 기준이 `b9e7768`이 아니면 사용자에게 알린다.

- [ ] **Step 3: 컴파일 확인** — `./gradlew compileJava compileTestJava` → `BUILD SUCCESSFUL`. 기준선 전체 테스트는 Task 8에서 묻고 돈다.

---

### Task 1: 마이그레이션과 스키마 계약

**Files:**
- Create: `src/main/resources/db/migration/V10__sync_run.sql`
- Modify: `src/test/java/com/stockproject/portfolio/query/SchemaContractTest.java` · `src/test/java/com/stockproject/portfolio/SchemaSmokeTest.java`
- Modify: `src/test/java/com/stockproject/portfolio/account/AccountFixture.java` · `snapshot/SnapshotFixture.java` · `src/main/resources/db/sample/sample_portfolio.sql`

**Interfaces:**
- Produces: 표 `sync_run`, `sync_run_account` — 컬럼 · CHECK · 인덱스는 설계 §3 그대로.

- [ ] **Step 1: `SchemaContractTest`를 바꾼다**

```java
// 사용자_컬럼은_계좌_알림_기기에만_있다 → 이름과 기대값을 바꾼다
.containsExactly("account", "alert", "push_device", "sync_run");

// 범위_밖_테이블을_만들지_않는다
assertThat(tables).doesNotContain("position_basis").contains("sync_run", "sync_run_account");

@Test
void sync_run_account는_collection_run에_FK를_걸지_않는다() {
    // position_line은_instrument에_FK를_걸지_않는다와 같은 조회
    assertThat(referenced).containsOnly("sync_run", "account");
}
```

`사용자_컬럼...` 테스트의 주석에 `sync_run`이 사용자에게 직접 속하는 이유를 한 줄 더한다: 전체 동기화는 계좌 하나로 정해지지 않는다. `범위_밖...` 주석에서 `sync_run`을 뺀다.

`SchemaSmokeTest.사용자_컬럼은_계좌_알림_기기에만_있다`도 같은 단언이다. 기대값을 `("account", "alert", "push_device", "sync_run")`으로 바꾸고 이름 · 주석을 같은 내용으로 맞춘다.

- [ ] **Step 2: 실패 확인(사용자에게 묻고)** — `./gradlew test --tests '*SchemaContractTest' --tests '*SchemaSmokeTest'` → FAIL(`sync_run` 없음).
- [ ] **Step 3: `V10__sync_run.sql`을 쓴다** — 설계 §3.1 · §3.2의 컬럼 · FK · CHECK와 아래를 넣는다. 각 표와 비자명한 컬럼에 `COMMENT`(V8 양식)를 단다.
  - `CHECK ((state = 'RUNNING') = (finished_at IS NULL))`
  - `CREATE INDEX idx_sync_run_open ON sync_run (user_id, started_at DESC) WHERE finished_at IS NULL;`
  - `CREATE INDEX idx_sync_run_account_collection ON sync_run_account (collection_run_id);`
- [ ] **Step 4: 세 곳의 `TRUNCATE` 목록 앞에 `sync_run_account, sync_run`을 더한다** — `account` · `app_user`를 참조하는 FK 때문에 그대로 두면 `TRUNCATE account`가 실패한다.
- [ ] **Step 5: 통과 확인(사용자에게 묻고)** — `./gradlew test --tests '*SchemaContractTest' --tests '*MigrationLintTest' --tests '*SchemaSmokeTest'` → PASS.
- [ ] **Step 6: 커밋(사용자 요청 시)** — `feat: 동기화 실행 표 sync_run · sync_run_account를 만든다`

---

### Task 2: 상태 도출과 닫기 판정

**Files:**
- Create: `sync/AccountProgress.java` · `AccountResult.java` · `Closing.java` · `SyncRules.java`
- Test: `sync/SyncRulesTest.java`(단위)

**Interfaces:**
- Produces:
  - `record AccountProgress(UUID accountId, String collectionState, String collectionFailureReason, boolean built)` — `collectionState`가 null이면 `collection_run` 행이 없다.
  - `record AccountResult(UUID accountId, String state, String failureReason)`
  - `record Closing(String state, String failureReason, OffsetDateTime finishedAt, List<AccountResult> accounts)`
  - `SyncRules.account(AccountProgress) : AccountResult` — 설계 §4.2 표. `failureReason`은 `FAILED` · `REAUTH_REQUIRED`일 때만 `FailureReasons.sanitize(collectionFailureReason)`, 그 밖은 null.
  - `SyncRules.runState(List<AccountResult>) : String` — `DONE` 수로 `DONE` · `PARTIAL` · `FAILED`.
  - `SyncRules.close(List<AccountProgress>, OffsetDateTime expiresAt, OffsetDateTime now) : Optional<Closing>` — 설계 §5.2 표.
  - `SyncRules.expired(List<AccountProgress>, OffsetDateTime expiresAt, OffsetDateTime now) : Optional<Closing>` — `now ≥ expiresAt`일 때만 값. `close`의 첫 행과 같은 결과.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
static final OffsetDateTime EXPIRES = OffsetDateTime.parse("2026-10-17T14:00:00+09:00");
static final OffsetDateTime BEFORE = EXPIRES.minusMinutes(1);

@Test void 계좌_상태는_수집과_생성기_기록으로_정한다() {
    assertThat(account(p("REQUESTED", null, false)).state()).isEqualTo("RUNNING");
    assertThat(account(p("RUNNING", null, false)).state()).isEqualTo("RUNNING");
    assertThat(account(p("DONE", null, false)).state()).isEqualTo("RUNNING");
    assertThat(account(p("DONE", null, true)).state()).isEqualTo("DONE");
    assertThat(account(p("FAILED", "SOURCE_TIMEOUT", false))).isEqualTo(new AccountResult(A, "FAILED", "SOURCE_TIMEOUT"));
    assertThat(account(p("REAUTH_REQUIRED", "SOURCE_REAUTH", false)).state()).isEqualTo("REAUTH_REQUIRED");
    assertThat(account(p(null, null, false)).state()).isEqualTo("RUNNING");
}
@Test void 코드가_아닌_사유는_UNKNOWN() { /* "KisError: 500" → "UNKNOWN" */ }
@Test void 실행_상태는_DONE_수로_정한다() { /* DONE·DONE→DONE, DONE·FAILED→PARTIAL, FAILED·REAUTH_REQUIRED→FAILED, DONE·REAUTH_REQUIRED→PARTIAL */ }
@Test void 시한_전에_모두_끝나면_지금_닫는다() {
    assertThat(close(List.of(p("DONE", null, true), p("FAILED", "X", false)), EXPIRES, BEFORE))
        .hasValueSatisfying(c -> { assertThat(c.state()).isEqualTo("PARTIAL");
                                   assertThat(c.failureReason()).isNull();
                                   assertThat(c.finishedAt()).isEqualTo(BEFORE); });
}
@Test void 시한_전에_진행_중이면_닫지_않는다() { /* close(...RUNNING..., BEFORE) → empty, expired(..., BEFORE) → empty */ }
@Test void 시한이_지나면_진행_중_계좌를_PICKUP_TIMEOUT으로_닫는다() {
    // DONE(built) + REQUESTED, now = EXPIRES → state PARTIAL, failureReason PICKUP_TIMEOUT, finishedAt EXPIRES,
    // 둘째 계좌 = AccountResult(B, "FAILED", "PICKUP_TIMEOUT"). expired(...)도 같은 값.
}
@Test void 시한이_지난_뒤엔_모두_끝났어도_시한_규칙으로_닫는다() {
    // DONE(built)만, now = EXPIRES.plusHours(1) → state DONE, failureReason null, finishedAt EXPIRES
}
```

- [ ] **Step 2: 실패 확인** — `./gradlew test --tests '*SyncRulesTest'` → 컴파일 실패.
- [ ] **Step 3: 구현한다** — 위 시그니처. `final class`, private 생성자. 사유 문자열은 상수 `PICKUP_TIMEOUT`.
- [ ] **Step 4: 통과 확인** — 같은 명령 → PASS.
- [ ] **Step 5: 커밋(사용자 요청 시)** — `feat: 동기화 실행과 계좌의 상태를 수집 결과로 도출한다`

---

### Task 3: 다음 픽업 · `already_final` · 문장

**Files:**
- Create: `sync/SyncProperties.java` · `PickupSchedule.java` · `Finality.java` · `SyncMessages.java`
- Modify: `snapshot/Finalizer.java`(`deadline`을 `public static`으로), `src/main/resources/application.yaml`
- Test: `sync/PickupScheduleTest.java` · `FinalityTest.java` · `SyncMessagesTest.java`(단위)

**Interfaces:**
- Consumes: `Finalizer.deadline(CalendarDay, LocalTime) : Optional<OffsetDateTime>`, `CalendarDay`(`alert.data`)
- Produces:
  - `@ConfigurationProperties("portfolio.sync") record SyncProperties(@DefaultValue("0 0 23 * * SUN,TUE,WED,THU") String pickupCron, @DefaultValue("PT96H") Duration timeout)` — `@ConfigurationPropertiesScan`이 잡는다. `application.yaml`에 `portfolio.sync` 두 키를 주석과 함께 적는다.
  - `@Component PickupSchedule(SyncProperties)` — `OffsetDateTime nextAfter(OffsetDateTime now)`: `CronExpression.parse(pickupCron).next(now.atZoneSameInstant(Asia/Seoul))`를 `+09:00` 오프셋으로.
  - `record Finality(boolean alreadyFinal, OffsetDateTime finalizedAt)`, `static Finality judge(CalendarDay day, OffsetDateTime snapshotRunFinishedAt, boolean allTargetLinesFinal, OffsetDateTime nextPickup, LocalTime finalizeAt)` — `day`가 null이면 캘린더에 없다. 설계 §5.3 표를 위에서부터 본다.
  - `SyncMessages.accepted(Finality, LocalDate asOf, OffsetDateTime nextPickup) : String`, `inProgress(OffsetDateTime nextPickup) : String`, `alreadyFinal(LocalDate asOf) : String` — 문구는 설계 §4.1 · §4.4. 날짜 `MM-dd`, 픽업 `MM-dd(E) HH:mm`(`Locale.KOREAN`, 요일 한 글자).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
// PickupScheduleTest — 기본 cron
nextAfter("2026-10-13T14:00+09:00") == "2026-10-13T23:00+09:00"   // 화
nextAfter("2026-10-13T23:00+09:00") == "2026-10-14T23:00+09:00"   // 정각은 다음
nextAfter("2026-10-15T23:30+09:00") == "2026-10-18T23:00+09:00"   // 목 → 일
nextAfter("2026-10-12T14:00Z")      == "2026-10-13T23:00+09:00"   // 입력 오프셋과 무관

// FinalityTest — finalizeAt 08:00, 캘린더는 SnapshotFixture와 같은 규칙(주말 · 10-09 휴장)
화 10-13 · 픽업 10-13T23:00 · 확정 없음      → (false, null)
월 10-12 · 픽업 10-13T23:00                 → (true, 2026-10-13T08:00+09:00)
금 10-16 · 픽업 10-18T23:00                 → (false, null)
토 10-17(비영업일)                           → (true, null)
day == null                                  → (true, null)
snapshotRunFinishedAt = 10-14T08:00          → (true, 그 값)
allTargetLinesFinal = true · 화 10-13         → (true, 2026-10-14T08:00+09:00)
nextTradingDay == null · 화 10-13             → (false, null)

// SyncMessagesTest
accepted(new Finality(false, null), 10-13, 10-18T23:00) == "다음 수집(10-18(일) 23:00)에 반영됩니다"
accepted(new Finality(true, 10-13T08:00), 10-12, 10-13T23:00) == "10-12 값은 이미 확정되어 바뀌지 않습니다. 계좌 상태만 다음 수집(10-13(화) 23:00)에 갱신됩니다"
inProgress(10-18T23:00)             == "동기화 요청을 받았습니다 · 다음 수집 10-18(일) 23:00"
alreadyFinal(10-12)                 == "10-12 값은 이미 확정되어 다시 수집해도 바뀌지 않습니다"
```

- [ ] **Step 2: 실패 확인** — `./gradlew test --tests '*PickupScheduleTest' --tests '*FinalityTest' --tests '*SyncMessagesTest'` → 컴파일 실패.
- [ ] **Step 3: 구현한다** — 위 시그니처. `Finalizer.deadline`은 접근 제한자만 바꾼다.
- [ ] **Step 4: 통과 확인** — 같은 명령, 그리고 `--tests '*FinalizerDeadlineTest'` → PASS.
- [ ] **Step 5: 커밋(사용자 요청 시)** — `feat: 다음 픽업 시각과 확정 여부로 동기화 안내 문장을 만든다`

---

### Task 4: `POST /sync`

**Files:**
- Create: `sync/SyncTarget.java` · `SyncMapper.java`(이 과제의 메서드) · `SyncService.java`(`request`) · `SyncRejected.java` · `SyncExceptionHandler.java` · `SyncController.java` · `sync/dto/SyncAcceptedResponse.java`
- Test: `sync/SyncRequestApiTest.java` · `SyncConcurrencyTest.java`(DB) · `SyncExceptionHandlerTest.java`(단위)

**Interfaces:**
- Consumes: Task 3 전부, `PositionWriteMapper.lockUserAccounts(UUID)`, `MarketDataMapper.calendar(String, LocalDate, LocalDate)`, `SnapshotProperties.finalizeAt()`, `Clock`
- Produces:
  - `record SyncTarget(UUID accountId, String accountRef, String linkState, String credentialRef, OffsetDateTime linkedAt)`
  - `SyncMapper`:
    - `List<SyncTarget> targets(UserScope scope)` — 그 사용자의 계좌 전부(해제 포함), `account_id` 순.
    - `UUID openUserRun(String accountRef, LocalDate asOf, OffsetDateTime linkedAt)` — 설계 §4.1 2단계. null 파라미터는 `CAST(#{linkedAt} AS timestamptz) IS NULL`로 비교한다. 없으면 null.
    - `void insertCollectionRun(UUID runId, String accountRef, LocalDate asOf, OffsetDateTime requestedAt, String credentialRef)` — `requested_by = 'USER'`, `state`는 표 기본값에 맡기지 않고 `'REQUESTED'`를 적는다(테스트 미러에는 기본값이 없다).
    - `OffsetDateTime snapshotRunFinishedAt(LocalDate asOf)`
    - `boolean allLinesFinal(List<UUID> accountIds, LocalDate asOf)` — 대상 계좌마다 그날 라인이 있고 모두 `is_final`.
    - `void insertRun(UUID runId, UUID userId, UUID accountId, LocalDate asOf, OffsetDateTime startedAt, boolean alreadyFinal, OffsetDateTime finalizedAt)` — `state = 'RUNNING'`.
    - `void insertRunAccount(UUID syncRunId, UUID accountId, UUID collectionRunId)`
  - `SyncService.request(UserScope scope, Optional<UUID> accountId) : SyncAcceptedResponse` — `@Transactional`. 설계 §4.1 처리 1~5. 잠금 뒤에 `targets`를 읽는다(연동 상태를 잠금 뒤 값으로 본다).
  - `record SyncAcceptedResponse(UUID runId, String message)`
  - `SyncRejected extends RuntimeException` — `HttpStatus status()`, `String code()`, 고정 `message`. 정적 생성자 `forbiddenAccount()`(`403 FORBIDDEN_ACCOUNT`, "요청한 계좌 중 본인 소유가 아닌 것이 있습니다"), `disconnected()`(`409 ACCOUNT_DISCONNECTED`, "연동을 해제한 계좌입니다"), `noAccounts()`(`409 NO_ACCOUNTS`, "동기화할 계좌가 없습니다"), `invalidRequest()`(`400 INVALID_REQUEST`, "요청 형식이 올바르지 않습니다"), `forbiddenRun()`(`403 FORBIDDEN_SYNC_RUN`, "요청한 동기화를 찾을 수 없습니다").
  - `SyncController` `@RequestMapping("/sync")`: `POST` — `@RequestBody(required = false) JsonNode body`. 본문 없음 · `account_id` 없음 · null → 전체. 객체가 아니거나 `account_id`가 문자열이 아니면 `invalidRequest()`. UUID가 아니면 `forbiddenAccount()`. `202`, `Location: /sync/{run_id}`.
  - `SyncExceptionHandler` — `@RestControllerAdvice(assignableTypes = SyncController.class)` `@Order(HIGHEST_PRECEDENCE)`. `SyncRejected`, `HttpMessageNotReadableException` → `invalidRequest`, DB 오류 → `500 INTERNAL_ERROR`(`AccountExceptionHandler`와 같은 방식과 로그).

- [ ] **Step 1: 실패하는 테스트를 쓴다** — `@SpringBootTest @AutoConfigureMockMvc @ActiveProfiles("test") @Import(SnapshotTestConfig.class)`. `SnapshotFixture`로 계좌 · 캘린더(10-01~10-31)를 심고, 로그인은 `AccountApiTest.tokenOf`(private)를 같은 모양으로 옮겨 쓴다(`yhr@a.com` · `jdh@a.com`, `local-dev-password`). `@BeforeEach`에서 `clock.set("2026-10-13T14:00:00+09:00")`(화 14:00 KST).

```java
@Test void 단일_계좌_요청은_202와_USER_행을_만든다() {
    // A(CONNECTED) → 202, Location "/sync/" + run_id, message "다음 수집(10-13(화) 23:00)에 반영됩니다"
    // collection_run: requested_by USER, as_of 2026-10-13, requested_at 지금, credential_ref "/stock-project/accounts/test/ar_a", state REQUESTED
    // sync_run: user_id YHR, account_id A, state RUNNING, as_of 10-13, already_final false; sync_run_account 1행
}
@Test void 전체_요청은_해제한_계좌를_뺀다() { /* A CONNECTED, B DISCONNECTED, C REAUTH_REQUIRED → 대상 A·C, account_id null */ }
@Test void CONNECTING_계좌도_받는다() { }
@Test void 거부_코드와_상태() {
    // JDH 계좌 → 403 FORBIDDEN_ACCOUNT, 없는 UUID → 403, "not-a-uuid" → 403
    // B DISCONNECTED 지정 → 409 ACCOUNT_DISCONNECTED, 계좌가 전부 해제된 사용자의 전체 요청 → 409 NO_ACCOUNTS
    // 거부된 요청은 collection_run · sync_run을 남기지 않는다
}
@Test void 같은_날_다시_요청하면_수집_행을_공유한다() { /* 두 sync_run, 같은 collection_run_id, collection_run 1행 */ }
@Test void 일부만_열려_있을_때_전체_요청은_나머지만_새로_넣는다() { /* A 단일 → 전체: A 공유, C 새 행 */ }
@Test void RUNNING_행은_공유하고_끝난_행은_공유하지_않는다() { /* f.run(..."RUNNING"...) 공유, "DONE" · "FAILED"는 새 행 */ }
@Test void 재연동_전에_생긴_열린_행은_공유하지_않는다() { /* account.linked_at을 그 행 requested_at 뒤로 */ }
@Test void 요청일이_다른_열린_행은_공유하지_않는다() {
    // 목 10-15T23:30 요청 → 금 10-16T10:00 요청: 서로 다른 collection_run, 둘째 as_of 10-16
}
@Test void 그날_스냅샷이_확정됐으면_already_final() { /* snapshot_run 10-13 finished_at 10-13T12:00 → already_final true, finalized_at 그 값 */ }
@Test void 대상_라인이_모두_확정이면_already_final() { /* A · C 10-13 라인 is_final → true, finalized_at 10-14T08:00+09 */ }
@Test void 일부_계좌만_라인이_있으면_already_final이_아니다() { /* A만 10-13 확정 라인 → false, finalized_at null */ }
@Test void 비영업일_요청은_finalized_at_없이_already_final() { /* 토 10-17 → true, finalized_at null */ }
@Test void 확정될_요청은_already_final로_안내한다() {
    // 월 10-12T14:00 → already_final true, finalized_at 10-13T08:00+09,
    // message "10-12 값은 이미 확정되어 바뀌지 않습니다. 계좌 상태만 다음 수집(10-13(화) 23:00)에 갱신됩니다"
}
@Test void 자정_직후_요청은_KST_날짜로_넣는다() { /* 시계 2026-10-13T00:10:00+09:00 → as_of 2026-10-13 */ }
@Test void 자정_직전_요청은_그날로_넣는다() { /* 시계 2026-10-13T23:50:00+09:00 → as_of 2026-10-13, 다음 픽업 10-14(수) 23:00 */ }
@Test void 본문과_Content_Type이_없어도_전체_계좌로_받는다() { /* post("/sync") + 토큰만 → 202 */ }
@Test void account_id가_null이면_전체() { }
@Test void account_id가_문자열이_아니면_400() { /* {"account_id":123} · [] · "{" → 400 INVALID_REQUEST */ }
@Test void 자격증명_참조가_없는_계좌도_받는다() { /* account.credential_ref = NULL → 202, 행 credential_ref null */ }
@Test void 토큰이_없으면_401() { }
@Test void 로그에_계좌_참조와_자격증명_참조가_없다(CapturedOutput output) {
    // 성공 · 거부 요청을 거친 뒤
    // output에 "ar_a" · "/stock-project/accounts/"가 없다. 클래스에 @ExtendWith(OutputCaptureExtension.class)
}
```

`SyncExceptionHandlerTest`(단위, `AccountExceptionHandlerTest`와 같은 방식): DB 예외 → `500 INTERNAL_ERROR`, 고정 문구, 응답 · 로그에 예외 메시지 없음.

`SyncConcurrencyTest`: 같은 사용자 `SyncService.request(scope, Optional.empty())`를 두 스레드에서 동시에 부른다(`SnapshotConcurrencyTest`의 방식). 결과: `sync_run` 2행, 계좌마다 열린 `USER` `collection_run` 1행.

- [ ] **Step 2: 실패 확인** — 단위: `./gradlew test --tests '*SyncExceptionHandlerTest'` → 컴파일 실패. DB(사용자에게 묻고): `--tests '*SyncRequestApiTest' --tests '*SyncConcurrencyTest'`.
- [ ] **Step 3: 매퍼 · 서비스 · 예외 · 처리기 · 컨트롤러를 구현한다** — 위 시그니처. 요청일 · 지금은 `OffsetDateTime.now(clock)`을 Asia/Seoul로 바꿔 얻는다. 다음 픽업은 `PickupSchedule.nextAfter(지금)`, 판정은 `Finality.judge(calendar 그날 행 또는 null, snapshotRunFinishedAt, allLinesFinal(대상), 다음 픽업, finalizeAt)`.
- [ ] **Step 4: 통과 확인** — 같은 명령들(DB는 사용자에게 묻고) → PASS.
- [ ] **Step 5: 커밋(사용자 요청 시)** — `feat: 수동 동기화 요청 POST /sync를 받는다`

---

### Task 5: `GET /sync/{run_id}`

**Files:**
- Create: `sync/SyncRunRow.java` · `SyncAccountRow.java` · `sync/dto/SyncRunResponse.java` · `SyncAccountDto.java`
- Modify: `sync/SyncMapper.java` · `SyncService.java` · `SyncController.java`
- Test: `sync/SyncRunApiTest.java`(DB)

**Interfaces:**
- Consumes: Task 2 `SyncRules`, `SyncProperties.timeout()`, `SnapshotCalendarRepository.latestAsOf(UserScope)`, `SnapshotFactsMapper.accountFreshness(UserScope, LocalDate)`
- Produces:
  - `record SyncRunRow(UUID runId, UUID userId, LocalDate asOf, OffsetDateTime startedAt, OffsetDateTime finishedAt, String state, String failureReason, boolean alreadyFinal, OffsetDateTime finalizedAt)`
  - `record SyncAccountRow(UUID accountId, String label, String collectionState, String collectionFailureReason, boolean built, String finalState, LocalDate finalAsOf, String finalFailureReason)` — `built`는 `position_build.run_id = collection_run_id`인 행이 있는가.
  - `SyncMapper.findRun(UserScope scope, UUID runId) : SyncRunRow` — 남의 것은 null.
  - `SyncMapper.accounts(UUID syncRunId) : List<SyncAccountRow>` — `account_id` 순, `collection_run` LEFT JOIN.
  - `SyncService.find(UserScope scope, UUID runId) : SyncRunResponse` — 없으면 `SyncRejected.forbiddenRun()`. 닫힌 실행은 `final_*`, 열린 실행은 `SyncRules.account` + 계좌 `as_of`(사용자 최신 `as_of`의 `accountFreshness`), 시한이 지난 열린 실행은 `SyncRules.expired`의 결과를 싣는다(설계 §4.2).
  - `SyncService.progress(List<SyncAccountRow>) : List<AccountProgress>` — 닫기 단계도 쓴다(패키지 공개).
  - `record SyncRunResponse(UUID runId, String state, OffsetDateTime startedAt, OffsetDateTime finishedAt, String failureReason, List<SyncAccountDto> accounts)`
  - `record SyncAccountDto(UUID accountId, String label, String state, LocalDate asOf, String failureReason)`
  - `SyncController` `GET /{runId}` — `@PathVariable String runId`. UUID가 아니면 `forbiddenRun()`.

- [ ] **Step 1: 실패하는 테스트를 쓴다** — Task 4와 같은 구성. 요청은 `POST /sync`로 만들고, 수집 진행은 `SnapshotFixture.sql`로 `collection_run`을 갱신해 흉내 낸다. 생성기 처리는 `RunProcessor.processOnce()`를 직접 부른다.

```java
@Test void 열린_실행은_스펙_모양으로_싣는다() {
    // 키: run_id, state RUNNING, started_at, finished_at null, failure_reason null,
    //     accounts[0]: account_id, label "ar_a", state RUNNING, as_of null(라인 없음), failure_reason null
}
@Test void 수집_DONE은_생성기_기록이_생겨야_DONE() {
    // collection_run DONE + silver_synced_at + cln_deposit → 처리 전 RUNNING, processOnce() 뒤 DONE, as_of 2026-10-13
}
@Test void 실패_계좌는_이월된_기준일과_사유를_싣는다() {
    // A 10-12 확정 라인이 있고 10-13 FAILED(SOURCE_TIMEOUT) → processOnce() 뒤 GET: state FAILED, failure_reason SOURCE_TIMEOUT,
    // as_of 2026-10-12 — 10-13 라인이 생기지 않아 사용자 최신 as_of가 10-12이고, 그날 A의 source_as_of 날짜다
}
@Test void 코드가_아닌_사유는_UNKNOWN() { }
@Test void 시한이_지난_열린_실행은_닫힌_것처럼_싣는다() {
    // 시계를 started_at + 96h로 → state FAILED, failure_reason PICKUP_TIMEOUT, finished_at = started_at + 96h,
    // 계좌 FAILED/PICKUP_TIMEOUT. sync_run 행은 여전히 RUNNING(저장하지 않는다).
}
@Test void 남의_실행_없는_실행_UUID_아님은_403() { /* FORBIDDEN_SYNC_RUN 세 경우 */ }
@Test void 실행_뒤_해제한_계좌도_싣는다() { /* POST → DELETE /accounts/{A} 대신 link_state DISCONNECTED로 갱신 → accounts에 A, label 유지 */ }
```

- [ ] **Step 2: 실패 확인(사용자에게 묻고)** — `./gradlew test --tests '*SyncRunApiTest'` → FAIL.
- [ ] **Step 3: 구현한다** — 위 시그니처.
- [ ] **Step 4: 통과 확인(사용자에게 묻고)** — 같은 명령 → PASS.
- [ ] **Step 5: 커밋(사용자 요청 시)** — `feat: 동기화 진행 상태 GET /sync/{run_id}를 연다`

---

### Task 6: 닫기 단계

**Files:**
- Create: `sync/SyncCloser.java`
- Modify: `sync/SyncMapper.java` · `snapshot/SnapshotJobs.java` · `snapshot/SnapshotRuntimeConfig.java` · `snapshot/Failures.java`(클래스와 `describe`를 `public`으로)
- Test: `sync/SyncCloserTest.java`(DB) · 수정 `snapshot/SnapshotJobsTest.java` · `snapshot/SnapshotRuntimeConfigTest.java`(둘 다 단위)

**Interfaces:**
- Consumes: Task 2 `SyncRules.close`, Task 5 `SyncMapper.accounts` · `SyncService.progress`, `SnapshotProperties.batchSize()`, `SyncProperties.timeout()`
- Produces:
  - `SyncMapper.openRunIds(int limit) : List<UUID>` — `finished_at IS NULL`, `started_at` 순. 잠그지 않는다.
  - `SyncMapper.lockRun(UUID runId) : SyncRunRow` — `WHERE run_id = #{runId} AND finished_at IS NULL FOR UPDATE SKIP LOCKED`. 잠그지 못했거나 이미 닫혔으면 null.
  - `SyncMapper.closeRun(UUID runId, String state, String failureReason, OffsetDateTime finishedAt) : int` — `WHERE finished_at IS NULL`. 바뀐 행 수.
  - `SyncMapper.closeAccount(UUID syncRunId, UUID accountId, String finalState, LocalDate finalAsOf, String finalFailureReason)`
  - `@Component SyncCloser` — `int closeOnce()`: `openRunIds(batchSize)`를 트랜잭션 밖에서 읽고, id마다 `TransactionTemplate` 하나에서 `lockRun` → null이면 건너뜀 → `accounts` · `SyncRules.close` → `closeAccount` · `closeRun`. 반환값은 `closeRun`이 1을 돌려준 수의 합(기존 `Finalizer`의 대상 읽기 · 계좌별 재잠금과 같은 구조). 실패는 `Failures.describe`로 경고 로그 후 다음 실행. `final_as_of`는 Task 5와 같은 기준일 조회.
  - `SnapshotJobs(CredentialFiller, RunProcessor, Finalizer, SyncCloser)` — `tick()`의 넷째 단계 `stage("동기화 닫기", closer::closeOnce)`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
// SyncCloserTest (@SpringBootTest, SnapshotTestConfig)
@Test void 모두_끝나면_닫고_계좌_결과를_굳힌다() {
    // A DONE(생성기 처리), C FAILED → closeOnce() == 1 → sync_run PARTIAL, finished_at 지금,
    // sync_run_account A(DONE, as_of 10-13, null), C(FAILED, 이월 기준일, 사유)
}
@Test void 전부_실패하면_FAILED() { }
@Test void FINAL_EXISTS로_끝난_계좌도_DONE() { /* 같은 날 SCHEDULE 확정 뒤 USER DONE → processOnce() → DONE */ }
@Test void 재시도_사유로_기록된_계좌도_DONE() { /* 예금 없는 USER DONE → processOnce() → position_build NO_BALANCE → closeOnce() 뒤 계좌 DONE */ }
@Test void 진행_중이면_닫지_않는다() { /* closeOnce() == 0, sync_run RUNNING */ }
@Test void 시한이_지나면_PICKUP_TIMEOUT으로_닫는다() {
    // 시계 started_at + 96h → FAILED, PICKUP_TIMEOUT, finished_at = started_at + 96h
}
@Test void 닫힌_뒤_수집이_끝나도_응답이_바뀌지_않는다() {
    // 시한으로 닫음 → collection_run DONE + processOnce() → SyncService.find의 state · 계좌 행 불변
}
@Test void 읽는_쪽_시한_응답과_저장_결과가_같다() {
    // 시한 뒤 find() 결과의 state · finished_at · failure_reason · 계좌 state · failure_reason == closeOnce() 뒤 find()
}
@Test void 두_단계가_동시에_돌아도_한_번만_닫는다() { /* closeOnce() 두 스레드 → 합 1 */ }

// SnapshotJobsTest — 생성자에 SyncCloser mock 추가
@Test void 확정이_실패해도_동기화_닫기는_돈다() { doThrow(...).when(finalizer).finalizeOnce(); jobs.tick(); verify(closer).closeOnce(); }
@Test void 네_단계를_순서대로_돈다() { /* InOrder: filler → processor → finalizer → closer */ }
// 기존 두 테스트에 verify(closer).closeOnce()를 더한다

// SnapshotRuntimeConfigTest — runner에 .withBean(SyncCloser.class, () -> mock(SyncCloser.class))를 더한다.
// 기존 기본은_꺼져_있다가 "스위치가 꺼져 있으면 닫기 단계도 돌지 않는다"를 덮는다(닫기는 SnapshotJobs 안에서만 돈다).
```

- [ ] **Step 2: 실패 확인** — 단위: `./gradlew test --tests '*SnapshotJobsTest' --tests '*SnapshotRuntimeConfigTest'` → 컴파일 실패. DB(사용자에게 묻고): `--tests '*SyncCloserTest'`.
- [ ] **Step 3: 구현한다** — 위 시그니처.
- [ ] **Step 4: 통과 확인** — 같은 명령들 → PASS.
- [ ] **Step 5: 커밋(사용자 요청 시)** — `feat: 생성기 회차 끝에 끝난 동기화를 닫는다`

---

### Task 7: 뷰 notice

**Files:**
- Create: `sync/OpenSync.java`
- Modify: `sync/SyncMapper.java` · `SyncService.java` · `view/assembly/AssemblyContext.java` · `NoticeCollector.java` · `view/SnapshotViewService.java` · `AssetChangeViewService.java` · `RealizedPnlViewService.java`
- Test: 수정 `view/assembly/NoticeCollectorTest.java`(단위) · 새 `sync/SyncNoticeApiTest.java`(DB)

**Interfaces:**
- Consumes: Task 3 `SyncMessages` · `PickupSchedule`, `SyncProperties.timeout()`
- Produces:
  - `record OpenSync(UUID syncRunId, OffsetDateTime nextPickupAt, LocalDate asOf, boolean alreadyFinal, OffsetDateTime finalizedAt)`
  - `SyncMapper.latestOpen(UserScope scope, OffsetDateTime startedAfter) : SyncRunRow` — `finished_at IS NULL AND started_at > startedAfter`, `started_at DESC` 첫 행.
  - `SyncService.openSync(UserScope scope) : Optional<OpenSync>` — `startedAfter = 지금 − timeout`, `nextPickupAt = PickupSchedule.nextAfter(지금)`.
  - `AssemblyContext` — 컴포넌트 `String syncRunId`와 `OffsetDateTime finalizedAt`을 `OpenSync openSync` 하나로 바꾸고 `Builder.openSync(OpenSync)`를 더한다.
  - `NoticeCollector` — `SYNC_IN_PROGRESS`: `openSync`가 있으면 `SyncMessages.inProgress`, `params("sync_run_id", id, "next_pickup_at", t)`. `ALREADY_FINAL`: `openSync.alreadyFinal()`이면 `SyncMessages.alreadyFinal`, `params("as_of", d, "finalized_at", t)`(null 가능). 주석 "아래 넷은 아직 재료가 없다"를 남은 둘(`CA_UNKNOWN` · `PRICE_LAG_MARKET`)로 고친다.
  - 세 뷰 서비스 — 생성자에 `SyncService`를 받고, 컨텍스트에 `.openSync(sync.openSync(scope).orElse(null))`. 스냅샷 · 자산 변화의 `emptyEnvelope`는 `notices.collect(AssemblyContext.builder(null).openSync(...).build())`를 싣는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
// NoticeCollectorTest
@Test void 열린_동기화는_SYNC_IN_PROGRESS를_싣는다() {
    // openSync(id, 10-18T23:00+09, 10-13, false, null) → code SYNC_IN_PROGRESS, severity info,
    // message "동기화 요청을 받았습니다 · 다음 수집 10-18(일) 23:00", params {sync_run_id, next_pickup_at}; ALREADY_FINAL 없음
}
@Test void 확정될_요청은_ALREADY_FINAL을_함께_싣는다() {
    // alreadyFinal true, finalizedAt 10-13T08:00 → 두 코드가 선언 순서(SYNC_IN_PROGRESS, ALREADY_FINAL)로,
    // ALREADY_FINAL message "10-12 값은 이미 확정되어 다시 수집해도 바뀌지 않습니다", params {as_of, finalized_at}
}
@Test void 비영업일_요청은_finalized_at이_null() { }
@Test void 동기화가_없으면_둘_다_없다() { }

// SyncNoticeApiTest — SnapshotViewApiTest가 쓰는 6개 경로와 쿼리 그대로
@Test void 열린_실행이_있으면_여섯_뷰_모두_싣는다() { /* POST /sync 뒤 각 뷰 notices에 SYNC_IN_PROGRESS, params.sync_run_id == run_id */ }
@Test void 여럿이면_가장_늦은_실행() { }
@Test void 확정될_요청이면_ALREADY_FINAL도_싣는다() { /* 시계 월 10-12T14:00 → POST → 요약 notices에 SYNC_IN_PROGRESS · ALREADY_FINAL 순서, params.finalized_at 10-13T08:00+09 */ }
@Test void 스냅샷이_없는_사용자의_빈_봉투에도_싣는다() { /* 라인 없음 → summary · asset-change notices에 SYNC_IN_PROGRESS, empty_reason 유지 */ }
@Test void 닫힌_실행이나_시한이_지난_실행만_있으면_없다() { }
@Test void 남의_실행은_보지_않는다() { /* JDH의 열린 실행 → YHR 뷰에 없음 */ }
```

- [ ] **Step 2: 실패 확인** — 단위: `./gradlew test --tests '*NoticeCollectorTest'`. DB(사용자에게 묻고): `--tests '*SyncNoticeApiTest'`.
- [ ] **Step 3: 구현한다** — 위 시그니처.
- [ ] **Step 4: 통과 확인** — 같은 명령들, 그리고 응답 비교 테스트(`SixViewGoldenTest` · `SnapshotViewApiTest` · `AssetChangeApiTest` · `RealizedPnlApiTest`, 사용자에게 묻고) → PASS. 열린 실행이 없으면 응답이 그대로여야 한다.
- [ ] **Step 5: 커밋(사용자 요청 시)** — `feat: 동기화 중 · 이미 확정 안내를 뷰 응답에 싣는다`

---

### Task 8: 전체 테스트와 마무리

- [ ] **Step 1: 사용자에게 묻고 전체 테스트** — `./gradlew test` → `BUILD SUCCESSFUL`. `ArchitectureRulesTest` · `ScopeSignatureTest`도 함께 돈다(둘 다 `sync` 패키지는 검사하지 않는다). 실패하면 출력 그대로 보고한다.
- [ ] **Step 2: 마이그레이션 번호 확인** — `git fetch` 후 `origin/main`에 `V10__`가 이미 있으면 사용자에게 알리고 번호를 다시 매긴다.
- [ ] **Step 3: 커밋 · 푸시 · PR은 사용자가 요청할 때만** 한다. 운영 반영 전제(생성기 스위치 `SNAPSHOT_RUNTIME_ENABLED`가 꺼져 있으면 닫기 단계도 돌지 않는다)는 설계 §2.3에 있다 — PR 본문에 그 사실을 적는다.
