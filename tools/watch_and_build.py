# -*- coding: utf-8 -*-
"""공통(main) `site/template/**` 이 바뀌면 전 과목을 자동으로 다시 빌드한다.

열린 경위(2026-09-02, 사용자): *[발화 생략]*

`buildlib/render.py` 가 템플릿을 이제 main 워크트리에서 직접 읽지만(머지 없이 최신을 쓴다),
브라우저는 **디스크에 이미 구워진 정적 HTML** 만 본다 — 그래서 템플릿을 고친 뒤에도 그 과목의
`build_site.py` 를 한 번은 돌려야 새로고침에 반영된다. 이 스크립트는 그 "한 번"을 자동화한다:
main 의 `site/template/**` 를 몇 초 간격으로 지켜보다가 바뀌면 형제 워크트리(과목) 전부를
백그라운드로 다시 빌드한다. 그 뒤에는 정말로 **새로고침만** 하면 된다.

- 감시 대상은 `site/template/**` 뿐이다(공통·과목무관). 과목 데이터(`data/<과목>/*.json`)는
  그 과목 세션에서 직접 `build_site.py` 를 돌리는 것이 정본이다 — 그건 이미 그 세션이 하고
  있어 자동화가 없어도 새로고침 전에 항상 빌드가 낀다.
- `tools/**`(빌드 스크립트 자체)는 대상이 아니다 — 그건 실행되는 코드라 각 워크트리가
  실제로 갖고 있어야 돌고, 그 로직을 고치면 여전히 `git merge main` 이 필요하다
  (`buildlib/render.py` 의 `_shared_site_root` 독스트링이 그 경계의 정본).
- 순수 폴링이다(외부 감시 라이브러리 의존 없음) — mtime 최댓값만 비교한다.
- 실패해도 감시를 멈추지 않는다: 한 과목 빌드가 깨져도(예: 그 과목이 진행 중인 미완성 데이터를
  갖고 있어도) 나머지 과목과 다음 회차는 계속 돈다. 실패 내용은 로그에 남는다.

사용:
    python tools/watch_and_build.py            # 상주(포그라운드, 로그를 표준출력에)
    python tools/watch_and_build.py --once      # 지금 상태로 한 번만 훑고 끝(디버그용)

로그: tools/watch_and_build.log (실행 중 계속 append)
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG_PATH = os.path.join(HERE, "watch_and_build.log")
WATCH_DIR = os.path.join(ROOT, "site", "template")
# 고른 값이다 — 파일 저장 직후 반응하되(1초는 너무 잦아 CPU만 태운다), 몇 초 늦어도 되는
# 자리다(사람이 저장하고 브라우저로 돌아가 새로고침하기까지 몇 초는 항상 걸린다).
POLL_SECONDS = 3


def _log(line):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = "[" + stamp + "] " + line
    print(msg, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    except OSError:
        pass


def watched_snapshot():
    """감시 대상 파일들의 (경로, mtime) 최댓값 — 통째로 다시 훑지 않게 max 하나로 압축."""
    latest = 0.0
    if not os.path.isdir(WATCH_DIR):
        return latest
    for name in os.listdir(WATCH_DIR):
        path = os.path.join(WATCH_DIR, name)
        if os.path.isfile(path):
            try:
                latest = max(latest, os.path.getmtime(path))
            except OSError:
                pass
    return latest


def worktrees():
    """(path, branch) 목록 — `deploy_all.worktrees()` 와 같은 파싱(중복이지만 의존을 안 만든다:
    이 스크립트는 그 자체로 최소한만 돌아야 한다 — build_site.py 를 부르는 것 말고는 아무 것도
    import 하지 않는다)."""
    out = subprocess.run(["git", "-C", ROOT, "worktree", "list", "--porcelain"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    res, cur = [], None
    for ln in out.splitlines():
        if ln.startswith("worktree "):
            cur = {"path": ln[len("worktree "):].strip(), "branch": None}
            res.append(cur)
        elif ln.startswith("branch ") and cur is not None:
            ref = ln[len("branch "):].strip()
            cur["branch"] = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
    return res


def rebuild_all_subjects():
    for wt in worktrees():
        branch = wt.get("branch")
        path = wt["path"]
        if not branch or branch == "main" or not os.path.isdir(path):
            continue
        build_script = os.path.join(path, "tools", "build_site.py")
        if not os.path.isfile(build_script):
            continue
        proc = subprocess.run([sys.executable, build_script, "--quiet"],
                               cwd=path, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        if proc.returncode == 0:
            _log(branch + ": 재빌드 완료")
        else:
            tail = (proc.stdout or "").strip().splitlines()[-3:]
            _log(branch + ": 재빌드 실패 — " + " / ".join(tail))


def main(argv):
    once = "--once" in argv
    _log("감시 시작 — " + WATCH_DIR)
    last = watched_snapshot()
    if once:
        rebuild_all_subjects()
        return 0
    while True:
        time.sleep(POLL_SECONDS)
        now = watched_snapshot()
        if now > last:
            last = now
            _log("템플릿 변경 감지 — 전 과목 재빌드")
            rebuild_all_subjects()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
