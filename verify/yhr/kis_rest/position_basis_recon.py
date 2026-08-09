#!/usr/bin/env python3
"""
포트폴리오 설계 전제 실측 ①② — 위탁계좌(01) 대상.

  실측①  opening_qty 역산이 실데이터로 동작하는가 (스펙 §4.4 신뢰도 등급)
          opening_qty = 잔고수량 - Σ(확보구간 매수) + Σ(확보구간 매도)
          = 0 → VERIFIED / > 0 → SEEDED / < 0 → CONFLICT
          부수: 조회 가능한 가장 이른 체결일(계좌 개설일까지 되는가)

  실측②  잔고 평단(pchs_avg_pric)에 매수 수수료가 포함되는가 (스펙 §4.1 §4.3)
          잔고 평단 vs 체결내역 이동가중평균 재구성 평단 비교.
          차이를 1주당·총액·내재 수수료율로 환산해 매수 제비용(prsm_tlex_smtl)과 대조.

사용 TR:
  TTTC8434R  국내주식 잔고조회
  TTTC0081R  주식일별주문체결조회 — 3개월 이내
  CTSC9215R  주식일별주문체결조회 — 3개월 이전

보안:
  App Key / Secret / 계좌번호는 환경변수로만. 코드·로그·저장소 노출 금지.
  콘솔 출력에서 계좌번호·주문번호는 마스킹한다.
  ※ 보유수량·평단 등 실제 잔고 수치는 콘솔에 그대로 출력된다(분석에 필요).
     문서로 옮길 때 마스킹할 것.

환경변수:
  export KIS_ENV=real                  # real | demo
  export KIS_APP_KEY=...               # 위탁(01) 계좌의 앱키
  export KIS_APP_SECRET=...
  export KIS_CANO=12345678             # 계좌 앞 8자리
  export KIS_ACNT_PRDT_CD=01           # 위탁 상품코드. IRP(29)는 APBK1744로 차단됨
  # 선택 — 체결내역 소급 조회 범위
  export RECON_BACK_YEARS=10           # 최대 몇 년 전까지 되짚을지 (기본 10)
  export RECON_EMPTY_STOP=8            # 연속 빈 윈도우 N개면 중단 (기본 8 = 약 2년)
  export RECON_WINDOW_DAYS=90          # 소급 조회 윈도우 크기 (기본 90일)
  export RECON_FEE_PROBE=1             # 윈도우별 매수 제비용 추가 조회 (기본 1)

실행:
  python verify/yhr/kis_rest/position_basis_recon.py
"""
import os
import sys
import json
import time
import datetime as dt
import urllib.request
import urllib.error
import urllib.parse
from collections import defaultdict
from decimal import Decimal, InvalidOperation

ENV = os.environ.get("KIS_ENV", "real")
BASE = {"real": "https://openapi.koreainvestment.com:9443",
        "demo": "https://openapivts.koreainvestment.com:29443"}[ENV]
APP_KEY = os.environ.get("KIS_APP_KEY", "")
APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
CANO = os.environ.get("KIS_CANO", "")
ACNT = os.environ.get("KIS_ACNT_PRDT_CD", "")
TOKEN_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".kis_token.json")

TR_BALANCE = {"real": "TTTC8434R", "demo": "VTTC8434R"}[ENV]
TR_INNER = {"real": "TTTC0081R", "demo": "VTTC0081R"}[ENV]
TR_BEFORE = {"real": "CTSC9215R", "demo": "VTSC9215R"}[ENV]
API_BALANCE = "/uapi/domestic-stock/v1/trading/inquire-balance"
API_CCLD = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"

BACK_YEARS = int(os.environ.get("RECON_BACK_YEARS", "10"))
EMPTY_STOP = int(os.environ.get("RECON_EMPTY_STOP", "8"))
WINDOW_DAYS = int(os.environ.get("RECON_WINDOW_DAYS", "90"))
FEE_PROBE = os.environ.get("RECON_FEE_PROBE", "1") == "1"

# CTSC9215R(3개월 이전)이 커버하는 경계. 이보다 최근은 TTTC0081R을 쓴다.
INNER_DAYS = 90
# 유량제한: 실전 20건/초, 모의 2건/초 → 환경별로 지연을 다르게 준다
SLEEP = 0.12 if ENV == "real" else 0.6


# ---------------------------------------------------------------- 공통 유틸

def _req(*names):
    miss = [n for n in names if not os.environ.get(n)]
    if miss:
        sys.exit(f"[설정오류] 환경변수 미설정: {', '.join(miss)}")


def mask(s, keep=2):
    s = str(s or "")
    return s[:keep] + "*" * max(0, len(s) - keep) if s else ""


def D(v, default="0"):
    try:
        return Decimal(str(v).strip() or default)
    except (InvalidOperation, AttributeError):
        return Decimal(default)


def fmt(v, nd=0):
    try:
        q = Decimal(10) ** -nd
        return f"{Decimal(v).quantize(q):,}"
    except Exception:
        return str(v)


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


def _get(token, api, tr_id, params, tr_cont=""):
    url = f"{BASE}{api}?{urllib.parse.urlencode(params)}"
    headers = {"authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET,
               "tr_id": tr_id, "custtype": "P", "tr_cont": tr_cont}
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()), r.headers.get("tr_cont", "")


# ---------------------------------------------------------------- 잔고 조회

def fetch_balance(token):
    """국내주식 잔고 전량(연속조회 포함). (보유종목 리스트, 계좌요약) 반환."""
    rows, summary = [], None
    fk = nk = ""
    cont = ""
    for page in range(1, 21):
        p = {"CANO": CANO, "ACNT_PRDT_CD": ACNT, "AFHR_FLPR_YN": "N", "OFL_YN": "",
             "INQR_DVSN": "02", "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
             "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
             "CTX_AREA_FK100": fk, "CTX_AREA_NK100": nk}
        res, cont = _get(token, API_BALANCE, TR_BALANCE, p, tr_cont=("N" if page > 1 else ""))
        if res.get("rt_cd") != "0":
            print(f"  [잔고 실패] rt_cd={res.get('rt_cd')} msg_cd={res.get('msg_cd')} "
                  f"msg1={str(res.get('msg1','')).strip()}")
            return rows, summary
        rows += (res.get("output1") or [])
        o2 = res.get("output2")
        if isinstance(o2, list) and o2:
            summary = o2[0]
        elif isinstance(o2, dict):
            summary = o2
        fk = (res.get("ctx_area_fk100") or "").strip()
        nk = (res.get("ctx_area_nk100") or "").strip()
        if cont not in ("M", "F"):
            break
        time.sleep(SLEEP)
    return [r for r in rows if D(r.get("hldg_qty")) > 0], summary


def fetch_balance_rlz_pl(token, cost_incl):
    """주식잔고조회_실현손익(TTTC8494R). COST_ICLD_YN을 토글해 비용 포함 평단을 직접 얻는다.
    반환: ({pdno: row}, err)"""
    p = {"CANO": CANO, "ACNT_PRDT_CD": ACNT, "AFHR_FLPR_YN": "N", "OFL_YN": "",
         "INQR_DVSN": "00", "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
         "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
         "COST_ICLD_YN": cost_incl,
         "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""}
    try:
        res, _ = _get(token, "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl",
                      "TTTC8494R", p)
    except urllib.error.HTTPError as e:
        return {}, f"HTTP {e.code}: {e.read().decode()[:160]}"
    if res.get("rt_cd") != "0":
        return {}, f"{res.get('msg_cd')} {str(res.get('msg1','')).strip()}"
    out = {}
    for r in (res.get("output1") or []):
        pdno = str(r.get("pdno", "")).strip()
        if pdno and D(r.get("hldg_qty")) > 0:
            out[pdno] = r
    return out, None


# ---------------------------------------------------------------- 체결 조회

def fetch_ccld_window(token, tr_id, start, end, sll_buy="00"):
    """한 윈도우의 체결(주문) 행 전량 + output2(요약). (rows, output2, err) 반환."""
    rows, out2, fk, nk, cont = [], None, "", "", ""
    for page in range(1, 31):
        p = {"CANO": CANO, "ACNT_PRDT_CD": ACNT,
             "INQR_STRT_DT": start, "INQR_END_DT": end,
             "SLL_BUY_DVSN_CD": sll_buy, "INQR_DVSN": "00", "PDNO": "",
             "CCLD_DVSN": "01",  # 01 = 체결만 (00은 전체)
             "ORD_GNO_BRNO": "", "ODNO": "",
             "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
             "CTX_AREA_FK100": fk, "CTX_AREA_NK100": nk}
        try:
            res, cont = _get(token, API_CCLD, tr_id, p, tr_cont=("N" if page > 1 else ""))
        except urllib.error.HTTPError as e:
            return rows, out2, f"HTTP {e.code}: {e.read().decode()[:160]}"
        if res.get("rt_cd") != "0":
            return rows, out2, f"{res.get('msg_cd')} {str(res.get('msg1','')).strip()}"
        rows += (res.get("output1") or [])
        if page == 1:
            o2 = res.get("output2")
            out2 = o2[0] if isinstance(o2, list) and o2 else (o2 if isinstance(o2, dict) else None)
        fk = (res.get("ctx_area_fk100") or "").strip()
        nk = (res.get("ctx_area_nk100") or "").strip()
        if cont not in ("M", "F"):
            break
        time.sleep(SLEEP)
    return rows, out2, None


def walk_fills(token):
    """오늘부터 과거로 윈도우를 되짚으며 전 체결 수집. (fills, windows, earliest) 반환."""
    today = dt.date.today()
    floor = today - dt.timedelta(days=365 * BACK_YEARS)
    fills, windows = [], []
    empty_streak = 0
    cur_end = today

    print(f"\n[체결내역 소급 수집] 최대 {BACK_YEARS}년 · 윈도우 {WINDOW_DAYS}일 · "
          f"연속 빈 윈도우 {EMPTY_STOP}개면 중단")

    while cur_end >= floor:
        cur_start = max(floor, cur_end - dt.timedelta(days=WINDOW_DAYS - 1))
        # 윈도우 전체가 최근 90일 안이면 TTTC0081R, 아니면 CTSC9215R
        recent_edge = today - dt.timedelta(days=INNER_DAYS)
        tr_id = TR_INNER if cur_start >= recent_edge else TR_BEFORE
        rows, out2, err = fetch_ccld_window(token, tr_id, cur_start.strftime("%Y%m%d"),
                                            cur_end.strftime("%Y%m%d"))
        time.sleep(SLEEP)

        n_ccld = 0
        for r in rows:
            if D(r.get("tot_ccld_qty")) > 0:
                fills.append(r)
                n_ccld += 1

        buy_fee = None
        if FEE_PROBE and n_ccld:
            _, o2b, _ = fetch_ccld_window(token, tr_id, cur_start.strftime("%Y%m%d"),
                                          cur_end.strftime("%Y%m%d"), sll_buy="02")
            time.sleep(SLEEP)
            if o2b:
                buy_fee = o2b.get("prsm_tlex_smtl")

        windows.append({"start": cur_start, "end": cur_end, "tr": tr_id,
                        "n": n_ccld, "err": err,
                        "tlex": (out2 or {}).get("prsm_tlex_smtl"),
                        "buy_tlex": buy_fee})
        flag = "  ← 에러" if err else ""
        print(f"  {cur_start:%Y-%m-%d}~{cur_end:%Y-%m-%d}  {tr_id}  체결 {n_ccld:>3}건"
              f"{'  매수제비용 ' + str(buy_fee) if buy_fee not in (None, '', '0') else ''}"
              f"{'  [' + err + ']' if err else ''}{flag}")

        if err:
            # 조회 한계에 닿았을 가능성 — 빈 윈도우와 동일하게 취급하되 사유를 남긴다
            empty_streak += 1
        elif n_ccld == 0:
            empty_streak += 1
        else:
            empty_streak = 0
        if empty_streak >= EMPTY_STOP:
            print(f"  → 연속 {EMPTY_STOP}개 윈도우가 비어 중단 (더 과거는 미조회)")
            break
        cur_end = cur_start - dt.timedelta(days=1)

    earliest = min((r.get("ord_dt") for r in fills if r.get("ord_dt")), default=None)
    return fills, windows, earliest


# ---------------------------------------------------------------- 집계·판정

def side_of(row):
    """매수/매도 판별. sll_buy_dvsn_cd: 01=매도, 02=매수."""
    c = str(row.get("sll_buy_dvsn_cd", "")).strip()
    if c == "02":
        return "BUY"
    if c == "01":
        return "SELL"
    name = str(row.get("sll_buy_dvsn_cd_name", ""))
    if "매수" in name:
        return "BUY"
    if "매도" in name:
        return "SELL"
    return None


def aggregate(fills):
    """종목별로 체결을 시간순 정렬해 집계."""
    per = defaultdict(lambda: {"name": "", "rows": [],
                               "buy_qty": Decimal(0), "buy_amt": Decimal(0),
                               "sell_qty": Decimal(0), "sell_amt": Decimal(0),
                               "unknown": 0})
    for r in fills:
        pdno = str(r.get("pdno", "")).strip()
        if not pdno:
            continue
        g = per[pdno]
        g["name"] = g["name"] or str(r.get("prdt_name", "")).strip()
        side = side_of(r)
        qty = D(r.get("tot_ccld_qty"))
        amt = D(r.get("tot_ccld_amt"))
        if amt == 0:
            amt = qty * D(r.get("avg_prvs"))
        if side == "BUY":
            g["buy_qty"] += qty
            g["buy_amt"] += amt
        elif side == "SELL":
            g["sell_qty"] += qty
            g["sell_amt"] += amt
        else:
            g["unknown"] += 1
            continue
        g["rows"].append({"dt": str(r.get("ord_dt", "")), "tm": str(r.get("ord_tmd", "")),
                          "side": side, "qty": qty, "amt": amt,
                          "px": D(r.get("avg_prvs")), "odno": r.get("odno")})
    for g in per.values():
        g["rows"].sort(key=lambda x: (x["dt"], x["tm"]))
    return per


def moving_avg_cost(rows):
    """이동가중평균 재구성. opening_qty=0(=확보구간이 포지션 전체) 가정.
    반환: (최종평단, 최종수량, 도중 음수수량 발생 여부)"""
    qty = Decimal(0)
    cost = Decimal(0)
    went_negative = False
    for r in rows:
        if r["side"] == "BUY":
            qty += r["qty"]
            cost += r["amt"]
        else:
            if qty <= 0:
                went_negative = True
                qty -= r["qty"]
                continue
            avg = cost / qty
            sell_q = min(r["qty"], qty)
            cost -= avg * sell_q
            qty -= r["qty"]
            if qty < 0:
                went_negative = True
    avg = (cost / qty) if qty > 0 else None
    return avg, qty, went_negative


def ca_hint(hldg, net):
    """기업행위(분할/병합) 의심 배수 힌트."""
    if net <= 0 or hldg <= 0:
        return ""
    ratio = hldg / net
    for k in (2, 3, 4, 5, 10, 20, 50, 100):
        if abs(ratio - k) < Decimal("0.02"):
            return f" ← 수량이 정확히 {k}배: 액면분할 의심"
        if abs(ratio - (Decimal(1) / k)) < Decimal("0.0002"):
            return f" ← 수량이 정확히 1/{k}배: 병합 의심"
    return ""


# ---------------------------------------------------------------- 리포트

def report_cost_toggle(token, balance_rows):
    """실측② 직접 측정 — TTTC8494R의 COST_ICLD_YN을 N/Y로 토글해 평단 차이를 본다.
    이 차이가 곧 '평단에 반영되는 비용'의 실체다."""
    print("\n" + "-" * 78)
    print("  [직접 측정] 주식잔고조회_실현손익(TTTC8494R)의 COST_ICLD_YN 토글")
    print("  KIS가 '비용 포함/미포함' 평단을 각각 계산해 주므로, 두 값의 차이가 곧 비용 반영분이다.")
    no_cost, e1 = fetch_balance_rlz_pl(token, "N")
    time.sleep(SLEEP)
    yes_cost, e2 = fetch_balance_rlz_pl(token, "Y")
    time.sleep(SLEEP)
    if e1 or e2:
        print(f"  🔴 호출 실패 — COST_ICLD_YN=N: {e1 or 'OK'} / =Y: {e2 or 'OK'}")
        return
    if not no_cost and not yes_cost:
        print("  응답에 보유종목이 없어 비교 불가.")
        return
    sample = next(iter((yes_cost or no_cost).values()))
    print(f"  output1 필드({len(sample)}개): {', '.join(sample.keys())}")
    print(f"\n  {'종목':<8} {'종목명':<18} {'평단(비용X)':>13} {'평단(비용O)':>13} "
          f"{'차이':>10} {'차이율%':>9}  {'잔고TR 평단':>13}")
    by_pdno = {str(r.get("pdno", "")).strip(): r for r in balance_rows}
    diffs = []
    for pdno in sorted(set(no_cost) | set(yes_cost)):
        rn, ry = no_cost.get(pdno), yes_cost.get(pdno)
        an = D(rn.get("pchs_avg_pric")) if rn else Decimal(0)
        ay = D(ry.get("pchs_avg_pric")) if ry else Decimal(0)
        name = str((ry or rn).get("prdt_name", "")).strip()
        d = ay - an
        rate = (d / an * 100) if an else Decimal(0)
        diffs.append(rate)
        base = D(by_pdno[pdno].get("pchs_avg_pric")) if pdno in by_pdno else Decimal(0)
        print(f"  {pdno:<8} {name[:18]:<18} {fmt(an,4):>13} {fmt(ay,4):>13} "
              f"{fmt(d,4):>10} {fmt(rate,5):>9}  {fmt(base,2):>13}")
    if diffs:
        nz = [x for x in diffs if x != 0]
        print(f"\n  → 차이가 있는 종목 {len(nz)}/{len(diffs)}건.")
        if nz:
            print(f"     차이율 범위 {fmt(min(nz),6)}% ~ {fmt(max(nz),6)}%")
            print("     ⇒ 잔고 TR(TTTC8434R) 평단이 어느 쪽과 일치하는지가 실측②의 답이다.")
        else:
            print("     ⇒ COST_ICLD_YN이 평단을 바꾸지 않음. 비용은 평단에 반영되지 않는다.")


def report(balance_rows, summary, per, windows, earliest):
    print("\n" + "=" * 78)
    print("실측① opening_qty 역산 — 스펙 §4.4 신뢰도 등급")
    print("=" * 78)

    q_start = min((w["start"] for w in windows), default=None)
    print(f"  조회 요청 구간   : {q_start:%Y-%m-%d} ~ {dt.date.today():%Y-%m-%d}")
    print(f"  실제 최초 체결일 : {earliest or '(체결 없음)'}")
    errs = [w for w in windows if w["err"]]
    if errs:
        print(f"  ⚠️ 에러 윈도우 {len(errs)}개 — 예: {errs[0]['start']:%Y-%m-%d}~{errs[0]['end']:%Y-%m-%d} "
              f"[{errs[0]['err']}]")
    else:
        print("  에러 윈도우      : 없음 (전 구간 정상 응답)")

    grades = {"VERIFIED": [], "SEEDED": [], "CONFLICT": []}
    detail = []
    for r in balance_rows:
        pdno = str(r.get("pdno", "")).strip()
        name = str(r.get("prdt_name", "")).strip()
        hldg = D(r.get("hldg_qty"))
        g = per.get(pdno)
        buy_q = g["buy_qty"] if g else Decimal(0)
        sell_q = g["sell_qty"] if g else Decimal(0)
        opening = hldg - buy_q + sell_q
        grade = "VERIFIED" if opening == 0 else ("SEEDED" if opening > 0 else "CONFLICT")
        grades[grade].append(pdno)
        first_fill = g["rows"][0]["dt"] if (g and g["rows"]) else None
        detail.append({"pdno": pdno, "name": name, "hldg": hldg, "buy": buy_q, "sell": sell_q,
                       "opening": opening, "grade": grade, "first": first_fill, "g": g})

    n = len(detail) or 1
    print(f"\n  보유 종목 {len(detail)}건에 대한 판정 분포")
    print(f"    {'등급':<10} {'종목수':>5} {'비율':>7}")
    for k in ("VERIFIED", "SEEDED", "CONFLICT"):
        c = len(grades[k])
        print(f"    {k:<10} {c:>5} {c*100//n:>6}%")

    print(f"\n  {'종목':<8} {'종목명':<22} {'잔고수량':>10} {'Σ매수':>10} {'Σ매도':>9} "
          f"{'opening_qty':>12} {'등급':<9} {'최초체결'}")
    for d in sorted(detail, key=lambda x: (x["grade"], x["pdno"])):
        hint = ca_hint(d["hldg"], d["buy"] - d["sell"]) if d["grade"] == "CONFLICT" else ""
        print(f"  {d['pdno']:<8} {d['name'][:22]:<22} {fmt(d['hldg']):>10} {fmt(d['buy']):>10} "
              f"{fmt(d['sell']):>9} {fmt(d['opening']):>12} {d['grade']:<9} "
              f"{d['first'] or '-'}{hint}")

    # 잔고에 없는데 체결만 있는 종목 = 기간 중 전량 청산
    closed = [p for p in per if p not in {d["pdno"] for d in detail}]
    if closed:
        print(f"\n  (참고) 확보구간에 매매했으나 현재 미보유인 종목 {len(closed)}건: "
              f"{', '.join(closed[:12])}{' 외' if len(closed) > 12 else ''}")

    # ---------------------------------------------------------------
    print("\n" + "=" * 78)
    print("실측② 잔고 평단에 매수 수수료가 포함되는가 — 스펙 §4.1 §4.3")
    print("=" * 78)
    print("  비교 대상: opening_qty = 0 (VERIFIED) 종목만. 그 외는 재구성 평단이 성립하지 않는다.")
    print(f"\n  {'종목':<8} {'종목명':<18} {'잔고평단':>12} {'재구성평단':>12} {'차이(주당)':>11} "
          f"{'차이(총액)':>12} {'내재율%':>9}")

    by_pdno = {str(r.get("pdno", "")).strip(): r for r in balance_rows}
    rate_samples = []
    for d in detail:
        if d["grade"] != "VERIFIED" or not d["g"]:
            continue
        avg_bal = D(by_pdno[d["pdno"]].get("pchs_avg_pric"))
        recon, rq, neg = moving_avg_cost(d["g"]["rows"])
        if recon is None or recon == 0:
            continue
        diff = avg_bal - recon
        diff_tot = diff * d["hldg"]
        rate = (diff / recon * 100) if recon else Decimal(0)
        rate_samples.append(rate)
        print(f"  {d['pdno']:<8} {d['name'][:18]:<18} {fmt(avg_bal,2):>12} {fmt(recon,4):>12} "
              f"{fmt(diff,4):>11} {fmt(diff_tot,0):>12} {fmt(rate,5):>9}"
              f"{'  ⚠️재구성수량≠잔고' if rq != d['hldg'] else ''}")

    if rate_samples:
        pos = sum(1 for x in rate_samples if x > 0)
        neg = sum(1 for x in rate_samples if x < 0)
        zero = sum(1 for x in rate_samples if x == 0)
        lo, hi = min(rate_samples), max(rate_samples)
        avg_rate = sum(rate_samples) / len(rate_samples)
        print(f"\n  내재 수수료율 분포: n={len(rate_samples)}  "
              f"양(+){pos} / 음(-){neg} / 정확히 0: {zero}")
        print(f"    범위 {fmt(lo,6)}% ~ {fmt(hi,6)}%   평균 {fmt(avg_rate,6)}%")
        print("    참고 — KIS 국내주식 온라인 위탁수수료는 통상 0.0036396%~0.15% 수준.")
        print("           0에 수렴하면 잔고 평단은 '수수료 미포함(체결가 기준)'.")
        print("           일정한 양수면 '매수 수수료 포함'.")
    else:
        print("\n  비교 가능한 VERIFIED 종목이 없어 판정 불가.")

    fee_windows = [w for w in windows if w.get("buy_tlex") not in (None, "", "0")]
    if fee_windows:
        tot = sum(D(w["buy_tlex"]) for w in fee_windows)
        print(f"\n  매수 제비용 실측(prsm_tlex_smtl, 매수만 조회): 윈도우 {len(fee_windows)}개 합계 {fmt(tot)}원")
        for w in fee_windows[:10]:
            print(f"    {w['start']:%Y-%m-%d}~{w['end']:%Y-%m-%d}  {fmt(D(w['buy_tlex']))}원")

    # 잔고의 매입금액 컬럼과 평단×수량 대조 (반올림·수수료 흡수 여부)
    print("\n  [보조] 잔고 자체의 정합성 — pchs_amt vs pchs_avg_pric × hldg_qty")
    for r in balance_rows:
        pa = D(r.get("pchs_amt"))
        calc = D(r.get("pchs_avg_pric")) * D(r.get("hldg_qty"))
        if pa == 0:
            continue
        print(f"    {str(r.get('pdno','')).strip():<8} pchs_amt={fmt(pa):>13}  "
              f"평단×수량={fmt(calc,2):>15}  차이={fmt(pa-calc,2):>10}")

    if summary:
        print("\n  [보조] 잔고 output2 요약 필드:", ", ".join(sorted(summary.keys())))


def main():
    _req("KIS_CANO", "KIS_ACNT_PRDT_CD")
    print(f"[환경] {ENV}  계좌={mask(CANO)}-{ACNT}")
    if ACNT == "29":
        sys.exit("  ⚠️ 상품코드 29(IRP)는 기간 체결내역이 APBK1744로 차단된다. 위탁(01)로 실행할 것.")
    tok = get_token()

    print("\n[잔고 조회] TTTC8434R")
    balance_rows, summary = fetch_balance(tok)
    print(f"  보유 종목 {len(balance_rows)}건")
    for r in balance_rows:
        print(f"    {str(r.get('pdno','')).strip():<8} {str(r.get('prdt_name','')).strip()[:24]:<24} "
              f"수량={fmt(D(r.get('hldg_qty'))):>8}  평단={fmt(D(r.get('pchs_avg_pric')),2):>12}  "
              f"평가={fmt(D(r.get('evlu_amt'))):>13}")
    if not balance_rows:
        print("  보유 종목이 없어 실측①②를 수행할 수 없다.")
        return

    fills, windows, earliest = walk_fills(tok)
    print(f"\n  수집 체결(주문) 행: {len(fills)}건 · 최초 체결일 {earliest or '-'}")

    per = aggregate(fills)
    unknown = sum(g["unknown"] for g in per.values())
    if unknown:
        print(f"  ⚠️ 매수/매도 판별 불가 행 {unknown}건 (집계 제외)")

    report(balance_rows, summary, per, windows, earliest)
    report_cost_toggle(tok, balance_rows)

    print("\n[해석 가이드]")
    print("  실측① VERIFIED 비율이 낮고 SEEDED가 지배적이면 §4.5의 '추정 배지'가 화면 대부분에 붙는다.")
    print("        CONFLICT가 흔하면 §4.4 등급 체계 자체를 재설계해야 한다.")
    print("  실측② 내재 수수료율이 0에 수렴하면 잔고 평단 = 체결가 기준(수수료 미포함).")
    print("        이 경우 §4.1의 '수수료 포함 여부' 근거 문구를 수정해야 한다.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"[HTTP오류] {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        import traceback
        print(f"[오류] {type(e).__name__}: {e}")
        traceback.print_exc()
