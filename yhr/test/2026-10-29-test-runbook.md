# 테스트 실행 부록

- **작성일**: 2026-10-29
- **케이스**: [테스트 케이스](2026-10-28-test-cases.md). 케이스의 절차가 이 문서의 준비 데이터(`F-…`) · 판정 질의(`Q-…`) · 요청 묶음(`A-…`)을 ID로 가리킨다
- **설계**: [통합테스트 설계](2026-10-16-test-design.md)
- **읽는 이**: 케이스를 실행하는 Claude Code와 사람. 이 문서만으로 실행할 수 있게 쓴다

## 1. 누가 무엇을 하는가

| 일 | `로컬` | `연계` |
|---|---|---|
| API 호출 | 에이전트 | 에이전트. `it1@a.com` · `it2@a.com` 토큰으로만 |
| DB 읽기 | 에이전트. 읽기 전용 세션(§4.2) | 에이전트. 읽기 전용 세션(§4.2) |
| DB 쓰기 | 에이전트. 이 문서의 `F-…`만 적는 그대로 쓴다. 이 범위는 사전 승인됐다 | 하지 않는다. 상태는 앱 조작과 API로만 만든다 |
| 크롬 조작 | 에이전트 | 에이전트. 클러스터 백엔드에 웹 출처 허용이 배포된 뒤 |
| 로그인 | 에이전트(§3.1) | 사람(§3.2) |
| 백엔드 · 앱 기동과 재기동 | 사람. 에이전트는 사전 승인을 받은 뒤에만 | 하지 않는다 |
| 자격증명 입력 · 실기기 조작 · KIS 앱 대조 | 사람 | 사람 |

**에이전트가 지키는 것**

- 토큰 · 비밀번호 · 앱키 · 시크릿 · 계좌번호 · 푸시 토큰을 출력하지 않고, 증거와 로그에 남기지 않는다. `curl -v`를 쓰지 않는다. `credential_ref` 값은 질의에서 고르지 않고 비교 결과(참 · 거짓)만 고른다.
- `F-…`에 없는 쓰기, 다른 사용자 계정(`yhr` · `hhj` · `jdh`)으로의 `연계` 요청, 코드 수정은 하지 않는다. 실패를 찾아도 고치지 않고 기록한다.
- 기대 결과와 같으면 `통과`, 다르면 `실패`와 증거다. 기대 결과로 판정이 서지 않으면 결과를 `미실행`으로 두고 사람에게 묻는다.
- 케이스의 `실행 시점`이 지금과 맞지 않으면 돌리지 않는다.
- 수단이 `사람` · `실기기`인 단계에 오면 멈추고, 사람에게 무엇을 해 달라는지 한 줄로 말한다.

## 2. 환경

| 항목 | `로컬` | `연계` |
|---|---|---|
| API | `http://localhost:8080` | `http://localhost:18080` |
| 웹 | `http://localhost:8081` | `http://localhost:8081`(앱 `.env`의 API 주소를 `http://localhost:18080`으로) |
| DB | 로컬 Docker `portfolio` | 클러스터 `portfolio-db-0` |
| 계정 | `yhr@a.com` · `hhj@a.com` · `jdh@a.com` · `test_empty@a.com`(계좌 없음) | `it1@a.com`(본인 역) · `it2@a.com`(격리 확인용) |
| 띄우는 법 | [앱 실행 안내서](../guide/2026-10-17-app-run-guide.md) 1부. 백엔드는 §2.1의 명령으로 | 안내서 2부. 터널과 포트포워드는 사람이 연다 |

### 2.1 로컬 백엔드

수동 동기화를 닫고 수집 결과를 반영하는 단계는 보유 스냅샷 생성기 스위치로 돈다. 로컬 기본 기동은 스위치를 켠다.

```bash
cd <작업폴더>/back-end
docker compose up -d db
SNAPSHOT_RUNTIME_ENABLED=true ./gradlew bootRun --args='--spring.profiles.active=local'
```

생성기를 끈 기동이 필요한 케이스는 사전조건에 `생성기 끈 백엔드`라고 적는다. 그때는 `SNAPSHOT_RUNTIME_ENABLED=true`를 빼고 띄운다.

알림 평가기 · 발송기 · 영수증 확인기를 끈 기동이 필요한 케이스는 사전조건에 `알림 스케줄 끈 백엔드`라고 적는다. 그때는 `ALERT_RUNTIME_ENABLED=false`를 더해 띄운다(백엔드 `application.yaml`의 `enabled: ${ALERT_RUNTIME_ENABLED:true}`).

평단 · 실현손익 계산은 생성기 회차의 마지막 단계라 생성기 스위치와 평단 스위치를 함께 켜야 돈다. 로컬 기본은 끔이고 운영 배포는 켠다. 이것이 필요한 케이스는 사전조건에 `평단 계산 켠 백엔드`라고 적고 아래처럼 띄운다.

```bash
SNAPSHOT_RUNTIME_ENABLED=true BASIS_ENABLED=true ./gradlew bootRun --args='--spring.profiles.active=local'
```

로컬 기준 시각은 개발 머신의 시계다. 날짜 · 요일에 걸린 케이스는 `실행 시점`(§8)이 맞는 날에 돈다.

## 3. 로그인

토큰은 `~/.cache/stock-it/<환경>/<이메일>` 파일에 둔다. `<환경>`은 `local` · `cluster`다. 요청은 이 파일을 읽어 헤더에 넣는다(§4.1).

### 3.1 `로컬` — 에이전트가 한다

로컬 계정 비밀번호는 공개된 개발용 값(`local-dev-password`, 안내서 1.5)이다.

```bash
login_local() {
  local d="$HOME/.cache/stock-it/local"; mkdir -p "$d"; chmod 700 "$d"
  jq -n --arg e "$1" '{email:$e,password:"local-dev-password"}' \
    | curl -sf -X POST http://localhost:8080/auth/login -H 'Content-Type: application/json' -d @- \
    | jq -r .access_token > "$d/$1" && chmod 600 "$d/$1"
}
login_local yhr@a.com
```

### 3.2 `연계` — 사람이 한다

사람이 자기 터미널에서 돌린다. 비밀번호는 화면에도 기록에도 남지 않는다.

```bash
login_cluster() {
  local d="$HOME/.cache/stock-it/cluster" pw; mkdir -p "$d"; chmod 700 "$d"
  printf '%s 비밀번호: ' "$1"; read -rs pw; echo
  jq -n --arg e "$1" --arg p "$pw" '{email:$e,password:$p}' \
    | curl -sf -X POST http://localhost:18080/auth/login -H 'Content-Type: application/json' -d @- \
    | jq -r .access_token > "$d/$1" && chmod 600 "$d/$1"
  unset pw
}
login_cluster it1@a.com
login_cluster it2@a.com
```

요청이 `401`이면 토큰이 만료된 것이다. 에이전트는 `로컬`이면 다시 로그인하고, `연계`면 사람에게 다시 돌려 달라고 한다.

## 4. 요청과 질의

### 4.1 API 요청

```bash
API=http://localhost:8080; ENV=local; ME=yhr@a.com
OUT=~/stock-it-evidence/$(date +%F)/PF3-01; mkdir -p "$OUT"
curl -s -o "$OUT/01-post-sync.json" -D "$OUT/01-post-sync.headers" -w '%{http_code}\n' \
  -X POST "$API/sync" \
  -H "Authorization: Bearer $(cat ~/.cache/stock-it/$ENV/$ME)" \
  -H 'Content-Type: application/json' -d '{}'
```

`-D`로 남긴 응답 헤더에는 요청의 `Authorization`이 들어가지 않는다.

**요청 묶음**

| ID | 내용 |
|---|---|
| `A-VIEWS` | 봉투를 쓰는 여섯 뷰를 차례로 `GET`: `/portfolio/views/summary` · `/portfolio/views/positions` · `/portfolio/views/allocation?axis=market` · `/portfolio/views/accounts` · `/portfolio/views/realized-pnl` · `/portfolio/views/asset-change` |

### 4.2 DB 읽기

읽기 전용 세션을 연다. 질의의 `:'이름'`은 `-v 이름=값`으로 넘긴다.

```bash
# 로컬
docker compose -f <작업폴더>/back-end/docker-compose.yml exec -T \
  -e PGOPTIONS='-c default_transaction_read_only=on -c search_path=app,data' \
  db psql -U portfolio -d portfolio -v ON_ERROR_STOP=1 -v run=<run_id> -f - < q.sql

# 연계 — 터널이 열려 있어야 한다
kubectl -n portfolio exec -i portfolio-db-0 -- \
  env PGOPTIONS='-c default_transaction_read_only=on -c search_path=app,data' \
  psql -U portfolio -d portfolio -v ON_ERROR_STOP=1 -v run=<run_id> -f - < q.sql
```

### 4.3 DB 쓰기 — `로컬`의 `F-…`만

```bash
docker compose -f <작업폴더>/back-end/docker-compose.yml exec -T \
  -e PGOPTIONS='-c search_path=app,data' \
  db psql -U portfolio -d portfolio -v ON_ERROR_STOP=1 -v run=<run_id> -f - < f.sql
```

## 5. 증거

- 자리: `~/stock-it-evidence/<YYYY-MM-DD>/<케이스 ID>/`. 저장소 밖에 둔다
- 파일: 단계 번호를 앞에 붙인다. 응답 본문 `.json` · 응답 헤더 `.headers` · 질의 결과 `.txt` · 화면 `.png`
- 케이스의 `비고`에 결과 · 실행일 · 환경 · 증거 자리를 적는다. 실패면 기대와 다르게 보인 값을 한 줄로 더한다

## 6. 초기화

| ID | 언제 | 하는 일 |
|---|---|---|
| `R-LOCAL` | `로컬` 묶음을 시작할 때, 케이스의 사전조건이 앞 케이스에 깨졌을 때 | 샘플 두 파일을 다시 넣고(안내서 1.2) `F-00` · `F-01`을 적용한다. 샘플은 `app_user` 밖의 앱 표(계좌 · 라인 · 처리 기록 · 동기화 · 평단 · 실현손익 · 입출금 · 알림 · 기기 · `snapshot_run`)와 종목 · 수집 · 잔고 · 환율 · 시세 · 캘린더 미러를 비우고 다시 만든다. 체결 · 기업행위 미러(`cln_trade` · `cln_trade_coverage` · `corporate_action` · `ca_coverage`)는 `F-01`이 비운다. 브라우저 저장소의 마지막 동기화 실행 id(`sync.last_run_id`)는 남지만, 그 실행 조회가 `403`이면 앱이 지운다 |

`연계`는 초기화하지 않는다. 테스트 계정의 상태는 앱 조작과 API로만 바꾼다.

## 7. 준비 데이터와 판정 질의

### 7.1 공통

**로컬 사용자와 계좌** (샘플)

| 사용자 | `id` | 계좌 `account_id` · 라벨 · 출처 |
|---|---|---|
| `yhr@a.com` | `40000000-…-000000000001` | `…0001` 한국투자 위탁(KIS) · `…0002` 삼성증권(CODEF) · `…0003` 한국투자 IRP(KIS) · `…0004` 미래에셋 연금(CODEF) |
| `jdh@a.com` | `40000000-…-000000000002` | `…0005` 키움 위탁(CODEF) · `…0006` 미래에셋 IRP(CODEF) |
| `hhj@a.com` | `40000000-…-000000000003` | `…0007` 한국투자 위탁(KIS) |
| `test_empty@a.com` | `40000000-…-000000000004` | 없음 |

계좌 id의 앞부분은 `20000000-0000-0000-0000-00000000000N`이다. 샘플 라인은 `2026-07-27`(미확정)과 그 앞 날짜다.

**`F-00` 캘린더를 테스트 기간까지 늘린다** — 샘플 캘린더는 `2026-10-30`에서 끝난다. 평일을 영업일로 둔다(휴장일 없음).

```sql
INSERT INTO dim_market_calendar (market, date, is_trading_day, prev_trading_day, next_trading_day, open_at, close_at)
SELECT m.market, d::date, extract(isodow FROM d) < 6,
       (SELECT max(p::date) FROM generate_series(d - interval '7 day', d - interval '1 day', interval '1 day') p
         WHERE extract(isodow FROM p) < 6),
       (SELECT min(n::date) FROM generate_series(d + interval '1 day', d + interval '7 day', interval '1 day') n
         WHERE extract(isodow FROM n) < 6),
       CASE WHEN extract(isodow FROM d) < 6 THEN (d::date + m.open_time) AT TIME ZONE m.zone END,
       CASE WHEN extract(isodow FROM d) < 6 THEN (d::date + m.close_time) AT TIME ZONE m.zone END
  FROM generate_series('2026-10-31'::date, '2026-12-31'::date, interval '1 day') d
 CROSS JOIN (VALUES ('KR', 'Asia/Seoul', time '09:00', time '15:30'),
                    ('US', 'America/New_York', time '09:30', time '16:00')) AS m(market, zone, open_time, close_time)
ON CONFLICT (market, date) DO NOTHING;
```

**`F-01` 체결 · 기업행위 미러를 비운다** — 샘플이 비우지 않는 네 표다

```sql
TRUNCATE cln_trade, cln_trade_coverage, corporate_action, ca_coverage;
```

**`Q-USER-ACCOUNTS` 사용자의 계좌**

```sql
SELECT a.account_id, a.label, a.source, a.link_state, a.linked_at, a.kis_env
  FROM account a JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email' ORDER BY a.account_id;
```

### 7.2 PF3

**`F-PF3-DISCONNECT` 계좌 하나를 해제 상태로**

```sql
UPDATE account SET link_state = 'DISCONNECTED' WHERE account_id = :'account';
```

**`F-PF3-FINAL-TODAY` 오늘(KST)을 확정된 날로**

```sql
INSERT INTO snapshot_run (as_of, finished_at)
VALUES ((now() AT TIME ZONE 'Asia/Seoul')::date, now()) ON CONFLICT (as_of) DO NOTHING;
```

**`F-PF3-COLLECTED` 실행의 한 계좌 수집을 끝낸다** — `state`는 `DONE` · `FAILED` · `REAUTH_REQUIRED`, `reason`은 `FAILED`일 때 `SOURCE_TIMEOUT`, 그 밖에는 빈 문자열. `DONE`이면 반영 완료 시각(`silver_synced_at`)을 함께 찍는다. 생성기는 그것이 찍힌 `DONE`만 집는다

```sql
UPDATE collection_run
   SET state = :'state', finished_at = now(), failure_reason = NULLIF(:'reason', ''),
       silver_synced_at = CASE WHEN :'state' = 'DONE' THEN now() END
 WHERE run_id = (SELECT collection_run_id FROM sync_run_account
                  WHERE sync_run_id = :'run' AND account_id = :'account');
```

**`F-PF3-BUILT` 그 수집을 생성기가 처리한 것으로** — `생성기 끈 백엔드`에서 쓴다

```sql
INSERT INTO position_build (run_id, account_id, as_of, outcome, reason, built_at)
SELECT sra.collection_run_id, sra.account_id, cr.as_of, 'SKIPPED', 'NO_BALANCE', now()
  FROM sync_run_account sra JOIN collection_run cr ON cr.run_id = sra.collection_run_id
 WHERE sra.sync_run_id = :'run' AND sra.account_id = :'account';
```

**`F-PF3-AGED` 실행을 시한(96시간) 넘게 묵힌다**

```sql
UPDATE sync_run SET started_at = now() - interval '97 hours'
 WHERE run_id = :'run' AND finished_at IS NULL;
```

**`Q-PF3-RUN` 실행**

```sql
SELECT run_id, account_id, as_of, state, failure_reason, already_final, finalized_at,
       started_at, finished_at
  FROM sync_run WHERE run_id = :'run';
```

**`Q-PF3-RUN-ACCOUNTS` 실행의 계좌와 수집 행**

```sql
SELECT sra.account_id, sra.collection_run_id, sra.final_state, sra.final_as_of, sra.final_failure_reason,
       cr.requested_by, cr.as_of, cr.state, cr.failure_reason,
       cr.credential_ref IS NOT DISTINCT FROM a.credential_ref AS credential_matches,
       pb.outcome AS build_outcome, pb.reason AS build_reason
  FROM sync_run_account sra
  JOIN account a ON a.account_id = sra.account_id
  LEFT JOIN collection_run cr ON cr.run_id = sra.collection_run_id
  LEFT JOIN position_build pb ON pb.run_id = sra.collection_run_id
 WHERE sra.sync_run_id = :'run' ORDER BY sra.account_id;
```

**`Q-PF3-USER-RUNS` 사용자의 오늘(KST) 수동 수집 행 수와 실행 수**

```sql
SELECT a.account_id,
       (SELECT count(*) FROM collection_run cr
         WHERE cr.account_ref = a.account_ref AND cr.requested_by = 'USER'
           AND cr.as_of = (now() AT TIME ZONE 'Asia/Seoul')::date) AS user_runs_today
  FROM account a JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email' ORDER BY a.account_id;
SELECT count(*) AS sync_runs FROM sync_run s JOIN app_user u ON u.id = s.user_id WHERE u.email = :'email';
```

**`Q-PF3-ACCOUNT-AS-OF` 계좌별 기준일** — 사용자의 가장 늦은 `as_of` 라인에서 계좌마다 가장 이른 `source_as_of`의 KST 날짜(동기화 설계 §4.2)

```sql
WITH mine AS (SELECT a.account_id FROM account a JOIN app_user u ON u.id = a.user_id WHERE u.email = :'email'),
     latest AS (SELECT max(pl.as_of) AS d FROM position_line pl JOIN mine USING (account_id))
SELECT pl.account_id, (min(pl.source_as_of) AT TIME ZONE 'Asia/Seoul')::date AS account_as_of
  FROM position_line pl JOIN mine USING (account_id), latest
 WHERE pl.as_of = latest.d GROUP BY pl.account_id ORDER BY pl.account_id;
```

**`Q-PF3-ACCOUNT-VALUE` 그날 계좌 금액** — 계좌별 뷰 계좌 행의 `market_value_krw`(예수금 포함) · `deposit_krw`와 대조

```sql
SELECT pl.account_id,
       sum(pl.market_value_krw) AS market_value_krw,
       coalesce(sum(pl.market_value_krw) FILTER (WHERE i.asset_class = 'CASH'), 0) AS deposit_krw
  FROM position_line pl JOIN instrument i ON i.instrument_id = pl.instrument_id
 WHERE pl.as_of = :'as_of' AND pl.account_id = :'account'
 GROUP BY pl.account_id;
```

### 7.3 C1 · C2 · X1 · X2 · X3

**`F-C1-EMPTY-ACCOUNT` `test_empty@a.com`에 라인 없는 연동 계좌 하나를 둔다** — 첫 수집 전 사용자(`NO_HOLDINGS`)를 만든다

```sql
INSERT INTO account (account_id, user_id, account_ref, broker, label, account_type, source,
                     credential_ref, link_state, linked_at)
SELECT '20000000-0000-0000-0000-000000000099', u.id, 'ar_c1_no_holdings', '한국투자증권', 'C1 빈 계좌',
       'GENERAL', 'KIS', NULL, 'CONNECTED', now()
  FROM app_user u WHERE u.email = 'test_empty@a.com'
ON CONFLICT (account_id) DO NOTHING;
```

**`Q-C1-USER-ALERTS` 사용자의 삭제되지 않은 알림 수와 발화 수**

```sql
SELECT (SELECT count(*) FROM alert a JOIN app_user u ON u.id = a.user_id
         WHERE u.email = :'email' AND a.deleted_at IS NULL) AS alerts,
       (SELECT count(*) FROM alert_event e JOIN alert a USING (alert_id) JOIN app_user u ON u.id = a.user_id
         WHERE u.email = :'email') AS events;
```

**`F-X1-FINALIZE` 그날의 라인을 모두 확정 라인으로** — `snapshot_run`은 쓰지 않는다. `생성기 끈 백엔드`에서 쓴다

```sql
UPDATE position_line SET is_final = true WHERE as_of = :'as_of';
```

**`F-X1-SNAPSHOT-RUN` 그날의 보유 스냅샷 완료 신호를 쓴다**

```sql
INSERT INTO snapshot_run (as_of, finished_at) VALUES (:'as_of', now())
ON CONFLICT (as_of) DO NOTHING;
```

**`F-X1-SELL-ALL` 한 종목을 다 판 다음 날 스냅샷을 만든다** — 사용자의 `from` 라인을 `as_of`로 옮겨 적되 그 종목을 뺀다. 확정 라인으로 쓴다. `as_of`는 KR 영업일이어야 한다

```sql
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'as_of'::date, pl.account_id, pl.instrument_id, pl.quantity,
       pl.cost_amount_local, pl.market_value_local, pl.cost_amount_krw, pl.market_value_krw,
       pl.fx_rate, pl.fx_as_of,
       CASE WHEN pl.is_carried_forward THEN pl.source_as_of
            ELSE (:'as_of'::date + time '15:30') AT TIME ZONE 'Asia/Seoul' END,
       pl.is_carried_forward, true
  FROM position_line pl JOIN account a USING (account_id) JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email' AND pl.as_of = :'from' AND pl.instrument_id <> :'instrument'::uuid
ON CONFLICT (as_of, account_id, instrument_id) DO NOTHING;
```

**`Q-X1-ALERT` 알림의 상태 · 평가 상태 · 발화**

```sql
SELECT a.alert_id, a.name, a.status, a.deleted_at,
       s.last_result, s.last_known_result, s.unknown_reason,
       s.evaluated_as_of AT TIME ZONE 'Asia/Seoul' AS evaluated_as_of_kst, s.version,
       (SELECT count(*) FROM alert_event e WHERE e.alert_id = a.alert_id) AS events
  FROM alert a JOIN alert_state s USING (alert_id)
 WHERE a.alert_id = :'alert';
SELECT e.event_id, e.as_of AT TIME ZONE 'Asia/Seoul' AS as_of_kst, e.fired_at, e.title, e.lines, e.read_at
  FROM alert_event e WHERE e.alert_id = :'alert' ORDER BY e.as_of;
```

**`Q-X1-SNAPSHOT` 가장 늦은 완료 신호와 사용자의 가장 늦은 확정 라인 날짜**

```sql
SELECT (SELECT max(as_of) FROM snapshot_run) AS latest_snapshot_run,
       (SELECT max(pl.as_of) FROM position_line pl JOIN account a USING (account_id)
          JOIN app_user u ON u.id = a.user_id
         WHERE u.email = :'email' AND pl.is_final) AS latest_final_line;
```

**`Q-X1-HOLDING-PNL` 그날 그 종목의 계좌 합산 평가손익률과 이월 · 확정 여부** — 연동 중인 계좌만. 종목별 화면 행의 `unrealized_pnl_pct`와 대조

```sql
SELECT pl.as_of, i.symbol, sum(pl.quantity) AS quantity,
       sum(pl.market_value_krw) AS market_value_krw, sum(pl.cost_amount_krw) AS cost_amount_krw,
       round((sum(pl.market_value_krw) - sum(pl.cost_amount_krw)) * 100.0
             / nullif(sum(pl.cost_amount_krw), 0), 4) AS pnl_pct,
       bool_or(pl.is_carried_forward) AS carried, bool_and(pl.is_final) AS final
  FROM position_line pl JOIN account a USING (account_id) JOIN app_user u ON u.id = a.user_id
  JOIN instrument i ON i.instrument_id = pl.instrument_id
 WHERE u.email = :'email' AND pl.as_of = :'as_of' AND i.symbol = :'symbol'
   AND a.link_state <> 'DISCONNECTED' AND pl.quantity > 0
 GROUP BY pl.as_of, i.symbol;
```

**`Q-X2-PUSH-DEVICES` 푸시 수신 기기와 지금 주인** — 푸시 토큰은 고르지 않는다

```sql
SELECT d.device_id, u.email, d.platform, d.created_at, d.last_seen_at
  FROM push_device d JOIN app_user u ON u.id = d.user_id
 ORDER BY d.last_seen_at DESC;
```

**`Q-X2-USER-EVENTS` 사용자의 발화** — 늦게 울린 것부터

```sql
SELECT e.event_id, a.alert_id, a.name AS alert_name, e.title,
       e.as_of AT TIME ZONE 'Asia/Seoul' AS as_of_kst, e.fired_at, e.read_at
  FROM alert_event e JOIN alert a USING (alert_id) JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email'
 ORDER BY e.fired_at DESC;
```

**`Q-X2-EVENT-DELIVERY` 발화 하나의 주인 · 읽음과 발송 행** — 발송 행이 없으면 발송 칸이 빈 한 줄이다

```sql
SELECT e.event_id, owner.email AS owner, e.title, e.read_at,
       d.device_id, d.state, d.attempts, d.sent_at, d.last_error,
       now_user.email AS device_user_now
  FROM alert_event e
  JOIN alert a USING (alert_id)
  JOIN app_user owner ON owner.id = a.user_id
  LEFT JOIN alert_delivery d ON d.event_id = e.event_id
  LEFT JOIN push_device pd ON pd.device_id = d.device_id
  LEFT JOIN app_user now_user ON now_user.id = pd.user_id
 WHERE e.event_id = :'event';
```

### 7.4 PF1 · PF2 · PF4

PF3의 `Q-PF3-ACCOUNT-VALUE`와 공통 `Q-USER-ACCOUNTS`를 함께 쓴다. `credential_ref` 값은 고르지 않고 비교 결과만 고른다.

**`F-PF1-EOD` 계좌에 그날 EOD 수집 요청 행을 만든다** — 데이터 쪽 `create_eod`의 대역이다. `credential_ref`는 비워 두고, 생성기의 자격증명 채우기가 1분 안에 채운다

```sql
INSERT INTO collection_run (run_id, account_ref, requested_by, as_of, requested_at, state)
SELECT gen_random_uuid(), a.account_ref, 'SCHEDULE', (now() AT TIME ZONE 'Asia/Seoul')::date, now(), 'REQUESTED'
  FROM account a WHERE a.account_id = :'account';
```

**`F-PF1-FINISH` 계좌의 `REQUESTED` 수집을 끝낸다** — `state`는 `DONE` · `FAILED`, `reason`은 `FAILED`일 때 `SOURCE_API_ERROR`, 그 밖에는 빈 문자열. `DONE`이면 원화 예수금 1,000,000원 잔고를 함께 넣고 반영 완료 시각을 찍는다. `F-PF1-EOD`보다 1초 넘게 뒤에 돌린다

```sql
INSERT INTO cln_deposit (account_ref, currency, amount, source_as_of)
SELECT a.account_ref, 'KRW', 1000000, now() - interval '1 second'
  FROM account a WHERE a.account_id = :'account' AND :'state' = 'DONE';
UPDATE collection_run r
   SET state = :'state', finished_at = now(), failure_reason = NULLIF(:'reason', ''),
       silver_synced_at = CASE WHEN :'state' = 'DONE' THEN now() END
  FROM account a
 WHERE a.account_id = :'account' AND r.account_ref = a.account_ref AND r.state = 'REQUESTED';
```

**`F-PF2-DROP-ACCOUNT` 라인 · 수집 행이 없는 계좌 행을 없앤다** — 해제 시트가 열린 사이 "이미 없는 계좌"를 만든다. 다른 표가 참조하면 실패한다

```sql
DELETE FROM account WHERE account_id = :'account'
   AND NOT EXISTS (SELECT 1 FROM position_line WHERE account_id = :'account');
```

**`F-PF4-REAUTH-RUN` 계좌의 그날 수집을 재인증 요구로 끝낸다** — 데이터 워커가 `REAUTH_REQUIRED`를 낸 것과 같다. 생성기가 1분 안에 계좌를 `REAUTH_REQUIRED`로 옮긴다

```sql
INSERT INTO collection_run (run_id, account_ref, requested_by, as_of, requested_at, state, finished_at)
SELECT gen_random_uuid(), a.account_ref, 'SCHEDULE', (now() AT TIME ZONE 'Asia/Seoul')::date,
       now() - interval '1 minute', 'REAUTH_REQUIRED', now()
  FROM account a WHERE a.account_id = :'account';
```

**`F-PF4-CARRY` 계좌의 그날 라인을 이월값으로 바꾼다**

```sql
UPDATE position_line SET is_carried_forward = true, source_as_of = :'source_as_of'::timestamptz
 WHERE account_id = :'account' AND as_of = :'as_of'::date;
```

**`Q-PF1-LINK` 사용자 계좌의 연동 상태와 자격증명 참조 모양**

```sql
SELECT a.account_id, a.label, a.broker, a.account_type, a.source, a.link_state, a.kis_env, a.linked_at,
       a.credential_ref = '/stock-project/accounts/' || a.account_ref AS credential_ref_matches,
       a.credential_ref IS NULL AS credential_ref_null
  FROM account a JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email' ORDER BY a.account_id;
```

**`Q-PF1-RUNS` 계좌의 수집 행과 생성기 처리**

```sql
SELECT r.requested_by, r.as_of, r.state, r.failure_reason, r.requested_at, r.finished_at,
       r.credential_ref IS NULL AS credential_null,
       r.credential_ref IS NOT DISTINCT FROM a.credential_ref AS credential_matches,
       pb.outcome AS build_outcome, pb.reason AS build_reason
  FROM account a JOIN collection_run r ON r.account_ref = a.account_ref
  LEFT JOIN position_build pb ON pb.run_id = r.run_id
 WHERE a.account_id = :'account' ORDER BY r.requested_at;
```

**`Q-PF1-RAW` 원문 문자열이 들어 있는 행 수** — `needle`은 가짜 앱키 · 시크릿 · 계좌번호. `로컬`에서만 쓴다

```sql
SELECT (SELECT count(*) FROM account a WHERE a::text LIKE '%' || :'needle' || '%') AS account_rows,
       (SELECT count(*) FROM collection_run r WHERE r::text LIKE '%' || :'needle' || '%') AS collection_run_rows;
```

**`Q-PF1-LINES` 사용자의 날짜 · 계좌별 라인**

```sql
SELECT pl.as_of, pl.account_id, count(*) AS line_count, sum(pl.market_value_krw) AS market_value_krw,
       bool_or(pl.is_carried_forward) AS carried, bool_or(pl.is_final) AS final
  FROM position_line pl JOIN account a USING (account_id) JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email' AND pl.as_of >= :'from'::date
 GROUP BY pl.as_of, pl.account_id ORDER BY pl.as_of, pl.account_id;
```

**`Q-PF2-RUNS-SINCE` 그 시각 뒤 계좌에 생긴 수집 행 수**

```sql
SELECT count(*) AS runs_since
  FROM collection_run r JOIN account a ON a.account_ref = r.account_ref
 WHERE a.account_id = :'account' AND r.requested_at > :'since'::timestamptz;
```

**`Q-PF2-ALERT-STATE` 사용자 알림의 평가 상태**

```sql
SELECT al.alert_id, al.name, al.status, s.last_result, s.unknown_reason, s.evaluated_as_of
  FROM alert al JOIN app_user u ON u.id = al.user_id
  LEFT JOIN alert_state s ON s.alert_id = al.alert_id
 WHERE u.email = :'email' AND al.deleted_at IS NULL ORDER BY al.created_at;
```

### 7.5 PF5 · PF6 · PF7

질의의 범위는 화면과 같다. 최신 기준일은 그 사용자 계좌에 라인이 있는 가장 늦은 `as_of`(해제 계좌 포함)이고, 현재 보유 값은 `DISCONNECTED`가 아닌 계좌만 더한다(포트폴리오 §3.8 · §7.5). 자산 변화의 기초 · 기말은 해제 계좌의 과거도 센다.

**`F-PF5-SAME-INSTRUMENT` 삼성전자를 두 번째 계좌에도 보유시킨다** — `yhr@a.com`의 `…0002`(삼성증권)에 `2026-07-27` 삼성전자 100주(매입 7,000,000 · 평가 7,120,000)

```sql
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
VALUES ('2026-07-27', '20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001', 100,
        7000000, 7120000, 7000000, 7120000, 1, '2026-07-27', '2026-07-27T15:30:00+09', false, false)
ON CONFLICT DO NOTHING;
```

**`F-PF6-COVERED` TIGER 미국나스닥100을 구성종목 확보 ETF로**

```sql
INSERT INTO etf_coverage (etf_instrument_id, state, as_of)
VALUES ('10000000-0000-0000-0000-000000000006', 'COVERED', '2026-07-27')
ON CONFLICT (etf_instrument_id) DO UPDATE SET state = 'COVERED', as_of = EXCLUDED.as_of;
```

**`F-PF7-NO-DEPOSIT` `yhr@a.com`의 7월 입금을 지운다**

```sql
DELETE FROM manual_cashflow WHERE id = '30000000-0000-0000-0000-000000000001';
```

**`Q-PF5-TOTALS` 최신 기준일의 합계** — 스냅샷 뷰 `total`과 대조

```sql
WITH me AS (SELECT id FROM app_user WHERE email = :'email'),
     d AS (SELECT max(pl.as_of) AS as_of
             FROM position_line pl JOIN account a USING (account_id)
            WHERE a.user_id = (SELECT id FROM me)),
     l AS (SELECT pl.*, i.asset_class
             FROM position_line pl
             JOIN account a USING (account_id)
             JOIN instrument i USING (instrument_id)
             CROSS JOIN d
            WHERE a.user_id = (SELECT id FROM me) AND pl.as_of = d.as_of
              AND a.link_state <> 'DISCONNECTED')
SELECT (SELECT as_of FROM d) AS as_of,
       sum(market_value_krw) AS total_assets_krw,
       coalesce(sum(market_value_krw) FILTER (WHERE asset_class <> 'CASH'), 0) AS securities_value_krw,
       coalesce(sum(market_value_krw) FILTER (WHERE asset_class = 'CASH'), 0) AS deposit_krw,
       coalesce(sum(cost_amount_krw) FILTER (WHERE asset_class <> 'CASH'), 0) AS cost_amount_krw,
       coalesce(sum(market_value_krw - cost_amount_krw) FILTER (WHERE asset_class <> 'CASH'), 0) AS unrealized_pnl_krw,
       count(DISTINCT instrument_id) FILTER (WHERE asset_class <> 'CASH') AS instrument_count,
       count(DISTINCT account_id) AS account_count,
       (SELECT count(*) FROM position_line pl JOIN account a USING (account_id)
         WHERE a.user_id = (SELECT id FROM me) AND pl.is_final) AS final_lines
  FROM l;
```

**`Q-PF5-BY-INSTRUMENT` 종목별 수량 · 평단** — 종목별 뷰 행과 대조. 평단은 `Σ매입(현지) ÷ Σ수량`, 원화 0자리 · 달러 2자리 반올림

```sql
WITH me AS (SELECT id FROM app_user WHERE email = :'email'),
     d AS (SELECT max(pl.as_of) AS as_of
             FROM position_line pl JOIN account a USING (account_id)
            WHERE a.user_id = (SELECT id FROM me))
SELECT i.symbol, i.name, i.currency,
       sum(pl.quantity) AS quantity,
       CASE WHEN i.asset_class = 'CASH' THEN NULL
            ELSE round(sum(pl.cost_amount_local) / sum(pl.quantity),
                       CASE i.currency WHEN 'KRW' THEN 0 ELSE 2 END) END AS avg_cost,
       sum(pl.market_value_krw) AS market_value_krw,
       sum(pl.market_value_local) AS market_value_local,
       count(DISTINCT pl.account_id) AS accounts
  FROM position_line pl
  JOIN account a USING (account_id)
  JOIN instrument i USING (instrument_id)
  CROSS JOIN d
 WHERE a.user_id = (SELECT id FROM me) AND pl.as_of = d.as_of
   AND a.link_state <> 'DISCONNECTED'
 GROUP BY i.symbol, i.name, i.currency, i.asset_class
 ORDER BY market_value_krw DESC, i.symbol;
```

**`Q-PF5-BY-ACCOUNT` 계좌유형 소계와 계좌 행** — 계좌별 뷰와 대조. `account_id`가 빈 행이 소계

```sql
WITH me AS (SELECT id FROM app_user WHERE email = :'email'),
     d AS (SELECT max(pl.as_of) AS as_of
             FROM position_line pl JOIN account a USING (account_id)
            WHERE a.user_id = (SELECT id FROM me)),
     l AS (SELECT pl.*, a.account_type, a.label, i.asset_class
             FROM position_line pl
             JOIN account a USING (account_id)
             JOIN instrument i USING (instrument_id)
             CROSS JOIN d
            WHERE a.user_id = (SELECT id FROM me) AND pl.as_of = d.as_of
              AND a.link_state <> 'DISCONNECTED'),
     t AS (SELECT sum(market_value_krw) AS total FROM l)
SELECT account_type, account_id, label,
       sum(market_value_krw) AS market_value_krw,
       coalesce(sum(market_value_krw) FILTER (WHERE asset_class = 'CASH'), 0) AS deposit_krw,
       coalesce(sum(cost_amount_krw) FILTER (WHERE asset_class <> 'CASH'), 0) AS cost_amount_krw,
       coalesce(sum(market_value_krw - cost_amount_krw) FILTER (WHERE asset_class <> 'CASH'), 0) AS unrealized_pnl_krw,
       round(sum(market_value_krw) * 100 / (SELECT total FROM t), 1) AS weight_pct
  FROM l
 GROUP BY GROUPING SETS ((account_type), (account_type, account_id, label))
 ORDER BY account_type, account_id NULLS FIRST;
```

**`Q-PF5-FX` 통화별로 적용한 환율과 가장 이른 기준일** — `FX_APPLIED.params.rates`와 대조

```sql
WITH me AS (SELECT id FROM app_user WHERE email = :'email'),
     d AS (SELECT max(pl.as_of) AS as_of
             FROM position_line pl JOIN account a USING (account_id)
            WHERE a.user_id = (SELECT id FROM me))
SELECT DISTINCT ON (i.currency) i.currency || '/KRW' AS pair, pl.fx_rate, pl.fx_as_of
  FROM position_line pl
  JOIN account a USING (account_id)
  JOIN instrument i USING (instrument_id)
  CROSS JOIN d
 WHERE a.user_id = (SELECT id FROM me) AND pl.as_of = d.as_of
   AND a.link_state <> 'DISCONNECTED' AND i.currency <> 'KRW'
 ORDER BY i.currency, pl.fx_as_of;
```

**`Q-PF5-DAILY` 직전 기준일과 일간 변화** — 요약 `daily_change_krw` · `daily_change_pct`와 대조. 직전 쪽도 오늘 연동이 유효한 계좌만 더한다. `isodow` 1 = 월, 5 = 금

```sql
WITH me AS (SELECT id FROM app_user WHERE email = :'email'),
     cur AS (SELECT max(pl.as_of) AS as_of
               FROM position_line pl JOIN account a USING (account_id)
              WHERE a.user_id = (SELECT id FROM me)),
     prev AS (SELECT max(pl.as_of) AS as_of
                FROM position_line pl JOIN account a USING (account_id)
               WHERE a.user_id = (SELECT id FROM me) AND a.link_state <> 'DISCONNECTED'
                 AND pl.as_of < (SELECT as_of FROM cur)),
     tot AS (SELECT (SELECT sum(pl.market_value_krw) FROM position_line pl JOIN account a USING (account_id)
                      WHERE a.user_id = (SELECT id FROM me) AND a.link_state <> 'DISCONNECTED'
                        AND pl.as_of = (SELECT as_of FROM cur)) AS total_now,
                    (SELECT sum(pl.market_value_krw) FROM position_line pl JOIN account a USING (account_id)
                      WHERE a.user_id = (SELECT id FROM me) AND a.link_state <> 'DISCONNECTED'
                        AND pl.as_of = (SELECT as_of FROM prev)) AS total_prev)
SELECT (SELECT as_of FROM cur) AS as_of,
       extract(isodow FROM (SELECT as_of FROM cur)) AS as_of_dow,
       (SELECT as_of FROM prev) AS prev_as_of,
       extract(isodow FROM (SELECT as_of FROM prev)) AS prev_dow,
       total_now, total_prev,
       total_now - total_prev AS daily_change_krw,
       round((total_now - total_prev) * 100 / nullif(total_prev, 0), 1) AS daily_change_pct
  FROM tot;
```

**`Q-PF6-GROUP` 시장 또는 통화 축 묶음** — `axis`는 `market` · `currency`. 비중 분석 행과 대조. `currencies`가 1이고 원화가 아닐 때만 현지 통화가 병기된다

```sql
WITH me AS (SELECT id FROM app_user WHERE email = :'email'),
     d AS (SELECT max(pl.as_of) AS as_of
             FROM position_line pl JOIN account a USING (account_id)
            WHERE a.user_id = (SELECT id FROM me))
SELECT CASE :'axis' WHEN 'market' THEN i.market ELSE i.currency END AS key,
       count(DISTINCT i.currency) AS currencies,
       min(i.currency) AS currency,
       sum(pl.market_value_krw) AS market_value_krw,
       sum(pl.market_value_local) AS market_value_local,
       coalesce(sum(pl.cost_amount_krw) FILTER (WHERE i.asset_class <> 'CASH'), 0) AS cost_amount_krw,
       coalesce(sum(pl.cost_amount_local) FILTER (WHERE i.asset_class <> 'CASH'), 0) AS cost_amount_local,
       count(DISTINCT pl.instrument_id) FILTER (WHERE i.asset_class <> 'CASH') AS instrument_count
  FROM position_line pl
  JOIN account a USING (account_id)
  JOIN instrument i USING (instrument_id)
  CROSS JOIN d
 WHERE a.user_id = (SELECT id FROM me) AND pl.as_of = d.as_of
   AND a.link_state <> 'DISCONNECTED'
 GROUP BY 1
 ORDER BY market_value_krw DESC;
```

**`Q-PF6-ETF-COVERAGE` 보유 ETF의 구성종목 확보 상태** — `etf_coverage`에 `COVERED`가 없으면 렌즈를 켜도 분해하지 않는다

```sql
WITH me AS (SELECT id FROM app_user WHERE email = :'email'),
     d AS (SELECT max(pl.as_of) AS as_of
             FROM position_line pl JOIN account a USING (account_id)
            WHERE a.user_id = (SELECT id FROM me))
SELECT i.symbol, i.name, coalesce(c.state, '없음') AS coverage_state, c.as_of AS coverage_as_of,
       sum(pl.market_value_krw) AS market_value_krw
  FROM position_line pl
  JOIN account a USING (account_id)
  JOIN instrument i USING (instrument_id)
  LEFT JOIN etf_coverage c ON c.etf_instrument_id = pl.instrument_id
  CROSS JOIN d
 WHERE a.user_id = (SELECT id FROM me) AND pl.as_of = d.as_of
   AND a.link_state <> 'DISCONNECTED' AND i.asset_class = 'ETF'
 GROUP BY i.symbol, i.name, c.state, c.as_of
 ORDER BY i.symbol;
```

**`Q-PF7-PAIR` 자산 변화의 기초 · 기말과 넣은 돈** — `from` · `to`는 `YYYY-MM-DD`, `account`는 비우거나 쉼표로 이은 계좌 id. 기초는 기간 시작 전 마지막 라인(없으면 기간 안 첫 라인), 기말은 기간 끝 이하 마지막 라인, 넣은 돈은 (기초, 기말] 구간(포트폴리오 §2.9 · 동작은 `SnapshotPairResolver` · `ManualCashflowMapper`). 배당 · 수수료는 0이라 `investment_pnl`이 응답의 `earned`와 같다

```sql
WITH me AS (SELECT id FROM app_user WHERE email = :'email'),
     mine AS (SELECT a.account_id FROM account a
               WHERE a.user_id = (SELECT id FROM me)
                 AND (:'account' = '' OR a.account_id::text = ANY (string_to_array(:'account', ',')))),
     days AS (SELECT DISTINCT pl.as_of FROM position_line pl JOIN account a USING (account_id)
               WHERE a.user_id = (SELECT id FROM me)),
     pair AS (SELECT coalesce((SELECT max(as_of) FROM days WHERE as_of < :'from'::date),
                              (SELECT min(as_of) FROM days WHERE as_of >= :'from'::date)) AS opening,
                     (SELECT max(as_of) FROM days WHERE as_of <= :'to'::date) AS closing,
                     NOT EXISTS (SELECT 1 FROM days WHERE as_of < :'from'::date) AS opening_substituted),
     ends AS (
       SELECT p.*,
              (SELECT coalesce(sum(pl.market_value_krw), 0) FROM position_line pl JOIN mine USING (account_id)
                WHERE pl.as_of = p.opening) AS opening_krw,
              (SELECT coalesce(sum(pl.market_value_krw), 0) FROM position_line pl JOIN mine USING (account_id)
                WHERE pl.as_of = p.closing) AS closing_krw,
              (SELECT coalesce(sum(pl.market_value_krw), 0) FROM position_line pl JOIN mine USING (account_id)
                WHERE pl.as_of = p.closing
                  AND pl.account_id NOT IN (SELECT x.account_id FROM position_line x WHERE x.as_of = p.opening)) AS included_krw,
              (SELECT coalesce(sum(pl.market_value_krw), 0) FROM position_line pl JOIN mine USING (account_id)
                WHERE pl.as_of = p.opening
                  AND pl.account_id NOT IN (SELECT x.account_id FROM position_line x WHERE x.as_of = p.closing)) AS excluded_krw,
              (SELECT coalesce(sum(CASE m.type WHEN 'DEPOSIT' THEN m.amount ELSE -m.amount END), 0)
                 FROM manual_cashflow m JOIN mine USING (account_id)
                WHERE m.occurred_on > p.opening AND m.occurred_on <= p.closing) AS deposited
         FROM pair p)
SELECT opening, closing, opening_substituted, opening_krw, closing_krw, deposited, included_krw, excluded_krw,
       closing_krw - opening_krw - deposited - included_krw + excluded_krw AS investment_pnl
  FROM ends;
```

### 7.6 PF8 · PF9 · PF11

PF10은 준비 데이터 · 판정 질의가 없다(종목 상세 구현이 없어 모든 케이스가 유보다). PF9-16의 `F-PF9-SEEDED`는 `평단 계산 켠 백엔드`(§2.1)에서 쓰고, 끝나면 `R-LOCAL`이다. PF8은 `F-PF3-DISCONNECT`를 함께 쓴다.

PF11의 `F-…`는 `\gset`으로 날짜를 정하므로 `-f -`로 넘기는 §4.3의 방식 그대로 돈다. 오늘이 KR 영업일이 아니면 `\gset`이 행을 얻지 못해 멈춘다.

**`Q-PF8-CASHFLOWS` 사용자의 입출금**

```sql
SELECT m.id, m.account_id, a.label, m.type, m.amount, m.currency, m.occurred_on, m.memo
  FROM manual_cashflow m
  JOIN account a ON a.account_id = m.account_id
  JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email'
 ORDER BY m.occurred_on DESC, m.id;
```

**`Q-PF8-WINDOW` 견준 두 잔고의 총자산과 그 사이 넣은 돈** — 자산 변화의 `opening` · `closing` · `deposited`와 대조. `after` · `through`는 입출금 목록 응답의 `window` 값

```sql
WITH mine AS (SELECT a.account_id FROM account a JOIN app_user u ON u.id = a.user_id WHERE u.email = :'email')
SELECT (SELECT coalesce(sum(pl.market_value_krw), 0) FROM position_line pl JOIN mine USING (account_id)
         WHERE pl.as_of = :'after')   AS opening,
       (SELECT coalesce(sum(pl.market_value_krw), 0) FROM position_line pl JOIN mine USING (account_id)
         WHERE pl.as_of = :'through') AS closing,
       (SELECT coalesce(sum(m.amount) FILTER (WHERE m.type = 'DEPOSIT'), 0)
             - coalesce(sum(m.amount) FILTER (WHERE m.type = 'WITHDRAW'), 0)
          FROM manual_cashflow m JOIN mine USING (account_id)
         WHERE m.occurred_on > :'after' AND m.occurred_on <= :'through') AS deposited;
```

**`F-PF9-EXCLUDED` 합계에서 빠질 체결 두 건을 넣는다** — `…0003`의 `UNAVAILABLE` 한 건, `…0004`의 `CONFLICT` 한 건. 둘 다 `2026-04`이고 원가 · 손익이 없다. 샘플의 `T-0004`(`…0002` `CONFLICT`, `2026-04-01`)와 합쳐 빠진 계좌가 셋이다. 생성기를 켠 기동에서도 덮어쓰지 않게 닫힌 행으로 둔다

```sql
INSERT INTO realized_pnl_line (trade_id, account_id, instrument_id, sold_at, quantity,
    sell_amount_local, cost_basis_local, sell_amount_krw, cost_basis_krw,
    fee_tax, realized_pnl_local, realized_pnl_krw, grade,
    evaluated_as_of, position_closed, ca_unknown, seed_reason, coverage_start_at) VALUES
 ('T-9001', '20000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000006',
   '2026-04-10T10:00:00+09', 10, 1100000, NULL, 1100000, NULL, 1000, NULL, NULL, 'UNAVAILABLE',
   DATE '2026-04-10', true, false, NULL, NULL),
 ('T-9002', '20000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000002',
   '2026-04-15T10:00:00+09', 1, 200000, NULL, 200000, NULL, 500, NULL, NULL, 'CONFLICT',
   DATE '2026-04-15', true, false, NULL, NULL);
```

**`F-PF9-SEEDED` 확보 구간이 늦게 시작한 계좌의 매도를 만든다** — `…0001`(`ar_7f3a91c4`)의 거래내역 확보 구간을 `2026-07-24 ~ 2026-07-27`(확정 아님)로 두고 그 안에 삼성전자 50주 매도(`T-PF916`)를 넣는다. 07-24 확정 라인의 200주가 확보 구간 시작 전에 산 보유분이다. 07-27 라인을 매도 뒤 150주로 고쳐 확정하고 `2026-07-27` 완료 신호를 쓴다. 기업행위 확인 범위를 올해 전체로 둬 `ca_unknown`이 서지 않게 한다. `R-LOCAL` 직후에 쓴다

```sql
BEGIN;
INSERT INTO cln_trade_coverage (account_ref, covered_from, covered_to, is_definitive, empty_streak, computed_at)
VALUES ('ar_7f3a91c4', '2026-07-24', '2026-07-27', false, 0, now());
INSERT INTO cln_trade (trade_id, account_ref, instrument_id, isin, side, quantity, price, fee, tax, currency,
                       executed_at, trade_date)
VALUES ('T-PF916', 'ar_7f3a91c4', '10000000-0000-0000-0000-000000000001', 'KR7005930003', 'SELL',
        50, 71200, 1000, 5000, 'KRW', '2026-07-27T10:00:00+09', '2026-07-27');
INSERT INTO ca_coverage (market, instrument_id, covered_from, covered_to, state)
VALUES ('KR', '10000000-0000-0000-0000-000000000001', '2026-01-01', '2026-12-31', 'COVERED');
UPDATE position_line
   SET quantity = 150, cost_amount_local = 9000000, cost_amount_krw = 9000000,
       market_value_local = 10680000, market_value_krw = 10680000
 WHERE as_of = '2026-07-27' AND account_id = '20000000-0000-0000-0000-000000000001'
   AND instrument_id = '10000000-0000-0000-0000-000000000001';
UPDATE position_line SET is_final = true
 WHERE as_of = '2026-07-27' AND account_id = '20000000-0000-0000-0000-000000000001';
INSERT INTO snapshot_run (as_of, finished_at) VALUES ('2026-07-27', now()) ON CONFLICT (as_of) DO NOTHING;
COMMIT;
```

**`Q-PF9-TRADES` 사용자의 기간 매도 체결과 항등식** — 기간은 체결일(KST) 기준, 양 끝 포함. 원가가 없는 `UNAVAILABLE` · `CONFLICT` 행은 `identity_ok`가 null이다

```sql
SELECT r.trade_id, r.account_id, i.symbol,
       (r.sold_at AT TIME ZONE 'Asia/Seoul')::date AS sold_on, r.quantity,
       r.sell_amount_krw, r.cost_basis_krw, r.fee_tax, r.realized_pnl_krw, r.grade,
       r.seed_reason, r.coverage_start_at, r.ca_unknown, r.position_closed,
       r.sell_amount_krw - r.cost_basis_krw - r.fee_tax = r.realized_pnl_krw AS identity_ok
  FROM realized_pnl_line r
  JOIN account a ON a.account_id = r.account_id
  JOIN app_user u ON u.id = a.user_id
  JOIN instrument i ON i.instrument_id = r.instrument_id
 WHERE u.email = :'email'
   AND (r.sold_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN :'from' AND :'to'
 ORDER BY r.sold_at DESC, r.trade_id;
```

**`Q-PF9-BASIS` 사용자 계좌의 그 종목 평단 상태와 평단 계산 처리 기록**

```sql
SELECT a.account_id, i.symbol, pb.evaluated_as_of, pb.evaluated_qty, pb.opening_qty, pb.seed_avg_price,
       pb.avg_cost_local, pb.avg_cost_krw, pb.grade, pb.seed_permanent, pb.coverage_start_at, pb.ca_unknown
  FROM position_basis pb
  JOIN account a ON a.account_id = pb.account_id
  JOIN app_user u ON u.id = a.user_id
  JOIN instrument i ON i.instrument_id = pb.instrument_id
 WHERE u.email = :'email' AND i.symbol = :'symbol'
 ORDER BY a.account_id;
SELECT b.account_id, b.as_of, b.outcome, b.reason
  FROM basis_build b
  JOIN account a ON a.account_id = b.account_id
  JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email'
 ORDER BY b.as_of, b.account_id;
```

**`Q-PF11-DATES` 오늘 · 이월할 날 `{d}` · 그 직전 영업일 `{prev}`** — 모두 KR 캘린더 기준

```sql
SELECT c.date AS today, c.is_trading_day AS today_is_trading_day,
       c.prev_trading_day AS d, p.prev_trading_day AS prev
  FROM dim_market_calendar c
  JOIN dim_market_calendar p ON p.market = 'KR' AND p.date = c.prev_trading_day
 WHERE c.market = 'KR' AND c.date = (now() AT TIME ZONE 'Asia/Seoul')::date;
```

**`F-PF11-CARRY` `{d}`에 `…0003`만 EOD 수집이 실패한 상태를 만든다** — `yhr@a.com`의 네 계좌에 `{prev}` 확정 라인을 샘플 `2026-07-27` 금액으로 심고(모두 실측), `…0001` · `…0002` · `…0004`에 `{d}` 확정 라인을 심고, `…0003`에 `{d}`의 `SCHEDULE` `FAILED` 수집 행을 넣는다. 생성기가 1~2분 안에 `…0003`을 처리하고 `{prev}` 라인을 `{d}`로 이월해 확정한다. `R-LOCAL` 직후에 쓴다

```sql
SELECT c.prev_trading_day AS d, p.prev_trading_day AS prev
  FROM dim_market_calendar c
  JOIN dim_market_calendar p ON p.market = 'KR' AND p.date = c.prev_trading_day
 WHERE c.market = 'KR' AND c.date = (now() AT TIME ZONE 'Asia/Seoul')::date AND c.is_trading_day
\gset

BEGIN;
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'prev'::date, account_id, instrument_id, quantity,
       cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
       fx_rate, :'prev'::date, (:'prev' || ' 15:30:00+09')::timestamptz, false, true
  FROM position_line
 WHERE as_of = '2026-07-27'
   AND account_id IN ('20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
                      '20000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000004');

INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'d'::date, account_id, instrument_id, quantity,
       cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
       fx_rate, :'d'::date, (:'d' || ' 15:30:00+09')::timestamptz, false, true
  FROM position_line
 WHERE as_of = '2026-07-27'
   AND account_id IN ('20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
                      '20000000-0000-0000-0000-000000000004');

INSERT INTO collection_run (run_id, account_ref, requested_by, as_of, requested_at,
    state, finished_at, failure_reason)
SELECT gen_random_uuid(), account_ref, 'SCHEDULE', :'d'::date, now() - interval '2 minutes',
       'FAILED', now() - interval '1 minute', 'SOURCE_TIMEOUT'
  FROM account WHERE account_id = '20000000-0000-0000-0000-000000000003';
COMMIT;
```

**`F-PF11-RECOVER` 오늘 네 계좌 수집이 모두 성공한 것으로** — `{오늘}` 잠정 실측 라인을 샘플 `2026-07-27` 금액으로 쓰되 `…0003`의 TIGER 미국나스닥100 평가금액만 11,500,000으로 올린다. `F-PF11-CARRY`가 끝난 같은 날에 쓴다

```sql
SELECT c.date AS today
  FROM dim_market_calendar c
 WHERE c.market = 'KR' AND c.date = (now() AT TIME ZONE 'Asia/Seoul')::date AND c.is_trading_day
\gset

INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'today'::date, account_id, instrument_id, quantity, cost_amount_local,
       CASE WHEN account_id = '20000000-0000-0000-0000-000000000003'
             AND instrument_id = '10000000-0000-0000-0000-000000000006' THEN 11500000 ELSE market_value_local END,
       cost_amount_krw,
       CASE WHEN account_id = '20000000-0000-0000-0000-000000000003'
             AND instrument_id = '10000000-0000-0000-0000-000000000006' THEN 11500000 ELSE market_value_krw END,
       fx_rate, :'today'::date, now(), false, false
  FROM position_line
 WHERE as_of = '2026-07-27'
   AND account_id IN ('20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
                      '20000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000004');
```

**`Q-PF11-LINES` 그날 사용자의 계좌별 라인 요약**

```sql
SELECT pl.account_id, count(*) AS lines, sum(pl.market_value_krw) AS market_value_krw,
       bool_or(pl.is_carried_forward) AS carried, bool_and(pl.is_final) AS final,
       (min(pl.source_as_of) AT TIME ZONE 'Asia/Seoul')::date AS source_as_of
  FROM position_line pl
  JOIN account a ON a.account_id = pl.account_id
  JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email' AND pl.as_of = :'as_of'
 GROUP BY pl.account_id ORDER BY pl.account_id;
```

**`Q-PF11-BUILD` 그날 생성기 처리 기록과 날짜 확정**

```sql
SELECT pb.account_id, pb.run_id IS NOT NULL AS from_run, pb.outcome, pb.reason
  FROM position_build pb
  JOIN account a ON a.account_id = pb.account_id
  JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email' AND pb.as_of = :'as_of'
 ORDER BY pb.account_id, pb.build_id;
SELECT as_of, finished_at FROM snapshot_run WHERE as_of = :'as_of';
```

### 7.7 AL1 · AL2 · AL3 · AL4

AL1 ~ AL4가 함께 쓰는 질의는 `Q-AL1-…` · `Q-AL3-…`로 둔다. 푸시 토큰 값은 고르지 않는다(실행 부록 §1).

**`F-AL1-SEARCH` 검색 정렬을 가를 종목 셋을 더한다** — 로컬 종목 마스터 미러에만 쓴다. `R-LOCAL`이 지운다

```sql
INSERT INTO instrument (instrument_id, isin, symbol, name, asset_class, market, currency, sector, is_leveraged) VALUES
 ('10000000-0000-0000-0000-000000000091', NULL, '006400', '삼성SDI', 'STOCK', 'KR', 'KRW', NULL, false),
 ('10000000-0000-0000-0000-000000000092', NULL, '102780', 'KODEX 삼성그룹', 'ETF', 'KR', 'KRW', NULL, false),
 ('10000000-0000-0000-0000-000000000093', NULL, 'AAPU', 'Direxion Daily AAPL Bull 2X Shares', 'ETF', 'US', 'USD', NULL, true)
ON CONFLICT (instrument_id) DO NOTHING;
```

**`F-AL1-EMPTY-MASTER` 종목 마스터를 비운다** — 포트폴리오 뷰도 함께 깨지므로 케이스가 끝나면 곧바로 `R-LOCAL`

```sql
DELETE FROM instrument;
```

**`F-AL3-FAKE-DEVICE` 사용자에게 가짜 iOS 기기 하나를 등록한다** — 로컬은 Expo 발송이 꺼져 있어 실제로 보내지 않는다. `R-LOCAL`이 지운다

```sql
INSERT INTO push_device (device_id, user_id, expo_push_token, platform, created_at, last_seen_at)
SELECT '50000000-0000-0000-0000-0000000000a3', u.id, 'ExponentPushToken[local-it-al3]', 'IOS', now(), now()
  FROM app_user u WHERE u.email = :'email'
ON CONFLICT DO NOTHING;
```

**`Q-AL1-ALERTS` 사용자의 알림과 평가 상태** — 삭제된 알림도 고른다. `events`는 그 알림의 발화 수

```sql
SELECT a.alert_id, a.name, a.instrument_id, a.cadence, a.notify_mode, a.cooldown_min, a.expires_at,
       a.status, a.trigger_type, a.trigger_spec, a.spec_version, a.created_at, a.deleted_at,
       s.last_result, s.last_known_result, s.unknown_reason, s.evaluated_as_of, s.version,
       (SELECT count(*) FROM alert_event e WHERE e.alert_id = a.alert_id) AS events
  FROM alert a
  JOIN alert_state s USING (alert_id)
  JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email'
 ORDER BY a.created_at, a.alert_id;
```

**`Q-AL1-WATCHLIST` 알림 대상 종목**

```sql
SELECT instrument_id, market, intraday FROM alert_watchlist ORDER BY instrument_id;
```

**`Q-AL1-DEVICES` 사용자의 푸시 수신 기기** — 토큰은 고르지 않는다

```sql
SELECT d.device_id, d.platform, d.created_at, d.last_seen_at
  FROM push_device d JOIN app_user u ON u.id = d.user_id
 WHERE u.email = :'email'
 ORDER BY d.created_at;
```

**`Q-AL2-LAG` 저장된 조건에 `lag`가 있는가**

```sql
SELECT alert_id, trigger_type, trigger_spec::text LIKE '%"lag"%' AS has_lag, trigger_spec
  FROM alert WHERE alert_id = :'alert';
```

**`Q-AL3-EVENTS` 사용자의 발화** — 데이터 시점 내림차순

```sql
SELECT e.event_id, e.alert_id, a.name AS alert_name, e.as_of, e.fired_at,
       e.title, e.body, e.lines, e.observed, e.read_at
  FROM alert_event e
  JOIN alert a USING (alert_id)
  JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email'
 ORDER BY e.as_of DESC, e.event_id;
```

**`Q-AL3-UNREAD` 사용자의 미확인 발화 수** — 삭제된 알림의 발화도 센다(알림 §6.8)

```sql
SELECT count(*) AS unread
  FROM alert_event e JOIN alert a USING (alert_id) JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email' AND e.read_at IS NULL;
```

**`Q-AL3-DELIVERIES` 사용자 발화의 기기별 발송 상태** — 토큰은 고르지 않는다

```sql
SELECT dl.event_id, dl.device_id, d.platform, dl.state, dl.attempts, dl.next_attempt_at,
       dl.sent_at, dl.expo_ticket_id IS NOT NULL AS has_ticket, dl.last_error
  FROM alert_delivery dl
  JOIN alert_event e USING (event_id)
  JOIN alert a USING (alert_id)
  JOIN app_user u ON u.id = a.user_id
  LEFT JOIN push_device d ON d.device_id = dl.device_id
 WHERE u.email = :'email'
 ORDER BY e.as_of DESC, dl.event_id, dl.device_id;
```

**`Q-AL3-FLOW-STREAK` 최신 수급 신호 날까지 외국인이 3일 연속 순매수한 국내 종목** — `연계`에서 수급 변형의 종목을 고른다. 읽기만 한다

```sql
WITH latest AS (
  SELECT max((as_of AT TIME ZONE 'Asia/Seoul')::date) AS d
    FROM market_data_run WHERE market = 'KR' AND kind = 'DAILY_FLOW' AND state = 'DONE'
), last3 AS (
  SELECT f.instrument_id, f.date, f.foreign_net_buy_krw,
         row_number() OVER (PARTITION BY f.instrument_id ORDER BY f.date DESC) AS rn
    FROM investor_flow_daily f, latest WHERE f.date <= latest.d
)
SELECT i.instrument_id, i.symbol, i.name
  FROM last3 JOIN instrument i USING (instrument_id), latest
 WHERE last3.rn <= 3 AND i.market = 'KR' AND i.asset_class <> 'CASH' AND i.delisted_on IS NULL
 GROUP BY i.instrument_id, i.symbol, i.name, latest.d
HAVING count(*) = 3 AND bool_and(last3.foreign_net_buy_krw > 0) AND max(last3.date) = latest.d
 ORDER BY i.symbol LIMIT 5;
```

### 7.8 AL5 · AL6 · AL7 · AL8

시각 값(`at`)은 `2026-10-29T10:20:00+09:00` 꼴로 넘긴다. 날짜 값(`d`)은 `2026-09-28` 꼴이다. 발화 · 상태의 시각은 KST로 바꿔 고른다.

**`F-AL5-QUOTE` 장중 스냅샷 한 행** — 완료 신호는 따로 넣는다(`F-AL5-QUOTE-DONE`)

```sql
INSERT INTO intraday_quote (instrument_id, snapshot_at, price, cum_volume)
VALUES (:'instrument', :'at', :'price', 100000);
```

**`F-AL5-QUOTE-DONE` 그 시각의 장중 완료 신호** — `market`은 `KR` · `US`

```sql
INSERT INTO market_data_run (market, kind, as_of, state, finished_at)
VALUES (:'market', 'INTRADAY_QUOTE', :'at', 'DONE', now());
```

**`F-AL5-PRIOR-FIRE` 알림이 `at`보다 `ago`분 앞에 울린 것으로** — 그 시점의 발화 한 행을 넣고 평가 상태를 그 시점으로 맞춘다. `known`은 지금 엣지 기준(`TRUE` · `FALSE`)

```sql
INSERT INTO alert_event (event_id, alert_id, as_of, fired_at, title, body, lines, observed, read_at)
VALUES (gen_random_uuid(), :'alert',
        :'at'::timestamptz - make_interval(mins => :'ago'::int),
        :'at'::timestamptz - make_interval(mins => :'ago'::int),
        '주입한 이전 발화', '주입한 이전 발화', '[]', '{}', now());
UPDATE alert_state
   SET last_result = :'known', last_known_result = :'known', unknown_reason = NULL,
       evaluated_as_of = :'at'::timestamptz - make_interval(mins => :'ago'::int)
 WHERE alert_id = :'alert';
```

**`F-AL6-BAR` 종목의 그날 일봉** — 고가 · 저가는 종가 ±500

```sql
INSERT INTO adjusted_price_daily (instrument_id, date, open, high, low, close, volume, adj_factor)
VALUES (:'instrument', :'d', :'close', :'close'::numeric + 500, :'close'::numeric - 500, :'close', 1000000, 1);
```

**`F-AL6-DAILY-RUN` 그 거래일의 일별 완료 신호** — `kind`는 `DAILY_BAR` · `DAILY_FLOW`, `state`는 `DONE` · `FAILED`. `as_of`는 캘린더의 `close_at`이다

```sql
INSERT INTO market_data_run (market, kind, as_of, state, finished_at)
SELECT market, :'kind', close_at, :'state', now()
  FROM dim_market_calendar WHERE market = :'market' AND date = :'d';
```

**`F-AL7-EXPIRE-NOW` 알림의 유효기간을 방금 지난 것으로** — 다음 평가 주기가 `EXPIRED`로 옮긴다

```sql
UPDATE alert SET expires_at = now() - interval '1 minute' WHERE alert_id = :'alert';
```

**`Q-AL5-STATE` 알림의 상태와 평가 상태**

```sql
SELECT a.alert_id, a.status, a.notify_mode, s.last_result, s.last_known_result, s.unknown_reason,
       to_char(s.evaluated_as_of AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') AS evaluated_as_of_kst,
       s.version
  FROM alert a JOIN alert_state s ON s.alert_id = a.alert_id
 WHERE a.alert_id = :'alert';
```

**`Q-AL5-EVENTS` 알림의 발화** — 데이터 시점 순

```sql
SELECT event_id,
       to_char(as_of AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') AS as_of_kst,
       to_char(fired_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI:SS') AS fired_at_kst,
       title, body, lines, observed, read_at IS NOT NULL AS read
  FROM alert_event WHERE alert_id = :'alert' ORDER BY as_of;
```

**`Q-AL5-DELIVERIES` 알림의 발화별 발송 행** — 발송 행이 없는 발화는 발송 열이 비어 나온다

```sql
SELECT e.event_id, to_char(e.as_of AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') AS as_of_kst,
       d.device_id, p.platform, d.state, d.attempts, d.last_error
  FROM alert_event e
  LEFT JOIN alert_delivery d ON d.event_id = e.event_id
  LEFT JOIN push_device p ON p.device_id = d.device_id
 WHERE e.alert_id = :'alert' ORDER BY e.as_of, d.device_id;
```

**`Q-AL5-SIGNALS` 시장의 최근 완료 신호 10개**

```sql
SELECT kind, state,
       to_char(as_of AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') AS as_of_kst,
       to_char(finished_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI:SS') AS finished_at_kst
  FROM market_data_run WHERE market = :'market'
 ORDER BY as_of DESC LIMIT 10;
```

**`Q-AL5-QUOTES` 종목의 최근 장중 스냅샷 5개**

```sql
SELECT to_char(snapshot_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') AS snapshot_kst, price, cum_volume
  FROM intraday_quote WHERE instrument_id = :'instrument'
 ORDER BY snapshot_at DESC LIMIT 5;
```

**`Q-AL5-WATCHLIST` 종목의 알림 대상 행**

```sql
SELECT instrument_id, market, intraday FROM alert_watchlist WHERE instrument_id = :'instrument';
```

**`Q-AL7-LAG` 알림의 평가 시점과 그 시장 종류별 최신 `DONE`** — `evaluated_as_of_kst`가 기다리는 종류의 `latest_done_kst`보다 이르면 평가 전(평가기 미가동 · 대기), 같고 `last_result = UNKNOWN`이면 확인 불가, `FALSE`면 조건 거짓

```sql
SELECT a.alert_id, a.cadence, a.status, i.market, s.last_result, s.unknown_reason,
       to_char(s.evaluated_as_of AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') AS evaluated_as_of_kst,
       r.kind,
       to_char(max(r.as_of) AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') AS latest_done_kst
  FROM alert a
  JOIN alert_state s ON s.alert_id = a.alert_id
  JOIN instrument i ON i.instrument_id = a.instrument_id
  JOIN market_data_run r ON r.market = i.market AND r.state = 'DONE'
 WHERE a.alert_id = :'alert'
 GROUP BY a.alert_id, a.cadence, a.status, i.market, s.last_result, s.unknown_reason, s.evaluated_as_of, r.kind
 ORDER BY r.kind;
```

**`Q-AL8-DEVICES` 사용자의 푸시 수신 기기** — 토큰은 고르지 않는다

```sql
SELECT p.device_id, p.platform, p.created_at, p.last_seen_at
  FROM push_device p JOIN app_user u ON u.id = p.user_id
 WHERE u.email = :'email' ORDER BY p.created_at;
```

**`Q-AL8-USER-EVENTS` 사용자의 발화와 발화별 발송 행 수**

```sql
SELECT e.event_id, e.title, e.body, e.read_at IS NOT NULL AS read,
       (SELECT count(*) FROM alert_delivery d WHERE d.event_id = e.event_id) AS deliveries
  FROM alert_event e
  JOIN alert a ON a.alert_id = e.alert_id
  JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email' ORDER BY e.fired_at;
```

### 7.9 시나리오 밖 케이스 — 포트폴리오

`F-N-…`는 `로컬`에서만 쓴다(§4.3). 계좌 · 종목 id는 §7.1의 표기(`…0001` = `20000000-0000-0000-0000-000000000001`, 종목 `10000000-0000-0000-0000-00000000000N`)를 쓴다.

종목 id: `…0001` 삼성전자(005930) · `…0002` SK하이닉스(000660) · `…0003` NAVER(035420) · `…0004` 애플(AAPL) · `…0005` 마이크로소프트(MSFT) · `…0006` TIGER 미국나스닥100(133690) · `…0007` KRW 예수금 · `…0008` USD 예수금.

**준비 데이터**

**`F-N-FX-RATE` USD/KRW `BASE` 환율 한 행을 넣는다** — `as_of` · `rate`

```sql
INSERT INTO fx_rate (as_of, currency_pair, rate_type, rate, source)
VALUES (:'as_of'::date, 'USD/KRW', 'BASE', :'rate'::numeric, 'np-local')
ON CONFLICT (as_of, currency_pair, rate_type) DO UPDATE SET rate = EXCLUDED.rate;
```

**`F-N-FINISH-USD` 계좌의 `REQUESTED` 수집을 원화 · 달러 예수금 잔고와 함께 끝낸다** — `F-PF1-FINISH`(`state=DONE`)와 같고 예수금이 KRW 1,000,000 · USD 100 두 행이다. `F-PF1-EOD`보다 1초 넘게 뒤에 돌린다

```sql
BEGIN;
INSERT INTO cln_deposit (account_ref, currency, amount, source_as_of)
SELECT a.account_ref, c.currency, c.amount, now() - interval '1 second'
  FROM account a CROSS JOIN (VALUES ('KRW', 1000000), ('USD', 100)) AS c(currency, amount)
 WHERE a.account_id = :'account';
UPDATE collection_run r
   SET state = 'DONE', finished_at = now(), failure_reason = NULL, silver_synced_at = now()
  FROM account a
 WHERE a.account_id = :'account' AND r.account_ref = a.account_ref AND r.state = 'REQUESTED';
COMMIT;
```

**`F-N-FX-NEAR` 오늘보다 8일 앞선 환율 하나만 두고, 그 사이 평일 하루를 KR 휴장일로 바꾼다** — 앞의 `\gset`이 바꿀 날을 `holiday`로 정한다. 끝나면 `F-N-FX-NEAR-UNDO`(`holiday`). `prev_trading_day` · `next_trading_day`는 고치지 않는다

```sql
SELECT (now() AT TIME ZONE 'Asia/Seoul')::date AS today,
       (now() AT TIME ZONE 'Asia/Seoul')::date - 8 AS fx_day
\gset
SELECT max(date) AS holiday FROM dim_market_calendar
 WHERE market = 'KR' AND date > :'fx_day'::date AND date < :'today'::date AND is_trading_day
\gset
\echo fx_day=:fx_day holiday=:holiday
BEGIN;
DELETE FROM fx_rate WHERE currency_pair = 'USD/KRW';
INSERT INTO fx_rate (as_of, currency_pair, rate_type, rate, source)
VALUES (:'fx_day'::date, 'USD/KRW', 'BASE', 1400, 'np-local');
UPDATE dim_market_calendar SET is_trading_day = false WHERE market = 'KR' AND date = :'holiday'::date;
COMMIT;
```

**`F-N-FX-NEAR-UNDO`** — `holiday`

```sql
UPDATE dim_market_calendar SET is_trading_day = true WHERE market = 'KR' AND date = :'holiday'::date;
```

**`F-N-HOLIDAY-TODAY` 오늘(KST)을 KR 휴장일로** — 끝나면 `F-N-HOLIDAY-TODAY-UNDO`

```sql
UPDATE dim_market_calendar SET is_trading_day = false
 WHERE market = 'KR' AND date = (now() AT TIME ZONE 'Asia/Seoul')::date;
```

**`F-N-HOLIDAY-TODAY-UNDO`**

```sql
UPDATE dim_market_calendar SET is_trading_day = true
 WHERE market = 'KR' AND date = (now() AT TIME ZONE 'Asia/Seoul')::date;
```

**`F-N-CAL-GAP-TODAY` 오늘(KST)의 KR 캘린더 행을 지운다** — 평일에만 쓴다. 끝나면 `F-N-CAL-GAP-TODAY-UNDO`

```sql
DELETE FROM dim_market_calendar WHERE market = 'KR' AND date = (now() AT TIME ZONE 'Asia/Seoul')::date;
```

**`F-N-CAL-GAP-TODAY-UNDO`** — `F-00`과 같은 식으로 오늘의 KR 행을 되살린다

```sql
INSERT INTO dim_market_calendar (market, date, is_trading_day, prev_trading_day, next_trading_day, open_at, close_at)
SELECT 'KR', d, extract(isodow FROM d) < 6,
       (SELECT max(p::date) FROM generate_series(d - interval '7 day', d - interval '1 day', interval '1 day') p
         WHERE extract(isodow FROM p) < 6),
       (SELECT min(n::date) FROM generate_series(d + interval '1 day', d + interval '7 day', interval '1 day') n
         WHERE extract(isodow FROM n) < 6),
       CASE WHEN extract(isodow FROM d) < 6 THEN (d + time '09:00') AT TIME ZONE 'Asia/Seoul' END,
       CASE WHEN extract(isodow FROM d) < 6 THEN (d + time '15:30') AT TIME ZONE 'Asia/Seoul' END
  FROM (SELECT (now() AT TIME ZONE 'Asia/Seoul')::date AS d) t
ON CONFLICT (market, date) DO NOTHING;
```

**`F-N-USER-DONE` 수동 동기화 실행의 한 계좌 수집을 원화 예수금 잔고와 함께 끝낸다** — `run` · `account` · `amount`. `F-PF3-COLLECTED`와 달리 반영 완료 시각(`silver_synced_at`)을 찍는다. `POST /sync`보다 1초 넘게 뒤에 돌린다

```sql
BEGIN;
INSERT INTO cln_deposit (account_ref, currency, amount, source_as_of)
SELECT a.account_ref, 'KRW', :'amount'::numeric, now() - interval '1 second'
  FROM account a WHERE a.account_id = :'account';
UPDATE collection_run
   SET state = 'DONE', finished_at = now(), failure_reason = NULL, silver_synced_at = now()
 WHERE run_id = (SELECT collection_run_id FROM sync_run_account
                  WHERE sync_run_id = :'run' AND account_id = :'account');
COMMIT;
```

**`F-N-DONE-UNSYNCED` 계좌의 `REQUESTED` 수집을 끝내되 반영 완료 시각을 비운다** — `account`. 예수금 KRW 1,000,000. `F-PF1-EOD`보다 1초 넘게 뒤에 돌린다

```sql
BEGIN;
INSERT INTO cln_deposit (account_ref, currency, amount, source_as_of)
SELECT a.account_ref, 'KRW', 1000000, now() - interval '1 second' FROM account a WHERE a.account_id = :'account';
UPDATE collection_run r
   SET state = 'DONE', finished_at = now(), failure_reason = NULL, silver_synced_at = NULL
  FROM account a
 WHERE a.account_id = :'account' AND r.account_ref = a.account_ref AND r.state = 'REQUESTED';
COMMIT;
```

**`F-N-SYNCED` 그 수집에 반영 완료 시각을 찍는다** — `account`

```sql
UPDATE collection_run r SET silver_synced_at = now()
  FROM account a
 WHERE a.account_id = :'account' AND r.account_ref = a.account_ref
   AND r.state = 'DONE' AND r.silver_synced_at IS NULL;
```

**`F-N-TWO-SETS` 예수금 잔고 두 벌(10초 전 500,000 · 1초 전 1,000,000)을 쓰고 수집을 끝낸다** — `account`. `F-PF1-EOD`보다 15초 넘게 뒤에 돌린다

```sql
BEGIN;
INSERT INTO cln_deposit (account_ref, currency, amount, source_as_of)
SELECT a.account_ref, 'KRW', v.amount, now() - v.ago
  FROM account a CROSS JOIN (VALUES (500000, interval '10 second'), (1000000, interval '1 second')) AS v(amount, ago)
 WHERE a.account_id = :'account';
UPDATE collection_run r
   SET state = 'DONE', finished_at = now(), failure_reason = NULL, silver_synced_at = now()
  FROM account a
 WHERE a.account_id = :'account' AND r.account_ref = a.account_ref AND r.state = 'REQUESTED';
COMMIT;
```

**`F-N-BALANCE-ONLY` 예수금 없이 종목 잔고 한 행만 쓰고 수집을 끝낸다** — `account`. 삼성전자 10주(평단 70,000 · 평가 712,000). `F-PF1-EOD`보다 1초 넘게 뒤에 돌린다

```sql
BEGIN;
INSERT INTO cln_balance (account_ref, instrument_id, isin, quantity, avg_price, market_value, currency, source_as_of, ingest_id)
SELECT a.account_ref, '10000000-0000-0000-0000-000000000001', 'KR7005930003', 10, 70000, 712000, 'KRW',
       now() - interval '1 second', 'np-local'
  FROM account a WHERE a.account_id = :'account';
UPDATE collection_run r
   SET state = 'DONE', finished_at = now(), failure_reason = NULL, silver_synced_at = now()
  FROM account a
 WHERE a.account_id = :'account' AND r.account_ref = a.account_ref AND r.state = 'REQUESTED';
COMMIT;
```

**`F-N-UNMATCHED` 종목 마스터에 없는 종목 잔고와 예수금을 함께 쓰고 수집을 끝낸다** — `account`. 예수금 KRW 1,000,000, 모르는 종목 1주(평가 10,000)

```sql
BEGIN;
INSERT INTO cln_deposit (account_ref, currency, amount, source_as_of)
SELECT a.account_ref, 'KRW', 1000000, now() - interval '1 second' FROM account a WHERE a.account_id = :'account';
INSERT INTO cln_balance (account_ref, instrument_id, isin, quantity, avg_price, market_value, currency, source_as_of, ingest_id)
SELECT a.account_ref, gen_random_uuid(), NULL, 1, 10000, 10000, 'KRW', now() - interval '1 second', 'np-local'
  FROM account a WHERE a.account_id = :'account';
UPDATE collection_run r
   SET state = 'DONE', finished_at = now(), failure_reason = NULL, silver_synced_at = now()
  FROM account a
 WHERE a.account_id = :'account' AND r.account_ref = a.account_ref AND r.state = 'REQUESTED';
COMMIT;
```

**`F-N-DUP-CASH` 예수금과 같은 의사종목을 종목 잔고로도 쓰고 수집을 끝낸다** — `account`. 한 벌에서 KRW 예수금 라인이 둘이 된다(그레인 유일성 위반)

```sql
BEGIN;
INSERT INTO cln_deposit (account_ref, currency, amount, source_as_of)
SELECT a.account_ref, 'KRW', 1000000, now() - interval '1 second' FROM account a WHERE a.account_id = :'account';
INSERT INTO cln_balance (account_ref, instrument_id, isin, quantity, avg_price, market_value, currency, source_as_of, ingest_id)
SELECT a.account_ref, '10000000-0000-0000-0000-000000000007', NULL, 5, 1, 5, 'KRW',
       now() - interval '1 second', 'np-local'
  FROM account a WHERE a.account_id = :'account';
UPDATE collection_run r
   SET state = 'DONE', finished_at = now(), failure_reason = NULL, silver_synced_at = now()
  FROM account a
 WHERE a.account_id = :'account' AND r.account_ref = a.account_ref AND r.state = 'REQUESTED';
COMMIT;
```

**`F-N-DROP-INSTRUMENT-PF` 종목 마스터에서 한 종목 행을 지운다** — `instrument`. `R-LOCAL`이 되살린다

```sql
DELETE FROM instrument WHERE instrument_id = :'instrument';
```

**`F-N-BREAK-NO-LINE` `…0002`의 `2026-07-27` 라인을 지운다** — 연동 계좌의 라인 누락

```sql
DELETE FROM position_line WHERE as_of = '2026-07-27' AND account_id = '20000000-0000-0000-0000-000000000002';
```

**`F-N-BREAK-CASH` `…0001`의 `2026-07-27` KRW 예수금 행 원가를 평가금액과 다르게**

```sql
UPDATE position_line SET cost_amount_krw = market_value_krw - 1
 WHERE as_of = '2026-07-27' AND account_id = '20000000-0000-0000-0000-000000000001'
   AND instrument_id = '10000000-0000-0000-0000-000000000007';
```

**`F-N-BREAK-CARRY` `…0004`의 `2026-07-27` 이월 라인 원천 시각을 기준일 뒤로**

```sql
UPDATE position_line SET source_as_of = '2026-07-27T16:00:00+09'
 WHERE as_of = '2026-07-27' AND account_id = '20000000-0000-0000-0000-000000000004';
```

**`F-N-FINAL-TODAY-LINES` 사용자의 `2026-07-27` 라인을 오늘(KST) 확정 실측 라인으로 옮겨 적는다** — `email`. 오늘이 KR 영업일이 아니면 `\gset`이 멈춘다

```sql
SELECT c.date AS today FROM dim_market_calendar c
 WHERE c.market = 'KR' AND c.date = (now() AT TIME ZONE 'Asia/Seoul')::date AND c.is_trading_day
\gset
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'today'::date, pl.account_id, pl.instrument_id, pl.quantity,
       pl.cost_amount_local, pl.market_value_local, pl.cost_amount_krw, pl.market_value_krw,
       pl.fx_rate, :'today'::date, (:'today' || ' 15:30:00+09')::timestamptz, false, true
  FROM position_line pl JOIN account a USING (account_id) JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email' AND pl.as_of = '2026-07-27'
ON CONFLICT (as_of, account_id, instrument_id) DO NOTHING;
```

**`F-N-REAUTH-CARRY` `{d}`에 `…0003`만 수집이 재인증 요구로 끝난 상태를 만든다** — `F-PF11-CARRY`와 같고 마지막 수집 행의 상태만 `REAUTH_REQUIRED`(사유 없음)다. `R-LOCAL` 직후에 쓴다

```sql
SELECT c.prev_trading_day AS d, p.prev_trading_day AS prev
  FROM dim_market_calendar c
  JOIN dim_market_calendar p ON p.market = 'KR' AND p.date = c.prev_trading_day
 WHERE c.market = 'KR' AND c.date = (now() AT TIME ZONE 'Asia/Seoul')::date AND c.is_trading_day
\gset

BEGIN;
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'prev'::date, account_id, instrument_id, quantity,
       cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
       fx_rate, :'prev'::date, (:'prev' || ' 15:30:00+09')::timestamptz, false, true
  FROM position_line
 WHERE as_of = '2026-07-27'
   AND account_id IN ('20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
                      '20000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000004');

INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'d'::date, account_id, instrument_id, quantity,
       cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
       fx_rate, :'d'::date, (:'d' || ' 15:30:00+09')::timestamptz, false, true
  FROM position_line
 WHERE as_of = '2026-07-27'
   AND account_id IN ('20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
                      '20000000-0000-0000-0000-000000000004');

INSERT INTO collection_run (run_id, account_ref, requested_by, as_of, requested_at, state, finished_at)
SELECT gen_random_uuid(), account_ref, 'SCHEDULE', :'d'::date, now() - interval '2 minutes',
       'REAUTH_REQUIRED', now() - interval '1 minute'
  FROM account WHERE account_id = '20000000-0000-0000-0000-000000000003';
COMMIT;
```

**`F-N-NO-RUN-CARRY` `{d}`에 `…0003`만 수집 행이 없고 나머지 세 계좌는 수집이 실패한 상태를 만든다** — 네 계좌에 `{prev}` 확정 라인을 심고(모두 실측), `…0001` · `…0002` · `…0004`에 `{d}`의 `SCHEDULE` `FAILED` 수집 행을 넣는다. `{d}` 라인은 심지 않는다. `R-LOCAL` 직후에 쓴다

```sql
SELECT c.prev_trading_day AS d, p.prev_trading_day AS prev
  FROM dim_market_calendar c
  JOIN dim_market_calendar p ON p.market = 'KR' AND p.date = c.prev_trading_day
 WHERE c.market = 'KR' AND c.date = (now() AT TIME ZONE 'Asia/Seoul')::date AND c.is_trading_day
\gset

BEGIN;
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'prev'::date, account_id, instrument_id, quantity,
       cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
       fx_rate, :'prev'::date, (:'prev' || ' 15:30:00+09')::timestamptz, false, true
  FROM position_line
 WHERE as_of = '2026-07-27'
   AND account_id IN ('20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
                      '20000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000004');

INSERT INTO collection_run (run_id, account_ref, requested_by, as_of, requested_at, state, finished_at, failure_reason)
SELECT gen_random_uuid(), account_ref, 'SCHEDULE', :'d'::date, now() - interval '2 minutes',
       'FAILED', now() - interval '1 minute', 'SOURCE_TIMEOUT'
  FROM account
 WHERE account_id IN ('20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
                      '20000000-0000-0000-0000-000000000004');
COMMIT;
```

**`F-N-CARRY-TWICE` `…0003`이 `{p1}` · `{d}` 이틀 연속 수집에 실패한 상태를 만든다** — `{d}`는 오늘의 직전 KR 영업일, `{p1}`은 그 직전, `{p2}`는 또 그 직전이다. `{p2}`에 네 계좌 실측 확정 라인, `{p1}`에 `…0001` · `…0002` · `…0004` 실측과 `…0003` 이월(원천 `{p2}`) 확정 라인, `{d}`에 `…0001` · `…0002` · `…0004` 실측 확정 라인과 `…0003`의 `SCHEDULE` `FAILED` 수집 행을 넣는다. `R-LOCAL` 직후에 쓴다

```sql
SELECT c.prev_trading_day AS d, p.prev_trading_day AS p1, q.prev_trading_day AS p2
  FROM dim_market_calendar c
  JOIN dim_market_calendar p ON p.market = 'KR' AND p.date = c.prev_trading_day
  JOIN dim_market_calendar q ON q.market = 'KR' AND q.date = p.prev_trading_day
 WHERE c.market = 'KR' AND c.date = (now() AT TIME ZONE 'Asia/Seoul')::date AND c.is_trading_day
\gset

BEGIN;
-- {p2}: 네 계좌 실측
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'p2'::date, account_id, instrument_id, quantity,
       cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
       fx_rate, :'p2'::date, (:'p2' || ' 15:30:00+09')::timestamptz, false, true
  FROM position_line
 WHERE as_of = '2026-07-27'
   AND account_id IN ('20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
                      '20000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000004');
-- {p1}: 세 계좌 실측, …0003 이월
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'p1'::date, account_id, instrument_id, quantity,
       cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
       fx_rate,
       CASE WHEN account_id = '20000000-0000-0000-0000-000000000003' THEN :'p2'::date ELSE :'p1'::date END,
       CASE WHEN account_id = '20000000-0000-0000-0000-000000000003'
            THEN (:'p2' || ' 15:30:00+09')::timestamptz ELSE (:'p1' || ' 15:30:00+09')::timestamptz END,
       account_id = '20000000-0000-0000-0000-000000000003', true
  FROM position_line
 WHERE as_of = '2026-07-27'
   AND account_id IN ('20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
                      '20000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000004');
-- {d}: 세 계좌 실측
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'d'::date, account_id, instrument_id, quantity,
       cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
       fx_rate, :'d'::date, (:'d' || ' 15:30:00+09')::timestamptz, false, true
  FROM position_line
 WHERE as_of = '2026-07-27'
   AND account_id IN ('20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
                      '20000000-0000-0000-0000-000000000004');
INSERT INTO collection_run (run_id, account_ref, requested_by, as_of, requested_at, state, finished_at, failure_reason)
SELECT gen_random_uuid(), account_ref, 'SCHEDULE', :'d'::date, now() - interval '2 minutes',
       'FAILED', now() - interval '1 minute', 'SOURCE_TIMEOUT'
  FROM account WHERE account_id = '20000000-0000-0000-0000-000000000003';
COMMIT;
```

**`F-N-JOIN` `yhr@a.com`에 `2026-07-27`부터 잔고가 있는 계좌 `…0096`을 두고, 오늘(KST) 다섯 계좌의 라인을 심는다** — `…0096`은 `07-27` SK하이닉스 10주(평가 1,800,000) + 예수금 1,000,000, 오늘 SK하이닉스 평가 2,000,000 + 예수금 1,000,000. `…0001` ~ `…0004`의 오늘 라인은 `07-27` 값을 그대로 옮긴다(이월 라인은 이월 그대로). 오늘이 KR 영업일이어야 한다. `R-LOCAL` 직후에 쓴다

```sql
SELECT c.date AS today FROM dim_market_calendar c
 WHERE c.market = 'KR' AND c.date = (now() AT TIME ZONE 'Asia/Seoul')::date AND c.is_trading_day
\gset

BEGIN;
INSERT INTO account (account_id, user_id, account_ref, broker, label, account_type, source,
                     credential_ref, link_state, linked_at)
SELECT '20000000-0000-0000-0000-000000000096', u.id, 'ar_np_join', '한국투자증권', 'NP 편입 계좌',
       'GENERAL', 'KIS', NULL, 'CONNECTED', now()
  FROM app_user u WHERE u.email = 'yhr@a.com';

INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final) VALUES
 ('2026-07-27', '20000000-0000-0000-0000-000000000096', '10000000-0000-0000-0000-000000000002', 10,
   1700000, 1800000, 1700000, 1800000, 1, '2026-07-27', '2026-07-27T15:30:00+09', false, false),
 ('2026-07-27', '20000000-0000-0000-0000-000000000096', '10000000-0000-0000-0000-000000000007', 1000000,
   1000000, 1000000, 1000000, 1000000, 1, '2026-07-27', '2026-07-27T15:30:00+09', false, false),
 (:'today', '20000000-0000-0000-0000-000000000096', '10000000-0000-0000-0000-000000000002', 10,
   1700000, 2000000, 1700000, 2000000, 1, :'today', (:'today' || ' 15:30:00+09')::timestamptz, false, false),
 (:'today', '20000000-0000-0000-0000-000000000096', '10000000-0000-0000-0000-000000000007', 1000000,
   1000000, 1000000, 1000000, 1000000, 1, :'today', (:'today' || ' 15:30:00+09')::timestamptz, false, false);

INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'today'::date, account_id, instrument_id, quantity,
       cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
       fx_rate, fx_as_of,
       CASE WHEN is_carried_forward THEN source_as_of ELSE (:'today' || ' 15:30:00+09')::timestamptz END,
       is_carried_forward, false
  FROM position_line
 WHERE as_of = '2026-07-27'
   AND account_id IN ('20000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002',
                      '20000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000004');
COMMIT;
```

**`F-N-BASIS-HHJ` `hhj@a.com`(`…0007`, `account_ref = ar_18d9b642`)의 체결 · 커버리지 · 확정 라인을 심는다** — 확정일 `2026-07-28`. `R-LOCAL` 직후에 쓴다. 끝나면 `F-N-BASIS-UNDO` → `R-LOCAL`

| 종목 | 체결(체결일) | `2026-07-28` 잔고 | 판정에 걸리는 것 |
|---|---|---|---|
| 삼성전자 | 매수 10@70,000 수수료 100(07-20) · 매도 4@75,000 수수료 100 세금 200(07-22) · 매수 1@71,000(07-29, 판정일 뒤) | 6주 · 매입 420,000 | 시작 수량 0 |
| SK하이닉스 | 07-15 잔고 10주 · 매입 1,500,000 → 매도 10@160,000 수수료 100 세금 300(07-21) → 매수 4@155,000 수수료 50(07-22) | 4주 · 매입 620,000 | 첫 구간 시작 수량 10 · 청산 |
| NAVER | 매수 10@200,000(07-20) · 매도 2@210,000(07-22) | 5주 · 매입 1,000,000 | 잔고 < 체결 |
| 애플 | 없음 | 5주(USD) | 해외 종목 |

체결 이력 `2026-07-15` ~ `2026-07-28`, `is_definitive = false`. 기업행위 커버리지는 삼성전자 · NAVER만 `COVERED`(2026 전체)다.

```sql
SET search_path = app, data;
BEGIN;
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final) VALUES
 ('2026-07-15','20000000-0000-0000-0000-000000000007','10000000-0000-0000-0000-000000000002',10,
   1500000,1500000,1500000,1500000,1,'2026-07-15','2026-07-15T15:30:00+09',false,true),
 ('2026-07-28','20000000-0000-0000-0000-000000000007','10000000-0000-0000-0000-000000000001',6,
   420000,450000,420000,450000,1,'2026-07-28','2026-07-28T15:30:00+09',false,true),
 ('2026-07-28','20000000-0000-0000-0000-000000000007','10000000-0000-0000-0000-000000000002',4,
   620000,640000,620000,640000,1,'2026-07-28','2026-07-28T15:30:00+09',false,true),
 ('2026-07-28','20000000-0000-0000-0000-000000000007','10000000-0000-0000-0000-000000000003',5,
   1000000,1050000,1000000,1050000,1,'2026-07-28','2026-07-28T15:30:00+09',false,true),
 ('2026-07-28','20000000-0000-0000-0000-000000000007','10000000-0000-0000-0000-000000000004',5,
   1000,1100,1400000,1540000,1400,'2026-07-28','2026-07-28T15:30:00+09',false,true),
 ('2026-07-28','20000000-0000-0000-0000-000000000007','10000000-0000-0000-0000-000000000007',460000,
   460000,460000,460000,460000,1,'2026-07-28','2026-07-28T15:30:00+09',false,true);

INSERT INTO cln_trade (trade_id, account_ref, instrument_id, isin, side, quantity, price, fee, tax,
                       currency, executed_at, trade_date) VALUES
 ('T-NP-H01','ar_18d9b642','10000000-0000-0000-0000-000000000001','KR7005930003','BUY',10,70000,100,0,'KRW','2026-07-20T10:00:00+09','2026-07-20'),
 ('T-NP-H02','ar_18d9b642','10000000-0000-0000-0000-000000000001','KR7005930003','SELL',4,75000,100,200,'KRW','2026-07-22T10:00:00+09','2026-07-22'),
 ('T-NP-H03','ar_18d9b642','10000000-0000-0000-0000-000000000002','KR7000660001','SELL',10,160000,100,300,'KRW','2026-07-21T10:00:00+09','2026-07-21'),
 ('T-NP-H04','ar_18d9b642','10000000-0000-0000-0000-000000000002','KR7000660001','BUY',4,155000,50,0,'KRW','2026-07-22T11:00:00+09','2026-07-22'),
 ('T-NP-H05','ar_18d9b642','10000000-0000-0000-0000-000000000003','KR7035420009','BUY',10,200000,0,0,'KRW','2026-07-20T11:00:00+09','2026-07-20'),
 ('T-NP-H06','ar_18d9b642','10000000-0000-0000-0000-000000000003','KR7035420009','SELL',2,210000,0,0,'KRW','2026-07-22T12:00:00+09','2026-07-22'),
 ('T-NP-H08','ar_18d9b642','10000000-0000-0000-0000-000000000001','KR7005930003','BUY',1,71000,0,0,'KRW','2026-07-29T09:30:00+09','2026-07-29');

INSERT INTO cln_trade_coverage (account_ref, covered_from, covered_to, is_definitive, empty_streak, computed_at)
VALUES ('ar_18d9b642','2026-07-15','2026-07-28',false,0,now());

INSERT INTO ca_coverage (market, instrument_id, covered_from, covered_to, state) VALUES
 ('KR','10000000-0000-0000-0000-000000000001','2026-01-01','2026-12-31','COVERED'),
 ('KR','10000000-0000-0000-0000-000000000003','2026-01-01','2026-12-31','COVERED')
ON CONFLICT (market, instrument_id) DO NOTHING;

INSERT INTO snapshot_run (as_of, finished_at) VALUES ('2026-07-28', now()) ON CONFLICT (as_of) DO NOTHING;
COMMIT;
```

**`F-N-BASIS-LATE-TRADE` 판정이 끝난 날짜 안에 체결 한 건을 더 넣는다** — 삼성전자 매수 1@71,000(07-23). `F-N-BASIS-HHJ`의 `07-28` 처리 기록이 생긴 뒤에 쓴다. 다음 확정일 전에 `F-N-BASIS-LATE-TRADE-UNDO`

```sql
INSERT INTO cln_trade (trade_id, account_ref, instrument_id, isin, side, quantity, price, fee, tax,
                       currency, executed_at, trade_date)
VALUES ('T-NP-H07','ar_18d9b642','10000000-0000-0000-0000-000000000001','KR7005930003','BUY',1,71000,0,0,
        'KRW','2026-07-23T10:00:00+09','2026-07-23');
```

**`F-N-BASIS-LATE-TRADE-UNDO`**

```sql
DELETE FROM cln_trade WHERE trade_id = 'T-NP-H07';
```

**`F-N-BASIS-HHJ-DAY2` `hhj@a.com`의 다음 확정일 `2026-07-29`를 같은 잔고로 만든다** — `07-28` 확정 라인을 그대로 옮기고, 판정일 뒤 체결 `T-NP-H08`을 지우고, 체결 이력을 `07-29`까지 늘리고, `snapshot_run`을 쓴다. `F-N-BASIS-HHJ`의 `07-28` 처리 기록이 생긴 뒤에 쓴다

```sql
BEGIN;
DELETE FROM cln_trade WHERE trade_id IN ('T-NP-H07', 'T-NP-H08');
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT '2026-07-29', account_id, instrument_id, quantity,
       cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
       fx_rate, '2026-07-29', '2026-07-29T15:30:00+09', false, true
  FROM position_line
 WHERE as_of = '2026-07-28' AND account_id = '20000000-0000-0000-0000-000000000007';
UPDATE cln_trade_coverage SET covered_to = '2026-07-29', computed_at = now() WHERE account_ref = 'ar_18d9b642';
INSERT INTO snapshot_run (as_of, finished_at) VALUES ('2026-07-29', now()) ON CONFLICT (as_of) DO NOTHING;
COMMIT;
```

**`F-N-BASIS-EMPTY` `test_empty@a.com`에 확정일 `2026-07-28`의 세 계좌를 둔다** — `F-C1-EMPTY-ACCOUNT` 뒤에 쓴다(`…0099`가 있어야 한다)

| 계좌 | `account_ref` | 체결 이력 | 체결 | `2026-07-28` 잔고 |
|---|---|---|---|---|
| `…0099` C1 빈 계좌 | `ar_c1_no_holdings` | 없음 | 없음 | 삼성전자 3주 · 매입 195,000 + 예수금 100,000 |
| `…0098` NP 입고 계좌 | `ar_np_definitive` | 07-15 ~ 07-28, `is_definitive = true` | 삼성전자 매도 2@70,000(07-22) | 삼성전자 8주 · 매입 520,000 + 예수금 140,000 |
| `…0097` NP 분할 계좌 | `ar_np_split` | 07-15 ~ 07-28, `is_definitive = false` | TIGER 미국나스닥100 매수 10@10,000(07-16) · 매도 5@6,000(07-21). 07-20에 2:1 분할 | TIGER 15주 · 매입 75,000 + 예수금 50,000 |

```sql
SET search_path = app, data;
BEGIN;
INSERT INTO account (account_id, user_id, account_ref, broker, label, account_type, source,
                     credential_ref, link_state, linked_at)
SELECT v.id, u.id, v.ref, '한국투자증권', v.label, 'GENERAL', 'KIS', NULL, 'CONNECTED', now()
  FROM app_user u
 CROSS JOIN (VALUES ('20000000-0000-0000-0000-000000000098'::uuid, 'ar_np_definitive', 'NP 입고 계좌'),
                    ('20000000-0000-0000-0000-000000000097'::uuid, 'ar_np_split', 'NP 분할 계좌')) AS v(id, ref, label)
 WHERE u.email = 'test_empty@a.com'
ON CONFLICT (account_id) DO NOTHING;

INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final) VALUES
 ('2026-07-28','20000000-0000-0000-0000-000000000099','10000000-0000-0000-0000-000000000001',3,
   195000,213000,195000,213000,1,'2026-07-28','2026-07-28T15:30:00+09',false,true),
 ('2026-07-28','20000000-0000-0000-0000-000000000099','10000000-0000-0000-0000-000000000007',100000,
   100000,100000,100000,100000,1,'2026-07-28','2026-07-28T15:30:00+09',false,true),
 ('2026-07-28','20000000-0000-0000-0000-000000000098','10000000-0000-0000-0000-000000000001',8,
   520000,568000,520000,568000,1,'2026-07-28','2026-07-28T15:30:00+09',false,true),
 ('2026-07-28','20000000-0000-0000-0000-000000000098','10000000-0000-0000-0000-000000000007',140000,
   140000,140000,140000,140000,1,'2026-07-28','2026-07-28T15:30:00+09',false,true),
 ('2026-07-28','20000000-0000-0000-0000-000000000097','10000000-0000-0000-0000-000000000006',15,
   75000,90000,75000,90000,1,'2026-07-28','2026-07-28T15:30:00+09',false,true),
 ('2026-07-28','20000000-0000-0000-0000-000000000097','10000000-0000-0000-0000-000000000007',50000,
   50000,50000,50000,50000,1,'2026-07-28','2026-07-28T15:30:00+09',false,true);

INSERT INTO cln_trade (trade_id, account_ref, instrument_id, isin, side, quantity, price, fee, tax,
                       currency, executed_at, trade_date) VALUES
 ('T-NP-B01','ar_np_definitive','10000000-0000-0000-0000-000000000001','KR7005930003','SELL',2,70000,0,0,'KRW','2026-07-22T10:00:00+09','2026-07-22'),
 ('T-NP-C01','ar_np_split','10000000-0000-0000-0000-000000000006','KR7133690008','BUY',10,10000,0,0,'KRW','2026-07-16T10:00:00+09','2026-07-16'),
 ('T-NP-C02','ar_np_split','10000000-0000-0000-0000-000000000006','KR7133690008','SELL',5,6000,0,0,'KRW','2026-07-21T10:00:00+09','2026-07-21');

INSERT INTO cln_trade_coverage (account_ref, covered_from, covered_to, is_definitive, empty_streak, computed_at) VALUES
 ('ar_np_definitive','2026-07-15','2026-07-28',true,0,now()),
 ('ar_np_split','2026-07-15','2026-07-28',false,0,now());

INSERT INTO corporate_action (instrument_id, type, ratio, ex_date)
VALUES ('10000000-0000-0000-0000-000000000006','SPLIT',2,'2026-07-20');

INSERT INTO ca_coverage (market, instrument_id, covered_from, covered_to, state) VALUES
 ('KR','10000000-0000-0000-0000-000000000001','2026-01-01','2026-12-31','COVERED'),
 ('KR','10000000-0000-0000-0000-000000000006','2026-01-01','2026-12-31','COVERED')
ON CONFLICT (market, instrument_id) DO NOTHING;

INSERT INTO snapshot_run (as_of, finished_at) VALUES ('2026-07-28', now()) ON CONFLICT (as_of) DO NOTHING;
COMMIT;
```

**`F-N-BASIS-UNDO` 등급 판정용으로 심은 데이터 표의 행을 지운다** — 샘플 파일이 비우지 않는 표(`cln_trade` · `cln_trade_coverage` · `corporate_action` · `ca_coverage` · `snapshot_run`)를 되돌린다. 그 뒤 `R-LOCAL`

```sql
SET search_path = app, data;
BEGIN;
DELETE FROM cln_trade WHERE trade_id LIKE 'T-NP-%';
DELETE FROM cln_trade_coverage WHERE account_ref IN ('ar_18d9b642', 'ar_np_definitive', 'ar_np_split');
DELETE FROM corporate_action WHERE instrument_id = '10000000-0000-0000-0000-000000000006' AND ex_date = '2026-07-20';
DELETE FROM ca_coverage WHERE instrument_id IN ('10000000-0000-0000-0000-000000000001',
                                                '10000000-0000-0000-0000-000000000003',
                                                '10000000-0000-0000-0000-000000000006')
   AND covered_from = '2026-01-01' AND covered_to = '2026-12-31';
DELETE FROM snapshot_run WHERE as_of IN ('2026-07-28', '2026-07-29');
COMMIT;
```

**`F-N-REALIZED-USD` `yhr@a.com`의 `…0001`에 애플 매도 체결 한 건을 넣는다** — 2026-06-10, 5주, 매도 $1,050(매도일 환율 1,370) · 원가 $1,000(매입일 환율 1,350) · 비용 $1

```sql
INSERT INTO realized_pnl_line (trade_id, account_id, instrument_id, sold_at, quantity,
    sell_amount_local, cost_basis_local, sell_amount_krw, cost_basis_krw,
    fee_tax, realized_pnl_local, realized_pnl_krw, grade,
    evaluated_as_of, position_closed, ca_unknown, seed_reason, coverage_start_at)
VALUES ('T-NP-U01', '20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000004',
        '2026-06-10T23:00:00+09', 5, 1050, 1000, 1438500, 1350000, 1, 49, 87130, 'VERIFIED',
        DATE '2026-06-10', true, false, NULL, NULL);
```

**`F-N-ETF-UNAVAILABLE` TIGER 미국나스닥100의 구성종목 커버리지를 `UNAVAILABLE`로**

```sql
INSERT INTO etf_coverage (etf_instrument_id, state, as_of)
VALUES ('10000000-0000-0000-0000-000000000006', 'UNAVAILABLE', '2026-07-27')
ON CONFLICT (etf_instrument_id) DO UPDATE SET state = 'UNAVAILABLE', as_of = EXCLUDED.as_of;
```

**판정 질의**

**`Q-N-USER-ID` 사용자 id**

```sql
SELECT id FROM app_user WHERE email = :'email';
```

**`Q-N-FX-LINES` 그날 사용자 라인의 환율과 이월 여부**

```sql
SELECT pl.account_id, i.symbol, pl.quantity, pl.market_value_local, pl.market_value_krw,
       pl.fx_rate, pl.fx_as_of, pl.is_carried_forward, pl.is_final
  FROM position_line pl JOIN account a USING (account_id) JOIN app_user u ON u.id = a.user_id
  JOIN instrument i ON i.instrument_id = pl.instrument_id
 WHERE u.email = :'email' AND pl.as_of = :'as_of'
 ORDER BY pl.account_id, i.symbol;
```

**`Q-N-CALENDAR-PF` KR 캘린더 한 날**

```sql
SELECT date, is_trading_day, prev_trading_day, next_trading_day FROM dim_market_calendar
 WHERE market = 'KR' AND date = :'date';
```

**`Q-N-BASIS` 사용자 계좌의 평단 상태**

```sql
SELECT pb.account_id, i.symbol, pb.evaluated_as_of, pb.evaluated_qty, pb.opening_qty,
       pb.avg_cost_local, pb.avg_cost_krw, pb.seed_avg_price, pb.coverage_start_at,
       pb.grade, pb.seed_permanent, pb.ca_unknown
  FROM position_basis pb JOIN account a USING (account_id) JOIN app_user u ON u.id = a.user_id
  JOIN instrument i ON i.instrument_id = pb.instrument_id
 WHERE u.email = :'email'
 ORDER BY pb.account_id, i.symbol;
```

**`Q-N-BASIS-BUILD` 사용자 계좌의 평단 처리 기록**

```sql
SELECT bb.account_id, bb.as_of, bb.outcome, bb.reason
  FROM basis_build bb JOIN account a USING (account_id) JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email'
 ORDER BY bb.account_id, bb.as_of;
```

**`Q-N-REALIZED` 사용자 계좌의 실현손익 행과 산출 근거**

```sql
SELECT r.trade_id, r.account_id, i.symbol, (r.sold_at AT TIME ZONE 'Asia/Seoul')::date AS sold_on,
       r.quantity, r.sell_amount_krw, r.cost_basis_krw, r.fee_tax, r.realized_pnl_krw, r.grade,
       r.seed_reason, r.coverage_start_at, r.evaluated_as_of, r.position_closed, r.ca_unknown
  FROM realized_pnl_line r JOIN account a ON a.account_id = r.account_id
  JOIN app_user u ON u.id = a.user_id
  JOIN instrument i ON i.instrument_id = r.instrument_id
 WHERE u.email = :'email'
 ORDER BY r.sold_at, r.trade_id;
```

**`Q-N-LINE-INVARIANTS` 보유 라인 팩트 정합성 위반 건수** — `연계`에서 읽기 전용으로 돈다. 사용자 값은 고르지 않고 건수만 고른다. 모든 열이 0이어야 한다

```sql
WITH kr AS (SELECT date, is_trading_day FROM dim_market_calendar WHERE market = 'KR'),
     user_days AS (SELECT DISTINCT a.user_id, pl.as_of
                     FROM position_line pl JOIN account a USING (account_id)),
     user_prev AS (SELECT user_id, as_of, lag(as_of) OVER (PARTITION BY user_id ORDER BY as_of) AS prev_as_of
                     FROM user_days)
SELECT
  (SELECT count(*) FROM (SELECT 1 FROM position_line GROUP BY as_of, account_id, instrument_id HAVING count(*) > 1) g)
      AS duplicated_grain,
  (SELECT count(*) FROM position_line WHERE fx_rate IS NULL OR fx_as_of IS NULL) AS missing_fx,
  (SELECT count(*) FROM position_line
    WHERE is_carried_forward AND (source_as_of AT TIME ZONE 'Asia/Seoul')::date >= as_of) AS carried_not_stale,
  (SELECT count(*) FROM position_line pl LEFT JOIN kr ON kr.date = pl.as_of
    WHERE kr.date IS NULL OR NOT kr.is_trading_day) AS non_trading_as_of,
  (SELECT count(*) FROM position_line pl JOIN instrument i USING (instrument_id)
    WHERE i.asset_class = 'CASH' AND pl.cost_amount_krw <> pl.market_value_krw) AS cash_cost_mismatch,
  (SELECT count(*) FROM position_line pl LEFT JOIN instrument i USING (instrument_id)
    WHERE i.instrument_id IS NULL) AS unmatched_instrument,
  (SELECT count(*) FROM user_prev up
     JOIN account a ON a.user_id = up.user_id AND a.link_state <> 'DISCONNECTED'
    WHERE up.prev_as_of IS NOT NULL
      AND EXISTS (SELECT 1 FROM position_line x WHERE x.account_id = a.account_id AND x.as_of = up.prev_as_of)
      AND NOT EXISTS (SELECT 1 FROM position_line y WHERE y.account_id = a.account_id AND y.as_of = up.as_of))
      AS missing_line;
```

### 7.10 시나리오 밖 케이스 — 알림

시각 값(`at`)은 `2026-10-29T10:20:00+09:00` 꼴, 날짜 값(`d`)은 `2026-09-28` 꼴로 넘긴다(실행 부록 §7.8과 같다).

**`F-N-STALE-HASH` 평가 상태의 해시를 지금 코드의 컴파일 결과와 다른 값으로** — 템플릿 로직 · 업캐스팅이 바뀐 배포 직후를 흉내 낸다(알림 §6.6)

```sql
UPDATE alert_state SET spec_hash = 'it-stale' WHERE alert_id = :'alert';
```

**`F-N-OLD-FIRE` 알림의 발화 기록 시각을 이틀 앞으로** — 데이터 시점(`as_of`)은 그대로 둔다

```sql
UPDATE alert_event SET fired_at = fired_at - interval '2 day' WHERE alert_id = :'alert';
```

**`F-N-FLOW` 종목의 그날 수급 한 행** — 완료 신호는 따로 넣는다(`F-AL6-DAILY-RUN`의 `kind=DAILY_FLOW`)

```sql
INSERT INTO investor_flow_daily (instrument_id, date, foreign_net_buy_krw, institution_net_buy_krw)
VALUES (:'instrument', :'d', :'foreign', :'institution');
```

**`F-N-BAR` 종목의 그날 일봉을 값을 정해 한 행** — `F-AL6-BAR`의 고가 · 저가(±500)가 맞지 않는 종목(미국 등)에 쓴다

```sql
INSERT INTO adjusted_price_daily (instrument_id, date, open, high, low, close, volume, adj_factor)
VALUES (:'instrument', :'d', :'close', :'high', :'low', :'close', :'volume', 1);
```

**`F-N-ADJUST-HISTORY` 그날 이전의 봉을 보정 계열로 다시 쓴다** — `factor`는 행위 뒤 가격 ÷ 행위 전 가격(2:1 분할이면 `0.5`). 데이터가 보정된 계열을 준 뒤를 흉내 낸다(알림 §7.3)

```sql
UPDATE adjusted_price_daily
   SET open = open * :'factor', high = high * :'factor', low = low * :'factor', close = close * :'factor',
       volume = volume / :'factor', adj_factor = :'factor'
 WHERE instrument_id = :'instrument' AND date < :'d';
```

**`F-N-DAILY-RUN-AT` 일별 완료 신호를 시각을 정해 한 행** — 캘린더 행이 없는 날에 쓴다

```sql
INSERT INTO market_data_run (market, kind, as_of, state, finished_at)
VALUES (:'market', :'kind', :'at', 'DONE', now());
```

**`F-N-HOLIDAY` 그날을 휴장일로 바꾸고 앞뒤 날의 연결을 다시 잇는다**

```sql
UPDATE dim_market_calendar SET is_trading_day = false, open_at = NULL, close_at = NULL
 WHERE market = :'market' AND date = :'d';
UPDATE dim_market_calendar c
   SET prev_trading_day = (SELECT max(x.date) FROM dim_market_calendar x
                            WHERE x.market = c.market AND x.date < c.date AND x.is_trading_day),
       next_trading_day = (SELECT min(x.date) FROM dim_market_calendar x
                            WHERE x.market = c.market AND x.date > c.date AND x.is_trading_day)
 WHERE c.market = :'market' AND c.date BETWEEN :'d'::date - 7 AND :'d'::date + 7;
```

**`F-N-EARLY-CLOSE` 국내 그날을 13:00 조기 폐장으로**

```sql
UPDATE dim_market_calendar SET close_at = (:'d'::date + time '13:00') AT TIME ZONE 'Asia/Seoul'
 WHERE market = 'KR' AND date = :'d';
```

**`F-N-OPEN-AT` 그날의 개장 시각을 바꾼다** — 개장 지연일을 만들 때와 되돌릴 때 쓴다

```sql
UPDATE dim_market_calendar SET open_at = :'at' WHERE market = :'market' AND date = :'d';
```

**`F-N-DROP-CALENDAR` 캘린더 행을 지운다** — 캘린더가 빈 날을 만든다

```sql
DELETE FROM dim_market_calendar WHERE market = :'market' AND date BETWEEN :'from' AND :'to';
```

**`F-N-DROP-INSTRUMENT-AL` 종목 마스터에서 한 종목을 지운다** — 포트폴리오 라인이 없는 종목에만 쓴다

```sql
DELETE FROM instrument WHERE instrument_id = :'instrument';
```

**`F-N-DELIST` 종목을 상장폐지로**

```sql
UPDATE instrument SET delisted_on = :'d' WHERE instrument_id = :'instrument';
```

**`F-N-COPY-LINES` 사용자의 `from` 라인을 `as_of`로 그대로 옮겨 적는다** — 확정 라인으로 쓴다. `F-X1-SELL-ALL`에서 뺀 종목을 다시 산 날을 만든다. `as_of`는 KR 영업일이어야 한다

```sql
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT :'as_of'::date, pl.account_id, pl.instrument_id, pl.quantity,
       pl.cost_amount_local, pl.market_value_local, pl.cost_amount_krw, pl.market_value_krw,
       pl.fx_rate, pl.fx_as_of,
       CASE WHEN pl.is_carried_forward THEN pl.source_as_of
            ELSE (:'as_of'::date + time '15:30') AT TIME ZONE 'Asia/Seoul' END,
       pl.is_carried_forward, true
  FROM position_line pl JOIN account a USING (account_id) JOIN app_user u ON u.id = a.user_id
 WHERE u.email = :'email' AND pl.as_of = :'from'
ON CONFLICT (as_of, account_id, instrument_id) DO NOTHING;
```

**`Q-N-HASH` 알림의 평가 상태와 해시가 주입한 값인지**

```sql
SELECT a.status, s.last_result, s.last_known_result, s.unknown_reason,
       s.spec_hash = 'it-stale' AS hash_is_stale, s.version,
       to_char(s.evaluated_as_of AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') AS evaluated_as_of_kst
  FROM alert a JOIN alert_state s USING (alert_id)
 WHERE a.alert_id = :'alert';
```

**`Q-N-PREV-DAY` 그 시장의 오늘(현지 날짜) 행과 직전 거래일** — `zone`은 `Asia/Seoul` · `America/New_York`

```sql
SELECT date, is_trading_day, prev_trading_day,
       to_char(open_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') AS open_kst,
       to_char(close_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') AS close_kst
  FROM dim_market_calendar
 WHERE market = :'market' AND date = (now() AT TIME ZONE :'zone')::date;
```

**`Q-N-CALENDAR-AL` 그 시장의 날짜 범위 캘린더**

```sql
SELECT date, is_trading_day, prev_trading_day, next_trading_day,
       to_char(open_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') AS open_kst,
       to_char(close_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM-DD HH24:MI') AS close_kst
  FROM dim_market_calendar
 WHERE market = :'market' AND date BETWEEN :'from' AND :'to' ORDER BY date;
```

**`Q-N-CASH` 예수금 의사종목**

```sql
SELECT instrument_id, symbol, name FROM instrument WHERE asset_class = 'CASH' ORDER BY symbol;
```

**`Q-N-ALERT-OWNER` 알림 하나의 주인 · 상태 · 버전** — 남의 요청이 바꾸지 못했는지 볼 때 쓴다

```sql
SELECT a.alert_id, u.email AS owner, a.status, a.deleted_at, a.trigger_spec, s.version
  FROM alert a JOIN alert_state s USING (alert_id) JOIN app_user u ON u.id = a.user_id
 WHERE a.alert_id = :'alert';
```

## 8. 실행 시점

| 값 | 뜻 |
|---|---|
| 언제든 | 시각 제약이 없다 |
| 확정 전 | 화 · 수 · 목 23:00 전, 또는 금요일. 다음 픽업이 그날 확정 마감 전이라 이미 확정으로 판정되지 않는다(동기화 설계 §2.1 · §5.3) |
| 화 · 수 · 목 23:00 전 | 요청한 그날 밤 수집된다 |
| 다음 수집 뒤 | 요청 뒤 첫 일 · 화 · 수 · 목 23:00 수집과 반영이 끝난 뒤. 수집은 데이터 쪽이 돌고, 반영은 생성기가 1분마다 집는다 |
| 월요일 | 다음 픽업이 그날 확정 마감(화 08:00) 뒤라 이미 확정으로 판정된다 |
| 비영업일 | 토 · 일 · 휴장일 |
| 영업일 | KR 영업일 아무 때 |
| KR 영업일 08:00 뒤(그날 안) | 직전 KR 영업일의 확정 마감(다음 KR 영업일 08:00)이 지났고 오늘의 마감은 오지 않았다. 생성기 확정 단계가 직전 영업일 하루만 확정하고 오늘에서 멈춘다(생성기 설계 §6.2) |
| 국내 장중 | 평일 09:10 ~ 15:30 KST |
| 국내 장 시간 밖 | 평일 15:30 ~ 다음 날 09:00 KST, 또는 토 · 일 |
| 클러스터 가동 시간 안 | 3주 계획의 클러스터 가동 시간 |
| 미국 장중 | 미국 정규장 시간. 한국 시각 22:30 ~ 다음 날 05:00(미국 서머타임 기간), 서머타임이 끝난 뒤(2026-11-01부터)는 23:30 ~ 다음 날 06:00. 미국 현지 날짜가 평일이어야 한다 |

케이스는 이 값에 괄호로 시각 제약을 덧붙이거나(`언제든(KST 00:10 이후)`), 선행 케이스와의 관계(`PF11-01과 같은 날`)로 적는다.
