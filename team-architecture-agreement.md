# 전반적인 아키텍처 및 기능/기술스택 합의

> 작성일: 2026-07-04, 2026-07-05 갱신(피드백·데이터원천 보강) · 참여: 유희라 · 황해정(해정) · 전대홍
> 상태: **정리 중** — 1장(기능)은 팀 공통 초안, 2장(아키텍처)은 인원별 파트를 각자 채운다. 이 갱신에서는 **2.2 황해정(인프라)** 파트를 확정했고, 나머지는 각자 갱신 전까지 플레이스홀더로 둔다.
> 관련: [hhj/architecture.md](./hhj/architecture.md) · [hhj/tech-stack.md](./hhj/tech-stack.md) · [hhj/infrastructure.md](./hhj/infrastructure.md) · [hhj/service.md](./hhj/service.md) · [hhj/alert.md](./hhj/alert.md) · [yhr 1차 기능명세](./yhr/specs/2026-06-28-feature-spec-and-tech-review.md) · [jdh 계좌통합(CODEF 흐름 참고)](./jdh/features/01-account-consolidation.md)

---

## 0. 피드백 요약 (2026-07-05)

이번 갱신 전 초안 상태 기준으로, **비어 있던 항목 / 실현 가능성이 불확실했던 항목**을 정리하고 이번에 새로 확인한 내용으로 메웠다.

| 위치 | 초안 상태 | 이번에 확인·보강한 내용 |
|---|---|---|
| §1.1.1 요구사항 | 비어 있음 | 하단에 채움(계좌 통합 목적·CODEF 위탁 원칙·비동기 배치 전제) |
| §1.1.2 벤치마크 비교 차트 | 데이터 원천 미기재 | **FinanceDataReader(MIT, 무료)**가 KOSPI(`KS11`)·S&P500(`S&P500`) 시계열을 동일 인터페이스로 제공 — 신규 벤더 없이 해결 가능 |
| §2.1.2 지표/연산자 | 비어 있음 | 하단에 채움(7종 연산자는 팀이 이미 참고한 open-trading-api 컨벤션과 통일) |
| §2.1.2 "ETF 종목까지 묶어 합산 수급" | 데이터 원천 미정으로 보류 표시 | **부분 해결**: 종목별 외국인/기관 순매수 자체는 **KIS OpenAPI에 이미 TR 존재**(`종목별 외국인 기관 추정가집계`, `종목별 외국계 순매수추이`, `국내기관_외국인 매매종목가집계` — 국내주식 시세분석 카테고리, 종목코드 기준 일별). 신규 벤더 불필요, **기존 KIS 앱키로 바로 조회 가능**. 단 "ETF 합산"은 여전히 **국내 ETF 구성종목 확보**(이미 차단 확정, [ETF 조사](./yhr/research/etf-constituent-sources.md))에 걸려 있어, 그 문제가 풀려야 완성됨 — **새 블로커가 아니라 기존에 알려진 블로커에 종속**된다는 점이 이번에 명확해짐 |
| §2.1.3 기술 스택 | 비어 있음 | 하단에 채움([hhj/architecture.md](./hhj/architecture.md) 그대로 연결) |
| §3.1, §3.3 (유희라/전대홍) | 비어 있음 | 임의로 채우지 않음 — 각자 작성 전까지 참고 링크만 표시 |
| 섹션 번호 | "2. 매수/매도 타이밍 알림"과 "2. 아키텍처"가 같은 번호로 중복 | 이 문서에서는 "3. 아키텍처"로 정정(내용 변경 아님, 표기만) |

**남은 팀 결정 사항** (기술 조사로는 못 푸는 것들):
1. CODEF 정식 전환 시점·비용 — §3.2 참고, 팀 합의 필요.
2. 국내 ETF 구성종목 확보 방법(A 헤드리스/B 운용사파일/C 벤더, [ETF 조사](./yhr/research/etf-constituent-sources.md) §4) 확정 — 안 풀리면 §2.1.2의 "ETF 합산 수급"과 §1.1의 국내 ETF look-through 둘 다 보류 상태 유지.
3. PER/PBR 데이터 원천 확정 — 아직 이 문서에 명시 안 됨(§1.1.2에 항목은 있으나 원천 미기재, 추가 조사 필요).

---

## 1. 통합 계좌 관리 (기능)

### 1.1.1. 요구사항

- 여러 증권사(국내 KIS + 비KIS 기관)에 흩어진 보유 자산을 하나로 모아 조회한다.
- 계좌 정보(인증서/비밀번호 등)는 서비스가 직접 저장하지 않고, 스크래핑 대행 사업자(CODEF)에게 위탁한다.
- 통합 결과는 종목·섹터·시장·통화 기준으로 비중과 손익을 계산해 보여준다(항목은 1.1.2).
- 동기화는 무겁고 느릴 수 있음을 전제로 **비동기 배치**로 처리한다(실시간 아님).

### 1.1.2. 항목

- 종목명 / 종목분야 / 보유 수량 / 평균 매입 단가 / 현재가 / 평가손익 / 수익률
- 포트폴리오 총 평가금액
- 누적 수익률 / 일간 수익률
- 벤치마크 비교 차트 (동일 시작일 기준 수익률 곡선)
- 섹터별 비중 / 종목 수 / 평가금액
- 종목별 현재 PER / PBR
- 동일 섹터 내 PER / PBR 분위수

### 1.1.3. 기술 스택

**수집 방법 — CODEF(마이데이터·스크래핑 대행 API)로 여러 기관 잔고 통합**

| 항목 | 내용 | 확인 근거 |
|---|---|---|
| 개인 개발자 이용 | 홈페이지 가입 후 **데모 신청**(일 최대 100회, 3개월 무료) → 정식 전환. 개인 사이드 프로젝트 규모로 시작 가능 | codef.io, developer.codef.io (2026-07-04 확인) |
| 인증정보 처리 | CODEF 발급 **RSA 공개키**로 인증서/비밀번호를 클라이언트에서 암호화해 전송 → 서비스는 **Connected ID만 저장**, 원본 인증정보는 저장하지 않음 | developer.codef.io RSA 가이드, [jdh 계좌통합 흐름](./jdh/features/01-account-consolidation.md) 2~4단계와 동일 패턴 채택 |
| 토큰 | 1회 발급 토큰은 **1주일 재사용** 가능 | developer.codef.io |
| 증권사 지원 범위 | 증권사 **전계좌/종합자산/잔고조회/입출금내역** API 제공 → KIS가 커버하지 못하는 타 증권사 계좌를 CODEF로 보완 | developer.codef.io/products/stock |
| 안정성 | 스크래핑 기반이라 **느리고 실패 가능** → 재시도·부분 실패 허용 전제로 배치 설계(§2.2 아키텍처 참고) | jdh 계좌통합 문서 "핵심 주의점" |
| KIS와의 역할 분담 | **KIS(본인 위탁계좌)**: 잔고+실시간 시세(무료, 이미 실측 완료) / **CODEF**: KIS가 커버 못하는 타 증권사 잔고(스크래핑, 유료 전환 가능성 있음) — 사용자가 KIS만 쓰면 CODEF 없이도 이 기능은 부분 동작 | 팀 결정 |
| **벤치마크 비교 차트 데이터 원천(신규)** | **FinanceDataReader**(Python, MIT 라이선스, 무료) — `fdr.DataReader('KS11')`(KOSPI)·`fdr.DataReader('S&P500')`를 동일 인터페이스로 제공. 신규 벤더 계약·인증 불필요 | GitHub FinanceData/FinanceDataReader (2026-07-05 확인) |

---

## 2. 매수/매도 타이밍 알림 (기능)

### 2.1.1. 요구사항

- 사용자가 매수/매도 알림 조건을 직접 정의한다.
  - 세부 방법: 빈 캔버스가 아니라 **목적 → 프리셋 선택 → (적용 범위 + 기준값)** 3단계 가이드형으로 구성(자유 조합 빌더는 1차에서 숨김) — [yhr 스펙 §2.4](./yhr/specs/2026-06-28-feature-spec-and-tech-review.md) 채택
- 등락률 기준(±5%)은 사용자별로 조정 가능하도록 파라미터화
- 사용자 설정 목표가 이상 도달 시
- 당일 누적 거래량이 20일 평균 대비 3배 이상일 때
- 5일 이동평균선이 20일 이동평균선을 상향 돌파(골든크로스) 또는 하향 이탈(데드크로스) 시
- RSI 30 이하 진입(과매도) / RSI 70 이상 진입(과매수) 시
- 외국인·기관 수급 기반 알림
  - 외국인 순매도 / 순매수 전환 알림
  - 기관 순매도 / 순매수 전환 알림
  - 며칠 연속으로 빼고 있는지(연속 순매도 일수) 추적
  - **ETF 종목까지 묶어서** 합산 수급 알림

### 2.1.2. 항목

**지표** (일봉 기준 자체 계산 — [hhj/architecture.md §4](./hhj/architecture.md#4-실시간-vs-배치-판정-기준-alertmd-52-계승)의 배치 판정과 동일 원칙)

| 구분 | 지표 |
|---|---|
| 가격/이벤트(실시간) | 목표가 도달, 전일 종가 대비 등락률(±X%), 거래량 급증(틱 집계) |
| 기술지표(배치, EOD) | MA5/MA20(골든·데드크로스), RSI(14일), 이격도, 20일 평균거래량 |
| 수급(배치, EOD) | 외국인 순매수/매도, 기관 순매수/매도, 연속 순매수·순매도 일수, **ETF 구성종목 가중합산 수급**(아래 참고) |

**연산자** (7종, [yhr 조사](./yhr/research/claude-stock-tools.md) — open-trading-api strategy_builder 컨벤션 채택)

`cross_above` · `cross_below` · `greater_than` · `less_than` · `greater_equal` · `less_equal` · `equals`

> **ETF 합산 수급의 데이터 요구사항 — 2026-07-05 갱신**: 기존 ETF look-through(§ETF 조사)는 **가격·평가금액·섹터 비중** 기준으로만 설계돼 있었다. "ETF 종목까지 묶어서 합산 수급"은 **종목별 수급(외국인/기관 순매수) × ETF 구성비중**을 합산해야 한다.
> - **종목별 수급 데이터**: ✅ 확인됨 — **KIS OpenAPI에 이미 TR 존재**(국내주식 시세분석 카테고리: `종목별 외국인 기관 추정가집계`, `종목별 외국계 순매수추이`, `국내기관_외국인 매매종목가집계`. 종목코드 파라미터, 일별 배치). 팀이 이미 쓰는 KIS 앱키로 바로 조회 가능 — **신규 벤더 불필요**.
> - **ETF 구성비중**: 여전히 **국내 ETF 구성종목 확보 문제**(KRX JS 봇 차단 + 약관상 사설 라이브러리 금지, [ETF 조사](./yhr/research/etf-constituent-sources.md) §4)에 종속. 이 항목 자체가 새로 막힌 게 아니라 **기존에 이미 알려진 블로커 하나에 묶여 있을 뿐**이라는 게 이번에 명확해짐.
> - **참고**: "외국인/기관 순매수"는 KRX(한국 시장) 고유 개념이라 미국 ETF에는 이 알림 개념 자체가 잘 맞지 않음 — 사실상 **국내 ETF 한정 기능**으로 범위를 좁히는 게 자연스럽다.

### 2.1.3. 기술 스택

- 실시간(가격/급락/거래량급증): raw WebSocket 수집 → Redis Streams 슬라이딩 윈도우 집계 → 즉시 RuleState 평가
- 배치(기술지표·수급, EOD 1회): APScheduler 잡 → `cln_*` 정제 → `mart_stock_signal_daily` 등 집계 → RuleState 평가
- 알림 발송: FCM 푸시(1차), 카카오 알림톡은 사업자등록 필요로 보류
- 상세: [hhj/architecture.md](./hhj/architecture.md), [hhj/tech-stack.md](./hhj/tech-stack.md)

---

## 3. 아키텍처 (인원별)

### 3.1. 유희라

> _(작성 예정 — 백엔드 도메인 모델·API·정합성 계산은 [yhr 1차 기능명세](./yhr/specs/2026-06-28-feature-spec-and-tech-review.md) §4~6 참고. 이번 갱신에서 CODEF 도입이 도메인 모델(§4.1 `Account.source`)에 영향을 주므로 반영 필요.)_

### 3.2. 황해정 (인프라)

**전체 그림**: 애플리케이션 계층(FastAPI·수집기·Postgres·Redis)은 [hhj/architecture.md](./hhj/architecture.md)에 정리된 그대로 유지한다. 이번 문서(§1)에서 확정된 **CODEF 도입**을 반영해 배치 수집 계층에 한 갈래를 추가한다.

**1) CODEF 반영에 따른 아키텍처 변경점**

```
[KIS OpenAPI]                    [CODEF API]
  REST(잔고·시세·체결내역)          POST /account/create → Connected ID
  WebSocket(실시간 체결가/호가)      POST /account/{connectedId}/... (잔고·전계좌·입출금내역)
        │                               │
        ▼                               ▼
┌─────────────────────────────────────────────────────────┐
│ 수집(Collector)                                           │
│  · KIS WS 수집기(상시, asyncio) — 기존과 동일               │
│  · KIS REST 폴링 — 기존과 동일                             │
│  · CODEF 배치 잡(신규) — APScheduler 트리거, 비동기·재시도    │
│    - 인증정보는 CODEF RSA 공개키로 암호화해 전송(서버 미저장)  │
│    - 응답 원본은 raw_codef_* (Bronze 성격) 테이블에 append   │
│    - 실패/추가인증 요구는 별도 상태로 저장 후 알림(§운영)      │
└─────────────────────────────────────────────────────────┘
        │
        ▼  cln_* 정제(계좌·기관 응답 정규화) → mart_* 집계(ISIN 합산 포트폴리오)
```

- CODEF는 **스크래핑 기반이라 느리고 실패 가능** → KIS REST(초당 20건, 준안정)와 신뢰도가 다르므로 **같은 배치 파이프라인 안에서도 재시도 정책을 분리**한다(CODEF는 지수 백오프 + 부분 실패 허용, KIS는 레이트리밋 스로틀 중심).
- 인증정보 비저장 원칙은 KIS(본인 앱키·토큰)와 CODEF(Connected ID) 모두 동일하게 적용 — 시크릿 관리는 `.env`+파일권한 수준 유지(팀·계정 규모상 KMS 등은 과설계, [tech-stack.md](./hhj/tech-stack.md) §1 동일 결론).
- CODEF 응답 스키마(기관별로 상이)를 다루는 정규화 로직은 데이터 담당(전대홍) 영역이다. **정정(2026-09-27)**: 이 항목 작성 시점엔 "별도 데이터 레이크 도입은 하지 않는다"고 봤으나, 이후 팀 논의로 뒤집혔다 — S3 Iceberg 기반 레이크(Bronze `raw_codef_*`/`raw_kis_*` → Silver `cln_*` → Gold `mart_*`)를 실제로 구축했고, CODEF·KIS 원본은 Postgres가 아니라 이 레이크의 Bronze 계층에 append된다. 백엔드가 쓰는 건 그중 일부를 Postgres `data` 스키마로 리버스ETL한 결과뿐이다 — 상세는 §3.3.

**2) 배포 인프라 (기존 유지)**

EC2 + kubeadm 자체 구축 클러스터(master×3 + worker×2 + storage×1, AWS NLB로 control-plane HA) — 상세는 [hhj/infrastructure.md](./hhj/infrastructure.md). CODEF 배치 잡은 worker 노드의 APScheduler 컨테이너에 잡 하나가 추가되는 정도라 **노드 구성 변경 없음**.

**3) 이번 기능 반영에 따른 열린 질문**

1. ETF 합산 수급(§2.1.2): 종목별 수급 데이터는 KIS TR로 해결됐으나, **국내 ETF 구성종목 확보**가 안 풀리면 여전히 동작 불가 — 그 확보 방법(§0 남은 팀 결정 사항 #2)이 확정되기 전까지 이 알림 항목은 Phase 1.5 유지를 제안.
2. CODEF 정식 전환 시 요금제(데모 100회/일·3개월 이후) — 팀 규모에서 비용이 얼마나 늘지 견적 필요.
3. CODEF 재인증(2단계 인증 만료 등) 발생 시 사용자에게 알리는 채널도 결국 FCM 1차 채널을 공유 — 큐 우선순위(가격 알림 vs 재인증 요청)를 구분할지 여부.

### 3.3. 전대홍

**전체 그림**: 레이크는 Bronze(`raw_*`, 원천 응답 그대로) → Silver(`cln_*`, 정제·정규화) → Gold(`mart_*`, 집계) 3계층(S3 + Apache Iceberg)이고, 백엔드는 이 중 일부를 Postgres `data` 스키마로 리버스ETL 받은 것만 읽는다 — `raw_*`와 `mart_portfolio_daily`/`mart_allocation_daily`/`mart_asset_change_monthly`(user_id 포함) 등은 레이크 전용이라 백엔드가 직접 접근하지 않는다. 인프라는 §3.2와 같은 kubeadm 클러스터 안에서 ArgoCD(GitOps)로 관리한다 — 매니페스트는 `stock-project-crew/argocd` 저장소, 파이프라인 코드는 `stock-project-crew/dataeng`.

**1) 파이프라인 우선순위 — 화면이 실데이터로 도는 순서부터**

화면 6개가 지금 백엔드 샘플 데이터로 돌아가고 있어서, 계좌 수집·종목 마스터·환율처럼 화면에 직결되는 파이프라인이 최우선이고, 시세·알림·백테스트(원래 1차 설계에서 먼저 만들었던 것)는 후순위로 재배열했다.

| # | 파이프라인 | 수집할 데이터 | 소스/API | 상태 |
|---|---|---|---|---|
| 1 | 계좌 수집 | 잔고·체결·배당·예수금 | KIS Open API / CODEF API | KIS 부분 구현, CODEF 미구현 |
| 2 | 종목 마스터 | KRX 상장목록, 미국 종목·섹터 | FinanceDataReader + yfinance + Naver WICS | 미착수 |
| 3 | 환율 | 날짜별 원화 환산 환율 | 한국수출입은행 API / KIS | 미착수(스키마만 있음) |
| 4 | ETF 구성종목 | ETF별 구성종목·비중 | SPDR(미국) + KRX/pykrx(국내, 약관 미정) | 미착수 |
| 5 | 기업행위 | 액면분할·유상증자·합병 | DART Open API | 미착수, 소스 확정 필요 |
| 6 | 거래일 캘린더 | KRX/NYSE 휴장일 | KRX/NYSE | 미착수 |
| 7 | CDC 소비 | `account`/`position_line`/`realized_pnl_line`/`manual_cashflow` 변경 이벤트 | portfolio-db → Debezium → Kafka | 배선만 있음, 소비 잡 없음 |
| 8 | 시세 | 일봉 OHLCV, 현재가·52주 고저 | KIS 기간별시세·현재가조회 API | Bronze/Silver/Gold 있음(알림·백테스트 전용, 서비스 미사용) |
| 9 | 알림·백테스트·뉴스 | 실시간 체결틱, 조정종가, 뉴스 | KIS WebSocket / Naver·RSS / LLM API | 전부 후순위 |

1~3번(카탈로그 정비 포함)이 끝나야 서비스가 처음으로 실데이터로 돈다. 표 배경과 컬럼 단위 스키마는 데이터팀 Notion "🗂️ 필요 데이터 재정리" 문서 참고.

**2) 기술 스택 요약**
- 저장: S3 + Apache Iceberg — 카탈로그는 지금 SQLite-on-S3(Glue 권한 없어 임시)라 동시 실행 시 충돌 위험이 있어 Postgres JDBC 카탈로그로 전환 예정
- 배치: Airflow(KubernetesPodOperator, 검증 완료) + Python/pyiceberg(소량 파이프라인) + Spark 3.5.9 standalone(대량 재계산·백테스트)
- 스트리밍: Debezium(Postgres CDC, `wal_level=logical`) → Kafka(Strimzi) — Flink 소비 잡은 아직 0개
- 조회: Trino — 카탈로그 미설정
- 리버스ETL: 소스 파이프라인별로 Iceberg → Postgres `data` 스키마 upsert, 일 1회. 백엔드는 이 스키마에 읽기 권한만(§4.2 순환 금지와 일치)

**3) 남은 열린 질문**

1. **국내 ETF 구성종목 확보 방법** — §0 남은 팀 결정 사항 #2, 여전히 미해결. pykrx는 약관 문제로 국내 소스 확정을 못 했다([ETF 조사](./yhr/research/etf-constituent-sources.md) 참고).
2. **`collection_run` 쓰기 권한 분리** — 백엔드는 `REQUESTED` 행 INSERT만, 데이터팀 워커는 상태 전이 UPDATE만 하는 방식을 제안 중.
3. **`fx_rate.rate_type`** — 평가·원가·실현손익에 타입을 나눌지 단일화할지 팀 확인 필요.
4. **ETF 펼치는 깊이·순환 처리 규칙** — 실제 SPDR 데이터를 받아본 뒤 정할 사안.

나머지 열린 질문과 근거는 데이터팀 리뷰 문서([2026-08-30 OLAP 스키마 검토](./yhr/reviews/2026-08-30-data-team-olap-schema-review.md)) §5, 데이터팀 Notion "🗂️ 필요 데이터 재정리" 참고.
