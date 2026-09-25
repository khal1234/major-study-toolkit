#!/usr/bin/env python
"""축 이름을 화살촉에서 규격 거리(0.5em)로 옮긴다 — 빌드 자 `axis_name_gap_issues` 의 처방.

    python tools/fix_axis_name_gap.py --all                 # 전 과목, 무엇이 옮겨질지만 본다
    python tools/fix_axis_name_gap.py --all --apply         # 실제로 고친다
    python tools/fix_axis_name_gap.py data/<과목>/chNN.json [--apply]
    python tools/fix_axis_name_gap.py --all --fig=<그림 id,…> --em=0.72 --apply  # F1 과 부딪는 그림만 그 값

**왜 열렸나 (2026-09-24, 클라우드 큐 29).** `c17e41ed` 가 축 이름–화살촉 거리 규격을 1.0em → 0.5em
(허용 ±0.25em)으로 내렸는데(설계도 4절 사용자 판정 *[발화 생략]*), 옛 규격 1.0em 으로 그려 둔 다른
과목 삽화가 전부 빌드 error 로 넘어가 전체 빌드가 막혔다. 규칙을 바꾼 자리에서 **소급 처방**이
없었던 것이다(규칙 7 ⑵). 이 도구가 그 처방이고, 이미 쓴 콘텐츠는 빌드 자가 계속 잰다(⑶ 은
빌드 검사가 대신한다 — `audit_convention_drift` 에 따로 올리지 않는다).

**무엇을 하나.** 빌드 자와 **같은 측정**(`checks_svg._axis_name_gaps` — 이름 글자의 x·y 기준점에서
가장 가까운 채운 삼각형의 꼭짓점까지)을 쓰고, 규격 밖인 이름만 **꼭짓점 → 이름 방향을 그대로 둔 채**
거리만 0.5em 으로 맞춘다. 방향을 바꾸지 않으므로 이름이 축의 어느 쪽에 있었는지(위·오른쪽)는
그대로다. 화살표가 아예 없는 이름(3.5em 밖)은 다른 자의 몫이라 건드리지 않는다.

**데이터를 다시 직렬화하지 않는다.** 장 파일을 글자 그대로 읽어 해당 `<text …>` 태그의 `x`·`y`
값만 바꾼다 — JSON 직렬화기로 통째 되쓰면 파일 전체가 다시 포맷돼 diff 가 쓸모없어진다.
(그래서 `write_chapter` 계약 검사의 대상도 아니다 — 객체를 다시 쓰지 않는다.)

**못 보는 것.** 옮긴 뒤 글자가 다른 선·글자와 겹치는지는 이 도구가 안 잰다 — `--apply` 뒤
`lint_chapter`·빌드가 잰다(F1·F4 등). 렌더 육안은 로컬 [사람].
"""
import contextlib
import glob
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from buildlib.checks_svg import (AXIS_ARROW_MAX_EM, AXIS_NAME_GAP_EM,  # noqa: E402
                                 AXIS_NAME_GAP_TOL_EM, _attr, _axis_name_gaps)
from audit_figure_balance import _content_extent, _viewbox             # noqa: E402
from fix_figure_vertical_balance import plan_line                      # noqa: E402
from buildlib.checks_content import lint_chapter                       # noqa: E402

_TEXT_TAG = re.compile(r"<text([^>]*)>")


def _fmt(v):
    """좌표 표기 — 소수 한 자리, 정수면 소수점 없이(기존 데이터의 표기와 같다)."""
    v = round(v, 1)
    return str(int(v)) if v == int(v) else "%.1f" % v


def _set_attr(attrs, name, value):
    """태그 속성 문자열에서 `name='…'`(또는 큰따옴표)의 값만 갈아끼운다."""
    prefix = r"((?<![A-Za-z0-9:_-])" + re.escape(name) + r"=)(['\"])[^'\"]*\2"
    return re.sub(prefix, lambda m: m.group(1) + m.group(2) + value + m.group(2), attrs, count=1)


def fix_svg(svg, target_em=AXIS_NAME_GAP_EM, force=False):
    """(고친 svg, [(옛 x, 옛 y, 새 x, 새 y, 옛 em, 새 em)]) — 순수 함수, 테스트가 부른다.

    `target_em`·`force` 는 F1(글–선 0.5em 하한)과 부딪는 그림을 위한 것이다: 가로축 이름이
    화살촉 옆으로 0.5em 까지 당겨지면 글자 상자가 축선 끝에 0.5em 안으로 붙는다. 그때는
    허용 안(≤ 0.75em)의 큰 값으로 **두 축을 함께** 다시 놓는다(규격 「두 축 모두 같은 값」).
    `force` 는 이미 허용 안에 든 이름도 그 값으로 옮긴다.
    """
    gaps = _axis_name_gaps(svg)
    targets = {}
    for x, y, fs, near, apex in gaps:
        if near is None or near > AXIS_ARROW_MAX_EM * fs or not fs:
            continue
        em = near / fs
        if near == 0 or (not force and abs(em - AXIS_NAME_GAP_EM) <= AXIS_NAME_GAP_TOL_EM):
            continue
        scale = target_em * fs / near
        nx = apex[0] + (x - apex[0]) * scale
        ny = apex[1] + (y - apex[1]) * scale
        targets[(x, y)] = (nx, ny, em)
    if not targets:
        return svg, []
    changes = []

    def repl(m):
        attrs = m.group(1)
        if "axis-name" not in (_attr(attrs, "class") or ""):
            return m.group(0)
        try:
            key = (float(_attr(attrs, "x", "0")), float(_attr(attrs, "y", "0")))
        except (TypeError, ValueError):
            return m.group(0)
        if key not in targets:
            return m.group(0)
        nx, ny, em = targets.pop(key)
        changes.append((key[0], key[1], round(nx, 1), round(ny, 1), em, target_em))
        attrs = _set_attr(_set_attr(attrs, "x", _fmt(nx)), "y", _fmt(ny))
        return "<text" + attrs + ">"

    return _TEXT_TAG.sub(repl, svg), changes


def _pads(svg):
    """(위 여백, 아래 여백) — 세로 균형 감사와 **같은 함수**로 잰다. 못 재면 None."""
    probe = svg.replace('\\"', '"')
    vb = _viewbox(probe)
    if not vb or len(vb) != 4:
        return None
    top, bottom = _content_extent(probe, vb)
    if top is None:
        return None
    return top - vb[1], (vb[1] + vb[3]) - bottom


def keep_vertical_margins(before, after):
    """이름을 옮겨 콘텐츠 위·아래 끝이 움직였으면 viewBox 를 옛 여백으로 되돌린다. 순수 함수.

    ★ 2026-09-24 첫 적용 실측: 세로축 맨 위의 이름을 화살촉 쪽으로 내리면 콘텐츠 윗끝이 내려가
      위 여백만 커진다 — 열역학 ch03·04·06·07·08 · 응용열 ch10 · 공수1 ch05 가 세로 균형·여백
      규칙에 새로 걸려 커밋 게이트가 막았다. 옮긴 만큼 viewBox 를 줄이는 것이 같은 처방의 뒷절반이다.
      계산은 `fix_figure_vertical_balance.plan_line`(margin 모드 — 줄이기만)을 그대로 쓴다.
    """
    old = _pads(before)
    if old is None:
        return after
    fixed, _shift, _note = plan_line(after, margin=max(old))
    return fixed


# 옮길 거리의 사다리 — 규격값(0.5em)부터 허용 상한 안쪽까지 세 칸. F1(글–선 0.5em 하한)이나
# 가장자리 여유에 걸리면 한 칸씩 멀리 둔다. 0.72 는 허용 상한 0.75em 에서 좌표 반올림 여유 0.03 을
# 뺀 값, 0.6 은 그 사이의 중간 칸이다(2026-09-24 응용열 ch10 — 0.5 는 F1, 0.72 는 가장자리에 걸렸다).
LADDER_EM = (AXIS_NAME_GAP_EM, 0.6, 0.72)
_FAIL = re.compile(r"\[FAIL\] (fig-[^\s:\[]+)(.*)$")
_QUOTED = re.compile(r"'([^']*)'\s*(?:\(|·|$)")


def lint_fails(raw, path):
    """빌드와 **같은 lint**(`checks_content.lint_chapter`)를 돌려 {그림 id: {신고 줄}} 을 낸다.

    ★ 2026-09-24 실사고: 첫 적용 뒤 커밋 게이트(규칙 등록부)는 통과했지만 F1 은 안 봐서, 슬라이드
      단계 프레임까지 F1 이 40여 건 새로 났다(열역학 ch03·04·06·07·08 · 응용열 ch10 · 전전 ch07).
      빌드 출력이 잘려 그 자리에서 못 봤다. → 처방이 **스스로** 빌드 lint 로 재고 거리를 고른다.
    """
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            lint_chapter(json.loads(raw), path)
    except ValueError:
        pass
    out = {}
    for line in buf.getvalue().splitlines():
        m = _FAIL.search(line)
        if m:
            out.setdefault(m.group(1), set()).add(m.group(2).strip())
    return out


def _axis_texts(svg):
    return {re.sub(r"<[^>]+>", "", t).strip()
            for t in re.findall(r"<text[^>]*axis-name[^>]*>(.*?)</text>", svg, re.S)}


def _about_axis(line, names):
    """신고 줄이 축 이름 글자에 관한 것인가 — 축 자 신고이거나, 인용한 글자가 축 이름이다."""
    if "[축]" in line:
        return True
    return any(any(n.startswith(q) or q.startswith(n) for n in names) for q in _QUOTED.findall(line) if q)


def _bad(fig, svg, fails, base):
    """옮긴 뒤 이 그림이 받아들일 수 없는가 — 새로 생긴 신고가 있거나, 축 이름에 걸린 신고가 남았다."""
    names = _axis_texts(svg)
    return any(line not in base.get(fig, ()) or _about_axis(line, names)
               for line in fails.get(fig, ()))


def _hits_axis(fig, svg, fails):
    """옮기기 전부터 이 그림의 축 이름이 신고에 걸려 있나(허용 안이어도 다시 놓을 대상)."""
    names = _axis_texts(svg)
    return any(_about_axis(line, names) for line in fails.get(fig, ()))


def fix_file(path, apply, target_em=AXIS_NAME_GAP_EM, only_figs=None, lint=lint_fails):
    """장 파일 한 벌 — 글자 그대로 읽어 svg 조각마다 고친다. 반환 ([(fig id, 변경)], [되돌린 fig id]).

    그림마다 사다리(`LADDER_EM`)를 한 칸씩 오른다: 옮긴 뒤 빌드 lint 에서 그 그림에 새 신고가
    생기거나 축 이름이 걸리면 다음 칸으로, 칸이 다하면 **그 그림은 원래대로 두고** 사람 몫으로 보고한다.
    `only_figs` 에 든 그림은 사다리 대신 `target_em` 한 칸이다(허용 안에 든 이름도 옮긴다).
    한 번의 `--apply` 로 끝나야 트리가 깨끗한 채로 커밋된다.
    """
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    spans = []
    for m in re.finditer(r"<svg\b.*?</svg>", raw, re.S):
        ids = re.findall(r'"id":\s*"(fig-[^"]+)"', raw[:m.start()])
        spans.append((m.start(), m.end(), ids[-1] if ids else "?", m.group(0)))
    base_fails = lint(raw, path) if apply else {}
    step = {}                                   # svg 순번 → 사다리 칸(없으면 손대지 않음)
    for i, (_s, _e, fig, svg) in enumerate(spans):
        if only_figs is not None and fig in only_figs:
            step[i] = 0
        elif fix_svg(svg)[1] or _hits_axis(fig, svg, base_fails):
            step[i] = 0
    ladder = lambda i: ((target_em,) if only_figs is not None and spans[i][2] in only_figs
                        else LADDER_EM)
    reverted = []
    while True:
        out, pos, report, placed = [], 0, [], {}
        for i, (s, e, fig, svg) in enumerate(spans):
            fixed, changes = svg, []
            if i in step:
                em = ladder(i)[step[i]]
                force = em != AXIS_NAME_GAP_EM or (only_figs is not None and fig in only_figs) \
                    or _hits_axis(fig, svg, base_fails)
                fixed, changes = fix_svg(svg, em, force=force)
                if changes:
                    fixed = keep_vertical_margins(svg, fixed)
                    placed[i] = fixed
                    report.append((fig, changes))
            out.append(raw[pos:s])
            out.append(fixed)
            pos = e
        out.append(raw[pos:])
        new = "".join(out)
        if not apply or not placed:
            break
        fails = lint(new, path)
        bumped = False
        for i, fixed in placed.items():
            if _bad(spans[i][2], fixed, fails, base_fails):
                if step[i] + 1 < len(ladder(i)):
                    step[i] += 1
                else:
                    del step[i]
                    reverted.append(spans[i][2])
                bumped = True
        if not bumped:
            break
    if apply and new != raw:
        json.loads(new)          # 고친 결과가 여전히 JSON 인지 — 깨지면 쓰지 않는다
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(new)
    return report, reverted


def main(argv):
    apply = "--apply" in argv
    opts = dict(a[2:].split("=", 1) for a in argv[1:] if a.startswith("--") and "=" in a)
    only = set(opts["fig"].split(",")) if "fig" in opts else None
    target = float(opts.get("em", AXIS_NAME_GAP_EM))
    if abs(target - AXIS_NAME_GAP_EM) > AXIS_NAME_GAP_TOL_EM:
        sys.exit("--em=%s 은 규격 허용(0.5 ± 0.25em) 밖이다 — 빌드 자가 다시 막는다" % target)
    paths = [a for a in argv[1:] if not a.startswith("--")]
    if "--all" in argv:
        paths = sorted(glob.glob(os.path.join(ROOT, "data", "*", "ch*.json")))
    if not paths:
        print(__doc__)
        return 2
    total = files = 0
    left = []
    for path in paths:
        report, reverted = fix_file(path, apply, target, only)
        left += [os.path.relpath(path, ROOT) + " " + f for f in reverted]
        if not report:
            continue
        files += 1
        print(os.path.relpath(path, ROOT))
        for fig, changes in report:
            for ox, oy, nx, ny, em, to_em in changes:
                total += 1
                print("  %s  (%s,%s) → (%s,%s)  %.2fem → %.2fem"
                      % (fig, _fmt(ox), _fmt(oy), _fmt(nx), _fmt(ny), em, to_em))
    print("합계 %d건 · 장 %d개 · 훑은 장 %d%s" % (total, files, len(paths),
                                            "" if apply else " (보기만 — F1 사다리는 --apply 때만 돈다)"))
    if left:
        print("사다리를 다 올라도 F1 에 걸려 원래대로 둔 그림 %d개 — 사람이 자리를 정한다:" % len(left))
        for item in left:
            print("  " + item)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
