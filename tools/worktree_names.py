# -*- coding: utf-8 -*-
"""워크트리 폴더 이름 규칙 — `<한글표시>-<갈래>` (2026-08-23 신설).

**왜 있는가.** 폴더 이름이 `thermo`·`appthermo` 뿐이면 프로젝트를 고르는 화면에서
어느 과목인지 사람이 못 읽는다(2026-08-23 사용자 지적). 그렇다고 폴더를 통째로
한글로 바꾸면 `serve_site.vbs` 가 죽는다 — 그 파일은 ANSI 로 해석되므로 UTF-8 로
저장된 한글 **문자열 리터럴**이 깨져 `Select Case` 비교가 늘 빗나간다(그 파일 주석에
적힌 실측). 그래서 **둘 다** 가진다:

    열역학-thermo     ← 사람이 읽는 것은 앞, 기계가 읽는 것은 뒤
    공학수학2-math2
    main              ← 구분자가 없으면 통째로 갈래다 (공통 워크트리)

**정본은 이 파일이다.** 같은 규칙이 `serve_site.vbs`(VBS) 와 `install_startup.ps1`(PS1)
에도 한 줄씩 있다 — 그 둘은 파이썬을 못 부른다. 세 벌이 표류하지 않는지는
`test_checks.test_worktree_folder_names` 가 지킨다.

★ 브랜치 이름은 바꾸지 않는다. 원격 ref 가 퍼센트 인코딩되고 `git` 표준출력이
  깨지기 때문이다(`git worktree list` 가 경로를 8진수로 뱉는 그 증상).
  폴더만 병기 이름이고, `guard_bash.SUBJECT_BY_BRANCH` 는 그대로 갈래를 키로 쓴다.

사용:
    python tools/worktree_names.py            # 지금 이름 → 바뀔 이름 (미리보기)
    python tools/worktree_names.py --apply    # git worktree move 로 실제 이동
"""

import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = "-"

# 표시 이름은 과목 이름에서 공백만 뺀 것이다 — 표를 하나 더 두면 표류한다.
# 예외는 **경로가 길어져 위험한 것**만 (윈도 MAX_PATH 260; 이 리포는 컨테이너 경로부터
# 한글이라 여유가 적다). 예외를 늘릴 때는 test_checks 의 길이 단언을 함께 볼 것.
# `math` 는 표에 **접두어**로만 적혀 있다('공학수학' — 실제 폴더는 '공학수학 1').
# 그대로 쓰면 `공학수학-math` 와 `공학수학2-math2` 가 나란히 서서 어느 쪽이 1학기인지 안 읽힌다.
LABEL_OVERRIDE = {"ee": "전기전자실험", "math": "공학수학1"}


def branch_token(folder_name):
    """폴더 이름에서 갈래(ASCII). `열역학-thermo` → `thermo` · `main` → `main`.

    순수 함수 — 테스트가 직접 부른다. VBS·PS1 에 같은 규칙이 한 줄씩 있다.
    """
    return folder_name.rsplit(SEP, 1)[-1].lower()


def label_for(branch, subject):
    """폴더 앞에 붙일 한글 표시. 공백은 뺀다 — 경로에 공백이 들어가면 인용이 늘어난다."""
    return LABEL_OVERRIDE.get(branch) or (subject or "").replace(" ", "")


def folder_name(branch, subject):
    """그 과목 워크트리가 가져야 할 폴더 이름."""
    label = label_for(branch, subject)
    return (label + SEP + branch) if label else branch


def find_worktree(parent, branch):
    """컨테이너 폴더에서 그 갈래의 워크트리 경로. 없으면 None.

    ★ `os.path.join(parent, branch)` 를 직접 쓰면 안 된다 — 폴더에 한글 표시가 붙은
      순간 «워크트리 없음» 으로 조용히 빠진다. 이름을 짐작하지 말고 **훑어서 찾는다**.
    """
    exact = os.path.join(parent, branch)
    if os.path.isdir(exact):
        return exact
    try:
        names = sorted(os.listdir(parent))
    except OSError:
        return None
    for name in names:
        path = os.path.join(parent, name)
        if os.path.isdir(path) and branch_token(name) == branch:
            return path
    return None


# ── 이동 도구 ───────────────────────────────────────────────────────────────

def _git(args, cwd=None):
    return subprocess.run(["git", "-C", cwd or ROOT] + args, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def worktrees():
    """`(경로, 갈래)` 목록. **목록을 코드에 적지 않는다.**

    `--porcelain` 은 경로를 날것 UTF-8 로 뱉는다(비porcelain 은 8진수로 인용한다 —
    한글 경로에서 그쪽을 파싱하면 깨진다. 2026-08-23 실측).
    """
    out, cur = [], None
    for line in _git(["worktree", "list", "--porcelain"]).stdout.splitlines():
        if line.startswith("worktree "):
            cur = line[len("worktree "):].strip()
        elif line.startswith("branch ") and cur:
            out.append((cur, line[len("branch "):].strip().rsplit("/", 1)[-1]))
            cur = None
    return out


def plan():
    """`(현재경로, 새경로, 갈래)` 중 **바뀌는 것만**."""
    sys.path.insert(0, os.path.join(ROOT, ".claude", "hooks"))
    from guard_bash import subject_of_branch                              # noqa: E402

    moves = []
    for path, branch in worktrees():
        # 표를 직접 뒤지지 않는다 — 챕터 브랜치(`thermo-ch02`)까지 아는 것은 이 함수뿐이다.
        subject = subject_of_branch(branch)
        if not subject:                       # main 등 과목 아닌 갈래는 그대로 둔다
            continue
        if SEP in branch:                     # 챕터 병렬 워크트리는 자기 이름을 지킨다
            continue                          # (`열역학-thermo-ch02` 면 토큰이 ch02 가 된다)
        parent, cur = os.path.dirname(path), os.path.basename(path)
        want = folder_name(branch, subject)
        if cur != want:
            moves.append((path, os.path.join(parent, want), branch))
    return moves


# ── 미리보기 서버 세우기·되살리기 ──────────────────────────────────────────
#
# ★ 폴더를 옮기려면 **서버를 먼저 내려야 한다** (2026-08-23 실측: `Permission denied`).
#   `serve_site.vbs` 가 띄운 `python -m http.server` 의 현재 폴더가 그 워크트리라
#   윈도가 폴더 이름 변경을 거부한다. 사람이 «권한 문제인가» 로 읽기 딱 좋은 메시지라
#   도구가 직접 내리고 직접 되살린다 — 손으로 12개를 세우게 두지 않는다.

def _port_map():
    """`{갈래: 포트}` — 정본은 이 워크트리(main)의 런처다. 사본을 두지 않는다."""
    from serve_status import port_map                                     # noqa: E402
    with open(os.path.join(ROOT, "tools", "serve_site.vbs"), encoding="utf-8") as fh:
        return port_map(fh.read())


def _ports():
    # 8800 은 «폴더 이름을 못 읽었을 때» 런처가 떨어지는 자리다. 여기 붙은 것이 있으면
    # 그건 옛 사본이 잘못 뜬 것이므로 같이 내린다 — 안 내리면 다음 것이 그 포트에 못 붙는다.
    return sorted(set(_port_map().values()) | {8800})


def restart_all():
    """모든 과목 워크트리의 미리보기 서버를 **포트를 지정해** 다시 띄운다."""
    stop_servers()
    parent, started = os.path.dirname(ROOT), 0
    for branch, port in sorted(_port_map().items(), key=lambda kv: kv[1]):
        wt = find_worktree(parent, branch)
        if wt and start_server(wt, port):
            started += 1
        else:
            print("skip  : " + branch + " (워크트리 없음)")
    print("[+] 미리보기 서버 " + str(started) + "개를 띄웠다 — 확인: python tools/serve_status.py")
    return 0


def _pids_on(ports):
    """그 포트를 **듣고 있는** 프로세스 pid. 포트로 좁혀 잡는다 — 파이썬을 통째로 죽이지 않는다."""
    want = {str(p) for p in ports}
    r = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    pids = set()
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3].upper() == "LISTENING":
            local = parts[1].rsplit(":", 1)
            if len(local) == 2 and local[1] in want:
                pids.add(parts[4])
    return sorted(pids)


def stop_servers():
    pids = _pids_on(_ports())
    for pid in pids:
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
    print("[-] 미리보기 서버 " + str(len(pids)) + "개를 내렸다 (폴더가 잠겨 있어서다)")
    return pids


def start_server(worktree_dir, port=None):
    """그 워크트리의 런처를 창 없이 띄운다.

    ★ **포트를 인자로 준다** (2026-08-23 실측). 런처는 폴더 이름으로도 포트를 정할 줄 알지만,
      그 판단을 하는 것은 **그 워크트리가 가진 자기 사본**이다 — 공통이 아직 merge 되지 않은
      갈래에서는 옛 사본이 돌고, 새 이름을 못 읽어 전부 8800 으로 떨어진다. 폴더를 옮긴 직후
      12개가 한 포트를 다퉜다(그중 하나만 떴고 나머지는 로그에만 흔적이 남았다).
    """
    vbs = os.path.join(worktree_dir, "tools", "serve_site.vbs")
    if not os.path.isfile(vbs):
        return False
    cmd = ["wscript", vbs] + ([str(port)] if port else [])
    subprocess.run(cmd, cwd=worktree_dir, capture_output=True)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 옮긴다(기본은 미리보기)")
    ap.add_argument("--restart", action="store_true",
                    help="옮기지 않고 미리보기 서버만 전부 다시 띄운다(포트 지정)")
    args = ap.parse_args(argv)

    if args.restart:
        return restart_all()

    moves = plan()
    if not moves:
        print("바꿀 것 없음 — 모든 과목 워크트리가 이미 `<한글표시>-<갈래>` 다.")
        return 0

    if args.apply:
        stop_servers()

    moved = []
    ports = _port_map() if args.apply else {}
    for src, dst, _branch in moves:
        print(("이동  " if args.apply else "예정  ")
              + os.path.basename(src) + "  →  " + os.path.basename(dst))
        if not args.apply:
            continue
        r = _git(["worktree", "move", src, dst])
        if r.returncode != 0:
            print("[FAIL] " + (r.stderr or r.stdout or "")[:400])
            break
        moved.append((dst, ports.get(_branch)))

    if not args.apply:
        print("\n실제로 옮기려면 --apply")
        return 0

    # ★ **옮긴 것만** 되살리면 안 된다 (2026-08-23 실측). 하나가 «Permission denied» 로 막히면
    #   나머지는 내린 채로 남아 미리보기가 통째로 꺼진다 — 실패한 자리가 아니라 **손댄 자리 전부**를
    #   원상으로 돌린다. `moved` 는 보고용이고 되살리기의 단위가 아니다.
    parent = os.path.dirname(ROOT)
    for branch, port in sorted(_port_map().items(), key=lambda kv: kv[1]):
        wt = find_worktree(parent, branch)
        if wt:
            start_server(wt, port)
    print("[+] 미리보기 서버를 다시 띄웠다 — 확인: python tools/serve_status.py")
    print("[!] 로그온 자동 실행 등록은 옛 경로를 가리킨다 — 다음을 한 번 돌릴 것:")
    print("    powershell -ExecutionPolicy Bypass -File tools\\install_startup.ps1 -AsTask -All")
    return 0 if len(moved) == len(moves) else 1


if __name__ == "__main__":
    sys.exit(main())
