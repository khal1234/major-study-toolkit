# -*- coding: utf-8 -*-
"""**문항에 붙인 삽화를 통째로 걷어낸다** (열린 날 2026-09-10).

    python tools/drop_item_diagrams.py <챕터경로> <문항id…> --why "<사유>" [--apply]

★ **왜 열렸나** — 삽화를 그린 뒤에 그 문항의 `noDiagramReason` 을 읽었더니
  *[발화 생략]* 였다(규칙 12⑶). **되돌려야 하는데
  되돌리는 자가 없었다** — `drop_card_diagrams.py` 는 유도 카드 전용이라 문항을 못 찾는다.
  같은 날 세 문항에서 같은 일이 났다(ch13-q01·ch13-q07·ch14-q03).

  손으로 지우려면 한 줄짜리 SVG 수천 자를 그대로 다시 적어야 해서 편집이 위험하다.
  **줄 단위로 도려내는 것이 이 자의 몫이다.**

## 어떻게 고치나

`"id": "<문항id>"` 줄부터 그 객체 안의 `"diagrams": [` … `]` 블록을 찾아 **줄을 지운다.**
`figureMode` 도 함께 지운다 — 삽화가 없으면 「주어진 그림인가」를 선언할 대상이 없다.
지운 자리에 `noDiagramReason` 이 이미 있으면 그대로 두고, 없으면 `--why` 를 그 자리에 넣는다.

**JSON 을 되읽어 덤프하지 않는다** — 다시 쓰면 파일 전체의 따옴표·줄바꿈이 갈려
변경점 검수가 죽는다(`fix_formula_declarations.py` 와 같은 이유).

## ☐ 이 자가 못 보는 것 (규칙 21)

- **여러 줄로 접힌 `diagrams` 안의 중첩 배열은 안 본다.** 이 리포는 삽화 하나가 한 줄이라
  `]` 의 들여쓰기로 끝을 찾는데, 더 깊은 배열이 같은 들여쓰기로 끝나면 잘못 자른다.
  그래서 **자른 뒤 JSON 을 파싱해 보고, 깨지면 쓰지 않는다.**
- **그 사유가 타당한지 안 본다.** 「왜 되돌리나」는 사람이 적는다.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ID_RE = re.compile(r'^(\s*)"id":\s*"([^"]+)"')


def cut_item_diagrams(lines, item_id, why):
    """그 문항의 `diagrams` 블록과 `figureMode` 줄을 뺀 새 줄 목록. 순수 함수.

    돌려주는 것은 (새 줄 목록, 잘라 냈나, 사유를 새로 넣었나).
    """
    out, i, cut, added = [], 0, False, False
    n = len(lines)
    while i < n:
        m = ID_RE.match(lines[i])
        if not (m and m.group(2) == item_id):
            out.append(lines[i])
            i += 1
            continue
        indent = m.group(1)
        out.append(lines[i])
        i += 1
        has_reason = False
        while i < n:
            line = lines[i]
            m2 = ID_RE.match(line)
            if m2 and len(m2.group(1)) <= len(indent) and m2.group(2) != item_id:
                break                                   # 다음 문항으로 넘어갔다
            if line.strip().startswith('"noDiagramReason"'):
                has_reason = True
            if line.strip().startswith('"figureMode"'):
                i += 1
                cut = True
                continue
            if line.strip().startswith('"diagrams": ['):
                depth = 0
                while i < n:
                    depth += lines[i].count("[") - lines[i].count("]")
                    i += 1
                    if depth <= 0:
                        break
                cut = True
                if not has_reason and why:
                    out.append('%s"noDiagramReason": "%s",\n' % (indent, why))
                    added = True
                continue
            out.append(line)
            i += 1
        # 사유가 뒤쪽에 있었고 우리가 앞에 또 넣었으면 중복이다 — 기계가 못 가르므로
        # `--apply` 전에 미리보기로 사람이 본다.
    return out, cut, added


def main(argv):
    if len(argv) < 2:
        sys.exit("쓰는 법 — python tools/drop_item_diagrams.py <챕터경로> <문항id…> "
                 "--why \"<사유>\" [--apply]")
    path = argv[0]
    apply_it = "--apply" in argv
    why = ""
    ids = []
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--why":
            i += 1
            why = argv[i] if i < len(argv) else ""
        elif a == "--apply":
            pass
        else:
            ids.append(a)
        i += 1
    if not ids:
        sys.exit("거부 — 걷어낼 문항 id 를 하나 이상 줄 것.")
    if not os.path.exists(path):
        sys.exit("거부 — 챕터를 못 찾았다: %s" % path)

    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    done = []
    for item_id in ids:
        lines, cut, added = cut_item_diagrams(lines, item_id, why)
        if cut:
            done.append(item_id + (" (사유 신설)" if added else ""))
        else:
            print("  %s · 걷어낼 삽화가 없다" % item_id)
    if not done:
        return 0
    text = "".join(lines)
    json.loads(text)                                    # 깨뜨렸으면 여기서 멈춘다
    print("  걷어냄 — %s" % ", ".join(done))
    if apply_it:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print("반영")
    else:
        print("미리보기(--apply 로 반영)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
