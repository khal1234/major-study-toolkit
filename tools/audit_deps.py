# -*- coding: utf-8 -*-
r"""이 리포의 `.py` 가 실제로 무엇을 요구하는지 전수로 세고 `requirements.txt` 를 만든다.

    python tools/audit_deps.py              # 세기만 한다(어디서 쓰는지까지 찍는다)
    python tools/audit_deps.py --write      # requirements.txt 를 다시 쓴다
    python tools/audit_deps.py --check      # 파일이 실제 import 와 어긋나면 exit 1

열린 날 2026-09-08. 공용 폴더 `변경일지.md` 2026-09-08 「`requirements.txt` 를 각 리포가 세울 것」.
사용자 판정: 매니페스트를 세우자. **이 계정의 여덟 프로젝트가 파이썬 하나를 공유하는데
어느 코드가 무엇을 요구하는지 적힌 파일이 어디에도 없었다.** 그 대가를 하루에 세 번 봤다
(그 표에 실측이 적혀 있다).

★ **이 자가 조심하는 것 셋 — 전부 그날 실제로 데인 자리다.**

⑴ **extra 의존은 import 스캔에 안 보인다.** `font_subset.py` 는 `fontTools` 만 import 하는데
   woff2 서브셋은 `brotli`·`zopfli` 가 있어야 돈다(`fonttools[woff]`). 「아무도 import
   안 한다」로 지우면 그 자리가 죽는다. `pip check` 도 extra 를 안 본다.
   → 그런 것은 `EXTRA_REQUIRES` 에 **사유와 함께** 손으로 적는다. 기계가 못 찾는다.

⑵ **import 이름과 배포 이름이 다르다.** `fitz`→`pymupdf` · `PIL`→`pillow` ·
   `cv2`→`opencv-python-headless` · `yaml`→`PyYAML`. `DIST_NAME` 이 그 사전이다.

⑶ **다른 리포의 사본을 세지 않는다.** 검증 산출물·백업·`_retired/` 안의 `.py` 는
   「쓰는 중」이라고 거짓말한다. `SKIP_DIRS` 가 그것을 뺀다.

☐ **이 자가 못 보는 것:** 동적 import(`importlib.import_module(name)`) · 선택 의존
  (`try: import X except ImportError`) 의 «없어도 되는가» 판정 · 외부 실행파일
  (Tesseract 같은 것은 파이썬 패키지가 아니라 이 목록에 안 들어간다).
"""
import ast
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQ_PATH = os.path.join(ROOT, "requirements.txt")

# 다른 리포의 사본·산출물·캐시. 여기 있는 `.py` 는 「쓰는 중」의 근거가 못 된다.
#   ★ **`.claude/` 는 안 뺀다** — 훅이 거기 산다. 처음에 점으로 시작하는 폴더를 통째로
#   건너뛰었더니 `guard_bash`·`session_brief` 같은 **우리 훅 아홉이 서드파티로 잡혔다**
#   (2026-09-08 첫 실행). 로컬 이름을 모으는 자와 import 를 훑는 자가 **같은 범위**를 봐야 한다.
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build",
             "review-artifacts", "site", "_retired", ".mypy_cache", ".pytest_cache",
             ".claude-worktrees", ".idea", ".vscode"}

# import 이름 → 배포 이름. 다르면 여기 적는다(없으면 이름을 그대로 쓴다).
DIST_NAME = {
    "fitz": "pymupdf",
    "PIL": "pillow",
    "cv2": "opencv-python-headless",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "dateutil": "python-dateutil",
    "pdfminer": "pdfminer.six",
    "svgelements": "svgelements",
    "fontTools": "fonttools",
    "whisper": "openai-whisper",
}

# 기계가 못 찾는 의존 — **사유를 반드시 적는다.**
EXTRA_REQUIRES = [
    ("fonttools[woff]",
     "woff2 서브셋(`tools/font_subset.py`)이 brotli·zopfli 를 쓴다 — extra 라 import 에 안 보인다"),
]

# 요구 인터프리터. 공용 폴더 표의 ⑶ — **버전을 파일에 적는 것이 이 매니페스트의 요점 중 하나다.**
PYTHON_REQUIRES = ">=3.10"
PYTHON_NOTE = ("이 PC 는 3.14 로 돌린다(`AppData/Local/Python/pythoncore-3.14-64`). "
               "하한 3.10 은 **잰 값이다** — `sys.stdlib_module_names`(3.10 신설)를 "
               "`tools/audit_deps.py` 가 쓴다. `tomllib`(3.11)는 이 리포에 쓰는 자리가 없다.")


def _iter_py():
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            if n.endswith(".py"):
                yield os.path.join(base, n)


def _local_names():
    """리포 안에 있는 모듈·패키지 이름 — 서드파티로 세면 안 된다."""
    out = set()
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            if n.endswith(".py"):
                out.add(n[:-3])
        for d in dirs:
            if os.path.exists(os.path.join(base, d, "__init__.py")):
                out.add(d)
    return out


def scan():
    """{배포이름: {쓰는 파일 상대경로}}"""
    local, std = _local_names(), set(sys.stdlib_module_names)
    used = {}
    for path in _iter_py():
        try:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
        except (OSError, SyntaxError, ValueError):
            continue
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                heads = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:                       # 상대 import 는 늘 우리 것이다
                    continue
                heads = [(node.module or "").split(".")[0]]
            else:
                continue
            for head in heads:
                if not head or head in std or head in local or head == "__future__":
                    continue
                used.setdefault(DIST_NAME.get(head, head), set()).add(rel)
    return used


def render(used):
    lines = [
        "# 전공정리프로젝트 — 파이썬 의존 매니페스트",
        "#",
        "# ★ 손으로 고치지 말 것 — `python tools/audit_deps.py --write` 가 만든다.",
        "#   서드파티 목록은 리포의 모든 `.py` 를 ast 로 훑어 뽑는다(그 도구 독스트링 참조).",
        "#",
        "# 열린 날 2026-09-08 — 공용 폴더 `변경일지.md` 「requirements.txt 를 각 리포가 세울 것」.",
        "#   여덟 프로젝트가 파이썬 하나를 공유하는데 어느 코드가 무엇을 요구하는지",
        "#   적힌 파일이 어디에도 없었다.",
        "#",
        "# 요구 인터프리터: python " + PYTHON_REQUIRES,
        "#   " + PYTHON_NOTE,
        "#",
        "# ☐ 이 파일이 안 적는 것: 외부 실행파일(브라우저 — `render_figure_review.py` 가",
        "#   Edge·Chrome 을 헤드리스로 부른다 · `vercel` CLI — 배포에만).",
        "",
    ]
    # extra 로 다시 적는 것은 여기서 뺀다 — `fonttools` 와 `fonttools[woff]` 를 둘 다
    # 적으면 뒤엣것이 앞엣것을 덮어 **읽는 사람만 헷갈린다**(pip 은 둘 다 받아들인다).
    covered = {n.split("[", 1)[0] for n, _why in EXTRA_REQUIRES}
    for name in sorted(used, key=str.lower):
        if name in covered:
            continue
        where = sorted(used[name])
        head = where[0] + (" 외 %d곳" % (len(where) - 1) if len(where) > 1 else "")
        lines.append("%-28s # %s" % (name, head))
    if EXTRA_REQUIRES:
        lines += ["", "# --- import 스캔에 안 잡히는 것 (extra 의존) ---"]
        for name, why in EXTRA_REQUIRES:
            lines.append("%-28s # %s" % (name, why))
    return "\n".join(lines) + "\n"


def main():
    used = scan()
    text = render(used)
    if "--write" in sys.argv:
        with open(REQ_PATH, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print("requirements.txt 를 다시 썼다 — 서드파티 %d개" % len(used))
        return
    if "--check" in sys.argv:
        try:
            with open(REQ_PATH, encoding="utf-8") as fh:
                cur = fh.read()
        except OSError:
            sys.exit("requirements.txt 가 없다 — `python tools/audit_deps.py --write`")
        if cur.replace("\r\n", "\n") != text:
            sys.exit("requirements.txt 가 실제 import 와 어긋난다 —"
                     " `python tools/audit_deps.py --write` 로 맞출 것")
        print("requirements.txt 가 실제 import 와 일치한다 — 서드파티 %d개" % len(used))
        return
    print("서드파티 의존 %d개 (스캔 대상 `.py` 를 ast 로 훑었다)\n" % len(used))
    for name in sorted(used, key=str.lower):
        where = sorted(used[name])
        print("  %-28s %s" % (name, where[0]
                              + (" 외 %d곳" % (len(where) - 1) if len(where) > 1 else "")))
    if not used:
        sys.exit("서드파티가 0개다 — 순회 범위를 확인할 것(0 이 «없다» 가 아니다)")


if __name__ == "__main__":
    main()
