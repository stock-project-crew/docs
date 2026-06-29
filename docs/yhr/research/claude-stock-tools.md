# 주식 관련 Claude Code 플러그인·스킬 조사

> 조회 시점: 2026-06-28 · 모든 Star/Fork/Commit 수치는 이 시점 기준이며 계속 변동함
> 아래 5개는 각 저장소의 GitHub README를 직접 확인해 작성한 내용임

## 선정 기준

1. 주식과 직접 관련 (crypto 전용 제외)
2. GitHub에 실재하고 README를 직접 확인해 수치를 검증함
3. Star·활성도로 주요도 판단

---

## 한눈에 보는 목적·기능

| # | 도구 | 한 줄 목적·기능 |
|---|---|---|
| 1 | **anthropics/financial-services** | 금융 전문가(IB·리서치·PE·자산관리) 업무를 자동화하는 Anthropic 공식 플러그인·에이전트 모음. DCF/LBO/comps 모델링, 실적 노트, IC 메모 등 |
| 2 | **tradermonty/claude-trading-skills** | 시간 부족한 미국 주식 개인투자자용 스킬 모음. 시장 리뷰·스크리닝·리스크 관리·매매 저널링·회고 |
| 3 | **koreainvestment/open-trading-api** | 한국투자증권 공식 Open API 샘플코드 + 전략 빌더 + 백테스터 + MCP. 한국·해외 주식 시세/주문/자동매매 |
| 4 | **quant-sentiment-ai/claude-equity-research** | 슬래시 커맨드 하나로 미국 종목 기관급 리서치 리포트(BUY/SELL/HOLD)를 생성하는 Claude Code 플러그인 |
| 5 | **koreainvestment/kis-ai-extensions** | 한국투자증권 공식 npm 플러그인. 전략 설계→백테스팅→주문 실행을 AI 에이전트에서 자연어로 조작 (Claude Code/Cursor/Codex/Gemini) |

---

## 기본 정보

| 항목 | financial-services | claude-trading-skills | open-trading-api | claude-equity-research | kis-ai-extensions |
|---|---|---|---|---|---|
| 소유자 | anthropics (Anthropic 공식) | tradermonty (개인) | koreainvestment (한투 공식) | quant-sentiment-ai (개인) | koreainvestment (한투 공식) |
| 형태 | 플러그인+에이전트+MCP 커넥터 | Claude Skills 모음 | 샘플코드+전략/백테스트+MCP | Claude Code 플러그인 | 멀티 에이전트 플러그인 (npm) |
| 대상 시장 | 미국·글로벌 (전문가용) | 미국 주식 (개인투자자) | 한국·해외 주식, 채권, 선물옵션 등 | 미국 주식 | 한국 주식 |
| Star | 32.7k | 1.6k | 1.4k | 552 | 11 |
| Fork | 4.7k | 413 | 726 | 64 | 2 |
| Commits | 62 | 436 | 392 | 17 | 2 |
| 라이선스 | Apache-2.0 | MIT | (README 명시 없음) | MIT | (README 명시 없음) |
| 주 언어 | Python 78.9% | Python 99.9% | Python 90.1% | (명시 없음) | JS 47.4%, Python 37.5% |

---

## 구성 요소

| 도구 | 주요 구성 |
|---|---|
| financial-services | 10개 에이전트(Pitch Agent, Market Researcher, Earnings Reviewer, Model Builder, GL Reconciler 등) + 7개 버티컬 플러그인(financial-analysis 코어, investment-banking, equity-research, private-equity, wealth-management, fund-admin, operations) + 파트너 플러그인(LSEG, S&P Global) + 12개 MCP 데이터 커넥터(FactSet, Morningstar, PitchBook 등) + 슬래시 커맨드(`/comps`, `/dcf`, `/lbo`, `/earnings`, `/ic-memo` 등) |
| claude-trading-skills | 40+ 스킬: Market Regime, Core Portfolio(배당·가치 스크리너), Swing(vcp/canslim/finviz 스크리너), Trade Planning, Trade Memory(저널·회고), Strategy Research(백테스트·edge 파이프라인), Advanced Satellite(옵션·페어트레이드) |
| open-trading-api | `examples_llm/`·`examples_user/`(API 샘플), `strategy_builder/`(80개 지표·10개 프리셋 전략), `backtester/`(Docker 기반 QuantConnect Lean), `MCP/`(KIS Code Assistant + Trading MCP) |
| claude-equity-research | 슬래시 커맨드 `/trading-ideas:research <TICKER>` 단일 기능. 8섹션 리포트 + 등급 + 목표가, `--detailed`로 옵션 플로우·내부자 분석 추가 |
| kis-ai-extensions | 5개 스킬(kis-strategy-builder, kis-backtester, kis-order-executor, kis-team, kis-cs) + 커맨드(/auth, /my-status 등) + MCP 서버 + 보안 훅(secret-guard, prod-guard 등) |

---

## 설치·요구사항

| 도구 | 설치 | 요구사항 |
|---|---|---|
| financial-services | `claude plugin marketplace add anthropics/financial-services` 후 플러그인별 install (또는 Cowork에서 repo URL 추가) | Claude 유료 플랜(Pro/Max/Team/Enterprise), MCP 커넥터는 제공사 구독/API 키 별도 |
| claude-trading-skills | `.skill` 파일 웹앱 업로드 또는 스킬 폴더를 Claude Code Skills 디렉토리에 복사 | 스킬별 상이. FMP(무료 250req/day)·FINVIZ Elite($39.50/월, 선택)·Alpaca(페이퍼 무료). 무API 5개 스킬 별도 제공 |
| open-trading-api | `git clone` 후 `uv sync` | Python 3.11+, uv, KIS 앱키/시크릿. 전략/백테스트엔 Node.js 18+·Docker 추가 |
| claude-equity-research | `/plugin marketplace add` → `/plugin install` | Claude Code CLI 2.0.11+, Claude 유료 구독, 인터넷 |
| kis-ai-extensions | open-trading-api 클론 후 `npx @koreainvestment/kis-quant-plugin init --agent claude` | Python 3.11+, uv, Node.js 18+, Docker, KIS 앱키/시크릿 |

---

## 성격·안전장치 (README 명시)

| 도구 | 내용 |
|---|---|
| financial-services | "투자/법률/세무/회계 자문 아님. 에이전트는 전문가 검토용 초안을 작성할 뿐, 투자 추천·거래 실행·원장 기록을 하지 않으며 모든 산출물은 사람 승인 대기" |
| claude-trading-skills | "시그널 서비스·수익 보장 아님, 완전 자동매매·단타 스캘핑용 아님. 인간 의사결정 게이트 중심" |
| open-trading-api | "샘플 코드 참고용, 이용자 프로그램 손해는 회사 책임 없음" |
| claude-equity-research | "교육·연구용, 금융 자문 아님" |
| kis-ai-extensions | 신호 강도 0.5 미만 자동 건너뜀, 실전 주문 시 사용자 승인 강제, appkey/secret/토큰 출력 금지 |

---

## 매수·매도 트리거 로직 & 데이터 의존성 (트리거 관점 추가 조사)

> 2026-06-28 추가 — claude-trading-skills README와 open-trading-api/strategy_builder를 직접 확인해 "무슨 데이터로 언제 사고팔지"를 정리

### 공통 패턴
- **매수=기회탐지 / 매도=리스크관리로 분리.** claude-trading-skills는 진입 로직만 스킬에 담고, 청산(손절·트레일링·R-multiple)은 `position-sizer`·`technical-analyst`로 위임.
- **대부분 일봉 OHLCV + 펀더멘털(FMP)로 동작.** 실시간/분봉은 고급 스킬(파라볼릭 숏 5분봉/Alpaca, 모멘텀버스트 옵션)에만. open-trading-api의 WebSocket은 라이브 주문 실행용.
- **사람 게이트:** 모든 도구가 자동주문 전 사용자 승인. kis-ai-extensions는 신호강도 0.5 미만 자동 스킵.

### claude-trading-skills — 스킬별 진입 조건/데이터
| 스킬 | 데이터 | 진입 조건 |
|---|---|---|
| VCP Screener | 일봉(FMP) | Minervini VCP: Stage2 회복 + 변동성 수축 + 거래량 압축 후 돌파 |
| CANSLIM | 펀더멘털+기술(FMP) | O'Neil 성장주 기준(EPS 가속, 기관보유, 주도주) |
| Stockbee 모멘텀버스트 | 일봉(+옵션 실시간) | 4% 돌파·레인지/거래량 확장, 3~5일 모멘텀 |
| Value Dividend | 펀더멘털(FMP) | PER<20, PBR<2, 배당수익률 3%+, 3년 우상향 |
| Dividend Growth Pullback | 펀더멘털+기술 | 배당성장 12%+, 수익률 1.5%+, RSI≤40 과매도 |
| 어닝스 트레이드 | 실적 펀더멘털 | 5팩터 스코어(갭·추세·거래량·MA200·MA50) |
| 청산(공통) | — | 진입 스킬엔 청산 임계값 명시 적음 → 리스크 모듈에서 손절 브래킷/최악손실 계산 |

### open-trading-api strategy_builder — 선언형 전략
- **코딩 없이** 전략을 `.kis.yaml`로 정의 → 백테스트 → 라이브 신호/주문.
- **프리셋 10종:** golden_cross(골든크로스), momentum, trend_filter, week52_high(52주 신고가 돌파), consecutive(N일 연속), disparity(이격도), breakout_fail(돌파실패=매도), strong_close, volatility(변동성 확장), mean_reversion(평균회귀).
- **연산자 7종:** cross_above, cross_below, greater_than, less_than, greater_equal, less_equal, equals.
- **지표 80종**(RSI/MACD/볼린저/VWAP/일목 등) + **캔들패턴 57종**.
- 구조: `indicators`(지표+params) → `entry`/`exit`(conditions: indicator+operator+compare_to, AND/OR) → `risk`(stop_loss 등). 데이터는 일봉 OHLCV 중심, 실시간은 WebSocket.

---

## 선정에서 제외했거나 미확인한 후보

| 후보 | 처리 | 사유 |
|---|---|---|
| jeremylongshore/claude-code-plugins-plus-skills | 미확인 | 검색엔 등장했으나 README 직접 확인 못 함 (백테스팅·리스크 관리 스킬) |
| JoelLewis/finance_skills | 미확인 | 검색엔 등장했으나 README 직접 확인 못 함 (데이터 인제스천·리스크 관리 스킬) |
| koreainvestment/koreainvestment-mcp | 제외 | open-trading-api와 기능 중복(한투 API 자연어 검색 MCP), 대표로 후자만 선정 |
| coinpaprika/claude-marketplace 등 | 제외 | crypto 전용이라 "주식" 기준에서 제외 |

---

## 레퍼런스 (직접 확인한 페이지)

- anthropics/financial-services — https://github.com/anthropics/financial-services
- tradermonty/claude-trading-skills — https://github.com/tradermonty/claude-trading-skills
- koreainvestment/open-trading-api — https://github.com/koreainvestment/open-trading-api
- quant-sentiment-ai/claude-equity-research — https://github.com/quant-sentiment-ai/claude-equity-research
- koreainvestment/kis-ai-extensions — https://github.com/koreainvestment/kis-ai-extensions

### 참고 (검색 단계에서 참조했으나 미확정)

- Anthropic 공식 금융 플러그인 설치 안내 — https://support.claude.com/en/articles/13851150-install-financial-services-plugins
- koreainvestment/koreainvestment-mcp — https://github.com/koreainvestment/koreainvestment-mcp
- jeremylongshore/claude-code-plugins-plus-skills (검색 출처) — https://snyk.io/articles/top-claude-skills-finance-quantitative-developers/

---

*본 문서는 도구 조사 자료이며 투자 자문이 아님. 실제 매매 판단과 책임은 사용자 본인에게 있음. 주문 실행 기능이 있는 도구는 모의투자 계좌로 충분히 검증 후 사용 권장.*
