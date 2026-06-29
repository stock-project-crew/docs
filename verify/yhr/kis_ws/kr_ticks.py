#!/usr/bin/env python3
"""
KIS 국내주식 실시간(WebSocket) 틱 수신 검증 — 장중(09:00~15:30 KST).

목적: 국내 실시간체결가 H0STCNT0로 실제 틱을 받아 현재가·전일대비율·틱체결량·
      누적거래량 실값을 확인하고, 급락·거래량급증 산출이 실제로 가능한지 검증.

⚠️ 한도: 현재 IRP(29) appkey는 실시간 등록 3건 캡 → 3종목까지. 틱 검증엔 충분.
⏰ 09:00~15:20 연속체결 구간에 실행 권장(15:20~15:30은 단일가라 체결틱이 끊김).

보안: appkey/secret 환경변수로만. 코드/로그/repo 노출 금지.
실행 전: .venv 활성화(websocket-client 포함) 또는 pip install websocket-client
환경변수:
  export KIS_APP_KEY=...        # 실전 IRP 키(시세조회 허용)
  export KIS_APP_SECRET=...
  export KR_SYMBOLS=005930,000660,035720   # 생략 시 기본(삼성전자/SK하이닉스/카카오)
  export KR_WINDOW=60          # 수신 대기 초(기본 60)
실행:
  python verify/yhr/kis_ws/kr_ticks.py
"""
import os
import sys
import json
import time
import urllib.request

try:
    import websocket  # websocket-client
except ModuleNotFoundError:
    sys.exit("[의존성] 'pip install websocket-client' 필요(또는 .venv 활성화)")

REST = "https://openapi.koreainvestment.com:9443"
WS = "ws://ops.koreainvestment.com:21000"
APP_KEY = os.environ.get("KIS_APP_KEY", "")
APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
TR = "H0STCNT0"
SYMBOLS = [s.strip() for s in os.environ.get(
    "KR_SYMBOLS", "005930,000660,035720").split(",") if s.strip()][:3]
WINDOW = int(os.environ.get("KR_WINDOW", "60"))

# H0STCNT0 컬럼 인덱스(소스 확인)
I = {"CODE": 0, "TIME": 1, "PRICE": 2, "CHG_RATE": 5, "TICK_VOL": 12,
     "ACML_VOL": 13, "STRENGTH": 18, "PRDY_VOL_RATE": 23}


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


def sub_msg(key, tr_key):
    return json.dumps({
        "header": {"approval_key": key, "custtype": "P",
                   "tr_type": "1", "content-type": "utf-8"},
        "body": {"input": {"tr_id": TR, "tr_key": tr_key}},
    })


def main():
    key = get_approval_key()
    ws = websocket.create_connection(WS, timeout=5)
    print(f"[ws] 연결 OK  {WS}  TR={TR}  종목={SYMBOLS}")

    ok = 0
    for sym in SYMBOLS:
        ws.send(sub_msg(key, sym))
        ack = None
        for _ in range(10):
            try:
                m = ws.recv()
            except Exception:
                break
            if m and m[0] == "{":
                ack = json.loads(m)
                break
        b = ack.get("body", {}) if ack else {}
        if b.get("rt_cd") == "0":
            ok += 1
            print(f"  구독 OK: {sym}")
        else:
            print(f"  구독 실패: {sym} | rt_cd={b.get('rt_cd')} msg={str(b.get('msg1','')).strip()}")
    print(f"[구독] 성공 {ok}/{len(SYMBOLS)}\n")

    print(f"[데이터] 국내 실시간 틱 수신 ({WINDOW}초)...")
    ws.settimeout(WINDOW)
    stat = {}  # sym -> dict(count, first_price, last_price, min_price, max_price, tick_vol_sum)
    printed = 0
    t0 = time.time()
    while time.time() - t0 < WINDOW:
        try:
            m = ws.recv()
        except Exception:
            break
        if not (m and m[0] in "01"):
            continue
        parts = m.split("|")
        if len(parts) < 4 or parts[1] != TR:
            continue
        # 한 프레임에 여러 체결이 올 수 있음(parts[2]=건수). 첫 건만 파싱해도 검증엔 충분.
        f = parts[3].split("^")
        if len(f) <= I["ACML_VOL"]:
            continue
        sym = f[I["CODE"]]
        price = float(f[I["PRICE"]] or 0)
        s = stat.setdefault(sym, {"n": 0, "first": price, "last": price,
                                  "min": price, "max": price, "tvol": 0})
        s["n"] += 1
        s["last"] = price
        s["min"] = min(s["min"], price)
        s["max"] = max(s["max"], price)
        try:
            s["tvol"] += int(f[I["TICK_VOL"]] or 0)
        except ValueError:
            pass
        if printed < 12:  # 처음 12틱만 상세 출력
            printed += 1
            print(f"  {sym} 시각={f[I['TIME']]} 현재가={f[I['PRICE']]} 전일대비율={f[I['CHG_RATE']]}% "
                  f"틱체결량={f[I['TICK_VOL']]} 누적량={f[I['ACML_VOL']]} "
                  f"체결강도={f[I['STRENGTH']]} 전일거래량대비={f[I['PRDY_VOL_RATE']]}")

    print("\n=== 수신 요약 ===")
    if not stat:
        print("  수신 0건 — 장 시간(09:00~15:20) 확인 또는 단일가 구간(15:20~15:30) 여부 확인.")
    for sym, s in stat.items():
        drop = (s["min"] - s["first"]) / s["first"] * 100 if s["first"] else 0
        print(f"  {sym}: {s['n']}틱 | 시작={s['first']:.0f} 현재={s['last']:.0f} "
              f"min={s['min']:.0f} max={s['max']:.0f} | 윈도우내 최대낙폭={drop:+.2f}% "
              f"| 틱체결량합={s['tvol']:,}")
    if stat:
        print("\n  → 현재가·전일대비율·틱체결량·누적거래량 실값 수신 확인.")
        print("    급락(최대낙폭)·거래량급증(틱체결량합/전일거래량대비) 산출 가능 검증 완료.")
    ws.close()
    print("\n[종료] 연결 정상 종료")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[오류] {type(e).__name__}: {e}")
