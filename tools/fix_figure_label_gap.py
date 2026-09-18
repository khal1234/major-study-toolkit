# -*- coding: utf-8 -*-
"""라벨-도형 간격을 규격(1em)까지 벌린다 — 감사가 재는 그 값을 그대로 목표로 쓴다.

왜 만들었나 (열린 날 2026-07-30):
    `audit_figure_balance.py` 의 「라벨-도형 간격」이 전 챕터 **300건**(오탐 91건을 걷어낸 실수치)
    이었다. 어느 챕터도 이 규격을 만족한 적이 없다 — 규격은 2026-07-29 에 세웠는데
    **재는 도구만 있고 맞추는 도구가 없었다.**

    손으로 고치면 안 된다. 삽화마다 사람이 눈으로 간격을 정하게 되고, 그게 바로
    *[발화 생략]* 라는
    지적이 열린 원인이다(캡션 위계에서 이미 같은 이유로 도구를 만들었다 —
    `fix_figure_caption_tier.py`).

    사용자 결정(2026-07-30): *[발화 생략]* → 도구로 맞추고, 새로 생긴 겹침은 검수로 잡는다.

무엇을 하는가
    ⑴ 감사와 **같은 함수**로 잰다(`_required_gap`·`_segment_to_rect_distance`). 따로 재면 갈라진다.
    ⑵ 가장 가까운 선분의 **법선 방향**으로만 민다. 그 방향을 지배축(가로/세로)으로 스냅하므로
       **나머지 축의 정렬이 보존된다** — 눈금선에 맞춘 세로 중심, 화살표 축에 맞춘 가로 중심 등.
       (이게 없으면 축 라벨이 자기 눈금에서 떨어져 나간다.)
    ⑶ 민 뒤 **그 라벨이 감사를 통과하는지** 다시 재고, 통과하지 못하면 그 후보를 버린다.
       즉 '얼마나 밀지'를 계산으로 정하지 않고 **판정으로** 정한다.
    ⑷ 다른 글자와의 간격을 **나빠지게 하지 않는다.** 이미 붙어 있던 짝은 그 값을 하한으로 삼는다
       (감사가 텍스트↔텍스트를 재지 않으므로 여기서만 볼 수 있다 — AGENTS 「여백·라벨 규격」).
    ⑸ viewBox 를 벗어나지 않는다.
    못 미는 라벨은 **건너뛰고 사유를 찍는다.** 억지로 밀어 새 결함을 만드는 것보다 남기는 게 낫다.

쓰기 규율: 기본은 **보고만** 한다. `--apply` 를 줘야 파일을 쓴다.

    python tools/fix_figure_label_gap.py                        # 전 챕터 보고
    python tools/fix_figure_label_gap.py --chapter=ch01.json
    python tools/fix_figure_label_gap.py --chapter=ch01.json --id fig-heat-modes --apply
"""
import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from audit_figure_balance import (  # noqa: E402
    GAP_TOL_PX, _closed_regions, _required_gap, _viewbox,
)
from buildlib.checks_svg import (  # noqa: E402
    _fraction_bars, _rect_x_rect, _segment_to_rect_distance, _svg_filled_shapes, _svg_segments,
    _svg_texts, _text_bbox, check_figure_lint, check_svg,
)

ROOT = Path(__file__).resolve().parent.parent
# ★ 과목 폴더를 박지 않는다 (열린 날 2026-07-30. thermo 는 "세 번째", math 실측으로는
#   `build_review`(07-27)까지 포함해 **네 번째**다 — 어느 쪽이든 같은 부류의 반복이다).
#   `data/열역학` 하드코딩이라 다른 과목 워크트리에서는 glob 이 0건이 되어
#   **아무것도 안 하고 조용히 exit 0** 이었다 — 실패인데 성공처럼 보이는 최악의 형태다
#   (`--chapter` 를 주면 그제야 깨진 경로로 FileNotFoundError 가 났다).
#   math 실측(2026-07-30): 그래서 ch01 6건·ch02 6건이 이 도구를 **쓸 수 없었고**, 그 사이
#   같은 규격 위반을 손으로 고치게 된다 — 그게 이 도구가 없애려던 결함이다.
#   audit_content(2026-07-26)·fix_figure_text_scale(2026-07-28)이 이미 같은 실수를 고쳤고
#   그 이력이 주석으로 남아 있는데도 재발했다 → 회귀 두 개가 각각 다른 각도로 잠근다:
#   `test_no_subject_hardcoded_data_root`(이 파일) · `test_tools_do_not_hardcode_a_subject`
#   (`tools/**` 전수 — 어느 파일이 새로 박아도 걸린다).
#   ※ 병합 메모(2026-07-30): 기계재료 세션도 같은 결함을 **독립적으로** 고쳤다(`subject_dirs`·
#     `_my_subject` 를 불러 쓰는 형태). 판정이 한 곳(`audit_content.DATA`)으로 모이는 이쪽을
#     정본으로 남기고 그 구현은 버렸다 — 같은 일을 두 곳에서 하면 반드시 갈라진다.
import audit_content  # noqa: E402
DATA = Path(audit_content.DATA)

# 글자끼리의 최소 간격. 감사가 재지 않는 축이라 여기서만 지킬 수 있다.
# 이미 이보다 붙어 있던 짝은 **그 값**을 하한으로 쓴다(이 도구가 나빠지게만 안 하면 된다).
TEXT_MIN_PX = 2.0
VIEWBOX_MARGIN_PX = 2.0
STEP_PX = 0.5


def _rect_gap(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def _shift_box(box, dx, dy):
    return (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)


def _closest_point_on_segment(seg, px, py):
    x1, y1, x2, y2 = seg[0], seg[1], seg[2], seg[3]
    dx, dy = x2 - x1, y2 - y1
    denom = dx * dx + dy * dy
    if not denom:
        return x1, y1
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / denom))
    return x1 + t * dx, y1 + t * dy


def _push_axis(seg, box):
    """어느 축으로 밀지와 그 부호. 가장 가까운 선분에서 **멀어지는** 쪽이다.

    지배축으로 스냅하는 이유: 대각선 방향으로 밀면 두 축의 정렬이 **둘 다** 깨진다.
    한 축만 건드리면 나머지 축(눈금선·화살표 축에 맞춰 둔 정렬)은 그대로 남는다.
    """
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    qx, qy = _closest_point_on_segment(seg, cx, cy)
    vx, vy = cx - qx, cy - qy
    if vx == 0 and vy == 0:      # 라벨 중심이 선 위 — 밀 방향을 정할 근거가 없다
        return None, 0
    if abs(vx) >= abs(vy):
        return "x", (1 if vx > 0 else -1)
    return "y", (1 if vy > 0 else -1)


ALIGN_TOL_PX = 0.75      # 이 안이면 '같은 축에 맞춰 둔 것'으로 본다
FS_TOL_PX = 0.6          # 글자 크기가 이만큼 차이나면 다른 층(제목 vs 라벨)이다
# 규격을 이만큼 넘겨서까지 밀지는 않는다. 목표는 **일관된 간격**이지 '멀리 떼어놓기'가 아니다.
MAX_OVERSHOOT_EM = 0.5


def _alignment_cluster(texts, boxes, index, axis):
    """`index` 라벨과 **그 축에 정렬돼 있는** 라벨들의 인덱스 집합.

    ★ 왜 필요한가 (2026-07-30 첫 시안이 실제로 이걸 깼다):
      `fig-steady-flow-snapshots` 의 `300°C` 는 바로 위 `입구` 와 x 가 같다(둘 다 48).
      간격을 벌리려고 `300°C` 만 x 로 밀면 **그 짝의 세로 정렬이 깨진다** —
      AGENTS 「여백·라벨 규격」이 *[발화 생략]* 로 금지한 것이고,
      애초에 이 규격이 생긴 이유(*[발화 생략]*)와
      같은 부류다. 간격 하나를 고치려고 정렬을 깨면 **거래가 아니라 손해**다.
      → 정렬된 라벨은 **한 덩어리로 같이 옮긴다.**

    ★ 처음엔 '중심 거리 4em 안'이라는 반경을 걸었다가 **부류를 절반 놓쳤다**(2026-07-30 실측):
      `fig-cup-macro-vs-micro` 의 좌·우 패널 캡션은 y 가 같은 **한 줄**인데 x 로 270px 떨어져 있어
      반경 밖이었다. 그래서 왼쪽만 밀리고 오른쪽은 건너뛰어 **두 캡션 높이가 어긋났다** —
      고치려던 그 결함(*[발화 생략]*)을 새로 만든 것이다.
      반경을 없애고 대신 **같은 층인지**(글자 크기·정렬 기준)로 가른다. 도판을 가로지르는
      한 줄은 실제로 한 줄이다 — 멀다고 남남이 아니다.
    """
    own = texts[index]["x"] if axis == "x" else texts[index]["y"]
    out = {index}
    for j, other in enumerate(texts):
        if j == index:
            continue
        if other["anchor"] != texts[index]["anchor"]:
            continue          # 정렬 기준점이 다르면 좌표가 같아도 같이 안 움직인다
        if abs(other["fs"] - texts[index]["fs"]) > FS_TOL_PX:
            continue          # 제목과 라벨은 같은 줄에 있어도 다른 층이다
        coord = other["x"] if axis == "x" else other["y"]
        if abs(coord - own) <= ALIGN_TOL_PX:
            out.add(j)
    return out


def _straddles(box, shapes):
    """채운 도형의 **경계에 걸쳤는가** — 안이든 밖이든 한쪽에 완전히 있어야 한다.

    ★ 첫 시안이 이걸 빠뜨려 빌드가 2건을 잡았다(`fig-continuum-vs-rarefied` 'λ',
      `fig-d-fluid-element` 'Δx'). 간격만 보고 밀면 **라벨이 도형 테두리에 얹힌다** —
      AGENTS 「여백·라벨 규격」의 *[발화 생략]* 위반이고
      빌드는 이걸 error 로 본다. 즉 도구가 **빌드가 거부할 것을 제안하고 있었다.**
      판정을 새로 쓰지 않고 빌드와 **같은 함수**(`_svg_filled_shapes`·`_rect_x_rect`)로 본다.
    """
    for shape in shapes:
        if not _rect_x_rect(box, shape):
            continue
        if not (shape[0] <= box[0] and shape[1] <= box[1]
                and shape[2] >= box[2] and shape[3] >= box[3]):
            return True
    return False


# ★ 「중앙에 놓기로 한 라벨」로 볼 가로 오차. 2px 은 조판 반올림만 흡수하는 값이다 —
#   느슨하게 잡으면 중앙이 아닌 라벨까지 x 가 잠겨 도구가 못 고치는 자리가 늘어난다.
CENTER_LOCK_TOL_PX = 2.0


def _is_centered_on_shape(box, shapes):
    """이 라벨이 어떤 채운 도형의 **가로 중앙**에 놓여 있는가. 순수 함수.

    세로로 겹치는 도형만 본다 — 겹치지 않으면 그 도형의 이름표가 아니라 남남이다.
    """
    cx = (box[0] + box[2]) / 2.0
    for sx0, sy0, sx1, sy1 in shapes:
        if sx1 <= sx0:
            continue
        if box[3] <= sy0 or box[1] >= sy1:
            continue
        if abs(cx - (sx0 + sx1) / 2.0) <= CENTER_LOCK_TOL_PX:
            return True
    return False


def _build_verdict(fig_id, svg):
    """빌드가 이 SVG 에 붙일 error 개수. 도구의 최종 관문이다.

    ★ 왜 자체 판정으로 끝내지 않는가: 빌드에는 라벨 위치에 걸리는 검사가 여럿 있다
      (글자끼리 겹침 · F1 0.5em · 선/패스 교차 · 도형 경계 걸침 · z-order · viewBox 이탈).
      그중 하나만 재현해 놓으면 **나머지가 사각지대**가 된다. 그래서 마지막에 빌드의
      검사 함수를 그대로 돌려 **에러가 늘지 않았을 때만** 그 삽화의 이동을 채택한다.
      한 삽화당 두 번만 부르므로 비용도 감당된다(라벨마다 부르면 수천 번이 된다).
    """
    errors, warnings = [], []
    # strict 플래그는 **전부 켜서** 본다 — 지금 strict 가 아닌 챕터에 새 위반을 심어 두면
    # 나중에 승격할 때 그 챕터가 통째로 막힌다(그 승격이 남은 작업 목록에 있다).
    check_svg(fig_id, svg, errors, warnings, layout_strict=True,
              halo_gap_strict=True, clearance_strict=True)
    check_figure_lint(fig_id, svg, errors, warnings, strict=True, geometry_strict=True)
    return len(errors)


def _measure(box, fs, segments, regions):
    """이 위치에서의 (요구치, 최근접 거리, 최근접 선분)."""
    want, _why = _required_gap(box, fs, regions)
    nearest, seg = None, None
    for candidate in segments:
        dist = _segment_to_rect_distance(candidate, box)
        if nearest is None or dist < nearest:
            nearest, seg = dist, candidate
    return want, nearest, seg


def plan_figure(svg, fig_id="?"):
    """이 삽화에서 옮길 라벨을 정한다. 순수 함수 — 테스트가 직접 부른다.

    반환: (moves, skips)
      moves = [{"pos", "axis", "old", "new", "text", "from", "to", "want"}]
      skips = [{"text", "want", "dist", "reason"}]
    """
    vb = _viewbox(svg)
    if not vb:
        return [], []
    vx, vy, vw, vh = vb
    segments = _svg_segments(svg)
    regions = _closed_regions(svg)
    shapes = _svg_filled_shapes(svg, (vx, vy, vw, vh))
    texts = _svg_texts(svg)
    if not segments or not texts:
        return [], []

    boxes = [_text_bbox(t) for t in texts]
    moves, skips = [], []

    # ★ 분수선은 **자기 그룹 안의 분자·분모에게는 도형이 아니다** (열린 날 2026-08-01).
    #   `audit_figure_balance` 는 이 면제를 갖고 있었는데 이 도구는 없었다 — 이 파일 첫머리가
    #   *[발화 생략]* 라고 적어 둔 바로 그 갈라짐이다.
    #   실사고: 동역학 `fig-sva-chain` 의 `d/dt` 에서 분모 'dt' 를 y 76.85 → 123.37 로 밀어
    #   **정상 조판된 분수를 깨뜨렸다.** 감사는 그 삽화를 0건으로 보고 있었으므로,
    #   도구가 감사도 신고하지 않은 것을 '고치'고 있었다.
    bars = _fraction_bars(svg)

    def segs_for(t):
        own = {seg for (gs, ge), seg in bars if gs <= t["pos"] < ge}
        return [s for s in segments if s not in own] if own else segments

    for i, text in enumerate(texts):
        box = boxes[i]
        want, dist, seg = _measure(box, text["fs"], segs_for(text), regions)
        if dist is None or want - dist <= GAP_TOL_PX:
            continue
        axis, sign = _push_axis(seg, box)
        if axis is None:
            skips.append({"text": text["s"][:18], "want": want, "dist": dist,
                          "reason": "라벨 중심이 선 위 — 밀 방향을 정할 수 없다"})
            continue

        # ★ 도형의 가로 중앙에 놓인 라벨은 **x 를 잠근다** (열린 날 2026-08-07).
        #   재발 이력: ch02 `cycle` 글자가 상자 중심 230 인데 236.74 에 있어 **사용자가 3회**
        #   지적했다. 원인은 손이 아니라 **이 도구**다 — `220ac12`(1em 확보, 전 챕터 232건 이동)
        #   가 라벨을 x 로 밀었고, **정렬(중앙 맞춤)을 보는 검사가 0개**라 아무도 신고하지
        #   않았다. 그래서 손으로 고쳐도 도구를 다시 돌리면 또 밀렸다(두 번 고쳐도 살아남음).
        #   ★ 태깅(`class='center-in'`)을 요구하지 않는 이유: 이미 만든 삽화를 전부 태깅하려면
        #   **검수를 끝낸 챕터를 건드려야** 하고 그건 하이라이트 잡음이 된다. 그래서 규칙을
        #   선언에 걸지 않고 **기본값을 안전한 쪽으로 뒤집는다**(AGENTS 규칙 7⑷ 의 선호 형태).
        #   간격이 정말 모자라면 사람이 본다 — 건너뛴 것은 출력에 남는다.
        if axis == "x" and _is_centered_on_shape(box, shapes):
            skips.append({"text": text["s"][:18], "want": want, "dist": dist,
                          "reason": "도형의 가로 중앙에 놓인 라벨이라 x 를 잠갔다 — "
                                    "밀면 중앙 정렬이 깨진다(사람이 볼 몫)"})
            continue

        cluster = _alignment_cluster(texts, boxes, i, axis)
        # 덩어리의 다른 식구들이 지금 얼마나 여유가 있는지 — 밀어서 **나빠지면** 안 된다.
        before = {j: _measure(boxes[j], texts[j]["fs"], segs_for(texts[j]), regions)
                  for j in cluster}

        need = want - dist
        limit = need + 2.0 * want          # 이보다 밀면 라벨이 자기 대상에서 떨어져 나간다
        best = None
        pair_blocked = flip_blocked = False
        # ★ **멀어지는 쪽으로만** 민다. 반대쪽 대안을 두었더니 도구가 라벨을 **선 반대편으로
        #   넘겨** 버렸다(실측: y 94 → 120.38 — 선 위에 있던 라벨이 선 아래로 갔다).
        #   간격은 맞지만 **라벨이 가리키는 쪽이 바뀐다** — `저온`/`고온`, 위/아래 첨자,
        #   경계 안/밖 라벨에서 이건 간격 문제가 아니라 **틀린 그림**이다.
        #   자리가 없으면 넘기지 말고 건너뛴다(사람이 볼 몫이다).
        for direction in (sign,):
            shift = need
            while shift <= limit + 1e-9:
                dx = direction * shift if axis == "x" else 0.0
                dy = direction * shift if axis == "y" else 0.0
                cands = {j: _shift_box(boxes[j], dx, dy) for j in cluster}
                ok = True
                for j, cand in cands.items():
                    if (cand[0] < vx + VIEWBOX_MARGIN_PX or cand[2] > vx + vw - VIEWBOX_MARGIN_PX
                            or cand[1] < vy + VIEWBOX_MARGIN_PX or cand[3] > vy + vh - VIEWBOX_MARGIN_PX):
                        ok = False
                        break
                    # 원래 안 걸쳐 있었다면 걸치게 만들지 않는다(걸쳐 있던 것은 이 도구 몫이 아니다).
                    if _straddles(cand, shapes) and not _straddles(boxes[j], shapes):
                        ok = False
                        break
                    # ★ 선을 넘지 않는다 — **사후 검출이 아니라 사전 차단** (열린 날 2026-07-30, 2회차).
                    #   `verify_against()` 가 이 결함을 **적용한 뒤에** 잡아내도록 돼 있었고,
                    #   실제로 1건이 그렇게 검출돼 사람이 손으로 되돌렸다. 되돌린 좌표에는
                    #   잠금이 없어서 **다음 `--apply` 가 같은 이동을 다시 한다**(실측 확인).
                    #   판정 함수는 이미 있었으므로(`_side_of`) 그것을 수용 조건으로 옮긴다 —
                    #   같은 자를 나중에 대는 대신 **먼저** 대는 것이 이 부류의 유일한 차이다.
                    ref_seg = before[j][2]
                    if ref_seg is not None and _side_of(ref_seg, cand) != _side_of(ref_seg, boxes[j]):
                        ok = False
                        flip_blocked = True
                        break
                    new_want, new_dist, _ = _measure(cand, texts[j]["fs"],
                                                     segs_for(texts[j]), regions)
                    if j == i:
                        if new_want - new_dist > GAP_TOL_PX:
                            ok = False       # 목표 라벨이 아직 규격 미달이면 더 밀어 본다
                            break
                        # ★ 넘겨서까지 밀지 않는다. 작은 이동이 막혀 있으면 탐색이 계속 커져
                        #   규격의 두세 배까지 가는데(실측: 기준 14.5 인데 35.1 까지 갔다),
                        #   그건 간격을 맞춘 것이 아니라 **배치를 바꾼 것**이다.
                        #   그 경우는 통과가 아니라 '못 미룸'으로 처리해 사람에게 넘긴다.
                        if new_dist > new_want + MAX_OVERSHOOT_EM * texts[j]["fs"]:
                            ok = False
                            break
                    else:
                        old_want, old_dist, _ = before[j]
                        # ★ 식구도 **규격을 만족해야** 한다 (열린 날 2026-07-30, 2회차).
                        #
                        #   예전 규칙은 식구에게 '더 나빠지지만 않으면 된다'만 요구했다. 그래서
                        #   목표 라벨은 규격에 닿고 짝은 미달인 채 **덩어리가 통째로 움직였다.**
                        #   실측(`fig-card-multifluid-sign`): `수은 h₃` 9.00→12.50(기준 12.50)인데
                        #   짝 `−ρgh` 는 9.34→11.50 으로 **여전히 미달**이다. 두 번 돌리면 또 움직인다.
                        #
                        #   이 이동이 바로 지난 세션이 **손으로 되돌린** 그 이동이다
                        #   (도구가 낸 새 결함 ⑷ '라벨이 선 반대편으로 넘어감'). 되돌리기만 하고
                        #   잠그지 않았으므로 **다음 `--apply` 가 조용히 되살린다** — 사람의
                        #   성실성에 기댄 조치였다(AGENTS 규칙 7-⑷).
                        #
                        #   짝을 만족시킬 수 없다는 것은 **간격 문제가 아니라 배치 문제**라는 뜻이다.
                        #   그건 위 MAX_OVERSHOOT 주석과 같은 판단이므로 사람에게 넘긴다.
                        if new_want - new_dist > GAP_TOL_PX:
                            ok = False
                            pair_blocked = True
                            break
                        if (new_want - new_dist) > max(GAP_TOL_PX, old_want - old_dist) + 1e-9:
                            ok = False
                            break
                if ok:
                    # 덩어리 밖 글자와의 간격도 나빠지게 하지 않는다.
                    for j, cand in cands.items():
                        for k, other in enumerate(boxes):
                            if k in cluster:
                                continue
                            if _rect_x_rect(cand, other):   # 겹침은 빌드가 error 로 본다
                                ok = False
                                break
                            floor = min(TEXT_MIN_PX, _rect_gap(boxes[j], other))
                            if _rect_gap(cand, other) < floor - 1e-9:
                                ok = False
                                break
                        if not ok:
                            break
                if ok:
                    best = (dx, dy, cands)
                    break
                shift += STEP_PX
            if best:
                break

        if not best:
            skips.append({"text": text["s"][:18], "want": want, "dist": dist,
                          "reason": ("밀면 라벨이 선 반대편으로 넘어간다 — 가리키는 쪽이 바뀐다"
                                     if flip_blocked else
                                     "정렬 짝을 함께 규격에 못 맞춘다 — 간격이 아니라 배치 문제다"
                                     if pair_blocked else
                                     "밀 수 있는 자리가 없다(다른 글자·도형·viewBox 에 걸린다)")})
            continue

        dx, dy, cands = best
        delta = dx if axis == "x" else dy
        for j in sorted(cluster):
            old = texts[j]["x"] if axis == "x" else texts[j]["y"]
            _, jdist, _ = _measure(cands[j], texts[j]["fs"], segs_for(texts[j]), regions)
            moves.append({"pos": texts[j]["pos"], "axis": axis, "old": old, "new": old + delta,
                          "text": texts[j]["s"][:18], "from": before[j][1], "to": jdist,
                          "want": before[j][0], "with": len(cluster) > 1 and j != i})
            boxes[j] = cands[j]      # 뒤 라벨의 판정이 이 이동을 보게 한다

    # ★ 마지막 관문 — 빌드의 판정으로 검산한다. 에러가 늘면 **그 삽화는 통째로 포기**한다.
    #   일부만 되돌리면 어느 조합이 안전한지 다시 따져야 하고, 그 계산이 여기서 틀린 것이다.
    if moves:
        after = apply_moves(svg, moves)
        if _build_verdict(fig_id, after) > _build_verdict(fig_id, svg):
            return [], skips + [{"text": "(삽화 전체)", "want": 0.0, "dist": 0.0,
                                 "reason": "밀면 빌드 검사가 새 위반을 낸다 — 이 삽화는 손으로 볼 것"}]
    return moves, skips


def _set_text_coord(svg, pos, axis, value):
    """`<text>` 태그의 x/y 만 바꾼다. 다른 속성·자식(tspan)은 건드리지 않는다."""
    end = svg.find(">", pos)
    tag = svg[pos:end]
    fmt = "%g" % round(value, 2)
    pattern = re.compile(r"(\b" + axis + r"\s*=\s*)(['\"])(-?\d*\.?\d+)\2")
    match = pattern.search(tag)
    if match:
        tag = tag[:match.start()] + match.group(1) + match.group(2) + fmt + match.group(2) + tag[match.end():]
    else:
        tag = "<text " + axis + "='" + fmt + "'" + tag[len("<text"):]
    return svg[:pos] + tag + svg[end:]


def apply_moves(svg, moves):
    """뒤에서부터 쓴다 — 앞을 먼저 고치면 뒤 라벨의 pos 가 밀린다."""
    for move in sorted(moves, key=lambda m: m["pos"], reverse=True):
        svg = _set_text_coord(svg, move["pos"], move["axis"], move["new"])
    return svg


# ★ JSON 을 파싱해 다시 덤프하지 않는다 — `"svg":` **그 줄만** 갈아 끼운다.
# 형제 도구(`fix_figure_caption_tier.py`)가 쓰는 규약이고, 이유는 재덤프가 키 순서·이스케이프·
# 들여쓰기를 건드려 **삽화 한 줄 고친 것이 파일 전체 diff** 로 나오기 때문이다.
# 그러면 `verify_workorder.py` 의 "기록한 변경 파일이 실제로 바뀌었는가" 대조가 무의미해진다.
SVG_LINE_RE = re.compile(r'^(\s*"svg":\s*)("(?:[^"\\]|\\.)*")(,?)\s*$')
# 삽화 id 만 잡는다 — 앞줄에는 소유 항목의 id(`sec-…`·`ch01-p03`)도 섞여 있다.
FIG_ID_RE = re.compile(r'"id"\s*:\s*"(fig-[^"]+)"')


def run(chapter_path, wanted=None, apply=False):
    path = Path(chapter_path)
    lines = path.read_text(encoding="utf-8").split("\n")
    total_moves = total_skips = touched = 0

    for i, line in enumerate(lines):
        match = SVG_LINE_RE.match(line)
        if not match:
            continue
        fig_id = "?"
        for back in range(i - 1, max(i - 10, -1), -1):
            found = FIG_ID_RE.search(lines[back])
            if found:
                fig_id = found.group(1)
                break
        if wanted and fig_id not in wanted:
            continue
        svg = json.loads(match.group(2))
        moves, skips = plan_figure(svg, fig_id)
        if not moves and not skips:
            continue
        print(f"\n{fig_id}")
        for move in moves:
            tag = "  (정렬 동반)" if move.get("with") else ""
            print(f"  옮김   {move['text']!r:22} {move['axis']} {move['old']:g} → {move['new']:g}"
                  f"   간격 {move['from']:.2f} → {move['to']:.2f} (기준 {move['want']:.2f}){tag}")
        for skip in skips:
            print(f"  건너뜀 {skip['text']!r:22} 간격 {skip['dist']:.2f} (기준 {skip['want']:.2f})"
                  f" — {skip['reason']}")
        total_moves += len(moves)
        total_skips += len(skips)
        if moves:
            touched += 1
            new_svg = apply_moves(svg, moves)
            lines[i] = (match.group(1) + json.dumps(new_svg, ensure_ascii=False)
                        + match.group(3))

    print(f"\n{path.name}: 옮김 {total_moves} · 건너뜀 {total_skips} · 삽화 {touched}개")
    if apply and total_moves:
        path.write_text("\n".join(lines), encoding="utf-8", newline="")
        print("  → 저장했다. 빌드와 렌더 검수를 반드시 돌릴 것.")
    elif not apply:
        print("  (보고만 했다 — 쓰려면 --apply)")
    return total_moves, total_skips


def _side_of(seg, box):
    """라벨 중심이 그 선분의 **어느 쪽**에 있는가 — 부호로만 답한다(0 = 선 위)."""
    cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
    qx, qy = _closest_point_on_segment(seg, cx, cy)
    vx, vy = cx - qx, cy - qy
    if abs(vx) >= abs(vy):
        return 0 if vx == 0 else (1 if vx > 0 else -1)
    return 1 if vy > 0 else -1


def verify_against(chapter_path, rev):
    """`rev` 대비 **선 반대편으로 넘어간 라벨**이 있는지 본다. 읽기 전용.

    왜 필요한가 (2026-07-30): 이 도구의 첫 판이 자리를 못 찾으면 반대 방향도 시도했고,
    그 결과 라벨이 **선 반대편으로 넘어갈 수 있었다**(간격은 맞지만 가리키는 쪽이 바뀐다).
    그 대안은 없앴지만, **이미 적용된 데이터가 안전한지는 따로 증명해야 한다** —
    "고쳤으니 괜찮다"는 검증이 아니다(AGENTS 규칙 11).
    `git show` 를 subprocess 로 읽으므로 작업 트리를 건드리지 않는다.
    """
    import subprocess
    rel = str(Path(chapter_path).relative_to(ROOT)).replace("\\", "/")
    old_text = subprocess.run(["git", "show", rev + ":" + rel], cwd=str(ROOT),
                              capture_output=True, encoding="utf-8").stdout
    if not old_text:
        print(f"  {Path(chapter_path).name}: {rev} 에서 읽지 못했다 — 건너뜀")
        return 0
    old_svgs, new_svgs = [], []
    for text, bucket in ((old_text, old_svgs),
                         (path_read(chapter_path), new_svgs)):
        for line in text.split("\n"):
            m = SVG_LINE_RE.match(line)
            if m:
                bucket.append(json.loads(m.group(2)))
    if len(old_svgs) != len(new_svgs):
        print(f"  {Path(chapter_path).name}: 삽화 수가 달라 대조 불가")
        return 0
    flips = 0
    for old_svg, new_svg in zip(old_svgs, new_svgs):
        if old_svg == new_svg:
            continue
        segments = _svg_segments(old_svg)
        old_texts, new_texts = _svg_texts(old_svg), _svg_texts(new_svg)
        if len(old_texts) != len(new_texts) or not segments:
            continue
        for ot, nt in zip(old_texts, new_texts):
            if ot["x"] == nt["x"] and ot["y"] == nt["y"]:
                continue
            obox, nbox = _text_bbox(ot), _text_bbox(nt)
            seg = min(segments, key=lambda s: _segment_to_rect_distance(s, obox))
            if _side_of(seg, obox) != _side_of(seg, nbox):
                flips += 1
                print(f"  ★ 넘어감 {ot['s'][:18]!r} — 선 {seg} 기준 반대편으로")
    print(f"  {Path(chapter_path).name}: 선 넘어간 라벨 {flips}건")
    return flips


def path_read(p):
    return Path(p).read_text(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="라벨-도형 간격을 규격까지 벌린다")
    parser.add_argument("--verify-against", dest="verify",
                        help="이 커밋 대비 '선 반대편으로 넘어간 라벨'을 찾는다 (읽기 전용)")
    parser.add_argument("--chapter", help="chNN.json (없으면 전 챕터)")
    parser.add_argument("--id", dest="ids", action="append", help="특정 삽화만 (반복 가능)")
    parser.add_argument("--apply", action="store_true", help="실제로 파일을 쓴다")
    args = parser.parse_args()

    print("[대상] " + DATA.name)
    chapters = ([DATA / args.chapter] if args.chapter
                else sorted(p for p in DATA.glob("ch*.json") if re.fullmatch(r"ch\d+\.json", p.name)))
    if args.verify:
        print(f"[검증] {args.verify} 대비 선을 넘어간 라벨을 찾는다 (읽기 전용)")
        total = sum(verify_against(p, args.verify) for p in chapters)
        print(f"\n합계: 선 넘어간 라벨 {total}건")
        return 1 if total else 0
    grand_moves = grand_skips = 0
    for path in chapters:
        moves, skips = run(path, set(args.ids) if args.ids else None, args.apply)
        grand_moves += moves
        grand_skips += skips
    if len(chapters) > 1:
        print(f"\n합계: 옮김 {grand_moves} · 건너뜀 {grand_skips}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
