# -*- coding: utf-8 -*-
"""삽화의 **캡션 블록**을 그림에서 규격만큼 떼어 놓는다 (신설 2026-08-23).

    python tools/fix_caption_block_gap.py [--chapter=chNN.json] [--show] [--apply]

★★ **열린 날 2026-08-23, 사용자 지적** (동역학 ch13 2절):
    *"같은 힘과 질량 사이 여백 있지 줄과 줄 사이 여백. 이거가 그 위에 줄과 다른 삽화 사이의
    여백과 차이가 있어야해. **위에가 더 커야지. 어느정돈 분리되게**"*

★ **규격은 이미 있었고 재는 자가 없었다.** AGENTS 「라벨의 기준 위치」가 *블록 간 1.5em ·
  캡션 줄 간격 0.5em* 을 정해 두었는데, 캡션 **줄끼리**의 간격만 자가 있고(C21
  `figure_text_grouping_hits`) **그림 ↔ 캡션 블록**은 아무도 안 봤다. 그래서 줄 간격은
  6개 삽화가 전부 0.56em 으로 가지런한데 그림과의 간격은 0.82~1.58em 으로 갈렸다
  (동역학 ch13 실측). 캡션이 그림에 붙어 **그림의 일부처럼** 읽히던 것이 그 결과다.

★ **무엇을 옮기나 — 캡션만 내리고 캔버스를 그만큼 늘린다.**
  그림을 올리면 위 여백이 줄어 `audit_figure_balance` 의 상하 균형이 깨진다. 캡션을 Δ 만큼
  내리고 `viewBox` 높이를 **같은 Δ 만큼** 늘리면 위 여백도 아래 여백도 그대로다.

★ **캡션 판정은 빌드와 같은 함수(`_is_caption_text`)를 쓴다.** 여기서 따로 «한글 몇 자» 를
  세면 자가 둘이 되어 갈라진다 — 이 리포가 반복해 데인 자리다.

★ **줄 간격은 안 건드린다.** 실측이 이미 규격(0.5em)에 맞고, 손대면 사용자가 «위가 더 커야
  한다» 고 한 그 대비가 아니라 **둘 다** 흔들린다.
"""
import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from buildlib.checks_svg import (_is_caption_text, _path_polyline, _svg_texts,  # noqa: E402
                                 _text_bbox)
from buildlib.jsontext import write_chapter  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 블록 경계의 규격. AGENTS 「라벨의 기준 위치」가 정본이고 여기서 다시 정하지 않는다.
BLOCK_GAP_EM = 1.5
# 허용 오차 — 규격에 맞춰 놓은 삽화를 반올림 차이로 다시 건드리지 않기 위한 값이다.
# 0.5 SVG px 는 이 리포의 좌표 표기(소수 첫째 자리)에서 «같은 자리» 로 볼 수 있는 최대치다.
TOLERANCE_PX = 0.5

_VIEWBOX_RE = re.compile(r"""viewBox\s*=\s*(['"])\s*([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\1""")
_NUM = r"[-+]?\d*\.?\d+"


def _floats(attrs, name):
    m = re.search(name + r"\s*=\s*['\"]\s*(" + _NUM + r")", attrs)
    return float(m.group(1)) if m else None


def drawing_bottom(svg, caption_positions):
    """캡션을 뺀 **그림 자체**의 아래 끝. 못 재면 None. 순수 함수 — 테스트가 직접 부른다."""
    bottom = None

    def push(v):
        nonlocal bottom
        if v is not None and (bottom is None or v > bottom):
            bottom = v

    for m in re.finditer(r"<(rect|circle|ellipse|line|path)\b([^>]*)>", svg):
        tag, attrs = m.group(1), m.group(2)
        if tag == "rect":
            y, h = _floats(attrs, "y"), _floats(attrs, "height")
            if y is not None:
                push(y + (h or 0))
        elif tag in ("circle", "ellipse"):
            cy = _floats(attrs, "cy")
            r = _floats(attrs, "r") if tag == "circle" else _floats(attrs, "ry")
            if cy is not None:
                push(cy + (r or 0))
        elif tag == "line":
            push(max(_floats(attrs, "y1") or 0, _floats(attrs, "y2") or 0))
        else:
            d = re.search(r"d\s*=\s*['\"]([^'\"]*)", attrs)
            if d:
                # `_path_polyline` 은 **선분**(x1, y1, x2, y2)을 준다 — 점이 아니다.
                for seg in _path_polyline(d.group(1)) or []:
                    push(max(seg[1], seg[3]))
    for it in _svg_texts(svg):
        if it["pos"] in caption_positions:
            continue
        push(_text_bbox(it)[3])
    return bottom


def plan(svg):
    """(Δ, 캡션들, 지금 간격, 규격) — 옮길 것이 없으면 None. 순수 함수."""
    texts = _svg_texts(svg)
    caps = [t for t in texts if _is_caption_text(t)]
    if not caps:
        return None
    caps.sort(key=lambda t: t["y"])
    # ★★ **캡션이라고 다 «아래 캡션 블록» 은 아니다** (첫 실행이 잡은 자를 다시 잰 자리).
    #   `_is_caption_text` 는 «굵지 않고 한글 6자 이상» 이라 그림 **한가운데의 설명 라벨**도
    #   캡션으로 친다. 그것을 블록의 첫 줄로 삼으면 그 아래 그림이 통째로 «그림 바닥» 이 되어
    #   간격이 **음수**로 나온다(ch12 실측 −311.6 등 6건). 규칙 11 이 말한 «새 자의 첫 출력은
    #   재는 것이 아니라 자를 재는 것» 의 실례라 그대로 적어 둔다.
    #   → 블록은 **그림 전체보다 아래에 있는 뒤쪽 연속 묶음**이다. 가장 큰 그런 묶음을 고른다.
    for k in range(len(caps)):
        block = caps[k:]
        bottom = drawing_bottom(svg, {t["pos"] for t in block})
        if bottom is None:
            return None
        top = _text_bbox(block[0])[1]
        if top < bottom:
            continue                       # 이 줄 위로 아직 그림이 남아 있다 — 블록이 아니다
        gap = top - bottom
        need = BLOCK_GAP_EM * block[0]["fs"]
        if gap >= need - TOLERANCE_PX:
            return None
        return (round(need - gap, 1), block, round(gap, 1), round(need, 1))
    return None


def shift(svg, delta, caps):
    """캡션들을 Δ 만큼 내리고 `viewBox` 높이를 같은 Δ 만큼 늘린 SVG. 순수 함수."""
    for it in sorted(caps, key=lambda t: t["pos"], reverse=True):
        head_end = svg.index(">", it["pos"])
        head = svg[it["pos"]:head_end]
        new_head = re.sub(r"(y\s*=\s*['\"])\s*" + _NUM,
                          lambda m: m.group(1) + _fmt(it["y"] + delta), head, count=1)
        svg = svg[:it["pos"]] + new_head + svg[head_end:]
    m = _VIEWBOX_RE.search(svg)
    if m:
        box = "viewBox='%s %s %s %s'" % (_fmt(float(m.group(2))), _fmt(float(m.group(3))),
                                         _fmt(float(m.group(4))),
                                         _fmt(float(m.group(5)) + delta))
        svg = svg[:m.start()] + box + svg[m.end():]
    return svg


def _fmt(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


def iter_figures(node):
    """`diagrams` 와 **슬라이드 `figure`** 를 함께 흘린다 — 둘 다 화면에 그려지는 그림이다."""
    if isinstance(node, dict):
        for pool in (node.get("diagrams"), [node.get("figure")]):
            if isinstance(pool, list):
                for fig in pool:
                    if isinstance(fig, dict) and fig.get("id") and fig.get("svg"):
                        yield fig
        for value in node.values():
            yield from iter_figures(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_figures(value)


def run(path, apply_changes):
    with open(path, encoding="utf-8", newline="") as fh:
        data = json.loads(fh.read())
    before = copy.deepcopy(data)
    hits = []
    for fig in iter_figures(data):
        p = plan(fig["svg"])
        if not p:
            continue
        delta, caps, gap, need = p
        hits.append((fig["id"], gap, need, delta))
        if apply_changes:
            fig["svg"] = shift(fig["svg"], delta, caps)
    name = os.path.basename(path)
    for fig_id, gap, need, delta in hits:
        print("  %-34s 지금 %5.1f  규격 %5.1f  →  %+.1f" % (fig_id, gap, need, delta))
    print("%s — 어긋남 %d건%s" % (name, len(hits), " (적용함)" if apply_changes and hits else ""))
    if apply_changes and hits:
        # ★ 표기 보존 기록기 — 통째로 다시 쓰면 재포맷 diff 가 변경점을 통째로 잡음으로 만든다.
        status, why = write_chapter(path, before, data)
        if status == "skipped":
            raise SystemExit("[FAIL] " + name + " — " + why)
    return len(hits)


def main():
    ap = argparse.ArgumentParser(description="캡션 블록을 그림에서 1.5em 떼어 놓는다")
    ap.add_argument("--chapter", help="chNN.json (없으면 그 과목 전 챕터)")
    ap.add_argument("--show", action="store_true", help="무엇이 걸리는지만 본다(기본)")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()
    # 과목 이름을 이 도구가 알면 안 된다 — 순회 대상은 `audit_content` 가 판정한 것을 쓴다
    # (AGENTS 「공통 도구에 과목별 사실을 박지 않는다」. 폴백을 두면 그 과목만 조용히 도는 길이 열린다).
    from audit_content import CHAPTERS, DATA
    root = DATA
    names = ([args.chapter] if args.chapter
             else [ch + ".json" for ch in CHAPTERS])
    total = 0
    for name in names:
        total += run(os.path.join(root, name), args.apply)
    print("합계 — 어긋남 %d건" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
