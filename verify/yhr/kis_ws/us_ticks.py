#!/usr/bin/env python3
"""
KIS 미국주식 실시간(WebSocket) 틱 수신 검증 — 프리마켓/정규장.

목적: 해외(미국) 실시간지연체결가 HDFSCNT0(미국=0분 지연 무료)로 실제 틱을 받아
      가격·등락률·체결량·누적거래량 필드 실값을 확인. (급락/거래량급증 신호의 원천)

⚠️ 한도: 현재 IRP(29) appkey는 실시간 등록 3건 캡 → 미국도 3종목까지. 검증엔 충분.

시간(KST) 가이드:
  - 미국 정규장: 약 22:30~05:00 → 틱 가장 풍부(가장 확실)
  - 미국 프리마켓: 약 17:00~22:30 → 거래 적어 틱 드물 수 있음(내일 20:00 슬롯이 여기)
  - 미국 애프터마켓: 약 05:00~07:00
  ※ 한국 낮(국내장 시간)엔 미국 틱 없음.

보안: appkey/secret 환경변수로만. 코드/로그/repo 노출 금지.
실행 전: pip install websocket-client (또는 .venv 활성화)
환경변수:
  export KIS_APP_KEY=...      # 실전 IRP 키로 미국 시세 조회 가능(IRP도 시세조회 허용)
  export KIS_APP_SECRET=...
  export US_SYMBOLS=DNASAAPL,DNASTSLA,DNASNVDA   # 생략 시 기본값. 형식: D+거래소(NAS/NYS/AMS)+심볼
  export US_WINDOW=60        # 수신 대기 초(기본 60)
실행:
  python verify/yhr/kis_ws/us_ticks.py
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

REST = "https://openapi.koreainvestment.com:9443"
WS = "ws://ops.koreainvestment.com:21000"
APP_KEY = os.environ.get("KIS_APP_KEY", "")
APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
TR = "HDFSCNT0"  # 해외주식 실시간지연체결가 (미국=실시간 0분지연 무료)
SYMBOLS = [s.strip() for s in os.environ.get(
    "US_SYMBOLS", "DNASAAPL,DNASTSLA,DNASNVDA").split(",") if s.strip()][:3]
WINDOW = int(os.environ.get("US_WINDOW", "60"))

# HDFSCNT0 응답 컬럼(인덱스 매핑)
COL = {"SYMB": 0, "XHMS": 4, "KHMS": 6, "OPEN": 7, "HIGH": 8, "LOW": 9,
       "LAST": 10, "DIFF": 12, "RATE": 13, "EVOL": 18, "TVOL": 19, "STRN": 23}


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
    print(f"[ws] 연결 OK  {WS}  TR={TR}")

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
        if ack and ack.get("body", {}).get("rt_cd") == "0":
            ok += 1
            print(f"  구독 OK: {sym}")
        else:
            b = ack.get("body", {}) if ack else {}
            print(f"  구독 실패: {sym} | rt_cd={b.get('rt_cd')} msg={str(b.get('msg1','')).strip()}")
    print(f"[구독] 성공 {ok}/{len(SYMBOLS)}종목\n")

    print(f"[데이터] 미국 실시간 틱 수신 ({WINDOW}초)...")
    ws.settimeout(WINDOW)
    seen = {}
    t0 = time.time()
    while time.time() - t0 < WINDOW:
        try:
            m = ws.recv()
        except Exception:
            break
        if m and m[0] in "01":
            parts = m.split("|")
            if len(parts) >= 4 and parts[1] == TR:
                f = parts[3].split("^")
                if len(f) <= COL["TVOL"]:
                    continue
                sym = f[COL["SYMB"]]
                seen[sym] = seen.get(sym, 0) + 1
                if seen[sym] <= 3:  # 종목당 처음 3틱만 출력
                    print(f"  {sym} 한국시각={f[COL['KHMS']]} 현재가(LAST)={f[COL['LAST']]} "
                          f"등락률(RATE)={f[COL['RATE']]}% 체결량(EVOL)={f[COL['EVOL']]} "
                          f"누적(TVOL)={f[COL['TVOL']]} 체결강도(STRN)={f[COL['STRN']] if len(f)>COL['STRN'] else '?'}")
    print()
    if seen:
        print(f"[결과] 수신 틱: " + ", ".join(f"{k}={v}건" for k, v in seen.items()))
        print("  → 미국 실시간(0분 지연) 틱 수신 확인. LAST/RATE/EVOL/TVOL로 급락·거래량급증 산출 가능.")
    else:
        print("[결과] 수신 0건.")
        print("  → 프리마켓이라 거래가 없거나, 해당 종목 미거래 구간일 수 있음.")
        print("  → 가장 확실한 검증은 미국 정규장(약 22:30 KST 이후) 재시도.")
    ws.close()
    print("\n[종료] 연결 정상 종료")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[오류] {type(e).__name__}: {e}")
