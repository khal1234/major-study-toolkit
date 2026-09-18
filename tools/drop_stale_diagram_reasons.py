# -*- coding: utf-8 -*-
"""**삽화를 그린 뒤에도 남아 있는 `noDiagramReason` 을 걷어낸다** (열린 날 2026-09-10).

    python tools/drop_stale_diagram_reasons.py --subject=응용고체역학            # 미리보기
    python tools/drop_stale_diagram_reasons.py --subject=응용고체역학 --apply
    python tools/drop_stale_diagram_reasons.py --subject=응용고체역학 --chapter=ch13 --apply

★ **왜 열렸나** — 문항에 삽화를 붙이면서 「왜 안 그렸는지」를 적어 둔 줄을 같이 지우지 않았다.
  발행본에는 안 나간다(`render.AUTHOR_ONLY_KEYS`). 그래서 **아무도 안 아프고, 그래서 쌓인다.**
  다음 세션은 그 줄을 읽고 「이 문항은 안 그리기로 판정된 자리」로 오해한다 — 판정 기록이
  사실과 어긋나면 기록이 없는 것보다 나쁘다.

  손으로 지우면 아홉 줄에 아홉 번 편집이 들고, 같은 드리프트가 장마다 다시 생긴다.
  **그리는 일과 지우는 일을 한 명령으로 묶는 것이 이 자의 몫이다.**

## 어떻게 고치나 — JSON 을 되읽어 덤프하지 않는다

`fix_formula_declarations.py` 와 같은 이유로 **날 줄을 지운다.** 다시 쓰면 파일 전체의 따옴표·
줄바꿈이 갈려 변경점 검수가 죽는다.

지운 줄이 그 객체의 **마지막 키**였으면 앞 줄의 꼬리 쉼표도 함께 뗀다 — 안 떼면 JSON 이 깨진다.

## ☐ 이 자가 못 보는 것 (규칙 21)

- **여러 줄에 걸친 사유는 안 건드린다.** 이 리포는 긴 문자열도 한 줄에 두지만, 줄을 접어 놓은
  것이 있으면 세지 않고 그냥 남긴다(목록에 「손으로 볼 것」으로 찍는다).
- **삽화가 타당한지 안 본다.** `diagrams` 가 비지 않았다는 사실만 본다.
- **챕터 수준 사유는 대상이 아니다** — 문항 안의 키만 본다.
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

ITEM_COLLECTIONS = ("practice", "problems")
REASON_KEY = "noDiagramReason"
ID_RE = re.compile(r'^\s*"id":\s*"([^"]+)"')
REASON_RE = re.compile(r'^\s*"%s":\s*".*?"(,?)\s*$' % REASON_KEY)


def drawn_item_ids(data):
    """삽화를 이미 지닌 문항의 id 집합. 순수 함수."""
    out = set()
    for coll in ITEM_COLLECTIONS:
        for item in data.get(coll) or []:
            if isinstance(item, dict) and item.get("diagrams") and item.get("id"):
                out.add(item["id"])
    return out


def item_ids(data):
    """문항 id 전체. 삽화 id 와 가르기 위해 필요하다 — 둘 다 `"id"` 로 적힌다."""
    out = set()
    for coll in ITEM_COLLECTIONS:
        for item in data.get(coll) or []:
            if isinstance(item, dict) and item.get("id"):
                out.add(item["id"])
    return out


def strip_reason_lines(lines, targets, known_ids):
    """대상 문항의 `noDiagramReason` 줄을 뺀 새 줄 목록과 뺀 id 목록. 순수 함수.

    마지막 키였으면(줄 끝에 쉼표가 없으면) 바로 앞 줄의 꼬리 쉼표를 뗀다.

    ★ **삽화 객체도 `"id"` 를 갖는다** — 그것을 문항 id 로 읽으면 그 뒤의 사유가 통째로
      남는다(첫 실행이 이 구멍으로 0줄을 찍었다). 그래서 **아는 문항 id 일 때만** 자리를 옮긴다.
    """
    out, removed, current = [], [], None
    for line in lines:
        m = ID_RE.match(line)
        if m and m.group(1) in known_ids:
            current = m.group(1)
        r = REASON_RE.match(line)
        if r and current in targets:
            removed.append(current)
            if not r.group(1):                    # 마지막 키였다
                for i in range(len(out) - 1, -1, -1):
                    if out[i].strip():
                        out[i] = re.sub(r",(\s*)$", r"\1", out[i])
                        break
            continue
        out.append(line)
    return out, removed


def main(argv):
    subject = None
    chapter = None
    apply_it = "--apply" in argv
    for a in argv:
        if a.startswith("--subject="):
            subject = a.split("=", 1)[1]
        elif a.startswith("--chapter="):
            chapter = a.split("=", 1)[1]
    if not subject:
        sys.exit("거부 — `--subject=<과목 폴더>` 를 줄 것 (전 과목 스윕은 열어 두지 않았다).")

    dirs = [d for d in audit_content.subject_dirs()
            if subject in os.path.basename(d)]
    if not dirs:
        sys.exit("거부 — 과목 폴더를 못 찾았다: %s" % subject)

    total = 0
    for d in dirs:
        print("[대상] %s" % os.path.relpath(d, audit_content.ROOT).replace("\\", "/"))
        for name in sorted(f for f in os.listdir(d)
                           if re.fullmatch(r"ch\d+\.json", f)):
            if chapter and not name.startswith(chapter + "."):
                continue
            path = os.path.join(d, name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            try:
                data = json.loads(text)
            except ValueError:
                print("  %s · JSON 을 못 읽어 건너뛴다" % name)
                continue
            targets = drawn_item_ids(data)
            if not targets:
                continue
            lines = text.splitlines(keepends=True)
            new_lines, removed = strip_reason_lines(lines, targets, item_ids(data))
            if not removed:
                continue
            total += len(removed)
            print("  %s · %d줄 — %s" % (name, len(removed), ", ".join(removed)))
            if apply_it:
                new_text = "".join(new_lines)
                json.loads(new_text)              # 깨뜨렸으면 여기서 멈춘다
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new_text)

    if not total:
        print("\n낡은 사유 0줄 — 걷어낼 것이 없다")
        return 0
    print("\n%s — 낡은 사유 %d줄" % ("반영" if apply_it else "미리보기(--apply 로 반영)", total))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
