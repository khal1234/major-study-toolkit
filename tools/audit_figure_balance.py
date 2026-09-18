# -*- coding: utf-8 -*-
"""삽화의 '균형'을 수치로 잰다 — 읽기 전용 감사.

왜 만들었나 (열린 날 2026-07-29):
    `fig-closed-open-isolated` 가 *[발화 생략]* 으로 **3회** 지적됐다. 6회차에 원인을
    *[발화 생략]* 로 정확히 진단해 놓고, 7회차에서는
    **간격을 눈으로 정해** 재배치했다. 기준이 없으니 두 번째 시도도 빗나갔다.

    빌드 검사(F1)는 `< 0.5em` 만 막는다. 그건 **하한**이지 **균형**이 아니다.
    이 도구는 빌드가 보지 않는 두 가지를 잰다:
      ⑴ 콘텐츠의 위 여백 vs 아래 여백 (세로 균형)
      ⑵ 라벨이 도형에서 얼마나 떨어져 있는지의 **분포** (간격 일관성)
    사용자 지적이 λ는 "너무 붙었다", T₁·v₁는 "너무 떴다"로 **양방향**이었다는 것은
    넓히거나 좁히라는 뜻이 아니라 **기준이 없다**는 뜻이다.

기준 (이 도구가 쓰는 값 — 근거는 위 진단이고, 바꾸려면 여기 한 곳만 고친다):
    LABEL_TO_SHAPE_EM = 1.0   라벨과 도형 외형선 사이. 빌드 하한 0.5em의 2배 —
                              "최소만 겨우 넘기게 밀면 간격이 들쭉날쭉해진다"(6회차 교훈)에 대한 답.
    BALANCE_TOL_PX    = 6.0   위·아래 여백 차이 허용치. 이보다 크면 한쪽으로 쏠려 보인다.

사용:
    python tools/audit_figure_balance.py data/열역학/ch01.json
    python tools/audit_figure_balance.py data/열역학/ch01.json --id fig-closed-open-isolated
"""
import argparse

# `--fail-only` 가 켜지면 참고용 절을 생략한다(아래 `audit()` 안 주석이 정본).
FAIL_ONLY = False
import json
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_content import (  # noqa: E402
    DIM_GAP_SCREEN_PX, DIM_GEOM_TOL_PX, DIM_OVERSHOOT_SCREEN_PX, dim_extension_rows,
)
from buildlib.checks_svg import (  # noqa: E402
    _attr, _distance, _effective, _fraction_bars, _path_polyline, _svg_segments, _svg_texts,
    _text_bbox, _segment_to_rect_distance, arrow_geometry, fraction_unit_boxes,
    BOX_CENTER_MAX_RATIO, BOX_CENTER_TOL_EM, LABEL_PAIR_RATIO_MAX, figure_box_centering,
    figure_label_pair_gap_hits, symbol_below_caption_rows,
    FIGURE_BALANCE_TOL_PX, figure_vertical_extent,
)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# ★ 나가는 쪽도 고친다 — 안 고치면 **오류 메시지만** 깨진다(AGENTS 「알려진 함정」).
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LABEL_TO_SHAPE_EM = 1.0
BALANCE_TOL_PX = FIGURE_BALANCE_TOL_PX   # 정본은 빌드 쪽 상수다(F7 게이트)
CAPTION_HANGUL_MIN = 6   # 한글 음절 이만큼 이상이면 '설명 문장'으로 본다
TIP_TOL_PX = 0.5         # 화살촉 끝점이 기준선의 stroke 폭 밖으로 이만큼 넘으면 결함
# 끝점에서 이 범위 안에 있는 기준선만 '자기 기준선'으로 본다.
# 8.0 으로 열었다가 **부류의 절반을 놓쳤다**(2026-07-29 실측): FBD의 힘 화살표가
# 피스톤 면에서 9.25px 떠 있었는데 반경 밖이라 0건으로 나왔고, 나는 그 0건을 근거로
# "이 화살표들은 닿아 있다"고 사용자에게 보고했다. 순회 범위를 확인하지 않은 '0건'은
# '없다'가 아니라 '거기까지는 없다'이다(규칙 11) — 반경 자체가 그 사각지대였다.
TIP_SEARCH_PX = 16.0
TIP_MAX_SIDE = 32.0      # 변이 이보다 길면 화살촉이 아니라 도형이다 (checks_svg와 같은 값)
# 글자 폭은 `_char_w` 로 **추정**한 값이라 여유 계산에 그만큼 오차가 실린다.
# 이 슬랙보다 작은 미달은 "안 맞다"가 아니라 "잴 수 없다" 이므로 신고하지 않는다.
GAP_TOL_PX = 1.0


def _hangul_count(s):
    return sum(1 for c in s if 0xAC00 <= ord(c) <= 0xD7AF)


def _is_caption(text):
    """설명 캡션인가 — 굵지 않고 한글 음절이 여러 개면 문장으로 본다.

    굵기를 쓰는 이유: 패널 제목은 거의 항상 font-weight 700이고 길이도 길어서,
    길이만 보면 제목이 캡션으로 잡힌다.
    한글 음절 수를 쓰는 이유: '0 K, -273.15°C' 같은 눈금 라벨은 14자로 길지만
    문장이 아니다 — 글자 수로만 재면 이런 라벨이 전부 캡션으로 잡힌다.
    """
    if text["bold"]:
        return False
    return _hangul_count(text["s"]) >= CAPTION_HANGUL_MIN


_DRAWABLE = re.compile(r"<(path|rect|circle|ellipse|line|polygon|polyline)\b")


def drawable_count(svg):
    """그리기 요소 수 — 배경판 하나는 뺀다. 순수 함수.

    왜 재나 (2026-08-04, 인박스 R-40) — *[발화 생략]* 라는 지적이 반복되는데
    **성의는 기계가 못 본다.** 대신 *지문의 주인공을 그리려면 요소가 몇 개는 든다*는 것은 잴 수 있다.
    실측 근거: 퍼니큘러 삽화가 고치기 전 **6개**(막대·보조선·호·화살표뿐), 고친 뒤 30개 남짓.
    ★ 이것은 **후보 목록**이지 판정이 아니다 — 개념 삽화는 원래 요소가 적을 수 있다.
      문턱을 정하려면 먼저 분포를 봐야 하므로, 이 절은 **전부 찍는다**(규칙 11).
    """
    return max(0, len(_DRAWABLE.findall(svg or "")) - 1)


def iter_diagrams(node):
    """chNN.json 안의 삽화를 전부 낸다.

    ★ 유도 카드의 슬라이드 삽화(`derivation.formulas[].figure`, 단수 객체)도 여기서 낸다
    (2026-08-29, 사용자: *[발화 생략]* — 새로 만든 슬라이드 삽화 두 개가
    이 감사에 한 번도 안 걸렸다. `diagrams`(배열) 만 보고 `figure`(단수)는 안 봐서, 유도 탭의
    삽화는 태생적으로 사각지대였다 — 원인은 「배열이 아니라 단수 하나」라는 스키마 차이다).
    """
    if isinstance(node, dict):
        for diagram in node.get("diagrams") or []:
            if isinstance(diagram, dict) and diagram.get("svg"):
                yield diagram
        fig = node.get("figure")
        if isinstance(fig, dict) and fig.get("svg"):
            yield fig
        for value in node.values():
            yield from iter_diagrams(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_diagrams(value)


def _viewbox(svg):
    raw = _attr(svg[svg.find("<svg"):svg.find(">") + 1], "viewBox")
    return [float(v) for v in raw.split()] if raw else None


def _content_extent(svg, vb):
    """배경을 뺀 콘텐츠의 세로 범위 — **정본은 빌드 쪽**이다.

    2026-09-09 에 이 판정을 `buildlib/checks_svg.figure_vertical_extent` 로 올렸다
    (F7 게이트). 같은 값을 두 자로 재면 갈리므로 여기서는 그 함수를 그대로 부른다.
    """
    return figure_vertical_extent(svg, vb)


_NUM = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
_TRIANGLE_RE = re.compile(
    rf"M\s*({_NUM})[ ,]({_NUM})\s*L\s*({_NUM})[ ,]({_NUM})"
    rf"\s*L\s*({_NUM})[ ,]({_NUM})\s*Z", re.I
)


def _triangle_elements(svg):
    """채운 삼각형의 (attrs, 세 꼭짓점) — `<path d>` 와 **`<polygon points>` 양쪽**.

    ★ 열린 날 2026-07-30 — 이 함수는 `<path>` 만 돌았다. 열역학 삽화가 path 로 화살촉을
    그리기 때문에 그 과목에서는 잘 돌고, `<polygon>` 을 쓰는 과목(공학수학 전 삽화)에서는
    「화살촉 끝점」 절이 **영구히 `0건`** 을 찍었다 — 순회 범위 0건이지 결함 0건이 아니다.
    판정은 `checks_svg.polygon_triangle_points` 하나로 한다(사본 금지 — 그 독스트링이 전말).
    """
    for match in re.finditer(r"<path\b([^>]*?)/?>", svg):
        attrs = match.group(1)
        if _attr(attrs, "fill") in (None, "none"):
            continue
        found = _TRIANGLE_RE.search(_attr(attrs, "d", "") or "")
        if found:
            yield attrs, [(float(found.group(i)), float(found.group(i + 1))) for i in (1, 3, 5)]
    # ※ `<polygon>` 은 순회하지 않는다 — 빌드 L7 이 형식을 `<path d='…Z'/>` 로 못박는다
    #   (2026-07-30 thermo 설계 채택). 자를 넓히는 대신 집 형식을 하나로 두는 쪽이다.


def _filled_triangles(svg):
    """채운 삼각형(= 화살촉)의 (밑변 중앙, 꼭짓점, 세 꼭짓점)을 뽑는다."""
    out = []
    for attrs, pts in _triangle_elements(svg):
        pairs = ((0, 1), (0, 2), (1, 2))
        if max(_distance(pts[a], pts[b]) for a, b in pairs) > TIP_MAX_SIDE:
            continue
        # 꼭짓점 = **무게중심에서 가장 먼 점.**
        #
        # 처음에는 '이등변삼각형의 꼭짓점은 두 밑변 꼭짓점에서 같은 거리'라는 성질을 썼는데,
        # 세 변이 비슷한 화살촉에서 **엉뚱한 점을 꼭짓점으로 골랐다**(실측 2026-07-30,
        # ch02 `fig-02-p06`: 변 길이 13.0 / 13.4 / 13.9 → 거리차 0.4 vs 0.47 로 판정이 뒤집혔다).
        # 그 결과 '끝점이 11.56px 지나침'이라는 **없는 결함**을 신고했다 — 감사 도구가
        # 없는 결함을 만들면 사람이 멀쩡한 데이터를 고치게 되므로 놓치는 것만큼 나쁘다.
        # 무게중심 거리는 밑변이 높이의 2배를 넘지 않는 한(화살촉이면 늘 그렇다) 안정적이다.
        centroid = (sum(p[0] for p in pts) / 3.0, sum(p[1] for p in pts) / 3.0)
        ranked = sorted(range(3), key=lambda k: _distance(pts[k], centroid), reverse=True)
        far, second = (_distance(pts[ranked[0]], centroid), _distance(pts[ranked[1]], centroid))
        if far <= second * 1.02:
            continue          # 정삼각형에 가까워 꼭짓점을 못 가린다 — 판정하지 않는다
        tip_index = ranked[0]
        base_pair = tuple(sorted({0, 1, 2} - {tip_index}))
        tip = pts[tip_index]
        base = ((pts[base_pair[0]][0] + pts[base_pair[1]][0]) / 2.0,
                (pts[base_pair[0]][1] + pts[base_pair[1]][1]) / 2.0)
        out.append((base, tip, pts))
    return out


def _float_attr(attrs, name, default):
    try:
        return float(_attr(attrs, name, default))
    except (TypeError, ValueError):
        return float(default)


def _marker_circles(svg):
    """표식 원 (cx, cy, r). 화살촉이 **여기 착지하는 것도 '닿았다'** 이다.

    열린 날 2026-07-30 — 도구 자체의 오탐. `fig-steady-flow-snapshots` 의 유동 화살표 3개는
    입구 점에서 출구 점까지를 가리키는 것이라 **출구 표식 원의 테두리에 정확히** 끝난다
    (끝점 128 · 원 cx 132 r 4 → 오차 0.00px). 그런데 이 감사는 선분만 기준선으로 보아,
    16px 떨어진 **관 외형선**을 '자기 기준선'으로 잡고 "16px 못 미침"이라고 신고했다.
    화살표를 관 벽까지 늘리면 출구 점을 뚫고 지나가 그림이 틀려진다 — 즉 신고대로 고치면
    더 나빠지는 결함이었다.

    완화가 아니다: 판정은 **정확히 테두리 위(±TIP_TOL_PX)** 일 때만 면제한다.
    원 근처에서 어정쩡하게 멈춘 화살촉은 그대로 걸린다(`test_tip_landing_on_marker_circle`).
    """
    out = []
    for m in re.finditer(r"<circle([^>]*)>", svg):
        a = m.group(1)
        r = _float_attr(a, "r", 0)
        if r:
            out.append((_float_attr(a, "cx", 0), _float_attr(a, "cy", 0), r))
    return out


def _segments_with_stroke(svg):
    """선분마다 stroke-width를 함께 돌려준다 — 굵기를 모르면 '닿았다'를 판정할 수 없다.

    굵은 외형선(stroke 3)에 화살촉이 바깥에서 닿으면 기하학적 중심선과는 1.5px 떨어진다.
    그걸 결함으로 세면 규격을 지킨 삽화만 골라 때리게 된다(L5의 전례).
    """
    out = []
    for match in re.finditer(r"<rect([^>]*?)/?>", svg):
        attrs = match.group(1)
        if _attr(attrs, "stroke") in (None, "none"):
            continue
        width = _float_attr(attrs, "stroke-width", 1)
        x, y = _float_attr(attrs, "x", 0), _float_attr(attrs, "y", 0)
        w, h = _float_attr(attrs, "width", 0), _float_attr(attrs, "height", 0)
        for seg in ((x, y, x + w, y), (x + w, y, x + w, y + h),
                    (x + w, y + h, x, y + h), (x, y + h, x, y)):
            out.append((seg, width))
    for match in re.finditer(r"<line([^>]*?)/?>", svg):
        attrs = match.group(1)
        out.append((tuple(_float_attr(attrs, k, 0) for k in ("x1", "y1", "x2", "y2")),
                    _float_attr(attrs, "stroke-width", 1)))
    for match in re.finditer(r"<path([^>]*?)/?>", svg):
        attrs = match.group(1)
        dstr = _attr(attrs, "d")
        if not dstr or _attr(attrs, "stroke") in (None, "none"):
            continue
        width = _float_attr(attrs, "stroke-width", 1)
        for seg in _path_polyline(dstr):
            out.append((seg, width))
    return out


def _same_segment(seg, wall):
    (ax, ay), (bx, by) = wall
    fwd = (abs(seg[0] - ax) < 0.01 and abs(seg[1] - ay) < 0.01
           and abs(seg[2] - bx) < 0.01 and abs(seg[3] - by) < 0.01)
    rev = (abs(seg[0] - bx) < 0.01 and abs(seg[1] - by) < 0.01
           and abs(seg[2] - ax) < 0.01 and abs(seg[3] - ay) < 0.01)
    return fwd or rev


def _container_walls(base, regions):
    """화살표의 **꼬리를 담고 있는** 칸의 변들. 이건 겨냥한 기준선이 아니다.

    열린 날 2026-07-30 — **감사 도구 자체의 오탐**. `fig-sensible-temperature` 의
    분자 속도 벡터는 **길이가 곧 정보**다(느린 분자 8px · 빠른 분자 24px). 그런데 각 패널의
    맨 오른쪽 화살표가 우연히 벽에서 8·12px 떨어져 끝나 반경 16px 안에 들어왔고,
    자는 그 벽을 '자기 기준선'으로 잡아 "못 미침"이라고 신고했다.
    **신고대로 벽까지 늘리면 세 화살표가 같은 길이가 되어 이 삽화의 비교가 통째로 사라진다.**

    판정 기준은 **꼬리가 그 칸 안에 있는가**다. 칸 안에서 그려진 화살표는 그 칸의 벽을
    겨냥한 것이 아니라 칸 안의 무엇을 가리키는 것이다. 반대로 FBD 의 힘 화살표는
    꼬리가 물체 **밖**에 있고 끝점이 면에 닿아야 하므로 이 면제에 걸리지 않는다
    (그 부류를 잡으려고 TIP_SEARCH_PX 를 8→16 으로 넓혔던 것이다 — 그 강화는 그대로다).
    """
    walls = []
    for region in regions:
        if not _point_in_polygon(base, region["pts"]):
            continue
        pts = region["pts"]
        walls.extend((pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))
    return walls


FLOAT_TOUCH_PX = 3.0     # 이만큼 안에 다른 선·도형이 있으면 「붙어 있다」로 본다


def _point_to_segment(pt, seg):
    """점과 선분 사이의 최단 거리. 순수 함수 — 테스트가 직접 부른다."""
    ax, ay, bx, by = seg
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom < 1e-12:
        return _distance(pt, (ax, ay))
    t = max(0.0, min(1.0, ((pt[0] - ax) * dx + (pt[1] - ay) * dy) / denom))
    return _distance(pt, (ax + t * dx, ay + t * dy))


def _region_edges(region):
    pts = region["pts"]
    return [(p[0], p[1], q[0], q[1]) for p, q in zip(pts, pts[1:] + pts[:1])]


def _is_panel_divider(seg, others, regions):
    """패널 칸막이인가 — **양 끝이 아무것에도 안 닿고 떠 있는 선**. 순수 함수.

    열린 날 2026-08-13 — **감사 도구 자체의 오탐**(사용자 지적이 아니다. 고체역학 실측 5건).
    2패널 삽화의 세로 구분선은 *겨냥한 대상* 이 아니라 **레이아웃 칸막이**다. 그런데
    `TIP_SEARCH_PX`(16) 안에 들어오면 자가 그것을 「자기 기준선」으로 잡아, 양쪽 패널의
    자유 힘 화살표를 «못 미침/지나침» 으로 신고했다. `fig-shear-bolt` 은 양쪽 화살촉이
    칸막이에서 **정확히 12px 로 대칭**이라 의도가 분명한데도 걸렸다 —
    신고대로 늘리면 두 패널이 서로 침범한다.

    ★ **태깅(`class='panel-divider'`)을 요구하지 않는 이유는 중앙 정렬 잠금과 같다** —
      이미 만든 삽화를 전부 태깅하려면 검수를 끝낸 챕터를 건드려야 하고 그건 하이라이트
      잡음이 된다. 그래서 선언에 걸지 않고 **기본값을 안전한 쪽으로 뒤집는다**
      (AGENTS 규칙 7⑷ 의 선호 형태 · `fix_figure_label_gap._is_centered_on_shape` 선례).

    ★ 판정선은 **둘 다** 참일 때다 — 색·굵기를 열거하지 않는다(부류로 가른다).
      ⑴ **양 끝이 허공이다.** 이 리포에서 화살촉이 겨냥하는 기준선 셋은 전부 무언가에
         붙어 있다: 도형의 외형선(도형의 일부) · 치수보조선(재는 면에서 나온다) ·
         축(원점에서 만난다). 칸막이만 양 끝이 안 붙어 있다.
      ⑵ **양쪽에 패널 내용이 있다.** ⑴만으로는 너무 넓다 — 격리 픽스처의 외톨이
         기준선(`test_tip_landing_on_marker_circle` 의 x=144 선)까지 칸막이로 보고
         회귀 두 건을 죽였다. 칸막이는 *가르는* 선이라 양쪽에 도형이 있어야 한다.
    """
    edges = [e for region in regions for e in _region_edges(region)]
    for end in ((seg[0], seg[1]), (seg[2], seg[3])):
        near = [o for o in others if o is not seg]
        if any(_point_to_segment(end, o) <= FLOAT_TOUCH_PX for o in near):
            return False
        if any(_point_to_segment(end, e) <= FLOAT_TOUCH_PX for e in edges):
            return False
    nx, ny = -(seg[3] - seg[1]), seg[2] - seg[0]
    sides = set()
    for region in regions:
        pts = region["pts"]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        signed = (cx - seg[0]) * nx + (cy - seg[1]) * ny
        if abs(signed) > 1e-9:
            sides.add(signed > 0)
    return len(sides) == 2


def _runs_along_an_edge(base, tip, ux, uy, segments):
    """면을 **따라 흐르는** 화살표인가 — 그렇다면 겨냥한 기준선이 없다. 순수 함수.

    열린 날 2026-08-13 — **감사 도구 자체의 오탐**(고체역학 ch11 실측 2건).
    전단응력 화살표는 정의상 **면과 나란하게** 그려진다. 그런데 이 자는 411행에서
    *[발화 생략]* 이라며 **자기 면을 후보에서 빼고**, 그러면 모서리에서
    만나는 **옆 면**(축과 수직이다)이 「자기 기준선」으로 잡힌다. 실제로 마름모 요소의
    전단 화살촉 넷 중 둘이 *[발화 생략]* 으로 신고됐다 — 그 옆 면은 겨냥한 대상이
    아니고, 신고대로 늘리면 **화살표가 모서리를 뚫고 나간다.**

    판정선: **밑변과 끝점이 둘 다 같은 선분 위에 있다**(±`FLOAT_TOUCH_PX`)면 그 화살표는
    그 선을 *따라가는* 것이지 무엇을 *겨냥한* 것이 아니다. 겨냥하는 화살표는 대상 면에
    수직이라 그 면 위에 누울 수 없으므로, 이 면제가 진짜 결함을 풀어 주지 않는다.
    (`_container_walls`·`_is_panel_divider` 와 같은 부류 — 자가 만든 없는 결함을 닫는다.)
    """
    for seg, _width in segments:
        dx, dy = seg[2] - seg[0], seg[3] - seg[1]
        seg_len = math.hypot(dx, dy)
        if seg_len < 1e-6:
            continue
        vx, vy = dx / seg_len, dy / seg_len
        if abs(ux * vx + uy * vy) < 0.99:
            continue
        if (_point_to_segment(base, seg) <= FLOAT_TOUCH_PX
                and _point_to_segment(tip, seg) <= FLOAT_TOUCH_PX):
            return True
    return False


def _is_arrowhead_region(region, tri_points):
    """이 닫힌 영역이 **화살촉 자신**인가. 순수 함수 — 위 `_tip_alignment_rows` 주석이 정본."""
    pts = region.get("pts") or []
    if len(pts) != 3:
        return False
    return all(any(_distance(p, q) < 0.01 for q in tri_points) for p in pts)


def _tip_alignment_rows(svg):
    """화살촉 **끝점**이 자기 기준선(치수보조선·외형선)에 정확히 닿는지 잰다.

    열린 날 2026-07-29. `fig-continuum-vs-rarefied` 의 치수 화살촉 8곳이 전부 치수보조선을
    **2px씩 지나쳐** 있었는데, 소스로는 안 보이고 렌더 PNG에서야 드러났다. 사용자 지적은
    한 삽화였지만 *같은 값으로 8곳 전부* 어긋난 것은 인스턴스가 아니라 **부류**라는 뜻이다.

    빌드에 이미 있는 `figure-lint G1` 은 **선 끝이 화살촉 밑변을 지나치는 것**(stem 쪽)만 본다.
    반대편인 **끝점 ↔ 기준선**은 어느 검사도 보지 않았다 — 그래서 8곳이 통과했다.
    "빠뜨렸다"가 아니라 *빠뜨려도 통과되는 구조*가 원인이다(규칙 7 ⑷).

    판정: 끝점이 기준선의 stroke 띠(±sw/2) 밖으로 TIP_TOL_PX 넘게 나가면 결함.
      overshoot > 0  끝점이 선을 **지나침**
      overshoot < 0  끝점이 선에 **못 미침**
    """
    triangles = _filled_triangles(svg)
    markers = _marker_circles(svg)
    tri_points = [p for _, _, pts in triangles for p in pts]
    # ★★ **화살촉은 「패널 내용」이 아니다** (열린 날 2026-08-25 — 이 자의 blind spot).
    #   `_head_tag` 가 화살촉에 자기 색 테두리를 두르면서(2026-08-25) 삼각형이 **닫힌 영역**
    #   으로도 잡히게 됐다. 그러면 `_is_panel_divider` 의 ⑵「양쪽에 패널 내용이 있다」가
    #   **자기 화살촉 둘로** 충족돼, 떠 있는 치수보조선이 통째로 칸막이로 오인된다.
    #   실측: `svg_dimension` 출력의 꼭짓점을 8px 더 밀어도 **0건**이 나왔다 —
    #   「0건이 아니라 한 건도 안 본 것」의 전형이고, 그 사이 생성기는 꼭짓점을 11.03px
    #   지나치게 찍고 있었다. 잠금은 `test_svg_generators_pass_their_own_rulers` 의 양성 대조군.
    containers = [c for c in _closed_regions(svg)
                  if not _is_arrowhead_region(c, tri_points)]
    segments = []
    for seg, width in _segments_with_stroke(svg):
        head, tail = (seg[0], seg[1]), (seg[2], seg[3])
        if _distance(head, tail) < 1e-6:
            continue
        # 화살촉 자신의 변은 기준선이 아니다.
        if (any(_distance(head, p) < 0.01 for p in tri_points)
                and any(_distance(tail, p) < 0.01 for p in tri_points)):
            continue
        segments.append((seg, width))
    raw_segments = [seg for seg, _ in segments]

    rows = []
    for base, tip, _pts in triangles:
        axis = (tip[0] - base[0], tip[1] - base[1])
        axis_len = math.hypot(*axis)
        if axis_len < 1e-6:
            continue
        ux, uy = axis[0] / axis_len, axis[1] / axis_len
        if _runs_along_an_edge(base, tip, ux, uy, segments):
            continue           # 면을 따라 흐르는 전단 화살표 — 위 독스트링이 정본
        if any(abs(_distance(tip, (cx, cy)) - r) <= TIP_TOL_PX for cx, cy, r in markers):
            continue           # 표식 원의 테두리에 착지한 화살촉 — 자기 기준선은 그 원이다
        walls = _container_walls(base, containers)
        best = None
        for seg, width in segments:
            if any(_same_segment(seg, wall) for wall in walls):
                continue       # 자기를 담고 있는 칸의 벽 — 그건 겨냥한 대상이 아니다
            if _is_panel_divider(seg, raw_segments, containers):
                continue       # 패널 칸막이 — 위 `_is_panel_divider` 독스트링이 정본
            dx, dy = seg[2] - seg[0], seg[3] - seg[1]
            seg_len = math.hypot(dx, dy)
            vx, vy = dx / seg_len, dy / seg_len
            if abs(ux * vx + uy * vy) > 0.4:
                continue           # 축과 나란한 선은 기준선이 아니라 stem 쪽이다
            nx, ny = -vy, vx       # 기준선의 법선
            denom = ux * nx + uy * ny
            if abs(denom) < 1e-9:
                continue
            signed = (tip[0] - seg[0]) * nx + (tip[1] - seg[1]) * ny
            overshoot = signed / denom
            if abs(overshoot) > TIP_SEARCH_PX:
                continue
            cross = (tip[0] - overshoot * ux, tip[1] - overshoot * uy)
            along = ((cross[0] - seg[0]) * vx + (cross[1] - seg[1]) * vy) / seg_len
            if not -0.02 <= along <= 1.02:
                continue           # 교차점이 그 선분의 밖이면 그 선은 기준선이 아니다
            if best is None or abs(overshoot) < abs(best[0]):
                best = (overshoot, seg, width)
        if best is None:
            continue               # 닿을 기준선이 없는 화살표(자유 방향 표시)는 대상이 아니다
        overshoot, seg, width = best
        if abs(overshoot) > width / 2.0 + TIP_TOL_PX:
            rows.append((tip, overshoot, width, seg))
    return rows


def _point_in_polygon(pt, pts):
    """광선 투사. 경계 위의 점은 안쪽으로 친다(라벨 중심이 변에 걸리는 일은 없다)."""
    x, y = pt
    inside = False
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        if (y1 > y) != (y2 > y):
            xc = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xc:
                inside = not inside
    return inside


def _closed_regions(svg):
    """라벨을 **담고 있을 수 있는** 닫힌 도형과 그 자신의 변들.

    ★ 왜 필요한가 (열린 날 2026-07-30, 사용자 지적이 아니라 도구 자체의 오탐):
        이 감사는 '라벨에서 가장 가까운 **아무** 선분'까지의 거리를 1em과 견줬다.
        그런데 막대그래프 칸·상자 안에 든 라벨은 **자기를 담은 칸의 변**이 가장 가깝다.
        `fig-two-ledgers` 의 `KE = 5 kJ`(fs 16.5)는 높이 40px 짜리 막대 칸 한가운데 있는데,
        위아래로 16.5px씩 띄우는 것은 **기하학적으로 불가능**하다 — 칸이 그만큼 안 크다.
        그런데도 매번 '기준 미달'로 신고돼, 실측하면 ch01 152 · ch02 141 · ch03 40 ·
        ch04 49 · ch05 9 = **391건**이 쌓였다. 즉 어느 챕터도 만족한 적이 없었다.

        **'전 챕터가 못 지키는 기준'은 대개 데이터가 아니라 자가 틀린 것이다.**
        이 상태로 데이터를 '고치면' 라벨을 자기 칸 밖으로 밀어내 진짜 결함을 만든다.
        그래서 자를 먼저 고친다 — 담은 칸에 대해서는 **칸이 허용하는 만큼**만 요구한다.

    반환: {"pts": 다각형 꼭짓점, "bbox": (x0,y0,x1,y1)}
    선분을 내놓지 않는 도형(stroke 없는 rect 등)은 애초에 거리 계산 대상이 아니라 뺀다.
    """
    regions = []

    def add(pts):
        if len(pts) < 3:
            return
        xs, ys = zip(*pts)
        regions.append({"pts": pts, "bbox": (min(xs), min(ys), max(xs), max(ys))})

    for m in re.finditer(r"<rect([^>]*?)/?>", svg):
        a = m.group(1)
        if _effective(svg, m.start(), a, "stroke") in (None, "none"):
            continue
        x, y = float(_attr(a, "x", "0")), float(_attr(a, "y", "0"))
        w, h = float(_attr(a, "width", "0")), float(_attr(a, "height", "0"))
        if w > 0 and h > 0:
            add([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
    for m in re.finditer(r"<path([^>]*?)/?>", svg):
        dstr = _attr(m.group(1), "d")
        if not dstr or not re.search(r"[Zz]", dstr):
            continue          # 닫히지 않은 path는 무엇도 담지 못한다
        segs = _path_polyline(dstr)
        add([(s[0], s[1]) for s in segs])
    return regions


# ★ 패널·상자의 **제목/머리말**은 0.5em (사용자 승인 2026-07-30).
#
# 왜 1em 이 아닌가 — 요구치가 `1em × 그 글자의 font-size` 라서 **글자가 클수록 더 많이 띄우라**고
# 요구한다. 그런데 패널 제목은 자기 패널에 **붙어 있어야** 무엇의 제목인지 읽힌다.
# 실측: `fig-heat-modes` 의 `전도`(fs 23)는 패널 위 12.5px 인데 규칙은 23px 을 요구했다 —
# 그대로 맞추면 제목이 패널에서 **지금의 2배** 멀어진다.
#
# 결정적 근거(2026-07-30 육안 61건 대조): 눈으로 잡힌 라벨 배치 결함 3건(R5·R6·R7)은
# 이 목록에 **하나도 없었고**, 목록이 지목한 삽화들은 렌더에서 멀쩡했다.
# 즉 이 자는 '보기 나쁜 것'을 못 잡고 '보기 괜찮은 것'만 잡고 있었다.
#
# ★ 완화가 아니라 **역할 분리**다. 화살표·치수선에 붙은 라벨은 1.0em 그대로다 —
# 거기서는 1em 이 실제로 눈에 보이는 결함을 잡는다. AGENTS 가 이미 쓰는
# `제목–부제 0.5em` 을 재사용하므로 새 상수도 아니다.
PANEL_TITLE_EM = 0.5
# 칸에서 이보다 멀면 그 칸의 제목으로 보지 않는다(멀면 어차피 1em 을 이미 만족한다).
PANEL_TITLE_MAX_OFFSET_EM = 2.0


def _box_contains(outer, inner):
    if not (outer[0] <= inner[0] and outer[1] <= inner[1]
            and outer[2] >= inner[2] and outer[3] >= inner[3]):
        return False
    return ((outer[2] - outer[0]) * (outer[3] - outer[1])
            > (inner[2] - inner[0]) * (inner[3] - inner[1]))


def _title_bands(regions):
    """제목이 아우를 수 있는 **칸의 줄**. 나란한 칸 여럿을 하나로 묶는다.

    ★ 왜 필요한가 (열린 날 2026-07-30, 사용자 지적이 아니라 도구 자체의 오탐):
        제목·캡션이 **나란한 칸 두 개를 아울러** 가운데 놓이면 그 중심은 두 칸 *사이*라
        어느 칸의 가로 범위에도 안 들어간다. 그래서 `fig-thermal-equilibrium-snapshots` 의
        '다린 셔츠'(칸 두 개의 머리말)와 '같은 온도, 전달 멈춤'(칸 두 개의 캡션)이
        제목으로 인정되지 않아 1em(14.5·14)을 요구받았다. 칸 사이는 34px 인데 요구치는
        14.5+14.79+14.5 = 43.8px — **데이터로는 못 고치는 신고**였다.
        같은 삽화의 '보냉팩' 머리말은 우연히 한쪽 칸의 가로 범위 안에 떨어져 통과했다.
        즉 같은 역할의 라벨이 **우연한 x 좌표**로 다른 자를 받고 있었다.

    ★ 묶음은 **더하는** 것이지 대신하는 것이 아니다. 처음엔 개별 칸을 묶음으로 갈아치웠는데,
      묶기 전에 '다른 칸을 품는 칸'(패널 테두리)을 뺐더니 **패널 제목이 갈 곳을 잃어**
      ch02 에서 통과하던 제목 6건(`전도`·`대류`·`복사`·`처음`…)이 한꺼번에 신고됐다.
      테두리를 빼는 것 자체는 옳다(넣으면 패널 하나가 모든 칸을 삼켜 '칸 안'으로 뒤집힌다) —
      틀린 것은 개별 칸을 후보에서 지운 쪽이다.
    """
    boxes = [r["bbox"] for r in regions]
    leaves = [box for i, box in enumerate(boxes)
              if not any(j != i and _box_contains(box, other)
                         for j, other in enumerate(boxes))]
    bands = []
    for x0, y0, x1, y1 in leaves:
        for band in bands:
            share = min(y1, band[3]) - max(y0, band[1])
            if share > 0.5 * min(y1 - y0, band[3] - band[1]):
                band[0], band[1] = min(band[0], x0), min(band[1], y0)
                band[2], band[3] = max(band[2], x1), max(band[3], y1)
                break
        else:
            bands.append([x0, y0, x1, y1])
    return [tuple(b) for b in bands] + boxes


def _is_panel_title(box, fs, regions):
    """라벨이 어떤 칸의 **바로 위나 아래**에 그 칸의 가로 범위 안에서 놓였는가.

    '그 칸에 속한 글'의 기계적 정의다 — 제목이든 머리말이든 설명 캡션이든 공통점은
    ⑴ 칸 밖이고 ⑵ 세로로 칸에 **바로 잇닿아** 있으며 ⑶ 그 칸의 가로 범위 안에 중심이 있다는 것이다.
    칸 안이면 내용이고(그건 「칸 안」 상한이 따로 본다), 멀리 떨어져 있으면 그 칸의 글이 아니다.

    ★ 위만 볼 것인가 아래도 볼 것인가 (2026-07-30 판단) — **아래도 본다.**
      `fig-thermal-equilibrium-snapshots` 의 `큰 온도차, 빠른 전달` 은 패널 **아래**에 붙은
      설명인데, 위만 인정하면 같은 성격의 글이 위/아래에 따라 다른 자를 받는다.
      AGENTS 도 `제목–부제 0.5em` 과 `캡션 줄 간격 0.5em` 을 같은 값으로 쓴다.
    """
    cx = (box[0] + box[2]) / 2.0
    for band in _title_bands(regions):
        x0, y0, x1, y1 = band
        if not (x0 <= cx <= x1):
            continue                                   # 그 칸의 가로 범위 밖이다
        if box[1] < y1 and box[3] > y0:
            continue                                   # 칸과 세로로 겹친다 = 칸 안이다
        gap = (y0 - box[3]) if box[3] <= y0 else (box[1] - y1)
        if gap > PANEL_TITLE_MAX_OFFSET_EM * fs:
            continue                                   # 너무 멀면 그 칸의 글이 아니다
        return True
    return False


def _required_gap(box, fs, regions, unit_box=None):
    """이 라벨에 **요구할 수 있는** 간격과, 값이 깎였으면 그 사유.

    ★ 요구치는 선분별이 아니라 **라벨별 상한**이다.
      라벨이 어떤 칸 안에 갇혀 있으면, 그 칸이 줄 수 있는 최대 여유보다 큰 간격은
      *칸 밖의 무엇에 대해서도* 달성할 수 없다. 처음엔 '담은 칸의 변'만 요구치를 깎았는데,
      칸 모서리와 **좌표만 겹치는 별개의 선**(막대 위를 가로지르는 비교선 등)이 남아
      같은 라벨이 그대로 신고됐다(2026-07-30 ch02 실측: 141 → 110, 오탐이 그대로).
      선분의 정체를 맞히려 들 것이 아니라 **라벨이 움직일 수 있는 범위**를 재는 것이 맞다.

    칸이 줄 수 있는 최대 = 라벨을 칸 한가운데 두었을 때의 여유(가로·세로 중 작은 쪽).
    여러 칸에 겹쳐 들어 있으면 **가장 작은 칸**이 라벨을 묶으므로 그쪽을 쓴다.
    """
    want = LABEL_TO_SHAPE_EM * fs
    note = ""
    if _is_panel_title(box, fs, regions):
        want, note = PANEL_TITLE_EM * fs, "제목"
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    # ★ 여유는 **조판 단위**로 잰다. 분수의 분자만 떼어 재면 "아직 여유가 있다"가 나오지만
    #   실제로 움직일 수 있는 폭은 분자+분수선+분모가 함께 결정한다(ch05 실측 24.6 vs 10.3).
    ref = unit_box or box
    cap = None
    for region in regions:
        if not _point_in_polygon((cx, cy), region["pts"]):
            continue
        x0, y0, x1, y1 = region["bbox"]
        room = min((x1 - x0 - (ref[2] - ref[0])) / 2.0, (y1 - y0 - (ref[3] - ref[1])) / 2.0)
        room = max(0.0, room)
        cap = room if cap is None else min(cap, room)
    if cap is not None and cap < want:
        return cap, "칸 안"
    return want, note


def _texts_with_weight(svg):
    """_svg_texts 결과에 bold 여부를 붙인다 — 원본에 font-weight가 없어서 직접 읽는다."""
    out = []
    for text in _svg_texts(svg):
        tag = svg[text["pos"]:svg.find(">", text["pos"]) + 1]
        text["bold"] = "font-weight='700'" in tag or 'font-weight="700"' in tag
        out.append(text)
    return out


def audit(chapter_path, wanted=None):
    data = json.loads(Path(chapter_path).read_text(encoding="utf-8"))
    rows, gap_rows, tier_rows, tip_rows, dim_rows = [], [], [], [], []
    arrow_rows, box_rows, order_rows, density_rows = [], [], [], []
    pair_rows = []
    for diagram in iter_diagrams(data):
        fig_id = diagram.get("id") or "?"
        if wanted and fig_id not in wanted:
            continue
        svg = diagram["svg"]
        vb = _viewbox(svg)
        if not vb:
            continue
        vx, vy, vw, vh = vb
        top, bottom = _content_extent(svg, vb)
        if top is None:
            continue
        pad_top = top - vy
        pad_bottom = (vy + vh) - bottom
        rows.append((fig_id, vw, vh, pad_top, pad_bottom, pad_bottom - pad_top))

        # 화살표 크기 — 화면 실효 px 로 잰다(글자·치수와 같은 자).
        for arrow in arrow_geometry(svg):
            scale = 612.0 / vw
            arrow_rows.append((fig_id, arrow["length"] * scale, arrow["width"] * scale,
                               None if arrow["tail"] is None else arrow["tail"] * scale,
                               arrow["tip"]))

        segments = _svg_segments(svg)
        regions = _closed_regions(svg)
        # 분수선은 자기 수식 그룹(`<g class='frac'>`) 안의 글자에게는 도형이 아니다 —
        # 분자·분모는 0.12em, 옆에 선 항은 0.5em 남짓이 **정상 조판**이라 1em 자를 들이대면
        # 전부 미달로 나온다. 자를 느슨하게 하는 대신 **면제 범위를 그룹 안으로 한정**한다.
        # (빌드 F1 도 같은 판정을 쓴다 — 두 자가 갈라지면 그게 이 도구의 다음 오탐이 된다.)
        bars = _fraction_bars(svg)
        units = fraction_unit_boxes(svg)
        for text in _svg_texts(svg):
            box = _text_bbox(text)
            own = {seg for (gs, ge), seg in bars if gs <= text["pos"] < ge}
            unit = next((ub for (gs, ge), ub in units if gs <= text["pos"] < ge), None)
            ranked = sorted(((_segment_to_rect_distance(s, box), s)
                             for s in segments if s not in own),
                            key=lambda p: p[0])
            if not ranked:
                continue
            nearest, seg = ranked[0]
            want, why = _required_gap(box, text["fs"], regions, unit_box=unit)
            if want - nearest > GAP_TOL_PX:
                gap_rows.append((fig_id, text["s"][:18], nearest, want, text["fs"], seg, why))

        for tip, overshoot, width, seg in _tip_alignment_rows(svg):
            tip_rows.append((fig_id, tip, overshoot, width, seg))

        # 칸 안 덩어리의 세로 중앙 (C28) — **문턱 아래 값까지 전부 찍는다.**
        # 규격을 데이터로 정하려면 걸린 것만이 아니라 분포가 보여야 한다(규칙 11).
        for cell, block, gap_top, gap_bot, off, fs, preview in figure_box_centering(svg):
            box_rows.append((fig_id, cell, block, gap_top, gap_bot, off, fs, preview))
        # C31 — 짝 라벨의 거리 **비교**(하한이 아니다). 판정 근거는 checks_svg 의 주석이 정본.
        for why, preview in figure_label_pair_gap_hits(svg):
            pair_rows.append((fig_id, why, preview))
        density_rows.append((drawable_count(svg), fig_id, vw, vh))
        for weak, strong, ytop_a, ytop_b in symbol_below_caption_rows(svg):
            order_rows.append((fig_id, weak, strong, ytop_a, ytop_b))

        # 치수보조선 — 물체에서 띄운 간격과 치수선을 지나 더 나간 넘김(화면 실효 px)
        for row in dim_extension_rows(svg):
            dim_rows.append((fig_id, row["seg"], row["gap"], row["over"]))

        # 위계: 설명 캡션은 라벨보다 작아야 한다. 같으면 독자가 경중을 못 가린다.
        weighted = _texts_with_weight(svg)
        captions = [t for t in weighted if _is_caption(t)]
        labels = [t for t in weighted if not _is_caption(t) and not t["bold"]]
        if captions and labels:
            label_max = max(t["fs"] for t in labels)
            for cap in captions:
                if cap["fs"] >= label_max:
                    tier_rows.append((fig_id, cap["s"][:26], cap["fs"], label_max, vw))

    print("=" * 78)
    print("세로 균형 — 위 여백 vs 아래 여백 (배경 테두리 제외)")
    print("=" * 78)
    print(f"{'삽화':38} {'viewBox':>11} {'위':>7} {'아래':>7} {'차이':>7}")
    off = 0
    for fig_id, vw, vh, pt, pb, diff in rows:
        mark = ""
        if abs(diff) > BALANCE_TOL_PX:
            mark = "  <-- 아래로" if diff > 0 else "  <-- 위로"
            off += 1
        print(f"{fig_id:38} {vw:5.0f}x{vh:<5.0f} {pt:7.1f} {pb:7.1f} {diff:+7.1f}{mark}")
    print(f"\n균형 이탈 {off}건 / {len(rows)}건 (허용치 ±{BALANCE_TOL_PX:g}px)")

    print()
    print("=" * 78)
    print(f"라벨-도형 간격이 기준({LABEL_TO_SHAPE_EM:g}em) 미만인 글자")
    print("=" * 78)
    # 가장 가까운 선분을 함께 찍는다 — 어떤 도형에 붙었는지 모르면 '결함'인지
    # '치수 라벨이 자기 치수선 화살촉 옆에 있는 정상 배치'인지 판정할 수 없다(규칙 11).
    for fig_id, text, nearest, want, fs, seg, why in gap_rows:
        seg_s = f"({seg[0]:g},{seg[1]:g})-({seg[2]:g},{seg[3]:g})"
        tag = f" [{why}]" if why else ""
        print(f"{fig_id:38} {text!r:22} {nearest:6.2f}px (기준 {want:5.2f} · fs {fs:g}){tag}  최근접 {seg_s}")
    print(f"\n기준 미달 {len(gap_rows)}건")

    print()
    print("=" * 78)
    print(f"짝 라벨 — 같은 색·크기·굵기인데 도형과의 거리가 {LABEL_PAIR_RATIO_MAX:g}배 넘게"
          " 갈린 자리 (후보 · 판정은 사람이)")
    print("=" * 78)
    for fig_id, why, preview in pair_rows:
        print(f"{fig_id:38} {preview}")
        print(f"{'':38} {why}")
    print(f"\n거리 갈림 {len(pair_rows)}건")

    print()
    print("=" * 78)
    print("글자 위계 — 설명 캡션이 라벨보다 작지 않은 삽화 (화면 실효 px 병기)")
    print("=" * 78)
    for fig_id, text, cap_fs, label_fs, vw in tier_rows:
        eff = cap_fs * 612.0 / vw
        print(f"{fig_id:38} {text!r:30} 캡션 fs {cap_fs:g}(실효 {eff:4.1f}) >= 라벨 fs {label_fs:g}")
    print(f"\n위계 없음 {len(tier_rows)}건")

    print()
    print("=" * 78)
    print(f"치수보조선 — 물체에서 띄운 간격({DIM_GAP_SCREEN_PX:g}px)과 치수선을 지나는 넘김"
          f"({DIM_OVERSHOOT_SCREEN_PX:g}px) · 화면 실효 px")
    print("=" * 78)
    bad_dim = 0
    for fig_id, seg, gap, over in dim_rows:
        gap_s = "  없음" if gap is None else f"{gap:6.2f}"
        flags = []
        if gap is not None and abs(gap - DIM_GAP_SCREEN_PX) > DIM_GEOM_TOL_PX:
            flags.append("간격")
        if abs(over - DIM_OVERSHOOT_SCREEN_PX) > DIM_GEOM_TOL_PX:
            flags.append("넘김")
        if flags:
            bad_dim += 1
        print(f"{fig_id:38} ({seg[0]:5.0f},{seg[1]:5.0f})-({seg[2]:5.0f},{seg[3]:5.0f})"
              f"  간격 {gap_s}  넘김 {over:6.2f}  {'·'.join(flags)}")
    print(f"\n규격 이탈 {bad_dim}건 / {len(dim_rows)}건 (허용 ±{DIM_GEOM_TOL_PX:g}px)")

    # ★★ `--fail-only` — 아래 다섯 절은 **전부 참고용**(위반이 아니라 분포·목록을 보여 준다).
    #   합쳐 60~90줄이라 감사를 한 번 부를 때마다 1~3k 토큰을 먹는데, 대개는 그중 한 절만 본다.
    #   신설 이유(2026-08-12, 사용자: *[발화 생략]*).
    #   ★ 위반을 세는 절(세로 균형·라벨 간격·치수보조선·글자 위계)은 **끄지 않는다** —
    #     그건 조용해지면 안 되는 자리다.
    # ★★★ **위반이 있는 절은 참고 절이라도 낸다** (고침 2026-08-13).
    #   위 분류가 틀렸다 — 「화살촉 끝점」은 분포가 아니라 **위반을 세는 절**인데 참고로 묶여
    #   있었다. 그래서 ch06 펌프 화살표가 `12.00px 못 미침` 으로 **정확히 신고되고 있었는데도**
    #   사람에게 한 번도 도달하지 않았다(이 리포의 기본 호출이 `--fail-only` 다).
    #   **빠뜨림이 아니라 신고가 닿지 않는 구조**였고, 사용자는 같은 자리를 두 번 지적했다.
    #   → `--fail-only` 는 이제 **통과한 것만** 줄인다. 위반이 하나라도 있으면 그 절은 나온다.
    if FAIL_ONLY:
        box_bad = [r for r in box_rows if abs(r[5]) > BOX_CENTER_TOL_EM * r[6]]
        if tip_rows:
            print()
            print("=" * 78)
            print("화살촉 끝점 — 자기 기준선에 닿았는가 (참고 절이지만 **위반이라 낸다**)")
            print("=" * 78)
            for fig_id, tip, overshoot, width, seg in tip_rows:
                seg_s = f"({seg[0]:g},{seg[1]:g})-({seg[2]:g},{seg[3]:g})"
                verdict = "지나침" if overshoot > 0 else "못 미침"
                print(f"{fig_id:38} 끝점({tip[0]:6.1f},{tip[1]:6.1f}) {abs(overshoot):5.2f}px"
                      f" {verdict}  (기준선 sw {width:g} ·"
                      f" 허용 {width / 2.0 + TIP_TOL_PX:.2f})  {seg_s}")
            print(f"\n끝점 어긋남 {len(tip_rows)}건")
        if box_bad:
            print(f"\n[칸 안 덩어리] 중앙 이탈 {len(box_bad)}건"
                  " — 빌드 C28 이 같은 것을 error 로 막는다")
        quiet = ["라벨 순서", "삽화 밀도", "화살표 크기"]
        if not tip_rows:
            quiet.append("화살촉 끝점")
        if not box_bad:
            quiet.append("칸 안 덩어리")
        print("\n(위반 없는 참고 절 생략 — " + "·".join(quiet) + ". 보려면 --fail-only 없이)")
        return
    print()
    print("=" * 78)
    print("칸 안 덩어리 — 글자가 칸의 세로 중앙인가 (C28)")
    print("=" * 78)
    over = 0
    for fig_id, cell, block, gap_top, gap_bot, off, fs, preview in box_rows:
        tol = BOX_CENTER_TOL_EM * fs
        flag = ""
        if abs(off) > tol:
            over += 1
            flag = "  <-- " + ("위로" if off < 0 else "아래로")
        print(f"{fig_id:30} 칸 y={cell[1]:6.1f}~{cell[3]:6.1f} 덩어리 {block:5.1f}"
              f"  위 {gap_top:6.2f} 아래 {gap_bot:6.2f}  어긋남 {off:+6.2f}"
              f" (허용 {tol:.1f})  {preview[:26]}{flag}")
    print(f"\n중앙 이탈 {over}건 / {len(box_rows)}건"
          f" (허용 {BOX_CENTER_TOL_EM:g}em · 칸/덩어리 높이비 {BOX_CENTER_MAX_RATIO:g} 이하만 본다)")

    print()
    print("=" * 78)
    print("라벨 순서 — 굵은 글자(기호·제목)가 안 굵은 글자 **아래**에 놓인 자리 (판정은 사람이)")
    print("=" * 78)
    for fig_id, weak, strong, ya, yb in order_rows:
        print(f"{fig_id:30} 위 {ya:7.1f} {weak[:22]:24} → 아래 {yb:7.1f} {strong[:22]}")
    print(f"\n후보 {len(order_rows)}건 — '이름 위 / 기호 아래'가 옳은 자리도 있다(흐름도 등). 눈으로 볼 것")

    print()
    print("=" * 78)
    print("삽화 밀도 — 그리기 요소 수 (적은 순 · 판정은 사람이)")
    print("=" * 78)
    for n, fig_id, vw, vh in sorted(density_rows):
        print(f"{n:5d}  {fig_id:34} {vw:.0f}x{vh:.0f}")
    counts = sorted(r[0] for r in density_rows)
    if counts:
        mid = counts[len(counts) // 2]
        print(f"\n요소 수: 최소 {counts[0]} · 하위 4분위 {counts[len(counts) // 4]}"
              f" · 중앙 {mid} · 최대 {counts[-1]}  (n={len(counts)})")

    print()
    print("=" * 78)
    print("화살촉 끝점 — 자기 기준선(치수보조선·외형선)에 닿았는가")
    print("=" * 78)
    # 어느 선을 기준으로 판정했는지 함께 찍는다 — 그게 없으면 사람이 판정을 검증할 수 없다(규칙 11).
    for fig_id, tip, overshoot, width, seg in tip_rows:
        seg_s = f"({seg[0]:g},{seg[1]:g})-({seg[2]:g},{seg[3]:g})"
        verdict = "지나침" if overshoot > 0 else "못 미침"
        print(f"{fig_id:38} 끝점({tip[0]:6.1f},{tip[1]:6.1f}) {abs(overshoot):5.2f}px {verdict}"
              f"  (기준선 sw {width:g} · 허용 {width / 2.0 + TIP_TOL_PX:.2f})  {seg_s}")
    print(f"\n끝점 어긋남 {len(tip_rows)}건")

    print()
    print("=" * 78)
    print("화살표 크기 — 화살촉 길이·폭과 꼬리 길이 (화면 실효 px · 글자와 같은 자)")
    print("=" * 78)
    lengths = sorted(r[1] for r in arrow_rows)
    tails = sorted(r[3] for r in arrow_rows if r[3] is not None)
    for fig_id, length, width, tail, tip in arrow_rows:
        tail_s = "  없음" if tail is None else f"{tail:6.1f}"
        print(f"{fig_id:38} 촉 길이 {length:5.1f} · 폭 {width:5.1f} · 꼬리 {tail_s}"
              f"   끝점({tip[0]:6.1f},{tip[1]:6.1f})")

    def _stat(name, values):
        if not values:
            print(f"  {name}: 없음")
            return
        mid = values[len(values) // 2]
        print(f"  {name}: 최소 {values[0]:.1f} · 중앙 {mid:.1f} · 최대 {values[-1]:.1f}"
              f"  (n={len(values)})")
    print()
    _stat("화살촉 길이", lengths)
    _stat("꼬리 길이", tails)
    return rows, gap_rows, tier_rows, tip_rows, dim_rows


def balance_rows(chapter_path):
    """세로 균형만 잰다 — **전 과목 순회용**이라 무거운 절(간격·화살촉·칸)은 안 돈다.

    ★ 열린 날 2026-09-08. 이 자는 `chapter` 를 **필수 위치 인자**로 받아서
      전 과목 순회가 아예 불가능했다(순회기에 물리면 21과목이 전부 `exit 2`).
      그래서 「위 7.0 / 아래 30.4」 같은 쏠림이 **아무 데서도 안 세어졌다** —
      감사가 있는데 한 챕터씩 손으로 부르지 않으면 안 도는 상태였다.
    """
    try:
        data = json.loads(Path(chapter_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for diagram in iter_diagrams(data):
        svg = diagram.get("svg") or ""
        vb = _viewbox(svg) if svg else None
        if not vb:
            continue
        vx, vy, vw, vh = vb
        top, bottom = _content_extent(svg, vb)
        if top is None:
            continue
        pad_top, pad_bottom = top - vy, (vy + vh) - bottom
        out.append((diagram.get("id") or "?", vw, vh, pad_top, pad_bottom,
                    pad_bottom - pad_top))
    return out


def sweep_all():
    """전 과목 세로 균형 — 위반만 찍고, **훑은 수를 함께 낸다**(0 이 «없다» 가 아니게)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import audit_content                                                     # noqa: E402
    subjects = audit_content.subject_dirs()
    total = off = 0
    for folder in subjects:
        name = os.path.basename(folder)
        hits = []
        for fname in sorted(n for n in os.listdir(folder)
                            if re.fullmatch(r"ch\d{2}\.json", n)):
            for fig_id, vw, vh, pt, pb, diff in balance_rows(os.path.join(folder, fname)):
                total += 1
                if abs(diff) > BALANCE_TOL_PX:
                    off += 1
                    hits.append((fname[:-5], fig_id, vw, vh, pt, pb, diff))
        if hits:
            print(f"\n-- {name} -- {len(hits)}건")
            for ch, fig_id, vw, vh, pt, pb, diff in hits:
                print(f"   {ch} {fig_id:36} {vw:5.0f}x{vh:<5.0f}"
                      f" 위 {pt:6.1f} 아래 {pb:6.1f} 차이 {diff:+7.1f}")
    print(f"\n합계 — 균형 이탈 {off}건 / 삽화 {total}개 · 훑은 과목 {len(subjects)}개"
          f" (허용치 ±{BALANCE_TOL_PX:g}px)")
    if total == 0:
        sys.exit("삽화를 한 개도 안 봤다 — 순회 범위를 확인할 것(0 이 «없다» 가 아니다)")
    return 0


def main():
    parser = argparse.ArgumentParser(description="삽화 세로 균형·라벨 간격 감사 (읽기 전용)")
    parser.add_argument("chapter", nargs="?",
                        help="chapter JSON path, relative to repository root")
    parser.add_argument("--all", action="store_true",
                        help="전 과목을 훑어 **세로 균형 이탈만** 낸다(무거운 절은 안 돈다)")
    parser.add_argument("--id", dest="ids", action="append", help="특정 삽화만 (반복 가능)")
    parser.add_argument("--fail-only", action="store_true",
                        help="위반을 세는 절만 낸다 — 참고용 5개 절(칸 안·라벨 순서·밀도·"
                             "화살촉 끝점·화살표 크기)을 생략해 출력을 1/3 로 줄인다")
    global FAIL_ONLY
    args = parser.parse_args()
    FAIL_ONLY = args.fail_only
    if args.all:
        return sweep_all()
    if not args.chapter:
        parser.error("chapter 를 주거나 --all 을 줄 것")
    audit(ROOT / args.chapter, set(args.ids) if args.ids else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
