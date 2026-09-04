# -*- coding: utf-8 -*-
"""컨테이너 루트 세션에 **과목 정체를 선언**한다 — 가드가 그 파일을 읽는다 (신설 2026-08-15).

★ **왜 열렸나.** 컨테이너 루트 세션에는 과목이 없어서 `guard_bash.container_root_violation`
  이 과목 콘텐츠 커밋을 전부 막고 `guard_write` 는 남의 워크트리 쓰기를 막는다. 그 판정은
  옳지만 **갈래가 13개라 «한 줄 고치러 세션을 새로 여는» 일이 계속 생긴다.**
  사용자: [사용자 발화 인용 생략].

★★ **그런데 「허락」은 가드의 입력이 아니다.** 이 계통은 이미 판정해 뒀다 —
  [사용자 발화 인용 생략](공용 `규칙/공개-전-점검.md`).
  그래서 채팅의 허락이 아니라 **파일로 선언**하고, 가드가 그 파일을 읽는다.

★★★ **이것은 검사 완화가 아니다.** 가드가 막던 진짜 이유는 «허락이 없어서» 가 아니라
  **«이 세션에 과목 정체가 없어 어느 파일이 정당한지 기계가 못 가려서»** 였다(그 판정의
  독스트링이 그렇게 적혀 있다). 선언은 **빠진 입력을 주는 것**이고, 선언 뒤에도
  **나머지 11과목은 그대로 foreign 으로 막힌다.**

★ **선언 중에는 공통을 커밋하지 못한다 — 배타다.** 안 그러면 「한 세션이 전 과목 규격을
  소유」로 되돌아가는데, 컨테이너 루트 배선이 없애려던 것이 정확히 그 형태다. 배타로 두면
  그 회귀가 **구조적으로 불가능**하다(둘을 동시에 가질 수 없으므로).

★ **세션에 묶인다.** 표식에 세션 id 가 박히고(가드가 처음 읽을 때 박는다) 다른 세션에서는
  무시된다 — 잊고 남겨 둬도 다음 세션이 **자기가 선언한 적 없는 경계**를 물려받지 않는다.
  세션 id 를 못 읽는 환경에서는 시간으로 만료된다(2차 방어).

    python tools/session_subject.py appsolids --why "textbook-pdf-map 한 줄"
    python tools/session_subject.py --status      # 지금 상태만 (기본)
    python tools/session_subject.py --off

잠금 `tools/test_checks.py::test_subject_declaration_restores_the_boundary` ·
`test_subject_declaration_blocks_a_stale_worktree`.
"""
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, ".claude", "hooks"))
import guard_bash as gb                                                    # noqa: E402

def marker_path(root=ROOT):
    """표식을 쓸 자리 — **가드가 읽는 자리**여야 한다.

    ★★ 첫 판이 여기서 틀렸다. 표식 경로를 «이 도구가 사는 갈래» 에서 잡았는데, 컨테이너 배선의
      settings 는 훅을 언제나 `$CLAUDE_PROJECT_DIR/main/.claude/hooks/` 로 건다 — 그래서
      `appsolids/tools/session_subject.py` 로 부르면 **선언이 아무 데도 안 닿는다**(도구는
      «켰다» 고 말하는데 가드는 못 본다. 이 리포에서 가장 비싼 형태의 실패다).
    → 형제 폴더에 `main` 워크트리가 보이면 **거기에 쓴다.** 안 보이면 자기 자리를 쓴다
      (컨테이너가 아닌 단독 리포에서도 도는 형태로 남긴다).
    """
    sibling = os.path.join(os.path.dirname(root), "main", ".claude", "hooks")
    if os.path.isdir(sibling):
        return os.path.join(sibling, os.path.basename(gb.SUBJECT_DECL))
    return gb.SUBJECT_DECL


DECL = marker_path()


# ══ 신선도 — **선언 시점이 유일한 관문이다** (열린 날 2026-08-25) ═══════════════
#
# ★ **왜 열렸나.** `.claude/hooks/common_guard.py` 는 «그 워크트리에서 세션이 열릴 때»
#   신선도를 알린다. 그런데 컨테이너 루트 세션이 여기서 과목을 선언하는 운용에서는
#   **그 훅이 도는 자리가 아예 없다** — 선언은 경계를 열지만 신선도는 아무도 안 본다.
#   실사고 셋(2026-08-25 삽화 회차): `dynamics` 가 `98fa1a80`(삽화 생성기가 자기 산출물로
#   빌드를 통과하게 한 수정) 없이 삽화를 그려 **화살촉 11곳을 손으로 때웠고**,
#   `appsolids`(10커밋)·`solids`(11커밋)는 같은 커밋이 빠진 채 사양서를 썼다.
#
# ★★ **판정선을 「수」로 못 세운다 — 그래서 수는 알림이다** (AGENTS 실행 규율 17).
#   규율 17 은 재는 자를 만들면 «이 수가 얼마를 넘으면 마감이 막히나» 를 같이 정하고,
#   **정할 수 없으면 그 사실을 적어 두라**고 한다. 여기서는 정할 수 없다:
#   위 실사고는 **빠진 커밋 하나**(`98fa1a80`)가 낸 것이고, 지금 `thermo` 도 1커밋 뒤졌지만
#   그 하나가 무해할 수 있다. 즉 **뒤진 커밋 수는 위험과 단조 관계가 아니다** —
#   문턱을 어디에 두든 1에서 막으면 상시 차단이고 2에서 막으면 실사고를 그대로 통과시킨다.
#   → 수는 **찍기만** 한다.
#
# ★★★ **대신 이진으로 셀 수 있는 것을 막는다 — 「이 워크트리에서 도는 공통 코드」다.**
#   공통에는 성질이 다른 둘이 섞여 있다:
#     · **읽히는 것**(`AGENTS.md`·`docs/**`) — 낡으면 *사람이* 틀린 전제로 설계한다.
#       기계가 못 막는다. 그래서 AGENTS 「남의 워크트리의 공통 문서를 인용하지 마라」로 간다.
#     · **도는 것**(`tools/**`·`.claude/hooks/**`·`site/template/**`) — 낡으면 사람의
#       주의력과 무관하게 **기계가 틀린 판정을 낸다.** 컨테이너 루트에서 그 과목을 작업할 때
#       실제로 부르는 것은 `python <워크트리>/tools/…` 라 **그 사본이 정본처럼 군다.**
#   뒤쪽은 「main 의 blob 과 같은가」 하나로 갈려 판단이 안 들어간다 → **막는다.**
#   비용은 **명령 하나**(`git -C <워크트리> merge main`)라 「작업이 통째로 멈춘다」가 아니다.
#   우회 깃발을 두지 않는다 — 푸는 길이 merge 뿐이어야 다음 세션이 낡은 채로 못 선다.
RUNNING_COMMON = ["tools", ".claude/hooks", "site/template"]
READ_COMMON = ["AGENTS.md", "CLAUDE.md", "docs"]


def stale_running_files(diff_output):
    """`git diff --name-only <갈래> main -- <RUNNING_COMMON>` 출력 → 목록. 순수 함수.

    과목 소유 도구(`gen_steam_tables.py` 류, `guard_bash.is_subject_owned_tool_path`)는
    과목마다 내용이 달라도 되는 자산이라 여기서 뺀다 — 안 빼면 다른 과목과 같은 이름의
    `tools/` 파일을 가진 모든 과목이 매 세션 신선도 차단에 걸린다(2026-09-03,
    appthermo `gen_steam_tables.py` 실사고).
    """
    lines = [ln.strip() for ln in (diff_output or "").splitlines() if ln.strip()]
    return [ln for ln in lines if not gb.is_subject_owned_tool_path(ln)]


def freshness_verdict(behind, stale):
    """`(None|"warn"|"block", 사유)`. 순수 함수 — 테스트가 직접 부른다.

    `behind` 는 읽히는 공통까지 포함한 뒤진 커밋 수(**찍기만 한다**),
    `stale` 은 이 워크트리에서 **도는** 공통 코드 중 main 과 다른 파일 목록(**막는다**).
    """
    if stale:
        return ("block",
                "이 워크트리에서 **도는** 공통 코드 %d개가 main 과 다르다 — 선언을 막는다.\n"
                "  %s\n"
                "  낡은 사본이 정본처럼 군다: 컨테이너 루트에서 그 과목을 작업하면 "
                "`python <워크트리>/tools/…` 가 **저 사본**을 부른다. 2026-08-25 에 그렇게 "
                "삽화 생성기 출력이 낡은 검사에 막혀 화살촉 11곳을 손으로 때웠다.\n"
                "  → 먼저 받아라:  git -C \"<워크트리>\" merge main"
                % (len(stale), " · ".join(stale[:12]) + (" …" if len(stale) > 12 else "")))
    if behind > 0:
        return ("warn",
                "공통이 main 에서 %d커밋 앞서 있다(읽히는 문서 포함) — **막지는 않는다.**\n"
                "  뒤진 커밋 수는 위험과 단조 관계가 아니라 문턱을 못 세운다(실행 규율 17).\n"
                "  ★ 남의 워크트리의 **공통 문서**(AGENTS.md·docs/**)를 인용하지 마라 — 낡았다."
                % behind)
    return (None, "")


def _git(args):
    """git 을 subprocess 로 — 승인을 안 탄다. 못 돌면 빈 문자열(신선도 검사는 조용히 꺼진다)."""
    try:
        return subprocess.run(["git", "-C", ROOT] + args, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=10).stdout
    except Exception:
        return ""


def measure_freshness(branch):
    """`(판정, 사유)` — 실제 리포를 잰다. 순수 함수가 아니므로 판정은 위 둘에 맡긴다."""
    try:
        behind = int((_git(["rev-list", "--count", branch + "..main", "--"]
                           + RUNNING_COMMON + READ_COMMON) or "0").strip() or "0")
    except ValueError:
        behind = 0
    stale = stale_running_files(
        _git(["diff", "--name-only", branch, "main", "--"] + RUNNING_COMMON))
    return freshness_verdict(behind, stale)


def _worktree_hint(branch):
    """그 갈래의 워크트리 경로 — 이름을 짐작하지 않는다(`worktree_names` 가 정본)."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import worktree_names as wn                                       # noqa: E402
        return wn.find_worktree(os.path.dirname(ROOT), branch) or "<워크트리>"
    except Exception:
        return "<워크트리>"


def declare(branch, why):
    """선언을 쓴다. 갈래 이름과 사유가 **둘 다** 있어야 한다."""
    if branch not in gb.SUBJECT_BY_BRANCH:
        print("모르는 갈래다: " + branch, file=sys.stderr)
        print("  아는 갈래: " + " · ".join(sorted(gb.SUBJECT_BY_BRANCH)), file=sys.stderr)
        return 1
    if not why:
        # 사유를 요구하는 이유는 `orphan-checks-allow.txt`·`.write-roots.txt` 와 같다 —
        # 경계를 여는 자리라, 왜 열렸는지가 없으면 다음 사람이 지울 수도 없다.
        print("`--why \"<사유>\"` 가 필요하다 — 경계를 여는 선언이라 사유 없이는 안 쓴다.",
              file=sys.stderr)
        return 1
    verdict, reason = measure_freshness(branch)
    if verdict == "block":
        print("[신선도] " + reason.replace("<워크트리>", _worktree_hint(branch)),
              file=sys.stderr)
        return 1
    if verdict == "warn":
        print("[신선도] " + reason)
    os.makedirs(os.path.dirname(DECL), exist_ok=True)
    with open(DECL, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"branch": branch, "why": why, "at": int(time.time()), "session": None},
                  fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("[과목 선언] 이 세션은 이제 **%s (%s)** 세션이다 — %s"
          % (branch, gb.SUBJECT_BY_BRANCH[branch], why))
    print("            · 나머지 과목은 그대로 막힌다(경계가 꺼진 것이 아니다).")
    print("            · **선언 중에는 공통(tools/·AGENTS.md·site/template …)을 커밋하지 못한다.**")
    print("            · 끝나면 `python tools/session_subject.py --off`.")
    return 0


def clear():
    try:
        os.remove(DECL)
        print("[과목 선언] 껐다 — 이 세션은 다시 컨테이너 루트(공통 전용)다.")
    except OSError:
        print("[과목 선언] 켜져 있지 않다.")
    return 0


def status():
    decl = gb.read_declaration(DECL)
    if not decl:
        print("[과목 선언] 없음 — 이 세션은 공통 전용이다.")
        return 0
    live = gb.declaration_is_live(decl)
    age = int(time.time()) - int(decl.get("at") or 0)
    print("[과목 선언] %s (%s) · 사유: %s · %d분 전 · %s"
          % (decl.get("branch"), gb.SUBJECT_BY_BRANCH.get(decl.get("branch"), "?"),
             decl.get("why"), age // 60, "살아 있음" if live else "만료됨(무시된다)"))
    if decl.get("session"):
        print("            세션에 묶여 있다 — 다른 세션에서는 무시된다.")
    return 0


def main(argv):
    if "--off" in argv:
        return clear()
    names = [a for a in argv if not a.startswith("--")]
    if "--status" in argv or not names:
        return status()
    why = ""
    if "--why" in argv:
        i = argv.index("--why")
        if i + 1 < len(argv):
            why = argv[i + 1]
            names = [n for n in names if n != why]
    return declare(names[0], why)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
