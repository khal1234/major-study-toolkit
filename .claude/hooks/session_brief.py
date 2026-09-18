#!/usr/bin/env python
"""세션이 열릴 때 «지금 어느 갈래에서 무엇이 열려 있나» 를 사실로 찍는다 (2026-08-14 신설).

**왜 이 훅인가.** 같은 사고가 두 번 났다 — 폴더 이름으로 목표를 짐작해 **엉뚱한 프로젝트**의
할 일 목록을 뽑았고, 사용자가 아직 편입 시험을 준비하는 줄 알고 답했다. 원인은 성실성이 아니라
**세션 첫 화면에 사실이 하나도 없다**는 것이다. 규칙으로 *[발화 생략]* 고
적어 두면 읽은 것과 안 읽은 것이 구별되지 않는다(규칙 11) — 그래서 **사실을 눈앞에 놓는다.**

**여기서 판정은 하나도 하지 않는다.** 무엇을 할지는 인박스·워크오더가 정하고, 이 훅은
*그 파일이 어디 있는지*만 말한다. 판정을 여기 넣으면 두 벌이 되어 갈린다.

**출력은 짧아야 한다.** 매 세션 문맥에 실리므로 길면 그 자체가 낭비다(실행 규율 12) —
그래서 갈래·과목·열린 파일 몇 줄로 끝낸다. 없으면 아무것도 안 찍는다.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
MAX_PER_KIND = 3          # 최근 것 몇 개까지 보여줄까 — 목록이 길면 아무도 안 읽는다


def branch_of(root):
    """현재 브랜치. 못 읽으면 빈 문자열 — 훅은 어떤 경우에도 세션을 막지 않는다."""
    try:
        r = subprocess.run(["git", "-C", str(root), "branch", "--show-current"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.stdout.strip() if r.returncode == 0 else ""
    except OSError:
        return ""


def is_worktree(root):
    """이 자리가 **과목 워크트리**인가(아니면 그것들을 담은 컨테이너인가).

    ★★ **`branch --show-current` 만으로는 못 가른다 (실측 2026-08-15).** 컨테이너 폴더의
      `.git` 은 **bare 저장소**를 가리키고, bare 에서 그 명령은 실패하지 않는다 — HEAD 가
      가리키는 이름(`main`)을 **성공적으로** 돌려준다. 그래서 이 훅은 컨테이너 루트 세션에
      **`[세션] main` 이라고 틀린 사실을 찍고 있었다.** 이 훅의 존재 이유가 «첫 화면에 사실을
      놓는 것» 인데 거짓을 놓았으니, 빈 줄을 찍는 것보다 나쁘다.
    ★ 오늘 같은 전제(**「세션은 워크트리에 선다」**)에서 넷째다 — 과목 경계 · 도구 경로 ·
      `git -C` · 여기. 새 판정을 쓸 때 그 전제를 먼저 의심할 것.
    """
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.stdout.strip() == "true"
    except OSError:
        return True          # 못 읽으면 옛 동작(과목 워크트리)으로 — 훅은 세션을 막지 않는다


def worktrees_under(root):
    """컨테이너 바로 아래에 있는 갈래 폴더 이름. 목록을 코드에 적지 않는다."""
    try:
        return sorted(p.name for p in root.iterdir()
                      if p.is_dir() and (p / ".git").exists())
    except OSError:
        return []


def subjects_in(root):
    """`data/` 아래 실재하는 과목 폴더 이름. **목록을 코드에 적지 않는다** — 적으면
    새 과목이 생긴 날 이 훅만 옛 세상을 말한다(공통에 과목을 박지 않는다는 규칙).

    ★ 점으로 시작하는 폴더는 과목이 아니다 (2026-09-07). `data/.textbook-fingerprint` 가
      과목으로 찍혀 매 세션 브리핑이 «과목 22개» 라고 말했다 — 사실만 낸다는 이 훅의 약속을
      스스로 어긴 자리다. 판정 정본은 `audit_content.subject_dirs()` 이고 거기엔 이미 있었다.
    """
    data = root / "data"
    if not data.is_dir():
        return []
    return sorted(p.name for p in data.iterdir()
                  if p.is_dir() and not p.name.startswith("."))


def open_files(root, patterns, limit=MAX_PER_KIND):
    """패턴에 걸리는 파일을 **최근 수정순**으로. 순수하지는 않지만 판정은 없다."""
    found = []
    for pattern in patterns:
        found.extend(p for p in root.glob(pattern) if p.is_file())
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.relative_to(root).as_posix() for p in found[:limit]]


def lines(root):
    """찍을 줄들. 순수 함수에 가깝게 떼어 둔다 — 테스트가 직접 부른다."""
    out = []
    if not is_worktree(root):
        # 컨테이너 루트 — **과목이 없다.** 여기서 할 것은 공통뿐이고, 과목 콘텐츠 커밋은
        # `guard_bash.container_root_violation` 이 실제로 막는다(말로만 적어 두지 않는다).
        trees = worktrees_under(root)
        out.append("[세션] **컨테이너 루트 — 과목이 없다.** 여기서는 공통만 다룬다"
                   "(tools/ · CLAUDE.md · site/template · site/fonts · .claude/ · docs/).")
        if trees:
            out.append("  갈래 " + str(len(trees)) + "개: " + ", ".join(trees))
        out.append("  ☞ 과목 작업은 그 폴더의 세션에서. 남의 과목은 `git show <갈래>:<경로>` 로 읽는다.")
        ledger = shared_ledger()
        if ledger:
            out.append("  삽질 전에 공용 원장부터 검색: " + ledger)
        return out

    branch, subjects = branch_of(root), subjects_in(root)
    head = "[세션] " + (branch or "(브랜치 미상)")
    if subjects:
        head += " · 과목 " + ", ".join(subjects)
    out.append(head)

    inbox = open_files(root, ["data/*/*review-inbox.md"])
    orders = open_files(root, ["data/*/*.workorder.md"], limit=2)
    if inbox:
        out.append("  인박스(최근): " + " · ".join(inbox))
    if orders:
        out.append("  워크오더(최근): " + " · ".join(orders))
    out.extend(handoff_lines(root))
    tail = "  ☞ 할 일은 **이 파일을 읽어서** 정한다(추정 금지)."
    ledger = shared_ledger()
    if ledger:
        tail += " 삽질 전에 공용 원장부터 검색: " + ledger
    out.append(tail)
    return out


HANDOFF = "docs/인계.md"


def handoff_lines(root):
    """`docs/인계.md` 맨 위 줄(도구 · 마지막 커밋)과 **그 커밋 이후 인계 줄 없는 커밋 수**.

    무엇을 재나: Claude↔GPT 를 한도가 찰 때마다 바꿔 쓰면, 상대가 한 일을 다음 세션이 모른다
    (XSanity 2026-09-17 «몰랐어» — GPT 가 만든 페이지를 Claude 가 없는 것으로 판정). 인계 줄은
    사람이 적는 요약이고, 빠뜨린 커밋은 git 이 센다 — 줄이 없어도 «인계 없는 변경 N개» 는 뜬다.
    문턱: 없음. 셈만 찍고 판정은 세션이 한다(이 훅의 약속). 못 보는 것: 미커밋 변경(`git status`
    는 세션이 본다) · 인계 줄의 내용이 맞는지 · 다른 브랜치의 커밋.
    한 줄로 낸다 — 브리핑 상한 5줄(`test_session_brief_states_facts_not_guesses`)을 두 줄이 넘겼다(2026-09-17).
    """
    path = root / HANDOFF
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rows = [ln for ln in text.splitlines()
            if ln.startswith("| 20") and ln.count("|") >= 6]
    if not rows:
        return []
    cells = [c.strip() for c in rows[0].strip("|").split("|")]
    date, tool, sha = cells[0], cells[1], cells[2].strip("`")
    line = ("  인계(최근): " + date + " " + tool + " · 마지막 커밋 " + sha
            + " · 다음 「" + cells[4][:60] + "」 — 전문은 " + HANDOFF)
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-list", "--count", sha + "..HEAD"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        n = int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else None
    except (OSError, ValueError):
        n = None
    if n:
        line += (" · ★ 그 뒤 인계 줄 없는 커밋 " + str(n) + "개 — `git log " + sha
                 + "..HEAD --format=%s` 로 먼저 읽는다(상대 도구가 한 일일 수 있다)")
    return [line]


def shared_ledger():
    """공용 **실사고 원장** 경로(없으면 빈 문자열).

    ★ 왜 첫 화면에 거는가: 규칙은 프로젝트마다 옮겨 갔는데 **«언제 어떻게 데였나» 는 안 옮겨져서**,
      한 프로젝트가 다른 프로젝트가 이미 판 구멍을 다시 팠다(2026-08-14). 규칙은 «하지 마라» 만
      말하고 원장은 **«이 자리에서 이렇게 데였다»** 를 말한다 — 삽질을 막는 것은 후자다.
    ★ 경로를 여기 다시 적지 않는다 — `shared_sync_check` 의 `SHARED` 를 그대로 쓴다(두 벌이면 갈린다).
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from shared_sync_check import SHARED                             # noqa: E402
    except Exception:                                      # noqa: BLE001 — 훅은 세션을 막지 않는다
        return ""
    path = Path(SHARED) / "기록" / "feedback-ledger.md"
    return str(path) if path.is_file() else ""


def main():
    for line in lines(ROOT):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
