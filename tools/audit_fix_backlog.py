# -*- coding: utf-8 -*-
r"""이미 있는 `fix_*.py` 처방 도구들이 **다른 과목의 기존 콘텐츠**에도 걸리는 후보가 있는지,
과목을 커밋 수(활동량) 내림차순으로 순회하며 한 번에 훑는다.

    python tools/audit_fix_backlog.py
    python tools/audit_fix_backlog.py --only=thermo,dynamics

열린 날 2026-08-29. 원인 — AGENTS 규칙 7 확장(「부류 판정은 과목 경계를 넘는다」)의 ⑶에
해당하는 도구: `fix_*.py`(⑵)는 이미 여럿 있는데, 그 처방이 다른 과목의 **기존** 콘텐츠에도
적용 대상이 있는지 훑는 자리(⑶)가 없었다. 각 도구를 미리보기(비-`--apply`) 모드로
과목마다 돌려 후보 수만 모은다.

★ 이 도구는 **판정하지 않고 고치지도 않는다.** 후보 수만 낸다 — 실제 적용은 사람이
그 과목 세션에서 `--apply` 로 돈다(공통 도구를 컨테이너 루트에서 `--apply` 하면 과목 데이터
쓰기라 guard_bash 가 막는다 — 정상이다).

★ **과목 이름을 박지 않는다.** 갈래 목록은 `git worktree list`, 순서는 `git rev-list --count`
로 정한다(audit_convention_drift.py 와 같은 패턴).

★ 도구마다 인터페이스가 조금씩 다르다(일부만 `--summary`). 우선순위로 하나를 고르고,
출력에서 `\d+\s*(건|개)` 패턴을 찾아 후보 수로 삼는다 — 못 찾으면 원출력 줄 수를 낸다
(대략치라고 표시한다).
"""
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 처방 도구 목록 — AGENTS.md 도구 등록부의 "이미 있는 삽화의 규격 전수 교정" · 표기 계열.
# 값(문턱·규격)은 안 적는다 — 각 도구 자신이 안다.
TOOLS = [
    ("fix_caption_block_gap.py", []),
    ("fix_miter_join.py", []),
    ("fix_dim_label_gap.py", []),
    ("fix_dim_extension.py", []),
    ("fix_rate_dot.py", []),
    ("fix_math_slash_fraction.py", []),
    ("fix_symbol_product.py", ["--summary"]),
    ("fix_numeric_product.py", ["--summary"]),
    ("fix_latex_brace_args.py", []),
    ("fix_honorific.py", []),
    ("fix_velocity_symbol.py", []),
    ("fix_figure_caption_tier.py", []),
]

COUNT_RE = re.compile(r"(\d+)\s*(건|개|곳|자리)")


def git(*args):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") if r.returncode == 0 else ""


def worktrees():
    """{branch: 절대경로} — main 은 뺀다(과목이 없다)."""
    out, cur = {}, {}
    for line in git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            cur = {"path": line.split(" ", 1)[1]}
        elif line.startswith("branch "):
            name = line.split("/")[-1].strip()
            if name and name != "main":
                out[name] = cur["path"]
    return out


def commit_count(branch):
    r = subprocess.run(["git", "rev-list", "--count", branch],
                        capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return int((r.stdout or "0").strip())
    except ValueError:
        return 0


def run_tool(worktree_path, tool_name, extra_flags):
    tool_path = worktree_path.rstrip("/\\") + "/tools/" + tool_name
    r = subprocess.run(["python", tool_path, *extra_flags], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", cwd=worktree_path,
                        stdin=subprocess.DEVNULL)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode not in (0, 1):
        return "[해당 없음 또는 오류 rc=%d]" % r.returncode
    lines = [l for l in out.splitlines() if l.strip()]
    if not lines:
        return "0건"
    last = lines[-1]
    nums = COUNT_RE.findall(last)
    if nums:
        return "0건" if all(n[0] == "0" for n in nums) else last.strip()
    m = COUNT_RE.search(out)
    if m:
        return m.group(0)
    return "~%d줄(대략치 — 이 도구는 건수 패턴 없음)" % len(lines)


def main():
    only = None
    for flag in sys.argv[1:]:
        if flag.startswith("--only="):
            only = {s.strip() for s in flag.split("=", 1)[1].split(",") if s.strip()}

    wts = worktrees()
    ranked = sorted(wts, key=lambda b: -commit_count(b))
    if only:
        ranked = [b for b in ranked if b in only]

    print("fix_*.py 후보 백로그 — 과목을 활동량(커밋 수) 내림차순으로 훑는다\n")

    for branch in ranked:
        path = wts[branch]
        print("-- %s (%d commits) --" % (branch, commit_count(branch)))
        for tool, flags in TOOLS:
            result = run_tool(path, tool, flags)
            if result != "0건":
                print("  [%s] %s" % (tool, result))
        print()

    print("※ 후보만 낸다 — 판정은 사람이, 적용은 그 과목 세션에서 --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
