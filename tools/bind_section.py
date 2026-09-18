# -*- coding: utf-8 -*-
r"""문항에 **`section`(붙는 이론 절)** 을 달아 준다 — 사람이 판정한 짝을 받아 적기만 한다.

    python tools/bind_section.py --chapter "data/<과목>/chNN.json" \
        --map "ch07-p01=sec-exergy-balance,ch07-q02=sec-exergy-of-system"
    python tools/bind_section.py --chapter … --map … --apply

열린 날 2026-09-10. 회차 구조(`docs/2026-09-10-학습-회차-구조.workorder.md`)가 서려면
`practice[]`·`problems[]` 의 모든 항목이 이론 절 하나를 가리켜야 한다. 전 과목 실측으로
**256건**(세 과목만)이라 손으로 붙이면 같은 편집을 수백 번 한다.

★ **이 자는 판정하지 않는다.** 어느 문항이 어느 절에 붙는지는 문항을 읽어야 아는 것이라
  사람이 `--map` 으로 준다(AGENTS 규칙 10 노랑). 이 자가 하는 일은 셋뿐이다 —
  ⑴ 그 절 id 가 실재하는지 확인 ⑵ 이미 붙어 있으면 건드리지 않고 알린다
  ⑶ **텍스트 삽입**으로 한 줄만 넣는다.

★ **다시 직렬화하지 않는다** (2026-09-10, `declare_check_waiver.py` 가 같은 자리에서 데였다 —
  한 줄 넣으려다 354줄이 바뀌었다). `json.dumps` 로 파일을 다시 쓰면 들여쓰기·순서·이스케이프가
  통째로 흔들려 diff 가 검수 불가능해진다. 그래서 `"id": "<그 id>",` 줄을 찾아 **그 다음 줄에**
  같은 들여쓰기로 한 줄을 끼운다.

☐ **이 자가 못 보는 것:** 짝이 옳은지. `--map` 에 엉뚱한 절을 적어도 그 절이 실재하기만 하면
  통과한다. 옳은지는 사람이 보고, 붙은 뒤에는 `audit_section_binding.py` 가 실이 끊겼는지만 센다.
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

COLLECTIONS = ("practice", "problems")


def theory_section_ids(chapter):
    node = chapter.get("theory")
    if isinstance(node, dict):
        node = node.get("sections")
    return {str(s.get("id")) for s in (node or [])
            if isinstance(s, dict) and s.get("id")}


def item_sections(chapter):
    """{문항 id: 이미 붙은 section 또는 None}."""
    out = {}
    for coll in COLLECTIONS:
        for item in (chapter.get(coll) or []):
            if isinstance(item, dict) and item.get("id"):
                out[str(item["id"])] = item.get("section")
    return out


def insert_lines(text, pairs):
    """`"id": "<iid>",` 줄 뒤에 `"section": "<sec>",` 를 끼운 새 본문. 순수 함수.

    같은 들여쓰기를 그대로 쓴다 — 그래야 diff 가 한 줄이다.
    """
    out, done = [], set()
    for line in text.split("\n"):
        out.append(line)
        m = re.match(r'^(\s*)"id":\s*"([^"]+)",\s*$', line)
        if m and m.group(2) in pairs and m.group(2) not in done:
            out.append('%s"section": "%s",' % (m.group(1), pairs[m.group(2)]))
            done.add(m.group(2))
    return "\n".join(out), done


def main():
    ap = argparse.ArgumentParser(description="문항에 section 을 달아 준다")
    ap.add_argument("--chapter", required=True)
    ap.add_argument("--map", required=True, help="문항id=절id,문항id=절id …")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.chapter):
        sys.exit("그런 파일이 없다: " + args.chapter)
    with open(args.chapter, encoding="utf-8") as fh:
        raw = fh.read()
    chapter = json.loads(raw)

    known_secs = theory_section_ids(chapter)
    known_items = item_sections(chapter)

    pairs = {}
    for chunk in args.map.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            sys.exit("짝의 꼴이 아니다(문항id=절id): " + chunk)
        iid, sec = (p.strip() for p in chunk.split("=", 1))
        if iid not in known_items:
            sys.exit("그런 문항이 이 장에 없다: " + iid)
        if sec not in known_secs:
            sys.exit("그런 이론 절이 이 장에 없다: " + sec
                     + "\n   있는 절 — " + ", ".join(sorted(known_secs)))
        if known_items[iid]:
            print("[건너뜀] %s 는 이미 %r 에 붙어 있다" % (iid, known_items[iid]))
            continue
        pairs[iid] = sec

    if not pairs:
        print("붙일 것이 없다 — 0건")
        return 0

    new, done = insert_lines(raw, pairs)
    missed = sorted(set(pairs) - done)
    if missed:
        sys.exit("이 문항의 `\"id\": …,` 줄을 못 찾았다(줄 꼴이 다르다): " + ", ".join(missed))
    json.loads(new)          # 이스케이프가 깨졌으면 여기서 멈춘다 — 쓰기 전에 판다

    print("붙일 것 %d건" % len(pairs))
    for iid in sorted(pairs):
        print("   %s → %s" % (iid, pairs[iid]))
    if not args.apply:
        print("\n※ `--apply` 를 안 줘서 쓰지 않았다")
        return 0
    with open(args.chapter, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new)
    print("\n%s 에 %d줄을 넣었다" % (args.chapter, len(pairs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
