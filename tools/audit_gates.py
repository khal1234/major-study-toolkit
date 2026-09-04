# -*- coding: utf-8 -*-
"""**게이트가 진짜 게이트인가** — 자 · 문 · 부르는 자, 셋을 다 본다.

    python 도구/audit_gates.py            # 판정 (반쪽이 있으면 exit 1)
    python 도구/audit_gates.py --selftest # 자를 먼저 잰다
    python 도구/audit_gates.py --quiet

왜 이 자가 필요한가 (2026-08-25)
--------------------------------
이 폴더가 하루 밤에 같은 문장을 **세 번** 적었다 — 규칙도 있고 자도 있는데 그걸 실제로 막는 문이 없다는 진단.

  · `check_narration` — 판정은 멀쩡한데 훅 여덟 중 부르는 것이 **0개**였다.
  · `audit_session_conduct` — 「미검증 방치」를 세는데 **언제나 exit 0** 이라 아무것도 안 막는다.
  · `audit_stamps` — 내가 만들고 **exit 0 으로 두고 잤다**(실행 규율 17 이 금지한 그것).
  · XSanity — deny 네 줄이 **문법 때문에** 죽어 있었고, 삭제 훅은 트리 교집합을 요구해
    사고 난 폴더가 사정권 밖이었다.

**넷 다 「있다」고 보고됐다.** 사람이 목록을 눈으로 훑으면 넷 다 통과한다 —
파일이 실재하고 이름이 그럴듯하기 때문이다. 그래서 **눈이 아니라 자가 본다.**

세 부분 — 하나라도 빠지면 그건 게이트가 아니다
----------------------------------------------
| 부분 | 무엇을 보나 | 빠지면 |
|---|---|---|
| **자** | 그 파일이 실재하나 | 없는 것을 가리키는 목록 |
| **문** | `exit != 0` 을 낼 수 있나 | 숫자만 나오고 아무 일도 안 일어난다 |
| **부르는 자** | 훅·마감·커밋 중 어디서 실제로 부르나 | 손으로 안 돌리면 영영 안 돈다 |

★ **「문」은 정적으로 본다** — 소스에 `exit 1`·`return 1` 계열이 있는가. 실제로 그 가지가
  도는지는 이 자가 **모른다.** 그건 각 자의 `--selftest` 몫이다(그래서 그 칸도 같이 찍는다).
  **못 보는 것을 적어 두는 것이 이 자의 절반이다** — 안 적으면 이 자가 다음번 「있다고 했는데
  아니었다」가 된다.

선언은 자료가 갖는다
--------------------
`기록/게이트-실체.txt` 가 정본이다. 한 줄에 하나:

    <이 게이트가 막는 것> | <자 경로> | <부르는 자리, 쉼표> [| <종류>]

    근거 없는 확정 | 도구/audit_stamps.py | 도구/close_report.py
    실리는 지침이 자랐나 | 도구/audit_guide_size.py | 도구/close_report.py | 래칫:기록/지침-크기-기준선.txt

- `#` 은 주석. 형식이 깨진 줄은 선언으로 안 친다.
- 선언이 없으면 **해당 없음으로 exit 0** (대상 없는 프로젝트에서 실패를 내지 않는다).

★★ 넷째 칸 「래칫」 — **문이 없는 것이 아니라 문이 사람이다** (신설 2026-08-26)
-------------------------------------------------------------------------------
`audit_guide_size` 가 영구히 `FAIL — 문 아님(언제나 exit 0)` 을 냈다. **그 자는 설계상 옳다** —
래칫은 기준선보다 자란 것을 신고하고 판정은 사람이 한다. 어긋난 것은 **선언**이었다.

고치는 길이 둘이었고 **선언에서 빼지 않기로 판정했다** (2026-08-26). 근거 둘:

  ⑴ **래칫이 하나가 아니다.** `audit_magic_numbers`·`audit_check_erosion` 도 같은 성격이라
     빼는 방식이면 그때마다 또 빼야 하고, **빠진 자들이 배선됐는지 아무도 안 보게 된다.**
  ⑵ **래칫에도 문은 있다 — 사람이다.** 기준선을 넘으면 사람이 `--accept` 로 옮기는 것이 그
     문이고, AGENTS 실행 규율 20 이 그것을 정본 절차로 적어 두었다. 그러니 「문이 없다」가
     아니라 **「문이 사람이다」** 가 맞다.

★ **무르게 하려고 만든 칸이 아니다.** 래칫은 `exit != 0` 대신 셋으로 잰다 —
  ⑴ **기준선 파일이 있나** ⑵ **`--accept` 를 받나** ⑶ **부르는 자가 있나.**
  하나라도 없으면 사람이 그 문 앞에 설 수가 없으므로 **여전히 반쪽으로 신고한다.**
☐ 못 보는 것: 기준선이 **실제로 갱신되는지**는 안 본다(파일이 있나만 본다).
"""
import argparse
import ast
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECL_NAME = "게이트-실체.txt"

# 「문」의 정적 표식. 이 자가 보는 것은 **그런 줄이 있나** 뿐이다.
GATE_EXIT = re.compile(r"(sys\.exit\(\s*[12]|return\s+[12]\b|exit\(\s*[12]\s*\))")
SELFTEST_FLAG = re.compile(r"--selftest|--hook-selftest")
# 래칫의 「사람 문」 — 기준선을 옮기는 경로가 소스에 실재하나.
ACCEPT_FLAG = re.compile(r"--accept")
RATCHET = "래칫"
# 참고 게이트 — 세기만 하고 판정·차단은 안 하는 자(AGENTS 도구 등록부가 그렇게 선언한 것).
# 「문 아님(언제나 exit 0)」은 결함이 아니라 설계라 그 사유만 뺀다 — 「부르는 자 0곳」은 그대로 잰다.
ADVISORY = "참고"
# 「부르는 자」에서 뺄 확장자 — 사람이 읽는 문서는 아무것도 실행하지 않는다(나루 2026-08-26,
# `게이트-실체.txt`가 `.py` 대신 `WORKORDER_*.md`를 적어 초록을 준 실사고). `.py`만 세는
# 것도 틀린다 — `.claude/settings.json`은 훅을 실제로 등록하는 자리라 남긴다.
NON_EXECUTABLE_CALLER_EXT = (".md", ".txt", ".rst", ".adoc")


def _strip_selftest(src):
    """자가검정 구간을 도려낸 소스 — 「문」 판정은 `main()`이 낼 수 있나를 물어야 한다.

    나루 2026-08-25 실사고: 파일 전체에서 `return 1`을 찾아 `selftest()` 안에만 있는
    자(예: 래칫류)를 「문 있음」으로 오판했다. `main()`은 전 경로 exit 0인데도 그랬다.
    ☐ 못 보는 것: 이름에 `selftest`가 안 든 검정 함수는 못 도려낸다.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    cut = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and "selftest" in node.name:
            for i in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                cut.add(i)
    if not cut:
        return src
    return chr(10).join(l for i, l in enumerate(src.splitlines(), 1) if i not in cut)


def decl_path(root):
    for folder in ("기록", "docs", "_log", ""):
        p = os.path.join(root, folder, DECL_NAME) if folder else os.path.join(root, DECL_NAME)
        if os.path.isfile(p):
            return p
    return None


def parse_decl(text):
    """`(막는 것, 자, [부르는 자리], 종류, 기준선)`. 순수 함수 — 테스트 대상.

    넷째 칸은 **선택**이다 — 없으면 보통 게이트(`문`)다. `래칫:<기준선 경로>` 로 적으면
    「문이 사람인 자」로 잰다(위 머리말 ★★). **기준선 경로를 코드에 박지 않는 것이 요점**이라
    선언이 그것을 들고 있다 — 자가 자기 기준선을 옮기면 이 줄이 낡아 빨개지고, 그건 옳은
    실패다(선언이 낡은 것을 조용히 넘기면 이 칸이 장식이 된다).
    `참고` 로 적으면 「문 아님(언제나 exit 0)」만 면제한다 — 세기만 하는 것이 설계인 자용
    (AGENTS 도구 등록부가 그렇게 선언한 것). 「부르는 자」는 참고여도 그대로 잰다.
    """
    out = []
    for ln in text.splitlines():
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) < 3 or not parts[0] or not parts[1]:
            continue
        callers = [c.strip() for c in parts[2].split(",") if c.strip()]
        kind, baseline = "문", ""
        if len(parts) > 3 and parts[3]:
            kind, _, baseline = parts[3].partition(":")
            kind, baseline = kind.strip(), baseline.strip()
        out.append((parts[0], parts[1], callers, kind, baseline))
    return out


def ratchet_gate_from(src, baseline_exists):
    """래칫의 「사람 문」이 실재하나 — **순수 함수**(셀프테스트가 문자열을 직접 먹인다).

    ★ 둘 다 있어야 한다. `--accept` 만 있고 기준선 파일이 없으면 사람이 **옮길 것이 없고**,
      기준선만 있고 `--accept` 가 없으면 **옮길 길이 없다.** 둘 중 하나면 그건 여전히
      숫자만 찍는 자다.
    """
    return bool(ACCEPT_FLAG.search(src)) and bool(baseline_exists)


def ratchet_gate(root, tool, baseline):
    """파일을 읽어 위 순수 함수에 넘긴다. 기준선 선언이 없으면 **문이 없는 것으로 친다.**"""
    full = tool if os.path.isabs(tool) else os.path.join(root, tool)
    if not os.path.isfile(full):
        return False
    src = io.open(full, encoding="utf-8", errors="replace").read()
    base = baseline if os.path.isabs(baseline) else os.path.join(root, baseline)
    return ratchet_gate_from(src, bool(baseline) and os.path.isfile(base))


def judge(root, tool, callers):
    """`(자, 문, 부르는자, 자기검정)` 넷을 판정. 순수에 가깝게 — 파일만 읽는다."""
    full = tool if os.path.isabs(tool) else os.path.join(root, tool)
    if not os.path.isfile(full):
        return False, False, 0, False
    src = io.open(full, encoding="utf-8", errors="replace").read()
    gate = bool(GATE_EXIT.search(_strip_selftest(src)))
    selft = bool(SELFTEST_FLAG.search(src))
    name = os.path.basename(tool)
    hit = 0
    for c in callers:
        if os.path.splitext(c)[1].lower() in NON_EXECUTABLE_CALLER_EXT:
            continue
        cf = c if os.path.isabs(c) else os.path.join(root, c)
        if not os.path.isfile(cf):
            continue
        csrc = io.open(cf, encoding="utf-8", errors="replace").read()
        # ★★ **선언을 읽어 도는 자는 선언된 것 전부를 부른다** (2026-08-25, 실사고).
        #   `close_gates.py` 는 `게이트-실체.txt` 를 읽어 그 안의 자를 돌린다 — 이름이
        #   소스에 **글자로 없다**. 첫 판은 이름 문자열만 봐서 「부르는 자 0곳」을 냈고,
        #   **실제로는 부르는데 안 부른다고 신고**했다. 이 폴더가 반복해 잡아 온
        #   「분류의 근거는 이름이 아니라 자료가 들고 있는 꼬리표」의 그 부류다.
        #   → 그 파일이 **선언 파일 이름을 읽고 있으면** 선언된 것을 부르는 자로 친다.
        #   ☐ 못 보는 것: 선언을 읽되 **일부만** 돌리는 자는 여기서 구별 못 한다.
        if name in csrc or DECL_NAME in csrc:
            hit += 1
    return True, gate, hit, selft


# ★★ **경로를 박지 않는다** (2026-08-25, 이 자가 첫 자동 실행에서 스스로 잡혔다).
#   첫 판은 `도구/audit_gates.py` 를 박아 뒀는데, 전공정리는 `tools/` 라 **이식하자마자
#   자기 검정이 실패했다.** 「도구 폴더 이름을 박으면 가져간 쪽에서 죽는다」는 이 계통이
#   `commit.py` 에서 네 번 겪은 그 부류이고, **자기 검정 안에서 또 밟았다.**
#   → 자기 위치에서 유도한다. 어느 배치에서든 같은 답이 나온다.
SELF_REL = os.path.relpath(os.path.abspath(__file__), ROOT).replace("\\", "/")
SELFTEST_DECL = ("# 주석은 무시된다\n있는 자 | %s | %s\n형식깨짐 | 하나만\n"
                 "래칫인 자 | %s | %s | %s:docs/없는-기준선.txt\n"
                 % (SELF_REL, SELF_REL, SELF_REL, SELF_REL, RATCHET))


def selftest():
    bad = 0
    d = parse_decl(SELFTEST_DECL)
    ok = len(d) == 2 and d[0][0] == "있는 자"
    bad += 0 if ok else 1
    print("  %s 선언 파서 — 주석·깨진 줄을 버린다 (%d줄 남음)"
          % ("OK  " if ok else "**틀림**", len(d)))

    # ★ 넷째 칸 (신설 2026-08-26) — 없으면 「문」, `래칫:<기준선>` 이면 래칫이다.
    ok = d and d[0][3] == "문" and d[0][4] == ""
    bad += 0 if ok else 1
    print("  %s 넷째 칸이 없으면 보통 게이트로 친다 (옛 3칸 선언이 그대로 돈다)"
          % ("OK  " if ok else "**틀림**"))

    ok = len(d) == 2 and d[1][3] == RATCHET and d[1][4] == "docs/없는-기준선.txt"
    bad += 0 if ok else 1
    print("  %s `%s:<기준선>` 을 종류와 기준선 경로로 가른다 (%s)"
          % ("OK  " if ok else "**틀림**", RATCHET,
             repr(d[1][3:]) if len(d) == 2 else "줄이 없다"))

    ok = ratchet_gate_from("ap.add_argument('--accept', action='store_true')", True)
    bad += 0 if ok else 1
    print("  %s 양성 — 기준선이 있고 `--accept` 를 받으면 「문이 사람」이다"
          % ("OK  " if ok else "**틀림**"))

    ok = not ratchet_gate_from("print('자란 것 %d개' % n)", True)
    bad += 0 if ok else 1
    print("  %s 음성 — `--accept` 가 없으면 사람이 기준선을 **옮길 길이 없다**"
          % ("OK  " if ok else "**틀림**"))

    ok = not ratchet_gate_from("ap.add_argument('--accept')", False)
    bad += 0 if ok else 1
    print("  %s 음성 — 기준선 파일이 없으면 사람이 **옮길 것이 없다** "
          "(무르게 하려고 만든 칸이 아니다)" % ("OK  " if ok else "**틀림**"))

    ok = not ratchet_gate(ROOT, SELF_REL, "docs/없는-기준선.txt")
    bad += 0 if ok else 1
    print("  %s 음성 — 선언한 기준선이 **실재하지 않으면** 반쪽으로 남는다"
          % ("OK  " if ok else "**틀림**"))

    d2 = parse_decl("참고인 자 | %s | | %s\n" % (SELF_REL, ADVISORY))
    ok = len(d2) == 1 and d2[0][3] == ADVISORY
    bad += 0 if ok else 1
    print("  %s `참고` 를 종류로 읽는다(부르는 자 0곳이어도 「문 아님」만 뺀다)"
          % ("OK  " if ok else "**틀림**"))

    e, g, h, s = judge(ROOT, SELF_REL, [SELF_REL])
    ok = e and g and h == 1 and s
    bad += 0 if ok else 1
    print("  %s 양성 — 자기 자신은 자·문·부르는자·검정 넷 다 있다 (%s %s %d %s)"
          % ("OK  " if ok else "**틀림**", e, g, h, s))

    e, g, h, s = judge(ROOT, os.path.dirname(SELF_REL) + "/없는자.py", [])
    ok = not e
    bad += 0 if ok else 1
    print("  %s 음성 — 없는 자는 「자 없음」으로 잡힌다" % ("OK  " if ok else "**틀림**"))

    e, g, h, s = judge(ROOT, SELF_REL, [])
    ok = e and not h
    bad += 0 if ok else 1
    print("  %s 음성 — 부르는 자리를 안 적으면 0곳으로 잡힌다" % ("OK  " if ok else "**틀림**"))

    L = chr(10)
    only_in_selftest = "def main():" + L + "    return 0" + L + L + "def selftest():" + L + "    return 1" + L
    in_main = "def main():" + L + "    return 1" + L + L + "def selftest():" + L + "    return 1" + L
    ok = not GATE_EXIT.search(_strip_selftest(only_in_selftest))
    bad += 0 if ok else 1
    print("  %s ★ 양성 — `return 1` 이 자가검정 안에만 있으면 문이 아니다"
          % ("OK  " if ok else "**틀림**"))
    ok = bool(GATE_EXIT.search(_strip_selftest(in_main)))
    bad += 0 if ok else 1
    print("  %s ★ 음성 — `main()` 에 있는 진짜 문은 안 지운다" % ("OK  " if ok else "**틀림**"))
    ok = _strip_selftest("def main(:") == "def main(:"
    bad += 0 if ok else 1
    print("  %s 음성 — 못 읽는 소스는 원본 그대로(조용히 통과 안 시킨다)"
          % ("OK  " if ok else "**틀림**"))

    for desc, ext, want in [
        ("★ 양성 — `.md` 는 부르는 자로 안 센다", ".md", True),
        ("양성 — `.txt` 선언 파일도 부르는 자가 아니다", ".txt", True),
        ("★ 음성 — `.json` 은 센다(settings.json 이 훅을 진짜 등록한다)", ".json", False),
        ("음성 — `.py` 는 당연히 센다", ".py", False),
    ]:
        skipped = ext.lower() in NON_EXECUTABLE_CALLER_EXT
        ok = skipped == want
        bad += 0 if ok else 1
        print("  %s %s" % ("OK  " if ok else "**틀림**", desc))

    print("\n  ※ ☐ 이 자가 **못 보는 것**: 「문」은 소스에 `exit 1` 계열이 있나만 본다 —")
    print("     **그 가지가 실제로 도는지는 모른다.** 그건 각 자의 `--selftest` 몫이라")
    print("     검정 칸을 따로 찍는다. 검정이 없는 자의 「문」은 **미검증**이다.")
    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=ROOT)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    # ★★★ 사슬의 끝을 잇는 자리 (2026-08-25). `--selftest` 는 **아무도 자동으로 안 불렀다** —
    #   실측 grep 0건(`close_report`·`commit.py`·`settings.json`). 자기 검정을 셋이나 붙여
    #   놓고 전부 **손으로만** 돌리고 있었고, 손으로 돌리는 자는 바쁜 날 안 돈다.
    ap.add_argument("--run-selftests", action="store_true",
                    help="선언된 자들의 --selftest 를 실제로 돌린다 (close_report 가 쓴다)")
    a = ap.parse_args()
    if a.selftest:
        print("[자기 검정] 게이트 감사기")
        return selftest()

    root = os.path.abspath(a.root)
    dp = decl_path(root)
    if not dp:
        if not a.quiet:
            print("[게이트 감사] 선언이 없다 — **해당 없음** (실패가 아니다)")
            print("  `기록/%s` 에 한 줄씩: <막는 것> | <자> | <부르는 자리>" % DECL_NAME)
        return 0

    decls = parse_decl(io.open(dp, encoding="utf-8", errors="replace").read())
    if not decls:
        print("[게이트 감사] 선언은 있는데 **성립하는 줄이 0개다**: %s" % dp, file=sys.stderr)
        return 1

    half = []
    print("[게이트 감사] 자 · 문 · 부르는 자 — 하나라도 빠지면 게이트가 아니다")
    print("%-30s %-26s %4s %4s %4s %6s %6s"
          % ("막는 것", "자", "종류", "자", "문", "부름", "검정"))
    for what, tool, callers, kind, baseline in decls:
        e, g, h, s = judge(root, tool, callers)
        # ★ 래칫은 `exit != 0` 대신 **기준선 · `--accept` · 부르는 자** 셋으로 잰다.
        #   「문이 없다」가 아니라 **「문이 사람이다」** 이기 때문이다(머리말 ★★).
        ratchet = kind == RATCHET
        advisory = kind == ADVISORY
        if ratchet and e:
            g = ratchet_gate(root, tool, baseline)
        why = []
        if not e:
            why.append("자 없음")
        else:
            if not g and not advisory:
                why.append("**래칫인데 사람 문이 없다(기준선·`--accept` 확인)**" if ratchet
                           else "**문 아님(언제나 exit 0)**")
            if not h:
                why.append("**부르는 자 0곳**")
        kind_label = RATCHET if ratchet else (ADVISORY if advisory else "문")
        door_label = ("人" if g else "X") if ratchet else (("참고" if advisory and not g else "O") if g or advisory else "X")
        print("%-30s %-26s %4s %4s %4s %6s %6s%s"
              % (what[:30], os.path.basename(tool)[:26], kind_label,
                 "O" if e else "X", door_label,
                 h, "O" if s else "-",
                 ("   ← " + " · ".join(why)) if why else ""))
        if why:
            half.append((what, why))

    print()
    print("  ※ **검정 `-`** 은 그 자에 `--selftest` 가 없다는 뜻 — 「문」이 실제로 도는지 **미검증**이다.")
    print("  ※ **문 `人`** 은 래칫이라 **판정하는 문이 사람**이라는 뜻이다(실행 규율 20 —")
    print("     자란 것이 정당하면 사람이 `--accept` 로 기준선을 옮긴다). 면제가 아니라")
    print("     **기준선 파일과 `--accept` 경로가 실재하는지**를 대신 잰 것이다.")

    if a.run_selftests:
        # ★★ **자를 재고 나서 재는 것이 순서다.** 대조군을 안 돌린 자의 「0건」은
        #   «없다» 가 아니라 «자가 못 봤다» 이므로(공용 「규칙/증거의-정직.md」 ⑴),
        #   이 자리가 없으면 위 표 전체가 그 위에 서 있게 된다.
        # ☐ 못 보는 것: `--selftest` 가 **없는** 자는 여기서 통과도 실패도 아니고
        #   **미검증**이다. 그 목록을 찍어 두는 것이 이 블록의 절반이다.
        print()
        print("[자기 검정 연쇄] 선언된 자들의 대조군을 실제로 돌린다")
        unverified = []
        for what, tool, _callers, _kind, _baseline in decls:
            full = tool if os.path.isabs(tool) else os.path.join(root, tool)
            if not os.path.isfile(full):
                continue
            if not SELFTEST_FLAG.search(io.open(full, encoding="utf-8",
                                                errors="replace").read()):
                unverified.append(os.path.basename(tool))
                continue
            try:
                r = subprocess.run([sys.executable, full, "--selftest"],
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=120, cwd=root)
                code = r.returncode
            except (OSError, subprocess.SubprocessError) as e:
                code, r = 1, None
                print("  ✘ %-28s 못 돌렸다: %s" % (os.path.basename(tool), e))
            # ★★ **「그 낱말이 있다」와 「그 깃발을 받는다」는 다르다** (2026-08-25, 첫 자동
            #   실행에서 드러났다). `SELFTEST_FLAG` 는 소스에 그 글자가 있나만 본다 —
            #   설명·주석에 적어 둔 파일까지 걸려 `--selftest` 를 모르는 자에게 그 깃발을
            #   넘겼고, argparse 가 «unrecognized arguments» 로 죽어 **가짜 실패**가 났다
            #   (전공정리 `test_checks.py`). 이름 어림으로 판정한 그 부류다.
            #   → 그 오류는 **실패가 아니라 「대조군 없음」** 으로 돌린다.
            if r is not None and code != 0 and "unrecognized arguments" in (r.stderr or ""):
                unverified.append(os.path.basename(tool))
                continue
            if r is not None:
                print("  %s %-28s %s" % ("✔" if code == 0 else "✘",
                                         os.path.basename(tool),
                                         "대조군 통과" if code == 0 else "**대조군 실패**"))
            if code != 0:
                half.append((what, ["**자기 검정 실패**"]))
        if unverified:
            # ★ **찍는 수와 보여주는 목록이 같아야 한다.** 한 자가 선언에 두 줄이면
            #   원수는 6, 목록은 5가 되어 «둘 중 하나는 거짓말» 이 된다(같은 자가
            #   `close_report` 에서 두 번 세어진 실측). 세는 것도 겹을 뺀 뒤에 센다.
            uniq = sorted(set(unverified))
            print("  — 대조군이 **없는** 자 %d개(미검증): %s" % (len(uniq), ", ".join(uniq)))
            print("    ※ 실패가 아니다. **다음에 대조군을 붙일 목록**이다.")

    # ★★★ **「자 없음」은 막지 않는다** (2026-08-25, 마감에서 드러난 설계 결함).
    #   선언에 「아직 못 만든 것」을 적으면(「못 막는 것도 적는다」) 그 줄이 자 없음으로 뜬다.
    #   그걸 FAIL 로 치면 **마감이 영영 안 난다** — 못 지우는 빨간불은 게이트가 아니라 **벽**이고,
    #   벽이 서면 그 아래 멀쩡한 줄까지 함께 무시된다. 더 나쁜 것은 **안 적는 쪽이 유리해지는**
    #   것이다: 구멍을 선언에서 지우면 초록이 된다. 그러면 이 자가 정반대로 작동한다.
    #   → **막는 것은 「자는 있는데 문이 없거나 아무도 안 부르는 것」** 뿐이다. 그건 회귀다.
    #     자 없음은 **할 일 목록**이라 찍기만 한다(같은 판정선을 `weekly_check` 도 쓴다).
    missing = [(w, y) for w, y in half if any("자 없음" in s for s in y)]
    broken = [(w, y) for w, y in half if not any("자 없음" in s for s in y)]
    if missing:
        print("\n  — 아직 **자가 없는** 것 %d개 (할 일 목록 · 막지 않는다):" % len(missing))
        for what, _ in missing:
            print("      · " + what)
    if broken:
        print("\nFAIL — 반쪽 게이트 %d개. **「있다」고 보고되지만 아무것도 안 막는다.**"
              % len(broken), file=sys.stderr)
        for what, why in broken:
            print("  · %s — %s" % (what, " · ".join(why)), file=sys.stderr)
        return 1
    if not a.quiet:
        print("전부 자·문·부르는 자 셋을 갖췄다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
