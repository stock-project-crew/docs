# A단계 진단 결과 (11/14)

- 기준: back-end `732cb39`, front-end `cd43b47`, docs `156e533`(모두 main). dataeng `8be9e28`.
- 리뷰어 9개가 읽기만 해서 낸 결과를 모았다.
  - 문서와 코드의 차이 5개: 공통 / 포트폴리오 화면·계산 / 포트폴리오 연동·스냅샷·데이터 / 알림 / 데이터 계약
  - 테스트 문서 1개, 코드 리뷰 2개(백엔드, 앱), 주석 1개
- 표기
  - [확인]: 세션에서 코드를 직접 다시 본 것
  - 무표기: 리뷰어 보고(파일:줄 근거가 붙어 있음)
- 자격증명 갱신 작업(back-end feat/credential-refresh, front-end 미커밋)은 "작업 중"이라 차이에서 뺐다.
- 주석 지칭 전체 목록은 `comment-refs.tsv`에 있다.

---

## 1. 즉시 위험 — 보안·개인정보

| # | 내용 | 근거 | 영향 |
|---|---|---|---|
| R1 | `dataeng_writer`가 `app` 스키마 전체에 DML을 갖고, 기본 권한으로 새 표에도 자동으로 붙는다. 회수 대상은 app_user·push_device·flyway 쓰기뿐이라 auth_session·account·alert*·position_*가 열려 있다. [확인] | k8s/db-roles-job.yaml:69-86 | writer 자격을 가진 쪽이 자기가 고른 토큰의 SHA-256으로 auth_session 행을 넣으면 아무 사용자로 갱신(로그인)할 수 있다. account.user_id·credential_ref도 바꿀 수 있다. 데이터팀 코드는 app에 쓰지 않는다. 운영 DB의 실제 권한은 확인하지 않았다 |
| R2 | 앱이 로그인·로그아웃·만료 때 조회 캐시를 비우지 않는다. 캐시 키에 사용자가 없다. [확인] | front-end App.tsx:19, AuthContext.tsx, keys.ts | 같은 폰에서 계정을 바꾸면 30초 안에는 앞사람의 총자산·계좌·알림이 보이고, 5분 안에는 앞사람 값이 먼저 그려진다. 테스트(X2)는 테스트용 캐시 설정(gcTime 0)이 달라 이 문제를 구조적으로 잡지 못한다 |
| R3 | reader도 app 전체를 SELECT할 수 있어 계약(alert_watchlist와 CDC 대상만)보다 넓다 | db-roles-job.yaml:69-70 | manual_cashflow.memo, 알림 등 사용자 데이터 노출 범위가 넓다 |
| R4 | 로그인 시도 횟수 제한이 없고 bcrypt CPU limit도 없다 | AuthController.java:45-55 | 외부 노출 범위(Ingress)가 판단 불가라 심각도가 미정이다 |

## 2. 사용자에게 틀린 숫자·문장이 보임

| # | 내용 | 근거 |
|---|---|---|
| N1 | 오늘 새로 연동한 계좌의 총자산 전체가 "직전 거래일 대비" 이익으로 잡힌다. 해제 계좌는 막았지만 신규 계좌는 빠졌다 [확인] | SnapshotViewService.java:269-285, SnapshotCalendarMapper.java:106 |
| N2 | 자산 변화 문장이 편입·제외를 모른다. 넣은 돈이 양수여도 "…원을 뺐거든요"가 나올 수 있다 | front-end assetChange/Sentence.tsx:36-66 |
| N3 | `계좌 제외`가 양수로 보여 항등식이 화면에서 맞지 않는다(D-29), 번 돈과 같은 들여쓰기다(D-30) | FlowList.tsx:51-54 |
| N4 | 요약·종목·실현손익·종목 상세 응답이 여러 질의를 트랜잭션 없이 던진다. 한 화면에 다른 시점의 값이 섞일 수 있고, 렌즈 검사에서 일시 500이 날 수 있다(자산 변화만 REPEATABLE READ) | SnapshotViewService.java:151-171 외 |
| N5 | 종목 하나가 마스터에 없으면 계좌 전체가 빠진다. 그런데 계좌는 CONNECTED(연동됨)로 보인다(SG-16 미반영, D-19) | LineCalculator.java:33-35, RunProcessor.java:87 |
| N6 | 예수금 통화가 일부 빠지면 총자산이 조용히 준다(SG-20 미반영, D-21) | LineCalculator.java:48-56 |
| N7 | 경계 이월 경고의 계좌 수를 두 번 센다(SG-06 미반영, D-05) | AssetChangeViewService.java:197-199 |
| N8 | 실현손익 목록에서 미포함 체결 행이 사라진다(SG-10 미반영, D-23). 종목 상세는 다른 규칙이다 | RealizedPnlViewService.java:79-81 |
| N9 | 해외 종목 매도는 실현손익이 늘 "미포함"이다(평단 설계가 정한 한계) | BasisBuilder.java:190 |
| N10 | 앱 비율 반올림에 부동소수 오차가 있다(1.15→1.1%) | front-end format/number.ts:42-48 |
| N11 | 입출금 POST에 멱등 키가 없다(네트워크 재시도 때 중복). 앱 버튼 쪽 이중 탭 잠금은 있다 | ManualCashflowService.java:47-63 |

## 3. 운영 안정성

| # | 내용 | 근거 |
|---|---|---|
| O1 | 처리할 때마다 예외가 나는 실행이 있으면 position_build 기록이 남지 않는다. 확정은 날짜 단위 전역이라 그날과 이후 날짜의 확정이 전 사용자에 대해 멈춘다. 단서는 warn 로그뿐이다 | Finalizer.java:102-130, RunProcessor.java:56-63 |
| O2 | 메트릭(Micrometer/Prometheus)이 없고 health만 있다. 스냅샷 틱 소요, 발송 적체, 확정 지연을 관측할 수 없다 | build.gradle.kts, SnapshotJobs.java |
| O3 | 자동 배포 롤링 중 옛 파드와 새 스키마가 함께 돈다. 호환되지 않는 마이그레이션(V19 같은 유형)을 막는 장치가 없다 | V19, deployment.yaml |
| O4 | 스케줄 풀 4에 작업 5(주석은 "넷"). 웹 종료 20초 + 스케줄 종료 20초가 grace 30초를 넘을 수 있다 | application.yaml:28-36 |
| O5 | 발송 기한을 알림의 cadence로 판정한다. 데이터 닫힘으로 종가 평가된 장중 알림 발화도 30분 기한이다 [확인] | DeliveryMapper.java:29 |
| O6 | 재연동 전에 요청된 옛 수집 행이 같은 SSM 이름이라 새 키로 수집되고, CONNECTED 전이를 일으킬 수 있다(linked_at은 표시에만 쓴다) | PositionWriteMapper.java:85-86 |
| O7 | 계좌 등록·해제가 행 잠금을 쥔 채 SSM을 호출한다(최대 10초). put 뒤 커밋이 실패하면 고아가 생기고, delete 뒤 커밋이 실패하면 연동 중인데 자격증명이 없다 | AccountLinkService.java:50-96 |
| O8 | 잠금 순서 예외(계좌 → 이후 날짜)를 Postgres 재배치에 맡기고 실측하지 않았다. 주석끼리도 모순이다 | RunProcessor.java:142 vs PositionWriteMapper.java:16 |
| O9 | Finalizer 후보가 max(snapshot_run)+1부터다. 앞에 빈 날이 있으면 막힌다 | Finalizer.java:61-64 |

## 4. SG 결정은 했는데 코드에 반영되지 않은 것 (결함 열림)

| SG | 내용 | 결함 |
|---|---|---|
| 04 | 해제 계좌의 지난 입출금 입력 | D-04 |
| 06 | 경계 이월 경고는 필터 안 계좌만 | D-05 |
| 10 | 미포함 체결 행도 목록에 보이기 | D-23 |
| 11 | 권한을 끈 기기의 등록 삭제 | D-24 |
| 14 | 요약에 "N개 계좌가 MM-DD 기준" 한 줄 | D-18 |
| 15 | 캘린더 공백일을 확정으로 안내하지 않기 | D-15 |
| 16 | 미매칭 종목이면 계좌 이월 + 첫 수집 안내 | D-19 |
| 19 | 막 건 장중 알림의 시세 없음 = 데이터 없음 | D-20 |
| 20 | 예수금 통화 누락이면 이월 | D-21 |
| 24 | 누락일은 종류별·캘린더 일부 공백 처리 | D-16, D-31 |
| 26 | 마스터에서 빠진 종목은 마지막 이름 표시 | D-25 |
| 27 | 상장폐지 종목은 확인 불가로 | D-26 |
| 30 | 서버가 거절할 날짜면 거절 이유 먼저 | D-28 |
| 32 | 500 message를 화면에 보이지 않기 | D-33 |
| 37 | 형식 오류는 400 INVALID_REQUEST | D-35 |
| 40 | "다음 수집" 안내 시각 | — |
| 35 | 손익 탭 처음 기간 — **미결** | — |
| 38 | 미리보기 칸 오류를 언제부터 — **미결** | D-39 |

## 5. 앱 코드 (R2 외)

- 중
  - 오류가 있으면 데이터를 들고 있어도 본문을 오류 화면으로 바꾼다(ScreenFrame.tsx:82-90).
  - 조건을 바꾼 조회가 실패하면 필터 컨트롤이 사라져 그 탭에 갇힌다(PositionsScreen.tsx:168 외).
  - focusManager·onlineManager를 연결하지 않아 앱이 앞으로 와도 다시 받지 않는다.
  - ErrorBoundary가 없고 응답을 런타임 검증 없이 캐스팅한다. 자동 배포로 서버가 먼저 바뀌면 크래시할 수 있다.
- 하
  - 타임아웃이 없다.
  - 늦은 401에 갱신을 한 번 더 한다.
  - 알림 경로 id를 인코딩하지 않는다.
  - 오늘 날짜를 기기 시간대로 계산한다.
  - 무효화 목록을 문자열로 관리해 instrument-detail이 빠졌다.
  - 이중 탭 보호가 두 방식이다.
  - 큰 목록을 ScrollView로 그린다.
  - 화면 간 중복 컴포넌트, 죽은 코드(Placeholder, alerts.device_id)가 있다.
  - 테스트용 QueryClient가 앱과 다르다.

## 6. 테스트 문서·테스트 코드

| # | 내용 |
|---|---|
| T1 | 자산 변화 항등식 테스트가 동어반복이다. 서버가 투자손익을 잔차로 계산하므로 편입·제외가 틀려도 통과하고, 실제로 D-01을 놓쳤다 [확인] |
| T2 | 판정 질의 Q-PF7-PAIR가 구현(SnapshotPairResolver)을 베꼈고, D-01이 결함으로 정한 옛 의미를 쓴다 |
| T3 | "둘 다" 1등급 10건이 연계 실행 없이 통과로 적혀 있다 |
| T4 | 결함 등급이 케이스 등급보다 일관되게 낮다(D-21 S2, D-18·D-16 S3 등). S1 정의대로면 S1 후보다 |
| T5 | 종료 조건 판정 기록이 없다. 1등급 실행 94%, S1 잔여, 앱 CI 없음, 운영테스트·품질 검사 산출물 없음 |
| T6 | 동시성 테스트(*ConcurrencyTest, DeliveryDispatcherTest:208)가 케이스에 연결돼 있지 않다. 동시성을 범주만으로 3등급에 넣었다 |
| T7 | 빠진 범주: 미국 서머타임 종료, 금액 정밀도, 외부 API 타임아웃, 백업·복구, 마이그레이션 롤백, 관측 |
| T8 | 인용 테스트 표본 14건 중 6건이 케이스 핵심을 검증하지 않는다(AL8-06은 반대 전제) |
| T9 | 문서 유지: SG가 결함 목록에 섞임, 근거 "—" 결함 3건, 숫자·기준 커밋 낡음, 제목 배치 오류, 일정 변경 미반영 |
| 잘된 점 | 분기 대응표 약 750행, ID 추적, 실패 30건 모두 결함 연결, 줄 단위 원인, 증거 436폴더, 권한·소유를 같은 응답 수준까지 검증 |

## 7. 문서 쪽 (E단계 입력)

- **문서끼리 모순**
  - 포트폴리오 §8.8 ↔ 세션 설계 §4.2(재사용 판정 범위)
  - 렌즈 토글 이름 두 개
  - SG-10 ↔ 종목 상세 범위
  - 항등식 부호
  - §2.3 ↔ §8.7 새로고침
  - 알림 상세 market
  - "재개돼요/이어져요"
  - held_since 표
  - 기기 등록 시점
  - PLB §2 ↔ §5.1 ↔ §7 확정 불변
  - DISCONNECTED 수집 행
- **계획서에만 있고 코드에 들어간 알림 결정** (A로 끌어올림): 중복 방지 강화 조건, 잠금 순서, 발송 임대·재시도·기한, 영수증, 오류 코드, observed 모양, 결측 사유, 지연 판정 시각, 따라잡기 상한, 해시 규칙
- **구현되지 않은 문서 내용**: 카탈로그 deprecated·spec_version 업캐스팅
- **낡은 레포 문서**: decisions.md 인증·CORS, decisions-deploy 상태 점검, deployment.yaml 주석, 두 README, dataeng README의 GRANT·DONE 기준
- **데이터 계약**: "현재 상태" 칸 대부분이 낡았다. 이미 해소된 N·Q가 많다. 알려진 한계 후보 17개와 KIS 전용 잔재 목록이 있다
- **테이블 정리**: 리뷰어가 P 7용 12개, A 7용 7개를 정리했다. 다만 보고서는 이 세션 대화에만 있다. E단계에서 문서를 쓸 때 코드 기준으로 다시 뽑는다(절별 "현행 사실"도 마찬가지).

## 8. 주석

- **지칭**: main 293줄, test 149줄, 앱 101줄. § 외에 계획 작업 번호, Review Focus, 사례 #n도 있다.
  - "설계 §"와 "스펙 §"가 패키지마다 다른 문서를 가리킨다.
  - SG-·D- 형식은 0건이다.
- **일회성**: 확정 15건(대부분 "그 기능이 아직 없는 서버" 호환 서술), 애매 13건. TODO·커밋 해시·날짜는 0건이다.
- **문체가 두 갈래다**
  - 포트폴리오 조회·auth: 문서 없이 읽히는 "왜" 중심이다.
  - alert·앱 alertEditor: "짧은 이름 + 지칭" 형식이다.
  - 지칭을 걷어내면 alert/catalog·alert/api/dto·alertEditor가 얇아지므로 핵심 문장을 풀어 넣어야 한다.
- **마이그레이션 컬럼 주석**: 있음 2, 대체로 있음 3, 일부 12, 테이블만 1(manual_cashflow). 먼저 채울 곳은 position_line, position_basis, auth_session, alert·alert_state, manual_cashflow.amount이다.

## 9. 고도화 후보 (D단계 재료)

- 백엔드
  - A. 배치 규모 실험(합성 데이터 10·100배, EXPLAIN)
  - B. 조회 API 부하 테스트(k6, look-through·발화 목록)
  - C. 잠금·교착 실측
  - D. 리더 없는 복제본의 비용(LOST 비율, 분할 비교)
  - E. 관측 지표와 경보
  - F. 마이그레이션 호환 테스트
- 앱
  - 세션 경계 캐시 격리
  - 생명주기·오프라인 UX
  - 응답 계약 안전망(ErrorBoundary, OpenAPI 타입)
  - 공통 화면 키트
- 쿼리·인덱스 개별 후보
  - etf_constituent `(etf, as_of)`
  - collection_run `account_ref`
  - alert_event user_id 비정규화
  - pg_trgm 검색
  - 실현손익 기간 조건의 시간대 식

## 10. 회고 소재 (모음)

- **동시성**
  - 리더 없는 복제본(조건부 UPDATE + prev + UNIQUE, 대가는 중복 계산과 롤링 중 엣지 유실)
  - 잠금 순서 규약과 그 예외
  - 갱신 토큰 회전(행 잠금, 직전 해시 + confirmed, 감수한 창)
  - 앱 쪽 세대 번호
  - 테이블 대기열 발송(SKIP LOCKED + 임대 + 트랜잭션 밖 호출)
- **멱등성**: 처리 기록 테이블(position_build, basis_build, sync_run), POST /sync 열린 행 공유
- **정합성**: GROUPING SETS로 Σrows = total 구조 강제, 렌즈 판정 조각 공유와 총합 검증, 자산 변화 REPEATABLE READ(한 곳에만 둔 것이 N4로 이어짐)
- **보안**
  - 소금 친 HMAC account_ref, SSM 쓰기만, 누출 차단, DUMMY_HASH, 오류 디스패치
  - 반대로 R1(회수 목록 방식이 새 표를 자동으로 열었다)과 R2(공용 기기 원칙이 앱 메모리까지 이어지지 않았다)
- **팀 경계**
  - collection_run 계약
  - 계약에 없던 암묵 의존이 사고로 드러남(finished_at, credential_ref 시한, DONE 비율)
  - 컬럼이 맞아도 의미 계약이 어긋남(adj_factor=1)
  - 진행 기록 칸이 실측보다 늦었다
- **문서 운영**: 확정이 두 층(is_final, snapshot_run)이라 서술이 엇갈림, 새 컬럼을 기존 판정이 따라가지 못함(O5)
- **테스트**: 기대값의 독립성(T1·T2), 등급 기준 일관성(T4), 종료 판정(T5)
- **놓친 역량**: 부하 0건, 동시성은 3등급, 관측 없음, 인덱스는 기준만
