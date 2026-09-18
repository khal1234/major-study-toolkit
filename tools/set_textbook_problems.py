"""장 JSON 에 교재 추천 문제(`textbookProblems`) 블록을 새로 끼운다.

재는 것: 없다 — **문항 고르기·답·풀이 뼈대는 사람이 쓰고 이 도구는 적는 일만 한다.**
빈 장의 후보는 `audit_convention_drift.py --check=textbook-problems` 가 낸다.

하는 일: 스펙 파일 `{source, note?, items}` 를 C54(`checks_content.textbook_problem_issues`)로
  먼저 재고, 통과하면 장 JSON 의 맨 끝 `}` 바로 앞에 `"textbookProblems"` 키 하나만 붙인다.
  파일을 다시 직렬화하지 않는다 — 포맷을 정규화하면 diff 가 불어난다(`set_practice_prompt_ko.py` 와
  같은 이유). 쓰기 전에 결과를 다시 파싱해 「원래 장 + 이 키 하나」와 같은지 대조한다.
  이미 키가 있는 장은 거부한다(덮어쓰면 사람이 고친 항목이 조용히 사라진다).

못 보는 것: 답이 맞는가(과목 검산기 몫 — 공학수학 2 는 `verify_math2_answer.py`) ·
  `answer`·`outline` 에 교재 문장을 옮겨 적었는가(C54 도 못 본다) · 존댓말(빌드 C23).

쓰는 법:
  python tools/set_textbook_problems.py "data/<과목>/chNN.json" --spec <스펙.json>          (셈만)
  python tools/set_textbook_problems.py "data/<과목>/chNN.json" --spec <스펙.json> --apply
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from buildlib.checks_content import textbook_problem_issues   # noqa: E402

KEY = "textbookProblems"


def appended(text, block):
    """`text`(장 JSON 원문)의 최상위 객체 끝에 `KEY: block` 을 붙인 원문을 낸다."""
    end = text.rstrip().rfind("}")
    body = text[:end].rstrip()
    dumped = json.dumps(block, ensure_ascii=False, indent=2).replace("\n", "\n  ")
    return body + ',\n  "' + KEY + '": ' + dumped + "\n}" + text[end + 1:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chapter")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    with open(a.chapter, encoding="utf-8") as fh:
        text = fh.read()
    with open(a.spec, encoding="utf-8") as fh:
        block = json.load(fh)
    chapter = json.loads(text)
    if KEY in chapter:
        sys.exit(f"{a.chapter}: 이미 {KEY} 가 있다 — 이 도구는 새로 끼우기만 한다")
    issues = textbook_problem_issues({KEY: block})
    if issues:
        sys.exit("C54 에 걸렸다:\n  " + "\n  ".join(issues))

    new_text = appended(text, block)
    want = dict(chapter)
    want[KEY] = block
    if json.loads(new_text) != want:
        sys.exit("결과 JSON 이 「원래 장 + 이 키」와 다르다 — 쓰지 않았다")
    n = len(block["items"])
    if not a.apply:
        print(f"[셈만] {a.chapter}: {KEY} {n}문항을 끼울 수 있다(--apply 로 쓴다)")
        return
    with open(a.chapter, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_text)
    print(f"[씀] {a.chapter}: {KEY} {n}문항")


if __name__ == "__main__":
    main()
