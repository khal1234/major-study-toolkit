"""화살촉 접합부의 흰 이음매 없애기 — 자기 색 테두리를 두른다.

열린 날 2026-08-07. 사용자: *[발화 생략]* → 어느 삽화냐고 묻자 ***"이건 뭔 삽화든 다 동일해."***

판정과 근거는 `buildlib/checks_svg.arrowhead_seam_issues` 위 주석이 정본이다. 요지만:
축선 끝과 화살촉 밑변이 **같은 좌표**라(AGENTS 삽화 표준이 그렇게 정했다) 맞닿은 두 도형이
따로 안티에일리어싱되어 경계에 배경이 비친다. 좌표를 옮기지 않고 **겹치게** 만들어 없앤다.

    python tools/fix_arrow_seam.py                  # 미리보기
    python tools/fix_arrow_seam.py --apply          # 반영
    python tools/fix_arrow_seam.py --chapter=ch01.json --apply
"""

import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_content  # noqa: E402
from buildlib.checks_content import iter_chapter_diagrams  # noqa: E402
from buildlib.checks_svg import ARROW_SEAM_STROKE, arrowhead_seam_hits  # noqa: E402
from buildlib.jsontext import write_chapter  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 이미 붙어 있는 stroke 계열 속성. 판정기가 **진짜 테두리가 있는 화살촉은 걸러 내므로**
# 여기 걸리는 것은 `stroke='none'` 이거나 이 도구가 앞서 붙인 것뿐이다.
_STROKE_ATTRS = re.compile(r"\sstroke(?:-width|-linejoin)?\s*=\s*'[^']*'", re.I)


def seamed(whole, fill):
    """화살촉 태그에 자기 색 테두리를 끼운 문자열. 순수 함수 — 테스트가 직접 부른다.

    ★ **덧붙이지 않고 갈아 끼운다** (실측 2026-08-07). 처음에는 태그 끝에 속성을 덧붙였는데,
      `stroke='none'` 을 이미 가진 화살촉에서 `_attr` 이 **앞에 있는 'none' 을 먼저 읽어**
      계속 '테두리 없음' 으로 판정했다. 그래서 도구가 매 판 속성을 하나씩 더 붙이며
      **끝나지 않았다**(무한 루프. `fig-d-fluid-element`·`fig-q16-hydraulic-lift` 등 8개).
      수를 세는 것으로는 원인을 못 좁혔고, **남은 태그를 그대로 찍고 나서야** 보였다.
    """
    body = _STROKE_ATTRS.sub("", whole)
    add = " stroke='%s' stroke-width='%g' stroke-linejoin='round'" % (fill, ARROW_SEAM_STROKE)
    # 자기 닫음(`/>`)과 여는 태그(`>`) 둘 다 있다. 끝의 `/` 앞에 끼워 넣는다.
    if body.endswith("/>"):
        return body[:-2].rstrip() + add + "/>"
    return body[:-1].rstrip() + add + ">"


def main():
    ap = argparse.ArgumentParser(description="화살촉에 자기 색 테두리를 둘러 이음매를 없앤다")
    ap.add_argument("--chapter", help="chNN.json 하나만")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    print("규격: 화살촉에 stroke=<fill> · stroke-width=%g · stroke-linejoin='round'"
          % ARROW_SEAM_STROKE)
    print("(좌표는 건드리지 않는다 — '선 끝 = 밑변 중앙' 규격은 그대로 산다)")
    names = ([args.chapter] if args.chapter
             else [name + ".json" for name in audit_content.CHAPTERS])
    total = figs = stuck = 0
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        # 표기 보존 기록기에 넘길 '고치기 전' 사본 — 원본의 들여쓰기·줄바꿈을 건드리지 않는다.
        # 통째 재작성은 손대지 않은 줄까지 diff 로 띄워 검수를 망친다(실측: 이 도구의 첫 판이
        # 그렇게 써서 삽화 117줄 말고 **6줄이 더** 움직였다. 기록기로 바꾸니 117/117 이 됐다).
        before = copy.deepcopy(data)
        changed = False
        for fig_id, dg in iter_chapter_diagrams(data):
            svg = str(dg.get("svg") or "")
            if not svg:
                continue
            # ★ 자를 다시 대어 **남는 것이 없을 때까지** 돈다. 판 수에 상한을 두는 것은
            #   도구가 *반드시 끝나게* 하기 위해서다 — 위 `seamed` 의 무한 루프를 겪고 넣었다.
            count = 0
            for _pass in range(6):
                hits = arrowhead_seam_hits(svg)
                if not hits:
                    break
                moved = 0
                for whole, fill in hits:
                    if whole in svg:                 # 앞 치환으로 이미 사라졌을 수 있다
                        svg = svg.replace(whole, seamed(whole, fill), 1)
                        moved += 1
                if not moved:
                    break
                count += moved
            left = arrowhead_seam_hits(svg)
            if left:
                # 남은 것을 **수가 아니라 태그로** 보고한다. 수만 찍으면 원인을 못 좁힌다.
                stuck += len(left)
                print("  [수렴 실패] %s — 남은 %d개, 첫 태그:\n      %s"
                      % (fig_id, len(left), left[0][0][:220]))
            if not count:
                continue
            dg["svg"] = svg
            changed = True
            figs += 1
            total += count
            print("  %-38s 화살촉 %d개" % (fig_id, count))
        if changed and args.apply:
            state, why = write_chapter(path, before, data)
            print("  [%s] %s" % (state, why or name))
    print("\n삽화 %d개 · 화살촉 %d개%s"
          % (figs, total, "" if args.apply else "  (미리보기 — --apply 로 반영)"))
    if stuck:
        print("수렴 실패 %d개 — 위 태그를 사람이 볼 것" % stuck)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
