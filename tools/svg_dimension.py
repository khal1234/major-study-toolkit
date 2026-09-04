# -*- coding: utf-8 -*-
"""삽화에 넣을 **치수선 한 벌** SVG 조각을 찍어 준다 (붙여넣기용).

왜 있나 — `svg_fraction.py` 와 같은 이유다. 치수선 규격(간격 4px · 넘김 10px · 라벨 위치 ·
화살촉 비율)이 문서에만 있으면 삽화마다 손으로 좌표를 잡게 되고, **그 갈라짐 자체가 다음
지적이 된다**: *"스프링이랑 볼트랑 치수보조선 떨어진게 값이 달라"*(2026-07-31) ·
*"치수보조선 시작이나 끝점이 도형과 겹쳐 있으면 안 돼"*(2026-07-25) ·
*"`ℓ` 과 치수선 사이 여백 왜 이렇게 커"*(2026-08-13).

기하는 `buildlib.checks_svg.svg_dimension` 이 정본이고 이 스크립트는 문자열로 찍기만 한다.
**고치는 자와 그리는 자가 같은 상수를 쓴다** — 전수 교정은 `fix_dim_extension.py`·
`fix_dim_label_gap.py`, 새로 그리는 것은 여기다.

    python tools/svg_dimension.py --axis h --p1 180 --p2 340 --face 190 --line 232 \\
        --fs 15 --vb 500 --label "ℓ"
    python tools/svg_dimension.py --axis v --p1 70 --p2 190 --face 180 --line 138 \\
        --fs 15 --vb 500 --label "h"

`--face` 는 **재는 면이 있는 외형선**(가로 치수면 그 면의 y), `--line` 은 치수선이 놓일 자리다.
보조선은 외형선에서 간격만큼 띄워 시작하고 치수선을 넘김만큼 지나 끝난다 — 둘 다 규격값이라
인자로 받지 않는다(받으면 그 순간 삽화마다 갈린다).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_svg import svg_dimension                              # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="삽화용 치수선 한 벌 SVG 조각 생성")
    ap.add_argument("--axis", choices=("h", "v"), required=True,
                    help="h=가로 치수(보조선이 세로) · v=세로 치수")
    ap.add_argument("--p1", type=float, required=True, help="재는 첫 면 (가로면 x · 세로면 y)")
    ap.add_argument("--p2", type=float, required=True, help="재는 둘째 면")
    ap.add_argument("--face", type=float, required=True, help="그 면이 있는 외형선의 반대 축 좌표")
    ap.add_argument("--line", type=float, required=True, help="치수선이 놓일 자리")
    ap.add_argument("--fs", type=float, required=True, help="라벨 글자 크기(SVG px)")
    ap.add_argument("--vb", type=float, required=True, help="그 삽화의 viewBox 폭")
    ap.add_argument("--label", default="", help="치수 문자. 회전하지 않는다")
    ap.add_argument("--stroke", default="#3a4252")
    ap.add_argument("--fill", default="#2c3a44", help="라벨 색")
    args = ap.parse_args()

    out, info = svg_dimension(args.axis, args.p1, args.p2, args.face, args.line,
                              args.fs, args.vb, args.label, args.stroke, args.fill)
    print(out)
    print("[규격] 간격 %.2f · 넘김 %.2f · 화살촉 %.2f (SVG px · 배율 %.3f = viewBox %g / 612)"
          % (info["gap"], info["over"], info["head_len"], info["scale"], args.vb))
    print("       규격값은 화면 실효 px 가 정본이다 — `checks_content.DIM_GAP_SCREEN_PX`·"
          "`DIM_OVERSHOOT_SCREEN_PX`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
