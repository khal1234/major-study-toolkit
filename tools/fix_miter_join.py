# -*- coding: utf-8 -*-
"""예각 꼭짓점의 **마이터 가시** 없애기 — 그 요소에 `stroke-linejoin='round'` 를 준다.

열린 날 2026-08-23. 사용자: *[발화 생략]* (3차원 유체 요소).

판정과 근거는 `buildlib/checks_svg.MITER_SPIKE_RATIO` 위 주석이 정본이다. 요지만:
SVG 기본 이음이 `miter` 라 끼인각이 예각인 꼭짓점에서 이음의 끝이 선폭의 몇 배까지 나간다.
`stroke-miterlimit`(기본 4) 아래의 각은 **깎이지도 않아** 바늘처럼 남는다.

    python tools/fix_miter_join.py                  # 미리보기
    python tools/fix_miter_join.py --apply          # 반영
    python tools/fix_miter_join.py --chapter=ch01.json --apply

**좌표를 건드리지 않는다** — 도형은 그대로 두고 이음만 둥글게 한다.
사람이 판정할 자리: *둥근 이음이 싫은 도형*(뾰족한 것이 뜻인 화살촉·쐐기)은 이 자가
안 본다 — 화살촉은 `stroke` 가 없거나 이미 `round` 라 애초에 걸리지 않는다. 그래도
«여기는 뾰족해야 한다» 는 도형이 걸리면 고치지 말고 그 삽화의 `lintWaivers` 로 사유와 함께 끌 것.
"""

import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_content  # noqa: E402
from buildlib.checks_content import (_figure_view_width, _iter_diagrams,  # noqa: E402
                                     slide_card_figures)
from buildlib.checks_svg import miter_spike_hits  # noqa: E402
from buildlib.jsontext import write_chapter  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_JOIN_ATTR = re.compile(r"\sstroke-linejoin\s*=\s*'[^']*'", re.I)


def rounded(whole):
    """그 요소 태그에 `stroke-linejoin='round'` 를 끼운 문자열. 순수 함수 — 테스트가 부른다.

    ★ 덧붙이지 않고 **갈아 끼운다**. `stroke-linejoin='miter'` 를 명시한 요소에 덧붙이면
      앞의 값을 먼저 읽는 파서(`_attr`)가 계속 miter 로 보고, 도구가 판마다 속성을 하나씩
      더 붙이며 안 끝난다 — `fix_arrow_seam` 이 2026-08-07 에 실제로 겪은 무한 루프다.
    """
    body = _JOIN_ATTR.sub("", whole)
    add = " stroke-linejoin='round'"
    if body.endswith("/>"):
        return body[:-2].rstrip() + add + "/>"
    return body[:-1].rstrip() + add + ">"


def figures_of(data):
    """이 챕터의 **고칠 수 있는** 삽화 dict 전부 — `diagrams` + 카드 슬라이드."""
    return list(_iter_diagrams(data)) + slide_card_figures(data)


def main():
    ap = argparse.ArgumentParser(description="예각 꼭짓점의 마이터 가시를 둥근 이음으로 없앤다")
    ap.add_argument("--chapter",
                    help="chNN.json 하나만 — 다른 과목이면 경로로 준다"
                         " (예: data/&lt;과목&gt;/ch02.json)")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    print("규격: 걸린 요소에 stroke-linejoin='round' (좌표는 그대로 둔다)")
    names = ([args.chapter] if args.chapter
             else [name + ".json" for name in audit_content.CHAPTERS])
    total = figs = stuck = 0
    for name in names:
        # ★ 경로로 줘도 받는다 — 이 자는 `audit_content.DATA` 한 과목만 보게 돼 있어서
        #   다른 과목의 `chNN.json` 을 주면 **파일을 못 찾고 조용히 «0개» 를 찍었다**
        #   (2026-09-08 실측: 열역학 ch02 를 주었는데 계측공학 폴더를 뒤졌다).
        #   화면이 「고칠 것이 없다」와 똑같아 보이는 것이 이 리포가 반복해 닫는 부류다.
        path = name if os.path.isfile(name) else os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            if args.chapter:                       # 이름을 대 놓고 못 찾은 것은 실패다
                sys.exit("그 챕터를 못 찾았다: " + name
                         + "\n  다른 과목이면 경로로 줄 것 — 예: data/&lt;과목&gt;/ch02.json")
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        # 표기 보존 기록기에 넘길 '고치기 전' 사본 — 통째 재작성은 안 건드린 줄까지 diff 로 띄운다.
        before = copy.deepcopy(data)
        changed = False
        for dg in figures_of(data):
            svg = str(dg.get("svg") or "")
            if not svg:
                continue
            view = _figure_view_width(svg)
            count = 0
            for _pass in range(6):          # 자를 다시 대어 남는 것이 없을 때까지 (상한은 종료 보장)
                hits = miter_spike_hits(svg, view)
                if not hits:
                    break
                moved = 0
                for whole, _theta, _px in hits:
                    if whole in svg:        # 앞 치환으로 이미 사라졌을 수 있다
                        svg = svg.replace(whole, rounded(whole), 1)
                        moved += 1
                if not moved:
                    break
                count += moved
            left = miter_spike_hits(svg, view)
            if left:
                # 남은 것을 **수가 아니라 태그로** 보고한다 — 수만 찍으면 원인을 못 좁힌다.
                stuck += len(left)
                print("  [수렴 실패] %s — 남은 %d개, 첫 태그:\n      %s"
                      % (dg.get("id", "?"), len(left), left[0][0][:220]))
            if not count:
                continue
            dg["svg"] = svg
            changed = True
            figs += 1
            total += count
            print("  %-38s 요소 %d개" % (dg.get("id", "?"), count))
        if changed and args.apply:
            state, why = write_chapter(path, before, data)
            print("  [%s] %s" % (state, why or name))
    print("\n삽화 %d개 · 요소 %d개%s"
          % (figs, total, "" if args.apply else "  (미리보기 — --apply 로 반영)"))
    if stuck:
        print("수렴 실패 %d개 — 위 태그를 사람이 볼 것" % stuck)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
