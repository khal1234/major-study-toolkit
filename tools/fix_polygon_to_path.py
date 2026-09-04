# -*- coding: utf-8 -*-
"""`<polygon points>` 을 `<path d='M… L… Z'>` 로 바꾼다 — 빌드 L7 이 요구하는 형식.

신설 2026-07-30. 왜 이 방향인가 (checks_svg L7 주석이 정본):
    이 리포의 SVG 판정 함수는 **전부 `<path d='…Z'/>` 를 전제**한다 —
    `_arrowhead_connection_issues`(G1: 선 끝이 화살촉 밑변 중앙인가) ·
    `filled_triangle_count`(L4) · L2 의 `has_arrowhead`. `checks_svg.py` 전체에
    `polygon` 이라는 문자열이 **한 번도 없었다.**

    그래서 `<polygon>` 으로 그린 화살촉은 *규격을 통과한 것이 아니라 검사를 받지 않은 것*이다.
    ★ math 실측(2026-07-30): 자를 polygon 까지 넓혀 보니 그 즉시
    `fig-existence-rect` 의 초기점 지시 화살촉이 **끝점 7.00px 못 미침**으로 드러났다 —
    그 위반은 규격이 생긴 뒤 내내 있었고 아무도 못 봤다.

    **어느 쪽을 고칠 것인가:** 판정 함수마다 polygon 을 가르치면 하나만 빠져도 그 자리가
    조용히 꺼진다(그게 지금 상태다). 집 형식을 하나로 두는 편이 싸고 확실하다 —
    SVG 로서 동등하고 렌더 결과도 같다. 그래서 데이터를 형식에 맞춘다.

**손으로 고치지 않는 이유:** 좌표를 옮겨 적다가 한 점이라도 틀리면 화살촉이 뒤틀리고,
그건 렌더 검수로만 잡힌다. 변환은 기계가 한다(값을 그대로 옮기므로 형상이 바뀌지 않는다).

    python tools/fix_polygon_to_path.py                       # 미리보기
    python tools/fix_polygon_to_path.py --chapter=ch01.json
    python tools/fix_polygon_to_path.py --apply
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_content                                                       # noqa: E402
from buildlib.checks_content import iter_chapter_diagrams                  # noqa: E402

DATA = audit_content.DATA
POLYGON_RE = re.compile(r"<polygon\b([^>]*?)/?>")
POINTS_RE = re.compile(r"\bpoints\s*=\s*(['\"])(.*?)\1", re.S)
NUM = r"-?(?:\d+(?:\.\d*)?|\.\d+)"


def points_to_d(points):
    """`points` 문자열 → `d` 문자열. 좌표를 **그대로** 옮긴다(형상 불변).

    쌍이 3개 미만이면 None — 삼각형·다각형이 아니라 잘못된 값이므로 손대지 않는다.
    """
    nums = re.findall(NUM, points or "")
    if len(nums) < 6 or len(nums) % 2:
        return None
    pairs = [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]
    head = "M" + pairs[0][0] + "," + pairs[0][1]
    rest = " ".join("L" + x + "," + y for x, y in pairs[1:])
    return head + " " + rest + " Z"


def convert_svg(svg):
    """(바뀐 svg, 변환 건수, 건너뛴 points 목록)."""
    out, converted, skipped, last = [], 0, [], 0
    for m in POLYGON_RE.finditer(svg):
        attrs = m.group(1)
        pm = POINTS_RE.search(attrs)
        d = points_to_d(pm.group(2)) if pm else None
        if d is None:
            skipped.append(pm.group(2) if pm else "(points 없음)")
            continue
        # points= 를 d= 로 갈아끼우고 나머지 속성(fill·stroke·opacity…)은 그대로 둔다.
        new_attrs = attrs[:pm.start()] + "d='" + d + "'" + attrs[pm.end():]
        out.append(svg[last:m.start()])
        out.append("<path" + new_attrs + "/>")
        last = m.end()
        converted += 1
    out.append(svg[last:])
    return "".join(out), converted, skipped


def run(path, only_ids, apply):
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    ch = json.loads(raw)
    total, figs = 0, 0
    for fid, dg in iter_chapter_diagrams(ch):
        if only_ids and fid not in only_ids:
            continue
        svg = str(dg.get("svg") or "")
        if "<polygon" not in svg:
            continue
        new_svg, n, skipped = convert_svg(svg)
        for bad in skipped:
            print("  건너뜀 %-22s points=%r — 좌표쌍이 3개 미만" % (fid, bad[:40]))
        if not n:
            continue
        # JSON 문자열 안의 SVG 를 **문자열 replace 로만** 바꾼다(정규식 replace 금지 — AGENTS 함정).
        raw = raw.replace(json.dumps(svg, ensure_ascii=False)[1:-1],
                          json.dumps(new_svg, ensure_ascii=False)[1:-1])
        print("  변환 %-24s polygon %d개 → path" % (fid, n))
        total += n
        figs += 1
    if apply and total:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(raw)
        print("  → 저장했다. 빌드와 렌더 검수를 반드시 돌릴 것.")
    return figs, total


def main():
    apply = "--apply" in sys.argv
    only_ch = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    only_ids = {a.split("=", 1)[1] for a in sys.argv if a.startswith("--id=")}
    print("[대상] " + os.path.basename(DATA))
    grand_figs = grand = 0
    for name in sorted(os.listdir(DATA)):
        if not re.fullmatch(r"ch\d+\.json", name):
            continue
        if only_ch and name != only_ch:
            continue
        figs, n = run(os.path.join(DATA, name), only_ids or None, apply)
        grand_figs += figs
        grand += n
    print("\n합계: 삽화 %d개 · polygon %d개" % (grand_figs, grand))
    if not apply:
        print("미리보기다. 반영하려면 --apply 를 붙일 것.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
