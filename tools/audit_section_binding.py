# -*- coding: utf-8 -*-
r"""문항이 **어느 이론 절에 붙는지**를 잰다 — 회차 구조가 서려면 이 실이 있어야 한다.

    python tools/audit_section_binding.py                 # 전 과목 요약
    python tools/audit_section_binding.py --only=<과목>
    python tools/audit_section_binding.py --gaps          # 1회차에 빈 절만 나열
    python tools/audit_section_binding.py --fail-only

열린 날 2026-09-10. 사용자 원문 —
*[발화 생략]*.

**무엇이 없었나 — 문항과 절을 잇는 실이 아예 없다.** `practice[]` 에는 `section` 필드가 없고
`problems[]` 도 `relatedFormulas`(유도 카드)만 갖는다. 그래서 화면은 **종류별로만** 묶을 수
있었고(이론 전부 → 유도 전부 → 문풀 전부), 사용자가 짚은 거부감이 거기서 나왔다.

**이 자가 재는 것 셋**

1. **미선언** — `section` 이 없는 문항 수. 회차 화면이 그 문항을 어디에도 못 놓는다.
2. **끊어진 실** — `section` 이 있는데 그런 절 id 가 없는 것. 절 id 를 고치면 조용히 생긴다.
3. **1회차 구멍** — 이론 절 가운데 `difficulty: basic` 문풀이 **하나도 없는** 절.
   사용자가 말한 [발화 생략]가 실제로 없는 자리다.

☐ **이 자는 판정하지 않는다.** 셋째는 특히 그렇다 — 정의만 있고 계산이 없는 절(과목 개요,
낱말 정리)에는 딸깍 문항이 없는 것이 맞다. 문턱은 실측을 보고 사람이 정한다
(워크오더 `docs/2026-09-10-학습-회차-구조.workorder.md` 의 C56 줄).

☐ **`ramp` 와 헷갈리지 않는다.** `ramp` 는 지문의 부담, `difficulty` 는 계산의 난이도,
`section` 은 붙는 자리다. 셋은 서로 독립이고 이 자는 셋째만 본다.

☐ **요약·모의고사 장(`ch90` 이상)은 안 본다** — 아래 `SUMMARY_CHAPTER_FROM` 주석이 사유다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from audit_content import ROOT, subject_dirs                              # noqa: E402

COLLECTIONS = ("practice", "problems")
EASY = "basic"

# 요약·모의고사 장(`ch90` 이상)은 이 자의 대상이 아니다.
# ★ **둘째 실행이 이 상수를 만들었다 (규칙 21).** 모의고사 장은 **여러 장에서 뽑아 섞은 시험지**라
#   그 장의 이론 절 둘(안내·정리)에 문항을 붙이는 것이 애초에 뜻이 없다. 그런데 첫 판은 그 장의
#   문항 20개를 전부 「미선언」으로 세어, 응용열역학의 잔량이 실제보다 40 건 크게 보였다.
#   회차 스위치도 그 장에서는 안 뜬다(`section` 이 하나도 없으므로) — 세는 쪽만 어긋나 있었다.
#   `audit_theory_figure_reasons.SUMMARY_CHAPTER_FROM` 과 같은 판정선이고 근거도 같다.
SUMMARY_CHAPTER_FROM = 90


def is_summary_chapter(stem):
    """`ch90` 이상이면 참. 파일 이름만 보고 정한다(데이터에 시험 표시가 없는 장이 있다)."""
    digits = stem[2:]
    return digits.isdigit() and int(digits) >= SUMMARY_CHAPTER_FROM


def chapter_files(folder):
    return sorted(n for n in os.listdir(folder)
                  if n.startswith("ch") and n.endswith(".json") and len(n) == 9
                  and not is_summary_chapter(n.rsplit(".", 1)[0]))


def blob(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def theory_sections(ch):
    """이론 절 목록. `{"sections": [...]}` 와 그냥 목록 두 꼴을 다 받는다.

    ★ 두 꼴을 다 받는 이유 — 이 리포에 실제로 둘 다 있다. 한 꼴만 가정하면 다른 꼴의
      과목에서 **절 0개**로 읽혀 「구멍 없음」이라는 거짓 초록이 나온다.
    """
    node = ch.get("theory")
    if isinstance(node, dict):
        node = node.get("sections")
    return [s for s in (node or []) if isinstance(s, dict)]


def scan(ch):
    """(절 id 목록, 미선언, 끊어진 실, 1회차 구멍). 순수 함수 — 테스트가 부른다."""
    sections = theory_sections(ch)
    sec_ids = [str(s.get("id") or "") for s in sections if s.get("id")]
    known = set(sec_ids)
    unbound, broken = [], []
    easy_by_sec = {}
    for coll in COLLECTIONS:
        for item in (ch.get(coll) or []):
            if not isinstance(item, dict):
                continue
            iid = str(item.get("id") or "?")
            sec = item.get("section")
            if not sec:
                unbound.append(coll + "[" + iid + "]")
                continue
            if sec not in known:
                broken.append(coll + "[" + iid + "] → " + repr(sec))
                continue
            if coll == "practice" and item.get("difficulty") == EASY:
                easy_by_sec.setdefault(sec, []).append(iid)
    # ★ **미선언이 남아 있으면 구멍을 안 잰다** (2026-09-10, 이 자의 첫 실행에서 걸렸다).
    #   실이 하나도 안 이어진 상태에서는 모든 절이 「basic 문풀 없음」으로 읽혀 **절 수가 그대로
    #   구멍 수로** 나왔다(세 과목 135절 → 구멍 135). 그건 «없다» 가 아니라 «아직 못 잰다» 다.
    #   묶기가 끝난 장에서만 세고, 아닌 장은 `None` 을 돌려 「못 잼」으로 찍는다.
    # ★ **문풀이 한 건도 없는 장도 못 잰다** (2026-09-10, 셋째 교정). 과목 개요(`ch00`)가
    #   그렇다 — 절만 있고 `practice` 가 통째로 비어 있어 **모든 절이 구멍**으로 잡혔다(세 과목
    #   에서 14건). 그건 「딸깍이 빠졌다」가 아니라 「이 장에는 문풀을 안 만든다」이고,
    #   0장에 문풀을 두지 않는 것은 이미 정해진 규약이다(AGENTS 「과목 개요와 챕터 도입부」).
    #   위 미선언 규칙과 같은 판정선이다 — **못 재는 것을 0 이나 N 으로 찍지 않는다.**
    if not (ch.get("practice") or []):
        return sec_ids, unbound, broken, None
    gaps = None if unbound else [sid for sid in sec_ids if not easy_by_sec.get(sid)]
    return sec_ids, unbound, broken, gaps


def main():
    args = sys.argv[1:]
    only = None
    for a in args:
        if a.startswith("--only="):
            only = {s.strip() for s in a.split("=", 1)[1].split(",") if s.strip()}
        elif a not in ("--gaps", "--fail-only"):
            sys.exit("모르는 인자: " + a
                     + "\n쓰는 법 — --only=<과목>,<과목> · --gaps(1회차 구멍만) · --fail-only")
    folders = [f for f in subject_dirs(os.path.join(ROOT, "data"))
               if not only or os.path.basename(f) in only]
    if only and not folders:
        sys.exit("[대상 없음] `--only` 에 맞는 과목 폴더가 없다 — 0건이 아니라 한 과목도 안 봤다")
    if not folders:
        print("[해당 없음] 과목 폴더가 없다 — 0건")
        return 0

    gaps_only = "--gaps" in args
    fail_only = "--fail-only" in args
    tot_sec = tot_unbound = tot_broken = tot_gap = 0
    print("문항-절 실 — 미선언 / 끊어진 실 / 1회차 구멍 (판정은 사람이 한다)\n")
    for folder in folders:
        subject = os.path.basename(folder)
        lines = []
        s_sec = s_un = s_br = s_gap = 0
        for name in chapter_files(folder):
            ch = blob(os.path.join(folder, name))
            if not ch or ch.get("placeholder") is True:
                continue
            sec_ids, unbound, broken, gaps = scan(ch)
            if not sec_ids:
                continue
            s_sec += len(sec_ids)
            s_un += len(unbound)
            s_br += len(broken)
            s_gap += len(gaps or ())
            stem = name.rsplit(".", 1)[0]
            if gaps_only:
                if gaps:
                    lines.append("   %s · 1회차 구멍 %d — %s" % (stem, len(gaps), ", ".join(gaps)))
                continue
            if unbound or broken or gaps:
                lines.append("   %s · 절 %d · 미선언 %d · 끊어진 실 %d · 1회차 구멍 %s"
                             % (stem, len(sec_ids), len(unbound), len(broken),
                                "못 잼(미선언 남음)" if gaps is None else str(len(gaps))))
                for b in broken:
                    lines.append("      [끊어진 실] " + b)
        tot_sec += s_sec
        tot_unbound += s_un
        tot_broken += s_br
        tot_gap += s_gap
        if lines or not fail_only:
            print("== %s — 절 %d · 미선언 %d · 끊어진 실 %d · 1회차 구멍 %d"
                  % (subject, s_sec, s_un, s_br, s_gap))
            for line in lines:
                print(line)
    print("\n합계 — 절 %d · 미선언 %d · 끊어진 실 %d · 1회차 구멍 %d · 훑은 과목 %d개"
          % (tot_sec, tot_unbound, tot_broken, tot_gap, len(folders)))
    print("※ 「1회차 구멍」은 결함이 아니라 후보다 — 계산이 없는 절에는 딸깍 문항이 없는 것이 맞다")
    # 끊어진 실만 그 자리에서 틀린 것이다(절 id 가 실제로 없다). 나머지 둘은 목록이다.
    return 1 if tot_broken else 0


if __name__ == "__main__":
    sys.exit(main())
