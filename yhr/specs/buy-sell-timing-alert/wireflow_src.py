# -*- coding: utf-8 -*-
"""매수·매도 타이밍 알림 — 와이어플로우 생성기 (단일 소스 → drawio + png)

실행:  pip install pillow && python3 wireflow_src.py
출력:  wireflow.drawio · wireflow.png (이 파일과 같은 디렉터리)
drawio 파일을 app.diagrams.net에서 직접 편집한 경우, 이 스크립트도 함께 수정해야
두 산출물이 어긋나지 않는다. 프리미티브·컴포넌트는 포트폴리오 와이어플로우 생성기와 같다.
"""


from PIL import Image, ImageDraw, ImageFont

# ── 팔레트 (포트폴리오 와이어플로우와 공통) ──────────────────────
BG      = '#F7F9FC'
FRAME   = '#AAB2C0'
BORDER  = '#E2E7EF'
LINE    = '#B7C0D0'
PANEL   = '#F4F6FA'
PANEL2  = '#EDF1F7'
TXT     = '#1A1D24'
SUB     = '#3A4048'
MUT     = '#6B7280'
FAINT   = '#8A93A0'
DIM     = '#9AA1AC'
PRI     = '#3B5BDB'
UP      = '#E0483C'   # 상승(빨강)
DOWN    = '#1F6FE5'   # 하락(파랑)
GRN     = '#2E7D52'
GRN_BG  = '#E7F3EC'
GRN_BOX = '#F0FAF3'
GRN_ST  = '#7FC79A'
AMB     = '#E0A93B'
AMB_TX  = '#B7791F'
AMB_BG  = '#FBEFD3'
AMB_BOX = '#FDF3D6'
AMB_ST  = '#C7B98F'
GRY_BG  = '#ECEEF1'
BLU_BG  = '#DCE6F8'
INF_BOX = '#EAF0FB'
INF_ST  = '#9DB6E6'
CARD_ST = '#E2E7EF'

FONT_KR = '/System/Library/Fonts/AppleSDGothicNeo.ttc'
FONT_MN = '/System/Library/Fonts/Supplemental/Courier New.ttf'
_IDX = {False: 0, True: 6}

SHAPES = []
_seq = [0]


def _nid():
    _seq[0] += 1
    return 'p%d' % _seq[0]


def esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
             .replace('"', '&quot;').replace('\n', '&lt;br&gt;'))


# ── 프리미티브 ────────────────────────────────────────────────
def rect(x, y, w, h, fill='#FFFFFF', stroke='none', sw=1, arc=0, shadow=False,
         ellipse=False, dashed=False):
    i = _nid()
    SHAPES.append(dict(t='rect', id=i, x=x, y=y, w=w, h=h, fill=fill, stroke=stroke,
                       sw=sw, arc=arc, shadow=shadow, ellipse=ellipse, dashed=dashed))
    return i


def text(x, y, w, h, s, size=12, color=TXT, align='left', valign='middle',
         bold=False, mono=False, sl=0, sr=0):
    i = _nid()
    SHAPES.append(dict(t='text', id=i, x=x, y=y, w=w, h=h, s=s, size=size, color=color,
                       align=align, valign=valign, bold=bold, mono=mono, sl=sl, sr=sr))
    return i


def edge(pts, label='', color=PRI, dashed=False, lseg=None, loff=(0, -11)):
    """pts: 직교 폴리라인 좌표열. lseg: 라벨을 놓을 세그먼트 인덱스(기본 가장 긴 것)."""
    i = _nid()
    SHAPES.append(dict(t='edge', id=i, pts=pts, label=label, color=color,
                       dashed=dashed, lseg=lseg, loff=loff))
    return i


def diamond(x, y, w, h, s):
    i = _nid()
    SHAPES.append(dict(t='diamond', id=i, x=x, y=y, w=w, h=h, s=s))
    return i


# ── drawio XML ───────────────────────────────────────────────
def to_drawio(pw, ph, name):
    o = ['<mxfile host="app.diagrams.net">',
         '  <diagram name="%s" id="wf1">' % name,
         ('    <mxGraphModel dx="1600" dy="1000" grid="0" gridSize="8" guides="1" '
          'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
          'pageWidth="%d" pageHeight="%d" math="0" shadow="0" background="%s">' % (pw, ph, BG)),
         '      <root>', '        <mxCell id="0"/>', '        <mxCell id="1" parent="0"/>']
    for s in SHAPES:
        if s['t'] == 'rect':
            st = 'whiteSpace=wrap;html=1;fillColor=%s;strokeColor=%s;strokeWidth=%s;' % (
                s['fill'], s['stroke'], s['sw'])
            st += 'rounded=%d;' % (1 if s['arc'] else 0)
            if s['arc']:
                st += 'arcSize=%d;' % s['arc']
            if s['ellipse']:
                st += 'shape=ellipse;'
            if s['shadow']:
                st += 'shadow=1;'
            if s['dashed']:
                st += 'dashed=1;dashPattern=4 4;'
            o.append('<mxCell id="%s" value="" style="%s" vertex="1" parent="1">'
                     '<mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
                     % (s['id'], st, s['x'], s['y'], s['w'], s['h']))
        elif s['t'] == 'text':
            st = ('text;html=1;whiteSpace=wrap;fillColor=none;strokeColor=none;'
                  'fontSize=%d;fontColor=%s;align=%s;verticalAlign=%s;spacingLeft=%d;'
                  'spacingRight=%d;spacingTop=1;fontStyle=%d;'
                  % (s['size'], s['color'], s['align'], s['valign'], s['sl'], s['sr'],
                     1 if s['bold'] else 0))
            if s['mono']:
                st += 'fontFamily=Courier New;'
            o.append('<mxCell id="%s" value="%s" style="%s" vertex="1" parent="1">'
                     '<mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
                     % (s['id'], esc(s['s']), st, s['x'], s['y'], s['w'], s['h']))
        elif s['t'] == 'diamond':
            st = ('rhombus;whiteSpace=wrap;html=1;fillColor=#FFF7E6;strokeColor=#E0A93B;'
                  'strokeWidth=1.5;fontSize=11;fontColor=#8A5A00;fontStyle=1;')
            o.append('<mxCell id="%s" value="%s" style="%s" vertex="1" parent="1">'
                     '<mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
                     % (s['id'], esc(s['s']), st, s['x'], s['y'], s['w'], s['h']))
        elif s['t'] == 'edge':
            st = ('edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;'
                  'jettySize=auto;strokeColor=%s;strokeWidth=2;fontColor=%s;fontSize=11;'
                  'fontStyle=1;labelBackgroundColor=#FFFFFF;spacing=4;'
                  % (s['color'], s['color']))
            if s['dashed']:
                st += 'dashed=1;dashPattern=6 4;'
            p = s['pts']
            mid = ''.join('<mxPoint x="%d" y="%d" as="point"/>' % (a, b) for a, b in p[1:-1])
            o.append('<mxCell id="%s" value="%s" style="%s" edge="1" parent="1">'
                     '<mxGeometry relative="1" as="geometry">'
                     '<mxPoint x="%d" y="%d" as="sourcePoint"/>'
                     '<mxPoint x="%d" y="%d" as="targetPoint"/>'
                     '<Array as="points">%s</Array></mxGeometry></mxCell>'
                     % (s['id'], esc(s['label']), st, p[0][0], p[0][1], p[-1][0], p[-1][1], mid))
    o += ['      </root>', '    </mxGraphModel>', '  </diagram>', '</mxfile>', '']
    return '\n'.join(o)


# ── PNG ──────────────────────────────────────────────────────
_fc = {}


def _font(size, bold=False, mono=False, S=1.0):
    k = (round(size * S), bold, mono)
    if k not in _fc:
        if mono:
            _fc[k] = ImageFont.truetype(FONT_MN, k[0])
        else:
            _fc[k] = ImageFont.truetype(FONT_KR, k[0], index=_IDX[bold])
    return _fc[k]


def _hex(c):
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _pick(ch, f, fb):
    """고정폭 폰트에 한글·기호 글리프가 없으므로 ASCII만 mono, 나머지는 한글 폰트로."""
    return f if fb is None or ord(ch) < 128 else fb


def _len(d, s, f, fb=None):
    if fb is None:
        return d.textlength(s, font=f)
    return sum(d.textlength(ch, font=_pick(ch, f, fb)) for ch in s)


def _draw(d, xy, s, f, fill, fb=None):
    if fb is None:
        d.text(xy, s, font=f, fill=fill)
        return
    x, y = xy
    for ch in s:
        ff = _pick(ch, f, fb)
        d.text((x, y), ch, font=ff, fill=fill)
        x += d.textlength(ch, font=ff)


def _wrap(d, s, f, maxw, fb=None):
    out = []
    for para in s.split('\n'):
        if not para:
            out.append('')
            continue
        cur = ''
        for ch in para:
            if _len(d, cur + ch, f, fb) <= maxw or not cur:
                cur += ch
            else:
                out.append(cur)
                cur = ch
        out.append(cur)
    return out


def to_png(pw, ph, path, S=1.5):
    W, H = int(pw * S), int(ph * S)
    img = Image.new('RGB', (W, H), _hex(BG))
    d = ImageDraw.Draw(img)

    def sc(v):
        return v * S

    for s in SHAPES:
        if s['t'] == 'rect':
            x0, y0 = sc(s['x']), sc(s['y'])
            x1, y1 = sc(s['x'] + s['w']), sc(s['y'] + s['h'])
            fill = None if s['fill'] in ('none', None) else _hex(s['fill'])
            strk = None if s['stroke'] in ('none', None) else _hex(s['stroke'])
            wdt = max(1, int(round(s['sw'] * S)))
            if s['shadow']:
                sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
                ds = ImageDraw.Draw(sh)
                ds.rounded_rectangle([x0 + 3 * S, y0 + 4 * S, x1 + 3 * S, y1 + 4 * S],
                                     radius=8 * S, fill=(24, 30, 44, 26))
                img.paste(Image.alpha_composite(img.convert('RGBA'), sh).convert('RGB'), (0, 0))
                d = ImageDraw.Draw(img)
            if s['ellipse']:
                d.ellipse([x0, y0, x1, y1], fill=fill, outline=strk, width=wdt)
            else:
                r = 0
                if s['arc']:
                    r = min(s['arc'] * min(s['w'], s['h']) / 100.0 * S,
                            min(x1 - x0, y1 - y0) / 2.0)
                    r = max(r, 2 * S) if s['arc'] < 50 else min(x1 - x0, y1 - y0) / 2.0
                if r > 0.5:
                    d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=fill,
                                        outline=strk, width=wdt)
                else:
                    d.rectangle([x0, y0, x1, y1], fill=fill, outline=strk, width=wdt)

        elif s['t'] == 'diamond':
            cx, cy = sc(s['x'] + s['w'] / 2), sc(s['y'] + s['h'] / 2)
            hw, hh = sc(s['w'] / 2), sc(s['h'] / 2)
            d.polygon([(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)],
                      fill=_hex('#FFF7E6'), outline=_hex('#E0A93B'), width=max(1, int(1.5 * S)))
            f = _font(11, True, False, S)
            lines = s['s'].split('\n')
            lh = 11 * S * 1.35
            ty = cy - lh * len(lines) / 2
            for ln in lines:
                w = d.textlength(ln, font=f)
                d.text((cx - w / 2, ty), ln, font=f, fill=_hex('#8A5A00'))
                ty += lh

        elif s['t'] == 'text':
            f = _font(s['size'], s['bold'], s['mono'], S)
            fb = _font(s['size'], s['bold'], False, S) if s['mono'] else None
            bx0, bx1 = sc(s['x']) + sc(s['sl']), sc(s['x'] + s['w']) - sc(s['sr'])
            lines = _wrap(d, s['s'], f, max(4, bx1 - bx0), fb)
            lh = s['size'] * S * 1.34
            total = lh * len(lines)
            if s['valign'] == 'top':
                ty = sc(s['y']) + 1 * S
            elif s['valign'] == 'bottom':
                ty = sc(s['y'] + s['h']) - total
            else:
                ty = sc(s['y']) + (sc(s['h']) - total) / 2
            col = _hex(s['color'])
            for ln in lines:
                w = _len(d, ln, f, fb)
                if s['align'] == 'center':
                    tx = bx0 + (bx1 - bx0 - w) / 2
                elif s['align'] == 'right':
                    tx = bx1 - w
                else:
                    tx = bx0
                asc, desc = f.getmetrics()
                _draw(d, (tx, ty + (lh - (asc + desc)) / 2), ln, f, col, fb)
                ty += lh

        elif s['t'] == 'edge':
            pts = [(sc(a), sc(b)) for a, b in s['pts']]
            col = _hex(s['color'])
            w = max(2, int(round(2 * S)))
            if s['dashed']:
                for i in range(len(pts) - 1):
                    (ax, ay), (bx, by) = pts[i], pts[i + 1]
                    ln = ((bx - ax) ** 2 + (by - ay) ** 2) ** .5
                    n = max(1, int(ln / (10 * S)))
                    for k in range(n):
                        if k % 2:
                            continue
                        t0, t1 = k / n, min(1, (k + .6) / n)
                        d.line([ax + (bx - ax) * t0, ay + (by - ay) * t0,
                                ax + (bx - ax) * t1, ay + (by - ay) * t1], fill=col, width=w)
            else:
                d.line(pts, fill=col, width=w, joint='curve')
            # arrowhead
            (ax, ay), (bx, by) = pts[-2], pts[-1]
            dx, dy = bx - ax, by - ay
            ln = max(1e-6, (dx * dx + dy * dy) ** .5)
            ux, uy = dx / ln, dy / ln
            L, Wd = 11 * S, 5.5 * S
            d.polygon([(bx, by), (bx - ux * L - uy * Wd, by - uy * L + ux * Wd),
                       (bx - ux * L + uy * Wd, by - uy * L - ux * Wd)], fill=col)
            if s['label']:
                segs = [(i, abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1]))
                        for i in range(len(pts) - 1)]
                i = s['lseg'] if s['lseg'] is not None else max(segs, key=lambda t: t[1])[0]
                mx = (pts[i][0] + pts[i + 1][0]) / 2 + sc(s['loff'][0])
                my = (pts[i][1] + pts[i + 1][1]) / 2 + sc(s['loff'][1])
                f = _font(11, True, False, S)
                tw = d.textlength(s['label'], font=f)
                th = 11 * S * 1.34
                d.rectangle([mx - tw / 2 - 4 * S, my - th / 2 - 1 * S,
                             mx + tw / 2 + 4 * S, my + th / 2 + 1 * S], fill=(255, 255, 255))
                asc, desc = f.getmetrics()
                d.text((mx - tw / 2, my - th / 2 + (th - (asc + desc)) / 2), s['label'],
                       font=f, fill=col)

    img.save(path, 'PNG')
    return W, H


PW, PH = 300, 600
PGW, PGH = 2020, 2260


# ── 컴포넌트 ──────────────────────────────────────────────────
def ph(x, y, title, back=True, right=None, tab=None):
    rect(x, y, PW, PH, '#FFFFFF', FRAME, 1.5, arc=6, shadow=True)
    rect(x, y + 1, PW, 22, PANEL)
    text(x + 10, y + 1, 60, 22, '9:41', 9, MUT, bold=True)
    text(x + PW - 74, y + 1, 64, 22, '●●● ■', 9, MUT, align='right', sr=10)
    rect(x, y + 23, PW, 42, '#FFFFFF')
    rect(x, y + 64, PW, 1, BORDER)
    text(x, y + 23, PW, 42, title, 14, TXT, align='center', bold=True)
    if back:
        text(x + 10, y + 23, 24, 42, '‹', 17, PRI, bold=True)
    if right:
        text(x + PW - 96, y + 23, 86, 42, right, 11, PRI, align='right', bold=True)
    if tab:
        tabbar(x, y, tab)
    return x + 12, y + 65


def tabbar(x, y, active):
    ty = y + PH - 45
    rect(x, ty, PW, 1, BORDER)
    rect(x, ty + 1, PW, 44, '#FFFFFF')
    tw = PW / 6
    for i, lb in enumerate(['요약', '종목', '비중', '계좌', '손익', '알림']):
        on = (lb == active)
        text(x + i * tw, ty + 1, tw, 44, lb, 10, PRI if on else DIM,
             align='center', bold=on)
        if on:
            rect(x + i * tw + tw / 2 - 4, ty + 36, 8, 3, PRI, arc=50)


def card(x, y, w, h, fill='#FFFFFF', stroke=CARD_ST):
    return rect(x, y, w, h, fill, stroke, 1, arc=8)


def pill(x, y, w, h, bg, fg, s, dot=None, size=9):
    rect(x, y, w, h, bg, 'none', 1, arc=50)
    if dot:
        rect(x + 8, y + h / 2 - 3, 6, 6, dot, 'none', 1, ellipse=True)
        text(x + 18, y, w - 22, h, s, size, fg, bold=True)
    else:
        text(x, y, w, h, s, size, fg, align='center', bold=True)


def chip(x, y, w, s, on=False):
    rect(x, y, w, 24, BLU_BG if on else '#FFFFFF', 'none' if on else LINE, 1, arc=50)
    text(x, y, w, 24, s, 10, PRI if on else SUB, align='center', bold=on)


def toggle(x, y, on):
    rect(x, y, 34, 20, PRI if on else '#CDD3DE', 'none', 1, arc=50)
    rect(x + (16 if on else 2), y + 2, 16, 16, '#FFFFFF', 'none', 1, ellipse=True)


def box(x, y, w, h, kind='info'):
    m = {'info': (INF_BOX, INF_ST), 'ok': (GRN_BOX, GRN_ST), 'warn': (AMB_BOX, AMB_ST),
         'gray': (PANEL, BORDER)}
    return rect(x, y, w, h, m[kind][0], m[kind][1], 1, arc=8)


def mono(x, y, w, s, h=26):
    text(x, y, w, h, s, 9, FAINT, mono=True, valign='top')


def hr(x, y, w, c=BORDER):
    rect(x, y, w, 1, c)


def asof(x, y, w, main, right='새로고침', h=26):
    rect(x, y, w, h, PANEL)
    text(x + 12, y, w - 80, h, main, 9, MUT)
    if right:
        text(x + w - 74, y, 62, h, right, 9, PRI, align='right', bold=True)


def bar(x, y, w, h, c, pct):
    rect(x, y, w, h, '#EEF1F6', 'none', 1, arc=50)
    if pct > 0:
        rect(x, y, max(3, int(w * pct)), h, c, 'none', 1, arc=50)


def ring(cx, cy, r, label):
    rect(cx - r, cy - r, r * 2, r * 2, BLU_BG, 'none', 1, ellipse=True)
    rect(cx - r + 14, cy - r + 14, (r - 14) * 2, (r - 14) * 2, '#FFFFFF', 'none', 1, ellipse=True)
    text(cx - r, cy - 9, r * 2, 18, label, 9, MUT, align='center', bold=True)


# ══════════════════════════════════════════════════════════════
# 범례
# ══════════════════════════════════════════════════════════════
LX, LY, LW = 40, 190, 290
rect(LX, LY, LW, 900, '#FBFCFE', '#C7CFDD', 1, arc=6, shadow=True)
cx, cy = LX + 16, LY + 16
text(cx, cy, LW - 32, 26, '매수·매도 타이밍 알림', 16, TXT, bold=True)
hr(cx, cy + 34, LW - 32, '#E2E7EF')
text(cx, cy + 46, LW - 32, 18, '범례 (Legend)', 12, TXT, bold=True)

y = cy + 72
text(cx, y, LW - 32, 16, '알림 상태 (status + last_result)', 10, MUT, bold=True)
y += 20
for lb, bg, fg, dot in [('감시 중', GRN_BG, GRN, GRN),
                        ('조건 충족 중', AMB_BG, AMB_TX, AMB),
                        ('확인 불가 · 사유', GRY_BG, MUT, DIM),
                        ('꺼짐', GRY_BG, MUT, None),
                        ('발화 후 종료', BLU_BG, PRI, None),
                        ('만료', GRY_BG, FAINT, None)]:
    pill(cx, y, 150, 20, bg, fg, lb, dot=dot)
    y += 24
text(cx, y, 250, 30, '카드 문구는 서버 status와 마지막 평가 결과\n(TRUE/FALSE/UNKNOWN)에서 정해진다', 8, DIM)
y += 40

text(cx, y, LW - 32, 16, '평가 시점 (cadence)', 10, MUT, bold=True)
y += 22
chip(cx, y, 60, '장중', on=True)
text(cx + 70, y, 190, 24, 'INTRADAY · 가격·등락률·거래량', 9, SUB)
y += 30
chip(cx, y, 60, '종가', on=True)
text(cx + 70, y, 190, 24, 'CLOSE · 카탈로그 전부', 9, SUB)
y += 34

text(cx, y, LW - 32, 16, '등락색 (상태색과 분리)', 10, MUT, bold=True)
y += 20
rect(cx, y + 3, 14, 14, UP, 'none', 1, arc=20)
text(cx + 22, y, 90, 20, '상승(빨강)', 10, SUB)
rect(cx + 130, y + 3, 14, 14, DOWN, 'none', 1, arc=20)
text(cx + 152, y, 90, 20, '하락(파랑)', 10, SUB)
y += 34

text(cx, y, LW - 32, 16, '화살표', 10, MUT, bold=True)
y += 22
rect(cx, y + 7, 44, 3, PRI)
text(cx + 54, y, 190, 18, '주 흐름 (파랑)', 10, SUB)
y += 22
rect(cx, y + 7, 44, 3, GRN)
text(cx + 54, y, 190, 18, '저장 후 이동 (초록)', 10, SUB)
y += 22
rect(cx, y + 7, 44, 3, AMB)
text(cx + 54, y, 190, 18, '앱 밖에서 들어옴 (푸시)', 10, SUB)
y += 22
text(cx, y, 240, 18, '◇ = 분기   ‹ = 뒤로', 10, SUB)
y += 20
text(cx, y, 250, 44, '※ 새 알림 흐름은 모달. 닫으면 들어온 자리\n※ 종목 상세 `알림 걸기`는 조건 선택으로 진입', 9, MUT)
y += 50

text(cx, y, LW - 32, 16, '전달', 10, MUT, bold=True)
y += 20
text(cx, y, 250, 44, '울린 알림은 항상 앱 안에 기록된다\n앱 푸시는 v1에서 iOS만', 9, SUB)
y += 52

text(cx, y, LW - 32, 16, '표기 규칙', 10, MUT, bold=True)
y += 20
text(cx, y, 130, 18, 'UI 카피', 10, SUB)
text(cx + 120, y, 140, 18, '한국어', 10, MUT)
y += 20
text(cx, y, 130, 18, '개발 enum·필드', 10, SUB)
text(cx + 120, y, 140, 18, 'EDGE_REARM', 9, FAINT, mono=True)
y += 26
text(cx, y, 250, 32, '그리드 8pt · 터치타깃 44pt\n타입 22/16/14/12/10/9', 9, DIM)


def sect(x, y, s, right=None):
    text(x, y, 200, 22, s, 10, MUT, bold=True)
    if right:
        text(x + 176, y, 100, 22, right, 10, PRI, align='right', bold=True)


def field(x, y, label, value, w=276, arrow=True):
    text(x, y, w, 16, label, 9, MUT)
    rect(x, y + 18, w, 32, '#FFFFFF', LINE, 1, arc=12)
    text(x + 12, y + 18, w - 40, 32, value, 11, TXT)
    if arrow:
        text(x + w - 28, y + 18, 20, 32, '▼', 10, MUT, align='center')


def stepper(x, y, label, value, w=276):
    text(x, y, w, 16, label, 9, MUT)
    rect(x, y + 18, w, 32, '#FFFFFF', LINE, 1, arc=12)
    text(x, y + 18, 36, 32, '－', 14, MUT, align='center')
    text(x + 36, y + 18, w - 72, 32, value, 12, TXT, align='center', bold=True)
    text(x + w - 36, y + 18, 36, 32, '+', 14, MUT, align='center')


def radio(x, y, s, on, sub=None):
    rect(x, y + 4, 14, 14, '#FFFFFF', PRI if on else LINE, 1.5, ellipse=True)
    if on:
        rect(x + 4, y + 8, 6, 6, PRI, 'none', 1, ellipse=True)
    text(x + 22, y, 150, 22, s, 11, TXT if sub != 'off' else DIM)
    if sub and sub != 'off':
        text(x + 150, y, 126, 22, sub, 8, FAINT, mono=True, align='right')


def alert_card(x, y, name, cond, pl, meta, right='toggle'):
    card(x, y, 276, 62)
    text(x + 12, y + 6, 150, 20, name, 12, TXT, bold=True)
    pill(x + 276 - 12 - pl[0], y + 8, pl[0], 18, pl[1], pl[2], pl[3], dot=pl[4], size=8)
    text(x + 12, y + 26, 200, 16, cond, 10, SUB)
    text(x + 12, y + 42, 200, 14, meta, 8, FAINT)
    if right == 'toggle':
        toggle(x + 230, y + 36, True)
    elif right:
        text(x + 196, y + 36, 70, 20, right, 9, PRI, align='right', bold=True)


# ══════════════════════════════════════════════════════════════
# 밴드 1 — 알림 탭 · 울린 알림 · 알림 상세
# ══════════════════════════════════════════════════════════════
B1 = 190

# A1 알림 (탭 루트)
x, y = ph(360, B1, '알림', back=False, right='＋ 새 알림', tab='알림')
asof(360, y, PW, '최근 평가 2026-09-26 10:15', right=None)
y += 34
sect(x, y, '새로 울린 알림 2', '전체 →')
y += 26
for t, s in [('삼성전자 · 가격 도달', '10:15 · 현재가 70,200원'),
             ('카카오 · RSI 과매수', '9/26 종가 · RSI(14) 71.3')]:
    card(x, y, 276, 40, '#FFFFFF', INF_ST)
    rect(x + 10, y + 17, 6, 6, UP, 'none', 1, ellipse=True)
    text(x + 22, y + 3, 200, 18, t, 11, TXT, bold=True)
    text(x + 22, y + 20, 200, 16, s, 9, MUT)
    text(x + 244, y, 24, 40, '›', 14, DIM, align='center')
    y += 46
y += 6
sect(x, y, '내 알림')
y += 26
alert_card(x, y, '삼성전자', '장중 · 현재가 ≥ 70,000원',
           (64, GRN_BG, GRN, '감시 중', GRN), '돌파할 때마다 · 최근 발화 10:15')
y += 68
alert_card(x, y, '카카오', '종가 · RSI(14) 3거래일 연속 ≥ 70',
           (84, AMB_BG, AMB_TX, '조건 충족 중', AMB), '돌파할 때마다 · 최근 발화 9/26')
y += 68
alert_card(x, y, 'SK하이닉스', '종가 · 20일 박스권 상단 돌파',
           (104, GRY_BG, MUT, '확인 불가 · 거래 없음', DIM), '돌파할 때마다')
y += 68
alert_card(x, y, 'NAVER', '장중 · 현재가 ≤ 180,000원',
           (80, BLU_BG, PRI, '발화 후 종료', None), '한 번만 · 9/24 울림', right='다시 켜기')
y += 68
mono(x, y, 276, 'GET /alerts · data.rows + data.unread')

# A2 울린 알림 (목록)
x, y = ph(760, B1, '울린 알림', right='모두 읽음')
asof(760, y, PW, '최근 평가 2026-09-26 10:15', right=None)
y += 34
for t, s, unread, dele in [('삼성전자 · 가격 도달', '9/26 10:15 · 현재가 70,200원', True, False),
                           ('카카오 · RSI 과매수', '9/26 종가 · RSI(14) 71.3', True, False),
                           ('삼성전자 · 가격 도달', '9/25 09:42 · 현재가 70,100원', False, False),
                           ('NAVER · 가격 도달', '9/24 13:05 · 현재가 179,500원', False, False),
                           ('LG에너지솔루션 · 급등락', '9/20 종가 · 등락률 -6.1%', False, True)]:
    card(x, y, 276, 50)
    if unread:
        rect(x + 10, y + 22, 6, 6, UP, 'none', 1, ellipse=True)
    text(x + 22, y + 6, 190, 18, t, 11, TXT if not dele else MUT, bold=unread)
    text(x + 22, y + 26, 200, 16, s, 9, MUT)
    if dele:
        pill(x + 196, y + 15, 70, 18, GRY_BG, FAINT, '삭제된 알림', size=8)
    y += 56
mono(x, y + 4, 276, 'GET /alert-events · 삭제된 알림의 발화도 남는다')

# A3 울린 알림 상세
x, y = ph(1160, B1, '울린 알림')
y += 14
text(x, y, 276, 24, '삼성전자 · 가격 도달', 16, TXT, bold=True)
y += 26
text(x, y, 276, 18, '2026-09-26 10:15 기준 · 10:15:41 울림', 9, MUT)
y += 28
box(x, y, 276, 64, 'ok')
text(x + 12, y + 8, 250, 16, '울린 이유', 9, GRN, bold=True)
text(x + 12, y + 26, 250, 30, '현재가 70,200원 ≥ 70,000원', 14, TXT, bold=True)
y += 76
for k, v in [('평가 시점', '장중'), ('발화 방식', '돌파할 때마다'), ('알림', '삼성전자 7만원')]:
    text(x, y, 120, 26, k, 10, MUT)
    text(x + 120, y, 156, 26, v, 11, TXT, align='right')
    hr(x, y + 26, 276)
    y += 30
y += 14
rect(x, y, 276, 40, '#FFFFFF', PRI, 1, arc=12)
text(x, y, 276, 40, '알림 보기 →', 12, PRI, align='center', bold=True)
y += 48
rect(x, y, 276, 40, PANEL, 'none', 1, arc=12)
text(x, y, 276, 40, '이 알림 끄기', 12, SUB, align='center', bold=True)
y += 54
mono(x, y, 276, 'alert_event: title · body · observed · as_of\n여는 순간 읽음 처리', h=36)

# 푸시 (앱 밖)
PX, PY = 1200, 70
rect(PX, PY, 260, 72, '#FFFFFF', AMB_ST, 1, arc=12, shadow=True)
text(PX + 12, PY + 6, 200, 16, '주식앱 · 지금', 8, MUT)
text(PX + 12, PY + 22, 236, 18, '삼성전자 · 가격 도달', 11, TXT, bold=True)
text(PX + 12, PY + 42, 236, 18, '현재가 70,200원 ≥ 70,000원 · 10:15 기준', 9, SUB)
text(PX + 270, PY + 10, 180, 50, 'iOS 앱 푸시\n…://alert-events/{event_id}', 9, AMB_TX)

# A4 알림 상세
x, y = ph(1660, B1, '알림 상세', right='수정')
y += 14
text(x, y, 200, 24, '삼성전자 7만원', 16, TXT, bold=True)
pill(x + 206, y + 3, 70, 20, GRN_BG, GRN, '감시 중', dot=GRN)
y += 32
box(x, y, 276, 48, 'info')
text(x + 12, y, 252, 48, '장중 · 현재가가 70,000원 이상이 되면\n알려요', 11, TXT)
y += 58
for k, v in [('마지막 평가', '10:20 · 조건 미충족'), ('발화 방식', '돌파할 때마다'),
             ('유효기간', '무기한')]:
    text(x, y, 120, 26, k, 10, MUT)
    text(x + 120, y, 156, 26, v, 11, TXT, align='right')
    hr(x, y + 26, 276)
    y += 30
y += 10
sect(x, y, '최근 울린 알림')
y += 26
for t in ['9/26 10:15 · 현재가 70,200원', '9/25 09:42 · 현재가 70,100원']:
    text(x, y, 250, 24, t, 10, SUB)
    text(x + 252, y, 24, 24, '›', 13, DIM, align='center')
    hr(x, y + 26, 276)
    y += 30
y += 16
text(x, y, 200, 24, '감시', 12, TXT, bold=True)
toggle(x + 242, y + 2, True)
y += 40
text(x, y, 276, 24, '알림 삭제', 11, '#C0392B', align='center', bold=True)
y += 34
mono(x, y, 276, 'GET /alerts/{id} · pause · resume · DELETE')

# ══════════════════════════════════════════════════════════════
# 밴드 2 — 새 알림 흐름
# ══════════════════════════════════════════════════════════════
B2 = 900

# N1 대상 종목
x, y = ph(360, B2, '대상 종목')
rect(x, y + 10, 276, 34, PANEL2, 'none', 1, arc=12)
text(x + 12, y + 10, 250, 34, '삼성', 11, TXT)
y += 56
sect(x, y, '검색 결과')
y += 26
for nm, cd, held in [('삼성전자', '005930', True), ('삼성SDI', '006400', False),
                     ('삼성바이오로직스', '207940', False), ('삼성전기', '009150', False)]:
    card(x, y, 276, 40)
    text(x + 12, y, 150, 40, nm, 11, TXT, bold=True)
    text(x + 150, y, 60, 40, cd, 9, FAINT, mono=True)
    pill(x + 210, y + 11, 26, 18, BLU_BG, PRI, 'KR', size=8)
    if held:
        pill(x + 240, y + 11, 30, 18, GRN_BG, GRN, '보유', size=8)
    y += 46
y += 8
text(x, y, 276, 34, '검색어가 없으면 `보유 종목` 구역을 먼저 보여준다', 9, MUT)
y += 40
mono(x, y, 276, 'GET /instruments?q=&held=\n→ alert.instrument_id', h=36)

# N2 조건 선택
x, y = ph(760, B2, '조건 선택')
y += 10
rect(x, y, 276, 38, AMB_BOX, AMB, 1.2, arc=10, dashed=True)
text(x + 12, y, 200, 38, '＋ 직접 조건 만들기', 12, AMB_TX, bold=True)
text(x + 190, y, 76, 38, 'COMPOSABLE', 7, AMB_ST, mono=True, align='right')
y += 50
sect(x, y, '프리셋')
y += 24
for nm, cad, dis in [('가격 도달', '장중·종가', False), ('급등락', '장중·종가', False),
                     ('거래량 급증', '장중·종가', False), ('골든·데드크로스', '종가', False),
                     ('RSI 과매수·과매도', '종가', False), ('박스권 돌파', '종가', False),
                     ('외국인·기관 연속 순매수', '종가', False),
                     ('외국인·기관 순매수 전환', '종가', False),
                     ('수익률 도달 · 보유 종목', '종가', False)]:
    rect(x, y, 276, 32, INF_BOX, INF_ST, 1, arc=8)
    text(x + 12, y, 190, 32, nm, 11, TXT, bold=True)
    pill(x + 200, y + 7, 66, 18, '#FFFFFF', PRI, cad, size=8)
    y += 36
mono(x, y + 2, 276, 'GET /alerts/catalog · 시장이 지원하지 않는 프리셋은 비활성', h=30)

diamond(1105, B2 + 250, 110, 70, 'trigger\ntype ?')

# N3 박스권 돌파 (프리셋 입력)
x, y = ph(1260, B2, '박스권 돌파', right='다음')
rect(x, y + 10, 276, 26, INF_BOX, 'none', 1, arc=6)
text(x + 10, y + 10, 266, 26, '프리셋 · 종가', 10, PRI, bold=True)
y += 48
stepper(x, y, '관찰 기간 (window_days)', '20 일')
y += 60
stepper(x, y, '최대 폭 (max_range_pct)', '15 %')
y += 62
text(x, y, 276, 16, '방향 (direction)', 9, MUT)
y += 20
radio(x, y, '상단 돌파', True)
radio(x + 140, y, '하단 이탈', False)
y += 34
text(x, y, 276, 16, '평가 시점', 9, MUT)
y += 20
chip(x, y, 70, '종가', on=True)
rect(x + 80, y, 70, 24, PANEL, 'none', 1, arc=50)
text(x + 80, y, 70, 24, '장중', 10, DIM, align='center')
y += 36
box(x, y, 276, 58, 'ok')
text(x + 12, y + 6, 256, 48, '지금 · 9/26 종가 기준\n직전 20일 폭 11.2% · 최고가 71,800원\n종가 71,200원 · 돌파까지 +600원', 9, GRN)
y += 68
mono(x, y, 276, 'preset_key + params 저장 · 평가 시점 컴파일\nPOST /alerts/preview → current', h=36)

# N4 공통 설정
x, y = ph(1660, B2, '공통 설정')
y += 12
text(x, y, 276, 16, '발화 방식', 9, MUT)
y += 20
radio(x, y, '돌파할 때마다', True, 'EDGE_REARM')
y += 26
radio(x, y, '한 번만', False, 'ONE_SHOT')
y += 26
radio(x, y, 'N분마다 다시 · 장중만', False, 'off')
y += 36
field(x, y, '유효기간', '무기한')
y += 62
field(x, y, '알림 이름', '삼성전자 박스권', arrow=False)
y += 66
box(x, y, 276, 50, 'warn')
text(x + 12, y, 256, 50, '이미 조건을 충족 중이면 여기서 알려요\n같은 조건의 알림이 있어도 알려요', 9, AMB_TX)
y += 62
rect(x, y, 276, 44, PRI, 'none', 1, arc=12)
text(x, y, 276, 44, '저장', 13, '#FFFFFF', align='center', bold=True)
y += 56
mono(x, y, 276, 'POST /alerts · 첫 저장 시 푸시 권한 요청(iOS)', h=30)

# ══════════════════════════════════════════════════════════════
# 밴드 3 — 조건 만들기 · 개념도
# ══════════════════════════════════════════════════════════════
B3 = 1610

# N5 직접 조건 만들기
x, y = ph(1260, B3, '직접 조건 만들기', right='다음')
y += 10
text(x, y, 276, 16, '평가 시점 (cadence · 이 알림 전체)', 9, MUT)
y += 20
rect(x, y, 276, 30, PANEL2, 'none', 1, arc=10)
text(x, y, 138, 30, '장중', 11, DIM, align='center')
rect(x + 140, y + 2, 134, 26, '#FFFFFF', BORDER, 1, arc=10)
text(x + 138, y, 138, 30, '종가', 11, PRI, align='center', bold=True)
y += 42
rect(x, y, 276, 206, '#FFFFFF', AMB_ST, 1, arc=10, dashed=True)
text(x + 12, y + 6, 100, 18, '조건 1', 10, AMB_TX, bold=True)
cx2 = x + 12
field(cx2, y + 26, '지표', 'RSI (14)', w=120)
field(cx2 + 132, y + 26, '변형', '현재값', w=120)
field(cx2, y + 82, '연산자', '≥', w=70)
text(cx2 + 82, y + 82, 90, 16, '기준값', 9, MUT)
rect(cx2 + 82, y + 100, 90, 32, AMB_BOX, AMB_ST, 1, arc=10)
text(cx2 + 82, y + 100, 90, 32, '70', 13, TXT, align='center', bold=True)
rect(cx2 + 180, y + 100, 72, 32, PANEL, 'none', 1, arc=10)
text(cx2 + 180, y + 100, 72, 32, '상수 ▼', 10, SUB, align='center')
text(cx2, y + 140, 200, 16, '유지 방식 (modifier)', 9, MUT)
rect(cx2, y + 158, 90, 30, BLU_BG, 'none', 1, arc=8)
text(cx2, y + 158, 90, 30, '연속 ▼', 10, PRI, align='center', bold=True)
rect(cx2 + 98, y + 158, 90, 30, '#FFFFFF', LINE, 1, arc=8)
text(cx2 + 98, y + 158, 90, 30, '－   3   ＋', 11, TXT, align='center')
text(cx2 + 194, y + 158, 60, 30, '거래일', 9, AMB_TX)
y += 216
rect(x, y, 276, 32, INF_BOX, INF_ST, 1, arc=10)
text(x, y, 276, 32, '＋ 조건 추가 (AND)', 11, PRI, align='center', bold=True)
y += 42
box(x, y, 276, 40, 'gray')
text(x + 10, y, 260, 40, '“종가 기준, RSI(14)가 3거래일 연속\n70 이상이면 알림”', 10, TXT, bold=True)
y += 48
box(x, y, 276, 30, 'ok')
text(x + 10, y, 260, 30, '지금 · RSI 68.4 (9/26 종가) · 조건까지 +1.6', 9, GRN)
y += 38
mono(x, y, 276, 'cadence + conditions[] (AND) → trigger_spec JSONB')

# 개념도 — 두 입력 → 하나의 저장 구조 → 평가 → 전달
CX, CY = 360, B3
text(CX, CY, 800, 26, '두 입력 → 하나의 저장 구조 → 평가 → 전달', 14, TXT, bold=True)


def cbox(x, y, w, h, title, sub, kind):
    fills = {'amb': (AMB_BOX, AMB_ST, AMB_TX), 'inf': (INF_BOX, INF_ST, PRI),
             'core': ('#FFFFFF', TXT, TXT), 'gray': (PANEL, BORDER, SUB), 'ok': (GRN_BOX, GRN_ST, GRN)}
    f, s, t = fills[kind]
    rect(x, y, w, h, f, s, 2 if kind == 'core' else 1, arc=8)
    text(x, y + 8, w, 20, title, 11, t, align='center', bold=True)
    text(x + 8, y + 30, w - 16, h - 36, sub, 8, MUT, align='center', valign='top', mono=True)


cbox(CX, CY + 50, 220, 60, '프리셋 입력', 'preset_key + params', 'amb')
cbox(CX, CY + 130, 220, 60, '조립형 입력', 'cadence · conditions[]', 'inf')
cbox(CX + 300, CY + 80, 300, 80, '검증 → 저장 (alert)', 'trigger_type + trigger_spec\nJSONB (spec_version)', 'core')
edge([(CX + 220, CY + 80), (CX + 260, CY + 80), (CX + 260, CY + 120), (CX + 300, CY + 120)],
     '검증 후', lseg=1, loff=(0, 0))
edge([(CX + 220, CY + 160), (CX + 260, CY + 160), (CX + 260, CY + 120), (CX + 300, CY + 120)])

cbox(CX, CY + 240, 220, 70, '완료 신호', 'market_data_run\n(시장 · 종류 · 시점) DONE', 'gray')
cbox(CX + 300, CY + 230, 300, 90, '평가기 (백엔드 앱 안)', '템플릿 컴파일 · 이력 재계산\nTRUE / FALSE / UNKNOWN\n조건부 갱신으로 한 번만', 'core')
edge([(CX + 220, CY + 275), (CX + 300, CY + 275)], '1분마다')
edge([(CX + 450, CY + 160), (CX + 450, CY + 230)], '평가 시', loff=(34, 0))

cbox(CX + 300, CY + 380, 300, 70, 'alert_state + alert_event', '한 트랜잭션 · (alert_id, as_of) 유일', 'ok')
edge([(CX + 450, CY + 320), (CX + 450, CY + 380)], '참이 되면', loff=(40, 0))

cbox(CX, CY + 490, 220, 60, '발송기 → Expo Push', 'SKIP LOCKED · 재시도 · iOS', 'inf')
cbox(CX + 380, CY + 490, 220, 60, '앱 · 울린 알림', '목록 · 배지 · 전 기기', 'inf')
edge([(CX + 400, CY + 450), (CX + 400, CY + 470), (CX + 110, CY + 470), (CX + 110, CY + 490)],
     '대기 행', lseg=1)
edge([(CX + 490, CY + 450), (CX + 490, CY + 490)], '조회', loff=(26, 0))

text(CX, CY + 570, 760, 20,
     '└ 필드 매핑 · JSON 예시 · 검증 규칙 · 상태 전수 = 스펙 문서(.md)에서 확정', 9, GRN)

# ══════════════════════════════════════════════════════════════
# 흐름선
# ══════════════════════════════════════════════════════════════
# 밴드 1
edge([(660, B1 + 140), (760, B1 + 140)], '전체 →', loff=(0, -12))
edge([(1060, B1 + 130), (1160, B1 + 130)], '행 탭', loff=(0, -12))
edge([(500, B1), (500, B1 - 30), (1230, B1 - 30), (1230, B1)], '새로 울린 알림 행', lseg=1)
edge([(1330, PY + 72), (1330, B1)], '푸시 탭', color=AMB, loff=(34, 0))
edge([(1460, B1 + 380), (1660, B1 + 380)], '알림 보기', loff=(0, -12))
edge([(560, B1 + 600), (560, B1 + 640), (1760, B1 + 640), (1760, B1 + 600)], '내 알림 행', lseg=1)
edge([(420, B1 + 600), (420, B2)], '＋ 새 알림', loff=(44, 0))

# 밴드 2
edge([(660, B2 + 300), (760, B2 + 300)], '종목 확정', loff=(0, -12))
edge([(1060, B2 + 285), (1105, B2 + 285)])
edge([(1215, B2 + 285), (1260, B2 + 285)], 'PRESET', loff=(0, -14))
edge([(1160, B2 + 320), (1160, B3 + 300), (1260, B3 + 300)], '= COMPOSABLE', lseg=0, loff=(50, 0))
edge([(1560, B2 + 300), (1660, B2 + 300)], '파라미터', loff=(0, -12))
edge([(1560, B3 + 300), (1610, B3 + 300), (1610, B2 + 450), (1660, B2 + 450)], '조건 구성 후',
     lseg=1, loff=(0, 0))
edge([(1900, B2), (1900, B1 + 600)], '저장 → 알림 상세', color=GRN, loff=(-60, 0))

# ══════════════════════════════════════════════════════════════
import os
OUT = os.path.dirname(os.path.abspath(__file__))
open(os.path.join(OUT, 'wireflow.drawio'), 'w').write(
    to_drawio(PGW, PGH, '매수·매도 타이밍 알림 와이어플로우 v1'))
w, h = to_png(PGW, PGH, os.path.join(OUT, 'wireflow.png'), S=1.5)
print('shapes=%d  png=%dx%d' % (len(SHAPES), w, h))
