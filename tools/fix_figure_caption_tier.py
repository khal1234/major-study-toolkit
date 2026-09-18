# -*- coding: utf-8 -*-
"""설명 캡션을 라벨보다 한 단계 작게 내린다 — 삽화 안의 글자 위계 복구.

    python tools/fix_figure_caption_tier.py            # 미리보기(파일을 쓰지 않는다)
    python tools/fix_figure_caption_tier.py --apply    # 실제 반영

**왜 필요한가 (열린 날 2026-07-29).**
사용자 지적: *[발화 생략]*

절대 크기는 이미 규격이 있다 — `figure_text_scale_issues`가 화면 실효 13~19px을 강제한다.
**없던 것은 한 삽화 안의 위계다.** 그래서 제목·라벨·설명 문장이 전부 같은 크기로 나왔고,
독자는 무엇이 도형의 이름이고 무엇이 부연인지 크기로 구별할 수 없었다.
ch01 실측(2026-07-29): 51개 삽화 중 **28개**가 캡션 = 라벨 크기였다. 두 인스턴스가 아니라 부류다.

**왜 손편집이 아니라 스크립트인가.** `fix_figure_text_scale.py`와 같은 이유다 —
28개를 손으로 고치면 삽화마다 위계 비율이 갈라지고, 그게 이 규격이 없애려는 결함 그 자체다.

규칙:
    캡션 = 굵지 않고(제목은 font-weight 700) 한글 음절이 6자 이상인 텍스트.
           글자 수로만 재면 '0 K, -273.15°C' 같은 눈금 라벨이 캡션으로 잡힌다.
    라벨 = 그 외의 굵지 않은 텍스트.
    목표 = 캡션 font-size를 `라벨 최대 × 0.85`로 내리되, 화면 실효 13px 아래로는 안 내린다.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_svg import (  # noqa: E402
    FIGURE_RENDER_WIDTH, FIGURE_TEXT_MIN_PX, _svg_texts,
)
from audit_figure_balance import CAPTION_HANGUL_MIN, _hangul_count  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.join(ROOT, "data")
CAPTION_RATIO = 0.85
VIEWBOX_RE = re.compile(r"viewBox='([-\d.\s]+)'")
FIG_ID_RE = re.compile(r'"id":\s*"([^"]+)"')


def _round_half(value):
    return round(value * 2.0) / 2.0


def _fmt(value):
    return str(int(value)) if float(value).is_integer() else format(value, ".1f")


def _tag_of(line, pos):
    """`pos`에서 시작하는 <text ...> 여는 태그 (끝의 '>' 포함)."""
    return line[pos:line.find(">", pos) + 1]


def plan_line(svg_line):
    """svg 한 줄을 받아 (새 줄, 바꾼 캡션 수, 설명)을 돌려준다. 순수 함수 — 테스트가 부른다."""
    vb = VIEWBOX_RE.search(svg_line)
    if not vb:
        return svg_line, 0, ""
    parts = vb.group(1).split()
    if len(parts) != 4:
        return svg_line, 0, ""
    vw = float(parts[2])

    texts = _svg_texts(svg_line)
    for t in texts:
        tag = _tag_of(svg_line, t["pos"])
        t["bold"] = "font-weight='700'" in tag or 'font-weight="700"' in tag
        t["caption"] = (not t["bold"]) and _hangul_count(t["s"]) >= CAPTION_HANGUL_MIN

    captions = [t for t in texts if t["caption"]]
    labels = [t for t in texts if not t["caption"] and not t["bold"]]
    if not captions or not labels:
        return svg_line, 0, ""
    label_max = max(t["fs"] for t in labels)
    # ★ 게이트는 일부러 규격(0.85배)보다 **느슨하다** — 건드리지 말 것 (판정 2026-07-30).
    # AGENTS 「글자 크기 위계」는 *[발화 생략]* 인데 여기 게이트는
    # `캡션 >= 라벨 최대` 다. 둘을 맞추려고 0.85 로 조여 봤더니 **전 챕터 34삽화·캡션 52개**가
    # 대상이 됐고 ch01 이 12삽화 포함됐다. 그런데 ch01 캡션에 대한 **가장 최근 사용자 지적은
    # 반대 방향**이다 — 2026-07-30 *[발화 생략]*(인박스 V-3). 그 지적의
    # 원인이 바로 2026-07-29 의 0.85 일괄 축소였다. 게이트를 조이면 그 과교정을 되풀이한다.
    # 즉 여기서 갈리는 것은 버그가 아니라 **두 지적 사이에서 고른 위치**다.
    # 바꾸려면 사용자 판단을 먼저 받을 것(캡션 크기는 취향이 아니라 반복 지적 이력이 있는 자리다).
    if not any(t["fs"] >= label_max for t in captions):
        return svg_line, 0, ""

    floor = FIGURE_TEXT_MIN_PX * vw / FIGURE_RENDER_WIDTH
    target = _round_half(label_max * CAPTION_RATIO)
    if target >= label_max:                     # 반올림이 라벨과 같아지면 한 눈금 더 내린다
        target = _round_half(label_max - 0.5)
    if target < floor:                          # 실효 13px 아래로는 안 내린다
        target = _round_half(floor + 0.4)
    if target >= label_max:                     # 내릴 여지가 없는 삽화는 건드리지 않는다
        return svg_line, 0, ""

    # ★ 기준을 넘은 캡션만이 아니라 **그 삽화의 캡션 전부**를 target 으로 맞춘다
    #   (열린 날 2026-07-30, thermo-ch04 세션 보고).
    #   옛 조건은 `fs >= label_max` 인 것만 내렸는데, 캡션이 둘이고 크기가 다르면
    #   큰 쪽만 내려가 **둘의 순서가 뒤집힌다** — 실측: `fig-joule-free-expansion` 에서
    #   결론(14)이 설명(15.5)보다 작아졌다. 캡션은 위계상 **한 단계**이므로 한 삽화 안에서
    #   크기가 갈리는 것 자체가 이 규격이 없애려는 결함이다. ch04는 데이터에서 손으로
    #   맞췄지만 그건 인스턴스 수정이라 다음 챕터에서 그대로 재발한다.
    bad = [t for t in captions if abs(t["fs"] - target) > 1e-6]
    if not bad:
        return svg_line, 0, ""

    out = svg_line
    # 뒤에서부터 고쳐야 앞쪽 인덱스가 밀리지 않는다.
    for t in sorted(bad, key=lambda t: t["pos"], reverse=True):
        tag = _tag_of(out, t["pos"])
        if "font-size=" in tag:
            new_tag = re.sub(r"font-size='[\d.]+'", "font-size='" + _fmt(target) + "'", tag, count=1)
        else:                                   # <g font-size>에서 물려받던 글자 — 명시로 고정한다
            new_tag = tag.replace("<text", "<text font-size='" + _fmt(target) + "'", 1)
        out = out[:t["pos"]] + new_tag + out[t["pos"] + len(tag):]

    return out, len(bad), (
        "라벨 " + _fmt(label_max) + " → 캡션 " + _fmt(target)
        + " (실효 " + format(target * FIGURE_RENDER_WIDTH / vw, ".1f") + "px)")


def main():
    apply = "--apply" in sys.argv
    sys.path.insert(0, os.path.join(ROOT, ".claude", "hooks"))
    # ★ `SUBJECT_BY_BRANCH.get(branch)` 를 직접 부르지 말 것 — `subject_of_branch()` 가 정본이다.
    #   표를 직접 조회하면 `claude/thermo-ch02-…` 같은 실제 워크트리 브랜치를 못 알아본다
    #   (2026-07-29 ch02 세션 실사고: 이 도구가 '과목=None' 으로 거부했다).
    from guard_bash import subject_of_branch, _current_branch                 # noqa: E402
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--subject=")), None)
    mine = arg or subject_of_branch(_current_branch(""))
    names = sorted(n for n in os.listdir(DATA_ROOT)
                   if os.path.isdir(os.path.join(DATA_ROOT, n)))
    dirs = [n for n in names if mine and n.startswith(mine)]
    if not dirs:
        print("거부 — 이 브랜치의 과목 폴더를 찾지 못했다(과목=" + str(mine) + ").")
        return 2
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    data_dir = os.path.join(DATA_ROOT, dirs[0])
    print("[대상] data/" + dirs[0] + (" · " + only if only else ""))
    total_figs = total_caps = 0
    for name in sorted(os.listdir(data_dir)):
        if not re.fullmatch(r"ch\d+\.json", name):
            continue
        if only and name != only:
            continue
        path = os.path.join(data_dir, name)
        lines = open(path, encoding="utf-8").read().split("\n")
        touched = 0
        for i, line in enumerate(lines):
            if '"svg":' not in line:
                continue
            new_line, n, note = plan_line(line)
            if not n:
                continue
            fig = "?"
            for back in range(i - 1, max(i - 8, -1), -1):
                m = FIG_ID_RE.search(lines[back])
                if m:
                    fig = m.group(1)
                    break
            print("  " + name + " · " + fig + ": 캡션 " + str(n) + "개 — " + note)
            lines[i] = new_line
            touched += 1
            total_figs += 1
            total_caps += n
        if touched and apply:
            open(path, "w", encoding="utf-8", newline="").write("\n".join(lines))
    print()
    print(("반영" if apply else "미리보기") + " — 삽화 " + str(total_figs)
          + "개 · 캡션 " + str(total_caps) + "개")
    if not apply:
        print("실제로 쓰려면 --apply 를 붙일 것")
    return 0


if __name__ == "__main__":
    sys.exit(main())
