# 개인 투자 관리 플랫폼 — 통합 설계 문서

> 본인 명의 자산 통합 관리 사이드프로젝트. **데이터 엔지니어링 풀스택(메달리온 + 람다 아키텍처)** 을 EC2 3~4대 안에서 구현.
>
> 5개 기능: ① 계좌 통합 ② 매수/매도 알림 ③ ETF Look-through ④ 뉴스 해석 LLM ⑤ 장기투자 백테스트

- 작성: jdh · 최종 갱신: 2026-06-29

---

## 문서 구성

| # | 문서 | 내용 |
|---|------|------|
| 1 | (본 문서 ↓) | 아키텍처 개요 — 람다 × 메달리온, 데이터 흐름 |
| 2-1 | [features/01-account-consolidation.md](./features/01-account-consolidation.md) | 계좌 통합 관리 — Batch |
| 2-2 | [features/02-trade-alerts.md](./features/02-trade-alerts.md) | 매수/매도 알림 — Speed (유일한 실시간) |
| 2-3 | [features/03-etf-look-through.md](./features/03-etf-look-through.md) | ETF Look-through — Batch |
| 2-4 | [features/04-news-llm.md](./features/04-news-llm.md) | 뉴스 해석 LLM — Batch |
| 2-5 | [features/05-backtest.md](./features/05-backtest.md) | 장기투자 백테스트 — Batch (최고부하) |
| 3 | [tech-stack.md](./tech-stack.md) | 기술 스택 |
| 4 | [infrastructure.md](./infrastructure.md) | 인프라 (k3s / EC2 / 비용) |
| 부록 | [build-order.md](./build-order.md) | 추천 빌드 순서 |

---

## 1. 아키텍처 개요

두 가지 패턴을 **직교(orthogonal)하게** 겹친다.

- **람다 아키텍처 = 처리 경로 (수평)**
  - **Speed 레이어**: 실시간. Kafka → Spark Structured Streaming. (이 프로젝트에선 *매수/매도 알림* 하나만 실시간)
  - **Batch 레이어**: 정확·완전 재계산. Spark 배치 + Airflow 스케줄 + dbt 변환. (나머지 4개 기능)
  - **Serving 레이어**: 두 경로 결과를 합쳐 조회. Trino(분석) + Postgres(핫 상태).

- **메달리온 아키텍처 = 데이터 품질 계층 (수직, S3 위)**
  - **Bronze**: 원본 그대로. CODEF 응답, KIS 틱, ETF holdings, 뉴스. 불변·append-only.
  - **Silver**: 정제·정규화·dedup·식별해소. Iceberg 테이블.
  - **Gold**: 비즈니스 집계. 포트폴리오 뷰, 룩스루 노출, 백테스트용 시계열. 서빙 대상.

### 데이터 흐름 한눈에

```
[외부 소스]  KIS(실시간 틱)            CODEF · ETF · 뉴스(배치 수집)
                  │                            │
                  ▼                            ▼
[수집]         Kafka  ───────────────┐    배치 수집 잡
              (Speed 백본)           │         │
                  │                  └─► Bronze(원본) 아카이브
                  ▼                            │
[처리]  Spark Structured Streaming     Spark Batch (Airflow 오케스트레이션)
        (피처계산·알림평가)              Bronze → Silver → Gold (dbt 변환)
                  │                            │
                  ▼                            ▼
              알림 발송          [저장] S3 데이터레이크 (Iceberg / Glue Catalog)
            (FCM/알림톡)               Bronze → Silver → Gold
                                             │
                              ┌──────────────┴───────────────┐
                              ▼                               ▼
[서빙]                  Trino (분석 쿼리)              Postgres (핫 상태)
                              └──────────────┬───────────────┘
                                             ▼
[앱]                              FastAPI ──► 클라이언트
```

핵심: **Speed 경로**는 알림만 담당하고 원본을 Bronze에 흘려둔다. **Batch 경로**가 Bronze→Silver→Gold로 끌어올리며, 서빙 레이어가 둘을 합쳐 API에 노출한다.

---

## 기능 표기 규칙

각 기능을 *엔드포인트 → 버튼별 내부 동작(엔드투엔드) → 핵심 주의점* 으로 정리한다.

태그:
- `[프론트]` UI
- `[백엔드]` FastAPI(API·인증·트리거·서빙)
- `[데이터]` 데이터 플랫폼(Airflow·Spark·Kafka·S3/Iceberg·dbt)

※ v1의 `[워커]`(Celery)는 v2에서 `[데이터]`(Airflow/Spark)로 흡수됨.

---

*면책: 알림 임계값·백테스트 결과는 투자 권유가 아니며 본 문서는 기술 설계 참고용이다. 백테스트는 "과거 수익 ≠ 미래 수익" 한계를 항상 명시할 것.*
