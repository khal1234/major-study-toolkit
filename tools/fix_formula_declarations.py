# -*- coding: utf-8 -*-
"""**이름을 부르고도 선언 안 한 문항**에 그 카드 id 를 넣는다 (열린 날 2026-09-09).

    python tools/fix_formula_declarations.py --subject=<폴더접두> [--chapter=chNN] [--apply]

`audit_formula_declarations.py` 의 ⑴ 이 낸 것만 고친다 — **문항의 글에 카드 id 가 글자
그대로 있는데 `relatedFormulas` 에는 없는** 자리다. 무엇을 넣을지 이 도구가 판단하지 않는다:
저자가 이미 «이 카드를 쓴다» 고 적어 둔 id 를 선언 칸으로 옮길 뿐이다.

★ **JSON 을 다시 덤프하지 않고 날 줄을 고친다.** 되읽어 쓰면 파일 전체의 줄바꿈·따옴표가
  갈려 diff 가 통째로 붉어지고 변경점 검수가 죽는다(같은 이유로 `fix_figure_*` 계열도 전부
  줄 단위로 고친다). 그래서 이 도구는 **문항 id 줄을 찾아 그 아래 창에서만** 손댄다.

## ☐ 이 도구가 못 하는 것

- **어느 카드를 가리켜야 하는지 못 찾는다.** 글에 이름이 안 나온 문항은 대상이 아니다 —
  그건 사람이 읽어야 한다(감사의 ⑵ 「선언 공백」이 그 자리를 가리킨다).
- **한 줄에 여러 문항이 눌려 있는 파일은 건너뛴다.** 이 리포의 챕터 JSON 은 전부 들여쓴
  여러 줄 꼴이라 지금은 걸리는 파일이 없지만, 그런 파일이 생기면 조용히 고치지 않고 센다.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import audit_content                                                    # noqa: E402
import audit_formula_declarations as decl                               # noqa: E402

ID_LINE = re.compile(r'^(\s*)"id"\s*:\s*"([^"]+)"')
REL_ONELINE = re.compile(r'^(\s*)"relatedFormulas"\s*:\s*\[(.*)\](,?)\s*$')
REL_OPEN = re.compile(r'^(\s*)"relatedFormulas"\s*:\s*\[\s*$')


def item_window(lines, qid):
    """문항 id 줄의 번호와, 다음 `"id"` 줄 직전까지의 창. 못 찾으면 (None, None)."""
    start = None
    for i, line in enumerate(lines):
        m = ID_LINE.match(line)
        if not m:
            continue
        if start is not None:
            return start, i
        if m.group(2) == qid:
            start = i
    return (start, len(lines)) if start is not None else (None, None)


def add_to_lines(lines, qid, fid):
    """`relatedFormulas` 에 fid 를 넣은 새 줄 목록. 못 넣으면 원본 그대로 돌려준다.

    순수 함수 — 테스트가 직접 부른다.
    """
    start, end = item_window(lines, qid)
    if start is None:
        return lines, False
    indent = ID_LINE.match(lines[start]).group(1)

    for i in range(start + 1, end):
        m = REL_ONELINE.match(lines[i])
        if m:
            inner = m.group(2).strip()
            if fid in inner:
                return lines, False
            body = ('"%s"' % fid) if not inner else (inner + ', "%s"' % fid)
            out = list(lines)
            out[i] = '%s"relatedFormulas": [%s]%s' % (m.group(1), body, m.group(3))
            return out, True
        m = REL_OPEN.match(lines[i])
        if m:
            close = None
            for j in range(i + 1, end):
                if lines[j].strip().startswith("]"):
                    close = j
                    break
            if close is None:
                return lines, False
            out = list(lines)
            if close > i + 1 and not out[close - 1].rstrip().endswith(","):
                out[close - 1] = out[close - 1].rstrip() + ","
            out.insert(close, '%s  "%s"' % (m.group(1), fid))
            return out, True

    out = list(lines)
    out.insert(start + 1, '%s"relatedFormulas": ["%s"],' % (indent, fid))
    return out, True


def main(argv):
    apply = "--apply" in argv
    subject = next((a.split("=", 1)[1] for a in argv if a.startswith("--subject=")), None)
    only_ch = next((a.split("=", 1)[1] for a in argv if a.startswith("--chapter=")), None)
    if only_ch:
        only_ch = only_ch.replace(".json", "")
    if not subject:
        sys.exit("--subject=<폴더접두> 를 줄 것 (전 과목 스윕은 열어 두지 않는다)")

    dirs = [d for d in audit_content.subject_dirs() if subject in os.path.basename(d)]
    if not dirs:
        sys.exit("과목 폴더를 못 찾았다: " + subject)

    touched = 0
    for d in dirs:
        for name in sorted(f for f in os.listdir(d)
                           if re.fullmatch(r"ch\d+\.json", f)):
            if only_ch and name[:-5] != only_ch:
                continue
            path = os.path.join(d, name)
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            targets = decl.named_but_undeclared(data)
            if not targets:
                continue
            lines = raw.split("\n")
            for _layer, qid, fid in targets:
                lines, ok = add_to_lines(lines, qid, fid)
                mark = "  넣음" if ok else "  건너뜀(줄을 못 찾았다)"
                print("%s %s · %s → %s%s"
                      % (os.path.basename(d), name[:-5], qid, fid, mark))
                if ok:
                    touched += 1
            new = "\n".join(lines)
            if apply and new != raw:
                json.loads(new)          # 쓰기 전에 JSON 으로 다시 읽힌다는 것을 확인한다
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new)

    print("\n%s — %d건" % ("반영" if apply else "미리보기", touched))
    print("실제로 쓰려면 --apply 를 붙일 것" if not apply else "")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
