r"""인자를 중괄호로 감싸지 않은 매크로를 고친다 — `\dot m` → `\dot{m}`.

열린 날 2026-08-12 (열역학 검수 인박스 부류 1 「수식이 화면에서 깨진다」).
사용자 실측: ch01 유도 1/13 이 `\vec F=m\vec a` 를 **LaTeX 원문 그대로** 화면에 찍었고
ch02 유도 4/15 에 `\dot` 이 노출됐다.

**원인은 renderMath 의 문법이다.** 뷰어의 치환은 `/\\dot\{([^{}]*)\}/` 처럼 **중괄호 형태만**
받는다 — `\dot m` 은 매치되지 않아 매크로 이름이 글자로 남는다. LaTeX 자체는 `\dot m` 을
받아 주므로 **데이터를 쓰는 쪽에서는 틀린 줄 모른다.** 그래서 손으로 조심하는 것으로는 안 되고
빌드가 막아야 한다 — 그 자리가 `checks_content.brace_arg_macro_issues`(C39)이고,
이 도구는 **이미 들어온 것을 걷어내는** 쪽이다.

★ 자동으로 고치는 것은 **인자가 한 글자**인 경우뿐이다(`\dot m`·`\vec F`). 여러 글자
  (`\mathrm kg`)나 인자가 둘인 `\frac a b` 는 어디까지가 인자인지 기계가 모른다 —
  그 자리는 **목록으로만 내놓고 사람이 고친다.** 기계가 찍으면 `\mathrm{k}g` 처럼
  조용히 틀린 것이 들어간다.

★ SVG 는 건드리지 않는다 — `<svg>` 안에서는 인라인 수식이 렌더되지 않는다(`fix_rate_dot` 선례).

    python tools/fix_latex_brace_args.py [--chapter=chNN.json] [--apply]
"""

import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_content  # noqa: E402
from buildlib.checks_content import brace_arg_macro_hits  # noqa: E402
from buildlib.jsontext import write_chapter  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 인자가 하나인 매크로만 자동 변환한다. `frac` 는 인자가 둘이라 여기 없다.
ONE_ARG = ("vec", "ddot", "dot", "hat", "mathbf", "mathcal", "mathrm", "text", "sqrt")
AUTO_RE = re.compile(r"\\(" + "|".join(ONE_ARG) + r")(?![A-Za-z])[ ]+([A-Za-z0-9])(?![A-Za-z0-9])")

SKIP_KEYS = {"svg"}


def convert(text):
    """고친 결과. 순수 함수 — 테스트가 직접 부른다."""
    if not isinstance(text, str):
        return text
    return AUTO_RE.sub(lambda m: "\\" + m.group(1) + "{" + m.group(2) + "}", text)


def walk(node, key=None):
    """(고친 노드, 바꾼 문자열 수, 남은 수동 항목)."""
    left = []
    if isinstance(node, dict):
        n = 0
        for k, v in node.items():
            if k in SKIP_KEYS:
                continue
            node[k], c, rest = walk(v, k)
            n += c
            left.extend(rest)
        return node, n, left
    if isinstance(node, list):
        n = 0
        for i, v in enumerate(node):
            node[i], c, rest = walk(v, key)
            n += c
            left.extend(rest)
        return node, n, left
    if isinstance(node, str):
        new = convert(node)
        return new, (1 if new != node else 0), brace_arg_macro_hits(new)
    return node, 0, left


def main():
    ap = argparse.ArgumentParser(description="중괄호 없는 매크로 인자를 감싼다")
    ap.add_argument("--chapter", help="chNN.json 하나만")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    print(r"규격: `\dot m` → `\dot{m}` — renderMath 는 중괄호 형태만 치환한다 (빌드 C39)")
    print("인자가 여러 글자이거나 둘인 것은 자동으로 안 고친다 — 아래 [수동] 목록을 사람이 본다")
    names = ([args.chapter] if args.chapter
             else [n + ".json" for n in audit_content.CHAPTERS])
    total, manual = 0, 0
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        before = copy.deepcopy(data)
        data, n, left = walk(data)
        if n:
            total += n
            print("  %-12s 문자열 %d개" % (name, n))
            if args.apply:
                state, why = write_chapter(path, before, data)
                print("  [%s] %s" % (state, why or name))
        for macro, snip in left:
            manual += 1
            print("  [수동] %-12s \\%-8s %s" % (name, macro, snip))
    print("\n자동 %d개 · 수동 %d개%s"
          % (total, manual, "" if args.apply else "  (미리보기 — --apply 로 반영)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
