# -*- coding: utf-8 -*-
r"""수식 바로 뒤의 **줄표를 콜론으로** 바꾼다 — 줄표가 마이너스로 읽히기 때문이다.

    python tools/fix_math_label_dash.py                      # 무엇을 바꿀지만 보여준다
    python tools/fix_math_label_dash.py --chapter=ch12.json --apply

왜 도구인가 (신설 2026-08-07, 동역학 ch12 9절에서 열림) — 사용자 지적:
*[발화 생략]*. 같은 사용자가 **바로 앞 문장에서** 절 제목의 줄표
(*[발화 생략]*)는 *[발화 생략]* 라고 했다 — 즉 줄표 자체가 아니라
**수식 뒤에 붙은 줄표**가 문제다.

★ 왜 수식 뒤에서만 불편한가: 바로 앞에 `= -\dot\theta\,\mathbf{u}_r` 처럼 **진짜 마이너스**가
  있으면 눈은 같은 높이의 짧은 가로줄을 하나 더 보고 **연산자로 읽는다.** 산문 뒤라면
  그렇게 읽힐 여지가 없다. 그래서 판정선은 *[발화 생략]* 하나다.
★ 처방이 콜론인 이유: 이 자리의 문형은 **`수식(레이블) → 설명(값)`** 이고, AGENTS 표기 세부가
  *[발화 생략]* 이라고 이미 정해 두었다. 새 규격이 아니라
  **적용을 빠뜨린 자리**다.
★ 손으로 고치지 말 것: 실측 동역학 3챕터에 11곳이었고, 고치면서 **콜론 뒤 공백을 빠뜨리기 쉽다**
  (실제로 그렇게 한 번 났다 — AGENTS *[발화 생략]*). 그래서 이 도구는
  ⑴ 줄표→콜론 ⑵ 콜론 뒤 공백 정규화를 **함께** 한다.

판정은 `buildlib.checks_content.math_label_dash_hits` 하나를 쓴다 — 자와 처방이 갈리면
감사는 0건인데 화면은 그대로인 상태가 만들어진다(이 리포가 반복해 만난 형태다).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from audit_conventions import chapters                                 # noqa: E402
from buildlib.checks_content import math_label_dash_fix                # noqa: E402
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
        fixed, hits = math_label_dash_fix(node)
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
