# 2-4. 뉴스 해석 LLM — Batch (10분 마이크로배치)

> 관련: [설계 개요](../README.md) · [기술 스택](../tech-stack.md)

**엔드포인트**

| Method | Path | 설명 |
|--------|------|------|
| GET | `/news/feed` | 보유 종목 관련 뉴스 + 해석 피드 |
| GET | `/news/{id}` | 개별 기사 해석 상세 |

**뉴스 처리 파이프라인 (백그라운드)**

1. `[데이터]` Airflow `news` DAG (10분) — 네이버/NewsAPI/RSS 수집
2. `[데이터]` 원본 기사 → **Bronze**
3. `[데이터]` Spark: 중복 제거 + 엔티티 링킹(기사→종목) → **Silver** (+ pgvector 임베딩, 선택)
4. `[데이터]` **비용 필터** — 누군가의 포트폴리오에 있는 종목 기사만 LLM 큐로
5. `[데이터]` LLM 잡: 기사 **본문 + 프롬프트** → Claude structured output → `{호재/중립/악재, affected_tickers, rationale, horizon, confidence}` → **Gold**
   - 기사 해시로 캐시 (이미 해석한 기사 재호출 방지)
6. `[데이터]` Gold → Postgres

**뉴스 피드 진입 시**

1. `[프론트]` `GET /news/feed`
2. `[백엔드]` Postgres에서 보유 종목과 연결된 기사 + 해석 조회 → 영향도/최신순 정렬 → 응답

**핵심 주의점**

- 비용 통제가 관건: **포트폴리오와 겹치는 기사만** LLM에 전달
- **본문 안에서만 해석**(모델 기억 의존 X → 환각 방지)
- 결과 화면에 "정보 제공일 뿐 투자 권유 아님" 명시
