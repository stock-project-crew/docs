# 종목 → 섹터(업종) 분류 데이터 원천 조사

> 용도: 포트폴리오의 **섹터별 비중**을 계산하기 위해, 보유 종목(및 ETF 구성종목 look-through 결과)을
> 섹터로 매핑하는 "종목 → 섹터" 분류 테이블이 필요. 국내·미국 둘 다.
>
> 작성일: 2026-06-29
> 검증 원칙: 본문 ✅ 표기는 **실제 curl/Python 호출로 확인**한 것. 직접 확인 못 한 항목은 단정하지 않고
> 맨 아래 **"확인 필요 항목"**으로 분리. 라이선스 판단은 일반적 공개정보 기반이며 법률 자문 아님.
>
> 평가축: **(b)무료/한도 · (c)라이선스·재배포 · (e)순수 코드(requests/curl) 수집 가능 · (f)식별자**
> 관련 문서: [ETF 구성종목 데이터 원천](etf-constituent-data-sources.md) — ETF look-through는 그쪽 참조.

---

## 0. 실측 검증 결과 (2026-06-29, 실제 실행)

환경: macOS + 가정용 IP, `curl` / `.venv/bin/python`(yfinance 설치), 별도 프록시 없음.

| 원천 | 결과 | 핵심 관찰 |
|------|------|-----------|
| **SEC EDGAR `company_tickers.json`** | ✅ 성공 | `curl -A "<email>"`로 200, 10,433개 ticker↔CIK 매핑(798KB). 봇 게이트 없음. |
| **SEC EDGAR `submissions/CIK….json`** | ✅ 성공 | AAPL → `sic:"3571", sicDescription:"Electronic Computers", tickers:["AAPL"], exchanges:["Nasdaq"]`. |
| **yfinance `Ticker.info`** | ✅ 성공 (미국+국내) | AAPL→Technology/Consumer Electronics, **삼성전자 005930.KS→Technology**, SK하이닉스 000660.KS→Technology, 카카오 035720.KS→Communication Services, 에코프로비엠 247540.KQ→Industrials. **ETF(069500/SPY)는 sector=None**. `sectorKey`/`industryKey`(머신용 slug)도 제공. |
| **Alpha Vantage `OVERVIEW`** | ✅ 성공 (demo key) | IBM → `Sector:"TECHNOLOGY", Industry:"INFORMATION TECHNOLOGY SERVICES", CIK:"51143"`. |
| **Alpha Vantage `ETF_PROFILE`** | ✅ 성공 (demo key) | QQQ → `sectors:[{sector:"INFORMATION TECHNOLOGY",weight:"0.586"},…]` + `holdings`. GICS식 섹터명. |
| **SPDR Select Sector ETF XLSX** (XLK) | ✅ 다운로드 성공 | `holdings-daily-us-en-xlk.xlsx`를 `curl -L`로 22KB OOXML 수신. **단 행별 `Sector` 컬럼은 전부 `-`(빈 값)**. 그러나 **ETF 자체가 곧 섹터**(XLK=Technology)이므로 11개 합치면 섹터 매핑 됨(아래 §1-D). |
| **Naver 금융 업종** | ✅ 성공 | `sise/sise_group.naver?type=upjong` 200(EUC-KR), **79개 업종**. 상세 `sise_group_detail…&no=283`(전기제품) → 68개 종목 **6자리 코드+종목명** 추출됨. |
| **data.go.kr 금융위_KRX상장종목정보** | ✅ 엔드포인트 생존 | 잘못된 키로 호출 시 `HTTP 401 Unauthorized` → 엔드포인트는 살아있고 **무료 serviceKey만 발급받으면 됨**. (업종 필드 포함 여부는 확인 필요 §2-D) |
| **KIS OpenAPI 종목정보** | ⏸ 미검증 | 이 세션에 `KIS_*` env 미설정 + 실계좌가 [퇴직연금](../../../../.claude/projects/-Users-yhr-Dev-workspace-personal-stock-project/memory/kis-account-is-pension.md)이라 일부 TR 막힘 → 라이브 호출 보류. TR·필드명만 정리(§2-A). |

> ⚠️ 기존 [ETF 문서](etf-constituent-data-sources.md) §0에서 확인된 차단도 그대로 유효:
> **KRX/pykrx = `agent.js` JS 게이트, iShares = Akamai 봇매니저** → 둘 다 requests/curl로 못 뚫음.

---

## 1. 미국 주식

### 1-A. yfinance (`Ticker.info`의 `sector`/`industry`) — ✅ 실측, **국내까지 한 방에**
- **(a) 접근**: `pip install yfinance` → `yf.Ticker("AAPL").info["sector"]`. 내부적으로 Yahoo Finance `quoteSummary`(`assetProfile` 모듈) 스크래핑.
- **(b) 무료/한도**: 무료. 공식 API 아님 → **비공식 rate limit**(과도 호출 시 일시 차단). 배치 시 `Tickers([...])`/지연 권장.
- **(c) 라이선스**: ⚠️ **가장 약한 고리**. Yahoo 데이터를 비공식 스크래핑 → Yahoo ToS상 회색지대. **개인 분석/내부용은 사실상 관행**이나, 재배포·상용은 부적합. *단 섹터 분류 체계 자체는 GICS 상표가 아닌 **Yahoo 자체 11개 섹터**(Technology, Financial Services, Healthcare …)라 GICS 라이선스 문제는 회피*.
- **(d) 체계**: Yahoo 자체 11 sector + ~140 industry. GICS와 유사하나 동일하지 않음(명칭·경계 다름).
- **(e) 순수 코드 수집**: ✅ 브라우저 불필요. JS 게이트 없음.
- **(f) 식별자**: ticker. 국내는 `005930.KS`(KOSPI) / `247540.KQ`(KOSDAQ) 접미사. CUSIP/ISIN 직접 조인은 안 됨.
- **메모**: **ETF는 sector=None** → ETF는 look-through 후 구성종목에 적용해야 함.

### 1-B. SEC EDGAR — SIC 코드 (**공공 도메인, 라이선스 완전 클린**) — ✅ 실측
- **(a) 접근** (둘 다 curl, `User-Agent`에 이메일 필수):
  - ticker↔CIK: `https://www.sec.gov/files/company_tickers.json`
  - 회사별 SIC: `https://data.sec.gov/submissions/CIK{10자리 zero-pad}.json` → `sic`, `sicDescription`
- **(b) 무료/한도**: 완전 무료. 가이드라인 **10 req/sec**, UA 헤더 권장.
- **(c) 라이선스**: ✅ **미국 정부 공공 도메인. 재배포 자유.** GICS 회피의 핵심 대안.
- **(d) 체계**: **SIC**(4자리, 산업분류). 투자자용 "섹터"와 1:1 아님 → 앞 1~2자리로 division(10개) 롤업하거나 SIC→GICS-style 매핑 테이블 별도 필요. 다소 구식·제조업 편중.
- **(e) 순수 코드 수집**: ✅ 정적 JSON, 게이트 없음.
- **(f) 식별자**: ticker·CIK 동시 제공. CUSIP/ISIN은 없음(별도 매핑 필요).
- **메모**: NAICS(미 Census, 공공도메인)도 대안이나 SEC 제출서류 기본 노출값은 SIC. EDGAR가 ETF엔 섹터를 안 줌(개별주만).

### 1-C. Alpha Vantage `OVERVIEW` / `ETF_PROFILE` — ✅ 실측 (demo key)
- **(a) 접근**: `query?function=OVERVIEW&symbol=IBM&apikey=KEY` → `Sector`,`Industry`,`CIK`. ETF는 `function=ETF_PROFILE` → `sectors[]`(weight 포함)+`holdings[]`.
- **(b) 무료/한도**: 무료키 **25 req/day**(매우 빡빡). `demo` 키는 IBM/QQQ 등 일부만.
- **(c) 라이선스**: 무료티어 = 개인/비상업. 섹터명은 GICS식이지만 AV 가공 데이터.
- **(d) 체계**: GICS식 대분류(11). ETF_PROFILE은 **ETF 섹터 비중을 직접** 줘서 look-through 없이 ETF 비중에 바로 쓸 수 있음(편리).
- **(e) 순수 코드 수집**: ✅ REST JSON.
- **(f) 식별자**: ticker(+CIK). **국내 종목은 커버리지 빈약**(미국 위주).
- **메모**: 25/day 한도 → 전 종목 일괄용 부적합, **보유 소수 종목·ETF 보조용**으로 적합.

### 1-D. SPDR Select Sector ETF "멤버십 = 섹터" 기법 — ✅ 실측, **S&P500 한정 클린 매핑**
- **(a) 접근**: 11개 ETF XLSX를 `curl -L`. 각 ETF의 holdings = 그 섹터 종목.
  `…/holdings-daily-us-en-{xlk|xle|xlf|xli|xlb|xlc|xlp|xlre|xlu|xlv|xly}.xlsx`
  | ETF | 섹터 | ETF | 섹터 |
  |---|---|---|---|
  | XLK | Technology | XLV | Health Care |
  | XLF | Financials | XLE | Energy |
  | XLY | Consumer Discretionary | XLP | Consumer Staples |
  | XLI | Industrials | XLB | Materials |
  | XLC | Communication Svcs | XLU | Utilities |
  | XLRE | Real Estate | | |
- **(b) 무료/한도**: 무료, 게이트 없음(SPDR는 정적 파일).
- **(c) 라이선스**: ETF holdings는 공시 의무 정보. **분류 자체는 GICS지만**, "이 종목이 XLK에 들어있다"는 사실 활용은 라이선스 회피로 통용. 본격 상용 재배포는 주의.
- **(d) 체계**: GICS 11 섹터(S&P가 ETF에 적용). 행별 Sector컬럼은 비어있으니 **ETF=섹터로 부여**.
- **(e) 순수 코드 수집**: ✅ (iShares와 달리 SPDR은 봇 게이트 없음 — 기존 ETF문서 §0 확인).
- **(f) 식별자**: ticker + **CUSIP**(Identifier 컬럼) + SEDOL. **CUSIP 조인 가능**이 강점. ISIN 없음.
- **한계**: **S&P 500 구성종목만** 커버(약 500). 그 외(소형주·KOSDAQ류 미국 ADR 등)는 빠짐.

### 1-E. Finnhub / FMP — ⏸ 미검증(키 필요), 문서 기준
- **Finnhub** `/stock/profile2?symbol=AAPL` → `finnhubIndustry`(자체 ~40 산업). 무료 60 req/min. 무료티어 라이선스: 개인. ISIN/CUSIP 일부 제공. **국내 커버리지는 확인 필요.**
- **FMP** `/api/v3/profile/AAPL` → `sector`,`industry`(GICS식). 무료 한도 축소 경향(최근 250/day). 국내 커버 빈약.
- 둘 다 REST·순수코드 OK. **키 발급 후 실측 권장**.

---

## 2. 국내 주식

### 2-A. KIS OpenAPI 종목정보 — ⏸ 미검증, TR·필드 정리
- **(a) 접근**: 국내주식 기본정보 TR(예: **주식기본조회 / 상품기본조회**)에 산업분류 필드가 있음.
  대표 후보: `std_idst_clsf_cd`(표준산업분류=KSIC), `idx_bztp_lcls_cd / _mcls / _scls`(업종 대/중/소분류).
- **(b) 무료/한도**: 보유 계좌 기반 무료, TR별 유량제한.
- **(c) 라이선스**: 본인 계좌 데이터 활용. 분류는 KSIC/KRX 업종(상표 이슈 적음).
- **(e) 순수 코드 수집**: ✅ REST(이미 프로젝트에 토큰·호출 코드 존재 `verify/yhr/kis_rest/balance.py`).
- **(f) 식별자**: 6자리 종목코드.
- ⚠️ **확인 필요**: 실계좌가 **퇴직연금**이라 일부 일반 TR 차단됨([메모](../../../../.claude/projects/-Users-yhr-Dev-workspace-personal-stock-project/memory/kis-account-is-pension.md)). 기본정보 TR이 연금계좌에서도 열리는지, 정확한 TR ID/필드명은 **라이브 호출로 확인 필요**.

### 2-B. Naver 금융 업종 — ✅ 실측, **국내 1차 후보**
- **(a) 접근**: 목록 `finance.naver.com/sise/sise_group.naver?type=upjong`(79개 업종) →
  상세 `…/sise_group_detail.naver?type=upjong&no={코드}` → 종목별 **6자리 코드+종목명** 파싱.
- **(b) 무료/한도**: 무료. 명시 한도 없음(과도 호출 자제).
- **(c) 라이선스**: ⚠️ 비공식 스크래핑(회색지대). 개인/내부 분석 관행. 표시 분류는 **WICS 계열**(전기제품/생명과학도구및서비스 등 WICS식 명칭).
- **(d) 체계**: WICS식 79개 업종(GICS 한국판에 가까움, 세분도 높음).
- **(e) 순수 코드 수집**: ✅ EUC-KR HTML, **JS 게이트 없음**(KRX와 대조적).
- **(f) 식별자**: 6자리 종목코드. **국내 종목코드로 바로 조인**.
- **메모**: 방향이 "업종→종목 리스트"라 역인덱스(종목→업종)로 뒤집어 테이블화. KOSPI+KOSDAQ 모두 포함.

### 2-C. FnGuide WICS — ⏸ 미검증, 참고
- **(d) 체계**: **WICS**(WISE Industry Classification Standard, FnGuide·WISEfn). 한국 시장 사실상 표준, GICS 호환 구조.
- **(c) 라이선스**: ⚠️ **FnGuide 독점**. 무료 재배포 부적합 → 직접 데이터 소싱보다 **Naver(2-B)가 WICS를 노출**하는 경로로 우회.
- comp.fnguide.com 등은 봇/JS 가능성 → **확인 필요**.

### 2-D. data.go.kr 금융위_KRX상장종목정보 — ✅ 엔드포인트 생존, 업종필드 확인 필요
- **(a) 접근**: `apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo?serviceKey=…&resultType=json`.
- **(b) 무료/한도**: data.go.kr 무료 serviceKey(일/트래픽 제한). 엔드포인트 401로 생존 확인.
- **(c) 라이선스**: ✅ **공공데이터(클린)**. 재배포 비교적 자유(이용허락범위 확인).
- **(e) 순수 코드 수집**: ✅ REST(JSON/XML), JS 게이트 없음.
- **(f) 식별자**: 단축코드(6자리)·**ISIN**(`isinCd`)·법인등록번호(`crno`) → **ISIN 조인 가능**이 강점.
- ⚠️ **확인 필요**: 이 서비스의 기본 응답에 **업종/섹터 컬럼이 포함되는지 불확실**(시장구분 `mrktCtg`는 있으나 업종은 없을 수 있음). 업종이 없으면 금융위 **기업기본정보(CorpOutline) 서비스**의 업종 필드를 병행해야 할 수 있음 → 키 발급 후 실측 필요.

### 2-E. KRX(KIND / data.krx) 업종분류 — ❌ 직접 수집 차단
- **(e)**: 기존 [ETF 문서](etf-constituent-data-sources.md) §0에서 확정 — **`agent.js` JS 게이트로 requests/curl 불가**. data.go.kr(2-D) 또는 Naver(2-B)로 우회 권장.

### 2-F. KSIC(통계청 한국표준산업분류) — 공공도메인 대안(SIC의 국내판)
- SIC/NAICS의 한국 대응. **공공도메인**이라 라이선스 클린하나, 투자자용 "섹터"와 거리가 있어(산업 행정분류) **롤업 매핑 필요**. KIS의 `std_idst_clsf_cd`(§2-A)가 이 코드. 1차보다는 보조/검증용.

---

## 3. 결론 — 1차 채택안

### 미국 🇺🇸
- **1차: yfinance(`sector`/`industry`)**. 이유: 무료·순수코드·**미국+국내 동시 커버**·ETF 외 거의 전 종목. 분류도 Yahoo 자체라 **GICS 상표 회피**. 한계는 비공식 ToS(개인 분석 한정)와 ETF 미커버.
- **라이선스 완전 클린이 필수면: SEC EDGAR SIC**(공공도메인). 단 SIC→섹터 롤업 매핑을 직접 만들어야 함.
- **보조: Alpha Vantage ETF_PROFILE**(ETF 섹터 비중 직접) + **SPDR 11종 ETF 멤버십**(S&P500 GICS 섹터, CUSIP 조인). yfinance 결측·ETF 보완용.

### 국내 🇰🇷
- **1차: Naver 금융 업종**(§2-B). 이유: **무료·순수 curl·JS 게이트 없음**(KRX와 정반대), 6자리 코드로 바로 조인, WICS식 79업종으로 세분도 충분, KOSPI+KOSDAQ 전체. 한계는 비공식 스크래핑(개인/내부용).
- **라이선스 클린 우선이면: data.go.kr KRX상장종목정보**(공공데이터, ISIN 조인) — **단 업종 필드 유무 실측 확정 후**(§2-D 확인 필요).
- **보조/교차검증: KIS 종목정보 TR**(연금계좌 접근성 확인 후), **yfinance**(`.KS`/`.KQ`, 영문 섹터로 미국과 체계 통일 가능).

### 실무 팁 — 체계 통일
미국 yfinance(Yahoo 11섹터)와 국내 Naver(WICS 79업종)는 **분류 체계가 달라** 섹터 비중을 한 표에서 비교하려면 **공통 11 섹터로의 매핑 테이블**이 필요. 국내도 **yfinance `.KS/.KQ`로 받으면 Yahoo 11섹터로 통일** 가능(커버리지·정확도는 실측 검증 권장).

---

## 4. 확인 필요 항목 (직접 검증 못 함)

1. **KIS 종목정보 TR**: 정확한 TR ID/필드명(`std_idst_clsf_cd` 등)과 **퇴직연금 실계좌에서 호출 가능 여부**. (env 미설정으로 미검증)
2. **data.go.kr KRX상장종목정보**: 기본 응답에 **업종/섹터 컬럼 존재 여부**. 없으면 금융위 기업기본정보(CorpOutline) 병행 필요. (무료키 발급 후 실측)
3. **Finnhub / FMP**: 무료티어 정확한 한도(변동 잦음)와 **국내 종목 섹터 커버리지**. (API키 필요로 미검증)
4. **yfinance 국내 커버리지·정확도**: 소형주/스팩/우선주에서 sector 결측·오분류 빈도. (샘플 몇 종목만 확인)
5. **FnGuide WICS 직접 소싱 경로**의 봇/JS 차단 여부 및 라이선스 범위.
6. **SIC→투자자섹터, WICS↔GICS, Yahoo섹터↔GICS** 매핑 테이블의 정확한 대응(공개 크로스워크 존재 여부).
7. **라이선스 판단**은 일반 공개정보 기반 추정 — 상용/재배포 시 각 출처 약관 재확인 필요.

---

### 부록 — 실행한 검증 명령 요약
```bash
# SEC (공공도메인, curl OK)
curl -s -A "you@email" https://www.sec.gov/files/company_tickers.json
curl -s -A "you@email" https://data.sec.gov/submissions/CIK0000320193.json   # sic, sicDescription

# Alpha Vantage (demo key)
curl -s "https://www.alphavantage.co/query?function=OVERVIEW&symbol=IBM&apikey=demo"
curl -s "https://www.alphavantage.co/query?function=ETF_PROFILE&symbol=QQQ&apikey=demo"

# SPDR 섹터 ETF (curl -L 필요)
curl -sL ".../etfs/us/holdings-daily-us-en-xlk.xlsx" -o xlk.xlsx

# Naver 업종 (EUC-KR, JS 게이트 없음)
curl -s "https://finance.naver.com/sise/sise_group.naver?type=upjong"
curl -s "https://finance.naver.com/sise/sise_group_detail.naver?type=upjong&no=283"

# yfinance (미국+국내)
python -c "import yfinance as yf; print(yf.Ticker('005930.KS').info['sector'])"
```
