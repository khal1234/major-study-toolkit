# -*- coding: utf-8 -*-
"""치수 라벨을 **자기 치수 그룹 안으로** 넣고, 규격 위치에서 얼마나 벗어났는지 잰다.

왜 있나 (열린 날 2026-08-04, R-25 · 사용자 지적):
    *[발화 생략]*

    ★ 뿌리는 **라벨이 치수 그룹 밖에 있었다**는 것이다. 그래서 치수 규격을 보는 검사들이
      본선·보조선·화살촉만 재고 라벨은 한 번도 안 봤다(`untagged_dimension_issues` 와 같은 부류).

★★ **이 도구는 좌표를 옮기지 않는다.** 사용자가 준 것은 인스턴스 수정이 아니라 원칙이다 —
   *[발화 생략]*
   자리를 만드는 것은 형상 판단이라 사람 몫이고, 도구가 라벨만 규격 위치로 밀면
   **그 원칙을 정면으로 어긴다**(도형 위로 올라가거나 다른 라벨을 덮는다).
   그래서 도구가 하는 일은 둘뿐이다: ⑴ **태깅**(그룹 안으로 이동) ⑵ **측정**(어디가 어긋났나).

사용:
    python tools/fix_dim_label.py                          # 전 챕터 — 치수마다 후보 목록
    python tools/fix_dim_label.py --chapter=ch02.json
    python tools/fix_dim_label.py --apply --pair=fig-02-q02:'z = 12 m'
    python tools/fix_dim_label.py --apply --pairs=data/열역학/dim-label-pairs.txt

`--pair` 는 «삽화 id : 라벨 글자» 다. **사람이 짝을 확인해 준 것만 옮긴다** —
가장 가까운 글자를 자동으로 라벨로 단정하면 캡션·상태 라벨을 그룹 안으로 끌고 들어온다.
"""
import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 오류는 stderr 로 나간다 — 그쪽도 UTF-8 로 돌려놓지 않으면 **한글 오류만 깨진다**
# (2026-08-12, 동역학 세션 보고. 잠금 `test_checks.py::test_tool_errors_are_utf8`).
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_content import (                                      # noqa: E402
    dim_label_rows, iter_chapter_diagrams,
)
from buildlib.checks_content import _point_to_segment                      # noqa: E402
from buildlib.checks_svg import _attr, _effective                          # noqa: E402
from buildlib.jsontext import write_chapter                                # noqa: E402
import audit_content                                                       # noqa: E402


def _materialize(node, svg, item):
    """옮기기 **전에** 물려받던 속성을 글자에 박은 `<text>` 마크업.

    ★ 이게 없으면 두 방향으로 조용히 깨진다.
      ⑴ 치수 그룹은 `<g class='dim' stroke='#5b5f57' fill='none'>` 처럼 **자기 속성**을 갖는 일이
         흔하다. 그대로 옮기면 글자가 `fill='none'` 을 물려받아 **화면에서 사라지거나**
         글리프에 윤곽선이 생긴다.
      ⑵ 반대로 글자가 있던 자리가 `<g font-size='16' text-anchor='middle'>` 였으면
         옮기는 순간 크기·정렬을 잃는다(실측 `fig-continuum-vs-rarefied` 의 L·λ 가 그 형태).
      둘 다 빌드 검사가 못 보는 종류다 — 좌표는 그대로고 마크업도 유효하기 때문이다.
    """
    head = node[:node.index(">") + 1]
    attrs = head[len("<text"):-1]
    add = []
    for name, value in (("font-size", "%g" % item["fs"]),
                        ("text-anchor", item["anchor"]),
                        ("fill", item["fill"]),
                        ("font-weight", item["weight"]),
                        ("font-family", _effective(svg, item["pos"], attrs, "font-family", ""))):
        if value and _attr(attrs, name) is None:
            add.append("%s='%s'" % (name, value))
    if _attr(attrs, "stroke") is None:
        add.append("stroke='none'")   # 치수 그룹의 stroke 를 글리프가 물려받지 않게
    return "<text " + " ".join([attrs.strip()] + add).strip() + node[node.index(">"):]


def _load_pairs(args):
    """«삽화 id → 옮길 라벨 글자들». `--pair` 여러 번 + `--pairs` 파일."""
    pairs = {}
    for raw in list(args.pair or []):
        fig, _sep, label = raw.partition(":")
        if not _sep:
            raise SystemExit("--pair 는 '<삽화 id>:<라벨 글자>' 형식이다: " + raw)
        pairs.setdefault(fig.strip(), []).append(label.strip())
    if args.pairs:
        with open(args.pairs, encoding="utf-8") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                fig, _sep, label = line.partition(":")
                if _sep:
                    pairs.setdefault(fig.strip(), []).append(label.strip())
    return pairs


def _move_into_group(svg, item, group_end):
    """`<text>` 를 통째로 들어내 치수 그룹의 `</g>` **직전**에 끼운 SVG.

    ★ 그룹은 대개 라벨보다 **앞**에 있으므로 이동은 글자를 소스상 앞으로 당긴다 =
      **z-order 가 내려간다.** 뒤에 오는 채운 도형에 덮일 수 있다 — 그건 빌드의 겹침
      검사(C15·F4)가 잡으므로 여기서 미리 재지 않는다. 잡히면 그 삽화는 사람이 본다.
    """
    start, end = item["pos"], item["end"]
    node = _materialize(svg[start:end], svg, item)
    rest = svg[:start] + svg[end:]
    close = group_end - len("</g>") - ((end - start) if start < group_end else 0)
    return rest[:close] + node + rest[close:]


def main():
    ap = argparse.ArgumentParser(description="치수 라벨 태깅·측정 (좌표는 옮기지 않는다)")
    ap.add_argument("--chapter", help="chNN.json 하나만")
    ap.add_argument("--pair", action="append", help="'<삽화 id>:<라벨 글자>' — 사람이 확인한 짝")
    ap.add_argument("--pairs", help="같은 형식을 한 줄씩 담은 파일")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    pairs = _load_pairs(args)
    names = ([args.chapter] if args.chapter
             else [name + ".json" for name in audit_content.CHAPTERS])
    tagged = untagged = offspec = 0
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        # ★ 기록은 **표기를 보존해서** 한다 — 아래 `write_chapter` 가 원본과 대조할 사본이다.
        before = copy.deepcopy(data)
        changed = False
        for fig_id, dg in iter_chapter_diagrams(data):
            svg = str(dg.get("svg") or "")
            if not svg:
                continue
            wanted = list(pairs.get(fig_id, []))
            # 한 번 옮길 때마다 좌표(소스 오프셋)가 밀리므로 **매번 다시 잰다.**
            while True:
                rows = dim_label_rows(svg)
                # ★ 짝은 **가장 가까운 치수**에게 준다. 처음엔 '먼저 나온 치수'에 붙였는데
                #   한 삽화에 치수가 둘이면 두 라벨이 **같은 그룹으로 몰렸다**(실측
                #   `fig-abs-gage-vacuum-bars`: Pvac 이 Pgage 의 그룹으로 갔다).
                todo = None
                for row in rows:
                    for cand in row["outside"]:
                        if cand["s"].strip() not in wanted:
                            continue
                        far = _point_to_segment((cand["x"], cand["y"]), row["main"])
                        if todo is None or far < todo[0]:
                            todo = (far, row, cand)
                if not todo:
                    break
                _far, row, cand = todo
                svg = _move_into_group(svg, cand, row["group"][1])
                wanted.remove(cand["s"].strip())   # 같은 글자가 둘이면 **하나만** 지운다
                changed, tagged = True, tagged + 1
                print("  [태깅] %-30s %r → 치수 그룹 안" % (fig_id, cand["s"][:24]))
            for w in wanted:
                print("  [못 찾음] %-28s %r — 그룹 밖 후보에 없다" % (fig_id, w[:24]))
            for row in dim_label_rows(svg):
                axis = "수직" if row["axis"] == "v" else "수평"
                if not row["inside"]:
                    untagged += 1
                    near = ", ".join("%r(%.0f,%.0f)" % (t["s"][:16], t["x"], t["y"])
                                     for t in row["outside"][:3])
                    print("  [무라벨] %-28s %s 치수 base=%.0f 구간 %.0f~%.0f — 후보 %s"
                          % (fig_id, axis, row["base"], row["lo"], row["hi"], near or "없음"))
                    continue
                near = min(row["inside"],
                           key=lambda t: abs((t["y"] if row["axis"] == "v" else t["x"]) - row["mid"]))
                along = near["y"] if row["axis"] == "v" else near["x"]
                across = near["x"] if row["axis"] == "v" else near["y"]
                bad = []
                if not (row["lo"] <= along <= row["hi"]):
                    bad.append("구간 밖(%.0f ∉ %.0f~%.0f)" % (along, row["lo"], row["hi"]))
                # 수평 치수의 위/아래는 **일부러 묻지 않는다** — 근거는
                # `checks_content.dim_label_placement_issues` 독스트링의 반박 기록.
                if row["axis"] == "v" and across > row["base"]:
                    bad.append("오른쪽(x %.0f > %.0f)" % (across, row["base"]))
                if bad:
                    offspec += 1
                    print("  [위치] %-30s %r %s 치수 — %s · 규격 중심 %.0f"
                          % (fig_id, near["s"][:24], axis, " · ".join(bad), row["mid"]))
            dg["svg"] = svg
        if changed and args.apply:
            # ★ 표준 직렬화로 통째로 다시 쓰면 **손으로 압축한 표기가 있는 챕터가 통째로
            #   재포맷**되고, 그러면 변경점 하이라이트가 잡음이 된다(공학수학 ch02 는 한 줄짜리
            #   `{ "text": …, "equations": […] }` 가 113곳이다). 같은 부류를 `fix_honorific`·
            #   `fix_notation_split` 에서 이미 닫았는데 새 도구가 다시 열었다 — 잠금은
            #   `test_json_rewrite_preserves_formatting` ⑸ 가 세 도구를 모두 본다.
            status, why = write_chapter(path, before, data)
            print(("[쓰기] " + name) if status == "written"
                  else "  [중단] 표기를 보존한 채로는 못 쓴다 — %s" % why)
    print("\n태깅 %d건 · 무라벨 %d건 · 위치 위반 %d건%s"
          % (tagged, untagged, offspec, "" if args.apply else " (미리보기 — --apply 로 반영)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
