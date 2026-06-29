#!/usr/bin/env python3
"""
python-kis 실시간 '구독 등록' 실측: 캡(MAX SUBSCRIBE OVER) 동작을 직접 측정.

목적: raw WebSocket에서 본 등록 한도(IRP=3 / 모의=41)를 python-kis로도 재현/실측해
      추론을 사실로 전환한다. 시세 데이터(틱) 없이도 '등록' 단계에서 캡이 걸리므로
      장 마감/주말에도 측정 가능.

핵심 발견(소스): python-kis 2.1.6은 OPSP0008(MAX SUBSCRIBE OVER)에 대한 case가 없어
      예외 없이 경고 로그만 남기고 조용히 무시함 → 콜백이 안 오는 형태로 실패.
      이 스크립트는 'pykis' 로거를 가로채 등록 성공(OPSP0000) / 캡초과(OPSP0008)를 집계한다.

보안: id/appkey/secret/계좌는 환경변수로만. 코드/로그/repo 노출 금지.
환경변수:
  export KIS_HTS_ID=...    KIS_APP_KEY=...   KIS_APP_SECRET=...
  export KIS_ACCOUNT=44444444-29
  export KIS_VIRTUAL=0     # 1=모의(데모 키), 0=실전(IRP 키)
실행:
  python verify/yhr/pykis/realtime_cap.py
"""
import os
import sys
import time
import logging

REQUIRED = ["KIS_HTS_ID", "KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT"]
missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    sys.exit(f"[설정오류] 환경변수 미설정: {', '.join(missing)}")

try:
    from pykis import PyKis, KisAuth
except ModuleNotFoundError:
    sys.exit("[의존성] python-kis 미설치 → 'pip install python-kis' (Python 3.10+)")

# 등록 6종목(>3)으로 캡 경계를 넘겨본다 (시세 데이터는 공개정보)
SYMBOLS = ["005930", "000660", "207940", "005380", "035420", "051910"]


class CapCounter(logging.Handler):
    """pykis 로거에서 등록 성공/캡초과를 집계."""
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.subscribed = 0
        self.cap_over = 0
        self.others = []

    def emit(self, record):
        msg = record.getMessage()
        if "RTC Subscribed to" in msg:
            self.subscribed += 1
        elif "OPSP0008" in msg or "MAX SUBSCRIBE OVER" in msg:
            self.cap_over += 1
        elif "Unhandled control message" in msg:
            # OPSP0008이 case _ 로 빠지는 경로
            if "OPSP0008" in msg:
                self.cap_over += 1
            else:
                self.others.append(msg[:120])


def mask(s, keep=2):
    s = str(s or "")
    return s[:keep] + "*" * max(0, len(s) - keep) if s else ""


def main():
    virtual = os.environ.get("KIS_VIRTUAL", "0") == "1"
    counter = CapCounter()
    plog = logging.getLogger("pykis")
    plog.setLevel(logging.DEBUG)
    plog.addHandler(counter)

    auth = KisAuth(
        id=os.environ["KIS_HTS_ID"],
        appkey=os.environ["KIS_APP_KEY"],
        secretkey=os.environ["KIS_APP_SECRET"],
        account=os.environ["KIS_ACCOUNT"],
        virtual=virtual,
    )
    kis = PyKis(auth, keep_token=True)
    env = "모의(VTS)" if virtual else "실전"
    print(f"[접속] {env}  account={mask(os.environ['KIS_ACCOUNT'], 2)}")
    print(f"[테스트] {len(SYMBOLS)}종목 실시간(price) 구독 시도 → 등록 성공/캡초과 집계\n")

    recv = {}
    tickets = []

    def make_cb(sym):
        def cb(sender, e):
            recv[sym] = recv.get(sym, 0) + 1
        return cb

    for sym in SYMBOLS:
        try:
            tickets.append(kis.stock(sym).on("price", make_cb(sym)))
            print(f"  on('price') 호출: {sym}")
            time.sleep(0.5)  # 서버 ack 수신 여유
        except Exception as ex:
            print(f"  {sym} 구독 예외: {type(ex).__name__}: {ex}")

    time.sleep(3)  # 잔여 ack 수집

    print("\n=== 실측 결과 ===")
    print(f"  등록 성공(OPSP0000)  : {counter.subscribed}")
    print(f"  캡초과(OPSP0008)     : {counter.cap_over}")
    if counter.others:
        print(f"  기타 미처리 메시지   : {len(counter.others)}")
        for m in counter.others[:5]:
            print(f"    - {m}")
    print(f"  실제 콜백 수신 종목   : {len([s for s,c in recv.items() if c>0])} "
          f"(장중 아니면 0 정상)")
    print("\n[해석]")
    print("  - 성공3 + 캡초과3  → IRP 실전과 동일한 3건 캡을 python-kis도 그대로 겪음(확정).")
    print("  - 성공6 + 캡초과0  → 모의/위탁 appkey라 캡 미도달(라이브러리는 정상 등록).")
    print("  - python-kis는 OPSP0008을 예외로 안 알리고 경고 로그만 남김(조용한 실패).")

    for t in tickets:
        try:
            t.unsubscribe()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[오류] {type(e).__name__}: {e}")
