# -*- coding: utf-8 -*-
"""삽화에 넣을 **분수 SVG 조각**을 찍어 준다 (붙여넣기용).

왜 있나 — 분수를 텍스트(`P/ρ`)로 쓰는 부류가 세 번 재발했고(인박스 W-9·V-11·C9),
매번 "고쳐라"는 알았지만 **어떻게 그리는지가 삽화마다 새로 정해졌다.**
좌표를 손으로 잡으면 분수선 굵기·간격·중심선이 갈라지고, 그 갈라짐 자체가 다음 지적이 된다
("분수선과 등호가 같은 선상에 없어", 2026-07-28). 기하는 `buildlib.checks_svg` 가 정본이고
이 스크립트는 그것을 문자열로 찍기만 한다.

    python tools/svg_fraction.py --cx 195 --axis 70 --num "P" --den "ρ" --fs 13 \
        --fill "#8c4a22" --weight 700
    python tools/svg_fraction.py --line --x 430 --y 282 --fs 17.5 \
        --expr "θ = h + {V²/2} + gz"

`--line` 은 한 줄 수식 전체를 조판한다(`{분자/분모}` 가 분수 마커). `--y` 는 보통 글자의
baseline이고 분수선은 그보다 0.34em 위(수식 중심선)에 놓인다.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_svg import run_width, svg_fraction, svg_math_line   # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="삽화용 분수 SVG 조각 생성")
    ap.add_argument("--line", action="store_true", help="한 줄 수식 전체를 조판한다")
    ap.add_argument("--expr", default="", help="--line 용 수식. 분수는 {분자/분모}")
    ap.add_argument("--x", type=float, default=0.0, help="--line 의 기준 x")
    ap.add_argument("--y", type=float, default=0.0, help="--line 의 보통 글자 baseline")
    ap.add_argument("--anchor", default="middle", choices=("start", "middle", "end"))
    ap.add_argument("--cx", type=float, default=0.0, help="분수 하나의 중심 x")
    ap.add_argument("--axis", type=float, default=0.0, help="분수선(수식 중심선)의 y")
    ap.add_argument("--num", default="", help="분자")
    ap.add_argument("--den", default="", help="분모")
    ap.add_argument("--fs", type=float, required=True)
    ap.add_argument("--fill", default="#2c3a44")
    ap.add_argument("--weight", default="")
    args = ap.parse_args()

    weight = args.weight or None
    if args.line:
        if not args.expr:
            ap.error("--line 에는 --expr 가 필요하다")
        out = svg_math_line(args.x, args.y, args.expr, args.fs, args.fill, weight, args.anchor)
        print(out)
        print("[폭 참고] 마커를 뺀 글자 폭 %.2f" % run_width(args.expr, args.fs))
        return 0

    if not (args.num and args.den):
        ap.error("--num 과 --den 이 필요하다 (한 줄 수식은 --line)")
    out, width = svg_fraction(args.cx, args.axis, args.num, args.den, args.fs,
                              args.fill, weight)
    print(out)
    print("[폭] %.2f  → 분수선 x %.2f ~ %.2f / 글자 상자 y %.2f ~ %.2f"
          % (width, args.cx - width / 2, args.cx + width / 2,
             args.axis - 1.14 * args.fs, args.axis + 1.14 * args.fs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
