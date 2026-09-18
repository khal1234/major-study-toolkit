#!/usr/bin/env python
"""수치의 곱을 **괄호 병치에서 곱셈 기호로** 바꾼다 — `(4)(9.81)` → `4 × 9.81`.

    python tools/fix_numeric_product.py [--chapter=chNN.json] [--show|--summary] [--apply]

## 왜 (2026-08-13, 사용자 판정)

사용자: *[발화 생략]*

괄호 병치는 교재(Cengel)의 관례이지만, 이 리포는 같은 날 **곱을 붙여 쓰기로** 정했다
(AGENTS 「기호 사이의 가운데점」). 기호는 붙일 수 있어도 **수는 붙일 수 없으므로**
그 규칙과 결이 맞는 것은 **연산자를 드러내는 것**이다.

- **가운데점은 안 된다.** 이 리포에서 가운데점은 **단위의 곱**에만 쓴다(`kJ/(kg·K)`).
  수에 쓰면 그 규약이 무너진다 — 사용자가 든 두 후보 중 이쪽을 뺀 이유다.
- **자리마다 글자가 다르다.** 수식 안은 `\\times`, 산문·삽화는 `×`(U+00D7).
  산문에 `\\times` 를 쓰면 역슬래시째 찍히고, 수식에 `×` 를 쓰면 글꼴이 갈린다.
  ★ 산문의 `×` 는 **이미 이 자료의 관례**다(ch04 풀이 `2.5 × 1.005 × 130`) — 새 표기가 아니다.
- **판정선은 「괄호 안이 수인가」 하나다.** `(a)`·`(b)` 같은 문항 표시는 수가 아니라 안 걸린다.
  기호 병치(`(P)(V)`)도 대상이 아니다 — 그건 붙여 쓰는 쪽이고 `fix_symbol_product` 의 몫이다.

## 자리 판정은 빌드의 등록부를 그대로 쓴다

「이 필드가 통째로 LaTeX 인가」는 `MATH_NATIVE_KEYS` 가 정본이다. 같은 질문에 자를 두 개
두면 반드시 갈라진다 — `fix_symbol_product` 가 그 자리에서 한 번 데었다(2026-08-13).
산문 안의 `\\(…\\)` 스팬도 수식으로 본다.
"""
import argparse
import copy
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import audit_content                                                    # noqa: E402
from buildlib.checks_content import MATH_NATIVE_KEYS                    # noqa: E402
from buildlib.jsontext import write_chapter                             # noqa: E402
from buildlib.review import AUTHOR_ONLY_FIELDS                          # noqa: E402

MATH_KEYS = frozenset(k.lstrip("/") for k in MATH_NATIVE_KEYS) - {"svg"}
EXEMPT_KEYS = frozenset(AUTHOR_ONLY_FIELDS) | frozenset(
    {"id", "sourceRef", "source", "href", "sourcePages", "supplementNotes",
     "reviewNote", "reviewClass", "lintWaivers"})

# 괄호 안이 **수**인 것만. `{,}`(LaTeX 천 단위)와 쉼표·소수점을 허용한다.
_NUM = r"\(\s*-?\d[\d.,]*(?:\{,\}[\d.,]*)*\s*\)"
CHAIN = re.compile(r"(?:" + _NUM + r"){2,}")
INNER = re.compile(_NUM)
_MATH_SPAN = re.compile(r"\\\((.*?)\\\)", re.S)
_SVG_TEXT = re.compile(r"(<(?:text|tspan)\b[^>]*>)([^<>]*)(</(?:text|tspan)>)")


def rewrite(text, math=False):
    """(고친 글, [(전, 후)]) — **판정과 처방이 한 함수에 있다.** 순수 함수.

    `math` 는 값 전체가 LaTeX 인 자리. 산문은 `\\(…\\)` 안팎을 갈라 각각 처리한다.
    """
    if not isinstance(text, str) or not text:
        return text, []
    if math:
        return _one(text, True)
    # 산문 — `\(…\)` 안은 수식, 밖은 산문. 한 문자열 안에서 글자가 갈린다.
    out, hits, pos = [], [], 0
    for m in _MATH_SPAN.finditer(text):
        seg, hs = _one(text[pos:m.start()], False)
        out.append(seg)
        hits.extend(hs)
        inner, hs = _one(m.group(1), True)
        out.append("\\(" + inner + "\\)")
        hits.extend(hs)
        pos = m.end()
    seg, hs = _one(text[pos:], False)
    out.append(seg)
    hits.extend(hs)
    return "".join(out), hits


def _one(text, math):
    glue = " \\times " if math else " × "
    hits = []

    def sub(m):
        parts = [p.strip("() \t") for p in INNER.findall(m.group(0))]
        new = glue.join(parts)
        hits.append((m.group(0), new))
        return new
    return CHAIN.sub(sub, text), hits


def rewrite_svg(text):
    """삽화는 `<text>` 안의 글자만 본다 — `path` 의 좌표에 손대면 도형이 깨진다."""
    hits = []

    def body(m):
        fixed, hs = _one(m.group(2), False)
        hits.extend(hs)
        return m.group(1) + fixed + m.group(3)
    return _SVG_TEXT.sub(body, text), hits


def walk(node, key, trail, found, apply_):
    """스키마를 열거하지 않는다 — 새 필드가 조용히 빠지지 않게 통째로 내려간다."""
    if isinstance(node, dict):
        return {k: (v if k in EXEMPT_KEYS else walk(v, k, trail + "/" + str(k), found, apply_))
                for k, v in node.items()}
    if isinstance(node, list):
        return [walk(v, key, trail + "[" + str(i) + "]", found, apply_)
                for i, v in enumerate(node)]
    if isinstance(node, str):
        if key == "svg":
            fixed, hs = rewrite_svg(node)
        else:
            fixed, hs = rewrite(node, math=(key in MATH_KEYS
                                            or (key == "answer" and "blanks[" in trail)))
        for h in hs:
            found.append((trail, h))
        return fixed if apply_ else node
    return node


def main():
    ap = argparse.ArgumentParser(description="수치의 곱을 곱셈 기호로 (기본은 미리보기)")
    ap.add_argument("--chapter", help="chNN.json 하나만")
    ap.add_argument("--show", action="store_true", help="기본값 — 걸린 자리를 낸다")
    ap.add_argument("--summary", action="store_true", help="건수만")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    ap.add_argument("--limit", type=int, default=40, help="챕터당 출력 줄 수")
    args = ap.parse_args()

    print("규격: 수치의 곱은 곱셈 기호로 — 수식은 \\times, 산문·삽화는 ×")
    names = ([args.chapter] if args.chapter
             else [n + ".json" for n in audit_content.CHAPTERS])
    total = 0
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        before = copy.deepcopy(data)
        found = []
        after = walk(data, None, "root", found, args.apply)
        if not found:
            continue
        total += len(found)
        print("=== %s — %d곳" % (name, len(found)))
        if not args.summary:
            for i, (trail, (old, new)) in enumerate(found):
                if i >= args.limit:
                    print("    … 외 %d곳" % (len(found) - i))
                    break
                print("  %s → %s   %s" % (old, new, trail))
        if args.apply:
            state, why = write_chapter(path, before, after)
            print("  [%s] %s" % (state, why or name))
    print("\n합계 — %d곳%s" % (total, "" if args.apply else "  (--apply 를 붙여야 쓴다)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
