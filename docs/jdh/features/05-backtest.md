# 2-5. 장기투자 백테스트 — Batch (최고부하)

> 관련: [설계 개요](../README.md) · [ETF 룩스루](./03-etf-look-through.md) · [인프라](../infrastructure.md)

**엔드포인트**

| Method | Path | 설명 |
|--------|------|------|
| POST | `/backtest` | 백테스트 잡 생성 |
| GET | `/backtest/{id}` | 결과 조회 (폴링) |
| GET | `/backtest` | 잡 목록 |

**`[백테스트 실행]` 버튼을 누르면**

1. `[프론트]` 입력 — 종목/전략(예: 매월 30만원 적립) · 시작일 · 기간(10년)
2. `[프론트]` `POST /backtest`
3. `[백엔드]` `backtest_jobs` 생성(status=queued) → **Airflow `backtest` DAG 트리거**(파라미터 전달) → 잡 ID 응답
4. `[데이터]` `backtest` DAG 실행
   - Spark 배치: Iceberg에서 **조정 가격**(배당·분할 반영) 로드 (Silver/Gold)
   - **레버리지 ETF(QLD)** 면 시뮬레이션 경로로 분기
     `QLD 일수익 ≈ 2 × QQQ 일수익 − (보수율+차입비용)/252` (변동성 끌림 반영, 단순 ×2 금지)
   - 전략 시뮬레이션 + 지표 계산: 최종 평가액, **CAGR, MDD, 변동성, Sharpe**
   - 결과를 Gold/Postgres 저장, status=done
5. `[프론트]` `GET /backtest/{id}` 폴링 → 자산곡선 차트 렌더

**핵심 주의점**

- 최고부하 → **ephemeral Spark executor**(잡 실행 시만), 야간 실행 권장
- look-ahead bias / 레버리지 ETF 일일 리셋 / 총수익(배당 조정) 반드시 반영
- "과거 수익 ≠ 미래 수익" 명시
