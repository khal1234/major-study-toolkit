#!/usr/bin/env python
"""InstructionsLoaded 훅 — 지침 파일이 **언제·왜** 로드됐는지 남긴다.

열린 날 2026-07-28. `docs/context-budget-plan.md` 의 **검산 도구**다(그 계획 5단계 중 3번).

**왜 필요한가 — 계획의 성패를 확인할 방법이 없었다.**
예산 계획은 AGENTS.md 의 삽화 표준 등을 `.claude/rules/` 로 내리고 `paths` 프론트매터를
붙여 **그 패턴의 파일을 읽을 때만** 로드되게 만드는 것이다. 문제는 *[발화 생략]* 를
확인할 수단이 없다는 것이었다. 안 돌면 규칙이 **없는 채로** 삽화를 만들게 되고, 그게 바로
2026-07-21 에 같은 지적이 3~4라운드 반복된 그 사고다(AGENTS 문서 배치 원칙의 근거).

공식 문서 확인(2026-07-28): `InstructionsLoaded` 의 **matcher 는 load reason** 이고
값은 `session_start` · `nested_traversal` · **`path_glob_match`** · `include` · `compact` 다.
→ 경로 스코핑이 실제로 발동했는지를 `path_glob_match` 로 **정확히 걸러** 볼 수 있다.
   "됐겠지" 가 아니라 로그가 남는다(AGENTS 규칙 11: 판정은 명령으로 뒷받침한다).

**토큰 비용 0** — `permission_log.py` 와 같은 설계다. stdout 에 아무것도 쓰지 않고
파일에만 append 한다. 공식 문서상 이 이벤트는 decision control 이 없다
(*"No decision control. Used for side effects like logging or cleanup"*).

읽는 법: `python tools/inspect_data.py` 같은 도구가 아직 없으므로 그냥 파일을 Read 한다.
계획이 끝나 스코핑이 확인되면 이 훅은 **꺼도 된다** — 진단 도구이지 상시 장치가 아니다.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from guard_bash import read_payload  # noqa: E402

_LOG_DIR = os.environ.get("CLAUDE_HOOK_LOG_DIR") or os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(_LOG_DIR, ".instructions_load.log")
MAX_LINES = 500          # 무한정 자라지 않게 — 진단용이라 최근 것만 있으면 된다
SCHEMA_VERSION = 2       # 2 = append 전용(기록이 안 사라진다). 1(= `v` 없음)은 유실 가능.


def load_record(payload, now=None):
    """남길 한 줄(dict). 순수 함수 — 테스트가 직접 부른다.

    `file_path` 는 **파일 이름만** 남긴다. 절대경로를 통째로 쌓으면 로그가 커지기만 하고,
    어느 지침이 로드됐는지는 파일명으로 충분히 갈린다.
    """
    path = str(payload.get("file_path") or "")
    return {
        # 기록 형식 판(2026-09-12 신설). `v` 가 없는 줄은 **읽고-고쳐-쓰던 시절**의 것이라
        # 동시 이벤트에서 한 건씩 조용히 사라졌다 — `guard_write` 가 이 칸으로 «믿을 수 있는
        # 기록인가» 를 가른다. 값을 올릴 일이 생기면 그 자리도 함께 본다.
        "v": SCHEMA_VERSION,
        "ts": now or time.strftime("%Y-%m-%d %H:%M:%S"),
        "file": os.path.basename(path.replace("\\", "/")) or "?",
        "memory_type": str(payload.get("memory_type") or "?"),
        "load_reason": str(payload.get("load_reason") or "?"),
        # `guard_write` 가 「이 세션에 그 경로 규칙이 실렸나」를 이 칸으로 가른다.
        "session_id": str(payload.get("session_id") or ""),
    }


def trim(lines, limit=MAX_LINES):
    """오래된 줄을 버린다(순수 함수)."""
    return lines[-limit:] if len(lines) > limit else lines


# 잘라내기를 미루는 여유분. 기록 자체는 append 라 절대 안 잃고, **자르기**만 가끔 진다 —
# 진 자르기는 로그가 조금 길어질 뿐이라 해가 없다(잃은 기록은 가드를 틀리게 만든다).
TRIM_SLACK = 2


def main():
    """한 줄을 **append** 한다 — 읽고-고쳐-쓰지 않는다.

    무엇을 재나: `InstructionsLoaded` 한 건 = 한 줄.
    왜 append 인가(2026-09-12 실측): 한 번의 `Read` 가 경로 규칙 둘을 동시에 물리면 훅 프로세스
    둘이 같은 순간에 뜬다. 읽고-고쳐-쓰기였을 때 둘이 같은 `lines` 를 읽고 차례로 덮어써
    **한 건이 통째로 사라졌고**(17:26:12 `figures.md` 만 남고 `content.md` 유실), 그 유실을
    `guard_write` 가 「규칙이 안 실렸다」로 읽어 정당한 장 JSON 수정을 막았다. 찢어진 줄
    (`"}` 한 줄)도 같은 자리에서 나왔다.
    못 보는 것: 동시 append 가 OS 단에서 섞이는 경우(줄이 짧아 실제로는 안 났다) · 자르기 경합.
    """
    try:
        payload = read_payload()
    except Exception:
        return
    try:
        line = json.dumps(load_record(payload), ensure_ascii=False)
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        with open(LOG_PATH, encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        if len(lines) > MAX_LINES * TRIM_SLACK:
            with open(LOG_PATH, "w", encoding="utf-8") as fh:
                fh.write("\n".join(trim(lines)) + "\n")
    except Exception:
        pass
    # stdout 에 아무것도 쓰지 않는다.


if __name__ == "__main__":
    main()
