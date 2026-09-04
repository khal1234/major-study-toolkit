"""산문의 '닷 붙은 유량 기호'를 인라인 수식으로 — `ṁ` → `\\(\\dot{m}\\)`.

열린 날 2026-08-07. 사용자: [사용자 발화 인용 생략]

**실측으로 원인을 좁혔다(추정으로 닫지 않았다):**
  ⑴ 둘 다 완성형이다 — `ṁ` U+1E41 · `Ẇ` U+1E86. 결합문자 문제가 아니다.
  ⑵ 둘 다 Pretendard 가 그린다 — 캔버스 폭이 serif 폴백과 달랐다(13.34 vs 15.58).
     즉 글꼴이 없어서 폴백된 것도 아니다.
  ⑶ 남는 것은 **글자 디자인**이다. 소문자 m 위의 점은 작고, m 자체가 넓고 복잡해 묻힌다.
     대문자 W 위의 점은 트인 자리에 있어 잘 보인다. **글꼴을 바꿀 수 없으면 못 고친다.**

**그래서 글자가 아니라 조판으로 옮긴다.** 뷰어에는 이미 `\\dot` 조판이 있다
(`.dot` + `.dot-mark` — `currentColor` 로 **그리는** 점이라 글꼴 글리프가 아니다).
같은 챕터가 이미 두 표기를 섞어 쓰고 있었다 — 날 `ṁ = ρV̇`(ch02 1868행) 옆에
`\\(\\dot{m} = \\rho\\dot{V}\\)`(2114행). **새 규격이 아니라 있던 관례를 맞추는 것이다.**

★ SVG 는 건드리지 않는다 — `<svg>` 안에서는 인라인 수식이 렌더되지 않는다(날것으로 남는다).
  삽화의 닷은 삽화 규격의 몫이라 여기서 손대면 화면이 깨진다.

    python tools/fix_rate_dot.py [--chapter=chNN.json] [--apply]
"""

import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_content  # noqa: E402
from buildlib.jsontext import write_chapter  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 완성형 '점 붙은 글자' → 밑글자. 유니코드에 완성형이 **없는** 것도 있어서
# (V̇·Q̇ 는 결합문자밖에 방법이 없다) 결합문자 형태도 함께 본다.
PRECOMPOSED = {
    "ṁ": "m", "Ṁ": "M", "Ẇ": "W", "ẇ": "w", "Ė": "E", "ė": "e",
    "Ṡ": "S", "ṡ": "s", "Ṫ": "T", "ṫ": "t", "Ṅ": "N", "ṅ": "n",
    "Ṗ": "P", "ṗ": "p", "Ṙ": "R", "ṙ": "r", "Ḃ": "B", "ḃ": "b",
    "Ċ": "C", "ċ": "c", "Ḋ": "D", "ḋ": "d", "Ḟ": "F", "ḟ": "f",
    "Ġ": "G", "ġ": "g", "Ḣ": "H", "ḣ": "h", "Ẋ": "X", "ẋ": "x",
    "Ẏ": "Y", "ẏ": "y", "Ż": "Z", "ż": "z",
}
_COMBINING = "̇"
# `ρV̇` 는 통째로 한 수식으로 묶는다 — 나눠 두면 그리스 문자만 본문 글꼴로 남아 어색하다.
_GREEK_TEX = {"ρ": "\\rho", "θ": "\\theta", "ω": "\\omega", "α": "\\alpha", "β": "\\beta"}

_TOKEN = re.compile(
    "([" + "".join(_GREEK_TEX) + "]?)"
    + "((?:[" + "".join(PRECOMPOSED) + "])|(?:[A-Za-z]" + _COMBINING + "))"
)
# 이미 수식 안에 있는 조각은 건드리지 않는다.
_MATH_SPAN = re.compile(r"\\\((?:[^\\]|\\(?!\)))*\\\)")

# 독자 화면에 안 나가는 자리 + SVG. 여기 손대면 얻는 것 없이 diff 만 커진다.
SKIP_KEYS = {"svg", "sourceRef", "rationale", "notes", "id", "name"}


def _base(sym):
    return PRECOMPOSED.get(sym) or sym[0]


def convert(text):
    """산문 한 줄을 고친 결과. 순수 함수 — 테스트가 직접 부른다."""
    if not isinstance(text, str) or "<svg" in text:
        return text
    guard = [(m.start(), m.end()) for m in _MATH_SPAN.finditer(text)]

    def inside(pos):
        return any(a <= pos < b for a, b in guard)

    out, last = [], 0
    for m in _TOKEN.finditer(text):
        if inside(m.start()):
            continue
        greek, sym = m.group(1), m.group(2)
        tex = (_GREEK_TEX[greek] if greek else "") + "\\dot{" + _base(sym) + "}"
        out.append(text[last:m.start()])
        out.append("\\(" + tex + "\\)")
        last = m.end()
    if not out:
        return text
    out.append(text[last:])
    return "".join(out)


def walk(node, key=None):
    """(고친 노드, 바꾼 개수). SKIP_KEYS 아래로는 내려가지 않는다."""
    if isinstance(node, dict):
        n = 0
        for k, v in node.items():
            if k in SKIP_KEYS:
                continue
            node[k], c = walk(v, k)
            n += c
        return node, n
    if isinstance(node, list):
        n = 0
        for i, v in enumerate(node):
            node[i], c = walk(v, key)
            n += c
        return node, n
    if isinstance(node, str):
        new = convert(node)
        return new, (1 if new != node else 0)
    return node, 0


def main():
    ap = argparse.ArgumentParser(description="산문의 닷 기호를 인라인 수식으로")
    ap.add_argument("--chapter", help="chNN.json 하나만")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    print("규격: 산문의 `ṁ`·`V̇` → `\\(\\dot{m}\\)`·`\\(\\dot{V}\\)` (뷰어 .dot-mark 조판)")
    print("SVG·출처·근거 필드는 건드리지 않는다 — 인라인 수식이 렌더되지 않거나 독자가 안 본다")
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
        data, n = walk(data)
        if not n:
            continue
        total += n
        print("  %-12s 문자열 %d개" % (name, n))
        if args.apply:
            state, why = write_chapter(path, before, data)
            print("  [%s] %s" % (state, why or name))
    print("\n문자열 %d개%s" % (total, "" if args.apply else "  (미리보기 — --apply 로 반영)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
