# 포트폴리오 계좌 파이프라인 — 데이터 요구사항 대비 실측

- **일자**: 2026-10-15
- **대상**: 데이터 담당 — 계좌 수집(①)·`collection_run` 워커·리버스 ETL
- **기준**: [데이터 요구사항](../specs/data-requirements.md) §2.2 · §6.1 · §6.4~6.10 / [포트폴리오 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) §3.6 · §7.7 · §9.1
- **실측 대상**: `dataeng` `origin/main` `323ea1e` · `airflow-dags` `main` `60cbdff` · S3 레이크 `stock-project-bronze-394686422456/warehouse/` 목록과 Iceberg 메타데이터·매니페스트(2026-10-15) · 운영 앱 DB(`portfolio-db`, 읽기 전용, 2026-10-14)
- **범위**: 요구와 실제의 차이, 그 차이가 막는 화면, 요청. 코드·데이터·스펙은 고치지 않았다

---

## 0. 한 장 요약

**포트폴리오 화면을 실데이터로 채우는 경로가 처음부터 끝까지 한 번도 돈 적이 없다.** 백엔드의 보유 스냅샷 생성(스펙 §3.6 1단계)이 읽을 `cln_balance`·`cln_deposit`이 앱 DB에도, 레이크에도 없다.

| # | 차이 | 막는 것 | 요청 |
|---|---|---|---|
| **G1** | `cln_*` 6개가 `data` 스키마에 DDL도 리버스 ETL도 없다 | 요약·종목별·비중 분석·계좌별·자산 변화 — 실데이터 전부 | **최우선.** `cln_balance`·`cln_deposit`부터 |
| **G2** | 레이크에도 `cln_*`와 계좌 Bronze(`raw_kis_balance` 등)가 없다 — 계좌 수집이 레이크에 쓴 적이 없다 | G1과 같다 | 수집이 실제로 도는지 확인 |
| **G3** | `cln_*`의 `instrument_id`를 채우는 코드가 없다(항상 null) | 백엔드가 보유 라인의 종목을 정할 수 없다 | 종목 마스터 매핑 |
| **G4** | `collection_run` 워커가 실제 DB 행의 `as_of`(`datetime.date`)에 pendulum 메서드를 부른다 | 모든 계좌가 `FAILED`로 끝날 것으로 보인다(코드 판독, 미실행) | 확인·수정 |
| **G5** | `silver_synced_at`이 리버스 ETL 뒤가 아니라 Silver 정제 뒤에, 정제가 실패해도 찍힌다 | 백엔드가 "반영 완료"로 믿고 빈 입력으로 스냅샷을 만든다 | 의미를 §6.10대로 |
| **G6** | EOD 스케줄이 KR 영업일이 아니라 요일 고정(일·화·수·목)이고 `as_of`가 KST 오늘이다 | 월·금 스냅샷이 매주 이월되고 일요일 `as_of` 행이 생긴다 | 영업일 캘린더 기준 |
| G7 | `cln_trade`의 `fee`·`tax`가 항상 null, `trade_date` 없음, 체결 커버리지에 `is_definitive` 없음 | 실현손익·등급 판정(스펙 §3.6 1.5·1.6단계) | 다음 순위 |
| G8 | `etf_constituent`가 `data`에 없고, 구성종목 57.1%가 `underlying_instrument_id` null | 구성종목 기준 보기(LOOK_THROUGH) | 다음 순위 |

통합·운영테스트([3주 계획](../plan/2026-10-11-integration-and-operation-test-plan.md))에 실데이터로 들어가려면 **G1~G6이 10/21(수)까지** 풀려야 한다. 그 뒤면 포트폴리오 운영 관찰은 시드로 덮고 범위 제외로 기록한다.

---

## 1. 놓인 곳 — `data` 스키마 · 리버스 ETL · 레이크

요구 §2.2: 백엔드는 레이크를 읽지 않으며, `cln_*`·`cln_*_coverage`·`etf_constituent`는 리버스 ETL로 `data` 스키마에 와야 한다.

| 테이블 | `data` DDL (`reverse_etl/ddl.py`) | 리버스 ETL (`reverse_etl/push.py`) | 레이크 Silver (S3) | 운영 앱 DB |
|---|---|---|---|---|
| `cln_balance` | 없음 | 없음 | **없음** | 없음 |
| `cln_deposit` | 없음 | 없음 | **없음** | 없음 |
| `cln_trade` | 없음 | 없음 | **없음** | 없음 |
| `cln_cashflow` | 없음 | 없음 | **없음** | 없음 |
| `cln_trade_coverage` · `cln_cashflow_coverage` | 없음 | 없음 | **없음** | 없음 |
| `etf_constituent` | 없음 | 없음 | 있음 — 89,130행 | 없음 |
| `fx_rate` | 있음 | 있음 | 있음 — 6,732행 | 306행(2025-07-14 ~ 2026-10-14, `BASE`만) |
| `collection_run` | 있음 | 해당 없음(직접 적재) | 해당 없음 | 0행 |

- `ddl.py`가 만드는 표는 11개다: `dim_market_calendar` · `fx_rate` · `adjusted_price_daily` · `investor_flow_daily` · `intraday_quote` · `market_data_run` · `instrument` · `etf_coverage` · `corporate_action` · `ca_coverage` · `collection_run`. 운영 `data` 스키마의 표 목록과 같다.
- 레이크 `warehouse/silver/`의 표는 `ca_coverage` · `cln_daily_price` · `cln_us_daily_price` · `corporate_action` · `dim_account` · `dim_instrument` · `dim_market_calendar` · `etf_constituent` · `etf_coverage` · `fx_rate` · `investor_flow_daily`다. `warehouse/bronze_api/`에도 `raw_kis_balance` · `raw_kis_ccld` · `raw_kis_rights` · `raw_codef_*`가 없다. 네임스페이스 위치는 `{WAREHOUSE}/{ns}`(`lib/lake.py`)이며 그 기본 위치를 열람한 결과다.

### `dim_account`와 운영 계좌가 다르다

`collection_run`의 EOD 행 생성(`create_eod_requests`)과 증권사 판별은 `silver.dim_account`를 읽는다. 그 표의 최신 스냅샷은 **2026-10-08, 7행, `link_state` 전부 `CONNECTED`, `source` ∈ {`KIS`, `CODEF`}**인데, 운영 `app.account`는 **0행**이다(2026-10-14). Bronze `snap_account`는 2026-10-14까지 쌓였지만 Silver는 10/08 이후 갱신되지 않았다. 지금 EOD를 켜면 운영에 없는 계좌 7개에 행을 만든다. 10/08 스냅샷이 어느 DB를 읽은 것인지는 확인하지 못했다.

---

## 2. 테이블별 — 레이크 Silver 정의 대비 요구

레이크에 행이 없으므로 아래는 **코드가 정의한 스키마**(`silver/cln_account.py` · `silver/refine_cln_kis.py` · `silver/refine_cln_codef.py`)와 요구의 비교다.

### 2.1 `cln_balance` (§6.5)

| 요구 | 정의 | 근거 |
|---|---|---|
| PK `(account_ref, instrument_id, source_as_of)` | 키 `(account_ref, source_as_of, item_code, balance_type)` | `cln_account.py` `KEYS` |
| `instrument_id` uuid NOT NULL | string, KIS·CODEF 둘 다 항상 `None`. 매핑 코드 없음 | `refine_cln_kis.py:85` · README "미룬 것" |
| `avg_price` decimal(20,4) | decimal(20,6) | `cln_account.py` `schemas()` |
| `quantity`·`avg_price`·`market_value` NOT NULL | nullable | 같은 곳 |
| `ingest_id` | 없음. `_ingest_ts`가 있다 | 같은 곳 |
| `currency` `KRW`·`USD` | KIS는 `KRW` 고정. 국내 잔고 TR(`TTTC8434R`)만 부른다 | `refine_cln_kis.py:92` · `lib/kis.py` `TR` |

같은 `(account_ref, instrument_id)`에 `balance_type`이 다른 행이 둘 이상 나오면 백엔드는 무엇을 합칠지 알 수 없다. `balance_type`의 값 목록과 합산 규칙을 정해 달라.

**미국 종목 잔고는 수집하지 않는다.** KIS 해외 잔고 TR을 부르지 않아, 보유 미국 종목·USD 예수금이 있어도 스냅샷에 들어오지 않는다. 화면의 환율 표기·미국 가격 기준일·통화 병기 분기가 열리지 않는다.

### 2.2 `cln_deposit` (§6.6)

컬럼은 요구와 맞는다. 다르다: `amount` nullable, KIS·CODEF 모두 `KRW`만 만든다(KIS는 D+2 예수금 `prvs_rcdl_excc_amt`, CODEF 외화 예수금은 필드 미확인이라 읽지 않음 — `refine_cln_codef.py` 상단).

### 2.3 `cln_trade` (§6.7)

| 요구 | 정의 | 근거 |
|---|---|---|
| `trade_id` = `{account_ref}:{주문일}:{주문번호}` | 일치 | `refine_cln_kis.py:120` |
| `fee`·`tax` NOT NULL | **항상 `None`** — 체결 TR에 없다 | `refine_cln_kis.py:130-131` |
| `executed_at` 체결 시각 | 주문일 + 주문 시각(`ord_dt`·`ord_tmd`) | `refine_cln_kis.py:133` |
| `trade_date` date NOT NULL | 컬럼 없음 | `cln_account.py` `schemas()` |
| `instrument_id` NOT NULL | 항상 `None` | `refine_cln_kis.py:124` |
| `price` decimal(20,4) | decimal(20,6) | `schemas()` |
| `currency` | `KRW` 고정 — 국내 체결 TR만 | `refine_cln_kis.py:132` |

CODEF는 체결 상품이 없어 `cln_trade`를 만들지 않는다(요구가 예상한 것).

`fee`·`tax`가 비면 백엔드는 매수 수수료를 취득원가에 넣지 못하고(스펙 §4.3) 매도 비용을 빼지 못한다. 실현손익이 체계적으로 부풀려진다.

### 2.4 `cln_cashflow` (§6.8)

| 요구 | 정의 | 근거 |
|---|---|---|
| PK `cashflow_id` | 복합키 `(account_ref, tr_key)` | `KEYS` |
| `instrument_id` (nullable) | 컬럼 없음 | `schemas()` |
| `type` `DIVIDEND`·`FEE`·`TAX` | KIS는 `DIVIDEND`만(권리유형 03·32), CODEF는 적요 키워드로 셋 | `refine_cln_kis.py:155-170` · `refine_cln_codef.py` `CASHFLOW_RULES` |
| 매매대금·입출금 배제 | CODEF는 적요 키워드 방식. 실데이터로 검증되지 않았다(README "데모 실계좌로 확정할 것") | dataeng README |

`tr_key`는 KIS `rights:{종목}:{기준일}:{권리유형}`, CODEF `일시:입금:출금:거래후잔액`이다. 백엔드는 `(account_ref, tr_key)`를 키로 받아도 된다 — 재수집에 같은 값이면 충분하다. CODEF 키가 그 조건을 지키는지(같은 일시·금액의 거래 두 건) 확인해 달라.

### 2.5 커버리지 (§6.9)

| 요구 | 정의 |
|---|---|
| `cln_trade_coverage` 계좌 1행 · `is_definitive` · `empty_streak` · `computed_at` | 조회 창(90일)마다 1행 `(account_ref, covered_from, covered_to)`. 세 컬럼 없음, 계산 코드 없음 |
| `cln_cashflow_coverage` 계좌×유형 1행 · `state` · `computed_at` | 기간 행 `(account_ref, type, covered_from, covered_to)`. `state` 없음 — 행이 있으면 확보. `DEPOSIT`·`WITHDRAW` 행은 만들지 않는다 |

창 단위 행은 백엔드가 계좌별로 접을 수 있다(최소 `covered_from` ~ 최대 `covered_to`, 사이에 빈 구간이 없을 때). `is_definitive`는 접어서 만들 수 없다 — "계좌 최초 체결일에 닿았는가"는 수집기만 안다. 없으면 영구 `추정` 판정(§6.9 마지막 문단)이 서지 않는다.

### 2.6 `etf_constituent` (§6.1)

레이크 실측(Iceberg 메타데이터 `00026-…`, 매니페스트 통계): 컬럼 `as_of` · `etf_instrument_id` · `etf_symbol` · `underlying_instrument_id` · `underlying_symbol` · `underlying_name` · `weight decimal(9,6)` · `source` · `_ingest_ts`. **89,130행 중 `underlying_instrument_id` null 50,851행(57.1%).**

| 요구 | 실제 |
|---|---|
| 범위: "현재 원천은 미국(SPDR)뿐" | 국내(KRX)만. 미국은 미착수 |
| PK에 `underlying_instrument_id` | 키 `(as_of, etf_instrument_id, underlying_symbol)` |
| 미매칭 구성종목은 행을 만들지 않는다 | null로 남긴다 |
| 평탄화·깊이 제한·순환 차단 | 구현돼 있다(`silver/etf_constituent.py`) |

국내만인 것은 요구 문서 쪽이 실제를 따라가지 못한 것이다. 리버스 ETL 때 null 행을 거르면 요구와 맞는다(그 몫은 `기타` 버킷이 된다).

### 2.7 `fx_rate` (§6.4)

`data` 표는 요구와 컬럼·PK·CHECK가 같다. 리버스 ETL은 레이크의 `KEB_BASE`를 `BASE`로 바꿔 `USD/KRW`만 보낸다(`push.py`). 과거 범위는 2025-07-14부터라, 체결 실측에 쓴 위탁계좌의 최초 체결일 2025-10-16([KIS 실측](../verification/kis-portfolio-assumptions.md) §1)을 덮는다. `market_data_daily` DAG가 일·화·수·목에만 돌아 "KR 영업일 1회"를 채우지 않지만, 백엔드는 직전 행으로 폴백하므로(§5.3) 막히지는 않는다.

---

## 3. `collection_run` 계약 (§6.10)

DDL은 요구 10개 컬럼·CHECK와 **정확히 일치**한다. 차이는 동작에 있다.

| 항목 | 요구 | 실제 | 근거 |
|---|---|---|---|
| 픽업 | `credential_ref`가 채워진 `REQUESTED` | `REQUESTED` 전부를 `RUNNING`으로. `credential_ref` 조건 없음 → 비어 있으면 즉시 `FAILED("credential_ref 없음")` | `lib/collection_run.py` `pick_up_requested` · `run_collection.py:80-81` |
| EOD `as_of` | KR 영업일 | `pendulum.today("Asia/Seoul")` — 캘린더를 보지 않는다 | `run_collection.py` `main` |
| EOD 주기 | KR 영업일마다 | `0 23 * * 0,2,3,4` KST(일·화·수·목) | `airflow-dags` `collection_run_daily.py:78` |
| `silver_synced_at` | `cln_*`가 `data`에 반영된 시각 | Silver 정제 뒤 `DONE`이고 비어 있는 **모든** 행에 `now()`. 정제가 실패해도 찍힌다(`trigger_rule="all_done"`). `refine_cln_codef`는 DAG에 없는데 CODEF 행에도 찍힌다 | `collection_run.py` `mark_synced` · `collection_run_daily.py:103-119` |
| `failure_reason` | 코드(`SCRAPE_TIMEOUT` 등) | 자유 문자열(`"credential_ref 없음"`, `"UNKNOWN_BROKER: …"`, `"{예외타입}: {메시지}"`) | `run_collection.py:79,81,117` |
| `REAUTH_REQUIRED` | KIS·CODEF | CODEF만 낸다 | `collect_kis_account.py` |
| 재시도 | — | 하지 않는다. 백엔드가 새 행을 만든다 | `run_collection.py` 상단 |

**`as_of` 타입 (G4).** `collect_one`이 `run["as_of"].subtract(days=…)`·`.format(…)`를 부른다(`run_collection.py:88-99`). `run["as_of"]`는 `pick_up_requested`가 DB에서 읽은 값이고, `lib/appdb.py`에는 pendulum 타입 어댑터가 없다. 그러면 psycopg 기본값인 `datetime.date`가 들어와 `subtract`가 없다. 테스트는 `pendulum.date`를 직접 넣어 이 경로를 지나지 않는다(`tests/test_run_collection.py:17`). 실제 DB 행으로 돌린 기록이 없어(`collection_run` 0행) 실행으로는 확인하지 못했다.

**`DAG` 상태.** `collection_run_daily`는 `is_paused_upon_creation=True`다. 이유는 EOD 행의 `credential_ref`를 백엔드가 채우는 시점이 맞춰지지 않아서다(DAG docstring). Airflow의 실제 일시정지 여부와 실행 이력은 확인하지 못했다.

---

## 4. 요청

순서가 곧 우선순위다. 앞의 여섯이 테스트 창(10/21)에 걸린다.

1. **`cln_balance`·`cln_deposit` → `data` (G1·G2).** `ddl.py`에 표를 더하고 `push.py`로 보낸다. 컬럼은 §6.5·§6.6. 그 전에 KIS 위탁계좌 1개로 수집 → Silver가 레이크에 실제로 쓰이는지 확인해 달라.
2. **`instrument_id` 매핑 (G3).** `item_code`(+시장) → `instrument.instrument_id`. 매칭 안 된 행을 어떻게 내보낼지(행 제외 또는 null + 별도 표기)도 정해 달라 — 백엔드는 null 행을 "종목 미매칭"으로 다룬다.
3. **`collection_run` `as_of` 타입 (G4).** 실제 DB 행으로 `collect_one`을 한 번 돌려 확인.
4. **`silver_synced_at` (G5).** `data` 반영(리버스 ETL 커밋) 뒤에, 그 실행의 계좌 행에만 찍는다. 정제·반영이 실패한 실행에는 찍지 않는다.
5. **EOD를 KR 영업일로 (G6).** 스케줄 또는 `create_eod_requests`가 `dim_market_calendar` KR `is_trading_day`를 보게. `dim_account` 갱신이 멈춘 것(§1)도 함께.
6. **픽업 조건.** `credential_ref IS NOT NULL`인 `REQUESTED`만 집는다. 백엔드는 EOD 행에 `credential_ref`를 채우는 잡을 둔다(아래 §5) — 그 사이 행이 `FAILED`로 끝나지 않게.
7. `cln_trade` `fee`·`tax`·`trade_date`, `cln_trade_coverage.is_definitive` (G7).
8. `etf_constituent` → `data`, 미매칭 행 제외 (G8).
9. `cln_cashflow`·커버리지 → `data`. `failure_reason` 코드화. KIS 해외 잔고.

## 5. 백엔드가 하는 것

- `account` 등록 시 `account_ref`를 발급하고, 자격증명을 SSM SecureString에 쓰고, 그 파라미터 이름을 `credential_ref`로 둔다(스펙 §7.1). 워커가 `ssm:GetParameter`로 읽는 방식(`run_collection.py` `_load_credential_ref`)에 맞춘다.
- 수동 새로고침 행(`USER`)은 `credential_ref`를 채워 넣는다. EOD 행(`SCHEDULE`)은 생성 직후 백엔드 잡이 채운다.
- 보유 스냅샷 생성은 계좌별로 그날 최종 `collection_run`이 `DONE`이고 `silver_synced_at`이 있을 때 진행하고, 아니면 이월한다(§6.10 · 스펙 §7.3).

## 6. 확인하지 못한 것

| 항목 | 이유 |
|---|---|
| 운영 `data`·`app` 행 수의 오늘 값 | 2026-10-14 읽기 전용 조회 이후 클러스터 터널이 닫혀 있다 |
| `dataeng_*` 역할과 `data` 스키마 권한 | 같은 이유 |
| Glue 카탈로그의 현재 메타데이터 포인터 | `glue:GetTables` 권한 없음. S3의 가장 높은 번호 `metadata.json`을 현재로 봤다 |
| SSM 파라미터 목록 | `ssm:DescribeParameters` 권한 없음. 값은 조회하지 않았다 |
| Airflow DAG의 실제 일시정지 여부·실행 이력 | 클러스터 접근 불가 |
| `dim_account` 10/08 스냅샷의 출처 | Bronze payload를 읽을 도구(pyarrow)가 로컬에 없다 |
| IRP(29) 계좌의 잔고 수집 | 지금 TR(`TTTC8434R`)로 되는지 실측 기록이 없다. 연금 전용 TR은 코드에 없다. IRP의 기간 체결내역은 `APBK1744`로 막힌다([KIS 실시간 실측](../verification/kis-realtime-and-pykis.md) §1-3) |
