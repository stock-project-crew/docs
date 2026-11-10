# KIS 전용 범위 구현 계획 — 재인증 걷기

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 이번 범위는 KIS 계좌만 연동 · 수집하고 재인증 조치를 두지 않는다. 백엔드와 앱에서 재인증 필요 상태 · notice · 문구를 걷고, 로컬 샘플의 타 기관 계좌를 KIS 계좌로 바꾼다.

**Architecture:** `LinkState`에서 `REAUTH_REQUIRED`를 빼고, 그 값을 읽던 notice 판정과 동기화 상태 도출을 지운다. 앱은 응답 타입에서 그 값을 빼고, 배지 · 상태 줄 · 동기화 줄 · 탭 점 조건에서 그 분기를 지운다. 탭 점(`accountTabNeedsLook`)과 배지(`StateBadge`의 `LINK_LABEL`)는 구조를 그대로 두어 다음 작업이 조건과 문구를 더할 수 있게 한다. 생성기의 재인증 전이를 지운 뒤 DB CHECK를 좁힌다(Task 8 · 9).

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · MyBatis · PostgreSQL 16 · JUnit 5 · AssertJ / React Native(Expo 54) · TypeScript · jest-expo

**Spec:** [포트폴리오 스펙](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) §7.1 · §7.2 · §7.5 · §8.2 · [계좌 연동 · 동기화 화면 설계](../specs/portfolio-management/2026-10-18-account-link-screen-design.md) §3.1 · §3.4 · §3.5 · [수동 동기화 설계](../specs/portfolio-management/2026-10-17-manual-sync-design.md) §4.2 · §5.2

## Global Constraints

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어. 커밋 접두어 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **커밋 · 푸시는 사용자가 요청할 때만 한다.**
- 주석은 히스토리 없이 최신 사실만 쓰고, 문서 절 번호를 지칭하지 않는다. 고치는 주석에 이미 있는 절 지칭은 함께 풀어 쓴다.
- `dataeng/`, 통합테스트 문서(`docs/yhr/test/`)는 고치지 않는다. 생성기(`snapshot/`)는 재인증 전이만 고친다(Task 8).
- 마이그레이션은 `V15` 하나다. `data.collection_run` 미러(`db/external/V7`)는 데이터팀 계약이라 그대로 둔다.
- DB를 쓰는 테스트는 브랜치 전용 DB에서만, 돌리기 전에 묻는다: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_kis_only?currentSchema=app,data' ./gradlew test --rerun-tasks`. DB를 만드는 일도 승인을 받는다. DB 없는 단위 테스트는 묻지 않는다.
- 앱: Expo SDK 54 고정. 끝에 `npx jest` · `npx tsc --noEmit` 통과.

## Review Focus

1. **`REAUTH_REQUIRED`가 남은 곳이 데이터 계약을 읽는 곳뿐인가** — 백엔드 `src/main`에서 그 문자열은 수집 상태를 읽는 생성기 SQL(`CollectionRunMapper` · `FinalizeMapper`), 기존 마이그레이션과 미러, `V15`에만 남아야 한다. → Task 4 · 8의 grep.
2. **동기화가 수집 `REAUTH_REQUIRED`를 받으면** — 계좌 결과는 `RUNNING`으로 남고 시한이 지나면 `FAILED` · `PICKUP_TIMEOUT`으로 닫힌다. KIS 수집은 그 값을 내지 않아 이번 범위에서는 생기지 않는다. → Task 3 `알_수_없는_수집_상태는_RUNNING이다`.
3. **샘플 전환이 금액 · 소유 · 순서를 바꾸지 않는가** — 바뀌는 것은 `source` · `broker` · `label` 글자뿐이다. 계좌별 뷰와 카탈로그의 순서가 그대로다. → Task 1.
4. **계좌 탭 점** — `STALE_ACCOUNTS`에만 켜지고, 판정 함수와 접근성 이름의 구조는 그대로다. → Task 5.

---

## 파일 구조

**back-end** (`.worktrees/back-end-kis-only`, 브랜치 `chore/scope-kis-only`)

| 파일 | 책임 |
|---|---|
| `src/main/resources/db/sample/sample_portfolio.sql` | 타 기관 계좌 넷을 KIS 계좌로 |
| `src/test/resources/golden/accounts.json` · `query/AccountRepositoryTest.java` · `query/aggregate/AggregateQueryRepositoryTest.java` · `api/DisconnectedAccountViewTest.java` | 샘플 라벨 · 기관명 기대값 |
| `src/main/java/com/stockproject/portfolio/view/assembly/NoticeCode.java` · `NoticeCollector.java` · 테스트 `NoticeCollectorTest.java` | 재인증 notice 제거 |
| `src/main/java/com/stockproject/portfolio/sync/SyncRules.java` · `AccountResult.java` · 테스트 `SyncRulesTest` · `SyncCloserTest` · `SyncRunApiTest` · `SyncRequestApiTest` | 동기화 상태 도출 |
| `src/main/java/com/stockproject/portfolio/domain/LinkState.java` · `account/AccountRefIssuer.java` | enum 값 제거, 기관코드 주석 |

**front-end** (`.worktrees/front-end-kis-only`, 브랜치 `chore/scope-kis-only`)

| 파일 | 책임 |
|---|---|
| `src/api/types.ts` | `AccountLinkState`에서 값 제거 |
| `src/screens/accounts/StateBadge.tsx` · `src/screens/accountLink/linkStatus.ts` · `src/screens/accounts/syncCopy.ts` | 배지 · 상태 줄 · 동기화 줄 |
| `src/screens/accounts/tabDot.ts` · `src/app/navigation/Tabs.tsx` · `src/envelope/notices.ts` | 탭 점 조건 · notice 자리 |
| `src/fixtures/accountLinks.ts` · `src/fixtures/syncRun.ts` · `src/fixtures/golden/accounts.json` | 픽스처 |
| `src/__tests__/` 의 `accountTabDot` · `accounts` · `linkStatus` · `notices` · `syncCard` · `syncCopy` · `cashflows` · `positions` · `realizedPnl` | 테스트 |

**docs** (`.worktrees/docs-kis-only`, 브랜치 `chore/scope-kis-only`)

| 파일 | 책임 |
|---|---|
| `yhr/specs/` 7개 파일 | 스펙 · IA · 데이터 요구사항 · 설계서 셋 · 입출금 설계의 샘플 라벨 (이미 고침) |
| `yhr/specs/portfolio-management/wireflow_src.py` · `wireflow.drawio` · `wireflow.png` | 범례와 상태 목록에서 재인증 제거 |

---

## 샘플 전환표 (Task 1)

금액 · 소유자 · 계좌유형 · `account_ref`는 그대로다. `broker`는 넷 다 `한국투자증권`, `source`는 `KIS`.

| 계좌 | 소유 | 유형 | 라벨 |
|---|---|---|---|
| `…0002` | yhr | 일반 | `삼성증권` → `국내주식` |
| `…0004` | yhr | 연금 | `미래에셋 연금` → `연금저축` |
| `…0005` | jdh | 일반 | `키움 위탁` → `한국투자 주식` |
| `…0006` | jdh | 연금 | `미래에셋 IRP` → `한국투자 개인연금` |

새 라벨은 같은 유형의 다른 라벨(`한국투자 위탁` · `한국투자 IRP`)과의 순서가 코드 포인트순 · 가나다순 모두 기존과 같다. jdh 라벨은 사용자 격리 검사가 라벨 글자로 남의 계좌를 가리므로 yhr 라벨과 겹치지 않게 한다.

---

## Task 1: 샘플의 타 기관 계좌를 KIS 계좌로

**Files:** `sample_portfolio.sql`, `golden/accounts.json`, `AccountRepositoryTest.java`, `AggregateQueryRepositoryTest.java`, `DisconnectedAccountViewTest.java`(주석)

- [ ] 기대값을 먼저 바꾼다: `AccountRepositoryTest`의 `미래에셋 연금` · `미래에셋증권` → `연금저축` · `한국투자증권`, `키움 위탁` 주석 → `한국투자 주식`. `AggregateQueryRepositoryTest`의 `삼성증권` → `국내주식`, `미래에셋 연금` → `연금저축`. `golden/accounts.json`의 라벨 둘.
- [ ] 단위로 확인할 수 없어 DB 테스트(아래 Task 6)에서 실패를 본다.
- [ ] `sample_portfolio.sql`의 계좌 넷을 전환표대로 바꾼다.
- [ ] `DisconnectedAccountViewTest` 주석의 `계좌 2(삼성증권)` → `계좌 2(국내주식)`.

## Task 2: 재인증 notice를 걷는다

**Files:** `NoticeCode.java`, `NoticeCollector.java`, `NoticeCollectorTest.java`

- [ ] `NoticeCollectorTest`의 재인증 테스트(`LinkState.REAUTH_REQUIRED` 계좌 → `REAUTH_REQUIRED`)를 지운다. 같은 자리에 `연동_상태는_안내를_만들지_않는다`를 둔다: `CONNECTING` · `CONNECTED` 계좌만 있으면 계좌 관련 notice가 없다.
- [ ] `NoticeCode.REAUTH_REQUIRED`, `NoticeCollector`의 `case`와 `reauthRequired`를 지운다. `LinkState` import가 남지 않으면 지운다.
- [ ] `./gradlew test --tests '*NoticeCollectorTest'` (DB 없음) 통과.

## Task 3: 동기화 상태 도출에서 재인증을 걷는다

**Files:** `SyncRules.java`, `AccountResult.java`, `SyncRulesTest.java`, `SyncCloserTest.java`, `SyncRunApiTest.java`, `SyncRequestApiTest.java`

- [ ] `SyncRulesTest`: `REAUTH_REQUIRED` 단언을 지우고 `알_수_없는_수집_상태는_RUNNING이다`를 더한다(수집 `state = "X"` → `RUNNING`, 사유 null). 사유를 싣는 테스트는 `FAILED`만 남긴다. 실행 상태 테스트의 `REAUTH_REQUIRED`는 `FAILED`로 바꾼다.
- [ ] `SyncRules`에서 `REAUTH_REQUIRED` 상수와 분기를 지운다. `AccountResult` 주석의 상태 목록을 `RUNNING · DONE · FAILED`로.
- [ ] `./gradlew test --tests '*SyncRulesTest'` (DB 없음) 통과.
- [ ] DB 테스트 기대값: `SyncCloserTest`의 재인증 수집 → `FAILED` 수집으로 바꾸고 기대 `("FAILED", "FAILED")`. `SyncRunApiTest`의 `재인증이_필요한_수집은_REAUTH_REQUIRED`를 지운다. `SyncRequestApiTest`의 `C` 계좌를 `CONNECTING`으로(연동 중 계좌도 대상임을 본다).

## Task 4: `LinkState`에서 값을 뺀다

**Files:** `LinkState.java`, `AccountRefIssuer.java`

- [ ] `LinkState`를 `CONNECTING, CONNECTED, DISCONNECTED`로.
- [ ] `AccountRefIssuer` 기관코드 주석: "같은 계좌를 다른 경로로도 등록할 수 있게 되면 그 경로도 금융결제원 기관코드를 써야 같은 account_ref가 나온다. account_ref를 정하므로 계좌를 등록한 뒤에는 바꾸지 않는다."
- [ ] `./gradlew compileJava compileTestJava` 통과.
- [ ] `git grep -n REAUTH src/main` 결과가 `snapshot/`(생성기)뿐이고, `src/test`는 `snapshot/` 테스트뿐인지 본다. `CODEF`는 `src/main`에서 V1 CHECK뿐인지 본다.

## Task 5: 앱에서 재인증을 걷는다

**Files:** front-end 표 전부

- [ ] 테스트를 먼저 바꾼다.
  - `accountTabDot.test`: "낡은 계좌가 있으면 참", "다른 경고 notice(`FX_STALE`)만 있으면 거짓".
  - `accounts.test`: `재인증 필요` 배지 테스트를 지운다. 연동 해제 배지 테스트가 있으면 그것으로 배지 자리를 지킨다.
  - `linkStatus.test`: 픽스처 구조 분해를 새 순서로, 재인증 단언 삭제.
  - `notices.test`: 계좌별 화면 자리 단언에서 `REAUTH_REQUIRED` 삭제.
  - `syncCopy.test` · `syncCard.test`: 재인증 계좌 줄을 `수집 실패`로(픽스처의 세 번째 계좌가 `FAILED`가 된다).
- [ ] `npx jest`로 실패를 본다.
- [ ] 구현: `types.ts` 값 제거, `StateBadge`의 `LINK_LABEL` 항목 제거, `linkStatus` · `syncCopy`의 `case` 제거, `tabDot`은 `STALE_ACCOUNTS`만, `notices.ts`의 계좌별 목록에서 제거, 주석(`tabDot` · `Tabs` · `notices`)에서 재인증을 뺀다.
- [ ] 픽스처: `accountLinks`의 세 번째 계좌를 지운다. `syncRun`의 세 번째 계좌를 `FAILED` · `SOURCE_API_ERROR`로.
- [ ] 샘플과 맞춘다: `fixtures/golden/accounts.json`을 백엔드 골든과 같게. `cashflows` · `positions` · `realizedPnl` · `accounts` 테스트의 `삼성증권` · `미래에셋 연금` · `미래에셋증권`을 전환표대로.
- [ ] `npx jest` · `npx tsc --noEmit` 통과.

## Task 6: 백엔드 전체 테스트 (DB, 승인 후)

- [ ] 승인을 받아 `portfolio_test_kis_only`를 만든다.
- [ ] 승인을 받아 `TEST_DB_URL=… ./gradlew test --rerun-tasks`. 생성기 테스트 `RunProcessorTest` · `CredentialFillerTest`도 통과해야 한다(CHECK가 그대로라 문자열 값을 넣을 수 있다).

## Task 7: 와이어플로우 다시 그리기 (설치 승인 후)

- [ ] `wireflow_src.py`는 이미 고쳤다. pillow 설치 승인을 받아 스크래치패드 venv에서 `python3 wireflow_src.py`로 `wireflow.drawio` · `wireflow.png`를 다시 만든다. 범례와 상태 목록 밖은 바뀌지 않았는지 drawio diff로 본다.

---

## Task 8: 생성기의 재인증 전이를 걷는다

**Files:** `snapshot/RunProcessor.java`, `snapshot/PositionWriteMapper.java`, `snapshot/RunProcessorTest.java`, `snapshot/CredentialFillerTest.java`, 생성기 설계 §1 · §5.1 · §9 · 테스트 표

- [ ] `RunProcessorTest`: 재인증 테스트 둘을 `연동_상태는_DONE이면_CONNECTED로_옮긴다`와 `재인증_수집은_연동_상태를_바꾸지_않는다`(수집 `REAUTH_REQUIRED` → 계좌 `CONNECTED` 그대로, `SKIPPED` `RUN_NOT_DONE`)로 바꾼다. 실패를 본다.
- [ ] `RunProcessor`의 재인증 전이와 `PositionWriteMapper.markReauthRequired`를 지운다. 수집 상태를 읽는 `CollectionRunMapper` · `FinalizeMapper`의 `IN ('FAILED', 'REAUTH_REQUIRED')`는 데이터 계약을 읽는 것이라 남긴다.
- [ ] `CredentialFillerTest`의 채우지 않는 계좌를 `DISCONNECTED`로.
- [ ] `RunProcessorTest` · `CredentialFillerTest` (DB) 통과.

## Task 9: CHECK를 좁힌다 (`V15`)

**Files:** `db/migration/V15__account_kis_only.sql`, `query/SchemaContractTest.java`, 수동 동기화 설계 §3.2

- [ ] `SchemaContractTest`에 `계좌는_KIS와_세_연동_상태만_받는다` · `동기화_계좌_결과는_DONE과_FAILED만_받는다`를 더하고 실패를 본다.
- [ ] `V15`: 남은 `REAUTH_REQUIRED` 계좌는 `CONNECTED`, 동기화 결과는 `FAILED`로 옮긴 뒤 `account.link_state` · `account.source`(`KIS`만) · `sync_run_account.final_state` CHECK를 좁힌다. CODEF 계좌가 남아 있으면 마이그레이션이 실패한다.
- [ ] 배포 전에 운영 DB를 읽기 조회로 확인한다(승인 후): `account`의 `source` · `link_state`별 수, `sync_run_account`의 `final_state = 'REAUTH_REQUIRED'` 수.
- [ ] 머지 직전 `origin/main`에 `V15`가 생겼으면 다음 빈 번호로 옮기고 브랜치 DB를 새로 만들어 다시 돌린다.
- [ ] 전체 테스트 (DB).
