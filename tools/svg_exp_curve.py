# -*- coding: utf-8 -*-
"""삽화에 넣을 **1차 과도응답 곡선(지수)** SVG 조각을 찍어 준다 (붙여넣기용).

왜 있나 — RC·RL 과도응답은 이 과목에서 반복해 나오는 그림인데(4주차 커패시터 충·방전,
5주차 인덕터, 6주차 정류 회로의 평활), 지수 곡선은 **손으로 점을 찍으면 반드시 틀린다.**
「63퍼센트 지점」과 「출발점 접선이 최종값 선과 만나는 곳」은 둘 다 시정수 하나를 가리켜야
하는데, 어림한 곡선에서는 그 둘이 서로 다른 자리에 떨어진다 — 그러면 삽화가 본문과 다른
말을 하게 된다(AGENTS 「좌표는 어림하지 말고 자를 먼저」).

곡선은 둘 중 하나다(`--mode`):

    charge   v(t) = Vf (1 - exp(-t/tau))     0 에서 올라가 Vf 로 (충전)
    decay    v(t) = V0 exp(-t/tau)           V0 에서 내려와 0 으로 (방전)

    python tools/svg_exp_curve.py --mode charge --x0 90 --y0 300 --w 420 --h 150
    python tools/svg_exp_curve.py --mode decay  --x0 90 --y0 300 --w 420 --h 150 --span 5

찍어 주는 것 — 곡선 polyline · 시정수 눈금 x 좌표 · 63퍼센트(또는 37퍼센트) 지점 ·
출발점 접선의 두 끝점 · 최종값 수평선. **라벨 문구와 색은 사람이 정한다**(이 도구는 기하만).

★ 규격값을 인자로 받지 않는다 — `--span`(시정수 몇 배까지 그릴지)만 열어 둔다.
  기본 5 는 본문이 「사실상의 끝」으로 쓰는 값과 같아야 한다(그래야 그림과 글이 같은 말을 한다).
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SAMPLES = 60          # 폴리라인 점 수 — 60이면 5tau 구간에서 꺾임이 눈에 안 보인다


def curve_points(mode, x0, y0, w, h, span, samples=SAMPLES):
    """(polyline 문자열, [(t/tau, frac, x, y)…]) 를 돌려준다.

    frac 은 **화면 높이에 대한 비율**이다(charge 면 0→1, decay 면 1→0).
    """
    tau_px = w / float(span)
    pts, rows = [], []
    for i in range(samples + 1):
        tt = span * i / float(samples)
        if mode == "charge":
            frac = 1.0 - math.exp(-tt)
        else:
            frac = math.exp(-tt)
        x = x0 + tt * tau_px
        y = y0 - frac * h
        pts.append("%.1f,%.1f" % (x, y))
        rows.append((tt, frac, x, y))
    return " ".join(pts), rows


def main():
    ap = argparse.ArgumentParser(description="삽화용 1차 과도응답(지수) 곡선 SVG 조각 생성")
    ap.add_argument("--mode", choices=("charge", "decay"), required=True)
    ap.add_argument("--x0", type=float, required=True, help="원점 x(축이 만나는 자리)")
    ap.add_argument("--y0", type=float, required=True, help="원점 y(화면 좌표 — 아래가 크다)")
    ap.add_argument("--w", type=float, required=True, help="span×tau 가 차지할 가로 길이")
    ap.add_argument("--h", type=float, required=True, help="최종값(또는 초기값)까지의 세로 높이")
    ap.add_argument("--span", type=float, default=5.0, help="시정수 몇 배까지 그릴지(기본 5)")
    ap.add_argument("--stroke", default="#3a4252")
    ap.add_argument("--width", type=float, default=2.2, help="곡선 굵기(형상선 2~2.5)")
    args = ap.parse_args()

    poly, rows = curve_points(args.mode, args.x0, args.y0, args.w, args.h, args.span)
    tau_px = args.w / float(args.span)

    print("<polyline points='%s' fill='none' stroke='%s' stroke-width='%s' "
          "stroke-linejoin='round' stroke-linecap='round'/>"
          % (poly, args.stroke, args.width))
    print()

    mark = 1.0 - math.exp(-1.0) if args.mode == "charge" else math.exp(-1.0)
    xt = args.x0 + tau_px
    yt = args.y0 - mark * args.h
    print("[기하] 이 아래 값은 라벨을 붙일 자리다 — 문구와 색은 사람이 정한다")
    print("  시정수 지점 t=tau  : (%.1f, %.1f) · 화면비 %.4f (= %.1f 퍼센트)"
          % (xt, yt, mark, 100.0 * mark))
    print("  출발점 접선        : (%.1f, %.1f) → (%.1f, %.1f)"
          % (args.x0, rows[0][3], xt, args.y0 - (1.0 if args.mode == "charge" else 0.0) * args.h))
    print("  시정수 눈금 x      : %s"
          % ", ".join("%.1f" % (args.x0 + k * tau_px)
                      for k in range(int(args.span) + 1)))
    print("  최종값 수평선 y    : %.1f  (x %.1f ~ %.1f)"
          % (args.y0 - (args.h if args.mode == "charge" else 0.0),
             args.x0, args.x0 + args.w))
    print("  축                : x (%.1f,%.1f)-(%.1f,%.1f) · y (%.1f,%.1f)-(%.1f,%.1f)"
          % (args.x0, args.y0, args.x0 + args.w + 20, args.y0,
             args.x0, args.y0, args.x0, args.y0 - args.h - 30))
    for k in (3, 5):
        if k <= args.span:
            done = 1.0 - math.exp(-k) if args.mode == "charge" else math.exp(-k)
            print("  검산 %dtau         : %.2f 퍼센트 %s"
                  % (k, 100.0 * done, "진행" if args.mode == "charge" else "남음"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
