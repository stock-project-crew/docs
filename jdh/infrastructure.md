# 4. 인프라 (Infra)

> 관련: [설계 개요](./README.md) · [기술 스택](./tech-stack.md) · [빌드 순서](./build-order.md)
>
> 주의: 지정한 스택(Kafka + Spark + Trino + Airflow + k8s)은 **메모리를 많이 먹는다.** 라이트 설계의 t3.large(8GB)로는 부족하다. 아래는 현실적인 사이징.

## 4-1. 컴퓨팅 — k3s on EC2 3~4대

- 쿠버네티스는 **k3s**(경량·인증 K8s)로 직접 운영 → EKS 컨트롤플레인 월 ~$73 불필요.
- 항상 켜져 있는 컴포넌트(steady-state)와 잠깐만 도는 배치(bursty)를 구분해 배치한다.

## 4-2. 노드 역할 배치 (4대 기준)

| 노드 | 역할 | 항상 켜짐 |
|------|------|-----------|
| node-1 | k3s 서버(control) + FastAPI + Airflow(scheduler/web) | O |
| node-2 | Kafka 브로커 + Spark Streaming(driver/executor) | O |
| node-3 | Trino(coordinator+worker) + dbt | O |
| node-4 | Spark **배치** executor 착지 + 여유 용량 | 배치 시만 |
| (외부) | Postgres = **RDS**(클러스터 밖, 내구성) | — |

- `taint`/`label` + `nodeSelector`로 stateful·메모리 무거운 것(Kafka, Trino)을 고정 배치.
- **Spark 배치 executor는 ephemeral 파드**로 잡 실행 시만 생성→종료. 백테스트 같은 무거운 잡은 야간에 돌려 상시 컴포넌트와 경합 최소화. → 소수 노드에 무거운 배치 스택을 욱여넣는 핵심 트릭.

## 4-3. 인스턴스 사이징

| 구성 | 노드 사양 | 총량 | 비고 |
|------|-----------|------|------|
| 현실적 최소 | m5.xlarge(4vCPU/16GB) × 4 | 16 vCPU / 64GB | 빡빡함, 배치 동시성 제한 |
| 쾌적 | m5.2xlarge(8vCPU/32GB) × 3 | 24 vCPU / 96GB | 여유 있음 |

- 상시 점유(Kafka~4GB + Spark Streaming~5GB + Trino~6GB + Airflow~3GB + 시스템) ≈ 20~28GB → 16GB×3으로는 부족, **최소 16GB×4 또는 32GB×3**.
- t3 같은 버스터블은 상시 부하(Kafka/Trino/streaming)에서 크레딧 소진·스로틀 위험 → **m5(고정 성능)** 권장.

## 4-4. 네트워크 / 저장소 (Terraform 관리)

1. VPC + 단일 AZ(개인용, 크로스AZ 전송비 회피) + **퍼블릭 서브넷 + 엄격 보안그룹** → NAT 게이트웨이(월 ~$33) 회피
2. 외부 노출은 k3s 내장 ingress(traefik)를 노드 IP에 → AWS LB(월 ~$20) 회피
3. S3 버킷: `bronze` / `silver` / `gold` 프리픽스
4. IAM: 파드가 S3·Glue 접근하도록 **IRSA**(IAM Roles for Service Accounts)
5. ECR(이미지), RDS(Postgres), EIP

## 4-5. 비용 (개략)

- 컴퓨트: m5.xlarge×4 서울 ≈ 월 **~$690**(온디맨드) / **~$435**(1년 Savings Plan)
- + EBS(Kafka 로그·Spark scratch ~250GB) ~$25 + S3 ~$10 + RDS(db.t3.medium) ~$50 + 전송 변동
- **올인 대략 월 $500~750(온디맨드), 약정 시 $350~500.** 라이트 스택보다 확실히 비싸다(스택이 무거운 대가).
- 확정 견적은 calculator.aws.

## 4-6. 배포

1. **Terraform**: VPC·EC2·S3·IAM·RDS·ECR 등 AWS 인프라
2. k3s 설치(서버 1 + 에이전트 2~3, 또는 HA 서버 3)
3. **Helm**: Strimzi(Kafka), Spark Operator, Airflow, Trino, Prometheus/Grafana 차트
4. (선택) **ArgoCD**로 GitOps — 매니페스트를 Git에서 동기화
5. Airflow DAG·dbt 프로젝트·Spark 잡은 별도 리포에서 CI로 배포
