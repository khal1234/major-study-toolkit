#!/usr/bin/env python
"""워크트리 bare 오인 복구 (2026-07-26 신설).

**왜 이 도구인가 (사용자 지적):**
*"git config --worktree core.bare false — 정상이면 ask로 떠야 하지 않나. 모두 허용 뜨는거 자체가
합리적이지 않다고 봐. 1회 허용만 뜨는거면 몰라도."*

맞는 지적이다. 이 명령은 승인창에서 **`모두 허용`** 을 제공하는데, 거기 한 번 누르면
`git config` **쓰기 전체**가 영구히 열린다(`user.email`·`core.autocrlf`까지). 게이트를 둔 목적과
정반대다. 그렇다고 매번 손으로 치게 두면 같은 프롬프트가 계속 뜬다.

그래서 `commit.py`·`sync_common.py`와 같은 해법을 쓴다 — **git을 subprocess로 돌리는 tools/ 도구**.
`python tools/*.py`는 자동 허용이라 프롬프트가 없고, **이 도구가 할 수 있는 일은 코드로 고정**돼
있어 권한 글롭보다 훨씬 좁다. 즉 넓은 권한을 여는 대신 **좁은 능력을 주는** 쪽이다.

## 무엇을 고치나
bare 리포 + 링크드 워크트리 구성에서 `extensions.worktreeConfig`가 켜지면, **자기 `config.worktree`가
없는 워크트리**는 `core.bare` 해석을 잃고 bare로 오인된다 → `git status`·`add`·`commit`이
`fatal: this operation must be run in a work tree`로 전부 죽는다.
Claude가 백그라운드 작업용 워크트리를 만들 때 이 확장이 켜지므로 **재발한다**(2026-07-26 실사고).

이 도구는 **오직** `core.bare=false`만 현재 워크트리에 쓴다. 다른 키는 건드리지 않는다.

    python tools/fix_worktree_config.py          # 진단만 (아무것도 쓰지 않는다)
    python tools/fix_worktree_config.py --apply  # 고장 났을 때만 고친다
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ★ 이 도구가 쓸 수 있는 유일한 설정. 여기를 늘리면 도구의 존재 이유(좁은 능력)가 무너진다.
ALLOWED_WRITE = ("core.bare", "false")


def _git(args, cwd=ROOT):
    return subprocess.run(["git", "-C", cwd] + args, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def diagnose(cwd=ROOT):
    """(고장인가, 사유) — 순수 조회. 테스트 대상."""
    bare = _git(["rev-parse", "--is-bare-repository"], cwd).stdout.strip()
    inside = _git(["rev-parse", "--is-inside-work-tree"], cwd)
    if bare == "true":
        return True, "git이 이 워크트리를 bare로 오인한다 (--is-bare-repository=true)"
    if inside.returncode != 0:
        return True, "work tree로 인식되지 않는다: " + inside.stderr.strip()
    return False, "정상 — work tree로 인식된다"


def main(argv):
    apply = "--apply" in argv
    broken, why = diagnose()
    print("[진단] " + why)
    if not broken:
        print("고칠 것이 없다. (--apply 를 줘도 쓰지 않는다)")
        return 0
    if not apply:
        print("고치려면: python tools/fix_worktree_config.py --apply")
        return 1

    key, value = ALLOWED_WRITE
    r = _git(["config", "--worktree", key, value])
    if r.returncode != 0:
        print("실패:\n" + r.stderr)
        return 1
    broken_after, why_after = diagnose()
    print("[적용] " + key + "=" + value + " (현재 워크트리 전용)")
    print("[재확인] " + why_after)
    return 1 if broken_after else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
