# 2-1. 계좌 통합 관리 — Batch (Bronze→Silver→Gold)

> 관련: [설계 개요](../README.md) · [기술 스택](../tech-stack.md) · [인프라](../infrastructure.md)

**엔드포인트**

| Method | Path | 설명 |
|--------|------|------|
| POST | `/accounts/connect` | 계좌 연동 시작 |
| POST | `/accounts/{id}/reauth` | 추가 인증 처리 |
| GET | `/accounts` | 연동된 계좌 목록 |
| DELETE | `/accounts/{id}` | 연동 해제 |
| POST | `/portfolio/sync` | 수동 새로고침 |
| GET | `/portfolio` | 통합 포트폴리오 조회 |
| GET | `/portfolio/history` | 자산 추이(시계열) |

**`[계좌 연동]` 버튼을 누르면**

1. `[프론트]` 기관(은행/증권사) + 인증수단(인증서 또는 ID/PW) 입력 받음
2. `[프론트]` 인증정보를 CODEF가 발급한 publicKey로 **RSA 암호화** → `POST /accounts/connect`
3. `[백엔드]` CODEF `POST /account/create` 호출
   - 성공 시 **Connected ID** 발급받음
   - 추가 인증 필요 시(2단계 등) `reauth` 흐름으로 분기
4. `[백엔드]` DB 저장
   - `connected_accounts`에 **Connected ID와 기관코드만** 저장
   - 인증서/비밀번호는 **절대 저장하지 않음** (CODEF만 보유)
5. `[백엔드]` **Airflow `account_sync` DAG 트리거** 후 `202 Accepted` 응답
6. `[데이터]` `account_sync` 실행 (메달리온 파이프라인)
   - 수집 잡: CODEF 호출 → 원본 응답을 **Bronze**(S3)에 적재
   - Spark 배치: Bronze → **Silver** (기관별 응답 정규화, 거래 dedup, 일별 스냅샷)
   - dbt: Silver → **Gold** (ISIN 합산 포트폴리오 뷰, 자산 추이)
   - Gold 핫 데이터를 **Postgres**로 materialize
7. `[백엔드]` 완료 신호(SSE 또는 폴링) 수신
8. `[프론트]` 포트폴리오 화면 갱신

**`[새로고침]` 버튼을 누르면**

1. `[프론트]` `POST /portfolio/sync`
2. `[백엔드]` 사용자의 모든 `connected_accounts`에 대해 Airflow `account_sync` 트리거
3. `[데이터]` 수집→Bronze→Silver→Gold 재실행
   - 실패 시 재시도, **부분 실패 허용**(한 기관 실패해도 나머지 진행)
   - 추가 인증 요구 시 Airflow sensor가 사용자 재인증 요청 이벤트 발송
4. `[백엔드]` 완료 후 해당 사용자의 포트폴리오 캐시 무효화

**포트폴리오 화면 진입 시**

1. `[프론트]` `GET /portfolio`
2. `[백엔드]` 캐시 확인 → 있으면 즉시 반환
3. `[백엔드]` 캐시 미스 시
   - Postgres의 **Gold 포트폴리오** 로드 (ISIN 합산은 Gold 생성 시 이미 반영됨)
   - 환율(USD→KRW) 적용, 평가액·평가손익 계산
   - 결과 캐싱 후 반환
   - 자산 추이(`GET /portfolio/history`)는 **Trino**로 Gold 시계열 조회

**핵심 주의점**

- 인증정보 비저장 원칙 (Connected ID만 보유) → 유출 리스크 최소화
- 동기화는 무겁고 느리므로 **반드시 비동기**, 응답은 `202`로 먼저 주고 결과는 푸시/폴링
- CODEF는 스크래핑 기반이라 느리고 불안정 → Airflow 재시도·부분 실패 허용 전제
- 계좌 데이터는 **Batch 경로**(실시간 아님)
