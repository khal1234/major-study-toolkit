# -*- coding: utf-8 -*-
r"""수식 안의 `\cdot` 을 **병치**(또는 숫자가 끼면 `\times`)로 바꾼다.

    python tools/fix_cdot.py                        # 무엇을 바꿀지만 보여준다
    python tools/fix_cdot.py --chapter=ch01.json --apply

왜 도구인가 (신설 2026-08-07) — `checks_content.latex_cdot_hits` 가 신고는 하는데
**고치는 쪽이 없었다.** 그러면 과목마다 손으로 고치게 되고, 손으로 고치면 `\,` 과 `\times`
가 풀이마다 갈린다 — 그 갈림이 이 검사가 없애려던 결함(*[발화 생략]*)과
같은 부류다. 실측: 공학수학 두 챕터에 34곳이었고 `Edit` 로 하나씩 고치면 34번이다
(AGENTS 실행 규율 4 — 파일 편집도 배치로).

판정과 처방은 `buildlib.checks_content` 한 곳에 있다(`latex_cdot_hits` ↔ `latex_cdot_fix`).
사본을 두면 감사는 0건인데 화면은 그대로인 상태가 만들어진다 — 이 리포가 반복해 만난 형태다.

★ 단위(`\mathrm{N \cdot m}`)는 건드리지 않는다. 거기서는 가운데점이 규격이다.
★ `\cdots`(줄임표)도 대상이 아니다 — 곱이 아니다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from audit_conventions import chapters                                 # noqa: E402
from buildlib.checks_content import latex_cdot_fix                     # noqa: E402
from buildlib.jsontext import write_chapter                            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def rewrite(node, log):
    """트리를 돌며 문자열을 고친 사본을 돌려준다."""
    if isinstance(node, dict):
        return dict((k, rewrite(v, log)) for k, v in node.items())
    if isinstance(node, list):
        return [rewrite(v, log) for v in node]
    if isinstance(node, str):
        fixed, hits = latex_cdot_fix(node)
        if hits:
            log.extend(hits)
        return fixed
    return node


def main():
    only = next((a.split("=", 1)[1] for a in sys.argv
                 if a.startswith("--chapter=")), None)
    apply_ = "--apply" in sys.argv
    total = 0
    for subject, name, chapter in chapters():
        if only and name != only and name != os.path.splitext(only)[0]:
            continue
        log = []
        fixed = rewrite(chapter, log)
        if not log:
            continue
        total += len(log)
        print("=== %s %s — %d곳 ===" % (subject, name, len(log)))
        for snip in log[:12]:
            print("   ", snip)
        if len(log) > 12:
            print("    … 외 %d곳" % (len(log) - 12))
        if apply_:
            path = os.path.join(DATA, subject,
                                name if name.endswith(".json") else name + ".json")
            write_chapter(path, chapter, fixed)
            print("  [written]", os.path.relpath(path, ROOT))
    print("\n합계 %d곳%s" % (total, "" if apply_ else " (--apply 를 붙여야 쓴다)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
