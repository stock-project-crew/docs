# 용어표

새 설계서 · ADR · 테스트 문서 · 코드 주석이 쓰는 말이다. 개념 하나에 낱말 하나를 쓴다.

- **쓸 말**: 문서와 주석에 쓰는 말. 화면 문구가 다르면 비고에 적는다.
- **쓰지 않을 말**: 같은 뜻으로 쓰지 않는다. 다른 뜻이면 쓸 수 있다.
- **코드 이름**: 클래스 · enum · 컬럼 · API 필드. 바꾸지 않는다. 문서에서 코드를 가리킬 때는 그대로 쓴다.
- 정의는 지금 코드의 동작이다.
- 11/15 사용자 확정. E2에서 설계서의 용어 절로 옮기고, E5에서 주석 · 테스트 이름 · 아래 화면 문구에 반영한다.

## 2. 공통 · 인증

### G1. 기준일 · as_of
- 쓸 말: **기준일**(날짜) · **데이터 시점**(알림의 시각 값)
- 쓰지 않을 말: 기준 시각(배너 표시 시각만 예외)
- 코드 이름: `position_line.as_of`(date), `alert_event.as_of`(timestamptz), `source_as_of`, `price_as_of`, `fx_as_of`, `evaluated_as_of`
- 정의: 그 값이 어느 날(또는 어느 시각)의 데이터로 계산됐는지를 가리키는 날짜다.
- 비고: `as_of`가 표마다 타입이 다르다(보유 라인은 KR 영업일 date, 알림 발화는 timestamptz). "기준"은 "취득원가 기준", "구성종목 기준으로 보기", "묶음 기준"(축), "기준값"(조건 오른쪽)처럼 '잣대'라는 뜻으로도 화면에 나온다.

### G2. 화면 · 뷰 · 탭
- 쓸 말: **화면** (탭은 하단 탭 막대를 가리킬 때만)
- 쓰지 않을 말: 뷰
- 코드 이름: `ViewKey`(SUMMARY · POSITIONS · ALLOCATION · ACCOUNTS · REALIZED_PNL · ASSET_CHANGE), `ScreenKey`(앱)
- 정의: 앱에서 한 번에 보이는 한 페이지다. 서버는 화면마다 응답 하나(`ViewKey`)를 준다.

### G3. 거래일 · 영업일
- 쓸 말: **거래일**
- 쓰지 않을 말: 영업일. 가동일은 데이터 DAG 일정에만 쓴다.
- 코드 이름: `dim_market_calendar.is_trading_day`, `CalendarDay.isTradingDay()`, `next_trading_day`
- 정의: 시장 캘린더에서 장이 열린 날(`is_trading_day`)이다.
- 비고: 알림 기간의 "일"은 시장 거래일이 아니라 그 종목이 실제로 거래된 날(거래정지일 제외)이라 뜻이 하나 더 있다(`screens/alerts/AlertDetailScreen.tsx:137`).

### G4. 갱신 · 새로고침 · refresh
- 쓸 말: ① **인증 정보 갱신** ② **토큰 갱신** ③ **새로고침**(화면 조회만) — 수동 수집 요청은 D2 **동기화**
- 쓰지 않을 말: 수집 요청을 뜻하는 "새로고침"

### G5. 인증
- 쓸 말: 앱 계정은 **로그인**, 증권사 키 거절은 **인증 실패**
- 쓰지 않을 말: 로그인을 뜻하는 "인증"
- 코드 이름: `auth` 패키지(로그인 · JWT) / `failure_reason = AUTH_FAILED`, `NoticeCode.CREDENTIAL_INVALID`(증권사 키)
- 정의: 인증 실패는 데이터 쪽 수집이 앱키 · 앱 시크릿 거절로 끝난 상태다. 로그인과는 무관하다.

### G6. 평가
- 쓸 말: 단어를 바꾸지 않되 늘 붙여 쓴다 — **평가금액 · 평가손익**(밸류), **평가 · 평가 시점**(알림). 단독 "평가"는 알림에만 쓴다
- 코드 이름: `market_value_*`, `unrealized_pnl_*` / `evaluate`, `EvaluationRunner`, `evaluated_as_of`, `cadence`
- 정의: 밸류 쪽은 종가로 매긴 값, 알림 쪽은 조건의 참 · 거짓을 계산하는 일이다.

### G7. 확정
- 쓸 말: ①은 **확정**, ②는 **실현손익**(P7), ③은 **확정된 일봉**처럼 대상을 붙인다

### G8. UNAVAILABLE
- 쓸 말: 문서에서는 영어 값을 개념어로 쓰지 않는다. 코드 이름으로만 남기고 뜻은 각 개념어(미포함 · 확보 안 됨 · 미분해 …)로 쓴다

### G9. 데이터팀 테이블 · 원천 · 미러
- 쓸 말: 운영 표는 **데이터팀 표**, 로컬 · 테스트 복제는 **미러**
- 쓰지 않을 말: 운영 표를 가리키는 "미러"
- 코드 이름: `data.` 스키마(`cln_balance` · `cln_trade` · `collection_run` …), `db/external/V*__*_mirror.sql`
- 정의: 미러는 데이터팀 소유 표를 로컬 · 테스트에서만 만드는 복제이고, 운영 프로필은 적용하지 않는다.

### G10. 종목 · 종목 마스터 · instrument
- 쓸 말: 대상은 **종목**, 표는 **종목 마스터**(`data.instrument`)
- 쓰지 않을 말: 화면 · 문서 본문의 "instrument"
- 정의: 종목 마스터는 데이터팀이 주는 종목 목록이고, 라인 · 알림은 `instrument_id`로 이 표를 가리킨다.

## 3. 포트폴리오

### P1. 라인 (보유 라인)
- 쓸 말: **라인**
- 쓰지 않을 말: 보유 행
- 코드 이름: `position_line`, `Line`, `LineCalculator`, `PositionLineInvariants`
- 정의: 계좌 × 종목 × 기준일 한 칸의 보유 수량 · 매입금액 · 평가금액 행이다. 예수금도 `CASH` 종목 라인 하나로 담는다.

### P2. 잔고 · 보유 스냅샷
- 쓸 말: 사용자 문장 · 문서 본문은 **잔고**(그 계좌의 그날 보유 상태). 백엔드가 만든 날짜별 라인 묶음은 **보유 스냅샷**
- 쓰지 않을 말: 스냅샷(단독)
- 코드 이름: 원천 `data.cln_balance` · `cln_deposit`; 백엔드 `position_line`의 한 날짜 묶음, `snapshot_run`; API `first_balance_on` · `last_balance_on`
- 정의: 잔고는 한 계좌의 한 날짜 보유 수량 · 예수금이다.
- 비고: "잔고"가 데이터팀 원천 행(`cln_balance`)과 백엔드가 만든 라인 날짜를 둘 다 가리킨다. 평단(P4)도 원천 잔고 기준이다.

### P3. 포지션
- 쓸 말: 보유 시작부터 전량 매도까지는 **포지션 구간**. `positions` 화면은 UI대로 **종목** 화면
- 쓰지 않을 말: 종목 화면을 뜻하는 "포지션"
- 코드 이름: `position_basis`, `position_closed` / `ViewKey.POSITIONS`, `/positions`, `PositionsScreen`, `PositionRow`
- 정의: 포지션 구간은 수량이 0에서 늘어난 때부터 다시 0이 될 때까지이고, 평단 신뢰 등급은 지금 열린 구간마다 매긴다.

### P4. 평단
- 쓸 말: **평단**
- 쓰지 않을 말: 평균단가, 평균 매입가
- 코드 이름: `avg_cost`, `MetricKey.AVG_COST`("평단")
- 정의: 잔고 기준 Σ매입금액 ÷ Σ수량이다(`catalog/Metric.java:27`). 체결로 계산한 취득원가(P6)와 다를 수 있다.

### P5. 매입금액 · 원가
- 쓸 말: **매입금액**
- 쓰지 않을 말: 원가(이 뜻으로)
- 코드 이름: `cost_amount_local` · `cost_amount_krw`, `MetricKey.COST_AMOUNT_KRW`("매입금액")
- 정의: 증권사 잔고가 준 매입금액이며, 평가손익 = 평가금액 − 매입금액이다.
- 비고: "원가"가 코드 주석에서는 매입금액을, 화면에서는 취득원가(P6)를 가리킨다.

### P6. 취득원가
- 쓸 말: **취득원가**
- 쓰지 않을 말: 원가(단독)
- 코드 이름: `cost_basis_local` · `cost_basis_krw`, `realized_pnl_line`, `BasisCalculator`
- 정의: 체결 이력으로 매도 한 건에 배분한 매입 비용이며, 정하지 못하면 비어 있고 그 매도는 실현손익 합계에서 빠진다(P17).

### P7. 실현손익
- 쓸 말: **실현손익**
- 쓰지 않을 말: 확정 손익, 확정한 손익(투자손익 내역의 "확정" 줄 이름은 P9)
- 코드 이름: `realized_pnl_line`, `realized_pnl_krw`, `MetricKey.REALIZED_PNL_KRW`("실현손익"), `ViewKey.REALIZED_PNL`
- 정의: 기간 안 매도 체결마다 매도금액 − 취득원가 − 수수료·세금을 더한 값이며, 체결일로 기간에 넣는다.

### P8. 평가손익
- 쓸 말: **평가손익**
- 쓰지 않을 말: 미실현손익
- 코드 이름: `unrealized_pnl_krw` · `unrealized_pnl_pct`, 알림 지표 `UNREALIZED_PNL_PCT`("평가손익률")
- 정의: 그날 평가금액 − 매입금액(예수금 제외)이다.

### P9. 투자손익 내역의 확정 · 평가
- 쓸 말: 화면 문구대로 **확정 · 평가**로 쓰되 문서에서는 늘 "투자손익의 확정 · 평가"로 묶어 쓴다
- 쓰지 않을 말: 미실현(단독)
- 정의: 투자손익을 매도로 생긴 몫(확정 = 그 기간 실현손익)과 나머지(평가 = 투자손익 − 확정)로 나눈 것이다.
- 비고: 여기의 "평가"는 평가손익 자체가 아니라 기간 동안의 변화분이라, 같은 화면의 평가손익과 숫자가 다르다. 코드 이름 `unrealized`도 평가손익(P8)과 같은 말이다.

### P10. 투자손익
- 쓸 말: **투자손익**
- 쓰지 않을 말: 투자 손익(띄어쓰기)
- 코드 이름: `INVESTMENT_PNL`, `investmentPnl`(`view/AssetChangeViewService.java:123`)
- 정의: 기말자산 − 기초자산 − 넣은 돈 − 배당 + 수수료·세금 − 계좌 편입 + 계좌 제외다. 스펙 l.333과 코드가 일치한다.

### P11. 번 돈
- 쓸 말: **번 돈**
- 코드 이름: `AssetChangeData.earned`
- 정의: 투자손익 + 배당 − 수수료·세금이다(`view/AssetChangeViewService.java:129`).
- 비고: 같은 서비스의 클래스 Javadoc은 "투자로 번 돈을 따로 세지 않고 나머지 전부로 정의한다"(l.45)라며 "번 돈"을 투자손익 뜻으로 쓴다.

### P12. 넣은 돈
- 쓸 말: **넣은 돈**
- 쓰지 않을 말: 순입금, 순유입
- 코드 이름: `AssetChangeData.deposited`
- 정의: 두 잔고 사이 `(기초 기준일, 기말 기준일]`에 사용자가 입력한 입금 − 출금이다.

### P13. 입출금 · 현금흐름 · cashflow
- 쓸 말: 사용자 입력은 **입출금**, 배당 · 수수료 · 세금은 **배당 · 수수료 · 세금**(묶어 부를 때 **손익성 현금흐름**). 현금흐름은 둘을 아우를 때만
- 쓰지 않을 말: 수동 입출금
- 코드 이름: 사용자 입력 `manual_cashflow`, `ManualCashflowService`, `CashflowType`(DEPOSIT · WITHDRAW) / 데이터팀 `data.cln_cashflow`, `EarningsCashflowType`(DIVIDEND · FEE · TAX), `CASHFLOW_UNCOVERED`
- 정의: 입출금은 사용자가 앱에서 입력한 입금 · 출금 기록이고, 배당 · 수수료 · 세금은 데이터팀이 주며 입출금은 그 표에 들어오지 않는다.
- 비고: 코드 이름 `cashflow`가 두 원천을 모두 가리킨다(`CashflowController`는 입출금, `EarningsCashflowMapper`는 배당 · 수수료 · 세금).

### P14. 기초자산 · 기말자산
- 쓸 말: **기초자산 · 기말자산**
- 쓰지 않을 말: 시작 자산, 기간 말 자산
- 정의: 기초는 `from` 전날까지의 가장 늦은 잔고(없으면 기간 안 첫 잔고), 기말은 `to` 이하 가장 늦은 잔고의 총자산이다.

### P15. 총자산
- 쓸 말: 
- 정의: 예수금을 포함한 평가금액 합계다(`catalog/Metric.java:18`).

### P16. 계좌 편입 · 계좌 제외
- 쓸 말: **계좌 편입 · 계좌 제외**
- 코드 이름: `account_included` · `account_excluded`, `boundary.included()`
- 정의: 기간 중 처음 잔고가 생긴 계좌의 첫 잔고 총자산(편입)과, 기간 중 잔고가 끊긴 계좌의 마지막 잔고 총자산(제외)이다.
- 비고: "제외"가 실현손익의 빠진 체결(P17 `EXCLUDED_ACCOUNTS`)과 지표의 예수금 제외(`CashScope.EXCLUDED`)에도 쓰인다. 이 개념에는 늘 "계좌"를 붙인다.

### P17. 미포함 (실현손익 합계에서 빠진 체결)
- 쓸 말: **미포함**
- 쓰지 않을 말: 제외(이 뜻으로), 합계에서 뺀 계좌
- 코드 이름: `NoticeCode.EXCLUDED_ACCOUNTS`, `excludedAccountCount`, `EmptyReason.ALL_UNAVAILABLE`, 원가 null 행(`Grade` UNAVAILABLE · CONFLICT)
- 정의: 취득원가를 정하지 못한 매도 체결(등급 UNAVAILABLE · CONFLICT)은 합계와 목록에서 빠지고, 그런 체결이 있는 계좌 수만 따로 센다.

### P18. 추정 · 실현손익 등급
- 쓸 말: **추정**
- 쓰지 않을 말: 시드, 시드 평단(코드 `seed_avg_price`는 코드 이름으로 둔다)
- 코드 이름: `Grade` { VERIFIED, SEEDED, UNAVAILABLE, CONFLICT }, 응답 전용 `MIXED`, `SeedReason` { LATE_COVERAGE, NOT_TRADED }, `NoticeCode.SEEDED_ROWS`
- 정의: 거래내역이 포지션 구간 시작보다 늦게 확보됐거나(LATE_COVERAGE) 매매 없이 입고된(NOT_TRADED) 수량에 잔고 평단을 취득원가로 매겨 계산한 손익이다.

### P19. 예수금 · 현금
- 쓸 말: **예수금**(계좌의 현금 잔고). 자산군 이름일 때만 **현금**
- 쓰지 않을 말: 현금보유
- 코드 이름: `deposit_krw`, `MetricKey.DEPOSIT_KRW`("예수금"), `AssetClass.CASH`, `CASH_RATIO_PCT`("현금비중"), 원천 `cln_deposit`
- 정의: 예수금은 계좌에 남은 현금이고, 라인에서는 `CASH` 종목 라인으로 담겨 총자산에 들어간다.
- 비고: "ETF 안 현금"(OTHER 그룹)은 예수금이 아니다. 코드의 `deposit`은 예수금(`deposit_krw`)과 입금(`CashflowType.DEPOSIT`, `deposited`)을 모두 가리킨다.

### P20. ETF 분해 · 렌즈 · 구성종목 기준 보기
- 쓸 말: **ETF 분해**
- 쓰지 않을 말: 렌즈, 전개, 룩스루, 구성종목 기준 보기(`lens`는 코드 이름)
- 코드 이름: `Lens` { DIRECT, LOOK_THROUGH }, 쿼리 `lens`, `LensSafety`, `LENS_METRICS_OMITTED`
- 정의: 구성종목을 아는 ETF만 구성비중대로 안에 든 종목으로 나눠 같은 종목끼리 합쳐 보이는 보기이며, 행의 평단 · 평가손익은 빠진다.
- 비고: 같은 토글이 두 화면과 서버 문구에서 이름이 셋이다.

### P21. 확보 · 커버리지 · coverage
- 쓸 말: **확보**(확보 구간)
- 쓰지 않을 말: 커버리지, 수집 창
- 코드 이름: `cln_trade_coverage`, `cln_cashflow_coverage`(COVERED · UNAVAILABLE, `covered_from`~`covered_to`), `coverage_start_at`, `etf_coverage`
- 정의: 데이터팀이 그 계좌의 거래내역 · 배당 등을 조회해 빠짐없이 갖고 있다고 보장하는 기간이다.
- 비고: coverage가 체결 이력 · 손익성 현금흐름 · ETF 구성종목 세 가지에 쓰인다.

### P22. 이월
- 쓸 말: **이월**
- 쓰지 않을 말: 캐리포워드, 직전 값, 이전 값
- 코드 이름: `is_carried_forward`, `BuildOutcome.CARRIED`, `source_as_of`, `STALE_ACCOUNTS`, `BOUNDARY_CARRIED_FORWARD`
- 정의: 그날 잔고로 라인을 만들지 못한 계좌에 직전 확정 라인을 금액 · 환율 · 원천 시각 그대로 옮겨 쓴 것이며, `source_as_of`가 원본 날짜다.
- 비고: 화면은 대부분 날짜("~ 기준")로 말하고, 자산 변화 화면의 서버 문구만 "이월값"이라는 말을 그대로 보인다.

### P23. 계좌유형 (일반 · 연금 / 위탁 · 연금저축)
- 쓸 말: 계좌유형은 **일반 · 연금**, KIS 상품은 **위탁 · 연금저축**(상품 코드 01 · 22). 둘을 섞어 쓰지 않는다
- 코드 이름: `AccountType` { GENERAL, PENSION }, `KisProduct` { BROKERAGE("01"), PENSION_SAVINGS("22") }
- 정의: 계좌유형은 기관과 무관한 분류이고(GENERAL · PENSION), 지금은 KIS 상품 01 → GENERAL, 22 → PENSION으로 하나씩 대응한다.
- 비고: 비중 화면의 레버리지 축도 레버리지가 아닌 종목을 "일반"으로 표시한다(`query/aggregate/AxisSql.java:50`). 같은 화면군에서 "일반"이 두 뜻이다.

### P24. 일간 변화 · 직전 거래일 대비
- 쓸 말: **직전 거래일 대비**
- 쓰지 않을 말: 일간 변화(카탈로그 라벨도 맞출 후보)
- 코드 이름: `daily_change_krw` · `daily_change_pct`
- 정의: 그날 총자산 − 직전 기준일 총자산이다.

### P25. 증권사 · 기관 · broker
- 쓸 말: **증권사**
- 쓰지 않을 말: 기관(이 뜻으로)
- 코드 이름: `account.broker`, `AccountLinkService.BROKER = "한국투자증권"`
- 정의: 계좌를 연 금융회사이며, 지금은 한국투자증권 하나다.

### P26. 체결 · 거래내역
- 쓸 말: 매매 한 건은 **체결**, 체결을 모은 이력은 **거래내역**. 원장은 문서의 "3원장" 설명에만 쓴다
- 비고: 알림의 "거래 없음"(`NO_TRADE`)은 그날 거래량이 없다는 뜻이라 다르다.

## 4. 알림

### A1. 알림
- 쓸 말: 규칙은 **알림**, 기기로 보내는 것은 **푸시**. 동사는 **알림 걸기**
- 쓰지 않을 말: 알림 규칙, 시그널
- 코드 이름: `alert` / `push_device`, `alert_delivery`, `ExpoPushGateway`
- 정의: 알림은 종목 하나에 건 조건 · 평가 시점 · 알림 방식 · 유효기간 묶음이다.

### A2. 울림 (울린 알림)
- 쓸 말: **울림 · 울린 알림**
- 쓰지 않을 말: 발화, 이벤트, 트리거(동사)
- 코드 이름: `alert_event`, `fired_at`, `AlertEvent*`, `Outcome.FIRED`, `last_fired_at`
- 정의: 알림의 조건이 한 데이터 시점에서 참이 되어(알림 방식 규칙에 따라) 기록과 푸시가 생긴 것이며, 알림을 지워도 기록은 남는다.

### A3. 조건
- 쓸 말: **조건**(UI대로 ①②를 모두 덮는다). 한 줄만 가리킬 때는 "조건 한 줄", 목록을 거르는 것은 **필터**
- 쓰지 않을 말: 트리거, 규칙, 필터 뜻의 "조건"(`trigger_*`는 코드 이름)
- 코드 이름: `trigger_type`(PRESET · COMPOSABLE), `trigger_spec`, `conditions[]`, `ConditionBox`
- 정의: 조건은 지표와 기준값을 연산자로 견준 식이고, 직접 조건은 최대 5개를 AND로 묶는다.

### A4. 평가 시점
- 쓸 말: **평가 시점**, 값은 **장중 · 종가**
- 쓰지 않을 말: 평가 주기, 케이던스
- 코드 이름: `Cadence` { INTRADAY("장중"), CLOSE("종가") }
- 정의: INTRADAY는 장중 시세로, CLOSE는 일별 종가로 평가한다.

### A5. 평가 · 판정 (알림)
- 쓸 말: **평가**
- 쓰지 않을 말: 판정(알림 뜻)
- 코드 이름: `EvaluationRunner`, `ConditionEvaluator`, `alert_state.evaluated_as_of`(timestamptz) / 포트폴리오 `position_basis.evaluated_as_of`(date, "판정일")
- 정의: 알림의 조건을 한 데이터 시점의 값으로 참 · 거짓 · 확인 불가 중 하나로 정하는 일이다.
- 비고: 같은 컬럼 이름 `evaluated_as_of`가 알림에서는 "마지막으로 평가한 데이터 시점", 평단 표에서는 "판정일"이다. 문서의 "판정"은 등급 판정 · 확정 판정 등에도 넓게 쓰인다.

### A6. 꺼짐 · 멈춤 · 일시중지
- 쓸 말: 사용자가 끈 것은 **꺼짐(끄기 · 다시 켜기)**, 데이터 닫힘으로 멈춘 것은 **일시중지**
- 쓰지 않을 말: 멈춤, 정지
- 코드 이름: `AlertStatus.PAUSED` / `Closure.Kind.HELD`, `held_since`
- 정의: 꺼짐은 사용자가 평가를 멈춘 상태이고, 일시중지는 필요한 시장 데이터를 제공하지 않는 동안 서버가 평가를 건너뛰는 상태다.

### A7. 알림 방식 (notify_mode)
- 쓸 말: **알림 방식**, 값은 UI대로 **돌파할 때마다 · 한 번만 · N분마다 다시**, 간격은 **다시 알림 간격**
- 쓰지 않을 말: 재무장, 쿨다운
- 코드 이름: `NotifyMode` { EDGE_REARM, ONE_SHOT, COOLDOWN }, `cooldown_min`
- 정의: EDGE_REARM은 거짓→참이 될 때마다, ONE_SHOT은 처음 한 번 울리고 끝, COOLDOWN은 참인 동안 마지막 울림의 데이터 시점부터 N분 뒤 다시 울린다.
- 비고: "돌파할 때마다"의 "돌파"는 연산자 "상향 돌파"(`CROSSES_ABOVE`)와 같은 말이라, 가격 돌파 조건이 아닌 알림에서도 "돌파"로 읽힌다.

### A8. 유지 방식 · 유지 조건 · 지속
- 쓸 말: **유지 방식**, 값은 **N일 연속 · N분 이상 유지**
- 쓰지 않을 말: 유지 조건, 지속, 수식어
- 코드 이름: `Modifier` { `Streak`, `PersistMin` }, `streak`, `persist_min`
- 정의: 조건이 종가 알림에서는 N거래일 연속, 장중 알림에서는 N분 이상 참이어야 울리게 하는 덧붙임이다.

### A9. 피연산자 · 지표 · 기준값
- 쓸 말: 왼쪽은 **지표**, 오른쪽은 **기준값**(상수 또는 비교 지표)
- 쓰지 않을 말: 피연산자, 좌변 · 우변(`operand`는 코드 이름)
- 코드 이름: `Operand`, `left` · `right`, `IndicatorKey`, `Transform`
- 정의: 조건은 왼쪽 지표를 오른쪽 기준값과 연산자로 견준다.

### A10. 확인 불가
- 쓸 말: 
- 코드 이름: `Truth.UNKNOWN`, `UnknownReason`(라벨이 서버 enum에 있고 앱 `status.ts`에 같은 문구가 중복)
- 정의: 값이 없거나 이력이 모자라 조건의 참 · 거짓을 정할 수 없는 평가 결과다.

### A11. 데이터 닫힘
- 쓸 말: 
- 코드 이름: `DataClosure`, `Closure.Kind` { AS_CLOSE, HELD }
- 정의: 데이터 쪽이 장중 시세나 외국인 · 기관 수급을 제공하지 않는 동안, 알림을 종가로 돌리거나(AS_CLOSE) 일시중지(HELD)하는 규칙이다.

## 5. 데이터 연동

### D1. 수집 (collection run)
- 쓸 말: **수집**(한 계좌의 한 번은 **수집 실행**, 매일 정해진 것은 **정기 수집**)
- 쓰지 않을 말: 자동 동기화, 싱크
- 코드 이름: `data.collection_run`(requested_by SCHEDULE · USER), `RunProcessor`, `last_collection`, `CollectionStatus`, `CollectionAlert`, `last_synced_at`
- 정의: 데이터팀 DAG가 계좌 하나의 잔고 · 예수금을 증권사에서 가져오는 한 번의 실행이며, 끝나면 백엔드가 그 결과로 라인을 만든다.
- 비고: 컬럼 `account.last_synced_at`은 이름과 달리 "DONE으로 끝난 수집 가운데 가장 늦은 종료 시각"이다. 초기 문서(2026-06-22 · 06-28)는 정기 수집을 "자동 동기화"로 쓴다.

### D2. 동기화 (sync run)
- 쓸 말: **동기화**
- 쓰지 않을 말: 싱크, 새로고침(이 뜻으로), 수동 새로고침
- 코드 이름: `sync_run`, `sync_run_account`, `SyncService`, `SyncCloser`, `POST /sync`, `SYNC_IN_PROGRESS`
- 정의: 사용자가 요청해 계좌마다 USER 수집을 넣고 그 결과를 한 묶음(sync run)으로 지켜보는 일이며, 실제 수집은 다음 가동일 밤에 일어난다.

### D3. 확정 (라인) · 잠정 · 승격
- 쓸 말: **확정 · 잠정**
- 쓰지 않을 말: final(본문에서), 마감(이 뜻으로)
- 코드 이름: `position_line.is_final`, `Finalizer`, `BuildOutcome` { BUILT, CARRIED, PROMOTED, SKIPPED }, `Finality`, `NoticeCode.ALREADY_FINAL`
- 정의: 확정 라인은 정기 수집이 쓴 라인과 확정 단계가 승격 · 이월한 라인이며, 동기화는 확정 라인이 있는 날을 다시 쓰지 않는다. 확정 전 라인은 잠정이다.
- 비고: G7의 다른 "확정"(실현손익 · 일봉)과 섞인다.

### D4. 확정 마감 · 마감
- 쓸 말: **확정 마감**. 단독 "마감"은 장 마감(시장 종료)에만 쓴다
- 코드 이름: `Finalizer.deadline`, `portfolio.snapshot.finalize-at`(기본 08:00), `BuildReason.DEADLINE`, `Finality.finalizedAt`
- 정의: 그날 라인을 더 기다리지 않고 확정하는 시각으로, 그 날 다음 KR 거래일의 `finalize-at`(기본 08:00, KST)이다.

### D5. 연동 · 등록 · 추가 · 연결
- 쓸 말: **연동**(동작 · 상태 모두), 되돌림은 **해제**
- 쓰지 않을 말: 등록, 연결, 계좌 추가(버튼 문구는 남길지 별도 결정)
- 코드 이름: `LinkState` { CONNECTING, CONNECTED, DISCONNECTED }, `LinkCommand`, `AccountLinkService`, `linked_at`, `POST /accounts`
- 정의: 사용자가 앱키 · 앱 시크릿 · 계좌번호를 넣어 계좌를 앱에 붙이는 일이며, 첫 수집이 끝나기 전까지 CONNECTING("연동 중")이다.

### D6. 인증 정보 · 자격증명 · 앱키
- 쓸 말: 묶음은 **인증 정보**, 낱개는 **앱키 · 앱 시크릿**
- 쓰지 않을 말: 자격증명, 시크릿(단독), 키
- 코드 이름: `KisCredential`, `CredentialInput`, `CredentialStore`(SSM), `credential_ref`, `CredentialFiller`
- 정의: 인증 정보는 사용자가 넣는 KIS 앱키와 앱 시크릿이며, 서버는 이를 SSM에 두고 수집 요청에는 참조(`credential_ref`)만 채운다.

## 그대로 쓰는 말

- 총자산 — `total_assets_krw`, 예수금 포함 평가금액 합 (P15)
- 평가금액 — `market_value_*`, 종가로 매긴 값 (UI "평가금액순")
- 비중 — `weight_pct`, 행 평가금액 ÷ 총자산 (탭 이름과 같음)
- 구성종목 · 구성비중 — ETF 안에 든 종목과 그 비율 (`etf_constituent`, `CONSTITUENT_AS_OF`)
- 미분해 — 구성종목을 몰라 ETF 분해에서 그대로 남은 ETF (UI 배지 "미분해")
- 기업행위 — `corporate_action`(분할 · 유상증자 · 합병), UI 섹션 이름과 같음
- 환율 — `fx_rate` · `fx_as_of`
- 계좌유형 축 · 시장 · 통화 · 자산군 · 섹터 — `AxisKey` 라벨과 UI 일치
- 해제 — 연동을 끊는 일, `DISCONNECTED`, UI "해제" · "연동 해제됨"
- 연동 상태 — CONNECTING "연동 중" · CONNECTED "연동됨" · DISCONNECTED "연동 해제됨"
- 인증 실패 · 연속 실패 — `CREDENTIAL_INVALID` · `REPEATED_FAILURE`, UI "인증 실패", "N일째 수집 실패"
- 픽업 · 다음 수집 — 데이터 DAG가 요청을 집는 시각, UI는 "다음 수집(…)"로만 보인다
- 집계 — 라인을 만들어 합계에 넣는 일, `ACCOUNT_NOT_AGGREGATED` "아직 집계하지 못했어요"
- 라벨 — 사용자가 붙인 계좌 이름, `account.label`, UI "라벨"
- 넣은 돈 — `deposited` (P12)
- 입금 · 출금 — `DEPOSIT` · `WITHDRAW`
- 배당 · 수수료 · 세금 — `DIVIDEND` · `FEE` · `TAX`, UI "수수료·세금"
- 기간 — 이번 달 · 지난달 · 올해 · 작년 · 지정, `Period`
- 안내 — 화면 위 notice, `NoticeCode`, UI "안내 N개 더"
- 로그인 · 로그아웃 · 계정 — 앱 계정은 관리자가 발급, 문서의 "사용자"는 사람을 가리킬 때만
- 접근 토큰 · 갱신 토큰 · 세션 — auth-session-design.md와 코드 일치
- 프리셋 · 직접 조건 — `PRESET` · `COMPOSABLE`, UI와 일치
- 지표 · 연산자 — `IndicatorKey` · `OperatorKey`, UI "지표" · "연산자"
- 장중 · 종가 — `INTRADAY` · `CLOSE`
- 감시 중 · 조건 충족 중 · 울린 뒤 종료 · 만료 — 알림 상태 배지, UI와 문서 일치
- 유효기간 · 만료 날짜 — `expires_at`, "만료"는 로그인 만료에도 쓰이나 맥락으로 갈린다
- 미리보기 · 현재값 — `preview`, UI "현재값"
- 읽음 — `read_at`, UI "모두 읽음"
- 푸시 — `push_device` · `alert_delivery`, 문서의 "발송"은 기기별 전송 행을 말할 때만
- 종목 마스터 (G10) · 데이터팀 표 · 미러 (G9)

## E5에서 바꿀 화면 문구 (11/15 확정)

| # | 지금 | 바꿀 문구 |
|---|---|---|
| 1 | 종목 화면 "ETF 분해 모드", 비중 화면 "구성종목 기준으로 보기", 서버 문구 "구성종목 기준 보기" | "ETF 분해" |
| 2 | 요약 타일 "현금보유" | "예수금" |
| 3 | 종목 상세 빈 문구 "이 종목에서 확정한 손익이 아직 없어요" | "이 종목의 실현손익이 아직 없어요" |
| 4 | "＋ 계좌 추가", 서버 문구 "등록할 수 있습니다" · "다시 등록해 주세요" | "연동"으로 통일("＋ 계좌 연동", "연동할 수 있습니다") |
| 5 | 자산 변화 안내 "%d개 계좌가 이월값입니다" | "%d개 계좌는 기간 경계에서 지난 값을 썼어요" |
| 6 | 오류 문구의 "자격증명" | "인증 정보" |
| 7 | 알림 문장의 "유지 조건" · "N분 지속" | "유지 방식" · "N분 이상 유지" |
| 8 | 자산 변화 링크 "실현손익 뷰 →" | "실현손익 보기 →" |
