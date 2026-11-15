# 국내 증권사 계좌 통합 도구 조사

본 문서는 **여러 국내 증권사 계좌(보유 종목에 미국 상장 포함)를 하나로 통합 관리**하는 도구를 정리한 자료다.

- 작성/조회 시점: **2026-06-28**. GitHub Star·Fork·Commit·릴리스 수치는 이 시점 기준이며 계속 변동한다.
- **검증 기준**: 모든 사실은 각 저장소의 GitHub README 또는 공식 페이지(앱 스토어/증권사 포털)를 **직접 확인**해 작성했다. 직접 확인되지 않은 항목은 본문에 넣지 않고 맨 아래 "확인 필요 항목"으로 분리했다.

## 통합의 두 갈래 (구조 이해)

국내 증권사 계좌 통합에는 두 가지 접근이 있다.

1. **마이데이터 통합 앱 (노코드)** — 여러 증권사를 한 번에 자동 취합. 빠르지만 분석 깊이·커스터마이징은 앱이 주는 범위로 고정.
2. **증권사 Open API + 오픈소스로 직접 구축** — 통제·분석·자동화가 자유롭다. 단, **증권사 Open API는 "그 증권사의 내 계좌"만 접근**하며, 증권사마다 API 키를 따로 발급받아 합쳐야 한다.

공개 개인용 Open API가 없는 증권사 계좌가 섞여 있으면, 그 부분만 1번(마이데이터)으로 메우는 하이브리드가 현실적이다.

---

## A. Claude 생태계 (MCP · 플러그인)

대화형으로 잔고·보유종목을 질의하거나 전략·백테스트를 자연어로 다루는 경로. 국내 계좌 관점에서는 한국투자증권(KIS) 관련 도구가 직접 해당한다.

| 항목 | 제공처 | 형태 | 핵심 | Star / Fork |
|---|---|---|---|---|
| **koreainvestment/open-trading-api** | 한국투자증권(공식) | 샘플코드 + 전략빌더 + 백테스터 + MCP | KIS Code Assistant MCP(API 사용법·샘플 검색) + KIS Trading MCP(API 직접 호출). 국내·해외 주식, 채권, 선물옵션 등 | 1.4k / 726 |
| **koreainvestment/kis-ai-extensions** | 한국투자증권(공식) | 멀티 에이전트 플러그인 (npm `@koreainvestment/kis-quant-plugin`) | Claude Code·Cursor·Codex·Gemini 지원. 5개 스킬(kis-strategy-builder, kis-backtester, kis-order-executor, kis-team, kis-cs) + MCP 서버 + 보안 훅(secret-guard, prod-guard 등) | 11 / 2 |

**검증 메모**: 두 저장소 모두 README 직접 확인. open-trading-api는 KIS 단일 계좌 기준이며, 다증권사 통합 기능은 제공하지 않는다(통합은 아래 D의 게이트웨이에서 처리하고 그 위에 얇은 인터페이스를 붙이는 구조가 현실적).

---

## B. 마이데이터 통합 앱 (노코드)

여러 국내 증권사를 자동 취합해 종목·비중·수익률을 통합해 보는 앱. 아래는 **각 앱의 공식 스토어/공식 페이지 설명 기준**이다(벤더 자체 설명).

| 앱 | 국내 증권사 통합 (공식 설명) | 특징 |
|---|---|---|
| **증권플러스 (두나무)** | 11개 주요 증권사 통합 거래/관리 — 키움·미래에셋·삼성·NH투자·KB·신한투자·대신(크레온)·한화투자·IBK투자·유진투자·유안타 | 여러 증권사에 흩어진 종목·체결 내역을 한 번에 확인. 카카오 계정 연동, 차트·테마·AI 종목진단 |
| **토스 (비바리퍼블리카)** | 예·적금·청약·증권·대출 등 "내 모든 계좌"를 한 번에 관리. 다수 은행·증권사와 공식 제휴 | 마이데이터 기반 자산 통합. 증권은 토스증권 연계. 자산관리 중심으로 종목 단위 분석은 얕은 편 |
| **더리치 (The Rich)** | 키움·삼성·미래에셋·한국투자·나무·KB 등 20여 곳 증권사 연동 + 거래소 연동 | 여러 포트폴리오 생성 + 모아보기, 섹터 편집, S&P500 비교 백테스팅. 연동 자산은 미국 상장 종목 포함 |
| **도미노 (Domino)** | 국내·해외주식·펀드·부동산·외환 통합 (마이데이터 + 수동 입력) | 종목 간 비중 확인, 기간별 배당, 나스닥 실시간 시세 제공 |
| **뱅크샐러드** | 다양한 금융기관 연동, 일부 증권사 주식 연동 | 계좌·카드·투자 통합 자산관리. 국내·해외주식 수익 통합 뷰. 투자 분석 깊이는 얕은 편 |

**검증 메모**: 위 5개는 App Store / Google Play / 공식 페이지 설명을 직접 확인했다. 단, 이 설명들은 **벤더 자체 기재 내용**이며, 지원 증권사 범위·시세 정확도·연동 방식(자동연동/스크린샷 등)은 정책·법규 변화로 수시로 바뀌므로 **사용 전 각 앱에서 직접 확인**이 필요하다.

---

## C. 국내 증권사 Open API (직접 호출용 데이터 소스)

직접 구축(D) 시 데이터를 끌어오는 원천. 개인 고객이 본인 계좌를 다룰 수 있는 API를 **방식별로** 정리했다. 아래는 모두 공식 페이지 또는 동작 가능 어댑터로 직접 확인한 것이다.

| 증권사 | 개인용 API 방식 | 플랫폼 | 확인 출처 |
|---|---|---|---|
| **한국투자증권 (KIS)** | REST + WebSocket | 크로스플랫폼 | KIS 공식 포털. 개인 고객은 **본인 자산 투자 목적에 한해** 이용, 제3자 제공 불가. 국내주식·해외주식·국내선물옵션·해외선물옵션·장내채권 제공 |
| **키움증권** | REST(신규) + OpenAPI+(구형 OCX) | REST는 크로스, OCX는 Windows | 키움 REST API 공식 포털 및 Open API+(OCX) 공식 안내 페이지 |
| **LS증권** | REST | 크로스플랫폼 | krsec(아래 D)의 LS REST 어댑터가 문서화된 REST TR 스냅샷 기반으로 동작 |
| **토스증권** | REST | 크로스플랫폼 | krsec의 Toss 어댑터가 Toss 공식 OpenAPI JSON 스냅샷 기반으로 동작 |
| **NH투자증권 (나무)** | QV Open API — 연결모듈로 시세/잔고/주문 연동 | **Windows 32bit DLL(C++)** | NH투자증권(나무증권) 공식 Open API 안내 페이지. 계좌 개설 + HTS ID 등록 후 가입 |

**개인 매매용으로 보기 어려운 경우 (공식 확인)**

| 증권사 | 형태 | 확인 출처 |
|---|---|---|
| **신한투자증권** | Open API가 **B2B 제휴형**(1:1 제휴문의 → 이용기관 등록 → 서비스 개시). 개인 자가서비스 매매 API로 보기 어려움 | 신한 Open API 공식 포털 |
| **KB증권 (KB금융그룹)** | 오픈API가 **그룹·외부기업 공개형(B2B)** — 계열사 정보·서비스를 외부 기업에 공개하는 개방형 서비스 | KB금융그룹 오픈API 공식 문서 |

**검증 메모**: REST 기반으로 크로스플랫폼 직접 통합이 현실적인 곳은 **한투·키움·LS·토스**다. NH는 개인용 API가 있으나 Windows DLL 방식이라 통합 파이프라인 구성 난이도가 높다. 신한·KB는 개인 매매용 자가서비스가 아니라 기관/제휴용이다. 삼성·미래에셋 개인용 공개 API, 대신증권 크레온 API 기술 사양은 공식 1차 출처로 확정하지 못했다(아래 "확인 필요 항목").

---

## D. 오픈소스 래퍼 · 통합 게이트웨이 (직접 구축)

증권사 API를 코드로 감싸 통합하는 도구. 모두 GitHub README를 직접 확인했다.

| 도구 | 대상 증권사 | 언어 / 라이선스 | 다계좌·통합 관련 | Star / Fork | 활성도 |
|---|---|---|---|---|---|
| **smallfish06/krsec** | 한투·키움·LS·토스 | Go / Apache-2.0 | **다증권사 통합 게이트웨이**. 증권사별 인증·파라미터·응답을 단일 `broker.Broker` 인터페이스로 통일. `GET /accounts/summary`(멀티계좌 통합 잔고), `/accounts/{id}/balance`·`/positions` 공통화. 미국 해외주식 시세·조회 포함 | 3 / 0 | 85 commits, 32 릴리스, 최신 v0.18.0(2026-06) |
| **Soju06/python-kis (PyKis)** | 한국투자증권 | Python / MIT | 한투 국내·해외를 동일 인터페이스로. `account.balance()`가 `KisIntegrationBalance`로 국내+해외 보유·예수금 통합 반환. 전면 타입힌트, 복구형 웹소켓 | 281 / 90 | 304 commits, 13 릴리스, 최신 v2.1.6(2025-10) |
| **elbakramer/koapy (KOAPY)** | 키움증권 | Python / MIT·Apache-2.0·GPL-3.0 중 택1 | 키움 OpenAPI+(OCX)를 gRPC 서버-클라이언트로 감싸 32bit 제약 우회. 잔고·예수금·평가(`GetAccountEvaluationStatusAsSeriesAndDataFrame`, `GetDepositInfo`) 제공. PyPI 배포(`pip install koapy`) | 222 / 77 | 406 commits. README에 **"알파 단계, 충분히 테스트되지 않음, 구조 급변 가능"** 명시 |
| **sharebook-kr/pykiwoom** | 키움증권 | Python / MIT | 키움 OpenAPI+(OCX) 래퍼. `GetLoginInfo("ACCNO")`로 전체 계좌 리스트 조회. 의존성 pandas·pyqt5·pywin32(**Windows 전용**) | 112 / 58 | setup.py 기준 v0.1.5 |
| **sharebook-kr/mojito (mojito2)** | 한국투자증권 | Python / MIT | "대한민국 증권사 통합 래퍼"를 표방하나 **README의 구현·예제는 현재 한투(`KoreaInvestment`) 중심**. `fetch_balance()` 잔고 조회, 미국주식 주문(`exchange="NASD"`) | 91 / 44 | 92 commits, 릴리스 게시 없음 |

**검증 메모**: 표의 모든 수치·기능·라이선스는 각 README 직접 확인 결과다. mojito는 명칭상 "통합"이지만 README 기준 실제 지원은 한투 중심이라는 점을 명시한다. 다증권사 통합이 목적이면 **krsec**가 설계상 가장 부합하고(한투·키움·LS·토스), 한투 단일이면 python-kis가 잔고 통합·문서화 면에서 강하다.

---

## 주의점 및 제약사항

- **Open API의 접근 범위**: 증권사 Open API는 원칙적으로 **본인의 해당 증권사 계좌**만 조회·거래할 수 있다(예: KIS는 개인 고객 본인 자산 투자 목적에 한정, 제3자 제공 불가). N개 증권사 통합은 N개 증권사에서 각각 API 사용 신청·키 발급 후 코드로 병합해야 한다.
- **호출 제한(Rate limit)**: 증권사 API에는 초당/시간당 호출 제한이 있다. KIS 공식 포털도 초당 호출 제한 관련 공지를 게시한 바 있으므로, 다계좌·다종목을 주기적으로 조회하려면 호출 빈도·직렬화·캐싱을 설계해야 한다. (증권사별 구체 수치는 각 공식 가이드에서 직접 확인 필요)
- **플랫폼 제약**: 키움 OpenAPI+(OCX) 계열(pykiwoom, koapy)과 NH QV Open API(32bit DLL/C++)는 Windows 환경 의존성이 있다. REST 계열(KIS·LS·토스, krsec, python-kis)은 리눅스/맥에서도 동작한다.
- **성숙도 차이**: koapy는 README에 알파 단계임을 명시한다. krsec는 활발히 릴리스되나 Star 수가 적은 신생 프로젝트다. 실거래 적용 전 **모의투자 계좌로 충분히 검증**해야 한다.
- **자격증명 보안**: API Key·App Secret·토큰은 코드·로그·저장소에 노출하면 안 된다. 환경변수/별도 시크릿 파일로 분리하고, 키 입력은 사용자가 직접 처리해야 한다(제3자나 도구가 대신 입력하지 않도록).
- **마이데이터 앱의 변동성**: B의 앱들은 지원 증권사 범위, 연동 방식(자동/스크린샷), 해외주식 시세 정확도가 정책·법규 변화로 자주 바뀐다. 실제 매매 판단 전 증권사 정식 앱과 교차 확인이 안전하다.
- **자동 연동 도구의 프라이버시**: 일부 통합 서비스는 제3자 데이터 수집기에 로그인/금융정보를 공유하는 구조일 수 있다. 프라이버시가 중요하면 직접 구축(D) 또는 명세서 임포트형을 우선 고려한다.
- **면책**: 본 문서는 도구 조사 자료이며 투자 자문이 아니다. 모든 매매 판단과 책임은 사용자 본인에게 있다.

---

## 확인 필요 항목 (본 조사에서 1차 출처로 확정하지 못함)

아래는 존재가 거론되나 공식 1차 출처로 확정하지 못해 본문에서 단정하지 않은 항목이다. 사용 전 직접 확인이 필요하다.

- **삼성증권·미래에셋증권의 개인용 공개 Open API 제공 여부**: 공식 개발자 포털을 통한 개인 자가서비스 API를 1차 출처로 확인하지 못함.
- **대신증권 CYBOS Plus(크레온) API의 기술 사양·플랫폼**: 제품(크레온)의 존재는 증권플러스 연동 목록 등에서 확인되나, COM 기반·Windows 전용 등 구체 사양은 대신증권 공식 페이지로 확정하지 못함.
- **핀트(FINT)·세이브로(SEIBro, 한국예탁결제원) 등의 다증권사 통합 조회 기능**: 공식 페이지로 기능·지원 범위를 확정하지 못함.
- **한투 REST API의 "국내 최초/출시 시점" 등 연혁성 주장**: 2차 자료에만 근거(대신증권이 COM 기반 OpenAPI를 먼저 제공했다는 서술과 혼재). 단일 1차 출처로 확정 못함.

---

## 레퍼런스 (직접 확인한 페이지)

- KIS Developers 포털 — https://apiportal.koreainvestment.com/intro
- KIS Open API 서비스 소개 — https://apiportal.koreainvestment.com/about-open-api
- koreainvestment/open-trading-api — https://github.com/koreainvestment/open-trading-api
- koreainvestment/kis-ai-extensions — https://github.com/koreainvestment/kis-ai-extensions
- 키움 REST API 포털 — https://openapi.kiwoom.com/
- 키움 Open API+ 안내 — https://www.kiwoom.com/h/customer/download/VOpenApiInfoView
- NH투자증권(나무) QV Open API 안내 — https://www.mynamuh.com/WMDoc.action?viewPage=%2FguestGuide%2Ftrading%2FopenAPI.jsp
- 신한 Open API 포털 — https://openapi.shinhan.com/
- smallfish06/krsec — https://github.com/smallfish06/krsec
- Soju06/python-kis — https://github.com/Soju06/python-kis
- elbakramer/koapy — https://github.com/elbakramer/koapy
- sharebook-kr/pykiwoom — https://github.com/sharebook-kr/pykiwoom
- sharebook-kr/mojito — https://github.com/sharebook-kr/mojito
- 증권플러스 (Google Play) — https://play.google.com/store/apps/details?id=com.dunamu.stockplus
- 토스 (Google Play) — https://play.google.com/store/apps/details?id=viva.republica.toss
- 더리치 (App Store) — https://apps.apple.com/kr/app/id1462844342
- 더리치 (Google Play) — https://play.google.com/store/apps/details?id=io.therich.app
- 도미노 (Google Play) — https://play.google.com/store/apps/details?id=com.favv.neo
