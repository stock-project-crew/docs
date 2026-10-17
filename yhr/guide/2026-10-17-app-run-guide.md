# 앱을 내 폰에서 실행하기

PC에서 앱 개발 서버를 띄우고, 폰의 Expo Go로 연다. 백엔드는 두 가지 중 하나에 붙인다.

| | 1부 — PC 백엔드 + 로컬 DB | 2부 — 클러스터 백엔드 + 클러스터 DB |
|---|---|---|
| 데이터 | 샘플 데이터 | 실데이터. 운영테스트 기록이 쌓이는 곳 |
| 계정 | 공개된 개발용 계정 | 자기 계정 |
| 할 수 있는 것 | 무엇이든. DB를 지우고 다시 만들어도 된다 | 평소처럼 앱을 쓰는 것만 |

명령은 macOS 기준이다. 저장소는 한 폴더 아래에 나란히 둔다고 가정한다(`<작업폴더>/back-end`, `<작업폴더>/front-end`).

---

## 0. 준비물

**PC**

| 항목 | 확인 명령 | 기대 |
|---|---|---|
| Git | `git --version` | 버전이 나온다 |
| Node.js · npm | `node -v` · `npm -v` | 버전이 나온다 |
| Docker Desktop (1부) | `docker compose version` | 버전이 나온다. Docker Desktop이 켜져 있어야 한다 |
| JDK 21 (1부) | `java -version` | `21`로 시작한다 |
| AWS CLI · 프로필 `stock-project` (2부) | `AWS_PROFILE=stock-project aws sts get-caller-identity` | 자기 IAM 사용자가 나온다 |
| Session Manager 플러그인 (2부) | `session-manager-plugin --version` | 버전이 나온다 |
| kubectl · 개인 kubeconfig (2부) | `kubectl config current-context` | `stock-project` |

**폰**

- Expo Go를 스토어에서 설치한다. 앱은 Expo SDK 54이고, 스토어판 Expo Go가 이 버전을 연다.
- PC와 **같은 Wi-Fi**에 붙인다. 회사·공용 Wi-Fi는 기기 사이 통신을 막는 경우가 있다 — 그때는 집 Wi-Fi나 PC 핫스팟을 쓴다.

**저장소** — 처음 한 번

```bash
cd <작업폴더>
git clone https://github.com/stock-project-crew/back-end.git
git clone https://github.com/stock-project-crew/front-end.git
```

이미 있으면 둘 다 `git switch main && git pull`.

**PC의 LAN IP** — 1부 · 2부 모두 쓴다

```bash
ipconfig getifaddr en0        # 예: 192.168.0.12
```

아무것도 안 나오면 `ipconfig getifaddr en1`. 이하 `<LAN IP>`는 이 값이다. Wi-Fi를 바꾸면 값이 바뀐다.

---

## 1부 — PC 백엔드 + 로컬 DB

### 1.1 DB와 백엔드를 띄운다

터미널 A:

```bash
cd <작업폴더>/back-end
docker compose up -d db
./gradlew bootRun --args='--spring.profiles.active=local'
```

`Started PortfolioApplication`이 찍히면 떴다. 이 터미널은 열어 둔다.

### 1.2 샘플 데이터를 넣는다 — DB를 새로 만들었을 때 한 번

터미널 B:

```bash
cd <작업폴더>/back-end
docker compose exec -T db psql -U portfolio -d portfolio -f /sample/sample_portfolio.sql
docker compose exec -T db psql -U portfolio -d portfolio -f /sample/sample_alert_market.sql
```

확인:

```bash
curl -s localhost:8080/actuator/health          # {"status":"UP"...}
```

### 1.3 앱 주소를 넣는다

```bash
cd <작업폴더>/front-end
cp .env.example .env
```

`.env`를 열어 한 줄을 이렇게 둔다.

```
EXPO_PUBLIC_API_BASE_URL=http://<LAN IP>:8080
```

`.env`는 커밋하지 않는다.

### 1.4 앱을 띄운다

```bash
cd <작업폴더>/front-end
npm install
npx expo start -c
```

터미널에 QR 코드가 나온다.

- **iPhone**: 기본 카메라로 QR을 찍고 Expo Go로 연다.
- **Android**: Expo Go를 열고 `Scan QR code`로 찍는다.
- QR이 안 되면 Expo Go에서 `exp://<LAN IP>:8081`을 직접 넣는다.

### 1.5 로그인

| 계정 | 비밀번호 |
|---|---|
| `yhr@a.com` · `hhj@a.com` · `jdh@a.com` | `local-dev-password` |

클러스터(2부)에서는 이 비밀번호를 쓰지 않는다 — 2.4에서 자기 비밀번호로 바꾼다.

### 1.6 브라우저로 보기 — 선택

1.4를 띄운 채로 PC 브라우저에서 `http://localhost:8081`을 연다. 주소는 정확히 이것이어야 한다(`127.0.0.1`이나 다른 포트는 백엔드가 막는다).

### 1.7 푸시 받아 보기 — 선택, iPhone만

Android의 Expo Go는 원격 푸시를 받지 않는다. Android에서는 울린 알림이 앱 안 목록과 탭 배지로만 보인다.

터미널 A에서 백엔드를 끄고(Ctrl+C) 이렇게 다시 띄운다.

```bash
EXPO_PUSH_ENABLED=true ./gradlew bootRun --args='--spring.profiles.active=local'
```

앱에서 지금 이미 맞는 조건으로 종가 알림을 저장한다(예: 가격 도달 '이상'에 아주 낮은 금액). 첫 저장 때 알림 권한을 묻는다 — 허용한다. 평가기가 1분마다 돌아 곧 울린다. 한 번 울린 알림은 다시 울리지 않으므로 다시 볼 때는 새 알림을 만든다.

### 1.8 지키는 것

- `local` 프로파일 백엔드는 **로컬 DB에만** 붙인다. `DB_URL`을 클러스터로 바꾸지 않는다 — 이 프로파일은 데이터팀 테이블의 미러를 DB에 만든다.
- 로컬 DB를 처음부터 다시 만들려면 `docker compose down -v && docker compose up -d db` 후 1.1 ~ 1.2를 다시 한다.

---

## 2부 — 클러스터 백엔드 + 클러스터 DB

PC에 백엔드를 띄우지 않는다. PC는 폰과 클러스터 사이를 잇기만 한다.

```
폰(Expo Go) → PC <LAN IP>:18080 → (port-forward) → 클러스터 portfolio-api
```

### 2.1 지키는 것

- 이 DB에 3주 운영테스트 기록이 쌓인다. **자기 계정으로 평소처럼 앱을 쓰는 것만 한다.**
- DB에 직접 접속하거나 쓰지 않는다. 2.4의 내 비밀번호 바꾸기만 예외다. 클러스터 리소스를 만들거나 지우지 않는다.
- 남의 계정으로 로그인하지 않는다.
- 접속 자격증명(`~/.aws/`, kubeconfig)과 비밀번호는 저장소 · 문서 · 채팅에 붙이지 않는다.

### 2.2 클러스터가 켜져 있는지 본다

클러스터는 정해진 시간에만 켜져 있다. 꺼져 있으면 2.3의 터널이 열리지 않는다.

### 2.3 터널을 연다

터미널 A — 열어 두고, 끝나면 Ctrl+C:

```bash
AWS_PROFILE=stock-project aws ssm start-session \
  --target i-0797d47f4be26f433 \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["6443"],"localPortNumber":["16443"]}'
```

`Waiting for connections...`가 나오면 열렸다.

터미널 B에서 확인:

```bash
kubectl -n portfolio get pods
```

`portfolio-api-…` 파드가 `Running`이면 된다.

### 2.4 처음 한 번 — 내 비밀번호를 바꾼다

클러스터 DB의 세 계정은 처음에 1.5의 공개된 비밀번호를 갖는다. 2부를 처음 쓰기 전에 자기 계정의 비밀번호를 바꾼다.

2.3의 터널을 연 채로 [`back-end/docs/ops/app-user.md`](https://github.com/stock-project-crew/back-end/blob/main/docs/ops/app-user.md)를 이 순서로 따른다.

1. "해시 만들기" — 자기 PC에서 해시를 만든다
2. "DB에 접속하기" — 표의 `운영` 명령으로 접속하고 해시를 `\prompt`로 받는다
3. "비밀번호 교체" — `WHERE email`에 **자기 이메일**을 넣는다. `RETURNING`이 1행이고 `prefix`가 `$2y$10$`일 때만 `COMMIT`한다

비밀번호와 해시는 누구에게도 보내지 않는다. 잊으면 이 절을 다시 한다.

### 2.5 API를 PC의 18080에 잇는다

터미널 B — 열어 두고, 끝나면 Ctrl+C:

```bash
kubectl -n portfolio port-forward --address 0.0.0.0 svc/portfolio-api 18080:8080
```

`--address 0.0.0.0`이 있어야 폰이 PC를 통해 닿는다. macOS가 `kubectl`의 들어오는 연결을 허용할지 물으면 허용한다.

확인 — **폰의 브라우저**에서 `http://<LAN IP>:18080/actuator/health`를 연다. `{"status":"UP"...}`이 보이면 폰에서 닿는다.

### 2.6 앱 주소를 바꾸고 띄운다

`<작업폴더>/front-end/.env`를 이렇게 둔다.

```
EXPO_PUBLIC_API_BASE_URL=http://<LAN IP>:18080
```

터미널 C:

```bash
cd <작업폴더>/front-end
npm install
npx expo start -c
```

`-c`를 꼭 붙인다. 주소가 번들에 박혀 있어 캐시를 비워야 바뀐다. 폰에서 여는 법은 1.4와 같다.

### 2.7 로그인

자기 이메일(`hhj@a.com` · `jdh@a.com` · `yhr@a.com`)과 2.4에서 정한 비밀번호로 로그인한다.

### 2.8 푸시

클러스터 백엔드가 푸시를 보내는지는 `back-end/k8s/deployment.yaml`의 `EXPO_PUSH_ENABLED` 값이 정한다. `false`면 울린 알림은 앱 안 목록과 탭 배지로만 보인다. Android는 값과 관계없이 원격 푸시를 받지 않는다.

### 2.9 끝낼 때

터미널 C · B · A 순서로 Ctrl+C. 1부로 돌아가려면 `.env`를 `http://<LAN IP>:8080`으로 되돌리고 `npx expo start -c`.

---

## 3. 막히는 곳

| 증상 | 원인 | 할 일 |
|---|---|---|
| Expo Go가 QR을 찍어도 안 열린다 · 계속 로딩 | 폰과 PC가 다른 네트워크, 또는 Wi-Fi가 기기 사이 통신을 막는다 | 같은 Wi-Fi인지 본다. 안 되면 집 Wi-Fi나 PC 핫스팟 |
| 앱은 열리는데 로그인에 `연결에 실패했어요` | 폰이 API 주소에 닿지 않는다 | 폰 브라우저로 `http://<LAN IP>:8080/actuator/health`(1부) 또는 `:18080`(2부)를 연다. 안 열리면 백엔드 · port-forward가 떠 있는지, `.env`의 IP가 지금 IP인지 본다 |
| `.env`를 고쳤는데 옛 주소로 간다 | 번들 캐시 | `npx expo start -c` |
| Expo Go가 SDK 버전이 안 맞는다고 한다 | 스토어의 Expo Go가 낡았다 | 스토어에서 Expo Go를 업데이트한다 |
| 로그인에 `이메일 또는 비밀번호가 올바르지 않습니다` | 1부에서 클러스터 비밀번호, 2부에서 `local-dev-password`를 넣었다 | 1.5 · 2.7을 본다 |
| 쓰던 중 로그인 화면으로 가며 `로그인이 만료되었어요` | 토큰 만료(12시간) | 다시 로그인한다 |
| 2.3이 오류로 끝나거나 응답이 없다 | 클러스터가 꺼져 있다 | 2.2. 켜진 시간에 다시 한다 |
| `kubectl`이 `connection refused` · `127.0.0.1:16443` | 터널(2.3)이 닫혔다 | 터미널 A의 터널을 다시 연다 |
| port-forward가 `lost connection to pod`로 끝난다 | 파드가 재시작됐거나 터널이 끊겼다 | 2.5를 다시 실행한다 |
| 1.1에서 `port 5432 already in use` | PC에 다른 Postgres가 떠 있다 | 그 Postgres를 끄고 다시 한다 |
| 1.1에서 `port 8080 already in use` | 다른 백엔드가 떠 있다 | `lsof -i :8080`으로 찾아 끈다 |
