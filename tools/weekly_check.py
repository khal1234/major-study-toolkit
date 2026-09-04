# -*- coding: utf-8 -*-
"""**주마다 전 프로젝트 게이트 상태를 재고 추세를 남긴다** (신설 2026-08-25).

    python 도구/weekly_check.py            # 재고 찍는다 (완성이 줄었으면 exit 1)
    python 도구/weekly_check.py --record   # 재고 **대장에 한 줄 남긴다**
    python 도구/weekly_check.py --selftest

왜 월간(`insights_due`)과 따로 있나 — **성격이 다르다**
--------------------------------------------------------
월간은 `/insights` 를 알린다. 그건 **터미널 대화형이라 에이전트가 못 돌린다** — 그래서
그 자는 «사람이 앞에 있을 때 알리기만» 한다. **여기는 반대다:** 게이트 상태는 기계가
직접 잴 수 있으므로 **알림이 아니라 측정**이어야 한다. 알림으로 만들면 사람이 매주
같은 명령을 손으로 치게 되고, 손으로 치는 것은 바쁜 주에 안 돈다.

무엇을 재나 — **자·문·부르는 자** 셋의 프로젝트별 합계
-------------------------------------------------------
`audit_gates` 를 각 프로젝트에서 돌려 **완성 / 반쪽 / 미검증**을 센다.
목록은 코드가 아니라 `기록/주간-점검.txt` 가 갖는다(규칙 4c).

판정선 — **완성이 줄면 막는다**
-------------------------------
★ 「반쪽이 늘면 막는다」로 두지 **않았다.** 반쪽은 **정직하게 늘어난다** —
  아직 못 만든 것을 선언에 적으면(「못 막는 것도 적는다」) 그 줄이 반쪽으로 뜬다.
  그걸 벌하면 **선언을 안 적는 쪽이 유리해지고**, 그러면 구멍이 화면에서 사라진다.
★ 그래서 재는 것은 **회귀**다: 지난주에 완성이던 것이 이번주에 줄었나.
  배선이 끊겼거나 자가 죽었다는 뜻이고, 그건 언제나 나쁘다.

☐ 못 보는 것
------------
- **선언에 없는 프로젝트는 안 본다.** knu-rl(층 0)·잡탕용은 일부러 뺐다 —
  「어느 수준까지」는 층이 정한다(`규칙/프로젝트-층.md`).
- **게이트가 옳은지는 안 본다.** 세는 것은 «자·문·부르는 자가 있나» 하나다.
- 첫 실행은 견줄 것이 없어 **언제나 통과**한다. 그 사실을 화면에 적는다.
"""
import argparse
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ★ **폴더 이름을 박지 않는다** (2026-08-26). 첫 판은 `기록/주간-점검.txt` 를 박았는데
#   그건 **나루의 폴더 이름**이라 이 리포(`docs/`)로 가져오자마자 «선언이 없다» 로 죽었다.
#   짝인 `weekly_due.py` 는 이미 세 자리를 훑고 있었으므로(`NAMES`), **알림은 뜨는데
#   재는 자는 다른 파일을 보는** 상태였다 — 자와 문이 서로 다른 것을 가리키는 그 부류다.
#   → 같은 세 자리를 같은 순서로 본다. 어느 배치에서든 같은 답이 나온다.
DECL_NAMES = ("기록/주간-점검.txt", "docs/주간-점검.txt", "주간-점검.txt")
TIMEOUT = 300


def find_decl(root=ROOT):
    """선언 파일 경로. 없으면 **첫 이름을 돌려준다**(«없다» 를 찍을 자리가 필요하다)."""
    for n in DECL_NAMES:
        p = os.path.join(root, *n.split("/"))
        if os.path.isfile(p):
            return p
    return os.path.join(root, *DECL_NAMES[0].split("/"))


DECL = find_decl()


def parse_decl(text):
    """`(이름, 경로, 도구폴더)` 목록. 순수 함수 — 테스트 대상.

    **사유 칸이 빈 줄은 선언으로 안 친다** — 이 계통의 예외 대장과 같은 판정선이다.
    """
    out = []
    for ln in text.splitlines():
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) < 4 or not all(parts[:3]) or not parts[3]:
            continue
        # ★ 물결표를 편다 — 선언에 **절대 경로를 박으면 홈 이름이 새어 나간다.**
        #   2026-08-25 에 개인정보 스캔이 이 파일에서 잡았다 — **자를 세운 날 그 자에게
        #   잡혔다.** 선언은 남에게 건너가는 자료라 홈 이름이 들어가면 안 된다.
        out.append((parts[0], os.path.expanduser(parts[1]), parts[2]))
    return out


def parse_history(text):
    """`{이름: 완성수}` — 대장의 **마지막** 줄에서. 순수 함수."""
    last = None
    for ln in text.splitlines():
        ln = ln.split("#")[0].strip()
        if ln.startswith("측정"):
            last = ln
    if not last:
        return {}
    out = {}
    for m in re.finditer(r"([^\s|]+)=(\d+)/(\d+)", last):
        out[m.group(1)] = int(m.group(2))
    return out


def measure(name, path, tools):
    """`(완성, 반쪽, 미검증)`. 못 재면 `None`."""
    gates = os.path.join(path, tools, "audit_gates.py")
    if not os.path.isfile(gates):
        return None
    try:
        r = subprocess.run([sys.executable, gates, path, "--run-selftests"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=TIMEOUT, cwd=path)
    except Exception:
        return None
    out = r.stdout or ""
    done = len(re.findall(r"  O    O ", out)) - len(
        [l for l in out.splitlines() if "←" in l and "  O    O " in l])
    half = len([l for l in out.splitlines() if "←" in l])
    m = re.search(r"없는\*\* 자 (\d+)개", out)
    return done, half, int(m.group(1)) if m else 0


def selftest():
    bad = 0

    def chk(desc, cond, got=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %-46s %s" % ("OK  " if cond else "**틀림**", desc, got))

    d = parse_decl("# 주석\n가 | C:/x | tools | 사유 있음\n나 | C:/y | tools |\n깨짐 | 둘\n")
    chk("★ 사유 없는 줄은 선언으로 안 친다", len(d) == 1 and d[0][0] == "가", str(d))

    # ★ 폴더 이름을 박으면 가져간 쪽에서 죽는다 (2026-08-26 실사고 — 나루 `기록/` 를 박아 뒀다).
    chk("★ 선언 자리는 **훑는다** — 나루 `기록/` 와 이 리포 `docs/` 둘 다",
        DECL_NAMES[:2] == ("기록/주간-점검.txt", "docs/주간-점검.txt"), str(DECL_NAMES))
    chk("선언이 없으면 첫 이름을 돌려준다 («없다» 를 찍을 자리)",
        os.path.basename(find_decl(os.path.join(ROOT, "없는폴더"))) == "주간-점검.txt")

    h = parse_history("# 머리\n측정 2026-08-18 나루=5/12 편입=4/4\n측정 2026-08-25 나루=9/12 편입=4/4\n")
    chk("대장의 **마지막** 줄만 읽는다", h == {"나루": 9, "편입": 4}, str(h))
    chk("대장이 비면 견줄 것이 없다 (첫 실행은 통과)", parse_history("") == {})

    print()
    print("  ※ ☐ 「반쪽이 늘면 막는다」로 **안 했다** — 반쪽은 정직하게 는다.")
    print("     못 만든 것을 선언에 적으면 반쪽이 되는데, 그걸 벌하면 **안 적는 쪽이 유리해진다.**")
    print("     재는 것은 **회귀**다: 지난주 완성이던 것이 줄었나.")
    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true", help="대장에 한 줄 남긴다")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        print("[자기 검정] 주간 점검")
        return selftest()

    if not os.path.isfile(DECL):
        print("[주간] 선언이 없다 — `%s` 에 «이름 | 경로 | 도구폴더 | 사유»"
              % os.path.relpath(DECL, ROOT).replace("\\", "/"))
        return 0
    text = io.open(DECL, encoding="utf-8", errors="replace").read()
    decls = parse_decl(text)
    prev = parse_history(text)

    print("[주간 점검] 자 · 문 · 부르는 자 — 프로젝트별")
    print("%-12s %6s %6s %8s   %s" % ("프로젝트", "완성", "반쪽", "미검증", "지난주 대비"))
    stamp, regressed = [], []
    for name, path, tools in decls:
        got = measure(name, path, tools)
        if got is None:
            print("%-12s %s" % (name, "**못 쟀다** — 경로나 자가 없다"))
            continue
        done, half, unver = got
        before = prev.get(name)
        if before is None:
            delta = "첫 측정"
        elif done < before:
            delta = "**완성 %d → %d 줄었다**" % (before, done)
            regressed.append((name, before, done))
        else:
            delta = "완성 %d → %d" % (before, done)
        print("%-12s %6d %6d %8d   %s" % (name, done, half, unver, delta))
        stamp.append("%s=%d/%d" % (name, done, done + half))

    if a.record and stamp:
        import datetime as _dt
        with io.open(DECL, "a", encoding="utf-8") as fh:
            fh.write("측정 %s %s\n" % (_dt.date.today().isoformat(), " ".join(stamp)))
        print("\n대장에 남겼다 — 다음 주가 이 줄과 견준다.")

    if regressed:
        print("\nFAIL — **완성이 줄었다.** 배선이 끊겼거나 자가 죽었다.", file=sys.stderr)
        for n, b, d in regressed:
            print("  · %s %d → %d" % (n, b, d), file=sys.stderr)
        return 1
    if not prev:
        print("\n첫 측정이라 견줄 것이 없다 — **통과**(다음 주부터 회귀를 본다).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
