<!-- Generator: Widdershins v4.0.1 -->

<h1 id="-api">포트폴리오 · 알림 API vmain</h1>

앱(React Native)과 서버(Spring Boot) 사이의 계약이다. 서버 코드에서 생성했다.

- **인증**: `POST /auth/login`으로 받은 접근 토큰을 `Authorization: Bearer <토큰>`으로 보낸다. 토큰이 없거나 만료되면 401이고, 앱은 갱신 토큰으로 `POST /auth/refresh`를 부른다.
- **사용자**: 사용자 id는 경로 · 쿼리 · 본문 어디에서도 받지 않는다. 토큰이 정한다.
- **필드 이름**: 요청 · 응답 모두 snake_case다.
- **조회 봉투**: 목록 조회는 `as_of`(기준 시각) · `data` · `empty_reason`(빈 목록일 때 화면이 고를 상태) · `notices`(화면 위 안내)로 감싼다. 빈 목록은 오류가 아니라 200이다.
- **문장은 서버가 만든다**: 안내 · 오류의 `message`는 화면에 그대로 보이는 완성된 문장이다. 앱은 `code`로 색 · 아이콘 · 다음 동작만 고른다.
- **오류**: 모든 오류는 `ApiError` 모양이다. 엔드포인트별 오류 코드는 각 설계서의 오류 절에 있다.

설계서: [공통](https://github.com/stock-project-crew/docs/blob/main/yhr/specs/common.md) · [포트폴리오](https://github.com/stock-project-crew/docs/blob/main/yhr/specs/portfolio.md) · [알림](https://github.com/stock-project-crew/docs/blob/main/yhr/specs/alert.md)

# Authentication

- HTTP Authentication, scheme: bearer 로그인으로 받은 접근 토큰

<h1 id="-api--">로그인</h1>

로그인 · 토큰 갱신 · 로그아웃. 설계서: common.md «로그인·세션»

## POST /auth/refresh

<a id="opIdrefresh_1"></a>

`POST /auth/refresh`

> Body parameter

```json
{
  "refresh_token": "string"
}
```

<h3 id="refresh_1-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[RefreshRequest](#schemarefreshrequest)|true|none|

> Example responses

> 200 Response

```json
{
  "access_token": "string",
  "expires_at": "2019-08-24T14:15:22Z",
  "refresh_token": "string"
}
```

<h3 id="refresh_1-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[TokenResponse](#schematokenresponse)|

<aside class="success">
This operation does not require authentication
</aside>

## POST /auth/logout

<a id="opIdlogout"></a>

`POST /auth/logout`

> Body parameter

```json
{
  "refresh_token": "string"
}
```

<h3 id="logout-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[RefreshRequest](#schemarefreshrequest)|true|none|

<h3 id="logout-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|204|[No Content](https://tools.ietf.org/html/rfc7231#section-6.3.5)|No Content|None|

<aside class="success">
This operation does not require authentication
</aside>

## POST /auth/login

<a id="opIdlogin"></a>

`POST /auth/login`

> Body parameter

```json
{
  "email": "string",
  "password": "string"
}
```

<h3 id="login-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[LoginRequest](#schemaloginrequest)|true|none|

> Example responses

> 200 Response

```json
{
  "access_token": "string",
  "expires_at": "2019-08-24T14:15:22Z",
  "refresh_token": "string"
}
```

<h3 id="login-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[TokenResponse](#schematokenresponse)|

<aside class="success">
This operation does not require authentication
</aside>

## GET /auth/me

<a id="opIdme"></a>

`GET /auth/me`

> Example responses

> 200 Response

```json
{
  "user_id": "a169451c-8525-4352-b8ca-070dd449a1a5",
  "email": "string",
  "display_name": "string"
}
```

<h3 id="me-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[MeResponse](#schemameresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">보유 화면</h1>

요약 · 종목 · 비중 · 계좌별. 설계서: portfolio.md «화면» · «집계 모델»

## GET /portfolio/views/summary

<a id="opIdsummary"></a>

`GET /portfolio/views/summary`

<h3 id="summary-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|mini_chart_lens|query|string|false|none|
|mini_chart_axis|query|string|false|none|

> Example responses

> OK

```json
{
  "as_of": "2026-07-27T15:30:00+09:00",
  "data": {
    "group_by": [],
    "lens": "DIRECT",
    "total": {
      "total_assets_krw": 58000000,
      "securities_value_krw": 53300000,
      "deposit_krw": 4700000,
      "cost_amount_krw": 48800000,
      "unrealized_pnl_krw": 4500000,
      "unrealized_pnl_pct": 9.2,
      "cash_ratio_pct": 8.1,
      "instrument_count": 6,
      "account_count": 4,
      "daily_change_krw": 1200000,
      "daily_change_pct": 2.1
    },
    "rows": [],
    "mini_chart": {
      "group_by": [
        "market"
      ],
      "lens": "DIRECT",
      "rows": [
        {
          "key": "KR",
          "label": "국내",
          "market_value_krw": 46800000,
          "weight_pct": 80.7
        },
        {
          "key": "US",
          "label": "미국",
          "currency": "USD",
          "market_value_krw": 11200000,
          "market_value_local": 8000,
          "weight_pct": 19.3
        }
      ]
    }
  },
  "empty_reason": null,
  "notices": [
    {
      "code": "FX_APPLIED",
      "severity": "info",
      "message": "USD/KRW 1,400.00 적용 · 기준 2026-07-24",
      "params": {
        "rates": [
          {
            "pair": "USD/KRW",
            "rate": 1400,
            "fx_as_of": "2026-07-24"
          }
        ],
        "oldest_fx_as_of": "2026-07-24"
      }
    },
    {
      "code": "STALE_ACCOUNTS",
      "severity": "warn",
      "message": "1개 계좌가 07-24 기준입니다",
      "params": {
        "count": 1,
        "oldest": "2026-07-24"
      }
    },
    {
      "code": "PRICE_LAG_MARKET",
      "severity": "info",
      "message": "미국 종목은 07-24 종가 기준이에요",
      "params": {
        "markets": [
          {
            "market": "US",
            "price_as_of": "2026-07-24",
            "quote_count": 0
          }
        ]
      }
    }
  ]
}
```

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="summary-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[EnvelopeSnapshotViewData](#schemaenvelopesnapshotviewdata)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## GET /portfolio/views/positions

<a id="opIdpositions"></a>

`GET /portfolio/views/positions`

<h3 id="positions-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|lens|query|string|false|none|
|account|query|array[string]|false|none|
|market|query|array[string]|false|none|
|asset_class|query|array[string]|false|none|

> Example responses

> OK

```json
{
  "as_of": "2026-07-27T15:30:00+09:00",
  "data": {
    "group_by": [
      "instrument"
    ],
    "lens": "DIRECT",
    "total": {
      "total_assets_krw": 58000000,
      "securities_value_krw": 53300000,
      "deposit_krw": 4700000,
      "cost_amount_krw": 48800000,
      "unrealized_pnl_krw": 4500000,
      "unrealized_pnl_pct": 9.2,
      "cash_ratio_pct": 8.1,
      "instrument_count": 6,
      "account_count": 4
    },
    "rows": [
      {
        "key": "005930",
        "label": "삼성전자",
        "quantity": 200,
        "avg_cost": 60000,
        "market_value_krw": 14240000,
        "cost_amount_krw": 12000000,
        "unrealized_pnl_krw": 2240000,
        "unrealized_pnl_pct": 18.7,
        "weight_pct": 24.6,
        "market": "KR",
        "instrument_id": "10000000-0000-0000-0000-000000000001"
      },
      {
        "key": "133690",
        "label": "TIGER 미국나스닥100",
        "quantity": 100,
        "avg_cost": 100000,
        "market_value_krw": 11000000,
        "cost_amount_krw": 10000000,
        "unrealized_pnl_krw": 1000000,
        "unrealized_pnl_pct": 10,
        "weight_pct": 19,
        "market": "KR",
        "instrument_id": "10000000-0000-0000-0000-000000000006"
      },
      {
        "key": "000660",
        "label": "SK하이닉스",
        "quantity": 50,
        "avg_cost": 160000,
        "market_value_krw": 9000000,
        "cost_amount_krw": 8000000,
        "unrealized_pnl_krw": 1000000,
        "unrealized_pnl_pct": 12.5,
        "weight_pct": 15.5,
        "market": "KR",
        "instrument_id": "10000000-0000-0000-0000-000000000002"
      },
      {
        "key": "035420",
        "label": "NAVER",
        "quantity": 40,
        "avg_cost": 225000,
        "market_value_krw": 8000000,
        "cost_amount_krw": 9000000,
        "unrealized_pnl_krw": -1000000,
        "unrealized_pnl_pct": -11.1,
        "weight_pct": 13.8,
        "market": "KR",
        "instrument_id": "10000000-0000-0000-0000-000000000003"
      },
      {
        "key": "AAPL",
        "label": "애플",
        "currency": "USD",
        "quantity": 20,
        "avg_cost": 200,
        "market_value_krw": 6160000,
        "market_value_local": 4400,
        "cost_amount_krw": 5600000,
        "cost_amount_local": 4000,
        "unrealized_pnl_krw": 560000,
        "unrealized_pnl_pct": 10,
        "weight_pct": 10.6,
        "market": "US",
        "instrument_id": "10000000-0000-0000-0000-000000000004"
      },
      {
        "key": "MSFT",
        "label": "마이크로소프트",
        "currency": "USD",
        "quantity": 10,
        "avg_cost": 300,
        "market_value_krw": 4900000,
        "market_value_local": 3500,
        "cost_amount_krw": 4200000,
        "cost_amount_local": 3000,
        "unrealized_pnl_krw": 700000,
        "unrealized_pnl_pct": 16.7,
        "weight_pct": 8.4,
        "market": "US",
        "instrument_id": "10000000-0000-0000-0000-000000000005"
      },
      {
        "key": "CASH-KRW",
        "label": "KRW 예수금",
        "quantity": 4560000,
        "avg_cost": null,
        "market_value_krw": 4560000,
        "cost_amount_krw": null,
        "unrealized_pnl_krw": null,
        "unrealized_pnl_pct": null,
        "weight_pct": 7.9,
        "market": "KR"
      },
      {
        "key": "CASH-USD",
        "label": "USD 예수금",
        "currency": "USD",
        "quantity": 100,
        "avg_cost": null,
        "market_value_krw": 140000,
        "market_value_local": 100,
        "cost_amount_krw": null,
        "unrealized_pnl_krw": null,
        "unrealized_pnl_pct": null,
        "weight_pct": 0.2,
        "market": "US"
      }
    ]
  },
  "empty_reason": null,
  "notices": [
    {
      "code": "FX_APPLIED",
      "severity": "info",
      "message": "USD/KRW 1,400.00 적용 · 기준 2026-07-24",
      "params": {
        "rates": [
          {
            "pair": "USD/KRW",
            "rate": 1400,
            "fx_as_of": "2026-07-24"
          }
        ],
        "oldest_fx_as_of": "2026-07-24"
      }
    },
    {
      "code": "STALE_ACCOUNTS",
      "severity": "warn",
      "message": "1개 계좌가 07-24 기준입니다",
      "params": {
        "count": 1,
        "oldest": "2026-07-24"
      }
    },
    {
      "code": "PRICE_LAG_MARKET",
      "severity": "info",
      "message": "미국 종목은 07-24 종가 기준이에요",
      "params": {
        "markets": [
          {
            "market": "US",
            "price_as_of": "2026-07-24",
            "quote_count": 0
          }
        ]
      }
    }
  ]
}
```

```json
{
  "as_of": "2026-07-27T15:30:00+09:00",
  "data": {
    "group_by": [
      "instrument"
    ],
    "lens": "LOOK_THROUGH",
    "total": {
      "total_assets_krw": 60000000,
      "securities_value_krw": 55300000,
      "deposit_krw": 4700000,
      "cost_amount_krw": 50600000,
      "unrealized_pnl_krw": 4700000,
      "unrealized_pnl_pct": 9.3,
      "cash_ratio_pct": 7.8,
      "instrument_count": 6,
      "account_count": 4
    },
    "rows": [
      {
        "key": "005930",
        "label": "삼성전자",
        "quantity": 222,
        "market_value_krw": 15806400,
        "weight_pct": 26.3,
        "market": "KR"
      },
      {
        "key": "AAPL",
        "label": "애플",
        "currency": "USD",
        "quantity": 36,
        "market_value_krw": 11088000,
        "market_value_local": 7920,
        "weight_pct": 18.5,
        "market": "US"
      },
      {
        "key": "000660",
        "label": "SK하이닉스",
        "quantity": 50,
        "market_value_krw": 9000000,
        "weight_pct": 15,
        "market": "KR"
      },
      {
        "key": "MSFT",
        "label": "마이크로소프트",
        "currency": "USD",
        "quantity": 16.6,
        "market_value_krw": 8134000,
        "market_value_local": 5810,
        "weight_pct": 13.6,
        "market": "US"
      },
      {
        "key": "035420",
        "label": "NAVER",
        "quantity": 40,
        "market_value_krw": 8000000,
        "weight_pct": 13.3,
        "market": "KR"
      },
      {
        "key": "CASH-KRW",
        "label": "KRW 예수금",
        "quantity": null,
        "market_value_krw": 4560000,
        "weight_pct": 7.6,
        "market": "KR"
      },
      {
        "key": "069500",
        "label": "KODEX 200",
        "quantity": 50,
        "market_value_krw": 2000000,
        "weight_pct": 3.3,
        "market": "KR"
      },
      {
        "key": "CASH-USD",
        "label": "USD 예수금",
        "currency": "USD",
        "quantity": null,
        "market_value_krw": 140000,
        "market_value_local": 100,
        "weight_pct": 0.2,
        "market": "US"
      },
      {
        "key": "OTHER",
        "label": "기타(ETF 내 비주식·미매칭)",
        "quantity": null,
        "market_value_krw": 1271600,
        "weight_pct": 2.1
      }
    ]
  },
  "empty_reason": null,
  "notices": [
    {
      "code": "FX_APPLIED",
      "severity": "info",
      "message": "USD/KRW 1,400.00 적용 · 기준 2026-07-24",
      "params": {
        "rates": [
          {
            "pair": "USD/KRW",
            "rate": 1400,
            "fx_as_of": "2026-07-24"
          }
        ],
        "oldest_fx_as_of": "2026-07-24"
      }
    },
    {
      "code": "STALE_ACCOUNTS",
      "severity": "warn",
      "message": "1개 계좌가 07-24 기준입니다",
      "params": {
        "count": 1,
        "oldest": "2026-07-24"
      }
    },
    {
      "code": "CONSTITUENT_AS_OF",
      "severity": "info",
      "message": "구성비중 기준 07-24",
      "params": {
        "oldest": "2026-07-24",
        "count": 1
      }
    },
    {
      "code": "CONSTITUENT_UNAVAILABLE",
      "severity": "warn",
      "message": "1개 ETF는 구성종목으로 나누지 못해 그대로 표시했습니다",
      "params": {
        "count": 1,
        "undecomposed_krw": 2000000,
        "keys": [
          "069500"
        ]
      }
    },
    {
      "code": "LENS_METRICS_OMITTED",
      "severity": "info",
      "message": "ETF 분해에서는 매입금액·평가손익을 행에 표시할 수 없습니다",
      "params": {
        "metrics": [
          "avg_cost",
          "cost_amount_krw",
          "unrealized_pnl_krw",
          "unrealized_pnl_pct"
        ]
      }
    },
    {
      "code": "PRICE_LAG_MARKET",
      "severity": "info",
      "message": "미국 종목은 07-24 종가 기준이에요",
      "params": {
        "markets": [
          {
            "market": "US",
            "price_as_of": "2026-07-24",
            "quote_count": 0
          }
        ]
      }
    }
  ]
}
```

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="positions-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[EnvelopeSnapshotViewData](#schemaenvelopesnapshotviewdata)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## GET /portfolio/views/allocation

<a id="opIdallocation"></a>

`GET /portfolio/views/allocation`

<h3 id="allocation-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|axis|query|string|true|none|
|lens|query|string|false|none|
|account|query|array[string]|false|none|
|account_type|query|array[string]|false|none|

> Example responses

> OK

```json
{
  "as_of": "2026-07-27T15:30:00+09:00",
  "data": {
    "group_by": [
      "sector"
    ],
    "lens": "DIRECT",
    "total": {
      "total_assets_krw": 58000000,
      "securities_value_krw": 53300000,
      "deposit_krw": 4700000,
      "cost_amount_krw": 48800000,
      "unrealized_pnl_krw": 4500000,
      "unrealized_pnl_pct": 9.2,
      "cash_ratio_pct": 8.1,
      "instrument_count": 6,
      "account_count": 4
    },
    "rows": [
      {
        "key": "반도체",
        "label": "반도체",
        "market_value_krw": 23240000,
        "cost_amount_krw": 20000000,
        "unrealized_pnl_krw": 3240000,
        "unrealized_pnl_pct": 16.2,
        "weight_pct": 40.1,
        "instrument_count": 2
      },
      {
        "key": "소프트웨어",
        "label": "소프트웨어",
        "market_value_krw": 12900000,
        "cost_amount_krw": 13200000,
        "unrealized_pnl_krw": -300000,
        "unrealized_pnl_pct": -2.3,
        "weight_pct": 22.2,
        "instrument_count": 2
      },
      {
        "key": "UNCLASSIFIED",
        "label": "미분류",
        "market_value_krw": 11000000,
        "cost_amount_krw": 10000000,
        "unrealized_pnl_krw": 1000000,
        "unrealized_pnl_pct": 10,
        "weight_pct": 19,
        "instrument_count": 1
      },
      {
        "key": "IT서비스",
        "label": "IT서비스",
        "currency": "USD",
        "market_value_krw": 6160000,
        "market_value_local": 4400,
        "cost_amount_krw": 5600000,
        "cost_amount_local": 4000,
        "unrealized_pnl_krw": 560000,
        "unrealized_pnl_pct": 10,
        "weight_pct": 10.6,
        "instrument_count": 1
      },
      {
        "key": "CASH",
        "label": "현금",
        "market_value_krw": 4700000,
        "cost_amount_krw": null,
        "unrealized_pnl_krw": null,
        "unrealized_pnl_pct": null,
        "weight_pct": 8.1,
        "instrument_count": 0
      }
    ]
  },
  "empty_reason": null,
  "notices": [
    {
      "code": "FX_APPLIED",
      "severity": "info",
      "message": "USD/KRW 1,400.00 적용 · 기준 2026-07-24",
      "params": {
        "rates": [
          {
            "pair": "USD/KRW",
            "rate": 1400,
            "fx_as_of": "2026-07-24"
          }
        ],
        "oldest_fx_as_of": "2026-07-24"
      }
    },
    {
      "code": "STALE_ACCOUNTS",
      "severity": "warn",
      "message": "1개 계좌가 07-24 기준입니다",
      "params": {
        "count": 1,
        "oldest": "2026-07-24"
      }
    },
    {
      "code": "PRICE_LAG_MARKET",
      "severity": "info",
      "message": "미국 종목은 07-24 종가 기준이에요",
      "params": {
        "markets": [
          {
            "market": "US",
            "price_as_of": "2026-07-24",
            "quote_count": 0
          }
        ]
      }
    }
  ]
}
```

```json
{
  "as_of": "2026-07-27T15:30:00+09:00",
  "data": {
    "group_by": [
      "sector"
    ],
    "lens": "LOOK_THROUGH",
    "total": {
      "total_assets_krw": 60000000,
      "securities_value_krw": 55300000,
      "deposit_krw": 4700000,
      "cost_amount_krw": 50600000,
      "unrealized_pnl_krw": 4700000,
      "unrealized_pnl_pct": 9.3,
      "cash_ratio_pct": 7.8,
      "instrument_count": 6,
      "account_count": 4
    },
    "rows": [
      {
        "key": "반도체",
        "label": "반도체",
        "market_value_krw": 24806400,
        "weight_pct": 41.3,
        "instrument_count": 2
      },
      {
        "key": "소프트웨어",
        "label": "소프트웨어",
        "market_value_krw": 16134000,
        "weight_pct": 26.9,
        "instrument_count": 2
      },
      {
        "key": "IT서비스",
        "label": "IT서비스",
        "currency": "USD",
        "market_value_krw": 11088000,
        "market_value_local": 7920,
        "weight_pct": 18.5,
        "instrument_count": 1
      },
      {
        "key": "CASH",
        "label": "현금",
        "market_value_krw": 4700000,
        "weight_pct": 7.8,
        "instrument_count": 0
      },
      {
        "key": "UNCLASSIFIED",
        "label": "미분류",
        "market_value_krw": 2000000,
        "weight_pct": 3.3,
        "instrument_count": 1
      },
      {
        "key": "OTHER",
        "label": "기타(ETF 내 비주식·미매칭)",
        "market_value_krw": 1271600,
        "weight_pct": 2.1,
        "instrument_count": null
      }
    ]
  },
  "empty_reason": null,
  "notices": [
    {
      "code": "FX_APPLIED",
      "severity": "info",
      "message": "USD/KRW 1,400.00 적용 · 기준 2026-07-24",
      "params": {
        "rates": [
          {
            "pair": "USD/KRW",
            "rate": 1400,
            "fx_as_of": "2026-07-24"
          }
        ],
        "oldest_fx_as_of": "2026-07-24"
      }
    },
    {
      "code": "STALE_ACCOUNTS",
      "severity": "warn",
      "message": "1개 계좌가 07-24 기준입니다",
      "params": {
        "count": 1,
        "oldest": "2026-07-24"
      }
    },
    {
      "code": "CONSTITUENT_AS_OF",
      "severity": "info",
      "message": "구성비중 기준 07-24",
      "params": {
        "oldest": "2026-07-24",
        "count": 1
      }
    },
    {
      "code": "CONSTITUENT_UNAVAILABLE",
      "severity": "warn",
      "message": "1개 ETF는 구성종목으로 나누지 못해 그대로 표시했습니다",
      "params": {
        "count": 1,
        "undecomposed_krw": 2000000,
        "keys": [
          "069500"
        ]
      }
    },
    {
      "code": "LENS_METRICS_OMITTED",
      "severity": "info",
      "message": "ETF 분해에서는 매입금액·평가손익을 행에 표시할 수 없습니다",
      "params": {
        "metrics": [
          "cost_amount_krw",
          "unrealized_pnl_krw",
          "unrealized_pnl_pct"
        ]
      }
    },
    {
      "code": "PRICE_LAG_MARKET",
      "severity": "info",
      "message": "미국 종목은 07-24 종가 기준이에요",
      "params": {
        "markets": [
          {
            "market": "US",
            "price_as_of": "2026-07-24",
            "quote_count": 0
          }
        ]
      }
    }
  ]
}
```

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="allocation-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[EnvelopeSnapshotViewData](#schemaenvelopesnapshotviewdata)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## GET /portfolio/views/accounts

<a id="opIdaccounts"></a>

`GET /portfolio/views/accounts`

<h3 id="accounts-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|lens|query|string|false|none|
|account|query|array[string]|false|none|

> Example responses

> OK

```json
{
  "as_of": "2026-07-27T15:30:00+09:00",
  "data": {
    "group_by": [
      "account_type",
      "account"
    ],
    "lens": "DIRECT",
    "total": {
      "total_assets_krw": 58000000,
      "securities_value_krw": 53300000,
      "deposit_krw": 4700000,
      "cost_amount_krw": 48800000,
      "unrealized_pnl_krw": 4500000,
      "unrealized_pnl_pct": 9.2,
      "cash_ratio_pct": 8.1,
      "instrument_count": 6,
      "account_count": 4
    },
    "rows": [
      {
        "key": "GENERAL",
        "label": "일반",
        "rows": [
          {
            "key": "20000000-0000-0000-0000-000000000001",
            "label": "한국투자 위탁",
            "market_value_krw": 31960000,
            "deposit_krw": 2560000,
            "cost_amount_krw": 25600000,
            "unrealized_pnl_krw": 3800000,
            "unrealized_pnl_pct": 14.8,
            "weight_pct": 55.1,
            "link_state": "CONNECTED",
            "last_collection": null,
            "collection_alert": null,
            "last_synced_at": null,
            "source_as_of": "2026-07-27",
            "is_carried_forward": false
          },
          {
            "key": "20000000-0000-0000-0000-000000000002",
            "label": "국내주식",
            "market_value_krw": 9000000,
            "deposit_krw": 1000000,
            "cost_amount_krw": 9000000,
            "unrealized_pnl_krw": -1000000,
            "unrealized_pnl_pct": -11.1,
            "weight_pct": 15.5,
            "link_state": "CONNECTED",
            "last_collection": null,
            "collection_alert": null,
            "last_synced_at": null,
            "source_as_of": "2026-07-27",
            "is_carried_forward": false
          }
        ],
        "market_value_krw": 40960000,
        "deposit_krw": 3560000,
        "cost_amount_krw": 34600000,
        "unrealized_pnl_krw": 2800000,
        "unrealized_pnl_pct": 8.1,
        "weight_pct": 70.6
      },
      {
        "key": "PENSION",
        "label": "연금",
        "rows": [
          {
            "key": "20000000-0000-0000-0000-000000000003",
            "label": "한국투자 IRP",
            "market_value_krw": 12000000,
            "deposit_krw": 1000000,
            "cost_amount_krw": 10000000,
            "unrealized_pnl_krw": 1000000,
            "unrealized_pnl_pct": 10,
            "weight_pct": 20.7,
            "link_state": "CONNECTED",
            "last_collection": null,
            "collection_alert": null,
            "last_synced_at": null,
            "source_as_of": "2026-07-27",
            "is_carried_forward": false
          },
          {
            "key": "20000000-0000-0000-0000-000000000004",
            "label": "연금저축",
            "currency": "USD",
            "market_value_krw": 5040000,
            "market_value_local": 3600,
            "deposit_krw": 140000,
            "cost_amount_krw": 4200000,
            "cost_amount_local": 3000,
            "unrealized_pnl_krw": 700000,
            "unrealized_pnl_pct": 16.7,
            "weight_pct": 8.7,
            "link_state": "CONNECTED",
            "last_collection": null,
            "collection_alert": null,
            "last_synced_at": null,
            "source_as_of": "2026-07-24",
            "is_carried_forward": true
          }
        ],
        "market_value_krw": 17040000,
        "deposit_krw": 1140000,
        "cost_amount_krw": 14200000,
        "unrealized_pnl_krw": 1700000,
        "unrealized_pnl_pct": 12,
        "weight_pct": 29.4
      }
    ]
  },
  "empty_reason": null,
  "notices": [
    {
      "code": "FX_APPLIED",
      "severity": "info",
      "message": "USD/KRW 1,400.00 적용 · 기준 2026-07-24",
      "params": {
        "rates": [
          {
            "pair": "USD/KRW",
            "rate": 1400,
            "fx_as_of": "2026-07-24"
          }
        ],
        "oldest_fx_as_of": "2026-07-24"
      }
    },
    {
      "code": "STALE_ACCOUNTS",
      "severity": "warn",
      "message": "1개 계좌가 07-24 기준입니다",
      "params": {
        "count": 1,
        "oldest": "2026-07-24"
      }
    },
    {
      "code": "PRICE_LAG_MARKET",
      "severity": "info",
      "message": "미국 종목은 07-24 종가 기준이에요",
      "params": {
        "markets": [
          {
            "market": "US",
            "price_as_of": "2026-07-24",
            "quote_count": 0
          }
        ]
      }
    }
  ]
}
```

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="accounts-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[EnvelopeSnapshotViewData](#schemaenvelopesnapshotviewdata)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">실현손익</h1>

설계서: portfolio.md «실현손익» · «평단과 실현손익»

## GET /portfolio/views/realized-pnl

<a id="opIdrealizedPnl"></a>

`GET /portfolio/views/realized-pnl`

<h3 id="realizedpnl-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|period|query|string|false|none|
|from|query|string(date)|false|none|
|to|query|string(date)|false|none|
|account|query|array[string]|false|none|

> Example responses

> OK

```json
{
  "as_of": "2026-07-27T15:30:00+09:00",
  "data": {
    "period": {
      "from": "2026-01-01",
      "to": "2026-12-31"
    },
    "total": {
      "realized_pnl_krw": -28000,
      "cost_basis_krw": 3120000,
      "realized_pnl_pct": -0.9
    },
    "rows": [
      {
        "key": "005930",
        "label": "삼성전자",
        "sell_amount_krw": 1100000,
        "cost_basis_krw": 820000,
        "realized_pnl_krw": 277000,
        "realized_pnl_pct": 33.8,
        "first_sold_at": "2026-03-02",
        "last_sold_at": "2026-05-12",
        "trade_count": 2,
        "grade": "MIXED",
        "rows": [
          {
            "trade_id": "T-0002",
            "sold_at": "2026-05-12",
            "quantity": 5,
            "sell_amount_krw": 700000,
            "cost_basis_krw": 500000,
            "realized_pnl_krw": 198000,
            "grade": "VERIFIED"
          },
          {
            "trade_id": "T-0001",
            "sold_at": "2026-03-02",
            "quantity": 3,
            "sell_amount_krw": 400000,
            "cost_basis_krw": 320000,
            "realized_pnl_krw": 79000,
            "grade": "SEEDED",
            "seed_reason": "LATE_COVERAGE",
            "coverage_start_at": "2026-01-01"
          }
        ]
      },
      {
        "key": "035420",
        "label": "NAVER",
        "sell_amount_krw": 2250000,
        "cost_basis_krw": 2300000,
        "realized_pnl_krw": -305000,
        "realized_pnl_pct": -13.3,
        "first_sold_at": "2026-02-18",
        "last_sold_at": "2026-04-01",
        "trade_count": 2,
        "grade": "MIXED",
        "rows": [
          {
            "trade_id": "T-0004",
            "sold_at": "2026-04-01",
            "quantity": 1,
            "sell_amount_krw": 250000,
            "cost_basis_krw": null,
            "realized_pnl_krw": null,
            "grade": "CONFLICT"
          },
          {
            "trade_id": "T-0003",
            "sold_at": "2026-02-18",
            "quantity": 10,
            "sell_amount_krw": 2000000,
            "cost_basis_krw": 2300000,
            "realized_pnl_krw": -305000,
            "grade": "VERIFIED"
          }
        ]
      }
    ]
  },
  "empty_reason": null,
  "notices": [
    {
      "code": "EXCLUDED_ACCOUNTS",
      "severity": "warn",
      "message": "1개 계좌의 체결이 합계에서 빠졌습니다",
      "params": {
        "count": 1
      }
    },
    {
      "code": "SEEDED_ROWS",
      "severity": "warn",
      "message": "1개 종목은 취득원가를 추정해 계산했습니다",
      "params": {
        "count": 1
      }
    },
    {
      "code": "CA_UNKNOWN",
      "severity": "warn",
      "message": "1개 종목은 기업행위 이력을 확인하지 못해 손익이 다를 수 있습니다",
      "params": {
        "instrument_ids": [
          "10000000-0000-0000-0000-000000000003"
        ]
      }
    }
  ]
}
```

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="realizedpnl-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[EnvelopeRealizedPnlData](#schemaenveloperealizedpnldata)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">자산 변화</h1>

설계서: portfolio.md «자산 변화» · «자산 변화 항등식과 분해»

## GET /portfolio/views/asset-change

<a id="opIdassetChange"></a>

`GET /portfolio/views/asset-change`

<h3 id="assetchange-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|period|query|string|false|none|
|from|query|string(date)|false|none|
|to|query|string(date)|false|none|
|account|query|array[string]|false|none|

> Example responses

> OK

```json
{
  "as_of": "2026-07-27T15:30:00+09:00",
  "data": {
    "period": {
      "from": "2026-07-01",
      "to": "2026-07-31"
    },
    "opening": 56800000,
    "closing": 58000000,
    "deposited": 2000000,
    "earned": -800000,
    "account_included": 0,
    "account_excluded": 0,
    "breakdown": [
      {
        "type": "DEPOSIT",
        "amount": 2000000
      },
      {
        "type": "INVESTMENT_PNL",
        "amount": -800000
      }
    ],
    "investment_pnl": {
      "total": -800000,
      "realized": null,
      "unrealized_change": null,
      "split_available": false,
      "realized_period": null,
      "realized_link_available": false
    }
  },
  "empty_reason": null,
  "notices": [
    {
      "code": "CASHFLOW_UNCOVERED",
      "severity": "warn",
      "message": "3개 계좌에 입출금이 입력되지 않았고 배당·수수료·세금 내역도 없어 투자손익이 정확하지 않을 수 있어요",
      "params": {
        "types": [
          "DIVIDEND",
          "FEE",
          "TAX",
          "DEPOSIT",
          "WITHDRAW"
        ],
        "account_count": 4,
        "manual_uncovered_account_count": 3
      }
    },
    {
      "code": "PERIOD_TRUNCATED",
      "severity": "info",
      "message": "2026-07-24부터 계산했습니다",
      "params": {
        "actual_from": "2026-07-24"
      }
    },
    {
      "code": "BOUNDARY_CARRIED_FORWARD",
      "severity": "warn",
      "message": "1개 계좌는 기간 경계에서 지난 값을 썼어요",
      "params": {
        "count": 1,
        "boundary": "2026-07-27"
      }
    }
  ]
}
```

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="assetchange-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[EnvelopeAssetChangeData](#schemaenvelopeassetchangedata)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">종목 상세</h1>

설계서: portfolio.md «종목 상세»

## GET /portfolio/instruments/{id}

<a id="opIddetail_1"></a>

`GET /portfolio/instruments/{id}`

<h3 id="detail_1-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|id|path|string|true|none|

> Example responses

> OK

```json
{
  "as_of": "2026-07-27T15:30:00+09:00",
  "data": {
    "instrument": {
      "id": "10000000-0000-0000-0000-000000000001",
      "symbol": "005930",
      "label": "삼성전자",
      "market": "KR",
      "currency": "KRW",
      "delisted_on": null,
      "last_close": 63010,
      "last_close_on": "2026-09-25"
    },
    "position": {
      "quantity": 200,
      "avg_cost": 60000,
      "cost_amount_krw": 12000000,
      "market_value_krw": 14240000,
      "unrealized_pnl_krw": 2240000,
      "unrealized_pnl_pct": 18.7
    },
    "by_account": [
      {
        "account_id": "20000000-0000-0000-0000-000000000001",
        "label": "한국투자 위탁",
        "account_type": "GENERAL",
        "quantity": 200,
        "avg_cost": 60000,
        "market_value_krw": 14240000,
        "is_carried_forward": false,
        "source_as_of": "2026-07-27T15:30:00+09:00",
        "basis": null
      }
    ],
    "realized": {
      "total": {
        "realized_pnl_krw": 277000,
        "excluded_account_count": 0
      },
      "rows": [
        {
          "trade_id": "T-0002",
          "account_id": "20000000-0000-0000-0000-000000000001",
          "account_label": "한국투자 위탁",
          "sold_at": "2026-05-12",
          "quantity": 5,
          "sell_amount_krw": 700000,
          "cost_basis_krw": 500000,
          "realized_pnl_krw": 198000,
          "grade": "VERIFIED",
          "ca_unknown": false
        },
        {
          "trade_id": "T-0001",
          "account_id": "20000000-0000-0000-0000-000000000001",
          "account_label": "한국투자 위탁",
          "sold_at": "2026-03-02",
          "quantity": 3,
          "sell_amount_krw": 400000,
          "cost_basis_krw": 320000,
          "realized_pnl_krw": 79000,
          "grade": "SEEDED",
          "seed_reason": "LATE_COVERAGE",
          "coverage_start_at": "2026-01-01",
          "ca_unknown": false
        }
      ]
    },
    "trades": [],
    "corporate_actions": []
  },
  "empty_reason": null,
  "notices": []
}
```

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="detail_1-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[EnvelopeInstrumentDetailData](#schemaenvelopeinstrumentdetaildata)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">포트폴리오 카탈로그</h1>

화면 · 축 · 지표 정의. 설계서: portfolio.md «화면 사양»

## GET /portfolio/catalog

<a id="opIdcatalog"></a>

`GET /portfolio/catalog`

> Example responses

> 200 Response

```json
{
  "axes": [],
  "metrics": [],
  "views": [],
  "accounts": []
}
```

<h3 id="catalog-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[CatalogDto](#schemacatalogdto)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">입출금</h1>

설계서: portfolio.md «입출금» · «입출금 입력과 미입력 판정»

## PUT /portfolio/cashflows/{id}

<a id="opIdsave"></a>

`PUT /portfolio/cashflows/{id}`

> Body parameter

```json
{}
```

<h3 id="save-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|id|path|string(uuid)|true|none|
|body|body|object|true|none|

> Example responses

> 200 Response

```json
{
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08"
}
```

<h3 id="save-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[CashflowIdResponse](#schemacashflowidresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## DELETE /portfolio/cashflows/{id}

<a id="opIddelete"></a>

`DELETE /portfolio/cashflows/{id}`

<h3 id="delete-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|id|path|string|true|none|

> Example responses

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="delete-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|204|[No Content](https://tools.ietf.org/html/rfc7231#section-6.3.5)|No Content|None|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## GET /portfolio/cashflows

<a id="opIdlist_2"></a>

`GET /portfolio/cashflows`

<h3 id="list_2-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|from|query|string|false|none|
|to|query|string|false|none|
|account|query|array[string]|false|none|

> Example responses

> 200 Response

```json
{
  "window": {},
  "cashflows": []
}
```

<h3 id="list_2-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[CashflowListResponse](#schemacashflowlistresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## GET /portfolio/cashflows/accounts

<a id="opIdaccounts_1"></a>

`GET /portfolio/cashflows/accounts`

> Example responses

> 200 Response

```json
{
  "accounts": []
}
```

<h3 id="accounts_1-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[CashflowAccountsResponse](#schemacashflowaccountsresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">계좌</h1>

연동 · 해제 · 인증 정보 갱신. 설계서: portfolio.md «계좌 연동·동기화»

## PUT /accounts/{accountId}/credentials

<a id="opIdrefresh"></a>

`PUT /accounts/{accountId}/credentials`

> Body parameter

```json
{
  "app_key": "string",
  "app_secret": "string",
  "label": "string"
}
```

<h3 id="refresh-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|accountId|path|string(uuid)|true|none|
|body|body|[RefreshCredentialsRequest](#schemarefreshcredentialsrequest)|true|none|

> Example responses

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="refresh-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|204|[No Content](https://tools.ietf.org/html/rfc7231#section-6.3.5)|No Content|None|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## GET /accounts

<a id="opIdlist_1"></a>

`GET /accounts`

> Example responses

> 200 Response

```json
{
  "accounts": []
}
```

<h3 id="list_1-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[AccountListResponse](#schemaaccountlistresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## POST /accounts

<a id="opIdlink"></a>

`POST /accounts`

> Body parameter

```json
{
  "app_key": "string",
  "app_secret": "string",
  "account_number": "string",
  "env": "string",
  "label": "string"
}
```

<h3 id="link-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[LinkAccountRequest](#schemalinkaccountrequest)|true|none|

> Example responses

> 200 Response

```json
{
  "account_id": "449e7a5c-69d3-4b8a-aaaf-5c9b713ebc65",
  "link_state": "CONNECTING",
  "challenge": {}
}
```

<h3 id="link-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[LinkAccountResponse](#schemalinkaccountresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## DELETE /accounts/{accountId}

<a id="opIdunlink"></a>

`DELETE /accounts/{accountId}`

<h3 id="unlink-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|accountId|path|string(uuid)|true|none|

> Example responses

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="unlink-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|204|[No Content](https://tools.ietf.org/html/rfc7231#section-6.3.5)|No Content|None|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">동기화</h1>

설계서: portfolio.md «동기화»

## POST /sync

<a id="opIdrequest"></a>

`POST /sync`

> Body parameter

```json
{}
```

<h3 id="request-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|object|false|none|

> Example responses

> 200 Response

```json
{
  "run_id": "dded282c-8ebd-44cf-8ba5-9a234973d1ec",
  "message": "string"
}
```

<h3 id="request-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[SyncAcceptedResponse](#schemasyncacceptedresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## GET /sync/{runId}

<a id="opIdfind"></a>

`GET /sync/{runId}`

<h3 id="find-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|runId|path|string|true|none|

> Example responses

> 200 Response

```json
{
  "run_id": "dded282c-8ebd-44cf-8ba5-9a234973d1ec",
  "state": "string",
  "started_at": "2019-08-24T14:15:22Z",
  "finished_at": "2019-08-24T14:15:22Z",
  "failure_reason": "string",
  "accounts": []
}
```

<h3 id="find-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[SyncRunResponse](#schemasyncrunresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">알림</h1>

설계서: alert.md «조건 모델» · «API»

## GET /alerts/{alertId}

<a id="opIddetail"></a>

`GET /alerts/{alertId}`

<h3 id="detail-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|alertId|path|string(uuid)|true|none|

> Example responses

> 200 Response

```json
{
  "alert_id": "c8b0bcf7-1a95-4165-9b1e-665b02ceda9f",
  "name": "string",
  "instrument": {},
  "cadence": "string",
  "notify_mode": "string",
  "cooldown_min": 0,
  "expires_at": "2019-08-24T14:15:22Z",
  "status": "string",
  "trigger_type": "string",
  "trigger_spec": {},
  "summary": {},
  "last_result": "string",
  "unknown_reason": "string",
  "evaluated_as_of": "2019-08-24T14:15:22Z",
  "data_closure": {},
  "recent_events": []
}
```

<h3 id="detail-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[AlertDetailDto](#schemaalertdetaildto)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## PUT /alerts/{alertId}

<a id="opIdupdate"></a>

`PUT /alerts/{alertId}`

> Body parameter

```json
{}
```

<h3 id="update-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|alertId|path|string(uuid)|true|none|
|body|body|object|true|none|

> Example responses

> 200 Response

```json
{
  "alert_id": "c8b0bcf7-1a95-4165-9b1e-665b02ceda9f"
}
```

<h3 id="update-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[AlertIdResponse](#schemaalertidresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## DELETE /alerts/{alertId}

<a id="opIddelete_1"></a>

`DELETE /alerts/{alertId}`

<h3 id="delete_1-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|alertId|path|string(uuid)|true|none|

> Example responses

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="delete_1-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|204|[No Content](https://tools.ietf.org/html/rfc7231#section-6.3.5)|No Content|None|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## GET /alerts

<a id="opIdlist"></a>

`GET /alerts`

> Example responses

> 200 Response

```json
{
  "as_of": "2019-08-24T14:15:22Z",
  "data": {},
  "empty_reason": "string",
  "notices": []
}
```

<h3 id="list-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[EnvelopeAlertListData](#schemaenvelopealertlistdata)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## POST /alerts

<a id="opIdcreate"></a>

`POST /alerts`

> Body parameter

```json
{}
```

<h3 id="create-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|object|true|none|

> Example responses

> 201 Response

```json
{
  "alert_id": "c8b0bcf7-1a95-4165-9b1e-665b02ceda9f"
}
```

<h3 id="create-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|201|[Created](https://tools.ietf.org/html/rfc7231#section-6.3.2)|Created|[AlertIdResponse](#schemaalertidresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## POST /alerts/{alertId}/resume

<a id="opIdresume"></a>

`POST /alerts/{alertId}/resume`

> Body parameter

```json
{}
```

<h3 id="resume-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|alertId|path|string(uuid)|true|none|
|body|body|object|false|none|

> Example responses

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="resume-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|204|[No Content](https://tools.ietf.org/html/rfc7231#section-6.3.5)|No Content|None|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## POST /alerts/{alertId}/pause

<a id="opIdpause"></a>

`POST /alerts/{alertId}/pause`

<h3 id="pause-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|alertId|path|string(uuid)|true|none|

> Example responses

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="pause-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|204|[No Content](https://tools.ietf.org/html/rfc7231#section-6.3.5)|No Content|None|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## POST /alerts/preview

<a id="opIdpreview"></a>

`POST /alerts/preview`

> Body parameter

```json
{}
```

<h3 id="preview-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|object|true|none|

> Example responses

> 200 Response

```json
{
  "valid": true,
  "errors": [],
  "summary": {},
  "current": {},
  "already_satisfied": true,
  "already_fired": true,
  "duplicate_of": "15a4136f-d85d-4645-ade9-a6c6085b348c"
}
```

<h3 id="preview-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[PreviewResponse](#schemapreviewresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">알림 카탈로그</h1>

지표 · 연산자 · 프리셋. 설계서: alert.md «지표 카탈로그»

## GET /alerts/catalog

<a id="opIdcatalog_1"></a>

`GET /alerts/catalog`

> Example responses

> 200 Response

```json
{
  "indicators": [],
  "presets": [],
  "cadence_options": [],
  "transforms": [],
  "operators": []
}
```

<h3 id="catalog_1-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[CatalogResponse](#schemacatalogresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">종목 검색</h1>

설계서: alert.md «종목 검색»

## GET /instruments

<a id="opIdsearch"></a>

`GET /instruments`

<h3 id="search-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|q|query|string|false|none|
|held|query|boolean|false|none|

> Example responses

> 200 Response

```json
{
  "rows": []
}
```

<h3 id="search-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[InstrumentSearchResponse](#schemainstrumentsearchresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">울린 알림</h1>

설계서: alert.md «울린 알림 · 울린 알림 상세»

## POST /alert-events/{eventId}/read

<a id="opIdread"></a>

`POST /alert-events/{eventId}/read`

<h3 id="read-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|eventId|path|string(uuid)|true|none|

> Example responses

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="read-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|204|[No Content](https://tools.ietf.org/html/rfc7231#section-6.3.5)|No Content|None|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## POST /alert-events/read-all

<a id="opIdreadAll"></a>

`POST /alert-events/read-all`

> Example responses

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="readall-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|204|[No Content](https://tools.ietf.org/html/rfc7231#section-6.3.5)|No Content|None|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## GET /alert-events

<a id="opIdlist_3"></a>

`GET /alert-events`

<h3 id="list_3-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|alert_id|query|string|false|none|
|cursor|query|string|false|none|
|limit|query|string|false|none|

> Example responses

> 200 Response

```json
{
  "as_of": "2019-08-24T14:15:22Z",
  "data": {},
  "empty_reason": "string",
  "notices": []
}
```

<h3 id="list_3-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[EnvelopeEventListData](#schemaenvelopeeventlistdata)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## GET /alert-events/{eventId}

<a id="opIddetail_2"></a>

`GET /alert-events/{eventId}`

<h3 id="detail_2-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|eventId|path|string(uuid)|true|none|

> Example responses

> 200 Response

```json
{
  "event_id": "a7a26ff2-e851-45b6-9634-d595f45458b7",
  "title": "string",
  "body": "string",
  "lines": [],
  "as_of": "2019-08-24T14:15:22Z",
  "cadence": "string",
  "market": "string",
  "fired_at": "2019-08-24T14:15:22Z",
  "observed": {},
  "read_at": "2019-08-24T14:15:22Z",
  "alert": {}
}
```

<h3 id="detail_2-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[EventDetailDto](#schemaeventdetaildto)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## GET /alert-events/unread-count

<a id="opIdunreadCount"></a>

`GET /alert-events/unread-count`

> Example responses

> 200 Response

```json
{
  "count": 0
}
```

<h3 id="unreadcount-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[UnreadCountDto](#schemaunreadcountdto)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

<h1 id="-api--">기기</h1>

푸시 수신 기기 등록. 설계서: alert.md «수신 기기 등록»

## POST /devices

<a id="opIdregister"></a>

`POST /devices`

> Body parameter

```json
{
  "expo_push_token": "string",
  "platform": "string"
}
```

<h3 id="register-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|body|body|[DeviceRequest](#schemadevicerequest)|true|none|

> Example responses

> 200 Response

```json
{
  "device_id": "3bafab7b-4400-4bcf-8e6e-09f954699940"
}
```

<h3 id="register-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|OK|[DeviceResponse](#schemadeviceresponse)|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

## DELETE /devices/{deviceId}

<a id="opIdunregister"></a>

`DELETE /devices/{deviceId}`

<h3 id="unregister-parameters">Parameters</h3>

|Name|In|Type|Required|Description|
|---|---|---|---|---|
|deviceId|path|string(uuid)|true|none|

> Example responses

> 401 Response

```json
{
  "error": {}
}
```

<h3 id="unregister-responses">Responses</h3>

|Status|Meaning|Description|Schema|
|---|---|---|---|
|204|[No Content](https://tools.ietf.org/html/rfc7231#section-6.3.5)|No Content|None|
|401|[Unauthorized](https://tools.ietf.org/html/rfc7235#section-3.1)|로그인이 필요하다(토큰 없음 · 만료 · 세션 끝남)|[ApiError](#schemaapierror)|

<aside class="warning">
To perform this operation, you must be authenticated by means of one of the following methods:
bearer
</aside>

# Schemas

<h2 id="tocS_JsonNode">JsonNode</h2>
<!-- backwards compatibility -->
<a id="schemajsonnode"></a>
<a id="schema_JsonNode"></a>
<a id="tocSjsonnode"></a>
<a id="tocsjsonnode"></a>

```json
{}

```

JSON 값. 모양은 설계서가 정한다

### Properties

*None*

<h2 id="tocS_CashflowIdResponse">CashflowIdResponse</h2>
<!-- backwards compatibility -->
<a id="schemacashflowidresponse"></a>
<a id="schema_CashflowIdResponse"></a>
<a id="tocScashflowidresponse"></a>
<a id="tocscashflowidresponse"></a>

```json
{
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|id|string(uuid)|false|none|none|

<h2 id="tocS_AlertIdResponse">AlertIdResponse</h2>
<!-- backwards compatibility -->
<a id="schemaalertidresponse"></a>
<a id="schema_AlertIdResponse"></a>
<a id="tocSalertidresponse"></a>
<a id="tocsalertidresponse"></a>

```json
{
  "alert_id": "c8b0bcf7-1a95-4165-9b1e-665b02ceda9f"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|alert_id|string(uuid)|false|none|none|

<h2 id="tocS_RefreshCredentialsRequest">RefreshCredentialsRequest</h2>
<!-- backwards compatibility -->
<a id="schemarefreshcredentialsrequest"></a>
<a id="schema_RefreshCredentialsRequest"></a>
<a id="tocSrefreshcredentialsrequest"></a>
<a id="tocsrefreshcredentialsrequest"></a>

```json
{
  "app_key": "string",
  "app_secret": "string",
  "label": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|app_key|string|false|none|none|
|app_secret|string|false|none|none|
|label|string|false|none|none|

<h2 id="tocS_SyncAcceptedResponse">SyncAcceptedResponse</h2>
<!-- backwards compatibility -->
<a id="schemasyncacceptedresponse"></a>
<a id="schema_SyncAcceptedResponse"></a>
<a id="tocSsyncacceptedresponse"></a>
<a id="tocssyncacceptedresponse"></a>

```json
{
  "run_id": "dded282c-8ebd-44cf-8ba5-9a234973d1ec",
  "message": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|run_id|string(uuid)|false|none|none|
|message|string|false|none|none|

<h2 id="tocS_DeviceRequest">DeviceRequest</h2>
<!-- backwards compatibility -->
<a id="schemadevicerequest"></a>
<a id="schema_DeviceRequest"></a>
<a id="tocSdevicerequest"></a>
<a id="tocsdevicerequest"></a>

```json
{
  "expo_push_token": "string",
  "platform": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|expo_push_token|string|false|none|none|
|platform|string|false|none|none|

<h2 id="tocS_DeviceResponse">DeviceResponse</h2>
<!-- backwards compatibility -->
<a id="schemadeviceresponse"></a>
<a id="schema_DeviceResponse"></a>
<a id="tocSdeviceresponse"></a>
<a id="tocsdeviceresponse"></a>

```json
{
  "device_id": "3bafab7b-4400-4bcf-8e6e-09f954699940"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|device_id|string(uuid)|false|none|none|

<h2 id="tocS_RefreshRequest">RefreshRequest</h2>
<!-- backwards compatibility -->
<a id="schemarefreshrequest"></a>
<a id="schema_RefreshRequest"></a>
<a id="tocSrefreshrequest"></a>
<a id="tocsrefreshrequest"></a>

```json
{
  "refresh_token": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|refresh_token|string|false|none|none|

<h2 id="tocS_TokenResponse">TokenResponse</h2>
<!-- backwards compatibility -->
<a id="schematokenresponse"></a>
<a id="schema_TokenResponse"></a>
<a id="tocStokenresponse"></a>
<a id="tocstokenresponse"></a>

```json
{
  "access_token": "string",
  "expires_at": "2019-08-24T14:15:22Z",
  "refresh_token": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|access_token|string|false|none|none|
|expires_at|string(date-time)|false|none|none|
|refresh_token|string|false|none|none|

<h2 id="tocS_LoginRequest">LoginRequest</h2>
<!-- backwards compatibility -->
<a id="schemaloginrequest"></a>
<a id="schema_LoginRequest"></a>
<a id="tocSloginrequest"></a>
<a id="tocsloginrequest"></a>

```json
{
  "email": "string",
  "password": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|email|string|false|none|none|
|password|string|false|none|none|

<h2 id="tocS_CurrentDto">CurrentDto</h2>
<!-- backwards compatibility -->
<a id="schemacurrentdto"></a>
<a id="schema_CurrentDto"></a>
<a id="tocScurrentdto"></a>
<a id="tocscurrentdto"></a>

```json
{
  "result": "TRUE",
  "as_of": "2019-08-24T14:15:22Z",
  "header": "string",
  "result_text": "string",
  "conditions": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|result|string|false|none|none|
|as_of|string(date-time)|false|none|none|
|header|string|false|none|none|
|result_text|string|false|none|none|
|conditions|[[LineDto](#schemalinedto)]|false|none|none|

#### Enumerated Values

|Property|Value|
|---|---|
|result|TRUE|
|result|FALSE|
|result|UNKNOWN|

<h2 id="tocS_FieldError">FieldError</h2>
<!-- backwards compatibility -->
<a id="schemafielderror"></a>
<a id="schema_FieldError"></a>
<a id="tocSfielderror"></a>
<a id="tocsfielderror"></a>

```json
{
  "path": "string",
  "code": "string",
  "message": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|path|string|false|none|none|
|code|string|false|none|none|
|message|string|false|none|none|

<h2 id="tocS_LineDto">LineDto</h2>
<!-- backwards compatibility -->
<a id="schemalinedto"></a>
<a id="schema_LineDto"></a>
<a id="tocSlinedto"></a>
<a id="tocslinedto"></a>

```json
{
  "result": "TRUE",
  "unknown_reason": "DATA_MISSING",
  "text": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|result|string|false|none|none|
|unknown_reason|string|false|none|none|
|text|string|false|none|none|

#### Enumerated Values

|Property|Value|
|---|---|
|result|TRUE|
|result|FALSE|
|result|UNKNOWN|
|unknown_reason|DATA_MISSING|
|unknown_reason|INSUFFICIENT_HISTORY|
|unknown_reason|NO_TRADE|
|unknown_reason|PRICE_ADJUSTMENT_SUSPECTED|
|unknown_reason|NOT_HELD|
|unknown_reason|AWAITING_FINAL|
|unknown_reason|INSTRUMENT_UNKNOWN|

<h2 id="tocS_PreviewResponse">PreviewResponse</h2>
<!-- backwards compatibility -->
<a id="schemapreviewresponse"></a>
<a id="schema_PreviewResponse"></a>
<a id="tocSpreviewresponse"></a>
<a id="tocspreviewresponse"></a>

```json
{
  "valid": true,
  "errors": [],
  "summary": {},
  "current": {},
  "already_satisfied": true,
  "already_fired": true,
  "duplicate_of": "15a4136f-d85d-4645-ade9-a6c6085b348c"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|valid|boolean|false|none|none|
|errors|[[FieldError](#schemafielderror)]|false|none|none|

<h2 id="tocS_SummaryDto">SummaryDto</h2>
<!-- backwards compatibility -->
<a id="schemasummarydto"></a>
<a id="schema_SummaryDto"></a>
<a id="tocSsummarydto"></a>
<a id="tocssummarydto"></a>

```json
{
  "short": "string",
  "sentence": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|short|string|false|none|none|
|sentence|string|false|none|none|

<h2 id="tocS_LinkAccountRequest">LinkAccountRequest</h2>
<!-- backwards compatibility -->
<a id="schemalinkaccountrequest"></a>
<a id="schema_LinkAccountRequest"></a>
<a id="tocSlinkaccountrequest"></a>
<a id="tocslinkaccountrequest"></a>

```json
{
  "app_key": "string",
  "app_secret": "string",
  "account_number": "string",
  "env": "string",
  "label": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|app_key|string|false|none|none|
|app_secret|string|false|none|none|
|account_number|string|false|none|none|
|env|string|false|none|none|
|label|string|false|none|none|

<h2 id="tocS_LinkAccountResponse">LinkAccountResponse</h2>
<!-- backwards compatibility -->
<a id="schemalinkaccountresponse"></a>
<a id="schema_LinkAccountResponse"></a>
<a id="tocSlinkaccountresponse"></a>
<a id="tocslinkaccountresponse"></a>

```json
{
  "account_id": "449e7a5c-69d3-4b8a-aaaf-5c9b713ebc65",
  "link_state": "CONNECTING",
  "challenge": {}
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|account_id|string(uuid)|false|none|none|
|link_state|string|false|none|none|
|challenge|object|false|none|none|

#### Enumerated Values

|Property|Value|
|---|---|
|link_state|CONNECTING|
|link_state|CONNECTED|
|link_state|DISCONNECTED|

<h2 id="tocS_SyncAccountDto">SyncAccountDto</h2>
<!-- backwards compatibility -->
<a id="schemasyncaccountdto"></a>
<a id="schema_SyncAccountDto"></a>
<a id="tocSsyncaccountdto"></a>
<a id="tocssyncaccountdto"></a>

```json
{
  "account_id": "449e7a5c-69d3-4b8a-aaaf-5c9b713ebc65",
  "label": "string",
  "state": "string",
  "as_of": "2019-08-24",
  "failure_reason": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|account_id|string(uuid)|false|none|none|
|label|string|false|none|none|
|state|string|false|none|none|
|as_of|string(date)|false|none|none|
|failure_reason|string|false|none|none|

<h2 id="tocS_SyncRunResponse">SyncRunResponse</h2>
<!-- backwards compatibility -->
<a id="schemasyncrunresponse"></a>
<a id="schema_SyncRunResponse"></a>
<a id="tocSsyncrunresponse"></a>
<a id="tocssyncrunresponse"></a>

```json
{
  "run_id": "dded282c-8ebd-44cf-8ba5-9a234973d1ec",
  "state": "string",
  "started_at": "2019-08-24T14:15:22Z",
  "finished_at": "2019-08-24T14:15:22Z",
  "failure_reason": "string",
  "accounts": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|run_id|string(uuid)|false|none|none|
|state|string|false|none|none|
|started_at|string(date-time)|false|none|none|
|finished_at|string(date-time)|false|none|none|
|failure_reason|string|false|none|none|
|accounts|[[SyncAccountDto](#schemasyncaccountdto)]|false|none|none|

<h2 id="tocS_EnvelopeSnapshotViewData">EnvelopeSnapshotViewData</h2>
<!-- backwards compatibility -->
<a id="schemaenvelopesnapshotviewdata"></a>
<a id="schema_EnvelopeSnapshotViewData"></a>
<a id="tocSenvelopesnapshotviewdata"></a>
<a id="tocsenvelopesnapshotviewdata"></a>

```json
{
  "as_of": "2019-08-24T14:15:22Z",
  "data": {},
  "empty_reason": "string",
  "notices": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|as_of|string(date-time)|false|none|none|

<h2 id="tocS_NoticeDto">NoticeDto</h2>
<!-- backwards compatibility -->
<a id="schemanoticedto"></a>
<a id="schema_NoticeDto"></a>
<a id="tocSnoticedto"></a>
<a id="tocsnoticedto"></a>

```json
{
  "code": "FX_APPLIED",
  "severity": "info",
  "message": "string",
  "params": {}
}

```

화면 위 안내 한 건. `message`는 서버가 완성한 문장이고, `params`는 같은 내용을 기계가 읽는 모양이다.

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|code|string|false|none|안내 종류. 앱은 이 값으로 색 · 아이콘 · 다음 동작을 고른다|
|severity|string|false|none|none|
|message|string|false|none|none|
|params|object|false|none|none|
|» **additionalProperties**|object|false|none|none|

#### Enumerated Values

|Property|Value|
|---|---|
|code|FX_APPLIED|
|code|STALE_ACCOUNTS|
|code|CREDENTIAL_INVALID|
|code|REPEATED_FAILURE|
|code|CREDENTIAL_UPDATED|
|code|ACCOUNT_NOT_AGGREGATED|
|code|CONSTITUENT_AS_OF|
|code|CONSTITUENT_UNAVAILABLE|
|code|LENS_METRICS_OMITTED|
|code|EXCLUDED_ACCOUNTS|
|code|SEEDED_ROWS|
|code|CA_UNKNOWN|
|code|CASHFLOW_UNCOVERED|
|code|PERIOD_TRUNCATED|
|code|BOUNDARY_CARRIED_FORWARD|
|code|SYNC_IN_PROGRESS|
|code|PRICE_LAG_MARKET|
|code|ALREADY_FINAL|
|code|FX_STALE|
|severity|info|
|severity|warn|
|severity|error|

<h2 id="tocS_RowDto">RowDto</h2>
<!-- backwards compatibility -->
<a id="schemarowdto"></a>
<a id="schema_RowDto"></a>
<a id="tocSrowdto"></a>
<a id="tocsrowdto"></a>

```json
{
  "key": "string",
  "label": "string",
  "currency": "string",
  "rows": [],
  "quantity": 0,
  "total_assets_krw": 0,
  "securities_value_krw": 0,
  "market_value_krw": 0,
  "deposit_krw": 0,
  "daily_change_krw": 0,
  "daily_change_pct": 0,
  "cost_amount_krw": 0,
  "unrealized_pnl_krw": 0,
  "unrealized_pnl_pct": 0,
  "avg_cost": 0,
  "weight_pct": 0,
  "cash_ratio_pct": 0,
  "instrument_count": 0,
  "account_count": 0,
  "realized_pnl_krw": 0,
  "realized_pnl_pct": 0
}

```

목록의 한 행. 지표는 행에 평탄하게 놓인다. 키가 아예 없으면 그 보기에서 말할 수 없는 값(예: ETF 분해 뒤의 매입금액)이고, 키가 있고 값이 null이면 값이 없는 것이 정상인 경우(예: 예수금 행의 손익)다. 어느 화면에 어떤 지표가 나오는지는 `GET /portfolio/catalog`가 정한다.

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|key|string|false|none|none|
|label|string|false|none|none|
|currency|string|false|none|none|
|rows|[[RowDto](#schemarowdto)]|false|none|[목록의 한 행. 지표는 행에 평탄하게 놓인다. 키가 아예 없으면 그 보기에서 말할 수 없는 값(예: ETF 분해 뒤의 매입금액)이고, 키가 있고 값이 null이면 값이 없는 것이 정상인 경우(예: 예수금 행의 손익)다. 어느 화면에 어떤 지표가 나오는지는 `GET /portfolio/catalog`가 정한다.]|

<h2 id="tocS_SnapshotViewData">SnapshotViewData</h2>
<!-- backwards compatibility -->
<a id="schemasnapshotviewdata"></a>
<a id="schema_SnapshotViewData"></a>
<a id="tocSsnapshotviewdata"></a>
<a id="tocssnapshotviewdata"></a>

```json
{
  "group_by": [],
  "lens": "DIRECT",
  "total": {},
  "rows": [],
  "mini_chart": {}
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|group_by|[string]|false|none|none|
|lens|string|false|none|none|
|total|object|false|none|none|
|» **additionalProperties**|object|false|none|none|
|rows|[[RowDto](#schemarowdto)]|false|none|[목록의 한 행. 지표는 행에 평탄하게 놓인다. 키가 아예 없으면 그 보기에서 말할 수 없는 값(예: ETF 분해 뒤의 매입금액)이고, 키가 있고 값이 null이면 값이 없는 것이 정상인 경우(예: 예수금 행의 손익)다. 어느 화면에 어떤 지표가 나오는지는 `GET /portfolio/catalog`가 정한다.]|

#### Enumerated Values

|Property|Value|
|---|---|
|lens|DIRECT|
|lens|LOOK_THROUGH|

<h2 id="tocS_EnvelopeRealizedPnlData">EnvelopeRealizedPnlData</h2>
<!-- backwards compatibility -->
<a id="schemaenveloperealizedpnldata"></a>
<a id="schema_EnvelopeRealizedPnlData"></a>
<a id="tocSenveloperealizedpnldata"></a>
<a id="tocsenveloperealizedpnldata"></a>

```json
{
  "as_of": "2019-08-24T14:15:22Z",
  "data": {},
  "empty_reason": "string",
  "notices": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|as_of|string(date-time)|false|none|none|

<h2 id="tocS_InstrumentNode">InstrumentNode</h2>
<!-- backwards compatibility -->
<a id="schemainstrumentnode"></a>
<a id="schema_InstrumentNode"></a>
<a id="tocSinstrumentnode"></a>
<a id="tocsinstrumentnode"></a>

```json
{
  "key": "string",
  "label": "string",
  "currency": "string",
  "sell_amount_krw": 0,
  "cost_basis_krw": 0,
  "realized_pnl_krw": 0,
  "realized_pnl_pct": 0,
  "first_sold_at": "2019-08-24",
  "last_sold_at": "2019-08-24",
  "trade_count": 0,
  "grade": "string",
  "rows": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|key|string|false|none|none|
|label|string|false|none|none|
|currency|string|false|none|none|
|sell_amount_krw|number|false|none|none|
|cost_basis_krw|number|false|none|none|
|realized_pnl_krw|number|false|none|none|
|realized_pnl_pct|number|false|none|none|
|first_sold_at|string(date)|false|none|none|
|last_sold_at|string(date)|false|none|none|
|trade_count|integer(int32)|false|none|none|
|grade|string|false|none|none|
|rows|[[TradeNode](#schematradenode)]|false|none|none|

<h2 id="tocS_PeriodDto">PeriodDto</h2>
<!-- backwards compatibility -->
<a id="schemaperioddto"></a>
<a id="schema_PeriodDto"></a>
<a id="tocSperioddto"></a>
<a id="tocsperioddto"></a>

```json
{
  "from": "2019-08-24",
  "to": "2019-08-24"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|from|string(date)|false|none|none|
|to|string(date)|false|none|none|

<h2 id="tocS_RealizedPnlData">RealizedPnlData</h2>
<!-- backwards compatibility -->
<a id="schemarealizedpnldata"></a>
<a id="schema_RealizedPnlData"></a>
<a id="tocSrealizedpnldata"></a>
<a id="tocsrealizedpnldata"></a>

```json
{
  "period": {},
  "total": {},
  "rows": []
}

```

### Properties

*None*

<h2 id="tocS_TradeNode">TradeNode</h2>
<!-- backwards compatibility -->
<a id="schematradenode"></a>
<a id="schema_TradeNode"></a>
<a id="tocStradenode"></a>
<a id="tocstradenode"></a>

```json
{
  "trade_id": "string",
  "sold_at": "2019-08-24",
  "quantity": 0,
  "sell_amount_krw": 0,
  "cost_basis_krw": 0,
  "realized_pnl_krw": 0,
  "grade": "string",
  "seed_reason": "string",
  "coverage_start_at": "2019-08-24"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|trade_id|string|false|none|none|
|sold_at|string(date)|false|none|none|
|quantity|number|false|none|none|
|sell_amount_krw|number|false|none|none|
|cost_basis_krw|number|false|none|none|
|realized_pnl_krw|number|false|none|none|
|grade|string|false|none|none|
|seed_reason|string|false|none|none|
|coverage_start_at|string(date)|false|none|none|

<h2 id="tocS_AssetChangeData">AssetChangeData</h2>
<!-- backwards compatibility -->
<a id="schemaassetchangedata"></a>
<a id="schema_AssetChangeData"></a>
<a id="tocSassetchangedata"></a>
<a id="tocsassetchangedata"></a>

```json
{
  "period": {},
  "opening": 0,
  "closing": 0,
  "deposited": 0,
  "earned": 0,
  "account_included": 0,
  "account_excluded": 0,
  "breakdown": [],
  "investment_pnl": {}
}

```

### Properties

*None*

<h2 id="tocS_BreakdownItem">BreakdownItem</h2>
<!-- backwards compatibility -->
<a id="schemabreakdownitem"></a>
<a id="schema_BreakdownItem"></a>
<a id="tocSbreakdownitem"></a>
<a id="tocsbreakdownitem"></a>

```json
{
  "type": "string",
  "amount": 0
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|type|string|false|none|none|
|amount|number|false|none|none|

<h2 id="tocS_EnvelopeAssetChangeData">EnvelopeAssetChangeData</h2>
<!-- backwards compatibility -->
<a id="schemaenvelopeassetchangedata"></a>
<a id="schema_EnvelopeAssetChangeData"></a>
<a id="tocSenvelopeassetchangedata"></a>
<a id="tocsenvelopeassetchangedata"></a>

```json
{
  "as_of": "2019-08-24T14:15:22Z",
  "data": {},
  "empty_reason": "string",
  "notices": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|as_of|string(date-time)|false|none|none|

<h2 id="tocS_InvestmentPnl">InvestmentPnl</h2>
<!-- backwards compatibility -->
<a id="schemainvestmentpnl"></a>
<a id="schema_InvestmentPnl"></a>
<a id="tocSinvestmentpnl"></a>
<a id="tocsinvestmentpnl"></a>

```json
{
  "total": 0,
  "realized": 0,
  "unrealized_change": 0,
  "split_available": true,
  "realized_period": {},
  "realized_link_available": true
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|total|number|false|none|none|
|realized|number|false|none|none|
|unrealized_change|number|false|none|none|
|split_available|boolean|false|none|none|

<h2 id="tocS_AccountLine">AccountLine</h2>
<!-- backwards compatibility -->
<a id="schemaaccountline"></a>
<a id="schema_AccountLine"></a>
<a id="tocSaccountline"></a>
<a id="tocsaccountline"></a>

```json
{
  "account_id": "449e7a5c-69d3-4b8a-aaaf-5c9b713ebc65",
  "label": "string",
  "account_type": "string",
  "quantity": 0,
  "avg_cost": 0,
  "market_value_krw": 0,
  "market_value_local": 0,
  "is_carried_forward": true,
  "source_as_of": "2019-08-24T14:15:22Z",
  "basis": {}
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|account_id|string(uuid)|false|none|none|
|label|string|false|none|none|
|account_type|string|false|none|none|
|quantity|number|false|none|none|
|avg_cost|number|false|none|none|
|market_value_krw|number|false|none|none|
|market_value_local|number|false|none|none|
|is_carried_forward|boolean|false|none|none|
|source_as_of|string(date-time)|false|none|none|

<h2 id="tocS_Basis">Basis</h2>
<!-- backwards compatibility -->
<a id="schemabasis"></a>
<a id="schema_Basis"></a>
<a id="tocSbasis"></a>
<a id="tocsbasis"></a>

```json
{
  "grade": "string",
  "seed_reason": "string",
  "coverage_start_at": "2019-08-24",
  "ca_unknown": true
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|grade|string|false|none|none|
|seed_reason|string|false|none|none|
|coverage_start_at|string(date)|false|none|none|
|ca_unknown|boolean|false|none|none|

<h2 id="tocS_CorporateAction">CorporateAction</h2>
<!-- backwards compatibility -->
<a id="schemacorporateaction"></a>
<a id="schema_CorporateAction"></a>
<a id="tocScorporateaction"></a>
<a id="tocscorporateaction"></a>

```json
{
  "type": "string",
  "ratio": 0,
  "ex_date": "2019-08-24"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|type|string|false|none|none|
|ratio|number|false|none|none|
|ex_date|string(date)|false|none|none|

<h2 id="tocS_EnvelopeInstrumentDetailData">EnvelopeInstrumentDetailData</h2>
<!-- backwards compatibility -->
<a id="schemaenvelopeinstrumentdetaildata"></a>
<a id="schema_EnvelopeInstrumentDetailData"></a>
<a id="tocSenvelopeinstrumentdetaildata"></a>
<a id="tocsenvelopeinstrumentdetaildata"></a>

```json
{
  "as_of": "2019-08-24T14:15:22Z",
  "data": {},
  "empty_reason": "string",
  "notices": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|as_of|string(date-time)|false|none|none|

<h2 id="tocS_Instrument">Instrument</h2>
<!-- backwards compatibility -->
<a id="schemainstrument"></a>
<a id="schema_Instrument"></a>
<a id="tocSinstrument"></a>
<a id="tocsinstrument"></a>

```json
{
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
  "symbol": "string",
  "label": "string",
  "market": "string",
  "currency": "string",
  "delisted_on": "2019-08-24",
  "last_close": 0,
  "last_close_on": "2019-08-24"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|id|string(uuid)|false|none|none|
|symbol|string|false|none|none|
|label|string|false|none|none|
|market|string|false|none|none|
|currency|string|false|none|none|
|delisted_on|string(date)|false|none|none|
|last_close|number|false|none|none|
|last_close_on|string(date)|false|none|none|

<h2 id="tocS_InstrumentDetailData">InstrumentDetailData</h2>
<!-- backwards compatibility -->
<a id="schemainstrumentdetaildata"></a>
<a id="schema_InstrumentDetailData"></a>
<a id="tocSinstrumentdetaildata"></a>
<a id="tocsinstrumentdetaildata"></a>

```json
{
  "instrument": {},
  "position": {},
  "by_account": [],
  "realized": {},
  "trades": [],
  "corporate_actions": []
}

```

### Properties

*None*

<h2 id="tocS_Position">Position</h2>
<!-- backwards compatibility -->
<a id="schemaposition"></a>
<a id="schema_Position"></a>
<a id="tocSposition"></a>
<a id="tocsposition"></a>

```json
{
  "quantity": 0,
  "avg_cost": 0,
  "cost_amount_krw": 0,
  "market_value_krw": 0,
  "unrealized_pnl_krw": 0,
  "unrealized_pnl_pct": 0,
  "market_value_local": 0,
  "cost_amount_local": 0
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|quantity|number|false|none|none|
|avg_cost|number|false|none|none|
|cost_amount_krw|number|false|none|none|
|market_value_krw|number|false|none|none|
|unrealized_pnl_krw|number|false|none|none|
|unrealized_pnl_pct|number|false|none|none|
|market_value_local|number|false|none|none|
|cost_amount_local|number|false|none|none|

<h2 id="tocS_Realized">Realized</h2>
<!-- backwards compatibility -->
<a id="schemarealized"></a>
<a id="schema_Realized"></a>
<a id="tocSrealized"></a>
<a id="tocsrealized"></a>

```json
{
  "total": {},
  "rows": []
}

```

### Properties

*None*

<h2 id="tocS_RealizedRow">RealizedRow</h2>
<!-- backwards compatibility -->
<a id="schemarealizedrow"></a>
<a id="schema_RealizedRow"></a>
<a id="tocSrealizedrow"></a>
<a id="tocsrealizedrow"></a>

```json
{
  "trade_id": "string",
  "account_id": "449e7a5c-69d3-4b8a-aaaf-5c9b713ebc65",
  "account_label": "string",
  "sold_at": "2019-08-24",
  "quantity": 0,
  "sell_amount_krw": 0,
  "cost_basis_krw": 0,
  "realized_pnl_krw": 0,
  "grade": "string",
  "seed_reason": "string",
  "coverage_start_at": "2019-08-24",
  "ca_unknown": true
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|trade_id|string|false|none|none|
|account_id|string(uuid)|false|none|none|
|account_label|string|false|none|none|
|sold_at|string(date)|false|none|none|
|quantity|number|false|none|none|
|sell_amount_krw|number|false|none|none|
|cost_basis_krw|number|false|none|none|
|realized_pnl_krw|number|false|none|none|
|grade|string|false|none|none|
|seed_reason|string|false|none|none|
|coverage_start_at|string(date)|false|none|none|
|ca_unknown|boolean|false|none|none|

<h2 id="tocS_Total">Total</h2>
<!-- backwards compatibility -->
<a id="schematotal"></a>
<a id="schema_Total"></a>
<a id="tocStotal"></a>
<a id="tocstotal"></a>

```json
{
  "realized_pnl_krw": 0,
  "excluded_account_count": 0
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|realized_pnl_krw|number|false|none|none|
|excluded_account_count|integer(int32)|false|none|none|

<h2 id="tocS_Trade">Trade</h2>
<!-- backwards compatibility -->
<a id="schematrade"></a>
<a id="schema_Trade"></a>
<a id="tocStrade"></a>
<a id="tocstrade"></a>

```json
{
  "trade_id": "string",
  "account_id": "449e7a5c-69d3-4b8a-aaaf-5c9b713ebc65",
  "account_label": "string",
  "side": "string",
  "quantity": 0,
  "price": 0,
  "fee": 0,
  "tax": 0,
  "currency": "string",
  "executed_at": "2019-08-24T14:15:22Z",
  "executed_on": "2019-08-24"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|trade_id|string|false|none|none|
|account_id|string(uuid)|false|none|none|
|account_label|string|false|none|none|
|side|string|false|none|none|
|quantity|number|false|none|none|
|price|number|false|none|none|
|fee|number|false|none|none|
|tax|number|false|none|none|
|currency|string|false|none|none|
|executed_at|string(date-time)|false|none|none|
|executed_on|string(date)|false|none|none|

<h2 id="tocS_Account">Account</h2>
<!-- backwards compatibility -->
<a id="schemaaccount"></a>
<a id="schema_Account"></a>
<a id="tocSaccount"></a>
<a id="tocsaccount"></a>

```json
{
  "account_id": "449e7a5c-69d3-4b8a-aaaf-5c9b713ebc65",
  "broker": "string",
  "label": "string",
  "account_type": "string",
  "link_state": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|account_id|string(uuid)|false|none|none|
|broker|string|false|none|none|
|label|string|false|none|none|
|account_type|string|false|none|none|
|link_state|string|false|none|none|

<h2 id="tocS_Axis">Axis</h2>
<!-- backwards compatibility -->
<a id="schemaaxis"></a>
<a id="schema_Axis"></a>
<a id="tocSaxis"></a>
<a id="tocsaxis"></a>

```json
{
  "key": "string",
  "label": "string",
  "lens_sensitive": true,
  "enabled": true,
  "applicable_views": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|key|string|false|none|none|
|label|string|false|none|none|
|lens_sensitive|boolean|false|none|none|
|enabled|boolean|false|none|none|
|applicable_views|[string]|false|none|none|

<h2 id="tocS_CatalogDto">CatalogDto</h2>
<!-- backwards compatibility -->
<a id="schemacatalogdto"></a>
<a id="schema_CatalogDto"></a>
<a id="tocScatalogdto"></a>
<a id="tocscatalogdto"></a>

```json
{
  "axes": [],
  "metrics": [],
  "views": [],
  "accounts": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|axes|[[Axis](#schemaaxis)]|false|none|none|

<h2 id="tocS_Metric">Metric</h2>
<!-- backwards compatibility -->
<a id="schemametric"></a>
<a id="schema_Metric"></a>
<a id="tocSmetric"></a>
<a id="tocsmetric"></a>

```json
{
  "key": "string",
  "label": "string",
  "additive": true,
  "cash_scope": "string",
  "lens_safe": "string",
  "scope": "string",
  "formula": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|key|string|false|none|none|
|label|string|false|none|none|
|additive|boolean|false|none|none|
|cash_scope|string|false|none|none|
|lens_safe|string|false|none|none|
|scope|string|false|none|none|
|formula|string|false|none|none|

<h2 id="tocS_SubBlock">SubBlock</h2>
<!-- backwards compatibility -->
<a id="schemasubblock"></a>
<a id="schema_SubBlock"></a>
<a id="tocSsubblock"></a>
<a id="tocssubblock"></a>

```json
{
  "name": "string",
  "group_by": [],
  "lens_policy": "string",
  "metrics": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|name|string|false|none|none|
|group_by|[string]|false|none|none|
|lens_policy|string|false|none|none|
|metrics|[string]|false|none|none|

<h2 id="tocS_View">View</h2>
<!-- backwards compatibility -->
<a id="schemaview"></a>
<a id="schema_View"></a>
<a id="tocSview"></a>
<a id="tocsview"></a>

```json
{
  "view_key": "string",
  "question": "string",
  "grain": "string",
  "group_by": [],
  "axis_options": [],
  "metrics": [],
  "row_fields": [],
  "filters": {},
  "lens_policy": "string",
  "sub_blocks": [],
  "ledgers": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|view_key|string|false|none|none|
|question|string|false|none|none|
|grain|string|false|none|none|
|group_by|[string]|false|none|none|
|axis_options|[string]|false|none|none|
|metrics|[string]|false|none|none|
|row_fields|[string]|false|none|none|
|filters|object|false|none|none|
|» **additionalProperties**|[string]|false|none|none|
|lens_policy|string|false|none|none|
|sub_blocks|[[SubBlock](#schemasubblock)]|false|none|none|

<h2 id="tocS_CashflowListResponse">CashflowListResponse</h2>
<!-- backwards compatibility -->
<a id="schemacashflowlistresponse"></a>
<a id="schema_CashflowListResponse"></a>
<a id="tocScashflowlistresponse"></a>
<a id="tocscashflowlistresponse"></a>

```json
{
  "window": {},
  "cashflows": []
}

```

### Properties

*None*

<h2 id="tocS_Item">Item</h2>
<!-- backwards compatibility -->
<a id="schemaitem"></a>
<a id="schema_Item"></a>
<a id="tocSitem"></a>
<a id="tocsitem"></a>

```json
{
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
  "account_id": "449e7a5c-69d3-4b8a-aaaf-5c9b713ebc65",
  "account_label": "string",
  "type": "DEPOSIT",
  "amount": 0,
  "currency": "string",
  "occurred_on": "2019-08-24",
  "memo": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|id|string(uuid)|false|none|none|
|account_id|string(uuid)|false|none|none|
|account_label|string|false|none|none|
|type|string|false|none|none|
|amount|number|false|none|none|
|currency|string|false|none|none|
|occurred_on|string(date)|false|none|none|
|memo|string|false|none|none|

#### Enumerated Values

|Property|Value|
|---|---|
|type|DEPOSIT|
|type|WITHDRAW|

<h2 id="tocS_Window">Window</h2>
<!-- backwards compatibility -->
<a id="schemawindow"></a>
<a id="schema_Window"></a>
<a id="tocSwindow"></a>
<a id="tocswindow"></a>

```json
{
  "after": "2019-08-24",
  "through": "2019-08-24"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|after|string(date)|false|none|none|
|through|string(date)|false|none|none|

<h2 id="tocS_CashflowAccountsResponse">CashflowAccountsResponse</h2>
<!-- backwards compatibility -->
<a id="schemacashflowaccountsresponse"></a>
<a id="schema_CashflowAccountsResponse"></a>
<a id="tocScashflowaccountsresponse"></a>
<a id="tocscashflowaccountsresponse"></a>

```json
{
  "accounts": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|accounts|[[Item](#schemaitem)]|false|none|none|

<h2 id="tocS_InstrumentSearchResponse">InstrumentSearchResponse</h2>
<!-- backwards compatibility -->
<a id="schemainstrumentsearchresponse"></a>
<a id="schema_InstrumentSearchResponse"></a>
<a id="tocSinstrumentsearchresponse"></a>
<a id="tocsinstrumentsearchresponse"></a>

```json
{
  "rows": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|rows|[[Row](#schemarow)]|false|none|none|

<h2 id="tocS_Row">Row</h2>
<!-- backwards compatibility -->
<a id="schemarow"></a>
<a id="schema_Row"></a>
<a id="tocSrow"></a>
<a id="tocsrow"></a>

```json
{
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
  "label": "string",
  "symbol": "string",
  "market": "string",
  "held": true,
  "last_close": 0,
  "last_close_on": "2019-08-24"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|id|string(uuid)|false|none|none|
|label|string|false|none|none|
|symbol|string|false|none|none|
|market|string|false|none|none|
|held|boolean|false|none|none|
|last_close|number|false|none|none|
|last_close_on|string(date)|false|none|none|

<h2 id="tocS_MeResponse">MeResponse</h2>
<!-- backwards compatibility -->
<a id="schemameresponse"></a>
<a id="schema_MeResponse"></a>
<a id="tocSmeresponse"></a>
<a id="tocsmeresponse"></a>

```json
{
  "user_id": "a169451c-8525-4352-b8ca-070dd449a1a5",
  "email": "string",
  "display_name": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|user_id|string(uuid)|false|none|none|
|email|string|false|none|none|
|display_name|string|false|none|none|

<h2 id="tocS_AlertCardDto">AlertCardDto</h2>
<!-- backwards compatibility -->
<a id="schemaalertcarddto"></a>
<a id="schema_AlertCardDto"></a>
<a id="tocSalertcarddto"></a>
<a id="tocsalertcarddto"></a>

```json
{
  "alert_id": "c8b0bcf7-1a95-4165-9b1e-665b02ceda9f",
  "name": "string",
  "instrument": {},
  "cadence": "string",
  "notify_mode": "string",
  "status": "string",
  "expires_at": "2019-08-24T14:15:22Z",
  "summary": {},
  "last_result": "string",
  "unknown_reason": "string",
  "evaluated_as_of": "2019-08-24T14:15:22Z",
  "last_fired_at": "2019-08-24T14:15:22Z",
  "data_closure": {}
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|alert_id|string(uuid)|false|none|none|
|name|string|false|none|none|

<h2 id="tocS_AlertListData">AlertListData</h2>
<!-- backwards compatibility -->
<a id="schemaalertlistdata"></a>
<a id="schema_AlertListData"></a>
<a id="tocSalertlistdata"></a>
<a id="tocsalertlistdata"></a>

```json
{
  "rows": [],
  "unread": [],
  "unread_more": 0
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|rows|[[AlertCardDto](#schemaalertcarddto)]|false|none|none|

<h2 id="tocS_DataClosureDto">DataClosureDto</h2>
<!-- backwards compatibility -->
<a id="schemadataclosuredto"></a>
<a id="schema_DataClosureDto"></a>
<a id="tocSdataclosuredto"></a>
<a id="tocsdataclosuredto"></a>

```json
{
  "kind": "string",
  "message": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|kind|string|false|none|none|
|message|string|false|none|none|

<h2 id="tocS_EnvelopeAlertListData">EnvelopeAlertListData</h2>
<!-- backwards compatibility -->
<a id="schemaenvelopealertlistdata"></a>
<a id="schema_EnvelopeAlertListData"></a>
<a id="tocSenvelopealertlistdata"></a>
<a id="tocsenvelopealertlistdata"></a>

```json
{
  "as_of": "2019-08-24T14:15:22Z",
  "data": {},
  "empty_reason": "string",
  "notices": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|as_of|string(date-time)|false|none|none|

<h2 id="tocS_InstrumentDto">InstrumentDto</h2>
<!-- backwards compatibility -->
<a id="schemainstrumentdto"></a>
<a id="schema_InstrumentDto"></a>
<a id="tocSinstrumentdto"></a>
<a id="tocsinstrumentdto"></a>

```json
{
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
  "label": "string",
  "market": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|id|string(uuid)|false|none|none|
|label|string|false|none|none|
|market|string|false|none|none|

<h2 id="tocS_ShortSummaryDto">ShortSummaryDto</h2>
<!-- backwards compatibility -->
<a id="schemashortsummarydto"></a>
<a id="schema_ShortSummaryDto"></a>
<a id="tocSshortsummarydto"></a>
<a id="tocsshortsummarydto"></a>

```json
{
  "short": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|short|string|false|none|none|

<h2 id="tocS_UnreadDto">UnreadDto</h2>
<!-- backwards compatibility -->
<a id="schemaunreaddto"></a>
<a id="schema_UnreadDto"></a>
<a id="tocSunreaddto"></a>
<a id="tocsunreaddto"></a>

```json
{
  "event_id": "a7a26ff2-e851-45b6-9634-d595f45458b7",
  "title": "string",
  "cadence": "string",
  "market": "string",
  "as_of": "2019-08-24T14:15:22Z",
  "fired_at": "2019-08-24T14:15:22Z",
  "alert_deleted": true
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|event_id|string(uuid)|false|none|none|
|title|string|false|none|none|
|cadence|string|false|none|none|
|market|string|false|none|none|
|as_of|string(date-time)|false|none|none|
|fired_at|string(date-time)|false|none|none|
|alert_deleted|boolean|false|none|none|

<h2 id="tocS_AlertDetailDto">AlertDetailDto</h2>
<!-- backwards compatibility -->
<a id="schemaalertdetaildto"></a>
<a id="schema_AlertDetailDto"></a>
<a id="tocSalertdetaildto"></a>
<a id="tocsalertdetaildto"></a>

```json
{
  "alert_id": "c8b0bcf7-1a95-4165-9b1e-665b02ceda9f",
  "name": "string",
  "instrument": {},
  "cadence": "string",
  "notify_mode": "string",
  "cooldown_min": 0,
  "expires_at": "2019-08-24T14:15:22Z",
  "status": "string",
  "trigger_type": "string",
  "trigger_spec": {},
  "summary": {},
  "last_result": "string",
  "unknown_reason": "string",
  "evaluated_as_of": "2019-08-24T14:15:22Z",
  "data_closure": {},
  "recent_events": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|alert_id|string(uuid)|false|none|none|
|name|string|false|none|none|

<h2 id="tocS_RecentEventDto">RecentEventDto</h2>
<!-- backwards compatibility -->
<a id="schemarecenteventdto"></a>
<a id="schema_RecentEventDto"></a>
<a id="tocSrecenteventdto"></a>
<a id="tocsrecenteventdto"></a>

```json
{
  "event_id": "a7a26ff2-e851-45b6-9634-d595f45458b7",
  "title": "string",
  "as_of": "2019-08-24T14:15:22Z",
  "cadence": "string",
  "read": true
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|event_id|string(uuid)|false|none|none|
|title|string|false|none|none|
|as_of|string(date-time)|false|none|none|
|cadence|string|false|none|none|
|read|boolean|false|none|none|

<h2 id="tocS_CadenceOptionDto">CadenceOptionDto</h2>
<!-- backwards compatibility -->
<a id="schemacadenceoptiondto"></a>
<a id="schema_CadenceOptionDto"></a>
<a id="tocScadenceoptiondto"></a>
<a id="tocscadenceoptiondto"></a>

```json
{
  "key": "string",
  "available": true,
  "unavailable_reason": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|key|string|false|none|none|
|available|boolean|false|none|none|
|unavailable_reason|string|false|none|none|

<h2 id="tocS_CatalogResponse">CatalogResponse</h2>
<!-- backwards compatibility -->
<a id="schemacatalogresponse"></a>
<a id="schema_CatalogResponse"></a>
<a id="tocScatalogresponse"></a>
<a id="tocscatalogresponse"></a>

```json
{
  "indicators": [],
  "presets": [],
  "cadence_options": [],
  "transforms": [],
  "operators": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|indicators|[[IndicatorDto](#schemaindicatordto)]|false|none|none|

<h2 id="tocS_FnDto">FnDto</h2>
<!-- backwards compatibility -->
<a id="schemafndto"></a>
<a id="schema_FnDto"></a>
<a id="tocSfndto"></a>
<a id="tocsfndto"></a>

```json
{
  "key": "string",
  "label": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|key|string|false|none|none|
|label|string|false|none|none|

<h2 id="tocS_IndicatorDto">IndicatorDto</h2>
<!-- backwards compatibility -->
<a id="schemaindicatordto"></a>
<a id="schema_IndicatorDto"></a>
<a id="tocSindicatordto"></a>
<a id="tocsindicatordto"></a>

```json
{
  "key": "string",
  "label": "string",
  "category": "string",
  "unit": "string",
  "params": [],
  "intraday_left": true,
  "markets": [],
  "allowed_transforms": [],
  "transform_ranges": {},
  "allowed_operators": [],
  "scope": "string",
  "deprecated": true,
  "available": true,
  "unavailable_reason": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|key|string|false|none|none|
|label|string|false|none|none|
|category|string|false|none|none|
|unit|string|false|none|none|
|params|[[ParamDto](#schemaparamdto)]|false|none|none|
|allowed_operators|[string]|false|none|none|
|scope|string|false|none|none|
|deprecated|boolean|false|none|none|
|available|boolean|false|none|none|
|unavailable_reason|string|false|none|none|

<h2 id="tocS_OperatorDto">OperatorDto</h2>
<!-- backwards compatibility -->
<a id="schemaoperatordto"></a>
<a id="schema_OperatorDto"></a>
<a id="tocSoperatordto"></a>
<a id="tocsoperatordto"></a>

```json
{
  "key": "string",
  "symbol": "string",
  "word": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|key|string|false|none|none|
|symbol|string|false|none|none|
|word|string|false|none|none|

<h2 id="tocS_ParamDto">ParamDto</h2>
<!-- backwards compatibility -->
<a id="schemaparamdto"></a>
<a id="schema_ParamDto"></a>
<a id="tocSparamdto"></a>
<a id="tocsparamdto"></a>

```json
{
  "key": "string",
  "default": 0,
  "min": 0,
  "max": 0
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|key|string|false|none|none|
|default|integer(int32)|false|none|none|
|min|integer(int32)|false|none|none|
|max|integer(int32)|false|none|none|

<h2 id="tocS_PresetDto">PresetDto</h2>
<!-- backwards compatibility -->
<a id="schemapresetdto"></a>
<a id="schema_PresetDto"></a>
<a id="tocSpresetdto"></a>
<a id="tocspresetdto"></a>

```json
{
  "key": "string",
  "label": "string",
  "cadences": [],
  "markets": [],
  "scope": "string",
  "param_schema": [],
  "available": true,
  "unavailable_reason": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|key|string|false|none|none|
|label|string|false|none|none|
|cadences|[string]|false|none|none|
|markets|[string]|false|none|none|
|scope|string|false|none|none|
|param_schema|[[PresetParamDto](#schemapresetparamdto)]|false|none|none|

<h2 id="tocS_PresetParamDto">PresetParamDto</h2>
<!-- backwards compatibility -->
<a id="schemapresetparamdto"></a>
<a id="schema_PresetParamDto"></a>
<a id="tocSpresetparamdto"></a>
<a id="tocspresetparamdto"></a>

```json
{
  "key": "string",
  "kind": "string",
  "min": {},
  "max": {},
  "default": {},
  "choices": [],
  "required": true
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|key|string|false|none|none|
|kind|string|false|none|none|
|min|object|false|none|none|
|max|object|false|none|none|
|default|object|false|none|none|
|choices|[string]|false|none|none|
|required|boolean|false|none|none|

<h2 id="tocS_RangeDto">RangeDto</h2>
<!-- backwards compatibility -->
<a id="schemarangedto"></a>
<a id="schema_RangeDto"></a>
<a id="tocSrangedto"></a>
<a id="tocsrangedto"></a>

```json
{
  "min": 0,
  "max": 0
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|min|integer(int32)|false|none|none|
|max|integer(int32)|false|none|none|

<h2 id="tocS_TransformDto">TransformDto</h2>
<!-- backwards compatibility -->
<a id="schematransformdto"></a>
<a id="schema_TransformDto"></a>
<a id="tocStransformdto"></a>
<a id="tocstransformdto"></a>

```json
{
  "key": "string",
  "label": "string",
  "fns": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|key|string|false|none|none|
|label|string|false|none|none|
|fns|[[FnDto](#schemafndto)]|false|none|none|

<h2 id="tocS_EnvelopeEventListData">EnvelopeEventListData</h2>
<!-- backwards compatibility -->
<a id="schemaenvelopeeventlistdata"></a>
<a id="schema_EnvelopeEventListData"></a>
<a id="tocSenvelopeeventlistdata"></a>
<a id="tocsenvelopeeventlistdata"></a>

```json
{
  "as_of": "2019-08-24T14:15:22Z",
  "data": {},
  "empty_reason": "string",
  "notices": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|as_of|string(date-time)|false|none|none|

<h2 id="tocS_EventListData">EventListData</h2>
<!-- backwards compatibility -->
<a id="schemaeventlistdata"></a>
<a id="schema_EventListData"></a>
<a id="tocSeventlistdata"></a>
<a id="tocseventlistdata"></a>

```json
{
  "rows": [],
  "next_cursor": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|rows|[[EventRowDto](#schemaeventrowdto)]|false|none|none|

<h2 id="tocS_EventRowDto">EventRowDto</h2>
<!-- backwards compatibility -->
<a id="schemaeventrowdto"></a>
<a id="schema_EventRowDto"></a>
<a id="tocSeventrowdto"></a>
<a id="tocseventrowdto"></a>

```json
{
  "event_id": "a7a26ff2-e851-45b6-9634-d595f45458b7",
  "alert_id": "c8b0bcf7-1a95-4165-9b1e-665b02ceda9f",
  "title": "string",
  "body": "string",
  "cadence": "string",
  "market": "string",
  "as_of": "2019-08-24T14:15:22Z",
  "fired_at": "2019-08-24T14:15:22Z",
  "read": true,
  "alert_deleted": true
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|event_id|string(uuid)|false|none|none|
|alert_id|string(uuid)|false|none|none|
|title|string|false|none|none|
|body|string|false|none|none|
|cadence|string|false|none|none|
|market|string|false|none|none|
|as_of|string(date-time)|false|none|none|
|fired_at|string(date-time)|false|none|none|
|read|boolean|false|none|none|
|alert_deleted|boolean|false|none|none|

<h2 id="tocS_EventAlertDto">EventAlertDto</h2>
<!-- backwards compatibility -->
<a id="schemaeventalertdto"></a>
<a id="schema_EventAlertDto"></a>
<a id="tocSeventalertdto"></a>
<a id="tocseventalertdto"></a>

```json
{
  "alert_id": "c8b0bcf7-1a95-4165-9b1e-665b02ceda9f",
  "name": "string",
  "cadence": "string",
  "notify_mode": "string",
  "status": "string",
  "last_result": "string",
  "unknown_reason": "string",
  "deleted": true,
  "data_closure": {},
  "instrument": {}
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|alert_id|string(uuid)|false|none|none|
|name|string|false|none|none|
|cadence|string|false|none|none|
|notify_mode|string|false|none|none|
|status|string|false|none|none|
|last_result|string|false|none|none|
|unknown_reason|string|false|none|none|
|deleted|boolean|false|none|none|

<h2 id="tocS_EventDetailDto">EventDetailDto</h2>
<!-- backwards compatibility -->
<a id="schemaeventdetaildto"></a>
<a id="schema_EventDetailDto"></a>
<a id="tocSeventdetaildto"></a>
<a id="tocseventdetaildto"></a>

```json
{
  "event_id": "a7a26ff2-e851-45b6-9634-d595f45458b7",
  "title": "string",
  "body": "string",
  "lines": [],
  "as_of": "2019-08-24T14:15:22Z",
  "cadence": "string",
  "market": "string",
  "fired_at": "2019-08-24T14:15:22Z",
  "observed": {},
  "read_at": "2019-08-24T14:15:22Z",
  "alert": {}
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|event_id|string(uuid)|false|none|none|
|title|string|false|none|none|
|body|string|false|none|none|
|lines|[string]|false|none|none|
|as_of|string(date-time)|false|none|none|
|cadence|string|false|none|none|
|market|string|false|none|none|
|fired_at|string(date-time)|false|none|none|

<h2 id="tocS_EventInstrumentDto">EventInstrumentDto</h2>
<!-- backwards compatibility -->
<a id="schemaeventinstrumentdto"></a>
<a id="schema_EventInstrumentDto"></a>
<a id="tocSeventinstrumentdto"></a>
<a id="tocseventinstrumentdto"></a>

```json
{
  "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
  "label": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|id|string(uuid)|false|none|none|
|label|string|false|none|none|

<h2 id="tocS_UnreadCountDto">UnreadCountDto</h2>
<!-- backwards compatibility -->
<a id="schemaunreadcountdto"></a>
<a id="schema_UnreadCountDto"></a>
<a id="tocSunreadcountdto"></a>
<a id="tocsunreadcountdto"></a>

```json
{
  "count": 0
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|count|integer(int32)|false|none|none|

<h2 id="tocS_AccountDto">AccountDto</h2>
<!-- backwards compatibility -->
<a id="schemaaccountdto"></a>
<a id="schema_AccountDto"></a>
<a id="tocSaccountdto"></a>
<a id="tocsaccountdto"></a>

```json
{
  "account_id": "449e7a5c-69d3-4b8a-aaaf-5c9b713ebc65",
  "broker": "string",
  "label": "string",
  "account_type": "GENERAL",
  "source": "string",
  "env": "REAL",
  "account_number_masked": "string",
  "link_state": "CONNECTING",
  "last_synced_at": "2019-08-24T14:15:22Z",
  "last_collection": {},
  "collection_alert": {}
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|account_id|string(uuid)|false|none|none|
|broker|string|false|none|none|
|label|string|false|none|none|
|account_type|string|false|none|none|
|source|string|false|none|none|
|env|string|false|none|none|
|account_number_masked|string|false|none|none|
|link_state|string|false|none|none|
|last_synced_at|string(date-time)|false|none|none|

#### Enumerated Values

|Property|Value|
|---|---|
|account_type|GENERAL|
|account_type|PENSION|
|env|REAL|
|env|DEMO|
|link_state|CONNECTING|
|link_state|CONNECTED|
|link_state|DISCONNECTED|

<h2 id="tocS_AccountListResponse">AccountListResponse</h2>
<!-- backwards compatibility -->
<a id="schemaaccountlistresponse"></a>
<a id="schema_AccountListResponse"></a>
<a id="tocSaccountlistresponse"></a>
<a id="tocsaccountlistresponse"></a>

```json
{
  "accounts": []
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|accounts|[[AccountDto](#schemaaccountdto)]|false|none|none|

<h2 id="tocS_CollectionAlert">CollectionAlert</h2>
<!-- backwards compatibility -->
<a id="schemacollectionalert"></a>
<a id="schema_CollectionAlert"></a>
<a id="tocScollectionalert"></a>
<a id="tocscollectionalert"></a>

```json
{
  "code": "string",
  "failed_days": 0,
  "next_pickup_at": "2019-08-24T14:15:22Z"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|code|string|false|none|none|
|failed_days|integer(int32)|false|none|none|
|next_pickup_at|string(date-time)|false|none|none|

<h2 id="tocS_CollectionStatus">CollectionStatus</h2>
<!-- backwards compatibility -->
<a id="schemacollectionstatus"></a>
<a id="schema_CollectionStatus"></a>
<a id="tocScollectionstatus"></a>
<a id="tocscollectionstatus"></a>

```json
{
  "state": "string",
  "as_of": "2019-08-24",
  "failure_reason": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|state|string|false|none|none|
|as_of|string(date)|false|none|none|
|failure_reason|string|false|none|none|

<h2 id="tocS_ApiError">ApiError</h2>
<!-- backwards compatibility -->
<a id="schemaapierror"></a>
<a id="schema_ApiError"></a>
<a id="tocSapierror"></a>
<a id="tocsapierror"></a>

```json
{
  "error": {}
}

```

오류 응답. 화면은 `error.code`로 분기하고 `error.message`를 그대로 보인다.

### Properties

*None*

<h2 id="tocS_Detail">Detail</h2>
<!-- backwards compatibility -->
<a id="schemadetail"></a>
<a id="schema_Detail"></a>
<a id="tocSdetail"></a>
<a id="tocsdetail"></a>

```json
{
  "code": "string",
  "message": "string"
}

```

### Properties

|Name|Type|Required|Restrictions|Description|
|---|---|---|---|---|
|code|string|false|none|none|
|message|string|false|none|none|

