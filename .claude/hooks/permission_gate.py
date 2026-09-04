#!/usr/bin/env python
"""PermissionRequest 훅 — guard가 이미 안전하다고 판정한 명령의 **승인창 자체를 없앤다**.

열린 날 2026-07-28. 사용자 지적(반복): *"난 ask로 뜨는 거에 불만있는 게 아냐.
**모두 허용**으로 뜨는 게 불만이지. 1회 허용으로 뜨거나 allow로 안 떠야지."*

**왜 PreToolUse 만으로는 안 되나 (guard_bash.allow_reason 독스트링의 실측):**
PreToolUse 가 `permissionDecision: allow` 를 돌려줘도 **settings 의 `ask` 를 이기지 못한다**
(2026-07-24 실측: `python tools/scratch/restructure_ch01.py` 는 allow 판정인데도
`Bash(*python* tools/scratch/*)` ask 에 걸려 프롬프트가 떴다).
그래서 승인창이 뜨고, 승인창에는 **'모두 허용' 버튼이 함께 뜬다.** 그걸 한 번 누르면
그 패턴이 settings 의 allow 로 들어가고 — AGENTS 실측대로 — **allow 는 훅 deny 를 무시하므로
가드가 통째로 우회된다.** 되돌리기 어려운 명령을 지키는 게이트가 클릭 한 번에 사라진다.

`PermissionRequest` 는 **승인이 요청되는 시점**에 도는 이벤트라 그 뒤에서 판정할 수 있다.
공식 문서: *"When allowing, you can also modify the tool's input or apply permission rules
so the user isn't prompted again."* (<https://code.claude.com/docs/en/hooks>)

**★ 안전성은 실험이 아니라 구조로 보장한다 (이게 이 파일의 핵심 설계다).**
이 훅은 **새 권한을 하나도 열지 않는다.** allow 를 내리는 집합이
`guard_bash.allow_reason()` 이 이미 통과시키던 집합과 **정확히 같다** —
판정 함수를 재사용하므로 사본이 없고(AGENTS: "중복은 곧 갈라진다"), 여기서 allow 가 나오는
명령은 전부 PreToolUse 가 이미 안전하다고 판정했던 것뿐이다.
즉 이 훅이 바꾸는 것은 **"guard 가 안전하다고 한 것이 settings 의 ask 때문에 프롬프트를
띄우던 구멍"** 하나뿐이다.

그리고 `deny_reason()` 이 걸리면 여기서도 **deny 한다** — 조일 수는 있어도 풀지는 않는다.

**미검증 (2026-07-28):** 이 훅이 실제로 `ask` 를 이기는지는 **측정하지 못했다.**
그날 세션이 `acceptEdits` 였는데 settings ask 2건(`mkdir *`·`date *`)과 guard 가 낸
ask 1건(`git checkout`)이 **셋 다 프롬프트 없이 실행**돼, 프롬프트를 재현할 수 없었다.
→ 프롬프트가 실제로 뜨는 세션에서 `python tools/test_checks.py` 가 아니라 **눈으로**
   확인할 것. 안 되면 settings.json 의 `PermissionRequest` 블록만 지우면 원상복구다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from guard_bash import allow_reason, deny_reason, read_payload  # noqa: E402


def gate_decision(tool_name, tool_input):
    """(behavior, reason) 또는 None(판정 보류 — 평소대로 승인창).

    **판정은 전부 이 함수 안에 둔다** — guard_bash.deny_reason 과 같은 이유다.
    main() 에 직접 쓰면 `test_guard_rules` 가 그 규칙을 볼 수 없다.
    """
    if tool_name != "Bash":
        return None                      # Bash 밖은 건드리지 않는다(범위를 좁게 유지)
    command = str((tool_input or {}).get("command", ""))
    if not command.strip():
        return None
    reason = deny_reason(command)
    if reason:
        return ("deny", reason)          # 조이는 쪽은 언제나 허용된다
    reason = allow_reason(command)
    if reason:
        return ("allow", reason + " (PermissionRequest — 새로 열리는 권한 없음)")
    return None


def main():
    try:
        payload = read_payload()
    except Exception:
        return                            # 페이로드를 못 읽으면 막지 않는다(가드가 인질이 되면 안 된다)
    verdict = gate_decision(str(payload.get("tool_name", "")),
                            payload.get("tool_input") or {})
    if not verdict:
        return
    behavior, reason = verdict
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PermissionRequest",
        "decision": {"behavior": behavior},
        "permissionDecisionReason": reason,
    }}, sys.stdout)


if __name__ == "__main__":
    main()
