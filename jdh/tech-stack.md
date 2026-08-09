# 3. 기술 스택 (Tech)

> 관련: [설계 개요](./README.md) · [인프라](./infrastructure.md)

`기본` = 직접 지정 / `추가` = 동작에 필요해 보강.

| 계층 | 기술 | 구분 | 역할 |
|------|------|------|------|
| 오케스트레이션(컨테이너) | **Kubernetes (k3s)** | 기본 | 전 컴포넌트의 실행 기반. 경량이라 EC2 소수에 적합 |
| 스트리밍 백본 | **Kafka (KRaft 모드)** | 기본 | Speed 경로 수집·버퍼. ZooKeeper 불필요 |
| ─ Kafka 운영 | Strimzi Operator | 추가 | k8s 위에서 Kafka 브로커 라이프사이클 관리 |
| 처리 엔진 | **Spark** | 기본 | Batch(메달리온 변환·백테스트) + Structured Streaming(Speed) |
| ─ Spark 운영 | Spark Operator (on k8s) | 추가 | 배치 잡을 파드로 동적 생성·종료 |
| 오케스트레이션(워크플로) | **Airflow** | 기본 | 배치 DAG 스케줄·트리거. KubernetesExecutor |
| 변환 | **dbt** (dbt-trino) | 기본 | Silver→Gold SQL 변환, 테스트, lineage |
| IaC | **Terraform** | 기본 | AWS 인프라 전체 코드화 |
| 데이터 레이크 | **S3** | 기본 | Bronze/Silver/Gold 저장소 |
| 테이블 포맷 | **Apache Iceberg** | 추가 | ACID·스키마진화·**시점조회**(룩스루·백테스트 정확도) |
| 카탈로그 | AWS Glue Data Catalog | 추가 | Iceberg 메타스토어. 별도 노드 불필요(서버리스) |
| 쿼리/서빙 | **Trino** | 추가 | S3·Iceberg 분석 쿼리 + dbt 컴퓨트 타깃 |
| 서빙 DB(핫) | **Postgres** (RDS 권장) | 추가 | 포트폴리오·알림규칙·해석 핫 상태 + Airflow 메타DB |
| 애플리케이션 | **FastAPI** | 추가 | API 서빙, Airflow 트리거, 알림 컨슈머 |
| LLM | **Anthropic Claude API** | 추가 | 뉴스 해석(structured output) |
| 캐시(선택) | Redis | 추가 | API 응답 캐시 |
| 이미지 레지스트리 | ECR | 추가 | k8s 컨테이너 이미지 |
| 패키지 관리 | Helm (+ ArgoCD 선택) | 추가 | Strimzi·Spark·Airflow·Trino 차트 배포(GitOps) |
| 관측 | Prometheus + Grafana | 추가 | k8s/데이터 스택 모니터링 |
| 시크릿 | AWS Secrets Manager + External Secrets | 추가 | CODEF/KIS/Claude 자격증명 |
| 수집 라이브러리 | codef SDK, python-kis, pykrx, yfinance | 추가 | 소스별 수집 |

## 왜 이 보강이 필요한가 (요약)

1. **Iceberg + Glue Catalog** — S3에 그냥 Parquet만 쌓으면 Silver/Gold의 ACID·스키마 변경·시점 조회가 안 된다. Iceberg가 이를 해결하고 Spark·Trino·dbt가 모두 같은 테이블을 본다. Glue를 카탈로그로 쓰면 메타스토어 노드를 따로 안 띄워도 된다.
2. **Trino** — Gold(S3)를 API와 dbt가 SQL로 질의할 엔진. dbt-trino로 변환까지 한 엔진에서.
3. **Postgres(핫)** — 레이크는 분석엔 좋지만 API의 빠른 포인트 조회엔 부적합. 핫 상태는 Postgres에 둔다. Airflow 메타DB도 여기 둔다. **잃으면 안 되는 데이터라 RDS(관리형) 권장.**
4. **Strimzi / Spark Operator / Helm** — Kafka·Spark를 쿠버네티스 위에서 "제대로" 돌리는 표준 방식.
