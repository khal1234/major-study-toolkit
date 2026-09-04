# -*- coding: utf-8 -*-
"""표기·삽화 규약 감사 (읽기 전용) — 반복 지적된 부류를 한 번에 훑는다.

신설 2026-07-30. 왜 별도 도구인가: 아래 부류들은 **사용자가 2~4회씩 반복 지적**했는데
빌드 검사가 보지 못하는 자리다(태깅 안 된 치수 요소, 평문 필드의 수식 흔적, 한 문장 안의
아래첨자 혼용, 풀이의 가로 전개). 매번 일회성 스크립트를 짜면 같은 감사를 다시 설계하게 되고,
그게 승인 피로의 1위였다(AGENTS 실행 규율 2).

**이 도구는 아무것도 고치지 않는다.** 판정과 위치만 낸다.

    python tools/audit_conventions.py                 # 전 챕터
    python tools/audit_conventions.py --chapter=ch01  # 한 챕터
    python tools/audit_conventions.py --class=A       # 부류 하나만
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# 화면 실효 크기 계산용 — 삽화 박스 안쪽 폭.
# ★ 하드코딩했다가 **596 으로 잘못 박아** 실효 크기를 3% 작게 계산했다(실제 612).
# 그래서 '규격 밖'이라고 신고해야 할 것을 통과시키거나 반대로 오탐을 냈다.
# 정본은 buildlib 하나뿐이어야 한다 — 숫자를 베끼지 말고 가져온다.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from buildlib.checks_svg import (  # noqa: E402
    FIGURE_RENDER_WIDTH, DASH_LEGIT_ROLES, _effective, _is_caption_text,
    figure_math_typesetting_hits, figure_text_grouping_hits, _text_stacks,
)
from buildlib.checks_content import (  # noqa: E402
    horizontal_step_issues, mask_inline_math, sentence_endings, split_paragraphs, TONE_SKIP,
)


def chapters(only=None):
    for subject in sorted(os.listdir(DATA)):
        sub_dir = os.path.join(DATA, subject)
        if not os.path.isdir(sub_dir):
            continue
        for name in sorted(os.listdir(sub_dir)):
            if not re.fullmatch(r"ch\d+\.json", name):
                continue
            if only and os.path.splitext(name)[0] != only:
                continue
            with open(os.path.join(sub_dir, name), encoding="utf-8") as fh:
                yield subject, os.path.splitext(name)[0], json.load(fh)


def walk_figures(chapter):
    """챕터 어디에 있든 삽화를 전부 꺼낸다 — 순회 범위가 좁으면 '0건'이 거짓말이 된다."""
    def rec(node, owner):
        if isinstance(node, dict):
            own = node.get("id", owner)
            for d in node.get("diagrams") or []:
                if isinstance(d, dict) and d.get("svg"):
                    yield own, d
            for key, value in node.items():
                if key == "diagrams":
                    continue
                yield from rec(value, own)
        elif isinstance(node, list):
            for item in node:
                yield from rec(item, owner)
    yield from rec(chapter, "?")


def walk_text_fields(chapter):
    """평문/LaTeX 텍스트 필드를 경로와 함께 낸다."""
    def rec(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                rec(value, path + "/" + str(key))
        elif isinstance(node, list):
            for i, item in enumerate(node):
                rec(item, path + "[" + str(i) + "]")
        elif isinstance(node, str):
            out.append((path, node))
    out = []
    rec(chapter, "")
    return out


def viewbox_width(svg):
    m = re.search(r"viewBox=['\"]\s*[\d.+-]+\s+[\d.+-]+\s+([\d.]+)", svg)
    return float(m.group(1)) if m else None


# ── A. 치수 요소의 파선 ────────────────────────────────────────────────────────
# 규격(2026-07-29 개정): 치수선·치수보조선은 **가는 실선 + 채운 화살촉**. 파선은 숨은선의 몫.
# 빌드는 `<g id='dim-…'>`/`class='dim'` 로 **태깅된** 것만 본다 → 태깅 없는 파선이 사각지대다.
#
# ★ 2026-07-30: 정당한 역할 목록을 **buildlib에서 가져온다**(`DASH_LEGIT_ROLES`).
# 예전에는 여기서 `hidden-edge` 하나만 걸러서, 빌드가 정당하다고 인정하는
# datum·divider·guide·phantom 을 이 감사만 계속 신고했다 — ch02 10건·ch05 1건이
# 고칠 것도 없이 매번 출력에 남았다. **잡음이 쌓이면 다음 사람이 감사를 통째로 무시한다.**
# 역할 목록을 두 곳에 적으면 반드시 갈라진다(이 파일 위쪽 FIGURE_RENDER_WIDTH 와 같은 교훈).
DASH_RE = re.compile(r"<(line|path|polyline)\b[^>]*stroke-dasharray[^>]*>")


def audit_dash(figure_id, svg):
    hits = []
    dim_spans = [(m.start(), m.end()) for m in
                 re.finditer(r"<g[^>]*(?:id=['\"]dim[^'\"]*['\"]|class=['\"][^'\"]*\bdim\b[^'\"]*['\"])[^>]*>.*?</g>",
                             svg, re.S)]
    for m in DASH_RE.finditer(svg):
        # ★ 상속을 본다 (2026-07-30). 요소 **자신의** class 만 보면 `<g class='guide'>` 로
        #   묶은 파선을 전부 '태깅 없음'으로 신고한다 — 빌드는 `_effective` 로 상속을 보고
        #   통과시키므로 **감사와 빌드가 갈라진다**(실측: ch02 guide 4건이 빌드 0 · 감사 4).
        #   판정 함수를 빌드에서 가져와 쓴다 — 같은 것을 두 번 구현하면 반드시 갈라진다.
        role = (_effective(svg, m.start(), m.group(0), "class", "") or "").lower()
        if any(mark in role for mark in DASH_LEGIT_ROLES):
            continue                      # 파선이 규격인 역할 — 태깅으로 그 역할을 밝힌 것
        tagged = any(s <= m.start() < e for s, e in dim_spans)
        width = re.search(r"stroke-width=['\"]([\d.]+)", m.group(0))
        w = float(width.group(1)) if width else None
        # 치수 계열로 의심되는 조건: dim 그룹 안이거나, 가는 선(≤1.5)이라 형상선이 아닌 것.
        suspect = tagged or (w is not None and w <= 1.5)
        hits.append({"tagged": tagged, "width": w, "suspect": suspect,
                     "snippet": m.group(0)[:110]})
    return hits


# ── B. 글자 위계 — 캡션이 라벨보다 **너무** 작아지지 않았는가 ─────────────────
# 2026-07-29 에 캡션을 라벨의 0.85배 이하로 일괄 축소했는데 사용자가 [사용자 발화 인용 생략] 로 되돌아왔다.
# 위계(제목 > 라벨 > 캡션)는 유지하되 **하한**을 본다. 화면 실효 px 로 잰다.
TEXT_RE = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)
HANGUL = re.compile(r"[가-힣]")


def audit_text_scale(figure_id, svg):
    vb = viewbox_width(svg)
    if not vb:
        return []
    scale = FIGURE_RENDER_WIDTH / vb
    rows = []
    for m in TEXT_RE.finditer(svg):
        attrs, inner = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        fs = re.search(r"font-size=['\"]([\d.]+)", attrs)
        if not fs:
            continue
        size = float(fs.group(1))
        bold = "font-weight='700'" in attrs or 'font-weight="700"' in attrs
        # ★ 캡션 판정은 **빌드와 같은 함수**로 한다 (2026-07-30).
        #   여기 한글 음절 수를 세는 사본이 따로 있어 자가 셋이 됐고
        #   (checks_svg._is_caption_text · 이 사본 · fix_figure_caption_tier),
        #   같은 삽화를 두고 결과가 갈렸다 — `fig-char-cases` 가 이 감사에서는 '위계 없음' 1건,
        #   나머지 둘에서는 0건이었다. 태그 한 글자로 검사가 꺼진 `_tagged_group_spans` 사고와
        #   같은 부류라 사본을 지운다(원어 병기 분기도 그 함수만 갖고 있었다).
        kind = "제목" if bold else (
            "캡션" if _is_caption_text({"weight": "700" if bold else "", "s": inner}) else "라벨")
        rows.append({"kind": kind, "effective": round(size * scale, 1),
                     "raw": size, "text": inner.strip()[:34]})
    return rows


# ── E. 평문 자리에 남은 수식 흔적 ─────────────────────────────────────────────
# 사용자: [사용자 발화 인용 생략] (2회 이상).
PLAIN_MATH = [
    (re.compile(r"\)\s*/\s*\("), "괄호분수 `)/(` — 수식 렌더러로 옮길 것"),
    (re.compile(r"\b\d+\s*×\s*10\^"), "거듭제곱 `10^` 이 평문에 남음"),
]
# 수식 자리(LaTeX)는 제외한다 — 거기 `^` 는 정상이다.
MATH_FIELDS = ("/latex", "/equations", "/solutionTemplate", "/svg", "/answer")


# ── G. 아래첨자 표기 혼용 ─────────────────────────────────────────────────────
# 한 문장 안에 `rho_oil`(밑줄 있음)과 `h1`(밑줄 없음)이 섞이면 화면에서 한쪽만 첨자가 된다.
SUB_UNDERSCORE = re.compile(r"[A-Za-zρ]_\{?[A-Za-z0-9]")
SUB_BARE = re.compile(r"(?<![A-Za-z_^{])\b([A-Za-z]|rho|SG)(\d)\b")


# ── H. 풀이의 가로 전개 ───────────────────────────────────────────────────────
# AGENTS 표기 규약: 문풀은 **세로 전개**. 가로로 이어 붙이면 계산 흐름이 안 보인다.
#
# ★★ 2026-08-04 — **판정을 빌드 검사(C27)로 옮기고 여기서는 그것을 부른다.**
#   여기 있던 자는 두 겹으로 빗나가 있었다: ⑴ `practice[].blanks[].answer` 만 순회했고
#   ⑵ 패턴에 실제로 쓰인 **`\qquad` 가 없었다.** 그래서 전 챕터 30곳이 있는데 **0건**을 찍었다.
#   자를 두 벌 두면 이렇게 갈라진다 — 이 리포가 분수·치수 라벨에서 이미 겪은 형태다.
#   판정의 정본은 `checks_content.horizontal_step_issues` 하나뿐이다.


# ── I. 삽화 수식이 **산문 수식과 다른 조판** ──────────────────────────────────
# 열린 날 2026-08-02(열역학) → 같은 부류가 동역학에도 그대로 있었다(사용자: [사용자 발화 인용 생략]).
#
# ★ **왜 못 잡았나 — 규격은 생성기에만 있고 자가 없었다.** 2026-08-02 에 `svg_fraction`·
#   `svg_math_line` 이 글꼴(등폭)·분수선 굵기·중심선·위첨자 조판을 산문에 맞춰 전부 바뀌었는데,
#   **이미 데이터에 박힌 조각은 아무도 다시 보지 않는다.** 생성기를 고치는 것은 *앞으로 찍을 것*만
#   고치는 일이라, 옛 조판이 남은 삽화는 규격이 바뀔 때마다 조용히 뒤처진다
#   (열역학도 같은 이유로 `잔여 6곳` 을 남겼다 — 인스턴스를 세었을 뿐 자를 만들지 않았다).
#
# 그래서 **지금 생성기가 찍을 값과 데이터를 직접 대조**한다. 규격이 또 바뀌면 이 감사가
# 자동으로 뒤처진 삽화를 지목한다 — 상수를 여기 베끼지 않고 buildlib 에서 가져오는 이유다.
# 판정은 **빌드와 같은 함수**를 부른다(`figure_math_typesetting_hits`). 여기 사본을 두면
# 감사 0건과 빌드 error 가 동시에 나는 상태가 만들어진다 — 이 리포가 이미 캡션 자·치수 그룹 자로
# 두 번 겪은 부류다. 이 절이 하는 일은 **출력 형식**뿐이다.
RELATION_MARKS = "=≈≠≤≥∫∑→"


# ── J. 같은 식을 **어디는 수식, 어디는 평문**으로 ──────────────────────────────
# 사용자(2026-08-02, 동역학 ch12): [사용자 발화 인용 생략]
#
# ★ **채팅에서는 두 표기가 똑같아 보인다** — 갈라지는 것은 화면이다. 한쪽은 인라인 수식으로
#   조판되고 다른 쪽은 본문 글꼴 그대로다. 그래서 사람이 눈으로 훑어서는 전수를 못 센다.
#   기존 검사들은 *분수·첨자·기호*처럼 **모양이 틀린 것**만 봤고, "같은 식인데 표기가 둘"이라는
#   **일관성** 축은 아무도 재지 않았다(규칙 11 — 자가 못 보는 축은 영원히 통과한다).
#
# 판정: 이 챕터가 **이미 인라인 수식으로 쓴 식**을 기준으로 삼는다. 정본이 데이터 안에 있으므로
# 과목·기호 목록을 코드에 박지 않아도 된다(공통 도구에 과목별 사실을 넣지 않는다).
INLINE_MATH_RE = re.compile(r"\\\((.+?)\\\)", re.S)
# 평문으로 옮길 수 있는 **간단한 식**만 기준으로 쓴다 — 분수·첨자·근호는 평문에 그대로 적을 수
# 없어서 "평문으로도 썼다"는 판정 자체가 성립하지 않는다.
SPACING_CMD = re.compile(r"\\[,;!]|\\ ")
# 평문 필드는 첨자를 **유니코드**로 쓴다(AGENTS 「plain 텍스트 필드는 유니코드 위첨자」).
# 그래서 `v_0`·`v^{2}` 를 평문으로 옮기면 `v₀`·`v²` 가 된다 — 그 모습으로도 대조해야
# `\(v^{2} = v_0^{2} + 2a_c(s-s_0)\)` 와 평문 `v² = v₀² + 2a_c(s−s₀)` 가 같은 식으로 잡힌다.
_SUB_MAP = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
            "6": "₆", "7": "₇", "8": "₈", "9": "₉", "n": "ₙ", "x": "ₓ"}
_SUP_MAP = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵",
            "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "n": "ⁿ", "-": "⁻", "+": "⁺"}
_SCRIPT = re.compile(r"([_^])\{([^{}]+)\}|([_^])(\w)")
# ★ 자리를 **글자 뒤에 붙여** 판정한다 — `source`·`sourceRef` 처럼 esc() 로 렌더되는 필드는
#   인라인 수식을 쓸 수 없으므로 신고해도 고칠 방법이 없다(잡음이 쌓이면 감사를 통째로 무시한다).
NOT_RENDERED_KEYS = ("/source", "/sourceRef", "/id", "/href", "/topic", "/stage")
# 필드 전체가 LaTeX 인 자리 — 거기서는 평문 대조가 성립하지 않는다.
# ★ `answer` 를 통째로 빼면 안 된다 (2026-08-02 실측). 이해도 체크의 `answer` 는 **산문**이고,
#   실제로 `\(a = \frac{dv}{dt}\)` 와 평문 `a ds = v dv` 가 **한 문장 안에** 섞여 있었다.
# ★ 빈칸 채우기의 답(`practice[].blanks[].answer`)도 **뺴지 않는다.** 빌드의 분수 검사는 그 자리를
#   면제하지만 그건 *학생이 분수를 타이핑할 수 없어서*이고, 여기서 묻는 것은 **표기 일관성**이다.
#   뷰어는 그 값을 `renderMath(blank.answer)` 로 그리므로(실측 2026-08-02) 인라인 수식이 통한다 —
#   면제를 베껴 오면 같은 식이 본문에서는 수식, 빈칸에서는 평문으로 갈린다.
NOTATION_EXEMPT = ("/latex", "/equations", "/solutionTemplate", "/svg")


# ★ 부분 문자열로 잡으면 **더 긴 식의 조각**이 걸린다 (2026-08-02 실측):
#   기준 `s = 0` 이 `Δs = 0.20 m` 안에서 매치돼 멀쩡한 자리를 신고했다.
#   식은 낱말이 아니라서 `\b` 로는 못 막는다 — 양옆이 수식을 이어 가는 글자면 조각이다.
_EXPR_CHAR = re.compile(r"[A-Za-z0-9α-ωΑ-Ω₀-₉⁰-⁹.Δ∆_]")


def standalone_at(text, start, end):
    """`text[start:end]` 가 **더 긴 식의 조각이 아닌가**."""
    if start and _EXPR_CHAR.match(text[start - 1]):
        return False
    return not (end < len(text) and _EXPR_CHAR.match(text[end]))


def notation_field(path):
    """표기 일관성을 물어도 되는 자리인가 — 화면에 나가고 렌더러를 거치는 필드."""
    if any(k in path for k in NOTATION_EXEMPT):
        return False
    return not any(path.endswith(k) or k + "[" in path for k in NOT_RENDERED_KEYS)


def _to_unicode_script(kind, body):
    table = _SUB_MAP if kind == "_" else _SUP_MAP
    out = "".join(table.get(c, "") if c in table else "" for c in body)
    return out if len(out) == len(body) else None


def math_plain_form(body):
    """인라인 수식을 **평문으로 적었을 때의 모습**. 옮길 수 없는 식이면 None."""
    s = SPACING_CMD.sub(" ", body)
    while True:
        m = _SCRIPT.search(s)
        if not m:
            break
        kind = m.group(1) or m.group(3)
        conv = _to_unicode_script(kind, m.group(2) or m.group(4))
        if conv is None:
            return None                    # 유니코드로 못 옮기는 첨자 — 평문형이 없다
        s = s[:m.start()] + conv + s[m.end():]
    if re.search(r"[\\^_{}]", s):
        return None                        # 분수·근호 등은 평문으로 적을 수 없다
    s = re.sub(r"\s+", " ", s).strip()
    # 너무 짧으면 우연히 겹친다(`v`·`a = 0`). 관계 기호가 있는 식만 본다.
    if len(s) < 5 or not any(c in s for c in RELATION_MARKS):
        return None
    return s


def audit_notation_split(fields):
    """(평문형, LaTeX 본문, 수식으로 쓴 자리, 평문으로 쓴 자리들) 목록.

    LaTeX 본문을 함께 내는 이유 — **처방(`tools/fix_notation_split.py`)이 같은 자를 쓰게** 하려고.
    정본은 *그 챕터가 이미 수식으로 쓴 형태*이지 도구가 아는 표기가 아니다(과목 무관).
    """
    canon = {}
    for path, text in fields:
        if "/svg" in path:
            continue
        for m in INLINE_MATH_RE.finditer(text):
            plain = math_plain_form(m.group(1))
            if plain:
                canon.setdefault(plain, (m.group(1), path))
    out = []
    for plain, (latex, where_math) in sorted(canon.items()):
        plain_hits = []
        for path, text in fields:
            if not notation_field(path):
                continue
            masked = mask_inline_math(text)
            at = masked.find(plain)
            while at >= 0 and not standalone_at(masked, at, at + len(plain)):
                at = masked.find(plain, at + 1)
            if at >= 0:
                plain_hits.append(path)
        if plain_hits:
            out.append((plain, latex, where_math, plain_hits))
    return out


# ★ J-2 — **대응하는 수식이 아예 없는** 평문 등호식. 위의 J-1 은 "이 챕터가 이미 수식으로 쓴 식"을
#   기준으로 삼으므로, 처음부터 끝까지 평문으로만 쓴 식은 기준이 없어 안 걸린다.
#   (사용자 요청: [사용자 발화 인용 생략] — '다' 를 만족시키려면
#   기준이 데이터 안에 있는 것만으로는 부족하다.)
BARE_EQUATION = re.compile(
    r"(?<![\w가-힣])"
    r"[A-Za-zα-ωΑ-Ω][A-Za-zα-ωΑ-Ω0-9₀-₉⁰-⁹·\s]{0,18}?"
    r"\s=\s"
    r"[A-Za-zα-ωΑ-Ω0-9(−+][A-Za-zα-ωΑ-Ω0-9₀-₉⁰-⁹·()+\-−\s]{0,24}")


def audit_bare_equations(fields):
    """**같은 글 안에서** 어떤 식은 인라인 수식, 어떤 식은 평문 — (자리, 걸린 조각) 목록.

    ★ 판정을 *그 글 자체*에 건다. "산문의 모든 등호식을 수식으로 올려야 하는가"는 취향이 갈리는
      설계 문제이고(영문 지문의 `at t = 4 s` 는 평문이 자연스럽다), 그걸 전부 신고하면
      실측 63건 중 대부분이 고칠 것 없는 잡음이 된다 — 잡음이 쌓이면 감사를 통째로 무시한다
      (규칙 7 의 A 절이 정확히 그렇게 죽었다). 반면 **한 문단 안에서 갈리는 것**은
      취향이 아니라 결함이다: 글쓴이가 그 자리에서 이미 수식 모드였는데 하나만 빠뜨린 것이다.
    """
    out = []
    for path, text in fields:
        if "/svg" in path or any(k in path for k in MATH_FIELDS):
            continue
        if any(path.endswith(k) or k + "[" in path for k in NOT_RENDERED_KEYS):
            continue
        if not INLINE_MATH_RE.search(text):
            continue                       # 이 글은 수식 모드가 아니다 — 취향 문제로 남긴다
        for m in BARE_EQUATION.finditer(mask_inline_math(text)):
            frag = m.group(0).strip()
            if HANGUL.search(frag):
                continue
            out.append((path, frag))
    return out


# ── L. 「잘 놓쳐요」와 「떠올리기」가 같은 말을 한다 ────────────────────────────
# 사용자(2026-08-02): [사용자 발화 인용 생략]
#
# ★ 두 카드는 **역할이 다르다** — 함정은 [사용자 발화 인용 생략] 는 경고(교재 근거가 붙는다),
#   이해도 체크는 독자가 **스스로 인출**하게 하는 질문이다. 그런데 같은 내용을 나란히 두면
#   체크의 답이 바로 옆에 적혀 있는 꼴이라 **인출이라는 목적 자체가 사라진다.**
#   게다가 본문이 이미 그 이야기를 했으면 같은 말이 한 화면에 세 번 나온다.
#
# ★ 판정은 **기계가 대신 못 한다** — 두 글이 '같은 내용인가'는 의미의 문제다.
#   그래서 이 절은 **후보와 점수만** 낸다(사람이 판정한다, 규칙 11). 한국어는 조사가 붙어
#   낱말 단위 비교가 어긋나므로 **글자 2-gram** 으로 잰다(형태소 분석기 없이 쓰는 표준 방식).
_KO_KEEP = re.compile(r"[가-힣A-Za-z0-9]+")
# 실측(동역학 ch12): 후보 3건이 0.31~0.37 이고 그 아래는 뚝 떨어진다. 낮추면 어휘가 같을 뿐인
# 정상 쌍이 쏟아지고, 올리면 사용자가 실제로 짚은 0.33 이 빠진다.
CARD_OVERLAP_MIN = 0.30
# ★ **너무 짧은 카드는 재지 않는다** (신설 2026-08-06, ch01 실측).
#   점수를 `min(len)` 으로 정규화하므로 **짧은 쪽이 짧을수록 점수가 튄다.**
#   `T(K) = T(°C) + ___` / `273.15` 같은 식 빈칸은 한글이 거의 없어 2-gram 이 6개뿐이고,
#   그 6개가 함정에 다 나오면 **자동으로 1.00** 이 된다 — 실제로 ch01 1위가 그것이었다.
#   내용이 겹쳐서가 아니라 **잴 것이 없어서** 나온 점수라, 그런 1.00 이 목록 맨 위에 있으면
#   읽는 사람이 이 감사를 통째로 불신하게 된다(잡음이 쌓이면 자를 무시한다 — [A] 의 교훈).
CARD_OVERLAP_MIN_GRAMS = 16


def _bigrams(text):
    out = set()
    for run in _KO_KEEP.findall(mask_inline_math(text)):
        if len(run) == 1:
            out.add(run)
        for i in range(len(run) - 1):
            out.add(run[i:i + 2])
    return out


def card_overlap_verdicts(subject):
    """사람이 '중복 아님'으로 판정한 쌍 — `data/<과목>/card-overlap-verdicts.json`.

    ★ 판정 파일을 **과목 폴더**에 둔다. 무엇이 중복인지는 그 과목의 콘텐츠 사실이라
      공통 코드가 알면 안 된다(선례: `problem-originality-verdicts.json`).
      없으면 빈 사전이라 **기존 동작 그대로**다 — 폴백이 과목을 알지 않는다.
    """
    path = os.path.join(DATA, subject, "card-overlap-verdicts.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh).get("verdicts") or {}
    except (OSError, ValueError, AttributeError):
        return {}


def verdict_hit(verdicts, ch, pid, cid):
    """이 쌍에 걸린 판정 키(없으면 None). 순수 함수 — 테스트가 직접 부른다.

    ★ **카드 id 는 챕터 안에서만 유일하다** (열린 날 2026-08-06, 고체역학 실측).
      `p1`·`p4`·`c2`·`c7` 은 챕터마다 처음부터 다시 붙으므로, 챕터를 담지 않은 키는
      한 챕터에 적은 판정이 **남의 챕터까지 조용히 면제**한다. 면제가 새는 것은
      감사를 장식으로 만드는 가장 빠른 길이라 키에 챕터를 넣는다.
      정본은 `chNN::함정::체크` 이고, 챕터 없는 두 토막 키는 뒤로 호환만 한다.
    """
    pair = str(pid) + "::" + str(cid)
    for key in (str(ch) + "::" + pair, pair):
        if key in verdicts:
            return key
    return None


def audit_prereq_overlap(chapter, subject, ch_name):
    """앞 장을 **되짚는다고 선언한 절**이 그 앞 장 본문을 그대로 되풀이하는 자리.

    (왼쪽 절, 오른쪽 `chNN/절`, 점수, 미리보기) 목록 — 점수 내림차순. 읽기 전용.

    왜 있나 (열린 날 2026-08-06 · 갚은 날 2026-08-13, 승격 잔량 ch04-review-inbox):
        [L] 은 **한 챕터 안에서만** 잰다(절 간 비교는 하지만 장 간 비교는 없다). 그런데
        사용자가 짚은 중복은 `ch02 ↔ ch04` 였다 — 자가 챕터 경계에서 끊겨 **구조적
        사각지대**였다. 그 항목이 남긴 처방이 이것이다:

        [사용자 발화 인용 생략]

    ★ **선언이 있는 자리만 본다.** 모든 절을 모든 앞 장 절과 견주면 후보가 조합으로 불어나
      진짜 중복이 그 더미에 묻힌다([L] 이 recall 을 뺀 것과 같은 이유).
    ★ **판정은 사람이 한다.** [사용자 발화 인용 생략] 는 기계가 못 본다 — 되짚기는 원래
      앞 장 말을 다시 하는 일이라, 겹치는 것 자체는 결함이 아니다. 이 절은 후보만 낸다.
    """
    cache, rows = {}, []

    def load(number):  # noqa: E306  (아래 주석이 이 함수의 자리를 설명한다)
        name = "ch%02d" % int(number)
        if name not in cache:
            path = os.path.join(DATA, subject, name + ".json")
            try:
                with open(path, encoding="utf-8") as fh:
                    cache[name] = json.load(fh)
            except (OSError, ValueError):
                cache[name] = None
        return name, cache[name]

    for sec in ((chapter.get("theory") or {}).get("sections") or []):
        for ref in sec.get("reviewPrerequisites") or []:
            prev_name, prev = load(ref.get("chapterNumber", -1))
            if not prev or prev_name == ch_name:
                continue
            target = next((s for s in ((prev.get("theory") or {}).get("sections") or [])
                           if s.get("id") == ref.get("sectionId")), None)
            if not target:
                continue
            best = best_paragraph_overlap(sec.get("content"), target.get("content"))
            if best:
                rows.append((str(sec.get("id")),
                             prev_name + "/" + str(target.get("id")), best[0], best[1]))
    return sorted(rows, key=lambda r: -r[2])


# 한 문단이 '잴 만한' 최소 길이. 짧은 문단은 2-gram 이 적어 점수가 튄다.
PREREQ_PARA_MIN_CHARS = 60


def best_paragraph_overlap(left_content, right_content):
    """두 본문에서 **가장 많이 겹치는 문단 쌍**의 (점수, 왼쪽 미리보기). 순수 함수.

    ★ 절 전체를 한 덩어리로 재지 않는 이유는 [L] 과 같다 — 긴 쪽에 묻혀 점수가 깔린다.
      문단 단위로 재고 **최댓값**을 그 쌍의 점수로 삼는다.
    ★ 떼어낸 이유: 디스크를 읽는 부분(`audit_prereq_overlap`)과 **점수 내는 부분**을 갈라야
      회귀가 과목 데이터를 전제하지 않고 판정을 잠글 수 있다
      (`test_shared_tests_do_not_assume_subject_data` 가 요구하는 형태다).
    """
    def paragraphs(text):
        return [p for p in str(text or "").split("\n\n")
                if len(p.strip()) >= PREREQ_PARA_MIN_CHARS]

    best = None
    for here in paragraphs(left_content):
        for there in paragraphs(right_content):
            a, b = _bigrams(here), _bigrams(there)
            if min(len(a), len(b)) < CARD_OVERLAP_MIN_GRAMS:
                continue
            score = len(a & b) / float(min(len(a), len(b)))
            if best is None or score > best[0]:
                best = (score, here.strip()[:70])
    return best


def audit_card_overlap(chapter):
    """(소유자, 왼쪽 id, 오른쪽 id, 점수, 미리보기) — 점수 내림차순. 순수 함수.

    ★ **본문도 잰다** (넓힌 날 2026-08-06 — 사용자가 발견한 사각지대).
      처음에는 함정 ↔ 이해도 체크만 봤다. 그런데 사용자가 ch03 §2 에서 짚은 것은
      [사용자 발화 인용 생략] 과 [사용자 발화 인용 생략] 였다 —
      **한 화면에 같은 말이 세 번** 나오는데 자는 그중 한 쌍만 보고 있었다.
      겹침이 나쁜 이유(체크의 답이 옆에 적혀 있으면 인출이 사라진다)는 본문에도 그대로
      적용된다. 본문은 문단 단위로 쪼개 재야 한다 — 절 전체를 한 덩어리로 재면 긴 쪽에
      묻혀 점수가 0.1 아래로 깔린다(실측).

    ★ 판정은 여전히 **사람이 한다.** 이 절은 후보와 점수만 낸다 — 어휘만 같은 정상 쌍이
      섞여 나오는 것이 정상이고, 점수를 판정으로 읽으면 멀쩡한 카드를 지운다.
    """
    rows, all_connects = [], []

    def owners(node):
        if isinstance(node, dict):
            if node.get("comprehensionChecks") or node.get("pitfalls"):
                yield node
            for v in node.values():
                yield from owners(v)
        elif isinstance(node, list):
            for v in node:
                yield from owners(v)

    def score_pair(left_text, right_text):
        a, b = _bigrams(left_text), _bigrams(right_text)
        if min(len(a), len(b)) < CARD_OVERLAP_MIN_GRAMS:
            return None          # 잴 것이 없어서 나오는 점수는 판정 대상이 아니다
        return len(a & b) / float(min(len(a), len(b)))

    for own in owners(chapter):
        oid = own.get("id")
        pits = [(p.get("id"), str(p.get("note") or "")) for p in own.get("pitfalls") or []]
        checks = [(c.get("id"), str(c.get("prompt") or "") + " " + str(c.get("answer") or ""))
                  for c in own.get("comprehensionChecks") or []]
        # ★ 본문과 견줄 때는 **연결하기(connect)** 만 본다.
        #   빈칸 회상(recall)의 답은 정의상 본문에서 뽑은 낱말이라 겹치는 것이 정상이다 —
        #   섞어 재면 ch03 한 장에서 후보가 56건으로 불어나 진짜 중복이 그 더미에 묻힌다
        #   (실측 2026-08-06: 상위 12건이 전부 본문 ↔ recall 이었다).
        #   문제가 되는 것은 *추론을 요구해야 할 카드가 본문을 되풀이하는 것*이다.
        connects = [(c.get("id"), str(c.get("prompt") or "") + " " + str(c.get("answer") or ""))
                    for c in own.get("comprehensionChecks") or []
                    if c.get("stage") == "connect"]
        paras = [("본문 ¶%d" % (i + 1), para)
                 for i, para in enumerate(str(own.get("content") or "").split("\n\n"))
                 if len(para.strip()) >= 60]
        all_connects.extend((oid, cid, ctext) for cid, ctext in connects)
        for left, right in ((pits, checks), (paras, connects), (paras, pits)):
            for lid, ltext in left:
                for rid, rtext in right:
                    sc = score_pair(ltext, rtext)
                    if sc is not None:
                        rows.append((oid, lid, rid, sc, ltext.strip()[:38]))
    # ★ **절과 절 사이도 본다** (넓힌 날 2026-08-06 — 자기 사고로 열렸다).
    #   §2 의 연결하기를 '고산 산장 라면' 으로 바꿨는데, §7 에 이미 '고산지대에서 물이
    #   낮은 온도에서 끓는다' 가 있었다. **같은 현상을 두 절이 각각 묻고 있었는데** 자는
    #   소유자(절) 안에서만 비교해서 0건이었다 — 고치는 쪽이 새 중복을 만들어도 조용했다.
    #   연결하기끼리만 본다: 회상은 절마다 그 절의 용어를 묻는 것이 정상이라 섞으면 잡음이다.
    for i, (o1, id1, t1) in enumerate(all_connects):
        for o2, id2, t2 in all_connects[i + 1:]:
            sc = score_pair(t1, t2)
            if sc is not None and sc >= CARD_OVERLAP_MIN:
                rows.append(("절 간 " + str(o1) + "↔" + str(o2), id1, id2, sc,
                             t1.strip()[:38]))
    rows.sort(key=lambda r: -r[3])
    return rows


# ── M. 독자에게 말하는 글의 말투 ──────────────────────────────────────────────
# 사용자(2026-08-02): [사용자 발화 인용 생략]
#
# ★ **관행은 있었는데 문서가 없었다.** 그래서 새 과목이 평어로 써도 아무것도 걸리지 않았다
#   (AGENTS·docs 전체 grep 에 말투 조항이 0건). 규칙이 없으면 데이터가 마음대로 정한다 —
#   `§N` 과 정확히 같은 부류다.
#
# 이 절은 **종결어미를 세기만 한다.** 어느 필드까지 존댓말로 갈지는 사람이 정하고,
# 바꾸는 것은 `tools/fix_honorific.py` 가 한다(손으로 고치면 문장마다 갈라진다).
# 판정은 **빌드와 같은 함수**를 쓴다(`checks_content.sentence_endings`·`TONE_SKIP`).
# 사본을 두면 감사 0건과 빌드 error 가 동시에 나는 상태가 만들어진다 — 이 파일에서만 세 번째다.


def plain_ending_histogram(chapter):
    """평어 종결 **어절**의 빈도 — 변환기가 다뤄야 할 가짓수를 먼저 재기 위한 것.

    한국어 어미 활용은 불규칙이 많아 통째로 정규식 변환하면 뜻이 상한다. 그래서
    `tools/fix_honorific.py` 는 **여기 나온 어절만** 화이트리스트로 바꾸고 나머지는 사람에게 넘긴다.
    """
    counts = {}
    for path, text in walk_text_fields(chapter):
        if any(k in path for k in TONE_SKIP):
            continue
        for sent, verdict in sentence_endings(text):
            if verdict != "plain":
                continue
            word = re.split(r"\s+", sent.rstrip(".!?"))[-1]
            counts[word] = counts.get(word, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])


# ── N. 분류·정의 나열이 산문에 뭉쳐 있는가 ────────────────────────────────────
# 사용자(2026-08-06): [사용자 발화 인용 생략]
#
# ★★ **규칙은 2026-07-27 부터 있었는데 그것을 재는 자가 하나도 없었다.**
#   AGENTS 「콘텐츠 표기 규약」이 *정의·분류 나열 → 불릿 목록(`- 용어: 설명`)* 이라고 적어 두었지만,
#   빌드에도 감사에도 이 부류를 묻는 검사가 **0개**였다. 유일한 이웃은 글 밀도 검사인데
#   그것은 `flow_break_paragraphs` 로 **목록을 '삽화의 대체재'로 세기만** 한다 —
#   즉 삽화가 충분한 절은 목록이 0개여도 영원히 통과한다. **목록을 요구하는 자는 없었다.**
#   실측이 그 구조를 그대로 보여 준다: ch00·ch01·ch02 는 4·3·4건인데 **ch03~05 는 0·0·0**.
#   규칙 승격 당시 손대던 장에만 들어갔고 **부류 전수 감사가 뒤 챕터로 안 갔다**(규칙 7 의 ⑵단계 누락).
#
# ★ 판정은 사람이 한다 — 이 절은 **후보와 근거만** 낸다([L]·[J] 와 같은 급).
#   [사용자 발화 인용 생략] 이라고 규칙 자신이 단서를 달았으므로, 기계가
#   '여기는 목록이어야 한다'를 단정하면 그 단서를 어기게 된다.
# ★ 글자 클래스에서 **문장부호와 줄바꿈을 빼는 것이 핵심**이다. `[^,]` 로 두면 마침표를
#   넘어가 두 문장에 걸친 조각을 '대구'로 읽는다(첫 실행 실측: 9건 중 5건이 그 오탐이었다).
_LIST_RUN = re.compile(r"(?:[가-힣][^,.!?\n]{0,40}?[는은] [^,.!?\n]{2,60}?고, ){2,}")
_TERM_PAIR = re.compile(r"[가-힣][가-힣 ]{0,12}\([a-zA-Z][a-zA-Z \-]{2,}\)")


def audit_prose_list(chapter):
    """산문에 뭉친 분류 나열 후보 — (경로, 사유, 미리보기). 순수 함수(테스트가 부른다).

    두 신호만 본다. 둘 다 **한 단락 안**에서 재고, 이미 목록·표인 단락은 건너뛴다.
      ⑴ `A는 …고, B는 …고, C는 …` 대구가 이어지는 문장 (고체·액체·기체가 그 모양이다)
      ⑵ `용어(english)` 병기가 **3개 이상** 들어찬 단락 (상변화 5분류가 그 모양이다)
    """
    rows = []
    for path, text in walk_text_fields(chapter):
        if not path.endswith("/content"):
            continue                      # 이론 본문만 — 함정·풀이는 원래 짧다
        for para in split_paragraphs(text):
            lines = [ln for ln in para.split("\n") if ln.strip()]
            if lines and all(re.match(r"^\s*[-|]", ln) for ln in lines):
                continue                  # 이미 목록·표다
            run = _LIST_RUN.search(para)
            if run:
                rows.append((path, "대구 나열이 한 문장에 이어진다 — `- 용어: 설명` 후보",
                             run.group(0)[:60]))
            pairs = _TERM_PAIR.findall(para)
            if len(pairs) >= 3:
                rows.append((path, "한 단락에 용어 병기 %d개 — 분류 목록 후보" % len(pairs),
                             " · ".join(p.strip() for p in pairs[:4])))
    return rows


def audit_tone(chapter):
    """필드 갈래별 (평어 수, 존댓말 수, 평어 예시들). 순수 함수."""
    groups = {}
    for path, text in walk_text_fields(chapter):
        if any(k in path for k in TONE_SKIP):
            continue
        kind = re.sub(r"\[\d+\]", "[]", path)
        for sent, verdict in sentence_endings(text):
            if verdict is None:
                continue
            row = groups.setdefault(kind, {"plain": 0, "polite": 0, "samples": []})
            row[verdict] += 1
            if verdict == "plain" and len(row["samples"]) < 2:
                row["samples"].append(sent[-30:])
    return groups


def main():
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    want = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--class=")), None)
    totals = {}

    def bump(key, n=1):
        totals[key] = totals.get(key, 0) + n

    def on(key):
        return want is None or want.upper() == key

    for subject, ch, chapter in chapters(only):
        figures = list(walk_figures(chapter))
        fields = walk_text_fields(chapter)

        if on("A"):
            print("\n=== [A] 치수 요소의 파선 — %s %s ===" % (subject, ch))
            for owner, d in figures:
                for hit in audit_dash(d["id"], d["svg"]):
                    if not hit["suspect"]:
                        continue
                    bump("A")
                    print("  %-28s 태깅=%s 굵기=%s\n      %s"
                          % (d["id"], "예" if hit["tagged"] else "아니오",
                             hit["width"], hit["snippet"]))

        if on("B"):
            print("\n=== [B] 글자 위계·실효 크기 — %s %s ===" % (subject, ch))
            for owner, d in figures:
                rows = audit_text_scale(d["id"], d["svg"])
                caps = [r for r in rows if r["kind"] == "캡션"]
                labels = [r for r in rows if r["kind"] == "라벨"]
                if not caps:
                    continue
                lo = min(r["effective"] for r in caps)
                lab = (sum(r["effective"] for r in labels) / len(labels)) if labels else None
                flag = []
                if lo < 13.0:
                    flag.append("캡션 실효 %.1fpx < 13 하한" % lo)
                if lab and lo > lab * 0.95:
                    flag.append("캡션이 라벨과 거의 같음(위계 없음)")
                if flag:
                    bump("B")
                    print("  %-28s %s  (라벨 평균 %s)"
                          % (d["id"], " · ".join(flag), ("%.1f" % lab) if lab else "-"))

        if on("E"):
            print("\n=== [E] 평문에 남은 수식 흔적 — %s %s ===" % (subject, ch))
            for path, text in fields:
                if any(path.endswith(k) or k in path for k in MATH_FIELDS):
                    continue
                for rx, why in PLAIN_MATH:
                    if rx.search(text):
                        bump("E")
                        print("  %s\n      %s\n      %s" % (path, why, text[:110]))
                        break

        if on("G"):
            print("\n=== [G] 아래첨자 표기 혼용 — %s %s ===" % (subject, ch))
            for path, text in fields:
                if "/svg" in path:
                    continue
                if SUB_UNDERSCORE.search(text) and SUB_BARE.search(text):
                    bump("G")
                    bare = set(m.group(0) for m in SUB_BARE.finditer(text))
                    print("  %s\n      밑줄 없는 첨자: %s\n      %s"
                          % (path, ", ".join(sorted(bare))[:70], text[:110]))

        if on("H"):
            print("\n=== [H] 풀이의 가로 전개 — %s %s ===" % (subject, ch))
            for why in horizontal_step_issues(chapter):
                bump("H")
                print("  " + why)

        if on("I"):
            print("\n=== [I] 삽화 수식 조판이 산문과 다름 — %s %s ===" % (subject, ch))
            for owner, d in figures:
                for why, preview in figure_math_typesetting_hits(d["svg"]):
                    bump("I")
                    print("  %-28s %s\n      %s" % (d["id"], why, preview))

        if on("M"):
            print("\n=== [M] 말투 — 독자에게 말하는 글의 종결어미 — %s %s ===" % (subject, ch))
            print("  %-46s %6s %6s" % ("필드", "평어", "존댓"))
            for kind, row in sorted(audit_tone(chapter).items(),
                                    key=lambda kv: -kv[1]["plain"]):
                if not row["plain"]:
                    continue
                bump("M", row["plain"])
                print("  %-46s %6d %6d" % (kind[:46], row["plain"], row["polite"]))
                for s in row["samples"]:
                    print("        … %s" % s)
            hist = plain_ending_histogram(chapter)
            print("  — 평어 종결 어절 %d가지 (변환기가 다뤄야 할 가짓수)" % len(hist))
            print("    " + " · ".join("%s×%d" % (w, n) for w, n in hist[:18]))

        if on("L"):
            print("\n=== [L] 본문·잘 놓쳐요·떠올리기 내용 겹침 (사람이 판정) — %s %s ==="
                  % (subject, ch))
            verdicts = card_overlap_verdicts(subject)
            for owner, pid, cid, score, note in audit_card_overlap(chapter):
                if score < CARD_OVERLAP_MIN:
                    continue
                if verdict_hit(verdicts, ch, pid, cid):
                    print("  %-26s %.2f  %s ↔ %s  [판정 기록됨]" % (owner, score, pid, cid))
                    continue
                bump("L")
                print("  %-26s %.2f  %s ↔ %s\n      %s" % (owner, score, pid, cid, note))

        if on("P"):
            print("\n=== [P] 앞 장을 되짚는다고 선언한 절 ↔ 그 앞 장 본문 (사람이 판정) — %s %s ==="
                  % (subject, ch))
            verdicts = card_overlap_verdicts(subject)
            for left, right, score, note in audit_prereq_overlap(chapter, subject, ch):
                if score < CARD_OVERLAP_MIN:
                    continue
                if verdict_hit(verdicts, ch, left, right):
                    print("  %-26s %.2f  → %s  [판정 기록됨]" % (left, score, right))
                    continue
                bump("P")
                print("  %-26s %.2f  → %s\n      %s" % (left, score, right, note))

        if on("K"):
            print("\n=== [K] 색 묶음과 간격이 어긋남 — %s %s ===" % (subject, ch))
            for owner, d in figures:
                hits = figure_text_grouping_hits(d["svg"])
                for why, preview in hits:
                    bump("K")
                    print("  %-28s %s\n      %s" % (d["id"], why, preview))
                if not hits:
                    continue
                # ★ **어느 간격을 벌려야 하는지**까지 찍는다 (2026-08-02).
                #   신고 문구는 부류만 알려 줄 뿐이라, 고치는 사람이 매번 SVG 를 되짚어
                #   y·색·앵커를 손으로 복원해야 했다. 그 복원이 이 부류를 고치는 비용의
                #   대부분이고, 손으로 하면 틀린다 — 자가 이미 아는 값을 그냥 내보낸다.
                for chain in _text_stacks(d["svg"]):
                    if len({it["fill"] for it in chain}) < 2:
                        continue                       # 색 경계가 없으면 비교할 짝이 없다
                    print("      ── 줄기 (x=%.1f · %s)" % (chain[0]["x"], chain[0]["anchor"]))
                    for a, b in zip([None] + chain, chain + [None]):
                        if a is None:
                            continue
                        mark = ""
                        if b is not None:
                            gap = b["box"][1] - a["box"][3]
                            mark = ("  ↓ %5.1fpx  %s" % (gap, "같은 색" if a["fill"] == b["fill"]
                                                         else "★색 경계"))
                        print("         y=%-7.1f %-8s %s%s"
                              % (a["y"], a["fill"], a["s"].strip()[:24], mark))

        if on("N"):
            print("\n=== [N] 분류 나열이 산문에 뭉침 (사람이 판정) — %s %s ===" % (subject, ch))
            for path, why, preview in audit_prose_list(chapter):
                bump("N")
                print("  %s\n      %s\n      %s" % (path, why, preview))

        if on("J"):
            print("\n=== [J] 같은 식을 수식·평문 두 표기로 — %s %s ===" % (subject, ch))
            for plain, _latex, where_math, plain_hits in audit_notation_split(fields):
                bump("J", len(plain_hits))
                print("  %r\n      수식으로: %s\n      평문으로 %d곳:" % (plain, where_math, len(plain_hits)))
                for p in plain_hits:
                    print("        %s" % p)
            for path, frag in audit_bare_equations(fields):
                bump("J")
                print("  [수식 대응 없음] %s\n      %r" % (path, frag))

    print("\n" + "=" * 62)
    if totals:
        print("합계: " + " · ".join("%s %d건" % (k, v) for k, v in sorted(totals.items())))
    else:
        print("해당 없음 (0건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
