# 부록. 추천 빌드 순서

> 관련: [설계 개요](./README.md) · [인프라](./infrastructure.md)

한 번에 다 세우지 말 것.

1. **기반 인프라** — Terraform으로 VPC·EC2·S3 → k3s 구동 → Iceberg+Glue+Trino 연결 확인
2. **계좌 통합(Batch)** — Airflow→Spark→Bronze/Silver/Gold→Postgres→FastAPI 한 줄 완성(메달리온 골격)
   → [features/01-account-consolidation.md](./features/01-account-consolidation.md)
3. **백테스트(Batch)** — Spark 배치 + Iceberg 읽기. 독립적이라 검증 쉬움
   → [features/05-backtest.md](./features/05-backtest.md)
4. **ETF 룩스루(Batch)** — 계좌 + holdings 결합
   → [features/03-etf-look-through.md](./features/03-etf-look-through.md)
5. **알림(Speed)** — Kafka + Spark Streaming. **첫 실시간 경로** (인프라 난이도 ↑)
   → [features/02-trade-alerts.md](./features/02-trade-alerts.md)
6. **뉴스 LLM(Batch)** — 가장 복잡·고비용
   → [features/04-news-llm.md](./features/04-news-llm.md)

> 2~4번까지는 Batch만으로 메달리온 전체를 한 바퀴 돌려보고, 5번에서 Kafka+Streaming(Speed)을 얹는 순서가 가장 덜 꼬인다.

---

*면책: 알림 임계값·백테스트 결과는 투자 권유가 아니며 본 문서는 기술 설계 참고용이다. 백테스트는 "과거 수익 ≠ 미래 수익" 한계를 항상 명시할 것.*
