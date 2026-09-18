#!/usr/bin/env python
"""첫 세션 안내 — 과목이 하나도 없으면 에이전트에게 「이 틀을 채택하고 START.md 순서로 간다」를 박는다.

무엇을 재나: `data/*/SUBJECT.md` 가 하나라도 있나 · `~/.claude/rules/층0-판정선.md` 가 깔렸나.
문턱: 과목 0개일 때만 말한다 — 과목이 생기면 조용하다(매 세션 문맥을 먹지 않게).
못 보는 것: 에이전트가 이 안내를 실제로 따랐는지는 모른다. Codex 는 훅을 안 돌리므로
같은 말을 `AGENTS.md` 머리와 `START.md` 에도 둔다.
"""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def main() -> int:
    try:
        subjects = list((ROOT / "data").glob("*/SUBJECT.md"))
        rules = (Path.home() / ".claude/rules/층0-판정선.md").exists()
    except OSError:
        return 0
    if subjects:
        return 0
    lines = [
        "[첫 세션] 이 저장소는 참고 자료가 아니라 **네가 따를 작업 틀**이다 — CLAUDE.md 를 작업 규칙으로 채택한다.",
        "  아직 과목이 없다. **START.md 를 읽고 그 순서대로** 사용자를 안내한다(설치 확인 → 과목 넷 묻기 → 첫 장).",
    ]
    if not rules:
        lines.append("  공통 규칙·스킬이 안 깔렸다 — 사용자에게 `python setup.py --rules --skills` 를 권한다(깔고 세션을 새로 연다).")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
