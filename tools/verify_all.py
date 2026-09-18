# -*- coding: utf-8 -*-
"""**공통을 고쳤을 때 전 과목이 아직 서는가** — 한 번에 돈다 (신설 2026-08-15).

★ 왜 열렸나. 공통(`tools/`·`site/template/`·`.claude/hooks/`)을 한 줄 고치면 그 영향은
  **모든 갈래**에 간다. 그런데 확인은 갈래마다 손으로 `build_site` + `test_checks` 를 돌리는
  것뿐이었다 — 12과목이면 24번이다. 실측(2026-08-15 이 세션): 공통을 여덟 번 고치는 동안
  **같은 두 명령을 스무 번 넘게** 손으로 쳤고, 그때마다 «어느 과목까지 봤나» 를 사람이 셌다.
  전파는 `sync_common --merge-all` 이 한 번에 도는데 **확인만 손이었다.**

★★ **판정하지 않는다 — 돌리고 표로 낸다.** 무엇이 실패인지는 각 도구가 이미 정한다
  (빌드는 exit 코드, 회귀는 `--fail-only`). 여기서 판정을 다시 적으면 **자가 둘**이 되고,
  그러면 «도구는 빨간불인데 이 표는 초록» 같은 자리가 생긴다.

★ **콘텐츠가 없는 갈래도 찍는다.** 2-2 과목처럼 챕터가 0개면 빌드할 것이 없는데, 그 줄을
  안 찍으면 «안 돈 것»과 «통과한 것»이 화면에서 같아진다(규칙 11).

쓰는 법
  python tools/verify_all.py              # 전 갈래 · 빌드 + 회귀
  python tools/verify_all.py --tests-only # 회귀만 (빌드는 건너뛴다)
  python tools/verify_all.py --only=thermo,math
"""
import os
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(args, cwd=None):
    return subprocess.run(["git", "-C", cwd or ROOT] + args, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def worktrees():
    """`(경로, 갈래)` 목록. **목록을 코드에 적지 않는다** — 새 과목이 생긴 날 여기만 옛 세상이 된다."""
    out, cur = [], None
    for line in _git(["worktree", "list", "--porcelain"]).stdout.splitlines():
        if line.startswith("worktree "):
            cur = line[len("worktree "):].strip()
        elif line.startswith("branch ") and cur:
            out.append((cur, line[len("branch "):].strip().rsplit("/", 1)[-1]))
            cur = None
    return out


def failure_count(text, ok):
    """그 출력이 신고한 **실제 건수**. 순수 함수 — 테스트가 직접 부른다.

    ★ **열린 날 2026-08-26.** 요약이 `bad += 1` 로 «갈래 × 축» 을 세면서 단위를 「건」이라
      적었다 — 한 갈래가 넷을 신고해도 화면에는 «실패 1건» 이 남는다. 「1건이면 사소하다」로
      읽히는 자리라, 세는 것과 적는 단위가 어긋나면 **요약이 본문보다 힘이 세다.**
    ★ `[FAIL]` 표식을 센다(회귀의 형식). 표식이 없는 자(빌드는 exit 코드로만 말한다)는
      **실패 1건으로 친다** — 0으로 두면 «실패했는데 0건» 이 되어 같은 결함을 되풀이한다.
    """
    if ok is not False:
        return 0
    n = sum(1 for ln in (text or "").splitlines() if "[FAIL]" in ln)
    return n or 1


def run(path, script, args):
    """그 갈래의 **자기 사본**으로 돌린다. `(성공, 마지막 줄, 건수)`.

    ★ 남의 갈래를 이 갈래의 도구로 재지 않는다 — 공통이 아직 전파 안 됐으면 그 사실 자체가
      드러나야 한다(자기 사본으로 돌려야 «merge 를 안 했다» 가 빨간불로 보인다).
    ★★ **`cwd` 는 그 갈래다 — 컨테이너 루트에서 손으로 돌린 결과와 다를 수 있다** (2026-08-26).
      실측: dynamics 회귀가 여기서는 1건, 컨테이너 루트를 cwd 로 두고 같은 파일을 돌리면 4건이다
      (늘어난 셋은 `git` 을 `-C` 없이 부르는 검사라 cwd 를 탄다). **여기 값이 기준이다** —
      그 갈래 세션이 실제로 서는 자리가 그 폴더이기 때문이다. 손으로 견줄 때는 cwd 를 맞출 것.
    """
    tool = os.path.join(path, "tools", script)
    if not os.path.isfile(tool):
        return None, "도구 없음 (merge 안 됨?)", 0
    r = subprocess.run([sys.executable, tool] + args, cwd=path, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    body = (r.stdout or "") + (r.stderr or "")
    tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    ok = r.returncode == 0
    return ok, (tail[-1][:70] if tail else (r.stderr or "").strip()[:70]), failure_count(body, ok)


def main(argv):
    only = next((a.split("=", 1)[1].split(",") for a in argv if a.startswith("--only=")), None)
    tests_only = "--tests-only" in argv
    rows, bad_branches, bad_cases = [], set(), 0
    for path, branch in worktrees():
        if only and branch not in only:
            continue
        has_data = os.path.isdir(os.path.join(path, "data"))
        if tests_only or not has_data:
            build = (None, "과목 없음" if not has_data else "건너뜀", 0)
        else:
            build = run(path, "build_site.py", ["--all", "--quiet"])
        tests = run(path, "test_checks.py", ["--fail-only"])
        for ok, _msg, n in (build, tests):
            if ok is False:
                bad_branches.add(branch)
                bad_cases += n
        rows.append((branch, build, tests))

    def cell(triple):
        ok, msg, n = triple
        mark = "—" if ok is None else ("통과" if ok else "★실패 %d건" % n)
        return "%-9s %s" % (mark, msg)

    print("\n[전 갈래 확인] 갈래 %d개" % len(rows))
    print("%-12s %-28s %s" % ("갈래", "빌드", "회귀"))
    print("-" * 92)
    for branch, build, tests in rows:
        print("%-12s %-28s %s" % (branch, cell(build)[:28], cell(tests)))
    if bad_branches:
        # ★ **갈래 수와 건수를 따로 적는다** — 한 갈래가 넷을 신고해도 옛 요약은 «실패 1건»
        #   이었고, 그 한 줄이 본문 넷보다 힘이 셌다(2026-08-26).
        print("\n★ 실패 — 갈래 %d개 · 신고 **%d건** (%s)"
              % (len(bad_branches), bad_cases, ", ".join(sorted(bad_branches))))
        print("  그 갈래 폴더를 cwd 로 두고 직접 돌려 무엇이 깨졌는지 볼 것"
              " — cwd 가 다르면 건수도 달라진다(`run` 독스트링).")
        return 1
    print("\n전 갈래 통과.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
