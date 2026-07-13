# 전반적 아키텍처 

> 관련 문서: [service.md](./service.md) · [alert.md](./alert.md) · [기술 스택](./tech-stack.md) · [인프라(EC2+kubeadm)](./infrastructure.md)
> · [yhr KIS 실시간·python-kis 검증](../yhr/verification/kis-realtime-and-pykis.md)
> · [yhr 1차 기능명세·기술검토](../yhr/specs/2026-06-28-feature-spec-and-tech-review.md)
> · [jdh 통합설계 문서(비교 대상)](../jdh/README.md)
>
> 작성: hhj(해정) · 작성일: 2026-07-04 (2026-07-04 2차 갱신: 배포 대상을 Docker Compose 단일 호스트 → **EC2 + kubeadm 자체 구축 클러스터**로 변경)
> 원칙: **웹 검색·팀 내 실측 검증으로 "지금 실현 가능"이 확인된 것만** 채택. 미검증·차단 확정 항목은 채택하지 않고 각주로 남긴다.
>
> **배포 방향 변경 메모**: 애초 이 문서는 트래픽 규모에 맞춘 "축소 스택"(Docker Compose 단일 호스트)을 제안했으나, 해정 본인이 인프라 담당으로서 **k8s를 EKS(관리형) 없이 kubeadm으로 직접 구축해보는 학습 경험**을 우선순위로 두기로 했다. 즉 이후의 배포 관련 결정은 "이 규모에 최소한으로 필요한 것"이 아니라 "직접 운영해보고 싶은 것" 기준으로 바뀐다. 애플리케이션 계층(FastAPI/수집기/Postgres/Redis 등, §3)의 구성 자체는 그대로 유지하고, **배포 대상만 단일 호스트에서 자체 구축 k8s 클러스터로 옮긴다.**

---

## 0. 전제

- **운영 모델**: [yhr 스펙](../yhr/specs/2026-06-28-feature-spec-and-tech-review.md) 기준 **본인 키 모델**(각자 자기 KIS 앱키로 자기 계좌만 연동). 멀티유저 커스터디 없음 → 인프라 부담이 "동시접속자 확장"이 아니라 **개인/소수 팀 규모의 상시 가동 안정성**에 있음.
- **팀 규모**: 3인(백엔드·데이터·인프라). 트래픽은 팀원 수 × 관심종목 수 규모 — 대용량 아님.
- **핵심 데이터 원천**: 한국투자증권(KIS) OpenAPI. REST(잔고·시세·주문·체결내역) + WebSocket(실시간 체결가·호가).
- **이 문서의 목적**: [jdh 통합설계](../jdh/README.md)가 제안한 k3s(EC2 3~4대) + Kafka + Spark + Trino + Airflow + Iceberg 스택(월 $500~750)은 **개인 명의 자산 통합 관리라는 별도 사이드프로젝트** 기준이며, 규모·비용 면에서 이 팀 프로젝트(본인 키 모델·3인·수십 종목)엔 과설계다. 본 문서는 **같은 메달리온(Raw→Cleansed→Mart) 개념은 유지하되, 인프라는 팀·데이터 규모에 맞게 축소한 대안**을 제시한다.

---

## 1. KIS API 기준 — 실현 가능성 확정 사실

[yhr 실측 문서](../yhr/verification/kis-realtime-and-pykis.md)에서 실계좌로 검증된 사실을 아키텍처 전제로 그대로 채택한다(재검증하지 않고 인용).

| 항목 | 확정 사실 | 아키텍처 영향 |
|---|---|---|
| 실시간 WS 등록 한도 | **위탁(01)·모의=41건** / **IRP(29)=3건** (체결가만 기준. 체결+호가 동시면 종목당 2건 소모 → 실질 ~20종목) | 실시간 감시는 **위탁계좌 앱키**로만 의미 있게 동작. 팀·개인 모두 위탁계좌 확보가 선결 조건 |
| REST 호출 제한 | 앱키당 초당 ~20건 | 배치 잡의 동시 호출 수를 계좌·앱키 단위로 직렬화/스로틀 필요 |
| WebSocket 재연결 | python-kis는 자동 복구, raw는 approval_key 재사용 후 재구독 | 상시 프로세스에 헬스체크+재연결 로직 필수(인프라 책임) |
| python-kis 실시간 캡 처리 | OPSP0008(캡 초과)을 조용히 무시(예외 없음) | 대량 구독은 **raw WebSocket 직접 구현** 채택(이미 팀 결론), python-kis는 잔고 조회용으로 한정 |
| 분봉 실시간 TR | 없음(체결틱만) | 급락/거래량급증은 **틱→N초/1분 버킷 자체 집계**로 처리(스트림 처리기 필요, 아래 §3) |
| 미국 실시간 | 체결가·1호가 0분 지연 무료 | 국내와 동일 파이프라인으로 처리 가능 |

이 표 바깥의 항목(국내 ETF 구성종목 자동수집, 해외/USD 잔고 실값 등)은 [ETF 원천 조사](../yhr/research/etf-constituent-sources.md)·[yhr 스펙 §3.4](../yhr/specs/2026-06-28-feature-spec-and-tech-review.md)에서 이미 "차단 확정" 또는 "미실증"으로 분류되어 있어 본 아키텍처에서도 1차 범위에서 제외한다.

---

## 2. 이번 조사에서 새로 확인한 제약 (2026-07-04, 웹 검색)

| 항목 | 결과 | 근거 |
|---|---|---|
| **카카오 알림톡** | 발신 프로필 생성에 **사업자등록번호 필수** — 사업자 등록이 없는 순수 개인은 비즈니스 채널 신청 불가 → **본인 키 모델(비사업자 개인)에선 1차 실현 불가** | 카카오 고객센터 "비즈니스 채널 신청" 가이드 |
| **FCM(Firebase Cloud Messaging) 푸시** | 개인 Firebase 프로젝트로 무료 발급 가능, Python은 `firebase-admin` 또는 `pyfcm`(2024.06 HTTP v1 마이그레이션 완료)으로 발송 | Firebase 공식 문서, PyFCM PyPI |
| **python-kis 유지 상태** | 최신 2.1.6(2025-10) 이후 신규 릴리스는 없으나 2026-01~02 이슈 등록 등 **활성 유지 중** | Soju06/python-kis GitHub |
| **APScheduler vs Airflow** | 단순 배치 스케줄(일 1회 EOD 지표 계산 등) 규모에서는 APScheduler가 Airflow보다 운영 부담이 훨씬 적다는 것이 중론 | 다수 2026년 비교 아티클 |
| **Redis Streams vs Kafka** | 초당 이벤트가 수백~수천 수준(개인/소수 팀 규모)이면 Redis Streams(컨슈머 그룹·ack 지원)가 Kafka 없이 동일 패턴을 충분히 대체 | Redis 공식 튜토리얼, 2026 비교 아티클 |
| **kubeadm on EC2** | EC2 인스턴스에 kubeadm으로 클러스터를 직접 구축하는 것은 표준적으로 문서화된 경로(다수 2025~2026 가이드) | devopscube, kitemetric 등 다수 가이드 |
| **kubeadm control-plane HA** | etcd 쿼럼상 master는 **홀수·3대 이상** 필요(2대는 1대보다 가용성이 나쁨). API 서버 앞에 **로드밸런서**가 필수(`--control-plane-endpoint`) | kubernetes.io 공식 HA 가이드 |
| **AWS에서 keepalived/VRRP** | AWS VPC는 멀티캐스트·그라튜이터스 ARP 기반 플로팅 VIP를 공식 지원하지 않아 온프레미스식 keepalived+haproxy가 불안정 → **AWS 표준은 NLB(TCP passthrough)를 control-plane-endpoint로 사용** | 공식 kubeadm ha-considerations, 다수 실전 가이드 |

**결론**: 알림 채널은 **1차 FCM 푸시 단일 채널**로 좁힌다(카카오 알림톡은 팀/개인이 사업자 등록을 하기 전까진 기술적으로 불가능하므로 로드맵에서도 "사업자 등록 이후"로 조건부 표기). 스트리밍 백본은 Kafka 대신 **Redis Streams**, 배치 오케스트레이션은 Airflow 대신 **APScheduler(또는 OS cron)**로 확정한다. 배포 대상은 **EC2 + kubeadm 자체 구축 클러스터**로 확정하고(§3, 상세는 [infrastructure.md](./infrastructure.md)), control-plane HA는 **master 3대 + AWS NLB**로 구성한다(팀 결정: 애플리케이션 계층 이중화만이 아니라 control-plane까지 진짜 HA로 구축).

---

## 3. 전체 아키텍처

```
[KIS OpenAPI]
   ├─ REST: 잔고·시세(일봉)·기간체결내역·주문(미사용)
   └─ WebSocket: 실시간 체결가(H0STCNT0)/호가(H0STASP0), 해외(HDFSCNT0)
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│ 수집(Collector) — 상시 프로세스 1개(asyncio)                │
│  · raw WebSocket 직접 구현(위탁계좌 앱키, 최대 41종목/세션)   │
│  · REST 폴링(잔고·일봉·수급 등, 초당 20건 스로틀)            │
│  · 헬스체크 + approval_key 재사용 재연결                     │
└───────────────────────────────────────────────────────────┘
        │ 원본 그대로 append                 │ 틱 이벤트 publish
        ▼                                    ▼
┌───────────────────┐              ┌───────────────────────┐
│ Postgres           │              │ Redis Streams          │
│  raw_* (Bronze)     │              │  tick 스트림 (Speed)   │
│  append-only        │              │  슬라이딩 윈도우 집계   │
└───────────────────┘              └───────────────────────┘
        │                                    │ 급락/거래량급증 판정
        ▼                                    ▼
┌───────────────────────────────────────────────────────────┐
│ 배치 처리(Processor) — APScheduler 잡                       │
│  · EOD: cln_* (Silver) 정제 → mart_* (Gold) 집계             │
│  · 지표: MA/RSI/거래량평균/수급 3일연속 (일봉 기준)           │
│  · ETF look-through(미국 SPDR만) · 섹터 매핑(yfinance/Naver) │
└───────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│ 서빙(API) — FastAPI (Deployment, replica 2 → worker 2대 분산) │
│  · 포트폴리오 대시보드 조회 (mart_* 조회 중심)                │
│  · AlertRule CRUD + RuleState 평가(엣지/히스테리시스/쿨다운)  │
│  · 실시간 급락 이벤트는 Redis Streams 구독 → 즉시 평가        │
└───────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────┐
│ 알림 발송           │   1차: FCM 푸시 (무료, 사업자등록 불필요)
│  Notification      │   보류: 카카오 알림톡 (사업자등록 필요 확인됨 → 제외)
└───────────────────┘
```

**배포 대상**: 개발은 로컬 **Docker Compose**로 진행(FastAPI·수집기·Postgres·Redis 4개 컨테이너). 안정화되면 **EC2 kubeadm 클러스터**(master×3 + worker×2 + storage×1, [infrastructure.md](./infrastructure.md))에 컨테이너 이미지를 그대로 배포한다 — Postgres·Redis는 storage 노드의 NFS PV를 쓰는 StatefulSet/Deployment로, FastAPI·수집기는 worker 2대에 분산 배치한다. 수집기(WebSocket)는 종목 샤딩을 하지 않는 한 **replica 1로 고정**(다중 인스턴스가 같은 종목을 중복 구독하면 KIS 세션당 한도를 이중으로 소모).

### 계층 설명 (jdh 메달리온 용어와 대응)

| 이 문서 | jdh 문서 대응 | 차이 |
|---|---|---|
| `raw_*` (Postgres) | Bronze(S3) | 저장소만 S3/Iceberg → Postgres 스키마로 축소. 데이터량이 개인/팀 스케일이라 파일 레이크 불필요 |
| `cln_*` / `mart_*` (Postgres) | Silver / Gold(S3, Iceberg) | 동일 개념, Spark/dbt 대신 **Python 배치 스크립트 + SQL**로 변환 |
| Redis Streams 틱 집계 | Kafka + Spark Structured Streaming | 이벤트량이 Kafka 운영 비용을 정당화할 수준이 아니므로 Redis Streams로 대체 |
| APScheduler | Airflow | 배치 잡이 수 개 수준(EOD 지표·수급 조인·ETF 갱신)이라 DAG 오케스트레이터 불필요 |
| EC2 + kubeadm 자체 구축(master×3+worker×2+storage×1) | k3s on EC2 3~4대(관리형 부담 최소화 지향) | **여기는 방향이 반대**: jdh는 "필요 최소한"으로 k3s를 골랐지만, 이 문서는 해정의 인프라 학습 목적상 **EKS 없이 kubeadm으로 control-plane까지 직접 구축**하는 쪽을 의도적으로 선택([infrastructure.md](./infrastructure.md)). 트래픽 근거가 아니라 학습 목적 근거임을 명시 |

---

## 4. 실시간 vs 배치 판정 기준 (alert.md §5.2 계승)

[alert.md](./alert.md)의 결론을 그대로 계승한다 — **실시간은 가격/이벤트 중심, 배치는 기술지표/수급 중심**.

- **실시간(WS + Redis Streams)**: 목표가 도달, 전일 종가 대비 ±X% 등락, 급락/거래량 급증(틱 집계).
- **배치(APScheduler, EOD 1회)**: 골든/데드크로스, RSI, 20일 평균거래량, 외국인·기관 3일 연속 순매수.
- 이유: 실시간 지표는 장중 흔들림으로 오탐 위험이 크고, KIS가 분봉 실시간 TR을 제공하지 않아 종가 확정치가 더 신뢰도 높음(§1 표 참조).

---

## 5. 운영 관점 필수 설계

- **단일 장애점**: 수집 프로세스가 1개이므로 다운 시 실시간 알림이 조용히 끊긴다 → systemd/Docker restart policy + 외부 헬스체크(예: 무료 uptime 모니터 핑)로 liveness 감시 필수(alert.md §5.4, yhr 스펙 §5와 동일 결론).
- **계좌 제약**: IRP(29) 앱키는 실시간 3건 캡 → **위탁(01) 계좌 앱키 확보가 실시간 기능의 선결 조건**. 위탁계좌가 없으면 실시간 감시 범위는 사실상 무의미(§1).
- **레이트리밋**: REST 초당 ~20건은 배치 잡(다수 종목 일봉 조회 등)에서 병목 → 요청 큐잉 + 지수 백오프.
- **알림 중복 방지**: RuleState(엣지 트리거) + 쿨다운은 Postgres 테이블로 충분(대규모 캐시 불필요, Redis는 스트림 용도로만 사용해도 됨).

---

## 6. 1차 범위에서 제외한 것 (근거 명시)

| 항목 | 제외 사유 |
|---|---|
| 카카오 알림톡 | 사업자등록번호 없이 비즈니스 채널 발급 불가(§2 확인) — 팀/개인이 사업자 등록 시 재검토 |
| Kafka / Spark / Trino / Airflow | 애플리케이션 계층 자체의 트래픽·데이터 규모 대비 운영 비용·복잡도 과다(§2) — 트래픽이 커지면 단계적 도입. **단, 배포 대상(k8s)은 학습 목적으로 별도 채택함**(§3, §6 바로 위 표 참고 — 스택 규모와 배포 인프라 규모는 서로 다른 판단 기준) |
| EKS(관리형 k8s) | control-plane을 AWS가 쥐는 형태라 "직접 구축 경험"이라는 목적과 배치 → kubeadm 자체 구축 채택([infrastructure.md](./infrastructure.md)) |
| 국내 ETF 구성종목 자동 수집 | KRX JS 봇 차단 + 약관상 사설 라이브러리 금지(이미 팀 내 확정, [ETF 조사](../yhr/research/etf-constituent-sources.md)) |
| 멀티유저 커스터디 | 마이데이터 허가제(자본금 5억) 대상이라 개인 사이드 프로젝트 범위 밖([portfolio-signal-design.md](../yhr/specs/2026-06-22-portfolio-signal-design.md) §7) |

---

## 7. 열린 질문

1. 위탁(01) 계좌 앱키를 팀 차원에서 확보할지, 각자 개인 위탁계좌로 개별 구동할지 — 본인 키 모델 원칙상 후자가 기본값이나 운영 정책 확정 필요.
2. 트래픽이 늘어나 Redis Streams/APScheduler로 부족해지는 시점(예: 관심종목 수백 개, 팀 확장)에 Kafka/Airflow 등 jdh 스택 구성요소를 부분 도입할 조건을 무엇으로 정의할지.
3. EC2 6대(master×3+worker×2+storage×1) + NLB 상시 운영 비용([infrastructure.md](./infrastructure.md) §4)을 학습 기간 동안 어떻게 감당할지(상시 가동 vs 학습 세션마다 기동/종료).
4. storage 노드(NFS 단일)가 그 자체로 단일 장애점이라는 점을 감수하고 갈지, 추후 Longhorn 등 분산 스토리지로 옮길지.
