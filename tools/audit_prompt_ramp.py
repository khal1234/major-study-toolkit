# -*- coding: utf-8 -*-
r"""문항 **지문의 부담**을 잰다 — 언어·문장 수·글자 수가 번호를 따라 자라는가.

    python tools/audit_prompt_ramp.py --lengths                 # 분포 (눈금을 고르기 전에 재는 자리)
    python tools/audit_prompt_ramp.py --lengths --only=<과목>
    python tools/audit_prompt_ramp.py                           # ramp 미선언·역행 후보
    python tools/audit_prompt_ramp.py --only=<과목> --fail-only

열린 날 2026-09-10. 사용자 원문 —
*[발화 생략]* ·
*[발화 생략]*.

**무엇이 새어나갔나 — 「지문 눈금」이 없었다.**
난이도 눈금(AGENTS 「문제 설계」 ⑵)과 유형 축 A/B/C 는 있는데 **지문의 길이·언어를 재는 자가
하나도 없었다.** 눈금이 없으면 쓰는 사람은 손에 든 원서 지문을 닮는 쪽으로 수렴한다 —
열역학(첫 과목)의 지문이 본래 길었고(상태·과정·장치를 서술해야 값이 정해진다) 그 형태가
**과목을 안 가리고 복제**됐다. 사용자가 든 사례는 공수2 `ch07-p01` 로, 네 줄짜리 영문 지문 뒤의
실제 계산은 **성분 덧셈 한 줄**이었다.

★ **이 자는 「길다」를 벌하지 않는다.** 칸 4(원서 지문 길이)는 목표이지 결함이 아니다.
  재는 것은 **한 챕터 안에서 번호를 따라 자라는가** 하나다.

★ **눈금의 근거는 문장 수다 — 글자 수가 아니다.** 한글과 영문은 같은 내용에서 글자 수가
  두 배 넘게 갈리므로(아래 `--lengths` 실측) 글자 수로 눈금을 박으면 언어를 바꾸는 순간
  눈금이 거짓말을 한다. 사용자의 말도 «한 문장 / 두세 문장» 이라는 문장 단위였다.
  글자 수는 **한 문장이 괴물처럼 길어지는 것**을 막는 둘째 자로만 쓴다(상한의 근거는
  `checks_content.RAMP_SPEC` 주석이 정본 — 실측 분포에서 고른다).

★ **문장을 세는 자를 새로 만들지 않는다** — `checks_content.check_answer_sentences()` 를
  그대로 부른다. 세는 법이 두 벌이면 «자가 재는 것»과 «검사가 막는 것»이 갈린다
  (그 함수 자신이 같은 이유로 공유되고 있다).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from audit_content import ROOT, subject_dirs                              # noqa: E402
from buildlib.checks_content import (                                     # noqa: E402
    RAMP_LEVELS, check_answer_sentences, prompt_ramp_issues, prompt_shape,
)

COLLECTIONS = ("practice", "problems")


def chapter_files(folder):
    return sorted(n for n in os.listdir(folder)
                  if n.startswith("ch") and n.endswith(".json") and len(n) == 9)


def blob(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def declared_language(folder):
    idx = blob(os.path.join(folder, "index.json")) or {}
    return idx.get("promptLanguage")


def rows_for(folder):
    """(챕터, 컬렉션, id, ramp, 언어, 문장수, 글자수) — 순수 수집. 판정하지 않는다."""
    out = []
    for name in chapter_files(folder):
        ch = blob(os.path.join(folder, name))
        if not ch or ch.get("placeholder") is True:
            continue
        for coll in COLLECTIONS:
            for item in (ch.get(coll) or []):
                lang, sentences, chars = prompt_shape(item.get("prompt"))
                out.append((name.rsplit(".", 1)[0], coll, str(item.get("id") or "?"),
                            item.get("ramp"), lang, sentences, chars))
    return out


def _percentiles(values):
    if not values:
        return (0, 0, 0, 0)
    s = sorted(values)

    def at(q):
        return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]
    return (s[0], at(0.5), at(0.9), s[-1])


def show_lengths(folders):
    """분포만 낸다 — **눈금을 고르기 전에 부르는 자리**다. 판정·차단 없음(exit 0)."""
    print("지문 부담 분포 — 언어별 문장 수·글자 수 (최소 / 중앙 / 90% / 최대)\n")
    pool = {}
    for folder in folders:
        subject = os.path.basename(folder)
        rows = rows_for(folder)
        if not rows:
            continue
        print("== " + subject + "  (지문 언어 선언: " + repr(declared_language(folder)) + ")")
        for coll in COLLECTIONS:
            for lang in ("ko", "en"):
                sel = [r for r in rows if r[1] == coll and r[4] == lang]
                if not sel:
                    continue
                sen = _percentiles([r[5] for r in sel])
                cha = _percentiles([r[6] for r in sel])
                print("   %-9s %s %3d건 · 문장 %d/%d/%d/%d · 글자 %d/%d/%d/%d"
                      % (coll, lang, len(sel), *sen, *cha))
                pool.setdefault((coll, lang), []).extend(sel)
        print("")
    print("== 합계 (훑은 과목 " + str(len(folders)) + "개)")
    for (coll, lang), sel in sorted(pool.items()):
        sen = _percentiles([r[5] for r in sel])
        cha = _percentiles([r[6] for r in sel])
        one = [r for r in sel if r[5] <= 1]
        print("   %-9s %s %4d건 · 문장 %d/%d/%d/%d · 글자 %d/%d/%d/%d · 한 문장짜리 %d건(%.0f%%)"
              % (coll, lang, len(sel), *sen, *cha, len(one), 100.0 * len(one) / len(sel)))
    # ★ **칸 1·3 의 글자 상한은 여기서 고른다** — 「지금 한 문장으로 쓰인 지문」의 분포다.
    #   전체 분포로 고르면 여러 문장짜리가 섞여 상한이 부풀고, 그러면 자가 아무것도 안 막는다.
    print("\n== 한 문장짜리 지문만 — 글자 수 (최소 / 중앙 / 90% / 최대)  ← 칸 1·3 상한의 근거")
    for lang in ("ko", "en"):
        sel = [r for v in pool.values() for r in v if r[4] == lang and r[5] <= 1]
        if sel:
            print("   %s %4d건 · %d/%d/%d/%d" % (lang, len(sel), *_percentiles([r[6] for r in sel])))
    print("\n※ 이 출력은 재기만 한다. 눈금은 checks_content.RAMP_SPEC 이 정본이다.")
    return 0


def show_candidates(folders, fail_only=False):
    total = 0
    for folder in folders:
        subject = os.path.basename(folder)
        declared = declared_language(folder)
        hits = []
        for name in chapter_files(folder):
            ch = blob(os.path.join(folder, name))
            if not ch or ch.get("placeholder") is True:
                continue
            for line in prompt_ramp_issues(ch, declared):
                hits.append(name.rsplit(".", 1)[0] + " · " + line)
        total += len(hits)
        if hits or not fail_only:
            print("== " + subject + " — " + str(len(hits)) + "건")
            for line in hits:
                print("   " + line)
    print("\n합계 " + str(total) + "건 · 훑은 과목 " + str(len(folders)) + "개"
          + "  (칸 눈금: " + ", ".join(str(k) + "=" + v for k, v in RAMP_LEVELS.items()) + ")")
    return 0


def main():
    args = sys.argv[1:]
    only = None
    for a in args:
        if a.startswith("--only="):
            only = {s.strip() for s in a.split("=", 1)[1].split(",") if s.strip()}
        elif a not in ("--lengths", "--fail-only"):
            sys.exit("모르는 인자: " + a
                     + "\n쓰는 법 — --lengths(분포) · --only=<과목>,<과목> · --fail-only")
    folders = [f for f in subject_dirs(os.path.join(ROOT, "data"))
               if not only or os.path.basename(f) in only]
    if only and not folders:
        sys.exit("[대상 없음] `--only` 에 맞는 과목 폴더가 없다 — 0건이 아니라 한 과목도 안 봤다")
    if not folders:
        print("[해당 없음] 과목 폴더가 없다 — 0건")
        return 0
    if "--lengths" in args:
        return show_lengths(folders)
    return show_candidates(folders, "--fail-only" in args)


if __name__ == "__main__":
    sys.exit(main())
