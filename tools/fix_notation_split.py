# -*- coding: utf-8 -*-
r"""같은 식이 **어디는 인라인 수식, 어디는 평문**인 자리를 수식 쪽으로 통일한다.

    python tools/fix_notation_split.py                       # 무엇을 바꿀지만 보여준다
    python tools/fix_notation_split.py --chapter=ch12.json --apply

왜 도구인가 (신설 2026-08-02, 동역학 ch12 에서 열림) — 사용자 지적:
*[발화 생략]*

★ **채팅에서는 두 표기가 똑같아 보인다.** 갈라지는 것은 화면이다 — 한쪽은 수식으로 조판되고
  다른 쪽은 본문 글꼴 그대로다. 그래서 사람이 눈으로 훑어 전수를 세는 것이 불가능하고,
  손으로 고치면 16곳 중 한둘이 반드시 남는다(그 남은 하나가 다음 지적이 된다).

★ **정본은 도구가 아니라 데이터가 갖는다.** 바꿔 넣을 LaTeX 는 *그 챕터가 이미 수식으로 쓴 형태*를
  그대로 쓴다. 그래서 이 도구에는 과목·기호 목록이 하나도 없다(AGENTS 「공통 도구에 과목별 사실을
  박지 않는다」). 판정도 `audit_conventions.audit_notation_split` 하나를 부른다 —
  자와 처방이 갈리면 감사는 0건인데 화면은 그대로인 상태가 만들어진다.

**포맷을 건드리지 않는다는 것은 기계가 보증한다** — 바뀐 문자열 값만 리터럴 단위로 갈아끼우고,
쓴 내용을 다시 파싱해 의도한 것과 같은지 본다(`buildlib/jsontext.py`).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from audit_conventions import (                                        # noqa: E402
    chapters, walk_text_fields, audit_notation_split, notation_field, standalone_at,
)
from buildlib.checks_content import (                                 # noqa: E402
    mask_inline_math, merge_split_inline_subscripts, normalize_unicode_partial_fractions,
)
from buildlib.jsontext import write_chapter                            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def replace_outside_math(text, plain, latex):
    """`plain` 을 `\\(latex\\)` 로 — 단 **이미 수식 안**인 자리는 건드리지 않는다."""
    masked = mask_inline_math(text)          # 길이를 보존하므로 좌표를 그대로 쓸 수 있다
    out, i, n = [], 0, 0
    while True:
        j = masked.find(plain, i)
        if j < 0:
            break
        if not standalone_at(masked, j, j + len(plain)):
            out.append(text[i:j + len(plain)])   # 더 긴 식의 조각이다 — 그대로 둔다
            i = j + len(plain)
            continue
        out.append(text[i:j])
        out.append("\\(" + latex + "\\)")
        i, n = j + len(plain), n + 1
    out.append(text[i:])
    return "".join(out), n


def rewrite(node, path, rules, log):
    """트리를 돌며 문자열을 고친 사본을 돌려준다."""
    if isinstance(node, dict):
        return {k: rewrite(v, path + "/" + str(k), rules, log) for k, v in node.items()}
    if isinstance(node, list):
        return [rewrite(v, path + "[" + str(i) + "]", rules, log)
                for i, v in enumerate(node)]
    if not isinstance(node, str) or not notation_field(path):
        return node
    text = merge_split_inline_subscripts(node)
    if text != node:
        log.append((path, "수식 밖 첨자", 1))
    normalized = normalize_unicode_partial_fractions(text)
    if normalized != text:
        log.append((path, "유니코드 편미분 슬래시", 1))
        text = normalized
    for plain, latex in rules:
        text, hit = replace_outside_math(text, plain, latex)
        if hit:
            log.append((path, plain, hit))
    return text


def main():
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    apply_it = "--apply" in sys.argv
    only_stem = os.path.splitext(only)[0] if only else None
    total = 0

    for subject, ch, chapter in chapters(only_stem):
        found = audit_notation_split(walk_text_fields(chapter))
        rules = [(plain, latex) for plain, latex, _w, _hits in found]
        log = []
        fixed = rewrite(chapter, "", rules, log)
        if not rules and not log:
            continue
        print("\n=== %s %s ===" % (subject, ch))
        for plain, latex, where_math, _hits in found:
            print("  %r → \\(%s\\)   (정본: %s)" % (plain, latex, where_math))
        for path, plain, hit in log:
            total += hit
            print("    %-64s %d곳" % (path, hit))
        if not apply_it:
            continue

        # ★ 표기는 한 글자도 안 움직인다 — 바뀐 문자열 값만 리터럴 단위로 갈아끼우고
        #   다시 파싱해 검증한다(`buildlib/jsontext.py` 가 정본).
        ch_path = os.path.join(DATA, subject, ch + ".json")
        status, why = write_chapter(ch_path, chapter, fixed)
        if status == "written":
            print("  [기록] %s" % os.path.relpath(ch_path, ROOT))
        elif status == "nochange":
            print("  [그대로] 바꿀 것이 없다")
        else:
            print("  [중단] 표기를 보존한 채로는 못 쓴다 — %s" % why)

    print("\n합계 %d곳%s" % (total, "" if apply_it else "  (--apply 로 기록)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
