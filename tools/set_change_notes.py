r"""변경점 하이라이트의 **사유**(`changeNote`)를 항목에 적는다.

열린 날 2026-08-13. 빌드가 *"하이라이트 N건에 changeNote 가 없다"* 를 신고하기 시작한 뒤
(같은 지적 4회 — `buildlib/review.py` 주석이 정본), **사유를 채우는 쪽에 도구가 없었다.**
그래서 채우려면 절·카드마다 `Edit` 를 부르게 되고, 한 배치가 수십 건이라 그 자체가
승인 피로가 된다(AGENTS 실행 규율 4 「파일 편집도 배치로」). 이 도구가 그 자리다.

★ **판정은 사람이 한다.** 어느 부류가 이 카드를 건드렸는지는 기준선과의 diff 를 보고 사람이
  정하고, 도구는 넘겨받은 문장을 **그대로** 적는다. 기계가 사유를 지어내면 그것이 곧
  *«배치 사유를 여러 카드에 복사해 붙인 것»* 이고, 빌드가 `[사유만 있음]` 으로 신고하는
  바로 그 결함이다(review.py `staleNote`).

★ **표기를 보존한다.** `json.dumps` 로 통째로 다시 쓰지 않고 `"id": …` 줄 **바로 아래에
  한 줄을 끼워 넣는다**(`set_derivation_kind.py` 와 같은 처방 — 재포맷하면 변경점
  하이라이트가 통째로 잡음이 된다). 안전장치는 마지막 재파싱이다: 갈아끼운 본문을 다시 읽어
  **의도한 객체와 같지 않으면 안 쓴다.**

★ **사유의 머리는 부류 선언이다.** 뷰어가 `^지적\([^)]*\)` 를 키로 같은 부류를 묶어
  **앞 3건만** 보여 준다(`reviewNoteKey`). 그래서 같은 부류에는 **머리를 글자 그대로 같게**
  적어야 한다 — 조치 문장만 카드마다 다르게 쓴다. 머리가 갈리면 부류 12곳이 12개 부류가 된다.

    python tools/set_change_notes.py --chapter=ch01.json --from=notes.json [--apply]
    python tools/set_change_notes.py --chapter=ch01.json --list

`--from` 파일은 `{"<항목 id>": "<사유>"}` 꼴의 JSON 이다(줄바꿈은 `\n`).
"""

import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_content  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 오류는 stderr 로 나간다 — 그쪽도 UTF-8 로 돌려놓지 않으면 **한글 오류만** 깨진다
# (AGENTS 「나가는 쪽도 마찬가지다」. 잠금 `test_checks.py::test_tool_failures_are_readable`).
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 사유를 달 수 있는 자리 = 빌드가 하이라이트를 만드는 자리(`buildlib.review` 의 컬렉션)와 같다.
# 두 벌로 적으면 갈라지므로 **여기서만** 경로를 푼다.
COLLECTIONS = (
    ("theory", lambda d: ((d.get("theory") or {}).get("sections") or [])),
    ("derivation", lambda d: ((d.get("derivation") or {}).get("formulas") or [])),
    ("practice", lambda d: (d.get("practice") or [])),
    ("problems", lambda d: (d.get("problems") or [])),
)


def items_of(data):
    """[(컬렉션 이름, 항목 dict)] — 순수 함수. 테스트가 직접 부른다."""
    out = []
    for name, pick in COLLECTIONS:
        for item in pick(data):
            if isinstance(item, dict) and item.get("id"):
                out.append((name, item))
    return out


def apply_text(original, notes):
    """(새 본문, 사유). 사유가 있으면 쓰지 않는다. 순수 함수 — 테스트가 직접 부른다.

    `notes` = {항목 id: 사유}. `"id": "<x>",` 줄을 찾아 그 아래에 같은 들여쓰기로
    `"changeNote": "<사유>",` 를 끼우거나, 이미 그 자리에 있으면 갈아끼운다.
    """
    lines = original.split("\n")
    for item_id, note in notes.items():
        literal = json.dumps(item_id, ensure_ascii=False)
        hits = [i for i, ln in enumerate(lines)
                if re.match(r'^(\s*)"id": ' + re.escape(literal) + r',\s*$', ln)]
        if len(hits) != 1:
            return None, "id 줄을 하나로 특정하지 못했다(%d개): %s" % (len(hits), item_id)
        i = hits[0]
        indent = re.match(r"^(\s*)", lines[i]).group(1)
        row = indent + '"changeNote": ' + json.dumps(note, ensure_ascii=False) + ","
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if re.match(r'^' + indent + r'"changeNote": ', nxt):
            lines[i + 1] = row
        else:
            lines.insert(i + 1, row)
    return "\n".join(lines), None


def main():
    ap = argparse.ArgumentParser(description="변경점 하이라이트의 사유를 적는다")
    ap.add_argument("--chapter", required=True, help="chNN.json")
    ap.add_argument("--from", dest="src", default="", help='{"id": "사유"} JSON 파일')
    ap.add_argument("--list", action="store_true", help="지금 사유 상태만 본다")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    path = os.path.join(audit_content.DATA, args.chapter)
    if not os.path.isfile(path):
        sys.exit("없는 챕터다: " + path)
    with open(path, encoding="utf-8", newline="") as fh:
        original = fh.read()
    data = json.loads(original)
    pairs = items_of(data)

    if args.list:
        print("== %s 항목 %d건" % (args.chapter, len(pairs)))
        for name, item in pairs:
            note = str(item.get("changeNote") or "").strip()
            print("  %-11s %-28s %s" % (name, item.get("id"), note[:52] or "(사유 없음)"))
        return 0

    if not args.src:
        sys.exit("--from 이나 --list 중 하나가 있어야 한다")
    with open(args.src, encoding="utf-8") as fh:
        notes = json.load(fh)
    if not isinstance(notes, dict):
        sys.exit("--from 파일은 {id: 사유} 꼴의 JSON 이어야 한다")

    known = {item.get("id") for _, item in pairs}
    unknown = sorted(set(notes) - known)
    if unknown:
        sys.exit("이 챕터에 없는 id: " + ", ".join(unknown))
    blank = sorted(k for k, v in notes.items() if not str(v or "").strip())
    if blank:
        # 빈 사유는 «지우기» 로 보이지만 그건 `clear_change_notes.py` 의 몫이다.
        # 두 도구가 같은 일을 하면 어느 쪽이 정본인지 갈린다.
        sys.exit("빈 사유가 있다(지우려면 clear_change_notes.py): " + ", ".join(blank))

    now = {item.get("id"): str(item.get("changeNote") or "") for _, item in pairs}
    changes = {k: v for k, v in notes.items() if now.get(k) != v}
    for name, item in pairs:
        item_id = item.get("id")
        if item_id in notes:
            print("  %-11s %-28s %s" % (name, item_id,
                                        "그대로" if item_id not in changes else "사유 씀"))
    if not changes:
        print("\n바꿀 것 없음")
        return 0
    print("\n%d건%s" % (len(changes), "" if args.apply else "  (미리보기 — --apply 로 반영)"))
    if not args.apply:
        return 0

    text, why = apply_text(original, changes)
    if why:
        sys.exit("안 썼다 — " + why)
    want = copy.deepcopy(data)
    for _, item in items_of(want):
        if item.get("id") in changes:
            item["changeNote"] = changes[item["id"]]
    if json.loads(text) != want:
        sys.exit("안 썼다 — 갈아끼운 결과가 의도한 내용과 다르다")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print("[written] " + args.chapter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
