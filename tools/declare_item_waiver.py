# -*- coding: utf-8 -*-
r"""문항 하나에 **사유 있는 검사 면제**를 달아 준다 — 판정은 사람이 하고 이 자는 받아 적는다.

    python tools/declare_item_waiver.py --chapter "data/<과목>/chNN.json" \
        --waive "ch08-p01::표를 여는 것이 이 문항의 훈련이다" \
        --waive "ch11-p02::물성값이라 잰 값이다"
    python tools/declare_item_waiver.py --chapter … --waive … --key <검사이름> --apply

열린 날 2026-09-10. `calculator-free-first-rung` 의 첫 전수 판정에서 후보가 **39건**이었고
그 가운데 여럿이 「자가 못 보는 것」(표 조회·큰 곱셈·로그가 주제인 문항)이었다. 매번 다시
판정하면 목록이 잡음에 덮여 진짜가 안 보이므로(경보 피로), 판정을 **데이터에 남긴다.**

★ **이 자는 판정하지 않는다.** 무엇을 면제할지는 문항을 읽어야 아는 것이라 사람이 준다.
  이 자가 하는 일은 셋뿐이다 — ⑴ 그 문항이 실재하는지 확인 ⑵ 이미 면제가 있으면 건드리지
  않고 알린다 ⑶ **텍스트 삽입**으로 한 줄만 넣는다.

★ **다시 직렬화하지 않는다** (`bind_section.py` 와 같은 규율 — `declare_check_waiver.py` 가
  한 줄 넣으려다 354줄을 흔든 선례가 있다). `"id": "<그 id>",` 줄을 찾아 그 다음 줄에 같은
  들여쓰기로 `"lintWaivers": {…},` 한 줄을 끼운다.

☐ **이 자가 못 보는 것:** 사유가 옳은지. 빈 사유는 거부하지만, 「그냥 두자」는 뜻의 사유를
  적어도 통과한다 — 면제는 사람이 읽으라고 남기는 것이지 기계가 판정하는 것이 아니다.
  이미 `lintWaivers` 가 있는 문항은 **손으로** 합친다(키가 여럿인 경우를 텍스트 삽입으로
  다루면 따옴표 하나에 파일이 깨진다).
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

COLLECTIONS = ("practice", "problems")


def items_of(chapter):
    out = {}
    for coll in COLLECTIONS:
        for item in (chapter.get(coll) or []):
            if isinstance(item, dict) and item.get("id"):
                out[str(item["id"])] = item
    return out


def insert_line(text, item_id, line):
    """`"id": "<item_id>",` 줄 **다음에** 같은 들여쓰기로 한 줄을 끼운 글을 돌려준다."""
    pattern = re.compile(r'^(\s*)"id":\s*"' + re.escape(item_id) + r'",\s*$', re.M)
    match = pattern.search(text)
    if not match:
        return None
    indent = match.group(1)
    end = match.end()
    return text[:end] + "\n" + indent + line + text[end:]


def main():
    ap = argparse.ArgumentParser(description="문항에 사유 있는 검사 면제를 단다")
    ap.add_argument("--chapter", required=True, help="data/<과목>/chNN.json")
    ap.add_argument("--key", default="calculator-free-first-rung", help="면제할 검사 이름")
    ap.add_argument("--waive", action="append", default=[],
                    help='"<문항 id>::<사유>" 꼴. 여러 번 줄 수 있다')
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다(없으면 보기만)")
    args = ap.parse_args()

    if not os.path.isfile(args.chapter):
        sys.exit("그런 챕터 파일이 없다: " + args.chapter)
    with open(args.chapter, encoding="utf-8") as fh:
        text = fh.read()
    chapter = json.loads(text)
    known = items_of(chapter)

    plan = []
    for raw in args.waive:
        if "::" not in raw:
            sys.exit("`--waive` 는 `<id>::<사유>` 꼴이다: " + raw)
        item_id, why = raw.split("::", 1)
        item_id, why = item_id.strip(), why.strip()
        if not why:
            sys.exit("사유가 빈 줄은 면제가 아니다: " + item_id)
        if item_id not in known:
            sys.exit("그 챕터에 없는 문항이다: " + item_id)
        if known[item_id].get("lintWaivers"):
            print("   [건너뜀] %s — 이미 lintWaivers 가 있다. 손으로 합칠 것" % item_id)
            continue
        plan.append((item_id, why))

    if not plan:
        print("붙일 것이 없다")
        return 0

    print("붙일 것 %d건 (%s)" % (len(plan), args.key))
    for item_id, why in plan:
        print("   %s → %s" % (item_id, why))
    if not args.apply:
        print("\n(--apply 를 붙이면 실제로 쓴다)")
        return 0

    for item_id, why in plan:
        line = '"lintWaivers": {%s: %s},' % (json.dumps(args.key, ensure_ascii=False),
                                             json.dumps(why, ensure_ascii=False))
        nxt = insert_line(text, item_id, line)
        if nxt is None:
            sys.exit('`"id": "%s",` 줄을 못 찾았다 — 손으로 넣을 것' % item_id)
        text = nxt

    json.loads(text)          # 깨뜨렸으면 여기서 걸린다
    with open(args.chapter, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("\n%s 에 %d줄을 넣었다" % (args.chapter, len(plan)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
