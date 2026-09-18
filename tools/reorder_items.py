#!/usr/bin/env python
"""장 JSON 의 한 컬렉션(`practice`·`problems`) 안에서 항목 순서를 id 목록대로 바꾼다.

    python tools/reorder_items.py "data/<과목>/chNN.json" practice <id> <id> … [--apply]
    (--apply 가 없으면 새 순서만 보인다)

무엇을 하나: 적은 id 를 그 순서로 앞에 세우고, 안 적은 항목은 원래 순서대로 뒤에 붙인다. 내용은 안 건드린다.
문턱: 모르는 id · 겹친 id 가 하나라도 있으면 아무것도 안 쓰고 exit 1.
못 보는 것: 순서가 램프(C54)·절 순서에 맞는지는 `tools/audit_prompt_ramp.py` 가 잰다.
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

COLLECTIONS = ("practice", "problems")


def main(argv):
    apply = "--apply" in argv
    argv = [a for a in argv if a != "--apply"]
    if len(argv) < 4 or argv[2] not in COLLECTIONS:
        sys.exit(__doc__)
    path, coll, order = argv[1], argv[2], argv[3:]
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    ch = json.loads(raw)
    items = ch.get(coll) or []
    by_id = {it.get("id"): it for it in items}
    errors = [i for i in order if i not in by_id]
    dup = sorted({i for i in order if order.count(i) > 1})
    if errors or dup:
        sys.exit("모르는 id: %s · 겹친 id: %s" % (errors, dup))
    rest = [it for it in items if it.get("id") not in order]
    if not apply:
        print("새 순서: " + " ".join(order + [it.get("id") for it in rest]))
        print("실제로 쓰려면 --apply")
        return 0
    ch[coll] = [by_id[i] for i in order] + rest
    nl = "\r\n" if "\r\n" in raw else "\n"
    with open(path, "w", encoding="utf-8", newline=nl) as f:
        f.write(json.dumps(ch, ensure_ascii=False, indent=2) + "\n")
    print("%s 순서 %d건 앞에 세움 · 나머지 %d건" % (coll, len(order), len(rest)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
