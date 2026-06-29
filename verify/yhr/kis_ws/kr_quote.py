#!/usr/bin/env python3
"""
KIS 실시간(WebSocket) 검증: approval_key 발급 → 국내 체결가/호가 구독 →
세션당 등록 한도(문서상 41건) 실측 → 장중이면 체결틱 샘플 출력.

보안: appkey/secret 은 환경변수로만. 코드/로그/repo 노출 금지.
실행 전: pip install websocket-client
환경변수:
  export KIS_ENV=real              # real(실전) | demo(모의)
  export KIS_APP_KEY=...
  export KIS_APP_SECRET=...
  export KIS_SUB=ccnl              # ccnl(체결가 H0STCNT0) | asp(호가 H0STASP0)
실행:
  python verify/yhr/kis_ws/kr_quote.py
"""
import os
import sys
import json
import time
import urllib.request

try:
    import websocket  # websocket-client
except ModuleNotFoundError:
    sys.exit("[의존성] 'pip install websocket-client' 필요")

ENV = os.environ.get("KIS_ENV", "real")
REST = {"real": "https://openapi.koreainvestment.com:9443",
        "demo": "https://openapivts.koreainvestment.com:29443"}[ENV]
WS = {"real": "ws://ops.koreainvestment.com:21000",
      "demo": "ws://ops.koreainvestment.com:31000"}[ENV]
APP_KEY = os.environ.get("KIS_APP_KEY", "")
APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
TR = {"ccnl": "H0STCNT0", "asp": "H0STASP0"}[os.environ.get("KIS_SUB", "ccnl")]

# 한도 테스트용 KOSPI 대형주 50종목 (시세 데이터는 공개정보)
SYMBOLS = [
    "005930", "000660", "207940", "005380", "005490", "035420", "051910", "006400",
    "035720", "000270", "068270", "105560", "055550", "012330", "028260", "066570",
    "003670", "096770", "034730", "015760", "032830", "017670", "030200", "086790",
    "009150", "011200", "010130", "316140", "024110", "018260", "010950", "090430",
    "051900", "161390", "097950", "078930", "011170", "002790", "000810", "138040",
    "005940", "071050", "016360", "029780", "008770", "069960", "023530", "003550",
    "047810", "010620",
]


def mask(s, keep=6):
    s = str(s or "")
    return s[:keep] + "*" * max(0, len(s) - keep)


def get_approval_key():
    if not (APP_KEY and APP_SECRET):
        sys.exit("[설정오류] KIS_APP_KEY / KIS_APP_SECRET 미설정")
    body = json.dumps({"grant_type": "client_credentials",
                       "appkey": APP_KEY, "secretkey": APP_SECRET}).encode()
    req = urllib.request.Request(REST + "/oauth2/Approval", data=body,
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        key = json.loads(r.read())["approval_key"]
    print(f"[approval] 발급 OK  key={mask(key)}")
    return key


def sub_msg(key, tr_id, tr_key, tr_type="1"):
    return json.dumps({
        "header": {"approval_key": key, "custtype": "P",
                   "tr_type": tr_type, "content-type": "utf-8"},
        "body": {"input": {"tr_id": tr_id, "tr_key": tr_key}},
    })


def main():
    key = get_approval_key()
    ws = websocket.create_connection(WS, timeout=5)
    print(f"[ws] 연결 OK  {WS}  TR={TR}")

    ok, first_fail = 0, None
    for i, sym in enumerate(SYMBOLS, 1):
        ws.send(sub_msg(key, TR, sym))
        # ack 대기 (데이터 프레임은 '0'/'1' 로 시작 → 건너뜀)
        ack = None
        for _ in range(10):
            try:
                m = ws.recv()
            except Exception:
                break
            if m and m[0] == "{":
                ack = json.loads(m)
                break
        if ack is None:
            continue
        b = ack.get("body", {})
        rt = b.get("rt_cd")
        if rt == "0":
            ok += 1
        else:
            first_fail = (i, sym, rt, b.get("msg_cd"), str(b.get("msg1", "")).strip())
            print(f"[한도] {i}번째 등록 실패 → 직전까지 성공 {ok}건 | rt_cd={rt} "
                  f"msg_cd={first_fail[3]} msg1={first_fail[4]}")
            break
    if first_fail is None:
        print(f"[한도] {len(SYMBOLS)}종목 전부 등록 성공 (한도 미도달 또는 한도 ≥ {len(SYMBOLS)})")
    else:
        print(f"[한도] 세션당 동시 등록 한도 ≈ {ok}건 (문서상 41 대조)")

    # 장중이면 체결틱 샘플 (최대 8초)
    print("\n[데이터] 수신 샘플(최대 8초, 장 마감시 없음):")
    ws.settimeout(8)
    seen = 0
    t0 = time.time()
    while time.time() - t0 < 8 and seen < 3:
        try:
            m = ws.recv()
        except Exception:
            break
        if m and m[0] in "01":  # 실시간 데이터 프레임: 암호화여부|TR_ID|건수|필드^필드^...
            parts = m.split("|")
            if len(parts) >= 4:
                fields = parts[3].split("^")
                seen += 1
                # H0STCNT0: [0]종목 [1]체결시각 [2]현재가 ... [12]틱체결량 [13]누적거래량
                print(f"  {parts[1]} 종목={fields[0]} 시각={fields[1]} 현재가={fields[2]} "
                      f"전일대비율={fields[5] if len(fields) > 5 else '?'} "
                      f"틱량={fields[12] if len(fields) > 12 else '?'} "
                      f"누적량={fields[13] if len(fields) > 13 else '?'}")
    if seen == 0:
        print("  (수신 없음 — 장 마감/비거래시간으로 추정)")
    ws.close()
    print("\n[종료] 연결 정상 종료")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[오류] {type(e).__name__}: {e}")
