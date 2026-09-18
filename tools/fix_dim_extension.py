# -*- coding: utf-8 -*-
"""치수보조선의 **간격**(물체에서 띄운 양)과 **넘김**(치수선을 지나 더 나간 양)을 규격에 맞춘다.

왜 있나 (열린 날 2026-07-31, 사용자 지적):
    *[발화 생략]*
    *[발화 생략]*

    AGENTS 는 *[발화 생략]* 라고만 적고 **수치가 없었다.** 그래서 삽화마다 사람이 눈으로
    정했고 실제로 갈라졌다(같은 viewBox 폭 500 에서 볼트 `3/8`, 스프링 `6/0`).
    ★ 이 리포에서 이미 배운 것 — **재는 도구만 만들고 맞추는 도구를 안 만들면 규격은 장식이 된다**
    (라벨 간격 1em 이 정확히 그렇게 됐다, 원장 2026-07-30). 그래서 자와 함께 이 도구를 낸다.

기준값은 `buildlib/checks_content.py` 의 `DIM_GAP_SCREEN_PX`·`DIM_OVERSHOOT_SCREEN_PX` 가 정본이고,
근거는 **사용자가 적합하다고 판정한 볼트 삽화**(`fig-elastic-rod-work`)의 실측값이다.

건드리지 않는 것(판단이 필요한 자리 — 사람 몫으로 남기고 목록에 찍는다):
  · 재는 면을 못 찾은 보조선(`간격 없음`) — 무엇을 기준으로 띄울지가 정해지지 않았다
  · 길이 80px 초과 — 기준선·형상선일 수 있다(`fig-p05-barometer` 의 액면선이 그 부류)

사용:
    python tools/fix_dim_extension.py                     # 전 챕터 미리보기
    python tools/fix_dim_extension.py --chapter=ch02.json # 한 챕터만
    python tools/fix_dim_extension.py --apply             # 실제 수정
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_content import (                                      # noqa: E402
    DIM_EXTENSION_MAX_LEN, DIM_GAP_SCREEN_PX, DIM_OVERSHOOT_SCREEN_PX,
    dim_extension_fixes, dim_extension_rows, iter_chapter_diagrams,
)
import audit_content                                                       # noqa: E402


def _fmt(v):
    s = "%.2f" % float(v)
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _same(a, b):
    return all(abs(p - q) <= 0.05 for p, q in zip(a, b))


def _replace_line(svg, old, new):
    """좌표가 `old` 인 보조선 하나를 `new` 로 바꾼 SVG (못 찾으면 None).

    ★ `<line>` 과 `<path>` 를 **둘 다** 본다. 처음엔 `<line>` 만 봤는데 실측에서 11건이
      *[발화 생략]* 로 빠졌다 — 같은 보조선을 `<path d='M264 224V270'/>` 로
      그린 삽화들이다. 한쪽 문법만 보는 도구는 **그 문법을 쓰는 삽화에서 조용히 아무것도 안 한다**
      (원장 2026-07-30 '홑따옴표만 보던 수정 도구'와 같은 부류).
    """
    for m in re.finditer(r"<line\b[^>]*/?>", svg):
        tag = m.group(0)
        vals = []
        for key in ("x1", "y1", "x2", "y2"):
            hit = re.search(key + r"='(-?[\d.]+)'", tag)
            vals.append(float(hit.group(1)) if hit else None)
        if None in vals or not (_same(vals, old) or _same(vals, old[2:] + old[:2])):
            continue
        order = ("x1", "y1", "x2", "y2") if _same(vals, old) else ("x2", "y2", "x1", "y1")
        fixed = tag
        for key, value in zip(order, new):
            fixed = re.sub(key + r"='-?[\d.]+'", key + "='" + _fmt(value) + "'", fixed, count=1)
        return svg[:m.start()] + fixed + svg[m.end():]

    # ★ 하위 경로가 **여럿인** `d` 도 본다 — `d='M576 114 H603 M576 276 H603'` 처럼 보조선 둘을
    #   한 `<path>` 에 담은 삽화가 실측 7건이었다. 통째로 매칭하면 그 삽화들이 조용히 빠진다.
    sub_re = re.compile(r"M\s*(-?[\d.]+)[ ,]\s*(-?[\d.]+)\s*([HV])\s*(-?[\d.]+)")
    for m in re.finditer(r"<path\b[^>]*/?>", svg):
        tag = m.group(0)
        d = re.search(r"d='([^']*)'", tag)
        if not d:
            continue
        for sub in sub_re.finditer(d.group(1)):
            x, y, cmd, to = (float(sub.group(1)), float(sub.group(2)),
                             sub.group(3), float(sub.group(4)))
            pts = (x, y, to, y) if cmd == "H" else (x, y, x, to)
            flip = _same(pts, old[2:] + old[:2])
            if not (_same(pts, old) or flip):
                continue
            a, b = (new[2:], new[:2]) if flip else (new[:2], new[2:])
            moved = ("M%s %s %s%s" % (_fmt(a[0]), _fmt(a[1]), cmd,
                                      _fmt(b[0] if cmd == "H" else b[1])))
            body = d.group(1)[:sub.start()] + moved + d.group(1)[sub.end():]
            fixed = tag.replace("d='" + d.group(1) + "'", "d='" + body + "'")
            return svg[:m.start()] + fixed + svg[m.end():]
    return None


def main():
    ap = argparse.ArgumentParser(description="치수보조선 간격·넘김 규격 맞추기")
    ap.add_argument("--chapter", help="chNN.json 하나만")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    print("규격: 간격 %g px · 넘김 %g px (화면 실효) — 근거는 fig-elastic-rod-work 실측"
          % (DIM_GAP_SCREEN_PX, DIM_OVERSHOOT_SCREEN_PX))
    # `audit_content.CHAPTERS` 는 확장자 없는 `ch01` 형태다 — 여기서 파일명으로 맞춘다.
    names = ([args.chapter] if args.chapter
             else [name + ".json" for name in audit_content.CHAPTERS])
    moved = skipped = 0
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        changed = False
        for fig_id, dg in iter_chapter_diagrams(data):
            svg = str(dg.get("svg") or "")
            if not svg:
                continue
            # 건너뛴 것만 보고한다 — 고칠 수 있는 것은 아래 루프가 따로 찍는다.
            # (둘 다 찍으면 같은 선이 '건너뜀'과 '이동'으로 두 번 나와 보고가 거짓이 된다.)
            for row in dim_extension_rows(svg):
                length = (abs(row["seg"][3] - row["seg"][1]) if row["axis"] == "v"
                          else abs(row["seg"][2] - row["seg"][0]))
                too_long = length > DIM_EXTENSION_MAX_LEN
                over_ok = abs(row["over"] - DIM_OVERSHOOT_SCREEN_PX) <= 0.05
                if too_long or (row["gap"] is None and over_ok):
                    skipped += 1
                    print("  [건너뜀] %-34s (%g,%g)-(%g,%g) — %s"
                          % (fig_id, row["seg"][0], row["seg"][1], row["seg"][2], row["seg"][3],
                             "길이 %g px" % length if too_long else "재는 면 없음(넘김만 규격)"))
            for old, new in dim_extension_fixes(svg):
                out = _replace_line(svg, old, new)
                if out is None:
                    print("  [실패] %-36s (%g,%g)-(%g,%g) — <line> 을 못 찾았다"
                          % (fig_id, old[0], old[1], old[2], old[3]))
                    continue
                print("  %-38s (%g,%g)-(%g,%g) → (%s,%s)-(%s,%s)"
                      % (fig_id, old[0], old[1], old[2], old[3],
                         _fmt(new[0]), _fmt(new[1]), _fmt(new[2]), _fmt(new[3])))
                svg, changed, moved = out, True, moved + 1
            dg["svg"] = svg
        if changed and args.apply:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            print("[쓰기] " + name)
    print("\n이동 %d건 · 건너뜀 %d건%s" % (moved, skipped, "" if args.apply else " (미리보기 — --apply 로 반영)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
