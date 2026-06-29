#!/usr/bin/env python3
"""
KIS 국내주식 '기간 체결내역' 실측 — 위탁계좌(01)·실매매 이력 대상.

검증 목표:
  1. 3개월 이내(TTTC0081R) / 3개월 이전(CTSC9215R) 둘 다 호출 성공하는지(APBK1744 미발생).
  2. output1(체결 건별)·output2(요약)의 실제 응답 필드명/값 확인(전체 덤프, 마스킹).
  3. 연속조회(CTX_AREA_FK/NK100)로 다건 페이징 동작.
  4. 과거 며칠/몇개월 전까지 조회되는지(기간 한계) 점검.

보안: 키/계좌는 환경변수로만. 코드/로그/repo 노출 금지. 주문번호·계좌는 마스킹.
실행 전: 추가 의존성 없음(표준 라이브러리).
환경변수:
  export KIS_ENV=real                 # real | demo
  export KIS_APP_KEY=...               # 위탁(01) 계좌의 앱키
  export KIS_APP_SECRET=...
  export KIS_CANO=12345678             # 위탁 계좌 앞 8자리
  export KIS_ACNT_PRDT_CD=01           # 위탁 상품코드(01)
  # (선택) 조회 구간 override. 미설정 시 기본값 사용.
  export CCLD_INNER_START=20260601 CCLD_INNER_END=20260629   # 3개월 이내 테스트
  export CCLD_BEFORE_START=20260101 CCLD_BEFORE_END=20260131  # 3개월 이전 테스트
  export CCLD_DEEP_START=20240101 CCLD_DEEP_END=20240131      # 기간 한계 점검(과거)
실행:
  python verify/yhr/kis_rest/ccld_history.py
"""
import os
import sys
import json
import time
import datetime as dt
import urllib.request
import urllib.parse

ENV = os.environ.get("KIS_ENV", "real")
BASE = {"real": "https://openapi.koreainvestment.com:9443",
        "demo": "https://openapivts.koreainvestment.com:29443"}[ENV]
APP_KEY = os.environ.get("KIS_APP_KEY", "")
APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
CANO = os.environ.get("KIS_CANO", "")
ACNT = os.environ.get("KIS_ACNT_PRDT_CD", "")
TOKEN_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".kis_token.json")

# 기간 체결내역 TR (위탁/일반 계좌)
TR_INNER = {"real": "TTTC0081R", "demo": "VTTC0081R"}[ENV]   # 3개월 이내
TR_BEFORE = {"real": "CTSC9215R", "demo": "VTSC9215R"}[ENV]  # 3개월 이전
API = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"

# 민감 추정 필드(마스킹)
SENSITIVE = {"odno", "orgn_odno", "cano", "acnt_prdt_cd", "ord_gno_brno"}
# 관심 필드(있으면 강조 출력)
HILITE = ["ord_dt", "odno", "pdno", "prdt_name", "sll_buy_dvsn_cd_name",
          "ord_qty", "ord_unpr", "tot_ccld_qty", "avg_prvs", "tot_ccld_amt",
          "rmn_qty", "ccld_cndt_name", "excg_id_dvsn_cd"]


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
            # ENV + 앱키 지문 모두 일치할 때만 재사용(다른 계좌 토큰 오용 방지)
            if c.get("env") == ENV and c.get("appkey_fp") == fp and c.get("expire", 0) > time.time() + 600:
                return c["token"]
        except Exception:
            pass
    _req("KIS_APP_KEY", "KIS_APP_SECRET")
    body = json.dumps({"grant_type": "client_credentials",
                       "appkey": APP_KEY, "appsecret": APP_SECRET}).encode()
    req = urllib.request.Request(BASE + "/oauth2/tokenP", data=body,
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        res = json.loads(r.read())
    token = res["access_token"]
    expire = time.time() + int(res.get("expires_in", 86400))
    json.dump({"env": ENV, "appkey_fp": fp, "token": token, "expire": expire}, open(TOKEN_CACHE, "w"))
    os.chmod(TOKEN_CACHE, 0o600)
    print(f"[토큰] 발급/캐시 OK  만료={dt.datetime.fromtimestamp(expire)}")
    return token


def call(token, tr_id, start, end, fk="", nk="", tr_cont=""):
    params = {
        "CANO": CANO, "ACNT_PRDT_CD": ACNT,
        "INQR_STRT_DT": start, "INQR_END_DT": end,
        "SLL_BUY_DVSN_CD": "00", "INQR_DVSN": "00", "PDNO": "",
        "CCLD_DVSN": "00", "ORD_GNO_BRNO": "", "ODNO": "",
        "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
        "CTX_AREA_FK100": fk, "CTX_AREA_NK100": nk,
    }
    url = f"{BASE}{API}?{urllib.parse.urlencode(params)}"
    headers = {
        "authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET,
        "tr_id": tr_id, "custtype": "P", "tr_cont": tr_cont,
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        cont = r.headers.get("tr_cont", "")
        return json.loads(r.read()), cont


def dump_fields(rows, label):
    if not rows:
        print(f"    {label}: (데이터 없음)")
        return
    row = rows[0]
    print(f"    {label}: {len(rows)}건, 필드 {len(row)}개")
    print(f"    └ 강조필드:")
    for k in HILITE:
        if k in row:
            v = mask(row[k]) if k in SENSITIVE else row[k]
            print(f"        {k:22s} = {v}")
    other = [k for k in row.keys() if k not in HILITE]
    print(f"    └ 그 외 필드명: {', '.join(other)}")


def run_test(token, title, tr_id, start, end, paginate=False):
    print(f"\n=== {title} | TR={tr_id} | {start}~{end} ===")
    try:
        res, cont = call(token, tr_id, start, end)
    except urllib.error.HTTPError as e:
        print(f"  [HTTP오류] {e.code}: {e.read().decode()[:200]}")
        return
    rt = res.get("rt_cd")
    print(f"  rt_cd={rt}  msg_cd={res.get('msg_cd')}  msg1={str(res.get('msg1','')).strip()}  tr_cont(헤더)={cont}")
    if rt != "0":
        print("  → 호출 실패(위 메시지 확인). APBK1744면 해당 계좌가 위탁계좌가 아님.")
        return
    out1 = res.get("output1") or []
    out2 = res.get("output2")
    total = len(out1)
    dump_fields(out1, "output1(체결 건별)")
    if isinstance(out2, dict):
        print(f"    output2(요약) 필드: {', '.join(out2.keys())}")
    elif isinstance(out2, list) and out2:
        print(f"    output2(요약) 필드: {', '.join(out2[0].keys())}")

    # 연속조회 페이징(최대 5페이지)로 총 건수·동작 확인
    if paginate:
        fk = res.get("ctx_area_fk100", "").strip()
        nk = res.get("ctx_area_nk100", "").strip()
        page = 1
        while cont in ("M", "F") and page < 5:
            time.sleep(0.1)
            res, cont = call(token, tr_id, start, end, fk, nk, tr_cont="N")
            n = len(res.get("output1") or [])
            total += n
            fk = res.get("ctx_area_fk100", "").strip()
            nk = res.get("ctx_area_nk100", "").strip()
            page += 1
            print(f"    [연속조회 p{page}] +{n}건 (tr_cont={cont})")
        print(f"  → 누적 체결 건수(최대 5p): {total}")


def main():
    _req("KIS_CANO", "KIS_ACNT_PRDT_CD")
    print(f"[환경] {ENV}  계좌={mask(CANO)}-{ACNT}")
    if ACNT == "29":
        print("  ⚠️ 상품코드 29(IRP)로 보임 — 위탁(01) 계좌로 테스트해야 의미 있음.")
    tok = get_token()

    today = dt.date.today()
    inner_s = os.environ.get("CCLD_INNER_START", (today - dt.timedelta(days=30)).strftime("%Y%m%d"))
    inner_e = os.environ.get("CCLD_INNER_END", today.strftime("%Y%m%d"))
    before_s = os.environ.get("CCLD_BEFORE_START", (today - dt.timedelta(days=130)).strftime("%Y%m%d"))
    before_e = os.environ.get("CCLD_BEFORE_END", (today - dt.timedelta(days=100)).strftime("%Y%m%d"))

    run_test(tok, "① 3개월 이내", TR_INNER, inner_s, inner_e, paginate=True)
    run_test(tok, "② 3개월 이전", TR_BEFORE, before_s, before_e, paginate=True)

    # 과거 기간 한계 점검(선택)
    if os.environ.get("CCLD_DEEP_START") and os.environ.get("CCLD_DEEP_END"):
        run_test(tok, "③ 과거 기간 한계 점검", TR_BEFORE,
                 os.environ["CCLD_DEEP_START"], os.environ["CCLD_DEEP_END"], paginate=False)

    print("\n[해석]")
    print("  - 둘 다 rt_cd=0 + output1 필드 수신 → 위탁계좌 기간 체결내역 실측 완료.")
    print("  - ②/③에서 일정 과거부터 데이터가 비면 그 지점이 사실상 조회 한계.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[오류] {type(e).__name__}: {e}")
