r"""끝난 배치의 `changeNote` 를 걷어낸다 — **기준선을 옮기는 그 자리에서 함께 돈다.**

열린 날 2026-08-12 (열역학 검수 인박스 **부류 11**).
사용자: *[발화 생략]* · *[발화 생략]*
→ **두 요구는 충돌하지 않는다: 끝난 것은 지우고, 이번 배치 것만 남긴다.**

★★ **왜 도구인가 — 규칙은 있었는데 아무도 안 돌렸다.**
  AGENTS 는 *[발화 생략]* 고 적어 두었지만
  **그 일을 하는 코드가 없었다.** `--accept-review-*` 는 스냅샷만 쓰고 데이터는 안 건드린다.
  그래서 규칙이 사람의 성실성에 걸려 있었고, 실제로 **ch05 5.1 에 2026-07-29 자 기록이
  살아남아** 사용자가 지적했다(인박스 부류 11 의 실증). 실측 2026-08-12: 남아 있던 것 **47개**.

★ **판정선은 「이번 배치의 것인가」 하나다.** 이번 배치의 `changeNote` 는 *기준선 이후* 변경의
  사유라 화면에 떠야 하고, 그 앞의 것은 기준선 뒤로 넘어갔으므로 뜻이 없다.
  구분은 `--keep` 표시(보통 배치 날짜)로 한다 — 값 안에 그 글자가 있으면 남긴다.

★ **표기를 보존한다.** 줄 단위로 지우고 **재파싱해 의도한 객체와 같은지 확인한 뒤에만** 쓴다
  (`buildlib.jsontext` 를 못 쓰는 이유는 키 삭제가 구조 변경이라서다 —
  `set_derivation_kind.py` 와 같은 처방).

    python tools/clear_change_notes.py --keep=2026-08-12 [--chapter=chNN.json] [--apply]
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_content  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_LINE = re.compile(r'^\s*"changeNote":\s*"(.*)",?\s*$')


def strip_lines(original, keep):
    """(새 본문, 지운 수). 순수 함수 — 테스트가 직접 부른다.

    한 줄짜리 `"changeNote": "…"` 만 지운다. 여러 줄로 접힌 것은 **건드리지 않고 세어서
    알린다** — 줄 단위로 자르면 JSON 이 깨지고, 그 조용한 깨짐이 이 부류에서 가장 나쁘다.
    """
    out, removed = [], 0
    for line in original.split("\n"):
        m = _LINE.match(line)
        if m and keep not in m.group(1):
            removed += 1
            continue
        out.append(line)
    return "\n".join(out), removed


def main():
    ap = argparse.ArgumentParser(description="끝난 배치의 changeNote 를 걷어낸다")
    ap.add_argument("--keep", required=True,
                    help="이 글자가 들어 있는 changeNote 는 남긴다 (보통 이번 배치 날짜)")
    ap.add_argument("--chapter", help="chNN.json 하나만")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    print("남길 표시: %r — 그 밖의 changeNote 는 끝난 배치의 것으로 본다" % args.keep)
    names = ([args.chapter] if args.chapter else [n + ".json" for n in audit_content.CHAPTERS])
    total, stuck = 0, 0
    for name in names:
        path = audit_content.chapter_file(name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", newline="") as fh:
            original = fh.read()
        before = json.loads(original)
        text, removed = strip_lines(original, args.keep)
        # 줄이 안 잡힌 것(여러 줄로 접힌 값)을 세어 알린다 — 조용히 지나가면 안 된다.
        left = original.count('"changeNote"') - removed
        kept = sum(1 for m in re.finditer(r'"changeNote":\s*"(.*)",?\s*$', original, re.M)
                   if args.keep in m.group(1))
        stuck += max(0, left - kept)
        if not removed:
            continue
        total += removed
        print("  %-12s 지움 %d · 남김 %d" % (name, removed, left))
        if not args.apply:
            continue
        try:
            after = json.loads(text)
        except json.JSONDecodeError as exc:
            print("  [안 씀] json 이 깨졌다: %s" % exc)
            continue
        want = json.loads(json.dumps(before, ensure_ascii=False))

        def drop(node):
            if isinstance(node, dict):
                note = node.get("changeNote")
                # ★ 값 안의 줄바꿈은 **JSON 이스케이프**(`\n`)라 파일에서는 한 줄이다.
                #   여기서 `"\n" not in note` 로 걸렀더니 안전장치가 전부 거부했다 —
                #   *파일의 줄 수*와 *값의 줄 수*를 헷갈린 것이다(2026-08-12 첫 실행).
                if isinstance(note, str) and args.keep not in note:
                    node.pop("changeNote")
                for v in node.values():
                    drop(v)
            elif isinstance(node, list):
                for v in node:
                    drop(v)
        drop(want)
        if after != want:
            print("  [안 씀] 지운 결과가 의도한 내용과 다르다")
            continue
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print("  [written] " + name)
    print("\n지운 것 %d개%s%s"
          % (total,
             ("  · 여러 줄로 접혀 못 지운 것 %d개(사람이 본다)" % stuck) if stuck else "",
             "" if args.apply else "  (미리보기 — --apply 로 반영)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
