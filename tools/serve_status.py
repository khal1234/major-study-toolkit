#!/usr/bin/env python
"""로컬 뷰어 서버 상태 + 접속 링크 (2026-07-28 신설 · 2026-09-07 평탄화 반영).

**왜 도구인가 — 승인 프롬프트의 필요를 없애려고.** 서버가 떠 있는지 보려고 `netstat` 을
불렀더니 승인창이 떴다. `Bash(netstat *)` 가 allow 에 있는데도, 그리고 세션 시작 시점의
설정에도 이미 있었는데도 그랬다(승인 원장 16번 — **원인 미상**). 권한을 추측으로 손대는 대신
**그 명령을 부를 일 자체를 없앤다** — 원장 9번(`> 리디렉션` → `--fail-only` 신설)과 같은 방식.
`python tools/*.py` 는 자동 허용이라 프롬프트가 0이다.

★ **포트는 `serve_site.vbs` 가 정본**이다 — 여기서 다시 적지 않고 파싱해서 읽는다.
  사본을 만들면 반드시 갈라진다(이 리포가 install_startup.ps1 에서 이미 겪은 부류).

★★ **과목별 포트 표는 폐기됐다** (2026-09-06 구조 이전 · 2026-09-07 평탄화). 나눈 이유는
  «과목마다 워크트리가 따로라 그 site\\ 에 자기 과목만 있다» 였는데, 한 트리로 합친 뒤에는
  **서버 하나가 전 과목을 낸다.** 그래서 이 도구도 «워크트리를 찾는» 일을 하지 않는다 —
  `data/<과목>/index.json` 이 있는 폴더가 곧 과목이다(폴더 이름을 짐작하지 않는다는 성질은
  그대로다. 짐작할 이름 자체가 없어졌을 뿐이다).

    python tools/serve_status.py           # 전 과목 상태와 링크
    python tools/serve_status.py --open ch01   # 링크를 chNN 로 만들어 준다

exit 0 = 떠 있음, 1 = 꺼져 있음.
"""
import argparse
import json
import os
import re
import socket
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.join(ROOT, "tools", "serve_site.vbs")
DATA = os.path.join(ROOT, "data")


def default_port(vbs_text):
    """`serve_site.vbs` 의 기본 포트. 순수 함수 — 테스트가 직접 부른다.

    정본이 한 곳(vbs)이라 표류가 불가능하다. 못 읽으면 **짐작하지 않고** None 을 준다 —
    8800 을 폴백으로 박아 두면 런처가 바뀐 것을 아무도 모른 채 «떠 있음» 이 거짓말이 된다.
    """
    m = re.search(r"If\s+port\s*=\s*0\s+Then\s+port\s*=\s*(\d+)", vbs_text)
    return int(m.group(1)) if m else None


def subjects():
    """`data/<과목>/index.json` 이 있는 폴더 이름 전부 (정렬)."""
    if not os.path.isdir(DATA):
        return []
    return [n for n in sorted(os.listdir(DATA))
            if os.path.isfile(os.path.join(DATA, n, "index.json"))]


def is_up(port, timeout=0.4):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex(("127.0.0.1", port)) == 0


def first_chapter(subject):
    """index.json 의 첫 챕터 파일명 → chNN. 없으면 None."""
    idx = os.path.join(DATA, subject, "index.json")
    try:
        with open(idx, encoding="utf-8") as fh:
            chapters = json.load(fh).get("chapters") or []
    except Exception:
        return None
    for entry in chapters:
        if os.path.isfile(os.path.join(DATA, subject, entry.get("file", ""))):
            return "ch" + str(entry["chapterNumber"]).zfill(2)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", default="", help="링크를 이 챕터로 만든다(예 ch01). 없으면 첫 챕터")
    args = ap.parse_args()

    with open(LAUNCHER, encoding="utf-8") as fh:
        port = default_port(fh.read())
    if port is None:
        print("serve_site.vbs 에서 기본 포트를 못 읽었다 — `If port = 0 Then port = …` 이 바뀌었나.",
              file=sys.stderr)
        return 1

    up = is_up(port)
    print("포트 %d — %s" % (port, "떠 있음" if up else "꺼짐"))
    print("-" * 74)
    for subject in subjects():
        chapter = args.open or first_chapter(subject) or ""
        tail = "/" + chapter + ".html" if chapter else "/"
        built = os.path.isdir(os.path.join(ROOT, "site", subject))
        print("%-24s %-7s http://localhost:%d/%s%s"
              % (subject, "빌드됨" if built else "빌드안됨", port, subject, tail))

    if not up:
        print("\n꺼져 있다. 지금 띄우려면:  wscript tools/serve_site.vbs")
        print("로그온 자동 실행까지 걸려면:  "
              "powershell -ExecutionPolicy Bypass -File tools/install_startup.ps1 -AsTask -All")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
