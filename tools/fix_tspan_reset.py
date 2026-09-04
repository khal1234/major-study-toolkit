# -*- coding: utf-8 -*-
"""아래첨자를 되돌리는 **빈 `<tspan dy>`** 를 고친다 — 뒤따르는 글자를 그 안에 넣는다.

왜 있나 (열린 날 2026-07-31, 사용자 지적):
    *"`E_in - E_out = ΔE_system` 얘네 왜 내려가냐 이런거 만들 때 한줄로 안만들고
      문자 하나하나씩 배치하는거야??"*

    아래첨자 관용구는 `<tspan dy='2.5'>in</tspan>` 로 내리고 `<tspan dy='-2.5'></tspan>` 로
    되돌리는 것인데, **되돌리는 tspan 이 비어 있으면 브라우저가 그 dy 를 적용하지 않는다**
    (dy 는 글리프마다 적용되는데 글리프가 없다). 그래서 첨자 뒤 글자가 내려간 채 남고,
    첨자가 둘이면 두 배로 내려간다 — 화면에서는 글자를 하나씩 흩어 놓은 것처럼 보인다.

    고친 형태는 리포의 다른 삽화가 이미 쓰고 있던 것이다: `<tspan dy='-2.5'> - E</tspan>`.
    즉 **관용구가 두 벌 섞여 있었고 그중 하나가 깨진 것**이다.

판정·검사는 `buildlib/checks_content.empty_dy_reset_issues`(C11)가 정본이고,
잠그는 것은 `test_checks.py::test_empty_dy_reset`.

사용:
    python tools/fix_tspan_reset.py            # 미리보기
    python tools/fix_tspan_reset.py --apply
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_content import iter_chapter_diagrams                  # noqa: E402
import audit_content                                                      # noqa: E402

# 빈 되돌림 tspan + 바로 뒤에 오는 **글자 덩어리**(다음 태그 전까지)를 한 번에 잡는다.
PATTERN = re.compile(r"(<tspan\b[^>]*\bdy='-[\d.]+'[^>]*>)\s*</tspan>([^<]+)")


def fix_svg(svg):
    """고친 SVG 와 바뀐 개수. 순수 함수 — 테스트가 직접 부른다."""
    return PATTERN.subn(lambda m: m.group(1) + m.group(2) + "</tspan>", svg)


def main():
    ap = argparse.ArgumentParser(description="빈 dy 되돌림 tspan 고치기")
    ap.add_argument("--chapter", help="chNN.json 하나만")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    names = ([args.chapter] if args.chapter
             else [name + ".json" for name in audit_content.CHAPTERS])
    total = 0
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        changed = 0
        for fig_id, dg in iter_chapter_diagrams(data):
            svg = str(dg.get("svg") or "")
            fixed, n = fix_svg(svg)
            if n:
                print("  %-38s %d곳" % (fig_id, n))
                dg["svg"], changed = fixed, changed + n
        total += changed
        if changed and args.apply:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            print("[쓰기] %s — %d곳" % (name, changed))
    print("\n총 %d곳%s" % (total, "" if args.apply else " (미리보기 — --apply 로 반영)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
