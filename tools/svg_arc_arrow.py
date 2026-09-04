# -*- coding: utf-8 -*-
"""삽화에 넣을 **각도 호 + 접선 화살촉** SVG 조각을 찍어 준다 (붙여넣기용).

왜 있나 — 회전(축일 기기·사이클·모멘트)은 글자 `↻` 를 쓰지 않고 **원호 + 채운 화살촉**으로
그린다(§4 「시각 문법」). 그런데 화살촉을 손으로 붙이면 **끝점은 맞는데 방향이 호를 거스르는**
결함이 난다 — 2026-07-25 에 실제로 그렇게 열렸고, 끝점만 보던 검사는 그것을 통과시켰다.
접선 방향은 눈으로 잡을 수 없고 삼각함수로만 나온다(AGENTS 「좌표는 어림하지 말고 자를 먼저」).

기하는 `buildlib.checks_svg.svg_arc_arrow` 가 정본이고, 그 출력은 같은 파일의
`arc_arrowhead_issues`(= 빌드가 쓰는 자)가 그대로 통과시켜야 한다 — 회귀가 그것을 잠근다.

    python tools/svg_arc_arrow.py --cx 250 --cy 160 --r 60 --from 200 --to 340 --vb 500
    python tools/svg_arc_arrow.py --cx 250 --cy 160 --r 60 --from 340 --to 200 --vb 500

각은 **도(°)** 이고 SVG 좌표계(y 가 아래로 증가)다 — 0°가 오른쪽, 90°가 **아래쪽**이다.
`--from` 보다 `--to` 가 크면 시계 방향(화면 기준)으로 돈다.

★ **`--to` 는 화살촉 «꼭짓점»이 닿는 각이다**(2026-08-25 에 뜻을 바꿨다). 호는 그보다 화살촉
  길이만큼 물러난 자리에서 끝난다. 옛 판은 호를 `--to` 까지 긋고 그 끝에 밑변을 놓아
  **꼭짓점이 기준선을 뚫고 나왔다**(동역학 `fig-ch16-q01`·`q02`·`q06`). 경위는
  `buildlib.checks_svg.svg_arc_arrow` 독스트링이 정본이다.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_svg import svg_arc_arrow                              # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="삽화용 각도 호 + 접선 화살촉 SVG 조각 생성")
    ap.add_argument("--cx", type=float, required=True)
    ap.add_argument("--cy", type=float, required=True)
    ap.add_argument("--r", type=float, required=True)
    ap.add_argument("--from", dest="a0", type=float, required=True, help="시작 각(°)")
    ap.add_argument("--to", dest="a1", type=float, required=True,
                    help="끝 각(°) — 화살촉 **꼭짓점**이 닿는 각(호는 그보다 물러나 끝난다)")
    ap.add_argument("--vb", type=float, required=True, help="그 삽화의 viewBox 폭")
    ap.add_argument("--stroke", default="#3a4252")
    ap.add_argument("--width", type=float, default=2.0, help="호의 굵기(형상선 2~2.5)")
    args = ap.parse_args()

    out, info = svg_arc_arrow(args.cx, args.cy, args.r, args.a0, args.a1,
                              args.vb, args.stroke, args.width)
    print(out)
    print("[기하] 시작 (%.2f, %.2f) → 호 끝=밑변 (%.2f, %.2f) → 꼭짓점 (%.2f, %.2f) · "
          "접선 (%.3f, %.3f) · 화살촉 %.2f px · 물린 각 %.2f°"
          % (info["start"][0], info["start"][1], info["end"][0], info["end"][1],
             info["tip"][0], info["tip"][1],
             info["tangent"][0], info["tangent"][1], info["head_len"], info["pullback_deg"]))
    print("       **꼭짓점이 `--to` 각에 정확히 놓인다** — 호는 그만큼 물러나 끝나고 거기에 밑변이 붙는다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
