# -*- coding: utf-8 -*-
"""삽화 라벨의 날것 첨자(`σx1`·`τx1y1`·`σmax`)를 `<tspan dy>` 첨자로 내린다.

    python tools/fix_flat_subscript.py            # 후보만 센다
    python tools/fix_flat_subscript.py --apply    # data/<과목>/chNN.json 에 쓴다

판정은 `buildlib.checks_svg.FLAT_SUBSCRIPT_RE` 하나다 — 빌드 검사(C47-c)와 같은 자를 쓴다.
조판: 글자 첨자는 `dy='2.5' font-size='83%'`(생성기 `gen_chain_fbd` 와 같은 꼴), 숫자 첨자는
`digit_subscript_target`(C47-b, 밑글자의 0.70배 · 하한 10.5px). 첨자 뒤에 글자가 이어지면
`<tspan dy='-2.5'>` 로 기준선으로 되돌린다.

☐ 못 하는 것: 등폭(수식 줄, `svg_math_line` 산출물) 글자는 폭이 바뀌면 조판 자(C20)가 어긋나므로
  안 고치고 `[수식 줄]` 로 낸다 — 생성기 표현식에 tspan 을 넣어 다시 찍는 것이 사람 몫이다.
  `<tspan>` 안(깊이 1 이상)의 날것 첨자도 안 고친다(빌드는 신고한다). 생성기(`tools/gen_*.py`)는
  안 고친다 — 다시 돌리면 빌드가 그 삽화를 신고한다.
"""
import copy
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_svg import (FIGURE_RENDER_WIDTH, FLAT_SUBSCRIPT_RE, MATH_FONT,  # noqa: E402
                                 _attr, _effective, _inherited_font_size, _view_width,
                                 digit_subscript_target)
from buildlib.jsontext import write_chapter                                        # noqa: E402

TEXT_RE = re.compile(r"(<text\b[^>]*>)(.*?)(</text>)", re.S)
SUB_DY = "2.5"          # 글자 첨자 내림 — 생성기(gen_chain_fbd·gen_meter_placement)와 같은 값
SUB_PCT = 0.83          # 글자 첨자 비율 — 규격 하한 12.9px 을 15.5px 라벨에서 넘기는 값(checks_svg 주석)
_UNI_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def _typeset(m, base_fs, scale):
    """한 매치(`τx1y1`)를 밑글자 + tspan 첨자열로 바꾼다."""
    out, first, prev_fs = [m.group(1)], True, base_fs
    for part in re.findall(r"[a-z]+|[0-9₀-₉]+", m.group(2)):
        dy = " dy='" + SUB_DY + "'" if first else ""
        if part[0].isalpha():
            out.append("<tspan" + dy + " font-size='" + "%g%%" % (SUB_PCT * 100) + "'>" + part + "</tspan>")
            prev_fs = SUB_PCT * base_fs
        else:
            want = digit_subscript_target(prev_fs, scale)
            fs = math.ceil(want * 10.0 - 1e-6) / 10.0
            out.append("<tspan" + dy + " font-size='" + "%g" % fs + "'>"
                       + part.translate(_UNI_DIGITS) + "</tspan>")
            prev_fs = fs
        first = False
    return "".join(out)


def _rewrite_plain(tok, base_fs, scale):
    out, last, n = [], 0, 0
    for m in FLAT_SUBSCRIPT_RE.finditer(tok):
        pre = tok[last:m.start()]
        if pre:
            out.append("<tspan dy='-" + SUB_DY + "'>" + pre + "</tspan>" if n else pre)
        out.append(_typeset(m, base_fs, scale))
        n += 1
        last = m.end()
    rest = tok[last:]
    if rest:
        out.append("<tspan dy='-" + SUB_DY + "'>" + rest + "</tspan>" if n else rest)
    return "".join(out), n


def _rewrite_inner(inner, base_fs, scale):
    toks = [m.group(0) for m in re.finditer(r"<[^>]+>|[^<]+", inner)]
    depth, n = 0, 0
    for i, tok in enumerate(toks):
        if not tok.startswith("<"):
            if depth == 0:
                toks[i], c = _rewrite_plain(tok, base_fs, scale)
                n += c
        elif tok.startswith("</"):
            depth = max(0, depth - 1)
        elif not tok.endswith("/>"):
            depth += 1
    return "".join(toks), n


def _count_plain(inner):
    """깊이 0 의 날것 첨자 수 — 이미 `<tspan>` 으로 내린 것은 안 센다.
    (2026-09-25: 태그를 걷은 문자열로 세니 고친 `σ<tspan>x</tspan>` 도 「사람 몫」으로 찍혔다.)"""
    depth, n = 0, 0
    for tok in re.findall(r"<[^>]+>|[^<]+", inner):
        if not tok.startswith("<"):
            if depth == 0:
                n += len(FLAT_SUBSCRIPT_RE.findall(tok))
        elif tok.startswith("</"):
            depth = max(0, depth - 1)
        elif not tok.endswith("/>"):
            depth += 1
    return n


def rewrite_svg(svg):
    """SVG 한 장을 고쳐 (새 SVG, 고친 곳 수, 수식 줄이라 넘긴 곳 수) 를 돌려준다. 순수 함수."""
    vw = _view_width(svg)
    if not vw:
        return svg, 0, 0
    scale = FIGURE_RENDER_WIDTH / vw
    total, skipped = 0, 0
    out, last = [], 0
    for m in TEXT_RE.finditer(svg):
        if _effective(svg, m.start(), m.group(1), "font-family", "") == MATH_FONT:
            skipped += _count_plain(m.group(2))
            continue
        own = _attr(m.group(1), "font-size")
        if own and re.fullmatch(r"\d+(?:\.\d+)?", own):
            fs = float(own)
        else:
            fs = _inherited_font_size(svg, m.start()) or 12.0
        inner, n = _rewrite_inner(m.group(2), fs, scale)
        if n:
            out.append(svg[last:m.start()] + m.group(1) + inner + m.group(3))
            last = m.end()
            total += n
    out.append(svg[last:])
    return "".join(out), total, skipped


def _walk(node):
    """JSON 트리 안의 모든 SVG 문자열을 고친다. (새 노드, 고친 곳 수, 넘긴 곳 수)."""
    if isinstance(node, dict):
        n = s = 0
        for k, v in node.items():
            node[k], c, d = _walk(v)
            n += c
            s += d
        return node, n, s
    if isinstance(node, list):
        n = s = 0
        for i, v in enumerate(node):
            node[i], c, d = _walk(v)
            n += c
            s += d
        return node, n, s
    if isinstance(node, str) and "<svg" in node:
        return rewrite_svg(node)
    return node, 0, 0


def main():
    apply = "--apply" in sys.argv[1:]
    import audit_content                                                    # noqa: E402
    folders = audit_content.subject_dirs()
    total, touched, skipped = 0, 0, 0
    for folder in folders:
        for name in sorted(os.listdir(folder)):
            if not re.fullmatch(r"ch\d{2}\.json", name):
                continue
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8") as fh:
                ch = json.load(fh)
            before = copy.deepcopy(ch)
            ch, n, s = _walk(ch)
            skipped += s
            if not n and not s:
                continue
            total += n
            touched += 1 if n else 0
            state = ""
            if apply and n:
                state, why = write_chapter(path, before, ch)
                state = " [" + state + (" — " + why if why else "") + "]"
            print("%4d  %s/%s%s%s" % (n, os.path.basename(folder), name, state,
                                       ("  [수식 줄 %d곳 — 사람 몫]" % s) if s else ""))
    print("합계 %d곳 · %d장 · 수식 줄 넘김 %d곳 · 훑은 과목 %d개%s"
          % (total, touched, skipped, len(folders), "" if apply else " (후보만 — --apply 로 쓴다)"))
    return 1 if not folders else 0


if __name__ == "__main__":
    sys.exit(main())
