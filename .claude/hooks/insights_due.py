#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""달마다 한 번 도는 것이 밀렸을 때만 한 줄 알린다 (나루에서 받음 2026-08-16).

    settings.json 의 SessionStart 훅으로 건다(이 리포의 자리):
        python "$CLAUDE_PROJECT_DIR/main/.claude/hooks/insights_due.py"

사용자 요청: [사용자 발화 인용 생략]

★ **왜 훅이고 예약 작업이 아닌가.** `/insights` 는 **터미널 대화형이라 에이전트가 못
  돌린다**. 예약 작업은 사람이 없을 때도 울리고, 울려도 그가 칠 수 없다.
  **알림은 사람이 터미널 앞에 있는 순간에만 값을 한다.**
★ **평소에는 한 글자도 안 낸다** — `cost_brief`·`shared_sync_check` 와 같은 규율이다.
★ **판정하지 않는다. 알리기만 한다.** 돌릴지는 그 세션이 정한다.
★ **날짜를 기계가 안 찍는다** — 사람이 돌린 뒤 에이전트가 대장에 적는다. 스스로 찍으면
  «돌렸다» 와 «돌렸다고 적혔다» 가 구별되지 않는다(규칙 11).

☐ 못 보는 것: 사용자가 돌리고 **아무에게도 말 안 하면** 대장이 안 움직여 계속 알린다.
  그건 흠이 아니라 이 대장의 값어치다 — 남는 것이 없으면 다음 달에 견줄 것도 없다.
"""
import datetime as dt
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAMES = ("기록/월간-점검.txt", "docs/월간-점검.txt", "월간-점검.txt")

# 고른 값 — 사용자 요청이 [사용자 발화 인용 생략] 이라 **달의 길이**를 그대로 쓴다(28·30·31 중
# 가장 흔한 쪽). 잰 값이 아니므로 «몇 일이 적정한가» 를 주장하지 않는다 — 이 자는 알리기만
# 하고 판정은 사람이 하므로, 틀려도 **한 세션에 한 줄이 이르거나 늦을 뿐**이다.
DUE_DAYS = 30


def shared_root():
    """공용 시스템 폴더. **경로를 코드에 적지 않는다** — `shared_sync_check.SHARED` 가 정본이다
    (둘 다 보고 환경변수를 존중하는 유일한 자리 — `CLAUDE.md`)."""
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        from shared_sync_check import SHARED
        return str(SHARED)
    except Exception:
        return None


def _in(base):
    for n in NAMES:
        p = os.path.join(base, *n.split("/"))
        if os.path.isfile(p):
            return p
    return None


def find_records():
    """읽을 대장 전부(공용 먼저). 없으면 빈 목록 — 이 프로젝트는 대상이 아니다.

    ★★ **공용 대장을 함께 읽는다** (사용자 판정 2026-08-17: [사용자 발화 인용 생략]). `/insights` 는 **기계 전역**이라
      한 번 돌리면 어디서 돌렸든 끝난 것인데, 대장이 프로젝트마다 따로면 **나머지가 계속
      조른다.** 실측: 나루가 2026-08-16 에 154세션을 돌려 적었는데 이 리포는 「기록 없음」으로
      떠 있었다 — 알림이 사실과 어긋난 것이다.
    ★ 처방은 이 계통에 이미 있다 — `feedback_lookup` 이 [사용자 발화 인용 생략] 로 같은 판정을 했다.
    ★ **자기 리포 대장도 함께 읽는다.** 그 프로젝트에만 있는 월간 항목은 거기 산다 —
      «무엇이 월간인가» 는 프로젝트마다 다르다. 없으면 조용히 지나간다(선언이 곧 opt-in).
    ★ 같은 항목이 양쪽에 있으면 **더 최근 날짜가 이긴다** — 물음이 «돌린 적 있나» 이기 때문이다.
    """
    out = []
    for base in (shared_root(), ROOT, os.path.dirname(ROOT)):
        p = _in(base) if base else None
        if p and p not in out:
            out.append(p)
    return out


def rows(text):
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [c.strip() for c in line.split("|")]
        if len(parts) >= 3 and parts[0]:
            yield parts[0], parts[1], parts[2]


def overdue(name, last, note, today):
    """(밀렸나, 며칠째). 사유 칸이 비면 실행으로 안 친다."""
    if not note:
        return True, None
    if not last:
        return True, None
    try:
        d = dt.date(*[int(x) for x in last.split("-")])
    except ValueError:
        return True, None
    gap = (today - d).days
    return gap >= DUE_DAYS, gap


def collect(paths):
    """`{항목: (last, note, 적는 자리)}` — 같은 항목은 **더 최근 날짜**가 이긴다."""
    seen = {}
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        for name, last, note in rows(text):
            old = seen.get(name)
            if old is None or (last or "") > (old[0] or ""):
                seen[name] = (last, note, p)
    return seen


def main():
    paths = find_records()
    if not paths:
        return 0                       # 대장이 없으면 이 프로젝트는 대상이 아니다
    today = dt.date.today()
    late = []
    for name, (last, note, where) in collect(paths).items():
        due, gap = overdue(name, last, note, today)
        if due:
            late.append((name, gap, where))
    if not late:
        return 0                       # ★ 평소에는 **한 글자도 안 낸다**
    print("[달마다] 밀린 것이 있다 — **터미널에서 사람이 친다**")
    for name, gap, where in late:
        when = "%d일째" % gap if gap is not None else "기록 없음"
        print("  · /%s  (%s)" % (name, when))
        print("      ※ 돌린 뒤 **무엇이 나왔는지 한 줄**을 `%s` 에 적는다"
              % os.path.relpath(where))
    return 0


if __name__ == "__main__":
    sys.exit(main())
