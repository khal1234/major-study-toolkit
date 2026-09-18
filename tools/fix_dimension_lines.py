# -*- coding: utf-8 -*-
"""치수·투영·기준선의 파선을 가는 실선으로 되돌리고, 진짜 숨은선은 태깅한다.

신설 2026-07-30. 사용자 지적 3회(19/62 · 연습문제 7 · 연습문제 8):
    *[발화 생략]*
    *[발화 생략]*

규격(AGENTS 삽화 표준, 2026-07-29 개정): **치수선·치수보조선은 둘 다 가는 실선 + 채운 화살촉.
파선은 숨은선의 몫이다.** 그런데 ch01 의 가는 파선 30곳이 **전부 태깅되지 않아**
빌드의 치수 규격 검사(checks_svg L2)를 한 번도 받지 않았다 — 빌드가 조용한 것이
'규격을 지켰다'가 아니었다.

**손으로 고치지 않는 이유:** 삽화마다 사람이 판단하면 그 판단이 갈리고, 갈린 것이 곧
이 규격이 없애려는 결함이다(캡션 위계 때와 같은 실패 형태).

    python tools/fix_dimension_lines.py --chapter=ch01           # 미리보기
    python tools/fix_dimension_lines.py --chapter=ch01 --apply   # 반영
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

THIN = 1.5  # 이보다 굵으면 형상선이다 — 건드리지 않는다.

# ── 파선으로 남겨야 하는 것 = **진짜 숨은선**뿐이다 ───────────────────────────
# 키는 (삽화 id, d/좌표에 들어 있는 고유 조각). 사유를 반드시 적는다 —
# 사유 없는 면제는 '아직 안 고친 것'과 구별되지 않는다(AGENTS 경고 유예 규칙과 같은 논리).
KEEP_DASHED = {
    ("fig-d-fluid-element", "M240 95 L248 81"):
        "등축투영에서 가려진 뒤쪽 모서리 — 숨은선이므로 파선이 맞다.",
    ("fig-d-fluid-element", "M248 81 L293 55"):
        "등축투영에서 가려진 뒤쪽 모서리 — 숨은선이므로 파선이 맞다.",
    ("fig-closed-open-isolated", "M479 165.3 H497"):
        "고립계에서 '막힌 경로'를 뜻하는 표식이다. 치수선이 아니라 의미 기호이며 "
        "끊긴 선 자체가 '통과하지 못한다'를 나타낸다.",
}
# 숨은선으로 남긴 것에 붙일 표식 — 이게 있어야 빌드가 '태깅 안 된 파선'과 구별한다.
HIDDEN_MARK = "hidden-edge"

ELEMENT = re.compile(r"<(line|path|polyline)\b([^>]*)/?>")
# ★ 그룹에 건 파선 (보강 2026-07-30). 처음 구현은 요소 자신의 속성만 봐서
# `<g stroke-dasharray='4,3'><line …/></g>` 를 통째로 놓쳤다 — ch01 에서만 16곳이 그랬다.
# 검사(checks_svg)도 같은 사각지대였고, 사용자가 눈으로 먼저 잡았다.
GROUP = re.compile(r"<g\b([^>]*)>")


def stroke_width(attrs):
    m = re.search(r"stroke-width=['\"]([\d.]+)", attrs)
    return float(m.group(1)) if m else None


def keep_reason(fig_id, tag_src):
    for (fid, needle), why in KEEP_DASHED.items():
        if fid == fig_id and needle in tag_src:
            return why
    return None


def fix_svg(fig_id, svg):
    """되돌린 개수와 새 SVG를 낸다. 순수 함수 — 테스트 대상."""
    changed, kept = [], []

    def repl(m):
        whole, attrs = m.group(0), m.group(2)
        if "stroke-dasharray" not in attrs:
            return whole
        width = stroke_width(attrs)
        if width is not None and width > THIN:
            return whole                      # 형상선은 대상이 아니다
        why = keep_reason(fig_id, whole)
        if why:
            kept.append(why)
            if HIDDEN_MARK in attrs:
                return whole
            # 숨은선이라는 것을 명시한다 — 태깅해야 빌드가 '남겨둔 것'으로 인정한다.
            return whole.replace("<" + m.group(1), "<" + m.group(1)
                                 + " class='" + HIDDEN_MARK + "'", 1)
        changed.append(whole[:70])
        return re.sub(r"\s*stroke-dasharray=['\"][^'\"]*['\"]", "", whole)

    def repl_group(m):
        whole, attrs = m.group(0), m.group(1)
        if "stroke-dasharray" not in attrs:
            return whole
        width = stroke_width(attrs)
        if width is not None and width > THIN:
            return whole
        why = keep_reason(fig_id, whole)
        if why:
            kept.append(why)
            if HIDDEN_MARK in attrs:
                return whole
            return whole.replace("<g", "<g class='" + HIDDEN_MARK + "'", 1)
        changed.append(whole[:70])
        return re.sub(r"\s*stroke-dasharray=['\"][^'\"]*['\"]", "", whole)

    return GROUP.sub(repl_group, ELEMENT.sub(repl, svg)), changed, kept


def walk(node, owner="?"):
    if isinstance(node, dict):
        own = node.get("id", owner)
        for d in node.get("diagrams") or []:
            if isinstance(d, dict) and d.get("svg"):
                yield d
        for key, value in node.items():
            if key != "diagrams":
                yield from walk(value, own)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item, owner)


def main():
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    apply_changes = "--apply" in sys.argv
    total, kept_total, touched_files = 0, 0, []

    for subject in sorted(os.listdir(DATA)):
        sub_dir = os.path.join(DATA, subject)
        if not os.path.isdir(sub_dir):
            continue
        for name in sorted(os.listdir(sub_dir)):
            if not re.fullmatch(r"ch\d+\.json", name):
                continue
            if only and os.path.splitext(name)[0] != only:
                continue
            path = os.path.join(sub_dir, name)
            with open(path, encoding="utf-8") as fh:
                chapter = json.load(fh)
            file_changed = False
            for d in walk(chapter):
                new_svg, changed, kept = fix_svg(d["id"], d["svg"])
                if kept:
                    kept_total += len(kept)
                    for why in kept:
                        print("  [유지] %-28s %s" % (d["id"], why))
                if new_svg != d["svg"]:
                    file_changed = True
                    total += len(changed)
                    for snippet in changed:
                        print("  [실선화] %-28s %s" % (d["id"], snippet))
                    d["svg"] = new_svg
            if file_changed and apply_changes:
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    json.dump(chapter, fh, ensure_ascii=False, indent=2)
                    fh.write("\n")
                touched_files.append(os.path.relpath(path, ROOT))

    print("\n" + "=" * 62)
    print("실선으로 되돌림 %d건 · 숨은선으로 유지 %d건" % (total, kept_total))
    if apply_changes:
        print("반영한 파일: " + (", ".join(touched_files) if touched_files else "없음"))
    else:
        print("미리보기다. 반영하려면 --apply 를 붙일 것.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
