# -*- coding: utf-8 -*-
"""근접성 위계(상한) 후보를 **대상이 판별되는 것만** 대상 쪽으로 당긴다 — 나머지는 사람 몫으로 분류해 낸다.

왜(2026-09-24, 클라우드 큐 (5)~(26) 근접성 소급): `audit_figure_balance --proximity` 가 전 과목
2,700여 건 후보를 냈다(라벨 상한 1636 · 화살표 사선 374 · 다른 색 최근접 301 · 제목 407). 그 자는
**라벨의 대상을 모른다** — 최근접 아무 선분까지 잰다. 그래서 대상을 모르는 채 「가장 가까운 선 쪽으로」
당기면 영역 라벨(`습증기 영역`)을 돔 선에 붙이고 축 이름을 엉뚱한 선에 붙인다 — 틀린 그림을 만든다.
형제 도구 `fix_figure_label_gap.py`(하한 쪽 · 밀기)와 같은 안전 장치를 쓰되, 방향은 당기기다.

대상을 판별할 수 있는 둘만 옮긴다:
  ⑴ **유채색 낱말 라벨(4자 이상)** — 대상 = 같은 색 선분(규격: 색이 곧 대상 표지). 가장 가까운 같은 색
     선분 쪽으로 0.75em 이 될 때까지 당긴다. 「최근접이 다른 색」 후보도 이 이동으로 함께 닫힌다.
  ⑵ **짧은 라벨(3자 이하)은 옮기지 않는다** — 점 이름·축 이름·첨자라 대상이 점인지 선인지 축인지
     기계가 못 가린다(실측: 색 규칙·점 규칙 둘 다 틀린 대상으로 끌었다 — 아래 회귀 ⑹⑺). 채운 점이 이미
     1.0em 안이면 **자 사각**(자는 채운 점을 안 센다)으로 분류만 한다.
  ⑶ **화살표 라벨 사선** — 대상 = 그 화살표(자가 이미 찾는다). 화살표 축을 따라 미끄러뜨려 수선의 발을
     꼬리–끝점 구간 안으로 넣는다(축과의 수직 거리는 그대로).
분류만 하는 것: 축 이름(`class='axis-name'` — `checks_svg.axis_name_gap_issues` 가 따로 잰다) ·
  대상 불명(무채색 긴 라벨 · 점 없는 짧은 라벨) · 굵은 제목(배치를 바꿔야 한다) · 변환 먹은 글자.
옮긴 뒤 관문: 선 반대편으로 안 넘어간다 · 다른 글자와 겹치지 않는다 · viewBox 안 · 도형 경계에 안 걸친다 ·
  **빌드 검사(`check_svg`·`check_figure_lint`, strict 전부) 에러가 늘지 않는다** — 늘면 그 라벨을 되돌린다.

쓰기 규율: 기본은 보고만. `--apply` 로 쓴다. 과목은 인자로 받는다(공통 도구에 과목을 박지 않는다).
    python tools/fix_label_proximity.py "data/<과목>"                 # 보고(분류별 건수 + 사람 몫 목록)
    python tools/fix_label_proximity.py "data/<과목>" --apply --note "근접성 규격 소급(날짜) — …"
      (--apply 는 --note 필수 — 옮긴 삽화의 주인 항목에 changeNote 로 덧붙인다. 밑줄 금지)
    python tools/fix_label_proximity.py "data/<과목>/ch07.json" --list  # 사람 몫을 한 줄씩
못 보는 것: 렌더 결과(옮긴 라벨이 보기에 맞는가 — 사람) · 무채색 라벨의 대상 · 대상이 점도 선도 아닌 영역.
잠금 `test_checks.py::test_label_proximity_pulls_only_known_targets`.
"""
import argparse
import copy
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import audit_figure_balance as A                                           # noqa: E402
from buildlib.checks_svg import (  # noqa: E402
    AXIS_ARROW_MAX_EM, _axis_name_gaps, _drawable, _rect_x_rect, _tagged_group_spans, _segment_to_rect_distance, _svg_filled_shapes, _text_bbox,
    check_figure_lint, check_svg,
)
from buildlib.jsontext import write_chapter                             # noqa: E402
import set_change_notes as SCN                                           # noqa: E402
from fix_figure_label_gap import (  # noqa: E402
    _closest_point_on_segment, _rect_gap, _shift_box, _side_of, _straddles,
)

# 고른 값: 도달점을 상한 1.0em 에서 0.25em 안쪽으로 — 반올림·폭 추정 오차로 되튀지 않게, 하한 0.5em 보다는 멀게.
LAND_EM = 0.75
DOT_MAX_R = 6.0            # 고른 값: 상태점 표지 반지름 상한 — 이 리포 점 표지는 r 3~5, 전원 원(17)은 빼야 한다
SHORT_LABEL_MAX = 3        # 고른 값: 「1」「2s」「A」「4′」 같은 점 이름의 길이 — 한글 낱말 라벨(2음절+)과 가른다
STEP_PX = 0.5              # 고른 값: 형제 도구(fix_figure_label_gap)의 탐색 간격과 같다 — 좌표 반올림(0.01)보다 넉넉하고 선 굵기(2)의 1/4
TEXT_CLEAR_EM = 0.5        # 규격 「내용끼리 0.5em」 — 옮긴 글자는 다른 글자와 이보다 붙지 않는다(이미 붙어 있던 짝은 그 값)
VIEWBOX_MARGIN_PX = 2.0    # 고른 값: 형제 도구와 같은 값 — 글자 상자를 viewBox 가장자리에서 선 굵기만큼 띄운다
# 고른 값: 글자 사이가 이보다 좁으면 한 라벨의 조각(밑글자+첨자·단위)으로 본다 — 낱말 사이 띄어쓰기(~0.3em) 수준.
GLUED_EM = 0.35
# 고른 값: 같은 줄(세로로 겹침)에서 이 안에 이웃 글자가 있으면 한 식·한 문구의 조각으로 본다 — 식 조각 사이 공백(0.3~0.8em)을 덮는 1em.
SAME_LINE_EM = 1.0
# 고른 값: 위아래로 이 안에 가로가 겹치는 글자가 있으면 여러 줄 라벨의 한 줄로 본다 — 행간 1.2~1.5em 이면 상자 사이는
# 0.2~0.5em 이고, 도달점(LAND_EM)과 같게 둬 「한 줄만 옮겨 다른 줄과 떨어뜨리는」 거리보다 좁게 잡는다.
STACK_EM = 0.75
# 고른 값: 좌표 반올림(0.01)보다 넉넉하고 손 배치의 우연한 일치(보통 수 px)보다 좁게 — 눈금 라벨·주어진 값 열은
# 생성기가 같은 x 나 같은 y 로 찍는다.
ALIGN_EM = 0.1
# 고른 값: 규격 제목–내용 간격(1.5em) — 옮기기 전 이보다 가까운 다른 색 선은 라벨이 함께 가리킬 수 있는 이웃이라 멀어지면 안 된다.
KEEP_EM = 1.5

KINDS = {
    "moved": "옮김",
    "dot_ok": "자 사각 — 점 표지가 이미 1.0em 안(자는 채운 점을 안 센다)",
    "inside": "도형 안 이름표 — 대상은 감싼 도형(자는 도형 안을 못 본다)",
    "axis": "축 이름 — axis_name_gap 검사 몫",
    "unknown": "대상 불명 — 무채색 라벨 [사람]",
    "title": "굵은 제목 — 배치 판단 [사람]",
    "blocked": "당기면 관문에 걸림 [사람]",
    "transform": "변환 먹은 글자·삽화 [사람]",
}


def _dots(svg):
    """작은 채운 원(상태점 표지)의 (cx, cy, r). 변환 먹은 것은 뺀다(좌표를 믿을 수 없다)."""
    out = []
    for m in re.finditer(r"<circle\b([^>]*)/?>", _drawable(svg)):
        a = m.group(1)
        fill = (A._effective(svg, m.start(), a, "fill", "") or "").strip().lower()
        r = A._attr(a, "r")
        if not r or fill in ("", "none") or "transform" in a:
            continue
        try:
            rv = float(r)
        except ValueError:
            continue
        if rv <= DOT_MAX_R:
            out.append((float(A._attr(a, "cx", "0")), float(A._attr(a, "cy", "0")), rv, fill))
    return out


def _rect_to_dot(box, dot):
    cx, cy, r = dot[:3]
    dx = max(box[0] - cx, 0.0, cx - box[2])
    dy = max(box[1] - cy, 0.0, cy - box[3])
    return max(0.0, math.hypot(dx, dy) - r)


def _joined(box, fs, others):
    """이 글자가 다른 글자와 한 줄을 이루는 조각인가 — 붙어 있거나(GLUED_EM) 같은 줄에서 1em 안에 이웃이 있다.

    ★ 같은 줄 규칙(2026-09-24): 고체 ch02 `fig-p02-bracket` 에서 `F₁` 뒤의 `= 150 N` 만 끌려가 `= F₁50 N`
      으로 겹쳤다 — 두 조각 사이가 붙음 문턱보다 넓어 첫 가드를 빠져나갔다.
    ★ 여러 줄 규칙(2026-09-24 큐 (30)): 열역학 ch01 `fig-system-surrounding-boundary` 에서 두 줄 라벨
      `경계` / `(boundary)` 의 아랫줄만 끌려가 윗줄과 갈라졌다 — 위아래로 쌓인 줄은 같은 줄 규칙이 못 본다.
    """
    for o in others:
        gap = _rect_gap(box, o)
        if gap < GLUED_EM * fs:
            return True
        overlap_y = min(box[3], o[3]) - max(box[1], o[1])
        if overlap_y > 0.3 * fs and gap < SAME_LINE_EM * fs:
            return True
        overlap_x = min(box[2], o[2]) - max(box[0], o[0])
        if overlap_x > 0 and gap < STACK_EM * fs:
            return True
    return False


def _aligned(i, texts):
    """i 번 글자가 같은 크기의 다른 글자와 한 줄(같은 y)이나 한 열(같은 정렬·같은 x)에 서 있나 — 눈금·값 목록의 한 칸이다.

    왜(2026-09-24 큐 (30)): 열역학 ch03 `fig-ch03-p06` 의 가로축 눈금 `250°C`(200°C·220°C 와 같은 y)가 같은
    색 자료선 쪽으로 끌려갔고, `fig-ch03-p05` 의 주어진 값 열(`T = 25°C` · `P = 300 kPa`, 같은 x)에서 한 칸만 화살표로 갔다.
    """
    t = texts[i]
    for j, o in enumerate(texts):
        if j == i or abs(o["fs"] - t["fs"]) > 0.01:
            continue
        if abs(o["y"] - t["y"]) < ALIGN_EM * t["fs"]:
            return True
        if o.get("anchor") == t.get("anchor") and abs(o["x"] - t["x"]) < ALIGN_EM * t["fs"]:
            return True
    return False


def _enclosing_own_shape(i, boxes, shapes):
    """i 번 글자를 통째로 감싸고 다른 글자의 중심은 하나도 안 든 채운 도형이 있나 — 그 도형의 이름표다.

    왜(2026-09-24 큐 (30)): 열역학 ch01 `fig-zeroth-law-transitivity` 에서 원 C 안의 이름 `C(온도계)` 가
    같은 색 선(A–B 연결선) 쪽으로 끌려가 원이 이름을 잃었다 — 대상(감싼 원)은 선분이 아니라 색 규칙이 못 봤다.
    """
    box = boxes[i]
    for sh in shapes:
        if not (sh[0] <= box[0] and sh[1] <= box[1] and sh[2] >= box[2] and sh[3] >= box[3]):
            continue
        if not any(j != i and sh[0] <= _center(b)[0] <= sh[2] and sh[1] <= _center(b)[1] <= sh[3]
                   for j, b in enumerate(boxes)):
            return True
    return False


def _center(box):
    return (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0


def _verdict(fig_id, svg):
    errors, warnings = [], []
    check_svg(fig_id, svg, errors, warnings, layout_strict=True,
              halo_gap_strict=True, clearance_strict=True)
    check_figure_lint(fig_id, svg, errors, warnings, strict=True, geometry_strict=True)
    # 경고도 센다 — 응용고체 ch14 첫 적용에서 옮긴 라벨이 halo 글자 위 선 교차(F4, close 차단 경고)를 새로 냈다.
    return len(errors) + len(warnings)


def _set_xy(svg, pos, x, y):
    end = svg.find(">", pos)
    tag = svg[pos:end]
    for axis, value in (("x", x), ("y", y)):
        fmt = "%g" % round(value, 2)
        pat = re.compile(r"(\s" + axis + r"\s*=\s*)(['\"])(-?\d*\.?\d+)\2")
        m = pat.search(tag)
        if m:
            tag = tag[:m.start()] + m.group(1) + m.group(2) + fmt + m.group(2) + tag[m.end():]
        else:
            tag = "<text " + axis + "='" + fmt + "'" + tag[len("<text"):]
    return svg[:pos] + tag + svg[end:]


def _pull(box, fs, dist_fn, toward, others, shapes, vb, ref_seg=None, keep=()):
    """`toward(box)` 가 준 점 쪽으로 STEP 씩 당겨 dist_fn ≤ LAND_EM·fs 가 되는 (dx, dy). 못 하면 None.

    `keep` = [(선분, 옮기기 전 거리)] — 도달점에서 이 선들과 멀어지면 거절한다(열역학 ch03 `fig-ch03-p03` 의
    `Tsat = …` 가 같은 색 돔 쪽으로 가며 자기 대상인 옅은 색 포화선에서 멀어졌다 — 색이 같은 계열이라 색 규칙이 갈랐다).
    """
    vx, vy, vw, vh = vb
    goal = LAND_EM * fs
    low = 0.5 * fs
    tx, ty = toward(box)
    cx, cy = _center(box)
    ux, uy = tx - cx, ty - cy
    norm = math.hypot(ux, uy)
    if norm < 1e-9:
        return None
    ux, uy = ux / norm, uy / norm
    shift = STEP_PX
    while shift <= norm:
        cand = _shift_box(box, ux * shift, uy * shift)
        d = dist_fn(cand)
        if d <= goal:
            if d < low - A.GAP_TOL_PX:
                return None
            if (cand[0] < vx + VIEWBOX_MARGIN_PX or cand[2] > vx + vw - VIEWBOX_MARGIN_PX
                    or cand[1] < vy + VIEWBOX_MARGIN_PX or cand[3] > vy + vh - VIEWBOX_MARGIN_PX):
                return None
            if _straddles(cand, shapes) and not _straddles(box, shapes):
                return None
            if ref_seg is not None and _side_of(ref_seg, cand) != _side_of(ref_seg, box):
                return None
            if any(_segment_to_rect_distance(sg, cand) > d0 + A.GAP_TOL_PX for sg, d0 in keep):
                return None
            for other in others:
                if _rect_x_rect(cand, other):
                    return None
                # 다른 글자와 0.5em(내용끼리 간격) 안으로 새로 붙지 않는다 — 응용유체 ch06 `fig-deriv-couette` 에서
                # `선형 성분` 이 `U` 에 2px 로 붙어 `U선형 성분` 으로 읽혔다(옛 하한 2px 은 겹침만 막았다).
                if _rect_gap(cand, other) < min(TEXT_CLEAR_EM * fs, _rect_gap(box, other)) - 1e-9:
                    return None
            return ux * shift, uy * shift
        shift += STEP_PX
    return None


def plan_figure(svg, fig_id="?"):
    """(새 svg, [(분류, 글자, 전, 후)]) — 순수 함수. 분류 키는 KINDS."""
    vb = A._viewbox(svg)
    rows = []
    if not vb:
        return svg, rows
    segments = A._svg_segments(svg) + A._stroked_ellipse_segments(svg)
    if not segments:
        return svg, rows
    texts = A._texts_with_weight(svg)
    boxes = [_text_bbox(t) for t in texts]
    bars = A._fraction_bars(svg)
    regions = A._closed_regions(svg)
    colored = A._colored_segments(svg)
    shapes = _svg_filled_shapes(svg, tuple(vb))
    dots = _dots(svg)
    arrows = []
    for base, tip, pts in A._filled_triangles(svg):
        own = {s for s in segments
               if all(any(A._distance(e, p) <= A.PROX_SHAFT_TOUCH_PX for p in pts)
                      for e in ((s[0], s[1]), (s[2], s[3])))}
        tail = tip
        for s in segments:
            for e, o in (((s[0], s[1]), (s[2], s[3])), ((s[2], s[3]), (s[0], s[1]))):
                if A._distance(e, base) <= A.PROX_SHAFT_TOUCH_PX and s not in own:
                    own.add(s)
                    tail = o
        arrows.append((tail, tip, own))
    # 빌드의 축 이름 자가 알아본 글자(화살촉 곁) — 그 거리는 axis_name_gap(0.5em) 이 정본이라 여기서 안 당긴다.
    axis_names = [(x, y) for x, y, afs, anear, _apex in _axis_name_gaps(svg)
                  if anear is not None and anear <= AXIS_ARROW_MAX_EM * afs]
    base_err = None
    for i in range(len(texts)):
        text = texts[i]                            # 옮긴 뒤 다시 읽은 목록 — pos 가 밀렸을 수 있다
        box, fs = boxes[i], text["fs"]
        mine_bars = {seg for (gs, ge), seg in bars if gs <= text["pos"] < ge}
        segs = [s for s in segments if s not in mine_bars]
        ranked = min(((_segment_to_rect_distance(s, box), s) for s in segs), default=None,
                     key=lambda p: p[0])
        if ranked is None:
            continue
        near, near_seg = ranked
        s = text["s"].strip()
        if text["bold"] and A._hangul_count(s) >= A.PROX_TITLE_HANGUL_MIN:
            gaps = [near] + [_rect_gap(box, o) for j, o in enumerate(boxes) if j != i]
            if A.PROX_TITLE_MIN_EM * fs - min(gaps) > A.GAP_TOL_PX:
                rows.append(("title", s, min(gaps), None))
            continue
        if text["bold"] or A._is_caption(text):
            continue
        cx, cy = _center(box)
        if any(A._point_in_polygon((cx, cy), r["pts"]) for r in regions) or \
                A._is_panel_title(box, fs, regions):
            continue
        far = near - A.PROX_LABEL_MAX_EM * fs > A.GAP_TOL_PX
        owner = next((a for a in arrows if near_seg in a[2]), None)
        oblique = False
        if owner is not None and not text.get("axis_name"):
            (tx, ty), (hx, hy) = owner[0], owner[1]
            ax, ay = hx - tx, hy - ty
            l2 = ax * ax + ay * ay
            if l2 > 1e-9:
                t = ((cx - tx) * ax + (cy - ty) * ay) / l2
                oblique = max(-t, t - 1.0, 0.0) * math.sqrt(l2) > A.GAP_TOL_PX
        fill = text.get("fill", "")
        mine = [sg for sg, c in colored if c == fill] if A._is_chromatic(fill) else []
        others_c = [sg for sg, c in colored if c != fill] if mine else []
        foreign = bool(mine and others_c and
                       min(_segment_to_rect_distance(sg, box) for sg in mine)
                       - min(_segment_to_rect_distance(sg, box) for sg in others_c) > A.GAP_TOL_PX)
        if not (far or oblique or foreign):
            continue
        if text.get("rot") or text.get("mat") is not None:
            rows.append(("transform", s, near, None))
            continue
        if text.get("axis_name") or any(abs(ax - text["x"]) < 0.01 and abs(ay - text["y"]) < 0.01
                                        for ax, ay in axis_names):
            rows.append(("axis", s, near, None))
            continue
        other_boxes = [b for j, b in enumerate(boxes) if j != i]
        if _enclosing_own_shape(i, boxes, shapes):
            rows.append(("inside", s, near, None))
            continue
        # ★ 붙은 글자 묶음(`h` + 따로 찍은 첨자 `steam`)은 하나만 옮기면 묶음이 깨진다 — 첫 적용
        #   (응용열 ch08 fig-08-regenerative-flow)에서 첨자만 끌려가 `steam h` 로 뒤집혔다. 묶음은 사람 몫.
        if _joined(box, fs, other_boxes):
            rows.append(("blocked", s, near, None))
            continue
        # ★ 조판 묶음(`mathline`·`frac` 그룹, 분수선 그룹) 안의 조각도 하나만 옮기면 식이 깨진다 —
        #   열역학 ch05 `fig-steady-device-balance` 에서 `ṁ(h₁ +` · `+ gz₂)` 조각만 옮기려 했다(조각 사이가 넓어 위 가드를 빠져나감).
        if any(gs <= text["pos"] < ge for gs, ge, _b in _tagged_group_spans(svg, ("mathline", "frac"))) \
                or any(gs <= text["pos"] < ge for (gs, ge), _seg in bars):
            rows.append(("blocked", s, near, None))
            continue
        move = None
        # ★ 짧은 라벨은 사선 미끄럼보다도 먼저 거른다(2026-09-24 큐 (30)): 공수2 ch07 `fig-07-th-line-through-two-points`
        #   의 원점 이름 `O` 가 화살표 꼬리 곁이라 「화살표 라벨 사선」으로 잡혀 화살표를 따라 미끄러졌다 — 짧은
        #   이름은 점·축·첨자일 수 있어 화살표가 대상이라는 보장도 없다.
        if len(s) <= SHORT_LABEL_MAX and not far and oblique:
            rows.append(("unknown", s, near, None))
            continue
        if oblique and not far:
            (tx, ty), (hx, hy) = owner[0], owner[1]
            ax, ay = hx - tx, hy - ty
            l2 = ax * ax + ay * ay
            t = ((cx - tx) * ax + (cy - ty) * ay) / l2
            tt = min(max(t, 0.15), 0.85)       # 고른 값: 자루 양 끝 15 % 는 비운다 — 촉·꼬리에 붙지 않게
            dx, dy = (tt - t) * ax, (tt - t) * ay
            cand = _shift_box(box, dx, dy)
            if all(not _rect_x_rect(cand, o) for o in other_boxes):
                move = (dx, dy)
        elif len(s) <= SHORT_LABEL_MAX and dots:
            # ★ 짧은 라벨은 점 규칙이 색 규칙보다 먼저다 — 유체 ch05 첫 적용에서 파란 상태점 이름 `1` 이
            #   같은 파란색 **화살표** 쪽으로 끌려갔다(점은 선분이 아니라 색 규칙이 못 본다). 색이 있으면 같은 색 점을 고른다.
            pool = [d for d in dots if not A._is_chromatic(fill) or d[3] == fill] or dots
            dot = min(pool, key=lambda d: _rect_to_dot(box, d))
            if _rect_to_dot(box, dot) <= A.PROX_LABEL_MAX_EM * fs + A.GAP_TOL_PX:
                rows.append(("dot_ok", s, near, _rect_to_dot(box, dot)))
                continue
            # ★ 화살촉 끝이 점보다 가까우면 그 라벨은 화살표(축) 이름이다 — 응용고체 ch11 첫 재적용에서
            #   세로축 이름 `+τ` 가 멀리 있는 중심점 C 로 끌려갔다(빌드 축 이름 자도 못 알아본 자리).
            # ★★ 점으로 **당기지는 않는다** — 짧은 라벨은 분류만. 응용고체 ch11 `fig-11-p03-three-stresses`
            #   에서 `σ2`(축 위 교점의 이름)가 원 꼭대기의 점(최대 전단 표지)으로 끌려갔다. 점이 라벨의 대상이라는
            #   보장이 없고, 색 규칙도 짧은 라벨에서 두 번 틀렸다(유체 ch05 `1`). 짧은 이름은 대상 불명으로 사람 몫.
            rows.append(("unknown", s, near, None))
            continue
        elif len(s) <= SHORT_LABEL_MAX:
            rows.append(("unknown", s, near, None))
            continue
        elif mine:
            dist_fn = lambda b: min(_segment_to_rect_distance(sg, b) for sg in mine)   # noqa: E731
            # 「최근접이 다른 색」만 남은 후보가 이미 도달점 안이면 당겨도 안 풀린다 — 다른 색 선이 더 가까운 것이
            # 문제라서다. 다시 돌릴 때마다 조금씩 더 당기던 자리(열역학 ch01 `fig-01-p04` `26 kPa` 7.1 → 6.7).
            if not far and dist_fn(box) <= LAND_EM * fs + A.GAP_TOL_PX:
                rows.append(("blocked", s, near, None))
                continue

            def toward(b, _m=mine):
                c = _center(b)
                sg = min(_m, key=lambda q: _segment_to_rect_distance(q, b))
                return _closest_point_on_segment(sg, c[0], c[1])
            if _aligned(i, texts):
                rows.append(("blocked", s, near, None))
                continue
            keep = [(sg, d0) for sg, c in colored if c != fill
                    for d0 in [_segment_to_rect_distance(sg, box)] if d0 <= KEEP_EM * fs]
            move = _pull(box, fs, dist_fn, toward, other_boxes, shapes, vb, keep=keep)
        else:
            rows.append(("unknown", s, near, None))
            continue
        if move is None:
            rows.append(("blocked", s, near, None))
            continue
        cand_svg = _set_xy(svg, text["pos"], text["x"] + move[0], text["y"] + move[1])
        if base_err is None:
            base_err = _verdict(fig_id, svg)
        if _verdict(fig_id, cand_svg) > base_err:
            rows.append(("blocked", s, near, None))
            continue
        svg = cand_svg
        new_box = _shift_box(box, move[0], move[1])
        boxes[i] = new_box
        texts = A._texts_with_weight(svg)          # 좌표 문자열 길이가 바뀌면 뒤 글자의 pos 가 밀린다
        rows.append(("moved", s, near, min(_segment_to_rect_distance(sg, new_box) for sg in segs)))
    return svg, rows


def owners_of(data):
    """{id(삽화 dict): 그 삽화를 가진 항목 id} — 사유(`changeNote`)를 다는 자리는 빌드 하이라이트와 같은
    컬렉션(`set_change_notes.items_of`)이다. 순수 함수 — 테스트가 직접 부른다."""
    owners = {}
    for _name, item in SCN.items_of(data):
        for diagram in A.iter_diagrams(item):
            owners.setdefault(id(diagram), item["id"])
    return owners


def note_problem(note):
    """사유 문장의 결함(없으면 None). `changeNote` 는 fmtText 를 안 거치는 필드라 `_` 가 아래첨자로 읽혀
    빌드 lint 에 걸린다(9ad43851 — 밑줄 있는 도구 이름을 넣은 사유 22장). 순수 함수."""
    if not str(note or "").strip():
        return "사유가 비었다"
    if "_" in note:
        return "사유에 밑줄(_)이 있다 — changeNote 는 미렌더 필드라 아래첨자로 읽힌다(도구 이름을 빼고 쓸 것)"
    return None


def run(path, apply=False, listing=False, note=""):
    """삽화는 감사와 같은 순회(`iter_diagrams`)로 찾고, 기록은 표기 보존 기록기(`write_chapter`)로 한다.

    `apply` 면 옮긴 삽화의 주인 항목에 `note` 를 `changeNote` 로 덧붙인다(`set_change_notes` 의 append).
    왜(2026-09-24, 큐 (30)): 좌표만 옮기고 사유를 안 달아 변경점 사유 게이트(전 과목 error)에 22장이
    걸렸다 — 사유를 따로 다는 단계가 있으면 빠뜨려도 이 도구는 통과했다.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    before_data = copy.deepcopy(data)
    owners = owners_of(data)
    touched, orphans = [], []
    tally = {k: 0 for k in KINDS}
    for diagram in A.iter_diagrams(data):
        svg = diagram["svg"]
        fig_id = diagram.get("id") or "?"
        new_svg, rows = plan_figure(svg, fig_id)
        # 사람 몫 목록은 em 도 찍는다 — 규격(1.0em·1.5em)이 글자 크기 단위라 px 만으로는 판정이 안 선다(큐 (31)).
        size_of = {t["s"].strip(): t["fs"] for t in A._svg_texts(svg)}
        for kind, s, before, _after in rows:
            tally[kind] += 1
            if listing == "moved" and kind == "moved":
                print(f"  {Path(path).stem} {fig_id:34} [옮김] {s[:24]!r} {before:.1f} → {_after:.1f}")
            elif listing is True and kind not in ("moved", "dot_ok"):
                em = f" = {before / size_of[s]:.2f}em" if size_of.get(s) else ""
                print(f"  {Path(path).stem} {fig_id:34} [{KINDS[kind]}] {s[:24]!r} 잰 값 {before:.1f}{em}")
        if new_svg != svg:
            diagram["svg"] = new_svg
            owner = owners.get(id(diagram))
            if owner is None:
                orphans.append(fig_id)
            elif owner not in touched:
                touched.append(owner)
    if apply and data != before_data:
        status, why = write_chapter(str(path), before_data, data)
        if status == "skipped":
            print(f"  [건너뜀] {path}: 표기 보존 기록 실패 — {why}")
            return tally
        if touched:
            SCN.run_chapter(str(path), {oid: note for oid in touched}, True, True)
        for fid in orphans:
            print(f"  [사유 자리 없음] {Path(path).stem} {fid} — 하이라이트 컬렉션 밖 삽화(사람이 확인)")
    return tally


def nudge(path, specs, apply=False, note=""):
    """사람이 렌더를 보고 정한 이동 — `그림id::글자::dx::dy[::몇째]` 마다 옮기기 전·뒤 최근접 선 거리(em)를 찍는다.

    왜(2026-09-24 큐 (31)): 사람 몫 후보 중 규격(1.0em)을 조금 넘는 것은 방향이 렌더로 정해지는데, 좌표를 손으로 고치면
    잰 값도 관문도 없다. 여기서 옮기면 빌드 검사(`_verdict`)가 늘 때 거절하고, 옮긴 카드에 사유를 함께 단다.
    반환: [(그림id, 글자, 전 em, 후 em, 상태)].
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    before_data = copy.deepcopy(data)
    owners = owners_of(data)
    touched, out = [], []
    diagrams = list(A.iter_diagrams(data))
    for spec in specs:
        parts = spec.split("::")
        fig_id, label, dx, dy = parts[0], parts[1], float(parts[2]), float(parts[3])
        nth = int(parts[4]) if len(parts) > 4 else 0
        diagram = next((d for d in diagrams if d.get("id") == fig_id), None)
        if diagram is None:
            out.append((fig_id, label, None, None, "그림 없음"))
            continue
        svg = diagram["svg"]
        hits = [t for t in A._svg_texts(svg) if t["s"].strip() == label]
        if len(hits) <= nth:
            out.append((fig_id, label, None, None, "글자 없음"))
            continue
        t = hits[nth]
        segs = A._svg_segments(svg) + A._stroked_ellipse_segments(svg)
        box = _text_bbox(t)
        d0 = min((_segment_to_rect_distance(s, box) for s in segs), default=0.0) / t["fs"]
        cand = _set_xy(svg, t["pos"], t["x"] + dx, t["y"] + dy)
        d1 = min((_segment_to_rect_distance(s, _shift_box(box, dx, dy)) for s in segs), default=0.0) / t["fs"]
        if _verdict(fig_id, cand) > _verdict(fig_id, svg):
            out.append((fig_id, label, d0, d1, "거절 — 빌드 검사가 는다"))
            continue
        diagram["svg"] = cand
        owner = owners.get(id(diagram))
        if owner and owner not in touched:
            touched.append(owner)
        out.append((fig_id, label, d0, d1, "옮김"))
    if apply and data != before_data:
        status, why = write_chapter(str(path), before_data, data)
        if status == "skipped":
            print(f"  [건너뜀] {path}: 표기 보존 기록 실패 — {why}")
        elif touched:
            SCN.run_chapter(str(path), {oid: note for oid in touched}, True, True)
    return out


def verify_against(path, rev, restore=False, to_rev=None):
    """`rev` 대비 좌표가 바뀐 글자 중 조판 묶음(mathline·frac·분수선 그룹) 안의 조각을 찾는다.

    왜: 묶음 가드(`793daded`)가 들어오기 전 회차의 적용분이 안전한지는 따로 증명해야 한다.
    `restore` 면 그 조각만 `rev` 좌표로 되돌려 표기 보존 기록기로 쓴다(실측: 기계공작법 ch10 2건).
    """
    import subprocess
    rel = str(Path(path).resolve().relative_to(Path(__file__).resolve().parent.parent)).replace("\\", "/")
    old_text = subprocess.run(["git", "show", rev + ":" + rel], capture_output=True,
                              encoding="utf-8", cwd=str(Path(__file__).resolve().parent.parent)).stdout
    if not old_text:
        return []
    # 순서로 짝짓는다 — id 로 짝지으면 같은 id 가 둘인 장(열역학 ch02 `fig-mass-flow-column`)에서 엉뚱한 짝을 대 오신고한다.
    old = [d["svg"] for d in A.iter_diagrams(json.loads(old_text))]
    if to_rev:
        # 두 커밋 사이만 본다(읽기 전용) — 그 뒤 다른 세션이 옮긴 글자(축 이름 도구 등)를 이 도구 몫으로 오신고하지 않게.
        new_text = subprocess.run(["git", "show", to_rev + ":" + rel], capture_output=True,
                                  encoding="utf-8", cwd=str(Path(__file__).resolve().parent.parent)).stdout
        data, restore = json.loads(new_text), False
    else:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    before_data = copy.deepcopy(data)
    hits = []
    cur = list(A.iter_diagrams(data))
    if len(cur) != len(old):
        return [("?", "(삽화 수가 달라 대조 불가)")]
    for d, before in zip(cur, old):
        if not before or before == d["svg"]:
            continue
        spans = [(gs, ge) for gs, ge, _b in _tagged_group_spans(before, ("mathline", "frac"))]
        spans += [span for span, _seg in A._fraction_bars(before)]
        ot, nt = A._svg_texts(before), A._svg_texts(d["svg"])
        if len(ot) != len(nt):
            hits.append((d.get("id"), "(글자 수가 달라 대조 불가)"))
            continue
        back = []
        oboxes = [_text_bbox(t) for t in ot]
        vb = A._viewbox(before)
        oshapes = _svg_filled_shapes(before, tuple(vb)) if vb else []
        for k, (a, b) in enumerate(zip(ot, nt)):
            if (a["x"], a["y"]) == (b["x"], b["y"]):
                continue
            joined = _joined(oboxes[k], a["fs"], [ob for j, ob in enumerate(oboxes) if j != k]) \
                or _enclosing_own_shape(k, oboxes, oshapes) or len(a["s"].strip()) <= SHORT_LABEL_MAX \
                or _aligned(k, ot)
            nbox = _text_bbox(b)
            crowded = any(_rect_gap(nbox, _text_bbox(nt[j])) < min(TEXT_CLEAR_EM * a["fs"], _rect_gap(oboxes[k], ob)) - 1e-9
                          for j, ob in enumerate(oboxes) if j != k)
            if joined or crowded or any(gs <= a["pos"] < ge for gs, ge in spans):
                hits.append((d.get("id"), a["s"][:24]))
                back.append((b["pos"], a["x"], a["y"]))
        if restore:
            svg = d["svg"]
            for pos, x, y in sorted(back, reverse=True):     # 뒤에서부터 — 앞을 고치면 뒤 pos 가 밀린다
                svg = _set_xy(svg, pos, x, y)
            d["svg"] = svg
    if restore and data != before_data:
        write_chapter(str(path), before_data, data)
    return hits


def chapters_of(target):
    p = Path(target)
    if p.is_file():
        return [p]
    return sorted(q for q in p.glob("ch*.json") if re.fullmatch(r"ch\d+\.json", q.name))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", help="data/<과목> 폴더 또는 장 JSON")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--list", dest="listing", action="store_true", help="사람 몫을 한 줄씩")
    ap.add_argument("--moves", action="store_true", help="옮길(옮긴) 라벨을 한 줄씩 — 렌더 검수 목록")
    ap.add_argument("--verify-against", dest="verify", help="이 커밋 대비 옮겨진 조판 묶음 조각을 찾는다(읽기 전용)")
    ap.add_argument("--nudge", action="append", default=[],
                    help="그림id::글자::dx::dy[::몇째] — 렌더를 보고 사람이 정한 이동(반복 가능, 장 JSON 하나)")
    ap.add_argument("--verify-to", dest="verify_to", help="대조의 새 쪽을 작업 트리 대신 이 커밋으로(읽기 전용)")
    ap.add_argument("--note", default="", help="--apply 필수: 옮긴 삽화의 주인 항목에 덧붙일 changeNote(밑줄 금지)")
    args = ap.parse_args()
    if args.moves:
        args.listing = "moved"
    if args.apply and not args.verify and note_problem(args.note):
        print("[거부] --apply 에는 --note 가 필요하다 — " + note_problem(args.note))
        return 2
    if args.nudge:
        if len(chapters_of(args.target)) != 1:
            print("[거부] --nudge 는 장 JSON 하나에만")
            return 2
        for fid, label, d0, d1, status in nudge(chapters_of(args.target)[0], args.nudge, args.apply, args.note):
            em = f"{d0:.2f}em → {d1:.2f}em" if d0 is not None else ""
            print(f"  {fid:34} {label[:24]!r} {em} [{status}]")
        if not args.apply:
            print("(보고만 했다 — 쓰려면 --apply)")
        return 0
    chapters = chapters_of(args.target)
    if args.verify:
        hits = [(ch, fid, s) for ch in chapters
                for fid, s in verify_against(ch, args.verify, restore=args.apply, to_rev=args.verify_to)]
        if args.apply and hits:
            print("  (--apply: 그 조각을 대조 커밋의 좌표로 되돌렸다)")
        for ch, fid, s in hits:
            print(f"  ★ 묶음 조각이 옮겨짐 {ch.parent.name}/{ch.stem} {fid} {s!r}")
        print(f"합계 — {args.verify} 대비 옮겨진 묶음 조각 {len(hits)}건 · 훑은 장 {len(chapters)}")
        return 1 if hits else 0
    if not chapters:
        print("[해당 없음] 장 JSON 0개 — " + args.target)
        return 0
    total = {k: 0 for k in KINDS}
    for ch in chapters:
        t = run(ch, args.apply, args.listing, args.note)
        for k in total:
            total[k] += t[k]
        if any(t.values()):
            print(f"{ch.parent.name}/{ch.name}: " + " · ".join(f"{KINDS[k].split(' ')[0]} {v}"
                                                               for k, v in t.items() if v))
    print("합계 — " + " · ".join(f"{KINDS[k]} {v}" for k, v in total.items()))
    if not args.apply:
        print("(보고만 했다 — 쓰려면 --apply)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
