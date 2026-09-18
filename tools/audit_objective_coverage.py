#!/usr/bin/env python
"""학습목표 위→아래 연결을 잰다 (읽기 전용) — 빌드 검사 C60 의 표 보기.

    python tools/audit_objective_coverage.py "data/<과목>/chNN.json" [--strict]

판정은 `buildlib.checks_content.objective_coverage` 가 정본이다(무엇을 재나 · 문턱 · 못 보는 것은
그 독스트링). 이 자는 그 결과를 목표별 표로 펴서 보인다 — 분모 · 자가점검 · 교재 문제 · 문항 · basis.
`--strict` 는 사유가 하나라도 있으면 exit 1.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from buildlib.checks_content import objective_coverage, objective_map_path  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("사용법: python tools/audit_objective_coverage.py data/<과목>/chNN.json [--strict]")
    path = args[0]
    ch = load(path)
    mp = objective_map_path(path)
    omap = load(mp) if os.path.exists(mp) else None
    rows, unmapped, issues = objective_coverage(ch, omap)
    items = (omap or {}).get("items") or []
    exc = sum(1 for it in items if it.get("excluded"))
    print("분모 %d (%s) · 대응 %d · 제외 %d · 미대응 %d" % (
        len(items), os.path.basename(mp) if omap else "대응표 없음",
        len(items) - exc - len(unmapped), exc, len(unmapped)))
    print("  목표   분모 자가점검 교재문제 문항  basis")
    for i, r in rows.items():
        print("  %-5s %4d %6d %7d %5d  %s" % (i, r["denom"], r["recap"], r["textbook"], r["practice"],
                                              "O" if r["basis"] else "-"))
    for s in issues:
        print("  ✗ " + s)
    print("문제 %d건" % len(issues))
    return 1 if ("--strict" in argv and issues) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
