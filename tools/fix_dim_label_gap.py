# -*- coding: utf-8 -*-
r"""치수 라벨을 **자기 치수선에 붙인다** — 규격이 바뀐 뒤의 전수 정리 도구.

★ 왜 열렸나 (2026-08-13). 사용자가 `ℓ` 하나를 두고 *[발화 생략]* 를 세 번 말했고, 그 과정에서
  **자 두 개가 다른 것을 재고 있던 것**이 드러났다 — 「치수선 라벨은 0.94em」 규격은 **잉크**로,
  빌드 F1 의 하한은 **글자 상자**로 잰다. 상자는 디센더 자리만큼 잉크보다 내려가므로,
  잉크로 규격을 맞춰도 상자로는 막히는 자리가 생긴다.
  그래서 치수 라벨에만 별도 하한(`DIM_LABEL_GAP_MIN_EM`)을 두고 값을 내렸는데,
  **그 자로 다시 봐야 하는 라벨이 그 하나만이 아니다.** 이 도구가 그 전수를 맡는다.

★★ **손으로 옮기지 말 것.** 오늘 화살촉에서 배운 그대로다 — 값은 한 번에 안 정해진다
  (1.00 → 0.80 → 0.35 → 0.80 → 0.60). 손으로 옮기면 **되돌릴 수가 없다.**

무엇을 하나
  `class='dim'`·`id='dim-…'` 안의 `<text>` 중 **자기 그룹 안의 가로 치수선**과 짝지어지는 것을
  찾아, 글자 상자–선 간격을 `DIM_LABEL_GAP_TARGET_EM` 으로 맞춘다(위/아래 어느 쪽이든).

무엇을 안 하나
  · **가로 치수선이 아닌 것**(세로 치수선의 옆 라벨)은 건드리지 않는다 — 좌우 배치는 규칙이 다르다.
  · 그룹 안에 치수선 후보가 둘 이상이면 **가장 가까운 것**을 쓰되, 거리가 같으면 건너뛴다.
  · 이미 목표 ±0.5px 안이면 안 움직인다(잡음 diff 를 만들지 않는다).

쓰는 법
  python tools/fix_dim_label_gap.py                # 미리보기
  python tools/fix_dim_label_gap.py --apply
  python tools/fix_dim_label_gap.py --chapter=ch05.json --apply
"""
import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import audit_content                                                       # noqa: E402
from buildlib.checks_svg import (                                          # noqa: E402
    DIM_LABEL_GAP_MIN_EM, DIM_SIDE_LABEL_GAP_MIN_EM, DIM_SIDE_LABEL_GAP_TARGET_EM, _attr, _svg_segments_split,
    _svg_texts, _tagged_group_spans, _text_bbox,
)
# ★ 챕터 파일은 **표기 보존 기록기**로만 쓴다 — 통째로 다시 쓰면 손으로 압축해 둔 SVG 표기가
#   전부 재포맷된다. 이 부류는 `fix_dim_label` 로 한 번 재발했고, 그래서 `test_checks` 가
#   *[발화 생략]* 을 계약으로 잠갔다.
#   (그 계약은 글자로 검사하므로 여기 통째 재작성 함수의 **이름을 적지 않는다** — 주석이
#    검사에 걸리는 것도 이 리포가 겪은 부류다.)
from buildlib.jsontext import write_chapter                                # noqa: E402

DATA = audit_content.DATA
NUM = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
# 목표는 하한보다 살짝 위다 — 딱 하한에 두면 반올림으로 다시 걸린다(화살촉에서 겪은 자리).
DIM_LABEL_GAP_TARGET_EM = DIM_LABEL_GAP_MIN_EM + 0.02
# 이보다 멀면 «그 치수선에 붙은 라벨» 이 아니다 — 아래 주석이 정본.
DIM_LABEL_ATTACHED_MAX_EM = 1.5
HLINE_RE = re.compile(rf"M\s*({NUM})[ ,]({NUM})\s*H\s*({NUM})", re.I)


def _viewbox(svg):
    head = svg[svg.find("<svg"):svg.find(">") + 1]
    vb = _attr(head, "viewBox")
    if not vb:
        return None
    try:
        return [float(v) for v in vb.split()]
    except ValueError:
        return None


def label_moves(svg):
    """(옛 `y='…'` 조각, 새 조각, 사유) 목록. 순수 함수 — 테스트가 부른다."""
    vb = _viewbox(svg)
    if not vb:
        return []
    spans = [(s, e) for s, e, _b in _tagged_group_spans(svg, ("dim",))]
    if not spans:
        return []
    out = []
    for t in _svg_texts(svg):
        if not t["s"].strip():
            continue
        span = next(((s, e) for s, e in spans if s <= t["pos"] < e), None)
        if span is None:
            continue
        box = _text_bbox(t)
        # 같은 그룹 안의 **가로** 선만 짝으로 본다.
        near = []
        for m in HLINE_RE.finditer(svg[span[0]:span[1]]):
            x0, ly, x1 = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if max(x0, x1) < box[0] or min(x0, x1) > box[2]:
                continue                  # 글자 아래·위에 걸치지 않는 선
            gap = ly - box[3] if ly > box[3] else (box[1] - ly if ly < box[1] else 0.0)
            if gap > 0:
                near.append((gap, ly, ly > box[3], (x0 + x1) / 2.0))
        if not near:
            move = _side_move(svg, t, box)
            if move:
                out.append(move)
            continue
        near.sort()
        if len(near) > 1 and abs(near[0][0] - near[1][0]) < 0.5:
            continue                      # 어느 선의 라벨인지 못 가른다 — 사람이 본다
        gap, ly, below, line_mid = near[0]
        # ★★ **멀리 있는 글자는 그 선의 라벨이 아니다** (첫 실행에서 바로 드러났다).
        #   그룹 안 «가장 가까운 가로선» 만으로 짝을 지으면 38~70px 떨어진 글자까지 끌려온다 —
        #   그건 치수 라벨이 아니라 그 그룹에 같이 든 다른 글자다. 그대로 옮겼으면 삽화가 깨졌다.
        #   ★ 이 리포가 「검사가 결함을 유도하던 자리」라고 부르는 부류다 — 자가 대상을 넓게 잡으면
        #     자를 맞추려고 데이터를 나쁘게 만든다. 그래서 **이미 붙어 있는 것만** 당긴다.
        if gap > t["fs"] * DIM_LABEL_ATTACHED_MAX_EM:
            continue
        chunk = svg[t["pos"]:t["end"]]
        want = t["fs"] * DIM_LABEL_GAP_TARGET_EM
        delta = (gap - want) * (1 if below else -1)
        old_y = "y='%s'" % _fmt(t["y"])
        if abs(delta) >= 0.5 and old_y in chunk:
            out.append((t["pos"], old_y, "y='%s'" % _fmt(t["y"] + delta),
                        "%s  세로 간격 %.1f → %.1f px (%.2f → %.2fem)"
                        % (repr(t["s"].strip()[:14]), gap, want,
                           gap / t["fs"], DIM_LABEL_GAP_TARGET_EM)))
        # ★★ **좌우도 맞춘다 — 치수 라벨은 자기 치수선의 가운데다** (2026-08-13, 사용자:
        #   *[발화 생략]*).
        #   위아래만 맞추면 «붙긴 했는데 한쪽으로 쏠린» 라벨이 남는다 — 두 축은 한 배치다.
        #   ★ 기준은 **치수선의 중점**이지 글자 상자의 중심이 아니다. `text-anchor` 가
        #     무엇이든 상자로 재서 옮기므로 앵커를 바꿀 필요가 없다.
        dx = line_mid - (box[0] + box[2]) / 2.0
        old_x = "x='%s'" % _fmt(t["x"])
        if abs(dx) >= 0.5 and old_x in chunk:
            out.append((t["pos"], old_x, "x='%s'" % _fmt(t["x"] + dx),
                        "%s  가로 어긋남 %+.1f px → 치수선 중점"
                        % (repr(t["s"].strip()[:14]), -dx)))
    return out


def _side_move(svg, t, box):
    """세로 치수선 **옆** 라벨의 가로 간격을 `DIM_SIDE_LABEL_GAP_TARGET_EM` 으로 맞춘다.

    짝: 글자 상자의 세로 범위에 걸치는 세로 선 중 옆으로 가장 가까운 것.
    못 보는 것: 돌아간 글자(`mat`) · 좌우 거리가 같은 선 둘(어느 쪽 라벨인지 모른다).
    """
    if t.get("mat") is not None:
        return None
    near = []
    for sx0, sy0, sx1, sy1 in _svg_segments_split(svg)[0]:
        if abs(sx0 - sx1) > 0.5 or max(sy0, sy1) < box[1] or min(sy0, sy1) > box[3]:
            continue
        if sx0 <= box[0]:
            near.append((box[0] - sx0, -1.0))
        elif sx0 >= box[2]:
            near.append((sx0 - box[2], 1.0))
    near = sorted(n for n in near if n[0] > 0)
    if not near or near[0][0] > t["fs"] * DIM_LABEL_ATTACHED_MAX_EM:
        return None
    if len(near) > 1 and abs(near[0][0] - near[1][0]) < 0.5:
        return None
    gap, side = near[0]
    want = t["fs"] * DIM_SIDE_LABEL_GAP_TARGET_EM
    # 넓히기만 한다 — 이미 하한보다 먼 글자는 그 선의 치수 라벨이 아닐 수 있다(화살표 이름 등).
    if gap >= t["fs"] * DIM_SIDE_LABEL_GAP_MIN_EM:
        return None
    dx = (gap - want) * side
    old_x = "x='%s'" % _fmt(t["x"])
    chunk = svg[t["pos"]:t["end"]]
    if abs(dx) < 0.5 or old_x not in chunk:
        return None
    return (t["pos"], old_x, "x='%s'" % _fmt(t["x"] + dx),
            "%s  옆 간격 %.1f → %.1f px (%.2f → %.2fem)"
            % (repr(t["s"].strip()[:14]), gap, want, gap / t["fs"],
               DIM_SIDE_LABEL_GAP_TARGET_EM))


def _fmt(v):
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return s if s else "0"


def apply_moves(svg, moves):
    """뒤에서부터 갈아끼운다 — 앞에서 고치면 뒤 위치가 밀린다."""
    for pos, old, new, _why in sorted(moves, key=lambda m: -m[0]):
        end = svg.find(">", pos)
        chunk = svg[pos:end]
        svg = svg[:pos] + chunk.replace(old, new, 1) + svg[end:]
    return svg


def main():
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    apply_it = "--apply" in sys.argv
    print("규격: 치수 라벨–치수선 간격 %.2fem (글자 상자 기준) — 근거는 "
          "checks_svg.DIM_LABEL_GAP_MIN_EM 주석" % DIM_LABEL_GAP_TARGET_EM)
    total = 0
    for ch in audit_content.CHAPTERS:
        name = ch + ".json"
        if only and only not in (name, ch):
            continue
        path = os.path.join(DATA, name)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        before = copy.deepcopy(data)
        touched = False
        for dg in _iter_diagrams(data):
            svg = dg.get("svg") or ""
            moves = label_moves(svg)
            if not moves:
                continue
            for _pos, _old, _new, why in moves:
                print("  %-38s %s" % (dg.get("id", "?"), why))
            total += len(moves)
            if apply_it:
                dg["svg"] = apply_moves(svg, moves)
                touched = True
        if touched:
            state, why = write_chapter(path, before, data)
            print("[%s] %s%s" % ("쓰기" if state == "written" else state, name,
                                 (" — " + why) if why else ""))
    print("\n라벨 %d개%s" % (total, "" if apply_it else " (미리보기 — --apply 로 반영)"))
    return 0


def _iter_diagrams(node):
    if isinstance(node, dict):
        if "svg" in node and isinstance(node.get("svg"), str):
            yield node
        for value in node.values():
            for hit in _iter_diagrams(value):
                yield hit
    elif isinstance(node, list):
        for value in node:
            for hit in _iter_diagrams(value):
                yield hit


if __name__ == "__main__":
    sys.exit(main())
