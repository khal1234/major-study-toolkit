# -*- coding: utf-8 -*-
"""**아무도 안 부르는 검사·아무도 안 돌리는 도구**를 찾아낸다 — 읽기 전용.

    python tools/audit_orphan_checks.py
    python tools/audit_orphan_checks.py --fail-only

왜 있나 — 「close 의 정의」에 한 칸이 비어 있었다
------------------------------------------------
이 리포는 *[발화 생략]* 를 규율로 갖고 있고
(`AGENTS.md` 「close 의 정의」), `test_checks.py` 가 **검사가 결함을 잡는지**를 잠근다.
그런데 **그 검사가 실제로 호출되는지**는 아무도 안 봤다.

buildlib 에 `def ..._issues()` 를 써 놓고 `lint_chapter` 나 `build_site` 의 목록에
**배선하는 것을 빠뜨리면** 빌드는 초록이고 회귀도 통과한다 — 그 검사만 조용히 안 돈다.
`tools/` 의 감사·처방 도구도 같다: 만들 때 한 번 돌리고 어디에도 등록하지 않으면
다음 세션이 그 도구가 있다는 것조차 모른다. 다음 세션은 `AGENTS.md` 를 읽지 `tools/` 를
훑지 않기 때문이다 — 그래서 **이미 있는 도구를 안 읽고 새로 만드는** 낭비가 반복됐다.

**발상의 출처는 XSanity 개조 프로젝트다**(`_modding/scripts/check_orphan_checks.py`, 2026-08-08).
거기서 열린 지적: *[발화 생략]*

★ **원본의 구멍은 고쳐서 가져왔다.** 원본은 등록처 텍스트에 **검사 자신의 파일**을 넣고
`count >= 2` 로 판정해서, 독스트링에 사용법을 두 줄 적은 검사가 **자기 이름만으로 통과**했다
(실측: `check_song_paths.py` 가 어느 러너에도 없는데 OK 였다). 여기서는
**자기 정의·자기 파일을 등록처에서 뺀 뒤 1건 이상**을 요구한다.
잠금: `test_checks.py::test_orphan_check_audit_sees_its_own_blind_spot`.

무엇을 보나
-----------
⑴ **검사 함수** — `tools/buildlib/*.py` 의 `def *_issues|*_hits|lint_*`.
   자기 `def` 줄을 뺀 뒤 `tools/**` 어디에서도 이름이 안 나오면 **호출자 없음**.
⑵ **도구 파일** — `tools/*.py`. 자기 파일을 뺀 뒤 `AGENTS.md`·`CLAUDE.md`·`docs/**`·
   **`data/*/index.json`**·다른 `tools/**` 어디에도 이름이 없으면 **아무도 안 부른다**.
   `index.json` 을 보는 이유: 과목이 도구를 **선언**으로 등록하는 자리가 있다
   (`answerVerifier`). 그 선언을 안 보면 정상 등록을 orphan 으로 오보한다.

빠져나가는 법은 둘뿐이다 — **배선·등록하거나, 지우거나.**
의도적으로 남기는 것은 `docs/orphan-checks-allow.txt` 에 **사유와 함께** 적는다
(사유 없는 예외가 쌓이면 이 감사는 장식이 된다).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def _pick(*names):
    """이름이 여럿인 자리에서 **있는 것**을 고른다. 없으면 첫 이름(있다고 치고 빈 결과)."""
    for n in names:
        if (ROOT / n).is_dir():
            return ROOT / n
    return ROOT / names[0]


# ★★ **자리를 박아 두었더니 아무것도 안 훑고 「OK: 0 problems」 를 냈다** (2026-08-16).
#   `TOOLS = ROOT/"tools"` 는 전공정리 배치이고 공용 폴더는 `도구/` 다. 공용 폴더에서 이 자는
#   **도구 0개·검사 0개를 훑고 초록**이었다 — 「빈손인데 초록」은 이 계통이 가장 경계하는
#   모양이다(*[발화 생략]*, 규칙 11).
#   ★ 오늘 같은 부류 **네 번째**다: `check_narration`(ROOT.parent) · `feedback_lookup`
#     (ROOT/기록) · `commit.py`(.claude/hooks·tools) · 그리고 이것.
TOOLS = _pick("도구", "tools")
BUILDLIB = _pick("도구/buildlib", "tools/buildlib")
DOCS = _pick("기록", "docs")
DATA = _pick("data")
ALLOW = DOCS / "orphan-checks-allow.txt"

# 검사 함수의 이름꼴. `_` 로 시작하는 내부 헬퍼도 대상이다 —
# 안 불리는 헬퍼는 죽은 코드이고, 그것도 알아야 한다.
CHECK_DEF = re.compile(r"^def (_?[a-z][a-z0-9_]*(?:_issues|_hits))\(", re.M)
LINT_DEF = re.compile(r"^def (lint_[a-z0-9_]+)\(", re.M)

TOOL_SKIP = {"__init__.py"}


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def allowed() -> dict[str, str]:
    """예외 목록 -> {이름: 사유}. **사유가 없는 줄은 예외로 치지 않는다.**"""
    out: dict[str, str] = {}
    for line in read(ALLOW).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, _, why = line.partition("#")
        name, why = name.strip(), why.strip()
        if name and why:
            out[name] = why
    return out


def python_sources() -> list[tuple[Path, str]]:
    return [(p, read(p)) for p in sorted(TOOLS.rglob("*.py"))
            if "__pycache__" not in p.parts]


def doc_sources() -> list[tuple[Path, str]]:
    """등록처가 될 수 있는 문서 — 규칙 문서 + 과목의 선언 파일."""
    # ★ 등록처의 **이름도 프로젝트마다 다르다** (2026-08-16). 전공정리는 `AGENTS.md` +
    #   `docs/` 이고 공용 폴더는 `README.md` + `규칙/` 이다. 자리만 고치고 이 목록을 안 고쳤더니
    #   **README 에 두 줄로 등록돼 있는 `audit_path_names.py` 가 고아로 신고됐다** —
    #   빈손 초록의 반대편, 즉 **거짓 빨강**이다. 둘 다 「범위를 안 보고 낸 판정」이다.
    paths = [ROOT / "AGENTS.md", ROOT / "CLAUDE.md", ROOT / "README.md"]
    paths += sorted(DOCS.rglob("*.md")) if DOCS.is_dir() else []
    for extra in ("규칙", "docs"):
        d = ROOT / extra
        if d.is_dir() and d != DOCS:
            paths += sorted(d.rglob("*.md"))
    # 경로 규칙·스킬도 등록처다(2026-09-11 AGENTS 이관) — 안 훑으면 옮긴 절이 가리키던 도구가 거짓 고아가 된다
    claude = ROOT / ".claude"
    for sub, pat in (("rules", "*.md"), ("skills", "SKILL.md")):
        if (claude / sub).is_dir():
            paths += sorted((claude / sub).rglob(pat))
    # 과목 이름을 박지 않는다 — 폴더를 훑어 그 과목이 스스로 선언한 것을 읽는다
    paths += sorted(DATA.glob("*/index.json")) if DATA.is_dir() else []
    return [(p, read(p)) for p in paths if p.is_file()]


def orphan_functions(sources):
    """검사 함수 중 자기 def 줄 말고는 어디에도 안 나오는 것."""
    defined: dict[str, Path] = {}
    for path, text in sources:
        if path.parent != BUILDLIB:
            continue
        for pat in (CHECK_DEF, LINT_DEF):
            for name in pat.findall(text):
                defined.setdefault(name, path)

    rows = []
    for name, home in sorted(defined.items()):
        used = 0
        for path, text in sources:
            body = text
            if path == home:
                # 자기 정의 줄만 뺀다 — 같은 모듈 안의 호출(lint_chapter 등)은 정당한 배선이다
                body = re.sub(r"^def %s\(" % re.escape(name), "", body, count=1, flags=re.M)
            used += len(re.findall(r"\b%s\b" % re.escape(name), body))
        if used == 0:
            rows.append((name, home.name))
    return len(defined), rows


def orphan_tools(sources, docs, tools=None):
    """도구 파일 중 자기 파일 밖에서 이름이 한 번도 안 나오는 것.

    `tools` 를 주면 그 목록만 본다(테스트가 가짜 목록을 넘긴다).

    ★ NEW-NARU-002 (Codex 스테이지9 §3) — **「등록됐나」와 「배선됐나」는 다른 물음이다.**
      이 자의 목적은 등록부(AGENTS·CLAUDE·docs·`index.json`) 존재 확인이지 실행 배선
      확인이 아니다(그 물음은 `audit_gates.judge()` 가 이미 「부르는 자」로 따로 답한다).
      완전히 같은 기준을 적용하면 두 자가 같은 질문에 다르게 답할 소지가 생긴다 — 그래서
      **판정(등록됨/orphan)은 그대로 두고**, 문서에만 언급되고 다른 `.py` 에서는 한 번도
      안 불린 것만 **셋째 축(`doc_only_rows`)으로 따로** 낸다. FAIL 로 올리지 않는다 —
      그건 이 자의 목적이 아니라서다.
    """
    if tools is None:
        tools = [p for p in sorted(TOOLS.glob("*.py")) if p.name not in TOOL_SKIP]
    rows, doc_only_rows = [], []
    for tool in tools:
        stem = tool.stem
        py_used = 0
        for path, text in sources:
            if path == tool:
                continue                      # ★ 자기 파일의 사용법 언급은 등록이 아니다
            py_used += len(re.findall(r"\b%s\b" % re.escape(stem), text))
        doc_used = 0
        for _path, text in docs:
            doc_used += len(re.findall(r"\b%s\b" % re.escape(stem), text))
        if py_used + doc_used == 0:
            rows.append((tool.name, "AGENTS·CLAUDE·docs·index.json·다른 도구 어디에도 없음"))
        elif py_used == 0:
            doc_only_rows.append((tool.name, "문서에만 언급 — 다른 .py 에서 부르는 곳은 0곳"))
    return len(tools), rows, doc_only_rows


def selftest() -> int:
    bad = 0

    def chk(desc, cond, got=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %-50s %s" % ("OK  " if cond else "**틀림**", desc, got))

    home = BUILDLIB / "checks.py"
    sources = [
        (home, "def foo_issues(x):\n    return []\n\ndef _bar_issues(x):\n    return []\n"),
        (TOOLS / "caller.py", "from checks import foo_issues\nfoo_issues(1)\n"),
    ]
    n, rows = orphan_functions(sources)
    chk("호출자가 있는 함수는 안 잡힌다(foo_issues)",
        all(r[0] != "foo_issues" for r in rows), str(rows))
    chk("호출자가 없는 함수는 잡힌다(_bar_issues)",
        any(r[0] == "_bar_issues" for r in rows), str(rows))
    chk("정의 총수를 센다", n == 2, "n=%d" % n)

    tool_a = TOOLS / "used_tool.py"
    tool_b = TOOLS / "orphan_tool.py"
    tsources = [(tool_a, "print(1)"), (tool_b, "print(2)")]
    docs = [(ROOT / "AGENTS.md", "used_tool 을 쓴다")]
    nt, trows, doc_only = orphan_tools(tsources, docs, tools=[tool_a, tool_b])
    chk("문서에 이름이 있으면 orphan 이 아니다(used_tool)",
        all(r[0] != "used_tool.py" for r in trows), str(trows))
    chk("문서 어디에도 없으면 orphan 이다(orphan_tool)",
        any(r[0] == "orphan_tool.py" for r in trows), str(trows))
    chk("대상 도구 수를 센다", nt == 2, "n=%d" % nt)
    # ★ NEW-NARU-002 — 문서에만 언급되고 .py 에서 안 불린 것은 orphan 이 아니라
    #   「문서 전용」 셋째 축으로 따로 잡힌다(used_tool 이 그 사례 — caller.py 가 없다).
    chk("문서에만 언급된 것은 doc_only 로 잡힌다(used_tool)",
        any(r[0] == "used_tool.py" for r in doc_only), str(doc_only))

    # ★ 08-30 이 자를 짓다 확인 — 이 자의 자기 파일(__file__)을 도구 목록에 넣으면
    #   원본 결함(자기 이름만으로 통과)이 재현되는지도 확인해 둔다.
    self_path = Path(__file__).resolve()
    self_sources = [(self_path, read(self_path))]
    _, self_rows, _ = orphan_tools(self_sources, [], tools=[self_path])
    chk("★ 자기 파일 하나만 있고 등록처가 없으면 orphan 으로 잡힌다(원본 구멍 회귀 확인)",
        any(r[0] == self_path.name for r in self_rows), str(self_rows))

    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        return selftest()
    ap = argparse.ArgumentParser(description="아무도 안 부르는 검사·도구 감사 (읽기 전용)")
    ap.add_argument("--fail-only", action="store_true", help="문제만 출력")
    args = ap.parse_args()

    sources = python_sources()
    docs = doc_sources()
    skip = allowed()

    n_fn, fn_rows = orphan_functions(sources)
    n_tool, tool_rows, doc_only_rows = orphan_tools(sources, docs)

    fn_rows = [r for r in fn_rows if r[0] not in skip]
    tool_rows = [r for r in tool_rows if r[0] not in skip]
    doc_only_rows = [r for r in doc_only_rows if r[0] not in skip]

    if not args.fail_only:
        print("순회 범위: tools/**/*.py %d개 · 문서·선언 %d개 · 예외 %d개 (%s)"
              % (len(sources), len(docs), len(skip), ALLOW.relative_to(ROOT).as_posix()))
        print("  검사 함수 %d개 · 도구 파일 %d개" % (n_fn, n_tool))

    if fn_rows:
        print("\n[FAIL] 호출자 없는 검사 함수 %d개 — 정의만 있고 아무 데서도 안 부른다:" % len(fn_rows))
        for name, home in fn_rows:
            print("       %-42s %s" % (name, home))
        print("       -> 빌드·lint_chapter 에 배선하거나, 안 쓰면 지울 것")

    if tool_rows:
        print("\n[FAIL] 아무도 안 부르는 도구 %d개:" % len(tool_rows))
        for name, why in tool_rows:
            print("       %-42s %s" % (name, why))
        print("       -> AGENTS.md 「도구 등록부」·close_report 에 등록하거나, 안 쓰면 지울 것")
        print("          의도적으로 남긴다면 %s 에 `이름  # 사유` 로 적을 것"
              % ALLOW.relative_to(ROOT).as_posix())

    # ★ NEW-NARU-002 — 「문서에만 언급됨」은 이 자의 판정(등록됨/orphan)을 바꾸지 않는다.
    #   **막지 않는다** — `--fail-only` 는 문제만 보여준다는 계약이라 그때는 낸다.
    if doc_only_rows and not args.fail_only:
        print("\n[참고] 문서에만 등록되고 실행 배선(.py 호출)은 없는 도구 %d개:"
              % len(doc_only_rows))
        for name, why in doc_only_rows:
            print("       %-42s %s" % (name, why))
        print("       -> 「등록됐나」는 여기서 통과다. 「실제로 부르는 코드가 있나」는 "
              "`audit_gates.py` 의 몫이다(게이트로 선언돼 있다면).")

    bad = len(fn_rows) + len(tool_rows)
    print("\n%s: %d problem(s)." % ("FAIL" if bad else "OK", bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
