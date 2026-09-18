#!/usr/bin/env python
"""문항 풀이 해설(`solutionOutline`)의 첫 줄 「구할 것과 조건을 먼저 갈라 둡니다 …」를 걷는다 — 전 과목.

    python tools/drop_outline_preamble.py [--apply]

무엇을 하나: 모든 `data/<과목>/chNN.json` 의 `problems[]`·`practice[]` 에서 `solutionOutline` 의 **문자열** 항목 중
  `OUTLINE_PREAMBLE_PREFIX`(빌드 검사 C62 와 같은 상수)로 시작하는 줄을 지운다. `--apply` 가 없으면 세기만 한다.
문턱: 접두가 정확히 맞는 줄만 — 비슷한 말로 시작하는 다른 해설 줄은 안 건드린다.
못 보는 것: 같은 뜻을 다른 말로 쓴 줄(「조건은 … 구할 것은 …」 등)은 사람이 본다.
근거: 사용자 2026-09-19 [발화 생략](재발).
"""
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from buildlib.checks_content import OUTLINE_PREAMBLE_PREFIX  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    apply = "--apply" in argv
    total = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "*", "ch*.json"))):
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        ch = json.loads(raw)
        n = 0
        for coll in ("problems", "practice"):
            for it in ch.get(coll) or []:
                outline = it.get("solutionOutline") if isinstance(it, dict) else None
                if not isinstance(outline, list):
                    continue
                keep = [s for s in outline
                        if not (isinstance(s, str) and s.strip().startswith(OUTLINE_PREAMBLE_PREFIX))]
                n += len(outline) - len(keep)
                it["solutionOutline"] = keep
        if n:
            total += n
            print("  %s — %d줄" % (os.path.relpath(path, ROOT), n))
            if apply:
                nl = "\r\n" if "\r\n" in raw else "\n"
                with open(path, "w", encoding="utf-8", newline=nl) as f:
                    f.write(json.dumps(ch, ensure_ascii=False, indent=2) + "\n")
    print("합계 %d줄%s" % (total, "" if apply else " — 실제로 지우려면 --apply"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
