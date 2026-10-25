# KIS 계좌 등록 · 해제 API 설계

[포트폴리오 스펙](2026-07-28-portfolio-management-spec.md) §7.1 · §7.2 · §8.1 · §8.5의 계좌 엔드포인트 가운데 KIS 경로를 백엔드에 구현하는 설계다. 스펙이 정한 것은 다시 적지 않고, 스펙이 열어 둔 것을 정한다. 스펙과 이 문서가 다르면 스펙이 맞다. 스펙 문구를 다르게 읽은 곳은 [§9](#9-스펙-반영-후보)에 모았다.

| 근거 | 위치 |
|---|---|
| 두 경로 · 자격증명 격리 · `account_ref` · 계좌 상태 | 스펙 §7.1 · §7.2 · §9.1 |
| 엔드포인트 · 응답 · 오류 · 인증 | 스펙 §8.1 · §8.5 · §8.6 · §8.8 · §9.3 |
| 팀 경계 | 스펙 §11.1 · §11.2 |
| `collection_run` 계약 | [데이터 요구사항](../data-requirements.md) §6.10 |
| 계좌 행을 읽는 쪽 | [보유 스냅샷 생성기 설계](2026-10-15-position-line-builder-design.md) §6.1 · §8 · §9 · §10 |

## 1. 범위

**만든다**

- `POST /accounts` — KIS 계좌 등록. 해제했던 계좌는 같은 행으로 다시 연동한다.
- `DELETE /accounts/{id}` — 연동 해제.
- `GET /accounts` — 연동 중인 계좌 목록과 최근 수집 결과.
- 자격증명 저장 포트(`CredentialStore`)와 SSM 구현.
- 오류 디스패치(`/error`)가 인증 실패로 바뀌지 않게 하는 보안 설정 수정(§3.5).

**만들지 않는다**

- CODEF 경로. 기관 선택 · 1차 인증 · 계좌 선택 · RSA 전송이 따로 필요하다.
- `POST /accounts/{id}/reauth`. KIS는 앱키 방식이라 추가인증이 없고, 데이터 수집기도 KIS 계좌에 `REAUTH_REQUIRED`를 내지 않는다.
- 첫 수집 요청. 등록은 `collection_run` 행을 만들지 않는다(§2.1). 사용자가 일으키는 수집은 `POST /sync` · `sync_run`의 몫이다.
- 등록 때 KIS 호출로 키를 검증하는 일(§2.3).

## 2. 수집 파이프라인과 맞물리는 방식

### 2.1 첫 수집은 다음 EOD 실행이 한다

등록하면 `account` 행이 `CONNECTING`으로 생기고 `credential_ref`에 SSM 파라미터 이름이, `linked_at`에 등록 시각이 들어간다. 그 뒤는 기존 경로를 그대로 탄다.

```
등록            account(CONNECTING, credential_ref)          ← 이 API
23:00 collection_run_daily (일 · 화 · 수 · 목)
  collect_account_snapshot → refine_account_snapshot   그 시점의 app.account로 silver.dim_account 교체
  create_eod                                           DISCONNECTED가 아닌 계좌에 SCHEDULE 행
  wait_credentials                                     백엔드 CredentialFiller가 credential_ref 복사(최대 15분 대기)
  run_collection                                       credential_ref가 찬 REQUESTED만 집어 수집
  … mark_synced
그 뒤           생성기가 DONE을 처리 → CONNECTING → CONNECTED
```

등록한 계좌의 첫 데이터는 다음 가동일 밤에 온다.

등록이 `USER` 행을 함께 넣지 않는 이유:

- 데이터 워커는 `collection_run_daily` 안에서만 돈다. `USER` 행도 같은 23:00 실행에서 집히므로 빨라지지 않는다.
- 같은 날 `USER` 행과 EOD 행이 둘 다 생기면 하룻밤에 같은 앱키로 두 번 수집한다. KIS 접근 토큰 발급은 앱키당 1분에 1번이다.
- `USER` 행의 `as_of`와 진행 표시(`sync_run`)는 수동 동기화 설계가 정한다. 등록이 먼저 정하면 그쪽 설계를 묶는다.

### 2.2 `dim_account` 갱신 시점

데이터 워커는 `collection_run`에 없는 두 사실, 즉 계좌가 연동 중인지와 KIS · CODEF 중 어느 쪽인지를 `silver.dim_account`에서 읽는다. `collection_run_daily`가 `create_eod` 직전에 `app.account`로 이 표를 새로 고치므로, 실행 시작 전까지의 등록 · 해제가 그날 밤 실행에 반영된다.

새로 고침이 실패하면 그날은 직전 `dim_account`로 진행한다. 그때는 직전 갱신 이후의 변경이 반영되지 않는다.

| 직전 갱신 이후에 | 그날 밤 결과 |
|---|---|
| 등록 | EOD 행이 생기지 않는다. 첫 수집이 다음 가동일로 밀린다 |
| 해제 | 옛 스냅샷 때문에 `REQUESTED` 행이 생긴다. `CredentialFiller`가 `DISCONNECTED` 계좌를 채우지 않으므로 `wait_credentials`가 15분을 다 기다린다. 그 행은 다음 가동일에 `FAILED(EXPIRED)`로 끝나는데, 만료 처리가 대기 뒤에 돌아 다음 가동일에도 15분을 한 번 더 기다린다. 생성기는 `DISCONNECTED` 계좌를 건너뛴다 |
| 해제 뒤 재등록 | 옛 스냅샷이 `DISCONNECTED`라 EOD 행이 생기지 않는다. 다음 가동일로 밀린다 |

어느 경우도 라인을 틀리게 만들지 않는다. 백엔드는 따로 다루지 않는다.

### 2.3 등록 때 KIS를 부르지 않는다

증권사 호출은 데이터 몫이다(스펙 §11.1). 등록은 형식만 검사한다(§3.1).

앱키가 틀리면 첫 EOD 수집이 `FAILED`로 끝나고 계좌는 `CONNECTING`에 머문다. 첫 성공 수집 전 계좌는 `position_line`이 없어 계좌별 뷰에 행이 없다. 그래서 실패는 `GET /accounts`의 `last_collection`으로 보인다(§3.3). 사용자는 해제한 뒤 다시 등록한다. 다시 등록하면 `last_collection`은 다음 수집 전까지 `null`이다 — 이전 연동의 실패가 새 키의 결과처럼 보이지 않는다.

## 3. API

모든 엔드포인트가 인증을 요구하고, 사용자는 토큰에서만 온다(스펙 §8.8). 요청 · 응답 필드는 snake_case다.

### 3.1 `POST /accounts`

```json
// 요청
{ "app_key": "…", "app_secret": "…", "account_number": "00000000-01", "label": "생활비 계좌" }

// 202
{ "account_id": "…", "link_state": "CONNECTING", "challenge": null }
```

| 필드 | 규칙 |
|---|---|
| `app_key` · `app_secret` | 필수. 앞뒤 공백을 지운 값이 비어 있지 않고 각 1,024자 이하여야 하며, 지운 값을 저장한다. 상한은 둘을 담은 값이 SSM Standard 파라미터 값 상한(4KB) 안에 들게 한다. 내용은 해석하지 않는다 |
| `account_number` | 필수. 앞뒤 공백을 지운 뒤 숫자 8자리 + 2자리. 하이픈은 있어도 없어도 된다 |
| `label` | 선택. 없거나 `null`이면 신규는 기본값(§3.4), 재연동은 기존 값 유지. 있으면 앞뒤 공백을 지운 뒤 1 ~ 30자(코드 포인트 수, 이모지도 한 글자). 빈 문자열은 거부 |

KIS 등록은 추가인증이 없으므로 응답의 `challenge`는 항상 `null`이고 `link_state`는 `CONNECTING`이다.

### 3.2 `DELETE /accounts/{id}`

성공하면 `204`이고 본문이 없다. 이미 해제된 계좌도 `204`다.

### 3.3 `GET /accounts`

```json
{ "accounts": [
    { "account_id": "…", "broker": "한국투자증권", "label": "한국투자 위탁",
      "account_type": "GENERAL", "source": "KIS",
      "link_state": "CONNECTING", "last_synced_at": null,
      "last_collection": { "state": "FAILED", "as_of": "2026-10-18",
                           "failure_reason": "SOURCE_API_ERROR" } } ] }
```

- `DISCONNECTED`가 아닌 본인 계좌만 담는다. 정렬은 `account_type`, `label` 순이다.
- `last_collection`은 계좌별 뷰와 같은 원천(`CollectionRunStatusPort`, 그 계좌의 최신 `collection_run`)이다. 실행이 하나도 없으면 `null`이다.
- 최근 수집은 `account.linked_at`(마지막 등록 · 재연동 시각) 뒤에 요청된 실행에서 고른다. `account_ref`는 재연동해도 같으므로 실행이 어느 연동의 것인지는 이 시각으로 가른다. `linked_at`이 비어 있으면 거르지 않는다.
- `account_ref` · `credential_ref`는 어떤 응답에도 싣지 않는다.

### 3.4 상품코드와 계좌 속성

계좌번호 뒤 2자리(KIS 상품코드)가 계좌 속성을 정한다.

| 상품코드 | 상품 | `account_type` | 기본 `label` |
|---|---|---|---|
| `01` | 위탁(종합) | `GENERAL` | `한국투자 위탁` |
| `22` | 연금저축 | `PENSION` | `한국투자 연금저축` |
| 그 밖 | — | 거부 `UNSUPPORTED_ACCOUNT_PRODUCT` | — |

- `broker`는 `한국투자증권`, `source`는 `KIS`로 고정한다.
- 기본 `label`에 계좌번호의 어느 부분도 넣지 않는다. 같은 사용자의 연동 중인 계좌에 같은 `label`이 있으면 비어 있는 가장 작은 순번을 붙인다(`한국투자 위탁 2`). 순번은 기본값을 쓸 때만 붙이고, 요청이 준 `label`은 그대로 쓴다. 재연동에서 `label`이 없고 옛 `label`이 연동 중인 다른 계좌와 겹치면 기본값을 다시 매긴다(`한국투자 위탁 2`). 겹치지 않으면 옛 `label`을 둔다.
- IRP(`29`)는 받지 않는다. 데이터 수집기가 기간 체결 조회를 필수로 다루는데, IRP는 그 조회가 `APBK1744`로 막힌다. 등록하면 매일 `FAILED`로 끝나 영영 `CONNECTING`에 머문다. 데이터 쪽이 IRP를 지원하면 이 표에 `29` → `PENSION` · `한국투자 IRP`를 더한다(§10).
- DC(`55`)는 KIS Open API를 쓸 수 없는 상품이다.

### 3.5 오류

형식은 `{ "error": { "code", "message" } }`다(스펙 §8.6). `message`는 고정 문구이며 입력값을 되풀이하지 않는다.

| 상황 | 상태 | `code` |
|---|---|---|
| 토큰 없음 · 만료 | `401` | `UNAUTHENTICATED` |
| JSON이 깨졌거나 필수 필드 누락 · 형식 오류 | `400` | `INVALID_ACCOUNT_REQUEST` |
| 지원하지 않는 상품코드 | `400` | `UNSUPPORTED_ACCOUNT_PRODUCT` |
| 본인 계좌가 이미 연동 중(`DISCONNECTED`가 아님) | `409` | `ACCOUNT_ALREADY_LINKED` |
| 같은 계좌를 다른 사용자가 갖고 있다 | `409` | `ACCOUNT_UNAVAILABLE` |
| `DELETE` 대상이 본인 계좌가 아니다(없는 id, UUID가 아닌 id 포함) | `403` | `FORBIDDEN_ACCOUNT` |
| 자격증명 저장소 호출 실패 | `503` | `CREDENTIAL_STORE_UNAVAILABLE` |
| `Content-Type`이 JSON이 아니거나 없다 | `415` | `UNSUPPORTED_MEDIA_TYPE` |
| DB 오류(연결 실패 포함) | `500` | `INTERNAL_ERROR` |

- `ACCOUNT_UNAVAILABLE`의 문구는 다른 사용자가 있다는 사실을 말하지 않는다("이 계좌는 등록할 수 없습니다").
- `400` 매핑(`HttpMessageNotReadableException` · 형식 오류)과 UUID 변환 실패(`MethodArgumentTypeMismatchException`) 매핑은 `AccountController`에만 거는 예외 처리기(`@RestControllerAdvice(assignableTypes = AccountController.class)`)에 둔다. 전역 처리기에 두면 로그인 · 기기 등록의 깨진 JSON까지 `INVALID_ACCOUNT_REQUEST`가 된다.
- `415`는 모든 엔드포인트에 같은 뜻이라 전역 처리기(`ApiExceptionHandler`)가 맡는다. DB 오류는 계좌 처리기가 예외 종류와 SQLState만 로그에 남기고 고정 문구로 내린다. 연결을 얻지 못한 실패는 `DataAccessException`이 아니라 `TransactionException`으로 오므로 둘 다 받는다.

**오류 디스패치.** `SecurityConfig`는 `/error`를 열지 않고(`anyRequest().authenticated()`), JWT 필터는 ERROR 디스패치에서 다시 돌지 않는다. 그러면 처리기가 받지 못한 예외(415, 처리하지 않은 DB 오류 등)가 `/error`로 넘어가 인증 실패로 바뀌어 `401 UNAUTHENTICATED`가 나갈 수 있다. 클라이언트는 `401`을 전역 로그아웃으로 다룬다(스펙 §10). `DispatcherType.ERROR`를 `permitAll`로 연다. 이 설정은 모든 엔드포인트에 적용된다.

## 4. 흐름과 트랜잭션

등록과 해제 모두 **행을 잠근 뒤 저장소를 부르고, 그 뒤 커밋한다.** 행 잠금이 같은 계좌의 등록 · 해제를 한 줄로 세운다.

### 4.1 등록

1. 요청을 검사하고 계좌번호를 10자리로 정규화한다. `account_type` · 기본 `label`을 정한다(§3.4).
2. `account_ref`와 파라미터 이름을 계산한다(§5).
3. 트랜잭션을 열고 행을 확보한다.

   ```sql
   INSERT INTO account (account_id, user_id, account_ref, broker, label, account_type, source,
                        credential_ref, link_state, linked_at)
   VALUES (…, 'CONNECTING', now())
   ON CONFLICT (account_ref) DO NOTHING
   RETURNING account_id
   ```

   - 한 행이 돌아오면 새 행이다. 커밋 전까지 같은 `account_ref`의 다른 삽입은 이 트랜잭션이 끝나기를 기다린다.
   - 돌아온 행이 없으면 `SELECT … FROM account WHERE account_ref = ? FOR UPDATE`로 기존 행을 잠그고 갈린다.

| 기존 행 | 처리 |
|---|---|
| 본인 · `DISCONNECTED` | 같은 행을 `CONNECTING`으로, `credential_ref`를 채우고 `linked_at`을 지금 시각으로 바꾼다. `label`은 요청에 있으면 그 값으로 바꾸고, 없으면 옛 값을 두되 연동 중인 다른 계좌와 겹치면 기본값을 다시 매긴다(§3.4). `account_id` · `user_id` · `account_ref` · `account_type` · `broker` · `source` · `last_synced_at`은 그대로 둔다 |
| 본인 · 그 밖 | `409 ACCOUNT_ALREADY_LINKED`. 롤백 |
| 다른 사용자 | `409 ACCOUNT_UNAVAILABLE`. 롤백 |

4. 저장소에 쓴다(덮어쓰기). 실패하면 롤백하고 `503`이다. 행이 생기거나 바뀌지 않는다.
5. 커밋한다.

`ON CONFLICT DO NOTHING`은 UNIQUE 위반 오류를 내지 않으므로 트랜잭션이 abort되지 않고 같은 트랜잭션에서 이어 읽을 수 있다. 동시에 들어온 두 등록은 행 잠금 때문에 차례로 처리되고, 뒤의 것은 앞의 것이 커밋한 행을 보고 `409`가 된다.

저장소에 쓴 뒤 커밋이 실패하면 파라미터만 남는다. 행이 없거나 `DISCONNECTED`라 어느 `collection_run`에도 복사되지 않고, 같은 계좌의 다음 등록이 덮어쓴다. 롤백 뒤 보상 삭제는 하지 않는다. 그 사이에 다른 등록이 커밋되면 보상 삭제가 정상 파라미터를 지운다. 남은 파라미터는 데이터 워커의 IAM 와일드카드로 읽을 수 있다(§9의 5).

`account.user_id` · `account_ref`는 이 흐름 어디에서도 바뀌지 않는다(스펙 §9.1).

### 4.2 해제

1. `AccountOwnershipGuard`로 소유를 검사한다. 아니면 `403`.
2. 트랜잭션을 열고 `SELECT … FROM account WHERE account_id = ? AND user_id = ? FOR UPDATE`.
3. `link_state = 'DISCONNECTED'`, `credential_ref = NULL`로 바꾼다.
4. 저장소에서 파라미터를 지운다. 이름은 `account_ref`에서 다시 계산한다. 파라미터가 없으면 성공이다. 실패하면 롤백하고 `503`이다. 계좌는 연동 상태로 남아 `GET /accounts`에 보이므로 다시 해제할 수 있다.
5. 커밋하고 `204`.

- 이미 `DISCONNECTED`인 계좌도 같은 흐름을 탄다. 상태는 그대로이고 4번만 다시 한다.
- 저장소에서 지운 뒤 커밋이 실패하면 계좌는 연동 상태인데 파라미터가 없다. 다음 수집이 `FAILED(CREDENTIAL_UNREADABLE)`로 끝나 `last_collection`에 보이고, 다시 해제하면 끝난다.
- 과거 `position_line` · `account` 행은 지우지 않는다(스펙 §7.5).
- 해제 전에 이미 `credential_ref`가 복사된 `REQUESTED` 행은 워커가 집으면 파라미터를 읽지 못해 `FAILED(CREDENTIAL_UNREADABLE)`로 끝난다. 생성기는 `DISCONNECTED` 계좌의 실행을 `SKIPPED`로 처리한다(생성기 설계 §5.1).

### 4.3 생성기와의 관계

| 계좌 변화 | 생성기 쪽 결과 |
|---|---|
| 등록 · 재연동(`CONNECTING`) | `CredentialFiller`가 EOD 행에 `credential_ref`를 복사한다. 첫 `DONE` 처리에서 `CONNECTED`가 된다 |
| 재연동 직후 | 해제 기간에 라인이 없으므로 옛 보유를 이월하지 않는다. 첫 성공 수집부터 편입된다(생성기 설계 §6.1) |
| 해제(`DISCONNECTED`) | 복사 대상 · 확정 대상 · 라인 존재 검증에서 빠진다. 스냅샷 뷰 · 카탈로그 · 보유 판정에서도 즉시 빠진다(스펙 §7.5) |

`CredentialFiller`는 생성기 잡(`portfolio.snapshot.runtime.enabled`)이 켜져 있어야 돈다. 꺼져 있으면 EOD 행의 `credential_ref`가 비어 수집되지 않는다(§7).

## 5. `account_ref`와 파라미터 이름

```
account_ref = "ar_" + hex(HMAC-SHA256(salt, "<기관코드>:<계좌번호10자리>"))[0:32]
파라미터    = "/stock-project/accounts/" + account_ref
```

- 기관코드는 한국투자증권의 금융결제원 기관코드 `0243`이다. CODEF 기관코드도 같은 체계를 따르면 같은 계좌를 KIS와 CODEF 두 경로로 등록해도 같은 `account_ref`가 나와 UNIQUE가 중복 연동을 막는다. CODEF 기관코드 표에서 `0243`을 직접 확인하지는 않았다. 이 값은 `account_ref`를 정하므로 계좌를 등록한 뒤에는 바꾸지 않는다.
- 계좌번호는 하이픈을 뺀 숫자 10자리(8 + 2)다. 같은 계좌는 입력 모양과 관계없이 같은 문자열이 된다.
- HMAC 키(소금)는 비밀값이고 바뀌면 안 된다(§6.2). 계좌번호 공간이 좁아 소금 없는 해시는 역산된다(스펙 §7.1).
- 출력은 128비트(32hex)다. `trade_id`가 이 값을 접두로 갖는다(스펙 §7.1).
- 파라미터 이름에 사용자를 넣지 않는다. 이름은 늘 서버가 토큰 사용자의 계좌 행으로 만들고 요청값에서 받지 않는다. 남의 자격증명을 막는 것은 이 규칙이며, 이름의 모양이 아니다. 이름은 `collection_run.credential_ref`를 거쳐 데이터에 넘어가므로, 사용자를 넣으면 "사용자는 백엔드 안에만"(스펙 §11.2)이 깨진다. `account_ref`는 계좌마다 유일하고 재연동해도 같아서 이름으로 충분하다.

## 6. 시크릿 처리

### 6.1 `CredentialStore`

```java
interface CredentialStore {
    void put(String name, KisCredential credential);   // 덮어쓴다
    void delete(String name);                          // 없으면 성공
}
```

| 구현 | 쓰는 곳 |
|---|---|
| `SsmCredentialStore` | 운영 |
| `InMemoryCredentialStore` | local 프로파일 · 테스트 |

`portfolio.credentials.store`(`ssm` · `memory`)로 고른다. `application.yaml`에는 기본값이 없어, 설정이 빠지면 기동이 실패한다.

**`SsmCredentialStore`**

- AWS SDK v2 `ssm`. 리전 `ap-northeast-2`.
- `PutParameter(Name, Value, Type=SecureString, Overwrite=true)`. 키는 기본 `aws/ssm`이다.
- `Value`는 데이터 워커가 읽는 JSON과 같은 모양이다(`collect_kis_account.py` "자격증명").

  ```json
  {"app_key": "…", "app_secret": "…", "cano": "<앞 8자리>", "acnt_prdt_cd": "<뒤 2자리>"}
  ```

- `DeleteParameter`. `ParameterNotFoundException`은 성공으로 본다.
- 자격 증명은 `EnvironmentVariableCredentialsProvider`만 쓴다. 기본 체인은 환경변수가 없을 때 노드의 인스턴스 역할을 집을 수 있다.
- 연결 시간 제한 3초, 호출 시간 제한 10초. SDK 예외는 저장소 장애 예외 하나로 바꿔 던지고, 이것이 `503`이 된다.
- 백엔드는 파라미터 값을 읽지 않는다. `GetParameter`를 부르는 코드가 없다.

저장소 호출은 DB 트랜잭션과 행 잠금을 쥔 채 일어난다(§4). 호출 시간 제한이 잠금을 쥐는 최대 시간을 정한다.

### 6.2 소금

| 위치 | 값 |
|---|---|
| 설정 | `portfolio.account-ref.salt` ← 환경변수 `ACCOUNT_REF_SALT`. 기본값 없음 |
| 운영 | k8s Secret `portfolio-api`의 `ACCOUNT_REF_SALT` |
| 백업 | SSM SecureString `/stock-project/backend/account-ref-salt`. 사람이 콘솔에서 넣는다. 백엔드 IAM 사용자는 이 경로에 권한이 없다 |
| local · 테스트 | 개발용 고정값(`application-local.yaml` · `application-test.yaml`) |

- 기동 때 소금이 비었거나 32바이트보다 짧으면 실패한다.
- 소금을 잃거나 바꾸면 재등록 때 다른 `account_ref`가 나온다. 옛 행과 이어지지 않아 해제한 계좌의 과거 라인과 끊기고, 같은 계좌를 두 행으로 등록할 수 있게 된다. 백업에서 같은 값으로 되살린다.

### 6.3 값이 새지 않게

자격증명 값과 계좌번호는 요청 본문에서 들어와 `SsmCredentialStore` 안에서만 쓰인다. 그 사이에서 다음을 지킨다.

- **`toString`:** 요청 DTO · `KisCredential` · `KisAccountNumber`의 `toString`을 직접 정의해 값을 가린다. record 기본 `toString`은 필드를 그대로 찍는다.
- **검증 메시지:** Bean Validation을 쓰지 않는다. 검사는 코드로 하고 메시지는 고정 문구다.
- **JSON 오류:** `HttpMessageNotReadableException`을 `400 INVALID_ACCOUNT_REQUEST` 고정 문구로 바꾼다(§3.5). 예외 메시지는 응답에도 로그에도 내보내지 않는다. 원문 조각이 들어 있을 수 있다.
- **로그:** 이 기능의 코드는 `account_id`와 예외 클래스 · SQLState · AWS 오류 코드만 남긴다. 예외 메시지는 SDK 것이든 DB 것이든 남기지 않는다. PostgreSQL 제약 위반 메시지는 `account_ref` · `credential_ref` 값을 그대로 담는다. `account_ref` · `credential_ref` · 파라미터 이름도 남기지 않는다. SDK 와이어 로깅을 켜지 않는다.
- **응답:** `account_ref` · `credential_ref`를 싣지 않는다.
- **테스트:** 가짜 값만 쓴다(`test-app-key`, `00000000-01` 꼴).
- **문서:** 샘플의 계좌번호 · 키는 마스킹한다.

### 6.4 전송 구간

API는 지금 TLS 없이 평문 HTTP로 열려 있다. 등록 요청의 앱키 · 시크릿 · 계좌번호가 그 구간을 지나며, 위탁(`01`) 앱키는 주문까지 낼 수 있다. 이 설계는 TLS를 다루지 않는다. 운영 규칙은 다음과 같다.

- 실제 키는 같은 LAN 주소나 `kubectl port-forward`의 `localhost`로 연결했을 때만 입력한다.
- 공인 IP로 노출된 경로에서는 등록하지 않는다.

이 규칙은 `back-end/docs/ops`에도 적는다.

## 7. 인프라와 켜기 전 조건

| 대상 | 변경 |
|---|---|
| IAM 사용자 `portfolio-api-credentials` | 인라인 정책: `ssm:PutParameter` · `ssm:DeleteParameter`, 리소스 `arn:aws:ssm:ap-northeast-2:394686422456:parameter/stock-project/accounts/*`. 액세스 키 1쌍 |
| SSM | `/stock-project/backend/account-ref-salt` SecureString(§6.2) |
| k8s Secret `portfolio-api` | `AWS_ACCESS_KEY_ID` · `AWS_SECRET_ACCESS_KEY` · `ACCOUNT_REF_SALT` 추가 |
| `k8s/deployment.yaml` | env `AWS_ACCESS_KEY_ID` · `AWS_SECRET_ACCESS_KEY` · `AWS_REGION=ap-northeast-2` · `ACCOUNT_REF_SALT` · `CREDENTIAL_STORE=ssm` |

- **KMS:** 기본 `aws/ssm` 키로 SecureString을 쓸 때 IAM 정책에 KMS 권한이 따로 필요한지는 확인하지 않았다. 적용할 때 가짜 파라미터 하나를 쓰고 지워 본다.
- **적용 순서:** Secret을 먼저 적용하고 이미지를 배포한다. 거꾸로 하면 기동 검사(§6.1 · §6.2)에 걸려 파드가 뜨지 않는다.

등록한 계좌가 실제로 수집되려면 이 API 밖의 다음이 함께 갖춰져야 한다.

| 조건 | 없으면 |
|---|---|
| 보유 스냅샷 생성기가 main에 들어가 배포되고 `SNAPSHOT_RUNTIME_ENABLED=true`(생성기 설계 §10의 켜기 전 확인 포함) | `CredentialFiller`가 돌지 않는다. EOD 행이 `credential_ref` 없이 15분 대기 뒤 다음 가동일에 `EXPIRED`로 끝나고, 계좌는 `CONNECTING`에 머문다 |
| `collection_run_daily`가 켜져 있다 | 수집이 일어나지 않는다 |
| 데이터 쪽 조건(§10) | §10 표 |

## 8. 테스트

CI는 실제 Postgres(`postgres:16-alpine`, `portfolio_test`)로 돈다. 실제 AWS를 부르는 테스트는 두지 않는다.

**단위**

| 테스트 | 확인 |
|---|---|
| `KisAccountNumberTest` | 앞뒤 공백 · 하이픈 유무가 같은 10자리로 정규화된다 · 01/22 → 유형과 기본 `label` · 29 · 55 · 자릿수 · 숫자 아님은 거부 · 거부 메시지와 `toString`에 입력값이 없다 |
| `AccountRefIssuerTest` | 같은 입력은 같은 값 · 소금이나 계좌번호가 다르면 다른 값 · `ar_` + 32hex · 고정 벡터 1건(가짜 소금 · 가짜 계좌번호) |
| `SsmCredentialStoreTest` | `SsmClient` 목으로 요청 모양(이름, `SecureString`, `Overwrite`, 값 JSON의 네 키) · `ParameterNotFound` 삭제는 성공 · SDK 예외는 저장소 장애 예외 |
| 기동 검사 | 소금이 없거나 짧을 때, `portfolio.credentials.store`가 없을 때 컨텍스트가 뜨지 않는다(`ApplicationContextRunner`) |

**통합** (`InMemoryCredentialStore`, MockMvc, 실제 JWT)

| 사례 | 기대 |
|---|---|
| 신규 등록 | `202` · `CONNECTING` · 행의 `credential_ref` = `/stock-project/accounts/<account_ref>` · 저장소에 공백을 지운 값이 있다 |
| 기본 `label` 겹침 | 위탁 두 개를 `label` 없이 등록하면 `한국투자 위탁` · `한국투자 위탁 2` |
| 해제 → 재등록 | 같은 `account_id` · `label`은 요청에 있을 때만 바뀐다 · 저장소 값이 덮어써진다 · 해제 전 연동의 수집 실패는 `last_collection`에 보이지 않는다 |
| 본인이 이미 연동 중 | `409 ACCOUNT_ALREADY_LINKED` |
| 다른 사용자의 계좌 | `409 ACCOUNT_UNAVAILABLE` · 그 행은 바뀌지 않는다 |
| 등록 중 저장소 장애 | `503` · 신규면 행이 없고, 재연동이면 행이 `DISCONNECTED` 그대로 |
| 같은 계좌 동시 등록 두 건 | `InMemoryCredentialStore`의 대기 훅으로 첫 요청을 `put`에서 멈춘 채 둘째 요청을 보낸다. 행은 1개 · 한쪽 `202`, 다른 쪽 `409` |
| 해제 | `204` · `DISCONNECTED` · `credential_ref` null · 저장소에서 지워진다 · 두 번째 호출도 `204` |
| 해제와 재등록 경합 | 해제를 `delete`에서 멈춘 채 재등록을 보낸다. 재등록은 해제가 끝난 뒤 진행되고, 끝에 행은 `CONNECTING`이며 저장소에 새 값이 있다 |
| 해제 중 저장소 삭제 실패 | `503` · 행은 연동 상태 그대로이고 `credential_ref`도 그대로 · 저장소를 고친 뒤 다시 부르면 `204` |
| 해제 대상이 남의 계좌 · 없는 id · UUID가 아닌 id | `403 FORBIDDEN_ACCOUNT` |
| `GET /accounts` | 본인 · 연동 중인 계좌만 · `last_collection`(실행 없음 → `null`, 최신 실행의 상태, 재연동 전 실행 제외) · `account_ref` · `credential_ref` 없음 |
| 남의 데이터 격리 | 다른 사용자 토큰으로 `GET`에 남의 계좌가 없고, `DELETE`는 `403`, 남의 계좌번호 등록은 `409` |
| 형식 오류 · 깨진 JSON · 빈 `label` · IRP | 고정 코드 · 본문에 입력값이 없다 |
| 다른 컨트롤러의 깨진 JSON | 로그인의 깨진 JSON은 `INVALID_ACCOUNT_REQUEST`가 아니다 |
| 토큰 없음 | `401` |
| 누출 검사 | 위 성공 · 실패 · 장애 경로의 로그 전체(`OutputCaptureExtension`)와 응답 본문에 가짜 앱키 · 시크릿 · 계좌번호 문자열이 없다 |
| 생성기와 연결 | 등록 뒤 `CredentialFiller`가 EOD 행에 이 이름을 채운다 · 해제 뒤에는 채우지 않는다 |

**오류 디스패치** (`@SpringBootTest(webEnvironment = RANDOM_PORT)`, 실제 HTTP)

- MockMvc는 ERROR 디스패치를 하지 않아 §3.5의 `/error` 문제를 잡지 못한다. 실제 서블릿 경로로 유효한 토큰과 함께 `POST /accounts`에 `Content-Type: text/plain`을 보내 `415`가 `401`이 아닌지 본다.

**기존 테스트**

- `ArchitectureRulesTest`에 "`CredentialStore`에는 `account` 패키지만 의존한다"를 더한다.

실제 SSM 왕복은 §7 적용 때 가짜 파라미터로 확인한다.

## 9. 스펙 반영 후보

스펙 문장은 고치지 않고 아래처럼 읽었다. 스펙에 반영할지는 따로 정한다.

1. **파라미터 이름의 사용자** — §7.1 "`credential_ref`가 가리키는 시크릿 매니저 키 이름에도 사용자가 들어가"와 달리 이름은 `/stock-project/accounts/<account_ref>`이고 사용자를 넣지 않는다(§5). 이름이 `collection_run`을 거쳐 데이터에 넘어가므로 §11.2 "사용자는 백엔드 안에만"과 부딪치고, 남의 자격증명을 막는 것은 서버가 토큰 사용자의 계좌로만 이름을 만든다는 규칙이기 때문이다.
2. **재연동 시 계좌 행 재사용** — §7.1 "`account_id`를 그대로 쓰지 않는 것은 재등록 때 새 uuid가 나와"와 달리 해제한 계좌를 다시 연동하면 같은 행(같은 `account_id`)을 쓴다. V1 `account.account_ref`가 UNIQUE라 같은 계좌의 새 행을 넣을 수 없다.
3. **KIS 등록 응답** — §8.5의 `POST /accounts` 응답 예시는 `REAUTH_REQUIRED` · `CONNECTED`만 보인다. KIS 등록은 첫 수집 전이라 `CONNECTING`과 `challenge: null`을 낸다.
4. **상태 전이** — §7.2 상태도에 없는 `DISCONNECTED → CONNECTING`(재연동)과 `CONNECTING` · `REAUTH_REQUIRED → DISCONNECTED`(해제)를 허용한다.
5. **`credential_ref` "단기 참조"와 전달 경로** — §7.7 · §11.2의 "단기 자격증명 참조"를 계좌의 SSM 파라미터 이름으로 읽었다(생성기 설계 §12의 5와 같다). 이름은 `account_ref`에서 바로 나오고 데이터는 `account_ref`를 `dim_account`로 갖고 있다. 그래서 데이터 워커의 IAM 와일드카드(`/stock-project/accounts/*`)만 있으면 `collection_run` 픽업을 거치지 않고도 모든 계좌의 자격증명을 읽을 수 있다. §7.1 "수집이 필요한 시점에 `collection_run` 픽업으로만 전달"은 두 팀의 관례로 지켜지고, 권한으로 강제되지는 않는다.
6. **IRP 미지원** — §7.1은 KIS 경로의 계좌 종류를 제한하지 않고, §5.1 `account_type`은 `PENSION`을 둔다. 데이터 수집기가 IRP 체결 조회를 지원하기 전까지 IRP(`29`) 등록을 거부한다(§3.4).

## 10. 데이터 쪽 의존

| 항목 | 상태 | 빠지면 |
|---|---|---|
| `create_eod` 직전 `dim_account` 갱신 | 반영됨(dataeng `919508f`, airflow-dags `collection_run_daily`). 2026-10-18 가동일부터 적용 | §2.2 표의 지연 |
| `dataeng-pipeline`이 `/stock-project/accounts/*`를 `GetParameter`(복호화 포함)할 수 있다 | 확인하지 않음. `kis_account_daily` DAG 주석이 "IAM이 `/stock-project/accounts/*`만 허용한다"고 적고 그 아래 `/stock-project/accounts/ar_me/kis`를 쓴다. 데이터팀이 2026-10-18에 실제 수집기와 같은 이미지 · Secret으로 읽어 보기로 했다 | 모든 등록 계좌가 `FAILED(CREDENTIAL_UNREADABLE)`로 끝나 `CONNECTING`에 머문다 |
| `kis_account_daily`를 멈춘다 | 확인하지 않음. 이 DAG는 `ar_me` 한 계좌를 손으로 적어 같은 일 · 화 · 수 · 목 23:00에 수집한다 | 같은 실계좌를 API로 등록하면 같은 앱키로 같은 시각에 두 번 수집한다(토큰 발급 1분 제한). 레이크에 `ar_me`와 새 `account_ref` 두 갈래가 쌓인다 |
| `collection_run_daily` 켜짐 · `KIS_ENV` | DAG는 일시정지로 생성된다. `KIS_ENV`는 Airflow Variable `dataeng_kis_env`(없으면 `real`)이고 워커가 부르는 모든 KIS 계좌에 한꺼번에 적용된다. DAG 주석은 테스트 계좌가 모의투자인 동안 `demo`로 둔다고 적었다. Airflow의 실제 상태와 값은 확인하지 않음 | 수집이 일어나지 않거나, 실계좌 키로 모의 서버를 불러 실패한다 |
| IRP 수집 | 미지원. 수집기가 기간 체결(`TTTC0081R` · `CTSC9215R`)을 필수 조회로 다루고, IRP는 이 조회가 `APBK1744`로 막힌다 | IRP 등록을 받지 않는다(§3.4) |

**데이터팀 요청**

> **제목: 계좌 등록 API를 켜기 전에 확인할 두 가지**
>
> **배경**
> 백엔드 계좌 등록 API가 `/stock-project/accounts/<account_ref>`에 자격증명을 쓰고 `app.account`에 `CONNECTING` 행을 만듭니다. `create_eod` 직전 계좌 목록 새로 고침이 들어가서, 등록한 계좌는 그날 밤 EOD로 첫 수집됩니다.
>
> **요청사항**
> 1. 실계좌를 API로 등록하는 시점에 `kis_account_daily`를 멈춰 주세요. 이 DAG는 `ar_me` 계좌를 같은 23:00에 수집하므로, 같은 계좌를 API로 등록하면 같은 앱키로 두 번 수집하고 레이크에 계좌가 두 갈래로 쌓입니다. 멈추는 시점은 백엔드가 등록 날짜를 알려 드리면 맞춰 주세요.
> 2. IRP(상품코드 29) 수집을 지원할 계획이 있으면 알려 주세요. 지금 수집기는 기간 체결 조회를 필수로 다루는데, IRP는 이 조회가 `APBK1744`로 막힙니다. IRP에서는 체결을 선택 조회로 다루거나 연금 전용 TR(`TTTC2208R` 잔고 등)을 쓰면 등록을 열겠습니다.
>
> **기대**
> - API로 등록한 계좌가 하루에 한 번만 수집되고, 레이크의 계좌 식별자가 하나로 모입니다.
> - IRP 지원 여부에 따라 백엔드가 상품코드 29를 열지 정할 수 있습니다.
