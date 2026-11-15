# 데이터팀 OLAP 스키마 설계 검토 — 백엔드 관점

- **일자**: 2026-08-30
- **대상**: 데이터팀 `OLAP Schema Design` (Notion, 페이지 ID `3bb6ea40c08180528539c6197c542915`)
- **기준**: [설계 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) §5.1 · §7.7 · §11.2 · [조회 계층 계획](../plan/2026-08-09-portfolio-query-layer-plan.md) §A.7~A.9 · [설계 공유 문서](../meetings/2026-08-09-portfolio-design-review.md)
- **범위**: 계약 대조 · 구현 영향 · 잠금 해제 판정. 코드와 스펙은 고치지 않았다

---

## 0. 한 장 요약

데이터팀 설계는 **스펙 §5.1을 정확히 읽었다.** 백엔드 소유 7개 테이블의 컬럼이 부록 A에 스펙과 거의 그대로 재현돼 있고, `cln_*` 네 테이블은 스펙이 요구한 컬럼의 슈퍼셋이며, 커버리지는 요청한 두 개(`ca_coverage`·`etf_coverage`)를 넘어 네 개를 준다. `etf_coverage`는 백엔드 미러와 **컬럼명·상태값까지 정확히 일치**한다.

막힌 것은 스키마가 아니라 **경계 세 곳**이다.

| # | 문제 | 성격 | 고칠 쪽 |
|---|---|---|---|
| **B1** | `collection_run`의 스키마·상태 전이·픽업 주기·재시도 정책이 문서에 없고, 부록 E 서빙 매핑에도 없다. 게다가 §8.2가 백엔드에 `data` 스키마 **읽기 권한만** 주기로 해서, 스펙 §7.7의 "백엔드가 `REQUESTED` 행을 삽입한다"가 물리적으로 불가능해진다 | 계약 공백 + 정면 충돌 | 양팀 합의 |
| **B2** | `account_ref`가 **어디에도 실체가 없다.** 백엔드 `account` 테이블에 컬럼이 없고(스펙 §5.1에도 없다), `cdc_account`에도 없다. 그런데 `cln_*` 전부와 데이터팀 `recon_position_daily`가 이 값에 기댄다 | 우리 스펙의 구멍 | **백엔드** |
| **B3** | 데이터팀 산출물에 `user_id`가 들어갔다. `cdc_app_user`·`dim_account`·`mart_portfolio_daily`·`mart_allocation_daily`·`mart_asset_change_monthly`가 사용자 축을 갖는다. 스펙 §11.2 "데이터팀 산출물에 `user_id`가 없다"의 정면 위반이고, 마트 셋은 백엔드 6개 뷰 중 3개와 같은 숫자를 각자 계산한다 | 경계 위반 | 데이터팀 |

즉시 코드를 깨뜨리는 것은 하나도 없다. 백엔드가 지금 조인하는 테이블은 `instrument`와 `etf_coverage` 둘뿐이고(`AggregateMapper.xml:120`, `EtfCoverageMapper.xml:24`, `RealizedPnlMapper.xml:17`), `etf_coverage`는 완전 일치, `instrument`는 **이름과 컬럼 범위만 확정하면** 통과한다.

**잠금은 크게 풀렸다.** 1단계(스냅샷 생성)·1.5(등급 판정)·1.6(실현손익)·2단계(ETF 안분)·종목 상세가 데이터 쪽 의존을 벗었다. 남은 잠금은 계좌 연동·동기화 하나이며 원인이 B1이다.

---

## 1. 팀 경계 계약 대조 — 스펙 §11.2

스펙 §11.2 표는 11행이다(요청서에 열거된 10건 + `사용자 개념`). 11행 전부를 대조한다.

| # | 산출물 | 판정 | 근거 |
|---|---|---|---|
| 1 | 종목 마스터 | **부분** | 스키마 확정 ○ · 갱신 주기 ✕ · ISIN 미매칭 처리 ✕ · 유일성 깨짐 |
| 2 | ETF 구성비중(평탄화) | **부분** | 스키마·`as_of`·평탄화 ○ · 비중 합 보장 **반대 방향** · 깊이/순환 ✕ |
| 3 | 환율(일별) | **부분** | 소수 자릿수 ○ · 결측 보조 ○ · **PK 확장** · `rate_type` 의미 미결 |
| 4 | 원본 잔고·거래·입출금 | **충족(주의 1)** | 컬럼 슈퍼셋 ○ · 중복 처리 ○ · 조회 기간 한계 ○ · 잔고 최신행 선택 규칙 ✕ |
| 5 | `collection_run` | **미충족** | 문서에 스키마조차 없다. §8.2 권한 규칙과 §7.7이 충돌 |
| 6 | 자격증명 접근 | **충족(전달 경로는 5번에 묶임)** | 테이블 직접 접근 요구 없음. 오히려 CDC에서 명시적 제외 |
| 7 | `account_ref` 발급 | **미충족(양쪽)** | 전제만 있고 실체가 양쪽 어디에도 없다 |
| 8 | 사용자 개념 | **위반** | `user_id`가 레이크로 넘어갔다 |
| 9 | `trade_id` 안정성 | **충족(주의 2)** | 합성 규칙 문서화 ○ · 그레인이 "체결"이 아니라 "주문" |
| 10 | 커버리지 | **충족** | 요청한 2개 + `cln_trade_coverage` · `cln_cashflow_coverage` |
| 11 | 현금흐름 배제 규칙 | **부분** | 3종 축소·배제 명시 ○ · 커버리지 표와 유형 목록이 모순 |

### 1-1. 종목 마스터 — 부분

데이터팀 산출물은 `dim_instrument`(Iceberg · SCD2 · PK `instrument_sk`)이고, 백엔드에는 **`is_current` 뷰**가 리버스ETL로 온다(부록 E).

**맞는 것.** 스펙 §5.1의 9개 컬럼(`instrument_id`·`isin`·`symbol`·`name`·`asset_class`·`market`·`currency`·`sector`·`is_leveraged`)이 전부 있고 값 도메인도 일치한다(`STOCK/ETF/CASH`, `KR/US`, `KRW/USD`). `isin`이 nullable인 이유도 "발견 시점과 매칭 시점이 다름"으로 설명돼 있다.

**어긋나는 것 네 가지.**

**(a) 객체 이름과 컬럼 범위가 미정이다.** 백엔드는 `instrument`라는 이름으로 조인한다(`AggregateMapper.xml:120` 등 3곳). 데이터팀 문서는 부록 E에 "`dim_instrument`(`is_current` 뷰)"라고만 적어 Postgres 쪽 객체명을 정하지 않았다. 또 `dim_instrument`에는 `instrument_sk`·`sector_source`·`valid_from`·`valid_to`·`is_current` 다섯 컬럼이 더 있다.

`SchemaContractTest.instrument_컬럼_계약이_유지된다()`가 `containsExactly`로 아홉 컬럼을 못 박고 있어(`src/test/java/com/stockproject/portfolio/query/SchemaContractTest.java:26`), 뷰가 SCD2 컬럼까지 노출하면 이 테스트가 깨진다.

> **의견 — 데이터팀이 고친다.** `data.instrument`라는 이름의 뷰로, 스펙 §5.1의 아홉 컬럼만 노출한다. 뷰 정의 한 줄이라 비용이 사실상 0이고, 반대로 백엔드가 맞추면 매퍼 3곳 + 미러 + 계약 테스트가 함께 움직인다. `is_current` 필터를 뷰가 흡수하면 백엔드 쿼리에 SCD2 개념이 새어 들어오지 않는다는 이점도 있다.

**(b) `(symbol, market)`이 유일하지 않다.** 데이터팀이 명시적으로 적어 뒀다. 그런데 백엔드는 **`symbol`을 종목 축의 행 key로 쓴다**(`AxisSql.java:21` — `AxisKey.INSTRUMENT → "i.symbol"`, 라벨은 `i.name`). `GROUP BY`가 key와 label을 함께 묶으므로 크래시는 나지 않지만, 같은 티커를 가진 서로 다른 종목이 `종목별` 화면에 **같은 key로 두 행** 나온다. 프론트가 key를 행 식별자로 쓰면 여기서 깨진다.

데이터팀이 `instrument_alias`(티커↔종목 유효기간 매핑)를 리버스ETL 대상에 넣어 뒀으므로 해소 수단은 있다.

> **의견 — 백엔드가 고친다.** 행 key를 `instrument_id`로 바꾸고 `symbol`은 표시용 필드로 내린다. 축의 key가 도메인 식별자여야 한다는 원칙 문제이고, 데이터팀이 SCD2를 도입한 이상 티커 유일성은 앞으로도 보장되지 않는다. 다만 이건 조회 계층 변경이라 **이번 검토 범위 밖**이며, 별도 태스크로 잡아야 한다.

**(c) 상장폐지 종목이 뷰에서 사라질 수 있다.** 집계는 `instrument`를 **내부 조인**한다(`AggregateMapper.xml:120`). `is_current` 뷰가 상장폐지 종목을 떨어뜨리면 그 종목의 과거 `position_line`이 총자산에서 조용히 빠진다. 계획서 §A.8이 "모든 라인이 종목 마스터에 매칭된다"를 검증기 전용 규칙으로 둔 이유가 정확히 이것인데, 그때 500이 나는 것도 정상 동작은 아니다.

**(d) 갱신 주기와 ISIN 미매칭 처리가 문서에 없다.** 리버스ETL 스케줄이 §8.3에서 "홉이 두 개 늘었다"로만 언급되고 주기가 없다. ISIN이 안 붙은 종목을 마스터에 어떻게 남기는지(플레이스홀더 행을 만드는지, 아예 없는지)도 없다. `recon_position_daily.diff_reason`에 `ORPHAN_INSTRUMENT`가 있는 걸 보면 미매칭 자체는 인지하고 있으나, 백엔드가 그 라인을 어떻게 다뤄야 하는지는 정해지지 않았다.

**(e) 섹터 체계는 통일하지 않기로 결정됐다.** 미결 사항 표의 "섹터 라벨 통합(Yahoo 11 vs Naver WICS 79) — 하지 않기로 결정 (YAGNI)". `dim_instrument.sector`는 "원문 라벨 그대로"이고 출처는 `sector_source`(`YFINANCE`/`NAVER_WICS`)에 담긴다.

백엔드 섹터 축은 라벨 문자열로 그대로 묶는다(`AxisSql.java:22-23`). 그러면 `비중 분석` 섹터 차트에 **두 체계가 한 축에 섞여** 최대 90개 버킷이 나오고, 같은 반도체 기업이 국내·미국에서 다른 이름의 버킷에 앉는다. 스펙은 이걸 "외부 의존 대기 — 섹터 체계 통일 매핑"으로 남겨 뒀는데, 데이터팀이 하지 않기로 확정했으므로 이제 백엔드의 문제다.

> **의견 — 백엔드가 고친다.** 다만 매핑 테이블을 만드는 것은 과하다. 1차는 섹터 축 라벨에 출처를 함께 노출하거나(`반도체(WICS)`), 시장 필터와 섹터 축을 함께 쓰도록 화면에서 유도하는 선에서 정직하게 두는 편이 낫다. 이를 위해 뷰에 `sector_source`가 필요하며, 그러면 (a)의 "아홉 컬럼" 결정과 충돌한다 — **열 번째 컬럼으로 `sector_source`를 넣을지가 실제 판단점이다.** 추천은 넣는 쪽이다. null 섹터를 미분류로 모으는 것만으로는 두 체계 혼재를 사용자에게 설명할 방법이 없다.

### 1-2. ETF 구성비중(평탄화) — 부분

**맞는 것.** `etf_constituent` PK `(as_of, etf_instrument_id, underlying_instrument_id)`, `weight decimal(9,6)` — 스펙 §5.1과 컬럼·PK·타입이 정확히 일치한다. 부록 C-0이 변환을 "XLSX 파싱 → **중첩 ETF 평탄화** → ticker→`instrument_id` 해소"로 적어 §11.1의 "중첩 평탄화까지가 데이터"를 명시적으로 수용했다.

**어긋나는 것.**

**(a) 비중 합이 100%를 넘을 수 있다.** 데이터팀 주석: "합이 100%가 아닐 수 있음 (SPDR 실측 100.21%)". 스펙 §5.1은 "합이 100% **미만**일 수 있음 → 기타 버킷"으로 **부족한 쪽만** 가정했다.

이건 계획서 §A.8의 불변식 "look-through 전개 후 `Σ market_value_krw`가 전개 전과 일치(총합 보존)"를 직접 깬다. 100.21%로 안분하면 전개 후 총합이 원래보다 0.21% 커진다.

> **의견 — 백엔드가 고친다.** 데이터팀에 정규화를 요구하면 원본 파일이 준 값을 손대는 일이 되어 "원문은 버리지 않는다"는 그쪽 원칙과 부딪히고, 정규화 방식(비례 축소 vs 최대 항목 조정)이 도메인 판단이라 경계상으로도 백엔드 쪽이다. 안분 시 `Σ weight`로 나눠 정규화하고, 잔차는 기타 버킷이 **양수든 음수든** 흡수하도록 2단계 설계를 잡는다. 스펙 §5.1의 "100% 미만일 수 있음" 문구는 "100%와 다를 수 있음"으로 고쳐야 한다.

**(b) 깊이 제한과 순환 참조 차단이 문서에 없다.** §11.2가 명시적으로 합의 대상으로 지목한 두 항목인데 데이터팀 문서 어디에도 없다. 평탄화한다는 사실만 있고 순환을 만났을 때 무엇을 하는지(끊는지, 그 ETF를 미확보로 내리는지)가 없다.

**(c) 국내 ETF 원천이 없다.** `raw_etf_constituent`의 `source` enum은 `SPDR`을 포함하고 미결 사항에도 "SPDR 구성종목 CUSIP → ISIN 매핑"만 있다. KRX·국내 운용사 원천은 문서 전체에 등장하지 않는다. 즉 **국내 ETF는 미분해**가 사실상 확정이다 — 회의 안건 9의 제안(미국 ETF만 분해)과 같은 결론이지만, 데이터팀이 명시적으로 답한 것이 아니라 부재로 드러난 것이다.

이 경로는 이미 설계에 있어 동작에는 문제가 없다. `etf_coverage`에 행이 없으면 전개하지 않고 `CONSTITUENT_UNAVAILABLE`을 띄운다(`AggregateMapper.xml:36-39`).

### 1-3. 환율(일별) — 부분

**맞는 것.** `rate decimal(18,6)` — 스펙과 자릿수 일치. `as_of`가 "시장 현지 거래일 기준"이고 §6.1이 잔고 `date`와 같은 규칙을 쓴다고 못 박아, 스펙 §5.3의 환율 조인 기준과 정합한다. `dim_market_calendar`가 리버스ETL로 함께 와서 스펙 §5.3의 "직전 영업일 폴백"에 필요한 영업일 판정 원천이 생겼다.

**어긋나는 것 — PK가 확장됐다.**

| | 스펙 §5.1 | 데이터팀 |
|---|---|---|
| PK | `(as_of, currency_pair)` | `(as_of, currency_pair, rate_type)` |
| 추가 컬럼 | — | `rate_type` (`BASE`/`CLOSE`/`TT_BUY`/`TT_SELL`), `source` |

백엔드가 1단계에서 `rate_type` 없이 조인하면 **통화쌍당 최대 4행으로 팬아웃**된다. 게다가 데이터팀 미결 사항이 "`fx_rate.rate_type` 정의 — 매매기준율·종가 중 무엇을, 평가액용과 체결환산용을 나눌지"를 **미해결(우선순위 중간)** 로 남겨 뒀다. 값 목록만 있고 의미가 없다.

스펙 §5.3과 §4.3은 환율을 세 곳에서 쓴다 — 평가액 환산, 매입 시점 원가 환산, 매도일 환산. 셋이 같은 `rate_type`을 써야 하는지가 결정되지 않으면 1단계·1.6단계 중 하나가 잘못된 환율을 고른다.

> **의견 — 데이터팀이 정의하고, 스펙이 따라간다.** 어느 고시환율이 무엇을 뜻하는지는 원천 지식이라 데이터 쪽 판단이다. 백엔드는 "평가액·원가·실현 세 곳에 어느 `rate_type`을 쓸지"만 정하면 된다. 추천은 **세 곳 모두 하나의 `rate_type`(매매기준율 계열)으로 고정**하는 것이다 — 세 개를 다르게 쓰면 §5.3이 보장하는 "원화 평가손익에 환손익이 들어가지 않는다"가 깨진다. 스펙 §5.1의 `fx_rate` PK는 3컬럼으로 고쳐야 한다.

**결측 처리**는 데이터팀이 채우지 않고 백엔드가 폴백한다는 스펙 §5.3 그대로다. 다만 데이터팀이 **비영업일 행을 만드는지** 문서에 없다. 만든다면 폴백 로직이 영업일 캘린더 대신 행 존재로 판단해도 되고, 안 만든다면 `dim_market_calendar`가 필수다.

### 1-4. 원본 잔고·거래·입출금 — 충족(주의 1)

이 계약이 가장 잘 충족됐다. 스펙 §5.1과 부록 C-2를 대조하면:

| 테이블 | 스펙 컬럼 | 데이터팀 | 판정 |
|---|---|---|---|
| `cln_balance` | `account_ref`·`isin`·`quantity`·`avg_price`·`market_value`·`currency`·`source_as_of` | 전부 + `instrument_id`·`ingest_id` | **슈퍼셋** |
| `cln_deposit` | `account_ref`·`currency`·`amount`·`source_as_of` | 동일 | **일치** |
| `cln_trade` | `trade_id`·`account_ref`·`isin`·`side`·`quantity`·`price`·`fee`·`tax`·`currency`·`executed_at` | 전부 + `instrument_id`·`trade_date` | **슈퍼셋** |
| `cln_cashflow` | `account_ref`·`type`·`amount`·`currency`·`occurred_at` | 전부 + `cashflow_id`·`instrument_id` | **슈퍼셋** |

`instrument_id`를 데이터팀이 직접 붙여주는 것은 **스펙보다 나은 결정**이다. 스펙은 `isin`만 주기로 해서 백엔드가 마스터 매칭을 해야 했는데, 매칭 실패의 발견과 수정이 팀을 건너다니는 문제가 사라진다.

**조회 기간 한계**는 요구를 넘어섰다. `cln_trade_coverage(account_ref, covered_from, covered_to, is_definitive, empty_streak, computed_at)`가 있고, `is_definitive`가 "조회 한계"와 "정말 없음"을 가르며, `empty_streak` "연속 8회(≈2년) 빈 응답이면 최초 거래일 도달" 규칙까지 문서화됐다. 이것이 스펙 §4.4의 `coverage_start_at`과 등급 판정의 입력이 된다.

**중복 처리**도 명시됐다 — `cln_balance`는 `source_as_of` 기준, `cln_trade`는 `trade_id` 기준.

**주의 1 — `cln_balance` PK에 `source_as_of`가 있다.** PK가 `(account_ref, instrument_id, source_as_of)`이고 §8.2 리버스ETL 규칙이 "자연키 기준 `INSERT … ON CONFLICT DO UPDATE`"이므로, Postgres 사본에서도 **계좌×종목당 여러 행이 누적**된다. 백엔드 1단계는 그중 최신 1행만 필요하다.

> **의견 — 백엔드가 흡수한다.** `DISTINCT ON (account_ref, instrument_id) … ORDER BY source_as_of DESC`로 1단계에서 고르면 되고, 이력이 남는 것 자체는 대사에 쓸모가 있다. 다만 **보존 기간**을 물어야 한다 — 무한정 쌓이면 1단계 쿼리가 느려진다.

`cln_balance.avg_price`에 "KIS 원값 — 수수료 미포함"이 달렸다. 회의 문서 "검증되지 않은 가정 3가지"의 세 번째("잔고 평단의 수수료 포함 여부가 증권사마다 다름")가 KIS에 한해 답을 얻었다. CODEF는 `raw_codef_balance`가 "미구현"이라 여전히 미검증이다.

### 1-5. `collection_run` — 미충족 (B1)

**문서에 `collection_run`의 스키마가 없다.** 등장하는 곳은 셋뿐이다.

1. §4.2 — CDC **제외** 대상 목록에 포함. "이 테이블들은 리버스ETL이 쓰는 대상이므로"
2. 부록 B — Bronze-API 공통 컬럼 `collection_run_id`가 "OLTP `collection_run` 연결고리"
3. §8.3 · 미결 사항 — `collection_run.silver_synced_at` 컬럼 추가 여부가 **팀 합의 대기(우선순위 높음)**

부록 E 서빙 목적지 매핑에는 `collection_run`이 **아예 없다.** 리버스ETL 대상도, ClickHouse도, 레이크 전용도 아니다.

§11.2가 요구한 **상태 전이 규칙 · 픽업 주기 · 재시도 정책** 세 가지 모두 답이 없다.

**그리고 정면 충돌이 하나 있다.** §8.2 리버스ETL 규칙:

> 목적지는 Postgres `data` 스키마로 한정 / **백엔드는 `data` 스키마에 읽기 권한만** — 양쪽이 같은 행을 쓰면 lost update. 관례가 아니라 GRANT로 막는다

`collection_run`이 데이터팀 소유이므로 `data` 스키마에 놓이고, 그러면 백엔드는 읽기만 가능하다. 그런데 스펙 §7.7은 이렇게 정했다.

> 수동 새로고침 — **백엔드가 `REQUESTED` 행 삽입** → 데이터 잡이 집어감

**`collection_run`은 백엔드가 쓰는 유일한 데이터팀 테이블이다.** §8.2의 GRANT 규칙을 그대로 적용하면 수동 새로고침 경로가 성립하지 않는다.

이 충돌은 데이터팀 문서만 읽어서는 보이지 않는다 — §8.2의 규칙 자체는 옳고(리버스ETL 목적지에는 정확히 필요한 규칙이다), `collection_run`이 리버스ETL 목적지가 아니라 **양방향 큐**라는 사실이 그쪽 문서에서 빠져 있을 뿐이다.

> **의견 — 양팀 합의. 추천안은 `collection_run`을 리버스ETL 규칙의 명시적 예외로 두는 것.** `data` 스키마 안에 두되 이 테이블 하나에만 백엔드 INSERT 권한을 준다. lost update 위험은 **컬럼을 나눠** 막는다 — 백엔드는 `run_id`·`account_ref`·`requested_by`·`as_of`·`requested_at`·`credential_ref`만 쓰고, `state`·`finished_at`·`failure_reason`·`silver_synced_at`은 데이터팀만 쓴다. 두 팀이 같은 행을 쓰지만 같은 컬럼을 쓰지 않으므로 §8.2의 취지는 지켜진다.
>
> 대안(별도 `queue` 스키마 신설)은 스키마가 셋이 되고 §4.2의 순환 금지를 강제하는 `app`/`data` 이분법이 흐려져 추천하지 않는다.

**`silver_synced_at`은 받아들여야 한다.** §8.3이 지적한 대로 홉이 두 개 늘었고(수집 → Silver → 리버스ETL → Postgres → 백엔드 EOD), 백엔드 1단계는 리버스ETL이 끝나야 돌 수 있다. 스펙 §7.7의 상태 기계로는 이 대기를 표현할 수 없다는 그쪽 진단이 맞다. 스펙 §7.7 표에 컬럼을 추가해야 한다.

### 1-6. 자격증명 접근 — 충족

데이터팀이 §4.4에서 **스펙보다 보수적으로** 처리했다.

> `app_user.password_hash` · `app_user.email` · `account.credential_ref`는 Debezium 컬럼 필터에서 제외한다. (…) 시크릿 매니저 키 이름은 분석에 아무 값도 없으면서 공격 표면만 넓힌다

스펙 §11.2가 요구한 "테이블 직접 접근을 열지 않는다"가 충족되는 정도가 아니라, **키 이름조차 레이크에 넣지 않겠다**고 했다. 회의 안건 8(시크릿 매니저)에 대한 명시적 동의 문장은 없지만, `credential_ref`를 "시크릿 매니저 키 이름"으로 부르며 전제하고 있어 사실상 수용으로 읽힌다.

**남은 것은 전달 경로다.** 스펙 §7.7은 `collection_run.credential_ref`에 단기 참조를 실어 넘기기로 했는데, 그 테이블 스키마가 없으므로(B1) 이 부분은 확정되지 않았다.

### 1-7. `account_ref` 발급 — 미충족, 양쪽 (B2)

데이터팀은 `account_ref`를 전제로 설계했다. `cln_balance`·`cln_deposit`·`cln_trade`·`cln_cashflow`·`cln_trade_coverage`·`cln_cashflow_coverage` 전부가 이 컬럼으로 계좌를 식별하고, 백엔드가 발급하는 불투명 문자열임을 정확히 이해하고 있다("불투명 문자열 (계좌번호 아님)").

**그런데 이 값이 백엔드 어디에도 없다.**

- `account` 테이블 컬럼: `account_id`·`user_id`·`broker`·`label`·`account_type`·`source`·`credential_ref`·`link_state`·`last_synced_at` (`src/main/resources/db/migration/V1__initial_schema.sql:32-42`). **`account_ref` 없음**
- 스펙 §5.1의 `account` 정의에도 없음
- 데이터팀 `cdc_account`에도 없음(당연히 — 원천에 없다)

**결과 세 가지.**

1. 백엔드 1단계가 `cln_balance.account_ref` → `position_line.account_id` 변환을 할 수 없다. 이미 만들어 둔 두 포트의 시그니처가 이 구멍을 드러낸다 — `EarningsCashflowPort.totalsBetween(…, Set<UUID> accountIds)`와 `CollectionStatusPort.lastCollectionByAccount(…) → Map<UUID, CollectionStatus>`가 **UUID로 말하는데 상대 테이블은 text `account_ref`로 말한다.**
2. 데이터팀 `recon_position_daily`가 성립하지 않는다. 이 테이블은 PK `(as_of, account_id, instrument_id)`로 `qty_from_cln`(API 갈래, `account_ref` 키)과 `qty_from_oltp`(CDC 갈래, `account_id` 키)를 맞대는데, **둘을 잇는 매핑을 데이터팀이 가질 방법이 없다.** §6.3이 "두 갈래를 나눈 덕에 공짜로 얻는" 것이라 자랑한 대사가 실제로는 성립하지 않는다.
3. `trade_id` 안정성이 여기에 걸린다. `trade_id = {account_ref}:{ord_dt}:{odno}`이므로 `account_ref`가 바뀌면 과거 실현손익 키가 전부 바뀐다.

> **의견 — 백엔드가 고친다. 우리 스펙의 구멍이다.** `account` 테이블에 `account_ref text NOT NULL UNIQUE`를 추가하고, 스펙 §5.1 `account` 표에 "재연동해도 유지되며 계좌 해제 후 재등록 시에도 같은 계좌면 같은 값"을 명문화한다. 그리고 이 컬럼은 **CDC에 포함시켜야 한다** — 데이터팀 `dim_account`가 `account_ref`를 가져야 (2)의 대사가 성립한다. §4.4의 CDC 제외 목록과 충돌하지 않는다(개인정보도 자격증명도 아니다).
>
> 생성 규칙은 `account_id`를 그대로 쓰지 말 것을 추천한다. 불투명해야 한다는 요구는 충족되지만, 그러면 계좌를 해제했다 재등록할 때 `account_id`가 새로 발급되어 `account_ref`가 달라지고 과거 `cln_trade`와의 연결이 끊긴다. 계좌를 식별하는 안정적 입력(기관 + 계좌번호 해시)에서 유도해야 "같은 계좌면 같은 값"이 성립한다.

### 1-8. 사용자 개념 — 위반 (B3)

스펙 §11.2:

> 데이터팀 산출물에 `user_id`가 없다. 소유는 `account_ref` → 계좌 → 사용자로 백엔드가 해석한다. 소유를 경계 너머로 넘기면 두 팀이 같은 사실을 각자 들고 있게 된다

**데이터팀 설계에는 `user_id`가 여섯 곳에 있다.**

| 테이블 | 위치 | 성격 |
|---|---|---|
| `cdc_app_user` | PK | 백엔드 `app_user`를 통째로 CDC |
| `cdc_account` · `dim_account` | 컬럼. "소유 판정의 유일한 축"이라 주석까지 달림 | 소유 축을 레이크가 재구성 |
| `mart_portfolio_daily` | PK `(as_of, user_id)` | **`요약` 화면과 같은 계산** |
| `mart_allocation_daily` | PK `(as_of, user_id, axis, axis_value, lens)` | **`비중 분석` 화면과 같은 계산** |
| `mart_asset_change_monthly` | PK `(user_id, year_month)` | **`자산 변화` 화면과 같은 계산** |
| `backtest_result` | 컬럼 | 스펙 범위 밖 기능 |

`mart_allocation_daily`는 축 목록(`sector`/`market`/`currency`/`asset_class`/`instrument`)과 렌즈(`DIRECT`/`LOOK_THROUGH`)까지 백엔드 카탈로그와 같다. 두 팀이 같은 숫자를 각자 계산하고 있다.

**완화 요소.** 부록 E가 `mart_portfolio_daily`·`mart_allocation_daily`·`mart_asset_change_monthly`를 **"레이크에만"** 으로 분류했다. Postgres로 내려오지 않으므로 백엔드 `SchemaContractTest.소유권_축이_account에만_있다()`(`SchemaContractTest.java:47`)는 통과하고, 화면이 두 값을 섞어 보여줄 위험은 지금 없다.

**그래도 남는 문제 둘.** (1) `app_user` 전체를 CDC하는 것은 사용자 사실 자체를 레이크로 넘기는 일이다 — `email`·`password_hash`·`display_name`을 제외했어도 "누가 존재하는가"와 "누가 무엇을 소유하는가"는 넘어간다. (2) 마트 셋이 화면 계산과 어긋나기 시작하면 어느 쪽이 맞는지 판정할 기준이 없다.

> **의견 — 데이터팀이 정리한다. 다만 전면 철회는 요구하지 않는다.** 알림·백테스트가 사용자 단위 피처를 요구하는 것은 이해되고, 그 기능들은 이 스펙의 범위 밖이라 우리가 막을 근거도 약하다. 요구할 것은 두 가지다.
>
> 1. **부록 E의 "레이크에만" 분류를 계약으로 격상한다.** `mart_portfolio_daily`·`mart_allocation_daily`·`mart_asset_change_monthly`는 리버스ETL·ClickHouse 어디에도 내보내지 않으며, 사용자 화면이 이 값을 읽지 않는다. 문장으로 명문화하고 §10 설계 원칙에 넣는다.
> 2. **`cdc_app_user`를 빼거나 축소한다.** `dim_account`에 `user_id`가 있으면 마트 집계에 필요한 소유 축은 이미 확보된다. `app_user` 테이블 자체를 CDC할 이유가 남지 않는다.
>
> 그리고 이 결정은 스펙 §11.2에 반영해야 한다 — 현재 문구("데이터팀 산출물에 `user_id`가 없다")는 이미 사실이 아니다. "**백엔드가 소비하는** 데이터팀 산출물에 `user_id`가 없다"로 좁히는 것이 정직하다.

### 1-9. `trade_id` 안정성 — 충족(주의 2)

**합성 규칙이 문서로 고정됐다.** `trade_id = {account_ref}:{ord_dt}:{odno}` + 주석 "주문번호는 하루 안에서만 유일". 회의 안건 5가 우려한 `(계좌, 종목, 체결일시, 수량, 가격)` 해시 방식을 피했고, 정정 체결이 같은 `odno`로 오면 값만 갱신되어 upsert로 흡수된다. 스펙 §11.2의 요구를 충족한다.

**주의 2 — 그레인이 "체결"이 아니라 "주문"이다.** 부록 C-0의 `cln_trade` 변환: "payload 펼치기 → `trade_id` 합성 → **분할체결 주문 단위 합산** → `trade_date` 현지 거래일 부여".

스펙 §5.1의 `realized_pnl_line`은 "**매도 체결 1건**"이 한 행이다. 분할체결이 합산되면 실현손익 행도 주문 단위가 된다.

실질 영향은 크지 않다 — 같은 주문의 분할체결은 같은 날 같은 종목이고, 실현손익 합계·기간 귀속·화면 표시 어디에도 차이가 없다. 오히려 행 수가 줄어 좋다. 다만 **`price`가 가중평균 체결가가 된다**는 뜻이고, 스펙 문구가 "체결"이라 용어가 어긋난다.

> **의견 — 데이터팀 결정을 받아들이고 스펙 문구를 고친다.** §5.1 `realized_pnl_line`의 "매도 체결 1건"을 "매도 주문 1건(분할체결은 합산)"으로, `cln_trade.price`에 "가중평균 체결가"를 명시한다.

### 1-10. 커버리지 — 충족

요청한 두 개를 주고 두 개를 더 준다.

| 테이블 | 스펙 §5.1 | 데이터팀 | 판정 |
|---|---|---|---|
| `ca_coverage` | `market` 또는 `instrument_id` · `covered_from` · `covered_to` | 동일 + `state`(`COVERED`/`UNAVAILABLE`) · PK `(market, instrument_id)` · "**0행 = 전량 미확보 신호**" 명시 | 슈퍼셋 |
| `etf_coverage` | `etf_instrument_id` · `state`(`COVERED`/`UNAVAILABLE`) · `as_of` | **완전 일치** | 일치 |
| `cln_trade_coverage` | (스펙에 없음) | `account_ref` · `covered_from`/`covered_to` · `is_definitive` · `empty_streak` | 추가 제공 |
| `cln_cashflow_coverage` | (§4.6이 요구, §5.1에 표 없음) | `account_ref` · `type` · `state` · `computed_at` | 추가 제공 |

**`etf_coverage`는 백엔드 미러와 컬럼명·타입·CHECK 값까지 정확히 일치한다.** `src/main/resources/db/external/V3__etf_coverage_mirror.sql`과 대조했다. 렌즈 CTE(`AggregateMapper.xml:36-39`)와 `EtfCoverageMapper.xml:28-31`이 쓰는 `state = 'COVERED'` 조건이 그대로 동작한다. **이 계약은 지금 당장 실데이터로 바꿔도 안 깨진다.**

`ca_coverage`에 `state`가 추가된 것도 도움이 된다 — 스펙은 행의 존재/부재만으로 판정하게 했는데, 명시적 `UNAVAILABLE` 행이 있으면 "확인했고 없더라"와 "아직 안 봤다"까지 갈린다.

**다만 `corporate_action`은 0행이다.** 데이터팀 미결 사항 1순위가 "기업행위 원천(DART 등) 확정 — 미착수. `corporate_action` 0행이 조정종가·실현손익 대사·실시간 알림 억제 세 곳을 동시에 막는다". 스키마는 확정됐고 커버리지 구조도 있으므로 **설계는 정직하게 동작한다**(모든 종목이 `ca_unknown = true`). 원천만 없다.

### 1-11. 현금흐름 배제 규칙 — 부분

**맞는 것.** 부록 C-0의 `cln_cashflow` 변환: "payload 펼치기 → **매매대금·환전·예수금 내부이동 배제** → 유형 3종으로 축소". 회의 안건 1의 제안(데이터가 배제한 결과만 제공)을 그대로 수용했고, 스펙 §5.1의 배제 표 네 항목 중 셋이 명시적으로 언급됐다. `type` 값도 `DIVIDEND`/`FEE`/`TAX`로 스펙과 일치하며 "매매 외 비용만"이라는 단서까지 붙었다.

**어긋나는 것 — 커버리지 표가 다섯 유형을 든다.**

| | `type` 값 |
|---|---|
| `cln_cashflow` | `DIVIDEND` · `FEE` · `TAX` |
| `cln_cashflow_coverage` | `DIVIDEND` · `FEE` · `TAX` · **`DEPOSIT`** · **`WITHDRAW`** |

같은 문서 안의 모순이다. 두 해석이 가능하다.

1. **커버리지만 5종을 추적한다** — "입출금은 원천에서 확보 불가"를 기록하려는 의도. 이 경우 무해하고, 오히려 사용자에게 "이 계좌는 입출금 자동 확보가 안 되니 직접 입력하라"를 안내할 재료가 된다.
2. **`cln_cashflow`에 나중에 입출금을 넣을 여지를 남겼다** — 이 경우 **스펙 §9.1 위반**이다.

(2)라면 백엔드는 매핑 단계에서 터진다. 계획서 §A.8이 이 규칙을 **타입으로 강제**해 뒀기 때문이다 — `EarningsCashflowPort`가 읽는 유형 enum이 `EarningsCashflowType { DIVIDEND, FEE, TAX }`라 두 값을 표현할 방법이 없다. 조용히 틀리지 않고 크게 깨지므로 설계 의도대로 동작하지만, 그 시점이 1단계 구현 중이라 늦다.

**추가로 답이 없는 것 둘.**

- **배제 방법.** 회의 안건 1은 "응답 필드로 식별되는가, 안 되면 체결내역과 대조하는가"를 물었다. 데이터팀은 "배제한다"만 적고 방법을 적지 않았다. 체결 대조 방식이면 **체결내역이 없는 계좌(연금)에서 배제가 불완전해지는데, 하필 그 계좌가 `자산 변화` 화면이 가장 필요한 계좌다.**
- **`FEE`·`TAX`의 원천 범위.** `cln_cashflow`의 유일한 원천은 `raw_kis_rights`(KIS 권리·입출금 내역)다. 스펙 §5.1은 `FEE`/`TAX`를 "계좌 관리수수료·환전수수료·배당소득세 등 매매 외 비용"으로 정의했는데, 그 TR이 이 항목들을 담는지 확인된 바 없다.

---

## 2. 회의 안건 답변 현황

### 2-0. 먼저 — 안건 번호가 두 문서에서 어긋나 있다

[설계 공유 문서](../meetings/2026-08-09-portfolio-design-review.md)는 **9건**이고, [조회 계층 계획](../plan/2026-08-09-portfolio-query-layer-plan.md) §A.9는 **8건 체계**로 참조한다. 안건 2(입출금 사용자 입력)가 빠진 번호를 쓰고 있어 그 이후가 하나씩 밀린다.

| 계획서 §A.9 표기 | 실제 회의 안건 | 내용 |
|---|---|---|
| 안건 1 | 안건 1 | 매매대금 배제 |
| 안건 3 | **안건 4** | ETF 평탄화 |
| 안건 5 | **안건 6** | `cln_*` 컬럼 확정 |
| 안건 6 | **안건 7** | `collection_run` |
| 안건 7 | **안건 8** | 시크릿 매니저 |
| 안건 8 | **안건 9** | 국내 ETF 확보 |

**계획서 §A.9의 안건 번호를 회의 문서 기준으로 고쳐야 한다.** 아래는 회의 문서(9건) 기준이다.

### 2-1. 안건별 판정

| # | 안건 | 판정 | 근거 |
|---|---|---|---|
| 1 | 현금흐름에서 매매대금 배제 | **답 얻음(부분)** | 부록 C-0이 "매매대금·환전·예수금 내부이동 배제" 명시. **방법 미기재**, `FEE`/`TAX` 원천 범위 미확인 |
| 2 | 입출금을 사용자 입력으로 | **답 얻음** | `cdc_manual_cashflow`를 백엔드 소유로 인정하고 CDC로 읽는 설계 — 수용으로 읽힘. 단 `cln_cashflow_coverage`의 5종 목록이 모순 |
| 3 | "없음" vs "미확보" 구분 | **답 얻음** | `ca_coverage`(+`state`) · `etf_coverage` 제공. "0행 = 전량 미확보 신호" 명시. **원천(DART)은 미착수, 그쪽 최우선 미결** |
| 4 | ETF 구성비중 한 겹 평탄화 | **답 얻음(부분)** | 스키마·평탄화 ○. **깊이 제한·순환 차단 무기재**, 비중 합이 100%를 넘을 수 있음 |
| 5 | `trade_id` 안정성 | **답 얻음** | `{account_ref}:{ord_dt}:{odno}` 문서 고정. 그레인이 주문 단위 |
| 6 | `cln_*` 네 테이블 컬럼 확정 | **답 얻음** | 부록 C-2에 전문. 스펙의 슈퍼셋. 조회 기간 한계는 `cln_trade_coverage`로 초과 충족 |
| 7 | `collection_run` 단일 테이블 오케스트레이션 | **미해결** | 스키마 없음. §8.2 권한 규칙이 §7.7 양방향을 막는다(B1) |
| 8 | 자격증명을 시크릿 매니저에 | **사실상 수용** | 명시적 동의 문장은 없으나 §4.4가 `credential_ref`를 시크릿 키로 전제하고 CDC에서 제외 |
| 9 | 국내 ETF 구성종목 확보 | **부재로 답함** | 문서에 KRX·국내 운용사 원천이 없다. 미국(SPDR)만. 회의 제안(1차 미국만)과 같은 결론 |

**8/9가 답을 얻었고 남은 것은 안건 7 하나다.** 그리고 안건 7이 유일하게 남은 잠금(계좌 연동·동기화)의 원인이다.

---

## 3. 구현 영향

### 3-1. 지금 깨지는 것 — 없음

백엔드가 실제로 조인하는 데이터팀 테이블은 둘이다.

| 테이블 | 조인 위치 | 판정 |
|---|---|---|
| `instrument` | `AggregateMapper.xml:120` · `EtfCoverageMapper.xml:24` · `RealizedPnlMapper.xml:17` (전부 내부 조인) | **조건부 안전** |
| `etf_coverage` | `AggregateMapper.xml:36-39` · `EtfCoverageMapper.xml:28-31` | **안전** |

`etf_coverage`는 미러(`V3__etf_coverage_mirror.sql`)와 데이터팀 정의가 컬럼명·타입·`CHECK` 값까지 일치한다. 실데이터로 교체해도 렌즈 CTE와 `CONSTITUENT_UNAVAILABLE` notice가 그대로 동작한다.

`instrument`는 §1-1의 (a)만 정리되면 안전하다 — **뷰 이름을 `instrument`로, 컬럼을 스펙 9개(+`sector_source` 검토)로 한정.**

### 3-2. 곧 깨질 것 — 우선순위 순

| 순위 | 지점 | 무엇이 깨지는가 | 고칠 쪽 |
|---|---|---|---|
| 1 | `account_ref` 부재 | 1단계 전체. `EarningsCashflowPort`·`CollectionStatusPort` 두 포트가 UUID로 말하는데 상대는 text 키다 | 백엔드 |
| 2 | `collection_run` 미확정 + 쓰기 권한 | 계좌 연동·동기화 전체. `NoCollectionStatusPort` 스텁을 걷어낼 수 없다 | 양팀 |
| 3 | `fx_rate` PK 확장 | 1단계 환산·1.6단계 실현손익. `rate_type` 없이 조인하면 통화쌍당 최대 4행 팬아웃 | 데이터팀 정의 → 스펙 반영 |
| 4 | `instrument` 뷰 이름·컬럼 범위 | `SchemaContractTest`(`containsExactly` 9컬럼) + 매퍼 3곳 | 데이터팀 |
| 5 | ETF 비중 합 > 100% | 2단계 안분의 총합 보존 불변식(계획서 §A.8) | 백엔드 |
| 6 | `symbol` 유일성 없음 | `종목별` 화면 행 key 중복 (`AxisSql.java:21`) | 백엔드 |
| 7 | 섹터 두 체계 혼재 | `비중 분석` 섹터 축에 Yahoo 11 + WICS 79가 섞인다 (`AxisSql.java:22-23`) | 백엔드 |
| 8 | `cln_cashflow`에 `DEPOSIT`/`WITHDRAW` 유입 | `EarningsCashflowType` 매핑 실패 — 타입으로 막혀 있어 조용히 틀리진 않는다 | 데이터팀 확인 |
| 9 | `cln_balance` 다중 행 | 1단계가 최신 `source_as_of`를 고르지 않으면 중복 계상 | 백엔드 |

### 3-3. 새로 생긴 요구 — 데이터팀이 우리에게 요구하는 것

데이터팀 설계는 스펙 §11.2에 없던 **반대 방향 인터페이스**를 만든다. 백엔드 7개 테이블 전부를 CDC로 읽는다(`cdc_app_user`·`cdc_account`·`cdc_position_line`·`cdc_position_basis`·`cdc_realized_pnl_line`·`cdc_manual_cashflow`·`cdc_sync_run`). 여기서 우리에게 떨어지는 작업이 셋이다.

**(a) Postgres 스키마 분리 (`app` / `data`).** §4.2가 순환 금지를 강제하기 위해 요구하고, 데이터팀 미결 사항에 **우선순위 높음**으로 올라 있다. 백엔드 테이블은 현재 `public`에 있다(`SchemaContractTest.java:49`, `:60`이 `table_schema = 'public'`으로 조회). 마이그레이션과 매퍼 참조 방식(search_path vs 스키마 한정 이름) 결정이 필요하다.

> **의견 — 받아들인다.** §4.2의 순환 금지(리버스ETL → Postgres → CDC → 레이크 무한 루프)는 실제 위험이고, GRANT로 강제하겠다는 판단이 옳다. 다만 §1-5에서 적은 `collection_run` 예외를 함께 정해야 한다.

**(b) `cdc_app_user`의 PK 컬럼명이 실제와 다르다.** 데이터팀은 `cdc_app_user · PK(user_id)`로 잡았는데, 실제 `app_user`의 PK 컬럼은 **`id`** 다(`V1__initial_schema.sql:9`). `account.user_id`가 이것을 참조한다(`:34` — `REFERENCES app_user (id)`). Debezium 스키마가 그대로 `id`로 온다.

> **의견 — 데이터팀 문서를 고친다.** 백엔드 쪽 컬럼명 변경은 스펙 §5.1(`user_id` uuid PK)과 실제 구현이 이미 어긋나 있다는 뜻이기도 하다. 어느 쪽으로 통일할지는 별도 판단이지만, **지금 있는 것은 `id`** 이므로 CDC 설계가 그것을 따라야 한다.

**(c) 존재하지 않는 테이블을 전제한다.** `cdc_position_basis`와 `cdc_sync_run`이 설계돼 있으나, 두 테이블은 **아직 만들지 않았다.** 계획서 §A.9가 범위에서 제외했고 `SchemaContractTest.범위_밖_테이블을_만들지_않는다()`(`SchemaContractTest.java:56`)가 없음을 강제한다. CDC 커넥터를 붙이는 시점이 백엔드 1.5단계 이후여야 한다는 순서 제약이 생긴다.

### 3-4. 교차 소유 FK — 요구 없음, 명시적 합의

데이터팀 §10 설계 원칙:

> **소유 팀이 다르면 FK를 걸지 않는다** — 레이크에는 FK 개념이 없으므로 정합성 검사 잡으로 대체. 고아 `instrument_id` 탐지를 대사에 포함

우리가 물어본 것에 정확히 답했다. `SchemaContractTest.position_line은_instrument에_FK를_걸지_않는다()`(`SchemaContractTest.java:32`)가 지키는 원칙이 양팀에서 같다. 리버스ETL 목적지인 `data` 스키마 안에서 FK를 걸지에 대한 언급은 없으나, 위 원칙상 걸지 않는다고 읽는 것이 자연스럽다. **확인만 하면 된다.**

### 3-5. 백엔드에 유리하게 바뀐 것

부정적인 것만 적으면 균형이 안 맞으므로 함께 적는다.

| 항목 | 효과 |
|---|---|
| `cln_*`에 `instrument_id` 직접 제공 | ISIN 매칭이 데이터팀에서 끝난다. 매칭 실패의 발견과 수정이 한 팀 안에 머문다 |
| `dim_market_calendar` 리버스ETL 제공 | **계획서 §A.10의 열린 판단이 풀린다.** 휴장일 캘린더가 생겨 `PRICE_LAG_MARKET` notice를 정직하게 발화시킬 수 있고, 스펙 §5.4의 "국내 증시 영업일마다 한 벌"에도 판정 원천이 생긴다 |
| `cln_trade_coverage`(`is_definitive`·`empty_streak`) | 스펙 §4.4 등급 판정의 입력이 요구 이상으로 확보됐다 |
| `cln_cashflow_coverage` | 스펙 §4.6의 현금흐름 커버리지 요구가 충족된다 |
| `ca_coverage.state` | "확인했고 없더라"와 "아직 안 봤다"까지 갈린다 |
| `instrument_alias` | 티커 재사용 문제의 해소 수단(백엔드는 `instrument_id`를 쓰므로 직접 필요하진 않다) |
| §4.4 PII·자격증명 CDC 제외 | 요구보다 보수적 |

---

## 4. 스펙이 고쳐야 할 곳

이번에 고치지 않았다. 무엇을 고쳐야 하는지만 적는다.

| 위치 | 무엇을 | 왜 |
|---|---|---|
| §5.1 `account` | **`account_ref` 컬럼 추가** + "재연동해도 같은 계좌면 같은 값" 명문화 + 생성 규칙 | B2. 스펙의 구멍이다 |
| §5.1 `fx_rate` | PK를 `(as_of, currency_pair, rate_type)`으로. `rate_type` 값 목록과 **세 용도(평가·원가·실현)에 쓸 값** 지정 | §1-3 |
| §5.1 `etf_constituent` | "합이 100% **미만**일 수 있음" → "**100%와 다를 수 있음**". 초과분 처리(정규화·잔차 흡수) 규칙 추가 | §1-2(a) |
| §5.1 `realized_pnl_line` | "매도 **체결** 1건" → "매도 **주문** 1건(분할체결은 합산)" | §1-9 |
| §5.1 `cln_trade` | `price`에 "가중평균 체결가" 명시 | §1-9 |
| §5.1 `cln_balance` | PK가 `(account_ref, instrument_id, source_as_of)`임과 **최신행 선택이 백엔드 몫**임을 명시 | §1-4 |
| §5.1 `cln_cashflow_coverage` | 테이블 정의 추가(§4.6이 요구만 하고 §5.1에 표가 없다). `type` 5종과 `cln_cashflow` 3종의 관계 명시 | §1-11 |
| §7.7 `collection_run` | `silver_synced_at` 컬럼 추가. `data` 스키마 배치와 **컬럼 단위 쓰기 권한 분할** 명시 | B1 |
| §11.2 사용자 개념 | "데이터팀 산출물에 `user_id`가 없다" → "**백엔드가 소비하는** 데이터팀 산출물에 `user_id`가 없다" + 레이크 마트 비반출 계약 | B3 |
| §11.2 (신설 행) | **역방향 CDC 인터페이스.** 백엔드 테이블을 데이터팀이 CDC로 읽는다는 사실, 컬럼 필터(PII·자격증명 제외), `app`/`data` 스키마 분리 요구 | §3-3 |
| §11.1 · §5.1 | 종목 마스터 물리 객체명을 `data.instrument`(뷰)로 확정, 노출 컬럼 목록 고정 | §1-1(a) |
| 외부 의존 대기 | "섹터 체계 통일 매핑" 항목을 **"데이터팀이 하지 않기로 결정 — 백엔드 표시 정책으로 흡수"** 로 변경 | §1-1(e) |
| §3.4 / §6.1 | ETF 렌즈 설명에 "국내 ETF는 원천 미확보로 미분해"를 확정 사실로 반영(회의 안건 9 제안대로) | §1-2(c) |
| 계획서 §A.9 | 안건 번호를 회의 문서 9건 체계로 정정 | §2-0 |

---

## 5. 데이터팀에 되물을 것

우선순위 순. 1~3은 답이 없으면 해당 단계에 착수할 수 없다.

### 최우선 — 착수를 막는 것

**Q1. `collection_run`의 스키마·상태 전이·픽업 주기·재시도 정책을 확정해 달라. 그리고 백엔드 INSERT 권한 문제를 어떻게 풀 것인가.**

문서에 이 테이블의 정의가 없고 부록 E 서빙 매핑에도 빠져 있다. 더 중요한 것은 §8.2가 "백엔드는 `data` 스키마에 읽기 권한만"으로 못 박은 반면, 스펙 §7.7은 백엔드가 `REQUESTED` 행을 삽입하는 것을 수동 새로고침의 유일한 경로로 정했다는 점이다.

> **추천안.** `collection_run`을 §8.2 규칙의 명시적 예외로 두고, 이 테이블 하나에만 백엔드 INSERT 권한을 준다. lost update는 **컬럼 소유를 나눠** 막는다 — 백엔드는 `run_id`·`account_ref`·`requested_by`·`as_of`·`requested_at`·`credential_ref`, 데이터팀은 `state`·`finished_at`·`failure_reason`·`silver_synced_at`. `silver_synced_at`은 받아들인다.

**Q2. `account_ref`를 `dim_account`(및 CDC 대상)에 포함시켜 달라.**

`cln_*` 전부가 `account_ref`로 계좌를 식별하는데 `cdc_account`에는 그 컬럼이 없다. 그러면 `recon_position_daily`가 `qty_from_cln`과 `qty_from_oltp`를 같은 계좌로 맞댈 수 없다 — §6.3이 "두 갈래를 나눈 덕에 공짜로 얻는다"고 한 대사가 성립하지 않는다.

> **추천안.** 백엔드가 `account` 테이블에 `account_ref`를 추가하고 CDC 컬럼 필터에 포함시킨다. 개인정보도 자격증명도 아니라 §4.4의 제외 사유에 해당하지 않는다. **이 작업은 백엔드가 먼저 해야 하며, 우리 스펙의 구멍이었다.**

**Q3. `fx_rate.rate_type` 네 값의 의미를 확정해 달라. 평가액 환산·매입원가 환산·매도 환산 세 곳에 각각 무엇을 써야 하는가.**

미결 사항에 "매매기준율·종가 중 무엇을, 평가액용과 체결환산용을 나눌지"로 남아 있다. 값 목록만으로는 백엔드가 어느 행을 고를지 정할 수 없고, PK가 확장되어 `rate_type` 없이 조인하면 팬아웃된다.

> **추천안.** 세 곳 모두 **하나의 `rate_type`(매매기준율 계열)으로 고정**한다. 서로 다른 값을 쓰면 스펙 §5.3이 보장하는 "원화 평가손익에 환손익이 들어가지 않는다"(양변을 같은 환율로 환산)가 깨진다. `TT_BUY`/`TT_SELL`은 실제 체결 환전에만 쓰고 평가에는 쓰지 않는다.

### 높음 — 정의만 확인하면 되는 것

**Q4. 백엔드에 내려줄 종목 마스터의 물리 객체명과 노출 컬럼을 확정해 달라.**

부록 E에 "`dim_instrument`(`is_current` 뷰)"로만 적혀 있다. 백엔드는 `instrument`라는 이름으로 3곳에서 조인하고, 계약 테스트가 컬럼 아홉 개를 정확히 못 박고 있다.

> **추천안.** `data.instrument` 뷰로 노출하고 컬럼은 스펙 §5.1의 아홉 개 + `sector_source` 열 개로 한정한다. `sector_source`를 넣는 이유는 Q5.

**Q5. 섹터 체계를 통일하지 않기로 한 결정을 백엔드가 어떻게 표시하면 되는가.**

Yahoo 11개와 Naver WICS 79개가 한 축에 섞이면 `비중 분석` 섹터 차트가 최대 90개 버킷이 되고, 같은 산업의 국내·미국 종목이 다른 버킷에 앉는다.

> **추천안.** 결정 자체는 받아들인다(YAGNI가 맞다). `dim_instrument` 뷰에 `sector_source`를 포함시켜 주면 백엔드가 라벨에 체계를 함께 노출해 정직하게 처리한다. 데이터팀 쪽 추가 작업은 뷰 컬럼 하나다.

**Q6. `is_current` 뷰가 상장폐지·합병으로 사라진 종목의 행을 유지하는가.**

백엔드 집계는 `instrument`를 **내부 조인**한다(`AggregateMapper.xml:120`). 뷰에서 빠지면 그 종목의 과거 `position_line`이 총자산에서 조용히 빠지거나(검증기가 잡으면) 500이 난다. 과거 스냅샷 조회는 이미 청산된 종목을 반드시 포함한다.

> **추천안.** 상장폐지 종목도 마지막 버전을 `is_current = true`로 남긴다. `valid_to`가 닫히는 것은 **속성이 바뀌었을 때**뿐이어야 하고, 종목이 없어진 것은 새 상태(폐지)이지 버전의 종료가 아니다.

**Q7. ETF 평탄화의 깊이 제한과 순환 참조 차단 규칙은 무엇인가.**

§11.2가 명시적으로 합의 대상으로 지목했는데 문서에 없다. 순환을 만나면 끊는지, 그 ETF를 `etf_coverage.state = UNAVAILABLE`로 내리는지가 백엔드 화면 표시를 가른다.

> **추천안.** 순환·깊이 초과 시 그 ETF를 `UNAVAILABLE`로 내린다. 부분 전개된 결과를 주면 백엔드가 총합 보존을 검증할 수단이 없다(회의 안건 4의 트레이드오프 그대로).

**Q8. `cln_cashflow`에 `DEPOSIT`·`WITHDRAW`가 들어올 가능성이 있는가.**

`cln_cashflow.type`은 3종인데 `cln_cashflow_coverage.type`은 5종이다. 같은 문서 안의 모순이다.

> **추천안.** 커버리지만 5종을 추적하는 것으로 확정한다. 그 편이 "이 계좌는 입출금 자동 확보가 안 되니 직접 입력하라"를 사용자에게 안내할 재료가 되어 유용하다. **`cln_cashflow` 본체에는 3종만 넣는다** — 스펙 §9.1이 금지하고, 백엔드 `EarningsCashflowType`이 두 값을 표현하지 못해 매핑이 실패한다.

### 중간

**Q9. 매매대금·환전·내부이동 배제를 응답 필드로 하는가, 체결내역 대조로 하는가.**

체결 대조 방식이면 **체결내역이 없는 계좌(연금)에서 배제가 불완전해진다.** 하필 그 계좌가 `자산 변화` 화면이 가장 필요한 계좌라(회의 안건 1) 영향이 크다.

**Q10. `FEE`·`TAX`의 원천 범위는 어디까지인가.** 계좌 관리수수료·환전수수료·배당소득세가 `raw_kis_rights`에 담기는가. 스펙 §5.1이 정의한 "매매 외 비용"이 실제로 확보되는지 확인이 필요하다.

**Q11. `cln_balance`를 Postgres 사본에서 몇 벌 유지하는가.** PK에 `source_as_of`가 있어 계좌×종목당 여러 행이 쌓인다. 백엔드는 최신 1행만 쓰지만 보존 기간이 무한이면 1단계 쿼리가 느려진다.

**Q12. `mart_portfolio_daily`·`mart_allocation_daily`·`mart_asset_change_monthly`를 리버스ETL·ClickHouse로 내보내지 않는다는 것을 계약으로 확정해 달라.** 부록 E의 "레이크에만" 분류를 §10 설계 원칙에 문장으로 올려 주면 된다. 백엔드 6개 뷰와 같은 숫자를 각자 계산하고 있어, 화면과 마트가 어긋날 때 판정 기준이 필요하다.

**Q13. `cdc_app_user`가 필요한가.** `dim_account.user_id`로 마트 집계의 소유 축은 이미 확보된다. `app_user` 테이블 자체를 CDC할 이유가 남는가.

**Q14. `corporate_action.type`에 배당이 없다.** `SPLIT`/`RIGHTS`/`MERGER` 세 값인데, 문서는 이 테이블을 "액면분할·**배당** 같은 기업행위"로 설명하고 `adjusted_price_daily`가 조정계수를 여기서 유도한다. 배당 조정을 하지 않는 것이 맞는가, `type`에 값이 빠진 것인가.

**Q15. `cdc_app_user`의 PK 컬럼명은 `user_id`가 아니라 `id`다**(`V1__initial_schema.sql:9`). Debezium이 받는 것은 `id`이므로 부록 A를 정정해야 한다.

**Q16. 리버스ETL 갱신 주기와 ISIN 미매칭 종목 처리.** §11.2가 요구한 "갱신 주기"와 "ISIN 미매칭 처리"에 답이 없다. 미매칭 종목을 마스터에 플레이스홀더로 남기는가, 아예 없는가. 없다면 그 `position_line`이 내부 조인에서 사라진다.

**Q17. 리버스ETL 목적지(`data` 스키마)에서 테이블 간 FK를 거는가.** §10이 "소유 팀이 다르면 FK를 걸지 않는다"고 했으니 걸지 않는다고 읽었다. 확인만 필요하다.

**Q18. `fx_rate`에 비영업일 행을 만드는가.** 만들지 않는다면 백엔드 폴백이 `dim_market_calendar`에 의존한다.

---

## 6. 잠금 해제 판정 — 계획서 §A.9

| 제외 항목 | 막고 있던 것 | 지금 | 착수 가능 범위 |
|---|---|---|---|
| **`position_line` 생성 (1단계)** | `cln_*` 스키마 미합의 (안건 6) | **풀림 — 단 Q2 선행** | `cln_balance`·`cln_deposit` 미러 작성, 잔고→라인 정규화, 예수금 의사종목 변환, 캐리포워드. **`account_ref` 컬럼 추가가 선행 조건이다.** 환산은 Q3 이후 |
| **등급 판정 (1.5)** | `cln_trade` + `position_basis` 컬럼 확정 | **데이터 쪽 잠금은 풀림** | `cln_trade` ○ · `cln_trade_coverage`(`covered_from`·`is_definitive`·`empty_streak`) ○ → §4.4 역산의 입력이 전부 확보됐다. **남은 것은 우리 내부 미결** — 영구 `SEEDED` 사유 컬럼과 미설명 변동 대조 방식(§A.9가 든 이유는 데이터 의존이 아니었다) |
| **실현손익 산출 (1.6)** | 동상 + `trade_id` 안정성 | **풀림** | `trade_id` 합성 규칙 고정 ○ · `corporate_action` 스키마 확정(0행) ○ · `ca_coverage` ○ → 기업행위 미확보를 `ca_unknown`으로 정직하게 표시하며 산출 가능. 그레인이 주문 단위임을 반영 |
| **종목 상세** | `cln_trade` · `position_basis` · `corporate_action` | **풀림** | 셋 다 스키마 확정. `corporate_action`이 0행이라 기업행위 경고는 항상 `ca_unknown`으로 뜨지만 이는 설계된 정상 경로 |
| **ETF 분해 안분 (2단계)** | 구성비중 제공 형태 (안건 4·9) | **풀림 — 단서 있음** | `etf_constituent` 스키마·PK·`as_of` 확정 ○ · 평탄화 데이터팀 수용 ○ · `etf_coverage` 미러와 완전 일치 ○ → `AggregateMapper.xml`의 `UNION ALL` 자리에 전개 분기를 붙일 수 있다. **단서 둘**: 비중 합 100% 초과 정규화 규칙을 먼저 정할 것(§1-2a), **국내 ETF는 미분해 확정**(§1-2c) |
| **계좌 연동 · 동기화** | `collection_run` 계약 · 시크릿 관리 (안건 7·8) | **잠금 유지** | 시크릿(안건 8)은 사실상 수용됐으나 `collection_run`(안건 7)이 통째로 없다. `NoCollectionStatusPort` 스텁을 걷어낼 수 없고 `sync_run` 테이블도 만들 수 없다. **Q1이 유일한 열쇠** |
| **손익성 현금흐름** | 매매대금 배제 규칙 · `FEE`·`TAX` 원천 (안건 1) | **부분 해제** | `cln_cashflow` 스키마 확정 ○ · 배제 명시 ○ · `cln_cashflow_coverage` ○ → `EmptyEarningsCashflowPort`를 실제 구현으로 교체 가능. **Q8·Q10 확인 후 착수 권장** — 유형 목록 모순과 `FEE`/`TAX` 원천 범위가 남아 있다 |
| **`PRICE_LAG_MARKET` (§A.10 열린 판단)** | 휴장일 캘린더 없음 | **풀림 (새로 생긴 해제)** | `dim_market_calendar`(`market`·`date`·`is_trading_day`·`prev_trading_day`·`next_trading_day`)가 리버스ETL 대상이다. `WeekdayMarketCalendar` 근사 없이 정식 캘린더로 `MarketCalendarPort`를 구현할 수 있고, 스펙 §5.4의 "국내 증시 영업일마다 한 벌"에도 판정 원천이 생긴다 |

### 착수 순서 제안

```
0. account_ref 추가 (백엔드, Q2 선행)  ─┐
   fx_rate.rate_type 확정 (Q3)         ─┼→ 1단계
   instrument 뷰 이름·컬럼 확정 (Q4)   ─┘

1단계 완료 후 ─→ 1.5 등급 판정 ─→ 1.6 실현손익 ─→ 종목 상세

2단계(ETF 안분)는 1단계와 독립 — 비중 정규화 규칙만 정하면 지금 착수 가능

계좌 연동·동기화는 Q1 답을 기다린다
```

### 함께 봐야 할 것 — 일정 의존이 깊어졌다

데이터팀 §8.3이 스스로 지적했다.

> 이전에는 데이터팀과 백엔드가 같은 Postgres 안에 있어 인계가 테이블 읽기 한 번이었다. 이제는 수집 → 레이크 Silver → 리버스ETL → Postgres → 백엔드 EOD 배치 → CDC → 레이크로 홉이 두 개 늘었다.

그리고 문서 첫머리의 전제 콜아웃이 이 구조를 "성능이 아니라 학습"을 위해 선택했다고 밝히고 있다. 이 판단 자체는 데이터팀 몫이지만, **백엔드 EOD 배치의 시작 조건이 리버스ETL 완료로 바뀐다**는 결과는 우리 것이다. `silver_synced_at`을 받아들이는 것이 그 대응이고(Q1), 스펙 §7.7의 상태 기계를 그만큼 고쳐야 한다.

또 하나 — 리버스ETL이 지연되거나 실패했을 때 백엔드가 무엇을 하는지가 정해지지 않았다. 스펙 §7.3은 **수집** 실패에 대한 캐리포워드만 정의한다. 리버스ETL 실패는 `cln_*`이 어제 값으로 남는 상황이라 수집 실패와 구분되지 않으므로, 지금 설계로도 캐리포워드가 동작하기는 한다. 다만 사용자에게 무엇이 낡았는지 설명하는 문구가 부정확해진다. Q1 답을 받은 뒤 §7.3에 한 줄 보태면 된다.
