#!/usr/bin/env python
"""과목 작업 커밋 — git을 subprocess로 돌려 승인 프롬프트 없이 커밋한다 (2026-07-27 신설).

**왜 이 도구인가 (사용자 재지적, 시스템적 대응):**
settings의 ask에서 `git commit`을 빼고 `guard_bash.py`가 과목 브랜치 commit을 자동 허용하게 했으나,
세션이 settings.json을 시작 시점에 캐시하거나 `git -C …` 형태에서 자동 허용이 안 먹어 프롬프트가 계속 떴다.
`sync_common.py`처럼 **git을 subprocess로 실행하면 Bash 도구 승인 자체를 안 타** 확실히 무프롬프트다.
`python tools/*.py`는 자동 허용이므로 이 도구 실행에도 프롬프트가 없다.

usage: python tools/commit.py "<message>" <path> [<path> ...]
분리 통합: python tools/commit.py --integration-owner <작업ID> "<message>" <path> ...
분리 통합은 커밋에 담당자와 대기 상태를 기록하고 자동 main 덮어쓰기를 수행하지 않는다.
검사나 통합 완료를 뜻하지 않으며, 담당자가 검증 후 해당 커밋을 직렬 통합해야 한다.
안전장치:
- 경로를 **명시**해야 한다(`-A`·`.` 금지). guard를 우회하므로 스스로 과목 경계를 지킨다.
- 다른 과목 경로(`data/<타과목>`·`site/<타과목>`)는 거부한다(guard와 같은 `foreign_subject_paths`).
- Co-Authored-By 꼬리말을 자동으로 붙인다.

## ★ 공통이 든 커밋이면 그 자리에서 main 에 반영한다 (2026-08-13 신설)

규칙은 예전부터 *[발화 생략]* 였다(main 이 정본이고
다른 과목이 merge 로 받는다). 그런데 그것을 알리는 훅(`.claude/hooks/common_guard.py`)은
**파일을 고칠 때** 경고했다 — 정작 해야 하는 일은 **커밋한 뒤**라, 그 사이에 다른 일이 끼면
그대로 잊는다.

**2026-08-13 하루에 두 번 잊었다.** 뷰어 커밋 하나가 그냥 지나갔고, *다른 과목에 주려고 만든
공통 문서*가 이 브랜치에만 남아 다른 과목 세션이 그것을 겨우 찾아 읽고
*[발화 생략]* 라고 지적했다.

AGENTS 「방지장치의 트리거는 내가 반드시 하는 일에 건다」가 정확히 이 자리다 —
**이 리포에서 반드시 하는 일은 커밋**이므로 트리거를 커밋 성공 직후로 옮긴다.

- **무엇이 공통인지 여기서 판정하지 않는다.** `sync_common.common_paths_in()` 이 그 도구의
  동기화 목록을 그대로 읽는다. 판정을 두 곳에 적으면 반드시 갈라진다(이 리포의 단골 부류다).
- **커밋이 실패하면 아무것도 하지 않는다.**
- **반영이 실패해도 커밋은 이미 된 것이다.** 그 사실을 크게 찍되 **종료코드는 건드리지 않는다** —
  이 도구의 종료코드는 *커밋됐나* 하나만 뜻하고, 거기에 반영 실패를 얹으면 이 도구를 부르는
  다른 세션이 **커밋이 안 된 줄 알고 다시 시도한다**(그쪽이 더 위험하다).
- **끄는 인자를 만들지 않는다.** 우회로를 내면 그 자가 꺼진다.

## ★★ 인자로 받은 경로**만** 커밋한다 (2026-08-13 신설)

**이 도구는 경로를 인자로 받으면서도 그 인자를 안 지키고 있었다.** add 만 경로로 하고
커밋은 `git commit -m` — 즉 **그 시점의 인덱스 전체**를 담았다. 한 워크트리에서 여러 세션이
동시에 돌면 **남의 진행 중 편집이 내 커밋에 통째로 딸려 들어간다.**

실제로 2026-08-13 에 두 번 일어났다 — 한 세션의 회귀 테스트가 커밋 c7738fc 에,
침식 기준선이 d9b951a 에 그렇게 섞였다. **내용은 온전했지만 커밋 메시지는 그쪽 작업만
설명한다.** 이 리포는 커밋 메시지를 *무엇을·왜·근거* 의 **기록**으로 쓰므로,
담긴 것과 적힌 것이 어긋나면 **그 기록이 거짓말이 된다** — 되짚을 때
*이 변경이 왜 여기 있지* 가 된다. 공통 규칙도 *커밋은 자기 과목 경로만* 이라고 못 박는다.

- **`git commit -- <경로…>`** 로 한정한다. 인자가 있으면 git 은 `--only` 로 동작해
  **그 경로의 작업 트리 내용만** 담고 나머지 스테이징은 인덱스에 그대로 남긴다.
  바로 앞에서 같은 경로를 `git add` 하므로 인덱스와 작업 트리가 그 경로에서 일치한다.
- **★ 자와 실행의 범위를 같게 둔다.** 「스테이징된 것이 없다」 판정도 **같은 경로로 한정**한다.
  인덱스 전체를 보고 판단하면 *남의 변경 때문에* 커밋할 것이 있다고 오판한다 —
  판정과 실행이 갈리면 반드시 어긋난다(이 리포의 단골 부류).
- **경로 밖 스테이징은 막지 않고 한 줄 알린다.** 남의 세션이 작업 중인 정상 상태다.
- **main 반영 판정도 이 커밋에 담긴 것만 본다** — 남이 스테이징해 둔 공통 파일 때문에
  아직 커밋도 안 된 것을 main 으로 옮기면 안 된다.
- **인자 없는 호출은 계속 거부한다(exit 2).** 리포 전체에 프로그램 호출부가 없고
  (문서·안내 문구뿐), *경로를 명시하라* 는 것이 이 도구의 존재 이유다.
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 자리는 프로젝트마다 다르다 — 찾아서 쓴다 (미러가 두 번 덮었다. 세 번째로 적는다)
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
for _d in (".claude/hooks", "tools", "훅", "도구"):
    _p = os.path.join(ROOT, *_d.split("/"))
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
from guard_bash import foreign_subject_paths  # noqa: E402
import sync_common  # noqa: E402

TRAILER = "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"


def _git(args):
    return subprocess.run(["git", "-C", ROOT] + args, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def names_of(out):
    """`git diff --cached --name-only` 출력 → 이름 목록. 순수 함수 — 테스트가 직접 부른다."""
    return [ln.strip() for ln in (out or "").splitlines() if ln.strip()]


def out_of_scope(all_staged, in_scope):
    """스테이징돼 있지만 **이 커밋에는 안 담기는** 이름들. 순수 함수 — 테스트가 직접 부른다.

    막지 않는다 — 한 워크트리에서 다른 세션이 작업 중인 정상 상태다. 알리기만 한다.
    (몰래 담기던 것이 결함이었지, 남이 스테이징해 둔 것 자체는 결함이 아니다.)
    """
    inside = set(in_scope)
    return [n for n in all_staged if n not in inside]


def should_sync(branch, changed_names):
    """이 커밋이 `sync_common` 을 불러야 하는가. 순수 함수 — 테스트가 직접 부른다.

    판정의 정본은 `sync_common` 하나다. 여기서 다시 목록을 적지 않는다.

    ★★ **main 을 여기서 빼면 안 된다 (열린 날 2026-08-14, 같은 결함의 두 번째 자리).**
    옛 주석은 *[발화 생략]* 였다. 그 말은
    **브랜치→main 반영**에 대해서만 참인데, `sync_common` 은 그 일 말고 **공용 폴더 미러**도
    한다. 그래서 이 한 줄이 «main 에서 공통을 고쳐 커밋하는 정상 경로»에서 미러를 통째로 껐다.
    - 같은 판정이 `sync_common.main()` 에도 있었고 거기만 고쳤더니 **여기서 다시 막혔다** —
      *«같은 질문에 답하는 자가 둘이면 갈린다»* 의 실례라 두 곳을 함께 적어 둔다.
    - 실측: 2026-08-14 배포 도구 3건(`3ee4786`)과 이 배치의 첫 커밋(`e41d05b`) 둘 다
      main 에서 났고 **미러가 한 번도 안 돌았다**(공용 `도구/sync_common.py` 가 17:06 판본 그대로).
    - main 에서 부르면 `sync_common` 이 «반영은 할 일 없음, 미러만 돈다» 로 처리한다.
    """
    return bool(sync_common.common_paths_in(changed_names))


def main(argv):
    integration_owner = None
    if len(argv) > 1 and argv[1] == "--integration-owner":
        if len(argv) < 5 or not argv[2].strip() or argv[2].startswith("-"):
            print("--integration-owner 뒤에 담당 작업 ID, 메시지, 명시 경로가 필요하다.")
            return 2
        integration_owner = argv[2].strip()
        if any(c.isspace() for c in integration_owner):
            print("담당 작업 ID에 공백을 넣을 수 없다.")
            return 2
        argv = [argv[0]] + argv[3:]
    if len(argv) < 3:
        # 인자 없는 호출을 «전체 커밋»으로 봐주지 않는다 — 경로를 명시하라는 것이 존재 이유다.
        print('usage: python tools/commit.py "<message>" <path> [<path> ...]')
        print("  경로는 필수다 — 이 도구는 **인자로 준 경로만** 커밋한다.")
        return 2
    msg, paths = argv[1], argv[2:]
    if any(p in ("-A", "--all", ".", "-a") for p in paths):
        print("경로를 명시하라 — -A/-a/. 는 금지(과목 경계를 지키기 위함).")
        return 2

    branch = _git(["branch", "--show-current"]).stdout.strip()
    bad = foreign_subject_paths(branch, paths)
    if bad:
        print("과목 경계 위반 — 현재 브랜치 '" + branch + "'에서 다른 과목 경로: " + ", ".join(bad))
        return 2

    # ★ 이 커밋의 범위. add·판정·commit 이 **같은 하나**를 쓴다 — 두 번 적으면 갈라진다.
    scope = ["--"] + list(paths)
    r = _git(["add"] + scope)
    if r.returncode != 0:
        print("add 실패:\n" + r.stderr)
        return 1
    # 한글 경로가 8진 이스케이프로 나오지 않게 한다(quotepath). 판정·표시 둘 다 이 이름을 쓴다.
    quiet_path = ["-c", "core.quotepath=false"]
    mine = names_of(_git(quiet_path + ["diff", "--cached", "--name-only"] + scope).stdout)
    if not mine:
        print("스테이징된 변경이 없다 — 커밋 안 함(인자로 준 경로 기준).")
        return 1
    others = out_of_scope(names_of(_git(quiet_path + ["diff", "--cached", "--name-only"]).stdout), mine)
    if others:
        print("[알림] 이 커밋에 안 담긴 스테이징 변경 " + str(len(others)) + "건"
              "(다른 세션 작업일 수 있다): " + ", ".join(others[:4])
              + (" 외 " + str(len(others) - 4) + "건" if len(others) > 4 else ""))

    # ★ 규칙 등록부 게이트 (2026-09-18) — 장 JSON 이 담긴 커밋은 그 장의 미판정이 HEAD 보다 늘면 막는다.
    #   `rules.py` 가 있는 리포에서만 돈다(공용 폴더 미러에는 없다).
    chapters = [n for n in mine if re.fullmatch(r"data/[^/]+/ch\d{2}\.json", n)]
    rules_tool = os.path.join(TOOLS_DIR, "rules.py")
    if chapters and os.path.isfile(rules_tool):
        g = subprocess.run([sys.executable, rules_tool, "gate"] + chapters, cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if g.returncode != 0:
            print((g.stdout + g.stderr).strip())
            print("커밋 안 함 — 스테이징은 남아 있다.")
            return 1

    full = msg if TRAILER in msg else msg + "\n\n" + TRAILER
    if integration_owner:
        full += "\nIntegration-Owner: " + integration_owner + "\nIntegration-State: pending"
    c = _git(["commit", "-m", full] + scope)
    print((c.stdout + c.stderr).strip())
    if c.returncode != 0:
        return c.returncode

    # ★ 커밋이 성공한 **이 자리**가 트리거다 (위 독스트링 참조).
    # 판정은 **이 커밋에 담긴 것**만 본다 — 남이 스테이징만 해 둔 공통 파일을 옮기면 안 된다.
    if integration_owner:
        sha = _git(["rev-parse", "HEAD"]).stdout.strip()
        print("[통합 대기] " + sha + " · 담당 " + integration_owner
              + " — 자동 main 반영 없음. 담당자에게 전달하고 검증·통합 결과를 확인할 것.")
    elif should_sync(branch, mine):
        try:
            rc, why = sync_common.main(), ""
        except Exception as exc:                                     # noqa: BLE001
            rc, why = 1, type(exc).__name__ + ": " + str(exc)[:200]
        if rc != 0:
            print("★ 커밋은 됐다(위 sha). 하지만 **main 반영이 실패했다** — 이 공통 변경은 "
                  "아직 이 브랜치에만 있다." + (" 원인: " + why if why else " 사유는 위 줄에 있다.")
                  + "\n  고친 뒤 `python tools/sync_common.py` 를 다시 돌릴 것"
                  "(뒤졌다는 거부면 먼저 `git merge main`).")

    # ★ 상호작용 점검도 **이 자리**가 트리거다 (신설 2026-08-15, 사용자 질문:
    #   *[발화 생략]*).
    #   close 에만 두면 늦고(맥락이 날아간 뒤다) 매 턴은 소음이다. 커밋은 **반드시 하는 일**
    #   이면서 무엇보다 *«이걸 했다»고 주장하는 자리*라, 예고 미이행·미검증과 짝이 맞다.
    #   `--quiet` 라 걸린 게 없으면 한 줄도 안 낸다. **커밋 결과를 뒤집지 않는다** —
    #   이 도구의 종료코드는 «커밋됐나» 하나뿐이라는 계약은 그대로다.
    #   ★★ **진행 중계도 여기서 알린다** (2026-08-15, 사용자 판정 — [발화 생략]).
    #     `close_report` 에도 이 자가 있지만 거기서는 **세기만** 한다. 이유는 하나다:
    #     이 수는 **세션 전체 누적**이라 close 시점엔 이미 확정이고, 다른 close 항목처럼
    #     «고치고 다시 돌리면 초록» 이 **불가능**하다. 못 지우는 빨간불은 게이트가 아니라
    #     벽이고, 벽이 서면 그 아래 멀쩡한 19행까지 같이 무시된다.
    #     → 그래서 «아직 고칠 수 있는 시점»인 여기로 옮겼다. 넘겼으면 한 줄, 아니면 침묵.
    # ★ 자리는 `TOOLS_DIR` 로 잡는다 — `ROOT/"tools"` 로 박으면 **공용 폴더에서 죽는다**(2026-08-24).
    #   공용 폴더의 같은 파일은 `도구/` 에 사는데 이 줄만 `tools` 를 찾아 매번 되돌려 적혔고,
    #   그 되돌림이 다음 미러에 또 덮여 **네 번 반복**됐다(공용 폴더 `변경일지.md` 2026-08-14·17·20).
    #   `TOOLS_DIR` 은 이 파일이 있는 폴더라 두 배치에서 저절로 맞는다 — 한 파일이 양쪽에서 돈다.
    # `close_gates.py` 는 그 리포의 `게이트-실체.txt` 가 「부르는 자 = commit.py」로 선언했을 때만 돈다
    #   (공용 폴더 2026-09-11 추가). 전공정리는 선언 목록에 build_site·test_checks 가 있어 매 커밋 돌리면 수 분이라 선언 안 한다.
    tools = ["audit_session_conduct.py", "check_narration.py"]
    if _declares_commit_gate(ROOT):
        tools.append("close_gates.py")
    for tool in tools:
        try:
            subprocess.run([sys.executable, os.path.join(TOOLS_DIR, tool), "--quiet"],
                           cwd=ROOT, check=False)
        except OSError:
            pass
    return 0


def _declares_commit_gate(root):
    """`게이트-실체.txt` 에 `… | …close_gates.py | …commit.py…` 줄이 있나. 선언 파일 자리는 close_gates 가 찾는다."""
    try:
        sys.path.insert(0, TOOLS_DIR)
        from close_gates import decl_path
        p = decl_path(root)
    except Exception:
        return False
    if not p:
        return False
    with open(p, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            parts = [x.strip() for x in ln.split("|")]
            if (not ln.lstrip().startswith("#") and len(parts) >= 3
                    and parts[1].endswith("close_gates.py") and "commit.py" in parts[2]):
                return True
    return False


if __name__ == "__main__":
    sys.exit(main(sys.argv))
