#!/usr/bin/env python3
"""
포트폴리오 설계 전제 실측 ③ — 입출금내역에 매매대금이 섞이는가 (스펙 §1.4 §4.6 §5.1 `cln_cashflow`).

배경:
  자산 변화 뷰(§2.9)는 "자산 증감 − 넣은 돈"으로 투자손익을 구한다.
  증권사 입출금내역에 매도대금 입금이 섞이면 매도 한 번에 그 금액만큼 손실로 표시된다.
  스펙 §5.1은 "증권사 입출금내역은 매수대금 출금·매도대금 입금을 같은 응답에 담아 주므로
  데이터가 걸러낸다"고 전제한다. 이 전제를 KIS 응답으로 확인한다.

이 스크립트가 하는 일:
  KIS 국내주식 '주문/계좌' 카테고리에서 현금 흐름에 닿는 TR을 전부 호출해
  (a) 입출금 '이력'을 주는 TR이 존재하는지
  (b) 존재한다면 매매대금이 섞이는지 / 구분 필드가 있는지
  를 응답 필드 수준에서 판정한다. 응답은 전 필드를 덤프한다.

호출 대상 TR:
  TTTC8434R  국내주식 잔고조회            → output2의 예수금 계열 (잔액만, 이력 아님)
  CTRP6548R  투자계좌자산현황조회          → 계좌 자산 구성
  TTTC8708R  기간별손익일별합산조회        → 일자별 손익. 입출금 항목 존재 여부 확인
  TTTC8715R  기간별매매손익현황조회        → 종목별 매매손익 + 취득단가
  CTRGA011R  기간별계좌권리현황조회        → 배당·권리 이력 (cln_cashflow의 DIVIDEND 원천 후보)
  TTTC0081R  주식일별주문체결조회          → 매매만 (대조군)

보안:
  App Key / Secret / 계좌번호는 환경변수로만. 계좌번호·주문번호·실명확인번호는 마스킹.

환경변수:
  export KIS_ENV=real
  export KIS_APP_KEY=...  KIS_APP_SECRET=...
  export KIS_CANO=12345678  KIS_ACNT_PRDT_CD=01
  export CF_START=20250101  CF_END=20260809     # 선택. 기본 = 최근 13개월
실행:
  python verify/yhr/kis_rest/cashflow_probe.py
"""
import os
import sys
import json
import time
import datetime as dt
import urllib.request
import urllib.error
import urllib.parse

ENV = os.environ.get("KIS_ENV", "real")
BASE = {"real": "https://openapi.koreainvestment.com:9443",
        "demo": "https://openapivts.koreainvestment.com:29443"}[ENV]
APP_KEY = os.environ.get("KIS_APP_KEY", "")
APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
CANO = os.environ.get("KIS_CANO", "")
ACNT = os.environ.get("KIS_ACNT_PRDT_CD", "")
TOKEN_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".kis_token.json")

SENSITIVE = {"cano", "acnt_prdt_cd", "odno", "orgn_odno", "ord_gno_brno",
             "cust_rncno25", "hmid", "acnt_name", "cust_name",
             # 실계좌 응답에서 실제로 확인된 개인정보 필드 — 반드시 마스킹
             "acno10",         # 계좌번호 10자리 (CTRGA011R)
             "ctac_tlno",      # 연락처 전화번호 (TTTC0081R)
             "inqr_ip_addr",   # 주문 IP 주소 (TTTC0081R)
             "ordr_empno",     # 주문자 정보 (TTTC0081R)
             "ord_orgno"}      # 주문조직번호 (TTTC0081R)
# 유량제한: 실전 20건/초, 모의 2건/초
SLEEP = 0.15 if ENV == "real" else 0.6

# 실전 TR → 모의투자 변형. 값이 None이면 모의 미지원(실전 ID로 호출해 거부 사유를 남긴다).
DEMO_TR = {
    "TTTC8434R": "VTTC8434R",   # 국내주식 잔고조회
    "TTTC0081R": "VTTC0081R",   # 주식일별주문체결조회 (3개월 이내)
    "CTSC9215R": "VTSC9215R",   # 주식일별주문체결조회 (3개월 이전)
    "CTRP6548R": None,          # 투자계좌자산현황조회
    "TTTC8708R": None,          # 기간별손익일별합산조회
    "TTTC8715R": None,          # 기간별매매손익현황조회
    "CTRGA011R": None,          # 기간별계좌권리현황조회
    "TTTC8494R": None,          # 주식잔고조회_실현손익
}


def tr_for_env(tr_id):
    """(실제 호출할 tr_id, 주석) 반환."""
    if ENV != "demo":
        return tr_id, ""
    v = DEMO_TR.get(tr_id, None)
    if v:
        return v, f"모의 변형 {v}"
    return tr_id, "모의 변형 없음 — 실전 ID로 호출해 거부 사유 확인"

# 입출금·현금흐름 성격을 시사하는 필드명 조각 (응답 스캔용)
CASHFLOW_HINTS = ["dpsi", "wdrw", "tr_dvsn", "trad_dvsn", "rmrk", "smtl_amt",
                  "dnca", "prvs", "icdc", "cash", "dvdn", "rght", "tlex", "excc"]


def _req(*names):
    miss = [n for n in names if not os.environ.get(n)]
    if miss:
        sys.exit(f"[설정오류] 환경변수 미설정: {', '.join(miss)}")


def mask(s, keep=2):
    s = str(s or "")
    return s[:keep] + "*" * max(0, len(s) - keep) if s else ""


def _appkey_fp():
    import hashlib
    return hashlib.sha256(APP_KEY.encode()).hexdigest()[:12] if APP_KEY else ""


def get_token():
    fp = _appkey_fp()
    if os.path.exists(TOKEN_CACHE):
        try:
            c = json.load(open(TOKEN_CACHE))
            if c.get("env") == ENV and c.get("appkey_fp") == fp and c.get("expire", 0) > time.time() + 600:
                return c["token"]
        except Exception:
            pass
    _req("KIS_APP_KEY", "KIS_APP_SECRET")
    body = json.dumps({"grant_type": "client_credentials",
                       "appkey": APP_KEY, "appsecret": APP_SECRET}).encode()
    req = urllib.request.Request(BASE + "/oauth2/tokenP", data=body,
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        res = json.loads(r.read())
    token = res["access_token"]
    expire = time.time() + int(res.get("expires_in", 86400))
    json.dump({"env": ENV, "appkey_fp": fp, "token": token, "expire": expire}, open(TOKEN_CACHE, "w"))
    os.chmod(TOKEN_CACHE, 0o600)
    print(f"[토큰] 발급/캐시 OK  만료={dt.datetime.fromtimestamp(expire):%Y-%m-%d %H:%M}")
    return token


def call(token, api, tr_id, params):
    url = f"{BASE}{api}?{urllib.parse.urlencode(params)}"
    headers = {"authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET,
               "tr_id": tr_id, "custtype": "P", "tr_cont": ""}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return json.loads(raw), f"HTTP {e.code}"
        except Exception:
            return None, f"HTTP {e.code}: {raw[:200]}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def dump_block(label, block, limit=3):
    """output 블록의 전 필드명 + 샘플값(마스킹) 출력."""
    if block is None:
        print(f"    {label}: (없음)")
        return []
    if isinstance(block, dict):
        block = [block]
    if not block:
        print(f"    {label}: (빈 배열)")
        return []
    keys = list(block[0].keys())
    print(f"    {label}: {len(block)}행 · 필드 {len(keys)}개")
    print(f"      필드명: {', '.join(keys)}")
    hits = [k for k in keys if any(h in k.lower() for h in CASHFLOW_HINTS)]
    if hits:
        print(f"      ▶ 현금흐름 시사 필드: {', '.join(hits)}")
    for i, row in enumerate(block[:limit]):
        vals = {k: (mask(v) if k in SENSITIVE else v) for k, v in row.items()}
        vals = {k: v for k, v in vals.items() if str(v).strip() not in ("", "0")}
        print(f"      [{i}] {json.dumps(vals, ensure_ascii=False)[:600]}")
    return keys


def probe(token, title, api, tr_id, params, note=""):
    use_tr, env_note = tr_for_env(tr_id)
    print(f"\n{'-'*78}\n■ {title}  ({tr_id}{'  → ' + env_note if env_note else ''})")
    if note:
        print(f"  목적: {note}")
    res, err = call(token, api, use_tr, params)
    time.sleep(SLEEP)
    if res is None:
        print(f"  🔴 호출 실패 — {err}")
        return None
    rt = res.get("rt_cd")
    print(f"  rt_cd={rt}  msg_cd={res.get('msg_cd')}  msg1={str(res.get('msg1','')).strip()}")
    if rt != "0":
        print("  → 이 계좌/환경에서 사용 불가")
        return res
    for key in ("output", "output1", "output2", "output3"):
        if key in res:
            dump_block(key, res.get(key))
    return res


def main():
    _req("KIS_CANO", "KIS_ACNT_PRDT_CD")
    print(f"[환경] {ENV}  계좌={mask(CANO)}-{ACNT}")
    tok = get_token()

    today = dt.date.today()
    start = os.environ.get("CF_START", (today - dt.timedelta(days=395)).strftime("%Y%m%d"))
    end = os.environ.get("CF_END", today.strftime("%Y%m%d"))
    print(f"[조회구간] {start} ~ {end}")

    acct = {"CANO": CANO, "ACNT_PRDT_CD": ACNT}

    probe(tok, "국내주식 잔고조회 — 예수금 계열", "/uapi/domestic-stock/v1/trading/inquire-balance",
          "TTTC8434R",
          {**acct, "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01",
           "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
           "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""},
          "output2에 예수금 잔액이 있는가. 잔액뿐이면 '이력' 원장으로는 못 쓴다")

    probe(tok, "투자계좌자산현황조회", "/uapi/domestic-stock/v1/trading/inquire-account-balance",
          "CTRP6548R",
          {**acct, "INQR_DVSN_1": "", "BSPR_BF_DT_APLY_YN": ""},
          "계좌 자산 구성. 입출금 이력 항목이 있는지")

    probe(tok, "기간별손익일별합산조회", "/uapi/domestic-stock/v1/trading/inquire-period-profit",
          "TTTC8708R",
          {**acct, "INQR_STRT_DT": start, "INQR_END_DT": end, "SORT_DVSN": "01",
           "INQR_DVSN": "00", "CBLC_DVSN": "00", "PDNO": "",
           "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""},
          "일자별 손익 합산. 입출금 항목이 섞여 오는지")

    probe(tok, "기간별매매손익현황조회", "/uapi/domestic-stock/v1/trading/inquire-period-trade-profit",
          "TTTC8715R",
          {**acct, "SORT_DVSN": "01", "INQR_STRT_DT": start, "INQR_END_DT": end,
           "CBLC_DVSN": "00", "PDNO": "", "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""},
          "KIS가 자체 재구성한 취득단가·실현손익. 실측②의 교차검증에도 쓴다")

    probe(tok, "기간별계좌권리현황조회", "/uapi/domestic-stock/v1/trading/period-rights",
          "CTRGA011R",
          {"INQR_DVSN": "03", **acct, "INQR_STRT_DT": start, "INQR_END_DT": end,
           "CUST_RNCNO25": "", "HMID": "", "RGHT_TYPE_CD": "", "PDNO": "", "PRDT_TYPE_CD": "",
           "CTX_AREA_NK100": "", "CTX_AREA_FK100": ""},
          "배당·권리 이력. cln_cashflow의 DIVIDEND 원천이 될 수 있는지")

    probe(tok, "주식일별주문체결조회 (대조군)", "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
          "TTTC0081R",
          {**acct, "INQR_STRT_DT": (today - dt.timedelta(days=60)).strftime("%Y%m%d"),
           "INQR_END_DT": end, "SLL_BUY_DVSN_CD": "00", "INQR_DVSN": "00", "PDNO": "",
           "CCLD_DVSN": "01", "ORD_GNO_BRNO": "", "ODNO": "", "INQR_DVSN_3": "00",
           "INQR_DVSN_1": "", "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""},
          "매매만 담긴 원장. 입출금 TR이 없을 때 무엇으로 대체 불가능한지 대조")

    probe(tok, "주식잔고조회_실현손익 (COST_ICLD_YN=Y)",
          "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl", "TTTC8494R",
          {**acct, "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "00", "UNPR_DVSN": "01",
           "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
           "COST_ICLD_YN": "Y", "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""},
          "비용포함 평단 봉투 확인 — 실측②의 직접 측정 경로가 존재하는지")

    print("\n" + "=" * 78)
    print("판정 기준")
    print("=" * 78)
    print("  · 위 TR 중 '일자 + 금액 + 거래구분'을 행 단위로 주는 것이 있으면 입출금내역 원장 후보.")
    print("  · 잔액(예수금 현재값)만 주는 TR은 §1.4의 현금흐름 원장으로 쓸 수 없다.")
    print("  · 후보가 하나도 없으면 KIS는 cln_cashflow를 공급하지 못하며,")
    print("    자산 변화 뷰(§2.9)의 '넣은 돈'은 CODEF 또는 수기 입력에 전적으로 의존한다.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"[오류] {type(e).__name__}: {e}")
        traceback.print_exc()
