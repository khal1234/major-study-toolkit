# -*- coding: utf-8 -*-
"""세션 기록을 읽어 **도구 호출을 얼마나 묶어 불렀는지** 잰다 (읽기 전용).

    python tools/audit_tool_parallelism.py              # 최근 세션 5개
    python tools/audit_tool_parallelism.py --sessions=20
    python tools/audit_tool_parallelism.py --file=<jsonl>

왜 (2026-08-12): 외부 제보가 *"모델이 도구를 순차로 부르면 같은 일을 하고도 컨텍스트를
그 횟수만큼 다시 넣게 된다"* 고 지적했다. 타당한 주장이지만 **우리에게 해당하는지는 재 봐야
안다** — 이 리포의 규칙 11 은 *"수량 주장은 스크립트 출력에서 온 것이어야 한다"* 다.

무엇을 재나:
  ⑴ **묶음률** — 한 assistant 메시지에 도구 호출이 2개 이상이면 그 호출들은 한 번의
     컨텍스트 입력을 나눠 쓴다. `묶여 나간 호출 / 전체 호출`.
  ⑵ **왕복 수** — 도구를 부른 메시지 수. 같은 호출 수라면 이게 작을수록 싸다.
  ⑶ **검증 반복** — 빌드·회귀·감사를 한 세션에서 몇 번 돌렸나. 잦으면 「모아서 한 번」의 대상이다.

★ **이 자는 「낮으면 나쁘다」를 뜻하지 않는다.** 앞 결과를 봐야 다음을 정하는 호출은 묶을 수
  없다(읽고 → 고치고 → 돌린다). 그래서 묶음률의 목표치를 두지 않고 **추세**로 본다.
  숫자를 목표로 삼으면 의존이 있는 호출까지 묶어 오히려 틀린 일을 하게 된다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 세션 기록은 홈의 Claude 폴더에 있다. **읽기만 한다**(규칙 5 는 쓰기를 막는 규칙이다).
ROOT = Path.home() / ".claude" / "projects"
VERIFY_MARKS = ("build_site.py", "test_checks.py", "build_review.py",
                "audit_content.py", "close_report.py", "verify_workorder.py")


def sessions(limit=5, only=None):
    if only:
        return [Path(only)]
    files = [p for p in ROOT.rglob("*.jsonl") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def measure(path):
    """(호출 수, 도구를 부른 메시지 수, 묶여 나간 호출 수, 검증 명령 Counter). 순수 함수."""
    # ★ 기록은 **호출 하나에 레코드 하나**로 쪼개 저장한다. 그래서 레코드만 세면 묶음률이
    #   언제나 0% 로 나온다(첫 실행에서 실제로 그랬다 — 자를 안 고쳤으면 "우리는 하나도
    #   안 묶는다"는 **틀린 보고**를 낼 뻔했다). 같은 응답에서 나간 호출은 **같은 응답 id**
    #   를 공유하므로 그것으로 묶는다.
    groups = Counter()
    verify = Counter()
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message") or {}
            if msg.get("role") != "assistant":
                continue
            blocks = [b for b in (msg.get("content") or [])
                      if isinstance(b, dict) and b.get("type") == "tool_use"]
            if not blocks:
                continue
            key = msg.get("id") or rec.get("requestId") or rec.get("uuid")
            groups[key] += len(blocks)
            for b in blocks:
                cmd = str((b.get("input") or {}).get("command", ""))
                for mark in VERIFY_MARKS:
                    if mark in cmd:
                        verify[mark] += 1
    calls = sum(groups.values())
    turns = len(groups)
    batched = sum(n for n in groups.values() if n >= 2)
    return calls, turns, batched, verify


def selftest():
    import tempfile

    bad = 0

    def chk(desc, cond, got=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %-46s %s" % ("OK  " if cond else "**틀림**", desc, got))

    recs = [
        # 한 메시지(id=m1)에 도구 호출 2개 — 묶음
        {"message": {"role": "assistant", "id": "m1", "content": [
            {"type": "tool_use", "input": {"command": "echo a"}},
            {"type": "tool_use", "input": {"command": "python tools/test_checks.py"}},
        ]}},
        # 다른 메시지(id=m2)에 도구 호출 1개 — 안 묶임
        {"message": {"role": "assistant", "id": "m2", "content": [
            {"type": "tool_use", "input": {"command": "echo b"}},
        ]}},
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                      encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
        tmp = Path(fh.name)

    calls, turns, batched, verify = measure(tmp)
    chk("호출 총수(3개)를 센다", calls == 3, "calls=%d" % calls)
    chk("왕복(응답 id 2개)을 센다", turns == 2, "turns=%d" % turns)
    chk("묶여 나간 호출(m1 의 2개)만 센다", batched == 2, "batched=%d" % batched)
    chk("검증 명령(test_checks.py)을 잡는다",
        verify.get("test_checks.py") == 1, str(dict(verify)))

    tmp.unlink(missing_ok=True)
    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    limit, only = 5, None
    for arg in sys.argv[1:]:
        if arg.startswith("--sessions="):
            limit = int(arg.split("=", 1)[1])
        elif arg.startswith("--file="):
            only = arg.split("=", 1)[1]
    paths = sessions(limit, only)
    if not paths:
        print("[해당 없음] 세션 기록을 못 찾았다 — %s" % ROOT)
        return 0
    tot_calls = tot_turns = tot_batched = 0
    agg = Counter()
    print("%-14s %7s %7s %8s  %s" % ("세션", "호출", "왕복", "묶음률", "검증 반복"))
    for p in paths:
        calls, turns, batched, verify = measure(p)
        if not calls:
            continue
        tot_calls += calls
        tot_turns += turns
        tot_batched += batched
        agg += verify
        top = " ".join("%s×%d" % (k.replace(".py", ""), v)
                       for k, v in verify.most_common(3)) or "—"
        print("%-14s %7d %7d %7.0f%%  %s" % (p.stem[:12], calls, turns,
                                             100.0 * batched / calls, top))
    if not tot_calls:
        print("도구 호출이 없다")
        return 0
    print("\n합계 — 호출 %d · 왕복 %d · **묶음률 %.0f%%** (호출/왕복 = %.2f)"
          % (tot_calls, tot_turns, 100.0 * tot_batched / tot_calls, tot_calls / tot_turns))
    if agg:
        print("검증 반복 — " + " · ".join("%s %d회" % (k, v) for k, v in agg.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
