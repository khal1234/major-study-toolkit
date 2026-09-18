# -*- coding: utf-8 -*-
"""'주어진 조건값'에 칩 표기(`data-reveal`)를 붙인다 (신설 2026-08-05, 인박스 R-36).

사용자 지적: *[발화 생략]*
합의(사용자 승인 2026-08-05): **표기는 통일하고 가림 기능(`revealMode`)은 연습문제에 안 넣는다.**

★ 왜 도구인가 — 대상이 한 챕터에만 스무 삽화가 넘는다. 손으로 하면 어떤 삽화는 굵기를 빼고
  어떤 삽화는 안 빼는 식으로 갈라지는데, **그 갈라짐이 바로 R-14 가 없애려던 결함**이다
  (`fix_honorific`·`fix_arrow_scale` 과 같은 형태).

판정 규칙 — `<text>` 하나가 '주어진 조건값'인가:
  ⑴ 숫자를 포함한다(조건값은 수치다)
  ⑵ **답 슬롯을 품지 않는다** — `<tspan id='…answer-slot'>` 이 있으면 그건 구할 값이다
  ⑶ 물음표를 품지 않는다 — `= ?` 는 미지수 표기다
  ⑷ 아직 `data-reveal` 이 없다
붙일 때 **`font-weight='700'` 을 뺀다.** 신호는 칩 하나여야 한다(빌드 C16 이 이미 강제한다 —
칩과 굵기가 함께 있으면 '주어진 값'의 신호가 둘이 된다).

★ 판정은 기계가 못 하는 몫이 남는다 — 눈금 라벨·부품 이름에 숫자가 들어간 경우다.
  그래서 **미리보기가 기본**이고, 붙일 목록을 사람이 읽은 뒤 `--apply` 한다.

    python tools/fix_given_chip.py --chapter=ch02              # 미리보기
    python tools/fix_given_chip.py --chapter=ch02 --apply
    python tools/fix_given_chip.py --chapter=ch02 --only=fig-02-q01
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_content                                                       # noqa: E402
from buildlib.jsontext import write_chapter                                # noqa: E402

DATA = audit_content.DATA
TEXT_RE = re.compile(r"<text([^>]*)>(.*?)</text>", re.S)


def given_text_edits(svg):
    """(옛 <text> 마크업, 새 마크업) 목록. 순수 함수 — 테스트가 직접 부른다."""
    edits = []
    for m in TEXT_RE.finditer(svg):
        attrs, inner = m.group(1), m.group(2)
        if "data-reveal" in attrs:
            continue                                   # 이미 붙었다
        if "answer-slot" in inner or "?" in inner:
            continue                                   # 구할 값이다
        if not re.search(r"\d", inner):
            continue                                   # 수치가 없으면 조건값이 아니다
        new_attrs = re.sub(r"\s*font-weight='700'", "", attrs)
        new_attrs = " data-reveal='1'" + new_attrs
        edits.append((m.group(0), "<text" + new_attrs + ">" + inner + "</text>"))
    return edits


def _problem_diagrams(chapter):
    for prob in (chapter.get("problems") or []):
        for dg in (prob.get("diagrams") or []):
            yield (dg.get("id") or "?"), dg


def main():
    only_ch = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    only_ids = {a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")}
    apply_edits = "--apply" in sys.argv
    print("규칙: 숫자 있음 + 답 슬롯·물음표 없음 → data-reveal 부여 · font-weight 제거")
    print("대상: **연습문제(problems) 삽화만** — 문풀은 이미 적용돼 있다\n")
    touched = 0
    for stem in audit_content.CHAPTERS:
        if only_ch and stem != only_ch:
            continue
        path = os.path.join(DATA, stem + ".json")
        with open(path, encoding="utf-8") as fh:
            chapter = json.load(fh)
        with open(path, encoding="utf-8") as fh:
            fixed = json.load(fh)          # 원본과 사본 — write_chapter 는 둘을 나란히 훑는다
        changed = False
        for fig_id, dg in _problem_diagrams(fixed):
            if only_ids and fig_id not in only_ids:
                continue
            svg = str(dg.get("svg") or "")
            edits = given_text_edits(svg)
            if not edits:
                continue
            new_svg = svg
            for old, new in edits:
                new_svg = new_svg.replace(old, new, 1)
            print("  %-16s %d건" % (fig_id, len(edits)))
            for old, _new in edits:
                body = re.sub(r"<[^>]+>", "", TEXT_RE.match(old).group(2))
                print("      · " + body.strip()[:52])
            touched += 1
            dg["svg"] = new_svg
            changed = True
        if apply_edits and changed:
            # 표기 보존 기록기 — 원본의 들여쓰기·줄바꿈을 건드리지 않는다.
            # 통째 재작성은 손대지 않은 줄까지 diff 로 띄워 검수를 망친다.
            # ★ 넘기는 것은 **챕터 객체 둘**이다. SVG 문자열을 넘기면 `rewrite_text` 의
            #   `json.loads(원문) != before` 에 걸려 **언제나 skipped** 다 (2026-08-05 실측).
            state, why = write_chapter(path, chapter, fixed)
            print("  [%s] %s" % (state, why or stem))
    print("\n삽화 %d건%s" % (touched, "" if apply_edits else " (미리보기 — --apply 로 반영)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
