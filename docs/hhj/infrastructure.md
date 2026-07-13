# 인프라 — EC2 + kubeadm 자체 구축 클러스터

> 관련: [아키텍처](./architecture.md) · [기술 스택](./tech-stack.md)
> · [jdh 인프라(k3s, 비교 대상)](../jdh/infrastructure.md)
>
> 작성: hhj(해정) · 작성일: 2026-07-04
>
> **목적**: EKS(관리형 control-plane) 대신 **kubeadm으로 control-plane까지 직접 구축**해보는 것 자체가 목표. 개발은 로컬 Docker Compose로 진행하고, 안정화되면 아래 클러스터에 배포한다. 팀 결정: control-plane까지 진짜 이중화(HA)하고, storage 노드는 NFS 단일 노드로 단순하게 구성([architecture.md](./architecture.md) §2 질문 참조).

---

## 1. 왜 EKS가 아니라 kubeadm인가

EKS는 control-plane(API 서버·etcd·스케줄러)을 AWS가 관리해 사용자는 워커 노드만 신경 쓰면 된다. 그 대가로 **etcd 튜닝, control-plane 이중화, 인증서 갱신, 업그레이드 같은 "진짜 운영 경험"이 추상화되어 사라진다.** 인프라 담당(해정)이 얻고 싶은 것이 정확히 그 경험이므로, 이번 클러스터는 **EC2 위에 kubeadm으로 직접** 올린다.

---

## 2. 노드 구성

| 역할 | 개수 | 인스턴스(안) | 스펙 | 비고 |
|---|---|---|---|---|
| control-plane(master) | **3** | t3.medium | 2 vCPU / 4GB | kubeadm 최소 요구 2 vCPU 충족. stacked etcd(각 master에 etcd 동거) |
| worker | **2** | t3.medium~large | 2~4 vCPU / 4~8GB | FastAPI·수집기·Redis 파드 배치. 워크로드 보고 t3.large로 조정 |
| storage | **1** | t3.small~medium + 별도 EBS(gp3) | 2 vCPU / 2~4GB + gp3 볼륨(초기 50~100GB) | NFS 서버 전용. 컴퓨트보다 디스크가 중요 |
| (외부) | 1 | AWS NLB | — | control-plane-endpoint(§3) |

**총 6대 EC2 + NLB 1개.** kubeadm 요구사항상 control-plane 최소 2 vCPU·2GB, 프로덕션 가이드는 등 2 vCPU/4GB 이상을 권장 — t3.medium이 하한선에 가까우므로 etcd 지연이 체감되면 t3.large로 올린다.

---

## 3. Control-plane HA 설계

### 3-1. 왜 master 3대인가
kubeadm 공식 HA 가이드 기준 etcd는 과반수(quorum)로 합의한다. **master 2대는 1대보다 가용성이 나쁘다**(2대 중 1대만 죽어도 과반 미달) — 최소 홀수 3대부터 1대 장애를 버틴다. 그래서 "이중화"를 master까지 적용하기로 한 이상 대수는 3대가 하한선이다.

### 3-2. 왜 AWS NLB인가 (keepalived 대신)
kubeadm 표준 HA는 API 서버 앞에 로드밸런서를 두고 그 주소를 `--control-plane-endpoint`로 kubeadm init에 준다. 온프레미스에서 흔한 조합은 keepalived(VRRP 플로팅 IP) + haproxy이지만, **keepalived는 같은 L2 서브넷에서 그라튜이터스 ARP로 VIP를 옮기는 방식이라 AWS VPC(멀티캐스트·브로드캐스트 미지원)에서 공식적으로 지원되지 않는다.** AWS에서 kubeadm HA를 구축하는 표준 패턴은 **NLB(TCP passthrough, 6443)를 master 3대 앞에 두고 그 DNS를 endpoint로 쓰는 것** — 이 프로젝트도 이 방식을 따른다. NLB는 k8s 리소스를 전혀 알지 못하는 순수 L4 로드밸런서라 "control-plane을 AWS가 관리"하는 것과는 다르다(EKS와 성격이 다름).

### 3-3. 구축 순서(개요)
1. NLB 생성 → 타깃 그룹에 master 3대의 6443 포트 등록(헬스체크: TCP 6443 또는 `/healthz`)
2. 첫 master: `kubeadm init --control-plane-endpoint "<NLB DNS>:6443" --upload-certs --pod-network-cidr <CNI 대역>`
3. 나머지 master 2대: `kubeadm join ... --control-plane --certificate-key <key>` (`--certificate-key`는 2시간 후 만료 — 인증서 재업로드 필요할 수 있음)
4. worker 2대: `kubeadm join ...` (control-plane 플래그 없이)
5. CNI 설치: **Calico** (네트워크 정책 지원, kubeadm 조합 사례 풍부)
6. `kubectl get nodes`로 6개 노드 Ready 확인

---

## 4. Storage 노드 설계

- storage 노드 1대에 **NFS 서버**를 올리고, 별도 붙인 gp3 EBS 볼륨을 export한다.
- 클러스터에는 **nfs-subdir-external-provisioner**(Helm 차트)를 설치해 StorageClass로 동적 PV를 발급 — Postgres/Redis의 PVC가 이 StorageClass를 쓴다.
- **알려진 트레이드오프**: NFS 서버가 단일 노드이므로 그 자체가 새 단일 장애점이다. Longhorn 같은 분산 스토리지는 이 문제를 없애지만 "storage 전용 노드 1대" 개념 자체와 어긋나 이번엔 채택하지 않았다([architecture.md](./architecture.md) §7 열린 질문에 기록). 데이터 유실이 부담스러워지면 storage 노드의 EBS 스냅샷을 주기적으로 떠 두는 정도로 우선 완화한다.

---

## 5. 네트워킹 / 배치

- 6대 모두 같은 VPC/서브넷(AZ는 학습 목적상 단일 AZ로 시작 — 크로스 AZ 전송비 회피, jdh 인프라 문서와 동일한 절충).
- 보안그룹: worker↔master(API 6443, kubelet 10250), master↔master(etcd 2379-2380), 전 노드↔storage(NFS 2049)만 내부 허용, 외부는 NLB만 노출.
- CNI Pod 대역은 VPC CIDR과 겹치지 않게 지정(예: `192.168.0.0/16` Calico 기본값).
- 컨테이너 이미지: 초기엔 Docker Hub 프라이빗 리포 또는 ECR 아무거나로 시작 — 팀 크기상 ECR 과설계는 아니나 필수는 아님(비용 비교 후 결정).

---

## 6. 비용 추정 (ap-northeast-2, 온디맨드 개략치)

| 항목 | 단가(개략) | 수량 | 월 비용(개략) |
|---|---|---|---|
| t3.medium (master) | ~$35~40/월 | 3 | ~$105~120 |
| t3.medium (worker) | ~$35~40/월 | 2 | ~$70~80 |
| t3.small~medium (storage) | ~$20~40/월 | 1 | ~$20~40 |
| gp3 EBS(storage 볼륨, 100GB) | ~$8/월 | 1 | ~$8 |
| 각 노드 루트 EBS(gp3, 20GB×6) | ~$1.6/월 | 6 | ~$10 |
| NLB | ~$16.4/월 + LCU | 1 | ~$20~25 |
| **합계(개략)** | | | **~$235~285/월** (온디맨드) |

- 리전별 정확한 단가는 [AWS Pricing Calculator](https://calculator.aws/)로 재확인 필요(위 수치는 us-east-1 기준 공개 단가에 서울 리전 통상 프리미엄을 반영한 개략치).
- 절감 옵션: 학습 세션 단위로 클러스터를 켜고 끄기(상시 가동 아님), 1년 Savings Plan(최대 절반 수준 절감), storage 노드만 상시·나머지는 필요 시 기동 등 — [architecture.md §7](./architecture.md#7-열린-질문)에 열린 질문으로 남김.

---

## 7. 구축 순서 (전체)

1. **로컬 개발**: Docker Compose로 FastAPI·수집기·Postgres·Redis 통합 개발·테스트(architecture.md §3 애플리케이션 계층 그대로).
2. **이미지화**: 서비스별 Dockerfile 작성, 로컬에서 빌드·태깅.
3. **EC2 프로비저닝**: VPC/서브넷/보안그룹 + EC2 6대(Terraform 권장, jdh 인프라 문서와 도구 통일).
4. **kubeadm 클러스터 구축**: §3 순서대로 control-plane HA 구성 → CNI 설치 → worker join.
5. **Storage 연결**: NFS 서버 세팅 → nfs-subdir-external-provisioner 설치 → StorageClass 확인.
6. **앱 배포**: Postgres/Redis(StatefulSet/Deployment + PVC) → FastAPI/수집기(Deployment, 수집기는 replica 1) → Service/Ingress.
7. **검증**: 노드 1대 강제 종료 후 API 서버 가용성 확인(HA 검증), NFS 노드 재부팅 후 PV 재마운트 확인.

---

## 8. 참고 자료

- kubeadm 공식 HA 가이드 — https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/high-availability/
- kubeadm HA 토폴로지(stacked vs external etcd) — https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/ha-topology/
- kubeadm HA 고려사항(keepalived 서브넷 제약) — https://github.com/kubernetes/kubeadm/blob/main/docs/ha-considerations.md
- kubeadm on AWS EC2 구축 가이드 — https://devopscube.com/setup-kubernetes-cluster-kubeadm/ , https://kitemetric.com/blogs/setting-up-a-multi-node-kubernetes-cluster-with-kubeadm-on-aws
- k8s 스토리지 옵션 비교(NFS/Longhorn/EBS CSI) — https://oneuptime.com/blog/post/2026-02-20-kubernetes-csi-drivers-guide/view
- AWS Lightsail/EC2 가격 — https://calculator.aws/
