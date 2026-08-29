# 포트폴리오 종합 관리 — 백엔드 조회 계층 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

- **작성일**: 2026-08-09
- **대상 저장소**: `back-end/` (github.com/stock-project-crew/back-end)
- **근거 스펙**: [`2026-07-28-portfolio-management-spec.md`](../specs/portfolio-management/2026-07-28-portfolio-management-spec.md) · [와이어플로우](../specs/portfolio-management/wireflow.png) · [설계 공유 문서](../meetings/2026-08-09-portfolio-design-review.md) · [KIS 실측](../verification/kis-portfolio-assumptions.md)
- **스펙 수정 금지**: 이 계획은 스펙을 인용만 한다. 스펙 파일을 고치지 않는다.

**Goal:** `position_line`에 손으로 넣은 샘플 행만으로 6개 뷰의 REST 응답이 전부 나오는, 실행 가능한 조회 계층 뼈대를 만든다. 로그인한 사용자는 **자기 계좌의 자산만** 본다.

**Architecture:** 저장은 `position_line` 한 종류이고, 화면은 `group_by`만 바꾼다. 조회 요청은 한 개의 집계 쿼리로 처리한다 — 렌즈 CTE가 **인증 주체의** 대상 행 집합을 만들고, 마스터를 조인해 축을 붙이고, 필터를 걸고, 요청 축으로 `GROUP BY`하며 측정값을 `SUM`한다(스펙 §3.6의 2~4단계). 파생 지표와 응답 조립만 Java가 맡는다(5~6단계). 가산 가능한 측정값과 가산 불가능한 비율이 **서로 다른 타입**으로 분리되어 있어 비율을 더하는 코드는 컴파일되지 않는다.

**Tech Stack:** Java 21 · Spring Boot 3.4.5 · Gradle (Kotlin DSL) · PostgreSQL 16 · Flyway · MyBatis (ORM 없음) · Spring Security + JWT · Docker Compose · JUnit 5 + AssertJ + ArchUnit

---

## Global Constraints

이 절의 규칙은 모든 태스크의 요구사항에 암묵적으로 포함된다.

- **Java 21** (`--release 21`), **Spring Boot 3.4.5**, **Gradle 8.12+ Kotlin DSL**, **PostgreSQL 16**.
- **JSON 필드명은 snake_case.** Jackson `PropertyNamingStrategies.SNAKE_CASE`를 전역 설정한다. 스펙 §8의 예시가 모두 snake_case다.
- **비율·수익률 성격 컬럼을 스키마에 만들지 않는다** (스펙 §1.5 · §9.2). 마이그레이션 SQL을 정적 검사하는 테스트로 강제한다(Task 1).
- **금액 반올림은 라인 단위에서 한 번만.** 집계는 저장값을 그대로 더하고 집계 후 재반올림하지 않는다(§5.5).
- **비율은 응답 직전에 소수 1자리, `RoundingMode.HALF_UP`**. 분모가 0 또는 null이면 값은 `null`(0이 아니다).
- **모든 금액 계산은 `BigDecimal`.** `double`/`float`를 금액·수량·환율·비율에 쓰지 않는다. ArchUnit으로 강제한다(Task 3).
- **참조 테이블의 스키마는 SQL에 박지 않는다.** `instrument`는 데이터팀이 소유하고 백엔드가 만들지 않으므로(§11.2), 그 테이블이 어느 스키마에 놓이는지를 이쪽이 정하지 않는다. SQL은 스키마 무자격 이름으로 쓰고 해석은 JDBC URL의 `currentSchema`가 정한다 — 로컬·테스트는 `public`이다. 배치가 달라져도 코드는 그대로다.
- **데이터팀 소유 테이블을 백엔드 마이그레이션이 만들지 않는다.** 소유 경계는 스펙 §11.2 — 백엔드는 `account` · `position_line` · `position_basis` · `realized_pnl_line` · `sync_run`만 소유한다. 조인에 필요한 `instrument`는 로컬·테스트 전용 미러로만 만든다(§A.2.3).
- **모든 조회는 인증 주체의 데이터로 스코프된다**(스펙 §3.8). 스코프는 요청 파라미터가 아니라 토큰에서 오고, 강제 방법은 §A.3 불변식 5다.
- **한국어 라벨·메시지는 서버가 완성해 내린다**(§8.2). 클라이언트는 `message`를 그대로 출력하고 `code`로 분기한다.
- **커밋 메시지는 Conventional Commits** (`feat:` · `test:` · `chore:` · `docs:`). 각 태스크 끝에 1커밋.

---

# Part A — 배경 (이 계획만 읽고 구현할 수 있게 옮겨 담은 것)

## A.1 도달점과 범위

**도달점.** `docker compose up` → 샘플 SQL 실행 → 로그인해 얻은 토큰으로 아래 요청이 모두 `200`과 유효한 응답 봉투를 반환하고, **다른 사용자의 토큰으로 부르면 그 사용자의 값이 나온다.**

```
POST /auth/login
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

**스펙 §9 검증 규칙 중 이번 범위는 9.1의 사용자 스코프·`position_line`·렌즈 관련과 9.3 전부.** 9.1의 평단·등급 묶음은 1.5/1.6단계에 속해 제외한다.

## A.2 스택 선택과 근거

### A.2.1 빌드 도구 — **Gradle (Kotlin DSL)**

Maven과 기능 차이가 결과를 가르지 않는다. Gradle을 고른 이유는 (1) Spring Initializr 기본값이라 팀원이 프로젝트를 다시 생성해도 같은 모양이 나오고, (2) 증분 빌드로 테스트 반복이 빠르며, (3) 테스트 전용 설정이 한 파일에 모이기 때문이다. **근거가 취향 수준이라는 점을 그대로 적어 둔다** — Maven으로 바꿔도 이 계획의 나머지는 한 줄도 변하지 않는다.

### A.2.2 마이그레이션 — **Flyway (평문 SQL)**

Liquibase를 기각한 이유가 두 가지다.

1. **DB가 PostgreSQL 하나로 고정**이라 Liquibase의 DB 추상화(XML/YAML changeSet)가 값을 하지 않고 간접층만 늘린다.
2. **스펙 §9.2가 "비율 성격 컬럼은 스키마에 존재 불가 — 마이그레이션 리뷰에서 강제"를 요구한다.** 평문 SQL이면 이 규칙을 리뷰가 아니라 **테스트**로 바꿀 수 있다. `db/migration/*.sql`을 읽어 금지 패턴(`_pct` · `_ratio` · `_rate_of_return` · `weight` · `yield`)이 컬럼 정의에 나오면 실패하는 테스트를 Task 1에서 만든다. Liquibase XML이면 같은 검사가 changeSet 파서를 요구한다.

### A.2.3 데이터 접근 — **MyBatis (ORM 없음)**

SQL을 사람이 쓰고, 동적 조립을 매퍼 XML이 맡는다.

| 후보 | 기각 사유 |
|---|---|
| **Spring Data JPA / Hibernate** | 아래에 따로 적는다 |
| **jOOQ** | 강점 — 타입 안전한 동적 질의 조합 — 이 이 설계에 잘 맞는다. 코드 생성을 켜면 조인 대상 `instrument`가 데이터팀 소유라 소유하지 않은 테이블의 DDL 미러를 빌드 입력으로 유지해야 하고, 그 미러가 조용히 드리프트하는 두 번째 진실의 출처가 된다. 코드 생성을 끄면 그 문제는 사라지지만 남는 것은 쿼리 조립기뿐이라 MyBatis 대비 이점이 좁아진다 |
| **Spring JDBC `JdbcClient`** | 부품이 가장 적지만 반복되는 절(`GROUP BY` 축 목록, 선택적 필터)을 Java 문자열로 이어 붙이게 된다. 같은 일을 `<foreach>`·`<where>`가 언어 기능으로 제공한다 |

**JPA를 기각한 이유** — 관심 있는 후보라 자세히 적는다. 요약하면 **이 기능은 JPA가 잘하는 일을 하나도 하지 않는다.**

| # | 이유 |
|---|---|
| 1 | **반환이 엔티티가 아니라 프로젝션이다.** 이 계층은 축 값별 합계를 낸다. 영속성 컨텍스트·더티 체킹·지연 로딩·1차 캐시가 전부 쓰이지 않는다. JPA의 값은 그 기능들에 있는데 하나도 쓰지 않으면서 무게만 진다 |
| 2 | **`GROUPING SETS`가 JPQL에 없다.** 행·소계·전체 합계를 한 스캔에서 얻는 것이 이 설계의 핵심인데(§A.2.4) 표현할 방법이 없다. 네이티브 쿼리로 내려가면 `EntityManager`를 통해 문자열 SQL을 쓰는 셈이라, JPA를 쓰는 게 아니라 **JPA를 우회하는 코드**가 된다 |
| 3 | **동적 `GROUP BY`를 Criteria API로 쓰면 읽히지 않는다.** 축 8개 × 렌즈 2종 × 필터 조합을 `CriteriaBuilder`로 조립한 코드는 카탈로그 표(§A.4.1)와 대조가 불가능하다. 이 계획은 "스펙 문장과 SQL을 눈으로 맞춰본다"를 검증 수단으로 삼는다 |
| 4 | **엔티티가 파생 필드를 두도록 유혹한다.** `@Transient BigDecimal weightPct` 하나가 스펙 §1.5의 "비율은 저장하지 않는다"를 사실상 무너뜨린다. 불변식 1을 타입으로 지키려는 설계(§A.3)와 정면으로 어긋난다 |
| 5 | **소유 경계가 흐려진다.** `instrument`는 데이터팀 소유다(§11.2). `@Entity`로 매핑하면 우리 도메인 모델처럼 보이고, 스키마 배치가 미정이라 `@Table(schema = …)`에 박을 값도 없다 |
| 6 | **읽기 전용 팩트 테이블에 의식이 붙는다.** `position_line`은 복합 PK `(as_of, account_id, instrument_id)`라 `@IdClass`/`@EmbeddedId`가 필요하다. 쓰지도 않을 엔티티에 드는 비용이다 |

**JPA를 쓸 자리는 따로 있다.** 계좌 연동과 `manual_cashflow` 입력은 엔티티 단위 CRUD라 JPA가 실제로 잘하는 일이다. 실무에서도 **CRUD는 JPA, 조회·집계는 MyBatis나 네이티브 SQL**로 갈라 쓰는 구성이 흔하다. 이 계층에 넣는 것은 가장 안 맞는 자리에 넣는 것이므로, 도입한다면 후속 단계의 쓰기 경로에서 한다.

**채택 근거.**

1. **동적 조립이 XML의 언어 기능으로 표현된다.** 축 목록은 `<foreach>`, 선택적 필터는 `<where><if>`, 렌즈 CTE는 `<sql>` 조각 두 개와 `<include>`다. Java 문자열 이어 붙이기가 사라진다.
2. **SQL이 문자 그대로 남아 스펙과 1:1로 대조된다.** 리뷰어가 "§6.2의 `cash_included = 제외`가 이 `FILTER (WHERE asset_class <> 'CASH')`인가"를 눈으로 확인할 수 있다.
3. 코드 생성 단계가 없어 데이터팀 소유 테이블의 DDL 미러를 **빌드가 아니라 로컬·테스트 프로필에만** 둘 수 있다.
4. 결과 매핑이 `<resultMap>`으로 선언되어, 집계 결과가 `MeasureBundle`의 두 슬롯(§A.3 불변식 2)으로 어떻게 들어가는지가 한 곳에 보인다.

**감수하는 것과 완화.**

- **축 식은 값 바인딩(`#{}`)이 아니라 문자열 치환(`${}`)을 쓴다.** 컬럼 이름과 표현식은 바인딩할 수 없기 때문이다. `${}`에 들어가는 값은 **카탈로그 대조(§9.3)를 통과한 `AxisKey` enum이 고른 상수뿐**이며 요청 문자열이 닿지 않는다. → 이 규칙을 테스트로 고정한다(Task 6): 매퍼에 넘기는 축 목록의 타입이 `List<AxisKey>`이고 `String`을 받는 경로가 없다.
- 컬럼명 오타와 조각 조합 실수를 컴파일이 잡지 못한다. → (a) 축 × 렌즈 조합마다 실제 DB에서 실행되는지 테스트로 확인하고(Task 6), (b) 모든 스냅샷 뷰에서 `Σ rows = total`을 검사해 조합이 틀리면 수치로 드러나게 하며(Task 12), (c) 데이터팀 소유 테이블은 `information_schema` 대조 테스트로 계약을 검사한다(Task 4).

**되돌리는 조건.** 축이나 지표가 늘어 XML 조각 조합이 사람 눈으로 검토되지 않는 수준이 되면 jOOQ(코드 생성 없이)로 옮긴다. 그때 바뀌는 것은 `query` 패키지와 매퍼 XML이고 나머지 계층은 인터페이스로 격리돼 있다.

### A.2.4 집계 위치 — **SQL (Java는 파생 지표와 조립만)**

`GROUP BY`와 `SUM`은 DB가 한다. 스펙 §3.6의 2~4단계가 한 쿼리 안에서 끝나고, Java는 5단계(파생 지표)와 6단계(정렬·통화·조립)만 맡는다.

**렌즈도 SQL로 표현된다.** 스펙 §3.4가 렌즈를 "입력도 라인 집합, 출력도 라인 집합인 변환 함수"로 정의하는데, CTE가 정확히 그것이다. 렌즈 선택은 쿼리의 `WITH` 절 하나를 바꾸는 일이고, 그 아래 조인·필터·집계·파생은 렌즈와 무관하게 같은 모양으로 남는다 — §1.5가 요구하는 "하위 로직은 렌즈 적용 여부와 무관"이 쿼리 구조로 성립한다.

```sql
WITH target_line AS ( <DIRECT: position_line 그대로  |  LOOK_THROUGH: 안분 전개> )
SELECT <축 컬럼>, <측정값 SUM>
  FROM target_line t JOIN account a … JOIN instrument i …
 WHERE <필터>
 GROUP BY GROUPING SETS (<축 조합>, ())
```

**합계와 소계를 같은 스캔에서 얻는다.** `GROUPING SETS`가 행·소계·전체 합계를 한 결과로 내므로 `Σ rows = total`이 두 번 세는 것이 아니라 같은 집계에서 나온다. 계좌별 뷰의 2단계 중첩(§8.3)도 `GROUPING SETS ((account_type, account), (account_type), ())` 하나로 해결된다.

**CASH 분리는 `FILTER` 절이 한다.** 스펙 §6.2가 지표마다 정한 CASH 포함 여부가 SQL에 그대로 나타난다.

```sql
sum(t.market_value_krw)                                          AS total_assets_krw,
sum(t.market_value_krw) FILTER (WHERE i.asset_class <> 'CASH')   AS securities_value_krw,
sum(t.cost_amount_krw)  FILTER (WHERE i.asset_class <> 'CASH')   AS cost_amount_krw
```

**감수하는 것.** 불변식이 타입만으로 강제되지 않고 쿼리 조립에도 걸린다. → 집계 결과를 받는 타입(`MeasureBundle`)이 여전히 CASH를 두 슬롯으로 나눠 담고 비율을 담지 못하므로, **쿼리가 틀리면 매핑이 깨지거나 `Σ rows ≠ total` 테스트가 잡는다**(§A.3). 축 × 렌즈 조합마다 실제 실행 테스트를 둔다(Task 6).

### A.2.5 인덱스 · 보관 기간 · 파티셔닝 (스펙 §13이 구현 계획에서 확정하라고 한 것)

| 항목 | 결정 | 근거 |
|---|---|---|
| `app_user` 인덱스 | PK `user_id`, `email` UNIQUE | 로그인이 이메일로 한 행을 찾는다. UNIQUE가 곧 로그인 ID 유일성이다 |
| `account` 인덱스 | `(user_id)` + `account_ref` UNIQUE | 모든 조회가 계좌를 통해 사용자로 좁혀진다(§3.8). 계좌 수가 사용자당 한 자릿수라 이 인덱스 하나면 스코프 비용이 사라진다. `account_ref`의 UNIQUE는 유일성 강제이자 인덱스다 — 1단계가 `cln_*`을 이 값으로 조인해 `account_id`를 찾는다 |
| `account.user_id` FK | **건다** — `app_user` 참조 | `instrument`와 달리 같은 팀이 소유해 배포 순서가 묶이지 않는다. 소유자 없는 계좌는 스코프가 성립하지 않으므로 DB가 막는 편이 맞다 |
| `position_line` PK | `(as_of, account_id, instrument_id)` | 그레인 유일성을 DB가 1차 보증(§9.1) |
| `position_line` 보조 인덱스 | `(account_id, as_of)` | 자산 변화 뷰의 계좌 필터 + 기간 경계 조회 |
| `realized_pnl_line` 인덱스 | PK `trade_id`, 보조 `(sold_at)` · `(account_id, sold_at)` | 기간 귀속이 체결일(§4.3) |
| 보관 기간 | **무제한 삭제 없음** | 자산 변화 뷰가 과거 스냅샷을 읽고(§5.4), 지우면 과거 기간 계산이 불가능해진다(§7.5) |
| 파티셔닝 | **하지 않는다** | 연 증가량이 영업일 250 × 라인 수십 = 만 행 규모. 트리거를 미리 정해둔다: `position_line`이 1,000만 행을 넘거나 단일 `as_of` 조회 p95가 200ms를 넘으면 `as_of` RANGE 파티셔닝을 검토한다 |
| enum 표현 | **`text` + `CHECK`** (PostgreSQL ENUM 타입 아님) | ENUM 타입은 값 추가·삭제 마이그레이션이 번거롭고 매핑에서 이득이 없다 |
| 테스트 DB | compose의 **`portfolio_test`** 데이터베이스. 개발용 `portfolio`와 같은 인스턴스, 다른 DB | 테스트가 개발 데이터를 지우지 않는다. 시드 스크립트가 매 테스트 `TRUNCATE` 후 채우므로 격리는 그것으로 충분하고, Java에서 Docker API를 부르지 않아 도구 버전에 묶이지 않는다 |
| 마이그레이션 번호 | `db/migration`과 `db/external`을 통틀어 **하나의 순열**. 새 파일은 폴더와 무관하게 다음 번호 | 두 폴더가 이력 테이블 하나를 공유하므로 번호대를 예약하면 낮은 번호가 뒤늦게 나타나 순서 검증에 걸린다. 파일을 쓰는 쪽이 백엔드 하나뿐이라 예약이 막을 충돌도 없다. 운영에서는 미러 번호가 비지만, 번호가 비는 것은 순서 위반이 아니다 |
| 스키마 변경 방식 | 첫 운영 배포 전까지는 **기존 파일을 고치고 DB를 재생성**한다 | 지금 이 스키마가 도는 곳은 로컬과 테스트뿐이라 체크섬을 지킬 대상이 없고, 재생성 비용이 `docker compose down -v` 한 번이다. 번호를 더해 나가면 계획서 §C가 "최종 스키마"가 아니라 변경 누적본이 되어 읽는 사람이 여러 파일을 합성해야 한다. 운영에 처음 올리는 시점에 이 규칙을 닫고 그 뒤로는 새 번호만 더한다 |
| 참조 테이블 스키마 | SQL 무자격 + JDBC `currentSchema` | `instrument`는 데이터팀 소유라(§11.2) 스키마 배치를 이쪽이 정하지 않는다. SQL에 박으면 배치가 바뀔 때 코드를 고쳐야 한다 |
| `instrument` FK | **걸지 않는다** | 소유 팀이 달라(§11.2) 교차 소유 FK는 배포 순서를 묶는다. 미매칭은 조인 결과 null로 드러나고 검증기가 잡는다 |

## A.3 반드시 지켜야 할 불변식 다섯 가지와 강제 방법

이 다섯 개가 이 계획의 존재 이유다. 각 항목의 "구조로 강제"가 구현의 합격선이다.

### 불변식 1 — 비율은 저장하지 않고 집계 후 계산한다 (§1.5 · §3.2 · §9.2)

```
삼성전자    매입 1,000만  평가 1,100만  → +10%
SK하이닉스  매입   100만  평가   130만  → +30%
라인별 평균 = (10+30)/2            = +20%     ← 틀림
집계 후 계산 = (1,230−1,100)/1,100 = +11.8%   ← 맞음
```

**구조로 강제하는 방법 네 겹.**

1. 스키마에 비율 컬럼이 없다 → 마이그레이션 SQL 정적 검사 테스트(Task 1).
2. **집계 쿼리가 비율을 뽑지 못한다.** `SELECT` 목록을 만드는 빌더가 `Additivity.ADDITIVE`인 지표만 받는다. `weight_pct`를 넘기면 조립 단계에서 거부된다(Task 6).
3. 집계 결과를 받는 타입 `Measures`에 비율 필드가 없다 → ArchUnit이 `Measures`·`MeasureBundle`의 필드명에 `Pct`/`Ratio`/`Rate`가 등장하면 실패시킨다(Task 3).
4. 비율은 `Derived`의 static 메서드만 만들 수 있고, 입력이 **집계된 번들**이라 라인 하나로는 호출 자체가 성립하지 않는다(Task 3).

### 불변식 2 — 비중의 분모는 총자산(예수금 포함), 손익률의 분모는 매입금액(예수금 제외) (§6.2 · §9.3)

**구조로 강제하는 방법.** CASH 분리가 쿼리와 타입 양쪽에 나타난다.

쿼리에서는 `FILTER` 절이 슬롯을 가른다. 스펙 §6.2의 CASH 열이 SQL에 그대로 보인다.

```sql
sum(t.market_value_krw)                                        AS all_market_value_krw,
sum(t.market_value_krw) FILTER (WHERE i.asset_class <> 'CASH') AS sec_market_value_krw,
sum(t.cost_amount_krw)  FILTER (WHERE i.asset_class <> 'CASH') AS sec_cost_amount_krw
```

결과를 받는 타입은 그 둘을 **물리적으로 갈라** 담는다.

```java
record MeasureBundle(Measures securities /* asset_class <> CASH */,
                     Measures cash      /* asset_class =  CASH */, ...)
```

- 손익 계열(`cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct`)을 만드는 함수는 `securities` 슬롯만 읽는다. CASH를 섞을 코드 경로가 없다.
- 비중의 분모는 **`TotalAssetsKrw`라는 별개 타입**만 받는다. 이 타입의 유일한 생성 경로는 집계 산출물 `Aggregation`의 `weightDenominator()`이고, 그 값은 `GROUPING SETS`의 **전체 합계 행**에서 온다. 그룹 자신의 합계로 비중을 계산하는 실수는 타입이 막는다.

### 불변식 3 — 집계 값은 항상 원화, 묶음이 단일 통화일 때만 현지 통화 병기 (§3.7 · §9.3)

**구조로 강제하는 방법.** 집계 쿼리가 그룹마다 통화 집합을 함께 낸다.

```sql
array_agg(DISTINCT i.currency) AS currencies
```

`MeasureBundle`이 그것을 `CurrencySet`으로 담고, 현지 통화 금액은 `Optional<LocalMoney>`로만 꺼낼 수 있다. 집합 크기가 1이 아니면 `Optional.empty()`다 — 응답 조립기가 섞인 그룹에 현지 통화를 실을 방법이 없다.

**판정자는 `CurrencySet.single()` 하나다. 축 이름을 보지 않는다.** 스펙 §3.7이 "판정은 조회 시점에 이 묶음이 단일 통화인가로 한다"고 정한다 — 축 이름을 하드코딩하면 축이 늘 때마다 목록을 고쳐야 한다. 카탈로그에 축별 병기 허용 플래그를 두지 않는 이유가 이것이다.

단일 통화가 `KRW`이면 병기하지 않는다 — 원화가 곧 현지 통화라 중복이다.

| 묶음 | 샘플에서의 판정 | 근거 |
|---|---|---|
| 종목 1행 (AAPL) | 병기 | 정의상 단일 통화 |
| 통화 축 `USD` · 시장 축 `US` | 병기 | 정의상 단일 통화 |
| 섹터 `IT서비스` (AAPL 단독) | **병기** | 우연히 단일 통화 — 런타임 판정이라 잡힌다 |
| 섹터 `소프트웨어` (NAVER + MSFT) | 원화만 | 통화 혼합 |
| 계좌 `미래에셋 연금` (MSFT + USD 예수금) | **병기** | 우연히 단일 통화 |
| 계좌 `한국투자 위탁` · 포트폴리오 전체 | 원화만 | 통화 혼합 |

### 불변식 4 — 행 키와 합계 키는 이름이 겹치지 않는다 (§6.2)

같은 키가 행에서는 CASH를 포함하고 합계에서는 제외하면 소비자가 `Σ rows`와 `total`을 대조했을 때 어긋난다.

| 키 | 등장 위치 |
|---|---|
| `market_value_krw` | **행 전용** — `total`에 넣지 않는다 |
| `total_assets_krw` · `securities_value_krw` · `cash_ratio_pct` · `daily_change_krw` · `daily_change_pct` · `account_count` | **합계 전용** — `rows[]`에 넣지 않는다 |
| `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` · `instrument_count` | 행·합계 양쪽 (양쪽 모두 CASH 제외 의미로 동일) |
| `deposit_krw` | 행·합계 양쪽 (양쪽 모두 그 묶음의 CASH 평가금액 합 — §A.4.3 각주) |
| `quantity` · `avg_cost` · `weight_pct` | 행 전용 |

**구조로 강제하는 방법.** 카탈로그 `Metric`에 `scope: ROW | TOTAL | BOTH`를 두고, 응답 조립기가 `scope`를 보고 목적지를 정한다. 그리고 `Σ rows.market_value_krw == total.total_assets_krw`를 **모든 스냅샷 뷰 응답에서 검사하는 테스트**를 둔다(Task 6·9).

### 불변식 5 — 조회는 인증 주체의 데이터로만 스코프된다 (§3.8 · §8.8 · §9.1)

한 테이블에 여러 사용자의 자산이 함께 있으므로, `WHERE` 절 하나를 빠뜨리면 남의 자산이 총합에 섞이고 남의 계좌가 목록에 보인다. 앞의 네 불변식과 달리 **위반해도 값이 이상해 보이지 않는다** — 총자산이 좀 커 보일 뿐이다. 그래서 강제를 코드 리뷰에 맡기지 않는다.

**구조로 강제하는 방법 네 겹.**

1. **스코프가 CTE 안에 있다.** `targetLine` 조각이 `account`를 조인하고 `user_id`를 건다(Task 5). 그 아래 조인·필터·집계는 이미 좁혀진 집합을 받으므로 스코프를 다시 걸 자리도, 빠뜨릴 자리도 없다. 스펙 §3.8의 "스코프는 2단계 앞에 선다"가 쿼리 구조로 성립한다.
2. **매퍼가 스코프 없이 호출되지 않는다.** 사용자 소유 테이블을 읽는 모든 매퍼 메서드가 `UserScope`를 첫 파라미터로 받는다. 리플렉션 테스트가 매퍼 인터페이스를 훑어 이를 검사한다(Task 8).
3. **`UserScope`는 `LineFilter`와 다른 타입이다.** 필터는 사용자가 고르는 것이고 스코프는 고를 수 없는 것이라(§3.8), 한 타입에 담으면 `LineFilter.NONE`으로 스코프까지 비워진다. 두 타입이 갈려 있으면 그 실수가 컴파일되지 않는다.
4. **컨트롤러가 `user_id`를 받지 않는다.** ArchUnit이 `api` 패키지의 핸들러 시그니처에 `user`·`userId` 이름의 `@RequestParam`·`@PathVariable`이 있으면 실패시킨다(Task 8).

```java
/** 스코프 — 인증 주체가 정한다. 요청이 고를 수 없어 LineFilter와 타입을 나눈다(§3.8). */
public record UserScope(UUID userId) { }
```

그리고 **샘플 데이터가 네 사용자를 담는다**(§C). 스코프가 새면 골든 값 58,000,000이 74,000,000이 되어 Task 12의 골든 테스트가 즉시 깨진다 — 검사를 잊어도 수치가 말한다.

## A.4 카탈로그 — 실제 값

**코드 상수다. DB 테이블이 아니다**(§6). 운영자가 런타임에 뷰를 추가하지 않는다.

### A.4.1 축 8개 (§6.1)

```
Axis { key, label, source, applicableViews[], lensSensitive, enabled }
```

축에 현지 통화 병기 플래그를 두지 않는다 — 판정은 런타임 통화 집합으로만 한다(불변식 3).

| key | 라벨 | 출처 | 사용 뷰 | `lensSensitive` | `enabled` |
|---|---|---|---|---|---|
| `account` | 계좌 | 계좌 마스터 | `accounts` | false | true |
| `account_type` | 계좌유형 | 계좌 마스터 | `accounts` | false | true |
| `instrument` | 종목 | 종목 마스터 | `positions` · `allocation` | **true** | true |
| `sector` | 섹터 | 종목 마스터 | `allocation` | **true** | true |
| `market` | 시장 | 종목 마스터 | `allocation` · `summary` 미니차트 | **true** | true |

**시장 축은 CASH 폴백을 쓰지 않는다.** 예수금도 그 통화가 속한 시장에 넣는다 — 원화 예수금은 국내 자산의 일부이지 시장이 없는 무언가가 아니다. §C.5의 미니차트 `KR = 46,800,000`이 KRW 예수금 4,560,000을 포함한 값이다.
| `currency` | 통화 | 종목 마스터 | `allocation` | **true** | true |
| `asset_class` | 자산군 | 종목 마스터 | `allocation` · `summary` 미니차트 | **true** | true |
| `is_leveraged` | 레버리지 | 종목 속성 | `allocation` | **true** | **false** — 원천 미확보, 요청 시 거부(§9.3) |

`account` 계열이 `lensSensitive = false`인 이유: look-through가 총합을 보존하므로 계좌 합계가 렌즈에 흔들리지 않는다. 그래서 `LOOK_THROUGH`에서도 계좌 필터만 허용된다(§9.3).

**사용자 축은 없다.** 축은 한 사람의 자산을 묶는 기준이고 사용자는 대상 행 집합 자체를 정하므로, `AxisKey`에 값을 추가하지 않고 `UserScope`로 다룬다(§A.3 불변식 5).

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
| `deposit_krw` | 예수금 | ○ | 포함 | `ROW_AND_TOTAL` | BOTH | `Σ CASH 평가금액` |
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
| `summary` | 전체 1행 | `[]` | `total_assets_krw` · `securities_value_krw` · `deposit_krw` · `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` · `cash_ratio_pct` · `daily_change_krw` · `daily_change_pct` · `account_count` · `instrument_count` | — / — | `NONE` (미니차트 `subBlock`에 `OPTIONAL`) | 스냅샷 |
| `positions` | 종목 1행(계좌 합산) | `[instrument]` | `quantity` · `avg_cost` · `cost_amount_krw` · `market_value_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` · `weight_pct` | `account`·`market`·`asset_class` / **`account`만** | `OPTIONAL` | 스냅샷 |
| `allocation` | 축 값 1행 | 축 1개 택일: `instrument`·`sector`·`market`·`currency`·`asset_class`(·`is_leveraged` 비활성) | `market_value_krw` · `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` · `weight_pct` · `instrument_count` | `account`·`account_type` / `account`·`account_type` | `OPTIONAL` | 스냅샷 |
| `accounts` | 계좌 1행 | `[account_type, account]` | `market_value_krw` · `deposit_krw`\* · `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` · `weight_pct` | `account` / `account` | `NONE` | 스냅샷 |
| `realized-pnl` | 기간 × 종목 × 체결 | `[instrument, trade]` | `sell_amount_krw` · `cost_basis_krw` · `realized_pnl_krw` · `realized_pnl_pct` | `account`·`period` | `NONE` | 거래 |
| `asset-change` | 기간 × 현금흐름 유형 | — | — (§A.6.3 전용 스키마) | `account`·`period` | `NONE` | 스냅샷 + 현금흐름 |

\* `accounts` 뷰의 `deposit_krw`는 **행에도 실린다.** §2.7이 계좌 행 컬럼으로 예수금을 요구하고 응답 키를 `market_value_krw`(계좌 총자산) · `deposit_krw`로 못 박았다. 유가증권 평가금액은 클라이언트가 차감해 표시한다. 불변식 4와 충돌하지 않는다 — `deposit_krw`의 의미가 행·합계에서 같기 때문이다(그 묶음의 CASH 평가금액 합).

- **스냅샷 4개 뷰는 합계 블록을 공유한다**(§A.6.1). `total_assets_krw` · `securities_value_krw` · `deposit_krw` · `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` · `cash_ratio_pct` · `instrument_count` · `account_count` 아홉 개가 `group_by`와 무관하게 같은 묶음의 값이라 뷰가 달라도 키가 같고, 요약만 `daily_change_krw` · `daily_change_pct`를 더한다. 위 표의 지표 열은 그 뷰가 **행에** 싣는 것이며, 목적지 판정은 `Metric.scope`가 한다(불변식 4).
- `realized-pnl`의 `sell_amount_krw` · `cost_basis_krw`는 카탈로그 지표 17개에 없다. 축으로 묶는 값이 아니라 체결 노드의 값이라 §A.6.2의 전용 스키마가 정의한다.
- `rowFields[]` — 공통 행 스키마(§A.6.1)에 더해지는 필드. `accounts` 뷰는 `link_state` · `last_collection` · `last_synced_at` · `source_as_of` · `is_carried_forward`를 갖고(§6.3 · §7.4 · §8.2), `positions` 뷰는 시장 배지용 `market`을 갖는다. 둘 다 축이 아니라 표시용이며 집계에 참여하지 않는다.
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
- **봉투 `as_of`의 산출 규칙**: 대상 `as_of`의 라인 중 **캐리포워드가 아닌** 라인들의 `max(source_as_of)`. 그런 라인이 없으면 `as_of` 날짜의 `00:00:00+09:00`. 타임존은 `Asia/Seoul` 고정.
- **카탈로그 엔드포인트는 봉투를 쓰지 않는다** — 뷰 응답이 아니다.

### A.5.2 notice 코드 (스펙 §8.2 기준 **16종**)

| # | code | severity | 발생 조건 | params | 이번 범위 |
|---|---|---|---|---|---|
| 1 | `FX_APPLIED` | info | 원화 환산에 적용한 환율 (§2.3) | 통화쌍별 배열 `[{pair, rate, fx_as_of}]` + 최고령 `oldest_fx_as_of`. **통화쌍마다 한 항목**이며 기준일이 여럿이면 가장 오래된 것을 싣는다 — 화면이 "언제 환율인가"에 답할 때 가장 뒤처진 값을 말하는 편이 정직하다 | **발화** |
| 2 | `STALE_ACCOUNTS` | warn | 캐리포워드된 계좌 존재 (§7.3) | `count` · 최고령 `source_as_of` | **발화** |
| 3 | `CONSTITUENT_AS_OF` | info | 렌즈 적용 시 구성비중 기준일 (§3.4) | 최고령 기준일 `oldest` + 대상 ETF 수 `count` | 미발화 — 전개된 ETF가 0이면 생략(§A.9) |
| 4 | `CONSTITUENT_UNAVAILABLE` | warn | 구성종목 미확보 ETF 존재 (§3.4) | `count` · 미분해 평가금액 `undecomposed_krw` · 종목 심볼 `keys` | **발화** |
| 5 | `LENS_METRICS_OMITTED` | info | `TOTAL_ONLY` 지표가 행에서 빠짐 (§6.2) | 생략된 지표 키 배열 `metrics` | **발화** |
| 6 | `EXCLUDED_ACCOUNTS` | warn | 실현손익 합계에서 빠진 계좌 (§2.8) | `count` | 규칙 구현·샘플 미발화 |
| 7 | `SEEDED_ROWS` | warn | 추정 등급 행 존재 (§4.5) | `count` | **발화** (`realized_pnl_line.grade`에서) |
| 8 | `CA_UNKNOWN` | warn | 기업행위 이력 미확인 (§4.4) | `instrument_id` 배열 | 미발화 — `position_basis` 없음 |
| 9 | `CASHFLOW_UNCOVERED` | warn | 현금흐름 미확보 — 판정 단위는 **(계좌, 유형)** (§4.6) | `types` 배열 · `account_count` | **발화** (`DIVIDEND`·`FEE`·`TAX` 3유형 × 4계좌) |
| 10 | `PERIOD_TRUNCATED` | info | 기초 스냅샷 대체와 실제 시작일 (§2.9) | `actual_from` | **발화** |
| 11 | `BOUNDARY_CARRIED_FORWARD` | warn | 기간 경계 스냅샷에 이월 계좌 (§2.9) | `count` · `boundary` | **발화** |
| 12 | `REAUTH_REQUIRED` | warn | 재인증 대기 계좌 존재 (§7.2) | `count` | 규칙 구현·샘플 미발화 |
| 13 | `SYNC_IN_PROGRESS` | info | 동기화 진행 중 | `sync_run_id` | 미발화 — 동기화 범위 밖 |
| 14 | `PRICE_LAG_MARKET` | info | 시장별 가격 기준일이 화면 `as_of`보다 이르다 (§5.4) | 시장별 가격 기준일 | 미발화 — 시장 캘린더가 1단계 산출물이다 (§A.10) |
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

**판정 순서는 고정이다.** `NO_ACCOUNTS` → `NO_HOLDINGS` → (`realized-pnl`이면 `NO_TRADES_IN_PERIOD` → `ALL_UNAVAILABLE`) → `NO_MATCH_FILTER`. 먼저 맞는 것 하나만 내린다.

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
             "cash_ratio_pct": 8.1, "instrument_count": 6, "account_count": 4 },
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
- **CASH 행에서 `null`로 내리는 것은 금액 계열뿐이다** — `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` · `avg_cost`. 예수금은 사고판 것이 아니라 원가도 손익도 평단도 없다. 종목수는 세는 값이라 `0`이 사실이다.
- **CASH 행의 `instrument_count`는 `0`이다.** 지표 정의가 CASH를 제외하므로(§A.4.2) 자연히 0이 되며, 뷰별 예외를 두지 않는다. 화면은 CASH 행에서 종목수를 표시하지 않으면 된다.
- **현재가는 지표가 아니다.** `market_value_local ÷ quantity`로 얻을 수 있고 §2.5가 현재가를 종목 상세로 미루므로, 카탈로그 지표에 두지 않는다.

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
- **정렬**: `last_sold_at` 내림차순, 동률은 `key` 오름차순. 체결 노드도 같은 규칙이다.
- **기간의 기준일은 최신 `as_of`다.** `THIS_MONTH` · `THIS_YEAR` 같은 프리셋을 벽시계로 해석하면 스냅샷이 없는 날의 "이번 달"이 빈 응답이 되고 테스트가 날짜에 따라 깨진다. `asset-change`도 같다.

### A.6.3 자산 변화 (§8.4)

```json
{ "period": { "from": "2026-07-01", "to": "2026-07-31" },
  "opening": 56800000, "closing": 58000000,
  "deposited": 2000000, "earned": -800000,
  "account_included": 0, "account_excluded": 0,
  "breakdown": [ { "type": "DEPOSIT", "amount": 2000000 },
                 { "type": "INVESTMENT_PNL", "amount": -800000 } ],
  "investment_pnl": { "total": -800000, "realized": null,
                      "unrealized_change": null, "split_available": false } }
```

**항등식** (§2.9)

```
기말 총자산 = 기초 총자산 + 넣은 돈(입금−출금) + 번 돈(투자손익+배당−수수료·세금) ± 계좌 편입·제외
투자손익   = Δ총자산 − (입금−출금) − 배당 + 수수료·세금 − 계좌 편입·제외
```

- **투자손익은 나머지 전부로 정의한다.** 우변에 거래 원장이 들어가지 않아 체결내역이 막힌 연금계좌도 정확한 손익을 얻는다. **잔차 항목을 두지 않는다**(§4.6).
- **"넣은 돈"은 사용자 입력에서 온다**(§2.9 · §4.6). `DEPOSIT`·`WITHDRAW`는 백엔드 소유 `manual_cashflow`에서 읽고, `DIVIDEND`·`FEE`·`TAX`만 데이터팀 `cln_cashflow`에서 온다. 증권사 API가 입출금 이력을 열어주지 않는 경우가 있어 원천에 기댈 수 없다.
- **현금흐름 조회 구간은 요청 기간이 아니라 실제 기초·기말 스냅샷 구간이다.** 기초가 `PERIOD_TRUNCATED`로 대체되면 현금흐름도 그 날짜로 잘라야 한다 — 안 자르면 `넣은 돈`이 Δ총자산과 어긋나 항등식이 깨진다. 구간은 `(기초 as_of, 기말 as_of]`로 잡는다.
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
| `UNAUTHENTICATED` | 401 | 토큰 없음 · 만료 · 서명 불일치 (§8.8) |
| `INVALID_CREDENTIALS` | 401 | 로그인 실패. 이메일 없음과 비밀번호 불일치를 구분하지 않는다 |
| `FORBIDDEN_ACCOUNT` | 403 | 인증 주체 소유가 아닌 계좌를 필터로 지정 (§9.3) |

**빈 상태는 오류가 아니다.** `rows: []` + `empty_reason` + `200`이다.

**남의 계좌 지정은 빈 상태가 아니라 오류다.** `403`을 내는 이유는 조용히 비우면 존재하지 않는 계좌 ID(빈 결과)와 남의 계좌 ID(역시 빈 결과)가 같은 응답을 내야 하는데, 어느 쪽이든 응답이 달라지는 순간 계좌 ID의 존재 여부가 새기 때문이다. 처음부터 거부하면 그 구분이 필요 없다.

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

### A.7.2 `app_user` · `account` — 사용자와 계좌, 백엔드 소유 (§5.1)

소유권 축이 여기 있다. `app_user`가 스코프의 기준이고 `account.user_id`가 그것을 자산에 연결하는 유일한 고리다(§3.8).

**`app_user`**

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `user_id` | `uuid` PK | 토큰 `sub`가 이 값이다 |
| `email` | `text` UNIQUE NOT NULL | 로그인 ID |
| `password_hash` | `text` NOT NULL | BCrypt. 원문은 저장하지 않는다 |
| `display_name` | `text` NOT NULL | 화면 표시명 |
| `created_at` | `timestamptz` NOT NULL | |

행은 마이그레이션이 심는다(§C.1). 회원가입 경로를 두지 않는다(§12).

**`account`**

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `account_id` | `uuid` PK | |
| `user_id` | `uuid` NOT NULL | → `app_user` FK. 생성 후 변경 불가(§9.1) |
| `account_ref` | `text` NOT NULL UNIQUE | 데이터팀에 넘기는 불투명 문자열. `기관코드 + 계좌번호` 해시라 재연동해도 같은 값이다(§7.1). 생성 후 변경 불가(§9.1) |
| `broker` | `text` | 기관명 (`한국투자증권`) |
| `label` | `text` | 표시명. §8.5의 `by_account[].label`과 §2.7의 계좌 컬럼이 쓴다. 같은 기관에 계좌가 여럿이라(위탁·IRP) `broker`로는 구분되지 않는다 |
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

### A.7.4 `manual_cashflow` — 사용자 입력 입출금, 백엔드 소유 (§5.1)

증권사 API가 입출금 이력을 열어주지 않는 경우가 있어(KIS OpenAPI에는 해당 TR이 없다) `DEPOSIT`·`WITHDRAW`는 원천이 아니라 **사용자 입력**을 기본 경로로 둔다. 입력 빈도가 월 1~2건이고 사용자가 이체 기록으로 정확한 값을 아는 데이터라, "자동 연동만 지원"(§12) 원칙의 예외다.

| 컬럼 | 타입 | 비고 |
|---|---|---|
| `id` | `uuid` PK | |
| `account_id` | `uuid` | → `account` FK |
| `type` | `text` CHECK | `DEPOSIT` · `WITHDRAW` |
| `amount` | `numeric(20,0)` | |
| `currency` | `text` CHECK | `KRW` · `USD` |
| `occurred_on` | `date` | 사용자가 지정 |
| `memo` | `text` null | |

**입력 엔드포인트(`POST`)는 이번 범위가 아니다** — 조회 계층이 범위이고 입력은 쓰기 경로다. 샘플 행을 손으로 넣는 방식이 `position_line`과 같다. 단 §2.9가 워터폴의 `넣은 돈` 행에서 입력 화면으로 가는 진입점을 요구하므로, 후속 단계에서 가장 먼저 붙을 쓰기 경로다.

### A.7.5 `instrument` — 종목 마스터, **데이터팀 소유** (§5.1)

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

### A.7.6 예수금을 종목으로 취급한다 (§5.2)

`instrument.asset_class = CASH`인 통화별 의사종목(`KRW 예수금` · `USD 예수금`)을 두고 예수금도 `position_line`에 넣는다. 그러면 **총자산·현금비중·자산군 축이 모두 같은 팩트 하나에서 나온다.**

- **CASH 행의 원가는 평가금액과 같은 값으로 저장한다.** `null`을 두면 `fx_rate` 필수 규칙과 충돌하고 집계에서 NULL이 전파된다.
- 대신 **손익 계열 지표는 집계에서 `asset_class != CASH` 조건을 적용**한다 → 이 계획에서는 `MeasureBundle`의 두 슬롯이 그 조건이다(불변식 2).
- **응답의 CASH 행은 원가·손익을 `null`로 내린다.** 저장값과 노출값이 다르다.

## A.8 런타임 검증 (§9.1 중 이번 범위)

`position_line`을 읽은 직후, **집계 전에** 통과해야 한다. 위반은 조용히 넘기지 않고 `500 FACT_INVARIANT_VIOLATED`로 실패시킨다 — 손으로 넣은 샘플이 틀렸다는 뜻이므로 크게 터지는 쪽이 맞다.

**검증도 스코프 안에서 한다.** `PositionLineInvariants.validate(UserScope, LocalDate)`이며, 남의 데이터가 깨졌다고 내 화면이 `500`이 되지 않는다. 조회 경로가 이미 그 사용자만 읽으므로 검증 범위도 같아야 한다.

| 규칙 | 강제 지점 |
|---|---|
| 사용자 소유 테이블 조회는 `UserScope`로 좁혀진다 | **구조로 강제**(§A.3 불변식 5) — 매퍼 시그니처 리플렉션 테스트 + `targetLine` CTE + ArchUnit |
| `as_of` 후보는 그 사용자의 계좌에 라인이 있는 날짜뿐 (§3.8) | `SnapshotCalendarMapper`의 다섯 쿼리 전부가 `account` 조인 + `user_id` 조건 |
| `account.user_id`는 생성 후 변경 불가 | 이번 범위에 계좌 쓰기 경로가 없어 발생하지 않는다. 연동(§A.9)에서 강제 |
| `account.account_ref`는 생성 후 변경 불가 | 상동. UNIQUE 제약이 유일성만 1차 보증하고, 불변성은 연동에서 강제 |
| `position_line`은 `(as_of, account, instrument)`마다 **정확히 1행** — 그레인 유일성 | PK(1차) + `PositionLineInvariants`(적재된 라인 집합 재검사) |
| `market_value_krw`가 있으면 `fx_rate`·`fx_as_of` 필수 | `NOT NULL` 3개(1차) + 검증기(렌즈 산출 라인까지 커버) |
| 그 사용자의 연동이 유효한(`DISCONNECTED`가 아닌) 모든 계좌는 해당 `as_of`에 라인 존재 | 검증기 — 그 사용자의 `account` 목록과 대조. 빠뜨리면 그날만 총자산이 급락해 손실처럼 보인다 |
| `is_carried_forward = true`이면 `source_as_of < as_of` | **검증기 전용.** `timestamptz AT TIME ZONE`이 immutable이 아니라 CHECK 제약으로 표현할 수 없다 |
| CASH 행은 원가 = 평가금액 (§5.2) | 검증기 — `asset_class`가 다른 테이블에 있어 CHECK로 표현 불가 |
| 모든 라인이 종목 마스터에 매칭된다 (§11.2) | **검증기 전용.** `instrument`에 FK를 걸지 않아(§A.2.5) DB가 막지 못하고, 집계가 `instrument`를 내부 조인하므로 미매칭 라인의 금액이 총자산에서 조용히 빠진다 — `Σ rows = total`은 양쪽이 함께 줄어 통과한다 |
| look-through 전개 후 `Σ market_value_krw`가 전개 전과 일치 (총합 보존, 기타 버킷 포함) | 렌즈 CTE의 총합을 `position_line`의 총합과 대조하는 테스트 (Task 5) |
| `etf_coverage.state = UNAVAILABLE`인 ETF는 전개하지 않고 ETF 행을 남긴다 | `AggregateMapper.xml`의 `targetLine` 조각, `LOOK_THROUGH` 분기 (§A.9) |
| **`넣은 돈`은 `manual_cashflow`에서만 온다. `cln_cashflow`에 `DEPOSIT`·`WITHDRAW`가 있으면 거부** (§9.1 자산 변화) | **타입으로 강제** — `cln_cashflow`를 읽는 포트의 유형 enum이 `EarningsCashflowType { DIVIDEND, FEE, TAX }`라 두 값을 표현할 방법이 없다 |
| 기간 양 끝의 `position_line` 필요. 기초가 없으면 가장 이른 스냅샷으로 대체하고 실제 시작일 표시 (§9.1 자산 변화) | `AssetChangeViewService` (§A.6.3) |

**범위 밖인 §9.1 규칙과 이유**: `as_of` 영업일 생성·당일 외 수정 불가·비영업일 라인 미생성·`is_final` 보호는 모두 **라인을 만드는** 1단계 규칙이고, 평단·등급·실현손익 묶음은 1.5/1.6단계다.

## A.9 범위 제외와 뼈대에 남기는 자리

| 제외 항목 | 이유 | 뼈대에 남기는 자리 |
|---|---|---|
| `position_line` 생성 (1단계) | 입력이 될 `cln_*` 테이블 스키마가 팀 미합의 (설계 공유 문서 안건 5) | `position_line` 테이블 + 샘플 SQL. `cln_balance`/`cln_deposit` 미러는 만들지 않는다 |
| 등급 판정 (1.5) · 실현손익 산출 (1.6) | 영구 `SEEDED` 판정 사유(확보 구간 부족 / 비체결 입고)를 담을 컬럼과 확보 구간 중간의 미설명 변동 대조 방식이 미정이다(§4.4) | `realized_pnl_line` 테이블과 **읽기** 경로는 만든다. `grade`는 샘플에 직접 넣는다. `position_basis` 테이블은 만들지 않는다. `SEEDED_ROWS` notice는 사유를 구분하지 않으며, 1.5단계에서 사유를 params에 실을 자리를 남긴다 |
| ETF 분해 안분 (2단계) | 구성비중 제공 형태 미합의 (안건 3·8) | 렌즈 CTE(`AggregateMapper.xml`의 `targetLine` 조각)와 `DIRECT` 경로는 완성한다. `LOOK_THROUGH` CTE는 **미확보 분기만** 담아 ETF 행을 그대로 남기고, 전개 분기(`etf_constituent` 조인 · 기타 버킷 · 잔차 흡수)를 `UNION ALL`로 붙일 자리를 남긴다 |
| 계좌 연동 · 동기화 | `collection_run` 계약·시크릿 관리 미합의 (안건 6·7) | `sync_run` 테이블을 만들지 않는다. `accounts` 뷰 행의 `last_collection`은 `CollectionStatusPort` 스텁이 `null`을 낸다. `link_state`는 `account` 테이블에서 실제로 내린다 |
| 손익성 현금흐름 (`cln_cashflow` — `DIVIDEND`·`FEE`·`TAX`) | 매매대금 배제 규칙과 `FEE`·`TAX` 원천이 팀 미합의 (안건 1) | `EarningsCashflowPort` 인터페이스 + `EmptyEarningsCashflowPort`. 빈 결과가 곧 "미확보"이므로 `CASHFLOW_UNCOVERED`가 정직하게 뜨고 항등식은 그대로 성립한다 |
| 입출금 **입력 화면·`POST` 엔드포인트** | 조회 계층이 범위다. 읽기 경로와 테이블은 만든다 | `manual_cashflow` 테이블 + 샘플 행 + `ManualCashflowMapper`(읽기). **`DEPOSIT`·`WITHDRAW`는 스텁이 아니라 실제 값이다** |
| 종목 상세 `GET /portfolio/instruments/{id}` | `position_basis` · `cln_trade` · `corporate_action`에 의존 | 만들지 않는다. 6개 뷰 엔드포인트만 노출 |
| 회원가입 · 비밀번호 재설정 | 사용자가 늘어나는 속도가 사람을 추가하는 속도와 같아 셀프서비스가 값을 하지 않는다(§12) | 사용자 행은 마이그레이션이 심는다(§C.1). `app_user` 테이블과 로그인 조회 경로는 실제로 만든다 |
| refresh 토큰 · 강제 로그아웃 | 서버가 세션을 들지 않는 선택의 대가다(§8.8) | access token 하나로 끝낸다. 만료되면 재로그인 |
| 프론트엔드 | 담당자 미정 | — |

**`LOOK_THROUGH` 스텁이 가짜가 아닌 이유.** `etf_coverage`에 행이 없으면 모든 ETF가 미확보이고, 스펙 §3.4는 그 경우 "**전개하지 않고 ETF 행을 그대로 남긴다**"고 정한다. 즉 이번 범위의 `LOOK_THROUGH`는 **스펙이 정의한 정상 경로**를 타며, 미분해 평가금액을 `CONSTITUENT_UNAVAILABLE`에 실어 사용자에게 알린다. 구현하지 않는 것은 안분 산술 하나이고, 그것이 붙을 자리는 CTE의 `UNION ALL` 한 곳이다.

## A.10 열린 판단 — `PRICE_LAG_MARKET`

| 항목 | 지금의 처리 | 뒤집는 방법 |
|---|---|---|
| 휴장일 캘린더 없이 `PRICE_LAG_MARKET`을 발화시킬 것인가 | **발화시키지 않는다** | `WeekdayMarketCalendar`를 `MarketCalendarPort` 구현으로 넣고 한계를 배너에 함께 적는다. Task 7에 한 스텝이 추가된다 |

시장별 가격 기준일은 저장하지 않고 유도한다(§7.4) — `price_as_of` = `source_as_of` 기준 직전 해당 시장 영업일. `position_line`에 컬럼을 두지 않는 이유는 평가금액이 증권사 잔고에서 오는 값이라 **증권사가 어느 날짜 종가를 썼는지 알 수 없기** 때문이다. 유도하면 "이 시장의 직전 영업일" 이상을 주장하지 않아 정직하다.

유도에는 시장 캘린더가 필요하고, 그것은 `as_of` 생성 규칙(§9.1)과 함께 1단계 산출물이다. 휴장일을 모르는 상태로 유도하면 **미국 종목에서 실제보다 최신 날짜를 주장한다** — 직전 평일이 미국 휴장일이면 그날 종가가 없는데 있다고 말한다. 정보성 배너 하나 때문에 틀린 날짜를 보이는 쪽이 안 보이는 쪽보다 나쁘므로, 이번 범위에서는 `MarketCalendarPort` 인터페이스만 두고 notice를 내리지 않는다. 1단계에서 구현체를 끼우면 살아난다.

## A.11 개발 환경 전제

**손익 · 실현손익 · 권리 계열 증권사 TR 5종이 모의투자를 지원하지 않는다.** `cln_trade` · 배당 · 실현손익의 원천에 닿는 TR들이며, 목록은 [KIS 실측 문서](../verification/kis-portfolio-assumptions.md) §4-2에 있다.

| 단계 | 개발·테스트에 필요한 것 |
|---|---|
| **이번 범위 (조회 계층)** | **없음.** 입력이 사람이 넣은 샘플 행이고 증권사를 호출하지 않는다. Docker Compose + Postgres로 끝난다 |
| 1단계 (`position_line` 생성) | 잔고 TR은 모의투자로 가능하다. 실전 계좌가 없어도 착수할 수 있다 |
| **1.5 · 1.6단계 (등급 판정 · 실현손익)** | **실전 계좌 필수.** 체결·손익·권리 TR이 모의를 지원하지 않아 모의 앱키로는 개발도 테스트도 되지 않는다 |
| 자산 변화의 배당·수수료 | **실전 계좌 필수** (권리 TR `CTRGA011R`) |

**후속 단계 착수 조건**: 1.5단계 이후를 시작하기 전에 개발용 실전 계좌와 앱키가 준비돼 있어야 한다. 계획 A는 이 제약과 무관하게 끝까지 진행할 수 있다.

샘플 데이터만으로 도는 조회 계층을 먼저 세우는 것이 이 제약과 맞물린다 — 실전 계좌 확보를 기다리지 않고 집계 엔진과 응답 계약을 완성할 수 있다.

---

# Part B — 파일 구조

책임 단위로 나눈다. 계층으로 나누지 않는다 — 함께 바뀌는 것이 함께 있어야 한다.

```
back-end/
├── build.gradle.kts · settings.gradle.kts · gradle/wrapper/
├── docker-compose.yml · Dockerfile · .env.example
├── docker/initdb/       테스트 DB 생성 스크립트
├── README.md
├── docs/decisions.md                     빌드·마이그레이션·데이터 접근·집계 위치 결정 기록
└── src
    ├── main/java/com/stockproject/portfolio/
    │   ├── PortfolioApplication.java
    │   ├── catalog/                      코드 상수. DB 아님 (§6)
    │   │   ├── AxisKey.java              enum 8개
    │   │   ├── MetricKey.java            enum 17개
    │   │   ├── Metric.java               record + Additivity·CashScope·LensSafety·MetricScope
    │   │   ├── Lens.java · LensPolicy.java
    │   │   ├── ViewKey.java · ViewSpec.java · SubBlockSpec.java
    │   │   └── Catalog.java              축·지표·뷰 테이블 + 조회 + 요청 대조
    │   ├── domain/
    │   │   ├── AssetClass · Market · CurrencyCode · AccountType · LinkState · Grade
    │   │   ├── measure/
    │   │   │   ├── Measures.java         가산 측정값만. 비율 필드 없음 (불변식 1)
    │   │   │   ├── MeasureBundle.java    securities/cash 2슬롯 + CurrencySet (불변식 2·3)
    │   │   │   ├── CurrencySet.java
    │   │   │   └── LocalMoney.java
    │   │   ├── group/
    │   │   │   ├── Aggregation.java      + weightDenominator() — TotalAssetsKrw 유일 생성처
    │   │   │   ├── TotalAssetsKrw.java   package-private 생성자
    │   │   │   ├── GroupKey.java · GroupNode.java
    │   │   │   └── Derived.java          파생 지표 계산 유일 지점
    │   ├── auth/                         인증과 스코프 (§8.8 · §3.8)
    │   │   ├── UserScope.java            record(UUID userId) — LineFilter와 다른 타입
    │   │   ├── AppUser.java · AppUserMapper.java
    │   │   ├── JwtCodec.java             발급·검증. 비밀키는 환경변수
    │   │   ├── JwtAuthenticationFilter.java · SecurityConfig.java
    │   │   ├── UserScopeArgumentResolver.java  컨트롤러가 파라미터로 받지 않게 하는 주입 지점
    │   │   ├── AccountOwnershipGuard.java      계좌 필터 소유 검사 → 403
    │   │   └── AuthController.java · dto/ LoginRequest · TokenResponse · MeResponse
    │   ├── validation/
    │   │   ├── PositionLineInvariants.java
    │   │   ├── FactInvariantViolation.java
    │   │   └── RequestValidator.java     카탈로그 대조 (§9.3)
    │   ├── query/
    │   │   ├── LineFilter.java
    │   │   ├── AccountMapper.java · SnapshotCalendarMapper.java   @Select 애노테이션
    │   │   ├── UuidTypeHandler.java · StringArrayTypeHandler.java
    │   │   ├── FactCheckMapper.java          §9.1 검사 쿼리 5개
    │   │   ├── aggregate/
    │   │   │   ├── AxisSql.java              축 → SQL 식. AxisFragment 생성
    │   │   │   ├── AxisFragment.java         매퍼에 넘기는 유일한 SQL 조각 타입
    │   │   │   ├── AggregateMapper.java      XML 매퍼 인터페이스
    │   │   │   ├── AggregateQueryRepository.java  트리 조립·정렬
    │   │   │   └── EtfCoverageMapper.java · UndecomposedEtf.java
    │   │   ├── SnapshotCalendarRepository.java   as_of 목록·직전·기간 경계
    │   │   ├── SnapshotFactsMapper.java      배너 시각·이월 계좌·적용 환율·시장 배지
    │   │   ├── AccountRepository.java
    │   │   ├── RealizedPnlMapper.java
    │   │   ├── ManualCashflowRepository.java      넣은 돈 — 백엔드 소유, 실제 값
    │   │   ├── EarningsCashflowPort.java · EmptyEarningsCashflowPort.java
    │   │   ├── EarningsCashflowType.java          DIVIDEND·FEE·TAX — 입출금이 없다(§9.1 타입 강제)
    │   │   └── CollectionStatusPort.java · NoCollectionStatusPort.java
    │   ├── view/
    │   │   ├── BannerAsOf.java               모든 화면이 같은 "언제 기준"을 쓴다
    │   │   ├── CatalogService.java           카탈로그 + 그 사용자의 계좌
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
        ├── mapper/           AggregateMapper.xml
        ├── db/migration/     V1__initial_schema.sql      백엔드 소유 5개 테이블
        ├── db/external/      V2__instrument_mirror.sql · V3__etf_coverage_mirror.sql
        │                     데이터팀 소유 미러 — local·test 전용. 번호는 db/migration과 한 순열
        └── db/sample/        sample_portfolio.sql
    └── test/java/com/stockproject/portfolio/
        ├── ArchitectureRulesTest.java     불변식 1·5·BigDecimal·계층 접근
        ├── MigrationLintTest.java         비율 컬럼 금지 (§9.2)
        ├── UserScopeIsolationTest.java    사용자별 합계가 갈리는지
        ├── catalog/CatalogInvariantTest.java
        ├── domain/…                       가산성·총합 보존·분모·통화 단위 테스트
        ├── auth/…                         토큰 발급·검증·매퍼 시그니처 (불변식 5)
        ├── query/…                        portfolio_test DB 저장소 테스트
        └── api/SixViewGoldenTest.java     도달점 검증
    └── test/resources/golden/*.json
```

---

# Part C — 샘플 데이터와 기대 응답 (도달점의 정의)

`db/sample/sample_portfolio.sql`이 만드는 세계다. 태스크 12의 골든 테스트가 이 표를 그대로 검증한다.

**§C.5~C.11의 기대 응답은 전부 `yhr` 토큰으로 부른 것이다.** 다른 사용자의 데이터가 함께 들어 있어도 이 수치는 변하지 않아야 하고, 변하면 스코프가 샌 것이다(§C.12).

## C.1 사용자 4명과 계좌 7개

**`app_user`** — 마이그레이션이 심는다(§A.9). 샘플 SQL은 `test_empty`만 더하고 나머지는 건드리지 않는다.

| user_id 끝자리 | email | display_name | 출처 | 노리는 것 |
|---|---|---|---|---|
| `…0001` | yhr@a.com | yhr | `V1__initial_schema.sql` | 주 사용자. §C.5~C.11의 골든 값 |
| `…0002` | jdh@a.com | jdh | `V1__initial_schema.sql` | 겹치는 종목을 보유한 두 번째 사용자 |
| `…0003` | hhj@a.com | hhj | `V1__initial_schema.sql` | `as_of`가 하나뿐인 사용자 |
| `…0004` | test_empty@a.com | test_empty | 샘플 SQL | 계좌 0개 → `NO_ACCOUNTS` |

UUID는 `40000000-0000-0000-0000-00000000000N` 꼴. `password_hash`는 BCrypt이며 셋 다 로컬 개발용 같은 비밀번호다 — 운영 전 교체 대상임을 README에 적는다.

**`account`**

| account_id 끝자리 | 소유자 | broker | label | type | source | link_state |
|---|---|---|---|---|---|---|
| `…0001` | yhr | 한국투자증권 | 한국투자 위탁 | GENERAL | KIS | CONNECTED |
| `…0002` | yhr | 삼성증권 | 삼성증권 | GENERAL | CODEF | CONNECTED |
| `…0003` | yhr | 한국투자증권 | 한국투자 IRP | PENSION | KIS | CONNECTED |
| `…0004` | yhr | 미래에셋증권 | 미래에셋 연금 | PENSION | CODEF | CONNECTED |
| `…0005` | jdh | 키움증권 | 키움 위탁 | GENERAL | CODEF | CONNECTED |
| `…0006` | jdh | 미래에셋증권 | 미래에셋 IRP | PENSION | CODEF | CONNECTED |
| `…0007` | hhj | 한국투자증권 | 한국투자 위탁 | GENERAL | KIS | CONNECTED |

UUID는 `20000000-0000-0000-0000-00000000000N` 꼴.

**`test_empty`가 픽스처인 이유.** 팀원 셋은 실제 계정이라 배치가 붙어도 대체되지 않고 각자의 실계좌가 여기 매달린다. 계좌 없는 사용자는 사람이 아니라 빈 상태를 재현하기 위한 장치이므로, 마이그레이션이 아니라 샘플이 소유한다. 샘플의 `TRUNCATE` 대상에 `app_user`가 없는 것도 같은 이유다 — 픽스처가 계정을 지웠다 다시 만들면 개발 DB의 비밀번호 해시가 매번 초기화된다.

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

## C.3 `position_line` — `as_of = 2026-07-27`

USD 라인의 `fx_rate = 1400.000000`. **종목 가격은 사용자 사이에 같다** — 같은 세계의 같은 날 종가이므로 삼성전자는 누구에게나 07-27에 71,200원, 07-24에 65,200원이다.

### yhr — 10행

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

`source_as_of` — 이월이 아닌 라인은 `2026-07-27T15:30:00+09:00`, 미래에셋 연금 2행은 `2026-07-24T15:30:00+09:00`. `is_final = false`. **총자산 58,000,000.**

### jdh — 4행

| 계좌 | 종목 | qty | cost_local | mv_local | cost_krw | mv_krw | fx_as_of | 이월 |
|---|---|---|---|---|---|---|---|---|
| 키움 위탁 | 005930 | 100 | 6,500,000 | 7,120,000 | 6,500,000 | 7,120,000 | 07-27 | – |
| 키움 위탁 | CASH-KRW | 880,000 | 880,000 | 880,000 | 880,000 | 880,000 | 07-27 | – |
| 미래에셋 IRP | 133690 | 50 | 5,000,000 | 5,500,000 | 5,000,000 | 5,500,000 | 07-27 | – |
| 미래에셋 IRP | CASH-KRW | 500,000 | 500,000 | 500,000 | 500,000 | 500,000 | 07-27 | – |

`source_as_of`는 `2026-07-27T15:30:00+09:00`, `is_final = false`. **총자산 14,000,000.**

**삼성전자와 TIGER를 yhr과 겹쳐 보유한다.** 스코프가 새면 종목별 뷰에서 삼성전자 수량이 200이 아니라 300이 되고 평단이 흔들린다 — 총액만 보는 검사를 통과하고도 잡히는 자리다.

### hhj — 2행

| 계좌 | 종목 | qty | cost_local | mv_local | cost_krw | mv_krw | fx_as_of | 이월 |
|---|---|---|---|---|---|---|---|---|
| 한국투자 위탁 | AAPL | 5 | 1,000.00 | 1,100.00 | 1,400,000 | 1,540,000 | 07-27 | – |
| 한국투자 위탁 | CASH-KRW | 460,000 | 460,000 | 460,000 | 460,000 | 460,000 | 07-27 | – |

`source_as_of`는 `2026-07-27T15:30:00+09:00`, `is_final = false`. **총자산 2,000,000.**

### `as_of = 2026-07-24` 스냅샷 — yhr 10행 + jdh 4행

각 사용자의 07-27 라인을 복제하고 **삼성전자 `mv_local`·`mv_krw`만 단가 65,200원 기준으로** 바꾼다 — yhr 13,040,000(200주) · jdh 6,520,000(100주). 이월 플래그는 전부 `false`, `source_as_of`는 `2026-07-24T15:30:00+09:00`, `is_final = true`.

→ yhr 총자산 56,800,000 · jdh 총자산 13,400,000.

**hhj는 이 스냅샷을 갖지 않는다.** 연동을 07-27에 시작한 사용자이고, 이것이 `as_of` 캘린더가 스코프 안에 있는지(§3.8)를 검사하는 자리다 — 캘린더가 전역이면 hhj의 자산 변화 뷰가 07-24를 기초로 잡아 남의 세계에서 기간 손익을 계산한다.

전체 행 수는 07-27 16행 + 07-24 14행 = **30행**이다.

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
| **사용자 스코프** | 전역 합계 74,000,000 vs yhr 58,000,000 |
| **종목 겹침** | 005930 · 133690을 yhr·jdh가 함께 보유 |
| **`as_of` 캘린더 스코프** | hhj는 07-27만 |
| **계좌 없는 사용자** | test_empty → `NO_ACCOUNTS` |

## C.4 `realized_pnl_line` — 4행 · `manual_cashflow` — 2행

| trade_id | 소유자 | 계좌 | 종목 | sold_at | qty | sell_krw | cost_basis_krw | fee_tax | pnl_krw | grade |
|---|---|---|---|---|---|---|---|---|---|---|
| `T-0001` | yhr | 한국투자 위탁 | 005930 | 2026-03-02 | 3 | 400,000 | 320,000 | 1,000 | 79,000 | SEEDED |
| `T-0002` | yhr | 한국투자 위탁 | 005930 | 2026-05-12 | 5 | 700,000 | 500,000 | 2,000 | 198,000 | VERIFIED |
| `T-0003` | yhr | 삼성증권 | 035420 | 2026-02-18 | 10 | 2,000,000 | 2,300,000 | 5,000 | −305,000 | VERIFIED |
| `T-1001` | jdh | 키움 위탁 | 005930 | 2026-06-19 | 2 | 150,000 | 130,000 | 1,000 | 19,000 | VERIFIED |

`*_local`은 KRW 종목이라 `*_krw`와 같은 값.

`T-1001`도 **005930의 매도**다. 스코프가 새면 yhr의 실현손익 뷰에서 삼성전자 노드의 `trade_count`가 2가 아니라 3이 되고 `last_sold_at`이 05-12에서 06-19로 밀린다(§C.10).

**`manual_cashflow`** — 사용자 입력 입출금(§A.7.4)

| id | 소유자 | 계좌 | type | amount | currency | occurred_on | memo |
|---|---|---|---|---|---|---|---|
| `30000000-…-0001` | yhr | 한국투자 위탁 | `DEPOSIT` | 2,000,000 | KRW | 2026-07-27 | 월 적립 |
| `30000000-…-0002` | jdh | 키움 위탁 | `DEPOSIT` | 500,000 | KRW | 2026-07-27 | 월 적립 |

날짜가 `(기초 as_of 2026-07-24, 기말 as_of 2026-07-27]` 안에 들어와야 항등식이 성립한다(§A.6.3).
yhr의 한 행이 자산 변화 뷰의 존재 이유를 샘플에서 재현한다 — **자산은 120만원 늘었지만 200만원을 넣고 80만원을 잃은** 상황이다(§2.9). jdh는 같은 날짜에 반대 부호가 나와(Δ 600,000 − 넣은 돈 500,000 = +100,000) 두 사용자의 이야기가 갈린다.

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
               "daily_change_pct": 2.1, "account_count": 4, "instrument_count": 6 },
    "rows": [],
    "mini_chart": { "group_by": ["market"], "lens": "DIRECT",
      "rows": [ { "key": "KR", "label": "국내", "market_value_krw": 46800000, "weight_pct": 80.7 },
                { "key": "US", "label": "미국", "market_value_krw": 11200000, "weight_pct": 19.3,
                  "currency": "USD", "market_value_local": 8000.00 } ] } },
  "notices": [
    { "code": "FX_APPLIED", "severity": "info", "message": "USD/KRW 1,400.00 적용 · 기준 2026-07-24",
      "params": { "rates": [ { "pair": "USD/KRW", "rate": 1400.0, "fx_as_of": "2026-07-24" } ],
                  "oldest_fx_as_of": "2026-07-24" } },
    { "code": "STALE_ACCOUNTS", "severity": "warn", "message": "1개 계좌가 07-24 기준입니다",
      "params": { "count": 1, "oldest": "2026-07-24" } } ] }
```

미니차트 검산 — `KR = 14,240,000 + 9,000,000 + 8,000,000 + 11,000,000 + 2,560,000 + 1,000,000 + 1,000,000 = 46,800,000`,
`US = 6,160,000 + 4,900,000 + 140,000 = 11,200,000`, 합 58,000,000, 비중 80.7 / 19.3.

**`US` 행에 현지 통화가 붙는다** — 시장=US 묶음은 정의상 단일 통화다. `market_value_local = 4,400.00 + 3,500.00 + 100.00 = 8,000.00`.
`KR` 행은 단일 통화지만 `KRW`라서 병기하지 않는다.

## C.6 기대 응답 — `GET /portfolio/views/allocation?axis=sector&lens=DIRECT`

`total`은 §C.5의 `total`에서 `daily_change_*`를 뺀 것과 같다(일간 변화는 요약 전용 지표).

| 순서 | key | label | market_value_krw | cost_amount_krw | unrealized_pnl_krw | unrealized_pnl_pct | weight_pct | instrument_count |
|---|---|---|---|---|---|---|---|---|
| 1 | `반도체` | 반도체 | 23,240,000 | 20,000,000 | 3,240,000 | 16.2 | 40.1 | 2 |
| 2 | `소프트웨어` | 소프트웨어 | 12,900,000 | 13,200,000 | −300,000 | −2.3 | 22.2 | 2 |
| 3 | `UNCLASSIFIED` | 미분류 | 11,000,000 | 10,000,000 | 1,000,000 | 10.0 | 19.0 | 1 |
| 4 | `IT서비스` | IT서비스 | 6,160,000 | 5,600,000 | 560,000 | 10.0 | 10.6 | 1 |
| 5 | `CASH` | 현금 | 4,700,000 | **null** | **null** | **null** | 8.1 | 0 |

분류 축의 폴백은 `key`가 `UNCLASSIFIED`·`CASH`이고 `label`이 한국어다(§A.4.1).

`Σ market_value_krw = 58,000,000 = total.total_assets_krw` ✔ · `Σ weight_pct = 100.0` ✔ · `Σ cost = 48,800,000` ✔

**`IT서비스` 행에만 현지 통화가 붙는다** — AAPL 단독이라 우연히 단일 통화다. 판정이 축 이름이 아니라 런타임 통화 집합이라 잡힌다(불변식 3).

```json
{ "key": "IT서비스", "label": "IT서비스", "currency": "USD",
  "market_value_krw": 6160000, "market_value_local": 4400.00,
  "cost_amount_krw": 5600000, "cost_amount_local": 4000.00,
  "unrealized_pnl_krw": 560000, "unrealized_pnl_pct": 10.0,
  "weight_pct": 10.6, "instrument_count": 1 }
```

나머지 4행은 통화가 섞였거나(`소프트웨어`·`현금`) 단일 `KRW`라(`반도체`·`미분류`) 병기하지 않는다.

## C.7 기대 응답 — `GET /portfolio/views/allocation?axis=sector&lens=LOOK_THROUGH`

`total`은 §C.6과 **동일하다**(총합 보존). `rows[]`에서 `cost_amount_krw` · `unrealized_pnl_krw` · `unrealized_pnl_pct` **세 키가 사라진다**(`null`이 아니라 부재).

추가 notices:

```json
{ "code": "CONSTITUENT_UNAVAILABLE", "severity": "warn",
  "message": "1개 ETF는 구성종목 데이터가 없어 분해하지 않았습니다",
  "params": { "count": 1, "undecomposed_krw": 11000000, "keys": ["133690"] } },
{ "code": "LENS_METRICS_OMITTED", "severity": "info",
  "message": "구성종목 기준 보기에서는 매입금액·평가손익을 행에 표시할 수 없습니다",
  "params": { "metrics": ["cost_amount_krw", "unrealized_pnl_krw", "unrealized_pnl_pct"] } }
```

`CONSTITUENT_AS_OF`는 전개된 ETF가 0이라 생략한다.

**`keys`는 종목 심볼이다.** 종목 축(`positions` · `allocation?axis=instrument`)의 행 `key`와 같은 값이라 화면이 어느 행이 분해되지 않았는지 짚을 수 있다. 섹터·시장처럼 여러 종목이 한 행에 뭉치는 축에서는 행이 특정되지 않으므로 경고 줄로만 쓴다.

**금액은 `message`에 넣지 않는다.** 모바일 경고 줄에서 두 줄이 되어 읽히지 않는다. 화면이 필요하면 `params.undecomposed_krw`에서 꺼낸다.

`IT서비스` 행의 `currency` · `market_value_local`은 남는다 — 통화 병기는 지표가 아니라 표시 규칙이고 평가금액은 `ROW_AND_TOTAL`이다. 사라지는 것은 `cost_amount_local`뿐이다(원가 계열이 행에서 빠지므로).

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
| 1.1 | `…0001` / 한국투자 위탁 | 31,960,000 | 2,560,000 | 25,600,000 | 3,800,000 | 14.8 | 55.1 | `link_state: CONNECTED` · `last_collection: null` · `last_synced_at: null` · `source_as_of: 2026-07-27` · `is_carried_forward: false` |
| 1.2 | `…0002` / 삼성증권 | 9,000,000 | 1,000,000 | 9,000,000 | −1,000,000 | −11.1 | 15.5 | 동일 |
| 2 | `PENSION` / 연금 | 17,040,000 | 1,140,000 | 14,200,000 | 1,700,000 | 12.0 | 29.4 | – |
| 2.1 | `…0003` / 한국투자 IRP | 12,000,000 | 1,000,000 | 10,000,000 | 1,000,000 | 10.0 | 20.7 | 동일 |
| 2.2 | `…0004` / 미래에셋 연금 | 5,040,000 | 140,000 | 4,200,000 | 700,000 | 16.7 | 8.7 | 동일 + `currency: USD` · **`source_as_of: 2026-07-24` · `is_carried_forward: true`** |

`Σ 최상위 mv_krw = 58,000,000` ✔ · 자식 합 = 부모 ✔ · `Σ 최상위 weight_pct = 100.0` ✔

**`미래에셋 연금` 행에만 현지 통화가 붙는다** — MSFT + USD 예수금뿐이라 우연히 단일 통화다.
`market_value_local = 3,500.00 + 100.00 = 3,600.00`, `cost_amount_local = 3,000.00`(CASH 제외).
나머지 계좌와 두 소계는 통화가 섞였거나 단일 `KRW`라 병기하지 않는다.

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
    "deposited": 2000000, "earned": -800000,
    "account_included": 0, "account_excluded": 0,
    "breakdown": [ { "type": "DEPOSIT", "amount": 2000000 },
                   { "type": "INVESTMENT_PNL", "amount": -800000 } ],
    "investment_pnl": { "total": -800000, "realized": null,
                        "unrealized_change": null, "split_available": false } },
  "notices": [
    { "code": "CASHFLOW_UNCOVERED", "severity": "warn",
      "message": "배당·수수료 내역이 확보되지 않아 투자손익에 섞여 있을 수 있어요",
      "params": { "types": ["DIVIDEND", "FEE", "TAX"], "account_count": 4 } },
    { "code": "PERIOD_TRUNCATED", "severity": "info",
      "message": "2026-07-24부터 계산했습니다", "params": { "actual_from": "2026-07-24" } },
    { "code": "BOUNDARY_CARRIED_FORWARD", "severity": "warn",
      "message": "기간 경계 시점에 1개 계좌가 이월값입니다",
      "params": { "count": 1, "boundary": "2026-07-27" } } ] }
```

**검산** — `2026-07-01` 직전 스냅샷이 없어 가장 이른 `2026-07-24`를 기초로 대체하고 `PERIOD_TRUNCATED`를 붙인다. 현금흐름 구간도 요청 기간이 아니라 `(2026-07-24, 2026-07-27]`로 잘린다.

```
Δ총자산       = 58,000,000 − 56,800,000 =  1,200,000
넣은 돈       = manual_cashflow DEPOSIT  =  2,000,000   (사용자 입력, 실제 값)
배당·수수료   = 미확보                   =          0   (cln_cashflow 스텁)
투자손익      = 1,200,000 − 2,000,000    =   −800,000
번 돈         = −800,000 + 0 − 0         =   −800,000
항등식        56,800,000 + 2,000,000 + (−800,000) = 58,000,000 ✔
```

**이 응답이 뷰의 존재 이유를 보여준다** — 자산은 늘었는데 손실이다. 다른 어떤 뷰로도 드러나지 않는 상황이며(§2.9), 샘플 한 행으로 재현된다.

> 자산이 120만원 늘었지만 200만원을 넣고 80만원을 잃었어요

값이 0인 `WITHDRAW`·`DIVIDEND`·`FEE_TAX`는 `breakdown`에서 숨긴다. `split_available = false`는 거래 원장 산출이 범위 밖이기 때문이다 — `total`은 항상 정확하다.

## C.12 사용자 격리 — 같은 요청, 다른 토큰

같은 URL을 네 토큰으로 부른 결과다. 스코프가 새면 이 표가 깨진다.

```bash
TOKEN=$(curl -s localhost:8080/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"jdh@a.com","password":"…"}' | jq -r .access_token)
curl -s localhost:8080/portfolio/views/summary -H "Authorization: Bearer $TOKEN" | jq .
```

**`GET /portfolio/views/summary`**

| 지표 | yhr | jdh | hhj | test_empty |
|---|---|---|---|---|
| `total_assets_krw` | 58,000,000 | 14,000,000 | 2,000,000 | — |
| `securities_value_krw` | 53,300,000 | 12,620,000 | 1,540,000 | — |
| `deposit_krw` | 4,700,000 | 1,380,000 | 460,000 | — |
| `cost_amount_krw` | 48,800,000 | 11,500,000 | 1,400,000 | — |
| `unrealized_pnl_krw` | 4,500,000 | 1,120,000 | 140,000 | — |
| `unrealized_pnl_pct` | 9.2 | 9.7 | 10.0 | — |
| `cash_ratio_pct` | 8.1 | 9.9 | 23.0 | — |
| `daily_change_krw` | 1,200,000 | 600,000 | **null** | — |
| `daily_change_pct` | 2.1 | 4.5 | **null** | — |
| `account_count` | 4 | 2 | 1 | — |
| `instrument_count` | 6 | 2 | 1 | — |
| `empty_reason` | null | null | null | **`NO_ACCOUNTS`** |

hhj의 일간 변화가 `null`인 것은 직전 `as_of`가 없기 때문이다. 전역 캘린더를 쓰면 07-24가 잡히고, 그 날짜에 hhj의 라인이 없어 `0`이 되거나 남의 총자산이 들어온다.

**나머지 뷰**

| 요청 | yhr | jdh | hhj |
|---|---|---|---|
| `positions?lens=DIRECT` — 005930 행 | 200주 · 평단 60,000 | 100주 · 평단 65,000 | 행 없음 |
| `allocation?axis=sector` — `반도체` | 23,240,000 | 7,120,000 | 행 없음 |
| `accounts` — 최상위 노드 | 일반 · 연금 | 일반 · 연금 | 일반 |
| `realized-pnl?period=THIS_YEAR` | total −28,000 · 2행 | total 19,000 · 1행 | `NO_TRADES_IN_PERIOD` |
| `asset-change` 07-01~07-31 | 56,800,000 → 58,000,000 · 넣은 돈 2,000,000 · 번 돈 −800,000 | 13,400,000 → 14,000,000 · 넣은 돈 500,000 · 번 돈 +100,000 | 2,000,000 → 2,000,000 · `breakdown` 빈 배열 |

**스코프가 새면 나타나는 값** — 대조용이다.

| 자리 | 정상(yhr) | 전역 |
|---|---|---|
| 요약 총자산 | 58,000,000 | 74,000,000 |
| 종목별 005930 수량 | 200 | 300 |
| 섹터 `반도체` | 23,240,000 | 30,360,000 |
| 실현손익 005930 `trade_count` · `last_sold_at` | 2 · 2026-05-12 | 3 · 2026-06-19 |
| 계좌별 계좌 수 | 4 | 7 |

**소유하지 않은 계좌를 필터로 넣으면 `403`이다.** yhr 토큰으로 `?account=20000000-…-0005`(jdh의 키움 위탁)를 부르면 빈 결과가 아니라 `FORBIDDEN_ACCOUNT`다(§A.6.4).


---

# Part D — 태스크

12개 태스크. 각 태스크는 독립적으로 테스트 가능한 산출물로 끝나고 1커밋을 만든다.
의존: 1 → 2 → 3 → 4 → 5 → 6 → 7 → {8, 9, 10} → 11. 8·9·10은 서로 독립이라 병렬 가능하다.

---

### Task 1: 스캐폴딩 · Docker Compose · 마이그레이션 · 샘플 데이터

**Files:**
- Create: `back-end/settings.gradle.kts` · `back-end/build.gradle.kts` · `back-end/gradle/wrapper/*`
- Create: `back-end/docker-compose.yml` · `back-end/Dockerfile` · `back-end/.env.example`
- Create: `back-end/src/main/java/com/stockproject/portfolio/PortfolioApplication.java`
- Create: `back-end/src/main/resources/application.yaml` · `application-local.yaml`
- Create: `back-end/src/main/resources/db/migration/V1__initial_schema.sql`
- Create: `back-end/src/main/resources/db/external/V2__instrument_mirror.sql`
- Create: `back-end/src/main/resources/db/sample/sample_portfolio.sql`
- Test: `back-end/src/test/java/com/stockproject/portfolio/MigrationLintTest.java`
- Test: `back-end/src/test/java/com/stockproject/portfolio/SchemaSmokeTest.java`
- Test: `back-end/src/test/java/com/stockproject/portfolio/UserScopeIsolationTest.java`
- Modify: `back-end/README.md` · `back-end/.gitignore` (Gradle·빌드 산출물 추가)

**Interfaces:**
- Produces: Flyway 마이그레이션이 만드는 테이블 5개(`app_user`·`account`·`position_line`·`realized_pnl_line`·`manual_cashflow`)와 로컬 전용 미러 `instrument`. 이후 모든 태스크의 저장소가 이 스키마를 읽는다.
- Produces: 소유권 축 `account.user_id`. 이후 모든 조회가 이 컬럼을 통해 스코프된다(§A.3 불변식 5).

**완료 조건**
1. `./gradlew build`가 통과한다.
2. `docker compose up -d db` 후 `./gradlew bootRun --args='--spring.profiles.active=local'`로 앱이 뜨고 Flyway가 마이그레이션 2개를 적용한다.
3. `psql`로 `sample_portfolio.sql`을 실행하면 `position_line` 30행(07-27 16행 · 07-24 14행), `realized_pnl_line` 4행, `manual_cashflow` 2행, `account` 7행, `app_user` 4행, `instrument` 8행이 들어간다.
4. **사용자별 총자산이 58,000,000 / 14,000,000 / 2,000,000 / 0으로 갈린다**(§C.12). 전역 합계는 74,000,000이다.
5. `MigrationLintTest`가 통과한다 — 마이그레이션에 비율 컬럼이 없다.
6. `db/external`은 `local`·`test` 프로필에서만 적용되고 기본(운영) 프로필에서는 적용되지 않는다.
7. 마이그레이션 번호가 두 폴더를 통틀어 하나의 순열이다(§A.2.5). 이후 태스크가 파일을 더할 때는 폴더와 무관하게 그때의 다음 번호를 쓴다.

**검증 방법**
```bash
cd back-end
docker compose up -d db          # portfolio · portfolio_test 두 DB가 함께 뜬다
./gradlew test --tests '*MigrationLintTest' --tests '*SchemaSmokeTest' \
               --tests '*UserScopeIsolationTest'
docker compose exec -T db psql -U portfolio -d portfolio -f /sample/sample_portfolio.sql
docker compose exec -T db psql -U portfolio -d portfolio -c \
  "SELECT as_of, count(*) FROM position_line GROUP BY 1 ORDER BY 1;"
# 기대: 2026-07-24 | 14 / 2026-07-27 | 16
docker compose exec -T db psql -U portfolio -d portfolio -c \
  "SELECT u.display_name, coalesce(sum(pl.market_value_krw), 0) AS total
     FROM app_user u
     LEFT JOIN account a ON a.user_id = u.user_id
     LEFT JOIN position_line pl ON pl.account_id = a.account_id AND pl.as_of = '2026-07-27'
    GROUP BY u.display_name ORDER BY total DESC;"
# 기대: yhr | 58000000 / jdh | 14000000 / hhj | 2000000 / test_empty | 0
docker compose exec -T db psql -U portfolio -d portfolio -c \
  "SELECT u.display_name, m.type, m.amount FROM manual_cashflow m
     JOIN account a ON a.account_id = m.account_id
     JOIN app_user u ON u.user_id = a.user_id ORDER BY 1;"
# 기대: jdh | DEPOSIT | 500000 / yhr | DEPOSIT | 2000000
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
    implementation("org.mybatis.spring.boot:mybatis-spring-boot-starter:3.0.4")
    implementation("org.springframework.boot:spring-boot-starter-validation")
    implementation("org.flywaydb:flyway-core")
    implementation("org.flywaydb:flyway-database-postgresql")
    runtimeOnly("org.postgresql:postgresql")

    testImplementation("org.springframework.boot:spring-boot-starter-test")
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
    # currentSchema가 참조 테이블(instrument) 해석을 정한다. instrument는 데이터팀 소유다.
    url: ${DB_URL:jdbc:postgresql://localhost:5432/portfolio?currentSchema=public}
    username: ${DB_USER:portfolio}
    password: ${DB_PASSWORD:portfolio}
  flyway:
    # 백엔드 소유 테이블만. 데이터팀 소유 테이블 미러(db/external)는 운영에서 적용하지 않는다.
    locations: classpath:db/migration
  jackson:
    property-naming-strategy: SNAKE_CASE
    default-property-inclusion: always
    serialization:
      write-dates-as-timestamps: false
mybatis:
  mapper-locations: classpath:mapper/*.xml
  configuration:
    map-underscore-to-camel-case: true
server:
  port: 8080
portfolio:
  zone: Asia/Seoul
```

`application-local.yaml` — 데이터팀 소유 테이블 미러를 함께 적용:
```yaml
spring:
  flyway:
    # 데이터팀 소유 테이블 미러를 함께 적용한다 — 로컬 전용
    locations: classpath:db/migration,classpath:db/external
```

**번호는 두 폴더를 통틀어 하나의 순열이다.** 로컬·테스트는 두 위치를 함께 적용하고 Flyway는 이력을 한 테이블에 기록하므로, 폴더마다 번호대를 예약하면 낮은 번호가 뒤늦게 나타나 순서 검증에 걸린다. 미러 파일도 백엔드가 쓰는 것이라 번호를 두고 다툴 상대가 없으니 예약할 이유도 없다. 운영은 `db/migration`만 적용해 미러 번호가 비는데, **비는 것은 순서 위반이 아니라** 그대로 성립한다.

- [ ] **Step 3: 마이그레이션 SQL 작성**

백엔드 소유 테이블 다섯을 한 파일에 담는다. 처음 만드는 스키마이므로 중간 단계가 없다 — `account.user_id`는 컬럼 정의에 `NOT NULL REFERENCES` 한 줄로 들어간다.

`V1__initial_schema.sql`:
```sql
-- 백엔드 소유 테이블. 소유 경계는 설계 스펙 §11.2 — 데이터팀 소유 테이블은 여기서 만들지 않는다.
--
-- 마이그레이션 번호는 db/migration 과 db/external 을 통틀어 하나의 순열이다.
-- 새 파일은 폴더와 무관하게 그때의 다음 번호를 쓴다.

-- 사용자. 스코프의 기준이며 인증 토큰의 sub가 이 id다 — 설계 스펙 §3.8 · §8.8
CREATE TABLE app_user (
    id            uuid PRIMARY KEY,
    email         text        NOT NULL UNIQUE,
    password_hash text        NOT NULL,
    display_name  text        NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE app_user IS
  '사용자. 행은 이 마이그레이션이 심고 회원가입 경로를 두지 않는다 — 설계 스펙 §5.1 · §12';
COMMENT ON COLUMN app_user.password_hash IS
  'BCrypt 해시만 저장한다. 원문은 로그·응답 어디에도 남기지 않는다 — 설계 스펙 §8.8';

-- 비밀번호 해시는 로컬 개발용 값이다. 운영 배포 전에 교체한다.
INSERT INTO app_user (id, email, password_hash, display_name) VALUES
 ('40000000-0000-0000-0000-000000000001','yhr@a.com',
   '$2y$10$JJQvq3uLIY63DiNMRghXPeqrhqzfEPZZHjHTT3PXqCzyK6XY7YK8G','yhr'),
 ('40000000-0000-0000-0000-000000000002','jdh@a.com',
   '$2y$10$3G5stjp8OaLSEjyPiRpVh.VFOCyEMhSCClFc/zbf2W2wmIcETVOwO','jdh'),
 ('40000000-0000-0000-0000-000000000003','hhj@a.com',
   '$2y$10$uvxd.nOL0RT7hOgHKaxO4e5oWVWUSL7iiIZTpVbHvPA3j3l5BBUlm','hhj');

-- 계좌. user_id가 소유권 축이며, 보유 스냅샷·실현손익·입출금은 계좌를 통해
-- 소유자가 결정된다 — 설계 스펙 §3.8
CREATE TABLE account (
    account_id     uuid PRIMARY KEY,
    user_id        uuid NOT NULL REFERENCES app_user (id),
    account_ref    text NOT NULL UNIQUE,
    broker         text NOT NULL,
    label          text NOT NULL,
    account_type   text NOT NULL CHECK (account_type IN ('GENERAL', 'PENSION')),
    source         text NOT NULL CHECK (source IN ('KIS', 'CODEF')),
    credential_ref text,
    link_state     text NOT NULL CHECK (link_state IN
                     ('CONNECTING', 'CONNECTED', 'REAUTH_REQUIRED', 'DISCONNECTED')),
    last_synced_at timestamptz
);

CREATE INDEX idx_account_user ON account (user_id);

COMMENT ON COLUMN account.user_id IS
  '소유자. 생성 후 바뀌지 않는다 — 계좌 소유자 이전을 지원하지 않는다. 설계 스펙 §9.1 · §12';
COMMENT ON COLUMN account.account_ref IS
  '데이터팀에 넘기는 불투명 문자열. 기관코드+계좌번호 해시라 재연동해도 같은 값이다 — 설계 스펙 §7.1 · §11.2';
COMMENT ON COLUMN account.credential_ref IS
  '시크릿 매니저 키만 저장한다. 자격증명 값 자체를 저장하지 않는다 — 설계 스펙 §5.1';
COMMENT ON COLUMN account.label IS
  '표시명. broker와 다르다 — 같은 기관에 위탁·IRP가 함께 있다';

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
  '보유 스냅샷. 그레인 (as_of, account_id, instrument_id). 비율(수익률·비중) 컬럼을 두지 않는다 — 설계 스펙 §1.5 · §9.2';
COMMENT ON COLUMN position_line.cost_amount_local IS
  '잔고 평단 기준(cln_balance.avg_price × quantity). position_basis를 참조하지 않는다 — 설계 스펙 §4.1';
COMMENT ON COLUMN position_line.instrument_id IS
  '데이터팀 소유 instrument 참조. 배포 순서를 묶지 않기 위해 FK를 걸지 않는다';

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
  '매도 체결 1건 = 1행. trade_id upsert로만 생성한다(insert-only 금지) — 설계 스펙 §9.1';
COMMENT ON COLUMN realized_pnl_line.grade IS
  '산출 시점 position_basis 등급의 스냅샷. 이후 갱신하지 않는다. MIXED는 응답 조립 시에만 생기며 저장하지 않는다 — 설계 스펙 §4.3 · §8.4';

-- 사용자 입력 입출금. 증권사 API가 입출금 이력을 열어주지 않는 경우가 있어
-- DEPOSIT·WITHDRAW는 원천이 아니라 사용자 입력을 기본 경로로 둔다 — 설계 스펙 §4.6 · §5.1
CREATE TABLE manual_cashflow (
    id           uuid PRIMARY KEY,
    account_id   uuid           NOT NULL REFERENCES account (account_id),
    type         text           NOT NULL CHECK (type IN ('DEPOSIT', 'WITHDRAW')),
    amount       numeric(20, 0) NOT NULL CHECK (amount > 0),
    currency     text           NOT NULL CHECK (currency IN ('KRW', 'USD')),
    occurred_on  date           NOT NULL,
    memo         text
);

CREATE INDEX idx_manual_cashflow_occurred_on ON manual_cashflow (occurred_on);
CREATE INDEX idx_manual_cashflow_account_occurred_on ON manual_cashflow (account_id, occurred_on);

COMMENT ON TABLE manual_cashflow IS
  '자산 변화 뷰의 "넣은 돈"의 유일한 출처. cln_cashflow에는 DEPOSIT·WITHDRAW가 오지 않는다 — 설계 스펙 §9.1';
```

`fx_rate`·`fx_as_of`를 `NOT NULL`로 둔 것이 §9.1의 "`market_value_krw`가 있으면 `fx_rate`·`fx_as_of` 필수"를 스키마로 표현한 것이다. 세 컬럼 모두 `NOT NULL`이므로 규칙이 구조적으로 성립한다.

`manual_cashflow.amount`를 양수로 제약하고 방향은 `type`이 정한다 — 부호와 유형이 어긋나 이중 부정이 생기는 것을 막는다.

`app_user` 시드가 마이그레이션에 있는 이유는 회원가입 경로를 두지 않기 때문이다(§12). 사용자가 늘어나는 속도가 사람을 추가하는 속도와 같아 셀프서비스가 값을 하지 않는다.

`V2__instrument_mirror.sql` (`db/external/`):
```sql
-- 데이터팀 소유 테이블의 로컬·테스트 전용 미러.
-- 소유 경계는 설계 스펙 §11.2. 운영 프로필(spring.flyway.locations=classpath:db/migration)은
-- 이 파일을 적용하지 않는다.
--
-- 번호는 db/migration 과 통틀어 하나의 순열이다. 운영에서는 이 번호가 비지만,
-- 번호가 비는 것은 문제가 되지 않는다 — 낮은 번호가 뒤늦게 오는 것만 순서 위반이다.
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

- [ ] **Step 5: 스키마 스모크 테스트**

테스트는 compose의 `portfolio_test` 데이터베이스를 쓴다(§A.2.5).

```java
package com.stockproject.portfolio;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/** 테스트는 compose의 portfolio_test 데이터베이스를 쓴다. `docker compose up -d db`가 선행되어야 한다. */
@SpringBootTest
@ActiveProfiles("test")
class SchemaSmokeTest {

    @Autowired JdbcClient jdbc;

    @Test
    void 마이그레이션이_테이블_여섯개를_만든다() {
        List<String> tables = jdbc.sql("""
                SELECT table_name FROM information_schema.tables
                 WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                 ORDER BY table_name
                """).query(String.class).list();

        assertThat(tables).contains("app_user", "account", "position_line", "realized_pnl_line",
                                    "manual_cashflow", "instrument");
    }

    /** 소유권 축은 account 하나에만 있다 — 설계 스펙 §3.8. */
    @Test
    void 소유권_축이_account에만_있다() {
        List<String> owning = jdbc.sql("""
                SELECT table_name FROM information_schema.columns
                 WHERE table_schema = 'public' AND column_name = 'user_id'
                 ORDER BY table_name
                """).query(String.class).list();

        assertThat(owning).containsExactly("account");
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

`src/test/resources/application-test.yaml` — 로컬 프로필과 같은 이유로 두 위치를 함께 적용한다:
```yaml
spring:
  datasource:
    url: ${TEST_DB_URL:jdbc:postgresql://localhost:5432/portfolio_test?currentSchema=public}
    username: ${DB_USER:portfolio}
    password: ${DB_PASSWORD:portfolio}
  flyway:
    locations: classpath:db/migration,classpath:db/external
```

Run: `docker compose up -d db && ./gradlew test --tests '*SchemaSmokeTest'` → PASS.

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
      - ./docker/initdb:/docker-entrypoint-initdb.d:ro
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

`docker/initdb/01-create-test-database.sql` — 첫 기동 시 테스트 DB를 함께 만든다:
```sql
-- 테스트 전용 데이터베이스. 개발용 portfolio 와 분리해 테스트가 개발 데이터를 지우지 않게 한다.
CREATE DATABASE portfolio_test OWNER portfolio;
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

-- app_user는 지우지 않는다. 팀원 계정은 마이그레이션이 소유하는 실제 계정이고,
-- 이 파일은 계좌부터 아래의 포트폴리오 내용만 다시 만드는 픽스처다.
TRUNCATE realized_pnl_line, manual_cashflow, position_line, account, instrument;

-- 계좌가 하나도 없는 사용자. 요약 뷰의 온보딩 상태(NO_ACCOUNTS)를 재현하기 위한
-- 픽스처이며 사람이 아니다 — 그래서 마이그레이션이 아니라 여기서 만든다.
INSERT INTO app_user (id, email, password_hash, display_name) VALUES
 ('40000000-0000-0000-0000-000000000004','test_empty@a.com','<bcrypt>','test_empty')
ON CONFLICT (id) DO NOTHING;

INSERT INTO instrument (instrument_id, isin, symbol, name, asset_class, market, currency, sector, is_leveraged) VALUES
 ('10000000-0000-0000-0000-000000000001','KR7005930003','005930','삼성전자','STOCK','KR','KRW','반도체',false),
 ('10000000-0000-0000-0000-000000000002','KR7000660001','000660','SK하이닉스','STOCK','KR','KRW','반도체',false),
 ('10000000-0000-0000-0000-000000000003','KR7035420009','035420','NAVER','STOCK','KR','KRW','소프트웨어',false),
 ('10000000-0000-0000-0000-000000000004','US0378331005','AAPL','애플','STOCK','US','USD','IT서비스',false),
 ('10000000-0000-0000-0000-000000000005','US5949181045','MSFT','마이크로소프트','STOCK','US','USD','소프트웨어',false),
 ('10000000-0000-0000-0000-000000000006','KR7133690008','133690','TIGER 미국나스닥100','ETF','KR','KRW',NULL,false),
 ('10000000-0000-0000-0000-000000000007',NULL,'CASH-KRW','KRW 예수금','CASH','KR','KRW',NULL,NULL),
 ('10000000-0000-0000-0000-000000000008',NULL,'CASH-USD','USD 예수금','CASH','US','USD',NULL,NULL);

INSERT INTO account (account_id, user_id, account_ref, broker, label, account_type, source, credential_ref, link_state, last_synced_at) VALUES
 ('20000000-0000-0000-0000-000000000001','40000000-0000-0000-0000-000000000001','ar_7f3a91c4','한국투자증권','한국투자 위탁','GENERAL','KIS',NULL,'CONNECTED',NULL),
 ('20000000-0000-0000-0000-000000000002','40000000-0000-0000-0000-000000000001','ar_2b8e05da','삼성증권','삼성증권','GENERAL','CODEF',NULL,'CONNECTED',NULL),
 ('20000000-0000-0000-0000-000000000003','40000000-0000-0000-0000-000000000001','ar_c41d6e70','한국투자증권','한국투자 IRP','PENSION','KIS',NULL,'CONNECTED',NULL),
 ('20000000-0000-0000-0000-000000000004','40000000-0000-0000-0000-000000000001','ar_9a52f3b1','미래에셋증권','미래에셋 연금','PENSION','CODEF',NULL,'CONNECTED',NULL),
 ('20000000-0000-0000-0000-000000000005','40000000-0000-0000-0000-000000000002','ar_53c0ab29','키움증권','키움 위탁','GENERAL','CODEF',NULL,'CONNECTED',NULL),
 ('20000000-0000-0000-0000-000000000006','40000000-0000-0000-0000-000000000002','ar_e6740f8c','미래에셋증권','미래에셋 IRP','PENSION','CODEF',NULL,'CONNECTED',NULL),
 ('20000000-0000-0000-0000-000000000007','40000000-0000-0000-0000-000000000003','ar_18d9b642','한국투자증권','한국투자 위탁','GENERAL','KIS',NULL,'CONNECTED',NULL);

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
   100,100,140000,140000,1400,'2026-07-24','2026-07-24T15:30:00+09',true,false),
 -- jdh — 005930·133690을 yhr과 겹쳐 보유한다. 스코프가 새면 수량과 평단이 흔들린다.
 ('2026-07-27','20000000-0000-0000-0000-000000000005','10000000-0000-0000-0000-000000000001',100,
   6500000,7120000,6500000,7120000,1,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 ('2026-07-27','20000000-0000-0000-0000-000000000005','10000000-0000-0000-0000-000000000007',880000,
   880000,880000,880000,880000,1,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 ('2026-07-27','20000000-0000-0000-0000-000000000006','10000000-0000-0000-0000-000000000006',50,
   5000000,5500000,5000000,5500000,1,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 ('2026-07-27','20000000-0000-0000-0000-000000000006','10000000-0000-0000-0000-000000000007',500000,
   500000,500000,500000,500000,1,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 -- hhj — 07-27에 연동을 시작해 직전 스냅샷이 없다. as_of 캘린더가 스코프 안에 있는지 드러낸다.
 ('2026-07-27','20000000-0000-0000-0000-000000000007','10000000-0000-0000-0000-000000000004',5,
   1000,1100,1400000,1540000,1400,'2026-07-27','2026-07-27T15:30:00+09',false,false),
 ('2026-07-27','20000000-0000-0000-0000-000000000007','10000000-0000-0000-0000-000000000007',460000,
   460000,460000,460000,460000,1,'2026-07-27','2026-07-27T15:30:00+09',false,false);

-- as_of 2026-07-24 (EOD 확정). 삼성전자 단가만 65,200원으로 다르다 — 같은 날의 같은 종가라
-- 보유 수량에 곱하면 사용자마다의 값이 나온다. hhj는 아직 연동 전이라 제외한다.
INSERT INTO position_line (as_of, account_id, instrument_id, quantity,
    cost_amount_local, market_value_local, cost_amount_krw, market_value_krw,
    fx_rate, fx_as_of, source_as_of, is_carried_forward, is_final)
SELECT '2026-07-24', account_id, instrument_id, quantity,
       cost_amount_local,
       CASE WHEN instrument_id = '10000000-0000-0000-0000-000000000001'
            THEN quantity * 65200 ELSE market_value_local END,
       cost_amount_krw,
       CASE WHEN instrument_id = '10000000-0000-0000-0000-000000000001'
            THEN quantity * 65200 ELSE market_value_krw END,
       fx_rate, '2026-07-24', '2026-07-24T15:30:00+09', false, true
  FROM position_line
 WHERE as_of = '2026-07-27'
   AND account_id <> '20000000-0000-0000-0000-000000000007';

INSERT INTO realized_pnl_line (trade_id, account_id, instrument_id, sold_at, quantity,
    sell_amount_local, cost_basis_local, sell_amount_krw, cost_basis_krw,
    fee_tax, realized_pnl_local, realized_pnl_krw, grade) VALUES
 ('T-0001','20000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001',
   '2026-03-02T09:31:00+09',3,400000,320000,400000,320000,1000,79000,79000,'SEEDED'),
 ('T-0002','20000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001',
   '2026-05-12T10:02:00+09',5,700000,500000,700000,500000,2000,198000,198000,'VERIFIED'),
 ('T-0003','20000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000003',
   '2026-02-18T13:44:00+09',10,2000000,2300000,2000000,2300000,5000,-305000,-305000,'VERIFIED'),
 -- jdh의 005930 매도. 스코프가 새면 yhr의 삼성전자 노드에 섞여 trade_count와 last_sold_at이 밀린다.
 ('T-1001','20000000-0000-0000-0000-000000000005','10000000-0000-0000-0000-000000000001',
   '2026-06-19T11:07:00+09',2,150000,130000,150000,130000,1000,19000,19000,'VERIFIED');

-- 사용자 입력 입출금. (기초 as_of 2026-07-24, 기말 as_of 2026-07-27] 안에 들어와야
-- 자산 변화 항등식이 성립한다
INSERT INTO manual_cashflow (id, account_id, type, amount, currency, occurred_on, memo) VALUES
 ('30000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001',
   'DEPOSIT',2000000,'KRW','2026-07-27','월 적립'),
 ('30000000-0000-0000-0000-000000000002','20000000-0000-0000-0000-000000000005',
   'DEPOSIT',500000,'KRW','2026-07-27','월 적립');

COMMIT;
```

- [ ] **Step 8: 사용자 격리 테스트**

스코프를 거는 코드는 아직 없다. 이 단계에서 검사하는 것은 **데이터가 사용자별로 갈릴 수 있게 놓였는가**이며, 이후 태스크가 조회 경로에서 이 값을 재현해야 한다.

```java
/** 소유권 축이 사용자별 합계를 실제로 가른다. */
@SpringBootTest
@ActiveProfiles("test")
class UserScopeIsolationTest {

    @Autowired JdbcClient jdbc;

    @Test
    void 사용자별_총자산이_갈린다() {
        Map<String, Long> totals = jdbc.sql("""
                SELECT u.display_name, coalesce(sum(pl.market_value_krw), 0) AS total
                  FROM app_user u
                  LEFT JOIN account a ON a.user_id = u.id
                  LEFT JOIN position_line pl
                         ON pl.account_id = a.account_id AND pl.as_of = DATE '2026-07-27'
                 GROUP BY u.display_name
                """).query((rs, n) -> Map.entry(rs.getString(1), rs.getLong(2)))
                    .list().stream().collect(toMap(Map.Entry::getKey, Map.Entry::getValue));

        assertThat(totals).containsOnly(
                entry("yhr", 58_000_000L), entry("jdh", 14_000_000L),
                entry("hhj", 2_000_000L),  entry("test_empty", 0L));
    }

    /** 스코프를 빠뜨리면 이 값이 나온다 — 대조군이다. */
    @Test
    void 스코프_없는_합계는_전역이다() {
        assertThat(jdbc.sql("SELECT sum(market_value_krw) FROM position_line WHERE as_of = DATE '2026-07-27'")
                .query(Long.class).single()).isEqualTo(74_000_000L);
    }

    /** as_of 캘린더도 사용자별이다 — hhj는 07-27에 연동했다(§3.8). */
    @Test
    void as_of_후보가_사용자마다_다르다() {
        assertThat(asOfsOf("hhj")).containsExactly(LocalDate.of(2026, 7, 27));
        assertThat(asOfsOf("yhr")).containsExactly(LocalDate.of(2026, 7, 24), LocalDate.of(2026, 7, 27));
    }

    /** 겹치는 종목이 사용자마다 다른 수량으로 잡힌다. */
    @Test
    void 같은_종목을_두_사용자가_보유한다() {
        assertThat(quantityOf("yhr", "005930")).isEqualByComparingTo("200");
        assertThat(quantityOf("jdh", "005930")).isEqualByComparingTo("100");
    }
}
```

- [ ] **Step 9: 검증 명령을 실행하고 결과를 확인한다**

위 **검증 방법**의 명령을 순서대로 돌려 기대값과 일치하는지 본다.

- [ ] **Step 10: README와 커밋**

`README.md`에 실행 방법(위 검증 명령), 스택, 소유 테이블 경계(`db/external`은 데이터팀 소유 미러라 운영에서 적용하지 않는다), 그리고 **사용자 계정과 비밀번호**를 적는다 — 팀원 셋의 로그인 계정이 마이그레이션에 들어 있고 비밀번호 해시가 로컬 개발용이라 운영 배포 전에 교체해야 한다는 사실이다.

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
- `AxisKey`는 `label`·`lensSensitive`·`enabled`·`applicableViews`를 갖는다. 축 → SQL 식 매핑은 Task 6의 `AxisSql`이 별도로 들고, 현지 통화 병기 플래그는 두지 않는다(불변식 3).

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
    ACCOUNT      ("account",      "계좌",     false, true,  Set.of(ViewKey.ACCOUNTS)),
    ACCOUNT_TYPE ("account_type", "계좌유형", false, true,  Set.of(ViewKey.ACCOUNTS)),
    INSTRUMENT   ("instrument",   "종목",     true,  true,  Set.of(ViewKey.POSITIONS, ViewKey.ALLOCATION)),
    SECTOR       ("sector",       "섹터",     true,  true,  Set.of(ViewKey.ALLOCATION)),
    MARKET       ("market",       "시장",     true,  true,  Set.of(ViewKey.ALLOCATION, ViewKey.SUMMARY)),
    CURRENCY     ("currency",     "통화",     true,  true,  Set.of(ViewKey.ALLOCATION)),
    ASSET_CLASS  ("asset_class",  "자산군",   true,  true,  Set.of(ViewKey.ALLOCATION, ViewKey.SUMMARY)),
    /** 원천 미확보로 비활성. 요청 시 AXIS_DISABLED로 거부한다 — 스펙 §6.1 · §9.3 */
    IS_LEVERAGED ("is_leveraged", "레버리지", true,  false, Set.of(ViewKey.ALLOCATION));

    private final String key;
    private final String label;
    private final boolean lensSensitive;
    private final boolean enabled;
    private final Set<ViewKey> applicableViews;

    AxisKey(String key, String label, boolean lensSensitive, boolean enabled,
            Set<ViewKey> applicableViews) {
        this.key = key; this.label = label; this.lensSensitive = lensSensitive;
        this.enabled = enabled; this.applicableViews = applicableViews;
    }

    public String key() { return key; }
    public String label() { return label; }
    /** true면 LOOK_THROUGH에서 이 축으로 필터할 수 없다 — 전개가 종목 자체를 바꾼다(스펙 §9.3). */
    public boolean lensSensitive() { return lensSensitive; }
    public boolean enabled() { return enabled; }
    public Set<ViewKey> applicableViews() { return applicableViews; }

    // 현지 통화 병기 플래그를 두지 않는다 — 판정은 조회 시점 통화 집합으로만 한다(스펙 §3.7 · 불변식 3).

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

`Catalog`에 6개를 상수로 둔다. `allocation`은 `groupBy`가 요청의 `axis` 하나로 결정되므로 `groupBy = []`, `axisOptions = [INSTRUMENT, SECTOR, MARKET, CURRENCY, ASSET_CLASS, IS_LEVERAGED]`로 둔다. `accounts`는 `groupBy = [ACCOUNT_TYPE, ACCOUNT]`, `rowFields = ["link_state","last_collection","last_synced_at","source_as_of","is_carried_forward"]`. `summary`는 `subBlocks = [new SubBlockSpec("mini_chart", List.of(MARKET), LensPolicy.OPTIONAL, List.of(MARKET_VALUE_KRW, WEIGHT_PCT))]`.

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

}
```

- [ ] **Step 6: 테스트 실행 → 커밋**

```bash
./gradlew test --tests '*CatalogInvariantTest'
git add -A && git commit -m "feat: 카탈로그 상수 — 축 8 · 지표 17 · 뷰 6"
```

---

### Task 3: 도메인 타입 — 가산성과 분모 규칙을 타입으로 강제한다

집계는 SQL이 하고, 이 태스크는 **그 결과를 받는 타입**과 **파생 지표 계산**을 만든다. 비율을 담을 자리가 없고 분모를 바꿔 낄 방법이 없는 것이 이 타입들의 목적이다.

**Files:**
- Create: `domain/AssetClass.java` · `Market.java` · `CurrencyCode.java` · `AccountType.java` · `LinkState.java` · `Grade.java`
- Create: `domain/measure/Measures.java` · `MeasureBundle.java` · `CurrencySet.java` · `LocalMoney.java`
- Create: `domain/group/GroupKey.java` · `GroupNode.java` · `Aggregation.java` · `TotalAssetsKrw.java` · `Derived.java`
- Test: `test/.../domain/group/DerivedTest.java` · `test/.../ArchitectureRulesTest.java`

**Interfaces:**
- Produces:
  - `Measures(BigDecimal quantity, costAmountLocal, marketValueLocal, costAmountKrw, marketValueKrw)` · `Measures.ZERO`
  - `MeasureBundle(Measures securities, Measures cash, CurrencySet currencies, int instrumentCount, int accountCount)` · `MeasureBundle.EMPTY` · `total()`
  - `CurrencySet.single()` → `Optional<CurrencyCode>`
  - `GroupKey(String key, String label, boolean other)` · `GroupKey.CASH` · `UNCLASSIFIED` · `OTHER`
  - `GroupNode(GroupKey key, MeasureBundle measures, List<GroupNode> children)`
  - `Aggregation(MeasureBundle responseTotal, List<GroupNode> rows)` · `weightDenominator()` → `TotalAssetsKrw`
  - `Derived.totalAssetsKrw/securitiesValueKrw/depositKrw/costAmountKrw/unrealizedPnlKrw/unrealizedPnlPct/avgCost(MeasureBundle)`, `Derived.weightPct(MeasureBundle, TotalAssetsKrw)`, `cashRatioPct(MeasureBundle, TotalAssetsKrw)`, `changePct(BigDecimal, TotalAssetsKrw)`
- Consumes: Task 2의 `MetricKey`

**완료 조건**
1. `Measures`·`MeasureBundle`에 비율 필드가 없고 나눗셈 메서드가 없다.
2. 손익 계열 파생값이 `securities` 슬롯만 읽는다 — CASH만 담긴 번들의 `unrealizedPnlKrw`가 `0`이고 `unrealizedPnlPct`가 `null`이다.
3. `TotalAssetsKrw`를 `domain.group` 밖에서 `new`로 만들 수 없다(컴파일 불가).
4. 가산성 반례 테스트(§A.3 불변식 1의 삼성전자/하이닉스 예시)가 `+11.8%`를 낸다.
5. `ArchitectureRulesTest`가 통과한다.

**검증 방법**
```bash
./gradlew test --tests '*DerivedTest' --tests '*ArchitectureRulesTest'
```

- [ ] **Step 1: 실패하는 가산성 테스트를 먼저 쓴다**

```java
package com.stockproject.portfolio.domain.group;

import com.stockproject.portfolio.domain.CurrencyCode;
import com.stockproject.portfolio.domain.measure.*;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DerivedTest {

    /** 스펙 §3.2 — 라인별 수익률 평균은 틀리고, 집계 후 계산이 맞다. */
    @Test
    void 손익률은_그룹_평균이_아니라_집계값에서_계산된다() {
        MeasureBundle samsung  = securities("10000000", "11000000");
        MeasureBundle hynix    = securities("1000000",  "1300000");
        MeasureBundle combined = securities("11000000", "12300000");   // SQL이 낸 합계

        assertThat(Derived.unrealizedPnlPct(samsung)).isEqualByComparingTo("10.0");
        assertThat(Derived.unrealizedPnlPct(hynix)).isEqualByComparingTo("30.0");
        // (10 + 30) / 2 = 20.0 이 아니다
        assertThat(Derived.unrealizedPnlPct(combined)).isEqualByComparingTo("11.8");
        assertThat(Derived.unrealizedPnlKrw(combined)).isEqualByComparingTo("1300000");
    }

    /** 불변식 2 — 손익률 분모는 매입금액(CASH 제외). 예수금이 섞이면 값이 희석된다. */
    @Test
    void 예수금은_손익_분모에_섞이지_않는다() {
        MeasureBundle b = bundle(measures("10000000", "11000000"), measures("5000000", "5000000"));

        assertThat(Derived.costAmountKrw(b)).isEqualByComparingTo("10000000");
        assertThat(Derived.unrealizedPnlKrw(b)).isEqualByComparingTo("1000000");
        assertThat(Derived.unrealizedPnlPct(b)).isEqualByComparingTo("10.0");   // 6.7이 아니다
        assertThat(Derived.totalAssetsKrw(b)).isEqualByComparingTo("16000000");
        assertThat(Derived.securitiesValueKrw(b)).isEqualByComparingTo("11000000");
        assertThat(Derived.depositKrw(b)).isEqualByComparingTo("5000000");
    }

    /** 불변식 2 — 비중의 분모는 응답 전체 총자산이며 그룹 자신의 합계가 아니다. */
    @Test
    void 비중의_분모는_응답_전체_총자산이다() {
        MeasureBundle row   = securities("10000000", "11000000");
        MeasureBundle whole = bundle(measures("10000000", "11000000"), measures("5000000", "5000000"));
        Aggregation agg = new Aggregation(whole, List.of());

        assertThat(Derived.weightPct(row, agg.weightDenominator())).isEqualByComparingTo("68.8");
        assertThat(Derived.cashRatioPct(whole, agg.weightDenominator())).isEqualByComparingTo("31.3");
    }

    @Test
    void 분모가_영이면_비율은_null이다() {
        MeasureBundle onlyCash = bundle(Measures.ZERO, measures("5000000", "5000000"));
        assertThat(Derived.unrealizedPnlPct(onlyCash)).isNull();
        assertThat(Derived.unrealizedPnlKrw(onlyCash)).isEqualByComparingTo("0");
    }

    // --- 픽스처 -------------------------------------------------------------
    private static Measures measures(String costKrw, String marketKrw) {
        return new Measures(BigDecimal.ONE, new BigDecimal(costKrw), new BigDecimal(marketKrw),
                new BigDecimal(costKrw), new BigDecimal(marketKrw));
    }

    private static MeasureBundle bundle(Measures securities, Measures cash) {
        return new MeasureBundle(securities, cash, CurrencySet.of(CurrencyCode.KRW), 1, 1);
    }

    private static MeasureBundle securities(String costKrw, String marketKrw) {
        return bundle(measures(costKrw, marketKrw), Measures.ZERO);
    }
}
```

- [ ] **Step 2: 실행해 컴파일 실패를 확인한다**

Run: `./gradlew test --tests '*DerivedTest'`
Expected: 컴파일 실패 — `Measures` · `MeasureBundle` · `Derived` · `Aggregation` · `TotalAssetsKrw`가 없다.

- [ ] **Step 3: 열거 타입**

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

- [ ] **Step 4: `Measures` — 가산 측정값만 담는다**

```java
package com.stockproject.portfolio.domain.measure;

import java.math.BigDecimal;

/**
 * 집계 쿼리가 낸 SUM 값을 받는 타입 — 스펙 §1.5 · §3.2.
 * 비율 필드가 없고 나눗셈 연산이 없다. 자리가 없으면 잘못 더할 방법도 없다.
 * 비율은 Derived만 만들 수 있으며 입력이 집계된 MeasureBundle이다.
 */
public record Measures(BigDecimal quantity,
                       BigDecimal costAmountLocal, BigDecimal marketValueLocal,
                       BigDecimal costAmountKrw, BigDecimal marketValueKrw) {

    public static final Measures ZERO = new Measures(
            BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO);
}
```

- [ ] **Step 5: `CurrencySet` · `LocalMoney` · `MeasureBundle`**

```java
package com.stockproject.portfolio.domain.measure;

import com.stockproject.portfolio.domain.CurrencyCode;

import java.util.*;

/** 불변식 3 — 묶음의 통화 집합. 집계 쿼리의 array_agg(DISTINCT currency)를 받는다. */
public record CurrencySet(Set<CurrencyCode> values) {

    public static final CurrencySet EMPTY = new CurrencySet(Set.of());

    public static CurrencySet of(CurrencyCode... codes) {
        return codes.length == 0 ? EMPTY : new CurrencySet(EnumSet.copyOf(List.of(codes)));
    }

    /** 통화가 하나뿐일 때만 값이 있다. 섞인 묶음에는 현지 통화를 실을 방법이 없다. */
    public Optional<CurrencyCode> single() {
        return values.size() == 1 ? Optional.of(values.iterator().next()) : Optional.empty();
    }
}
```

```java
package com.stockproject.portfolio.domain.measure;

import com.stockproject.portfolio.domain.CurrencyCode;
import java.math.BigDecimal;

public record LocalMoney(CurrencyCode currency, BigDecimal marketValue, BigDecimal costAmount) { }
```

```java
package com.stockproject.portfolio.domain.measure;

/**
 * 집계 쿼리 한 행의 측정값 — 불변식 2를 타입으로 굳힌다.
 * CASH(예수금 의사종목)를 별도 슬롯에 담아, 손익 계열 파생값이 예수금을 섞을 코드 경로가 없다.
 * 두 슬롯은 SQL의 FILTER (WHERE asset_class <> 'CASH') 절이 갈라 준다. 스펙 §5.2 · §6.2.
 */
public record MeasureBundle(Measures securities, Measures cash, CurrencySet currencies,
                            int instrumentCount, int accountCount) {

    public static final MeasureBundle EMPTY =
            new MeasureBundle(Measures.ZERO, Measures.ZERO, CurrencySet.EMPTY, 0, 0);

    /** 예수금 포함 합계. total_assets_krw · market_value_krw · weight_pct 분모의 원천. */
    public Measures total() {
        return new Measures(
                securities.quantity().add(cash.quantity()),
                securities.costAmountLocal().add(cash.costAmountLocal()),
                securities.marketValueLocal().add(cash.marketValueLocal()),
                securities.costAmountKrw().add(cash.costAmountKrw()),
                securities.marketValueKrw().add(cash.marketValueKrw()));
    }
}
```

`total()`이 유일한 덧셈이며 **같은 그룹 안의 두 슬롯을 합치는 것**이다. 그룹끼리 더하는 연산은 두지 않는다 — 그것은 SQL이 한다.

- [ ] **Step 6: `GroupKey` · `GroupNode` · `Aggregation` · `TotalAssetsKrw` · `Derived`**

```java
package com.stockproject.portfolio.domain.group;

/** 축 값 하나. 기타 버킷은 other=true이며 정렬 시 항상 맨 끝으로 간다(스펙 §3.6 6단계). */
public record GroupKey(String key, String label, boolean other) {

    public static final GroupKey CASH         = new GroupKey("CASH", "현금", false);
    public static final GroupKey UNCLASSIFIED = new GroupKey("UNCLASSIFIED", "미분류", false);
    public static final GroupKey OTHER        = new GroupKey("OTHER", "기타(ETF 내 비주식·미매칭)", true);

    public static GroupKey of(String key, String label) {
        return new GroupKey(key, label, "OTHER".equals(key));
    }
}
```

```java
package com.stockproject.portfolio.domain.group;

import com.stockproject.portfolio.domain.measure.MeasureBundle;
import java.util.List;

public record GroupNode(GroupKey key, MeasureBundle measures, List<GroupNode> children) { }
```

```java
package com.stockproject.portfolio.domain.group;

import com.stockproject.portfolio.domain.measure.MeasureBundle;
import java.util.List;

/** 집계 쿼리 산출물 — GROUPING SETS의 전체 합계 행과 축 값 행들. */
public record Aggregation(MeasureBundle responseTotal, List<GroupNode> rows) {

    /** 비중의 분모. 전체 합계 행에서 오며 Σ rows와 같은 스캔에서 나온다(§8.3). */
    public TotalAssetsKrw weightDenominator() { return TotalAssetsKrw.of(responseTotal); }
}
```

```java
package com.stockproject.portfolio.domain.group;

import com.stockproject.portfolio.domain.measure.MeasureBundle;
import java.math.BigDecimal;

/**
 * 비중의 분모 — 불변식 2.
 * 생성자와 팩터리가 package-private이라 domain.group 밖에서 만들 수 없고,
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

`Derived`는 이전 설계와 같다 — 파생 지표를 만드는 유일한 지점이고, 비율은 소수 1자리 `HALF_UP`, 분모가 0이면 `null`이다.

```java
package com.stockproject.portfolio.domain.group;

import com.stockproject.portfolio.domain.CurrencyCode;
import com.stockproject.portfolio.domain.measure.MeasureBundle;

import java.math.BigDecimal;
import java.math.RoundingMode;

/** 파생 지표를 만드는 유일한 지점 — 스펙 §3.6 5단계. */
public final class Derived {

    private static final BigDecimal HUNDRED = new BigDecimal("100");
    private static final int PCT_SCALE = 1;

    private Derived() { }

    public static BigDecimal totalAssetsKrw(MeasureBundle b)     { return b.total().marketValueKrw(); }
    public static BigDecimal securitiesValueKrw(MeasureBundle b) { return b.securities().marketValueKrw(); }
    public static BigDecimal depositKrw(MeasureBundle b)         { return b.cash().marketValueKrw(); }
    public static BigDecimal costAmountKrw(MeasureBundle b)      { return b.securities().costAmountKrw(); }

    public static BigDecimal unrealizedPnlKrw(MeasureBundle b) {
        return b.securities().marketValueKrw().subtract(b.securities().costAmountKrw());
    }

    public static BigDecimal unrealizedPnlPct(MeasureBundle b) {
        return pct(unrealizedPnlKrw(b), b.securities().costAmountKrw());
    }

    /** 평단 = Σ매입 ÷ Σ수량. 통화 소수 자릿수로 반올림. 수량이 0이면 null. */
    public static BigDecimal avgCost(MeasureBundle b, CurrencyCode currency) {
        BigDecimal qty = b.securities().quantity();
        if (qty.signum() == 0) return null;
        return b.securities().costAmountLocal().divide(qty, currency.scale(), RoundingMode.HALF_UP);
    }

    public static int instrumentCount(MeasureBundle b) { return b.instrumentCount(); }
    public static int accountCount(MeasureBundle b)    { return b.accountCount(); }

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

- [ ] **Step 7: 테스트 통과 확인**

Run: `./gradlew test --tests '*DerivedTest'` → PASS. `11.8`과 `10.0`(예수금 희석 없음)이 나와야 한다.

- [ ] **Step 8: `TotalAssetsKrw` 봉인을 컴파일로 확인한다**

**`domain.group` 밖의 패키지에서** 확인해야 한다. `DerivedTest`는 같은 패키지라 소스 루트가 달라도 접근이 열려 있어 봉인이 드러나지 않는다. 임시 파일을 다른 패키지에 두고 컴파일해 두 줄이 모두 막히는지 보고 지운다.

```java
package com.stockproject.portfolio.domain.measure;   // domain.group이 아니다

TotalAssetsKrw byFactory     = TotalAssetsKrw.of(MeasureBundle.EMPTY);   // 팩터리 package-private
TotalAssetsKrw byConstructor = new TotalAssetsKrw(BigDecimal.ZERO);      // 생성자 private
```

- [ ] **Step 9: ArchUnit 규칙**

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

    /** 불변식 1 — 집계 결과 타입에 비율 필드를 둘 수 없다(스펙 §1.5 · §9.2). */
    @Test
    void 측정값_타입에_비율_필드가_없다() {
        ArchRule rule = fields()
                .that().areDeclaredInClassesThat().haveSimpleNameEndingWith("Measures")
                .or().areDeclaredInClassesThat().haveSimpleName("MeasureBundle")
                .should().haveNameNotMatching(".*(Pct|Ratio|Rate|Percent|Yield|Weight)$")
                .because("비율은 가산 불가라 집계 결과 타입에 자리를 두지 않는다 (스펙 §1.5)");
        rule.check(classes);
    }

    @Test
    void 도메인에_double과_float가_없다() {
        ArchRule rule = fields()
                .that().areDeclaredInClassesThat().resideInAPackage("..domain..")
                .should().notHaveRawType(double.class)
                .andShould().notHaveRawType(float.class)
                .because("금액 계산은 BigDecimal로만 한다");
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

- [ ] **Step 10: 전체 테스트 → 커밋**

```bash
./gradlew test --tests '*DerivedTest' --tests '*ArchitectureRulesTest' --tests '*MigrationLintTest'
git add -A && git commit -m "feat: 집계 결과 타입과 파생 지표 — 가산성과 분모 규칙을 타입으로 강제"
```

---

### Task 4: 계좌·달력 조회와 런타임 검증 (§9.1)

**Files:**
- Create: `auth/UserScope.java`
- Create: `query/AccountRepository.java` · `SnapshotCalendarRepository.java` · `LineFilter.java`
- Create: `query/CollectionStatusPort.java` · `NoCollectionStatusPort.java`
- Create: `validation/PositionLineInvariants.java` · `FactInvariantViolation.java`
- Test: `test/.../query/AccountRepositoryTest.java` · `SchemaContractTest.java` · `test/.../validation/PositionLineInvariantsTest.java`

**Interfaces:**
- Produces:
  - `record UserScope(UUID userId)` — 조회의 대상 세계를 정한다(§3.8). Task 8이 토큰에서 만들어 주입하며, 이 태스크에서는 저장소가 받는 파라미터로만 쓴다
  - `record AccountRow(UUID id, String broker, String label, AccountType type, LinkState linkState, OffsetDateTime lastSyncedAt)`
  - `List<AccountRow> AccountRepository.findAll(UserScope scope)`
  - `record LineFilter(Set<UUID> accountIds, Set<AccountType> accountTypes, Set<Market> markets, Set<AssetClass> assetClasses)` · `LineFilter.NONE` · `isEmpty()`
  - `Optional<LocalDate> SnapshotCalendarRepository.latestAsOf(UserScope)` · `previousAsOf(UserScope, LocalDate)` · `latestOnOrBefore(UserScope, LocalDate)` · `latestBefore(UserScope, LocalDate)` · `earliestOnOrAfter(UserScope, LocalDate)`
  - `BigDecimal SnapshotCalendarRepository.totalAssetsKrwAt(UserScope, LocalDate, LineFilter)`
  - `void PositionLineInvariants.validate(UserScope, LocalDate asOf)`

**완료 조건**
1. `yhr` 스코프에서 `latestAsOf()`가 `2026-07-27`, `previousAsOf`가 `2026-07-24`, `totalAssetsKrwAt(2026-07-24)`가 `56800000`이다.
2. **`hhj` 스코프에서 `latestAsOf()`가 `2026-07-27`이고 `previousAsOf`가 비어 있다** — `as_of` 캘린더가 사용자별이다(§3.8).
3. `AccountRepository.findAll`이 `yhr`에 4행, `jdh`에 2행, `hhj`에 1행, `test_empty`에 0행을 낸다.
4. `PositionLineInvariants.validate`가 §A.8의 6개 규칙을 **SQL 검사 쿼리**로 확인하고 위반 시 `FactInvariantViolation`을 던진다. 검사 범위는 그 사용자의 계좌다.
5. 위반 데이터를 넣으면 실제로 실패한다 — 규칙마다 테스트가 있다. **남의 계좌를 깨뜨리면 내 검증은 통과한다.**
6. `SchemaContractTest`가 데이터팀 소유 `instrument`의 컬럼 계약을 `information_schema`로 확인한다.
7. `LineFilter`와 `UserScope`가 **별개 타입**이다. `LineFilter.NONE`으로 스코프까지 비워지는 경로가 없다(§A.3 불변식 5).

**검증 방법**
```bash
./gradlew test --tests '*AccountRepositoryTest' --tests '*SchemaContractTest' \
               --tests '*PositionLineInvariantsTest'
```

> 운영 코드는 매퍼만 쓴다. **테스트의 픽스처 조작과 단언에는 `JdbcClient`를 그대로 쓴다** — 위반 데이터를 만들거나 `information_schema`를 훑는 일회성 SQL에 매퍼를 만들 이유가 없다. `mybatis-spring-boot-starter`가 `spring-boot-starter-jdbc`를 함께 가져오므로 의존성 추가가 없다.

- [ ] **Step 1: `UserScope`와 `LineFilter` — 타입을 가른다**

```java
package com.stockproject.portfolio.auth;

import java.util.UUID;

/**
 * 스코프 — 조회 대상 행이 애초에 누구 것인가(스펙 §3.8).
 * 요청이 고를 수 없으므로 LineFilter와 타입을 나눈다. 한 타입에 담으면
 * LineFilter.NONE 하나로 스코프까지 비워진다.
 */
public record UserScope(UUID userId) {
    public UserScope {
        java.util.Objects.requireNonNull(userId, "스코프 없는 조회는 성립하지 않는다");
    }
}
```

```java
package com.stockproject.portfolio.query;

import com.stockproject.portfolio.domain.*;

import java.util.Set;
import java.util.UUID;

/**
 * 요청 필터 — 스펙 §3.3. 필터는 그레인을 바꾸지 않고 대상 행만 고른다.
 * 값은 카탈로그 대조(§9.3)를 통과한 enum·계좌 ID이므로 SQL에 사용자 문자열이 닿지 않는다.
 * 계좌 ID의 소유 검사는 요청 검증 단계가 한다(§9.3) — 여기서는 이미 통과한 값만 받는다.
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

**`LineFilter.NONE`이 있고 `UserScope.NONE`이 없는 것**이 두 개념의 차이다. 필터를 걸지 않는 요청은 정상이고, 스코프를 걸지 않는 요청은 존재하지 않는다.

- [ ] **Step 2: 런타임 검증 테스트를 먼저 쓴다**

`PositionLineInvariantsTest` — 규칙마다 위반 데이터를 넣고 실패를 확인한다. 샘플 적재 후 각 테스트가 한 규칙만 깨뜨린다.

```java
    private static final UserScope YHR = new UserScope(UUID.fromString("40000000-…-0001"));
    private static final UserScope JDH = new UserScope(UUID.fromString("40000000-…-0002"));

    @Test
    void 정상_샘플은_통과한다() {
        invariants.validate(YHR, LocalDate.of(2026, 7, 27));      // 예외 없음
    }

    /** 스펙 §9.1 — 연동이 유효한 모든 계좌는 해당 as_of에 라인이 있어야 한다. */
    @Test
    void 연동된_계좌에_라인이_없으면_거부한다() {
        jdbc.sql("DELETE FROM position_line WHERE as_of = :d AND account_id = :a")
                .param("d", LocalDate.of(2026, 7, 27)).param("a", MIRAE).update();

        assertThatThrownBy(() -> invariants.validate(YHR, LocalDate.of(2026, 7, 27)))
                .isInstanceOf(FactInvariantViolation.class)
                .hasMessageContaining("라인 없음");
    }

    /** 검증도 스코프 안에서 한다 — 남의 데이터가 깨져도 내 조회는 산다. */
    @Test
    void 다른_사용자의_위반은_내_검증을_깨지_않는다() {
        jdbc.sql("DELETE FROM position_line WHERE as_of = :d AND account_id = :a")
                .param("d", LocalDate.of(2026, 7, 27)).param("a", KIWOOM).update();   // jdh의 계좌

        invariants.validate(YHR, LocalDate.of(2026, 7, 27));      // 예외 없음
        assertThatThrownBy(() -> invariants.validate(JDH, LocalDate.of(2026, 7, 27)))
                .hasMessageContaining("라인 없음");
    }

    /** 스펙 §7.5 — 연동 해제 계좌는 대상이 아니다. */
    @Test
    void 해제된_계좌는_라인이_없어도_통과한다() {
        jdbc.sql("DELETE FROM position_line WHERE as_of = :d AND account_id = :a")
                .param("d", LocalDate.of(2026, 7, 27)).param("a", MIRAE).update();
        jdbc.sql("UPDATE account SET link_state = 'DISCONNECTED' WHERE account_id = :a")
                .param("a", MIRAE).update();

        invariants.validate(YHR, LocalDate.of(2026, 7, 27));      // 예외 없음
    }

    /** 스펙 §5.2 — CASH 행은 원가 = 평가금액. */
    @Test
    void CASH_행의_원가가_평가금액과_다르면_거부한다() {
        jdbc.sql("""
                UPDATE position_line SET cost_amount_krw = market_value_krw - 1
                 WHERE as_of = :d AND instrument_id = :i AND account_id = :a
                """).param("d", LocalDate.of(2026, 7, 27)).param("i", CASH_KRW)
                    .param("a", KIS_GENERAL).update();

        assertThatThrownBy(() -> invariants.validate(YHR, LocalDate.of(2026, 7, 27)))
                .hasMessageContaining("CASH");
    }

    /** 스펙 §9.1 — is_carried_forward = true이면 source_as_of < as_of. */
    @Test
    void 이월_라인의_source_as_of가_as_of_이후면_거부한다() {
        jdbc.sql("""
                UPDATE position_line SET source_as_of = '2026-07-28T15:30:00+09'
                 WHERE as_of = :d AND is_carried_forward
                """).param("d", LocalDate.of(2026, 7, 27)).update();

        assertThatThrownBy(() -> invariants.validate(YHR, LocalDate.of(2026, 7, 27)))
                .hasMessageContaining("is_carried_forward");
    }
```

그레인 유일성은 PK가 막아 데이터로 재현할 수 없다. 대신 **검사 쿼리가 존재하고 0을 낸다**는 것을 확인한다.

```java
    @Test
    void 그레인_유일성_검사가_수행된다() {
        assertThatThrownBy(() -> jdbc.sql("""
                INSERT INTO position_line
                SELECT * FROM position_line WHERE as_of = :d LIMIT 1
                """).param("d", LocalDate.of(2026, 7, 27)).update())
                .isInstanceOf(org.springframework.dao.DuplicateKeyException.class);
    }
```

- [ ] **Step 3: 검증기 구현 — 검사를 SQL로 한다**

검사 쿼리는 애노테이션 매퍼로 둔다. 동적 조립이 없는 고정 SQL이라 XML을 쓸 이유가 없다.

```java
package com.stockproject.portfolio.query;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDate;

/**
 * 스펙 §9.1 팩트 정합성 검사. 각 메서드는 위반 건수를 낸다 — 0이면 통과다.
 * 모든 검사가 account를 조인해 스코프 안에서만 센다 — 남의 데이터가 깨졌다고
 * 내 화면이 500이 되지 않는다.
 */
@Mapper
public interface FactCheckMapper {

    /** 그레인 유일성 — PK가 1차 보증. 검사를 남겨 의도를 드러낸다. */
    @Select("""
            SELECT count(*) FROM (
              SELECT 1 FROM position_line pl JOIN account a USING (account_id)
               WHERE pl.as_of = #{asOf} AND a.user_id = #{scope.userId}
               GROUP BY pl.as_of, pl.account_id, pl.instrument_id HAVING count(*) > 1) d
            """)
    int duplicatedGrain(@Param("scope") UserScope scope, @Param("asOf") LocalDate asOf);

    /** market_value_krw가 있으면 fx_rate·fx_as_of 필수 (NOT NULL이 1차 보증). */
    @Select("""
            SELECT count(*) FROM position_line pl JOIN account a USING (account_id)
             WHERE pl.as_of = #{asOf} AND a.user_id = #{scope.userId}
               AND pl.market_value_krw IS NOT NULL
               AND (pl.fx_rate IS NULL OR pl.fx_as_of IS NULL)
            """)
    int missingFxRate(@Param("scope") UserScope scope, @Param("asOf") LocalDate asOf);

    /** CASH 행은 원가 = 평가금액 (스펙 §5.2). */
    @Select("""
            SELECT count(*) FROM position_line pl
              JOIN account a USING (account_id)
              JOIN instrument i USING (instrument_id)
             WHERE pl.as_of = #{asOf} AND a.user_id = #{scope.userId}
               AND i.asset_class = 'CASH'
               AND pl.cost_amount_krw <> pl.market_value_krw
            """)
    int cashCostMismatch(@Param("scope") UserScope scope, @Param("asOf") LocalDate asOf);

    /** is_carried_forward = true이면 source_as_of < as_of. */
    @Select("""
            SELECT count(*) FROM position_line pl JOIN account a USING (account_id)
             WHERE pl.as_of = #{asOf} AND a.user_id = #{scope.userId} AND pl.is_carried_forward
               AND (pl.source_as_of AT TIME ZONE 'Asia/Seoul')::date >= pl.as_of
            """)
    int carriedForwardNotStale(@Param("scope") UserScope scope, @Param("asOf") LocalDate asOf);

    /** 그 사용자의 연동이 유효한 모든 계좌는 해당 as_of에 라인 존재 (스펙 §7.3 · §9.1). */
    @Select("""
            SELECT count(*) FROM account a
             WHERE a.user_id = #{scope.userId} AND a.link_state <> 'DISCONNECTED'
               AND NOT EXISTS (SELECT 1 FROM position_line pl
                                WHERE pl.as_of = #{asOf} AND pl.account_id = a.account_id)
            """)
    int accountsWithoutLine(@Param("scope") UserScope scope, @Param("asOf") LocalDate asOf);
}
```

검사 하나가 **그 사용자의 `as_of`에서만 의미가 있다**는 점이 여기 드러난다. `hhj`에게 `2026-07-24`를 물으면 라인이 하나도 없어 전부 위반으로 나오지만, 애초에 캘린더가 그 날짜를 후보로 주지 않으므로 호출되지 않는다.

```java
package com.stockproject.portfolio.validation;

import com.stockproject.portfolio.query.FactCheckMapper;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.function.IntSupplier;

/**
 * 스펙 §9.1 팩트 정합성 — 집계 전에 통과해야 한다.
 * 집계를 SQL이 하므로 검증도 SQL로 한다. 적재된 행 일부가 아니라 그 as_of 전체를 본다.
 * 위반은 조용히 넘기지 않는다 — 손으로 넣은 샘플이 틀렸다는 뜻이므로 크게 터뜨린다.
 */
@Component
public class PositionLineInvariants {

    private final FactCheckMapper checks;

    public PositionLineInvariants(FactCheckMapper checks) { this.checks = checks; }

    public void validate(UserScope scope, LocalDate asOf) {
        List<String> violations = new ArrayList<>();

        add(violations, () -> checks.duplicatedGrain(scope, asOf),        "그레인 유일성 위반");
        add(violations, () -> checks.missingFxRate(scope, asOf),          "fx_rate·fx_as_of 누락");
        add(violations, () -> checks.cashCostMismatch(scope, asOf),       "CASH 행의 원가 ≠ 평가금액");
        add(violations, () -> checks.carriedForwardNotStale(scope, asOf), "is_carried_forward인데 source_as_of >= as_of");
        add(violations, () -> checks.accountsWithoutLine(scope, asOf),    "연동된 계좌에 라인 없음");

        if (!violations.isEmpty()) throw new FactInvariantViolation(violations);
    }

    private static void add(List<String> violations, IntSupplier check, String message) {
        int count = check.getAsInt();
        if (count > 0) violations.add("%s (%d건)".formatted(message, count));
    }
}
```

`AT TIME ZONE`이 immutable이 아니라 CHECK 제약으로 표현할 수 없어 규칙 4는 검사 쿼리 전용이다.

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

- [ ] **Step 4: `AccountMapper` · `SnapshotCalendarMapper` · `CollectionStatusPort`**

`AccountMapper.findAll(scope)`는 **그 사용자의** `account` 전체를 읽는다. `DISCONNECTED`도 함께 읽고 그 필터링은 호출자가 한다 — §7.5의 "연동 해제는 제외"와 §9.1의 "연동이 유효한 계좌"를 각각 판단해야 하기 때문이다. 스코프는 그와 달리 매퍼가 건다. 골라야 하는 것과 고를 수 없는 것의 차이다. `map-underscore-to-camel-case: true`라 `AccountRow`의 컴포넌트 이름이 컬럼과 그대로 맞는다.

`SnapshotCalendarMapper`는 `as_of` 축만 다룬다. 전부 고정 SQL이라 애노테이션으로 둔다. **다섯 쿼리 모두 `account`를 조인한다** — `as_of` 후보는 그 사용자의 계좌에 라인이 있는 날짜뿐이다(§3.8).

```java
@Mapper
public interface SnapshotCalendarMapper {

    @Select("""
            SELECT max(pl.as_of) FROM position_line pl JOIN account a USING (account_id)
             WHERE a.user_id = #{scope.userId}
            """)
    LocalDate latestAsOf(@Param("scope") UserScope scope);

    @Select("""
            SELECT max(pl.as_of) FROM position_line pl JOIN account a USING (account_id)
             WHERE a.user_id = #{scope.userId} AND pl.as_of < #{asOf}
            """)
    LocalDate previousAsOf(@Param("scope") UserScope scope, @Param("asOf") LocalDate asOf);

    @Select("""
            SELECT max(pl.as_of) FROM position_line pl JOIN account a USING (account_id)
             WHERE a.user_id = #{scope.userId} AND pl.as_of <= #{date}
            """)
    LocalDate latestOnOrBefore(@Param("scope") UserScope scope, @Param("date") LocalDate date);

    @Select("""
            SELECT max(pl.as_of) FROM position_line pl JOIN account a USING (account_id)
             WHERE a.user_id = #{scope.userId} AND pl.as_of < #{date}
            """)
    LocalDate latestBefore(@Param("scope") UserScope scope, @Param("date") LocalDate date);

    @Select("""
            SELECT min(pl.as_of) FROM position_line pl JOIN account a USING (account_id)
             WHERE a.user_id = #{scope.userId} AND pl.as_of >= #{date}
            """)
    LocalDate earliestOnOrAfter(@Param("scope") UserScope scope, @Param("date") LocalDate date);
}
```

**MyBatis 설정 둘이 이 매퍼들의 전제다.** `arg-name-based-constructor-auto-mapping: true`라야 결과가 record 생성자로 이름 기준 매핑되어 컬럼 순서에 묶이지 않고, `UuidTypeHandler`를 `type-handlers-package`로 등록해야 `IN (…)` 목록처럼 타입이 확정된 자리에서 `UUID`가 바인딩된다 — MyBatis 기본 등록에 `java.util.UUID`가 없다.

`SnapshotCalendarRepository`가 이 매퍼를 감싸 `null`을 `Optional`로 바꾸고 `totalAssetsKrwAt`을 제공한다.

`totalAssetsKrwAt`은 스코프와 `LineFilter`의 계좌 조건을 반영한다 — 이 값을 쓰는 두 뷰(요약의 일간 변화, 자산 변화)의 필터가 계좌·기간뿐이다.

```java
    @Test
    void as_of_캘린더가_사용자마다_다르다() {
        assertThat(calendar.latestAsOf(YHR)).contains(LocalDate.of(2026, 7, 27));
        assertThat(calendar.previousAsOf(YHR, LocalDate.of(2026, 7, 27)))
                .contains(LocalDate.of(2026, 7, 24));

        assertThat(calendar.latestAsOf(HHJ)).contains(LocalDate.of(2026, 7, 27));
        assertThat(calendar.previousAsOf(HHJ, LocalDate.of(2026, 7, 27))).isEmpty();
        assertThat(calendar.latestAsOf(TEST_EMPTY)).isEmpty();
    }

    @Test
    void 총자산이_사용자마다_갈린다() {
        assertThat(calendar.totalAssetsKrwAt(YHR, LocalDate.of(2026, 7, 24), LineFilter.NONE))
                .isEqualByComparingTo("56800000");
        assertThat(calendar.totalAssetsKrwAt(JDH, LocalDate.of(2026, 7, 24), LineFilter.NONE))
                .isEqualByComparingTo("13400000");
        assertThat(calendar.totalAssetsKrwAt(HHJ, LocalDate.of(2026, 7, 24), LineFilter.NONE))
                .isEqualByComparingTo("0");
    }

`CollectionStatusPort`는 데이터팀 소유 `collection_run`을 읽는 자리이며(스펙 §7.7), 계약이 미합의라 `NoCollectionStatusPort`가 빈 맵을 낸다.

- [ ] **Step 5: 스키마 계약 테스트**

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

- [ ] **Step 6: 테스트 통과 → 커밋**

```bash
./gradlew test --tests '*AccountRepositoryTest' --tests '*SchemaContractTest' --tests '*PositionLineInvariantsTest'
git add -A && git commit -m "feat: 계좌·달력 조회와 팩트 정합성 검증"
```

---

### Task 5: 렌즈 — CTE로 표현한다 (§3.4 · §3.6 2단계)

**Files:**
- Create: `src/main/resources/mapper/AggregateMapper.xml` (렌즈 `<sql>` 조각) · `EtfCoverageMapper.xml`
- Create: `query/aggregate/AggregateMapper.java` · `EtfCoverageMapper.java` · `UndecomposedEtf.java`
- Create: `src/main/resources/db/external/V3__etf_coverage_mirror.sql`
- Modify: `db/sample/sample_portfolio.sql` (`TRUNCATE` 대상에 `etf_coverage`를 더한다 — 픽스처가 세계 전체를 소유한다)
- Test: `test/.../query/aggregate/LensPreservationTest.java`

**Interfaces:**
- Produces:
  - `BigDecimal AggregateMapper.sumMarketValueKrw(UserScope scope, LocalDate asOf, Lens lens)` — 렌즈 CTE의 총합
  - `record UndecomposedEtf(int count, BigDecimal marketValueKrw, List<String> keys)`
  - `UndecomposedEtf EtfCoverageMapper.undecomposedAt(UserScope scope, LocalDate asOf, LineFilter filter)`

**완료 조건**
1. `DIRECT`와 `LOOK_THROUGH` 두 CTE 모두 `Σ market_value_krw`가 그 사용자의 `position_line` 총합과 같다 — 총합 보존(§9.1).
2. `etf_coverage`가 비어 있으면 `LOOK_THROUGH`가 ETF 행을 그대로 남긴다(§3.4).
3. `undecomposedAt`이 `yhr`에 미분해 ETF 1건 · `11000000`, `jdh`에 1건 · `5500000`, `hhj`에 0건 · `0`을 낸다.
4. 두 렌즈의 CTE 아래 쿼리 모양이 같다 — 집계·필터·조인이 렌즈와 무관하다(§1.5).
5. **두 렌즈 분기 모두 `account`를 조인하고 `user_id`를 건다.** 스코프가 CTE 안에 있어야 하위 단계가 빠뜨릴 자리가 없다(§A.3 불변식 5).

**검증 방법**
```bash
./gradlew test --tests '*LensPreservationTest'
```

- [ ] **Step 1: `etf_coverage` 미러를 추가한다**

`db/external/V3__etf_coverage_mirror.sql`을 새로 만든다. 데이터팀 소유이며 로컬·테스트 전용이라는 성격은 `instrument`와 같고, 번호는 폴더와 무관하게 그때의 다음 값이다(§A.2.5). **이미 적용된 마이그레이션은 고치지 않는다** — 내용을 바꾸면 Flyway가 체크섬 불일치로 거부한다.

```sql
CREATE TABLE IF NOT EXISTS etf_coverage (
    etf_instrument_id uuid PRIMARY KEY,
    state             text NOT NULL CHECK (state IN ('COVERED', 'UNAVAILABLE')),
    as_of             date
);
```

행을 넣지 않는다. **행이 없다는 것이 곧 "구성종목 미확보"이고**, 스펙 §3.4가 그 경우 "전개하지 않고 ETF 행을 그대로 남긴다"고 정한다. 즉 이번 범위의 `LOOK_THROUGH`는 스펙이 정의한 정상 경로를 탄다.

- [ ] **Step 2: 총합 보존 테스트를 먼저 쓴다**

```java
class LensPreservationTest {

    private static final LocalDate AS_OF = LocalDate.of(2026, 7, 27);

    /** 스펙 §9.1 렌즈 — 전개 후 Σ market_value가 전개 전과 일치한다. */
    @Test
    void 두_렌즈_모두_총합을_보존한다() {
        for (Lens lens : Lens.values()) {
            assertThat(aggregateMapper.sumMarketValueKrw(YHR, AS_OF, lens))
                    .as("%s 총합 보존", lens)
                    .isEqualByComparingTo("58000000");
        }
    }

    /** 스코프가 CTE 안에 있다 — 렌즈를 바꿔도 남의 자산이 들어오지 않는다(§3.8). */
    @Test
    void 두_렌즈_모두_스코프를_지킨다() {
        for (Lens lens : Lens.values()) {
            assertThat(aggregateMapper.sumMarketValueKrw(JDH, AS_OF, lens))
                    .isEqualByComparingTo("14000000");
            assertThat(aggregateMapper.sumMarketValueKrw(TEST_EMPTY, AS_OF, lens))
                    .isEqualByComparingTo("0");
        }
    }

    /**
     * 구성종목이 확보된 ETF는 미확보 분기에서 빠진다 — 전개 분기가 붙을 자리다(§A.9).
     * etf_coverage가 비어 있어 NOT EXISTS가 늘 참이므로, COVERED 행을 하나 넣어야
     * 이 조건이 실제로 도는지 확인된다.
     */
    @Test
    void 확보된_ETF는_미확보_분기에서_빠진다() {
        markCovered(TIGER);

        assertThat(etfCoverageMapper.undecomposedAt(YHR, AS_OF, LineFilter.NONE).count()).isZero();
        assertThat(aggregateMapper.sumMarketValueKrw(YHR, AS_OF, Lens.LOOK_THROUGH))
                .isEqualByComparingTo("47000000");
    }

    @Test
    void 미분해_ETF의_건수와_금액을_센다() {
        assertThat(etfCoverageMapper.undecomposedAt(YHR, AS_OF, LineFilter.NONE))
                .satisfies(u -> {
                    assertThat(u.count()).isEqualTo(1);
                    assertThat(u.marketValueKrw()).isEqualByComparingTo("11000000");
                });

        // jdh도 같은 ETF를 보유하지만 자기 몫만 센다
        assertThat(etfCoverageMapper.undecomposedAt(JDH, AS_OF, LineFilter.NONE).marketValueKrw())
                .isEqualByComparingTo("5500000");
    }
}
```

- [ ] **Step 3: 렌즈를 `<sql>` 조각으로 쓴다**

`src/main/resources/mapper/AggregateMapper.xml`에 둔다. 렌즈 선택이 `<choose>` 하나이고, 그 아래 조인·필터·집계는 렌즈와 무관하게 같은 모양으로 남는다(§1.5).

```xml
<!-- 렌즈 — 스펙 §3.4가 정의한 "입력도 라인 집합, 출력도 라인 집합인 변환 함수".
     출력 컬럼이 두 분기에서 동일하므로 하위 로직은 렌즈 적용 여부와 무관하다.

     스코프도 여기서 걸린다(§3.8) — 이 CTE가 내놓는 것이 이미 그 사용자의 세계라
     아래의 조인·필터·집계는 스코프를 다시 걸 필요도, 빠뜨릴 자리도 없다. -->
<sql id="targetLineColumns">
  pl.account_id, pl.instrument_id, pl.quantity,
  pl.cost_amount_local, pl.market_value_local, pl.cost_amount_krw, pl.market_value_krw
</sql>

<sql id="scopedLine">
  FROM position_line pl
  JOIN account owner ON owner.account_id = pl.account_id
 WHERE pl.as_of = #{asOf}
   AND owner.user_id = #{scope.userId}
</sql>

<sql id="targetLine">
  <choose>
    <when test="lens.name() == 'LOOK_THROUGH'">
      <!-- 구성종목이 확보된 ETF만 전개한다. etf_coverage에 COVERED 행이 없는 ETF는
           전개하지 않고 그대로 남긴다(§3.4). 기타 버킷에 넣지 않는다 —
           "ETF 내 비주식"과 뭉개지기 때문이다.
           전개 분기(ETF 평가금액 × 구성비중 + 기타 버킷 + 잔차 흡수)는 2단계 범위이며
           etf_constituent 조인으로 여기에 UNION ALL 된다. 그 분기도 이 조각을 쓴다. -->
      SELECT <include refid="targetLineColumns"/>
      <include refid="scopedLine"/>
        AND NOT EXISTS (SELECT 1 FROM etf_coverage c
                         WHERE c.etf_instrument_id = pl.instrument_id
                           AND c.state = 'COVERED')
    </when>
    <otherwise>
      <!-- DIRECT — 2단계를 건너뛰고 position_line이 그대로 3단계로 간다(§3.6). -->
      SELECT <include refid="targetLineColumns"/>
      <include refid="scopedLine"/>
    </otherwise>
  </choose>
</sql>
```

**`scopedLine`을 별도 조각으로 뽑은 이유.** 전개 분기가 `UNION ALL`로 붙을 때 스코프를 다시 써야 하는데, 손으로 옮겨 적으면 한쪽만 고치는 실수가 난다. 조각 하나를 `<include>`하면 두 분기가 같은 조건을 공유하고, 앞으로 붙을 세 번째 분기도 마찬가지다.

총합 보존을 확인할 수 있게 매퍼에 조회 메서드를 하나 둔다. 이것이 §9.1의 "전개 후 Σ market_value가 전개 전과 일치"를 검증 가능하게 만든다.

```xml
<select id="sumMarketValueKrw" resultType="java.math.BigDecimal">
  WITH target_line AS (<include refid="targetLine"/>)
  SELECT coalesce(sum(market_value_krw), 0) FROM target_line
</select>
```

- [ ] **Step 4: `EtfCoverageMapper`**

```xml
<!-- 전개되지 않은 ETF의 건수·평가금액과 종목 심볼 — CONSTITUENT_UNAVAILABLE notice 재료(§8.2).
     심볼은 종목 축의 행 key와 같은 값이라 화면이 행을 짚을 수 있다. -->
<select id="undecomposedAt" resultMap="undecomposedEtf">
  SELECT count(DISTINCT pl.instrument_id) AS count,
         coalesce(sum(pl.market_value_krw), 0) AS market_value_krw,
         array_agg(DISTINCT i.symbol) AS keys
    FROM position_line pl
    JOIN instrument i ON i.instrument_id = pl.instrument_id
    JOIN account acct ON acct.account_id = pl.account_id
   WHERE pl.as_of = #{asOf} AND acct.user_id = #{scope.userId}
     AND i.asset_class = 'ETF'
     AND NOT EXISTS (SELECT 1 FROM etf_coverage c
                      WHERE c.etf_instrument_id = pl.instrument_id
                        AND c.state = 'COVERED')
  <include refid="accountFilter"/>
</select>
```

이 쿼리는 `targetLine`을 거치지 않으므로 스코프를 직접 건다. **`position_line`에서 곧바로 읽는 쿼리는 전부 그렇다** — 매퍼 시그니처 테스트(Task 8)가 `UserScope`를 받지 않는 메서드를 잡아내 이런 자리를 빠뜨리지 않게 한다.

- [ ] **Step 5: 테스트 통과 → 커밋**

```bash
./gradlew test --tests '*LensPreservationTest'
git add -A && git commit -m "feat: 렌즈를 CTE로 — DIRECT 경로와 미확보 ETF 분기"
```

---

### Task 6: 집계 쿼리 (§3.6 3~4단계)

이 태스크가 계획의 중심이다. **저장은 한 종류, 화면은 묶는 기준만 바꾼다**가 여기서 한 개의 쿼리 빌더로 구현된다.

**Files:**
- Create: `query/aggregate/AxisSql.java` · `AxisFragment.java` · `AggregateMapper.java` · `AggregateRowDto.java` · `AggregateQueryRepository.java`
- Modify: `src/main/resources/mapper/AggregateMapper.xml` (Task 5의 렌즈 조각에 이어 붙인다)
- Test: `test/.../query/aggregate/AxisSqlTest.java` · `AggregateQueryRepositoryTest.java`

**Interfaces:**
- Consumes: Task 2 `AxisKey`·`MetricKey`·`Lens`, Task 3 `MeasureBundle`·`Aggregation`·`GroupNode`·`GroupKey`, Task 5 `targetLine` 조각
- Produces:
  - `String AxisSql.keyExpr(AxisKey)` · `String AxisSql.labelExpr(AxisKey)`
  - `List<AxisFragment> AxisSql.fragmentsOf(List<AxisKey>)` · `List<List<AxisFragment>> AxisSql.groupingSets(List<AxisFragment>)`
  - `List<AggregateRowDto> AggregateMapper.aggregate(...)`
  - `Aggregation AggregateQueryRepository.aggregate(UserScope scope, LocalDate asOf, List<AxisKey> groupBy, Lens lens, LineFilter filter)`

**완료 조건**
1. `groupBy = []`이면 전체 합계 1행만 나온다(요약).
2. `groupBy = [SECTOR]`이면 §C.6의 5행이 평가금액 내림차순으로 나오고 `현금`·`미분류` 폴백이 적용된다.
3. `groupBy = [ACCOUNT_TYPE, ACCOUNT]`이면 2단계 중첩이 나오고 **자식 합 = 부모**가 성립한다.
4. **모든 축 × 두 렌즈 조합에서 `Σ rows.market_value_krw = responseTotal`이 성립한다.**
5. `기타` 버킷은 금액과 무관하게 항상 맨 끝이다.
6. 집계 SELECT에 비율 지표가 없다 — `<sql id="measures">`에 `additive = false`인 지표가 등장하지 않는다(불변식 1).
7. 매퍼가 `String` 축을 받는 경로가 없다 — `AxisFragment`만 받는다.
8. **모든 축 × 두 렌즈 조합에서 사용자마다 다른 값이 나온다** — §C.12의 표가 재현된다. `test_empty`는 어느 조합에서도 빈 결과다.

**검증 방법**
```bash
./gradlew test --tests '*AxisSqlTest' --tests '*AggregateQueryRepositoryTest'
```

- [ ] **Step 1: 총합 보존 테스트를 먼저 쓴다**

```java
class AggregateQueryRepositoryTest {

    private static final LocalDate AS_OF = LocalDate.of(2026, 7, 27);

    /** 스펙 §8.3 — Σ rows.market_value_krw = total.total_assets_krw가 항상 성립한다. */
    @Test
    void 모든_축과_렌즈_조합에서_행_합이_전체_합계와_같다() {
        for (AxisKey axis : AxisKey.values()) {
            if (!axis.enabled()) continue;
            for (Lens lens : Lens.values()) {
                Aggregation agg = repository.aggregate(YHR, AS_OF, List.of(axis), lens, LineFilter.NONE);

                BigDecimal rowSum = agg.rows().stream()
                        .map(n -> n.measures().total().marketValueKrw())
                        .reduce(BigDecimal.ZERO, BigDecimal::add);

                assertThat(rowSum).as("axis=%s lens=%s", axis.key(), lens)
                        .isEqualByComparingTo(agg.responseTotal().total().marketValueKrw())
                        .isEqualByComparingTo("58000000");
            }
        }
    }

    /** 스펙 §6.1 폴백 — CASH는 현금, sector가 null인 종목은 미분류로 모인다. */
    @Test
    void 섹터_축의_폴백과_정렬() {
        Aggregation agg = repository.aggregate(YHR, AS_OF, List.of(AxisKey.SECTOR), Lens.DIRECT, LineFilter.NONE);

        assertThat(agg.rows()).extracting(n -> n.key().label())
                .containsExactly("반도체", "소프트웨어", "미분류", "IT서비스", "현금");
        assertThat(agg.rows()).extracting(n -> n.measures().total().marketValueKrw().longValue())
                .containsExactly(23_240_000L, 12_900_000L, 11_000_000L, 6_160_000L, 4_700_000L);
        assertThat(agg.rows().get(4).key().key()).isEqualTo("CASH");
    }

    /** 스펙 §8.3 — group_by가 2단계면 중첩되고 소계는 서버가 계산한다. */
    @Test
    void 계좌유형_소계가_자식_합과_같다() {
        Aggregation agg = repository.aggregate(YHR, AS_OF,
                List.of(AxisKey.ACCOUNT_TYPE, AxisKey.ACCOUNT), Lens.DIRECT, LineFilter.NONE);

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

    @Test
    void group_by가_비면_전체_합계만_나온다() {
        Aggregation agg = repository.aggregate(YHR, AS_OF, List.of(), Lens.DIRECT, LineFilter.NONE);
        MeasureBundle t = agg.responseTotal();

        assertThat(agg.rows()).isEmpty();
        assertThat(Derived.totalAssetsKrw(t)).isEqualByComparingTo("58000000");
        assertThat(Derived.securitiesValueKrw(t)).isEqualByComparingTo("53300000");
        assertThat(Derived.depositKrw(t)).isEqualByComparingTo("4700000");
        assertThat(Derived.costAmountKrw(t)).isEqualByComparingTo("48800000");
        assertThat(Derived.unrealizedPnlKrw(t)).isEqualByComparingTo("4500000");
        assertThat(Derived.unrealizedPnlPct(t)).isEqualByComparingTo("9.2");
        assertThat(Derived.cashRatioPct(t, agg.weightDenominator())).isEqualByComparingTo("8.1");
        assertThat(Derived.instrumentCount(t)).isEqualTo(6);
        assertThat(Derived.accountCount(t)).isEqualTo(4);
    }

    /** 불변식 3 — 통화 집합이 그룹마다 따라온다. */
    @Test
    void 그룹의_통화_집합이_함께_나온다() {
        Aggregation agg = repository.aggregate(YHR, AS_OF, List.of(AxisKey.SECTOR), Lens.DIRECT, LineFilter.NONE);

        assertThat(node(agg, "IT서비스").measures().currencies().single()).contains(CurrencyCode.USD);
        assertThat(node(agg, "소프트웨어").measures().currencies().single()).isEmpty();
    }

    /** 필터는 마스터 조인 뒤에 적용된다(§3.6 3.5단계). */
    @Test
    void 시장_필터가_동작한다() {
        Aggregation agg = repository.aggregate(YHR, AS_OF, List.of(AxisKey.INSTRUMENT), Lens.DIRECT,
                new LineFilter(Set.of(), Set.of(), Set.of(Market.US), Set.of()));

        assertThat(agg.rows()).extracting(n -> n.key().key())
                .containsExactlyInAnyOrder("AAPL", "MSFT", "CASH-USD");
    }

    /** 같은 요청이 사용자마다 다른 값을 낸다. 겹치는 종목이 합쳐지지 않는다. */
    @Test
    void 같은_요청이_사용자마다_다른_값을_낸다() {
        assertThat(row(JDH, AxisKey.INSTRUMENT, "005930").measures().total().quantity())
                .isEqualByComparingTo("100");
        assertThat(row(YHR, AxisKey.INSTRUMENT, "005930").measures().total().quantity())
                .isEqualByComparingTo("200");

        assertThat(row(JDH, AxisKey.SECTOR, "반도체").measures().total().marketValueKrw())
                .isEqualByComparingTo("7120000");
        assertThat(row(YHR, AxisKey.SECTOR, "반도체").measures().total().marketValueKrw())
                .isEqualByComparingTo("23240000");
    }

    /** 계좌가 없는 사용자는 어느 조합에서도 빈 결과다 — empty_reason의 재료다. */
    @Test
    void 계좌가_없으면_모든_조합이_비어_있다() {
        for (AxisKey axis : AxisKey.values()) {
            if (!axis.enabled()) continue;
            for (Lens lens : Lens.values()) {
                Aggregation agg = repository.aggregate(
                        TEST_EMPTY, AS_OF, List.of(axis), lens, LineFilter.NONE);

                assertThat(agg.rows()).as("axis=%s lens=%s", axis.key(), lens).isEmpty();
                assertThat(agg.responseTotal().total().marketValueKrw())
                        .isEqualByComparingTo(BigDecimal.ZERO);
            }
        }
    }
}
```

- [ ] **Step 2: 실행해 실패 확인**

Run: `./gradlew test --tests '*AggregateQueryRepositoryTest'` → 컴파일 실패.

- [ ] **Step 3: `AxisSql` — 축을 SQL 식으로 옮긴다**

카탈로그(§A.4.1)의 축 표와 나란히 놓고 검토하는 것이 이 클래스의 목적이다. 분류 축의 폴백(§6.1)이 `CASE` 식에 나타난다.

```java
package com.stockproject.portfolio.query.aggregate;

import com.stockproject.portfolio.catalog.AxisKey;

import java.util.Map;

/** 축 → SQL 식. 스펙 §6.1의 축 표와 폴백 규칙을 그대로 옮긴 것이다.
 *  바깥 쿼리의 별칭은 계좌가 acct, 종목이 i다. */
public final class AxisSql {

    private static final Map<AxisKey, String> KEY_EXPR = Map.of(
        AxisKey.ACCOUNT,      "acct.account_id::text",
        AxisKey.ACCOUNT_TYPE, "acct.account_type",
        AxisKey.INSTRUMENT,   "i.symbol",
        AxisKey.SECTOR,       "CASE WHEN i.asset_class = 'CASH' THEN 'CASH' "
                            + "ELSE coalesce(i.sector, 'UNCLASSIFIED') END",
        AxisKey.MARKET,       "CASE WHEN i.asset_class = 'CASH' THEN 'CASH' ELSE i.market END",
        AxisKey.CURRENCY,     "i.currency",
        AxisKey.ASSET_CLASS,  "CASE WHEN i.asset_class = 'CASH' THEN 'CASH' ELSE i.asset_class END",
        AxisKey.IS_LEVERAGED, "CASE WHEN i.asset_class = 'CASH' THEN 'CASH' "
                            + "WHEN i.is_leveraged IS NULL THEN 'UNCLASSIFIED' "
                            + "ELSE i.is_leveraged::text END");

    private static final Map<AxisKey, String> LABEL_EXPR = Map.of(
        AxisKey.ACCOUNT,      "acct.label",
        AxisKey.ACCOUNT_TYPE, "CASE acct.account_type WHEN 'GENERAL' THEN '일반' ELSE '연금' END",
        AxisKey.INSTRUMENT,   "i.name",
        AxisKey.SECTOR,       "CASE WHEN i.asset_class = 'CASH' THEN '현금' "
                            + "ELSE coalesce(i.sector, '미분류') END",
        AxisKey.MARKET,       "CASE WHEN i.asset_class = 'CASH' THEN '현금' "
                            + "WHEN i.market = 'KR' THEN '국내' ELSE '미국' END",
        AxisKey.CURRENCY,     "i.currency",
        AxisKey.ASSET_CLASS,  "CASE i.asset_class WHEN 'STOCK' THEN '주식' "
                            + "WHEN 'ETF' THEN 'ETF' ELSE '현금' END",
        AxisKey.IS_LEVERAGED, "CASE WHEN i.asset_class = 'CASH' THEN '현금' "
                            + "WHEN i.is_leveraged IS NULL THEN '미분류' "
                            + "WHEN i.is_leveraged THEN '레버리지' ELSE '일반' END");

    private AxisSql() { }

    public static String keyExpr(AxisKey axis)   { return KEY_EXPR.get(axis); }
    public static String labelExpr(AxisKey axis) { return LABEL_EXPR.get(axis); }
}
```

- [ ] **Step 4: `AxisFragment` — 매퍼에 넘기는 유일한 SQL 조각 타입**

축 식은 값 바인딩(`#{}`)이 아니라 문자열 치환(`${}`)으로 들어간다. 컬럼 이름과 표현식은 바인딩할 수 없기 때문이다. **그래서 매퍼가 `String`을 받는 경로를 만들지 않는다** — `AxisKey`에서만 만들어지는 `AxisFragment`를 받는다.

```java
package com.stockproject.portfolio.query.aggregate;

/**
 * 매퍼의 ${}에 들어가는 유일한 타입. 생성 경로가 AxisSql.fragmentsOf 하나뿐이고
 * 그 입력이 카탈로그 대조를 통과한 AxisKey라, 요청 문자열이 SQL에 닿지 않는다.
 */
public record AxisFragment(int index, String keyExpr, String labelExpr) { }
```

```java
    /** 요청 축 목록 → SQL 조각. 매퍼는 이 타입만 받는다. */
    public static List<AxisFragment> fragmentsOf(List<AxisKey> axes) {
        List<AxisFragment> out = new ArrayList<>();
        for (int i = 0; i < axes.size(); i++) {
            AxisKey axis = axes.get(i);
            if (!axis.enabled()) throw new IllegalArgumentException("비활성 축: " + axis.key());
            out.add(new AxisFragment(i, keyExpr(axis), labelExpr(axis)));
        }
        return out;
    }

    /** GROUPING SETS 조합 — 잎 · 소계 · 전체 합계. */
    public static List<List<AxisFragment>> groupingSets(List<AxisFragment> axes) {
        List<List<AxisFragment>> sets = new ArrayList<>();
        for (int depth = axes.size(); depth > 0; depth--) sets.add(axes.subList(0, depth));
        sets.add(List.of());                      // ()  — 전체 합계
        return sets;
    }
```

- [ ] **Step 5: 집계 매퍼 XML**

```xml
<!-- 측정값. CASH 분리를 FILTER 절이 하며, 스펙 §6.2의 CASH 열이 여기 그대로 보인다.
     비율은 이 목록에 없다 — 파생 지표는 Derived가 집계 후에 만든다(불변식 1). -->
<sql id="measures">
  sum(t.quantity)           FILTER (WHERE i.asset_class &lt;&gt; 'CASH') AS secQuantity,
  sum(t.cost_amount_local)  FILTER (WHERE i.asset_class &lt;&gt; 'CASH') AS secCostLocal,
  sum(t.market_value_local) FILTER (WHERE i.asset_class &lt;&gt; 'CASH') AS secMarketLocal,
  sum(t.cost_amount_krw)    FILTER (WHERE i.asset_class &lt;&gt; 'CASH') AS secCostKrw,
  sum(t.market_value_krw)   FILTER (WHERE i.asset_class &lt;&gt; 'CASH') AS secMarketKrw,
  sum(t.quantity)           FILTER (WHERE i.asset_class =  'CASH') AS cashQuantity,
  sum(t.cost_amount_local)  FILTER (WHERE i.asset_class =  'CASH') AS cashCostLocal,
  sum(t.market_value_local) FILTER (WHERE i.asset_class =  'CASH') AS cashMarketLocal,
  sum(t.cost_amount_krw)    FILTER (WHERE i.asset_class =  'CASH') AS cashCostKrw,
  sum(t.market_value_krw)   FILTER (WHERE i.asset_class =  'CASH') AS cashMarketKrw,
  array_agg(DISTINCT i.currency)                                   AS currencies,
  count(DISTINCT i.instrument_id) FILTER (WHERE i.asset_class &lt;&gt; 'CASH') AS instrumentCount,
  count(DISTINCT t.account_id)                                     AS accountCount
</sql>

<!-- 필터 — 스펙 §3.6 3.5단계. 마스터 조인 뒤에 적용된다. -->
<sql id="filters">
  <where>
    <if test="filter.accountIds.size() > 0">
      AND acct.account_id IN
      <foreach item="id" collection="filter.accountIds" open="(" separator="," close=")">#{id}</foreach>
    </if>
    <if test="filter.accountTypes.size() > 0">
      AND acct.account_type IN
      <foreach item="v" collection="filter.accountTypes" open="(" separator="," close=")">#{v}</foreach>
    </if>
    <if test="filter.markets.size() > 0">
      AND i.market IN
      <foreach item="v" collection="filter.markets" open="(" separator="," close=")">#{v}</foreach>
    </if>
    <if test="filter.assetClasses.size() > 0">
      AND i.asset_class IN
      <foreach item="v" collection="filter.assetClasses" open="(" separator="," close=")">#{v}</foreach>
    </if>
  </where>
</sql>

<!-- 스펙 §3.6 2~4단계를 한 쿼리로. -->
<select id="aggregate" resultType="AggregateRowDto">
  WITH target_line AS (<include refid="targetLine"/>)
  SELECT
  <foreach item="ax" collection="axes">
    ${ax.keyExpr}   AS key${ax.index},
    ${ax.labelExpr} AS label${ax.index},
    grouping(${ax.keyExpr}) AS g${ax.index},
  </foreach>
  <include refid="measures"/>
    FROM target_line t
    JOIN account    acct ON acct.account_id    = t.account_id
    JOIN instrument i    ON i.instrument_id    = t.instrument_id
  <include refid="filters"/>
  GROUP BY GROUPING SETS (
    <foreach item="set" collection="groupingSets" separator=", ">
      (<foreach item="ax" collection="set" separator=", ">${ax.keyExpr}, ${ax.labelExpr}</foreach>)
    </foreach>
  )
</select>
```

빈 조합 `()`는 `groupingSets`의 빈 리스트가 그대로 렌더링해 준다. `map-underscore-to-camel-case`가 켜져 있어도 별칭을 카멜케이스로 준 것은 `AggregateRowDto`의 필드명과 직접 맞추기 위해서다.

**`AggregateRowDto`는 record가 아니라 세터를 가진 POJO다.** 요청 축이 0~2개라 `key1`·`label1`·`g1` 컬럼이 아예 없는 조합이 있고, 생성자 매핑은 없는 컬럼을 채울 방법이 없다. 세터 자동 매핑이면 나온 컬럼만 채워지고 나머지는 비어 있어 축 개수가 그대로 표현된다. `grouping()` 기본값을 `1`로 두어 **없는 축은 "묶이지 않은 축"**이 되고, `depth()`가 0의 개수로 그 행의 깊이를 낸다.

`array_agg`가 내는 `text[]`는 `StringArrayTypeHandler`가 `String[]`으로 받는다 — `UuidTypeHandler`와 같은 이유로 MyBatis 기본 등록에 없다.

`AggregateMapper` 인터페이스:

```java
@Mapper
public interface AggregateMapper {

    List<AggregateRowDto> aggregate(@Param("scope") UserScope scope,
                                    @Param("asOf") LocalDate asOf,
                                    @Param("axes") List<AxisFragment> axes,
                                    @Param("groupingSets") List<List<AxisFragment>> groupingSets,
                                    @Param("lens") Lens lens,
                                    @Param("filter") LineFilter filter);

    BigDecimal sumMarketValueKrw(@Param("scope") UserScope scope,
                                 @Param("asOf") LocalDate asOf,
                                 @Param("lens") Lens lens);
}
```

**매개변수 타입이 이 설계의 안전장치다.** `axes`가 `List<AxisFragment>`라 호출자가 임의 문자열을 넣을 수 없고, `AxisFragment`는 `AxisSql.fragmentsOf(List<AxisKey>)`만 만든다. `scope`가 첫 자리에 고정인 것도 같은 성격이다 — 빠뜨리면 컴파일되지 않고, 리플렉션 테스트(Task 8)가 자리까지 검사한다.

- [ ] **Step 6: `AggregateQueryRepository` — 실행하고 트리로 조립**

`grouping()` 값이 그 행의 깊이를 알려준다. `g0 = 1`이면 전체 합계, `g0 = 0 && g1 = 1`이면 1단계 소계, 둘 다 `0`이면 잎이다. 잎을 부모 키로 묶어 `GroupNode` 트리를 만들고, 정렬은 §3.6 6단계대로 **평가금액 내림차순 · 기타 버킷 맨 끝**으로 Java가 한다.

```java
    private static final Comparator<GroupNode> ORDER =
            Comparator.<GroupNode, Boolean>comparing(n -> n.key().other())
                    .thenComparing(n -> n.measures().total().marketValueKrw(), Comparator.reverseOrder())
                    .thenComparing(n -> n.key().key());
```

`array_agg(DISTINCT currency)`는 `String[]`으로 오므로 `CurrencySet`으로 옮긴다. `FILTER`가 걸러 낸 `NULL`은 `Measures.ZERO` 쪽으로 접는다.

- [ ] **Step 7: 조각 생성 단위 테스트**

```java
class AxisSqlTest {

    /** 불변식 1 — 비율 지표는 집계 SELECT에 들어갈 수 없다. */
    @Test
    void 집계_SELECT에_비율_지표가_없다() throws Exception {
        String xml = Files.readString(Path.of("src/main/resources/mapper/AggregateMapper.xml"));
        int measures = xml.indexOf("<sql id=\"measures\">");
        String block = xml.substring(measures, xml.indexOf("</sql>", measures));

        assertThat(block).doesNotContain("weight_pct", "unrealized_pnl_pct", "cash_ratio_pct",
                                         "realized_pnl_pct", "daily_change_pct");
        assertThat(Metric.of(MetricKey.WEIGHT_PCT).additivity()).isEqualTo(Additivity.NON_ADDITIVE);
    }

    @Test
    void 비활성_축은_거부한다() {
        assertThatThrownBy(() -> AxisSql.fragmentsOf(List.of(AxisKey.IS_LEVERAGED)))
                .isInstanceOf(IllegalArgumentException.class);
    }

    /** 스펙 §8.3 — 2단계 축이면 잎·소계·전체 합계 세 조합이 나온다. */
    @Test
    void GROUPING_SETS_조합이_깊이만큼_생긴다() {
        List<AxisFragment> axes = AxisSql.fragmentsOf(
                List.of(AxisKey.ACCOUNT_TYPE, AxisKey.ACCOUNT));

        assertThat(AxisSql.groupingSets(axes)).hasSize(3);
        assertThat(AxisSql.groupingSets(axes).get(2)).isEmpty();      // () — 전체 합계
        assertThat(AxisSql.groupingSets(AxisSql.fragmentsOf(List.of()))).containsExactly(List.of());
    }

    /** 매퍼에 임의 문자열을 넘길 수 없다는 것을 시그니처로 고정한다. */
    @Test
    void 매퍼는_문자열_축을_받지_않는다() {
        assertThat(AggregateMapper.class.getMethods())
                .filteredOn(m -> m.getName().equals("aggregate"))
                .allSatisfy(m -> assertThat(m.getParameterTypes()).doesNotContain(String.class));
    }
}
```

`두_렌즈의_쿼리는_CTE만_다르다`는 문자열 비교 대신 **결과로 확인한다** — 렌즈를 바꿔도 `total`이 같다는 것이 §1.5가 실제로 요구하는 바다. 그 검증은 Task 12의 교차 검증에 있다.

- [ ] **Step 8: 테스트 통과 → 커밋**

```bash
./gradlew test --tests '*Aggregate*'
git add -A && git commit -m "feat: 집계 쿼리 — GROUPING SETS로 행·소계·합계를 한 스캔에서"
```

---

### Task 7: 응답 조립 — 봉투 · notice 16종 · empty_reason · 통화 · lens_safe

**Files:**
- Create: `api/dto/Envelope.java` · `NoticeDto.java` · `RowDto.java` · `SnapshotViewData.java`
- Create: `view/assembly/RowValuePolicy.java` · `CurrencyDisplayPolicy.java` · `NoticeCollector.java` · `NoticeCode.java` · `EmptyReason.java` · `EmptyReasonResolver.java` · `SnapshotResponseAssembler.java`
- Test: `test/.../view/assembly/RowValuePolicyTest.java` · `CurrencyDisplayPolicyTest.java` · `NoticeCollectorTest.java` · `EmptyReasonResolverTest.java`

**Interfaces:**
- Consumes: Task 2 카탈로그, Task 3 `Derived`·`Aggregation`, Task 5 `UndecomposedEtf`, Task 6 집계 결과
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

    /**
     * 불변식 3 — 판정자는 묶음의 통화 집합 하나다. 축 이름을 보지 않는다(스펙 §3.7).
     * 섹터 IT서비스(AAPL 단독)처럼 우연히 단일 통화인 묶음도 병기된다.
     */
    @Test
    void 단일_USD_묶음이면_축과_무관하게_병기한다() {
        assertThat(policy.localOf(usdOnlyBundle()))
                .get().extracting(LocalMoney::currency).isEqualTo(CurrencyCode.USD);
    }

    @Test
    void 통화가_섞이면_병기하지_않는다() {
        assertThat(policy.localOf(mixedBundle())).isEmpty();
    }

    /** 원화가 곧 현지 통화이므로 병기가 중복이다. */
    @Test
    void 단일_KRW_묶음에는_병기하지_않는다() {
        assertThat(policy.localOf(krwOnlyBundle())).isEmpty();
    }

    /** 판정자가 통화 집합 하나임을 고정한다 — 축을 받는 오버로드를 만들지 않는다. */
    @Test
    void 축을_인자로_받는_오버로드가_없다() {
        assertThat(CurrencyDisplayPolicy.class.getMethods())
                .filteredOn(m -> m.getName().equals("localOf"))
                .allSatisfy(m -> assertThat(m.getParameterCount()).isEqualTo(1));
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
 * 판정자는 묶음의 통화 집합 하나다. 축 이름을 하드코딩하면 축이 늘 때마다 고쳐야 하므로
 * §3.7이 판정을 조회 시점 런타임으로 못 박았다.
 */
@Component
public class CurrencyDisplayPolicy {

    public Optional<LocalMoney> localOf(MeasureBundle bundle) {
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
        UndecomposedEtf undecomposed,
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
                .containsExactly("FX_APPLIED", "STALE_ACCOUNTS");   // 선언 순서대로 실린다
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
 * 판정 순서를 고정한다: NO_ACCOUNTS → NO_HOLDINGS
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
2. `rows` — `agg.rows()`를 `RowDto`로 바꾼다. 지표는 `RowValuePolicy.rowMetrics(...)`가 결정하고, 현지 통화는 `CurrencyDisplayPolicy.localOf(node.measures())`가 결정한다(축을 넘기지 않는다 — 불변식 3). 자식이 있으면 재귀.
3. `lens == LOOK_THROUGH`이면 `omittedRowMetrics`를 `AssemblyContext`에 넣어 `LENS_METRICS_OMITTED`가 뜨게 한다.
4. `accounts` 뷰이면 자식 노드에 `rowFields`(`link_state`·`last_collection`·`last_synced_at`·`source_as_of`·`is_carried_forward`)를, `positions` 뷰이면 `market`을 더한다. **계좌유형 그룹 노드에는 붙이지 않는다** — 접힌 헤더의 경고 수는 화면이 자식 행에서 센다.

`source_as_of`와 `is_carried_forward`는 스펙 §7.4의 두 번째 층이다. 전역 배너(`STALE_ACCOUNTS`)가 "몇 개가 낡았다"까지만 말하므로, 어느 계좌인지는 행이 가리킨다. 한 계좌 안에서 종목마다 값이 갈리면 **낡은 쪽을 대표로 잡는다** — `min(source_as_of)` · `bool_or(is_carried_forward)`. 일부만 이월된 계좌를 최신으로 보이게 하면 낡은 값이 숨는다.

- [ ] **Step 9: 테스트 통과 → 커밋**

```bash
./gradlew test --tests '*view.assembly.*'
git add -A && git commit -m "feat: 응답 조립 — 봉투 · notice 16종 · empty_reason · 통화 · lens_safe"
```

---

### Task 8: 인증 — 로그인 · JWT · 스코프 주입 (§8.8 · §3.8)

앞의 태스크들이 `UserScope`를 파라미터로 받아 왔다. 이 태스크가 **그 값이 어디서 오는지**를 정하고, 요청이 그것을 고를 수 없게 만든다.

**Files:**
- Create: `auth/AppUser.java` · `AppUserMapper.java` · `JwtCodec.java` · `JwtProperties.java`
- Create: `auth/SecurityConfig.java` · `JwtAuthenticationFilter.java` · `UserScopeArgumentResolver.java`
- Create: `auth/AccountOwnershipGuard.java` · `AuthController.java`
- Create: `auth/dto/LoginRequest.java` · `TokenResponse.java` · `MeResponse.java`
- Modify: `build.gradle.kts` (`spring-boot-starter-security` · `jjwt`)
- Create: `api/ApiExceptionHandler.java` · `api/ApiError.java` (`401` · `403`. 나머지 코드는 뒤에서 더한다)
- Test: `test/.../auth/JwtCodecTest.java` · `LoginApiTest.java` · `ScopeSignatureTest.java`
- Modify: `test/.../ArchitectureRulesTest.java` (불변식 5)

**Interfaces:**
- Consumes: Task 4의 `UserScope`, Task 1의 `app_user` 테이블
- Produces:
  - `String JwtCodec.issue(UUID userId)` · `Optional<UUID> JwtCodec.verify(String token)`
  - `Optional<AppUser> AppUserMapper.findByEmail(String email)`
  - `void AccountOwnershipGuard.check(UserScope scope, Set<UUID> accountIds)` — 아니면 `ForbiddenAccountException`
  - 컨트롤러 메서드가 `UserScope`를 파라미터로 선언하면 리졸버가 토큰에서 채워 준다

**완료 조건**
1. `POST /auth/login`이 올바른 자격으로 `200`과 `access_token` · `expires_at`을 낸다.
2. 잘못된 비밀번호와 없는 이메일이 **같은 응답**을 낸다 — `401 INVALID_CREDENTIALS`(§8.8).
3. 토큰 없이 뷰 엔드포인트를 부르면 `401 UNAUTHENTICATED`. 만료·변조 토큰도 같다.
4. `GET /auth/me`가 토큰 주인의 `user_id` · `email` · `display_name`을 낸다.
5. 남의 계좌를 `?account=`로 넣으면 `403 FORBIDDEN_ACCOUNT`. **빈 결과가 아니다.**
6. `ScopeSignatureTest` — 사용자 소유 테이블을 읽는 매퍼 메서드가 전부 `UserScope`를 **첫 파라미터**로 받는다.
7. `ArchitectureRulesTest` — `api`·`auth` 패키지의 핸들러에 `user`·`user_id` 이름의 `@RequestParam`·`@PathVariable`이 없다.
8. 비밀번호 원문이 로그·응답 어디에도 나오지 않는다.

**검증 방법**
```bash
./gradlew test --tests '*auth.*' --tests '*ArchitectureRulesTest'

TOKEN=$(curl -s localhost:8080/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"yhr@a.com","password":"…"}' | jq -r .access_token)
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/portfolio/views/summary          # 401
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/portfolio/views/summary \
  -H "Authorization: Bearer $TOKEN"                                                      # 200
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
  'localhost:8080/portfolio/views/summary?account=20000000-0000-0000-0000-000000000005'  # 403
```

- [ ] **Step 1: 의존성과 설정**

```kotlin
implementation("org.springframework.boot:spring-boot-starter-security")
implementation("io.jsonwebtoken:jjwt-api:0.12.6")
runtimeOnly("io.jsonwebtoken:jjwt-impl:0.12.6")
runtimeOnly("io.jsonwebtoken:jjwt-jackson:0.12.6")
testImplementation("org.springframework.security:spring-security-test")
```

```yaml
portfolio:
  auth:
    # HS256 서명키. 운영에서는 환경변수로만 주입한다.
    secret: ${JWT_SECRET:local-development-secret-key-at-least-32-bytes}
    ttl: PT12H
```

기본값을 둔 것은 로컬에서 바로 뜨게 하기 위해서이고, `.env.example`과 README에 운영 주입을 적는다. 32바이트 미만이면 `JwtCodec`이 기동 시점에 거부한다 — 짧은 키로 서명하면 HS256이 의미를 잃는다.

- [ ] **Step 2: 로그인 실패가 구분되지 않는 것을 테스트로 먼저 고정한다**

```java
    /** 스펙 §8.8 — 가입 여부가 응답으로 새지 않는다. */
    @Test
    void 없는_이메일과_틀린_비밀번호가_같은_응답을_낸다() throws Exception {
        var noSuchUser = login("nobody@a.com", "whatever");
        var wrongPassword = login("yhr@a.com", "whatever");

        assertThat(noSuchUser.getStatus()).isEqualTo(401).isEqualTo(wrongPassword.getStatus());
        assertThat(noSuchUser.getContentAsString()).isEqualTo(wrongPassword.getContentAsString());
    }

    @Test
    void 비밀번호가_응답에_나오지_않는다() throws Exception {
        assertThat(login("yhr@a.com", "…").getContentAsString())
                .doesNotContain("password", "hash");
    }
```

응답 본문까지 같은지 보는 이유는 상태 코드만 맞추고 메시지가 갈리는 경우를 잡기 위해서다.

- [ ] **Step 3: `JwtCodec` · `AppUserMapper` · `AuthController`**

`JwtCodec`은 `sub`·`iat`·`exp`만 싣는다. 계좌 목록을 싣지 않는 이유는 §8.8에 있다 — 계좌는 바뀌고 토큰은 고정이다.

```java
@Component
public class JwtCodec {
    public String issue(UUID userId) { /* sub = userId, exp = now + ttl */ }
    public Optional<UUID> verify(String token) { /* 서명·만료 실패는 Optional.empty() */ }
}
```

`AuthController`는 두 엔드포인트뿐이다. 로그인은 `AppUserMapper.findByEmail` → `BCryptPasswordEncoder.matches` → 발급이며, **사용자가 없을 때도 더미 해시로 한 번 비교한다** — 존재하지 않는 이메일이 빨리 실패해 응답 시간으로 가입 여부가 새는 것을 막는다.

- [ ] **Step 4: 필터와 스코프 주입**

`JwtAuthenticationFilter`가 `Authorization` 헤더를 읽어 `UUID`를 꺼내고, `UserScopeArgumentResolver`가 그것을 컨트롤러 파라미터로 넘긴다.

```java
@GetMapping("/views/summary")
public Envelope<SnapshotViewData> summary(UserScope scope, @RequestParam ... ) { }
```

**컨트롤러가 스코프를 "받는" 것처럼 보이지만 요청은 그 값을 정할 수 없다.** 리졸버가 인증 컨텍스트에서만 만들고, 요청 파라미터를 보지 않는다. 이 성질을 ArchUnit이 지킨다.

```java
    /** 불변식 5 — 사용자 ID는 요청에서 오지 않는다(§8.8). */
    @ArchTest
    static final ArchRule 핸들러는_사용자_ID를_파라미터로_받지_않는다 =
            noMethods().that().areDeclaredInClassesThat().resideInAPackage("..api..")
                    .should(haveRequestBoundParameterNamed("user", "userId", "user_id"));
```

`SecurityConfig`는 `POST /auth/login`만 열고 나머지를 막는다. 세션을 쓰지 않으므로 `STATELESS`이고 CSRF는 끈다 — 쿠키를 쓰지 않아 CSRF의 전제가 성립하지 않는다.

- [ ] **Step 5: 매퍼 시그니처 테스트**

불변식 5의 두 번째 겹이다. 새 매퍼가 늘어도 스코프를 빠뜨리면 여기서 잡힌다.

```java
/**
 * 사용자 소유 테이블을 읽는 매퍼는 UserScope를 첫 파라미터로 받는다.
 * 빠뜨리면 다른 사용자의 자산이 결과에 섞이고, 그 사실이 값으로는 잘 드러나지 않는다.
 */
class ScopeSignatureTest {

    @Test
    void 스코프_없는_조회_경로가_없다() {
        // query 패키지의 매퍼는 전부 사용자 소유 테이블을 읽는다.
        // 참조 데이터만 읽는 매퍼가 생기면 그때 다른 패키지로 가른다.
        List<Class<?>> mappers = new ClassPathScanner()
                .findInterfacesAnnotatedWith(Mapper.class, "com.stockproject.portfolio.query");

        assertThat(mappers).isNotEmpty();
        for (Class<?> mapper : mappers) {
            for (Method m : mapper.getDeclaredMethods()) {
                assertThat(m.getParameterTypes())
                        .as("%s.%s", mapper.getSimpleName(), m.getName())
                        .isNotEmpty()
                        .satisfies(types -> assertThat(types[0]).isEqualTo(UserScope.class));
            }
        }
    }
}
```

**목록을 손으로 유지하지 않고 패키지를 훑는다.** 이후 태스크가 매퍼를 더 만들어도 자동으로 대상이 되며, 목록에 추가하는 것을 잊어 검사에서 빠지는 일이 없다. 인증 자체를 담당하는 `AppUserMapper`가 `auth` 패키지에 있어 대상에서 빠지는 것도 의도한 것이다 — 그것은 스코프를 **만드는** 쪽이라 받을 스코프가 없다.

- [ ] **Step 6: 계좌 소유 검사**

```java
/** 스펙 §9.3 — 계좌 필터 값은 인증 주체 소유여야 한다. 빈 결과가 아니라 403이다. */
@Component
public class AccountOwnershipGuard {
    public void check(UserScope scope, Set<UUID> accountIds) {
        if (accountIds.isEmpty()) return;
        Set<UUID> owned = accountRepository.findAll(scope).stream().map(AccountRow::id).collect(toSet());
        if (!owned.containsAll(accountIds)) throw new ForbiddenAccountException();
    }
}
```

`RequestValidator`가 카탈로그 대조를 마친 뒤 이 검사를 부른다. 순서가 이런 이유는 형식이 틀린 값(`400`)과 남의 것을 가리키는 값(`403`)이 다른 실패이기 때문이다.

- [ ] **Step 7: 테스트 통과 → 커밋**

```bash
./gradlew test --tests '*auth.*' --tests '*ArchitectureRulesTest'
git add -A && git commit -m "feat: 인증 — 로그인·JWT·사용자 스코프 주입"
```

---

### Task 9: 스냅샷 4개 뷰 엔드포인트와 요청 검증

**Files:**
- Create: `view/SnapshotViewService.java` · `validation/RequestValidator.java` · `api/ViewController.java` · `api/CatalogController.java` · `api/dto/CatalogDto.java`
- Modify: `api/ApiExceptionHandler.java` (요청 검증 실패와 팩트 정합성 위반을 더한다)
- Test: `test/.../api/SnapshotViewApiTest.java` · `test/.../validation/RequestValidatorTest.java`

**Interfaces:**
- Consumes: Task 4 저장소·검증기, Task 5 렌즈, Task 6 엔진, Task 7 조립기, Task 8 스코프 주입·소유 검사
- Produces:
  - `Envelope<SnapshotViewData> SnapshotViewService.summary(UserScope, Lens miniChartLens, AxisKey miniChartAxis)`
  - `Envelope<SnapshotViewData> SnapshotViewService.positions(UserScope, Lens, LineFilter)`
  - `Envelope<SnapshotViewData> SnapshotViewService.allocation(UserScope, AxisKey, Lens, LineFilter)`
  - `Envelope<SnapshotViewData> SnapshotViewService.accounts(UserScope)`
  - `void RequestValidator.validateSnapshotRequest(UserScope, ViewKey, AxisKey axisOrNull, Lens, Map<String,List<String>> filters)`

**완료 조건**
1. 4개 엔드포인트가 `yhr` 토큰으로 `200`과 §C.5·C.6·C.8·C.9의 값을 낸다.
2. **같은 요청을 `jdh`·`hhj` 토큰으로 부르면 §C.12의 값이 나온다.**
3. `?axis=is_leveraged` → `400 AXIS_DISABLED`. `?axis=sector`를 `positions`에 → `400 AXIS_NOT_APPLICABLE`.
4. `positions?lens=LOOK_THROUGH&market=US` → `400 LENS_SENSITIVE_FILTER_REJECTED`.
5. `accounts?lens=LOOK_THROUGH` → `400 LENS_NOT_ALLOWED`.
6. 계좌가 없으면(`test_empty`) `200` + `empty_reason: NO_ACCOUNTS`.
7. 남의 계좌를 `?account=`로 넣으면 `403 FORBIDDEN_ACCOUNT` — 카탈로그 대조를 통과한 UUID여도 그렇다.
8. `GET /portfolio/catalog`의 계좌 목록에 **인증 주체의 계좌만** 실린다(§8.1).

**검증 방법**
```bash
./gradlew test --tests '*SnapshotViewApiTest' --tests '*RequestValidatorTest'
# 그리고 실물 확인 — TOKEN은 POST /auth/login 응답의 access_token이다
curl -s -H "Authorization: Bearer $TOKEN" \
  'localhost:8080/portfolio/views/allocation?axis=sector&lens=DIRECT' | jq .
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
  'localhost:8080/portfolio/views/allocation?axis=is_leveraged'                            # 400
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" \
  'localhost:8080/portfolio/views/accounts?account=20000000-0000-0000-0000-000000000005'   # 403
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
 * 팩트 검증은 집계 전에, 필터와 무관하게 그 as_of 전체를 대상으로 수행한다 —
 * "연동된 모든 계좌에 라인 존재" 규칙이 필터를 걸면 성립하지 않는다.
 */
@Service
public class SnapshotViewService {

    public Envelope<SnapshotViewData> render(ViewKey viewKey, AxisKey rowAxis,
                                             Lens lens, LineFilter filter) {
        List<AccountRow> accounts = accountRepository.findAll();
        Optional<LocalDate> asOf = calendar.latestAsOf();
        if (asOf.isEmpty()) return emptyEnvelope(accounts);

        positionLineInvariants.validate(asOf.get());                       // §9.1

        ViewSpec view = Catalog.view(viewKey);
        Aggregation agg = aggregateQuery.aggregate(                        // §3.6 2~4단계
                asOf.get(), groupByOf(view, rowAxis), lens, filter);

        return assembler.assemble(view, lens, rowAxis, agg, contextOf(...));
    }
}
```

**필터는 집계 쿼리의 `WHERE` 절이며 마스터 조인 뒤에 적용된다**(§3.6 3.5단계). 계좌 필터를 렌즈 CTE 안으로 밀면 결과가 같으면서 스캔이 줄지만, 스펙이 그것을 "구현 최적화 여지"로 남겼으므로 이 계획은 규칙대로 조인 뒤에 둔다.

`summary`는 `render(SUMMARY, null, DIRECT, NONE)` 결과에 미니차트 블록을 더한다. 미니차트는 `groupBy = [miniChartAxis]`로 집계 쿼리를 한 번 더 실행하며, 렌즈는 미니차트 블록에만 적용한다(§6.3). 총합이 보존되므로 `total`은 렌즈와 무관하게 같다. `daily_change_*`는 `calendar.previousAsOf(asOf)`의 `totalAssetsKrwAt`으로 계산하며, 직전 스냅샷이 없으면 두 값 모두 `null`이다.

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
            .andExpect(jsonPath("$.data.total.instrument_count").value(6))
            .andExpect(jsonPath("$.data.total.market_value_krw").doesNotExist())   // 불변식 4
            .andExpect(jsonPath("$.data.mini_chart.rows[0].key").value("KR"))
            .andExpect(jsonPath("$.data.mini_chart.rows[0].market_value_krw").value(46800000))
            .andExpect(jsonPath("$.data.mini_chart.rows[0].weight_pct").value(80.7))
            .andExpect(jsonPath("$.data.mini_chart.rows[0].currency").doesNotExist())   // 단일 KRW
            .andExpect(jsonPath("$.data.mini_chart.rows[1].currency").value("USD"))     // 단일 USD
            .andExpect(jsonPath("$.data.mini_chart.rows[1].market_value_local").value(8000.00))
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

### Task 10: 실현손익 엔드포인트 (§8.4)

**Files:**
- Create: `query/RealizedPnlMapper.java` · `view/RealizedPnlViewService.java` · `view/PeriodResolver.java` · `api/dto/RealizedPnlData.java`
- Modify: `api/ViewController.java` (엔드포인트 추가)
- Test: `test/.../view/RealizedPnlViewServiceTest.java` · `test/.../api/RealizedPnlApiTest.java`

**Interfaces:**
- Produces:
  - `record RealizedPnlRow(String tradeId, UUID accountId, UUID instrumentId, String instrumentKey, String instrumentLabel, CurrencyCode currency, OffsetDateTime soldAt, BigDecimal quantity, BigDecimal sellAmountLocal, BigDecimal costBasisLocal, BigDecimal sellAmountKrw, BigDecimal costBasisKrw, BigDecimal realizedPnlKrw, Grade grade)`
  - `List<RealizedPnlRow> RealizedPnlMapper.findByPeriod(UserScope scope, LocalDate from, LocalDate to, LineFilter filter)`
  - `record Period(LocalDate from, LocalDate to)` · `Period PeriodResolver.resolve(String period, LocalDate from, LocalDate to, LocalDate referenceAsOf)`
  - `Envelope<RealizedPnlData> RealizedPnlViewService.render(UserScope, String period, LocalDate from, LocalDate to, LineFilter)`

**완료 조건**
1. `?period=THIS_YEAR`가 `yhr`에 §C.10의 값을 낸다 — 2행, `MIXED`, `SEEDED_ROWS`.
2. **같은 요청이 `jdh`에 1행 · `total 19,000`, `hhj`에 `NO_TRADES_IN_PERIOD`를 낸다.** 삼성전자 노드의 `trade_count`가 2이고 `last_sold_at`이 `2026-05-12`인 것이 스코프가 걸렸다는 증거다 — jdh의 `T-1001`(06-19)이 섞이면 둘 다 밀린다.
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

`RealizedPnlMapper.findByPeriod`의 SQL — 기간 귀속은 **체결일**(§4.3)이고 타임존은 `Asia/Seoul`이다:
```sql
SELECT r.trade_id, r.account_id, r.instrument_id, i.symbol, i.name, i.currency,
       r.sold_at, r.quantity, r.sell_amount_local, r.cost_basis_local,
       r.sell_amount_krw, r.cost_basis_krw, r.realized_pnl_krw, r.grade
  FROM realized_pnl_line r
  JOIN account    a ON a.account_id    = r.account_id
  JOIN instrument i ON i.instrument_id = r.instrument_id
 WHERE a.user_id = #{scope.userId}
   AND (r.sold_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN :from AND :to
```
계좌 필터는 `<include refid="accountFilter"/>`로 붙인다 — 집계 매퍼와 같은 조각을 쓴다. 스코프는 필터와 달리 항상 붙으므로 `<where>` 밖 고정 조건이다.

서비스가 하는 일:
1. 기준일 = `calendar.latestAsOf(scope)` → `PeriodResolver.resolve(...)`. **기준일이 사용자마다 다를 수 있다** — `THIS_YEAR` 같은 상대 기간이 그 사용자의 최신 스냅샷에서 계산된다
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

### Task 11: 자산 변화 엔드포인트 (§2.9 · §8.4)

**Files:**
- Create: `view/AssetChangeViewService.java` · `api/dto/AssetChangeData.java`
- Create: `query/ManualCashflowMapper.java` (실제 구현) · `query/EarningsCashflowPort.java` · `query/EmptyEarningsCashflowPort.java` · `query/EarningsCashflowType.java`
- Modify: `api/ViewController.java`
- Test: `test/.../view/AssetChangeViewServiceTest.java` · `test/.../api/AssetChangeApiTest.java`

**Interfaces:**
- Produces:
  - `record ManualCashflowTotals(BigDecimal deposit, BigDecimal withdraw)` — 백엔드 소유 테이블에서 읽은 **실제 값**
  - `ManualCashflowTotals ManualCashflowMapper.totalsBetween(UserScope, LocalDate exclusiveFrom, LocalDate inclusiveTo, LineFilter)`
  - `enum EarningsCashflowType { DIVIDEND, FEE, TAX }` — **`DEPOSIT`·`WITHDRAW`가 없다.** 스펙 §9.1의 "`cln_cashflow`에 `DEPOSIT`·`WITHDRAW`가 있으면 거부"를 타입으로 강제한다
  - `record EarningsCashflowTotals(BigDecimal dividend, BigDecimal feeTax, Set<UUID> coveredAccountIds, Set<EarningsCashflowType> coveredTypes)`
  - `EarningsCashflowTotals EarningsCashflowPort.totalsBetween(LocalDate exclusiveFrom, LocalDate inclusiveTo, Set<UUID> accountIds)` — 계좌 목록으로 좁히므로 스코프가 이미 반영된 인자를 받는다
  - `Envelope<AssetChangeData> AssetChangeViewService.render(UserScope, String period, LocalDate from, LocalDate to, LineFilter)`

**완료 조건**
1. `yhr`에 §C.11의 값을 낸다 — `opening 56,800,000` · `closing 58,000,000` · `deposited 2,000,000` · `investment_pnl −800,000` · `split_available false`.
2. 항등식이 성립한다: `closing = opening + deposited + earned + included − excluded`. **네 사용자 모두에서 성립한다.**
2.1. `jdh`는 `13,400,000 → 14,000,000` · 넣은 돈 `500,000` · 번 돈 `+100,000`이다 — 자산이 늘고 벌기도 한 반대 사례다.
2.2. **`hhj`는 기초 스냅샷이 없어 가장 이른 `2026-07-27`로 대체되고 `opening = closing = 2,000,000`, `breakdown`이 빈 배열이다.** 캘린더가 전역이면 여기서 `2026-07-24`가 잡혀 남의 세계에서 기간 손익이 계산된다.
3. 값이 0인 `breakdown` 항목이 숨겨진다 (`WITHDRAW`·`DIVIDEND`·`FEE_TAX`).
4. `PERIOD_TRUNCATED` · `BOUNDARY_CARRIED_FORWARD` · `CASHFLOW_UNCOVERED`가 뜨고, `CASHFLOW_UNCOVERED`의 `types`가 `["DIVIDEND","FEE","TAX"]`다 — **입출금은 입력됐으므로 여기 포함되지 않는다.**
5. 기초·기말 스냅샷이 없으면 `200` + `NO_HOLDINGS`.
6. **현금흐름 조회 구간이 요청 기간이 아니라 `(기초 as_of, 기말 as_of]`다.** `2026-07-01` 요청이지만 기초가 `2026-07-24`로 대체되므로 `2026-07-24` 이전의 입출금은 더하지 않는다.
7. `EarningsCashflowType`에 `DEPOSIT`·`WITHDRAW`가 없다(§9.1 타입 강제).

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

    /**
     * 이 뷰의 존재 이유 — 자산은 늘었는데 손실인 상황(스펙 §2.9).
     * 넣은 돈은 manual_cashflow에서 온 실제 값이고, 배당·수수료만 미확보다.
     */
    @Test
    void 자산이_늘었는데_손실인_경우를_드러낸다() {
        AssetChangeData d = render("2026-07-01", "2026-07-31").data();

        assertThat(d.opening()).isEqualByComparingTo("56800000");
        assertThat(d.closing()).isEqualByComparingTo("58000000");   // 자산은 +1,200,000
        assertThat(d.deposited()).isEqualByComparingTo("2000000");  // 넣은 돈 200만
        assertThat(d.earned()).isEqualByComparingTo("-800000");     // 번 돈 −80만
        assertThat(d.investmentPnl().total()).isEqualByComparingTo("-800000");
        assertThat(d.investmentPnl().splitAvailable()).isFalse();
        assertThat(d.investmentPnl().realized()).isNull();
    }

    /** 스펙 §2.9 — 값이 0인 항목은 행을 숨긴다. */
    @Test
    void 값이_0인_항목은_breakdown에서_숨는다() {
        AssetChangeData d = render("2026-07-01", "2026-07-31").data();
        assertThat(d.breakdown()).extracting(b -> b.type())
                .containsExactly("DEPOSIT", "INVESTMENT_PNL");   // WITHDRAW·DIVIDEND·FEE_TAX는 0
    }

    /**
     * 현금흐름 구간은 요청 기간이 아니라 실제 스냅샷 구간이다.
     * 기초가 2026-07-24로 대체됐으므로 그 이전 입출금은 더하지 않는다 — 안 그러면 항등식이 깨진다.
     */
    @Test
    void 현금흐름은_실제_기초_기말_구간으로_잘린다() {
        insertManualCashflow("2026-07-05", "DEPOSIT", "9000000");   // 기초 스냅샷보다 이전

        AssetChangeData d = render("2026-07-01", "2026-07-31").data();

        assertThat(d.deposited()).isEqualByComparingTo("2000000");  // 900만은 제외
        assertThat(d.closing()).isEqualByComparingTo(
                d.opening().add(d.deposited()).add(d.earned()));    // 항등식 유지
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

    /**
     * 스펙 §4.6 — 커버리지 판정 단위는 (계좌, 유형)이다.
     * 입출금은 입력됐고 배당·수수료만 미확보이므로 types가 셋이다.
     */
    @Test
    void 미확보_유형을_경고한다() {
        Envelope<AssetChangeData> env = render("2026-07-01", "2026-07-31");

        assertThat(noticeParams(env, "CASHFLOW_UNCOVERED"))
                .containsEntry("types", List.of("DIVIDEND", "FEE", "TAX"))
                .containsEntry("account_count", 4);
    }

    /** 스펙 §9.1 — 넣은 돈은 manual_cashflow에서만 온다. 타입이 그것을 강제한다. */
    @Test
    void 손익성_현금흐름_유형에_입출금이_없다() {
        assertThat(EarningsCashflowType.values())
                .containsExactly(EarningsCashflowType.DIVIDEND,
                                 EarningsCashflowType.FEE,
                                 EarningsCashflowType.TAX);
    }
}
```

- [ ] **Step 2: 현금흐름 두 경로 — 입출금은 실제, 손익성 현금은 스텁**

현금흐름의 출처는 둘로 갈린다. **입출금은 백엔드 소유 테이블에서 읽는 실제 값이고, 손익성 현금만 데이터팀 미합의로 스텁이다.**

```java
package com.stockproject.portfolio.query;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDate;

/**
 * manual_cashflow 조회 — 백엔드 소유(스펙 §5.1).
 * 자산 변화 뷰의 "넣은 돈"의 유일한 출처다(§9.1). 스텁이 아니다.
 * 구간은 (exclusiveFrom, inclusiveTo] — 기초 스냅샷 시점 이후에 발생한 것만 센다.
 */
@Mapper
public interface ManualCashflowMapper {

    ManualCashflowTotals totalsBetween(@Param("scope") UserScope scope,
                                       @Param("from") LocalDate exclusiveFrom,
                                       @Param("to") LocalDate inclusiveTo,
                                       @Param("filter") LineFilter filter);
}
```

```xml
<select id="totalsBetween" resultType="ManualCashflowTotals">
  SELECT coalesce(sum(CASE WHEN m.type = 'DEPOSIT'  THEN m.amount END), 0) AS deposit,
         coalesce(sum(CASE WHEN m.type = 'WITHDRAW' THEN m.amount END), 0) AS withdraw
    FROM manual_cashflow m
    JOIN account acct ON acct.account_id = m.account_id
   WHERE acct.user_id = #{scope.userId}
     AND m.occurred_on &gt;  #{from}
     AND m.occurred_on &lt;= #{to}
  <include refid="accountFilter"/>
</select>
```

```java
package com.stockproject.portfolio.query;

/**
 * cln_cashflow의 유형 — 손익성 현금만 담는다(스펙 §5.1).
 * 이 enum에 두 값이 없다는 사실이 §9.1의 "cln_cashflow에 DEPOSIT·WITHDRAW가 있으면 거부"를
 * 런타임 검사가 아니라 타입으로 강제한다.
 */
public enum EarningsCashflowType { DIVIDEND, FEE, TAX }
```

```java
package com.stockproject.portfolio.query;

/**
 * cln_cashflow 조회 — 데이터팀 소유(스펙 §5.1 · §11.2).
 * 매매대금·예수금 내부 이동·환전·매매 수수료를 제외한 결과만 제공받는 계약이며(§5.1),
 * 배제 규칙과 FEE·TAX 원천이 팀 미합의라(설계 공유 문서 안건 1, KIS는 배당만 제공 — 실측 §4-3)
 * 이번 범위에서는 EmptyEarningsCashflowPort가 빈 값을 낸다.
 * 빈 값은 곧 "미확보"이므로 CASHFLOW_UNCOVERED가 정직하게 뜨고 항등식은 그대로 성립한다.
 */
public interface EarningsCashflowPort {
    EarningsCashflowTotals totalsBetween(LocalDate exclusiveFrom, LocalDate inclusiveTo,
                                         Set<UUID> accountIds);
}
```

```java
@Component
public class EmptyEarningsCashflowPort implements EarningsCashflowPort {
    @Override public EarningsCashflowTotals totalsBetween(LocalDate exclusiveFrom,
                                                          LocalDate inclusiveTo,
                                                          Set<UUID> accountIds) {
        return new EarningsCashflowTotals(BigDecimal.ZERO, BigDecimal.ZERO, Set.of(), Set.of());
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
1. 기준일 = `calendar.latestAsOf(scope)`. `PeriodResolver.resolve(...)`로 `Period`를 얻는다.
2. **기초 스냅샷**: `calendar.latestBefore(scope, period.from())`. 없으면 `calendar.earliestOnOrAfter(scope, period.from())`을 쓰고 그 날짜를 `PERIOD_TRUNCATED.actual_from`으로 남긴다. 둘 다 없으면 `NO_HOLDINGS`.
3. **기말 스냅샷**: `calendar.latestOnOrBefore(scope, period.to())`. 없으면 `NO_HOLDINGS`.
4. `opening` · `closing` = 각 시점의 `totalAssetsKrwAt(scope, asOf, filter)`.
5. **계좌 편입·제외**: 기초·기말 스냅샷의 계좌 집합을 비교한다. 편입 = 기말에만 있는 계좌의 기말 총자산, 제외 = 기초에만 있는 계좌의 기초 총자산. (§2.9 경계 처리의 "첫/마지막 스냅샷 총자산"을 기간 양 끝 스냅샷으로 근사한다 — 기간 내 중간 스냅샷을 훑지 않는 단순화이며, 계좌 편입·제외가 기간 경계 밖에서 일어난 경우를 다루지 않는다. 이 근사를 코드 주석에 남긴다.)
6. **현금흐름 구간을 `(기초 as_of, 기말 as_of]`로 잡는다** — 요청 기간이 아니다(§A.6.3). 기초가 대체됐어도 항등식이 성립하게 하는 핵심이다.
7. `ManualCashflowMapper.totalsBetween(...)`으로 입출금을 읽는다. `deposited = deposit − withdraw`. **실제 값이다.**
8. `EarningsCashflowPort.totalsBetween(...)`으로 배당·수수료를 읽는다. 이번 범위에서는 0이다.
9. `investmentPnl = (closing − opening) − deposited − dividend + feeTax − included + excluded`.
10. `earned = investmentPnl + dividend − feeTax`.
11. `breakdown` = `DEPOSIT`(deposit) · `WITHDRAW`(−withdraw) · `DIVIDEND` · `FEE_TAX`(−feeTax) · `INVESTMENT_PNL` 중 **0이 아닌 것만**.
12. `investment_pnl.split_available = false`, `realized`·`unrealized_change` = `null` — 거래 원장 산출이 범위 밖이다.
13. notice: `CASHFLOW_UNCOVERED`의 `types` = `EarningsCashflowType` 전체 − `coveredTypes`, `account_count` = **그 사용자의** 연동 유효 계좌 수 − `coveredAccountIds` 크기. **입출금은 `manual_cashflow`가 원천이므로 미확보 유형에 넣지 않는다.** 경계 이월 계좌 수 = 두 경계 스냅샷의 `is_carried_forward` distinct 계좌 수(있으면 기말 날짜를 `boundary`로).

- [ ] **Step 5: 엔드포인트와 API 테스트**

```java
    @GetMapping("/views/asset-change")
    public Envelope<AssetChangeData> assetChange(
            UserScope scope,                        // 인증 토큰에서 주입된다 — 요청이 정하지 않는다
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
            .andExpect(jsonPath("$.data.deposited").value(2000000))
            .andExpect(jsonPath("$.data.earned").value(-800000))
            .andExpect(jsonPath("$.data.account_included").value(0))
            .andExpect(jsonPath("$.data.account_excluded").value(0))
            .andExpect(jsonPath("$.data.breakdown.length()").value(2))
            .andExpect(jsonPath("$.data.breakdown[0].type").value("DEPOSIT"))
            .andExpect(jsonPath("$.data.breakdown[0].amount").value(2000000))
            .andExpect(jsonPath("$.data.breakdown[1].type").value("INVESTMENT_PNL"))
            .andExpect(jsonPath("$.data.breakdown[1].amount").value(-800000))
            .andExpect(jsonPath("$.data.investment_pnl.total").value(-800000))
            .andExpect(jsonPath("$.data.investment_pnl.split_available").value(false))
            .andExpect(jsonPath("$.notices[?(@.code=='CASHFLOW_UNCOVERED')].params.account_count")
                    .value(4))
            .andExpect(jsonPath("$.notices[?(@.code=='PERIOD_TRUNCATED')].params.actual_from")
                    .value("2026-07-24"));
    }
```

- [ ] **Step 6: 커밋**

```bash
./gradlew test --tests '*AssetChange*'
git add -A && git commit -m "feat: 자산 변화 뷰 — 항등식 · 입출금 실제 값 · 손익성 현금 스텁"
```

---

### Task 12: 도달점 검증 — 6개 응답 골든 테스트와 문서

**Files:**
- Create: `test/.../api/SixViewGoldenTest.java`
- Create: `test/resources/golden/summary.json` · `positions.json` · `allocation-sector.json` · `allocation-sector-lookthrough.json` · `accounts.json` · `realized-pnl.json` · `asset-change.json`
- Create: `back-end/docs/decisions.md`
- Modify: `back-end/README.md`

**Interfaces:**
- Consumes: Task 9·10·11의 엔드포인트 전부

**완료 조건**
1. 샘플 SQL만 적재된 상태에서 `yhr` 토큰으로 부른 6개 엔드포인트 응답이 골든 JSON과 **완전히 일치**한다(필드 순서 무시, 값·키 존재 모두 비교).
2. 골든 JSON이 §C.5~C.11의 표와 일치한다.
3. 불변식 다섯 개를 응답 수준에서 다시 확인하는 교차 검증 테스트가 통과한다.
4. **같은 일곱 요청을 `jdh`·`hhj`·`test_empty` 토큰으로 부른 결과가 §C.12의 표와 일치한다.** 골든 파일은 `yhr`만 두고 나머지는 표의 핵심 수치만 단언한다 — 골든 네 벌을 두면 샘플을 손볼 때마다 네 벌을 고쳐야 한다.
5. `README.md`가 실행 절차·범위 경계·로그인 방법을 적는다.
6. `docs/decisions.md`가 §A.2의 네 결정(빌드·마이그레이션·데이터 접근·집계 위치)과 인증 방식, 그리고 각각을 되돌리는 조건을 적는다.

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
  printf '%s -> %s\n' "$p" \
    "$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" \
       "localhost:8080/portfolio/$p")"
done
# 기대: 전부 200. 토큰을 빼면 전부 401이다
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
        String actual = mockMvc.perform(get(path.trim()).header("Authorization", bearer(YHR)))
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

    /**
     * 불변식 3 — 병기 여부는 축이 아니라 그 묶음의 통화 집합이 정한다(스펙 §3.7).
     * 통화가 섞인 묶음에는 없고, 우연히 단일 외화인 묶음에는 있다.
     */
    @Test
    void 현지_통화는_단일_외화_묶음에만_실린다() throws Exception {
        JsonNode sector = json("/portfolio/views/allocation?axis=sector&lens=DIRECT").get("data").get("rows");

        assertThat(rowByLabel(sector, "IT서비스").get("currency").asText()).isEqualTo("USD");
        assertThat(rowByLabel(sector, "IT서비스").get("market_value_local").decimalValue())
                .isEqualByComparingTo("4400.00");
        assertThat(rowByLabel(sector, "소프트웨어").has("market_value_local")).isFalse();   // KRW + USD
        assertThat(rowByLabel(sector, "현금").has("market_value_local")).isFalse();         // KRW + USD
        assertThat(rowByLabel(sector, "반도체").has("market_value_local")).isFalse();       // 단일 KRW

        JsonNode pension = json("/portfolio/views/accounts").get("data").get("rows").get(1);
        assertThat(pension.has("market_value_local")).isFalse();                          // 소계는 혼합
        JsonNode mirae = pension.get("rows").get(1);
        assertThat(mirae.get("currency").asText()).isEqualTo("USD");                      // MSFT + USD 예수금
        assertThat(mirae.get("market_value_local").decimalValue()).isEqualByComparingTo("3600.00");
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

    /** 스펙 §2.9 항등식 — 잔차가 생길 자리가 없다. */
    @Test
    void 자산_변화_항등식이_응답_수준에서_성립한다() throws Exception {
        JsonNode d = json("/portfolio/views/asset-change?period=CUSTOM&from=2026-07-01&to=2026-07-31")
                .get("data");

        BigDecimal rhs = d.get("opening").decimalValue()
                .add(d.get("deposited").decimalValue())
                .add(d.get("earned").decimalValue())
                .add(d.get("account_included").decimalValue())
                .subtract(d.get("account_excluded").decimalValue());

        assertThat(d.get("closing").decimalValue()).isEqualByComparingTo(rhs);
        assertThat(d.get("earned").decimalValue().signum()).isNegative();   // 자산은 늘고 손익은 손실
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
- 데이터 접근을 MyBatis로 정한 결정, JPA를 기각한 여섯 가지 이유, jOOQ로 옮기는 조건.
- 집계를 Java에서 하는 결정과, SQL 구현을 추가할 때 **두 구현 대조 테스트를 함께 넣는다**는 조건.
- 인덱스·보관 기간·파티셔닝 트리거(§A.2.5).
- 인증을 JWT Bearer로 정한 이유와, 세션 쿠키·소셜 로그인으로 옮기는 조건.

- [ ] **Step 5: `README.md`**

- 실행: `docker compose up -d --build` → 샘플 적재 → `curl` 6개.
- 스택과 버전.
- **로그인 방법과 계정** — 팀원 셋의 계정이 마이그레이션에 들어 있고, 비밀번호 해시가 로컬 개발용이라 운영 배포 전에 교체해야 한다는 사실.
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
1 ─ 2 ─ 3 ─ 4 ─ 5 ─ 6 ─ 7 ─ 8 ─┬─  9 ─┐
                                ├─ 10 ─┼─ 12
                                └─ 11 ─┘
```

9·10·11은 서로 다른 서비스·DTO를 만들고 공유 상태가 없어 병렬로 진행할 수 있다. 단 셋 다 `api/ViewController.java`를 수정하므로, 병렬로 돌리면 그 파일에서 충돌한다 — 컨트롤러를 뷰별로 셋으로 쪼개거나(`SnapshotViewController` · `RealizedPnlController` · `AssetChangeController`) 순차로 처리한다. **쪼개는 쪽을 권한다** — 파일이 함께 바뀌는 이유가 없다.

**인증(8)이 엔드포인트 앞에 서는 이유.** 4~7은 `UserScope`를 파라미터로 받기만 하므로 그 값이 어디서 오는지 몰라도 만들어지고 테스트된다. 값의 출처가 실제로 필요해지는 지점은 HTTP 요청이 들어오는 9~11이다. 그래서 스코프를 받는 타입은 4에서, 그것을 채우는 장치는 8에서 만든다.

## E.2 착수 전 확인 하나

`PRICE_LAG_MARKET`을 휴장일 캘린더 없이 발화시킬지 여부다. 지금 계획은 발화시키지 않으며, 근거와 뒤집는 방법은 §A.10에 있다. 답이 없어도 진행에는 지장이 없다.

## E.2.1 후속 단계 착수 조건

**계획 A(이번 범위)는 증권사 계좌가 필요 없다.** 입력이 사람이 넣은 샘플 행이다.

**1.5단계(등급 판정) 이후는 개발용 실전 계좌가 필요하다** — 손익·실현손익·권리 계열 TR 5종이 모의투자를 지원하지 않아 모의 앱키로는 개발도 테스트도 되지 않는다(§A.11). 계획 A를 진행하는 동안 실전 계좌와 앱키를 준비해 두면 대기 시간이 겹치지 않는다.

## E.3 이 계획이 검증하는 스펙 항목 대조

| 스펙 절 | 태스크 |
|---|---|
| §1.3 그레인 · §3.1 팩트 그레인 | 1(PK) · 4(검증기) |
| §3.8 사용자 스코프 | 1(소유권 축·샘플) · 4(저장소·캘린더) · 5(CTE) · 6(집계) · 8(주입·소유 검사) |
| §8.8 인증 | 8 |
| §1.5 · §3.2 저장 규칙·가산성 | 1(린트) · 3(타입) · 6(집계 쿼리) |
| §3.3 축과 필터 | 2(카탈로그) · 6(마스터 조인·필터) |
| §3.4 렌즈 | 5 |
| §3.5 뷰 사양 | 2 |
| §3.6 파이프라인 2~6단계 | 4·5·6·7·8 |
| §3.7 통화 표시 | 3(CurrencySet) · 7(정책) · 11(교차 검증) |
| §5.1 테이블 (`app_user` 포함) | 1 |
| §5.1 `manual_cashflow` (사용자 입력 입출금) | 1(마이그레이션·샘플) · 11(읽기 경로) |
| §5.2 예수금을 종목으로 | 1(샘플) · 3(2슬롯) · 7(응답 null) |
| §5.3 원화 환산 머티리얼라이즈 | 1(컬럼) · 7(`FX_APPLIED`·`FX_STALE`) |
| §5.5 타입 정책·반올림 | 1(numeric) · 3(비율 1자리) |
| §6.1~6.4 카탈로그·서빙 계약 | 2 · 9(카탈로그 엔드포인트·요청 검증) |
| §8.1 엔드포인트 | 8·9·10·11 |
| §8.2 봉투·notice·empty_reason | 7 |
| §8.6 인증·권한 실패(`401`·`403`) | 8 |
| §8.3 스냅샷 뷰 응답 | 7·9 |
| §4.6 현금흐름 커버리지 (계좌, 유형) | 11 |
| §8.4 실현손익·자산 변화 응답 | 10·11 |
| §8.6 오류와 빈 상태 | 7·9 |
| §9.1 런타임 검증(사용자 스코프·`position_line`·렌즈) | 4(검사 쿼리) · 5(총합 보존·CTE 스코프) · 8(매퍼 시그니처) |
| §9.2 스키마 규약 | 1(린트) · 3(ArchUnit) |
| §9.3 요청 검증·응답 조립 | 7·8(계좌 소유 검사) · 9 |
| §10 화면 상태 전수 | 7·9·10·11 (빈 상태·경고·계좌 상태 세 표현 수단) |
| §13이 계획에서 확정하라 한 것 | §A.2.5(인덱스·보관·파티셔닝) · 8(토큰 비밀키와 만료) |

**이번 범위에서 다루지 않는 스펙 절**: §4.1~4.5(평단·등급 판정 — 1.5/1.6단계) · §7(계좌 연동·동기화) · §9.1의 평단·등급 묶음 · §11(역할 분담, 문서) · §12(YAGNI 경계, 의도적 제외).

## E.4 실행 방식 선택

계획이 `docs/yhr/plan/2026-08-09-portfolio-query-layer-plan.md`에 저장됐다. 실행은 두 갈래다.

1. **서브에이전트 주도 (권장)** — 태스크마다 새 서브에이전트를 띄우고 태스크 사이에 리뷰한다. 컨텍스트가 태스크 단위로 깨끗하고 반복이 빠르다. `superpowers:subagent-driven-development`.
2. **인라인 실행** — 이 세션에서 태스크를 이어서 실행하고 체크포인트에서 리뷰한다. `superpowers:executing-plans`.
