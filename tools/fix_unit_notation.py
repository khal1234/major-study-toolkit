#!/usr/bin/env python
r"""단위를 `\mathrm{}` 로 표시해 **이름 판정에서 벗어나게** 한다.

왜 이 도구가 있나 (열린 날 2026-08-02 — 평문 분수 **8회째** 지적의 근본 처방):

    분수 검사(`text_fraction_hit`·`math_slash_fraction_issues`)는 슬래시 양옆이 단위면
    나눗셈이 아니라고 보고 넘긴다. 그 판정을 **이름**으로 한다 — `UNIT_BASES` 목록에
    있으면 단위. 그런데 한 글자 단위는 물리량 기호와 **같은 글자**다:

        K 켈빈 / 상계 상수      C 쿨롱 / 적분상수      N 뉴턴 / 법선력
        W 와트 / 일             L 리터 / 길이          m 미터 / 질량

    그래서 진짜 분수가 조용히 통과한다. 실측 이력 — 2026-07-31 에 `g`(그램)가
    `mg/A`(무게÷면적) 4곳을 삼켰고, 2026-08-02 에 `K` 가 `b/K` 7곳을 삼켰다.
    **같은 자리에서 두 번 났다.** 그때마다 그 글자를 목록에서 뺐지만, 그건 인스턴스
    제거이지 구조 수정이 아니다 — 다음 글자가 또 온다.

    근본 해법은 SI 조판 관례다: **단위는 로만체, 변수는 이탤릭.** 데이터에서는
    `\mathrm{}` 로 표시한다. 그러면 검사가 이름을 몰라도 판정할 수 있다 —
    `\(\mathrm{kJ}/\mathrm{kg}\)` 는 단위, `\(b/K\)` 는 분수. 끝.

★ 왜 과목별 선언(opt-in)인가:

    이름 판정을 끄는 순간, 아직 `\mathrm` 을 안 쓴 과목은 **모든 단위가 분수로 신고된다.**
    전역 승격 목록이 남의 과목 빌드를 멈춘 사고가 2026-08-02 하루에 두 번 났다.
    그래서 판정 전환은 `data/<과목>/index.json` 의 `unitNotation: "mathrm"` 선언으로만
    켜진다. 선언하지 않은 과목은 **동작이 한 글자도 안 바뀐다.**

쓰기 규율: 기본은 **보고만** 한다. `--apply` 를 줘야 파일을 쓴다.

    python tools/fix_unit_notation.py                # 이 과목의 전환 대상 조사
    python tools/fix_unit_notation.py --apply        # `\mathrm{}` 로 감싸기

★ 도구가 **건드리지 않는 것** (사람이 판단한다):
    ⑴ 한 글자 토큰 — `K` 가 켈빈인지 상계 상수인지는 문맥이 정한다. 목록으로 찍어 준다.
    ⑵ 수식 **밖**의 산문 단위 — `\(…\)` 로 감쌀지 말지는 문장마다 다르다.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import audit_content                                                        # noqa: E402
from buildlib.checks_content import (INLINE_MATH_RE, UNIT_BASES,            # noqa: E402
                                     _is_unit_token, iter_visible_texts)

# 여러 글자 단위만 자동으로 감싼다 — 한 글자는 물리량 기호와 구별할 수 없다(위 독스트링 ⑴).
_TOKEN = re.compile(r"(?<![A-Za-z\\{])([A-Za-zμµ]{2,})(?![A-Za-z}])")


def _already_wrapped(span, start):
    r"""이 위치가 이미 `\mathrm{...}` 안인가."""
    head = span[:start]
    opened = head.rfind("\\mathrm{")
    if opened < 0:
        return False
    return "}" not in head[opened:]


def wrap_units(span):
    r"""인라인 수식 한 조각에서 여러 글자 단위를 `\mathrm{}` 로 감싼다. 순수 함수(테스트 대상)."""
    out, last = [], 0
    for m in _TOKEN.finditer(span):
        token = m.group(1)
        if not _is_unit_token(token) or len(token) < 2:
            continue
        if _already_wrapped(span, m.start()):
            continue
        out.append(span[last:m.start()])
        out.append("\\mathrm{" + token + "}")
        last = m.end()
    out.append(span[last:])
    return "".join(out)


def survey(chapter):
    """전환 대상과 **사람이 판단할 것**을 갈라 돌려준다. 순수 함수(테스트 대상)."""
    auto, manual = [], []
    for where, blob in iter_visible_texts(chapter):
        for span in INLINE_MATH_RE.findall(str(blob or "")):
            for m in re.finditer(r"(?<![A-Za-z\\{])([A-Za-zμµ]+)(?![A-Za-z}])", span):
                token = m.group(1)
                if not _is_unit_token(token) or _already_wrapped(span, m.start()):
                    continue
                (auto if len(token) > 1 else manual).append((where, token, span[:70]))
    return auto, manual


def main():
    ap = argparse.ArgumentParser(description="인라인 수식의 단위를 \\mathrm{} 로 표시")
    ap.add_argument("--chapter", help="chNN.json (생략하면 이 과목 전 챕터)")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 쓴다")
    args = ap.parse_args()

    names = [args.chapter.replace(".json", "")] if args.chapter else audit_content.CHAPTERS
    total_auto = total_manual = written = 0
    for name in names:
        path = os.path.join(audit_content.DATA, name + ".json")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        chapter = json.loads(raw)
        auto, manual = survey(chapter)
        total_auto += len(auto)
        total_manual += len(manual)
        print("=== " + name + " ===")
        for where, token, sample in auto:
            print("  [자동] " + token.ljust(6) + " " + where + "  " + repr(sample))
        for where, token, sample in manual:
            print("  [사람] " + token.ljust(6) + " " + where + "  " + repr(sample)
                  + "   ← 한 글자다. 단위인지 물리량 기호인지 문맥으로 판정할 것")
        if not auto and not manual:
            print("  전환할 단위 없음")
        if args.apply and auto:
            # 인라인 수식 조각만 바꾼다 — 수식 **밖**의 글자는 건드리지 않는다.
            fixed = INLINE_MATH_RE.sub(
                lambda m: m.group(0).replace(m.group(1), wrap_units(m.group(1)), 1), raw)
            if fixed != raw:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(fixed)
                written += 1
                print("  [기록] " + path)

    print("\n합계 — 자동 " + str(total_auto) + " · 사람 판정 " + str(total_manual)
          + (" · 기록 " + str(written) + "파일" if args.apply else "  (--apply 로 기록)"))
    if not total_auto and not total_manual:
        print("★ 이 과목은 인라인 수식에 단위가 없다 — "
              "`index.json` 에 `\"unitNotation\": \"mathrm\"` 를 선언해도 데이터 변경이 0건이다.")
    print("등록부 크기(참고): UNIT_BASES " + str(len(UNIT_BASES)) + "종")
    return 0


if __name__ == "__main__":
    sys.exit(main())
