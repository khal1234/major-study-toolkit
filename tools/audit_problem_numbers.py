"""문항의 수치가 서로 어긋나는가 — 지문 ↔ 답 ↔ 삽화.

열린 날 2026-08-07. **무엇이 새어나갔나:** 열역학 ch04-p01 의 지문은
`P = 320 kPa, V₁ = 0.015, V₂ = 0.062 m³` (답 15.0 kJ) 인데
`expectedOutput` 은 `6.00 kJ` 이었고 삽화는 `200 kPa · 0.02 · 0.05` 를 그리고 있었다.
지문의 숫자만 나중에 바뀌고 **답과 삽화가 따라오지 않은** 것이다.

빌드가 이걸 통과시킨 이유는 단순하다 — 세 자리(지문·답·삽화)가 **서로를 전혀 안 본다.**
각각은 문법적으로 멀쩡한 문자열이라 어느 검사에도 걸리지 않는다.

**두 층으로 낸다.** 확실한 것만 빌드가 막고, 애매한 것은 여기서 사람에게 넘긴다:

  [어긋남] 삽화가 문항 수치를 **하나도** 안 그린다 / expectedOutput 의 값이 어디에도 없다
           → 빌드 **C37** 이 같은 판정으로 막는다 (`checks_content.problem_number_issues`)
  [참고]   삽화에 문항에 없는 값이 섞여 있다
           → 대개 정당하다. 실측 7건 중 5건이 그랬다 —
             `나머지 55%`(45% 의 나머지) · 온도 눈금 `10·20·30·40`.
             **판정은 사람이 한다.** 어긋난 것이 보이면 지문·답·삽화 중 무엇이 옳은지 정한다.

    python tools/audit_problem_numbers.py [--all]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_content import CHAPTERS, load  # noqa: E402
from buildlib.checks_content import (  # noqa: E402
    _item_numbers, _svg_shown_numbers, problem_numbers,
)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VERBOSE = "--all" in sys.argv


def rows_for(data):
    """한 챕터의 (등급, 대상, 설명) 목록."""
    rows = []
    for coll in ("practice", "problems"):
        for item in data.get(coll) or []:
            if not isinstance(item, dict):
                continue
            pid = item.get("id", "?")
            known = _item_numbers(item)

            exp = item.get("expectedOutput")
            if isinstance(exp, str) and exp:
                rest = _item_numbers({k: v for k, v in item.items()
                                      if k != "expectedOutput"})
                stray = sorted(problem_numbers(exp) - rest)
                if stray and rest:
                    rows.append(("어긋남", pid,
                                 "expectedOutput 의 " + ", ".join(stray)
                                 + " 가 지문·풀이·정답 어디에도 없다"))

            for fig in item.get("diagrams") or []:
                if not isinstance(fig, dict) or fig.get("numericLabels") != "intentional":
                    continue
                fid = fig.get("id", "?")
                shown = _svg_shown_numbers(fig.get("svg", ""))
                if not shown or not known:
                    continue
                if not (shown & known):
                    rows.append(("어긋남", fid,
                                 "문항의 수치를 하나도 안 그린다 — 삽화 "
                                 + ", ".join(sorted(shown)[:6])))
                else:
                    stray = sorted(shown - known)
                    if stray:
                        rows.append(("참고", fid,
                                     "삽화에만 있는 값: " + ", ".join(stray[:6])
                                     + (" …" if len(stray) > 6 else "")))
    return rows


def main():
    print("문항 수치 대조 — 지문·풀이·답이 가진 값과 삽화·정답 줄을 맞춰 본다")
    print("[어긋남] 은 빌드 C37 이 함께 막는다 · [참고] 는 대개 정당하니 사람이 판정한다")
    bad = note = 0
    for ch in CHAPTERS:
        rows = rows_for(load(ch))
        shown = rows if VERBOSE else [r for r in rows if r[0] == "어긋남"]
        bad += sum(1 for r in rows if r[0] == "어긋남")
        note += sum(1 for r in rows if r[0] == "참고")
        skipped = len(rows) - len(shown)
        tail = f" (참고 {skipped}건 숨김 — --all)" if skipped else ""
        print(f"\n-- {ch}: 어긋남 {sum(1 for r in rows if r[0] == '어긋남')}건{tail}")
        for grade, target, why in shown:
            print(f"   [{grade}] {target:<24} {why}")
    print(f"\n합계 — 어긋남 {bad}건 · 참고 {note}건")
    print("\n(읽기 전용 감사 — 파일을 쓰지 않았다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
