# -*- coding: utf-8 -*-
"""삽화 글자 크기를 화면 실효 규격(13~19px)으로 일괄 재조정한다.

    python tools/fix_figure_text_scale.py            # 미리보기(파일을 쓰지 않는다)
    python tools/fix_figure_text_scale.py --apply    # 실제 반영

**왜 손편집이 아니라 스크립트인가.**
2026-07-28 규격 신설(`checks_svg.figure_text_scale_issues`)로 5개 챕터 삽화 전체가 대상이 됐다.
글자를 하나씩 고치면 **한 삽화 안의 위계(라벨 vs 캡션)가 삽화마다 갈라진다** — 그건 이번 규격이
없애려는 결함 그 자체다. 그래서 **한 삽화의 모든 font-size에 같은 배율**을 곱해 상대 위계를 보존한다.

배율은 그 삽화 font-size의 **중앙값이 실효 16px(규격 13~19의 중앙)** 에 오도록 잡고,
0.5 단위로 반올림한 뒤 각 값을 규격 범위 안으로 clamp한다.
**이미 전부 규격 안인 삽화는 건드리지 않는다** — 불필요한 변경은 검수 부담이 된다.

주의: `<tspan font-size='78%'>` 같은 상대 지정은 대상이 아니다(정규식이 숫자만 받는다).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_svg import (  # noqa: E402
    FIGURE_RENDER_WIDTH, FIGURE_TEXT_MAX_PX, FIGURE_TEXT_MIN_PX, FIGURE_TEXT_BODY_PX,
    _is_caption_text, _svg_texts,
)

# ★ --floor 모드 (신설 2026-07-30). 위 기본 모드는 **규격 밖(13~19)** 인 것만 손댄다.
# 그래서 '규격 안이지만 본문보다 작은' 삽화는 영영 안 커졌다 — ch01 은 기본 모드로
# 0개가 나왔는데 사용자는 계속 *"글자가 작다"* 고 했다. 규격의 바닥이 낮았던 것이다.
# 이 모드는 **비-캡션 라벨의 최소 실효 크기**를 바닥(기본 15px = 본문)까지 끌어올린다.
# 캡션을 빼는 이유: 캡션은 라벨의 0.85배가 규격이라 같이 재면 바닥이 두 번 적용된다.

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.join(ROOT, "data")
TARGET_PX = (FIGURE_TEXT_MIN_PX + FIGURE_TEXT_MAX_PX) / 2.0
FONT_RE = re.compile(r"font-size='(\d+(?:\.\d+)?)'")
VIEWBOX_RE = re.compile(r"viewBox='([-\d.\s]+)'")
FIG_ID_RE = re.compile(r'"id":\s*"([^"]+)"')


def label_sizes(svg_line):
    """비-캡션(라벨·제목) 글자의 font-size 목록. 순수 함수 — 테스트가 부른다.

    ★ 2026-07-30 재작성: **검사기의 함수를 그대로 부른다**(`_svg_texts` + `_is_caption_text`).

    열린 날 2026-07-30 (ch02~05 이관 중). 이 함수는 원래 *"검사와 같은 규약"* 이라는 주석을
    달고 판정을 **다시 구현**하고 있었다. 다시 구현하면 반드시 갈라진다 — 실제로 두 군데서 갈렸다:
      ⑴ `<g font-size='11'>` 를 물려받는 `<text>` 를 **아예 못 봤다**(자기 attr 만 봤다).
         검사기는 `_inherited_font_size()` 로 상속을 따라간다 — 즉 **검사가 잡은 그 글자를
         수정 도구는 존재하지 않는 것으로 보고** 배율 계산에서 뺐다.
      ⑵ 원어 병기(`(boundary)`)를 검사기는 라벨의 하위 단으로 따로 처리하는데 여기는 몰랐다.
    결과: `fig-quality-mixture` 는 검사 13.1px · 도구 계산 14.2px 로 **다른 것을 재고 있었다.**
    고친 형태 = 규약을 공유하는 게 아니라 **함수를 공유**한다.
    """
    return [t["fs"] for t in _svg_texts(svg_line) if not _is_caption_text(t)]


def plan_line_floor(svg_line, floor=FIGURE_TEXT_BODY_PX):
    """라벨의 최소 실효 크기가 `floor` 에 닿도록 삽화 전체를 같은 배율로 키운다.

    **삽화 안의 상대 위계는 보존한다** — 한 값만 키우면 위계가 삽화마다 갈라지고,
    그건 이 규격이 없애려는 결함 그 자체다(기본 모드와 같은 이유).
    """
    vb = VIEWBOX_RE.search(svg_line)
    sizes = [float(m) for m in FONT_RE.findall(svg_line)]
    labels = label_sizes(svg_line)
    if not vb or not sizes or not labels:
        return svg_line, 0, ""
    parts = vb.group(1).split()
    if len(parts) != 4:
        return svg_line, 0, ""
    vw = float(parts[2])
    to_px = FIGURE_RENDER_WIDTH / vw
    min_label_px = min(labels) * to_px
    if min_label_px >= floor - 0.05:
        return svg_line, 0, ""                       # 이미 본문만 하다 — 건드리지 않는다
    # ★ 배율을 `floor / min` 으로 잡으면 각 값을 0.5 단위로 **반올림**할 때 최소 라벨이
    # 하한 밑으로 다시 내려간다(2026-07-30 실측: 8.55 → 8.5 → 실효 14.9px < 15).
    # 그래서 목표 font-size 를 먼저 **0.5 단위로 올림**해 두고 그 값에서 배율을 역산한다.
    # 이렇게 하면 최소 라벨은 반올림 뒤에도 정확히 목표값이 된다.
    need = floor / to_px                             # 하한을 만족하는 font-size (viewBox 단위)
    target = _ceil_half(need)                        # 0.5 단위 올림
    scale = target / min(labels)
    # 상한을 넘기지 않는 선까지만 키운다.
    max_px = max(sizes) * to_px
    if max_px * scale > FIGURE_TEXT_MAX_PX:
        scale = FIGURE_TEXT_MAX_PX / max_px
    if scale <= 1.0:
        # 균등 배율이 상한에 막혔다 — 아래쪽만 압축한다(`_lift_below_floor` 독스트링이 경위).
        out, lifted = _lift_below_floor(svg_line, to_px, floor)
        if not lifted:
            return svg_line, 0, ""
        return out, lifted, ("라벨 최소 실효 " + format(min_label_px, ".1f") + "px → "
                             + format(min(label_sizes(out)) * to_px, ".1f")
                             + "px · 균등 배율 불가(상한) → 바닥 올림 " + str(lifted) + "개")

    changed = [0]
    # ★ 0.5 단위 반올림이 상한을 도로 넘길 수 있다 (2026-07-30 실사고).
    # `fig-name-at-boundary`: 배율을 상한에 맞춰 1.0276 으로 깎았는데, 14.5 × 1.0276 = 14.90 이
    # **반올림으로 15.0** 이 되어 실효 19.1px — 빌드가 exit 1 로 막았다.
    # 배율만 클램프하고 **반올림 뒤 값을 안 보면** 상한 보장이 성립하지 않는다.
    cap = _floor_half(FIGURE_TEXT_MAX_PX / to_px)

    def repl(m):
        old = float(m.group(1))
        new = _round_half(old * scale)
        new = max(old, min(new, cap))   # 바닥 모드는 키우기만 한다 — 이미 상한 밖인 값은 그대로 둔다
        if abs(new - old) > 1e-9:
            changed[0] += 1
        return "font-size='" + _fmt(new) + "'"

    out = FONT_RE.sub(repl, svg_line)
    out, lifted = _lift_below_floor(out, to_px, floor)
    changed[0] += lifted
    note = ("라벨 최소 실효 " + format(min_label_px, ".1f") + "px → "
            + format(min(label_sizes(out)) * to_px, ".1f") + "px · 배율 " + format(scale, ".2f")
            + (" + 바닥 올림 " + str(lifted) + "개" if lifted else ""))
    return out, changed[0], note


def _lift_below_floor(svg_line, to_px, floor):
    """균등 배율로는 못 닿는 라벨을 **값 단위로** 바닥까지 끌어올린다. (신설 2026-07-30)

    왜 필요한가 — 균등 배율은 상한(19px)에 먼저 부딪힌다. 한 삽화의 글자 폭이
    `13.4 ~ 19px` 이면 비율이 1.42 인데 허용 밴드 `15.5 ~ 19` 는 1.23 밖에 안 된다.
    **밴드보다 넓은 위계는 균등 배율로 절대 밴드 안에 못 들어간다** — 실측: ch04 4개 삽화가
    이 이유로 도구에서 0개로 나왔고, 그래서 "도구를 돌렸는데 경고가 그대로"인 상태가 남았다.

    그래서 상한에 막히면 **아래쪽만 압축한다**: 바닥 미만인 font-size 값을 바닥값으로 올린다.
    - 위계 손실을 인정한다. 바닥 밑에 두 단이 있었으면 한 단으로 합쳐진다.
      그래도 이게 맞다 — 바닥의 뜻은 '이 정도면 봐준다'가 아니라 **'본문과 같은 크기'** 이고,
      본문보다 작은 라벨을 위계라는 이름으로 남겨 두는 것이 사용자가 4회 지적한 그 결함이다.
    - **캡션은 건드리지 않는다.** 캡션 규격은 라벨의 아래 단(하한 13px)이라 별개다.
      그래서 값 단위가 아니라 **글자 단위**로 고친다 — 라벨과 캡션이 같은 font-size 값을
      쓰고 있으면 값 단위 치환은 캡션까지 끌어올린다(2026-07-30 실사고:
      `fig-thermal-equilibrium-snapshots` 의 패널 캡션 3개가 그렇게 14 → 14.5 로 딸려 올라가
      패널 폭 174px 을 넘겼고 빌드가 F1 로 막았다). 캡션은 크기를 올릴 이유가 없다.
    - `<g font-size>` 를 물려받던 라벨은 자기 태그에 font-size 를 **명시로 박아** 분리한다.
    """
    texts = _svg_texts(svg_line)
    need = _ceil_half(floor / to_px)
    bad = [t for t in texts
           if not _is_caption_text(t) and t["fs"] * to_px < floor - 0.05 and need > t["fs"]]
    if not bad:
        return svg_line, 0
    out = svg_line
    for t in sorted(bad, key=lambda t: t["pos"], reverse=True):   # 뒤에서부터 — 인덱스 보존
        tag = out[t["pos"]:out.find(">", t["pos"]) + 1]
        if "font-size=" in tag:
            new_tag = re.sub(r"font-size='[\d.]+'", "font-size='" + _fmt(need) + "'", tag, count=1)
        else:
            new_tag = tag.replace("<text", "<text font-size='" + _fmt(need) + "'", 1)
        out = out[:t["pos"]] + new_tag + out[t["pos"] + len(tag):]
    return out, len(bad)


def _ceil_half(value):
    return -(-value * 2 // 1) / 2


def _floor_half(value):
    return (value * 2 // 1) / 2


def _round_half(value):
    return round(value * 2.0) / 2.0


def _fmt(value):
    return str(int(value)) if float(value).is_integer() else format(value, ".1f")


def plan_line(svg_line):
    """svg 한 줄을 받아 (새 줄, 바뀐 개수, 설명)을 돌려준다. 순수 함수 — 테스트가 부른다."""
    vb = VIEWBOX_RE.search(svg_line)
    sizes = [float(m) for m in FONT_RE.findall(svg_line)]
    if not vb or not sizes:
        return svg_line, 0, ""
    parts = vb.group(1).split()
    if len(parts) != 4:
        return svg_line, 0, ""
    vw = float(parts[2])
    lo = FIGURE_TEXT_MIN_PX * vw / FIGURE_RENDER_WIDTH
    hi = FIGURE_TEXT_MAX_PX * vw / FIGURE_RENDER_WIDTH
    if all(lo <= s <= hi for s in sizes):
        return svg_line, 0, ""                      # 이미 규격 안 — 건드리지 않는다

    ordered = sorted(sizes)
    median = ordered[len(ordered) // 2]
    scale = (TARGET_PX * vw / FIGURE_RENDER_WIDTH) / median

    changed = [0]

    def repl(m):
        old = float(m.group(1))
        new = min(hi, max(lo, _round_half(old * scale)))
        new = _round_half(new)
        if new < lo:                                # clamp 뒤 반올림이 다시 벗어나지 않게
            new = _round_half(lo + 0.5)
        if new > hi:
            new = _round_half(hi - 0.5)
        if abs(new - old) > 1e-9:
            changed[0] += 1
        return "font-size='" + _fmt(new) + "'"

    return FONT_RE.sub(repl, svg_line), changed[0], (
        "viewBox " + _fmt(vw) + " · 배율 " + format(scale, ".2f")
        + " · 규격 font-size " + format(lo, ".1f") + "~" + format(hi, ".1f"))


def subject_dirs(names, mine):
    """`data/` 아래에서 **내 과목** 폴더만 고른다. 순수 함수 — 테스트가 부른다.

    과목 이름은 접두어다(`SUBJECT_BY_BRANCH` 의 `공학수학` ↔ 폴더 `공학수학 1`) —
    `new_subject.inherited_subject_dirs` 와 같은 규약을 쓴다.

    ★ 열린 날 2026-07-28. 이 파일은 처음에 `DATA = data/열역학` 으로 **과목을 하드코딩**했다.
    공통 도구(`tools/`)인데 한 과목만 보므로, 다른 과목은 같은 규격 위반을 **손으로** 고치게 된다 —
    그게 바로 이 도구가 없애려던 '삽화마다 위계가 갈라지는' 결함이다.
    AGENTS 「공통 vs 과목별」이 경고하는 부류(공통에 과목별 사실을 박지 말 것)라 여기서 뒤집는다.
    """
    return [n for n in names if mine and n.startswith(mine)]


def _my_subject():
    sys.path.insert(0, os.path.join(ROOT, ".claude", "hooks"))
    # 표를 직접 조회하지 않는다 — `subject_of_branch()` 가 챕터 브랜치까지 포함한 정본이다.
    from guard_bash import subject_of_branch, _current_branch                 # noqa: E402
    return subject_of_branch(_current_branch(""))


def main():
    apply = "--apply" in sys.argv
    # --floor[=px]: 규격 안이지만 **본문보다 작은** 라벨을 끌어올린다(기본 15px = 본문).
    floor_arg = next((a for a in sys.argv if a == "--floor" or a.startswith("--floor=")), None)
    floor = None
    if floor_arg:
        floor = float(floor_arg.split("=", 1)[1]) if "=" in floor_arg else FIGURE_TEXT_BODY_PX
    # --chapter=chNN: 한 챕터만. 다른 챕터를 같이 고치면 그 챕터의 검수 하이라이트가 오염된다.
    only_ch = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    if only_ch:
        only_ch = only_ch.replace(".json", "")
    # --except=fig-a,fig-b: 그 삽화만 건너뛴다. 사용자가 **재설계를 보류한** 삽화에
    # 배율만 먼저 걸면 겹침이 더 심해지고, 보류 중인 판단(글자 크기)을 도구가 대신 내려 버린다.
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
    total_figs = total_texts = 0
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
            for back in range(i - 1, max(i - 6, -1), -1):
                m = FIG_ID_RE.search(lines[back])
                if m:
                    fig = m.group(1)
                    break
            if fig in skip:
                print("  " + name + " · " + fig + ": 건너뜀 (--except)")
                continue
            new_line, n, note = (plan_line_floor(line, floor) if floor is not None
                                 else plan_line(line))
            if not n:
                continue
            print("  " + name + " · " + fig + ": 글자 " + str(n) + "개 — " + note)
            lines[i] = new_line
            touched += 1
            total_figs += 1
            total_texts += n
        if touched and apply:
            open(path, "w", encoding="utf-8", newline="").write("\n".join(lines))
    print()
    print(("반영" if apply else "미리보기") + " — 삽화 " + str(total_figs)
          + "개 · 글자 " + str(total_texts) + "개")
    if not apply:
        print("실제로 쓰려면 --apply 를 붙일 것")
    return 0


if __name__ == "__main__":
    sys.exit(main())
