# -*- coding: utf-8 -*-
"""삽화의 **세로 균형**을 맞춘다 — 위 여백 == 아래 여백.

왜 도구인가 (신설 2026-07-30):
    `audit_figure_balance.py` 가 재는 '균형 이탈'이 ch02 32건·ch03 10건·ch04 7건으로
    **49건**이었다. 손으로 고치면 삽화마다 여백 기준이 갈라지고, 그게 바로 이 규격이
    없애려는 결함이다(사용자 지적 *[발화 생략]* — 같은 삽화로 3회).
    `fix_figure_caption_tier.py`·`fix_figure_text_scale.py` 와 같은 이유로 도구로 만든다.

**어떻게 고치나 — 좌표를 옮기지 않는다.**
    viewBox 의 `min-y` 만 움직인다. 콘텐츠 좌표는 한 글자도 건드리지 않으므로
    ⑴ 도형끼리의 상대 위치 ⑵ 라벨 간격 ⑶ 화살촉 연결이 **정의상 그대로**다.
    높이(`height`)도 바뀌지 않는다 — 위·아래 여백의 합은 보존되고 배분만 바뀌기 때문이다:
        새 min-y = min-y + (위여백 − 아래여백) / 2
    배경 사각형(viewBox 를 통째로 덮는 rect)은 새 viewBox 를 따라 같이 옮긴다.
    안 옮기면 아래쪽에 배경이 없는 띠가 생긴다.

**총량을 줄이는 길은 `--margin=<px>` 이고, 그 확인은 2026-09-09 에 받았다.**
    사용자: *[발화 생략]* ·
    *[발화 생략]* · *[발화 생략]*.
    실측이 왜 부류인지를 보였다 — 기계공작법 ch10 아홉 장의 여백이 **5.7 에서 42.7 까지**
    제각각이었다. 손으로 맞추면 그 갈라짐이 그대로 남으므로 한 값으로 눌러야 한다.
    `--margin` 은 `min-y` 와 `height` 를 함께 옮겨 위·아래를 그 값으로 만든다.
    **줄이기만 한다** — 이미 그 값보다 좁은 삽화는 건드리지 않는다(넓히면 지적이 되돌아온다).

**무엇을 고치지 않나.**
    - `--margin` 없이 부르면 **배분만** 한다(옛 기본값 그대로).
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
    python tools/fix_figure_vertical_balance.py --subject=유체역학 --chapter=ch01 \\
        --margin=9 --apply        # 위·아래를 9px 로 눌러 준다(넓히지는 않는다)
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
# ★★ **따옴표가 항상 작은따옴표라는 전제는 틀렸다** (고친 날 2026-09-08).
#   이 줄에는 *[발화 생략]* 라고 적혀 있었는데, 계측공학
#   `ch07` 의 삽화 둘은 JSON 안에서 **이스케이프한 큰따옴표**(`viewBox=\"…\"`)를 쓴다.
#   그래서 감사는 그 둘을 신고하는데 처방은 조용히 건너뛰었다 — **자와 처방이 다른 것을
#   보는** 자리이고, 겉으로는 「고칠 수 없는 2건」처럼 보였다. 두 꼴을 다 받는다.
VIEWBOX_RE = re.compile(r"viewBox=(['\"]|\\\")(.*?)\1")


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


def _set_attr(rect_tag, name, value):
    """`<rect …>` 태그의 속성 하나를 바꾼다. 없으면 넣는다.

    따옴표는 **그 태그가 쓰던 꼴을 따른다** — 위 `VIEWBOX_RE` 주석의 그 이유다.
    """
    m = re.search(r"\b" + name + r"=(['\"]|\\\")[^'\"]*\1", rect_tag)
    if m:
        q = m.group(1)
        return (rect_tag[:m.start()] + name + "=" + q + _fmt(value) + q
                + rect_tag[m.end():])
    q = "\\\"" if "\\\"" in rect_tag else "'"
    return rect_tag.replace("<rect", "<rect " + name + "=" + q + _fmt(value) + q, 1)


def _set_y(rect_tag, new_y):
    return _set_attr(rect_tag, "y", new_y)


def plan_line(svg_line, margin=None):
    """svg 한 줄 → (새 줄, 옮긴 px, 설명). 순수 함수 — 테스트가 직접 부른다.

    옮긴 px 가 0이면 손대지 않은 것이다.
    `margin` 을 주면 위·아래 여백을 그 값으로 **줄인다**(넓히지는 않는다).
    """
    # ★★ **재는 것은 풀어 놓은 사본으로 한다** (2026-09-08). 이 파일은 JSON 의 **날 줄**을
    #   다루는데, 삽화에 따라 속성이 `attr='…'` 이 아니라 이스케이프한 `attr=\"…\"` 로
    #   적혀 있다(계측공학 ch07). 그러면 `_attr` 계열이 아무 속성도 못 읽어 `_content_extent`
    #   가 조용히 «잴 것이 없다» 를 내고, 감사는 신고하는데 처방만 건너뛴다.
    #   → 재기는 풀어 놓은 사본으로, **고치기는 날 줄에** 한다(따옴표 꼴을 보존해야 한다).
    probe = svg_line.replace('\\"', '"')
    vb = _viewbox(probe)
    if not vb or len(vb) != 4:
        return svg_line, 0.0, ""
    vx, vy, vw, vh = vb
    top, bottom = _content_extent(probe, vb)
    if top is None:
        return svg_line, 0.0, ""
    pad_top = top - vy
    pad_bottom = (vy + vh) - bottom
    if pad_top < 0 or pad_bottom < 0:
        return svg_line, 0.0, ("콘텐츠가 viewBox 밖 — 건너뜀 (위 " + format(pad_top, ".1f")
                               + " 아래 " + format(pad_bottom, ".1f") + ")")
    if margin is not None:
        # **줄이기만 한다** — 이미 좁은 쪽을 넓히면 그게 다음 지적이 된다
        if pad_top <= margin and pad_bottom <= margin:
            return svg_line, 0.0, ""
        new_vy = _round_half(top - min(pad_top, margin))
        new_vh = _round_half(bottom + min(pad_bottom, margin) - new_vy)
        shift = abs(vy - new_vy) + abs(vh - new_vh)
        target = ("위 " + format(pad_top, ".1f") + " / 아래 " + format(pad_bottom, ".1f")
                  + " → 양쪽 " + _fmt(float(margin))
                  + " (높이 " + _fmt(vh) + " → " + _fmt(new_vh) + ")")
    else:
        if abs(pad_bottom - pad_top) <= BALANCE_TOL_PX:
            return svg_line, 0.0, ""
        shift = _round_half((pad_top - pad_bottom) / 2.0)
        new_vy, new_vh = vy + shift, vh
        target = ("위 " + format(pad_top, ".1f") + " / 아래 " + format(pad_bottom, ".1f")
                  + " → 양쪽 " + format((pad_top + pad_bottom) / 2.0, ".1f"))
    if not shift:
        return svg_line, 0.0, ""

    # ★ 원래 쓰던 따옴표를 그대로 돌려준다 — 한 삽화 안에서 꼴이 갈리면 JSON 이 깨진다.
    out = VIEWBOX_RE.sub(
        lambda m: "viewBox=" + m.group(1)
        + " ".join(_fmt(v) for v in (vx, new_vy, vw, new_vh)) + m.group(1),
        svg_line, count=1)

    found = _covering_rect(out, vb)
    if found:
        m, _x, _y, _w, _h = found
        tag = _set_attr(m.group(0), "y", new_vy)
        tag = _set_attr(tag, "height", new_vh)
        out = out[:m.start()] + tag + out[m.end():]
        bg = ""
    else:
        bg = " · 배경 사각형 없음"
    note = (target + " (viewBox min-y " + _fmt(vy) + " → " + _fmt(new_vy) + ")" + bg)
    return out, shift, note


def main():
    apply = "--apply" in sys.argv
    margin = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--margin=")), None)
    margin = float(margin) if margin is not None else None
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
            new_line, shift, note = plan_line(line, margin)
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
