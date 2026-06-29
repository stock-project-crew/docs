#!/usr/bin/env python3
"""
python-kis(Soju06/python-kis) 검증: 통합 잔고 필드 + 실시간 시세 구독.

보안: id/appkey/secret/계좌는 환경변수로만. 코드/로그/repo 노출 금지.
실행 전:
  python3.11 -m venv .venv && . .venv/bin/activate
  pip install python-kis
환경변수:
  export KIS_HTS_ID=...            # HTS 로그인 ID (python-kis 필수)
  export KIS_APP_KEY=...           # App Key
  export KIS_APP_SECRET=...        # App Secret
  export KIS_ACCOUNT=44444444-29   # 계좌번호 8-2 형식
  export KIS_VIRTUAL=0             # 1=모의, 0=실전
  export KIS_RT=0                  # 1이면 실시간 시세도 테스트(장중에만 데이터)
실행:
  python verify/yhr/pykis/balance_quote.py
"""
import os
import sys
import time

REQUIRED = ["KIS_HTS_ID", "KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT"]
missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    sys.exit(f"[설정오류] 환경변수 미설정: {', '.join(missing)}")

try:
    from pykis import PyKis, KisAuth
except ModuleNotFoundError:
    sys.exit("[의존성] python-kis 미설치 → 'pip install python-kis' (Python 3.10+)")


def mask(s, keep=2):
    s = str(s or "")
    return s[:keep] + "*" * max(0, len(s) - keep) if s else ""


def fmt(x):
    # Decimal/float를 사람이 읽기 쉬운 표기로 (지수표기 방지)
    if x is None:
        return "-"
    try:
        f = float(x)
        return f"{int(f):,}" if f == int(f) else f"{f:,.4f}"
    except (TypeError, ValueError):
        return str(x)


def main():
    virtual = os.environ.get("KIS_VIRTUAL", "0") == "1"
    auth = KisAuth(
        id=os.environ["KIS_HTS_ID"],
        appkey=os.environ["KIS_APP_KEY"],
        secretkey=os.environ["KIS_APP_SECRET"],
        account=os.environ["KIS_ACCOUNT"],
        virtual=virtual,
    )
    kis = PyKis(auth, keep_token=True)
    print(f"[접속] virtual={virtual}  account={mask(os.environ['KIS_ACCOUNT'], 2)}")

    # ---- 통합 잔고 ---------------------------------------------------------
    bal = kis.account().balance()
    print("\n=== balance() 계좌 요약 ===")
    print(f"  총매입(purchase_amount): {fmt(bal.purchase_amount)}")
    print(f"  총평가(current_amount) : {fmt(bal.current_amount)}")
    print(f"  평가손익(profit)       : {fmt(bal.profit)}  ({float(bal.profit_rate):.2f}%)")
    print(f"  통화별 예수금(deposits):")
    for cur, dep in bal.deposits.items():
        print(f"    - {cur}: amount={fmt(dep.amount)}  출금가능={fmt(dep.withdrawable_amount)}  환율={fmt(dep.exchange_rate)}")

    print(f"\n=== 보유종목(stocks) {len(bal.stocks)}건 ===")
    for s in bal.stocks:
        # 주의: python-kis 2.1.6의 s.domestic/foreign은 market='KRX' 리터럴을 오분류함.
        # 신뢰 가능한 판별은 통화(KRW=국내) 기준.
        tag = "국내" if s.currency == "KRW" else "해외"
        print(f"  [{tag}] {s.symbol} {s.name} (market={s.market})")
        print(f"        수량={fmt(s.qty)} 평단={fmt(s.purchase_price)} 현재가={fmt(s.current_price)} 통화={s.currency} 환율={fmt(s.exchange_rate)}")
        print(f"        평가금액={fmt(s.amount)} 평가손익={fmt(s.profit)}({float(s.profit_rate):.2f}%) 원화환산매입={fmt(s.purchase_amount_krw)}")

    # ---- 실시간 시세(옵션) -------------------------------------------------
    if os.environ.get("KIS_RT", "0") == "1" and bal.stocks:
        sym = bal.stocks[0]
        stock = kis.stock(sym.symbol)
        print(f"\n=== 실시간 시세 구독 테스트: {sym.symbol} (15초) ===")
        cnt = {"n": 0}

        def on_price(sender, e):
            r = e.response
            cnt["n"] += 1
            if cnt["n"] <= 5:
                print(f"  tick {cnt['n']}: price={r.price} 전일대비율={r.change_rate}% "
                      f"틱량={r.volume} 전일거래량대비={r.volume_rate} 체결강도={r.intensity} {r.time_kst}")

        ticket = stock.on("price", on_price)
        try:
            time.sleep(15)
        finally:
            ticket.unsubscribe()
        print(f"  수신 tick 수: {cnt['n']}  (0이면 장 마감/비거래시간)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[오류] {type(e).__name__}: {e}")
