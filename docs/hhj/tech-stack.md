# 기술 스택 (해정 · 인프라 관점)

> 관련: [아키텍처](./architecture.md) · [service.md](./service.md) · [alert.md](./alert.md)
> · [jdh 기술 스택(비교 대상)](../jdh/tech-stack.md) · [jdh 인프라](../jdh/infrastructure.md)
>
> `채택` = 웹 검색/팀 실측으로 실현 가능 확인 · `보류` = 기술은 가능하나 전제 조건 미충족(사업자등록 등) · `기각` = 이 규모엔 과설계이거나 차단 확정

---

## 1. 계층별 스택

| 계층 | 기술 | 상태 | 근거 |
|---|---|---|---|
| 언어/런타임 | **Python 3.11+** | 채택 | python-kis 3.10+ 요구([yhr 검증](../yhr/verification/kis-realtime-and-pykis.md) §2-1), 팀 검증 스크립트(`verify/yhr/`)가 이미 Python |
| KIS 실시간 수집 | **raw WebSocket 직접 구현** (python-kis 아님) | 채택 | python-kis는 구독 캡 초과(OPSP0008)를 조용히 무시 → 운영 리스크. raw 구현으로 등록 성공/실패를 직접 카운트해야 함([yhr 검증](../yhr/verification/kis-realtime-and-pykis.md) §2-3-1) |
| KIS 잔고/시세 조회 | **python-kis (PyKis)** | 채택 | 국내+해외 통합 잔고·환율 필드를 한 인터페이스로 제공, 실측 raw API와 수치 일치. `Decimal` 표시 변환, `domestic/foreign` quirk(→`currency` 사용) 주의 |
| API 서버 | **FastAPI** | 채택 | jdh 스택과 동일 선택 유지(팀 컨벤션), 비동기 지원이 WS 수집기와 궁합 좋음 |
| DB | **PostgreSQL** (단일 인스턴스) | 채택 | raw/cln/mart를 스키마로 구분해 메달리온 개념 유지, jdh 문서의 "핫 상태"용 Postgres와 동일 컴포넌트를 Bronze/Silver/Gold까지 확장해 단일화 |
| 실시간 이벤트 버스 | **Redis Streams** | 채택 | Kafka 대비 신규 인프라 없이(Redis 하나로 캐시+스트림 겸용) 컨슈머 그룹·ack 지원, 개인/소수팀 이벤트량엔 충분 |
| 배치 스케줄러 | **APScheduler** (또는 OS cron) | 채택 | EOD 지표 계산 등 잡 수가 적어 Airflow 도입 비용 대비 이득 없음 |
| 실시간 스트림 처리 | 자체 asyncio 슬라이딩 윈도우 | 채택 | KIS에 분봉 실시간 TR이 없어 틱→버킷 집계가 필요([yhr 검증](../yhr/verification/kis-realtime-and-pykis.md) §4-1). Flink/Spark Streaming 불필요한 규모 |
| 알림 발송 | **FCM (Firebase Cloud Messaging)** | 채택 | 개인 Firebase 프로젝트 무료 발급, `firebase-admin`/`pyfcm`(HTTP v1, 2024.06 마이그레이션 완료)로 Python 발송 |
| 알림 발송(보조) | 카카오 알림톡 | **보류** | 발신 프로필 생성에 **사업자등록번호 필수** — 비사업자 개인은 비즈니스 채널 신청 불가(2026-07-04 확인). 사업자 등록 이후 재검토 |
| 개발 환경 | **Docker Compose** (로컬) | 채택 | API+수집기+Postgres+Redis 4개 컨테이너로 로컬 개발·통합테스트. 완성 후 동일 이미지를 k8s에 배포 |
| 배포(운영) | **EC2 + kubeadm 자체 구축 클러스터** (master×3, worker×2, storage×1) | 채택(학습 목적) | EKS는 control-plane을 AWS가 관리 → 직접 구축 경험이 목적이라 제외하고 kubeadm 선택. 상세 노드 구성·HA·비용은 [infrastructure.md](./infrastructure.md) |
| control-plane HA | **kubeadm stacked etcd, master 3대 + AWS NLB**(control-plane-endpoint) | 채택 | etcd 쿼럼상 master 짝수/1대는 오히려 불리 → 홀수 3대 필요(공식 가이드). AWS VPC는 keepalived/VRRP 플로팅 VIP를 안정적으로 지원하지 않아 NLB로 대체(§3 근거) |
| storage 노드 | **NFS 서버 + nfs-subdir-external-provisioner** | 채택 | storage 전용 노드 1대 개념과 정확히 맞음. Longhorn(분산) 대비 구성이 단순하나 NFS 노드 자체는 단일 장애점으로 남음(인지된 트레이드오프, [architecture.md](./architecture.md) §7) |
| ETF look-through | 미국 **SPDR XLSX**만 | 채택(범위 한정) | 봇 차단 없음, curl로 안정 수집([ETF 조사](../yhr/research/etf-constituent-sources.md) §0). 국내 ETF는 KRX 약관·JS 게이트로 기각 |
| 섹터 분류 | **yfinance**(미국+국내 겸용) 1차, **Naver 업종** 국내 보조 | 채택 | 둘 다 순수 코드 수집 실측 확인([섹터 조사](../yhr/research/sector-classification-sources.md) §0) |
| 시크릿 관리 | `.env` + OS 파일 권한 (개인/소수팀 규모) | 채택 | AWS Secrets Manager 등은 관리 대상 앱키가 팀원별 소수 개라 과설계 |

---

## 2. 기각한 옵션과 이유

| 옵션 | jdh 문서 채택 여부 | 이 문서 판단 | 이유 |
|---|---|---|---|
| Kafka (KRaft) | 채택 | 기각 | 이벤트량이 초당 수백~수천 미만(개인/소수팀) → Redis Streams로 충분, 운영 인력·비용 정당화 안 됨 |
| Spark (Batch+Streaming) | 채택 | 기각 | 데이터량이 분산처리를 요구하는 규모가 아님 → Python 스크립트/SQL로 충분 |
| Trino + Iceberg + Glue | 채택 | 기각 | S3 레이크하우스는 대용량 분석 쿼리용 — Postgres 단일 인스턴스로 조회 성능 충분 |
| Airflow | 채택 | 기각 | 배치 DAG 수가 적어 스케줄러(K8s Executor 포함) 운영 비용 대비 이득 없음 → APScheduler |
| k3s (k8s) 3~4대 | 채택 | **역방향 채택** — kubeadm으로 6대(master3+worker2+storage1) | 트래픽 근거로는 여전히 과설계이나, 해정의 인프라 학습 목적(EKS 없이 control-plane 직접 구축)이 우선순위가 되어 오히려 jdh안보다 무거운 진짜 HA 구성을 선택([architecture.md](./architecture.md) §3 비교표) |
| EKS | 문서에 없음(신규 검토) | 기각 | control-plane을 AWS가 소유 — "직접 구축 경험"이라는 목적과 정면으로 배치 |
| 카카오 알림톡 | 문서에 없음(신규 조사) | 보류 | 사업자등록번호 필요(§1) — 기술이 아니라 자격 요건 문제 |

> 트래픽/팀 규모가 실제로 커지면(관심종목 수백 개, 다수 사용자) jdh 스택으로의 단계적 전환이 합리적 — [architecture.md §7](./architecture.md#7-열린-질문) 참조.

---

## 3. 출처 (2026-07-04 웹 검색 확인)

- KIS Developers 앱키 신청 절차 — https://apiportal.koreainvestment.com/apiservice
- Soju06/python-kis (유지 상태·최신 버전) — https://github.com/Soju06/python-kis
- Firebase Cloud Messaging 공식 문서 — https://firebase.google.com/docs/cloud-messaging
- PyFCM (HTTP v1 마이그레이션) — https://pypi.org/project/pyfcm/
- 카카오 비즈니스 채널 신청 자격(사업자등록증 필요) — https://cs.kakao.com/helps_html/1073204966?locale=ko
- Oracle Cloud Always Free 한도 변경(2026-06) — https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm , https://www.oracle.com/cloud/free/faq/
- AWS Lightsail 가격 — https://aws.amazon.com/lightsail/pricing/
- APScheduler vs Airflow 비교 — https://apscheduler.com/
- Redis Streams vs Kafka 비교 — https://redis.io/tutorials/howtos/solutions/microservices/interservice-communication/
- kubeadm 공식 HA 가이드(등급 etcd 쿼럼·로드밸런서 필요성) — https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/high-availability/ , https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/ha-topology/
- kubeadm HA 고려사항(keepalived 서브넷 제약 등) — https://github.com/kubernetes/kubeadm/blob/main/docs/ha-considerations.md
- kubeadm on EC2 구축 가이드 — https://devopscube.com/setup-kubernetes-cluster-kubeadm/ , https://kitemetric.com/blogs/setting-up-a-multi-node-kubernetes-cluster-with-kubeadm-on-aws
- k8s on-prem 스토리지 비교(NFS/Longhorn/EBS CSI) — https://oneuptime.com/blog/post/2026-02-20-kubernetes-csi-drivers-guide/view

이 외 KIS API 세부 사실(구독 한도·rate limit·필드)은 팀 내 실측 문서([yhr 검증](../yhr/verification/kis-realtime-and-pykis.md))를 1차 출처로 인용했다.
