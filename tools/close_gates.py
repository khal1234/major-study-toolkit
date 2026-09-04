# -*- coding: utf-8 -*-
"""**작은 프로젝트용 마감 게이트** — 선언된 자들을 돌리고 하나라도 실패하면 막는다.

    python tools/close_gates.py            # 마감 판정 (실패가 있으면 exit 1)
    python tools/close_gates.py --selftest # 대조군으로 자를 먼저 잰다
    python tools/close_gates.py --quiet

왜 이 자가 따로 있나 (2026-08-25)
---------------------------------
전공정리 `close_report` 는 게이트 16개, XSanity 는 50개다. 그걸 **편입·토익에 그대로
옮기는 것이 곧 과잉**이다 — 사용자 판정: *"체계없는건 만들필요 있는지와 있다면 어떻게
어느 수준까지로만 만들건지"*.

★ **개수 상한은 「그 프로젝트에서 실제로 난 사고 수」다.** XSanity 가 50개인 것은 사고를
  그만큼 겪어서지 50개가 좋아서가 아니다. 사고를 안 겪은 리포에 50개를 세우면
  **그 우산을 아무도 안 쓴다**(경보 피로는 검사기를 죽인다).

그래서 이 자는 **자기 목록을 안 갖는다.** `게이트-실체.txt` 에 선언된 것만 돌린다 —
그 프로젝트가 «막아야 한다» 고 적은 것이 곧 범위다. 사고가 생기면 선언에 한 줄 늘고,
그때 이 자가 자동으로 그것도 돌린다.

무엇을 하나
-----------
1. `audit_gates` 를 `--run-selftests` 로 부른다 — **자를 먼저 재고**(대조군) 시작한다.
2. 선언된 자 중 **실행 가능한 것**(`.py`)을 하나씩 돌린다.
3. 하나라도 exit≠0 이면 **exit 1**. 「미완」과 「통과」가 겉모습이 같으면 안 된다.

☐ 못 보는 것
------------
- **선언에 없는 것은 안 본다.** 이 자의 범위는 그 파일이 정한다 — 비어 있으면 아무것도 안 막는다.
- **자가 옳은지는 안 본다.** 대조군을 돌리는 것까지가 이 자의 몫이고, 그 대조군이
  충분한지는 사람이 본다.
- 훅은 안 본다(`audit_gates` 가 「부르는 자」로 본다).
"""
import argparse
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
DECL_NAME = "게이트-실체.txt"
TIMEOUT = 180


def decl_path(root):
    for folder in ("기록", "docs", "_log", ""):
        p = os.path.join(root, folder, DECL_NAME) if folder else os.path.join(root, DECL_NAME)
        if os.path.isfile(p):
            return p
    return None


def declared_tools(text):
    """선언에서 **실행 가능한 자**만. 순수 함수 — 테스트 대상.

    「미정-…」 처럼 아직 없는 자는 여기서 빠진다 — 그건 `audit_gates` 가
    「자 없음」으로 따로 보여 준다. **없는 것을 돌리려다 죽는 것과 없다고 아는 것은 다르다.**

    ★ **넷째 칸(종류)이 붙은 줄도 읽는다** (2026-08-26). `audit_gates` 에 「래칫」 칸이
      생기면서 선언 세 줄에 넷째 칸이 붙었는데, 여기가 `len(parts) != 3` 으로 걸러
      **그 셋을 조용히 안 돌릴 뻔했다.** 같은 파일을 두 자가 읽는데 한쪽만 형식을 따라가면
      **줄어든 쪽이 조용하다** — 이 리포가 반복해 잡아 온 그 부류다.
    """
    out = []
    for ln in text.splitlines():
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) < 3 or not parts[1].endswith(".py"):
            continue
        out.append((parts[0], parts[1]))
    return out


def selftest():
    bad = 0

    def chk(desc, cond, got=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %-46s %s" % ("OK  " if cond else "**틀림**", desc, got))

    d = declared_tools("# 주석\n가 | tools/a.py | tools/c.py\n나 | tools/미정-b.py | x\n"
                       "형식깨짐 | 하나만\n다 | tools/d.txt | x\n")
    chk("실행 가능한 .py 만 고른다 (미정도 .py 면 고른다)", len(d) == 2, "%d개" % len(d))
    # ★ 회귀 재현 2026-08-26 — 넷째 칸(종류)이 붙은 줄을 `!= 3` 으로 걸러 **조용히 안 돌릴
    #   뻔했다.** 같은 선언을 읽는 두 자가 형식을 따로 알면 줄어든 쪽이 조용하다.
    r = declared_tools("래칫 | tools/e.py | tools/close_report.py | 래칫:docs/기준선.txt\n")
    chk("넷째 칸(종류)이 붙은 줄도 고른다 (회귀 재현: 래칫 셋이 조용히 빠졌다)",
        [t for _, t in r] == ["tools/e.py"], str(r))
    chk("형식 깨진 줄과 .py 아닌 것은 뺀다",
        all(t.endswith(".py") for _, t in d), str([t for _, t in d]))

    d2 = declared_tools("")
    chk("빈 선언은 0개 — 아무것도 안 막는다", d2 == [])

    print()
    print("  ※ ☐ 이 자가 **못 보는 것**: 선언에 없는 것은 안 본다. 범위를 정하는 것은")
    print("     이 코드가 아니라 그 프로젝트의 `게이트-실체.txt` 다.")
    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=ROOT)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        print("[자기 검정] 작은 마감 게이트")
        return selftest()

    root = os.path.abspath(a.root)
    dp = decl_path(root)
    if not dp:
        if not a.quiet:
            print("[마감] 선언이 없다 — **해당 없음** (실패가 아니다)")
        return 0

    gates = os.path.join(TOOLS, "audit_gates.py")
    rows, bad = [], 0
    if os.path.isfile(gates):
        r = subprocess.run([sys.executable, gates, root, "--quiet", "--run-selftests"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=TIMEOUT, cwd=root)
        rows.append(("게이트 실체", r.returncode, (r.stdout or "").strip().splitlines()))
        bad += 1 if r.returncode else 0

    for what, tool in declared_tools(io.open(dp, encoding="utf-8", errors="replace").read()):
        full = tool if os.path.isabs(tool) else os.path.join(root, tool)
        if not os.path.isfile(full) or os.path.basename(full) == "audit_gates.py":
            continue
        if os.path.samefile(full, os.path.abspath(__file__)) if os.path.exists(full) else False:
            continue
        try:
            r = subprocess.run([sys.executable, full, "--quiet"], capture_output=True,
                               text=True, encoding="utf-8", errors="replace",
                               timeout=TIMEOUT, cwd=root)
            # ★★ **「그 깃발을 받는다」를 가정하지 않는다** (2026-08-25, 같은 부류 두 번째).
            #   `--quiet` 를 모르는 자에게 넘기면 argparse 가 «unrecognized arguments» 로
            #   죽고 그게 **가짜 실패**가 된다. 자를 세운 날 그 함정을 `audit_gates` 에서
            #   한 번 고쳤는데 이 파일에서 또 밟았다 — 깃발 없이 다시 부른다.
            if r.returncode != 0 and "unrecognized arguments" in (r.stderr or ""):
                r = subprocess.run([sys.executable, full], capture_output=True,
                                   text=True, encoding="utf-8", errors="replace",
                                   timeout=TIMEOUT, cwd=root)
            code = r.returncode
            tail = [l for l in (r.stdout or "").strip().splitlines() if l.strip()][-1:]
        except Exception as e:
            code, tail = 1, [str(e)[:100]]
        rows.append((what, code, tail))
        bad += 1 if code else 0

    if a.quiet and not bad:
        return 0
    print("[마감] 선언된 게이트를 돌린다 — %s" % os.path.relpath(dp, root))
    for what, code, tail in rows:
        print("  [%s] %-34s %s" % ("PASS" if code == 0 else "FAIL", what[:34],
                                   (tail[-1][:70] if tail else "")))
    if bad:
        print("\nFAIL %d건 — **마감 못 한다.**" % bad, file=sys.stderr)
        return 1
    if not a.quiet:
        print("\n전부 통과.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
