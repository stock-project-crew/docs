# KIS 계좌 등록 · 해제 API 구현 계획

> **에이전트 작업자에게:** 필수 하위 스킬 — superpowers:subagent-driven-development(권장) 또는 superpowers:executing-plans로 과제 단위로 구현한다. 단계는 체크박스(`- [ ]`)로 추적한다.

**목표:** KIS 계좌를 등록 · 재연동 · 해제하고 연동 중인 계좌를 나열하는 API(`POST /accounts` · `DELETE /accounts/{id}` · `GET /accounts`)를 만든다. 자격증명 값은 SSM SecureString에만 둔다.

**구조:** 새 패키지 `com.stockproject.portfolio.account`에 컨트롤러 · 서비스 · 매퍼 · 값 객체 · 저장 포트를 둔다. 등록과 해제는 행을 잠근 트랜잭션 안에서 저장소(SSM)를 부른 뒤 커밋한다. 운영은 `SsmCredentialStore`, 로컬 · 테스트는 `InMemoryCredentialStore`를 쓴다.

**기술:** Java 21 · Spring Boot 3.4.5 · MyBatis 애너테이션 매퍼 · PostgreSQL 16 · AWS SDK for Java v2(`ssm`, `url-connection-client`) · JUnit 5 · AssertJ · Mockito · ArchUnit

**설계:** [`docs/yhr/specs/portfolio-management/2026-10-16-account-link-api-design.md`](../specs/portfolio-management/2026-10-16-account-link-api-design.md). 계획과 설계가 다르면 설계가 맞다. 둘 다 읽는다.

## 전역 제약

- 작업 위치: worktree `/Users/yhr/Dev/workspace/personal/stock-project/back-end-account-api`, 브랜치 `feat/account-link-api`(기준 `feat/position-line-builder` `ae2a2a9`). 이 계획의 모든 경로는 이 worktree 기준이다.
- `./gradlew test`(어느 범위든)는 실행 전에 사용자에게 묻는다. 로컬 `portfolio_test` DB를 다른 세션과 공유한다.
- 새 의존성을 처음 내려받는 빌드도 실행 전에 사용자에게 묻는다(Task 4).
- 커밋은 사용자가 요청할 때만 한다. 메시지는 한국어, 접두는 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝에 아래 두 줄을 단다.
  ```
  Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_011ctfGjdDQefysLwAyXZn8D
  ```
- 마이그레이션을 만들지 않는다. V1 `account` 표를 그대로 쓴다.
- 자격증명 · 계좌번호는 코드 · 로그 · 저장소 어디에도 넣지 않는다. 테스트 값은 가짜다: 앱키 `test-app-key-LEAKCHECK`, 시크릿 `test-app-secret-LEAKCHECK`, 계좌번호 `12345678-01` · `87654321-22` · `11112222-01`.
- 로그에는 `account_id`와 예외 클래스 · SQLState · AWS 오류 코드만 남긴다. 예외 메시지 · `account_ref` · `credential_ref` · 파라미터 이름은 남기지 않는다.
- 파라미터 이름은 `/stock-project/accounts/<account_ref>`, `account_ref`는 `ar_` + HMAC-SHA256(소금, `<기관코드>:<계좌번호10자리>`)의 앞 32hex다.
- 오류 본문은 `{"error":{"code","message"}}`(`ApiError`)이고 `message`는 고정 문구다.
- 응답 필드는 snake_case다. Jackson 전역 설정(`SNAKE_CASE`, `default-property-inclusion: always`)이 처리하므로 DTO에 애너테이션을 달지 않는다.
- 주석 · 문서는 히스토리 없이 현재 사실만 쓴다. 확인하지 않은 것은 단정하지 않는다.
- 운영 반영(IAM · SSM · Secret · 머지)은 Task 10의 절차대로, 단계마다 사용자 승인을 받는다.

## 검토 초점

과제의 테스트가 직접 겨누지 않지만 실제 사용에서 가장 먼저 터질 입력과 조건이다. 각 줄의 테스트는 해당 과제에 넣었다.

1. **복사 · 붙여넣기한 키의 앞뒤 공백과 줄바꿈.** 저장되는 값은 앞뒤 공백을 지운 값이어야 한다 → Task 7 `공백을_지운_키를_저장한다`.
2. **위탁 계좌 두 개를 `label` 없이 등록, 또는 해제한 계좌를 라벨 없이 재연동.** 둘이 구분돼야 한다(`한국투자 위탁`, `한국투자 위탁 2`) → Task 5 `기본_라벨이_겹치면_순번을_붙인다` · `재연동할_때_옛_라벨이_겹치면_순번을_다시_매긴다`.
3. **해제한 계좌의 기본 라벨 자리.** 해제한 계좌의 라벨은 순번 계산에서 빠져야 한다. 해제 뒤 새 위탁을 등록하면 `한국투자 위탁`을 다시 쓴다 → Task 5 `해제한_계좌의_라벨은_순번에_세지_않는다`.
4. **잘못된 HTTP 요청(본문 없음 · 지원하지 않거나 빠진 `Content-Type`).** `401`이 아니라 `400`이나 `415`여야 한다 → Task 7 `본문이_없으면_400` · Task 8 `지원하지_않는_형식은_415` · `Content_Type이_없어도_401이_아니다`.
5. **재연동 때 `label`을 빈 문자열로 보냄.** 거부(`400`)하고 기존 라벨은 그대로여야 한다 → Task 7 `빈_라벨은_거부하고_기존_값을_유지한다`.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `src/main/java/com/stockproject/portfolio/account/KisProduct.java` | 허용 상품코드 → `account_type` · 기본 라벨 |
| `src/main/java/com/stockproject/portfolio/account/KisAccountNumber.java` | 계좌번호 정규화 · 검증 · 마스킹 |
| `src/main/java/com/stockproject/portfolio/account/AccountRejected.java` | 이 기능의 4xx 거부(상태 · 코드 · 고정 문구) |
| `src/main/java/com/stockproject/portfolio/account/LinkCommand.java` | 등록 요청 값 검증 · 정규화 |
| `src/main/java/com/stockproject/portfolio/account/AccountRefProperties.java` | 소금 설정과 기동 검사 |
| `src/main/java/com/stockproject/portfolio/account/AccountRefIssuer.java` | `account_ref` · 파라미터 이름 계산 |
| `src/main/java/com/stockproject/portfolio/account/KisCredential.java` | 저장소로 넘기는 자격증명 값(마스킹) |
| `src/main/java/com/stockproject/portfolio/account/CredentialStore.java` | 저장 포트 |
| `src/main/java/com/stockproject/portfolio/account/CredentialStoreUnavailable.java` | 저장소 장애(메시지 고정) |
| `src/main/java/com/stockproject/portfolio/account/InMemoryCredentialStore.java` | 로컬 · 테스트 구현 |
| `src/main/java/com/stockproject/portfolio/account/SsmCredentialStore.java` | 운영 구현 |
| `src/main/java/com/stockproject/portfolio/account/CredentialsProperties.java` | 저장소 선택 · 리전 설정과 기동 검사 |
| `src/main/java/com/stockproject/portfolio/account/AccountLinkConfig.java` | `CredentialStore` · `AccountRefIssuer` 빈 |
| `src/main/java/com/stockproject/portfolio/account/AccountLinkMapper.java` | `account` 표 쓰기 · 잠금 · 목록 |
| `src/main/java/com/stockproject/portfolio/account/AccountLinkService.java` | 등록 · 해제 · 목록 흐름과 트랜잭션 |
| `src/main/java/com/stockproject/portfolio/account/AccountController.java` | `/accounts` 세 엔드포인트 |
| `src/main/java/com/stockproject/portfolio/account/AccountExceptionHandler.java` | 이 컨트롤러 전용 예외 → 응답 |
| `src/main/java/com/stockproject/portfolio/account/dto/*.java` | 요청 · 응답 DTO |
| `src/main/java/com/stockproject/portfolio/auth/SecurityConfig.java` | ERROR 디스패치 허용(수정) |
| `src/main/resources/application.yaml` · `application-local.yaml` · `src/test/resources/application-test.yaml` | 설정(수정) |
| `build.gradle.kts` | AWS SDK 의존성(수정) |
| `k8s/deployment.yaml` | env(수정) |
| `docs/ops/account-credentials.md` | 운영 규칙 · 반영 절차 |
| `src/test/java/com/stockproject/portfolio/account/*` | 테스트 · 픽스처 |

---

### Task 0: worktree와 기준선

**Files:** 없음(작업 디렉터리)

- [ ] **Step 1: 경로 · 브랜치를 사용자에게 알리고 승인을 받는다**

  알릴 내용: worktree `/Users/yhr/Dev/workspace/personal/stock-project/back-end-account-api`, 브랜치 `feat/account-link-api`, 기준 커밋 `ae2a2a9`.

- [ ] **Step 2: 승인 뒤 worktree를 만든다**

```bash
git -C /Users/yhr/Dev/workspace/personal/stock-project/back-end worktree add \
  -b feat/account-link-api \
  /Users/yhr/Dev/workspace/personal/stock-project/back-end-account-api ae2a2a9
git -C /Users/yhr/Dev/workspace/personal/stock-project/back-end-account-api log --oneline -1
```

Expected: `ae2a2a9 fix: 이후 날짜 잠금의 대기 순환을 주석에 사실대로 적는다`

- [ ] **Step 3: 기준선 테스트를 돌릴지 사용자에게 묻고, 승인되면 실행한다**

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project/back-end-account-api && ./gradlew test
```

Expected: `BUILD SUCCESSFUL`. 실패하면 이 계획을 진행하지 말고 실패 목록을 보고한다.

---

### Task 1: 계좌번호 · 상품코드 · 거부 예외

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/account/KisProduct.java`
- Create: `src/main/java/com/stockproject/portfolio/account/KisAccountNumber.java`
- Create: `src/main/java/com/stockproject/portfolio/account/AccountRejected.java`
- Test: `src/test/java/com/stockproject/portfolio/account/KisAccountNumberTest.java`

**Interfaces:**
- Produces:
  - `enum KisProduct { BROKERAGE, PENSION_SAVINGS }`
    - `String code()`
    - `AccountType accountType()`
    - `String defaultLabel()`
    - `static Optional<KisProduct> of(String code)`
  - `record KisAccountNumber(String cano, KisProduct product)`
    - `static KisAccountNumber parse(String raw)` — 실패하면 `AccountRejected`
    - `String digits()` — 10자리
  - `class AccountRejected extends RuntimeException`
    - `HttpStatus status()`
    - `String code()`
    - 정적 생성자 `invalidRequest()` · `unsupportedProduct()` · `alreadyLinked()` · `unavailable()`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.account;

import com.stockproject.portfolio.domain.AccountType;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** 계좌번호 정규화와 상품코드 판정 (설계 §3.1 · §3.4). */
class KisAccountNumberTest {

    @ParameterizedTest
    @ValueSource(strings = {"12345678-01", "1234567801", "  12345678-01 \n"})
    void 입력_모양과_관계없이_같은_10자리가_된다(String raw) {
        KisAccountNumber number = KisAccountNumber.parse(raw);

        assertThat(number.digits()).isEqualTo("1234567801");
        assertThat(number.cano()).isEqualTo("12345678");
        assertThat(number.product()).isEqualTo(KisProduct.BROKERAGE);
    }

    @Test
    void 위탁은_일반_연금저축은_연금이다() {
        assertThat(KisAccountNumber.parse("12345678-01").product().accountType()).isEqualTo(AccountType.GENERAL);
        assertThat(KisAccountNumber.parse("12345678-01").product().defaultLabel()).isEqualTo("한국투자 위탁");
        assertThat(KisAccountNumber.parse("87654321-22").product().accountType()).isEqualTo(AccountType.PENSION);
        assertThat(KisAccountNumber.parse("87654321-22").product().defaultLabel()).isEqualTo("한국투자 연금저축");
    }

    @ParameterizedTest
    @ValueSource(strings = {"12345678-29", "12345678-55", "12345678-99"})
    void IRP와_DC와_모르는_상품은_거부한다(String raw) {
        assertThatThrownBy(() -> KisAccountNumber.parse(raw))
                .isInstanceOfSatisfying(AccountRejected.class, e -> {
                    assertThat(e.code()).isEqualTo("UNSUPPORTED_ACCOUNT_PRODUCT");
                    assertThat(e.status().value()).isEqualTo(400);
                    assertThat(e.getMessage()).doesNotContain("12345678");
                });
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "   ", "1234567-01", "123456789-01", "12345678-1", "1234abcd-01", "12345678--01", "12-345678-01"})
    void 형식이_틀리면_입력값을_되풀이하지_않고_거부한다(String raw) {
        assertThatThrownBy(() -> KisAccountNumber.parse(raw))
                .isInstanceOfSatisfying(AccountRejected.class, e -> {
                    assertThat(e.code()).isEqualTo("INVALID_ACCOUNT_REQUEST");
                    if (!raw.isBlank()) assertThat(e.getMessage()).doesNotContain(raw.strip());
                });
    }

    @Test
    void null도_형식_오류다() {
        assertThatThrownBy(() -> KisAccountNumber.parse(null))
                .isInstanceOfSatisfying(AccountRejected.class,
                        e -> assertThat(e.code()).isEqualTo("INVALID_ACCOUNT_REQUEST"));
    }

    @Test
    void 문자열로_바꿔도_계좌번호가_보이지_않는다() {
        assertThat(KisAccountNumber.parse("12345678-01").toString())
                .doesNotContain("12345678").doesNotContain("1234567801");
    }
}
```

- [ ] **Step 2: 테스트를 돌릴지 사용자에게 묻고, 승인되면 실행해 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.KisAccountNumberTest'`

Expected: 컴파일 실패(`KisAccountNumber` 없음).

- [ ] **Step 3: 구현한다**

`KisProduct.java`:

```java
package com.stockproject.portfolio.account;

import com.stockproject.portfolio.domain.AccountType;

import java.util.Arrays;
import java.util.Optional;

/**
 * 등록을 받는 KIS 상품코드(계좌번호 뒤 2자리).
 *
 * <p>IRP(29)는 받지 않는다. 데이터 수집기가 기간 체결 조회를 필수로 다루는데 IRP는 그 조회가 막혀
 * 매일 실패로 끝난다. DC(55)는 KIS Open API를 쓸 수 없는 상품이다.</p>
 */
public enum KisProduct {
    BROKERAGE("01", AccountType.GENERAL, "한국투자 위탁"),
    PENSION_SAVINGS("22", AccountType.PENSION, "한국투자 연금저축");

    private final String code;
    private final AccountType accountType;
    private final String defaultLabel;

    KisProduct(String code, AccountType accountType, String defaultLabel) {
        this.code = code;
        this.accountType = accountType;
        this.defaultLabel = defaultLabel;
    }

    public String code() { return code; }

    public AccountType accountType() { return accountType; }

    /** 계좌번호의 어느 부분도 담지 않는다. */
    public String defaultLabel() { return defaultLabel; }

    public static Optional<KisProduct> of(String code) {
        return Arrays.stream(values()).filter(p -> p.code.equals(code)).findFirst();
    }
}
```

`AccountRejected.java`:

```java
package com.stockproject.portfolio.account;

import org.springframework.http.HttpStatus;

/**
 * 계좌 등록 · 해제 요청을 받아들일 수 없다. 메시지는 고정 문구이며 입력값을 담지 않는다.
 */
public class AccountRejected extends RuntimeException {

    private final HttpStatus status;
    private final String code;

    private AccountRejected(HttpStatus status, String code, String message) {
        super(message);
        this.status = status;
        this.code = code;
    }

    public static AccountRejected invalidRequest() {
        return new AccountRejected(HttpStatus.BAD_REQUEST, "INVALID_ACCOUNT_REQUEST",
                "계좌 등록 요청의 형식이 올바르지 않습니다");
    }

    public static AccountRejected unsupportedProduct() {
        return new AccountRejected(HttpStatus.BAD_REQUEST, "UNSUPPORTED_ACCOUNT_PRODUCT",
                "지원하지 않는 계좌 상품입니다. 위탁(01)과 연금저축(22)만 등록할 수 있습니다");
    }

    public static AccountRejected alreadyLinked() {
        return new AccountRejected(HttpStatus.CONFLICT, "ACCOUNT_ALREADY_LINKED",
                "이미 연동된 계좌입니다");
    }

    /** 다른 사용자가 가진 계좌다. 문구는 그 사실을 말하지 않는다. */
    public static AccountRejected unavailable() {
        return new AccountRejected(HttpStatus.CONFLICT, "ACCOUNT_UNAVAILABLE",
                "이 계좌는 등록할 수 없습니다");
    }

    public HttpStatus status() { return status; }

    public String code() { return code; }
}
```

`KisAccountNumber.java`:

```java
package com.stockproject.portfolio.account;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * KIS 계좌번호. 앞 8자리(종합계좌번호)와 뒤 2자리(상품코드)다.
 *
 * <p>하이픈은 있어도 없어도 같은 계좌다. toString은 번호를 가린다 — 로그나 예외에 실려도 새지 않게.</p>
 */
public record KisAccountNumber(String cano, KisProduct product) {

    private static final Pattern FORMAT = Pattern.compile("(\\d{8})-?(\\d{2})");

    public static KisAccountNumber parse(String raw) {
        if (raw == null) throw AccountRejected.invalidRequest();
        Matcher m = FORMAT.matcher(raw.strip());
        if (!m.matches()) throw AccountRejected.invalidRequest();
        KisProduct product = KisProduct.of(m.group(2)).orElseThrow(AccountRejected::unsupportedProduct);
        return new KisAccountNumber(m.group(1), product);
    }

    /** 하이픈 없는 10자리. */
    public String digits() { return cano + product.code(); }

    @Override
    public String toString() { return "KisAccountNumber[********-" + product.code() + "]"; }
}
```

- [ ] **Step 4: 승인을 받아 테스트를 돌려 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.KisAccountNumberTest'`

Expected: PASS

- [ ] **Step 5: 커밋(사용자가 요청한 경우)**

```bash
git add src/main/java/com/stockproject/portfolio/account src/test/java/com/stockproject/portfolio/account
git commit -m "feat: KIS 계좌번호를 정규화하고 상품코드로 계좌 유형을 정한다"
```

---

### Task 2: `account_ref` 발급과 소금 설정

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/account/AccountRefProperties.java`
- Create: `src/main/java/com/stockproject/portfolio/account/AccountRefIssuer.java`
- Modify: `src/main/resources/application.yaml`(`portfolio:` 아래)
- Modify: `src/main/resources/application-local.yaml`
- Modify: `src/test/resources/application-test.yaml`
- Test: `src/test/java/com/stockproject/portfolio/account/AccountRefIssuerTest.java`

**Interfaces:**
- Consumes: `KisAccountNumber.digits()`(Task 1)
- Produces:
  - `record AccountRefProperties(String salt)` — 값 검사는 하지 않는다(Task 3의 `AccountLinkConfig`가 한다)
  - `class AccountRefIssuer`
    - `AccountRefIssuer(String salt)`
    - `String issue(KisAccountNumber number)`
    - `static String parameterName(String accountRef)`
    - 상수 `KIS_INSTITUTION_CODE`

- [ ] **Step 1: 기관코드를 확인한다**

  기관코드는 한국투자증권의 금융결제원 코드 `0243`이다(설계 §5). 고정 벡터는 테스트 소금 `test-account-ref-salt-0123456789abcdef`로 계산한 값이다.

  ```bash
  printf '%s' '0243:1234567801' | openssl dgst -sha256 -hmac 'test-account-ref-salt-0123456789abcdef' | awk '{print $NF}' | cut -c1-32
  ```

  Expected: `a452129164d28a20ec0619f73af2e683`

- [ ] **Step 2: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.account;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/** account_ref 발급 (설계 §5). 소금의 기동 검사는 AccountLinkConfigTest(Task 3)가 본다. */
class AccountRefIssuerTest {

    private static final String SALT = "test-account-ref-salt-0123456789abcdef";
    private final AccountRefIssuer issuer = new AccountRefIssuer(SALT);

    @Test
    void 고정_벡터와_같다() {
        // printf '%s' '0243:1234567801' | openssl dgst -sha256 -hmac '<SALT>' 의 앞 32hex
        assertThat(issuer.issue(KisAccountNumber.parse("12345678-01")))
                .isEqualTo("ar_a452129164d28a20ec0619f73af2e683");
    }

    @Test
    void 같은_계좌는_입력_모양과_관계없이_같은_값이다() {
        assertThat(issuer.issue(KisAccountNumber.parse("1234567801")))
                .isEqualTo(issuer.issue(KisAccountNumber.parse(" 12345678-01 ")));
    }

    @Test
    void 계좌번호나_소금이_다르면_다른_값이다() {
        String base = issuer.issue(KisAccountNumber.parse("12345678-01"));

        assertThat(issuer.issue(KisAccountNumber.parse("11112222-01"))).isNotEqualTo(base);
        assertThat(new AccountRefIssuer(SALT + "x").issue(KisAccountNumber.parse("12345678-01"))).isNotEqualTo(base);
    }

    @Test
    void 형식은_ar_과_32자리_소문자_16진수다() {
        assertThat(issuer.issue(KisAccountNumber.parse("87654321-22"))).matches("ar_[0-9a-f]{32}");
    }

    @Test
    void 파라미터_이름에는_account_ref만_들어간다() {
        assertThat(AccountRefIssuer.parameterName("ar_abc")).isEqualTo("/stock-project/accounts/ar_abc");
    }
}
```

- [ ] **Step 3: 승인을 받아 실행해 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.AccountRefIssuerTest'`

Expected: 컴파일 실패(`AccountRefIssuer` 없음).

- [ ] **Step 4: 구현한다**

`AccountRefProperties.java`:

```java
package com.stockproject.portfolio.account;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * account_ref를 만드는 HMAC 키.
 *
 * <p>값이 바뀌면 같은 계좌가 다른 account_ref를 받아 해제했던 계좌의 과거와 끊긴다. 그래서 기본값을 두지 않는다.
 * 길이 검사는 이 생성자가 아니라 AccountLinkConfig가 한다 — 바인딩 중에 실패하면 기동 실패 보고에 값이 찍힌다.
 * 운영 값은 Secret에서 오고 백업은 SSM에 있다(docs/ops/account-credentials.md).</p>
 */
@ConfigurationProperties(prefix = "portfolio.account-ref")
public record AccountRefProperties(String salt) { }
```

`AccountRefIssuer.java`:

```java
package com.stockproject.portfolio.account;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.HexFormat;

/**
 * 계좌를 데이터팀에 넘기는 불투명 식별자(account_ref)와 자격증명 파라미터 이름을 만든다 (설계 §5).
 *
 * <p>입력은 기관코드와 계좌번호뿐이라 해제했다 다시 등록해도 같은 값이 나온다. 계좌번호 공간이 좁아
 * 소금 없는 해시는 역산되므로 HMAC으로 만든다.</p>
 */
public class AccountRefIssuer {

    /**
     * 한국투자증권의 금융결제원 기관코드. CODEF 기관코드도 같은 체계면 KIS · CODEF 어느 경로로 등록해도 같은 값이 나온다
     * (CODEF 표로는 확인하지 않았다). account_ref를 정하므로 계좌를 등록한 뒤에는 바꾸지 않는다.
     */
    static final String KIS_INSTITUTION_CODE = "0243";

    private static final String PARAMETER_PREFIX = "/stock-project/accounts/";

    private final SecretKeySpec key;

    public AccountRefIssuer(String salt) {
        this.key = new SecretKeySpec(salt.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
    }

    public String issue(KisAccountNumber number) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(key);
            byte[] digest = mac.doFinal((KIS_INSTITUTION_CODE + ":" + number.digits()).getBytes(StandardCharsets.UTF_8));
            return "ar_" + HexFormat.of().formatHex(digest).substring(0, 32);
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("HmacSHA256을 쓸 수 없다", e);
        }
    }

    /** 사용자를 넣지 않는다 — 이 이름은 collection_run을 거쳐 데이터팀에 넘어간다. */
    public static String parameterName(String accountRef) {
        return PARAMETER_PREFIX + accountRef;
    }
}
```

`application.yaml`의 `portfolio:` 아래, `snapshot:`과 같은 깊이에 더한다:

```yaml
  account-ref:
    # account_ref를 만드는 HMAC 키. 바뀌면 같은 계좌가 다른 값을 받는다. 기본값이 없어 빠지면 기동하지 않는다.
    salt: ${ACCOUNT_REF_SALT:}
```

`application-local.yaml` 끝에 더한다:

```yaml
portfolio:
  account-ref:
    # 로컬 전용 값. 운영 값과 다르므로 로컬에서 만든 account_ref는 운영과 이어지지 않는다.
    salt: local-development-account-ref-salt-0123
```

`application-test.yaml`의 `portfolio:` 아래에 더한다:

```yaml
  account-ref:
    salt: test-account-ref-salt-0123456789abcdef
```

`AccountRefIssuer` 빈은 Task 3의 `AccountLinkConfig`가 등록한다.

- [ ] **Step 5: 승인을 받아 테스트를 돌려 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.AccountRefIssuerTest'`

Expected: PASS

- [ ] **Step 6: 커밋(사용자가 요청한 경우)**

```bash
git add -A src/main src/test
git commit -m "feat: 기관코드와 계좌번호로 account_ref를 발급한다"
```

---

### Task 3: 저장 포트 · 메모리 구현 · 빈 구성

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/account/KisCredential.java`
- Create: `src/main/java/com/stockproject/portfolio/account/CredentialStore.java`
- Create: `src/main/java/com/stockproject/portfolio/account/CredentialStoreUnavailable.java`
- Create: `src/main/java/com/stockproject/portfolio/account/InMemoryCredentialStore.java`
- Create: `src/main/java/com/stockproject/portfolio/account/CredentialsProperties.java`
- Create: `src/main/java/com/stockproject/portfolio/account/AccountLinkConfig.java`
- Modify: `src/main/resources/application.yaml` · `application-local.yaml` · `src/test/resources/application-test.yaml`
- Test: `src/test/java/com/stockproject/portfolio/account/AccountLinkConfigTest.java`

**Interfaces:**
- Consumes: `AccountRefProperties`, `AccountRefIssuer(String)`(Task 2)
- Produces:
  - `record KisCredential(String appKey, String appSecret, KisAccountNumber accountNumber)`
  - `interface CredentialStore`
    - `void put(String name, KisCredential credential)`
    - `void delete(String name)`
  - `class CredentialStoreUnavailable extends RuntimeException`
    - `CredentialStoreUnavailable(String causeType, String awsErrorCode)`
    - `String causeType()`
    - `String awsErrorCode()`
  - `class InMemoryCredentialStore implements CredentialStore`
    - `Optional<KisCredential> get(String name)`
  - `record CredentialsProperties(Kind store, String region)` · `enum Kind { SSM, MEMORY }`
  - `AccountLinkConfig`의 빈: `CredentialStore credentialStore(...)` · `AccountRefIssuer accountRefIssuer(...)`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.account;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import static org.assertj.core.api.Assertions.assertThat;

/** 저장소 선택과 기동 검사 (설계 §6.1 · §6.2). */
class AccountLinkConfigTest {

    private static final String SALT = "portfolio.account-ref.salt=test-account-ref-salt-0123456789abcdef";

    private final ApplicationContextRunner runner = new ApplicationContextRunner()
            .withUserConfiguration(AccountLinkConfig.class)
            .withBean(ObjectMapper.class, ObjectMapper::new);

    @Test
    void 저장소_설정이_없으면_기동하지_않는다() {
        runner.withPropertyValues(SALT).run(ctx -> assertThat(ctx).hasFailed());
        runner.withPropertyValues(SALT, "portfolio.credentials.store=").run(ctx -> assertThat(ctx).hasFailed());
    }

    @Test
    void memory면_메모리_저장소를_쓴다() {
        runner.withPropertyValues(SALT, "portfolio.credentials.store=memory").run(ctx -> {
            assertThat(ctx).hasSingleBean(CredentialStore.class);
            assertThat(ctx.getBean(CredentialStore.class)).isInstanceOf(InMemoryCredentialStore.class);
            assertThat(ctx).hasSingleBean(AccountRefIssuer.class);
        });
    }

    @Test
    void 소금이_없거나_짧으면_기동하지_않고_값을_드러내지_않는다() {
        runner.withPropertyValues("portfolio.credentials.store=memory").run(ctx -> assertThat(ctx).hasFailed());
        runner.withPropertyValues("portfolio.credentials.store=memory", "portfolio.account-ref.salt=")
                .run(ctx -> assertThat(ctx).hasFailed());
        runner.withPropertyValues("portfolio.credentials.store=memory", "portfolio.account-ref.salt=short-salt-VALUE")
                .run(ctx -> {
                    assertThat(ctx).hasFailed();
                    assertThat(ctx.getStartupFailure()).rootCause()
                            .isInstanceOf(IllegalStateException.class)
                            .hasMessageNotContaining("short-salt-VALUE");
                });
    }

    @Test
    void 메모리_저장소는_덮어쓰고_없는_이름의_삭제도_성공한다() {
        InMemoryCredentialStore store = new InMemoryCredentialStore();
        KisCredential first = new KisCredential("k1", "s1", KisAccountNumber.parse("12345678-01"));
        KisCredential second = new KisCredential("k2", "s2", KisAccountNumber.parse("12345678-01"));

        store.put("/stock-project/accounts/ar_x", first);
        store.put("/stock-project/accounts/ar_x", second);
        assertThat(store.get("/stock-project/accounts/ar_x")).contains(second);

        store.delete("/stock-project/accounts/ar_x");
        store.delete("/stock-project/accounts/ar_x");
        assertThat(store.get("/stock-project/accounts/ar_x")).isEmpty();
    }

    @Test
    void 자격증명을_문자열로_바꿔도_값이_보이지_않는다() {
        KisCredential c = new KisCredential("test-app-key-LEAKCHECK", "test-app-secret-LEAKCHECK",
                KisAccountNumber.parse("12345678-01"));

        assertThat(c.toString()).doesNotContain("LEAKCHECK").doesNotContain("12345678");
    }

    @Test
    void 저장소_장애의_메시지는_고정이다() {
        CredentialStoreUnavailable e = new CredentialStoreUnavailable("SsmException", "ThrottlingException");

        assertThat(e.getMessage()).isEqualTo("자격증명 저장소를 호출하지 못했다");
        assertThat(e.getCause()).isNull();
        assertThat(e.causeType()).isEqualTo("SsmException");
        assertThat(e.awsErrorCode()).isEqualTo("ThrottlingException");
    }
}
```

- [ ] **Step 2: 승인을 받아 실행해 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.AccountLinkConfigTest'`

Expected: 컴파일 실패.

- [ ] **Step 3: 구현한다**

`KisCredential.java`:

```java
package com.stockproject.portfolio.account;

/**
 * 저장소로만 넘어가는 KIS 자격증명. toString은 값을 가린다.
 */
public record KisCredential(String appKey, String appSecret, KisAccountNumber accountNumber) {

    @Override
    public String toString() { return "KisCredential[***]"; }
}
```

`CredentialStore.java`:

```java
package com.stockproject.portfolio.account;

/**
 * 계좌 자격증명 저장소. 백엔드는 쓰고 지우기만 한다 — 값을 읽는 쪽은 데이터 수집기다.
 *
 * <p>실패하면 {@link CredentialStoreUnavailable}을 던진다.</p>
 */
public interface CredentialStore {

    /** 같은 이름이 있으면 덮어쓴다. */
    void put(String name, KisCredential credential);

    /** 없는 이름도 성공으로 본다. */
    void delete(String name);
}
```

`CredentialStoreUnavailable.java`:

```java
package com.stockproject.portfolio.account;

/**
 * 저장소 호출이 실패했다.
 *
 * <p>원래 예외를 원인으로 붙이지 않는다. SDK 예외 메시지에 파라미터 이름이 들어갈 수 있어서,
 * 남길 수 있는 것은 예외 클래스 이름과 AWS 오류 코드뿐이다.</p>
 */
public class CredentialStoreUnavailable extends RuntimeException {

    private final String causeType;
    private final String awsErrorCode;

    public CredentialStoreUnavailable(String causeType, String awsErrorCode) {
        super("자격증명 저장소를 호출하지 못했다");
        this.causeType = causeType;
        this.awsErrorCode = awsErrorCode;
    }

    public String causeType() { return causeType; }

    /** AWS 서비스 오류가 아니면 null. */
    public String awsErrorCode() { return awsErrorCode; }
}
```

`InMemoryCredentialStore.java`:

```java
package com.stockproject.portfolio.account;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/** 로컬 · 테스트용 저장소. 프로세스가 끝나면 사라진다. */
public class InMemoryCredentialStore implements CredentialStore {

    private final Map<String, KisCredential> values = new ConcurrentHashMap<>();

    @Override
    public void put(String name, KisCredential credential) { values.put(name, credential); }

    @Override
    public void delete(String name) { values.remove(name); }

    public Optional<KisCredential> get(String name) { return Optional.ofNullable(values.get(name)); }
}
```

`CredentialsProperties.java`:

```java
package com.stockproject.portfolio.account;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 자격증명 저장소 설정.
 *
 * @param store  ssm(운영) · memory(로컬 · 테스트). 기본값이 없어 빠지면 기동하지 않는다 —
 *               운영에서 메모리 저장소로 조용히 떨어지면 등록한 키가 재시작에 사라진다.
 * @param region SSM 리전
 */
@ConfigurationProperties(prefix = "portfolio.credentials")
public record CredentialsProperties(Kind store, String region) {

    public enum Kind { SSM, MEMORY }

    public CredentialsProperties {
        if (store == null) throw new IllegalArgumentException("portfolio.credentials.store(ssm · memory)가 없다");
        if (region == null || region.isBlank()) region = "ap-northeast-2";
    }
}
```

`AccountLinkConfig.java`(Task 4가 `SSM` 분기를 채운다. 이 과제에서는 `SSM`이면 기동을 막는다):

```java
package com.stockproject.portfolio.account;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.nio.charset.StandardCharsets;

/** 계좌 연동의 저장소와 account_ref 발급기. */
@Configuration
@EnableConfigurationProperties({CredentialsProperties.class, AccountRefProperties.class})
public class AccountLinkConfig {

    @Bean
    CredentialStore credentialStore(CredentialsProperties properties, ObjectMapper json) {
        return switch (properties.store()) {
            case MEMORY -> new InMemoryCredentialStore();
            case SSM -> throw new IllegalStateException("SSM 저장소는 아직 구성되지 않았다");
        };
    }

    /** 소금이 비었거나 32바이트보다 짧으면 기동하지 않는다. 문구에 값을 넣지 않는다. */
    @Bean
    AccountRefIssuer accountRefIssuer(AccountRefProperties properties) {
        String salt = properties.salt();
        if (salt == null || salt.getBytes(StandardCharsets.UTF_8).length < 32) {
            throw new IllegalStateException("portfolio.account-ref.salt가 없거나 32바이트보다 짧다");
        }
        return new AccountRefIssuer(salt);
    }
}
```

`application.yaml`의 `portfolio:` 아래에 더한다:

```yaml
  credentials:
    # ssm(운영) · memory(로컬 · 테스트). 기본값이 없어 빠지면 기동하지 않는다.
    store: ${CREDENTIAL_STORE:}
    region: ${AWS_REGION:ap-northeast-2}
```

`application-local.yaml`의 `portfolio:` 아래에 더한다:

```yaml
  credentials:
    store: memory
```

`application-test.yaml`의 `portfolio:` 아래에 더한다:

```yaml
  credentials:
    store: memory
```

- [ ] **Step 4: 승인을 받아 테스트를 돌려 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.*'`

Expected: PASS

- [ ] **Step 5: 커밋(사용자가 요청한 경우)**

```bash
git add -A src/main src/test
git commit -m "feat: 계좌 자격증명 저장 포트와 메모리 구현을 둔다"
```

---

### Task 4: SSM 저장소

**Files:**
- Modify: `build.gradle.kts`
- Create: `src/main/java/com/stockproject/portfolio/account/SsmCredentialStore.java`
- Modify: `src/main/java/com/stockproject/portfolio/account/AccountLinkConfig.java`
- Test: `src/test/java/com/stockproject/portfolio/account/SsmCredentialStoreTest.java`

**Interfaces:**
- Consumes: `CredentialStore`, `KisCredential`, `CredentialStoreUnavailable`, `CredentialsProperties`(Task 3)
- Produces:
  - `class SsmCredentialStore implements CredentialStore`
    - `SsmCredentialStore(SsmClient ssm, ObjectMapper json)`
    - `static SsmClient client(String region)`

- [ ] **Step 1: 의존성을 더한다**

`build.gradle.kts`의 `dependencies { … }` 안, `flyway` 줄들 아래에 더한다:

```kotlin
    // 계좌 자격증명을 SSM SecureString에 쓰고 지운다. HTTP 클라이언트는 JDK 기본(url-connection)을 쓴다.
    implementation(platform("software.amazon.awssdk:bom:2.29.0"))
    implementation("software.amazon.awssdk:ssm") {
        exclude(group = "software.amazon.awssdk", module = "apache-client")
        exclude(group = "software.amazon.awssdk", module = "netty-nio-client")
    }
    implementation("software.amazon.awssdk:url-connection-client")
```

- [ ] **Step 2: 의존성 내려받기를 포함한 빌드를 사용자에게 묻고, 승인되면 확인한다**

Run: `./gradlew dependencies --configuration runtimeClasspath | grep -E 'awssdk:(ssm|url-connection-client|apache-client|netty)'`

Expected:
- `ssm`과 `url-connection-client`가 2.29.0으로 해석된다.
- `apache-client`와 `netty-nio-client`는 없다.
- BOM 버전이 해석되지 않으면 멈추고 보고한다.

- [ ] **Step 3: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.account;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import software.amazon.awssdk.awscore.exception.AwsErrorDetails;
import software.amazon.awssdk.core.exception.SdkClientException;
import software.amazon.awssdk.services.ssm.SsmClient;
import software.amazon.awssdk.services.ssm.model.DeleteParameterRequest;
import software.amazon.awssdk.services.ssm.model.ParameterNotFoundException;
import software.amazon.awssdk.services.ssm.model.ParameterType;
import software.amazon.awssdk.services.ssm.model.PutParameterRequest;
import software.amazon.awssdk.services.ssm.model.SsmException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/** SSM 요청 모양과 실패 변환 (설계 §6.1). */
class SsmCredentialStoreTest {

    private static final String NAME = "/stock-project/accounts/ar_test";
    private final SsmClient ssm = mock(SsmClient.class);
    private final ObjectMapper json = new ObjectMapper();
    private final SsmCredentialStore store = new SsmCredentialStore(ssm, json);
    private final KisCredential credential = new KisCredential(
            "test-app-key-LEAKCHECK", "test-app-secret-LEAKCHECK", KisAccountNumber.parse("12345678-01"));

    @Test
    void 데이터_워커가_읽는_모양의_SecureString으로_덮어쓴다() throws Exception {
        store.put(NAME, credential);

        ArgumentCaptor<PutParameterRequest> captor = ArgumentCaptor.forClass(PutParameterRequest.class);
        verify(ssm).putParameter(captor.capture());
        PutParameterRequest request = captor.getValue();
        assertThat(request.name()).isEqualTo(NAME);
        assertThat(request.type()).isEqualTo(ParameterType.SECURE_STRING);
        assertThat(request.overwrite()).isTrue();

        JsonNode value = json.readTree(request.value());
        assertThat(value.size()).isEqualTo(4);
        assertThat(value.get("app_key").asText()).isEqualTo("test-app-key-LEAKCHECK");
        assertThat(value.get("app_secret").asText()).isEqualTo("test-app-secret-LEAKCHECK");
        assertThat(value.get("cano").asText()).isEqualTo("12345678");
        assertThat(value.get("acnt_prdt_cd").asText()).isEqualTo("01");
    }

    @Test
    void 이름으로_지운다() {
        store.delete(NAME);

        ArgumentCaptor<DeleteParameterRequest> captor = ArgumentCaptor.forClass(DeleteParameterRequest.class);
        verify(ssm).deleteParameter(captor.capture());
        assertThat(captor.getValue().name()).isEqualTo(NAME);
    }

    @Test
    void 없는_파라미터의_삭제는_성공이다() {
        when(ssm.deleteParameter(any(DeleteParameterRequest.class)))
                .thenThrow(ParameterNotFoundException.builder().message(NAME).build());

        assertThatCode(() -> store.delete(NAME)).doesNotThrowAnyException();
    }

    @Test
    void 서비스_오류는_코드만_남긴_저장소_장애가_된다() {
        when(ssm.putParameter(any(PutParameterRequest.class))).thenThrow(SsmException.builder()
                .message("denied for " + NAME)
                .awsErrorDetails(AwsErrorDetails.builder().errorCode("AccessDeniedException").build())
                .build());

        assertThatThrownBy(() -> store.put(NAME, credential))
                .isInstanceOfSatisfying(CredentialStoreUnavailable.class, e -> {
                    assertThat(e.awsErrorCode()).isEqualTo("AccessDeniedException");
                    assertThat(e.causeType()).isEqualTo("SsmException");
                    assertThat(e.getMessage()).doesNotContain(NAME);
                    assertThat(e.getCause()).isNull();
                });
    }

    @Test
    void 닫으면_SSM_클라이언트를_닫는다() {
        store.close();

        verify(ssm).close();
    }

    @Test
    void 연결_실패도_저장소_장애가_된다() {
        when(ssm.deleteParameter(any(DeleteParameterRequest.class)))
                .thenThrow(SdkClientException.create("timeout to " + NAME));

        assertThatThrownBy(() -> store.delete(NAME))
                .isInstanceOfSatisfying(CredentialStoreUnavailable.class, e -> {
                    assertThat(e.awsErrorCode()).isNull();
                    assertThat(e.causeType()).isEqualTo("SdkClientException");
                });
    }
}
```

- [ ] **Step 4: 승인을 받아 실행해 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.SsmCredentialStoreTest'`

Expected: 컴파일 실패(`SsmCredentialStore` 없음).

- [ ] **Step 5: 구현한다**

`SsmCredentialStore.java`:

```java
package com.stockproject.portfolio.account;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import software.amazon.awssdk.auth.credentials.EnvironmentVariableCredentialsProvider;
import software.amazon.awssdk.awscore.exception.AwsServiceException;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.ssm.SsmClient;
import software.amazon.awssdk.services.ssm.model.DeleteParameterRequest;
import software.amazon.awssdk.services.ssm.model.ParameterNotFoundException;
import software.amazon.awssdk.services.ssm.model.ParameterType;
import software.amazon.awssdk.services.ssm.model.PutParameterRequest;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 계좌 자격증명을 SSM SecureString에 쓴다 (설계 §6.1).
 *
 * <p>값은 데이터 수집기(collect_kis_account.py)가 읽는 JSON 모양 그대로다. 백엔드는 값을 읽지 않는다.</p>
 *
 * <p>AWS 자격 증명은 환경변수에서만 받는다. 기본 체인은 환경변수가 없을 때 노드의 인스턴스 역할을 집을 수 있다.</p>
 */
public class SsmCredentialStore implements CredentialStore, AutoCloseable {

    private final SsmClient ssm;
    private final ObjectMapper json;

    public SsmCredentialStore(SsmClient ssm, ObjectMapper json) {
        this.ssm = ssm;
        this.json = json;
    }

    /** 이 호출 시간 제한이 등록 · 해제가 계좌 행 잠금을 쥐는 최대 시간을 정한다. */
    public static SsmClient client(String region) {
        return SsmClient.builder()
                .region(Region.of(region))
                .credentialsProvider(EnvironmentVariableCredentialsProvider.create())
                .httpClient(UrlConnectionHttpClient.builder()
                        .connectionTimeout(Duration.ofSeconds(3))
                        .socketTimeout(Duration.ofSeconds(10))
                        .build())
                .overrideConfiguration(c -> c.apiCallTimeout(Duration.ofSeconds(10)))
                .build();
    }

    @Override
    public void put(String name, KisCredential credential) {
        try {
            ssm.putParameter(PutParameterRequest.builder()
                    .name(name)
                    .value(valueOf(credential))
                    .type(ParameterType.SECURE_STRING)
                    .overwrite(true)
                    .build());
        } catch (SdkException e) {
            throw unavailable(e);
        }
    }

    @Override
    public void delete(String name) {
        try {
            ssm.deleteParameter(DeleteParameterRequest.builder().name(name).build());
        } catch (ParameterNotFoundException e) {
            // 이미 없다 — 지우려던 상태가 이미 성립한다
        } catch (SdkException e) {
            throw unavailable(e);
        }
    }

    /** 빈 소멸 때 컨테이너가 부른다(close 메서드 추론). */
    @Override
    public void close() { ssm.close(); }

    private String valueOf(KisCredential c) {
        Map<String, String> value = new LinkedHashMap<>();
        value.put("app_key", c.appKey());
        value.put("app_secret", c.appSecret());
        value.put("cano", c.accountNumber().cano());
        value.put("acnt_prdt_cd", c.accountNumber().product().code());
        try {
            return json.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new CredentialStoreUnavailable(e.getClass().getSimpleName(), null);
        }
    }

    private static CredentialStoreUnavailable unavailable(SdkException e) {
        String code = e instanceof AwsServiceException aws && aws.awsErrorDetails() != null
                ? aws.awsErrorDetails().errorCode() : null;
        return new CredentialStoreUnavailable(e.getClass().getSimpleName(), code);
    }
}
```

`AccountLinkConfig.java`의 `SSM` 분기를 바꾼다:

```java
            case SSM -> new SsmCredentialStore(SsmCredentialStore.client(properties.region()), json);
```

- [ ] **Step 6: 승인을 받아 테스트를 돌려 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.*'`

Expected: PASS

- [ ] **Step 7: 커밋(사용자가 요청한 경우)**

```bash
git add build.gradle.kts src/main/java/com/stockproject/portfolio/account src/test/java/com/stockproject/portfolio/account
git commit -m "feat: 계좌 자격증명을 SSM SecureString에 쓰고 지운다"
```

---

### Task 5: 매퍼와 등록 서비스

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/account/AccountLinkMapper.java`
- Create: `src/main/java/com/stockproject/portfolio/account/LinkCommand.java`
- Create: `src/main/java/com/stockproject/portfolio/account/AccountLinkService.java`
- Create: `src/test/java/com/stockproject/portfolio/account/ControllableCredentialStore.java`
- Create: `src/test/java/com/stockproject/portfolio/account/AccountTestConfig.java`
- Create: `src/test/java/com/stockproject/portfolio/account/AccountFixture.java`
- Test: `src/test/java/com/stockproject/portfolio/account/AccountLinkServiceTest.java`

**Interfaces:**
- Consumes: `KisAccountNumber` · `KisProduct` · `AccountRejected`(Task 1), `AccountRefIssuer`(Task 2), `CredentialStore` · `KisCredential` · `CredentialStoreUnavailable`(Task 3), `UserScope`(기존)
- Produces:
  - `record LinkCommand(String appKey, String appSecret, KisAccountNumber accountNumber, String label)`
    - `static LinkCommand of(String appKey, String appSecret, String accountNumber, String label)`
  - `AccountLinkService`
    - `LinkResult link(UserScope scope, LinkCommand command)`
    - `record LinkResult(UUID accountId, LinkState linkState)`
  - `AccountLinkMapper`
    - `UUID insertIfAbsent(NewAccount)`
    - `LockedAccount lockByRef(String)`
    - `LockedAccount lockOwned(UUID, UUID)`
    - `void relink(UUID, String, String)`
    - `void disconnect(UUID)`
    - `List<String> linkedLabels(UUID)`
    - `List<LinkedAccountRow> listLinked(UUID)`
  - 테스트용: `ControllableCredentialStore`
    - `failNext()`
    - `pauseNext()` · `awaitPaused()` · `resume()`
    - `get(String)`
  - 테스트용: `AccountFixture`
    - `reset()`
    - `row(UUID)`
    - `accountIdOf(String accountRef)`
    - `waitingOnLock()`

- [ ] **Step 1: 테스트 연결 풀을 줄이고 테스트 지원 코드를 쓴다**

이 과제부터 테스트 컨텍스트가 늘어난다. 캐시된 컨텍스트마다 연결 풀이 살아 있다. Hikari 기본값은 10개 연결을 미리 채우므로, 지금 9개 컨텍스트(약 90연결)에 더하면 PostgreSQL 기본 한도 100을 넘는다. `application-test.yaml`의 `spring.datasource` 아래에 더한다:

```yaml
    # 캐시된 테스트 컨텍스트마다 풀이 살아 있다. 기본값(10개 미리 채움)이면 컨텍스트가 늘 때 DB 연결 한도(100)를 넘는다.
    # 가장 많이 쓰는 동시성 테스트도 연결 셋이면 된다.
    hikari:
      maximum-pool-size: 5
      minimum-idle: 1
```

`ControllableCredentialStore.java`:

```java
package com.stockproject.portfolio.account;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** 실패와 멈춤을 걸 수 있는 테스트 저장소. 다음 한 번의 호출에만 걸린다. */
public class ControllableCredentialStore implements CredentialStore {

    private final Map<String, KisCredential> values = new ConcurrentHashMap<>();
    private final AtomicBoolean failNext = new AtomicBoolean();
    private final AtomicBoolean pauseNext = new AtomicBoolean();
    private volatile CountDownLatch paused = new CountDownLatch(1);
    private volatile CountDownLatch released = new CountDownLatch(1);

    @Override
    public void put(String name, KisCredential credential) {
        gate();
        values.put(name, credential);
    }

    @Override
    public void delete(String name) {
        gate();
        values.remove(name);
    }

    public Optional<KisCredential> get(String name) { return Optional.ofNullable(values.get(name)); }

    public void failNext() { failNext.set(true); }

    public void pauseNext() {
        paused = new CountDownLatch(1);
        released = new CountDownLatch(1);
        pauseNext.set(true);
    }

    public void awaitPaused() throws InterruptedException {
        if (!paused.await(10, TimeUnit.SECONDS)) throw new IllegalStateException("저장소 호출이 오지 않았다");
    }

    public void resume() { released.countDown(); }

    public void clear() {
        values.clear();
        failNext.set(false);
        pauseNext.set(false);
    }

    private void gate() {
        if (pauseNext.compareAndSet(true, false)) {
            paused.countDown();
            try {
                if (!released.await(10, TimeUnit.SECONDS)) throw new IllegalStateException("멈춘 호출이 풀리지 않았다");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException(e);
            }
        }
        if (failNext.compareAndSet(true, false)) throw new CredentialStoreUnavailable("TestFailure", "Simulated");
    }
}
```

`AccountTestConfig.java`:

```java
package com.stockproject.portfolio.account;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;

/** 계좌 연동 테스트의 저장소와 픽스처. */
@TestConfiguration
@Import(AccountFixture.class)
public class AccountTestConfig {

    @Bean
    @Primary
    ControllableCredentialStore controllableCredentialStore() { return new ControllableCredentialStore(); }
}
```

`AccountFixture.java`:

```java
package com.stockproject.portfolio.account;

import org.springframework.jdbc.core.simple.JdbcClient;

import java.util.Map;
import java.util.UUID;

/** 계좌 표를 비우고 읽는 픽스처. 사용자 행은 마이그레이션이 심은 것을 쓴다. AccountTestConfig가 @Import로 등록한다. */
public class AccountFixture {

    public static final UUID YHR = UUID.fromString("40000000-0000-0000-0000-000000000001");
    public static final UUID JDH = UUID.fromString("40000000-0000-0000-0000-000000000002");

    private final JdbcClient jdbc;

    public AccountFixture(JdbcClient jdbc) { this.jdbc = jdbc; }

    public void reset() {
        jdbc.sql("""
                TRUNCATE position_build, realized_pnl_line, manual_cashflow, position_line, account, collection_run
                """).update();
    }

    public Map<String, Object> row(UUID accountId) {
        return jdbc.sql("""
                SELECT account_id, user_id, account_ref, broker, label, account_type, source,
                       credential_ref, link_state, last_synced_at
                  FROM account WHERE account_id = :id
                """).param("id", accountId).query().singleRow();
    }

    public long count() {
        return jdbc.sql("SELECT count(*) FROM account").query(Long.class).single();
    }

    public UUID accountIdOf(String accountRef) {
        return jdbc.sql("SELECT account_id FROM account WHERE account_ref = :r").param("r", accountRef)
                .query(UUID.class).single();
    }

    /**
     * 계좌 삽입에서 다른 트랜잭션을 기다리는 세션 수. 동시성 테스트가 상대 요청이 정말 막혔는지 확인하는 데 쓴다.
     * 테스트 DB를 다른 세션과 같이 쓰므로 이 기능의 삽입 문장으로 좁힌다.
     */
    public long waitingOnLock() {
        return jdbc.sql("""
                SELECT count(*) FROM pg_stat_activity
                 WHERE datname = current_database() AND wait_event_type = 'Lock'
                   AND pid <> pg_backend_pid() AND backend_type = 'client backend'
                   AND query LIKE '%INSERT INTO account%'
                """).query(Long.class).single();
    }

    public void sql(String statement) { jdbc.sql(statement).update(); }
}
```

- [ ] **Step 2: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.account;

import com.stockproject.portfolio.auth.UserScope;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

import static com.stockproject.portfolio.account.AccountFixture.JDH;
import static com.stockproject.portfolio.account.AccountFixture.YHR;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** 등록과 재연동 (설계 §4.1). */
@SpringBootTest
@AutoConfigureMockMvc   // AccountApiTest와 같은 컨텍스트를 쓰게 한다 — 컨텍스트마다 연결 풀이 생긴다
@ActiveProfiles("test")
@Import(AccountTestConfig.class)
class AccountLinkServiceTest {

    @Autowired AccountLinkService service;
    @Autowired AccountFixture f;
    @Autowired ControllableCredentialStore store;
    @Autowired AccountRefIssuer refs;

    @BeforeEach
    void setUp() {
        f.reset();
        store.clear();
    }

    private static LinkCommand command(String number, String label) {
        return LinkCommand.of("test-app-key-LEAKCHECK", "test-app-secret-LEAKCHECK", number, label);
    }

    private String parameterOf(String number) {
        return AccountRefIssuer.parameterName(refs.issue(KisAccountNumber.parse(number)));
    }

    @Test
    void 새_계좌는_연동_중으로_생기고_저장소에_값이_있다() {
        AccountLinkService.LinkResult result = service.link(new UserScope(YHR), command("12345678-01", null));

        var row = f.row(result.accountId());
        assertThat(row.get("user_id")).isEqualTo(YHR);
        assertThat(row.get("link_state")).isEqualTo("CONNECTING");
        assertThat(row.get("broker")).isEqualTo("한국투자증권");
        assertThat(row.get("source")).isEqualTo("KIS");
        assertThat(row.get("account_type")).isEqualTo("GENERAL");
        assertThat(row.get("label")).isEqualTo("한국투자 위탁");
        assertThat(row.get("credential_ref")).isEqualTo(parameterOf("12345678-01"));
        assertThat(store.get(parameterOf("12345678-01"))).isPresent();
    }

    @Test
    void 기본_라벨이_겹치면_순번을_붙인다() {
        UUID first = service.link(new UserScope(YHR), command("12345678-01", null)).accountId();
        UUID second = service.link(new UserScope(YHR), command("11112222-01", null)).accountId();

        assertThat(f.row(first).get("label")).isEqualTo("한국투자 위탁");
        assertThat(f.row(second).get("label")).isEqualTo("한국투자 위탁 2");
    }

    @Test
    void 해제한_계좌의_라벨은_순번에_세지_않는다() {
        UUID first = service.link(new UserScope(YHR), command("12345678-01", null)).accountId();
        f.sql("UPDATE account SET link_state = 'DISCONNECTED' WHERE account_id = '" + first + "'");

        UUID second = service.link(new UserScope(YHR), command("11112222-01", null)).accountId();

        assertThat(f.row(second).get("label")).isEqualTo("한국투자 위탁");
    }

    @Test
    void 재연동할_때_옛_라벨이_겹치면_순번을_다시_매긴다() {
        UUID a = service.link(new UserScope(YHR), command("12345678-01", null)).accountId();
        f.sql("UPDATE account SET link_state = 'DISCONNECTED', credential_ref = NULL WHERE account_id = '" + a + "'");
        UUID b = service.link(new UserScope(YHR), command("11112222-01", null)).accountId();

        service.link(new UserScope(YHR), command("12345678-01", null));

        assertThat(f.row(b).get("label")).isEqualTo("한국투자 위탁");
        assertThat(f.row(a).get("label")).isEqualTo("한국투자 위탁 2");
    }

    @Test
    void 요청한_라벨은_그대로_쓴다() {
        UUID id = service.link(new UserScope(YHR), command("87654321-22", "  노후 대비  ")).accountId();

        assertThat(f.row(id).get("label")).isEqualTo("노후 대비");
        assertThat(f.row(id).get("account_type")).isEqualTo("PENSION");
    }

    @Test
    void 해제한_계좌를_다시_등록하면_같은_행을_쓰고_라벨은_요청에_있을_때만_바꾼다() {
        UUID id = service.link(new UserScope(YHR), command("12345678-01", "옛 이름")).accountId();
        f.sql("UPDATE account SET link_state = 'DISCONNECTED', credential_ref = NULL WHERE account_id = '" + id + "'");

        UUID again = service.link(new UserScope(YHR), LinkCommand.of("new-key", "new-secret", "12345678-01", null)).accountId();

        assertThat(again).isEqualTo(id);
        assertThat(f.row(id).get("link_state")).isEqualTo("CONNECTING");
        assertThat(f.row(id).get("label")).isEqualTo("옛 이름");
        assertThat(f.row(id).get("credential_ref")).isEqualTo(parameterOf("12345678-01"));
        assertThat(store.get(parameterOf("12345678-01")).orElseThrow().appKey()).isEqualTo("new-key");

        f.sql("UPDATE account SET link_state = 'DISCONNECTED', credential_ref = NULL WHERE account_id = '" + id + "'");
        service.link(new UserScope(YHR), command("12345678-01", "새 이름"));
        assertThat(f.row(id).get("label")).isEqualTo("새 이름");
    }

    @Test
    void 이미_연동_중이면_거부한다() {
        service.link(new UserScope(YHR), command("12345678-01", null));

        assertThatThrownBy(() -> service.link(new UserScope(YHR), command("12345678-01", null)))
                .isInstanceOfSatisfying(AccountRejected.class,
                        e -> assertThat(e.code()).isEqualTo("ACCOUNT_ALREADY_LINKED"));
    }

    @Test
    void 다른_사용자의_계좌는_거부하고_그_행을_건드리지_않는다() {
        UUID id = service.link(new UserScope(YHR), command("12345678-01", "yhr 계좌")).accountId();
        f.sql("UPDATE account SET link_state = 'DISCONNECTED' WHERE account_id = '" + id + "'");

        assertThatThrownBy(() -> service.link(new UserScope(JDH), command("12345678-01", "jdh 시도")))
                .isInstanceOfSatisfying(AccountRejected.class,
                        e -> assertThat(e.code()).isEqualTo("ACCOUNT_UNAVAILABLE"));
        assertThat(f.row(id).get("user_id")).isEqualTo(YHR);
        assertThat(f.row(id).get("label")).isEqualTo("yhr 계좌");
        assertThat(f.row(id).get("link_state")).isEqualTo("DISCONNECTED");
    }

    @Test
    void 저장소가_실패하면_새_행이_남지_않는다() {
        store.failNext();

        assertThatThrownBy(() -> service.link(new UserScope(YHR), command("12345678-01", null)))
                .isInstanceOf(CredentialStoreUnavailable.class);
        assertThat(f.count()).isZero();
    }

    @Test
    void 재연동_중_저장소가_실패하면_해제_상태_그대로다() {
        UUID id = service.link(new UserScope(YHR), command("12345678-01", null)).accountId();
        f.sql("UPDATE account SET link_state = 'DISCONNECTED', credential_ref = NULL WHERE account_id = '" + id + "'");
        store.failNext();

        assertThatThrownBy(() -> service.link(new UserScope(YHR), command("12345678-01", "바꾼 이름")))
                .isInstanceOf(CredentialStoreUnavailable.class);
        assertThat(f.row(id).get("link_state")).isEqualTo("DISCONNECTED");
        assertThat(f.row(id).get("credential_ref")).isNull();
        assertThat(f.row(id).get("label")).isEqualTo("한국투자 위탁");
    }

    @Test
    void 같은_계좌를_동시에_등록하면_한쪽만_성공한다() throws Exception {
        store.pauseNext();
        CompletableFuture<AccountLinkService.LinkResult> first = CompletableFuture.supplyAsync(
                () -> service.link(new UserScope(YHR), command("12345678-01", null)));
        store.awaitPaused();   // 첫 요청이 행을 삽입하고 커밋 전에 멈췄다

        CompletableFuture<Object> second = CompletableFuture.supplyAsync(() -> {
            try {
                return service.link(new UserScope(YHR), command("12345678-01", null));
            } catch (AccountRejected e) {
                return e;
            }
        });
        awaitLockWait();       // 둘째 요청이 같은 account_ref 삽입에서 막혔다
        store.resume();

        assertThat(first.get(10, TimeUnit.SECONDS).linkState()).isEqualTo(com.stockproject.portfolio.domain.LinkState.CONNECTING);
        assertThat(second.get(10, TimeUnit.SECONDS)).isInstanceOfSatisfying(AccountRejected.class,
                e -> assertThat(e.code()).isEqualTo("ACCOUNT_ALREADY_LINKED"));
        assertThat(f.count()).isEqualTo(1);
    }

    private void awaitLockWait() throws InterruptedException {
        Instant deadline = Instant.now().plus(Duration.ofSeconds(10));
        while (f.waitingOnLock() == 0) {
            if (Instant.now().isAfter(deadline)) throw new IllegalStateException("상대 트랜잭션이 잠금을 기다리지 않았다");
            Thread.sleep(50);
        }
    }
}
```

- [ ] **Step 3: 승인을 받아 실행해 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.AccountLinkServiceTest'`

Expected: 컴파일 실패(`AccountLinkService` · `LinkCommand` 없음).

- [ ] **Step 4: 구현한다**

`LinkCommand.java`:

```java
package com.stockproject.portfolio.account;

/**
 * 검증 · 정규화를 마친 등록 요청 (설계 §3.1).
 *
 * <p>키는 앞뒤 공백을 지운 값을 쓴다 — 복사해 붙인 줄바꿈이 섞이면 증권사 호출이 실패한다.
 * label이 null이면 신규는 기본값, 재연동은 기존 값이다. toString은 값을 가린다.</p>
 */
public record LinkCommand(String appKey, String appSecret, KisAccountNumber accountNumber, String label) {

    private static final int LABEL_MAX = 30;

    public static LinkCommand of(String appKey, String appSecret, String accountNumber, String label) {
        String key = required(appKey);
        String secret = required(appSecret);
        KisAccountNumber number = KisAccountNumber.parse(accountNumber);
        String trimmedLabel = null;
        if (label != null) {
            trimmedLabel = label.strip();
            if (trimmedLabel.isEmpty() || trimmedLabel.length() > LABEL_MAX) throw AccountRejected.invalidRequest();
        }
        return new LinkCommand(key, secret, number, trimmedLabel);
    }

    private static String required(String value) {
        if (value == null || value.isBlank()) throw AccountRejected.invalidRequest();
        return value.strip();
    }

    @Override
    public String toString() { return "LinkCommand[" + accountNumber + ", label=" + label + "]"; }
}
```

`AccountLinkMapper.java`:

```java
package com.stockproject.portfolio.account;

import com.stockproject.portfolio.domain.AccountType;
import com.stockproject.portfolio.domain.LinkState;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 계좌 등록 · 해제가 쓰는 account 쿼리.
 *
 * <p>잠금 조회는 캐시를 쓰지 않는다 — 한 세션 안에서 같은 SELECT를 되풀이하면 MyBatis가 캐시한 결과를 돌려줘
 * FOR UPDATE가 DB에 가지 않는다.</p>
 */
@Mapper
public interface AccountLinkMapper {

    record NewAccount(UUID accountId, UUID userId, String accountRef, String broker, String label,
                      AccountType accountType, String credentialRef) { }

    record LockedAccount(UUID accountId, UUID userId, String accountRef, String label, LinkState linkState) { }

    record LinkedAccountRow(UUID accountId, String broker, String label, AccountType accountType,
                            String source, LinkState linkState, OffsetDateTime lastSyncedAt) { }

    /** 행이 없으면 넣고 그 id를, 같은 account_ref가 있으면 null을 돌려준다. UNIQUE 위반을 내지 않는다. */
    @Select("""
            INSERT INTO account (account_id, user_id, account_ref, broker, label, account_type, source,
                                 credential_ref, link_state)
            VALUES (#{a.accountId}, #{a.userId}, #{a.accountRef}, #{a.broker}, #{a.label}, #{a.accountType}, 'KIS',
                    #{a.credentialRef}, 'CONNECTING')
            ON CONFLICT (account_ref) DO NOTHING
            RETURNING account_id
            """)
    @Options(flushCache = Options.FlushCachePolicy.TRUE, useCache = false)
    UUID insertIfAbsent(@Param("a") NewAccount account);

    @Select("""
            SELECT account_id, user_id, account_ref, label, link_state
              FROM account WHERE account_ref = #{accountRef} FOR UPDATE
            """)
    @Options(flushCache = Options.FlushCachePolicy.TRUE, useCache = false)
    LockedAccount lockByRef(@Param("accountRef") String accountRef);

    @Select("""
            SELECT account_id, user_id, account_ref, label, link_state
              FROM account WHERE account_id = #{accountId} AND user_id = #{userId} FOR UPDATE
            """)
    @Options(flushCache = Options.FlushCachePolicy.TRUE, useCache = false)
    LockedAccount lockOwned(@Param("accountId") UUID accountId, @Param("userId") UUID userId);

    /** label이 null이면 기존 값을 둔다. */
    @Update("""
            UPDATE account
               SET link_state = 'CONNECTING', credential_ref = #{credentialRef},
                   label = COALESCE(#{label,jdbcType=VARCHAR}, label)
             WHERE account_id = #{accountId}
            """)
    void relink(@Param("accountId") UUID accountId, @Param("credentialRef") String credentialRef,
                @Param("label") String label);

    @Update("""
            UPDATE account SET link_state = 'DISCONNECTED', credential_ref = NULL
             WHERE account_id = #{accountId}
            """)
    void disconnect(@Param("accountId") UUID accountId);

    @Select("SELECT label FROM account WHERE user_id = #{userId} AND link_state <> 'DISCONNECTED'")
    @Options(flushCache = Options.FlushCachePolicy.TRUE, useCache = false)
    List<String> linkedLabels(@Param("userId") UUID userId);

    @Select("""
            SELECT account_id, broker, label, account_type, source, link_state, last_synced_at
              FROM account
             WHERE user_id = #{userId} AND link_state <> 'DISCONNECTED'
             ORDER BY account_type, label
            """)
    List<LinkedAccountRow> listLinked(@Param("userId") UUID userId);
}
```

`AccountLinkService.java`(이 과제에서는 `link`만 만든다. `unlink` · `list`는 Task 6):

```java
package com.stockproject.portfolio.account;

import com.stockproject.portfolio.auth.UserScope;
import com.stockproject.portfolio.domain.LinkState;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

/**
 * KIS 계좌 등록 · 재연동 · 해제 (설계 §4).
 *
 * <p>행을 잠근 뒤 저장소를 부르고 그다음 커밋한다. 행 잠금이 같은 계좌의 등록과 해제를 한 줄로 세우고,
 * 저장소가 실패하면 롤백되어 행과 저장소가 어긋나지 않는다.</p>
 *
 * <p>로그에는 account_id와 예외 종류만 남긴다. account_ref · 파라미터 이름 · 자격증명 값을 남기지 않는다.</p>
 */
@Service
public class AccountLinkService {

    private static final Logger log = LoggerFactory.getLogger(AccountLinkService.class);
    private static final String BROKER = "한국투자증권";

    private final AccountLinkMapper accounts;
    private final AccountRefIssuer refs;
    private final CredentialStore store;

    public AccountLinkService(AccountLinkMapper accounts, AccountRefIssuer refs, CredentialStore store) {
        this.accounts = accounts;
        this.refs = refs;
        this.store = store;
    }

    public record LinkResult(UUID accountId, LinkState linkState) { }

    @Transactional
    public LinkResult link(UserScope scope, LinkCommand command) {
        KisAccountNumber number = command.accountNumber();
        String accountRef = refs.issue(number);
        String parameter = AccountRefIssuer.parameterName(accountRef);

        String label = command.label() != null
                ? command.label() : defaultLabel(scope, number.product().defaultLabel());
        UUID accountId = accounts.insertIfAbsent(new AccountLinkMapper.NewAccount(
                UUID.randomUUID(), scope.userId(), accountRef, BROKER, label,
                number.product().accountType(), parameter));

        if (accountId == null) {
            AccountLinkMapper.LockedAccount existing = accounts.lockByRef(accountRef);
            if (!existing.userId().equals(scope.userId())) throw AccountRejected.unavailable();
            if (existing.linkState() != LinkState.DISCONNECTED) throw AccountRejected.alreadyLinked();
            accounts.relink(existing.accountId(), parameter, relinkLabel(scope, command, existing));
            accountId = existing.accountId();
        }

        try {
            store.put(parameter, new KisCredential(command.appKey(), command.appSecret(), number));
        } catch (CredentialStoreUnavailable e) {
            log.warn("자격증명 저장 실패 account_id={} cause={} aws_code={}", accountId, e.causeType(), e.awsErrorCode());
            throw e;
        }
        return new LinkResult(accountId, LinkState.CONNECTING);
    }

    /**
     * 재연동의 라벨. 요청에 있으면 그 값, 없으면 옛 값을 둔다. 옛 값이 연동 중인 다른 계좌와 겹치면 기본값을 다시 매긴다 —
     * 해제한 사이에 다른 계좌가 그 기본 라벨을 가져갔을 수 있다. null이면 옛 값을 그대로 둔다는 뜻이다.
     */
    private String relinkLabel(UserScope scope, LinkCommand command, AccountLinkMapper.LockedAccount existing) {
        if (command.label() != null) return command.label();
        if (!accounts.linkedLabels(scope.userId()).contains(existing.label())) return null;
        return defaultLabel(scope, command.accountNumber().product().defaultLabel());
    }

    /** 연동 중인 본인 계좌와 겹치지 않는 기본 라벨. 해제한 계좌의 라벨은 세지 않는다. */
    private String defaultLabel(UserScope scope, String base) {
        Set<String> taken = new HashSet<>(accounts.linkedLabels(scope.userId()));
        if (!taken.contains(base)) return base;
        for (int n = 2; ; n++) {
            String candidate = base + " " + n;
            if (!taken.contains(candidate)) return candidate;
        }
    }
}
```

- [ ] **Step 5: 승인을 받아 테스트를 돌려 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.AccountLinkServiceTest'`

Expected: PASS

동시 등록 테스트가 `상대 트랜잭션이 잠금을 기다리지 않았다`로 실패하면, `ON CONFLICT`가 진행 중인 삽입을 기다리지 않는 것이다. 그 경우 설계 §4.1의 전제가 틀린 것이므로 고치지 말고 멈춰 보고한다.

- [ ] **Step 6: 커밋(사용자가 요청한 경우)**

```bash
git add src/main/java/com/stockproject/portfolio/account src/test/java/com/stockproject/portfolio/account
git commit -m "feat: KIS 계좌를 등록하고 해제한 계좌는 같은 행으로 다시 연동한다"
```

---

### Task 6: 해제 · 목록

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/account/AccountLinkService.java`
- Test: `src/test/java/com/stockproject/portfolio/account/AccountUnlinkServiceTest.java`

**Interfaces:**
- Consumes: `AccountLinkMapper.lockOwned/disconnect/listLinked`(Task 5), `CollectionStatusPort` · `CollectionStatus`(기존 `query` 패키지), `ForbiddenAccountException`(기존 `auth`)
- Produces:
  - `void unlink(UserScope scope, UUID accountId)`
  - `List<LinkedAccount> list(UserScope scope)`
  - `record LinkedAccount(AccountLinkMapper.LinkedAccountRow row, CollectionStatus lastCollection)`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.account;

import com.stockproject.portfolio.auth.ForbiddenAccountException;
import com.stockproject.portfolio.auth.UserScope;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

import static com.stockproject.portfolio.account.AccountFixture.JDH;
import static com.stockproject.portfolio.account.AccountFixture.YHR;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** 해제와 목록 (설계 §3.3 · §4.2). */
@SpringBootTest
@AutoConfigureMockMvc   // AccountApiTest와 같은 컨텍스트를 쓰게 한다 — 컨텍스트마다 연결 풀이 생긴다
@ActiveProfiles("test")
@Import(AccountTestConfig.class)
class AccountUnlinkServiceTest {

    @Autowired AccountLinkService service;
    @Autowired AccountFixture f;
    @Autowired ControllableCredentialStore store;

    private static final String NUMBER = "12345678-01";

    @BeforeEach
    void setUp() {
        f.reset();
        store.clear();
    }

    private UUID linked(UUID user, String number) {
        return service.link(new UserScope(user),
                LinkCommand.of("test-app-key-LEAKCHECK", "test-app-secret-LEAKCHECK", number, null)).accountId();
    }

    private String parameterOf(UUID accountId) {
        return AccountRefIssuer.parameterName((String) f.row(accountId).get("account_ref"));
    }

    @Test
    void 해제하면_상태와_참조를_비우고_저장소에서_지운다() {
        UUID id = linked(YHR, NUMBER);
        String parameter = parameterOf(id);

        service.unlink(new UserScope(YHR), id);

        assertThat(f.row(id).get("link_state")).isEqualTo("DISCONNECTED");
        assertThat(f.row(id).get("credential_ref")).isNull();
        assertThat(store.get(parameter)).isEmpty();
    }

    @Test
    void 이미_해제한_계좌를_다시_해제해도_성공한다() {
        UUID id = linked(YHR, NUMBER);
        service.unlink(new UserScope(YHR), id);

        service.unlink(new UserScope(YHR), id);

        assertThat(f.row(id).get("link_state")).isEqualTo("DISCONNECTED");
    }

    @Test
    void 남의_계좌나_없는_계좌는_거부한다() {
        UUID id = linked(YHR, NUMBER);

        assertThatThrownBy(() -> service.unlink(new UserScope(JDH), id)).isInstanceOf(ForbiddenAccountException.class);
        assertThatThrownBy(() -> service.unlink(new UserScope(YHR), UUID.randomUUID()))
                .isInstanceOf(ForbiddenAccountException.class);
        assertThat(f.row(id).get("link_state")).isEqualTo("CONNECTING");
    }

    @Test
    void 저장소_삭제가_실패하면_연동_상태_그대로이고_다시_해제할_수_있다() {
        UUID id = linked(YHR, NUMBER);
        String parameter = parameterOf(id);
        store.failNext();

        assertThatThrownBy(() -> service.unlink(new UserScope(YHR), id)).isInstanceOf(CredentialStoreUnavailable.class);
        assertThat(f.row(id).get("link_state")).isEqualTo("CONNECTING");
        assertThat(f.row(id).get("credential_ref")).isEqualTo(parameter);
        assertThat(store.get(parameter)).isPresent();

        service.unlink(new UserScope(YHR), id);
        assertThat(store.get(parameter)).isEmpty();
    }

    @Test
    void 해제가_끝나기_전의_재등록은_해제_뒤에_진행되어_새_값이_남는다() throws Exception {
        UUID id = linked(YHR, NUMBER);
        String parameter = parameterOf(id);

        store.pauseNext();
        CompletableFuture<Void> unlink = CompletableFuture.runAsync(() -> service.unlink(new UserScope(YHR), id));
        store.awaitPaused();   // 해제가 행을 잠그고 저장소 삭제에서 멈췄다

        CompletableFuture<AccountLinkService.LinkResult> relink = CompletableFuture.supplyAsync(() ->
                service.link(new UserScope(YHR), LinkCommand.of("new-key", "new-secret", NUMBER, null)));
        awaitLockWait();       // 재등록의 삽입이 해제 트랜잭션이 끝나기를 기다린다
        store.resume();

        unlink.get(10, TimeUnit.SECONDS);
        assertThat(relink.get(10, TimeUnit.SECONDS).accountId()).isEqualTo(id);
        assertThat(f.row(id).get("link_state")).isEqualTo("CONNECTING");
        assertThat(store.get(parameter).orElseThrow().appKey()).isEqualTo("new-key");
    }

    @Test
    void 목록은_연동_중인_본인_계좌와_최근_수집_결과를_담는다() {
        UUID kept = linked(YHR, NUMBER);
        UUID removed = linked(YHR, "11112222-01");
        linked(JDH, "87654321-22");
        service.unlink(new UserScope(YHR), removed);
        String ref = (String) f.row(kept).get("account_ref");
        f.sql("""
                INSERT INTO collection_run (run_id, account_ref, requested_by, as_of, requested_at, state, finished_at, failure_reason)
                VALUES ('%s', '%s', 'SCHEDULE', '2026-10-18', '2026-10-18T23:00:00+09', 'FAILED', '2026-10-18T23:05:00+09', 'SOURCE_API_ERROR')
                """.formatted(UUID.randomUUID(), ref));

        var accounts = service.list(new UserScope(YHR));

        assertThat(accounts).singleElement().satisfies(a -> {
            assertThat(a.row().accountId()).isEqualTo(kept);
            assertThat(a.lastCollection().state()).isEqualTo("FAILED");
            assertThat(a.lastCollection().asOf()).isEqualTo(LocalDate.of(2026, 10, 18));
            assertThat(a.lastCollection().failureReason()).isEqualTo("SOURCE_API_ERROR");
        });
    }

    @Test
    void 수집이_없는_계좌의_최근_수집은_null이다() {
        linked(YHR, NUMBER);

        assertThat(service.list(new UserScope(YHR))).singleElement()
                .satisfies(a -> assertThat(a.lastCollection()).isNull());
    }

    private void awaitLockWait() throws InterruptedException {
        Instant deadline = Instant.now().plus(Duration.ofSeconds(10));
        while (f.waitingOnLock() == 0) {
            if (Instant.now().isAfter(deadline)) throw new IllegalStateException("재등록이 잠금을 기다리지 않았다");
            Thread.sleep(50);
        }
    }
}
```

`FailureReasons.sanitize`가 `SOURCE_API_ERROR`를 다른 값으로 바꾸면, 위 기대값을 그 함수의 출력에 맞춘다. 원본은 `query/FailureReasons.java`에서 확인한다.

- [ ] **Step 2: 승인을 받아 실행해 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.AccountUnlinkServiceTest'`

Expected: 컴파일 실패(`unlink` · `list` 없음).

- [ ] **Step 3: 구현한다**

설계 §4.2의 소유 검사(`AccountOwnershipGuard`)와 행 잠금을 `lockOwned(accountId, userId)` 한 문장으로 합친다. Guard도 `link_state`로 거르지 않는 본인 계좌 집합을 보므로 판정이 같고, 검사와 잠금 사이에 틈이 없다.

`AccountLinkService.java` 생성자에 `CollectionStatusPort`를 더한다. import에 `com.stockproject.portfolio.auth.ForbiddenAccountException`, `com.stockproject.portfolio.query.CollectionStatus`, `com.stockproject.portfolio.query.CollectionStatusPort`, `java.util.List`, `java.util.Map`을 더한다.

```java
    private final CollectionStatusPort collections;

    public AccountLinkService(AccountLinkMapper accounts, AccountRefIssuer refs, CredentialStore store,
                              CollectionStatusPort collections) {
        this.accounts = accounts;
        this.refs = refs;
        this.store = store;
        this.collections = collections;
    }

    public record LinkedAccount(AccountLinkMapper.LinkedAccountRow row, CollectionStatus lastCollection) { }

    /**
     * 연동 해제. 행을 잠그고 상태를 바꾼 뒤 저장소에서 지우고 커밋한다.
     * 저장소가 실패하면 롤백되어 계좌가 목록에 남으므로 사용자가 다시 해제할 수 있다.
     * 본인 계좌가 아니면(없는 id 포함) 거부한다.
     */
    @Transactional
    public void unlink(UserScope scope, UUID accountId) {
        AccountLinkMapper.LockedAccount account = accounts.lockOwned(accountId, scope.userId());
        if (account == null) throw new ForbiddenAccountException();

        accounts.disconnect(accountId);
        try {
            store.delete(AccountRefIssuer.parameterName(account.accountRef()));
        } catch (CredentialStoreUnavailable e) {
            log.warn("자격증명 삭제 실패 account_id={} cause={} aws_code={}", accountId, e.causeType(), e.awsErrorCode());
            throw e;
        }
    }

    /** 연동 중인 본인 계좌. 최근 수집 결과는 계좌별 뷰와 같은 원천에서 온다. */
    @Transactional(readOnly = true)
    public List<LinkedAccount> list(UserScope scope) {
        Map<UUID, CollectionStatus> last = collections.lastCollectionByAccount(scope);
        return accounts.listLinked(scope.userId()).stream()
                .map(row -> new LinkedAccount(row, last.get(row.accountId())))
                .toList();
    }
```

- [ ] **Step 4: 승인을 받아 테스트를 돌려 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.*'`

Expected: PASS

- [ ] **Step 5: 커밋(사용자가 요청한 경우)**

```bash
git add src/main/java/com/stockproject/portfolio/account src/test/java/com/stockproject/portfolio/account
git commit -m "feat: 계좌 연동을 해제하고 연동 중인 계좌를 최근 수집 결과와 함께 나열한다"
```

---

### Task 7: 컨트롤러 · DTO · 전용 예외 처리기

**Files:**
- Create: `src/main/java/com/stockproject/portfolio/account/dto/LinkAccountRequest.java`
- Create: `src/main/java/com/stockproject/portfolio/account/dto/LinkAccountResponse.java`
- Create: `src/main/java/com/stockproject/portfolio/account/dto/AccountDto.java`
- Create: `src/main/java/com/stockproject/portfolio/account/dto/AccountListResponse.java`
- Create: `src/main/java/com/stockproject/portfolio/account/AccountController.java`
- Create: `src/main/java/com/stockproject/portfolio/account/AccountExceptionHandler.java`
- Test: `src/test/java/com/stockproject/portfolio/account/AccountApiTest.java`

**Interfaces:**
- Consumes: `AccountLinkService.link/unlink/list` · `LinkResult` · `LinkedAccount`(Task 5 · 6), `LinkCommand.of`(Task 5), `AccountRejected` · `CredentialStoreUnavailable`, `ApiError`(기존 `api.dto`), `CollectionStatus`(기존)
- Produces: HTTP `GET /accounts` · `POST /accounts` · `DELETE /accounts/{accountId}`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.account;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.stockproject.portfolio.snapshot.CredentialFiller;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import java.nio.charset.StandardCharsets;
import java.util.UUID;

import static com.stockproject.portfolio.account.AccountFixture.YHR;
import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

/** /accounts 엔드포인트 (설계 §3 · §6.3 · §8). */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(AccountTestConfig.class)
@ExtendWith(OutputCaptureExtension.class)
class AccountApiTest {

    private static final String PASSWORD = "local-dev-password";
    private static final String KEY = "test-app-key-LEAKCHECK";
    private static final String SECRET = "test-app-secret-LEAKCHECK";
    private static final String NUMBER = "12345678-01";

    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper json;
    @Autowired AccountFixture f;
    @Autowired ControllableCredentialStore store;
    @Autowired CredentialFiller filler;

    @BeforeEach
    void setUp() {
        f.reset();
        store.clear();
    }

    @Test
    void 등록하면_202와_연동_중_상태를_돌려준다() throws Exception {
        MockHttpServletResponse response = register("yhr@a.com", NUMBER, null);

        assertThat(response.getStatus()).isEqualTo(202);
        JsonNode body = json.readTree(body(response));
        assertThat(body.get("link_state").asText()).isEqualTo("CONNECTING");
        assertThat(body.has("challenge")).isTrue();
        assertThat(body.get("challenge").isNull()).isTrue();
        assertThat(f.row(UUID.fromString(body.get("account_id").asText())).get("user_id")).isEqualTo(YHR);
    }

    @Test
    void 공백을_지운_키를_저장한다() throws Exception {
        String id = accountIdOf(perform(post("/accounts"), "yhr@a.com", """
                {"app_key": "  %s\\n", "app_secret": "\\t%s ", "account_number": " %s "}
                """.formatted(KEY, SECRET, NUMBER)));

        String parameter = (String) f.row(UUID.fromString(id)).get("credential_ref");
        assertThat(store.get(parameter).orElseThrow().appKey()).isEqualTo(KEY);
        assertThat(store.get(parameter).orElseThrow().appSecret()).isEqualTo(SECRET);
    }

    @Test
    void 빈_라벨은_거부하고_기존_값을_유지한다() throws Exception {
        String id = accountIdOf(register("yhr@a.com", NUMBER, "원래 이름"));
        assertThat(perform(delete("/accounts/" + id), "yhr@a.com", null).getStatus()).isEqualTo(204);

        MockHttpServletResponse response = register("yhr@a.com", NUMBER, "   ");

        assertThat(response.getStatus()).isEqualTo(400);
        assertThat(code(response)).isEqualTo("INVALID_ACCOUNT_REQUEST");
        assertThat(f.row(UUID.fromString(id)).get("label")).isEqualTo("원래 이름");
        assertThat(f.row(UUID.fromString(id)).get("link_state")).isEqualTo("DISCONNECTED");
    }

    @Test
    void 거부_코드와_상태() throws Exception {
        register("yhr@a.com", NUMBER, null);

        assertStatus(register("yhr@a.com", NUMBER, null), 409, "ACCOUNT_ALREADY_LINKED");
        assertStatus(register("jdh@a.com", NUMBER, null), 409, "ACCOUNT_UNAVAILABLE");
        assertStatus(register("yhr@a.com", "12345678-29", null), 400, "UNSUPPORTED_ACCOUNT_PRODUCT");
        assertStatus(register("yhr@a.com", "1234-01", null), 400, "INVALID_ACCOUNT_REQUEST");
        assertStatus(perform(post("/accounts"), "yhr@a.com", "{\"app_key\": "), 400, "INVALID_ACCOUNT_REQUEST");
        assertStatus(perform(post("/accounts"), "yhr@a.com", "{}"), 400, "INVALID_ACCOUNT_REQUEST");
    }

    @Test
    void 본문이_없으면_400() throws Exception {
        MockHttpServletResponse response = mockMvc.perform(post("/accounts")
                        .header("Authorization", "Bearer " + tokenOf("yhr@a.com"))
                        .contentType(MediaType.APPLICATION_JSON))
                .andReturn().getResponse();

        assertStatus(response, 400, "INVALID_ACCOUNT_REQUEST");
    }

    @Test
    void 저장소_장애는_503() throws Exception {
        store.failNext();

        assertStatus(register("yhr@a.com", NUMBER, null), 503, "CREDENTIAL_STORE_UNAVAILABLE");
        assertThat(f.count()).isZero();
    }

    @Test
    void 해제는_204이고_두_번째도_204다() throws Exception {
        String id = accountIdOf(register("yhr@a.com", NUMBER, null));

        assertThat(perform(delete("/accounts/" + id), "yhr@a.com", null).getStatus()).isEqualTo(204);
        assertThat(perform(delete("/accounts/" + id), "yhr@a.com", null).getStatus()).isEqualTo(204);
        assertThat(f.row(UUID.fromString(id)).get("link_state")).isEqualTo("DISCONNECTED");
    }

    @Test
    void 남의_계좌_없는_계좌_UUID가_아닌_id의_해제는_403() throws Exception {
        String id = accountIdOf(register("yhr@a.com", NUMBER, null));

        assertStatus(perform(delete("/accounts/" + id), "jdh@a.com", null), 403, "FORBIDDEN_ACCOUNT");
        assertStatus(perform(delete("/accounts/" + UUID.randomUUID()), "yhr@a.com", null), 403, "FORBIDDEN_ACCOUNT");
        assertStatus(perform(delete("/accounts/not-a-uuid"), "yhr@a.com", null), 403, "FORBIDDEN_ACCOUNT");
    }

    @Test
    void 해제_중_저장소_장애는_503이고_계좌는_목록에_남는다() throws Exception {
        String id = accountIdOf(register("yhr@a.com", NUMBER, null));
        store.failNext();

        assertStatus(perform(delete("/accounts/" + id), "yhr@a.com", null), 503, "CREDENTIAL_STORE_UNAVAILABLE");
        assertThat(body(perform(get("/accounts"), "yhr@a.com", null))).contains(id);
        assertThat(perform(delete("/accounts/" + id), "yhr@a.com", null).getStatus()).isEqualTo(204);
    }

    @Test
    void 목록은_본인의_연동_중인_계좌만_내리고_내부_식별자를_싣지_않는다() throws Exception {
        String mine = accountIdOf(register("yhr@a.com", NUMBER, null));
        String removed = accountIdOf(register("yhr@a.com", "11112222-01", null));
        String theirs = accountIdOf(register("jdh@a.com", "87654321-22", null));
        perform(delete("/accounts/" + removed), "yhr@a.com", null);

        MockHttpServletResponse response = perform(get("/accounts"), "yhr@a.com", null);
        JsonNode accounts = json.readTree(body(response)).get("accounts");

        assertThat(response.getStatus()).isEqualTo(200);
        assertThat(accounts).hasSize(1);
        JsonNode a = accounts.get(0);
        assertThat(a.get("account_id").asText()).isEqualTo(mine);
        assertThat(a.get("broker").asText()).isEqualTo("한국투자증권");
        assertThat(a.get("label").asText()).isEqualTo("한국투자 위탁");
        assertThat(a.get("account_type").asText()).isEqualTo("GENERAL");
        assertThat(a.get("source").asText()).isEqualTo("KIS");
        assertThat(a.get("link_state").asText()).isEqualTo("CONNECTING");
        assertThat(a.get("last_synced_at").isNull()).isTrue();
        assertThat(a.get("last_collection").isNull()).isTrue();
        assertThat(body(response)).doesNotContain(theirs, removed, "account_ref", "credential_ref", "ar_", "/stock-project/");
    }

    @Test
    void 토큰이_없으면_401() throws Exception {
        assertStatus(mockMvc.perform(get("/accounts")).andReturn().getResponse(), 401, "UNAUTHENTICATED");
        assertStatus(mockMvc.perform(post("/accounts").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andReturn().getResponse(), 401, "UNAUTHENTICATED");
    }

    @Test
    void 다른_컨트롤러의_깨진_JSON은_계좌_오류_코드가_아니다() throws Exception {
        MockHttpServletResponse response = mockMvc.perform(post("/auth/login")
                        .contentType(MediaType.APPLICATION_JSON).content("{\"email\": "))
                .andReturn().getResponse();

        assertThat(body(response)).doesNotContain("INVALID_ACCOUNT_REQUEST");
    }

    @Test
    void 등록한_계좌에_생성기가_자격증명_참조를_채우고_해제하면_채우지_않는다() throws Exception {
        String id = accountIdOf(register("yhr@a.com", NUMBER, null));
        String ref = (String) f.row(UUID.fromString(id)).get("account_ref");
        UUID before = requested(ref, "2026-10-18");

        filler.fillOnce();
        assertThat(credentialOf(before)).isEqualTo("/stock-project/accounts/" + ref);

        perform(delete("/accounts/" + id), "yhr@a.com", null);
        UUID after = requested(ref, "2026-10-20");
        filler.fillOnce();
        assertThat(credentialOf(after)).isNull();
    }

    @Test
    void 자격증명과_계좌번호가_로그와_응답에_남지_않는다(CapturedOutput output) throws Exception {
        StringBuilder bodies = new StringBuilder();
        String id = accountIdOf(register("yhr@a.com", NUMBER, null));
        bodies.append(body(register("yhr@a.com", NUMBER, null)));
        bodies.append(body(register("jdh@a.com", NUMBER, null)));
        bodies.append(body(register("yhr@a.com", "12345678-29", null)));
        bodies.append(body(register("yhr@a.com", "12345678-0x", null)));
        store.failNext();
        bodies.append(body(register("yhr@a.com", "11112222-01", null)));
        store.failNext();
        bodies.append(body(perform(delete("/accounts/" + id), "yhr@a.com", null)));
        bodies.append(body(perform(get("/accounts"), "yhr@a.com", null)));

        for (String secret : new String[]{KEY, SECRET, "12345678", "11112222", "1234567801"}) {
            assertThat(output.getAll()).doesNotContain(secret);
            assertThat(bodies.toString()).doesNotContain(secret);
        }
        assertThat(output.getAll()).doesNotContain("/stock-project/accounts/");
    }

    // ── 도우미 ──

    private MockHttpServletResponse register(String email, String number, String label) throws Exception {
        String labelJson = label == null ? "" : ", \"label\": \"" + label + "\"";
        return perform(post("/accounts"), email, """
                {"app_key": "%s", "app_secret": "%s", "account_number": "%s"%s}
                """.formatted(KEY, SECRET, number, labelJson));
    }

    private MockHttpServletResponse perform(MockHttpServletRequestBuilder request, String email, String content) throws Exception {
        request.header("Authorization", "Bearer " + tokenOf(email));
        if (content != null) request.contentType(MediaType.APPLICATION_JSON).content(content);
        return mockMvc.perform(request).andReturn().getResponse();
    }

    private String accountIdOf(MockHttpServletResponse response) throws Exception {
        assertThat(response.getStatus()).isEqualTo(202);
        return json.readTree(body(response)).get("account_id").asText();
    }

    private void assertStatus(MockHttpServletResponse response, int status, String code) throws Exception {
        assertThat(response.getStatus()).isEqualTo(status);
        assertThat(code(response)).isEqualTo(code);
    }

    private String code(MockHttpServletResponse response) throws Exception {
        return json.readTree(body(response)).get("error").get("code").asText();
    }

    private UUID requested(String ref, String asOf) {
        UUID id = UUID.randomUUID();
        f.sql("""
                INSERT INTO collection_run (run_id, account_ref, requested_by, as_of, requested_at, state)
                VALUES ('%s', '%s', 'SCHEDULE', '%s', now(), 'REQUESTED')
                """.formatted(id, ref, asOf));
        return id;
    }

    private String credentialOf(UUID runId) {
        return f.credentialOfRun(runId);
    }

    private String tokenOf(String email) throws Exception {
        String response = mockMvc.perform(post("/auth/login").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\": \"%s\", \"password\": \"%s\"}".formatted(email, PASSWORD)))
                .andReturn().getResponse().getContentAsString();
        return json.readTree(response).get("access_token").asText();
    }

    private static String body(MockHttpServletResponse response) throws Exception {
        return response.getContentAsString(StandardCharsets.UTF_8);
    }
}
```

`AccountFixture`에 다음 메서드를 더한다:

```java
    public String credentialOfRun(UUID runId) {
        return jdbc.sql("SELECT credential_ref FROM collection_run WHERE run_id = :id").param("id", runId)
                .query(String.class).optional().orElse(null);
    }
```

- [ ] **Step 2: 승인을 받아 실행해 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.AccountApiTest'`

Expected: 컴파일 실패(`AccountFixture.credentialOfRun` · DTO 없음). 컴파일되면 FAIL(컨트롤러가 없다).

- [ ] **Step 3: 구현한다**

`dto/LinkAccountRequest.java`:

```java
package com.stockproject.portfolio.account.dto;

/** POST /accounts 본문. toString은 값을 가린다 — 요청이 로그에 실려도 새지 않게. */
public record LinkAccountRequest(String appKey, String appSecret, String accountNumber, String label) {

    @Override
    public String toString() { return "LinkAccountRequest[***]"; }
}
```

`dto/LinkAccountResponse.java`:

```java
package com.stockproject.portfolio.account.dto;

import com.stockproject.portfolio.domain.LinkState;

import java.util.UUID;

/** 202 응답. KIS 등록은 추가인증이 없어 challenge가 늘 null이다 (설계 §3.1). */
public record LinkAccountResponse(UUID accountId, LinkState linkState, Object challenge) { }
```

`dto/AccountDto.java`:

```java
package com.stockproject.portfolio.account.dto;

import com.stockproject.portfolio.domain.AccountType;
import com.stockproject.portfolio.domain.LinkState;
import com.stockproject.portfolio.query.CollectionStatus;

import java.time.OffsetDateTime;
import java.util.UUID;

/** GET /accounts 한 행. account_ref · credential_ref를 싣지 않는다. */
public record AccountDto(UUID accountId, String broker, String label, AccountType accountType, String source,
                         LinkState linkState, OffsetDateTime lastSyncedAt, CollectionStatus lastCollection) { }
```

`dto/AccountListResponse.java`:

```java
package com.stockproject.portfolio.account.dto;

import java.util.List;

public record AccountListResponse(List<AccountDto> accounts) { }
```

`AccountController.java`:

```java
package com.stockproject.portfolio.account;

import com.stockproject.portfolio.account.dto.AccountDto;
import com.stockproject.portfolio.account.dto.AccountListResponse;
import com.stockproject.portfolio.account.dto.LinkAccountRequest;
import com.stockproject.portfolio.account.dto.LinkAccountResponse;
import com.stockproject.portfolio.auth.UserScope;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

/** KIS 계좌 등록 · 해제 · 목록 (스펙 §8.1, 설계 §3). */
@RestController
@RequestMapping("/accounts")
public class AccountController {

    private final AccountLinkService service;

    public AccountController(AccountLinkService service) { this.service = service; }

    @GetMapping
    public AccountListResponse list(UserScope scope) {
        return new AccountListResponse(service.list(scope).stream()
                .map(a -> new AccountDto(a.row().accountId(), a.row().broker(), a.row().label(),
                        a.row().accountType(), a.row().source(), a.row().linkState(), a.row().lastSyncedAt(),
                        a.lastCollection()))
                .toList());
    }

    /** 첫 수집은 다음 EOD 실행이 한다 — 등록은 수집을 요청하지 않는다(설계 §2.1). */
    @PostMapping
    public ResponseEntity<LinkAccountResponse> link(UserScope scope, @RequestBody LinkAccountRequest body) {
        LinkCommand command = LinkCommand.of(body.appKey(), body.appSecret(), body.accountNumber(), body.label());
        AccountLinkService.LinkResult result = service.link(scope, command);
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(new LinkAccountResponse(result.accountId(), result.linkState(), null));
    }

    @DeleteMapping("/{accountId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void unlink(UserScope scope, @PathVariable UUID accountId) {
        service.unlink(scope, accountId);
    }
}
```

`AccountExceptionHandler.java`:

```java
package com.stockproject.portfolio.account;

import com.stockproject.portfolio.api.dto.ApiError;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.sql.SQLException;

/**
 * 계좌 컨트롤러 전용 오류 변환 (설계 §3.5 · §6.3). 다른 컨트롤러의 오류는 ApiExceptionHandler가 맡는다.
 *
 * <p>예외 메시지는 응답에도 로그에도 내보내지 않는다. JSON 파싱 메시지에는 원문 조각이, PostgreSQL 제약 위반 메시지에는
 * account_ref · credential_ref 값이 들어 있다.</p>
 */
@RestControllerAdvice(assignableTypes = AccountController.class)
@Order(Ordered.HIGHEST_PRECEDENCE)
public class AccountExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(AccountExceptionHandler.class);

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ApiError> unreadable(HttpMessageNotReadableException e) {
        AccountRejected rejected = AccountRejected.invalidRequest();
        return ResponseEntity.status(rejected.status()).body(ApiError.of(rejected.code(), rejected.getMessage()));
    }

    /** UUID가 아닌 id는 어느 사용자의 계좌도 아니다. */
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ApiError> notAnId(MethodArgumentTypeMismatchException e) {
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(ApiError.of("FORBIDDEN_ACCOUNT", "요청한 계좌 중 본인 소유가 아닌 것이 있습니다"));
    }

    @ExceptionHandler(AccountRejected.class)
    public ResponseEntity<ApiError> rejected(AccountRejected e) {
        return ResponseEntity.status(e.status()).body(ApiError.of(e.code(), e.getMessage()));
    }

    @ExceptionHandler(CredentialStoreUnavailable.class)
    public ResponseEntity<ApiError> storeUnavailable(CredentialStoreUnavailable e) {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(ApiError.of("CREDENTIAL_STORE_UNAVAILABLE",
                        "계좌 자격증명 저장소에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요"));
    }

    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<ApiError> database(DataAccessException e) {
        log.error("계좌 요청 처리 중 DB 오류 type={} sqlstate={}", e.getClass().getSimpleName(), sqlState(e));
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiError.of("INTERNAL_ERROR", "요청을 처리하지 못했습니다"));
    }

    private static String sqlState(Throwable e) {
        for (Throwable t = e; t != null; t = t.getCause()) {
            if (t instanceof SQLException sql) return sql.getSQLState();
        }
        return null;
    }
}
```

- [ ] **Step 4: 승인을 받아 테스트를 돌려 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.account.*'`

Expected: PASS

- [ ] **Step 5: 커밋(사용자가 요청한 경우)**

```bash
git add src/main/java/com/stockproject/portfolio/account src/test/java/com/stockproject/portfolio/account
git commit -m "feat: 계좌 등록 · 해제 · 목록 API를 연다"
```

---

### Task 8: 오류 디스패치가 401로 바뀌지 않게

**Files:**
- Modify: `src/main/java/com/stockproject/portfolio/auth/SecurityConfig.java`(`authorizeHttpRequests` 블록)
- Test: `src/test/java/com/stockproject/portfolio/auth/ErrorDispatchTest.java`

**Interfaces:**
- Consumes: `/auth/login`, `POST /accounts`(Task 7)
- Produces: ERROR 디스패치 허용

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```java
package com.stockproject.portfolio.auth;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 컨트롤러 밖에서 끝난 오류(/error로 넘어간 것)가 인증 실패로 바뀌지 않는지 실제 서블릿 경로로 본다.
 * MockMvc는 ERROR 디스패치를 하지 않아 이 경로를 지나지 않는다.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class ErrorDispatchTest {

    @Autowired TestRestTemplate http;
    @Autowired ObjectMapper json;

    @Test
    void 지원하지_않는_형식은_415() throws Exception {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token());
        headers.setContentType(MediaType.TEXT_PLAIN);

        ResponseEntity<String> response = http.postForEntity("/accounts", new HttpEntity<>("x", headers), String.class);

        assertThat(response.getStatusCode().value()).isEqualTo(415);
    }

    @Test
    void Content_Type이_없어도_401이_아니다() throws Exception {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token());

        ResponseEntity<String> response = http.postForEntity("/accounts", new HttpEntity<>(new byte[]{1}, headers), String.class);

        assertThat(response.getStatusCode().value()).isEqualTo(415);
    }

    private String token() throws Exception {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        String body = http.postForObject("/auth/login", new HttpEntity<>(
                "{\"email\": \"yhr@a.com\", \"password\": \"local-dev-password\"}", headers), String.class);
        return json.readTree(body).get("access_token").asText();
    }
}
```

- [ ] **Step 2: 승인을 받아 실행해 실패를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.auth.ErrorDispatchTest'`

Expected: FAIL — `expected: 415 but was: 401`

`401`이 아니라 `415`로 처음부터 통과하면 설계 §3.5의 전제가 틀린 것이다. Step 3을 하지 말고 결과를 보고한다.

- [ ] **Step 3: 구현한다**

`SecurityConfig.filterChain`의 `authorizeHttpRequests`를 다음처럼 바꾸고, import에 `jakarta.servlet.DispatcherType`을 더한다. 클래스 Javadoc에 아래 문단을 더한다.

```java
                .authorizeHttpRequests(requests -> requests
                        .dispatcherTypeMatchers(DispatcherType.ERROR).permitAll()
                        .requestMatchers("/auth/login").permitAll()
                        .requestMatchers("/actuator/health", "/actuator/health/**").permitAll()
                        .anyRequest().authenticated())
```

```java
 * <p>오류 디스패치(/error)는 연다. JWT 필터는 요청마다 한 번만 돌아 오류 디스패치에서는 인증이 비어 있고,
 * 막으면 컨트롤러 밖에서 끝난 오류(415 · 처리하지 않은 예외)가 모두 401로 바뀐다 — 클라이언트는 401을 로그아웃으로 다룬다.
 * 원래 요청은 이미 인가를 통과했다.</p>
```

- [ ] **Step 4: 승인을 받아 테스트를 돌려 통과를 확인한다**

Run: `./gradlew test --tests 'com.stockproject.portfolio.auth.*'`

Expected: PASS(기존 `LoginApiTest` 등 포함)

- [ ] **Step 5: 커밋(사용자가 요청한 경우)**

```bash
git add src/main/java/com/stockproject/portfolio/auth/SecurityConfig.java src/test/java/com/stockproject/portfolio/auth/ErrorDispatchTest.java
git commit -m "fix: 오류 디스패치가 인증 실패로 바뀌지 않게 한다"
```

---

### Task 9: 아키텍처 규칙과 전체 테스트

**Files:**
- Modify: `src/test/java/com/stockproject/portfolio/ArchitectureRulesTest.java`

**Interfaces:**
- Consumes: `CredentialStore`(Task 3)

- [ ] **Step 1: 규칙을 더한다**

`ArchitectureRulesTest`에 메서드를 더하고 import `com.stockproject.portfolio.account.CredentialStore`를 더한다.

```java
    /** 자격증명 저장소를 부르는 길은 계좌 연동 하나다 — 값을 다루는 코드를 한 패키지에 가둔다. */
    @Test
    void 자격증명_저장소는_계좌_패키지만_쓴다() {
        ArchRule rule = noClasses()
                .that().resideOutsideOfPackage("com.stockproject.portfolio.account..")
                .should().dependOnClassesThat().areAssignableTo(CredentialStore.class)
                .because("자격증명 값이 지나가는 코드를 계좌 연동 패키지 안에 둔다");
        rule.check(classes);
    }
```

- [ ] **Step 2: 전체 테스트를 사용자에게 묻고, 승인되면 실행한다**

Run: `./gradlew test`

Expected: `BUILD SUCCESSFUL`. 기존 테스트가 깨지면 원인을 보고한다. 특히 다음 둘이 원인인지 확인한다.
- 새 `application-test.yaml` 설정(연결 풀 크기 포함). `too many clients already`가 나오면 컨텍스트 수와 풀 크기를 본다
- `AccountFixture.reset()`이 비우는 표(다른 테스트 클래스는 각자 `@Sql`이나 자기 픽스처로 채운다)

- [ ] **Step 3: 커밋(사용자가 요청한 경우)**

```bash
git add src/test/java/com/stockproject/portfolio/ArchitectureRulesTest.java
git commit -m "test: 자격증명 저장소를 계좌 연동 패키지만 쓰는지 본다"
```

---

### Task 10: 배포 매니페스트 · 운영 문서 · 반영 절차

**Files:**
- Modify: `k8s/deployment.yaml`(`env:` 목록)
- Create: `docs/ops/account-credentials.md`

**Interfaces:**
- Consumes: 환경변수 `CREDENTIAL_STORE` · `AWS_REGION` · `ACCOUNT_REF_SALT` · `AWS_ACCESS_KEY_ID` · `AWS_SECRET_ACCESS_KEY`(Task 2 · 3 · 4)

- [ ] **Step 1: 매니페스트에 env를 더한다**

`k8s/deployment.yaml`의 `EXPO_ACCESS_TOKEN` 항목 다음에 더한다:

```yaml
            # 계좌 자격증명 저장소. 백엔드는 SSM /stock-project/accounts/* 에 쓰고 지우기만 한다.
            - name: CREDENTIAL_STORE
              value: ssm
            - name: AWS_REGION
              value: ap-northeast-2
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: portfolio-api
                  key: AWS_ACCESS_KEY_ID
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: portfolio-api
                  key: AWS_SECRET_ACCESS_KEY
            # account_ref를 만드는 HMAC 키. 바뀌면 같은 계좌가 다른 값을 받는다 — 백업은 SSM에 있다.
            - name: ACCOUNT_REF_SALT
              valueFrom:
                secretKeyRef:
                  name: portfolio-api
                  key: ACCOUNT_REF_SALT
```

- [ ] **Step 2: 운영 문서를 쓴다**

`docs/ops/account-credentials.md`:

````markdown
# 계좌 자격증명 운영

계좌 등록 API(`POST /accounts`)는 KIS 앱키 · 시크릿 · 계좌번호를 SSM SecureString `/stock-project/accounts/<account_ref>`에 쓰고,
해제(`DELETE /accounts/{id}`)는 그 파라미터를 지운다. 설계는 docs 저장소
`yhr/specs/portfolio-management/2026-10-16-account-link-api-design.md`다.

## 지키는 것

- 실제 키는 같은 LAN 주소나 `kubectl port-forward`의 `localhost`로 연결했을 때만 입력한다. API는 TLS 없이 평문 HTTP이고,
  위탁(01) 앱키는 주문까지 낼 수 있다. 공인 IP로 노출된 경로에서는 등록하지 않는다.
- 키 · 계좌번호를 저장소 · 문서 · 채팅 · 이슈에 남기지 않는다. 문서 샘플은 `43******-01`처럼 가린다.
- 소금(`ACCOUNT_REF_SALT`)은 바꾸지 않는다. 바뀌면 같은 계좌가 다른 `account_ref`를 받아, 해제했던 계좌의 과거와
  끊기고 같은 계좌를 두 행으로 등록할 수 있게 된다.

## 구성

| 대상 | 값 |
|---|---|
| IAM 사용자 `portfolio-api-credentials` | 인라인 정책: `ssm:PutParameter` · `ssm:DeleteParameter`, 리소스 `arn:aws:ssm:ap-northeast-2:394686422456:parameter/stock-project/accounts/*` |
| k8s Secret `portfolio-api` | `AWS_ACCESS_KEY_ID` · `AWS_SECRET_ACCESS_KEY`(위 사용자) · `ACCOUNT_REF_SALT` |
| 소금 백업 | SSM SecureString `/stock-project/backend/account-ref-salt`. 위 IAM 사용자는 이 경로에 권한이 없다 |
| 읽는 쪽 | 데이터 워커(IAM 사용자 `dataeng-pipeline`)가 `collection_run.credential_ref`로 받은 이름을 `ssm:GetParameter`로 읽는다 |

## 소금 만들기

```bash
openssl rand -base64 48 | tr -d '\n'; echo
```

출력(64자)을 Secret과 SSM 백업에 같은 값으로 넣는다. 명령줄 인자로 다른 명령에 넘기지 말고 붙여넣기로 넣는다.

## 처음 켜는 순서

1. IAM 사용자와 정책을 만들고 액세스 키를 발급한다.
2. 소금을 만들어 SSM 백업에 넣는다.
3. Secret `portfolio-api`에 세 키를 더한다.
4. 가짜 파라미터로 쓰기 · 지우기를 확인한다(위 IAM 사용자의 키로). `aws/ssm` 키 사용에 KMS 권한이 따로 필요한지 여기서 드러난다.
   ```bash
   aws ssm put-parameter --name /stock-project/accounts/ar_smoketest --type SecureString \
     --value '{"app_key":"x","app_secret":"x","cano":"00000000","acnt_prdt_cd":"01"}' --overwrite
   aws ssm delete-parameter --name /stock-project/accounts/ar_smoketest
   ```
5. 이미지를 배포한다(main 머지 → CI → ArgoCD). Secret보다 먼저 배포하면 기동 검사에 걸려 파드가 뜨지 않는다.

## 등록한 계좌가 수집되려면

- 보유 스냅샷 생성기가 켜져 있다(`SNAPSHOT_RUNTIME_ENABLED=true`). 꺼져 있으면 EOD 행에 `credential_ref`가 채워지지 않는다.
- 데이터 DAG `collection_run_daily`가 켜져 있다.
- 같은 실계좌를 수집하는 `kis_account_daily`는 멈춘다.

## 남은 파라미터 정리

등록 때 SSM에 쓴 뒤 DB 커밋이 실패하면 행 없는 파라미터가 남을 수 있다. 같은 계좌의 다음 등록이 덮어쓴다.
따로 지워야 하면 `account` 표에 그 `account_ref`의 `CONNECTING` · `CONNECTED` 행이 없는 것을 먼저 확인하고 지운다.
````

- [ ] **Step 3: 커밋(사용자가 요청한 경우)**

```bash
git add k8s/deployment.yaml docs/ops/account-credentials.md
git commit -m "chore: 계좌 자격증명 저장소 설정을 배포에 더하고 운영 절차를 적는다"
```

- [ ] **Step 4: 운영 반영 — 단계마다 사용자 승인을 받는다**

  이 브랜치는 `feat/position-line-builder` 위에 있다. 머지 전에 다음을 차례로 확인하고, 각 단계를 실행하기 전에 사용자 승인을 받는다.

  1. 생성기 브랜치의 main 머지 순서를 사용자와 정한다.
  2. 마이그레이션 번호는 이 브랜치에 새 파일이 없으므로 영향이 없다.
  3. `docs/ops/account-credentials.md` "처음 켜는 순서"의 1~4를 실행한다(AWS 리소스 생성 · Secret 적용).
  4. main에 머지한다(배포가 일어난다).
  5. 데이터팀 확인을 기다린다.
     - 2026-10-18의 SSM 읽기 확인
     - `kis_account_daily` 정지 시점
  6. 실계좌를 등록한다(LAN 경로).
  7. 다음 가동일 밤에 `collection_run`이 `DONE`이 되고 계좌가 `CONNECTED`가 되는지 본다(운영 DB는 읽기만).
