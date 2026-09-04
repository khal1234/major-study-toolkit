#!/usr/bin/env python
"""공통 코어 신선도·편집 경고 훅 (2026-07-27 신설).

과목=브랜치 구조에서 공통 규칙(AGENTS.md·CLAUDE.md·.claude·tools·site/template·docs)은
**main이 정본**이고 각 과목 브랜치가 `git merge main`으로 받는다. 이 훅이 두 가지를 기계로 알린다:

  SessionStart          : main이 공통 경로에서 현재 브랜치보다 앞서 있으면 "먼저 merge하라" 경고.
  PreToolUse(Edit|Write): 공통 파일을 고치면 "커밋 후 즉시 main 반영, 다른 과목은 merge로 받게" 리마인더.

둘 다 **비차단 경고**다(작업을 막지 않는다 — additionalContext로 문맥에 한 줄 주입).
판정 로직은 순수 함수(`is_common_path`·`commits_behind_main`)에 두고
`tools/test_checks.py::test_common_guard`가 검증한다 — 규칙을 지우면 그 테스트가 깨진다.
"""
import json
import os
import re
import subprocess
import sys

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

# main이 정본인 공통 경로. 여기 커밋이 생기면 과목 브랜치는 merge로 받아야 한다.
# ★ `.gitignore` 는 2026-07-28에 들어왔다 — 아래 COMMON_FILES 주석 참조.
COMMON_PATHS = ["AGENTS.md", "CLAUDE.md", ".gitignore", ".claude/settings.json",
                ".claude/launch.json", ".claude/hooks", ".claude/skills", "tools",
                "site/template", "site/fonts", "docs"]

# 과목별(브랜치 고유)·로컬 — 공통이 아니다. **파일명 정확 일치**로만 제외한다.
# (부분문자열로 하면 `.claude/SUBJECT.md.template`이 `.claude/SUBJECT.md`에 걸려 오분류된다 — 실버그였다.)
SUBJECT_EXACT = ("/.claude/subject.md", "/.claude/settings.local.json")
COMMON_FILES = ("/agents.md", "/claude.md", "/.claude/settings.json",
                "/.claude/launch.json", "/.claude/subject.md.template",
                # .gitignore(2026-07-28 추가): 무엇을 커밋하느냐의 규칙이라 과목 무관이고,
                # 등록 검사가 **모든 과목**의 산출물 경로를 여기서 찾는다. 공통에서 빠져 있던
                # 동안 브랜치마다 갈라져 새 브랜치(dynamics)가 만들자마자 실패했다.
                # sync_common.SYNC_PATHS와 짝을 이룬다 — 한쪽만 넣으면 테스트가 깨진다.
                "/.gitignore")
# 디렉터리 — `/tools/foo.py`(안의 파일)와 `/tools`(디렉터리 자체) 둘 다 잡는다.
# `site/fonts` 는 2026-08-15에 들어왔다 — 실어 두는 웹폰트는 **공통 뷰어가 선언하는 것**이라
# 과목이 아니라 전 과목 한 벌이다. `sync_common.SYNC_PATHS` 와 짝을 이룬다(한쪽만 넣으면
# `SYNC_PATHS 항목은 공통이다` 회귀가 깨진다 — 실제로 그렇게 잡혔다).
COMMON_DIRS = ("/.claude/hooks", "/.claude/skills", "/tools", "/site/template",
               "/site/fonts", "/docs")


def is_common_path(path):
    """이 경로가 공통 코어인가(편집 시 main 반영 대상). 순수 함수 — 테스트 대상.

    절대·상대·역슬래시·디렉터리 경로 모두 받는다. `.claude/SUBJECT.md`·`settings.local.json`은
    과목별/로컬이라 공통에서 제외한다(그래서 이 판정이 먼저 온다).
    """
    p = path.strip().strip("'\"").replace("\\", "/").lower()
    if any(p.endswith(s) for s in SUBJECT_EXACT):
        return False
    if any(p.endswith(s) for s in COMMON_FILES):
        return True
    return any((d + "/") in p or p.endswith(d) for d in COMMON_DIRS)


def commits_behind_main(git_count_output):
    """`git rev-list --count HEAD..main -- <공통경로>` 출력 → 정수. 순수 함수 — 테스트 대상."""
    try:
        return int((git_count_output or "0").strip() or "0")
    except ValueError:
        return 0


# ★ 같은 파일을 한 세션에 여러 번 Edit 하는 것을 막는다 (열린 날 2026-07-27).
#
# 사용자 지적 — 승인이 필요하다는 것 자체엔 동의하지만, 매번 여러 번 뜨는 것은 불합리하다는 취지.
#
# **원인은 게이트가 아니라 에이전트의 위반이다.** AGENTS 실행 규율 4가 *"파일 편집도 배치로 —
# 한 파일에 여러 곳을 고칠 때 Edit 를 여러 번 나눠 부르지 말 것, 매번 승인이 뜬다"* 고 이미
# 적고 있는데, 그날 AGENTS.md 하나를 **Edit 6번**으로 나눠 불러 프롬프트가 6번 떴다.
# `ask` 에는 '세션 1회' 라는 눈금이 없으므로(매 호출 독립 매칭), 횟수를 줄이는 길은
# **호출을 합치는 것**뿐이다. 문서에만 있던 그 규칙을 여기서 기계가 강제한다.
#
# `Write`(전체 교체)는 세지 않는다 — 그게 바로 우리가 유도하려는 형태다.
EDIT_COUNTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".edit_counts.json")
GATED_RULE_FILES = ("/agents.md", "/claude.md")   # settings 를 못 읽을 때의 폴백(아래 참조)
EDIT_DENY_AT = 3                                  # 3번째 Edit 부터 거부 (2번까지는 경고)

# ★★ **범위를 settings 에서 끌어온다 — 목록을 두 벌 두지 않는다** (넓힌 날 2026-08-05).
#
#   **왜 다시 열렸나 (원장 11번의 재발).** 11번은 `AGENTS.md` 를 Edit 6번으로 나눈 사고였고,
#   처방으로 이 카운터를 넣으면서 대상을 **그때 문제가 된 두 파일**로 못 박았다. 그런데 승인
#   프롬프트를 만드는 것은 «규칙 파일» 이 아니라 **settings 의 `ask` 에 걸린 모든 Edit 대상**이다.
#   그래서 2026-08-05 기계재료 세션에서 `data/기계재료/index.json`(ask 에 있다)을 3번,
#   `tools/**`(ask 에 있다)을 여러 번 나눠 불렀는데 **카운터가 한 번도 돌지 않았다.**
#   사용자 재지적 — 같은 부류의 승인이 계속 개별로 뜨는데 왜 한 번에 몰아서 처리가 안 되냐는 취지(다른 브랜치는 한 번만 뜨는데 이쪽만 반복됨).
#   → 원인은 «에이전트가 또 잊었다» 가 아니라 **처방의 범위가 증상 하나에 맞춰져 있었던 것**이다.
#   같은 세션에서 사용자가 **세 번째**로 지적한 뒤에야 이 자리를 봤다는 것이 그 증거다.
#
#   그래서 하드코딩 목록을 지우고 `settings.json` 의 `permissions.ask` 에서 `Edit(...)`·
#   `MultiEdit(...)` 패턴을 읽어 온다. 사본을 두면 settings 에 새 ask 가 늘 때마다 갈라진다
#   (이 리포가 여러 번 겪은 부류다). 잠금은 `test_checks.py::test_edit_counter_covers_ask_globs`
#   — settings 의 모든 Edit ask 항목이 이 매처에 걸리는지 본다.
_ASK_EDIT_CACHE = None                             # None = 아직 안 읽음, [] = 읽었는데 없음


def ask_edit_patterns(settings_text):
    """settings 본문 → ask 에 걸린 Edit 대상 glob 목록. 순수 함수 — 테스트 대상."""
    try:
        data = json.loads(settings_text or "{}")
    except ValueError:
        return []
    out = []
    for entry in ((data.get("permissions") or {}).get("ask") or []):
        m = re.match(r"^(?:Edit|MultiEdit)\((.+)\)$", str(entry).strip())
        if m:
            out.append(m.group(1).replace("\\", "/").lower())
    return out


def glob_hits(pattern, path):
    """`Edit(...)` 의 glob 이 이 경로를 가리키는가. 순수 함수 — 테스트 대상.

    `**` 는 경로 구분자를 넘고 `*` 는 넘지 않는다 — 하네스의 권한 glob 과 같은 규약이다.
    경로는 **끝에서** 맞춘다(설정은 리포 상대 경로, 훅이 받는 것은 절대 경로다).
    """
    p = str(path).replace("\\", "/").lower().lstrip("/")
    rx, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            rx, i = rx + "(?:.*/)?", i + 3      # 디렉터리 0개 이상
        elif pattern.startswith("**", i):
            rx, i = rx + ".*", i + 2            # 나머지 전부(구분자 포함)
        elif pattern[i] == "*":
            rx, i = rx + "[^/]*", i + 1         # 한 칸 안에서만
        else:
            rx, i = rx + re.escape(pattern[i]), i + 1
    return re.search(r"(?:^|/)" + rx + r"$", p) is not None


def is_ask_gated(path, patterns=None):
    """이 경로가 승인 프롬프트를 만드는가(= 나눠 부르면 그만큼 클릭이 는다). 순수 함수."""
    pats = _ask_patterns() if patterns is None else patterns
    if pats and any(glob_hits(g, path) for g in pats):
        return True
    p = str(path).replace("\\", "/").lower()
    return any(p.endswith(s) for s in GATED_RULE_FILES)   # settings 를 못 읽을 때의 폴백


def edit_verdict(count, path, patterns=None):
    """이번이 `count` 번째 Edit 일 때의 판정. 순수 함수 — 테스트 대상.

    반환 `(None|"warn"|"deny", 사유)`. **거부는 `ask` 에 걸린 경로에만** 한다 — 거기서만
    나눠 부른 만큼 사용자가 실제로 클릭하기 때문이다. 나머지는 경고에 그친다:
    넓게 거부하면 정상 작업까지 인질로 잡는다(가드가 작업을 막아선 안 된다는 원칙).
    """
    if is_ask_gated(path, patterns) and count >= EDIT_DENY_AT:
        return ("deny",
                "이 파일을 이번 세션에 " + str(count) + "번째 Edit 하려 한다 — 차단됨"
                "(AGENTS 실행 규율 4: 파일 편집도 배치로). 이 파일은 settings 의 `ask` 에 걸려 "
                "**Edit 한 번마다 승인 프롬프트가 뜬다.** `ask` 에는 '세션 1회' 가 없어서 "
                "나눠 부른 만큼 그대로 사용자가 클릭해야 한다.\n"
                "→ **남은 변경을 전부 설계한 뒤 `Write` 로 파일을 통째로 교체할 것**"
                "(`Write` 는 세지 않는다). 지금까지의 변경을 되돌릴 필요는 없다 — "
                "남은 것만 합쳐서 한 번에 쓰면 된다.")
    if count >= 2:
        return ("warn",
                "이 파일을 이번 세션에 " + str(count) + "번째 고치고 있다. 남은 변경이 더 있으면 "
                "**한 번의 `Write` 로 몰 것**(실행 규율 4 — 나눠 부르면 승인 프롬프트가 그만큼 뜬다).")
    return (None, "")


def bump(counts, session, path):
    """세션·파일별 편집 횟수를 1 올리고 (새 counts, 이번 횟수) 를 돌려준다. 순수 함수 — 테스트 대상.

    세션이 바뀌면 이전 세션 기록은 버린다 — 파일이 무한히 자라지 않게.
    """
    key = str(path).replace("\\", "/").lower()
    if counts.get("session") != session:
        counts = {"session": session, "files": {}}
    files = dict(counts.get("files") or {})
    files[key] = int(files.get(key, 0)) + 1
    return {"session": session, "files": files}, files[key]


# ★ 교재 폴더 읽기 권한을 **각 워크트리가 스스로 고친다** (열린 날 2026-07-28, 승인 원장 17).
#
# 사용자 지적 — 다른 브랜치에서 다른 과목 폴더를 열어도 같은 문제가 재발한다는 것, 그 브랜치들에는 별도로 시킨 작업이 없었다는 취지.
#
# **원장 17 의 실측:** `.claude/settings.json`(project) 에 등록된 디렉터리는 **그 폴더 하나만**
# 열리고 하위 트리는 안 열린다. `.claude/settings.local.json`(워크트리 전용) 항목만 하위를 연다.
# 교재는 언제나 하위(`2-1/9. 기계재료/…`)에 있으므로 project 등록만으로는 못 읽는다.
#
# 그래서 **project 에 이미 등록된 경로를 그 워크트리의 local 로 복제**한다.
#   · **새 권한은 하나도 열리지 않는다** — 출처가 project 의 목록뿐이고, 거기 없는 경로는
#     절대 추가하지 않는다(그게 아래 함수가 project 목록만 인자로 받는 이유다).
#   · **쓰기는 안 넓어진다** — settings 의 `deny` 에 `Edit/Write(google drive_excess/**)` 가 그대로다.
#   · 과목마다 값을 따로 정할 필요가 없다. 새 교재 경로는 project 에 한 번 넣고 sync 하면
#     각 워크트리가 다음 세션에 스스로 받는다 — **브랜치별 수작업이 0이 되는 것이 이 조치의 목적이다.**
#
# settings 는 세션 시작 시점에 캐시되므로 **효과는 다음 세션부터**다. 그래서 바꿨을 때만 한 줄 알린다.
LOCAL_SETTINGS = os.path.join(PROJECT_DIR, ".claude", "settings.local.json")
PROJECT_SETTINGS = os.path.join(PROJECT_DIR, ".claude", "settings.json")


def _ask_patterns():
    """settings 의 Edit ask 목록(한 번만 읽어 캐시). 못 읽으면 빈 목록 → 위 폴백이 받는다."""
    global _ASK_EDIT_CACHE
    if _ASK_EDIT_CACHE is None:
        try:
            with open(PROJECT_SETTINGS, encoding="utf-8") as fh:
                _ASK_EDIT_CACHE = ask_edit_patterns(fh.read())
        except OSError:
            _ASK_EDIT_CACHE = []
    return _ASK_EDIT_CACHE


# ★ 복제 대상은 디렉터리**만이 아니다** — `allow` 도 같다 (열린 날 2026-08-01, 승인 원장 19).
#
# 사용자 — 왜 이 명령에 모두-허용 승인창이 뜨는지 물었다. 「wscript tools/serve_site.vbs」가 **두 번째로** 떴다
# (원장 18 이 같은 명령, dynamics 세션).
#
# **부류를 절반만 옮긴 것이 원인이다.** 위 원장 17 의 실측은 *"project 항목은 이 하네스에서
# 안 먹고 local 이라야 먹는다"* 인데, 그건 디렉터리만의 성질이 아니다 — `allow` 규칙도 똑같이
# project 에만 있으면 Bash 매칭에 안 걸린다(18·19 에서 `Bash(wscript tools/serve_site.vbs*)` 가
# project 에 **있는데도** 승인창이 떴다). 그런데 이 훅은 `additionalDirectories` 만 복제했다.
#
# 18 번의 조치는 *"그 워크트리의 local 에 손으로 두 줄 넣기"* 였는데 이 파일은 `.gitignore` 라
# **다른 워크트리로 갈 길이 없다.** 그래서 워크트리를 열 때마다 사람이 같은 손질을 반복해야 했고,
# 반복하지 않으면 재발한다 — solids 에서 그대로 재발했다. 손질을 기억하는 대신 **복제 범위를 넓힌다.**
#
# 권한 확대는 0 이다: 출처가 project 의 목록뿐이고 거기 없는 항목은 절대 만들지 않는다.
MIRRORED_KEYS = ("additionalDirectories", "allow")


def _norm(key, value):
    """비교용 정규화 — 경로는 대소문자·구분자를 무시하고, 규칙 문자열은 그대로 본다."""
    if key == "additionalDirectories":
        return os.path.normcase(os.path.normpath(str(value)))
    return str(value)


def mirror_perms(project_perms, local_text):
    """project 의 `MIRRORED_KEYS` 를 local 에 채운다 → (새 local 텍스트|None, {키: 추가된 목록}).

    순수 함수 — 테스트가 직접 부른다. 바뀔 것이 없으면 `(None, {})`.
    **project 목록 밖의 항목은 만들어내지 않는다** — 권한이 넓어지지 않는다는 보장이 여기 있다.
    """
    data = json.loads(local_text) if (local_text or "").strip() else {}
    perms = data.setdefault("permissions", {})
    added = {}
    for key in MIRRORED_KEYS:
        mine = perms.setdefault(key, [])
        have = {_norm(key, v) for v in mine}
        new = [v for v in (project_perms or {}).get(key) or []
               if _norm(key, v) not in have]
        if new:
            mine.extend(new)
            added[key] = new
    if not added:
        return None, {}
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n", added


def mirror_dirs(project_dirs, local_text):
    """예전 이름 — 디렉터리만 복제한다. 회귀 테스트와 옛 호출부를 위해 남긴다."""
    text, added = mirror_perms({"additionalDirectories": project_dirs}, local_text)
    return text, added.get("additionalDirectories", [])


def _repair_local_dirs():
    """project 의 디렉터리·allow 를 이 워크트리의 local 에 반영한다. 실패해도 조용히 넘어간다."""
    try:
        with open(PROJECT_SETTINGS, encoding="utf-8") as fh:
            wanted = json.load(fh).get("permissions") or {}
        local_text = ""
        if os.path.isfile(LOCAL_SETTINGS):
            with open(LOCAL_SETTINGS, encoding="utf-8") as fh:
                local_text = fh.read()
        text, added = mirror_perms(wanted, local_text)
        if not added:
            return []
        with open(LOCAL_SETTINGS, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        # 알림은 한 줄로 — 무엇이 몇 건 늘었는지만. 목록 전체를 찍으면 매번 화면을 먹는다.
        return [k + " " + str(len(v)) + "건" for k, v in added.items()]
    except Exception:
        return []          # 권한 보정 실패가 세션을 막아선 안 된다


def _git(args):
    # encoding="utf-8" 을 빼면 안 된다 — text=True 는 로케일 인코딩(Windows=cp949)으로 디코드해
    # 한글 경로가 섞인 출력이 깨지거나 UnicodeDecodeError 로 죽는다(2026-07-27 부류 결함).
    try:
        return subprocess.run(["git", "-C", PROJECT_DIR] + args, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=5).stdout
    except Exception:
        return ""


def read_payload(source=None):
    """훅 페이로드를 **UTF-8로** 읽는다. `json.load(sys.stdin)` 을 쓰지 말 것.

    Windows의 `sys.stdin` 인코딩은 cp949 인데 하네스는 UTF-8 로 보낸다 → 한글이 깨진다.
    guard_bash 에서 이 결함이 `git -C` 차단과 **과목 경계 강제**를 통째로 무력화하고 있었다
    (2026-07-27 실측). 여기 `is_common_path` 는 ASCII 경로만 보지만 같은 부류라 함께 고친다 —
    `data/공학수학 1/…` 처럼 한글이 든 경로를 판정에 쓰게 되는 순간 같은 방식으로 죽는다.
    """
    raw = source if isinstance(source, (bytes, str)) else (source or sys.stdin.buffer).read()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return json.loads(raw.decode("utf-8", "replace"))


def _emit(event, context):
    json.dump({"hookSpecificOutput": {
        "hookEventName": event, "additionalContext": context}}, sys.stdout)
    sys.exit(0)


def _decide(decision, reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}, sys.stdout)
    sys.exit(0)


def _load_counts():
    try:
        with open(EDIT_COUNTS, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_counts(counts):
    try:
        with open(EDIT_COUNTS, "w", encoding="utf-8") as fh:
            json.dump(counts, fh, ensure_ascii=False)
    except Exception:
        pass          # 세는 데 실패했다고 작업을 막지 않는다


def main():
    try:
        payload = read_payload()
    except Exception:
        return  # 입력을 못 읽으면 조용히 통과 — 경고 훅이 작업을 막아선 안 된다
    event = payload.get("hook_event_name") or payload.get("hookEventName") or ""

    # SessionStart(세션 시작) + UserPromptSubmit(매 채팅 턴) 둘 다에서 검사한다.
    # 세션 시작만 검사하면 세션 도중 다른 과목이 올린 것을 못 잡는다(2026-07-27 충돌 사고).
    # 매 턴 검사는 git rev-list 한 번뿐이고, 낡았을 때만 한 줄 출력 → 평소 토큰 0.
    if event in ("SessionStart", "UserPromptSubmit"):
        notes = []
        # ★ 매 턴 검사한다(세션 시작에서만 하지 않는다). 다른 과목이 `git merge main` 으로 이 훅을
        #    **세션 도중** 받기 때문이다 — 그 세션의 SessionStart 는 이미 지나갔으므로 시작에서만
        #    고치면 복제가 다음 세션으로, 적용은 그 다음 세션으로 밀려 **두 세션을 기다린다.**
        #    매 턴 도는 비용은 작은 JSON 두 개를 읽는 것뿐이고(바로 아래 rev-list 보다 싸다),
        #    **바뀔 것이 있을 때만 쓴다**(`mirror_dirs` 가 없으면 `(None, [])`).
        added = _repair_local_dirs()
        if added:
            notes.append(
                "🔧 교재 폴더 읽기 권한을 이 워크트리의 `.claude/settings.local.json` 에 "
                "복제했다 — " + ", ".join(os.path.basename(str(a).rstrip("\\/")) or str(a)
                                          for a in added) + ". "
                "project 설정의 항목은 **그 폴더 하나만** 열고 하위를 못 열어서, 교재가 있는 "
                "하위 폴더마다 승인창이 떴다(승인 원장 17). **효과는 다음 세션부터**다 — "
                "settings 는 세션 시작 때 캐시된다. 이번 세션에서 교재 하위 폴더를 열면 "
                "아직 한 번 뜰 수 있다.")
        n = commits_behind_main(_git(["rev-list", "--count", "HEAD..main", "--"] + COMMON_PATHS))
        if n > 0:
            notes.append(
                "⚠️ 공통 코어(AGENTS.md·CLAUDE.md·.claude·tools·site/template·docs)가 "
                "main에서 " + str(n) + "커밋 앞서 있다. 작업을 잇기 전에 먼저 "
                "`git merge main` 으로 받아라(과목=브랜치, main이 공통 정본).")
        if notes:
            _emit(event, "\n".join(notes))
        return

    if event == "PreToolUse":
        tool = payload.get("tool_name") or ""
        if tool not in ("Edit", "Write", "MultiEdit"):
            return
        path = str((payload.get("tool_input") or {}).get("file_path", ""))
        note = ""

        # 횟수는 **모든 파일**에 대해 센다. 거부는 `ask` 에 걸린 경로에만 하고(거기서만 실제로
        # 클릭이 는다) 나머지는 2번째부터 경고다 — 세지 않으면 경고조차 못 낸다는 것이
        # 원장 11번이 좁게 닫혀 재발한 이유다(위 `ask_edit_patterns` 주석이 전말).
        # `Write` 는 세지 않는다 — 그게 우리가 유도하려는 형태다.
        session = payload.get("session_id") or payload.get("sessionId")
        if tool in ("Edit", "MultiEdit") and session and path:
            counts, n = bump(_load_counts(), session, path)
            _save_counts(counts)
            verdict, reason = edit_verdict(n, path)
            if verdict == "deny":
                _decide("deny", reason)
            if verdict == "warn":
                note = "\n" + reason

        if is_common_path(path):
            _emit("PreToolUse",
                  "공통 파일을 수정 중이다(전 과목 공유). 커밋 후 **즉시 main에 반영**하고 "
                  "다른 과목 세션은 `git merge main`으로 받게 하라 — 브랜치에만 두면 갈라진다." + note)
        elif note:
            _emit("PreToolUse", note.strip())
        return


if __name__ == "__main__":
    main()
