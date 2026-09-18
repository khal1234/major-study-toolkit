#!/usr/bin/env python
"""장 JSON 의 항목에 학습목표 연결(`objectives`)을 적는다.

    python tools/set_objectives.py "data/<과목>/chNN.json" <항목id>=lo1,lo2 [<항목id>=lo3 …] [--apply]
    (--apply 가 없으면 무엇을 적을지만 보인다)

무엇을 하나: id 가 같은 항목(자가점검 `comprehensionChecks[]` · `practice[]` · `problems[]` ·
  `textbookProblems.items[]` · 이론 절)에 `objectives` 를 **덮어쓴다**. 값을 비우면(`id=`) 필드를 지운다.
문턱: 모르는 id · 모르는 lo 는 하나라도 있으면 아무것도 안 쓰고 exit 1 — 절반만 적힌 장을 남기지 않는다.
못 보는 것: 그 목표가 맞는 연결인지는 사람이 판정한다(재는 자 `tools/audit_objective_coverage.py`).
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def targets(ch):
    for s in (ch.get("theory") or {}).get("sections") or []:
        yield s
        for c in s.get("comprehensionChecks") or []:
            yield c
    for coll in ("practice", "problems"):
        for it in ch.get(coll) or []:
            yield it
    for it in (ch.get("textbookProblems") or {}).get("items") or []:
        yield it


def main(argv):
    apply = "--apply" in argv
    argv = [a for a in argv if a != "--apply"]
    if len(argv) < 3:
        sys.exit(__doc__)
    path = argv[1]
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    ch = json.loads(raw)
    los = {lo.get("id") for lo in ch.get("learningObjectives") or []}
    by_id = {}
    for t in targets(ch):
        if isinstance(t, dict) and t.get("id"):
            by_id[t["id"]] = t
    errors, plan = [], []
    for arg in argv[2:]:
        iid, _, val = arg.partition("=")
        objs = [v for v in val.split(",") if v]
        if iid not in by_id:
            errors.append("모르는 항목 id: " + iid)
        for o in objs:
            if o not in los:
                errors.append("%s: 모르는 학습목표 %s" % (iid, o))
        plan.append((iid, objs))
    if errors:
        sys.exit("\n".join(errors))
    if not apply:
        for iid, objs in plan:
            print("  %s ← %s" % (iid, ",".join(objs) or "(지움)"))
        print("%d건 — 실제로 쓰려면 --apply" % len(plan))
        return 0
    for iid, objs in plan:
        if objs:
            by_id[iid]["objectives"] = objs
        else:
            by_id[iid].pop("objectives", None)
    nl = "\r\n" if "\r\n" in raw else "\n"
    with open(path, "w", encoding="utf-8", newline=nl) as f:
        f.write(json.dumps(ch, ensure_ascii=False, indent=2) + "\n")
    print("objectives %d건 적음" % len(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
