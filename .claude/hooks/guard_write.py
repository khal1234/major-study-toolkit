# -*- coding: utf-8 -*-
"""PreToolUse 훅 — **쓰기 계열**(`Write`/`Edit`/`MultiEdit`/`NotebookEdit`)의 마지막 층.

    stdin  : Claude Code 가 주는 PreToolUse JSON
    exit 0 : 통과   /   exit 2 : 차단 (stderr 가 사유로 전달된다)

## 왜 열렸나 (2026-08-12)

`AGENTS.md` 규칙 9 는 **자기 입으로 구멍을 자백하고 있었다:**

> [사용자 발화 인용 생략]

즉 리포 밖 쓰기를 막는 것이 **에이전트의 성실성뿐**이었다. 그런데 규칙 9 가 실제로 깨지는
가장 흔한 경로는 `Bash` 가 아니라 **`Write`/`Edit` 툴 자체**다 — `guard_bash.py` 는 그 툴을
아예 보지 못한다(matcher 가 `Bash`). 방지장치를 설계할 때 *발동하는 사건을 내가 못 보고
지나갈 수 있나* 를 물어야 한다는 것이 이 리포의 판정 기준인데(「방지장치의 트리거」),
규칙 9 는 그 물음에 걸리는 자리였다.

**출처:** XSanity 프로젝트의 `guard_write.py` 를 공용 시스템 폴더에서 가져와 이 리포에 맞췄다.
그쪽에서 이미 [사용자 발화 인용 생략] 는 판정을 내려
두었다. 가져오면서 **판정 내용은 전부 이 리포의 규칙으로 갈아 끼웠다**(원본은 채보 백업·
생성물 손편집이 대상이었다).

## 무엇을 막나 — 넷 다 이 리포에 이미 있는 규칙이다

  ⑴ **규칙 9** — 쓰기는 허용된 자리에만. 리포 · 스크래치패드 · 공용 시스템 폴더 ·
     에이전트 메모리, 이 넷 밖은 차단한다.
  ⑵ **규칙 1** — 빌드 산출물(`site/<과목>/*.html`) 손편집 금지. 고칠 곳은
     `site/template/viewer.template.html` 과 `data/**` 다.
  ⑶ **과목 경계** — 다른 과목의 `data/`·`site/`. `guard_bash` 가 `git add`/`commit` 에서만
     막고 있었다 — **파일을 직접 고치는 경로는 열려 있었다.**
  ⑷ **챕터 경계** — 챕터 worktree 가 공통(`tools/`·`AGENTS.md`·`site/template/`)을 고치는 것.
     ⑶⑷ 의 판정은 `guard_bash` 의 순수 함수를 **그대로 import 해서 쓴다** — 두 벌로 두면
     갈라지고, 갈라진 경계는 꺼진 경계와 같다.

★ **메모리 디렉터리는 예외다.** 규칙 5 는 `~/.claude/**` 를 건드리지 말라고 하는데, 그 안의
  `projects/<프로젝트>/memory/` 는 **에이전트가 쓰라고 하네스가 준 자리**다. 규칙 5 의 뜻은
  [사용자 발화 인용 생략] 이므로 메모리만 열어 둔다.
  이걸 안 열면 이 훅이 **메모리 저장을 통째로 막는다**(도입 전에 실제로 확인한 자리다).

★ **판정은 전부 `deny_reason()` 안에 둔다.** `main()` 에 흩으면
  `tools/test_checks.py::test_guard_write_rules` 가 판정을 못 본다 — `guard_bash` 가 같은 이유로
  같은 형태를 하고 있다. 훅이 실제로 발화하는지와 무관하게 판정은 테스트로 지켜진다.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard_bash as gb                      # 과목·챕터 경계 판정을 재사용한다

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                        # 아주 오래된 파이썬 — 훅이 작업을 브릭하지 않게
        pass

REPO = Path(__file__).resolve().parents[2]   # .claude/hooks/guard_write.py → 리포 루트
# ★ 공용 시스템 폴더가 `Claude` → `naru` 로 옮겨졌다 (2026-08-15 실측: `Documents/Claude` 는
#   이제 없다). **둘 다 본다** — 다른 PC·다른 프로젝트 사본이 한꺼번에 바뀌지 않기 때문이다.
#   환경변수 `CLAUDE_SHARED_SYSTEM` 이 있으면 그것이 이긴다. 이 판정은 `shared_sync_check.SHARED`
#   와 **글자 그대로 같은 모양**이어야 한다 — 갈리면 훅마다 다른 폴더를 연다.
SHARED_SYSTEM = Path(os.environ.get("CLAUDE_SHARED_SYSTEM")
                     or next((p for p in (Path.home() / "Documents" / "naru",
                                          Path.home() / "Documents" / "Claude")
                              if p.is_dir()), Path.home() / "Documents" / "naru"))
SELFTEST = "THERMO_" + "HOOK_SELFTEST_DENY"  # 쪼개 둔다 — 이 파일 자신이 걸리지 않게

# 사용자가 명시적으로 연 리포 밖 쓰기 경로의 **선언 파일**.
# `.` 접두라 `.gitignore` 의 `/.claude/hooks/.*` 가 덮는다 — 즉 **이 워크트리에만 있고
# main 을 거쳐 다른 과목으로 퍼지지 않는다.** 그게 이 파일이 아니라 선언으로 둔 이유다.
EXTRA_ROOTS = Path(__file__).resolve().parent / ".write-roots.txt"


def _resolve(p, cwd=None):
    q = Path(p)
    if not q.is_absolute() and cwd:
        q = Path(cwd) / q
    try:
        return q.resolve(strict=False)
    except OSError:
        return q


def _under(path, root):
    try:
        Path(path).relative_to(root)
        return True
    except ValueError:
        return False


def _is_scratchpad(path):
    return "\\temp\\claude\\" in str(path).replace("/", "\\").lower()


def _is_agent_memory(path):
    """`~/.claude/projects/<프로젝트>/memory/**` — 하네스가 에이전트에게 준 자리."""
    s = str(path).replace("\\", "/").lower()
    return "/.claude/projects/" in s and "/memory/" in s


def _under_ci(path, root):
    """윈도 경로는 대소문자를 안 가린다 — `d:\\xsanity` 와 `D:\\XSanity` 는 같은 곳이다.

    `_under()` 는 `Path.relative_to` 라 글자 그대로 비교해서, 선언과 실제 경로의 표기가
    다르면 **열어 준 줄 알았는데 안 열린다.** 형제 폴더(`D:\\XSanity2`)는 걸리지 않아야 하므로
    구분자까지 붙여서 본다.
    """
    p = os.path.normcase(str(path))
    r = os.path.normcase(str(root)).rstrip("\\/")
    return p == r or p.startswith(r + os.sep)


def parse_write_roots(text):
    """선언 텍스트 → 경로 목록. **사유가 없는 줄은 안 친다.** 순수 함수.

    사유를 요구하는 이유는 `orphan-checks-allow.txt`·`check-erosion-allow.txt` 와 같다 —
    사유가 없으면 *잊은 것*과 *일부러 연 것*이 겉모습이 같아진다. 게다가 이 파일은
    **경계를 넓히는** 자리라, 왜 열렸는지 없이 남으면 다음 세션이 지울 수도 없다.
    """
    out = []
    for ln in text.splitlines():
        if ln.lstrip().startswith("#"):
            continue
        head, sep, why = ln.partition("#")
        head, why = head.strip(), why.strip()
        if head and sep and why:
            out.append(Path(head))
    return out


def extra_write_roots(decl=None):
    """선언 파일이 연 경로들. 없으면 빈 목록 — **기본값은 닫힘이다.**"""
    p = Path(decl) if decl else EXTRA_ROOTS
    try:
        if not p.is_file():
            return []
        return parse_write_roots(p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return []


def current_branch(repo=None):
    """워크트리의 현재 브랜치. 못 읽으면 빈 문자열 — 경계 판정을 건너뛴다."""
    try:
        out = subprocess.run(["git", "-C", str(repo or REPO), "branch", "--show-current"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=5)
        return (out.stdout or "").strip()
    except Exception:
        return ""


def declared_worktree(branch, parent=None):
    """선언한 갈래의 워크트리 경로. **폴더 이름을 짐작하지 않는다.**

    ★ 열린 날 2026-08-24 — 워크트리 폴더가 `<한글표시>-<갈래>`(«유체역학-fluids»)로 바뀐 뒤
      `REPO.parent / declared` 는 **없는 경로**를 가리켰다. 그러면 선언을 켠 세션의 쓰기가
      전부 «리포 밖» 으로 차단된다(실측: 과목을 선언하고 `data/유체역학/terms.json` 을 쓰려다
      규칙 9 로 막혔다 — 훅은 옛 이름 `…/fluids` 를 리포라고 찍고 있었다).
      같은 「짐작」이 `serve_site.vbs`·`install_startup.ps1`·`serve_status.py` 에도 있었고
      그날 함께 걷어냈는데 **훅 두 개가 빠져 있었다.** 규칙 정본은 `tools/worktree_names.py`.
    """
    base = Path(parent) if parent else REPO.parent
    try:
        sys.path.insert(0, str(REPO / "tools"))
        from worktree_names import find_worktree                          # noqa: E402
        got = find_worktree(str(base), branch)
        if got:
            return Path(got)
    except Exception:                        # 도구가 없거나 못 읽으면 옛 동작으로 — 훅이 세션을 브릭하지 않게
        pass
    return base / branch


def deny_reason(tool_name, tool_input, cwd=None, branch=None, repo=None, extra_roots=None,
                declared=None):
    """차단 사유 문자열, 통과면 None. **판정은 전부 여기 있다.**

    `declared` 는 컨테이너 루트 세션이 **스스로 선언한 갈래**다(`session_subject.py`).
    선언이 있으면 «리포» 를 그 워크트리로 바꿔 잰다 — 그러면 아래 과목·챕터 경계가
    **그대로 다시 성립한다**(경계를 여는 것이 아니라 기준점을 주는 것이다).
    ★ 그 대신 **선언 중에는 공통을 못 고친다** — 둘을 동시에 가지면 「한 세션이 전 과목
      규격을 소유」로 되돌아간다(`guard_bash.container_root_violation` 과 같은 판정).
    """
    tool_input = tool_input or {}
    if declared and repo is None:
        repo = declared_worktree(declared)
    repo = Path(repo) if repo else REPO
    fp = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not isinstance(fp, str) or not fp.strip():
        return None
    if SELFTEST in fp:
        return ("[selftest] 훅이 살아 있다 — 이 메시지가 보이면 PreToolUse 가 allow 보다 먼저 발화한다.")

    path = _resolve(fp, cwd)
    rel = None
    if _under(path, repo):
        rel = Path(path).relative_to(repo).as_posix()

    # ── 선언 중의 배타 ─────────────────────────────────────────
    # 과목을 선언한 세션은 **그 과목만** 만진다. 공통(main 워크트리 전체 + 자기 갈래의
    # `tools/`·`docs/`·`.claude/` …)은 선언을 끈 뒤에 고친다 — 둘을 동시에 가지면
    # 「한 세션이 전 과목 규격을 소유」로 되돌아가고, 그게 컨테이너 루트 배선이 없앤 형태다.
    # ★ `_under(path, REPO)` 가 재는 것은 **이 훅이 사는 워크트리(보통 main)의 공통**이다.
    #   그래서 선언한 갈래가 **바로 그 워크트리일 때는 그 절이 자기 데이터까지 «공통» 으로
    #   만든다** — 선언한 과목이 자기 것을 못 쓰는 상태가 된다. 2026-08-15 에 appsolids
    #   워크트리에서 회귀 ⑼-b·⑼-c 가 정확히 그렇게 빨간불이었다(다른 갈래에서는 초록이라
    #   **한 갈래에서만 보이는 결함**이었다 — 과목 경계 「담김」 사고와 같은 부류다).
    #   그 자리에서는 경로 판정(`common_repo_paths`) 하나로 충분하다.
    if declared and ((_under(path, REPO) and repo != REPO)
                     or (rel and gb.common_repo_paths([rel]))):
        return (f"과목(`{declared}`)을 선언한 동안에는 **공통을 고치지 않는다**.\n"
                f"  대상: {path}\n"
                "  둘을 동시에 가지면 「한 세션이 전 과목 규격을 소유」로 되돌아간다 —\n"
                "  컨테이너 루트 배선이 없애려던 바로 그 형태다.\n"
                "  -> `python tools/session_subject.py --off` 로 선언을 먼저 끌 것.")

    # ── 규칙 9 — 쓰기가 허용된 자리 ─────────────────────────────
    #  선언된 경로는 **규칙 5 를 못 이긴다.** 홈의 Claude 설정은 사용자 것이라, 다른
    #  프로젝트를 열어 준 선언이 그 자리까지 함께 여는 일이 있어선 안 된다.
    in_home_claude = _under(path, Path.home() / ".claude")
    roots = extra_write_roots() if extra_roots is None else extra_roots
    declared = (not in_home_claude) and any(_under_ci(path, r) for r in roots)
    if rel is None and not (_is_scratchpad(path) or _under(path, SHARED_SYSTEM)
                            or _is_agent_memory(path) or declared):
        where = "규칙 5(홈의 Claude 설정)" if in_home_claude else "규칙 9"
        return (f"{where} — 쓰기는 네 곳뿐이다: 리포(`{repo}`) · 세션 스크래치패드 · "
                f"공용 시스템(`{SHARED_SYSTEM}`) · 에이전트 메모리.\n"
                f"  경로: {path}\n"
                "  -> 그 밖에 써야 할 일이면 **하지 말고 사용자에게 먼저 묻는다.**\n"
                f"     (사용자가 연 경로는 `{EXTRA_ROOTS.name}` 에 사유와 함께 적힌다.\n"
                "      **스스로 거기 줄을 더하지 않는다** — 그러면 이 경계는 없는 것과 같다.)")

    if rel is None:
        return None                          # 스크래치패드·공용·메모리 — 아래 규칙은 리포 전용이다

    # ── 규칙 1 — 빌드 산출물 손편집 금지 ────────────────────────
    if rel.startswith("site/") and not rel.startswith("site/template/") and rel.endswith(".html"):
        return ("규칙 1 — 빌드 산출물은 손으로 고치지 않는다. 빌드가 덮어쓴다.\n"
                f"  대상: {rel}\n"
                "  -> 뷰어는 `site/template/viewer.template.html`, 콘텐츠는 `data/**/*.json` 을\n"
                "     고치고 `python tools/build_site.py` 를 돌릴 것.")

    branch = current_branch(repo) if branch is None else branch

    # ── 과목 경계 ───────────────────────────────────────────────
    if gb.foreign_subject_paths(branch, [rel]):
        return (f"과목 경계 — `{branch}` 세션은 다른 과목 파일을 고치지 않는다(그 폴더 세션의 몫).\n"
                f"  대상: {rel}\n"
                "  -> 읽는 것은 된다: `git show <브랜치>:<경로>`.")

    # ── 챕터 경계 ───────────────────────────────────────────────
    if gb.out_of_chapter_paths(branch, [rel]):
        return (f"챕터 경계 — `{branch}` 는 자기 챕터 콘텐츠만 만진다.\n"
                f"  대상: {rel}\n"
                "  -> 공통(규격·검사·뷰어)은 과목 본 세션이 소유한다. 그쪽에 요청하고 merge 로 받을 것.")

    return None


def main():
    try:
        payload = gb.read_payload()          # cp949 로 읽으면 한글 경로가 조용히 깨진다
    except Exception:
        return 0                             # 못 읽으면 통과 — 훅이 작업을 브릭하지 않게
    if not isinstance(payload, dict):
        return 0                             # 입력을 못 읽으면 통과 — 훅이 작업을 브릭하지 않게
    reason = deny_reason(payload.get("tool_name", ""),
                         payload.get("tool_input") or {},
                         payload.get("cwd") or os.getcwd(),
                         declared=gb.declared_subject(payload))
    if reason:
        sys.stderr.write("[guard_write 차단]\n" + reason + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
