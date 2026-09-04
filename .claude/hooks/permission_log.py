#!/usr/bin/env python
"""PermissionDenied 훅 — 거부된 명령을 **부류별로 세어** 파일에 남긴다.

열린 날 2026-07-28.

**왜 필요한가 — 규칙이 사람의 성실성에 기대고 있었다.**
AGENTS 실행 규율 7: *"프롬프트가 뜬 명령은 전부 `docs/permission-prompt-ledger.md` 에 남긴다
— 고치기 **전에** 한 줄. 기록이 없으면 **재발인지 첫 발생인지 구별할 수 없다.**"*
그런데 이 규칙을 지키는 주체는 에이전트고, **잊으면 그냥 안 적힌다.** 실제로 `git -C`·`echo`·
`python -c` 는 사용자가 **3회씩** 지적하고 나서야 고쳐졌다. 규칙 7-⑷ 가 스스로 못박은 대로
*"조치는 사람의 성실성에 기대는 것이 아니라 기계가 막는 것이어야 한다."*

`PermissionDenied` 는 **decision control 이 없는 순수 로깅 이벤트**라(공식 문서:
*"No decision control. Used for side effects like logging or cleanup"*) 용도가 정확히 맞는다.

**설계 — 토큰을 쓰지 않는다.**
사용자 질문이 *"토큰이 그렇게 많이 드나?"* 였다. 답: **0 이다.**
  ⑴ 거부가 **실제로 일어났을 때만** 돈다(평소 0회).
  ⑵ **stdout 에 아무것도 쓰지 않는다** — 훅 출력이 없으면 컨텍스트에 들어가는 것도 없다.
  ⑶ 인스턴스를 줄줄이 쌓지 않고 **부류(pattern)별 카운트**만 갱신한다 — 파일이 안 자란다.

**왜 `docs/` 가 아니라 로컬인가 (되돌릴 수 있는 판단):**
`docs/` 는 `sync_common.py` 가 옮기는 공통 정본이라 두 과목 worktree 가 같은 파일을 동시에
고치면 merge 마다 충돌한다. 게다가 거부는 세션마다 나므로 git 트리가 계속 더러워진다.
→ 기계 기록은 **로컬**(`.denials.json`, gitignore)에 두고, **부류가 승격될 때 사람이
   `docs/permission-prompt-ledger.md` 에 한 줄 남기는 것은 그대로 유지**한다.
   즉 이 훅은 원장을 대체하지 않는다. *"이게 몇 번째인가"* 에 답할 근거를 만들 뿐이다.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from guard_bash import read_payload  # noqa: E402

# 회귀 테스트가 **실제 진단 기록을 오염시키지 않도록** 디렉터리를 갈아끼울 수 있게 한다.
# (테스트가 남긴 가짜 부류가 섞이면 "몇 번째 재발인가" 라는 이 파일의 존재 이유가 무너진다.)
_LOG_DIR = os.environ.get("CLAUDE_HOOK_LOG_DIR") or os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(_LOG_DIR, ".denials.json")


def denial_pattern(tool_name, tool_input):
    """거부를 묶을 **부류 키**. 순수 함수 — 테스트가 직접 부른다.

    Bash 는 명령 + 첫 서브커맨드까지만 본다(`git log`·`python -c`). 인스턴스 전체를
    키로 쓰면 경로 하나만 달라도 다른 부류가 돼 **재발 판정이 무너진다** — 그게 이 훅의 목적이다.
    """
    tool_name = str(tool_name or "?")
    if tool_name != "Bash":
        return tool_name
    command = str((tool_input or {}).get("command", "")).strip()
    if not command:
        return "Bash"
    tokens = command.split()
    return "Bash: " + " ".join(tokens[:2])


def record(store, pattern, kind, now=None):
    """카운트 갱신(순수 함수 — 파일 I/O 없이 테스트한다)."""
    now = now or time.strftime("%Y-%m-%d %H:%M:%S")
    entry = store.setdefault(pattern, {"count": 0, "first": now, "kinds": {}})
    entry["count"] += 1
    entry["last"] = now
    entry["kinds"][kind] = entry["kinds"].get(kind, 0) + 1
    return store


def main():
    try:
        payload = read_payload()
    except Exception:
        return
    try:
        pattern = denial_pattern(payload.get("tool_name"), payload.get("tool_input") or {})
        kind = str(payload.get("toolDenialKind") or payload.get("reason") or "unknown")
        store = {}
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, encoding="utf-8") as fh:
                store = json.load(fh)
        record(store, pattern, kind)
        with open(LOG_PATH, "w", encoding="utf-8") as fh:
            json.dump(store, fh, ensure_ascii=False, indent=1, sort_keys=True)
    except Exception:
        pass          # 로깅이 세션을 인질로 잡아선 안 된다
    # stdout 에 아무것도 쓰지 않는다 — 이게 '토큰 0' 의 구현이다.


if __name__ == "__main__":
    main()
