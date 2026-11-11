# 로그인 세션 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 접근 토큰 30분 · 유휴 7일 · 절대 30일의 서버 세션과 회전하는 갱신 토큰을 두고, 푸시 수신 기기를 그 세션에 묶어 세션이 끝난 기기로는 보내지 않게 한다. 앱은 `401`을 받으면 갱신하고 다시 보낸다.

**Architecture:**
- 백엔드
  - `auth_session` 테이블(V19)이 갱신 토큰의 해시와 세대를 든다.
  - 요청 필터가 JWT의 `sid`로 세션이 살아 있는지 매 요청 확인한다.
  - `push_device.session_id`는 세션을 `ON DELETE CASCADE`로 참조한다. 그래서 세션을 지우면 기기와 발송 행이 함께 지워진다.
  - 발송 쿼리 셋이 "살아 있는 세션" 조건을 공유한다.
- 앱
  - `client.ts`가 한 번에 하나만 도는 갱신을 갖는다.
  - `AuthContext`가 부팅 · 저장 · 로그아웃을 세션 기준으로 바꾼다.
  - `device.ts`가 로그아웃을 `POST /auth/logout`으로 보낸다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · Spring Security · jjwt · MyBatis · Flyway · PostgreSQL 16 · JUnit 5 · AssertJ / React Native(Expo SDK 58) · TypeScript · jest-expo

**Spec:** [로그인 세션 설계](../specs/portfolio-management/2026-11-11-auth-session-design.md) — 이 계획의 §번호는 그 문서의 절이다. 상위 근거는 [포트폴리오 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) §8.8, [알림 스펙](../specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md) §9.2.

## Global Constraints

- **언어와 커밋 형식**
  - 응답 · 주석 · 문서 · 커밋 메시지는 한국어다.
  - 커밋 접두어는 `feat:` · `fix:` · `test:` · `docs:` · `chore:`이다.
  - 끝줄은 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`이다.
- **커밋 · 푸시 · 머지 · 배포는 사용자가 요청할 때만 한다.** 각 태스크의 커밋 단계는 요청을 받은 뒤 실행한다.
- **주석**
  - 히스토리 없이 최신 사실만 쓴다.
  - 문서 절 번호(§ · `SG-`)를 지칭하지 않고, 주석만 읽어도 이해되게 쓴다.
  - 검증하지 않은 것은 단정하지 않는다.
- **하지 않을 것**
  - 운영 DB에 쓰지 않는다.
  - `snapshot/` 패키지 · `dataeng/` · `docs/yhr/test/`를 고치지 않는다.
  - 구현 중 설계와 코드가 어긋나면 멈추고 보고한다.
- **수명 값:** `access-ttl: PT30M`, `idle-ttl: P7D`, `absolute-ttl: P30D`. 환경변수는 `PORTFOLIO_AUTH_ACCESS_TTL` · `PORTFOLIO_AUTH_IDLE_TTL` · `PORTFOLIO_AUTH_ABSOLUTE_TTL`이다.
- **살아 있는 세션**은 `last_refreshed_at > now − idle-ttl AND absolute_expires_at > now`이다. 쿼리에서 `now()`를 쓰지 않는다. 주입한 `Clock`의 시각과 `idleCutoff = now − idle-ttl`을 인자로 넘긴다.
- **마이그레이션 번호는 `V19`다.** 머지 직전 `origin/main`에 V19가 생겼으면 다음 빈 번호로 옮기고, 전용 DB를 새로 만들어(승인 후) 다시 돈다.
- **테스트 실행**
  - DB 테스트는 전용 DB에서만 돈다: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_auth_session?currentSchema=app,data' ./gradlew test --rerun-tasks`. 특정 클래스만 돌릴 때는 `--tests '<FQCN>'`를 더한다.
  - DB 테스트는 돌리기 전에 사용자에게 묻는다. DB 없는 단위 테스트는 묻지 않는다.
  - 테스트 메서드 이름은 기존처럼 한국어 문장이다.
- 앱은 Expo SDK를 바꾸지 않는다. 끝에 `npx jest` · `npx tsc --noEmit`이 통과해야 한다.
- 갱신 토큰 · 접근 토큰 · Expo 푸시 토큰은 로그에 남기지 않는다.
- **중간에 빨간 구간이 있다.**
  - Task 1이 `push_device.session_id`를 NOT NULL로 만들면, Task 5가 등록을 세션에 묶을 때까지 기기를 등록하는 DB 테스트가 실패한다(`DeviceApiTest` · `DeliveryDispatcherTest` · `ReceiptCheckerTest` · `AlertRuntimeWriterTest` · `AlertRuntimeFlowTest` 등).
  - Task 2 ~ 4 사이에는 접근 토큰이 임시 세션을 실어 세션 확인이 없다.
  - 그래서 Task 1 ~ 4는 각 태스크가 지정한 테스트만 돌린다. 백엔드 전체는 Task 5 뒤부터 돌린다.
- 백엔드 DB 테스트가 세션 · 기기 수를 셀 때는 다른 테스트가 남긴 행을 피한다. 두 방법 중 하나를 쓴다.
  - 넣은 행의 ID로 남은 것과 지워진 것을 단언한다.
  - 클래스에 `@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})`를 붙여 비우고 시작한다.
- 앱 `client.ts`의 모듈 상태는 `resetClientState()`로 테스트 사이에 비운다(Task 9).

## Review Focus

1. **고정 시계 테스트에서 토큰이 만료로 읽힘**
   - 문제: DB 테스트 16곳이 `FixedClockConfig`(2026-09-28)를 쓴다. JWT 만료를 시스템 시각으로 확인하면 그 테스트들의 로그인 토큰이 전부 `401`이 된다.
   - 막는 법: 발급 · 확인을 같은 `Clock`으로 한다.
   - 테스트: Task 2 `고정_시계로_발급한_토큰을_같은_시계로_확인한다`.
2. **같은 갱신 토큰으로 연달아 두 번 갱신**
   - 문제: 응답이 유실돼 앱이 다시 보내는 경우다.
   - 기대: 둘 다 성공하되 세대가 둘 오르고, 세션은 끊기지 않는다. 두 번째 요청은 "직전 토큰 · 미확인"으로 다시 발급된다. 동시에 들어온 경우는 행 잠금이 같은 순서로 줄을 세운다. 테스트는 연달아 보내는 경우만 본다.
   - 테스트: Task 4 `같은_갱신_토큰의_두_번째_갱신은_새_쌍을_다시_준다`.
3. **갱신 전에 받은 접근 토큰이 아직 30분 안**
   - 기대: 요청은 받고 `confirmed`를 세우지 않는다. 세우면 응답 유실이 재사용으로 오판된다.
   - 테스트: Task 4 `이전_세대_접근_토큰은_받되_확인으로_치지_않는다`.
4. **로그아웃 뒤에 늦게 끝난 갱신**
   - 기대: 결과가 저장소에 남지 않고 만료 배너도 뜨지 않는다.
   - 테스트: Task 9 · Task 11 `로그아웃_뒤에_끝난_갱신은_저장하지_않는다`.
5. **부팅 때 오프라인 + 접근 토큰 만료**
   - 기대: 로그인 화면이 아니라 탭이다. 저장된 세션도 남는다.
   - 테스트: Task 11 `부팅_갱신이_닿지_않으면_탭을_열고_세션을_지우지_않는다`.

---

## 파일 구조

**back-end** (`.worktrees/back-end-auth-session`, 브랜치 `feat/auth-session`). 경로 접두 `src/main/java/com/stockproject/portfolio/`는 줄인다.

| 파일 | 책임 |
|---|---|
| `src/main/resources/db/migration/V19__auth_session.sql` | `auth_session`, `push_device.session_id` |
| `auth/AuthProperties.java`(`JwtProperties.java`를 바꿈) | 서명키 · 세 수명 |
| `auth/AccessClaims.java` · `auth/JwtCodec.java` | 접근 토큰의 `sub` · `sid` · `gen` |
| `auth/session/RefreshTokens.java` · `SessionRow.java` · `RefreshDecision.java` | 갱신 토큰 생성 · 해시 · 판정 표 |
| `auth/session/AuthSessionMapper.java` · `SessionService.java` · `IssuedTokens.java` | 세션 저장과 로그인 · 갱신 · 로그아웃 · 요청 확인 · 정리 |
| `auth/session/AuthSessionJobs.java` · `AuthSessionJobsConfig.java` | 한 시간마다 정리 |
| `auth/AuthPrincipal.java` · `SessionScope.java` · `SessionScopeArgumentResolver.java` | 요청에 붙는 사용자 · 세션 |
| `auth/JwtAuthenticationFilter.java` · `UserScopeArgumentResolver.java` · `SecurityConfig.java` · `WebOriginCorsConfig.java` | 세션 확인 · 공개 경로 · CORS |
| `auth/AuthController.java` · `auth/dto/TokenResponse.java` · `auth/dto/RefreshRequest.java` · `api/ApiExceptionHandler.java` | 세 API · 갱신 거절의 오류 봉투 |
| `alert/api/DeviceController.java` · `alert/service/DeviceService.java` · `alert/store/PushDeviceMapper.java` | 기기를 세션에 묶기 |
| `alert/store/RuntimeMapper.java` · `AlertRuntimeStore.java` · `alert/runtime/AlertRuntimeWriter.java` | 발송 대기 행 만들 때 살아 있는 세션만 |
| `alert/store/DeliveryMapper.java` · `alert/delivery/DeliveryDispatcher.java` | `SESSION_ENDED` · 집기 조건 |
| `src/main/resources/application.yaml` · `src/test/resources/application-test.yaml` | 수명 · 정리 스위치 |
| `src/main/resources/db/sample/sample_alert_market.sql` | 비우는 목록에 `auth_session` |
| `src/test/java/com/stockproject/portfolio/support/SessionFixtures.java`(신규) | 테스트용 세션 열기 · 끝내기 · 시각 당기기 |
| 테스트: `auth/JwtCodecTest` · `auth/session/RefreshDecisionTest`(신규) · `auth/session/AuthSessionApiTest`(신규) · `auth/session/AuthSessionSchemaTest`(신규) · `auth/session/AuthSessionJobsConfigTest`(신규) · `auth/LoginApiTest` · `auth/WebOriginCorsTest` · `alert/api/DeviceApiTest` · `alert/delivery/DeliveryFixtures` · `DeliveryDispatcherTest` · `alert/runtime/AlertRuntimeWriterTest` · `alert/AlertSchemaTest` · `SchemaSmokeTest` · `query/SchemaContractTest` · `support/MovableClock`(신규) · `support/MovableClockConfig`(신규) | |

**front-end** (`.worktrees/front-end-auth-session`, 브랜치 `feat/auth-session`)

| 파일 | 책임 |
|---|---|
| `src/auth/session.ts` | `Session` 타입(앱 전체에서 하나) · `isExpired` |
| `src/auth/tokenStore.ts` | 한 키(`portfolio.session`) 저장 |
| `src/api/types.ts` | `LoginResponse.refresh_token` |
| `src/api/client.ts` | 갱신 · 다시 보내기 · 로그아웃 경계 · `logoutSessionAs` |
| `src/auth/AuthContext.tsx` | 부팅 표 · 갱신 저장 · 로그아웃 |
| `src/push/device.ts` · `src/push/PushRouter.tsx` · `src/api/alertEndpoints.ts` | 세션 로그아웃 · 재시도 · 앞으로 올 때 재등록 |
| `src/testing/sessionSeed.ts`(신규) | 테스트용 저장 세션 심기 |
| 테스트: `src/__tests__/refresh.test.tsx`(신규) · `client.test.ts` · `login.test.tsx` · `logout.test.tsx` · `push.test.tsx` | |

**docs** (`.worktrees/docs-auth-session`, 브랜치 `docs/auth-session`): 설계 · 이 계획 · 스펙 세 문서(Task 12).

---

### Task 0: 작업 공간과 전용 DB

**Files:** 없음(머신 상태 변경)

- [ ] **Step 1: 명령을 승인받고 실행한다.** 아래 명령을 사용자에게 보여 주고 승인받은 뒤 실행한다.

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project
git -C back-end fetch origin
git -C back-end worktree add -b feat/auth-session ../.worktrees/back-end-auth-session origin/main
git -C front-end fetch origin
git -C front-end worktree add -b feat/auth-session ../.worktrees/front-end-auth-session origin/main
```

- [ ] **Step 2: 전용 DB를 만든다.** 같은 승인에 포함해 묻는다. `portfolio_test_auth_session`을 `docs/yhr/plan/2026-10-14-test-environment-setup.md`의 테스트 DB와 같은 방법으로 만든다(소유자 `portfolio`, `app` · `data` 스키마).
- [ ] **Step 3: 13과 겹치는지 본다.** `git -C front-end branch -a`와 worktree 목록에서 13(울린 알림 정렬 · iOS 날짜 칸 · 만료 뒤 누른 푸시)의 브랜치를 찾는다. 있으면 `AuthContext.tsx` · `pushInbox.ts` 변경이 Task 10 · 11과 겹치는지 확인해 사용자에게 알린다. 없으면 넘어간다.
- [ ] **Step 4: 기준선을 잡는다.**
  - back-end: Global Constraints의 테스트 명령. DB 테스트 승인 후 돌린다. Expected: 전부 통과.
  - front-end: `npm ci && npx jest && npx tsc --noEmit`. Expected: 통과.

---

### Task 1: V19 스키마

**Files:**
- Create: `src/main/resources/db/migration/V19__auth_session.sql`
- Modify: `src/main/resources/db/sample/sample_alert_market.sql`
- Test:
  - Create: `src/test/java/com/stockproject/portfolio/auth/session/AuthSessionSchemaTest.java`
  - Modify: `alert/AlertSchemaTest.java`, `SchemaSmokeTest.java`, `query/SchemaContractTest.java`

**Interfaces:**
- Produces:
  - 테이블 `auth_session`. 열과 제약은 설계 §3.1 그대로다.
  - `push_device.session_id uuid NOT NULL REFERENCES auth_session(session_id) ON DELETE CASCADE`와 인덱스 `idx_push_device_session`.

- [ ] **Step 1: 실패하는 테스트를 쓴다.** `AuthSessionSchemaTest`(`@SpringBootTest @ActiveProfiles("test")`, `JdbcClient`). 행 수는 넣은 행의 ID로만 센다.
  - `세션을_지우면_기기와_발송_행이_함께_지워진다`
    - 준비: SQL로 세션 · 기기 · 발화 · 발송 행을 하나씩 넣는다.
    - 실행: `DELETE FROM auth_session WHERE session_id = :s`.
    - 단언: 넣은 `device_id`의 `push_device` 행 0, 넣은 `(event_id, device_id)`의 `alert_delivery` 행 0. 넣은 `event_id`의 `alert_event` 행은 남는다.
  - `기기는_세션_없이_만들_수_없다`: `session_id` 없는 `INSERT INTO push_device`가 NOT NULL 위반이다.
  - `갱신_토큰_해시는_겹칠_수_없다`: 같은 `refresh_hash` 두 행이면 UNIQUE 위반이다.
- [ ] **Step 2: 실행해 실패를 확인한다.** `--tests '*AuthSessionSchemaTest'`. Expected: `relation "auth_session" does not exist`.
- [ ] **Step 3: V19를 쓴다.**
  - 순서: 테이블 → `DELETE FROM push_device` → 열 추가 → 인덱스.
  - `COMMENT`
    - `auth_session`: "로그인 한 번이 만든 세션. 끝난 세션은 행을 지운다. 유휴 만료 시각은 저장하지 않고 last_refreshed_at과 설정의 유휴 수명으로 계산한다"
    - `push_device.session_id`: "이 기기를 등록한 로그인 세션. 세션이 지워지면 기기도 지워진다"
    - `push_device.user_id`: 지금 문구를 유지한다.
  - `DELETE` 앞 주석: "기존 등록은 묶을 세션이 없다. 옛 토큰은 거절되므로 다시 로그인할 때 등록이 새로 생긴다".
- [ ] **Step 4: 기존 스키마 테스트를 맞춘다.**
  - `AlertSchemaTest`: `push_device` 열 목록에 `session_id`를 더한다. 기존 외래키 테스트는 `alert_delivery`의 외래키만 보므로 건드리지 않는다. 대신 `기기는_사용자와_세션을_참조하고_세션이_지워지면_함께_지워진다`를 더한다.
    - 대상: `conrelid = 'app.push_device'::regclass`의 외래키.
    - 기대: `FOREIGN KEY (user_id) REFERENCES app_user(id)`와 `FOREIGN KEY (session_id) REFERENCES auth_session(session_id) ON DELETE CASCADE`.
  - `SchemaSmokeTest` · `SchemaContractTest`: 사용자 컬럼을 가진 테이블에 `auth_session`을 더한다. 기대는 `"account", "alert", "auth_session", "push_device", "sync_run"`이다.
    - 두 파일의 설명 주석에 "로그인 세션"을 넣는다.
    - `SchemaContractTest`의 "그 밖의 테이블에 user_id를 복사하지 않는다" 주석도 맞춰 고친다.
    - 메서드 이름 `사용자_컬럼은_계좌_알림_기기_동기화에만_있다`는 `사용자_컬럼은_계좌_알림_세션_기기_동기화에만_있다`로 바꾼다.
  - `sample_alert_market.sql`: `TRUNCATE` 목록의 `push_device` 뒤에 `auth_session`을 더한다.
- [ ] **Step 5: 통과를 확인한다.** 위 넷만 `--tests`로 돌린다. Expected: PASS.
- [ ] **Step 6: 커밋한다(요청 시).** `feat: 로그인 세션 테이블을 두고 푸시 기기를 세션에 묶는다`

---

### Task 2: 설정과 접근 토큰

**Files:**
- Modify:
  - `auth/JwtProperties.java` → `auth/AuthProperties.java`로 이름을 바꾼다
  - `auth/JwtCodec.java`
  - `src/main/resources/application.yaml`
  - `src/test/resources/application-test.yaml`
- Create: `auth/AccessClaims.java`
- Test: `src/test/java/com/stockproject/portfolio/auth/JwtCodecTest.java`

**Interfaces:**
- Produces:
  - `record AuthProperties(String secret, Duration accessTtl, Duration idleTtl, Duration absoluteTtl)`. `@ConfigurationProperties(prefix = "portfolio.auth")`.
  - `record AccessClaims(UUID userId, UUID sessionId, int generation)`
  - `JwtCodec(AuthProperties properties, Clock clock)`
    - `String issue(AccessClaims claims)`
    - `Optional<AccessClaims> verify(String token)`: `sid`나 `gen`이 없거나 형식이 틀리면 빈 값이다.
    - `Instant expiresAt(String token)`

- [ ] **Step 1: 실패하는 테스트를 쓴다.** 기존 `JwtCodecTest`를 새 생성자로 옮기고 아래를 더한다.
  - `세션과_세대를_싣고_읽는다`: `issue(new AccessClaims(u, s, 3))` → `verify`가 같은 셋을 준다.
  - `세션이_없는_토큰은_서명이_맞아도_거절한다`: 같은 키로 `Jwts.builder().subject(u)`만 만든 토큰 → 빈 값.
  - `고정_시계로_발급한_토큰을_같은_시계로_확인한다`: `Clock.fixed(2026-09-28T01:20Z)`로 만든 코덱이 발급 · 확인 → 값이 있다. 같은 키에 `Clock.fixed(2026-09-28T01:51Z)`로 만든 두 번째 코덱이 확인 → 빈 값.
  - `세대가_없는_토큰도_거절한다`: `sub` · `sid`만 실은 토큰 → 빈 값.
  - `만료는_발급_후_접근_토큰_수명이다`: `expiresAt − 발급 시각 = 30분`.
- [ ] **Step 2: 실행해 실패를 확인한다.** `./gradlew test --tests '*JwtCodecTest'`(DB 없음). Expected: 컴파일 실패.
- [ ] **Step 3: 구현한다.**
  - 발급 시각은 `clock.instant()`다. 확인은 jjwt 파서의 `.clock(() -> Date.from(clock.instant()))`로 한다.
  - 클레임 이름은 `sid` · `gen`이다.
  - `application.yaml`
    - `ttl: PT12H`와 그 주석을 지운다.
    - `access-ttl: ${PORTFOLIO_AUTH_ACCESS_TTL:PT30M}` · `idle-ttl: ${PORTFOLIO_AUTH_IDLE_TTL:P7D}` · `absolute-ttl: ${PORTFOLIO_AUTH_ABSOLUTE_TTL:P30D}`를 둔다.
    - `cleanup.enabled: true`를 둔다. 주석: "접근 토큰이 만료되면 앱이 갱신 토큰으로 새 쌍을 받는다. 유휴 만료는 마지막 갱신부터, 절대 상한은 로그인부터 센다".
  - `application-test.yaml`: `portfolio.auth.cleanup.enabled: false`. 주석은 알림 런타임 스위치와 같은 이유로 쓴다.
  - 클래스 주석의 "서버가 세션을 들지 않으므로" 같은 문장을 최신 사실로 바꾼다.
- [ ] **Step 4: 통과를 확인한다.** `--tests '*JwtCodecTest'`. Expected: PASS. 컴파일이 깨지지 않게 Step 3에서 두 곳을 최소로 고친다. `AuthController.login`은 임시로 `issue(new AccessClaims(user.id(), UUID.randomUUID(), 1))`을 부른다. `JwtAuthenticationFilter`는 `verify(...).map(AccessClaims::userId)`로 읽는다. 둘 다 Task 4가 바꾼다. 그 사이 DB 테스트는 돌리지 않는다.
- [ ] **Step 5: 커밋한다(요청 시).** `feat: 접근 토큰에 세션과 세대를 싣고 주입한 시계로 확인한다`

---

### Task 3: 갱신 토큰과 판정 표

**Files:**
- Create: `auth/session/RefreshTokens.java`, `auth/session/SessionRow.java`, `auth/session/RefreshDecision.java`
- Test: `src/test/java/com/stockproject/portfolio/auth/session/RefreshDecisionTest.java`(DB 없음)

**Interfaces:**
- Produces:
  - `RefreshTokens`
    - `static String generate()`: 32바이트 `SecureRandom`을 base64url로 적고, 패딩은 없다.
    - `static byte[] hash(String token)`: UTF-8 바이트의 SHA-256이다.
  - `record SessionRow(UUID sessionId, UUID userId, byte[] refreshHash, byte[] prevRefreshHash, int generation, boolean confirmed, OffsetDateTime lastRefreshedAt, OffsetDateTime absoluteExpiresAt)`
    - `boolean live(OffsetDateTime now, Duration idleTtl)`
  - `enum RefreshDecision { ROTATE, REISSUE, EXPIRED, REUSED }`
    - `static RefreshDecision decide(SessionRow row, byte[] presented, OffsetDateTime now, Duration idleTtl)`. 행이 없는 경우는 호출자가 처리한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다.** 설계 §4.2 표의 행마다 하나씩 쓴다. 기준은 `now = 2026-11-11T10:00+09`, `idle = 7일`이다.
  - `지금_토큰이면_회전한다` → `ROTATE`
  - `직전_토큰이고_미확인이면_다시_준다` → `REISSUE`
  - `직전_토큰이고_확인됐으면_재사용이다` → `REUSED`
  - `마지막_갱신_후_7일이면_만료다`: `lastRefreshedAt = now − 7일` → `EXPIRED`. 경계가 포함된다. 7일 − 1초는 `ROTATE`다.
  - `절대_상한이_지나면_만료다`: `absoluteExpiresAt = now` → `EXPIRED`.
  - `만료가_재사용보다_먼저다`: 직전 토큰 · 확인됨 · 유휴 지남 → `EXPIRED`.
  - `RefreshTokens`: `generate()` 두 번이 다르고 43자다. `hash`가 같은 입력에 같은 32바이트를 낸다.
- [ ] **Step 2: 실행해 실패를 확인한다.** `--tests '*RefreshDecisionTest'`. Expected: 컴파일 실패.
- [ ] **Step 3: 구현한다.** 해시 비교는 `MessageDigest.isEqual`이다.
- [ ] **Step 4: 통과를 확인한다.** Expected: PASS.
- [ ] **Step 5: 커밋한다(요청 시).** `feat: 갱신 토큰 회전과 재사용 판정을 둔다`

---

### Task 4: 세션 저장 · 세 API · 요청마다 확인

**Files:**
- Create:
  - `auth/session/AuthSessionMapper.java`, `SessionService.java`, `IssuedTokens.java`
  - `auth/AuthPrincipal.java`, `auth/SessionScope.java`, `auth/SessionScopeArgumentResolver.java`
  - `auth/dto/RefreshRequest.java`
  - `src/test/java/com/stockproject/portfolio/support/MovableClock.java`, `MovableClockConfig.java`
- Modify:
  - `auth/AuthController.java`, `auth/dto/TokenResponse.java`, `api/ApiExceptionHandler.java`
  - `auth/JwtAuthenticationFilter.java`, `auth/UserScopeArgumentResolver.java`
  - `auth/SecurityConfig.java`, `auth/WebOriginCorsConfig.java`
- Test:
  - Create: `src/test/java/com/stockproject/portfolio/auth/session/AuthSessionApiTest.java`
  - Modify: `auth/LoginApiTest.java`, `auth/WebOriginCorsTest.java`

**Interfaces:**
- Consumes: Task 2 `JwtCodec` · `AccessClaims` · `AuthProperties`, Task 3 전부.
- Produces:
  - `record IssuedTokens(String accessToken, OffsetDateTime expiresAt, String refreshToken)`
  - `SessionService`
    - `IssuedTokens open(UUID userId)`
    - `Optional<IssuedTokens> refresh(String refreshToken)`: `@Transactional`이다.
    - `void logout(String refreshToken)`
    - `boolean admit(AccessClaims claims)`: 살아 있고 주인이 같으면 true다. 세대가 같고 미확인이면 확인으로 바꾼다.
    - `int purgeDead()`
  - `record AuthPrincipal(UUID userId, UUID sessionId)`. 인증 객체의 principal이다.
  - `record SessionScope(UUID sessionId)`. 컨트롤러 인자이고 `SessionScopeArgumentResolver`가 채운다.
  - `record TokenResponse(String accessToken, OffsetDateTime expiresAt, String refreshToken)`
  - `record RefreshRequest(@NotBlank String refreshToken)`
  - 테스트 지원
    - `MovableClock extends Clock`: `advance(Duration)`, `set(Instant)`가 있다.
    - `MovableClockConfig`: `@TestConfiguration`. `@Primary Clock`이 `MovableClock`이고 시작은 `2026-11-11T01:00:00Z`다.

- [ ] **Step 1: 실패하는 테스트를 쓴다.** `AuthSessionApiTest`(`@SpringBootTest @AutoConfigureMockMvc @ActiveProfiles("test") @Import(MovableClockConfig.class)`). 각 테스트 앞에서 시계를 시작 시각으로 되돌린다.
  - `로그인이_접근_토큰_만료_시각_갱신_토큰을_준다`: 세 필드가 있다. `expires_at` = 시작 + 30분이다.
  - `접근_토큰이_만료돼도_갱신하면_새_토큰으로_조회된다`: 31분 진행 → 옛 토큰으로 `/auth/me`는 `401` → `/auth/refresh` `200` → 새 토큰으로 `/auth/me` `200`.
  - `마지막_갱신_후_7일이_지나면_갱신이_거절되고_세션이_지워진다`
    - 6일 진행 → 갱신 성공 → 6일 진행 → 갱신 성공(유휴가 늘어난다) → 7일 진행 → `401`.
    - `auth_session`에 그 행이 없다.
  - `로그인_후_30일이_지나면_갱신해도_거절된다`: 6일씩 네 번 갱신(24일)은 모두 성공 → 6일 더(30일) 갱신이 `401`이다. 절대 상한 시각은 포함하지 않는다. 그 세션 행이 지워져 있다.
  - `같은_갱신_토큰의_두_번째_갱신은_새_쌍을_다시_준다`: R1으로 두 번 → 둘 다 `200`. 행의 `generation = 3`.
  - `새_토큰으로_요청한_뒤_직전_토큰이_오면_세션을_끝낸다`
    - R1 → R2. R2의 접근 토큰으로 `/auth/me` → R1 갱신이 `401`.
    - 그 세션의 `push_device` 행도 없다. 기기는 SQL로 넣는다.
    - R2 갱신도 `401`이다.
  - `이전_세대_접근_토큰은_받되_확인으로_치지_않는다`: R1 → R2 후 1세대 접근 토큰으로 `/auth/me` `200` → `confirmed`가 false다. 이어서 R1 갱신은 `200`(REISSUE)이다.
  - `로그아웃하면_그_접근_토큰은_만료_전에도_거절된다`: `/auth/logout` `204` → 같은 접근 토큰 `/auth/me` `401`.
  - `직전_갱신_토큰으로도_로그아웃된다`: R1 → R2 후 R1으로 로그아웃 → 행 없음.
  - `모르는_갱신_토큰의_로그아웃도_204다`
  - `빈_갱신_토큰은_400이다`: refresh · logout 둘 다.
  - `세션이_없는_옛_토큰은_거절한다`: 같은 키로 `sub`만 실은 토큰 → `/auth/me` `401` `UNAUTHENTICATED`.
  - `다른_사용자의_세션을_실은_토큰은_거절한다`: jdh 로그인의 `sid`를 yhr의 `sub`와 함께 같은 키로 서명 → `/auth/me` `401`.
  - `갱신_거절은_오류_봉투로_나간다`: 모르는 토큰 갱신 → `error.code = UNAUTHENTICATED`.
  - `갱신_로그아웃은_접근_토큰_없이_열린다`: Authorization 없이 `/auth/refresh`에 유효한 R → `200`.
- [ ] **Step 2: 실행해 실패를 확인한다.** 승인 후 `--tests '*AuthSessionApiTest'`. Expected: 컴파일 실패 또는 `404`.
- [ ] **Step 3: 매퍼를 구현한다.** `AuthSessionMapper`는 애너테이션 SQL이다. 메서드는 다음과 같다.
  - `insert(SessionRow row, OffsetDateTime createdAt)`
  - `Optional<SessionRow> lockByHash(byte[] hash)`: `refresh_hash = #{hash} OR prev_refresh_hash = #{hash}` `FOR UPDATE`.
  - `rotate(UUID sessionId, byte[] prev, byte[] next, int generation, OffsetDateTime now)`: `confirmed = false`.
  - `reissue(UUID sessionId, byte[] next, int generation, OffsetDateTime now)`: `confirmed = false`이고 `prev`는 그대로 둔다.
  - `int delete(UUID sessionId)`
  - `int deleteByHash(byte[] hash)`
  - `Optional<SessionRow> findLive(UUID sessionId, OffsetDateTime now, OffsetDateTime idleCutoff)`
  - `int confirm(UUID sessionId, int generation)`: `WHERE generation = #{generation} AND NOT confirmed`.
  - `int deleteDead(OffsetDateTime now, OffsetDateTime idleCutoff)`
- [ ] **Step 4: 서비스를 구현한다.** `SessionService.refresh`는 `RefreshDecision`으로 갈라 매퍼를 부른다.
  - `EXPIRED` · `REUSED`는 `delete` 후 빈 값이다.
  - `REUSED`는 `log.warn`으로 세션 ID만 남긴다. 토큰은 남기지 않는다.
- [ ] **Step 5: 컨트롤러 · 보안 · CORS를 바꾼다.**
  - 컨트롤러: `/auth/refresh` · `/auth/logout`(`@ResponseStatus(NO_CONTENT)`)을 둔다.
  - 갱신 거절: `AuthController.SessionRejectedException`을 둔다. `ApiExceptionHandler`가 `InvalidCredentialsException`을 다루는 방식 그대로 `401` · `ApiError.of("UNAUTHENTICATED", "다시 로그인해 주세요")`로 바꾼다.
  - `refresh_token` 누락: 기존 `@Valid` 검증 실패와 같은 `400` 경로를 탄다.
  - 매퍼: `bytea`는 `byte[]`로 받는다. 레코드 생성자 매핑이 안 되면 `@Results`로 열을 명시한다.
  - 필터: `verify` → `sessions.admit(claims)`가 true일 때만 `AuthPrincipal`을 붙인다.
  - `UserScopeArgumentResolver`: principal이 `AuthPrincipal`이면 `userId`를 쓴다.
  - `SecurityConfig`: `permitAll`에 `/auth/refresh` · `/auth/logout`을 더하고, `SessionScopeArgumentResolver`를 등록한다.
  - `WebOriginCorsConfig`: `/auth/refresh` · `/auth/logout`에 `POST`를 연다.
  - `TokenResponse` 클래스 주석의 "갱신 토큰을 주지 않으므로…"를 최신 사실로 바꾼다.
- [ ] **Step 6: 기존 테스트를 맞추고 통과를 확인한다.**
  - `LoginApiTest`: "올바른 자격" 테스트에 `refresh_token`을 단언한다.
  - `WebOriginCorsTest`: 기존 preflight 테스트 방식으로 `/auth/refresh` · `/auth/logout`의 `POST` preflight가 허용되는지 더한다.
  - 실행: `--tests '*AuthSessionApiTest' --tests '*LoginApiTest' --tests '*WebOriginCors*'`. Expected: PASS.
- [ ] **Step 7: 커밋한다(요청 시).** `feat: 갱신 · 로그아웃 API를 열고 요청마다 세션을 확인한다`

---

### Task 5: 기기를 세션에 묶기

**Files:**
- Modify: `alert/api/DeviceController.java`, `alert/service/DeviceService.java`, `alert/store/PushDeviceMapper.java`
- Create: `src/test/java/com/stockproject/portfolio/support/SessionFixtures.java`
- Test: `alert/api/DeviceApiTest.java`, `alert/delivery/DeliveryFixtures.java`, `alert/delivery/DeliveryDispatcherTest.java`, `alert/runtime/AlertRuntimeWriterTest.java`

**Interfaces:**
- Consumes: Task 4 `SessionScope` · `SessionService.open`.
- Produces:
  - `DeviceService.register(UserScope scope, SessionScope session, String token, String platform) -> UUID`
  - `PushDeviceMapper.upsert(UserScope scope, UUID sessionId, UUID deviceId, String token, String platform, OffsetDateTime now)`: 충돌하면 `user_id` · `session_id` · `platform` · `last_seen_at`을 바꾼다.
  - `public final class SessionFixtures`(테스트 지원, 다른 패키지에서 쓴다). 생성자는 `(SessionService sessions, JwtCodec jwt, JdbcClient jdbc)`다.
    - `SessionScope open(UserScope user)`: `sessions.open`이 준 접근 토큰의 `sid`를 돌려준다.
    - `void end(UUID deviceId)`: 그 기기의 세션 행을 지운다.
    - `void idle(UUID deviceId, OffsetDateTime lastRefreshedAt)`: 그 기기 세션의 `last_refreshed_at`을 바꾼다.
    - `void absoluteAt(UUID deviceId, OffsetDateTime at)`: `absolute_expires_at`을 바꾼다.
  - `DeliveryFixtures`
    - 생성자에 `SessionFixtures`를 더한다.
    - `device(String token)`은 YHR로 등록한다.
    - `device(UserScope user, String token)`을 더한다. 둘 다 부를 때마다 새 세션을 연다.

- [ ] **Step 1: 실패하는 테스트를 쓴다.** `DeviceApiTest`
  - `등록은_그_요청의_세션에_묶인다`: 등록 후 `push_device.session_id` = 로그인 응답 토큰의 `sid`.
  - `같은_토큰을_다른_세션에서_등록하면_그_세션으로_옮긴다`
    - yhr 두 번 로그인(S1 · S2), 같은 Expo 토큰을 S1 → S2 순서로 등록한다.
    - 단언: `device_id`가 같고 `session_id = S2`.
  - `로그아웃하면_그_세션의_기기와_발송_행이_지워진다`: 등록 후 발송 대기 행을 SQL로 하나 넣는다 → 그 로그인의 갱신 토큰으로 `/auth/logout` → 그 `device_id`의 `push_device` · `alert_delivery` 행이 0이다.
  - `다른_세션의_로그아웃은_기기를_지우지_않는다`: S1로 등록 → S2로 같은 토큰 등록 → S1 로그아웃 → 행이 남는다.
- [ ] **Step 2: 실행해 실패를 확인한다.** 승인 후 `--tests '*DeviceApiTest'`. Expected: FAIL.
- [ ] **Step 3: 구현한다.** 컨트롤러 `register`가 `SessionScope`를 받는다. `unregister`는 그대로다. 매퍼 주석은 "토큰이 이미 있으면 지금 사용자와 지금 세션으로 옮긴다"로 고친다.
- [ ] **Step 4: 발송 테스트 픽스처를 옮기고 통과를 확인한다.**
  - `DeliveryFixtures`를 새 생성자로 옮긴다. 생성하는 테스트 클래스들도 같이 고친다.
  - `DeliveryDispatcherTest:164`의 `devices.register(JDH, …)`는 `devices.register(JDH, sessionFixtures.open(JDH), …)`로 바꾼다.
  - `AlertRuntimeWriterTest`의 직접 등록 네 곳(66–68행 · 118행)도 같은 방식으로 바꾼다.
  - 실행: `--tests '*DeviceApiTest' --tests 'com.stockproject.portfolio.alert.*'`. Expected: PASS.
- [ ] **Step 5: 커밋한다(요청 시).** `feat: 푸시 기기 등록을 로그인 세션에 묶는다`

---

### Task 6: 끝난 세션의 기기로 보내지 않기

**Files:**
- Modify:
  - `alert/store/RuntimeMapper.java`, `alert/store/AlertRuntimeStore.java`, `alert/runtime/AlertRuntimeWriter.java`
  - `alert/store/DeliveryMapper.java`, `alert/delivery/DeliveryDispatcher.java`
- Test: `alert/runtime/AlertRuntimeWriterTest.java`, `alert/delivery/DeliveryDispatcherTest.java`

**Interfaces:**
- Consumes: Task 2 `AuthProperties.idleTtl()`, Task 5 `SessionFixtures.end` · `idle` · `absoluteAt`.
- Produces:
  - `RuntimeMapper.insertDeliveries(UUID eventId, UUID userId, OffsetDateTime now, OffsetDateTime idleCutoff)`
  - `DeliveryMapper.failSessionEnded(OffsetDateTime now, OffsetDateTime idleCutoff) -> int`: `last_error = 'SESSION_ENDED'`이다. 대상은 `failOwnerChanged`와 같다.
  - `DeliveryMapper.lockDue(now, maxAttempts, limit, idleCutoff)`
  - `AlertRuntimeWriter` · `DeliveryDispatcher`가 `AuthProperties`를 받아 `idleCutoff = now − idleTtl`을 만든다.

- [ ] **Step 1: 실패하는 테스트를 쓴다.**
  - `AlertRuntimeWriterTest` `유휴_만료된_세션의_기기에는_발송_대기_행을_만들지_않는다`
    - 준비: 기기 둘(하나는 `idle(d, NOW − 7일)`).
    - 실행: 발화.
    - 단언: 살아 있는 기기의 행만 1개다.
  - `AlertRuntimeWriterTest` `절대_상한이_지난_세션의_기기에도_만들지_않는다`: `absoluteAt(d, NOW)`.
  - `DeliveryDispatcherTest` `대기_중에_세션이_끝난_행은_SESSION_ENDED로_끝나고_보내지_않는다`
    - 준비: `pending` 후 `idle(d, NOW − 7일)`.
    - 실행: `dispatchOnce`.
    - 단언: `state = FAILED`, `last_error = SESSION_ENDED`, `FakePushGateway`가 받은 메시지 0.
  - `DeliveryDispatcherTest` `로그아웃한_세션의_대기_행은_지워져_보내지_않는다`: `pending` 후 `end(d)` → `column(e, d, "state")`가 null · 보낸 것 0.
  - `DeliveryDispatcherTest` `임대가_끝난_전송_중_행도_세션이_끝났으면_보내지_않는다`: `sending(..., 지난 시각)` 후 `idle(d, NOW − 7일)` → `FAILED` `SESSION_ENDED`.
- [ ] **Step 2: 실행해 실패를 확인한다.** 승인 후 두 클래스. Expected: FAIL.
- [ ] **Step 3: 구현한다.**
  - 세 쿼리에 `JOIN auth_session s ON s.session_id = p.session_id AND s.last_refreshed_at > #{idleCutoff} AND s.absolute_expires_at > #{now}` 꼴의 조건을 더한다. `failSessionEnded`는 그 반대 조건이다.
  - `DeliveryDispatcher`는 `failOwnerChanged` 바로 뒤에 `failSessionEnded`를 부른다.
  - `insertDeliveries` 주석에 "로그인 세션이 살아 있는 기기만"을 더한다.
  - 깨지는 기존 호출 세 곳을 고친다.
    - `DeliveryDispatcherTest:205`의 `mapper.lockDue(NOW, 5, DeliveryDispatcher.BATCH)`: `idleCutoff` 인자를 더한다.
    - `DeliveryDispatcherTest:226` · `245`의 `new DeliveryDispatcher(...)`: `AuthProperties`를 더한다.
- [ ] **Step 4: 통과를 확인한다.** Expected: PASS.
- [ ] **Step 5: 커밋한다(요청 시).** `feat: 세션이 끝난 기기에는 발송 대기 행을 만들지도 보내지도 않는다`

---

### Task 7: 세션 정리 작업과 백엔드 전체 확인

**Files:**
- Create: `auth/session/AuthSessionJobs.java`, `auth/session/AuthSessionJobsConfig.java`
- Test: `auth/session/AuthSessionApiTest.java`에 더한다. `auth/session/AuthSessionJobsConfigTest.java`(신규, DB 없음)

**Interfaces:**
- Consumes: `SessionService.purgeDead()`
- Produces:
  - `AuthSessionJobs.purge()`: `@Scheduled(fixedDelayString = "PT1H", initialDelayString = "PT5M")`. 지운 수가 0보다 크면 `log.info`로 수만 남긴다.
  - `AuthSessionJobsConfig`
    - `@EnableScheduling`을 직접 단다. 알림 런타임을 끈 파드에서도 정리가 돌아야 하기 때문이다.
    - `@ConditionalOnProperty(name = "portfolio.auth.cleanup.enabled", havingValue = "true", matchIfMissing = true)`일 때만 빈을 만든다.
    - 환경변수 덮어쓰기는 두지 않는다. 운영에서 끌 이유가 없다.

- [ ] **Step 1: 실패하는 테스트를 쓴다.** `정리는_끝난_세션과_그_기기를_지우고_산_세션은_남긴다`
  - 준비: 세션 셋(산 것 · 유휴 지남 · 절대 지남). 각각 기기를 단다.
  - 실행: `purgeDead()`.
  - 단언: 넣은 세 세션 ID 가운데 산 것만 남는다. 그 기기만 남는다. 돌려준 수는 2 이상이다. 다른 테스트가 남긴 끝난 세션도 함께 지워지기 때문이다.
- `AuthSessionJobsConfigTest`: `AlertRuntimeConfigTest`와 같은 방식(`ApplicationContextRunner`)이다.
  - `정리_스위치가_꺼지면_정리_작업이_없다`
  - `설정이_없으면_정리_작업이_있다`
- [ ] **Step 2: 실행해 실패를 확인한다.** Expected: FAIL.
- [ ] **Step 3: 구현한다.**
- [ ] **Step 4: 통과를 확인한다.** Expected: PASS.
- [ ] **Step 5: 백엔드 전체를 돌린다.** 승인 후 Global Constraints의 명령. Expected: 전부 통과. 깨지는 기존 테스트가 있으면 원인이 설계대로의 변화인지 보고 맞춘다. 설계와 다르면 멈추고 보고한다.
- [ ] **Step 6: 커밋한다(요청 시).** `feat: 끝난 로그인 세션을 한 시간마다 정리한다`

---

### Task 8: 앱 저장 형식

**Files:**
- Modify: `src/auth/session.ts`, `src/auth/tokenStore.ts`, `src/api/types.ts`
- Create: `src/testing/sessionSeed.ts`
- Test: `src/__tests__/login.test.tsx`, `src/__tests__/logout.test.tsx`

**Interfaces:**
- Produces:
  - `src/auth/session.ts`: `export type Session = { token: string; expiresAt: string; refreshToken: string }`. 앱 전체에서 이 타입 하나만 쓴다. `device.ts`의 같은 이름 타입은 Task 10이 지운다. 그때까지 `AuthContext`는 `device.ts`의 것을 그대로 쓴다. `isExpired`는 그대로다. 파일 주석의 "갱신도 강제 로그아웃도 없는 무상태 토큰" 문단은 "만료됐으면 갱신부터 한다"로 바꾼다.
  - `tokenStore`
    - `saveSession(session: Session, email: string): Promise<void>`: `portfolio.session`에 JSON 한 덩어리로 쓴다.
    - `saveRefreshedSession(session: Session): Promise<void>`: 이메일은 건드리지 않는다.
    - `loadSession(): Promise<Session | null>`: 세 값이 다 있어야 한다. 옛 키만 있으면 옛 키를 지우고 null이다.
    - `clearSession()`: 새 키와 옛 키를 모두 지운다.
    - `clearLastEmail` 위에 겹친 옛 JSDoc을 지운다.
  - `LoginResponse`에 `refresh_token: string`.
  - `src/testing/sessionSeed.ts`: `seedStoredSession(partial?: Partial<Session> & { email?: string })`. 기본값은 `{ token: 'tok-a', expiresAt: '2099-01-01T00:00:00+09:00', refreshToken: 'ref-a' }`이고 `a@test.com`이다.

- [ ] **Step 1: 실패하는 테스트를 쓴다.** `login.test.tsx`
  - `로그인하면_세션을_한_키에_저장한다`: `storedItems.get('portfolio.session')`의 JSON에 셋이 있다.
  - `옛_형식으로_저장된_세션은_없는_것으로_치고_지운다`: 옛 두 키만 심고 부팅 → 로그인 화면 · 배너 없음 · 옛 키 없음.
- [ ] **Step 2: 실행해 실패를 확인한다.** `npx jest login logout`. Expected: FAIL.
- [ ] **Step 3: 구현한다.** `login.test.tsx` · `logout.test.tsx`에서 옛 키를 심던 곳은 `seedStoredSession`으로 바꾼다. `login.test.tsx` 222행 블록은 Task 11이 고친다. 이 태스크에서는 심는 키만 바꾼다. 로그인 응답 대역에 `refresh_token`을 더한다.
- [ ] **Step 4: 통과를 확인한다.** `npx jest && npx tsc --noEmit`. 이 시점의 `AuthContext`는 `saveSession(session, email)` 새 서명에 맞춘 최소 수정만 한다. Expected: 통과.
- [ ] **Step 5: 커밋한다(요청 시).** `feat: 접근 토큰 · 만료 시각 · 갱신 토큰을 한 키에 저장한다`

---

### Task 9: 갱신과 다시 보내기 — `client.ts`

**Files:**
- Modify: `src/api/client.ts`
- Test: `src/__tests__/refresh.test.tsx`(신규, 이 태스크에서는 `apiGet`을 직접 부르는 단위 수준), `src/__tests__/client.test.ts`

**Interfaces:**
- Consumes: Task 8 `Session`.
- Produces(`client.ts`)
  - `setSession(session: Session | null): void`: 접근 토큰과 갱신 토큰을 함께 바꾼다. `setAccessToken`은 테스트 지원용으로 남기고 접근 토큰만 바꾼다.
  - `currentSession(): Session | null`
  - `setSessionRefreshedHandler(handler: ((session: Session) => Promise<void>) | null)`: 갱신이 성공하면 이 약속이 끝난 뒤에 새 쌍을 메모리에 넣는다. 실패(거부)해도 메모리에는 넣는다.
  - `refreshSession(): Promise<RefreshOutcome>`, `type RefreshOutcome = 'refreshed' | 'rejected' | 'unreached'`
    - 진행 중인 갱신이 있으면 그 약속을 돌려준다.
    - `401` · `404`는 `rejected`, 연결 실패 · `5xx`는 `unreached`다.
    - `200`인데 본문에 `access_token` · `expires_at` · `refresh_token` 중 하나라도 없으면 `unreached`다. 중간의 무언가가 답한 것으로 본다. 기존의 "200인데 JSON이 아니면 연결 오류"와 같은 판단이다.
    - 메모리에 갱신 토큰이 없으면 요청을 보내지 않고 `rejected`다. 접근 토큰만 심은 테스트와 옛 저장 상태가 이 경로다.
  - `beginLogout(): Promise<Session | null>`
    - 로그아웃 세대를 올린다.
    - 진행 중인 갱신이 있으면 그 갱신을 기다린다. 그 결과는 저장하거나 메모리에 넣지 않는다. 갱신이 성공했으면 응답의 새 쌍을 돌려준다.
    - 그다음 메모리의 세션을 비운다.
    - 기다림의 상한은 부르는 쪽이 건다.
  - `logoutSessionAs(refreshToken: string, signal?: AbortSignal): Promise<void>`: `POST /auth/logout`. Authorization을 싣지 않는다. 만료 처리를 부르지 않는다.
  - `resetClientState(): void`(테스트 지원): 세션 · 진행 중인 갱신 · 로그아웃 세대 · 갱신 핸들러를 비운다. `login.test` · `logout.test` · `refresh.test` · `client.test`의 `beforeEach`가 부른다.
  - 요청 규칙
    - 일반 요청(`apiGet` · `apiPost` · `apiPut` · `apiDelete`)이 `401`을 받으면 `refreshSession()`을 부른다.
    - `refreshed`면 새 접근 토큰으로 한 번만 다시 보낸다. 다시 보낸 요청의 `401`은 갱신하지 않는다.
    - `rejected`면 만료 처리를 부른다. `unreached`면 `NetworkError`를 던진다.
    - 요청이 시작될 때의 로그아웃 세대가 지금과 다르면 만료 처리를 부르지 않는다.
    - 로그인 · 갱신 · 로그아웃 경로와 `sendAs`는 갱신하지 않는다.
- 파일 머리 주석의 "여기서 하는 일은 넷"을 갱신을 넣어 고친다.

- [ ] **Step 1: 실패하는 테스트를 쓴다.** `refresh.test.tsx` `describe('갱신')`. `serveRoutes`로 응답한다.
  - `401을_받으면_갱신하고_새_토큰으로_다시_보낸다`
    - 단언: `/portfolio/views/summary` 두 번째 호출의 `auth`가 `Bearer tok-b`. `/auth/refresh` 본문은 `{ refresh_token: 'ref-a' }`.
  - `동시에_401을_받은_요청_셋이_갱신을_한_번만_부른다`
  - `갱신이_401이면_만료_처리를_부른다`: 등록한 핸들러가 1번 불린다.
  - `갱신_API가_없으면_만료_처리를_부른다`: refresh 경로가 없어 `404`인 경우다.
  - `갱신이_닿지_않으면_연결_오류로_끝나고_만료_처리를_부르지_않는다`
  - `다시_보낸_요청이_또_401이면_한_번만_만료_처리한다`: 갱신은 1번이다.
  - `갱신한_쌍은_저장이_끝난_뒤에_쓴다`
    - 준비: 핸들러가 `wait`로 멈춰 있다.
    - 단언: 그동안 다시 보낸 요청이 없다. 풀면 나간다.
  - `로그아웃_뒤에_끝난_갱신은_저장하지_않는다`: 갱신 대기 중 `beginLogout()` → 핸들러 0번 · `currentSession()` null · 원래 요청의 `401`이 만료 처리를 부르지 않는다. (Review Focus 4의 단위 쪽)
  - `logoutSessionAs는_인증_헤더_없이_갱신_토큰을_싣는다`
  - `갱신이_200인데_토큰이_없으면_연결_오류로_본다`
  - `갱신_토큰이_없으면_요청_없이_만료_처리한다`
  - `client.test.ts` 140행 `조회 요청의 401은 로그아웃으로 이어진다`: 갱신 토큰이 없어 그대로 통과해야 한다. 기대는 바꾸지 않는다.
- [ ] **Step 2: 실행해 실패를 확인한다.** `npx jest refresh`. Expected: FAIL.
- [ ] **Step 3: 구현한다.**
- [ ] **Step 4: 통과를 확인한다.** `npx jest && npx tsc --noEmit`. Expected: 통과.
- [ ] **Step 5: 커밋한다(요청 시).** `feat: 401을 받으면 한 번만 갱신하고 다시 보낸다`

---

### Task 10: 세션 로그아웃 · 재시도 · 다시 등록 — `device.ts`

**Files:**
- Modify: `src/push/device.ts`, `src/push/PushRouter.tsx`, `src/api/alertEndpoints.ts`, `src/auth/AuthContext.tsx`(호출 자리와 재시도 구독만)
- Test: `src/__tests__/logout.test.tsx`, `src/__tests__/push.test.tsx`

**Interfaces:**
- Consumes: Task 8 `Session`, Task 9 `logoutSessionAs` · `refreshSession` · `currentSession` · `currentAccessToken`.
- Produces
  - `releaseOnLogout(refreshToken: string | null, limitMs: number = deviceTiming.unregisterLimitMs): Promise<void>`. `limitMs`는 로그아웃 요청에 줄 남은 시간이다(Task 11이 남은 시간을 넘긴다).
  - `retryPendingRelease(): Promise<void>`: 대기는 `{ refreshToken }`뿐이고 만료 검사가 없다.
  - `registerThisDevice()`
    - 먼저 `await retryPendingRelease()`를 부른다. 같은 '앞으로 옴' 이벤트에서 구독 순서와 상관없이 재시도가 등록보다 먼저 끝난다.
    - `currentSession()`이 있고 접근 토큰이 만료돼 있으면 `refreshSession()`을 기다린다. `refreshed`가 아니면 등록하지 않는다.
    - `currentSession()`이 null이면 `currentAccessToken()`으로 지금처럼 등록한다. 만료 검사는 없다. 접근 토큰만 심는 화면 테스트가 이 경로를 쓴다.
  - 없애는 것: `device.ts`의 `Session` 타입(`@/auth/session`으로 옮김), `inFlightDeviceId`, `posting`, `unregisterDeviceIdAs`.
  - `AuthContext`의 최소 수정
    - `releaseOnLogout(liveSession.current?.refreshToken ?? null)`
    - 재시도 구독은 `status`와 상관없이 둔다.

- [ ] **Step 1: 테스트를 바꾸고 더한다.**
  - `logout.test.tsx`: 기대를 바꾸는 것
    - `deletes()`를 `/auth/logout` 호출을 찾는 `logouts()`로 바꾼다. 기대 본문은 `{ refresh_token: 'ref-a' }`이고 `auth`가 없다.
    - 116행 `시트에서 로그아웃하면 기기 해제 요청이 나가고…`의 이름을 `시트에서 로그아웃하면 세션 로그아웃이 나가고 로그인 화면으로 간다`로 바꾼다.
    - `해제가 404를 받으면…`과 `해제가 401을 받으면…`은 `로그아웃이_4xx를_받으면_끝난_것으로_보고_OS_수신을_끊지_않는다` 하나로 합친다.
    - 266행 `등록한 적 없는 기기는 권한이 있으면 OS 수신만 끊는다`는 둘로 나눈다.
      - `등록한_기기가_없어도_갱신_토큰이_있으면_로그아웃을_보낸다`
      - `저장된_세션이_없으면_권한이_있을_때_OS_수신만_끊는다`
    - 334행 `재시도가 401을 받으면…`과 `토큰이 만료된 대기는 보내지 않고 버린다`는 지운다. 4xx는 끝난 것이고, 대기에 만료가 없다.
    - `로그인한 동안은 재시도하지 않는다` · `로그인 뒤 등록이 성공하면 대기를 버린다`는 다음 둘로 바꾼다.
      - `다시_로그인한_뒤에도_앞으로_오면_대기한_로그아웃을_보낸다`
      - `재시도가_성공하면_다음에는_보내지_않는다`
    - `로그아웃 전에 시작된 등록은…` · `상한이 지난 해제가 늦게 끝나도…`: 세대 번호 테스트로 남긴다. 기기 해제 대신 `alerts.device_id`가 남지 않는지를 본다.
  - `logout.test.tsx`: 더하는 것
    - `로그아웃이_닿지_않으면_OS_수신을_끊고_앞으로_올_때_다시_보낸다`
    - `로그인한_동안_앞으로_오면_기기를_다시_등록한다`: `POST /devices` 2번째 호출.
    - `접근_토큰이_만료된_채_등록하면_먼저_갱신한다`: `/auth/refresh` 뒤에 `/devices`, auth는 새 토큰.
    - `진행_중인_재시도가_끝난_뒤에_다시_등록한다`: 기존 테스트를 새 흐름으로 옮긴다.
  - `push.test.tsx` 287행 `등록이 진행 중이면 해제는 그것을 기다린 뒤 방금 받은 device_id를 지운다`는 지운다. 대신 `로그아웃_뒤에_끝난_등록은_device_id를_저장하지_않는다`로 바꾼다.
    - 순서: 등록 응답을 `wait`로 붙잡고 `releaseOnLogout('ref-a')` → 풀린다.
    - 단언: `alerts.device_id`가 없다. `/auth/logout`이 한 번 나갔다.
- [ ] **Step 2: 실행해 실패를 확인한다.** `npx jest logout push`. Expected: FAIL.
- [ ] **Step 3: 구현한다.**
  - `device.ts`
    - 로그아웃 결과 분류: `2xx` · `4xx` → `released`. 그 밖 · 상한 초과 → `unreached`(OS 수신 끊기 + 대기).
    - 갱신 토큰이 없으면 08처럼 권한이 있을 때 수신만 끊는다.
    - 파일 머리와 함수 주석을 "로그아웃은 세션을 끝내고, 서버가 그 세션의 기기를 함께 지운다"로 바꾼다.
  - `PushRouter`: `AppState`가 `active`가 될 때 `registerThisDevice()`를 부른다. 미확인 수 갱신 구독 옆에 둔다.
  - `alertEndpoints.ts`: `unregisterDeviceIdAs`를 지운다.
- [ ] **Step 4: 통과를 확인한다.** `npx jest && npx tsc --noEmit`. Expected: 통과.
- [ ] **Step 5: 커밋한다(요청 시).** `feat: 로그아웃이 세션을 끝내고 앱이 앞으로 올 때 기기를 다시 등록한다`

---

### Task 11: 부팅 · 로그인 · 로그아웃 — `AuthContext`

**Files:**
- Modify: `src/auth/AuthContext.tsx`
- Test: `src/__tests__/refresh.test.tsx`에 `describe('부팅')` · `describe('쓰는 중')` · `describe('로그아웃')`를 더한다(`renderAppWithAuth`). `src/__tests__/login.test.tsx`도 고친다.

**Interfaces:**
- Consumes: Task 8 · Task 9 · Task 10 전부.
- Produces
  - `liveSession` ref의 타입은 `@/auth/session`의 `Session`이다.
  - `endSession`은 `setSession(null)`을 부른다. 그래서 로그아웃 · 만료 뒤 갱신 토큰이 메모리에 남지 않는다.
  - 갱신 핸들러는 `saveRefreshedSession`을 부르고 `liveSession`을 바꾼다.
  - 동작은 부팅 표(설계 §7.3)를 따른다.

- [ ] **Step 1: 실패하는 테스트를 쓴다.**
  - `부팅`
    - `접근_토큰이_살아_있으면_서버에_묻지_않고_탭을_연다`: `/auth/refresh` 호출 0.
    - `접근_토큰이_만료됐으면_갱신한_뒤_탭을_연다`: 저장소 `portfolio.session`의 토큰이 새것이다.
    - `부팅_갱신이_거절되면_배너_없이_로그인_화면이고_세션을_지운다`: 이메일 칸이 채워져 있다.
    - `부팅_갱신이_닿지_않으면_탭을_열고_세션을_지우지_않는다`
  - `쓰는 중`
    - `접근_토큰_수명이_지나도_쓰는_동안은_로그인_화면으로_가지_않는다`: 요약이 `401`을 받으면 갱신하고 요약이 그려진다. 계정 버튼이 보인다.
    - `갱신이_거절되면_만료_배너가_있는_로그인_화면이다`: 문구는 `ⓘ 로그인이 만료되었어요. 다시 로그인해 주세요`이고 이메일이 채워져 있다.
    - `만료_뒤에는_갱신_토큰이_메모리에_남지_않는다`: 거절 뒤 `currentSession()`이 null이다.
  - `로그아웃`
    - `로그아웃_뒤에_끝난_갱신은_저장하지_않는다`
      - 순서: 갱신이 대기 중일 때 로그아웃 → 갱신을 푼다.
      - 단언: `portfolio.session` 없음 · 로그인 화면 · 배너 없음.
      - 로그아웃 요청의 갱신 토큰은 갱신이 준 새 토큰이다.
    - `갱신을_기다린_시간까지_합쳐_로그아웃은_상한_안에_끝난다`: `deviceTiming.unregisterLimitMs = 100`. 갱신과 로그아웃이 둘 다 응답하지 않을 때, 100ms 남짓에 로그인 화면이다. 200ms가 아니다.
  - `login.test.tsx` 222행 `저장된 토큰이 만료됐으면…`
    - `seedStoredSession({ expiresAt: '2020-01-01T00:00:00+09:00' })`로 심고, `/auth/refresh`만 `401`로 응답하게 바꾼다.
    - 235행 단언은 `portfolio.session`이 없는지로 바꾼다.
- [ ] **Step 2: 실행해 실패를 확인한다.** Expected: FAIL.
- [ ] **Step 3: 구현한다.**
  - 로그인: `saveSession`을 기다린 뒤 `setSession`. 저장 실패는 지금처럼 삼키고 계속한다.
  - `logout`은 마감 시각 하나로 상한을 지킨다.

```ts
const deadline = Date.now() + deviceTiming.unregisterLimitMs;
const latest = await Promise.race([beginLogout(), delay(deviceTiming.unregisterLimitMs).then(() => liveSession.current)]);
await releaseOnLogout(latest?.refreshToken ?? null, Math.max(0, deadline - Date.now()));
```

  - 부팅 주석의 "만료 시각만 보고 첫 화면을 정한다"를 최신 사실로 바꾼다.
- [ ] **Step 4: 통과를 확인한다.** `npx jest && npx tsc --noEmit`. Expected: 통과.
- [ ] **Step 5: 커밋한다(요청 시).** `feat: 부팅 때 만료된 접근 토큰을 갱신하고 로그아웃이 진행 중인 갱신을 기다린다`

---

### Task 12: 스펙 반영

**Files:**
- Modify(docs worktree)
  - `yhr/specs/portfolio-management/2026-07-28-portfolio-management-spec.md`
  - `yhr/specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md`
  - `yhr/specs/app-information-architecture.md`

- [ ] **Step 1: 고친다.** 설계 §10.1 ~ §10.3의 문구를 그대로 넣는다. 각 절의 위치는 §10 제목이 가리킨다.
- [ ] **Step 2: 남은 문구가 없는지 확인한다.** `grep -n -E '12시간|토큰 만료|세션을 보관하지 않는다|refresh 토큰' yhr/specs/portfolio-management/2026-07-28-portfolio-management-spec.md yhr/specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md yhr/specs/app-information-architecture.md`.
  - Expected: 인증과 무관한 줄만 남는다. 예: 알림 발송 기한의 "12시간".
  - 남은 인증 문구가 있으면 사용자에게 문구를 보이고 승인받은 뒤 고친다.
- [ ] **Step 3: 커밋한다(요청 시).** `docs: 로그인 세션과 세션에 묶인 기기 등록을 스펙에 반영한다`. 설계 · 계획 두 파일도 같은 브랜치에 커밋한다. 커밋 메시지는 `docs: 로그인 세션의 설계와 구현 계획을 쓴다`다.

---

### Task 13: 마무리 확인과 보고

- [ ] **Step 1: 전체 테스트를 돌린다.**
  - back-end 전체 테스트(승인 후). origin/main에 V19가 생겼으면 번호를 옮기고, 전용 DB를 새로 만들어(승인 후) 다시 돈다.
  - front-end `npx jest && npx tsc --noEmit`.
  - Expected: 통과.
- [ ] **Step 2: 실기기 확인을 제안한다.** 사용자가 원할 때만, 로컬 백엔드 기동 승인 후 한다.
  - 기동 설정: `PORTFOLIO_AUTH_ACCESS_TTL=PT2M`.
  - 확인 1: 앱을 쓰는 동안 2분이 지나도 로그인 화면으로 가지 않는다.
  - 확인 2: 로그아웃 뒤 발화시킨 알림의 푸시가 오지 않는다.
- [ ] **Step 3: 보고한다.**
  - 바뀐 파일 · 테스트 결과 · 남은 것.
  - 세 수명 값과 밀려나는 조건.
  - 로그아웃 · 유휴 · 절대 상한에서 기기가 어떻게 되는지(설계 §8). 오프라인 로그아웃 때 푸시가 올 수 있는 최대 시간: OS 끊기가 듣지 않을 때 7일.
  - 영향받는 통합테스트 케이스
    - C2-01 ~ C2-08: 만료 재현 방법이 `PORTFOLIO_AUTH_TTL`에서 `PORTFOLIO_AUTH_IDLE_TTL`로 바뀐다. 접근 토큰 수명만 줄이면 이제 조용히 갱신된다.
    - X2-01: 기기가 사용자와 함께 새 세션으로 옮겨진다.
    - X2-07 · E28: 로그아웃 요청이 `DELETE /devices/{id}`에서 `POST /auth/logout`으로 바뀐다.
    - N-13: 갱신 · 로그아웃이 토큰 없이 열리는 경로에 더해진다.
  - 실기기 확인 여부.
