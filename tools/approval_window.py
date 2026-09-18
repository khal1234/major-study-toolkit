# -*- coding: utf-8 -*-
"""**승인 창구** — 승인창이 뜰 편집을 사용자가 없는 동안 띄우지 않고, 쌓았다가 한 번에 묻는다.

부르는 법(훅 배선은 `.claude/settings.json`):
    PreToolUse(Edit|Write|MultiEdit|NotebookEdit)  python tools/approval_window.py hook
    UserPromptSubmit                                python tools/approval_window.py prompt
    Stop                                            python tools/approval_window.py stop
    사람·에이전트                                    python tools/approval_window.py list | done <번호…>

재는 것: `permissions.ask` 에 걸린 편집이 **창구가 열린 때**인가. 창구 = 마지막 사용자 발화(루프 회차·
  메타 제외) 뒤로 쓰기 동작(`WORK_TOOLS`)이 이 호출 말고 0개. 숫자 문턱이 없다 — 「사용자가 방금
  말했고 아직 일이 안 돌았다」만 본다. 닫힌 때 온 편집은 입력째 대기열에 쌓고 exit 2(승인창 안 뜸).
왜(2026-09-14 사용자): 무인 루프가 승인창 하나에 밤새 섰고, 루프가 아니어도 몰아서 도는 중에 뜨면
  같다 — *[발화 생략]*. 허락을 구하는 자리는 설계 때와
  사용자가 채팅을 보낸 그때뿐이다. 논리를 `.claude/hooks/` 가 아니라 여기 둔 까닭: auto 모드 분류기가
  훅 폴더 쓰기를 자기수정으로 막아, 사람 승인이 필요한 면을 배선 한 줄로 줄인다.
못 보는 것: Bash 로 같은 파일을 쓰는 경로(`guard_bash` 몫) · 대화록 형식이 바뀌면 발화를 못 찾아
  닫힘으로 본다(엄한 쪽) · 읽기 전용 Bash(`git status`)도 쓰기로 센다(엄한 쪽) · 사용자가 턴 도중
  보낸 메시지가 대화록에 발화로 안 남으면 창구를 못 연다.
"""
import json
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
HOOKS = ROOT / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))
sys.path.insert(0, str(TOOLS))

import guard_write as gw                       # noqa: E402 — glob·경로 해석을 한 곳에서
import wakeup_guard as wg                      # noqa: E402 — 대화록 발화 판정을 한 곳에서

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

QUEUE = HOOKS / ".approval_queue.jsonl"        # `/.claude/hooks/.*` 라 커밋 안 됨
SETTINGS = ROOT / ".claude" / "settings.json"
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
WORK_TOOLS = EDIT_TOOLS + ("Bash", "PowerShell")
REPORT_MARK = "승인 대기열"                    # 최종 보고에 이 낱말이 있어야 Stop 이 통과한다


# ── 판정 (순수 함수 — 테스트가 직접 부른다) ─────────────────────────────────

def ask_patterns(settings):
    """`permissions.ask` 중 편집 도구 규칙 → 정규식 목록."""
    out = []
    for rule in (settings.get("permissions") or {}).get("ask") or []:
        name, sep, rest = str(rule).partition("(")
        if name not in EDIT_TOOLS or not sep or not rest.endswith(")"):
            continue
        pat = rest[:-1].lstrip("/")
        while pat.startswith("**/"):
            pat = pat[3:]
        out.append(gw._glob_re(pat))
    return out


def _is_real_prompt(entry):
    if not wg._is_user_prompt(entry) or entry.get("isMeta"):
        return False
    return not (wg.is_loop_round(entry) or "<<autonomous-loop" in wg._prompt_text(entry))


def window_open(entries, tool_use_id=None):
    """마지막 사용자 발화가 진짜이고, 그 뒤로 쓰기 동작이 (이 호출 말고) 0개인가."""
    for entry in reversed(entries):
        if wg._is_user_prompt(entry):
            return _is_real_prompt(entry)
        if entry.get("type") != "assistant":
            continue
        for c in (entry.get("message") or {}).get("content") or []:
            if (isinstance(c, dict) and c.get("type") == "tool_use"
                    and c.get("name") in WORK_TOOLS and c.get("id") != tool_use_id):
                return False
    return False


def defer_reason(tool_name, tool_input, entries, patterns, repo=ROOT, tool_use_id=None):
    """미룰 사유, 통과면 None."""
    if tool_name not in EDIT_TOOLS or not patterns:
        return None
    fp = gw.target_path(tool_input or {})
    if fp is None:
        return None
    path = gw._resolve(fp)
    if not gw._under(path, repo):
        return None
    rel = Path(path).relative_to(repo).as_posix()
    if not any(p.match(rel) for p in patterns) or window_open(entries, tool_use_id):
        return None
    return (f"[승인 창구 닫힘] `{rel}` 는 승인창이 뜨는 편집인데 지금은 사용자가 막 말한 때가 아니다.\n"
            "  -> 입력째 대기열에 적었다. **다음 항목으로 계속하고**, 최종 보고에 「승인 대기열」 절로 한 번에\n"
            "     판정을 요구한다(`python tools/approval_window.py list`). 사용자가 채팅을 보내면 그 턴엔 물어도 된다.\n"
            "  -> 우회 금지: 같은 파일을 Bash·스크립트로 쓰지 않는다.")


def last_assistant_text(entries):
    """마지막 사용자 발화 뒤 어시스턴트 글 전부."""
    parts = []
    for entry in reversed(entries):
        if wg._is_user_prompt(entry):
            break
        if entry.get("type") == "assistant":
            for c in (entry.get("message") or {}).get("content") or []:
                if isinstance(c, dict) and c.get("type") == "text":
                    parts.append(c.get("text") or "")
    return "\n".join(parts)


def stop_reason(queue, session_id, entries, stop_hook_active=False):
    """이 세션이 쌓은 대기열이 있는데 최종 보고가 그것을 안 꺼냈으면 사유."""
    mine = [r for r in queue if r.get("session_id") == session_id]
    if stop_hook_active or not mine or REPORT_MARK in last_assistant_text(entries):
        return None
    return (f"[승인 대기열] 이 세션에서 미룬 편집 {len(mine)}건을 최종 보고가 안 꺼냈다.\n"
            f"  -> 보고 끝에 「{REPORT_MARK}」 절을 붙여 건마다 무엇을·왜를 적고 판정을 요구한다"
            " (`python tools/approval_window.py list`).")


# ── 대기열 ─────────────────────────────────────────────────────────────────

def load_queue(path=QUEUE):
    try:
        with open(path, encoding="utf-8") as fh:
            return [json.loads(ln) for ln in fh if ln.strip().startswith("{")]
    except (OSError, ValueError):
        return []


def save_queue(items, path=QUEUE):
    with open(path, "w", encoding="utf-8") as fh:
        for r in items:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _summary(rec):
    inp = rec.get("input") or {}
    fp = str(gw.target_path(inp) or "?")
    try:
        fp = Path(gw._resolve(fp)).relative_to(ROOT).as_posix()
    except ValueError:
        pass
    size = len(str(inp.get("new_string") or inp.get("content") or ""))
    return f"{rec.get('ts', '?')} · {rec.get('tool', '?')} · {fp} · 새 글자 {size}"


# ── 진입점 ─────────────────────────────────────────────────────────────────

def _payload():
    try:
        p = gw.gb.read_payload()
        return p if isinstance(p, dict) else {}
    except Exception:
        return {}


def main(argv):
    cmd = argv[0] if argv else "list"
    if cmd == "hook":
        p = _payload()
        try:
            settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        except Exception:
            return 0
        entries = wg.load_transcript(p.get("transcript_path") or "")
        reason = defer_reason(p.get("tool_name", ""), p.get("tool_input") or {}, entries,
                              ask_patterns(settings), ROOT, p.get("tool_use_id"))
        if not reason:
            return 0
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "session_id": p.get("session_id", ""),
               "tool": p.get("tool_name", ""), "input": p.get("tool_input") or {}}
        try:
            with open(QUEUE, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass
        sys.stderr.write(reason + "\n")
        return 2
    if cmd == "prompt":
        q = load_queue()
        if q:
            print(f"[{REPORT_MARK}] {len(q)}건 — 사용자가 방금 말했으니 이 턴(쓰기 전)에는 판정을 물을 수 있다."
                  " 목록 `python tools/approval_window.py list`.")
        return 0
    if cmd == "stop":
        p = _payload()
        reason = stop_reason(load_queue(), p.get("session_id", ""),
                             wg.load_transcript(p.get("transcript_path") or ""),
                             bool(p.get("stop_hook_active")))
        if reason:
            sys.stderr.write(reason + "\n")
            return 2
        return 0
    if cmd == "list":
        q = load_queue()
        if not q:
            print("[승인 대기열] 0건")
        for i, rec in enumerate(q, 1):
            print(f"{i}. {_summary(rec)}")
        return 0
    if cmd == "done":
        q = load_queue()
        drop = {int(x) for x in argv[1:] if x.isdigit()}
        save_queue([r for i, r in enumerate(q, 1) if i not in drop])
        print(f"[승인 대기열] {len(drop & set(range(1, len(q) + 1)))}건 지움 · 남은 {len(q) - len(drop & set(range(1, len(q) + 1)))}건")
        return 0
    print("쓰는 법 — hook | prompt | stop | list | done <번호…>", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
