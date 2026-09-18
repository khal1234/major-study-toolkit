# -*- coding: utf-8 -*-
"""**「0건」이 「없다」인가 「못 봤다」인가** — 감사 도구가 자기 순회 범위를 밝히는가.

    python tools/audit_sweep_reach.py            # 판정 (조용한 0건이 늘면 exit 1)
    python tools/audit_sweep_reach.py --selftest # 자를 먼저 잰다
    python tools/audit_sweep_reach.py --accept   # 기준선을 지금 값으로 옮긴다
    python tools/audit_sweep_reach.py --quiet

## 왜 이 자가 필요한가 (2026-09-09)

사용자 지적: *[발화 생략]* — 다른 프로젝트에서 **[발화 생략]이 실은 자가 죽어 있어 1건만 보였던 것**으로 드러난 일이 있었고, 이 리포에도 같은 부류가
쌓여 있다는 것이다. 실제로 **같은 날 두 번** 났다:

- `audit_figure_balance --all` 이 796 삽화 **0건**을 냈는데, 같은 판정을 빌드에 붙이자 90여 건이
  나왔다. `--all` 이 **슬라이드 프레임을 안 펴서** 그만큼을 안 보고 있었다.
- `audit_theory_figure_reasons` 가 **장 단위**라 절 13 개에 삽화 2 개인 장을 통과시켰다.
  사용자가 화면을 보고 잡았다.

AGENTS 규칙 11 이 이미 *[발화 생략]* 라고
적어 두었다. **그 규칙을 기계로 옮긴 자가 없었다.**

## 무엇을 세나 — 두 축

⑴ **조용한 0건.** `--only=` 를 받는 도구에 **없는 과목 이름**을 준다. 대상이 하나도 없는데
   그 사실을 말하지 않고 정상 종료하면 신고한다. 「없는 과목을 물었더니 0건」과 「진짜 0건」이
   화면에서 구별되지 않으면, 오타 하나로 감사 전체가 조용히 죽는다.
⑵ **범위를 안 찍는 순회 도구.** 데이터를 훑는데 「몇 개를 봤나」를 출력하지 않는 도구.
   후보로만 낸다(판정은 사람) — 출력이 표 하나뿐인 도구도 있다.

## ☐ 이 자가 못 보는 것 (규칙 21)

- **`--only=` 가 없는 도구는 ⑴ 에서 안 본다.** 순회 범위를 다른 인자로 받는 도구는 사각지대다.
- **표식은 낱말로 찾는다.** 「대상」·「없」 같은 말로 정직함을 판정하므로, 다른 말로 밝히는
  도구는 억울하게 걸린다 — 그때는 낱말을 늘리지 말고 **그 도구가 쓰는 말을 표준에 맞춘다.**
- **도구가 실제로 옳게 세는지는 안 본다.** 이 자가 보는 것은 「범위를 밝히나」 하나다.
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
TOOLS = os.path.join(ROOT, "tools")
BASELINE = os.path.join(ROOT, "docs", "순회범위-기준선.txt")

# 있을 수 없는 과목 이름. 어느 과목 폴더에도 부분일치하지 않아야 한다.
NO_SUCH_SUBJECT = "존재하지않는과목ZZZ"
# 「대상이 없다」를 밝히는 말. 늘리는 것은 마지막 수단이다(독스트링 ☐ 참조).
HONEST_MARKS = ("대상", "해당 없음", "없다", "없음", "0개 과목", "훑은 과목 0")
# 순회 규모를 찍었다고 볼 표식.
REACH_MARKS = ("훑은", "순회", "합계 —", "훑음")
# `--only=` 를 실제로 받는가.
ONLY_FLAG = re.compile(r'--only')
# 데이터를 훑는가 — 과목 폴더나 챕터 목록을 쓰는 도구.
SWEEPS_DATA = re.compile(r"subject_dirs|audit_content\.CHAPTERS|for_each_subject|DATA\b")
# 한 번 돌리는 데 이만큼 넘게 걸리면 「없는 과목」조차 순회한다는 뜻이라 시간을 끊는다.
RUN_TIMEOUT_S = 90

# 순회 도구가 아니거나 이 자의 대상이 아닌 것 — 세션·도구·문서 감사.
NOT_A_DATA_SWEEP = {
    "audit_gates.py", "audit_orphan_checks.py", "audit_check_erosion.py",
    "audit_guide_size.py", "audit_magic_numbers.py", "audit_scope_claims.py",
    "audit_stamps.py", "audit_session_conduct.py", "audit_session_cost.py",
    "audit_serial_waits.py", "audit_tool_parallelism.py", "audit_deps.py",
    "audit_path_names.py", "audit_fix_tool_coverage.py", "audit_fix_backlog.py",
    "audit_dropped_input.py", "audit_checks_load.py", "audit_sweep_reach.py",
    # 라이브러리 겸 감사 본체 — 다른 자들이 임포트해 쓰는 자리라 이 자의 대상이 아니다.
    # (`reject_unmatched_only` 독스트링의 `--only` 때문에 필터를 받는 것으로 잡혔다.)
    "audit_content.py",
}


def audit_tools():
    return sorted(f for f in os.listdir(TOOLS)
                  if f.startswith("audit_") and f.endswith(".py")
                  and f not in NOT_A_DATA_SWEEP)


def source_of(name):
    with io.open(os.path.join(TOOLS, name), encoding="utf-8", errors="replace") as fh:
        return fh.read()


def takes_only(src):
    """`--only` 를 인자로 받는가. 순수 함수."""
    return bool(ONLY_FLAG.search(src))


def sweeps_data(src):
    """데이터(과목·챕터)를 훑는가. 순수 함수."""
    return bool(SWEEPS_DATA.search(src))


def declares_reach(text):
    """출력이 순회 규모를 밝히나. 순수 함수."""
    return any(m in text for m in REACH_MARKS)


def admits_empty(text, code):
    """대상이 하나도 없을 때 그 사실을 말하나. 순수 함수."""
    return code != 0 or any(m in text for m in HONEST_MARKS)


def run_with_no_match(name):
    """없는 과목 이름을 주고 돌린다. (출력, 종료코드) — 못 돌리면 (None, None)."""
    try:
        r = subprocess.run([sys.executable, os.path.join("tools", name),
                            "--only=" + NO_SUCH_SUBJECT],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=RUN_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None, None
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def read_baseline():
    try:
        with io.open(BASELINE, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    return int(line)
    except (OSError, ValueError):
        return None
    return None


def selftest():
    """대조군 — 이 자가 정직한 출력과 조용한 0건을 갈라내는가."""
    ok = True

    def expect(what, cond):
        nonlocal ok
        print("  %s %s" % ("[ok]  " if cond else "[FAIL]", what))
        ok = ok and bool(cond)

    expect("정상 종료에 표식이 없으면 조용한 0건이다", not admits_empty("합계 — 0건", 0))
    expect("「대상 없음」을 말하면 정직하다", admits_empty("[대상 없음] 그 과목이 없다", 0))
    expect("exit≠0 도 정직으로 본다", admits_empty("합계 — 0건", 1))
    expect("훑은 수를 찍으면 범위를 밝힌 것이다", declares_reach("합계 — 훑은 과목 21개"))
    expect("표만 찍으면 범위를 안 밝힌 것이다", not declares_reach("| 장 | 절 |"))
    expect("--only 를 찾는다", takes_only('p.add_argument("--only")'))
    expect("--only 가 없으면 못 찾는다", not takes_only("def main(): pass"))
    expect("데이터 순회를 알아본다", sweeps_data("for d in audit_content.subject_dirs():"))
    expect("세션 감사는 순회로 안 본다", not sweeps_data("read_transcript()"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="감사 도구가 자기 순회 범위를 밝히는가")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--accept", action="store_true", help="기준선을 지금 값으로 옮긴다")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        print("[자기 검정] 순회 범위 감사")
        return selftest()

    quiet_zero, no_reach, unrunnable = [], [], []
    for name in audit_tools():
        src = source_of(name)
        if not sweeps_data(src):
            continue
        if takes_only(src):
            out, code = run_with_no_match(name)
            if out is None:
                unrunnable.append(name)
            elif not admits_empty(out, code):
                quiet_zero.append(name)
            elif not declares_reach(src):
                # ★ 범위 표시는 **소스**로 본다(첫 실행이 고친 자리 — 규칙 21).
                #   없는 과목으로 돌린 출력에는 당연히 순회 규모가 없으므로, 그 출력으로
                #   재면 정직하게 끝난 자가 그대로 「범위 미표시」로 신고된다.
                no_reach.append(name)
        elif not declares_reach(src):
            no_reach.append(name + " (--only 없음 — 손으로 잰다)")

    if quiet_zero:
        print("[조용한 0건] 없는 과목을 물었는데 **아무 말 없이 정상 종료**한다")
        print("   ※ 오타 하나로 이 감사 전체가 죽는다 — 「대상 없음」을 찍게 할 것")
        for name in quiet_zero:
            print("   · " + name)
    if unrunnable and not a.quiet:
        print("\n[못 돌렸다] 시간 초과나 오류 — 사람이 본다")
        for name in unrunnable:
            print("   · " + name)
    if no_reach and not a.quiet:
        print("\n[범위 미표시] 후보 — 몇 개를 훑었는지 출력에 없다(표만 내는 도구도 있다)")
        for name in no_reach:
            print("   · " + name)

    base = read_baseline()
    print("\n합계 — 조용한 0건 %d개 · 범위 미표시 %d개 · 못 돌린 것 %d개"
          % (len(quiet_zero), len(no_reach), len(unrunnable)))
    if a.accept:
        with io.open(BASELINE, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# 조용한 0건의 기준선(래칫) — 늘면 막힌다. 줄이면 이 수를 낮춘다.\n")
            fh.write("# 재는 자: python tools/audit_sweep_reach.py\n")
            fh.write("%d\n" % len(quiet_zero))
        print("기준선 갱신 — 조용한 0건 %d개. **이 커밋이 곧 기록이다.**" % len(quiet_zero))
        return 0
    if base is None:
        print("※ 기준선을 못 읽었다 — 엄한 쪽으로 본다")
        return 1
    if len(quiet_zero) > base:
        print("※ 기준선 %d 보다 늘었다 — 새로 만든 감사에 「대상 없음」을 찍게 할 것" % base)
        return 1
    if len(quiet_zero) < base:
        print("※ 기준선 %d 보다 줄었다 — `--accept` 로 낮출 것" % base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
