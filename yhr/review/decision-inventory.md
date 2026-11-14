# 결정 목록 (ADR 고르기용 전수, 11/14)

- 훑은 곳: docs `156e533`의 specs 전부(큰 스펙 2개, 추가 설계 10개, IA, 데이터 요구사항, 06-22·06-28 제안서), plan 31개, meetings·reviews·research·verification, test 결함 목록(SG·D·DT·RQ). back-end main `70d79cc`의 docs/decisions*.md, docs/ops, README, k8s, workflow, Dockerfile, application.yaml, 마이그레이션 주석, src/main/java의 "왜" 주석, git log 241커밋. front-end main `cd43b47`의 README와 코드 주석.
- 제외한 곳: docs/hhj, docs/jdh, team-architecture-agreement.md, yhr/review/(번호 대조에만 썼다), back-end `feat/credential-refresh`. front-end는 읽을 때 커밋 안 한 변경이 없었다. `docs/.superpowers`에는 결정 기록이 없고, back-end·front-end `.superpowers/sdd`는 git에 올라가 있지 않아 보조 근거로만 썼다.
- 총 **412건**: 동시성·잠금 24 / 멱등·정합성 38 / 쿼리·데이터 모델 58 / 보안·인증 34 / 운영·배포 47 / 데이터팀 연동 46 / 도메인(포트폴리오) 61 / 도메인(알림) 38 / 범위 15 / 기술 선택 23 / 앱 28. 판단 불가·애매는 22건이다.
- 정리 방법: 다섯 갈래로 나눠 읽은 뒤 합쳤다. 같은 결정은 한 줄로 합쳤다. 큰 계획서(QL·RULES·RT·PLB·ALA·MCF·FE1·FE2)는 키워드 주변만 읽었으므로, Task 본문 안쪽의 세부 결정은 빠졌을 수 있다.

**근거 약칭** (docs는 `yhr/` 기준)
- 스펙: PM = specs/portfolio-management/2026-07-28-portfolio-management-spec.md, AL = specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md, DR = specs/data-requirements.md, IA = specs/app-information-architecture.md, SIG = specs/2026-06-22-portfolio-signal-design.md, FTR = specs/2026-06-28-feature-spec-and-tech-review.md
- 추가 설계(specs/portfolio-management/, 뒤에 -d): PLB-d position-line-builder, ALA-d account-link-api, MCF-d manual-cashflow-input, SYNC-d manual-sync, ALS-d account-link-screen, PB-d position-basis, LT-d look-through, ECF-d earnings-cashflow, ID-d instrument-detail, AUTH-d auth-session
- 계획서(plan/, 앞에 p/): QL 08-09 query-layer, FE1 08-17 frontend-portfolio-app, FE2 08-30 frontend-remaining-views, RULES·RT 10-11 alert-backend-rules·runtime, FEA 10-11 frontend-alert, TEST 10-11 integration-and-operation-test, ENV 10-14 test-environment-setup, PLB 10-15, ALA 10-16, MCF 10-17, ALS 10-18 account-link-screen, MS 10-18 manual-sync, MSS 10-28 manual-sync-screen, PB 10-29, LT 11-04, EC 11-10 earnings-cashflow, SDK 11-10 expo-sdk-58, IDA·IDB 11-10 instrument-detail app·backend, KIS 11-10 scope-kis-only, CLO 11-11 alert-data-closure, AS 11-11 auth-session, IPS 11-11 investment-pnl-split, LO 11-11 logout-entry, FIRED 11-12 alert-fired-order, CRA·CRB 11-12 credential-refresh app·backend, IOS 11-12 ios-date-field, PLM 11-12 price-lag-market, REOPEN 11-12 push-reopen-after-expiry
- 기록: M0809·M0927·M1005 = meetings/, R0830·R1015·R1017 = reviews/, RS-ETF·RS-SEC·RS-BRK = research/, V-KPA = verification/kis-portfolio-assumptions.md, V-RT = verification/kis-realtime-and-pykis.md
- 레포: DEC = back-end/docs/decisions.md, DEP = back-end/docs/decisions-deploy.md, OPS-ac·OPS-au = back-end/docs/ops/account-credentials.md·app-user.md. 파일명만 적은 `.java`·`V*.sql`·`*.yaml`은 back-end, `fe:`는 front-end/src/. 7자리 해시는 back-end 커밋이다(front-end는 "front-end" 표기).
- 결과 흔적: D-·DT-·SG-·RQ- = test/2026-10-30-defects.md, R·N·O·T = review/diagnosis.md, "B단계"는 review/triage.md의 분류다(원천 아님, 대조용).

---

## 1. 동시성·잠금 (CC)

| ID | 결정(무엇을 골랐나) | 버린 대안 | 근거 위치 | 결과 흔적 |
|---|---|---|---|---|
| CC-01 | 리더 선출 없이 스케줄 작업 전부(평가·발송·영수증·스냅샷·세션 정리)를 모든 복제본에서 돌리고, 중복은 잠금이 아닌 데이터(조건부 UPDATE·UNIQUE·처리 기록)로 막는다 | 리더 선출, 분산 잠금, 별도 라이브러리 | AL:568-584; p/RT:13, 6360-6363; M0927:248; DEC:137-142; AlertJobs.java:10-11; SnapshotJobs.java:10-12; PLB-d:47 | 롤링 중 엣지 손실 감수(p/RT:301, DEC:150-151). LOST 비율 미측정(고도화 D). 동시성 테스트가 케이스에 안 묶임(T6) |
| CC-02 | 알림 잠금 순서: alert → alert_state → 종목 advisory. ONE_SHOT은 반영 전 alert를 `FOR NO KEY UPDATE`로 먼저. 평가 반영만이면 alert_state만 잠근다 | 모든 트랜잭션에 같은 순서 강제(옛 문서) | p/RT:146, 2201, 6369; DEC:147-148; AlertRuntimeWriter.java:26-28; RuntimeMapper.java:62 | `158601d` 문서 정정, `6310a66` 교착 테스트 |
| CC-03 | 종목별 alert_watchlist 갱신을 `pg_advisory_xact_lock(hashtext)`로 직렬화 | 기록 없음 | WatchlistMapper.java:18-22; `adf4697` | — |
| CC-04 | 만료 전이는 `UPDATE … RETURNING`으로 한쪽 복제본만 옮긴다 | 기록 없음 | p/RT:150; RuntimeMapper.java:28-35 | — |
| CC-05 | 발송 대기열은 `FOR UPDATE OF d SKIP LOCKED`로 100건씩 집고, SENDING + 2분 임대로 바꿔 커밋한다 | 기록 없음 | AL:582; p/RT:193, 205-206, 4298, 4408; DEC:157-166; DeliveryMapper.java:14-15, 81 | 스펙 §10 표에 SENDING 없음(doc-map §4.4) |
| CC-06 | Expo 호출은 DB 트랜잭션 밖(집기 → 전송 → 기록 트랜잭션) | 트랜잭션 안에서 호출(커밋 실패 시 재발송, 잠금·연결 점유) | p/RT:199-208; DeliveryDispatcher.java:19-24 | `55e1c6f`. 중복 푸시 감수(DEC:170-171) |
| CC-07 | 등록이 풀린 기기는 기록 커밋 뒤 하나씩 따로 지운다 | 같은 트랜잭션에서 삭제(발송기·영수증 확인기 교착) | p/RT:217 | — |
| CC-08 | 영수증 조회는 잠그지 않는다(같은 티켓을 두 복제본이 물어도 기록이 같다) | 잠금 | p/RT:226, 4342; DeliveryMapper.java:126 | — |
| CC-09 | 스냅샷 잠금 순서: 날짜 advisory → 계좌 `FOR UPDATE`(account_id 순). 실행 처리·계좌 확정은 공유, 날짜 확정은 배타. 키는 `'SNAP'` 두 칸 | 한 칸 hashtext 키(다른 잠금과 겹침), 실행 단위 재시도로 교착 감싸기 | PLB-d:294-302; p/PLB:7, 37, 3437; PositionWriteMapper.java:15-34 | O8: 예외(계좌 잠금 뒤 이후 날짜 잠금)를 Postgres에 맡기고 실측 안 함, 주석끼리 모순(RunProcessor.java:142 ↔ PositionWriteMapper.java:16). 고도화 C |
| CC-10 | 실행 처리는 잠정 이월 때문에 그 사용자 계좌 전부를 잠그고, 이후 날짜 공유 잠금만 계좌 잠금 뒤에 잡는다. 교착은 롤백 후 재처리로 감수 | 기록 없음 | PLB-d:298, 303-304 | O8 |
| CC-11 | 잠근 뒤 position_build를 다시 읽고 `ON CONFLICT DO UPDATE`로 기록 | 기록 없음 | PLB-d:305 | — |
| CC-12 | 평단(1.5단계)도 1단계와 같은 키 공간·같은 순서로 잠그고, 잠근 뒤 읽는다 | 기록 없음 | PB-d:146, 175; `dbb60d2` | — |
| CC-13 | 계좌 등록·해제·갱신은 계좌 행 잠금 → SSM 호출 → 커밋. 등록은 `INSERT ON CONFLICT DO NOTHING` 뒤 `FOR UPDATE`. SSM 시간 제한이 잠금 최대 시간이다 | 기록 없음 | ALA-d:245-273; p/ALA:7, 1681-1682; AccountLinkService.java:22-23; SsmCredentialStore.java:35 | O7(잠금 쥔 채 SSM, 고아·불일치) → B단계 받아들임. doc-map §5 |
| CC-14 | 잠금 조회는 MyBatis 캐시를 끈다. 소유 검사와 잠금을 한 문장(`lockOwned`)으로 합친다 | Guard를 따로 두기 | p/ALA:1592-1593, 1957; AccountLinkMapper.java:18-19 | — |
| CC-15 | `POST /sync`는 사용자 계좌 행을 account_id 순으로 잠가 생성기·동시 요청과 직렬화 | 기록 없음 | SYNC-d:127 | — |
| CC-16 | 동기화 닫기는 잠그지 않고 판정한 뒤 닫을 것만 `SKIP LOCKED`로 재판정하고 `finished_at IS NULL` 조건 UPDATE. 실행 행을 못 바꾸면 롤백 | 기록 없음 | SYNC-d:243; SyncMapper.java:128-140; SyncCloser.java:23, 80 | `a5fa678` |
| CC-17 | 갱신 토큰 동시 갱신은 refresh 해시 행 `FOR UPDATE` + 한 트랜잭션으로 줄 세운다 | 기록 없음 | AUTH-d:94; SessionService.java:56-57; AuthSessionMapper.java:40 | — |
| CC-18 | V19는 push_device를 비우기 전에 `LOCK TABLE … ACCESS EXCLUSIVE` | 잠그지 않고 비우기(다른 연결의 등록이 끼면 NOT NULL 추가 실패) | V19__auth_session.sql:18-21 | `70a426d`에서 추가(배포 전 수정, `47155af` 뒤). O3 유형 |
| CC-19 | 스케줄은 fixedDelay(겹쳐 돌지 않음). 평가 1분, 발송 5초(100건 차면 이어서), 영수증 5분, 스냅샷 1분, 세션 정리 1시간 | 스레드 1개(평가가 발송을 붙잡음) | p/RT:78-88; AlertJobs.java:11, 30, 39, 46; SnapshotJobs.java:35; AuthSessionJobs.java:19 | — |
| CC-20 | 스케줄 풀 크기 3 → 4 | 기본값 1 | p/RT:78-88; PLB-d:57; p/PLB:57, 68; application.yaml:28-32 | O4: 작업 5개인데 풀 4·주석 "넷" → B단계 고칠 것 |
| CC-21 | 자산 변화 render만 REPEATABLE READ 읽기 전용 트랜잭션으로 한 시점을 본다 | 기록 없음 | p/IPS:10, 66 | N4: 다른 조회는 트랜잭션 없이 여러 질의 → B단계 고칠 것 |
| CC-22 | (앱) 이중 탭은 ref로 잠근다 | `isPending`에만 의존(다음 렌더에야 반영) | p/MCF:3679; fe:screens/cashflows/CashflowForm.tsx:53, CashflowList.tsx:50, accountLink/AccountLinkScreen.tsx:31, accounts/useSyncCard.ts:47 | 진단 §5 "두 방식"(그냥 둠). N11은 서버 멱등이 없어 남음 |
| CC-23 | (앱) 로그아웃 세대 번호로 늦게 끝난 요청·갱신 결과를 버린다. 기기 등록은 세대 번호·진행 중 로그아웃 수로 멈추고, 로그아웃 요청은 3초에 AbortController로 끊는다 | 기록 없음 | AUTH-d:256-262; p/AS:499, 509; p/LO:9-11, 37-42; fe:api/client.ts:110-118; fe:push/device.ts:20-36 | — |
| CC-24 | (앱) 갱신은 single-flight. 401 받은 요청은 그 갱신을 기다렸다 재전송하고, 재전송의 401은 만료 처리. 만료 직전 사전 갱신 안 함 | 사전 갱신 | AUTH-d:198-209; p/AS:14; fe:api/client.ts:119-122, 303 | 진단 §5 늦은 401 재갱신 → B단계 그냥 둠 |

## 2. 멱등·정합성 (IC)

| ID | 결정 | 버린 대안 | 근거 위치 | 결과 흔적 |
|---|---|---|---|---|
| IC-01 | 평가 반영은 조건부 UPDATE(version 일치, `evaluated_as_of < :as_of`). version은 규칙과 같은 SELECT에서 읽는다. 0행이면 진 것으로 본다 | 따로 읽기 | AL:572-579, 1435-1436; RuntimeMapper.java:41-56 | — |
| IC-02 | 조건부 UPDATE에 `evaluated_as_of IS NOT DISTINCT FROM :prev`와 만료 안 됨(EXISTS)을 더한다. 스펙보다 엄격 | 스펙 조건만 | p/RT:119-127 | 스펙 미반영(진단 §7 "계획서에만 있는 알림 결정") |
| IC-03 | 발화는 `UNIQUE(alert_id, as_of)` + `ON CONFLICT DO NOTHING`. 충돌하면 발송 행을 만들지 않고 ONE_SHOT도 끝내지 않는다 | 기록 없음 | AL:580, 722; p/RULES:436; p/RT:144; V4__alert_tables.sql:72; RuntimeMapper.java:79 | D-03(S1): 충돌 시 엣지 기준이 참으로 남음 → SG-01, `964fe31`·front-end `0f59d96` |
| IC-04 | 상태 갱신·발화·발송 행·ENDED 전이를 한 트랜잭션으로 | 기록 없음 | AL:581, 1440; M0927:252 | — |
| IC-05 | ONE_SHOT이 울리면 version을 올린다. 사용자 변경(끄기·삭제·수정)도 version을 올려 평가기의 옛 결과를 막는다 | 기록 없음 | p/RT:145; AL:453; AlertCommandService.java:37-39 | — |
| IC-06 | 발송 결과 기록은 "아직 SENDING이고 집을 때의 attempts"일 때만. 일시 실패면 기록을 3번까지 재실행. 같은 푸시 두 번(기록 실패·읽기 시간 초과)은 감수 | 기록 없음 | p/RT:208, 220-221, 6392; DEC:170-171; RecordTransaction.java:9 | — |
| IC-07 | spec_hash가 바뀌면 울리지 않고 재기준만(배포 직후 일제 발화 방지). 결과가 UNKNOWN이면 기준·해시 모두 유지 | 상태에 평가기 코드 버전 저장(잦아지면) | p/RT:136-137, 301, 6372; FiringRule.java:10-12 | 롤링 중 재기준이 오가 엣지 유실 가능(doc-map §5) |
| IC-08 | 미리보기와 평가기는 같은 순수 패키지·같은 "시점 하나의 입력" 메서드를 쓰고 동등성을 Parity 테스트로 지킨다. 입력 수집 코드 차이는 감수 | 각자 계산 | p/RULES:85, 9617-9628; p/RT:6365-6366; DEC:110-124, 144-145 | — |
| IC-09 | 평가기는 신호 처리 여부를 따로 기록하지 않는다. `evaluated_as_of`가 그 기록이라 메모리 상태가 없다 | 별도 신호 처리 기록 | EvaluationRunner.java:38-41 | — |
| IC-10 | 처리 기록 position_build(`run_id UNIQUE`, 확정 행 `(account, as_of)` 부분 UNIQUE)를 멱등 키 겸 로그로 두고 지우지 않는다 | 기록 없음 | PLB-d:93-126, 418; p/PLB:7, 260, 558; V8__position_build.sql:1-21 | `b1db475`. O1: 매번 예외 나는 실행은 기록이 안 남아 전 사용자 확정이 멈춤 → B단계 고칠 것 |
| IC-11 | 실패 사유를 재시도 가능(데이터 지연 6종)과 최종으로 나누고, 재시도 사유는 확정 전까지 매 회차 다시 처리 | 기록 없음 | PLB-d:124, 207-214 | O1 |
| IC-12 | 수치·통화 null은 예외 대신 최종 사유 INVARIANT로 남겨 그 계좌만 이월 | 예외로 종료(뒤 날짜 확정 전체 정지) | PLB-d:214-218; LineCalculator.java:33-38 | O1(다른 예외 경로는 남음) |
| IC-13 | UNMATCHED_INSTRUMENT(재시도 사유)를 INVARIANT·종가 검사보다 먼저 판정 | 반대 순서(재시도가 영구 실패가 됨) | PLB-d:216; p/PLM:26; LineCalculator.java:33-38 | `4d961ef`(승인 기록은 비추적 sdd에만) |
| IC-14 | 같은 날 더 새로운 실측이 있으면 OLDER_THAN_EXISTING으로 건너뛴다. 처음 보는 실행을 재시도보다 먼저, 모르는 account_ref는 고르지 않는다 | 기록 없음 | PLB-d:161; RunProcessor.java:121; CollectionRunMapper.java:28-30 | — |
| IC-15 | 잔고 시각 < requested_at이면 STALE_BALANCE로 재시도 | 기록 없음 | PLB-d:210, 220 | — |
| IC-16 | 잔고 한 벌 = 그 계좌 cln_deposit `max(source_as_of)`, 실행 finished_at 이하만 | 종목마다 최신 행(판 종목이 남음) | PLB-d:169-173, 416 | SG-25(현 동작을 기대값으로). SG-20/D-21·N6(통화 일부 누락 시 총자산이 조용히 줄어듦) |
| IC-17 | 연동 상태 전이는 그 계좌에서 requested_at이 가장 늦은 실행일 때만 | 기록 없음 | PLB-d:333 | O6: 재연동 전 옛 행이 CONNECTED 전이 가능 → B단계 받아들임 |
| IC-18 | basis_build PK `(account_id, as_of)`를 1.5단계 멱등 키로. 계좌별로 앞으로만 가고, 계좌×날짜마다 트랜잭션 하나 | 기록 없음 | PB-d:96-108, 173, 421; V13__position_basis.sql:1, 28-34; BasisBuilder.java:32-35 | `dbb60d2` |
| IC-19 | position_basis는 확보 구간 전체를 매번 다시 접는다(계좌 단위 delete+insert) | 증분 누적 | PM:561; PB-d:161 | — |
| IC-20 | realized_pnl_line은 trade_id upsert. 열린 포지션 행만 금액·등급을 함께 갱신하고 청산·강등 전 행은 고정, 이번 계산에 안 나온 매도 행은 지우지 않는다 | insert-only, 한쪽만 갱신, 삭제 | PM:562, 1599; PB-d:117, 174, 279-293, 410 | 충돌 PM:669·1600("갱신 안 함") → SG-22로 평단 설계 채택 |
| IC-21 | 계산할 수 없는 값(avg_cost, 원가·손익)은 0으로 채우지 않고 null. 원인 모르는 옛 행의 seed_reason은 비운다 | 0 채움, 원인 지어내기 | PB-d:93, 119, 129; PM:306 | — |
| IC-22 | 실패 계좌 하나만 롤백하고 다음 계좌로. 스냅샷 회차는 자격증명 → 반영 → 확정 → 동기화 닫기 → 평단이고 한 단계 실패가 다음을 막지 않는다 | 기록 없음 | PLB-d:47, 282; PB-d:30-45, 167-169; SYNC-d:229-237; SnapshotJobs.java:11-12, 46 | `58136ef`(단계 격리) |
| IC-23 | 팩트 불변식(그레인 유일, fx 필수, 이월이면 source_as_of<as_of)을 쓰기 전과 조회 시 모두 검사하고, 위반이면 500 FACT_INVARIANT_VIOLATED로 크게 실패 | 조용히 넘김 | PM:1571-1586; PLB-d:222-229; p/QL:656-658; ApiExceptionHandler.java:56 | SG-25. SG-32/D-33(내부 문장이 화면에 노출) |
| IC-24 | look-through 총합 보존(평가·원가)을 렌즈 요청마다 검증하고 어긋나면 오류 | 틀린 금액 표시 | PM:1608; LT-d:159 | N4(트랜잭션 없어 렌즈 검사가 일시 500 가능) |
| IC-25 | `POST /sync`는 진행 중이어도 거절하지 않고 매번 새 sync_run을 만들되, 같은 계좌·요청일의 열린 USER 행을 공유(다른 날 행은 공유 안 함) | 진행 중 거절, 다른 날 공유 | SYNC-d:128-137 | SG-40(열린 실행 안내 시각) |
| IC-26 | sync_run은 사용자에 속하고, sync_run_account는 열린 동안 도출만 하다 닫을 때 굳힌다. already_final은 요청 때 한 번 예측해 저장 | 계좌 소속, 결과 복사 | p/MS:108; SYNC-d:102, 265-274, 327 | D-41(`f65358a`), D-15 |
| IC-27 | 같은 account_ref는 `ON CONFLICT DO NOTHING`, 재연동은 같은 account 행(같은 account_id) 재사용 | 새 uuid 행 | PLB-d:27, 417; ALA-d:266, 529; AccountLinkMapper.java:32, 38; `9384c6e` | 충돌 PM:1110("새 uuid"). O6 |
| IC-28 | SSM에 쓴 뒤 커밋이 실패해 남은 파라미터는 보상 삭제하지 않고 다음 등록이 덮는다. 해제는 SSM 삭제 실패면 롤백 503 | 보상 삭제·즉시 정리 | ALA-d:275, 279-290; p/ALA:2776-2778; OPS-ac:51-54 | O7(delete 뒤 커밋 실패면 연동 중인데 자격증명 없음) |
| IC-29 | 실패 계좌는 직전 성공분을 이월해 총자산에 넣고 낡음을 표시한다. 트리거는 "그날 collection_run 최종이 DONE이 아니면" 하나, 계좌 단위 독립. 리버스 ETL 실패도 같이 | 실패 계좌 빼기(총자산 급락) | M0809:310-312; DR:444, 617-618; R0830:522; PM:1139, 1163-1169, 1196-1201, 1578 | SG-02·SG-14/D-18·SG-16/D-19·N5·SG-20/D-21. DT-01(S1): 해외 조회 실패도 DONE이라 이월이 안 붙음 |
| IC-30 | 스냅샷은 만든 값을 나중에 고치지 않는다. is_final로 확정·잠정을 가르고 확정 행은 수동 동기화가 덮지 않는다(ALREADY_FINAL) | 소급 수정 | PM:958, 960, 1580-1582, 1745; DR:472; PLB-d:131 | 충돌 PLB-d:412(snapshot_run 전이면 씀). SG-43(미국 종가를 소급 못 해 미결) |
| IC-31 | 확정을 두 층으로: 계좌 행 is_final과 날짜 snapshot_run. snapshot_run을 알림 평가 신호로 쓰고 알림이 읽는 확정본도 snapshot_run 있는 날로 한정. 대상 0개인 날도 마감 뒤 쓴다 | is_final만 보기(일부 계좌 확정일 오독) | PM:556; PLB-d:286, 288 | 진단 §10 "확정 두 층이라 서술이 엇갈림" |
| IC-32 | 확정은 가장 이른 미확정 영업일부터 날짜 순, 막히면 뒤 날짜를 보지 않는다. 마감은 다음 KR 영업일 08:00. 확정 이월은 Finalizer만 | RunProcessor에서 이월 | PLB-d:263-268, 290; Finalizer.java:26-27; RunProcessor.java:23 | O1(한 계좌가 전 사용자 확정 정지). O9 → B단계 그냥 둠 |
| IC-33 | 캘린더에 그날이 없으면 평일로 어림하지 않고 건너뛰며 확정을 멈춘다 | 비영업일로 간주·평일 어림(휴장일 가짜 스냅샷 확정) | p/PLB:36; SG-15 | D-15(동기화는 확정으로 안내). 알림 쪽은 반대로 어림(AMB-03) |
| IC-34 | 확정 전 잠정 이월: 한 계좌만 갱신된 날 같은 사용자의 다른 계좌를 직전 값으로 채운다. 늦게 생긴 앞 날짜 라인도 이후 날짜로 이월 | 이월은 실패 계좌만 | PLB-d:39-42, 231-245, 414; p/PLB:2058, 2200-2228; `1f8203d`, `4d961ef` | 스펙(PM)에 없는 확장 |
| IC-35 | 직전 영업일 라인이 있는 계좌만 확정 대상에 편입. 재연동 직후엔 옛 보유를 이월하지 않는다 | 기록 없음 | PLB-d:251-259, 411 | 충돌 PM:1577("유효 계좌 전부"). N1(신규 계좌 총자산이 일간 이익으로) |
| IC-36 | 같은 날 수동 동기화 실측을 확정으로 승격(PROMOTED) | 기록 없음 | PLB-d:277, 413 | 충돌 PM:960("EOD 배치만 is_final") |
| IC-37 | USD·KRW 외 통화는 1로 환산하지 않고 계좌를 실패(FX_MISSING) | 1로 환산 | p/PLB:35 | SG-25(폴백할 환율 없으면 라인 없음) |
| IC-38 | 잔고와 예수금은 같은 source_as_of로 쓴다는 것을 데이터 계약으로 요청 | 기록 없음 | R1015:157; PLB-d:416 | RQ-02(보내기 전) |

## 3. 쿼리·데이터 모델 (QD)

| ID | 결정 | 버린 대안 | 근거 위치 | 결과 흔적 |
|---|---|---|---|---|
| QD-01 | 저장 그레인을 position_line `(as_of, 계좌, 종목)` 하나로. 축은 계좌·종목 마스터 조인으로 유도하고 뷰는 그 위 GROUP BY | 기록 없음 | PM:43-58, 441-447; M0809:266-274 | — |
| QD-02 | 원장을 셋(보유 스냅샷 / 현금흐름 / 거래)으로 나눠 리스크를 격리한다. 6개 뷰 중 4개가 스냅샷만 쓴다 | 같은 팩트에 담기(그레인이 달라 불가) | PM:69-81, 605-630; M0809:280-288 | V-KPA:267 실측(KIS 입출금 TR 없음)이 격리 효과를 보여 줌 |
| QD-03 | 금액·수량만 저장하고 비율(수익률·비중) 컬럼은 두지 않는다. MigrationLintTest·ArchUnit으로 강제 | 라인에 비율 저장, 리뷰로만 강제 | PM:85-91, 467, 1051, 1626; M0809:278; p/QL:24, 169-183; DEC:22-24; Line.java:9 | — |
| QD-04 | Portfolio는 테이블이 아니라 집계로 파생한다. 사전 집계·집계 캐시·전개 결과 저장을 두지 않는다 | 집계 캐시 | FTR:282; PM:477, 1748 | — |
| QD-05 | 집계(GROUP BY·SUM)는 SQL, Java는 파생 지표와 조립만. 행·소계·합계를 GROUPING SETS 한 스캔으로 내고 렌즈는 CTE 하나를 바꾼다 | Java 집계(옮기면 대조 테스트를 함께) | DEC:54-67; p/QL:120-124, 134; MeasureBundle.java:27 | 충돌 p/QL:5236("집계를 Java에서"). T1(항등식 테스트 동어반복) |
| QD-06 | CASH 분리는 FILTER 절 + MeasureBundle 두 슬롯. 비중 분모는 CASH 포함 총자산, 손익률 분모는 CASH 제외 매입금액이고 별도 타입으로 강제 | 그룹 자체 합계를 분모로 | p/QL:136-144, 185-205; PM:1041, 1649 | SG-17(필터 응답의 분모) |
| QD-07 | 예수금을 통화별 CASH 의사종목으로 position_line에 넣고 원가=평가로 저장, 응답에서는 원가·손익 null | 예수금 별도 테이블, 원가 null 저장(NULL 전파) | PM:926-932, 1356, 1586; PLB-d:199; p/QL:646-652; DR:132, 481 | SG-20/D-21, SG-29/D-27 |
| QD-08 | 원화 환산값을 라인에 머티리얼라이즈하고 fx_rate·fx_as_of를 함께 둔다. 결측은 그 날짜 이하 최근 환율로 폴백(`fx_as_of<as_of`가 증거), KR 영업일 5일 넘으면 FX_STALE | 집계 시점 환산, 별도 플래그 | PM:93, 934-940; PLB-d:186; FTR:300, 332; DR:190, 418 | D-11(코드는 달력 7일), D-09(앱이 안 그림) |
| QD-09 | 환율은 한 rate_type을 평가·원가·매도·현금흐름 네 곳에 쓴다 | 용도별 다른 rate_type | R0830:109, 427; DR:430, 821 | 데이터 Q3 확정 대기 |
| QD-10 | 분류 축(섹터 등)은 라인에 복사하지 않고 마스터 조인(분류 보정이 과거에도 소급) | 라인 복사(오분류 고착) | PM:67, 475-477 | — |
| QD-11 | 금액 반올림은 라인에서 한 번(원화 정수, 집계 후 재반올림 없음). 비율은 응답 직전 소수 1자리 HALF_UP, 분모 0이면 null | 집계 후 반올림 | PM:973; PLB-d:187; LT-d:119; p/QL:25-26 | N10(앱 반올림 부동소수 오차) |
| QD-12 | 금액은 BigDecimal(double 금지, ArchUnit). 알림 지표도 BigDecimal·DECIMAL64, 비교는 원값, 반올림은 표시 때만 | double/float | p/QL:27; p/RULES:27, 156-157 | T7(금액 정밀도 범주 없음) |
| QD-13 | 스냅샷은 KR 영업일(dim_market_calendar)마다만 만든다 | 캘린더일마다(주말 전부 이월) | PM:954, 1580; DR:188, 191 | — |
| QD-14 | 평가금액은 데이터팀 종가 평가 뷰(그 시장 마지막 거래일 종가)로 내고 price_as_of에 남긴다. 종가가 없으면 원천 평가금액 + price_as_of null. 과거 라인은 다시 계산하지 않는다 | 원천 잔고 평가금액(조회 시각 시세, 미국은 프리마켓) | PM:958; PLB-d:184-192; DR:462-470; p/PLM:5-7, 27; V20__position_line_price_as_of.sql:1-4; V21:3-5 | `fd9b6a5`. 변경: p/QL:696-704는 price_as_of를 저장하지 않았음. SG-43(미결) |
| QD-15 | as-of를 세 층(화면 / 계좌 source_as_of / 시장별 가격 기준일)으로 두고 가격 기준일을 라인에 저장 | 화면·뷰에서 재유도 | PM:1171-1189 | SG-43, PF5-07 |
| QD-16 | 카탈로그(축 8·지표 17·뷰 6)와 알림 카탈로그는 DB가 아니라 코드 상수로 두고 API로 내린다 | DB 테이블, 앱 하드코딩 | PM:979; p/QL:264; AL:206 | — |
| QD-17 | 뷰는 서버가 가진 사양 데이터. 범용 쿼리 엔드포인트를 두지 않고 카탈로그에 있는 조합만 받는다 | 임의 조합 쿼리 엔드포인트 | PM:527-537, 1085, 1749; p/QL:4298; RequestValidator.java:15; Catalog.java:16 | SG-25(화면에 없는 파라미터 무시) |
| QD-18 | 행 키와 합계 키의 이름을 분리(`total_assets_krw`/`securities_value_krw`, Metric.scope ROW/TOTAL/BOTH) | 같은 키로 의미 다르게 | PM:1039; p/QL:230-242 | — |
| QD-19 | 서버 정렬은 평가금액 내림차순 고정, 화면 정렬은 클라이언트 | 정렬 요청 파라미터 | PM:213, 1077 | — |
| QD-20 | 빈 상태는 봉투 empty_reason(200). notice message는 서버가 완성하고 클라이언트는 code로만 분기. 계좌 단위 상태는 notices가 아니라 계좌별 뷰 행 필드 | 빈 상태마다 notice 코드, 클라이언트 문구 조립, notices에 계좌 상태 | PM:1287, 1312, 1319, 1476; ALS-d:260 | SG-25(NO_HOLDINGS 등) |
| QD-21 | 커버리지 테이블(ca_coverage·etf_coverage)로 "없음"과 "미확보"를 가른다. ca_coverage 0행은 전량 미확보 | 행 부재로 판단, 경고 포기 | PM:794, 1720; M0809:111-113; DR:383, 395, 406 | — |
| QD-22 | 실현손익은 체결을 종목으로 접지 않고 2단 중첩(rows[].rows). MIXED는 저장하지 않고 응답 조립 때만 | 종목으로 접기("섞이면 낮은 쪽") | PM:304, 1396 | — |
| QD-23 | 일간 변화는 직전 as_of와 비교하되 직전 쪽도 오늘 유효 계좌만 넣고, 첫날은 0이 아니라 null | 0 표시 | PM:199, 1024 | N1: 오늘 새로 연동한 계좌가 전액 이익으로 잡힘 → B단계 고칠 것 |
| QD-24 | 계좌 편입·제외는 breakdown[]이 아니라 최상위 필드 두 개 | breakdown에 포함 | PM:1404 | D-01·D-02(S1, `1121942`), D-29, D-30, N2, N3 |
| QD-25 | LOOK_THROUGH 분기만 UNION ALL 세 갈래(그대로·구성종목·기타)로 바꾸고, 세 갈래 모두 scopedLine CTE에서 읽는다. 아래 조인·필터·GROUPING SETS는 그대로 | 갈래별로 position_line 직접 읽기 | LT-d:47; p/LT:7 | — |
| QD-26 | 기타 라인은 원래 ETF instrument_id에 묶고 is_residual로 표시, 축 SQL이 OTHER로 바꾼다 | instrument_id 비우기 | LT-d:80-93 | — |
| QD-27 | 분해 가능 여부와 비중을 한 SQL 조각(decomposableWeight)에서 정하고, 미분해 안내도 같은 조각의 반대 조건을 쓴다 | 기록 없음 | LT-d:53-68; p/LT:7 | — |
| QD-28 | 구성비중은 ETF별 max(as_of) 한 벌만. 최신이 비중 0뿐이어도 이전 파일로 물러나지 않는다 | 이전 파일 폴백 | LT-d:55 | — |
| QD-29 | 유효 비중 `w÷max(Σw,1)`: Σw≤1이면 나누지 않고 모자란 몫은 기타로 | 항상 Σw로 정규화(데이터 요구사항 §6.1) | LT-d:105-110, 311; R0830:86; DR:362 | 충돌 DR(AMB-14) |
| QD-30 | 안분은 라인(계좌×ETF)마다 floor 내림, 끝전은 기타(≥0), 0원 기타 행은 만들지 않고 기타는 늘 맨 끝 | 합친 뒤 내림 | LT-d:115-119; PM:490; p/LT:26-30, 210, 233 | 금액 HALF_UP 규칙(p/QL:25)과 다른 반올림 |
| QD-31 | 환산수량은 가격 기준일 종가로, 종가가 없으면 null(이전 날 대체 안 함). 예수금 환산수량도 null | 이전 날짜 종가 대체 | LT-d:139-153; PM:505 | SG-29/D-27(`2d2a2f4`·front-end `e1dfa6f`) |
| QD-32 | 현지 통화 병기는 "묶음이 단일 외화인가"를 조회 시점에 판정. 아니면 원화만 | 축별 병기 플래그, 축 이름 하드코딩 | PM:567-577, 1648; LT-d:123-137; p/QL:217-219, 272 | SG-23, D-14 |
| QD-33 | position_line PK `(as_of, account_id, instrument_id)`, 인덱스 `account(user_id)`·`position_line(account_id, as_of)` | 기록 없음 | p/QL:153-154; DEC:182-185 | — |
| QD-34 | 보관 기간 무제한(삭제 없음), 파티셔닝 안 함. 1,000만 행 또는 p95 200ms면 as_of RANGE 파티셔닝 검토 | 미리 파티셔닝 | p/QL:156-157; DEC:187-188 | 진단 "인덱스·파티셔닝은 기준만", 고도화 A |
| QD-35 | enum은 text + CHECK, 시각은 timestamptz, 거래일은 시장 현지 날짜 | PostgreSQL ENUM(값 추가·삭제가 번거로움) | p/QL:158; DEC:189; DR:85, 89-90 | V15에서 CHECK를 좁혀 KIS 전용화(SC-01) |
| QD-36 | 축 식의 `${}` 치환은 AxisKey enum 상수만 허용(SQL 주입 완화) | 기록 없음 | p/QL:115 | — |
| QD-37 | 응답 행은 Map으로 둬 "키 없음"과 "null"을 가른다. MyBatis 결과는 record 생성자에 이름 기반 매핑 | 컬럼 순서 기반 매핑 | RowDto.java:12; application.yaml:42-43 | — |
| QD-38 | 알림 봉투는 관계형 컬럼, trigger_spec은 JSONB. spec 안을 조회하는 파생 컬럼은 두지 않는다 | 정규화(EAV, 프리셋마다 테이블), 파생 컬럼 | AL:144, 190, 196 | — |
| QD-39 | JSONB는 MyBatis 타입 핸들러 없이 SQL CAST로. 저장하는 spec은 요청 원문이 아니라 해석한 모델을 다시 쓴 것 | 타입 핸들러, 원문 저장 | p/RULES:94, 7163, 9630-9639; DEC:126-135 | 되돌리는 조건: JSONB 컬럼이 셋을 넘을 때 |
| QD-40 | 평가 상태는 1:1 alert_state 테이블. 마지막 발화 시각은 저장하지 않고 alert_event에서 구한다. 수정 시 상태 행은 그 자리에서 초기화 | alert에 합침, 중복 저장, 삭제 후 재생성 | AL:146, 415, 453; p/RULES:7149 | — |
| QD-41 | alert_event 하나가 이력·앱 목록·배지·푸시 재시도의 원천. alert_delivery는 기기별 행, 기기 삭제 시 CASCADE | 별도 큐, 발화에 합침 | AL:615, 735; M0927:252; p/RT:217 | — |
| QD-42 | alert_delivery 상태에 SENDING(임대)과 sent_at을 더한다 | 스펙의 PENDING/SENT/FAILED만 | p/RT:189-197, 297 | 스펙 미반영(AL:729) |
| QD-43 | 소유 팀이 다른 테이블·instrument_id·collection_run_id에 FK를 걸지 않는다(배포 순서 결합 회피). 미매칭은 검증기가 잡는다 | 교차 소유 FK | AL:680; p/RULES:392; p/QL:163, 671; DEC:186; V1__initial_schema.sql:1-2; SYNC-d:101; DR:84, 858; R0830:364 | SG-26/D-25, SG-27/D-26(마스터에서 빠진 종목) |
| QD-44 | 소유권 축은 account.user_id와 alert.user_id 하나씩. 다른 테이블(라인 등)에 user_id를 복사하지 않는다 | 계좌 경유(알림), 라인에 소유 복사 | PM:595; AL:693; p/RULES:554; V1:30-31; V4:2-3; README.md:127-129 | 고도화 후보 "alert_event user_id 비정규화" |
| QD-45 | spec_hash = SHA-256 64자. 정규형은 평가 시점 + 조건 순서 그대로, 숫자 꼬리 0 제거, 파라미터 이름순, lag 포함 | 기록 없음 | p/RULES:1972, 2493-2530 | 스펙 미반영. 조건 순서가 다르면 중복으로 안 잡음 |
| QD-46 | spec_version은 서버 상수 1(요청에서 안 받음). 카탈로그는 append-only, 폐기는 deprecated, 업캐스팅은 뜻을 바꾸지 않는다 | 요청값, 삭제 | AL:198, 329-331, 1399; p/RULES:7681 | 미구현: 모델에 deprecated 없음·업캐스터 없음(진단 §7, p/RULES:8940, p/CLO:121) |
| QD-47 | 종목 검색 정렬은 `COLLATE "C"`, LIKE ESCAPE, 최대 30건. 종목코드 일부 일치도 셋째 단계에 건다 | DB 기본 정렬 | p/RULES:162, 8613, 9109 | SG-34. pg_trgm(DR:154 추천)은 안 씀 → 고도화 후보 |
| QD-48 | 기기 등록은 `ON CONFLICT (expo_push_token)` upsert로 지금 사용자에게 옮긴다 | 새 행 | p/RULES:9237; AL:1454 | — |
| QD-49 | 울린 알림 정렬은 `fired_at DESC, event_id DESC`, 커서 키도 같다. 커서 버전 표식 없음, 인덱스 추가 안 함. 커서는 base64url, limit 1~50 | as_of 내림차순(RT A.11), 커서 버전 | p/FIRED:5-7, 20, 128; p/RT:246-248; AL:827, 882 | SG-41(AL3-17): 울린 알림 목록·새로 울린·최근 울린 모두 이 순서로 결정 |
| QD-50 | alert_event.cadence는 NULL 허용, 읽을 때 `COALESCE(e.cadence, a.cadence)`(롤아웃 중 옛 파드 INSERT 보호) | NOT NULL | p/CLO:171, 245; V18 | O5: 발송 기한은 아직 a.cadence로 판정 → B단계 고칠 것 |
| QD-51 | held_since는 비어 있을 때만 쓰고 반영·수정·다시 켜기에서 비운다 | 기록 없음 | p/CLO:173-176; AL:705 | 진단 §7 held_since 표 모순 |
| QD-52 | 종목 공통 키는 instrument_id(uuid), symbol은 표시용, ISIN은 nullable | ISIN 통일 키(FTR), symbol 식별 | DR:83, 143; R0830:64; FTR:93; RS-ETF:281 | 변경: FTR은 ISIN 키 |
| QD-53 | data.instrument는 현재 버전만 보이는 11컬럼 뷰(SCD2 숨김). 상장폐지는 지우지 않고 delisted_on, ISIN 미매칭도 플레이스홀더 행 | 백엔드가 SCD2에 맞춤, 삭제·버전 종료 | R0830:58, 447; DR:152-156, 824, 855; PM:771 | R1017:115(delisted_on 전부 null), D-26 |
| QD-54 | 일봉은 거래정지일에 행을 만들지 않는다. 이력 300거래일, 수급 30거래일 | 직전 값 채우기 | DR:249-251, 278; M0927:58 | — |
| QD-55 | cln_balance 중복은 백엔드가 최신 source_as_of 1행을 고른다(DISTINCT ON) | 데이터팀 dedup | R0830:132; DR:460 | 보존 기간 Q11 미결 |
| QD-56 | "보유 라인" 판정을 SQL 조각 하나(SharedSql.HELD_LINE)와 latestAsOf로 상세·검색·알림이 공유 | 기록 없음 | p/IDB:7 | AMB-04 |
| QD-57 | 세션 생존 판정은 주입한 Clock 값을 인자로 넘긴다(쿼리 now() 안 씀). Clock 빈 하나(Asia/Seoul) | 시스템 시각 | p/AS:38, 57-59; p/RULES:89 | — |
| QD-58 | 계좌 기준일·이월 날짜는 DB 세션 시간대와 무관하게 KST로 자른다 | 기록 없음 | application.yaml:63; `b218613` | 진단 §5 앱은 기기 시간대(받아들임) |

## 4. 보안·인증 (SA)

| ID | 결정 | 버린 대안 | 근거 위치 | 결과 흔적 |
|---|---|---|---|---|
| SA-01 | 사용자는 축도 필터도 아닌 스코프. 인증 주체가 정하고 렌즈 전개 앞, CTE 안에 건다. 매퍼 첫 인자를 UserScope 타입으로 강제, NONE 없음, user_id는 경로·쿼리·바디에서 받지 않는다(ArchUnit) | 사용자 축·필터, `/users/{id}/…` 경로, 코드 리뷰에 맡김 | PM:585-599, 998, 1265, 1541, 1566-1567; p/QL:244-260; AL:790; p/RULES:25; UserScope.java:11-12 | 진단 잘된 점(권한·소유 검증) |
| SA-02 | 남의 계좌·동기화는 403(빈 결과는 존재 여부를 흘림, 400 검사 먼저). 알림·기기·발화·입출금은 "남의 것 = 없는 것" 404 | 빈 결과, 403 구분 | PM:601, 1637; p/QL:544, 4176; AL:977; p/RULES:26; ALA-d:158; MCF-d:75; SYNC-d:194; ForbiddenAccountException.java:6-7; AlertStore.java:13 | doc-map §4.3: 기능마다 응답이 갈림(cashflow 404 / sync 403 / account 403 / instrument 404) |
| SA-03 | 종목 상세는 403을 쓰지 않는다(마스터는 공용). 비UUID·없음·CASH는 404 | 403 | ID-d:56-62; PM:1437 | — |
| SA-04 | 토큰에 계좌 목록을 싣지 않고 매 요청 DB로 확인 | 토큰에 계좌(추가 즉시 낡음) | PM:1526; JwtCodec.java:19-22; DEC:74-75 | — |
| SA-05 | (초기) 서버가 세션을 들지 않는 무상태 JWT 12시간. 갱신 토큰·강제 로그아웃 없음 | 세션 쿠키, 소셜 로그인, 세션 저장소 | DEC:69-81; p/QL:691, 4096, 5237; p/FE1:164 | SA-06으로 바뀜(`47155af`~`811e664`). DEC·OPS-au:79·deployment.yaml:7에 옛 서술이 남음 |
| SA-06 | 서버 세션: 접근 JWT HS256 30분(sub·sid·gen) + auth_session 테이블, 요청마다 세션 PK 확인, 유휴 7일(마지막 갱신 기준, 시각은 계산)·절대 30일, 로그인마다 새 세션(다중 기기) | 로그인 후 12시간 고정 | AUTH-d:3, 28-32, 65, 87, 131, 138-150; PM:1511-1520; p/AS:5-12, 37; IA:58; V19:1-16; application.yaml:69-72; SessionService.java:95-110 | R2(앱이 로그인·만료 때 조회 캐시를 안 비움) → B단계 고칠 것 |
| SA-07 | 갱신 토큰은 32바이트 난수, 서버는 SHA-256 해시만 저장, 갱신마다 회전 | 느린 해시 | AUTH-d:91-92; PM:1517; RefreshTokens.java:9-30 | — |
| SA-08 | 재사용 감지: 직전 해시 + confirmed. 직전 토큰인데 새 세대가 미확인이면 응답 유실로 보고 재발급(REISSUE), 확인됐으면 REUSED로 세션 삭제. 훔친 쪽이 먼저 오는 창은 감수 | 옛 토큰이 오면 즉시 세션 종료 | AUTH-d:94-118; PM:1524; p/AS:61-67, 242; RefreshDecision.java:8-34 | `3fb27b3`. 진단 §7 PM §8.8 ↔ 세션 설계 §4.2 재사용 판정 범위 모순 |
| SA-09 | 끝난 세션은 행을 지운다(기록 안 남김). 유휴·절대 만료는 1시간 정리 작업이 지우고 기기·발송 행이 연쇄 삭제 | 기록 보존 | AUTH-d:68, 172; AuthSessionJobs.java:18-19 | `811e664`. O4(다섯 번째 작업) |
| SA-10 | 실패 사유를 응답으로 구분하지 않는다: 갱신 거절은 모두 401, 로그인은 이메일 없음·비밀번호 틀림 구분 없음 + 없는 이메일도 DUMMY_HASH로 한 번 비교(타이밍) | 사유별 응답, 즉시 실패 | AUTH-d:136; PM:1549; AuthController.java:28-33, 51-52, 57, 89 | R4(시도 횟수 제한 없음) → B단계 받아들임(내부망) |
| SA-11 | 로그아웃은 접근 토큰 없이 refresh_token으로, 모르는 토큰도 204 | 기록 없음 | AUTH-d:133; PM:1533-1539 | — |
| SA-12 | sid/gen 없는 토큰은 거절해 배포 즉시 옛 토큰을 무효화하고 기존 push_device를 전부 지운다 | 기록 없음 | AUTH-d:80, 87, 176 | O3 유형(호환 안 되는 배포) |
| SA-13 | 푸시 기기를 로그인 세션에 묶는다(push_device.session_id FK CASCADE). 끝난 세션의 기기에는 발송 행을 만들지도 보내지도 않는다(SESSION_ENDED) | 기록 없음 | AUTH-d:72-81, 160-168; PM:1522; AL:622-634; p/AS:11-12, 151; V19:23-29; RuntimeMapper.java:88-90; DeliveryMapper.java:46-47 | `b81157e`, `5f926b9`. 알림 계획(RULES·RT)엔 없던 것 |
| SA-14 | 비밀번호는 BCrypt(비용 10) 해시만. 계정은 SQL로 넣고 비밀번호는 프롬프트로 받는다. 회원가입·재설정 경로 없음 | 셀프서비스 가입, 명령줄 인자 | PM:832, 836, 1551, 1733; p/QL:690, 1486; DEC:76-77; OPS-au:3-4, 15-30 | R4(bcrypt CPU limit 없음) |
| SA-15 | CSRF 끔(쿠키 안 씀), 서블릿 세션 안 만듦. `/error` 디스패치는 permitAll(처리 안 된 예외가 401로 둔갑하면 앱이 로그아웃함) | 오류 디스패치 막기 | DEC:78; SecurityConfig.java:26-37; ALA-d:169 | `d6407ff` |
| SA-16 | JWT_SECRET은 32바이트 미만이면 기동 거부, 운영은 환경변수로만 | 저장소 기본값 | README.md:266-267; application.yaml:67-68 | — |
| SA-17 | CORS는 설정한 출처만, 경로·메서드 목록 방식, 허용 헤더 둘(Authorization, Content-Type), 자격 증명 불허, CORS 필터를 인증 필터 앞에 | MVC 레벨 CORS(시큐리티 체인 뒤라 preflight가 막힘) | DEC:83-108; p/RULES:9604-9610; WebOriginCorsConfig.java:46-59, 82; SecurityConfig.java:31-33 | `abdb811` → `1aa767d` → `211b318`(운영에 localhost:8081 개방). DEC:90 목록 낡음 |
| SA-18 | 계좌 자격증명은 SSM SecureString `/stock-project/accounts/<account_ref>`에 두고 테이블엔 credential_ref만. 파라미터 이름에 사용자를 넣지 않는다 | 데이터 잡이 백엔드 테이블 직접 읽기, 이름에 사용자 포함 | M0809:217-223; R1015:169; DR:619; ALA-d:339, 528; p/ALA:5, 25; OPS-ac:3-4; SsmCredentialStore.java:23 | `a0a1881`. 충돌 PM:1106("키 이름에 사용자") |
| SA-19 | 백엔드 IAM은 수집용 값에 Put/Delete만(읽기 없음, 리소스 accounts/*). 계좌번호는 백엔드만 읽는 별도 계좌 정보 값(`/account-numbers/<ref>`)에 둔다 | 계좌번호 재입력 | PM:1108; ALA-d:330-333, 355, 387, 429; OPS-ac:19-21; p/CRB:7, 20 | 계좌 정보 값은 feat/credential-refresh에서 작업 중 |
| SA-20 | AWS 자격증명은 환경변수(EnvironmentVariableCredentialsProvider)로만 | 기본 체인(노드 인스턴스 역할을 집음) | ALA-d:385; SsmCredentialStore.java:25 | — |
| SA-21 | account_ref = `ar_` + HMAC-SHA256(소금, 기관코드 0243:계좌번호 10자리) 앞 128비트. 계좌번호를 안 뒤 발급, 사용자 정보 없음, 재연동해도 같은 값 | 소금 없는 해시(계좌번호 공간이 좁아 역산), account_id 그대로 | PM:1110-1112; ALA-d:328-338; R0830:192-194; DR:658; p/ALA:25, 2735; AccountRefIssuer.java:12-42 | `d5e376b` |
| SA-22 | 소금과 기관코드는 바꾸지 않는다. 소금은 환경변수(Secret)로 주고 SSM에 백업(백엔드 권한 없음), 비었거나 32바이트 미만이면 기동 실패 | 기본값 | ALA-d:335, 395-401; AccountRefProperties.java:8; AccountLinkConfig.java:23; OPS-ac:12-13 | — |
| SA-23 | 값 누출 차단: toString을 가리고, Bean Validation을 쓰지 않고, 예외 메시지·ref·파라미터 이름·토큰을 로그와 응답에 내지 않으며 SDK 예외는 cause로 붙이지 않는다 | record 기본 toString | ALA-d:405-414; PLB-d:69; p/ALA:26; p/MS:23; p/AS:45; AL:666; KisAccountNumber.java:9; RefreshRequest.java:8; CredentialStoreUnavailable.java:6 | `70a426d`, `0da33b7` |
| SA-24 | account_ref·credential_ref·계좌번호 원문은 어떤 응답에도 싣지 않는다(가린 번호만). failure_reason은 코드 모양일 때만, 아니면 UNKNOWN | 자유 문자열 그대로 | ALA-d:130, 411; PLB-d:337 | — |
| SA-25 | 실제 KIS 키는 LAN·port-forward localhost에서만 입력(평문 HTTP). TLS는 범위 밖, 앱은 경고 표시 | 공인 IP 경로 | ALA-d:418-423; ALS-d:366; OPS-ac:9-11; p/ALA:2733 | R4 판단 근거(같은 네트워크만) |
| SA-26 | 데이터팀 DB 역할을 dataeng_reader·dataeng_writer 둘로 가른다 | 하나로 합치기(쓰기 키가 새면 따로 교체 불가) | DEP:295-297; db-roles-job.yaml:1-2 | `74121ea`(읽기만) → `812fbc9`(쓰기 추가) |
| SA-27 | app 스키마 권한은 "회수 목록" 방식: 동기화마다 INSERT·UPDATE·DELETE와 기본 권한을 회수하고 app_user·push_device는 읽기까지 회수. 새 표가 기본 권한으로 자동으로 열리는 것은 감수 | 부여만 하기(따로 준 쓰기가 남음) | db-roles-job.yaml:63-87; DEP:341-356; p/RULES:568-575 | R1(S급): writer가 app 전체 DML → auth_session 위조 가능 → `70d79cc`로 app 읽기 전용. auth_session SELECT는 여전히 열림(doc-map §5). R3(reader 전체 SELECT) → B단계 받아들임 |
| SA-28 | 데이터팀에 넘기는 alert_watchlist와 데이터 산출물에 사용자 정보를 넣지 않는다 | 소유를 경계 너머로 넘김 | AL:1596; p/RULES:460; DR:60, 630-646; PM:1718, 1725 | R0830:224 문구 좁힘 |
| SA-29 | (앱) 앱키·시크릿·계좌번호는 폼 useState에만 둔다(컨텍스트·네비 파라미터·kvStore·쿼리 키·mutation 변수·console 금지). 등록·갱신은 useMutation 없이 직접 호출, 실패 시 시크릿만 비움 | useMutation(캐시가 인자를 보관) | ALS-d:344-347; p/ALS:7, 24; p/CRA:22, 170; front-end .superpowers SDD:11; fe:screens/accountLink/AccountLinkFormScreen.tsx:47-49 | — |
| SA-30 | (앱) 시크릿만 가리고 앱키는 보인다. 자동완성·학습 끔, 붙여넣기 허용, 화면 캡처 방지는 하지 않는다 | expo-screen-capture | ALS-d:358-361, 371 | — |
| SA-31 | (앱) 세션(접근·만료·갱신)을 보안 저장소 한 키 JSON으로, 비밀번호 저장 안 함. 새 쌍은 저장소에 먼저 쓰고 메모리에(쓰기 실패여도 계속) | 키별 저장(섞이면 재사용 판정) | AUTH-d:192, 201; fe:auth/tokenStore.ts:4-9; fe:api/client.ts:90-93 | — |
| SA-32 | (앱) 닿지 못한 로그아웃의 갱신 토큰은 메모리 대기 목록에만 두고 로그인 화면일 때만 재전송 | 저장소 보관 | AUTH-d:238-251; p/LO:12, 43; fe:push/device.ts:42-48 | — |
| SA-33 | (앱) 로그아웃하면 이메일 칸을 비우고 마지막 이메일을 지운다(공용 기기). 세션 만료 때는 채운다 | 기록 없음 | IA:116; p/LO:45; fe:auth/tokenStore.ts:63 | R2: 공용 기기 원칙이 조회 캐시까지 이어지지 않음 |
| SA-34 | 키는 환경변수로, 사용자가 자기 키를 직접 입력한다(코드·로그·저장소에 두지 않음) | 노출 | FTR:309; RS-BRK:93; V-KPA:5 | — |

## 5. 운영·배포 (OD)

| ID | 결정 | 버린 대안 | 근거 위치 | 결과 흔적 |
|---|---|---|---|---|
| OD-01 | main 푸시 = 운영 배포. 테스트 → 빌드 → ECR → CI가 태그 갱신 커밋 → ArgoCD. paths-ignore로 자기 호출을 막는다 | 사람이 태그 갱신 | DEP:235-257; .github/workflows/build-and-push.yml:1-14, 91-99; p/PLM:23, 206 | `f3f5a94`, `b7e628f`. README:228-230 낡음. O3(옛 파드와 새 스키마 공존을 막는 장치 없음) → 고도화 F |
| OD-02 | CI는 OIDC로 main 전용 역할을 맡는다. 저장소에 AWS 키를 두지 않는다 | 저장된 자격증명 | DEP:241-246, 256-257; build-and-push.yml:4-6 | `b7e628f` |
| OD-03 | CI 테스트는 실제 Postgres 서비스 컨테이너로 돌리고 통과한 것만 이미지로. 실제 AWS를 부르는 테스트는 두지 않는다 | 기록 없음 | DEP:248-249; build-and-push.yml:32; ALA-d:465; PLB-d:354 | T7(외부 API 타임아웃 범주 없음) |
| OD-04 | 이미지 태그는 짧은 커밋 해시, ECR IMMUTABLE, 있는 태그면 빌드 건너뜀, 태그 없는 이미지는 7일 뒤 삭제 | latest | DEP:152-165; build-and-push.yml:59, 69-70 | `b7e628f` |
| OD-05 | ECR 이미지는 노드 인스턴스 역할 + kubelet 자격증명 공급자로 당긴다 | imagePullSecrets에 토큰 복사(12시간 만료) | DEP:176-189 | `773c49c` |
| OD-06 | 매니페스트는 앱 저장소 k8s/에. ArgoCD Application은 저장소 루트, 동기화 경로는 k8s/만, prune·selfHeal 켬 | 별도 매니페스트 저장소, 루트 전체 동기화(자기 삭제 위험), kubectl apply | DEP:128-141, 215-233; argocd-app-portfolio.yaml:14-26 | `e258f39`, `7a3fe08` |
| OD-07 | 네임스페이스는 portfolio | default | DEP:143-150 | — |
| OD-08 | 이미지: 컨테이너 안에서 빌드하고 의존성을 별도 레이어로, 빌드 단계는 빌드 기계 아키텍처·실행 단계만 amd64, alpine JRE, 비-root(uid 100), MaxRAMPercentage 75, .dockerignore | 로컬 jar 복사·BuildKit 캐시·계층형 jar, 전체 amd64 에뮬레이션, glibc·JDK, 기본 25% 힙 | DEP:68-126; Dockerfile:2-27 | `52fd305`, `a7d1a04`, `967056e`. 메모리 512Mi/768Mi는 잠정(DEP:380) |
| OD-09 | DB는 클러스터 안 StatefulSet(복제 1, Retain 볼륨, PGDATA 하위 디렉터리), /dev/shm 256Mi | Airflow Postgres 공유, RDS(권한·비용), Deployment, 기본 64MB shm | DEP:191-213; k8s/postgres.yaml:1-81 | `8d4e8e9`, `ed96e76`. 백업 없음 미결(DEP:376), T7(백업·복구 범주 없음) |
| OD-10 | actuator는 health만, show-details never. readiness(DB 포함)·liveness(DB 제외), 관리 포트는 8080 공용 | env·beans 노출, 별도 관리 포트 | DEP:7-38; application.yaml:47-61 | `dca164c` 제거 → `f1fac19` 재도입 |
| OD-11 | 메트릭 수집 없음. 알림 평가 한 주기 소요를 로그 한 줄(elapsed_ms·alerts·points·pod)로 남기고 30초 넘으면 WARN | Prometheus 지표 경로(수집처 없음, 인증 없는 경로 증가) | DEP:37-38; AL:594-600; p/CLO:41, 225-227; TickReport.java:5; `600c70b` | O2 → 고도화 E. T7(관측 범주 없음) |
| OD-12 | initContainer에서 pg_isready로 DB를 기다린다. liveness는 initialDelay 30초, 3회 실패 시 재시작 | 기록 없음 | DEP:40-52; deployment.yaml:22-24, 113-128 | `21957e6` |
| OD-13 | graceful shutdown 20초 + 스케줄러 종료 20초, terminationGracePeriod 30초 | 기본 즉시 종료 | DEP:54-66; application.yaml:20-36, 46; deployment.yaml:18-20 | O4(합 40초 > 30초). 근거 "조회 API라 짧다"(DEP:59)가 낡음 |
| OD-14 | CPU limit을 두지 않는다(기동이 길어지고 지연이 튐) | CPU limit | deployment.yaml:135-136 | R4(bcrypt CPU 제한 없음) |
| OD-15 | 복제본 2개, 롤링 배포는 기본값, 롤링 중 엣지 손실 감수 | 기록 없음 | deployment.yaml:7-9; DEC:150-151 | O3 |
| OD-16 | Flyway는 앱 기동 시 실행(복제본 동시 기동 확인) | 별도 Job(미결) | DEP:379 | O3 |
| OD-17 | Secret은 kubectl로 직접 만들고 매니페스트는 이름만 참조. Expo 토큰도 수동 Secret | SealedSecrets, External Secrets(클러스터에 없음), Secret 관리 도구(미룸) | DEP:378; M0927:188-206 | README:237의 키 목록 낡음 |
| OD-18 | 운영에는 프로파일을 주지 않는다(local이 미러와 CORS를 켬) | 기록 없음 | deployment.yaml:37-38 | — |
| OD-19 | 기능 스위치(SNAPSHOT·BASIS·EXPO_PUSH)는 기본 꺼짐. 운영 DB 권한 확인 질의(has_table_privilege)를 통과한 뒤 켜고, 권한이 없으면 켜지 않는다 | 기록 없음 | application.yaml:84-100; PLB-d:57, 347-350; PB-d:388-389; p/PLB:3609-3622; p/RT:89, 289; p/PLM:206; README.md:150-186 | `f8a2936`(스냅샷), `b28a659`(평단), `211b318`(푸시) |
| OD-20 | 수집 픽업 cron은 매니페스트 env(Airflow와 맞춤, 재빌드 불필요). 동기화 시한 PT96H는 백엔드가 둔다(PICKUP_TIMEOUT, 생성기가 꺼져도 읽는 쪽이 같은 코드로 적용) | 데이터 쪽 만료에 의존 | SYNC-d:37, 56, 61, 249-257, 280-283; p/MS:7, 156-167; application.yaml:108-112; deployment.yaml:90-93 | `de1ccbc`. SG-40. 가동 시간은 매주 바뀜(doc-map §4.6) |
| OD-21 | 외부 노출은 ClusterIP + port-forward만, 클러스터 API는 SSM 포트포워딩으로만. TLS·도메인은 미결 | 인터넷 노출 | service.yaml:7; DEP:381; p/ENV:171 | R4 |
| OD-22 | 알림 평가기·발송기·영수증 확인기는 portfolio-api 안의 스케줄 작업. 평가 한 번이 주기 절반(30초)을 넘거나 API가 느려지면 같은 이미지를 ALERT_RUNTIME_ENABLED로 워커로 나눈다 | 지금 별도 앱·Deployment | AL:556, 592; p/RT:84, 6375-6377; DEC:153-155; application.yaml:76-78; M1005:72 | 변경: FTR:311, 351은 평가기 liveness를 데이터팀 운영으로 둠 |
| OD-23 | 발송 규칙: 기한 장중 30분·종가 12시간(지나면 EXPIRED), 재시도 30초부터 두 배·5번째에서 끝, 429·5xx·연결 실패만 재시도, 요청 실패·MessageRateExceeded면 이어 보내기 멈춤, 영수증은 15분 뒤 묻고 24시간에 비움, last_error는 짧은 코드, HTTP 연결 5초·읽기 15초 | 기록 없음 | p/RT:187-233, 298; AL:637; DEC:165-172; DeliveryMapper.java:20-41; DeliveryDispatcher.java:63 | O5(기한을 알림 cadence로 판정). SG-25(오래 대기한 행 끝냄). 스펙 미반영(진단 §7) |
| OD-24 | 푸시는 EXPO_PUSH_ENABLED로 켠다(기본 false, 꺼져도 발화·배지는 남음). 운영에서 켜는 일은 사람이 | 기록 없음 | p/RT:89, 289; application.yaml:84-86; deployment.yaml:59-63 | `211b318` |
| OD-25 | alert_delivery는 지우지 않고 쌓는다. 1,000만 행을 넘으면 보관 기간을 정한다 | 기록 없음 | p/RT:6394-6398; DEC:173, 176 | — |
| OD-26 | 배포 순서를 정한다: 인증은 백엔드 먼저·앱 직후(롤링 중 몇 분 불일치 감수), 종목 상세도 백엔드 먼저, 계좌 등록은 IAM → 소금 → Secret → 이미지 → 백필 dry-run → apply, 인증 정보 갱신은 IAM → 배포 → 스크립트(따로 승인) | 앱 먼저 | AUTH-d:181-186; ID-d:271; p/IDB:23; p/IDA:17; ALA-d:437, 453; p/ALA:2739-2767; p/CRB:25 | O3 |
| OD-27 | 계좌 정보 값 백필 스크립트는 dry-run 기본, 값을 인자·로그에 넣지 않고 운영자 자격 증명으로. 가린 계좌번호는 기동 때와 1시간마다 채운다 | 사람이 운영 DB를 수기로 | ALA-d:443-451 | 브랜치 작업 중 |
| OD-28 | 자격증명 저장소(ssm/memory)는 기본값이 없어 빠지면 기동 실패. 로컬·테스트는 InMemory. 저장소는 계좌 연동 패키지만 쓴다(ArchUnit) | 기본값 | ALA-d:362; p/ALA:7, 758; application.yaml:104-106; ArchitectureRulesTest.java:71 | `f475484` |
| OD-29 | SSM은 SecureString·Overwrite, 연결 3초·호출 10초, SDK 예외는 503 | 기록 없음 | ALA-d:366-386; SsmCredentialStore.java:35 | O7(잠금 보유 시간을 정함) |
| OD-30 | 마이그레이션 번호는 db/migration·db/external을 통틀어 한 순열. 적용된 파일은 고치지 않고, 첫 운영 배포 전까지만 고치고 재생성 | 폴더별 번호대 예약, 번호 계속 더하기 | p/QL:160-161; p/PLB:24; README.md:206-221; V1:4-5 | `96b5907`, `daf5d08`. V19는 배포 전 수정(`47155af` → `70a426d`) |
| OD-31 | 테스트 DB: 처음엔 같은 인스턴스의 portfolio_test + TRUNCATE, 이후 마이그레이션 브랜치는 전용 테스트 DB. DB 테스트·생성은 사용자 승인 뒤 | Java에서 Docker API 호출(Testcontainers류), 공유 portfolio_test | p/QL:159; DEC:190; README.md:106-110; p/PLM:17-20; p/AS:41-44; p/PB:22 | `af39578`. p/MS:16·p/MCF:26은 공유 DB |
| OD-32 | 알림 계획은 새 라이브러리를 들이지 않는다 | 기록 없음 | p/RULES:23; p/RT:23 | — |
| OD-33 | 통합테스트(분기 전수·시드)와 운영테스트(실데이터·사람 관찰)를 나누고 데이터 품질 검사를 따로 매일 돈다 | 둘을 대체 관계로 | p/TEST:14-27 | T5: 운영테스트·품질 검사 산출물 없음 |
| OD-34 | 가동과 관찰을 나눈다(평가기 10/19 가동, 3주차 집중 관찰). 데이터 연계가 막혀도 가동일을 미루지 않고, 10/21까지 안 쌓이면 시드로 덮고 범위 제외로 기록 | 일정 연기 | p/TEST:33-45, 155; R1015:26; R1017:6 | — |
| OD-35 | 운영테스트 계좌는 KIS 모의계좌(범위 축소로 기록) | 실계좌 | p/TEST:132 | DT-02(모의 서버 외화 예수금 0, dataeng #60) |
| OD-36 | 클러스터 DB를 같이 쓰는 조건: 테스트 계정 분리, 주입·골든 비교는 로컬만, 주입은 환경 플래그 뒤·되돌릴 수 없는 주입 금지, 클러스터 DB에는 읽기 전용 세션(권한이 아니라 규칙으로) | 클러스터 주입 | p/TEST:103-107, 244; p/ENV:173-175, 204-208 | — |
| OD-37 | 실기기 푸시가 막히면 alert_delivery 적재까지로 판정하고 수신은 범위 제외 | 기록 없음 | p/TEST:171 | — |
| OD-38 | 관측은 대시보드 없이 조회 수단 하나 | 대시보드 | p/TEST:177, 185 | O2 |
| OD-39 | 프론트엔드 CI 게이트를 새로 두고 백엔드 CI는 그대로 | 기록 없음 | p/TEST:189-190 | T5: 앱 CI 없음 |
| OD-40 | 클러스터 DB에 쓰기 전에 pg_dump CronJob을 두고 복구를 한 번 해 본다 | 기록 없음 | p/TEST:195-198 | 실행 흔적 없음(OD-09 백업 미결) |
| OD-41 | 결함 관리 규칙: D-(우리 코드)·DT-(데이터)·SG-(스펙 공백)·RQ-(데이터팀 요청)를 나눔, 등급 S1~S4(S1 즉시·S2 동결 전·S3 시간 나면·S4 기록만), 근거 절 없으면 SG로 분리하고 고치기 전 보고, S1·S2는 자동 테스트를 남김, 10/28 동결 후 S1만, "닫힘" = 그 케이스가 main에서 통과(배포 무관) | 한 목록 | p/TEST:291-336 | T4(결함 등급이 케이스보다 일관되게 낮음), T9(SG가 결함 목록에 섞임) |
| OD-42 | 종료 조건(1등급 100%·S1 0·2등급 90%·영업일 10일·오발화 0 등)이 미달이면 미달로 기록. 테스트는 스펙을 고치지 않고, 등급·종료 판정은 사람이 한다 | 억지로 채우기, 에이전트에 맡기기 | p/TEST:8, 340-372, 409 | T5: 종료 판정 기록 없음. T3 |
| OD-43 | 운영 일지는 한 파일에 날짜순, "느낌" 줄 필수 | 기록 없음 | p/TEST:272, 285 | T5(산출물 없음) |
| OD-44 | 두 머신은 같은 도구 버전·절차, 머신별 값은 커밋하지 않음. JDK 21은 Homebrew + JAVA_HOME, psql은 compose 컨테이너 것, 로컬 DB는 다시 만들 수 있는 샘플만, 사내 CA는 JDK cacerts와 AWS ca_bundle에만, 빈 캐시 첫 Jest는 직렬 | 시스템 JDK 링크, psql 설치, 셸 프로필 수정, 병렬 | p/ENV:5, 43, 50, 64, 73, 99, 117, 165 | — |
| OD-45 | KIS appkey: 개발은 모의, 실전은 위탁(01) 전용 appkey, IRP는 조회용 | IRP appkey(실시간 3종목 캡·체결 내역 차단) | V-RT:315-316; FTR:219 | — |
| OD-46 | 실시간 30~50종목은 다중 appkey 세션 샤딩 | 단일 세션 | V-RT:125, 312 | AMB-17 |
| OD-47 | 평가기 liveness 헬스체크·알람을 둔다 | 기록 없음 | FTR:39, 311 | O2(관측 없음) |

## 6. 데이터팀 연동 (DI)

| ID | 결정 | 버린 대안 | 근거 위치 | 결과 흔적 |
|---|---|---|---|---|
| DI-01 | 팀 경계 = "기관 고유성이 사라지는 지점". 정규화까지 데이터, 도메인 규칙은 백엔드 | 기록 없음 | M0809:322; DR:58; M0927:258; PM:751, 1688-1700 | — |
| DI-02 | 연동은 같은 Postgres의 `data` 스키마 하나. 백엔드는 레이크·ClickHouse를 읽지 않는다. 경로 세 갈래: 직접 적재(장중·완료 신호·collection_run) / 리버스 ETL / 레이크 전용 | Kafka `signals` 토픽 + Gold 서빙 테이블(SIG), 레이크·ClickHouse 직접 읽기 | SIG:73, 97; DR:66-72; M1005:57; DEP:272-274, 367 | 변경(SIG → DR). R1015·R1017: 계약은 맞았는데 파이프라인이 끝까지 돈 적 없음 |
| DI-03 | data는 백엔드 읽기 전용, 예외는 collection_run 하나 | 별도 queue 스키마 | DR:76; R0830:160-162 | — |
| DI-04 | 스키마를 소유별로 app·data로 가르고 `currentSchema=app,data`로 해석, SQL에 스키마를 붙이지 않음, `spring.flyway.schemas: app` 명시 | 한 스키마에 섞기, 테이블마다 접두, public 유지 | DEP:259-291; application.yaml:5-14; p/QL:28, 162; PLB-d:85; R0830:350 | `348964f`, `92491a4`, `32a9666` |
| DI-05 | 데이터팀 표는 db/external 미러(local·test만, dataeng DDL을 따름)로만 두고 운영에 적용하지 않는다. V1에서 만들지 않는다 | 백엔드 마이그레이션으로 생성, 운영에도 미러 적용 | p/QL:29; p/RULES:31; PLB-d:87-89; PB-d:62-64; LT-d:265; ECF-d:151; README.md:193-204; V1:1-2 | — |
| DI-06 | DB 역할은 마이그레이션이 아니라 ArgoCD PostSync 훅 Job이 만든다(BeforeHookCreation, 멱등 SQL). SQL은 일반 리소스 ConfigMap 파일로 마운트, restartPolicy Never, app 스키마가 없으면 권한 부분 건너뜀, search_path는 `data, app` | 마이그레이션(비밀번호가 Git에), 일반 Job(수정 불가), command 안 SQL(`$$` 축약), OnFailure(파드 삭제) | DEP:299-322; k8s/db-roles-job.yaml:4-6, 52-66, 91-110 | `77637d4`, `8e13c05` |
| DI-07 | writer 권한은 data에 SELECT·INSERT·UPDATE·DELETE와 CREATE | ALL(TRUNCATE는 배타 락, REFERENCES·TRIGGER 쓸 곳 없음) | db-roles-job.yaml:43-50; DEP:337-339 | — |
| DI-08 | 백엔드 표는 CDC로 읽게 한다(account_ref 포함, 자격증명·PII 제외, 1.5단계 이후 붙임, 복제용은 별도 역할). cdc_app_user는 빼거나 축소 | app_user 전체 CDC | DR:650-656, 849; R0830:192, 222, 356; DEP:358-360 | AMB-11(M1005:184 배치 제안과 충돌). wal_level 미결 |
| DI-09 | 사용자 축을 가진 레이크 마트는 앱으로 내보내지 않는다 | 기록 없음 | DR:79; R0830:221 | — |
| DI-10 | 원천 선택·수집 방법·레이크 내부 모델은 데이터 담당이 정한다. 스펙과 데이터 요구사항이 다르면 스펙이 맞고, 두 기능을 합쳐야 정해지는 것은 데이터 요구사항이 정한다 | 기록 없음 | DR:10-12, 48-49 | — |
| DI-11 | 수집 요청·완료를 큐 없이 collection_run 테이블 하나로 주고받는다. 컬럼별로 쓰는 쪽을 나누고(생성 컬럼은 만든 쪽, 상태는 데이터) silver_synced_at을 받아들인다 | 큐 인프라, queue 스키마 | M0809:201-205; R0830:160-164; DR:616; PM:1218, 1242; M1005:145 | R1015:134 DDL 일치. 진단 §10 계약에 없던 암묵 의존(finished_at, credential_ref 시한, DONE 비율) |
| DI-12 | 스냅샷 날짜는 실행 시각이 아니라 collection_run.as_of | 실행 시각 | DR:600; PM:1241 | — |
| DI-13 | 재시도는 데이터가 아니라 백엔드가 새 행으로. EOD는 KR 영업일 캘린더 기준. 픽업은 credential_ref가 채워진 REQUESTED만 | cron 요일 고정, 전부 픽업 후 FAILED | R1015:144, 161-170; M1005:136 | — |
| DI-14 | credential_ref "단기 참조"를 SSM 파라미터 이름 복사로 구현. 백엔드가 쓰는 collection_run 컬럼은 이것 하나(CredentialFiller), 값은 다루지 않는다 | 단기 자격증명 참조 | PLB-d:310-324, 415; ALA-d:530; CollectionRunMapper.java:14; README.md:153-157 | 충돌 PM:1106·1716("픽업으로만"). 워커 IAM 와일드카드라 관례로만 지켜짐 |
| DI-15 | 등록·갱신 때 KIS로 키를 검증하지 않는다(다음 수집에서 드러남). 등록은 collection_run을 만들지 않고 첫 수집은 다음 EOD | 등록 시 검증, USER 행 동시 삽입(토큰 1분 제한·중복 수집) | PM:1146; ALA-d:30-31, 52-56, 72-81; p/CRB:20; AccountController.java:39 | SG-39 |
| DI-16 | 수집의 REAUTH_REQUIRED는 FAILED처럼 건너뛰고 연동 상태를 바꾸지 않는다. 미러는 데이터 계약이라 남기고 RUNNING으로 두어 시한에 닫는다 | 기록 없음 | PM:1239; PLB-d:149, 335; p/KIS:23, 26; V15 | SG-36 |
| DI-17 | 인증 실패 판별은 데이터의 SOURCE_CREDENTIAL_INVALID 코드에 의존하고 목록 한 곳(CredentialFailureReasons)에 모은다 | 기록 없음 | PM:1156, 1763; ALA-d:222 | SG-39 ②(데이터팀 답 대기) |
| DI-18 | linked_at 이후 요청된 실행만 현재 자격증명의 결과로 본다(account_ref는 재연동해도 같으므로) | 기록 없음 | PM:1137; ALA-d:126; V9__account_linked_at.sql:1-2; SyncMapper.java:29 | O6 → B단계 받아들임 |
| DI-19 | KIS 실전·모의(env)를 필수로 받아 자격증명 JSON과 account.kis_env에 둔다 | 기록 없음 | V11__account_kis_env.sql:1-2; `1e5ec53` | DT-02 |
| DI-20 | 지표는 백엔드가 계산하고 데이터는 일봉 원재료와 수정주가 보정만 준다 | 미리 계산한 지표 마트(데이터팀 Spark) | DR:62, 252; M1005:42-48; AL:1496-1498; FTR:348 | 변경(FTR → DR) |
| DI-21 | 도착은 완료 신호 market_data_run(시장·종류·시점마다 한 행)으로 안다. collection_run과 신호를 나눈다. DONE은 data 반영까지 끝난 뒤에만, DONE 행은 바꾸지 않는다 | 하나로 묶은 신호(가장 늦는 데이터가 전부 붙잡음), 행 존재로 추측, 레이크 적재·비율 기준 DONE | AL:493, 506, 1566-1568; M0927:136-138; DR:329-332, 684-699 | R1017:95 실측: 구현은 95%/50% 비율 기준 DONE |
| DI-22 | 일별 신호는 최근 창의 마감된 모든 거래일에 쓰게 요청 | 실행 시점 최근 거래일 하나만 | R1017:74 | 요청 단계 |
| DI-23 | 다음 거래일이 DONE이면 오지 않은 D는 데이터 없이 평가(DATA_MISSING) | 무한 대기 | AL:509; DR:317; p/RT:101 | — |
| DI-24 | 캘린더에 개장·마감 시각을 넣고 시각 판정은 모두 캘린더에서(종가 시점은 close_at만). 캘린더는 포트폴리오·알림 공용 | 고정 시각(09:00~15:30), 팀별 계산 | M0927:156-158; DR:184, 680-682; AL:511 | 알림은 캘린더가 없으면 평일 어림(AMB-03), D-16 |
| DI-25 | 장중 스냅샷은 레이크를 거치지 않고 data에 직접, alert_watchlist(intraday) 종목만 5분 이하 간격. watchlist는 종목·시장·장중 여부만, 데이터는 매 벌 시작 때 읽는다 | 레이크 → 리버스 ETL, 전 종목 수집(호출 한도) | AL:756, 771, 1548; M0927:110; DR:303-304, 630-646 | — |
| DI-26 | snapshot_at은 수집 시각이 아니라 시세 기준 시각(원천 시각이 다르면 가장 이른 시각). 장중 가격은 원시 가격, 당일분만 보관 | 수집 시각 | AL:1554; DR:297-305, 766 | R1017:116(US 15분 일괄 보정) |
| DI-27 | 수급은 장 마감 후 확정치만 | 장중 잠정치 | AL:1533; M0927:84; DR:277 | — |
| DI-28 | 수정주가: 포트폴리오에는 corporate_action 원본, 알림에는 보정 계열(분할·병합·무상증자만, 배당 보정 없음) | 배당 보정 | DR:217-221, 701-716, 771 | AMB-13(R1017:106 KIS 수정주가 제안). 데이터 요구사항 N7 미결 |
| DI-29 | ETF 중첩 평탄화·매칭은 데이터, 백엔드는 한 겹 곱셈만. 비중 합은 원본 그대로 두고 정규화는 백엔드. 깊이 초과·순환은 UNAVAILABLE | 백엔드 재귀, 데이터팀 정규화, 부분 전개 | M0809:135; DR:360-362, 383; R0830:86, 453; PM:494, 1700; LT-d:78 | — |
| DI-30 | 1차 ETF 분해는 미국 ETF만, 국내는 미분해 표시 | 헤드리스 수집, 운용사 파일 파싱, 유료 벤더 | M0809:239-252; R0830:90 | AMB-12(실측 레이크는 국내만, R1015:119) |
| DI-31 | 현금흐름에서 매매대금·내부 이동·환전·매매 수수료 배제, 재귀 깊이·순환 차단은 데이터 계약 | 백엔드 배제 | M0809:49-51; DR:542-550; PM:809-816, 1654, 1721 | 배제 방법 Q9 미결 |
| DI-32 | trade_id는 원천 ID 우선, 없으면 `{account_ref}:{주문일}:{주문번호}` 합성 규칙 고정 | (계좌·종목·일시·수량·가격) 해시, 백엔드 자체 키 | M0809:151-155; DR:506; R0830:228 | — |
| DI-33 | cln_trade 그레인은 주문 단위(분할체결 합산), 실현손익 행은 매도 주문 1건 | 체결 단위 | R0830:236, 391; DR:497, 502 | — |
| DI-34 | cln_* 컬럼은 최소 필드로 정하고 추가는 마이그레이션 | 넉넉하게 잡기, 확정 미루기 | M0809:178-180 | — |
| DI-35 | cln_cashflow 본체는 DIVIDEND·FEE·TAX만, 커버리지는 5유형. 키는 (account_ref, tr_key), 조회 창 단위 커버리지는 백엔드가 접는다 | 본체에 입출금 포함, cashflow_id 단일 | R0830:459; DR:536, 835; R1015:102, 111; V16__cashflow_mirror.sql:4 | — |
| DI-36 | 백엔드는 cln_*만 읽고 raw_*는 읽지 않는다 | 기록 없음 | PM:798 | — |
| DI-37 | 구성종목 종가는 adjusted_price_daily에서 | 별도 가격 테이블 | DR:731 | — |
| DI-38 | 섹터 체계를 통일하지 않고 원 라벨에 sector_source를 붙인다 | 공통 11섹터 매핑 테이블 | R0830:70, 74; DR:150, 827 | 변경(RS-SEC:173·FTR:75는 매핑 필요) |
| DI-39 | 데이터가 요청을 따르지 않아도 금액이 틀리지 않게 분해 여부를 실제 비중으로도 판정 | coverage만 신뢰 | LT-d:41 | — |
| DI-40 | etf_constituent 인덱스는 백엔드 미러에 걸지 않고 느려지면 데이터팀에 요청 | 이쪽이 인덱스를 검 | LT-d:303; V14__etf_constituent_mirror.sql:6 | `77e48b1`(보유 ETF만 읽어 340→40ms 우회, doc-map §5). 고도화 A |
| DI-41 | 데이터팀에 kis_account_daily 중지와 IRP 지원 여부를 요청 | 기록 없음 | ALA-d:539, 546-557 | — |
| DI-42 | 데이터 쪽 급한 순서는 알림 테이블 먼저, 포트폴리오는 collection_run | 기록 없음 | DR:120 | — |
| DI-43 | 실시간 시세는 데이터팀 서빙 테이블 + 신선도 SLA로 받는다 | 백엔드가 한투 직접 폴링 | FTR:323 | 이후 intraday 직접 적재로 구체화(DI-25) |
| DI-44 | 지연 판정 기대 시각: 장중은 마지막 DONE(또는 open_at) + 허용 지연(국내 10분·미국 20분, 여유 없음), KR 일봉은 다음 날 00:00, US 일봉·KR 수급은 다음 거래일 open_at | 기록 없음 | p/RT:257-263, 302; AL:545, 1550; DR:288-290 | 데이터 요구사항 N3 미결. 스펙 미반영 |
| DI-45 | 미국 일봉 도착은 국내 휴장과 무관하게 다음 미국 장 개장 전 | 기록 없음 | M0927:60, 72; DR:235 | 데이터 요구사항 N14 재확인 필요 |
| DI-46 | 데이터의 snapshot_run은 EOD 배치 끝에서 recorder로 쓴다(ON CONFLICT DO NOTHING) | 기록 없음 | p/RT:238 | — |

## 7. 도메인 규칙 — 포트폴리오 (PD)

| ID | 결정 | 버린 대안 | 근거 위치 | 결과 흔적 |
|---|---|---|---|---|
| PD-01 | 투자손익 = 나머지 전부(잔차). 거래 원장 없이 스냅샷 두 개 + 현금흐름으로 구하고 "설명되지 않는 변화" 항목은 두지 않는다 | 잔차 항목 | PM:330-336, 743, 1616; M0809:292-296; p/QL:510 | 충돌 PM:1169 → SG-03(§2.9 따름). T1(서버가 잔차로 계산해 항등식 테스트가 동어반복, D-01을 놓침), T2 |
| PD-02 | 투자손익을 확정(견준 두 잔고 사이 매도 실현손익 합)과 평가(나머지)로 나눈다. 구간의 모든 계좌가 5조건을 만족할 때만 나누고, BUILT이고 built_at ≥ computed_at인 처리만 인정, 기말이 확정 전이면 나누지 않음 | 기말 미실현 − 기초 미실현 별도 계산, 일부 계좌만 분리 | PM:340-349, 1400; p/IPS:5, 43-64 | SG-09. D-08(`18cb256`·front-end `18aa945`) |
| PD-03 | 해외 체결은 받지 않는다. 외화가 섞이면 분리하지 않고, 해외 종목 매도의 실현손익은 미포함(UNAVAILABLE) | 기록 없음 | PM:347, 350; PB-d:25, 223, 418 | N9 → B단계: 11/14 국내·미국 같은 규칙으로 바꾸기로(데이터팀 커버리지 의존) |
| PD-04 | 자산 변화의 실현손익 링크는 합계가 확정과 같을 때만 그리고, 이전 응답을 자리표시로 보이는 동안은 그리지 않는다 | 기록 없음 | PM:351, 1402; p/IPS:51-55, 68-71 | D-43 |
| PD-05 | 넣은 돈(입출금)은 사용자 입력 manual_cashflow에서만 받는다(자동 연동 원칙의 유일한 예외). 원장 유형 enum에 DEPOSIT/WITHDRAW가 없게 타입으로 강제 | Δ예수금 근사 역산, 증권사 입출금 이력 | PM:353, 733, 822, 1619, 1740; M0809:81-83; DR:550; p/QL:674; V1:108-109 | 근거 V-KPA:21, 197(KIS에 입출금 TR 없음). N11(POST 멱등 키 없음), AMB-15 |
| PD-06 | 배당·수수료·세금은 "번 돈". 데이터팀 cln_cashflow에서 읽고 빠진 유형만 경고 | 빈 포트 스텁(QL) | PM:355, 1618; p/QL:687; p/EC:5, 19 | 변경(QL 스텁 → EC 실제 구현) |
| PD-07 | 계좌 편입·제외는 넣은 돈·번 돈 어디에도 넣지 않는 별도 항목 | 기록 없음 | PM:415, 1617 | D-01·D-02(S1, `1121942`), D-29, D-30, N2, N3 |
| PD-08 | 기초 스냅샷이 없으면 기간 안 가장 이른 스냅샷으로 대신하고 실제 시작일을 표시. 넣은 돈 구간은 (기초 as_of, 기말 as_of]이고 자산 변화와 입출금 목록이 SnapshotPairResolver를 공유 | 기록 없음 | PM:406, 1615; MCF-d:129-139; p/MCF:5, 235-291; SnapshotPairResolver.java:22 | T2(판정 질의가 구현을 베낌) |
| PD-09 | 기간 경계 이월 계좌는 경고만 하고 오차를 정량화하지 않는다 | 기록 없음 | PM:410 | SG-06/D-05·N7, SG-07 |
| PD-10 | 계좌 간 이체는 식별하지 않고 각주로 고지 | 기록 없음 | PM:413, 1750 | — |
| PD-11 | 현재 보유는 잔고 스냅샷이 유일한 진실(거래로 역산하지 않음). 손익·비중은 우리 계산이 표준이고 증권사 값은 검증용 | 거래 역산 | PM:617; FTR:51, 62, 297 | — |
| PD-12 | 미실현 원가는 잔고 평단, 실현 원가는 재구성 평단. 불일치를 허용하고 잔고 평단의 수수료는 보정하지 않는다 | 기록 없음 | PM:615, 1585 | — |
| PD-13 | 평단은 이동가중평균, 계좌마다 독립, 세무 신고용이 아니다. 평단 대신 총 매입금액을 굴린다 | 평단 운반(반올림 누적) | PM:634, 675, 1751; PB-d:195 | — |
| PD-14 | 매수 수수료는 취득원가에 넣어 매도 시점까지 이연 | 증권사식(매수 시점 실현손실) | PM:640, 677; V-KPA:138, 231 | AMB-10 |
| PD-15 | 실현손익 기간 귀속은 체결일 | 결제일(T+2) | PM:644, 1601 | 고도화 후보 "기간 조건의 시간대 식" |
| PD-16 | 청산(수량 0) 시 basis를 지우고 재매수는 새 포지션 VERIFIED. 청산된 과거 구간은 재현하지 않는다 | 기록 없음 | PM:561, 643; PB-d:92, 242-245, 293 | — |
| PD-17 | 외화 실현손익은 매입일·매도일 환율을 각각 적용(환손익 포함, 분리 안 함). 미실현은 양변 같은 환율이라 환손익이 빠진다 | 환손익 분리 | PM:650-656, 942-950, 1747; DR:430 | 변경: FTR:116은 원화 평가손익에 환손익을 섞음 |
| PD-18 | 기업행위는 ex_date에 수량·평단 상태만 바꾸고 과거 거래를 다시 쓰지 않는다. ex_date 당일 체결보다 먼저, 같은 시각은 매수 먼저, 수량 0 체결은 무시 | 거래 재작성, 보정 가격 계열 사용, 매도 먼저(거짓 CONFLICT) | PM:660; DR:217, 221, 707; PB-d:186, 204; p/PB:28-30 | — |
| PD-19 | SPLIT만 수량을 보정(⌊수량×ratio⌋, 총액 비례 축소, 단주 대금은 실현손익에 안 넣음). MERGER·RIGHTS는 보정하지 않고 ca_unknown만 세운다 | 수량×ratio 보정 | PB-d:26, 201-205, 397, 419 | 충돌 PM:663(AMB-20) |
| PD-20 | 등급은 (계좌×종목) 역산 opening_qty로 판정(0=VERIFIED, >0=SEEDED, <0=CONFLICT), 좌변은 잔고 수량. f(S)=L인 최소 정수 S를 이분 탐색, 도중에 수량이 음수면 CONFLICT | 재구성 수량(자기참조), 스펙 공식 그대로 역산, 감 | PM:681-696, 1593; M0809:304-308; V-KPA:209; PB-d:207-225, 414-415 | V-KPA 실측으로 재설계 불필요 판정 |
| PD-21 | 등급은 1단계 직후 배치에서만 판정하고 조회 때 다시 판정하지 않는다 | 조회 시 판정 | PM:689; PB-d:137; ID-d:26 | — |
| PD-22 | 같은 opening_qty의 CONFLICT가 연속 두 판정이면 UNAVAILABLE로 강등해 "미포함 계좌"에 흡수 | 고칠 수 없는 경고 영구 표시 | PM:702; PB-d:238, 417 | — |
| PD-23 | SEEDED는 숨기지 않고 "추정" 배지(사유 NOT_TRADED/LATE_COVERAGE, 시작일). 영구 SEEDED는 "곧 해소" 뉘앙스를 빼고, 시차 오판은 도착 지연 문구로 | 숨기기, 재동기화 유도 | PM:700, 704, 717-721; PB-d:94, 114-115, 227, 320-330; V-KPA:215; DR:577 | D-07 |
| PD-24 | 시드 평단은 이력 안 가장 이른 비이월 확정 라인에서 체결을 거꾸로 되돌려 구한다 | 이력 밖 잔고 평단 | PB-d:246-258, 416 | — |
| PD-25 | 체결 커버리지 행이 없는 계좌(IRP 등)도 건너뛰지 않고 UNAVAILABLE BUILT로 남긴다 | 건너뛰기(영원히 미판정) | PB-d:163 | — |
| PD-26 | ca_unknown은 등급과 직교하는 플래그, 포지션 시작일부터 커버리지 대조로 판정. 이력 중간 미설명 수량 변동 대조는 범위 밖 | 감으로 판정 | PM:698, 1596; PB-d:24, 297-304, 420 | 충돌 PM:706(AMB-20) |
| PD-27 | UNAVAILABLE·CONFLICT는 실현손익 합계에서 빼되 "미포함 계좌 N개"로 노출 | 조용히 제외 | PM:300, 1650; ID-d:179-181 | SG-10(행은 보이고 합계에서만 뺀다)/D-23/N8. D-07 |
| PD-28 | 실현손익은 원화만 쓰고 미실현 평가손익을 실현손익 뷰에 넣지 않는다 | 현지 통화 병기, 한 화면 합산 | PM:296, 579; ID-d:183 | D-14 |
| PD-29 | 현금흐름 커버리지는 (계좌, 유형) 단위. COVERED이고 기간이 세는 날을 다 덮을 때만 확보, 행 없음은 UNAVAILABLE(0으로 읽지 않음). 백엔드는 DEPOSIT/WITHDRAW 커버리지를 읽지 않는다 | 일부 덮으면 부분 계산, 0으로 간주, 계좌×기간 단위 | PM:735; ECF-d:105-111; V-KPA:253; DR:557, 579, 810 | — |
| PD-30 | 배당은 원천징수 후 실입금액 그대로(세전 환원 안 함), 지급일 귀속. 부호는 계좌 현금 기준 | 세전 환원 | PM:818; ECF-d:79; V-KPA:195; DR:537, 801-803 | — |
| PD-31 | 외화 현금흐름은 발생일(KST) 환율 → 없으면 이하 최근 → 가장 이른 → 없으면 미확보. 원장 행마다 원 단위 HALF_UP 뒤 합산 | 기말 환율 | PM:820; ECF-d:83-91; p/EC:22-23 | — |
| PD-32 | 배당·수수료 원장은 계좌마다 (첫 잔고, 마지막 잔고]만 센다. 판정 대상은 구간이 비지 않은 계좌이고 연동 상태는 보지 않는다(해제 계좌 포함) | 연동 상태로 거르기 | PM:409; ECF-d:46, 52-61, 97-101, 126; p/EC:20-21 | SG-25. doc-map §4.3 CASHFLOW_UNCOVERED 이중 정의 |
| PD-33 | 원장 instrument_id(배당 종목별 귀속)는 쓰지 않는다 | 기록 없음 | PM:1742; ECF-d:26 | — |
| PD-34 | 입출금 미입력은 계좌 단위(기말 잔고 계좌 중 넣은 돈 구간 입력이 0건인 계좌)로 판정 | 기록 없음 | MCF-d:149-153, 362 | 충돌 PM:733("기간 판정 불가"). SG-08/D-22(`7544627`) |
| PD-35 | 입출금 날짜는 첫 잔고 다음 날부터 오늘(KST)까지, 해제 계좌는 마지막 잔고까지. 금액은 1 이상 15자리 이하 정수, KRW만 | 해제 계좌 입력 차단, UTC 시계 | MCF-d:88-98; p/MCF:39, 45 | SG-04/D-04(시트에 해제 계좌가 없음), SG-30/D-28 |
| PD-36 | 값 0 숨김은 입금·출금 항목 줄에만. 넣은 돈 그룹과 입력 링크는 남긴다 | 기록 없음 | MCF-d:188, 368 | 충돌 PM:412(AMB-20) |
| PD-37 | 같은 종목은 계좌를 합산해 1행, 평단은 수량가중. 종목 상세도 합산한 뒤 평단 | 합산 전 반올림 | PM:217; p/IDB:30-32 | — |
| PD-38 | 예수금 의사종목 행을 종목별 목록에 남긴다 | 목록에서 제외 | PM:228 | — |
| PD-39 | 원화 평단은 원 단위 아래를 버리고(증권사 앱과 맞춤), 외화는 HALF_UP | 전부 HALF_UP | PM:1031; ID-d:136; Derived.java:35-41 | `96fd715` |
| PD-40 | 렌즈에서 원가·평가손익은 행에서 빼고(TOTAL_ONLY) 평단은 숨긴다. LOOK_THROUGH에서는 lens_sensitive 축 필터를 거부(계좌 계열만) | "안분" 배지로 노출, 전개 전/후 적용 | PM:506-517, 563, 1355, 1640 | D-13 |
| PD-41 | 미분해: etf_coverage UNAVAILABLE이거나, COVERED여도 현금 제외 매칭 양수 비중이 없거나 전부 미매칭이면 ETF 행으로 남긴다 | 기타 버킷에 넣기, coverage 상태만으로 판정, 전부 기타 | PM:253, 492, 1609; LT-d:62-66, 309-310; p/LT:5 | 충돌 PM:492·253(AMB-20) |
| PD-42 | CONSTITUENT_AS_OF는 분해된 ETF가 있을 때만 싣고, 미분류 도움말의 "렌즈 켜면 실제 섹터" 안내는 뺀다 | 렌즈 응답에 항상 | LT-d:200, 232, 312-313 | 충돌 PM:1647·257(AMB-20) |
| PD-43 | 자산군 값을 다른 축에 넣지 않는다(섹터 축에서 ETF는 미분류) | ETF를 섹터 값으로 | PM:1009 | — |
| PD-44 | 종목 상세: realized와 trades는 따로 읽고(trade_id로 엮지 않음), 전 기간을 페이지 없이, 계좌별 줄엔 등급 배지 없이 실현손익 영역에 "원가 근거 줄", FX 안내는 그 종목 라인 환율만(원화 종목엔 없음) | trade_id로 종속, 기간 자르기, 계좌 줄 배지, 그날 전체 라인 | PM:424-433; ID-d:41, 200, 206, 318-331, 431; p/IDB:30-32 | 진단 §7 SG-10 ↔ 종목 상세 범위 모순 |
| PD-45 | 연동 상태와 수집 결과를 직교로 둔다. 수집 결과는 저장하지 않고 최신 collection_run에서 파생 | 한 enum | PM:1116-1134; PLB-d:337 | — |
| PD-46 | 연동 뒤 키가 무효가 되면 해제·재연동이 아니라 인증 정보 갱신으로 고친다(앱키·시크릿·라벨만, 계좌번호·env 불변, 통째로 덮음, account_ref 재계산 불일치는 409, linked_at 이동) | 해제 후 재연동 | PM:1141-1146; ALA-d:171-192, 303-311; p/CRB:7, 30 | SG-39 ③. 코드는 feat/credential-refresh 작업 중(main 미반영) |
| PD-47 | 수집 안내: CREDENTIAL_INVALID > REPEATED_FAILURE(CONNECTED, KR 영업일 2일 이상) > CREDENTIAL_UPDATED. 저장하지 않고, 원인을 단정하지 않고 연속 실패로 센다. 하루에 DONE이 하나라도 있으면 성공, 열린 실행·비영업일은 세지 않음, 인증 실패는 마지막 성공 뒤 실패들에서 찾는다. CONNECTING엔 띄우지 않음. 판정은 CollectionAlertPort 하나 | 앱키 문제로 단정, 실행 단위 세기, 마지막 실행만 보기 | PM:1148-1161; ALA-d:204-226; p/CRB:7, 31-34 | SG-39 ①. 작업 중 |
| PD-48 | next_pickup_at은 linked_at 기준, 3시간 지나면 지금 기준 | 지금 기준 | ALA-d:228 | — |
| PD-49 | KIS 상품코드는 01(위탁)·22(연금저축)만, IRP(29)·DC(55)는 거부 | IRP 수용(체결 조회 막힘), DC(Open API 불가) | ALA-d:136-145, 531; KisProduct.java:11-12 | 스펙 §7.1(제한 없음)과 다름(doc-map §4.1) |
| PD-50 | 기본 라벨은 계좌번호 없이 순번. 해제한 계좌 라벨은 순번에서 뺀다 | 기록 없음 | ALA-d:143; p/ALA:37-38 | — |
| PD-51 | 기관별 규칙은 등록 폼·처리에 격리하고 목록·뷰는 기관을 가리지 않는다(앱 KIS 규칙은 form.ts) | KIS 전제 구조 | PM:1101-1102; ALS-d:40; p/ALS:7, 31-33 | SG-33/D-34(고치지 않음) |
| PD-52 | 동기화는 항상 비동기 202. 완료 푸시 없이 폴링(GET /sync/{run_id})만, 앱은 전 계좌 동기화만 | 동기, 완료 푸시, 단일 계좌 버튼 | PM:1210, 1212; SYNC-d:27, 331; ALS-d:34, 36, 520-521 | 충돌 PM:1210(AMB-20) |
| PD-53 | 본문·Content-Type 없는 POST /sync는 전체 동기화, as_of는 KST | 400·415 | p/MS:32-34 | SG-37 |
| PD-54 | 비영업일 수동 동기화는 ALREADY_FINAL | 기록 없음 | DR:188, 191 | D-15, D-41 |
| PD-55 | 연동 해제는 즉시 현재 화면에서 빼고 과거 라인은 보존(soft delete) | 삭제 | PM:1201-1203; ALA-d:289 | SG-04/D-04 |
| PD-56 | 재연동 계좌의 평단은 마지막 basis_build 다음 날부터 잇고 해제 기간 실현손익은 보존 | 기록 없음 | p/PB:32 | — |
| PD-57 | 이월 계좌는 전역 배너가 아니라 계좌별 행 배지 + 탭 점으로 알린다 | 전역 배너 한 줄 | PM:163, 1199; ALS-d:202; p/FE2:157 | SG-14로 요약에 한 줄 추가 결정/D-18. SG-02(`MM-DD 기준`) |
| PD-58 | 필터를 건 응답의 비중 분모는 필터를 반영한 그 응답의 total_assets_krw | 기록 없음 | 결함 목록 SG-17 | — |
| PD-59 | 미매칭 종목이 있으면 그 종목만 빼지 않고 계좌 전체를 이월, 첫 수집 계좌는 안내 | 그 종목만 미매칭(줄어든 총자산이 확정) | 결함 목록 SG-16 | D-19·N5 열림 → B단계 고칠 것 |
| PD-60 | 예수금이 통화 일부만 빠지면 그 계좌를 이월하고, 계좌가 가진 통화마다 0원이라도 행을 받게 계약을 늘린다 | 기록 없음 | 결함 목록 SG-20 | D-21·N6 열림, RQ-02 |
| PD-61 | 서버 500의 message는 화면에 보이지 않고 고정 문구 + 다시 시도. 형식 오류 공통 기본값은 400 INVALID_REQUEST(API 전용 처리기가 있으면 그 코드 먼저) | 기록 없음 | 결함 목록 SG-32, SG-37; ALA-d:166(계좌 400은 전용 처리기) | D-33, D-35 열림 |

## 8. 도메인 규칙 — 알림 (AD)

| ID | 결정 | 버린 대안 | 근거 위치 | 결과 흔적 |
|---|---|---|---|---|
| AD-01 | 조건은 조립형과 프리셋 두 방식, 저장은 trigger_type + trigger_spec 하나. 프리셋은 preset_key + params로 두고 평가 때 컴파일, 평가기는 하나 | 컴파일 결과 저장 | AL:29-34, 184-186; M0927:236 | — |
| AD-02 | 조건은 AND로 묶은 평탄 리스트만. OR가 필요하면 알림 2개 | OR·불리언 트리 | AL:152, 1604 | — |
| AD-03 | 피연산자끼리 산술은 두지 않고 자주 쓰는 비율은 지표로 정의 | 피연산자 산술 | AL:1605 | — |
| AD-04 | 평가기는 알림마다 상태(링버퍼·카운터)를 들지 않고 매번 저장된 이력을 다시 읽는다 | 링버퍼·연속 카운터 | AL:88; M0927:240 | — |
| AD-05 | 평가 시점은 INTRADAY·CLOSE 둘이고 한 알림에 섞지 않는다. 이평·RSI·수급은 종가로만, 장중 왼쪽엔 가격·등락률·거래량만, 장중 오른쪽엔 직전 거래일까지 확정값 허용 | 장중·종가 혼합, 형성 중인 봉으로 판정 | AL:101-112, 252, 1606; M0927:22 | — |
| AD-06 | 미국 종목은 기준값을 USD로 받고 원화로 환산하지 않는다. 거래일은 현지 날짜 | 원화 환산(알림이 환율을 감시하게 됨) | AL:123; DR:419 | D-10(상세가 한국 날짜) |
| AD-07 | 따라잡기는 CLOSE만 밀린 거래일을 순서대로(알림당 주기마다 최대 20시점). INTRADAY는 최신 스냅샷 하나, 허용 지연 넘으면 버린다 | 기록 없음 | AL:129-134; p/RT:91-107, 2918; EvaluationRunner.java:180-192 | `b58f472` |
| AD-08 | 만료는 실제 시각으로 판정하고 만료된 알림은 밀린 거래일도 평가하지 않는다 | 기록 없음 | AL:136; p/RT:148-151 | — |
| AD-09 | lag는 요청에서 받지 않고 서버가 맞은편을 보고 정한다(LAG_NOT_ALLOWED) | 사용자가 오늘 포함 여부 선택 | AL:167, 1139; p/RULES:150 | — |
| AD-10 | persist_min은 끊김 없이 참인 구간. 허용 지연 넘는 공백이나 UNKNOWN이 끼면 UNKNOWN | 기록 없음 | AL:168 | — |
| AD-11 | 프리셋 정의: 박스권은 직전 n일 좁은 폭 + 오늘 이탈, 순매수 전환은 어제 부호 포함, 연속 순매수는 "매일 > 0", 상수와의 교차는 두지 않음, RSI는 250봉 고정 창 Wilder | 폭 조건 없음, 엣지만으로 표현, delta>0, crosses 상수, 전체 이력 의존 | AL:253, 267, 298-300; p/RULES:158 | RSI가 증권사 값과 소수점 아래에서 다를 수 있음을 감수 |
| AD-12 | 사용자 상태 지표는 CLOSE만, streak·교차 불가, 시장 지표와 섞지 않음. 값은 확정 스냅샷의 종목별 행 값 | 기록 없음 | AL:254-256, 1414-1417; PM:1053; ID-d:239 | — |
| AD-13 | 평가는 참·거짓·확인 불가 3값. AND는 FALSE 먼저 UNKNOWN 다음. UNKNOWN은 발화하지 않고 엣지 기준도 바꾸지 않는다 | 기록 없음 | M0927:244; AL:374-380, 392; FiringRule.java:10-12 | — |
| AD-14 | 발화 방식 기본은 EDGE_REARM, ONE_SHOT·COOLDOWN(장중만). COOLDOWN 경계: 마지막 발화 as_of + N분 = 이번 as_of면 울림 | 평가마다 발화(레벨 트리거) | AL:384-391; FTR:175-178, 302; p/RULES:388; p/RT:138, 142-143 | — |
| AD-15 | 생성·다시 켜기·수정 시 엣지 기준 FALSE에서 시작(이미 충족 중이면 바로 울림, 미리보기가 경고). evaluated_as_of가 빈 알림은 최신 DONE 시점 하나만 | 침묵(무음 무장), 지난 시점 소급 | AL:396-400; FTR:184 | AMB-08. SG-01/D-03: 이미 울린 시점 재평가 시 기준 거짓(`964fe31`·front-end `0f59d96`), `already_fired` 안내 |
| AD-16 | 재무장 조작은 두지 않고 ONE_SHOT은 다시 켜기로 | 재무장 조작 | AL:427 | — |
| AD-17 | 같은 종목·평가 시점·spec_hash 중복은 경고만, 저장은 막지 않는다 | 저장 차단 | AL:460 | — |
| AD-18 | 알림은 소프트 삭제하고 발화 기록은 남긴다 | 하드 삭제 | AL:464-466 | SG-25(삭제된 알림 조작은 404) |
| AD-19 | 발화 문구는 발화 시점에 서버가 완성해 저장(계좌 정보 없음). 조건 문장도 모두 서버(프리셋은 전용 틀), 제목은 고른 갈래의 이름 | 조회 시 생성, 앱이 생성, 카탈로그 라벨 고정 | AL:470, 485, 987, 1008; p/FEA:27; p/RT:157, 164-172 | SG-13, SG-28 |
| AD-20 | observed 모양은 `{conditions:[{left,right,progress}]}`, 꼬리 0 제거, 앱과의 계약 | 스펙 예시 `{price, threshold}` | p/RT:160 | 스펙 미반영(AL:719, 907) |
| AD-21 | 계열은 있는 봉으로 만든다(거래정지일·누락일 제외). 연속·교차 구간 안의 누락일만 UNKNOWN | 결측을 FALSE로 | AL:525-526; p/RULES:111-121 | SG-24/D-16·D-31 열림 |
| AD-22 | 결측 사유 2종: 분모 0은 NO_TRADE, 장중 교차에서 직전 스냅샷이 없거나 멀면 DATA_MISSING | 미리보기의 INSUFFICIENT_HISTORY 유지 | p/RT:280-281, 519 | SG-19/D-20(막 건 장중 알림은 `데이터 없음`), SG-25 |
| AD-23 | 종목 마스터에 없는 종목은 KR로 보고 INSTRUMENT_UNKNOWN | 기록 없음 | p/RT:103 | SG-26/D-25, SG-27/D-26 |
| AD-24 | 국내는 계산 창 안 ±30% 넘는 종가 변동이면 PRICE_ADJUSTMENT_SUSPECTED(첫 봉 제외), 미국은 판정 없음 | 기록 없음 | AL:535-537; M0927:62; DR:250; p/RULES:125 | D-17(하루 값 조건은 판정 안 함) |
| AD-25 | 오늘 산 종목은 확정 전 보유 AWAITING_FINAL(UNKNOWN, 발화 없음). NOT_HELD는 알림을 무효로 만들지 않고, 미리보기 NOT_HELD면 current null. 보유는 생성할 때만 확인 | 매도 시 알림 제거, NOT_HELD로 거절, 장중 값으로 미리보기 | AL:527-528, 1398; ID-d:255-269; p/IDB:5-7, 28; V17__alert_reason_awaiting_final.sql:1-3 | `462ce7b`. RULES의 CHECK에는 없던 값 |
| AD-26 | "보유 중"을 최신 스냅샷(확정 전 포함) 하나로 상세·검색·알림이 공유 | 최신 확정 스냅샷으로 보유 확인 | ID-d:237-253; p/IDB:7 | AMB-04 |
| AD-27 | 연동을 해제한 계좌는 해제한 순간부터 보유로 세지 않는다 | 기록 없음 | HoldingMapper.java:14; `27db40a`, `41f539c` | — |
| AD-28 | 데이터 닫힘: ALERT_FLOW_ENABLED·ALERT_INTRADAY_ENABLED를 운영자가 정하고 재시작으로 적용(값은 운영 market_data_run 결과 보고 후 승인). 닫힌 동안 수급·N분 지속 알림은 HELD, 나머지 장중은 종가로(AS_CLOSE, 해시는 원래 기준), 첫 평가는 최신 확정 종가 하나, HELD는 다시 열려도 따라잡지 않음, 수정은 닫힌 항목을 새로 넣을 때만 거부, 미리보기는 종가로, 지연 배너는 실제 컴파일 기준·HELD 제외 | 데이터 유무로 자동 닫기(일시 장애에도 닫힘), 지속 조건 떼고 평가, 재기준, 쌓인 시점 따라잡기, 전부 거부 | AL:338-361, 899; DR:266, 290; p/CLO:30, 101-156, 193-200, 243-247, 265-266; DataClosure.java:17-18; V18 | SG-31. `600c70b`, `3ec15cc`·`c0aaed1`(검증용 끄기·복구) |
| AD-29 | 수정할 때 종목과 트리거 종류는 바꿀 수 없다. 만료 알림을 다시 켤 때 expires_at 필수. 상태 전환 불가는 INVALID_STATUS_TRANSITION, 검증 오류는 InvalidAlertError(fields)와 코드 표 | ApiError에 fields 추가 | AL:1091, 1095; p/RULES:129-152, 7146 | SG-12(오류 표에 넣음) |
| AD-30 | 미리보기 하나가 검증·현재값·충족 여부·중복을 함께 돌려주고 오류가 있어도 200 | 기록 없음 | AL:899; p/FEA:74 | SG-38(칸 오류 노출 시점 미결)/D-39 |
| AD-31 | v1 푸시는 iOS만, 발송 행도 IOS 기기에만. Android는 앱 안 알림만 | Android 원격 푸시, 개발 빌드(expo-dev-client) 전환 | AL:660; p/RT:176, 300; M0927:214-226; DEC:166, 173; RuntimeMapper.java:88; fe:push/config.ts:5-18 | 충돌 AL:662("서버 변경 없이 연다", AMB-21) |
| AD-32 | 발화 전달 실패는 notice로 띄우지 않고, 평가하지 못한 장중 구간은 기록하지 않는다 | 공백 기록 | AL:548, 632-636, 832 | — |
| AD-33 | 푸시 페이로드에 sound: default | 기록 없음 | p/RT:178 | 스펙 페이로드에 없음(AMB-21) |
| AD-34 | 저장할 수 없는 조건을 읽지 못한 알림은 건너뛰고 경고 로그(카드만 `조건을 읽을 수 없어요`). 만료 전이나 알림 하나의 실패가 나머지를 막지 않는다. 같은 주기의 같은 입력은 한 번만 읽는다 | 전체 실패 | p/RT:50, 104-106, 2940, 3042; AL:566; StoredTriggers.java:13-14; AlertQueryService.java:40 | — |
| AD-35 | 1차 프리셋은 일봉 지표 + 시세 폴링(장기·스윙), 손절은 보유 종목만, 트리거 UX는 가이드형(자유 빌더는 1차에서 숨김) | 실시간 급변, 빈 캔버스 | FTR:148, 154, 157-168 | 변경: 이후 조립형 "조건 만들기"가 새 알림 흐름에 들어감(IA:63-64, 199) |
| AD-36 | 일봉이 하나도 없는 종목의 장중 급등락은 확인 불가, 장중 가격 도달만 동작 | 기록 없음 | 결함 목록 SG-18 | RQ-01(보내기 전) |
| AD-37 | 상장폐지 종목에 걸린 알림은 `확인 불가 · 종목 정보 없음`으로 울리지 않는다. 마스터에서 빠진 종목은 마지막 이름이나 코드를 보인다. 상장폐지 종목엔 새 알림 걸기를 두지 않는다 | `감시 중`으로 남기기 | 결함 목록 SG-26, SG-27; PM:435; ID-d:371 | D-25, D-26 열림 |
| AD-38 | 권한을 나중에 끈 기기는 앱이 앞으로 올 때 등록을 지우고, 다시 켜면 다음 저장·실행에서 재등록 | 기록 없음 | 결함 목록 SG-11 | D-24 열림 |

## 9. 범위 (SC)

| ID | 결정 | 버린 대안 | 근거 위치 | 결과 흔적 |
|---|---|---|---|---|
| SC-01 | 이번 범위는 KIS 계좌만 연동·수집한다. 재인증 상태·notice·문구를 걷어내고 V15에서 CHECK를 좁힌다(남은 CODEF 계좌가 있으면 마이그레이션을 실패시켜 자동으로 정하지 않음) | CODEF 연동, 재인증 조치 유지 | DR:603; p/KIS:5, 7; V15__account_kis_only.sql:1-19 | `4123c10`. 변경: 원래 KIS + CODEF(M0809:215, 351). SG-36(돌아오는 길 안 둠), SG-33/D-34·D-06 "고치지 않음" |
| SC-02 | 개인용 도구로 각자 본인 API 키로 본인 계좌만 연동한다 | 불특정 다수 키를 보관하는 멀티유저 서비스 | FTR:15, 309, 369 | 상업화 때 입력 모델·보관 재설계 |
| SC-03 | 자동 주문 없이 알림까지만(최종 결정은 사람) | 기록 없음 | FTR:18, 147 | — |
| SC-04 | 마이데이터 통합 제외 | 마이데이터(자본금·허가제) | SIG:179 | — |
| SC-05 | 처음엔 매수 기회 포착만 했다가 매수·매도 타이밍 알림으로 넓혔다 | 기록 없음 | SIG:23; FTR:1, 12, 145 | 변경 |
| SC-06 | 처음 MVP는 뉴스 이벤트 → 매칭 → 알림(실시간 이벤트 B 제외)이었고, 이후 뉴스 해석을 미루고 프리셋 지표 알림을 1차로 | 이벤트 유형 B를 MVP에 | SIG:136, 147; FTR:42 | 변경 |
| SC-07 | 보유·거래의 수동 입력·CSV는 두지 않고 자동 연동만(입출금만 예외) | 수동/CSV 입력(SIG:51, 178은 MVP 입력, FTR:59는 1차에 제대로 설계) | PM:1104, 1740; M0809:73, 81 | 변경(SIG·FTR → M0809·PM) |
| SC-08 | 테마는 반도체 중심으로 손으로 seed(5~6테마 × 20~30종목) | 뉴스 co-occurrence·임베딩 자동 매핑 | SIG:162-170 | 이후 원천에 후속 기록 없음 |
| SC-09 | 포트폴리오는 EOD 일배치 + 수동 새로고침만(실시간 아님) | 실시간 | M0809:22 | — |
| SC-10 | 포트폴리오 범위 밖: 수집 구현 상세, KIS 밖 기관, 재인증, 인프라, 알림 발송, PER/PBR, 벤치마크, TWR·MWR, 배당 종목별 귀속, 백테스트, 데이터 반출·계정 삭제, 과거 화면 재현, 미국 종가 당일 반영, 미국 분할 기준일 평가 어긋남 | 기록 없음 | PM:6, 1737-1746; PLB-d:29; ALA-d:28-29; SYNC-d:26; FTR:42, 106 | SG-43(미국 종가 반영이 다시 미결로) |
| SC-11 | 알림 범위 밖: 방해 금지 시간대, 평가 공백 기록, 알림 수 상한, 네이티브 프리셋, 백테스트. 알림 계획 시점엔 종목 상세의 `알림 걸기` 진입도 밖 | 기록 없음 | AL:1600-1620; p/FEA:120 | 이후 종목 상세 설계에서 진입이 생김(ID-d:371) |
| SC-12 | 회원가입·비밀번호 재설정·소셜 로그인·권한 등급·계정 공유·계좌 소유자 이전·세션 목록·원격 로그아웃을 두지 않는다(user_id 불변) | 셀프서비스, OIDC, 공유 | PM:843, 1568, 1733-1736; p/QL:690; AUTH-d:23 | — |
| SC-13 | 입출금 수정 API 없음(지우고 다시 넣기), USD 입력 없음(currency 필드는 유지) | 수정 API | MCF-d:26-27 | — |
| SC-14 | 조회 계층 1차는 파이프라인 2~6단계만(생성기·등급·실현손익 산출·ETF 안분·연동·동기화·입출금 POST·종목 상세 제외), 뒤 계획들이 하나씩 채움 | 기록 없음 | p/QL:53-66, 679-692 | README "이 저장소에 없는 것"(README.md:269-276)이 낡음 |
| SC-15 | 소소한 비범위: 요약 미니차트 렌즈 미사용(API 경로는 둠), 계좌 행에 마지막 동기화 시각 미표시(지어낸 값 방지), 다크모드 v1 미지원 | 지어낸 값·빈 자리 | LT-d:25; PM:279; ALS-d:522; p/FE1:509 | — |

## 10. 기술 선택 (TS)

| ID | 결정 | 버린 대안 | 근거 위치 | 결과 흔적 |
|---|---|---|---|---|
| TS-01 | 백엔드는 Spring Boot + PostgreSQL | 기록 없음 | SIG:89 | — |
| TS-02 | 빌드 도구는 Gradle Kotlin DSL(근거가 취향 수준임을 명시) | Maven | DEC:8-15; p/QL:72-74 | — |
| TS-03 | 마이그레이션은 Flyway 평문 SQL(금지 패턴을 정적 검사할 수 있음) | Liquibase(DB 추상화가 쓸모없고 XML이면 파서 필요) | DEC:17-26; p/QL:76-81 | 되돌리는 조건: 지원 DB가 둘 이상 |
| TS-04 | 데이터 접근은 MyBatis, ORM 없음 | JPA(GROUPING SETS 불가 등 6가지), jOOQ(코드 생성 시 미러 드리프트), JdbcClient(문자열 조립) | DEC:28-52; p/QL:83-104, 118 | AMB-05(쓰기 경로 JPA 자리도 MyBatis로 감) |
| TS-05 | 메시지 브로커를 두지 않고 DB 테이블을 대기열로 쓴다 | Kafka 등 브로커 발행(DB 커밋과 발행을 함께 성공시킬 수 없음) | AL:617, 1614; M0927:252; M1005:75-77; p/RT:6383-6386; DEC:157-166 | 변경: SIG:73, 97은 Kafka signals. M1005:87은 시세 수집용 Kafka는 허용 |
| TS-06 | 알림 전달은 Expo Push | WebSocket/SSE 푸시 + 이메일 폴백 | M0927:188-206; FTR:180; SIG:114 | 변경 |
| TS-07 | Expo 호출은 RestClient로 직접 | Expo 서버 SDK(호출 두 개뿐) | p/RT:6386-6387; DEC:161-162 | — |
| TS-08 | AWS SDK는 SSM만, HTTP 클라이언트는 JDK url-connection | apache-client, netty-nio-client | build.gradle.kts:25-30 | — |
| TS-09 | 알림 계산 순수 패키지는 Spring·MyBatis·Jakarta·Jackson에 의존하지 않고 ArchUnit으로 강제 | 기록 없음 | p/RULES:29; p/RT:37 | 진단 §8(주석 문체 차이) |
| TS-10 | 조회 컨트롤러를 뷰별로 셋으로 쪼갠다 | 단일 ViewController | p/QL:5265 | — |
| TS-11 | KIS 잔고는 python-kis, 실시간은 raw WebSocket. 국내/해외 판별은 currency로 | python-kis 실시간(캡 초과 시 조용히 실패), domestic 속성(오분류) | FTR:194; V-RT:248, 277-280 | — |
| TS-12 | 다증권사 게이트웨이 krsec·키움 REST는 1차에 쓰지 않는다(한투 단독) | krsec(신생·미검증), 키움(국내주식만) | FTR:32; RS-BRK:83; SIG:181 | — |
| TS-13 | pykrx는 시세 원천에서 뺀다 | pykrx(JS 차단·약관) | FTR:68, 230; RS-SEC:50; RS-ETF:330 | 1.2.8 + 로그인은 개발·연습 한정 후보 |
| TS-14 | 섹터 1차 원천: 미국 yfinance, 국내 Naver 업종(WICS) | SEC SIC(롤업), Alpha Vantage(25/day), KRX pykrx(대분류·상용 금지), data.go.kr | RS-SEC:162-169 | SIG:160(KRX/GICS)에서 변경. 원천 선택은 데이터 담당(DI-10) |
| TS-15 | 미국 ETF 구성종목은 SPDR XLSX 주, iShares 보조 | iShares 주(Akamai·헤드리스) | FTR:232; RS-ETF:342-353 | 국내 원천 보류(RS-ETF:340) |
| TS-16 | Expo SDK는 스토어판 Expo Go가 지원하는 58에 맞추고(55~57을 거치지 않음) `npx expo install`만 쓴다 | 개발 빌드, 한 단계씩 올리기 | p/FE1:24; p/SDK:5-7, 18-20; p/FEA:22; p/ENV:58 | AMB-07 |
| TS-17 | 앱 네비게이션은 React Navigation(native-stack + bottom-tabs) | Expo Router(딥링크 요구 없음, 조건 분기 복잡) | p/FE1:74-81 | D-43(탭 묶음을 하나 더 쌓음) |
| TS-18 | 서버 상태는 TanStack Query v5 | useEffect 직접, RTK Query, SWR | p/FE1:83-93 | R2(캐시 키에 사용자 없음), D-32(focusManager 미연결) |
| TS-19 | 클라이언트 상태는 AuthContext 하나 + 화면 로컬 state. 알림 초안은 모달 범위 Context + useReducer | Zustand·Jotai·Redux, 전역 상태 | p/FE1:95-99; p/FEA:112 | — |
| TS-20 | 스타일은 StyleSheet + 토큰 객체 | NativeWind(Babel·Metro 체인이 SDK에 민감) | p/FE1:101-103 | — |
| TS-21 | 차트 라이브러리 없이 막대는 flex View 둘 | gifted-charts·svg(도넛·워터폴) | p/FE1:105-107; p/FE2:25, 434-436 | FE1은 패키지 유지, FE2에서 제거 |
| TS-22 | 앱 테스트는 jest-expo + RNTL, 순수 함수·골든 렌더, E2E 없음 | Detox·Maestro | p/FE1:109-116 | T5(앱 CI 없음) |
| TS-23 | 앱 URL 스킴 없이 푸시의 data.event_id로 화면을 연다. 닫은 배너는 kvStore | 스킴, 새 패키지 | p/FEA:111, 119; AL:648 | — |

## 11. 앱 (FE)

| ID | 결정 | 버린 대안 | 근거 위치 | 결과 흔적 |
|---|---|---|---|---|
| FE-01 | 탭 6개(요약·종목·비중·계좌·손익·알림)를 아이콘 없이 두 글자로. 알림은 화면에 매달지 않고 탭으로. 자산 변화·입출금·연동·종목 상세·알림 상세는 스택 | 종목 화면에만 매달기, 탭으로 두기 | IA:22-34; PM:144; fe:app/navigation/RootStack.tsx:22-31 | SG-05(다른 탭 갔다 와도 상태 유지) |
| FE-02 | 인증 만료는 전역 처리: 401 → 갱신 → 거절일 때만 루트를 로그인으로 바꿔 탭 트리를 걷어낸다(모달로 보존 안 함). `/auth/login`의 401은 제외 | 화면별 상태, 모달로 덮기 | p/FE1:166, 419; PM:1678; fe:app/Root.tsx:11; fe:api/client.ts:401 | R2 |
| FE-03 | 부팅: 처음엔 로컬 expires_at만 보고 `/auth/me`를 부르지 않았다. 세션 도입 뒤 만료면 최대 5초 갱신을 기다리고, 오프라인이면 세션을 지우지 않고 탭을 연다(배너 없음) | 서버 조회, 로그인 화면으로 | p/FE1:164; AUTH-d:211-234; p/AS:71-73; fe:auth/AuthContext.tsx:155; fe:auth/session.ts:7 | 변경. doc-map §5: `GET /auth/me`는 앱이 부르지 않음 |
| FE-04 | 서버 문구를 그대로 쓰고 code로 자리만 고른다(수집 안내도 실패 코드를 읽지 않음). 비율은 클라이언트가 계산하지 않는다(금액 뺄셈·막대 길이만). 필터 선택지·축·렌즈 허용은 카탈로그에서만 | 클라이언트 재작성, 응답 행에서 수집(필터를 걸면 선택지가 줄어듦) | p/FE1:26-30, 403; p/FE2:27; p/ALS:25; p/CRA:7, 140, 191 | SG-32/D-33(500 message가 그대로 나옴), N10 |
| FE-05 | notice는 화이트리스트에 없으면 조용히 버린다. 렌즈 안내는 화면의 ⓘ가 맡고 LENS_METRICS_OMITTED는 그리지 않는다 | 서버 notice 사용 | p/FE1:257-259, 468, 474; fe:envelope/notices.ts:10 | D-09(FX_STALE이 목록에 없음), D-18 |
| FE-06 | 렌더 분기는 화면 상태가 아니라 응답의 data.group_by로 | 축·렌즈 상태로 분기 | p/FE2:26 | — |
| FE-07 | 쿼리 기본값: staleTime 30초, ApiError는 재시도 안 하고 네트워크 실패만 2회. 카탈로그 1시간, 동기화 실행·미리보기 0. 목록은 keepPreviousData, 종목 상세는 placeholder 없음(다른 종목 숫자 오인 방지) | 기록 없음 | fe:app/App.tsx:19-25; fe:api/queries/useCatalog.ts:10-19; useSyncRun.ts:45; useInstrumentDetail.ts:11-12; usePositions.ts:27 | R2(30초 안 앞사람 값), D-32. 진단 §5 타임아웃 없음 |
| FE-08 | 응답 필드는 snake_case 그대로 | camelCase 변환 | fe:api/types.ts:4-5 | 진단 §5 런타임 검증 없음 → 고도화 G |
| FE-09 | 요약은 두 응답이 다 와야 그린다 | 부분 렌더 | fe:screens/summary/SummaryScreen.tsx:129 | 진단 §5 오류가 본문을 덮음 |
| FE-10 | 탭 표시는 숫자가 아닌 점, 조치 경로가 있을 때만 켠다. CREDENTIAL_UPDATED만 있으면 켜지 않는다 | 숫자 배지, 조치 없는 알림 | IA:24, 131-132; p/FE2:157, 722; p/CRA:32, 124; fe:app/navigation/Tabs.tsx:20 | D-18 |
| FE-11 | 웹을 개발 경로로 쓰고 최종 확인은 실기기(웹은 localStorage, 배포 안 함) | 기록 없음 | p/FE2:442-445; fe:storage/kvStore.ts:8-9 | D-38, D-42(웹 한정 결함) |
| FE-12 | 필터 UI는 칩 하나 + 바텀시트. 상승·하락은 부호와 색, 화살표 없음 | 칩 3개 나열, ▲▼ | p/FE1:255, 435-441; fe:ui/FilterSheet.tsx:13 | D-37 |
| FE-13 | 화면 형태: 요약 미니차트는 시장 축 고정 100% 누적 막대(DIRECT), 비중은 순위 막대(손익 열 없음), 종목별은 2줄 카드(현재가·매입금액 없음), 기타 행은 key=OTHER로 분기해 맨 끝, 자산 변화 막대는 0 기준 좌우·색은 증감만 | 도넛, 자산군 축, 접힌 목록, 표, 라벨 문자열 분기, 전통 워터폴·색=출처 | PM:173, 203, 224-226, 247-255, 384, 391; LT-d:227 | D-29, D-30 |
| FE-14 | 알림 탭 루트에 규칙과 사건을 한 화면(새로 울린 최대 3건, 넘치면 "외 N건"). 새 알림은 모달·한 번 저장, 종목 선택은 전 종목 검색(보유 우선 정렬 없음), 보유 종목 알림 진입은 종목 상세, 온보딩이 알림 탭을 막지 않는다 | 종목별 화면 재사용, 종목별 행 두 번째 동작, 보유 우선 | IA:73, 92-110, 168; AL:1107 | — |
| FE-15 | 알림 카드엔 현재값 없음·카드에서 삭제 불가·상태순. 편집기는 자동 갱신 없이 0.5초 디바운스, 미리보기는 요청 JSON을 쿼리 키로 해 마지막 입력 응답만. 가격 도달 칸은 직전 종가로 미리 채움. 배지 전용 색 #7C3AED | 현재값 표시, 스와이프 삭제, 자동 갱신, 장중 값 | AL:1052-1055, 1130, 1219-1223; p/FEA:28, 39, 113, 115, 1485 | SG-38/D-39 |
| FE-16 | 발화는 상세를 열 때 읽음 처리 | 탭을 열 때 | IA:130 | D-40 |
| FE-17 | 푸시 라우팅: 페이로드는 event_id만, 누르면 알림 탭으로 바꾼 뒤(pop) 울린 알림 상세를 쌓는다. 작성 중 모달이면 닫힐 때까지 기다리고 마지막 푸시만. 앞화면이면 시스템 배너 대신 앱 안 배너 5초. 로그인 직후 첫 화면은 요약 | 바로 쌓기, 알림 탭으로 이동, 시스템 배너 | IA:144-166; p/FEA:118, 122; fe:push/PushRouter.tsx:21-47; fe:push/notifications.ts:14; p/SDK:31 | SG-25(작성 중 푸시는 버릴지 먼저 묻기) |
| FE-18 | 세션 만료·로그인 전에 누른 푸시는 pushInbox에 맡기고 표(ticket)로 기억한다. 결과를 그리거나 404이거나 화면을 떠나면 지우고, 배너 탭도 같은 길. 로그인에 실패해도 남기고 로그아웃 때만 버린다. 다른 계정이면 `찾을 수 없는 알림이에요` | event_id로 맞추기, 실패 시 버림 | p/REOPEN:7, 20-21, 79-86, 165-166, 247; IA:152-160; fe:push/pushInbox.ts:1-11, 61 | D-40(S2) → front-end `d495305` |
| FE-19 | 로그아웃은 계정 아이콘 → 시트 → 로그아웃(확인 없음). 서버에 닿지 않아도 막지 않고, 기기 정리는 세션 종료(CASCADE)로 | 확인 대화상자, device_id로 기기 해제(LO) | IA:114, 118; p/LO:5; p/AS:568-584; fe:screens/summary/AccountSheet.tsx:14; fe:auth/AuthContext.tsx:202; fe:push/device.ts:10-14 | 변경(LO → AS). R2 |
| FE-20 | 기기 등록은 앱이 켜질 때와 앞으로 올 때마다 다시 한다(upsert). 401로 밀려날 때는 기기를 지우지 않는다. 해제·재시도 요청의 401엔 만료 안내 없음 | 켜질 때 한 번 | AUTH-d:226-230; fe:push/PushRouter.tsx:28; p/FEA:8990; p/LO:13, 44 | SG-11/D-24 |
| FE-21 | 알림 권한은 로그인 직후가 아니라 알림을 저장할 때, 시스템 창보다 안내 시트를 먼저 | 로그인 직후 요청 | AL:621, 1212; fe:push/gate.ts:9-10 | SG-11 |
| FE-22 | 동기화는 별도 화면 없이 계좌 탭 카드. RUNNING·포커스·앱 활성일 때만 60초 폴링, 실행 id는 notice 우선·없으면 kvStore, 남의 실행 403이면 카드 없이 id 삭제, 닫힘을 처음 보면 한 번 전체 무효화 | 별도 화면, 오류 표시 | ALS-d:36, 209, 437-461; p/MSS:7, 26, 33-37; fe:api/queries/useSyncRun.ts:10, 31 | SG-40 |
| FE-23 | 무효화 범위: 등록·해제·갱신 뒤 포트폴리오 조회 전체, 입출금 저장·삭제 뒤 cashflows·asset-change. 응답 전에 화면을 떠나면 goBack은 안 하되 무효화는 한다 | 기록 없음 | ALS-d:455-461; p/ALS:7, 35; p/MCF:5 | 진단 §5: 무효화 목록을 문자열로 관리해 instrument-detail 누락 |
| FE-24 | 계좌 등록 폼: 라벨 필수·상품코드로 기본값 자동 채움(고치면 유지), 실전/모의는 체크박스(바꾸려면 해제 후 재등록), 계좌번호 숫자 10자리·키 공백 제거·라벨 30자. 갱신 폼은 계좌번호·env 읽기 전용, 본문 3필드 | 서버 순번 의존 | ALS-d:303-313; p/ALS:31-33; p/CRA:28-29, 167 | 갱신 폼은 작업 중 |
| FE-25 | 입출금 화면은 스택, 링크 줄만 누를 수 있고 저장 성공 시 금액·메모만 비운다. API는 `/portfolio/cashflows`, 목록 응답엔 봉투 없음(GET /accounts도). 서버는 JsonNode를 직접 해석해 칸별 fields[] 오류, 쓰기 매퍼는 분리하고 첫 인자 UserScope | 그룹 통째 누름, `/accounts/{id}/cashflows`, Jackson 바인딩 | MCF-d:42, 57, 100, 116-120, 174, 187, 232; ALS-d:431 | N11, D-36 |
| FE-26 | 종목 상세: instrument_id 있는 행만 누를 수 있고(예수금·렌즈 행 제외, 화살표 없음) 문구·판정은 present.ts 한 곳, 전부 미포함이면 0원 대신 —, 알림 걸기는 응답 뒤·상장폐지 종목엔 숨김, 날짜는 연도 포함 | 앱이 예수금·렌즈 판별, 0원 | PM:230; ID-d:233, 362, 372, 376-378; p/IDA:7, 27-30; fe:screens/instrumentDetail/present.ts:45 | — |
| FE-27 | iOS 날짜 칸은 투명 Modal + inline 달력(ko-KR), 바깥을 누르면 값 유지. Android·웹은 그대로 | compact 기본값(두 번 눌러야 열리고 영어) | p/IOS:7; fe:ui/DateField.tsx:14 | SG-42 |
| FE-28 | 화면 문구·문서 용어·코드 식별자를 공통 이름 표 한 곳에 두고 "발화"는 화면에 쓰지 않는다 | 기록 없음 | IA:174, 219 | 진단 §7 "재개돼요/이어져요", 렌즈 토글 이름 둘(D-13) |

## 12. SG 세부 결정 (문구·표기 수준)

위 표에 결과 흔적으로만 연결한 SG 결정이다. 미세한 화면 결정이라 따로 행을 두지 않았다.

- SG-02 이월 배지 `MM-DD 기준`(PD-57) · SG-05 탭 상태 유지(FE-01) · SG-07 기초 쪽 경계 날짜는 판정 안 함(PD-09) · SG-12 INVALID_STATUS_TRANSITION 오류 표에 추가(AD-29) · SG-13 발화 제목은 갈래 이름(AD-19) · SG-21 계좌별 뷰의 계좌 필터를 스펙에 반영 · SG-23 통화 병기는 본문 규칙(QD-32) · SG-25 세부 분기 23종은 현 코드 동작을 기대값으로 · SG-28 부호 표기 규칙(AD-19) · SG-29 렌즈 예수금 환산수량 `—`(QD-31) · SG-30 거절 이유 먼저(PD-35) · SG-33 해제 문구 KIS 앱키 유지(PD-51) · SG-34 종목코드 일부 일치(QD-47) · SG-40 열린 실행 안내는 요청 시각 뒤 첫 수집(IC-25) · SG-42 iOS 날짜 칸(FE-27)

---

## 13. 판단 불가·애매

| # | 내용 | 근거 |
|---|---|---|
| AMB-01 | 10-05 회의 안건 6건 모두 결정란이 비어 있다(문서 상태 "결정 대기"). 실시간 알림 판정·발송 주체(#2), 일봉 리버스 ETL(#1), 장 시간 클러스터 가동(#3), collection_run 컬럼 분할(#4), 미국 기업행위 원천(#5), CDC 대 배치(#6 계열). #1·#4는 DDL 실측상 시행된 것으로 보이고 #2는 스펙이 백엔드를 전제하지만, 결정 기록은 없다. #5는 R1017:107이 "결정 대기"인데 코드 주석은 "미확보로 결정"이라 적어 서로 다르다 | M1005:4, 56-59, 65-100, 117-121, 163-166, 184, 192; R1015:134; R1017:19, 107 |
| AMB-02 | 08-09 회의 문서에는 안건 9건의 결정란이 없다. 수용 여부는 08-30 리뷰가 데이터팀 설계를 근거로 판정했다. 그래서 QD-02·DI-11 등의 "결정 시점·결정 주체"가 원천상 애매하다 | M0809 전체; R0830:299-311 |
| AMB-03 | 캘린더 공백 처리가 기능마다 반대다. 포트폴리오는 평일로 어림하지 않고 확정을 멈추는데(SG-15, IC-33), 알림은 캘린더가 없으면 평일로 어림한다. 의도된 차이인지 기록이 없다 | SG-15; p/PLB:36; p/RULES:119; p/RT:266; D-16 |
| AMB-04 | 알림 생성 때 보유 판정 기준: 생성기 설계는 "가장 늦은 확정 스냅샷", 종목 상세 설계는 "최신 스냅샷(확정 전 포함)". 코드는 뒤쪽이지만 생성기 설계 개정 기록이 없다 | PLB-d:288; ID-d:237-253; p/IDB:7 |
| AMB-05 | decisions.md는 "JPA는 계좌 연동·입출금 쓰기 경로에서 쓸 자리"라 했는데 실제로는 둘 다 MyBatis다. JPA를 안 쓰기로 다시 정한 기록이 없다 | DEC:45-46; AccountLinkMapper, ManualCashflowWriteMapper |
| AMB-06 | 조회 계층 계획 안에서 집계 위치가 "SQL"(§A.2.4)과 "집계를 Java에서 하는 결정"(말미)으로 갈린다. 코드와 decisions.md는 SQL이다 | p/QL:120, 5236; DEC:54-67 |
| AMB-07 | Expo SDK 상한: front-end sdd 제약은 "Expo Go 상한 54", 같은 작업의 계획서·README는 58 | front-end .superpowers/sdd/2026-10-18-account-link-screen-plan/global-constraints.md:4; p/ALS:18 |
| AMB-08 | 생성 시 이미 참인 알림: 06-28 제안서는 "무음 무장(권장)", 알림 스펙은 "바로 울린다". 스펙이 뒤집은 근거가 기록에 없다 | FTR:184; AL:396, 400 |
| AMB-09 | 06-28 제안서의 알림 스코프(SINGLE·WATCHLIST·ALL_HOLDINGS·SECTOR·THEME 폴리모픽)가 이후 종목 단위로 바뀌었는데 바꾼 결정 기록이 없다 | FTR:152; IA:63; DR:631 |
| AMB-10 | 매수 수수료 이연(PD-14)은 KIS 방식과 다르다는 것을 알고 고른 것인지 "확인 필요"로 남아 있다 | V-KPA:138, 231 |
| AMB-11 | 데이터팀이 백엔드 표를 읽는 방식: 데이터 요구사항은 CDC, 10-05 회의는 일일 배치 SELECT + 읽기 계정을 제안. 10-17 리뷰는 읽기 계정으로 alert_watchlist를 읽는 것을 확인. 결정 기록이 없다 | DR:650-656; M1005:184; R1017:20; DEP:358-360 |
| AMB-12 | ETF 분해 범위: 회의·리뷰는 "1차는 미국만", 실측 레이크는 국내(KRX)만 있고 미국은 미착수. 데이터 요구사항 문구(미국 SPDR뿐)도 실제와 다르다 | M0809:239-252; R0830:90; R1015:119; DR:345 |
| AMB-13 | 국내 수정주가를 KIS 수정주가로 받자는 요구사항 개정 제안이 있으나, 계약 1("corporate_action만으로 보정")과 충돌하고 결론이 없다 | R1017:106, 114; DR:714 |
| AMB-14 | ETF 비중 정규화: 데이터 요구사항은 "Σweight로 나누고 잔차는 기타", look-through 설계는 Σw>1일 때만 나눈다. 데이터 요구사항 개정 기록이 없다 | DR:362; LT-d:105-110, 311 |
| AMB-15 | 입출금 POST에 멱등 키가 없다. 일부러 안 둔 결정인지, 빠뜨린 것인지 원천에 기록이 없다(B단계는 고칠 것으로 분류) | ManualCashflowService.java:47-63; 진단 N11 |
| AMB-16 | SG-35(손익 탭 처음 기간)·SG-38(미리보기 칸 오류 노출 시점)은 결함 목록에서 "미결"이다. 리뷰 작업물(triage §9)에 11/14 답이 있지만 원천 문서에는 아직 반영되지 않았다 | 결함 목록 SG-35, SG-38; review/triage.md §4, §9 |
| AMB-17 | 실시간 30~50종목 다중 appkey 샤딩(OD-46)은 백엔드가 실시간을 직접 받던 전제의 결정이다. 장중 시세를 데이터팀이 적재하게 된 뒤(DI-25) 이 결정이 살아 있는지 판단할 수 없다 | V-RT:125, 312; FTR:367; DR:303-304 |
| AMB-18 | SG-43(미국 종목 가격 기준일 어긋남)은 근본 해결 셋을 적고 "테스트 기간 뒤 검토"로 미결이다. 지금은 PRICE_LAG_MARKET 안내만 결정됐다 | 결함 목록 SG-43; p/PLM |
| AMB-19 | 테스트 기간 클러스터 상시 가동은 계획서에서 "미결"이고, 안 되면 주입으로 덮는다고만 적혀 있다 | p/TEST:86, 381 |
| AMB-20 | 포트폴리오 스펙과 추가 설계의 결론이 다른 곳 가운데 SG로 정리되지 않은 것: 재연동 account_id(IC-27), SSM 키 이름(SA-18), credential_ref 전달(DI-14), 동기화 완료 알림·단일 계좌(PD-52), 확정 전 수정·수동 실측 승격·편입 조건(IC-30·IC-35·IC-36), 미분해 조건(PD-41), CONSTITUENT_AS_OF·미분류 안내(PD-42), 입출금 미입력 판정(PD-34), 0 숨김 범위(PD-36), MERGER·RIGHTS(PD-19), 미설명 수량 변동(PD-26), IRP(PD-49). 코드는 대개 추가 설계 쪽인데 스펙 개정 기록이 없어, 어느 쪽을 "결정"으로 볼지 원천만으로는 정할 수 없다 | 각 행의 근거 |
| AMB-21 | 알림 스펙과 계획서의 결론이 다른 곳: alert_delivery 상태(QD-42), observed 모양(AD-20), 페이로드 sound(AD-33), Android를 서버 변경 없이 연다는 서술(AD-31), deprecated·spec_version 업캐스팅(QD-46, 계획·코드엔 없음). 계획서 쪽이 구현됐지만 스펙은 고쳐지지 않았다 | 각 행의 근거 |
| AMB-22 | 생성기의 설계 변경 두 건(I1 잠정 이월 확장, I2 미매칭 판정 순서)의 사용자 승인 기록이 git에 올라가지 않은 sdd 파일에만 있다. 커밋(`1f8203d`, `4d961ef`)은 있지만 결정 근거 문서가 남지 않는다 | back-end .superpowers/sdd progress.md(비추적) |
