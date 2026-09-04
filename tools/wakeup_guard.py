"""루프 재예약 감시 — 사람의 기억이 아니라 훅이 본다 (2026-08-07 신설 · 2026-08-26 개편).

★★ **이 도구는 컴퓨터를 끄지 않는다.** 2026-08-26 에 사용자가 종료를 은퇴시켰다
([사용자 발화 인용 생략]).
`shutdown.exe` 를 부르던 셋(`_shutdown`·`cancel`·`arm`)과 `subprocess` 를 통째로 들어냈고,
남은 것은 **「예약 감시」 하나**다. 옛 이름 `shutdown_timer.py` 도 같이 은퇴했다 —
이름이 남으면 다음 회차가 그 이름을 근거로 종료를 되살린다.

**왜 감시는 남기나 — 루프가 조용히 서는 사고가 두 번 났다.**

⑴ 2026-08-07. `/loop` 7회차 끝에 `ScheduleWakeup` 을 빠뜨려 루프가 죽었다.
⑵ 2026-08-26. 같은 일이 또 났다 — 「전기전자로 넘어갑니다」라고 써 놓고 예약을 안 걸었다.
   사용자: [사용자 발화 인용 생략]

→ 자리를 비운 사이 도는 루프에서 **예약을 빠뜨린 턴은 곧 아침까지 서 있는 화면**이다.
  사용자 지시 6번이 [사용자 발화 인용 생략] 라고 ⑴ 을
  정확히 예고했는데도 났다 — **경고문으로는 못 막는 부류**라서 훅으로 옮겼다.

**형태 — Stop 훅이 턴이 끝날 때마다 `tick` 을 부른다.**

⑴ 루프 모드가 켜져 있는데 이번 턴에 `ScheduleWakeup` 이 없으면 **멈춤을 막고**(exit 2)
   그 사실을 모델에게 알린다. 루프가 죽는 경로 그 자체를 닫는다.
⑵ 깃발이 없으면 **아무것도 하지 않는다.** 기본값이 「조용함」 쪽이라, 훅이 깔려 있어도
   루프를 안 돌리는 세션에는 영향이 0이다.
⑶ 깃발에 **만료 시각**을 둔다(기본 12시간). 끄는 것을 잊어도 하루를 넘겨 잔소리하지 않는다.

**`StopFailure` 배선은 함께 걷어냈다** (옛 `push` 진입점). 그 훅의 유일한 일이 「종료 예약을
뒤로 민다」였는데 밀 예약이 없어졌다. 감시를 그쪽으로 옮기지도 않는다 — 이미 오류로 끝난
자리에서 멈춤을 막으면 재시도 폭주가 된다. **아무 일도 안 하는 훅을 등록해 두는 것**이
이 리포가 「꺼진 자」라 부르는 형태다.

깃발은 `.claude/wakeup-guard.json` — `.gitignore` 안이라 커밋되지 않고 워크트리마다 따로다.

    python tools/wakeup_guard.py on [--hours 12]
    python tools/wakeup_guard.py off
    python tools/wakeup_guard.py status
"""

import argparse
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAG = os.path.join(ROOT, ".claude", "wakeup-guard.json")

DEFAULT_HOURS = 12        # 깃발 자동 만료 — 끄는 것을 잊어도 여기서 멈춘다

NAG = ("루프 모드가 켜져 있는데 이번 턴에 ScheduleWakeup 이 없다. "
       "다음 회차를 예약하고 끝내라 — 예약을 빼먹으면 루프가 여기서 조용히 죽고, "
       "「다음으로 넘어갑니다」라고 써 둔 화면 그대로 아침까지 서 있는다 "
       "(2026-08-07 · 2026-08-26 실사고). "
       "루프를 정말 끝낼 것이면 `python tools/wakeup_guard.py off` 로 루프 모드를 먼저 꺼라.")


# ── 깃발 (순수 함수는 테스트가 직접 부른다) ──────────────────────────────────

def is_active(data, now):
    """깃발이 켜져 있고 아직 만료되지 않았는가. `data` 가 None 이면 꺼진 것이다."""
    if not isinstance(data, dict):
        return False
    try:
        return float(data.get("expiresAt", 0)) > float(now)
    except (TypeError, ValueError):
        return False


def read_flag():
    try:
        with open(FLAG, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def write_flag(data):
    os.makedirs(os.path.dirname(FLAG), exist_ok=True)
    with open(FLAG, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def clear_flag():
    try:
        os.remove(FLAG)
    except OSError:
        pass


# ── 이번 턴에 재예약을 했는가 (순수 함수) ────────────────────────────────────

def _is_user_prompt(entry):
    """사용자가 실제로 친 발화인가. 도구 결과(tool_result)는 발화가 아니다."""
    if not isinstance(entry, dict) or entry.get("type") != "user":
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list):
        kinds = {c.get("type") for c in content if isinstance(c, dict)}
        if kinds and kinds <= {"tool_result"}:
            return False
    return True


def _tool_names(entry):
    if not isinstance(entry, dict) or entry.get("type") != "assistant":
        return []
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return []
    return [c.get("name") for c in content
            if isinstance(c, dict) and c.get("type") == "tool_use"]


def wakeup_in_last_turn(entries):
    """마지막 사용자 발화 뒤의 도구 호출 가운데 ScheduleWakeup 이 있는가."""
    for entry in reversed(entries):
        if _is_user_prompt(entry):
            break
        if "ScheduleWakeup" in _tool_names(entry):
            return True
    return False


def load_transcript(path):
    entries = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return entries


# ── 훅 진입점 ────────────────────────────────────────────────────────────────

def tick(payload, now=None):
    """Stop 훅이 부른다. `(exit_code, stderr)` 를 돌려준다.

    바깥에 내는 부작용은 둘 — ⑴ 깃발 파일을 지우는 것(만료됐을 때) ⑵ **자동 무장**(신설).
    예전에는 shutdown 관련 부작용도 있었는데 2026-08-26 에 전부 걷어냈다.

    ★ 자동 무장 (2026-09-02, 재발 3회째 — medesign·heat·instru·numeth 가 한 번, 그 뒤
    heat·sysctrl 이 또 났다). `on` 은 **사람이 쓰는 켜기 명령**인데, 실사용은 컨테이너 루트
    세션이 여러 과목 세션에 "루프 써서 계속해라"를 던지는 형태라 **누군가 매번 그 명령을
    잊지 않고 켜야 하는 구조**였다 — 그건 성실성에 기대는 방지장치라 규칙 7⑷ 위반이다.
    → 대신 **관측 가능한 사건**에 건다: 이번 턴에 `ScheduleWakeup` 이 실제로 불렸다는 것 자체가
    "이 세션이 지금 루프를 돈다"는 선언이다. 깃발이 없어도 그 사건이 보이면 그 자리에서
    무장해, 다음 턴부터 예약을 빠뜨리면 바로 잡힌다. 잘못 무장돼도 12시간 뒤 조용히 풀린다.
    """
    now = time.time() if now is None else now
    data = read_flag()

    if data is None:                       # 한 번도 안 켰다
        entries = load_transcript(payload.get("transcript_path") or "")
        if entries and wakeup_in_last_turn(entries):
            write_flag({"expiresAt": now + DEFAULT_HOURS * 3600, "armedBy": "auto"})
        return 0, ""
    if not is_active(data, now):           # 만료됐다 — 깃발만 거둔다
        clear_flag()
        return 0, ""

    if payload.get("stop_hook_active"):    # 이미 한 번 막았다 — 되풀이하지 않는다
        return 0, ""
    entries = load_transcript(payload.get("transcript_path") or "")
    if entries and not wakeup_in_last_turn(entries):
        return 2, NAG
    return 0, ""


# ── CLI ──────────────────────────────────────────────────────────────────────

def _fmt(epoch):
    return time.strftime("%m-%d %H:%M", time.localtime(epoch))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=["on", "off", "status", "tick"])
    ap.add_argument("--hours", type=float, default=DEFAULT_HOURS,
                    help="루프 모드 자동 만료 (기본 %d시간)" % DEFAULT_HOURS)
    args = ap.parse_args()

    if args.action == "on":
        expires = time.time() + args.hours * 3600
        write_flag({"expiresAt": expires})
        print("루프 감시 ON — 턴이 끝날 때마다 그 턴에 ScheduleWakeup 이 있었는지 본다.")
        print("  없으면 멈춤을 막고 다시 예약하라고 알린다 (루프가 조용히 서지 않는다)")
        print("  ★ 이 도구는 PC 를 끄지 않는다 — 종료는 2026-08-26 에 은퇴했다")
        print("  깃발 만료: " + _fmt(expires) + " (이후로는 훅이 아무 말도 안 한다)")
        print("  끄기: python tools/wakeup_guard.py off")
        return 0

    if args.action == "off":
        clear_flag()
        print("루프 감시 OFF — 훅이 이제 아무것도 보지 않는다.")
        return 0

    if args.action == "status":
        data = read_flag()
        if not is_active(data, time.time()):
            print("루프 감시 OFF" + (" (깃발 만료됨)" if data else ""))
            return 0
        print("루프 감시 ON — 깃발 만료 " + _fmt(float(data["expiresAt"])))
        return 0

    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        payload = {}
    payload = payload if isinstance(payload, dict) else {}
    code, message = tick(payload)
    if message:
        sys.stderr.write(message + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
