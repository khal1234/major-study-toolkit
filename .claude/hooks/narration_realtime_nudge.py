#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PostToolUse — **턴 안에서 실시간으로**, 그러나 **막지 않고** 진행 중계를 귀띔한다.

    settings.json 의 PostToolUse 훅으로 건다 (매처는 실제 작업 도구 — Bash|Edit|Write 등):
        python "$CLAUDE_PROJECT_DIR/훅/narration_realtime_nudge.py"

## 이전 실험(narration_realtime_experiment.py)과 다른 점

그 자는 `PreToolUse` 에서 **거부(deny)** 했다 — 예산을 넘으면 그 턴의 남은 도구 호출이
전부 막히는 결함이 있었다(2026-08-28, 공용 폴더 설계 단계에서 찾고 전공정리 실험에서 확인
시도 — 하네스 auto 분류기가 설치 자체를 막아 실행은 못 함).

이 자는 **`PostToolUse` 에서 `additionalContext` 로만 귀띔한다 — 아무것도 거부하지
않는다.** 2026-08-28 공용 폴더 자신에게 실측으로 확인됨: `PostToolUse` 의 `additionalContext`
는 **거부 없이, 도구 호출 직후 즉시 모델 문맥에 실제로 들어온다**(표식 문자열로 검증).

## 왜 이게 안전한가

- **막는 통로가 없다.** `permissionDecision` 을 아예 안 쓴다 — 이 자가 무슨 값을 내도
  도구 호출은 항상 그대로 진행된다. 이전 자의 결함(누적 카운트가 못 줄어 영구 막힘)이
  **원천적으로 발생할 수 없다.**
- **가장 나쁜 경우가 "무시당한다"뿐이다.** 모델이 귀띔을 읽고도 계속 중계를 쓰면
  아무 일도 안 생긴다 — 이전과 같은 상태로 돌아갈 뿐 더 나빠지지 않는다.

## 판정선

`check_narration.Tally` 를 그대로 쓴다 — 진행 중인 턴(`turn_window(recs, completed=False)`)
안의 relay 줄 수를 잰다. 상한을 넘으면 **매번** 알리지 않고 **넘은 시점에 한 번만** 알린다
(안 그러면 그 뒤 도구 호출마다 계속 뜨는 게 곧 소음이 된다 — 그 자체가 또 다른 「중계」다).
같은 세션·같은 턴에서 이미 알렸으면 조용히 넘어간다(래치, `session_size_guard.py` 와 같은 형태).
"""
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "도구"))
for _name in ("도구", "tools"):
    _d = os.path.join(os.environ.get("CLAUDE_PROJECT_DIR") or "", _name)
    if os.path.isdir(_d):
        sys.path.insert(0, _d)
        break

# ★ 이 리포 전용 정정(2026-09-06) — `json.load(sys.stdin)`은 Windows에서 cp949로
#   깨진다(공용 공용 폴더 판은 이 문제를 안 겪는 환경에서 짜여 그대로였다). 이 리포는
#   `common_guard.read_payload()`로 이미 고쳐 둔 사고가 있어(2026-07-27) 그걸 쓴다 —
#   판정을 새로 안 만들고 이미 검증된 것을 재사용한다.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from common_guard import read_payload
except ImportError:
    def read_payload(source=None):
        import json as _json
        return _json.load(sys.stdin)

BUDGET = 3          # 예산을 넘은 「시점」만 잡는다 — 넘은 뒤 계속 알리지 않는다(래치)
LATCH = Path(os.environ.get("TEMP") or "/tmp") / "claude-narration-nudge-latch"

try:
    from check_narration import Tally, turn_window, records, latest_session, repo_root
except ImportError:
    def main():
        return 0
else:
    def main():
        try:
            payload = read_payload()
        except Exception:
            return 0
        sid = str(payload.get("session_id") or "")
        try:
            root = repo_root()
            p = latest_session(root)
            if not p or not p.exists():
                return 0
            recs = list(records(p))
            s, e = turn_window(recs, completed=False)
            t = Tally()
            for r in recs[s:e]:
                t.feed(r)
            n = t.result()["n"]
        except Exception:
            return 0  # 자기 실패는 조용히 통과 — 절대 도구 호출을 막지 않는다

        if n <= BUDGET:
            return 0

        LATCH.mkdir(parents=True, exist_ok=True)
        mark = LATCH / f"{sid}.turn"
        # ★ NARU-003 (Codex 스테이지9 §3) — 래치 키가 세션 id 뿐이라 **턴 경계를 못 봤다**.
        #   `n` 은 진행 중인 턴만 세는데(위 turn_window) 래치는 세션 내내 안 지워져서, 새 턴이
        #   `last`(직전 턴에서 찍힌 값)보다 낮게 시작하면 `n <= last` 가 참이 되어 새 턴의
        #   진짜 초과를 놓쳤다. **턴 시작 인덱스 `s`** 를 래치에 같이 적어 턴이 바뀌면
        #   `last` 를 0으로 되돌린다.
        last, last_turn_start = 0, None
        try:
            if mark.exists():
                raw = json.loads(mark.read_text(encoding="utf-8"))
                last_turn_start, last = raw.get("turn_start"), int(raw.get("max_n") or 0)
        except (OSError, ValueError):
            last, last_turn_start = 0, None
        if last_turn_start != s:
            last = 0          # 새 턴 — 지난 턴의 래치 값은 안 물려받는다
        if n <= last:
            return 0
        try:
            mark.write_text(json.dumps({"turn_start": s, "max_n": n}), encoding="utf-8")
        except OSError:
            pass

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"[진행 중계 · 실시간] 이번 턴에서 이미 {n}줄 나갔습니다(상한 {BUDGET}). "
                    "이 알림은 도구 호출을 막지 않습니다 — 다음 문장부터 중계를 멈춰 주세요. "
                    "판정거리가 있는 최종 보고만 남기면 됩니다."
                ),
            }
        }, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    sys.exit(main())
