# -*- coding: utf-8 -*-
"""회전한 평면응력 요소의 네 면 화살표를 찍는다 (좌표를 손으로 잡지 않는다).

**무엇을 푸는가.** 정사각 요소를 각 θ 만큼 돌리면 네 면 각각에 수직응력 σ 하나와
전단응력 τ 하나가 붙는다. 여덟 개를 손으로 놓으면 두 가지가 반드시 틀린다 —
⑴ 점대칭 복제만 하고 **우력의 부호**를 안 재서 네 τ 가 같은 방향으로 돈다
⑵ 같은 면의 σ 와 τ 가 겹쳐 「무엇이 무엇과 짝인가」가 안 읽힌다.
둘 다 2026-09-09 응용고체 `fig-11-stress-element` 에서 실제로 났고, 사용자가
   *[발화 생략]* ·
   *[발화 생략]*
로 두 번 짚었다. 그래서 **부호는 축에서 세우고 위치는 꼭짓점에서 잰다**:

- τ 는 +x1 면에서 +y1 을, +y1 면에서 +x1 을 향한다(양의 전단). 그러면 네 화살표가
  두 꼭짓점(대각으로 마주 보는 둘)으로 **모인다** — 두 우력이 반대라는 것이 그림에서 닫힌다.
- τ 는 그 **모이는 꼭짓점** 쪽에, σ 는 같은 면의 **반대쪽 꼭짓점** 쪽에 놓는다.

사람이 정하는 것은 중심·크기·각도뿐이고, 좌표는 이 도구가 찍는다(삽화 규격).

사용:
    python tools/svg_stress_element.py --centre 450,160 --half 55 --angle 50
    python tools/svg_stress_element.py --centre 450,160 --half 55 --angle 50 --arrows-only

각도는 **SVG 화면 좌표**(y 가 아래로 증가)에서 잰 x1 축의 방향이다 — 50 이면
x1 이 오른쪽 아래를 향한다. 라벨 자리는 「여기쯤」이 아니라 화살촉 끝에서 뻗은 값으로 낸다.
"""
import argparse
import math
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 아래 다섯은 **기존 삽화에서 실측한 값**이다(2026-09-09, `fig-11-stress-element` 의
# σ·τ 화살표를 축에 투영해 잼). 새로 고른 수가 아니라 이미 화면에 있던 비례라
# 같은 장의 다른 삽화와 굵기·길이가 어긋나지 않는다.
SIG_SHAFT, SIG_TIP, SIG_HALF = 24.0, 38.0, 5.0   # σ: 선 24 · 촉 끝 38 · 촉 반폭 5
# τ 는 σ 보다 **짧다.** σ 가 면 중점에서 나가는 자리를 비켜 주는 몫을 길이로 낸다 —
# 사용자 판정 2026-09-09: *[발화 생략]*. 첫 판은 σ 를 옆으로 밀어 자리를 만들었는데,
# **면 중점에서 나가는 것이 σ 의 뜻**이라 옮기면 안 되는 것이었다.
TAU_SHAFT, TAU_TIP, TAU_HALF = 18.0, 27.0, 4.0

# σ 는 **면 중점**에서 바깥으로 나간다. 0 이 아닌 값을 주면 그 뜻이 깨진다.
SIG_OFFSET_RATIO = 0.0
TAU_OUT = 10.0      # τ 를 면 바깥으로 띄우는 거리 — 도선이 아니라 면 위의 응력임이 보이게
# τ 꼬리를 모이는 꼭짓점 쪽으로 미는 거리. 면 중점의 σ 와 이만큼 떨어지고,
# 촉 끝은 half − TAU_SLIDE − TAU_TIP 만큼 꼭짓점에 못 미쳐 모서리에 안 박힌다.
TAU_SLIDE = 22.0

SIG_COLOR, SIG_WIDTH = "#8b929c", "1.8"   # 고정부 계열 — 규격 팔레트
TAU_COLOR, TAU_WIDTH = "#4a5568", "1.6"   # 윤곽선과 같은 짙은 색(전단은 면을 쓸어 간다)
# 화살촉 끝에서 라벨 **중심**까지. 라벨은 점이 아니라 상자라, 축 방향으로 뻗은 상자
# 반너비(글자 17px 기준 약 16.5)를 빼고도 규격의 여백 하한 0.5em(8.5px)이 남아야 한다.
# 18 로 잡았더니 실측 여백이 1.5px 였다(2026-09-09) — 30 이면 13.5px 가 남는다.
LABEL_GAP = 30.0


def _add(*vs):
    return (sum(v[0] for v in vs), sum(v[1] for v in vs))


def _mul(v, s):
    return (v[0] * s, v[1] * s)


def _neg(v):
    return (-v[0], -v[1])


def axes(angle_deg):
    """x1·y1 단위벡터. y1 은 x1 을 화면에서 +90° 돌린 것(오른손 짝)."""
    a = math.radians(angle_deg)
    x1 = (math.cos(a), math.sin(a))
    y1 = (math.sin(a), -math.cos(a))
    return x1, y1


def arrow(base, direction, shaft, tip, half, color, width):
    """꼬리 base 에서 direction 으로 뻗는 화살표 한 벌. (svg, 화살촉 끝) 을 낸다."""
    perp = (-direction[1], direction[0])
    end = _add(base, _mul(direction, shaft))
    p1 = _add(base, _mul(direction, shaft), _mul(perp, half))
    p2 = _add(base, _mul(direction, shaft), _mul(perp, -half))
    p3 = _add(base, _mul(direction, tip))
    svg = (
        "<line x1='%.2f' y1='%.2f' x2='%.2f' y2='%.2f' stroke='%s' stroke-width='%s'/>"
        % (base[0], base[1], end[0], end[1], color, width)
        + "<path d='M%.2f %.2f L%.2f %.2f L%.2f %.2f Z' fill='%s' stroke='%s'"
          " stroke-width='0.75' stroke-linejoin='round'/>"
        % (p1[0], p1[1], p2[0], p2[1], p3[0], p3[1], color, color)
    )
    return svg, p3


def faces(centre, half, angle_deg):
    """네 면을 (이름, 바깥 법선, τ 가 향하는 방향) 으로 낸다.

    τ 방향이 양의 전단 규약을 그대로 옮긴 것이다 — +x1 면에서 +y1, +y1 면에서 +x1,
    나머지 둘은 그 점대칭. 그래서 네 화살표가 두 꼭짓점으로만 모인다.
    """
    x1, y1 = axes(angle_deg)
    return [
        ("+x1", x1, y1),
        ("+y1", y1, x1),
        ("-x1", _neg(x1), _neg(y1)),
        ("-y1", _neg(y1), _neg(x1)),
    ]


def element(centre, half, angle_deg, arrows_only=False):
    """요소 하나 분량의 SVG 조각과 라벨 자리 목록."""
    x1, y1 = axes(angle_deg)
    corners = [
        _add(centre, _mul(x1, half), _mul(y1, half)),
        _add(centre, _mul(x1, -half), _mul(y1, half)),
        _add(centre, _mul(x1, -half), _mul(y1, -half)),
        _add(centre, _mul(x1, half), _mul(y1, -half)),
    ]
    parts = []
    if not arrows_only:
        parts.append(
            "<path d='M%s Z' fill='#e4e7ec' fill-opacity='0.5' stroke='#4a5568' stroke-width='2'/>"
            % " L".join("%.2f %.2f" % c for c in corners)
        )
    sig_offset = half * SIG_OFFSET_RATIO
    labels = []
    for name, n, t in faces(centre, half, angle_deg):
        mid = _add(centre, _mul(n, half))
        sig_base = _add(mid, _mul(t, -sig_offset))
        sig_svg, sig_tip = arrow(sig_base, n, SIG_SHAFT, SIG_TIP, SIG_HALF, SIG_COLOR, SIG_WIDTH)
        tau_base = _add(mid, _mul(n, TAU_OUT), _mul(t, TAU_SLIDE))
        tau_svg, tau_tip = arrow(tau_base, t, TAU_SHAFT, TAU_TIP, TAU_HALF, TAU_COLOR, TAU_WIDTH)
        parts.append(sig_svg)
        parts.append(tau_svg)
        # σ 라벨은 화살촉 **앞**에 둔다 — 화살표가 가리키는 쪽이 곧 그 응력의 방향이다.
        labels.append((name, "σ", _add(sig_tip, _mul(n, LABEL_GAP))))
        # τ 라벨은 화살촉 앞이 아니라 화살표 **옆**(면 바깥쪽)에 둔다. τ 는 면을 따라
        # 누우므로 앞쪽은 모이는 꼭짓점이라 이미 붐빈다 — 실측 2026-09-09: 앞에 두었더니
        # 화살촉과 겹쳐 lint F1(0.5em)과 도형 경계 검사가 함께 걸렸다.
        labels.append((name, "τ", _add(tau_base, _mul(t, TAU_TIP * 0.5), _mul(n, LABEL_GAP))))
    return "".join(parts), labels, corners


def main():
    ap = argparse.ArgumentParser(description="회전 평면응력 요소의 면 화살표를 찍는다")
    ap.add_argument("--centre", required=True, help="중심 x,y")
    ap.add_argument("--half", type=float, required=True, help="반쪽 변 길이")
    ap.add_argument("--angle", type=float, required=True, help="x1 축 각(도, SVG 화면 좌표)")
    ap.add_argument("--arrows-only", action="store_true", help="사각형은 빼고 화살표만")
    args = ap.parse_args()

    cx, cy = (float(v) for v in args.centre.split(","))
    svg, labels, corners = element((cx, cy), args.half, args.angle, args.arrows_only)
    print(svg)
    print("")
    print("# 꼭짓점")
    for c in corners:
        print("#   %.2f %.2f" % c)
    bx0 = min(c[0] for c in corners)
    by0 = min(c[1] for c in corners)
    bx1 = max(c[0] for c in corners)
    by1 = max(c[1] for c in corners)
    print("# ★ 라벨 상자는 아래 **바깥 상자** 밖으로 뺀다: %.2f %.2f — %.2f %.2f" % (bx0, by0, bx1, by1))
    print("#   빌드의 「글자가 도형 경계에 걸침」 검사는 기울어진 요소를 바깥 상자로 재므로,")
    print("#   요소 안쪽이 아니어도 그 상자에 걸치면 신고된다(2026-09-09 실측).")
    print("# 라벨 자리 시작점 (σ 는 화살촉 앞 %.0f · τ 는 화살표 옆 %.0f)" % (LABEL_GAP, LABEL_GAP))
    for name, kind, p in labels:
        print("#   %s 면 %s : x='%.2f' y='%.2f'" % (name, kind, p[0], p[1]))


if __name__ == "__main__":
    main()
