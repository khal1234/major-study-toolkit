#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SessionStart 훅 — **주간 게이트 점검이 밀렸을 때만** 한 줄 알린다 (신설 2026-08-25).

    settings.json 의 SessionStart 훅으로 건다 (훅 폴더 이름은 프로젝트마다 다르다):
        python "$CLAUDE_PROJECT_DIR/.claude/hooks/weekly_due.py"   # 이 리포
        python "$CLAUDE_PROJECT_DIR/훅/weekly_due.py"              # 나루

월간(`insights_due`)과 무엇이 다른가
------------------------------------
월간은 `/insights` 를 알린다 — **터미널 대화형이라 에이전트가 못 돌린다.** 그 자는
«사람이 앞에 있을 때 알리는 것» 이 전부다.
**여기는 에이전트가 돌릴 수 있다** — 그래서 알림에 **돌릴 명령을 같이 준다.**
그 한 줄이 차이의 전부다: 사람이 무엇을 해야 하는지가 아니라, **내가 무엇을 돌려야
하는지**를 알린다.

★ **평소에는 한 글자도 안 낸다** — 7일이 안 지났으면 침묵한다
  (`cost_brief`·`insights_due`·`open_items` 와 같은 규율).
★ **판정하지 않는다.** 돌릴지는 그 세션이 정한다. 이 자는 «밀렸다» 만 본다.
★ **날짜를 이 자가 안 찍는다** — `weekly_check --record` 가 잰 뒤에 찍는다.
  스스로 찍으면 «쟀다» 와 «쟀다고 적혔다» 가 구별되지 않는다(규칙 11).

☐ 못 보는 것
- 대장에 측정 줄이 하나도 없으면 **밀린 것으로 본다**(첫 실행을 재촉한다).
- 측정했는데 대장에 안 적으면 계속 알린다. 그건 흠이 아니라 이 대장의 값어치다 —
  남는 것이 없으면 다음 주에 견줄 것도 없다.
"""
import datetime as dt
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = ("기록/주간-점검.txt", "docs/주간-점검.txt", "주간-점검.txt")
# ★ **도구 폴더 이름도 박지 않는다** (2026-08-26). 첫 판은 알림에 `도구/weekly_check.py` 를
#   글자로 박아 뒀는데 그건 **나루의 이름**이고 이 리포는 `tools/` 다 — 알림을 그대로 친
#   세션은 «그런 파일 없다» 를 받는다. 이 자의 값어치는 «돌릴 명령을 같이 준다» 하나인데
#   그 한 줄이 틀리면 값어치가 통째로 0 이 된다.
TOOL_DIRS = ("tools", "도구")
DUE_DAYS = 7
STAMP = re.compile(r"^측정\s+(\d{4}-\d{2}-\d{2})")


def tool_hint(root=ROOT):
    """알림에 실을 «돌릴 명령». 실재하는 자리를 골라 준다."""
    for d in TOOL_DIRS:
        if os.path.isfile(os.path.join(root, d, "weekly_check.py")):
            return "%s/weekly_check.py" % d
    return "%s/weekly_check.py" % TOOL_DIRS[0]


def find_record(root=ROOT):
    for n in NAMES:
        p = os.path.join(root, *n.split("/"))
        if os.path.isfile(p):
            return p
    return None


def last_date(text):
    """대장의 **마지막** 측정 날짜. 없으면 `None`. 순수 함수 — 테스트 대상."""
    found = None
    for ln in text.splitlines():
        m = STAMP.match(ln.strip())
        if m:
            try:
                found = dt.date.fromisoformat(m.group(1))
            except ValueError:
                continue
    return found


def verdict(text, today):
    """`(밀렸나, 며칠 됐나)`. 순수 함수 — 날짜를 **받는다**(테스트가 고정할 수 있게)."""
    d = last_date(text)
    if d is None:
        return True, None
    days = (today - d).days
    return days >= DUE_DAYS, days


def selftest():
    bad = 0

    def chk(desc, cond, got=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %-44s %s" % ("OK  " if cond else "**틀림**", desc, got))

    t = dt.date(2026, 9, 1)
    chk("측정 줄이 없으면 밀린 것으로 본다 (첫 실행 재촉)",
        verdict("# 머리만 있다\n", t) == (True, None))
    chk("7일이 안 지났으면 안 밀렸다",
        verdict("측정 2026-08-28 나루=9/12\n", t)[0] is False, str(verdict("측정 2026-08-28 나루=9/12\n", t)))
    chk("7일이 지났으면 밀렸다",
        verdict("측정 2026-08-25 나루=9/12\n", t) == (True, 7))
    chk("★ **마지막** 줄을 쓴다 (여러 번 쟀으면 최근 것)",
        last_date("측정 2026-08-01 x=1/1\n측정 2026-08-30 x=1/1\n") == dt.date(2026, 8, 30))
    chk("깨진 날짜는 건너뛴다", last_date("측정 2026-13-99 x=1/1\n") is None)
    # ★ 폴더 이름을 박으면 가져간 쪽에서 알림이 **없는 명령**을 안내한다 (2026-08-26).
    chk("★ 돌릴 명령의 폴더는 **실재하는 자리**를 고른다",
        tool_hint().endswith("/weekly_check.py")
        and tool_hint().split("/")[0] in TOOL_DIRS, tool_hint())
    chk("도구가 아예 없으면 첫 이름으로 안내한다",
        tool_hint(os.path.join(ROOT, "없는폴더")) == "tools/weekly_check.py")

    print()
    print("  ※ ☐ 이 자는 **알리기만** 한다 — 재는 것은 `%s` 다." % tool_hint())
    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        print("[자기 검정] 주간 점검 알림")
        return selftest()
    root = os.environ.get("CLAUDE_PROJECT_DIR") or ROOT
    p = find_record(root) or find_record()
    if not p:
        return 0                      # 선언이 없으면 이 프로젝트는 대상이 아니다
    try:
        text = open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return 0
    due, days = verdict(text, dt.date.today())
    if not due:
        return 0                      # ★ 평소에는 **한 글자도 안 낸다**
    if days is None:
        print("[주간 점검] 아직 한 번도 안 쟀다 — **첫 측정이 기준선이 된다**")
    else:
        print("[주간 점검] %d일째 안 쟀다 (주기 %d일)" % (days, DUE_DAYS))
    print("  $ python %s --record" % tool_hint(root))
    print("  선언된 갈래의 **완성 / 반쪽 / 미검증**을 재고 대장에 한 줄 남긴다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
