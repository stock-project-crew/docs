# 인증 정보 갱신 · 수집 안내 백엔드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 연동한 KIS 계좌의 앱키 · 시크릿을 계좌번호 입력 없이 갱신하는 `PUT /accounts/{id}/credentials`와, 수집 결과에서 계산하는 수집 안내(`collection_alert` · 계좌별 뷰 notice 셋)를 만든다.

**Architecture:** 계좌번호는 앱키와 따로, 백엔드만 읽는 SSM 값(`/stock-project/account-numbers/<account_ref>`)에 둔다. 갱신은 계좌 행을 잠근 채 그 값을 읽어 수집용 값을 통째로 다시 쓰고 `linked_at`을 옮긴다. 수집 안내는 `CollectionAlertPort` 하나가 사용자 단위 쿼리 한 번으로 판정하고, `GET /accounts`와 계좌별 뷰(행 · notice)가 같은 값을 쓴다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · MyBatis · Flyway · PostgreSQL 16 · AWS SDK v2 `ssm` · JUnit 5 · AssertJ · Mockito

**Spec:** [등록 · 해제 · 인증 정보 갱신 API 설계](../specs/portfolio-management/2026-10-16-account-link-api-design.md) — 이 계획의 §번호는 그 문서의 절이다. 상위 근거는 [포트폴리오 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) §7.1 · §7.2 · §7.5 · §8.2 · §8.5. 이 기능이 걸친 절은 API 설계 §2.3 · §3.3 · §3.5 · §3.6 · §3.7 · §4.1 · §4.2 · §4.4 · §5 · §6.1 · §6.3 · §7 · §8 · §10이다.

## Global Constraints

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어. 커밋 접두어 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **커밋 · 푸시는 사용자가 요청할 때만 한다.** 각 태스크의 커밋 단계는 요청을 받은 뒤 실행한다.
- 주석은 히스토리 없이 최신 사실만 쓰고, 문서 절 번호(§ · SG-)를 지칭하지 않고 주석만으로 이해되게 쓴다. 검증하지 않은 것은 단정하지 않는다.
- 운영 DB에 쓰지 않는다. 스펙 · 설계를 고치지 않는다. 구현 중 설계와 코드가 어긋나면 멈추고 보고한다.
- **갱신 API의 응답 모양(`204` · 오류 코드)과 `collection_alert` · notice 셋의 모양은 앱 세션이 픽스처로 쓰고 있다.** 바꿔야 하면 멈추고 보고한다.
- 계좌 상태에 재인증 상태를 더하지 않는다. 갱신 때 KIS를 부르지 않는다. 백엔드가 수집용 값(`/stock-project/accounts/*`)을 읽는 코드를 두지 않는다.
- 앱키 · 시크릿 · 계좌번호 원문을 응답 · 로그 · 예외 메시지에 내지 않는다. 테스트는 `test-app-key` · `test-app-secret` · `00000000-01` 꼴의 가짜 값만 쓴다.
- 마이그레이션 번호는 `V22`(`db/migration`). `db/external`도 같은 번호 체계를 쓴다. 병합 직전 origin/main에 V22가 생겼으면 다음 빈 번호로 옮기고 전용 DB를 새로 만들어 다시 테스트한다(DB를 지우거나 만드는 일은 승인).
- DB를 쓰는 테스트는 전용 DB에서만 돈다: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_credential?currentSchema=app,data' ./gradlew test --rerun-tasks`(특정 클래스는 `--tests '<FQCN>'` 추가). 공유 `portfolio_test`에서 돌리지 않는다. DB 테스트는 돌리기 전에 사용자에게 묻는다. DB 없는 단위 테스트는 묻지 않는다.
- 테스트 메서드 이름은 기존처럼 한국어 문장.
- **IAM 정책 변경과 운영자 스크립트 실행은 이 계획에서 적용하지 않는다.** 바꿀 정책 내용과 스크립트를 만들어 보고하고, 적용은 따로 승인을 받는다(§7 켜는 순서: IAM → 배포 → 스크립트).
- `NoticeCollector` · `NoticeCode`는 "미국 종목의 가격 기준일 안내(`PRICE_LAG_MARKET`)" 작업과 같이 고친다. 나중에 머지하는 쪽이 최신 origin/main에 맞춰 리베이스한다.

## Review Focus

1. **갱신이 다른 계좌의 계좌번호로 수집용 값을 쓰지 않는다** — 읽은 계좌번호의 `account_ref`가 행과 다르면 쓰지 않고 `409`. → Task 5 `다른_계좌의_계좌_정보_값이면_쓰지_않는다`.
2. **인증 실패가 뒤의 다른 실패에 가려지지 않는다** — 같은 날 인증 실패 뒤에 `SOURCE_UNREACHABLE`로 끝난 실행이 있어도 `CREDENTIAL_INVALID`. → Task 6 `인증_실패_뒤의_다른_실패가_안내를_가리지_않는다`.
3. **한 밤의 장애가 여러 날로 세지지 않는다** — 토 · 일 `as_of`의 동기화 실패는 세지 않는다. → Task 6 `비영업일_기준일은_세지_않는다`.
4. **동기화를 눌러도 연속 실패 일수가 줄지 않는다** — 열린 실행은 보지 않는다. → Task 6 `열린_실행은_일수를_줄이지_않는다`.
5. **갱신 직후 판정** — `CONNECTED`면 `CREDENTIAL_UPDATED`, `CONNECTING`이면 안내 없음, 갱신 전 실패는 `last_collection`에서 빠진다. → Task 5 · Task 7.
6. **누출** — 갱신의 성공 · 409 · 503 경로 로그와 응답에 가짜 키 · 계좌번호 원문이 없다. → Task 5 `갱신_경로에_입력값이_새지_않는다`.

---

## 파일 구조

**back-end** (`.worktrees/back-end-credential-refresh`, 브랜치 `feat/credential-refresh`). 경로 접두 `src/main/java/com/stockproject/portfolio/`는 줄인다.

| 파일 | 책임 |
|---|---|
| `src/main/resources/db/migration/V22__account_number_masked.sql` | `account.account_number_masked` 컬럼, `linked_at` 주석 |
| `account/KisAccountNumber.java` | `masked()` — `****5678-01` |
| `account/AccountRefIssuer.java` | `accountNumberName(accountRef)` |
| `account/KisCredential.java` | `env`를 비울 수 있게 |
| `account/CredentialStore.java` · `SsmCredentialStore.java` · `InMemoryCredentialStore.java` | 계좌 정보 값 쓰기 · 읽기 · 지우기 |
| `account/AccountLinkService.java` · `AccountLinkMapper.java` · `AccountController.java` | 등록 · 해제가 계좌 정보 값을 함께 다룸, 갱신 흐름 |
| `account/RefreshCommand.java` · `account/dto/RefreshCredentialsRequest.java` | 갱신 요청 검사 |
| `account/AccountRejected.java` | `disconnected()` · `accountNumberUnavailable()` |
| `account/AccountNumberMaskFiller.java` | 가린 계좌번호 채우기 잡 |
| `account/dto/AccountDto.java` | `account_number_masked` · `collection_alert` |
| `query/CredentialFailureReasons.java` | 인증 실패 코드 목록 |
| `query/CollectionAlert.java` · `CollectionAlertMapper.java` · `CollectionAlertPort.java` · `CollectionAlertJudge.java` | 수집 안내 판정 |
| `sync/PickupSchedule.java` | `nextAfterLinked(linkedAt, now)` |
| `view/SnapshotViewService.java` · `catalog/Catalog.java` | 계좌별 뷰 행에 `collection_alert` |
| `view/assembly/NoticeCode.java` · `NoticeCollector.java` · `AssemblyContext.java` | notice 셋 |
| `scripts/ops/backfill-account-numbers.sh` | 운영자 스크립트 |
| `docs/ops/account-credentials.md` | IAM 정책 · 켜는 순서 · 스크립트 사용법 |

---

### Task 0: 작업 공간과 전용 DB

**Files:** 없음(머신 상태 변경)

- [ ] **Step 1: 아래 명령을 사용자에게 보여 주고 승인받은 뒤 실행한다.**

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project
git -C back-end fetch origin
git -C back-end worktree add -b feat/credential-refresh ../.worktrees/back-end-credential-refresh origin/main
```

- [ ] **Step 2: 전용 DB를 만든다(같은 승인에 포함해 묻는다).** 로컬 Postgres 컨테이너에서 `CREATE DATABASE portfolio_test_credential OWNER portfolio`, 그 안에 `app` · `data` 스키마를 기존 테스트 DB와 같은 방법(`docs/yhr/plan/2026-10-14-test-environment-setup.md`)으로 만든다.
- [ ] **Step 3: 기준선.** Global Constraints의 테스트 명령(DB 테스트 승인 후). Expected: 전부 통과.

---

### Task 1: V22 마이그레이션

**Files:**
- Create: `src/main/resources/db/migration/V22__account_number_masked.sql`
- Test: 기존 마이그레이션 검사 테스트가 있으면 거기에, 없으면 `account/AccountApiTest`의 첫 사례로 컬럼 존재를 본다

- [ ] **Step 1: 실패하는 테스트.** `account_number_masked` 컬럼을 읽는 쿼리가 실패하는 것을 확인한다.
- [ ] **Step 2: 마이그레이션.**

```sql
ALTER TABLE account ADD COLUMN account_number_masked text;
COMMENT ON COLUMN account.account_number_masked IS
  '화면에 보이는 가린 계좌번호(****5678-01). 원문은 SSM 계좌 정보 값에만 있다';
COMMENT ON COLUMN account.linked_at IS
  '지금 자격증명으로 수집을 시작한 시각(등록 · 재연동 · 인증 정보 갱신). 그 전에 요청된 collection_run은 최근 수집과 수집 안내에 세지 않는다';
```

- [ ] **Step 3: 통과 확인(DB 테스트 승인 후).**
- [ ] **Step 4: 커밋(요청 시).** `feat: 가린 계좌번호 컬럼을 더하고 linked_at의 뜻을 주석에 적는다`

---

### Task 2: 가린 계좌번호와 계좌 정보 값 이름

**Files:**
- Modify: `account/KisAccountNumber.java` · `account/AccountRefIssuer.java`
- Test: `account/KisAccountNumberTest.java` · `account/AccountRefIssuerTest.java`

- [ ] **Step 1: 실패하는 단위 테스트.**

```java
@Test
void 앞_네자리를_가린다() {
    KisAccountNumber n = KisAccountNumber.parse("00005678-01");
    assertThat(n.masked()).isEqualTo("****5678-01");
    assertThat(n.masked()).doesNotContain("0000");
}

@Test
void 계좌_정보_값_이름은_수집용_값과_다른_경로다() {
    assertThat(AccountRefIssuer.accountNumberName("ar_x")).isEqualTo("/stock-project/account-numbers/ar_x");
    assertThat(AccountRefIssuer.accountNumberName("ar_x")).doesNotStartWith("/stock-project/accounts/");
}
```

(`KisAccountNumber`의 기존 정적 팩터리 이름이 다르면 그것을 쓴다.)

- [ ] **Step 2: 실패 확인 → 구현 → 통과 확인.** 실패 확인: `./gradlew test --tests '*KisAccountNumberTest' --tests '*AccountRefIssuerTest'`(DB 없음). 구현: `masked()`는 `"****" + digits.substring(4, 8) + "-" + digits.substring(8)`. 주석은 "앞 4자리를 가린다. 비밀이 아니라 DB · 응답에 둘 수 있다".
- [ ] **Step 3: 커밋(요청 시).** `feat: 가린 계좌번호와 계좌 정보 값 이름을 만든다`

---

### Task 3: 저장소의 계좌 정보 값

**Files:**
- Modify: `account/CredentialStore.java` · `account/SsmCredentialStore.java` · `account/InMemoryCredentialStore.java` · `account/KisCredential.java`
- Test: `account/SsmCredentialStoreTest.java`

**Interfaces:**
- Produces: `CredentialStore.putAccountNumber(String name, KisAccountNumber number)` · `Optional<KisAccountNumber> readAccountNumber(String name)` · `deleteAccountNumber(String name)`. `KisCredential.env()`는 `null`일 수 있다.

- [ ] **Step 1: 실패하는 단위 테스트(`SsmClient` 목).**
  - `put`에 `env`가 `null`이면 값 JSON에 `env` 키가 없다.
  - `putAccountNumber`가 `SecureString` · `Overwrite` · 값 JSON 키 둘(`cano` · `acnt_prdt_cd`)로 부른다.
  - `readAccountNumber`가 `WithDecryption=true`로 부르고 값을 돌려준다. `ParameterNotFoundException` → empty. 키가 빠졌거나 계좌번호 규칙에 맞지 않는 값 → empty. 그 밖의 `SdkException` → `CredentialStoreUnavailable`.
  - `deleteAccountNumber`의 `ParameterNotFoundException`은 성공.
  - 예외 메시지 · `toString`에 값이 없다.
- [ ] **Step 2: 실패 확인 → 구현 → 통과 확인(DB 없음).** `InMemoryCredentialStore`는 이름 → 계좌번호 맵을 따로 두고, 테스트가 쓰는 대기 훅이 있으면 새 메서드에도 같은 방식으로 건다. 수집용 값을 읽는 메서드는 두지 않는다. 인터페이스 주석: "백엔드는 수집용 값을 쓰고 지우기만 하고, 계좌 정보 값만 읽는다".
- [ ] **Step 3: 커밋(요청 시).** `feat: 저장소가 계좌 정보 값을 쓰고 읽고 지운다`

---

### Task 4: 등록 · 재연동 · 해제가 계좌 정보 값을 함께 다룬다

**Files:**
- Modify: `account/AccountLinkService.java` · `account/AccountLinkMapper.java`
- Test: `account/AccountApiTest.java` · `account/AccountLinkServiceTest.java` · `account/AccountUnlinkServiceTest.java`

- [ ] **Step 1: 실패하는 통합 테스트(DB 승인 후).**
  - 신규 등록 뒤 저장소에 계좌 정보 값이 있고 행의 `account_number_masked`가 `****5678-01` 꼴이다.
  - 재연동 뒤 같다.
  - 등록 중 계좌 정보 값 쓰기가 실패하면 `503` · 행 없음 · 수집용 값도 쓰지 않는다.
  - 해제 뒤 두 값이 모두 없다. 계좌 정보 값 지우기가 실패하면 `503` · 행은 연동 상태 그대로.
- [ ] **Step 2: 구현.** 등록은 계좌 정보 값 → 수집용 값 순서로 쓴다(§4.1의 4). `insertIfAbsent` · `relink`가 `account_number_masked`를 쓴다. 해제는 수집용 값 → 계좌 정보 값 순서로 지운다(§4.2의 4). 로그 관례(`account_id` · 예외 종류 · AWS 코드만)를 그대로 따른다.
- [ ] **Step 3: 통과 확인(DB 승인 후).** `--tests 'com.stockproject.portfolio.account.*'`.
- [ ] **Step 4: 커밋(요청 시).** `feat: 등록 · 해제가 계좌 정보 값과 가린 계좌번호를 함께 다룬다`

---

### Task 5: 갱신 API

**Files:**
- Create: `account/RefreshCommand.java` · `account/dto/RefreshCredentialsRequest.java`
- Modify: `account/AccountController.java` · `account/AccountLinkService.java` · `account/AccountLinkMapper.java` · `account/AccountRejected.java`
- Test: `account/AccountRefreshApiTest.java`(새 파일) · `account/RefreshCommandTest.java`(새 파일)

**Interfaces:**
- Produces: `PUT /accounts/{id}/credentials` → `204`. 오류는 §3.5 표: `400 INVALID_ACCOUNT_REQUEST` · `403 FORBIDDEN_ACCOUNT` · `409 ACCOUNT_DISCONNECTED`(문구 `연동이 해제된 계좌입니다`) · `409 ACCOUNT_NUMBER_UNAVAILABLE`(문구 `이 계좌는 아직 인증 정보를 갱신할 수 없습니다`) · `503 CREDENTIAL_STORE_UNAVAILABLE`.
- Consumes: `lockOwned`, Task 3의 `readAccountNumber`, `AccountRefIssuer.issue`.

- [ ] **Step 1: 실패하는 단위 테스트(`RefreshCommandTest`).** 앱키 · 시크릿 공백 제거 · 비면 거부 · 1,024자 경계 · `label`은 `null`이면 유지, 있으면 1 ~ 30 코드 포인트 · 빈 문자열 거부 · 거부 메시지와 `toString`에 입력값이 없다. 등록의 `LinkCommand` 검사 코드를 공유한다(복사하지 않는다).
- [ ] **Step 2: 실패하는 통합 테스트(DB 승인 후).** API 설계 §8 표의 "갱신 …" 행 전부:

```java
@Test void 갱신하면_앱키_시크릿만_바뀌고_linked_at이_옮겨진다()
@Test void kis_env가_없는_계좌는_env_키_없이_쓴다()
@Test void 연동_중_계좌도_갱신하고_상태는_그대로다()
@Test void 해제된_계좌는_409이고_저장소에_쓰지_않는다()
@Test void 계좌_정보_값이_없으면_409다()
@Test void 다른_계좌의_계좌_정보_값이면_쓰지_않는다()
@Test void 저장소_읽기_실패면_503이고_아무것도_바뀌지_않는다()
@Test void 저장소_쓰기_실패면_503이고_linked_at과_label이_그대로다()
@Test void 갱신과_해제가_겹치면_차례로_처리된다()        // 대기 훅으로 두 방향 모두
@Test void 남의_계좌_없는_id_UUID_아닌_id는_403이다()
@Test void 갱신_전_실패는_last_collection에서_빠진다()
@Test void 갱신_뒤_동기화는_갱신_전에_열린_USER_행을_공유하지_않는다()
@Test void 갱신_경로에_입력값이_새지_않는다()             // OutputCaptureExtension + 응답 본문
```

- [ ] **Step 3: 구현.** §4.4의 1 ~ 7을 그대로 따른다.
  - 매퍼: `markRefreshed(accountId, label, masked)` — `UPDATE account SET linked_at = now(), label = COALESCE(#{label}, label), account_number_masked = COALESCE(account_number_masked, #{masked}) WHERE account_id = #{accountId}`.
  - `account_ref` 불일치 로그: `log.warn("계좌 정보 값이 계좌와 맞지 않음 account_id={}", id)`.
  - `@RestControllerAdvice(assignableTypes = AccountController.class)`가 그대로 받는다. 컨트롤러는 `@PutMapping("/{accountId}/credentials") @ResponseStatus(NO_CONTENT)`.
  - `AccountLinkService` 클래스 주석의 "등록 · 재연동 · 해제"를 "등록 · 재연동 · 해제 · 인증 정보 갱신"으로 넓힌다.
- [ ] **Step 4: 통과 확인(DB 승인 후).**
- [ ] **Step 5: 커밋(요청 시).** `feat: 연동한 계좌의 인증 정보를 계좌번호 입력 없이 갱신한다`

---

### Task 6: 수집 안내 판정

**Files:**
- Create: `query/CredentialFailureReasons.java` · `query/CollectionAlert.java` · `query/CollectionAlertMapper.java` · `query/CollectionAlertJudge.java` · `query/CollectionAlertPort.java`
- Modify: `sync/PickupSchedule.java`
- Test: `query/CollectionAlertJudgeTest.java`(단위) · `query/CollectionAlertPortTest.java`(DB) · `sync/PickupScheduleTest.java`

**Interfaces:**
- Produces: `record CollectionAlert(String code, int failedDays, OffsetDateTime nextPickupAt)`. `CollectionAlertPort.alertsByAccount(UserScope) : Map<UUID, CollectionAlert>`(안내가 없는 계좌는 맵에 없다). `CredentialFailureReasons.INVALID : Set<String>` = `{"SOURCE_CREDENTIAL_INVALID"}`. `PickupSchedule.nextAfterLinked(OffsetDateTime linkedAt, OffsetDateTime now)`.

판정은 두 단계로 나눈다. 매퍼는 사실만 모으고, 판정은 DB 없는 `CollectionAlertJudge`가 한다.

- [ ] **Step 1: 실패하는 단위 테스트(`CollectionAlertJudgeTest`).** 입력은 계좌 하나의 `link_state` · `linked_at`과 끝난 실행 목록(`as_of` · `state` · `failure_reason` · `finished_at` · `run_id`) · KR 영업일 여부다.

```java
@Test void 마지막_DONE_뒤에_인증_실패가_있으면_CREDENTIAL_INVALID다()
@Test void 인증_실패_뒤의_다른_실패가_안내를_가리지_않는다()
@Test void 마지막이_DONE이면_안내가_없다()
@Test void 같은_날_실행이_여럿이어도_하루로_센다()
@Test void 하루라도_DONE이면_성공한_날이다()
@Test void 비영업일_기준일은_세지_않는다()
@Test void REAUTH_REQUIRED도_실패로_센다()
@Test void 하루_실패는_안내가_없다()
@Test void CONNECTED가_이틀_실패하면_REPEATED_FAILURE다()
@Test void CONNECTING은_이틀_실패해도_REPEATED_FAILURE가_아니다()
@Test void CONNECTING도_인증_실패는_CREDENTIAL_INVALID다()
@Test void CREDENTIAL_INVALID의_일수는_0일_수_있다()
@Test void CONNECTED이고_끝난_실행이_없으면_CREDENTIAL_UPDATED다()
@Test void CONNECTING이고_끝난_실행이_없으면_안내가_없다()
@Test void 모르는_원문_실패_사유는_UNKNOWN으로_거른_뒤_비교한다()
```

- [ ] **Step 2: 실패하는 단위 테스트(`PickupScheduleTest`).** `linked_at` 뒤 첫 수집 시각 · 그 시각이 지난 지 3시간 안이면 그대로 · 넘으면 `now` 뒤 첫 수집 시각.
- [ ] **Step 3: 구현(판정 · 시각).** `CredentialFailureReasons` 주석: "앱키 · 시크릿이 무효라 다시 수집해도 풀리지 않는 실패. 데이터가 그런 코드를 더 주면 여기에만 더한다". 3시간은 상수 `PICKUP_GRACE = Duration.ofHours(3)`이고 주석에 "그 시각의 수집이 도는 동안 같은 값을 보이고, 그 뒤에도 끝난 실행이 없으면 수집이 돌지 않은 것으로 본다"를 쓴다.
- [ ] **Step 4: 실패하는 DB 테스트(`CollectionAlertPortTest`, 승인 후).** `collection_run` · `dim_market_calendar` 행을 넣고 Step 1의 대표 사례 셋(인증 실패 · 연속 실패 · 갱신 직후)이 계좌별로 나오는지, 열린 실행이 일수를 줄이지 않는지(`열린_실행은_일수를_줄이지_않는다`), 남의 계좌가 없는지, `DISCONNECTED` 계좌가 없는지 본다.
- [ ] **Step 5: 구현(매퍼).** 사용자 단위 쿼리 한 번. `account`(DISCONNECTED 제외) × `collection_run`(`requested_at >= linked_at`, `linked_at`이 null이면 거르지 않음, 끝난 상태만) LEFT JOIN `dim_market_calendar`(`market = 'KR'`, `date = as_of`)로 영업일 여부를 붙여 행으로 내린다. 끝난 실행이 없는 계좌도 계좌 행 하나로 내려 `CREDENTIAL_UPDATED`를 판정할 수 있게 한다. 실패 사유는 `FailureReasons.sanitize`를 거친다.
- [ ] **Step 6: 통과 확인.**
- [ ] **Step 7: 커밋(요청 시).** `feat: 수집 결과에서 인증 실패 · 연속 실패 · 갱신 뒤 확인 대기를 판정한다`

---

### Task 7: 응답에 싣기 — `GET /accounts` · 계좌별 뷰 행

**Files:**
- Modify: `account/dto/AccountDto.java` · `account/AccountController.java` · `account/AccountLinkService.java` · `account/AccountLinkMapper.java`(`listLinked`에 `account_number_masked`) · `view/SnapshotViewService.java`(`rowFields`) · `catalog/Catalog.java`(계좌별 행 키)
- Test: `account/AccountApiTest.java` · `api/SixViewGoldenTest.java`와 골든 `src/test/resources/golden/accounts.json`

- [ ] **Step 1: 실패하는 테스트(DB 승인 후).** `GET /accounts`에 `account_number_masked` · `collection_alert`(`code` · `failed_days` · `next_pickup_at`, 안내 없으면 `null`)가 실리고 계좌번호 원문이 없다. 계좌별 뷰 행에 `collection_alert`가 실린다. `Catalog`의 계좌별 행 키 목록에 `collection_alert`가 있다.
- [ ] **Step 2: 구현.** JSON 이름은 snake_case(`collection_alert` · `failed_days` · `next_pickup_at`). 두 곳 모두 `CollectionAlertPort`를 부른다.
- [ ] **Step 3: 골든 갱신.** `accounts.json`의 행에 `"collection_alert": null`이 더해진다. 바뀐 줄이 그것뿐인지 diff로 본다.
- [ ] **Step 4: 통과 확인.**
- [ ] **Step 5: 커밋(요청 시).** `feat: 계좌 목록과 계좌별 뷰 행에 수집 안내와 가린 계좌번호를 싣는다`

---

### Task 8: 계좌별 뷰 notice 셋

**Files:**
- Modify: `view/assembly/NoticeCode.java` · `view/assembly/NoticeCollector.java` · `view/assembly/AssemblyContext.java` · `view/SnapshotViewService.java`(계좌별 뷰 일반 · 빈 봉투 경로) · `sync/SyncMessages.java`(시각 표기 재사용)
- Test: `view/assembly/NoticeCollectorTest.java` · 계좌별 뷰 API 테스트

- [ ] **Step 1: 실패하는 단위 테스트(`NoticeCollectorTest`).** §3.7 notice 표의 세 code × 계좌 하나 · 여럿 문구 · `params`(`account_ids` 순서, `failed_days` 가장 긴 값, `next_pickup_at` 가장 이른 값) · `severity` · 선언 순서(`STALE_ACCOUNTS` 바로 뒤에 `CREDENTIAL_INVALID` · `REPEATED_FAILURE` · `CREDENTIAL_UPDATED`).
- [ ] **Step 2: 실패하는 API 테스트(DB 승인 후).** 계좌별 뷰에 실린다 · 첫 수집 전 `CONNECTING` 계좌도 들어간다 · 스냅샷 없는 빈 봉투에도 실린다 · 요약 등 다른 뷰에는 없다.
- [ ] **Step 3: 구현.** `AssemblyContext`에 `collectionAlerts`(계좌 id · 라벨 · `CollectionAlert`, `GET /accounts`와 같은 순서) 하나를 더하고 계좌별 뷰만 채운다. 다음 수집 표기는 `SyncMessages`의 `MM-dd(E) HH:mm` 포맷을 공유한다. 빈 봉투 경로는 동기화 notice를 싣는 자리에 이 셋을 함께 싣는다. `NoticeCode` 주석은 각 code의 뜻을 한 줄로 쓴다.
- [ ] **Step 4: 통과 확인.** 골든이 notice 순서 때문에 흔들리지 않는지 함께 본다.
- [ ] **Step 5: 커밋(요청 시).** `feat: 계좌별 뷰에 인증 실패 · 연속 실패 · 갱신 뒤 확인 대기 안내를 싣는다`

---

### Task 9: 가린 계좌번호 채우기

**Files:**
- Create: `account/AccountNumberMaskFiller.java`
- Modify: `account/AccountLinkMapper.java`(`unmaskedAccounts` · `fillMask`) · `account/AccountLinkConfig.java`(빈 등록)
- Test: `account/AccountNumberMaskFillerTest.java`

- [ ] **Step 1: 실패하는 테스트(DB 승인 후).** 계좌 정보 값이 있고 `account_number_masked`가 빈 계좌만 채운다 · 값이 없으면 건너뛴다 · `account_ref`가 맞지 않으면 건너뛴다 · 저장소 장애면 건너뛰고 예외를 밖으로 내지 않는다 · 이미 찬 값을 바꾸지 않는다 · `DISCONNECTED`는 보지 않는다 · 건너뛴 개수만 로그에 남고 값 · 이름이 없다.
- [ ] **Step 2: 구현.** 기동 직후 한 번과 그 뒤 1시간마다(`@Scheduled(initialDelay = …, fixedDelay = 1h)`, 기존 스케줄 잡이 쓰는 설정 방식을 따른다). 갱신은 `UPDATE … SET account_number_masked = ? WHERE account_id = ? AND account_number_masked IS NULL`. 주석: "운영자가 계좌 정보 값을 만든 계좌의 가린 번호를 백엔드가 직접 채운다. 복제본이 함께 돌아도 빈 값만 채우므로 같다".
- [ ] **Step 3: 통과 확인.**
- [ ] **Step 4: 커밋(요청 시).** `feat: 계좌 정보 값이 생긴 계좌의 가린 계좌번호를 채운다`

---

### Task 10: 운영자 스크립트와 운영 문서

**Files:**
- Create: `scripts/ops/backfill-account-numbers.sh`
- Modify: `docs/ops/account-credentials.md`

- [ ] **Step 1: 스크립트.** §7 표를 그대로 따른다.
  - `set -euo pipefail`, `set -x` 없음. 기본 `--dry-run`, 쓰려면 `--apply`. 리전 `ap-northeast-2`.
  - `aws ssm get-parameters-by-path --path /stock-project/accounts/ --no-recursive`로 이름만 받고, `^/stock-project/accounts/ar_[0-9a-f]{32}$`만 대상으로 한다.
  - 이름마다: 계좌 정보 값이 이미 있으면 건너뜀(`get-parameter`의 존재만 본다) → 수집용 값을 `--with-decryption`으로 받아 파이프로 곧바로 `jq '{Name: $n, Type: "SecureString", Overwrite: false, Value: ({cano, acnt_prdt_cd} | tojson)}'`에 넘겨 `mktemp` + `chmod 600` 파일에 쓴다 → `put-parameter --cli-input-json file://…` → `trap`으로 파일 삭제. 셸 변수에 값을 담지 않는다.
  - `cano`가 8자리 숫자, `acnt_prdt_cd`가 2자리 숫자가 아니면 "모양이 다름"으로 세고 쓰지 않는다.
  - 끝에 개수만 출력한다(대상 · 씀 · 이미 있음 · 모양이 다름 · 실패).
- [ ] **Step 2: 확인(DB · AWS 없음).** `bash -n`과 `shellcheck`(설치돼 있을 때만, 설치는 하지 않는다). 실제 AWS로 돌리지 않는다.
- [ ] **Step 3: 운영 문서.** `account-credentials.md`에 바뀐 IAM 정책 두 문장(§7 표), KMS 확인 방법(가짜 계좌 정보 값 쓰기 · 읽기 · 지우기), 켜는 순서(IAM → 배포 → 스크립트 `--dry-run` → `--apply` → 1시간 안에 가린 번호), 스크립트를 돌리는 사람의 권한을 적는다.
- [ ] **Step 4: 커밋(요청 시).** `chore: 계좌 정보 값을 만드는 운영 스크립트와 적용 순서를 적는다`

---

### Task 11: 주석 정리와 마무리

**Files:**
- Modify: `query/CollectionRunStatusMapper.java` · `sync/SyncMapper.java` · `sync/SyncTarget.java` · `account/AccountLinkMapper.java`(`relink` 주석)

- [ ] **Step 1: 주석.** `linked_at`을 "마지막 등록 · 재연동 시각"으로 적은 곳을 "지금 자격증명으로 수집을 시작한 시각(등록 · 재연동 · 인증 정보 갱신)"으로 고친다. 동작은 바꾸지 않는다.
- [ ] **Step 2: `ArchitectureRulesTest`.** "`CredentialStore`에는 `account` 패키지만 의존한다"가 새 메서드에도 맞는지 본다. `AccountNumberMaskFiller`가 `account` 패키지에 있다.
- [ ] **Step 3: 전체 테스트(DB 승인 후).** Global Constraints의 명령. Expected: 전부 통과.
- [ ] **Step 4: 머지 직전.** 최신 origin/main에 리베이스하고(`NoticeCollector` · `NoticeCode` 충돌은 선언 순서를 지켜 합친다), V22가 비어 있는지 다시 보고, 전체 테스트를 다시 돌린다.
- [ ] **Step 5: 보고.** 바뀐 파일 · 테스트 결과 · 승인받을 IAM 정책 변경(Task 10 문서의 두 문장) · 운영자 스크립트 실행 절차 · 데이터팀 코드가 더 오면 넣을 곳(`query/CredentialFailureReasons.INVALID`) · 영향받는 통합테스트 동작.

---

## 데이터팀 코드

- 인증 실패 코드 `SOURCE_CREDENTIAL_INVALID`는 dataeng main에 있다(API 설계 §10). 목록에 처음부터 넣는다.
- 운영 파이프라인 이미지에 들어갔는지는 확인하지 않았다. 들어가기 전에는 인증 실패도 `SOURCE_API_ERROR` · `SOURCE_UNREACHABLE`로 와서 `CONNECTED` 계좌는 2일 뒤 `REPEATED_FAILURE`로만 보인다. 백엔드가 따로 할 일은 없다.
- 데이터가 앱키 · 시크릿 무효를 가리는 코드를 더 주면 `CredentialFailureReasons.INVALID`에 더하고 `CollectionAlertJudgeTest`에 그 코드의 사례 하나를 더한다.
