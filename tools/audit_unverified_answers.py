#!/usr/bin/env python
"""검산 케이스가 없는 수치 답 문항을 센다 — 전 과목 (읽기 전용).

    python tools/audit_unverified_answers.py                 # 과목별 표(과목 · 검산 도구 · 분모 · 미검산)
    python tools/audit_unverified_answers.py --list          # 미검산 id 까지
    python tools/audit_unverified_answers.py --only=<과목>   # 과목 한정(부분 일치)
    python tools/audit_unverified_answers.py --md            # 표를 마크다운으로(인박스 접수용)
    python tools/audit_unverified_answers.py --only=<과목> --show   # 미검산 문항의 지문·풀이틀·답(채우는 회차용)

**왜 열렸나 (2026-09-24, 클라우드 큐 3번 · 설계도 `docs/2026-09-24-전전-ch01-E10-E26-설계도.md` 6절 12).**
검산 도구(`verify_*_answer.py`)는 **opt-in** 이다 — 문항을 새로 넣고 케이스를 안 넣어도 아무 게이트도
안 빨개진다. 2026-09-24 GPT 작업 검증에서 「내용 완료이나 검산 케이스 0」(E02·E07·T01)이 그렇게
나왔다. 절대 규칙 4(수치는 스크립트로 독립 검산)의 **빠진 쪽**을 재는 자가 없었다.

**무엇을 세나.**
  · 분모 = 수치 답 문항 수 — `practice[].blanks[].answer` · `problems[].answer` ·
    `textbookProblems.items[].answer` 중 하나라도 수(식별자·첨자에 붙지 않은 아라비아 숫자)를 담은 항목.
  · 미검산 = 그중 그 과목 `index.json` 의 `answerVerifier` 소스에 **id 가 안 나오는** 것.
    id 의 `-` 는 `-`·`_`·공백 어느 것과도 맞춘다(`ch01-q17` ↔ 라벨 `ch01 q17` ↔ 함수 `ch01_q17`),
    앞뒤가 영숫자면 안 맞는다(`ch01-q1` 이 `ch01 q17` 에 맞지 않게).
  · 검산 도구를 선언하지 않은 과목은 분모 전부가 미검산이다(「선언 없음」으로 표시).

**이 자가 못 보는 것(첫 실행 전에 적는다 — 규칙 11).**
  · 라벨에 id 를 안 쓰는 검산 도구 — 케이스가 있어도 미검산으로 센다(과대). 과목 비율이 100 % 에
    가까운데 검산 도구가 선언돼 있으면 이 자리부터 의심한다.
  · id 가 소스에 **주석으로만** 나와도 검산된 것으로 센다(과소) — 「대상 아님」 주석이 그 예다.
  · 수를 한글로만 쓴 답(「두 배」)은 분모에서 빠진다.
  · 어느 **칸**이 검산됐는지는 모른다 — 문항 단위다.

**판정에 아직 못 쓴다(실행 규율 17).** 몇 건이면 막을지 정하지 않았다 — 첫 표로 분모부터 재고,
문턱은 과목별 채움이 끝난 뒤 정한다. 그래서 exit 는 늘 0 이다(세는 자, 막는 자 아님).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import audit_content as ac  # noqa: E402

TOOLS = os.path.dirname(os.path.abspath(__file__))
# 식별자·첨자·LaTeX 명령에 붙은 숫자(`R_2`·`x^2`·`\frac12` 의 앞자리)는 수치 답이 아니다.
NUMBER = re.compile(r"(?<![A-Za-z_^{\\])[0-9]")
# 수 하나(쉼표 자리수·소수점 포함). 답과 지문의 수를 견줄 때 쓴다 — 첨자 숫자는 NUMBER 와 같은 규칙으로 뺀다.
VALUE = re.compile(r"(?<![A-Za-z_^{\\0-9.,])[0-9][0-9,]*(?:\.[0-9]+)?")


def _texts(value):
    """답 칸이 문자열·목록·사전 어느 꼴이든 문자열 조각으로 편다. 순수 함수."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _texts(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _texts(v)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield str(value)


def answer_texts(item):
    """한 문항의 답 칸들. 순수 함수."""
    out = list(_texts(item.get("answer")))
    for blank in item.get("blanks") or []:
        if isinstance(blank, dict):
            out.extend(_texts(blank.get("answer")))
    return out


def has_numeric_answer(item):
    """★ 참/거짓 문항(`oxCorrect`)은 답이 판정이라 분모에서 뺀다 — 해설에 「10 km」 같은 지문 값이
    섞여 수치 답으로 잘못 셌다(2026-09-24 둘째 실행, 열역학 ox 17건)."""
    if "oxCorrect" in item:
        return False
    answer_numbers = set()
    for t in answer_texts(item):
        answer_numbers.update(VALUE.findall(t))
    if not answer_numbers:
        return False
    # ★ 답의 수가 전부 지문에 이미 있으면 계산이 아니라 **고르기**다(「0 mm 와 6 mm 중 무엇」 → 6 mm).
    #   검산할 계산이 없으므로 분모에서 뺀다(2026-09-24 셋째 실행, 기계공작법 절 예제 실측).
    prompt_numbers = set(VALUE.findall(str(item.get("prompt") or "")))
    return not answer_numbers <= prompt_numbers


def chapter_items(chapter):
    """장 JSON 에서 답이 있는 문항 세 컬렉션. 순수 함수."""
    for key in ("practice", "problems"):
        for it in chapter.get(key) or []:
            if isinstance(it, dict) and it.get("id"):
                yield it
    tb = chapter.get("textbookProblems")
    items = tb.get("items") if isinstance(tb, dict) else tb
    for it in items or []:
        if isinstance(it, dict) and it.get("id"):
            yield it


def id_pattern(item_id):
    """id 가 소스에 나오는 꼴. `<접두>-chNN-<번호>` 꼴 id 는 라벨이 장을 앞으로 빼 적는
    `chNN <접두>-<번호>` 꼴도 받는다(2026-09-24 첫 실행 — `q-ch08-07` ↔ 라벨 `ch08 q-07`
    를 못 봐 한 과목이 통째로 「판정 불가」로 보였다)."""
    def spelled(parts):
        # 구분자는 `-`·`_`·공백·점 — 교재 문항 라벨이 `tb 14.45` 처럼 절 번호를 점으로 쓴다(id `tb-14-45`).
        return r"[-_ .]".join(re.escape(p) for p in parts)
    parts = str(item_id).split("-")
    forms = [spelled(parts)]
    if len(parts) >= 3 and re.fullmatch(r"ch\d{2}", parts[1]):
        forms.append(spelled([parts[1], parts[0]] + parts[2:]))
    return re.compile(r"(?<![0-9A-Za-z])(?:" + "|".join(forms) + r")(?![0-9A-Za-z])")


def is_covered(item_id, verifier_src):
    return bool(verifier_src) and bool(id_pattern(item_id).search(verifier_src))


def audit_subject(subject_dir, tools_dir=TOOLS):
    """과목 하나 → {'subject','verifier','denominator','unverified':[id…]}."""
    verifier, src = None, ""
    index = os.path.join(subject_dir, "index.json")
    if os.path.isfile(index):
        with open(index, encoding="utf-8") as fh:
            verifier = (json.load(fh) or {}).get("answerVerifier")
    if verifier:
        path = os.path.join(tools_dir, verifier)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
    denominator, unverified, shown = 0, [], []
    for name in sorted(os.listdir(subject_dir)):
        if not re.fullmatch(r"ch\d{2}\.json", name):
            continue
        with open(os.path.join(subject_dir, name), encoding="utf-8") as fh:
            chapter = json.load(fh)
        for it in chapter_items(chapter):
            if not has_numeric_answer(it):
                continue
            denominator += 1
            if not is_covered(it["id"], src):
                unverified.append(name[:4] + ":" + str(it["id"]))
                shown.append((name[:4], it))
    return {"subject": os.path.basename(subject_dir), "items": shown,
            "verifier": verifier if (verifier and src) else ("파일 없음: " + verifier if verifier else None),
            "denominator": denominator, "unverified": unverified}


def main(argv):
    only = next((a.split("=", 1)[1] for a in argv if a.startswith("--only=")), "")
    dirs = ac.subject_dirs()
    if ac.reject_unmatched_only(only, dirs):
        return 0
    rows = [audit_subject(d) for d in ac.only_matches(only, dirs)]
    md = "--md" in argv
    if md:
        print("| 과목 | 검산 도구 | 분모(수치 답 문항) | 미검산 |")
        print("|---|---|---|---|")
    total_d = total_u = 0
    for r in rows:
        n = len(r["unverified"])
        total_d += r["denominator"]
        total_u += n
        tool = r["verifier"] or "선언 없음"
        if md:
            print("| %s | `%s` | %d | %d |" % (r["subject"], tool, r["denominator"], n))
        else:
            print("%-24s %-32s 분모 %4d · 미검산 %4d" % (r["subject"], tool, r["denominator"], n))
        if "--list" in argv and n:
            print("    " + " ".join(r["unverified"]))
        if "--show" in argv:
            # 채우는 회차용 — 미검산 문항의 지문·주어진 값·답을 한 화면에(케이스를 쓰려면 셋 다 필요하다).
            for ch, it in r["items"]:
                given = it.get("prompt") or it.get("topic") or ""
                print("\n[%s %s] %s" % (ch, it["id"], given))
                if it.get("solutionTemplate"):
                    print("  풀이틀: " + it["solutionTemplate"].replace("\n", " ⏎ "))
                if it.get("outline"):   # 교재 문항은 입력값이 지문이 아니라 개요에 적혀 있다
                    print("  개요: " + " ⏎ ".join(str(o) for o in it["outline"]))
                print("  답: " + " | ".join(answer_texts(it)))
    print(("| **합계** | %d과목 | %d | %d |" if md else "합계 %d과목 · 분모 %d · 미검산 %d")
          % (len(rows), total_d, total_u))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
