# -*- coding: utf-8 -*-
"""삽화에 넣을 **축류팬 SVG 조각**을 찍어 준다 (붙여넣기용).

왜 있나 — 사용자 지적(2026-08-04, 인박스 R-39):
*"q12 팬 일러 이상해. 이전에 팬 만든거 있잖아 일관되게 적용해줘."*
팬을 그릴 때마다 좌표를 새로 잡아서 삽화마다 다르게 생겼다(실측: 한쪽은 곡선 날개,
다른 쪽은 삼각형 날개에 허브 비율도 달랐다). 기하는 `buildlib.checks_svg` 가 정본이고
이 스크립트는 그것을 문자열로 찍기만 한다 — `svg_fraction.py` 와 같은 구조다.

    python tools/svg_fan.py --cx 240 --cy 138 --r 42
    python tools/svg_fan.py --cx 174 --cy 136 --r 33 --blades 3

찍어 준 조각의 `class='fan'` 과 `data-fan` 을 **지우지 말 것** — 빌드 C29 가 그 값으로 다시
찍어 데이터와 대조한다. 지우면 그 삽화만 조용히 정본 밖으로 빠진다.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_svg import (                                       # noqa: E402
    FAN_HUB_TIP_RATIO, FAN_ROOT_IN_HUB, fan_svg,
)


def main():
    ap = argparse.ArgumentParser(description="삽화용 축류팬 SVG 조각 생성 (출력만 한다)")
    ap.add_argument("--cx", type=float, required=True)
    ap.add_argument("--cy", type=float, required=True)
    ap.add_argument("--r", type=float, required=True, help="바깥 링 반지름")
    ap.add_argument("--blades", type=int, default=3)
    ap.add_argument("--fill", default="#4d7690")
    ap.add_argument("--paper", default="#f7f4ec", help="링 안쪽(배경) 색")
    ap.add_argument("--hub-fill", dest="hub_fill", default="#2c3a44")
    a = ap.parse_args()
    print(fan_svg(a.cx, a.cy, a.r, a.blades, a.fill, a.paper, a.hub_fill))
    hub = a.r * FAN_HUB_TIP_RATIO
    print("\n  허브 반지름 %.2f (허브/팁 %.3f) · 뿌리 현 반지름 %.2f · 그리기 순서 링→날개→허브"
          % (hub, FAN_HUB_TIP_RATIO, hub * FAN_ROOT_IN_HUB))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
