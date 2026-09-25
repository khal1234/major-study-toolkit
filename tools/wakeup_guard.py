"""루프 재예약 감시 — 사람의 기억이 아니라 훅이 본다 (2026-08-07 신설 · 2026-08-26 개편).

★★ **이 도구는 컴퓨터를 끄지 않는다.** 2026-08-26 에 사용자가 종료를 은퇴시켰다
(*[발화 생략]*).
`shutdown.exe` 를 부르던 셋(`_shutdown`·`cancel`·`arm`)과 `subprocess` 를 통째로 들어냈고,
남은 것은 **「예약 감시」 하나**다. 옛 이름 `shutdown_timer.py` 도 같이 은퇴했다 —
이름이 남으면 다음 회차가 그 이름을 근거로 종료를 되살린다.

**왜 감시는 남기나 — 루프가 조용히 서는 사고가 두 번 났다.**

⑴ 2026-08-07. `/loop` 7회차 끝에 `ScheduleWakeup` 을 빠뜨려 루프가 죽었다.
⑵ 2026-08-26. 같은 일이 또 났다 — 「전기전자로 넘어갑니다」라고 써 놓고 예약을 안 걸었다.
   사용자: *[발화 생략]*

→ 자리를 비운 사이 도는 루프에서 **예약을 빠뜨린 턴은 곧 아침까지 서 있는 화면**이다.
  사용자 지시 6번이 *[발화 생략]* 라고 ⑴ 을
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

★★ **둘째 감시 — 「회차가 너무 짧다」 (2026-09-08 신설, 같은 지적 3회째).**

예약을 거는 것만으로는 루프가 살아 있다고 할 수 없다. 사용자 지적(2026-07-30 원장,
2026-09-08 재발):

    "loop 돌리면 왤캐 작업을 조금조금하는거지 … loop만 하면 한번 채팅당 돌리는 양이
     확 낮아지는 느낌이네" · "암만 생각해도 회차간 작업량 자체가 너무 적은데"
    "애초에 루프는 계속 작업을 해야 하는데 안하길래 거는 최소한의 장치지.
     이렇게 계속 작은 단위로 끊고 멈추고 끊고 멈추고 하려고 걸은게 아닌데"

2026-07-30 에 **문서로만** 닫았고(원장 상태 「닫힘(문서) · 기계 잠금 없음」) 그래서 또 났다.
실행 규율 6 이 *[발화 생략]* 라고 적어 뒀지만 **아무도 세지 않았다** — 판정선이 관측 불가능하면 규칙은 안 지켜진다.

→ **닫았다는 것의 관측 가능한 형태는 「커밋」이다.** 루프 회차인데 그 턴에 `commit.py` 가
  한 번도 안 불렸으면 그 회차는 아무것도 안 닫은 것이라 멈춤을 막는다. 한 항목이 막혀 있으면
  **같은 턴 안에서** 다음 항목으로 이어 가는 것이 루프의 형태이고, 정말 전부 막혔으면
  회차를 늘릴 것이 아니라 `off` 로 루프를 끝내고 보고하는 것이 맞다.

☐ **못 보는 것:** 커밋 하나를 억지로 쪼개 넣는 것 · 「막혔다」가 진짜인지. 그래서 이 자는
  **하한만** 세운다(0 을 막는다). 회차의 크기를 재는 눈금은 `--measure` 가 낸다.

☐ **대화 턴은 대상이 아니다.** 마지막 사용자 발화가 `/loop` 가 아니면 이 감시는 조용하다 —
  사용자가 중간에 말을 걸어 답하는 턴까지 막으면 그건 대화를 막는 것이다.

깃발은 `.claude/wakeup-guard.json` — `.gitignore` 안이라 커밋되지 않고 워크트리마다 따로다.

    python tools/wakeup_guard.py on [--hours 12]
    python tools/wakeup_guard.py off --reason <user|blocked|done>   # 문맥 크기는 사유가 아니다
    python tools/wakeup_guard.py status
    python tools/wakeup_guard.py measure                 # 훅이 쌓아 둔 회차 크기 분포
    python tools/wakeup_guard.py measure --transcript <세션 jsonl>   # 전사본에서 직접
"""

import argparse
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAG = os.path.join(ROOT, ".claude", "wakeup-guard.json")
# 회차 크기 기록 — **훅만이 전사본을 읽을 수 있어서** 여기 남긴다. 전사본은 홈의
# `~/.claude/**` 에 있고 그쪽은 규칙 5 가 셸에서 막는다(막는 것이 맞다). 훅은 페이로드로
# 경로를 받으므로 볼 수 있고, 본 것을 리포 안에 적어 두면 나중에 사람이 눈금을 잰다.
ROUNDS = os.path.join(ROOT, ".claude", "loop-rounds.jsonl")
ROUNDS_KEEP = 500        # 마지막 N줄만 남긴다 — 눈금을 내는 데 그 이상은 안 쓴다

DEFAULT_HOURS = 12        # 깃발 자동 만료 — 끄는 것을 잊어도 여기서 멈춘다

NAG = ("루프 모드가 켜져 있는데 이번 턴에 ScheduleWakeup 이 없다. "
       "다음 회차를 예약하고 끝내라 — 예약을 빼먹으면 루프가 여기서 조용히 죽고, "
       "「다음으로 넘어갑니다」라고 써 둔 화면 그대로 아침까지 서 있는다 "
       "(2026-08-07 · 2026-08-26 실사고). "
       "루프를 정말 끝낼 것이면 `python tools/wakeup_guard.py off --reason <user|blocked|done>` 로 루프 모드를 먼저 꺼라"
       " — 문맥 크기는 사유가 아니다(하네스가 자동 압축한다).")

# 회차 하한 — **1 은 「0 을 막는다」는 뜻이지 고른 수가 아니다.** 닫은 것이 하나도 없는
# 회차를 막을 뿐, 「얼마나 커야 하나」는 이 자가 정하지 않는다(`measure` 가 눈금을 낸다).
MIN_COMMITS = 1

# ★★ 콘텐츠 편집 하한 — **다섯 번째 재발에서 놓았다** (2026-09-10).
#
#   사용자: *[발화 생략]*
#
# `MIN_COMMITS = 1` 은 **0 만 막는다.** 실측: 문제가 된 회차들은 커밋이 2~3회였고 하한을
# 여유롭게 넘겼다 — 즉 그 자는 이 병을 못 본다. 세는 것을 「커밋 수」에서 **「콘텐츠 파일을
# 몇 번 고쳤나」** 로 옮긴다.
#
# **8 은 고른 값이다**(규칙 16). 이 리포에서 자연스러운 단위는 **한 챕터의 문항 넷**이고,
# 사용자가 짚은 회차는 2·3·5 였다. 8 은 그 단위의 **두 배**라 「한 챕터를 닫고 바로 멈추는」
# 형태를 막는다 — 「한 챕터면 충분한가」가 아니라 「한 챕터에서 끊지 마라」가 이 수의 뜻이다.
# 회차가 정말 막혔으면 하한을 채우는 것이 아니라 **루프를 끝내고 보고한다**(아래 문구).
MIN_EDITS = 8
DATA_MARKS = ("/data/", "\\data\\")

SHORT_ROUND = (
    "이번 루프 회차는 **아무것도 닫지 않았다** — 도구 호출 %d회에 커밋 0회다(하한 %d).\n"
    "  루프는 「계속 작업하는 장치」이지 작은 단위로 끊고 멈추는 장치가 아니다"
    " (사용자 2026-07-30 · 2026-09-08 재발: *\"이렇게 계속 작은 단위로 끊고 멈추고"
    " 끊고 멈추고 하려고 걸은게 아닌데\"*).\n"
    "  → 한 항목이 막혔으면 **그 자리에서 다음 항목으로 이어 간다** — 예약을 걸고 60초를"
    " 버리는 것이 아니라 같은 턴 안에서 하나를 닫는다.\n"
    "  → 정말로 전부 막혔으면 회차를 늘릴 것이 아니라"
    " `python tools/wakeup_guard.py off --reason blocked` 로 루프를 끝내고 무엇이 막혔는지 보고해라.")

THIN_ROUND = (
    "이번 루프 회차는 **너무 얇다** — `data/**` 편집이 %d회다(하한 %d).\n"
    "  사용자 2026-09-10(다섯 번째 재발): 회차마다 삽화 두세 개만 하고 끝내는 패턴이 반복됐다.\n"
    "  ★ **커밋·빌드·푸시는 챕터의 끝이지 턴의 끝이 아니다.** 한 챕터를 닫았으면"
    " 예약하지 말고 **그 자리에서 다음 챕터로 이어 간다** — 다음 대상은 그 자리에서"
    " 자가 정한다(`audit_item_figure_reasons` · `audit_theory_figure_reasons` ·"
    " `audit_convention_drift`).\n"
    "  → 예약을 부르는 자리는 셋뿐이다: **사용자 판정이 있어야 다음이 안 열릴 때 ·"
    " 외부를 기다릴 때 · 턴 출력 한계에 실제로 닿았을 때.**"
    " 그중 하나라면 이 훅을 무시하지 말고 **루프를 끝내고 보고해라**"
    " (`python tools/wakeup_guard.py off --reason <user|blocked|done>` — 문맥 크기는 사유가 아니다).\n"
    "  정본 `docs/2026-09-10-루프-회차는-길게.md`")


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


# ── 회차의 크기 (순수 함수) ──────────────────────────────────────────────────

def _prompt_text(entry):
    """사용자 발화의 본문. 슬래시 명령은 `<command-name>` 로 실려 온다."""
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content
                        if isinstance(c, dict) and c.get("type") == "text")
    return ""


def is_loop_round(entry):
    """이 발화가 `/loop` 회차를 연 것인가. 대화 턴은 이 감시의 대상이 아니다."""
    text = _prompt_text(entry)
    return "/loop" in text


def _tool_inputs(entry):
    if not isinstance(entry, dict) or entry.get("type") != "assistant":
        return []
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return []
    return [c.get("input") or {} for c in content
            if isinstance(c, dict) and c.get("type") == "tool_use"]


_DATA_ARG = re.compile(r"data[/\\]([^\s\"']+?\.json)")


def _data_paths(command):
    """커밋 명령에 적힌 `data/**` 경로들 — 「이 회차가 무엇을 고쳤나」의 목록. 순수 함수."""
    return {m.group(1).replace("\\", "/") for m in _DATA_ARG.finditer(command)}


def round_work(entries):
    """마지막 턴의 (도구 호출 수, 커밋 수, 루프 회차인가).

    커밋은 `commit.py` 를 부른 Bash 호출로 센다 — 이 리포에서 커밋하는 길이 그것뿐이라
    (`git commit` 은 승인을 타고 실행 규율 7 이 도구를 쓰라고 정해 뒀다) 세는 자리가 하나다.
    """
    tools = commits = edits = 0
    tool_written, hand_edited = set(), set()
    loop = False
    for entry in reversed(entries):
        if _is_user_prompt(entry):
            loop = is_loop_round(entry)
            break
        for name, inp in zip(_tool_names(entry), _tool_inputs(entry)):
            tools += 1
            if name == "Bash":
                command = str(inp.get("command") or "")
                if "commit.py" in command:
                    commits += 1
                    # ★ **리포 도구가 고친 데이터도 센다** (넓힌 날 2026-09-11).
                    #   이 자는 `Edit`/`Write` 호출만 셌는데, `set_no_diagram_reason.py`·
                    #   `fix_figure_vertical_balance.py` 처럼 **여러 장을 한 번에 고치는
                    #   리포 도구**는 Bash 로 파일을 쓰므로 한 건도 안 잡혔다. 그래서 한 회차에
                    #   아홉 장을 닫고도 「너무 얇다」로 막혔다 — 자가 일을 못 본 것이지 일이
                    #   얇았던 것이 아니다. **문턱(8)은 그대로 두고 세는 범위만 넓힌다.**
                    #   커밋은 경로를 명시하므로(`git add -A` 금지) 그 인자가 곧 고친 목록이다.
                    tool_written.update(_data_paths(command))
            if name in ("Edit", "Write", "NotebookEdit"):
                path = str(inp.get("file_path") or "").replace("\\", "/")
                if "/data/" in path:
                    edits += 1
                    hand_edited.add(path.split("/data/", 1)[1])
    return tools, commits, loop, edits + len(tool_written - hand_edited)


# 루프 회차에 쓰면 안 되는 「끝날 때 보고」 표지 — 사용자 층 [발화 생략]의 ★ 줄과 [발화 생략]의 남은 일.
#   열린 날 2026-09-19 — 새어나간 것: 재예약 프롬프트가 사용자 발화 모양으로 와서 매 회차 끝에 ★ 세 줄·남은 일·
#   긴 표 보고를 붙였다. 사용자 [발화 생략].
#   못 보는 것: 표지 없이 길게 쓴 보고(길이 자는 check_narration 몫).
ROUND_REPORT_MARKS = ("★ 이번에 좋았던", "★ 이렇게 쓰면", "**남은 일")


def last_turn_text(entries):
    """마지막 사용자 발화 뒤 어시스턴트가 쓴 글(도구 호출 제외)을 이어 붙인다. 순수 함수."""
    out = []
    for entry in reversed(entries):
        if _is_user_prompt(entry):
            break
        if isinstance(entry, dict) and entry.get("type") == "assistant":
            content = (entry.get("message") or {}).get("content")
            if isinstance(content, list):
                out.extend(c.get("text", "") for c in content
                           if isinstance(c, dict) and c.get("type") == "text")
            elif isinstance(content, str):
                out.append(content)
    return "\n".join(reversed(out))


def round_report_marks(entries):
    """재예약한 턴(= 아직 루프 중)에 끝날 때 보고 표지가 있으면 그 표지들. 순수 함수."""
    if not wakeup_in_last_turn(entries):
        return []
    text = last_turn_text(entries)
    return [m for m in ROUND_REPORT_MARKS if m in text]


ROUND_REPORT = (
    "[루프 회차 보고] 재예약한 턴(루프가 계속된다)인데 끝날 때 보고 표지가 있다: %s.\n"
    "  사용자 2026-09-19 [발화 생략].\n"
    "  → 회차 끝은 한 줄 상태뿐이다. ★ 줄·남은 일·표 보고는 `wakeup_guard.py off` 로 루프를 끝내는 턴에만 쓴다.")


def load_lines(path):
    """빈 줄을 뺀 줄 목록. 파일이 없으면 빈 목록이다."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return [l.strip() for l in fh if l.strip()]
    except OSError:
        return []


def load_transcript(path):
    entries = []
    for line in load_lines(path):
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
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
    if not entries:
        return 0, ""
    if not wakeup_in_last_turn(entries):
        return 2, NAG
    marks = round_report_marks(entries)
    if marks:
        return 2, ROUND_REPORT % " · ".join(marks)
    tools, commits, loop, edits = round_work(entries)
    if loop:
        record_round(tools, commits, now, edits)
    if loop and commits < MIN_COMMITS:
        return 2, SHORT_ROUND % (tools, MIN_COMMITS)
    if loop and edits < MIN_EDITS:
        return 2, THIN_ROUND % (edits, MIN_EDITS)
    return 0, ""


def record_round(tools, commits, now, edits=0):
    """회차 하나를 기록한다. 기록에 실패해도 훅을 멈추지 않는다 — 재는 자가 막는 자를
    무너뜨리면 안 된다."""
    try:
        os.makedirs(os.path.dirname(ROUNDS), exist_ok=True)
        lines = []
        if os.path.exists(ROUNDS):
            with open(ROUNDS, encoding="utf-8") as fh:
                lines = fh.read().splitlines()[-(ROUNDS_KEEP - 1):]
        lines.append(json.dumps({"t": int(now), "tools": tools,
                                 "commits": commits, "edits": edits}))
        with open(ROUNDS, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except (OSError, ValueError):     # ValueError — 경로에 NUL 이 섞이는 꼴
        pass


# ── CLI ──────────────────────────────────────────────────────────────────────

OFF_REASONS = ("user", "blocked", "done")   # 사용자 요청 · 전부 막힘 · 큐 끝 — 멈춤 자리 셋(사용자 층 [발화 생략])


def off_reason_issue(reason):
    """`off` 사유 판정. 통과면 None, 아니면 거부 문구. 순수 함수 — 테스트가 직접 부른다.

    열린 날 2026-09-18: 루프 중 문맥 60만을 이유로 스스로 끄고 멈췄다(사용자 *[발화 생략]*). 하네스가 자동 압축하므로 문맥 크기는 멈춤 사유가 아니다.
    못 보는 것: 사유를 거짓으로 고르는 것 — 고른 사유는 출력에 남아 사후 대조만 된다.
    """
    if reason in OFF_REASONS:
        return None
    return ("off 사유는 %s 중 하나다(사용자 요청 · 전부 막힘 · 큐 끝). 문맥 크기는 사유가 아니다 — "
            "루프 중엔 사용자가 없고 하네스가 자동 압축한다. 다음 항목으로 이어 가라." % "·".join(OFF_REASONS))


def _fmt(epoch):
    return time.strftime("%m-%d %H:%M", time.localtime(epoch))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=["on", "off", "status", "tick", "measure"])
    ap.add_argument("--hours", type=float, default=DEFAULT_HOURS,
                    help="루프 모드 자동 만료 (기본 %d시간)" % DEFAULT_HOURS)
    ap.add_argument("--transcript", help="measure 가 읽을 세션 jsonl")
    ap.add_argument("--reason", help="off 사유: " + " · ".join(OFF_REASONS) + " (필수)")
    args = ap.parse_args()

    if args.action == "measure" and not args.transcript:
        # 기본은 훅이 쌓아 둔 기록을 읽는다 — 전사본은 셸에서 못 연다(규칙 5).
        rows = [json.loads(l) for l in load_lines(ROUNDS)]
        print("기록된 /loop 회차 %d개  (%s)" % (len(rows), ROUNDS))
        if rows:
            tools = sorted(r.get("tools", 0) for r in rows)
            print("  회차당 도구 호출 — 최소 %d · 중앙값 %d · 최대 %d"
                  % (tools[0], tools[len(tools) // 2], tools[-1]))
            print("  커밋 0회로 끝난 회차 %d개 / %d개"
                  % (sum(1 for r in rows if not r.get("commits")), len(rows)))
        else:
            print("  아직 없다 — 훅이 회차를 한 번 넘겨야 채워진다")
        return 0

    if args.action == "measure":
        entries = load_transcript(args.transcript)
        rounds, cur, prompt = [], None, None
        for entry in entries:
            if _is_user_prompt(entry):
                if cur is not None:
                    rounds.append((prompt, cur))
                prompt, cur = is_loop_round(entry), [0, 0]
                continue
            if cur is None:
                continue
            for name, inp in zip(_tool_names(entry), _tool_inputs(entry)):
                cur[0] += 1
                if name == "Bash" and "commit.py" in str(inp.get("command") or ""):
                    cur[1] += 1
        if cur is not None:
            rounds.append((prompt, cur))
        loops = [c for is_loop, c in rounds if is_loop]
        print("턴 %d개 · 그중 /loop 회차 %d개" % (len(rounds), len(loops)))
        if loops:
            tools = sorted(c[0] for c in loops)
            print("  회차당 도구 호출 — 최소 %d · 중앙값 %d · 최대 %d"
                  % (tools[0], tools[len(tools) // 2], tools[-1]))
            print("  커밋 0회로 끝난 회차 %d개 / %d개"
                  % (sum(1 for c in loops if c[1] == 0), len(loops)))
        return 0

    if args.action == "on":
        expires = time.time() + args.hours * 3600
        write_flag({"expiresAt": expires})
        print("루프 감시 ON — 턴이 끝날 때마다 그 턴에 ScheduleWakeup 이 있었는지 본다.")
        print("  없으면 멈춤을 막고 다시 예약하라고 알린다 (루프가 조용히 서지 않는다)")
        print("  ★ 이 도구는 PC 를 끄지 않는다 — 종료는 2026-08-26 에 은퇴했다")
        print("  깃발 만료: " + _fmt(expires) + " (이후로는 훅이 아무 말도 안 한다)")
        print("  끄기: python tools/wakeup_guard.py off --reason <user|blocked|done>"
              " (문맥 크기는 사유가 아니다)")
        return 0

    if args.action == "off":
        issue = off_reason_issue(args.reason)
        if issue:
            sys.exit(issue)
        clear_flag()
        print("루프 감시 OFF (사유 %s) — 훅이 이제 아무것도 보지 않는다." % args.reason)
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
