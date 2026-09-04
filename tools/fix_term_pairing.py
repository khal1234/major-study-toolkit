# -*- coding: utf-8 -*-
r"""선언한 용어의 **이론 본문 첫 등장**에 원어를 병기한다 (C41 의 처방).

    python tools/fix_term_pairing.py                        # 무엇을 바꿀지만 보여준다
    python tools/fix_term_pairing.py --chapter=ch14.json --apply

왜 도구인가 (신설 2026-08-07) — 사용자 지적:
*"열역학은 잘 지키는데 너는 잘 안지키네. 시스템으로 안올라왔나?
구심력 원심력 이런 단어들 옆에 영어 병기가 필요해"*

★ **손으로 채우면 다음 챕터에서 또 끊긴다.** 실제로 그렇게 끊겼다 — 열역학이 지켜 온 것은
  규칙이 아니라 습관이었고, 동역학 ch14 는 병기가 **0건**으로 만들어졌다. 챕터를 새로 쓸 때마다
  같은 일이 반복되므로 검사(C41)와 처방(이 도구)을 함께 둔다.
★ **목록은 과목이 갖는다** — `data/<과목>/terms.json`. 이 파일에는 용어가 하나도 없다
  (AGENTS 「공통 도구에 과목별 사실을 박지 않는다」).
★ 판정은 `checks_content.term_pairing_issues` 와 **같은 함수**를 쓴다. 자와 처방이 갈리면
  감사는 0건인데 화면은 그대로인 상태가 만들어진다.

**넣는 자리는 첫 등장 바로 뒤 하나뿐이다.** 굵게(`**용어**`) 안이면 굵게 안쪽에 넣는다 —
`**용어**(English)` 로 두면 강조가 용어에서 끊겨 보인다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from audit_conventions import chapters                                 # noqa: E402
from buildlib.checks_content import (                                  # noqa: E402
    MATH_LABEL_EXEMPT_KEYS, TERM_SEARCH_EXEMPT_KEYS,
    subject_terms, term_pairing_issues, _is_hangul,
)

# ★ 검사가 **읽지 않는 자리**에 넣으면 신고가 그대로 남는다 (첫 실행에서 8건이 그랬다).
#   출처(`sourceRef`)·삽화 SVG 에도 용어가 들어 있어서, 건너뛸 키를 손으로 적었더니
#   검사와 갈라졌다. 그래서 **검사가 쓰는 집합을 그대로 가져온다** — 자와 처방은 한 벌이다.
SKIP_KEYS = MATH_LABEL_EXEMPT_KEYS | TERM_SEARCH_EXEMPT_KEYS
from buildlib.jsontext import write_chapter                            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def missing_terms(chapter, terms):
    """C41 이 신고한 용어들만 뽑는다 — 자와 처방이 같은 판정을 쓴다."""
    out = []
    for issue in term_pairing_issues(chapter, terms):
        ko = issue.split("'")[1]
        out.append((ko, terms[ko]))
    return out


def pair_first(text, ko, en):
    """`text` 안 첫 등장(낱말 조각 제외) 뒤에 `(en)` 을 넣는다. 못 넣으면 None."""
    i = -1
    while True:
        i = text.find(ko, i + 1)
        if i < 0:
            return None
        if not _is_hangul(text[i - 1:i]):
            break
    j = i + len(ko)
    if text[j:j + 2] == "**":              # `**용어**` — 굵게 **안쪽**에 넣는다
        return text[:j] + "(" + en + ")" + text[j:]
    return text[:j] + "(" + en + ")" + text[j:]


def rewrite(node, wanted, done, key=None):
    """이론 본문을 문서 순서대로 돌며 **처음 만난 자리 한 곳**에만 넣는다."""
    if isinstance(node, dict):
        return dict((k, node[k] if k in SKIP_KEYS
                     else rewrite(node[k], wanted, done, k)) for k in node)
    if isinstance(node, list):
        return [rewrite(v, wanted, done, key) for v in node]
    if isinstance(node, str):
        out = node
        for ko, en in wanted:
            if ko in done:
                continue
            fixed = pair_first(out, ko, en)
            if fixed is not None:
                out, _ = fixed, done.add(ko)
        return out
    return node


def main():
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    apply_ = "--apply" in sys.argv
    total = 0
    for subject, name, chapter in chapters():
        if only and name != only and name != os.path.splitext(only)[0]:
            continue
        path = os.path.join(DATA, subject,
                            name if name.endswith(".json") else name + ".json")
        terms = subject_terms(path)
        wanted = missing_terms(chapter, terms)
        if not wanted:
            continue
        done = set()
        fixed = dict(chapter)
        fixed["theory"] = rewrite(chapter.get("theory") or {}, wanted, done)
        print("=== %s %s — %d개 ===" % (subject, name, len(done)))
        for ko, en in wanted:
            print("   ", ("[넣음] " if ko in done else "[못 찾음] ") + ko + "(" + en + ")")
        total += len(done)
        if apply_ and done:
            write_chapter(path, chapter, fixed)
            print("  [written]", os.path.relpath(path, ROOT))
    print("\n합계 %d개%s" % (total, "" if apply_ else " (--apply 를 붙여야 쓴다)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
