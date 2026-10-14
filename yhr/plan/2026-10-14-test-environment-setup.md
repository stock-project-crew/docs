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
| psql | 16 이상 | 관측 질의 · 데이터 품질 검사 · 클러스터 DB 조회 | `brew install libpq` 후 `/opt/homebrew/opt/libpq/bin`을 `PATH`에 추가 |
| AWS CLI | v2 | 클러스터 접속 | `brew install awscli` |
| kubectl | — | 클러스터 조회 | `brew install kubectl` |
| Expo Go (iOS 실기기) | **SDK 54** | 실기기 확인 · 푸시 수신 | App Store |

**JDK 21은 Homebrew 포뮬러로 설치하고 시스템 JDK 목록에 링크한다.** sudo가 필요 없고, `java_home`과 Gradle 툴체인 탐지가 이 링크로 JDK를 찾는다.

```bash
brew install openjdk@21
mkdir -p ~/Library/Java/JavaVirtualMachines
ln -sfn /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk ~/Library/Java/JavaVirtualMachines/openjdk-21.jdk
```

**백엔드 명령은 JDK 21로 실행한다.** `./gradlew`는 `JAVA_HOME`의 JDK로 뜨므로, `PATH`의 기본 `java`가 다른 버전이어도 아래처럼 지정하면 두 머신에서 같게 돈다.

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 21)
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
"$(/usr/libexec/java_home -v 21)/bin/keytool" -importcert -noprompt -cacerts \
  -storepass changeit -alias company-fortinet-ca -file fortinet-ca.pem
rm fortinet-ca.pem
```

- `FG4H0FT923904340`은 사내 CA의 이름(CN)이다. 위 확인 명령의 `issuer=`에 나온 `CN=` 값과 같아야 한다
- 이 설정은 `brew upgrade openjdk@21`로 JDK가 바뀌면 사라진다. 업그레이드 뒤에는 다시 넣는다
- 넣었는지 확인: `"$(/usr/libexec/java_home -v 21)/bin/keytool" -list -cacerts -storepass changeit -alias company-fortinet-ca`

AWS CLI·kubectl이 같은 증상(인증서 검증 실패)을 보이면 같은 CA 파일을 `AWS_CA_BUNDLE`로 지정한다.

---

## 5. 머신 점검

머신을 옮겨 처음 작업할 때 한 번 돌린다. 모든 줄이 기대대로 나오면 그 머신에서 로컬 작업을 시작할 수 있다.

```bash
/usr/libexec/java_home -v 21          # JDK 21 경로가 나온다
docker info --format '{{.ServerVersion}}'   # 버전이 나온다. 오류면 Docker Desktop이 꺼져 있다
psql --version                        # 16 이상
aws --version
kubectl version --client
ls front-end/node_modules >/dev/null && echo ok   # 없으면 front-end에서 npm ci
test -f front-end/.env && echo ok                 # 없으면 §3
```

빌드 도구가 외부에 붙는지는 DB 없이 도는 백엔드 테스트로 본다. PKIX 오류가 나면 §4.

```bash
cd back-end
JAVA_HOME=$(/usr/libexec/java_home -v 21) ./gradlew test --tests '*MigrationLintTest' --tests '*ArchitectureRulesTest'
```

전체 확인은 README 절차를 그대로 따른다.

```bash
cd back-end && docker compose up -d db && JAVA_HOME=$(/usr/libexec/java_home -v 21) ./gradlew test
cd ../front-end && npx tsc --noEmit && npm test
```

프론트 테스트는 변환 캐시가 빈 첫 실행에서 일부 스위트가 실패하고 다시 돌리면 통과하는 경우가 있다. 원인은 확인되지 않았다. 두 번째 실행에서도 실패하면 실제 실패로 본다.

---

## 6. 클러스터 접속

인증과 터널 절차는 접속 자료를 받은 뒤 채운다.

- 클러스터 운영 DB에는 **읽기만** 한다. 쓰기는 사용자 행위(앱 조작)로만 일어난다 — 계획서 §3.1
- 접속 자격증명은 `~/.aws/`와 kubeconfig에만 둔다. 저장소·문서·로그에 넣지 않는다
