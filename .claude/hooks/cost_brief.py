# -*- coding: utf-8 -*-
"""세션 비용이 **자기 과거보다 나빠졌을 때만** 한 줄 알린다 (신설 2026-08-15).

    settings.json 의 SessionStart 훅으로 건다:
        python .claude/hooks/cost_brief.py

**왜 이 형태인가** (2026-08-15 사용자 판정):

    [사용자 발화 인용 생략]

  ★ **평소 비용이 0이어야 매 세션 돌릴 수 있다** — `shared_sync_check` 와 같은 규율이다.
    읽는 것은 이미 계산된 CSV 한 장뿐이고, **나빠진 것이 없으면 아무것도 출력하지 않는다.**
  ★ **판정하지 않는다. 알리기만 한다.** 무엇을 고칠지는 그 세션이 정한다.

★★ **목표치를 쓰지 않는다 — 자기 과거와만 견준다.** 이 계통은 이미 [사용자 발화 인용 생략] 이라고 못 박았다. 프로젝트마다 하는 일이
   달라 **고정 기준선은 어느 쪽에서든 거짓말을 한다** — 실측 2026-08-15: 같은 「비효율」이
   XSanity 는 왕복(묶음 6% · 재생성 0.8%)이고 전공정리는 큰 출력(묶음 49% · 재생성 8.6%)이라
   **처방이 정반대**였다. 고정 기준으로 쟀으면 이미 잘하는 쪽에 대고 그걸 더 하라고 했을 것이다.

★ **작은 세션은 건드리지 않는다.** 표본이 작으면 비율이 요동쳐서 그 알림은 곧 소음이 되고,
  소음이 된 알림은 아무도 안 읽는다(이 저장소가 반복해 겪은 부류).
"""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SHARED = Path(os.environ.get("CLAUDE_SHARED_SYSTEM")
              or next((p for p in (Path.home() / "Documents" / "naru",
                                    Path.home() / "Documents" / "Claude")
                            if p.is_dir()), Path.home() / "Documents" / "naru"))
RECORD = SHARED / "기록" / "세션비용.csv"
MIN_EDITS = 15          # 이보다 작은 세션은 비율이 요동쳐서 안 본다
MIN_PAST = 2            # 견줄 과거가 이만큼은 있어야 «추세» 라 부를 수 있다


def key(cwd):
    """기록의 «프로젝트» 칸과 같은 꼴 — 경로 뒤 두 조각."""
    parts = [p.rstrip(":\\/") for p in Path(cwd).parts if p.strip(":\\/")]
    return "/".join(parts[-2:]) if len(parts) > 1 else str(cwd)


def rows_for(text, want):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("프로젝트,"):
            continue
        f = line.split(",")
        if len(f) < 8 or f[0] != want:
            continue
        try:
            out.append({"날": f[1], "출력": int(f[2]), "재생성": float(f[3]),
                        "묶음": float(f[4]), "편집": int(f[5]),
                        "편집당": float(f[7]) if f[7] else None})
        except ValueError:
            continue
    return out


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    mid = len(xs) // 2
    return xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2.0


def brief(rows):
    """나빠진 축만 문장으로. **없으면 빈 목록** — 그게 평소 상태다."""
    if len(rows) < MIN_PAST + 1:
        return []
    now, past = rows[0], rows[1:]
    if now["편집"] < MIN_EDITS:
        return []
    said = []
    was = median([p["재생성"] for p in past])
    # 절대값도 함께 본다 — 0.4%→0.9% 는 «두 배»지만 아프지 않다.
    if was and now["재생성"] >= max(2 * was, 5.0):
        said.append("캐시 재생성 %.1f%% (평소 %.1f%%) — **큰 도구 출력**을 의심한다"
                    % (now["재생성"], was))
    was = median([p["묶음"] for p in past])
    if was and was >= 20 and now["묶음"] <= was / 2:
        said.append("묶음률 %.0f%% (평소 %.0f%%) — 의존 없는 호출이 흩어졌다"
                    % (now["묶음"], was))
    was = median([p["편집당"] for p in past])
    if was and now["편집당"] is not None and now["편집당"] <= was / 2:
        said.append("편집당 게이트 %.2f (평소 %.2f) — **감수가 얇아졌다**"
                    % (now["편집당"], was))
    return said


STALE_HOURS = 12


def refresh_if_stale():
    """낡았으면 **자기 사본으로** 다시 잰다. 못 하면 «낡았다»고 말한다.

    ★★ **낡은 값으로 자신 있게 말하는 것은 아예 안 도는 것보다 나쁘다.** 이 기록은 파생물이라
      누가 언제 다시 만들어도 되는데, 아무도 안 만들면 훅은 **옛 숫자를 오늘 것처럼** 말한다.
    ★ 다시 재는 것은 **이 프로젝트의 자기 사본**(`tools/audit_session_cost.py`)으로 한다 —
      공용 경로의 스크립트를 직접 돌리는 형태는 이 계통의 가드가 막는다(`check_floor` 선례).
      사본이 없으면 **재지 못한다** — 그때는 조용히 넘기지 말고 **낡았다고 한 줄** 낸다.
    ★ 실측 2026-08-15: 세션 209개(1.66GB)에 **1.8초**. SessionStart 에 둘 만하다.
    """
    try:
        age = (__import__("time").time() - RECORD.stat().st_mtime) / 3600.0
    except OSError:
        return None
    if age < STALE_HOURS:
        return None
    tool = Path.cwd() / "tools" / "audit_session_cost.py"
    if tool.is_file():
        try:
            __import__("subprocess").run(
                [sys.executable, str(tool), "--record"], cwd=str(Path.cwd()),
                capture_output=True, timeout=60)
            return None
        except Exception:
            pass
    return "기록이 %.0f시간 낡았다 — `python tools/audit_session_cost.py --record` 로 다시 잰다" % age


def main():
    if not RECORD.is_file():
        return 0                      # 공용 폴더가 없는 환경에서는 조용히 아무것도 안 한다
    stale = refresh_if_stale()
    if stale:
        # 낡은 채로 «평소보다 나쁘다» 를 말하지 않는다 — 그건 틀린 값을 자신 있게 말하는 것이다.
        print("[세션 비용] " + stale)
        return 0
    try:
        text = RECORD.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    rows = rows_for(text, key(os.getcwd()))
    said = brief(rows)
    if not said:
        return 0                      # ★ 평소에는 **한 글자도 안 낸다**
    print("[세션 비용] 지난 세션이 **자기 평소보다** 나빴다 — 판정은 사람이 한다")
    for line in said:
        print("  · " + line)
    print("  ※ 자세히: `python tools/audit_session_cost.py --sessions=3`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
