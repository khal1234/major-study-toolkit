#!/usr/bin/env python
"""PreToolUse(Bash) 가드 — AGENTS.md 실행 규율을 기계가 강제한다.

메모리·문서에만 있던 규칙은 에이전트가 잊으면 그대로 통과했다(2026-07-22까지 최소 3회 재발).
여기서 명령 문자열을 실행 전에 검사해 거부한다.

**이 파일 자체의 잠금장치는 권한이 아니라 테스트다 (2026-07-24 개편).**
`.claude/**`를 통째로 승인 게이트에 두었더니 한 세션에 5번 프롬프트가 떴다. 게이트를
`.claude/settings*.json`으로 좁히는 대신, **거부 규칙 하나하나를
`tools/test_checks.py::test_guard_rules`가 검증**하게 했다. 규칙을 지우거나 약하게 하면
회귀 테스트가 깨지고, 그 테스트는 빌드·`verify_workorder.py`·`close_report.py`가 돌린다.
사람이 diff를 읽어야만 발견되던 것을 기계가 매번 본다.

→ **판정 로직은 전부 `deny_reason()` 안에 둔다.** main()에 직접 검사를 쓰면 테스트가
   그 규칙을 볼 수 없어 다시 사람 눈에 의존하게 된다.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time


def _decide(decision, reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}, sys.stdout)
    sys.exit(0)


# 인자가 무엇이든 파괴가 불가능한 읽기 전용 git 서브커맨드만. commit·push·reset·
# checkout·restore·merge·rebase·rm·clean·tag·branch·remote·config·stash 는 넣지 않는다
# (settings.json의 ask/deny 판정에 맡긴다).
# 2026-07-27: ls-tree·rev-list 등이 빠져 있어 읽기 전용인데도 승인 프롬프트가 샜다(사용자 지적).
# 부류 전체(브랜치 간 대조·이력 조회에 쓰는 읽기 서브커맨드)를 한 번에 채운다.
SAFE_GIT = {"status", "diff", "log", "show", "ls-files", "ls-tree", "rev-parse",
            "rev-list", "merge-base", "cat-file", "for-each-ref", "ls-remote",
            "name-rev", "show-ref", "describe", "blame", "shortlog", "check-ignore",
            # 2026-07-27 추가 (사용자 3회째 지적 "이거 항상 허용 왜 뜨지").
            # fetch: 원격 추적 ref만 갱신한다 — 워킹트리를 건드리지 않고 **게시도 하지 않는다**.
            #        (`git pull`은 여기 없다. 그건 merge를 품어 워킹트리를 바꾼다.)
            # grep:  워킹트리·이력 검색. 순수 읽기.
            "fetch", "grep"}
# worktree는 넣지 않는다 — list는 읽기지만 add/remove/prune이 같은 서브커맨드다(config와 같은 부류).
# → 그 부류는 아래 SAFE_GIT_PAIRS(쌍 판정)와 read_only_git_config(전용 판정)가 나눠 맡는다.


def read_only_git_config(command):
    """`git config`의 **읽기 형태**인가 — 읽기만 자동 허용하고 쓰기는 승인에 남긴다.

    열린 날 2026-07-26 (사용자 지적: "이거 항상 허용 왜 뜨지") — config는 읽기와 쓰기가
    **같은 서브커맨드**라 SAFE_GIT에 통째로 넣을 수 없었고, 가르는 로직이 없어 순수 조회
    (`git config core.bare`)까지 매번 프롬프트를 띄웠다. 읽기 판정:
      ⑴ --get/--get-all/--get-regexp/--list/-l/--show-origin/--show-scope 플래그가 있거나
      ⑵ 플래그를 뺀 인자가 **키 하나뿐**일 때 (`git config core.bare` — 값이 없으면 조회다).
    --unset/--add/--replace-all/--edit/키+값 두 인자는 쓰기 → None(승인 유지).
    """
    m = re.match(r"\s*git\s+(?:-C\s+(?:\"[^\"]*\"|'[^']*'|\S+)\s+)?config\s+(.*)$", command)
    if not m:
        return False
    rest = m.group(1)
    if re.search(r"--(unset|unset-all|add|replace-all|edit|rename-section|remove-section)\b", rest):
        return False
    if re.search(r"--(get|get-all|get-regexp|list|show-origin|show-scope)\b", rest) or \
            re.search(r"(^|\s)-l(\s|$)", rest):
        return True
    positional = [t for t in rest.split() if not t.startswith("-")]
    return len(positional) == 1

# ★ `git branch` 의 조회 형태 (열린 날 2026-08-01, 사용자 지적 "이거 모두 허용 왜 나오지").
#
# 아래 SAFE_GIT_PAIRS 에 `("branch","--show-current")`·`("branch","--list")` **둘만** 있어
# **`git branch -a`** — 가장 흔한 조회 — 가 판정 보류로 빠졌다. 그러면 통과 여부가 settings
# 캐시에 달리고, settings 는 세션 시작 때 캐시되므로 세션마다 갈린다.
#
# `branch` 를 통째로 SAFE_GIT 에 넣을 수는 없다 — `-d/-D`(삭제)·`-m/-M`(이름 변경)·
# `-c/-C`(복사)가 **같은 서브커맨드**다. 쌍 판정으로도 못 덮는다: 조회 형태가
# `-a`·`-v`·`-vv`·`-av`·`-r`·`--all`·`--merged`·인자 없는 `git branch` 등 여러 가지라
# '다음 토큰 하나'로는 열거가 끝나지 않는다. `git config` 가 전용 판정기를 갖게 된 것과 같은 자리다.
#
# 그래서 **쓰기 플래그의 부재**로 판정한다. 위치 인자가 있으면(= 새 브랜치 생성) 자동 허용하지
# 않되, `--list <패턴>`·`--contains <ref>` 처럼 인자를 갖는 조회만 예외로 둔다.
_BRANCH_WRITE_FLAGS = re.compile(
    r"(^|\s)(-[dDmMcCfu]\b|--delete\b|--move\b|--copy\b|--force\b|--set-upstream(-to)?\b|"
    r"--unset-upstream\b|--edit-description\b|--track\b|--no-track\b|--create-reflog\b)")
_BRANCH_QUERY_WITH_ARG = re.compile(r"--(list|contains|no-contains|merged|no-merged|points-at)\b")


_RESET_MODE_FLAGS = re.compile(r"--(hard|soft|mixed|merge|keep)\b")


def read_only_git_reset(command):
    """`git reset -- <경로...>`(인덱스만 되돌림)인가. 순수 함수 — 테스트 대상.

    열린 날 2026-09-02 — 사용자 지적: [사용자 발화 인용 생략] `git reset -- <path>`는
    **인덱스(스테이징)만** 되돌리고 작업 트리·HEAD는 그대로다 — `git add`로 바로
    되돌아가는, git 명령 중 가장 무해한 축에 든다.

    `--`가 없는 형태(`git reset <commit>`)는 HEAD를 옮길 수 있어 여기 포함하지 않는다 —
    반드시 `--` 뒤에 경로가 있는 형태만 인정한다(git 자체의 경로/커밋-ish 구분 관례와 같다).
    `--hard`·`--soft`·`--mixed`·`--merge`·`--keep`(작업 트리나 HEAD를 옮기는 모드
    플래그)이 있으면 이 함수는 False고, GATED_GIT의 ask로 그대로 남는다.
    """
    m = re.match(r"\s*git\s+(?:-C\s+(?:\"[^\"]*\"|'[^']*'|\S+)\s+)?reset\b(.*)$", command)
    if not m:
        return False
    rest = m.group(1)
    if _RESET_MODE_FLAGS.search(rest):
        return False
    if "--" not in rest.split():
        return False
    after = rest.split("--", 1)[1].strip()
    return bool(after)


def read_only_git_checkout_ours(command):
    """`git checkout --ours -- <경로...>`(병합 충돌 해결)인가. 순수 함수 — 테스트 대상.

    열린 날 2026-09-02 — 사용자 지적: [사용자 발화 인용 생략] 버려지는 "theirs" 쪽
    내용은 사라지지 않는다 — 병합 대상 브랜치/커밋에 그대로 남아 있어
    `git show <sha>:<경로>`로 되찾을 수 있다. `git push --force`처럼 원격 이력 자체를
    지우는 것과는 다른 위험도라 여기서만 좁게 뺀다.

    브랜치 전환(`git checkout <branch>`)이나 일반 파일 복구(`git checkout -- <file>`,
    작업 트리 변경을 버림)는 `--ours` 플래그가 없으므로 여기 안 걸리고 GATED_GIT ask로
    남는다. `--theirs`는 이번에 합의한 범위 밖이라 포함하지 않는다 — 필요해지면 그때 넓힌다.
    """
    m = re.match(r"\s*git\s+(?:-C\s+(?:\"[^\"]*\"|'[^']*'|\S+)\s+)?checkout\b(.*)$", command)
    if not m:
        return False
    return bool(re.search(r"(^|\s)--ours\b", m.group(1)))


def read_only_git_checkout_from_ref(command):
    """`git checkout <참조> -- <경로...>`(특정 커밋에서 경로만 복원)인가. 순수 함수 — 테스트 대상.

    열린 날 2026-09-03 — 사용자 지적: [사용자 발화 인용 생략]
    (main의 실수로 덮인 파일 하나를 특정 커밋에서 되돌리는 명령이 매번 ask를 띄운 자리).
    이 형태는 **참조가 git 역사에 그대로 남아 있어 언제나 되돌릴 수 있다** — HEAD도
    브랜치도 안 옮기고, 지정한 경로만 그 커밋 시점 내용으로 바뀐다.

    판정선은 **`--` 앞에 실제 참조 토큰이 있는가**다. `git checkout -- <file>`처럼
    참조 없이 경로만 있으면(현재 **미커밋** 변경을 버리는 형태) 여기 안 걸리고 GATED_GIT
    ask로 남는다 — 그건 되돌릴 데가 없어 위험도가 다르다(위 `read_only_git_checkout_ours`
    독스트링과 같은 구분). 브랜치 전환(`git checkout <branch>`, `--`가 아예 없는 형태)도
    안 걸린다 — 미커밋 변경을 잃을 수 있다.
    """
    if git_subcommand(command) != "checkout":
        return False
    m = re.match(r"\s*git\s+(.+)", command)
    try:
        tokens = shlex.split(m.group(1))
    except ValueError:
        tokens = m.group(1).split()
    i = tokens.index("checkout") if "checkout" in tokens else -1
    rest = tokens[i + 1:] if i >= 0 else []
    if not rest or rest[0].startswith("-") or rest[0] == "--":
        return False
    if "--" not in rest:
        return False
    paths = rest[rest.index("--") + 1:]
    return bool(paths)


def read_only_git_branch(command):
    """`git branch` 의 **조회 형태**인가. 순수 함수 — 회귀가 직접 부른다.

    읽기: `git branch` · `-a` · `-v` · `-vv` · `-av` · `-r` · `--all` · `--sort=…` ·
          `--format=…` · `--list 'thermo*'` · `--merged main`
    쓰기(자동 허용 안 함): `-d`·`-D`·`--delete` · `-m`·`-M` · `-c`·`-C` · `-f`·`--force` ·
          `-u`·`--set-upstream-to` · `--unset-upstream` · `--edit-description` ·
          **위치 인자만 있는 형태**(`git branch 새이름` = 생성)
    """
    m = re.match(r"\s*git\s+(?:-C\s+(?:\"[^\"]*\"|'[^']*'|\S+)\s+)?branch\b(.*)$", command)
    if not m:
        return False
    rest = m.group(1)
    if _BRANCH_WRITE_FLAGS.search(rest):
        return False
    positional = [t for t in rest.split() if not t.startswith("-")]
    if positional and not _BRANCH_QUERY_WITH_ARG.search(rest):
        return False
    return True


# ★ 부모 서브커맨드는 파괴적이지만 **특정 하위/플래그만은 읽기 전용**인 부류 (2026-07-26).
# 열린 계기: `git worktree list`가 순수 조회인데 프롬프트가 떴다(사용자 지적). `worktree`를
# 통째로 SAFE_GIT에 넣으면 `worktree remove`까지 자동 허용돼 워크트리가 소리 없이 사라진다.
# 그래서 이름 하나가 아니라 **(서브커맨드, 다음 토큰) 쌍**으로 판정한다.
# 여기에 추가할 때는 그 쌍이 인자가 무엇이든 파괴 불가인지 확인할 것.
SAFE_GIT_PAIRS = {("worktree", "list"), ("stash", "list"),
                  ("branch", "--show-current"), ("branch", "--list"),
                  ("remote", "-v"), ("remote", "show"),
                  ("config", "--get"), ("config", "--list")}

# `python <경로>` 로 실행해도 되는 곳 — 리포 고정 도구와 훅 자신뿐.
RUNNABLE_PREFIXES = ("tools/", "./tools/", ".claude/hooks/")


def mask_quoted(command):
    r"""따옴표 **안**을 같은 길이의 무해한 글자로 덮는다(오프셋이 그대로여야 한다).

    열린 날 2026-08-02 — `python tools/commit.py "…python -c 와 같은 부류로 차단" …` 이
    **거부됐다.** `inline_python` 이 명령 전체를 훑으므로 커밋 메시지 안에 적힌 `python -c`
    라는 **글자**가 실행으로 잡힌 것이다. 원장·문서·커밋 메시지에서 이 부류를 *언급*하는 것은
    앞으로도 계속 있을 일이라(이 리포는 규칙의 경위를 글로 남긴다) 인스턴스 회피로는 안 닫힌다.

    ★ 이 마스킹이 규칙을 약하게 하지 않는다 — 진짜 `python -c "코드"` 는 **`-c` 가 따옴표
    바깥**에 있어서 덮이지 않는다. 덮이는 것은 코드 본문뿐이고 판정은 `-c` 로 한다.
    """
    return re.sub(r"'[^']*'|\"[^\"]*\"",
                  lambda m: m.group(0)[0] + "x" * (len(m.group(0)) - 2) + m.group(0)[0],
                  command)


def inline_python(command):
    """`python -c "..."` / `python -` 처럼 파일 없이 코드를 실행하는 형태인가.

    두 형태를 한 함수로 묶는다 — 갈라 두었더니 `-`만 막히고 `-c`가 남았다(2026-07-24).
    `python tools/x.py -c` 처럼 **스크립트의 인자**로 오는 -c는 막지 않는다.

    2026-07-26 실사고 — 위 2026-07-24 조치는 **한 번도 발동하지 않았다.** 옛 정규식이
    `(?P<rest>.*)$` 였는데 `.`은 개행에 안 걸리고 `$`는 문자열 끝만 본다. 그래서

        python -c "
        import json ...
        "

    처럼 **코드가 여러 줄인 형태**는 마지막 줄(`"`)에 `python`이 없어 매칭 자체가 실패했다.
    실제로 쓰이는 형태가 바로 이것이라, 사용자는 세 세션에 걸쳐 같은 승인 프롬프트를 눌렀다
    (지적 3회). 회귀 테스트가 한 줄짜리만 담고 있어 계속 초록이었던 것이 이 결함을 가렸다.
    → 줄 앵커를 버리고 `python` 다음 **첫 토큰**만 본다. 개행이 있든 없든 같게 판정된다.
    """
    scan = mask_quoted(command)
    for m in re.finditer(r"(^|[\s|;&])(python|python3|py)(\.exe)?\s+", scan):
        rest = scan[m.end():].lstrip()
        if rest == "-" or rest.startswith("-c") or re.match(r"-\s*($|[|;&\s])", rest):
            return True
    return False


def inline_powershell(command):
    r"""`powershell -Command "..."` 처럼 **파일 없이** 코드를 실행하는 형태인가.

    열린 날 2026-08-02 (원장 22번). 에이전트가 포트 확인을 하려고
    `powershell -NoProfile -Command "(Test-NetConnection -ComputerName localhost -Port 8802 …)"`
    를 돌렸고 사용자에게 '모두 허용'이 떴다 — [사용자 발화 인용 생략].

    **`inline_python` 과 완전히 같은 부류다.** 일회성 조회를 인라인 코드로 짜면
    ⑴ 매번 승인을 요구하고 ⑵ 다음 세션이 같은 조회를 또 짠다. 파이썬 쪽만 막아 두고
    셸 쪽을 열어 둔 것은 **차단 목록을 언어로 적었기 때문**이지 부류가 달라서가 아니다.

    막지 않는 것: `-File <경로>` 로 **리포 안 스크립트를 실행**하는 형태.
    `tools/install_startup.ps1` 이 그 용도로 실재하고, 그건 재사용 가능한 파일이라
    이 규칙이 없애려는 '일회성 스니펫'이 아니다.
    """
    scan = mask_quoted(command)
    for m in re.finditer(r"(^|[\s|;&])(powershell|powershell_ise|pwsh)(\.exe)?\s+",
                         scan, re.IGNORECASE):
        rest = scan[m.end():]
        if re.search(r"(^|\s)-(c|command|e|ec|encodedcommand)(\s|$|:)", rest, re.IGNORECASE):
            return True
    return False


def git_subcommand(command):
    """서브커맨드를 찾는다. **인용부호를 지운 문자열이 아니라 원본 명령을 넘길 것.**

    2026-07-24 실측 결함: 호출부가 따옴표 안을 통째로 지운 문자열을 넘겨서
    `git -C "…/전공정리프로젝트" status --short` 가 `git -C  status --short` 로 보였고,
    `-C`가 인자 대신 `status`를 먹어 서브커맨드가 None이 됐다 → 자동 허용이 안 걸려
    읽기 전용 git에 승인 프롬프트가 매 세션 떴다(사용자 보고: 4세션째).
    따옴표를 지운 문자열은 체인(`&& ; |`) 탐지 전용이고, 토큰 파서에 넘기면 안 된다.
    """
    m = re.match(r"\s*git\s+(.+)", command)
    if not m:
        return None
    try:
        tokens = shlex.split(m.group(1))
    except ValueError:          # 따옴표가 안 닫힌 명령 — 공백 분할로 물러선다
        tokens = m.group(1).split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-C", "-c"):      # 전역 옵션 + 인자
            i += 2
            continue
        if tok.startswith("-"):      # --no-pager 등
            i += 1
            continue
        return tok
    return None


def git_subcommand_pair(command):
    """(서브커맨드, 바로 다음 토큰). SAFE_GIT_PAIRS 판정용 — 다음 토큰은 플래그여도 그대로 준다.

    `git branch --show-current`처럼 **플래그가 읽기 전용임을 결정**하는 경우가 있어
    git_subcommand처럼 `-`로 시작하는 토큰을 건너뛰면 안 된다.
    """
    sub = git_subcommand(command)
    if not sub:
        return (None, None)
    m = re.match(r"\s*git\s+(.+)", command)
    try:
        tokens = shlex.split(m.group(1))
    except ValueError:
        tokens = m.group(1).split()
    for i, tok in enumerate(tokens):
        if tok == sub:
            return (sub, tokens[i + 1] if i + 1 < len(tokens) else None)
    return (sub, None)


# 과목 = git 브랜치. worktree로 폴더가 갈려 두 채팅이 동시에 다른 과목을 작업한다
# (2026-07-25 채택). 열역학 세션은 thermo 브랜치, 공학수학은 math 브랜치.
# 훅이 현재 브랜치를 읽어 **다른 과목 콘텐츠 경로의 커밋을 차단**한다 —
# 세션이 자기 과목만 건드리게 기계가 강제한다. 매핑에 없는 브랜치(main 등)는 통과.
SUBJECT_BY_BRANCH = {"thermo": "열역학", "math": "공학수학", "dynamics": "동역학", "materials": "기계재료", "solids": "고체역학", "mfg": "기계공작법", "fluids": "유체역학", "appthermo": "응용열역학", "appsolids": "응용고체역학", "ee": "전기전자공학기초 및 실험", "math2": "공학수학 2", "family": "행복한 삶과 가족", "medesign": "기계요소설계", "sysctrl": "시스템제어", "instru": "계측공학", "numeth": "수치해석", "heat": "열전달", "appfluid": "응용유체역학", "vib": "진동공학", "smartmfg": "스마트생산시스템", "quality": "품질 및 신뢰성공학개론"}
SUBJECT_ROOTS = ("data/", "site/")


# 챕터 병렬 브랜치 — `<과목브랜치>-chNN` 이 **어딘가에 들어 있으면** 인정한다.
#
# ★ 처음엔 `^([A-Za-z]+)-(ch\d{2})$` 로 **정확히 일치**만 받았다. 그게 틀렸다 (2026-07-29 실사고).
# 하네스가 에이전트 워크트리에 붙이는 실제 브랜치 이름은
#   `claude/thermo-ch02-spec-backport-7558f1`
# 처럼 **앞에 `claude/`, 뒤에 작업명·해시**가 붙는다. 앵커된 정규식은 이걸 못 받았고,
# 그러면 `subject_of_branch()` 가 None 을 돌려주므로 **과목 경계까지 통째로 꺼졌다**
# (`foreign_subject_paths` 가 `mine is None` 에서 빈 목록을 준다).
# ch02 세션이 보고한 실제 증상: [사용자 발화 인용 생략]
# **가드가 사람의 성실성으로 대체된 것 — 그건 가드가 아니다**(AGENTS 규칙 7 ⑷).
#
# 그래서 경계(`^` 또는 `/`)와 구분자(`-`·`/`·끝)만 요구하고 나머지는 흘린다.
# 과목 판별은 `SUBJECT_BY_BRANCH` 조회가 최종 관문이므로, `feature-ch02` 같은 우연한 일치는
# 과목이 None 이 되어 자동으로 걸러진다.
# ★ 브랜치 이름에 **숫자**가 들어갈 수 있다 (2026-08-15, 2-2 과목을 세우다 걸렸다).
#   `[A-Za-z]+` 이면 `math2-ch01` 이 **아예 매치되지 않아** 과목이 None 이 되고, 그러면
#   `foreign_subject_paths` 가 빈 목록을 줘 **과목 경계가 통째로 꺼진 채** 돌아간다 —
#   바로 위 주석이 «우연한 일치는 걸러진다» 고 안심하던 것과 반대 방향의 실패다.
#   공학수학 2(`math2`)처럼 **숫자가 과목 이름의 일부**인 과목이 실제로 생겼으므로 허용한다.
#   최종 관문은 여전히 `SUBJECT_BY_BRANCH` 조회라, 넓혀도 남의 브랜치가 과목을 얻지는 않는다.
CHAPTER_BRANCH_RE = re.compile(r"(?:^|/)([A-Za-z][A-Za-z0-9]*)-(ch\d{2})(?:[-/]|$)")


def subject_of_branch(branch):
    """브랜치 이름에서 과목. `thermo` 도 `thermo-ch02` 도 열역학이다(순수 함수 — 테스트 대상).

    ★ 챕터 병렬 작업(2026-07-29 신설). 챕터마다 worktree를 파서 동시에 작업하려면
    브랜치가 `<과목>-chNN` 이 된다. 예전 표는 브랜치→과목 **1:1**이라 그런 브랜치가
    표에 없었고, 그러면 `allow_reason`의 자동 허용이 안 걸려 **커밋마다 승인 프롬프트**가 떴다.
    (실측 2026-07-29: 이것이 챕터 병렬화를 막고 있던 유일한 기계적 블로커였다.)
    """
    if branch in SUBJECT_BY_BRANCH:
        return SUBJECT_BY_BRANCH[branch]
    m = CHAPTER_BRANCH_RE.search(branch or "")
    return SUBJECT_BY_BRANCH.get(m.group(1)) if m else None


def branch_chapter_scope(branch):
    """`claude/thermo-ch02-작업명-해시` → 'ch02'. 챕터 스코프가 없으면 None.

    순수 함수 — 테스트 대상. `search` 인 이유는 CHAPTER_BRANCH_RE 주석 참조.
    """
    m = CHAPTER_BRANCH_RE.search(branch or "")
    return m.group(2) if m and m.group(1) in SUBJECT_BY_BRANCH else None


def out_of_chapter_paths(branch, paths):
    """챕터 브랜치가 건드리면 안 되는 경로(순수 함수 — 테스트 대상).

    ★ **왜 경계가 필요한가.** 챕터 세션 4개가 동시에 `tools/`·`AGENTS.md`·`site/template/`를
    고치면 2026-07-27 과목 간 클로버 사고가 챕터 단위로 재현된다. 그때 원인은 사람의 부주의가
    아니라 **뒤진 브랜치가 공통을 덮어쓸 수 있는 구조**였다. 병렬 세션을 늘리면 그 확률만 커진다.

    그래서 규칙은 하나다 — **챕터 세션은 자기 챕터 콘텐츠만 만진다.**
    공통(규격·검사·뷰어)은 과목 본 브랜치(`thermo`) 세션 한 곳이 소유한다.
    공통을 고쳐야 하면 그 세션에 요청하고, 챕터 세션은 `git merge`로 받는다.
    """
    scope = branch_chapter_scope(branch)
    if not scope:
        return []
    subject = subject_of_branch(branch)
    bad = []
    for p in paths:
        norm = p.strip().strip("'\"").replace("\\", "/")
        if not norm:
            continue
        # 허용: data/<내 과목>/<내 챕터>* 만. (chNN.json·chNN-review-inbox.md·chNN.textbook-map.md …)
        prefix = "data/" + subject + "/"
        if norm.startswith(prefix) and norm[len(prefix):].startswith(scope):
            continue
        bad.append(p)
    return bad


def foreign_subject_paths(branch, paths):
    """현재 브랜치 과목이 아닌 **다른 과목 콘텐츠 경로** 목록(순수 함수 — 테스트 대상).

    tools/·site/template 같은 공유 인프라는 과목 폴더가 아니므로 통과한다.
    data/열역학·site/열역학처럼 `<root><다른과목>` 형태만 잡는다.

    ★★ **폴더 이름은 「담김」이 아니라 「경계」로 본다 (2026-08-15 실사고).**
    옛 판은 `(root + other) in norm` — 순수한 부분문자열 포함이라, **남의 과목 이름이 내 과목
    이름의 접두**이면 내 폴더가 남의 것으로 잡혔다. 실측: `math2`(공학수학 2) 세션이
    `data/공학수학 2/index.json` 을 쓰려는데 **`data/공학수학` 이 그 문자열에 들어 있어** 거부됐다
    (`math` 의 과목이 «공학수학» 이라서). 즉 **그 과목이 자기 폴더를 영원히 못 만지는 상태**였고,
    화면에는 «과목 경계가 지켜졌다» 로 똑같이 보였다.
    → **내 과목 폴더인지를 먼저 본다**(경로 조각이 통째로 내 과목 이름과 같은가). 그 뒤에야
    옛 판정을 그대로 돌린다 — 담김 판정은 `data/공학수학 1` 처럼 **실재하지 않는 폴더**까지
    남의 것으로 잡아 주는 효과가 있어서(회귀 5건이 그것을 잠그고 있다) 통째로 바꾸지 않는다.
    고치는 것은 **「내 것이 남의 것으로 잡히던 자리」 하나**다.
    """
    mine = subject_of_branch(branch)
    if mine is None:
        return []
    others = [s for b, s in SUBJECT_BY_BRANCH.items() if s != mine]
    bad = []
    for p in paths:
        norm = p.strip().strip("'\"").replace("\\", "/")
        own = False
        for root in SUBJECT_ROOTS:
            at = norm.find(root)
            while at != -1:
                seg = norm[at + len(root):].split("/", 1)[0]
                if seg == mine:
                    own = True
                    break
                at = norm.find(root, at + 1)
            if own:
                break
        if own:
            continue
        if any((root + other) in norm for root in SUBJECT_ROOTS for other in others):
            bad.append(p)
    return bad


def _git_output(args):
    # encoding="utf-8" 을 빼면 안 된다 — text=True 는 로케일 인코딩(Windows=cp949)으로 디코드해
    # `git diff --cached --name-only` 가 돌려주는 **한글 경로가 깨진다**. 그러면 아래
    # foreign_subject_paths 의 과목 경계 판정이 영원히 불일치한다(2026-07-27 실측 결함).
    try:
        return subprocess.run(["git"] + args, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=5).stdout
    except Exception:
        return ""


def repo_from_command(command):
    """명령의 `-C <경로>`에서 대상 저장소 경로. 없으면 None(순수 함수 — 테스트 대상).

    2026-07-25 실사고: `-C`를 안 보고 훅 cwd에서 브랜치를 읽어, 훅 cwd가 프로젝트
    루트가 아니면 브랜치가 빈값이 되어 과목 경계가 통과됐다. worktree는 폴더가 다르므로
    반드시 명령이 가리키는 repo(=그 세션의 과목 브랜치)를 봐야 한다.
    """
    m = re.search(r'(?:^|\s)-C\s+(?:"([^"]+)"|(\S+))', command)
    return (m.group(1) or m.group(2)) if m else None


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _norm(path):
    return os.path.normcase(os.path.normpath(str(path).replace("\\", "/").rstrip("/")))


def home_claude_path(command):
    """홈의 Claude 전용 디렉터리(`~/.claude/**`)를 가리키는 셸 명령인가. 순수 함수.

    열린 날 2026-08-02 (원장 21번). 사용자: [사용자 발화 인용 생략] —
    `ls "…/.claude/projects/…/memory/"` 가 승인창을 띄웠다.

    ★ **명령이 아니라 경로가 원인이었다.** `Bash(ls *)` 는 allow 에 이미 있었고, guard 도 중립이었다.
      대상이 **프로젝트 루트 밖 + `additionalDirectories` 밖**이라 하네스의 디렉터리 게이트가
      물은 것이다(원장 14번과 같은 부류).

    ★ **14번과 조치가 반대다 — 여기는 열지 않는다.** 14번은 *교재 폴더*라 읽어야 해서 범위를
      넓혔지만, 홈 `.claude/**` 는 AGENTS **규칙 5** 가 [사용자 발화 인용 생략] 으로
      못 박은 곳이고 규칙 9 의 읽기 허용 목록(프로젝트 루트·교재 폴더·스크래치패드)에도 없다.
      **프롬프트는 경계가 제대로 돈 증거**였고, 고쳐야 할 것은 설정이 아니라 내 행동이었다.

    ★ 그래서 하네스에 맡기지 않고 여기서 막는다 — 규칙 5 에는 **기계 강제가 하나도 없었다.**
      특히 쓰기(`> ~/.claude/…`)는 권한 규칙이 대상 경로를 못 봐서 규칙 9 가 말한 구멍으로
      그대로 들어간다. 사용자 이름을 박지 않으려고 홈 경로는 `expanduser` 로 구한다.

    **프로젝트 안의 `.claude/` 는 대상이 아니다** — 절대 경로가 달라 걸리지 않고,
    `.claude/hooks/…` 같은 상대 경로도 홈 접두사를 포함하지 않는다(회귀가 이걸 잠근다).

    ★ **글자로 찾으면 안 된다 — 경로 '인자'만 본다** (같은 날 즉시 정정). 처음엔 명령 문자열에
      그 경로가 **들어 있기만 하면** 막았는데, 그러자 이 규칙을 설명하는 **커밋 메시지**가
      막혔다(`commit.py "홈 ~/.claude 셸 접근을 …"`). 경로를 *언급*하는 것과 *대상으로 삼는* 것은
      다르다 — 오늘만 세 번째로 겪은 «검사가 데이터의 정당한 표현형을 못 본다» 부류다.
      그래서 따옴표를 아는 토크나이저로 잘라 **토큰이 그 경로로 시작할 때만** 막는다.
    """
    home = os.path.join(os.path.expanduser("~"), ".claude").replace("\\", "/").lower()
    probe = command.replace("\\", "/")
    try:
        tokens = shlex.split(probe, posix=True)
    except ValueError:
        tokens = probe.split()          # 따옴표가 안 맞으면 보수적으로 — 쪼개서 본다
    for raw in tokens:
        tok = raw.lstrip("<>|&(").lower()
        if tok.startswith(home) or tok.startswith("~/.claude"):
            return True
    return False


def redundant_git_c(command, session_root_hint=None):
    """`git -C <이 프로젝트 루트>` 인가 — Bash 도구의 cwd가 이미 그 루트라 `-C`는 순수 잡음이다.

    열린 날 2026-07-27 (사용자: [사용자 발화 인용 생략]).

    **왜 반복됐나:** 지금까지 이건 문서·메모리에만 있던 습관 지침이었다. 실행 직전에
    아무것도 검사하지 않으므로 새 세션의 나는 그냥 또 쓴다 — `cd` 접두사가 3회 재발했던 것과
    **완전히 같은 구조**이고, 그때의 해법도 이 훅이었다.

    **부수 효과가 크다:** settings의 allow 규칙은 `Bash(git status *)` 처럼 **접두 매칭**이라
    `git -C … status` 는 매칭되지 않는다. 즉 불필요한 `-C` 하나가 승인 프롬프트를 만들어 왔다.
    이걸 막으면 프롬프트 원인 한 부류가 통째로 사라진다.

    다른 워크트리를 가리키는 `-C`는 막지 않는다 — 그건 실제로 필요할 때가 있다.

    ★★ **비교 대상은 «세션이 선 자리» 이지 이 훅 파일의 위치가 아니다 (고침 2026-08-15).**
      `PROJECT_ROOT` 는 이 파일 경로에서 계산되므로 훅이 main 에 살면 언제나 main 이다.
      그런데 **컨테이너 루트 세션**은 cwd 가 그 부모라 `git -C main …` 이 **필수**인데,
      옛 판정은 그것을 «잡음» 으로 읽고 거부했다(실측: push 가 통째로 막혔다).
      → `session_root` 를 받으면 그것과 비교한다. 안 받으면 옛 동작 그대로다.
      ★ 오늘 같은 부류를 **세 번째** 고친다 — `container_root_violation`(과목 경계) ·
        `runnable_script`(도구 경로) · 여기. 셋 다 **«세션은 워크트리에 선다»** 는 한 전제에서
        나왔다. 새 판정을 쓸 때 그 전제를 먼저 의심할 것.
    """
    if not re.match(r"^\s*git(\s|$)", command):
        return False
    repo = repo_from_command(command)
    here = session_root_hint or PROJECT_ROOT
    return bool(repo) and _norm(repo) == _norm(here)


def _current_branch(command):
    repo = repo_from_command(command)
    args = (["-C", repo] if repo else []) + ["branch", "--show-current"]
    return _git_output(args).strip()


def _commit_target_paths(command, subcommand):
    """git add/commit이 건드릴 경로. add는 인자에서, commit은 스테이징에서 읽는다."""
    if subcommand == "commit":
        repo = repo_from_command(command)
        args = (["-C", repo] if repo else []) + ["diff", "--cached", "--name-only"]
        return [ln for ln in _git_output(args).splitlines() if ln.strip()]
    m = re.match(r"\s*git\s+(.+)", command)
    if not m:
        return []
    try:
        tokens = shlex.split(m.group(1))
    except ValueError:
        tokens = m.group(1).split()
    # git [전역옵션] add <경로...> — 옵션(-A 등)과 서브커맨드를 지나 경로만.
    out, seen_add = [], False
    for tok in tokens:
        if tok == "add":
            seen_add = True
            continue
        if seen_add and not tok.startswith("-"):
            out.append(tok)
    return out


def script_target(command):
    """`python <경로>` 의 경로. 없으면 None.

    2026-09-02: 경로가 따옴표로 감싸여 있고 그 안에 공백이 있으면(예: 폴더 이름에
    한글 띄어쓰기가 든 과목, `품질 및 신뢰성공학개론-quality`) `[^\\s]+` 가 첫 공백에서
    멈춰 경로를 반토막 낸다 — 따옴표 쌍을 먼저 본다.
    """
    run = re.search(r"(^|\s)(python|python3|py)(\.exe)?\s+", command)
    if not run:
        return None
    rest = command[run.end():]
    for quote in ('"', "'"):
        if rest.startswith(quote):
            j = rest.find(quote, 1)
            if j > 0:
                return rest[1:j].replace("\\", "/")
    m = re.match(r"[^\s]+", rest)
    return m.group(0).strip("'\"").replace("\\", "/") if m else None


_COMMIT_TOOL_RE = re.compile(r"tools[/\\]commit\.py")


def without_commit_message(command):
    """`commit.py "<메시지>" <경로…>` 에서 **메시지를 뺀** 명령. 순수 함수 — 테스트 대상.

    열린 날 2026-08-25 (appsolids 실측). **커밋 메시지는 산문이지 인자가 아니다** —
    그런데 경로를 뽑는 자들이 명령 문자열을 통째로 훑어, 메시지 안에 인용한 파일 이름을
    **«이 커밋이 건드리는 경로»** 로 읽었다. 실사고: `data/응용고체역학` 만 넘긴 커밋이
    메시지에 적은 `tools/…py` 때문에 「선언 중에는 공통을 커밋하지 않는다」로 거부됐다.
    그 파일은 한 글자도 안 바뀐 상태였다(`git status --porcelain` 으로 확인).

    **부류가 나쁜 쪽으로 기운다** — 규율 14 는 메시지에 「왜」를 적으라고 요구하고, 「왜」에는
    **다른 파일 이름이 자연스럽게 들어온다.** 그래서 성실하게 쓸수록 더 자주 막힌다.
    메시지를 줄여 피하는 것은 규율 14 를 깎는 것이라 처방이 아니다.

    판정선은 **인용부호**다 — `commit.py` 의 첫 인용 덩어리가 메시지다(도구 서명이 그렇다).
    적용 대상은 **`commit.py` 를 실제로 부르는 명령**뿐이다 — 「이름이 어딘가에 나온다」로 재면
    `git add "tools/commit.py"` 까지 걸려 **진짜 인자를 지운다**(자가 자기 함정에 빠진 자리라
    회귀로 잠갔다). 그래서 앞머리 세 토큰 안에서 `python …/tools/commit.py` 꼴을 찾는다.
    """
    toks = command.replace("\\", "/").split()
    if not toks or not os.path.basename(toks[0]).startswith("python"):
        return command
    if not any(_COMMIT_TOOL_RE.search(t.strip("\"'")) for t in toks[:3]):
        return command
    for quote in ('"', "'"):
        i = command.find(quote)
        if i < 0:
            continue
        j = command.find(quote, i + 1)
        if j > i:
            return command[:i] + " " + command[j + 1:]
    return command


def subject_content_paths(command):
    """명령 문자열에 든 **과목 콘텐츠 경로**(`data/<과목>`·`site/<과목>`). 순수 함수.

    과목 이름을 여기 적지 않는다 — `SUBJECT_BY_BRANCH` 하나가 정본이다.
    커밋 메시지는 먼저 뺀다(`without_commit_message` 독스트링이 경위의 정본).
    """
    norm = without_commit_message(command).replace("\\", "/")
    hits = {root + s for s in SUBJECT_BY_BRANCH.values() for root in SUBJECT_ROOTS
            if (root + s + "/") in norm}
    return sorted(hits)


# ── 컨테이너 루트 세션 — 과목이 없다 (신설 2026-08-15) ───────────────────────
#
# 세션이 과목 워크트리가 아니라 **그것들을 담은 폴더**에서 열리면 이 세션에는 과목이 없다.
# 그런데 옛 판정은 **cwd 의 브랜치**로 과목을 정했고, 컨테이너 루트에서는 그게 빈값이라
# `subject_of_branch("")` → None → `foreign_subject_paths` 가 **빈 목록**을 준다.
# 즉 **경계가 꺼진다** — AGENTS 가 `claude --worktree` 를 금지하며 경고한 바로 그 상태다.
#
# ★ 여기서 «남의 과목» 이라는 말이 성립하지 않는 것이 핵심이다. 컨테이너 루트에서는
#   `git -C <아무 워크트리>` 로 **모든 과목**에 닿을 수 있고, 그때 `repo_from_command` 가
#   그 워크트리의 브랜치를 읽으므로 옛 판정은 [사용자 발화 인용 생략] 로 통과시킨다.
#   → 그래서 판정을 뒤집는다: **과목이 없는 세션은 과목 콘텐츠를 커밋하지 않는다.**
#
# ★★ **읽기는 막지 않는다.** `git show <갈래>:data/<과목>/…` 은 AGENTS 가 정한 정식
#   읽기 수단이고, 빌드(`build_site.py`)도 남의 과목 데이터를 읽어 산출물을 쓴다(그 산출물은
#   추적되지 않는다). 막는 것은 **콘텐츠를 커밋으로 굳히는 자리** 하나다.
WRITE_GIT_SUBCOMMANDS = ("add", "commit", "rm", "mv")


# ── 과목 «선언» — 컨테이너 루트 세션이 자기 정체를 말하는 자리 (신설 2026-08-15) ─────────
#
# ★ 위 판정(«과목이 없는 세션은 과목 콘텐츠를 커밋하지 않는다»)은 옳지만, 갈래가 13개라
#   **«한 줄 고치러 세션을 새로 여는» 일이 계속 생긴다.** 사용자: [사용자 발화 인용 생략].
# ★★ **「허락」은 이 가드의 입력이 아니다** — 이 계통은 [사용자 발화 인용 생략] 를 이미 판정했다. 그래서 채팅이 아니라 **파일로 선언**하고 여기서 읽는다.
# ★★★ **완화가 아니다.** 위 판정이 막던 진짜 이유는 «허락이 없어서» 가 아니라 **«이 세션에
#   과목 정체가 없어 어느 파일이 정당한지 기계가 못 가려서»** 다(바로 위 주석이 그렇게 적혀
#   있다). 선언은 그 **빠진 입력**을 주고, 선언 뒤에도 나머지 과목은 그대로 foreign 이다.
# ★ **선언 중에는 공통을 커밋하지 못한다 — 배타다.** 안 그러면 「한 세션이 전 과목 규격을
#   소유」로 되돌아가는데, 이 배선이 없애려던 것이 정확히 그 형태다. 동시에 가질 수 없게
#   두면 그 회귀가 **구조적으로** 불가능하다.
SUBJECT_DECL =os.path.join(os.path.dirname(os.path.abspath(__file__)), ".session-subject.json")
# 선언이 살아 있는 시간. ★ **고른 값** — `tools/wakeup_guard.py` 의 루프 깃발(12시간)과 견줘
# 같은 값으로 골랐다. 둘 다 목적이 «잊고 남겨 둬도 하루를 안 넘긴다» 로 같다. 1차 방어는
# 세션 id 이고 이건 그 id 를 못 읽는 환경의 2차 방어라 더 짧게 잡을 이유가 없다.
SUBJECT_DECL_TTL_SEC = 12 * 3600
# 공통 표면 — 선언 중에 커밋을 막을 자리. `sync_common.SYNC_PATHS` 와 같은 것을 가리키지만
# **훅은 tools/ 를 import 하지 않는다**(훅이 리포 코드에 매달리면 그쪽이 깨질 때 함께 죽는다).
COMMON_PREFIXES = ("tools/", "docs/", ".claude/", "site/template/", "site/fonts/")
COMMON_FILES = ("AGENTS.md", "CLAUDE.md")
# ★ `.claude/` 안에서 **이 둘은 과목별이다** — AGENTS 「공통 vs 과목별」 표가 명시한 예외다.
#   안 빼면 선언 중에 **그 과목의 자기 파일이 «공통» 으로 막힌다.** 실측으로 걸렸다:
#   선언 기구를 처음 쓴 자리에서 `appsolids/.claude/SUBJECT.md` 를 못 고쳤다.
COMMON_EXCEPT = (".claude/SUBJECT.md", ".claude/settings.local.json")

# ★ 과목 소유 도구 — `tools/` 아래 있지만 「공통」이 아니다 (2026-09-03 결함 발견).
#   `common_repo_paths()`가 `tools/` 전체를 공통으로 묶어, 과목이 자기 소유 생성기·검산기를
#   선언 중에 새로 못 만드는 구멍이 있었다(응용열역학이 `gen_steam_tables.py`를 만들려다
#   막힘 — 열역학에 이미 같은 이름·같은 로직의 파일이 있는데도). AGENTS 도구 등록부는 이미
#   이런 파일을 "과목 전용 자산이라 하드코딩이 정당하다"고 문서화해 뒀다(`test_checks.py`의
#   같은 취지 `allowed` 사전) — 가드 코드만 그 구분을 안 하고 있었다.
#   판정을 두 곳(그 사전과 여기)에 각각 적어 두는 것은 이 리포가 반복해 겪은 「같은 질문에
#   답하는 자가 둘」 부류이지만, 한쪽(`test_checks.py`)은 "이름을 박아도 되는가"를 묻고
#   여기는 "선언 중에 써도 되는가"를 물어 **다른 질문**이다 — 목록만 같게 유지한다.
SUBJECT_OWNED_TOOL_BASENAMES = {"gen_steam_tables.py", "verify_steam_tables.py"}
_SUBJECT_ANSWER_VERIFIER_RE = re.compile(r"^verify_[a-z0-9]+_answer\.py$")


def is_subject_owned_tool_path(norm):
    """`tools/<file>` 형태이고 file 이 과목 소유 자산으로 알려진 이름인가. 순수 함수."""
    if not norm.startswith("tools/") or "/" in norm[len("tools/"):]:
        return False
    base = norm[len("tools/"):]
    return base in SUBJECT_OWNED_TOOL_BASENAMES or bool(_SUBJECT_ANSWER_VERIFIER_RE.match(base))


def read_declaration(path=None):
    """선언 파일 → dict. 없거나 못 읽으면 None. **기본값은 «선언 없음» 이다.**"""
    try:
        with open(path or SUBJECT_DECL, encoding="utf-8") as fh:
            got = json.load(fh)
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) and got.get("branch") else None


def declaration_is_live(decl, session_id=None, now=None):
    """그 선언이 **지금 이 세션에서** 유효한가. 순수 함수 — 테스트 대상.

    ★ 세션이 다르면 무시한다. 잊고 남겨 둔 선언을 다음 세션이 물려받으면 그 세션은
      **자기가 선언한 적 없는 경계**로 돌아간다 — 경계를 여는 표식에서 가장 나쁜 실패다.
    ★ 세션 id 를 못 읽는 환경에서는 **시간**으로 만료시킨다(2차 방어).
    """
    if not decl or not decl.get("branch"):
        return False
    bound = decl.get("session")
    if bound and session_id and bound != session_id:
        return False
    at = decl.get("at")
    if isinstance(at, (int, float)) and (now if now is not None else time.time()) - at > SUBJECT_DECL_TTL_SEC:
        return False
    return True


def declared_subject(payload=None, path=None, now=None):
    """이 세션이 선언한 갈래 — 없으면 None. **처음 읽을 때 세션 id 를 박는다.**"""
    decl = read_declaration(path)
    session_id = (payload or {}).get("session_id")
    if not declaration_is_live(decl, session_id, now):
        return None
    if session_id and not decl.get("session"):
        decl["session"] = session_id
        try:
            with open(path or SUBJECT_DECL, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(decl, fh, ensure_ascii=False, indent=1)
        except OSError:
            pass                               # 못 박아도 TTL 이 2차로 막는다
    return decl["branch"]


def command_arguments(command):
    """명령에서 **실행되는 스크립트 자신**을 뺀 나머지. 순수 함수.

    ★ 없으면 `python <갈래>/tools/commit.py …` 의 앞머리가 `tools/` 를 포함해
      **«공통을 건드린다» 로 오독된다** — 모든 커밋이 그 형태라 판정이 통째로 거짓이 된다.
    """
    toks = command.replace("\\", "/").split()
    if toks and os.path.basename(toks[0]).startswith("python"):
        for i, tok in enumerate(toks[1:], 1):
            if tok.endswith(".py"):
                del toks[i]
                break
    return " ".join(toks)


def common_repo_paths(paths):
    """리포 상대 경로들 중 **공통 표면**에 드는 것. 순수 함수 — 선언 중에 이것을 막는다.

    ★ `guard_write` 도 이 함수를 부른다 — 판정이 두 곳에 적히면 갈라진다(이 리포가 반복해
      겪은 「같은 질문에 답하는 자가 둘」 부류).
    """
    out = []
    for p in paths or ():
        # ★ `lstrip("./")` 을 쓰지 말 것 — **문자 집합** 제거라 `.claude/…` 의 앞점까지 깎아
        #   그 경로가 통째로 공통에서 빠진다(실측으로 걸렸다. ⑷-c 가 «옳은 이유가 아닌» 채로
        #   통과하고 ⑷-d 가 깨졌다).
        norm = str(p).replace("\\", "/")
        norm = norm[2:] if norm.startswith("./") else norm
        if norm in COMMON_EXCEPT or is_subject_owned_tool_path(norm):
            continue                           # `.claude/` 안의 과목별 예외 둘 + 과목 소유 도구
        if norm.startswith(COMMON_PREFIXES) or norm in COMMON_FILES:
            out.append(norm)
    return sorted(set(out))


def common_paths_in_command(command):
    """명령에 든 **공통 표면** 경로.

    ★ **토큰으로 본다 — 부분 문자열이 아니다.** 부분 문자열로 재면 `.claude/SUBJECT.md` 가
      `.claude/` 를 포함한다는 이유로 «공통» 이 되는데, 그건 명시된 과목별 예외다.
    ★ **커밋 메시지는 먼저 뺀다** — `without_commit_message` 독스트링이 경위의 정본.
    """
    args = command_arguments(without_commit_message(command))
    return common_repo_paths(tok.strip("\"'") for tok in args.split())


def container_root_violation(command, container_root, declared=None):
    """과목이 없는 세션이 과목 콘텐츠를 커밋하려 하면 사유. 순수 함수 — 테스트 대상.

    `declared` 가 있으면 «과목이 없는 세션» 이 아니라 **«그 갈래 세션»** 으로 잰다.
    """
    if not container_root:
        return None
    sub = git_subcommand(command)
    commits = bool(re.search(r"tools[/\\]commit\.py", command.replace("\\", "/")))
    if sub not in WRITE_GIT_SUBCOMMANDS and not commits:
        return None
    hits = subject_content_paths(command)
    if declared:
        foreign = foreign_subject_paths(declared, hits)
        if foreign:
            return ("선언된 갈래는 **" + declared + "** 다 — 다른 과목 콘텐츠는 그 과목 "
                    "세션의 몫이다: " + ", ".join(foreign) + "\n"
                    "  둘을 동시에 가지면 「한 세션이 전 과목 규격을 소유」로 되돌아간다 —\n"
                    "  컨테이너 루트 배선이 없애려던 바로 그 형태다.\n"
                    "  -> 공통을 고치려면 `python tools/session_subject.py --off` 로 선언을 먼저 끌 것.")
        return None
    if not hits:
        return None
    return ("이 세션은 **컨테이너 루트**라 과목이 없다 — 과목 콘텐츠는 그 과목 세션에서 "
            "커밋한다: " + ", ".join(hits) + "\n"
            "  여기서 할 것은 공통뿐이다(tools/ · AGENTS.md · site/template · site/fonts · "
            ".claude/ · docs/).\n"
            "  읽기는 막지 않는다 — `git show <갈래>:<경로>` 를 쓸 것.\n"
            "  이 세션에서 그 과목을 만져야 하면 **선언**할 것: "
            "`python main/tools/session_subject.py <갈래> --why \"<사유>\"` "
            "(선언 중에는 공통 커밋이 막힌다).")


def runnable_script(target, session_root=None):
    """`python <target>` 을 허용할 자리인가. 순수 함수 — 테스트 대상.

    ★ **컨테이너 루트 세션에서는 도구가 `<워크트리>/tools/…` 로 불린다** — 그 세션에는
      워크트리가 없어서 `tools/x.py` 라는 상대 경로가 아예 성립하지 않는다. 그것을 «리포 밖»
      으로 읽으면 **공통을 고칠 수단 자체가 사라진다**(실측 2026-08-15: 훅을 켠 바로 그 명령이
      `sync_common.py` 거부였다 — 배선을 깔자마자 배선 도구가 막혔다).
    ★★ 그렇다고 아무 `*/tools/*` 나 열면 이 규칙이 없어지는 것과 같다. 그래서 **세션 루트
      바로 아래 한 칸**(= 워크트리 폴더)의 `tools/`·`.claude/hooks/` 만 인정한다.
      두 칸 아래나 루트 밖은 여전히 거부다.
    """
    t = (target or "").replace("\\", "/")
    if t.startswith(RUNNABLE_PREFIXES):
        return True
    if not session_root:
        return False
    root = os.path.normpath(str(session_root)).replace("\\", "/").rstrip("/")
    full = t if re.match(r"^(?:[A-Za-z]:)?/", t) else root + "/" + t
    full = os.path.normpath(full).replace("\\", "/")
    if not full.lower().startswith(root.lower() + "/"):
        return False
    return bool(re.match(r"^[^/]+/(?:tools|\.claude/hooks)/", full[len(root) + 1:]))


def trusted_repo_script(target, session_root=None):
    """실행 대상이 **HEAD에 추적된 그대로의 blob**인가.

    경로 모양만으로 `tools/*.py`를 신뢰하면 새 파일을 쓴 직후 자식 프로세스로 권한
    경계를 우회할 수 있다. 추적 여부와 working-tree blob을 둘 다 확인한다. Git 확인이
    실패하거나 파일이 수정·신규 상태면 엄한 쪽(False)으로 넘어진다.
    """
    root = os.path.abspath(str(session_root or PROJECT_ROOT))
    t = (target or "").replace("\\", "/")
    full = os.path.abspath(t if os.path.isabs(t) else os.path.join(root, t))
    try:
        top = subprocess.run(
            ["git", "-C", os.path.dirname(full), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if top.returncode != 0:
            return False
        repo = os.path.normcase(os.path.abspath((top.stdout or "").strip()))
        norm_full = os.path.normcase(full)
        if os.path.commonpath([repo, norm_full]) != repo:
            return False
        rel = os.path.relpath(full, repo).replace("\\", "/")
        if not (rel.startswith("tools/") or rel.startswith(".claude/hooks/")):
            return False
        tracked = subprocess.run(
            ["git", "-C", repo, "ls-files", "--error-unmatch", "--", rel],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if tracked.returncode != 0:
            return False
        work_hash = subprocess.run(
            ["git", "-C", repo, "hash-object", "--", rel],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        head_hash = subprocess.run(
            ["git", "-C", repo, "rev-parse", "HEAD:" + rel],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return (work_hash.returncode == 0 and head_hash.returncode == 0
                and work_hash.stdout.strip() == head_hash.stdout.strip())
    except (OSError, ValueError):
        return False


def deny_reason(command, container_root=False, session_root=None, declared=None):
    """차단해야 할 명령이면 사유 문자열, 아니면 None.

    **거부 규칙은 전부 여기 있어야 한다** — test_checks.py가 이 함수를 직접 부른다.
    `container_root` 는 «이 세션에 과목이 없다»는 사실이고, `session_root` 는 그 세션이
    선 폴더다(컨테이너 루트에서 `<워크트리>/tools/…` 를 인정하는 데 쓴다).
    `declared` 는 그 세션이 **스스로 선언한 갈래**다 — 없으면 옛 판정 그대로다.
    """
    hit = container_root_violation(command, container_root, declared)
    if hit:
        return hit

    if re.match(r"^\s*cd\s", command):
        return ("`cd`로 시작하는 명령은 차단됨(AGENTS.md 실행 규율 4 / 메모리 no-cd-prefix). "
                "Bash 도구의 작업 디렉터리는 이미 프로젝트 루트이고, `cd` 접두사는 "
                "settings.json allow 규칙을 무력화해 불필요한 승인 프롬프트를 만든다. "
                "명령을 실행 파일 이름(python, git, ...)으로 시작할 것.")

    # ★ echo 금지 (2026-07-27). 사용자가 `git -C`와 함께 **불편감 투탑**으로 지목했고,
    # 여러 세션에 걸쳐 고쳐 달라 했는데 계속 되살아났다 — 문서에만 있었기 때문이다.
    #
    # 위험도 실질적이다: `Bash(echo *)` 가 allow에 있으면 **리디렉션으로 어디든 쓸 수 있다**
    # (`echo x > 아무경로`). 권한 규칙은 명령 문자열만 보고 `>` 대상 경로를 못 본다 —
    # AGENTS 규칙 9가 "권한이 못 막는 마지막 층"이라 부른 바로 그 구멍이다.
    # 대체 수단은 전부 있다: 파일 쓰기는 Write, 읽기는 Read·Grep, 확인 출력은 도구의 print.
    # ★ 명령 치환(백틱 · `$(…)`)은 차단 (2026-08-15, **실측으로 열렸다**).
    #
    # **커밋 메시지가 조용히 깨졌다.** 이 리포의 문서 관례는 코드·경로를 백틱으로 감싸는
    # 것인데, 그 메시지를 `commit.py "…"` 로 넘기면 **bash 가 백틱 안을 명령으로 실행하고
    # 결과로 갈아치운다.** 실측(a664004): 한 커밋에서 **문장 셋의 주어가 통째로 사라졌고**,
    # 커밋은 exit 0 이라 **아무도 안 신고했다** — 이 리포에서 가장 비싼 «그럴듯하게 틀린» 부류다.
    # ★ 위험도 실질적이다: 치환은 **임의 명령 실행**이라 `echo`·힙독을 막은 것과 같은 자리다.
    # → 메시지에는 「」·«» 를 쓰고, 값이 필요하면 `python tools/…` 의 print 로 받는다.
    if "`" in command or "$(" in command:
        return ("명령 치환(백틱 · `$(…)`)은 차단됨 — **bash 가 그 안을 실행해 결과로 갈아치운다.**\n"
                "  실측 2026-08-15: 커밋 메시지의 백틱이 먹혀 **문장 셋의 주어가 사라졌는데**\n"
                "  커밋은 exit 0 이라 아무도 신고하지 않았다.\n"
                "  -> 메시지·설명에는 「」 나 «» 를 쓸 것. 값이 필요하면 `python tools/…` 의 print.")

    if re.match(r"^\s*echo(\s|$)", command):
        return ("`echo`는 차단됨(2026-07-27, 사용자 반복 지적). 필요한 일이 무엇이든 더 안전한 "
                "수단이 있다 — 파일을 만들거나 고치려면 **Write/Edit 도구**, 내용을 보려면 "
                "**Read·Grep 도구**, 값을 확인하려면 `python tools/…`의 print를 쓸 것. "
                "`echo`를 allow에 두면 `echo x > 경로` 리디렉션으로 **프로젝트 밖에도 쓸 수 있고**, "
                "권한 규칙은 `>` 대상 경로를 보지 못한다(AGENTS 규칙 9).")

    # ★ 홈의 Claude 전용 디렉터리 금지 (2026-08-02, 원장 21번).
    if home_claude_path(command):
        return ("홈의 Claude 디렉터리(`~/.claude/**`)를 셸로 건드리는 것은 차단됨 "
                "(AGENTS 규칙 5 — Claude 전용이라 이 리포의 작업 대상이 아니다. "
                "프로젝트 안의 `.claude/`는 대상이 **아니고** 정상 작업 경로다). "
                "메모리 목록이 필요하면 세션 시작 때 이미 문맥에 실리는 `MEMORY.md`를 보고, "
                "개별 파일은 **Read·Write 도구**로 연다 — 그 경로는 도구 쪽에서 따로 허용된다. "
                "셸로 훑으면 프로젝트 밖이라 승인 프롬프트가 뜨고, 리디렉션(`> ~/.claude/…`)은 "
                "권한 규칙이 대상 경로를 보지 못해 규칙 9의 구멍으로 그대로 들어간다.")

    # ★ 불필요한 `git -C <프로젝트 루트>` 금지 (2026-07-27, 위와 같은 '투탑').
    if redundant_git_c(command, session_root):
        return ("`git -C \"" + str(repo_from_command(command)) + "\"` 는 차단됨 — "
                "**`-C`를 빼고 그냥 `git …`으로 쓸 것.** Bash 도구의 작업 디렉터리가 이미 이 "
                "프로젝트 루트라 `-C`는 아무것도 바꾸지 않는다. 게다가 settings의 allow는 "
                "`Bash(git status *)`처럼 **접두 매칭**이라 `git -C … status`가 규칙에 걸리지 않고 "
                "**불필요한 승인 프롬프트**를 만든다(사용자 반복 지적). "
                "다른 워크트리를 가리키는 `-C`는 막지 않는다.")

    # ★ `2>&1` 등 리디렉션 금지 (2026-07-27, 사용자 지적 "이거 분명 안 나오게 한다 예전 세션에서 했는데").
    #
    # AGENTS 실행 규율 4가 이미 [사용자 발화 인용 생략]
    # 이라고 적고 있는데 **한 세션에 20회 넘게 반복**됐다. 문서에만 있어서다 — echo·`cd`와 같은 구조.
    #
    # 실제 피해: `python tools/test_checks.py` 는 allow에 있는데 `> 파일 2>&1` 이 붙는 순간
    # 규칙과 다르게 평가돼 **승인 프롬프트**가 뜬다. 게다가 `>` 대상 경로는 권한 규칙이 보지 못해
    # 프로젝트 밖으로도 쓸 수 있다(AGENTS 규칙 9).
    #
    # **먼저 필요를 없앴다:** 출력이 길어 읽기 힘들던 것이 이유였으므로
    # `python tools/test_checks.py --fail-only` 를 만들었다. 이제 리디렉션할 이유가 없다.
    redir = re.search(r"2>&1|(?<![0-9])>>?\s*\S", re.sub(r"'[^']*'|\"[^\"]*\"", "", command))
    if redir:
        return ("출력 리디렉션(`" + redir.group(0).strip() + "`)은 차단됨(AGENTS 실행 규율 4). "
                "정확 허용된 명령에 리디렉션이 붙으면 규칙과 다르게 평가돼 **승인 프롬프트**가 뜨고, "
                "`>` 대상 경로는 권한 규칙이 보지 못해 프로젝트 밖으로도 쓸 수 있다(규칙 9).\n"
                "대체 수단: 회귀 테스트는 **`python tools/test_checks.py --fail-only`**(실패만 출력), "
                "긴 출력을 파일로 남겨야 하면 그 도구에 `--out` 같은 옵션을 추가할 것. "
                "파일을 읽으려면 Read·Grep 도구를 쓴다.")

    # ★ grep/rg 패턴에 꺾쇠(`<`·`>`)가 들어가면 거부 (2026-07-30, 원장 19번).
    #
    # 사용자: [사용자 발화 인용 생략] — `grep -n -o "이해도[^<]\{0,40\}" …` 에 승인창이 떴다.
    # settings 에 `Bash(grep *)` 가 **있는데도** 떴고, 같은 세션의 꺾쇠 없는 grep 은 안 떴다.
    # 하네스의 권한 매처가 따옴표 안의 `<` 를 **리디렉션으로 읽는 것**으로 보인다(미검증).
    #
    # 원인을 우리가 못 고치므로 **필요를 없앤다.** Grep 도구는 승인을 아예 안 타고
    # 파일 링크까지 붙는다 — SVG·빌드 출력을 뒤지는 일은 전부 그쪽이 낫다.
    # AGENTS 실행 규율 4에 이미 적혀 있었는데 문서에만 있어서 매번 Bash grep 으로 돌아갔다.
    # ★ 2026-07-31 확장 — 방아쇠는 꺾쇠가 아니라 **쉘 특수문자 전체**였다(원장 20번).
    #   사용자: [사용자 발화 인용 생략] — `grep -o "[^\"]\{0,60\}frac[^\"]\{0,60\}" …`.
    #   꺾쇠가 하나도 없는데 떴다. 공통점은 *따옴표 안에 있어도 쉘 렉서가 특별히 읽는 문자*다
    #   (`<`·`>` = 리디렉션, `\"` = 따옴표 이스케이프). 즉 부류는 "꺾쇠"가 아니라
    #   **매처가 명령을 우리와 다르게 쪼개게 만드는 문자**다 — 좁게 잡았더니 그 밖으로 새로 들어왔다.
    #
    # ★★★ **2026-08-24 — 세 번째다. 문자 목록을 버리고 명령을 통째로 막는다**(원장 29번).
    #   사용자: [사용자 발화 인용 생략] — `grep -c "" "…/naru/변경일지.md"`.
    #   이번 방아쇠는 **빈 따옴표 `""`** 였다. 꺾쇠도 이스케이프 따옴표도 없다.
    #   ★ **앞의 두 판이 틀린 방식이었다는 것이 요점이다.** 방아쇠 문자를 하나씩 추가하는 한
    #     «아직 안 만난 문자» 가 남아 있고, 그건 사용자가 승인창으로 알려 줄 때까지 안 보인다 —
    #     즉 **이 규칙은 구조상 항상 한 발 늦는다.** 2026-07-31 판이 [사용자 발화 인용 생략] 며 좁게 남겼는데, 그때 걱정한 「우회」는 실체가 없었다: 막힌 자리의 대체 수단이
    #     **Grep 도구 하나로 완전**하기 때문이다(내용 검색·글롭·문맥·개수 전부 된다).
    #   → 그래서 `grep`·`rg` 를 **조건 없이** 막는다. 이 부류는 여기서 끝난다.
    #   ※ 줄 수만 세는 것이라면 `wc` 가 열려 있고, 파일을 보는 것이라면 Read 가 있다.
    if re.match(r"^\s*(?:grep|rg)\b", command):
        return ("Bash 의 `grep`/`rg` 는 차단됨(원장 19·20·29번 — **같은 부류 3회**).\n"
                "settings 에 `Bash(grep *)` 가 있어도 패턴 안의 어떤 문자(`<`·`>`·`\\\"`·`\"\"` …)가 "
                "하네스 매처를 쉘 문법으로 헷갈리게 하면 접두 규칙 밖으로 떨어져 **승인창이 뜬다.** "
                "방아쇠 문자를 하나씩 막는 방식은 세 번 다 한 발 늦었다.\n"
                "→ **Grep 도구를 쓸 것** — 승인을 안 타고, 파일 링크가 붙고, `output_mode`·`glob`·"
                "`-C` 로 개수·문맥까지 다 된다. 줄 수만 세려면 `wc`, 파일을 보려면 Read.")

    if "<<" in command:
        return ("힙독(`<<`)은 차단됨(AGENTS.md 실행 규율 2). 일회성 감사를 쪼개 반복 실행하지 말 것. "
                "필요한 감사를 한 스크립트로 설계해 파일로 저장한 뒤 "
                "`python <경로>`로 한 번만 실행하고, 재사용할 것 같으면 tools/ 로 승격할 것.")

    # `python -`(표준입력)과 `python -c`(인라인 코드)는 같은 결함이다 — 쪼갠 일회성 감사.
    # 2026-07-24: `-`만 막혀 있어 `python -c`가 3~4세션 동안 계속 새어나갔다(사용자 실측).
    if inline_python(command):
        return ("`python -c`/`python -`(인라인·표준입력 실행)은 차단됨(AGENTS.md 실행 규율 2). "
                "한 줄짜리 조회라도 예외가 아니다 — 같은 조회를 다음 세션이 또 하게 된다. "
                "**데이터를 들여다보려는 것이라면 `python tools/inspect_data.py`를 쓸 것** — "
                "챕터 요약·연습문제 표·문풀 표·항목 JSON·삽화 목록·증기표 조회가 다 있고 "
                "tools/ 안이라 승인 프롬프트가 없다. 거기 없는 조회면 스니펫을 짜지 말고 "
                "그 도구에 서브커맨드를 추가할 것(재사용 가능한 형태로 남는다).")

    # ★ `powershell -Command "..."` 도 같은 부류다 (2026-08-02, 원장 22번).
    #   파이썬만 막아 두었더니 셸 쪽으로 새어나갔다 — 차단 목록을 **언어로** 적은 탓이다.
    if inline_powershell(command):
        return ("`powershell -Command`(인라인 코드 실행)은 차단됨(AGENTS.md 실행 규율 2). "
                "`python -c` 와 같은 부류다 — 일회성 스니펫은 매번 승인을 요구하고 "
                "다음 세션이 같은 조회를 또 짠다. "
                "**서버가 떠 있는지 보려는 것이라면 그냥 `preview_start` 로 열어 볼 것** "
                "(안 떠 있으면 그때 `wscript tools/serve_site.vbs`). "
                "재사용할 조회면 `tools/` 에 스크립트로 남기고 `-File tools\\<이름>.ps1` 로 부를 것.")

    # 명령을 이어붙이면 조각마다 독립 매칭이라 하나만 빠져도 승인 프롬프트가 뜬다.
    # (2026-07-20 실측) 따옴표 안의 구분자는 셸이 해석하지 않으므로 먼저 지우고 본다.
    bare = re.sub(r"'[^']*'|\"[^\"]*\"", "", command)
    chain = re.search(r"(\|\||&&|[|;])", bare)
    if chain:
        return ("명령 이어붙이기(`" + chain.group(1) + "`)는 차단됨(AGENTS.md 실행 규율 4). "
                "복합 명령은 조각마다 독립 매칭돼 승인 프롬프트를 만든다. "
                "Bash 한 번에 명령 하나. 여러 단계가 필요하면 tools/ 의 도구 하나로 합칠 것. "
                "파일을 읽으려면 파이프 대신 Read·Grep 도구를 쓸 것.")

    # 과목 경계 — 현재 브랜치와 다른 과목 콘텐츠를 add/commit하려 하면 막는다.
    sub = git_subcommand(command)
    if sub in ("add", "commit"):
        branch = _current_branch(command)
        targets = _commit_target_paths(command, sub)
        bad = foreign_subject_paths(branch, targets)
        if bad:
            return ("과목 경계 위반 — 현재 브랜치 '" + branch + "'(" + str(subject_of_branch(branch))
                    + ")에서 다른 과목 경로를 " + sub + "하려 함: " + ", ".join(bad[:4])
                    + " (2026-07-25 과목=브랜치 정책). 이 세션은 자기 과목만 다룬다 — "
                    + "다른 과목은 그 과목 worktree 폴더의 세션이 커밋한다. "
                    + "스테이징에 섞였으면 `git reset <경로>`로 빼라.")
        # 챕터 경계 — 챕터 브랜치는 자기 챕터 콘텐츠 밖을 커밋하지 않는다 (2026-07-29 병렬화).
        outside = out_of_chapter_paths(branch, targets)
        if outside:
            scope = branch_chapter_scope(branch)
            return ("챕터 경계 위반 — 브랜치 '" + branch + "'는 " + str(scope)
                    + " 콘텐츠 전용인데 그 밖을 " + sub + "하려 함: " + ", ".join(outside[:4])
                    + ". 챕터 세션은 `data/" + str(subject_of_branch(branch)) + "/" + str(scope)
                    + "*` 만 커밋한다. 공통(tools/·AGENTS.md·site/template/)은 과목 본 브랜치 "
                    + "세션 한 곳이 소유한다 — 규격을 고쳐야 하면 그 세션에 요청하고 "
                    + "여기서는 `git merge`로 받아라. (2026-07-27 공통 클로버 사고가 "
                    + "챕터 단위로 재현되는 것을 막는 경계다.)")

    # 일회성 스크립트 금지 — 실행 규율 2의 '고정 도구로 승격'을 기계가 강제한다.
    target = script_target(command)
    if target and not target.startswith("-") and not runnable_script(target, session_root):
        return ("리포 밖 스크립트 실행은 차단됨: " + target + " (AGENTS.md 실행 규율 2). "
                "일회성 감사 스크립트를 새로 짜지 말 것 — 먼저 tools/ 의 기존 도구가 "
                "이미 그 검사를 하는지 확인하고(build_site.py·audit_content.py 등), "
                "없으면 tools/ 에 고정 도구로 추가해 실행할 것. "
                "실측 2026-07-22: 앵커 감사를 스크래치패드로 짰는데 빌드에 이미 있던 검사였다.")
    script_root = os.path.abspath(str(session_root or PROJECT_ROOT))
    script_path = os.path.abspath(target if (target and os.path.isabs(target))
                                  else os.path.join(script_root, target or ""))
    if (target and target.endswith(".py") and runnable_script(target, session_root)
            and os.path.isfile(script_path)
            and not trusted_repo_script(target, session_root)):
        return ("신규·수정된 리포 도구는 자동 실행하지 않는다: " + target + ". "
                "HEAD 추적 여부와 blob 해시가 일치해야 한다. 도구 변경을 검토·커밋한 뒤 실행할 것. "
                "Python 자식 프로세스는 도구 권한 경계를 다시 타지 않으므로 경로 모양만 믿을 수 없다.")

    return None


def allow_reason(command, session_root=None):
    """settings.json allow 리스트를 우회해 확실히 통과시킬 명령이면 사유, 아니면 None.

    2026-07-23: `Bash(python tools/build_site.py)`가 allow에 글자 그대로 있는데도
    승인 프롬프트가 반복해 떴다(엔진 매칭 실패). 그래서 '안전한 리포 고정 도구'만
    여기서 명시적으로 통과시킨다. **deny_reason()이 None일 때만 유효하다.**

    **★ 한계 (2026-07-24 실측으로 정정): 이 allow는 settings.json의 `ask`를 이기지 못한다.**
    `python tools/scratch/restructure_ch01.py`는 여기서 allow로 판정되는데도
    `Bash(*python* tools/scratch/*)`(ask)에 걸려 프롬프트가 떴다. 이전 주석은
    "deny가 먹으니 allow도 먹는다"고 **추정**해 적혀 있었으나 근거가 없었다
    (build_site.py는 settings allow에도 있어 훅과 무관하게 통과하던 것).
    → 프롬프트를 없애려면 훅이 아니라 settings의 ask를 손봐야 한다.
    """
    target = script_target(command)
    if (target and target.endswith(".py") and target.startswith(("tools/", "./tools/"))
            and trusted_repo_script(target, session_root)):
        return "리포 고정 도구(python tools/*.py) — guard 자동 허용"
    # ★ 훅 스크립트도 같은 부류다 (열린 날 2026-08-23 · 승인 원장 27번).
    #   사용자: [사용자 발화 인용 생략] — `python .claude/hooks/shared_sync_check.py --list`.
    #   **AGENTS 가 손으로 부르라고 적어 둔 명령들**이다(`shared_sync_check.py --accept` ·
    #   `gate_rerun_guard.py --check-wiring .` · `session_brief.py`). 그런데 자동 허용은
    #   `tools/` 접두만 봐서 **어느 목록에도 없는 채 판정 보류로 빠졌다**(원장 21번과 같은 부류).
    #   ★ 범위를 넓히는 것이 아니다 — 리포 안에 고정된 파이썬 스크립트라는 점이 `tools/` 와 같고,
    #     HEAD 추적·blob 일치까지 확인한 것만 여기서 자동 허용한다.
    if (target and target.endswith(".py")
            and target.startswith((".claude/hooks/", "./.claude/hooks/"))
            and trusted_repo_script(target, session_root)):
        return "리포 고정 훅(python .claude/hooks/*.py) — guard 자동 허용"
    if re.search(r"cscript\b.*tools/serve_site\.vbs", command.replace("\\", "/")):
        return "로컬 미리보기 서버 — guard 자동 허용"
    if git_subcommand(command) in SAFE_GIT:
        return "읽기 전용 git — guard 자동 허용"
    # 아래 둘은 2026-07-26에 thermo·math가 **같은 사용자 지적("이거 항상 허용 왜 뜨지")을
    # 각자 고쳐** main에서 충돌한 것이다. 한쪽을 버리면 다른 과목이 고친 부류가 되살아나므로
    # 둘 다 남긴다 — 쌍 판정은 worktree·stash·branch·remote를, config는 읽기/쓰기가 같은
    # 서브커맨드라 전용 판정기가 맡는다(플래그 조합이 많아 쌍으로는 못 덮는다).
    if git_subcommand_pair(command) in SAFE_GIT_PAIRS:
        return "읽기 전용 git 하위명령 — guard 자동 허용"
    if read_only_git_config(command):
        return "git config 조회(읽기 형태) — guard 자동 허용"
    if read_only_git_branch(command):
        return "git branch 조회(읽기 형태) — guard 자동 허용"
    # ★ 2026-09-02 신설 — 사용자가 GATED_GIT을 인자 무관 매번 ask로 뭉뚱그린 것을 지적:
    #   "git reset --는 인덱스만 되돌리는 거라 사실상 무해한데" · "checkout --ours도 버려지는
    #   쪽이 다른 브랜치에 남아 있어서 force-push급 위험이 아닌데". 아래 두 좁은 형태만 자동
    #   허용으로 빼고, 그 외(--hard·일반 checkout·branch 전환·rebase 등)는 GATED_GIT에 그대로 둔다.
    if read_only_git_reset(command):
        return "git reset -- <경로>(인덱스만 되돌림, 작업 트리·HEAD 불변) — guard 자동 허용"
    if read_only_git_checkout_ours(command):
        return "git checkout --ours(병합 충돌 해결, 버려지는 쪽은 다른 브랜치에 남음) — guard 자동 허용"
    if read_only_git_checkout_from_ref(command):
        return "git checkout <참조> -- <경로>(그 커밋에서 경로만 복원, 참조가 역사에 남아 있어 되돌릴 수 있음) — guard 자동 허용"
    # ★ 일상 로컬 git 쓰기(add·commit·merge)는 과목 브랜치에서 guard가 자동 허용한다
    # (2026-07-27, 사용자 재지적: git 쓰기 프롬프트가 매 세션 반복됨).
    # 근거: deny_reason이 **다른 과목 경로**를 건드리는 add/commit을 이미 막았으므로,
    # 여기 도달한 것은 자기 과목·공통 파일 대상 = 로컬·되돌림 가능 = 안전.
    # blocking 훅 deny가 permission allow보다 우선한다. 판정은 훅 한 곳에서 통제한다.
    # **일반 checkout·restore·rebase·push 는 넣지 않는다** — 작업 소실·게시라 게이트 유지.
    # reset·checkout은 위 두 좁은 형태(인덱스만 되돌리는 reset, --ours 병합 해결)만 예외로 뺐다
    # (2026-09-02). merge는 주로 `git merge main`(공통 정본 수신)이고 되돌릴 수 있어 포함한다.
    if git_subcommand(command) in ("add", "commit", "merge") and subject_of_branch(_current_branch(command)):
        return "과목 브랜치의 로컬 git(add/commit/merge) — guard 자동 허용(foreign·챕터 경계 통과분)"
    # ★★ **루프 회차의 마지막 도구 호출은 재예약이다** (열린 날 2026-08-07 · 한 세션에서 2회 빠뜨림).
    #
    #   사용자: [사용자 발화 인용 생략] — 실측하니 `/loop` 이 **한 회차 돌고 죽어** 있었다.
    #   원인은 도구가 아니라 **회차 마무리의 순서**다. 사용자가 정한 회차 끝 의식이
    #   `shutdown -a` + `shutdown -s -t <초>` 두 줄이라, 그 둘을 실행하고 요약을 쓰면
    #   *끝냈다* 는 느낌이 들어 **ScheduleWakeup 을 안 부른다.** 그런데 루프는 매 턴 다시
    #   예약해야만 이어진다(re-arming is a per-turn choice, not a default).
    #   두 번 다 사람이 발견했다 — 즉 사람의 성실성에 기대는 상태였다.
    #
    #   ☞ **그 두 줄을 실행하는 순간** 리마인더를 띄운다. 규칙 문서에 적는 것으로는 못 막는다 —
    #     빠뜨리는 자리가 *문서를 읽는 때* 가 아니라 **턴을 닫는 때** 이기 때문이다.
    #     막지는 않는다(종료 타이머는 정당한 명령이고, 막으면 자리 비움 자동 종료가 깨진다).
    #     `-a`(취소)에는 안 뜬다 — 회차를 닫는 것은 **무장하는 줄**이다.
    #   ☞ 공통 파일이라 `sync_common` 으로 **다른 과목 세션도 같은 리마인더를 받는다.**
    #     그 세션들에 붙여넣는 지시문에도 같은 구멍이 있었다(사용자가 relay 하는 문구라
    #     문구만 고치면 다음에 또 복제된다).
    #   잠금: `test_checks.py::test_guard_rules` 의 「루프 재예약 리마인더」 케이스.
    if re.search(r"\bshutdown\b[^\n]*(?:-|/)s\b", command):
        return ("종료 타이머 — guard 자동 허용. ★ 이 턴이 `/loop` 회차라면 "
                "**마지막 도구 호출은 ScheduleWakeup 이어야 한다** — 요약 문구를 먼저 쓰고 "
                "그다음 재예약할 것. 빠뜨리면 루프가 한 회차 돌고 죽는다 "
                "(2026-08-07 같은 세션에서 2회 발생, 두 번 다 사용자가 발견).")
    return None


# ★ 매번 물어야 하는 git 쓰기 — **영구 허용으로 넘어가면 안 되는** 부류 (2026-07-27 신설).
#
# 사용자 지적: [사용자 발화 인용 생략]
#
# blocking PreToolUse 훅은 permission allow보다 먼저 평가되고 deny가 우선한다. 이 게이트는
# 설정의 넓은 allow와 무관하게 되돌리기 어려운 Git 쓰기를 매번 ask로 돌린다.
#
# 여기서 하는 일은 두 가지다.
#   ⑴ 훅이 **명시적으로 ask를 돌려주고**, 그 사유 문구에 *1회 허용만 누를 것*을 적는다
#      (승인창에 그대로 뜬다 — 버튼 구성을 리포에서 바꿀 수는 없지만 사유는 우리가 쓴다).
#   ⑵ 그래도 눌렸을 때를 대비해 **회귀 테스트가 settings의 allow를 감시한다**
#      (`test_guard_rules`의 '게이트 명령이 allow에 새어 들어가지 않았다').
# push는 여기 없다 — deny_reason이 아예 막고 `tools/push.py`로 보낸다(프롬프트 0).
# 아래 넷은 아직 프롬프트가 뜨고, 그러면 '모두 허용' 버튼도 함께 뜬다.
# **남은 숙제다** — 각각 좁은 전용 도구를 만들어 push와 같은 구조로 옮겨야 한다.
# 그때까지는 사유 문구로 경고하고, 눌렸는지는 회귀 테스트가 감시한다.
# ★ 2026-09-02 — `reset`·`checkout`은 **여전히 이 집합 안에 있다**. 위에서 뺀 것은
#   allow_reason의 두 좁은 형태(인덱스만 되돌리는 reset, --ours 병합 해결)뿐이고,
#   그 조건에 안 걸리는 나머지 reset·checkout(예: `--hard`·브랜치 전환·일반 파일 복구)은
#   여전히 여기 걸려 매번 ask다. GATED_GIT 자체를 좁히지 않은 이유: 이 상수를 직접
#   좁히면 두 함수의 조건을 다시 여기 베껴 써야 해서 판정이 두 곳에 흩어진다(이 리포가
#   반복해 겪은 "같은 질문에 답하는 자가 둘" 부류) — 판정은 allow_reason 쪽 함수 두 개에만 둔다.
GATED_GIT = {"reset", "checkout", "restore", "rebase"}
GATED_ASK_REASON = (
    "되돌리기 어려운 git 쓰기다 — **1회 허용**으로만 진행할 것. "
    "blocking PreToolUse 훅이 permission allow보다 먼저 평가되므로 이 ask는 유지된다. "
    "settings allow에 남은 중복 규칙은 설정 의도를 흐리므로 회귀 테스트가 따로 잡는다."
)


def session_root(payload=None):
    """이 세션이 선 폴더. 하네스가 주는 것을 먼저 믿고, 없으면 cwd 로 떨어진다."""
    return (os.environ.get("CLAUDE_PROJECT_DIR")
            or (payload or {}).get("cwd") or os.getcwd())


def session_has_no_subject(payload=None):
    """이 세션이 선 자리가 **git 워크트리가 아닌가** (= 과목이 없는 컨테이너 루트인가).

    ★ 판정을 «브랜치가 비었나» 로 하지 않는다 — detached HEAD 도 빈값이라 과목 워크트리를
      컨테이너로 오인한다. `--is-inside-work-tree` 는 그 둘을 정확히 가른다.
    ★ 못 읽으면 **False**(= 과목 워크트리)로 넘어진다. 여기서 True 로 넘어지면 git 이 잠깐
      느린 날 정상 커밋이 통째로 거부된다 — 이 판정의 값어치보다 그 피해가 크다.
    """
    root = (os.environ.get("CLAUDE_PROJECT_DIR")
            or (payload or {}).get("cwd") or os.getcwd())
    out = _git_output(["-C", str(root), "rev-parse", "--is-inside-work-tree"]).strip()
    return out == "false"


def read_payload(source=None):
    """훅 페이로드를 **UTF-8로** 읽는다. `json.load(sys.stdin)` 을 쓰지 말 것.

    `source` 는 테스트용 — bytes/str 을 직접 주거나 읽을 수 있는 스트림을 준다.

    열린 날 2026-07-27 — 이 리포에서 가장 오래 숨어 있던 결함이고, 사용자가 반복 지적한
    `git -C` 프롬프트의 **진짜 원인**이다.

    Windows에서 `sys.stdin` 의 인코딩은 **cp949**(ANSI 코드페이지)인데 하네스는 페이로드를
    **UTF-8**로 보낸다. 그래서 명령에 한글이 들어 있으면 조용히 깨진다(실측 기록):

        보낸 것 : …/Documents/전공정리프로젝트/math   ('전공정리프로젝트' 8자)
        읽은 것 : …/Documents/<깨진 13자>/math       (U+DCEC 등 **로운 대리쌍**이 섞인다)

    (실측 코드포인트는 원장 10번에 남겼다. 여기 그대로 적으면 소스에 로운 대리쌍이 박혀
     모듈 import 자체가 UnicodeEncodeError 로 죽는다 — 실제로 한 번 그렇게 만들었다.)

    **ASCII만 보는 규칙(echo·리디렉션·힙독·체인)은 멀쩡했기 때문에 가드가 동작하는 것처럼
    보였다.** 실제로는 비ASCII 문자열을 비교하는 규칙이 전부 죽어 있었다:
      ⑴ `redundant_git_c` — 경로 비교가 영원히 불일치 → `git -C <루트>` 가 계속 통과했다.
         (원장 8번이 "settings 캐시 때문으로 보인다"고 **추정**했는데 틀린 진단이었다.)
      ⑵ `foreign_subject_paths` — `data/열역학` 같은 한글 경로가 매칭되지 않아
         **과목 경계 강제가 통째로 무력**이었다(2026-07-25 정책이 기계로는 하나도 안 걸렸다).

    `json.loads` 는 bytes를 주면 UTF-8로 해석하므로 **버퍼에서 직접** 읽는다.
    """
    raw = source if isinstance(source, (bytes, str)) else (source or sys.stdin.buffer).read()
    if isinstance(raw, str):                      # 테스트가 문자열을 넘길 때
        raw = raw.encode("utf-8")
    return json.loads(raw.decode("utf-8", "replace"))


def _trace(command):
    """훅 **실행 시점**의 경로 인식을 파일로 남긴다 — `GUARD_TRACE=1` 일 때만.

    위 결함을 찾아낸 수단이라 남겨 둔다. 함수 단위 회귀 테스트는 `deny_reason(… PROJECT_ROOT …)`
    처럼 **자기가 계산한 값을 자기에게 물어보는** 형태가 되기 쉬워서, 훅 실행 시점의 값이
    어긋나 있어도 영원히 초록이다. 규칙이 테스트는 통과하는데 실제로 안 걸리면 이걸 켤 것.
    """
    if os.environ.get("GUARD_TRACE") != "1":
        return
    try:
        info = {"command": command, "abs": os.path.abspath(__file__),
                "project_root": PROJECT_ROOT, "norm_root": _norm(PROJECT_ROOT),
                "cwd": os.getcwd(), "repo_arg": repo_from_command(command),
                "norm_repo": _norm(repo_from_command(command) or ""),
                "redundant": redundant_git_c(command),
                "fsencoding": sys.getfilesystemencoding(),
                "stdin_encoding": getattr(sys.stdin, "encoding", "?")}
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".guard_trace.json"),
                  "w", encoding="utf-8", errors="backslashreplace") as fh:
            # ensure_ascii=True — 깨진 문자열이 섞여도 진단 파일 자체는 반드시 남게 한다.
            json.dump(info, fh, ensure_ascii=True, indent=1)
    except Exception:
        pass


def main():
    try:
        payload = read_payload()
    except Exception:
        return  # 입력을 못 읽으면 막지 않는다 — 가드가 작업을 인질로 잡아선 안 된다
    # ★ 2026-08-12 — matcher 를 `Bash|PowerShell` 로 넓히면서 필드 이름도 넓혔다.
    #   PowerShell 계열 툴이 명령을 `command` 가 아닌 이름으로 줄 수 있는데, 그 경우 빈
    #   문자열을 판정해 **조용히 전부 통과**한다(가드가 도는 것처럼 보이는 가장 나쁜 모양).
    ti = payload.get("tool_input") or {}
    command = str(ti.get("command") or ti.get("script") or ti.get("code") or "")
    _trace(command)

    _root = session_root(payload)
    reason = deny_reason(command, session_has_no_subject(payload), _root,
                         declared_subject(payload))
    if reason:
        _decide("deny", reason)
    reason = allow_reason(command, _root)
    if reason:
        _decide("allow", reason)
    if git_subcommand(command) in GATED_GIT:
        _decide("ask", GATED_ASK_REASON)


if __name__ == "__main__":
    main()
