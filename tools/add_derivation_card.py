"""유도 탭(`derivation.formulas`) 맨 끝에 카드 하나를 끼워 넣는다 — 공식 정리(`kind: "summary"`) 카드용.

재는 것: 없다 — **카드 내용은 사람이 쓰고 이 도구는 끼우는 일만 한다.** 후보는
`audit_convention_drift.py --check=formula-summary-card` 가 낸다.

하는 일: 준 카드를 `formulas` 배열의 마지막 원소 뒤에 텍스트로 끼운다. 파일을 다시 직렬화하지 않는다
  (`json.dump` 로 되쓰면 포맷이 정규화돼 diff 가 불어난다 — `clear_expected_echo.py` 와 같은 이유).
  쓰기 전에 ⑴ 같은 id 가 없는지 ⑵ 결과 JSON 의 `formulas` 가 「원래 + 이 카드」와 같은지 대조한다.

못 보는 것: 카드의 식이 이론·유도와 맞는가(빌드 C38·C43 과 사람) · 카드가 그 장의 식을 빠짐없이 모았는가.

쓰는 법:
  python tools/add_derivation_card.py "data/<과목>/chNN.json" --card <카드.json>          (셈만)
  python tools/add_derivation_card.py "data/<과목>/chNN.json" --card <카드.json> --apply
"""
import argparse
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from set_practice_prompt_ko import top_key, value_end   # noqa: E402

INDENT = "      "   # `derivation` → `formulas` → 카드: 이 리포 장 파일의 들여쓰기(2칸 × 3)


def main():
    ap = argparse.ArgumentParser(description="유도 탭 끝에 카드 하나를 끼운다(내용은 사람이 쓴다)")
    ap.add_argument("chapter", help="data/<과목>/chNN.json")
    ap.add_argument("--card", help="카드 하나(JSON 객체) 파일")
    ap.add_argument("--list", action="store_true",
                    help="지금 유도 탭 카드의 id·종류·이름·식·기호를 찍는다(정리 카드를 쓰기 전에 읽는 자리)")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다(없으면 셈만)")
    ap.add_argument("--no-lint", action="store_true",
                    help="쓴 뒤 lint 를 안 돌린다 — 장 스키마가 없는 조각 파일(회귀 테스트)에만 쓴다")
    args = ap.parse_args()

    if not os.path.exists(args.chapter):
        sys.exit("파일이 없다: " + args.chapter)
    if args.list:
        # 장 파일 통째 Read 는 삽화 SVG 때문에 크다 — 정리 카드에 필요한 칸만 뽑는다.
        with open(args.chapter, encoding="utf-8") as fh:
            ch = json.load(fh)
        for f in (ch.get("derivation") or {}).get("formulas") or []:
            print("== %s [%s] %s · topic=%s" % (f.get("id"), f.get("kind"), f.get("name"), f.get("topic")))
            print("   latex:", json.dumps(f.get("latex"), ensure_ascii=False))
            print("   applies:", f.get("appliesTo"))
            print("   vars:", json.dumps(f.get("variables"), ensure_ascii=False))
            print("   assumptions:", json.dumps(f.get("assumptions"), ensure_ascii=False))
        return 0
    if not args.card:
        sys.exit("--card 나 --list 중 하나가 필요하다")
    with open(args.card, encoding="utf-8") as fh:
        card = json.load(fh)
    with open(args.chapter, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    ch = json.loads(raw)
    formulas = (ch.get("derivation") or {}).get("formulas")
    if not isinstance(formulas, list) or not formulas:
        sys.exit("`derivation.formulas` 가 없거나 비었다 — 끼울 자리가 없다")
    if any(isinstance(f, dict) and f.get("id") == card.get("id") for f in formulas):
        sys.exit("같은 id 가 이미 있다: " + str(card.get("id")))

    d = top_key(raw, "derivation")
    d_val = raw.index("{", raw.index(":", d))
    d_span = raw[d_val:value_end(raw, d_val)]
    f_rel = top_key(d_span, "formulas")
    f_val = d_val + d_span.index("[", d_span.index(":", f_rel))
    f_end = value_end(raw, f_val) - 1          # 닫는 `]` 의 위치
    close = f_end                              # 닫는 괄호 앞 공백·줄바꿈을 건너 마지막 원소 끝에 붙인다
    while raw[close - 1] in " \t\r\n":
        close -= 1
    body = json.dumps(card, ensure_ascii=False, indent=2).replace("\n", "\n" + INDENT)
    out = raw[:close] + ",\n" + INDENT + body + raw[close:]

    got = json.loads(out)
    if got["derivation"]["formulas"] != formulas + [card]:
        sys.exit("대조 실패 — 끼운 결과가 기대와 다르다")
    rest = {k: v for k, v in got.items() if k != "derivation"}
    if rest != {k: v for k, v in ch.items() if k != "derivation"}:
        sys.exit("대조 실패 — 유도 탭 밖이 바뀌었다")

    print("  [끼움] %s (%s) — 유도 탭 %d → %d장 (%s)"
          % (card.get("id"), card.get("kind"), len(formulas), len(formulas) + 1, os.path.basename(args.chapter)))
    if not args.apply:
        print("※ --apply 를 주면 실제로 쓴다")
        return 0
    with open(args.chapter, "w", encoding="utf-8", newline="") as fh:
        fh.write(out)
    # ★ 쓴 뒤 그 장의 lint 를 돌려 걸리면 되돌린다 (2026-09-18 실측: 카드 7장 중 3장이 가운데점 셋 ·
    #   `\cdot` · 슬래시 분수로 걸려 파일을 손으로 다시 고쳤다 — 손 편집이 이 도구를 만든 이유였다).
    if args.no_lint:
        return 0
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                     "lint_chapter.py"), args.chapter],
                       capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        with open(args.chapter, "w", encoding="utf-8", newline="") as fh:
            fh.write(raw)
        print("\n".join(l for l in r.stdout.splitlines() if "[FAIL]" in l))
        sys.exit("lint 에 걸려 되돌렸다 — 카드 파일을 고쳐 다시 준다")
    print("  [lint 통과]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
