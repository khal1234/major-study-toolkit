# -*- coding: utf-8 -*-
r"""수식 안의 슬래시 분수를 `\frac{…}{…}` 로 바꾼다 — **확실한 것만**.

    python tools/fix_math_slash_fraction.py                      # 전 챕터 미리보기
    python tools/fix_math_slash_fraction.py --chapter=ch05.json
    python tools/fix_math_slash_fraction.py --chapter=ch05.json --apply

왜 도구인가 (신설 2026-08-12) — 공학수학 세션 보고:
*"수식 안 슬래시 분수에는 fix 도구가 없습니다. `math_slash_fraction_issues` 는 error 인데
고치는 쪽이 없어 과목마다 손으로 고치게 됩니다(`fix_cdot` 이 닫은 것과 같은 부류 —
'자는 신고하는데 처방이 없다')."*

★ **자와 처방은 한 함수를 쓴다.** 찾는 일은 `checks_content.slash_fraction_spans` 하나가 하고
  (단위 면제·지수 안 슬래시 판정이 전부 거기 있다), 이 파일은 **어디까지 기계가 고쳐도 되는가**
  만 판정한다. 처방이 판정을 다시 구현하면 이 리포가 여러 번 겪은 그 사고가 난다 —
  *검사는 신고하는데 도구는 안 고치는* 상태(`declared_roles`·`tone_segments` 선례).

★★ **기계가 고치면 안 되는 것이 실제로 있다.** 슬래시 앞뒤가 늘 낱개 기호인 것은 아니다:
    `\dot{m}/A`  → 찾는 자에게는 분자가 `dot{m}` 으로 보인다(백슬래시는 원자의 첫 글자가
                  될 수 없다). 그대로 감싸면 `\` 가 밖에 남아 **수식이 깨진다.**
    `\frac{a}{b}/2` → 같은 이유로 분자가 `frac{a}{b}` 로 잡힌다.
  그래서 **앞 글자가 `\`·`{` 이거나 분자·분모가 낱개 원자(첨자 포함)가 아니면 손대지 않고
  `[사람]` 으로 낸다.** 애매한 것을 기계가 고치는 쪽이 훨씬 비싸다 — 깨진 수식은 화면에서
  발견되고, 그때는 이미 커밋된 뒤다(`fix_velocity_symbol` 의 SVG `V` 사고와 같은 자리).

★ `variables` 의 **키**도 화면에 그려지는 수식이지만(2026-08-12 에 검사가 그 자리를 보게 됐다)
  키를 바꾸는 것은 값 치환이 아니라 **구조 변경**이라 여기서 하지 않는다 — `[사람]` 으로 낸다.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 오류는 stderr 로 나간다 — 그쪽도 UTF-8 로 돌려놓지 않으면 **한글 오류만 깨진다**
# (2026-08-12, 동역학 세션 보고. 잠금 `test_checks.py::test_tool_errors_are_utf8`).
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import audit_content                                              # noqa: E402
from buildlib.checks_content import (MATH_ONLY_KEYS,              # noqa: E402
                                     _MATH_SPAN_RE, slash_fraction_spans)
from buildlib.jsontext import write_chapter                       # noqa: E402

# 낱개 원자 — 글자·숫자에 첨자가 붙은 것까지. 백슬래시·중첩 중괄호가 보이면 사람이 본다.
_ATOM = re.compile(r"^[A-Za-z0-9∂∆]+(?:[_^]\{[^{}\\]*\}|[_^][A-Za-z0-9])*$")


def rewrite(span):
    """(바뀐 수식, 바꾼 수, [사람이 볼 것]). 순수 함수 — 테스트가 직접 부른다."""
    hits = slash_fraction_spans(span)
    out, done, manual = span, 0, []
    for at, slash, end, _num, _den in reversed(hits):        # 뒤에서부터 — 앞 좌표가 안 흔들린다
        num_text = span[at:slash].rstrip()
        den_text = span[slash + 1:end].lstrip()
        before = span[at - 1] if at else ""
        if before in ("\\", "{") or not _ATOM.match(num_text) or not _ATOM.match(den_text):
            manual.append(num_text + "/" + den_text)
            continue
        out = out[:at] + "\\frac{" + num_text + "}{" + den_text + "}" + out[end:]
        done += 1
    return out, done, list(reversed(manual))


def convert(value, is_math_field):
    """필드 하나. 값 전체가 LaTeX 인 필드면 통째로, 산문이면 `\\( … \\)` 안만."""
    if is_math_field:
        return rewrite(value)
    done, manual, pieces, cur = 0, [], [], 0
    for m in _MATH_SPAN_RE.finditer(value):
        new, n, left = rewrite(m.group(1))
        pieces.append(value[cur:m.start(1)])
        pieces.append(new)
        cur = m.end(1)
        done += n
        manual.extend(left)
    pieces.append(value[cur:])
    return "".join(pieces), done, manual


def walk(node, trail, log, manual, key=None):
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "variables" and isinstance(v, dict):
                # 키는 **구조**라 여기서 안 바꾼다(위 독스트링). 걸리면 자리만 알린다.
                for vk in v:
                    if slash_fraction_spans(str(vk)):
                        manual.append((trail + "/variables{" + str(vk) + "}", str(vk)))
            out[k] = walk(v, trail + "/" + str(k), log, manual, k)
        return out
    if isinstance(node, list):
        return [walk(v, trail + "[" + str(i) + "]", log, manual, key)
                for i, v in enumerate(node)]
    if not isinstance(node, str):
        return node
    if key == "svg":
        return node          # 삽화는 `svg_fraction.py` 의 몫 — 여기서 LaTeX 를 넣으면 안 된다
    new, n, left = convert(node, key in MATH_ONLY_KEYS)
    if n:
        log.append((trail, node[:60], n))
    manual.extend((trail, w) for w in left)
    return new


def main():
    ap = argparse.ArgumentParser(description="수식 안 슬래시 분수를 \\frac 으로")
    ap.add_argument("--chapter", help="chNN.json 하나만")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    names = ([args.chapter] if args.chapter
             else [n + ".json" for n in audit_content.CHAPTERS])
    total, held = 0, 0
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        log, manual = [], []
        fixed = walk(data, "", log, manual)
        total += sum(n for _t, _s, n in log)
        held += len(manual)
        print("\n=== %s ===" % name)
        for trail, before, n in log:
            print("  %-52s %d곳  %s" % (trail[:52], n, before))
        for trail, what in manual:
            print("  [사람] %-46s %s" % (trail[:46], what))
        if not log:
            print("  바꿀 것 없음")
        if not args.apply:
            continue
        status, why = write_chapter(path, data, fixed)
        print("  [%s] %s" % (status, why or os.path.relpath(path, audit_content.ROOT)))
    print("\n바꾼 곳 %d · 사람이 볼 것 %d%s"
          % (total, held, "" if args.apply else "  (미리보기 — --apply 로 반영)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
