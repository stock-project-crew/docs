# 2-2. 매수/매도 알림 — Speed (유일한 실시간)

> 관련: [설계 개요](../README.md) · [기술 스택](../tech-stack.md) · [인프라](../infrastructure.md)
>
> 이 기능만 **Speed 경로** — 나머지 4개는 전부 Batch.

**엔드포인트**

| Method | Path | 설명 |
|--------|------|------|
| POST | `/alerts/rules` | 알림 규칙 생성 |
| GET | `/alerts/rules` | 규칙 목록 |
| PATCH | `/alerts/rules/{id}` | 규칙 수정/활성·비활성 |
| DELETE | `/alerts/rules/{id}` | 규칙 삭제 |
| GET | `/alerts/events` | 발화 이력 |

**`[알림 추가]` 버튼을 누르면**

1. `[프론트]` 조건 입력 — 예: "NVDA, 평단가 대비 −10% 도달 시, **매수** 알림"
2. `[프론트]` `POST /alerts/rules`
3. `[백엔드]` `alert_rules`에 저장 (status=active, cooldown). 핫 상태라 **Postgres**
4. `[백엔드]` 해당 종목을 **KIS 구독 목록에 추가** → `[데이터]`가 그 종목 틱 수집 시작

**알림 발화 — Speed 경로 (백그라운드)**

1. `[데이터]` KIS WebSocket 틱 → Kafka 토픽 `prices.raw`
2. `[데이터]` 동시에 원본 틱을 **Bronze**(S3)로 아카이브 (백테스트·재처리용)
3. `[데이터]` Spark Structured Streaming이 `prices.raw` 소비 → 피처(전일대비·최근고점·MA) 계산 → `prices.features`
4. `[데이터]` 스트리밍 조인으로 `alert_rules` 평가
   - 평단가 기준: `(현재가 − 평단가)/평단가 ≤ −0.10` ?
   - 최근 고점 기준 / 전일 대비 / 절대가 등 분기
5. `[데이터]` 충족 + cooldown 경과 + **멱등키**(`rule_id`+봉시각) 미발송 → `alerts.events`로 emit
6. `[백엔드]` 알림 컨슈머가 `alerts.events` 소비 → FCM / 카카오 알림톡 / 이메일 발송
   - 성공 시 멱등키 기록, 실패 시 재시도
7. `[백엔드]` cooldown 윈도우 시작 → 같은 규칙 도배 차단

**핵심 주의점**

- **평가(스트리밍) ≠ 발송(컨슈머)** 분리 → 발송 실패해도 알림 유실 방지
- 멱등키 + cooldown 없으면 알림 폭탄
- 이 기능만 **Speed 경로** — 나머지는 전부 Batch
- 개인 규모면 Kafka 브로커 1대(KRaft)로 충분
