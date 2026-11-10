# 종목 상세 백엔드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `GET /portfolio/instruments/{id}`가 종목 하나의 보유 · 계좌별 분해 · 실현손익 · 거래내역 · 기업행위를 내 계좌 범위로 내리고, 종목별 행에 `instrument_id`를 싣고, 알림의 "보유 중" 판정을 포트폴리오 화면과 같은 최신 스냅샷으로 맞추며, 확정 전 보유를 확인 불가 사유 `AWAITING_FINAL`로 판정한다.

**Architecture:** 보유 판정의 날짜는 `SnapshotCalendarRepository.latestAsOf` 하나가 정하고, "그 날짜에 보유 중인 라인"은 날짜를 받는 SQL 조각 상수 `SharedSql.HELD_LINE` 하나로 둔다. 종목 상세 · 종목 검색 `held` · 알림 생성/미리보기의 보유 확인이 둘을 함께 쓴다. 알림 평가는 확정 스냅샷(`HoldingReader.latestFinal` · `holding`)을 그대로 읽고, 평가 입력 `Series`에 "공유 판정으로 지금 보유 중" 한 비트를 더해 `ConditionEvaluator`가 `NOT_HELD` 자리에서 `AWAITING_FINAL`을 가른다 — 미리보기와 저장된 알림이 같은 평가기를 거친다. 종목 상세는 새 매퍼 `InstrumentDetailMapper`(+ `RealizedPnlMapper.findByInstrument`)가 재료를 읽고, 순수 조립기 `InstrumentDetailAssembler`가 합산 · 반올림 · 정렬 · 등급 모양을 정하며, `InstrumentDetailViewService`가 404 · 날짜 · 불변식 · 배너 · 안내 순서를 지킨다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · MyBatis(어노테이션 + XML) · PostgreSQL 16 · JUnit 5 · AssertJ · JSONAssert

**Spec:** [종목 상세 설계](../specs/portfolio-management/2026-11-10-instrument-detail-design.md) — 이 계획의 §번호는 그 문서의 절이다. 상위 근거는 [포트폴리오 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md).

## Global Constraints

- 작업 위치: 최신 `origin/main`에서 만든 새 worktree `/Users/yhr/Dev/workspace/personal/stock-project/.worktrees/back-end-instrument-detail`, 브랜치 `feat/instrument-detail`. **만들기 전에 사용자 승인.** 작업 트리 `back-end`(브랜치 `feat/position-line-builder`)와 `.worktrees/back-end-main`은 건드리지 않는다.
- 다른 트랙 코드 수정 금지: `snapshot/` 패키지, `dataeng/`. 그쪽 문제를 발견하면 고치지 말고 보고한다.
- 마이그레이션은 하나다: `db/migration/V16__alert_reason_awaiting_final.sql`(Task 2) — `alert_state.unknown_reason` CHECK에 `AWAITING_FINAL`을 더한다. 번호는 origin/main 마지막(`V15`) 다음이고, 머지 직전 origin/main에 `V16`이 생겼으면 다음 빈 번호로 옮긴다. 종목 상세가 읽는 표는 모두 있다 — `cln_trade` · `corporate_action`(`db/external/V12`), `position_basis`(`V13`), `instrument.delisted_on` · `adjusted_price_daily`(`V5`). 그 밖의 스키마 변경이 필요해지면 멈추고 보고한다.
- DB 테스트는 브랜치 전용 DB에서만, **돌리기 전에 사용자에게 묻는다**: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_instrument_detail?currentSchema=app,data' ./gradlew test --rerun-tasks` (특정 클래스는 `--tests '<FQCN 또는 *이름>'`). 전용 DB 생성도 승인 사항. 공유 `portfolio_test` 금지. DB 없는 단위 테스트(`@SpringBootTest` 없는 클래스)는 묻지 않고 `./gradlew test --tests '...'`로 돌린다. 각 태스크에 [DB] / [단위]를 표시했다.
- TDD. 테스트 메서드 이름은 기존처럼 한국어 문장.
- 커밋 · 푸시는 사용자가 요청할 때만. 접두 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- 주석 · 응답 · 커밋은 한국어. 주석은 히스토리 없이 최신 사실만, 문서 절 번호(§ · SG-)를 지칭하지 않고 주석만으로 이해되게, 검증하지 않은 것은 단정하지 않는다. 기존 주석이 "최신 확정 스냅샷에서 보유"라고 말하는 곳(`HoldingReader.held` · `HoldingMapper` · `InstrumentSearchMapper` · `InstrumentFacts`)은 새 사실로 고친다.
- 운영 DB에 쓰지 않는다. 스펙과 통합테스트 문서(`docs/yhr/test/`)를 고치지 않는다. 구현 중 설계와 코드가 어긋나면 멈추고 보고한다.
- 머지 전: 최신 origin/main에 리베이스하고 전체 테스트 재실행. 이 백엔드 브랜치가 앱 브랜치보다 먼저 머지 · 배포된다(§3.8 배포 순서 전제).
- CORS: `/portfolio/**` GET이 이미 열려 있다(`auth/WebOriginCorsConfig.java:49`). 새 경로는 그 안이라 변경 · 태스크 없음.

## Review Focus

1. **오늘 산 종목의 수익률 알림** — 화면엔 보유인데 생성이 `NOT_HELD`로 거절되면 앱의 `알림 걸기`가 깨지고, 만들어져도 카드가 저녁까지 `미보유`면 잘못 건 것으로 읽힌다. → Task 1 `오늘_산_종목에_수익률_조건을_만들_수_있다`, Task 2 `오늘_산_종목의_수익률_알림은_어제_확정으로_평가해도_첫_판정_대기다` · `오늘_산_종목의_알림은_목록과_상세에서_첫_판정_대기다`.
2. **오늘 판 종목의 미리보기에 어제 수익률이 보이는 것** — 저장할 수 없는 알림에 숫자가 붙으면 사용자는 걸 수 있다고 읽는다. → Task 2 `오늘_판_종목의_수익률_미리보기는_현재값이_없다`.
3. **상세의 수량 · 평단이 종목별 행과 다른 것(PF10-01)** — 두 계좌에 나눠 가진 종목에서 합산 전 반올림을 하면 끝전이 갈린다. → Task 6 `두_계좌_라인을_합산한_뒤_평단을_낸다`, Task 7 `종목별_행과_수량_평단이_같다`.
4. **남의 계좌가 섞이는 것(N-51)** — 005930을 yhr · jdh가 함께 갖는다. 라인 · 체결 · 실현손익 어느 블록에도 jdh 계좌가 나오면 안 된다. → Task 4 `세_블록_모두_내_계좌만_읽는다`, Task 7 `함께_가진_종목에서_남의_계좌가_없다`.
5. **원화 종목 상세에 달러 환율 안내가 붙는 것** — 그날 전체 라인으로 환율을 모으면 yhr 삼성전자 상세에 `USD/KRW` 안내가 뜬다. → Task 6 `원화_종목은_환율_안내가_없다`, Task 7 `원화_종목_상세에는_FX_APPLIED가_없다`.

---

## 파일 구조

back-end (`.worktrees/back-end-instrument-detail`). 접두 `M:` = `src/main/java/com/stockproject/portfolio/`, `T:` = `src/test/java/com/stockproject/portfolio/`.

| 파일 | 책임 |
|---|---|
| `M:query/SharedSql.java`(신규) | `HELD_LINE`(보유 판정 조각) · `LAST_CLOSE`(직전 종가 조각, 검색에서 옮김) |
| `M:alert/data/HoldingMapper.java` · `HoldingReader.java` · `alert/store/InstrumentSearchMapper.java` · `alert/service/InstrumentSearchService.java` · `alert/validation/InstrumentFacts.java` | 보유 판정을 조각으로 |
| `M:alert/evaluation/UnknownReason.java` · `ConditionEvaluator.java` · `alert/indicator/Series.java` · `alert/data/EvaluationInputFactory.java` · `alert/sentence/SentenceWriter.java` · `alert/service/AlertPreviewService.java` | `AWAITING_FINAL` 판정 · 문구, `NOT_HELD`면 현재값 없음 |
| `src/main/resources/db/migration/V16__alert_reason_awaiting_final.sql`(신규) | 확인 불가 사유 CHECK |
| `M:query/InstrumentBadge.java` · `query/SnapshotFactsMapper.java` · `view/SnapshotViewService.java` | 종목별 행 `instrument_id` |
| `M:query/InstrumentDetailMapper.java` · `InstrumentHeaderRow` · `InstrumentLineRow` · `InstrumentBasisRow` · `InstrumentTradeRow` · `InstrumentActionRow`(모두 신규, `query/`) | 상세 재료 |
| `M:query/RealizedPnlMapper.java` · `src/main/resources/mapper/RealizedPnlMapper.xml` | 종목 단위 실현손익 |
| `src/main/resources/db/sample/sample_portfolio.sql` | TRUNCATE에 `cln_trade` · `corporate_action` 추가 |
| `M:view/assembly/AssemblyContext.java` · `NoticeCollector.java` | 종목 하나용 `CA_UNKNOWN` 문구 |
| `M:api/dto/InstrumentDetailData.java`(신규) · `view/InstrumentDetailAssembler.java`(신규) | 응답 모양 · 조립 |
| `M:view/InstrumentDetailViewService.java` · `api/InstrumentDetailController.java`(신규) · `api/RequestParams.java` | 순서 · 404 |
| `src/test/resources/golden/instrument-detail.json`(신규) · `positions.json` | 골든(앱이 `front-end/src/fixtures/golden/`로 복사) |
| `T:alert/data/HoldingReaderFinalTest.java` · `alert/api/InstrumentSearchApiTest.java` · `alert/api/AlertCommandApiTest.java` | 보유 기준 |
| `T:alert/evaluation/ConditionEvaluatorTest.java` · `alert/sentence/SentenceWriterTest.java` · `alert/api/AlertPreviewApiTest.java` · `alert/runtime/EvaluationRunnerTest.java` · `alert/runtime/PreviewEvaluatorParityTest.java` · `alert/api/AlertRuntimeFlowTest.java` | `AWAITING_FINAL` · 미리보기 |
| `T:api/SnapshotViewApiTest.java` · `api/SixViewGoldenTest.java` | `instrument_id` · 골든 |
| `T:query/InstrumentDetailMapperTest.java` · `view/InstrumentDetailAssemblerTest.java` · `api/InstrumentDetailApiTest.java`(신규) · `view/assembly/NoticeCollectorTest.java` | 상세 |

---

## 픽스처 수치

`sample_portfolio.sql` 기준(as_of 2026-07-27 확정 전, 07-24 확정 · `snapshot_run` 07-24는 `sample_alert_market.sql`). 상수: yhr `40000000-…-0001`, jdh `…-0002`, test_empty `…-0004`. 계좌 `20000000-…-000N`: 1 한국투자 위탁(yhr, `ar_7f3a91c4`) · 2 국내주식(yhr, `ar_2b8e05da`) · 4 연금저축(yhr, 이월) · 5 한국투자 주식(jdh, `ar_53c0ab29`). 종목 `10000000-…-000N`: 1 005930 · 2 000660 · 3 NAVER · 5 MSFT · 7 CASH-KRW.

| 경우 | 준비(테스트 안 주입) | 기대 |
|---|---|---|
| yhr 005930 그대로 | — | position 200 · 60000 · 원가 12,000,000 · 평가 14,240,000 · 손익 2,240,000 · 18.7. by_account [계좌1 200 · 60000 · 14,240,000 · 이월 false · `2026-07-27T15:30:00+09:00` · basis null]. realized 277,000 / 0, rows [T-0002, T-0001]. notices [] |
| 두 계좌 분할 | 07-27 계좌2 × 005930: 50주 · 원가 3,000,000 · 평가 3,560,000 · fx 1 · 확정 전 | position 250 · 60000 · 15,000,000 · 17,800,000 · 2,800,000 · 18.7. by_account [계좌1, 계좌2]. 종목별 행 005930도 250 · 60000 |
| yhr MSFT(외화 · 이월) | — | position 10 · 300.00 · 4,200,000 · 4,900,000 · 700,000 · 16.7 · 현지 평가 3,500 · 원가 3,000. by_account [계좌4 · 이월 true · `2026-07-24T15:30:00+09:00` · 현지 평가 3,500]. notices [FX_APPLIED `USD/KRW 1,400.00 적용 · 기준 2026-07-24`] |
| yhr NAVER | — | position 40 · 225000 · 9,000,000 · 8,000,000 · −1,000,000 · −11.1. realized −305,000 / excluded 1(T-0004 CONFLICT), rows [T-0003]. notices [CA_UNKNOWN](T-0003 `ca_unknown`) |
| 판 종목 | yhr 07-27 계좌2 × NAVER 라인 삭제 | position null · by_account [] · realized 그대로 |
| 아무것도 없음 | jdh × 000660 | position null · 목록 모두 빔 · instrument 채움(last_close 109000 · 2026-09-25) |
| 오늘 산 종목 | 07-27 계좌5(jdh) × NAVER: 10주 · 2,000,000 / 2,000,000 · 확정 전 | jdh `held` 참 · 최신 확정(07-24)에는 없음 |
| 오늘 판 종목 | yhr 07-27 계좌2 × NAVER 라인 삭제 | yhr `held` 거짓 · 07-24 확정에는 있음 |

거래내역 주입(종목 005930): `B-0001` 계좌1 BUY 200 @60000 `2026-01-05T09:10:00+09` · `S-0002` 계좌1 SELL 5 @140000 fee 2000 `2026-05-12T10:02:00+09` · `S-0003`과 `S-0004` 계좌1 SELL 1 @70000 같은 시각 `2026-07-21T15:30:00Z` · `J-0001` 계좌5(jdh) · `N-0001` 계좌2 NAVER. yhr 기대 순서 `S-0003, S-0004, S-0002, B-0001`, `S-0003.executed_at = 2026-07-22T00:30:00+09:00`, `executed_on = 2026-07-22`. `trade_date`는 체결 시각의 서울 날짜로 넣는다.

골든 `instrument-detail.json`(yhr 005930, `@Sql` 두 파일) — `last_close`는 `sample_alert_market.sql`의 마지막 일봉(2026-09-25, 63,010):

```json
{ "as_of": "2026-07-27T15:30:00+09:00",
  "data": {
    "instrument": { "id": "10000000-0000-0000-0000-000000000001", "symbol": "005930", "label": "삼성전자",
                    "market": "KR", "currency": "KRW", "delisted_on": null,
                    "last_close": 63010, "last_close_on": "2026-09-25" },
    "position": { "quantity": 200, "avg_cost": 60000, "cost_amount_krw": 12000000,
                  "market_value_krw": 14240000, "unrealized_pnl_krw": 2240000, "unrealized_pnl_pct": 18.7 },
    "by_account": [ { "account_id": "20000000-0000-0000-0000-000000000001", "label": "한국투자 위탁",
                      "account_type": "GENERAL", "quantity": 200, "avg_cost": 60000, "market_value_krw": 14240000,
                      "is_carried_forward": false, "source_as_of": "2026-07-27T15:30:00+09:00", "basis": null } ],
    "realized": { "total": { "realized_pnl_krw": 277000, "excluded_account_count": 0 },
      "rows": [
        { "trade_id": "T-0002", "account_id": "20000000-0000-0000-0000-000000000001", "account_label": "한국투자 위탁",
          "sold_at": "2026-05-12", "quantity": 5, "sell_amount_krw": 700000, "cost_basis_krw": 500000,
          "realized_pnl_krw": 198000, "grade": "VERIFIED", "ca_unknown": false },
        { "trade_id": "T-0001", "account_id": "20000000-0000-0000-0000-000000000001", "account_label": "한국투자 위탁",
          "sold_at": "2026-03-02", "quantity": 3, "sell_amount_krw": 400000, "cost_basis_krw": 320000,
          "realized_pnl_krw": 79000, "grade": "SEEDED", "seed_reason": "LATE_COVERAGE",
          "coverage_start_at": "2026-01-01", "ca_unknown": false } ] },
    "trades": [], "corporate_actions": [] },
  "empty_reason": null, "notices": [] }
```

---

### Task 0: 작업 공간과 전용 DB

**Files:** 없음(머신 상태 변경)

- [ ] **Step 1: 아래를 사용자에게 보여 주고 승인받은 뒤 실행한다.**

```bash
cd /Users/yhr/Dev/workspace/personal/stock-project
git -C back-end fetch origin
git -C back-end worktree add -b feat/instrument-detail ../.worktrees/back-end-instrument-detail origin/main
```

- [ ] **Step 2: 전용 DB(같은 승인에 포함해 묻는다).** 로컬 Postgres에 `CREATE DATABASE portfolio_test_instrument_detail OWNER portfolio`, 그 안에 `app` · `data` 스키마를 기존 테스트 DB와 같은 방법(`yhr/plan/2026-10-14-test-environment-setup.md`)으로 만든다.
- [ ] **Step 3: 기준선 [DB].** Global Constraints의 전체 테스트 명령(승인 후). Expected: 전부 통과. 실패가 있으면 이 작업 전의 실패로 기록하고 보고한다.

---

### Task 1: 보유 판정을 한 조각으로 [DB]

**Files:**
- Create: `M:query/SharedSql.java`
- Modify: `M:alert/data/HoldingMapper.java`, `HoldingReader.java`, `M:alert/store/InstrumentSearchMapper.java`, `M:alert/service/InstrumentSearchService.java`, `M:alert/validation/InstrumentFacts.java`(주석)
- Test: `T:alert/data/HoldingReaderFinalTest.java`, `T:alert/api/InstrumentSearchApiTest.java`, `T:alert/api/AlertCommandApiTest.java`

**Interfaces:**
- Produces: `public final class SharedSql` — `public static final String HELD_LINE`: `position_line` 행을 고르는 `SELECT pl.* …` 문(괄호로 감싸 하위질의로 쓴다). 조건은 `pl.as_of = #{asOf}` · `a.user_id = #{scope.userId}` · `a.link_state <> 'DISCONNECTED'` · `pl.quantity > 0`. 파라미터는 `scope` · `asOf` 둘이고, `asOf`는 부르는 쪽이 `SnapshotCalendarRepository.latestAsOf`로 정해 넘긴다 — 날짜를 정하는 곳도 하나다. `asOf`가 null이면 행이 없다. `<script>` 없는 `@Select`에서만 쓴다(`<>`를 이스케이프하지 않는다 — 조각 주석에 적는다). `public static final String LAST_CLOSE` — `InstrumentSearchMapper.LAST_CLOSE`를 그대로 옮긴 것(별칭 `i` 기준 `LEFT JOIN LATERAL … lc`).
- Produces: `HoldingMapper.heldAt(@Param("scope") UserScope scope, @Param("asOf") LocalDate asOf, @Param("instrumentId") UUID instrumentId): boolean` — `SELECT EXISTS (SELECT 1 FROM (HELD_LINE) h WHERE h.instrument_id = #{instrumentId})`.
- Produces: `HoldingReader(HoldingMapper, AggregateQueryRepository, SnapshotCalendarRepository)`. `held(UserScope, InstrumentRow)` 시그니처 그대로, 몸통은 `calendar.latestAsOf(scope).map(d -> mapper.heldAt(scope, d, id)).orElse(false)`. `latestFinal` · `holding`은 바꾸지 않는다.
- Produces: `InstrumentSearchMapper.HELD` = `WITH held AS (SELECT DISTINCT h.instrument_id FROM (HELD_LINE) h)`. 메서드는 `search(scope, @Param("asOf") LocalDate asOf, q, pattern, limit)` · `held(scope, @Param("asOf") LocalDate asOf)`. `InstrumentSearchService`가 `calendar.latestAsOf(scope).orElse(null)`을 넘긴다.

- [ ] **Step 1: 실패하는 테스트.** 오늘 산 / 오늘 판 준비는 픽스처 표 그대로.
  - `HoldingReaderFinalTest.확정_전_라인에만_있는_종목도_보유다`: 오늘 산 준비 → `held(JDH, NAVER)` 참, `latestFinal(JDH)`는 여전히 07-24, `holding(JDH, 07-24, NAVER)` null(평가 입력은 확정 스냅샷).
  - `HoldingReaderFinalTest.확정에는_있고_최신에는_없는_종목은_보유가_아니다`: 오늘 판 준비 → `held(YHR, NAVER)` 거짓, `holding(YHR, 07-24, NAVER)`는 null 아님.
  - `InstrumentSearchApiTest.오늘_산_종목은_검색에서_보유다`: 오늘 산 준비 → jdh `q=NAVER`의 `held` 참, `held=true` 구역 라벨에 `NAVER`. `오늘_판_종목은_검색에서_보유가_아니다`: 오늘 판 준비 → yhr `q=NAVER` `held` 거짓, `held=true` 구역에 없음.
  - `AlertCommandApiTest.오늘_산_종목에_수익률_조건을_만들_수_있다`: 오늘 산 준비 → jdh `POST /alerts` pnl_reach(기존 `보유하지_않은_종목에_수익률_조건은_만들_수_없다`와 같은 본문) → 201. `오늘_판_종목에_수익률_조건은_만들_수_없다`: 오늘 판 준비 → yhr 400 · `NOT_HELD`.
- [ ] **Step 2: 실행해 실패를 확인한다.** `--tests '*HoldingReaderFinalTest' --tests '*InstrumentSearchApiTest' --tests '*AlertCommandApiTest'`. Expected: 새 테스트 6개 FAIL(오늘 산 종목 거짓 · 오늘 판 종목 참), 기존 테스트 PASS.
- [ ] **Step 3: 구현.** 위 Interfaces대로. `SharedSql` 클래스 주석: "앱 어디서나 '지금 보유 중인가'는 이 조각 하나로 판정한다 — 그 사용자의 최신 스냅샷(확정 전 포함, `SnapshotCalendarRepository.latestAsOf`)에서 연동 중인 계좌에 수량이 있는 라인. 종목 상세 · 종목 검색 · 알림 생성과 평가의 보유 확인이 쓴다. 알림의 수익률 · 비중은 확정 스냅샷을 따로 읽는다."
- [ ] **Step 4: 통과 확인.** 같은 명령 + `--tests '*HoldingReaderDisconnectedTest' --tests '*AlertPreviewApiTest'`. Expected: PASS(해제 계좌 테스트는 샘플에서 결과가 같다). `AlertPreviewApiTest`의 NOT_HELD 케이스도 이 단계에서는 그대로 통과해야 한다.
- [ ] **Step 5: 커밋(요청 시).** `feat: 보유 중 판정을 최신 스냅샷 한 조각으로 모은다`

---

### Task 2: 확정 전 보유 `AWAITING_FINAL`과 미리보기 현재값 [단위 + DB]

**Files:**
- Create: `src/main/resources/db/migration/V16__alert_reason_awaiting_final.sql`
- Modify: `M:alert/evaluation/UnknownReason.java`, `M:alert/indicator/Series.java`, `M:alert/evaluation/ConditionEvaluator.java`, `M:alert/data/EvaluationInputFactory.java`, `M:alert/sentence/SentenceWriter.java`, `M:alert/service/AlertPreviewService.java`
- Test: `T:alert/evaluation/ConditionEvaluatorTest.java`, `T:alert/sentence/SentenceWriterTest.java` [단위] · `T:alert/api/AlertPreviewApiTest.java`, `T:alert/runtime/EvaluationRunnerTest.java`, `T:alert/runtime/PreviewEvaluatorParityTest.java`, `T:alert/api/AlertRuntimeFlowTest.java` [DB]

**Interfaces:**
- Consumes: `HoldingReader.held`(Task 1).
- Produces: `UnknownReason.AWAITING_FINAL("오늘 저녁 첫 판정")` — 라벨은 카드 문구다.
- Produces: `record Series(List<Bar> bars, List<FlowBar> flows, List<Snapshot> snapshots, Holding holding, boolean heldNow)`. `heldNow`는 "확정 스냅샷에 그 종목 행이 없지만 공유 판정으로는 지금 보유 중"이고 `holding`이 있으면 늘 거짓이다. 기존 4인자 생성자는 `heldNow = false`로 위임해 남긴다(기존 호출부 그대로). `Series.empty()`도 거짓.
- Produces: `EvaluationInputFactory.userAt(UserScope, InstrumentRow, Cadence, LocalDate, Set<DataKind>)` 시그니처 그대로, 몸통은 `holding = holdings.holding(scope, date, instrument)`, `heldNow = holding == null && holdings.held(scope, instrument)`로 `new Series(List.of(), List.of(), List.of(), holding, heldNow)`. 미리보기(`forPreview`)와 평가기(`EvaluationRunner`)가 모두 이 메서드로 사용자 상태 입력을 만들므로 두 경로가 같은 입력을 받는다. `EvaluationRunner`는 바꾸지 않는다.
- Produces: `ConditionEvaluator.absent`의 사용자 상태 분기 — `holding == null`이면 `heldNow ? AWAITING_FINAL : NOT_HELD`. 결과는 `UNKNOWN`이라 발화하지 않는다(`FiringRule`은 그대로).
- Produces: `SentenceWriter.AWAITING_FINAL_TEXT = "오늘 저녁 확정 후 첫 판정을 해요"`. `unknownText`와 `presetUnknownText`가 `AWAITING_FINAL`에는 라벨 대신 이 문장을 쓴다 — 줄은 `{조건 이름} — 오늘 저녁 확정 후 첫 판정을 해요`(프리셋은 `{presetShort} — …`).
- Produces: `AlertPreviewService.preview` — 오류에 `code = NOT_HELD`가 있으면 `current = null`(따라서 `already_satisfied` · `already_fired` 거짓). 그 밖의 현재값 계산은 그대로이고 응답 DTO도 그대로.
- Produces: `V16__alert_reason_awaiting_final.sql` — `ALTER TABLE alert_state DROP CONSTRAINT alert_state_reason, ADD CONSTRAINT alert_state_reason CHECK (unknown_reason IS NULL OR unknown_reason IN ('DATA_MISSING', 'INSUFFICIENT_HISTORY', 'NO_TRADE', 'PRICE_ADJUSTMENT_SUSPECTED', 'NOT_HELD', 'INSTRUMENT_UNKNOWN', 'AWAITING_FINAL'))`(기존 목록은 `V4__alert_tables.sql:52-54`). 머리 주석: "확정 전 보유를 판정을 기다리는 상태로 저장한다".

**영향 범위:** 오늘 산 종목의 사용자 상태 알림이 알림 목록 · 상세의 `unknown_reason`으로 `AWAITING_FINAL`을 내고(앱이 카드 문구를 더한다), 편집기 · 알림 상세의 현재값 상자 줄이 `… — 오늘 저녁 확정 후 첫 판정을 해요`가 된다. `NOT_HELD` 검증 오류가 난 미리보기는 현재값 상자가 없다. 기존 알림에는 생성 검증의 `NOT_HELD`가 없으므로 진짜 미보유 알림은 계속 `NOT_HELD` · `… — 미보유`다. 발화 · 이벤트 본문(`EventText`)은 바뀌지 않는다.

- [ ] **Step 1: 실패하는 테스트.** 오늘 산 / 오늘 판 준비는 픽스처 표. 평가기 테스트는 `EvaluationRunnerTest`의 `runner(AT_10_20)` · `evaluatedAsOf` · `lastResult` · `bodies` 도우미를 쓴다.
  - `ConditionEvaluatorTest.확정_스냅샷에_없어도_지금_보유_중이면_첫_판정_대기다` [단위]: 수익률 조건, `Series(…, null, true)` → `UNKNOWN · AWAITING_FINAL`. `Series(…, null, false)` → `UNKNOWN · NOT_HELD`. 시장 조건은 `heldNow`와 무관.
  - `SentenceWriterTest.확정_전_보유의_수익률_줄은_첫_판정_안내다` [단위]: 기존 `손실 10% 도달 — 미보유` 예와 같은 pnl 프리셋에 `AWAITING_FINAL` 결과 → `new Line(UNKNOWN, AWAITING_FINAL, "손실 10% 도달 — 오늘 저녁 확정 후 첫 판정을 해요")`. `UnknownReason.AWAITING_FINAL.label()`은 `오늘 저녁 첫 판정`.
  - `AlertPreviewApiTest.오늘_산_종목의_수익률_미리보기는_첫_판정_안내다` [DB]: 오늘 산 준비 → jdh NAVER pnl_reach 미리보기 → `errors` 비어 있음, `current.result = UNKNOWN`, 줄 `unknown_reason = AWAITING_FINAL` · text `수익 10% 도달 — 오늘 저녁 확정 후 첫 판정을 해요`(관측 수익률 숫자 없음).
  - `AlertPreviewApiTest.오늘_판_종목의_수익률_미리보기는_현재값이_없다` [DB]: 오늘 판 준비 → yhr NAVER → `errors[0].code = NOT_HELD`, `current`가 JSON null, `already_satisfied` 거짓.
  - 기존 테스트를 설계에 맞춰 바꾼다: `미보유_종목의_수익률_도달은_오류이지만_지금_값을_보인다` → `미보유_종목의_수익률_도달은_오류이고_현재값이_없다`(`current` null). `계좌를_모두_해제하면_수익률_도달의_지금_값은_미보유다` → `계좌를_모두_해제하면_수익률_도달은_NOT_HELD이고_현재값이_없다`.
  - `EvaluationRunnerTest.오늘_산_종목의_수익률_알림은_어제_확정으로_평가해도_첫_판정_대기다` [DB]: 오늘 산 준비 → `commands.create(JDH, pnlReach(NAVER, "5"))` → tick → `evaluatedAsOf` 2026-07-24 15:30+09, `last_result = UNKNOWN`, `unknown_reason = AWAITING_FINAL`, `bodies(id)` 빔.
  - `EvaluationRunnerTest.저녁_확정_라인이_생기면_실제_결과로_바뀐다` [DB]: 위에 이어 jdh 07-27 라인을 `is_final = true`로, `snapshot_run`에 `('2026-07-27', '2026-07-27T18:00:00+09')` → tick → `evaluatedAsOf` 2026-07-27 15:30+09, `last_result = FALSE`(NAVER 손익률 0%), `unknown_reason` null.
  - `EvaluationRunnerTest.지금도_보유하지_않으면_미보유다` [DB]: yhr NAVER pnl 알림을 만든 뒤 계좌2의 07-24 · 07-27 NAVER 라인을 지운다 → tick → `NOT_HELD`(대조군).
  - `PreviewEvaluatorParityTest.오늘_산_종목도_미리보기와_평가기의_결과가_같다` [DB]: 오늘 산 준비 → jdh로 미리보기 · 생성 · tick → `alert_state`의 `last_result` · `unknown_reason`이 미리보기 `current`의 `result` · 첫 `unknown_reason`(`UNKNOWN` · `AWAITING_FINAL`)과 같고, `as_of`가 `evaluated_as_of`와 같은 순간. 기존 파라미터 테스트의 도우미(`stateText` · `firstUnknownReason`)를 쓴다.
  - `AlertRuntimeFlowTest.오늘_산_종목의_알림은_목록과_상세에서_첫_판정_대기다` [DB]: 오늘 산 준비 → jdh `POST /alerts` pnl_reach → `runner.tick()` → `GET /alerts`의 그 행과 `GET /alerts/{id}` 모두 `last_result = UNKNOWN` · `unknown_reason = AWAITING_FINAL`, `alert_event`에 그 알림 행 없음.
- [ ] **Step 2: 실행해 실패를 확인한다.** `./gradlew test --tests '*ConditionEvaluatorTest' --tests '*SentenceWriterTest'`(DB 없음) → 컴파일 실패. DB 테스트(승인 후) `--tests '*AlertPreviewApiTest' --tests '*EvaluationRunnerTest' --tests '*PreviewEvaluatorParityTest' --tests '*AlertRuntimeFlowTest'` → 새 테스트와 바꾼 2개 FAIL.
- [ ] **Step 3: 구현.** 위 Interfaces대로. `Series.heldNow` 주석: "확정 스냅샷에는 그 종목이 없지만 최신 스냅샷(확정 전 포함)으로는 보유 중이다 — 오늘 산 종목. 미보유가 아니라 그날 저녁 확정을 기다리는 상태로 판정한다."
- [ ] **Step 4: 통과 확인.** 위 단위 · DB 명령 + `--tests '*AlertQueryApiTest' --tests '*AlertFlowApiTest' --tests '*EvaluationInputFactoryTest' --tests '*AlertSchemaTest' --tests '*MigrationLintTest'`. Expected: PASS(기존 동등성 파라미터 케이스는 샘플에 오늘 산 종목이 없어 그대로다).
- [ ] **Step 5: 커밋(요청 시).** `feat: 확정 전 보유를 첫 판정 대기로 판정한다`

---

### Task 3: 종목별 행의 `instrument_id` [DB]

**Files:**
- Modify: `M:query/InstrumentBadge.java`, `M:query/SnapshotFactsMapper.java`, `M:view/SnapshotViewService.java`, `src/test/resources/golden/positions.json`
- Test: `T:api/SnapshotViewApiTest.java`, `T:api/SixViewGoldenTest.java`, `T:api/LookThroughGoldenTest.java`(변경 없이 통과 확인)

**Interfaces:**
- Produces: `record InstrumentBadge(String symbol, String market, UUID instrumentId)` — `instrumentId`는 예수금 · 렌즈 배지에서 null. `instrumentBadges`는 `CASE WHEN i.asset_class <> 'CASH' THEN i.instrument_id END AS instrument_id`를 더한다. `badgesFor`는 `NULL::uuid AS instrument_id`.
- Produces: `SnapshotViewService.rowFields`의 POSITIONS 분기 — `market`은 지금처럼, `lens == DIRECT && badge.instrumentId() != null`일 때만 `instrument_id`(문자열)를 같은 행 맵에 더한다. 다른 화면의 `rowFields`는 그대로.

- [ ] **Step 1: 실패하는 테스트.** `SnapshotViewApiTest.종목_행에만_종목_ID가_있다`: yhr `/portfolio/views/positions` 005930 행 `instrument_id = 10000000-0000-0000-0000-000000000001`, `CASH-KRW` · `CASH-USD` 행에 키 없음, `/portfolio/views/allocation?axis=instrument` 행에 키 없음. `종목_ID는_렌즈_응답에_없다`(메서드 `@Sql` 두 파일: `sample_portfolio.sql`, `sample_lookthrough.sql`): `lens=LOOK_THROUGH` 모든 행에 키 없음.
- [ ] **Step 2: 실행해 실패를 확인한다.** Expected: 키 없음으로 FAIL.
- [ ] **Step 3: 구현과 골든.** 위대로 구현하고 `positions.json`의 비현금 6행에 `instrument_id`를 손으로 더한다(005930 `…0001`, 133690 `…0006`, 000660 `…0002`, 035420 `…0003`, AAPL `…0004`, MSFT `…0005`). 응답을 붙여 넣지 않는다.
- [ ] **Step 4: 통과 확인.** `--tests '*SnapshotViewApiTest' --tests '*SixViewGoldenTest' --tests '*LookThroughGoldenTest'`. Expected: PASS(렌즈 골든은 바뀌지 않는다).
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목별 행에 종목 ID를 싣는다`

---

### Task 4: 상세 재료 매퍼 [DB · 단위]

**Files:**
- Create: `M:query/InstrumentDetailMapper.java`, `InstrumentHeaderRow.java`, `InstrumentLineRow.java`, `InstrumentBasisRow.java`, `InstrumentTradeRow.java`, `InstrumentActionRow.java`
- Modify: `M:query/RealizedPnlMapper.java`, `src/main/resources/mapper/RealizedPnlMapper.xml`, `src/main/resources/db/sample/sample_portfolio.sql`
- Test: `T:query/InstrumentDetailMapperTest.java`(신규), `T:auth/ScopeSignatureTest.java`(변경 없이 통과)

**Interfaces:**
- Consumes: `SharedSql.HELD_LINE` · `LAST_CLOSE`(Task 1).
- Produces(모두 첫 파라미터 `@Param("scope") UserScope`, `ScopeSignatureTest` 규칙):
  - `InstrumentHeaderRow instrument(scope, @Param("id") UUID id)` — 없으면 null. `record InstrumentHeaderRow(UUID id, String symbol, String label, String assetClass, String market, String currency, LocalDate delistedOn, BigDecimal lastClose, LocalDate lastCloseOn)`. 종목 마스터는 공용이라 범위를 조건에 걸지 않는다(`badgesFor`와 같은 주석).
  - `List<InstrumentLineRow> heldLines(scope, @Param("asOf") LocalDate asOf, @Param("instrumentId") UUID)` — `FROM (HELD_LINE) h WHERE h.instrument_id = …`. `asOf`는 서비스가 `latestAsOf`로 정해 불변식 · 배너와 같은 날짜를 넘긴다. `record InstrumentLineRow(UUID accountId, BigDecimal quantity, BigDecimal costAmountLocal, BigDecimal marketValueLocal, BigDecimal costAmountKrw, BigDecimal marketValueKrw, BigDecimal fxRate, LocalDate fxAsOf, OffsetDateTime sourceAsOf, boolean carriedForward)`.
  - `List<InstrumentBasisRow> basis(scope, instrumentId)` — `position_basis` × 내 계좌. `record InstrumentBasisRow(UUID accountId, Grade grade, boolean seedPermanent, LocalDate coverageStartAt, boolean caUnknown)`.
  - `List<InstrumentTradeRow> trades(scope, instrumentId)` — `cln_trade t JOIN account a ON a.account_ref = t.account_ref`, 내 계좌(해제 포함). `record InstrumentTradeRow(String tradeId, UUID accountId, String side, BigDecimal quantity, BigDecimal price, BigDecimal fee, BigDecimal tax, String currency, OffsetDateTime executedAt)`.
  - `List<InstrumentActionRow> corporateActions(scope, instrumentId)` — `record InstrumentActionRow(String type, BigDecimal ratio, LocalDate exDate)`.
  - `RealizedPnlMapper.findByInstrument(scope, @Param("instrumentId") UUID): List<RealizedPnlRow>` — 전 기간, 계좌 소유로 범위(해제 포함). XML에서 `findByPeriod`와 열 목록을 `<sql id="rowColumns">`로 공유한다.
  - 정렬은 SQL이 아니라 조립기(Task 6)가 한다.
- `sample_portfolio.sql`: TRUNCATE 목록에 `cln_trade, corporate_action`을 더하고 주석 "체결 · 기업행위는 비운 채로 둔다 — 실현손익 행만 있고 체결은 없는 상태가 이 샘플의 기준이다". 이유: 지금 목록(`sample_portfolio.sql:9-10`)에는 두 표가 없어, 이 계획의 테스트가 넣은 체결 · 기업행위 행이 샘플을 다시 적재한 다음 테스트로 남는다 — 골든의 `trades` · `corporate_actions`가 빈 목록이 아니게 되고, 기업행위는 사용자 범위도 없어 어느 사용자 응답에나 붙는다. 평단 계산 테스트는 `BasisFixture.java:29`에서 두 표를 스스로 TRUNCATE하므로 이 변경의 영향을 받지 않는다.

- [ ] **Step 1: 실패하는 테스트(`InstrumentDetailMapperTest`, `@Sql` 두 파일).** 거래내역 주입은 픽스처 표.
  - `heldLines`는 모두 `asOf = 2026-07-27`로 부른다.
  - `세_블록_모두_내_계좌만_읽는다`: yhr 005930 `heldLines` 계좌 `[…0001]`, `trades` id 집합 `{B-0001, S-0002, S-0003, S-0004}`(J-0001 · N-0001 없음), `findByInstrument` id 집합 `{T-0001, T-0002}`(T-1001 없음). jdh는 각각 `[…0005]` · `{J-0001}` · `{T-1001}`.
  - `해제한_계좌의_라인은_빠지고_체결과_실현손익은_남는다`: 계좌1 `DISCONNECTED` → yhr 005930 `heldLines` 빔, `trades` 4건, `findByInstrument` 2건.
  - `넘긴_날짜의_라인만_읽는다`: yhr 005930 `heldLines(…, 2026-07-24, …)` → 1행이고 평가 13,040,000(07-24 단가 65,200).
  - `이월_라인의_시각과_표시가_실린다`: yhr MSFT `heldLines` 1행 `carriedForward` 참, `sourceAsOf`가 `2026-07-24T15:30+09:00`과 같은 순간, `fxAsOf` 07-24.
  - `등급_행을_읽는다`: 계좌1 × 005930 `position_basis` SEEDED(`avg_cost_*` 60000, `seed_avg_price` 60000, `coverage_start_at` 2026-01-01, `seed_permanent` false, `opening_qty` 200, `evaluated_qty` 200, `evaluated_as_of` 07-27) → `InstrumentBasisRow(…0001, SEEDED, false, 2026-01-01, false)`.
  - `종목_헤더와_직전_종가`: 005930 `lastClose` 63010 · `lastCloseOn` 2026-09-25 · `assetClass` STOCK. 없는 UUID → null. `corporateActions`: `corporate_action`에 005930 SPLIT 2 2026-04-01 주입 → 1행.
- [ ] **Step 2: 실행해 실패를 확인한다.** Expected: 컴파일 실패.
- [ ] **Step 3: 구현.** 위대로. 매퍼 클래스 주석에 "라인은 보유 판정 조각을 그대로 써 종목별 화면 · 검색 · 알림과 같은 라인을 본다. 체결 · 실현손익은 이미 판 계좌와 해제한 계좌의 것도 내 계좌면 읽는다."
- [ ] **Step 4: 통과 확인.** `--tests '*InstrumentDetailMapperTest' --tests '*RealizedPnlApiTest' --tests '*BasisBuilderTest'` [DB], `./gradlew test --tests '*ScopeSignatureTest' --tests '*ArchitectureRulesTest'` [단위]. Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목 상세의 재료를 내 계좌 범위로 읽는다`

---

### Task 5: 종목 하나용 `CA_UNKNOWN` 문구 [단위]

**Files:**
- Modify: `M:view/assembly/AssemblyContext.java`, `NoticeCollector.java`
- Test: `T:view/assembly/NoticeCollectorTest.java`

**Interfaces:**
- Produces: `AssemblyContext`에 컴포넌트 `boolean caUnknownForInstrument`(`caUnknownInstruments` 다음). `Builder.caUnknownInstrument(String instrumentId)` — `caUnknownInstruments = List.of(instrumentId)`, 플래그 참. 플래그가 참이면 `CA_UNKNOWN` 문구는 `기업행위 이력을 확인하지 못해 실현손익이 다를 수 있습니다`, params `instrument_ids = [id]`, severity `warn`. 아니면 지금 문구.

- [ ] **Step 1: 실패하는 테스트.** `종목_하나를_보는_화면의_CA_UNKNOWN은_개수를_세지_않는다`: `builder(AS_OF).caUnknownInstrument("id-1")` → 메시지 위 문장, `instrument_ids` `["id-1"]`, severity `warn`. 기존 `N개 종목은 …` 테스트는 그대로 통과.
- [ ] **Step 2: 실행해 실패를 확인한다.** `./gradlew test --tests '*NoticeCollectorTest'`. Expected: 컴파일 실패.
- [ ] **Step 3: 구현.**
- [ ] **Step 4: 통과 확인.** 같은 명령. Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목 상세의 기업행위 미확인 안내 문구를 둔다`

---

### Task 6: 응답 모양과 조립 [단위]

**Files:**
- Create: `M:api/dto/InstrumentDetailData.java`, `M:view/InstrumentDetailAssembler.java`
- Test: `T:view/InstrumentDetailAssemblerTest.java`(신규)

**Interfaces:**
- Produces: `record InstrumentDetailData(Instrument instrument, Position position, List<AccountLine> byAccount, Realized realized, List<Trade> trades, List<CorporateAction> corporateActions)`, 중첩 레코드(이름은 SNAKE_CASE로 직렬화된다):
  - `Instrument(UUID id, String symbol, String label, String market, String currency, LocalDate delistedOn, BigDecimal lastClose, LocalDate lastCloseOn)`
  - `Position(BigDecimal quantity, BigDecimal avgCost, BigDecimal costAmountKrw, BigDecimal marketValueKrw, BigDecimal unrealizedPnlKrw, BigDecimal unrealizedPnlPct, @JsonInclude(NON_NULL) BigDecimal marketValueLocal, @JsonInclude(NON_NULL) BigDecimal costAmountLocal)`
  - `AccountLine(UUID accountId, String label, String accountType, BigDecimal quantity, BigDecimal avgCost, BigDecimal marketValueKrw, @JsonInclude(NON_NULL) BigDecimal marketValueLocal, boolean isCarriedForward, OffsetDateTime sourceAsOf, Basis basis)`
  - `Basis(String grade, @JsonInclude(NON_NULL) String seedReason, @JsonInclude(NON_NULL) LocalDate coverageStartAt, boolean caUnknown)`
  - `Realized(Total total, List<RealizedRow> rows)`, `Total(BigDecimal realizedPnlKrw, int excludedAccountCount)`
  - `RealizedRow(String tradeId, UUID accountId, String accountLabel, LocalDate soldAt, BigDecimal quantity, BigDecimal sellAmountKrw, BigDecimal costBasisKrw, BigDecimal realizedPnlKrw, String grade, @JsonInclude(NON_NULL) String seedReason, @JsonInclude(NON_NULL) LocalDate coverageStartAt, boolean caUnknown)`
  - `Trade(String tradeId, UUID accountId, String accountLabel, String side, BigDecimal quantity, BigDecimal price, BigDecimal fee, BigDecimal tax, String currency, OffsetDateTime executedAt, LocalDate executedOn)`
  - `CorporateAction(String type, BigDecimal ratio, LocalDate exDate)`
- Produces: `final class InstrumentDetailAssembler`, 생성자 `(ZoneId zone)`:
  - `InstrumentDetailData assemble(InstrumentHeaderRow header, List<InstrumentLineRow> lines, List<InstrumentBasisRow> basis, List<RealizedPnlRow> realized, List<InstrumentTradeRow> trades, List<InstrumentActionRow> actions, List<AccountRow> accounts)`
  - `static List<FxApplied> fxApplied(InstrumentHeaderRow header, List<InstrumentLineRow> lines)` — 원화 종목이면 빈 목록, 아니면 `fxAsOf`가 가장 이른 라인 하나로 `FxApplied(currency + "/KRW", fxRate, fxAsOf)`.
  - `static boolean caUnknown(List<InstrumentLineRow> lines, List<InstrumentBasisRow> basis, List<RealizedPnlRow> realized)` — `by_account`에 실린 계좌(= `lines`의 계좌)의 basis 중 하나, 또는 실현손익 행(제외 등급 포함) 중 하나라도 `caUnknown`.
- 규칙(구현이 지킨다): `position`은 라인이 없으면 null. 평단 · 손익률은 합산한 `MeasureBundle`(securities 슬롯)에 `Derived.avgCost(bundle, CurrencyCode.valueOf(currency))` · `Derived.unrealizedPnlPct`를 쓴다 — 종목별 응답과 같은 코드. 계좌 줄도 그 계좌 라인 하나로 만든 묶음에 같은 함수. 현지 금액 키는 `currency != KRW`일 때만 값을 넣는다. `basis`는 `seedPermanent`면 `NOT_TRADED`, SEEDED이고 아니면 `LATE_COVERAGE` + `coverageStartAt`, 그 밖 등급은 둘 다 null, 행이 없으면 null. 정렬: 계좌 `marketValueKrw` 내림 → `accountId.toString()` 오름(UUID의 `compareTo`는 부호 있는 비교라 쓰지 않는다), 실현 `soldAt`(시각) 내림 → `tradeId` 오름, 체결 `executedAt` 내림 → `tradeId` 오름, 기업행위 `exDate` 내림 → `type` 오름. 시각은 `atZoneSameInstant(zone).toOffsetDateTime()`, 날짜는 그 서울 날짜. 계좌 이름은 `accounts`(해제 포함 전 계좌)에서 찾는다.

- [ ] **Step 1: 실패하는 테스트(`InstrumentDetailAssemblerTest`, DB 없음, `zone = Asia/Seoul`).** 수치는 픽스처 표.
  - `두_계좌_라인을_합산한_뒤_평단을_낸다`: 분할 두 라인 → position 250 · 60000 · 15,000,000 · 17,800,000 · 2,800,000 · 18.7, by_account 순서 `[…0001, …0002]`, Σ수량 250.
  - `평단은_통화_자릿수로_반올림한다`: KRW 3주 · 원가 100 → 33. USD 3주 · 원가 100.00 → 33.33.
  - `원가가_0이면_손익률이_null이다`.
  - `원화_종목은_현지_금액이_없고_외화_종목은_있다`: 005930 → `marketValueLocal` · `costAmountLocal` null. MSFT → 3500 · 3000, 계좌 줄 3500.
  - `평가금액이_같으면_계좌_ID_순이다`.
  - `등급_모양은_저장된_판정을_그대로_옮긴다`: SEEDED+false → `LATE_COVERAGE` · 2026-01-01, SEEDED+true → `NOT_TRADED` · null, UNAVAILABLE · CONFLICT → 둘 다 null, 행 없음 → `basis` null.
  - `믿을_수_없는_매도는_목록과_합계에서_빠지고_계좌만_센다`: VERIFIED 198,000 · SEEDED 79,000 · CONFLICT(계좌2) · UNAVAILABLE(계좌2) → rows 2, total 277,000, excluded 1. 행이 하나도 없으면 total 0 · 0.
  - `매도_시각_내림차순이고_같으면_거래_ID_순이다`, `매도일은_서울_날짜다`: `2026-03-01T15:30:00Z` → `2026-03-02`.
  - `해제한_계좌의_매도에도_계좌_이름이_붙는다`.
  - `체결은_서울_시각과_체결일을_싣는다`: 픽스처 표의 순서와 `S-0003` 값.
  - `원화_종목은_환율_안내가_없다`: 005930 → `fxApplied` 빈 목록. MSFT 두 라인(fx 07-24 · 07-27) → `[USD/KRW 1400 07-24]`.
  - `기업행위_미확인은_등급과_제외된_매도까지_본다`: 실린 계좌 basis 참 → 참, CONFLICT 행만 참 → 참, 모두 거짓 → 거짓, 라인 없는 계좌의 basis만 참 → 거짓.
- [ ] **Step 2: 실행해 실패를 확인한다.** `./gradlew test --tests '*InstrumentDetailAssemblerTest'`. Expected: 컴파일 실패.
- [ ] **Step 3: 구현.** 위 규칙대로. 클래스 주석에 "합산한 뒤 평단 · 비율을 낸다. 라인마다 내린 값을 더하면 종목별 행과 끝전이 갈린다"와 "실현손익과 체결은 따로 읽고 서로 엮지 않는다 — 체결이 없는 실현손익도 보여야 한다".
- [ ] **Step 4: 통과 확인.** 같은 명령 + `--tests '*DerivedTest' --tests '*ArchitectureRulesTest'`. Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목 상세 응답을 조립한다`

---

### Task 7: 서비스 · 컨트롤러 · 404 [DB]

**Files:**
- Create: `M:view/InstrumentDetailViewService.java`, `M:api/InstrumentDetailController.java`
- Modify: `M:api/RequestParams.java`
- Test: `T:api/InstrumentDetailApiTest.java`(신규, `@SpringBootTest @AutoConfigureMockMvc @ActiveProfiles("test") @Sql({sample_portfolio.sql, sample_alert_market.sql})`, 로그인 도우미는 `SixViewGoldenTest`와 같게)

**Interfaces:**
- Consumes: Task 4 매퍼, Task 5 `caUnknownInstrument`, Task 6 조립기.
- Produces: `RequestParams.instrumentId(String raw): UUID` — 파싱 실패면 `new RequestRejected("INSTRUMENT_NOT_FOUND", "종목을 찾을 수 없어요", true)`.
- Produces: `InstrumentDetailViewService.render(UserScope scope, UUID instrumentId): Envelope<InstrumentDetailData>`. 순서가 계약이다:
  1. `header = mapper.instrument(...)`. null이거나 `assetClass = CASH`면 위와 같은 404.
  2. `latest = calendar.latestAsOf(scope)`. 있으면 `invariants.validate(scope, asOf)`(실패는 기존 처리기로 500 `FACT_INVARIANT_VIOLATED`), `lines = mapper.heldLines(scope, asOf, id)` — 불변식 · 라인 · 배너가 이 한 날짜를 쓴다, 배너는 `bannerAsOf.of(facts.currentFactsAt(scope, asOf), asOf)` — 종목별 화면과 같은 호출. 없으면 `lines = []`, 배너는 `OffsetDateTime.now(zone)`.
  3. basis · 실현손익 · 체결 · 기업행위 · `accounts.findAll(scope)`를 읽어 조립.
  4. 안내는 `AssemblyContext.builder(asOf 또는 null).fxApplied(fxApplied(header, lines))`에 `caUnknown(...)`이면 `.caUnknownInstrument(id.toString())`. 다른 항목은 채우지 않는다(그래서 `STALE_ACCOUNTS` · `SYNC_IN_PROGRESS` · `SEEDED_ROWS` · `EXCLUDED_ACCOUNTS`가 실리지 않는다).
  5. `Envelope.of(banner, data, null, notices)` — `empty_reason`은 늘 null.
- Produces: `@RestController @RequestMapping("/portfolio/instruments") InstrumentDetailController`, `@GetMapping("/{id}") Envelope<InstrumentDetailData> detail(UserScope scope, @PathVariable String id)`. 컨트롤러는 매퍼를 모른다(`ArchitectureRulesTest`).

- [ ] **Step 1: 실패하는 테스트(`InstrumentDetailApiTest`).** 준비 · 수치는 픽스처 표.
  - `보유_요약과_계좌별_분해를_낸다`(PF10-01 · 02): yhr 005930 → 골든 표의 position · by_account. `position`에 `market_value_local` 키 없음.
  - `종목별_행과_수량_평단이_같다`(PF10-01): 두 계좌 분할 준비 → 상세 `position.quantity` · `avg_cost` = `/portfolio/views/positions` 005930 행의 값, `Σ by_account.quantity = position.quantity`.
  - `외화_이월_계좌를_그대로_말한다`: yhr MSFT → 픽스처 표 값, 계좌 줄 `is_carried_forward` 참 · `source_as_of` 문자열 `2026-07-24T15:30:00+09:00`, notices 코드 `[FX_APPLIED]`과 그 문구.
  - `원화_종목_상세에는_FX_APPLIED가_없다`: yhr 005930 notices `[]`(같은 사용자 종목별 응답에는 `FX_APPLIED`가 있다 — 대조로 함께 단언).
  - `환율이_오래되면_FX_STALE을_싣는다`: MSFT 07-27 라인 `fx_as_of = 2026-07-10` → notices에 `FX_STALE`(`USD/KRW 환율이 2026-07-10 기준으로 오래됐습니다`).
  - `거래내역을_체결_시각_순으로_낸다`(PF10-03): 거래 주입 → 4건, 순서 · `S-0003` 필드 · `account_label` `한국투자 위탁` · `price` 70000 · `currency` KRW. `거래내역이_없으면_빈_목록이다`(PF10-04): 주입 없이 `trades = []`, `empty_reason` null.
  - `실현손익은_목록에서_뺀_매도를_계좌_수로만_센다`(PF10-05): yhr NAVER → rows `[T-0003]`, total −305,000 / 1. 005930에 UNAVAILABLE 매도(계좌2, `RealizedPnlApiTest.insertTrade`와 같은 모양) 주입 → total 277,000 / 1.
  - `계좌별_등급을_싣는다`(PF10-06): 분할 준비 + 계좌1 SEEDED(Task 4 행) + 계좌2 UNAVAILABLE(`avg_cost_*` · `seed_avg_price` null) → 계좌1 `basis = {grade SEEDED, seed_reason LATE_COVERAGE, coverage_start_at 2026-01-01, ca_unknown false}`, 계좌2 `basis = {grade UNAVAILABLE, ca_unknown false}`(두 키 없음). 계좌4 × MSFT에 SEEDED · `seed_permanent` true(`avg_cost_*` 300 / 420000, `seed_avg_price` 300, `coverage_start_at` null, `opening_qty` · `evaluated_qty` 10) → MSFT 상세 계좌4 `basis = {grade SEEDED, seed_reason NOT_TRADED, ca_unknown false}`(`coverage_start_at` 키 없음). 행을 넣지 않은 상태의 MSFT `basis`는 null.
  - `기업행위를_확인하지_못하면_CA_UNKNOWN을_싣는다`(PF10-07): yhr NAVER → `CA_UNKNOWN` 문구 `기업행위 이력을 확인하지 못해 실현손익이 다를 수 있습니다`, `instrument_ids = ["…0003"]`. T-0003 거짓 · T-0004(CONFLICT) 참으로 바꿔도 실린다. 005930 계좌1 basis `ca_unknown` 참이면 실린다. 모두 거짓이면 없다.
  - `함께_가진_종목에서_남의_계좌가_없다`(N-51): 거래 주입 후 yhr 005930 응답 전체에 `20000000-0000-0000-0000-000000000005` · `…0006` 문자열이 없고, jdh 응답의 by_account는 `[…0005]`, realized rows `[T-1001]`, trades `[J-0001]`.
  - `판_종목은_보유가_없고_실현손익은_남는다`, `아무것도_없는_종목도_머리글은_채운다`: 픽스처 표. `스냅샷이_없는_사용자도_200이다`: test_empty × 005930 → 200, `position` null, `as_of` 있음.
  - `없는_종목은_404다`: 없는 UUID · `abc` · CASH-KRW(`…0007`) 모두 404 · `INSTRUMENT_NOT_FOUND`. 토큰 없이 401.
  - `라인_규칙이_깨지면_종목별과_같이_실패한다`: yhr 07-27 계좌2 라인을 모두 지운다 → 상세 005930과 `/portfolio/views/positions` 모두 500 `FACT_INVARIANT_VIOLATED`.
- [ ] **Step 2: 실행해 실패를 확인한다.** `--tests '*InstrumentDetailApiTest'`. Expected: 404(경로 없음)로 FAIL.
- [ ] **Step 3: 구현.** 위 순서대로. 서비스 클래스 주석에 순서의 이유(존재 확인 → 규칙 확인 → 읽기 → 조립)와 "응답은 종목 하나의 서술이라 비는 것은 영역 하나씩이다 — 빈 이유를 싣지 않는다".
- [ ] **Step 4: 통과 확인.** `--tests '*InstrumentDetailApiTest' --tests '*SnapshotViewApiTest'` [DB], `./gradlew test --tests '*ArchitectureRulesTest' --tests '*ScopeSignatureTest'` [단위]. Expected: PASS.
- [ ] **Step 5: 커밋(요청 시).** `feat: 종목 상세 조회를 연다`

---

### Task 8: 골든 [DB]

**Files:**
- Create: `src/test/resources/golden/instrument-detail.json`
- Modify: `T:api/SixViewGoldenTest.java`

**Interfaces:**
- Produces: 골든 `back-end/src/test/resources/golden/instrument-detail.json`(앱이 `front-end/src/fixtures/golden/instrument-detail.json`으로 복사) · 갱신된 `positions.json`(Task 3).

- [ ] **Step 1: 테스트.** `SixViewGoldenTest`에 `종목_상세_응답이_기대와_일치한다`를 더한다. 메서드에 `@Sql({"classpath:db/sample/sample_portfolio.sql", "classpath:db/sample/sample_alert_market.sql"})` — `last_close`가 일봉 데이터에 달려 있어 두 파일을 다 적는다(메서드 `@Sql`은 클래스 것을 덮어쓴다). `/portfolio/instruments/10000000-0000-0000-0000-000000000001`을 yhr로 불러 `JSONCompareMode.NON_EXTENSIBLE`로 비교한다. `토큰_없이는_모든_화면이_닫혀_있다`의 경로 목록에 같은 경로를 더한다.
- [ ] **Step 2: 골든을 손으로 쓴다.** 값은 "픽스처 수치"의 JSON 그대로. 응답을 붙여 넣지 않는다.
- [ ] **Step 3: 실행해 비교한다.** `--tests '*SixViewGoldenTest'`. Expected: PASS. 실패하면 손 계산 오류인지 구현 오류인지 가려 고친다.
- [ ] **Step 4: 전체 백엔드 테스트.** Global Constraints 명령(승인 후). Expected: 전부 통과.
- [ ] **Step 5: 커밋(요청 시).** `test: 종목 상세 골든을 더한다`

---

### Task 9: 리베이스와 끝 보고

- [ ] **Step 1:** 최신 origin/main에 리베이스(`git -C .worktrees/back-end-instrument-detail fetch origin && git … rebase origin/main`). origin/main에 `V16`이 생겼으면 이 작업의 마이그레이션을 다음 빈 번호로 옮기고, origin/main의 새 마이그레이션이 `alert_state_reason` 제약이나 이 작업이 읽는 표를 바꿨는지 본다. 전체 테스트를 다시 돈다(승인 후).
- [ ] **Step 2: 끝 보고(사용자에게).**
  - 바뀐 파일(파일 구조 표 기준, 실제와 다르면 차이).
  - 테스트 결과: 전체 통과 수 · 실패 수 · 기준선(Task 0)과의 차이.
  - 남은 것: 앱 브랜치는 이 브랜치가 main에 머지 · 배포된 뒤에 머지한다. 앱은 `instrument-detail.json` · 갱신된 `positions.json`을 복사하고, 확인 불가 사유 타입과 카드 상태 문구에 `AWAITING_FINAL`(`오늘 저녁 첫 판정`, 감시 중과 같은 색)을 더한다.
  - 영향받는 통합테스트 케이스(§7 표 기준, 테스트 트랙에 넘긴다): PF10-01(종목별 행 `instrument_id`) · PF10-03/04(`trades[]` · `executed_on`) · PF10-05(`realized.rows` · `realized.total`) · PF10-06(`by_account[].basis`) · PF10-07(`by_account[].basis.ca_unknown`, 종목 상세의 `CA_UNKNOWN`) · N-51(`realized.rows` 추가) · X1-03 · 알림 생성 `NOT_HELD` · 검색 `held`(최신 스냅샷 기준, 샘플에선 결과 같음) · 알림 미리보기 현재값 · 확인 불가 사유 · 카드 상태 문구(`NOT_HELD` 오류면 `current = null`. 오늘 산 종목은 확인 불가 사유 `AWAITING_FINAL` — 카드 `오늘 저녁 첫 판정`, 미리보기 줄 `… — 오늘 저녁 확정 후 첫 판정을 해요`, 알림 스펙 §7.2의 사유 목록에 더해짐).
- [ ] **Step 3:** 커밋 · 푸시 · PR은 요청받으면 진행한다.

---
