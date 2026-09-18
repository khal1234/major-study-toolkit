# -*- coding: utf-8 -*-
r"""치수 계열의 **굵기**를 형상선의 절반(`checks_svg.DIM_EXT_WIDTH`)으로 맞춘다 — 전수 교정.

★ 왜 열렸나 (2026-09-09, 사용자 지적)
  *[발화 생략]*

  같은 날 `checks_svg.DIM_EXT_WIDTH` 가 **1.2 → 1.0** 으로 내려갔다(KS B 0001·ISO 128 의
  굵은:가는 = 2:1 이고 이 리포 형상선이 2.0 이다). 그런데 **그것은 앞으로 찍을 것만 바꾼다** —
  이미 데이터에 박힌 SVG 는 1.2 인 채로 남아 형상선과의 비가 1.67:1 이었고, 회로도처럼 선이
  촘촘한 그림에서 치수가 형상선과 안 갈렸다. 「자만 고치고 이미 쓴 콘텐츠를 안 보는」 것이
  이 리포의 반복 결함이라(AGENTS 규칙 7⑵⑶), 새 자와 **같은 배치**에서 이 도구를 낸다.

무엇을 하나
  `class='dim'`·`id='dim-…'` 그룹 **안**의 선(`<line>`·비삼각 `<path>`·`<polyline>`)에서
  굵기가 `DIM_EXT_WIDTH` 보다 굵고 `checks_content.DIM_EXTENSION_MAX_WIDTH` 이하인 것을
  `DIM_EXT_WIDTH` 로 내린다. **수를 여기 다시 적지 않는다** — 두 상수가 정본이다.

무엇을 안 하나 (사람이 판정하는 자리 — 목록에만 찍는다)
  · **태그 밖의 선** — 치수인지 형상인지 도구가 못 가른다. 세는 자는
    `tools/audit_untagged_dimensions.py`(목록만 낸다).
  · **화살촉 삼각형**(`stroke-width=ARROW_SEAM_STROKE`) — 테두리는 이음매를 메우는 다른 규격이다.
  · **상한을 넘는 굵기** — 치수 그룹 안이어도 형상선일 수 있다.
  · **`<g>` 자신의 굵기 중 화살촉에도 걸리는 것** — 그룹 굵기를 내리면 테두리까지 얇아진다.

쓰는 법
  python tools/fix_dim_stroke_width.py                       # 전 과목 미리보기
  python tools/fix_dim_stroke_width.py --only=<과목폴더>
  python tools/fix_dim_stroke_width.py --skip=<과목폴더>/ch01.json,<과목폴더>/ch02.json
  python tools/fix_dim_stroke_width.py --apply
"""
import argparse
import copy
import json
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
from buildlib.checks_content import (                                      # noqa: E402
    DIM_EXTENSION_MAX_WIDTH, iter_chapter_diagrams,
)
from buildlib.checks_svg import (                                          # noqa: E402
    DIM_EXT_WIDTH, _attr, _is_triangle_path, _tagged_group_spans,
)
from buildlib.jsontext import write_chapter                                # noqa: E402

# 굵기를 갖는 태그. `<g>` 는 상속시키므로 따로 판정한다(아래 `_group_is_safe`).
TAG_RE = re.compile(r"<(g|line|path|polyline|polygon|rect|circle)\b([^>]*?)/?>")
WIDTH_RE = re.compile(r"stroke-width\s*=\s*(['\"])\s*([-\d.]+)\s*\1")


def _fmt(value):
    """생성기(`svg_dimension`)와 **같은 표기**로 찍는다 — 새로 그린 것과 고친 것이 갈리면 안 된다."""
    return "%.2f" % float(value)


def _outermost(spans):
    """겹치는 그룹에서 바깥 것만. 안쪽까지 세면 같은 선을 두 번 고친 것으로 보고한다."""
    out = []
    for start, end in sorted((s, e) for s, e, _b in spans):
        if any(a <= start and end <= b for a, b in out):
            continue
        out.append((start, end))
    return out


def _elements_in(svg, start, end):
    """(태그 시작, 태그이름, 속성문자열, **속성문자열의 절대 위치**) — 그룹 범위 안의 태그.

    ★ 절대 위치를 함께 낸다. 속성 안에서 찾은 오프셋을 «태그 시작 + 1» 로 환산하면 태그 이름
      길이만큼 어긋나 **엉뚱한 자리를 갈아끼운다** — 조용히 SVG 를 깨뜨리는 부류다.
    """
    return [(m.start(), m.group(1), m.group(2), m.start(2))
            for m in TAG_RE.finditer(svg, start, end)]


def _group_is_safe(svg, pos, span_end):
    """`<g>` 의 굵기를 내려도 **화살촉 테두리에 안 걸리나**. 순수 함수.

    그룹 굵기는 상속된다 — 안쪽 삼각형이 자기 `stroke-width` 를 안 가졌으면 그룹을 내리는 순간
    화살촉 테두리(`ARROW_SEAM_STROKE`)까지 얇아진다. 그 자리는 사람이 본다.
    """
    for _p, tag, a, _s in _elements_in(svg, pos, span_end):
        if tag == "path" and _is_triangle_path(_attr(a, "d", "") or ""):
            if not WIDTH_RE.search(a):
                return False
    return True


def plan_svg(svg):
    """(새 svg, 바꾼 목록, 건너뛴 목록). **순수 함수** — 테스트가 직접 부른다.

    목록의 한 줄은 `(태그, 옛 굵기, 사유)` 이고, 바꾼 쪽의 사유는 빈 문자열이다.
    """
    spans = _outermost(_tagged_group_spans(svg, ("dim",)))
    if not spans:
        return svg, [], []
    changed, skipped, edits = [], [], []
    for start, end in spans:
        for pos, tag, attrs, attrs_at in _elements_in(svg, start, end):
            hit = WIDTH_RE.search(attrs)
            if not hit:
                continue
            try:
                width = float(hit.group(2))
            except ValueError:
                continue
            triangle = tag == "path" and _is_triangle_path(_attr(attrs, "d", "") or "")
            if triangle:
                skipped.append((tag, width, "화살촉 테두리 — 다른 규격이다"))
                continue
            if width <= DIM_EXT_WIDTH:
                continue                       # 이미 규격 안이다(잡음 diff 를 안 만든다)
            if width > DIM_EXTENSION_MAX_WIDTH:
                skipped.append((tag, width, "상한 %g 초과 — 치수 그룹 안이어도 형상선일 수 있다"
                                % DIM_EXTENSION_MAX_WIDTH))
                continue
            if tag == "g" and not _group_is_safe(svg, pos, end):
                skipped.append((tag, width, "그룹 굵기가 화살촉 테두리에도 걸린다"))
                continue
            edits.append((pos, attrs_at + hit.start(), attrs_at + hit.end()))
            changed.append((tag, width, ""))
    # 뒤에서부터 갈아끼운다 — 앞을 먼저 바꾸면 뒤 좌표가 밀린다.
    out = svg
    for _pos, lo, hi in sorted(edits, reverse=True):
        quote = out[lo:hi][-1]
        out = out[:lo] + "stroke-width=" + quote + _fmt(DIM_EXT_WIDTH) + quote + out[hi:]
    return out, changed, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description="치수 계열 굵기를 규격(DIM_EXT_WIDTH)으로 맞춘다")
    ap.add_argument("--only", help="과목 폴더 이름(부분 일치)")
    ap.add_argument("--skip", default="", help="건드리지 않을 <과목폴더>/chNN.json 목록(쉼표)")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    ap.add_argument("--fail-only", action="store_true", help="합계만 찍는다")
    args = ap.parse_args(argv)

    subjects = audit_content.subject_dirs()
    if audit_content.reject_unmatched_only(args.only, subjects):
        return 1
    subjects = audit_content.only_matches(args.only, subjects)
    skip = {s.replace("\\", "/").strip() for s in args.skip.split(",") if s.strip()}

    print("규격: 치수 계열 굵기 %g (형상선의 절반) · 상한 %g — 정본은 checks_svg.DIM_EXT_WIDTH"
          % (DIM_EXT_WIDTH, DIM_EXTENSION_MAX_WIDTH))
    moved = skipped_n = held = 0
    per_subject = []
    for subject in subjects:
        folder = os.path.basename(subject)
        subject_moved, subject_figs = 0, []
        for name in sorted(os.listdir(subject)):
            if not re.fullmatch(r"ch\d{2}\.json", name):
                continue
            path = os.path.join(subject, name)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            before = copy.deepcopy(data)
            touched = []
            for fig_id, dg in iter_chapter_diagrams(data):
                svg = str(dg.get("svg") or "")
                if not svg:
                    continue
                new_svg, changed, skips = plan_svg(svg)
                skipped_n += len(skips)
                if not args.fail_only:
                    for tag, width, why in skips:
                        print("  [건너뜀] %-40s <%s> %g — %s" % (folder + "/" + fig_id,
                                                                tag, width, why))
                if not changed:
                    continue
                if folder + "/" + name in skip:
                    held += len(changed)
                    print("  [보류] %-42s %d건 — --skip 목록(다른 세션이 편집 중)"
                          % (folder + "/" + name + " " + fig_id, len(changed)))
                    continue
                touched.append((fig_id, changed))
                dg["svg"] = new_svg
                subject_moved += len(changed)
                moved += len(changed)
                subject_figs.append(fig_id)
                if not args.fail_only:
                    print("  %-44s %s → %s (%d건)"
                          % (folder + "/" + fig_id,
                             ", ".join(_fmt(w) for _t, w, _y in changed),
                             _fmt(DIM_EXT_WIDTH), len(changed)))
            if touched and args.apply:
                state, why = write_chapter(path, before, data)
                print("[%s] %s%s" % (state, folder + "/" + name, (" — " + why) if why else ""))
                if state == "skipped":
                    return 1
        if subject_moved:
            per_subject.append((folder, subject_moved, len(set(subject_figs))))

    print("\n합계 — 바꿈 %d건 · 건너뜀 %d건 · 보류 %d건 · 훑은 과목 %d개%s"
          % (moved, skipped_n, held, len(subjects),
             "" if args.apply else " (미리보기 — --apply 로 반영)"))
    for folder, count, figs in per_subject:
        print("  · %-24s %3d건 / 삽화 %d개" % (folder, count, figs))
    if not subjects:
        print("★ 훑은 과목이 0개다 — 이 「0건」은 «없다»가 아니라 «못 봤다»이다.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
