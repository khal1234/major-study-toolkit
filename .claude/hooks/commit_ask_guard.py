#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stop — 커밋/푸시를 **빈손으로 물어 놓고 턴을 끝내는 것**을, 예외 조건이 하나도
없을 때만 막아 세우고 그냥 하라고 되돌린다 (신설 2026-08-30).

    settings.json 의 Stop 훅으로 건다:
        python .claude/hooks/commit_ask_guard.py

## 왜 이제 짓나 — 이 행은 승격이다

`기록/feedback-ledger.md` 2026-08-25 항목이 **이미 이 자리를 예견했다**:
*[발화 생략]*

사용자가 2026-08-30 에 *[발화 생략]* 라고
했다 — 승격 문턱을 넘었다. `규칙/커밋-푸시-규약.md` §1 은 이미 *[발화 생략]* 라고 판정을 끝냈으므로, **이건 새 판정이 아니라 이미 내려진 판정을
기계로 옮기는 것**이다.

## ★ 08-25 의 우려("정당한 물음까지 막는다")를 어떻게 풀었나

그때는 「빈손으로 물었나」만 봐서 §3 이 살려 둔 예외(공개 리포·협업·되돌릴 수 없는
조작·CI 부착)까지 같이 막을 위험이 있었다. 이 자는 **그 넷을 직접 잰다** —
`gh repo view --json isPrivate`(비공개인가) · `git log` 저자 수(1명인가) ·
`.github/workflows` 존재(CI 없나). **넷 다 「예외 없음」으로 나올 때만** 막는다.
셋 중 하나라도 확인이 안 되거나(네트워크 없음 등) 예외 신호가 있으면 **막지 않는다**
— 판단이 안 서면 08-25 의 실사고(재지도 않고 물었다)와 반대쪽으로, **안전하게 통과**시킨다.

## ★ 무한 루프를 막는 안전판

`narration_realtime_experiment.py`(폐기)의 결함 — 누적 카운트가 못 줄어 영구히
막히는 것 — 과 같은 부류가 여기서도 날 수 있다(모델이 귀띔을 무시하고 같은 질문을
반복하면). `MAX_BLOCKS_PER_SESSION` 로 세션당 상한을 둔다 — 상한을 넘으면 그 뒤론
조용히 통과시킨다(사람이 직접 보게 된다, 이전과 같은 상태로 돌아갈 뿐 더 나빠지지 않는다).

## 판정선

마지막으로 **완결된 턴**의 마지막 assistant 글이 물음(`?`)으로 끝나고, `**제안:**`
표지가 없고, 그 줄에 커밋/푸시를 가리키는 낱말이 있으면 — 그리고 `git status
--porcelain` 이 비어 있지 않으면(커밋할 것이 실제로 있으면) — 위 네 조건을 잰다.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# ★ 2026-09-07 — 자리를 하나로 박지 않는다(같은 부류: 규칙 4c). XSanity 는
#   `_modding/scripts` 라 «도구» 만 보면 import 가 실패하고, 아래 except 가
#   전부 None 으로 두어 **자기검정이 AttributeError 로 죽는다.**
# 훅이 `<뿌리>/훅`(공용 폴더) 일 수도 `<뿌리>/.claude/hooks`(XSanity) 일 수도 있어
# **위로 훑는다.** 한 자리에 박으면 한쪽에서 import 가 조용히 실패하고,
# 아래 except 가 전부 None 으로 두어 자기검정이 AttributeError 로 죽는다.
for _here in list(Path(__file__).resolve().parents)[1:4]:
    _hit = next((_here / n for n in ("도구", "tools", "_modding/scripts")
                 if (_here / n).is_dir()), None)
    if _hit:
        sys.path.insert(0, str(_hit))
        break

try:
    from audit_session_conduct import ASK_END_RE, PROPOSAL_RE
    from check_narration import records, turn_window
except ImportError:
    ASK_END_RE = PROPOSAL_RE = records = turn_window = None

# 고른 값(2026-08-30 원본): 1 이면 귀띔 한 번 무시와 오판을 못 가르고, 더 크면 같은 물음 되풀이가 길어진다. 잰 값 아님.
MAX_BLOCKS_PER_SESSION = 2
COMMIT_WORD_RE = re.compile(r"커밋|푸시|push|commit", re.IGNORECASE)
STATE_DIR = Path(os.environ.get("TEMP") or "/tmp") / "claude-commit-ask-guard"


def _run(args, cwd, timeout=8):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            timeout=timeout, encoding="utf-8", errors="replace")
        return r
    except Exception:
        return None


def has_uncommitted_changes(cwd):
    r = _run(["git", "status", "--porcelain"], cwd)
    if r is None or r.returncode != 0:
        return False  # 모르면 없다고 본다 — 막을 근거가 안 된다
    return bool(r.stdout.strip())


def is_private_or_unknown(cwd):
    """비공개면 True, **모르면(네트워크 없음 등) None**을 돌려준다 — 안다/모른다를 가른다."""
    r = _run(["gh", "repo", "view", "--json", "isPrivate"], cwd, timeout=10)
    if r is None or r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return bool(json.loads(r.stdout).get("isPrivate"))
    except ValueError:
        return None


def single_author(cwd):
    r = _run(["git", "log", "--format=%ae"], cwd)
    if r is None or r.returncode != 0:
        return None
    emails = {ln.strip() for ln in r.stdout.splitlines() if ln.strip()}
    if not emails:
        return None
    return len(emails) == 1


def no_ci(cwd):
    return not (Path(cwd) / ".github" / "workflows").is_dir()


def flagged_last_line(last_chunk):
    """마지막 assistant 글 한 덩어리를 받아, **커밋/푸시를 묻는 줄**이 있으면 그 줄을,
    아니면 `None` 을 돌려준다. 순수 함수 — git/gh 를 안 건드려서 셀프테스트가 부른다.

    판정선: 한 줄 안에 커밋/푸시 낱말과 물음표가 같이 있다. `★` 꼬리 줄·인용(`>`)은 안 본다.
    ★ 2026-09-25 재발 — 예전엔 **마지막 줄**만 봐서, 층 0 이 끝에 붙이는 `★` 줄 뒤로 물음이
    밀리면 통과했다(「…커밋과 주간 점검 한 번이야. … 할까?」 뒤에 ★ 세 줄). `**제안:**`
    면제도 뺐다 — 층 0 「「제안한다」도 묻는 것이다」와 어긋났다. 정당한 물음은 아래
    `exception_free`(공개·협업·CI)가 살린다. 못 보는 것: 물음표 없이 묻는 말(「해도 되면 말해줘」).
    """
    if not last_chunk:
        return None
    for ln in last_chunk.splitlines():
        s = ln.strip()
        if not s or s.startswith(("★", ">")):
            continue
        if re.search(r"[?？]", s) and COMMIT_WORD_RE.search(s):
            return s
    return None


def exception_free(cwd):
    """§3 의 넷 중 확인 가능한 셋이 **전부 「예외 없음」**이면 True. 하나라도 모르면 False."""
    priv = is_private_or_unknown(cwd)
    if priv is not True:          # 비공개가 아니거나 모르면 예외 있을 수 있음
        return False
    single = single_author(cwd)
    if single is not True:
        return False
    return no_ci(cwd)


def selftest() -> int:
    """git/gh 없이 `flagged_last_line` 만 잰다 — 나머지 셋(비공개·저자·CI)은
    2026-08-30 이 저장소에 대고 손으로 실측했다(위 docstring)."""
    bad = 0

    def chk(desc, cond, got=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %-46s %s" % ("OK  " if cond else "**틀림**", desc, got))

    chk("양성 — 빈손 커밋 물음을 잡는다",
        flagged_last_line("다 됐습니다.\n\n커밋할까요?") == "커밋할까요?")
    chk("음성 — `**제안:**` 있으면 안 잡는다",
        flagged_last_line("**제안:** 바로 커밋합니다.\n진행할까요?") is None)
    chk("양성 — 물음 뒤에 ★ 꼬리가 붙어도 잡는다(2026-09-25 재발)",
        flagged_last_line("**남은 일:** 커밋과 점검 한 번이야. 할까?\n\n★ 좋았던 지시 — x") is not None)
    chk("양성 — `**제안:**` 이 있어도 커밋을 물으면 잡는다",
        flagged_last_line("**제안:** 바로 커밋.\n커밋 진행할까요?") is not None)
    chk("음성 — ★ 꼬리 줄 안의 커밋 물음은 안 본다",
        flagged_last_line("끝났어.\n★ 이렇게 쓰면 더 좋다 — 「커밋했어?」") is None)
    chk("음성 — 커밋/푸시 낱말이 없으면 안 잡는다",
        flagged_last_line("이대로 진행할까요?") is None)
    chk("음성 — 물음으로 안 끝나면 안 잡는다",
        flagged_last_line("커밋했습니다. 다음으로 넘어갑니다.") is None)
    chk("음성 — 빈 입력",
        flagged_last_line("") is None and flagged_last_line(None) is None)

    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main() -> int:
    try:
        # 2026-09-24 — 로케일(cp949)로 읽으면 한글 cwd 가 깨져 git 이 실패하고 조용히 통과한다.
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0

    sid = str(payload.get("session_id") or "unknown")
    tpath = payload.get("transcript_path")
    cwd = payload.get("cwd") or os.getcwd()
    if not tpath:
        return 0

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        block_count_file = STATE_DIR / f"{sid}.blocks"
        n_blocked = int(block_count_file.read_text(encoding="utf-8")) if block_count_file.exists() else 0
    except OSError:
        n_blocked = 0

    if n_blocked >= MAX_BLOCKS_PER_SESSION:
        return 0  # 안전판 — 더는 막지 않는다

    if records is None or turn_window is None:
        return 0

    try:
        recs = list(records(Path(tpath)))
        s, e = turn_window(recs, completed=True)
        turn = recs[s:e]
    except Exception:
        return 0

    last_chunk = None
    for rec in reversed(turn):
        msg = rec.get("message") or {}
        if msg.get("role") != "assistant":
            continue
        for block in msg.get("content") or []:
            if block.get("type") == "text" and block.get("text", "").strip():
                last_chunk = block["text"]
        if last_chunk:
            break

    last_line = flagged_last_line(last_chunk)
    if not last_line:
        return 0

    if not has_uncommitted_changes(cwd):
        return 0
    if not exception_free(cwd):
        return 0  # 예외 조건이 있거나 확인이 안 됨 — 정당한 물음일 수 있다, 막지 않는다

    try:
        block_count_file.write_text(str(n_blocked + 1), encoding="utf-8")
    except OSError:
        pass

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"방금 \"{last_line}\" 로 턴을 끝내려 했습니다 — 이 저장소는 `규칙/커밋-푸시-규약.md` "
            "기본값 조건(비공개 · 단독 저자 · CI 없음)을 만족하므로 **묻지 말고 커밋(원격이 "
            "비공개면 push까지)하고, 한 줄로 사후보고하십시오.** "
            "「커밋 <hash> · main → origin(비공개)」 형식입니다."
        ),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(selftest())
    sys.exit(main())
