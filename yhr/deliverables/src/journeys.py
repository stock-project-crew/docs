#!/usr/bin/env python3
"""사용자 여정 이미지를 실제 앱 캡처로 합성한다.

screens/의 캡처를 여정 순서로 늘어놓고, 화면 사이 화살표 위에 누르는 것을, 화면 아래에 한 줄 설명을 단다.
캡처를 다시 찍으면 이 스크립트만 다시 돌린다.

필요한 것: Python 3, Pillow
실행:  python3 journeys.py
출력:  ../journeys/<번호>-<이름>.png

캡처를 다시 찍는 법은 ../journeys.md의 "다시 찍기"에 있다.
"""

import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SCREENS = os.path.join(HERE, "..", "screens")
OUT = os.path.join(HERE, "..", "journeys")
FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"

BG = "#F7F9FC"
TXT = "#1A1D24"
SUB = "#4B5563"
MUT = "#8A93A0"
LINE = "#3B5BDB"
FRAME = "#1A1D24"
PLACE_BG = "#ECEEF1"

PHONE_W = 330          # 캡처를 줄인 폭(390pt 화면의 약 0.85배)
PER_ROW = 5
GAP = 120              # 화면 사이(화살표 자리)
MARGIN = 60

# (캡처 이름 또는 None=자리만, 이 화면으로 올 때 누르는 것, 화면 아래 설명)
JOURNEYS = [
    ("1-first-link", "처음 계좌를 연동하고 자산을 본다",
     "계좌가 없는 사용자가 한국투자증권 계좌를 연동하고 동기화를 요청한다", [
         ("login", "", "계정은 관리자가 발급한다. 회원가입이 없다"),
         ("summary-empty", "로그인", "계좌가 없으면 요약이 연동 안내가 된다"),
         ("account-link-empty", "계좌 탭 · 계좌 연동 관리", "연동한 계좌 목록"),
         ("kis-link-form", "＋ 계좌 연동", "앱키 · 시크릿 · 계좌번호. 값은 DB가 아니라 비밀 저장소로 간다"),
         ("account-link-connecting", "연동하기", "연동 중. 데이터팀의 다음 정기 수집 뒤 잔고가 반영된다"),
         ("accounts-sync-requested", "‹ · 지금 동기화", "수집은 서버가 아니라 데이터팀이 다음 수집 시각에 한다"),
     ]),
    ("2-concentration", "어디에 쏠렸나",
     "보유 종목을 보고, ETF를 구성종목으로 나눠 실제 노출을 본다", [
         ("positions", "", "계좌를 합친 종목별 보유. 평가금액은 일별 종가"),
         ("positions-etf", "ETF 분해 켜기", "ETF가 구성종목으로 나뉜다. 구성종목을 모르는 ETF는 그대로 남기고 알린다"),
         ("allocation", "비중 탭 · 섹터", "같은 라인을 섹터로 묶는다. 행을 더하면 총자산이다"),
         ("allocation-etf", "ETF 분해 켜기", "ETF 안의 반도체가 반도체로 더해진다"),
         ("instrument-detail", "종목 탭 · 종목 행", "어느 계좌에 얼마나, 언제 얼마에 팔았나"),
     ]),
    ("3-earned-or-deposited", "번 돈인가 넣은 돈인가",
     "판 것으로 번 돈에서 시작해 기간 동안 늘어난 자산을 나눠 본다", [
         ("realized-pnl", "", "올해 판 것의 실현손익. 취득원가를 추정한 매도는 표시한다"),
         ("asset-change", "이 기간 전체 투자손익 보기 →", "늘어난 자산 = 넣은 돈 + 번 돈 + 계좌 편입"),
         ("cashflows", "넣은 돈 입력 →", "증권사가 입출금 내역을 주지 않아 넣은 돈은 사용자가 입력한다"),
     ]),
    ("4-alert", "알림을 걸고 울림을 받는다",
     "종목에 조건을 걸면 서버가 평가해 참이 되면 울리고 푸시를 보낸다", [
         ("instrument-detail", "", "종목 상세에서 알림을 건다"),
         ("alert-pick-condition", "알림 걸기", "프리셋 9종 또는 직접 조건"),
         ("alert-preset-input", "가격 도달", "저장 전에 지금 값으로 충족 여부를 미리 본다"),
         ("alert-common-settings", "다음", "이미 충족 중이면 곧 울린다고 알린다"),
         ("alert-detail", "저장", "감시 중. 평가 시점마다 서버가 평가한다"),
         ("alerts-tab", "1분 안에 평가 · 울림", "울림은 앱 안 기록으로 반드시 남고 배지가 켜진다"),
         (None, "푸시", "푸시(실기기 캡처 자리)"),
         ("fired-detail", "푸시를 누름", "울린 이유는 울린 그때의 값으로 남는다"),
     ]),
    ("5-unknown-is-shown", "모르면 모른다고 보인다",
     "계산할 수 없는 값을 0이나 그럴듯한 값으로 채우지 않는다", [
         ("summary", "", "수집에 실패한 계좌는 지난 값을 쓰고 그 사실을 띄운다"),
         ("realized-pnl", "", "취득원가 추정 · 합계에서 뺀 매도를 배지와 문장으로 알린다"),
         ("accounts-notices", "", "인증에 실패한 계좌에 갱신 버튼을 단다"),
         ("positions-etf", "", "구성종목을 모르는 ETF는 쪼개지 않고 미분해로 남긴다"),
         ("alert-detail-unknown", "", "일봉이 모자라면 참 · 거짓 대신 확인 불가"),
     ]),
]


def font(size, bold=False):
    # AppleSDGothicNeo.ttc: 0 Regular, 6 Bold 근처. 굵기는 인덱스로 고른다.
    return ImageFont.truetype(FONT, size, index=6 if bold else 0)


def wrap(draw, text, f, width):
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=f) > width and cur:
            lines.append(cur)
            cur = ch.lstrip()
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def phone(name):
    if name is None:
        return None
    im = Image.open(os.path.join(SCREENS, name + ".png")).convert("RGB")
    h = round(im.height * PHONE_W / im.width)
    return im.resize((PHONE_W, h), Image.LANCZOS)


def rounded(im, r):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    out = Image.new("RGBA", im.size)
    out.paste(im, (0, 0), mask)
    return out


def render(key, title, subtitle, steps):
    phones = [phone(n) for n, _, _ in steps]
    ph = max(p.height for p in phones if p is not None)
    cap_h = 90
    rows = (len(steps) + PER_ROW - 1) // PER_ROW
    cols = min(len(steps), PER_ROW)
    head = 150
    w = MARGIN * 2 + cols * PHONE_W + (cols - 1) * GAP
    row_h = ph + 20 + cap_h + 60
    h = head + rows * row_h + 20
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    d.text((MARGIN, 40), title, font=font(44, True), fill=TXT)
    d.text((MARGIN, 100), subtitle, font=font(24), fill=SUB)
    fcap, farrow = font(20), font(19, True)
    for i, ((name, action, caption), p) in enumerate(zip(steps, phones)):
        r, c = divmod(i, PER_ROW)
        x = MARGIN + c * (PHONE_W + GAP)
        y = head + r * row_h
        if p is None:
            d.rounded_rectangle((x, y, x + PHONE_W, y + ph), 36, fill=PLACE_BG, outline=MUT, width=3)
            for k, line in enumerate(wrap(d, caption, font(24, True), PHONE_W - 60)):
                tw = d.textlength(line, font=font(24, True))
                d.text((x + (PHONE_W - tw) / 2, y + ph / 2 - 20 + k * 34), line, font=font(24, True), fill=MUT)
        else:
            img.paste(rounded(p, 36), (x, y), rounded(p, 36))
            d.rounded_rectangle((x - 3, y - 3, x + PHONE_W + 3, y + p.height + 3), 39, outline=FRAME, width=4)
        if p is not None:
            for k, line in enumerate(wrap(d, caption, fcap, PHONE_W)):
                d.text((x, y + ph + 20 + k * 28), line, font=fcap, fill=TXT)
        # 화살표: 같은 줄의 앞 화면에서 이 화면으로. 줄이 바뀌면 줄 앞에 라벨만 둔다.
        if i > 0 and action:
            if c > 0:
                ax0, ax1, ay = x - GAP + 12, x - 12, y + ph / 2
                d.line((ax0, ay, ax1, ay), fill=LINE, width=4)
                d.polygon([(ax1, ay), (ax1 - 16, ay - 10), (ax1 - 16, ay + 10)], fill=LINE)
                lines = wrap(d, action, farrow, GAP - 8)
                for k, line in enumerate(lines):
                    tw = d.textlength(line, font=farrow)
                    d.text((x - GAP / 2 - tw / 2, ay - 16 - (len(lines) - k) * 26), line, font=farrow, fill=LINE)
            else:
                d.text((x, y - 34), "→ " + action, font=farrow, fill=LINE)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, key + ".png")
    img.save(path, optimize=True)
    print(f"{key}: 화면 {len(steps)}개 → {path}")


if __name__ == "__main__":
    for j in JOURNEYS:
        render(*j)
