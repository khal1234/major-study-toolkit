# -*- coding: utf-8 -*-
"""소문자 밑 숫자 아래첨자를 밑글자의 0.70배(하한 10.5px)로 맞춘다.

    python tools/fix_digit_subscript.py            # 후보만 센다
    python tools/fix_digit_subscript.py --apply    # data/<과목>/chNN.json 에 쓴다

판정은 `buildlib.checks_svg.digit_under_lower` · 크기는 `digit_subscript_target` 하나다 —
빌드 검사(C47-b)와 같은 함수를 부른다.

☐ 못 하는 것: 숫자가 tspan 안에 **혼자** 있지 않은 자리(`<tspan>x1</tspan>`)는 안 고친다(빌드도
  그 자리를 안 본다). 윗첨자(dy<0)는 대상이 아니다. 생성기(`tools/gen_*.py`)는 안 고친다 —
  다시 돌리면 빌드가 그 삽화를 신고한다.
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

from buildlib.checks_svg import (FIGURE_RENDER_WIDTH, _attr, _inherited_font_size,  # noqa: E402
                                 _scaled_font_size, _view_width, digit_subscript_target,
                                 digit_under_lower)
from buildlib.jsontext import write_chapter                                        # noqa: E402

TEXT_RE = re.compile(r"(<text\b[^>]*>)(.*?)(</text>)", re.S)
FS_ATTR_RE = re.compile(r"font-size\s*=\s*(['\"])[^'\"]*\1")
# 목표와 이만큼 넘게 다르면 고친다 — 빌드 검사의 여유(`DIGIT_UNDER_LOWER_TOL`)보다 좁아
# 고친 뒤 검사가 다시 걸지 않는다.
REWRITE_TOL = 0.02


def _set_font_size(tok, want, parent_fs):
    raw = _attr(tok, "font-size")
    if raw and raw.strip().endswith("%"):
        val = "%g%%" % (math.ceil(want / parent_fs * 1000.0 - 1e-6) / 10.0)
    else:
        val = "%g" % (math.ceil(want * 10.0 - 1e-6) / 10.0)
    if FS_ATTR_RE.search(tok):
        return FS_ATTR_RE.sub("font-size='" + val + "'", tok, count=1)
    return tok[:-1] + " font-size='" + val + "'>"


def _rewrite_inner(inner, base_fs, scale):
    toks = [m.group(0) for m in re.finditer(r"<[^>]+>|[^<]+", inner)]
    stack = []                                    # (여는 태그 자리, 그 태그 바깥 크기)
    cur_fs, shift, prev, prev_fs, n = base_fs, 0.0, "", base_fs, 0
    for i, tok in enumerate(toks):
        if not tok.startswith("<"):
            plain = tok.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            if not plain.strip():
                continue
            run = {"s": plain, "fs": cur_fs, "depth": len(stack), "shift": shift,
                   "prev": prev, "prev_fs": prev_fs}
            if digit_under_lower(run):
                want = digit_subscript_target(prev_fs, scale)
                oi, parent_fs = stack[-1]
                alone = oi == i - 1 and i + 1 < len(toks) and toks[i + 1].startswith("</")
                if alone and abs(cur_fs - want) > want * REWRITE_TOL:
                    toks[oi] = _set_font_size(toks[oi], want, parent_fs)
                    cur_fs = _scaled_font_size(_attr(toks[oi], "font-size"), parent_fs)
                    n += 1
            prev, prev_fs = plain.rstrip()[-1], cur_fs
        elif tok.startswith("</"):
            if stack:
                cur_fs = stack.pop()[1]
        elif not tok.endswith("/>"):
            stack.append((i, cur_fs))
            cur_fs = _scaled_font_size(_attr(tok, "font-size"), cur_fs)
            try:
                shift += float(_attr(tok, "dy", "0") or 0.0)
            except ValueError:
                pass
    return "".join(toks), n


def rewrite_svg(svg):
    """SVG 한 장을 고쳐 (새 SVG, 고친 곳 수) 를 돌려준다. 순수 함수 — 테스트가 직접 부른다."""
    vw = _view_width(svg)
    if not vw:
        return svg, 0
    scale = FIGURE_RENDER_WIDTH / vw
    total = 0
    out, last = [], 0
    for m in TEXT_RE.finditer(svg):
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
    return "".join(out), total


def _walk(node):
    """JSON 트리 안의 모든 SVG 문자열을 고친다. (새 노드, 고친 곳 수)."""
    if isinstance(node, dict):
        n = 0
        for k, v in node.items():
            node[k], c = _walk(v)
            n += c
        return node, n
    if isinstance(node, list):
        n = 0
        for i, v in enumerate(node):
            node[i], c = _walk(v)
            n += c
        return node, n
    if isinstance(node, str) and "<svg" in node:
        return rewrite_svg(node)
    return node, 0


def main():
    apply = "--apply" in sys.argv[1:]
    import audit_content                                                    # noqa: E402
    folders = audit_content.subject_dirs()
    total, touched = 0, 0
    for folder in folders:
        for name in sorted(os.listdir(folder)):
            if not re.fullmatch(r"ch\d{2}\.json", name):
                continue
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8") as fh:
                ch = json.load(fh)
            before = copy.deepcopy(ch)
            ch, n = _walk(ch)
            if not n:
                continue
            total += n
            touched += 1
            state = ""
            if apply:
                state, why = write_chapter(path, before, ch)
                state = " [" + state + (" — " + why if why else "") + "]"
            print("%4d  %s/%s%s" % (n, os.path.basename(folder), name, state))
    print("합계 %d곳 · %d장 · 훑은 과목 %d개%s" % (total, touched, len(folders),
                                          "" if apply else " (후보만 — --apply 로 쓴다)"))
    return 1 if not folders else 0


if __name__ == "__main__":
    sys.exit(main())
