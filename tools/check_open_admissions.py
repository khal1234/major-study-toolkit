# -*- coding: utf-8 -*-
"""코드 주석·독스트링의 「찾았는데 안 고쳤다」 자백을 세는 래칫 (공용 폴더 `도구/check_open_admissions.py` 이식 2026-09-11).

    python tools/check_open_admissions.py            # 새 자백이 있으면 exit 1
    python tools/check_open_admissions.py --show     # 지금 잡히는 것 전부
    python tools/check_open_admissions.py --seed     # 지금 것을 한 번 소급 면제(빚)
    python tools/check_open_admissions.py --selftest

재는 것: `tools/`·`tools/buildlib/`·`.claude/hooks/` 의 `.py` 주석·독스트링에서 종결형 자백
(아직 없다 · 아직 못 …다 · TODO/FIXME/미구현 · 손으로 …해야 · 다음 세션에/나중에 …하자).
문턱: 씨앗(`docs/open-admissions-seed.txt`)에도 사유 있는 면제(`docs/open-admissions-allow.txt`)에도
없는 것이 1건이라도 있으면 막는다. 면제 사유는 보류 넷(다른 리포 소관 · 기능 요청 · 사람 판단 대기 · 기각됨)뿐.
못 보는 것: 문자열 리터럴·`print` 안(사용자에게 하는 말) · `.md`(연대기라 `verify_workorder` 몫) ·
인용부호 안 · 관형형(「아직 안 읽은 것」) · 다른 말투로 쓴 자백.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "docs" / "open-admissions-seed.txt"
ALLOW = REPO / "docs" / "open-admissions-allow.txt"
SCAN = (REPO / "tools", REPO / "tools" / "buildlib", REPO / ".claude" / "hooks")

# 인용부호 안은 남의 말이라 뺀다(공용 폴더 첫 실행이 사용자 발화 인용을 오탐했다).
# 백틱 코드와 홑따옴표도 낱말의 언급이라 뺀다(이식 첫 실행: `미구현`·'아직 없다' 오탐).
QUOTED = re.compile(r'«[^»]*»|\*"[^"]*"\*|"[^"]*"|‘[^’]*’|“[^”]*”|`[^`]*`|\'[^\']*\'')
DOC_DELIM = re.compile(r'"""|\'\'\'')

# 종결형만 본다 — 관형형(「아직 못 본 것」)은 기능 설명이라 공용 폴더 첫 판에서 오탐 밭이었다.
PATTERNS = (
    ("아직없다", re.compile(r"아직\s*없다")),
    ("아직못", re.compile(r"아직\s*못\s*\S*(?:다|한다|된다)[\.\s»*]")),
    ("TODO", re.compile(r"\bTODO\b|\bFIXME\b|미구현")),
    ("손으로", re.compile(r"(?:손으로|사람이\s*손으로)\s*\S*\s*해야")),
    ("나중에", re.compile(r"다음\s*세션에\s*\S*\s*(?:필요|하자|한다)|나중에\s*\S+하자")),
)
# 긍정 서술(「새어나간 것: 아직 없다」)은 자백이 아니다.
NOT_ADMISSION = re.compile(r"새어나간\s*것\s*[:：]|없는\s*것과는\s*다르")


def strip_quotes(ln, in_quote):
    """인용부호 안을 지운 줄과, 줄 끝에서 인용이 열려 있는지(여러 줄 인용)."""
    if in_quote:
        m = re.search(r'»|"\*|"|’|”', ln)
        if not m:
            return " ", True
        return " " + QUOTED.sub(" ", ln[m.end():]), False
    bare = QUOTED.sub(" ", ln)
    opened = re.search(r'«|\*"|"|‘|“', bare)
    if opened:
        return bare[:opened.start()], True
    return bare, False


def comment_lines(src):
    """주석·독스트링 줄만 [(줄번호, 줄)]. 깨진 파일에서도 돌게 토크나이저 대신 줄 단위."""
    out, in_doc, doc_q = [], False, ""
    for i, ln in enumerate(src.splitlines(), 1):
        st = ln.strip()
        if in_doc:
            out.append((i, ln))
            if doc_q in ln:
                in_doc = False
            continue
        m = re.match(r'^(?:[rubf]*)("""|\'\'\')', st)
        if m:
            doc_q = m.group(1)
            out.append((i, ln))
            if doc_q not in st[m.end():]:
                in_doc = True
            continue
        if st.startswith("#"):
            out.append((i, ln))
    return out


def admissions(src):
    """[(줄번호, 갈래, 줄)] — 한 파일 소스 안의 자백. 순수 함수."""
    hits, in_quote = [], False
    for lineno, ln in comment_lines(src):
        bare, in_quote = strip_quotes(DOC_DELIM.sub(" ", ln), in_quote)
        if NOT_ADMISSION.search(bare):
            continue
        for kind, rx in PATTERNS:
            if rx.search(bare):
                hits.append((lineno, kind, ln.strip()[:150]))
                break
    return hits


def scan():
    """[(파일, 줄번호, 갈래, 줄)]."""
    hits = []
    for base in SCAN:
        if not base.is_dir():
            continue
        for p in sorted(base.glob("*.py")):
            if p.name == "check_open_admissions.py":
                continue
            try:
                src = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = p.relative_to(REPO).as_posix()
            hits.extend((rel,) + h for h in admissions(src))
    return hits


def key(h):
    """열쇠 = 파일 + 줄 앞 60자. 줄 번호는 밀리면 씨앗이 되살아나 안 쓴다."""
    return "%s | %s" % (h[0], h[3][:60])


def parse_seed(lines):
    return {ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")}


def parse_allow(lines):
    """`<파일> | <앞머리> | <사유>` — 사유 칸이 빈 줄은 면제로 안 친다."""
    out = set()
    for ln in lines:
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        parts = [x.strip() for x in ln.split("|")]
        if len(parts) >= 3 and all(parts[:3]):
            out.add("%s | %s" % (parts[0], parts[1][:60]))
    return out


def _read(p):
    return list(io.open(p, encoding="utf-8-sig")) if p.is_file() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    hits = scan()
    if a.seed:
        keys = sorted({key(h) for h in hits})
        SEED.write_text("# 2026-09-11 소급 면제 — 빚이다. 그 자리를 다시 만지면 고치고 줄을 지운다.\n"
                        + "".join(k + "\n" for k in keys), encoding="utf-8")
        print("씨앗 %d줄 -> %s" % (len(keys), SEED.relative_to(REPO).as_posix()))
        return 0

    seeded, ok = parse_seed(_read(SEED)), parse_allow(_read(ALLOW))
    new = [h for h in hits if key(h) not in seeded and key(h) not in ok]
    if a.show:
        for h in sorted(hits):
            mark = "씨앗" if key(h) in seeded else "면제" if key(h) in ok else "새것"
            print("  %-4s %s:%d  %s" % (mark, h[0], h[1], h[3][:90]))
    print("주석·독스트링 자백 %d건 (훑은 파일 %d개 · 씨앗 %d · 면제 %d · 새것 %d)"
          % (len(hits), sum(len(list(b.glob("*.py"))) for b in SCAN if b.is_dir()),
             len(seeded), len(ok), len(new)))
    if not new:
        print("OK   새로 생긴 자백 없음")
        return 0
    print("FAIL 새 자백 %d건 — 찾았으면 고친다. 못 고치면 `docs/open-admissions-allow.txt` 에 사유와 함께:" % len(new))
    for h in new[:12]:
        print("   %s:%d  %s" % (h[0], h[1], h[3][:100]))
    print("   <파일> | <줄 앞머리> | <사유: 다른 리포 소관 / 기능 요청 / 사람 판단 대기 / 기각됨>")
    return 1


def selftest():
    bad = 0

    def check(name, ok, got=""):
        nonlocal bad
        print("  %s %s%s" % ("OK  " if ok else "FAIL", name, "" if ok else "  <- %r" % (got,)))
        bad += 0 if ok else 1

    src = "\n".join([
        '# 대조하는 자는 아직 없다.',
        'x = 1',
        'def f():',
        '    """독스트링인데 TODO 가 있다."""',
        '    print("기록이 아직 없다: %s" % p)',
        '    s = "미구현"',
        '# 사용자: *[발화 생략]* 라 했다',
        '# 새어나간 것: 아직 없다',
        '# 아직 안 읽은 것만 본다',
        "# 미완을 뜻하는 말은 `미구현` 이다 · '아직 없다' 문구",
    ])
    got = [n for n, _k, _l in admissions(src)]
    check("양성 — 주석·독스트링의 종결형 자백만 잡는다(1·4행)", got == [1, 4], got)
    check("음성 — print·문자열·인용·긍정·관형형·백틱은 안 잡는다", not set(got) & {5, 6, 7, 8, 9, 10}, got)
    check("사유 있는 줄만 면제로 친다",
          parse_allow(["a.py | 아직 없다 | 사람 판단 대기\n", "b.py | 아직 없다\n"]) == {"a.py | 아직 없다"})
    n = len(scan())
    check("분모 — 실제 리포에서 하나 이상 잡는다(0이면 자가 눈이 멀었다)", n > 0, n)
    print("%s   %d problem(s)." % ("FAIL" if bad else "OK  ", bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
