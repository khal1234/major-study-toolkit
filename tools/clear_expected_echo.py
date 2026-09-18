"""「최종 답」이 빈칸을 되읊기만 하는 문항의 `expectedOutput` 을 비운다.

재는 것: 없다 — **판정은 사람이 하고 이 도구는 적는 일만 한다.** 후보는
`audit_convention_drift.py --check=expected-echo` 가 내고, 그 후보에는 빈칸에 없는 판정
문장(「~라면」·「비용 정보가 필요하다」)을 담은 것이 섞인다(2026-09-18 첫 실행에서 후보 3 중 1만
실제 삭제였다). 그래서 **id 를 손으로 받는다.**

하는 일: 준 id 마다 ⑴ `expectedOutput` 을 `""` 로 ⑵ `changeNote` 를 부류 문구로 덮는다.
  뷰어는 `expectedOutput` 이 비면 「최종 답」 줄과 「빈칸 답을 모두 펼치면…」 잠금 문구를 둘 다 안 그린다.

못 보는 것: 그 문항이 정말 되읊기인지 · 채점기·검산 스크립트가 `expectedOutput` 을 읽는지
  (이 리포에서는 `verify_*.py` 가 자체 기대값을 들고 있어 안 읽는다 — 옮길 때 다시 잰다).

쓰는 법:
  python tools/clear_expected_echo.py "data/<과목>/chNN.json" --ids ch07-p01,ch07-p05
  python tools/clear_expected_echo.py "data/<과목>/chNN.json" --ids … --apply
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

NOTE = ("지적(2026-09-18, 부류 «최종 답이 빈칸을 되읊는다») 「최종 답」 줄을 지웠습니다 — "
        "빈칸 답을 그대로 다시 적을 뿐이었습니다.")


def main():
    ap = argparse.ArgumentParser(description="되읊는 최종 답을 비운다(판정은 사람이 한다)")
    ap.add_argument("chapter", help="data/<과목>/chNN.json")
    ap.add_argument("--ids", required=True, help="쉼표로 구분한 문항 id")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다(없으면 셈만)")
    args = ap.parse_args()

    want = [s.strip() for s in args.ids.split(",") if s.strip()]
    if not os.path.exists(args.chapter):
        sys.exit("파일이 없다: " + args.chapter)
    with open(args.chapter, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    ch = json.loads(raw)
    # ★★ **포맷이 정규형인지 먼저 잰다** (2026-09-18 실측). `json.dump(indent=2)` 로 다시 쓰면
    #   원본이 한 줄로 적어 둔 배열·객체가 펼쳐져 **한 문항을 고친 커밋의 diff 가 63줄 늘었다**
    #   (유체 ch04). 변경점 검수는 diff 를 사람이 읽는 일이라 그게 곧 잡음이다.
    #   → 정규형이 아니면 멈추고 사람이 그 파일만 손으로 고치게 한다.
    #   ★★ **파일을 통째로 다시 쓰지 않는다** (2026-09-18 실측으로 되돌린 설계). `json.dump` 로
    #   되쓰면 장마다 다른 포맷이 정규화돼 **한 문항 수정의 diff 가 63줄 늘었다**(유체 ch04).
    #   그래서 값 문자열 **하나만** 텍스트로 치환한다 — 포맷은 손도 안 댄다.
    #   안전장치: 그 값이 파일에 **꼭 한 번** 나와야 한다(여러 번이면 어느 문항인지 못 가린다).

    hit, miss, empty, ambiguous = [], [], [], []
    out = raw
    for coll in ("practice", "problems"):
        for item in ch.get(coll) or []:
            if not isinstance(item, dict) or item.get("id") not in want:
                continue
            value = str(item.get("expectedOutput") or "")
            if not value.strip():
                empty.append(item["id"])
                continue
            # ★ **키까지 붙여 찾는다** — 값만 찾으면 빈칸 답과 같은 문자열이라 파일에 두 번 나온다
            #   (빈칸이 하나인 문항은 거의 언제나 그렇다, 2026-09-18 전전 ch04 실측).
            encoded = json.dumps(value, ensure_ascii=False)
            cands = [n for n in ('"expectedOutput": ' + encoded, '"expectedOutput":' + encoded)
                     if out.count(n) == 1]
            if not cands:
                counts = [out.count('"expectedOutput": ' + encoded), out.count('"expectedOutput":' + encoded)]
                ambiguous.append(item["id"] + "(키를 붙여 찾아도 " + str(sum(counts)) + "번)")
                continue
            needle = cands[0]
            idx = out.index(needle)
            # ★ **사유(`changeNote`)도 같은 자리에서 적는다** (2026-09-18 재발 방지). 안 적으면
            #   빌드가 「사유 없음」으로 찍고 검수 화면에 왜 바뀌었는지가 안 뜬다(실행 규율 8).
            #   이미 `changeNote` 가 있으면 **덮어쓴다** — 새 키를 또 넣으면 한 객체에 같은 키가
            #   둘이 되고, 그 결함을 오늘 한 번 만들었다(응용열 ch07 p01).
            old_note = item.get("changeNote")
            if old_note is not None:
                old_needle = '"changeNote": ' + json.dumps(str(old_note), ensure_ascii=False)
                if out.count(old_needle) != 1:
                    old_needle = '"changeNote":' + json.dumps(str(old_note), ensure_ascii=False)
                if out.count(old_needle) == 1:
                    out = out.replace(old_needle, old_needle.split('"changeNote"')[0]
                                      + '"changeNote": ' + json.dumps(NOTE, ensure_ascii=False))
                    idx = out.index(needle)
                else:
                    print("  [사유 못 덮음]", item["id"], "— 기존 changeNote 를 한 자리로 못 집었다")
            else:
                line_start = out.rfind("\n", 0, idx) + 1
                indent = out[line_start:idx]
                note_kv = '"changeNote": ' + json.dumps(NOTE, ensure_ascii=False)
                # 줄 앞이 공백뿐이면 펼친 포맷이라 **새 줄**로, 아니면 한 줄짜리라 **바로 앞**에 붙인다.
                insert = (note_kv + ",\n" + indent) if indent.strip() == "" else (note_kv + ", ")
                out = out[:idx] + insert + out[idx:]
                idx = out.index(needle)
            out = out[:idx] + needle.split(encoded)[0] + '""' + out[idx + len(needle):]
            hit.append(item["id"])
    found = set(hit) | set(empty) | {a.split("(")[0] for a in ambiguous}
    miss = [i for i in want if i not in found]
    for i in ambiguous:
        print("  [못 가림]", i)

    for i in hit:
        print("  [비움]", i)
    for i in empty:
        print("  [이미 비어 있음]", i)
    for i in miss:
        print("  [못 찾음]", i)
    print("합계 — 비움 %d · 이미 빔 %d · 못 찾음 %d (%s)"
          % (len(hit), len(empty), len(miss), os.path.basename(args.chapter)))

    if not args.apply:
        print("※ --apply 를 주면 실제로 쓴다")
        return 1 if (miss or ambiguous) else 0
    if hit:
        json.loads(out)      # 치환이 JSON 을 깨뜨리지 않았는지 먼저 확인한다
        # `newline=""` — 읽을 때와 같은 줄끝을 그대로 되쓴다(변환이 붙으면 diff 가 파일 전체가 된다).
        with open(args.chapter, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
    return 1 if (miss or ambiguous) else 0


if __name__ == "__main__":
    sys.exit(main())
