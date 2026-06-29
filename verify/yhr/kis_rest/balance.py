#!/usr/bin/env python3
"""
한국투자증권(KIS) OpenAPI 잔고/체결 응답 구조 검증 스크립트.

보안:
  - App Key / Secret / 토큰은 환경변수로만 읽는다. 코드/로그/저장소에 절대 적지 않는다.
  - 콘솔 출력 시 계좌번호·키·토큰 등 민감정보는 마스킹한다.

사용법(키는 네가 직접 셸에서 export):
  export KIS_ENV=real                      # real(실전) | demo(모의)
  export KIS_APP_KEY=...                    # 발급받은 App Key
  export KIS_APP_SECRET=...                 # 발급받은 App Secret
  export KIS_CANO=12345678                  # 계좌 앞 8자리
  export KIS_ACNT_PRDT_CD=01                # 계좌 뒤 2자리
  python3 verify/yhr/kis_rest/balance.py

토큰은 ./.kis_token.json 에 캐시한다(유효시간 1일). 이 파일은 .gitignore 에 추가할 것.
"""
import os
import sys
import json
import time
import datetime as dt
import urllib.request
import urllib.error

# ---- 도메인 (공식) -----------------------------------------------------------
DOMAINS = {
    "real": "https://openapi.koreainvestment.com:9443",
    "demo": "https://openapivts.koreainvestment.com:29443",
}
# ---- TR ID (env별) -----------------------------------------------------------
TR = {
    "balance_dom":   {"real": "TTTC8434R", "demo": "VTTC8434R"},  # 일반 주식잔고조회
    "psbl_order":    {"real": "TTTC8908R", "demo": "VTTC8908R"},  # 일반 매수가능조회(주문가능현금)
    "ccld_inner":    {"real": "TTTC0081R", "demo": "VTTC0081R"},  # 일반 체결내역 3개월 이내
    "ccld_before":   {"real": "CTSC9215R", "demo": "VTSC9215R"},  # 일반 체결내역 3개월 이전
    # --- 퇴직연금(DC/IRP) 전용 ---
    "pen_balance":   {"real": "TTTC2208R", "demo": "TTTC2208R"},  # 퇴직연금 잔고조회
    "pen_ccld":      {"real": "TTTC2201R", "demo": "TTTC2201R"},  # 퇴직연금 체결/미체결
}
# 계좌유형: 'pension'(퇴직연금 DC/IRP) | 'normal'(일반/위탁)
ACCT_TYPE = os.environ.get("KIS_ACCT_TYPE", "pension")

ENV = os.environ.get("KIS_ENV", "real")
BASE = DOMAINS[ENV]
APP_KEY = os.environ.get("KIS_APP_KEY", "")
APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
CANO = os.environ.get("KIS_CANO", "")
ACNT = os.environ.get("KIS_ACNT_PRDT_CD", "")
TOKEN_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".kis_token.json")


def _require(*names):
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"[설정오류] 환경변수 미설정: {', '.join(missing)}")


def mask(s, keep=2):
    if not s:
        return ""
    s = str(s)
    if len(s) <= keep:
        return "*" * len(s)
    return s[:keep] + "*" * (len(s) - keep)


def _post(path, body, headers):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _get(path, params, headers):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{BASE}{path}?{qs}", headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


import urllib.parse  # noqa: E402


def get_token():
    # 캐시 재사용(유효시간 1일, 6시간 내 재발급 시 동일 토큰 반환됨)
    if os.path.exists(TOKEN_CACHE):
        try:
            c = json.load(open(TOKEN_CACHE))
            if c.get("env") == ENV and c.get("expire", 0) > time.time() + 600:
                return c["token"]
        except Exception:
            pass
    _require("KIS_APP_KEY", "KIS_APP_SECRET")
    res = _post("/oauth2/tokenP",
                {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET},
                {})
    token = res["access_token"]
    # expires_in(초) 제공 / 보통 86400
    expire = time.time() + int(res.get("expires_in", 86400))
    json.dump({"env": ENV, "token": token, "expire": expire}, open(TOKEN_CACHE, "w"))
    os.chmod(TOKEN_CACHE, 0o600)
    print(f"[토큰] 발급/캐시 OK  token={mask(token, 6)}  만료={dt.datetime.fromtimestamp(expire)}")
    return token


def hdr(token, tr_id):
    return {
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",  # 개인
    }


def show_keys(title, rows, sample_fields=None):
    print(f"\n=== {title} ===")
    if not rows:
        print("  (데이터 없음)")
        return
    row = rows[0] if isinstance(rows, list) else rows
    print(f"  반환 필드 수: {len(row)}")
    if sample_fields:
        for f in sample_fields:
            v = row.get(f, "<없음>")
            if f in ("cano",):
                v = mask(v)
            print(f"  - {f:24s}: {v}")
    else:
        print("  필드명:", ", ".join(sorted(row.keys())))


def _status(r):
    # rt_cd: 0=정상, 그 외=에러. msg1: 응답 메시지. 진단용.
    print(f"  [응답] rt_cd={r.get('rt_cd')}  msg_cd={r.get('msg_cd')}  msg1={str(r.get('msg1','')).strip()}")


def check_balance_dom(token):
    p = {"CANO": CANO, "ACNT_PRDT_CD": ACNT, "AFHR_FLPR_YN": "N", "OFL_YN": "",
         "INQR_DVSN": "02", "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
         "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
         "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""}
    r = _get("/uapi/domestic-stock/v1/trading/inquire-balance", p, hdr(token, TR["balance_dom"][ENV]))
    _status(r)
    show_keys("국내 잔고 output1(보유종목)", r.get("output1"),
              ["pdno", "prdt_name", "hldg_qty", "pchs_avg_pric", "prpr",
               "evlu_amt", "evlu_pfls_amt", "evlu_pfls_rt"])
    show_keys("국내 잔고 output2(계좌요약)", r.get("output2"),
              ["dnca_tot_amt", "nxdy_excc_amt", "prvs_rcdl_excc_amt",
               "tot_evlu_amt", "nass_amt", "evlu_pfls_smtl_amt"])


def check_psbl_order(token):
    # 매수가능조회: 주문가능현금(ord_psbl_cash). 퇴직연금계좌는 미지원이라 normal일 때만 호출.
    if ACCT_TYPE == "pension":
        print("\n=== 국내 매수가능조회 ===\n  (퇴직연금계좌 미지원 TR — 건너뜀)")
        return
    p = {"CANO": CANO, "ACNT_PRDT_CD": ACNT, "PDNO": "005930", "ORD_UNPR": "0",
         "ORD_DVSN": "01", "CMA_EVLU_AMT_ICLD_YN": "N", "OVRS_ICLD_YN": "N"}
    r = _get("/uapi/domestic-stock/v1/trading/inquire-psbl-order", p, hdr(token, TR["psbl_order"][ENV]))
    _status(r)
    show_keys("국내 매수가능조회 output", r.get("output"),
              ["ord_psbl_cash", "nrcvb_buy_amt", "max_buy_amt", "psbl_qty_calc_unpr"])


def check_pension_balance(token):
    # 퇴직연금 잔고조회 (TTTC2208R)
    p = {"CANO": CANO, "ACNT_PRDT_CD": ACNT, "ACCA_DVSN_CD": "00", "INQR_DVSN": "00",
         "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""}
    r = _get("/uapi/domestic-stock/v1/trading/pension/inquire-balance", p, hdr(token, TR["pen_balance"][ENV]))
    _status(r)
    show_keys("퇴직연금 잔고 output1(보유종목)", r.get("output1"),
              ["pdno", "prdt_name", "hldg_qty", "pchs_avg_pric", "prpr",
               "evlu_amt", "evlu_pfls_amt", "evlu_pfls_rt"])
    show_keys("퇴직연금 잔고 output2(계좌요약)", r.get("output2"))


def check_ccld(token):
    if ACCT_TYPE == "pension":
        # 퇴직연금 체결/미체결 (TTTC2201R). 날짜범위 파라미터 없음 → 최근 주문 기준.
        p = {"CANO": CANO, "ACNT_PRDT_CD": ACNT, "USER_DVSN_CD": "%%",
             "SLL_BUY_DVSN_CD": "00", "CCLD_NCCS_DVSN": "%%", "INQR_DVSN_3": "00",
             "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""}
        r = _get("/uapi/domestic-stock/v1/trading/pension/inquire-daily-ccld", p,
                 hdr(token, TR["pen_ccld"][ENV]))
        _status(r)
        # 이 TR은 데이터를 output(단일 배열)로 반환함 (output1 아님)
        show_keys("퇴직연금 체결/미체결 output", r.get("output"))
        return
    today = dt.date.today().strftime("%Y%m%d")
    start = (dt.date.today() - dt.timedelta(days=30)).strftime("%Y%m%d")
    p = {"CANO": CANO, "ACNT_PRDT_CD": ACNT, "INQR_STRT_DT": start, "INQR_END_DT": today,
         "SLL_BUY_DVSN_CD": "00", "INQR_DVSN": "00", "PDNO": "", "CCLD_DVSN": "00",
         "ORD_GNO_BRNO": "", "ODNO": "", "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
         "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""}
    r = _get("/uapi/domestic-stock/v1/trading/inquire-daily-ccld", p, hdr(token, TR["ccld_inner"][ENV]))
    _status(r)
    show_keys(f"국내 체결내역 output1 ({start}~{today})", r.get("output1"),
              ["ord_dt", "pdno", "prdt_name", "sll_buy_dvsn_cd_name", "ord_qty",
               "tot_ccld_qty", "avg_prvs", "tot_ccld_amt"])


if __name__ == "__main__":
    _require("KIS_CANO", "KIS_ACNT_PRDT_CD")
    print(f"[환경] {ENV}  BASE={BASE}  CANO={mask(CANO)}-{ACNT}  ACCT_TYPE={ACCT_TYPE}")
    tok = get_token()
    try:
        check_balance_dom(tok)
        if ACCT_TYPE == "pension":
            check_pension_balance(tok)
        check_psbl_order(tok)
        check_ccld(tok)
    except urllib.error.HTTPError as e:
        print(f"[HTTP오류] {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        print(f"[오류] {type(e).__name__}: {e}")
