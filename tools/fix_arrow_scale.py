# -*- coding: utf-8 -*-
"""화살촉 크기를 규격(화면 실효 px)에 맞춘다 (신설 2026-08-02).

사용자 지적 두 개가 같은 뿌리였다:
  *[발화 생략]*
  *[발화 생략]*

**규격이 없었다.** 그래서 좌표로는 다들 `10 × 10` 을 쓰는데 viewBox 폭이 달라
화면에서는 19.1px vs 13.6px 로 갈렸다. 규격·근거는 `checks_svg.ARROW_HEAD_*` 주석이 정본이다.

★ **꼭짓점을 고정하고 밑변을 옮긴다.** 반대로 하면(밑변 고정) 꼭짓점이 움직여
  *[발화 생략]* 는 기존 규격(C5·F6·치수 끝점 검사)을 깬다.
  밑변이 움직이므로 **거기 붙어 있던 꼬리 선의 끝점도 함께** 옮긴다 — 안 그러면
  선이 화살촉 속으로 파고들거나 떠서 `_arrowhead_connection_issues` 가 잡는다.

꼬리 길이는 **건드리지 않는다.** 늘리면 다른 도형을 뚫을 수 있어서 어디를 넓힐지는
사람이 정해야 한다(사용자: *[발화 생략]*).
검사는 신고만 하고, 고치는 것은 삽화별 판단이다.

    python tools/fix_arrow_scale.py                 # 미리보기
    python tools/fix_arrow_scale.py --apply
    python tools/fix_arrow_scale.py --chapter=ch01 --apply
"""
import json
import math
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_content                                                       # noqa: E402
from buildlib.checks_svg import (                                          # noqa: E402
    ARROW_HEAD_MAX_PX, ARROW_HEAD_MIN_PX, ARROW_HEAD_TARGET_PX, ARROW_TAIL_MIN_RATIO,
    DIM_ARROW_WIDTH_RATIO_MAX, DIM_ARROW_WIDTH_RATIO_MIN, DIM_ARROW_WIDTH_RATIO_TARGET,
    FIGURE_RENDER_WIDTH, _attr, _distance, arrow_geometry, dim_arrow_positions,
)

DATA = audit_content.DATA
NUM = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
TRIANGLE_RE = re.compile(
    rf"M\s*({NUM})[ ,]({NUM})\s*L\s*({NUM})[ ,]({NUM})\s*L\s*({NUM})[ ,]({NUM})\s*Z", re.I)


def _fmt(value):
    text = ("%.2f" % value).rstrip("0").rstrip(".")
    return text if text not in ("", "-") else "0"


def _viewbox_width(svg):
    head = svg[svg.find("<svg"):svg.find(">") + 1]
    vb = _attr(head, "viewBox")
    try:
        return float(vb.split()[2])
    except (AttributeError, IndexError, ValueError):
        return None


def arrow_fixes(svg):
    """(옛 문자열, 새 문자열) 목록 — 삼각형과 그 꼬리 선의 끝점. 순수 함수(테스트가 부른다).

    ★ 꼬리 선은 **한 번에 모아서** 고친다 (열린 날 2026-08-02, 첫 실행에서 바로 터졌다).
      처음에는 화살촉마다 그 자리에서 선을 고쳤는데, **양 끝에 화살촉이 달린 선**은 편집이 둘
      생기고 둘 다 *원본 문자열*을 찾으므로 **뒤엣것이 조용히 버려진다**(먼저 것이 이미 원본을
      바꿔 놓았기 때문). 실측: 빌드 G1 *[발화 생략]* 11건.
      → 이동 목록을 먼저 다 모으고, 선을 훑으며 **양 끝을 한 번에** 반영한다.
    """
    view_width = _viewbox_width(svg)
    if not view_width:
        return []
    scale = FIGURE_RENDER_WIDTH / view_width
    dims = dim_arrow_positions(svg)
    edits, moves = [], []
    for arrow, match in zip(arrow_geometry(svg), _triangles(svg)):
        length = arrow["length"] * scale
        tip, base = arrow["tip"], arrow["base"]
        tail = None if arrow["tail"] is None else arrow["tail"] * scale
        # ★★ **치수 화살촉은 폭만 좁힌다** (2026-08-13). 제도 관례가 길이:폭 = 3:1 이라
        #   방향 화살촉(0.7~1.3)과 밴드가 다르다 — 근거는 `checks_svg.DIM_ARROW_WIDTH_RATIO_*`.
        #   ★ 폭만 바꾸는 편집은 **밑변 중심이 안 움직인다** → 꼬리를 따라 옮길 필요가 없어
        #     `_stem_can_follow` 게이트를 안 탄다(그 게이트는 밑변이 이동할 때의 «실금» 방지다).
        now_ratio = arrow["width"] / arrow["length"] if arrow["length"] else 1.0
        if arrow["pos"] in dims and not (
                DIM_ARROW_WIDTH_RATIO_MIN <= now_ratio <= DIM_ARROW_WIDTH_RATIO_MAX):
            axis = (tip[0] - base[0], tip[1] - base[1])
            norm = math.hypot(*axis)
            if not norm:
                continue
            unit = (axis[0] / norm, axis[1] / norm)
            perp = (-unit[1], unit[0])
            half = arrow["length"] * DIM_ARROW_WIDTH_RATIO_TARGET / 2.0
            corners = [(base[0] + perp[0] * half, base[1] + perp[1] * half),
                       (base[0] - perp[0] * half, base[1] - perp[1] * half)]
            edits.append((match.group(0), "M%s %s L%s %s L%s %s Z" % (
                _fmt(corners[0][0]), _fmt(corners[0][1]), _fmt(tip[0]), _fmt(tip[1]),
                _fmt(corners[1][0]), _fmt(corners[1][1]))))
            continue
        # ★★ **꼬리 하한도 이 도구가 푼다** (2026-08-05, 화살표 승격을 막던 11건).
        #   꼬리(`tail ≥ 1.5 × 촉`)는 여태 "늘리면 다른 도형을 뚫으니 사람이 정한다"며 손대지
        #   않았는데, 실측해 보니 **대부분은 늘릴 필요가 없었다** — 촉을 줄이면 밑변이 꼭짓점
        #   쪽으로 가고 꼬리가 그만큼 **늘어나기** 때문이다. 도형은 하나도 안 건드린다.
        #   촉을 δ 줄이면 조건은 `(T+δ) ≥ 1.5(L−δ)` 이므로 목표를 `(T+L)/2.5` 로 잡으면 된다.
        #   그래도 하한 8 에 못 미치는 것만 사람이 삽화를 키운다(실측 11건 중 2건).
        ratio_bad = tail is not None and tail < length * ARROW_TAIL_MIN_RATIO
        if ARROW_HEAD_MIN_PX <= length <= ARROW_HEAD_MAX_PX and not ratio_bad:
            continue
        # ★★ 머리와 꼬리는 **함께** 움직여야 한다 — 못 옮기면 아예 손대지 않는다
        #   (열린 날 2026-08-02, 사용자: *[발화 생략]*).
        #   머리만 줄이면 밑변이 꼬리 끝에서 떨어져 **실금 같은 틈**이 생기고,
        #   꼬리가 `<path>` 라 옮길 수단이 없으면 그 틈이 영구히 남는다.
        if not _stem_can_follow(svg, base, arrow["tail"]):
            continue
        axis = (tip[0] - base[0], tip[1] - base[1])
        norm = math.hypot(*axis)
        if not norm:
            continue
        unit = (axis[0] / norm, axis[1] / norm)
        # 목표 길이 — 기본은 13.5 지만, 꼬리가 짧으면 **촉을 줄여** 비를 맞춘다(위 주석의 산식).
        target = ARROW_HEAD_TARGET_PX
        if tail is not None:
            # 여유 0.15 — 딱 맞게 잡으면 반올림 때문에 **경계에서 다시 걸린다**
            #   (실측: 꼬리 13.8 vs 필요 13.8 로 3건이 되돌아왔다).
            target = min(target, (tail + length) / (ARROW_TAIL_MIN_RATIO + 1.0) - 0.15)
        target = max(target, ARROW_HEAD_MIN_PX)        # 하한 밑으로는 안 내린다 — 사람이 삽화를 키운다
        want = target / scale                          # SVG px 로 되돌린 목표 길이
        ratio = arrow["width"] / arrow["length"] if arrow["length"] else 1.0
        half = want * ratio / 2.0
        new_base = (tip[0] - unit[0] * want, tip[1] - unit[1] * want)
        perp = (-unit[1], unit[0])
        corners = [(new_base[0] + perp[0] * half, new_base[1] + perp[1] * half),
                   (new_base[0] - perp[0] * half, new_base[1] - perp[1] * half)]
        edits.append((match.group(0), "M%s %s L%s %s L%s %s Z" % (
            _fmt(corners[0][0]), _fmt(corners[0][1]), _fmt(tip[0]), _fmt(tip[1]),
            _fmt(corners[1][0]), _fmt(corners[1][1]))))
        moves.append((base, new_base))
    edits.extend(_stem_edits(svg, moves))
    return edits


def _triangles(svg):
    """`arrow_geometry` 와 **같은 순서**의 정규식 매치 — 짝을 지어 쓰기 위한 것."""
    out = []
    for match in TRIANGLE_RE.finditer(svg):
        points = [(float(match[i]), float(match[i + 1])) for i in (1, 3, 5)]
        pairs = ((0, 1), (0, 2), (1, 2))
        if max(_distance(points[a], points[b]) for a, b in pairs) > 40:
            continue
        out.append(match)
    return out


STEM_SNAP_PX = 6.0    # 밑변 중앙에서 이만큼 안에 있는 선 끝은 '이 화살촉의 꼬리'다
STEM_MIN_LEN = 2.0    # 고친 뒤 이보다 짧아지면 선이 사라진 것이다 — 건드리지 않는다


def _stem_can_follow(svg, base, tail):
    """이 화살촉의 꼬리를 함께 옮길 수 있는가. 순수 함수 — 테스트가 직접 부른다.

    ⑴ 꼬리가 아예 없으면 옮길 것도 없다 → 안전.
    ⑵ 꼬리가 `<line>` 이면 옮길 수 있다. 단 **옮긴 뒤 사라질 만큼 짧으면** 안 된다.
    ⑶ 꼬리가 `<path>` 면 이 도구가 옮길 수단이 없다 → 손대지 않는다(틈이 남는다).
    """
    if tail is None:
        return True
    for m in re.finditer(r"<line\b([^>]*?)/?>", svg):
        attrs = m.group(1)
        try:
            ends = [(float(_attr(attrs, "x1")), float(_attr(attrs, "y1"))),
                    (float(_attr(attrs, "x2")), float(_attr(attrs, "y2")))]
        except (TypeError, ValueError):
            continue
        near = min((0, 1), key=lambda i: _distance(ends[i], base))
        if _distance(ends[near], base) > STEM_SNAP_PX:
            continue
        # 남는 쪽 끝과 새 밑변 사이가 최소 길이보다 짧아질 수 있는지는 호출부가 모른다 —
        # 여기서는 **지금 길이**로 판정한다. 짧은 꼬리는 이 도구가 손대면 안 되는 부류다.
        return _distance(ends[0], ends[1]) >= ARROW_HEAD_TARGET_PX / 2.0
    for m in STEM_PATH_RE.finditer(svg):      # 한 마디 직선 `<path>` 꼬리 (2026-08-05)
        ends = _path_stem_ends(m)
        if not ends:
            continue
        near = min((0, 1), key=lambda i: _distance(ends[i], base))
        if _distance(ends[near], base) > STEM_SNAP_PX:
            continue
        return _distance(ends[0], ends[1]) >= ARROW_HEAD_TARGET_PX / 2.0
    return False                              # 곡선·다중 마디 꼬리 — 옮길 수단이 없다


def _stem_edits(svg, moves):
    """꼬리 선의 끝점을 새 밑변 중앙으로 옮긴다 — 선마다 **양 끝을 함께** 본다.

    반경을 `STEM_SNAP_PX` 로 잡는 이유: 원래 규격대로 밑변 중앙에 정확히 닿은 선뿐 아니라,
    **화살촉 속으로 파고든 선**(G1 이 잡는 그 결함)도 같이 끌어당기기 위해서다.

    ★★ **한 선의 두 끝을 같은 화살촉으로 끌어당기지 않는다** (열린 날 2026-08-02, 실사고).
      `fig-q16-hydraulic-lift` 의 s₁ 화살표는 꼬리가 6px 뿐이라 **양 끝이 모두** 밑변 6px 안에
      들어왔고, 둘 다 같은 점으로 옮겨져 **길이 0 — 화면에서 꼬리가 통째로 사라졌다**
      (사용자: *[발화 생략]*). 짧은 꼬리는 이 규격이 고치려던 바로 그 대상인데,
      고치는 도구가 그것을 **지워 버린** 것이다.
      → ⑴ 화살촉 하나당 **가장 가까운 끝 하나만** 옮기고 ⑵ 고친 뒤 길이가 `STEM_MIN_LEN`
        미만이면 그 선은 건드리지 않는다(꼬리 하한은 검사가 신고하고 사람이 늘린다).
    """
    edits = []
    for m in re.finditer(r"<line\b([^>]*?)/?>", svg):
        attrs = m.group(1)
        try:
            ends = [(float(_attr(attrs, "x1")), float(_attr(attrs, "y1"))),
                    (float(_attr(attrs, "x2")), float(_attr(attrs, "y2")))]
        except (TypeError, ValueError):
            continue
        moved = list(ends)
        for old_base, new_base in moves:
            if _distance(old_base, new_base) < 0.01:
                continue                      # 크기를 안 바꾼 화살촉 — 옮길 것이 없다
            near = min((0, 1), key=lambda i: _distance(ends[i], old_base))
            if _distance(ends[near], old_base) > STEM_SNAP_PX:
                continue
            moved[near] = new_base
        if moved == ends:
            continue
        if _distance(moved[0], moved[1]) < STEM_MIN_LEN:
            continue                          # 꼬리가 사라진다 — 그건 고침이 아니라 삭제다
        new = m.group(0)
        for i, suffix in enumerate(("1", "2")):
            if moved[i] != ends[i]:
                new = _replace_pair(new, "x" + suffix, "y" + suffix, moved[i])
        edits.append((m.group(0), new))
    # 한 마디 직선 `<path>` 꼬리도 같은 규칙으로 옮긴다 — 판정·안전장치를 `<line>` 과 공유한다.
    for m in STEM_PATH_RE.finditer(svg):
        ends = _path_stem_ends(m)
        if not ends:
            continue
        moved = list(ends)
        for old_base, new_base in moves:
            if _distance(old_base, new_base) < 0.01:
                continue
            near = min((0, 1), key=lambda i: _distance(ends[i], old_base))
            if _distance(ends[near], old_base) > STEM_SNAP_PX:
                continue
            moved[near] = new_base
        if moved == list(ends):
            continue
        if _distance(moved[0], moved[1]) < STEM_MIN_LEN:
            continue                          # 꼬리가 사라진다 — 그건 고침이 아니라 삭제다
        edits.append((m.group(0), _path_stem_markup(m, moved)))
    return edits


# ★★ **`<path>` 꼬리도 옮긴다** (2026-08-05, R-22 착수 중 실측으로 열림).
#
#   무엇이 새어나갔나 — 검사 문구는 *[발화 생략]* 고 말하는데,
#   `_stem_can_follow` 가 **꼬리가 `<line>` 일 때만** 옮겼다. 그런데 실측 `ch02.json` 의
#   `<line>` 은 **0개**(꼬리가 전부 `<path>`)라, 이 과목에서 그 도구는 구조적으로 거의 아무것도
#   못 고쳤다 — 빌드는 11 삽화 44건을 신고하는데 도구는 2 삽화만 집었다.
#   ★ 부류: **처방의 순회가 자보다 좁다**(2026-08-02·08-04 에 이어 3회째). 이번엔 좁은 것이
#     *의도적*이었다는 점이 다르다 — 문제는 설계가 아니라 **문구가 그 한계를 모른 채 도구를
#     가리킨 것**이다. 여기서 한계 자체를 없앤다.
#
#   ★ **한 마디짜리 직선 path 만** 옮긴다: `M x y L x2 y2` · `M x y H x2` · `M x y V y2`.
#     곡선(C·Q)·다중 마디는 손대지 않는다 — 끝점만 옮기면 곡률이 어긋나 선이 휜다.
#     못 옮기는 것은 예전처럼 **건너뛴다**(실금을 남기느니 안 건드린다).
STEM_PATH_RE = re.compile(
    rf"<path\b([^>]*?\bd=')M\s*({NUM})[ ,]({NUM})\s*"
    rf"(?:([LlHhVv])\s*({NUM})(?:[ ,]({NUM}))?)\s*('[^>]*?)/?>", re.I)


def _path_stem_ends(match):
    """한 마디 직선 path 의 (시작점, 끝점). 못 읽으면 None. 순수 함수 — 테스트가 부른다."""
    x1, y1 = float(match.group(2)), float(match.group(3))
    cmd, a = match.group(4), float(match.group(5))
    b = match.group(6)
    if cmd in "Ll":
        if b is None:
            return None
        x2, y2 = (a, float(b)) if cmd == "L" else (x1 + a, y1 + float(b))
    elif cmd in "Hh":
        x2, y2 = (a if cmd == "H" else x1 + a), y1
    else:
        x2, y2 = x1, (a if cmd == "V" else y1 + a)
    return (x1, y1), (x2, y2)


def _path_stem_markup(match, ends):
    """끝점을 옮긴 새 `<path>` 마크업 — 명령은 절대 `L` 로 통일한다(가장 안전한 형태)."""
    (x1, y1), (x2, y2) = ends
    return ("<path" + match.group(1) + "M%s %s L%s %s" % (_fmt(x1), _fmt(y1), _fmt(x2), _fmt(y2))
            + match.group(7) + "/>")


def _replace_pair(markup, kx, ky, point):
    for key, value in ((kx, point[0]), (ky, point[1])):
        markup = re.sub(r"(\b%s=')[^']*(')" % key, r"\g<1>" + _fmt(value) + r"\g<2>", markup)
    return markup


def main():
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    # ★ 삽화 하나만 고칠 수 있어야 한다 — 규격을 만들었다고 전 챕터를 한꺼번에 흔들면
    #   지적받지 않은 삽화가 깨진다(2026-08-02 실사고: 12삽화를 되돌렸다).
    only_ids = {a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")}
    apply_edits = "--apply" in sys.argv
    print("규격: 화살촉 길이 %g~%g px (목표 %g) · 화면 실효 — 근거는 checks_svg.ARROW_HEAD_* 주석"
          % (ARROW_HEAD_MIN_PX, ARROW_HEAD_MAX_PX, ARROW_HEAD_TARGET_PX))
    moved = 0
    # `audit_content.CHAPTERS` 는 확장자 없는 `ch01` 형태다 — 파일명으로 맞춘다.
    for stem in audit_content.CHAPTERS:
        if only and stem != only:
            continue
        name = stem + ".json"
        path = os.path.join(DATA, name)
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        chapter = json.loads(raw)
        changed = False
        for fig_id, diagram in _iter_diagrams(chapter):
            if only_ids and fig_id not in only_ids:
                continue
            svg = str(diagram.get("svg") or "")
            edits = arrow_fixes(svg)
            if not edits:
                continue
            new_svg = svg
            for old, new in edits:
                if old in new_svg:
                    new_svg = new_svg.replace(old, new, 1)
            if new_svg == svg:
                continue
            print("  %-38s 화살촉 %d개 교정" % (fig_id, sum(1 for o, _n in edits if o.startswith("M"))))
            moved += 1
            if apply_edits:
                diagram["svg"] = new_svg
                changed = True
        if changed:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(chapter, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            print("[쓰기] " + name)
    print("\n삽화 %d건%s" % (moved, "" if apply_edits else " (미리보기 — --apply 로 반영)"))
    return 0


def _iter_diagrams(node, trail="root"):
    if isinstance(node, dict):
        for dg in node.get("diagrams") or []:
            if isinstance(dg, dict):
                yield str(dg.get("id") or trail), dg
        for key, value in node.items():
            if key != "diagrams":
                yield from _iter_diagrams(value, trail + "/" + str(key))
    elif isinstance(node, list):
        for item in node:
            yield from _iter_diagrams(item, trail)


if __name__ == "__main__":
    sys.exit(main())
