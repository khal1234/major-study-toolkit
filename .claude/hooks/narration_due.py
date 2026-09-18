#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""UserPromptSubmit 훅 — **턴이 시작될 때** 지난 턴 중계 수를 문맥에 넣는다 (신설 2026-08-24).

    settings.json 의 UserPromptSubmit 훅으로 건다(이 리포의 자리):
        python "$CLAUDE_PROJECT_DIR/.claude/hooks/narration_due.py"

## 왜 열렸나 — Stop 은 이미 늦다 (같은 지적 4회차)

*[발화 생략]*

2026-08-24 에 `check_narration --last-turn` 을 **Stop 훅**에 걸었는데, 같은 세션에서
**또 어겼다.** Stop 은 턴이 **끝난 뒤**에 서서 이미 나간 말을 못 되돌린다 — 그 자의
독스트링이 스스로 *[발화 생략]* 라고 적어 뒀는데,
**그 「다음 턴」에 그 사실이 문맥에 없으면** 아무 일도 안 일어난다.

★ **이 자가 서는 자리가 그 「다음 턴의 첫머리」다.** `UserPromptSubmit` 의 표준출력은
  그 턴의 문맥으로 들어간다 — **글을 쓰기 직전**에 지난 턴의 수가 보인다.

## 왜 셋이 다 필요한가 — 자리가 다르다

| 자리 | 트리거 | 무엇을 할 수 있나 |
|---|---|---|
| `UserPromptSubmit` (이 자) | 턴 **시작** | **쓰기 전에** 보여 준다 — 유일하게 예방이다 |
| Stop (`--last-turn`) | 턴 **끝** | 방금 넘긴 것을 사용자 화면에 알린다 |
| `commit`·`close_report` | 커밋·마감 | 세션 누적 추세 |

## 판정선을 새로 만들지 않는다

`도구/check_narration.py` 의 `Tally` 와 `MAX_PER_USER_TURN` 을 **그대로 부른다.**
판정선이 두 벌이면 갈린다 — 그 파일이 이미 그 이유로 `audit_session_cost` 와
판정을 한 클래스로 합쳐 두었다.

★ **`completed=True` 로 부른다.** 이 훅이 설 때 **새 사용자 발화가 기록에 이미 들어가
  있을 수 있어서**, 그냥 «마지막 발화 이후» 로 창을 잡으면 언제나 0줄이 나온다 —
  **자가 조용히 꺼지고, 꺼진 자는 「깨끗하다」와 겉모습이 같다.**
  창 고르기는 `check_narration.turn_window` 가 정본이다.

☐ 못 보는 것
- **강제가 아니다.** 문맥에 한 줄 넣을 뿐이라 그것을 읽고도 또 쓰면 못 막는다.
  턴 안에서 내 문장을 보는 자는 없다 — `PreToolUse` 는 도구 인자만 본다.
- 지난 턴이 깨끗하면 **한 글자도 안 낸다**(`open_items`·`cost_brief` 와 같은 규율).
  그래서 «조용함» 이 «꺼짐» 일 수 있고, 그건 `--last-turn` 을 손으로 돌려 확인한다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ★ 도구 폴더 이름은 프로젝트마다 다르다(공용 폴더 `도구/` · 여기 `tools/`). 하나로 박으면
#   가져간 쪽에서 조용히 죽는다 — `commit.py` 가 `ROOT/"tools"` 를 박아 공용 폴더에서 네 번
#   되살아난 그 부류다(공용 폴더 `변경일지.md` 2026-08-14·17·20).
# ★★ **이 리포는 컨테이너 루트에서도 돈다** (전공정리 이식 2026-08-25). 공용 폴더 판본은
#   `CLAUDE_PROJECT_DIR/도구|tools` 를 봤는데, 컨테이너 루트 세션에서는 그 자리가
#   `<컨테이너>/tools` 라 없다 — 임포트가 실패하고 **자가 조용히 꺼진다**(이 훅의
#   독스트링이 스스로 경고한 «꺼진 자는 깨끗한 것과 겉모습이 같다»). 그래서 **찾는 자를
#   새로 만들지 않고** 같은 폴더의 `gate_rerun_guard.find_tools` 를 그대로 부른다
#   (그 자가 조상 폴더를 훑는다 — 두 벌이면 갈린다는 그 파일의 판정선).
sys.path.insert(0, HERE)
try:
    from gate_rerun_guard import find_tools
    _tools = find_tools(HERE) or find_tools(os.environ.get("CLAUDE_PROJECT_DIR") or ROOT)
except Exception:                    # noqa: BLE001 — 훅은 어떤 경우에도 세션을 막지 않는다
    _tools = None
if _tools:
    sys.path.insert(0, _tools)

try:
    from check_narration import last_turn_verdict, latest_session, repo_root
except ImportError:
    sys.exit(0)          # 자가 없으면 조용히 빠진다 — 훅이 세션을 막지 않는다


def main():
    try:
        p = latest_session(repo_root())
    except Exception:
        return 0
    if not p or not p.exists():
        return 0         # ★ 훅은 **못 찾았을 때도 조용해야 한다**
    return last_turn_verdict(p, completed=True, prefix="지난 ")


if __name__ == "__main__":
    sys.exit(main())
