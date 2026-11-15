# E-base 실습 노트: 관측 기반

- 날짜: 2026-11-15
- 계획: `yhr/review/upgrade-plan.md`의 E절, 0.2의 E-base 단위
- back-end: `practice/E-base` `8ab9493` (기준 origin/main `bffa4f6`, 로컬 커밋만)
- 범위: Prometheus 레지스트리, `/actuator/prometheus` 노출, LOST 계수기, 지표 이름·태그 목록. 나머지 지표 구현, 경보 규칙, 장애 주입은 E-alert의 몫이다.

## 1. 배경

### 출발한 문제

앱에는 사람이 보지 않아도 도는 주기 작업이 많다.

- 보유 스냅샷 생성기(1분): 자격증명 채우기, 실행 반영, 날짜 확정, 동기화 닫기, 평단·손익 계산
- 알림 평가기(1분), 발송기(5초), 영수증 확인기(5분)

이 작업들이 제대로 도는지 알 수 있는 신호는 warn 로그뿐이었다. 액추에이터는 `health`만 열려 있어서 "살아 있다"는 알아도 "제대로 일한다"는 알 수 없었다. 한 계좌 때문에 전 사용자의 확정이 멈춘 결함(O1)도 단서는 warn 로그뿐이었다. 누군가 `kubectl logs`를 열어 봐야만 알 수 있었다.

메우려는 역량은 실트래픽 운영이다. 앱이 자기 상태를 숫자로 내놓고, 숫자가 이상하면 사람이 로그를 보지 않아도 경보가 오게 하는 것이다.

### E-base가 따로 떨어진 이유

B(조회 부하), D(리더 없는 복제본의 비용), E-alert(경보)가 모두 지표를 읽는다. 지표 이름이 나중에 바뀌면 세 단위의 쿼리와 경보 식을 다 고쳐야 한다. 그래서 이름·태그 목록과 노출 기반을 먼저 떼어 관문 단위로 두었다. D는 특히 LOST 계수기가 있어야 시작할 수 있다.

### 계획서의 가설과 이 단위의 관계

E절의 가설 세 가지는 모두 E-alert에서 판정한다. E-base에는 그 대상이 되는 지표(DB 집계 Gauge)와 경보가 아직 없다.

- DB 집계 Gauge를 수집 주기마다 돌려도 부하가 작다 → Gauge를 E-alert가 만든다
- 다섯 경보가 "지속 시간 + 수집 주기" 안에 울린다 → 경보를 E-alert가 만든다
- 정상 하루에 거짓 경보가 나올 수 있는 곳이 둘 있다 → 지표 정의에 반영했다(3절). 판정은 E-alert가 한다

E-base 스스로의 기대는 이랬다. 관리 포트에 지표가 열리고 앱 포트에는 열리지 않는다, 로컬 앱 두 개를 Prometheus가 구분해 긁는다, LOST가 결과별 계수기로 나온다.

## 2. 진행

### 2.0 먼저 전체 그림을 잡았다

처음에는 지표 이름 초안과 결정 질문부터 냈다. 사용자가 과제 배경, Prometheus 기본 개념, 지표 설계 개요를 먼저 설명해 달라고 해서 순서를 바꿨다. 결정은 그 개념 위에서만 의미가 있어서, 이 순서가 맞았다.

익힌 개념은 다음과 같다.

- **풀(pull) 방식**: 앱은 숫자를 HTTP 경로에 펼쳐 두기만 하고, Prometheus가 주기적으로 가져간다. 수집기가 죽어도 앱은 영향을 받지 않는다. 가져가지 못하면 그 자체로 앱이 죽은 것을 안다(`up == 0`).
- **시계열**: 이름과 라벨 값 조합 하나가 시계열 하나다. Prometheus는 수집할 때 `instance` 라벨을 붙여 어느 파드에서 온 값인지 가른다.
- **지표 종류**
  - Counter: 올라가기만 하는 누적 수. `rate()`로 최근 N분 동안 초당 몇 번인지 본다. 재시작으로 0이 돼도 `rate()`가 보정한다.
  - Gauge: 지금 이 순간의 값. 수집할 때마다 값을 읽는다. DB를 세는 Gauge는 수집할 때마다 쿼리가 한 번 돈다.
  - Timer: 횟수, 합계, 최댓값. 백분위가 필요하면 히스토그램 버킷을 켜야 한다.
- **Micrometer**: 지표용 SLF4J다. 코드는 중립 API로 쓰고, 붙인 레지스트리가 내보내는 형식을 정한다. Spring Boot 액추에이터가 그 결과를 `/actuator/prometheus`에 연다.
- **카디널리티**: 시계열 수는 라벨 값 조합의 수다. `account_id`를 라벨로 달면 계좌 수만큼 시계열이 늘고, 수집기 메모리가 사용자 수에 비례해 커진다. 지표는 "문제가 있다"까지만 알리고, "어느 계좌인가"는 로그로 찾는다.
- **지표가 나오는 두 자리**
  - 코드 안의 사건(Counter, Timer)은 파드마다 따로 센다. 전체는 `sum`으로 합친다.
  - DB의 현재 상태(Gauge)는 두 파드가 같은 값을 낸다. `max`로 하나만 본다(`sum`이면 두 배가 된다).

### 2.1 지표 목록을 "알고 싶은 것"에서 거꾸로 짰다

지표를 많이 내는 것이 목적이 아니다. 사용자 피해로 이어지는 장애에서 거꾸로 짚었다.

| 알고 싶은 것 | 사용자 피해 | 지표 |
|---|---|---|
| 확정이 멈췄나 | 전 사용자의 어제 값이 확정되지 않음(O1) | 확정 지연 Gauge |
| 실행 처리가 밀리거나 실패하나 | 일부 계좌가 갱신되지 않음 | 대기 실행 수, 실패 실행 수와 가장 오래된 실패, 실패 횟수 |
| 스냅샷 단계가 얼마나 걸리나 | 반영이 늦어짐 | 단계별 Timer |
| 평가가 느려지나 | 알림이 늦게 울림 | 평가 주기 Timer, 대상 수, 시점 수 |
| 복제본끼리 같은 일을 하다 지나 | 자원 낭비(D가 비용을 잼) | 반영 결과 Counter, LOST는 `outcome="lost"` |
| 푸시가 안 나가나 | 알림이 기기에 오지 않음 | 발송 적체 수와 가장 오래 기다린 시간, 발송 결과 Counter |

목록을 짜면서 두 가지를 정했다.

- **LOST만 세지 않고 반영 결과 4종을 한 Counter로 센다.** D는 중복 비율을 재는데, LOST만 있으면 분모가 없다. 같은 Counter에 applied·fired·ended가 있으면 `lost / 전체`가 바로 나온다.
- **거짓 경보를 피하도록 정의를 좁힌다.** 계획서 가설대로, 발송 적체를 "PENDING 전체"로 세면 정상 운영에서도 울린다. 세션이 끝난 기기의 행과 기한이 12시간인 종가 발화 행이 오래 남기 때문이다. 그래서 "발송기가 지금 집을 수 있는 행"으로 정의했다.

### 2.2 결정 1: 지표 이름 규칙

배경: 한 Prometheus에 앱 지표와 라이브러리 지표(`jvm_*`, `hikaricp_*`)가 섞인다. 경보 식은 이름으로 지표를 찾는다.

| 선택지 | 얻는 것 | 잃는 것 |
|---|---|---|
| A. `portfolio.<영역>.<대상>` | 앱 지표를 `portfolio_` 접두로 한 번에 고른다. 라이브러리와 겹치지 않는다. 영역이 패키지와 같아 출처를 찾기 쉽다 | 이름이 길어진다 |
| B. 접두 없이 `<영역>.<대상>` | 짧다 | `alert_*` 같은 흔한 단어가 겹칠 수 있다. 앱 지표만 고르기 어렵다 |
| C. Prometheus 이름을 코드에 직접 쓴다 | 코드와 수집기에서 같은 문자열로 검색된다 | 접미사 처리를 따로 확인해야 하고, Micrometer 관례에서 벗어난다 |

고른 것: **A.**
이유: 이름만 보고 앱 지표인지, 어디서 나오는지 알 수 있다. 잃는 것은 길이뿐이다.

함께 정한 관례는 다음과 같다.

- 코드에는 점 표기를 쓰고 단위를 넣지 않는다. 내보낼 때 Micrometer가 밑줄로 바꾸고 `_total`, `_seconds`를 붙인다.
- "지금 몇 개" Gauge는 복수형(`runs.pending`), 사건 Counter는 사건 이름(`apply`, `run.failures`)을 쓴다.
- 시간 Gauge는 초 단위다.

### 2.3 결정 2: 태그 카디널리티

먼저 규칙으로 정한 것이 있다. 라벨 값은 코드에 고정된 영문 식별자만 쓴다. 사용자·계좌·알림·실행 ID는 쓰지 않는다. 스냅샷 단계는 로그용 한국어 이름과 별도로 `credential_fill` 같은 식별자를 둔다. 파드 구분은 수집 시 붙는 `instance`에 맡긴다.

**2-a. 발송 결과에 실패 사유 라벨을 달지**

실패 사유는 Expo 오류 문자열과 네트워크 실패 사유에서 와서, 값의 종류가 코드에 고정되어 있지 않다.

| 선택지 | 얻는 것 | 잃는 것 |
|---|---|---|
| `result`만 | 시계열 3개. 관리할 목록이 없다 | 원인은 warn 로그로 봐야 한다 |
| `result` + `reason`(모르는 사유는 `other`) | 원인별 추세가 지표에 보인다 | 목록을 관리해야 하고, 시계열이 늘고, 새 사유는 `other`에 섞인다 |

고른 것: **`result`만.**
이유: 다섯 경보 모두 사유가 필요 없고, 사유는 이미 로그에 있다. 라벨은 나중에 더해도 기존 식이 깨지지 않는다.

**2-b. 히스토그램을 어디에 켤지**

| 선택지 | 얻는 것 | 잃는 것 |
|---|---|---|
| 평가 주기에 30초 경계 버킷 하나 | 경보에 필요한 "30초를 넘은 주기의 비율"을 구한다. 시계열이 1~2개 는다 | 정확한 p95는 모른다 |
| 평가 주기 + HTTP 전체 히스토그램 | B가 서버 p95를 Prometheus로도 본다 | uri × method × status × 버킷 수만큼 시계열이 는다 |
| 없음 | 가장 가볍다 | 평가 주기 경보를 `max`나 평균으로 바꿔야 한다 |

고른 것: **평가 주기의 30초 버킷만.**
이유: 경보 식에 필요한 만큼만 켠다. HTTP 히스토그램이 필요한지는 B가 판정 방식에 따라 정한다.

이름과 태그를 정한 시점에 중간 공유 메모를 냈다. B·D·E-alert가 그 이름을 쓴다.

### 2.4 결정 3: 노출 방식

`/actuator/prometheus`는 수집기가 토큰 없이 긁어야 해서 인증 없이 연다. 그래서 "누가 이 포트에 닿는가"가 보안 범위다. 계획서는 그 범위를 "클러스터 안 수집기로만 한정"하라고 했다.

결정 전에 사실 세 가지를 확인했다.

- **F1. 관리 포트를 따로 둬도 Spring Security가 그대로 걸린다.**
  - 처음에는 포트를 가르면 보안 설정도 따로일 수 있다고 보고 확인부터 했다.
  - Boot 3.4.5 jar의 `ServletManagementChildContextConfiguration$ServletManagementContextSecurityConfiguration` 바이트코드를 읽었다. 관리 포트용 자식 컨텍스트가 부모의 `springSecurityFilterChain`을 꺼내 자기 필터로 등록한다.
  - 그래서 어느 쪽이든 `permitAll`이 필요하다.
- **F2. 관리 포트를 따로 두면 health도 그 포트로 옮겨 간다.**
  - 프로브를 앱 포트에 남기려면 `management.endpoint.health.probes.add-additional-paths=true`로 앱 포트에 `/livez`·`/readyz`를 연다(3.4.5 설정 메타데이터로 확인).
- **F3. 기존 결정과 운영 네트워크**
  - back-end `docs/decisions-deploy.md`는 "관리 포트는 8080, 외부 노출은 Ingress 경로 규칙으로 막는다"로 정해 두었다. 되돌리는 조건으로 "지표 수집이 붙으면 다시 본다"고 적혀 있었다.
  - 레포에는 Ingress 매니페스트가 없고, README에는 "API가 인터넷에 열려 있지 않다"고 적혀 있다.
  - 운영의 Ingress 유무는 확인하지 않았다.

| 선택지 | 얻는 것 | 잃는 것 |
|---|---|---|
| A. 앱 포트(8080)에 그대로 | 설정이 가장 적다. 매니페스트와 프로브를 바꾸지 않는다 | 8080에 닿는 누구나 읽는다. API를 밖에 열 때 `/actuator/**`를 막는 규칙을 누군가 기억해야 한다 |
| B. 관리 포트 분리(운영 8090, 로컬 8233·8234) | Service·Ingress가 앱 포트만 가리켜서 지표 포트가 따라 나가지 않는다. 나중에 NetworkPolicy로 포트 단위 제한을 걸 수 있다 | 설정할 곳이 는다. 프로브를 잘못 고치면 배포 때 파드가 준비 상태에 들지 못한다. 기존 결정 문서를 고쳐야 한다. NetworkPolicy가 없으면 클러스터 안 파드는 여전히 닿는다 |

고른 것: **B.** 프로브는 앱 포트의 `/livez`·`/readyz`로 둔다.
이유: 노출 범위를 사람이 기억하는 규칙이 아니라 구성 자체로 좁힌다. 프로브를 앱 포트에 남기면 "앱 포트가 요청을 받을 수 있는가"를 그 포트에서 판정한다.

로컬 관리 포트 8233·8234는 0.2 표에 없어서 사용자에게 확인받고 썼다.

### 2.5 구현

| 파일 | 바꾼 것 |
|---|---|
| `build.gradle.kts` | `runtimeOnly(micrometer-registry-prometheus)`. 테스트가 실제 출력 이름을 고정하려고 `testImplementation`에도 넣었다 |
| `application.yaml` | `management.server.port: ${MANAGEMENT_PORT:8090}`, 노출에 `prometheus`, `probes.add-additional-paths: true` |
| `SecurityConfig.java` | `/livez`·`/readyz`·`/actuator/prometheus`를 `permitAll`에 추가 |
| `ApplyOutcomes.java`(새 파일) | `portfolio.alert.apply` Counter를 결과 4종에 미리 만든다 |
| `EvaluationRunner.java` | `writer.apply(...)`가 돌아온 뒤 결과를 센다 |
| `k8s/deployment.yaml` | 관리 포트 8090 선언, 프로브를 `/readyz`·`/livez`로 변경 |
| 테스트 | `ApplyOutcomesTest`(새 파일, 3개), `EvaluationRunnerTest`(배선 테스트 1개) |

설계에서 짚은 원리는 두 가지다.

- **세는 자리를 트랜잭션 밖에 둔다.**
  - `AlertRuntimeWriter.apply`는 `@Transactional`이다. 안에서 세면 커밋이 실패해 롤백된 반영도 이미 세어진 뒤다.
  - 프록시가 커밋을 마치고 돌아온 뒤(`EvaluationRunner`)에 세면 DB에 실제로 남은 결과만 센다.
- **결과 4종의 Counter를 기동할 때 미리 만든다.**
  - Counter는 처음 증가할 때 생기는 것이 기본이다. 그러면 LOST가 한 번도 안 난 파드에는 `lost` 시계열이 아예 없다.
  - 시계열이 없으면 `rate()`가 0이 아니라 "값 없음"이 되어 비율 식이 빈다.
  - 미리 만들면 처음부터 0으로 나온다.

LOST에는 한계가 하나 있다. "다른 복제본에 진 경우"와 "사용자 변경에 진 경우"를 함께 센다. `Outcome` 주석과 `AlertRuntimeWriter`를 읽고 추론한 것이다. `applyState`가 false를 돌려주는 시점에는 둘을 가를 정보가 없다.

### 2.6 확인

1. `pf-e` 컨테이너(`postgres:16-alpine`, 5505)를 만들고 `portfolio`·`portfolio_test` DB를 두었다.
2. 전체 테스트를 `TEST_DB_URL`로 `pf-e`에 돌렸다(`--rerun-tasks`).
3. 앱 두 개를 local 프로필로 띄웠다(앱 8231/관리 8233, 앱 8232/관리 8234). 푸시·스냅샷·실현손익 생성기는 끄고, 평가기·발송기는 켰다.
   - 처음에는 `bootRun` 두 개를 생각했지만, 같은 worktree에서 두 Gradle 빌드가 빌드 디렉터리 잠금을 두고 부딪힌다. 그래서 `bootJar`로 한 번 빌드하고 `java -jar`로 두 번 띄웠다.
4. 경로별 응답 코드를 확인했다.
5. Prometheus 컨테이너(9090)를 띄워 두 관리 포트를 15초 간격으로 긁게 했다.

## 3. 결과

### 측정 조건

- 환경: 로컬 macOS 노트북, Docker
- 앱: Spring Boot 3.4.5, Micrometer Prometheus 레지스트리 1.14.6
- DB: `postgres:16-alpine`. Flyway만 적용하고 데이터는 넣지 않았다
- Prometheus: 3.16.0, 수집 간격 15초
- 반복: 각 확인을 한 번씩. 시간을 잰 측정은 없다

### 잰 것

| 확인 | 결과 |
|---|---|
| 전체 테스트 | 1,436개 통과(실패 0, 건너뜀 0). 이 중 지표 관련은 `ApplyOutcomesTest` 3개와 `EvaluationRunnerTest`의 배선 테스트 1개 |
| 관리 포트 `/actuator/prometheus` (8233, 8234) | 200, 토큰 없이 |
| 앱 포트 `/actuator/prometheus`, `/actuator/health` (8231) | 404 |
| 앱 포트 `/livez`, `/readyz` (8231) | 200 |
| 관리 포트에서 노출하지 않은 `/actuator/env` (8233) | 401 |
| Prometheus 수집 대상 | 두 대상 모두 `up` |
| `portfolio_alert_apply_total` | 앱마다 `outcome` 4종이 0으로 수집됨. `instance`로 두 앱이 구분됨 |
| 앱 하나의 시계열 수(유휴) | 두 번 쟀다. 앱 두 개와 프로브 요청 여러 건 뒤 204개, 앱 하나를 다시 띄워 요청 4건 뒤 189개. HTTP·보안 지표는 경로와 상태 조합이 늘수록 는다. 189개일 때 `spring_security_*` 53개(지표 이름 44개), `jvm_*` 60개 안팎, `hikaricp_*` 16개, `http_server_*` 12개, `portfolio_*` 4개 |
| 매칭되지 않은 경로의 HTTP 지표 | `uri="/**"` 하나로 묶임 |

배선 테스트는 실제 DB에서 평가 한 주기를 돌리고 `fired`가 1, 나머지가 0인지 본다. 띄운 앱에는 알림 데이터가 없어서, 실행 중인 앱에서 값이 움직이는 것은 보지 않았다.

### 가설 판정

| 가설 | 판정 |
|---|---|
| 관리 포트에 지표가 열리고 앱 포트에는 열리지 않는다(E-base 기대) | 맞음 |
| Prometheus가 두 앱을 구분해 긁는다(E-base 기대) | 맞음 |
| LOST가 결과별 계수기로 나온다(E-base 기대) | 맞음. 실행 중인 앱에서 LOST가 실제로 오르는 것은 보지 않았다(D가 본다) |
| DB 집계 Gauge의 부하가 작다(E절) | 판정 안 함. Gauge를 E-alert가 만든다 |
| 다섯 경보가 지속 시간 + 수집 주기 안에 울린다(E절) | 판정 안 함. E-alert |
| 정상 하루에 거짓 경보가 날 수 있는 곳 둘(E절) | 판정 안 함. 발송 적체는 "집을 수 있는 행"으로 정의해 반영했다. 판정은 E-alert |

## 4. 배운 점

### 원리

- 지표는 "알고 싶은 것"과 "그것이 틀어지면 사용자가 입는 피해"에서 거꾸로 짠다. 그렇게 하면 무엇을 세지 않을지도 같이 정해진다.
- 라벨은 값의 종류가 고정된 것만 쓴다. 지표는 문제를 알리는 데까지이고, 원인을 좁히는 것은 로그의 일이다.
- 경보에 쓸 Counter는 미리 0으로 만들어 둔다. 없는 시계열과 0인 시계열은 PromQL에서 다르게 동작한다.
- 트랜잭션 안에서 세면 롤백된 일도 센다. 커밋된 결과만 세려면 트랜잭션 경계 밖에서 센다.
- 관리 포트를 갈라도 인증 설정은 그대로 따라온다. 포트 분리는 네트워크 경로를 가르는 것이지 보안 설정을 가르는 것이 아니다.

### 예상과 달랐던 것

- `spring_security_*` 관측 지표가 앱 하나에 53개 시계열(지표 이름 44개)로, 전체의 약 4분의 1을 차지했다. 값의 종류는 정해져 있지만 경보에는 쓰지 않는다.
  - 처음에는 이름 수(44)를 시계열 수로 잘못 셌다. 라벨을 떼고 중복을 지운 뒤 센 탓이다. 다시 세어 바로잡았다.
- 노출하지 않은 엔드포인트(`/actuator/env`)가 관리 포트에서 404가 아니라 401을 돌려줬다.
  - 원인은 추론이다. `anyRequest().authenticated()`가 핸들러를 찾기 전에 먼저 막는 것으로 본다. 확인하지 않았다.
  - 내용은 드러나지 않는다.
- 매칭되지 않은 경로가 `uri="/**"` 하나로 묶여서, 아무 경로나 찔러도 HTTP 지표의 카디널리티가 늘지 않았다.

### 다시 한다면 바꿀 것

- 과제 배경과 개념 설명을 결정보다 먼저 한다. 이번에는 사용자가 요청해서 순서를 바꿨다.
- 0.2 포트 표에 관리 포트도 처음부터 적어 둔다. B·D도 같은 질문을 만나게 된다.
- Prometheus 수집 설정을 세션 임시 폴더가 아니라 실습 브랜치에 둔다. 임시 폴더는 세션이 끝나면 지워질 수 있어 E-alert가 이어 쓰지 못한다.

## 5. 남은 것

### 이 단위에서 하지 않은 것

- LOST를 뺀 나머지 앱 지표 구현(E-alert)
- 평가 주기 Timer의 30초 버킷과 그 `le` 표기 확인(E-alert)
- 실행 중인 앱에서 LOST가 오르는 것 확인(D)

### 다른 단위로 넘긴 것

- B
  - 서버 p95를 Prometheus로 볼지(HTTP 히스토그램) 정한다
  - 관리 포트가 필요하다. 0.2 표에 없다
- D: 중복 비율 `sum(rate(portfolio_alert_apply_total{outcome="lost"}[5m])) / sum(rate(portfolio_alert_apply_total[5m]))`. 사용자 변경을 넣지 않으면 복제본 경합만 남는다
- E-alert
  - 캘린더에 날짜가 없어 마감을 계산할 수 없을 때 `finalize.lag`을 어떻게 낼지 정한다
  - `spring_security_*`를 끌지 본다
  - Prometheus 설정을 브랜치에 둔다
- E-cluster
  - 운영 Ingress 유무와 경로 규칙을 확인한다
  - 운영 Prometheus가 대상을 찾는 방식을 확인한다. Service에 관리 포트가 없다
  - NetworkPolicy가 없는 상태를 확인한다

### main에 올릴 때

- back-end `docs/decisions-deploy.md`의 관리 포트 행과 "되돌리는 조건"을 고친다
- 계획서 "실습 시 고칠 문서" 중 설계서, 런북, ADR, 테스트 문서, README는 E-base에서 고치지 않았다

## 부록: 지표 이름·라벨 목록

| 코드 이름 | Prometheus 이름 | 종류 | 라벨 | 구현 |
|---|---|---|---|---|
| `portfolio.alert.apply` | `portfolio_alert_apply_total` | Counter | `outcome` = applied / fired / ended / lost | E-base |
| `portfolio.snapshot.stage` | `portfolio_snapshot_stage_seconds_*` | Timer | `stage` = credential_fill / run_process / finalize / sync_close / basis_build, `result` = ok / error | E-alert |
| `portfolio.snapshot.runs.pending` | `portfolio_snapshot_runs_pending` | Gauge(DB) | 없음 | E-alert |
| `portfolio.snapshot.run.failures` | `portfolio_snapshot_run_failures_total` | Counter | 없음 | E-alert |
| `portfolio.snapshot.runs.failed` | `portfolio_snapshot_runs_failed` | Gauge(DB) | 없음 | E-alert |
| `portfolio.snapshot.runs.failed.oldest` | `portfolio_snapshot_runs_failed_oldest_seconds` | Gauge(DB) | 없음 | E-alert |
| `portfolio.snapshot.finalize.lag` | `portfolio_snapshot_finalize_lag_seconds` | Gauge(DB) | 없음 | E-alert |
| `portfolio.alert.evaluation` | `portfolio_alert_evaluation_seconds_*` | Timer, 30초 버킷 | 없음 | E-alert |
| `portfolio.alert.evaluation.alerts` | `portfolio_alert_evaluation_alerts` | Gauge(파드별) | 없음 | E-alert |
| `portfolio.alert.evaluation.points` | `portfolio_alert_evaluation_points` | Gauge(파드별) | 없음 | E-alert |
| `portfolio.alert.delivery.due` | `portfolio_alert_delivery_due` | Gauge(DB) | 없음 | E-alert |
| `portfolio.alert.delivery.due.oldest` | `portfolio_alert_delivery_due_oldest_seconds` | Gauge(DB) | 없음 | E-alert |
| `portfolio.alert.delivery.results` | `portfolio_alert_delivery_results_total` | Counter | `result` = sent / failed / expired | E-alert |

- Gauge(DB)는 두 복제본이 같은 값을 낸다. `max`로 본다.
- Counter, Timer, Gauge(파드별)는 파드마다 따로 센다. `sum`으로 합친다.
