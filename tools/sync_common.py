#!/usr/bin/env python
"""공통 코어를 현재 과목 브랜치 → main 정본으로 반영하는 도구 (2026-07-27 신설).

**왜 이 도구인가 (2026-07-27 실사고 재발 방지, AGENTS 규칙 7⑷):**
공통 파일을 손으로 골라 `git checkout`으로 main에 복사하다 `.claude/hooks/guard_bash.py`를
빠뜨렸고, settings.json이 없는 훅을 참조 → 훅이 exit 2 → **main·math에서 Bash가 전면 차단**됐다.
손으로 고르면 또 빠뜨린다. 이 도구는 **공통 표면 전체를 통째로** 옮겨 누락을 구조적으로 막고,
git을 subprocess로 돌려(훅·settings ask를 안 탐) 승인 프롬프트도 없앤다.

공통 = AGENTS.md·CLAUDE.md·.claude(단 SUBJECT.md·settings.local.json 제외)·tools·site/template·docs.
과목별(SUBJECT.md·data·site/<과목>)은 옮기지 않는다.

절차: 현재 브랜치의 **커밋된** 공통 파일을 main worktree에 checkout → main에 커밋 →
      main을 현재 브랜치로 merge(동기 유지). 반영할 변경이 없으면 커밋하지 않는다.
      → 마지막에 **공용 시스템 폴더(`~/Documents/naru`) 미러**까지 한다(2026-08-14 신설).
        무엇을 옮길지는 `docs/shared-mirror.txt` 대장이 정한다 — 공통 표면 전체가 아니다.
사용: (공통 파일을 고쳐 현재 브랜치에 커밋한 뒤)  python tools/sync_common.py
"""
import json
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # 콘솔 cp949가 한글·em-dash를 못 찍는다
sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # 오류 메시지만 깨지는 것을 막는다

# 옮길 공통 경로 — 디렉터리는 통째로(손으로 파일 고르지 않는다. 그게 이 사고의 원인이었다).
# .gitignore(2026-07-28 추가): 무엇을 커밋하느냐의 규칙이라 과목과 무관한 공통이다.
# 빠져 있는 동안 브랜치마다 갈라졌고, 등록 검사(test_subject_registration_is_complete)는
# .gitignore가 **모든 과목**의 산출물 경로를 나열하기를 요구하는데 정작 그 파일이 동기화되지
# 않아 새 브랜치(dynamics)에서 곧바로 실패했다 — 검사와 동기화 범위가 어긋난 것이 원인이다.
# (solids 세션도 같은 날 독립적으로 같은 결론에 도달했다 — math의 SUBJECT.md 추적 조치가
#  main을 못 거쳐 새 워크트리가 낡은 .gitignore를 들고 태어났다.)
SYNC_PATHS = ["AGENTS.md", "CLAUDE.md", ".gitignore",
              ".claude/settings.json", ".claude/launch.json",
              ".claude/hooks", ".claude/skills", ".claude/SUBJECT.md.template",
              # ★ `site/fonts` 는 공통이다 (2026-08-15). 글꼴을 **선언하는 자리가 공통
              #   템플릿**이라 12과목이 같은 네 얼굴을 요구하는데, 파일이 thermo 브랜치에만
              #   있어서 나머지 과목은 woff2 404 를 내고 시스템 폴백으로 그려지고 있었다
              #   (실측 2026-08-15, 고체역학 ch05: 얼굴 4개 전부 `status: error`).
              #   실어 두는 한 벌은 `font_subset.py … --all-subjects` 로 만든 **합집합**이다.
              "tools", "site/template", "site/fonts", "docs"]
# 공통이 아니다 — 절대 옮기지 않는다(브랜치 고유/로컬).
NEVER_SYNC = [".claude/SUBJECT.md", ".claude/settings.local.json"]

# ★ `tools/` 아래 있지만 과목마다 이름은 같고 **내용이 다른** 파일 — 통째로 옮기면 마지막에
#   sync한 과목이 다른 과목 것을 덮어쓴다(2026-09-03 실사고: 응용열역학이 `commit.py`로
#   `tools/gen_steam_tables.py`를 커밋하자 이 도구가 그것을 "공통"으로 보고 main에 그대로
#   올렸고, main이 이미 갖고 있던 열역학판(물, `data/열역학/…`)을 응용열역학판(같은 이름,
#   `data/응용열역학/…`)으로 덮었다 — 다음에 열역학이 `merge main`을 받으면 자기 것과
#   충돌했을 자리다). `.claude/hooks/guard_bash.py`의 `SUBJECT_OWNED_TOOL_BASENAMES`·
#   `is_subject_owned_tool_path`와 **같은 목록이어야 한다** — 갈리면 한쪽만 막고
#   한쪽은 계속 샌다. (그 모듈을 import하지 않는 이유는 guard_bash 자신의 주석이 정본이다 —
#   훅이 리포 코드에 매달리면 그쪽이 깨질 때 함께 죽는다.)
SUBJECT_OWNED_TOOL_BASENAMES = {"gen_steam_tables.py", "verify_steam_tables.py"}
_SUBJECT_ANSWER_VERIFIER_RE = re.compile(r"^verify_[a-z0-9]+_answer\.py$")


def is_subject_owned_tool_path(name):
    """`tools/<file>` 이고 file 이 과목마다 갈라지는 이름으로 알려져 있는가. 순수 함수."""
    n = str(name).replace("\\", "/")
    if not n.startswith("tools/") or "/" in n[len("tools/"):]:
        return False
    base = n[len("tools/"):]
    return base in SUBJECT_OWNED_TOOL_BASENAMES or bool(_SUBJECT_ANSWER_VERIFIER_RE.match(base))


def staged_subject_files(staged_names):
    """스테이징 목록에서 과목별 파일만 골라낸다. **정확 일치 — 부분 문자열이 아니다.**

    2026-08-01 실사고: 판정이 `any(n in ln for n in NEVER_SYNC)` 라는 부분 문자열 검사여서
    `.claude/SUBJECT.md.template`(SYNC_PATHS에 **있는 공통 파일**)이 `.claude/SUBJECT.md` 를
    문자열로 포함한다는 이유로 매번 커밋에서 빠졌다. 즉 **템플릿을 고쳐도 main에 영영 안 올라갔고**,
    출력에는 "과목별 파일을 제외함" 경고만 떠서 정상 동작처럼 보였다.
    (발견 경위: 기계재료가 '지문 언어' 항목을 템플릿에 넣어 sync 했더니 그 경고가 떴다.
     **템플릿은 정책이 과목마다 갈라지는 것을 막으려고 있는 파일인데, 그 파일이 갈라지고 있었다.**)

    판정을 함수로 뽑은 이유는 guard_bash.deny_reason 과 같다 — main() 안에 있으면 테스트가 못 본다.
    """
    return [ln for ln in staged_names if ln.strip() in NEVER_SYNC]


def common_paths_in(names):
    """파일 목록에서 **이 도구가 실제로 main 에 옮길 것**만 골라낸다. 순수 함수 — 테스트 대상.

    열린 날 2026-08-13 — `tools/commit.py` 가 커밋 직후 이 도구를 자동으로 부르게 하면서
    필요해졌다(공통을 고쳐 커밋하고 main 반영을 하루에 두 번 빠뜨린 사고). 그때
    *"무엇이 공통인가"* 를 부르는 쪽에 다시 적으면 **목록이 두 벌**이 되어 반드시 갈라진다 —
    이 리포가 여러 번 겪은 부류라(폴백 사전·검사 두 벌) 판정을 여기 하나로 둔다.
    공통의 정의는 SYNC_PATHS·NEVER_SYNC 뿐이고 이 함수는 그것을 읽기만 한다.

    경계는 **경로 구분자**다 — `tools/x.py` 는 걸리고 `toolsmith/x.py` 는 안 걸린다.
    NEVER_SYNC 제외는 **정확 일치**로만 한다(부분 문자열로 하면 `.claude/SUBJECT.md.template`
    이 `.claude/SUBJECT.md` 에 걸려 오분류된다 — 위 `staged_subject_files` 의 2026-08-01 실사고).
    """
    out = []
    for raw in names:
        n = str(raw).strip().strip('"').replace("\\", "/")
        if n.startswith("./"):
            n = n[2:]
        if not n or n in NEVER_SYNC:
            continue
        if any(n == p or n.startswith(p + "/") for p in SYNC_PATHS):
            out.append(n)
    return out


def sync_command_plan(main_path, branch, paths=None):
    """main 워크트리에서 돌릴 git 명령 순서. **순수 함수 — 테스트가 직접 부른다.**

    핵심은 rm이 checkout보다 **먼저** 온다는 것이다.

    열린 날 2026-07-28 (dynamics 세션 실측) — `git checkout <브랜치> -- <경로>`는 소스
    브랜치에서 **삭제된 파일을 반영하지 않는다**(추가·수정만 옮긴다). 그래서 한 번 main에
    올라간 파일은 어느 브랜치에서 지워도 main에서 **부활**했다: thermo가 우회 도구
    `tools/push.py`를 지웠는데 main에 남아 있었고, 새 브랜치가 그것을 물려받아 회귀
    테스트 2건이 곧바로 깨졌다. 삭제가 안 옮겨지는 것은 '누락'이 아니라 **명령의 성질**이라
    사람이 조심해서는 못 막는다.

    → 대상 경로를 index·워킹트리에서 통째로 지운 뒤 소스 브랜치에서 다시 받는다.
      결과 상태 = 소스 브랜치의 그 경로 전체(삭제 포함). `--ignore-unmatch`는 아직 main에
      없는 경로(새 공통 파일)에서 rm이 실패하지 않게 한다.
    """
    paths = list(paths if paths is not None else SYNC_PATHS)
    return [
        ["-C", main_path, "rm", "-r", "-q", "--ignore-unmatch", "--"] + paths,
        ["-C", main_path, "checkout", branch, "--"] + paths,
    ]


def _git(args, cwd=None):
    # 한글 경로 때문에 인코딩을 utf-8로 못박는다(기본 cp949는 worktree 경로에서 깨진다).
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def main_worktree_path(worktree_list_porcelain):
    """`git worktree list --porcelain` 출력에서 main 브랜치의 worktree 경로. 순수 함수 — 테스트 대상."""
    path = None
    for line in worktree_list_porcelain.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):].strip()
        elif line.strip() == "branch refs/heads/main":
            return path
    return None


AGENT_WORKTREE_MARK = os.path.join(".claude", "worktrees")


def mergeable_worktrees(worktree_list_porcelain, main_branch="main"):
    """`main` 을 받아야 할 워크트리 `(경로, 브랜치)` 목록. 순수 함수 — 테스트 대상.

    ★ 왜 이 자리인가 (열린 날 2026-08-15). 공통을 고쳐 main 에 올려도 **각 갈래가 스스로
      `git merge main` 을 쳐야** 받는다. 갈래가 다섯일 때도 실측으로 **두 개를 건너뛰었고**
      (그날 미커밋이 있어서), 과목이 서른이 되면 «공통 수정 한 번에 손으로 서른 번» 이 된다.
      빠뜨린 갈래는 조용히 **낡은 규격으로 작업**하는데, 그건 이 리포가 가장 비싸게 겪은 부류다
      (2026-07-27 클로버 사고의 반대 방향).
    ★ **여기서 거르는 것 셋** — 나머지 판정(더러운가)은 파일시스템을 봐야 하므로 호출자가 한다:
      ⑴ main 자신 ⑵ 브랜치 없는(detached) 워크트리 ⑶ `.claude/worktrees/` 아래 에이전트 사본.
      셋 다 `deploy_all.deployable_worktrees` 가 이미 쓰는 판정선이다 — 같은 질문에 답하는
      자를 둘로 만들지 않으려고 **이유도 같게** 적어 둔다.
    """
    out, cur = [], None
    for line in worktree_list_porcelain.splitlines():
        if line.startswith("worktree "):
            cur = {"path": line[len("worktree "):].strip(), "branch": None}
        elif line.startswith("branch ") and cur is not None:
            ref = line[len("branch "):].strip()
            cur["branch"] = ref.split("/")[-1] if "/" in ref else ref
            if (cur["branch"] and cur["branch"] != main_branch
                    and AGENT_WORKTREE_MARK not in os.path.normpath(cur["path"])):
                out.append((cur["path"], cur["branch"]))
            cur = None
    return out


def cmd_merge_all(root):
    """깨끗한 갈래 전부에 `git merge main`. **더러운 갈래는 건드리지 않고 이름을 찍는다.**

    ★ 왜 건너뛰나: 그 워크트리는 **다른 세션이 작업 중**일 수 있고, 반쯤 고친 상태에 머지를
      끼얹으면 남의 작업을 흔든다. 「빠뜨림」과 「일부러 안 함」이 구별되게 **건너뛴 것을 찍는다** —
      찍지 않으면 조용히 낡은 갈래가 생기고, 그게 이 도구가 없애려는 바로 그 상태다.
    """
    porcelain = _git(["worktree", "list", "--porcelain"], cwd=root).stdout
    targets = mergeable_worktrees(porcelain)
    if not targets:
        print("[merge-all] 받을 갈래가 없다.")
        return 0
    merged, skipped, failed = [], [], []
    for path, branch in targets:
        if _git(["-C", path, "status", "--porcelain"]).stdout.strip():
            skipped.append(branch)
            continue
        r = _git(["-C", path, "merge", "main", "--no-edit"])
        (merged if r.returncode == 0 else failed).append(branch)
        if r.returncode != 0:
            # 충돌은 여기서 풀지 않는다 — 그 갈래의 세션이 자기 맥락에서 푼다.
            _git(["-C", path, "merge", "--abort"])
    if merged:
        print("[merge-all] 받음 " + str(len(merged)) + "개: " + ", ".join(merged))
    if skipped:
        print("[merge-all] 건너뜀(미커밋 있음) " + str(len(skipped)) + "개: " + ", ".join(skipped)
              + "\n        → 그 갈래 세션에서 직접 `git merge main` 할 것")
    if failed:
        print("[merge-all] ★ 충돌로 실패 " + str(len(failed)) + "개: " + ", ".join(failed)
              + "\n        → 머지는 되돌렸다. 그 갈래 세션에서 풀 것")
    return 0


# ── 공용 시스템 폴더 미러 (2026-08-14 신설) ──────────────────────────────────
#
# **왜 여기인가.** `CLAUDE.md` 는 「공통을 고쳐 이 도구를 돌린 **바로 그 자리에서** 같은 파일을
# `~/Documents/naru` 에도 복사한다」고 요구해 왔는데, 그 복사를 **사람이 손으로 쳤다.**
# 안 쳐도 빌드·회귀·`close_report` 가 전부 초록이라 «빠뜨린 것»과 «맞은 것»이 구별되지 않았다
# (규칙 11). 게다가 감시가 **한 방향뿐**이었다 — `shared_sync_check` 훅은 *공용 → 리포* 만 보고
# *리포 → 공용* 이 낡는 것은 아무도 안 봤다. 공용 폴더는 «새 프로젝트를 만들 때 참조하는 자리»라
# 낡으면 **낡은 규칙이 새 프로젝트로 복제**되는데, 그 사실이 거기서는 안 보인다.
# → 트리거를 «반드시 하는 일»로 옮긴다. `commit.py` 가 이 도구를 부르게 한 것과 같은 조치다.
MIRROR_MANIFEST = "docs/shared-mirror.txt"


def mirror_entries(text):
    """대장 → `[(리포 경로, 공용 경로)]`. 순수 함수 — 테스트 대상.

    형식은 `리포경로 | 공용경로 | 사유` 이고 **사유 없는 줄은 항목으로 안 친다** —
    이 리포의 다른 대장(`orphan-checks-allow.txt`·`check-erosion-allow.txt`)과 같은 규약이다.
    """
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3 or not all(parts[:3]):
            continue
        out.append((parts[0].replace("\\", "/"), parts[1].replace("\\", "/")))
    return out


def same_text(a, b):
    """줄끝(CRLF/LF)만 다른 것은 **같은 내용**으로 본다. 순수 함수 — 테스트 대상.

    열린 날 2026-08-14, **첫 실행 당일**. 바이트로 비교했더니 6건이 통째로 「충돌」로 떴는데
    `git diff` 로 재 보니 **넷은 줄끝만 달랐다.** 윈도우에서는 리포 쪽이 CRLF 로 체크아웃되고
    공용 폴더 사본은 LF 로 남아 있어서, 그대로 두면 **모든 파일이 영원히 다르다** —
    그러면 미러는 매번 덮거나 매번 신고하고, 그 신고는 곧 소음이 되어 아무도 안 읽는다.
    (겸사겸사: 그날 내가 병렬로 돌린 `git diff` 네 개의 결과가 서로 뒤섞여 나와, 그 값으로
     «양쪽이 갈렸다» 고 단정할 뻔했다. **재 볼 때는 한 번에 하나씩** — 규칙 11.)
    """
    return a.replace(b"\r\n", b"\n") == b.replace(b"\r\n", b"\n")


def mirror_plan(entries, repo_bytes, shared_bytes, last_seen, has_lock, digest):
    """항목마다 처분을 정한다. **파일을 안 건드리는 순수 함수** — 테스트가 직접 부른다.

    `repo_bytes`·`shared_bytes` 는 «경로 → bytes 또는 None(없음)» 을 주는 함수,
    `last_seen` 은 공용 폴더를 마지막으로 확인했을 때의 «공용경로 → 지문»
    (`.claude/hooks/.shared-system.lock`), `digest` 는 그 지문을 뜨는 함수다.

    ★ **「충돌」이 이 함수의 존재 이유다.** 그냥 덮으면 *공용 쪽에서 고친 것을 소리 없이 지운다* —
      공용은 여러 프로젝트가 함께 쓰는 자리라 남이 고쳐 두었을 수 있다. 공용 파일이 lock 의
      지문과 다르면 «우리가 모르는 사이에 바뀐 것» 이므로 **덮지 않고 신고**한다.
      받아올지는 사람이 판정하고, 그 알림은 `shared_sync_check` 훅이 이미 띄운다.
    ★ **`digest` 를 인자로 받는 이유**: 지문 방식을 여기 다시 적으면 lock 을 쓰는 쪽과 읽는 쪽이
      갈려 판정이 통째로 거짓말이 된다. 판정을 하나로 두고 **주입**한다.
    ★ lock 이 아예 없으면 기준선이 없는 첫 실행이라 충돌을 묻지 않는다 — 그 훅이 첫 실행에서
      조용히 기준을 잡는 것과 같은 판단이다(전부 충돌로 뜨면 그 신고는 소음이 된다).
    """
    out = []
    for repo_rel, shared_rel in entries:
        mine = repo_bytes(repo_rel)
        if mine is None:
            out.append((repo_rel, shared_rel, "없음"))
            continue
        theirs = shared_bytes(shared_rel)
        if theirs is None:
            out.append((repo_rel, shared_rel, "새로"))
        elif same_text(theirs, mine):
            out.append((repo_rel, shared_rel, "같음"))
        elif has_lock and last_seen.get(shared_rel) != digest(theirs):
            out.append((repo_rel, shared_rel, "충돌"))
        else:
            out.append((repo_rel, shared_rel, "복사"))
    return out


def _shared_mod(root):
    """공용 폴더 경로(`SHARED`)와 지문 방식을 갖고 있는 훅 모듈을 불러온다.

    두 벌로 적지 않으려고 임포트한다 — 환경변수 `CLAUDE_SHARED_SYSTEM` 해석과 지문이 갈리면
    lock 이 서로 다른 것을 가리킨다.
    """
    import importlib.util
    path = os.path.join(root, ".claude", "hooks", "shared_sync_check.py")
    try:
        spec = importlib.util.spec_from_file_location("shared_sync_check", path)
        if not spec or not spec.loader:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:                                     # noqa: BLE001 — 미러 실패가 sync 를 막지 않는다
        return None


def _read(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def shared_bytes_of(shared_root, rel):
    return _read(str(shared_root / rel)) or b""


def mirror_shared(root):
    """대장대로 공용 폴더에 반영한다. `(계획, 복사한 수)` 를 돌려준다."""
    manifest = _read(os.path.join(root, MIRROR_MANIFEST))
    if manifest is None:
        print("[미러] 대장이 없다: " + MIRROR_MANIFEST + " — 건너뛴다.")
        return [], 0
    mod = _shared_mod(root)
    if mod is None:
        print("[미러] 공용 판정 모듈(.claude/hooks/shared_sync_check.py)을 못 읽었다 — 건너뛴다.")
        return [], 0
    shared_root = mod.SHARED
    if not shared_root.is_dir():
        return [], 0                       # 공용 폴더가 없는 환경(다른 PC) — 조용히 넘어간다

    has_lock = mod.LOCK.is_file()
    last_seen = {}
    if has_lock:
        try:
            last_seen = json.loads(mod.LOCK.read_text(encoding="utf-8")).get("files") or {}
        except ValueError:
            last_seen = {}

    entries = mirror_entries(manifest.decode("utf-8", "replace"))
    plan = mirror_plan(entries,
                       lambda rel: _read(os.path.join(root, rel)),
                       lambda rel: _read(str(shared_root / rel)),
                       last_seen, has_lock, mod.digest)

    copied, healed = 0, 0
    for repo_rel, shared_rel, action in plan:
        if action == "같음" and shared_rel not in last_seen:
            # ★ lock 에 빠진 «우리 것과 같은» 파일은 지금 채워 둔다. 안 채우면 그 파일을 다음에
            #   고치는 날 **한 번씩 헛충돌**이 나고, 그 신고가 쌓이면 진짜 충돌이 거기 묻힌다.
            #   내용이 우리 것과 같다는 것을 방금 확인했으므로 «남의 것을 수락» 하는 것이 아니다.
            last_seen[shared_rel] = mod.digest(shared_bytes_of(shared_root, shared_rel))
            healed += 1
            continue
        if action not in ("복사", "새로"):
            continue
        dst = shared_root / shared_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(os.path.join(root, repo_rel), str(dst))
        last_seen[shared_rel] = mod.digest(_read(str(dst)) or b"")
        copied += 1

    if copied or healed:
        # 우리가 방금 만든 변화까지 '남이 고친 것' 으로 다시 뜨면 그 알림이 소음이 된다.
        mod.LOCK.write_text(json.dumps({"files": last_seen}, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")

    stuck = [(r, s, a) for r, s, a in plan if a in ("충돌", "없음")]
    if copied:
        print("[미러] 공용 폴더 갱신 " + str(copied) + "건 → " + str(shared_root))
    if healed:
        print("[미러] 기준선에 빠져 있던 " + str(healed) + "건을 채웠다 (내용은 우리 것과 같다)")
    for repo_rel, shared_rel, action in stuck:
        if action == "충돌":
            # ★ 자리 이름은 **박지 않고 방금 쓴 그 폴더를 찍는다** — 위 훅과 같은 판정이다
            #   (폴더가 개명되면 박아 둔 문구는 없는 경로를 가리킨다).
            print("[미러] ★ 충돌 — 공용 쪽이 우리 모르게 바뀌었다: " + shared_rel +
                  "\n        덮지 않았다. `" + str(shared_root) + "/변경일지.md` 의 그 줄을"
                  " 읽고 판정할 것"
                  " (가져왔으면 `python .claude/hooks/shared_sync_check.py --accept`).")
        else:
            print("[미러] ★ 대장이 낡았다 — 리포에 없는 경로: " + repo_rel +
                  " (" + MIRROR_MANIFEST + " 에서 지우거나 고칠 것)")
    return plan, copied


# ── 컨테이너 루트 세션 배선 (2026-08-15) ────────────────────────────────────
#
# **실측으로 열렸다.** 세션이 과목 워크트리가 아니라 그것들을 담은 **컨테이너 폴더**에서
# 열리면 그 폴더의 `.claude/` 가 비어 있어서 **훅이 하나도 안 걸린다**(실측: 파일 0개).
# `guard_bash`·`guard_write`·`common_guard`·`session_brief`·`cost_brief`·`shared_sync_check`
# 가 전부 꺼진 채로 돌았고, 그래서 `cd … &&` 가 거부되지 않고 «모두 허용» 창까지 흘러갔다.
#
# ★ **훅 파일을 복사하지 않는다 — main 것을 가리킨다.** 사본은 갈라지고, 이 리포는 그
#   부류로 여러 번 당했다(폴백 사전·검사 두 벌·목록 두 벌). `main` 이 공통 정본이고 언제나
#   그 자리에 있으므로 경로 하나만 바꿔 쓰면 된다.
# ★★ **그 settings.json 을 손으로 쓰지 않는다.** 손으로 쓰면 main 것과 갈라지는데, 갈라진
#   쪽이 «허용 규칙» 이라 조용히 프롬프트가 늘거나 조용히 넓어진다. 그래서 **파생물로**
#   만들고, 트리거를 «반드시 하는 일»(커밋 → commit.py → sync_common)에 건다.
# ★ 컨테이너 루트는 git 워크트리가 아니라 **리포 밖**이다. AGENTS 규칙 9 의 쓰기 경계를
#   넘는 유일한 자리라, 대상 경로를 «워크트리들의 부모 한 칸»으로 못 박고 그 밖으로 안 넓힌다.

CONTAINER_MARK = "이 파일은 파생물이다 — sync_common.mirror_container_root() 가 만든다"


def container_settings(main_settings_text):
    """main 의 settings.json → 컨테이너 루트용 텍스트. **순수 함수 — 테스트 대상.**

    바꾸는 것은 **경로 한 칸**이다. 컨테이너 루트에는 워크트리가 없어서 `.claude/hooks/…` 도
    `tools/…` 도 성립하지 않으므로, 둘 다 `main/` 한 칸 아래를 가리키게 옮긴다.

    ★ **처음에는 훅 경로만 옮겼고, 그 판본이 2026-08-15 에 실측으로 깨졌다.** 그때 독스트링은
      *"허용 규칙을 손대지 않는 것이 요점"* 이라고 적혀 있었는데, 안 손댄 결과가 이랬다 —
      ⑴ Stop·StopFailure 훅이 **없는 파일**(`<컨테이너>/tools/shutdown_timer.py`)을 가리켜
        **등록됐는데 파일이 없는** 상태로 돌았다(`check_floor` 가 *그쪽이 더 나쁘다* 고 적어 둔 형태다).
      ⑵ `Bash(python tools/*.py)` 류가 **어느 명령에도 안 걸려** 빌드·회귀가 매번 승인창을 탔다 —
        컨테이너 루트에서 실제로 치는 명령은 `python main/tools/…` 이기 때문이다.
      즉 «갈라짐»을 막으려다 **아예 안 도는 배선**을 만들었다.
    ★ 그 «갈라짐» 걱정 자체는 여전히 옳다. 그래서 **규칙을 더하거나 빼지 않는다** — 개수도
      형태도 그대로 두고 경로만 옮긴다(잠금 `test_container_root_session_has_no_subject` ⑻-d).
    """
    out = main_settings_text.replace('$CLAUDE_PROJECT_DIR/.claude/hooks',
                                     '$CLAUDE_PROJECT_DIR/main/.claude/hooks')
    out = out.replace('$CLAUDE_PROJECT_DIR/tools/', '$CLAUDE_PROJECT_DIR/main/tools/')
    # 허용·거부 규칙 안의 **상대** 경로 — `Bash(python tools/…)` · `Edit(tools/**)`.
    out = out.replace('(tools/', '(main/tools/').replace(' tools/', ' main/tools/')
    return out.replace('{\n', '{\n  "//": "' + CONTAINER_MARK + '",\n', 1)


def mirror_container_root(root):
    """워크트리들의 부모 폴더에 `.claude/settings.json` 을 깔아 준다. 쓴 경로 또는 None.

    **아무것도 안 하는 경우가 정상이다** — 부모가 워크트리들의 컨테이너가 아니면(즉
    형제 워크트리가 안 보이면) 손대지 않는다. 남의 폴더에 쓰지 않기 위한 판정이다.
    """
    parent = os.path.dirname(os.path.abspath(root))
    listing = _git(["worktree", "list", "--porcelain"], cwd=root).stdout
    siblings = [ln[len("worktree "):].strip() for ln in listing.splitlines()
                if ln.startswith("worktree ")]
    inside = [p for p in siblings
              if os.path.dirname(os.path.abspath(p)) == parent]
    if len(inside) < 2:
        return None
    src = os.path.join(root, ".claude", "settings.json")
    if not os.path.isfile(src):
        return None
    with open(src, encoding="utf-8") as fh:
        want = container_settings(fh.read())
    dst_dir = os.path.join(parent, ".claude")
    dst = os.path.join(dst_dir, "settings.json")
    try:
        with open(dst, encoding="utf-8") as fh:
            if fh.read() == want:
                return None
    except OSError:
        pass
    os.makedirs(dst_dir, exist_ok=True)
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(want)
    return dst


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # ★ 어느 경로로 들어와도 **먼저** 돈다. 아래 분기들은 저마다 일찍 return 하는데,
    #   그 아래에 두면 «main 에서 커밋한 날에는 안 도는» 형태가 된다 — 공용 미러가
    #   정확히 그렇게 조용히 꺼져 있었다(2026-08-14).
    wired = mirror_container_root(root)
    if wired:
        print("[컨테이너] 세션 배선을 깔았다: " + wired +
              "\n        훅은 main 것을 가리킨다(사본을 만들지 않는다).")
    if "--merge-all" in sys.argv[1:]:
        # 전파 방향이 반대다(main → 갈래). 그래서 아래 「뒤졌는가」 검사를 타지 않는다.
        return cmd_merge_all(root)
    branch = _git(["-C", root, "branch", "--show-current"]).stdout.strip()
    if branch == "main":
        # ★ 여기서 그냥 나가면 **공용 미러가 통째로 건너뛰어진다** (열린 날 2026-08-14).
        #   미러의 트리거는 «커밋 → commit.py → sync_common» 인데, **공통 정본이 main 이라
        #   main 에서 직접 고쳐 커밋하는 길이 정상 경로로 존재한다.** 그 길로 가면 이 이른
        #   return 이 `mirror_shared` 까지 함께 껐고, 그래서 대장에 오른 파일(AGENTS.md·
        #   guard_bash.py …)을 main 에서 고치면 **공용 폴더가 조용히 낡는다.**
        #   실측으로 걸렸다: 2026-08-14 배포 도구 3건을 main 에서 커밋했을 때 미러가 안 돌았다
        #   (그 셋은 대장 밖이라 피해는 0이었지만, 그건 운이지 방어가 아니다).
        #   「방지장치의 트리거는 내가 반드시 하는 일에 건다」가 막으려던 바로 그 형태 —
        #   **브랜치→main 반영은 할 일이 없어도 미러는 여기서도 돈다.**
        print("현재 main이다 — 공통 반영(브랜치 → main)은 할 일이 없다. 공용 미러만 돌린다.")
        mirror_shared(root)
        return 0
    if not branch:
        print("브랜치를 못 읽었다(detached?). 중단.")
        return 1

    main_path = main_worktree_path(_git(["worktree", "list", "--porcelain"], cwd=root).stdout)
    if not main_path or not os.path.isdir(main_path):
        print("main worktree를 못 찾았다: " + str(main_path))
        return 1

    # ★ 뒤진 채로 올리면 남의 공통 작업을 덮는다 (2026-07-27 실사고: math가 뒤진 채 sync해
    # thermo의 strict 승격·guard 수정을 main에서 되돌렸다). 그래서 먼저 뒤졌는지 검사해 거부한다.
    try:
        behind = int((_git(["rev-list", "--count", "HEAD..main", "--"] + SYNC_PATHS).stdout or "0").strip() or "0")
    except ValueError:
        behind = 0
    if behind > 0:
        print("거부 — 현재 브랜치가 공통에서 main보다 " + str(behind) + "커밋 뒤졌다.\n"
              "  먼저 `git merge main`으로 받아 통합한 뒤 다시 실행하라 "
              "(뒤진 채로 올리면 다른 과목이 올린 공통 작업을 덮어쓴다).")
        return 1

    # ★★ **main 워크트리도 남의 작업 자리다** (열린 날 2026-08-25 — 실사고).
    #   `merge_all` 은 다른 워크트리가 더러우면 `skipped` 로 비켜 준다. 그런데 **main 에는 그
    #   검사가 없었다** — main 은 이 도구의 «목적지» 라 「내 것」으로 취급됐지만, 공통을 소유하는
    #   컨테이너 루트 세션은 **바로 그 자리에서 편집한다.**
    #   실사고: 컨테이너 루트 세션이 `main/.claude/settings.json` 의 권한 게이트를 두 번 고쳤는데
    #   두 번 다 말없이 사라졌다. 지운 경로가 둘이다 —
    #     ⑴ `sync_command_plan` 의 `rm -r --ignore-unmatch` + `checkout <소스브랜치> --` 가 덮는다
    #     ⑵ 그 `rm` 이 「local modifications」로 실패하면 **아래 복구 코드가** `checkout HEAD --` +
    #        `reset` 으로 되돌려 편집을 그 자리에서 없앤다(복구가 곧 파괴다)
    #   두 세션(mfg·solids)이 각각 소스와 실행 로그로 같은 결론에 닿았다.
    #   ★ 부류 이름: **보호 장치가 남의 워크트리에만 있고 자기 목적지에는 없다.**
    #   ★ 왜 「비켜 주기」가 아니라 「거부」인가 — 다른 워크트리는 안 밀어도 그 갈래만 낡을 뿐이지만,
    #     main 은 밀 곳 자체라 건너뛰면 이 도구가 아무 일도 안 한 것이 된다. 사람이 먼저 정리해야 한다.
    dirty = _git(["-C", main_path, "status", "--porcelain", "--"] + SYNC_PATHS).stdout
    dirty_lines = [l for l in dirty.splitlines() if l.strip()]
    if dirty_lines:
        print("거부 — main 워크트리의 공통 파일에 미커밋 변경이 있다:\n"
              + "\n".join("  " + l for l in dirty_lines[:8])
              + ("\n  … 외 " + str(len(dirty_lines) - 8) + "개" if len(dirty_lines) > 8 else "")
              + "\n  이대로 돌리면 **그 편집이 말없이 사라진다** — 덮어쓰거나, 덮기가 실패하면\n"
              "  복구 코드가 HEAD 로 되돌려 없앤다(2026-08-25 실사고).\n"
              "  먼저 그 자리에서 커밋하거나 `python tools/revert_files.py <경로…>` 로 비켜 둘 것.")
        return 1

    print("[sync] " + branch + " 공통 → main (" + main_path + ")")
    plan = sync_command_plan(main_path, branch)
    for i, args in enumerate(plan):
        r = _git(args)
        if r.returncode != 0:
            print(args[2] + " 실패:\n" + r.stderr)
            # rm까지만 돌고 실패하면 main 워크트리가 비어 있는 상태로 남는다 — 되돌린다.
            _git(["-C", main_path, "checkout", "HEAD", "--"] + SYNC_PATHS)
            _git(["-C", main_path, "reset", "-q", "HEAD", "--"] + SYNC_PATHS)
            print("  (main 워크트리는 HEAD 상태로 복구했다)")
            return 1

    # 안전장치 — 과목별 파일이 어쩌다 스테이징에 끼면 뺀다(SYNC_PATHS엔 없지만 이중 방어).
    staged = _git(["-C", main_path, "diff", "--cached", "--name-only"]).stdout
    bad = staged_subject_files(staged.splitlines())
    for p in bad:
        _git(["-C", main_path, "reset", "-q", "HEAD", "--", p])
    if bad:
        print("경고: 과목별 파일을 스테이징에서 제외함: " + ", ".join(bad))
        staged = _git(["-C", main_path, "diff", "--cached", "--name-only"]).stdout

    # ★ 과목마다 이름은 같고 내용이 다른 tools/ 파일도 뺀다(위 SUBJECT_OWNED_TOOL_BASENAMES
    #   주석의 2026-09-03 실사고). `SYNC_PATHS`의 "tools" 전체 checkout이 이 파일들까지
    #   통째로 옮기므로, 여기서 지금 브랜치가 가져온 내용을 버리고 main의 기존 내용(있었다면)
    #   으로 되돌린다 — main에 아직 없었다면 이 sync로 새로 생기지도 않게 한다.
    subject_tools = [ln for ln in staged.splitlines() if is_subject_owned_tool_path(ln.strip())]
    for p in subject_tools:
        existed = _git(["-C", main_path, "cat-file", "-e", "HEAD:" + p]).returncode == 0
        if existed:
            _git(["-C", main_path, "checkout", "HEAD", "--", p])   # main 기존 내용으로 되돌림
        else:
            _git(["-C", main_path, "rm", "-f", "-q", "--cached", "--", p])  # 새로 안 생기게
            try:
                os.remove(os.path.join(main_path, p))   # 인덱스만 지우면 워킹트리에 untracked로 남는다
            except OSError:
                pass
        _git(["-C", main_path, "reset", "-q", "HEAD", "--", p])
    if subject_tools:
        print("경고: 과목마다 내용이 다른 tools/ 파일을 스테이징에서 제외함: " + ", ".join(subject_tools))
        staged = _git(["-C", main_path, "diff", "--cached", "--name-only"]).stdout

    if not staged.strip():
        print("[sync] main에 반영할 공통 변경 없음.")
    else:
        msg = "sync common from " + branch + "\n\ntools/sync_common.py 자동 반영(공통 표면 전체)."
        c = _git(["-C", main_path, "commit", "-m", msg])
        if c.returncode != 0:
            print("commit 실패:\n" + c.stdout + c.stderr)
            return 1
        print("[sync] main 커밋:\n  " + "\n  ".join(staged.strip().splitlines()))

    m = _git(["-C", root, "merge", "main", "-m", "merge main: 공통 동기화(sync_common)"])
    if m.returncode != 0:
        print("merge 실패(충돌?) — 수동 확인 필요:\n" + m.stdout + m.stderr)
        return 1
    print("[sync] 완료 — main 정본 갱신 · " + branch + " 동기화. "
          "다른 과목은 세션 시작 시 신선도 훅이 '먼저 merge하라'고 알린다.")
    mirror_shared(root)                    # 공용 폴더까지가 한 동작이다 — 사람이 따로 칠 자리를 없앤다
    return 0


if __name__ == "__main__":
    sys.exit(main())
