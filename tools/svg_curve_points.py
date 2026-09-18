# -*- coding: utf-8 -*-
"""사인·코사인 곡선의 `polyline points` 문자열을 찍는다 (열린 날 2026-09-09).

    python tools/svg_curve_points.py --x0=90 --x1=540 --step=9 \
        --mid=169.3 --amp=67.3 --period=450 --phase=146.3 --kind=-cos

★ **왜 열렸나** — 사용자 지적(`data/응용고체역학/2026-09-09-화면검수-인박스.md` ④):
  *[발화 생략]*.
  실측하니 사인 꼴 두 곡선이 **17점 polyline** 이었다 — 착시가 아니라 소스에 그대로 있었다.
  표본을 늘리면 되는데, **좌표를 손으로 적는 것은 규격이 금지한다**(삽화 규격 「손으로 좌표를
  잡지 않는다 — 사람이 정하는 것은 무엇을 어디에 놓을지뿐이다」). 그래서 찍는 자를 둔다.

## 인자의 뜻 — 전부 **viewBox 좌표**다

- `--x0`·`--x1` 곡선이 그려질 가로 구간. `--step` 은 표본 간격(px).
- `--mid` 곡선의 중심선 y. `--amp` 진폭(px). 화면 y 는 아래가 양수라 부호를 뒤집지 않는다 —
  `--kind` 로 고른다.
- `--period` 한 주기의 가로 길이(px). `--phase` 는 **위상 0 이 되는 x** 다.
- `--kind` — `sin` · `cos` · `-cos`(위상 자리에서 최댓값이 위로 솟는 꼴).
- `--decay` 진폭을 `exp(-decay*(x-x0))` 로 줄인다(1/px). 기준 x 를 옮기려면 `--decay-from`.
  부족감쇠 계단응답처럼 **포락선이 지수로 줄어드는 진동**이 이 인자로 열린다(2026-09-11).

## ☐ 이 자가 안 하는 것

- **곡선이 무엇을 뜻하는지 모른다.** 극값이 축 라벨·표시점과 맞는지는 사람이 본다 —
  표본을 늘리면 **표본점이 곧 극값이던 성질이 깨질 수 있다**(원래 17점 판은 극값이 표본이라
  자동으로 맞아 있었다). `--step` 이 주기를 정수로 나누면 그 성질이 유지된다.
- 좌표를 데이터에 **넣어 주지 않는다.** 찍은 문자열을 사람이 붙인다.
"""
import math
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

KINDS = {
    "sin": math.sin,
    "cos": math.cos,
    "-cos": lambda t: -math.cos(t),
}


def points(x0, x1, step, mid, amp, period, phase, kind, decay=0.0, decay_from=None):
    """`points` 에 넣을 (x, y) 목록. 순수 함수 — 테스트가 직접 부른다.

    `x1` 은 **포함**한다. 마지막 표본이 빠지면 곡선이 축 앞에서 끊긴다.

    `decay` 는 **1/px 단위의 감쇠율**이고 진폭에 `exp(-decay*(x-decay_from))` 을 곱한다
    (`decay_from` 의 기본값은 `x0`). 0 이면 예전과 같은 순수 사인·코사인이다 —
    부족감쇠 계단응답·감쇠 진동처럼 **포락선이 지수로 줄어드는 곡선**이 이 인자로 열린다.
    감쇠 진동은 한 과목의 사정이 아니라 여러 과목이 같은 꼴로 그린다.
    """
    fn = KINDS[kind]
    base = x0 if decay_from is None else decay_from
    out, x = [], x0
    n = int(round((x1 - x0) / step))
    for i in range(n + 1):
        x = x0 + i * step
        env = math.exp(-decay * (x - base)) if decay else 1.0
        y = mid + amp * env * fn(2.0 * math.pi * (x - phase) / period)
        out.append((round(x, 2), round(y, 2)))
    return out


def _fmt(v):
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def main(argv):
    opts = {}
    for a in argv:
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            opts[k] = v
    need = ("x0", "x1", "step", "mid", "amp", "period", "phase")
    missing = [k for k in need if k not in opts]
    if missing:
        sys.exit("빠진 인자: " + " ".join("--" + k for k in missing))
    kind = opts.get("kind", "sin")
    if kind not in KINDS:
        sys.exit("모르는 kind: %s (쓸 수 있는 것: %s)" % (kind, " · ".join(KINDS)))

    pts = points(float(opts["x0"]), float(opts["x1"]), float(opts["step"]),
                 float(opts["mid"]), float(opts["amp"]), float(opts["period"]),
                 float(opts["phase"]), kind, float(opts.get("decay", 0.0)),
                 float(opts["decay-from"]) if "decay-from" in opts else None)
    print(" ".join("%s,%s" % (_fmt(x), _fmt(y)) for x, y in pts))
    print("\n※ 표본 %d점 — 극값이 축 라벨·표시점과 맞는지는 사람이 본다" % len(pts),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
