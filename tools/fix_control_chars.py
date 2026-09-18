# -*- coding: utf-8 -*-
"""빌드가 금지하는 제어문자(BAD_CHARS)가 소스 파일에 섞여 들었을 때 걷어낸다.

    python tools/fix_control_chars.py <경로> [--apply]

`buildlib.textutil.BAD_CHARS` (chr 1·7·8·11·12) 와 같은 정의를 그대로 쓴다 — 판정
기준이 둘이면 갈린다. 편집 도구가 눈에 안 보이는 바이트를 실수로 끼워 넣었을 때
(문자열 인자로는 짚을 수 없다) 쓰는 마지막 수단이고, 기본은 후보만 보여주고
`--apply` 를 줘야 실제로 고친다.
"""
import sys

sys.path.insert(0, __file__.rsplit("tools", 1)[0] + "tools")
from buildlib.textutil import BAD_CHARS                                       # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    if not args:
        sys.exit("쓰는 법: python tools/fix_control_chars.py <경로> [--apply]")
    path = args[0]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    hits = [(i, hex(ord(c))) for i, c in enumerate(text) if c in BAD_CHARS]
    if not hits:
        print("[ok] " + path + " — 제어문자 없음")
        return 0
    print("[찾음] " + path + " — " + str(len(hits)) + "곳: "
          + ", ".join(code for _, code in hits[:10]))
    if not apply:
        print("--apply 를 주면 실제로 걷어낸다")
        return 0
    cleaned = "".join(c for c in text if c not in BAD_CHARS)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(cleaned)
    print("[적용] " + str(len(hits)) + "곳 제거")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
