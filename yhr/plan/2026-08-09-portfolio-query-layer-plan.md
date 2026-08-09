# 포트폴리오 종합 관리 — 백엔드 조회 계층 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

- **작성일**: 2026-08-09
- **대상 저장소**: `back-end/` (github.com/stock-project-crew/back-end)
- **근거 스펙**: [`2026-07-28-portfolio-management-spec.md`](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) · [와이어플로우](../specs/portfolio-management/wireflow.png) · [설계 공유 문서](../meetings/2026-08-09-portfolio-design-review.md)
- **스펙 수정 금지**: 이 계획은 스펙을 인용만 한다. 스펙 파일을 고치지 않는다.

**Goal:** `position_line`에 손으로 넣은 샘플 행만으로 6개 뷰의 REST 응답이 전부 나오는, 실행 가능한 조회 계층 뼈대를 만든다.

**Architecture:** 저장은 `position_line` 한 종류이고, 화면은 `group_by`만 바꾼다. 조회 요청은 `라인 적재 → 렌즈 변환 → 축 부여 → 필터 → GROUP BY+SUM → 파생 지표 → 응답 조립` 한 파이프라인을 지나며(스펙 §3.6의 2~6단계), 가산 가능한 측정값과 가산 불가능한 비율이 **서로 다른 타입**으로 분리되어 있어 비율을 더하는 코드는 컴파일되지 않는다. 집계는 SQL이 아니라 Java에서 수행한다 — 렌즈가 라인 집합을 라인 집합으로 바꾸는 순수 함수여야 하고, 그래야 `DIRECT`와 `LOOK_THROUGH`가 같은 집계 코드를 지나기 때문이다(근거는 §A.2.4).

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · Gradle (Kotlin DSL) · PostgreSQL 16 · Flyway · Spring JDBC `JdbcClient` (ORM 없음) · Docker Compose · JUnit 5 + AssertJ + Testcontainers + ArchUnit

---

## Global Constraints

이 절의 규칙은 모든 태스크의 요구사항에 암묵적으로 포함된다.

- **Java 21** (`--release 21`), **Spring Boot 3.4.5**, **Gradle 8.12+ Kotlin DSL**, **PostgreSQL 16**.
- **JSON 필드명은 snake_case.** Jackson `PropertyNamingStrategies.SNAKE_CASE`를 전역 설정한다. 스펙 §8의 예시가 모두 snake_case다.
- **비율·수익률 성격 컬럼을 스키마에 만들지 않는다** (스펙 §1.5 · §9.2). 마이그레이션 SQL을 정적 검사하는 테스트로 강제한다(Task 1).
- **금액 반올림은 라인 단위에서 한 번만.** 집계는 저장값을 그대로 더하고 집계 후 재반올림하지 않는다(§5.5).
- **비율은 응답 직전에 소수 1자리, `RoundingMode.HALF_UP`**. 분모가 0 또는 null이면 값은 `null`(0이 아니다).
- **모든 금액 계산은 `BigDecimal`.** `double`/`float`를 금액·수량·환율·비율에 쓰지 않는다. ArchUnit으로 강제한다(Task 3).
- **데이터팀 소유 테이블을 백엔드 마이그레이션이 만들지 않는다.** 소유 경계는 스펙 §11.2 — 백엔드는 `account` · `position_line` · `position_basis` · `realized_pnl_line` · `sync_run`만 소유한다. 조인에 필요한 `instrument`는 로컬·테스트 전용 미러로만 만든다(§A.2.3).
- **이번 범위에 인증을 넣지 않는다.** 근거는 §A.9.
- **한국어 라벨·메시지는 서버가 완성해 내린다**(§8.2). 클라이언트는 `message`를 그대로 출력하고 `code`로 분기한다.
- **커밋 메시지는 Conventional Commits** (`feat:` · `test:` · `chore:` · `docs:`). 각 태스크 끝에 1커밋.

---

# Part A — 배경 (이 계획만 읽고 구현할 수 있게 옮겨 담은 것)

## A.1 도달점과 범위

**도달점.** `docker compose up` → 샘플 SQL 실행 → 아래 6개 요청이 모두 `200`과 유효한 응답 봉투를 반환한다.

```
GET /portfolio/views/summary
GET /portfolio/views/positions?lens=DIRECT
GET /portfolio/views/allocation?axis=sector&lens=DIRECT
GET /portfolio/views/accounts
GET /portfolio/views/realized-pnl?period=THIS_YEAR
GET /portfolio/views/asset-change?period=CUSTOM&from=2026-07-01&to=2026-07-31
GET /portfolio/catalog
```

**스펙 §3.6 파이프라인 중 이번 범위는 2~6단계.** 0~1.6단계(수집·스냅샷 생성·등급 판정·실현손익 산출)는 범위 밖이고, 입력은 사람이 넣은 샘플 행이다.

| 단계 | 하는 일 | 이번 범위 |
|---|---|---|
| 0 | 수집·마스터 갱신 | ✕ 데이터팀 |
| 1 | 잔고 → `position_line` 정규화 | ✕ (§A.9) |
| 1.5 | `position_basis`·등급 판정 | ✕ (§A.9) |
| 1.6 | 실현손익 산출 | ✕ (§A.9) — 단 `realized_pnl_line` 테이블과 **읽기** 경로는 만든다 |
| 2 | ETF 안분(렌즈) | △ 인터페이스와 미확보 분기까지. 안분 산술은 ✕ |
| 3 | 마스터 조인 → 축 부여 | ○ |
| 3.5 | 필터 적용 | ○ |
| 4 | `GROUP BY` + `SUM` | ○ |
| 5 | 파생 지표 | ○ |
| 6 | 통화 선택·정렬·기타 버킷 배치·as-of 첨부 | ○ |

**스펙 §9 검증 규칙 중 이번 범위는 9.1의 `position_line`·렌즈 관련과 9.3 전부.** 9.1의 평단·등급 묶음은 1.5/1.6단계에 속해 제외한다.

## A.2 스택 선택과 근거

### A.2.1 빌드 도구 — **Gradle (Kotlin DSL)**

Maven과 기능 차이가 결과를 가르지 않는다. Gradle을 고른 이유는 (1) Spring Initializr 기본값이라 팀원이 프로젝트를 다시 생성해도 같은 모양이 나오고, (2) 증분 빌드로 테스트 반복이 빠르며, (3) Testcontainers·ArchUnit 같은 테스트 전용 설정이 한 파일에 모이기 때문이다. **근거가 취향 수준이라는 점을 그대로 적어 둔다** — Maven으로 바꿔도 이 계획의 나머지는 한 줄도 변하지 않는다.

### A.2.2 마이그레이션 — **Flyway (평문 SQL)**

Liquibase를 기각한 이유가 두 가지다.

1. **DB가 PostgreSQL 하나로 고정**이라(팀 합의 문서 §2.2) Liquibase의 DB 추상화(XML/YAML changeSet)가 값을 하지 않고 간접층만 늘린다.
2. **스펙 §9.2가 "비율 성격 컬럼은 스키마에 존재 불가 — 마이그레이션 리뷰에서 강제"를 요구한다.** 평문 SQL이면 이 규칙을 리뷰가 아니라 **테스트**로 바꿀 수 있다. `db/migration/*.sql`을 읽어 금지 패턴(`_pct` · `_ratio` · `_rate_of_return` · `weight` · `yield`)이 컬럼 정의에 나오면 실패하는 테스트를 Task 1에서 만든다. Liquibase XML이면 같은 검사가 changeSet 파서를 요구한다.

### A.2.3 데이터 접근 — **Spring JDBC `JdbcClient` + 손으로 쓴 SQL (ORM·jOOQ 없음)**

기각한 것과 이유:

| 후보 | 기각 사유 |
|---|---|
| **Spring Data JPA / Hibernate** | 이 서비스의 조회는 엔티티 그래프 순회가 아니라 `GROUP BY` 집계다. 더 나쁜 것은 JPA가 **엔티티에 파생 필드를 두도록 유혹한다**는 점이다 — `@Transient BigDecimal weightPct` 하나가 스펙 §1.5의 "비율은 저장하지 않는다"를 사실상 무너뜨린다. 동적 `group_by`를 Criteria API로 쓰면 읽을 수 없다. |
| **MyBatis** | XML 매퍼가 간접층을 하나 더 만들고, `<if>` 기반 동적 SQL이 Java 코드보다 리뷰하기 어렵다. 질의가 6개뿐인 규모에서 값을 하지 않는다. |
| **jOOQ** (차선) | 강점(타입 안전한 동적 질의 조합, 스키마 대조 컴파일 검증)은 실재한다. 그런데 **집계를 Java에서 하기로 정한 뒤 동적 질의가 사실상 사라졌고**(§A.2.4), 더 큰 문제는 코드 생성이다. 조인 대상인 `instrument`는 **데이터팀 소유**라 우리 마이그레이션에 없다. jOOQ 클래스를 생성하려면 소유하지 않은 테이블의 DDL 미러를 빌드 입력으로 유지해야 하고, 그 미러는 조용히 드리프트하는 **두 번째 진실의 출처**가 된다. |

**채택 근거.**

1. 집계를 Java에서 하기로 정하면 SQL 표면은 **6개 질의**로 고정된다 — 라인 적재(필터만 동적), 직전 `as_of` 총자산, `as_of` 목록, 계좌 목록, 실현손익 기간 조회, 기간 경계 스냅샷. 동적인 부분은 `WHERE` 절의 필터 조합 하나뿐이고, 필터 값은 카탈로그 대조를 통과한 enum이라 문자열 조립 위험이 없다.
2. SQL이 상수·리소스로 남아 **스펙 문장과 1:1로 대조**된다. 리뷰어가 "§6.2의 `cash_included = 제외`가 이 SQL에 반영됐는가"를 눈으로 확인할 수 있다.
3. 코드 생성 단계가 없어 데이터팀 소유 테이블의 DDL 미러를 **빌드가 아니라 로컬·테스트 프로필에만** 둘 수 있다.

**감수하는 것과 완화.** 컬럼명 오타를 컴파일이 잡지 못한다. → 질의마다 Testcontainers 저장소 테스트를 붙여(Task 4·9·10) 첫 실행에 전부 드러나게 하고, 데이터팀 소유 테이블은 `information_schema` 대조 테스트로 계약을 검사한다(Task 4).

**되돌리는 조건.** (a) §3.6 4단계를 SQL로 밀어야 할 성능 요구가 생기거나, (b) 질의 수가 15개를 넘으면 jOOQ로 옮긴다. 그때 바뀌는 것은 `query` 패키지 하나이고 나머지 계층은 인터페이스로 격리돼 있다.

### A.2.4 집계 위치 — **Java (SQL은 투영·조인·필터까지)**

렌즈는 스펙 §1.5·§3.4가 정의하듯 **라인 집합을 라인 집합으로 바꾸는 함수**다. `GROUP BY`를 SQL로 밀면 그 함수를 SQL 앞뒤 어디에도 끼울 수 없어 `DIRECT`는 SQL 집계, `LOOK_THROUGH`는 Java 집계로 **코드 경로가 갈린다.** 그러면 가산성·총합 보존·분모 규칙이 두 곳에 살고, "저장은 한 종류, 화면은 묶는 기준만 바꾼다"는 이 설계의 핵심 주장이 구현에서 깨진다.

데이터 규모가 이 선택을 공짜로 만든다. 스펙 §3.3이 "보유 규모상 조회 시 집계로 충분하므로 별도 집계 캐시는 두지 않는다"고 못 박았고, 단일 사용자 × 영업일 1벌 × 계좌×종목 수십 행이면 요청당 적재 행은 100행 이하다.

**감수하는 것.** 라인 수가 커지면 요청마다 전량 적재가 부담이 된다. → `AggregationEngine`이 인터페이스이므로 `DIRECT` 전용 SQL 구현을 뒤에 끼울 수 있다. 단 그때는 **두 구현이 같은 결과를 내는지 대조하는 테스트를 함께 넣는다**는 조건을 이 계획에 남긴다.

### A.2.5 인덱스 · 보관 기간 · 파티셔닝 (스펙 §13이 구현 계획에서 확정하라고 한 것)

| 항목 | 결정 | 근거 |
|---|---|---|
| `position_line` PK | `(as_of, account_id, instrument_id)` | 그레인 유일성을 DB가 1차 보증(§9.1) |
| `position_line` 보조 인덱스 | `(account_id, as_of)` | 자산 변화 뷰의 계좌 필터 + 기간 경계 조회 |
| `realized_pnl_line` 인덱스 | PK `trade_id`, 보조 `(sold_at)` · `(account_id, sold_at)` | 기간 귀속이 체결일(§4.3) |
| 보관 기간 | **무제한 삭제 없음** | 자산 변화 뷰가 과거 스냅샷을 읽고(§5.4), 지우면 과거 기간 계산이 불가능해진다(§7.5) |
| 파티셔닝 | **하지 않는다** | 연 증가량이 영업일 250 × 라인 수십 = 만 행 규모. 트리거를 미리 정해둔다: `position_line`이 1,000만 행을 넘거나 단일 `as_of` 조회 p95가 200ms를 넘으면 `as_of` RANGE 파티셔닝을 검토한다 |
| enum 표현 | **`text` + `CHECK`** (PostgreSQL ENUM 타입 아님) | ENUM 타입은 값 추가·삭제 마이그레이션이 번거롭고 `JdbcClient` 매핑에서 이득이 없다 |
| `instrument` FK | **걸지 않는다** | 소유 팀이 달라(§11.2) 교차 소유 FK는 배포 순서를 묶는다. 미매칭은 조인 결과 null로 드러나고 검증기가 잡는다 |

## A.3 반드시 지켜야 할 불변식 네 가지와 강제 방법

이 네 개가 이 계획의 존재 이유다. 각 항목의 "구조로 강제"가 구현의 합격선이다.

### 불변식 1 — 비율은 저장하지 않고 집계 후 계산한다 (§1.5 · §3.2 · §9.2)

```
삼성전자    매입 1,000만  평가 1,100만  → +10%
SK하이닉스  매입   100만  평가   130만  → +30%
라인별 평균 = (10+30)/2            = +20%     ← 틀림
집계 후 계산 = (1,230−1,100)/1,100 = +11.8%   ← 맞음
```

**구조로 강제하는 방법 세 겹.**

1. 스키마에 비율 컬럼이 없다 → 마이그레이션 SQL 정적 검사 테스트(Task 1).
2. 집계 누산기 타입 `Measures`에 비율 필드가 없다. `plus()`만 있고 나눗셈이 없다 → ArchUnit이 `Measures`·`MeasureBundle`의 필드명에 `Pct`/`Ratio`/`Rate`가 등장하면 실패시킨다(Task 3).
3. 비율은 `Derived`의 static 메서드만 만들 수 있고, 입력이 **집계된 번들**이라 라인 하나로는 호출 자체가 성립하지 않는다(Task 3).

### 불변식 2 — 비중의 분모는 총자산(예수금 포함), 손익률의 분모는 매입금액(예수금 제외) (§6.2 · §9.3)

**구조로 강제하는 방법.** 집계 결과 `MeasureBundle`이 CASH를 **두 슬롯으로 물리적으로 갈라** 담는다.

```java
record MeasureBundle(Measures securities /* asset_class != CASH */,
                     Measures cash      /* asset_class == CASH  */, ...)
```

- 손익 계열(`cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct`)을 만드는 함수는 `securities` 슬롯만 읽는다. CASH를 섞을 코드 경로가 없다.
- 비중의 분모는 **`TotalAssetsKrw`라는 별개 타입**만 받는다. 이 타입의 유일한 생성 경로는 집계 산출물 `Aggregation`의 `weightDenominator()`이고, 그 값은 필터·렌즈 적용 후 **응답 전체 합계**의 `securities + cash`다. 그룹 자신의 합계로 비중을 계산하는 실수는 타입이 막는다.

### 불변식 3 — 집계 값은 항상 원화, 묶음이 단일 통화일 때만 현지 통화 병기 (§3.7 · §9.3)

**구조로 강제하는 방법.** `MeasureBundle`이 통화 집합 `CurrencySet`을 함께 누산하고, 현지 통화 금액은 `Optional<LocalMoney>`로만 꺼낼 수 있다. 집합 크기가 1이 아니면 `Optional.empty()`다 — 응답 조립기가 섞인 그룹에 현지 통화를 실을 방법이 없다.

게이트는 **두 겹**이다. 스펙 §3.7 본문("묶음 안에 통화가 하나뿐일 때만")과 §3.7 표(섹터·시장·자산군·계좌·전체는 ✗)가 미묘하게 다르므로, 표를 카탈로그의 `Axis.localCurrencyEligible`로, 본문을 `CurrencySet.single()`로 각각 구현하고 **둘 다 통과할 때만** 병기한다. 단일 통화가 `KRW`이면 병기하지 않는다(원화가 곧 현지 통화).

| 묶음 | `localCurrencyEligible` |
|---|---|
| 종목 축(`instrument`) 행 · 종목별 뷰 행 | `true` |
| 통화 축(`currency`) 행 | `true` |
| 섹터 · 시장 · 자산군 · 레버리지 · 계좌 · 계좌유형 · 전체 합계 | `false` |

### 불변식 4 — 행 키와 합계 키는 이름이 겹치지 않는다 (§6.2)

같은 키가 행에서는 CASH를 포함하고 합계에서는 제외하면 소비자가 `Σ rows`와 `total`을 대조했을 때 어긋난다.

| 키 | 등장 위치 |
|---|---|
| `market_value_krw` | **행 전용** — `total`에 넣지 않는다 |
| `total_assets_krw` · `securities_value_krw` · `deposit_krw` · `cash_ratio_pct` · `daily_change_krw` · `daily_change_pct` · `account_count` | **합계 전용** — `rows[]`에 넣지 않는다 |
| `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` · `instrument_count` | 행·합계 양쪽 (양쪽 모두 CASH 제외 의미로 동일) |
| `quantity` · `avg_cost` · `weight_pct` | 행 전용 |

**구조로 강제하는 방법.** 카탈로그 `Metric`에 `scope: ROW | TOTAL | BOTH`를 두고, 응답 조립기가 `scope`를 보고 목적지를 정한다. 그리고 `Σ rows.market_value_krw == total.total_assets_krw`를 **모든 스냅샷 뷰 응답에서 검사하는 테스트**를 둔다(Task 6·8).

## A.4 카탈로그 — 실제 값

**코드 상수다. DB 테이블이 아니다**(§6). 운영자가 런타임에 뷰를 추가하지 않는다.

### A.4.1 축 8개 (§6.1)

```
Axis { key, label, source, applicableViews[], lensSensitive, enabled, localCurrencyEligible }
```

| key | 라벨 | 출처 | 사용 뷰 | `lensSensitive` | `enabled` |
|---|---|---|---|---|---|
| `account` | 계좌 | 계좌 마스터 | `accounts` | false | true |
| `account_type` | 계좌유형 | 계좌 마스터 | `accounts` | false | true |
| `instrument` | 종목 | 종목 마스터 | `positions` · `allocation` | **true** | true |
| `sector` | 섹터 | 종목 마스터 | `allocation` | **true** | true |
| `market` | 시장 | 종목 마스터 | `allocation` · `summary` 미니차트 | **true** | true |
| `currency` | 통화 | 종목 마스터 | `allocation` | **true** | true |
| `asset_class` | 자산군 | 종목 마스터 | `allocation` · `summary` 미니차트 | **true** | true |
| `is_leveraged` | 레버리지 | 종목 속성 | `allocation` | **true** | **false** — 원천 미확보, 요청 시 거부(§9.3) |

`account` 계열이 `lensSensitive = false`인 이유: look-through가 총합을 보존하므로 계좌 합계가 렌즈에 흔들리지 않는다. 그래서 `LOOK_THROUGH`에서도 계좌 필터만 허용된다(§9.3).

**분류 축의 폴백** (§6.1)

| 대상 | 그룹 키 | 라벨 |
|---|---|---|
| CASH 의사종목 | `CASH` | `현금` |
| 분류가 null인 종목(`sector = null` 등) | `UNCLASSIFIED` | `미분류` |
| 렌즈 안분의 잔여 버킷 | `OTHER` | `기타(ETF 내 비주식·미매칭)` — 정렬 시 항상 맨 끝 |

**자산군 값을 다른 축에 넣지 않는다**(§6.1). 섹터 축 `DIRECT`에서 ETF는 `미분류`로 모인다. ETF를 섹터 값으로 쓰면 축이 오염되고 렌즈의 역할과 겹친다.

### A.4.2 지표 17개 (§6.2)

```
Metric { key, label, additive, cashIncluded, lensSafe, scope, formula }
```

| key | 라벨 | 가산 | CASH | `lensSafe` | `scope` | 계산 |
|---|---|---|---|---|---|---|
| `quantity` | 수량 | ○ | 포함 | `ROW_AND_TOTAL` | ROW | `Σ 수량` |
| `total_assets_krw` | 총자산 | ○ | **포함** | `ROW_AND_TOTAL` | TOTAL | `Σ 평가금액` (securities+cash) |
| `securities_value_krw` | 유가증권 평가금액 | ○ | **제외** | `ROW_AND_TOTAL` | TOTAL | `Σ 평가금액` (securities만) |
| `market_value_krw` | 평가금액 | ○ | 행 기준 | `ROW_AND_TOTAL` | ROW | 그 행의 평가금액 (securities+cash) |
| `deposit_krw` | 예수금 | ○ | 포함 | `ROW_AND_TOTAL` | TOTAL | `Σ CASH 평가금액` |
| `daily_change_krw` | 일간 변화 | ○ | 포함 | — | TOTAL | 당일 − **직전 `as_of`**의 `total_assets_krw` |
| `daily_change_pct` | 일간 변화율 | ✕ | 포함 | — | TOTAL | `daily_change_krw ÷ 직전 as_of의 total_assets_krw` |
| `cost_amount_krw` | 매입금액 | ○ | **제외** | `TOTAL_ONLY` | BOTH | `Σ 매입금액` (securities만) |
| `unrealized_pnl_krw` | 평가손익 | ○ | **제외** | `TOTAL_ONLY` | BOTH | `Σ평가 − Σ매입` (securities만) |
| `unrealized_pnl_pct` | 평가손익률 | ✕ | **제외** | `TOTAL_ONLY` | BOTH | `평가손익 ÷ Σ매입` (securities만) |
| `avg_cost` | 평단 | ✕ | 제외 | `NEVER` | ROW | `Σ매입 ÷ Σ수량` — 잔고 평단·잔고 수량 기준 |
| `weight_pct` | 비중 | ✕ | 분모 포함 | `ROW_AND_TOTAL` | ROW | `행 평가금액 ÷ total_assets_krw` |
| `cash_ratio_pct` | 현금비중 | ✕ | 분모 포함 | `ROW_AND_TOTAL` | TOTAL | `CASH 평가 ÷ total_assets_krw` |
| `instrument_count` | 종목수 | ✕ | 제외 | `ROW_AND_TOTAL` | BOTH | `COUNT DISTINCT 종목` (CASH 제외) |
| `account_count` | 계좌수 | ✕ | 포함 | — | TOTAL | `COUNT DISTINCT 계좌` |
| `realized_pnl_krw` | 실현손익 | ○ | 제외 | `NEVER` | BOTH | `Σ 실현손익` |
| `realized_pnl_pct` | 실현손익률 | ✕ | 제외 | `NEVER` | BOTH | `Σ실현손익 ÷ Σ취득원가` |

- **가산 ○** = 행을 더해도 되는 값, **✕** = 집계 결과에만 적용 가능하며 라인 단위로 더하면 틀린다.
- **`lensSafe`** = `LOOK_THROUGH`에서의 유효 범위. `ROW_AND_TOTAL` 행·합계 모두 / `TOTAL_ONLY` **합계에만 싣고 `rows[]`에서 제외** (안분 원가가 허구이므로 — §3.4) / `NEVER` 분해 결과에서 제공 안 함.
- `daily_change_*` · `account_count`의 `lensSafe`가 `—`인 이유: 렌즈가 적용되는 지표가 아니다(요약 뷰 `total`은 렌즈 무관, §6.3).
- 평가손익은 파생 지표이지만 가산 가능하다. 저장하지 않는 이유는 가산 불가여서가 아니라 중복 저장을 피하기 위해서다(§6.2).

### A.4.3 뷰 6개 (§6.3)

```
View { viewKey, question, grain, groupBy[], metrics[], rowFields[],
        filters: { DIRECT: [...], LOOK_THROUGH: [...] },
        lensPolicy: NONE | OPTIONAL | ALWAYS, subBlocks[], ledgers[] }
```

| viewKey | 그레인 | `groupBy` | 지표 | 필터 (DIRECT / LOOK_THROUGH) | `lensPolicy` | 원장 |
|---|---|---|---|---|---|---|
| `summary` | 전체 1행 | `[]` | `total_assets_krw` · `securities_value_krw` · `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` · `cash_ratio_pct` · `daily_change_krw` · `daily_change_pct` · `account_count` · `instrument_count` | — / — | `NONE` (미니차트 `subBlock`에 `OPTIONAL`) | 스냅샷 |
| `positions` | 종목 1행(계좌 합산) | `[instrument]` | `quantity` · `avg_cost` · `cost_amount_krw` · `market_value_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` · `weight_pct` | `account`·`market`·`asset_class` / **`account`만** | `OPTIONAL` | 스냅샷 |
| `allocation` | 축 값 1행 | 축 1개 택일: `instrument`·`sector`·`market`·`currency`·`asset_class`(·`is_leveraged` 비활성) | `market_value_krw` · `weight_pct` · `instrument_count` | `account`·`account_type` / `account`·`account_type` | `OPTIONAL` | 스냅샷 |
| `accounts` | 계좌 1행 | `[account_type, account]` | `market_value_krw` · `deposit_krw`\* · `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` · `weight_pct` | — / — | `NONE` | 스냅샷 |
| `realized-pnl` | 기간 × 종목 × 체결 | `[instrument, trade]` | `sell_amount_krw` · `cost_basis_krw` · `realized_pnl_krw` · `realized_pnl_pct` | `account`·`period` | `NONE` | 거래 |
| `asset-change` | 기간 × 현금흐름 유형 | — | — (§A.6.3 전용 스키마) | `account`·`period` | `NONE` | 스냅샷 + 현금흐름 |

\* `accounts` 뷰의 `deposit_krw`는 **행에도 실린다.** §2.7이 계좌 행 컬럼으로 예수금을 요구하고 응답 키를 `market_value_krw`(계좌 총자산) · `deposit_krw`로 못 박았다. 유가증권 평가금액은 클라이언트가 차감해 표시한다. 불변식 4와 충돌하지 않는다 — `deposit_krw`의 의미가 행·합계에서 같기 때문이다(그 묶음의 CASH 평가금액 합).

- `rowFields[]` — 공통 행 스키마(§A.6.1)에 더해지는 필드. `accounts` 뷰는 `link_state` · `last_collection` · `last_synced_at`을 갖고(§6.3 · §8.2), `positions` 뷰는 시장 배지용 `market`을 갖는다(§A.10 #11). 둘 다 집계에 참여하지 않는 표시용 필드다.
- `filters` — 렌즈 상태별 허용 필터 맵. `LOOK_THROUGH`에서 `lensSensitive` 축이 빠진다. `positions`에서 `market`·`asset_class`가 사라지는 게 이 규칙의 실체다 — 전개 후 ETF가 존재하지 않아 `자산군=ETF` 필터는 항상 빈 목록이 된다(§3.6).
- `subBlocks[]` — 한 응답에 `group_by`·렌즈 조합이 둘 이상 필요한 뷰. **요약만 해당**하며 미니차트 블록은 `groupBy: [market]` 또는 `[asset_class]`, `lensPolicy: OPTIONAL`, 지표 `market_value_krw` · `weight_pct`.
- **정렬은 평가금액 내림차순 고정**이며 요청 파라미터로 받지 않는다. `기타` 버킷은 항상 맨 끝(§3.6 6단계).
- `realized-pnl`·`asset-change`는 공통 행 스키마를 쓰지 않는다(§6.3).

## A.5 응답 봉투 · notice · empty_reason

### A.5.1 봉투 (§8.2)

```json
{
  "as_of": "2026-07-27T15:30:00+09:00",
  "data": { },
  "empty_reason": null,
  "notices": [
    { "code": "STALE_ACCOUNTS", "severity": "warn",
      "message": "1개 계좌가 07-26 기준입니다",
      "params": { "count": 1, "oldest": "2026-07-26" } }
  ]
}
```

- `message`는 **서버가 완성해** 내리고 `code`를 함께 준다. 문구 수정에 앱 배포가 필요 없다.
- `severity` = `info | warn | error`.
- **봉투 `as_of`의 산출 규칙** (스펙이 값의 출처를 명시하지 않아 이 계획에서 확정): 대상 `as_of`의 라인 중 **캐리포워드가 아닌** 라인들의 `max(source_as_of)`. 그런 라인이 없으면 `as_of` 날짜의 `00:00:00+09:00`. 타임존은 `Asia/Seoul` 고정.
- **카탈로그 엔드포인트는 봉투를 쓰지 않는다** — 뷰 응답이 아니다.

### A.5.2 notice 코드 (스펙 §8.2 기준 **16종**)

> **요청서에는 "13종"으로 적혀 있으나 스펙 §8.2의 표는 16종이다.** 스펙을 기준으로 16종 전부를 옮겼다. 세는 방식의 차이일 수 있으니 계획 검토 시 확인이 필요하다.

| # | code | severity | 발생 조건 | params | 이번 범위 |
|---|---|---|---|---|---|
| 1 | `FX_APPLIED` | info | 원화 환산에 적용한 환율 (§2.3) | 통화쌍별 배열 `[{pair, rate, fx_as_of}]` + 최고령 `oldest_fx_as_of`. 라인마다 환율이 달라 단일 값으로 표기할 수 없다 | **발화** |
| 2 | `STALE_ACCOUNTS` | warn | 캐리포워드된 계좌 존재 (§7.3) | `count` · 최고령 `source_as_of` | **발화** |
| 3 | `CONSTITUENT_AS_OF` | info | 렌즈 적용 시 구성비중 기준일 (§3.4) | 최고령 기준일 `oldest` + 대상 ETF 수 `count` | 미발화 — 전개된 ETF가 0이면 생략(§A.9) |
| 4 | `CONSTITUENT_UNAVAILABLE` | warn | 구성종목 미확보 ETF 존재 (§3.4) | `count` · 미분해 평가금액 `undecomposed_krw` | **발화** |
| 5 | `LENS_METRICS_OMITTED` | info | `TOTAL_ONLY` 지표가 행에서 빠짐 (§6.2) | 생략된 지표 키 배열 `metrics` | **발화** |
| 6 | `EXCLUDED_ACCOUNTS` | warn | 실현손익 합계에서 빠진 계좌 (§2.8) | `count` | 규칙 구현·샘플 미발화 |
| 7 | `SEEDED_ROWS` | warn | 추정 등급 행 존재 (§4.5) | `count` | **발화** (`realized_pnl_line.grade`에서) |
| 8 | `CA_UNKNOWN` | warn | 기업행위 이력 미확인 (§4.4) | `instrument_id` 배열 | 미발화 — `position_basis` 없음 |
| 9 | `CASHFLOW_UNCOVERED` | warn | 현금흐름 미확보 계좌 (§4.6) | `count` | **발화** (전 계좌) |
| 10 | `PERIOD_TRUNCATED` | info | 기초 스냅샷 대체와 실제 시작일 (§2.9) | `actual_from` | **발화** |
| 11 | `BOUNDARY_CARRIED_FORWARD` | warn | 기간 경계 스냅샷에 이월 계좌 (§2.9) | `count` · `boundary` | **발화** |
| 12 | `REAUTH_REQUIRED` | warn | 재인증 대기 계좌 존재 (§7.2) | `count` | 규칙 구현·샘플 미발화 |
| 13 | `SYNC_IN_PROGRESS` | info | 동기화 진행 중 | `sync_run_id` | 미발화 — 동기화 범위 밖 |
| 14 | `PRICE_LAG_MARKET` | info | 시장별 가격 기준일이 화면 `as_of`보다 이르다 (§5.4) | 시장별 가격 기준일 | 미발화 — **스펙 공백**, §A.10 참조 |
| 15 | `ALREADY_FINAL` | info | EOD 확정 후 또는 비영업일 수동 동기화 요청 | 확정 시각 | 미발화 — 동기화 범위 밖 |
| 16 | `FX_STALE` | warn | 환율 폴백이 5영업일을 넘음 (§5.3) | 통화쌍 · `fx_as_of` | 규칙 구현·샘플 미발화 |

**16종 전부를 enum과 메시지 템플릿으로 정의한다.** 미발화 코드도 자리를 만들어야 나중에 붙일 때 응답 계약이 흔들리지 않는다.

**notices 정렬 순서는 위 표의 `#` 순서 고정.** 골든 테스트가 안정되려면 순서가 결정적이어야 한다.

### A.5.3 empty_reason 5값 (§8.2)

**빈 상태는 notices가 아니라 봉투 필드다.** `rows`가 비면 `empty_reason`이 필수이고 상태 코드는 `200`이다(§8.6).

| 값 | 조건 |
|---|---|
| `NO_ACCOUNTS` | `link_state != DISCONNECTED`인 `account` 행이 없다 (온보딩) |
| `NO_HOLDINGS` | 계좌는 있으나 대상 `as_of`의 `position_line`이 없다 |
| `NO_MATCH_FILTER` | 라인은 있으나 필터 적용 후 0행 |
| `NO_TRADES_IN_PERIOD` | `realized-pnl` — 기간 내 `realized_pnl_line`이 없다 |
| `ALL_UNAVAILABLE` | `realized-pnl` — 모든 행이 `UNAVAILABLE`·`CONFLICT`로 합계에서 제외됐다 |

**판정 순서를 고정한다** (스펙이 명시하지 않아 이 계획에서 확정): `NO_ACCOUNTS` → `NO_HOLDINGS` → (`realized-pnl`이면 `NO_TRADES_IN_PERIOD` → `ALL_UNAVAILABLE`) → `NO_MATCH_FILTER`. 먼저 맞는 것 하나만 내린다.

`summary`는 `rows`가 없는 뷰지만 라인이 0이면 같은 규칙으로 `empty_reason`을 내린다. `asset-change`는 기초·기말 스냅샷을 못 찾으면 `NO_HOLDINGS`다.

## A.6 응답 스키마

### A.6.1 스냅샷 뷰 공통 (§8.3)

요약·종목별·비중 분석·계좌별은 같은 팩트에 `group_by`만 다른 것이므로 응답 스키마도 하나다.

```json
{
  "group_by": ["sector"],
  "lens": "DIRECT",
  "total": { "total_assets_krw": 58000000, "securities_value_krw": 53300000,
             "deposit_krw": 4700000, "cost_amount_krw": 48800000,
             "unrealized_pnl_krw": 4500000, "unrealized_pnl_pct": 9.2,
             "cash_ratio_pct": 8.1, "instrument_count": 5, "account_count": 4 },
  "rows": [
    { "key": "반도체", "label": "반도체",
      "market_value_krw": 23240000, "cost_amount_krw": 20000000,
      "unrealized_pnl_krw": 3240000, "unrealized_pnl_pct": 16.2,
      "weight_pct": 40.1, "instrument_count": 2 }
  ]
}
```

- **파생 지표를 서버가 계산해 포함한다.** 가산성 규칙이 서버 안에 갇혀 클라이언트가 비율을 잘못 평균낼 여지가 없다.
- **`group_by`가 2단계면 `rows[].rows`로 중첩된다.** `accounts`가 `["account_type","account"]`이며 **소계는 항상 서버가 계산한다.**
- 요약은 `group_by`가 비어 `total`만 채워지고 미니차트가 하위 블록으로 실린다.

```json
{ "group_by": [], "lens": "DIRECT",
  "total": { "total_assets_krw": 58000000, "daily_change_krw": 1200000,
             "daily_change_pct": 2.1, "cash_ratio_pct": 8.1 },
  "rows": [],
  "mini_chart": { "group_by": ["market"], "lens": "DIRECT",
                  "rows": [ { "key": "KR", "label": "국내", "market_value_krw": 46800000, "weight_pct": 80.7 } ] } }
```

- **단일 통화 행에는 현지 통화 값을 함께 싣는다**(§3.7 · 불변식 3). 필드는 `currency` · `market_value_local` · `cost_amount_local` · `avg_cost`.
- **`Σ rows.market_value_krw = total.total_assets_krw`가 항상 성립한다.** 손익 계열은 `securities_value_krw`를 기준으로 하므로 `securities_value_krw − cost_amount_krw = unrealized_pnl_krw`도 성립한다.
- `lens = LOOK_THROUGH`이면 `TOTAL_ONLY` 지표가 `rows[]`에서 **빠지고**(`null`이 아니라 **키 자체가 없다**) `total`에만 남으며 `LENS_METRICS_OMITTED` notice가 붙는다. 위 예시 `rows[]`에서 `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` 세 개가 사라진다. `NEVER`인 `avg_cost`는 아예 제공하지 않는다.
- **CASH 행의 원가·손익은 `null`로 내린다**(키는 있고 값이 `null`). 저장값은 원가 = 평가금액이지만 노출값이 다르다(§5.2).

### A.6.2 실현손익 (§8.4)

```json
{ "period": { "from": "2026-01-01", "to": "2026-12-31" },
  "total": { "realized_pnl_krw": -28000, "cost_basis_krw": 3120000, "realized_pnl_pct": -0.9 },
  "rows": [
    { "key": "005930", "label": "삼성전자", "currency": "KRW",
      "sell_amount_krw": 1100000, "cost_basis_krw": 820000,
      "realized_pnl_krw": 277000, "realized_pnl_pct": 33.8,
      "first_sold_at": "2026-03-02", "last_sold_at": "2026-05-12",
      "trade_count": 2, "grade": "MIXED",
      "rows": [
        { "trade_id": "T-0002", "sold_at": "2026-05-12", "quantity": 5,
          "sell_amount_krw": 700000, "cost_basis_krw": 500000,
          "realized_pnl_krw": 198000, "grade": "VERIFIED" } ] } ] }
```

- **체결을 종목으로 접지 않는다**(§2.8). 2단계 중첩 `rows[].rows`를 그대로 쓴다.
- **종목 노드의 `grade`는 4값에 `MIXED`를 더한 5값**이고 체결 노드는 4값(`VERIFIED`·`SEEDED`·`UNAVAILABLE`·`CONFLICT`)이다. `MIXED`는 저장되지 않으며 **응답 조립 시에만 생긴다** — 체결 등급이 하나면 그 값, 섞이면 `MIXED`.
- `UNAVAILABLE`·`CONFLICT` 체결은 **합계에서 제외하되 제외 계좌 수를 `EXCLUDED_ACCOUNTS`로 노출**한다(§9.3). 조용히 제외하지 않는다.
- 종목 행은 단일 통화이므로 현지 통화 병기가 성립한다. **기간 합계는 원화**(§2.8).
- **정렬**: 스펙이 정하지 않았다. 이 계획에서 `last_sold_at` 내림차순, 동률은 `key` 오름차순으로 확정한다(와이어플로우의 목록 순서와 일치).

### A.6.3 자산 변화 (§8.4)

```json
{ "period": { "from": "2026-07-01", "to": "2026-07-31" },
  "opening": 56800000, "closing": 58000000,
  "deposited": 0, "earned": 1200000,
  "account_included": 0, "account_excluded": 0,
  "breakdown": [ { "type": "INVESTMENT_PNL", "amount": 1200000 } ],
  "investment_pnl": { "total": 1200000, "realized": null,
                      "unrealized_change": null, "split_available": false } }
```

**항등식** (§2.9)

```
기말 총자산 = 기초 총자산 + 넣은 돈(입금−출금) + 번 돈(투자손익+배당−수수료·세금) ± 계좌 편입·제외
투자손익   = Δ총자산 − (입금−출금) − 배당 + 수수료·세금 − 계좌 편입·제외
```

- **투자손익은 나머지 전부로 정의한다.** 우변에 거래 원장이 들어가지 않아 체결내역이 막힌 연금계좌도 정확한 손익을 얻는다. **잔차 항목을 두지 않는다**(§4.6).
- `breakdown[].type` = `DEPOSIT` · `WITHDRAW` · `DIVIDEND` · `FEE_TAX` · `INVESTMENT_PNL` (표시 유형이며 `cln_cashflow.type`과 별개). **값이 0인 항목은 행을 숨긴다**(§2.9).
- `split_available = false`이면 거래 원장이 없어 실현/미실현 분해를 생략한 것이고 `realized`·`unrealized_change`는 `null`이다. **`total`은 항상 정확하다.**
- 계좌 편입·제외는 손익도 넣은 돈도 아니므로 `breakdown[]`에 넣지 않고 **최상위 두 필드**로 둔다.
- **기초·기말 스냅샷 선정 규칙** (스펙 §2.9 경계 처리를 구현 규칙으로 확정): 기초 = `from` **직전**의 가장 늦은 `as_of` 스냅샷. 없으면 `from` 이후의 **가장 이른** 스냅샷을 쓰고 그 날짜를 `PERIOD_TRUNCATED.actual_from`으로 알린다. 기말 = `to` 이하의 가장 늦은 `as_of`.
- 계좌 편입 = 기초 스냅샷에 없고 기말에 있는 계좌의 **첫 스냅샷 총자산 합**, 제외 = 기초에 있고 기말에 없는 계좌의 **마지막 스냅샷 총자산 합**.

### A.6.4 오류 (§8.6)

```json
{ "error": { "code": "LENS_SENSITIVE_FILTER_REJECTED", "message": "구성종목 기준 보기에서는 시장 필터를 쓸 수 없습니다" } }
```

| code | HTTP | 조건 |
|---|---|---|
| `UNKNOWN_VIEW` | 404 | `view_key`가 카탈로그에 없다 |
| `UNKNOWN_AXIS` | 400 | `axis` 값이 카탈로그에 없다 |
| `AXIS_NOT_APPLICABLE` | 400 | 그 뷰에 쓸 수 없는 축 |
| `AXIS_DISABLED` | 400 | `enabled = false` 축 (`is_leveraged`) |
| `UNKNOWN_LENS` | 400 | `lens` 값이 `DIRECT`·`LOOK_THROUGH`가 아니다 |
| `LENS_NOT_ALLOWED` | 400 | `lensPolicy = NONE`인 뷰에 `lens=LOOK_THROUGH` |
| `FILTER_NOT_ALLOWED` | 400 | 그 뷰에서 지원하지 않는 필터 키 |
| `LENS_SENSITIVE_FILTER_REJECTED` | 400 | `LOOK_THROUGH` + `lensSensitive` 축 필터 (§9.3) |
| `UNKNOWN_FILTER_VALUE` | 400 | 필터 값이 enum·계좌 목록에 없다 |
| `INVALID_PERIOD` | 400 | `period=CUSTOM`인데 `from`/`to` 누락 또는 `from > to` |
| `FACT_INVARIANT_VIOLATED` | 500 | §9.1 런타임 검증 실패 (§A.8) |

**빈 상태는 오류가 아니다.** `rows: []` + `empty_reason` + `200`이다.

## A.7 테이블 컬럼과 타입

### A.7.1 `position_line` — 보유 스냅샷, 하루 한 벌 (§5.1)

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `as_of` | `date` | 일자 단위. 당일 upsert, 과거 불변 |
| `account_id` | `uuid` | → `account` FK |
| `instrument_id` | `uuid` | 데이터팀 소유 `instrument` 참조. **FK 걸지 않음**(§A.2.5) |
| `quantity` | `numeric(20,8)` | 소수 허용 — look-through 환산수량이 소수다 |
| `cost_amount_local` | `numeric(20,4)` | 매입금액은 `cln_balance.avg_price × quantity`. **`position_basis`를 쓰지 않는다** |
| `market_value_local` | `numeric(20,4)` | |
| `cost_amount_krw` | `numeric(20,0)` | 원화는 정수 |
| `market_value_krw` | `numeric(20,0)` | 원화는 정수 |
| `fx_rate` | `numeric(18,6)` | `market_value_krw`가 있으면 필수 |
| `fx_as_of` | `date` | 폴백 시 직전 영업일을 가리킨다 |
| `source_as_of` | `timestamptz` | 계좌별 실제 데이터 시각 |
| `is_carried_forward` | `boolean` | |
| `is_final` | `boolean` | EOD 배치만 true. 수동 동기화가 덮지 않는다 |

PK `(as_of, account_id, instrument_id)`. **비율 컬럼이 없다** — 자리가 없으면 잘못 더할 방법도 없다(§3.2).

### A.7.2 `account` — 계좌, 백엔드 소유 (§5.1)

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `account_id` | `uuid` PK | |
| `broker` | `text` | 기관명 (`한국투자증권`) |
| `label` | `text` | **스펙 §5.1 표에 없는 추가 컬럼.** §8.5의 `by_account[].label`과 §2.7의 계좌 표시명이 `broker`와 다르다(같은 기관에 위탁·IRP 두 계좌). 표시명을 저장한다 |
| `account_type` | `text` CHECK | `GENERAL` · `PENSION` |
| `source` | `text` CHECK | `KIS` · `CODEF` |
| `credential_ref` | `text` null | 시크릿 매니저 키. **값 자체는 저장하지 않음** |
| `link_state` | `text` CHECK | `CONNECTING` · `CONNECTED` · `REAUTH_REQUIRED` · `DISCONNECTED` |
| `last_synced_at` | `timestamptz` null | |

### A.7.3 `realized_pnl_line` — 실현손익, 매도 체결 1건 (§5.1)

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `trade_id` | `text` PK | `cln_trade` 참조. **upsert로만 생성** |
| `account_id` · `instrument_id` | `uuid` | |
| `sold_at` | `timestamptz` | 기간 귀속은 체결일 |
| `quantity` | `numeric(20,8)` | |
| `sell_amount_local` · `cost_basis_local` | `numeric(20,4)` | |
| `sell_amount_krw` · `cost_basis_krw` | `numeric(20,0)` | 각각 매도일·매입 시점 환율 적용 |
| `fee_tax` | `numeric(20,4)` | |
| `realized_pnl_local` | `numeric(20,4)` | |
| `realized_pnl_krw` | `numeric(20,0)` | |
| `grade` | `text` CHECK | `VERIFIED` · `SEEDED` · `UNAVAILABLE` · `CONFLICT` (`MIXED`는 저장하지 않는다) |

### A.7.4 `instrument` — 종목 마스터, **데이터팀 소유** (§5.1)

로컬·테스트 프로필에서만 미러를 만든다(§A.2.3).

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `instrument_id` | `uuid` PK | |
| `isin` | `text` | 국내·미국 공통 키 |
| `symbol` | `text` | 종목코드 / ticker. 행 `key`로 쓴다 |
| `name` | `text` | 행 `label`로 쓴다 |
| `asset_class` | `text` | `STOCK` · `ETF` · `CASH` |
| `market` | `text` | `KR` · `US` |
| `currency` | `text` | `KRW` · `USD` |
| `sector` | `text` null | 분류 미확정 시 null → `미분류` |
| `is_leveraged` | `boolean` null | 원천 확보 전 null |

### A.7.5 예수금을 종목으로 취급한다 (§5.2)

`instrument.asset_class = CASH`인 통화별 의사종목(`KRW 예수금` · `USD 예수금`)을 두고 예수금도 `position_line`에 넣는다. 그러면 **총자산·현금비중·자산군 축이 모두 같은 팩트 하나에서 나온다.**

- **CASH 행의 원가는 평가금액과 같은 값으로 저장한다.** `null`을 두면 `fx_rate` 필수 규칙과 충돌하고 집계에서 NULL이 전파된다.
- 대신 **손익 계열 지표는 집계에서 `asset_class != CASH` 조건을 적용**한다 → 이 계획에서는 `MeasureBundle`의 두 슬롯이 그 조건이다(불변식 2).
- **응답의 CASH 행은 원가·손익을 `null`로 내린다.** 저장값과 노출값이 다르다.

## A.8 런타임 검증 (§9.1 중 이번 범위)

`position_line`을 읽은 직후, **집계 전에** 통과해야 한다. 위반은 조용히 넘기지 않고 `500 FACT_INVARIANT_VIOLATED`로 실패시킨다 — 손으로 넣은 샘플이 틀렸다는 뜻이므로 크게 터지는 쪽이 맞다.

| 규칙 | 강제 지점 |
|---|---|
| `position_line`은 `(as_of, account, instrument)`마다 **정확히 1행** — 그레인 유일성 | PK(1차) + `PositionLineInvariants`(적재된 라인 집합 재검사) |
| `market_value_krw`가 있으면 `fx_rate`·`fx_as_of` 필수 | `NOT NULL` 3개(1차) + 검증기(렌즈 산출 라인까지 커버) |
| 연동이 유효한(`DISCONNECTED`가 아닌) 모든 계좌는 해당 `as_of`에 라인 존재 | 검증기 — `account` 목록과 대조. 빠뜨리면 그날만 총자산이 급락해 손실처럼 보인다 |
| `is_carried_forward = true`이면 `source_as_of < as_of` | **검증기 전용.** `timestamptz AT TIME ZONE`이 immutable이 아니라 CHECK 제약으로 표현할 수 없다 |
| CASH 행은 원가 = 평가금액 (§5.2) | 검증기 — `asset_class`가 다른 테이블에 있어 CHECK로 표현 불가 |
| look-through 전개 후 `Σ market_value_krw`가 전개 전과 일치 (총합 보존, 기타 버킷 포함) | `LensOutputInvariants` — 렌즈 적용 직후 |
| `etf_coverage.state = UNAVAILABLE`인 ETF는 전개하지 않고 ETF 행을 남긴다 | `LookThroughLens`의 분기 (§A.9) |

**범위 밖인 §9.1 규칙과 이유**: `as_of` 영업일 생성·당일 외 수정 불가·비영업일 라인 미생성·`is_final` 보호는 모두 **라인을 만드는** 1단계 규칙이고, 평단·등급·실현손익 묶음은 1.5/1.6단계다.

## A.9 범위 제외와 뼈대에 남기는 자리

| 제외 항목 | 이유 | 뼈대에 남기는 자리 |
|---|---|---|
| `position_line` 생성 (1단계) | 입력이 될 `cln_*` 테이블 스키마가 팀 미합의 (설계 공유 문서 안건 5) | `position_line` 테이블 + 샘플 SQL. `cln_balance`/`cln_deposit` 미러는 만들지 않는다 |
| 등급 판정 (1.5) · 실현손익 산출 (1.6) | 전제가 실측 대기 (안건 2·4, "검증되지 않은 가정 3가지") | `realized_pnl_line` 테이블과 **읽기** 경로는 만든다. `grade`는 샘플에 직접 넣는다. `position_basis` 테이블은 만들지 않는다 — 컬럼 구성이 실측에 달려 있다 |
| ETF 분해 안분 (2단계) | 구성비중 제공 형태 미합의 (안건 3·8) | `LensTransform` 인터페이스 · `DirectLens` 완성 · `LookThroughLens`는 **미확보 분기만** 구현. `ConstituentPort`(커버리지 조회)와 `ConstituentExpander`(안분) 두 인터페이스를 갈라, 이번 범위에서 후자가 **호출 불가능**함을 테스트로 고정한다 |
| 계좌 연동 · 동기화 | `collection_run` 계약·시크릿 관리 미합의 (안건 6·7) | `sync_run` 테이블을 만들지 않는다. `accounts` 뷰 행의 `last_collection`은 `CollectionStatusPort` 스텁이 `null`을 낸다. `link_state`는 `account` 테이블에서 실제로 내린다 |
| 현금흐름 (`cln_cashflow`) | 매매대금 배제 규칙 미합의 (안건 1) | `CashflowPort` 인터페이스 + `EmptyCashflowPort`. 빈 결과가 곧 "미확보 계좌"이므로 `CASHFLOW_UNCOVERED`가 정직하게 뜨고 항등식은 그대로 성립한다 |
| 종목 상세 `GET /portfolio/instruments/{id}` | `position_basis` · `cln_trade` · `corporate_action`에 의존 | 만들지 않는다. 6개 뷰 엔드포인트만 노출 |
| API 인증 | 자격증명 보관 방식이 안건 7에 걸려 있고, 단일 사용자 전제라 인증 모델이 계좌 연동과 함께 결정된다 | Spring Security를 넣지 않는다. 로컬 전용임을 README에 명시 |
| 프론트엔드 | 담당자 미정 | — |

**`LOOK_THROUGH` 스텁이 가짜가 아닌 이유.** `etf_coverage`에 행이 없으면 모든 ETF가 미확보이고, 스펙 §3.4는 그 경우 "**전개하지 않고 ETF 행을 그대로 남긴다**"고 정한다. 즉 이번 범위의 `LOOK_THROUGH`는 **스펙이 정의한 정상 경로**를 타며, 미분해 평가금액을 `CONSTITUENT_UNAVAILABLE`에 실어 사용자에게 알린다. 구현하지 않는 것은 안분 산술 하나다.

## A.10 스펙과 요청서의 차이 · 스펙 공백

계획 검토 시 확인이 필요한 것들이다. **스펙 파일은 고치지 않았다.**

| # | 항목 | 내용 | 이 계획의 처리 |
|---|---|---|---|
| 1 | 지표 수 | 요청서 "12개" vs 스펙 §6.2 표 **17개** | 17개 전부 옮겼다(§A.4.2) |
| 2 | notice 수 | 요청서 "13종" vs 스펙 §8.2 표 **16종** | 16종 전부 옮겼다(§A.5.2) |
| 3 | `PRICE_LAG_MARKET` | 시장별 가격 기준일을 담을 컬럼이 `position_line`에 **없다**. `source_as_of`는 계좌 단위라 한 계좌에 국내·미국이 섞이면 시장별로 말할 수 없다(§7.4가 이 층이 필요한 이유로 든 것과 같은 문제) | 이번 범위에서 발화하지 않는다. **1단계 설계 시 `price_as_of` 성격 컬럼 추가가 필요하다** |
| 4 | §3.7 표 vs 본문 | 본문은 "묶음이 단일 통화일 때만 병기", 표는 섹터·시장 등을 ✗로 고정. 실제로 시장=US 그룹은 단일 통화다 | 두 게이트를 모두 통과할 때만 병기 (불변식 3). 표는 `Axis.localCurrencyEligible`로, 본문은 `CurrencySet.single()`로 구현 |
| 5 | CASH 행의 `instrument_count` | `instrument_count`의 CASH 정책이 "제외"라 비중 분석의 `현금` 행은 값이 0이 된다 | **0으로 내린다**. 지표 정의를 뷰별로 예외 처리하지 않는 쪽을 택했다. 화면은 CASH 행에서 종목수를 표시하지 않으면 된다 |
| 6 | `realized-pnl` 정렬 | 스펙은 "정렬은 평가금액 내림차순 고정"이라 하는데 이 뷰에 평가금액이 없다 | `last_sold_at` 내림차순 + `key` 오름차순으로 확정(§A.6.2) |
| 7 | `CONSTITUENT_AS_OF` | §9.3은 "렌즈 적용 응답은 함께 싣는다"고 하나, 전개된 ETF가 0이면 실을 날짜가 없다 | 전개 ETF가 0이면 **생략**한다 |
| 8 | 봉투 `as_of` 출처 | 어느 값에서 오는지 스펙에 없다 | §A.5.1의 규칙으로 확정 |
| 9 | 기간 기준 시각 | `THIS_MONTH` 등의 기준이 벽시계인지 최신 `as_of`인지 스펙에 없다 | **최신 `as_of`** 기준. 벽시계를 쓰면 테스트가 날짜에 따라 깨지고, 스냅샷이 없는 날의 "이번 달"이 빈 응답이 된다 |
| 10 | 종목별 뷰의 **현재가** | §2.5 컬럼 목록에 있으나 §6.2 지표 17개에 없고 `position_line`에도 컬럼이 없다 | 지표로 두지 않는다. `market_value_local ÷ quantity`로 클라이언트가 얻거나 종목 상세(범위 밖)가 제공한다. §2.5 자신이 "현재가·매입금액은 종목 상세로 미룬다"고 하므로 이 처리가 스펙과 어긋나지 않는다 |
| 11 | 종목별 뷰의 **시장 배지** | §2.5가 행에 시장 배지를 요구하는데 §6.3은 `rowFields`가 `accounts` 뷰에만 있다고 한다 | `positions`의 `rowFields`에 `market`을 넣는다(§A.4.3). 축이 아니라 표시용 행 필드이며 집계에 참여하지 않는다 |

---

# Part B — 파일 구조

책임 단위로 나눈다. 계층으로 나누지 않는다 — 함께 바뀌는 것이 함께 있어야 한다.

```
back-end/
├── build.gradle.kts · settings.gradle.kts · gradle/wrapper/
├── docker-compose.yml · Dockerfile · .env.example
├── README.md
├── docs/decisions.md                     빌드·마이그레이션·데이터 접근·집계 위치 결정 기록
└── src
    ├── main/java/com/stockproject/portfolio/
    │   ├── PortfolioApplication.java
    │   ├── catalog/                      코드 상수. DB 아님 (§6)
    │   │   ├── AxisKey.java              enum 8개 + keyOf(Line) 폴백 규칙
    │   │   ├── MetricKey.java            enum 17개
    │   │   ├── Metric.java               record + Additivity·CashScope·LensSafety·MetricScope
    │   │   ├── Lens.java · LensPolicy.java
    │   │   ├── ViewKey.java · ViewSpec.java · SubBlockSpec.java
    │   │   └── Catalog.java              축·지표·뷰 테이블 + 조회 + 요청 대조
    │   ├── domain/
    │   │   ├── Line.java                 축이 붙은 조회 라인 (§3.6 3단계 산출물)
    │   │   ├── AssetClass · Market · CurrencyCode · AccountType · LinkState · Grade
    │   │   ├── measure/
    │   │   │   ├── Measures.java         가산 측정값만. 비율 필드 없음 (불변식 1)
    │   │   │   ├── MeasureBundle.java    securities/cash 2슬롯 + CurrencySet (불변식 2·3)
    │   │   │   ├── CurrencySet.java
    │   │   │   └── LocalMoney.java
    │   │   ├── group/
    │   │   │   ├── AggregationEngine.java
    │   │   │   ├── Aggregation.java      + weightDenominator() — TotalAssetsKrw 유일 생성처
    │   │   │   ├── TotalAssetsKrw.java   package-private 생성자
    │   │   │   ├── GroupKey.java · GroupNode.java
    │   │   │   └── Derived.java          파생 지표 계산 유일 지점
    │   │   └── lens/
    │   │       ├── LensTransform.java · DirectLens.java · LookThroughLens.java
    │   │       ├── ConstituentPort.java · ConstituentCoverage.java
    │   │       ├── ConstituentExpander.java   2단계 자리 — 이번 범위에서 호출 불가
    │   │       ├── NoConstituentDataPort.java
    │   │       └── LensResult.java        전개 라인 + 미분해 ETF 집계
    │   ├── validation/
    │   │   ├── PositionLineInvariants.java · LensOutputInvariants.java
    │   │   ├── FactInvariantViolation.java
    │   │   └── RequestValidator.java     카탈로그 대조 (§9.3)
    │   ├── query/
    │   │   ├── PositionLineRepository.java · LineFilter.java
    │   │   ├── SnapshotCalendarRepository.java   as_of 목록·직전·기간 경계
    │   │   ├── AccountRepository.java
    │   │   ├── RealizedPnlRepository.java
    │   │   ├── CashflowPort.java · EmptyCashflowPort.java
    │   │   └── CollectionStatusPort.java · NoCollectionStatusPort.java
    │   ├── view/
    │   │   ├── SnapshotViewService.java · RealizedPnlViewService.java
    │   │   ├── AssetChangeViewService.java
    │   │   ├── PeriodResolver.java
    │   │   └── assembly/
    │   │       ├── SnapshotResponseAssembler.java
    │   │       ├── RowValuePolicy.java          scope·lensSafe·CASH null 처리
    │   │       ├── CurrencyDisplayPolicy.java   불변식 3
    │   │       ├── NoticeCollector.java         16종
    │   │       └── EmptyReasonResolver.java     5값 + 판정 순서
    │   └── api/
    │       ├── ViewController.java · CatalogController.java
    │       ├── ApiExceptionHandler.java
    │       └── dto/ Envelope · NoticeDto · SnapshotViewData · RowDto
    │                RealizedPnlData · AssetChangeData · CatalogDto
    └── main/resources/
        ├── application.yaml · application-local.yaml
        ├── db/migration/     V1__account.sql · V2__position_line.sql · V3__realized_pnl_line.sql
        ├── db/external/      V900__instrument_mirror.sql   데이터팀 소유 미러 — local/test 전용
        └── db/sample/        sample_portfolio.sql
    └── test/java/com/stockproject/portfolio/
        ├── ArchitectureRulesTest.java     불변식 1·BigDecimal·계층 접근
        ├── MigrationLintTest.java         비율 컬럼 금지 (§9.2)
        ├── catalog/CatalogInvariantTest.java
        ├── domain/…                       가산성·총합 보존·분모·통화 단위 테스트
        ├── query/…                        Testcondtainers 저장소 테스트
        └── api/SixViewGoldenTest.java     도달점 검증
    └── test/resources/golden/*.json
```

---

# Part C — 샘플 데이터와 기대 응답 (도달점의 정의)

`db/sample/sample_portfolio.sql`이 만드는 세계다. 태스크 11의 골든 테스트가 이 표를 그대로 검증한다.

## C.1 계좌 4개

| account_id 끝자리 | broker | label | type | source | link_state |
|---|---|---|---|---|---|
| `…0001` | 한국투자증권 | 한국투자 위탁 | GENERAL | KIS | CONNECTED |
| `…0002` | 삼성증권 | 삼성증권 | GENERAL | CODEF | CONNECTED |
| `…0003` | 한국투자증권 | 한국투자 IRP | PENSION | KIS | CONNECTED |
| `…0004` | 미래에셋증권 | 미래에셋 연금 | PENSION | CODEF | CONNECTED |

UUID는 `20000000-0000-0000-0000-00000000000N` 꼴.

## C.2 종목 8개

| instrument_id 끝자리 | symbol | name | asset_class | market | currency | sector |
|---|---|---|---|---|---|---|
| `…0001` | 005930 | 삼성전자 | STOCK | KR | KRW | 반도체 |
| `…0002` | 000660 | SK하이닉스 | STOCK | KR | KRW | 반도체 |
| `…0003` | 035420 | NAVER | STOCK | KR | KRW | 소프트웨어 |
| `…0004` | AAPL | 애플 | STOCK | US | USD | IT서비스 |
| `…0005` | MSFT | 마이크로소프트 | STOCK | US | USD | 소프트웨어 |
| `…0006` | 133690 | TIGER 미국나스닥100 | ETF | KR | KRW | **null** → `미분류` |
| `…0007` | CASH-KRW | KRW 예수금 | CASH | KR | KRW | null → `현금` |
| `…0008` | CASH-USD | USD 예수금 | CASH | US | USD | null → `현금` |

UUID는 `10000000-0000-0000-0000-00000000000N` 꼴.

## C.3 `position_line` — `as_of = 2026-07-27` (10행)

USD 라인의 `fx_rate = 1400.000000`.

| 계좌 | 종목 | qty | cost_local | mv_local | cost_krw | mv_krw | fx_as_of | 이월 |
|---|---|---|---|---|---|---|---|---|
| 한국투자 위탁 | 005930 | 200 | 12,000,000 | 14,240,000 | 12,000,000 | 14,240,000 | 07-27 | – |
| 한국투자 위탁 | 000660 | 50 | 8,000,000 | 9,000,000 | 8,000,000 | 9,000,000 | 07-27 | – |
| 한국투자 위탁 | AAPL | 20 | 4,000.00 | 4,400.00 | 5,600,000 | 6,160,000 | 07-27 | – |
| 한국투자 위탁 | CASH-KRW | 2,560,000 | 2,560,000 | 2,560,000 | 2,560,000 | 2,560,000 | 07-27 | – |
| 삼성증권 | 035420 | 40 | 9,000,000 | 8,000,000 | 9,000,000 | 8,000,000 | 07-27 | – |
| 삼성증권 | CASH-KRW | 1,000,000 | 1,000,000 | 1,000,000 | 1,000,000 | 1,000,000 | 07-27 | – |
| 한국투자 IRP | 133690 | 100 | 10,000,000 | 11,000,000 | 10,000,000 | 11,000,000 | 07-27 | – |
| 한국투자 IRP | CASH-KRW | 1,000,000 | 1,000,000 | 1,000,000 | 1,000,000 | 1,000,000 | 07-27 | – |
| 미래에셋 연금 | MSFT | 10 | 3,000.00 | 3,500.00 | 4,200,000 | 4,900,000 | **07-24** | **✔** |
| 미래에셋 연금 | CASH-USD | 100 | 100.00 | 100.00 | 140,000 | 140,000 | **07-24** | **✔** |

`source_as_of` — 이월이 아닌 라인은 `2026-07-27T15:30:00+09:00`, 미래에셋 연금 2행은 `2026-07-24T15:30:00+09:00`. `is_final = false`.

**`as_of = 2026-07-24` 스냅샷**: 위와 같은 10행을 그대로 복제하고 **삼성전자 `mv_local`·`mv_krw`만 13,040,000**으로 바꾼다. 이월 플래그는 전부 `false`, `source_as_of`는 `2026-07-24T15:30:00+09:00`, `is_final = true`. → 총자산 56,800,000.

**이 데이터가 노리는 것**

| 노림 | 실현 |
|---|---|
| 손실 종목 | NAVER (매입 9,000,000 → 평가 8,000,000) |
| 외화 병기 | AAPL(USD) · MSFT(USD) · CASH-USD |
| 캐리포워드 → `STALE_ACCOUNTS` | 미래에셋 연금 2행 |
| 환율 폴백 → `FX_APPLIED.oldest` | 미래에셋 연금의 `fx_as_of = 2026-07-24` |
| `미분류` 폴백 | TIGER(sector null) |
| `현금` 폴백 · CASH 손익 null | CASH-KRW · CASH-USD |
| 미확보 ETF → `CONSTITUENT_UNAVAILABLE` | TIGER 1종, 미분해 11,000,000 |
| 일간 변화 | 07-24 대비 +1,200,000 |
| 2단계 중첩 소계 | 계좌유형 2 × 계좌 2 |

## C.4 `realized_pnl_line` — 3행

| trade_id | 계좌 | 종목 | sold_at | qty | sell_krw | cost_basis_krw | fee_tax | pnl_krw | grade |
|---|---|---|---|---|---|---|---|---|---|
| `T-0001` | 한국투자 위탁 | 005930 | 2026-03-02 | 3 | 400,000 | 320,000 | 1,000 | 79,000 | SEEDED |
| `T-0002` | 한국투자 위탁 | 005930 | 2026-05-12 | 5 | 700,000 | 500,000 | 2,000 | 198,000 | VERIFIED |
| `T-0003` | 삼성증권 | 035420 | 2026-02-18 | 10 | 2,000,000 | 2,300,000 | 5,000 | −305,000 | VERIFIED |

`*_local`은 KRW 종목이라 `*_krw`와 같은 값.

## C.5 기대 응답 — `GET /portfolio/views/summary`

```json
{ "as_of": "2026-07-27T15:30:00+09:00",
  "empty_reason": null,
  "data": {
    "group_by": [], "lens": "DIRECT",
    "total": { "total_assets_krw": 58000000, "securities_value_krw": 53300000,
               "deposit_krw": 4700000, "cost_amount_krw": 48800000,
               "unrealized_pnl_krw": 4500000, "unrealized_pnl_pct": 9.2,
               "cash_ratio_pct": 8.1, "daily_change_krw": 1200000,
               "daily_change_pct": 2.1, "account_count": 4, "instrument_count": 5 },
    "rows": [],
    "mini_chart": { "group_by": ["market"], "lens": "DIRECT",
      "rows": [ { "key": "KR", "label": "국내", "market_value_krw": 46800000, "weight_pct": 80.7 },
                { "key": "US", "label": "미국", "market_value_krw": 11200000, "weight_pct": 19.3 } ] } },
  "notices": [
    { "code": "FX_APPLIED", "severity": "info", "message": "USD/KRW 1,400.00 적용 · 기준 2026-07-24",
      "params": { "rates": [ { "pair": "USD/KRW", "rate": 1400.0, "fx_as_of": "2026-07-24" } ],
                  "oldest_fx_as_of": "2026-07-24" } },
    { "code": "STALE_ACCOUNTS", "severity": "warn", "message": "1개 계좌가 07-24 기준입니다",
      "params": { "count": 1, "oldest": "2026-07-24" } } ] }
```

미니차트 검산 — `KR = 14,240,000 + 9,000,000 + 8,000,000 + 11,000,000 + 2,560,000 + 1,000,000 + 1,000,000 = 46,800,000`,
`US = 6,160,000 + 4,900,000 + 140,000 = 11,200,000`, 합 58,000,000, 비중 80.7 / 19.3.

## C.6 기대 응답 — `GET /portfolio/views/allocation?axis=sector&lens=DIRECT`

`total`은 §C.5의 `total`에서 `daily_change_*`를 뺀 것과 같다(일간 변화는 요약 전용 지표).

| 순서 | key / label | market_value_krw | cost_amount_krw | unrealized_pnl_krw | unrealized_pnl_pct | weight_pct | instrument_count |
|---|---|---|---|---|---|---|---|
| 1 | `반도체` | 23,240,000 | 20,000,000 | 3,240,000 | 16.2 | 40.1 | 2 |
| 2 | `소프트웨어` | 12,900,000 | 13,200,000 | −300,000 | −2.3 | 22.2 | 2 |
| 3 | `미분류` | 11,000,000 | 10,000,000 | 1,000,000 | 10.0 | 19.0 | 1 |
| 4 | `IT서비스` | 6,160,000 | 5,600,000 | 560,000 | 10.0 | 10.6 | 1 |
| 5 | `현금` | 4,700,000 | **null** | **null** | **null** | 8.1 | 0 |

`Σ market_value_krw = 58,000,000 = total.total_assets_krw` ✔ · `Σ weight_pct = 100.0` ✔ · `Σ cost = 48,800,000` ✔
현지 통화 병기 없음 — 섹터 축은 `localCurrencyEligible = false`.

## C.7 기대 응답 — `GET /portfolio/views/allocation?axis=sector&lens=LOOK_THROUGH`

`total`은 §C.6과 **동일하다**(총합 보존). `rows[]`에서 `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` **세 키가 사라진다**(`null`이 아니라 부재).

추가 notices:

```json
{ "code": "CONSTITUENT_UNAVAILABLE", "severity": "warn",
  "message": "1개 ETF는 구성종목 데이터가 없어 분해하지 않았습니다 (11,000,000원)",
  "params": { "count": 1, "undecomposed_krw": 11000000 } },
{ "code": "LENS_METRICS_OMITTED", "severity": "info",
  "message": "구성종목 기준 보기에서는 매입금액·평가손익을 행에 표시할 수 없습니다",
  "params": { "metrics": ["cost_amount_krw", "unrealized_pnl_krw", "unrealized_pnl_pct"] } }
```

`CONSTITUENT_AS_OF`는 전개된 ETF가 0이라 생략한다(§A.10 #7).

## C.8 기대 응답 — `GET /portfolio/views/positions?lens=DIRECT`

| 순서 | key | label | qty | avg_cost | currency | mv_local | mv_krw | cost_krw | pnl_krw | pnl_pct | weight_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 005930 | 삼성전자 | 200 | 60,000 | – | – | 14,240,000 | 12,000,000 | 2,240,000 | 18.7 | 24.6 |
| 2 | 133690 | TIGER 미국나스닥100 | 100 | 100,000 | – | – | 11,000,000 | 10,000,000 | 1,000,000 | 10.0 | 19.0 |
| 3 | 000660 | SK하이닉스 | 50 | 160,000 | – | – | 9,000,000 | 8,000,000 | 1,000,000 | 12.5 | 15.5 |
| 4 | 035420 | NAVER | 40 | 225,000 | – | – | 8,000,000 | 9,000,000 | −1,000,000 | −11.1 | 13.8 |
| 5 | AAPL | 애플 | 20 | 200.00 | USD | 4,400.00 | 6,160,000 | 5,600,000 | 560,000 | 10.0 | 10.6 |
| 6 | MSFT | 마이크로소프트 | 10 | 300.00 | USD | 3,500.00 | 4,900,000 | 4,200,000 | 700,000 | 16.7 | 8.4 |
| 7 | CASH-KRW | KRW 예수금 | 4,560,000 | null | – | – | 4,560,000 | null | null | null | 7.9 |
| 8 | CASH-USD | USD 예수금 | 100 | null | USD | 100.00 | 140,000 | null | null | null | 0.2 |

`Σ mv_krw = 58,000,000` ✔ · `Σ weight_pct = 100.0` ✔
KRW 종목에는 `currency`·`*_local`을 싣지 않는다(원화가 곧 현지 통화 — 불변식 3).
CASH-USD 행은 CASH지만 단일 통화 USD이므로 `market_value_local`은 싣고 원가·손익만 `null`이다.

## C.9 기대 응답 — `GET /portfolio/views/accounts`

`group_by = ["account_type","account"]`, 2단계 중첩. 소계는 서버가 계산한다.

| 노드 | key / label | mv_krw | deposit_krw | cost_krw | pnl_krw | pnl_pct | weight_pct | 행 필드 |
|---|---|---|---|---|---|---|---|---|
| 1 | `GENERAL` / 일반 | 40,960,000 | 3,560,000 | 34,600,000 | 2,800,000 | 8.1 | 70.6 | – |
| 1.1 | `…0001` / 한국투자 위탁 | 31,960,000 | 2,560,000 | 25,600,000 | 3,800,000 | 14.8 | 55.1 | `link_state: CONNECTED`, `last_collection: null`, `last_synced_at: null` |
| 1.2 | `…0002` / 삼성증권 | 9,000,000 | 1,000,000 | 9,000,000 | −1,000,000 | −11.1 | 15.5 | 동일 |
| 2 | `PENSION` / 연금 | 17,040,000 | 1,140,000 | 14,200,000 | 1,700,000 | 12.0 | 29.4 | – |
| 2.1 | `…0003` / 한국투자 IRP | 12,000,000 | 1,000,000 | 10,000,000 | 1,000,000 | 10.0 | 20.7 | 동일 |
| 2.2 | `…0004` / 미래에셋 연금 | 5,040,000 | 140,000 | 4,200,000 | 700,000 | 16.7 | 8.7 | 동일 |

`Σ 최상위 mv_krw = 58,000,000` ✔ · 자식 합 = 부모 ✔ · `Σ 최상위 weight_pct = 100.0` ✔
계좌·계좌유형 축은 `localCurrencyEligible = false`이므로 병기 없음.

## C.10 기대 응답 — `GET /portfolio/views/realized-pnl?period=THIS_YEAR`

기준일은 최신 `as_of = 2026-07-27` → 기간 `2026-01-01 ~ 2026-12-31`.

```
total: realized_pnl_krw −28,000 · cost_basis_krw 3,120,000 · realized_pnl_pct −0.9
rows[0] 005930 삼성전자  sell 1,100,000 · cost 820,000 · pnl 277,000 · pct 33.8
        first_sold_at 2026-03-02 · last_sold_at 2026-05-12 · trade_count 2 · grade MIXED
        rows: T-0002(05-12, VERIFIED, 198,000) → T-0001(03-02, SEEDED, 79,000)
rows[1] 035420 NAVER     sell 2,000,000 · cost 2,300,000 · pnl −305,000 · pct −13.3
        first=last_sold_at 2026-02-18 · trade_count 1 · grade VERIFIED
notices: SEEDED_ROWS { count: 1 }
```

정렬: `last_sold_at` 내림차순 → 삼성전자(05-12) → NAVER(02-18). 체결 노드도 같은 규칙.

## C.11 기대 응답 — `GET /portfolio/views/asset-change?period=CUSTOM&from=2026-07-01&to=2026-07-31`

```json
{ "as_of": "2026-07-27T15:30:00+09:00", "empty_reason": null,
  "data": { "period": { "from": "2026-07-01", "to": "2026-07-31" },
    "opening": 56800000, "closing": 58000000,
    "deposited": 0, "earned": 1200000,
    "account_included": 0, "account_excluded": 0,
    "breakdown": [ { "type": "INVESTMENT_PNL", "amount": 1200000 } ],
    "investment_pnl": { "total": 1200000, "realized": null,
                        "unrealized_change": null, "split_available": false } },
  "notices": [
    { "code": "CASHFLOW_UNCOVERED", "severity": "warn",
      "message": "4개 계좌의 입출금 내역이 없어 투자손익에 섞여 있을 수 있어요",
      "params": { "count": 4 } },
    { "code": "PERIOD_TRUNCATED", "severity": "info",
      "message": "2026-07-24부터 계산했습니다", "params": { "actual_from": "2026-07-24" } },
    { "code": "BOUNDARY_CARRIED_FORWARD", "severity": "warn",
      "message": "기간 경계 시점에 1개 계좌가 이월값입니다",
      "params": { "count": 1, "boundary": "2026-07-27" } } ] }
```

`2026-07-01` 직전 스냅샷이 없어 가장 이른 `2026-07-24`를 기초로 대체 → `PERIOD_TRUNCATED`.
현금흐름 포트가 비어 있어 `deposited = 0`, 배당·수수료 0 → 투자손익 = Δ총자산 = 1,200,000. 값이 0인 항목은 `breakdown`에서 숨긴다.


---

# Part D — 태스크

11개 태스크. 각 태스크는 독립적으로 테스트 가능한 산출물로 끝나고 1커밋을 만든다.
의존: 1 → 2 → 3 → 4 → 5 → 6 → 7 → {8, 9, 10} → 11. 8·9·10은 서로 독립이라 병렬 가능하다.

---

### Task 1: 스캐폴딩 · Docker Compose · 마이그레이션 · 샘플 데이터

**Files:**
- Create: `back-end/settings.gradle.kts` · `back-end/build.gradle.kts` · `back-end/gradle/wrapper/*`
- Create: `back-end/docker-compose.yml` · `back-end/Dockerfile` · `back-end/.env.example`
- Create: `back-end/src/main/java/com/stockproject/portfolio/PortfolioApplication.java`
- Create: `back-end/src/main/resources/application.yaml` · `application-local.yaml`
- Create: `back-end/src/main/resources/db/migration/V1__account.sql` · `V2__position_line.sql` · `V3__realized_pnl_line.sql`
- Create: `back-end/src/main/resources/db/external/V900__instrument_mirror.sql`
- Create: `back-end/src/main/resources/db/sample/sample_portfolio.sql`
- Test: `back-end/src/test/java/com/stockproject/portfolio/MigrationLintTest.java`
- Test: `back-end/src/test/java/com/stockproject/portfolio/SchemaSmokeTest.java`
- Modify: `back-end/README.md` · `back-end/.gitignore` (Gradle·빌드 산출물 추가)

**Interfaces:**
- Produces: Flyway 마이그레이션이 만드는 테이블 3개(`account`·`position_line`·`realized_pnl_line`)와 로컬 전용 미러 `instrument`. 이후 모든 태스크의 저장소가 이 스키마를 읽는다.

**완료 조건**
1. `./gradlew build`가 통과한다.
2. `docker compose up -d db` 후 `./gradlew bootRun --args='--spring.profiles.active=local'`로 앱이 뜨고 Flyway가 4개 마이그레이션을 적용한다.
3. `psql`로 `sample_portfolio.sql`을 실행하면 `position_line` 20행(`as_of` 2개 × 10행), `realized_pnl_line` 3행, `account` 4행, `instrument` 8행이 들어간다.
4. `MigrationLintTest`가 통과한다 — 마이그레이션에 비율 컬럼이 없다.
5. `db/external`은 `local`·`test` 프로필에서만 적용되고 기본(운영) 프로필에서는 적용되지 않는다.

**검증 방법**
```bash
cd back-end
docker compose up -d db
./gradlew test --tests '*MigrationLintTest' --tests '*SchemaSmokeTest'
docker compose exec -T db psql -U portfolio -d portfolio -f /sample/sample_portfolio.sql
docker compose exec -T db psql -U portfolio -d portfolio -c \
  "SELECT as_of, count(*) FROM position_line GROUP BY 1 ORDER BY 1;"
# 기대: 2026-07-24 | 10 / 2026-07-27 | 10
docker compose exec -T db psql -U portfolio -d portfolio -c \
  "SELECT sum(market_value_krw) FROM position_line WHERE as_of='2026-07-27';"
# 기대: 58000000
```

- [ ] **Step 1: Gradle 프로젝트 생성**

`settings.gradle.kts`:
```kotlin
rootProject.name = "portfolio-api"
```

`build.gradle.kts`:
```kotlin
plugins {
    java
    id("org.springframework.boot") version "3.4.5"
    id("io.spring.dependency-management") version "1.1.7"
}

group = "com.stockproject"
version = "0.1.0"

java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }

repositories { mavenCentral() }

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-jdbc")
    implementation("org.springframework.boot:spring-boot-starter-validation")
    implementation("org.flywaydb:flyway-core")
    implementation("org.flywaydb:flyway-database-postgresql")
    runtimeOnly("org.postgresql:postgresql")

    testImplementation("org.springframework.boot:spring-boot-starter-test")
    testImplementation("org.springframework.boot:spring-boot-testcontainers")
    testImplementation("org.testcontainers:junit-jupiter")
    testImplementation("org.testcontainers:postgresql")
    testImplementation("com.tngtech.archunit:archunit-junit5:1.3.0")
}

tasks.withType<JavaCompile> { options.compilerArgs.add("-parameters") }
tasks.withType<Test> { useJUnitPlatform() }
```

`gradle wrapper --gradle-version 8.12`로 래퍼를 만든다.

- [ ] **Step 2: 애플리케이션 클래스와 설정**

`PortfolioApplication.java`:
```java
package com.stockproject.portfolio;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class PortfolioApplication {
    public static void main(String[] args) {
        SpringApplication.run(PortfolioApplication.class, args);
    }
}
```

`application.yaml` — 기본(운영) 프로필. `db/external`을 **포함하지 않는다**:
```yaml
spring:
  application:
    name: portfolio-api
  datasource:
    url: ${DB_URL:jdbc:postgresql://localhost:5432/portfolio}
    username: ${DB_USER:portfolio}
    password: ${DB_PASSWORD:portfolio}
  flyway:
    locations: classpath:db/migration
  jackson:
    property-naming-strategy: SNAKE_CASE
    default-property-inclusion: always
    serialization:
      write-dates-as-timestamps: false
server:
  port: 8080
portfolio:
  zone: Asia/Seoul
```

`application-local.yaml` — 데이터팀 소유 테이블 미러를 함께 적용:
```yaml
spring:
  flyway:
    locations: classpath:db/migration,classpath:db/external
```

- [ ] **Step 3: 마이그레이션 SQL 작성**

`V1__account.sql`:
```sql
CREATE TABLE account (
    account_id     uuid PRIMARY KEY,
    broker         text NOT NULL,
    label          text NOT NULL,
    account_type   text NOT NULL CHECK (account_type IN ('GENERAL', 'PENSION')),
    source         text NOT NULL CHECK (source IN ('KIS', 'CODEF')),
    credential_ref text,
    link_state     text NOT NULL CHECK (link_state IN
                     ('CONNECTING', 'CONNECTED', 'REAUTH_REQUIRED', 'DISCONNECTED')),
    last_synced_at timestamptz
);

COMMENT ON COLUMN account.credential_ref IS '시크릿 매니저 키만 저장한다. 자격증명 값 자체를 저장하지 않는다 — 스펙 §5.1';
COMMENT ON COLUMN account.label IS '표시명. broker와 다르다 — 같은 기관에 위탁·IRP가 함께 있다';
```

`V2__position_line.sql`:
```sql
CREATE TABLE position_line (
    as_of              date           NOT NULL,
    account_id         uuid           NOT NULL REFERENCES account (account_id),
    instrument_id      uuid           NOT NULL,
    quantity           numeric(20, 8) NOT NULL,
    cost_amount_local  numeric(20, 4) NOT NULL,
    market_value_local numeric(20, 4) NOT NULL,
    cost_amount_krw    numeric(20, 0) NOT NULL,
    market_value_krw   numeric(20, 0) NOT NULL,
    fx_rate            numeric(18, 6) NOT NULL,
    fx_as_of           date           NOT NULL,
    source_as_of       timestamptz    NOT NULL,
    is_carried_forward boolean        NOT NULL DEFAULT false,
    is_final           boolean        NOT NULL DEFAULT false,
    PRIMARY KEY (as_of, account_id, instrument_id)
);

CREATE INDEX idx_position_line_account_as_of ON position_line (account_id, as_of);

COMMENT ON TABLE position_line IS
  '보유 스냅샷. 그레인 (as_of, account_id, instrument_id). 비율(수익률·비중) 컬럼을 두지 않는다 — 스펙 §1.5 · §9.2';
COMMENT ON COLUMN position_line.cost_amount_local IS
  '잔고 평단 기준(cln_balance.avg_price × quantity). position_basis를 참조하지 않는다 — 스펙 §4.1';
COMMENT ON COLUMN position_line.instrument_id IS
  '데이터팀 소유 instrument 참조. 배포 순서를 묶지 않기 위해 FK를 걸지 않는다';
```

`fx_rate`·`fx_as_of`를 `NOT NULL`로 둔 것이 §9.1의 "`market_value_krw`가 있으면 `fx_rate`·`fx_as_of` 필수"를 스키마로 표현한 것이다. 세 컬럼 모두 `NOT NULL`이므로 규칙이 구조적으로 성립한다.

`V3__realized_pnl_line.sql`:
```sql
CREATE TABLE realized_pnl_line (
    trade_id           text           PRIMARY KEY,
    account_id         uuid           NOT NULL REFERENCES account (account_id),
    instrument_id      uuid           NOT NULL,
    sold_at            timestamptz    NOT NULL,
    quantity           numeric(20, 8) NOT NULL,
    sell_amount_local  numeric(20, 4) NOT NULL,
    cost_basis_local   numeric(20, 4) NOT NULL,
    sell_amount_krw    numeric(20, 0) NOT NULL,
    cost_basis_krw     numeric(20, 0) NOT NULL,
    fee_tax            numeric(20, 4) NOT NULL,
    realized_pnl_local numeric(20, 4) NOT NULL,
    realized_pnl_krw   numeric(20, 0) NOT NULL,
    grade              text           NOT NULL CHECK (grade IN
                         ('VERIFIED', 'SEEDED', 'UNAVAILABLE', 'CONFLICT'))
);

CREATE INDEX idx_realized_pnl_line_sold_at ON realized_pnl_line (sold_at);
CREATE INDEX idx_realized_pnl_line_account_sold_at ON realized_pnl_line (account_id, sold_at);

COMMENT ON TABLE realized_pnl_line IS
  '매도 체결 1건 = 1행. trade_id upsert로만 생성한다(insert-only 금지) — 스펙 §9.1';
COMMENT ON COLUMN realized_pnl_line.grade IS
  '산출 시점 position_basis 등급의 스냅샷. 이후 갱신하지 않는다. MIXED는 응답 조립 시에만 생기며 저장하지 않는다 — 스펙 §4.3 · §8.4';
```

`V900__instrument_mirror.sql` (`db/external/`):
```sql
-- 데이터팀 소유 테이블의 로컬·테스트 전용 미러.
-- 소유 경계는 스펙 §11.2. 운영 프로필(spring.flyway.locations=classpath:db/migration)은 이 파일을 적용하지 않는다.
CREATE TABLE IF NOT EXISTS instrument (
    instrument_id uuid PRIMARY KEY,
    isin          text,
    symbol        text NOT NULL,
    name          text NOT NULL,
    asset_class   text NOT NULL CHECK (asset_class IN ('STOCK', 'ETF', 'CASH')),
    market        text NOT NULL CHECK (market IN ('KR', 'US')),
    currency      text NOT NULL CHECK (currency IN ('KRW', 'USD')),
    sector        text,
    is_leveraged  boolean
);
```

- [ ] **Step 4: 마이그레이션 린트 테스트를 쓴다 (실패 확인)**

`MigrationLintTest.java`:
```java
package com.stockproject.portfolio;

import org.junit.jupiter.api.Test;

import java.nio.file.*;
import java.util.List;
import java.util.regex.Pattern;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

/** 스펙 §9.2 — 비율 성격 컬럼은 스키마에 존재 불가. 리뷰가 아니라 테스트로 강제한다. */
class MigrationLintTest {

    private static final List<String> FORBIDDEN =
            List.of("_pct", "_ratio", "_rate_of_return", "weight", "yield", "_percent");

    @Test
    void 마이그레이션에_비율_성격_컬럼이_없다() throws Exception {
        Path dir = Path.of("src/main/resources/db");
        try (Stream<Path> files = Files.walk(dir)) {
            List<String> offenders = files
                    .filter(p -> p.toString().endsWith(".sql"))
                    .flatMap(MigrationLintTest::columnDefinitions)
                    .filter(line -> FORBIDDEN.stream().anyMatch(line.toLowerCase()::contains))
                    .toList();
            assertThat(offenders)
                    .as("비율·수익률 컬럼은 스키마에 둘 수 없다 (스펙 §1.5 · §9.2)")
                    .isEmpty();
        }
    }

    /** COMMENT·주석 줄을 뺀 컬럼 정의 후보만 남긴다. */
    private static Stream<String> columnDefinitions(Path file) {
        try {
            return Files.readAllLines(file).stream()
                    .map(String::trim)
                    .filter(l -> !l.startsWith("--"))
                    .filter(l -> !l.toUpperCase().startsWith("COMMENT"))
                    .filter(l -> Pattern.compile("^[a-z_]+\\s+(uuid|text|date|boolean|numeric|timestamptz)")
                            .matcher(l).find())
                    .map(l -> file.getFileName() + ": " + l);
        } catch (Exception e) {
            throw new IllegalStateException(file.toString(), e);
        }
    }
}
```

Run: `./gradlew test --tests '*MigrationLintTest'` → **PASS**해야 한다(작성한 마이그레이션에 금지 컬럼이 없으므로). 검사기가 실제로 동작하는지 보려면 `V2`에 `weight_pct numeric(5,2),`를 임시로 넣고 실행해 FAIL을 확인한 뒤 되돌린다.

- [ ] **Step 5: Testcontainers 스모크 테스트**

`SchemaSmokeTest.java`:
```java
package com.stockproject.portfolio;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
@Testcontainers
class SchemaSmokeTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired JdbcClient jdbc;

    @Test
    void 마이그레이션이_테이블_네개를_만든다() {
        List<String> tables = jdbc.sql("""
                SELECT table_name FROM information_schema.tables
                 WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                 ORDER BY table_name
                """).query(String.class).list();

        assertThat(tables).contains("account", "position_line", "realized_pnl_line", "instrument");
    }

    @Test
    void position_line에_비율_컬럼이_없다() {
        List<String> columns = jdbc.sql("""
                SELECT column_name FROM information_schema.columns
                 WHERE table_name = 'position_line'
                """).query(String.class).list();

        assertThat(columns).noneMatch(c -> c.contains("pct") || c.contains("ratio") || c.contains("weight"));
    }
}
```

`src/test/resources/application-test.yaml`:
```yaml
spring:
  flyway:
    locations: classpath:db/migration,classpath:db/external
```

Run: `./gradlew test --tests '*SchemaSmokeTest'` → PASS.

- [ ] **Step 6: Docker Compose와 Dockerfile**

`docker-compose.yml`:
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: portfolio
      POSTGRES_USER: portfolio
      POSTGRES_PASSWORD: portfolio
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./src/main/resources/db/sample:/sample:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U portfolio -d portfolio"]
      interval: 3s
      retries: 20

  api:
    build: .
    depends_on:
      db: { condition: service_healthy }
    environment:
      SPRING_PROFILES_ACTIVE: local
      DB_URL: jdbc:postgresql://db:5432/portfolio
      DB_USER: portfolio
      DB_PASSWORD: portfolio
    ports: ["8080:8080"]

volumes:
  pgdata:
```

`Dockerfile`:
```dockerfile
FROM gradle:8.12-jdk21 AS build
WORKDIR /src
COPY . .
RUN gradle bootJar --no-daemon

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /src/build/libs/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
```

`.env.example`:
```
DB_URL=jdbc:postgresql://localhost:5432/portfolio
DB_USER=portfolio
DB_PASSWORD=portfolio
```

- [ ] **Step 7: 샘플 데이터 SQL** (§C의 표를 그대로 옮긴다)

`db/sample/sample_portfolio.sql`:
```sql
BEGIN;

TRUNCATE realized_pnl_line, position_line, account, instrument;

INSERT INTO instrument (instrument_id, isin, symbol, name, asset_class, market, currency, sector, is_leveraged) VALUES
 ('10000000-0000-0000-0000-000000000001','KR7005930003','005930','삼성전자','STOCK','KR','KRW','반도체',false),
 ('10000000-0000-0000-0000-000000000002','KR7000660001','000660','SK하이닉스','STOCK','KR','KRW','반도체',false),
 ('10000000-0000-0000-0000-000000000003','KR7035420009','035420','NAVER','STOCK','KR','KRW','소프트웨어',false),
 ('10000000-0000-0000-0000-000000000004','US0378331005','AAPL','애플','STOCK','US','USD','IT서비스',false),
 ('10000000-0000-0000-0000-000000000005','US5949181045','MSFT','마이크로소프트','STOCK','US','USD','소프트웨어',false),
 ('10000000-0000-0000-0000-000000000006','KR7133690008','133690','TIGER 미국나스닥100','ETF','KR','KRW',NULL,false),
 ('10000000-0000-0000-0000-000000000007',NULL,'CASH-KRW','KRW 예수금','CASH','KR','KRW',NULL,NULL),
 ('10000000-0000-0000-0000-000000000008',NULL,'CASH-USD','USD 예수금','CASH','US','USD',NULL,NULL);

INSERT INTO account (account_id, broker, label, account_type, source, credential_ref, link_state, last_synced_at) VALUES
 ('20000000-0000-0000-0000-000000000001','한국투자증권','한국투자 위탁','GENERAL','KIS',NULL,'CONNECTED',NULL),
 ('20000000-0000-0000-0000-000000000002','삼성증권','삼성증권','GENERAL','CODEF',NULL,'CONNECTED',NULL),
 ('20000000-0000-0000-0000-000000000003','한국투자증권','한국투자 IRP','PENSION','KIS',NULL,'CONNECTED',NULL),
 ('20000000-0000-0000-0000-000000000004','미래에셋증권','미래에셋 연금','PENSION','CODEF',NULL,'CONNECTED',NULL);

-- as_of 2026-07-27 (확정 전, is_final = false)
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final) VALUES
 ('2026-07-27','20000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001',200,
   12000000,14240000,12000000,14240000,1,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 ('2026-07-27','20000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000002',50,
   8000000,9000000,8000000,9000000,1,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 ('2026-07-27','20000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000004',20,
   4000,4400,5600000,6160000,1400,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 ('2026-07-27','20000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000007',2560000,
   2560000,2560000,2560000,2560000,1,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 ('2026-07-27','20000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000003',40,
   9000000,8000000,9000000,8000000,1,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 ('2026-07-27','20000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000007',1000000,
   1000000,1000000,1000000,1000000,1,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 ('2026-07-27','20000000-0000-0000-0000-000000000003','10000000-0000-0000-0000-000000000006',100,
   10000000,11000000,10000000,11000000,1,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 ('2026-07-27','20000000-0000-0000-0000-000000000003','10000000-0000-0000-0000-000000000007',1000000,
   1000000,1000000,1000000,1000000,1,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 -- 미래에셋 연금: 수집 실패 → 직전 성공 스냅샷 이월 (스펙 §7.3)
 ('2026-07-27','20000000-0000-0000-0000-000000000004','10000000-0000-0000-0000-000000000005',10,
   3000,3500,4200000,4900000,1400,'2026-07-24','2026-07-24T15:30:00+09',true,false),
 ('2026-07-27','20000000-0000-0000-0000-000000000004','10000000-0000-0000-0000-000000000008',100,
   100,100,140000,140000,1400,'2026-07-24','2026-07-24T15:30:00+09',true,false);

-- as_of 2026-07-24 (EOD 확정). 삼성전자 평가금액만 다르다 → 일간 변화 +1,200,000
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT '2026-07-24', account_id, instrument_id, quantity,
       cost_amount_local,
       CASE WHEN instrument_id = '10000000-0000-0000-0000-000000000001'
            THEN 13040000 ELSE market_value_local END,
       cost_amount_krw,
       CASE WHEN instrument_id = '10000000-0000-0000-0000-000000000001'
            THEN 13040000 ELSE market_value_krw END,
       fx_rate, '2026-07-24', '2026-07-24T15:30:00+09', false, true
  FROM position_line WHERE as_of = '2026-07-27';

INSERT INTO realized_pnl_line (trade_id, account_id, instrument_id, sold_at, quantity,
    sell_amount_local, cost_basis_local, sell_amount_krw, cost_basis_krw,
    fee_tax, realized_pnl_local, realized_pnl_krw, grade) VALUES
 ('T-0001','20000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001',
   '2026-03-02T09:31:00+09',3,400000,320000,400000,320000,1000,79000,79000,'SEEDED'),
 ('T-0002','20000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001',
   '2026-05-12T10:02:00+09',5,700000,500000,700000,500000,2000,198000,198000,'VERIFIED'),
 ('T-0003','20000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000003',
   '2026-02-18T13:44:00+09',10,2000000,2300000,2000000,2300000,5000,-305000,-305000,'VERIFIED');

COMMIT;
```

- [ ] **Step 8: 검증 명령을 실행하고 결과를 확인한다**

위 **검증 방법**의 네 명령을 순서대로 돌려 기대값과 일치하는지 본다.

- [ ] **Step 9: README와 커밋**

`README.md`에 실행 방법(위 검증 명령), 스택, **인증이 없고 로컬 전용이라는 사실**, 소유 테이블 경계(`db/external`은 데이터팀 소유 미러라 운영에서 적용하지 않는다)를 적는다.

```bash
git add -A
git commit -m "feat: 조회 계층 스캐폴딩 · 마이그레이션 · 샘플 데이터"
```

---

### Task 2: 카탈로그 상수 (축 8 · 지표 17 · 뷰 6)

**Files:**
- Create: `catalog/AxisKey.java` · `MetricKey.java` · `Metric.java` · `Lens.java` · `LensPolicy.java` · `ViewKey.java` · `ViewSpec.java` · `SubBlockSpec.java` · `Catalog.java`
- Create: `catalog/Additivity.java` · `CashScope.java` · `LensSafety.java` · `MetricScope.java`
- Test: `test/.../catalog/CatalogInvariantTest.java`

**Interfaces:**
- Produces: `Catalog.axes()` · `Catalog.metrics()` · `Catalog.views()` · `Catalog.view(ViewKey)` · `Catalog.axis(String)` · `Catalog.allowedFilters(ViewKey, Lens)` · `Catalog.rowMetrics(ViewKey, Lens)` · `Catalog.totalMetrics(ViewKey)`. Task 3 이후 모든 태스크가 여기서 규칙을 읽는다.
- `AxisKey.keyOf(Line)`는 Task 3에서 `Line`이 생긴 뒤 채운다. 이 태스크에서는 `AxisKey`에 `label`·`lensSensitive`·`enabled`·`localCurrencyEligible`·`applicableViews`만 둔다.

**완료 조건**
1. §A.4의 세 표가 코드 상수로 1:1 존재한다 — 축 8개, 지표 17개, 뷰 6개.
2. `CatalogInvariantTest`가 통과한다 — 불변식 4(행/합계 키 비충돌), `lensSensitive` 축이 `LOOK_THROUGH` 필터 목록에서 빠짐, 비활성 축이 어떤 뷰의 기본 축도 아님.
3. 지표 카탈로그의 `cashIncluded` 플래그와 §A.4.2 표가 일치한다.

**검증 방법**
```bash
./gradlew test --tests '*CatalogInvariantTest'
```

- [ ] **Step 1: 열거 타입들**

```java
package com.stockproject.portfolio.catalog;

public enum Lens { DIRECT, LOOK_THROUGH }

public enum LensPolicy { NONE, OPTIONAL, ALWAYS }

/** 스펙 §6.2 — 가산 가능 여부. false면 라인 단위 합산 금지, 집계 후에만 계산한다. */
public enum Additivity { ADDITIVE, NON_ADDITIVE }

/** 스펙 §6.2 — 예수금 의사종목을 집계에 포함하는가. */
public enum CashScope { INCLUDED, EXCLUDED, DENOMINATOR_ONLY }

/** 스펙 §6.2 — LOOK_THROUGH에서의 유효 범위. */
public enum LensSafety { ROW_AND_TOTAL, TOTAL_ONLY, NEVER, NOT_APPLICABLE }

/** 불변식 4 — 행 키와 합계 키는 이름이 겹치지 않는다. */
public enum MetricScope { ROW, TOTAL, BOTH }

public enum ViewKey {
    SUMMARY("summary"), POSITIONS("positions"), ALLOCATION("allocation"),
    ACCOUNTS("accounts"), REALIZED_PNL("realized-pnl"), ASSET_CHANGE("asset-change");

    private final String key;
    ViewKey(String key) { this.key = key; }
    public String key() { return key; }

    public static ViewKey of(String key) {
        for (ViewKey v : values()) if (v.key.equals(key)) return v;
        throw new IllegalArgumentException("UNKNOWN_VIEW: " + key);
    }
}
```

- [ ] **Step 2: 축 8개** (§A.4.1)

```java
package com.stockproject.portfolio.catalog;

import java.util.Set;

public enum AxisKey {
    ACCOUNT      ("account",      "계좌",     false, true,  false, Set.of(ViewKey.ACCOUNTS)),
    ACCOUNT_TYPE ("account_type", "계좌유형", false, true,  false, Set.of(ViewKey.ACCOUNTS)),
    INSTRUMENT   ("instrument",   "종목",     true,  true,  true,  Set.of(ViewKey.POSITIONS, ViewKey.ALLOCATION)),
    SECTOR       ("sector",       "섹터",     true,  true,  false, Set.of(ViewKey.ALLOCATION)),
    MARKET       ("market",       "시장",     true,  true,  false, Set.of(ViewKey.ALLOCATION, ViewKey.SUMMARY)),
    CURRENCY     ("currency",     "통화",     true,  true,  true,  Set.of(ViewKey.ALLOCATION)),
    ASSET_CLASS  ("asset_class",  "자산군",   true,  true,  false, Set.of(ViewKey.ALLOCATION, ViewKey.SUMMARY)),
    /** 원천 미확보로 비활성. 요청 시 AXIS_DISABLED로 거부한다 — 스펙 §6.1 · §9.3 */
    IS_LEVERAGED ("is_leveraged", "레버리지", true,  false, false, Set.of(ViewKey.ALLOCATION));

    private final String key;
    private final String label;
    private final boolean lensSensitive;
    private final boolean enabled;
    private final boolean localCurrencyEligible;
    private final Set<ViewKey> applicableViews;

    AxisKey(String key, String label, boolean lensSensitive, boolean enabled,
            boolean localCurrencyEligible, Set<ViewKey> applicableViews) {
        this.key = key; this.label = label; this.lensSensitive = lensSensitive;
        this.enabled = enabled; this.localCurrencyEligible = localCurrencyEligible;
        this.applicableViews = applicableViews;
    }

    public String key() { return key; }
    public String label() { return label; }
    /** true면 LOOK_THROUGH에서 이 축으로 필터할 수 없다 — 전개가 종목 자체를 바꾼다(스펙 §9.3). */
    public boolean lensSensitive() { return lensSensitive; }
    public boolean enabled() { return enabled; }
    /** 스펙 §3.7 표 — 이 축의 그룹에 현지 통화를 병기할 수 있는가. */
    public boolean localCurrencyEligible() { return localCurrencyEligible; }
    public Set<ViewKey> applicableViews() { return applicableViews; }

    public static AxisKey of(String key) {
        for (AxisKey a : values()) if (a.key.equals(key)) return a;
        throw new IllegalArgumentException("UNKNOWN_AXIS: " + key);
    }
}
```

- [ ] **Step 3: 지표 17개** (§A.4.2)

```java
package com.stockproject.portfolio.catalog;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

public record Metric(MetricKey key, String label, Additivity additivity,
                     CashScope cashScope, LensSafety lensSafety, MetricScope scope,
                     String formula) {

    private static final List<Metric> ALL = List.of(
      m(MetricKey.QUANTITY,             "수량",            Additivity.ADDITIVE,     CashScope.INCLUDED,          LensSafety.ROW_AND_TOTAL,   MetricScope.ROW,   "Σ 수량"),
      m(MetricKey.TOTAL_ASSETS_KRW,     "총자산",          Additivity.ADDITIVE,     CashScope.INCLUDED,          LensSafety.ROW_AND_TOTAL,   MetricScope.TOTAL, "Σ 평가금액 (예수금 포함)"),
      m(MetricKey.SECURITIES_VALUE_KRW, "유가증권 평가금액", Additivity.ADDITIVE,     CashScope.EXCLUDED,          LensSafety.ROW_AND_TOTAL,   MetricScope.TOTAL, "Σ 평가금액 (예수금 제외)"),
      m(MetricKey.MARKET_VALUE_KRW,     "평가금액",        Additivity.ADDITIVE,     CashScope.INCLUDED,          LensSafety.ROW_AND_TOTAL,   MetricScope.ROW,   "그 행의 평가금액"),
      m(MetricKey.DEPOSIT_KRW,          "예수금",          Additivity.ADDITIVE,     CashScope.INCLUDED,          LensSafety.ROW_AND_TOTAL,   MetricScope.BOTH,  "Σ CASH 평가금액"),
      m(MetricKey.DAILY_CHANGE_KRW,     "일간 변화",       Additivity.ADDITIVE,     CashScope.INCLUDED,          LensSafety.NOT_APPLICABLE,  MetricScope.TOTAL, "당일 − 직전 as_of의 total_assets_krw"),
      m(MetricKey.DAILY_CHANGE_PCT,     "일간 변화율",     Additivity.NON_ADDITIVE, CashScope.INCLUDED,          LensSafety.NOT_APPLICABLE,  MetricScope.TOTAL, "daily_change_krw ÷ 직전 as_of의 total_assets_krw"),
      m(MetricKey.COST_AMOUNT_KRW,      "매입금액",        Additivity.ADDITIVE,     CashScope.EXCLUDED,          LensSafety.TOTAL_ONLY,      MetricScope.BOTH,  "Σ 매입금액 (예수금 제외)"),
      m(MetricKey.UNREALIZED_PNL_KRW,   "평가손익",        Additivity.ADDITIVE,     CashScope.EXCLUDED,          LensSafety.TOTAL_ONLY,      MetricScope.BOTH,  "Σ평가 − Σ매입 (예수금 제외)"),
      m(MetricKey.UNREALIZED_PNL_PCT,   "평가손익률",      Additivity.NON_ADDITIVE, CashScope.EXCLUDED,          LensSafety.TOTAL_ONLY,      MetricScope.BOTH,  "평가손익 ÷ Σ매입"),
      m(MetricKey.AVG_COST,             "평단",            Additivity.NON_ADDITIVE, CashScope.EXCLUDED,          LensSafety.NEVER,           MetricScope.ROW,   "Σ매입 ÷ Σ수량 (잔고 기준)"),
      m(MetricKey.WEIGHT_PCT,           "비중",            Additivity.NON_ADDITIVE, CashScope.DENOMINATOR_ONLY,  LensSafety.ROW_AND_TOTAL,   MetricScope.ROW,   "행 평가금액 ÷ total_assets_krw"),
      m(MetricKey.CASH_RATIO_PCT,       "현금비중",        Additivity.NON_ADDITIVE, CashScope.DENOMINATOR_ONLY,  LensSafety.ROW_AND_TOTAL,   MetricScope.TOTAL, "CASH 평가 ÷ total_assets_krw"),
      m(MetricKey.INSTRUMENT_COUNT,     "종목수",          Additivity.NON_ADDITIVE, CashScope.EXCLUDED,          LensSafety.ROW_AND_TOTAL,   MetricScope.BOTH,  "COUNT DISTINCT 종목 (CASH 제외)"),
      m(MetricKey.ACCOUNT_COUNT,        "계좌수",          Additivity.NON_ADDITIVE, CashScope.INCLUDED,          LensSafety.NOT_APPLICABLE,  MetricScope.TOTAL, "COUNT DISTINCT 계좌"),
      m(MetricKey.REALIZED_PNL_KRW,     "실현손익",        Additivity.ADDITIVE,     CashScope.EXCLUDED,          LensSafety.NEVER,           MetricScope.BOTH,  "Σ 실현손익"),
      m(MetricKey.REALIZED_PNL_PCT,     "실현손익률",      Additivity.NON_ADDITIVE, CashScope.EXCLUDED,          LensSafety.NEVER,           MetricScope.BOTH,  "Σ실현손익 ÷ Σ취득원가")
    );

    private static final Map<MetricKey, Metric> BY_KEY =
            ALL.stream().collect(Collectors.toMap(Metric::key, Function.identity()));

    private static Metric m(MetricKey k, String label, Additivity a, CashScope c,
                            LensSafety l, MetricScope s, String formula) {
        return new Metric(k, label, a, c, l, s, formula);
    }

    public static List<Metric> all() { return ALL; }
    public static Metric of(MetricKey key) { return BY_KEY.get(key); }
}
```

`MetricKey`는 위 17개 이름을 그대로 갖는 enum이고, `key()`는 snake_case 문자열(`total_assets_krw` 등)을 낸다.

`DEPOSIT_KRW`의 `scope`가 `BOTH`인 이유는 §A.4.3의 각주 — `accounts` 뷰가 예수금을 행에도 싣고 의미가 같기 때문이다.

- [ ] **Step 4: 뷰 6개** (§A.4.3)

`ViewSpec`:
```java
public record ViewSpec(ViewKey key, String question, String grain,
                       List<AxisKey> groupBy, List<AxisKey> axisOptions,
                       List<MetricKey> metrics, List<String> rowFields,
                       Map<Lens, List<AxisKey>> filters,
                       LensPolicy lensPolicy, List<SubBlockSpec> subBlocks,
                       List<String> ledgers) { }
```

`Catalog`에 6개를 상수로 둔다. `allocation`은 `groupBy`가 요청의 `axis` 하나로 결정되므로 `groupBy = []`, `axisOptions = [INSTRUMENT, SECTOR, MARKET, CURRENCY, ASSET_CLASS, IS_LEVERAGED]`로 둔다. `accounts`는 `groupBy = [ACCOUNT_TYPE, ACCOUNT]`, `rowFields = ["link_state","last_collection","last_synced_at"]`. `summary`는 `subBlocks = [new SubBlockSpec("mini_chart", List.of(MARKET), LensPolicy.OPTIONAL, List.of(MARKET_VALUE_KRW, WEIGHT_PCT))]`.

- [ ] **Step 5: 카탈로그 불변식 테스트**

```java
package com.stockproject.portfolio.catalog;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

class CatalogInvariantTest {

    /** 불변식 4 — 행 키와 합계 키는 이름이 겹치지 않는다 (스펙 §6.2). */
    @Test
    void 행_전용_키와_합계_전용_키가_겹치지_않는다() {
        Set<String> rowOnly = Metric.all().stream()
                .filter(m -> m.scope() == MetricScope.ROW)
                .map(m -> m.key().key()).collect(Collectors.toSet());
        Set<String> totalOnly = Metric.all().stream()
                .filter(m -> m.scope() == MetricScope.TOTAL)
                .map(m -> m.key().key()).collect(Collectors.toSet());

        assertThat(rowOnly).doesNotContainAnyElementsOf(totalOnly);
        assertThat(rowOnly).contains("market_value_krw");
        assertThat(totalOnly).contains("total_assets_krw", "securities_value_krw");
    }

    /** 스펙 §6.2 — 비중의 분모는 총자산(CASH 포함), 손익률의 분모는 매입금액(CASH 제외). */
    @Test
    void 손익_계열은_CASH를_제외하고_비중_계열은_분모에_포함한다() {
        assertThat(Metric.of(MetricKey.COST_AMOUNT_KRW).cashScope()).isEqualTo(CashScope.EXCLUDED);
        assertThat(Metric.of(MetricKey.UNREALIZED_PNL_KRW).cashScope()).isEqualTo(CashScope.EXCLUDED);
        assertThat(Metric.of(MetricKey.UNREALIZED_PNL_PCT).cashScope()).isEqualTo(CashScope.EXCLUDED);
        assertThat(Metric.of(MetricKey.WEIGHT_PCT).cashScope()).isEqualTo(CashScope.DENOMINATOR_ONLY);
        assertThat(Metric.of(MetricKey.TOTAL_ASSETS_KRW).cashScope()).isEqualTo(CashScope.INCLUDED);
    }

    /** 스펙 §9.3 — LOOK_THROUGH에서는 lens_sensitive 축의 필터를 거부한다. 계좌 계열만 남는다. */
    @Test
    void LOOK_THROUGH_필터에는_lens_sensitive_축이_없다() {
        for (ViewSpec view : Catalog.views()) {
            List<AxisKey> allowed = view.filters().getOrDefault(Lens.LOOK_THROUGH, List.of());
            assertThat(allowed).allSatisfy(a ->
                    assertThat(a.lensSensitive())
                            .as("%s 뷰의 LOOK_THROUGH 필터에 lens_sensitive 축 %s", view.key(), a.key())
                            .isFalse());
        }
        assertThat(Catalog.view(ViewKey.POSITIONS).filters().get(Lens.LOOK_THROUGH))
                .containsExactly(AxisKey.ACCOUNT);
    }

    @Test
    void 축은_여덟개_지표는_열일곱개_뷰는_여섯개다() {
        assertThat(AxisKey.values()).hasSize(8);
        assertThat(Metric.all()).hasSize(17);
        assertThat(Catalog.views()).hasSize(6);
    }

    @Test
    void 비활성_축은_어떤_뷰의_기본_group_by도_아니다() {
        for (ViewSpec view : Catalog.views()) {
            assertThat(view.groupBy()).allSatisfy(a -> assertThat(a.enabled()).isTrue());
        }
    }

    /** 스펙 §3.7 표 — 현지 통화 병기가 가능한 축은 종목·통화뿐이다. */
    @Test
    void 현지_통화_병기_가능_축은_종목과_통화뿐이다() {
        assertThat(java.util.Arrays.stream(AxisKey.values())
                .filter(AxisKey::localCurrencyEligible).toList())
                .containsExactlyInAnyOrder(AxisKey.INSTRUMENT, AxisKey.CURRENCY);
    }
}
```

- [ ] **Step 6: 테스트 실행 → 커밋**

```bash
./gradlew test --tests '*CatalogInvariantTest'
git add -A && git commit -m "feat: 카탈로그 상수 — 축 8 · 지표 17 · 뷰 6"
```

---

### Task 3: 도메인 측정값 타입 — 가산성을 구조로 강제한다

이 태스크가 계획의 중심이다. 여기서 만든 타입이 "비율을 더한다"를 **컴파일 불가**로 만든다.

**Files:**
- Create: `domain/Line.java` · `AssetClass.java` · `Market.java` · `CurrencyCode.java` · `AccountType.java` · `LinkState.java` · `Grade.java`
- Create: `domain/measure/Measures.java` · `MeasureBundle.java` · `CurrencySet.java` · `LocalMoney.java`
- Create: `domain/group/TotalAssetsKrw.java` · `Derived.java`
- Test: `test/.../domain/measure/MeasuresTest.java` · `MeasureBundleTest.java`
- Test: `test/.../domain/group/DerivedTest.java`
- Test: `test/.../ArchitectureRulesTest.java`

**Interfaces:**
- Produces:
  - `Measures.plus(Measures)` · `Measures.ZERO` · `Measures.ofSecurities(Line)` · `Measures.ofCash(Line)`
  - `MeasureBundle.of(Line)` · `MeasureBundle.EMPTY` · `plus(MeasureBundle)` · `securities()` · `cash()` · `total()` · `currencies()` · `securityInstrumentIds()` · `accountIds()`
  - `CurrencySet.single()` → `Optional<CurrencyCode>`
  - `TotalAssetsKrw.value()` — 생성자는 package-private, `domain.group` 밖에서 만들 수 없다
  - `Derived.totalAssetsKrw/securitiesValueKrw/depositKrw/costAmountKrw/unrealizedPnlKrw/unrealizedPnlPct/avgCost/instrumentCount(MeasureBundle)`, `Derived.weightPct(MeasureBundle, TotalAssetsKrw)`, `Derived.cashRatioPct(MeasureBundle, TotalAssetsKrw)`, `Derived.changePct(BigDecimal, TotalAssetsKrw)`
- Consumes: Task 2의 `AxisKey`(이 태스크에서 `keyOf(Line)`을 채운다)

**완료 조건**
1. `Measures`·`MeasureBundle`에 비율 필드가 없고 나눗셈 메서드가 없다.
2. 손익 계열 파생값이 `securities` 슬롯만 읽는다 — CASH 라인만 있는 번들의 `unrealizedPnlKrw`가 `0`이고 `unrealizedPnlPct`가 `null`이다.
3. `TotalAssetsKrw`를 `domain.group` 밖에서 `new`로 만들 수 없다(컴파일 불가).
4. 가산성 반례 테스트(§A.3 불변식 1의 삼성전자/하이닉스 예시)가 `+11.8%`를 낸다.
5. `ArchitectureRulesTest`가 통과한다.

**검증 방법**
```bash
./gradlew test --tests '*MeasuresTest' --tests '*MeasureBundleTest' \
               --tests '*DerivedTest' --tests '*ArchitectureRulesTest'
```

- [ ] **Step 1: 실패하는 가산성 테스트를 먼저 쓴다**

`DerivedTest.java`:
```java
package com.stockproject.portfolio.domain.group;

import com.stockproject.portfolio.domain.*;
import com.stockproject.portfolio.domain.measure.MeasureBundle;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

class DerivedTest {

    /** 스펙 §3.2 — 라인별 수익률 평균은 틀리고, 집계 후 계산이 맞다. */
    @Test
    void 손익률은_라인_평균이_아니라_집계_후_계산이다() {
        MeasureBundle samsung  = bundleOf(stock("KRW", "10000000", "11000000"));
        MeasureBundle hynix    = bundleOf(stock("KRW", "1000000",  "1300000"));
        MeasureBundle combined = samsung.plus(hynix);

        // 틀린 방법: (10% + 30%) / 2 = 20%
        assertThat(Derived.unrealizedPnlPct(samsung)).isEqualByComparingTo("10.0");
        assertThat(Derived.unrealizedPnlPct(hynix)).isEqualByComparingTo("30.0");

        // 맞는 방법: (12,300,000 − 11,000,000) ÷ 11,000,000 = 11.8%
        assertThat(Derived.unrealizedPnlKrw(combined)).isEqualByComparingTo("1300000");
        assertThat(Derived.unrealizedPnlPct(combined)).isEqualByComparingTo("11.8");
    }

    /** 불변식 2 — 손익률 분모는 매입금액(CASH 제외). 예수금이 섞이면 값이 희석된다. */
    @Test
    void 예수금은_손익_분모에_섞이지_않는다() {
        MeasureBundle withCash = bundleOf(stock("KRW", "10000000", "11000000"))
                .plus(bundleOf(cash("KRW", "5000000")));

        assertThat(Derived.costAmountKrw(withCash)).isEqualByComparingTo("10000000");
        assertThat(Derived.unrealizedPnlKrw(withCash)).isEqualByComparingTo("1000000");
        assertThat(Derived.unrealizedPnlPct(withCash)).isEqualByComparingTo("10.0");   // 6.7이 아니다
        assertThat(Derived.totalAssetsKrw(withCash)).isEqualByComparingTo("16000000");
        assertThat(Derived.securitiesValueKrw(withCash)).isEqualByComparingTo("11000000");
        assertThat(Derived.depositKrw(withCash)).isEqualByComparingTo("5000000");
    }

    /** 불변식 2 — 비중의 분모는 총자산(CASH 포함)이며 그룹 자신의 합계가 아니다. */
    @Test
    void 비중의_분모는_응답_전체_총자산이다() {
        MeasureBundle row   = bundleOf(stock("KRW", "10000000", "11000000"));
        MeasureBundle whole = row.plus(bundleOf(cash("KRW", "5000000")));
        Aggregation agg = new Aggregation(whole, List.of());

        assertThat(Derived.weightPct(row, agg.weightDenominator()))
                .isEqualByComparingTo("68.8");   // 11,000,000 ÷ 16,000,000
        assertThat(Derived.cashRatioPct(whole, agg.weightDenominator()))
                .isEqualByComparingTo("31.3");
    }

    @Test
    void 분모가_영이면_비율은_null이다() {
        MeasureBundle onlyCash = bundleOf(cash("KRW", "5000000"));
        assertThat(Derived.unrealizedPnlPct(onlyCash)).isNull();
        assertThat(Derived.unrealizedPnlKrw(onlyCash)).isEqualByComparingTo("0");
    }

    // --- 픽스처 -------------------------------------------------------------
    private static MeasureBundle bundleOf(Line line) { return MeasureBundle.of(line); }

    private static Line stock(String currency, String costKrw, String marketKrw) {
        return line(AssetClass.STOCK, currency, costKrw, marketKrw);
    }

    private static Line cash(String currency, String amountKrw) {
        return line(AssetClass.CASH, currency, amountKrw, amountKrw);
    }

    private static Line line(AssetClass assetClass, String currency, String costKrw, String marketKrw) {
        return new Line(LocalDate.of(2026, 7, 27),
                UUID.randomUUID(), "계좌", AccountType.GENERAL, LinkState.CONNECTED,
                UUID.randomUUID(), "SYM", "종목", assetClass, Market.KR,
                CurrencyCode.valueOf(currency), "반도체", false,
                new BigDecimal("1"), new BigDecimal(costKrw), new BigDecimal(marketKrw),
                new BigDecimal(costKrw), new BigDecimal(marketKrw),
                BigDecimal.ONE, LocalDate.of(2026, 7, 27),
                OffsetDateTime.parse("2026-07-27T15:30:00+09:00"), false, false);
    }
}
```

- [ ] **Step 2: 테스트를 실행해 컴파일 실패를 확인한다**

Run: `./gradlew test --tests '*DerivedTest'`
Expected: 컴파일 실패 — `Line`, `Measures`, `MeasureBundle`, `Derived`, `Aggregation`, `TotalAssetsKrw`가 없다.

- [ ] **Step 3: `Line`과 열거 타입**

```java
package com.stockproject.portfolio.domain;

public enum AssetClass { STOCK, ETF, CASH }
public enum Market { KR, US }
public enum CurrencyCode {
    KRW(0), USD(2);
    private final int scale;
    CurrencyCode(int scale) { this.scale = scale; }
    /** 통화별 소수 자릿수 — 금액·평단 반올림에 쓴다(스펙 §5.5). */
    public int scale() { return scale; }
}
public enum AccountType { GENERAL, PENSION }
public enum LinkState { CONNECTING, CONNECTED, REAUTH_REQUIRED, DISCONNECTED }
public enum Grade { VERIFIED, SEEDED, UNAVAILABLE, CONFLICT }
```

```java
package com.stockproject.portfolio.domain;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

/**
 * 축이 붙은 조회 라인 — 스펙 §3.6 3단계의 산출물.
 * position_line + account 마스터 + instrument 마스터를 조인한 결과이며,
 * 렌즈(§3.4)의 입력이자 출력 타입이다. 비율 필드를 두지 않는다(§1.5).
 */
public record Line(
        LocalDate asOf,
        UUID accountId, String accountLabel, AccountType accountType, LinkState linkState,
        UUID instrumentId, String instrumentKey, String instrumentLabel,
        AssetClass assetClass, Market market, CurrencyCode currency,
        String sector, Boolean leveraged,
        BigDecimal quantity,
        BigDecimal costAmountLocal, BigDecimal marketValueLocal,
        BigDecimal costAmountKrw, BigDecimal marketValueKrw,
        BigDecimal fxRate, LocalDate fxAsOf,
        OffsetDateTime sourceAsOf, boolean carriedForward, boolean isFinal) {

    public boolean isCash() { return assetClass == AssetClass.CASH; }
    public boolean isEtf() { return assetClass == AssetClass.ETF; }
}
```

- [ ] **Step 4: `Measures` — 가산 측정값만 담는다**

```java
package com.stockproject.portfolio.domain.measure;

import com.stockproject.portfolio.domain.Line;

import java.math.BigDecimal;

/**
 * 가산 가능한 측정값만 담는다 — 스펙 §1.5 · §3.2.
 * 비율 필드가 없고 나눗셈 연산이 없다. 자리가 없으면 잘못 더할 방법도 없다.
 * 비율은 Derived만 만들 수 있으며 입력이 집계된 MeasureBundle이다.
 */
public record Measures(BigDecimal quantity,
                       BigDecimal costAmountLocal, BigDecimal marketValueLocal,
                       BigDecimal costAmountKrw, BigDecimal marketValueKrw) {

    public static final Measures ZERO = new Measures(
            BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO);

    public static Measures of(Line line) {
        return new Measures(line.quantity(),
                line.costAmountLocal(), line.marketValueLocal(),
                line.costAmountKrw(), line.marketValueKrw());
    }

    public Measures plus(Measures o) {
        return new Measures(
                quantity.add(o.quantity),
                costAmountLocal.add(o.costAmountLocal),
                marketValueLocal.add(o.marketValueLocal),
                costAmountKrw.add(o.costAmountKrw),
                marketValueKrw.add(o.marketValueKrw));
    }
}
```

- [ ] **Step 5: `CurrencySet`과 `MeasureBundle`**

```java
package com.stockproject.portfolio.domain.measure;

import com.stockproject.portfolio.domain.CurrencyCode;

import java.util.*;

/** 불변식 3 — 묶음의 통화 집합. 크기가 1일 때만 현지 통화 병기가 성립한다(스펙 §3.7). */
public record CurrencySet(Set<CurrencyCode> values) {

    public static final CurrencySet EMPTY = new CurrencySet(Set.of());

    public static CurrencySet of(CurrencyCode c) { return new CurrencySet(EnumSet.of(c)); }

    public CurrencySet plus(CurrencySet o) {
        if (values.isEmpty()) return o;
        if (o.values.isEmpty()) return this;
        EnumSet<CurrencyCode> merged = EnumSet.copyOf(values);
        merged.addAll(o.values);
        return new CurrencySet(merged);
    }

    /** 통화가 하나뿐일 때만 값이 있다. 섞인 묶음에는 현지 통화를 실을 방법이 없다. */
    public Optional<CurrencyCode> single() {
        return values.size() == 1 ? Optional.of(values.iterator().next()) : Optional.empty();
    }
}
```

```java
package com.stockproject.portfolio.domain.measure;

import com.stockproject.portfolio.domain.Line;

import java.util.*;

/**
 * 집계 누산기 — 불변식 2를 물리적으로 강제한다.
 * CASH(예수금 의사종목)를 별도 슬롯에 담아, 손익 계열 파생값이 예수금을 섞을 코드 경로가 없다.
 * 스펙 §5.2 · §6.2.
 */
public record MeasureBundle(Measures securities, Measures cash, CurrencySet currencies,
                            Set<UUID> securityInstrumentIds, Set<UUID> accountIds) {

    public static final MeasureBundle EMPTY =
            new MeasureBundle(Measures.ZERO, Measures.ZERO, CurrencySet.EMPTY, Set.of(), Set.of());

    public static MeasureBundle of(Line line) {
        Measures m = Measures.of(line);
        return new MeasureBundle(
                line.isCash() ? Measures.ZERO : m,
                line.isCash() ? m : Measures.ZERO,
                CurrencySet.of(line.currency()),
                line.isCash() ? Set.of() : Set.of(line.instrumentId()),
                Set.of(line.accountId()));
    }

    public MeasureBundle plus(MeasureBundle o) {
        Set<UUID> instruments = new HashSet<>(securityInstrumentIds);
        instruments.addAll(o.securityInstrumentIds);
        Set<UUID> accounts = new HashSet<>(accountIds);
        accounts.addAll(o.accountIds);
        return new MeasureBundle(
                securities.plus(o.securities), cash.plus(o.cash),
                currencies.plus(o.currencies), instruments, accounts);
    }

    /** 예수금 포함 합계. total_assets_krw · market_value_krw · weight_pct 분모의 원천. */
    public Measures total() { return securities.plus(cash); }
}
```

- [ ] **Step 6: `TotalAssetsKrw`와 `Aggregation`, `Derived`**

```java
package com.stockproject.portfolio.domain.group;

import com.stockproject.portfolio.domain.measure.MeasureBundle;

import java.math.BigDecimal;

/**
 * 비중의 분모 — 불변식 2.
 * 생성자와 팩터리가 package-private이므로 domain.group 밖에서 만들 수 없고,
 * 실질적 유일 생성 경로는 Aggregation.weightDenominator()다.
 * 그룹 자신의 합계를 비중 분모로 쓰는 실수를 타입이 막는다.
 */
public final class TotalAssetsKrw {
    private final BigDecimal value;

    private TotalAssetsKrw(BigDecimal value) { this.value = value; }

    static TotalAssetsKrw of(MeasureBundle responseTotal) {
        return new TotalAssetsKrw(responseTotal.total().marketValueKrw());
    }

    public BigDecimal value() { return value; }
}
```

```java
package com.stockproject.portfolio.domain.group;

import com.stockproject.portfolio.domain.measure.MeasureBundle;

import java.util.List;

/** 집계 산출물 — 스펙 §3.6 4단계. 응답 전체 합계와 축 값별 노드를 함께 담는다. */
public record Aggregation(MeasureBundle responseTotal, List<GroupNode> rows) {

    /** 비중의 분모. 필터·렌즈 적용 후 응답 전체 총자산이며 Σ rows와 일치한다(§8.3). */
    public TotalAssetsKrw weightDenominator() { return TotalAssetsKrw.of(responseTotal); }
}
```

```java
package com.stockproject.portfolio.domain.group;

import com.stockproject.portfolio.domain.CurrencyCode;
import com.stockproject.portfolio.domain.measure.MeasureBundle;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * 파생 지표를 만드는 유일한 지점 — 스펙 §1.5 · §3.6 5단계.
 * 입력이 집계된 MeasureBundle이라 라인 하나로는 비율 호출이 성립하지 않는다.
 * 비율은 소수 1자리 HALF_UP, 분모가 0이면 null(0이 아니다).
 */
public final class Derived {

    private static final BigDecimal HUNDRED = new BigDecimal("100");
    private static final int PCT_SCALE = 1;

    private Derived() { }

    // --- 합계 전용 (CASH 포함/제외가 슬롯으로 갈려 있다) --------------------
    public static BigDecimal totalAssetsKrw(MeasureBundle b)     { return b.total().marketValueKrw(); }
    public static BigDecimal securitiesValueKrw(MeasureBundle b) { return b.securities().marketValueKrw(); }
    public static BigDecimal depositKrw(MeasureBundle b)         { return b.cash().marketValueKrw(); }

    // --- 손익 계열: securities 슬롯만 읽는다 (CASH 제외) ------------------
    public static BigDecimal costAmountKrw(MeasureBundle b)     { return b.securities().costAmountKrw(); }

    public static BigDecimal unrealizedPnlKrw(MeasureBundle b) {
        return b.securities().marketValueKrw().subtract(b.securities().costAmountKrw());
    }

    public static BigDecimal unrealizedPnlPct(MeasureBundle b) {
        return pct(unrealizedPnlKrw(b), b.securities().costAmountKrw());
    }

    /** 평단 = Σ매입 ÷ Σ수량. 통화 소수 자릿수로 반올림한다. CASH·수량 0이면 null. */
    public static BigDecimal avgCost(MeasureBundle b, CurrencyCode currency) {
        BigDecimal qty = b.securities().quantity();
        if (qty.signum() == 0) return null;
        return b.securities().costAmountLocal().divide(qty, currency.scale(), RoundingMode.HALF_UP);
    }

    public static int instrumentCount(MeasureBundle b) { return b.securityInstrumentIds().size(); }
    public static int accountCount(MeasureBundle b)    { return b.accountIds().size(); }

    // --- 외부 분모를 요구하는 비율 (타입이 분모를 고정한다) -----------------
    public static BigDecimal weightPct(MeasureBundle row, TotalAssetsKrw denominator) {
        return pct(row.total().marketValueKrw(), denominator.value());
    }

    public static BigDecimal cashRatioPct(MeasureBundle b, TotalAssetsKrw denominator) {
        return pct(depositKrw(b), denominator.value());
    }

    public static BigDecimal changePct(BigDecimal deltaKrw, TotalAssetsKrw priorTotal) {
        return pct(deltaKrw, priorTotal.value());
    }

    private static BigDecimal pct(BigDecimal numerator, BigDecimal denominator) {
        if (numerator == null || denominator == null || denominator.signum() == 0) return null;
        return numerator.multiply(HUNDRED).divide(denominator, PCT_SCALE, RoundingMode.HALF_UP);
    }
}
```

`GroupNode`는 Task 6에서 쓰지만 `Aggregation`이 참조하므로 여기서 만든다:
```java
package com.stockproject.portfolio.domain.group;

import com.stockproject.portfolio.domain.measure.MeasureBundle;
import java.util.List;

public record GroupNode(GroupKey key, MeasureBundle measures, List<GroupNode> children) { }
```

`GroupKey`도 함께:
```java
package com.stockproject.portfolio.domain.group;

/** 축 값 하나. 기타 버킷은 other=true이며 정렬 시 항상 맨 끝으로 간다(스펙 §3.6 6단계). */
public record GroupKey(String key, String label, boolean other) {

    public static final GroupKey CASH         = new GroupKey("CASH", "현금", false);
    public static final GroupKey UNCLASSIFIED = new GroupKey("UNCLASSIFIED", "미분류", false);
    public static final GroupKey OTHER        = new GroupKey("OTHER", "기타(ETF 내 비주식·미매칭)", true);

    public static GroupKey of(String key, String label) { return new GroupKey(key, label, false); }

    /** 분류가 null인 종목은 미분류로 모인다 — 스펙 §6.1. */
    public static GroupKey ofNullable(String value) {
        return value == null || value.isBlank() ? UNCLASSIFIED : of(value, value);
    }
}
```

- [ ] **Step 7: `AxisKey.keyOf(Line)`을 채운다** (§A.4.1 폴백 규칙)

`AxisKey`에 추상 메서드를 추가하고 상수별 본문을 준다:
```java
    public abstract GroupKey keyOf(Line line);
```

| 축 | 구현 |
|---|---|
| `ACCOUNT` | `GroupKey.of(line.accountId().toString(), line.accountLabel())` |
| `ACCOUNT_TYPE` | `GroupKey.of(line.accountType().name(), line.accountType() == GENERAL ? "일반" : "연금")` |
| `INSTRUMENT` | `GroupKey.of(line.instrumentKey(), line.instrumentLabel())` |
| `SECTOR` | `line.isCash() ? GroupKey.CASH : GroupKey.ofNullable(line.sector())` |
| `MARKET` | `line.isCash() ? GroupKey.CASH : GroupKey.of(line.market().name(), line.market() == KR ? "국내" : "미국")` |
| `CURRENCY` | `GroupKey.of(line.currency().name(), line.currency().name())` — CASH도 통화가 있으므로 폴백 없음 |
| `ASSET_CLASS` | `line.isCash() ? GroupKey.CASH : GroupKey.of(line.assetClass().name(), line.assetClass() == STOCK ? "주식" : "ETF")` |
| `IS_LEVERAGED` | `line.isCash() ? GroupKey.CASH : line.leveraged() == null ? GroupKey.UNCLASSIFIED : GroupKey.of(...)` |

`CASH` 의사종목이 모든 분류 축에서 `현금`으로 모이는 것이 §6.1의 폴백 규칙이다. `instrument`·`currency` 축에서는 CASH가 자기 값을 갖는다(`CASH-KRW` · `KRW`) — 예수금을 종목으로 취급하기 때문이다(§5.2).

- [ ] **Step 8: 테스트를 실행해 통과를 확인한다**

Run: `./gradlew test --tests '*DerivedTest'`
Expected: PASS. 특히 `11.8`과 `10.0`(예수금 희석 없음)이 나와야 한다.

- [ ] **Step 9: `TotalAssetsKrw` 봉인을 컴파일로 확인한다**

`src/test/java/.../domain/measure/MeasureBundleTest.java`에 아래 주석을 남기고, 실제로 한 번 주석을 풀어 **컴파일 실패**를 확인한 뒤 되돌린다.

```java
    // 불변식 2 — 아래 줄은 컴파일되지 않아야 한다(TotalAssetsKrw 생성자·팩터리가 package-private).
    // TotalAssetsKrw wrong = TotalAssetsKrw.of(someGroupBundle);
```

그리고 통화 게이트 테스트를 추가한다:
```java
    @Test
    void 통화가_섞이면_현지_통화를_꺼낼_수_없다() {
        MeasureBundle mixed = MeasureBundle.of(krwLine()).plus(MeasureBundle.of(usdLine()));
        assertThat(mixed.currencies().single()).isEmpty();

        MeasureBundle usdOnly = MeasureBundle.of(usdLine());
        assertThat(usdOnly.currencies().single()).contains(CurrencyCode.USD);
    }
```

- [ ] **Step 10: ArchUnit 규칙**

`ArchitectureRulesTest.java`:
```java
package com.stockproject.portfolio;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.lang.ArchRule;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.fields;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

class ArchitectureRulesTest {

    private static JavaClasses classes;

    @BeforeAll
    static void importClasses() {
        classes = new ClassFileImporter()
                .withImportOption(ImportOption.Predefined.DO_NOT_INCLUDE_TESTS)
                .importPackages("com.stockproject.portfolio");
    }

    /** 불변식 1 — 집계 누산기에 비율 필드를 둘 수 없다(스펙 §1.5 · §9.2). */
    @Test
    void 측정값_타입에_비율_필드가_없다() {
        ArchRule rule = fields()
                .that().areDeclaredInClassesThat()
                .haveSimpleNameEndingWith("Measures")
                .or().areDeclaredInClassesThat().haveSimpleName("MeasureBundle")
                .should().haveNameNotMatching(".*(Pct|Ratio|Rate|Percent|Yield|Weight)$")
                .because("비율은 가산 불가라 누산기에 자리를 두지 않는다 (스펙 §1.5)");
        rule.check(classes);
    }

    /** 금액·수량·환율·비율에 부동소수점을 쓰지 않는다. */
    @Test
    void 도메인에_double과_float가_없다() {
        ArchRule rule = fields()
                .that().areDeclaredInClassesThat().resideInAPackage("..domain..")
                .should().notHaveRawType(double.class)
                .andShould().notHaveRawType(float.class)
                .because("금액 계산은 BigDecimal로만 한다");
        rule.check(classes);
    }

    /** 파생 지표는 Derived만 만든다 — 계산이 흩어지면 분모 규칙이 갈린다. */
    @Test
    void 파생_지표는_Derived만_만든다() {
        ArchRule rule = noClasses()
                .that().resideOutsideOfPackages("..domain.group..", "..view..")
                .should().callMethodWhere(
                        com.tngtech.archunit.core.domain.JavaCall.Predicates.target(
                                com.tngtech.archunit.core.domain.properties.HasOwner.Predicates
                                        .With.owner(
                                        com.tngtech.archunit.core.domain.JavaClass.Predicates
                                                .simpleName("Derived"))))
                .because("파생 지표 계산은 Derived 한 곳에 모은다 (스펙 §3.6 5단계)");
        rule.check(classes);
    }

    /** API 계층이 저장소를 직접 부르지 않는다 — 검증기를 우회하는 경로를 막는다. */
    @Test
    void api는_query를_직접_호출하지_않는다() {
        ArchRule rule = noClasses()
                .that().resideInAPackage("..api..")
                .should().dependOnClassesThat().resideInAPackage("..query..")
                .because("§9.1 런타임 검증을 우회하는 조회 경로를 만들지 않는다");
        rule.check(classes);
    }
}
```

- [ ] **Step 11: 전체 테스트 → 커밋**

```bash
./gradlew test
git add -A && git commit -m "feat: 측정값·파생 지표 타입 — 가산성과 분모 규칙을 타입으로 강제"
```

---

### Task 4: 조회 계층과 런타임 검증 (§3.6 3~3.5단계 · §9.1)

**Files:**
- Create: `query/PositionLineRepository.java` · `LineFilter.java` · `AccountRepository.java` · `SnapshotCalendarRepository.java`
- Create: `query/CollectionStatusPort.java` · `NoCollectionStatusPort.java`
- Create: `validation/PositionLineInvariants.java` · `FactInvariantViolation.java`
- Test: `test/.../query/PositionLineRepositoryTest.java` (Testcontainers)
- Test: `test/.../query/SchemaContractTest.java`
- Test: `test/.../validation/PositionLineInvariantsTest.java`

**Interfaces:**
- Consumes: Task 3의 `Line`, Task 2의 `AxisKey`
- Produces:
  - `List<Line> PositionLineRepository.findLines(LocalDate asOf, LineFilter filter)`
  - `record LineFilter(Set<UUID> accountIds, Set<AccountType> accountTypes, Set<Market> markets, Set<AssetClass> assetClasses)` + `LineFilter.NONE`
  - `Optional<LocalDate> SnapshotCalendarRepository.latestAsOf()` · `Optional<LocalDate> previousAsOf(LocalDate)` · `Optional<LocalDate> latestOnOrBefore(LocalDate)` · `Optional<LocalDate> earliestOnOrAfter(LocalDate)` · `Optional<LocalDate> latestBefore(LocalDate)`
  - `BigDecimal SnapshotCalendarRepository.totalAssetsKrwAt(LocalDate, LineFilter)`
  - `List<AccountRow> AccountRepository.findAll()` — `record AccountRow(UUID id, String broker, String label, AccountType type, LinkState linkState, OffsetDateTime lastSyncedAt)`
  - `void PositionLineInvariants.validate(LocalDate asOf, List<Line> lines, List<AccountRow> accounts)`

**완료 조건**
1. 샘플 데이터에서 `findLines(2026-07-27, NONE)`이 10행을 내고, 각 행의 축 값(계좌유형·섹터·시장·통화·자산군)이 마스터 조인으로 채워진다.
2. 필터가 §3.6 3.5단계대로 **마스터 조인 뒤** 적용된다 — `LineFilter(markets = {US})`가 3행(AAPL·MSFT·CASH-USD)을 낸다.
3. `PositionLineInvariants`가 §A.8의 5개 규칙을 검사하고 위반 시 `FactInvariantViolation`을 던진다.
4. `SchemaContractTest`가 데이터팀 소유 `instrument`의 컬럼 계약을 `information_schema`로 확인한다.
5. `totalAssetsKrwAt(2026-07-24, NONE)`이 `56800000`을 낸다.

**검증 방법**
```bash
./gradlew test --tests '*PositionLineRepositoryTest' --tests '*SchemaContractTest' \
               --tests '*PositionLineInvariantsTest'
```

- [ ] **Step 1: 저장소 테스트를 먼저 쓴다**

`PositionLineRepositoryTest.java`:
```java
package com.stockproject.portfolio.query;

import com.stockproject.portfolio.domain.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.datasource.init.ScriptUtils;
import org.springframework.test.context.ActiveProfiles;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import javax.sql.DataSource;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
@Testcontainers
class PositionLineRepositoryTest {

    @Container @ServiceConnection
    static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired DataSource dataSource;
    @Autowired PositionLineRepository repository;
    @Autowired SnapshotCalendarRepository calendar;

    private static final LocalDate AS_OF = LocalDate.of(2026, 7, 27);

    @BeforeEach
    void seed() throws Exception {
        try (var conn = dataSource.getConnection()) {
            ScriptUtils.executeSqlScript(conn, new ClassPathResource("db/sample/sample_portfolio.sql"));
        }
    }

    @Test
    void 마스터_조인으로_축_값이_채워진다() {
        List<Line> lines = repository.findLines(AS_OF, LineFilter.NONE);

        assertThat(lines).hasSize(10);
        Line samsung = lines.stream().filter(l -> l.instrumentKey().equals("005930")).findFirst().orElseThrow();
        assertThat(samsung.sector()).isEqualTo("반도체");
        assertThat(samsung.market()).isEqualTo(Market.KR);
        assertThat(samsung.currency()).isEqualTo(CurrencyCode.KRW);
        assertThat(samsung.assetClass()).isEqualTo(AssetClass.STOCK);
        assertThat(samsung.accountType()).isEqualTo(AccountType.GENERAL);
        assertThat(samsung.accountLabel()).isEqualTo("한국투자 위탁");

        Line etf = lines.stream().filter(l -> l.instrumentKey().equals("133690")).findFirst().orElseThrow();
        assertThat(etf.sector()).isNull();                 // 폴백은 축이 담당한다
        assertThat(etf.assetClass()).isEqualTo(AssetClass.ETF);
    }

    @Test
    void 라인_합이_총자산과_같다() {
        BigDecimal sum = repository.findLines(AS_OF, LineFilter.NONE).stream()
                .map(Line::marketValueKrw).reduce(BigDecimal.ZERO, BigDecimal::add);
        assertThat(sum).isEqualByComparingTo("58000000");
    }

    /** 스펙 §3.6 3.5단계 — 필터는 마스터 조인 뒤에 적용한다. */
    @Test
    void 시장_필터는_마스터_조인_값으로_동작한다() {
        List<Line> us = repository.findLines(AS_OF,
                new LineFilter(Set.of(), Set.of(), Set.of(Market.US), Set.of()));

        assertThat(us).extracting(Line::instrumentKey)
                .containsExactlyInAnyOrder("AAPL", "MSFT", "CASH-USD");
    }

    @Test
    void 계좌유형_필터가_동작한다() {
        List<Line> pension = repository.findLines(AS_OF,
                new LineFilter(Set.of(), Set.of(AccountType.PENSION), Set.of(), Set.of()));

        assertThat(pension).hasSize(4);
        assertThat(pension).extracting(Line::marketValueKrw)
                .extracting(BigDecimal::longValue)
                .containsExactlyInAnyOrder(11_000_000L, 1_000_000L, 4_900_000L, 140_000L);
    }

    @Test
    void 직전_스냅샷과_총자산을_읽는다() {
        assertThat(calendar.latestAsOf()).contains(AS_OF);
        assertThat(calendar.previousAsOf(AS_OF)).contains(LocalDate.of(2026, 7, 24));
        assertThat(calendar.totalAssetsKrwAt(LocalDate.of(2026, 7, 24), LineFilter.NONE))
                .isEqualByComparingTo("56800000");
    }

    @Test
    void 캐리포워드_라인이_표시된다() {
        List<Line> lines = repository.findLines(AS_OF, LineFilter.NONE);
        assertThat(lines).filteredOn(Line::carriedForward).hasSize(2)
                .allSatisfy(l -> assertThat(l.fxAsOf()).isEqualTo(LocalDate.of(2026, 7, 24)));
    }
}
```

- [ ] **Step 2: 실행해 실패를 확인한다**

Run: `./gradlew test --tests '*PositionLineRepositoryTest'`
Expected: 컴파일 실패 — `PositionLineRepository`·`LineFilter`·`SnapshotCalendarRepository`가 없다.

- [ ] **Step 3: `LineFilter`**

```java
package com.stockproject.portfolio.query;

import com.stockproject.portfolio.domain.*;

import java.util.Set;
import java.util.UUID;

/**
 * 요청 필터 — 스펙 §3.3. 필터는 그레인을 바꾸지 않고 대상 행만 고른다.
 * 값은 카탈로그 대조(§9.3)를 통과한 enum·계좌 ID이므로 SQL 조립 위험이 없다.
 */
public record LineFilter(Set<UUID> accountIds, Set<AccountType> accountTypes,
                         Set<Market> markets, Set<AssetClass> assetClasses) {

    public static final LineFilter NONE = new LineFilter(Set.of(), Set.of(), Set.of(), Set.of());

    public boolean isEmpty() {
        return accountIds.isEmpty() && accountTypes.isEmpty()
                && markets.isEmpty() && assetClasses.isEmpty();
    }
}
```

- [ ] **Step 4: `PositionLineRepository`**

```java
package com.stockproject.portfolio.query;

import com.stockproject.portfolio.domain.*;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.*;

/**
 * 스펙 §3.6 3단계(마스터 조인)와 3.5단계(필터)를 SQL로 수행한다.
 * 2·4·5·6단계는 Java가 맡는다 — 렌즈를 라인 집합 → 라인 집합 순수 함수로 유지하기 위해(계획 §A.2.4).
 */
@Repository
public class PositionLineRepository {

    private static final String BASE_SQL = """
            SELECT pl.as_of, pl.account_id, a.label AS account_label, a.account_type, a.link_state,
                   pl.instrument_id, i.symbol, i.name, i.asset_class, i.market, i.currency,
                   i.sector, i.is_leveraged,
                   pl.quantity, pl.cost_amount_local, pl.market_value_local,
                   pl.cost_amount_krw, pl.market_value_krw,
                   pl.fx_rate, pl.fx_as_of, pl.source_as_of, pl.is_carried_forward, pl.is_final
              FROM position_line pl
              JOIN account    a ON a.account_id    = pl.account_id
              JOIN instrument i ON i.instrument_id = pl.instrument_id
             WHERE pl.as_of = :asOf
            """;

    private final JdbcClient jdbc;

    public PositionLineRepository(JdbcClient jdbc) { this.jdbc = jdbc; }

    public List<Line> findLines(LocalDate asOf, LineFilter filter) {
        StringBuilder sql = new StringBuilder(BASE_SQL);
        Map<String, Object> params = new HashMap<>();
        params.put("asOf", asOf);

        if (!filter.accountIds().isEmpty()) {
            sql.append(" AND pl.account_id = ANY (:accountIds)");
            params.put("accountIds", filter.accountIds().toArray(UUID[]::new));
        }
        if (!filter.accountTypes().isEmpty()) {
            sql.append(" AND a.account_type = ANY (:accountTypes)");
            params.put("accountTypes", names(filter.accountTypes()));
        }
        if (!filter.markets().isEmpty()) {
            sql.append(" AND i.market = ANY (:markets)");
            params.put("markets", names(filter.markets()));
        }
        if (!filter.assetClasses().isEmpty()) {
            sql.append(" AND i.asset_class = ANY (:assetClasses)");
            params.put("assetClasses", names(filter.assetClasses()));
        }

        return jdbc.sql(sql.toString()).params(params)
                .query((rs, n) -> new Line(
                        rs.getObject("as_of", LocalDate.class),
                        rs.getObject("account_id", UUID.class), rs.getString("account_label"),
                        AccountType.valueOf(rs.getString("account_type")),
                        LinkState.valueOf(rs.getString("link_state")),
                        rs.getObject("instrument_id", UUID.class),
                        rs.getString("symbol"), rs.getString("name"),
                        AssetClass.valueOf(rs.getString("asset_class")),
                        Market.valueOf(rs.getString("market")),
                        CurrencyCode.valueOf(rs.getString("currency")),
                        rs.getString("sector"), (Boolean) rs.getObject("is_leveraged"),
                        rs.getBigDecimal("quantity"),
                        rs.getBigDecimal("cost_amount_local"), rs.getBigDecimal("market_value_local"),
                        rs.getBigDecimal("cost_amount_krw"), rs.getBigDecimal("market_value_krw"),
                        rs.getBigDecimal("fx_rate"), rs.getObject("fx_as_of", LocalDate.class),
                        rs.getObject("source_as_of", java.time.OffsetDateTime.class),
                        rs.getBoolean("is_carried_forward"), rs.getBoolean("is_final")))
                .list();
    }

    private static String[] names(Set<? extends Enum<?>> values) {
        return values.stream().map(Enum::name).toArray(String[]::new);
    }
}
```

`= ANY (:param)`에 배열을 넘기는 방식이라 `IN (...)` 문자열 조립이 없다.

- [ ] **Step 5: `SnapshotCalendarRepository`와 `AccountRepository`**

`SnapshotCalendarRepository`는 `position_line`의 `as_of` 축만 다룬다.
```java
    public Optional<LocalDate> latestAsOf() {
        return jdbc.sql("SELECT max(as_of) FROM position_line").query(LocalDate.class).optional();
    }

    public Optional<LocalDate> previousAsOf(LocalDate asOf) {
        return jdbc.sql("SELECT max(as_of) FROM position_line WHERE as_of < :asOf")
                .param("asOf", asOf).query(LocalDate.class).optional();
    }

    public Optional<LocalDate> latestOnOrBefore(LocalDate date) { /* as_of <= :date */ }
    public Optional<LocalDate> latestBefore(LocalDate date)     { /* as_of <  :date */ }
    public Optional<LocalDate> earliestOnOrAfter(LocalDate date) { /* min(as_of) WHERE as_of >= :date */ }
```

`totalAssetsKrwAt`은 `LineFilter`의 계좌 조건만 반영한다(자산 변화·일간 변화가 쓰는 값이고 두 뷰의 필터는 계좌·기간뿐이다):
```java
    public BigDecimal totalAssetsKrwAt(LocalDate asOf, LineFilter filter) {
        StringBuilder sql = new StringBuilder("""
                SELECT coalesce(sum(pl.market_value_krw), 0)
                  FROM position_line pl JOIN account a ON a.account_id = pl.account_id
                 WHERE pl.as_of = :asOf
                """);
        // accountIds · accountTypes 조건만 append (findLines와 동일 방식)
    }
```

`AccountRepository.findAll()`은 `account` 전체를 `AccountRow`로 읽는다. `DISCONNECTED` 계좌도 함께 읽고 필터링은 호출자가 한다 — §7.5의 "연동 해제는 제외"와 §9.1의 "연동이 유효한 계좌"를 각각 판단해야 하기 때문이다.

`CollectionStatusPort` (스텁 자리):
```java
package com.stockproject.portfolio.query;

import java.util.Map;
import java.util.UUID;

/**
 * 최신 collection_run 상태 — 데이터팀 소유 테이블(스펙 §7.7).
 * 계약이 미합의라 이번 범위에서는 NoCollectionStatusPort가 빈 맵을 낸다.
 */
public interface CollectionStatusPort {
    /** accountId → { state, as_of, failure_reason }. 없는 계좌는 키가 없다. */
    Map<UUID, Map<String, Object>> latestByAccount();
}
```
`NoCollectionStatusPort`는 `Map.of()`를 낸다(`@Component`).

- [ ] **Step 6: 검증기 테스트를 쓴다**

`PositionLineInvariantsTest.java` — 5개 규칙마다 한 개씩:
```java
    @Test
    void 그레인이_중복되면_거부한다() {
        Line dup = line(ACC_1, INST_1);
        assertThatThrownBy(() -> invariants.validate(AS_OF, List.of(dup, dup), accounts()))
                .isInstanceOf(FactInvariantViolation.class)
                .hasMessageContaining("그레인 유일성");
    }

    @Test
    void 환율이_없으면_거부한다() {
        Line noFx = lineWithFx(null, LocalDate.of(2026, 7, 27));
        assertThatThrownBy(() -> invariants.validate(AS_OF, List.of(noFx), accounts()))
                .hasMessageContaining("fx_rate");
    }

    @Test
    void CASH_행의_원가가_평가금액과_다르면_거부한다() {
        Line badCash = cashLine("1000000", "900000");
        assertThatThrownBy(() -> invariants.validate(AS_OF, List.of(badCash), accounts()))
                .hasMessageContaining("CASH");
    }

    @Test
    void 연동된_계좌에_라인이_없으면_거부한다() {
        // 계좌 2개 중 1개만 라인이 있다 → 그날만 총자산이 급락해 손실처럼 보인다(스펙 §7.3)
        assertThatThrownBy(() -> invariants.validate(AS_OF, List.of(line(ACC_1, INST_1)),
                        List.of(account(ACC_1, LinkState.CONNECTED), account(ACC_2, LinkState.CONNECTED))))
                .hasMessageContaining("라인 없음");
    }

    @Test
    void 해제된_계좌는_라인이_없어도_통과한다() {
        invariants.validate(AS_OF, List.of(line(ACC_1, INST_1)),
                List.of(account(ACC_1, LinkState.CONNECTED),
                        account(ACC_2, LinkState.DISCONNECTED)));   // 예외 없음
    }

    @Test
    void 이월_라인의_source_as_of가_as_of보다_늦으면_거부한다() {
        Line bad = carriedForwardLine(OffsetDateTime.parse("2026-07-28T15:30:00+09:00"));
        assertThatThrownBy(() -> invariants.validate(AS_OF, List.of(bad), accounts()))
                .hasMessageContaining("is_carried_forward");
    }
```

- [ ] **Step 7: 검증기 구현**

```java
package com.stockproject.portfolio.validation;

import com.stockproject.portfolio.domain.*;
import com.stockproject.portfolio.query.AccountRepository.AccountRow;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.ZoneId;
import java.util.*;

/**
 * 스펙 §9.1 팩트 정합성 — 저장·집계 전에 통과해야 한다.
 * 위반은 조용히 넘기지 않는다. 손으로 넣은 샘플이 틀렸다는 뜻이므로 크게 터뜨린다.
 */
@Component
public class PositionLineInvariants {

    private static final ZoneId KST = ZoneId.of("Asia/Seoul");

    public void validate(LocalDate asOf, List<Line> lines, List<AccountRow> accounts) {
        List<String> violations = new ArrayList<>();

        // 1. 그레인 유일성 — (as_of, account, instrument)마다 정확히 1행
        Set<List<Object>> seen = new HashSet<>();
        for (Line l : lines) {
            if (!seen.add(List.of(l.asOf(), l.accountId(), l.instrumentId()))) {
                violations.add("그레인 유일성 위반: %s / %s / %s"
                        .formatted(l.asOf(), l.accountId(), l.instrumentId()));
            }
        }

        for (Line l : lines) {
            // 2. market_value_krw가 있으면 fx_rate·fx_as_of 필수
            if (l.marketValueKrw() != null && (l.fxRate() == null || l.fxAsOf() == null)) {
                violations.add("fx_rate·fx_as_of 누락: " + l.instrumentKey());
            }
            // 3. CASH 행은 원가 = 평가금액 (스펙 §5.2)
            if (l.isCash() && l.costAmountKrw().compareTo(l.marketValueKrw()) != 0) {
                violations.add("CASH 행의 원가 ≠ 평가금액: " + l.instrumentKey());
            }
            // 4. is_carried_forward = true이면 source_as_of < as_of
            //    (timestamptz AT TIME ZONE이 immutable이 아니라 CHECK 제약으로 표현할 수 없다)
            if (l.carriedForward()
                    && !l.sourceAsOf().atZoneSameInstant(KST).toLocalDate().isBefore(l.asOf())) {
                violations.add("is_carried_forward인데 source_as_of >= as_of: " + l.instrumentKey());
            }
        }

        // 5. 연동이 유효한 모든 계좌는 해당 as_of에 라인 존재 (스펙 §7.3 · §9.1)
        Set<UUID> withLines = lines.stream().map(Line::accountId).collect(java.util.stream.Collectors.toSet());
        for (AccountRow a : accounts) {
            if (a.linkState() != LinkState.DISCONNECTED && !withLines.contains(a.id())) {
                violations.add("연동된 계좌에 %s 라인 없음: %s".formatted(asOf, a.label()));
            }
        }

        if (!violations.isEmpty()) throw new FactInvariantViolation(violations);
    }
}
```

```java
package com.stockproject.portfolio.validation;

import java.util.List;

public class FactInvariantViolation extends RuntimeException {
    private final List<String> violations;

    public FactInvariantViolation(List<String> violations) {
        super("팩트 정합성 위반 (스펙 §9.1): " + String.join(" | ", violations));
        this.violations = List.copyOf(violations);
    }

    public List<String> violations() { return violations; }
}
```

**주의**: 규칙 5는 **필터를 적용하지 않은** 라인 집합에 대해서만 검사한다. 계좌 필터를 걸면 당연히 일부 계좌의 라인이 없으므로, 검증은 필터 전에 수행한다(Task 8의 서비스가 순서를 지킨다).

- [ ] **Step 8: 스키마 계약 테스트**

```java
    /** 데이터팀 소유 instrument의 컬럼 계약 — 스펙 §11.2. 드리프트를 조기에 잡는다. */
    @Test
    void instrument_컬럼_계약이_유지된다() {
        List<String> columns = jdbc.sql("""
                SELECT column_name FROM information_schema.columns
                 WHERE table_name = 'instrument' ORDER BY column_name
                """).query(String.class).list();

        assertThat(columns).containsExactly("asset_class", "currency", "instrument_id",
                "is_leveraged", "isin", "market", "name", "sector", "symbol");
    }
```

- [ ] **Step 9: 테스트 통과 확인 → 커밋**

```bash
./gradlew test --tests '*PositionLineRepositoryTest' --tests '*SchemaContractTest' \
               --tests '*PositionLineInvariantsTest'
git add -A && git commit -m "feat: 라인 조회 계층과 팩트 정합성 검증"
```

---

### Task 5: 렌즈 — 인터페이스 · DIRECT 완성 · LOOK_THROUGH 미확보 분기

**Files:**
- Create: `domain/lens/LensTransform.java` · `DirectLens.java` · `LookThroughLens.java` · `LensResult.java`
- Create: `domain/lens/ConstituentPort.java` · `ConstituentCoverage.java` · `ConstituentExpander.java` · `NoConstituentDataPort.java`
- Create: `validation/LensOutputInvariants.java`
- Test: `test/.../domain/lens/DirectLensTest.java` · `LookThroughLensTest.java`

**Interfaces:**
- Produces:
  - `LensResult LensTransform.apply(List<Line> lines)`
  - `record LensResult(List<Line> lines, int undecomposedEtfCount, BigDecimal undecomposedKrw, List<LocalDate> constituentAsOfs)`
  - `ConstituentCoverage ConstituentPort.coverageOf(UUID etfInstrumentId)` → `COVERED | UNAVAILABLE`
  - `List<Line> ConstituentExpander.expand(Line etfLine)` — **2단계 자리. 이번 범위에서 호출 불가**
  - `void LensOutputInvariants.validateTotalPreserved(List<Line> before, List<Line> after)`

**완료 조건**
1. `DirectLens.apply(lines)`가 입력을 그대로 내고 `undecomposedEtfCount = 0`이다.
2. `LookThroughLens.apply(lines)`가 `NoConstituentDataPort` 아래에서 **ETF 행을 그대로 남기고** `undecomposedEtfCount = 1`, `undecomposedKrw = 11000000`을 낸다.
3. 두 렌즈 모두 `Σ market_value_krw`를 보존하고 `LensOutputInvariants`가 그것을 확인한다.
4. `ConstituentExpander`가 이번 범위에서 **도달 불가능**함을 테스트가 고정한다.

**검증 방법**
```bash
./gradlew test --tests '*DirectLensTest' --tests '*LookThroughLensTest'
```

- [ ] **Step 1: 테스트를 먼저 쓴다**

`LookThroughLensTest.java`:
```java
package com.stockproject.portfolio.domain.lens;

import com.stockproject.portfolio.domain.Line;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.*;

class LookThroughLensTest {

    private final ConstituentPort noData = new NoConstituentDataPort();
    private final ConstituentExpander unreachable = new ConstituentExpander() {
        @Override public List<Line> expand(Line etfLine) {
            throw new AssertionError("이번 범위에서 호출될 수 없다 — 2단계 자리");
        }
    };
    private final LookThroughLens lens = new LookThroughLens(noData, unreachable);

    /** 스펙 §3.4 — etf_coverage.state = UNAVAILABLE인 ETF는 전개하지 않고 ETF 행을 그대로 남긴다. */
    @Test
    void 구성종목_미확보_ETF는_전개하지_않고_남긴다() {
        List<Line> input = List.of(stock("005930", "14240000"), etf("133690", "11000000"));

        LensResult result = lens.apply(input);

        assertThat(result.lines()).isEqualTo(input);
        assertThat(result.undecomposedEtfCount()).isEqualTo(1);
        assertThat(result.undecomposedKrw()).isEqualByComparingTo("11000000");
        assertThat(result.constituentAsOfs()).isEmpty();   // 전개된 ETF가 없으면 기준일도 없다
    }

    /** 스펙 §9.1 렌즈 — 전개 후 Σ market_value가 전개 전과 일치한다(총합 보존). */
    @Test
    void 총합이_보존된다() {
        List<Line> input = List.of(stock("005930", "14240000"), etf("133690", "11000000"));

        LensResult result = lens.apply(input);

        assertThat(sum(result.lines())).isEqualByComparingTo(sum(input));
        new com.stockproject.portfolio.validation.LensOutputInvariants()
                .validateTotalPreserved(input, result.lines());   // 예외 없음
    }

    @Test
    void 기타_버킷을_만들지_않는다() {
        // 미확보 ETF를 기타 버킷에 넣으면 "ETF 내 비주식"과 뭉개진다(스펙 §3.4)
        LensResult result = lens.apply(List.of(etf("133690", "11000000")));
        assertThat(result.lines()).allSatisfy(l -> assertThat(l.instrumentKey()).isEqualTo("133690"));
    }

    private static BigDecimal sum(List<Line> lines) {
        return lines.stream().map(Line::marketValueKrw).reduce(BigDecimal.ZERO, BigDecimal::add);
    }
    // stock(), etf() 픽스처는 DerivedTest와 같은 방식으로 만든다 (assetClass만 다르다)
}
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `./gradlew test --tests '*LookThroughLensTest'` → 컴파일 실패.

- [ ] **Step 3: 인터페이스와 결과 타입**

```java
package com.stockproject.portfolio.domain.lens;

import com.stockproject.portfolio.domain.Line;
import java.util.List;

/**
 * 렌즈 — 입력도 라인 집합, 출력도 라인 집합인 변환 함수(스펙 §1.5 · §3.4).
 * 출력 스키마가 입력과 같으므로 하위의 집계·비중·환산 로직은 렌즈 적용 여부와 무관하다.
 */
public interface LensTransform {
    LensResult apply(List<Line> lines);
}
```

```java
package com.stockproject.portfolio.domain.lens;

import com.stockproject.portfolio.domain.Line;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

/**
 * 렌즈 산출물. 미분해 몫과 구성비중 기준일은 notice 재료다
 * (CONSTITUENT_UNAVAILABLE · CONSTITUENT_AS_OF — 스펙 §8.2).
 */
public record LensResult(List<Line> lines, int undecomposedEtfCount,
                         BigDecimal undecomposedKrw, List<LocalDate> constituentAsOfs) {

    public static LensResult identity(List<Line> lines) {
        return new LensResult(lines, 0, BigDecimal.ZERO, List.of());
    }
}
```

```java
package com.stockproject.portfolio.domain.lens;

public enum ConstituentCoverage { COVERED, UNAVAILABLE }
```

```java
package com.stockproject.portfolio.domain.lens;

import java.util.UUID;

/**
 * etf_coverage 조회 — 데이터팀 소유(스펙 §5.1 · §11.2).
 * "없음"과 "미확보"를 구분하는 것이 이 포트의 존재 이유다.
 */
public interface ConstituentPort {
    ConstituentCoverage coverageOf(UUID etfInstrumentId);
}
```

```java
package com.stockproject.portfolio.domain.lens;

import org.springframework.stereotype.Component;
import java.util.UUID;

/**
 * 구성비중 제공 형태가 팀 미합의라(설계 공유 문서 안건 3·8) 모든 ETF를 미확보로 본다.
 * 이 값이 스펙 §3.4가 정의한 정상 경로를 타게 하며, 사용자는 미분해 몫을 금액과 함께 안내받는다.
 */
@Component
public class NoConstituentDataPort implements ConstituentPort {
    @Override public ConstituentCoverage coverageOf(UUID etfInstrumentId) {
        return ConstituentCoverage.UNAVAILABLE;
    }
}
```

```java
package com.stockproject.portfolio.domain.lens;

import com.stockproject.portfolio.domain.Line;
import java.util.List;

/**
 * 2단계(ETF 안분)의 자리 — 스펙 §3.6 2단계.
 * ETF 평가금액 × 최종 구성비중 한 겹 곱셈으로 N개 라인을 만들고,
 * 반올림 잔차와 비중 미달분을 기타 버킷(GroupKey.OTHER)으로 흡수해 총합을 맞춘다.
 * 이번 범위에서는 구현체를 두지 않는다 — ConstituentPort가 COVERED를 내지 않으므로 도달 불가다.
 */
public interface ConstituentExpander {
    List<Line> expand(Line etfLine);
}
```

- [ ] **Step 4: 두 렌즈 구현**

```java
package com.stockproject.portfolio.domain.lens;

import com.stockproject.portfolio.domain.Line;
import org.springframework.stereotype.Component;
import java.util.List;

/** DIRECT — ETF를 한 종목으로 집계한다. 스펙 §3.6: 2단계를 건너뛴다. */
@Component
public class DirectLens implements LensTransform {
    @Override public LensResult apply(List<Line> lines) { return LensResult.identity(lines); }
}
```

```java
package com.stockproject.portfolio.domain.lens;

import com.stockproject.portfolio.domain.Line;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;

/** LOOK_THROUGH — ETF를 구성종목으로 분해한다. 미확보 ETF는 전개하지 않고 남긴다(스펙 §3.4). */
@Component
public class LookThroughLens implements LensTransform {

    private final ConstituentPort constituents;
    private final ConstituentExpander expander;

    public LookThroughLens(ConstituentPort constituents, ConstituentExpander expander) {
        this.constituents = constituents;
        this.expander = expander;
    }

    @Override
    public LensResult apply(List<Line> lines) {
        List<Line> out = new ArrayList<>();
        List<LocalDate> constituentAsOfs = new ArrayList<>();
        int undecomposedCount = 0;
        BigDecimal undecomposedKrw = BigDecimal.ZERO;
        Set<UUID> countedEtfs = new HashSet<>();

        for (Line line : lines) {
            if (!line.isEtf()) { out.add(line); continue; }

            if (constituents.coverageOf(line.instrumentId()) == ConstituentCoverage.UNAVAILABLE) {
                // 기타 버킷에 넣지 않는다 — "ETF 내 비주식"과 뭉개지기 때문(스펙 §3.4)
                out.add(line);
                if (countedEtfs.add(line.instrumentId())) undecomposedCount++;
                undecomposedKrw = undecomposedKrw.add(line.marketValueKrw());
            } else {
                out.addAll(expander.expand(line));
            }
        }
        return new LensResult(List.copyOf(out), undecomposedCount, undecomposedKrw,
                List.copyOf(constituentAsOfs));
    }
}
```

`ConstituentExpander` 구현체가 없으므로 스프링 컨텍스트가 뜨지 않는다. **`@ConditionalOnMissingBean`으로 도달 불가 구현을 하나 등록한다** — 이것이 "자리만 남긴다"의 실체다:
```java
package com.stockproject.portfolio.domain.lens;

import org.springframework.stereotype.Component;
import com.stockproject.portfolio.domain.Line;
import java.util.List;

/** 2단계 미구현 자리. ConstituentPort가 COVERED를 내지 않는 동안 이 메서드는 도달 불가다. */
@Component
public class UnreachableConstituentExpander implements ConstituentExpander {
    @Override public List<Line> expand(Line etfLine) {
        throw new IllegalStateException(
                "ETF 안분은 2단계 범위다. 구성비중 제공 형태 합의 후 구현한다 — 스펙 §3.6 2단계");
    }
}
```

- [ ] **Step 5: 총합 보존 검증기**

```java
package com.stockproject.portfolio.validation;

import com.stockproject.portfolio.domain.Line;

import java.math.BigDecimal;
import java.util.List;

/** 스펙 §9.1 렌즈 — look-through 전개 후 Σ market_value가 전개 전과 일치한다(기타 버킷 포함). */
public class LensOutputInvariants {

    public void validateTotalPreserved(List<Line> before, List<Line> after) {
        BigDecimal b = sum(before);
        BigDecimal a = sum(after);
        if (b.compareTo(a) != 0) {
            throw new FactInvariantViolation(List.of(
                    "렌즈 총합 보존 위반: 전개 전 %s ≠ 전개 후 %s".formatted(b, a)));
        }
    }

    private static BigDecimal sum(List<Line> lines) {
        return lines.stream().map(Line::marketValueKrw).reduce(BigDecimal.ZERO, BigDecimal::add);
    }
}
```

- [ ] **Step 6: 도달 불가를 고정하는 테스트**

```java
    /** 2단계 자리가 실제로 도달 불가임을 고정한다. 구현이 붙는 순간 이 테스트를 지운다. */
    @Test
    void 안분_구현은_이번_범위에서_도달_불가다() {
        assertThat(new NoConstituentDataPort().coverageOf(UUID.randomUUID()))
                .isEqualTo(ConstituentCoverage.UNAVAILABLE);
        assertThatThrownBy(() -> new UnreachableConstituentExpander().expand(null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("2단계");
    }
```

- [ ] **Step 7: 테스트 통과 → 커밋**

```bash
./gradlew test --tests '*Lens*'
git add -A && git commit -m "feat: 렌즈 인터페이스 · DIRECT 경로 · LOOK_THROUGH 미확보 분기"
```

---

### Task 6: 집계 엔진 (§3.6 4~5단계)

**Files:**
- Create: `domain/group/AggregationEngine.java`
- Test: `test/.../domain/group/AggregationEngineTest.java`

**Interfaces:**
- Consumes: Task 3의 `Line` · `MeasureBundle` · `GroupNode` · `GroupKey` · `Aggregation` · `TotalAssetsKrw`, Task 2의 `AxisKey.keyOf(Line)`
- Produces: `Aggregation AggregationEngine.aggregate(List<Line> lines, List<AxisKey> groupBy)`

**완료 조건**
1. `groupBy = []`이면 `rows`가 비고 `responseTotal`만 채워진다(요약).
2. `groupBy = [SECTOR]`이면 §C.6의 5행이 **평가금액 내림차순**으로 나오고 `현금`·`미분류` 폴백이 적용된다.
3. `groupBy = [ACCOUNT_TYPE, ACCOUNT]`이면 2단계 중첩이 나오고 **자식 합 = 부모**가 성립한다.
4. `Σ rows.total().marketValueKrw() == responseTotal.total().marketValueKrw()` — 모든 `groupBy`에서 성립한다.
5. `기타` 버킷(`GroupKey.other = true`)은 금액과 무관하게 항상 맨 끝이다.

**검증 방법**
```bash
./gradlew test --tests '*AggregationEngineTest'
```

- [ ] **Step 1: 총합 보존과 정렬 테스트를 먼저 쓴다**

```java
package com.stockproject.portfolio.domain.group;

import com.stockproject.portfolio.catalog.AxisKey;
import com.stockproject.portfolio.domain.Line;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class AggregationEngineTest {

    private final AggregationEngine engine = new AggregationEngine();

    /** 스펙 §8.3 — Σ rows.market_value_krw = total.total_assets_krw가 항상 성립한다. */
    @Test
    void 행_합이_전체_합계와_같다() {
        List<Line> lines = sampleLines();          // §C.3의 10행 (테스트 픽스처로 재현)

        for (List<AxisKey> groupBy : List.of(
                List.of(AxisKey.SECTOR), List.of(AxisKey.MARKET),
                List.of(AxisKey.INSTRUMENT), List.of(AxisKey.ASSET_CLASS),
                List.of(AxisKey.ACCOUNT_TYPE, AxisKey.ACCOUNT))) {

            Aggregation agg = engine.aggregate(lines, groupBy);
            BigDecimal rowSum = agg.rows().stream()
                    .map(n -> n.measures().total().marketValueKrw())
                    .reduce(BigDecimal.ZERO, BigDecimal::add);

            assertThat(rowSum)
                    .as("group_by=%s에서 Σ rows ≠ total", groupBy)
                    .isEqualByComparingTo(agg.responseTotal().total().marketValueKrw());
            assertThat(rowSum).isEqualByComparingTo("58000000");
        }
    }

    /** 스펙 §6.1 폴백 — CASH는 현금, sector가 null인 종목은 미분류로 모인다. */
    @Test
    void 섹터_축의_폴백과_정렬() {
        Aggregation agg = engine.aggregate(sampleLines(), List.of(AxisKey.SECTOR));

        assertThat(agg.rows()).extracting(n -> n.key().label())
                .containsExactly("반도체", "소프트웨어", "미분류", "IT서비스", "현금");
        assertThat(agg.rows()).extracting(n -> n.measures().total().marketValueKrw().longValue())
                .containsExactly(23_240_000L, 12_900_000L, 11_000_000L, 6_160_000L, 4_700_000L);
    }

    /** 스펙 §8.3 — group_by가 2단계면 rows[].rows로 중첩되고 소계는 서버가 계산한다. */
    @Test
    void 계좌유형_소계가_자식_합과_같다() {
        Aggregation agg = engine.aggregate(sampleLines(),
                List.of(AxisKey.ACCOUNT_TYPE, AxisKey.ACCOUNT));

        assertThat(agg.rows()).hasSize(2);
        for (GroupNode parent : agg.rows()) {
            BigDecimal childSum = parent.children().stream()
                    .map(c -> c.measures().total().marketValueKrw())
                    .reduce(BigDecimal.ZERO, BigDecimal::add);
            assertThat(childSum).isEqualByComparingTo(parent.measures().total().marketValueKrw());
        }
        assertThat(agg.rows().get(0).key().label()).isEqualTo("일반");
        assertThat(agg.rows().get(0).measures().total().marketValueKrw())
                .isEqualByComparingTo("40960000");
    }

    /** 스펙 §3.6 6단계 — 기타 버킷은 금액과 무관하게 항상 맨 끝. */
    @Test
    void 기타_버킷은_금액이_커도_맨_끝이다() {
        List<Line> lines = List.of(other("50000000"), stock("반도체", "1000000"));
        Aggregation agg = engine.aggregate(lines, List.of(AxisKey.SECTOR));

        assertThat(agg.rows()).extracting(n -> n.key().other()).containsExactly(false, true);
    }

    @Test
    void group_by가_비면_total만_채워진다() {
        Aggregation agg = engine.aggregate(sampleLines(), List.of());

        assertThat(agg.rows()).isEmpty();
        assertThat(agg.responseTotal().total().marketValueKrw()).isEqualByComparingTo("58000000");
        assertThat(Derived.securitiesValueKrw(agg.responseTotal())).isEqualByComparingTo("53300000");
        assertThat(Derived.depositKrw(agg.responseTotal())).isEqualByComparingTo("4700000");
        assertThat(Derived.costAmountKrw(agg.responseTotal())).isEqualByComparingTo("48800000");
        assertThat(Derived.unrealizedPnlKrw(agg.responseTotal())).isEqualByComparingTo("4500000");
        assertThat(Derived.unrealizedPnlPct(agg.responseTotal())).isEqualByComparingTo("9.2");
        assertThat(Derived.cashRatioPct(agg.responseTotal(), agg.weightDenominator()))
                .isEqualByComparingTo("8.1");
        assertThat(Derived.instrumentCount(agg.responseTotal())).isEqualTo(5);
        assertThat(Derived.accountCount(agg.responseTotal())).isEqualTo(4);
    }

    // sampleLines()는 §C.3 표의 10행을 그대로 만드는 픽스처.
    // 픽스처는 test/.../fixture/SampleLines.java에 두고 Task 8·11에서 재사용한다.
}
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `./gradlew test --tests '*AggregationEngineTest'` → 컴파일 실패(`AggregationEngine` 없음).

- [ ] **Step 3: 픽스처를 만든다**

`src/test/java/com/stockproject/portfolio/fixture/SampleLines.java` — §C.3 표의 10행을 `List<Line>`으로 만드는 정적 팩터리. Task 8·11이 재사용한다.

```java
public final class SampleLines {
    public static final UUID ACC_KIS_GENERAL = UUID.fromString("20000000-0000-0000-0000-000000000001");
    // … 계좌 4개 · 종목 8개 UUID 상수
    public static List<Line> asOf20260727() { /* §C.3 표 그대로 10행 */ }
    public static List<Line> asOf20260724() { /* 삼성전자 평가금액만 13,040,000 */ }
}
```

- [ ] **Step 4: 집계 엔진 구현**

```java
package com.stockproject.portfolio.domain.group;

import com.stockproject.portfolio.catalog.AxisKey;
import com.stockproject.portfolio.domain.Line;
import com.stockproject.portfolio.domain.measure.MeasureBundle;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.*;

/**
 * 스펙 §3.6 4단계(GROUP BY + SUM). 이 설계의 핵심 주장이 구현되는 자리다 —
 * 저장은 position_line 한 종류이고 화면은 group_by만 바꾼다.
 * 집계 값은 가산 측정값(MeasureBundle)만 담고 비율은 담지 않는다(§1.5).
 */
@Component
public class AggregationEngine {

    public Aggregation aggregate(List<Line> lines, List<AxisKey> groupBy) {
        return new Aggregation(bundleOf(lines), group(lines, groupBy, 0));
    }

    private List<GroupNode> group(List<Line> lines, List<AxisKey> axes, int depth) {
        if (depth >= axes.size()) return List.of();

        AxisKey axis = axes.get(depth);
        Map<GroupKey, List<Line>> buckets = new LinkedHashMap<>();
        for (Line line : lines) {
            buckets.computeIfAbsent(axis.keyOf(line), k -> new ArrayList<>()).add(line);
        }

        List<GroupNode> nodes = new ArrayList<>(buckets.size());
        buckets.forEach((key, bucketLines) ->
                nodes.add(new GroupNode(key, bundleOf(bucketLines),
                        group(bucketLines, axes, depth + 1))));

        nodes.sort(ORDER);
        return List.copyOf(nodes);
    }

    /** 스펙 §3.6 6단계 — 평가금액 내림차순, 기타 버킷은 항상 맨 끝. */
    private static final Comparator<GroupNode> ORDER =
            Comparator.<GroupNode, Boolean>comparing(n -> n.key().other())
                    .thenComparing(n -> n.measures().total().marketValueKrw(),
                                   Comparator.reverseOrder())
                    .thenComparing(n -> n.key().key());

    private static MeasureBundle bundleOf(List<Line> lines) {
        MeasureBundle acc = MeasureBundle.EMPTY;
        for (Line line : lines) acc = acc.plus(MeasureBundle.of(line));
        return acc;
    }
}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `./gradlew test --tests '*AggregationEngineTest'` → PASS. 특히 `9.2`·`8.1`·`53300000`이 §C.5와 일치해야 한다.

- [ ] **Step 6: 커밋**

```bash
git add -A && git commit -m "feat: 집계 엔진 — group_by + SUM + 2단계 중첩"
```

---

### Task 7: 응답 조립 — 봉투 · notice 16종 · empty_reason · 통화 · lens_safe

**Files:**
- Create: `api/dto/Envelope.java` · `NoticeDto.java` · `RowDto.java` · `SnapshotViewData.java`
- Create: `view/assembly/RowValuePolicy.java` · `CurrencyDisplayPolicy.java` · `NoticeCollector.java` · `NoticeCode.java` · `EmptyReason.java` · `EmptyReasonResolver.java` · `SnapshotResponseAssembler.java`
- Test: `test/.../view/assembly/RowValuePolicyTest.java` · `CurrencyDisplayPolicyTest.java` · `NoticeCollectorTest.java` · `EmptyReasonResolverTest.java`

**Interfaces:**
- Consumes: Task 2 카탈로그, Task 3 `Derived`, Task 6 `Aggregation`, Task 5 `LensResult`
- Produces:
  - `Envelope<T>(OffsetDateTime asOf, T data, String emptyReason, List<NoticeDto> notices)`
  - `RowDto(String key, String label, Map<String,Object> metrics, List<RowDto> rows)` — `metrics`는 `@JsonAnyGetter`로 평탄화된다
  - `SnapshotViewData(List<String> groupBy, Lens lens, Map<String,Object> total, List<RowDto> rows, SnapshotViewData miniChart)`
  - `SnapshotResponseAssembler.assemble(ViewSpec, Lens, Aggregation, AssemblyContext)`
  - `NoticeCollector.collect(AssemblyContext)` → `List<NoticeDto>` (§A.5.2 순서 고정)

**완료 조건**
1. `LOOK_THROUGH`에서 `rows[]`의 `cost_amount_krw`·`unrealized_pnl_krw`·`unrealized_pnl_pct` **키가 사라진다**(`null`이 아니다). `total`에는 남는다.
2. CASH 행의 원가·손익은 **키는 있고 값이 `null`**이다.
3. `market_value_krw`가 `total`에 없고 `total_assets_krw`가 `rows[]`에 없다(불변식 4).
4. 섹터 그룹에 현지 통화가 실리지 않고, 통화·종목 그룹의 단일 USD 그룹에는 실린다. 단일 KRW 그룹에는 실리지 않는다.
5. notice 16종이 enum으로 존재하고, 발화 조건이 있는 것들이 §A.5.2 순서대로 나온다.
6. `empty_reason` 판정 순서가 §A.5.3대로 동작한다.

**검증 방법**
```bash
./gradlew test --tests '*RowValuePolicyTest' --tests '*CurrencyDisplayPolicyTest' \
               --tests '*NoticeCollectorTest' --tests '*EmptyReasonResolverTest'
```

- [ ] **Step 1: `lens_safe` 제외와 CASH null 테스트를 먼저 쓴다**

```java
package com.stockproject.portfolio.view.assembly;

import com.stockproject.portfolio.catalog.*;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class RowValuePolicyTest {

    private final RowValuePolicy policy = new RowValuePolicy();

    /** 스펙 §8.3 · §9.3 — LOOK_THROUGH에서 TOTAL_ONLY 지표는 rows[]에서 사라진다(키 부재). */
    @Test
    void LOOK_THROUGH에서_TOTAL_ONLY_지표_키가_사라진다() {
        Map<String, Object> row = policy.rowMetrics(
                Catalog.view(ViewKey.ALLOCATION), Lens.LOOK_THROUGH, sectorNode(), denominator());

        assertThat(row).containsKeys("market_value_krw", "weight_pct", "instrument_count");
        assertThat(row).doesNotContainKeys("cost_amount_krw", "unrealized_pnl_krw", "unrealized_pnl_pct");
    }

    @Test
    void DIRECT에서는_TOTAL_ONLY_지표가_행에_남는다() {
        Map<String, Object> row = policy.rowMetrics(
                Catalog.view(ViewKey.ALLOCATION), Lens.DIRECT, sectorNode(), denominator());

        assertThat(row).containsKeys("cost_amount_krw", "unrealized_pnl_krw", "unrealized_pnl_pct");
    }

    /** 스펙 §5.2 · §8.3 — CASH 행의 원가·손익은 키를 남기고 값만 null로 내린다. */
    @Test
    void CASH_행의_원가와_손익은_null이다() {
        Map<String, Object> row = policy.rowMetrics(
                Catalog.view(ViewKey.ALLOCATION), Lens.DIRECT, cashNode(), denominator());

        assertThat(row).containsEntry("cost_amount_krw", null)
                       .containsEntry("unrealized_pnl_krw", null)
                       .containsEntry("unrealized_pnl_pct", null);
        assertThat(row.get("market_value_krw")).isNotNull();
    }

    /** 불변식 4 — 행 전용 키와 합계 전용 키가 서로의 자리에 나타나지 않는다. */
    @Test
    void 행과_합계의_키가_겹치지_않는다() {
        Map<String, Object> row   = policy.rowMetrics(Catalog.view(ViewKey.ALLOCATION),
                                                      Lens.DIRECT, sectorNode(), denominator());
        Map<String, Object> total = policy.totalMetrics(Catalog.view(ViewKey.ALLOCATION),
                                                        aggregation());

        assertThat(row).doesNotContainKeys("total_assets_krw", "securities_value_krw",
                                           "deposit_krw", "cash_ratio_pct", "account_count");
        assertThat(total).doesNotContainKey("market_value_krw");
    }
}
```

- [ ] **Step 2: 통화 표시 정책 테스트**

```java
class CurrencyDisplayPolicyTest {

    private final CurrencyDisplayPolicy policy = new CurrencyDisplayPolicy();

    /** 불변식 3 — 두 게이트를 모두 통과할 때만 병기한다. */
    @Test
    void 섹터_축은_단일_통화여도_병기하지_않는다() {
        // IT서비스 그룹은 AAPL 하나라 실제로 단일 USD지만, 섹터 축은 §3.7 표에서 ✗다
        assertThat(policy.localOf(AxisKey.SECTOR, usdOnlyBundle())).isEmpty();
    }

    @Test
    void 종목_축의_단일_USD_그룹에는_병기한다() {
        assertThat(policy.localOf(AxisKey.INSTRUMENT, usdOnlyBundle()))
                .get().extracting(LocalMoney::currency).isEqualTo(CurrencyCode.USD);
    }

    @Test
    void 통화가_섞이면_병기하지_않는다() {
        assertThat(policy.localOf(AxisKey.INSTRUMENT, mixedBundle())).isEmpty();
    }

    /** 원화가 곧 현지 통화이므로 병기가 중복이다. */
    @Test
    void 단일_KRW_그룹에는_병기하지_않는다() {
        assertThat(policy.localOf(AxisKey.INSTRUMENT, krwOnlyBundle())).isEmpty();
    }
}
```

`CurrencyDisplayPolicy` 구현:
```java
package com.stockproject.portfolio.view.assembly;

import com.stockproject.portfolio.catalog.AxisKey;
import com.stockproject.portfolio.domain.CurrencyCode;
import com.stockproject.portfolio.domain.measure.LocalMoney;
import com.stockproject.portfolio.domain.measure.MeasureBundle;
import org.springframework.stereotype.Component;

import java.util.Optional;

/**
 * 불변식 3 — 집계 값은 항상 원화, 묶음이 단일 통화일 때만 현지 통화 병기(스펙 §3.7 · §9.3).
 * 게이트가 두 겹이다: 축이 병기 가능해야 하고(§3.7 표), 묶음의 통화 집합이 실제로 하나여야 한다(§3.7 본문).
 */
@Component
public class CurrencyDisplayPolicy {

    public Optional<LocalMoney> localOf(AxisKey axis, MeasureBundle bundle) {
        if (axis != null && !axis.localCurrencyEligible()) return Optional.empty();
        return bundle.currencies().single()
                .filter(c -> c != CurrencyCode.KRW)          // 원화는 병기가 중복이다
                .map(c -> new LocalMoney(c,
                        bundle.total().marketValueLocal(),
                        bundle.securities().costAmountLocal()));
    }
}
```

`LocalMoney`:
```java
package com.stockproject.portfolio.domain.measure;

import com.stockproject.portfolio.domain.CurrencyCode;
import java.math.BigDecimal;

public record LocalMoney(CurrencyCode currency, BigDecimal marketValue, BigDecimal costAmount) { }
```

- [ ] **Step 3: notice 16종**

```java
package com.stockproject.portfolio.view.assembly;

/** 스펙 §8.2. 순서가 곧 응답의 notices 정렬 순서다(골든 테스트 안정성). */
public enum NoticeCode {
    FX_APPLIED(Severity.INFO),
    STALE_ACCOUNTS(Severity.WARN),
    CONSTITUENT_AS_OF(Severity.INFO),
    CONSTITUENT_UNAVAILABLE(Severity.WARN),
    LENS_METRICS_OMITTED(Severity.INFO),
    EXCLUDED_ACCOUNTS(Severity.WARN),
    SEEDED_ROWS(Severity.WARN),
    CA_UNKNOWN(Severity.WARN),
    CASHFLOW_UNCOVERED(Severity.WARN),
    PERIOD_TRUNCATED(Severity.INFO),
    BOUNDARY_CARRIED_FORWARD(Severity.WARN),
    REAUTH_REQUIRED(Severity.WARN),
    SYNC_IN_PROGRESS(Severity.INFO),
    PRICE_LAG_MARKET(Severity.INFO),
    ALREADY_FINAL(Severity.INFO),
    FX_STALE(Severity.WARN);

    public enum Severity { INFO, WARN, ERROR;
        public String wire() { return name().toLowerCase(); } }

    private final Severity severity;
    NoticeCode(Severity severity) { this.severity = severity; }
    public Severity severity() { return severity; }
}
```

`NoticeCollector`는 `AssemblyContext`를 받아 발화 조건을 판정한다. `AssemblyContext`는 조립에 필요한 사실을 모은 record:
```java
public record AssemblyContext(
        LocalDate asOf, OffsetDateTime bannerAsOf, Lens lens,
        List<Line> factLines,                 // 필터 전 라인 (STALE_ACCOUNTS · FX_APPLIED 재료)
        List<Line> lensedLines,               // 렌즈·필터 후 라인
        LensResult lensResult,
        List<MetricKey> omittedRowMetrics,
        List<AccountRow> accounts,
        int seededRowCount, int excludedAccountCount,
        LocalDate periodActualFrom, int boundaryCarriedForwardCount, LocalDate boundaryDate,
        int cashflowUncoveredAccountCount) { }
```

발화 규칙(§A.5.2 표를 코드로):

| code | 판정 |
|---|---|
| `FX_APPLIED` | `factLines`에서 `currency != KRW`인 라인의 `(통화쌍, fx_rate, fx_as_of)`를 모은다. 비어 있지 않으면 발화. `oldest_fx_as_of` = `min(fx_as_of)` |
| `STALE_ACCOUNTS` | `factLines`에서 `carriedForward = true`인 라인의 **distinct 계좌 수** > 0. `oldest` = `min(source_as_of)`의 날짜 |
| `CONSTITUENT_UNAVAILABLE` | `lensResult.undecomposedEtfCount() > 0` |
| `CONSTITUENT_AS_OF` | `lensResult.constituentAsOfs()`가 비어 있지 않을 때만 |
| `LENS_METRICS_OMITTED` | `omittedRowMetrics`가 비어 있지 않을 때 |
| `SEEDED_ROWS` | `seededRowCount > 0` |
| `EXCLUDED_ACCOUNTS` | `excludedAccountCount > 0` |
| `CASHFLOW_UNCOVERED` | `cashflowUncoveredAccountCount > 0` |
| `PERIOD_TRUNCATED` | `periodActualFrom != null` |
| `BOUNDARY_CARRIED_FORWARD` | `boundaryCarriedForwardCount > 0` |
| `REAUTH_REQUIRED` | `accounts`에 `link_state = REAUTH_REQUIRED`가 있을 때 |
| `FX_STALE` | `as_of − fx_as_of`가 5영업일 초과. **영업일 계산기가 없으므로 이번 범위에서는 달력일 7일로 근사하고 그 사실을 주석에 남긴다** |
| `CA_UNKNOWN` · `SYNC_IN_PROGRESS` · `PRICE_LAG_MARKET` · `ALREADY_FINAL` | 이번 범위에서 발화하지 않는다(§A.5.2) — enum과 메시지 템플릿만 둔다 |

메시지는 코드별 템플릿 메서드로 만든다. 예:
```java
    private static String staleAccountsMessage(int count, LocalDate oldest) {
        return "%d개 계좌가 %s 기준입니다".formatted(count, MM_DD.format(oldest));
    }
```

- [ ] **Step 4: notice 테스트**

```java
    @Test
    void 캐리포워드_계좌가_있으면_STALE_ACCOUNTS가_뜬다() {
        List<NoticeDto> notices = collector.collect(contextWithCarriedForward());

        assertThat(notices).extracting(NoticeDto::code)
                .containsExactly("FX_APPLIED", "STALE_ACCOUNTS");   // §A.5.2 순서
        NoticeDto stale = notices.get(1);
        assertThat(stale.severity()).isEqualTo("warn");
        assertThat(stale.message()).isEqualTo("1개 계좌가 07-24 기준입니다");
        assertThat(stale.params()).containsEntry("count", 1)
                                  .containsEntry("oldest", LocalDate.of(2026, 7, 24));
    }

    @Test
    void 렌즈를_켜면_미분해_ETF와_생략_지표를_알린다() {
        List<NoticeDto> notices = collector.collect(lookThroughContext());

        assertThat(notices).extracting(NoticeDto::code)
                .contains("CONSTITUENT_UNAVAILABLE", "LENS_METRICS_OMITTED")
                .doesNotContain("CONSTITUENT_AS_OF");     // 전개된 ETF가 없다
    }
```

- [ ] **Step 5: `empty_reason` 판정기**

```java
package com.stockproject.portfolio.view.assembly;

/** 스펙 §8.2 — 빈 상태는 notices가 아니라 봉투 필드다. */
public enum EmptyReason {
    NO_ACCOUNTS, NO_HOLDINGS, NO_MATCH_FILTER, NO_TRADES_IN_PERIOD, ALL_UNAVAILABLE
}
```

```java
/**
 * 판정 순서를 고정한다(계획 §A.5.3): NO_ACCOUNTS → NO_HOLDINGS
 *   → (realized-pnl이면 NO_TRADES_IN_PERIOD → ALL_UNAVAILABLE) → NO_MATCH_FILTER.
 * 먼저 맞는 것 하나만 내린다.
 */
@Component
public class EmptyReasonResolver {

    public EmptyReason resolveSnapshot(List<AccountRow> accounts, int factLineCount, int filteredCount) {
        if (accounts.stream().allMatch(a -> a.linkState() == LinkState.DISCONNECTED)) return EmptyReason.NO_ACCOUNTS;
        if (factLineCount == 0) return EmptyReason.NO_HOLDINGS;
        if (filteredCount == 0) return EmptyReason.NO_MATCH_FILTER;
        return null;
    }

    public EmptyReason resolveRealizedPnl(List<AccountRow> accounts, int periodRowCount, int includedCount) {
        if (accounts.stream().allMatch(a -> a.linkState() == LinkState.DISCONNECTED)) return EmptyReason.NO_ACCOUNTS;
        if (periodRowCount == 0) return EmptyReason.NO_TRADES_IN_PERIOD;
        if (includedCount == 0) return EmptyReason.ALL_UNAVAILABLE;
        return null;
    }
}
```

빈 계좌 목록(`accounts.isEmpty()`)도 `NO_ACCOUNTS`다 — `allMatch`가 빈 목록에 대해 `true`를 내므로 자연히 처리된다.

- [ ] **Step 6: 봉투와 행 DTO**

```java
package com.stockproject.portfolio.api.dto;

import java.time.OffsetDateTime;
import java.util.List;

/** 스펙 §8.2 — 모든 뷰 응답이 같은 봉투를 쓴다. */
public record Envelope<T>(OffsetDateTime asOf, T data, String emptyReason, List<NoticeDto> notices) {

    public static <T> Envelope<T> of(OffsetDateTime asOf, T data,
                                     EmptyReason reason, List<NoticeDto> notices) {
        return new Envelope<>(asOf, data, reason == null ? null : reason.name(), notices);
    }
}
```

```java
package com.stockproject.portfolio.api.dto;

import com.fasterxml.jackson.annotation.JsonAnyGetter;
import com.fasterxml.jackson.annotation.JsonInclude;
import java.util.List;
import java.util.Map;

/**
 * 공통 행 스키마(스펙 §8.3). 지표를 Map으로 담는 이유는
 * LOOK_THROUGH에서 TOTAL_ONLY 지표의 "키 부재"와 CASH 행의 "값 null"을 구분해야 하기 때문이다.
 */
public record RowDto(String key, String label,
                     @JsonInclude(JsonInclude.Include.NON_NULL) String currency,
                     @JsonAnyGetter Map<String, Object> metrics,
                     @JsonInclude(JsonInclude.Include.NON_NULL) List<RowDto> rows) { }
```

```java
package com.stockproject.portfolio.api.dto;

import java.util.Map;

/** 스펙 §8.2 — message는 서버가 완성해 내리고 클라이언트는 code로 분기한다. */
public record NoticeDto(String code, String severity, String message, Map<String, Object> params) { }
```

- [ ] **Step 7: `RowValuePolicy` — lens_safe 제외와 CASH null을 한 곳에 모은다**

```java
package com.stockproject.portfolio.view.assembly;

import com.stockproject.portfolio.catalog.*;
import com.stockproject.portfolio.domain.group.*;
import com.stockproject.portfolio.domain.measure.MeasureBundle;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 행·합계에 어떤 지표를 어떤 값으로 실을지 결정하는 유일한 지점.
 * 불변식 4(행/합계 키 분리)와 스펙 §9.3(lens_safe 제외), §5.2(CASH 행 null)를 여기서 강제한다.
 */
@Component
public class RowValuePolicy {

    /** 행 지표. LOOK_THROUGH에서 TOTAL_ONLY·NEVER 지표는 키 자체를 넣지 않는다. */
    public Map<String, Object> rowMetrics(ViewSpec view, Lens lens,
                                          GroupNode node, TotalAssetsKrw denominator) {
        Map<String, Object> out = new LinkedHashMap<>();
        boolean cashRow = isCashOnly(node.measures());

        for (MetricKey key : view.metrics()) {
            Metric metric = Metric.of(key);
            if (metric.scope() == MetricScope.TOTAL) continue;                 // 불변식 4
            if (lens == Lens.LOOK_THROUGH
                    && metric.lensSafety() != LensSafety.ROW_AND_TOTAL) continue;  // §9.3

            // CASH 행의 원가·손익은 키를 남기고 값만 null로 내린다 (§5.2 · §8.3)
            boolean nullForCash = cashRow && metric.cashScope() == CashScope.EXCLUDED;
            out.put(key.key(), nullForCash ? null : rowValue(key, node, denominator));
        }
        return out;
    }

    /** 합계 지표. 행 전용 키(market_value_krw)는 절대 넣지 않는다. */
    public Map<String, Object> totalMetrics(ViewSpec view, Aggregation agg) {
        Map<String, Object> out = new LinkedHashMap<>();
        for (MetricKey key : view.metrics()) {
            if (Metric.of(key).scope() == MetricScope.ROW) continue;           // 불변식 4
            out.put(key.key(), totalValue(key, agg));
        }
        return out;
    }

    private Object rowValue(MetricKey key, GroupNode node, TotalAssetsKrw denominator) {
        MeasureBundle b = node.measures();
        return switch (key) {
            case MARKET_VALUE_KRW    -> b.total().marketValueKrw();
            case QUANTITY            -> b.total().quantity();
            case COST_AMOUNT_KRW     -> Derived.costAmountKrw(b);
            case UNREALIZED_PNL_KRW  -> Derived.unrealizedPnlKrw(b);
            case UNREALIZED_PNL_PCT  -> Derived.unrealizedPnlPct(b);
            case WEIGHT_PCT          -> Derived.weightPct(b, denominator);
            case INSTRUMENT_COUNT    -> Derived.instrumentCount(b);
            case DEPOSIT_KRW         -> Derived.depositKrw(b);
            case AVG_COST            -> b.currencies().single()
                                          .map(c -> Derived.avgCost(b, c)).orElse(null);
            default -> throw new IllegalStateException("행에 실을 수 없는 지표: " + key);
        };
    }

    private Object totalValue(MetricKey key, Aggregation agg) {
        MeasureBundle b = agg.responseTotal();
        return switch (key) {
            case TOTAL_ASSETS_KRW     -> Derived.totalAssetsKrw(b);
            case SECURITIES_VALUE_KRW -> Derived.securitiesValueKrw(b);
            case DEPOSIT_KRW          -> Derived.depositKrw(b);
            case COST_AMOUNT_KRW      -> Derived.costAmountKrw(b);
            case UNREALIZED_PNL_KRW   -> Derived.unrealizedPnlKrw(b);
            case UNREALIZED_PNL_PCT   -> Derived.unrealizedPnlPct(b);
            case CASH_RATIO_PCT       -> Derived.cashRatioPct(b, agg.weightDenominator());
            case INSTRUMENT_COUNT     -> Derived.instrumentCount(b);
            case ACCOUNT_COUNT        -> Derived.accountCount(b);
            default -> throw new IllegalStateException("합계에 실을 수 없는 지표: " + key);
        };
    }

    /** CASH 전용 행 판정 — securities 슬롯이 비어 있고 cash 슬롯에 값이 있다. */
    private static boolean isCashOnly(MeasureBundle b) {
        return b.securities().marketValueKrw().signum() == 0
                && b.cash().marketValueKrw().signum() != 0;
    }
}
```

`AVG_COST`가 `lensSafety = NEVER`라 `LOOK_THROUGH`에서 자동으로 빠진다 — §3.4의 "평단가는 정의 불가, 컬럼 숨김"이 카탈로그 한 줄로 강제된다. `daily_change_*`는 `totalValue`의 `default`에 걸리므로 요약 서비스가 별도로 넣는다(직전 스냅샷이 필요해 `Aggregation`만으로는 계산할 수 없다).

- [ ] **Step 8: `SnapshotResponseAssembler`**

`assemble(ViewSpec view, Lens lens, AxisKey rowAxis, Aggregation agg, AssemblyContext ctx)`가 하는 일:
1. `totalMetrics` — `view.metrics()` 중 `scope != ROW`인 것을 `Derived`로 계산해 `Map`에 담는다. `market_value_krw`는 절대 넣지 않는다.
2. `rows` — `agg.rows()`를 `RowDto`로 바꾼다. 지표는 `RowValuePolicy.rowMetrics(...)`가 결정하고, 현지 통화는 `CurrencyDisplayPolicy.localOf(rowAxis, node.measures())`가 결정한다. 자식이 있으면 재귀.
3. `lens == LOOK_THROUGH`이면 `omittedRowMetrics`를 `AssemblyContext`에 넣어 `LENS_METRICS_OMITTED`가 뜨게 한다.
4. `accounts` 뷰이면 자식 노드에 `rowFields`(`link_state`·`last_collection`·`last_synced_at`)를, `positions` 뷰이면 `market`을 더한다.

- [ ] **Step 9: 테스트 통과 → 커밋**

```bash
./gradlew test --tests '*view.assembly.*'
git add -A && git commit -m "feat: 응답 조립 — 봉투 · notice 16종 · empty_reason · 통화 · lens_safe"
```

---

### Task 8: 스냅샷 4개 뷰 엔드포인트와 요청 검증

**Files:**
- Create: `view/SnapshotViewService.java` · `validation/RequestValidator.java` · `api/ViewController.java` · `api/CatalogController.java` · `api/ApiExceptionHandler.java` · `api/dto/CatalogDto.java` · `api/ApiError.java`
- Test: `test/.../api/SnapshotViewApiTest.java` · `test/.../validation/RequestValidatorTest.java`

**Interfaces:**
- Consumes: Task 4 저장소·검증기, Task 5 렌즈, Task 6 엔진, Task 7 조립기
- Produces:
  - `Envelope<SnapshotViewData> SnapshotViewService.summary(Lens miniChartLens, AxisKey miniChartAxis)`
  - `Envelope<SnapshotViewData> SnapshotViewService.positions(Lens, LineFilter)`
  - `Envelope<SnapshotViewData> SnapshotViewService.allocation(AxisKey, Lens, LineFilter)`
  - `Envelope<SnapshotViewData> SnapshotViewService.accounts()`
  - `void RequestValidator.validateSnapshotRequest(ViewKey, AxisKey axisOrNull, Lens, Map<String,List<String>> filters)`

**완료 조건**
1. 4개 엔드포인트가 `200`과 §C.5·C.6·C.8·C.9의 값을 낸다.
2. `?axis=is_leveraged` → `400 AXIS_DISABLED`. `?axis=sector`를 `positions`에 → `400 AXIS_NOT_APPLICABLE`.
3. `positions?lens=LOOK_THROUGH&market=US` → `400 LENS_SENSITIVE_FILTER_REJECTED`.
4. `accounts?lens=LOOK_THROUGH` → `400 LENS_NOT_ALLOWED`.
5. 계좌가 없으면 `200` + `empty_reason: NO_ACCOUNTS`.
6. `GET /portfolio/catalog`이 렌즈 상태별 허용 필터를 내린다.

**검증 방법**
```bash
./gradlew test --tests '*SnapshotViewApiTest' --tests '*RequestValidatorTest'
# 그리고 실물 확인
curl -s 'localhost:8080/portfolio/views/allocation?axis=sector&lens=DIRECT' | jq .
curl -s -o /dev/null -w '%{http_code}\n' 'localhost:8080/portfolio/views/allocation?axis=is_leveraged'  # 400
```

- [ ] **Step 1: 요청 검증 테스트를 먼저 쓴다**

```java
package com.stockproject.portfolio.validation;

import com.stockproject.portfolio.catalog.*;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.assertThatCode;

class RequestValidatorTest {

    private final RequestValidator validator = new RequestValidator();

    /** 스펙 §9.3 — 비활성 축은 요청 시 거부한다. */
    @Test
    void 비활성_축은_거부한다() {
        assertThatThrownBy(() -> validator.validateSnapshotRequest(
                ViewKey.ALLOCATION, AxisKey.IS_LEVERAGED, Lens.DIRECT, Map.of()))
                .isInstanceOf(RequestRejected.class)
                .hasFieldOrPropertyWithValue("code", "AXIS_DISABLED");
    }

    @Test
    void 그_뷰에_쓸_수_없는_축은_거부한다() {
        assertThatThrownBy(() -> validator.validateSnapshotRequest(
                ViewKey.POSITIONS, AxisKey.SECTOR, Lens.DIRECT, Map.of()))
                .hasFieldOrPropertyWithValue("code", "AXIS_NOT_APPLICABLE");
    }

    /** 스펙 §9.3 — LOOK_THROUGH이면 lens_sensitive 축의 필터를 거부한다. 계좌 계열만 허용. */
    @Test
    void LOOK_THROUGH에서_시장_필터를_거부한다() {
        assertThatThrownBy(() -> validator.validateSnapshotRequest(
                ViewKey.POSITIONS, null, Lens.LOOK_THROUGH, Map.of("market", List.of("US"))))
                .hasFieldOrPropertyWithValue("code", "LENS_SENSITIVE_FILTER_REJECTED");
    }

    @Test
    void LOOK_THROUGH에서_계좌_필터는_허용한다() {
        assertThatCode(() -> validator.validateSnapshotRequest(
                ViewKey.POSITIONS, null, Lens.LOOK_THROUGH,
                Map.of("account", List.of("20000000-0000-0000-0000-000000000001"))))
                .doesNotThrowAnyException();
    }

    /** 스펙 §6.3 — lens_policy = NONE인 뷰에는 렌즈를 노출하지 않는다. */
    @Test
    void 렌즈를_쓸_수_없는_뷰에서_LOOK_THROUGH를_거부한다() {
        assertThatThrownBy(() -> validator.validateSnapshotRequest(
                ViewKey.ACCOUNTS, null, Lens.LOOK_THROUGH, Map.of()))
                .hasFieldOrPropertyWithValue("code", "LENS_NOT_ALLOWED");
    }

    @Test
    void 뷰가_지원하지_않는_필터_키를_거부한다() {
        assertThatThrownBy(() -> validator.validateSnapshotRequest(
                ViewKey.ALLOCATION, AxisKey.SECTOR, Lens.DIRECT, Map.of("market", List.of("US"))))
                .hasFieldOrPropertyWithValue("code", "FILTER_NOT_ALLOWED");
    }
}
```

`RequestRejected`는 `code`와 한국어 `message`를 갖는 `RuntimeException`이다.

- [ ] **Step 2: 검증기 구현**

`validateSnapshotRequest`의 순서: (1) 뷰 존재 → (2) 렌즈 정책 대조 → (3) 축 존재·활성·적용 가능 → (4) 필터 키를 `Catalog.allowedFilters(view, lens)`와 대조. 필터 키가 뷰의 `DIRECT` 목록에는 있으나 `LOOK_THROUGH` 목록에는 없으면 `LENS_SENSITIVE_FILTER_REJECTED`, 아예 없으면 `FILTER_NOT_ALLOWED` — 두 오류를 갈라야 사용자에게 다른 안내를 줄 수 있다.

**요청 검증이 카탈로그 대조로 끝난다**는 것이 §6.4의 서빙 계약이다. 임의 조합을 받는 범용 쿼리 엔드포인트를 두지 않는다.

- [ ] **Step 3: `SnapshotViewService` — 파이프라인 순서를 코드로 고정한다**

```java
package com.stockproject.portfolio.view;

/**
 * 스펙 §3.6 2~6단계. 순서가 이 클래스의 계약이다.
 *   라인 적재 → 팩트 검증(§9.1) → 렌즈(2) → 총합 보존 검증 → 필터(3.5) → 집계(4)
 *   → 파생(5) → 조립(6)
 * 팩트 검증은 필터 전에 수행한다 — "연동된 모든 계좌에 라인 존재" 규칙이 필터를 걸면 성립하지 않는다.
 */
@Service
public class SnapshotViewService {

    public Envelope<SnapshotViewData> render(ViewKey viewKey, AxisKey rowAxis,
                                             Lens lens, LineFilter filter) {
        List<AccountRow> accounts = accountRepository.findAll();
        Optional<LocalDate> asOf = calendar.latestAsOf();
        if (asOf.isEmpty()) return emptyEnvelope(accounts);

        List<Line> factLines = positionLines.findLines(asOf.get(), LineFilter.NONE);
        positionLineInvariants.validate(asOf.get(), factLines, accounts);       // §9.1

        LensResult lensed = lensOf(lens).apply(factLines);
        lensOutputInvariants.validateTotalPreserved(factLines, lensed.lines()); // §9.1 렌즈

        List<Line> target = filter.isEmpty() ? lensed.lines() : applyFilter(lensed.lines(), filter);
        ViewSpec view = Catalog.view(viewKey);
        Aggregation agg = engine.aggregate(target, groupByOf(view, rowAxis));

        return assembler.assemble(view, lens, rowAxis, agg, contextOf(...));
    }
}
```

**필터를 렌즈 뒤에 두는 이유**: §3.6이 "필터는 마스터 조인 뒤에 적용한다"고 정하고, 계좌 필터만 렌즈 앞으로 밀 수 있다고 명시했다. 이 계획은 최적화를 하지 않고 규칙대로 렌즈 뒤에 둔다. 그래서 `LineFilter`가 SQL과 Java 두 곳에서 쓰인다 — `findLines`는 `LineFilter.NONE`으로만 호출하고, 실제 필터링은 Java `applyFilter`가 한다. **저장소의 필터 지원은 Task 4에서 테스트했고 향후 최적화 여지로 남긴다.**

`summary`는 `render(SUMMARY, null, DIRECT, NONE)` 결과에 미니차트 블록을 더한다. 미니차트는 같은 라인 집합에 `groupBy = [miniChartAxis]`로 한 번 더 집계하고, 렌즈는 미니차트 블록에만 적용한다(§6.3). `daily_change_*`는 `calendar.previousAsOf(asOf)`의 `totalAssetsKrwAt`으로 계산하며, 직전 스냅샷이 없으면 두 값 모두 `null`이다.

`accounts`는 `render(ACCOUNTS, null, DIRECT, NONE)`이고 `groupBy = [ACCOUNT_TYPE, ACCOUNT]`다. 행 필드는 `AccountRow`와 `CollectionStatusPort`에서 채운다.

- [ ] **Step 4: 컨트롤러**

```java
@RestController
@RequestMapping("/portfolio")
public class ViewController {

    @GetMapping("/views/summary")
    public Envelope<SnapshotViewData> summary(
            @RequestParam(defaultValue = "DIRECT") String lens,
            @RequestParam(name = "mini_chart_axis", defaultValue = "market") String miniChartAxis) { }

    @GetMapping("/views/positions")
    public Envelope<SnapshotViewData> positions(
            @RequestParam(defaultValue = "DIRECT") String lens,
            @RequestParam(required = false) List<String> account,
            @RequestParam(required = false) List<String> market,
            @RequestParam(name = "asset_class", required = false) List<String> assetClass) { }

    @GetMapping("/views/allocation")
    public Envelope<SnapshotViewData> allocation(
            @RequestParam String axis,
            @RequestParam(defaultValue = "DIRECT") String lens,
            @RequestParam(required = false) List<String> account,
            @RequestParam(name = "account_type", required = false) List<String> accountType) { }

    @GetMapping("/views/accounts")
    public Envelope<SnapshotViewData> accounts() { }
}
```

각 메서드는 원시 문자열을 모아 `RequestValidator`에 넘긴 뒤 `LineFilter`로 변환한다. 파싱을 검증 앞에 두지 않는다 — 파싱 실패가 `IllegalArgumentException`으로 새면 오류 코드가 뭉개진다.

`ApiExceptionHandler`가 `RequestRejected` → 400·404, `FactInvariantViolation` → 500 `FACT_INVARIANT_VIOLATED`로 매핑한다(§A.6.4 표).

- [ ] **Step 5: API 테스트**

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Testcontainers
class SnapshotViewApiTest {

    @Test
    void 요약_응답이_스펙_값을_낸다() throws Exception {
        mockMvc.perform(get("/portfolio/views/summary"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.as_of").value("2026-07-27T15:30:00+09:00"))
            .andExpect(jsonPath("$.data.total.total_assets_krw").value(58000000))
            .andExpect(jsonPath("$.data.total.securities_value_krw").value(53300000))
            .andExpect(jsonPath("$.data.total.deposit_krw").value(4700000))
            .andExpect(jsonPath("$.data.total.cost_amount_krw").value(48800000))
            .andExpect(jsonPath("$.data.total.unrealized_pnl_krw").value(4500000))
            .andExpect(jsonPath("$.data.total.unrealized_pnl_pct").value(9.2))
            .andExpect(jsonPath("$.data.total.cash_ratio_pct").value(8.1))
            .andExpect(jsonPath("$.data.total.daily_change_krw").value(1200000))
            .andExpect(jsonPath("$.data.total.daily_change_pct").value(2.1))
            .andExpect(jsonPath("$.data.total.account_count").value(4))
            .andExpect(jsonPath("$.data.total.instrument_count").value(5))
            .andExpect(jsonPath("$.data.total.market_value_krw").doesNotExist())   // 불변식 4
            .andExpect(jsonPath("$.data.mini_chart.rows[0].key").value("KR"))
            .andExpect(jsonPath("$.data.mini_chart.rows[0].market_value_krw").value(46800000))
            .andExpect(jsonPath("$.data.mini_chart.rows[0].weight_pct").value(80.7))
            .andExpect(jsonPath("$.notices[?(@.code=='STALE_ACCOUNTS')].params.count").value(1));
    }

    @Test
    void 비중_분석_섹터_응답이_스펙_값을_낸다() throws Exception {
        mockMvc.perform(get("/portfolio/views/allocation?axis=sector&lens=DIRECT"))
            .andExpect(jsonPath("$.data.rows.length()").value(5))
            .andExpect(jsonPath("$.data.rows[0].label").value("반도체"))
            .andExpect(jsonPath("$.data.rows[0].market_value_krw").value(23240000))
            .andExpect(jsonPath("$.data.rows[0].unrealized_pnl_pct").value(16.2))
            .andExpect(jsonPath("$.data.rows[0].weight_pct").value(40.1))
            .andExpect(jsonPath("$.data.rows[4].label").value("현금"))
            .andExpect(jsonPath("$.data.rows[4].cost_amount_krw").value(nullValue()))
            .andExpect(jsonPath("$.data.rows[4].weight_pct").value(8.1))
            .andExpect(jsonPath("$.data.rows[0].total_assets_krw").doesNotExist());  // 불변식 4
    }

    @Test
    void 렌즈를_켜면_행에서_원가_계열이_사라지고_합계는_그대로다() throws Exception {
        mockMvc.perform(get("/portfolio/views/allocation?axis=sector&lens=LOOK_THROUGH"))
            .andExpect(jsonPath("$.data.total.cost_amount_krw").value(48800000))     // 총합 보존
            .andExpect(jsonPath("$.data.rows[0].cost_amount_krw").doesNotExist())
            .andExpect(jsonPath("$.data.rows[0].unrealized_pnl_krw").doesNotExist())
            .andExpect(jsonPath("$.data.rows[0].unrealized_pnl_pct").doesNotExist())
            .andExpect(jsonPath("$.notices[?(@.code=='CONSTITUENT_UNAVAILABLE')].params.undecomposed_krw")
                    .value(11000000))
            .andExpect(jsonPath("$.notices[?(@.code=='CONSTITUENT_AS_OF')]").isEmpty());
    }

    @Test
    void 종목별_외화_행에_현지_통화가_병기된다() throws Exception {
        mockMvc.perform(get("/portfolio/views/positions"))
            .andExpect(jsonPath("$.data.rows[?(@.key=='AAPL')].currency").value("USD"))
            .andExpect(jsonPath("$.data.rows[?(@.key=='AAPL')].market_value_local").value(4400.00))
            .andExpect(jsonPath("$.data.rows[?(@.key=='AAPL')].avg_cost").value(200.00))
            .andExpect(jsonPath("$.data.rows[?(@.key=='005930')].currency").doesNotExist());
    }

    @Test
    void 계좌별_2단계_중첩과_소계() throws Exception {
        mockMvc.perform(get("/portfolio/views/accounts"))
            .andExpect(jsonPath("$.data.group_by[0]").value("account_type"))
            .andExpect(jsonPath("$.data.rows[0].label").value("일반"))
            .andExpect(jsonPath("$.data.rows[0].market_value_krw").value(40960000))
            .andExpect(jsonPath("$.data.rows[0].deposit_krw").value(3560000))
            .andExpect(jsonPath("$.data.rows[0].rows.length()").value(2))
            .andExpect(jsonPath("$.data.rows[0].rows[0].label").value("한국투자 위탁"))
            .andExpect(jsonPath("$.data.rows[0].rows[0].link_state").value("CONNECTED"))
            .andExpect(jsonPath("$.data.rows[0].rows[0].last_collection").value(nullValue()));
    }

    @Test
    void 잘못된_요청은_카탈로그_대조로_거부된다() throws Exception {
        mockMvc.perform(get("/portfolio/views/allocation?axis=is_leveraged"))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("AXIS_DISABLED"));

        mockMvc.perform(get("/portfolio/views/positions?lens=LOOK_THROUGH&market=US"))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("LENS_SENSITIVE_FILTER_REJECTED"));

        mockMvc.perform(get("/portfolio/views/accounts?lens=LOOK_THROUGH"))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error.code").value("LENS_NOT_ALLOWED"));
    }

    @Test
    void 계좌가_없으면_200과_NO_ACCOUNTS를_낸다() throws Exception {
        truncateAll();
        mockMvc.perform(get("/portfolio/views/summary"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.empty_reason").value("NO_ACCOUNTS"));
    }

    @Test
    void 필터_결과가_없으면_NO_MATCH_FILTER다() throws Exception {
        mockMvc.perform(get("/portfolio/views/positions?asset_class=ETF&market=US"))
            .andExpect(jsonPath("$.empty_reason").value("NO_MATCH_FILTER"));
    }
}
```

- [ ] **Step 6: 카탈로그 엔드포인트**

`GET /portfolio/catalog`은 봉투 없이 `CatalogDto`를 낸다:
```json
{ "views": [ { "view_key": "allocation", "grain": "축 값", "lens_policy": "OPTIONAL",
               "axis_options": ["instrument","sector","market","currency","asset_class"],
               "metrics": ["market_value_krw","weight_pct","instrument_count"],
               "filters": { "DIRECT": ["account","account_type"],
                            "LOOK_THROUGH": ["account","account_type"] } } ],
  "axes":    [ { "key": "sector", "label": "섹터", "lens_sensitive": true, "enabled": true } ],
  "metrics": [ { "key": "unrealized_pnl_pct", "label": "평가손익률", "additive": false,
                 "cash_included": false, "lens_safe": "TOTAL_ONLY" } ],
  "accounts": [ { "account_id": "…", "label": "한국투자 위탁",
                  "account_type": "GENERAL", "link_state": "CONNECTED" } ],
  "empty_reasons": ["NO_ACCOUNTS", "…"],
  "notice_codes":  ["FX_APPLIED", "…"] }
```

`axis_options`에서 `enabled = false`인 `is_leveraged`는 **제외한다** — 클라이언트가 고를 수 없게 하는 것이 §6.4의 목적이다.

- [ ] **Step 7: 테스트 통과 → 커밋**

```bash
./gradlew test --tests '*SnapshotViewApiTest' --tests '*RequestValidatorTest'
git add -A && git commit -m "feat: 스냅샷 4개 뷰 엔드포인트와 카탈로그 대조 요청 검증"
```

---

### Task 9: 실현손익 엔드포인트 (§8.4)

**Files:**
- Create: `query/RealizedPnlRepository.java` · `view/RealizedPnlViewService.java` · `view/PeriodResolver.java` · `api/dto/RealizedPnlData.java`
- Modify: `api/ViewController.java` (엔드포인트 추가)
- Test: `test/.../view/RealizedPnlViewServiceTest.java` · `test/.../api/RealizedPnlApiTest.java`

**Interfaces:**
- Produces:
  - `record RealizedPnlRow(String tradeId, UUID accountId, UUID instrumentId, String instrumentKey, String instrumentLabel, CurrencyCode currency, OffsetDateTime soldAt, BigDecimal quantity, BigDecimal sellAmountLocal, BigDecimal costBasisLocal, BigDecimal sellAmountKrw, BigDecimal costBasisKrw, BigDecimal realizedPnlKrw, Grade grade)`
  - `List<RealizedPnlRow> RealizedPnlRepository.findByPeriod(LocalDate from, LocalDate to, Set<UUID> accountIds, Set<AccountType> accountTypes)`
  - `record Period(LocalDate from, LocalDate to)` · `Period PeriodResolver.resolve(String period, LocalDate from, LocalDate to, LocalDate referenceAsOf)`
  - `Envelope<RealizedPnlData> RealizedPnlViewService.render(String period, LocalDate from, LocalDate to, LineFilter)`

**완료 조건**
1. `?period=THIS_YEAR`가 §C.10의 값을 낸다 — 2행, `MIXED`, `SEEDED_ROWS`.
2. 체결 노드가 `rows[].rows`로 중첩되고 접히지 않는다.
3. `UNAVAILABLE`·`CONFLICT` 체결이 합계에서 빠지고 `EXCLUDED_ACCOUNTS`가 뜬다(단위 테스트로 검증. 샘플에는 그런 행이 없다).
4. 기간에 매도가 없으면 `200` + `NO_TRADES_IN_PERIOD`.
5. `?period=CUSTOM` + `from`/`to` 누락 → `400 INVALID_PERIOD`.
6. 기간 기준일이 **최신 `as_of`**다 — 벽시계에 의존하지 않는다.

**검증 방법**
```bash
./gradlew test --tests '*RealizedPnl*'
curl -s 'localhost:8080/portfolio/views/realized-pnl?period=THIS_YEAR' | jq '.data.total'
```

- [ ] **Step 1: 기간 해석기 테스트를 먼저 쓴다**

```java
class PeriodResolverTest {

    private static final LocalDate REF = LocalDate.of(2026, 7, 27);   // 최신 as_of

    @Test
    void 기간_프리셋을_최신_as_of_기준으로_해석한다() {
        assertThat(resolver.resolve("THIS_MONTH", null, null, REF))
                .isEqualTo(new Period(LocalDate.of(2026, 7, 1), LocalDate.of(2026, 7, 31)));
        assertThat(resolver.resolve("LAST_MONTH", null, null, REF))
                .isEqualTo(new Period(LocalDate.of(2026, 6, 1), LocalDate.of(2026, 6, 30)));
        assertThat(resolver.resolve("THIS_YEAR", null, null, REF))
                .isEqualTo(new Period(LocalDate.of(2026, 1, 1), LocalDate.of(2026, 12, 31)));
        assertThat(resolver.resolve("LAST_YEAR", null, null, REF))
                .isEqualTo(new Period(LocalDate.of(2025, 1, 1), LocalDate.of(2025, 12, 31)));
    }

    @Test
    void CUSTOM은_from_to가_필수다() {
        assertThatThrownBy(() -> resolver.resolve("CUSTOM", null, null, REF))
                .hasFieldOrPropertyWithValue("code", "INVALID_PERIOD");
        assertThatThrownBy(() -> resolver.resolve("CUSTOM",
                LocalDate.of(2026, 8, 1), LocalDate.of(2026, 7, 1), REF))
                .hasFieldOrPropertyWithValue("code", "INVALID_PERIOD");
    }
}
```

- [ ] **Step 2: 등급 롤업과 제외 규칙 테스트**

```java
class RealizedPnlViewServiceTest {

    /** 스펙 §8.4 — 체결 등급이 하나면 그 값, 섞이면 MIXED. 저장되지 않고 조립 시에만 생긴다. */
    @Test
    void 등급이_섞이면_종목_노드는_MIXED다() {
        RealizedPnlData data = assemble(List.of(
                row("T-0001", "005930", Grade.SEEDED,   "79000",  "320000"),
                row("T-0002", "005930", Grade.VERIFIED, "198000", "500000")));

        assertThat(data.rows()).hasSize(1);
        assertThat(data.rows().get(0).grade()).isEqualTo("MIXED");
        assertThat(data.rows().get(0).tradeCount()).isEqualTo(2);
        assertThat(data.rows().get(0).realizedPnlKrw()).isEqualByComparingTo("277000");
        assertThat(data.rows().get(0).realizedPnlPct()).isEqualByComparingTo("33.8");
        assertThat(data.rows().get(0).firstSoldAt()).isEqualTo(LocalDate.of(2026, 3, 2));
        assertThat(data.rows().get(0).lastSoldAt()).isEqualTo(LocalDate.of(2026, 5, 12));
    }

    @Test
    void 등급이_하나면_그_값이다() {
        RealizedPnlData data = assemble(List.of(row("T-0003", "035420", Grade.VERIFIED, "-305000", "2300000")));
        assertThat(data.rows().get(0).grade()).isEqualTo("VERIFIED");
    }

    /** 스펙 §9.3 — UNAVAILABLE·CONFLICT는 합계에서 제외하되 제외 건수를 노출한다. 조용히 빼지 않는다. */
    @Test
    void 미제공_등급은_합계에서_빠지고_제외_계좌_수가_노출된다() {
        Envelope<RealizedPnlData> env = render(List.of(
                row("T-0002", "005930", Grade.VERIFIED,    "198000", "500000"),
                rowInAccount("T-0009", ACC_2, "000660", Grade.UNAVAILABLE, "999999", "1000000")));

        assertThat(env.data().total().get("realized_pnl_krw")).isEqualTo(new BigDecimal("198000"));
        assertThat(env.notices()).extracting(NoticeDto::code).contains("EXCLUDED_ACCOUNTS");
        assertThat(noticeParams(env, "EXCLUDED_ACCOUNTS")).containsEntry("count", 1);
    }

    @Test
    void 전부_미제공이면_ALL_UNAVAILABLE이다() {
        Envelope<RealizedPnlData> env = render(List.of(
                row("T-0009", "000660", Grade.CONFLICT, "1", "1")));
        assertThat(env.emptyReason()).isEqualTo("ALL_UNAVAILABLE");
    }

    /** 스펙 §4.5 — SEEDED는 숨기지 않고 표시하되 배지로 구분한다. */
    @Test
    void SEEDED_행이_있으면_SEEDED_ROWS가_뜬다() {
        Envelope<RealizedPnlData> env = render(List.of(
                row("T-0001", "005930", Grade.SEEDED, "79000", "320000")));
        assertThat(noticeParams(env, "SEEDED_ROWS")).containsEntry("count", 1);
    }
}
```

`SEEDED_ROWS`의 `count`는 **종목 노드 수**가 아니라 §4.5의 "N개 종목은 추정치입니다"에 맞춰 **SEEDED 체결을 가진 종목 노드 수**로 센다.

- [ ] **Step 3: 응답 DTO**

```java
package com.stockproject.portfolio.api.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

/** 스펙 §8.4 실현손익. 공통 행 스키마를 쓰지 않는다(§6.3). */
public record RealizedPnlData(PeriodDto period, Map<String, Object> total, List<InstrumentNode> rows) {

    public record PeriodDto(LocalDate from, LocalDate to) { }

    /** 종목 노드 — grade는 4값 + MIXED의 5값이다. */
    public record InstrumentNode(String key, String label,
                                 @JsonInclude(JsonInclude.Include.NON_NULL) String currency,
                                 BigDecimal sellAmountKrw, BigDecimal costBasisKrw,
                                 BigDecimal realizedPnlKrw, BigDecimal realizedPnlPct,
                                 LocalDate firstSoldAt, LocalDate lastSoldAt,
                                 int tradeCount, String grade, List<TradeNode> rows) { }

    /** 체결 노드 — grade는 4값이다. 종목으로 접지 않는다(§2.8). */
    public record TradeNode(String tradeId, LocalDate soldAt, BigDecimal quantity,
                            BigDecimal sellAmountKrw, BigDecimal costBasisKrw,
                            BigDecimal realizedPnlKrw, String grade) { }
}
```

- [ ] **Step 4: 저장소와 서비스 구현**

`RealizedPnlRepository.findByPeriod`의 SQL — 기간 귀속은 **체결일**(§4.3)이고 타임존은 `Asia/Seoul`이다:
```sql
SELECT r.trade_id, r.account_id, r.instrument_id, i.symbol, i.name, i.currency,
       r.sold_at, r.quantity, r.sell_amount_local, r.cost_basis_local,
       r.sell_amount_krw, r.cost_basis_krw, r.realized_pnl_krw, r.grade
  FROM realized_pnl_line r
  JOIN account    a ON a.account_id    = r.account_id
  JOIN instrument i ON i.instrument_id = r.instrument_id
 WHERE (r.sold_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN :from AND :to
```
계좌 필터는 `findLines`와 같은 `= ANY (:param)` 방식으로 append한다.

서비스가 하는 일:
1. 기준일 = `calendar.latestAsOf()` → `PeriodResolver.resolve(...)`
2. 행을 종목으로 묶는다(`instrumentId` 기준). **접는 것이 아니라 중첩이다** — 체결 노드를 모두 남긴다.
3. 종목 노드 합계는 **포함 대상 체결만**(`grade ∈ {VERIFIED, SEEDED}`) 더한다. `realized_pnl_pct = Σ실현손익 ÷ Σ취득원가`, 소수 1자리 HALF_UP.
4. 종목 노드 `grade` = 포함 대상 체결 등급의 distinct가 1이면 그 값, 2 이상이면 `MIXED`.
5. `total.realized_pnl_krw`·`cost_basis_krw`·`realized_pnl_pct`도 포함 대상만 더한다.
6. 제외된 체결의 distinct 계좌 수 → `EXCLUDED_ACCOUNTS`.
7. 정렬: 종목 노드는 `lastSoldAt` desc → `key` asc, 체결 노드는 `soldAt` desc → `tradeId` asc.
8. 현지 통화는 종목 노드에만, 통화가 `KRW`가 아닐 때만 병기한다.

- [ ] **Step 5: 엔드포인트 추가와 API 테스트**

```java
    @GetMapping("/views/realized-pnl")
    public Envelope<RealizedPnlData> realizedPnl(
            @RequestParam(defaultValue = "THIS_MONTH") String period,
            @RequestParam(required = false) LocalDate from,
            @RequestParam(required = false) LocalDate to,
            @RequestParam(required = false) List<String> account,
            @RequestParam(name = "account_type", required = false) List<String> accountType) { }
```

```java
    @Test
    void 올해_실현손익이_스펙_값을_낸다() throws Exception {
        mockMvc.perform(get("/portfolio/views/realized-pnl?period=THIS_YEAR"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data.period.from").value("2026-01-01"))
            .andExpect(jsonPath("$.data.total.realized_pnl_krw").value(-28000))
            .andExpect(jsonPath("$.data.total.realized_pnl_pct").value(-0.9))
            .andExpect(jsonPath("$.data.rows.length()").value(2))
            .andExpect(jsonPath("$.data.rows[0].key").value("005930"))
            .andExpect(jsonPath("$.data.rows[0].grade").value("MIXED"))
            .andExpect(jsonPath("$.data.rows[0].realized_pnl_krw").value(277000))
            .andExpect(jsonPath("$.data.rows[0].realized_pnl_pct").value(33.8))
            .andExpect(jsonPath("$.data.rows[0].trade_count").value(2))
            .andExpect(jsonPath("$.data.rows[0].rows[0].trade_id").value("T-0002"))
            .andExpect(jsonPath("$.data.rows[0].rows[0].grade").value("VERIFIED"))
            .andExpect(jsonPath("$.data.rows[1].key").value("035420"))
            .andExpect(jsonPath("$.notices[?(@.code=='SEEDED_ROWS')].params.count").value(1));
    }

    @Test
    void 매도가_없는_기간은_NO_TRADES_IN_PERIOD다() throws Exception {
        mockMvc.perform(get("/portfolio/views/realized-pnl?period=LAST_YEAR"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data.rows.length()").value(0))
            .andExpect(jsonPath("$.empty_reason").value("NO_TRADES_IN_PERIOD"));
    }
```

- [ ] **Step 6: 커밋**

```bash
./gradlew test --tests '*RealizedPnl*' --tests '*PeriodResolverTest'
git add -A && git commit -m "feat: 실현손익 뷰 — 2단계 중첩 · MIXED 롤업 · 미제공 등급 제외"
```

---

### Task 10: 자산 변화 엔드포인트 (§2.9 · §8.4)

**Files:**
- Create: `view/AssetChangeViewService.java` · `query/CashflowPort.java` · `query/EmptyCashflowPort.java` · `api/dto/AssetChangeData.java`
- Modify: `api/ViewController.java`
- Test: `test/.../view/AssetChangeViewServiceTest.java` · `test/.../api/AssetChangeApiTest.java`

**Interfaces:**
- Produces:
  - `record CashflowTotals(BigDecimal deposit, BigDecimal withdraw, BigDecimal dividend, BigDecimal feeTax, Set<UUID> coveredAccountIds)`
  - `CashflowTotals CashflowPort.totalsFor(Period, Set<UUID> accountIds)`
  - `Envelope<AssetChangeData> AssetChangeViewService.render(String period, LocalDate from, LocalDate to, LineFilter)`

**완료 조건**
1. §C.11의 값을 낸다 — `opening 56,800,000` · `closing 58,000,000` · `investment_pnl 1,200,000` · `split_available false`.
2. 항등식이 성립한다: `closing = opening + deposited + earned + included − excluded`.
3. 값이 0인 `breakdown` 항목이 숨겨진다.
4. `PERIOD_TRUNCATED` · `BOUNDARY_CARRIED_FORWARD` · `CASHFLOW_UNCOVERED`가 뜬다.
5. 기초·기말 스냅샷이 없으면 `200` + `NO_HOLDINGS`.

**검증 방법**
```bash
./gradlew test --tests '*AssetChange*'
curl -s 'localhost:8080/portfolio/views/asset-change?period=CUSTOM&from=2026-07-01&to=2026-07-31' | jq .
```

- [ ] **Step 1: 항등식 테스트를 먼저 쓴다**

```java
class AssetChangeViewServiceTest {

    /** 스펙 §2.9 항등식 — 투자손익은 나머지 전부. 잔차 항목을 두지 않는다. */
    @Test
    void 항등식이_성립한다() {
        AssetChangeData d = render("2026-07-01", "2026-07-31").data();

        BigDecimal lhs = d.closing();
        BigDecimal rhs = d.opening().add(d.deposited()).add(d.earned())
                .add(d.accountIncluded()).subtract(d.accountExcluded());
        assertThat(lhs).isEqualByComparingTo(rhs);
    }

    /** 현금흐름이 미확보면 투자손익 = Δ총자산이다. total은 항상 정확하다(스펙 §2.9). */
    @Test
    void 현금흐름_미확보시_투자손익은_자산_증감_전부다() {
        AssetChangeData d = render("2026-07-01", "2026-07-31").data();

        assertThat(d.opening()).isEqualByComparingTo("56800000");
        assertThat(d.closing()).isEqualByComparingTo("58000000");
        assertThat(d.deposited()).isEqualByComparingTo("0");
        assertThat(d.investmentPnl().total()).isEqualByComparingTo("1200000");
        assertThat(d.investmentPnl().splitAvailable()).isFalse();
        assertThat(d.investmentPnl().realized()).isNull();
    }

    /** 스펙 §2.9 — 값이 0인 항목은 행을 숨긴다. */
    @Test
    void 값이_0인_항목은_breakdown에서_숨는다() {
        AssetChangeData d = render("2026-07-01", "2026-07-31").data();
        assertThat(d.breakdown()).extracting(b -> b.type()).containsExactly("INVESTMENT_PNL");
    }

    /** 스펙 §2.9 경계 처리 — 기초 스냅샷이 없으면 가장 이른 스냅샷을 쓰고 실제 시작일을 표시한다. */
    @Test
    void 기초_스냅샷이_없으면_실제_시작일을_알린다() {
        Envelope<AssetChangeData> env = render("2026-07-01", "2026-07-31");
        assertThat(noticeParams(env, "PERIOD_TRUNCATED"))
                .containsEntry("actual_from", LocalDate.of(2026, 7, 24));
    }

    @Test
    void 기간_경계에_이월_계좌가_있으면_경고한다() {
        Envelope<AssetChangeData> env = render("2026-07-01", "2026-07-31");
        assertThat(noticeParams(env, "BOUNDARY_CARRIED_FORWARD"))
                .containsEntry("count", 1)
                .containsEntry("boundary", LocalDate.of(2026, 7, 27));
    }

    /** 스펙 §4.6 — 미확보 계좌의 입출금은 투자손익에 섞이므로 경고한다. 잔차 항목은 두지 않는다. */
    @Test
    void 현금흐름_미확보_계좌를_경고한다() {
        Envelope<AssetChangeData> env = render("2026-07-01", "2026-07-31");
        assertThat(noticeParams(env, "CASHFLOW_UNCOVERED")).containsEntry("count", 4);
    }
}
```

- [ ] **Step 2: 현금흐름 포트와 빈 구현**

```java
package com.stockproject.portfolio.query;

/**
 * cln_cashflow 조회 — 데이터팀 소유(스펙 §5.1 · §11.2).
 * 매매대금·예수금 내부 이동·환전·매매 수수료를 제외한 결과만 제공받는 계약이며(§5.1),
 * 그 배제 규칙이 팀 미합의라(설계 공유 문서 안건 1) 이번 범위에서는 EmptyCashflowPort가 빈 값을 낸다.
 * 빈 값은 곧 "전 계좌 미확보"이므로 CASHFLOW_UNCOVERED가 정직하게 뜨고 항등식은 그대로 성립한다.
 */
public interface CashflowPort {
    CashflowTotals totalsFor(Period period, Set<UUID> accountIds);
}
```

```java
@Component
public class EmptyCashflowPort implements CashflowPort {
    @Override public CashflowTotals totalsFor(Period period, Set<UUID> accountIds) {
        return new CashflowTotals(BigDecimal.ZERO, BigDecimal.ZERO,
                BigDecimal.ZERO, BigDecimal.ZERO, Set.of());
    }
}
```

- [ ] **Step 3: 응답 DTO**

```java
package com.stockproject.portfolio.api.dto;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;

/** 스펙 §8.4 자산 변화. 계좌 편입·제외는 breakdown에 넣지 않고 최상위 필드로 둔다. */
public record AssetChangeData(PeriodDto period,
                              BigDecimal opening, BigDecimal closing,
                              BigDecimal deposited, BigDecimal earned,
                              BigDecimal accountIncluded, BigDecimal accountExcluded,
                              List<BreakdownItem> breakdown, InvestmentPnl investmentPnl) {

    public record PeriodDto(LocalDate from, LocalDate to) { }

    /** type = DEPOSIT · WITHDRAW · DIVIDEND · FEE_TAX · INVESTMENT_PNL (표시 유형이며 cln_cashflow.type과 별개). */
    public record BreakdownItem(String type, BigDecimal amount) { }

    /** split_available = false이면 거래 원장이 없어 분해를 생략한 것이고 total은 항상 정확하다(§2.9). */
    public record InvestmentPnl(BigDecimal total, BigDecimal realized,
                                BigDecimal unrealizedChange, boolean splitAvailable) { }
}
```

- [ ] **Step 4: 서비스 구현**

순서:
1. 기준일 = `calendar.latestAsOf()`. `PeriodResolver.resolve(...)`로 `Period`를 얻는다.
2. **기초 스냅샷**: `calendar.latestBefore(period.from())`. 없으면 `calendar.earliestOnOrAfter(period.from())`을 쓰고 그 날짜를 `PERIOD_TRUNCATED.actual_from`으로 남긴다. 둘 다 없으면 `NO_HOLDINGS`.
3. **기말 스냅샷**: `calendar.latestOnOrBefore(period.to())`. 없으면 `NO_HOLDINGS`.
4. `opening` · `closing` = 각 시점의 `totalAssetsKrwAt(asOf, filter)`.
5. **계좌 편입·제외**: 기초·기말 스냅샷의 계좌 집합을 비교한다. 편입 = 기말에만 있는 계좌의 기말 총자산, 제외 = 기초에만 있는 계좌의 기초 총자산. (§2.9 경계 처리의 "첫/마지막 스냅샷 총자산"을 기간 양 끝 스냅샷으로 근사한다 — 기간 내 중간 스냅샷을 훑지 않는 단순화이며, 계좌 편입·제외가 기간 경계 밖에서 일어난 경우를 다루지 않는다. 이 근사를 코드 주석에 남긴다.)
6. `CashflowTotals`를 읽는다. `deposited = deposit − withdraw`.
7. `investmentPnl = (closing − opening) − deposited − dividend + feeTax − included + excluded`.
8. `earned = investmentPnl + dividend − feeTax`.
9. `breakdown` = `DEPOSIT`(deposit) · `WITHDRAW`(−withdraw) · `DIVIDEND` · `FEE_TAX`(−feeTax) · `INVESTMENT_PNL` 중 **0이 아닌 것만**.
10. `investment_pnl.split_available = false`, `realized`·`unrealized_change` = `null` — 거래 원장 산출이 범위 밖이다.
11. notice: 미확보 계좌 수 = `연동 유효 계좌 − coveredAccountIds`, 경계 이월 계좌 수 = 두 경계 스냅샷의 `is_carried_forward` distinct 계좌 수(있으면 기말 날짜를 `boundary`로).

- [ ] **Step 5: 엔드포인트와 API 테스트**

```java
    @GetMapping("/views/asset-change")
    public Envelope<AssetChangeData> assetChange(
            @RequestParam(defaultValue = "THIS_MONTH") String period,
            @RequestParam(required = false) LocalDate from,
            @RequestParam(required = false) LocalDate to,
            @RequestParam(required = false) List<String> account,
            @RequestParam(name = "account_type", required = false) List<String> accountType) { }
```

```java
    @Test
    void 자산_변화_응답이_스펙_값을_낸다() throws Exception {
        mockMvc.perform(get("/portfolio/views/asset-change?period=CUSTOM&from=2026-07-01&to=2026-07-31"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data.opening").value(56800000))
            .andExpect(jsonPath("$.data.closing").value(58000000))
            .andExpect(jsonPath("$.data.deposited").value(0))
            .andExpect(jsonPath("$.data.earned").value(1200000))
            .andExpect(jsonPath("$.data.account_included").value(0))
            .andExpect(jsonPath("$.data.account_excluded").value(0))
            .andExpect(jsonPath("$.data.breakdown.length()").value(1))
            .andExpect(jsonPath("$.data.breakdown[0].type").value("INVESTMENT_PNL"))
            .andExpect(jsonPath("$.data.investment_pnl.total").value(1200000))
            .andExpect(jsonPath("$.data.investment_pnl.split_available").value(false))
            .andExpect(jsonPath("$.notices[?(@.code=='CASHFLOW_UNCOVERED')].params.count").value(4))
            .andExpect(jsonPath("$.notices[?(@.code=='PERIOD_TRUNCATED')].params.actual_from")
                    .value("2026-07-24"));
    }
```

- [ ] **Step 6: 커밋**

```bash
./gradlew test --tests '*AssetChange*'
git add -A && git commit -m "feat: 자산 변화 뷰 — 항등식 · 현금흐름 포트 스텁 · 경계 경고"
```

---

### Task 11: 도달점 검증 — 6개 응답 골든 테스트와 문서

**Files:**
- Create: `test/.../api/SixViewGoldenTest.java`
- Create: `test/resources/golden/summary.json` · `positions.json` · `allocation-sector.json` · `allocation-sector-lookthrough.json` · `accounts.json` · `realized-pnl.json` · `asset-change.json`
- Create: `back-end/docs/decisions.md`
- Modify: `back-end/README.md`

**Interfaces:**
- Consumes: Task 8·9·10의 엔드포인트 전부

**완료 조건**
1. 샘플 SQL만 적재된 상태에서 6개 엔드포인트 응답이 골든 JSON과 **완전히 일치**한다(필드 순서 무시, 값·키 존재 모두 비교).
2. 골든 JSON이 §C.5~C.11의 표와 일치한다.
3. 불변식 4개를 응답 수준에서 다시 확인하는 교차 검증 테스트가 통과한다.
4. `README.md`가 실행 절차·범위 경계·인증 없음을 적는다.
5. `docs/decisions.md`가 §A.2의 네 결정(빌드·마이그레이션·데이터 접근·집계 위치)과 되돌리는 조건을 적는다.

**검증 방법**
```bash
./gradlew clean test        # 전체 통과
docker compose up -d --build
docker compose exec -T db psql -U portfolio -d portfolio -f /sample/sample_portfolio.sql
for p in \
  'views/summary' \
  'views/positions?lens=DIRECT' \
  'views/allocation?axis=sector&lens=DIRECT' \
  'views/allocation?axis=sector&lens=LOOK_THROUGH' \
  'views/accounts' \
  'views/realized-pnl?period=THIS_YEAR' \
  'views/asset-change?period=CUSTOM&from=2026-07-01&to=2026-07-31' \
  'catalog' ; do
  printf '%s -> %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' "localhost:8080/portfolio/$p")"
done
# 기대: 전부 200
```

- [ ] **Step 1: 골든 테스트를 쓴다 (실패 확인)**

```java
package com.stockproject.portfolio.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.skyscreamer.jsonassert.JSONAssert;
import org.skyscreamer.jsonassert.JSONCompareMode;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

/** 도달점 검증 — 샘플 행만으로 6개 뷰 응답이 전부 나온다. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Testcontainers
class SixViewGoldenTest {

    @ParameterizedTest(name = "{1}")
    @CsvSource(delimiter = '|', value = {
        "/portfolio/views/summary                                              | summary.json",
        "/portfolio/views/positions?lens=DIRECT                                | positions.json",
        "/portfolio/views/allocation?axis=sector&lens=DIRECT                   | allocation-sector.json",
        "/portfolio/views/allocation?axis=sector&lens=LOOK_THROUGH             | allocation-sector-lookthrough.json",
        "/portfolio/views/accounts                                             | accounts.json",
        "/portfolio/views/realized-pnl?period=THIS_YEAR                        | realized-pnl.json",
        "/portfolio/views/asset-change?period=CUSTOM&from=2026-07-01&to=2026-07-31 | asset-change.json"
    })
    void 여섯_뷰_응답이_골든과_일치한다(String path, String goldenFile) throws Exception {
        String actual = mockMvc.perform(get(path.trim()))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(java.nio.charset.StandardCharsets.UTF_8);
        String expected = new ClassPathResource("golden/" + goldenFile.trim())
                .getContentAsString(java.nio.charset.StandardCharsets.UTF_8);

        JSONAssert.assertEquals(expected, actual, JSONCompareMode.NON_EXTENSIBLE);
    }
}
```

`JSONCompareMode.NON_EXTENSIBLE`이 **응답에 골든에 없는 키가 있으면 실패**시킨다. `LOOK_THROUGH`에서 키가 사라지는 규칙을 검증하려면 이 모드가 필요하다. `org.skyscreamer:jsonassert`는 `spring-boot-starter-test`에 포함돼 있다.

- [ ] **Step 2: 골든 JSON을 §C.5~C.11에서 만든다**

Run: `./gradlew test --tests '*SixViewGoldenTest'` → FAIL. 실패 메시지의 실제 응답을 §C의 표와 **한 줄씩 대조**한 뒤 골든 파일에 옮긴다.

**실제 응답을 그대로 복사해 골든으로 삼지 않는다.** §C의 표가 기준이고, 어긋나면 구현을 고친다. 표가 틀렸다고 판단되면 계획을 고치고 그 사실을 커밋 메시지에 남긴다.

- [ ] **Step 3: 불변식 교차 검증 테스트를 추가한다**

```java
    /** 불변식 1·4 — Σ rows = total, 그리고 행/합계 키가 서로의 자리에 없다. */
    @ParameterizedTest
    @ValueSource(strings = {
        "/portfolio/views/positions?lens=DIRECT",
        "/portfolio/views/allocation?axis=sector&lens=DIRECT",
        "/portfolio/views/allocation?axis=market&lens=DIRECT",
        "/portfolio/views/allocation?axis=currency&lens=DIRECT",
        "/portfolio/views/allocation?axis=asset_class&lens=DIRECT",
        "/portfolio/views/allocation?axis=instrument&lens=DIRECT",
        "/portfolio/views/accounts"
    })
    void 모든_스냅샷_뷰에서_행_합이_총자산과_같다(String path) throws Exception {
        JsonNode data = json(path).get("data");

        BigDecimal rowSum = BigDecimal.ZERO;
        for (JsonNode row : data.get("rows")) {
            rowSum = rowSum.add(row.get("market_value_krw").decimalValue());
            assertThat(row.has("total_assets_krw")).isFalse();
            assertThat(row.has("securities_value_krw")).isFalse();
        }
        assertThat(rowSum).isEqualByComparingTo(data.get("total").get("total_assets_krw").decimalValue());
        assertThat(data.get("total").has("market_value_krw")).isFalse();
    }

    /** 불변식 2 — securities_value_krw − cost_amount_krw = unrealized_pnl_krw (스펙 §8.3). */
    @Test
    void 손익_계열은_유가증권_평가금액을_기준으로_한다() throws Exception {
        JsonNode total = json("/portfolio/views/allocation?axis=sector&lens=DIRECT").get("data").get("total");

        assertThat(total.get("securities_value_krw").decimalValue()
                        .subtract(total.get("cost_amount_krw").decimalValue()))
                .isEqualByComparingTo(total.get("unrealized_pnl_krw").decimalValue());
    }

    /** 불변식 3 — 여러 통화가 섞일 수 있는 묶음에는 현지 통화가 없다. */
    @Test
    void 섹터_시장_계좌_행에는_현지_통화가_없다() throws Exception {
        for (String path : List.of("allocation?axis=sector", "allocation?axis=market", "accounts")) {
            for (JsonNode row : json("/portfolio/views/" + path).get("data").get("rows")) {
                assertThat(row.has("market_value_local")).as(path).isFalse();
            }
        }
    }

    /** 불변식 3 — 비중 합이 100.0이다(반올림 허용 오차 ±0.2). */
    @Test
    void 비중_합이_백이다() throws Exception {
        JsonNode rows = json("/portfolio/views/allocation?axis=sector&lens=DIRECT").get("data").get("rows");
        BigDecimal sum = BigDecimal.ZERO;
        for (JsonNode row : rows) sum = sum.add(row.get("weight_pct").decimalValue());
        assertThat(sum).isCloseTo(new BigDecimal("100.0"), within(new BigDecimal("0.2")));
    }

    /** 렌즈를 켜도 total은 변하지 않는다 — 총합 보존(스펙 §3.4 · §6.3). */
    @Test
    void 렌즈는_합계를_바꾸지_않는다() throws Exception {
        JsonNode direct = json("/portfolio/views/allocation?axis=sector&lens=DIRECT").get("data").get("total");
        JsonNode lensed = json("/portfolio/views/allocation?axis=sector&lens=LOOK_THROUGH").get("data").get("total");

        assertThat(lensed.get("total_assets_krw")).isEqualTo(direct.get("total_assets_krw"));
        assertThat(lensed.get("cost_amount_krw")).isEqualTo(direct.get("cost_amount_krw"));
        assertThat(lensed.get("unrealized_pnl_krw")).isEqualTo(direct.get("unrealized_pnl_krw"));
    }

    /** 스펙 §8.2 — rows가 비면 empty_reason이 필수다. */
    @Test
    void 빈_목록에는_반드시_empty_reason이_있다() throws Exception {
        JsonNode env = json("/portfolio/views/positions?asset_class=ETF&market=US");
        assertThat(env.get("data").get("rows")).isEmpty();
        assertThat(env.get("empty_reason").isNull()).isFalse();
    }
```

`allocation?axis=currency`가 통과하려면 통화 축의 두 그룹(KRW·USD)이 각각 단일 통화이므로 USD 그룹에만 현지 통화가 실린다 — `positions`와 `allocation?axis=instrument`·`axis=currency`만 `market_value_local`을 가질 수 있다.

- [ ] **Step 4: `docs/decisions.md`**

§A.2의 네 결정을 그대로 옮긴다 — 후보, 기각 사유, 채택 근거, **감수하는 것**, **되돌리는 조건**. 특히:
- 데이터 접근을 `JdbcClient`로 정한 결정과 jOOQ로 옮기는 조건(질의 15개 초과 또는 4단계를 SQL로 이동).
- 집계를 Java에서 하는 결정과, SQL 구현을 추가할 때 **두 구현 대조 테스트를 함께 넣는다**는 조건.
- 인덱스·보관 기간·파티셔닝 트리거(§A.2.5).
- 인증을 넣지 않은 이유와 언제 결정하는지.

- [ ] **Step 5: `README.md`**

- 실행: `docker compose up -d --build` → 샘플 적재 → `curl` 6개.
- 스택과 버전.
- **인증이 없고 로컬 전용**이라는 경고.
- 소유 테이블 경계: `db/migration`(백엔드) vs `db/external`(데이터팀 미러, 운영 미적용).
- 범위 밖 목록과 이유 링크(§A.9).
- 스펙 링크.

- [ ] **Step 6: 전체 검증과 커밋**

```bash
./gradlew clean test
# 위 검증 방법의 curl 루프 실행 — 전부 200
git add -A && git commit -m "test: 6개 뷰 골든 테스트와 불변식 교차 검증 · docs: 결정 기록"
```

---

# Part E — 실행 순서와 남은 확인

## E.1 태스크 의존과 병렬화

```
1 ─ 2 ─ 3 ─ 4 ─ 5 ─ 6 ─ 7 ─┬─ 8 ─┐
                            ├─ 9 ─┼─ 11
                            └─ 10 ┘
```

8·9·10은 서로 다른 서비스·DTO를 만들고 공유 상태가 없어 병렬로 진행할 수 있다. 단 셋 다 `api/ViewController.java`를 수정하므로, 병렬로 돌리면 그 파일에서 충돌한다 — 컨트롤러를 뷰별로 셋으로 쪼개거나(`SnapshotViewController` · `RealizedPnlController` · `AssetChangeController`) 순차로 처리한다. **쪼개는 쪽을 권한다** — 파일이 함께 바뀌는 이유가 없다.

## E.2 착수 전에 답이 있으면 좋은 것 (없어도 진행 가능)

| 질문 | 없을 때의 진행 방식 |
|---|---|
| 지표 12개·notice 13종이라는 수치의 출처 | 스펙 §6.2·§8.2의 17개·16종으로 진행한다(§A.10 #1·#2) |
| `PRICE_LAG_MARKET`용 시장별 가격 기준일을 어디에 담을지 | 이번 범위에서 발화하지 않는다. 1단계 설계 때 `position_line`에 컬럼 추가를 검토한다(§A.10 #3) |
| §3.7 표와 본문의 우선순위 | 두 게이트를 모두 통과할 때만 병기한다. 표 쪽으로 좁히려면 `Axis.localCurrencyEligible`만 고치면 된다(§A.10 #4) |
| CASH 행의 종목수 표기 | 0으로 내리고 화면이 숨긴다(§A.10 #5) |

## E.3 이 계획이 검증하는 스펙 항목 대조

| 스펙 절 | 태스크 |
|---|---|
| §1.3 그레인 · §3.1 팩트 그레인 | 1(PK) · 4(검증기) |
| §1.5 · §3.2 저장 규칙·가산성 | 1(린트) · 3(타입) · 6(엔진) |
| §3.3 축과 필터 | 2(카탈로그) · 4(마스터 조인·필터) |
| §3.4 렌즈 | 5 |
| §3.5 뷰 사양 | 2 |
| §3.6 파이프라인 2~6단계 | 4·5·6·7·8 |
| §3.7 통화 표시 | 3(CurrencySet) · 7(정책) · 11(교차 검증) |
| §5.1 테이블 | 1 |
| §5.2 예수금을 종목으로 | 1(샘플) · 3(2슬롯) · 7(응답 null) |
| §5.3 원화 환산 머티리얼라이즈 | 1(컬럼) · 7(`FX_APPLIED`·`FX_STALE`) |
| §5.5 타입 정책·반올림 | 1(numeric) · 3(비율 1자리) |
| §6.1~6.4 카탈로그·서빙 계약 | 2 · 8(카탈로그 엔드포인트·요청 검증) |
| §8.1 엔드포인트 | 8·9·10 |
| §8.2 봉투·notice·empty_reason | 7 |
| §8.3 스냅샷 뷰 응답 | 7·8 |
| §8.4 실현손익·자산 변화 응답 | 9·10 |
| §8.6 오류와 빈 상태 | 7·8 |
| §9.1 런타임 검증(`position_line`·렌즈) | 4·5 |
| §9.2 스키마 규약 | 1(린트) · 3(ArchUnit) |
| §9.3 요청 검증·응답 조립 | 7·8 |
| §10 화면 상태 전수 | 7·8·9·10 (빈 상태·경고·계좌 상태 세 표현 수단) |
| §13이 계획에서 확정하라 한 것 | §A.2.5(인덱스·보관·파티셔닝) · §A.9(API 인증) |

**이번 범위에서 다루지 않는 스펙 절**: §4(3원장·등급 판정 — 1.5/1.6단계) · §7(계좌 연동·동기화) · §9.1의 평단·등급 묶음 · §11(역할 분담, 문서) · §12(YAGNI 경계, 의도적 제외).

## E.4 실행 방식 선택

계획이 `docs/yhr/plan/2026-08-09-portfolio-query-layer-plan.md`에 저장됐다. 실행은 두 갈래다.

1. **서브에이전트 주도 (권장)** — 태스크마다 새 서브에이전트를 띄우고 태스크 사이에 리뷰한다. 컨텍스트가 태스크 단위로 깨끗하고 반복이 빠르다. `superpowers:subagent-driven-development`.
2. **인라인 실행** — 이 세션에서 태스크를 이어서 실행하고 체크포인트에서 리뷰한다. `superpowers:executing-plans`.
