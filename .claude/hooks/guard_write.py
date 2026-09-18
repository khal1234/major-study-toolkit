# -*- coding: utf-8 -*-
"""PreToolUse 훅 — **쓰기 계열**(`Write`/`Edit`/`MultiEdit`/`NotebookEdit`)의 마지막 층.

    stdin  : Claude Code 가 주는 PreToolUse JSON
    exit 0 : 통과   /   exit 2 : 차단 (stderr 가 사유로 전달된다)

## 왜 열렸나 (2026-08-12)

`AGENTS.md` 규칙 9 는 **자기 입으로 구멍을 자백하고 있었다:**

> *[발화 생략]*

즉 리포 밖 쓰기를 막는 것이 **에이전트의 성실성뿐**이었다. 그런데 규칙 9 가 실제로 깨지는
가장 흔한 경로는 `Bash` 가 아니라 **`Write`/`Edit` 툴 자체**다 — `guard_bash.py` 는 그 툴을
아예 보지 못한다(matcher 가 `Bash`). 방지장치를 설계할 때 *발동하는 사건을 내가 못 보고
지나갈 수 있나* 를 물어야 한다는 것이 이 리포의 판정 기준인데(「방지장치의 트리거」),
규칙 9 는 그 물음에 걸리는 자리였다.

**출처:** XSanity 프로젝트의 `guard_write.py` 를 공용 시스템 폴더에서 가져와 이 리포에 맞췄다.
그쪽에서 이미 *[발화 생략]* 는 판정을 내려
두었다. 가져오면서 **판정 내용은 전부 이 리포의 규칙으로 갈아 끼웠다**(원본은 채보 백업·
생성물 손편집이 대상이었다).

## 무엇을 막나 — 다섯 다 이 리포에 이미 있는 규칙이다

  ⑴ **규칙 9** — 쓰기는 허용된 자리에만. 리포 · 스크래치패드 · 공용 시스템 폴더 ·
     에이전트 메모리, 이 넷 밖은 차단한다.
  ⑵ **규칙 1** — 빌드 산출물(`site/<과목>/*.html`) 손편집 금지. 고칠 곳은
     `site/template/viewer.template.html` 과 `data/**` 다.
  ⑶ **과목 경계** — 다른 과목의 `data/`·`site/`. `guard_bash` 가 `git add`/`commit` 에서만
     막고 있었다 — **파일을 직접 고치는 경로는 열려 있었다.**
  ⑷ **챕터 경계** — 챕터 worktree 가 공통(`tools/`·`AGENTS.md`·`site/template/`)을 고치는 것.
     ⑶⑷ 의 판정은 `guard_bash` 의 순수 함수를 **그대로 import 해서 쓴다** — 두 벌로 두면
     갈라지고, 갈라진 경계는 꺼진 경계와 같다.
  ⑸ **경로 규칙이 안 실린 쓰기**(2026-09-11) — `.claude/rules/*.md` 의 `paths:` 는 그 파일을
     Read 할 때만 실린다. 새 장 파일을 Write 로 만들면 규칙 없이 쓴다 → 이 세션의
     `instructions_log` 기록에 그 규칙이 없으면 막는다.

★ **메모리 디렉터리는 예외다.** 규칙 5 는 `~/.claude/**` 를 건드리지 말라고 하는데, 그 안의
  `projects/<프로젝트>/memory/` 는 **에이전트가 쓰라고 하네스가 준 자리**다. 규칙 5 의 뜻은
  *[발화 생략]* 이므로 메모리만 열어 둔다.
  이걸 안 열면 이 훅이 **메모리 저장을 통째로 막는다**(도입 전에 실제로 확인한 자리다).

★ **판정은 전부 `deny_reason()` 안에 둔다.** `main()` 에 흩으면
  `tools/test_checks.py::test_guard_write_rules` 가 판정을 못 본다 — `guard_bash` 가 같은 이유로
  같은 형태를 하고 있다. 훅이 실제로 발화하는지와 무관하게 판정은 테스트로 지켜진다.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard_bash as gb                      # 과목·챕터 경계 판정을 재사용한다

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                        # 아주 오래된 파이썬 — 훅이 작업을 브릭하지 않게
        pass

REPO = Path(__file__).resolve().parents[2]   # .claude/hooks/guard_write.py → 리포 루트
# ★ 공용 시스템 폴더가 `Claude` → `naru` 로 옮겨졌다 (2026-08-15 실측: `Documents/Claude` 는
#   이제 없다). **둘 다 본다** — 다른 PC·다른 프로젝트 사본이 한꺼번에 바뀌지 않기 때문이다.
#   환경변수 `CLAUDE_SHARED_SYSTEM` 이 있으면 그것이 이긴다. 이 판정은 `shared_sync_check.SHARED`
#   와 **글자 그대로 같은 모양**이어야 한다 — 갈리면 훅마다 다른 폴더를 연다.
SHARED_SYSTEM = Path(os.environ.get("CLAUDE_SHARED_SYSTEM")
                     or next((p for p in (Path.home() / "Documents" / "naru",
                                          Path.home() / "Documents" / "Claude")
                              if p.is_dir()), Path.home() / "Documents" / "naru"))
SELFTEST = "THERMO_" + "HOOK_SELFTEST_DENY"  # 쪼개 둔다 — 이 파일 자신이 걸리지 않게

# 사용자가 명시적으로 연 리포 밖 쓰기 경로의 **선언 파일**.
# `.` 접두라 `.gitignore` 의 `/.claude/hooks/.*` 가 덮는다 — 즉 **이 워크트리에만 있고
# main 을 거쳐 다른 과목으로 퍼지지 않는다.** 그게 이 파일이 아니라 선언으로 둔 이유다.
EXTRA_ROOTS = Path(__file__).resolve().parent / ".write-roots.txt"


def _resolve(p, cwd=None):
    q = Path(p)
    if not q.is_absolute() and cwd:
        q = Path(cwd) / q
    try:
        return q.resolve(strict=False)
    except OSError:
        return q


def _under(path, root):
    try:
        Path(path).relative_to(root)
        return True
    except ValueError:
        return False


def _is_scratchpad(path):
    return "\\temp\\claude\\" in str(path).replace("/", "\\").lower()


def _is_agent_memory(path):
    """`~/.claude/projects/<프로젝트>/memory/**` — 하네스가 에이전트에게 준 자리."""
    s = str(path).replace("\\", "/").lower()
    return "/.claude/projects/" in s and "/memory/" in s


def _under_ci(path, root):
    """윈도 경로는 대소문자를 안 가린다 — `d:\\xsanity` 와 `D:\\XSanity` 는 같은 곳이다.

    `_under()` 는 `Path.relative_to` 라 글자 그대로 비교해서, 선언과 실제 경로의 표기가
    다르면 **열어 준 줄 알았는데 안 열린다.** 형제 폴더(`D:\\XSanity2`)는 걸리지 않아야 하므로
    구분자까지 붙여서 본다.
    """
    p = os.path.normcase(str(path))
    r = os.path.normcase(str(root)).rstrip("\\/")
    return p == r or p.startswith(r + os.sep)


def parse_write_roots(text):
    """선언 텍스트 → 경로 목록. **사유가 없는 줄은 안 친다.** 순수 함수.

    사유를 요구하는 이유는 `orphan-checks-allow.txt`·`check-erosion-allow.txt` 와 같다 —
    사유가 없으면 *잊은 것*과 *일부러 연 것*이 겉모습이 같아진다. 게다가 이 파일은
    **경계를 넓히는** 자리라, 왜 열렸는지 없이 남으면 다음 세션이 지울 수도 없다.
    """
    out = []
    for ln in text.splitlines():
        if ln.lstrip().startswith("#"):
            continue
        head, sep, why = ln.partition("#")
        head, why = head.strip(), why.strip()
        if head and sep and why:
            out.append(Path(head))
    return out


def extra_write_roots(decl=None):
    """선언 파일이 연 경로들. 없으면 빈 목록 — **기본값은 닫힘이다.**"""
    p = Path(decl) if decl else EXTRA_ROOTS
    try:
        if not p.is_file():
            return []
        return parse_write_roots(p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return []


def current_branch(repo=None):
    """워크트리의 현재 브랜치. 못 읽으면 빈 문자열 — 경계 판정을 건너뛴다."""
    try:
        out = subprocess.run(["git", "-C", str(repo or REPO), "branch", "--show-current"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=5)
        return (out.stdout or "").strip()
    except Exception:
        return ""


def _glob_re(pat):
    """`paths:` glob → 정규식. `**/` 는 0개 이상의 폴더, `*` 는 한 폴더 안."""
    out, i = "", 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pat.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pat[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pat[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pat[i]), i + 1
    return re.compile(out + r"\Z")


def path_rules(rules_dir):
    """`.claude/rules/*.md` 중 `paths:` 가 있는 것 → [(파일 이름, [정규식…])]."""
    out = []
    for p in sorted(Path(rules_dir).rglob("*.md")) if Path(rules_dir).is_dir() else []:
        text = p.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            continue
        front = text.split("\n---", 1)[0]
        if "paths" not in front:
            continue
        pats = re.findall(r'(?m)^\s*-\s*["\']?([^"\'\n]+?)["\']?\s*$', front.split("paths", 1)[1])
        if pats:
            out.append((p.name, [_glob_re(x) for x in pats]))
    return out


def session_read_paths(transcript_path, repo):
    """이 세션 대화록에서 `Read` 한 리포 안 경로(posix 상대경로) 집합. 못 읽으면 빈 집합.

    재는 것: 대화록 한 줄에 든 `Read` 호출의 `file_path`.
    왜(2026-09-14 실측, 재발): 장 JSON 한 번의 `Read` 가 `content.md`·`figures.md` 본문을 함께
    실었는데 append 전용 기록에도 한 줄만 남았다 — 기록 훅 경합이 아니라 이벤트 누락이라
    기록만으로는 못 닫는다. 규칙이 실리는 조건(그 glob 파일 `Read`)을 대화록에서 본다.
    못 보는 것: 실패한 `Read`(차단·없는 파일)도 센다 · 대화록 형식이 바뀌면 빈 집합(= 종전 판정).
    """
    out = set()
    if not transcript_path:
        return out
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                if '"Read"' not in ln:
                    continue
                for m in re.finditer(r'"name":\s*"Read",\s*"input":\s*\{"file_path":\s*"((?:[^"\\]|\\.)*)"', ln):
                    path = _resolve(json.loads('"' + m.group(1) + '"'))
                    if _under(path, repo):
                        out.add(Path(path).relative_to(repo).as_posix())
    except Exception:
        return set()
    return out


def unloaded_rule_reason(rel, session_id, records, rules, read_paths=None):
    """`rel` 에 걸린 경로 규칙이 이 세션에 안 실렸으면 사유, 아니면 None.

    재는 것: `instructions_log` 기록 중 이 세션(`session_id`)의 로드 파일 이름 + 대화록의 `Read` 경로.
    문턱: ⑴ 이 세션의 기록이 **유실 없는 판**(`v >= 2`)이어야 하고 ⑵ 그 규칙의 `path_glob_match` 가
    기록에 한 번이라도 있어야 막는다 — 발동이 관측되기 전에 막으면 경로 규칙이 안 도는 환경에서
    장 쓰기가 통째로 막힌다. ⑶ 그 규칙 glob 에 걸린 파일을 이 세션이 `Read` 했으면 실린 것으로 본다.

    ★ ⑴ 이 2026-09-12 에 붙었다. 옛 기록 훅은 **읽고-고쳐-쓰기**라, 한 번의 `Read` 가 경로 규칙
      둘을 동시에 물리면 훅 프로세스 둘이 서로를 덮어써 **한 건이 사라졌다**(실측: `figures.md` 만
      남고 `content.md` 유실 → 그 세션에서 장 JSON 수정이 통째로 막혔다). 없는 기록과 사라진 기록이
      **겉모습이 같아** 가드가 「안 실렸다」로 오판한 자리다. 훅을 append 전용으로 고치면서
      기록에 `v` 를 박았고, 여기서는 **믿을 수 있는 기록을 가진 세션만** 막는다.
      `v` 없는 세션을 통과시키는 것은 완화가 아니라 「기록 훅이 죽은 세션」과 같은 판정이다 —
      새 세션은 전부 `v:2` 라 스스로 닫힌다.

    못 보는 것: Bash·스크립트로 쓰는 장 JSON · 기록 훅이 죽은 세션(그 세션 기록 0줄이면 통과) ·
    `v` 없는 옛 판으로 시작한 세션 · 로그가 잘려(500줄) 발동 증거가 밀려난 뒤(그때는 다시 안 막는다).
    """
    if not session_id or not rules:
        return None
    records = records or []
    ours = [r for r in records if r.get("session_id") == session_id]
    mine = {r.get("file") for r in ours}
    if not mine:
        return None
    # 세션 기록 **전부**가 유실 없는 판이어야 믿는다. 하나라도 옛 판이면 그 세션은 훅 교체를
    # 걸쳐 살았다는 뜻이고, 교체 전에 잃은 기록이 있을 수 있다(2026-09-12 실측 — 같은 세션에서
    # 규칙 파일 하나가 새로 실리자 `v:2` 한 줄이 생겨 잃어버린 `content.md` 를 다시 「안 실렸다」로 읽었다).
    if not all(isinstance(r.get("v"), int) and r["v"] >= 2 for r in ours):
        return None
    proven = {r.get("file") for r in records if r.get("load_reason") == "path_glob_match"}
    read_paths = read_paths or ()
    miss = [name for name, pats in rules
            if name in proven and name not in mine and any(p.match(rel) for p in pats)
            and not any(p.match(rp) for p in pats for rp in read_paths)]
    if not miss:
        return None
    return (f"경로 규칙 `.claude/rules/{miss[0]}` 가 이 세션에 안 실렸다 — 그 규칙은 `paths:` 에 걸린\n"
            "  파일을 **Read 할 때만** 실린다(새 파일 Write·스크립트 수정으로는 안 실린다).\n"
            f"  대상: {rel}\n"
            "  -> 그 파일(새 파일이면 같은 과목의 다른 장)을 `Read` 한 뒤 다시 쓴다."
            " 규칙 파일을 직접 열면 로드 기록이 안 남는다.")


# 편집 도구가 「어느 파일을 쓰나」를 담는 칸. 하네스가 바뀌면 **여기만** 는다.
TARGET_KEYS = ("file_path", "notebook_path")


def target_path(tool_input):
    """편집 입력에서 대상 경로 하나를 뽑는다. 못 뽑으면 None (순수 함수 — 테스트가 직접 부른다).

    ★ **판정에서 떼어낸 이유**(2026-09-12, Codex 검토 F08): 경로를 못 뽑으면 `deny_reason` 이
      곧바로 `None` 을 돌려준다 — 즉 **모르는 입력 형태는 조용히 통과한다.** 그게 판정 로직에
      섞여 있으면 «가드가 돈다» 와 «가드가 이 형태를 아예 못 본다» 가 겉으로 같다.

    무엇을 재나: `TARGET_KEYS` 중 비어 있지 않은 첫 문자열.
    못 보는 것 — **이 함수의 사각지대이고, 넓히지 않은 것은 관측한 적이 없어서다:**
      ⑴ 경로를 `command` 문자열 안에 담는 패치형 입력(예: 다른 에이전트의 `apply_patch`).
      ⑵ 한 호출이 여러 파일을 고치는 다중 파일 패치 — 이 함수는 하나만 돌려준다.
      안 본 형태에 맞춘 변환기는 짓지 않는다(규율 19). 실제 페이로드를 한 번 관측하면
      `TARGET_KEYS` 를 늘리거나 이 함수 위에 변환기를 얹는다 — **판정은 안 건드린다.**
    잠금 `test_guard_write_target_path_blind_spots`.
    """
    for key in TARGET_KEYS:
        value = (tool_input or {}).get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def load_records(log_path):
    """`instructions_log` 의 JSON 줄들. 못 읽으면 빈 목록."""
    try:
        with open(log_path, encoding="utf-8") as fh:
            return [json.loads(ln) for ln in fh if ln.strip().startswith("{")]
    except Exception:
        return []


def deny_reason(tool_name, tool_input, cwd=None, branch=None, repo=None, extra_roots=None,
                session_id=None, records=None, rules=None, read_paths=None):
    """차단 사유 문자열, 통과면 None. **판정은 전부 여기 있다.**

    ★ **과목 «선언» 경로는 은퇴했다 (2026-09-07)** — `declared` 인자 · `declared_worktree()` ·
      「선언 중에는 공통을 안 고친다」 배타절이 함께 사라졌다. 전제였던 컨테이너 루트가
      평탄화로 없어졌고, 반쯤 걷으면 「선언은 되는데 아무도 안 보는」 상태가 된다.
      경위는 `docs/폐기된-규약.md` 「컨테이너 루트 세션 배선」.
    """
    tool_input = tool_input or {}
    repo = Path(repo) if repo else REPO
    fp = target_path(tool_input)
    if fp is None:
        return None
    if SELFTEST in fp:
        return ("[selftest] 훅이 살아 있다 — 이 메시지가 보이면 PreToolUse 가 allow 보다 먼저 발화한다.")

    path = _resolve(fp, cwd)
    rel = None
    if _under(path, repo):
        rel = Path(path).relative_to(repo).as_posix()

    # ── 규칙 9 — 쓰기가 허용된 자리 ─────────────────────────────
    #  선언된 경로는 **규칙 5 를 못 이긴다.** 홈의 Claude 설정은 사용자 것이라, 다른
    #  프로젝트를 열어 준 선언이 그 자리까지 함께 여는 일이 있어선 안 된다.
    in_home_claude = _under(path, Path.home() / ".claude")
    roots = extra_write_roots() if extra_roots is None else extra_roots
    opened = (not in_home_claude) and any(_under_ci(path, r) for r in roots)
    if rel is None and not (_is_scratchpad(path) or _under(path, SHARED_SYSTEM)
                            or _is_agent_memory(path) or opened):
        where = "규칙 5(홈의 Claude 설정)" if in_home_claude else "규칙 9"
        return (f"{where} — 쓰기는 네 곳뿐이다: 리포(`{repo}`) · 세션 스크래치패드 · "
                f"공용 시스템(`{SHARED_SYSTEM}`) · 에이전트 메모리.\n"
                f"  경로: {path}\n"
                "  -> 그 밖에 써야 할 일이면 **하지 말고 사용자에게 먼저 묻는다.**\n"
                f"     (사용자가 연 경로는 `{EXTRA_ROOTS.name}` 에 사유와 함께 적힌다.\n"
                "      **스스로 거기 줄을 더하지 않는다** — 그러면 이 경계는 없는 것과 같다.)")

    if rel is None:
        return None                          # 스크래치패드·공용·메모리 — 아래 규칙은 리포 전용이다

    # ── 규칙 1 — 빌드 산출물 손편집 금지 ────────────────────────
    if rel.startswith("site/") and not rel.startswith("site/template/") and rel.endswith(".html"):
        return ("규칙 1 — 빌드 산출물은 손으로 고치지 않는다. 빌드가 덮어쓴다.\n"
                f"  대상: {rel}\n"
                "  -> 뷰어는 `site/template/viewer.template.html`, 콘텐츠는 `data/**/*.json` 을\n"
                "     고치고 `python tools/build_site.py` 를 돌릴 것.")

    branch = current_branch(repo) if branch is None else branch

    # ── 과목 경계 ───────────────────────────────────────────────
    if gb.foreign_subject_paths(branch, [rel]):
        return (f"과목 경계 — `{branch}` 세션은 다른 과목 파일을 고치지 않는다(그 폴더 세션의 몫).\n"
                f"  대상: {rel}\n"
                "  -> 읽는 것은 된다: `git show <브랜치>:<경로>`.")

    # ── 챕터 경계 ───────────────────────────────────────────────
    if gb.out_of_chapter_paths(branch, [rel]):
        return (f"챕터 경계 — `{branch}` 는 자기 챕터 콘텐츠만 만진다.\n"
                f"  대상: {rel}\n"
                "  -> 공통(규격·검사·뷰어)은 과목 본 세션이 소유한다. 그쪽에 요청하고 merge 로 받을 것.")

    # ── 경로 규칙이 실렸나(2026-09-11 AGENTS 이관 시범) ─────────────
    if session_id:
        rules = path_rules(repo / ".claude" / "rules") if rules is None else rules
        return unloaded_rule_reason(rel, session_id, records, rules, read_paths)
    return None


def main():
    try:
        payload = gb.read_payload()          # cp949 로 읽으면 한글 경로가 조용히 깨진다
    except Exception:
        return 0                             # 못 읽으면 통과 — 훅이 작업을 브릭하지 않게
    if not isinstance(payload, dict):
        return 0                             # 입력을 못 읽으면 통과 — 훅이 작업을 브릭하지 않게
    from instructions_log import LOG_PATH    # noqa: E402 — 기록 자리를 한 곳에서만 정한다
    reason = deny_reason(payload.get("tool_name", ""),
                         payload.get("tool_input") or {},
                         payload.get("cwd") or os.getcwd(),
                         session_id=payload.get("session_id"),
                         records=load_records(LOG_PATH),
                         read_paths=session_read_paths(payload.get("transcript_path"), REPO))
    if reason:
        sys.stderr.write("[guard_write 차단]\n" + reason + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
