#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PreToolUse(Bash) — **되돌릴 수 없는 상태에서 대량 적용을 돌리지 않는다** (나루에서 받음 2026-08-16).

    settings.json 의 PreToolUse(Bash) 훅으로 건다.
    자기 점검:  python .claude/hooks/bulk_apply_guard.py --selftest

## 왜 열렸나 (`/insights` 154세션, 나루 원장 2026-08-16)

기호 치환기가 부피 `V` 와 **체적유량 `V̇`** 를 속도 글리프로 바꿨고 **SVG `path` 의 `V`
명령**까지 물었다. 다른 세션에서는 자료가 통째로 비는 사고가 나 복구가 필요했다.
둘 다 **여러 라운드짜리 복구**가 됐다.

★ 이 리포가 그 부류의 본거지다 — `fix_*` 계열 열둘과 `set_change_notes`·`recolor_figures`·
`reorder_cards`·`clear_change_notes`·`replace_doc_section` 이 전부 `--apply` 관례를 쓴다.

## ★ 막는 조건은 하나 — 「되돌리기가 한 명령인가」

바깥 제안은 [사용자 발화 인용 생략] 였는데 **그 5는 근거 없는 수**다(실행 규율 16).
그리고 훅은 **명령이 몇 파일을 건드릴지 미리 모른다** — 세려면 돌려 봐야 하고, 돌려 보면 늦다.

→ 그래서 **파일 수를 안 센다.** 대신 **미커밋 변경이 있는 채로 대량 적용을 돌리는 것**만
막는다. 트리가 깨끗하면 어떤 스윕이 어긋나도 **되돌리기가 한 명령**이고, 더러우면
**남의 변경과 섞여 되돌릴 수 없다.** 판정선이 관측 가능하고 근거가 하나다.

## 무엇을 「대량 적용」으로 보나

이 계통의 도구가 **스스로 선언하는 관례**를 쓴다 — `--show`(기본)로 세어 보고 `--apply`
로 쓴다. 그래서 **`--apply` 가 붙은 실행**과 자리에서 고쳐 쓰는 `sed -i` · `perl -pi` 를 본다.
이름 어림(`fix_*`)은 **안 쓴다** — 나루가 같은 날 두 번 오막음한 그 방식이다.

## 못 보는 것 (정직하게 남긴다)

- **제외 규칙의 증명**(낱말 경계 · `path` 명령 · `V̇` 같은 점 찍힌 변종)은 기계가 못 본다.
  그건 사람이 `--show` 출력을 보고 판정한다. 이 자가 보증하는 것은 **되돌릴 수 있나** 하나다.
- 깃발 없이 쓰는 스크립트는 안 걸린다. **가드는 모를 때 통과시킨다.**
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

RUN = ("python", "python3", "py", "pwsh", "powershell", "node", "bash", "sh")
APPLY = re.compile(r"(?:^|\s)--apply(?:[=\s]|$)")
INPLACE = (("sed", "-i"), ("perl", "-pi"), ("perl", "-i"))


def _decide(decision, reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}, sys.stdout)
    sys.exit(0)


HEREDOC = re.compile(r"<<-?\s*['\"]?\w+")


def segments(command):
    """명령 조각들. **힙독 본문은 잘라낸다 — 그건 명령이 아니라 «자료» 다.**

    ★★ **이 자가 나루에서 첫 커밋에 자기를 막았다** (2026-08-16). 변경일지에 적을 글을
      `cat >> … <<'EOF'` 로 넣는 명령이었는데, 그 **본문 안의 `sed -i` 라는 글자**를
      명령으로 읽었다. 마크다운 표의 `|` 가 조각을 갈라 놓은 것도 겹쳤다.
      `audit_session_cost.gate_signature` 가 **같은 이유로 이미 힙독을 자른다**
      ([사용자 발화 인용 생략]) — 그 처방을 여기 안 걸었을 뿐이다.
    ★ 부류: **막는 자를 지을 때는 「명령」과 「자료」를 먼저 가른다** — 힙독 본문 ·
      따옴표 안 · 커밋 메시지는 자료다.
    """
    low = command.strip()
    cut = HEREDOC.search(low)
    if cut:
        low = low[:cut.start()]
    for sep in ("&&", ";", "|", "\n"):
        low = low.replace(sep, "\x00")
    return [s.strip() for s in low.split("\x00") if s.strip()]


def bulk_apply(command):
    """대량 적용으로 볼 조각. 아니면 `None`."""
    for seg in segments(command):
        toks = seg.split()
        if not toks:
            continue
        head = os.path.basename(toks[0].strip("(\"'")).lower()
        if head == "git":                 # `git apply` 는 git 이 되돌린다 — 대상이 아니다
            continue
        for name, flag in INPLACE:
            if head.split(".")[0] == name and flag in toks:
                return "%s %s" % (name, flag)
        if not (head.split(".")[0] in RUN
                or head.endswith((".py", ".ps1", ".sh", ".js"))):
            continue                      # 읽는 명령·훑기는 대상이 아니다
        if APPLY.search(seg):
            for tok in toks:
                if tok.endswith((".py", ".ps1", ".sh", ".js")):
                    return os.path.basename(tok)
            return head
    return None


def measurable_root(root):
    """미커밋 변경을 **잴 수 있는** 자리. 못 찾으면 `None`.

    ★★ **컨테이너 루트는 워크트리가 아니다** (전공정리 2026-08-16 — 이식하며 넓혔다).
      이 리포는 bare + 링크드 워크트리 13벌의 부모에서 세션이 서고, 거기서 `git status` 는
      [사용자 발화 인용 생략] 로 죽는다. 나루 원본을 그대로
      쓰면 그 자리에서 **`None` → 안 막음**이 되는데, **컨테이너 루트 세션이 고치는 것은
      `main/` 이고 그건 워크트리다.** 즉 「못 잰다」가 아니라 **「엉뚱한 곳을 쟀다」** 다.
      같은 날 `gate_rerun_guard` 가 밟은 부류(*자리를 짐작하지 말고 찾는다*)의 되풀이라,
      **이 훅이 사는 워크트리로 물러난다.**
    ★ 그래도 못 찾으면 `None` 을 돌려 **안 막는다** — 가드는 모를 때 통과시킨다.
    """
    for cand in (root, ROOT):
        if not cand:
            continue
        try:
            p = subprocess.run(["git", "-C", cand, "rev-parse", "--is-inside-work-tree"],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if p.returncode == 0 and (p.stdout or "").strip() == "true":
            return cand
    return None


def dirty_files(root):
    """미커밋 변경 목록. 못 읽으면 `None`(막지 않는다)."""
    where = measurable_root(root)
    if not where:
        return None
    try:
        p = subprocess.run(["git", "-C", where, "status", "--porcelain"],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return [ln for ln in (p.stdout or "").splitlines() if ln.strip()]


REASON = (
    "**`%s` — 미커밋 변경이 %d개 있는 채로 대량 적용을 돌리려 한다.**\n"
    "  스윕이 어긋나면 **남의 변경과 섞여 되돌릴 수 없다.** 트리가 깨끗하면\n"
    "  되돌리기가 한 명령이다.\n"
    "  ★ 나루 원장 2026-08-16: 기호 치환기가 부피 `V`·체적유량 `V̇`·SVG `path` 의 `V`\n"
    "  명령까지 물어 여러 라운드짜리 복구가 됐다.\n"
    "  → **먼저 커밋하고 돌린다**(`python tools/commit.py \"<왜>\" <경로…>`). 그리고\n"
    "  `--apply` 전에 `--show`(또는 `--dry-run`)로 **무엇이 걸리고 무엇이 제외됐는지**\n"
    "  한 번 본다 — 제외 규칙은 기계가 못 본다."
)


def verdict(command, root, dirty=None):
    """`(대상, 막나)`. **판정은 전부 여기 둔다** — `main()` 에 쓰면 자가 못 본다."""
    what = bulk_apply(command)
    if not what:
        return None, False
    files = dirty_files(root) if dirty is None else dirty
    if files is None:
        return what, False                # 트리를 못 읽으면 막지 않는다
    return what, len(files) > 0


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return
    ti = payload.get("tool_input") or {}
    command = str(ti.get("command") or ti.get("script") or "")
    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ROOT
    try:
        what, blocked = verdict(command, root)
    except Exception:
        return
    if blocked:
        _decide("deny", REASON % (what, len(dirty_files(root) or [])))


def selftest():
    ok = True
    DIRTY = [" M data/ch01.json"]
    cases = [
        ("python tools/fix_symbols.py --apply", DIRTY, "fix_symbols.py", True,
         "더러운 트리 + --apply 는 거부"),
        ("python tools/fix_symbols.py --apply", [], "fix_symbols.py", False,
         "깨끗하면 통과 — 되돌리기가 한 명령이다"),
        ("python tools/fix_symbols.py --show", DIRTY, None, False,
         "--show 는 쓰지 않는다"),
        ("sed -i 's/V/v/g' data/*.json", DIRTY, "sed -i", True,
         "자리에서 고쳐 쓰는 것도 대량 적용이다"),
        ("git apply patch.diff", DIRTY, None, False,
         "git 은 스스로 되돌린다 — 대상이 아니다"),
        ("grep -n -- --apply tools/fix_symbols.py", DIRTY, None, False,
         "훑기는 대상이 아니다"),
        ("cat tools/fix_symbols.py", DIRTY, None, False, "읽는 것은 대상이 아니다"),
        ("python tools/close_report.py", DIRTY, None, False, "게이트는 대상이 아니다"),
        # ★ 이 자가 나루에서 첫 커밋에 자기를 막은 실제 명령 꼴이다 — 잠근다
        ("cat >> 변경일지.md <<'EOF'\n| 표 | `sed -i`·`--apply` 를 본다 |\nEOF",
         DIRTY, None, False, "힙독 본문은 명령이 아니라 자료다"),
        # ★ 이 리포의 실제 도구 꼴 — 이름 어림이 아니라 깃발로 잡는지 잠근다
        ("python tools/clear_change_notes.py --keep=배치 --apply", DIRTY,
         "clear_change_notes.py", True, "이 리포의 --apply 관례를 실제로 잡는다"),
    ]
    for cmd, dirty, want_what, want_block, why in cases:
        what, blocked = verdict(cmd, ROOT, dirty=dirty)
        bad = (what != want_what) or (blocked != want_block)
        ok = ok and not bad
        print("%s %-38s 대상=%-16s 막음=%-5s  %s"
              % ("✘" if bad else "✔", cmd[:38], what, blocked, why))

    # ★★ **컨테이너 루트(워크트리가 아닌 자리)에서도 잰다** — 전공정리에서 넓힌 자리.
    #   나루 원본은 여기서 `None` 을 받아 «안 막음» 이 됐다. `main/` 으로 물러나 실제로 잰다.
    outside = os.path.dirname(ROOT)            # 워크트리들의 부모(컨테이너 루트)
    where = measurable_root(outside)
    bad = where is None
    ok = ok and not bad
    print("%s %-38s 대상=%-16s 막음=%-5s  %s"
          % ("✘" if bad else "✔", "(컨테이너 루트에서 잴 자리를 찾나)",
             os.path.basename(where or "없다"), "-", "워크트리로 물러난다"))

    print("\n%s" % ("OK   0 problem(s)." if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    # ★ 사람이 읽는 출력만 인코딩을 탄다 — 훅 경로는 `json.dump`(ensure_ascii)라 멀쩡하다.
    #   `gate_rerun_guard` 가 이 리포에서 그 이유로 죽어 **잠금장치가 한 번도 안 돌았다**.
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    main()
