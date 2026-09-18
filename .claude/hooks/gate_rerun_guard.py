#!/usr/bin/env python
"""PreToolUse(Bash) — **아무것도 안 바뀌었는데 같은 게이트를 또 도는 것**만 막는다.

## 왜 열렸나 (2026-08-16 실측 — `기록/세션비용.csv` 42세션)

편집당 게이트가 `solids 0.92` · `dynamics 0.97` · `math 0.97` 이었다. 규율 11 은
*[발화 생략]* 인데 실측은 **편집마다 한 번**이다. 그 규칙은 2026-08-12 에
있었고 **지켜지지 않았다.** 원인은 규칙이 없어서가 아니라 **재는 자만 있고 막는 자가
없어서**다 — 같은 날 실측: 재는 자 8개 중 `exit != 0` 을 내는 것은 **하나**뿐이었다.
AGENTS 17항이 스스로 적어 둔 함정이 이것이다: *[발화 생략]*

## ★ 막는 조건을 「배치당 한 번」으로 잡지 않는다

두 가지 이유로 그건 틀린 판정선이다.

1. **'배치'는 관측이 안 된다.** 관측이 안 되는 말로 판정선을 잡으면 언제 돌려도 지킨
   것처럼 보인다 — 「자연스러운 멈춤 지점까지」가 루프에서 정확히 그렇게 죽었다
   (원장 2026-07-30 · 재발 2026-08-12).
2. **반대편 실패가 더 나쁘다.** 규율 13: *[발화 생략]*
   게이트를 막는 자는 그 미완을 만들어 낼 수 있다.

→ 그래서 **결과가 반드시 같은 경우 하나만** 막는다:
**«직전 실행 이후 트리가 한 글자도 안 바뀌었다».** 그때의 재실행은 앞의 결과를 그대로
다시 얻는 것이라, 막아도 **검증이 사라지지 않는다.** 앞 판정은 여전히 유효하다.

## ★ 판정을 새로 만들지 않는다

*무엇이 게이트인가* 는 `도구/audit_session_cost.py` 의 `gate_tags` + `gate_signature` 와
`기록/게이트-목록.txt` 가 이미 판정한다. 여기서 다시 정하면 **두 벌이 되어 갈린다** —
이 저장소가 반복해 잡은 부류이고, `check_narration` ↔ `audit_session_cost` 가 이미 같은
이유로 한쪽을 빌려 쓴다.

## ★ 끄는 깃발을 두지 않는다

`commit.py` 의 *[발화 생략]* 와 같다. 정말 다시 돌려야 하면 **트리를 건드린 뒤에 돌린다** — 그러면 조건이
스스로 풀린다. 막힌 상태에서 할 수 있는 일이 «작업을 진행하는 것» 뿐이라는 뜻이다.

## 이 자가 못 보는 것 (정직하게 남긴다)

- **바깥 상태를 읽는 게이트**(망·시각·남의 리포)는 트리가 같아도 결과가 달라질 수 있다.
  선언된 7개 중엔 없어서 지금은 문제가 아니다. 생기면 이 줄을 근거로 예외를 연다.
- **잠금장치가 없다.** 공용 폴더엔 아직 회귀 하네스가 없다 — `--selftest` 가 그 자리를 임시로
  메운다(`python 훅/gate_rerun_guard.py --selftest`). 하네스가 서면 거기로 옮긴다.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def find_tools(root=None, deep=False):
    """`audit_session_cost.py` 가 사는 폴더. 못 찾으면 `None`.

    ★★ **자리를 짐작하지 않고 찾는다 — 같은 부류 9회차** (전공정리 이식 2026-08-16).
      공용 폴더 배치(`훅/`·`도구/`)가 글자로 박혀 있어 이 리포(`main/.claude/hooks/`)에서는
      `ROOT` 가 `main/.claude` 가 됐고, `audit_session_cost` 임포트가 실패해
      `decide()` 가 `(None, False)` 로 빠졌다 — **한 번도 안 막는데 배선 점검은 초록**이었다.
    ★★ **찾는 자를 하나로 둔다.** `check_wiring` 은 이미 walk 로 찾고 있었는데 임포트 자리는
      안 고쳐서 **재는 자와 도는 자가 다른 곳을 봤다**(「두 벌이면 갈린다」). 실측: 배선 점검이
      `appsolids/tools/` 를 찾아 «✔ 셈하는 자를 읽었다» 를 냈고, 정작 훅은 없는 경로를 보고 있었다.
    ★ 싼 후보(조상 폴더의 `도구`·`tools`)를 먼저 본다 — 이 훅은 **Bash 호출마다** 도므로
      매번 walk 하면 그 자체가 비용이다. `deep=True` 는 배선 점검처럼 한 번 도는 자리용
      (XSanity 는 `_modding/scripts/` 에 둔다).
    """
    base = os.path.abspath(root or HERE)
    anc, chain = base, []
    for _ in range(5):
        chain.append(anc)
        nxt = os.path.dirname(anc)
        if nxt == anc:
            break
        anc = nxt
    for d in chain:
        for name in ("도구", "tools"):
            cand = os.path.join(d, name)
            if os.path.isfile(os.path.join(cand, "audit_session_cost.py")):
                return cand
    if not deep:
        return None
    for cur, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs
                   if d not in (".git", "node_modules", "__pycache__", "site")]
        if cur[len(base):].count(os.sep) > 3:
            dirs[:] = []
            continue
        if "audit_session_cost.py" in names:
            return cur
    return None


_TOOLS = find_tools()
if _TOOLS:
    sys.path.insert(0, _TOOLS)


def _decide(decision, reason):
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}, sys.stdout)
    sys.exit(0)


def _git(root, args):
    try:
        r = subprocess.run(["git", "-C", root] + args, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.stdout if r.returncode == 0 else ""
    except OSError:
        return ""


def is_work_tree(root):
    """`root` 가 git 워크트리인가. 아니면 아래 지문을 **뜰 수 없다**."""
    return _git(root, ["rev-parse", "--is-inside-work-tree"]).strip() == "true"


def tree_fingerprint(root):
    """트리의 지금 상태 지문. **내용까지** 본다. 못 뜨면 `None`.

    `status --porcelain` 만 쓰면 이미 `M` 인 파일을 또 고쳐도 지문이 안 변해서
    **안 바뀐 것으로 오판**한다 — 그러면 이 자가 정당한 재실행을 막는다.
    그래서 셋을 합친다: 커밋 위치 · 추적 파일의 **내용 차이** · 미추적 파일의 크기·시각.

    ★★ **못 재면 `None` 이고, 그때는 안 막는다** (전공정리 2026-08-16 — 오막음 3회차).
      이 리포의 **컨테이너 루트는 워크트리가 아니다**(bare + 링크드 워크트리 13벌의 부모).
      거기서는 위 세 git 호출이 전부 실패해 빈 문자열을 내고, 지문이 **상수**가 되어
      «언제나 안 바뀜» 이 된다 — 한 번 돌린 게이트가 그 세션 내내 막힌다.
      **실제로 이 자를 고치는 도중 `test_checks.py --fail-only` 가 막혔다.**
    ★ 공용 폴더 원본이 *[발화 생략]* 를 열어 뒀는데, 그 구멍의 가장 나쁜
      얼굴이 **「아예 못 재는 자리」** 였다. 부류는 이 자가 스스로 적어 둔 것이다 —
      **막는 자는 세는 자보다 엄해야 한다.** 세는 자가 틀리면 숫자가 흔들리지만 막는 자가
      틀리면 작업이 멈춘다. → 못 재면 통과시킨다.
    ☐ 그래서 **컨테이너 루트 세션에서는 이 자가 사실상 꺼져 있다.** 값어치가 몰려 있는 곳은
      과목 워크트리 세션이라(편집당 게이트 실측 `solids 0.89 · dynamics 0.72`) 지금은 연다.
      닫으려면 형제 워크트리들의 지문을 합쳐야 하는데, 이 훅은 **Bash 호출마다** 돌아서
      13벌에 `git status` 를 돌리는 비용이 막는 값보다 크다.
    """
    if not is_work_tree(root):
        return None
    # ★★ `-z` 로 묻는다 — NUL 구분이고 **경로를 인용하지 않는다** (2026-08-25).
    #   기본 `--porcelain` 은 `core.quotepath` 기본값 탓에 비ASCII 경로를 8진수로 감싼다:
    #   `?? "data/\352\270\260…/ch13.json"`. 그 문자열을 `os.stat` 에 넘기면 언제나
    #   `OSError` 로 빠져 **줄 자체가 지문에 들어가는데**, 그 줄은 파일 내용이 어떻게 바뀌어도
    #   같으므로 **지문이 상수**가 된다 — 즉 미추적 파일을 아무리 고쳐도 «안 바뀌었다» 다.
    #   이 리포의 콘텐츠는 전부 `data/<한글 과목명>/` 이라 **새 챕터를 쓰는 내내** 그랬고,
    #   실제로 ch13 집필 중 빌드 재실행이 막혀 `git add` 로 우회했다(우회는 처방이 아니다 —
    #   미커밋 상태로 게이트를 도는 시나리오를 통째로 못 쓰게 만든다).
    #   ★ 8진수를 사후에 푸는 길도 있지만 그러면 이스케이프 표를 손으로 들고 있어야 한다.
    #     **안 나오게 묻는 쪽**이 표를 없앤다. (`verify_workorder` 는 같은 문제를
    #     `-c core.quotepath=false` 로 이미 막고 있었다 — 둘 중 하나면 된다.)
    #   잠금 `test_checks.py::test_git_status_paths_survive_non_ascii`.
    porcelain = _git(root, ["status", "--porcelain", "-z"])
    parts = [_git(root, ["rev-parse", "HEAD"]).strip(), porcelain,
             _git(root, ["diff", "HEAD"])]
    # `-z` 에서 이름 바뀜(R·C)은 원래 경로를 **접두 없는 별도 칸**으로 덧붙인다.
    # `?? ` 로 시작하는 칸만 보므로 그 칸들은 자연히 걸러진다.
    for entry in porcelain.split("\0"):
        if not entry.startswith("?? "):
            continue
        rel = entry[3:]
        try:
            st = os.stat(os.path.join(root, rel))
            parts.append("%s|%d|%d" % (rel, st.st_size, st.st_mtime_ns))
        except OSError:
            parts.append(entry)
    return hashlib.sha256("\n".join(parts).encode("utf-8", "replace")).hexdigest()


def _state_path(root, session):
    key = hashlib.sha256(("%s|%s" % (os.path.abspath(root), session))
                         .encode("utf-8", "replace")).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), "naru-gate-rerun-%s.json" % key)


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save(path, data):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except OSError:
        pass


RUN = ("python", "python3", "py", "pwsh", "powershell", "node", "bash", "sh")


def running_command_lines(timeout=4):
    """지금 도는 프로세스의 명령줄. 못 읽으면 **빈 목록**(막지 않는다).

    ★★ **어림을 안 쓴다 — 실제로 도는지 본다** (공용 폴더 2026-08-16, 규칙 B).
      「최근 N분 안에 시작했으면 도는 중」은 **근거 없는 수**를 하나 만드는 것이라
      실행 규율 16 이 금지한다. 완료 신호도 못 쓴다 — 배경 작업은 `PostToolUse` 가
      **즉시** 떨어져 표식이 바로 지워진다. 남는 길은 **프로세스 목록을 실제로 읽는 것** 하나다.
    ★ **게이트일 때만 부른다.** 평범한 명령에는 이 값이 0이어야 한다 — 매 `Bash` 호출마다
      프로세스를 훑으면 그 자체가 낭비다.
    """
    if os.name == "nt":
        # ★ `wmic` 는 최신 윈도우에서 **빠졌다** — 공용 폴더 실측에서 0줄이 나왔다(2026-08-16).
        #   그대로 뒀으면 규칙 B 가 **한 번도 발화하지 않으면서 있는 척**했을 것이다.
        cands = [["wmic", "process", "get", "commandline"],
                 ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                  "Get-CimInstance Win32_Process | "
                  "ForEach-Object { $_.CommandLine }"]]
    else:
        cands = [["ps", "-eo", "args"]]
    for argv in cands:
        try:
            p = subprocess.run(argv, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
        except (OSError, subprocess.SubprocessError):
            continue
        lines = [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]
        if len(lines) > 1:            # 머리글 한 줄만 온 것은 «못 읽었다» 다
            return lines
    return []


def in_this_project(token, root):
    """그 토큰이 **이 리포의** 스크립트를 가리키나. `True`/`False`/`None`(모름).

    ★★ **남의 리포에서 도는 같은 이름은 근거가 아니다** (열린 날 2026-08-26 · XSanity 신고).
      한 기계에 리포가 여섯이고 도구 이름이 **미러로 같다.** 그래서 전공정리
      `main/tools/close_report.py`(PID 16296)가 도는 동안 **XSanity 의 close_report 가 막혔다.**
    ★ 이 파일이 **같은 부류를 이미 한 번 겪었다** — 아래 규칙 B 주석의
      *[발화 생략]* 가 그것이다.
      그때는 **상태 열쇠**만 고치고 `already_running` 은 안 고쳤다. 그 절반이 오늘 재발했다.
    ☐ **모르면 `None` 이고, 모를 때는 안 막는다** — 이 파일의 첫 규율이다.
      디렉터리가 안 드러나는 호출(`python close_report.py` · `-m` · 껍데기)이 그것이다.
    """
    t = (token or "").strip().strip('"').strip("'").replace(chr(92), "/")
    if not t:
        return None
    r = os.path.abspath(root).replace(chr(92), "/").rstrip("/").lower()
    absolute = t.startswith("/") or (len(t) > 2 and t[1] == ":")
    if absolute:
        return os.path.abspath(t).replace(chr(92), "/").lower().startswith(r + "/")
    if "/" in t:                       # 상대경로 — 이 리포 밑에 그 파일이 실재하나
        return os.path.isfile(os.path.join(root, t))
    return None                        # 이름만 있다 — 어느 리포인지 알 수 없다


def already_running(gate, lines, root=ROOT):
    """그 게이트를 **지금 이 리포에서** 돌고 있는 프로세스가 있나.

    ☐ 못 보는 것: 명령줄에 스크립트 이름이 안 드러나는 형태(껍데기 스크립트·`-m`).
      그때는 안 막는다 — **가드는 모를 때 통과시킨다.**
    """
    g = gate.lower()
    for ln in lines:
        low = ln.lower()
        if g not in low:
            continue
        head = os.path.basename(low.split()[0].strip('"')) if low.split() else ""
        if not (head.split(".")[0] in RUN or head.endswith((".py", ".ps1", ".sh", ".js"))):
            continue
        # 게이트 이름이 든 **인자**를 집어 어느 리포인지 본다. 남의 것이면 근거가 아니다.
        tok = next((w for w in ln.split() if g in w.lower()), "")
        if in_this_project(tok, root) is False:
            continue
        return True
    return False


def actually_runs(command, gate):
    """그 게이트를 **정말로 돌리는** 명령인가. 이름만 스친 것은 아닌가.

    ★★ **막는 자는 세는 자보다 엄해야 한다** (2026-08-16, 이 자가 첫날 나를 잘못 막았다).
      `gate_signature` 는 자기 독스트링에 *[발화 생략]* 라고 적어 뒀는데
      나는 그 위에 **거부**를 얹었다. 실제로 이 명령이 막혔다 —

          grep -n "tools\\|rglob\\|glob" 도구/audit_orphan_checks.py | head -20

      `|` 로 조각을 가르는데 **따옴표 안의 `\\|` 까지 갈려서** `rglob" 도구/…py` 라는
      가짜 조각이 생겼고, 그 머리는 `INSPECT`(grep·cat·head…)에 없으니 훑기 필터를
      그대로 지나갔다. 세는 자였을 땐 숫자가 조금 흔들리는 것으로 끝나는 흠인데,
      **막는 자가 되니 작업이 멈췄다.**
    → 그래서 저쪽을 고치지 않고(그건 그쪽 용도에 맞다) **이쪽에서 한 겹 더 좁힌다:**
      조각의 **머리가 해석기이거나 스크립트 자신**일 때만 「돌렸다」로 친다.
    """
    low = command.strip().lower()
    for sep in ("&&", ";", "|", "\n"):
        low = low.replace(sep, "\x00")
    for seg in low.split("\x00"):
        toks = seg.split()
        if not toks or gate.lower() not in seg:
            continue
        head = os.path.basename(toks[0].strip("(\"'"))
        if head in RUN or head.split(".")[0] in RUN:
            return True
        if head.endswith((".py", ".ps1", ".sh", ".js")):
            return True
    return False


def verdict(command, root, session, now_fp=None, state=None, procs=None):
    """`(gate, 막나)`. **판정 로직은 전부 여기 둔다** — `main()` 에 쓰면 자가 못 본다.

    `guard_bash` 가 `deny_reason()` 하나로 몰아 둔 이유와 같다.
    """
    try:
        from audit_session_cost import gate_signature, gate_tags
    except Exception:
        return None, False          # 자를 못 읽으면 막지 않는다
    gate = gate_signature(command, gate_tags(root))
    if not gate or not actually_runs(command, gate):
        return None, False
    # ★★★ **서명이 해석기 이름이면 게이트가 아니다** (2026-08-25, 실사고 뒤 추가).
    #   `gate_signature` 는 조각에서 `.py`·`.ps1` 토큰을 못 찾으면 **머리를 그대로 서명으로**
    #   돌려준다. 그래서 `python -c "… 게이트 …"` 처럼 **스크립트 파일이 없는 명령**의 서명이
    #   `python` 이 되고, `already_running("python", …)` 이 **떠 있는 모든 파이썬**과 맞는다.
    #   실측(2026-08-25 04:35): 훅이 남긴 좀비 파이썬 12개가 14:44 부터 **14시간째** 살아 있어
    #   전공정리의 모든 `python -c` 가 막혔다 — **자기 훅이 남긴 것이 자기 게이트를 막았다.**
    #   ★ 이 파일이 이미 적어 둔 규율 그대로다: *[발화 생략]*
    #     `gate_signature` 는 **셈**이라 저렇게 넓은 것이 맞고(그쪽은 안 고친다),
    #     **거부를 얹는 이쪽에서 한 겹 더 좁힌다** — 첫날 `grep` 오막음을 고친 방식과 같다.
    #   ☐ 못 보는 것: 껍데기 스크립트로 감싼 진짜 게이트는 여기서 놓친다. **가드는 모를 때
    #     통과시킨다** — 잘못 막는 비용이 훨씬 크다(이번이 그 실물이다).
    if gate.split(".")[0].lower() in RUN:
        return None, False
    # ★★ **심판은 자기를 판정하지 않는다** (2026-08-25, 위 고침 직후 바로 드러났다).
    #   이 파일은 `PreToolUse` 훅으로 **떠 있는 채** 판정한다. 그래서 `--selftest` 를 돌리면
    #   명령줄의 `gate_rerun_guard.py` 가 **자기 훅 프로세스와 맞아** 스스로를 막는다 —
    #   즉 **이 자만 영영 자기 검정을 못 하는 상태**였다. 위 「해석기」 건과 같은 부류이고,
    #   하필 *[발화 생략]* 를 강제하는 자가 자기 대조군을
    #   못 돌리고 있었다(공용 「규칙/증거의-정직.md」 ⑴).
    #   ☐ 더 옳은 길은 PID 로 자기를 빼는 것이다. 지금은 명령줄만 읽어 PID 가 없으므로
    #     **이름으로 뺀다** — 그 대가로 「이 자를 두 번 나란히 돌리는 것」은 못 막는다.
    #     그건 이 자가 상태 파일만 만지므로 손해가 작다.
    if gate == os.path.basename(__file__):
        return None, False
    # 규칙 B — 이미 도는 중이면 인자가 달라도 막는다. 게이트일 때만 프로세스를 읽는다.
    # ★ 규칙 A(지문)로는 못 잡는다 — 나란히 도는 넷은 인자가 달라 **서로 다른 실행**으로 잡힌다.
    #   그 「인자가 다르면 다른 실행」은 오막음 2회차에서 배운 것이라 되돌리지 않고 B 를 따로 세운다.
    if procs is None:
        procs = running_command_lines()
    if already_running(gate, procs, root):
        return gate, "running"
    fp = now_fp if now_fp is not None else tree_fingerprint(root)
    if fp is None:
        return gate, False          # 지문을 못 뜨면 «같은 결과» 를 증명할 수 없다 → 안 막는다
    st = _load(_state_path(root, session)) if state is None else state
    # ★★ **열쇠는 게이트 이름이 아니라 「명령 전체」다** (2026-08-16, 같은 날 두 번째 오막음).
    #   이름으로만 잡았더니 `knu-bot 에서 check_floor .` 를 돌린 뒤 `토익 에서 check_floor .` 가
    #   막혔다 — **인자가 다르면 다른 실행**인데 같은 실행으로 봤다. 불변식은 이름이 아니라
    #   «같은 명령 + 안 바뀐 트리 = 같은 결과» 다.
    # ☐ **못 보는 것:** 지문은 이 세션이 선 트리(공용 폴더)만 잰다. 남의 리포를 대상으로 도는
    #   명령은 그쪽이 바뀌어도 여기 지문이 안 변한다 — 그때는 **같은 명령을 두 번째로**
    #   낼 때 잘못 막을 수 있다. 지금은 그 형태가 드물어 열어 둔다.
    key = "%s\x00%s" % (gate, " ".join(command.lower().split()))
    blocked = "same" if st.get(key) == fp else False
    if not blocked:
        st[key] = fp
        if state is None:
            _save(_state_path(root, session), st)
    return gate, blocked


REASON = {
    "same": (
        "**`%s` 는 직전 실행 이후 트리가 한 글자도 안 바뀌었다 — 결과가 같다.**\n"
        "  규율 11: 게이트는 배치 끝에 한 번. 실측(2026-08-16)은 편집당 0.9회였다.\n"
        "  ★ 앞의 판정은 그대로 유효하다 — 이 거부는 검증을 지우지 않는다.\n"
        "  다시 돌려야 하면 **먼저 고칠 것을 고친다.** 그러면 이 조건은 스스로 풀린다."),
    "running": (
        "**`%s` 가 이미 돌고 있다 — 프로세스 목록에서 확인했다.**\n"
        "  둘을 나란히 돌리면 빨라지지 않는다. 같은 파일을 두 번 읽고, 기록을 쓰는\n"
        "  게이트면 **서로의 출력을 덮는다.**\n"
        "  ★ 기다리려고 **또 한 줄을 띄우지 말 것** — 그건 기다리는 것이 아니라\n"
        "  프로세스를 하나 더 만드는 것이다(2026-08-16 XSanity: `close_report` 넷이\n"
        "  34·24·20·7분째 나란히 돌았고 그중 하나가 «끝나길 기다리는» 작업이었다).\n"
        "  → 돌고 있는 그것이 끝나기를 기다린다. 오래 걸리면 **전체 우산 대신\n"
        "  고친 것에 맞는 개별 게이트**를 돌린다."),
}


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return          # 입력을 못 읽으면 막지 않는다 — 가드가 작업을 인질로 잡아선 안 된다
    ti = payload.get("tool_input") or {}
    command = str(ti.get("command") or ti.get("script") or "")
    root = (os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ROOT)
    session = str(payload.get("session_id")
                  or os.environ.get("CLAUDE_SESSION_ID") or "nosession")
    try:
        gate, blocked = verdict(command, root, session)
    except Exception:
        return
    if blocked:
        _decide("deny", REASON[blocked] % gate)


def selftest():
    """잠금장치가 없는 자리를 임시로 메운다 — 하네스가 서면 그리로 옮긴다."""
    root, ok = ROOT, True
    st = {}
    cases = [
        ("python 도구/check_floor.py .", "check_floor.py", False, "첫 실행은 통과"),
        ("python 도구/check_floor.py .", "check_floor.py", "same", "안 바뀐 채 재실행은 거부"),
        ("python 도구/scan_private.py", "scan_private.py", False, "다른 게이트는 별개"),
        # ★ 오막음 2회차를 잠근다 — 인자가 다르면 다른 실행이다
        ("python 도구/check_floor.py ../토익", "check_floor.py", False,
         "같은 자, 다른 대상은 다른 실행"),
        ("git status", None, False, "게이트가 아니면 안 본다"),
        ("ls 도구/", None, False, "평범한 명령은 안 본다"),
        # ★ 이 자가 첫날 나를 잘못 막은 실제 명령이다 — 잠근다
        ('grep -n "tools\\|rglob" 도구/check_floor.py | head -20', None, False,
         "이름만 스친 훑기는 안 막는다"),
        ("cat 도구/check_floor.py", None, False, "읽는 것은 도는 것이 아니다"),
    ]
    for cmd, want_gate, want_block, why in cases:
        gate, blocked = verdict(cmd, root, "selftest", now_fp="FIXED", state=st, procs=[])
        bad = (gate != want_gate) or (blocked != want_block)
        ok = ok and not bad
        print("%s %-34s gate=%-18s 막음=%-5s  %s"
              % ("✘" if bad else "✔", cmd[:34], gate, blocked, why))
    # 트리가 바뀌면 다시 통과해야 한다 — 이게 「검증을 안 지운다」의 근거다
    gate, blocked = verdict("python 도구/check_floor.py .", root, "selftest",
                            now_fp="CHANGED", state=st, procs=[])
    bad = bool(blocked)
    ok = ok and not bad
    print("%s %-34s gate=%-18s 막음=%-5s  %s"
          % ("✘" if bad else "✔", "(트리가 바뀐 뒤)", gate, blocked, "고치면 스스로 풀린다"))

    # ★★ **지문을 못 뜨는 자리는 두 번 돌려도 안 막는다** (오막음 3회차 — 컨테이너 루트).
    #   워크트리가 아니면 git 호출이 전부 빈손이라 지문이 **상수**가 된다. 그 상태로 막으면
    #   그 세션의 게이트가 처음 한 번 뒤로 전부 죽는다.
    tmp = tempfile.gettempdir()
    st2 = {}
    unmeasurable = tree_fingerprint(tmp) is None
    first = verdict("python 도구/check_floor.py .", tmp, "selftest", state=st2, procs=[])[1]
    again = verdict("python 도구/check_floor.py .", tmp, "selftest", state=st2, procs=[])[1]
    bad = (not unmeasurable) or bool(first) or bool(again)
    ok = ok and not bad
    print("%s %-34s gate=%-18s 막음=%-5s  %s"
          % ("✘" if bad else "✔", "(워크트리가 아닌 자리)", "지문 없음", again,
             "못 재면 안 막는다"))

    # ── 규칙 B — XSanity 실사고를 그대로 재현한다 ──────────────────────────
    #   ★★ 2026-08-26 에 **기대값이 바뀌었다.** 전에는 이름만 맞으면 막았고, 그래서
    #     전공정리 close_report 가 도는 동안 **XSanity 것이 막혔다**(XSanity 신고).
    #     이제 «어느 리포인가» 를 같이 보므로 **같은 PROCS 라도 root 에 따라 답이 갈린다.**
    #     양성(같은 리포면 여전히 막는다)과 음성(남의 리포는 근거가 아니다)을 **둘 다** 둔다.
    XS = "D:/XSanity"
    PROCS = ["python D:\\XSanity\\_modding\\scripts\\close_report.py",
             "python D:\\XSanity\\_modding\\scripts\\close_report.py --full"]
    for cmd, rt, want, why in [
        ("python _modding/scripts/close_report.py --out r.txt", XS, "running",
         "★ 양성 — 같은 리포면 인자가 달라도 막는다"),
        ("python 도구/close_report.py --out r.txt", root, False,
         "★ 음성 — **남의 리포에서 도는 같은 이름은 근거가 아니다**"),
        ("python 도구/check_floor.py .", root, False, "안 도는 게이트는 그대로 통과"),
    ]:
        gate, blocked = verdict(cmd, rt, "selftest-B", now_fp="B", state={}, procs=PROCS)
        bad = blocked != want
        ok = ok and not bad
        print("%s %-34s gate=%-18s 막음=%-5s  %s"
              % ("✘" if bad else "✔", cmd[:34], gate, blocked, why))

    # ── ★★★ 규칙 B 의 오막음 — **서명이 해석기면 게이트가 아니다** (2026-08-25 실사고) ──
    #   훅이 남긴 좀비 파이썬 12개가 14:44 부터 **14시간째** 살아 있었고, 그 탓에
    #   전공정리의 모든 `python -c` 가 막혔다. 서명이 `python` 이 되면 **떠 있는 모든
    #   파이썬**과 맞기 때문이다. 사용자가 그날 밤 *[발화 생략]*
    #   고 한 그 자리이고, 승인창보다 나쁘다 — **사람이 와도 못 지나간다.**
    ZOMBIE = ["python.exe", "C:/Python/python.exe", "python.exe -c pass"]
    for cmd, want, why in [
        ("python -c \"p=1 # 게이트-실체.txt\"", False, "스크립트 없는 -c 는 게이트가 아니다"),
        ("python -m json.tool a.json", False, "-m 도 스크립트 파일이 없다"),
    ]:
        gate, blocked = verdict(cmd, root, "selftest-Z", now_fp="Z", state={}, procs=ZOMBIE)
        bad = bool(blocked)
        ok = ok and not bad
        print("%s %-34s gate=%-18s 막음=%-5s  %s"
              % ("✘" if bad else "✔", cmd[:34], gate, blocked, why))
    # 이름만 스친 프로세스는 근거가 아니다
    gate, blocked = verdict("python 도구/check_floor.py .", root, "selftest-C",
                            now_fp="C", state={},
                            procs=["grep check_floor.py 도구/", "tail -f check_floor.py.log"])
    bad = bool(blocked)
    ok = ok and not bad
    print("%s %-34s gate=%-18s 막음=%-5s  %s"
          % ("✘" if bad else "✔", "(훑기 프로세스만 있을 때)", gate, blocked,
             "읽는 프로세스는 도는 것이 아니다"))

    print("\n%s" % ("OK   0 problem(s)." if ok else "FAIL"))
    return 0 if ok else 1


def check_wiring(target):
    """이식이 **그 자리에서 도는가**. 복사됐는가가 아니다.

    ★ 왜 있나 (2026-08-16): 이 계통이 하루에 **네 번** 같은 부류를 밟았다 — 도구를 옮기고
      한 번도 안 돌려 봐서 남의 자리에서 죽었다. 이 자는 특히 위험하다: 선행조건이 없으면
      **조용히 전부 통과**시킨다(가드가 도는 것처럼 보이는 가장 나쁜 모양). 그래서
      **가져간 쪽이 돌려 볼 자**를 같이 넣는다.
    """
    root = os.path.abspath(target)
    print("[배선 점검] %s" % root)
    ok = True

    # ★ **자리를 짐작하지 말고 찾는다** — XSanity 는 `_modding/scripts/` 에 둔다.
    #   `도구`·`tools` 만 보다가 «사본 없음» 이라고 **또** 틀렸다(오늘 여섯 번째).
    #   ★ 2026-08-16 개정 — 이 walk 가 `find_tools` 로 합쳐졌다. 여기만 찾고 임포트 자리는
    #     안 찾으면 **재는 자와 도는 자가 다른 곳을 본다**(그 상태로 초록이 났다).
    found = find_tools(root, deep=True)
    if found:
        sys.path.insert(0, found)
    try:
        import audit_session_cost as asc
        from audit_session_cost import gate_tags
    except Exception as exc:
        print("  ✘ **audit_session_cost 를 못 읽는다** (%s)" % type(exc).__name__)
        print("      → 이 상태로 걸면 **아무것도 안 막으면서 막는 것처럼 보인다.**")
        print("      → 그 도구를 먼저 가져가거나, 이 훅을 걸지 않는다.")
        return 1
    # ★ **읽혔다고 그 프로젝트 것이 아니다** (2026-08-16, 이 자를 짜면서 바로 밟았다).
    #   공용 폴더의 `도구/` 가 이미 `sys.path` 에 있어서, 사본이 **없는** knu-bot 을 재는데
    #   공용 폴더 것을 읽고 «✔» 를 냈다 — 오늘 네 번 나온 그 부류의 **다섯 번째**이고,
    #   하필 «이식이 그 자리에서 도는가» 를 재려고 만든 자가 그랬다.
    src = os.path.abspath(getattr(asc, "__file__", ""))
    try:                       # 드라이브가 다르면 commonpath 가 던진다 (D:\XSanity ↔ C:\…)
        inside = os.path.commonpath([src, root]) == root
    except ValueError:
        inside = False
    if not inside:
        print("  ✘ **그 프로젝트에 사본이 없다** — 지금 읽힌 것은 남의 것이다:")
        print("      %s" % src)
        print("      → 훅만 가져가면 **조용히 전부 통과**한다. 셈하는 자를 먼저 가져갈 것")
        return 1
    print("  ✔ 셈하는 자를 읽었다 — %s" % os.path.relpath(src, root))

    tags = gate_tags(root)
    if tags:
        print("  ✔ 게이트 선언 %d개 — 선언한 것만 본다" % len(tags))
    else:
        ok = False
        print("  ? **게이트 선언이 없다** — 이름 어림(GATE_HINTS)으로 떨어진다.")
        print("      어림은 양쪽으로 틀린다(부풀리고·깎는다). `게이트-목록.txt` 를 둘 것")

    # ★★ **규칙 B 가 이 기계에서 실제로 읽나** (전공정리 2026-08-16). 공용 폴더가 `wmic` 이
    #   빠진 기계에서 **0줄**을 받아 «한 번도 발화하지 않으면서 있는 척» 할 뻔했다 —
    #   `--selftest` 는 `procs` 를 주입받으므로 **그 갈래를 안 재고**, 여기서 재야 한다.
    lines = running_command_lines()
    if lines:
        print("  ✔ 프로세스 목록을 읽었다 — %d줄 (규칙 B 가 발화할 수 있다)" % len(lines))
    else:
        ok = False
        print("  ? **프로세스 목록을 못 읽었다** — 규칙 B(이미 도는 게이트)는 안 막는다")
        print("      규칙 A(안 바뀐 트리)는 그대로 돈다")

    # ★★ **막을 수 있는 자리인가** (전공정리 2026-08-16). 파일이 있고 배선까지 돼도, 트리
    #   지문을 못 뜨면 이 자는 **아무것도 안 막는다** — 이 함수가 존재하는 이유가 그 상태를
    #   초록으로 내보내지 않는 것이다.
    if not is_work_tree(root):
        ok = False
        print("  ? **여기는 git 워크트리가 아니다** — 트리 지문을 못 떠서 안 막는다")
        print("      컨테이너 루트가 그렇다. 값어치는 **과목 워크트리 세션**에 있다")

    s = os.path.join(root, ".claude", "settings.json")
    wired = os.path.isfile(s) and os.path.basename(__file__) in open(
        s, encoding="utf-8", errors="replace").read()
    if wired:
        print("  ✔ settings.json 에 배선됐다")
    else:
        ok = False
        print("  ? **settings.json 에 이 자가 없다** — 파일만 있고 안 돈다")

    print("\n%s" % ("OK   배선까지 됐다." if ok else "사람이 볼 항목 있음(?)"))
    return 0


if __name__ == "__main__":
    # ★ 훅 경로는 `json.dump`(ensure_ascii) 라 인코딩을 안 타지만 **사람이 읽는 출력은 탄다** —
    #   Windows 기본이 cp949 라 `--selftest` 가 첫 줄 `✘` 에서 UnicodeEncodeError 로 죽었다.
    #   즉 **잠금장치가 이 리포에서 한 번도 안 돌았다**(AGENTS 「알려진 함정」 — stderr 도 함께).
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if "--check-wiring" in sys.argv:
        i = sys.argv.index("--check-wiring")
        tgt = sys.argv[i + 1] if len(sys.argv) > i + 1 else ROOT
        sys.exit(check_wiring(tgt))
    main()
