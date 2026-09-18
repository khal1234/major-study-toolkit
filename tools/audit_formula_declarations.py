# -*- coding: utf-8 -*-
"""**문항이 쓰는 식을 선언했나** — 문항 쪽에서 센다 (열린 날 2026-09-09).

    python tools/audit_formula_declarations.py                # 전 과목 (지금 학기 먼저)
    python tools/audit_formula_declarations.py --only=<과목>  # 한 과목만
    python tools/audit_formula_declarations.py --fail-only    # 게이트에 걸리는 것만

★ **왜 열렸나 — 짝이 되는 자가 반대쪽만 보고 있었다.**
  `audit_chain_selfsufficiency.py` 는 **카드 쪽**에서 센다: 「이 카드를 아무 문항도 안
  가리킨다」. 그래서 **한 카드라도 가리켜지면 그 장은 조용해진다.** 유체역학이 그 사각지대에
  그대로 들어갔다 — 아홉 장 전체에서 `relatedFormulas` 를 적는 것은 **문풀뿐이고 연습문제는
  한 건도 없는데**, 문풀이 몇 개를 가리켜 준 덕에 카드 쪽 자는 한 건만 신고했다
  (`data/유체역학/안-쓰이는-유도카드-판정.md` 가 그 사실을 적어 두고 이 자를 요청했다).

  ☞ **한 축만 재면 「0건」이 「다 됐다」로 읽힌다.** 이 자는 문항 쪽에서 같은 사슬을 잰다.

## 두 가지를 센다

⑴ **이름을 부르고도 선언 안 한 문항** — 문항의 글(`sourceRef`·풀이·답)에 **그 장 카드의
   id 가 글자 그대로** 들어 있는데 `relatedFormulas` 에는 없는 경우. 오탐이 없다 —
   저자가 그 카드를 쓴다고 이미 적어 둔 것이다. **이것이 게이트 후보다.**

⑵ **선언 공백** — 그 장에 유도 카드가 있는데 `problems`(또는 `practice`) 층이 **통째로**
   `relatedFormulas` 를 안 적는 경우. 습관의 문제라 문항 하나하나를 신고하지 않고 **층 단위**로
   센다. 후보이고 판정은 사람이 한다.

## ☐ 이 자가 못 보는 것 (첫 실행 전에 적는다 — 규칙 21)

- **식을 쓰는지 「글을 읽어」 판정하지 않는다.** ⑴ 은 id 가 글자로 나온 것만 본다.
  카드를 쓰면서 이름을 한 번도 안 부른 문항은 못 잡는다 — 그건 사람이 읽어야 한다.
- **⑵ 의 「0 건 아님」이 「제대로 선언했다」는 뜻이 아니다.** 한 층에서 한 문항만 적어도
  그 층은 공백이 아니다. 공백은 **바닥**을 재는 것이지 채움을 재는 것이 아니다.
- **어느 카드를 가리켜야 하는지는 안 알려 준다.** ⑴ 만 그 답을 주고, ⑵ 는 자리만 준다.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import audit_content                                                    # noqa: E402
import audit_chain_selfsufficiency as chain                             # noqa: E402

# 문항이 사는 두 층. 순서가 곧 보고 순서다.
ITEM_LAYERS = ("practice", "problems")

# 카드 id 로 볼 최소 길이 — 너무 짧으면 산문에 우연히 박힌다.
# 실측 근거: 이 리포의 카드 id 는 고체역학의 `f1`~`f5`(2자)가 가장 짧고 나머지는 전부
# `f-05-general-energy` 꼴이다. 2~3자짜리를 글에서 찾으면 「f1 절」·「q3」 같은 자리에
# 걸려 오탐이 쏟아지므로, **글자 검색은 4자 이상 id 에만** 건다.
MIN_ID_LEN_FOR_TEXT_SEARCH = 4


def item_text(item):
    """문항 하나의 글 전부 — 선언(`relatedFormulas`)은 빼고 모은다. 순수 함수.

    선언을 넣으면 「선언했으니 이름을 불렀다」가 되어 ⑴ 이 스스로를 증명한다.
    """
    if not isinstance(item, dict):
        return ""
    parts = []
    for key, value in item.items():
        if key == "relatedFormulas":
            continue
        parts.append(json.dumps(value, ensure_ascii=False))
    return " ".join(parts)


def named_but_undeclared(data):
    """(층, 문항 id, 카드 id) — 글에서 카드 이름을 부르고도 선언 안 한 것. 순수 함수."""
    known = {fid for fid in chain.formula_ids(data)
             if fid and len(fid) >= MIN_ID_LEN_FOR_TEXT_SEARCH}
    out = []
    for layer in ITEM_LAYERS:
        for item in (data.get(layer) or []):
            if not isinstance(item, dict):
                continue
            declared = set(item.get("relatedFormulas") or [])
            text = item_text(item)
            for fid in sorted(known):
                if fid in declared:
                    continue
                if re.search(re.escape(fid) + r"(?![0-9A-Za-z_-])", text):
                    out.append((layer, item.get("id"), fid))
    return out


def layer_gap(data):
    """카드가 있는데 통째로 선언이 없는 층의 이름들. 순수 함수.

    카드가 0 개인 장은 선언할 것이 없으므로 공백이 아니다 — 빈 목록을 돌려준다.
    """
    if not chain.formula_ids(data):
        return []
    gaps = []
    for layer in ITEM_LAYERS:
        items = [i for i in (data.get(layer) or []) if isinstance(i, dict)]
        if not items:
            continue
        if not any(i.get("relatedFormulas") for i in items):
            gaps.append((layer, len(items)))
    return gaps


def main(argv):
    only = None
    fail_only = "--fail-only" in argv
    for a in argv:
        if a.startswith("--only="):
            only = a.split("=", 1)[1]

    dirs = audit_content.subject_dirs()
    if audit_content.reject_unmatched_only(only, dirs):
        return 2
    sem = {os.path.basename(d): chain.subject_semester(d) for d in dirs}
    now = chain.current_semester(audit_content.DATA)

    named, gaps, seen = [], [], 0
    for d in dirs:
        subject = os.path.basename(d)
        if only and only not in subject:
            continue
        for name in sorted(f for f in os.listdir(d)
                           if re.fullmatch(r"ch\d+\.json", f)):
            try:
                with open(os.path.join(d, name), encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                continue
            seen += 1
            ch = name[:-5]
            for layer, qid, fid in named_but_undeclared(data):
                named.append((subject, ch, layer, qid, fid))
            for layer, count in layer_gap(data):
                gaps.append((subject, ch, layer, count))

    if named:
        print("[이름을 부르고도 선언 안 함] 문항의 글에 카드 id 가 있는데 relatedFormulas 에 없다")
        for subject, ch, layer, qid, fid in chain.semester_order(named, sem, now):
            print("   [%s] %s %s · %s %s → %s"
                  % (chain.semester_tag(sem, subject), subject, ch, layer, qid, fid))
    if gaps and not fail_only:
        print("\n[선언 공백] 카드는 있는데 그 층이 **통째로** relatedFormulas 를 안 적는다")
        print("   ※ 습관의 문제라 층 단위로 센다 — 어느 카드를 가리켜야 하는지는 사람이 정한다")
        for subject, ch, layer, count in chain.semester_order(gaps, sem, now):
            print("   [%s] %s %s · %s 층 %d문항"
                  % (chain.semester_tag(sem, subject), subject, ch, layer, count))

    print("\n합계 — 훑은 장 %d개 · 이름 부르고 미선언 %d건 · 선언 공백 층 %d개"
          % (seen, len(named), len(gaps)))
    print("※ 게이트는 「이름을 부르고도 선언 안 함」 하나다 — 선언 공백은 후보이고 판정은 사람이 한다")
    return 1 if named else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
