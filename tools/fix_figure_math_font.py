# -*- coding: utf-8 -*-
"""**낱개 라벨에 잘못 선언된 산문 수식 글꼴을 지운다** — C20 '한 삽화 안에서 글꼴이 갈렸다'.

    python tools/fix_figure_math_font.py                          # 미리보기(파일을 쓰지 않는다)
    python tools/fix_figure_math_font.py --chapter=ch01.json --only=fig-01-p01 --apply
    python tools/fix_figure_math_font.py --chapter=ch01.json --apply

**★ 방향이 2026-08-05 에 뒤집혔다 (부류31).** 이 도구는 2026-08-02 에 *관계 기호가 든 라벨을
등폭으로 올리는* 도구로 태어났는데, 그 자가 너무 넓어 **같은 막대의 이름표를 두 글꼴로 갈라
놓았다**(사용자: *[발화 생략]*). 등폭은 **조판 단위**(분수·한 줄
수식)의 글꼴이지 이름표의 글꼴이 아니다. 그래서 지금은 **반대로 지운다** — 조판 그룹
(`<g class='frac'>`) 밖의 라벨에서 등폭 선언을 빼 삽화 자신의 글꼴로 되돌린다.

**왜 손편집이 아니라 스크립트인가.** 열역학 ch01 만 삽화 25개에 박혀 있다. 손으로 지우면
어떤 라벨은 지워지고 어떤 라벨은 남아, 이 규격이 없애려는 '한 삽화 안 갈라짐'을 그대로 되풀이한다.

**판정은 이 파일에 없다** — `buildlib.checks_svg.figure_math_font_targets` 가 정본이고
C20 검사도 같은 함수를 쓴다. 자를 둘로 두면 갈라진다.

★ 새 교정 도구는 **삽화 하나에 먼저 적용해 렌더로 확인한 뒤** 넓힐 것 (`--only=`).
  `fix_arrow_scale.py` 를 ch01~ch05 에 한 번에 돌렸다가 짧은 꼬리를 길이 0 으로 지운
  사고가 2026-08-02 에 있었다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_svg import MATH_FONT, figure_math_font_targets  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.join(ROOT, "data")
FIG_ID_RE = re.compile(r'"id":\s*"([^"]+)"')


MATH_FONT_ATTR_RE = re.compile(r"\sfont-family='" + re.escape(MATH_FONT) + r"'")


def plan_line(svg_line):
    """svg 한 줄을 받아 (새 줄, 바꾼 라벨 목록). 순수 함수 — 테스트가 부른다."""
    targets = figure_math_font_targets(svg_line)
    if not targets:
        return svg_line, []
    out, changed = svg_line, []
    # 뒤에서부터 고쳐야 앞쪽 인덱스가 밀리지 않는다.
    for start, end, inner in sorted(targets, key=lambda t: t[0], reverse=True):
        tag = out[start:end]
        # **지우기만 한다.** 등폭이 아닌 다른 글꼴을 만나면 그건 저자가 고른 것이므로 손대지
        # 않는다 — 판정(`figure_math_font_targets`)이 등폭만 넘기므로 여기 오는 건 등폭뿐이다.
        new_tag = MATH_FONT_ATTR_RE.sub("", tag, count=1)
        if new_tag == tag:
            continue
        out = out[:start] + new_tag + out[end:]
        changed.append(inner.strip())
    return out, list(reversed(changed))


def main():
    apply = "--apply" in sys.argv
    sys.path.insert(0, os.path.join(ROOT, ".claude", "hooks"))
    # `subject_of_branch()` 가 정본이다 — 표를 직접 조회하면 챕터 워크트리 브랜치를 못 알아본다.
    from guard_bash import subject_of_branch, _current_branch                 # noqa: E402
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--subject=")), None)
    mine = arg or subject_of_branch(_current_branch(""))
    names = sorted(n for n in os.listdir(DATA_ROOT)
                   if os.path.isdir(os.path.join(DATA_ROOT, n)))
    dirs = [n for n in names if mine and n.startswith(mine)]
    if not dirs:
        print("거부 — 이 브랜치의 과목 폴더를 찾지 못했다(과목=" + str(mine) + ").")
        return 2
    only_ch = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    only_fig = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), None)
    data_dir = os.path.join(DATA_ROOT, dirs[0])
    print("[대상] data/" + dirs[0] + (" · " + only_ch if only_ch else "")
          + (" · " + only_fig if only_fig else ""))
    total_figs = total_labels = 0
    for name in sorted(os.listdir(data_dir)):
        if not re.fullmatch(r"ch\d+\.json", name):
            continue
        if only_ch and name != only_ch:
            continue
        path = os.path.join(data_dir, name)
        lines = open(path, encoding="utf-8").read().split("\n")
        touched = 0
        for i, line in enumerate(lines):
            if '"svg":' not in line:
                continue
            fig = "?"
            for back in range(i - 1, max(i - 30, -1), -1):
                m = FIG_ID_RE.search(lines[back])
                if m:
                    fig = m.group(1)
                    break
            if only_fig and fig != only_fig:
                continue
            new_line, changed = plan_line(line)
            if not changed:
                continue
            print("  " + name + " · " + fig + ": " + str(len(changed)) + "개 — "
                  + " / ".join(c[:28] for c in changed[:6])
                  + (" …" if len(changed) > 6 else ""))
            lines[i] = new_line
            touched += 1
            total_figs += 1
            total_labels += len(changed)
        if touched and apply:
            open(path, "w", encoding="utf-8", newline="").write("\n".join(lines))
    print()
    print(("반영" if apply else "미리보기") + " — 삽화 " + str(total_figs)
          + "개 · 라벨 " + str(total_labels) + "개")
    if not apply:
        print("실제로 쓰려면 --apply 를 붙일 것")
    return 0


if __name__ == "__main__":
    sys.exit(main())
