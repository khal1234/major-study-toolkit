# -*- coding: utf-8 -*-
r"""출력 검사 — 뷰어의 **실제 렌더 함수**로 글자를 그려 보고, 화면에 LaTeX 가 날것으로 남는지 잰다.

    python tools/buildlib/checks_render_output.py          # 전 과목 전 장, 걸린 자리만
    python tools/buildlib/checks_render_output.py --count  # 장별 건수만

잰다: 독자에게 보이는 문자열마다 뷰어가 쓰는 렌더러(`renderMath` 또는 `fmtText`)를 템플릿에서
  그대로 뽑아 node 로 돌리고, 태그를 걷은 결과 글자에 `\(`·`\)`·`\frac`·`\rho` 가 남으면 신고한다.
  입력(JSON)이 아니라 출력(렌더된 글자)을 보므로, 렌더러가 구분자를 모르는 필드·줄바꿈이 수식
  스팬을 가르는 자리처럼 **입력 검사의 등록표 밖**에서 새는 것도 잡는다(E19 — 전전 ch01 의
  `solutionTemplate` `\(R = \frac{ρℓ}{A}\)` 는 `renderMath` 가 `\(` 를 안 벗겨 화면에 그대로 나갔다.
  입력 자는 그 필드를 「통째로 LaTeX」로 보고 건너뛰었다).
렌더러 고르기: `is_whole_math_field` 이거나 `latex`·`equations`·`solutionTemplate` 이면 `renderMath`,
  나머지는 `fmtText`. 건너뛰는 것: 비표시 메타(`MATH_BLOB_NON_RENDERED_KEYS`)·`svg`·`changeNote`·
  `id`, 그리고 **템플릿 소스에 이름이 한 번도 안 나오는 키**(`anchorText` 처럼 빌드만 쓰는 키 —
  뷰어가 그 이름을 모르면 화면에 그릴 수 없다).
못 보는 것: 뷰어가 `esc()` 로만 찍는 필드(여기선 `fmtText` 로 그려 보므로 관대하다) ·
  `variables` 의 키 · 렌더는 되는데 틀리게 되는 경우 · node 가 없는 환경(그때는 error 한 줄).
"""
import glob
import json
import os
import re
import subprocess
import sys

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from buildlib.checks_content import (MATH_BLOB_NON_RENDERED_KEYS, is_whole_math_field,  # noqa: E402
                                     iter_visible_texts)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATE = os.path.join(ROOT, "site", "template", "viewer.template.html")

# 화면에 남으면 안 되는 글자 — 설계도 6절 1번이 고른 넷.
LEAK_TOKENS = ("\\(", "\\)", "\\frac", "\\rho")
RENDER_MATH_KEYS = ("latex", "equations", "solutionTemplate")
_SKIP_KEYS = MATH_BLOB_NON_RENDERED_KEYS | {"svg", "changeNote", "id"}
_FUNCS = ("esc", "scriptTailGap", "renderMath", "fmtOne", "fmtTable", "fmtBlock", "fmtText")
_VARS = ("SCRIPT_TAIL_BASE", "SCRIPT_TAIL_MATH", "SCRIPT_TAIL_SYM")

_JS_DRIVER = r"""
var location = {hostname: 'probe', protocol: 'http:'};
var LOCAL_PORTS = {};
"""
# 뷰어 코드는 명령줄 길이 상한(Windows 32K)을 넘으므로 stdin 첫 줄로 받아 eval 한다 — 파일을 안 쓴다.
_JS_LOADER = r"""
var rl = require('readline').createInterface({input: process.stdin}), ready = false;
rl.on('line', function(line){
  if (!ready) { (0, eval)(JSON.parse(line)); ready = true; return; }
  var items = JSON.parse(line), out = [];
  for (var i = 0; i < items.length; i++) {
    var html = items[i][0] === 'math' ? renderMath(items[i][1]) : fmtText(items[i][1]);
    out.push(String(html).replace(/<[^>]*>/g, '').replace(/&amp;/g, '&'));
  }
  process.stdout.write(JSON.stringify(out) + '\n');
});
"""

_proc = None
_template_names = None


def viewer_render_js(src):
    """템플릿에서 렌더 함수와 그 상수만 뽑는다. 못 찾은 이름은 ValueError(조용히 비지 않게)."""
    parts = []
    for name in _VARS:
        m = re.search(r"^var " + name + r"\s*=[^\n]*$", src, re.M)
        if not m:
            raise ValueError("뷰어 템플릿에 상수 " + name + " 가 없다")
        parts.append(m.group(0))
    for name in _FUNCS:
        m = re.search(r"^function " + name + r"\([^\n]*\)\{.*?\n\}", src, re.S | re.M)
        if not m:
            raise ValueError("뷰어 템플릿에 함수 " + name + " 가 없다")
        parts.append(m.group(0))
    return _JS_DRIVER + "\n".join(parts) + "\n"


def _template_src():
    with open(TEMPLATE, encoding="utf-8") as fh:
        return fh.read()


def _renderer():
    global _proc
    if _proc is None or _proc.poll() is not None:
        js = viewer_render_js(_template_src())
        _proc = subprocess.Popen(["node", "-e", _JS_LOADER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, encoding="utf-8")
        _proc.stdin.write(json.dumps(js) + "\n")
        _proc.stdin.flush()
    return _proc


def render_texts(items):
    """[(kind, text)] → 태그를 걷은 화면 글자 목록. kind 는 'math'(renderMath) 또는 'text'(fmtText)."""
    proc = _renderer()
    proc.stdin.write(json.dumps(items, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("뷰어 렌더러(node)가 응답하지 않았다: " + (proc.stderr.read() or "")[:300])
    return json.loads(line)


def _segments(where):
    return [re.sub(r"\[[^\]]*\]", "", s) for s in where.split("/")]


def template_knows(key):
    """템플릿 소스에 그 키 이름이 낱말로 나오나 — 안 나오면 뷰어는 그 필드를 못 그린다."""
    global _template_names
    if _template_names is None:
        _template_names = set(re.findall(r"[A-Za-z_]\w*", _template_src()))
    return key in _template_names


def renderer_for(where, knows=None):
    """그 트레일을 뷰어가 어느 렌더러로 그리나 — None 은 화면에 안 나가는 필드."""
    segments = _segments(where)
    if any(s in _SKIP_KEYS for s in segments):
        return None
    key = segments[-1]
    if not (knows or template_knows)(key):
        return None
    if key in RENDER_MATH_KEYS or is_whole_math_field(key, where.rsplit("/", 1)[0]):
        return "math"
    return "text"


def render_leak_issues(ch, knows=None):
    """렌더된 화면 글자에 LaTeX 가 날것으로 남은 자리. 판정선은 모듈 독스트링이 정본."""
    todo = []
    for where, blob in iter_visible_texts(ch):
        if "\\" not in blob:
            continue
        kind = renderer_for(where, knows)
        if kind:
            todo.append((where, kind, blob))
    if not todo:
        return []
    try:
        shown = render_texts([[kind, blob] for _w, kind, blob in todo])
    except (OSError, RuntimeError, ValueError) as exc:
        return ["[render_leak] 출력 검사를 못 돌렸다 — " + str(exc)[:200]]
    out = []
    for (where, kind, blob), text in zip(todo, shown):
        leaked = [tok for tok in LEAK_TOKENS if tok in text]
        if leaked:
            out.append(where + ": 화면에 LaTeX 가 날것으로 남는다 " + repr(leaked)
                       + " (렌더러 " + ("renderMath" if kind == "math" else "fmtText") + ")"
                       + " — 산문의 `\\(…\\)` 는 한 줄 안에서 닫을 것: " + repr(blob[:60]))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    count_only = "--count" in sys.argv
    total = seen = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "*", "ch*.json"))):
        with open(path, encoding="utf-8") as fh:
            ch = json.load(fh)
        seen += 1
        hits = render_leak_issues(ch)
        total += len(hits)
        if hits:
            print(os.path.relpath(path, ROOT) + " — " + str(len(hits)))
            if not count_only:
                for h in hits:
                    print("  " + h)
    print("합계 " + str(total) + "건 · 훑은 장 " + str(seen))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
