#!/usr/bin/env python
"""이론 절을 **다른 장으로** 옮긴다 — 절에 딸린 문풀·연습문제·학습목표와 지정한 유도 카드까지.

    python tools/move_sections.py --from=<원본 chNN.json> --to=<대상 chNN.json> \\
        --sections=sec-a,sec-b --after=<대상의 절 id|end> \\
        [--formulas=f-x,f-y --formula-after=<대상의 카드 id|end>] [--keep-source] [--apply]

`reorder_sections.py` 는 한 장 **안**의 순서만 바꾼다. 장의 경계를 옮기는 재구성(강의자료
주차에 맞춰 장을 다시 짜는 일)은 절 하나에 삽화·함정·이해도 체크·문항이 붙어 있어 손으로
잘라 붙이면 조용히 어긋난다.

무엇이 따라가나:
  · 절 — 삽화·함정·이해도 체크는 절 **안**에 있어 그대로 따라간다.
  · 문풀·연습문제 — `section` 이 옮기는 절인 것. id 는 대상 장 접두(`chNN-p05`)의 **다음 빈 번호**로
    바꾸고, 문항 안에 적힌 옛 id(`fig-ch03-q01` 등)도 함께 바꾼다.
  · 학습목표 — `relatedSections` 가 전부 옮기는 절인 것. 대상 장의 다음 `loN` 으로 바꾼다.
  · 유도 카드 — `--formulas` 로 **지정한 것만**(카드는 절을 적지 않아 자동으로 못 가른다).

☐ 못 하는 것(사람 몫): 장 제목·도입부·키워드·`noTheoryDiagramReason` 병합 · 본문 속 「N주차」
  같은 장 사이 표현 · 다른 장·부속 파일(판정 원장·검산기 라벨)이 옛 id 를 적은 자리 — 끝에
  **바꾼 id 표**를 찍으니 그것으로 찾는다.

쓰기 규율: 기본은 보고만 한다. `--apply` 를 줘야 쓴다. `--keep-source` 면 원본 장은 그대로 둔다
(원본을 통째로 보관 폴더로 옮길 때).
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ITEM_KINDS = ("practice", "problems")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def insert_after(items, new, after_id):
    """`after_id` 뒤(또는 `end`)에 `new` 를 순서대로 넣은 새 목록. 순수 함수."""
    if after_id == "end":
        return items + new
    ids = [x.get("id") for x in items]
    if ids.count(after_id) != 1:
        raise ValueError("기준 id 를 하나로 특정할 수 없다: %r (발견 %d개)" % (after_id, ids.count(after_id)))
    at = ids.index(after_id) + 1
    return items[:at] + new + items[at:]


def take(items, wanted):
    """`wanted` 순서대로 꺼낸 것과 남은 것. 없는 id 가 있으면 실패한다. 순수 함수."""
    by_id = {x.get("id"): x for x in items}
    missing = [w for w in wanted if w not in by_id]
    if missing:
        raise ValueError("원본에 없는 id: " + ", ".join(missing))
    return [by_id[w] for w in wanted], [x for x in items if x.get("id") not in set(wanted)]


def next_number(ids, pattern):
    nums = [int(m.group(1)) for i in ids for m in [re.fullmatch(pattern, i or "")] if m]
    return (max(nums) + 1) if nums else 1


def rename_item(item, old, new):
    """문항 안의 옛 id 를 전부 새 id 로. 다른 id 의 일부(`ch03-q01` ⊂ `ch03-q010`)는 안 건드린다."""
    text = json.dumps(item, ensure_ascii=False)
    text = re.sub(r"(?<![A-Za-z0-9])" + re.escape(old) + r"(?![0-9])", new, text)
    return json.loads(text)


def move(src, dst, sections, after, formulas, formula_after, dst_stem):
    """원본·대상 사전을 고쳐 돌려준다(원본은 사본). 바꾼 id 표도 함께. 순수 함수에 가깝다."""
    src = json.loads(json.dumps(src))
    dst = json.loads(json.dumps(dst))
    renames = []

    moved, rest = take(src["theory"]["sections"], sections)
    src["theory"]["sections"] = rest
    dst["theory"]["sections"] = insert_after(dst["theory"]["sections"], moved, after)

    if formulas:
        fm, frest = take(src["derivation"]["formulas"], formulas)
        src["derivation"]["formulas"] = frest
        dst["derivation"]["formulas"] = insert_after(dst["derivation"]["formulas"], fm, formula_after)

    moving = set(sections)
    for kind in ITEM_KINDS:
        going = [x for x in src.get(kind) or [] if x.get("section") in moving]
        src[kind] = [x for x in src.get(kind) or [] if x.get("section") not in moving]
        dst_items = dst.setdefault(kind, [])
        for item in going:
            old = item.get("id", "")
            m = re.fullmatch(r"ch\d+-([a-z]+)(\d+)", old)
            letter = m.group(1) if m else ("p" if kind == "practice" else "q")
            n = next_number([x.get("id") for x in dst_items], re.escape(dst_stem) + "-" + letter + r"(\d+)")
            new = "%s-%s%02d" % (dst_stem, letter, n)
            dst_items.append(rename_item(item, old, new) if old else item)
            renames.append((old, new))

    objs = src.get("learningObjectives") or []
    going = [o for o in objs if o.get("relatedSections") and set(o["relatedSections"]) <= moving]
    src["learningObjectives"] = [o for o in objs if o not in going]
    dst_objs = dst.setdefault("learningObjectives", [])
    for o in going:
        n = next_number([x.get("id") for x in dst_objs], r"lo(\d+)")
        renames.append(("%s:%s" % ("lo", o.get("id")), "lo%d" % n))
        o = dict(o, id="lo%d" % n)
        dst_objs.append(o)
    return src, dst, renames


def move_items(src, dst, item_ids, new_section, dst_stem):
    """절은 두고 **문항만** 옮긴다 — 문항이 대상 장의 개념을 쓸 때. id·section 을 새 장에 맞춘다."""
    src = json.loads(json.dumps(src))
    dst = json.loads(json.dumps(dst))
    if new_section not in {s.get("id") for s in dst["theory"]["sections"]}:
        raise ValueError("대상 장에 없는 절: " + new_section)
    renames, found = [], set()
    for kind in ITEM_KINDS:
        going = [x for x in src.get(kind) or [] if x.get("id") in item_ids]
        src[kind] = [x for x in src.get(kind) or [] if x.get("id") not in item_ids]
        dst_items = dst.setdefault(kind, [])
        for item in going:
            old = item["id"]
            found.add(old)
            letter = re.fullmatch(r"ch\d+-([a-z]+)\d+", old).group(1)
            n = next_number([x.get("id") for x in dst_items], re.escape(dst_stem) + "-" + letter + r"(\d+)")
            new = "%s-%s%02d" % (dst_stem, letter, n)
            moved = rename_item(item, old, new)
            moved["section"] = new_section
            dst_items.append(moved)
            renames.append((old, new))
    missing = [i for i in item_ids if i not in found]
    if missing:
        raise ValueError("원본에 없는 문항: " + ", ".join(missing))
    return src, dst, renames


def main():
    ap = argparse.ArgumentParser(description="이론 절을 다른 장으로 옮긴다(딸린 문항·학습목표 포함)")
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--to", dest="dst", required=True)
    ap.add_argument("--sections", default="", help="옮길 절 id, 쉼표로 — 이 순서대로 들어간다")
    ap.add_argument("--after", default="end", help="대상 장의 절 id 또는 end")
    ap.add_argument("--items", default="",
                    help="절 없이 **문항만** 옮긴다(id 쉼표로) — 절은 남는데 문항이 뒤 장 개념을 쓸 때")
    ap.add_argument("--item-section", default="", help="--items 로 옮긴 문항의 새 section id(대상 장의 절)")
    ap.add_argument("--formulas", default="", help="함께 옮길 유도 카드 id, 쉼표로")
    ap.add_argument("--formula-after", default="end")
    ap.add_argument("--keep-source", action="store_true", help="원본 장은 쓰지 않는다")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    src, dst = load(a.src), load(a.dst)
    sections = [s for s in a.sections.split(",") if s]
    formulas = [f for f in a.formulas.split(",") if f]
    items = [i for i in a.items.split(",") if i]
    if items:
        if sections or not a.item_section:
            raise SystemExit("--items 는 --sections 없이, --item-section 과 함께 쓴다")
        new_src, new_dst, renames = move_items(src, dst, items, a.item_section, stem(a.dst))
        sections = []
    else:
        if not sections:
            raise SystemExit("--sections 나 --items 중 하나가 필요하다")
        new_src, new_dst, renames = move(src, dst, sections, a.after, formulas, a.formula_after,
                                         stem(a.dst))

    if items:
        print("[문항] %s → %s: %s (새 section %s)" % (stem(a.src), stem(a.dst), ", ".join(items),
                                                   a.item_section))
    else:
        print("[절] %s → %s: %s (뒤: %s)" % (stem(a.src), stem(a.dst), ", ".join(sections), a.after))
    if formulas:
        print("[카드] %s (뒤: %s)" % (", ".join(formulas), a.formula_after))
    print("[바꾼 id] %d개" % len(renames))
    for old, new in renames:
        print("   %s → %s" % (old, new))
    print("[대상 절 순서] " + " · ".join(s["id"] for s in new_dst["theory"]["sections"]))
    if not a.apply:
        print("(보고만 했다 — 쓰려면 --apply)")
        return 0
    save(a.dst, new_dst)
    if not a.keep_source:
        save(a.src, new_src)
    print("저장했다%s. ★ 제목·도입부·키워드·장 사이 표현과 부속 파일의 옛 id 는 사람이 고칠 것."
          % (" (원본은 그대로 뒀다)" if a.keep_source else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
