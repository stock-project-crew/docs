# 문서 지도 (0단계 결과)

- 기준: 세 레포 모두 origin main이다(docs `156e533`, back-end `732cb39`, front-end `cd43b47`). dataeng도 main이다.
- 표기: [확인]은 파일이나 grep으로 직접 본 것이고, [추정]은 정황으로 판단한 것이다.

## 1. 기준선

main에 반영된 것:
- docs `docs/kis-only-tests`: 인증 정보 갱신 스펙, 종가 평가, 원화 평단 내림, 울린 시각 정렬, 세션 만료 뒤 푸시, iOS 날짜 칸
- back-end `fix/avg-cost-floor`: 종가 평가, 원화 평단 내림, 울린 알림 정렬

작업 중이라 제외한 것(리뷰 말단에 다시 받아 현행화한다):

| 위치 | 담긴 것 |
|---|---|
| back-end `feat/credential-refresh` (main보다 11커밋 앞섬) | 계좌 정보 값·가린 계좌번호, `PUT /accounts/{id}/credentials`, collection_alert 판정 |
| front-end 커밋 안 한 변경 34파일 | 인증 정보 갱신 화면, 수집 안내 카드 |

→ 스펙에는 인증 정보 갱신·수집 안내가 이미 있지만 코드 main에는 없다. 1단계 비교에서 이 차이는 "작업 중"으로 표시하고 넘어간다.

## 2. 문서 전수와 처리 방향

### 2-1. 설계 원천 (재편 대상)

| 문서 | 상태 | 처리 |
|---|---|---|
| specs/portfolio-management/…-portfolio-management-spec.md (1,774줄) | 살아 있는 원천. 헤더의 상태 표기와 §13만 낡음. §5 데이터 모델이 스키마보다 뒤처짐(position_build, basis_build, sync_run_account, auth_session 등이 없음) | 해체해서 overview / common / portfolio로 나눠 담는다 |
| specs/buy-sell-timing-alert/…-spec.md (1,629줄) | 살아 있는 원천. 헤더와 §18이 낡음. §10 alert_delivery 표가 낡음(SENDING, sent_at 없음). 계획서에만 있는 결정이 많음(발송 임대·재시도·기한, 오류 코드, observed 모양, 결측 사유 2종 등) | alert/ 세 문서로 나누고, 계획서에 있는 결정을 끌어올린다 |
| 추가 설계 10개 | 아래 2-2 | 새 구조로 흩어 넣는다 |
| specs/app-information-architecture.md | 현행 원천(11/13까지 수정됨) | 앱 구조 문서로 유지하고, 용어 절(§6)은 overview로 옮긴다 |
| specs/data-requirements.md | 현행 원천. 헤더 기준일이 낡음(10-05). CODEF·REAUTH 잔재가 있음 | 데이터팀 연동 계약 문서로 성격을 분명히 한다. §9·§10의 진행 기록은 뺀다 |
| specs/*/wireflow.{png,drawio,py} | 포트폴리오 그림에 로그인·계정 시트·인증 정보 갱신이 빠짐 [추정]. 알림 그림은 해피패스만 있음 | 5단계에서 실제 캡처로 대체한다. 개념도는 overview 아키텍처 재료로 쓴다 |
| specs/2026-06-28-feature-spec-and-tech-review.md | 일부 유효(원칙은 살아 있음. 엔티티·전달 방식·체결 TR 한계·국내 ETF 차단은 낡음) | 보관한다. §0·§1.1·§2.2·§5만 overview 재료로 쓴다 |
| specs/2026-06-22-portfolio-signal-design.md | 역사 기록(매수 전용, Kafka 계약) | 보관한다. 동기 서술만 overview 재료로 쓴다 |

### 2-2. 추가 설계 10개 → 행선지

| 문서 | 행선지 | 함께 고칠 것 |
|---|---|---|
| position-line-builder | **common/snapshot-pipeline (신설)** | §6.4 알림 보유 기준이 instrument-detail §3.8과 반대(낡음), §3 잡 그림이 3단계뿐(실제로는 5단계), §8과 manual-sync §2.2의 credential_ref 픽업 서술이 다름 |
| position-basis | 계산 규칙과 화면은 portfolio/holdings-basis, 잡·잠금은 snapshot-pipeline | 스펙 §4.3 "realized_pnl_line은 갱신하지 않음"과 모순(열린 포지션은 다시 씀) |
| account-link-api | common/account-link | 스펙 §7.1과 모순(시크릿 키 이름, 재연동 때 uuid, IRP 거부). 23:00 수집 시각을 단정함. 커밋 해시와 메일 전문이 들어 있음 |
| account-link-screen | common/account-link(화면) + 동기화 UI는 common/sync | § 지칭 117회 |
| manual-sync | common/sync | 스펙 §7.6 "완료 시 푸시"와 모순(폴링만 씀). 10-17 시점의 사실이 전제 절에 있음 |
| manual-cashflow-input | portfolio/asset-change | CASHFLOW_UNCOVERED를 earnings와 이중으로 정의함(판정 대상 계좌 기준도 다름) |
| earnings-cashflow | portfolio/asset-change | 위와 같음 |
| look-through | portfolio/look-through | **우선순위 규칙이 반대**("§9는 이 문서대로") [확인]. 스펙 §9.3·§2.6과 다름 |
| instrument-detail | portfolio/instrument-detail. 단 §3.8 "보유 중" 판정은 공통 정의로 뺀다 | 테스트 케이스 변경 표와 머지 순서 같은 작업 기록이 들어 있음 |
| auth-session | common/auth-session. 발송 부분은 alert, 배포 부분은 deploy-ops | 작업 번호 지칭("08", "13") |

목차 틀: 공통은 "근거 표 → 범위(만든다/만들지 않는다) → 본문 → 테스트 → 스펙과의 관계"다. 마지막 절 이름은 일곱 가지로 갈려 있다.

### 2-3. 레포 안 문서

| 문서 | 상태 | 처리 |
|---|---|---|
| back-end/docs/decisions.md | 결정 기록. **인증 절이 코드와 반대**(12시간 토큰, 세션 없음) [확인]. CORS 목록이 낡음 | 결정 기록(ADR) 산출물의 원천으로 쓰고, 설계와 겹치는 부분은 설계로 옮긴다 |
| back-end/docs/decisions-deploy.md | 배포 결정 | deploy-ops의 원천이다. 레포에 남길지 결정이 필요하다 |
| back-end/docs/ops/account-credentials.md, app-user.md | 운영 절차 | 레포에 남긴다(런북) |
| back-end/README.md | "계좌 연동·동기화·종목 상세 없음", "태그는 사람이 갱신"이 낡음 [확인 by 에이전트] | 고친다 |
| front-end/README.md | 화면 목록에서 3개 폴더가 빠짐 | 고친다. 구조 설명은 설계로 옮길 후보 |
| dataeng/README.md (collection_run, ⑦, 알림 데이터) | GRANT 예시가 백엔드 훅과 다름 | 데이터 계약 문서에서 인용만 한다(데이터팀 소유) |

### 2-4. 테스트 문서

| 문서 | 요점 |
|---|---|
| plan/…integration-and-operation-test-plan | 최상위 문서(일정, 결함 규칙, 종료 조건). 운영 일지·운영 런북 산출물은 없음 |
| plan/…test-environment-setup | 머신 전제 |
| test/…test-design | 시나리오 23개(PF4 없음), 추출 규칙, 등급. 코드 테스트 수가 낡음(110/42 → 154/55) |
| test/…test-cases | 454건: 통과 394, 실패 30, 유보 16, 미실행 14. 케이스 ID가 코드에는 없음(연결이 단방향) |
| test/…test-runbook | F/Q/A/R ID와 실행 절차 |
| test/…defects | D- 43건(열림 33), DT- 2건(DT-01 S1 열림), **SG- 스펙 공백 결정 43건**, RQ- 2건 |

- 부하·성능 테스트: 없음. 동시성: 문서에서는 3등급이지만, 코드에는 `*ConcurrencyTest` 3개 외에도 여럿 있다.
- SG 결정이 설계서에 반영됐는지: 설계서에 SG- 번호 지칭은 0건이다 [확인]. 하지만 내용만 반영됐을 수도 있어서, 반영 여부는 아직 모른다. 1단계에서 확인한다.

### 2-5. 근거·기록 문서 (보관, 회고와 ADR 근거)

| 문서 | 쓰임 |
|---|---|
| meetings/08-09, 09-27, 10-05 | ADR 근거(원장 3분리, 브로커 없음, 알림 안건 결정). 10-05의 "실시간 알림을 누가 울리나"는 **결정 기록이 비어 있음** |
| reviews/08-30, 10-15, 10-17 | 데이터팀 연동 회고(계약은 맞았는데 파이프라인이 끝까지 돈 적이 없음) |
| verification/kis-portfolio-assumptions, kis-realtime-and-pykis + verify/ 스크립트 | KIS 외부 연동 명세의 근거(입출금 TR 없음, IRP 제약, python-kis 조용한 실패) |
| research/* | 원천 선택 근거. 대부분 역사 기록 |
| guide/app-run-guide | 현행 실행 가이드 |
| plan/* (약 30개), .superpowers/sdd/* | 유지(작업용). 회고 소재로만 쓴다 |
| hhj/, jdh/, team-architecture-agreement.md | 팀원 초안. 근거로 쓰지 않는다 |

## 3. 코드 지도 (요약)

- 백엔드 패키지와 기능의 대응:
  - 공통: auth(+session) / account / sync / snapshot / domain / support
  - 포트폴리오: basis / cashflow / catalog / query / view / api / validation
  - 알림: 순수 패키지(catalog, spec, compile, indicator, evaluation, sentence)와 closure / data / runtime / delivery / service / store / validation / api
- REST 38개: auth 4, portfolio 11, accounts 3, sync 2, alerts 9, instruments 1, alert-events 5, devices 2, actuator. `PUT /accounts/{id}/credentials`는 브랜치에만 있다.
- 마이그레이션: migration은 V1·4·6·8·9·10·11·13·15·17·18·19, external 미러는 V2·3·5·7·12·14·16.
- 스케줄 작업 5개:
  - AlertJobs: 평가 1분, 발송 5초, 영수증 5분
  - SnapshotJobs: 1분, 5단계
  - AuthSessionJobs: 1시간
  - 복제본 2개에서 다 돌고, 리더 선출 없이 조건부 갱신과 잠금으로 중복을 막는다.
- 앱: 탭 6개 + 스택 화면 8개 + 알림 편집 모달. `placeholder` 화면은 쓰지 않는다.
- 외부 연동: SSM(자격증명), `data.collection_run`(팀 간 큐), 리버스 ETL 미러, Expo 푸시, ECR/ArgoCD.
- 설계 근거가 레포 밖(docs)에만 있는 영역: 세션, 동기화, basis, 알림 닫힘, 앱 푸시 라우팅, 토큰 갱신.

## 4. 확인된 모순·낡은 곳 (1단계 입력)

1. 포트폴리오 스펙 ↔ 추가 설계: 시크릿 키 이름과 전달, 재연동 uuid, IRP, 동기화 완료 알림, realized_pnl_line 갱신, 확정 전 수정, 렌즈 notice 2건, 입출금 미입력 판정·문구, 자산 변화 필터
2. 포트폴리오 스펙 내부: §7.3 "설명되지 않는 변화" ↔ §4.6 잔차 없음, §2.3 새로고침 ↔ §8.7, §8.5 env ↔ §5.1
3. 추가 설계끼리: 보유 판정 기준(line-builder ↔ instrument-detail), CASHFLOW_UNCOVERED 이중 정의, 잡 단계 그림, 남의 것·없는 것 응답(cashflow 404 / sync 403 / account 403 / instrument 404)
4. 알림 스펙 ↔ 계획서·코드: alert_delivery 상태, 발송 규칙, 오류 코드, observed 모양, 상세 문구 "재개돼요/이어져요"
5. 레포 문서 ↔ 코드: decisions.md 인증·CORS, 두 README
6. 시점 의존 서술: 수집 시각 23:00(가동 시간은 매주 바뀜), "2026-10-17 조회", 실측 수치, 커밋 해시, 작업 절차
7. 결정 기록 공백: 10-05 회의 결정, 데이터 요구사항 헤더 기준일

## 5. 3단계로 넘길 것 (코드 쪽)

- `db-roles-job.yaml`이 `auth_session`을 회수하지 않음 [확인]. 운영 DB의 실제 권한은 확인하지 않았다.
- 계좌 등록 때 트랜잭션 안에서 SSM 호출(최대 약 20초 잠금), 고아 파라미터 허용
- 롤링 배포 중 spec_hash 재기준이 오가며 엣지를 놓칠 수 있음
- 잠금 순환을 Postgres에 맡기고 실측하지 않았음
- `etf_constituent` 인덱스 보류(340ms→40ms 우회)
- `GET /auth/me`, `DELETE /devices/{id}`는 앱이 호출하지 않음. `placeholder` 화면은 쓰지 않음

## 6. 회고 소재 (모아 둔 것)

- 동시성: 리더 선출 없는 다중 복제본 평가(조건부 UPDATE, UNIQUE), 잠금 순서 규약(advisory 공유/배타 → 계좌 FOR UPDATE), 갱신 토큰 동시 갱신의 행 잠금, V19 LOCK TABLE
- 멱등성: 처리 기록 테이블을 멱등 키로(position_build, basis_build, sync_run), POST /sync의 열린 행 공유
- 대기열: 테이블을 큐로(alert_delivery SKIP LOCKED + SENDING 임대 + 트랜잭션 밖 호출, collection_run 팀 간 계약)
- 보안: 소금 친 HMAC account_ref, SSM 경로 분리로 백엔드는 읽지 못하게, 누출 차단, 앱의 자격증명 메모리 보관, 회전 토큰의 응답 유실과 재사용 구분, DUMMY_HASH 타이밍
- 쿼리·성능: GROUPING SETS로 가산성 보장, 부분 인덱스, look-through 340→40ms, 평가 한 주기 캐시와 "주기의 절반을 넘으면 분리" 기준
- 설계: 그레인 하나와 원장 3분리(리스크 격리. KIS 입출금 TR이 없다는 실측이 이를 증명), 투자손익 = 나머지, 3값 의미론, 이월하되 낡았다고 표시
- 협업·범위: 데이터팀 계약과 운영 실측 사이의 간극, Kafka 제안 → 브로커 없음, 범위 축소(KIS 전용)
- 놓친 것: 부하 테스트 없음, 동시성은 문서상 3등급, 운영테스트 산출물 없음, 인덱스·파티셔닝은 기준만 둠

## 7. 확정한 배치 (11/14)

원칙: 코드 레포에는 "어떻게 돌리고 운영하나"를, docs 레포에는 "무엇을, 왜"를 둔다. 현행 문서는 archive를 참조하지 않고, 필요한 근거는 본문에 사실로 옮겨 적는다. 살아 있는 문서는 파일 이름에 날짜를 붙이지 않는다.

```
docs/yhr/
├─ specs/          나누는 기준: 그 내용을 쓰는 기능
│   ├─ common.md         서비스 개요·원칙·용어, 시스템 구성, 앱 구조(IA), 로그인·세션, API 공통 규칙,
│   │                    데이터팀 연동(경계 원칙 + 계약 문서 링크), 서버 런타임, 역할 분담
│   ├─ portfolio.md      개요, 화면, 집계 모델, 원장과 등급, 계좌 연동·동기화, 스냅샷 생성·확정,
│   │                    데이터 모델, API, 검증, 상태 전수, 범위 밖
│   ├─ alert.md          개요, 화면, 조건 모델, 평가, 평가 런타임, 발화 전달,
│   │                    데이터 모델, API, 검증, 상태 전수, 범위 밖
│   ├─ data-contract.md  데이터팀과의 약속: 무엇을·언제까지·어떤 모양(컬럼표까지) + 안 지켜질 때 백엔드 대응 한 줄
│   └─ images/
│   설계서 원칙: 큰 스펙과 비슷한 구성으로 쓰되 구현 상세(클래스명, SQL·DDL, 테스트 목록, 마이그레이션 파일명,
│   켜는 절차, 브랜치·커밋, 시점 실측, 진행 기록)는 덜어낸다. 백엔드 테이블은 테이블 단위만 적는다
│   (역할·그레인, 키·유일성과 그 보장, 쓰는 쪽·읽는 쪽, 수명, 규칙에 나오는 컬럼·상태값의 뜻).
│   KIS 사실은 기능 문서에 사실로 적는다.
├─ decisions/      ADR. 거꾸로 모아 쓴다: 목록 초안 → 1단계 뒤 확정 → 작성
│                  파일마다 "당시 맥락·선택지·결정" + "돌아보며(잘된 점·대가·다시 한다면)"
├─ deliverables/   독립 산출물: 시나리오·기능명세·API 명세·화면 캡처·ERD·아키텍처도
├─ test/           + plan/의 테스트 계획 2개를 옮겨 옴
├─ plan/           그대로 둠(고치지 않음. 깨지는 링크는 감수)
├─ archive/        proposal(06-22·06-28) · meetings · reviews · research · verification
└─ review/         이번 회고 리뷰 작업물
(guide/는 없앤다. 앱 실행 가이드는 front-end로 옮긴다)

back-end/  README 고침 + docs 레포 링크 · docs/decisions*.md 삭제(ADR·설계서로 옮긴 뒤)
           docs/ops/ 런북 모음(account-credentials, app-user + 설계서의 "켜기 전 확인" 절 이동)
front-end/ README 고침 + 앱 실행 가이드
dataeng/   손대지 않음(데이터팀 소유)
docs/hhj, docs/jdh, team-architecture-agreement.md, docs/verify/  손대지 않음
```

이어지는 작업:
- 1단계: 옛 절 → 새 문서·절 대응표를 만든다(2단계에서 테스트 문서 근거 절을 기계적으로 치환하는 데 쓴다).
- 말단: origin main을 다시 받아 자격증명 갱신(back-end feat/credential-refresh, front-end 미커밋 변경)을 현행화하고, 산출물도 같이 점검한다.
  - 산출물마다 다시 만들기 절을 따라 재생성한다(ERD · API · 여정 · 구성도).
  - 설계서 · ADR · 테스트 문서 링크가 모두 열리는지 확인한다.
  - 계좌번호 · 이메일 · 실제 금액이 들어가 있는지 찾는다.
  - 고도화 실습이 끝났으면 "측정 안 함" 문장과 README «하지 않은 것» 절을 채운다.
