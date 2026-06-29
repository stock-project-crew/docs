# KIS 실시간(WebSocket) & python-kis 검증 결과

> 작성일: 2026-06-29 · 대상: 한국투자증권 OpenAPI 실시간 시세, python-kis(Soju06) 2.1.6
> 검증 방식: 공식 저장소 `koreainvestment/open-trading-api` 소스 + python-kis 실설치/introspection.
> 실시간 틱·잔고 **수치** 검증은 사용자 키로 동봉 스크립트(`kis_ws/kr_quote.py`, `pykis/balance_quote.py`) 실행 필요(장중).
> 보안: App Key/Secret/HTS ID/계좌는 **환경변수로만**. 코드·로그·repo 노출 금지. 샘플은 마스킹.

---

## 0. 검증 상태 요약

| 항목 | 상태 | 근거 |
|---|---|---|
| 국내 실시간 체결/호가 TR·필드 | ✅ **라이브 틱 실측** | 14:50 장중 3종목 수신(§1-5-1) |
| 세션당 등록 한도 | ✅ **확정**: IRP=3 / 위탁=41 / 모의=41 | IRP(29) 계좌만 서버측 캡(§1-3) |
| 다중 세션으로 30~50종목 커버 | ✅ 구조 확인 | approval_key·appkey 다중화 |
| 급락/거래량급증용 필드 | ✅ **라이브 실측** | 035720 +9.35% 등 실변동 포착(§1-5-1) |
| 미국 실시간 무료 여부 | ✅ 소스 확인 / ⚠️틱 미수신 | 0분지연, tr_key=`DNASAAPL`; 틱 실측은 미국장중(§1-6) |
| python-kis 설치/임포트 | ✅ 실설치 2.1.6 | venv 검증 |
| python-kis 실시간 캡 동작 | ✅ **실측**: IRP도 3건서 OPSP0008 | 조용한 실패+REST오버헤드 발견(§2-3-1) |
| python-kis 통합 잔고 필드 | ✅ **실계좌 실측** | raw API와 수치 일치(§2-2-1) |
| python-kis 원화환산/환율 | ✅ 필드 존재 / ⚠️USD 미실증 | KRW 보유만 있어 환율=1 |
| python-kis 국내/해외 판별 | ⚠️ quirk 발견 | `domestic`/`foreign` 오분류 → `currency` 사용 |
| python-kis 실시간 콜백 | ✅ **라이브 실측 27틱** | change_rate/volume/intensity 수신(§2-3-1) |
| python-kis 복구형 웹소켓 | ✅ 문서 명시 | README "완벽히 복구" |

---

## [1] KIS 실시간(WebSocket)

### 1-1. 접속 / 인증

| 구분 | 값 |
|---|---|
| 실전 WS | `ws://ops.koreainvestment.com:21000` |
| 모의 WS | `ws://ops.koreainvestment.com:31000` |
| 승인키 발급 | `POST {REST도메인}/oauth2/Approval` |
| 발급 body | `{"grant_type":"client_credentials","appkey":..,"secretkey":..}` → `approval_key` |

- REST 접근토큰과 **별개**로 WS는 `approval_key`를 사용. (body 필드명이 `secretkey`인 점 주의 — REST 토큰의 `appsecret`과 다름)
- 구독 메시지 구조:
  ```json
  {"header":{"approval_key":"<KEY>","custtype":"P","tr_type":"1","content-type":"utf-8"},
   "body":{"input":{"tr_id":"H0STCNT0","tr_key":"005930"}}}
  ```
  `tr_type` 1=등록(subscribe), 2=해지(unsubscribe).

### 1-2. 국내주식 실시간 TR (소스 확인)

| 용도 | TR ID | 비고 |
|---|---|---|
| 실시간체결가(KRX) | `H0STCNT0` | 급락/거래량 감지의 핵심 |
| 실시간호가(KRX) | `H0STASP0` | 1~10호가 |
| 실시간체결가(통합 KRX+NXT) | `H0UNCNT0` | 통합시세 |
| 실시간호가(통합) | `H0UNASP0` | |
| 실시간예상체결 | `H0STANC0` | 장 시작/마감 동시호가 |
| 실시간체결통보 | `H0STCNI0` (모의 `H0STCNI9`) | 내 주문 체결, 암호화 |

> 웹소켓 TR은 실전/모의 **동일 ID** 사용(체결통보만 모의가 `H0STCNI9`).

### 1-3. 세션당 등록 한도(문서상 41) — 실측 방법

- 문서상 **1 WebSocket 세션당 실시간 등록 41건**. `kis_ws/kr_quote.py`가 50종목을 순차 등록하며 실패 지점을 찾아 실측한다.

> **실측 결과(2026-06-29, 실계좌 주말) — 재현성 100%**:
> - 체결(H0STCNT0): 3건 성공 후 4번째에서 `rt_cd=1 / OPSP0008 / "MAX SUBSCRIBE OVER"`.
> - 호가(H0STASP0): **동일하게 3건**에서 동일 에러.
> - **매 실행 새 approval_key**를 발급받는데도 항상 정확히 3 → 일시적 쿼터 잔여가 아니라 **구조적 한도**.
> - 앱 종료·대기 후에도 동일 → 외부 세션 점유설(아래 3·4순위) 배제.
>
> **→ 확정된 한도 구조: TR 종류 무관 "세션(approval_key)당 총 3건"** (체결+호가 합산 총량형, 분리 아님). 문서상 41과 큰 차이.
>
> **남은 원인 후보(진단 중)** — 3·4순위(외부 세션 점유 / 일시 정책)는 재현성으로 배제:
> 1. **앱/계정의 실시간 시세 엔타이틀먼트가 낮음**: 신규 앱 기본 실시간 건수가 소량이고 KIS Developers에서 별도 *실시간 사용/건수 신청* 후 41로 확대되는 구조일 가능성.
> 2. **퇴직연금(DC/IRP) 계좌 제한**: 이 계좌는 이미 매수가능·체결내역이 `APBK1744`로 막힘 → 실시간 등록 한도도 축소됐을 개연성.
>
> **결정적 진단**: KIS Developers에서 **앱(App Key)을 하나 더 생성해 동일 테스트**.
> - 새 앱키도 3 → 계정(퇴직연금) 레벨 제한(후보 2) 확정.
> - 새 앱키는 41 → 첫 앱키의 엔타이틀먼트/신청 문제(후보 1) 확정.
> 병행: 포털에서 OPSP0008 정의·실시간 건수 정책·연금계좌 실시간 제한 공식 근거 확인.
>
> **운영 함의(현 상태 기준)**: 이 앱키로는 동시 **3종목**(체결 또는 호가)만 실시간 가능 → 30~50종목 모니터링은 **다중 앱키 세션 필수**(앱키당 3건이면 산술적으로 10~17개 앱키 필요). 한도 확대(신청/계좌변경) 가능 여부가 설계의 핵심 변수.

#### 1-3-1. 포털 공식 조사 결과 (2026-06-29)

KIS Developers 포털 FAQ·오류코드 기준 공식 사실:

| 항목 | 공식 내용 | 근거 |
|---|---|---|
| 실시간 한도 | **1 appkey당 1세션, 최대 41건** | FAQ "WebSocket 실시간시세 특정 종목 수신 안됨" / "코스피 전종목 실시간" |
| 한도 단위 | **App Key(계좌·앱) 기준** (approval_key 아님) | FAQ "다계좌 이용 시 유량 측정" |
| OPSP0008 | "MAX SUBSCRIBE OVER" = **41 초과 시** 발생 | 오류코드 표 + 위 FAQ |
| 신청/단계 확대 구조 | **없음** (소량→승인→41 같은 구조 미존재, 41이 곧 기본) | 근거 없음 확인 |
| 연금계좌 실시간 축소 | **공식 언급 없음** | 근거 없음 확인 |
| 계좌종류별 권한 | **IRP(29)=주문불가·조회/시세만 / DC(55)=API불가 / 위탁(01)·연금저축(22)=전부 가능** | FAQ "이용 가능 상품계좌종류" |

→ **가설 1(엔타이틀먼트/신청 후 확대) 반증**: 공식적으로 그런 단계 구조는 없고 41이 기본.
→ **본 계좌 = 상품코드 29 = IRP**. 주문계열 차단(`APBK1744`)은 IRP 권한으로 정확히 설명됨. 단 **IRP도 시세조회는 허용**이라 실시간 3건 캡은 공식 문서로 설명 안 됨.
→ **남은 결론**: "이 IRP appkey에 서버측 비공개 3건 캡"이 사실상 유일하게 남은 설명(공식 근거는 없음, 가설 영역).

**최종 분리 테스트(실행 완료, 2026-06-29)**: 모의투자 appkey로 동일 `kis_ws/kr_quote.py` 실행 →
**42번째에서 OPSP0008, 직전까지 41건 성공**. 즉 모의(위탁형 가상계좌)=공식대로 41, 실전 IRP=3.
→ **결론 확정: 3건 캡은 코드/세션/프로토콜 문제가 아니라 실전 IRP(29) 계좌·appkey에 걸린 KIS 서버측 제한.**
공식 문서엔 IRP 실시간 축소 명시가 없으나, 모의=41 / IRP=3 실측 대비로 원인이 계좌측임이 명확.

| 환경 | appkey | 실시간 등록 한도(실측) |
|---|---|---|
| 실전 | IRP(29) 계좌 | **3건** |
| 실전 | **위탁(01) 계좌** | **41건**(공식과 일치) |
| 모의투자 | 가상(위탁형) 계좌 | **41건**(공식과 일치) |

→ **실전 위탁(01)=41 직접 실측 완료** → "IRP만 3건 캡, 일반 계좌는 정상 41" 최종 확정(추론 잔여 0).

**근거 URL**:
- WebSocket 한도/MAX SUBSCRIBE OVER: `apiportal.koreainvestment.com/community/.../post/ba132252-2a48-456c-a76e-3c135dae4e35`
- 다계좌 유량 단위: `.../post/bcfb94ee-5aa3-4915-bca6-d63378c620c2`
- 이용 가능 계좌종류(IRP/DC/위탁): `.../post/0b29069f-812b-4a70-94db-63d07d5ad54c`
- 오류코드: `apiportal.koreainvestment.com/faq-error-code`
- ⚠️ **중요 카운트 규칙**: 등록 1건 = `tr_id`+`tr_key` 1쌍. **체결가와 호가를 동시에 보면 종목당 2건** 소모 → 41건이면 **체결+호가 동시 구독 시 약 20종목**이 한계.
- 1 `approval_key`(= 1 appkey)당 동시 WebSocket 세션은 사실상 1개로 운용됨.

### 1-4. 다중 세션/계좌로 30~50종목 커버

- 단일 세션(41건)으로 **체결가만** 구독하면 ~41종목 가능. **체결+호가**면 ~20종목.
- 30~50종목 + 체결·호가 동시 = 한도 초과 → **appkey(앱)를 복수 발급**해 각각 approval_key로 별도 세션을 띄워 분산하는 구조가 필요.
  - 같은 계좌라도 KIS Developers에서 앱을 여러 개 만들면 appkey가 분리됨. 종목을 N개 세션에 샤딩.
  - python-kis는 내부적으로 단일 KIS 세션을 쓰므로, 대량 구독은 **raw WebSocket 다중 세션 직접 구현**이 유리.

### 1-5. 급락·거래량급증 신호 생성 (✅ 라이브 틱 실측)

H0STCNT0(실시간체결가) 응답 컬럼(파이프·캐럿 구분, 소스 확인):

| 인덱스 | 필드 | 의미 | 용도 |
|---|---|---|---|
| 0 | `MKSC_SHRN_ISCD` | 종목코드 | 키 |
| 1 | `STCK_CNTG_HOUR` | 체결시각(HHMMSS) | 시간윈도우 |
| 2 | `STCK_PRPR` | 현재가(체결가) | **급락 계산** |
| 5 | `PRDY_CTRT` | 전일대비율(%) | 등락 |
| 12 | `CNTG_VOL` | 틱 체결량 | **거래량 급증** |
| 13 | `ACML_VOL` | 누적거래량 | 거래량 급증 |
| - | `PRDY_VOL_VRSS_ACML_VOL_RATE` | 전일거래량 대비 비율 | 거래량 급증 |

→ **"직전 N초 대비 급락"**: 종목별로 `(STCK_CNTG_HOUR, STCK_PRPR)`을 슬라이딩 윈도우에 적재, N초 전 가격 대비 하락률 계산.
→ **"거래량 급증"**: `CNTG_VOL` 누적 또는 `ACML_VOL` 증가 속도를 평소(분당 평균)와 비교. 1분봉이 직접 오지는 않으므로 **체결틱을 직접 1분 버킷으로 집계**해야 함(분봉 전용 실시간 TR은 없음).

#### 1-5-1. 실측 결과 (2026-06-29 14:50 KST 장중, `kis_ws/kr_ticks.py`)

IRP 실전 appkey로 3종목(005930/000660/035720) 구독 → 60초간 라이브 틱 수신:

| 종목 | 틱 수 | 샘플 |
|---|---|---|
| 005930 | 364틱 | 현재가 328,000 / 전일대비율 -3.39% / 누적량 28,576,648 |
| 000660 | 302틱 | 현재가 2,659,000 / -0.52% / 체결강도 111.51 |
| 035720 | 41틱 | 현재가 36,250 / **+9.35%(급등)** / 전일거래량대비 88.30 |

- ✅ **3/3 구독 성공**(IRP 3건 캡 내), **현재가·전일대비율·틱체결량·누적거래량·체결강도·전일거래량대비 전부 라이브 수신**.
- ✅ **지연**: 14:50:57~58초 사이 초당 다수 틱 → 체감 1초 미만(사실상 실시간).
- ✅ **신호 산출 실증**: 윈도우 내 낙폭·틱체결량합 계산 동작 → 급락·거래량급증 탐지 파이프라인 실데이터로 가능 확인.
- 035720 +9.35% / 전일거래량대비 88% 같은 실제 급변동이 그대로 포착됨.

### 1-6. 해외(미국) 실시간 (소스 확인 ✅)

| 용도 | TR ID | 미국 | 아시아 |
|---|---|---|---|
| 실시간지연체결가 | `HDFSCNT0` | **실시간 무료(0분 지연)** | 15분 지연(무료) |
| 실시간호가(1호가) | `HDFSASP0` | **실시간 1호가 무료**(유료시세 없음) | 유료신청 시 |
| 지연호가(아시아) | `HDFSASP1` | - | 15분 지연(무료) |
| 실시간체결통보 | (해외) | 내 주문 체결 | |

- **미국은 체결가·1호가 모두 0분 지연 무료** — 별도 유료 신청 불필요. (아시아는 15분 지연이 기본, 실시간은 유료)
- **`tr_key` 형식(소스 확인)**: 일반 세션 = `D` + 거래소(`NAS`나스닥/`NYS`뉴욕/`AMS`아멕스) + 심볼 → 예 `DNASAAPL`. 미국**주간거래**(10:00~16:00 KST)만 = `R` + `BAQ/BAY/BAA` + 심볼.
- **HDFSCNT0 응답 컬럼(인덱스)**: `LAST`(10, 현재가)·`RATE`(13, 등락률)·`EVOL`(18, 체결량)·`TVOL`(19, 누적거래량)·`KHMS`(6, 한국시각)·`STRN`(23, 체결강도) → 미국도 급락/거래량급증 산출 가능.
- 주의: 미국 0분지연시세는 장중 당일 시가가 상이할 수 있고 익일 정정될 수 있음(공식 고지).
- **시간대(KST)**: 정규장 ≈22:30~05:00(틱 풍부), 프리마켓 ≈17:00~22:30(드묾), 애프터 ≈05:00~07:00. 검증 스크립트 `kis_ws/us_ticks.py`(IRP 3건 캡 내 3종목). 프리마켓 0건이면 정규장(22:30+) 재시도 권장.

### 1-7. 지연(latency)·재연결

- ✅ **실측(2026-06-29 14:50 장중)**: 국내 틱 초당 다수 수신, 체결시각과 로컬 수신 거의 동시 → 체감 1초 미만. (정밀 latency 수치는 NTP 동기 후 별도 측정 권장)
- 재연결: KIS는 일정 시간 무데이터/네트워크 단절 시 연결이 끊김. **끊기면 approval_key는 재사용 가능**하므로 재연결 후 구독 메시지를 다시 send 하면 복구. (python-kis는 이 복구 로직을 내장 — [2-3] 참고)
- 운영 권고: ping/pong 또는 주기적 수신 체크로 헬스 모니터링 + 지수 백오프 재연결.

---

## [2] python-kis (Soju06/python-kis) — 실설치 2.1.6 검증

### 2-1. 설치 / 인증

```bash
python3.11 -m venv .venv && . .venv/bin/activate   # Python 3.10+ 필수
pip install python-kis
```
- 검증 환경: **Python 3.9에서는 임포트 실패**(`str | None` 문법) → **3.10+ 필요**. 3.11.15에서 정상.
- 의존성 `typing_extensions`가 누락될 수 있어 함께 설치 권장(`pip install typing_extensions`).
- 인증 객체(키는 환경변수로 주입, 파일 저장 지양):
  ```python
  from pykis import PyKis, KisAuth
  auth = KisAuth(id=HTS_ID, appkey=APP_KEY, secretkey=APP_SECRET,
                 account="44444444-29", virtual=False)
  kis = PyKis(auth, keep_token=True)
  ```
- ⚠️ python-kis는 **HTS ID(`id`)가 필수** — appkey/secret만으로는 안 됨.

### 2-2. 통합 잔고 `account().balance()` (introspection ✅)

`kis.account().balance()` → `KisBalance`. **국내+해외 동일 인터페이스로 통합 반환.**

**계좌 요약(`KisBalance`):**
| 필드 | 의미 |
|---|---|
| `purchase_amount` / `current_amount` | 총매입 / 총평가금액 |
| `profit` / `profit_rate` | 평가손익 / 손익률 |
| `deposits` | **통화별 예수금 dict** (`{'KRW':KisDeposit, 'USD':...}`) |
| `stocks` | 보유종목 리스트(`KisBalanceStock`) |
| `withdrawable_amount` | 출금가능금액 |

**예수금(`KisDeposit`)**: `amount`, `withdrawable_amount`, **`exchange_rate`**(환율).

**보유종목(`KisBalanceStock`)** — 요청 필드 전부 존재:
| 요청 항목 | 필드 |
|---|---|
| 종목코드 | `symbol` |
| 종목명 | `name` |
| 수량 | `qty` / `quantity` |
| 평단가 | `purchase_price` |
| 현재가 | `current_price` / `price` |
| 평가금액 | `amount` / `current_amount` |
| 평가손익 / 손익률 | `profit` / `profit_rate` |
| 통화 | `currency` ('KRW'/'USD') |
| **환율** | `exchange_rate` |
| **원화환산 매입금액** | `purchase_amount_krw` |
| 국내/해외 구분 | `domestic` / `foreign` |
| 시장 | `market` / `market_name` |

→ **해외 잔고의 원화환산·환율 필드 존재 확인됨**(`exchange_rate`, `purchase_amount_krw`). KIS raw API에서 2개 TR(현지통화 `TTTS3012R` + 환율 `CTRP6504R`)로 나뉘던 것을 python-kis가 종목 단위로 합쳐 제공.

#### 2-2-1. 실측 결과 (2026-06-29, 실계좌)

`pykis/balance_quote.py` 실행 성공 — raw API(`kis_rest/balance.py`)와 **수치 완전 일치**(교차검증):

| 항목 | raw TTTC8434R | python-kis balance() | 일치 |
|---|---|---|---|
| 총평가금액 | `tot_evlu_amt` 7,967,900 | `current_amount` 7,967,900 | ✅ |
| 평가손익 | `evlu_pfls_smtl_amt` 722,450 | `profit` 722,450 | ✅ |
| 종목 평가금액(284430) | `evlu_amt` 738,150 | `amount` 738,150 | ✅ |
| 보유종목 수 | 5건 | 5건 | ✅ |

- 보유 5종목 전부 **KRX 상장 ETF**(KODEX 미국S&P500 등 — 미국자산 추종이나 국내상장), `currency='KRW'`, `exchange_rate=1`.
- ⚠️ **발견한 라이브러리 quirk(python-kis 2.1.6)**: `KisBalanceStock.domestic`/`foreign`가 `MARKET_TYPE_MAP["KRX"]=['300']` 기준으로 판정하는데, 잔고 응답의 `market`이 리터럴 `"KRX"`로 와서 **국내 KRX 종목이 `foreign=True`로 오분류**됨. → 국내/해외 판별은 `domestic` 속성 대신 **`currency`(KRW=국내) 또는 `market` 문자열**로 할 것. (스크립트는 `currency` 기준으로 수정함)
- ⚠️ 반환값은 **`Decimal`**이라 그대로 출력하면 지수표기(`3E+1`)가 됨 → 표시 시 `float`/`int` 변환 필요(스크립트 `fmt()`로 처리).
- 이 계좌엔 **외화(USD) 보유가 없어** `exchange_rate`/원화환산의 실제 환율 적용은 미실증(필드 존재는 introspection으로 확인). 실제 미국주식 보유 계좌에서 USD 환율값 재확인 권장.

### 2-3. 실시간 시세 구독 (복구형 웹소켓 ✅)

```python
stock = kis.stock("005930")
def on_price(sender, e):
    r = e.response          # KisRealtimePrice
    ...
ticket = stock.on("price", on_price)   # "price" | "execution" | "orderbook"
ticket.unsubscribe()
```
- README 명시: **"연결이 끊겼을 때 완벽히 복구"** → 자동 재연결 내장.
- `KisRealtimePrice` 주요 필드(introspection): `price`/`last`, `change`/`change_rate`(전일대비/률 → **급락**), `volume`(틱량)/`volume_rate`(전일거래량대비 → **거래량급증**)/`prev_volume`, `intensity`(체결강도), `high`/`low`/`open`, `ask`/`bid`, `time_kst`.
- 이벤트 종류: `KisRealtimePrice`(체결가), `KisRealtimeOrderbook`(호가), `KisRealtimeExecution`(체결통보).

#### 2-3-1. 실측 결과 (2026-06-29, `pykis/realtime_cap.py`)

IRP 실전 appkey로 6종목 `on("price")` 구독 시도 → **로그 집계 실측**:

| 측정 | 값 |
|---|---|
| 등록 성공(OPSP0000) | **3건** |
| 캡초과(OPSP0008) | **3건** |
| 실제 콜백 수신 | 0 (주말이라 정상) |

- ✅ **python-kis도 IRP에서 동일한 3건 캡을 그대로 겪음 — 추론이 실측으로 확정**(raw=3, python-kis=3).
- ⚠️ **python-kis 2.1.6은 OPSP0008(MAX SUBSCRIBE OVER)에 대한 처리 case가 없음** → 예외를 던지지 않고 `RTC Unhandled control message ... (OPSP0008)` **경고 로그만 남기고 조용히 무시**. 4번째 종목부터 **콜백이 영영 오지 않는 형태로 실패** → 운영 시 반드시 로그 모니터링 또는 `subscribed_event` 카운트로 등록 성공 수를 직접 확인해야 함.
- ⚠️ **REST 오버헤드**: `kis.stock(sym).on(...)` 1건마다 현재가(`FHKST01010100`)+종목정보(`CTPF1604R`) **REST를 추가 호출** → 빠른 연속 구독 시 "API 호출 횟수를 초과하였습니다"(20건/초) 경고 다발. 대량 구독 시 구독 간 지연 필요.
- ⚠️ **모의(VTS) 단독 사용 불가**: `KisAuth(virtual=True)`만으로 `PyKis` 생성 시 `ValueError: auth에는 실전도메인 인증 정보를 입력해야 합니다`. python-kis는 **실전 appkey를 primary로 요구**하고, 모의는 `virtual_auth` 보조 인자로만 붙임(실전+모의 키 둘 다 필요).
- ⚠️ 단일 인스턴스는 한도(IRP=3 / 정상=41)를 공유 → 대량 구독은 raw WebSocket 다중 appkey 세션이 유리.

**실시간 콜백 라이브 실측(2026-06-29 14:56 장중)**: 284430 구독 → **15초간 27틱 수신**.
콜백 `KisRealtimePrice`에 `price`·`change_rate`·`volume`·`volume_rate`·`intensity`·`time_kst` 라이브 도착 확인.
→ ✅ python-kis 실시간 경로 정상 동작(IRP 3건 캡 내). 관찰: `volume`은 **누적거래량(ACML_VOL)** 으로 보임(틱당 증분 아님) → 거래량급증엔 `volume_rate`/델타 사용. 값은 `Decimal`이라 표시 시 변환 필요(잔고와 동일 quirk).

---

## 3. 실측 실행 방법(사용자)

```bash
# 공통: 키는 환경변수로만 (앞 공백 1칸 넣으면 셸 히스토리 미기록)
export KIS_APP_KEY='...'; export KIS_APP_SECRET='...'

# (A) 실시간 WebSocket + 41건 한도 실측
pip install websocket-client
export KIS_ENV=real KIS_SUB=ccnl
python verify/yhr/kis_ws/kr_quote.py

# (B) python-kis 통합 잔고 + 실시간
python3.11 -m venv .venv && . .venv/bin/activate
pip install python-kis
export KIS_HTS_ID='...' KIS_ACCOUNT='44444444-29' KIS_VIRTUAL=0 KIS_RT=1
python verify/yhr/pykis/balance_quote.py
```
- 실시간 **틱 데이터는 장중(평일 09:00~15:30 KST)**에만 수신. 한도 등록 테스트는 장 마감에도 가능.
- 산출물: 41건 한도 실측치, 체결틱 필드 실값, 잔고 통합 필드 실값.

## 4. 결론 / 설계 권고

1. **급락+거래량급증 탐지**: H0STCNT0(국내)/HDFSCNT0(미국) 체결틱을 받아 종목별 슬라이딩 윈도우로 직접 집계. 분봉 실시간 TR은 없으므로 **틱→1분 버킷 자체 집계** 구현.
2. **미국 실시간 무료** 확인 — 미국 종목 모니터링은 추가 비용 없이 가능(아시아만 15분 지연).
3. **30~50종목 커버**: 공식 한도 41이면 체결+호가 동시 ~20종목/세션. **그러나 현 IRP(29) appkey는 실측 3건 캡** → 이 계좌론 사실상 불가. 위탁계좌(01) appkey로 41 확보가 선결 과제. 그래도 30~50+체결·호가면 **다중 appkey 세션 샤딩** 필요.
4. **잔고/통합 조회는 python-kis가 가장 간편** — 국내+해외+환율+원화환산을 한 번에. 단 HTS ID 필요, Python 3.10+.
5. ⚠️ 이 계좌는 **IRP(29) 퇴직연금**: 주문계열 API 차단(`APBK1744`), 잔고/시세 조회는 정상. **실시간 등록 3건 캡 확정**(모의=41 대비 → IRP 계좌 서버측 제한). 이 계좌로는 실시간 대량 모니터링·자동매매 모두 불가.
6. **개발 단계: 모의투자 appkey 사용**(실측 41건 + 주문 시뮬레이션). 급락·거래량 탐지 파이프라인은 모의로 끝까지 구현·검증 가능.
7. **실전 운용 단계: 위탁계좌(01) 개설 + 전용 appkey**(공식 41 + 실주문). IRP는 잔고/시세 조회용으로만 유지. (원하면 KIS 고객의 소리에 'IRP appkey 실시간 3건 제한' 사유 문의 가능 — 정책 문의만 지원)

## 부가 검증: 기간 체결내역 (위탁계좌 01, ✅ 실측 2026-06-29)

별도 위탁(01) 계좌(실매매 이력 보유)로 `verify/yhr/kis_rest/ccld_history.py` 실행 → **양쪽 TR 정상**:

| 구간 | TR | 결과 |
|---|---|---|
| 3개월 이내 | `TTTC0081R` | rt_cd=0, 6건 수신 |
| 3개월 이전 | `CTSC9215R` | rt_cd=0, 5건 수신("마지막 자료"=D) |

- **APBK1744 미발생** → 위탁(01)은 기간 체결내역 정상 허용(IRP(29)는 차단됐던 것과 대비 확정).
- **3개월 이전 TR로 2~3월 데이터까지 조회 확인** → 과거 기간 조회 동작.
- **output1 필드(36개, 실데이터)**: 핵심 = `ord_dt`(주문일자)·`odno`(주문번호)·`pdno`/`prdt_name`·`sll_buy_dvsn_cd_name`(현금매수 등)·`ord_qty`/`ord_unpr`·`tot_ccld_qty`(총체결수량)·`avg_prvs`(체결평균가)·`tot_ccld_amt`(총체결금액)·`rmn_qty`(잔여)·`ccld_cndt_name`·`excg_id_dvsn_cd`(KRX). 그 외 `ord_dvsn_name`·`ord_tmd`(주문시각)·`cncl_yn`·`rjct_qty`·`loan_dt` 등.
- **output2 요약 필드**: `tot_ord_qty`·`tot_ccld_qty`·`tot_ccld_amt`·`prsm_tlex_smtl`(추정제비용)·`pchs_avg_pric`.
- 검증 스크립트: `verify/yhr/kis_rest/ccld_history.py`(3개월 이내/이전 + 연속조회 + 과거 한계 점검, 주문번호·계좌 마스킹).

## 부록: 동봉 스크립트 (`verify/yhr/`)
- `kis_rest/balance.py` — raw REST(국내/연금 잔고·체결내역)
- `kis_ws/kr_quote.py` — raw WebSocket 국내(체결/호가, 등록 한도 실측)
- `kis_ws/kr_ticks.py` — raw WebSocket 국내 실시간 틱 수신·급락/거래량 산출 검증(장중)
- `kis_ws/us_ticks.py` — raw WebSocket 미국(HDFSCNT0 실시간 틱, 프리/정규장)
- `pykis/balance_quote.py` — python-kis(통합 잔고 + 실시간 옵션)
- `pykis/realtime_cap.py` — python-kis 실시간 등록 캡 실측(OPSP0008 집계)
- `kis_rest/ccld_history.py` — 위탁계좌 기간 체결내역(3개월 이내/이전) 실측
