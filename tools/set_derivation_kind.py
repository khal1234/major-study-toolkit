r"""유도 카드의 **종류**(`kind`)를 선언한다 — `derivation` / `summary`.

열린 날 2026-08-12 (열역학 검수 인박스 부류 3 「형식 전환을 적용할 자리가 아니었다」).
사용자(ch01 유도 4/13·5/13): *[발화 생략]*

규격은 AGENTS 「유도 탭의 카드는 두 종류다」가 정본이고, 막는 것은 빌드 **C38**(선언과 모양이
맞는가) · **C43**(선언을 했는가)이다. 이 도구는 **선언을 데이터에 적는** 쪽이다.

★ **판정은 사람이 한다.** 도구는 넘겨받은 목록을 그대로 적을 뿐이고, 어느 카드가 공식
  정리인지는 추측하지 않는다 — 이름이나 단계 수로 찍으면 카드마다 갈라지고, 그 갈라짐이
  이 규격이 없애려는 결함이다.

★ **표기를 보존한다.** `json.dumps` 로 통째로 다시 쓰지 않고 `"id": …` 줄 **바로 아래에
  한 줄을 끼워 넣는다.** 재포맷하면 변경점 하이라이트가 통째로 잡음이 된다(AGENTS 「기준선」).
  `buildlib.jsontext.write_chapter` 를 못 쓰는 이유는 그쪽이 **문자열 값 치환만** 하기 때문이다 —
  키를 새로 넣는 것은 구조 변경이라 거기서는 `ValueError` 다.
  안전장치는 마지막 재파싱이다: 갈아끼운 본문을 다시 읽어 **의도한 객체와 같지 않으면 안 쓴다.**

    python tools/set_derivation_kind.py --chapter=ch01.json --summary=a,b [--apply]
    python tools/set_derivation_kind.py --chapter=ch01.json --list
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
# 오류는 stderr 로 나간다 — 그쪽도 UTF-8 로 돌려놓지 않으면 **한글 오류만 깨진다**
# (2026-08-12, 동역학 세션 보고. 잠금 `test_checks.py::test_tool_errors_are_utf8`).
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

KINDS = ("derivation", "summary")


def formulas_of(data):
    return ((data.get("derivation") or {}).get("formulas") or [])


def plan(data, summary_ids):
    """[(id, 지금, 바꿀 값)] — 순수 함수. 테스트가 직접 부른다."""
    out = []
    for f in formulas_of(data):
        fid = f.get("id")
        want = "summary" if fid in summary_ids else "derivation"
        out.append((fid, f.get("kind"), want))
    return out


def apply_text(original, changes):
    """(새 본문, 사유). 사유가 있으면 쓰지 않는다. 순수 함수 — 테스트가 직접 부른다.

    `changes` = {formula id: 새 kind}. `"id": "<fid>",` 줄을 찾아 그 아래에 같은 들여쓰기로
    `"kind": "<값>",` 을 끼우거나, 이미 있으면 그 줄을 갈아끼운다.
    """
    lines = original.split("\n")
    for fid, want in changes.items():
        literal = json.dumps(fid, ensure_ascii=False)
        hits = [i for i, ln in enumerate(lines)
                if re.match(r'^(\s*)"id": ' + re.escape(literal) + r',\s*$', ln)]
        if len(hits) != 1:
            return None, "id 줄을 하나로 특정하지 못했다(%d개): %s" % (len(hits), fid)
        i = hits[0]
        indent = re.match(r"^(\s*)", lines[i]).group(1)
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        row = indent + '"kind": ' + json.dumps(want, ensure_ascii=False) + ","
        if re.match(r'^' + indent + r'"kind": ', nxt):
            lines[i + 1] = row
        else:
            lines.insert(i + 1, row)
    return "\n".join(lines), None


def main():
    ap = argparse.ArgumentParser(description="유도 카드의 종류를 선언한다")
    ap.add_argument("--chapter", required=True, help="chNN.json")
    ap.add_argument("--summary", default="", help="공식 정리 카드의 id 를 쉼표로")
    ap.add_argument("--list", action="store_true", help="지금 선언 상태만 본다")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    path = audit_content.chapter_file(args.chapter)
    if not os.path.isfile(path):
        sys.exit("없는 챕터다: " + path)
    with open(path, encoding="utf-8", newline="") as fh:
        original = fh.read()
    data = json.loads(original)

    if args.list:
        print("== %s 유도 카드 %d건" % (args.chapter, len(formulas_of(data))))
        for i, f in enumerate(formulas_of(data), 1):
            steps = f.get("derivationSteps") or []
            obj = sum(1 for s in steps if isinstance(s, dict))
            print("  %2d/%d %-34s kind=%-11s 단계 %d(객체 %d)"
                  % (i, len(formulas_of(data)), f.get("id"),
                     f.get("kind") or "미선언", len(steps), obj))
        return 0

    ids = {f.get("id") for f in formulas_of(data)}
    summary_ids = {s.strip() for s in args.summary.split(",") if s.strip()}
    unknown = summary_ids - ids
    if unknown:
        sys.exit("이 챕터에 없는 id: " + ", ".join(sorted(unknown)))

    changes = {}
    for fid, now, want in plan(data, summary_ids):
        mark = "그대로" if now == want else ("%s → %s" % (now or "미선언", want))
        print("  %-34s %s" % (fid, mark))
        if now != want:
            changes[fid] = want
    if not changes:
        print("\n바꿀 것 없음")
        return 0
    print("\n%d건%s" % (len(changes), "" if args.apply else "  (미리보기 — --apply 로 반영)"))
    if not args.apply:
        return 0

    text, why = apply_text(original, changes)
    if why:
        sys.exit("안 썼다 — " + why)
    want_obj = copy.deepcopy(data)
    for f in formulas_of(want_obj):
        if f.get("id") in changes:
            f["kind"] = changes[f["id"]]
    if json.loads(text) != want_obj:
        sys.exit("안 썼다 — 갈아끼운 결과가 의도한 내용과 다르다")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print("[written] " + args.chapter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
