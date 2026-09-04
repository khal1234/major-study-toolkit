r"""한 글자가 두 물리량을 뜻할 때, **그 카드가 선언한 뜻대로** 기호를 옮긴다.

열린 날 2026-08-12 (열역학 검수 인박스 부류 2·12).
사용자: [사용자 발화 인용 생략]
→ 2026-08-08 판정(부피를 필기체)을 뒤집었다. 규격의 정본은 `data/<과목>/terms.json` 의
`symbols` 이고, 막는 것은 빌드 **C44** `symbol_role_issues` 다. 이 도구는 **이미 들어온 것을
옮기는** 쪽이다.

★★ **판정 축이 「토큰」이 아니라 「카드」다.** `V^{2}` 처럼 모양만 보고 옮기면 절반도 못 옮긴다 —
  실측(열역학 ch02·ch05): 속도 V 의 대부분이 `V_1`·`\rho V A_c` 같은 **맨 V** 라 부피의
  `V_1`·`V_2` 와 모양이 똑같다. 기계가 볼 수 있는 것은 **저자 선언**뿐이다:

      유도 카드의 `variables` 가 그 카드에서 V 가 무엇인지 말하고 있다.

  그래서 **`variables` 가 선언한 카드 안에서만** 옮긴다. 그 카드의 식·설명·삽화는 같은 기호를
  같은 뜻으로 쓰므로 카드 단위 치환이 안전하고, 선언이 없는 곳(이론 절·문풀·연습문제)은
  **어디를 볼지만 알려 주고 사람이 판정한다.**

★ **삽화(svg) 안에서는 글리프를 직접 쓴다.** 거기엔 renderMath 가 돌지 않아 `\mathcal{V}` 라고
  적으면 그 글자가 화면에 그대로 남는다(`ℓ` 이 이미 글리프로 들어가 있다).
  그 밖의 필드에는 매크로 이름을 쓴다.

★ **`\dot{V}`(체적유량)는 건드리지 않는다** — 부피의 시간율이라 부피 표기를 따라간다.
  치환 정규식이 `\dot{` 뒤의 V 를 제외하는 것이 그 장치다.

★ **표기를 보존해 쓴다** — `buildlib.jsontext.write_chapter` 가 바뀐 문자열 값만 갈아끼우고
  마지막에 재파싱으로 검증한다. 통째로 다시 쓰면 변경점 하이라이트가 잡음이 된다.

    python tools/fix_velocity_symbol.py [--chapter=chNN.json] [--apply]
"""

import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_content  # noqa: E402
from buildlib.checks_content import (_iter_check_owners, _symbol_base,  # noqa: E402
                                     _terms_list, _terms_raw, declared_roles,
                                     symbol_masked, symbol_role_word_issues,
                                     symbol_split_hits)
from buildlib.jsontext import write_chapter  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# ★★ **stderr 도 고친다** (열린 날 2026-08-12, 동역학 세션 보고). 이 도구가 선언 없는 과목에서
#   `sys.exit("이 과목은 …")` 로 끝났는데 그 글이 **`?? ??????…` 로 깨져 나왔다** — stdout 만
#   UTF-8 로 돌려놓았고 stderr 는 Windows 기본 cp949 그대로였기 때문이다. 실측: 이 리포의
#   79개 도구가 stdout 을 고치는데 stderr 를 고친 것은 **`backup_bundle.py` 하나뿐**이었다.
#   즉 **오류 메시지만 골라서 깨지는** 구조였고, 그건 사람이 가장 읽어야 할 글이다.
#   잠금 `test_checks.py::test_tool_errors_are_utf8`(stderr 를 쓰는 도구는 이 줄을 요구한다).
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

GLYPH = {"\\mathcal{V}": "\U0001D4B1"}   # 매크로 → 산문·삽화용 글리프
COMPOUNDS = ()   # 낱글자가 아니라 **한 낱말**인 글자 덩어리. 과목이 terms.json 에 적는다.
HOLD = "\x00"        # 동시 치환용 자리표 — 데이터에 못 들어오는 문자다(빌드가 제어문자를 막는다)


def card_roles(variables, symbols, not_roles):
    """{밑기호: 역할}. **판정은 `checks_content.declared_roles` 하나가 한다** —
    여기 복사본을 두었더니 검사만 고쳤을 때 `"V_{1}, V_{2}"` 를 검사는 신고하는데 도구는
    안 옮기는 상태가 실제로 났다(2026-08-12). 자를 두 벌 두지 않는다."""
    return {_symbol_base(k): role
            for k, role in declared_roles(variables, symbols, not_roles)}


_MATH_SPAN = re.compile(r"\\\((.*?)\\\)", re.S)
# 인자를 통째로 건너뛸 매크로 — 그 안의 글자는 **기호가 아니라 이름**이다(단위·로만체·이미 옮긴 것).
_OPAQUE = re.compile(r"\\(?:mathrm|text|mathcal|dot|operatorname)\{[^{}]*\}")
_LETTERS = re.compile(r"[A-Za-z]+")
_SVG_TEXT = re.compile(r"(<(?:text|tspan)\b[^>]*>)([^<]*)(</(?:text|tspan)>)")
COMBINING_DOT = "\u0307"          # `V̇` — 체적유량을 결합문자로 적은 자리다. 속도가 아니다.


def _mark_bare(text, sym, mark, compounds=()):
    r"""맨 기호 `sym` 자리에 자리표를 박는다. 순수 함수 — 테스트가 직접 부른다.

    ★★ **글자 인접을 통째로 막으면 안 된다** (2026-08-12 실측으로 열림).
      처음에는 `(?![A-Za-z])` 로 뒤에 글자가 오는 것을 전부 뺐다. 그런데 이 과목에서
      가장 흔한 속도 표기가 **`\rho V A_c`·`VA_c`** — 곱을 병치로 쓰므로 V 뒤에 A 가 온다.
      그래서 ch05 유도의 두 줄이 조용히 안 옮겨졌다(`\dot{V}=VA_c` 가 그대로 남았다).
      → 글자 **덩어리**를 보고 판정한다: 덩어리가 `KE`·`HV` 같은 **한 낱말**이면 건너뛰고,
        아니면 그 안의 낱글자는 각각 기호다(`VA` = V·A).
    ★ 매크로 인자(`\mathrm{kV}`·`\text{...}`·`\dot{V}`)는 통째로 가린다 — 거기 V 는 이름이다.
    ★ 결합 점(`V̇`)이 붙은 것은 **체적유량**이라 손대지 않는다. 실제로 한 번 바꿔 놓고
      `\mathcal{V}̇` 라는 없는 표기를 만들었다(같은 날 되돌렸다).
    """
    holes = []

    def hide(m):
        holes.append(m.group(0))
        return "\x01%d\x01" % (len(holes) - 1)

    # ★★ **삽화에서는 `<text>` 안만 본다** (2026-08-12 — `--show` 가 아니었으면 못 봤다).
    #   SVG path 의 `V` 는 **수직선 명령**이다(`M112 124V208`). 그것을 기호로 세면 도형이
    #   통째로 망가진다. `_BARE_ELL` 이 상대 lineto `l` 때문에 이미 같은 처방을 쓰고 있다.
    if "<svg" in text or "<path" in text:
        return _SVG_TEXT.sub(lambda m: m.group(1) + _mark_bare(m.group(2), sym, mark, compounds)
                             + m.group(3), text)
    text = _OPAQUE.sub(hide, text)
    out, at = [], 0
    for m in _LETTERS.finditer(text):
        run = m.group(0)
        if sym not in run or (len(run) > 1 and run in compounds):
            continue
        # 영어 낱말은 기호의 곱이 아니다 — `Throttling Valves`(출처 문구)가 실제로 걸렸다.
        # 기호 곱은 `VA`·`dV` 처럼 짧고 소문자가 하나뿐이다.
        if sum(1 for ch in run if ch.islower()) >= 2:
            continue
        for i, ch in enumerate(run):
            if ch != sym:
                continue
            pos = m.start() + i
            if text[pos + 1:pos + 2] == COMBINING_DOT:
                continue
            out.append(text[at:pos])
            out.append(mark)
            at = pos + 1
    out.append(text[at:])
    text = "".join(out)
    for i, raw in enumerate(holes):
        text = text.replace("\x01%d\x01" % i, raw)
    return text


# renderMath 가 **필드 전체**를 그리는 자리. 그 밖은 산문이라 인라인 수식 안에서만 그린다.
MATH_FIELDS = {"latex", "equations", "solutionTemplate"}


def swap(text, pairs, mode):
    """`pairs` = [(옛 표기, 새 표기)]. `mode` = 'math'·'prose'·'svg'. 순수 함수.

    ★★ **표기를 정하는 것은 「어느 필드인가」다** (2026-08-12 — 실측으로 열림).
      · `latex`·`equations`·`solutionTemplate` → renderMath 가 통째로 그린다 → **매크로**
      · 그 밖의 산문 → 인라인 수식 `\\(…\\)` **안에서만** 그린다 → 밖은 **글리프**
      · `svg` → renderMath 가 아예 안 돈다 → **글리프**(`ℓ`·`ρ` 가 이미 그렇게 들어가 있다)
      처음에는 `\\(` 가 있는지로만 갈랐다. 그래서 인라인 수식이 **하나도 없는 산문**이
      수식 취급을 받아 화면에 `\\mathcal{V}` 가 글자로 남았다 — 브라우저 실측 6곳
      (유도 단계 설명 `sttext` · 가정 칩 `ftag` · 문항 지문 `prompt` · 정답 `q-ans-val`).
    """
    if not isinstance(text, str) or not pairs:
        return text
    if mode == "math":
        return _swap_one(text, pairs, False)
    if mode == "svg":
        return _swap_one(text, pairs, True)
    out, at = [], 0
    for m in _MATH_SPAN.finditer(text):
        out.append(_swap_one(text[at:m.start()], pairs, True))        # 산문 → 글리프
        out.append("\\(" + _swap_one(m.group(1), pairs, False) + "\\)")
        at = m.end()
    out.append(_swap_one(text[at:], pairs, True))
    return "".join(out)


def _swap_one(text, pairs, as_glyph):
    """한 구간을 **동시에** 바꾼다 — 순차 치환은 서로를 먹는다.

    `as_glyph` 가 참이면 새 표기를 글리프로 넣는다(산문·삽화). 거짓이면 매크로 이름(수식).
    """
    if not text:
        return text
    marks = {}
    # 매크로 표기(`\mathcal{V}`)를 **먼저** 자리표로 뺀다 — 안 그러면 그 안의 맨 V 가 먼저 걸린다.
    for i, (old, new) in enumerate(sorted(pairs, key=lambda p: not p[0].startswith("\\"))):
        mark = HOLD + str(i) + HOLD
        marks[mark] = GLYPH.get(new, new) if as_glyph else new
        if old.startswith("\\"):
            # 옛 표기도 두 모양으로 들어와 있을 수 있다 — 매크로와 글리프 둘 다 걷는다.
            text = text.replace(old, mark)
            if old in GLYPH:
                text = text.replace(GLYPH[old], mark)
        else:
            text = _mark_bare(text, old, mark, COMPOUNDS)
    for mark, new in marks.items():
        text = text.replace(mark, new)
    return text


def _contexts(hits, span=26, limit=6):
    """걸린 자리를 앞뒤 문맥과 함께. **판정을 한 화면에서 하게 하는 것**이 목적이다 —
    항목마다 원문을 열어 읽으면 24항목에 24번 읽어야 한다.
    문자열 목록을 받는다(이어 붙인 덩어리를 받으면 삽화 판정이 통째로 걸린다)."""
    out = []
    for s in hits:
        marked = _mark_bare(s, "V", "\x02", COMPOUNDS)
        at = 0
        while len(out) < limit:
            i = marked.find("\x02", at)
            if i < 0:
                break
            piece = marked[max(0, i - span):i + span + 1].replace("\n", " ")
            out.append(piece.replace("\x02", "«V»"))
            at = i + 1
        if len(out) >= limit:
            break
    return out


def strings_of(node, out=None):
    """그 항목 안의 문자열 전부.

    직렬화 함수로 뭉쳐서 훑고 싶지만 **그 이름을 이 파일에 쓸 수 없다** —
    `test_json_rewrite_preserves_formatting` 은 파일 본문에 그 글자가 있으면
    *통째 재작성 도구*로 판정한다(문자열 검사라 쓰임새를 못 가린다).
    직접 모으는 편이 어차피 더 정확하다 — 이스케이프가 낀 표기를 안 만든다.
    """
    if out is None:
        out = []
    if isinstance(node, dict):
        for v in node.values():
            strings_of(v, out)
    elif isinstance(node, list):
        for v in node:
            strings_of(v, out)
    elif isinstance(node, str):
        out.append(node)
    return out


# 옮기지 않는 필드 — **인용과 출처**다. `changeNote` 는 사용자 지적을 그대로 옮겨 적는
# 리뷰 메타라(AGENTS: 원문 보존) 표기를 고치면 남의 말을 고쳐 쓰는 것이 된다.
SKIP_KEYS = {"changeNote", "rationale", "sourceRef"}


def walk(node, pairs, key=None):
    """(고친 노드, 바꾼 문자열 수)."""
    mode = "svg" if key == "svg" else ("math" if key in MATH_FIELDS else "prose")
    if isinstance(node, dict):
        n = 0
        for k, v in node.items():
            if k in SKIP_KEYS:
                continue
            node[k], c = walk(v, pairs, k)
            n += c
        return node, n
    if isinstance(node, list):
        n = 0
        for i, v in enumerate(node):
            node[i], c = walk(v, pairs, key)
            n += c
        return node, n
    if isinstance(node, str):
        new = swap(node, pairs, mode)
        return new, (1 if new != node else 0)
    return node, 0


# ★★ `--split` — **한 항목 안에서 갈린 자리만** 옮긴다 (신설 2026-08-12).
#
#   사용자가 검수하며 같은 부류를 여섯 번 짚었다(문풀 `ke = V²/2` · 유도 4번 · 5.4·5.5 삽화).
#   원인은 이 도구의 자가 **선언한 자리만** 봤기 때문이다 — 문풀·힌트·삽화 라벨·칩에는 선언이
#   없어 통째로 건너뛰었다. 판정은 검사와 **같은 함수**(`symbol_split_hits`)가 한다:
#   *같은 꼬리를 가진 토큰이 선언 표기와 맨 글자 두 가지로 한 항목에 함께 있는가.*
#
#   ★ **꼬리까지 맞는 자리만 바꾼다.** 밑기호만 보고 옮기면 같은 글자를 쓰는 다른 물리량
#     (`\int P\,dV` 의 부피)까지 바뀐다 — 회차 4에서 SVG path 의 `V` 를 옮길 뻔한 그 부류다.
#   ★ **삽화는 `<text>` 안만.** path 데이터의 `V` 는 수직선 명령이라 바꾸면 그림이 깨진다.
_SPLIT_GUARD = r"(?<![A-Za-z\\{])"


def _sub_split(text, bare, tail, good, symbols=None, glyphs=None):
    """꼬리까지 일치하는 자리만 치환. (새 글, 바꾼 수).

    ★ **선언된 표기를 가린 판에서 찾는다** — 검사와 같은 함수(`symbol_masked`)를 쓴다.
      안 가리면 `\\dot{V}`(체적유량) 안의 `V` 까지 잡아 **뜻이 다른 기호를 망가뜨린다.**
    ★ 치환문은 **함수로 준다** — `\\mathcal{V}` 의 백슬래시를 re 가 이스케이프로 읽어
      `bad escape \\m` 으로 죽는다(실측 2026-08-12).
    """
    masked = symbol_masked(text, symbols or {}, glyphs or {})
    pattern = re.compile(r"(?<![A-Za-z])" + re.escape(bare + tail) + r"(?![A-Za-z])")
    pieces, at, count = [], 0, 0
    for hit in pattern.finditer(masked):
        pieces.append(text[at:hit.start()])
        pieces.append(good + tail)
        at, count = hit.end(), count + 1
    pieces.append(text[at:])
    return "".join(pieces), count


def apply_split(node, bare, tail, macro, glyph, key=None, table=None):
    """(고친 노드, 바꾼 문자열 수). 수식 필드는 매크로, 산문·삽화는 글리프."""
    symbols, glyphs = (table or ({}, {}))
    if isinstance(node, dict):
        total = 0
        for k in list(node):
            if k in SKIP_KEYS:
                continue
            node[k], count = apply_split(node[k], bare, tail, macro, glyph, k, table)
            total += count
        return node, total
    if isinstance(node, list):
        total = 0
        for i, val in enumerate(node):
            node[i], count = apply_split(val, bare, tail, macro, glyph, key, table)
            total += count
        return node, total
    if not isinstance(node, str):
        return node, 0
    if key == "svg":
        seen = [0]

        def one(match):
            body, count = _sub_split(match.group(2), bare, tail, glyph, symbols, glyphs)
            seen[0] += count
            return match.group(1) + body + match.group(3)

        return re.sub(r"(<text\b[^>]*>)(.*?)(</text>)", one, node, flags=re.S), seen[0]
    good = macro if key in MATH_FIELDS else glyph
    return _sub_split(node, bare, tail, good, symbols, glyphs)


def run_split(names, symbols, glyphs, apply_it, not_roles=()):
    """갈린 자리를 항목마다 옮긴다. `variables` 의 **키**는 구조라 `[사람]` 으로 낸다."""
    moved, manual = 0, 0
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        print("\n=== %s ===" % name)
        renames = {}
        for kind, item in _iter_check_owners(data):
            before_issues = symbol_role_word_issues(item, symbols, not_roles, glyphs)
            for bad, good, role in symbol_split_hits(item, symbols, glyphs):
                bare = _symbol_base(bad)
                tail = bad[len(bare):]
                macro = symbols[role]
                # 글리프는 **과목이 선언한 표**를 쓴다(공통 코드가 과목 사실을 알면 안 된다).
                glyph = (glyphs or {}).get(macro, macro)
                # ★★ **처방이 자를 어기면 되돌린다** (열린 날 2026-08-12, 첫 실행에서 바로 났다).
                #   ch02 기호 안내 절은 *글자 자체를 이야기하는* 자리라 `교재는 부피와 속도에
                #   같은 글자 V 를 쓰지만…` 의 `V` 가 전부 부피다. 갈림 규칙만 보면 그 절도
                #   '두 표기가 함께 있다' 라서 걸리고, 실제로 **부피를 필기체로 바꿔 버렸다.**
                #   빌드의 C45(역할 낱말 옆 기호)가 곧바로 신고했다 — 즉 **자는 이미 답을 알고
                #   있었다.** 그래서 고친 뒤 같은 자로 다시 재고, 없던 신고가 생기면 되돌린다.
                keep = copy.deepcopy(item)
                _, count = apply_split(item, bare, tail, macro, glyph,
                                       table=(symbols, glyphs or {}))
                after = symbol_role_word_issues(item, symbols, not_roles, glyphs)
                if len(after) > len(before_issues):
                    item.clear()
                    item.update(keep)
                    print("  [되돌림] %-9s %-24s %s — 고치면 자가 신고한다(%s)"
                          % (kind, str(item.get("id"))[:24], bad, after[-1][:60]))
                    continue
                keys = [k for k in ((item.get("variables") or {}) if kind == "formula" else {})
                        if bad in str(k)]
                moved += count
                manual += len(keys)
                print("  %-9s %-28s %s → %s  (문자열 %d)"
                      % (kind, str(item.get("id"))[:28], bad, good, count))
                for k in keys:
                    # ★ 키는 **구조**라 값 치환으로 못 바꾼다 — `rename_keys` 가 카드 범위 안에서
                    #   줄 단위로 바꾼다(회차 3에 만든 그 경로를 그대로 쓴다).
                    renames.setdefault(str(item.get("id")), {})[k] = k.replace(bad, good)
                    print("     [키] variables — %s → %s" % (k, k.replace(bad, good)))
        if not apply_it:
            continue
        with open(path, encoding="utf-8") as fh:
            before = json.load(fh)
        status, why = write_chapter(path, before, data)
        print("  [%s] %s" % (status, why or os.path.relpath(path, audit_content.ROOT)))
        if not renames:
            continue
        with open(path, encoding="utf-8") as fh:
            original = fh.read()
        text, why = rename_keys(original, card_spans(original, list(renames)), renames)
        if text is None:
            print("  [키 안 씀] %s" % why)
            continue
        try:
            json.loads(text)                      # 재파싱 검증 — 깨진 JSON 을 쓰지 않는다
        except ValueError as exc:
            print("  [키 안 씀] 갈아끼운 결과가 JSON 이 아니다 — %s" % exc)
            continue
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print("  [키 written] %d카드" % len(renames))
    print("\n옮긴 문자열 %d · 사람이 볼 키 %d%s"
          % (moved, manual, "" if apply_it else "  (미리보기 — --apply 로 반영)"))
    return 0


def rename_keys(original, spans, renames):
    """`variables` 의 **키**를 카드 범위 안에서만 갈아끼운다. (새 본문, 사유).

    ★ 왜 `write_chapter` 로 못 하나 — 그쪽은 **문자열 값** 치환만 표기 보존으로 할 수 있다.
      키를 바꾸는 것은 구조 변경이라 거기서는 `ValueError` 다. 그래서 값은 그쪽에 맡기고
      키만 여기서 줄 단위로 바꾼다(`set_derivation_kind.py` 와 같은 처방).
    ★ 카드 범위로 가둔다 — `"V":` 는 여러 카드에 있고, 어느 카드의 V 를 옮길지는
      그 카드의 선언이 정한다. 범위를 안 가두면 남의 카드까지 바뀐다.
    """
    lines = original.split("\n")
    for fid, pairs in renames.items():
        lo, hi = spans.get(fid, (None, None))
        if lo is None:
            return None, "카드 범위를 못 찾았다: " + str(fid)
        for old, new in pairs.items():
            hit = [i for i in range(lo, hi)
                   if lines[i].lstrip().startswith(_lit(old) + ":")]
            if len(hit) != 1:
                return None, "키 줄을 하나로 특정하지 못했다(%d개): %s / %s" % (len(hit), fid, old)
            lines[hit[0]] = lines[hit[0]].replace(_lit(old) + ":", _lit(new) + ":", 1)
    return "\n".join(lines), None


_ENC = json.JSONEncoder(ensure_ascii=False)


def _lit(text):
    """JSON 문자열 리터럴. 인코더 객체를 쓰는 이유는 `strings_of` 독스트링에 적어 두었다."""
    return _ENC.encode(text)


def card_spans(original, ids):
    """{id: (시작 줄, 끝 줄)} — `"id": "<fid>",` 줄부터 다음 카드의 그 줄 앞까지."""
    lines = original.split("\n")
    at = {}
    for fid in ids:
        hit = [i for i, ln in enumerate(lines)
               if re.match(r'^\s*"id": ' + re.escape(_lit(fid)) + r',\s*$', ln)]
        if len(hit) == 1:
            at[fid] = hit[0]
    order = sorted(at.values())
    out = {}
    for fid, i in at.items():
        nxt = next((j for j in order if j > i), len(lines))
        out[fid] = (i, nxt)
    return out


def main():
    ap = argparse.ArgumentParser(description="선언한 뜻대로 기호를 옮긴다")
    ap.add_argument("--chapter", help="chNN.json 하나만")
    ap.add_argument("--items", default="",
                    help="선언이 없는 항목(이론 절·문풀·문항)의 id 를 쉼표로 — "
                         "그 항목 안의 맨 기호를 --role 로 본다. **판정은 사람이 한다**")
    ap.add_argument("--role", default="속도", help="--items 항목에서 맨 기호가 뜻하는 것")
    ap.add_argument("--normalize", action="store_true",
                    help="뜻은 그대로 두고 **표기 형태만** 자리에 맞게 고친다 "
                         "(수식 필드는 매크로 · 산문과 삽화는 글리프). 판정을 하지 않는다")
    ap.add_argument("--show", action="store_true", help="판정할 자리를 문맥과 함께 보여 준다")
    ap.add_argument("--split", action="store_true",
                    help="**한 항목 안에서 갈린 자리**만 옮긴다 — 저자가 같은 자리에 두 표기를 "
                         "적어 두었으므로 기계가 문맥을 추측할 필요가 없다(C46 과 같은 함수)")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    global COMPOUNDS
    probe = os.path.join(audit_content.DATA, "")
    symbols = _terms_raw(probe, "symbols") or {}
    not_roles = set(_terms_list(probe, "symbolNotRoles"))
    COMPOUNDS = frozenset(_terms_list(probe, "symbolCompounds"))
    if not symbols:
        # ★ **선언이 곧 opt-in 이다 — 대상이 아닌 과목은 「해당 없음」이지 오류가 아니다**
        #   (열린 날 2026-08-12, 동역학 세션 보고: [사용자 발화 인용 생략]).
        #   여기서 exit 1 을 내면 배치 스크립트와 사람 둘 다 *실패했다* 로 읽는다.
        #   선언은 「기호 v 가 무슨 뜻인가」라는 **사람의 판정**이라 이 도구가 대신할 수 없고,
        #   판정 전까지는 옮길 것이 없는 것이 정상이다.
        # ※ 안내 문구에 **과목 이름을 적지 않는다** — 공통 도구가 한 과목을 아는 순간
        #   이 리포가 네 번 겪은 그 부류가 된다(회귀 `test_tools_do_not_hardcode_a_subject`
        #   가 실제로 이 줄을 잡았다: 처음엔 예시 경로에 과목 폴더를 적었다).
        print("[해당 없음] 이 과목은 `terms.json` 에 `symbols` 를 선언하지 않았다 —"
              " 옮길 기준이 없어 0건으로 끝낸다. 선언하면 그때부터 이 도구가 돈다"
              " (형식은 `data/<과목>/terms.json` 의 `symbols`·`symbolNotRoles`).")
        return 0
    print("규격(terms.json): " + " · ".join("%s=%s" % kv for kv in symbols.items()))

    names = ([args.chapter] if args.chapter else [n + ".json" for n in audit_content.CHAPTERS])
    if args.split:
        return run_split(names, symbols, _terms_raw(probe, "symbolGlyphs") or {},
                         args.apply, not_roles)
    total, manual = 0, 0
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        before = copy.deepcopy(data)
        moved, renames = 0, {}
        if args.normalize:
            # 뜻은 안 건드린다 — 같은 기호를 **그 자리에 맞는 형태**로 다시 쓸 뿐이다.
            # (`\mathcal{V}` 가 산문에 글자로 남아 있던 것을 걷어내는 경로다. 멱등이다.)
            _, n = walk(data, [(sym, sym) for sym in GLYPH])
            moved += n
            if n:
                print("  %-12s 표기 형태 정규화 — 문자열 %d" % (name, n))
        for f in ((data.get("derivation") or {}).get("formulas") or []):
            roles = card_roles(f.get("variables"), symbols, not_roles)
            pairs = [(base, symbols[role]) for base, role in roles.items()
                     if base != _symbol_base(symbols[role])]
            if not pairs:
                continue
            # 키는 **구조**라 값과 따로 다룬다(아래 rename_keys). 여기서는 무엇을 바꿀지만 모은다.
            # variables 의 **키**는 뷰어가 renderMath 로 그린다 → 매크로다.
            keymap = {k: swap(k, pairs, "math") for k in (f.get("variables") or {})}
            keymap = {k: v for k, v in keymap.items() if k != v}
            if keymap:
                renames[f.get("id")] = keymap
            _, n = walk(f, pairs)
            moved += n
            print("  %-12s %-30s %s  (값 %d · 키 %d)"
                  % (name, f.get("id"), " · ".join("%s→%s" % p for p in pairs), n, len(keymap)))
        # 선언이 없는 자리 — 사람이 `--items` 로 판정을 넘긴 것만 옮기고, 나머지는 알려만 준다.
        # ★ 쓰기는 **아래 한 번**이다. 카드 pass 뒤에 따로 쓰면 두 번째 write_chapter 가
        #   [사용자 발화 인용 생략] 로 거부한다(before 스냅샷이 낡는다).
        want = {s.strip() for s in args.items.split(",") if s.strip()}
        if args.role not in symbols:
            sys.exit("`terms.json` 의 symbols 에 없는 역할이다: " + args.role)
        # ★ 유도 카드도 여기 넣는다 — 선언은 이미 옮겼는데 **식에 옛 기호가 남는** 자리가
        #   실제로 있었다(ch05 `mass-flow-rate` 의 `\dot{V}=VA_c` 두 줄). 선언이 맞아
        #   pairs 가 비면 위 pass 가 그 카드를 통째로 건너뛰기 때문이다.
        # ★ `theory`·`derivation` 은 **한 겹 더 들어가 있다**(`{"sections": …}`·`{"formulas": …}`).
        #   처음에 `data["theory"]` 로 읽었더니 이론 절이 통째로 순회 밖이었고, 출력이
        #   [사용자 발화 인용 생략] 이라 **없는 것처럼 보였다** — AGENTS 규칙 11 이 경고하는 그 모양이다.
        collections = {"theory": (data.get("theory") or {}).get("sections") or [],
                       "practice": data.get("practice") or [],
                       "problems": data.get("problems") or [],
                       "유도": (data.get("derivation") or {}).get("formulas") or []}
        for coll, items in collections.items():
            for item in items:
                # ★ **문자열마다 따로 본다.** 한 덩어리로 이어 붙이면 그 안에 `<svg` 가
                #   하나라도 있는 순간 항목 전체가 삽화 취급이 되어 산문의 V 가 안 보인다
                #   (실측: ch05 `sec-steady-energy` 가 목록에서 통째로 빠졌다).
                # 찾는 자와 옮기는 자를 **같은 함수로** 쓴다 — 한때 찾기만 옛 정규식이라
                # `VA_c` 가 목록에도 안 뜨고 옮겨지지도 않았다(ch05 실측).
                hits = [s for s in strings_of(item)
                        if _mark_bare(s, "V", "\x02", COMPOUNDS) != s]
                if not hits:
                    continue
                blob = "\n".join(hits)
                if str(item.get("id")) in want:
                    _, n = walk(item, [("V", symbols[args.role])])
                    moved += n
                    print("  %-12s %-9s %-24s V→%s  (문자열 %d)"
                          % (name, coll, item.get("id"), symbols[args.role], n))
                else:
                    manual += 1
                    print("  [사람] %-12s %-9s %s" % (name, coll, str(item.get("id"))))
                    if args.show:
                        for snip in _contexts(hits):
                            print("         · " + snip)

        total += moved
        if moved and args.apply:
            state, why = write_chapter(path, before, data)
            print("  [%s] %s" % (state, why or name))
            if state == "written" and renames:
                with open(path, encoding="utf-8", newline="") as fh:
                    raw = fh.read()
                text, why = rename_keys(raw, card_spans(raw, renames), renames)
                if why:
                    print("  [키 안 씀] " + why)
                else:
                    with open(path, "w", encoding="utf-8", newline="") as fh:
                        fh.write(text)
                    print("  [키 written] %d카드" % len(renames))
    print("\n카드 안 %d문자열 · 사람이 볼 항목 %d개%s"
          % (total, manual, "" if args.apply else "  (미리보기 — --apply 로 반영)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
