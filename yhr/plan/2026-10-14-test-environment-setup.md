# 테스트 작업 환경 구성 — 두 대의 맥북

- **대상**: 집 맥북 · 회사 맥북. 통합테스트·운영테스트 작업을 두 머신에서 번갈아 한다
- **관련 계획**: [통합테스트 · 운영테스트 3주 계획](2026-10-11-integration-and-operation-test-plan.md)
- **원칙**: 두 머신은 같은 도구 버전과 같은 절차를 쓴다. 머신마다 다른 값은 §3에, 회사 네트워크에만 필요한 설정은 §4에 모아두고 저장소에 커밋하지 않는다

로컬에서 백엔드·앱을 띄우는 절차는 각 저장소 README가 단일 출처다 — `back-end/README.md` §실행·§테스트, `front-end/README.md` §실행·§검사. 이 문서는 그 절차가 도는 데 필요한 머신 상태만 다룬다.

---

## 1. 작업 공간

```
stock-project/
  docs/       github.com/stock-project-crew/docs
  back-end/   github.com/stock-project-crew/back-end
  front-end/  github.com/stock-project-crew/front-end
  dataeng/    데이터 담당 파이프라인
```

네 저장소는 서로 독립이다. 머신을 옮겨 작업을 시작할 때 네 곳 모두 받는다.

```bash
for d in docs back-end front-end dataeng; do git -C "$d" pull --ff-only; done
```

`--ff-only`가 거절되면 그 머신에 커밋하지 않은 작업이나 올리지 않은 커밋이 있다는 뜻이다. 합치기 전에 무엇인지 본다.

---

## 2. 머신 사전 조건

| 도구 | 버전 | 쓰는 곳 | 설치 |
|---|---|---|---|
| JDK | **21** | 백엔드 빌드·테스트. `build.gradle.kts`의 toolchain이 21이다 | 아래 |
| Docker Desktop | — | 로컬 Postgres 16 (`back-end/docker-compose.yml`) | Docker Desktop을 띄워 둔다 |
| Node.js · npm | — | 앱 실행·테스트 | `brew install node` |
| AWS CLI | v2 | 클러스터 접속 | `brew install awscli` |
| Session Manager 플러그인 | — | 클러스터 API 터널 (`aws ssm start-session`) | `brew install --cask session-manager-plugin` |
| kubectl | — | 클러스터 조회 | `brew install kubectl` |
| Expo Go (iOS 실기기) | **SDK 54** | 실기기 확인 · 푸시 수신 | App Store |

**JDK 21은 Homebrew 포뮬러로 설치하고, `JAVA_HOME`을 그 경로로 지정한다.** `./gradlew`는 `JAVA_HOME`의 JDK로 뜨고 toolchain 21을 그 JDK로 채운다. 시스템 JDK 목록에 링크할 필요가 없고, `PATH`의 기본 `java`가 다른 버전이어도 두 머신에서 같게 돈다.

```bash
brew install openjdk@21
export JAVA_HOME=$(brew --prefix openjdk@21)   # 셸 프로필에 둔다
```

psql은 머신에 설치하지 않는다. 로컬 DB는 compose 컨테이너 안의 psql을 쓴다.

```bash
cd back-end && docker compose exec -T db psql -U portfolio -d portfolio -c 'select 1'
```

Gradle은 따로 설치하지 않는다. 저장소의 `./gradlew`가 버전을 고정한다.

**Expo SDK를 54 위로 올리지 않는다.** App Store 판 Expo Go가 54에서 멈춰 있어 그 위 SDK는 실기기가 거부한다.

---

## 3. 머신마다 다른 값

저장소에 커밋하지 않는다. 머신을 옮기면 그 머신에서 다시 확인한다.

| 값 | 위치 | 머신마다 다른 이유 |
|---|---|---|
| `EXPO_PUBLIC_API_BASE_URL` | `front-end/.env` | 실기기가 개발 머신의 LAN IP로 붙는다. 집과 회사의 네트워크가 다르다. `ipconfig getifaddr en0`로 확인 |
| 로컬 DB 볼륨 | Docker 볼륨 | 머신마다 따로 있다. 샘플 적재 여부도 따로다 |
| AWS 자격증명 | `~/.aws/` | 머신마다 따로 설정한다 |
| kubeconfig | `~/.kube/config` | 머신마다 따로 설정한다 |

로컬 DB에는 다시 만들 수 있는 샘플만 둔다. 두 머신의 로컬 DB를 맞추려 하지 않는다 — 맞춰야 하는 기록은 클러스터 운영 DB와 `docs` 저장소에 있다.

`EXPO_PUBLIC_*` 값은 번들에 박히므로 `.env`를 바꾼 뒤에는 `npx expo start -c`로 캐시를 비우고 띄운다.

---

## 4. 회사 네트워크 — TLS 검사

회사 네트워크는 Fortinet 장비가 HTTPS를 가로채 사내 CA로 다시 서명한다. 사내 CA는 macOS 키체인에 들어 있지만 Homebrew JDK의 신뢰 저장소(`cacerts`)에는 없다. 그래서 JDK로 외부에 붙는 일이 실패한다 — Gradle 래퍼의 배포본 내려받기, 의존성 내려받기.

**증상**

```
PKIX path building failed: ... unable to find valid certification path to requested target
```

**확인** — 발급자가 Fortinet이면 이 절에 해당한다.

```bash
echo | openssl s_client -connect services.gradle.org:443 2>/dev/null | grep '^issuer='
```

**조치** — 사내 CA를 키체인에서 꺼내 JDK 21의 `cacerts`에만 넣는다. 셸 프로필과 다른 프로젝트의 Gradle 설정은 건드리지 않는다.

```bash
security find-certificate -c FG4H0FT923904340 -p > fortinet-ca.pem
"$(brew --prefix openjdk@21)/bin/keytool" -importcert -noprompt -cacerts \
  -storepass changeit -alias company-fortinet-ca -file fortinet-ca.pem
rm fortinet-ca.pem
```

- `FG4H0FT923904340`은 사내 CA의 이름(CN)이다. 위 확인 명령의 `issuer=`에 나온 `CN=` 값과 같아야 한다
- 이 설정은 `brew upgrade openjdk@21`로 JDK가 바뀌면 사라진다. 업그레이드 뒤에는 다시 넣는다
- 넣었는지 확인: `"$(brew --prefix openjdk@21)/bin/keytool" -list -cacerts -storepass changeit -alias company-fortinet-ca`

AWS CLI·kubectl이 같은 증상(인증서 검증 실패)을 보이면 같은 CA 파일을 `AWS_CA_BUNDLE`로 지정한다.

---

## 5. 머신 점검

머신을 옮겨 처음 작업할 때 한 번 돌린다. 모든 줄이 기대대로 나오면 그 머신에서 로컬 작업을 시작할 수 있다.

```bash
"$JAVA_HOME/bin/java" -version         # 21이 나온다
docker info --format '{{.ServerVersion}}'   # 버전이 나온다. 오류면 Docker Desktop이 꺼져 있다
aws --version
session-manager-plugin --version
kubectl version --client
ls front-end/node_modules >/dev/null && echo ok   # 없으면 front-end에서 npm ci
test -f front-end/.env && echo ok                 # 없으면 §3
```

빌드 도구가 외부에 붙는지는 DB 없이 도는 백엔드 테스트로 본다. PKIX 오류가 나면 §4.

```bash
cd back-end
JAVA_HOME=$(brew --prefix openjdk@21) ./gradlew test --tests '*MigrationLintTest' --tests '*ArchitectureRulesTest'
```

전체 확인은 README 절차를 그대로 따른다.

```bash
cd back-end && docker compose up -d db && JAVA_HOME=$(brew --prefix openjdk@21) ./gradlew test
cd ../front-end && npx tsc --noEmit && npm test
```

**Jest 변환 캐시가 빈 머신에서는 첫 실행을 직렬로 돌린다** — `npx jest -w 1`. 캐시가 빈 상태로 병렬 실행하면 `allocation` · `assetChange` · `realizedPnl` 세 스위트의 첫 테스트가 매번 실패한다. 화면이 아직 로딩 중일 때 값을 기다리는 `waitFor`(기본 1초)가 먼저 끝나기 때문이다. 직렬 실행과 캐시가 찬 뒤의 병렬 실행은 통과한다. 그 밖의 실패는 실제 실패다.

---

## 6. 클러스터 접속

클러스터 API는 인터넷에 열려 있지 않다. SSM 포트포워딩으로 로컬 16443에 터널을 열고, kubectl은 그 터널로 붙는다.

- 클러스터 운영 DB에는 **읽기만** 한다. 쓰기는 사용자 행위(앱 조작)로만 일어난다 — 계획서 §3.1
- 접속 자격증명은 `~/.aws/`와 kubeconfig에만 둔다. 저장소·문서·로그에 넣지 않는다
- 개인 kubeconfig 계정은 배포 생성·파드 삭제까지 할 수 있다. 읽기만은 권한이 아니라 규칙으로 지킨다

**준비** — 머신마다 한 번

| 항목 | 값 |
|---|---|
| AWS 프로필 | `stock-project` · 리전 `ap-northeast-2`. `aws configure --profile stock-project` |
| kubeconfig | 팀에서 받은 개인 kubeconfig를 `~/.kube/config`에 두고 `chmod 600`. context `stock-project`, 서버 `https://127.0.0.1:16443` |

**터널** — 별도 터미널에서 열어 두고, 끝나면 Ctrl+C로 닫는다.

```bash
AWS_PROFILE=stock-project aws ssm start-session \
  --target i-0797d47f4be26f433 \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["6443"],"localPortNumber":["16443"]}'
```

`kubectl -n portfolio get pods`가 목록을 돌려주면 붙은 것이다.

**API** — 로컬 8080은 로컬 백엔드가 쓰므로 다른 포트로 잇는다.

```bash
kubectl -n portfolio port-forward svc/portfolio-api 18080:8080
curl -s localhost:18080/actuator/health        # {"status":"UP",...}
```

상태 점검 말고는 전부 토큰이 필요하다. 로그인과 조회는 `back-end/README.md` §실행과 같고 주소만 `localhost:18080`이다.

**운영 DB** — 앱이 쓰는 DB는 StatefulSet `portfolio-db`의 `portfolio-db-0`이다. 같은 네임스페이스의 Deployment `postgres`는 앱이 쓰지 않는다. 파드 안의 psql을 쓰고, 세션을 읽기 전용으로 연다.

```bash
kubectl -n portfolio exec -it portfolio-db-0 -- \
  env PGOPTIONS='-c default_transaction_read_only=on' psql -U portfolio -d portfolio
```

이 세션에서 쓰기 문장은 `cannot execute ... in a read-only transaction`으로 거부된다.
