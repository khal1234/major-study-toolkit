# -*- coding: utf-8 -*-
r"""**태깅 없이 치수 노릇 하는 양방향 화살표**를 전 과목에서 찾는다 — 목록만 낸다(게이트 아님).

    python tools/audit_untagged_dimensions.py
    python tools/audit_untagged_dimensions.py --only=<과목폴더>

★ 왜 열렸나 (2026-09-09). `docs/삽화-규격.md` 가 스스로 적어 둔 구멍이다 —
  *[발화 생략]* 태깅을 저자 선언으로 두는 것 자체는 옳다(이름으로 추측하면
  삽화마다 갈린다, `dim_arrow_positions` 독스트링). 문제는 **선언을 빠뜨린 자리를 세는 자가
  없었다**는 것이다 — 그래서 치수 굵기·화살촉 비율·라벨 간격 규격이 그 삽화들에서 통째로 안 돌았다.

무엇을 세나
  한 삽화 안의 **태깅 안 된 화살촉 두 개**가 ⑴ 방향이 서로 반대이고 ⑵ 같은 직선 위에 있고
  ⑶ 화살촉 길이보다 멀리 떨어져 있으면 «양방향 치수 흉내» 후보로 센다.
  안쪽을 향하든(→ ←) 바깥을 향하든(← →) 둘 다 제도에서 쓰는 치수 형태라 둘 다 센다.

무엇을 안 하나 — **고치지 않는다.**
  무엇을 재는 화살표인지는 그림마다 다르고 사람이 봐야 안다(치수가 아니라 「힘의 짝」·「대칭」을
  뜻하는 양방향 화살표가 정당하게 있다). **게이트로도 안 켠다** — 첫 실측 전에 exit 1 을 켜면
  경보 피로로 검사기가 죽는다(`audit_theory_figure_reasons` 가 같은 판정을 했다).

**사람이 판정하는 자리:** 후보 하나하나가 «치수인가 아닌가». 치수면 `<g class='dim'>` 으로 묶고
`python tools/fix_dim_stroke_width.py --apply` 를 다시 돌린다.
"""
import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import audit_content                                                       # noqa: E402
from buildlib.checks_content import iter_chapter_diagrams                  # noqa: E402
from buildlib.checks_svg import arrow_geometry, dim_arrow_positions        # noqa: E402

# 방향이 «반대»라고 볼 내적 상한. 정확히 -1 을 요구하면 좌표 반올림 하나에 후보가 사라진다.
OPPOSITE_DOT_MAX = -0.95
# 같은 직선 위라고 볼 수직 어긋남(SVG px). 화살촉 폭(≈8px)의 절반 아래로 잡는다 —
# 그보다 어긋나면 화면에서 두 줄로 보인다.
COLLINEAR_TOL_PX = 4.0


def _unit(arrow):
    dx = arrow["tip"][0] - arrow["base"][0]
    dy = arrow["tip"][1] - arrow["base"][1]
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n else None


def untagged_dimension_pairs(svg):
    """[(화살표A, 화살표B, 형태)] — 태깅 없는 양방향 치수 후보. **순수 함수**(테스트가 부른다).

    `형태` 는 `'바깥'`(← →, 표준 치수) 또는 `'안쪽'`(→ ←, 좁은 치수의 뒤집은 표기)이다.
    """
    dims = dim_arrow_positions(svg)
    arrows = [a for a in arrow_geometry(svg) if a["pos"] not in dims]
    out = []
    for i, a in enumerate(arrows):
        ua = _unit(a)
        if not ua:
            continue
        for b in arrows[i + 1:]:
            ub = _unit(b)
            if not ub:
                continue
            if ua[0] * ub[0] + ua[1] * ub[1] > OPPOSITE_DOT_MAX:
                continue
            vx = b["tip"][0] - a["tip"][0]
            vy = b["tip"][1] - a["tip"][1]
            along = vx * ua[0] + vy * ua[1]
            perp = abs(vx * (-ua[1]) + vy * ua[0])
            if perp > COLLINEAR_TOL_PX:
                continue
            if abs(along) <= max(a["length"], b["length"]):
                continue                      # 같은 화살표의 두 겹침·아주 짧은 쌍은 안 센다
            out.append((a, b, "안쪽" if along > 0 else "바깥"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="태깅 없는 양방향 치수 후보 — 목록만")
    ap.add_argument("--only", help="과목 폴더 이름(부분 일치)")
    ap.add_argument("--fail-only", action="store_true", help="합계만 찍는다")
    args = ap.parse_args(argv)

    subjects = audit_content.subject_dirs()
    if audit_content.reject_unmatched_only(args.only, subjects):
        return 1
    subjects = audit_content.only_matches(args.only, subjects)

    total = tagged_figs = 0
    per_subject = []
    for subject in subjects:
        folder = os.path.basename(subject)
        rows = []
        for name in sorted(os.listdir(subject)):
            if not re.fullmatch(r"ch\d{2}\.json", name):
                continue
            with open(os.path.join(subject, name), encoding="utf-8") as fh:
                data = json.load(fh)
            for fig_id, dg in iter_chapter_diagrams(data):
                svg = str(dg.get("svg") or "")
                if not svg:
                    continue
                if dim_arrow_positions(svg):
                    tagged_figs += 1
                for a, b, shape in untagged_dimension_pairs(svg):
                    rows.append((name, fig_id, shape, a["tip"], b["tip"]))
        if rows:
            per_subject.append((folder, len(rows)))
            total += len(rows)
            if not args.fail_only:
                print("\n[" + folder + "]")
                for name, fig_id, shape, ta, tb in rows:
                    print("  %-14s %-34s %s 향 (%.0f,%.0f)—(%.0f,%.0f)"
                          % (name, fig_id, shape, ta[0], ta[1], tb[0], tb[1]))

    print("\n합계 — 후보 %d건 · 훑은 과목 %d개 · 치수 태깅이 이미 있는 삽화 %d개"
          % (total, len(subjects), tagged_figs))
    for folder, count in per_subject:
        print("  · %-24s %3d건" % (folder, count))
    if not subjects:
        print("★ 훑은 과목이 0개다 — 이 「0건」은 «없다»가 아니라 «못 봤다»이다.")
        return 1
    print("※ 게이트가 아니다 — 치수인지 아닌지는 사람이 그림을 보고 판정한다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
