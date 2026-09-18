# -*- coding: utf-8 -*-
"""**꺾인 점 사슬을 매끄러운 3차 베지에로 바꾼다** (열린 날 2026-09-10).

    python tools/svg_smooth_path.py --points "430,362 454,357 478,364 502,357"
    python tools/svg_smooth_path.py --points "…" --closed --tension=0.8
    python tools/svg_smooth_path.py --points "…" --tail "L550 400 L430 400 Z"

★ **왜 열렸나** — 사용자 재지적 2026-09-10: *[발화 생략]*. 재는 자(`audit_curve_smoothness.py`)를 세웠지만 **고치는 자가
  없었다** — 점을 더 찍어 촘촘히 하는 길(`svg_curve_points.py`)은 사인·코사인처럼 **식이 있는
  곡선**에만 쓸 수 있고, 언덕 윤곽·수면 물결처럼 **손으로 고른 몇 점**은 그 길이 막힌다.
  점 사이를 곡선으로 잇는 것이 이 자의 몫이다.

## 어떻게 잇나 — Catmull-Rom → 3차 베지에

각 구간 `P1 → P2` 를 3차 베지에로 바꾼다. 제어점은 이웃 점이 정한다.

    B1 = P1 + t · (P2 − P0) / 6
    B2 = P2 − t · (P3 − P1) / 6

`t`(`--tension`, 기본 1.0)는 **원래 점을 반드시 지나면서** 얼마나 부풀릴지다. 0 이면 직선으로
돌아가고 1 이 표준 Catmull-Rom 이다. **점을 옮기지 않는다** — 원래 사슬이 지나던 자리를 그대로
지나므로 라벨·치수선을 다시 잡을 필요가 없다. 그것이 「점을 더 찍는 길」보다 나은 자리다.

열린 사슬의 양끝은 끝점을 한 번 더 쓴 것으로 본다(끝에서 곡률이 0 이 되어 튀지 않는다).

## ☐ 이 자가 못 보는 것 (규칙 21)

- **원래 사슬이 옳은지 안 본다.** 물리적으로 틀린 형상을 매끄럽게만 만든다.
- **자기 교차를 안 본다.** 꺾임이 아주 급한 자리(180° 가까이)에서는 부푼 곡선이 스스로를
  가로지를 수 있다 — `--tension` 을 낮추고 **렌더를 눈으로 본다**.
- **채움 도형의 나머지 변은 `--tail` 로 사람이 적는다.** 어디까지가 곡선이고 어디부터 직선인지는
  뜻이 정하는 것이라 기계가 못 가른다.
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_TENSION = 1.0       # 표준 Catmull-Rom. 부풀림을 줄일 때만 낮춘다
DECIMALS = 2


def parse_points(text):
    """`"x,y x,y …"` 또는 `"x y x y …"` 를 점 목록으로. 순수 함수."""
    vals = [float(v) for v in text.replace(",", " ").split()]
    if len(vals) % 2:
        raise ValueError("좌표 개수가 홀수다")
    return list(zip(vals[0::2], vals[1::2]))


def _fmt(v):
    return ("%%.%df" % DECIMALS) % v


def smooth_path(points, closed=False, tension=DEFAULT_TENSION):
    """점 사슬을 `M … C …` 문자열로. 순수 함수.

    닫힌 사슬이면 마지막 구간이 첫 점으로 돌아오고 `Z` 로 닫힌다.
    """
    n = len(points)
    if n < 3:
        raise ValueError("점이 셋보다 적으면 이을 곡선이 없다")

    def at(i):
        if closed:
            return points[i % n]
        return points[max(0, min(n - 1, i))]

    out = ["M%s %s" % (_fmt(points[0][0]), _fmt(points[0][1]))]
    last = n if closed else n - 1
    for i in range(last):
        p0, p1, p2, p3 = at(i - 1), at(i), at(i + 1), at(i + 2)
        b1 = (p1[0] + tension * (p2[0] - p0[0]) / 6.0,
              p1[1] + tension * (p2[1] - p0[1]) / 6.0)
        b2 = (p2[0] - tension * (p3[0] - p1[0]) / 6.0,
              p2[1] - tension * (p3[1] - p1[1]) / 6.0)
        out.append("C%s %s %s %s %s %s"
                   % (_fmt(b1[0]), _fmt(b1[1]), _fmt(b2[0]), _fmt(b2[1]),
                      _fmt(p2[0]), _fmt(p2[1])))
    if closed:
        out.append("Z")
    return " ".join(out)


def main(argv):
    text = None
    closed = "--closed" in argv
    tension = DEFAULT_TENSION
    tail = ""
    for a in argv:
        if a.startswith("--points="):
            text = a.split("=", 1)[1]
        elif a.startswith("--tension="):
            tension = float(a.split("=", 1)[1])
        elif a.startswith("--tail="):
            tail = a.split("=", 1)[1]
    if text is None:
        i = argv.index("--points") + 1 if "--points" in argv else -1
        if 0 < i < len(argv):
            text = argv[i]
        j = argv.index("--tail") + 1 if "--tail" in argv else -1
        if 0 < j < len(argv):
            tail = argv[j]
    if not text:
        sys.exit("쓰는 법 — python tools/svg_smooth_path.py --points \"x,y x,y …\" "
                 "[--closed] [--tension=1.0] [--tail \"L… Z\"]")
    d = smooth_path(parse_points(text), closed=closed, tension=tension)
    if tail:
        d = d + " " + tail
    print(d)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
