"""「최종 답」(`expectedOutput`)에서 빈칸 답을 되읊는 문장을 걷는다 — 전부 되읊기면 비운다.

재는 것: `practice`·`problems` 문항마다 `expectedOutput` 을 문장으로 가른 뒤, 숫자가 있고 그 숫자가 **전부**
  빈칸 답(`blanks[].answer`)에 있는 문장. 후보 자 `audit_convention_drift --check=expected-echo` 와 같은 수 토큰
  정규식을 쓴다.
문턱: 그런 문장은 걷고, 숫자 없는 문장(판정·결론)과 빈칸에 없는 수가 든 문장은 남긴다. 남는 것이 없으면 `""`
  — 뷰어가 「최종 답」 줄과 잠금 문구를 둘 다 안 그린다. 남는 것이 「물성 출처」 안내뿐이면 건드리지 않는다.
기록: **키를 붙여** 값 하나만 텍스트로 갈아끼운다(`clear_expected_echo` 와 같은 방식). `write_chapter` 는 못 쓴다 —
  ⑴ `changeNote` 키를 새로 넣어야 하고 ⑵ 빈칸이 하나인 문항은 최종 답 문자열이 빈칸 답과 같아 값만으로는
  자리를 못 가린다(2026-09-19 첫 적용에서 둘 다 실측으로 거부됐다).
왜: 사용자 2026-09-19 [발화 생략](응용열 ch07 p04).
못 보는 것: 같은 수를 단위만 바꿔 다시 적은 문장(3.3 V ↔ 3300 mV) · 숫자 없는 문장이 빈칸을 말로 되풀이하는 경우.

쓰는 법:
  python tools/trim_expected_echo.py "data/<과목>/chNN.json" …            # 셈만
  python tools/trim_expected_echo.py --apply "data/<과목>/chNN.json" …
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

NUM = re.compile(r"-?\d+(?:\.\d+)?")          # audit_convention_drift.check_expected_echo 와 같은 토큰
SENT = re.compile(r"(?<=[.!?。])\s+")
NOTE = "지적(2026-09-19, 부류 «최종 답이 빈칸을 되읊는다») 「최종 답」에서 빈칸 답을 다시 적던 문장을 걷었습니다."


def trim(expected, blank_answers):
    """(새 문자열, 걷은 문장 수)."""
    have = set()
    for a in blank_answers:
        have.update(NUM.findall(str(a or "")))
    if not have:
        return expected, 0
    keep, dropped = [], 0
    for s in SENT.split(str(expected).strip()):
        nums = NUM.findall(s)
        if nums and all(n in have for n in nums):
            dropped += 1
        else:
            keep.append(s)
    return " ".join(keep).strip(), dropped


def _enc(s):
    return json.dumps(s, ensure_ascii=False)


def one(chapter, apply):
    with open(chapter, encoding="utf-8", newline="") as fh:
        out = fh.read()
    ch = json.loads(out)
    n, problems = 0, []
    for coll in ("practice", "problems"):
        for item in ch.get(coll) or []:
            if not isinstance(item, dict) or not str(item.get("expectedOutput") or "").strip():
                continue
            old = item["expectedOutput"]
            new, dropped = trim(old, [b.get("answer") for b in item.get("blanks") or [] if isinstance(b, dict)])
            if not dropped:
                continue
            if new and all(s.startswith("물성 출처") for s in SENT.split(new)):
                print("  [건너뜀·물성 출처만 남음] %s" % item.get("id"))
                continue
            id_at = out.find('"id": ' + _enc(str(item.get("id"))))
            hit = None
            for sep in ('"expectedOutput": ', '"expectedOutput":'):
                needle = sep + _enc(old)
                at = out.find(needle, max(id_at, 0))
                if at >= 0 and (out.count(needle) == 1 or id_at >= 0):
                    hit = (at, needle)
                    break
            if not hit:
                problems.append(str(item.get("id")))
                continue
            at, needle = hit
            out = out[:at] + '"expectedOutput": ' + _enc(new) + out[at + len(needle):]
            # 사유 — 있으면 뒤에 잇고(앞 사유를 지우지 않는다), 없으면 최종 답 키 바로 앞에 끼운다
            note = item.get("changeNote")
            if isinstance(note, str) and NOTE in note:
                pass
            elif isinstance(note, str):
                for sep in ('"changeNote": ', '"changeNote":'):
                    nd = sep + _enc(note)
                    j = out.find(nd, max(id_at, 0))
                    if j >= 0:
                        joined = (note + " · " + NOTE) if note.strip() else NOTE
                        out = out[:j] + '"changeNote": ' + _enc(joined) + out[j + len(nd):]
                        break
                else:
                    problems.append(str(item.get("id")) + "(사유)")
            else:
                at = out.find('"expectedOutput": ' + _enc(new), max(id_at, 0))
                line_start = out.rfind("\n", 0, at) + 1
                indent = out[line_start:at]
                kv = '"changeNote": ' + _enc(NOTE)
                out = out[:at] + ((kv + ",\n" + indent) if indent.strip() == "" else (kv + ", ")) + out[at:]
            n += 1
            print("  [%s] %s%s" % ("비움" if not new else "줄임", item.get("id"), (" — " + new[:50]) if new else ""))
    for p in problems:
        print("  [못 함]", p)
    if not n:
        return 1 if problems else 0
    print("합계 — %d 문항 (%s)%s" % (n, chapter, "" if apply else " · ※ --apply 를 주면 실제로 쓴다"))
    if apply:
        json.loads(out)            # 치환이 JSON 을 깨뜨리지 않았는지 먼저 본다
        with open(chapter, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser(description="최종 답의 빈칸 되읊기 문장을 걷는다")
    ap.add_argument("chapters", nargs="+")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    rc = 0
    for p in args.chapters:
        if not os.path.exists(p):
            sys.exit("파일이 없다: " + p)
        rc |= one(p, args.apply)
    return rc


if __name__ == "__main__":
    sys.exit(main())
