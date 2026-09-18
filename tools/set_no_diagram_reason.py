# -*- coding: utf-8 -*-
"""**「안 그리는 사유」를 문항에 한꺼번에 적는다** (열린 날 2026-09-11).

    python tools/set_no_diagram_reason.py --file data/<과목>/chNN.json --from <사유맵.json>
    python tools/set_no_diagram_reason.py --file … --from … --apply

`사유맵.json` 은 `{"<문항 id>": "<사유 문장>", …}` 하나짜리 객체다.

★ **왜 도구인가** — 삽화 게이트(`audit_item_figure_reasons`)에 남은 문항이 **한 과목에 40개**
  가까이 있고, 그 대부분은 «대수 절차라 그릴 형상이 없다» 는 같은 부류다. 문항마다 `Edit` 를
  부르면 왕복이 40번이고, 그때마다 앵커를 손으로 골라야 해서 **엉뚱한 자리에 넣을 위험**이 생긴다.

★ **줄 단위로 끼운다 — JSON 을 다시 덤프하지 않는다.** 다시 덤프하면 들여쓰기·키 순서가
  통째로 바뀌어 diff 가 파일 전체가 된다(`fix_figure_vertical_balance` 가 같은 이유로 줄을 만진다).

☐ 이 자가 안 하는 것(규칙 21)
- **사유가 타당한지는 판정하지 않는다.** 문장은 사람이 쓴다 — 이 자는 옮겨 적기만 한다.
- 이미 `noDiagramReason` 이 있거나 `diagrams` 에 내용이 있는 문항은 **건드리지 않고 신고**한다.
- 넣은 뒤 **반드시 다시 파싱**해 본다. 깨지면 원래 내용으로 되돌리고 실패로 끝난다.
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ID_LINE = re.compile(r'^(\s*)"id":\s*"([^"]+)",\s*$')


def item_span(lines, start):
    """`"id"` 줄이 속한 객체의 끝 줄 번호 — 같은 들여쓰기의 `}` 또는 `},` 를 찾는다."""
    indent = len(lines[start]) - len(lines[start].lstrip())
    close = " " * (indent - 2) + "}"
    for i in range(start + 1, len(lines)):
        if lines[i].rstrip().rstrip(",") == close.rstrip():
            return i
    return len(lines) - 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="문항에 「안 그리는 사유」를 적는다")
    ap.add_argument("--file", help="고칠 챕터 하나")
    ap.add_argument("--from", dest="src", help="{id: 사유} 맵 JSON")
    ap.add_argument("--all", dest="bundle",
                    help="{챕터경로: {id: 사유}} 맵 JSON — 여러 장을 한 번에. "
                         "★ 한 번에 도는 이유: 이 도구는 미커밋 변경이 있으면 거부하므로 "
                         "장마다 따로 돌리면 장마다 커밋해야 한다(같은 배치가 커밋 아홉 개로 쪼개진다).")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    if args.bundle:
        with open(args.bundle, encoding="utf-8") as fh:
            bundle = json.load(fh)
        worst = 0
        for path, reasons in bundle.items():
            code = run_one(path, reasons, args.apply)
            worst = max(worst, code)
        return worst
    if not (args.file and args.src):
        ap.error("--file 과 --from 을 함께 주거나 --all 을 줄 것")
    with open(args.src, encoding="utf-8") as fh:
        reasons = json.load(fh)
    return run_one(args.file, reasons, args.apply)


def run_one(chapter, reasons, apply):
    with open(chapter, encoding="utf-8") as fh:
        original = fh.read()
    lines = original.split("\n")

    done, skipped = [], []
    out, i = [], 0
    while i < len(lines):
        out.append(lines[i])
        m = ID_LINE.match(lines[i])
        if m and m.group(2) in reasons:
            item_id = m.group(2)
            end = item_span(lines, i)
            body = "\n".join(lines[i:end])
            if '"noDiagramReason"' in body:
                skipped.append(item_id + " — 이미 사유가 있다")
            elif re.search(r'"diagrams":\s*\[\s*$', body, re.M):
                skipped.append(item_id + " — 삽화가 들어 있다")
            else:
                out.append(m.group(1) + '"noDiagramReason": '
                           + json.dumps(reasons[item_id], ensure_ascii=False) + ",")
                done.append(item_id)
        i += 1

    for name in sorted(set(reasons) - set(done) - {s.split(" — ")[0] for s in skipped}):
        skipped.append(name + " — 그 id 를 못 찾았다")

    text = "\n".join(out)
    try:
        json.loads(text)
    except ValueError as exc:
        print("[실패] 넣고 나니 JSON 이 깨진다 — 아무것도 쓰지 않았다: " + str(exc)[:160],
              file=sys.stderr)
        return 1

    for row in skipped:
        print("  [건너뜀] " + row)
    print(("반영" if apply else "미리보기") + " — " + chapter + " 문항 " + str(len(done)) + "개")
    if apply and done:
        open(chapter, "w", encoding="utf-8", newline="").write(text)
    return 1 if skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
