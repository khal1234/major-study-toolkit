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
    python tools/svg_circuit.py source --at 60,120 --kind v --label V --sub s
    python tools/svg_circuit.py node-dot --at 220,60
    python tools/svg_circuit.py arrow --from 240,60 --to 300,60 --label i
    python tools/svg_circuit.py polarity --at 140,60 --orient h
"""
import argparse
import math
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

# 저항 한 개의 치수. 지그재그 마루 여섯이 표준 기호이고, 진폭은 몸통 길이의 약 1/5.5 다.
# 리드는 노드 점(반지름 4)이 겹치지 않을 만큼만 남긴다.
RES_BODY, RES_AMP, RES_LEAD = 44.0, 8.0, 10.0
# 커패시터 한 개의 치수. 판 둘이 마주 보는 것이 기호의 전부라, 판 길이를 저항 진폭(8)의
# 1.75 배로 잡아 「마주 본 두 판」이 지그재그와 안 헷갈린다. 간격 8 은 판 길이의 절반 아래라
# 좁아 보이고, 리드 28 을 더하면 발자국이 저항과 같은 64 가 된다.
CAP_HALF, CAP_GAP, CAP_LEAD = 14.0, 8.0, 28.0
CAP_PLATE_WIDTH = 3.0       # 판은 도선보다 굵다 — 「선」이 아니라 「판」으로 읽혀야 한다
SRC_R = 17.0                # 전원 동그라미. 저항 진폭의 두 배가 조금 넘어 나란히 놓아도 안 눌린다
NODE_R = 4.0                # 노드 점 — 선 굵기 2 의 두 배라 「점」으로 읽힌다
ARROW_HEAD, ARROW_HALF = 11.0, 4.5   # 전류 화살촉 — 다른 삽화의 화살촉과 같은 비례
LABEL_GAP = 15.0            # 부품 중심에서 라벨 중심까지(수직 방향)
# 전원 중심에서 극성 부호까지. 반지름 17 + 규격 여백 0.5em(8.5) + 글자 반너비 5 = 30.5 라
# 31 이면 동그라미 테두리에서 여백이 남는다.
POLARITY_REACH = 31.0


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


def resistor(at, orient, color=WIRE_COLOR):
    """지그재그 저항 한 개. (svg, 두 리드 끝) 을 낸다."""
    ux, uy = axes(orient)
    half = RES_BODY / 2.0
    pts = [(-half - RES_LEAD, 0.0), (-half, 0.0)]
    steps = 6
    for i in range(steps + 1):
        fx = -half + RES_BODY * (2 * i + 1) / (2.0 * steps + 2.0)
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


def source(at, kind, color=WIRE_COLOR, side="left"):
    """전원 한 개. `v` 는 극성 부호를 곁에 단 동그라미, `i` 는 화살표를 넣은 동그라미.

    ★ **부호를 동그라미 안에 넣지 않는다.** 규격의 글자-선 여백 0.5em 을 지키면 반지름 17
    안에 17px 글자 둘이 못 들어간다(2026-09-09 실측: 안에 넣었더니 F1 넷 · 경계 걸침 둘).
    `side` 로 왼쪽·오른쪽을 골라 라벨과 겹치지 않게 둔다.
    """
    cx, cy = at
    parts = ["<circle cx='%.2f' cy='%.2f' r='%.2f' fill='%s' stroke='%s' stroke-width='%.1f'/>"
             % (cx, cy, SRC_R, BODY_FILL, color, WIRE_WIDTH)]
    if kind == "v":
        sx = cx - POLARITY_REACH if side == "left" else cx + POLARITY_REACH
        parts.append(label_text(sx, cy - 9.0, "+"))
        parts.append(label_text(sx, cy + 13.0, "−"))
    elif kind == "i":
        # ★ 동그라미 안의 화살표는 규격 둘에 동시에 끼인다 — 화살촉 **하한 8px** 과
        #   「꼬리는 촉의 1.5배 이상」. 반지름 17 안에서 둘을 다 채우는 자리가 촉 9 · 꼬리 14 다
        #   (2026-09-09: 촉을 비율로 잡아 7.2, 촉을 11 로 키우니 이번엔 꼬리가 짧다고 걸렸다).
        head_base, tip = cy - 4.0, cy - 13.0
        parts.append(wire([(cx, cy + 10.0), (cx, head_base)], color=color, width=1.8))
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

    for name in ("resistor", "capacitor", "polarity"):
        p = sub.add_parser(name)
        p.add_argument("--at", required=True)
        p.add_argument("--orient", default="h")
        p.add_argument("--side", default="left", choices=("left", "right"))
        p.add_argument("--color", default=WIRE_COLOR)
        p.add_argument("--label")
        p.add_argument("--sub", dest="subscript")

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

    p = sub.add_parser("arrow")
    p.add_argument("--from", dest="frm", required=True)
    p.add_argument("--to", required=True)
    p.add_argument("--color", default=WIRE_COLOR)
    p.add_argument("--label")
    p.add_argument("--sub", dest="subscript")

    args = ap.parse_args()
    ends = None
    if args.what == "wire":
        svg = wire([_pair(t) for t in args.points], color=args.color, width=args.width)
    elif args.what == "resistor":
        svg, ends = resistor(_pair(args.at), args.orient, color=args.color)
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
