# 2-3. ETF Look-through — Batch (Bronze→Silver→Gold)

> 관련: [설계 개요](../README.md) · [계좌 통합](./01-account-consolidation.md) · [백테스트](./05-backtest.md)

**엔드포인트**

| Method | Path | 설명 |
|--------|------|------|
| GET | `/portfolio/look-through` | ETF 해체 후 실질 노출 조회 |

**매일 holdings 파이프라인 (백그라운드)**

1. `[데이터]` Airflow `etf_holdings` DAG (일 1회) — 미국(EODHD 등) + 국내(KRX 자산구성내역)
2. `[데이터]` holdings 원본 → **Bronze**
3. `[데이터]` Spark: Bronze → **Silver** (ISIN 식별 해소, 비중을 **시점별**로 저장 — look-ahead bias 방지)
4. `[데이터]` dbt/Spark: 포지션 × 비중 전개 → **Gold**
   - 종목별 노출 = `Σ(ETF 평가액 × 비중)`
   - **중첩 ETF**(ETF 안의 ETF)는 재귀 전개(깊이 제한)
   - 직접 보유분과 **ISIN으로 병합** (ETF 속 AAPL + 직접 보유 AAPL = 합산)
   - 현금/비주식 슬리브 분리, 집중도 계산
5. `[데이터]` Gold → Postgres 캐시 / Trino 서빙

**`[룩스루 보기]` 버튼을 누르면**

1. `[프론트]` `GET /portfolio/look-through`
2. `[백엔드]` Postgres의 **Gold 룩스루 결과** 확인 → 있으면 즉시 반환 (매일 미리 계산됨)
3. `[백엔드]` 상세/임시 계산이 필요하면 **Trino**로 Gold 조회

**핵심 주의점**

- ISIN 식별 해소가 룩스루 정확도의 핵심
- 비중을 **시점별(Iceberg)** 로 저장해야 백테스트에서 look-ahead bias 방지
- 읽기 위주 → 매일 1회 미리 계산 후 캐시
