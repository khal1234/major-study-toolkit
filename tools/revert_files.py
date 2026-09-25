#!/usr/bin/env python
"""미커밋 변경을 HEAD 로 되돌린다 — **버릴 것을 먼저 보여 주고, 사본을 남기고** 되돌린다.

    python tools/revert_files.py <경로> [<경로> ...]
    python tools/revert_files.py --show <경로> ...   # 무엇이 사라지는지만 본다

## 왜 이 도구인가 (2026-08-13 신설, 사용자 지적)

사용자: *[발화 생략]*

`git checkout -- <파일>` 은 실행 규율 7 이 **게이트로 남겨 둔** 명령이다. 근거는 하나였다 —
**커밋 안 한 변경은 지우면 못 되찾는다.** 그 근거는 옳았지만, 그래서 매번 사람이 승인 버튼을
눌러야 했고 실제로 그 승인은 *[발화 생략]* 뿐이었다.

**그래서 게이트를 푸는 대신 위험 자체를 없앤다.** 되돌리기 전에

  ⑴ 버릴 변경의 `diff --stat` 을 **먼저 찍고**
  ⑵ 지금 내용을 **스크래치패드에 사본으로 남긴 뒤**
  ⑶ HEAD 로 복원한다.

사본이 남으므로 *[발화 생략]* 가 성립하지 않는다. `tools/*.py` 는 guard 가 자동 허용하므로
프롬프트도 사라진다 — `commit.py`·`sync_common.py` 가 git 을 감싼 것과 같은 형태다.

## 안 하는 것

- **브랜치 전환·리셋을 하지 않는다.** 이 도구가 아는 것은 `checkout -- <경로>` 하나뿐이다.
  `-b`·`--`·`.`·`-A` 같은 인자는 거부한다. 넓히면 게이트를 푼 것과 같아진다.
- **다른 과목 경로를 거부한다** — `commit.py` 와 **같은 함수**(`foreign_subject_paths`)를 쓴다.
- **추적되지 않는 파일은 손대지 않는다.** `checkout` 은 원래 그것을 못 지우고, 지우는 쪽으로
  넓히면 이 도구가 «삭제 도구» 가 된다.
- **사본을 지우지 않는다.** 스크래치패드는 세션마다 갈리므로 쌓여도 리포를 더럽히지 않는다.
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, ".claude", "hooks"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from guard_bash import foreign_subject_paths  # noqa: E402

BAD_ARGS = {"-A", "--all", ".", "-a", "-b", "-B", "--", "-f", "--force", "HEAD"}


def _git(args):
    return subprocess.run(["git", "-C", ROOT] + args, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def rejected_args(paths):
    """되돌릴 수 없게 넓히는 인자들. 순수 함수 — 테스트가 직접 부른다.

    경로를 **명시**하는 것이 이 도구의 존재 이유다. `.` 하나가 통과하면 워크트리 전체를
    되돌리게 되고, 그건 게이트를 없앤 것과 같다.
    """
    return [p for p in paths if p in BAD_ARGS or p.startswith("-")]


def backup_base(env):
    """사본을 둘 바탕 폴더 — 순수 함수, 테스트가 부른다.

    세션 스크래치패드가 있으면 거기, 없으면 **`.git/` 안**이다. 작업 트리에 두지 않는다 —
    되돌린 자국이 다음 배치의 변경점·미커밋으로 잡히면 잡음이 스스로를 재생산한다.
    ★ 2026-09-24 클라우드 실사고: 스크래치패드·TEMP 변수가 없는 컨테이너에서 옛 폴백 `"."` 이
      리포 루트에 `revert-backup-*/` 를 만들었고, 그것이 미커밋으로 남아 Stop 훅이 커밋을 요구했다
      (지우려면 `rm -rf` 승인이 필요했다). `.git/` 은 git 이 안 세고 리포 안이라 쓰기 경계(규칙 9)도 지킨다.
    """
    return env.get("CLAUDE_SCRATCHPAD") or env.get("TEMP") or os.path.join(ROOT, ".git")


def checkout_args(paths):
    """되돌리는 git 인자 — **HEAD 에서** 꺼낸다. 순수 함수, 테스트가 부른다.

    ★ 2026-09-24 실사고: 예전엔 `checkout -- <경로>` 였는데, 그건 **인덱스**에서 꺼낸다.
      `commit.py` 가 게이트에 막혀 스테이징을 남기면 인덱스 = 작업 트리라 아무것도 안 되돌리면서
      「HEAD 로 되돌렸다」 를 찍었고, 사람이 `git reset` 승인을 따로 해야 했다(클라우드 두 세션에서).
      `checkout HEAD -- <경로>` 는 인덱스와 작업 트리를 **둘 다** HEAD 로 되돌린다.
    """
    return ["checkout", "HEAD", "--"] + list(paths)


def backup_dir():
    out = os.path.join(backup_base(os.environ), "revert-backup-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(out, exist_ok=True)
    return out


def main(argv):
    args = argv[1:]
    show_only = "--show" in args
    paths = [a for a in args if a != "--show"]
    if not paths:
        print("usage: python tools/revert_files.py [--show] <경로> [<경로> ...]")
        print("  경로는 필수다 — 이 도구는 **인자로 준 파일만** 되돌린다.")
        return 2
    bad = rejected_args(paths)
    if bad:
        print("거부 — 경로를 명시하라: " + ", ".join(bad))
        print("  이 도구가 아는 것은 `git checkout -- <경로>` 하나뿐이다"
              "(브랜치 전환·리셋·강제는 여전히 사람이 승인한다).")
        return 2

    branch = _git(["branch", "--show-current"]).stdout.strip()
    foreign = foreign_subject_paths(branch, paths)
    if foreign:
        print("과목 경계 위반 — 현재 브랜치 '" + branch + "'에서 다른 과목 경로: "
              + ", ".join(foreign))
        return 2

    scope = ["--"] + list(paths)
    quiet_path = ["-c", "core.quotepath=false"]
    stat = _git(quiet_path + ["diff", "--stat", "HEAD"] + scope).stdout.strip()
    names = [ln.strip() for ln
             in _git(quiet_path + ["diff", "--name-only", "HEAD"] + scope).stdout.splitlines()
             if ln.strip()]
    if not names:
        print("되돌릴 변경이 없다 — 아무것도 하지 않았다(인자로 준 경로 기준).")
        return 0

    print("[버릴 변경]")
    print(stat)
    if show_only:
        print("(--show 라 아무것도 쓰지 않았다)")
        return 0

    # ⑵ 사본을 먼저 남긴다 — 이 한 줄이 «못 되찾는다» 를 «되찾을 수 있다» 로 바꾼다.
    out = backup_dir()
    saved = []
    for name in names:
        src = os.path.join(ROOT, name)
        if not os.path.isfile(src):
            continue                       # 삭제된 파일은 되살리는 쪽이라 사본이 필요 없다
        dst = os.path.join(out, name.replace("/", "__").replace("\\", "__"))
        with open(src, "rb") as fh_in, open(dst, "wb") as fh_out:
            fh_out.write(fh_in.read())
        saved.append(dst)
    print("[사본] " + str(len(saved)) + "개 — " + out)

    r = _git(checkout_args(paths))
    if r.returncode != 0:
        print("복원 실패:\n" + (r.stdout + r.stderr).strip())
        return 1
    print("[복원] " + str(len(names)) + "개 파일을 HEAD 로 되돌렸다.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
