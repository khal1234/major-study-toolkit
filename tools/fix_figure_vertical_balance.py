# -*- coding: utf-8 -*-
"""삽화의 **세로 균형**을 맞춘다 — 위 여백 == 아래 여백.

왜 도구인가 (신설 2026-07-30):
    `audit_figure_balance.py` 가 재는 '균형 이탈'이 ch02 32건·ch03 10건·ch04 7건으로
    **49건**이었다. 손으로 고치면 삽화마다 여백 기준이 갈라지고, 그게 바로 이 규격이
    없애려는 결함이다(사용자 지적 *"위 아래 여백이 개판"* — 같은 삽화로 3회).
    `fix_figure_caption_tier.py`·`fix_figure_text_scale.py` 와 같은 이유로 도구로 만든다.

**어떻게 고치나 — 좌표를 옮기지 않는다.**
    viewBox 의 `min-y` 만 움직인다. 콘텐츠 좌표는 한 글자도 건드리지 않으므로
    ⑴ 도형끼리의 상대 위치 ⑵ 라벨 간격 ⑶ 화살촉 연결이 **정의상 그대로**다.
    높이(`height`)도 바뀌지 않는다 — 위·아래 여백의 합은 보존되고 배분만 바뀌기 때문이다:
        새 min-y = min-y + (위여백 − 아래여백) / 2
    배경 사각형(viewBox 를 통째로 덮는 rect)은 새 viewBox 를 따라 같이 옮긴다.
    안 옮기면 아래쪽에 배경이 없는 띠가 생긴다.

**무엇을 고치지 않나.**
    - 여백의 **총량**은 줄이지 않는다. `fig-02-p03` 처럼 위아래 합이 165px(높이의 61%)인
      삽화는 균형을 맞춰도 여전히 헐렁하다 — 그건 viewBox 를 줄이는 별개 판단이고
      가로세로비가 바뀌므로 사용자 확인을 받는다. 이 도구는 **배분만** 한다.
    - 콘텐츠가 이미 viewBox 밖으로 나간 삽화(여백 < 0)는 건너뛴다. 균형을 맞추면
      넘친 사실이 숨겨진다 — 그건 고치는 게 아니라 가리는 것이다.

**계산은 감사와 같은 함수를 쓴다.** `audit_figure_balance._content_extent` 를 import 한다 —
    같은 것을 두 곳에서 재면 반드시 갈라지고, 그러면 "도구를 돌렸는데 감사가 그대로"가 된다
    (2026-07-30 파선 역할 등록부에서 실제로 겪은 부류).

사용:
    python tools/fix_figure_vertical_balance.py                    # 미리보기(전 챕터)
    python tools/fix_figure_vertical_balance.py --apply
    python tools/fix_figure_vertical_balance.py --chapter=ch02 --apply
    python tools/fix_figure_vertical_balance.py --except=fig-a,fig-b --apply
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from audit_figure_balance import _content_extent, _viewbox, BALANCE_TOL_PX  # noqa: E402
from buildlib.checks_svg import _attr                                       # noqa: E402
from fix_figure_text_scale import subject_dirs, _my_subject                 # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.join(ROOT, "data")
FIG_ID_RE = re.compile(r'"id":\s*"([^"]+)"')
RECT_RE = re.compile(r"<rect\b([^>]*?)/?>")
# viewBox 는 `<svg …>` 여는 태그 안에만 있다. 데이터에서 따옴표는 항상 작은따옴표다.
VIEWBOX_RE = re.compile(r"viewBox='([^']*)'")


def _fmt(value):
    return str(int(value)) if float(value).is_integer() else format(value, ".1f")


def _round_half(value):
    return round(value * 2.0) / 2.0


def _covering_rect(svg_line, vb):
    """viewBox 를 통째로 덮는 배경 사각형의 (match, x, y, w, h). 없으면 None.

    '덮는다'의 판정은 네 값이 viewBox 와 1.5px 안에서 일치하는 것 —
    `_content_extent` 가 배경 변을 제외할 때 쓰는 것과 같은 허용치다.
    """
    vx, vy, vw, vh = vb
    for m in RECT_RE.finditer(svg_line):
        attrs = m.group(1)
        try:
            x = float(_attr(attrs, "x", "0") or 0)
            y = float(_attr(attrs, "y", "0") or 0)
            w = float(_attr(attrs, "width", "0") or 0)
            h = float(_attr(attrs, "height", "0") or 0)
        except (TypeError, ValueError):
            continue
        if (abs(x - vx) < 1.5 and abs(y - vy) < 1.5
                and abs(w - vw) < 1.5 and abs(h - vh) < 1.5):
            return m, x, y, w, h
    return None


def _set_y(rect_tag, new_y):
    """`<rect …>` 태그의 y 를 바꾼다. y 속성이 없으면 넣는다(기본값 0이라 생략돼 있다)."""
    if re.search(r"\by='[^']*'", rect_tag):
        return re.sub(r"\by='[^']*'", "y='" + _fmt(new_y) + "'", rect_tag, count=1)
    return rect_tag.replace("<rect", "<rect y='" + _fmt(new_y) + "'", 1)


def plan_line(svg_line):
    """svg 한 줄 → (새 줄, 옮긴 px, 설명). 순수 함수 — 테스트가 직접 부른다.

    옮긴 px 가 0이면 손대지 않은 것이다.
    """
    vb = _viewbox(svg_line)
    if not vb or len(vb) != 4:
        return svg_line, 0.0, ""
    vx, vy, vw, vh = vb
    top, bottom = _content_extent(svg_line, vb)
    if top is None:
        return svg_line, 0.0, ""
    pad_top = top - vy
    pad_bottom = (vy + vh) - bottom
    if pad_top < 0 or pad_bottom < 0:
        return svg_line, 0.0, ("콘텐츠가 viewBox 밖 — 건너뜀 (위 " + format(pad_top, ".1f")
                               + " 아래 " + format(pad_bottom, ".1f") + ")")
    if abs(pad_bottom - pad_top) <= BALANCE_TOL_PX:
        return svg_line, 0.0, ""
    shift = _round_half((pad_top - pad_bottom) / 2.0)
    if not shift:
        return svg_line, 0.0, ""
    new_vy = vy + shift

    out = VIEWBOX_RE.sub(
        lambda m: "viewBox='" + " ".join(_fmt(v) for v in (vx, new_vy, vw, vh)) + "'",
        svg_line, count=1)

    found = _covering_rect(out, vb)
    if found:
        m, _x, _y, _w, _h = found
        out = out[:m.start()] + _set_y(m.group(0), new_vy) + out[m.end():]
        bg = ""
    else:
        bg = " · 배경 사각형 없음"
    note = ("위 " + format(pad_top, ".1f") + " / 아래 " + format(pad_bottom, ".1f")
            + " → 양쪽 " + format((pad_top + pad_bottom) / 2.0, ".1f")
            + " (viewBox min-y " + _fmt(vy) + " → " + _fmt(new_vy) + ")" + bg)
    return out, shift, note


def main():
    apply = "--apply" in sys.argv
    only_ch = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    if only_ch:
        only_ch = only_ch.replace(".json", "")
    skip = set()
    for a in sys.argv:
        if a.startswith("--except="):
            skip.update(s.strip() for s in a.split("=", 1)[1].split(",") if s.strip())
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--subject=")), None)
    mine = arg or _my_subject()
    names = sorted(n for n in os.listdir(DATA_ROOT)
                   if os.path.isdir(os.path.join(DATA_ROOT, n)))
    dirs = subject_dirs(names, mine)
    if not dirs:
        print("거부 — 이 브랜치의 과목 폴더를 찾지 못했다(과목=" + str(mine) + ").\n"
              "  과목 워크트리에서 실행하거나 `--subject=<폴더 접두어>` 를 줄 것.")
        return 2
    DATA = os.path.join(DATA_ROOT, dirs[0])
    print("[대상] data/" + dirs[0])

    total = 0
    skipped = []
    for name in sorted(os.listdir(DATA)):
        if not re.fullmatch(r"ch\d+\.json", name):
            continue
        if only_ch and os.path.splitext(name)[0] != only_ch:
            continue
        path = os.path.join(DATA, name)
        lines = open(path, encoding="utf-8").read().split("\n")
        touched = 0
        for i, line in enumerate(lines):
            if '"svg":' not in line:
                continue
            fig = "?"
            for back in range(i - 1, max(i - 8, -1), -1):
                m = FIG_ID_RE.search(lines[back])
                if m:
                    fig = m.group(1)
                    break
            if fig in skip:
                print("  " + name + " · " + fig + ": 건너뜀 (--except)")
                continue
            new_line, shift, note = plan_line(line)
            if not shift:
                if note:
                    skipped.append(name + " · " + fig + ": " + note)
                continue
            print("  " + name + " · " + fig + ": " + note)
            lines[i] = new_line
            touched += 1
            total += 1
        if touched and apply:
            open(path, "w", encoding="utf-8", newline="").write("\n".join(lines))

    for row in skipped:
        print("  [건너뜀] " + row)
    print()
    print(("반영" if apply else "미리보기") + " — 삽화 " + str(total) + "개")
    if not apply:
        print("실제로 쓰려면 --apply 를 붙일 것")
    return 0


if __name__ == "__main__":
    sys.exit(main())
