# -*- coding: utf-8 -*-
"""삽화에 넣을 **등축(캐비닛) 3D 조각 SVG** 를 찍어 준다 (붙여넣기용).

왜 있나 — `docs/삽화-규격.md` 「3D(등축투영)를 쓰는 조건」이 *[발화 생략]* 라고 적어 두고도 **그 프리미티브가
없었다**(`iso_cuboid`·`iso_ellipse` 는 2026-08 에 이름만 생기고 아무도 안 불렀다).
기하는 `buildlib.checks_svg` 가 정본이고 이 스크립트는 문자열로 찍기만 한다 —
`svg_fan.py`·`svg_fraction.py` 와 같은 구조다.

    python tools/svg_iso.py tube --x 180 --y 130 --r 46 --depth 150
    python tools/svg_iso.py box  --x 120 --y 90  --w 150 --depth 90 --h 110

**앞단면은 찌그러지지 않는다** — 원단면은 참원, 사각단면은 참직사각형이고 깊이만
오른쪽 위로 물러난다. 3D 조건 셋이 전부 「단면」에 걸려 있어 단면을 참모양으로 두는 쪽이
읽기 쉽기 때문이다. 색은 **단면·유체·벽을 서로 다르게** 준다(규격 「색으로 구분한다」).

사람이 판정하는 자리: **무엇을 어디에 놓을지**와 **깊이를 얼마로 줄지**. 좌표는 안 잡는다.
잠금 `tools/test_checks.py::test_iso_primitives_pass_their_own_rulers`.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_svg import (                                       # noqa: E402
    ISO_DEPTH_RISE, ISO_SECTION_SQUASH, iso_cuboid_svg, iso_pipe, iso_pipe_svg,
    iso_tube, iso_tube_svg,
)


def main():
    ap = argparse.ArgumentParser(description="삽화용 등축 3D 조각 생성 (출력만 한다)")
    sub = ap.add_subparsers(dest="shape", required=True)

    t = sub.add_parser("tube", help="누운 원통 — 관·덕트·검사체적")
    t.add_argument("--x", type=float, required=True, help="앞단면 중심 x")
    t.add_argument("--y", type=float, required=True, help="앞단면 중심 y")
    t.add_argument("--r", type=float, required=True)
    t.add_argument("--depth", type=float, required=True, help="뒤로 물러나는 길이")
    t.add_argument("--wall", default="#cbd5e0", help="벽 색")
    t.add_argument("--face", default="#eef1f5", help="앞단면(단면적 A) 색")

    p = sub.add_parser("pipe", help="누운 관 — 분기·노즐처럼 방향이 여럿인 배관")
    p.add_argument("--x1", type=float, required=True)
    p.add_argument("--y1", type=float, required=True)
    p.add_argument("--x2", type=float, required=True)
    p.add_argument("--y2", type=float, required=True)
    p.add_argument("--r", type=float, required=True)
    p.add_argument("--wall", default="#cbd5e0")
    p.add_argument("--face", default="#eef1f5")
    p.add_argument("--no-near-cap", dest="near_cap", action="store_false")
    p.add_argument("--no-far-cap", dest="far_cap", action="store_false")
    p.add_argument("--far-fill", dest="far_fill", default=None,
                   help="먼 단면 색 (기본은 벽 색)")

    b = sub.add_parser("box", help="직육면체 — 검사체적·경계이동일")
    b.add_argument("--x", type=float, required=True, help="앞면 왼쪽 위 x")
    b.add_argument("--y", type=float, required=True, help="앞면 왼쪽 위 y")
    b.add_argument("--w", type=float, required=True)
    b.add_argument("--depth", type=float, required=True)
    b.add_argument("--h", type=float, required=True)
    b.add_argument("--front", default="#eef1f5")
    b.add_argument("--top", default="#dbe3ea")
    b.add_argument("--side", default="#c7d2dc")

    a = ap.parse_args()
    if a.shape == "tube":
        print(iso_tube_svg(a.x, a.y, a.r, a.depth, wall=a.wall, face=a.face))
        g = iso_tube(a.x, a.y, a.r, a.depth)
        print("\n  앞단면 중심 (%.1f, %.1f) · 뒤단면 중심 (%.1f, %.1f) · 깊이 기울기 %.2f"
              % (g["near"][0], g["near"][1], g["far"][0], g["far"][1], ISO_DEPTH_RISE))
        print("  그리는 순서 뒤단면 → 몸통 → 앞단면 (바꾸면 관 속에 원이 하나 더 보인다)")
    elif a.shape == "pipe":
        print(iso_pipe_svg(a.x1, a.y1, a.x2, a.y2, a.r, wall=a.wall, face=a.face,
                           near_cap=a.near_cap, far_cap=a.far_cap, far_fill=a.far_fill))
        g = iso_pipe(a.x1, a.y1, a.x2, a.y2, a.r)
        print("\n  축 기울기 %.2f° · 단면 타원 단축/장축 %.2f (참등축 tan30°)"
              % (g["deg"], ISO_SECTION_SQUASH))
        print("  분기·합류는 이어지는 쪽 뚜껑을 `--no-near-cap`·`--no-far-cap` 으로 끈다")
    else:
        print(iso_cuboid_svg(a.x, a.y, a.w, a.depth, a.h,
                             front=a.front, top=a.top, side=a.side))
        print("\n  깊이 기울기 %.2f · 그리는 순서 top → side → front" % ISO_DEPTH_RISE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
