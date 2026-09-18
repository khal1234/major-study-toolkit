# -*- coding: utf-8 -*-
"""챕터 JSON 안 SVG 속성의 따옴표를 **홑따옴표로 정규화**한다.

    python tools/normalize_svg_quotes.py            # 미리보기(파일을 쓰지 않는다)
    python tools/normalize_svg_quotes.py --apply    # 실제 반영

**왜 이 도구가 필요한가 (열린 날 2026-07-30, 기계재료 세션).**
`tools/fix_figure_*.py` 다섯 개는 SVG 속성을 **홑따옴표 정규식**으로 찾는다
(`font-size='(\\d+)'` 등). 그런데 검사기(`buildlib/checks_svg._attr`)는 홑·쌍따옴표를
**둘 다** 읽는다. 그래서 챕터가 쌍따옴표 표기(JSON 안에서는 `font-size=\\"13\\"`)면
이런 상태가 된다:

  · 빌드 검사: 규격 위반을 **정확히 잡는다**(기계재료 ch01 46 errors)
  · 수정 도구: `삽화 0개` 라고 찍고 **아무 것도 하지 않는다**

즉 **재는 도구와 고치는 도구가 다른 것을 보고 있었다.** 더 나쁜 것은 실패가 조용하다는 점이다 —
`삽화 0개`는 "이미 규격을 만족한다"와 화면상 구별되지 않는다(`BOOK_DIRS` 누락이
'교재가 없는 과목'처럼 보였던 것과 같은 부류, 피드백 원장 2026-07-28 materials).

**왜 도구의 정규식을 고치지 않고 데이터를 정규화하나.**
⑴ 홑따옴표가 이 리포의 사실상 표준이다 — 열역학 5챕터·삽화 78개가 그 표기이고
   수정 도구·회귀 테스트가 전부 그 위에 서 있다.
⑵ JSON 문자열 안에서 `\\"` 이스케이프가 사라져 데이터가 짧아지고 읽기 쉬워진다.
⑶ 도구 5개의 정규식을 각각 양따옴표 대응으로 고치면 **같은 규약이 6곳에 갈라진다** —
   피드백 원장이 이미 지목한 부류다(*[발화 생략]*).
표기를 하나로 모으는 쪽이 갈라짐의 수를 줄인다.

**안전장치.** 값에 홑따옴표가 들어 있으면 그 속성은 건드리지 않고 보고한다(변환하면 SVG가 깨진다).
반영 뒤 JSON 파싱과 SVG 속성 개수 보존을 스스로 검사하고, 어긋나면 쓰지 않고 exit 1.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 과목 폴더 탐색은 **함수를 공유**한다 — 다시 구현하면 갈라진다(위 ⑶과 같은 이유).
from fix_figure_text_scale import DATA_ROOT, _my_subject, subject_dirs  # noqa: E402

# JSON 파일 텍스트에서 본 형태: `viewBox=\"0 0 700 360\"` (백슬래시 + 따옴표)
ESCAPED_ATTR_RE = re.compile(r'=\\"([^"\\]*)\\"')


def normalize_svg_line(line):
    """한 줄(=`"svg": "…"` 한 개)의 쌍따옴표 속성을 홑따옴표로 바꾼다.

    반환값 `(새 줄, 바꾼 개수, 건너뛴 값 목록)`. 순수 함수 — 회귀 테스트가 직접 부른다.
    값에 홑따옴표가 있으면 **바꾸지 않는다** — 바꾸면 그 속성이 조용히 깨진다.
    """
    skipped = []
    count = [0]

    def repl(m):
        value = m.group(1)
        if "'" in value:
            skipped.append(value[:40])
            return m.group(0)
        count[0] += 1
        return "='" + value + "'"

    return ESCAPED_ATTR_RE.sub(repl, line), count[0], skipped


def svg_attr_count(text):
    """SVG 속성 개수(홑·쌍따옴표 무관). 변환 전후가 같아야 한다 — 손실 검사용."""
    return len(re.findall(r"=\\\"[^\"\\]*\\\"", text)) + len(re.findall(r"='[^']*'", text))


def main():
    apply = "--apply" in sys.argv
    only_ch = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    if only_ch:
        only_ch = only_ch.replace(".json", "")
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--subject=")), None)
    mine = arg or _my_subject()
    names = sorted(n for n in os.listdir(DATA_ROOT)
                   if os.path.isdir(os.path.join(DATA_ROOT, n)))
    dirs = subject_dirs(names, mine)
    if not dirs:
        print("거부 — 이 브랜치의 과목 폴더를 찾지 못했다(과목=" + str(mine) + ").\n"
              "  과목 워크트리에서 실행하거나 `--subject=<폴더 접두어>` 를 줄 것.")
        return 2
    data_dir = os.path.join(DATA_ROOT, dirs[0])
    print("[대상] data/" + dirs[0])

    total_files = total_attrs = 0
    for name in sorted(os.listdir(data_dir)):
        if not re.fullmatch(r"ch\d+\.json", name):
            continue
        if only_ch and os.path.splitext(name)[0] != only_ch:
            continue
        path = os.path.join(data_dir, name)
        original = open(path, encoding="utf-8").read()
        lines = original.split("\n")
        changed_here = 0
        for i, line in enumerate(lines):
            if '"svg":' not in line:
                continue
            new_line, n, skipped = normalize_svg_line(line)
            if skipped:
                print("  " + name + ": 값에 홑따옴표가 있어 건너뜀 — " + ", ".join(skipped))
            if not n:
                continue
            lines[i] = new_line
            changed_here += n
        if not changed_here:
            continue
        merged = "\n".join(lines)
        # ── 자기 검사 둘: JSON 유효성 + 속성 개수 보존
        try:
            json.loads(merged)
        except ValueError as exc:
            print("  [FAIL] " + name + ": 변환 결과가 유효한 JSON이 아니다 — " + str(exc))
            return 1
        if svg_attr_count(merged) != svg_attr_count(original):
            print("  [FAIL] " + name + ": 속성 개수가 달라졌다 — 쓰지 않는다")
            return 1
        total_files += 1
        total_attrs += changed_here
        print("  " + name + ": 속성 " + str(changed_here) + "개 정규화")
        if apply:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(merged)

    print("\n" + ("반영" if apply else "미리보기") + " — 파일 " + str(total_files)
          + "개 · 속성 " + str(total_attrs) + "개")
    if not apply and total_attrs:
        print("실제로 쓰려면 --apply 를 붙일 것")
    return 0


if __name__ == "__main__":
    sys.exit(main())
