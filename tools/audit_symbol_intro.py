# -*- coding: utf-8 -*-
"""정의 없이 튀어나오는 기호를 찾는다 (읽기 전용).

열린 날 2026-08-01. 사용자가 ch01 방향장 절을 읽다 물었다 —
*"y(x+h) = y(x) + h y'(x) + h²/2 y''(ξ) 테일러 전개 이거 맞아? 처음 보는거라."*

맞는 식이었다. 문제는 **`ξ` 가 무엇인지 한 줄도 없이 등장한다**는 것이었다.
AGENTS 「목표 독자」의 *"기호가 어디서 왔는지 밝힌다"* 에 정면으로 걸리는데,
빌드에는 이걸 보는 검사가 하나도 없었다 — **빠뜨려도 통과되는 구조**다(규칙 7 ⑷).

무엇을 재는가
    ⑴ 챕터의 **산문 필드**에서 인라인 수식 `\\( … \\)` 을 모으고
    ⑵ 그 안의 **기호**(라틴 한 글자 · 그리스 문자 · `\\xi` 같은 LaTeX 명령)를 센다
    ⑶ 그중 **드물게 쓰이고(기본 2회 이하) 정의된 적이 없는** 것만 후보로 낸다.

    '정의됐다'의 판정은 둘 중 하나다.
      · 어느 유도의 `variables` 에 키로 등록돼 있다 (이 리포에서 기호를 정의하는 정식 자리)
      · 그 기호가 나온 자리 근처에 **정의 문구**가 있다(`~라 하자`·`여기서`·`~를 뜻한다` 등)

왜 '드문 것'만 보는가
    `x`·`y` 처럼 챕터 내내 쓰이는 기호는 맥락으로 익혀진다. 실제로 독자가 걸리는 것은
    **딱 한 번 나오고 설명이 없는 기호**다(`ξ` 가 정확히 그랬다 — 챕터 전체에서 1회).
    빈도를 낮게 잡을수록 후보가 길어지므로 기본값은 2회로 둔다.

★ 이 도구는 **판정하지 않는다 — 후보만 낸다.** '정의가 필요한 기호인가'는 문맥 판단이라
  기계가 정할 수 없다. 그래서 빌드 검사로 승격하지 않았다. 대신 후보를 짧게 유지해
  사람이 매번 다 볼 수 있게 하는 것이 이 도구의 목표다.

    python tools/audit_symbol_intro.py
    python tools/audit_symbol_intro.py --chapter=ch01
    python tools/audit_symbol_intro.py --max-count=3

--order — **소개보다 먼저 쓰인** 용어·기호 (열린 날 2026-08-02, 사용자 지적)
    사용자 원문: *"이론 2번째 절에 아직 건도 안나왔고 이제 건도 나올 예정이다 한건데
    떠올리기에 대뜸 (x=1) 나오는게 적절한가 싶네"*

    본문은 스스로 미뤘다 — *"그 정보를 숫자로 나타낸 것이 **다음 절**의 '건도(quality)'입니다"*.
    그런데 **같은 절의 이해도 체크 해설**이 `(x=1)` 을 먼저 썼다.

    ★ 부류: **본문이 뒤로 미룬 것을, 같은 화면의 다른 필드가 먼저 쓴다.**
      본문·유도·이해도 체크·문풀은 각각 다른 필드라 본문에서 미뤄도 나머지가 그걸 모른다.
      위 기본 모드는 ⑴ **인라인 수식만** 보고 ⑵ `x` 를 공용 기호(COMMON)로 봐주므로
      이 자리를 영영 못 본다 — 실제로 ch03 후보 0건이었다.

    무엇을 재는가: 읽는 순서(도입부 → 이론 절 → 유도 → 문풀 → 연습문제)를 세우고,
      · `건도(quality)` 처럼 **용어 병기**가 처음 나온 자리를 그 용어의 소개 지점으로 보고
      · 병기 바로 뒤의 한 글자(`건도(quality) x`)를 그 기호의 소개 지점으로 본다.
    그보다 **앞선** 자리에서 그 용어·기호를 쓰면 후보로 낸다.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_content                                                       # noqa: E402

DATA = audit_content.DATA

INLINE_MATH = re.compile(r"\\\((.+?)\\\)", re.S)
# 그리스 문자(유니코드 직접 표기) — 이 리포는 `ξ` 처럼 날것으로 쓰는 자리가 있다.
GREEK = re.compile(r"[Α-Ωα-ω]")
# `\xi` 같은 LaTeX 명령. 뒤에 글자가 더 붙으면 다른 명령이므로 경계를 둔다.
GREEK_CMD = re.compile(r"\\(alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|kappa"
                       r"|lambda|mu|nu|xi|pi|rho|sigma|tau|upsilon|phi|chi|psi|omega"
                       r"|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Phi|Psi|Omega)\b")
# 라틴 한 글자 — 앞뒤에 글자가 없어야 '기호'다(`sin`·`ln` 의 s·l 을 잡지 않기 위해).
LATIN = re.compile(r"(?<![A-Za-z\\])([A-Za-z])(?![A-Za-z])")

# 이 기호들은 이 리포의 공용 표기라 매번 정의하지 않는다.
#   x·y·t: 독립·종속 변수 / n·i·k: 지표 / e: 자연상수 / d: 미분 / c: 임의 상수
#   f·g: 일반 함수 / C: 적분상수
COMMON = set("xytnikedcfgC") | {"\\pi"}

# 근처에 이 말이 있으면 '정의하는 문장'으로 본다.
DEFINING = ("라 하자", "라고 하자", "라 한다", "라고 한다", "여기서", "란 ", "이란 ",
            "를 뜻한다", "을 뜻한다", "를 의미한다", "을 의미한다", "라 부른다",
            "이라 부른다", "로 둔다", "라 두면", "으로 둔다", "사이의", "사이에",
            "표기로", "라 쓰면", "로 쓴다", "정의한다", "정의하면")
DEFINE_WINDOW = 120      # 기호 앞뒤로 이만큼 안에 정의 문구가 있으면 소개된 것으로 본다


def walk_prose(chapter):
    """산문 필드를 (소유자 id, 필드 경로, 문자열) 로 흘린다.

    수식 전용 필드(`latex`·`equations`·`solutionTemplate`)와 `svg` 는 제외한다 —
    거기는 식이 사는 곳이지 기호를 **소개하는** 자리가 아니다.
    """
    skip = ("latex", "equations", "solutionTemplate", "svg", "answer", "sourceRef",
            "id", "topic", "file", "anchorText", "relatedFormulas")

    def rec(node, owner, path):
        if isinstance(node, dict):
            own = node.get("id", owner)
            for key, value in node.items():
                if key in skip:
                    continue
                rec(value, own, path + "/" + str(key))
        elif isinstance(node, list):
            for item in node:
                rec(item, owner, path)
        elif isinstance(node, str) and len(node) > 8:
            out.append((owner, path, node))

    out = []
    rec(chapter, "?", "")
    return out


def declared_variables(chapter):
    """유도의 `variables` 에 등록된 기호들 — 이 리포가 기호를 정의하는 정식 자리."""
    names = set()
    for formula in (chapter.get("derivation") or {}).get("formulas") or []:
        for key in (formula.get("variables") or {}):
            names.update(symbols_in(str(key)))
    return names


def symbols_in(text):
    """문자열에서 기호를 뽑는다. 순수 함수 — 테스트가 직접 부른다."""
    found = set(GREEK.findall(text))
    found.update("\\" + m for m in GREEK_CMD.findall(text))
    found.update(LATIN.findall(text))
    return found


def scan(chapter):
    """(기호 → {'count': n, 'defined': bool, 'where': [(owner, 발췌)]})."""
    declared = declared_variables(chapter)
    table = {}
    for owner, _path, text in walk_prose(chapter):
        for m in INLINE_MATH.finditer(text):
            span = m.group(1)
            # ★ 정의 판정은 **그 기호를 실제로 언급하는가**까지 본다 (열린 날 2026-08-01,
            #   이 도구의 첫 실행에서 바로 걸렸다).
            #
            #   첫 시안은 '근처에 정의 문구가 있으면 소개된 것'으로 봤다. 그랬더니
            #   **이 도구를 만든 계기인 `ξ` 를 놓쳤다** — 그 문단은
            #   *"…\\(… y''(ξ)\\)에서 앞의 두 항만 취한 것이 오일러법입니다.
            #   **여기서** \\(y'(x) = f(x,y)\\)는 …"* 라, `여기서` 가 **다른 기호**를
            #   정의하는데 그 근접성이 `ξ` 까지 통과시켰다.
            #
            #   자기가 만들어진 사례를 못 잡는 감사는 0건을 찍어도 의미가 없다(규칙 11).
            #   그래서 **⑴ 정의 문구가 있고 ⑵ 그 문맥에서 그 기호를 다시 언급**해야
            #   소개된 것으로 본다. 현재 수식 자신은 문맥에서 빼야 자기 언급이 근거가 안 된다.
            context = (text[max(0, m.start() - DEFINE_WINDOW):m.start()]
                       + " " + text[m.end():m.end() + DEFINE_WINDOW])
            has_marker = any(marker in context for marker in DEFINING)
            context_symbols = symbols_in(context) if has_marker else set()
            for sym in symbols_in(span):
                bare = sym.lstrip("\\")
                # COMMON 은 `\pi` 처럼 명령 형태로도 담기므로 **둘 다** 대조한다
                # (첫 시안은 `bare` 만 봐서 `\pi` 가 계속 후보로 남았다).
                if sym in COMMON or bare in COMMON or (len(bare) == 1 and bare in declared):
                    continue
                if sym in declared or bare in declared:
                    continue
                row = table.setdefault(sym, {"count": 0, "defined": False, "where": []})
                row["count"] += 1
                row["defined"] = row["defined"] or (sym in context_symbols)
                if len(row["where"]) < 2:
                    snippet = text[max(0, m.start() - 30):m.end() + 30].replace("\n", " ")
                    row["where"].append((owner, snippet.strip()))
    return table


# 읽는 순서 — 뷰어의 탭 순서이자 독자가 실제로 지나가는 순서다.
READING_ORDER = ("chapterIntro", "learningObjectives", "theory", "derivation",
                 "practice", "problems")
# ★ 도입부와 학습목표는 **예고하는 자리**다 — 거기서 용어를 먼저 부르는 것은 설계다
#   (AGENTS 「과목 개요와 챕터 도입부」). 그래서 '먼저 쓴 곳'에서 제외한다.
#   빼지 않으면 ch03 후보 22건 중 12건이 학습목표였다 — 그 잡음에 진짜 1건이 묻힌다.
PREVIEW_UNITS = ("chapterIntro", "learningObjectives")
# 두 글자 용어(물질·상태·질량·규칙)는 보통명사와 구별되지 않아 잡음만 낸다.
TERM_MIN_LEN = 3
# `건도(quality) x` · `방향장(direction field)` — 용어 병기와, 바로 뒤에 오는 한 글자 기호.
TERM_PAIR = re.compile(r"([가-힣]{2,12})\s*\(\s*([A-Za-z][A-Za-z\s/,'-]{1,28})\)"
                       r"(?:\s*([A-Za-z])(?![A-Za-z]))?")
# 기호가 **수식처럼** 쓰인 자리만 센다 — 산문 속 낱글자는 잡음이다.
SYMBOL_USE = r"(?:(?<=[(=])\s*{s}(?![A-Za-z가-힣])|(?<![A-Za-z\\]){s}\s*[=<>≥≤·×+\-−])"


def reading_units(chapter):
    """(소유자 id, 노드, 컬렉션 키) 를 읽는 순서대로. 안쪽 순서는 데이터 그대로다.

    **컬렉션 키를 함께 흘리는 이유:** 예고 자리 판정은 항목 id(`lo1`)가 아니라
    그 항목이 **어느 컬렉션에 사는지**로 해야 한다. 처음에 id 로 봤더니
    학습목표 12건이 그대로 후보에 남았다 — 걸러 내려던 바로 그것이다.
    """
    units = []
    for key in READING_ORDER:
        node = chapter.get(key)
        if node is None:
            continue
        if isinstance(node, dict) and key in ("theory", "derivation"):
            for item in (node.get("sections") or node.get("formulas") or []):
                units.append((item.get("id", key), item, key))
        elif isinstance(node, list):
            for item in node:
                units.append((item.get("id", key) if isinstance(item, dict) else key, item, key))
        else:
            units.append((key, node, key))
    return units


def order_issues(chapter):
    """소개보다 앞서 쓰인 용어·기호 [(종류, 이름, 소개 위치, 먼저 쓴 위치, 발췌)]. 순수 함수."""
    texts = []
    for i, (owner, node, key) in enumerate(reading_units(chapter)):
        for own, _path, text in walk_prose(node):
            texts.append((i, own if own != "?" else owner, text, key in PREVIEW_UNITS))
    terms, symbols = {}, {}
    for i, owner, text, _preview in texts:
        for m in TERM_PAIR.finditer(text):
            term, sym = m.group(1), m.group(3)
            if term not in terms or i < terms[term][0]:
                terms[term] = (i, owner)
            if sym and (sym not in symbols or i < symbols[sym][0]):
                symbols[sym] = (i, owner, term)
    out = []
    for term, (idx, owner) in sorted(terms.items()):
        if len(term) < TERM_MIN_LEN:
            continue
        for i, who, text, preview in texts:
            if i < idx and not preview and term in text:
                out.append(("용어", term, owner, who, _snippet(text, term)))
                break
    for sym, (idx, owner, term) in sorted(symbols.items()):
        pattern = re.compile(SYMBOL_USE.format(s=re.escape(sym)))
        for i, who, text, preview in texts:
            if i < idx and not preview and pattern.search(text):
                out.append(("기호 " + sym, term, owner, who,
                            _snippet(text, pattern.search(text).group(0).strip())))
                break
    return out


def _snippet(text, needle):
    at = text.find(needle)
    return re.sub(r"\s+", " ", text[max(0, at - 34):at + len(needle) + 34]).strip()


def run_order(only):
    print("소개보다 **먼저** 쓰인 용어·기호 — 후보 (판정은 사람이 한다)")
    print("기준: 용어 병기 `한글(English)` 가 처음 나온 자리를 소개 지점으로 본다\n")
    total = 0
    for name in sorted(os.listdir(DATA)):
        if not re.fullmatch(r"ch\d+\.json", name):
            continue
        if only and os.path.splitext(name)[0] != only:
            continue
        with open(os.path.join(DATA, name), encoding="utf-8") as fh:
            rows = order_issues(json.load(fh))
        print("-- %s : 후보 %d건" % (name, len(rows)))
        for kind, term, intro_at, used_at, snippet in rows:
            print("   %-8s %-10s 소개 [%s] ← 먼저 쓴 곳 [%s]" % (kind, term, intro_at, used_at))
            print("            %s" % snippet[:88])
        total += len(rows)
        print()
    print("합계 후보 %d건 — 각각 '독자가 여기서 막히는가'로 판정할 것" % total)
    print("(읽기 전용 감사 — 파일을 쓰지 않았다)")
    return 0


def main():
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    if "--order" in sys.argv:
        return run_order(only)
    max_count = int(next((a.split("=", 1)[1] for a in sys.argv
                          if a.startswith("--max-count=")), "2"))
    print("정의 없이 나오는 기호 — 후보 (판정은 사람이 한다)")
    print("기준: 인라인 수식에 %d회 이하로 나오고, variables 등록도 정의 문구도 없는 기호\n"
          % max_count)
    total = 0
    for name in sorted(os.listdir(DATA)):
        if not re.fullmatch(r"ch\d+\.json", name):
            continue
        stem = os.path.splitext(name)[0]
        if only and stem != only:
            continue
        with open(os.path.join(DATA, name), encoding="utf-8") as fh:
            chapter = json.load(fh)
        rows = [(sym, row) for sym, row in scan(chapter).items()
                if row["count"] <= max_count and not row["defined"]]
        print("-- %s : 후보 %d건" % (name, len(rows)))
        for sym, row in sorted(rows, key=lambda r: (r[1]["count"], r[0])):
            owner, snippet = row["where"][0]
            print("   %-10s %d회  [%s] %s" % (sym, row["count"], owner, snippet[:78]))
        total += len(rows)
        print()
    print("합계 후보 %d건 — 각각 '독자가 여기서 막히는가'로 판정할 것" % total)
    print("(읽기 전용 감사 — 파일을 쓰지 않았다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
