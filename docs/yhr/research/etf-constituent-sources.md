# ETF 구성종목(holdings / PDF) 데이터 원천 조사

> 용도: 포트폴리오 보유 ETF를 구성종목으로 **분해(look-through)**하여, 개별 종목의
> 종합 비중과 섹터별 비중을 계산하기 위함. 국내 ETF·미국 ETF 둘 다 대상.
>
> 작성일: 2026-06-28 (최종수정: 2026-06-29 — 실측·KRX 추가조사·데이터엔지니어링 검토 반영)
> 검증 원칙: 본문의 사실은 GitHub README 또는 공식/문서 페이지를 직접 확인해 작성.
> 직접 확인하지 못한 항목은 단정하지 않고 맨 아래 **"확인 필요 항목"**으로 분리.
> (일부 운용사·벤더 페이지는 봇 차단(403)/JS 렌더링으로 직접 fetch가 막혀, 다수 출처
> 교차검증 또는 검색 스니펫으로 확인한 부분은 그 취지를 본문/확인필요에 표기.)

용어: PDF = Portfolio Deposit File = (국내) 1CU(설정·환매 최소단위)당 자산구성내역 = 구성종목 바스켓.

---

## 0. 실측 검증 결과 (2026-06-28, 실제 실행)

> 아래를 **실제로 다운로드/호출**해 검증함. 실행 환경은 macOS + **KT 가정용 IP**(KT/Kornet AS4766,
> `hosting:false`로 확인 — 데이터센터 아님). curl/python으로 실행.
> ⚠️ **정정(2026-06-28):** 초판에서 pykrx·iShares 실패를 "데이터센터 IP 차단"으로 적었으나 **이는 틀렸음.**
> 실제로는 **가정용 KT IP에서 실행했고 그래도 막혔으며**, 원시 응답 분석 결과 원인은 IP가 아니라
> **JavaScript 기반 봇 차단**임을 확정함(아래 §0-근본원인 참조).

| 원천 | 결과 | 핵심 관찰 |
|------|------|-----------|
| **SPDR SPY XLSX** | ✅ **성공** | 진짜 엑셀 파일(54KB) 수신. 기준일 `As of 25-Jun-2026`, 약 503개 종목, weight 합계 **100.21%**(100% 초과). 봇 게이트 없음 → curl로도 정상. |
| **iShares IVV CSV** | ❌ **차단(JS 봇)** | `.ajax?fileType=csv`가 CSV 대신 **HTML 상품페이지** 반환. 응답에 **Akamai Bot Manager 쿠키(`bm_ss`/`bm_s`/`bm_so`)**. `content-type: text/csv`·`content-disposition: attachment` 헤더는 붙지만 본문은 2.17MB HTML(soft block). UA·Referer·`Sec-Fetch-*` 다 줘도 동일. |
| **pykrx / KRX** | ❌ **차단(JS 게이트)** | `get_etf_portfolio_deposit_file` 빈 DF, `get_etf_ticker_list()` `IndexError`. 원인: `getJsonData.cmd`가 **모든 bld**(전종목 시세 `MDCSTAT01501` 포함)에서 **`LOGOUT`(HTTP 400)**. KRX 첫 페이지는 474B JS 부트스트랩(`/WEB-APP/webponent/ci/agent.js`)뿐 — JS 실행 없이는 유효 세션 미발급. |
| (보너스) **네이버 ETF 목록 JSON** | ✅ 성공 | `finance.naver.com/api/sise/etfItemList.nhn` 정상 JSON(257KB). 단 **ETF 목록/NAV**이며 구성종목 아님(예: KODEX 200, nav 137479). |

### §0-근본원인 (원시 응답으로 확정)
- **KRX/pykrx = `agent.js` 클라이언트 무결성 JS 게이트.** 첫 페이지가 `<script src=".../ci/agent.js">` +
  `window.location.href=...` 부트스트랩(474B). 이 JS를 브라우저에서 실행해야 유효 쿠키가 생기며, 안 거치면
  데이터 API는 전부 `LOGOUT`. **UA/Referer/세션쿠키/XHR/https 변경 무효.** → `requests` 기반(pykrx 1.0.51 포함)은
  통과 불가. **pykrx 버그가 아니라 KRX 측 봇 차단.** IP 무관(가정용 KT에서도 동일).
- **iShares = Akamai Bot Manager JS 센서.** `bm_*` 쿠키가 그 증거. Akamai의 JS 센서(`_abck`)를 브라우저에서
  실행해 유효 세션을 못 만들면, 헤더는 CSV인 척하면서 본문은 HTML을 주는 soft block. **IP·헤더로는 못 뚫음.**
- **SPDR = 게이트 없음.** 정적 `library-content/...xlsx`라 curl로도 됨 → 환경 무관 안정.

### 실측으로 확정된 사실(데이터 포맷)
- **SPDR XLSX는 실전 사용 가능**. 실제 헤더(행 인덱스 3):
  `Name | Ticker | Identifier(=CUSIP 9자리) | SEDOL | Weight | Sector | Shares Held | Local Currency`
  - 상단 3행은 메타(Fund Name / Ticker / "As of …"), **하단 3행은 면책 문구** → 파싱 시 위·아래 모두 잘라내야 함.
  - **Sector 컬럼은 512행 전부 `-`(빈 값)** → SPY 일별 XLSX로는 **섹터 비중 못 구함**(섹터는 별도 원천 필요).
  - **ISIN 없음**(CUSIP·SEDOL만 제공). Shares는 지수표기(예 `2.97214682E8`).
  - weight 합계 **100.21%** → 100%가 아님(반올림/재정규화). look-through 시 합계 보정 정책 필요(3-2 참조).

### §0-2 브라우저 검증 (사용자 실측, 2026-06-29) — JS 게이트 가설 확정
실제 브라우저(사람)로 다운로드한 결과. **curl ❌ / 브라우저 ✅** 가 확인되어 "JS 봇 차단"이 원인임이 최종 증명됨.

| 원천 | 브라우저 | curl | 실측 내용 |
|------|:---:|:---:|-----------|
| **iShares IVV** | ✅ | ❌ | 실제 다운로드는 **`.xls`(Excel 2003 SpreadsheetML XML, 3.1MB)**. 진짜 holdings 확인 — 헤더 `Ticker, Name, Sector, Asset Class, Market Value, Weight (%), Notional Value, Quantity, Price, Location, Exchange, Currency, FX Rate, Accrual Date`. **Sector 채워져 있음**(예 NVDA=Information Technology), weight 합계 **100.07%**. |
| **SPDR SPY** | ✅ | ✅ | `holdings-daily-...spy.xlsx` 정상(게이트 없음, curl과 동일 파일). |
| **KRX 화면** | ✅(로그인 후) | ❌ | data.krx.co.kr 접속 시 **로그인 알럿** → 로그인 후 CSV 다운로드 가능. 첫 시도 화면(`data_3113`)은 **구성종목이 아니라 전체 ETF 목록·메타**(1142종목)였으나, **이후 올바른 ETF › PDF [13108] 화면에서 KODEX 200 구성종목 CSV 확보 성공**(201종목·§1-2). curl은 JS 게이트로 차단. |

**iShares 실제 다운로드 URL(브라우저가 호출하는 BlackRock varnish-api):**
```
https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v1/get-fund-document?appType=PRODUCT_PAGE&appSubType=ISHARES&targetSite=us-ishares&locale=en_US&portfolioId=239726&component=fundDownload&userType=individual
```
> `portfolioId`(=239726, IVV)만 바꾸면 다른 iShares 펀드도 동일 패턴. 응답은 `.xls`(SpreadsheetML). 단 이 URL도
> **Akamai 봇 센서를 통과한 브라우저 세션에서만** 파일이 내려옴(순수 curl은 동일하게 차단될 것으로 예상).

**중요 데이터 차이(실측 확정):** **iShares는 Sector·Asset Class를 제공**(섹터 비중 계산 가능)하지만 **SPDR SPY 일별 XLSX는 Sector가 빈 값**.
→ 섹터 분석이 목적이면 **iShares가 직접 제공해 유리**(단 다운로드에 브라우저 통과 필요). SPDR도 종목 마스터로 섹터 보강은 가능(§5).
> ⚠️ **단, 이 iShares `.xls`(fundDownload) 헤더엔 CUSIP/ISIN/SEDOL이 없음**(위 14개 컬럼이 전부). 식별자(ISIN 등)는
> 별도 `.ajax` CSV 경로(talsan README 기준)에는 있다고 하나 **본 실측 파일에는 미포함** → iShares도 ISIN 매핑이 필요할 수 있음.

### 결론에 대한 영향
- 두 실패는 **IP가 아니라 JS 봇 차단**이므로, "가정용 IP면 됨/서버면 막힘" 프레임은 **부정확**.
  브라우저(사람/헤드리스)는 JS를 실행하므로 통과하고, 순수 `requests`/`curl`은 환경과 무관하게 막힘. (§0-2로 증명됨)
- 따라서 **무인 자동화** 설계 시: ① 게이트 없는 원천 우선(미국=**SPDR**), ② 섹터까지 필요하거나 iShares가
  불가피하면 **헤드리스 브라우저**(Playwright/Selenium)로 JS 게이트 통과 후 수집(단 UI 취약·약관 검토).
- **KRX 화면 경로 주의:** 로그인이 필요하고, 처음 시도한 **목록/메타 화면**은 구성종목이 아니었음(이후 올바른
  **ETF › PDF [13108]** 화면에서 구성종목 CSV 확보 성공 — §1-2). **국내 OPEN API에는 구성종목이 없음이 §1-3에서
  확정**되었으므로, 국내 무료·합법·코드 자동화 경로 선택은 §4·§5에서 미결정으로 다룸.

---

## 1. 국내 ETF 구성종목 원천

### 1-1. pykrx (Python 라이브러리, KRX 스크래핑) — **API 확인됨 / 이 환경 실측 실패(§0)**
- **(a) 접근 방식**: Python 패키지. 내부적으로 KRX/네이버를 스크래핑.
  - 핵심 함수: `stock.get_etf_portfolio_deposit_file(ticker, date=None)`
  - 예시: ARIRANG 200(152100)의 구성종목으로 삼성전자(005930)가 비중 약 31.77%로 반환.
- **(b) 무료**: 무료. 오픈소스(GitHub `sharebook-kr/pykrx`).
- **(c) 갱신 주기**: KRX가 일별로 공시하는 PDF를 따라감(일별 기준일 조회 가능, `date` 인자).
- **(d) 제공 필드**: **티커, 계약수(수량), 금액, 비중** — 즉 종목코드·수량·평가금액·비중 + 기준일.
- **(e) 안정성/약관**: README 면책에 "데이터 저작권은 각 제공처(KRX/네이버)에 있으며 참고용으로만
  사용", 상업적 이용 시 원 제공처 약관 준수 명시. 스크래핑 기반이므로 KRX/네이버 페이지 구조
  변경 시 깨질 수 있음(라이브러리 업데이트 의존).
- ⚠️ **실측(§0)**: 내부적으로 `getJsonData.cmd`(bld `MDCSTAT05001`)를 `requests`로 호출하나, **KRX의
  `agent.js` JS 게이트 때문에 `LOGOUT`(400)으로 전량 차단**(IP 무관). pykrx 1.0.51 기준 **이 환경에서 작동 불가**.
- 🚫 **컴플라이언스(중요)**: KRX 공지(2026-06-01)가 **pykrx 등 비공식 사설 라이브러리 이용을 금지**한다고
  명시(§1-3). 기술적 차단과 별개로 **약관상으로도 권장되지 않음** → 무인/상업 파이프라인의 주원천으로 부적합.

### 1-2. KRX 정보데이터시스템 (data.krx.co.kr) — **✅ 구성종목 실측 확정** (브라우저 기준)
**증권상품 › ETF › PDF(Portfolio Deposit File) 화면 [13108]** 이 ETF 구성종목 조회 화면. 종목(예 069500)·
조회일자 입력 시 구성종목 표가 나옴. (화면 데이터는 "20분 지연 정보" 안내.) ETN·상장형 수익증권도 동일 PDF 화면 존재.
- **(a) 접근 방식**:
  - **화면→CSV/Excel 다운로드(OTP 방식)**: `…/comm/fileDn/GenerateOTP/generate.cmd` 로 OTP 토큰 발급 후
    다운로드 엔드포인트에 전달 → 파일 수신. (화면의 공식 내보내기 기능.)
  - **JSON 엔드포인트(POST)**: 모든 통계 화면이 공통으로 `https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd`
    사용. ETF 구성종목은 **`bld=dbms/MDC/STAT/standard/MDCSTAT05001`** + `isuCd`(표준코드 12자리, 예 KR7152100004)
    + `trdDd`(조회일자). 응답 필드: `COMPST_ISU_CD`(종목코드), `COMPST_ISU_NM`(종목명),
    `COMPST_ISU_CU1_SHRS`(주식수), `VALU_AMT`(평가금액), `COMPST_AMT`(구성금액), `COMPST_RTO`(구성비중).
  - ⚠️ **이 JSON/다운로드는 UI 내부 인터페이스**(공식 문서·보증 없음). **순수 `requests`/`curl`은
    `agent.js` JS 게이트로 `LOGOUT` 차단**(§0) → 브라우저/헤드리스 브라우저 세션 필요.
  - 🚫 **컴플라이언스**: KRX 공지(2026-06-01)는 목록에 없는 데이터는 **화면의 검색·다운로드 기능**으로만
    이용하라 권고하고 사설 라이브러리를 금지함(§1-3). `getJsonData.cmd`/OTP를 **프로그램으로 자동 호출**하는
    것은 그 취지와 충돌 소지 → **사람이 화면에서 CSV 받는 방식**이 약관상 안전. 자동화 전 이용약관 확인 필수.
- **(b) 무료**: 화면 조회·다운로드 무료. (단 화면 진입에 로그인이 요구되는 경우 있음 — 사용자 실측.)
- **(c) 갱신 주기**: 거래일 기준 일별(화면은 20분 지연 표기).
- **(d) 제공 필드(실측 CSV, KODEX 200)**: `종목코드, 구성종목명, 주식수(계약수), 평가금액, 시가총액, 시가총액 구성비중`.
  → **201종목, 비중합 100.11%**, 현금은 `KRD010010001 / 원화현금 / 비중 -0.01%` 라인으로 표기.
  (CSV는 표준코드 미포함·시가총액가중 비중. JSON(MDCSTAT05001)은 평가금액/구성금액/구성비중 등 더 상세.)
- **(e) 안정성/약관**: 공식 출처라 신뢰도 높음. **CSV는 EUC-KR 인코딩**. 내부 엔드포인트는 개편 시 변동 가능.
  **KRX 마켓데이터 이용약관(재배포·상업적 이용 제한)** 확인 필수. 별도 유료 대량 데이터 상품도 존재(무료 API와 무관).

### 1-3. KRX 공식 OPEN API (openapi.krx.co.kr) — **✅ 확정: ETF 구성종목 엔드포인트 없음** (사용자 실측)
- **(a) 접근 방식**: KRX가 별도로 운영하는 정식 OPEN API 포털(로그인은 data.krx와 동일 계정). 키 발급 후 REST.
- **결론**: **ETF 구성종목(PDF) API는 제공하지 않음.** 공식 'API 서비스 목록' 전수 확인 결과 증권상품 카테고리의
  ETF 관련 API는 **"ETF 일별매매정보"(시가·종가·거래량 등 매매정보) 하나뿐**이며 구성종목(바스켓)이 아님.
  (함께 ETN/ELW 일별매매정보, 지수 시세, 주식 매매·종목기본정보, 채권/파생/일반상품, ESG 정도. 모두 2010년 이후 일별.)
- **⚠️ 공지(2026-06-01, "KRX Open API 미제공 데이터에 대한 안내")**: Open API는 '서비스 목록' 항목만 제공하며,
  목록에 없는 데이터(=ETF 구성종목)는 ⓐ **Data Marketplace 화면에서 검색·다운로드**하거나 ⓑ **데이터 상품 구매**로
  이용하라고 안내. **이 공지는 pykrx 등 비공식 사설 라이브러리 이용을 금지한다고 명시.**
- **(e) 약관**: 따라서 §1-2의 `getJsonData.cmd` 내부 엔드포인트를 프로그램으로 호출하는 자동화는 위 공지 취지
  (화면의 검색·다운로드 기능만 사용 권고)와 **충돌 소지** → 자동화 전 **마켓데이터 이용약관 확인 필수**.
- 참고: 공공데이터포털 data.go.kr 에 KRX 연계 OpenAPI도 별도 존재(구성종목 포함 여부는 별건).

### 1-4. 네이버 금융 — **부분 확인**
- **(a) 접근 방식**:
  - ETF **목록**용 JSON 엔드포인트 `https://finance.naver.com/api/sise/etfItemList.nhn`
    (응답 `result.etfItemList`) — 단, 이는 **ETF 목록/시세/NAV** 데이터이며 **구성종목이 아님**.
  - **구성종목(CU 구성)**은 개별 ETF 종목 페이지의 "구성종목/CU당 구성종목" 영역을 스크래핑해야 함
    (BeautifulSoup/Selenium 등). 깔끔한 공개 JSON API는 확인 못 함.
- **(b) 무료**: 무료.
- **(c) 갱신 주기**: 일별(네이버가 표시하는 기준).
- **(d) 제공 필드**: 종목명/코드, 비중 등(페이지 표시 항목). 평가금액·수량 제공 범위는 페이지 의존.
- **(e) 안정성/약관**: 비공식 스크래핑 → 구조 변경 위험, robots.txt/약관 확인 필요. 식별자 매핑 시
  종목코드를 별도로 확보해야 하는 경우 있음.

### 1-5. 운용사 공식(삼성 KODEX, 미래에셋 TIGER 등) — **부분 확인**
- **KODEX(삼성자산운용)**: 공식 사이트 `samsungfund.com` ETF 라이브러리에서 ETF별 문서를
  **PDF 형식**으로 제공(`/etf/product/library/pdf.do`). 구성종목 자료가 PDF 문서로 공개됨.
  → 기계 가독 CSV/엑셀 직링크 형태인지(또는 PDF 파싱 필요인지)는 **확인 필요**.
- **TIGER(미래에셋자산운용)**: 공식 사이트 `investments.miraeasset.com/tigeretf`(구 tigeretf.com).
  각 ETF 상세 페이지에 **1CU 기준 구성종목(PDF)** 제공. 엑셀 다운로드 가능 여부는 검색으로 확정 못 함 → **확인 필요**.
- **(b) 무료**: 공개·무료.
- **(c) 갱신 주기**: 일별 공시(운용사 PDF는 영업일 기준 갱신).
- **(d) 필드**: 종목/수량/비중 등(운용사·문서 포맷별 상이).
- **(e) 안정성/약관**: 1차 출처라 신뢰도 높으나, 운용사마다 페이지/파일 포맷이 제각각이라
  통합 자동화 비용이 큼(운용사 N개 = 파서 N개).
- ⚠️ **실측 probe(2026-06-29)**: TIGER 상세 페이지는 **데이터를 JS로 렌더링**(정적 HTML엔 구성종목 표 없음),
  노출되는 건 **PDF 문서 링크**(`/tigeretf/upload/etf/*.pdf`)뿐. KODEX도 유사 추정(상품 페이지 302). → 순수 requests로
  바로 받으려면 **PDF 파싱** 또는 **화면 XHR 엔드포인트 역공학**이 필요(후자는 KRX 내부 엔드포인트와 같은 취약성 부류).

> 참고: 핀가이드(comp.fnguide.com)·와이즈리포트(comp.wisereport.co.kr) 등 3rd-party ETF 화면도
> 존재하나, 이용약관/안정성 측면에서 1차 채택 대상에서는 제외(필요 시 보조).

---

## 2. 미국 ETF holdings 원천

### 2-1. iShares (BlackRock) 공식 holdings — **브라우저 ✅ / 순수 curl ❌ Akamai 차단(§0·§0-2)**
> ⚠️ 실측: 순수 curl(브라우저 아님)로는 CSV가 아니라 HTML 상품페이지가 반환됨(Akamai 봇 차단, IP 무관).
> 브라우저 다운로드는 성공(§0-2). 아래 (d) 필드는 **두 경로가 다름**에 유의 — 본문 참조.
- **(a) 접근 방식**: 제품 페이지의 "Detail Holdings ... Download(CSV)" 링크. 공개 URL 패턴 예(IVV):
  `https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund`
  - 과거 일자: `&asOfDate=YYYYMMDD`(예 `asOfDate=20221230`) 추가. (오픈소스 스크래퍼 `talsan/ishares`
    기준 2006년까지 히스토리 조회 가능.)
- **(b) 무료**: 무료, **로그인 불필요**(공개 CSV).
- **(c) 갱신 주기**: 일 1회 갱신(영업일 기준).
- **(d) 제공 필드** — 경로별로 다름:
  - **실측 `.xls`(varnish-api fundDownload, §0-2)**: `Ticker, Name, Sector, Asset Class, Market Value, Weight (%),
    Notional Value, Quantity, Price, Location, Exchange, Currency, FX Rate, Accrual Date` → **섹터·Asset Class 있음, ISIN/CUSIP/SEDOL 없음**.
  - **`.ajax` CSV(talsan/ishares README 기준, 미실측)**: `ticker, name, sector, asset_class, market_value, weight,
    notional_value, shares, cusip, isin, sedol, price, ...` → 식별자 포함이라고 하나 **본 조사에서 직접 확인 못 함**(확인필요 #6 참조).
- **(e) 안정성/약관**: 1차 출처. 단, 봇 차단 정책(직접 자동화 시 `User-Agent`/throttle 필요, 위 스크래퍼도
  "polite, under-the-radar requests"). CSV 상단에 헤더/공시문구가 포함돼 파싱 시 스킵 처리 필요.
  공식 데이터 이용약관(자동 수집 허용 범위)은 **확인 필요**.

### 2-2. State Street SPDR 공식 XLSX — **✅ 실측 성공(§0)**
- **(a) 접근 방식**: 공개 라이브러리 직링크. 예(SPY):
  `https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx`
  (티커만 바꿔 다른 SPDR 펀드도 동일 패턴으로 접근하는 형태.)
- **(b) 무료**: 무료, 로그인 불필요(라이브러리 공개 파일).
- **(c) 갱신 주기**: 일별(파일명 `holdings-daily`).
- **(d) 제공 필드(실측 확정)**: `Name, Ticker, Identifier(CUSIP), SEDOL, Weight, Sector, Shares Held, Local Currency`.
  ⚠️ **Sector 컬럼은 SPY 파일에서 전부 빈 값(`-`)** → 섹터 비중은 이 파일로 못 구함. **ISIN 미제공**(CUSIP·SEDOL만).
- **(e) 안정성/약관**: 1차 출처, **서버 curl로도 정상 동작 확인**. 상단 3행(메타)·**하단 3행(면책)** 잘라내야 함.
  weight 합계가 100%가 아닐 수 있음(SPY 실측 100.21%). 자동 수집 약관 자체는 **확인 필요**.

### 2-3. Vanguard 공식 — **부분 확인**
- **(a) 접근 방식**: 각 ETF 제품 페이지의 "Holdings/Portfolio composition"에서 다운로드 가능(공개).
  iShares/SPDR 같은 **단일 안정 CSV 직링크 패턴은 직접 확인 못 함** → **확인 필요**.
  (개인 계좌 포지션 CSV는 로그인 필요이며, 이는 본 용도와 무관.)
- **(b) 무료**: 공개 페이지 무료.
- **(c)~(e)**: 갱신 주기·필드·직링크 안정성 미확인 → **확인 필요 항목** 참조.

### 2-4. Financial Modeling Prep (FMP) — **부분 확인(요금제 주의)**
- **(a) 접근 방식**: REST API.
  - 현행(stable): `https://financialmodelingprep.com/stable/etf/holdings?symbol=SPY&apikey=KEY`
    (과거 일자 `&date=...`), Bulk 엔드포인트도 존재.
  - 레거시: `/api/v3/etf-holder/{symbol}` ("ETF Holder API - Legacy").
- **(b) 무료**: **주의** — Free 플랜은 일 **250 requests/day**(초과 시 HTTP 429)지만, **ETF/펀드
  holdings 데이터셋은 유료 플랜(Starter 이상, 글로벌·전체 커버리지는 상위 Ultimate)에서 제공**된다는
  문서/리뷰 정황이 있음. Free에서 etf holdings가 어디까지 열리는지는 **확인 필요**.
- **(c) 갱신 주기**: 일별/분기 등 데이터별 상이(과거 일자 조회 지원).
- **(d) 제공 필드(추정)**: `asset`(티커), `name`, `shares`, `weightPercentage`, `marketValue` 등
  — 정확한 필드 스키마는 **확인 필요**(문서 페이지가 봇 차단됨).
- **(e) 안정성/약관**: 상용 API라 스키마 안정적. 단 무료 한도/유료 게이팅이 변동되는 편 → 의존 전 플랜 확인.

### 2-5. Alpha Vantage `ETF_PROFILE` — **확인됨(요금제·한도)**
- **(a) 접근 방식**: REST. `function=ETF_PROFILE&symbol=SPY&apikey=KEY`.
- **(b) 무료**: 무료 키로 사용 가능(평생 무료 키). **한도: 25 requests/day, 5 requests/min**.
- **(c) 갱신 주기**: ETF 프로파일/holdings·섹터(일/주기적 갱신).
- **(d) 제공 필드**: net_assets, expense_ratio 등 메타 + **holdings 배열(symbol, description, weight)**
  + **sectors 배열(sector, weight)** → 섹터 비중을 원천에서 바로 제공(섹터 집계에 유리).
  (정확한 JSON 키 표기는 일부 미세 확인 필요.)
- **(e) 안정성/약관**: 상용 API, 무료 한도가 매우 빡빡(25/day)해 다수 ETF 분해엔 부족. 캐싱 필수.

### 2-6. Finnhub `/etf/holdings` — **부분 확인(유료 가능성)**
- **(a) 접근 방식**: REST. ETF holdings/constituents 조회. `skip`(과거 구성, skip=0=최신) 또는 `date`
  파라미터(둘 중 하나만). 응답은 `symbol` + `holdings` 배열 구조.
- **(b) 무료**: **주의** — ETF/뮤추얼펀드 **글로벌 holdings 커버리지는 상위(advanced/enterprise) 유료**
  대상이라는 정황. 무료 티어에서 US ETF holdings가 열리는지는 **확인 필요**(가격 페이지 JS 차단).
- **(c) 갱신 주기**: 일별/공시 기준(과거 구성 조회 가능).
- **(d) 제공 필드(추정)**: symbol, name, isin/cusip, share(수량), percent(비중), value(평가금액) 등.
  정확 필드는 **확인 필요**.
- **(e) 안정성/약관**: 상용 API. 무료 한도(분당 호출)·premium 게이팅 확인 필요.

---

## 3. 매핑(식별자·합계·중첩) 이슈

### 3-1. 식별자 체계
- **국내**: 6자리 **종목코드(단축코드)** 중심(예 삼성전자 005930). KRX는 12자리 표준코드(ISIN, 예
  KR7005930003)도 존재. pykrx/KRX는 단축코드 기준이 일반적.
- **미국**: **ticker** 중심. CUSIP/SEDOL/ISIN은 **원천·파일별로 제공 여부가 다름** — talsan README의 iShares `.ajax`
  CSV는 cusip/isin/sedol 포함이라 하나, **실측한 iShares `.xls`(fundDownload)·SPDR XLSX에는 ISIN이 없었음**(SPDR은 CUSIP·SEDOL만).
  → ticker만으로는 거래소 충돌 위험이 있어 **종목 마스터로 ISIN 보강 필요**. 채권·현금성 라인은 ticker가 비거나 CUSIP만 있는 경우 많음.
- **국내↔미국 통합**: 공통 키로 **ISIN**이 가장 안정적(국내 KR…, 미국 US…). ticker는 거래소/접미사
  충돌 위험(예: 동일 ticker 다른 거래소). 통합 종목 마스터(ISIN ↔ 내부 종목ID) 테이블을 두고,
  원천별 식별자(국내 단축코드 / 미국 ticker+CUSIP)를 ISIN으로 정규화하는 매핑 레이어 권장.

### 3-2. 비중 합계 ≠ 100% (현금·미매핑)
- holdings의 weight 합은 100%가 아닐 수 있음. 원천별 표기:
  - **현금/현금성**: 별도 라인으로 잡힘. **실측 예: KRX KODEX 200 CSV의 마지막 행 = `종목코드 KRD010010001,
    구성종목명 원화현금, 비중 -0.01%`** (현금이 음수 비중으로 표기되기도 함). 미국은 `asset_class=Cash`/
    종목명 "CASH"/"USD CASH" 등. 일부 원천은 현금을 아예 제외해 합이 100% 미만이 됨.
  - **선물/파생/FX**: notional 기준 음수/큰 비중이 섞일 수 있음(특히 인버스·레버리지·채권 ETF).
    iShares CSV의 `notional_value`/`asset_class`로 구분 가능.
  - **반올림 오차**: 종목 weight 합이 99.x~100.x%로 어긋남.
- **권장 처리**: (1) 현금·파생·미매핑을 "기타/현금" 버킷으로 명시 분리, (2) 개별 종목 비중을
  **주식분 합계로 재정규화(re-normalize)** 할지, **원본 weight 유지**할지 정책을 명확히. look-through
  종합 비중 계산 시 ETF별 (보유금액 × 종목weight)를 합산하되, 미매핑분을 손실 없이 합계 추적.

### 3-3. 중첩 ETF (ETF가 ETF/펀드를 보유; fund-of-funds)
- 일부 ETF는 구성종목으로 **다른 ETF/펀드**를 보유(예: 자산배분형, BND/BNDX 보유하는 펀드 등).
  holdings 라인에 ticker가 또 다른 ETF로 표기됨(asset_class가 Equity가 아닌 Fund/ETF인 경우 있음).
- **look-through 시**: 해당 라인을 다시 그 ETF의 holdings로 재귀 분해해야 정확. 무한루프/순환참조
  방지(방문 집합), 재귀 깊이 제한, 분해 불가(원천 없음) 시 "ETF 단위 미분해" 플래그로 잔류 처리.

---

## 4. 원천 옵션 정리 (미결정 — 채택 보류, 2026-06-29)

> 전제: 이 프로젝트는 **look-through(개별 종목 종합 비중 + 섹터 비중)**가 목적. 아래는 실측(§0/§0-2)과
> KRX 추가조사를 반영한 **옵션 비교**이며, **아직 어떤 방식을 채택할지는 결정하지 않음**(보류).
> 각 옵션의 데이터엔지니어링 관점 완화 가능성은 **§5** 참조 후 추후 결정 예정.
>
> **프로젝트 맥락: 현재 소규모·개인 분석용, 추후 상업화 검토 예정.** 상업화 시 발효되는 제약은 아래 박스로 분리.

> **🚩 상업화 시 제약 체크리스트 (지금은 비활성, 상업화 진입 전 반드시 해소)**
> - **KRX(국내)**: 화면 CSV 다운로드는 개인 이용 전제. **재배포·상업적 이용·자동 수집은 KRX 마켓데이터 이용약관
>   대상** → 데이터 상품 구매 또는 별도 라이선스 필요. **pykrx·내부 엔드포인트 자동화는 공지상 금지**(§1-3).
> - **운용사(KODEX/TIGER)**: 공시자료 상업적 재사용은 각 운용사 약관 확인 필요.
> - **iShares/SPDR/Vanguard(미국)**: 공개 holdings지만 **자동·대량 수집 및 재배포 허용 범위는 각 사 ToS 확인 필요**.
> - **데이터 벤더(Alpha Vantage/FMP/Finnhub)**: 무료 티어는 비상업·평가용 한정인 경우가 많음 → 상업화 시 유료 플랜·
>   재배포 권리 별도 계약.
> - 공통: **데이터 재배포 vs 내부 계산 결과만 노출**을 구분(개별 종목 weight 원본 재공개는 라이선스 이슈가 큼).

### 국내 — 옵션 비교 (미결정)
실측으로 **KRX가 구성종목을 정확히 제공**함을 확정(KODEX 200: 삼성전자 34.46%·SK하이닉스 32.24%, 201종목,
비중합 100.11%, `원화현금 -0.01%` 라인까지). 다만 **무료 + 순수 코드 + UI변경 견고함**을 동시에 만족하는 경로가 없음:
- **공식 OPEN API에는 ETF 구성종목이 없음**(확정, §1-3). ETF 관련은 "일별매매정보"뿐.
- **KRX 공지(2026-06-01)**: 목록에 없는 데이터는 **화면 검색·다운로드** 또는 **데이터 상품 구매**로만 이용하라 권고,
  **pykrx 등 사설 라이브러리·내부 엔드포인트 자동 호출은 금지/충돌 소지**.

| 옵션 | 자동화(코드) | UI변경 견고성 | 약관 | 비용 |
|------|:---:|:---:|:---:|:---:|
| 화면 CSV 수동 다운로드 | ✕(사람) | — | 개인 OK | 무료 |
| A. KRX 헤드리스 브라우저 | ○(브라우저엔진) | 🔴 약함(UI 의존) | ⚠️ 회색지대 | 무료 |
| B. 운용사 파일(KODEX/TIGER) | △(정적 HTML엔 PDF뿐 → PDF파싱/XHR역공학) | 🟡 중간 | △ 운용사 약관 | 무료 |
| C. 유료 데이터 벤더/KRX 데이터상품 | ○(문서화 API) | 🟢 견고 | ✅ 명확 | 유료 |

→ **결정 보류.** 각 옵션의 약점 중 데이터엔지니어링으로 줄일 수 있는 부분은 **§5** 참조.

### 미국 — 옵션 비교 (미결정)
- **SPDR(State Street) 공식 XLSX**: **봇 게이트 없음**(순수 requests로 서버에서도 됨, §0 ✅). 정적 URL이라 **견고**.
  단 **SPY 일별 XLSX는 Sector가 빈 값**(별도 섹터 원천 필요), 식별자는 CUSIP·SEDOL(ISIN 없음).
- **iShares(BlackRock)**: holdings에 **Sector·Asset Class** 포함(섹터에 유리, §0-2). 단 실측 `.xls`(fundDownload)에는
  **CUSIP/ISIN/SEDOL이 없었음**(식별자 매핑은 별도 필요할 수 있음). **Akamai 봇 센서로 순수 requests 불가** →
  헤드리스 브라우저 필요(UI변경 취약). 실제 다운로드는 varnish-api `get-fund-document`(.xls).
- **보조**: **Alpha Vantage ETF_PROFILE**(holdings+섹터, 25/day → 캐싱 필수). FMP·Finnhub는 무료 holdings 게이팅 불확실(키 필요).
- 운용사별 포맷(CSV/XLSX/SpreadsheetML, 헤더 오프셋, 현금/파생 라인)이 달라 **원천별 어댑터** 필요.

### 현황 요약 (결정 아님)
- **국내**: 구성종목 자체는 KRX에 존재하나 **무료·코드·견고 셋을 동시 충족하는 경로 없음** → A/B/C 트레이드오프 미결정.
- **미국**: **SPDR = 무료·requests·견고(단 섹터 별도)**, **iShares = 데이터 풍부하나 헤드리스 필요**. 보조 Alpha Vantage.
- **통합 키 = ISIN**. SPDR/KRX-CSV는 ISIN 미제공이라 종목 마스터(종목코드/CUSIP↔ISIN) 매핑 레이어 필요.

---

## 5. 데이터엔지니어링 관점 — 방식별 약점 완화 검토 (2026-06-29)

> 목적: 각 방식의 약점 중 **엔지니어링으로 해소/완화 가능한 것**과 **불가능한 것**을 구분(결정용 입력, 채택 아님).
> 핵심 구분: **"데이터 모양" 문제는 대체로 해소 가능**(섹터·ISIN 보강, 헤더 파싱, 비중 정규화, 레이트리밋, 매핑, 중첩ETF).
> **"접근·법적" 문제는 해소 불가**(JS게이트로 브라우저 강제, KRX 약관 금지, 재배포 권리, 비용) — 완화(어댑터·검증·캐시로 취약성/노출↓)나 회피(다른 원천)만 가능.

### 5-0. 모든 원천에 공통 적용하는 완화 패턴
- **소스 어댑터 분리**(fetch→parse→normalize): 깨지는 건 얇은 fetch/parse 레이어만 → 교체·수리 국소화.
- **출력 계약 검증(contract test)**: 컬럼명·타입·행수·**weight합 100%±tol**·종목코드 포맷 체크 → 포맷/UI 변경을
  "조용히 틀린 데이터"가 아니라 **명시적 실패+알림**으로 전환(취약성의 피해를 줄임).
- **골든 파일 회귀 테스트** + **기준일(asof) 스냅샷 버저닝**(멱등 적재).
- **캐싱 + 갱신 주기 튜닝**: 구성종목은 천천히 변함(지수 ETF는 분기 리밸런싱) → 마지막 정상본 캐시 + 신선도
  정책으로 **원천 호출 빈도↓ = 레이트리밋·차단·취약성 노출↓**.

### 5-1. 방식별 약점 → 완화 가능성

| 방식 | 약점 | 데이터엔지니어링 완화 | 해소 정도 |
|------|------|----------------------|:--:|
| **SPDR XLSX(미국)** | Sector 빈 값 | **섹터는 holding이 아니라 "종목의 속성"** → 종목 마스터(ticker/CUSIP→GICS섹터)를 1회 구축해 **조인**하면 섹터 비중 산출 가능(섹터는 거의 안 변해 1회성) | 🟢 완전 |
| | ISIN 없음 | 종목 마스터 CUSIP→ISIN 매핑 | 🟢 완전 |
| | 헤더 오프셋·면책행, weight≠100 | 헤더행 **동적 탐지**+꼬리 컷, 정규화/현금 버킷 정책 | 🟢 완전 |
| **Alpha Vantage(보조)** | 25 req/day 한도 | 캐싱 + ETF당 갱신주기 분산(주1회면 25/day로 충분 커버) | 🟢 사실상 해소 |
| **iShares(미국)** | 헤드리스 필요(UI 취약) | 어댑터 격리·계약검증·저빈도; 단 브라우저 엔진 의존 자체는 못 없앰 | 🟡 완화 |
| | 실측 .xls엔 ISIN/CUSIP 없음 | 섹터·Asset Class는 내장(보강 불필요); ISIN은 종목 마스터로 매핑 | 🟢 완전 |
| **B. 운용사 파일(국내)** | 정적 HTML엔 PDF뿐 | PDF 표 추출(pdfplumber/camelot)+강한 검증; XHR 엔드포인트 발견 시 PDF보다 안정 → 어댑터 추상화; 발행사별 파서 모듈화(보유 ETF 발행사 수만큼) | 🟡 완화 |
| | 발행사가 포맷 변경 | 검증으로 조기 감지 가능하나 파서 갱신은 불가피 | 🟡 완화(0 아님) |
| **A. KRX 헤드리스(국내)** | UI/DOM 의존 깨짐 | 셀렉터 설정 외부화; **브라우저로 세션쿠키만 얻고 데이터는 JSON 호출**(DOM 의존↓); 계약검증·알림·저빈도+캐시 | 🟡 완화 |
| | JS 게이트(agent.js) | 브라우저 엔진 강제 — **제거 불가** | 🔴 불가 |
| | KRX 약관(자동화 금지) | **법적 문제 — 엔지니어링으로 해소 불가**(완화=저빈도/내부 계산결과만 노출, 회피=다른 원천) | 🔴 불가 |
| **C. 벤더 API(국내/미국)** | 비용·레이트리밋·무료티어 비상업 | 캐싱·배치·증분·쿼터 내 스케줄링·로컬 적재로 호출/비용 관리 | 🟡 완화(비용·재배포권리는 계약 문제) |
| **공통(§3)** | ISIN 통합·weight 정규화·중첩 ETF 재귀 | 종목 마스터·정규화 정책·재귀 분해(순환 방지) | 🟢 완전 |

### 5-2. 함의 (결정용)
- **미국 무료 경로(SPDR)의 단점(섹터·ISIN 없음)은 종목 마스터 1개로 거의 완전 해소** → 무료·requests·견고를 유지하면서
  섹터 비중까지 산출 가능. "SPDR은 섹터가 없어서 안 된다"는 **데이터엔지니어링으로 무력화되는 약점**.
- **국내의 진짜 병목은 "데이터 모양"이 아니라 "접근·법적"** (JS게이트 브라우저 강제 + KRX 약관) → 이건 코드로 못 없애고,
  **완화(취약성·노출 최소화)**나 **회피(벤더 등 다른 원천)**만 가능. 즉 국내 A/B/C 선택은 **엔지니어링 난이도가 아니라
  "취약성·약관 리스크를 어디까지 감수하느냐"의 문제**로 귀결.
- 공통 패턴(어댑터·계약검증·캐시)은 **모든 방식의 "UI/포맷 변경 취약성"을 "조용한 오류→명시적 실패"로 바꿔 피해를 줄임**
  (취약성을 0으로 만들진 못하지만 운영 리스크를 크게 낮춤).

---

## 출처 URL 목록
- pykrx (GitHub): https://github.com/sharebook-kr/pykrx
- KRX 정보데이터시스템(이용안내): https://data.krx.co.kr/contents/MDC/INFO/informationController/MDCINFO002.cmd
- KRX 정보데이터시스템(메인): https://data.krx.co.kr/
- KRX ETF 목록/메타 화면: https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd?menuId=MDC020103010901
- KRX ETF **구성종목(PDF)** 화면 [13108]: 증권상품 › ETF › PDF (data.krx.co.kr 통계 메뉴)
- KRX JSON 엔드포인트(내부): https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd  (bld=dbms/MDC/STAT/standard/MDCSTAT05001)
- KRX OPEN API 포털(정식, ETF 구성종목 미제공): https://openapi.krx.co.kr/
- KRX 공지 "Open API 미제공 데이터에 대한 안내"(2026-06-01, 사설 라이브러리 금지·화면/데이터상품 안내): openapi.krx.co.kr 공지사항
- 공공데이터포털 KRX상장종목정보: https://www.data.go.kr/data/15094775/openapi.do
- 네이버 금융 ETF 목록 API: https://finance.naver.com/api/sise/etfItemList.nhn
- KODEX(삼성자산운용) ETF 라이브러리(PDF): https://www.samsungfund.com/etf/product/library/pdf.do
- KODEX ETF 메인: https://www.samsungfund.com/etf/main.do
- TIGER(미래에셋) ETF: https://investments.miraeasset.com/tigeretf/ko/main/index.do
- iShares IVV 제품 페이지: https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf
- iShares **실제 다운로드(브라우저 호출, .xls)**: https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v1/get-fund-document?appType=PRODUCT_PAGE&appSubType=ISHARES&targetSite=us-ishares&locale=en_US&portfolioId=239726&component=fundDownload&userType=individual
- iShares 홀딩스 .ajax CSV(구 패턴, curl은 Akamai 차단): https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf/1467271812596.ajax?fileType=csv&fileName=IVV_holdings&dataType=fund
- iShares 스크래퍼(필드 참조, GitHub): https://github.com/talsan/ishares
- SPDR SPY 일별 holdings XLSX: https://www.ssga.com/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx
- SPDR SPY 제품 페이지: https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy
- FMP ETF Holdings 문서: https://site.financialmodelingprep.com/developer/docs/historical-etf-holdings-api
- FMP ETF Holder API(Legacy): https://site.financialmodelingprep.com/developer/docs/etf-holders-api
- FMP 요금제: https://site.financialmodelingprep.com/pricing-plans
- Alpha Vantage 문서: https://www.alphavantage.co/documentation/
- Finnhub ETF holdings 문서: https://finnhub.io/docs/api/etfs-holdings
- Finnhub ETF/Indices 요금: https://finnhub.io/pricing-etf-indices

---

## 확인 필요 항목 (직접 확인 못 함 / 차후 실측 권장)
1. **pykrx 라이선스**: README상 오픈소스·무료는 확인했으나 정확한 OSS 라이선스(MIT 등) 표기 미확인.
2. ~~**KRX 공식 OPEN API의 ETF 구성종목 엔드포인트**~~: **해결됨(사용자 실측)** — openapi.krx.co.kr에는
   **ETF 구성종목 API 없음**(ETF는 "일별매매정보"만). 공지(2026-06-01)가 사설 라이브러리(pykrx) 금지 + 목록 외
   데이터는 화면 다운로드/데이터상품 구매로만 안내. → 국내 무료·합법 자동화 경로는 사실상 부재.
3. **네이버 금융 구성종목**: 깔끔한 공개 JSON API 존재 여부 미확인(개별 종목 페이지 스크래핑 전제로 작성).
   `etfItemList.nhn`은 구성종목이 아니라 ETF 목록/시세임.
4. **운용사(KODEX/TIGER) 기계 가독 다운로드**: PDF/제품 페이지 제공은 확인했으나, CSV/엑셀 직링크 패턴·
   안정 URL·전 종목 일괄 다운로드 가능 여부 미확인(PDF 파싱 필요할 수 있음).
5. **iShares/SPDR 자동 수집 이용약관**: 공개 CSV/XLSX·로그인 불필요는 확인, 자동·대량 수집 허용 범위
   (ToS/robots) 미확인. (운용사 페이지 봇 차단 403로 직접 확인 실패 — URL·필드는 다수 출처 교차검증.)
6. **iShares 필드 — 부분 해결**: 브라우저 다운로드 `.xls`(fundDownload) 헤더는 실측 확정(§0-2: Sector·Asset Class 있음,
   **ISIN/CUSIP/SEDOL 없음**, weight합 100.07%). 단 **talsan README가 말하는 `.ajax` CSV의 cusip/isin/sedol 컬럼은
   본 조사에서 직접 확인 못 함** → 식별자가 필요하면 `.ajax` 경로(또는 다른 export)를 실측 재확인 권장.
7. **Vanguard 공식 holdings 직링크/포맷/갱신주기**: 제품 페이지 다운로드 가능 정황만 확인, 안정 CSV
   직링크 패턴·필드 미확인.
8. **FMP ETF holdings의 Free 티어 접근성**: Free 250/day는 확인. 그러나 holdings 데이터셋이 무료에서
   열리는지/Starter·Premium·Ultimate 게이팅인지는 문서 페이지 봇 차단으로 미확정(실측 필요).
   필드 스키마(asset/shares/weightPercentage/marketValue/name)도 추정값.
9. **Finnhub /etf/holdings의 Free 티어 제공 범위·필드·분당 한도**: 글로벌 holdings는 유료 정황,
   무료에서 US ETF holdings가 열리는지 미확정(가격 페이지 JS 차단). 필드도 추정.
10. **Alpha Vantage ETF_PROFILE의 정확한 JSON 키 표기 및 수량/평가금액 제공 여부**: 25/day·5/min 한도와
    holdings/sectors 제공은 확인, 개별 키 명칭·수량 필드 유무는 실 응답으로 재확인 권장.
