#!/usr/bin/env python
"""로컬 뷰어 서버 상태 + 접속 링크 (2026-07-28 신설).

**왜 도구인가 — 승인 프롬프트의 필요를 없애려고.** 서버가 떠 있는지 보려고 `netstat` 을
불렀더니 승인창이 떴다. `Bash(netstat *)` 가 allow 에 있는데도, 그리고 세션 시작 시점의
설정에도 이미 있었는데도 그랬다(승인 원장 16번 — **원인 미상**). 권한을 추측으로 손대는 대신
**그 명령을 부를 일 자체를 없앤다** — 원장 9번(`> 리디렉션` → `--fail-only` 신설)과 같은 방식.
`python tools/*.py` 는 자동 허용이라 프롬프트가 0이다.

포트 맵은 **`serve_site.vbs` 가 정본**이다 — 여기서 다시 적지 않고 파싱해서 읽는다.
사본을 만들면 반드시 갈라진다(이 리포가 install_startup.ps1 에서 이미 겪은 부류).

    python tools/serve_status.py           # 전 과목 상태와 링크
    python tools/serve_status.py --open ch01   # 링크를 chNN 로 만들어 준다

exit 0 = 하나라도 떠 있음, 1 = 전부 꺼져 있음.
"""
import argparse
import json
import os
import re
import socket
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.join(ROOT, "tools", "serve_site.vbs")
WORKTREE_PARENT = os.path.dirname(ROOT)

sys.path.insert(0, os.path.join(ROOT, "tools"))
from worktree_names import find_worktree                                  # noqa: E402


def port_map(vbs_text):
    """`serve_site.vbs` 의 Select Case 에서 (워크트리 폴더 → 포트) 를 뽑는다.

    순수 함수 — 테스트가 직접 부른다. 정본이 한 곳(vbs)이라 표류가 불가능하다.
    """
    pairs = re.findall(r'Case\s+"([A-Za-z0-9_-]+)"\s*\r?\n\s*port\s*=\s*(\d+)', vbs_text)
    return {name: int(p) for name, p in pairs}


def subject_of(worktree_dir):
    """그 워크트리가 담당하는 과목 폴더 이름. data/ 아래에서 찾는다(없으면 None)."""
    data_root = os.path.join(worktree_dir, "data")
    if not os.path.isdir(data_root):
        return None
    names = [n for n in sorted(os.listdir(data_root))
             if os.path.isfile(os.path.join(data_root, n, "index.json"))]
    return names[0] if len(names) == 1 else (names[0] if names else None)


def is_up(port, timeout=0.4):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex(("127.0.0.1", port)) == 0


def first_chapter(worktree_dir, subject):
    """index.json 의 첫 챕터 파일명 → chNN. 없으면 None."""
    idx = os.path.join(worktree_dir, "data", subject, "index.json")
    if not os.path.isfile(idx):
        return None
    try:
        with open(idx, encoding="utf-8") as fh:
            chapters = json.load(fh).get("chapters") or []
    except Exception:
        return None
    for entry in chapters:
        if os.path.isfile(os.path.join(worktree_dir, "data", subject, entry.get("file", ""))):
            return "ch" + str(entry["chapterNumber"]).zfill(2)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", default="", help="링크를 이 챕터로 만든다(예 ch01). 없으면 첫 챕터")
    args = ap.parse_args()

    with open(LAUNCHER, encoding="utf-8") as fh:
        ports = port_map(fh.read())
    if not ports:
        print("serve_site.vbs 에서 포트 맵을 못 읽었다 — Select Case 형식이 바뀌었는지 볼 것.")
        return 1

    print("포트   과목            상태    링크")
    print("-" * 74)
    any_up = False
    for branch, port in sorted(ports.items(), key=lambda kv: kv[1]):
        # 폴더 이름을 짐작하지 않는다 — «열역학-thermo» 라 join(parent, branch) 는 빗나간다
        # (2026-08-23). 규칙 정본은 tools/worktree_names.py.
        wt = find_worktree(WORKTREE_PARENT, branch)
        subject = subject_of(wt) if wt else None
        up = is_up(port)
        any_up = any_up or up
        if subject is None:
            print("%-6d %-15s %-7s %s" % (port, "(" + branch + ")", "—", "워크트리 없음"))
            continue
        chapter = args.open or first_chapter(wt, subject) or ""
        tail = "/" + chapter + ".html" if chapter else "/"
        print("%-6d %-15s %-7s http://localhost:%d/%s%s"
              % (port, subject, "떠 있음" if up else "꺼짐", port, subject, tail))

    if not any_up:
        print("\n전부 꺼져 있다. 이 워크트리만 띄우려면:  cscript tools/serve_site.vbs")
        print("로그온 자동 실행까지 걸려면:  powershell -ExecutionPolicy Bypass -File tools\\install_startup.ps1 -All")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
