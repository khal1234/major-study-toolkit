"""챕터 하나만 데이터 lint를 돈다(다른 챕터의 기존 결함이 있어도 안 막힌다).

    python tools/lint_chapter.py data/<과목>/chNN.json

`build_site.py`는 과목 전체를 순회하며 lint하므로, 한 챕터만 고친 배치를 확인하려 해도
**다른 챕터의 기존 결함**(아직 안 고친 것)에 막혀 전체가 죽는다 — 지금 만지는 챕터가
깨끗한지조차 알 수 없다. 이 도구는 그 결함을 우회하지 않는다 — **다른 챕터를 안 본다.**
`checks_content.lint_chapter`를 그대로 부르므로 판정 기준은 `build_site.py`와 완전히 같다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_content import lint_chapter  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit("사용: python tools/lint_chapter.py data/<과목>/chNN.json")
    path = sys.argv[1]
    with open(path, encoding="utf-8") as fh:
        ch = json.load(fh)
    try:
        lint_chapter(ch, path)
    except ValueError as e:
        sys.exit(str(e))
    print("[ok] " + path + " — 이 챕터만 lint 통과")


if __name__ == "__main__":
    main()
