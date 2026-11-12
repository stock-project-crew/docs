# 울린 알림 울린 시각 정렬 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 울린 알림 목록 · 새로 울린 알림 블록 · 알림 상세의 최근 5건을 모두 울린 시각(`fired_at`) 최신순으로 정렬한다. 울린 시각이 같으면 `event_id` 내림차순이다.

**Architecture:** 서버의 세 질의(`AlertEventMapper.page`, `AlertQueryMapper.unread`, `AlertQueryMapper.recentEvents`)의 `ORDER BY`를 `e.fired_at DESC, e.event_id DESC`로 바꾸고, 목록 커서의 위치 키를 `(fired_at, event_id)`로 바꾼다. 커서 문자열의 모양(`시각|event_id`의 base64)은 그대로 둔다. 앱은 정렬 코드가 없고 보이는 값도 바뀌지 않으므로 바꾸지 않는다. 인덱스와 마이그레이션은 더하지 않는다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · MyBatis · PostgreSQL 16 · JUnit 5 · AssertJ

**Spec:** [알림 스펙](../specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md) §11.3(API 요청 · 응답) · §12.3(울린 알림 · 울린 알림 상세 화면). 이 계획의 Task 3이 두 절을 고친다.

## Global Constraints

- 응답 · 주석 · 문서 · 커밋 메시지는 한국어. 커밋 접두어 `feat:` · `fix:` · `test:` · `docs:` · `chore:`, 끝줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **커밋 · 푸시는 사용자가 요청할 때만 한다.** 각 태스크의 커밋 단계는 요청을 받은 뒤 실행한다.
- 주석은 히스토리 없이 최신 사실만 쓰고, 문서 절 번호(§ · SG-)를 새로 넣지 않는다. 고치는 줄에 있던 절 지칭은 풀어 쓴다.
- 작업 위치: back-end `.worktrees/back-end-alert-fired-order`(브랜치 `fix/alert-fired-order`), docs `.worktrees/docs-alert-push-date`(브랜치 `docs/alert-push-date`).
- DB를 쓰는 테스트는 전용 DB에서만 돈다: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_alert_fired_order?currentSchema=app,data' ./gradlew test --rerun-tasks` (특정 클래스는 `--tests '<FQCN>'`). **DB 생성과 DB 테스트 실행은 돌리기 전에 사용자에게 묻는다.** 공유 `portfolio_test`는 쓰지 않는다.
- 옛 커서는 구분하지 않는다(사용자 결정). 커서에 버전 표식을 붙이지 않는다.
- 테스트 메서드 이름은 기존처럼 한국어 문장.

## Review Focus

1. **늦게 들어온 일봉으로 나중에 울린 종가 발화** — 데이터 시점은 앞서지만 울린 시각은 뒤인 발화가 목록 · 블록 · 최근 5건 모두에서 위에 와야 한다. → Task 1 `목록은_울린_시각_내림차순이고_다음_쪽을_커서로_넘긴다`, Task 2 `새로_울린_알림은_울린_시각_최신순이다` · `최근_울림은_울린_시각_최신순이다`.
2. **울린 시각이 같은 발화가 쪽 경계에 걸림** — 두 쪽을 이어 붙이면 빠지거나 겹치는 행이 없어야 한다. → Task 1 `울린_시각이_같으면_event_id_내림차순이고_쪽_경계에서_빠지거나_겹치지_않는다`.
3. **알림으로 거른 목록(`alert_id=`)** — 같은 정렬 · 커서를 따라야 한다. → Task 1 `알림으로_거른_목록도_울린_시각_내림차순이다`.
4. **블록 · 최근 5건의 보조 키 방향** — 목록과 같은 `event_id` 내림차순이어야 한다(지금은 오름차순). → Task 2 `새로_울린_알림도_울린_시각이_같으면_event_id_내림차순이다`.
5. **기존 테스트의 고정 기록 시각** — `AlertEventApiTest.event()`가 모든 발화를 같은 `fired_at`으로 넣어, 정렬을 바꾸면 순서를 보는 기존 단언이 무작위가 된다. → Task 1 Step 1에서 헬퍼를 고친다.

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `src/main/java/com/stockproject/portfolio/alert/store/AlertEventMapper.java` | `page()` 정렬 · 커서 비교 |
| `src/main/java/com/stockproject/portfolio/alert/service/EventCursor.java` | 커서 위치 `(firedAt, eventId)` |
| `src/main/java/com/stockproject/portfolio/alert/service/AlertEventService.java` | 커서를 마지막 행의 `firedAt`으로 만든다 |
| `src/main/java/com/stockproject/portfolio/alert/store/AlertQueryMapper.java` | `unread()` · `recentEvents()` 정렬 |
| `src/test/java/com/stockproject/portfolio/alert/api/AlertEventApiTest.java` | 목록 정렬 · 커서 |
| `src/test/java/com/stockproject/portfolio/alert/api/AlertQueryApiTest.java` | 블록 · 최근 5건 정렬 |
| docs `yhr/specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md` | §11.3 · §12.3 |

---

### Task 1: 울린 알림 목록을 울린 시각으로 정렬한다

**Files:**
- Modify: `alert/store/AlertEventMapper.java` (`page`)
- Modify: `alert/service/EventCursor.java`
- Modify: `alert/service/AlertEventService.java` (`list`)
- Test: `src/test/java/com/stockproject/portfolio/alert/api/AlertEventApiTest.java`

**Interfaces:**
- Produces: `EventCursor.Position(OffsetDateTime firedAt, UUID eventId)`, `EventCursor.encode(OffsetDateTime firedAt, UUID eventId)`, `AlertEventMapper.page(scope, alertId, @Param("afterFiredAt") OffsetDateTime afterFiredAt, @Param("afterId") UUID afterId, limit)`.

- [ ] **Step 1: 테스트 헬퍼가 기록 시각을 받게 한다**

`event(UUID alertId, String asOf)`는 기록 시각을 `asOf + 40초`로 넣고, `event(UUID alertId, String asOf, String firedAt)`을 더한다. 고정 `'2026-09-28T10:00:00+09'`을 쓰던 단언(`fired_at` 값 확인)은 새 오버로드로 그 값을 넘겨 유지한다. 순서를 보는 헬퍼 `firedAts(JsonNode)`와 `eventIds(JsonNode)`를 `asOfs` 옆에 더한다.

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`목록은_데이터_시점_내림차순이고_다음_쪽을_커서로_넘긴다`를 다음으로 바꾼다.

```java
@Test
void 목록은_울린_시각_내림차순이고_다음_쪽을_커서로_넘긴다() throws Exception {
    UUID alert = create("yhr", priceReach(SAMSUNG, "CLOSE", 1));
    event(alert, "2026-09-24T15:30:00+09", "2026-09-24T16:00:00+09");
    // 늦게 들어온 일봉: 데이터 시점은 가장 앞이지만 가장 나중에 울렸다.
    event(alert, "2026-09-23T15:30:00+09", "2026-09-26T09:00:00+09");
    event(alert, "2026-09-25T15:30:00+09", "2026-09-25T16:00:00+09");

    JsonNode first = api.get("/alert-events?limit=2", "yhr").body();
    assertThat(firedAts(first)).containsExactly("2026-09-26T09:00:00+09:00", "2026-09-25T16:00:00+09:00");

    JsonNode second = api.get("/alert-events?limit=2&cursor=" + first.get("data").get("next_cursor").asText(), "yhr").body();
    assertThat(firedAts(second)).containsExactly("2026-09-24T16:00:00+09:00");
    assertThat(second.get("data").get("next_cursor").isNull()).isTrue();
}
```

원래 테스트에 있던 행 필드 단언(`alert_id` · `title` · `body` · `cadence` · `market` · `read` · `alert_deleted` · `empty_reason`)은 그대로 옮겨 둔다.

```java
@Test
void 울린_시각이_같으면_event_id_내림차순이고_쪽_경계에서_빠지거나_겹치지_않는다() throws Exception {
    UUID alert = create("yhr", priceReach(SAMSUNG, "CLOSE", 1));
    String same = "2026-09-26T09:00:00+09";
    // 발화 ID 순서를 데이터 시점 순서와 반대로 둔다. 데이터 시점으로 정렬하면 순서가 어긋난다.
    List<UUID> ids = List.of(event(ID_1, alert, "2026-09-25T15:30:00+09", same),
            event(ID_2, alert, "2026-09-24T15:30:00+09", same), event(ID_3, alert, "2026-09-23T15:30:00+09", same));

    JsonNode first = api.get("/alert-events?limit=2", "yhr").body();
    JsonNode second = api.get("/alert-events?limit=2&cursor=" + first.get("data").get("next_cursor").asText(), "yhr").body();

    List<String> seen = new ArrayList<>(eventIds(first));
    seen.addAll(eventIds(second));
    assertThat(seen).containsExactlyElementsOf(
            ids.stream().map(UUID::toString).sorted(Comparator.reverseOrder()).toList());
}

@Test
void 알림으로_거른_목록도_울린_시각_내림차순이다() throws Exception {
    UUID alert = create("yhr", priceReach(SAMSUNG, "CLOSE", 1));
    UUID other = create("yhr", priceReach(SAMSUNG, "CLOSE", 2));
    event(alert, "2026-09-24T15:30:00+09", "2026-09-24T16:00:00+09");
    event(alert, "2026-09-23T15:30:00+09", "2026-09-26T09:00:00+09");
    event(other, "2026-09-25T15:30:00+09", "2026-09-25T16:00:00+09");

    JsonNode body = api.get("/alert-events?alert_id=" + alert, "yhr").body();
    assertThat(firedAts(body)).containsExactly("2026-09-26T09:00:00+09:00", "2026-09-24T16:00:00+09:00");
}
```

UUID 문자열의 사전순은 PostgreSQL `uuid` 비교 순서와 같다(둘 다 바이트 순). `ID_1` ~ `ID_3`은 `AlertEventApiTest`의 고정 상수(`00000000-0000-0000-0000-00000000000N`)다. 무작위 ID로 두면 고치기 전에도 우연히 통과할 수 있어, ID 순서를 데이터 시점 순서와 반대로 고정한다. 헬퍼에 `event(UUID id, UUID alertId, String asOf, String firedAt)` 오버로드를 더한다.

- [ ] **Step 3: DB 테스트 실행을 사용자에게 묻고, 승인되면 실패를 확인한다**

전용 DB가 없으면 만드는 것도 함께 묻는다(`createdb portfolio_test_alert_fired_order`).

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_alert_fired_order?currentSchema=app,data' ./gradlew test --rerun-tasks --tests 'com.stockproject.portfolio.alert.api.AlertEventApiTest'`
Expected: 새 세 테스트가 FAIL(순서가 데이터 시점 순으로 나옴). 나머지는 PASS. 같은 시각 테스트가 통과하면 ID 고정이 빠진 것이다.

- [ ] **Step 4: 정렬 · 커서를 바꾼다**

- `page()`: `(e.fired_at, e.event_id) < (#{afterFiredAt}::timestamptz, #{afterId}::uuid)`, `ORDER BY e.fired_at DESC, e.event_id DESC`. 파라미터 이름을 `afterFiredAt`으로 바꾼다.
- `EventCursor`: `Position(OffsetDateTime firedAt, UUID eventId)`, `encode(OffsetDateTime firedAt, UUID eventId)`. 클래스 주석은 "마지막 행의 울린 시각과 발화 ID를 이은 불투명 문자열이다. 같은 시각에 울린 발화가 여럿이어도 쪽 경계에서 빠지거나 겹치지 않는다."로 바꾼다(계획 지칭을 뺀다).
- `AlertEventService.list`: `after.firedAt()`을 넘기고 `EventCursor.encode(last.firedAt(), last.eventId())`.

- [ ] **Step 5: 테스트가 통과하는지 본다**

Run: Step 3과 같은 명령
Expected: `AlertEventApiTest` 전부 PASS. `잘못된_목록_요청은_400이다`도 그대로 PASS(커서 모양은 바뀌지 않았다).

- [ ] **Step 6: 커밋**

```bash
git add src/main/java/com/stockproject/portfolio/alert src/test/java/com/stockproject/portfolio/alert/api/AlertEventApiTest.java
git commit -m "fix: 울린 알림 목록을 울린 시각 최신순으로 정렬한다"
```

### Task 2: 새로 울린 알림 블록과 최근 5건도 울린 시각으로 정렬한다

**Files:**
- Modify: `alert/store/AlertQueryMapper.java` (`unread`, `recentEvents`)
- Test: `src/test/java/com/stockproject/portfolio/alert/api/AlertQueryApiTest.java`

**Interfaces:**
- Consumes: 없음. 응답 모양은 바뀌지 않는다(`recent_events`에 `fired_at`을 더하지 않는다).

- [ ] **Step 1: 헬퍼에 기록 시각 오버로드를 더한다**

`event(UUID alertId, String asOf, String readAt)`는 그대로 두고(`fired_at = as_of + 40초`), `eventFired(UUID alertId, String asOf, String firedAt)`을 더한다. 이 헬퍼는 `event_id`를 돌려준다(`gen_random_uuid()` 대신 Java에서 만든 UUID를 넣는다). ID를 정해 넣는 `eventFired(UUID id, UUID alertId, String asOf, String firedAt)`도 둔다.

- [ ] **Step 2: 실패하는 테스트를 쓴다**

```java
@Test
void 새로_울린_알림은_울린_시각_최신순이다() throws Exception {
    UUID id = create(priceReach(SAMSUNG, "INTRADAY", 70000));
    eventFired(id, "2026-09-26T09:10:00+09", "2026-09-26T09:10:40+09");
    // 늦게 들어온 일봉: 데이터 시점은 앞서지만 나중에 울렸다.
    eventFired(id, "2026-09-25T15:30:00+09", "2026-09-26T09:30:00+09");

    JsonNode unread = api.get("/alerts", "yhr").body().get("data").get("unread");
    assertThat(unread).extracting(e -> e.get("fired_at").asText())
            .containsExactly("2026-09-26T09:30:00+09:00", "2026-09-26T09:10:40+09:00");
}

@Test
void 새로_울린_알림도_울린_시각이_같으면_event_id_내림차순이다() throws Exception {
    UUID id = create(priceReach(SAMSUNG, "INTRADAY", 70000));
    String same = "2026-09-26T09:30:00+09";
    List<UUID> ids = List.of(eventFired(ID_3, id, "2026-09-24T15:30:00+09", same),
            eventFired(ID_2, id, "2026-09-25T15:30:00+09", same), eventFired(ID_1, id, "2026-09-26T09:10:00+09", same));

    JsonNode unread = api.get("/alerts", "yhr").body().get("data").get("unread");
    assertThat(unread).extracting(e -> e.get("event_id").asText())
            .containsExactlyElementsOf(ids.stream().map(UUID::toString).sorted(Comparator.reverseOrder()).toList());
}

@Test
void 최근_울림은_울린_시각_최신순이다() throws Exception {
    UUID id = create(priceReach(SAMSUNG, "INTRADAY", 70000));
    eventFired(id, "2026-09-26T09:10:00+09", "2026-09-26T09:10:40+09");
    eventFired(id, "2026-09-25T15:30:00+09", "2026-09-26T09:30:00+09");

    JsonNode recent = api.get("/alerts/" + id, "yhr").body().get("recent_events");
    assertThat(recent).extracting(e -> e.get("as_of").asText())
            .containsExactly("2026-09-25T15:30:00+09:00", "2026-09-26T09:10:00+09:00");
}
```

- [ ] **Step 3: DB 테스트 실행을 사용자에게 묻고, 승인되면 실패를 확인한다**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_alert_fired_order?currentSchema=app,data' ./gradlew test --rerun-tasks --tests 'com.stockproject.portfolio.alert.api.AlertQueryApiTest'`
Expected: 새 세 테스트 FAIL. 기존 테스트 PASS.

- [ ] **Step 4: 두 질의의 정렬을 바꾼다**

`unread()` · `recentEvents()` 모두 `ORDER BY e.fired_at DESC, e.event_id DESC`. `unread()` 주석은 "미확인 발화. 울린 시각 최신순이고 같으면 발화 ID 내림차순이다. 삭제된 알림의 발화도 남아 보인다."로 바꾼다. `recentEvents()`에 같은 정렬을 한 줄 주석으로 단다.

- [ ] **Step 5: 테스트가 통과하는지 본다**

Run: Step 3과 같은 명령
Expected: `AlertQueryApiTest` 전부 PASS. 기존 `새로_울린_알림은_세_건까지이고_삭제된_알림의_것도_보인다` · `최근_울림의_cadence는_발화_행의_값이다`는 `fired_at = as_of + 40초`라 순서가 그대로다.

- [ ] **Step 6: 전체 백엔드 테스트(사용자에게 묻고)**

Run: `TEST_DB_URL='jdbc:postgresql://localhost:5432/portfolio_test_alert_fired_order?currentSchema=app,data' ./gradlew test --rerun-tasks`
Expected: BUILD SUCCESSFUL

- [ ] **Step 7: 커밋**

```bash
git add src/main/java/com/stockproject/portfolio/alert/store/AlertQueryMapper.java src/test/java/com/stockproject/portfolio/alert/api/AlertQueryApiTest.java
git commit -m "fix: 새로 울린 알림과 최근 울림을 울린 시각 최신순으로 정렬한다"
```

### Task 3: 알림 스펙의 정렬 문장을 고친다

**Files:**
- Modify: docs `yhr/specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md`

- [ ] **Step 1: §11.3을 고친다**
  - `unread` 설명: "`unread`는 알림 탭 상단 `새로 울린 알림` 블록의 내용이며 최대 3건이다. 울린 시각(`fired_at`) 최신순이고, 같으면 `event_id` 내림차순이다. 넘친 건수는 `unread_more`다."
  - `recent_events` 설명: "`recent_events`는 울린 시각 최신순(같으면 `event_id` 내림차순)으로 최근 5건이다. …"
  - 목록: "정렬은 울린 시각(`fired_at`) 내림차순이고, 같으면 `event_id` 내림차순이다. `next_cursor`가 null이면 마지막 쪽이다."
- [ ] **Step 2: §12.3 표를 고친다**: "정렬 | 울린 시각 최신순. 날짜로 묶지 않는다"
- [ ] **Step 3: 다른 절에 "데이터 시점 내림차순" · "`as_of` 내림차순"이 남지 않았는지 본다**

Run: `grep -rn "데이터 시점 내림차순\|as_of\` 내림차순" yhr/specs`
Expected: 출력 없음

- [ ] **Step 4: 커밋**

```bash
git add yhr/specs/buy-sell-timing-alert/2026-07-12-buy-sell-timing-alert-spec.md
git commit -m "docs: 울린 알림 · 새로 울린 알림 · 최근 울림을 울린 시각 최신순으로 정한다"
```
