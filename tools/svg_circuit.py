# -*- coding: utf-8 -*-
"""회로도 조각을 찍는다 — 도선·저항·전원·노드 점·전류 화살표·극성 표시.

**왜 프리미티브부터인가.** 전기전자 과목은 앞으로 **전 장이 회로도**다. 낱개로 그리면
장마다 지그재그 꼭짓점과 리드 길이를 다시 잡게 되고, 그러면 같은 저항이 장마다 다른
크기로 나온다. 사람이 정하는 것은 **무엇을 어디에 놓을지**뿐이고 좌표는 이 도구가 찍는다
(삽화 규격 「손으로 좌표를 잡지 않는다」).

**색은 뜻이 있을 때만 준다**(규격: 한 시각 요소는 한 물리량만 맡는다). 기본은 형상선
`#3a4252` 하나이고, `--color` 로 바꾸는 자리는 **노드마다 다른 색을 줄 때**뿐이다 —
「한 노드 위의 모든 점은 전위가 같다」가 이 과목 1장의 첫 학습목표라, 그 하나만은
색이 물리량(어느 노드인가)을 맡는다.

부품 하나마다 **두 끝점(리드 끝)** 을 주석으로 함께 찍는다. 도선은 그 값을 이어 그린다.

사용:
    python tools/svg_circuit.py wire --points 60,60 220,60 220,180
    python tools/svg_circuit.py resistor --at 140,60 --orient h --label R --sub 1
    python tools/svg_circuit.py capacitor --at 140,60 --orient h --label C --sub 1
    python tools/svg_circuit.py battery --at 140,60 --orient v [--flip]
    python tools/svg_circuit.py resistor --at 140,60 --orient h --scale 2.0
    python tools/svg_circuit.py source --at 60,120 --kind v --label V --sub s
    python tools/svg_circuit.py node-dot --at 220,60
    python tools/svg_circuit.py arrow --from 240,60 --to 300,60 --label i
    python tools/svg_circuit.py polarity --at 140,60 --orient h
"""
import argparse
import math
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

from buildlib.checks_svg import DIGIT_UNDER_LOWER_RATIO                    # noqa: E402

WIRE_COLOR = "#3a4252"      # 형상선 — 규격이 정한 값 그대로
WIRE_WIDTH = 2.0            # 형상선 굵기 — 치수선 상한(1.5)보다 굵어 둘이 안 헷갈린다
BODY_FILL = "#e4e7ec"       # 부품 몸통 — 고정부 채움색
TEXT_COLOR = "#1f2933"
LABEL_SIZE = 17.0           # 라벨 — 기존 이 과목 삽화(fig-ee01-quantities)와 같은 크기
SUB_PCT = "83%"             # 아래첨자 — 규격 하한 12.90px 을 17px 기준으로 넘긴다

# 저항 한 개의 치수(규격 「회로 소자」 절). 꼭짓점 아홉 · 꼭짓점 간격 40/9 ≈ 4.4.
# 고른 값(2026-09-25 E43 「지그재그가 압축되게」): 옛 44·꼭짓점 일곱은 간격 6.3 이었다.
# 발자국(몸통 + 리드 둘)은 64 그대로 — 이미 찍은 회로도의 도선 끊는 자리가 안 바뀐다.
RES_BODY, RES_AMP, RES_LEAD = 40.0, 7.0, 12.0
RES_VERTS = 9               # 고른 값: 옛 7 보다 촘촘하게(E43) — 홀수라 양 끝 꼭짓점이 같은 쪽이다
RES_PITCH = RES_BODY / RES_VERTS
# 커패시터 한 개의 치수. 판 둘이 마주 보는 것이 기호의 전부라, 판 길이를 저항 진폭(8)의
# 1.75 배로 잡아 「마주 본 두 판」이 지그재그와 안 헷갈린다. 간격 8 은 판 길이의 절반 아래라
# 좁아 보이고, 리드 28 을 더하면 발자국이 저항과 같은 64 가 된다.
CAP_HALF, CAP_GAP, CAP_LEAD = 14.0, 8.0, 28.0
CAP_PLATE_WIDTH = 3.0       # 판은 도선보다 굵다 — 「선」이 아니라 「판」으로 읽혀야 한다
# 전지 − 판 길이 / + 판 길이. 고른 값: 표준 기호의 「긴 판·짧은 판」이 한눈에 갈리는 절반(설계도 E15).
BATTERY_SHORT_RATIO = 0.5
# 코일 혹 수. 고른 값: 표준 기호의 4 — 40 몸통에 반지름 5 라 혹 높이가 저항 진폭(7)보다 낮아 안 눌린다.
IND_TURNS = 4
# 다이오드 삼각형 길이·반높이. 고른 값: 반높이를 커패시터 판(14)보다 작은 11 로 두어 판과 안 헷갈리고,
# 길이 18 은 정삼각형에 가까워 「방향」이 한눈에 읽힌다.
DIODE_LEN, DIODE_HALF = 18.0, 11.0
# 저항 몸통 배율 상한. 고른 값(설계도 2026-09-24 E24): 40×2.5 = 100 — 640 폭 그림에 저항 셋이 가로로 들어간다.
RES_SCALE_MAX = 2.5
# 전원 동그라미 지름 ≤ 저항 몸통 × 이 비(규격 「회로 소자」 절 · 자 `circuit-part-ratio`).
# 고른 값(2026-09-25 E43 「전류원은 다른 거 대비 왜 이렇게 큰」): 옛 지름 34 는 몸통 44 의 0.77 이었다.
# 0.6(지름 24)을 먼저 골랐으나 안 화살촉이 화면 7.7px 로 하한 8 에 못 미쳐(lint) 반지름 13 이 드는 0.65 로 올렸다.
SRC_DIAM_RATIO = 0.65
# 전원 동그라미 반지름 13(지름 26 = 몸통 40 × 0.65). 전류원 안 화살표(촉 8.5 · 꼬리 13)가 들어가는 하한이다.
SRC_R = 13.0
SRC_HEAD, SRC_TAIL = 8.5, 13.0   # 촉 8.5 = 화면 8.1px(하한 8) · 꼬리 = 촉 × 1.5 이상
NODE_R = 4.0                # 노드 점 — 선 굵기 2 의 두 배라 「점」으로 읽힌다
ARROW_HEAD, ARROW_HALF = 11.0, 4.5   # 전류 화살촉 — 다른 삽화의 화살촉과 같은 비례
LABEL_GAP = 15.0            # 부품 중심에서 라벨 중심까지(수직 방향)
# 전원 중심에서 극성 부호까지. 반지름 13 + 테두리 반굵기 1 + 규격 여백 0.5em(8.5) + 글자 반너비 5 = 27.5.
POLARITY_REACH = 28.0


def _rot(v, ux, uy):
    """국소 좌표 (앞, 옆) 을 단위벡터 (ux, uy) 기준의 화면 좌표로."""
    return (v[0] * ux[0] + v[1] * uy[0], v[0] * ux[1] + v[1] * uy[1])


def axes(orient):
    """`h` 는 오른쪽, `v` 는 아래쪽을 「앞」으로 본다."""
    if orient == "h":
        return (1.0, 0.0), (0.0, -1.0)
    if orient == "v":
        return (0.0, 1.0), (1.0, 0.0)
    raise SystemExit("orient 는 h 또는 v 다: " + repr(orient))


def label_text(x, y, label, sub=None, size=LABEL_SIZE, anchor="middle"):
    body = label
    if sub:
        pct = SUB_PCT
        if str(sub).isdigit() and label and label[-1].islower():
            # 소문자 밑 숫자는 0.70배 — `checks_svg.DIGIT_UNDER_LOWER_RATIO` 가 정본
            pct = "%.0f%%" % (DIGIT_UNDER_LOWER_RATIO * 100.0)
        body += "<tspan dy='2.5' font-size='%s'>%s</tspan>" % (pct, sub)
    return ("<text x='%.2f' y='%.2f' font-size='%.0f' fill='%s' text-anchor='%s'>%s</text>"
            % (x, y, size, TEXT_COLOR, anchor, body))


def _one_path(points, color, width):
    d = " L".join("%.2f %.2f" % (p[0], p[1]) for p in points)
    return ("<path d='M%s' fill='none' stroke='%s' stroke-width='%.1f' "
            "stroke-linecap='round' stroke-linejoin='round'/>" % (d, color, width))


def wire(points, color=WIRE_COLOR, width=WIRE_WIDTH):
    """도선 한 줄.

    ★ **꼭짓점이 셋인 꺾은선은 두 조각으로 나눠 낸다.** `M…L…L` 에 `fill='none'` 은
    빌드의 L1 검사가 **닫다 만 화살촉**으로 읽는 서명이고(`checks_svg` L1), 실제로
    2026-09-09 첫 회로도에서 도선 둘이 그렇게 신고됐다. 끝을 둥글게 마감하므로
    나눠 그려도 꺾인 자리는 그대로 둥글다.
    """
    if len(points) == 3:
        return (_one_path(points[:2], color, width)
                + _one_path(points[1:], color, width))
    return _one_path(points, color, width)


def resistor_scale(value, smallest):
    """저항 값 → 몸통 배율. 선형(값 ∝ 길이)이고 가장 작은 값이 1배, 상한 `RES_SCALE_MAX`.

    설계도 2026-09-24 E24 — 문풀·문제 그림에서 값이 다른 저항이 같은 길이면 크기 비교가 안 읽힌다.
    상한 넘는 값은 상한에 붙는다(비례가 깨진다 — 그 그림은 사람이 본다).
    """
    if smallest <= 0 or value <= 0:
        raise SystemExit("저항 값은 양수다")
    return min(value / smallest, RES_SCALE_MAX)


def resistor(at, orient, color=WIRE_COLOR, scale=1.0):
    """지그재그 저항 한 개. (svg, 두 리드 끝) 을 낸다.

    `scale` 은 몸통 길이 배율(1~`RES_SCALE_MAX`). **꼭짓점 간격을 `RES_PITCH` 로 두고 꼭짓점 수를
    늘린다**(홀수) — 간격을 늘리면 E43 「지그재그가 벌어졌다」가 긴 저항에서 되살아난다. 리드 길이는 그대로다.
    """
    if not 1.0 <= scale <= RES_SCALE_MAX:
        raise SystemExit("scale 은 1 ~ %g 다: %r" % (RES_SCALE_MAX, scale))
    ux, uy = axes(orient)
    body = RES_BODY * scale
    half = body / 2.0
    pts = [(-half - RES_LEAD, 0.0), (-half, 0.0)]
    n = max(RES_VERTS, int(round(body / RES_PITCH)))
    n += 1 - n % 2
    for i in range(n):
        fx = -half + body * (2 * i + 1) / (2.0 * n)
        pts.append((fx, RES_AMP if i % 2 == 0 else -RES_AMP))
    pts.append((half, 0.0))
    pts.append((half + RES_LEAD, 0.0))
    world = [(at[0] + _rot(p, ux, uy)[0], at[1] + _rot(p, ux, uy)[1]) for p in pts]
    return wire(world, color=color), (world[0], world[-1])


def capacitor(at, orient, color=WIRE_COLOR):
    """평행판 커패시터 한 개. (svg, 두 리드 끝) 을 낸다.

    **발자국을 저항과 같은 64 로 맞춘다** — 반길이 32 가 이 리포의 회로 삽화 전부에서
    도선을 끊는 자리라, 커패시터만 다르면 같은 그림 안에서 부품이 어긋나 보인다.
    """
    ux, uy = axes(orient)
    half_gap = CAP_GAP / 2.0
    out = []
    for sign in (-1.0, 1.0):
        lead_a = _rot((sign * (half_gap + CAP_LEAD), 0.0), ux, uy)
        lead_b = _rot((sign * half_gap, 0.0), ux, uy)
        out.append(wire([(at[0] + lead_a[0], at[1] + lead_a[1]),
                         (at[0] + lead_b[0], at[1] + lead_b[1])], color=color))
        top = _rot((sign * half_gap, CAP_HALF), ux, uy)
        bot = _rot((sign * half_gap, -CAP_HALF), ux, uy)
        out.append(wire([(at[0] + top[0], at[1] + top[1]),
                         (at[0] + bot[0], at[1] + bot[1])],
                        color=color, width=CAP_PLATE_WIDTH))
    reach = _rot((half_gap + CAP_LEAD, 0.0), ux, uy)
    ends = ((at[0] - reach[0], at[1] - reach[1]), (at[0] + reach[0], at[1] + reach[1]))
    return "".join(out), ends


def inductor(at, orient, color=WIRE_COLOR):
    """코일 한 개 — 반원 혹 `IND_TURNS` 개. (svg, 두 리드 끝) 을 낸다.

    발자국은 저항·커패시터와 같은 64(몸통 44 + 리드 10×2). 혹은 h 면 위, v 면 오른쪽으로 부푼다 —
    호는 `A` 명령이라 L1(닫다 만 화살촉 서명 `M…L…L`)에 안 걸린다.
    """
    ux, uy = axes(orient)
    half = RES_BODY / 2.0
    r = RES_BODY / (2.0 * IND_TURNS)

    def w(p):
        q = _rot(p, ux, uy)
        return (at[0] + q[0], at[1] + q[1])

    a, s = w((-half - RES_LEAD, 0.0)), w((-half, 0.0))
    d = "M%.2f %.2f L%.2f %.2f" % (a[0], a[1], s[0], s[1])
    for i in range(1, IND_TURNS + 1):
        e = w((-half + 2.0 * r * i, 0.0))
        d += " A%.2f %.2f 0 0 1 %.2f %.2f" % (r, r, e[0], e[1])
    b = w((half + RES_LEAD, 0.0))
    d += " L%.2f %.2f" % (b[0], b[1])
    svg = ("<path d='%s' fill='none' stroke='%s' stroke-width='%.1f' "
           "stroke-linecap='round' stroke-linejoin='round'/>" % (d, color, WIRE_WIDTH))
    return svg, (a, b)


def diode(at, orient, color=WIRE_COLOR):
    """다이오드 한 개 — 앞(h 는 오른쪽, v 는 아래) 을 향한 삼각형과 그 끝의 막대. (svg, 두 리드 끝).

    발자국 64(몸통 `DIODE_LEN` + 리드). 삼각형은 채움 없이 형상선만 — 전류 방향 화살촉과 안 헷갈리게
    막대와 한 벌로 그린다.
    """
    ux, uy = axes(orient)
    half = DIODE_LEN / 2.0
    lead = 32.0 - half

    def w(p):
        q = _rot(p, ux, uy)
        return (at[0] + q[0], at[1] + q[1])

    a, b = w((-half - lead, 0.0)), w((half + lead, 0.0))
    t1, t2, tip = w((-half, DIODE_HALF)), w((-half, -DIODE_HALF)), w((half, 0.0))
    k1, k2 = w((half, DIODE_HALF)), w((half, -DIODE_HALF))
    # 꼭짓점 셋 `M L L Z` 는 빌드가 화살촉으로 읽는다(2026-09-25 첫 주입: 촉 17.2 · 꼬리 22 로 FAIL).
    # 다이오드는 화살표가 아니므로 밑변 가운데 꼭짓점 하나를 더해 넷으로 둔다 — 모양은 같다.
    bm = w((-half, 0.0))
    tri = ("<path d='M%.2f %.2f L%.2f %.2f L%.2f %.2f L%.2f %.2f Z' fill='%s' stroke='%s'"
           " stroke-width='%.1f' stroke-linejoin='round'/>"
           % (t1[0], t1[1], bm[0], bm[1], t2[0], t2[1], tip[0], tip[1],
              BODY_FILL, color, WIRE_WIDTH))
    svg = (_one_path([a, w((-half, 0.0))], color, WIRE_WIDTH) + tri
           + _one_path([k1, k2], color, CAP_PLATE_WIDTH) + _one_path([tip, b], color, WIRE_WIDTH))
    return svg, (a, b)


def npn(at, color=WIRE_COLOR):
    """npn 트랜지스터 — 베이스 막대 · 컬렉터 사선(위) · 이미터 사선(아래, 바깥을 향한 화살촉).

    (svg, {'b','c','e'} 리드 끝). 베이스는 왼쪽 수평, 컬렉터·이미터는 오른쪽 위·아래 수직으로 끝난다.
    이미터 사선 길이 28.4 는 화살촉 11 의 꼬리 규격(1.5배 이상)을 넘기려고 고른 값이다.
    """
    x, y = at
    bar_x = x - 8.0
    out = [_one_path([(x - 40.0, y), (bar_x, y)], color, WIRE_WIDTH),
           _one_path([(bar_x, y - 14.0), (bar_x, y + 14.0)], color, CAP_PLATE_WIDTH),
           wire([(bar_x, y - 6.0), (x + 14.0, y - 24.0), (x + 14.0, y - 40.0)], color=color),
           arrow((bar_x, y + 6.0), (x + 14.0, y + 24.0), color=color),
           _one_path([(x + 14.0, y + 24.0), (x + 14.0, y + 40.0)], color, WIRE_WIDTH)]
    return "".join(out), {"b": (x - 40.0, y), "c": (x + 14.0, y - 40.0), "e": (x + 14.0, y + 40.0)}


def battery(at, orient, color=WIRE_COLOR, flip=False):
    """전지 한 개 — 길이 다른 평행판 둘(긴 판 +, 짧은 판 −). (svg, 두 리드 끝) 을 낸다.

    설계도 2026-09-24 E15 — 전지는 생성기가 없어 손으로 그렸고 판 간격이 20 으로 벌어졌다(재발).
    **판 간격은 커패시터와 같은 `CAP_GAP`(8 ≈ 0.5em)**, 발자국도 커패시터와 같은 64 다.
    `flip` 이 거짓이면 「앞」 쪽(h 는 왼쪽, v 는 위쪽)이 + 판이다.
    """
    ux, uy = axes(orient)
    half_gap = CAP_GAP / 2.0
    out = []
    for sign in (-1.0, 1.0):
        lead_a = _rot((sign * (half_gap + CAP_LEAD), 0.0), ux, uy)
        lead_b = _rot((sign * half_gap, 0.0), ux, uy)
        out.append(wire([(at[0] + lead_a[0], at[1] + lead_a[1]),
                         (at[0] + lead_b[0], at[1] + lead_b[1])], color=color))
        positive = (sign < 0) != flip
        reach = CAP_HALF if positive else CAP_HALF * BATTERY_SHORT_RATIO
        top = _rot((sign * half_gap, reach), ux, uy)
        bot = _rot((sign * half_gap, -reach), ux, uy)
        out.append(wire([(at[0] + top[0], at[1] + top[1]),
                         (at[0] + bot[0], at[1] + bot[1])],
                        color=color, width=CAP_PLATE_WIDTH))
    reach = _rot((half_gap + CAP_LEAD, 0.0), ux, uy)
    ends = ((at[0] - reach[0], at[1] - reach[1]), (at[0] + reach[0], at[1] + reach[1]))
    return "".join(out), ends


def source(at, kind, color=WIRE_COLOR, side="left", down=False):
    """전원 한 개. `v` 는 극성 부호를 곁에 단 동그라미, `i` 는 화살표를 넣은 동그라미.

    ★ **부호를 동그라미 안에 넣지 않는다.** 규격의 글자-선 여백 0.5em 을 지키면 반지름 17
    안에 17px 글자 둘이 못 들어간다(2026-09-09 실측: 안에 넣었더니 F1 넷 · 경계 걸침 둘).
    `side` 는 부호 쪽이다 — **이름·값 라벨의 반대쪽**(보통 고리 안쪽)으로 준다. 같은 쪽이면 부호가 라벨과
    동그라미 사이에 끼어 라벨이 근접성 상한 1.0em 을 못 지킨다(EE-SRCLABEL · 라벨은 `SRC_LABEL_REACH`). `down` 은 + 를 아래(전압원)·화살표를
    아래(전류원)로 뒤집는다.
    **리드는 부르는 쪽이 위아래로 남긴다** — 동그라미 끝이 꺾인 도선에 바로 닿으면 안 된다(규격 「회로 소자」).
    """
    cx, cy = at
    s = -1.0 if down else 1.0
    parts = ["<circle cx='%.2f' cy='%.2f' r='%.2f' fill='%s' stroke='%s' stroke-width='%.1f'/>"
             % (cx, cy, SRC_R, BODY_FILL, color, WIRE_WIDTH)]
    if kind == "v":
        sx = cx - POLARITY_REACH if side == "left" else cx + POLARITY_REACH
        # 글자 중심이 기준선 6 위라 + 중심 cy−10 · − 중심 cy+10 — 동그라미 위아래 끝(±12) 안에 든다
        parts.append(label_text(sx, cy + 6.0 - 10.0 * s, "+"))
        parts.append(label_text(sx, cy + 6.0 + 10.0 * s, "−"))
    elif kind == "i":
        # ★ 동그라미 안의 화살표는 규격 둘에 동시에 끼인다 — 화살촉 **하한 8px** 과
        #   「꼬리는 촉의 1.5배 이상」. 반지름 13 안에서 둘을 다 채우는 자리가 촉 8.5 · 꼬리 13 이다.
        half = (SRC_HEAD + SRC_TAIL) / 2.0
        head_base, tip = cy + (half - SRC_TAIL) * s, cy - half * s
        parts.append(wire([(cx, cy + half * s), (cx, head_base)], color=color, width=1.8))
        parts.append("<path d='M%.2f %.2f L%.2f %.2f L%.2f %.2f Z' fill='%s' stroke='%s'"
                     " stroke-width='0.75' stroke-linejoin='round'/>"
                     % (cx - ARROW_HALF, head_base, cx + ARROW_HALF, head_base,
                        cx, tip, color, color))
    else:
        raise SystemExit("kind 는 v 또는 i 다: " + repr(kind))
    return "".join(parts), ((cx, cy - SRC_R), (cx, cy + SRC_R))


def node_dot(at, color=WIRE_COLOR):
    return "<circle cx='%.2f' cy='%.2f' r='%.2f' fill='%s'/>" % (at[0], at[1], NODE_R, color)


def arrow(frm, to, color=WIRE_COLOR):
    """전류 화살표 — 도선과 나란히 놓고 쓴다."""
    dx, dy = to[0] - frm[0], to[1] - frm[1]
    length = math.hypot(dx, dy)
    if length < ARROW_HEAD + 1.0:
        raise SystemExit("화살표가 화살촉보다 짧다")
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    base = (frm[0] + ux * (length - ARROW_HEAD), frm[1] + uy * (length - ARROW_HEAD))
    svg = wire([frm, base], color=color, width=1.8)
    svg += ("<path d='M%.2f %.2f L%.2f %.2f L%.2f %.2f Z' fill='%s' stroke='%s'"
            " stroke-width='0.75' stroke-linejoin='round'/>"
            % (base[0] + px * ARROW_HALF, base[1] + py * ARROW_HALF,
               base[0] - px * ARROW_HALF, base[1] - py * ARROW_HALF,
               to[0], to[1], color, color))
    return svg


def polarity(at, orient, reach=None, offset=24.0, side="left"):
    """소자 양 끝의 + / − 표시. 「극성 표시는 부호가 아니다」 절이 쓰는 조각이다.

    ★ **부호를 소자 축 위에 놓지 않는다.** 첫 판은 세로 소자에서 + 와 − 를 리드 선 위에
    얹어 글자와 도선이 겹쳤다(2026-09-09). 축을 따라 `reach` 만큼 벌리되, 축과 직각으로
    `offset` 만큼 비켜 놓는다 — `side` 로 라벨 반대쪽을 고른다.
    """
    reach = (RES_BODY / 2.0 + RES_LEAD) if reach is None else reach
    if orient == "v":
        s = -1.0 if side == "left" else 1.0
        x = at[0] + s * offset
        return (label_text(x, at[1] - reach + 5.0, "+")
                + label_text(x, at[1] + reach + 5.0, "−"))
    y = at[1] - offset + 5.0
    return label_text(at[0] - reach, y, "+") + label_text(at[0] + reach, y, "−")


_NUM = r"-?\d+(?:\.\d+)?"
_PATH_RE = re.compile(r"<path d='(M[^']*)'([^>]*)/>")
_TEXT_RE = re.compile(r"<text x='(%s)' y='(%s)'([^>]*)>(.*?)</text>" % (_NUM, _NUM))
_CIRCLE_RE = re.compile(r"<circle cx='(%s)' cy='(%s)' r='(%s)' fill='%s'[^>]*/>" % (_NUM, _NUM, _NUM, BODY_FILL))
# 다시 찍기가 알아보는 옛 전원: 채운 동그라미 반지름 [10, 30] 중 SRC_R 아닌 것 — 생성기 17·12 · 손그림 14·28.
# 극성 부호는 동그라미 옆 이 거리 안(옛 생성기 31−17 = 14 · 손그림 여유)의 「+」「−」 글자다.
_OLD_SRC_R_MIN, _OLD_SRC_R_MAX, _OLD_REACH_PAD = 10.0, 30.0, 20.0


def _ml_points(d):
    """`M x y L x y …` 꼴이면 점 목록, 아니면 None(호·닫힘 등)."""
    if not re.fullmatch(r"M%s %s(?: L%s %s)*" % ((_NUM,) * 4), d.strip()):
        return None
    nums = [float(v) for v in re.findall(_NUM, d)]
    return list(zip(nums[0::2], nums[1::2]))


def _same(p, q, tol=0.06):
    return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol


def _old_resistor(pts):
    """옛 저항 서명(리드 + 꼭짓점 일곱 + 리드, 발자국 64) → (중심, 방향) 또는 None."""
    if len(pts) != 11:
        return None
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    if abs(y0 - y1) < 0.06 and abs(math.hypot(x1 - x0, 0) - 64.0) < 0.1:
        orient, side = "h", [abs(p[1] - y0) for p in pts[2:9]]
    elif abs(x0 - x1) < 0.06 and abs(y1 - y0 - 64.0) < 0.1:
        orient, side = "v", [abs(p[0] - x0) for p in pts[2:9]]
    else:
        return None
    if min(side) < 3.0 or max(side) - min(side) > 0.1:
        return None
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0), orient


def _rezig(pts):
    """리드 길이·방향이 제각각인 옛 저항(점 11: 리드 끝 · 몸통 시작 · 꼭짓점 7 · 몸통 끝 · 리드 끝) → 새 저항 점 목록.
    리드 끝 둘은 그대로 두고 몸통(40 · 꼭짓점 9 · 진폭 7)을 옛 몸통 가운데에 다시 놓는다. 아니면 None.
    손그림·움직이는 그림(morph 점 목록)용 — 방향은 몸통 시작→끝 벡터로 읽어 기울어진 저항도 받는다."""
    if len(pts) != 11:
        return None
    (ax, ay), (bx, by) = pts[1], pts[9]
    length = math.hypot(bx - ax, by - ay)
    if length < 20.0:
        return None
    ux, uy = (bx - ax) / length, (by - ay) / length
    nx, ny = -uy, ux
    offs = [(p[0] - ax) * nx + (p[1] - ay) * ny for p in pts[2:9]]
    amp = sum(abs(o) for o in offs) / 7.0
    if amp < 3.0 or any(abs(abs(o) - amp) > 0.2 * amp for o in offs) \
            or any(offs[i] * offs[i + 1] >= 0 for i in range(6)):
        return None
    for lead, body in ((pts[0], pts[1]), (pts[10], pts[9])):     # 리드는 몸통 축 위에 있어야 한다
        if abs((lead[0] - body[0]) * nx + (lead[1] - body[1]) * ny) > 0.6:
            return None
    cx, cy = (ax + bx) / 2.0, (ay + by) / 2.0
    half = RES_BODY / 2.0
    side = 1.0 if offs[0] > 0 else -1.0
    out = [pts[0], (cx - ux * half, cy - uy * half)]
    for i in range(RES_VERTS):
        f = -half + RES_BODY * (2 * i + 1) / (2.0 * RES_VERTS)
        s = side * RES_AMP * (1 if i % 2 == 0 else -1)
        out.append((cx + ux * f + nx * s, cy + uy * f + ny * s))
    out += [(cx + ux * half, cy + uy * half), pts[10]]
    return [(round(x, 2), round(y, 2)) for x, y in out]


def _d_of(svg):
    return re.search(r"d='([^']*)'", svg).group(1)


def restamp_svg(svg):
    """이미 들어간 회로도의 옛 조각(저항 꼭짓점 일곱 · 코일 반지름 5.5 · 전원 반지름 17)을 지금 상수로
    다시 찍는다. (새 svg, 알림 목록).

    잰 것: 조각의 좌표 서명(생성기 출력 꼴). 손그림 좌표는 서명이 달라 안 건드린다.
    전원 끝이 가로 도선에 바로 닿아 있으면(E43) 전원을 그 세로 구간 가운데로 옮기고 곁 글자도 같이 옮긴다.
    못 보는 것: 옮긴 뒤 다른 글자와의 겹침(빌드 lint·렌더가 본다).
    """
    notes = []

    def res_sub(m):
        pts = _ml_points(m.group(1))
        hit = pts and _old_resistor(pts)
        if hit:
            return "<path d='%s'%s/>" % (_d_of(resistor(hit[0], hit[1])[0]), m.group(2))
        new = pts and _rezig(pts)
        if not new:
            return m.group(0)
        return "<path d='M%s'%s/>" % (" L".join("%g %g" % p for p in new), m.group(2))
    # 손그림 경로는 `d='M… L…'` 앞에 id 등이 붙기도 한다 — 속성 순서와 무관하게 d 만 바꾼다
    svg = _PATH_RE.sub(res_sub, svg)

    def any_path_sub(m):
        pts = _ml_points(m.group(2))
        new = pts and _rezig(pts)
        if not new:
            return m.group(0)
        return m.group(0).replace(m.group(2), "M" + " L".join("%g %g" % p for p in new), 1)
    svg = re.sub(r"<path\b([^>]*?)\sd='([^']*)'", any_path_sub, svg)

    def poly_sub(m):
        nums = [float(v) for v in re.findall(_NUM, m.group(2))]
        new = _rezig(list(zip(nums[0::2], nums[1::2])))
        if not new:
            return m.group(0)
        return m.group(0).replace(m.group(2), " ".join("%g,%g" % p for p in new), 1)
    svg = re.sub(r"<polyline\b([^>]*?)\spoints='([^']*)'", poly_sub, svg)

    ind = re.compile(r"M(%s) (%s) L%s %s(?: A5\.50 5\.50 0 0 1 %s %s){4} L(%s) (%s)"
                     % (_NUM, _NUM, _NUM, _NUM, _NUM, _NUM, _NUM, _NUM))

    def ind_sub(m):
        a = (float(m.group(1)), float(m.group(2)))
        b = (float(m.group(3)), float(m.group(4)))
        orient = "h" if abs(a[1] - b[1]) < 0.06 else "v"
        return _d_of(inductor(((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0), orient)[0])
    svg = ind.sub(ind_sub, svg)

    for cm in list(_CIRCLE_RE.finditer(svg)):
        cx, cy, r = float(cm.group(1)), float(cm.group(2)), float(cm.group(3))
        if abs(r - SRC_R) < 0.01 or not _OLD_SRC_R_MIN <= r <= _OLD_SRC_R_MAX:
            continue
        if any(abs(float(t.group(1)) - cx) < r and abs(float(t.group(2)) - 6.0 - cy) < r
               for t in _TEXT_RE.finditer(svg)):
            continue                                   # 글자가 든 동그라미 — 계기·기관이지 전원이 아니다
        stroke = re.search(r"stroke='([^']*)'", cm.group(0)).group(1)
        kind, side, down, drop = None, "left", False, []
        inner = [(pm.group(0), pm.group(1)) for pm in _PATH_RE.finditer(svg)]
        inner += [(lm.group(0), "M%s %s L%s %s" % lm.groups()) for lm in re.finditer(
            r"<line x1='(%s)' y1='(%s)' x2='(%s)' y2='(%s)'[^>]*/>" % ((_NUM,) * 4), svg)]
        for el, d in inner:                        # 동그라미 안 화살표(자루·촉) — path·line 둘 다
            pts = [(float(a), float(b)) for a, b in
                   zip(re.findall(_NUM, d)[0::2], re.findall(_NUM, d)[1::2])]
            if pts and all(math.hypot(x - cx, y - cy) <= r - 1.0 for x, y in pts):
                drop.append(el)
                kind = "i"
                if "Z" in d:                       # 방향은 촉(닫힌 삼각형)의 무게중심이 정한다 — 자루 끝이 아니라
                    down = down or sum(p[1] for p in pts) / len(pts) > cy
        if kind is None:
            for tm in _TEXT_RE.finditer(svg):
                x, y, s = float(tm.group(1)), float(tm.group(2)), tm.group(4)
                if s in ("+", "−") and r <= abs(x - cx) <= r + _OLD_REACH_PAD and abs(y - cy) < r:
                    drop.append(tm.group(0))
                    kind, side = "v", ("left" if x < cx else "right")
                    down = down or (s == "+" and y > cy)
        if kind is None:                             # 표지 없는 전원(뜻을 말로 주는 그림) — 크기만 바꾼다
            svg = svg.replace(cm.group(0), re.sub(r"r='%s'" % re.escape(cm.group(3)),
                                                  "r='%.2f'" % SRC_R, cm.group(0), count=1), 1)
            notes.append("표지 없는 전원 (%.0f, %.0f) — 반지름만 바꿈(리드는 그대로)" % (cx, cy))
            continue
        for el in drop:
            svg = svg.replace(el, "", 1)
        # 극점에 닿은 도선: 세로면 리드(끝을 새 극점으로), 가로면 E43 「끝이 꺾인 도선에 닿음」
        leads, rails = {}, {}
        for pm in list(_PATH_RE.finditer(svg)):
            pts = _ml_points(pm.group(1))
            if not pts:
                continue
            for i, p in enumerate(pts):
                for sgn in (-1.0, 1.0):
                    if not _same(p, (cx, cy + sgn * r)):
                        continue
                    nb = pts[i - 1] if i > 0 else pts[i + 1] if len(pts) > 1 else None
                    if nb is not None and abs(nb[0] - cx) < 0.06:
                        leads[sgn] = (pm.group(0), i, nb)
                    elif nb is not None:
                        rails[sgn] = p[1]
        ncy = cy
        if len(rails) == 1 and len(leads) == 1:
            rail_y, far = next(iter(rails.values())), next(iter(leads.values()))[2]
            ncy = (far[1] + rail_y) / 2.0
            notes.append("전원 (%.0f, %.0f) 끝이 가로 도선에 닿음 → 세로 구간 가운데 y=%.1f 로" % (cx, cy, ncy))
        elif rails:
            notes.append("전원 (%.0f, %.0f) 양 끝이 가로 도선 — 크기만 바꿈(손으로)" % (cx, cy))
        for sgn, (el, i, _nb) in leads.items():
            pts = _ml_points(_d_of(el))
            pts[i] = (cx, ncy + sgn * SRC_R)
            new = el.replace(_d_of(el), "M" + " L".join("%.2f %.2f" % p for p in pts), 1)
            svg = svg.replace(el, new, 1)
        extra = ""
        for sgn, rail_y in rails.items():
            extra += wire([(cx, ncy + sgn * SRC_R), (cx, rail_y)], color=stroke)
        if ncy != cy:                              # 곁 글자(값·이름)를 전원과 같이 옮긴다
            def move(tm):
                x, y = float(tm.group(1)), float(tm.group(2))
                if abs(x - cx) <= 90.0 and abs(y - cy) <= 30.0:
                    return "<text x='%s' y='%.2f'%s>%s</text>" % (tm.group(1), y + ncy - cy,
                                                                   tm.group(3), tm.group(4))
                return tm.group(0)
            svg = _TEXT_RE.sub(move, svg)
        new_src = source((cx, ncy), kind, color=stroke, side=side, down=down)[0]
        svg = svg.replace(cm.group(0), new_src + extra, 1)
    return svg, notes


# 라벨–소자 거리(규격 「근접성 위계」 · E10·E13·E14·E42). 소자 가장자리에서 라벨 상자까지 0.6em — 사용자 [발화 생략] 한 장으로 확정할 때까지 가안(워크오더 (40) 세션 3 행). 이보다 멀고 이 배수 안이면 당긴다.
# 당기는 범위 상한 2.3em: 첫 실행(전전 ch01)에서 소자 라벨은 2.2em(Rₛ) 까지였고, 그 밖(2.5~3.3em)은 화살표·치수선·고리
# 이름처럼 대상이 소자가 아닌 글자였다. 0.15em 은 반올림 잡음 — 이만큼도 안 먼 라벨은 안 건드린다.
LABEL_CLEAR_EM, LABEL_PULL_MAX_EM, LABEL_PULL_MIN_EXCESS_EM = 0.6, 2.3, 0.15
# 전원 중심에서 이름·값 라벨 끝까지 — 반지름 + 테두리 반굵기 1 + 위 0.6em. 부호는 반대쪽이라 사이에 아무것도 없다.
SRC_LABEL_REACH = SRC_R + 1.0 + LABEL_CLEAR_EM * LABEL_SIZE
_ELEM_TEXT_RE = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)


def _lint_count(s):
    """빌드 신고 수(경고 포함) — 위아래 여백(F7·세로 균형)은 뺀다: 글자를 옮기면 여백이 바뀌는 것은 당연하고
    viewBox 는 뒤에 `fix_figure_vertical_balance` 가 맞춘다."""
    from buildlib.checks_svg import check_figure_lint, check_svg
    errors, warnings = [], []
    check_svg("f", s, errors, warnings, layout_strict=True, halo_gap_strict=True, clearance_strict=True)
    check_figure_lint("f", s, errors, warnings, strict=True, geometry_strict=True)
    return sum(1 for m in errors + warnings if "F7" not in m and "세로 균형" not in m)


def flip_polarity(svg):
    """전압원 극성 부호가 이름·값 라벨과 같은 쪽에 있으면 반대쪽으로 비춘다. (새 svg, 알림).

    잰 것: 반지름 `SRC_R` 동그라미 곁 「+」「−」(가로 `_OLD_REACH_PAD` 안)와, 그 부호보다 바깥의 같은 쪽 글자
    (가로 120 · 세로 30 안). 반대쪽에 이미 글자가 있거나 비춘 뒤 빌드 신고가 늘면 안 비춘다.
    못 보는 것: 가로로 누운 전원 · 반대쪽 빈자리가 보기에 맞는가(렌더는 사람).
    """
    notes = []
    for cm in list(_CIRCLE_RE.finditer(svg)):
        cx, cy, r = float(cm.group(1)), float(cm.group(2)), float(cm.group(3))
        if abs(r - SRC_R) > 0.01:
            continue
        texts = [(tm.group(0), float(tm.group(1)), float(tm.group(2)), re.sub(r"<[^>]+>", "", tm.group(4)).strip())
                 for tm in _TEXT_RE.finditer(svg)]
        signs = [t for t in texts if t[3] in ("+", "−") and r <= abs(t[1] - cx) <= r + _OLD_REACH_PAD
                 and abs(t[2] - 6.0 - cy) < r]
        if len(signs) != 2 or (signs[0][1] - cx) * (signs[1][1] - cx) <= 0:
            continue
        side = 1.0 if signs[0][1] > cx else -1.0
        reach = max(abs(t[1] - cx) for t in signs)
        near = [t for t in texts if t not in signs and abs(t[2] - 6.0 - cy) <= 30.0]
        mine = [t for t in near if reach < (t[1] - cx) * side <= 120.0]
        other = [t for t in near if 0.0 < (t[1] - cx) * -side <= r + _OLD_REACH_PAD + 20.0]
        if not mine or other:
            continue
        trial = svg
        for el, x, _y, _s in signs:
            trial = trial.replace(el, _set_num_attr(el, "x", 2.0 * cx - x), 1)
        if _lint_count(trial) > _lint_count(svg):
            notes.append("전원 (%.0f, %.0f) 극성 부호 — 반대쪽으로 비추면 신고가 늘어 안 옮김(사람)" % (cx, cy))
            continue
        svg = trial
        notes.append("전원 (%.0f, %.0f) 극성 부호를 라벨 반대쪽으로" % (cx, cy))
    return svg, notes


def _set_num_attr(el, name, value):
    return re.sub(r"(\s%s=')(%s)(')" % (name, _NUM), lambda m: "%s%.2f%s" % (m.group(1), value, m.group(3)),
                  el, count=1)


def _label_texts(svg):
    """굵지 않고 변환 없는 글자마다 {x, y, fs, anchor, s, raw, el, box}."""
    from buildlib.checks_svg import _text_bbox
    texts = []
    for m in _ELEM_TEXT_RE.finditer(svg):
        a = m.group(1)
        try:
            x, y = float(re.search(r"\sx='(%s)'" % _NUM, a).group(1)), float(re.search(r"\sy='(%s)'" % _NUM, a).group(1))
        except AttributeError:
            continue
        fs = re.search(r"font-size='(%s)'" % _NUM, a)
        anchor = re.search(r"text-anchor='(\w+)'", a)
        s = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not s or "transform" in a or "font-weight" in a:
            continue
        it = {"x": x, "y": y, "fs": float(fs.group(1)) if fs else LABEL_SIZE,
              "anchor": anchor.group(1) if anchor else "start", "s": s, "raw": m.group(2), "el": m.group(0)}
        it["box"] = _text_bbox(it)
        texts.append(it)
    return texts


def split_stacks(svg):
    """가로 저항 한쪽에 쌓인 「기호 · 값」 두 줄을 저항 위아래로 가른다 — 값 줄을 반대쪽 0.6em 로. (새 svg, 알림).

    왜: 두 줄을 한쪽에 쌓으면 바깥 줄(기호)이 소자에서 1.9em — 근접성 상한 1.0em 을 넘는다(2026-09-25 ch91).
    잰 것: 가운데 정렬로 저항 몸통 위(또는 아래) 3em 안에 쌓인 글자가 정확히 둘 · 「숫자+단위」 줄 하나(값)와 아닌 줄 하나(기호) ·
    반대쪽 3em 안에 글자 없음. 옮긴 뒤 다른 글자와 0.5em 안이 되거나 빌드 신고가 늘면 안 옮긴다.
    못 보는 것: 세로 저항(옆에 쌓인 두 줄은 둘 다 소자에 가깝다) · 반대쪽이 보기에 맞는가(렌더는 사람).
    """
    from buildlib.checks_svg import _chains, _zigzags
    notes = []
    for axis, body, _pitch, p0, _p1 in _zigzags(_chains(svg)):
        if axis != "h":
            continue
        texts = _label_texts(svg)
        mid = (p0[0] + _p1[0]) / 2.0
        top, bot = p0[1] - RES_AMP, p0[1] + RES_AMP

        def near(t, above):
            b = t["box"]
            if t["anchor"] != "middle" or abs(t["x"] - mid) > 0.6:
                return False
            return (0 <= top - b[3] <= 3.0 * t["fs"]) if above else (0 <= b[1] - bot <= 3.0 * t["fs"])
        for above in (True, False):
            stack = [t for t in texts if near(t, above)]
            if len(stack) != 2 or any(near(t, not above) for t in texts):
                continue
            vals = [t for t in stack if re.search(r"\d\s*[kmMμnp]?(?:Ω|V|A|F|H|W|°)", t["s"])]   # 첨자 숫자(R1)는 값이 아니다
            if len(vals) != 1:
                continue
            val = vals[0]
            clear = LABEL_CLEAR_EM * val["fs"]
            b = val["box"]
            dy = (bot + clear - b[1]) if above else (top - clear - b[3])
            nb = (b[0], b[1] + dy, b[2], b[3] + dy)
            if any(u is not val and u["box"][0] < nb[2] + 0.5 * u["fs"] and nb[0] < u["box"][2] + 0.5 * u["fs"]
                   and u["box"][1] < nb[3] + 0.5 * u["fs"] and nb[1] < u["box"][3] + 0.5 * u["fs"] for u in texts):
                notes.append("저항 (%.0f, %.0f) 값 %r — 반대쪽에 글자가 있어 안 가름(사람)" % (mid, p0[1], val["s"]))
                continue
            trial = svg.replace(val["el"], _set_num_attr(val["el"], "y", val["y"] + dy), 1)
            if _lint_count(trial) > _lint_count(svg):
                notes.append("저항 (%.0f, %.0f) 값 %r — 가르면 신고가 늘어 안 가름(사람)" % (mid, p0[1], val["s"]))
                continue
            svg = trial
            notes.append("저항 (%.0f, %.0f) 기호·값 두 줄을 위아래로 가름" % (mid, p0[1]))
    return svg, notes


def pull_labels(svg):
    """회로 소자(저항 지그재그·전원 동그라미) 곁 라벨을 소자 가장자리에서 `LABEL_CLEAR_EM` 로 당긴다. (새 svg, 알림).

    잰 것: 라벨 상자(`checks_svg._text_bbox`)와 소자 상자(지그재그 몸통 ± 진폭 · 동그라미 + 극성 부호)의 틈 —
    세로 소자는 가로로, 가로 소자는 세로로 잰다. 같은 x·같은 정렬로 쌓인 라벨(기호 + 값)은 함께 옮긴다.
    옮긴 뒤 다른 도선·글자와 0.5em 안이 되면 안 옮기고 알린다.
    못 보는 것: 화살표·노드 점 라벨 · 가로로 누운 전원 · 소자 사이에 낀 라벨이 어느 소자 것인가(가까운 쪽으로 본다).
    """
    from buildlib.checks_svg import _chains, _zigzags
    texts = _label_texts(svg)
    chains = _chains(svg)
    parts = []                                         # (축, 상자)
    for axis, body, _pitch, p0, p1 in _zigzags(chains):
        if axis == "v":
            ys = sorted((p0[1], p1[1]))
            mid = (ys[0] + ys[1]) / 2.0
            parts.append(("v", (p0[0] - RES_AMP, mid - body / 2.0, p0[0] + RES_AMP, mid + body / 2.0)))
        else:
            xs = sorted((p0[0], p1[0]))
            mid = (xs[0] + xs[1]) / 2.0
            parts.append(("h", (mid - body / 2.0, p0[1] - RES_AMP, mid + body / 2.0, p0[1] + RES_AMP)))
    for cm in _CIRCLE_RE.finditer(svg):
        cx, cy, r = float(cm.group(1)), float(cm.group(2)), float(cm.group(3))
        if not _OLD_SRC_R_MIN <= r <= _OLD_SRC_R_MAX:
            continue
        box = [cx - r, cy - r, cx + r, cy + r]
        for t in texts:                                # 극성 부호는 전원의 일부다
            if t["s"] in ("+", "−") and abs(t["x"] - cx) <= r + _OLD_REACH_PAD and abs(t["y"] - cy) < r + 6:
                b = t["box"]
                box = [min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3])]
        parts.append(("v", tuple(box)))

    def gap(axis, pb, tb):
        """소자 옆(축과 직각) 틈 — 옆에 있지 않으면 None."""
        if axis == "v":
            if tb[3] < pb[1] or tb[1] > pb[3]:
                return None
            return (tb[0] - pb[2], 1.0) if tb[0] >= pb[2] - 0.5 else (pb[0] - tb[2], -1.0) if tb[2] <= pb[0] + 0.5 else None
        if tb[2] < pb[0] or tb[0] > pb[2]:
            return None
        return (tb[1] - pb[3], 1.0) if tb[1] >= pb[3] - 0.5 else (pb[1] - tb[3], -1.0) if tb[3] <= pb[1] + 0.5 else None

    notes, done = [], set()
    base = _lint_count(svg)
    for i, t in enumerate(texts):
        if i in done or t["s"] in ("+", "−"):
            continue
        best = None
        for axis, pb in parts:
            g = gap(axis, pb, t["box"])
            if g and (best is None or g[0] < best[0]):
                best = (g[0], g[1], axis, pb)
        if best is None:
            continue
        g, side, axis, pb = best
        want = LABEL_CLEAR_EM * t["fs"]
        if g <= want + LABEL_PULL_MIN_EXCESS_EM * t["fs"] or g > LABEL_PULL_MAX_EM * t["fs"]:
            continue
        if re.search(r"[가-힣]", t["s"]):
            continue                                   # 한글 글자는 설명·영역 이름이다 — 소자 이름표가 아니다
        # 쌓인 짝(가로 옆 라벨: 같은 x·정렬로 위아래 1.6em 안 · 위아래 라벨: 같은 x 로 쌓임)
        group = [j for j, u in enumerate(texts) if j not in done and u["s"] not in ("+", "−")
                 and abs(u["x"] - t["x"]) < 0.6 and u["anchor"] == t["anchor"] and abs(u["y"] - t["y"]) <= 1.6 * t["fs"]]
        if axis == "h":                                 # 위아래 라벨 묶음은 소자에서 먼 쪽까지 같이 민다
            group = [j for j in group if gap(axis, pb, texts[j]["box"])]
        d = (g - want) * -side
        dx, dy = (d, 0.0) if axis == "v" else (0.0, d)
        boxes = [tuple(b + o for b, o in zip(texts[j]["box"], (dx, dy, dx, dy))) for j in group]
        clear = 0.5 * t["fs"]
        hit = False
        for pts in chains:                              # 옮긴 상자가 다른 선에 0.5em 안으로 들어가나
            for p, q in zip(pts, pts[1:]):
                for b in boxes:
                    lo_x, hi_x = min(p[0], q[0]), max(p[0], q[0])
                    lo_y, hi_y = min(p[1], q[1]), max(p[1], q[1])
                    if (lo_x < b[2] + clear and hi_x > b[0] - clear and lo_y < b[3] + clear and hi_y > b[1] - clear):
                        inside_part = (pb[0] - 1 <= lo_x and hi_x <= pb[2] + 1 and pb[1] - 1 <= lo_y and hi_y <= pb[3] + 1)
                        if not inside_part:
                            hit = True
        for k, u in enumerate(texts):
            if k in group:
                continue
            for b in boxes:
                ub = u["box"]
                if ub[0] < b[2] + clear and b[0] < ub[2] + clear and ub[1] < b[3] + clear and b[1] < ub[3] + clear:
                    hit = True
        trial = svg
        if not hit:                                     # 빌드 검사로 한 번 더 — 옮긴 뒤 신고가 늘면 안 옮긴다
            for j in group:
                u = texts[j]
                new = _set_num_attr(u["el"], "x", u["x"] + dx) if dx else _set_num_attr(u["el"], "y", u["y"] + dy)
                trial = trial.replace(u["el"], new, 1)
            hit = _lint_count(trial) > base
        if hit:
            notes.append("라벨 %r 틈 %.1fem — 당기면 다른 선·글자와 붙어 안 옮김(사람)" % (t["s"], g / t["fs"]))
            continue
        svg = trial
        done.update(group)
        notes.append("라벨 %s 틈 %.1f → %.1fem" % ("·".join(texts[j]["s"] for j in group), g / t["fs"], LABEL_CLEAR_EM))
    return svg, notes


def restamp_chapter(path, fig_id=None, apply=False, note="", labels=False):
    """장 JSON 의 삽화마다 `restamp_svg` — 바뀐 그림 id 와 알림을 찍고, `apply` 면 쓰고 주인 항목에 사유를 단다."""
    import copy
    import json
    from pathlib import Path
    import audit_figure_balance as A
    import set_change_notes as SCN
    from buildlib.jsontext import write_chapter
    from fix_label_proximity import owners_of
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    before = copy.deepcopy(data)
    owners, touched, changed = owners_of(data), [], 0
    for diagram in A.iter_diagrams(data):
        fid = diagram.get("id") or "?"
        if fig_id and fid != fig_id or "svg" not in diagram:
            continue
        for track in (diagram.get("motion") or {}).get("tracks") or []:   # morph 점 목록도 같은 저항이다
            for key in ("points_from", "points_to"):
                pts = track.get(key)
                new_pts = _rezig([tuple(p) for p in pts]) if isinstance(pts, list) else None
                if new_pts:
                    track[key] = [list(p) for p in new_pts]
        new, notes = restamp_svg(diagram["svg"])
        if labels and not diagram.get("motion"):      # 움직이는 그림은 빌드가 프레임을 펴서 잰다 — 여기서 못 본다
            new, more = flip_polarity(new)
            notes += more
            new, more = split_stacks(new)
            notes += more
            new, more = pull_labels(new)
            notes += more
            if new != diagram["svg"]:                 # 당긴 라벨이 바꾼 위아래 여백을 규칙 목표(9)로 줄인다
                from fix_figure_vertical_balance import plan_line
                new = plan_line(new, 9.0)[0]
        for n in notes:
            print("  %s %s — %s" % (Path(path).stem, fid, n))
        if new != diagram["svg"]:
            changed += 1
            print("  [다시 찍음] %s %s" % (Path(path).stem, fid))
            diagram["svg"] = new
            owner = owners.get(id(diagram))
            if owner and owner not in touched:
                touched.append(owner)
    print("합계 — 다시 찍은 삽화 %d" % changed)
    if apply and data != before:
        status, why = write_chapter(str(path), before, data)
        if status == "skipped":
            # 움직이는 그림의 morph 점 목록은 길이가 바뀐다(점 11 → 13) — 표기 보존 기록기가 못 쓰는 유일한 꼴이라
            # 생성기(`gen_ee_problem_circuits`)와 같은 json.dump 로 쓴다. 다른 칸의 줄바꿈 꼴이 바뀔 수 있다.
            print("  [다시 씀] 표기 보존 기록 실패(" + str(why) + ") — json.dump 로 씀")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
        if touched:
            SCN.run_chapter(str(path), {oid: note for oid in touched}, True, True)
    return 0


def audit(root, verbose=False):
    """`root`(과목 폴더 또는 data) 아래 장마다 자 `circuit_part_ratio_issues` 건수 — 소급 후보 세기.
    분모(본 장·삽화 수)를 함께 찍는다."""
    import glob
    import json
    import os
    import audit_figure_balance as A
    from buildlib.checks_svg import boundary_dashed_issues, circuit_part_ratio_issues
    paths = sorted(glob.glob(os.path.join(root, "ch*.json")) or glob.glob(os.path.join(root, "*", "ch*.json")))
    n_fig = total = 0
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        hits = []
        for d in A.iter_diagrams(data):
            if "svg" not in d:
                continue
            n_fig += 1
            hits += circuit_part_ratio_issues(d.get("id") or "?", d["svg"])
            hits += boundary_dashed_issues(d.get("id") or "?", d["svg"])
        total += len(hits)
        if hits:
            figs = len({h.split(":")[0] for h in hits})
            print("  %s — 신고 %d · 그림 %d" % (p, len(hits), figs))
            for h in hits if verbose else []:
                print("      " + h)
    print("합계 — 장 %d · 삽화 %d · 신고 %d" % (len(paths), n_fig, total))
    return 0


def _pair(text):
    x, y = text.split(",")
    return (float(x), float(y))


def main():
    ap = argparse.ArgumentParser(description="회로도 조각을 찍는다")
    sub = ap.add_subparsers(dest="what", required=True)

    p = sub.add_parser("wire")
    p.add_argument("--points", nargs="+", required=True)
    p.add_argument("--color", default=WIRE_COLOR)
    p.add_argument("--width", type=float, default=WIRE_WIDTH)

    for name in ("resistor", "capacitor", "battery", "polarity"):
        p = sub.add_parser(name)
        p.add_argument("--at", required=True)
        p.add_argument("--orient", default="h")
        p.add_argument("--side", default="left", choices=("left", "right"))
        p.add_argument("--color", default=WIRE_COLOR)
        p.add_argument("--label")
        p.add_argument("--sub", dest="subscript")
        if name == "resistor":
            p.add_argument("--scale", type=float, default=1.0)
        if name == "battery":
            p.add_argument("--flip", action="store_true")

    p = sub.add_parser("source")
    p.add_argument("--at", required=True)
    p.add_argument("--kind", default="v")
    p.add_argument("--side", default="left", choices=("left", "right"))
    p.add_argument("--color", default=WIRE_COLOR)
    p.add_argument("--label")
    p.add_argument("--sub", dest="subscript")

    p = sub.add_parser("node-dot")
    p.add_argument("--at", required=True)
    p.add_argument("--color", default=WIRE_COLOR)

    p = sub.add_parser("restamp")
    p.add_argument("chapter")
    p.add_argument("--id", dest="fig_id")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--note", default="")
    p.add_argument("--labels", action="store_true", help="소자 곁 라벨도 LABEL_CLEAR_EM 로 당긴다")

    p = sub.add_parser("audit")
    p.add_argument("root")
    p.add_argument("--verbose", action="store_true")

    p = sub.add_parser("arrow")
    p.add_argument("--from", dest="frm", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--color", default=WIRE_COLOR)
    p.add_argument("--label")
    p.add_argument("--sub", dest="subscript")

    args = ap.parse_args()
    if args.what == "restamp":
        if args.apply and (not args.note.strip() or "_" in args.note):
            raise SystemExit("--apply 에는 밑줄 없는 --note 가 필요하다(주인 항목 changeNote)")
        return restamp_chapter(args.chapter, args.fig_id, args.apply, args.note, args.labels)
    if args.what == "audit":
        return audit(args.root, args.verbose)
    ends = None
    if args.what == "wire":
        svg = wire([_pair(t) for t in args.points], color=args.color, width=args.width)
    elif args.what == "resistor":
        svg, ends = resistor(_pair(args.at), args.orient, color=args.color, scale=args.scale)
    elif args.what == "battery":
        svg, ends = battery(_pair(args.at), args.orient, color=args.color, flip=args.flip)
    elif args.what == "capacitor":
        svg, ends = capacitor(_pair(args.at), args.orient, color=args.color)
    elif args.what == "source":
        svg, ends = source(_pair(args.at), args.kind, color=args.color, side=args.side)
    elif args.what == "node-dot":
        svg = node_dot(_pair(args.at), color=args.color)
    elif args.what == "arrow":
        svg = arrow(_pair(args.frm), _pair(args.to), color=args.color)
    else:
        svg = polarity(_pair(args.at), args.orient, side=args.side)

    print(svg)
    if ends:
        print("# 리드 끝: %.2f %.2f  ·  %.2f %.2f" % (ends[0][0], ends[0][1], ends[1][0], ends[1][1]))
    if getattr(args, "label", None):
        at = _pair(args.at) if args.what != "arrow" else _pair(args.to)
        print("# 라벨 자리(부품 중심에서 위로 %.0f): %s"
              % (LABEL_GAP, label_text(at[0], at[1] - LABEL_GAP - RES_AMP, args.label,
                                       args.subscript)))


if __name__ == "__main__":
    main()
