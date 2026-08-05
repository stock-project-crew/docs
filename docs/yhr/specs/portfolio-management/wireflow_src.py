# -*- coding: utf-8 -*-
"""포트폴리오 종합 관리 — 와이어플로우 생성기 (단일 소스 → drawio + png)

실행:  pip install pillow && python3 wireflow_src.py
출력:  wireflow.drawio · wireflow.png (이 파일과 같은 디렉터리)
drawio 파일을 app.diagrams.net에서 직접 편집한 경우, 이 스크립트도 함께 수정해야
두 산출물이 어긋나지 않는다.
"""

from PIL import Image, ImageDraw, ImageFont

# ── 팔레트 (알림 와이어플로우 승계) ──────────────────────────────
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
PGW, PGH = 2760, 2680


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
    for i, lb in enumerate(['요약', '종목', '비중', '계좌', '손익']):
        on = (lb == active)
        text(x + i * 60, ty + 1, 60, 44, lb, 10, PRI if on else DIM,
             align='center', bold=on)
        if on:
            rect(x + i * 60 + 26, ty + 36, 8, 3, PRI, arc=50)


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
LX, LY, LW = 40, 150, 290
rect(LX, LY, LW, 900, '#FBFCFE', '#C7CFDD', 1, arc=6, shadow=True)
cx, cy = LX + 16, LY + 16
text(cx, cy, LW - 32, 26, '포트폴리오 종합 관리', 16, TXT, bold=True)
hr(cx, cy + 34, LW - 32, '#E2E7EF')
text(cx, cy + 46, LW - 32, 18, '범례 (Legend)', 12, TXT, bold=True)

y = cy + 72
text(cx, y, LW - 32, 16, '연동 상태색', 10, MUT, bold=True)
y += 20
for lb, bg, fg, dot in [('연동됨 CONNECTED', GRN_BG, GRN, GRN),
                        ('동기화 중 SYNCING', BLU_BG, PRI, PRI),
                        ('재인증 필요 REAUTH', AMB_BG, AMB_TX, AMB),
                        ('실패·이월 STALE', GRY_BG, MUT, DIM)]:
    pill(cx, y, 152, 20, bg, fg, lb, dot=dot)
    y += 24

y += 8
text(cx, y, LW - 32, 16, '신뢰도 등급 (거래 원장)', 10, MUT, bold=True)
y += 20
for lb, bg, fg in [('VERIFIED — 배지 없음', '#FFFFFF', SUB),
                   ('SEEDED — 추정', AMB_BG, AMB_TX),
                   ('UNAVAILABLE — 거래내역 없음', GRY_BG, MUT),
                   ('CONFLICT — 수량 모순', '#FBE9E7', '#C0392B')]:
    rect(cx, y, 200, 20, bg, BORDER if bg == '#FFFFFF' else 'none', 1, arc=50)
    text(cx + 10, y, 190, 20, lb, 9, fg, bold=True)
    y += 24

y += 8
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
text(cx + 54, y, 190, 18, '동기화 완료 복귀 (초록)', 10, SUB)
y += 22
text(cx, y, 240, 18, '◇ = 분기   ‹ = 뒤로', 10, SUB)
y += 20
text(cx, y, 250, 30, '※ 탭바 이동은 인접 화면 간 화살표로 축약', 9, MUT)

y += 40
text(cx, y, LW - 32, 16, '렌즈 (ETF 분해)', 10, MUT, bold=True)
y += 20
text(cx, y, 250, 46, 'lens_policy=OPTIONAL 인 뷰에만 노출\n비중 분석 · 종목별 · 요약 미니차트', 9, SUB)

y += 56
text(cx, y, LW - 32, 16, '표기 규칙', 10, MUT, bold=True)
y += 20
text(cx, y, 130, 18, 'UI 카피', 10, SUB)
text(cx + 120, y, 140, 18, '한국어', 10, MUT)
y += 20
text(cx, y, 130, 18, '개발 enum·필드', 10, SUB)
text(cx + 120, y, 140, 18, 'LOOK_THROUGH', 9, FAINT, mono=True)
y += 26
text(cx, y, 250, 32, '그리드 8pt · 터치타깃 44pt\n타입 22/16/14/12/10/9', 9, DIM)

# ══════════════════════════════════════════════════════════════
# 밴드 1 — 계좌 연동 → 동기화
# ══════════════════════════════════════════════════════════════
B1 = 150

# P1 계좌 연동
x, y = ph(360, B1, '계좌 연동', back=True)
text(x, y + 3, 276, 24, '연동된 계좌가 없어요', 15, TXT, bold=True)
text(x, y + 29, 276, 32, '증권사를 연결하면 잔고·거래내역을 자동으로 불러와요', 11, MUT)
text(x, y + 71, 276, 16, '직접 연동', 10, MUT, bold=True)
card(x, y + 91, 276, 56)
text(x + 12, y + 99, 170, 20, '한국투자증권', 13, TXT, bold=True)
pill(x + 196, y + 101, 44, 18, GRN_BG, GRN, '무료')
text(x + 12, y + 120, 200, 18, '본인 앱키로 연결 · 빠르고 안정적', 10, MUT)
text(x + 246, y + 91, 20, 56, '›', 14, DIM, align='center')
text(x, y + 157, 276, 16, '기관 연동 (CODEF)', 10, MUT, bold=True)
for i, nm in enumerate(['삼성증권', '미래에셋증권', '키움증권']):
    yy = y + 177 + i * 52
    card(x, yy, 276, 44)
    text(x + 12, yy, 200, 44, nm, 13, TXT)
    text(x + 246, yy, 20, 44, '›', 14, DIM, align='center')
text(x, y + 337, 276, 20, '＋ 기관 더 보기', 11, PRI, bold=True)
box(x, y + 365, 276, 60, 'warn')
text(x + 12, y + 375, 252, 42, '일부 퇴직연금(DC) 계좌는 기관이 조회를 제공하지 않아 연동할 수 없어요', 10, AMB_TX)
mono(x, y + 437, 276, 'account.source = KIS | CODEF\n1차 범위: 자동 연동만 (수동 입력 없음)')

# P2 인증 정보 입력
x, y = ph(760, B1, '삼성증권 연동', back=True, right='다음')
text(x, y + 4, 276, 16, '인증 수단', 10, MUT, bold=True)
rect(x, y + 24, 12, 12, '#FFFFFF', PRI, 2, ellipse=True)
rect(x + 3, y + 27, 6, 6, PRI, 'none', 1, ellipse=True)
text(x + 20, y + 20, 100, 20, '공동인증서', 12, TXT, bold=True)
rect(x + 140, y + 24, 12, 12, '#FFFFFF', LINE, 1, ellipse=True)
text(x + 160, y + 20, 110, 20, 'ID · 비밀번호', 12, SUB)
text(x, y + 56, 276, 16, '인증서 비밀번호', 10, MUT, bold=True)
rect(x, y + 76, 276, 36, '#FFFFFF', LINE, 1, arc=8)
text(x + 12, y + 76, 252, 36, '●●●●●●●●', 12, TXT)
text(x, y + 124, 276, 16, '증권사 ID', 10, MUT, bold=True)
rect(x, y + 144, 276, 36, '#FFFFFF', LINE, 1, arc=8)
text(x + 12, y + 144, 252, 36, 'samsung_user', 12, SUB)
box(x, y + 194, 276, 92, 'ok')
text(x + 12, y + 204, 252, 20, '인증정보는 저장하지 않아요', 11, GRN, bold=True)
text(x + 12, y + 224, 252, 54,
     'CODEF 공개키로 암호화해 전송하고, 서비스는 Connected ID만 보관해요. '
     '인증서·비밀번호는 서버에 남지 않아요.', 10, SUB)
mono(x, y + 298, 276, 'RSA(publicKey) → POST /accounts/connect\nconnected_accounts ← connected_id only')
rect(x, y + 455, 276, 44, PRI, 'none', 1, arc=8)
text(x, y + 455, 276, 44, '연동하기', 13, '#FFFFFF', align='center', bold=True)

# 분기
diamond(1100, 395, 100, 76, '추가 인증\n요구 ?')

# P3 추가 인증
x, y = ph(1240, B1, '추가 인증', back=True)
text(x, y + 4, 276, 24, '휴대폰 인증이 필요해요', 15, TXT, bold=True)
text(x, y + 30, 276, 18, '삼성증권이 2단계 인증을 요구했어요', 11, MUT)
rect(x, y + 62, 276, 42, '#FFFFFF', LINE, 1, arc=8)
text(x + 12, y + 62, 180, 42, '인증번호 6자리', 12, DIM)
text(x + 200, y + 62, 64, 42, '02:47', 11, UP, align='right', bold=True)
rect(x, y + 114, 276, 36, '#FFFFFF', PRI, 1, arc=8)
text(x, y + 114, 276, 36, '인증번호 재전송', 11, PRI, align='center', bold=True)
box(x, y + 162, 276, 76, 'warn')
text(x + 12, y + 172, 252, 20, '이 계좌는 재인증 대기 상태예요', 11, AMB_TX, bold=True)
text(x + 12, y + 192, 252, 38, '인증을 마치면 즉시 동기화가 시작되고, 그때까지는 마지막 데이터로 표시돼요.', 10, SUB)
mono(x, y + 250, 276, 'account.state = REAUTH_REQUIRED\n인증 완료 → sync 즉시 트리거')
rect(x, y + 455, 276, 44, PRI, 'none', 1, arc=8)
text(x, y + 455, 276, 44, '확인', 13, '#FFFFFF', align='center', bold=True)

# P4 동기화
x, y = ph(1640, B1, '동기화', back=False)
text(x, y + 4, 276, 24, '포트폴리오를 불러오는 중', 15, TXT, bold=True)
rows = [('한국투자증권 위탁', '완료 15:30', GRN_BG, GRN, GRN, '✓'),
        ('한국투자증권 IRP', '완료 15:30', GRN_BG, GRN, GRN, '✓'),
        ('삼성증권', '진행 중', BLU_BG, PRI, PRI, '●'),
        ('미래에셋증권', '실패 · 재시도 2/3', GRY_BG, MUT, DIM, '×')]
for i, (nm, st, bg, fg, dot, mk) in enumerate(rows):
    yy = y + 36 + i * 52
    card(x, yy, 276, 44)
    text(x + 12, yy, 20, 44, mk, 12, fg, bold=True)
    text(x + 36, yy + 5, 150, 18, nm, 12, TXT if i < 3 else MUT, bold=True)
    text(x + 36, yy + 22, 150, 16, st, 9, MUT)
    if i == 3:
        pill(x + 176, yy + 12, 88, 20, GRY_BG, MUT, '07-26 이월')
    else:
        pill(x + 196, yy + 12, 68, 20, bg, fg, st.split(' ')[0], size=9)
box(x, y + 250, 276, 66, 'warn')
text(x + 12, y + 259, 252, 20, '실패한 계좌도 총자산에 포함해요', 11, AMB_TX, bold=True)
text(x + 12, y + 279, 252, 32, '마지막 성공 데이터로 이월해서 보여주고, 낡았다는 사실을 표시해요.', 10, SUB)
mono(x, y + 328, 276, '202 Accepted · 계좌별 독립 재시도\ncarry-forward → source_as_of · is_carried_forward')
text(x, y + 380, 276, 16, '진행률 3 / 4', 10, MUT, bold=True)
bar(x, y + 400, 276, 8, PRI, 0.75)

# 노트 1
NX, NY, NW = 2040, 150, 460
rect(NX, NY, NW, 600, '#FFFFFF', BORDER, 1, arc=8, shadow=True)
text(NX + 20, NY + 18, NW - 40, 24, '연동 · 동기화 원칙', 14, TXT, bold=True)
hr(NX + 20, NY + 50, NW - 40)
notes = [('인증정보 비저장', 'CODEF는 Connected ID만 보관하고 인증서·비밀번호는 서버에 남기지 않는다. '
                       'KIS는 본인 앱키를 암호화 저장한다.'),
         ('항상 비동기', '동기화는 무겁고 느리다. 202로 즉시 응답하고 완료는 푸시·폴링으로 알린다.'),
         ('부분 실패 허용', '계좌별로 독립 재시도한다. CODEF는 지수 백오프, KIS는 레이트리밋 스로틀 중심.'),
         ('캐리포워드', '실패해도 그날 position_line을 반드시 만든다. 빠뜨리면 그레인 유일성이 깨지고 '
                    '자산 변화 뷰의 항등식이 성립하지 않는다.'),
         ('as-of 두 층', '화면 as-of는 배치 실행 기준시각으로 단일. 계좌별 실제 시각은 source_as_of로 따로 추적.'),
         ('총자산에서 빼지 않는다', '실패 계좌를 제외하면 자산이 급감해 더 큰 오해를 낳는다. '
                            '포함하되 낡았다고 말한다. 연동 해제만 제외하되 자산 변화 뷰에 별도 항목으로 뽑는다.')]
yy = NY + 64
for t, b in notes:
    rect(NX + 20, yy + 7, 4, 14, PRI, 'none', 1, arc=50)
    text(NX + 32, yy, NW - 52, 20, t, 11, TXT, bold=True)
    text(NX + 32, yy + 20, NW - 60, 54, b, 10, MUT, valign='top')
    yy += 22 + (36 if len(b) < 56 else 54)

# ══════════════════════════════════════════════════════════════
# 밴드 2 — 요약 허브 → 스냅샷 뷰
# ══════════════════════════════════════════════════════════════
B2 = 830

# P5 요약
x, y = ph(360, B2, '포트폴리오', back=False, tab='요약')
asof(x - 12, y, PW, '기준 2026-07-27 15:30')
rect(x - 12, y + 26, PW, 24, AMB_BOX)
text(x, y + 26, 276, 24, '◆ 1개 계좌가 07-26 기준입니다', 9, AMB_TX, bold=True)
text(x, y + 60, 276, 16, '총자산', 10, MUT, bold=True)
text(x, y + 78, 276, 32, '58,000,000원', 22, TXT, bold=True)
text(x, y + 112, 276, 18, '▲ 1,240,000 (+2.1%)', 11, UP, bold=True)
text(x + 152, y + 112, 124, 18, '전일 종가 대비', 9, DIM, align='right')
kv = [('총매입', '52,900,000'), ('총평가손익', '+5,100,000'),
      ('현금비중', '6.4%'), ('계좌 · 종목', '4계좌 · 18종목')]
for i, (k, v) in enumerate(kv):
    bx = x + (i % 2) * 142
    by = y + 138 + (i // 2) * 62
    card(bx, by, 134, 54, PANEL, 'none')
    text(bx + 10, by + 8, 114, 16, k, 9, MUT, bold=True)
    text(bx + 10, by + 26, 114, 20, v, 12, UP if v.startswith('+') else TXT, bold=True)
box(x, y + 268, 276, 38, 'info')
text(x + 12, y + 268, 170, 38, '이번 달 자산 +800만원', 11, TXT, bold=True)
text(x + 186, y + 268, 78, 38, '왜? →', 11, PRI, align='right', bold=True)
text(x, y + 318, 276, 16, '자산 구성', 10, MUT, bold=True)
seg = [(0.44, '#4C6EF5'), (0.49, '#7FB3F0'), (0.07, '#C8D3E4')]
sx = x
for p, c in seg:
    rect(sx, y + 338, int(276 * p) - 2, 16, c, 'none', 1, arc=20)
    sx += int(276 * p)
for i, (lb, v, c) in enumerate([('국내주식', '44%', '#4C6EF5'),
                                ('미국주식', '49%', '#7FB3F0'),
                                ('현금', '7%', '#C8D3E4')]):
    yy = y + 362 + i * 20
    rect(x, yy + 5, 8, 8, c, 'none', 1, arc=50)
    text(x + 16, yy, 120, 18, lb, 10, SUB)
    text(x + 200, yy, 64, 18, v, 10, TXT, align='right', bold=True)
text(x, y + 422, 276, 14, '※ 이 미니차트에만 ETF 분해 렌즈가 적용된다', 8, DIM)
mono(x, y + 440, 276, 'group_by = none · 예수금은 asset_class=CASH 종목')

# P6 종목별
x, y = ph(760, B2, '종목별', back=False, tab='종목')
asof(x - 12, y, PW, '기준 2026-07-27 15:30')
for i, (s, w, on) in enumerate([('전체 계좌 ▽', 82, False), ('전체 시장 ▽', 82, False),
                                ('평가금액순 ▽', 88, True)]):
    chip(x + i * 90, y + 36, w, s, on)
card(x, y + 70, 276, 40)
text(x + 12, y + 70, 180, 40, '구성종목 기준으로 보기', 11, SUB)
toggle(x + 230, y + 80, False)
hdr = y + 120
text(x, hdr, 130, 18, '종목', 9, DIM, bold=True)
text(x + 130, hdr, 80, 18, '평가금액', 9, DIM, align='right', bold=True)
text(x + 214, hdr, 62, 18, '손익', 9, DIM, align='right', bold=True)
rows = [('삼성전자', '10주 · 평단 65,600', '712,000', '+8.5%', UP, None),
        ('TIGER 미국나스닥100', '5주 · 평단 98,400', '512,000', '+4.1%', UP, 'ETF'),
        ('AAPL', '3주 · 평단 $198.20', '848,000', '-2.3%', DOWN, '$612.30'),
        ('KRW 예수금', '—', '3,700,000', '—', DIM, '현금')]
for i, (nm, sub, amt, pnl, c, tag) in enumerate(rows):
    yy = y + 140 + i * 56
    hr(x, yy, 276)
    text(x, yy + 8, 132, 18, nm, 12, TXT, bold=True)
    text(x, yy + 27, 132, 16, sub, 9, MUT)
    text(x + 130, yy + 8, 80, 20, amt, 12, TXT, align='right', bold=True)
    text(x + 214, yy + 8, 62, 20, pnl, 11, c, align='right', bold=True)
    if tag and tag.startswith('$'):
        text(x + 130, yy + 28, 80, 16, tag, 9, MUT, align='right')
    elif tag:
        pill(x + 214, yy + 30, 62, 16, GRY_BG, MUT, tag, size=8)
mono(x, y + 372, 276, 'group_by=instrument · 계좌 합산\n평단 = 수량가중평균 (계좌별 분해는 상세에서)')

# P7 종목별 — 렌즈 ON
x, y = ph(1160, B2, '종목별', back=False, tab='종목')
rect(x - 12, y, PW, 38, PANEL)
text(x, y + 2, 200, 18, '기준 2026-07-27 15:30', 9, MUT)
text(x, y + 18, 200, 18, '구성비중 기준 2026-07-26', 9, AMB_TX, bold=True)
text(x + 202, y, 62, 38, '새로고침', 9, PRI, align='right', bold=True)
card(x, y + 48, 276, 40, INF_BOX, INF_ST)
text(x + 12, y + 48, 180, 40, '구성종목 기준으로 보기', 11, PRI, bold=True)
toggle(x + 230, y + 58, True)
box(x, y + 98, 276, 56, 'info')
text(x + 12, y + 106, 252, 18, '평단 · 수익률은 표시할 수 없어요', 10, PRI, bold=True)
text(x + 12, y + 124, 252, 24, 'ETF를 매입한 시점의 구성비중을 알 수 없어서예요', 9, SUB)
hdr = y + 164
text(x, hdr, 120, 18, '종목', 9, DIM, bold=True)
text(x + 118, hdr, 74, 18, '환산수량', 9, DIM, align='right', bold=True)
text(x + 196, hdr, 80, 18, '평가금액 · 비중', 9, DIM, align='right', bold=True)
rows = [('삼성전자', '10주', '712,000', '12.3%', False),
        ('AAPL', '3.37주', '953,000', '16.4%', False),
        ('MSFT', '0.82주', '428,000', '7.4%', False),
        ('NVDA', '0.61주', '391,000', '6.7%', False),
        ('기타 (현금·파생·미매칭)', '—', '182,000', '3.1%', True)]
for i, (nm, q, amt, wt, other) in enumerate(rows):
    yy = y + 184 + i * 44
    hr(x, yy, 276)
    text(x, yy + 6, 120, 18, nm, 11, MUT if other else TXT, bold=not other)
    text(x, yy + 24, 120, 14, '환산' if q != '—' and i > 0 else '', 8, DIM)
    text(x + 118, yy + 6, 74, 18, q, 11, MUT if other else SUB, align='right')
    text(x + 196, yy + 4, 80, 18, amt, 11, MUT if other else TXT, align='right', bold=True)
    text(x + 196, yy + 22, 80, 16, wt, 10, MUT, align='right')
mono(x, y + 410, 276, 'LOOK_THROUGH · 재귀 분해 · Σ 평가금액 보존\n평단 / 손익률 필드는 결과에 존재하지 않음')

# P8 비중 분석 — DIRECT
x, y = ph(1560, B2, '비중 분석', back=False, tab='비중')
asof(x - 12, y, PW, '기준 2026-07-27 15:30')
rect(x, y + 34, 276, 28, PANEL, 'none', 1, arc=8)
for i, (lb, on) in enumerate([('종목', False), ('섹터', True), ('시장', False),
                              ('통화', False), ('자산군', False)]):
    if on:
        rect(x + 2 + i * 54.4, y + 36, 52, 24, '#FFFFFF', BORDER, 1, arc=8)
    text(x + 2 + i * 54.4, y + 36, 52, 24, lb, 10, TXT if on else MUT,
         align='center', bold=on)
card(x, y + 72, 276, 38)
text(x + 12, y + 72, 180, 38, '구성종목 분해', 11, SUB)
toggle(x + 230, y + 81, False)
ring(x + 52, y + 162, 42, '섹터')
for i, (lb, v, c) in enumerate([('ETF', '42.1%', '#4C6EF5'),
                                ('반도체', '18.3%', '#7FB3F0'),
                                ('IT서비스', '11.2%', '#A8C6F0')]):
    yy = y + 132 + i * 22
    rect(x + 110, yy + 5, 8, 8, c, 'none', 1, arc=50)
    text(x + 124, yy, 90, 18, lb, 10, SUB)
    text(x + 210, yy, 56, 18, v, 10, TXT, align='right', bold=True)
for i, (lb, v, p) in enumerate([('ETF', '42.1%', .421), ('반도체', '18.3%', .183),
                                ('IT서비스', '11.2%', .112), ('금융', '8.0%', .080),
                                ('현금', '6.4%', .064)]):
    yy = y + 216 + i * 34
    text(x, yy, 140, 16, lb, 11, TXT, bold=(i == 0))
    text(x + 200, yy, 76, 16, v, 11, TXT, align='right', bold=True)
    bar(x, yy + 18, 276, 6, '#4C6EF5' if i == 0 else '#9DB6E6', p)
box(x, y + 390, 276, 46, 'gray')
text(x + 12, y + 398, 252, 32, 'ETF가 한 덩어리로 남아 실제 섹터가 보이지 않아요', 10, MUT)
mono(x, y + 444, 276, 'group_by=sector · lens=DIRECT')

# P9 비중 분석 — LOOK_THROUGH
x, y = ph(1960, B2, '비중 분석', back=False, tab='비중')
rect(x - 12, y, PW, 38, PANEL)
text(x, y + 2, 200, 18, '기준 2026-07-27 15:30', 9, MUT)
text(x, y + 18, 200, 18, '구성비중 기준 2026-07-26', 9, AMB_TX, bold=True)
text(x + 202, y, 62, 38, '새로고침', 9, PRI, align='right', bold=True)
rect(x, y + 46, 276, 28, PANEL, 'none', 1, arc=8)
for i, (lb, on) in enumerate([('종목', False), ('섹터', True), ('시장', False),
                              ('통화', False), ('자산군', False)]):
    if on:
        rect(x + 2 + i * 54.4, y + 48, 52, 24, '#FFFFFF', BORDER, 1, arc=8)
    text(x + 2 + i * 54.4, y + 48, 52, 24, lb, 10, TXT if on else MUT,
         align='center', bold=on)
card(x, y + 84, 276, 38, INF_BOX, INF_ST)
text(x + 12, y + 84, 180, 38, '구성종목 분해', 11, PRI, bold=True)
toggle(x + 230, y + 93, True)
ring(x + 52, y + 174, 42, '섹터')
for i, (lb, v, c) in enumerate([('반도체', '24.6%', '#4C6EF5'),
                                ('소프트웨어', '19.8%', '#7FB3F0'),
                                ('헬스케어', '9.1%', '#A8C6F0')]):
    yy = y + 144 + i * 22
    rect(x + 110, yy + 5, 8, 8, c, 'none', 1, arc=50)
    text(x + 124, yy, 90, 18, lb, 10, SUB)
    text(x + 210, yy, 56, 18, v, 10, TXT, align='right', bold=True)
for i, (lb, v, p, other) in enumerate([('반도체', '24.6%', .246, False),
                                       ('소프트웨어', '19.8%', .198, False),
                                       ('헬스케어', '9.1%', .091, False),
                                       ('금융', '8.6%', .086, False),
                                       ('현금', '6.4%', .064, False),
                                       ('기타 (현금·파생·미매칭)', '3.2%', .032, True)]):
    yy = y + 228 + i * 30
    text(x, yy, 176, 16, lb, 11, MUT if other else TXT, bold=(i == 0))
    text(x + 200, yy, 76, 16, v, 11, MUT if other else TXT, align='right', bold=True)
    bar(x, yy + 17, 276, 5, '#C8D3E4' if other else ('#4C6EF5' if i == 0 else '#9DB6E6'), p)
mono(x, y + 418, 276, 'lens=LOOK_THROUGH · 중첩 ETF 재귀 분해\n기타 버킷으로 합계 100% 보존')

# P10 계좌별
x, y = ph(2360, B2, '계좌별', back=False, tab='계좌')
asof(x - 12, y, PW, '기준 2026-07-27 15:30')
groups = [('일반', '41,200,000',
           [('한국투자증권 위탁', '32,100,000', '+6.2%', UP, '07-27 15:30', None),
            ('삼성증권', '9,100,000', '+1.4%', UP, '07-25 09:12', 'reauth')]),
          ('연금', '16,800,000',
           [('한국투자증권 IRP', '11,900,000', '+3.1%', UP, '07-27 15:30', None),
            ('미래에셋 연금', '4,900,000', '—', DIM, '07-26 15:30', 'stale')])]
yy = y + 34
for gname, gtot, accs in groups:
    rect(x, yy, 276, 22, PANEL)
    text(x + 10, yy, 100, 22, gname, 10, TXT, bold=True)
    text(x + 130, yy, 136, 22, gtot, 10, TXT, align='right', bold=True)
    yy += 26
    for nm, amt, pnl, c, sync, flag in accs:
        card(x, yy, 276, 58)
        text(x + 12, yy + 8, 168, 18, nm, 12, TXT, bold=True)
        text(x + 12, yy + 27, 168, 16, sync, 9, MUT)
        text(x + 176, yy + 8, 88, 18, amt, 12, TXT, align='right', bold=True)
        text(x + 176, yy + 27, 88, 16, pnl, 10, c, align='right', bold=True)
        if flag == 'reauth':
            pill(x + 12, yy + 40, 88, 15, AMB_BG, AMB_TX, '재인증 필요', size=8)
        elif flag == 'stale':
            pill(x + 12, yy + 40, 76, 15, GRY_BG, MUT, '07-26 이월', size=8)
        yy += 62
    yy += 6
hr(x, yy, 276, LINE)
text(x, yy + 8, 140, 22, '총자산', 12, TXT, bold=True)
text(x + 130, yy + 8, 146, 22, '58,000,000', 13, TXT, align='right', bold=True)
rect(x, yy + 42, 276, 36, '#FFFFFF', PRI, 1, arc=8)
text(x, yy + 42, 276, 36, '＋ 계좌 연동', 11, PRI, align='center', bold=True)
mono(x, y + 424, 276, 'group_by=account_type → account\n렌즈 없음 — look-through는 계좌 합계를 바꾸지 않음')

# ══════════════════════════════════════════════════════════════
# 밴드 3 — 원장 기반 뷰
# ══════════════════════════════════════════════════════════════
B3 = 1510

# P11 자산 변화
x, y = ph(360, B3, '자산 변화', back=True)
chip(x, y + 8, 82, '전체 계좌 ▽')
chip(x + 90, y + 8, 78, '이번 달 ▽', True)
y += 32
box(x, y + 6, 276, 86, 'ok')
text(x + 14, y + 12, 248, 18, '자산이 800만원 늘었는데', 11, MUT)
text(x + 14, y + 36, 120, 16, '넣은 돈', 9, MUT, bold=True)
text(x + 14, y + 52, 120, 26, '+600만원', 15, DOWN, bold=True)
rect(x + 140, y + 38, 1, 40, GRN_ST)
text(x + 154, y + 36, 108, 16, '번 돈', 9, MUT, bold=True)
text(x + 154, y + 52, 108, 26, '+200만원', 15, GRN, bold=True)
wf = [('총', '기초자산', '50,000,000', TXT, '#C8D3E4', .86),
      ('그룹', '넣은 돈', '+600만', DOWN, None, 0),
      ('항목', '＋ 입금', '+6,000,000', DOWN, '#7FB3F0', .10),
      ('항목', '－ 출금', '0', DIM, None, 0),
      ('그룹', '번 돈', '+200만', GRN, None, 0),
      ('강조', '± 투자손익', '+1,910,000', GRN, GRN_ST, .033),
      ('항목', '＋ 배당', '+120,000', GRN, GRN_ST, .012),
      ('항목', '－ 수수료 · 세금', '-30,000', MUT, '#C8D3E4', .008)]
yy = y + 102
for kind, lb, v, c, bc, p in wf:
    h = 26 if kind in ('총', '강조') else 24
    if kind == '강조':
        rect(x - 2, yy - 1, 280, h, GRN_BOX, 'none', 1, arc=6)
    if kind == '그룹':
        text(x + 4, yy, 130, h, lb, 11, TXT, bold=True)
        text(x + 120, yy, 100, h, v, 11, c, align='right', bold=True)
    else:
        ind = 4 if kind == '총' else 16
        text(x + ind, yy, 130, h, lb, 11, TXT if kind == '강조' else SUB,
             bold=(kind != '항목'))
        text(x + 120, yy, 100, h, v, 11, c, align='right', bold=True)
        if bc:
            rect(x + 226, yy + 9, max(4, int(46 * (p / .86))), 7, bc, 'none', 1, arc=50)
    yy += h
hr(x, yy + 4, 276, LINE)
text(x + 4, yy + 12, 130, 26, '기말자산', 12, TXT, bold=True)
text(x + 120, yy + 12, 152, 26, '58,000,000', 13, TXT, align='right', bold=True)
cyy = yy + 48
card(x, cyy, 276, 96, PANEL, 'none')
text(x + 12, cyy + 8, 252, 18, '투자손익 1,910,000원의 내역', 10, MUT, bold=True)
text(x + 12, cyy + 30, 120, 18, '확정 (실현)', 11, SUB)
text(x + 120, cyy + 30, 90, 18, '+850,000', 11, UP, align='right', bold=True)
text(x + 214, cyy + 30, 50, 18, '보기 →', 9, PRI, align='right', bold=True)
text(x + 12, cyy + 50, 120, 18, '평가 (미실현) 변화', 11, SUB)
text(x + 120, cyy + 50, 90, 18, '+1,060,000', 11, UP, align='right', bold=True)
text(x + 12, cyy + 72, 252, 16, '※ 일부 계좌는 거래내역이 없어 분해를 생략했어요', 9, DIM)
mono(x, cyy + 104, 276, '투자손익 = 나머지 전부 (잔차 항목 없음)\n거래 원장 없이 계산 — 연금계좌도 정확')
text(x, cyy + 140, 276, 16, '기준 07-27 15:30 · 기초 06-30', 9, DIM)

# P12 실현손익
x, y = ph(760, B3, '실현손익', back=False, tab='손익')
asof(x - 12, y, PW, '기준 2026-07-27 15:30')
chip(x, y + 34, 82, '전체 계좌 ▽')
chip(x + 90, y + 34, 62, '올해 ▽', True)
y += 32
card(x, y + 34, 276, 62, PANEL, 'none')
text(x + 12, y + 42, 252, 16, '올해 실현손익 (매도 확정)', 9, MUT, bold=True)
text(x + 12, y + 60, 252, 28, '+2,140,000원', 19, UP, bold=True)
hdr = y + 108
text(x, hdr, 120, 18, '종목', 9, DIM, bold=True)
text(x + 118, hdr, 70, 18, '매도일', 9, DIM, align='right', bold=True)
text(x + 192, hdr, 84, 18, '실현손익', 9, DIM, align='right', bold=True)
rows = [('삼성전자', '05-12', '+820,000', UP, None),
        ('카카오', '03-04', '-310,000', DOWN, 'SEEDED'),
        ('NAVER', '02-18', '+1,630,000', UP, 'SEEDED')]
for i, (nm, dt, v, c, g) in enumerate(rows):
    yy = y + 128 + i * 52
    hr(x, yy, 276)
    text(x, yy + 8, 120, 18, nm, 12, TXT, bold=True)
    if g:
        pill(x, yy + 28, 40, 16, AMB_BG, AMB_TX, '추정', size=8)
    text(x + 118, yy + 8, 70, 18, dt, 10, MUT, align='right')
    text(x + 192, yy + 8, 84, 18, v, 12, c, align='right', bold=True)
box(x, y + 292, 276, 44, 'gray')
text(x + 12, y + 300, 252, 30, '2개 종목은 추정치예요 · 미포함 계좌 1개', 10, MUT)
box(x, y + 346, 276, 38, 'info')
text(x + 12, y + 346, 180, 38, '이 기간 전체 투자손익', 11, TXT, bold=True)
text(x + 186, y + 346, 78, 38, '보기 →', 11, PRI, align='right', bold=True)
mono(x, y + 396, 276, 'realized_pnl_line · 이동가중평균\ngrade는 position_basis에서 상속')

# P13 종목 상세
x, y = ph(1160, B3, '삼성전자', back=True, right='＋ 알림')
card(x, y + 6, 276, 66, PANEL, 'none')
text(x + 12, y + 14, 150, 26, '71,200원', 17, TXT, bold=True)
text(x + 160, y + 16, 104, 22, '▲ 8.5%', 12, UP, align='right', bold=True)
text(x + 12, y + 44, 252, 18, '10주 · 평단 65,600 · 평가 712,000', 10, MUT)
text(x, y + 84, 276, 16, '계좌별 분해', 10, MUT, bold=True)
for i, (nm, q, ap) in enumerate([('한국투자 위탁 (일반)', '7주', '평단 64,200'),
                                 ('한국투자 IRP (연금)', '3주', '평단 68,900')]):
    yy = y + 104 + i * 40
    card(x, yy, 276, 34)
    text(x + 12, yy, 150, 34, nm, 11, TXT)
    text(x + 158, yy, 44, 34, q, 11, SUB, align='right')
    text(x + 204, yy, 60, 34, ap, 9, MUT, align='right')
text(x, y + 190, 276, 16, '거래내역', 10, MUT, bold=True)
for i, (dt, tp, q, pr) in enumerate([('2026-03-11', '매수', '5주', '@62,000'),
                                     ('2026-01-08', '매수', '5주', '@69,200')]):
    yy = y + 210 + i * 32
    hr(x, yy, 276)
    text(x, yy + 6, 90, 20, dt, 10, MUT)
    text(x + 92, yy + 6, 40, 20, tp, 10, UP, bold=True)
    text(x + 134, yy + 6, 50, 20, q, 10, SUB, align='right')
    text(x + 190, yy + 6, 86, 20, pr, 10, SUB, align='right')
box(x, y + 284, 276, 66, 'warn')
pill(x + 12, y + 292, 52, 17, AMB_BG, AMB_TX, 'SEEDED', size=8)
text(x + 72, y + 292, 192, 17, '거래내역 확보 2026-01-01부터', 9, AMB_TX, bold=True)
text(x + 12, y + 314, 252, 30, '이전 거래는 잔고 평단을 출발점으로 보정했어요. 실현손익은 추정치예요.', 9, SUB)
box(x, y + 360, 276, 46, 'warn')
text(x + 12, y + 368, 252, 32, '◆ 2026-04-15 액면분할 이력을 확인하지 못했어요', 10, AMB_TX, bold=True)
mono(x, y + 418, 276, 'position_basis(opening_qty, grade, ca_unknown)\ncorporate_action(ex_date) 보정 후 판정')

# ── 노트 2 : 화면 상태 전수 ─────────────────────────────────
NX, NY, NW = 1560, B3, 520
rect(NX, NY, NW, 600, '#FFFFFF', BORDER, 1, arc=8, shadow=True)
text(NX + 20, NY + 18, NW - 40, 24, '화면 상태 전수 (발췌)', 14, TXT, bold=True)
text(NX + 20, NY + 44, NW - 40, 18, '와이어플로우는 해피패스만 그린다. 누락되기 쉬운 상태를 앞에 적었다.',
     9, MUT)
hr(NX + 20, NY + 68, NW - 40)
st = [('요약', '지연 배너 · 연동 계좌 없음(온보딩) · 동기화 중'),
      ('종목별', '렌즈 ON 시 평단·손익률 컬럼 제거 · 보유 없음 · 필터 결과 없음'),
      ('비중 분석', '기타 버킷 · 구성비중 기준일 표기 · 축 전환 · 구성종목 없음'),
      ('계좌별', '재인증 필요 · 동기화 실패·이월 · 연동 해제 확인'),
      ('실현손익', '해당 기간 매도 없음 · 미포함 계좌 N개 · 추정 배지 · 전 계좌 조회 불가'),
      ('자산 변화', '기초 스냅샷 없음 · 계좌 편입·제외 · 현금흐름 미확보 · 손실 케이스'),
      ('종목 상세', '거래내역 없음 · 기업행위 경고(ca_unknown)'),
      ('계좌 연동', '추가 인증 요구 · 연동 실패·재시도 · 기관 선택')]
yy = NY + 80
for k, v in st:
    text(NX + 20, yy, 88, 18, k, 10, TXT, bold=True)
    text(NX + 112, yy, NW - 136, 36, v, 9, MUT, valign='top')
    yy += 40
box(NX + 20, yy + 4, NW - 40, 74, 'warn')
text(NX + 32, yy + 12, NW - 64, 18, '변형 — 현금흐름 미확보 (자산 변화)', 10, AMB_TX, bold=True)
text(NX + 32, yy + 32, NW - 64, 18, '1개 계좌의 입출금 내역이 없어 투자손익에 섞여 있을 수 있어요', 9, SUB)
text(NX + 32, yy + 52, NW - 64, 18, '잔차 항목을 만들지 않고 경고로 노출한다', 9, MUT)

# ── 노트 3 : 신뢰도 등급 ────────────────────────────────────
NX = 2140
rect(NX, NY, NW, 600, '#FFFFFF', BORDER, 1, arc=8, shadow=True)
text(NX + 20, NY + 18, NW - 40, 24, '신뢰도 등급 — 계산 가능한 판정', 14, TXT, bold=True)
hr(NX + 20, NY + 50, NW - 40)
box(NX + 20, NY + 62, NW - 40, 54, 'gray')
text(NX + 32, NY + 70, NW - 64, 18,
     'opening_qty = 현재 수량 - Σ(구간 매수) + Σ(구간 매도)', 10, TXT, mono=True)
text(NX + 32, NY + 90, NW - 64, 18,
     '기업행위(ex_date) 보정 후 계산 · (계좌 × 종목)마다', 9, MUT)
gr = [('VERIFIED', 'opening_qty = 0', '신뢰', '배지 없음', '#FFFFFF', SUB, BORDER),
      ('SEEDED', 'opening_qty > 0', '추정값', '추정 배지 + 사유', AMB_BG, AMB_TX, 'none'),
      ('UNAVAILABLE', '거래내역 미확보', '미제공', '거래내역 없음', GRY_BG, MUT, 'none'),
      ('CONFLICT', 'opening_qty < 0', '미제공', '경고 + 동기화 유도', '#FBE9E7', '#C0392B', 'none')]
yy = NY + 130
for k, cond, res, ui, bg, fg, st_ in gr:
    rect(NX + 20, yy, NW - 40, 46, bg, st_, 1, arc=8)
    text(NX + 32, yy + 5, 110, 18, k, 10, fg, bold=True)
    text(NX + 32, yy + 24, 130, 16, cond, 9, fg, mono=True)
    text(NX + 176, yy + 5, 80, 18, res, 10, fg, bold=True)
    text(NX + 268, yy + 5, NW - 300, 36, ui, 9, fg, valign='top')
    yy += 52
box(NX + 20, yy + 6, NW - 40, 58, 'warn')
text(NX + 32, yy + 14, NW - 64, 18, 'ca_unknown — 등급과 직교하는 플래그', 10, AMB_TX, bold=True)
text(NX + 32, yy + 34, NW - 64, 18,
     '등급은 "거래가 다 있나", 플래그는 "그 거래를 올바로 해석했나"', 9, SUB)
yy += 76
text(NX + 20, yy, NW - 40, 18, 'SEEDED 표시 정책', 10, TXT, bold=True)
text(NX + 20, yy + 20, NW - 40, 52,
     '조회 기간 한계·기관별 제공 범위 때문에 상당수 계좌가 SEEDED에 해당한다. '
     '숨기지 않고 표시하되 배지로 구분하고, 합계 하단에 추정 건수를 명시한다.', 9, MUT, valign='top')

# ══════════════════════════════════════════════════════════════
# 밴드 4 — 개념도
# ══════════════════════════════════════════════════════════════
B4 = 2200
text(360, B4, 900, 26, '하나의 팩트 → 축 조합으로 6개 뷰 (프로젝트 핵심 주장)', 14, TXT, bold=True)

cb = [(380, 400, '#FFFFFF', PRI, 'position_line',
       '그레인: as_of × 계좌 × 종목\n측정값만 저장 — 수량 · 매입금액 · 평가금액\n비율 컬럼은 스키마에 존재하지 않음'),
      (880, 340, '#EAF0FB', INF_ST, '렌즈 (lens)',
       'DIRECT  /  LOOK_THROUGH\n라인셋 → 라인셋 변환 · 스키마 보존\nΣ 평가금액 보존 · 기타 버킷'),
      (1320, 400, '#FFFFFF', LINE, '축 (group_by)',
       '계좌 · 계좌유형 · 종목 · 섹터\n시장 · 통화 · 자산군 · 레버리지(조건부)\n분류는 마스터 조인 — 보정이 과거에 소급'),
      (1820, 400, '#F0FAF3', GRN_ST, '6개 뷰',
       '요약 · 종목별 · 비중 분석 · 계좌별\n실현손익 · 자산 변화\n비율(수익률 · 비중)은 집계 후 파생')]
for bx, bw, fill, stc, t, s in cb:
    rect(bx, B4 + 40, bw, 116, fill, stc, 1.5, arc=8)
    text(bx + 16, B4 + 50, bw - 32, 22, t, 12, TXT, bold=True)
    text(bx + 16, B4 + 74, bw - 32, 74, s, 9.5, MUT, valign='top')
for ax in [(780, 880), (1220, 1320), (1720, 1820)]:
    edge([(ax[0], B4 + 98), (ax[1], B4 + 98)], '', PRI)
text(780, B4 + 66, 100, 18, '변환', 9, PRI, align='center', bold=True)
text(1220, B4 + 66, 100, 18, '집계', 9, PRI, align='center', bold=True)
text(1720, B4 + 66, 100, 18, '서빙', 9, PRI, align='center', bold=True)

L4 = B4 + 176
led = [(380, 440, '보유 스냅샷 · position_line', '현재 상태 = 진실. 항상 신뢰.\n요약 · 종목별 · 비중 · 계좌별', GRN_BG, GRN),
       (860, 440, '현금흐름 · cashflow', '자산 변화의 원인.\n미확보는 경고로 노출 (잔차 없음)', BLU_BG, PRI),
       (1340, 440, '거래 원장 · trade', '실현/미실현 분해 전용.\n등급 4단계 — 실현손익 뷰에만 노출', AMB_BG, AMB_TX)]
for bx, bw, t, s, bg, fg in led:
    rect(bx, L4, bw, 92, bg, 'none', 1, arc=8)
    text(bx + 16, L4 + 10, bw - 32, 20, t, 11, fg, bold=True)
    text(bx + 16, L4 + 32, bw - 32, 50, s, 9.5, SUB, valign='top')
rect(1820, L4, 400, 92, '#FFFFFF', LINE, 1.5, arc=8)
text(1836, L4 + 10, 368, 20, '리스크 격리', 11, TXT, bold=True)
text(1836, L4 + 32, 368, 50,
     '6개 뷰 중 4개는 항상 신뢰 가능한 원장만 사용한다.\n'
     '거래내역 불완전은 실현손익 뷰 한 곳에 갇히고,\n자산 변화 뷰가 백스톱이 된다.', 9.5, SUB, valign='top')

box(380, L4 + 108, 1840, 38, 'ok')
text(380, L4 + 108, 1840, 38,
     '↳ 필드 매핑 · 검증 규칙 · 상태 전수 · 카탈로그 = 스펙 문서(.md)에서 확정',
     10, GRN, align='center')

# ══════════════════════════════════════════════════════════════
# 흐름 (엣지)
# ══════════════════════════════════════════════════════════════
M1 = B1 + 300
edge([(660, M1), (760, M1)], '기관 선택')
edge([(1060, M1), (1080, M1), (1080, 433), (1100, 433)], '암호화 전송', lseg=0)
edge([(1200, 433), (1220, 433), (1220, M1), (1240, M1)], '= 필요', lseg=2, loff=(0, -12))
edge([(1150, 395), (1150, 118), (1790, 118), (1790, B1)], '= 불필요', lseg=1)
edge([(1540, M1), (1640, M1)], '인증 완료')
edge([(1740, B1 + 600), (1740, 790), (510, 790), (510, B2)],
     '동기화 완료 → 포트폴리오', GRN, lseg=1)

M2 = B2 + 300
edge([(660, M2), (760, M2)], '종목 탭')
edge([(1060, M2), (1160, M2)], '렌즈 ON')
edge([(1460, M2), (1560, M2)], '비중 탭')
edge([(1860, M2), (1960, M2)], '분해 ON')
edge([(2260, M2), (2360, M2)], '계좌 탭')

edge([(460, B2 + 600), (460, B3)], '왜? →', lseg=0, loff=(28, 0))
edge([(560, B2 + 600), (560, 1470), (910, 1470), (910, B3)], '손익 탭', lseg=1)
edge([(960, B2 + 600), (960, 1470), (1310, 1470), (1310, B3)], '행 탭', lseg=1)
edge([(910, B3 + 600), (910, 2150), (510, 2150), (510, B3 + 600)],
     '이 기간 전체 투자손익 →', lseg=1)

# ══════════════════════════════════════════════════════════════
import os
OUT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'wireflow.drawio'), 'w').write(
    to_drawio(PGW, PGH, '포트폴리오 와이어플로우 v1'))
w, h = to_png(PGW, PGH, os.path.join(OUT, 'wireflow.png'), S=1.5)
print('shapes=%d  png=%dx%d' % (len(SHAPES), w, h))
