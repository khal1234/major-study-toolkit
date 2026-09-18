#!/usr/bin/env python
"""새 과목(= git 브랜치 + worktree)을 세운다 — 등록 누락을 사람이 기억하지 않게.

**왜 도구인가.** 신규 과목 등록은 손으로 **4곳 + 과목 파일**이었고, 그중 하나를 빠뜨리면
증상이 조용하다:

  - `guard_bash.SUBJECT_BY_BRANCH` 누락 → `foreign_subject_paths()` 가 `mine is None` 에서
    **빈 목록**을 돌려준다. 즉 **과목 경계 강제가 통째로 꺼진 채** 아무 경고 없이 작업이 된다
    (2026-07-25 정책이 그 브랜치에서만 무효가 된다).
  - `SUBJECT_CONFIG` 누락 → 빌드가 `[skip] subject not in SUBJECT_CONFIG` 만 찍고 넘어간다.
  - `serve_site.vbs` 포트 누락 → 8800 으로 떨어져 다른 과목과 포트를 다툰다.
  - `.gitignore` 누락 → 빌드 산출물이 커밋에 섞인다. **실제로 난 적 있다** —
    `.claude/SUBJECT.md` 에 *[발화 생략]* 로
    사후 조치가 남아 있다.

사용자 요구(2026-07-28): *[발화 생략]*

**두 단계로 나눈 이유.** ⑴의 등록은 **공통 파일**이라 main 에 반영돼야 새 워크트리가 그것을
들고 태어난다. 그래서 `register` → `sync_common` → `worktree` 순서가 강제된다.

    python tools/new_subject.py register --subject 동역학 --branch dynamics --port 8803 \
        --cover-sub "Hibbeler 15판 (SI) 기준."
    python tools/sync_common.py
    python tools/new_subject.py worktree --subject 동역학 --branch dynamics \
        --chapters <스크래치패드/chapters.json>

`register` 는 **멱등**이다 — 이미 있으면 건드리지 않는다. 등록이 맞물렸는지는
`tools/test_checks.py::test_subject_registration_is_complete` 가 매번 검사한다.
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, ".claude", "hooks", "guard_bash.py")
BUILD = os.path.join(ROOT, "tools", "build_site.py")
SERVE = os.path.join(ROOT, "tools", "serve_site.vbs")
IGNORE = os.path.join(ROOT, ".gitignore")
# ★ 5번째 지점. 처음 이 도구를 짤 때 **내가 빠뜨렸고**, 기존 회귀
# `test_local_server_ports`("런처와 설치 스크립트의 포트 맵이 일치한다")가 잡았다.
# 등록 지점을 사람이 세는 한 또 빠진다는 증거라 여기 목록으로 고정한다.
STARTUP = os.path.join(ROOT, "tools", "install_startup.ps1")
TEXTUTIL = os.path.join(ROOT, "tools", "buildlib", "textutil.py")
# ★ 교재 폴더 읽기 권한은 **워크트리 단계**에서 등록한다 (2026-07-28 재번복 — 원장 17).
#
# 이 자리에는 한때 *[발화 생략]* 고 적혀 있었다. 근거는 원장 14-b 가
# `additionalDirectories` 에 상위 `2. 전공과목` 을 통째로 올려 *[발화 생략]* 는
# 것이었다. **그 전제가 틀렸다.** math 세션에서 7건을 실측해 갈랐다(원장 17):
#
#   · `.claude/settings.json`(project) 의 항목 → **그 폴더 하나만** 열린다. 하위는 안 열린다.
#     (`2. 전공과목` 은 조용한데 그 자식 `2-1` 은 승인창이 떴다.)
#   · `.claude/settings.local.json`(워크트리 전용) 의 항목 → **하위 트리까지** 열린다.
#     (`5. 공학수학` 도, 그 자식 `수업 ppt` 도 조용하다.)
#
# 즉 14-b 는 **일하던 좁은 항목 4개를 지우고 아무 하위도 못 여는 항목 1개로 바꾼 것**이었고,
# math 만 무사했던 이유는 그 워크트리의 local 에 `5. 공학수학` 이 남아 있어서였다.
# 그래서 등록 지점은 project 가 아니라 **새 워크트리의 local** 이다 — 과목마다 다른 값이고
# 워크트리 밖으로 나갈 이유가 없으므로 "두 곳이 갈라진다" 문제도 생기지 않는다.
# 잠금장치: `test_checks.py::test_textbook_dir_reaches_new_worktree`.
LOCAL_SETTINGS = os.path.join(".claude", "settings.local.json")
TEMPLATE = os.path.join(ROOT, ".claude", "SUBJECT.md.template")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _git(args):
    return subprocess.run(["git", "-C", ROOT] + args, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


# ── 물려받은 남의 과목 데이터 내리기 ────────────────────────────────────────
# 열린 날 2026-07-28 (dynamics 개설). **경고만 하고 지우지 못하는 상태가 교착이었다.**
#   ⑴ main 이 분리 이전 잔재로 data/열역학 을 들고 있어 새 워크트리가 통째로 상속한다.
#   ⑵ 그 사본은 그 과목 브랜치보다 낡아 **오늘 규칙으로 빌드가 죽는다**(dynamics 실측: ch01 lint 22 errors).
#   ⑶ 그런데 지우려 하면 과목 경계 가드가 막는다 — `commit.py "probe" data/열역학` → exit 2.
# 즉 도구는 "지워라"라고 하고 가드는 "못 지운다"고 해서 새 과목이 열릴 때마다 갇힌다.
# 같은 날 materials·solids 가 등록됐으므로 **재발이 예정돼 있었다.**
#
# 그래서 우회가 아니라 **좁고 검증된 정규 경로**를 만든다. 이 명령이 지울 수 있는 것은
#   · data/ 아래에서 **등록된 다른 과목**인 폴더뿐이고(모르는 폴더는 손대지 않는다),
#   · **그 파일이 다른 ref(그 과목 브랜치 또는 main)에 그대로 있을 때만**이다 — 소실이면 거부한다.
# 판정은 아래 두 순수 함수에 있고 `test_checks.py::test_drop_inherited_gate` 가 잠근다.

def inherited_subject_dirs(mine, names, known):
    """data/ 아래 폴더 중 **등록된 다른 과목**인 것. 모르는 이름은 돌려주지 않는다.

    과목 이름은 접두어다(SUBJECT_BY_BRANCH 의 '공학수학' ↔ 폴더 '공학수학 1') —
    등록 검사(test_subject_registration_is_complete)와 같은 규약을 쓴다.
    """
    others = [s for s in known if s != mine]
    return [n for n in names
            if not n.startswith(mine) and any(n.startswith(o) for o in others)]


def unsafe_drops(paths, elsewhere):
    """지우면 **소실**되는 경로(다른 ref 에 사본이 없는 것). 하나라도 있으면 지우지 않는다."""
    have = set(elsewhere)
    return [p for p in paths if p not in have]


# ── 등록 4곳 ────────────────────────────────────────────────────────────────
# 각 함수는 (바뀐 텍스트, 바꿨는가) 를 돌려준다. **순수 함수라 테스트가 직접 부른다.**

def add_guard_mapping(src, branch, subject):
    if '"' + branch + '"' in src:
        return src, False
    pat = r'(SUBJECT_BY_BRANCH = \{[^}]*)\}'
    new = re.sub(pat, lambda m: m.group(1) + ', "' + branch + '": "' + subject + '"}', src, count=1)
    return new, new != src


def add_build_config(src, subject, cover_sub):
    if '"' + subject + '"' in src:
        return src, False
    marker = '\n}\n'
    idx = src.find('SUBJECT_CONFIG = {')
    if idx < 0:
        return src, False
    end = src.find(marker, idx)
    if end < 0:
        return src, False
    entry = ('    "' + subject + '": {\n'
             '        "coverSub": "' + cover_sub + '",\n'
             '    },')
    new = src[:end] + '\n' + entry + src[end:]
    return new, True


def add_pitfall_book(src, subject, book):
    """`PITFALL_BOOK_BY_SUBJECT` 에 그 과목의 **1차 근거 접두어**를 등록한다(순수 함수).

    ★ 왜 늘었나 (열린 날 2026-08-15). 2-2 과목 일곱을 `register` 로 세웠더니 회귀가
      **7건 한꺼번에** 떴다 — *[발화 생략]*. 이 도구는
      «등록 누락을 사람이 기억하지 않게» 만든 것인데, 정작 **자기 목록에 이 자리가 없어서**
      새 과목마다 사람이 손으로 넣어야 했다. 빠뜨리면 그 과목은 규칙 2(출처 있는 pitfall)를
      **쓸 수 없다** — 빌드가 그 과목의 모든 pitfall 을 «출처 형식 위반» 으로 막는다.
    ★ 값을 기계가 정하지 않는다 — 저자 이름은 **보유 교재를 열어 확인한 사람**이 준다.
      교재가 없는 과목(강의노트로 정리하는 과목)은 `강의노트` 가 정당한 값이다.
    """
    if '"' + subject + '"' in src:
        return src, False
    idx = src.find("PITFALL_BOOK_BY_SUBJECT = {")
    if idx < 0:
        return src, False
    end = src.find("\n}\n", idx)
    if end < 0:
        return src, False
    entry = '    "' + subject + '": ("' + book + '",),'
    new = src[:end] + "\n" + entry + src[end:]
    return new, True


def add_serve_port(src, branch, port):
    if '"' + branch + '"' in src:
        return src, False
    anchor = '        Case Else'
    if anchor not in src:
        return src, False
    entry = '        Case "' + branch + '"\n            port = ' + str(port) + '\n'
    new = src.replace(anchor, entry + anchor, 1)
    return new, True


def add_gitignore(src, subject):
    line = '/site/' + subject + '/'
    if line in src:
        return src, False
    # 빌드 산출물 블록 뒤에 붙인다 — 다른 과목 줄 바로 아래.
    m = list(re.finditer(r'^/site/.+/$', src, re.M))
    if not m:
        return src + '\n' + line + '\n', True
    at = m[-1].end()
    return src[:at] + '\n' + line + src[at:], True


def add_startup_port(src, branch, port):
    """install_startup.ps1 의 포트 맵. serve_site.vbs 와 **표류하면 안 된다**.

    2026-07-28: 그 스크립트가 `switch`(표시용)에서 **`$PortMap` 해시테이블**로 바뀌었다
    — `-All` 이 그 맵을 돌면서 전 워크트리를 등록하기 때문이다. 여기 삽입 지점도 함께
    옮긴다. 옛 앵커(`default { 8800 }`)만 보고 있으면 **새 과목이 -All 대상에서 빠져**
    로그온 자동 실행이 조용히 안 걸린다(이 파일이 막으려는 바로 그 부류의 재발).
    """
    if "'" + branch + "'" in src:
        return src, False
    m = re.search(r"\$PortMap\s*=\s*@\{", src)
    if not m:
        return src, False
    return src[:m.end()] + " '" + branch + "' = " + str(port) + ";" + src[m.end():], True


def add_local_textbook_dir(src, textbook_dir):
    """워크트리 전용 `settings.local.json` 에 교재 폴더를 넣는다 (텍스트, 바꿨는가).

    **local 이어야 하는 이유는 위 LOCAL_SETTINGS 주석의 실측이다** — project 항목은
    그 폴더 하나만 열고 하위를 못 연다. 교재는 항상 하위(`교재 pdf/`·`수업 ppt/`)에 있다.

    빈 문자열도 받는다(새 워크트리엔 파일이 없다). 이미 같은 경로가 있으면 건드리지 않는다.
    """
    data = json.loads(src) if src.strip() else {}
    dirs = data.setdefault("permissions", {}).setdefault("additionalDirectories", [])
    want = os.path.normpath(textbook_dir)
    if any(os.path.normpath(str(d)) == want for d in dirs):
        return src, False
    dirs.append(want)
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n", True


# ── 개설 문답을 파일로 굳히기 ───────────────────────────────────────────────
# 열린 날 2026-07-28. **새어나간 것: 개설 세션의 문답 전체.**
# 사용자가 dynamics 를 만들면서 교재 폴더 경로·진도(12~15 중간/16~19 기말)·제외 범위
# (20·21 대학원, 22 3학년, 각 장 optional 절)·장별 요약 jpg 를 다 알려줬는데,
# 새 브랜치 세션은 **그중 하나도 못 받았다.** 사용자 지적: *[발화 생략]*
#
# **원인은 빠뜨림이 아니라 구조다.** 이 도구는 빈 템플릿을 복사하고
# *[발화 생략]* 고 안내했는데, 그 세션은 **아직 존재하지 않고
# 그 대화를 볼 방법이 없다.** 채팅에만 있는 사실은 100% 유실된다.
# → 개설 시점에 사실을 **인자로 받아 파일에 쓴다.** 없으면 워크트리를 만들지 않는다.

FACT_SECTIONS = (("## 범위 — 수업이 나가는 곳", "scope"),
                 ("## 제외 — 수업이 다루지 않는 곳", "excluded"),
                 ("## 수업 자료", "materials"),
                 ("## TODO — 아직 실측하지 못한 것", "todo"))


def as_items(value):
    """사실 항목을 **목록**으로 — 문자열은 한 항목이다 (순수 함수 — 테스트 대상).

    ★★ **실측으로 열렸다 (2026-08-15, mfg).** 예전에는 `[str(i) for i in (값 or [])]` 였는데
      **파이썬에서 문자열도 순회 가능**이라, 사실을 문자열로 하나 주면 그 글자 하나하나가
      항목이 됐다. 2-2 과목 일곱이 전부 그 상태로 개설됐다 —

          ## 범위 — 수업이 나가는 곳
          - T
          - O
          - D
          - O

      **예외가 안 나고 파일도 만들어지므로 개설은 «성공» 으로 끝난다.** 그 과목 세션이 열려
      SUBJECT.md 를 읽을 때까지 아무도 모른다(이 리포가 가장 비싸다고 적어 둔 «그럴듯하게
      틀린» 부류다).
    ★ 처방은 **기본값을 안전한 쪽으로** 뒤집는 것이다 — 문자열은 «한 항목», 목록은 그대로,
      그 외에는 문자열로 만들어 한 항목. 「문자열을 주지 말 것」 이라는 규율로 두면 다음에
      또 준다.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    try:
        return [str(i) for i in value]
    except TypeError:                          # 순회 불가 — 통째로 한 항목이다
        return [str(value)]


def render_subject_md(subject, branch, facts):
    """개설 문답을 SUBJECT.md 본문으로 굳힌다 (순수 함수 — 테스트가 직접 부른다).

    빠진 항목은 지우지 않고 **TODO 로 남긴다** — 없는 것이 눈에 보여야 채워진다.
    """
    f = facts or {}
    prof = (" 담당 " + f["professor"] + ".") if f.get("professor") else ""
    out = ["# SUBJECT.md — " + subject + " (" + branch + " 전용)", "",
           "> 과목 무관 규칙은 `CLAUDE.md` 에 있다. 여기에는 **이 과목의 사실**만 둔다.",
           "> main 에는 올리지 않는다 — `sync_common.py` 의 `NEVER_SYNC` 가 스테이징에서 뺀다.",
           "",
           "## 과목·교재",
           "- 과목: " + subject + "." + prof,
           "- 교재: " + (f.get("textbook") or "**TODO — 개설 시 안 받았다.**")]
    if f.get("textbookDir"):
        out += ["- 교재 폴더(읽기 전용): `" + f["textbookDir"] + "`",
                "  이 경로(또는 상위)가 settings `additionalDirectories` 에 있어야 읽을 수 있다."]
    else:
        out += ["- 교재 폴더(읽기 전용): **TODO** — settings `additionalDirectories` 에 등록할 것."]
    for title, key in FACT_SECTIONS:
        items = as_items(f.get(key))
        out += ["", title] + (["- " + i for i in items] if items
                              else ["- **TODO — 개설 시 안 받았다.**"])
    out += ["", "## 파일 배치 (과목 고유분)", "```",
            "data/" + subject + "/chNN.json , data/" + subject + "/*.workorder.md , "
            "site/" + subject + "/chNN.html", "```", "",
            "## 과목 특유 관례",
            "- 커밋 경로는 `data/" + subject + "`·`site/" + subject + "` 만(guard 가 강제). "
            "`git add -A` 금지.", ""]
    return "\n".join(out)


def cmd_register(args):
    steps = [
        (GUARD, lambda s: add_guard_mapping(s, args.branch, args.subject), "과목 경계(guard)"),
        (BUILD, lambda s: add_build_config(s, args.subject, args.cover_sub), "빌드 대상(SUBJECT_CONFIG)"),
        (SERVE, lambda s: add_serve_port(s, args.branch, args.port), "미리보기 포트"),
        (IGNORE, lambda s: add_gitignore(s, args.subject), "산출물 gitignore"),
        (STARTUP, lambda s: add_startup_port(s, args.branch, args.port), "로그온 자동실행 포트 맵"),
        # ★ 2026-08-15 추가 — 이 자리가 없어서 2-2 과목 일곱을 세우자 회귀가 7건 떴다.
        #   빠뜨리면 그 과목은 **출처 있는 pitfall 을 아예 못 쓴다**(빌드가 전부 막는다).
        (TEXTUTIL, lambda s: add_pitfall_book(s, args.subject, args.pitfall_book),
         "pitfall 1차 근거 접두어"),
    ]
    for path, fn, label in steps:
        text, changed = fn(_read(path))
        if changed:
            _write(path, text)
        print(("[+] " if changed else "[=] ") + label + " — " + os.path.relpath(path, ROOT)
              + ("" if changed else " (이미 있음)"))
    print("\n다음: python tools/sync_common.py   ← 등록은 공통이라 main 에 올려야 새 워크트리가 받는다")
    return 0


# ── 워크트리 + 과목 고유 파일 ───────────────────────────────────────────────

def cmd_worktree(args):
    if not args.facts:
        print("거부 — `--facts <json>` 이 필요하다.\n"
              "  개설 세션에서 확정한 사실(textbook·textbookDir·scope·excluded·materials·todo)을\n"
              "  **파일로** 넘겨야 새 브랜치가 그것을 들고 태어난다. 채팅에만 두면 그 브랜치의\n"
              "  새 세션은 그 대화를 볼 방법이 없어 100% 유실된다(2026-07-28 dynamics 실사고:\n"
              "  교재 폴더 경로·진도·optional 절 제외가 전부 새 세션에 전달되지 않았다).\n"
              "  모르는 항목은 넣지 마라 — 본문에 TODO 로 남는다. 빈 객체 `{}` 도 받는다.")
        return 2
    # ★ `utf-8-sig` 다 (열린 날 2026-08-15, 일곱 과목을 세우다 일곱 번 연속 죽었다).
    #   이 JSON 은 **바깥에서 들어오는 텍스트**다 — 사람이 메모장이나 PowerShell
    #   (`Set-Content -Encoding UTF8` 이 윈도우 5.1 에서 **BOM 을 단다**)로 만든다.
    #   `utf-8` 로 읽으면 첫 글자에서 `Unexpected UTF-8 BOM` 으로 죽는데, 그 메시지를 보고
    #   사람은 **자기 JSON 이 틀렸다고** 읽는다(내용은 멀쩡하다). 받는 쪽이 넓히는 것이 맞다 —
    #   AGENTS 「바깥에서 들어오는 텍스트는 무조건 UTF-8 로 명시해 읽는다」의 BOM 판이다.
    facts = json.load(open(args.facts, encoding="utf-8-sig"))
    # 폴더 이름은 «<한글표시>-<갈래>» 다 (2026-08-23) — 프로젝트를 고르는 화면에서
    # 과목이 읽혀야 한다. 규칙 정본은 tools/worktree_names.py.
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from worktree_names import folder_name                                # noqa: E402
    dest = args.path or os.path.join(os.path.dirname(ROOT),
                                     folder_name(args.branch, args.subject))
    if not os.path.isdir(dest):
        r = subprocess.run(["git", "worktree", "add", dest, "-b", args.branch, "main"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print("[FAIL] worktree add\n" + (r.stderr or "")[:400])
            return 1
        print("[+] worktree — " + dest)
    else:
        print("[=] worktree 이미 있음 — " + dest)

    # ★ .gitignore 는 sync_common 의 동기화 목록에 **없다** — 그래서 register 단계에서 고쳐도
    #   main 을 거쳐 새 워크트리로 오지 않는다(2026-07-28 실측). 여기서 직접 넣는다.
    #   이걸 빠뜨리면 새 과목의 빌드 산출물이 통째로 커밋에 섞인다.
    ig = os.path.join(dest, ".gitignore")
    if os.path.exists(ig):
        text, changed = add_gitignore(_read(ig), args.subject)
        if changed:
            _write(ig, text)
        print(("[+] " if changed else "[=] ") + "새 워크트리 .gitignore — /site/" + args.subject + "/")

    # 물려받은 다른 과목 데이터. main 이 data/열역학 을 들고 있어서(브랜치 분리 이전 잔재)
    # 새 과목이 남의 서랍을 통째로 물려받는다. **지우지는 않는다** — 콘텐츠 삭제는
    # 그 과목 세션의 판단이다(AGENTS 규칙 10). 여기서는 눈에 띄게 알리기만 한다.
    data_root = os.path.join(dest, "data")
    for name in sorted(os.listdir(data_root)) if os.path.isdir(data_root) else []:
        if name != args.subject:
            print("[!] 물려받은 다른 과목 데이터: data/" + name + " — 새 브랜치에서 지울 것")

    mine = os.path.join(data_root, args.subject)
    os.makedirs(mine, exist_ok=True)

    idx_path = os.path.join(mine, "index.json")
    if os.path.exists(idx_path):
        print("[=] index.json 이미 있음")
    else:
        chapters = json.load(open(args.chapters, encoding="utf-8")) if args.chapters else []
        index = {
            "subject": args.subject,
            "semester": args.semester or "",
            "baseTextbook": args.textbook or "TODO",
            "chapters": [
                {"chapterNumber": c["n"], "chapterTitle": c["title"],
                 "status": "todo", "file": "ch%02d.json" % c["n"]}
                for c in chapters
            ],
        }
        _write(idx_path, json.dumps(index, ensure_ascii=False, indent=2) + "\n")
        print("[+] data/" + args.subject + "/index.json — 챕터 " + str(len(index["chapters"])) + "개")

    subj_md = os.path.join(dest, ".claude", "SUBJECT.md")
    if os.path.exists(subj_md) and "[템플릿]" not in _read(subj_md):
        print("[=] .claude/SUBJECT.md 이미 있음(내용 있음) — 덮어쓰지 않는다")
    else:
        _write(subj_md, render_subject_md(args.subject, args.branch, facts))
        print("[+] .claude/SUBJECT.md — 개설 문답을 본문으로 굳혔다(빈 항목은 TODO 로 남는다)")

    # 교재 폴더 읽기 권한 — **이 워크트리의 local 에** 넣는다(원장 17). 없으면 새 세션이
    # 교재를 열 때마다 승인창을 받고, 그걸 `request_directory` 로 때우면 그 세션에서만 산다.
    tb = (facts or {}).get("textbookDir")
    if tb:
        lp = os.path.join(dest, LOCAL_SETTINGS)
        text, changed = add_local_textbook_dir(_read(lp) if os.path.exists(lp) else "", tb)
        if changed:
            os.makedirs(os.path.dirname(lp), exist_ok=True)
            _write(lp, text)
        print(("[+] " if changed else "[=] ") + "교재 폴더 읽기 권한 — " + LOCAL_SETTINGS
              + " (" + tb + ")")
    else:
        print("[!] facts 에 textbookDir 이 없다 — 새 세션이 교재를 못 읽는다(승인 원장 17). "
              "확인되면 그 워크트리의 " + LOCAL_SETTINGS + " 에 넣을 것")

    # ★ 루프 감시를 개설 시점에 켠다 (2026-09-02, 재발 4회 — medesign·heat·instru·numeth 가
    # 전부 같은 사고를 냈다: "계속 진행하겠습니다"라 써 놓고 ScheduleWakeup 을 빠뜨렸는데
    # 이 워크트리의 wakeup_guard 가 기본값(꺼짐)이라 아무도 안 막았다). 사용자:
    # "자꾸 자꾸 날 일시키게 만드네 … 한두번이 아닌데?" — 사람이 매번 켜는 방식은 재발을
    # 막지 못한다는 것이 이미 실측됐다. 12시간 만료라 그 세션이 루프를 안 쓰면 그냥 꺼진다.
    r = subprocess.run([sys.executable, os.path.join("tools", "wakeup_guard.py"), "on"],
                       cwd=dest, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(("[+] " if r.returncode == 0 else "[!] ") + "루프 감시 — " + (r.stdout or r.stderr or "").splitlines()[0])

    if args.drop_inherited:
        # 물려받은 남의 과목 데이터를 **개설 시점에** 내린다. 새 세션이 그것을 다시 발견하고
        # 다시 승인을 받는 왕복 자체가 낭비였다(2026-07-28 dynamics 실측: 한 세션을 통째로 썼다).
        # 새 워크트리 안에서 실행해야 그 브랜치의 과목 경계로 판정된다.
        r = subprocess.run([sys.executable, os.path.join(dest, "tools", "new_subject.py"),
                            "drop-inherited"], cwd=dest, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        print((r.stdout or "").rstrip() or "(drop-inherited 출력 없음)")
        if r.returncode != 0:
            print("[!] drop-inherited 실패 — 새 세션에서 직접 확인할 것\n" + (r.stderr or "")[:300])

    print("\n새 워크트리: " + dest)
    # ★ 로그온 자동 실행 등록은 **여기서 대신 실행하지 않는다** (2026-07-28).
    #   powershell 은 승인 게이트(`ask`)에 있고, 파이썬 도구가 그것을 subprocess 로 부르면
    #   게이트를 통째로 우회한다 — `tools/push.py` 로 한 번 사고가 났던 바로 그 구조다
    #   (test_tools_do_not_bypass_git_gates 참조). 대신 **빠뜨릴 수 없게 마지막 줄로 띄운다.**
    #   실측 2026-07-28: 이 안내가 없어 과목 5개 중 2개만 등록돼 있었고 8803~8805 가 안 떴다.
    print("다음 2가지:")
    print("  1) 로그온 자동 실행 등록 — 새 과목은 이걸 안 하면 서버가 영영 안 뜬다:")
    print("     powershell -ExecutionPolicy Bypass -File tools\\install_startup.ps1 -All")
    print("  2) 그 폴더에서 새 세션을 열면 SUBJECT.md 에 개설 문답이 이미 들어 있다.")
    return 0


# ── 물려받은 데이터 내리기 (그 과목 세션에서 실행) ──────────────────────────

TRAILER = "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"


def cmd_drop_inherited(args):
    """등록된 **다른 과목** 폴더만, **다른 ref 에 사본이 있을 때만** 지운다.

    과목 경계 가드(`guard_bash.foreign_subject_paths`)는 다른 과목 경로의 add/commit 을 막는다.
    그 규칙의 의도는 *[발화 생략]* 인데, 여기서 하는 일은
    **고치는 것이 아니라 중복 사본을 이 브랜치에서만 내리는 것**이고 원본은 그대로 남는다.
    그래서 가드를 끄지 않고 — 끄는 것은 빨강이다 — 조건을 더 좁힌 전용 경로를 둔다.
    """
    sys.path.insert(0, os.path.join(ROOT, ".claude", "hooks"))
    from guard_bash import SUBJECT_BY_BRANCH, subject_of_branch             # noqa: E402

    branch = _git(["branch", "--show-current"]).stdout.strip()
    # 표 직접조회 금지 — `subject_of_branch()` 만 챕터 브랜치(`claude/thermo-ch02-…`)까지 안다.
    mine = subject_of_branch(branch)
    if mine is None:
        print("거부 — 브랜치 '" + branch + "' 는 과목 매핑에 없다(main 등). 과목 워크트리에서 실행할 것.")
        return 2

    data_root = os.path.join(ROOT, "data")
    names = sorted(n for n in os.listdir(data_root)
                   if os.path.isdir(os.path.join(data_root, n)))
    victims = inherited_subject_dirs(mine, names, list(SUBJECT_BY_BRANCH.values()))
    if not victims:
        print("[=] 물려받은 다른 과목 데이터 없음 — 할 일 없다.")
        return 0

    owner = {}
    for b, s in SUBJECT_BY_BRANCH.items():
        for v in victims:
            if v.startswith(s):
                owner.setdefault(v, b)

    drop, rels = [], []
    for v in victims:
        tracked = [ln for ln in _git(["ls-files", "--", "data/" + v]).stdout.splitlines() if ln.strip()]
        if not tracked:
            print("[=] data/" + v + " — 추적되는 파일 없음, 건너뜀")
            continue
        refs = [r for r in (owner.get(v), "main") if r
                and _git(["rev-parse", "--verify", "-q", r + "^{commit}"]).returncode == 0]
        elsewhere = []
        for ref in refs:
            elsewhere += [ln for ln in _git(["ls-tree", "-r", "--name-only", ref, "--",
                                             "data/" + v]).stdout.splitlines() if ln.strip()]
        unsafe = unsafe_drops(tracked, elsewhere)
        if unsafe:
            print("거부 — data/" + v + " 의 " + str(len(unsafe)) + "개 파일이 다른 어느 ref 에도 없다"
                  " (지우면 소실): " + ", ".join(unsafe[:3]))
            return 1
        print("[o] data/" + v + " — 추적 " + str(len(tracked)) + "개 전부 "
              + "·".join(refs) + " 에 남아 있다(소실 없음)")
        drop.append(v)
        rels.append("data/" + v)

    if not drop:
        return 0
    if args.dry_run:
        print("\n--dry-run — 실제로 지우지 않았다.")
        return 0

    r = _git(["rm", "-r", "-q", "--"] + rels)
    if r.returncode != 0:
        print("삭제 실패:\n" + r.stderr)
        return 1
    msg = (branch + ": 물려받은 다른 과목 데이터 제거 — " + ", ".join(rels) + "\n\n"
           "main 이 브랜치 분리 이전 잔재로 들고 있어 새 워크트리가 상속한 사본이다.\n"
           "원본은 " + "·".join(sorted({owner.get(v, "main") for v in drop}))
           + " 브랜치에 그대로 있고(도구가 파일 단위로 대조함), 이 브랜치에서만 내린다.\n\n" + TRAILER)
    c = _git(["commit", "-m", msg])
    print((c.stdout + c.stderr).strip())
    return c.returncode


def main():
    ap = argparse.ArgumentParser(description="새 과목(브랜치+워크트리) 세우기")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register", help="공통 파일 4곳에 과목을 등록한다(멱등)")
    r.add_argument("--subject", required=True, help="과목 폴더 이름(한글). 예: 동역학")
    r.add_argument("--branch", required=True, help="브랜치 이름. 예: dynamics")
    r.add_argument("--port", required=True, type=int, help="로컬 미리보기 포트. 예: 8803")
    r.add_argument("--cover-sub", default="TODO", help="표지 한 줄(교재 표기)")
    # ★ 기본값을 «강의노트» 로 둔다 — 교재가 없는 과목이 실제로 있고(행복한 삶과 가족),
    #   저자 이름은 **책을 연 사람만** 안다. 기계가 추측해 넣으면 그 문자열이 데이터의
    #   «출처» 로 굳는다(규칙 11). 확인한 뒤 `--pitfall-book "Zill 본문 경고"` 로 준다.
    r.add_argument("--pitfall-book", default="강의노트",
                   help='pitfall 1차 근거 접두어. 예: "Zill 본문 경고" · 교재 없으면 강의노트')
    r.set_defaults(func=cmd_register)

    w = sub.add_parser("worktree", help="워크트리와 과목 고유 파일을 만든다")
    w.add_argument("--subject", required=True)
    w.add_argument("--branch", required=True)
    w.add_argument("--path", default=None,
                   help="워크트리 경로(기본: 저장소 형제 폴더/<한글표시>-<브랜치>)")
    w.add_argument("--chapters", default=None, help='[{"n":12,"title":"..."}] 형식 JSON 경로')
    w.add_argument("--facts", default=None, required=False,
                   help='필수. 개설 문답 JSON 경로 — {"textbook":…,"textbookDir":…,'
                        '"professor":…,"scope":[…],"excluded":[…],"materials":[…],"todo":[…]}')
    w.add_argument("--drop-inherited", action="store_true",
                   help="물려받은 남의 과목 데이터를 개설 시점에 바로 내린다(소실 없을 때만)")
    w.add_argument("--textbook", default=None)
    w.add_argument("--semester", default=None)
    w.set_defaults(func=cmd_worktree)

    d = sub.add_parser("drop-inherited",
                       help="물려받은 다른 과목 데이터를 이 브랜치에서 내린다(소실 없을 때만)")
    d.add_argument("--dry-run", action="store_true", help="무엇을 지울지만 보고 실제로는 안 지운다")
    d.set_defaults(func=cmd_drop_inherited)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
