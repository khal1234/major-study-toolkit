# -*- coding: utf-8 -*-
"""SVG geometry, answer-slot, and figure-style checks."""
import html
import math
import re

from .textutil import _plain_math_text

# ★ 좌표 수정 대기 명단 (2026-07-22 신설).
# halo 글자가 여백 검사를 통째로 건너뛰던 구멍을 막자 그동안 **아무 검사도 받지 않던**
# 라벨 겹침이 ch02에서 19건 드러났다. 숨기려고 두는 목록이 아니라, 무엇이 남았는지
# 이름으로 남겨 두는 목록이다 — 좌표를 고칠 때마다 여기서 지운다. 비면 끝난 것이다.
PENDING_FIG_FIXES = set()
# ★ 2026-07-30: ch00·ch04·ch05 를 승격했다. 승격 전에는 **검사가 도는데 아무것도 막지 않는**
# 상태였고, 그게 이 리포에서 결함이 반복해서 되살아난 구조다(AGENTS 규칙 7-⑷).
# 새 챕터를 만들면 여기 8개 목록에 **그 챕터를 반드시 추가한다** —
# 잠금장치는 test_checks.py::test_strict_promotion_covers_all_chapters.
FIGURE_LINT_STRICT_CHAPTERS = {"ch00.json", "ch01.json", "ch02.json", "ch03.json",
                               "ch04.json", "ch05.json", "ch06.json", "ch07.json",
                               "ch12.json"}
ARROW_CONNECTION_STRICT_CHAPTERS = {"ch00.json", "ch01.json", "ch02.json", "ch03.json",
                                    "ch04.json", "ch05.json", "ch06.json", "ch07.json",
                                    "ch12.json"}
ANSWER_SLOT_GEOMETRY_STRICT_CHAPTERS = {"ch00.json", "ch01.json", "ch02.json", "ch03.json",
                                        "ch04.json", "ch05.json", "ch06.json", "ch07.json",
                                        "ch12.json"}
SVG_LAYOUT_STRICT_CHAPTERS = {"ch00.json", "ch01.json", "ch02.json", "ch03.json",
                              "ch04.json", "ch05.json", "ch06.json", "ch07.json",
                              "ch12.json"}
# 승격을 **의식적으로** 미루는 챕터. 비어 있는 것이 정상이다.
# 넣을 때는 왜 못 올리는지와 언제 올릴지를 여기 주석으로 남긴다 —
# 그래야 '보류'와 '잊음'이 구별된다(그 구별이 없어서 ch04·ch05가 조용히 새어나갔다).
#
# ★ ch00~ch02 = **`MIDDOT_STRICT_CHAPTERS` 하나만** 보류다 (2026-08-02, solids 세션).
#   나머지 7개 목록에는 이미 들어 있고, 고체역학 데이터는 오늘 가운데점 **0건**으로 정리했다.
#   그런데도 못 올리는 이유는 **이 목록이 과목 간에 공유되는 파일명 집합**이라서다 —
#   여기 `ch01.json` 을 넣으면 열역학 ch01·공학수학 ch01 에도 그대로 걸리는데,
#   그 두 과목은 아직 정리 전이다(C17 주석의 실측: 열역학 116줄 · 공학수학 22줄).
#   즉 지금 올리면 **다른 과목 빌드를 세운다**(AGENTS: 한 과목의 승격이 남의 데이터에 걸린다).
#   → 두 과목이 정리를 끝내면 그때 `MIDDOT_STRICT_CHAPTERS` 로 옮기고 여기서 지운다.
#
#   ⚠️ **이 집합이 과목별 사실을 파일명으로 들고 있다는 것 자체가 잠재 결함이다.**
#   `ch12.json` 은 지금 동역학 기준으로 올라가 있는데, 고체역학도 12장(평면응력의 응용)이
#   범위라 그 챕터를 만드는 순간 **남의 과목 승격 상태를 그대로 물려받는다.** 반대도 같다.
#   AGENTS 「공통 도구에 과목별 사실을 박지 않는다」에 걸리는 형태 — 고치려면 8개 목록을
#   과목 폴더로 내려야 해서 이번 배치 범위 밖으로 둔다(사용자 판단 대기).
#
# ★ ch12 = **`PLOT_STRICT_CHAPTERS` 하나만** 보류다 (2026-08-02, dynamics 세션).
#   나머지 목록에는 이미 들어 있다. 못 올리는 이유는 데이터가 아니라 **자가 못 보기 때문**이다:
#   `_plot_axes` 는 L자 축을 **하나의 `<path>`** 로 그린 것만 축으로 인정하는데, 동역학 ch12 의
#   v-t·v-s 선도는 축을 `<line>` **두 개**로 그린다. 그래서 이 챕터의 선도는 검사 대상에조차
#   들지 않고, 지금 올리면 「0건」이 **"위반이 없다"가 아니라 "한 건도 안 봤다"** 가 된다
#   (AGENTS 규칙 11 · `PDF_FOR` 폴백 실사고와 같은 부류 — 통과와 미측정이 같은 출력이 된다).
#   → 검사를 여는 **것은 thermo 의 몫이다**(공통 1차 관리 주체). `<line>` 쌍도 축으로 인정하도록
#     `_plot_axes` 를 넓히면 **다른 과목의 안 보이던 선도가 한꺼번에 드러나** 그 빌드가 멈출 수
#     있으므로, 그 과목 세션에서 실측하며 여는 것이 맞다. 열리면 여기서 지우고 승격한다.
STRICT_PENDING_CHAPTERS = {"ch00.json", "ch01.json", "ch02.json", "ch12.json"}


def _attr(attrs, name, default=None):
    prefix = r"(?<![A-Za-z0-9:_-])" + re.escape(name)
    m = re.search(prefix + r"='([^']*)'", attrs) or re.search(prefix + r'="([^"]*)"', attrs)
    return m.group(1) if m else default

# ★★ 글자 폭 계수는 **브라우저에서 잰 값**이다 (교정 2026-08-07).
#
#   열린 계기: 사용자가 같은 자리를 두 번 지적했다 — [사용자 발화 인용 생략](ch01 유도 8번).
#   실측하니 겹침이 아니라 **벌어짐**이었고(브라우저 기준 1.9em), 그 구멍을 만든 것이
#   이 근사자였다. 분수를 붙이려 하면 빌드가 '글자끼리 겹침'으로 막고, 빌드를 만족시키면
#   화면에 구멍이 남는다 — **자가 실제보다 넓게 재고 있었기 때문**이다.
#
#   측정 방법: 뷰어가 실제로 쓰는 폰트에서 `<text>` 를 만들어 `getBBox().width / font-size`
#   (열역학 ch01 유도 카드, 2026-08-07). 옛 값 → 실측값:
#     한글 1.00 → **0.887**   (13% 과대 — 한글이 든 줄마다 그만큼 구멍이 생겼다)
#     공백 0.32 → **0.251**  (좁은 글자 목록에 뭉뚱그려 있었다)
#     `·()[]/°` 0.60 → **0.27~0.48**
#   ★ 반대 방향(과소 추정)도 있었다 — 이쪽이 **더 위험하다**(진짜 겹침을 놓친다):
#     `→` 0.60 → **0.957** · `←` 0.913 · `↔` 1.299 · `⇒` 0.957 · `≅` 1.001 · `%` 0.889
#   즉 이 자는 한쪽으로 안전한 자가 아니라 **양쪽으로 틀린 자**였다. 그래서 '완화'가 아니라
#   **교정**이다 — 잠금은 `test_checks.py::test_char_width_matches_the_browser`.
#
#   ★ 글자(A-Z·a-z·숫자)는 0.60 을 그대로 둔다. 실측은 대문자 0.644·소문자 0.512·숫자 0.590 이라
#     평균이 0.60 근처이고, 낱자별로 쪼개면 다른 과목의 통과하던 삽화가 무더기로 흔들린다.
#     여기서 고친 것은 **계통 오차가 확실한 자리**뿐이다.
_CHAR_W_WIDE = {"→": 0.957, "←": 0.913, "↔": 1.299, "⇒": 0.957, "≅": 1.001, "%": 0.889}
_CHAR_W_NARROW = {"·": 0.273, "(": 0.41, ")": 0.41, "[": 0.41, "]": 0.41,
                  "/": 0.478, "°": 0.478, " ": 0.251}
# ★★ **삽화에는 글꼴이 둘인데 자는 하나였다** (열린 날 2026-08-07 · 같은 자리 2회 지적).
#
#   위 표는 **삽화 라벨의 글꼴**(Pretendard)에서 잰 것이다. 그런데 2026-08-02 부터
#   조판 단위(`svg_fraction`·`svg_math_line`)는 산문 수식과 같은 **등폭 글꼴**(`MATH_FONT`)로
#   찍는다 — 그때 글꼴만 바꾸고 **폭을 재는 자는 그대로 두었다.**
#
#   실측(브라우저 `getExtentOfChar`, 2026-08-07 · **실제 삽화** `fig-d-piston-balance` 전수):
#       공백  삽화 0.251  vs  등폭 **0.586**  (2.3배)
#       한글  삽화 0.865  vs  등폭 **1.094**  (등폭 글꼴에 한글이 없어 대체 글꼴이 그린다)
#       `→`  삽화 0.892  vs  등폭 **0.586**
#       낱자  삽화 0.54~0.65 vs 등폭 **0.586** (등폭은 전부 같다 — 78% tspan 도 같은 비율)
#   ★★ **이 숫자들은 글꼴 선언에 딸린 값이다** — `MATH_FONT` 를 건드리면 함께 다시 잰다.
#     같은 날 스택이 Consolas 로 갈려 있을 때는 낱자 0.550 이었다.
#   ★★★ **재는 자리를 틀리면 한글 값이 조용히 바뀐다 — 같은 함정에 두 번 빠졌다.**
#     빈 `<svg>` 를 body 에 심어 재면 한글이 **1.000** 으로 나온다. 그 SVG 는 페이지의
#     글꼴 상속 사슬 밖이라 **대체 글꼴이 달라지기 때문**이다. 자는 반드시
#     **그 글자가 실제로 놓이는 삽화 안에서** 잰다(2026-08-07 두 번 모두 이걸로 틀렸고,
#     두 번째는 이 주석을 이미 적어 두고도 반복했다).
#   즉 한글·공백이 든 한 줄 수식은 조각 폭이 통째로 어긋나고, 그 어긋남은 **분수가 앞 글자
#   쪽으로 밀려드는 것**으로 나타난다. 사용자가 든 캡션(`정지 상태 → P_gas = P_atm + mg/A`)은
#   공백 7 + 한글 4 라 어긋남이 19px(1.9em)였다 — [사용자 발화 인용 생략] 가 그것이다.
#
#   ★ **그 캡션이 화면에서 멀쩡해 보였던 이유가 이 부류의 정체다** — 손으로 조립된 줄이라
#     생성기를 안 탔고 그래서 `font-family` 가 없었다. 자(Pretendard)와 렌더 글꼴이 우연히
#     맞아떨어져, *규격대로 찍은 줄이 오히려 틀리고 규격 밖의 줄이 맞는* 상태였다.
#     그 우연을 없애려고 C20 이 「조판 그룹 안의 글자는 수식 글꼴이어야 한다」를 검사한다.
MONO_CJK_W = 1.094   # 등폭 글꼴 안의 한글 advance (대체 글꼴이 그린다 — 실제 삽화에서 실측)
MONO_W = 0.586       # 그 밖의 모든 글자 — 등폭이라 **공백까지** 같다


def _char_w(ch, fs, mono=False, cjk_w=None):
    """글자 하나의 advance. `mono` 는 **`MATH_FONT` 로 그려질 글자**인가 (위 주석이 정본).

    `cjk_w` 를 주면 한글 폭을 그 값으로 본다 — **잘림 검사가 최악 글꼴로 재려고** 쓴다
    (아래 `CJK_W_WORST` 주석이 정본).
    """
    o = ord(ch)
    cjk = (0x1100 <= o <= 0x11FF or 0x3000 <= o <= 0x9FFF
           or 0xAC00 <= o <= 0xD7AF or 0xFF00 <= o <= 0xFFEF)
    if mono:
        return fs * (MONO_CJK_W if cjk else MONO_W)
    if cjk_w:
        # ★★ **최악 글꼴에서는 한글만 넓어지는 게 아니다** (실측 2026-08-12, Malgun Gothic).
        #   줄표·말줄임표는 **전각**이 되고 공백도 넓어진다. 한글 계수만 올리고 이 둘을
        #   Pretendard 값으로 두었더니 그 캡션이 321 로 나와 **여전히 통과했다**(실제 338.3).
        #   검증: 16한글×1.0 + 줄표 1.0 + 공백 5×0.36 = 18.8em × 18 = **338.4** ≈ 실측 338.3.
        if cjk or ch in "—–―…·":
            return fs * cjk_w
        if ch == " ":
            return fs * 0.36
    if cjk:
        return fs * 0.887
    if ch in _CHAR_W_WIDE:
        return fs * _CHAR_W_WIDE[ch]
    if ch in _CHAR_W_NARROW:
        return fs * _CHAR_W_NARROW[ch]
    if ch in "iIljtf.,:;|'":
        return fs * 0.32
    return fs * 0.60

def _inherited_attr(svg, pos, name, pattern=None):
    """`pos`의 요소가 조상 <g>에서 물려받는 속성값 (없으면 None).

    열린 날 2026-07-28(font-size) → **일반화 2026-07-30.**
    처음에는 font-size 전용이었는데, 같은 뿌리에서 결함이 셋 더 나왔다
    (thermo-ch03·ch04 세션 보고 + 이번 실측):
      - `<g text-anchor='middle'>` 안의 라벨을 전부 **좌측정렬로** 계산해 bbox가 틀렸다
      - `<g stroke='…'>` 안의 <rect>를 **도형으로 안 봤다**(fig-molecular-arrangement 상자 3개)
      - `<g fill='…'>` 안의 채운 path를 **채운 도형으로 안 봤다**(화살촉이 z-order 검사 밖)
    셋 다 '검사가 조용히 꺼진다'는 같은 증상이라 상속 자체를 한 곳에서 처리한다.
    각 챕터가 `<text>` 마다 속성을 다시 적어 **우회**하고 있었는데, 우회는 인스턴스
    처리라 다음 챕터에서 그대로 재발한다.

    여는 <g>를 스택에 쌓고 닫힐 때 빼서, 아직 열려 있는 것 중 **가장 안쪽** 값을 쓴다.
    """
    stack = []
    for m in re.finditer(r"<(/?)g\b([^>]*?)(/?)>", svg[:pos]):
        if m.group(1):
            if stack:
                stack.pop()
        elif not m.group(3):                      # 자체 종료(<g …/>)는 자식을 갖지 않는다
            stack.append(_attr(m.group(2), name))
    for value in reversed(stack):
        if value is None:
            continue
        if pattern and not re.fullmatch(pattern, value):
            continue
        return value
    return None


def _inherited_font_size(svg, pos):
    value = _inherited_attr(svg, pos, "font-size", r"\d+(?:\.\d+)?")
    return float(value) if value else None


def _effective(svg, pos, attrs, name, default=None):
    """자기 속성이 있으면 그것, 없으면 조상 <g>에서 물려받은 것."""
    own = _attr(attrs, name)
    if own is not None:
        return own
    inherited = _inherited_attr(svg, pos, name)
    return default if inherited is None else inherited


def _svg_texts(svg):
    items = []
    for m in re.finditer(r"<text([^>]*)>(.*?)</text>", svg, re.S):
        attrs, inner = m.group(1), m.group(2)
        if "transform" in attrs:  # 회전·이동 텍스트는 bbox 추정 불가 — 검사 제외
            continue
        s = re.sub(r"<[^>]+>", "", inner)
        s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        # ★ **수치 문자 참조도 풀어야 폭이 맞는다** (열린 날 2026-08-24, ee ch04).
        #   `&#8722;`(−) 를 안 풀면 **리터럴 8글자**로 재어 상자가 74px 이 된다 — 같은 자리의
        #   `+` 는 11px 다. 그래서 판에서 30px 이나 떨어뜨린 부호가 「도형 경계에 걸침」으로
        #   신고됐고, 좌표를 옮겨 피하려다 **전하를 판 바깥에 그리는** 틀린 삽화가 나왔다.
        #   폭을 재는 자가 틀리면 그 신고를 따르는 사람이 그림을 망가뜨린다.
        s = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), s)
        s = re.sub(r"&#[xX]([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), s)
        own = _attr(attrs, "font-size")
        inherited = _inherited_font_size(svg, m.start())
        items.append({
            "x": float(_attr(attrs, "x", "0")), "y": float(_attr(attrs, "y", "0")),
            "fs": (float(own) if own and re.fullmatch(r"\d+(?:\.\d+)?", own)
                   else (inherited if inherited else 12.0)),
            "anchor": _effective(svg, m.start(), attrs, "text-anchor", "start"),
            "halo": ("paint-order" in attrs) or ("paint-order" in inner),
            # 이 글자가 **등폭(수식) 글꼴로 그려지는가** — 폭을 재는 자가 갈린다(`_char_w` 주석).
            "mono": _effective(svg, m.start(), attrs, "font-family", "") == MATH_FONT,
            # 굵기는 캡션 판정에 쓴다(제목은 굵다) — `_is_caption_text` 참조.
            "weight": _effective(svg, m.start(), attrs, "font-weight", ""),
            # 색은 **묶음의 표시**다 — 같은 색이면 같은 위계, 색이 바뀌면 블록 경계다
            # (`figure_text_grouping_hits` 가 이걸로 간격을 판정한다).
            "fill": (_effective(svg, m.start(), attrs, "fill", "") or "").strip().lower(),
            "s": s,
            # 원본 마크업 — 폭을 잴 때 `<tspan font-size='78%'>` 같은 비율을 반영하려면
            # 태그를 지운 문자열만으로는 부족하다(`run_width` 가 이걸 쓴다).
            "raw": inner,
            "pos": m.start(),   # 그리기 순서 — 뒤에 그려진 도형은 글자를 덮는다
            # 끝 오프셋은 **글자를 옮기는 도구**가 쓴다(`tools/fix_dim_label.py` 가 치수 라벨을
            # 치수 그룹 안으로 옮긴다). 잘라낸 사본으로는 원본에서의 자리를 되찾을 수 없다.
            "end": m.end(),
        })
    return items


def _tagged_group_spans(svg, marks):
    """`class`/`id` 에 `marks` 중 하나가 든 <g> 의 (시작, 끝, 본문). **중첩을 세어 닫는다.**

    순수 함수 — 테스트가 직접 부른다.

    열린 날 2026-07-30 (ch04 규격 이관). 이걸 쓰는 두 검사가 `<g[^>]*>(.*?)</g>` 라는
    **비탐욕 정규식**으로 그룹 본문을 잘라 쓰고 있었다. 치수 그룹 안에서 보조선을
    `<g stroke=…>` 로 한 번 더 묶으면 본문이 **안쪽 `</g>` 에서 끊긴다.** 결과가 둘인데
    나쁜 쪽은 두 번째다:
      ⑴ 화살촉이 본문 밖으로 빠져 '치수 본선/채운 화살촉 구성 검토' **오경고**가 뜬다(시끄럽다).
      ⑵ 안쪽 `</g>` 뒤에 있는 굵은 선·파선이 **검사 범위 밖**이 된다 — 규격 위반이 조용히 통과한다.
    ⑴은 사람이 알아채지만 ⑵는 아무도 못 본다. 중첩을 세면 둘 다 없어진다.
    """
    out = []
    stack = []
    for t in re.finditer(r"<g\b([^>]*?)(/?)>|</g\s*>", svg, re.S):
        if t.group(0).startswith("</"):
            if stack:
                start, attrs, body_start = stack.pop()
                marker = " ".join((_attr(attrs, "id", ""), _attr(attrs, "class", ""))).lower()
                if any(m in marker for m in marks):
                    out.append((start, t.end(), svg[body_start:t.start()]))
        elif t.group(2) != "/":          # 자체 종료 <g …/> 는 자식을 갖지 않는다
            stack.append((t.start(), t.group(1), t.end()))
    return sorted(out)


def _svg_opaque_shapes_ordered(svg, viewbox):
    """채운 도형을 (bbox, 소스상 위치)로 돌려준다 — z-order 판정용.

    SVG는 소스 순서대로 덮어 그린다. 글자를 먼저 쓰고 채운 도형을 나중에 그리면
    글자는 화면에서 사라지는데, 좌표만 보는 검사는 '도형 안에 들어 있으니 정상'으로
    통과시킨다(_svg_filled_shapes의 contained 예외). 같은 지적이 3회 반복된 원인이다.
    반투명(fill-opacity<0.9) 도형은 밑이 비치므로 제외한다.
    """
    vx, vy, vw, vh = viewbox
    out = []

    def add(x0, y0, x1, y1, pos, attrs):
        if x0 <= vx and y0 <= vy and x1 >= vx + vw and y1 >= vy + vh:
            return                      # 배경판
        try:
            if float(_attr(attrs, "fill-opacity", "1")) < 0.9:
                return
        except ValueError:
            return
        out.append((x0, y0, x1, y1, pos))

    for m in re.finditer(r"<rect([^>]*?)/?>", svg):
        a = m.group(1)
        if (_attr(a, "fill") or "none") == "none":
            continue
        x, y = float(_attr(a, "x", "0")), float(_attr(a, "y", "0"))
        w, h = float(_attr(a, "width", "0")), float(_attr(a, "height", "0"))
        add(x, y, x + w, y + h, m.start(), a)
    for tag, rx_name, ry_name in (("circle", "r", "r"), ("ellipse", "rx", "ry")):
        for m in re.finditer(r"<" + tag + r"([^>]*?)/?>", svg):
            a = m.group(1)
            if (_attr(a, "fill") or "none") == "none":
                continue
            cx, cy = float(_attr(a, "cx", "0")), float(_attr(a, "cy", "0"))
            rx, ry = float(_attr(a, rx_name, "0")), float(_attr(a, ry_name, "0"))
            add(cx - rx, cy - ry, cx + rx, cy + ry, m.start(), a)
    for m in re.finditer(r"<path([^>]*?)/?>", svg):
        a = m.group(1)
        if (_attr(a, "fill") or "none") == "none":
            continue
        for subpath in (p for p in re.split(r"(?=[Mm])", _attr(a, "d", "")) if p.strip()):
            segments = _path_polyline(subpath)
            points = [(s[0], s[1]) for s in segments]
            points.extend((s[2], s[3]) for s in segments)
            if points:
                xs, ys = zip(*points)
                add(min(xs), min(ys), max(xs), max(ys), m.start(), a)
    return out

# ★★ **잘림은 「이 PC 의 글꼴」이 아니라 「가장 넓게 그리는 글꼴」로 재야 한다** (2026-08-12).
#
#   사용자: [사용자 발화 인용 생략]. 이 PC 에는
#   Pretendard 가 있어 검사도 렌더도 *안 잘린다* 고 답했는데, 그 폰트가 없는 기기에서는 잘린다.
#   실측(같은 브라우저에서 `font-family` 만 바꿔 그 삽화의 실제 마크업으로, viewBox 폭 700):
#       Pretendard 289.1 (여유 +21.2) · Noto Sans KR 306.8 (+12.3)
#       **Malgun Gothic 338.3 (−3.3)** · **Gulim 339.7 (−3.9)**  ← 윈도 기본, 실제로 잘린다
#   한글 advance 로 환산하면 Pretendard ≈ 0.83em, Malgun·Gulim ≈ **1.0em(전각)**.
#
#   ★ **겹침·라벨 여백은 이 값을 쓰지 않는다.** 그쪽은 *실제 화면에서 붙어 보이는가* 를 묻는
#     자라 이 PC 의 글꼴(0.887)이 맞고, 최악값으로 올리면 멀쩡한 삽화가 무더기로 신고된다.
#     **잘림만** 최악 기준이다 — 기기에 따라 글자가 사라지는 것은 되돌릴 수 없는 결함이라서다.
CJK_W_WORST = 1.0

# 글자 **상자**(잉크가 아니다)가 baseline 위·아래로 뻗는 양(em).
# ★ **새로 고른 수가 아니다 — `_text_bbox` 가 쓰던 값에 이름만 붙였다**(값 불변, 2026-08-25).
#   이름이 필요해진 이유: 겹침·F1·F4 가 전부 **이 상자**로 판정하는데, 라벨을 **놓는** 자
#   (`svg_dimension`)는 잉크 descent(`BOX_INK_DESCENT`)로 놓고 있었다. 두 자가 다른 것을 재니
#   «규격대로 놓았는데 빌드가 막는» 자리가 났다(가로 치수 라벨, F4). 놓는 자와 재는 자가
#   같은 상수를 봐야 그 갈라짐이 안 생긴다.
TEXT_BOX_ASCENT_RATIO = 0.78
# 아래쪽(디센더 자리). 잉크 descent(`BOX_INK_DESCENT` 0.03)보다 훨씬 크고, **그 차이가 곧
# 2026-08-25 결함의 크기**였다 — 놓는 자가 잉크로 재면 상자는 선 밑으로 내려간다.
TEXT_BOX_DESCENT_RATIO = 0.24


def _text_bbox(it, cjk_w=None):
    # ★ 폭을 재는 자는 **하나여야 한다** (2026-07-31). 조판 도구(`svg_math_line`)는
    #   `run_width` 로 재는데 여기서는 태그를 지운 글자를 100% 크기로 세고 있었다 —
    #   그래서 첨자가 붙은 라벨의 상자가 실제보다 넓게 잡혀, 도구가 규격대로 놓은 분수를
    #   '글자끼리 겹침'으로 신고했다(ch01 피스톤 캡션 실측). 같은 대상을 두 자로 재면 갈라진다.
    w = run_width(it.get("raw", it["s"]), it["fs"], it.get("mono", False), cjk_w)
    x0 = it["x"] - (w / 2 if it["anchor"] == "middle" else w if it["anchor"] == "end" else 0)
    return (x0, it["y"] - it["fs"] * TEXT_BOX_ASCENT_RATIO,
            x0 + w, it["y"] + it["fs"] * TEXT_BOX_DESCENT_RATIO)

def _bezier_points(p0, ctrls, steps):
    """de Casteljau — 2차·3차 모두 같은 코드로 편다. 순수 함수(테스트가 직접 부른다)."""
    out = []
    base = [p0] + list(ctrls)
    for k in range(1, steps + 1):
        t = k / float(steps)
        work = base
        while len(work) > 1:
            work = [((1 - t) * a[0] + t * b[0], (1 - t) * a[1] + t * b[1])
                    for a, b in zip(work, work[1:])]
        out.append(work[0])
    return out


def _bezier_steps(points):
    """제어 다각형 길이에 비례해 분할 수를 정한다 — 짧은 곡선을 과분할하지 않는다."""
    length = sum(_distance(points[i], points[i + 1]) for i in range(len(points) - 1))
    return max(4, min(24, int(length / 6.0) + 1))


def _path_polyline(dstr):
    """path의 d를 선분 목록으로 편다.

    ★ 곡선을 실제로 편다 (열린 날 2026-07-29, thermo-ch03 세션 보고).
      예전에는 `C/S/Q/T` 를 **시작점-끝점 직선(현)** 으로만 봤다. 볼록한 곡선일수록 오차가
      커져서 포화 돔에서는 **30~40px** 이 났고, 그 결과 ⑴ 곡선 위에 얹힌 라벨을 '멀리 있다'고
      읽어 F4가 침묵하고 ⑵ 반대로 곡선 밖 라벨을 '겹친다'고 신고했다.
      즉 곡선을 쓰는 삽화가 많은 챕터일수록 **기하 검사가 조용히 꺼졌다.**
      '빠뜨렸다'가 아니라 근사 오차가 검사 결과와 구별되지 않는 구조가 원인이다.

    남은 근사: `A`(호)는 여전히 현으로 본다. 이 리포의 SVG에 아직 A가 없어서
    지금 고치면 검증할 대상이 없다 — 쓰기 시작하면 그때 같은 방식으로 편다.
    """
    toks = re.findall(r"[MLHVZCSQTAmlhvzcsqta]|-?\d*\.?\d+(?:e-?\d+)?", dstr)
    segs, cur, start, i, cmd = [], None, None, 0, None
    prev_ctrl, prev_kind = None, None
    ARG_N = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                if cur and start and cur != start:
                    segs.append((cur[0], cur[1], start[0], start[1]))
                cur = start
            continue
        n = ARG_N.get(cmd.upper(), 2)
        args = [float(x) for x in toks[i:i + n]]
        if len(args) < n:
            break
        i += n
        rel = cmd.islower()
        cx, cy = cur or (0.0, 0.0)
        u = cmd.upper()
        if u in ("C", "S", "Q", "T"):
            pts = [((cx + args[j]) if rel else args[j],
                    (cy + args[j + 1]) if rel else args[j + 1])
                   for j in range(0, len(args), 2)]
            # S·T의 첫 제어점은 직전 곡선의 제어점을 현재 점에 대해 반사한 것이다.
            # 직전이 곡선이 아니면 현재 점 자신(SVG 스펙).
            reflected = (2 * cx - prev_ctrl[0], 2 * cy - prev_ctrl[1]) if prev_ctrl else (cx, cy)
            if u == "C":
                ctrls = pts
            elif u == "S":
                ctrls = [reflected if prev_kind in ("C", "S") else (cx, cy)] + pts
            elif u == "Q":
                ctrls = pts
            else:
                ctrls = [reflected if prev_kind in ("Q", "T") else (cx, cy)] + pts
            flat = _bezier_points((cx, cy), ctrls, _bezier_steps([(cx, cy)] + ctrls))
            if cur is not None:
                prev_pt = (cx, cy)
                for pt in flat:
                    segs.append((prev_pt[0], prev_pt[1], pt[0], pt[1]))
                    prev_pt = pt
            cur = flat[-1]
            prev_ctrl, prev_kind = ctrls[-2], u
            continue
        prev_ctrl, prev_kind = None, None
        if u == "H":
            nxt = (cx + args[0] if rel else args[0], cy)
        elif u == "V":
            nxt = (cx, cy + args[0] if rel else args[0])
        else:  # M L A — A(호)만 아직 끝점 직선 근사
            px, py = args[-2], args[-1]
            nxt = (cx + px, cy + py) if rel else (px, py)
        if u == "M":
            start = nxt
        elif cur is not None:
            segs.append((cx, cy, nxt[0], nxt[1]))
        cur = nxt
        if u == "M":
            cmd = "l" if rel else "L"  # M 뒤 잉여 좌표쌍은 L로 처리 (SVG 스펙)
    return segs

def _svg_segments(svg):
    segs = []
    # Stroke-only rectangles are common control-volume and system-boundary outlines.
    # They used to be omitted, so a label could straddle a vertical boundary unnoticed.
    for m in re.finditer(r"<rect([^>]*?)/?>", svg):
        a = m.group(1)
        # stroke는 조상 <g>에서 물려받을 수 있다 — 자기 속성만 보면 그런 상자가 통째로 안 보인다.
        if _effective(svg, m.start(), a, "stroke") in (None, "none"):
            continue
        x, y = float(_attr(a, "x", "0")), float(_attr(a, "y", "0"))
        w, h = float(_attr(a, "width", "0")), float(_attr(a, "height", "0"))
        segs.extend(((x, y, x + w, y), (x + w, y, x + w, y + h),
                     (x + w, y + h, x, y + h), (x, y + h, x, y)))
    for m in re.finditer(r"<line([^>]*?)/?>", svg):
        a = m.group(1)
        segs.append(tuple(float(_attr(a, k, "0")) for k in ("x1", "y1", "x2", "y2")))
    for m in re.finditer(r"<path([^>]*?)/?>", svg):
        dstr = _attr(m.group(1), "d")
        if dstr:
            segs.extend(_path_polyline(dstr))
    return segs

def _svg_filled_shapes(svg, viewbox):
    vx, vy, vw, vh = viewbox
    shapes = []

    def add_rect(x0, y0, x1, y1):
        # viewBox 전체를 덮는 배경판은 텍스트와의 경계 교차 대상이 아니다.
        if x0 <= vx and y0 <= vy and x1 >= vx + vw and y1 >= vy + vh:
            return
        shapes.append((x0, y0, x1, y1))

    # fill도 조상 <g>에서 물려받는다 — `<g fill='…'><path …/></g>` 로 그린 화살촉이
    # '채운 도형'으로 안 보여 z-order·halo 판정 밖에 있었다(2026-07-30).
    for m in re.finditer(r"<rect([^>]*?)/?>", svg):
        a = m.group(1)
        fill = _effective(svg, m.start(), a, "fill")
        if fill is None or fill == "none":
            continue
        x, y = float(_attr(a, "x", "0")), float(_attr(a, "y", "0"))
        w, h = float(_attr(a, "width", "0")), float(_attr(a, "height", "0"))
        add_rect(x, y, x + w, y + h)
    for tag, rx_name, ry_name in (("circle", "r", "r"), ("ellipse", "rx", "ry")):
        for m in re.finditer(r"<" + tag + r"([^>]*?)/?>", svg):
            a = m.group(1)
            fill = _effective(svg, m.start(), a, "fill")
            if fill is None or fill == "none":
                continue
            # ★ 시간율의 점(`class='rate-dot'`)은 **글자의 일부**이지 도형이 아니다
            #   (열린 날 2026-08-12). 삽화에서도 뷰어처럼 점을 그리기로 하자마자,
            #   그 점이 자기가 얹힌 글자에 대해 [사용자 발화 인용 생략] 을 6건 냈다.
            #   `<g class='frac'>` 의 분수선이 자기 분자·분모에게 '선'이 아닌 것과 같은 자리다 —
            #   **태깅이 없으면 정상 조판이 전부 위반으로 신고된다.**
            if "rate-dot" in _attr(a, "class", ""):
                continue
            cx, cy = float(_attr(a, "cx", "0")), float(_attr(a, "cy", "0"))
            rx, ry = float(_attr(a, rx_name, "0")), float(_attr(a, ry_name, "0"))
            add_rect(cx - rx, cy - ry, cx + rx, cy + ry)
    for m in re.finditer(r"<path([^>]*?)/?>", svg):
        a = m.group(1)
        fill, dstr = _effective(svg, m.start(), a, "fill"), _attr(a, "d")
        if fill is None or fill == "none" or not dstr:
            continue
        for subpath in (p for p in re.split(r"(?=[Mm])", dstr) if p.strip()):
            segments = _path_polyline(subpath)
            points = [(s[0], s[1]) for s in segments]
            points.extend((s[2], s[3]) for s in segments)
            if points:
                xs, ys = zip(*points)
                add_rect(min(xs), min(ys), max(xs), max(ys))
    return shapes

def _seg_x_seg(a, b):
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])
    p1, p2, p3, p4 = (a[0], a[1]), (a[2], a[3]), (b[0], b[1]), (b[2], b[3])
    d1, d2 = ccw(p3, p4, p1), ccw(p3, p4, p2)
    d3, d4 = ccw(p1, p2, p3), ccw(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

def _seg_x_rect(seg, r):
    x0, y0, x1, y1 = r
    if x0 <= seg[0] <= x1 and y0 <= seg[1] <= y1:
        return True
    if x0 <= seg[2] <= x1 and y0 <= seg[3] <= y1:
        return True
    edges = [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]
    return any(_seg_x_seg(seg, e) for e in edges)

def _rect_x_rect(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

def _point_to_segment_distance(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    denom = dx * dx + dy * dy
    if not denom:
        return _distance((px, py), (x1, y1))
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / denom))
    return _distance((px, py), (x1 + t * dx, y1 + t * dy))

def _segment_to_rect_distance(seg, rect):
    if _seg_x_rect(seg, rect):
        return 0.0
    x0, y0, x1, y1 = rect
    return min(_point_to_segment_distance(px, py, *seg)
               for px, py in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)))

def _numeric_unit_labels(texts):
    pattern = r"\b\d+(?:\.\d+)?\s*(?:Pa|kPa|MPa|J|kJ|W|kW|m|cm|mm|m³|m/s|m/s²|°C)\b"
    return [t["s"] for t in texts if re.search(pattern, t["s"])]


def iso_cuboid(x, y, width, depth, height):
    """Reusable isometric cuboid faces (top, front, side) as SVG path data."""
    dx, dy = depth, -depth * 0.58
    top = f"M{x} {y} L{x + width} {y} L{x + width + dx} {y + dy} L{x + dx} {y + dy} Z"
    front = f"M{x} {y} L{x + width} {y} L{x + width} {y + height} L{x} {y + height} Z"
    side = (f"M{x + width} {y} L{x + width + dx} {y + dy} "
            f"L{x + width + dx} {y + height + dy} L{x + width} {y + height} Z")
    return {"top": top, "front": front, "side": side}


def iso_ellipse(cx, cy, rx, ry):
    """Reusable SVG ellipse attributes for a section normal to an isometric axis."""
    return {"cx": cx, "cy": cy, "rx": rx, "ry": ry}


# ★ 삽화 안의 분수를 조판하는 **공용 프리미티브** (신설 2026-07-30 — 검사 C9 와 한 쌍).
#
# 왜 도구로 만드나: 분수를 텍스트(`P/ρ`)로 쓰는 부류가 세 번 재발했고, 그 세 번 모두
# "고쳐라"는 알았지만 **어떻게 그리는지가 매번 새로 정해졌다.** 손으로 그리면 삽화마다
# 분수선 굵기·간격·중심선이 갈라지고, 그 갈라짐이 다음 지적("분수선과 등호가 같은 선상에
# 없어" — 인박스 2026-07-28)의 정체다. 좌표를 손으로 잡는 한 그 부류는 계속 돌아온다.
#
# 기하 결정과 근거:
#   · **분수선 y = 수식의 중심선(math axis)** — 인라인으로 쓸 때 등호와 같은 높이가 된다.
#   · 분자 baseline = 축 − 0.36em, 분모 baseline = 축 + 0.90em. 이 값은
#     `_text_bbox` 의 근사(위 0.78em · 아래 0.24em)로 잰 **글자 상자가 분수선에서
#     위아래 0.12em씩 떨어지도록** 역산한 것이다 — 겹치면 빌드의 글자·선 교차 검사에 걸린다.
#     그래서 상자 전체가 축을 기준으로 정확히 대칭(±1.14em)이 되고, 칸 가운데에 두면 가운데다.
#   · 분수선 길이 = max(분자, 분모) + 0.30em × 2. 굵기는 0.09em(하한 1.2) —
#     형상선(2~2.5)보다 가늘고 치수선 규격(≤1.5)과 겹치지만, 양 끝에 **틱이 없어서**
#     C7(치수선 태깅 누락)에는 걸리지 않는다. 30px 미만이면 치수 본선 후보도 아니다.
# ★★ 분자·분모 baseline 도 **산문 렌더러 실측값**이다 (2026-08-02, 사용자 3회차 지적).
#
#   사용자: [사용자 발화 인용 생략]
#
#   실측(브라우저 probe, 산문 `.frac` fs 15.5) — 분자 baseline 이 분수선 위로 **0.407em**,
#   분모 baseline 이 아래로 **1.065em**. 옛 삽화 값은 0.36 / 0.90 이었고, 이게 **눈에 보이는
#   비대칭**을 만들었다:
#       분자 쪽 틈 = 0.36em (V² 는 내림이 없어 baseline 이 곧 글자 아랫변)
#       분모 쪽 틈 = 0.90 − 0.70(대문자 높이) = **0.20em**
#   즉 **위가 아래의 1.8배**. 산문은 0.407 / (1.065−0.70)=0.365 로 **거의 대칭**이라 안 거슬린다.
#   → 두 값을 산문 실측치로 바꾼다. 분자 쪽을 그냥 줄이면 안 된다 — `ρ` 처럼 **내림이 있는 분자**가
#     분수선을 뚫는다(그게 옛 0.36 이 넉넉했던 이유다). 산문 값은 그 여유를 이미 품고 있다.
#   ★ **두 조건이 충돌한다 — 사용자가 골랐다(2026-08-02).**
#     ⑴ *칸 한가운데에 두면 가운데로 보인다* → 상자 축 대칭 → `DEN = NUM + 0.54`
#        (빌드 bbox 근사 ascent 0.78 / descent 0.24)
#     ⑵ *보이는 위·아래 틈이 같다* → `DEN = NUM + 0.71` (숫자 높이 실측)
#     동시에 성립하지 않는다. **사용자 판정: ⑵(보이는 여백 대칭).**
#     대가는 칸 가운데 정렬 시 0.085em 위로 치우치는 것이고, 분수를 칸에 넣는 삽화는 소수다.
#
#   값의 근거 — 산문 실측 위 0.407 / 아래 0.365 의 평균 **0.386** 을 양쪽에 같게 준다.
#   내림이 있는 분자(`ρ`, descent 0.23)도 0.386 − 0.23 = 0.156em 이 남아 분수선을 뚫지 않는다.
FRACTION_NUM_BASE = 0.386                        # 분자 baseline 이 축 위로 (em)
FRACTION_DEN_BASE = 0.386 + 0.71                 # = 1.096. 숫자 높이 0.71 만큼 더 내려야 틈이 같다
# ★★ 아래 세 값은 **산문 렌더러(`.frac`·`.frac-num`)를 브라우저에서 실측한 값**이다
#     (열린 날 2026-08-02, 사용자: [사용자 발화 인용 생략]).
#
#   ★ **맞춰야 할 자가 옆에 있었다.** 2026-08-01 에는 `RELATION_GAP = 0.28`(TeX thickmuskip)을
#     근거로 여백을 **넓혔는데**, 정작 사용자가 [사용자 발화 인용 생략] 고 한 것은 TeX 이 아니라
#     **이 뷰어의 산문 렌더러**였다. 같은 화면에 나란히 보이는 그것을 재면 됐다.
#
#   ★ 그리고 방향이 반대였다. 실측(fs 15.5) 대조 —
#       분수선 좌우 나옴  산문 **0.194em** vs 삽화 0.30em  (1.55배)
#       분수선 굵기      산문 **0.065em** vs 삽화 0.09em  (1.38배)
#       분수 양옆 여백    산문 **0.129em** vs 삽화 0.28em  (2.2배)
#     즉 `=` 에서 분자 글자까지 **산문 0.32em vs 삽화 0.58em** — 삽화가 거의 두 배였다.
#     인박스 R-8 은 [사용자 발화 인용 생략] 로 읽었지만 답답함의 원인은 **폰트 크기**(실효 15.9px)였고,
#     그건 따로 고쳤다. 여백은 건드리지 말았어야 했다.
#
#   ★ 관계/이항 구분도 없앴다 — **산문 렌더러에는 그 구분이 없다**(`margin:0 2px` 하나뿐).
#     기준이 산문이면 규칙도 산문의 것이어야 한다. TeX 규칙을 절반만 흉내 내면 둘 다 아니게 된다.
FRACTION_SIDE_PAD = 0.194    # 분수선이 글자보다 좌우로 더 나오는 양 (em) — 산문 실측
FRACTION_BAR_MIN = 1.0       # 분수선 굵기 하한 (px)
# ★ 분수선의 세로 위치 — **산문과 같은 자리**로 내렸다 (2026-08-02, 사용자 판정 "삽화를 고쳐라").
#
# ★★ **고쳐 놓고도 어긋나 있었다 — 상수를 「남의 글꼴」로 계산했기 때문이다** (2026-08-07 재측정).
#   사용자: [사용자 발화 인용 생략] **맞는 지적이었다.**
#
#   2026-08-02 의 계산은 `=` 잉크가 baseline 위 **0.17~0.52em**(중심 0.345)이라는 값을 썼는데,
#   그건 **산문이 쓰는 글꼴(Cascadia Code)** 의 값이다. 삽화는 아래 `MATH_FONT` 가 스택을
#   줄여 놓아 **Consolas** 로 그려졌고, 그 글꼴의 `=` 잉크는 **0.14~0.40em**(중심 0.27)이다.
#   → 분수선 baseline−0.124em 은 `=` 잉크의 **아래쪽 획보다도 더 아래**(0.14 < 0.124 아님에
#   주의: 0.124 < 0.14) 로 떨어져, 글자 하나만큼 밑에 있는 것처럼 보인다.
#
#   ☞ **글꼴을 산문과 같게 맞추고(아래) 값을 산문 실측 그대로 쓴다.** 브라우저 실측
#   (`.fmath` 19px, 2026-08-07): 분수선 = baseline − **0.2417em**, 이때 `=` 중심보다
#   **0.103em 아래**. 새 글꼴의 `=` 잉크는 0.17~0.52em 이므로 이 값이 산문을 그대로 재현한다.
FRACTION_AXIS = 0.242        # 보통 글자 baseline 에서 수식 중심선까지 (em) — 산문 실측
# ★ 수식 글꼴 — **산문 수식과 같은 등폭 글꼴을 쓴다** (2026-08-02, 사용자 지적:
#   [사용자 발화 인용 생략]).
#
# ★★ **그때 스택을 줄인 것이 이 부류의 뿌리였다** (2026-08-07). 옛 주석은 [사용자 발화 인용 생략] 고 적어 두었는데,
#   ⑴ **작은따옴표로 감싼 속성 안의 큰따옴표는 XML 에서 정상**이라 그 걱정은 근거가 없었고
#   ⑵ 이름을 빼자 **Windows 에서 산문은 Cascadia Code, 삽화는 Consolas** 로 갈렸다.
#   실측 차이(2026-08-07): advance 0.586 vs 0.550 · `=` 잉크 0.17~0.52 vs 0.14~0.40.
#   즉 [사용자 발화 인용 생략] 고 선언해 놓고 두 글꼴을 쓰고 있었고, 그 위에서 계산한 상수가
#   전부 한쪽 글꼴 기준이 됐다(위 `FRACTION_AXIS` · 아래 `MONO_W`).
#
#   ☞ **뷰어 CSS 의 선언을 글자 그대로 옮긴다.** 특정 글꼴 이름을 고르는 것이 아니라
#     *스택을 같게* 하는 것이 핵심이다 — 그래야 어느 기계에서 무엇으로 해석되든 산문과 삽화가
#     **함께** 같은 글꼴로 떨어진다. 갈라짐은 `test_math_font_matches_the_prose_stack` 이 막는다
#     (뷰어 템플릿을 직접 읽어 대조한다 — 손으로 베낀 문자열은 반드시 언젠가 갈라진다).
MATH_FONT = 'ui-monospace,"SF Mono","Cascadia Code",Consolas,"Liberation Mono",monospace'
# 한 줄 수식에서 분수 **양옆**에 두는 여백 (em) — 산문의 `.frac{margin:0 2px}` 실측값.
# 0 으로 두면 분수선이 이웃 글자 상자에 맞닿아 '글자가 선과 교차' 검사에 걸린다
# (2026-07-31 실측: ch01 피스톤 캡션에서 정확히 0px 로 닿았다).
FRACTION_SIDE_GAP = 0.129


def _fmt(v):
    """좌표를 SVG 문자열로 — 소수 2자리, 꼬리 0 제거."""
    s = "%.2f" % float(v)
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def run_width(text, fs, mono=False, cjk_w=None):
    """글자 열의 대략 폭. 빌드의 bbox 검사와 **같은 근사자**를 쓴다(둘이 갈라지면 안 된다).

    ★ `mono` — 이 글자들이 **`MATH_FONT` 로 그려지는가**. 조판 단위(분수·한 줄 수식)는
      등폭이라 자가 다르다. 넘기지 않으면 한글·공백이 든 줄이 통째로 어긋난다
      (경위는 `_char_w` 위 주석이 정본, 열린 날 2026-08-07).

    `<tspan>` 아래첨자가 섞여 있어도 **보이는 글자만** 잰다 — 태그 글자까지 세면
    첨자가 붙은 항의 폭이 두 배 넘게 부풀어 조판이 통째로 어긋난다.

    ★ `font-size='78%'` 같은 **비율 크기도 반영한다** (2026-07-31, 렌더 검수에서 발견).
      첨자를 100%로 세면 `P_gas·A = P_atm·A + mg → …` 같은 줄이 실제보다 **40px 넓게**
      잡히고, 그만큼 뒤따르는 분수가 오른쪽으로 밀려 빈칸이 뜬다(ch01 피스톤 캡션 실측).
    """
    total, scale, stack = 0.0, 1.0, []
    for m in re.finditer(r"<[^>]+>|[^<]+", text):
        token = m.group(0)
        if not token.startswith("<"):
            # 엔티티는 **한 글자**다 — `&gt;` 를 네 글자로 세면 상자가 그만큼 넓어져
            # 도형 경계 검사가 오탐을 낸다(ch05 `V₂ &gt; V₁` 실측).
            plain = token.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            # ★ **수치 문자 참조도 한 글자다** (열린 날 2026-08-24, ee ch04).
            #   이름 엔티티 셋만 풀던 자리다. `&#8722;`(−) 가 8글자로 세어져 상자가
            #   74.5px(같은 자리 `+` 는 11.4px)이 됐고, 판에서 30px 뗀 부호가 「도형 경계에
            #   걸침」으로 신고됐다. 좌표로 피하려다 **전하를 판 바깥에 그린** 틀린 삽화가 났다.
            plain = re.sub(r"&#(\d+);", lambda mm: chr(int(mm.group(1))), plain)
            plain = re.sub(r"&#[xX]([0-9a-fA-F]+);",
                           lambda mm: chr(int(mm.group(1), 16)), plain)
            total += sum(_char_w(c, fs * scale, mono, cjk_w) for c in plain)
        elif token.startswith("</"):
            scale = stack.pop() if stack else 1.0
        elif not token.endswith("/>"):
            stack.append(scale)
            pct = re.search(r"font-size='(\d+(?:\.\d+)?)%'", token)
            if pct:
                scale = float(pct.group(1)) / 100.0
    return total


# ★★ 유니코드 위첨자(`²`)를 **산문 `<sup>` 과 같은 조판**으로 바꾼다 (열린 날 2026-08-02).
#
#   사용자: [사용자 발화 인용 생략] — **맞았다.**
#   실측(등폭 글꼴, canvas TextMetrics):
#       유니코드 `²` 글리프 높이 **0.40em**  vs  산문 `<sup>` 실효 높이 0.65×0.833 = **0.541em**
#       → 삽화 제곱이 **26% 작다.** `V` 자체는 0.64em 로 같은데 제곱만 작아
#         `V²` 덩어리 전체가 작아 보인다.
#   산문 `<sup>` 실측: 크기 **0.833배**, baseline 위로 **0.40em**(부모 기준).
#
#   ★ 되돌림 tspan 을 **비워 두면 안 된다** — 브라우저는 글리프가 없는 tspan 의 dy 를 적용하지
#     않아 뒤따르는 글자가 올라간 채로 남는다(빌드 C11 이 아래첨자 쪽에서 이미 겪은 함정이다).
#     그래서 위첨자 뒤에 글자가 있으면 **그 글자들을 되돌림 tspan 안에** 넣는다.
SUPERSCRIPT_RATIO = 0.83     # 산문 <sup> 실측 12.5/15
SUPERSCRIPT_RISE = 0.40      # 산문 <sup> 의 baseline 상승 (부모 em)
_SUPERSCRIPT_CHARS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5",
                      "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁺": "+", "⁻": "−",
                      "ⁿ": "n", "ⁱ": "i"}
_SUP_RUN = re.compile("[" + "".join(_SUPERSCRIPT_CHARS) + "]+")


def expand_superscripts(text, fs):
    """유니코드 위첨자를 산문과 같은 크기·높이의 tspan 으로 편다. 순수 함수(테스트가 부른다)."""
    rise = SUPERSCRIPT_RISE * fs
    pct = _fmt(SUPERSCRIPT_RATIO * 100) + "%"

    def walk(chunk):
        m = _SUP_RUN.search(chunk)
        if not m:
            return chunk
        body = "".join(_SUPERSCRIPT_CHARS[c] for c in m.group(0))
        out = (chunk[:m.start()] + "<tspan dy='" + _fmt(-rise) + "' font-size='" + pct
               + "'>" + body + "</tspan>")
        tail = chunk[m.end():]
        if tail:                       # 뒤 글자를 되돌림 tspan **안에** 넣는다(C11 의 교훈)
            out += "<tspan dy='" + _fmt(rise) + "'>" + walk(tail) + "</tspan>"
        return out

    # 이미 들어 있는 태그 안은 건드리지 않는다.
    return "".join(tok if tok.startswith("<") else walk(tok)
                   for tok in re.findall(r"<[^>]+>|[^<]+", text))


def svg_fraction(cx, axis_y, num, den, fs, fill="#2c3a44", weight=None):
    """가운데 정렬된 분수 한 덩어리를 (svg, 폭) 으로 돌려준다. 순수 함수 — 테스트가 부른다.

    `axis_y` 는 **분수선의 y**(수식 중심선)다. 칸 한가운데에 두려면 칸의 세로 중심을 준다.
    """
    # 위첨자를 먼저 편다 — **폭도 편 뒤에 재야 한다**(83% tspan 이라 그냥 세면 넓게 잡힌다).
    num, den = expand_superscripts(num, fs), expand_superscripts(den, fs)
    inner = max(run_width(num, fs, True), run_width(den, fs, True))   # 찍는 글꼴이 등폭이다
    width = inner + 2 * FRACTION_SIDE_PAD * fs
    bar = max(FRACTION_BAR_MIN, fs * 0.065)   # 0.065em = 산문 `.frac-num` 테두리 실측
    common = (" font-family='" + MATH_FONT + "' font-size='" + _fmt(fs)
              + "' text-anchor='middle' fill='" + fill + "'")
    if weight:
        common += " font-weight='" + str(weight) + "'"
    # ★ `<g class='frac'>` 로 묶는 이유 — **분수선은 라벨 여백 검사(F1)의 '선'이 아니다.**
    #   분자·분모는 분수선에서 0.12em 떨어지는 것이 정상인데, F1 은 글자와 선 사이 0.5em 을
    #   요구한다. 태깅이 없으면 우리가 만든 분수가 전부 F1 위반이 되고, 그 상태로 검사를
    #   느슨하게 만들면 진짜 겹침(4회 지적된 부류)이 함께 풀린다. 그래서 **면제 대상을
    #   자기 그룹 안으로 한정**한다 — 남의 라벨이 이 분수선에 붙는 것은 그대로 걸린다.
    svg = ("<g class='frac'>"
           + "<text x='" + _fmt(cx) + "' y='" + _fmt(axis_y - FRACTION_NUM_BASE * fs) + "'"
           + common + ">" + num + "</text>"
           + "<line x1='" + _fmt(cx - width / 2) + "' y1='" + _fmt(axis_y) + "' x2='"
           + _fmt(cx + width / 2) + "' y2='" + _fmt(axis_y) + "' stroke='" + fill
           + "' stroke-width='" + _fmt(bar) + "' stroke-linecap='butt'/>"
           + "<text x='" + _fmt(cx) + "' y='" + _fmt(axis_y + FRACTION_DEN_BASE * fs) + "'"
           + common + ">" + den + "</text></g>")
    return svg, width


def fraction_unit_boxes(svg):
    """분수 한 덩어리가 차지하는 상자 — ((그룹 범위), bbox) 목록. 순수 함수(테스트가 부른다).

    **조판 단위는 글자 하나가 아니라 분수 전체다.** 칸 안에 든 라벨의 여유를 잴 때
    분자 상자만으로 재면 "아직 24px 여유가 있다"가 나오지만, 실제로 움직일 수 있는 폭은
    분자+분수선+분모를 합친 높이가 결정한다(2026-07-30 ch05 실측: 24.6 vs 10.3).
    중첩된 그룹은 **바깥쪽**을 쓴다 — 한 줄 수식은 줄 전체가 함께 움직인다.
    """
    spans = sorted(_tagged_group_spans(svg, ("frac",)), key=lambda s: s[0])
    outer = []
    for start, end, _body in spans:
        if any(s <= start and end <= e for s, e in outer):
            continue
        outer.append((start, end))
    texts = _svg_texts(svg)
    out = []
    for start, end in outer:
        boxes = [_text_bbox(t) for t in texts if start <= t["pos"] < end]
        if boxes:
            out.append(((start, end), (min(b[0] for b in boxes), min(b[1] for b in boxes),
                                       max(b[2] for b in boxes), max(b[3] for b in boxes))))
    return out


def _fraction_bars(svg):
    """`<g class='frac'>` 안의 분수선 — (그룹 범위, 선 좌표). 순수 함수(테스트가 부른다).

    F1(라벨↔선 0.5em) 면제를 **자기 그룹 안으로만** 한정하기 위한 것이다.
    """
    out = []
    for start, end, body in _tagged_group_spans(svg, ("frac",)):
        for m in re.finditer(r"<line([^>]*?)/?>", body):
            a = m.group(1)
            out.append(((start, end),
                        tuple(float(_attr(a, k, "0")) for k in ("x1", "y1", "x2", "y2"))))
    return out


# 분자·분모 안에 `<tspan>` 이 들어올 수 있다 — 태그의 닫는 슬래시(`</tspan>`)를 구분자로
# 오해하면 첨자가 붙은 항이 통째로 마커에서 빠진다(실측: ch05 유입·유출 라벨).
_FRACTION_MARK = re.compile(r"\{((?:<[^>]*>|[^{}/])*)/((?:<[^>]*>|[^{}/])*)\}")


def svg_math_line(x, y, expr, fs, fill="#2c3a44", weight=None, anchor="middle"):
    """`{분자/분모}` 마커가 든 **한 줄 수식**을 조판한다 — `"θ = h + {V²/2} + gz"`.

    `y` 는 보통 글자의 baseline이고, 분수선은 그보다 0.34em 위(수식 중심선)에 놓인다.
    조각별 폭을 `run_width` 로 재서 이어 붙이므로 **글자 폭을 눈으로 재서 x를 정하는 일**이
    없어진다(AGENTS 「축 제목의 x는 눈으로 재지 말 것」과 같은 이유).
    순수 함수 — 테스트가 직접 부른다.
    """
    tokens, pos = [], 0
    for m in _FRACTION_MARK.finditer(expr):
        if m.start() > pos:
            tokens.append(("t", expr[pos:m.start()], ""))
        tokens.append(("f", m.group(1), m.group(2)))
        pos = m.end()
    if pos < len(expr):
        tokens.append(("t", expr[pos:], ""))

    # 분수 **밖**의 위첨자도 같은 조판으로 편다(`ke = V² + …`). 폭을 재기 **전에** 펴야
    # 83% tspan 이 반영된다 — 나중에 펴면 폭만 옛 값으로 남아 조각이 어긋난다.
    tokens = [(k, expand_superscripts(a, fs) if k == "t" else a, b) for k, a, b in tokens]
    has_frac = any(k == "f" for k, _a, _b in tokens)
    # 분수 양옆 여백은 **좌우 같다** — 산문 렌더러가 `margin:0 2px` 하나만 쓰기 때문이다
    # (2026-08-02, 관계/이항 구분을 없앴다. 경위는 FRACTION_SIDE_GAP 위 주석이 정본).
    widths = []
    for kind, a, b in tokens:
        widths.append(run_width(a, fs, True) if kind == "t"
                      else svg_fraction(0, 0, a, b, fs)[1] + 2 * FRACTION_SIDE_GAP * fs)
    total = sum(widths)
    left = {"middle": x - total / 2, "end": x - total, "start": x}[anchor]

    out, cur = [], left
    for i, ((kind, a, b), w) in enumerate(zip(tokens, widths)):
        if kind == "t":
            # ★ 분수 **바로 앞** 조각은 오른쪽 끝을 앵커로 잡는다 (2026-07-31 렌더 검수).
            #   폭 추정은 어차피 근사라 왼쪽부터 이어 붙이면 오차가 **분수 앞의 빈칸**으로 쌓인다
            #   (ch01 피스톤 캡션 실측 40px). 끝을 앵커로 잡으면 오차가 줄 전체의 미세한
            #   이동으로만 남고 조각 사이 간격은 항상 `FRACTION_SIDE_GAP` 로 일정해진다.
            after_frac = i > 0 and tokens[i - 1][0] == "f"
            # ★ `<tspan>` 이 든 조각은 끝 앵커를 쓰지 않는다 (2026-07-31 렌더 검수에서 확정).
            #   검수용 래스터(fitz)가 `text-anchor='end'` 의 기준 폭을 **부모 text 의 글자만으로**
            #   재서 tspan 몫이 빠지고, 그만큼 조각이 오른쪽으로 밀려 **글자가 서로 겹쳐 찍힌다**
            #   (ch01 피스톤 캡션에서 실제로 그렇게 나왔다). 브라우저는 다르게 그릴 수 있지만
            #   **확인할 수 없는 조판을 내보내지 않는다** — 그 경우 왼쪽 앵커 + 추정 폭으로 간다.
            before_frac = (i + 1 < len(tokens) and tokens[i + 1][0] == "f"
                           and "<tspan" not in a)
            # ★★ 분수 앞뒤의 **공백을 먹지 않는다** (열린 날 2026-08-02, 사용자 지적:
            #   [사용자 발화 인용 생략]).
            #
            #   SVG 는 글자 앞뒤 공백을 지우므로 공백 폭만큼 x 를 밀어 줘야 하는데,
            #   ⑴ 분수 **뒤** 조각은 `lead = 0.0` 으로 **앞 공백을 통째로 버렸고**
            #   ⑵ 분수 **앞** 조각은 오른쪽 끝 앵커를 `cur + w`(끝 공백 포함)에 두어
            #      **끝 공백만큼 글자를 오른쪽으로 밀어** 분수에 붙여 버렸다.
            #   그래서 `=` 잉크에서 분자 잉크까지가 산문 0.909em 대비 **0.323em** 이었다(2.8배 좁음).
            #   공백은 조판의 일부다 — `FRACTION_SIDE_GAP` 은 공백에 **더해지는** 값이지
            #   공백을 대신하는 값이 아니다.
            # ★ 양끝 공백은 **태그를 지운 글자**에서 잰다 (2026-08-07). SVG 렌더러는
            #   `<tspan dy='-2.5'> + </tspan>` 의 끝 공백도 지우는데, 날 문자열에 `lstrip`
            #   을 걸면 `</tspan>` 때문에 0 이 나와 그 공백이 조판에서 사라진다.
            plain = re.sub(r"<[^>]+>", "", a)
            lead = run_width(plain[:len(plain) - len(plain.lstrip())], fs, True)
            trail = run_width(plain[len(plain.rstrip()):], fs, True)
            text = a.strip()
            if text:
                side = "end" if before_frac else "start"
                at = cur + w - trail if before_frac else cur + lead
                attrs = (" font-family='" + MATH_FONT + "' font-size='" + _fmt(fs)
                         + "' text-anchor='" + side + "' fill='" + fill + "'")
                if weight:
                    attrs += " font-weight='" + str(weight) + "'"
                out.append("<text x='" + _fmt(at) + "' y='" + _fmt(y) + "'"
                           + attrs + ">" + text + "</text>")
        else:
            # 좌우 여백이 같으므로 조각 폭의 한가운데가 곧 분수의 중심이다.
            frag, _fw = svg_fraction(cur + w / 2, y - FRACTION_AXIS * fs,
                                     a, b, fs, fill, weight)
            out.append(frag)
        cur += w
    body = "".join(out)
    # 한 줄 전체를 `frac` 으로 묶는다 — 분수선 옆에 나란히 선 항(`θ = h +`)은 분수선에서
    # 0.5em 남짓 떨어지는 것이 정상 조판인데, 묶지 않으면 라벨 여백 자를 그대로 맞고 만다.
    # 면제 범위는 여전히 **이 그룹 안**이라, 바깥 라벨이 이 분수선에 붙는 것은 그대로 걸린다.
    #
    # ★ 분수가 없으면 `mathline` 로 묶는다 (2026-08-05, 부류31). 등폭은 **조판 단위**의
    #   글꼴이므로 C20 은 그룹 밖의 등폭을 전부 신고하는데, 분수 없는 줄을 안 묶으면
    #   *생성기가 찍은 것을 검사가 신고*하게 된다(자를 둘로 둔 것과 같다).
    #   `frac` 을 쓰지 않는 이유: 그 이름은 「분자 2 + 분수선 1」 규격 대조를 부르고,
    #   분수선이 없는 줄은 거기서 '구성이 규격과 다르다'로 걸린다. 이름이 곧 계약이다.
    return ("<g class='frac'>" if has_frac else "<g class='mathline'>") + body + "</g>"


# ★★ 삽화 수식이 **지금 규격과 어긋난 자리** (열린 날 2026-08-02, 동역학 ch12).
#
#   사용자: [사용자 발화 인용 생략] — 같은 부류가 다른 과목에서 그대로 나왔다.
#
#   **원인은 빠뜨림이 아니라 「생성기만 고치고 자를 안 만든 것」이다.** 2026-08-02 에 위
#   `svg_fraction`·`svg_math_line` 이 글꼴(등폭)·분수선 굵기·중심선·위첨자 조판을 산문에 맞춰
#   전부 바뀌었는데, 생성기를 고치는 것은 **앞으로 찍을 것**만 고친다. 이미 데이터에 박힌 조각은
#   아무도 다시 보지 않으므로, 규격이 바뀔 때마다 옛 삽화가 조용히 뒤처진다
#   (열역학이 그 자리에서 `잔여 6곳` 을 남겼다 — 인스턴스를 세었을 뿐 자를 만들지 않았다).
#
#   그래서 **지금 생성기가 찍을 값과 데이터를 직접 대조**한다. 규격을 또 고치면 이 검사가
#   뒤처진 삽화를 자동으로 지목한다 — 상수를 베끼지 않고 위 정의를 그대로 쓰는 것이 핵심이다.
_FRAC_TEXT_RE = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)
_FRAC_LINE_RE = re.compile(r"<line\b([^>]*?)/?>")
_SUP_GLYPHS = "".join(_SUPERSCRIPT_CHARS)


def _leaf_frac_groups(svg):
    """분수 **한 덩어리**(안에 다른 분수를 품지 않은 `frac` 그룹) — 한 줄 수식의 겉그룹은 뺀다."""
    spans = _tagged_group_spans(svg, ("frac",))
    return [(s, e, b) for s, e, b in spans
            if not any(s < s2 and e2 <= e for s2, e2, _b2 in spans)]


MATH_GROUP_MARKS = ("frac", "mathline")


def _standalone_texts(svg):
    """조판 그룹 **밖**의 `<text>` — (시작, 여는 태그 끝, 선언한 글꼴, 보이는 글자).

    C20 의 판정과 교정 도구(`tools/fix_figure_math_font.py`)가 **같은 자**를 쓰게 하려고
    필터를 여기 한 곳에 둔다. 각자 판정하면 갈라진다 — `run_width` 를 둘로 두었다가
    조판 도구가 규격대로 놓은 분수를 검사가 '겹침'으로 신고했던 것과 같은 부류다.
    """
    frac_spans = [(s, e) for s, e, _b in _tagged_group_spans(svg, MATH_GROUP_MARKS)]
    out = []
    for m in _FRAC_TEXT_RE.finditer(svg):
        if any(s <= m.start() < e for s, e in frac_spans):
            continue                      # 조판 그룹 안쪽은 따로 본다
        attrs = m.group(1)
        inner = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not inner:
            continue
        out.append((m.start(), m.start() + len(attrs) + len("<text") + 1,
                    _attr(attrs, "font-family", ""), inner))
    return out


# ★★ **낱개 라벨은 삽화 자신의 글꼴을 따른다** — 자를 좁힌 날 2026-08-05 (부류31, 열역학 ch02).
#
#   사용자: [사용자 발화 인용 생략] → **맞는 지적이라 되돌렸다.**
#
#   **무엇이 틀렸나.** 이 자리의 옛 자는 *관계 기호(`=≈≠≤≥∫∑→`)가 든 모든 `<text>`* 를 '식'으로
#   보고 산문 수식 글꼴(등폭)로 올리라고 신고했다(열역학 전 챕터 89건). 그런데 R-16 을 연
#   지적은 **분수 조판**(`P/ρ`·`V²/2`)의 여백·선 굵기·세로 위치였고, 글꼴을 등폭으로 맞춘
#   판단도 **분수 하나**(`fig-02-p01`)에 대한 것이었다. 자가 그 경계를 넘으면서
#   `fig-two-ledgers` 의 같은 막대 이름표가 **`KE = 5 kJ` 는 등폭 · `PE`·`U`·`+5 kJ` 는 본래 글꼴**로
#   갈렸다. 등폭은 **조판 단위**(분수·한 줄 수식)의 글꼴이지 이름표의 글꼴이 아니다.
#
#   ★ 이건 **짝 라벨 부류의 글꼴 판**이다(AGENTS 「같은 역할의 라벨은 같은 규칙으로 배치한다」).
#   그래서 경계를 **글자에서 조판 단위로** 옮긴다.
#     · 조판 그룹(`frac`·`mathline`) **안** → 생성기가 찍는 규격 그대로여야 한다(아래 조판 대조).
#     · 조판 그룹 **밖**(낱개 라벨) → **삽화 자신의 글꼴.** 등폭을 선언하면 그 자체가 결함이다.
#
#   **왜 '관계 기호' 자를 되살리면 안 되나.** 그 자는 *무엇이 식인가* 를 글자만 보고 판정하는데,
#   같은 삽화의 `KE = 5 kJ` 와 `PE` 는 **역할이 같고 글자만 다르다.** 역할은 글자에 안 적혀 있다 —
#   그래서 판정 기준을 '식인가'가 아니라 **'조판 단위 안인가'** 로 옮긴 것이다. 조판 단위는
#   저자가 `svg_fraction`·`svg_math_line` 을 불러 **선언**하는 것이라 글자를 훑어 추측할 필요가 없다.
#
#   ★ **그래서 조판 단위에는 분수가 아닌 항도 들어간다.** `fig-flow-mech-three-parts` 의 세 칸은
#   `P/ρ` · `V²/2` · `gz` 인데 앞 둘만 분수다. 앞 둘을 조판하고 `gz` 를 낱개 라벨로 두면
#   **같은 합의 세 항이 두 글꼴로 갈린다** — 사용자가 반려한 것과 똑같은 그림이다(렌더로 확인).
#   산문에서도 `\(gz\)` 는 분수와 같은 렌더러를 탄다. 그런 항은 `svg_math_line` 으로 찍어
#   `mathline` 그룹에 넣는다 — **저자가 '이건 조판이다'라고 선언하는 자리**이고,
#   선언이 없는 라벨은 삽화 글꼴을 따른다는 원칙은 그대로다.
#
#   **왜 '한 삽화 안에서 갈렸는가'(비교 판정)로 하지 않았나.** 그러면 라벨이 *우연히 전부* 식인
#   삽화는 통째로 등폭이 되어 통과한다(실측 `fig-01-p01`·`fig-01-p02` — 옛 자가 라벨 4개를 모두
#   바꿔 놓았다). 저자는 그 두 삽화에 글꼴을 선언한 적이 없고(`4649ed8^` 에 `font-family` 0건),
#   그 결과는 **옆 삽화와 갈라진다** — 한 단계 위에서 같은 부류가 된다.
def figure_math_font_targets(svg):
    """낱개 라벨에 **잘못 선언된** 산문 수식 글꼴 — 지워야 할 자리. 순수 함수(교정 도구가 부른다)."""
    return [(s, e, inner) for s, e, font, inner in _standalone_texts(svg)
            if font == MATH_FONT]


# ★★ **조판 그룹 안인데 수식 글꼴이 없는 글자** — 위 `figure_math_font_targets` 의 뒷면
#   (열린 날 2026-08-07, 사용자가 같은 자리를 2회 지적한 뒤).
#
#   C20 은 그동안 **분수 덩어리 안쪽**과 **그룹 밖 낱개 라벨**만 봤다. 그 사이, 즉 한 줄
#   수식에서 분수가 아닌 **글자 조각**은 아무도 안 봤다 — 그래서 손으로 조립된 줄
#   (`ch01 fig-d-piston-balance` 캡션)이 `font-family` 없이 몇 달을 지나갔다.
#
#   ★ 이건 미관 문제가 아니다. `run_width` 는 **등폭 가정**으로 조각 폭을 재서 분수 자리를
#     잡는데(`_char_w` 의 `mono`), 글꼴 선언이 없으면 그 글자는 삽화 글꼴로 그려진다 —
#     자와 렌더가 갈리므로 **분수가 앞 글자 쪽으로 밀려든다.** 사용자가 본 것이 그것이다.
def _line_fragment_texts(svg):
    """조판 그룹 안이지만 **분수 덩어리 밖**인 `<text>` — 한 줄 수식의 글자 조각.

    (시작, 선언한 글꼴, 보이는 글자). 순수 함수(테스트가 부른다).
    """
    groups = [(s, e) for s, e, _b in _tagged_group_spans(svg, MATH_GROUP_MARKS)]
    leaves = [(s, e) for s, e, _b in _leaf_frac_groups(svg)]
    out = []
    for m in _FRAC_TEXT_RE.finditer(svg):
        if not any(s <= m.start() < e for s, e in groups):
            continue
        if any(s <= m.start() < e for s, e in leaves):
            continue                      # 분자·분모는 위 조판 대조가 본다
        inner = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not inner:
            continue
        out.append((m.start(),
                    _effective(svg, m.start(), m.group(1), "font-family", ""), inner))
    return out


def figure_math_typesetting_hits(svg):
    """지금 생성기가 찍을 조판과 어긋난 자리를 (사유, 미리보기) 로. 순수 함수 — 테스트가 부른다."""
    hits = []

    for _s, _e, body in _leaf_frac_groups(svg):
        texts = _FRAC_TEXT_RE.findall(body)
        lines = _FRAC_LINE_RE.findall(body)
        if len(texts) != 2 or len(lines) != 1:
            hits.append(("분수 덩어리의 구성이 규격과 다르다 (글자 2 + 분수선 1 이 아님)",
                         body[:70]))
            continue
        (num_attrs, num_body), (den_attrs, den_body) = texts
        try:
            fs = float(_attr(num_attrs, "font-size", ""))
        except ValueError:
            hits.append(("분자에 font-size 가 없다", body[:70]))
            continue
        preview = re.sub(r"<[^>]+>", "", num_body) + "/" + re.sub(r"<[^>]+>", "", den_body)
        for label, attrs in (("분자", num_attrs), ("분모", den_attrs)):
            got = _attr(attrs, "font-family", "")
            if got != MATH_FONT:
                hits.append(("%s 글꼴이 산문 수식과 다르다 — %r ≠ 수식 글꼴"
                             % (label, got or "(없음)"), preview))
        for label, raw in (("분자", num_body), ("분모", den_body)):
            if any(c in raw for c in _SUP_GLYPHS):
                hits.append(("%s 의 위첨자가 유니코드 글리프다 — 산문 <sup> 보다 26%% 작다"
                             % label, preview))
        axis = float(_attr(lines[0], "y1", "0"))
        want = {
            "분자 baseline": (float(_attr(num_attrs, "y", "0")),
                             axis - FRACTION_NUM_BASE * fs),
            "분모 baseline": (float(_attr(den_attrs, "y", "0")),
                             axis + FRACTION_DEN_BASE * fs),
            "분수선 굵기": (float(_attr(lines[0], "stroke-width", "0")),
                         max(FRACTION_BAR_MIN, fs * 0.065)),
            "분수선 폭": (abs(float(_attr(lines[0], "x2", "0"))
                           - float(_attr(lines[0], "x1", "0"))),
                        max(run_width(expand_superscripts(num_body, fs), fs, True),
                            run_width(expand_superscripts(den_body, fs), fs, True))
                        + 2 * FRACTION_SIDE_PAD * fs),
        }
        for label, (got, exp) in want.items():
            if abs(got - exp) > 0.06:
                hits.append(("%s %.2f ≠ 지금 규격 %.2f" % (label, got, exp), preview))

    # 한 줄 수식의 글자 조각에 수식 글꼴이 없는 자리 (위 `_line_fragment_texts` 주석이 정본).
    for _pos, font, inner in _line_fragment_texts(svg):
        if font != MATH_FONT:
            hits.append(("한 줄 수식의 글자 조각에 수식 글꼴이 없다 — %r ≠ 수식 글꼴. "
                         "자(`run_width`)는 등폭으로 재는데 화면은 삽화 글꼴로 그려져 "
                         "분수 자리가 어긋난다" % (font or "(없음)"), inner[:44]))

    # 낱개 라벨의 글꼴이 한 삽화 안에서 갈린 자리 (위 `figure_math_font_targets` 주석이 정본).
    for _start, _end, inner in figure_math_font_targets(svg):
        hits.append(("낱개 라벨에 산문 수식 글꼴이 선언돼 같은 삽화 안에서 글꼴이 갈렸다",
                     inner[:44]))
    return hits


# ★★ **간격이 묶음을 만든다** — 색으로 묶어 놓고 간격이 그것을 부정하면 결함 (열린 날 2026-08-02).
#
#   사용자(동역학 ch12 `fig-sva-chain`): [사용자 발화 인용 생략]
#
#   실측(그 삽화): 같은 색 쌍 **7.7px** · 색이 바뀌는 쌍 **6.7px** — **거꾸로였다.**
#   독자는 색으로 한 묶음을 보고 간격으로 다른 묶음을 본다. 두 신호가 어긋나면 위계가 안 읽힌다.
#
# ★ **규칙은 이미 있었고, 없던 것은 「무엇이 블록 경계인가」를 판정하는 자였다.**
#   AGENTS 「라벨의 기준 위치」가 *블록 간 1.5em · 제목–부제 0.5em* 을 정해 두었지만,
#   어디부터가 새 블록인지는 사람의 눈에 맡겨져 있었다 — 그래서 삽화마다 갈렸다.
#   **색 변화가 그 판정자다.** 저자가 색을 바꾼 자리가 곧 저자가 선언한 블록 경계다.
#
# ★ 판정을 **절대값이 아니라 비교**로 한다. "0.5em/1.5em을 지켰는가"로 물으면 삽화마다 폰트와
#   여유가 달라 오탐이 쏟아진다(라벨 여백 자가 391건 중 91건 오탐이었던 선례). 물어야 할 것은
#   [사용자 발화 인용 생략] 하나뿐이고, 그건 그 삽화 안에서 자족적으로 판정된다.
GROUPING_MIN_RATIO = 1.5     # 색 경계의 간격은 같은 색 이웃 간격의 이 배 이상이어야 한다
GROUPING_X_OVERLAP = 0.35    # 가로로 이만큼 겹쳐야 '같은 세로 줄기'로 본다
GROUPING_X_TOL = 2.0         # 기준 x 가 이보다 어긋나면 같은 축에 정렬된 블록이 아니다
GROUPING_MAX_GAP_EM = 3.0    # 이보다 멀면 이웃이 아니다(다른 도해)
# ★★ **눈금선이 자리를 정한 라벨은 이 자의 대상이 아니다** (좁힌 날 2026-08-02, ch01 실측).
#
#   이 검사의 전제는 [사용자 발화 인용 생략] 이다. 그런데 눈금축의 라벨은 다르다 —
#   `Pabs = ?` 가 `Patm = 88 kPa` 아래 몇 px 에 있는지는 **압력값이 정하는 것**이고
#   조판으로 바꿀 수 있는 값이 아니다. 옮기면 그림이 물리적으로 틀려진다.
#
#   실측(`fig-01-p04`): 압력축 눈금 셋에 붙은 라벨이 색 경계 25.2px · 같은 색 38.0px 로
#   신고됐다. **고칠 방법이 없는 신고**다 — 라벨을 규격대로 눈금에 맞추면 25.2 → 15.0 으로
#   오히려 나빠진다(그 정렬 자체는 별개의 진짜 결함이라 데이터에서 고쳤다).
#   눈금 라벨은 이 부류의 어느 삽화에나 있으므로(압력 사다리·온도 눈금·T-v 선도)
#   인스턴스 면제로 덮으면 같은 신고가 챕터마다 돌아온다.
#
#   판정: 글자의 세로 중심 가까이에 **짧은 수평선**이 있고 그 선이 글자에 붙어 있으면
#   그 글자의 높이는 눈금이 정한 것이다. '짧은'을 요구하는 이유는 패널 상자의 가로변·
#   구분선이 우연히 캡션 높이에 걸려 **진짜 신고를 조용히 면제**하는 것을 막기 위해서다.
GROUPING_TICK_DY_EM = 0.5     # 눈금선이 글자 세로 중심에서 이만큼 안이면 그 눈금의 라벨이다
GROUPING_TICK_DX_EM = 3.0     # 그리고 가로로 이만큼 안에 붙어 있어야 한다
GROUPING_TICK_MAX_LEN = 60.0  # 이보다 길면 눈금이 아니라 상자변·구분선이다


def _horizontal_ticks(svg):
    """눈금으로 볼 만한 **짧은 수평선** — (x0, y, x1). 순수 함수(테스트가 부른다)."""
    out = []
    for x1, y1, x2, y2 in _svg_segments(svg):
        if abs(y1 - y2) >= 0.5 or abs(x1 - x2) > GROUPING_TICK_MAX_LEN:
            continue
        out.append((min(x1, x2), y1, max(x1, x2)))
    return out


# ★★ **다른 칸에 든 글자는 한 묶음이 아니다** (좁힌 날 2026-08-02, ch01 실측).
#
#   칸(채운 상자) 안의 라벨은 칸이 주는 여유가 상한이라 자유롭게 못 옮긴다 — 라벨 여백 자가
#   `min(1em, 칸 여유)` 로 바뀐 것과 같은 이유(`test_label_gap_respects_container`).
#   여기서는 한 걸음 더 나아간다: **칸 경계 자체가 블록 경계**이므로, 칸을 가로질러 잰
#   간격은 저자가 고른 조판 간격이 아니라 상자 배치의 결과다.
#
#   실측(`fig-intensive-extensive-split`): 위·아래 두 칸에 나눠 든 흰 글자 넷이 한 줄기로
#   묶여, **칸을 건너뛴 20.0px** 이 '같은 색 이웃' 의 대표값이 됐다. 그래서 패널 제목이
#   30px 넘게 떨어져야 한다는 요구가 나왔는데, 그러면 제목이 삽화 위 여백을 뚫는다.
#   게다가 왼쪽 패널(칸이 하나뿐)은 같은 20px 인데 신고되지 않아 **고치면 두 패널의 위계가
#   서로 어긋난다** — 규격이 없애려는 결함을 규격이 만드는 자리였다.
def _container_of(it, shapes):
    """이 글자를 담은 **가장 작은 칸**의 좌표 (없으면 None)."""
    cx = (it["box"][0] + it["box"][2]) / 2.0
    cy = (it["box"][1] + it["box"][3]) / 2.0
    best = None
    for x0, y0, x1, y1 in shapes:
        if not (x0 <= cx <= x1 and y0 <= cy <= y1):
            continue
        area = (x1 - x0) * (y1 - y0)
        if best is None or area < best[0]:
            best = (area, (x0, y0, x1, y1))
    return best[1] if best else None


def _tick_pinned(it, ticks):
    """이 글자의 높이를 **눈금선이 정했는가**. 그러면 간격은 조판이 아니라 값이 정한 것이다."""
    cy = it["y"] - it["fs"] * 0.27                 # _text_bbox 가 잡는 상자의 세로 중심
    for tx0, ty, tx1 in ticks:
        if abs(ty - cy) > GROUPING_TICK_DY_EM * it["fs"]:
            continue
        gap = max(tx0 - it["box"][2], it["box"][0] - tx1, 0.0)
        if gap <= GROUPING_TICK_DX_EM * it["fs"]:
            return True
    return False


def _text_stacks(svg):
    """세로로 이어진 글줄 묶음 — [[item, …], …]. 순수 함수(테스트가 부른다).

    분수 안쪽(`<g class='frac'>`)은 뺀다. 분자·분모는 한 덩어리라 간격이 규격상 아주 좁은데,
    그것을 '같은 색 이웃'으로 세면 그 삽화의 모든 블록 경계가 위반이 된다.

    눈금선이 높이를 정한 라벨도 뺀다 — 위 `_tick_pinned` 주석이 정본.
    서로 다른 칸에 든 글자는 잇지 않는다 — 위 `_container_of` 주석이 정본.
    """
    frac = [(s, e) for s, e, _b in _tagged_group_spans(svg, ("frac",))]
    items = [it for it in _svg_texts(svg)
             if it["s"].strip() and not any(s <= it["pos"] < e for s, e in frac)]
    for it in items:
        it["box"] = _text_bbox(it)
    ticks = _horizontal_ticks(svg)
    items = [it for it in items if not _tick_pinned(it, ticks)]
    vb = _attr(svg[svg.find("<svg"):svg.find(">") + 1], "viewBox")
    shapes = _svg_filled_shapes(svg, [float(v) for v in vb.split()]) if vb else []
    for it in items:
        it["cell"] = _container_of(it, shapes)
    items.sort(key=lambda it: it["box"][1])

    edges = {}
    for i, a in enumerate(items):
        best = None
        for b in items:
            if b["box"][1] <= a["box"][3] - 0.01:
                continue                                   # 위이거나 같은 줄
            # ★ **같은 정렬 기준을 공유해야 한 묶음이다** (2026-08-02, 첫 실행에서 오탐이 나와 정정).
            #   가로 겹침만 보면 넓은 삽화에서 **우연히 세로로 겹친 남남**이 한 줄기가 된다 —
            #   실측(`fig-rectilinear-position`): 화살표 라벨 둘과 상자 안 번호가 엮여
            #   32.7px/40.7px 로 신고됐는데, 셋은 서로 아무 관계도 없고 고칠 것도 없었다.
            #   캡션 블록은 **한 축에 정렬돼 있다**(AGENTS 「축 제목의 x는 눈으로 재지 말 것」) —
            #   앵커와 기준 x 가 같은 것만 묶으면 그 부류가 통째로 빠진다.
            if a["anchor"] != b["anchor"] or abs(a["x"] - b["x"]) > GROUPING_X_TOL:
                continue
            # ★ **둘 다 칸 안에 있고 칸이 다를 때만** 끊는다 (조인 날 2026-08-02, 양성 대조 실패).
            #   처음에는 `a["cell"] != b["cell"]` 로 끊었는데, 그러면 **칸 밖의 패널 제목**과
            #   칸 안의 첫 줄도 남남이 되어 [사용자 발화 인용 생략] 라는 정상 신고까지
            #   함께 꺼졌다. 좁히려던 것은 **칸을 건너뛴 이웃**이지 칸의 안팎이 아니다.
            if a["cell"] is not None and b["cell"] is not None and a["cell"] != b["cell"]:
                continue                                   # 칸 경계가 곧 블록 경계다
            lo, hi = max(a["box"][0], b["box"][0]), min(a["box"][2], b["box"][2])
            narrow = min(a["box"][2] - a["box"][0], b["box"][2] - b["box"][0])
            if narrow <= 0 or (hi - lo) < GROUPING_X_OVERLAP * narrow:
                continue                                   # 가로로 안 겹친다 — 다른 줄기
            gap = b["box"][1] - a["box"][3]
            if gap > GROUPING_MAX_GAP_EM * max(a["fs"], b["fs"]):
                continue
            if best is None or gap < best[0]:
                best = (gap, b)
        if best:
            edges[i] = (best[0], items.index(best[1]))

    stacks, seen = [], set()
    for i in range(len(items)):
        if i in seen or i in {t for _g, t in edges.values()}:
            continue                                       # 줄기의 머리에서만 출발한다
        chain, cur = [items[i]], i
        seen.add(i)
        while cur in edges:
            _g, nxt = edges[cur]
            if nxt in seen:
                break
            chain.append(items[nxt])
            seen.add(nxt)
            cur = nxt
        if len(chain) >= 3:
            stacks.append(chain)
    return stacks


def figure_text_grouping_hits(svg):
    """색이 묶은 것과 간격이 묶은 것이 어긋난 자리 — (사유, 미리보기). 순수 함수."""
    hits = []
    for chain in _text_stacks(svg):
        pairs = []
        for a, b in zip(chain, chain[1:]):
            pairs.append((b["box"][1] - a["box"][3], a["fill"] == b["fill"], a, b))
        same = [p for p in pairs if p[1]]
        diff = [p for p in pairs if not p[1]]
        if not same or not diff:
            continue                                       # 비교할 짝이 없다
        widest_same = max(same, key=lambda p: p[0])
        tightest_diff = min(diff, key=lambda p: p[0])
        if tightest_diff[0] >= GROUPING_MIN_RATIO * widest_same[0]:
            continue
        hits.append((
            "색이 바뀌는 자리(블록 경계)가 같은 색 이웃보다 안 멀다 — "
            "경계 %.1fpx ≤ 같은 색 %.1fpx × %.1f. 간격이 색과 같은 묶음을 만들어야 한다"
            % (tightest_diff[0], widest_same[0], GROUPING_MIN_RATIO),
            widest_same[2]["s"].strip()[:20] + " / " + widest_same[3]["s"].strip()[:20]
            + "  ↔  " + tightest_diff[2]["s"].strip()[:20] + " / "
            + tightest_diff[3]["s"].strip()[:20]))
    return hits


# ★ C31. **짝을 이루는 라벨이 자기 도형에서 같은 거리에 놓였는가** (열린 날 2026-08-05, R-24·R-26).
#
# 사용자(`fig-02-q02`): [사용자 발화 인용 생략] · (`fig-02-q03`) [사용자 발화 인용 생략]
#
# ★ **왜 기존 자가 통과시켰나 — 자가 「하한」만 본다.** 라벨 여백 자(F1)는 *1.0em 이상인가*만
#   묻는다. 그래서 실측 2.53em 과 1.43em 이 **둘 다 통과**했다. 그런데 AGENTS 「여백·라벨 규격」이
#   요구하는 것은 절대값이 아니라 **비교**다 — [사용자 발화 인용 생략] **물어본 적이 없는 것**이지 빠뜨린 것이 아니다.
#
# ★ 판정을 **비율**로 하는 것은 C21(색 묶음)에서 이미 검증된 형태다. 절대값으로 물으면
#   삽화마다 폰트·여유가 달라 오탐이 쏟아진다(라벨 여백 자 391건 중 91건 오탐 선례).
#
# ★★ **묶음은 「같은 색 + 같은 크기 + 같은 굵기」로만 잡는다.** 역할은 기계가 못 읽으므로
#   저자가 이미 선언한 것(색·크기·굵기)을 역할의 대리로 쓴다 — C21 이 색을 블록 경계의
#   대리로 쓰는 것과 같다. 셋이 모두 같은 글자 둘은 *저자 스스로 같은 위계라고 선언한 것*이다.
# ★★ **캡션은 뺀다.** 삽화 아래 조건 캡션은 도형에서 멀리 떨어지는 것이 정상이라, 같은 색의
#   라벨과 묶이면 비율이 무조건 커진다 — 고칠 것이 없는 신고가 된다(`_is_caption_text` 공유).
#
# ★★★ **빌드 error 로 올리지 않는다 — 후보만 낸다(`audit_figure_balance` 「짝 라벨」 절).**
#   열역학 ch02 전수 실측(2026-08-05, 삽화 42개): **후보 8건 중 진짜 3건**(`fig-02-q12` 의
#   Qin/Qout · `fig-02-q16` 의 같은 문구 둘 · `fig-p07-hydro-chain` 의 부품 이름 둘).
#   나머지 5건은 **역할이 다른 글자가 우연히 같은 색·크기였던 것**이다 — 분수 분자 대 항
#   (`V²` ↔ `gz`), 식 대 상자 이름(`Ein - Eout = ΔE` ↔ `계`), 상태 설명 대 미지수
#   (`still air` ↔ `Ẇmin = ?`). 색·크기·굵기는 역할의 **대리**일 뿐이라 여기까지가 한계다.
#   정밀도 3/8 로 error 를 삼으면 멀쩡한 삽화가 멈춘다 — AGENTS 「잡지 못하는 검사를 다는 것이
#   가장 나쁘다」의 반대편 실수(과탐)를 피한다. 선례는 [L] 카드 중복(점수만 내고 사람이 판정).
#
# ★★★ **못 잡는 부류를 밝혀 둔다.** 이 자는 R-24(`fig-02-q02`)는 잡지만 **R-26(`fig-02-q03`)은
#   못 잡는다** — 그 짝은 색도 크기도 서로 달라(#4d7690 fs15 대 #2c3a44 fs14) 애초에 같은 묶음이
#   아니었다. 즉 *저자가 같다고 선언한 것들 사이의 어긋남*만 볼 수 있고, **선언 자체가 갈린 경우는
#   사람만 안다.** 이걸 적어 두지 않으면 다음 세션이 이 자의 0건을 '없다'로 읽는다(규칙 11).
LABEL_PAIR_RATIO_MAX = 1.5       # 짝 라벨의 선-거리 비 상한 (C21 의 GROUPING_MIN_RATIO 와 같은 값)
LABEL_PAIR_MIN_EM = 0.25         # 이보다 붙은 것은 F1(하한)의 몫이다 — 비율로 또 신고하지 않는다


def figure_label_pair_gap_hits(svg):
    """짝 라벨이 자기 도형에서 서로 다른 거리에 놓인 자리 — (사유, 미리보기). 순수 함수.

    거리는 **em**(그 글자의 font-size 기준)으로 잰다. px 로 재면 크기가 다른 라벨이
    같은 취급을 못 받는데, 이 규격이 묻는 것은 *보기에 같은 만큼 떨어졌는가*다.

    ★★ **분수 조각은 짝이 아니다** (열린 날 2026-08-13 — **두 과목이 독립으로 신고**했다).
      · 동역학 `fig-sva-chain` `dt` ↔ `d` — 같은 분수의 분모와 분자다. 분수선이 사이에
        있으니 도형까지의 거리가 다를 수밖에 없다.
      · 공학수학 `fig-existence-rect` `b` ↔ `K`(0.92em 대 2.26em) — `α = b/K` 한 수식의 조각.
      둘 다 *같은 색·크기·굵기* 라 이 자가 「같은 역할」로 묶었는데, **역할이 같은 것이 아니라
      한 라벨의 부분**이다. 그 자리는 사람이 정하지 않는다 — `svg_fraction.py` 가 조판한다.
      그래서 «맞추라»는 신고는 **고칠 수 없는 신고**이고, 두 과목이 각각 판정 기록을 남겨
      영구 잔량이 됐다(공학수학 2026-08-05 · 동역학 2026-08-13 워크오더).

      ★ 면제(`own`)로는 못 닫는다 — 그건 *자기 분수선까지의 거리*만 빼 주고, 여기서 문제는
        **묶은 것 자체**다. C21·F1·C28 이 `frac` 을 면제하는 것과 자리가 다르다.
    """
    segments = _svg_segments(svg)
    if not segments:
        return []
    bars = _fraction_bars(svg)
    frac_spans = {span for span, _seg in bars}
    groups = {}
    for t in _svg_texts(svg):
        if not t["fs"] or not t["s"].strip():
            continue
        if _is_caption_text(t):
            continue
        if any(gs <= t["pos"] < ge for gs, ge in frac_spans):
            continue                                   # 분수 조각 — 위 독스트링이 정본
        box = _text_bbox(t)
        own = {seg for (gs, ge), seg in bars if gs <= t["pos"] < ge}
        gaps = [_segment_to_rect_distance(s, box) for s in segments if s not in own]
        if not gaps:
            continue
        em = min(gaps) / t["fs"]
        if em < LABEL_PAIR_MIN_EM:
            continue
        groups.setdefault((t["fill"], round(t["fs"], 2), t["weight"]), []).append((em, t))
    hits = []
    for _key, members in sorted(groups.items(), key=lambda kv: str(kv[0])):
        if len(members) < 2:
            continue                                   # 짝이 없으면 비교할 것도 없다
        members.sort(key=lambda p: p[0])
        near, far = members[0], members[-1]
        if far[0] <= LABEL_PAIR_RATIO_MAX * near[0]:
            continue
        hits.append((
            "짝 라벨이 자기 도형에서 다른 거리에 있다 — %.2fem 대 %.2fem (%.1f배, 상한 %.1f). "
            "같은 색·크기·굵기는 같은 역할이라는 선언이므로 거리·방향을 맞출 것"
            % (near[0], far[0], far[0] / near[0], LABEL_PAIR_RATIO_MAX),
            near[1]["s"].strip()[:20] + "  ↔  " + far[1]["s"].strip()[:20]))
    return hits


# ★ C28. **칸 안 글자 덩어리가 칸의 세로 중앙인가** (열린 날 2026-08-04, R-74).
#
# 사용자 지적(2장 4절 `fig-name-at-boundary`): [사용자 발화 인용 생략]
# 실측 — `계`(fs 12.5, baseline 82.25) + `U`(fs 14.5, baseline 107.02) 두 줄의 덩어리 중심이
# **91.5** 인데 사각형(`y=60~160`)의 중심은 **110** 이었다. **18.5 위로 치우쳐 있었다.**
#
# ★ 왜 기존 자가 못 봤나 — **재는 대상이 다르다.** `audit_figure_balance` 의 세로 균형은
#   *삽화 전체*의 위·아래 여백만 보고(이 삽화는 36.5/36.9 로 **합격**이었다),
#   C21 은 *글줄 사이 간격*을 보고, 라벨 여백 자는 *글자와 도형 사이 최소 거리*를 본다.
#   **「담는 상자 안에서 덩어리가 어디에 있는가」를 묻는 자가 하나도 없었다.**
#   그래서 이 결함은 세 자를 전부 통과했다 — 빠뜨린 것이 아니라 물어본 적이 없는 것이다.
#
# ★ **세로만 본다.** 가로는 왼쪽 정렬이 정당한 설계가 흔하지만(표의 항목·목록·축 라벨),
#   칸 안 글자가 위나 아래로 치우칠 정당한 이유는 드물다. 물을 수 있는 것만 묻는다.
#
# ★ **칸이 글자에 비해 아주 크면 그것은 '칸'이 아니라 '패널'이다.** 패널 안의 글자는 제목·주석이라
#   위쪽에 붙는 것이 규격이므로 중앙 정렬을 요구하면 안 된다 — 그래서 높이 비를 문턱으로 둔다.
#   (이 문턱이 없으면 정상 삽화가 무더기로 신고된다. 라벨 여백 자가 391건 중 91건 오탐을 낸
#    선례가 있어, 비교 대상이 아닌 것을 재지 않도록 범위부터 좁힌다.)
#
# ★★ **글자만 담은 칸에만 묻는다** (첫 실측에서 곧바로 좁혔다 — 11건 중 10건이 오탐이었다).
#   칸 안에 그림이 함께 있으면(컵·탱크·선도 곡선·자유물체도의 화살표) 글자는 그 그림을
#   **가리키느라** 위나 아래에 놓인 것이다. 그걸 칸 중앙으로 끌어오면 그림을 덮는다 —
#   즉 규격을 지킬수록 삽화가 나빠지는 자리다. 실측 오탐 예: `fig-cup-macro-vs-micro`(컵 그림),
#   `fig-tv-diagram`·`fig-pv-diagram`(선도 곡선), `fig-q13-piston-spring-fbd`(자유물체도 화살표).
#   **비교 대상이 아닌 것을 재지 않는 것이 이 자의 정확도를 만든다.**
BOX_INNER_MARGIN = 1.5           # 칸 테두리와 겹치는 선은 '안에 든 그림'이 아니다
# ★★★ **0.5 → 0.3, 그리고 재는 상자를 「em 상자」에서 「잉크」로 바꿨다** (2026-08-13, 같은 지적 4회차).
#   사용자: [사용자 발화 인용 생략]
#   실측(ch01 `fig-ch01-q05-situation`): 칸 y=58~146(중심 102) · `탱크` fs 13 baseline 101.
#   ⑴ **자가 다른 것을 재고 있었다.** `_text_bbox` 는 겹침 판정용 **em 상자**(위 0.78em ·
#      아래 0.24em)라 중심이 baseline − 0.27em 이다. 그런데 이 리포가 *글자를 선에 맞출 때* 쓰는
#      규약은 **`baseline = 중심 + fs × 0.35`**(AGENTS 「세로 눈금축의 라벨」)로, 중심이
#      baseline − 0.35em 이다. **같은 질문에 자가 둘이었고** 그 차이(0.08em)만큼 늘 통과했다.
#      → 이 검사만 **잉크 상자**(위 0.73em · 아래 0.03em — 한글은 디센더가 거의 없다)로 재서
#        규약과 같은 중심을 쓴다. 겹침 판정은 그대로 em 상자다(거기서는 그게 맞다).
#   ⑵ **문턱이 너무 느슨했다.** 위 실측의 어긋남은 잉크로 5.6px 인데 허용이 0.5em = 6.5px 라
#      **네 번을 지적받는 동안 한 번도 안 걸렸다.** 0.3em(3.9px)이면 걸린다.
#   ★ 문턱을 조이면 손으로 맞추던 자리가 무더기로 뜨므로 **처방을 함께 둔다** —
#     `python tools/fix_box_center.py [--chapter=chNN.json] [--apply]` 가 baseline 을 규약대로 옮긴다.
BOX_CENTER_TOL_EM = 0.3          # 덩어리 중심과 칸 중심의 허용 어긋남 (가장 큰 글자 기준)
BOX_INK_ASCENT = 0.73            # 잉크 상자 — 규약(baseline = 중심 + 0.35em)과 같은 중심을 준다
BOX_INK_DESCENT = 0.03
# ★★ 칸 높이 / 글자 덩어리 높이 — 넘으면 '패널'로 보고 묻지 않는다.
#   **3 → 10 (2026-08-05, 사용자 재지적:** [사용자 발화 인용 생략]). 실측 `fig-in-out-subscripts`: 칸 90px 에 `계` 한 줄(12px)뿐이라
#   **높이비 7.5** 로 옛 문턱 3 을 훌쩍 넘어 '패널'로 면제됐다 — 그런데 그건 계 상자이지
#   패널이 아니었고 글자가 **28px 위로** 떠 있었다. 같은 지적 2회차이므로 문턱을 데이터로 다시 잡는다.
#   ★ 두 극을 재서 그 사이로 정했다: 진짜 계 상자 **7.35** vs 진짜 패널 제목 **24.7**
#     (회귀 `test_box_center` ⑸ 의 픽스처). 10 은 둘을 가르면서 어느 쪽에도 붙지 않는 값이다.
#   ★ 처음에 3 을 고른 근거는 *오탐을 줄인다*였는데, 실측하면 오탐을 막은 것은 대부분
#     `_holds_drawing`(그림이 함께 든 칸) 쪽이었다 — **문턱은 그만큼 좁을 이유가 없었다.**
BOX_CENTER_MAX_RATIO = 10.0


# ★ C29. **축류팬은 조각 하나로만 그린다** (열린 날 2026-08-04, 인박스 R-39).
#
# 사용자: [사용자 발화 인용 생략]
#
# ★ 원인은 **팬을 그릴 때마다 좌표를 새로 잡은 것**이다. 실측 — `fig-02-p05` 는 곡선 날개에
#   허브/링 0.238, `fig-02-q13` 은 **삼각형 날개**에 0.21 이었다. 같은 사물인데 정본이 없었다.
#   AGENTS 가 3D 프리미티브에 대해 적어 둔 진단과 같다:
#   [사용자 발화 인용 생략]
#
# ★ 형상의 정본은 R-17 을 닫으며 다시 정의한 `fig-02-p05` 다. 세 가지가 규격이다 —
#   ⑴ **뿌리는 허브 원 안쪽의 현**(손 좌표로 찍으면 허브 반지름과 무관해져 한쪽은 묻히고
#      한쪽은 튀어나온다 — R-17 실측 6.80 vs 10.88, 허브 8)
#   ⑵ **허브/팁 ≈ 0.24**(축류팬의 실제 비율)
#   ⑶ **그리기 순서 링 → 날개 → 허브**(허브를 먼저 그리면 날개가 그 위에 얹혀 허브 원이
#      날개 수만큼 베어 물린 것처럼 보인다).
#
# ★ **`data-fan` 이 계약이다.** 그 속성이 붙은 `<g class='fan'>` 은 아래 `fan_svg` 가 같은
#   인자로 찍은 것과 **글자까지 같아야** 한다. 손으로 고치면 여기서 걸린다 —
#   `<g class='frac'>` 이 분수에 대해 하는 일과 같은 형태다.
BLADE_PROFILE = (
    (0.627381, -0.283333),      # 제어점 1
    (0.829762, -0.283333),      # 제어점 2
    (0.890476, 0.020238),       # 날개 끝
    (0.951190, 0.323810),       # 제어점 3
    (0.688095, 0.445238),       # 제어점 4
)
FAN_ROOT_SPAN_DEG = 38.66       # 뿌리 현이 허브 중심에서 벌리는 각
FAN_HUB_TIP_RATIO = 0.238       # 허브/팁 — 축류팬의 실제 비율
FAN_ROOT_IN_HUB = 0.85          # 뿌리 현의 반지름 ÷ 허브 반지름 (허브 아래로 숨는다)


def _fan_num(v):
    """좌표를 문자열로 — 정수는 정수로 적는다(손으로 적은 기존 조각과 표기를 맞춘다)."""
    r = round(v + 0.0, 2)
    return str(int(r)) if abs(r - int(r)) < 1e-9 else ("%.2f" % r).rstrip("0").rstrip(".")


def fan_blade_path(cx, cy, r, hub):
    """날개 한 장의 `d`. 순수 함수 — 테스트가 직접 부른다."""
    root = hub * FAN_ROOT_IN_HUB
    ang = math.radians(FAN_ROOT_SPAN_DEG)
    pts = [(cx + root, cy)]
    pts.extend((cx + r * dx, cy + r * dy) for dx, dy in BLADE_PROFILE)
    pts.append((cx + root * math.cos(ang), cy + root * math.sin(ang)))
    s = "M " + _fan_num(pts[0][0]) + " " + _fan_num(pts[0][1])
    s += " C " + " ".join(_fan_num(x) + " " + _fan_num(y) for x, y in pts[1:4])
    s += " C " + " ".join(_fan_num(x) + " " + _fan_num(y) for x, y in pts[4:7])
    return s + " Z"


def fan_svg(cx, cy, r, blades=3, fill="#4d7690", paper="#f7f4ec", hub_fill="#2c3a44",
            ring_width=4):
    """팬 조각 전체(링·날개·허브)를 `<g class='fan'>` 으로 묶어 돌려준다. 순수 함수."""
    hub = r * FAN_HUB_TIP_RATIO
    d = fan_blade_path(cx, cy, r, hub)
    step = 360.0 / blades
    out = ["<g class='fan' data-fan='"
           + ",".join(_fan_num(v) for v in (cx, cy, r)) + "," + str(blades) + "'>"]
    out.append("<circle cx='" + _fan_num(cx) + "' cy='" + _fan_num(cy) + "' r='" + _fan_num(r)
               + "' fill='" + paper + "' stroke='" + fill
               + "' stroke-width='" + _fan_num(ring_width) + "'/>")
    out.append("<g fill='" + fill + "'>")
    for i in range(blades):
        turn = ("" if i == 0 else
                " transform='rotate(" + _fan_num(step * i) + " " + _fan_num(cx) + " "
                + _fan_num(cy) + ")'")
        out.append("<path d='" + d + "'" + turn + "/>")
    out.append("</g>")
    out.append("<circle cx='" + _fan_num(cx) + "' cy='" + _fan_num(cy) + "' r='" + _fan_num(hub)
               + "' fill='" + hub_fill + "'/>")
    out.append("</g>")
    return "".join(out)


def fan_shape_issues(svg):
    """`data-fan` 을 단 조각이 정본과 어긋난 자리. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for start, end, _body in _tagged_group_spans(svg, ("fan",)):
        chunk = svg[start:end]
        params = _attr(chunk[:chunk.find(">") + 1], "data-fan")
        if not params:
            out.append("팬 조각에 `data-fan` 이 없다 — 정본 대조를 할 수 없다."
                       " `python tools/svg_fan.py` 가 찍는 조각으로 바꿀 것")
            continue
        # ★★ **색은 잠그지 않는다 — 잠그면 팔레트를 못 바꾼다** (고침 2026-08-13).
        #   이 계약이 지키려는 것은 **팬의 형상**이다(뿌리가 허브 안쪽 현인가 · 허브/팁 비 ·
        #   그리는 순서). 그런데 정본을 기본 색으로 찍어 글자까지 대조하니, 종이색을 바꾸는
        #   순간 **형상이 멀쩡한 팬 둘이 통째로 error** 가 됐다(사용자가 종이색을 고른 그 자리다).
        #   → 색은 **조각 자신에게서 읽어** 정본에 넣는다. 형상이 다르면 여전히 걸리고,
        #     팔레트를 갈아끼우는 것은 막지 않는다. **자가 재야 할 것과 잠글 것을 가른 것이다.**
        head = chunk[:chunk.find("/>") + 2]
        try:
            cx, cy, r, blades = params.split(",")
            want = fan_svg(float(cx), float(cy), float(r), int(blades),
                           fill=_attr(head, "stroke") or "#4d7690",
                           paper=_attr(head, "fill") or "#f7f4ec")
        except (ValueError, TypeError):
            out.append("팬 조각의 `data-fan` 을 읽을 수 없다: " + repr(params))
            continue
        if chunk != want:
            out.append("팬 조각이 정본과 다르다 — 같은 사물은 같은 조각으로 그린다"
                       " (`python tools/svg_fan.py --cx " + cx + " --cy " + cy
                       + " --r " + r + "` 가 찍는 것으로 바꿀 것)")
    return out


def symbol_below_caption_rows(svg):
    """한 묶음 안에서 **굵은 글자(기호·제목)가 안 굵은 글자 아래**에 놓인 자리. 순수 함수.

    열린 날 2026-08-04 — 사용자(`fig-name-at-boundary`):
    [사용자 발화 인용 생략]

    ★ **판정이 아니라 후보다.** `이름 위 / 기호 아래` 가 옳은 자리도 있다(흐름도의 단계 이름처럼).
      그래서 자는 세기만 하고 사람이 본다 — R-24(짝 라벨 비교 검사)가 열려 있는 동안의 눈이다.

    ★★ **`_text_stacks` 를 쓰지 않는다** (첫 구현이 그렇게 했다가 회귀에서 잡혔다).
      그 함수는 `len(chain) >= 3` 이라 **두 줄짜리 묶음을 아예 안 만든다** — 그런데 사용자가 든
      자리(`계` / `U`)가 정확히 두 줄이다. 그대로 뒀으면 이 자는 전 챕터 **0건**을 찍었을 것이고,
      그 0 은 *없다*가 아니라 *거기까지는 못 본다*였을 것이다(규칙 11). 짝 하나면 충분하므로
      여기서는 **이웃 한 쌍**을 직접 만든다. 묶는 조건(칸 경계·가로 겹침·최대 간격)은 공유한다.
    """
    head = svg[svg.find("<svg"):svg.find(">") + 1]
    vb = _attr(head, "viewBox")
    try:
        shapes = _svg_filled_shapes(svg, [float(v) for v in vb.split()]) if vb else []
    except ValueError:
        shapes = []
    items = [it for it in _svg_texts(svg) if it["s"].strip()]
    for it in items:
        it["box"] = _text_bbox(it)
        it["cell"] = _container_of(it, shapes)
    items.sort(key=lambda it: it["box"][1])
    rows = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if b["box"][1] <= a["box"][3] - 0.01:
                continue                                   # 위이거나 같은 줄
            if a["cell"] is not None and b["cell"] is not None and a["cell"] != b["cell"]:
                break                                      # 칸 경계가 곧 블록 경계다
            lo, hi = max(a["box"][0], b["box"][0]), min(a["box"][2], b["box"][2])
            narrow = min(a["box"][2] - a["box"][0], b["box"][2] - b["box"][0])
            if narrow <= 0 or (hi - lo) < GROUPING_X_OVERLAP * narrow:
                continue                                   # 가로로 안 겹친다 — 다른 줄기
            if b["box"][1] - a["box"][3] > GROUPING_MAX_GAP_EM * max(a["fs"], b["fs"]):
                break
            if (str(a.get("weight", "")).strip() not in ("700", "bold")
                    and str(b.get("weight", "")).strip() in ("700", "bold")):
                rows.append((a["s"].strip()[:20], b["s"].strip()[:20],
                             round(a["box"][1], 1), round(b["box"][1], 1)))
            break                                          # 바로 아래 이웃 하나만 본다
    return rows


def _holds_drawing(cell, shapes, segments):
    """이 칸 안에 **그림**(다른 채운 도형·선)이 함께 들어 있는가. 순수 함수.

    테두리와 겹치는 선은 그 칸 자신의 외곽이므로 세지 않는다(`BOX_INNER_MARGIN`).
    """
    x0, y0, x1, y1 = cell
    ix0, iy0 = x0 + BOX_INNER_MARGIN, y0 + BOX_INNER_MARGIN
    ix1, iy1 = x1 - BOX_INNER_MARGIN, y1 - BOX_INNER_MARGIN
    for sx0, sy0, sx1, sy1 in shapes:
        if (sx0, sy0, sx1, sy1) == cell:
            continue
        if sx0 >= ix0 and sy0 >= iy0 and sx1 <= ix1 and sy1 <= iy1:
            return True
    for seg in segments:
        ax, ay, bx, by = seg[0], seg[1], seg[2], seg[3]
        if (ix0 <= ax <= ix1 and iy0 <= ay <= iy1
                and ix0 <= bx <= ix1 and iy0 <= by <= iy1):
            return True
    return False


def figure_box_centering(svg, hide_reveal=False):
    """칸별 (칸, 덩어리 높이, 위 여백, 아래 여백, 어긋남, 최대 fs, 미리보기). 순수 함수.

    판정과 **재기**를 갈라 둔다 — 감사(`audit_figure_balance`)가 문턱 아래 값까지 보여 줘야
    규격을 데이터로 정할 수 있다. 판정만 내보내면 '왜 그 문턱인가'를 아무도 되짚을 수 없다.

    ★★ `hide_reveal` — **독자가 처음 보는 상태**로 잰다 (열린 날 2026-08-04, 사용자 재지적:
      [사용자 발화 인용 생략]). 문풀 삽화의 조건 수치는 `data-reveal` 이라
      뷰어가 `visibility:hidden` 으로 가려 두고 버튼을 눌러야 나온다. 정적 SVG 만 재면
      **화면에 없는 글자까지 덩어리에 넣어** 중앙을 계산하므로, 기본 화면에서는 오히려 치우친다.
      실측 사고: `fig-p08-bourdon-stack` 을 두 줄 기준으로 맞췄더니 기본 화면의 `탱크` 한 줄이
      **12px 위로** 떴다 — *검사를 통과시키려고 데이터를 나쁘게 만든* 형태다.
      → 두 상태를 **모두** 본다. 한쪽만 보면 반대쪽이 조용히 어긋난다.
    """
    head = svg[svg.find("<svg"):svg.find(">") + 1]
    vb = _attr(head, "viewBox")
    if not vb:
        return []
    try:
        viewbox = [float(v) for v in vb.split()]
    except ValueError:
        return []
    return [(cell, bot - top, top - cell[1], cell[3] - bot, off, fs, preview)
            for cell, _shown, (top, bot, off, fs, preview) in _box_cells(svg, viewbox, hide_reveal)]


def _box_cells(svg, viewbox, hide_reveal=False):
    """칸마다 (칸, 보이는 글자들, 세로 요약) 을 흘린다 — **세로 자와 가로 자가 함께 쓰는 몸통**.

    ★ 왜 떼어냈나 (2026-08-13): 가로 중앙 자를 새로 만들면서 이 판정(무엇이 «칸» 인가 ·
      패널 제외 · 그림 든 칸 제외 · 가려진 줄 처리)을 두 벌로 적을 뻔했다. **두 곳에 적으면
      갈라진다** — 이 리포가 자를 만들 때마다 겪은 부류라 몸통을 하나로 둔다.
    """
    shapes = _svg_filled_shapes(svg, viewbox)
    if not shapes:
        return []
    frac = [(s, e) for s, e, _b in _tagged_group_spans(svg, ("frac",))]
    groups = {}
    for it in _svg_texts(svg):
        if not it["s"].strip():
            continue
        if any(s <= it["pos"] < e for s, e in frac):
            continue                      # 분자·분모는 한 덩어리라 따로 세지 않는다
        it["hidden"] = "data-reveal" in svg[it["pos"]:it["end"]]
        it["box"] = _text_bbox(it)
        # 세로 중심은 **잉크**로 잰다 — 위 BOX_INK_ASCENT 주석이 정본(자가 둘이던 자리다).
        it["ink"] = (it["y"] - it["fs"] * BOX_INK_ASCENT,
                     it["y"] + it["fs"] * BOX_INK_DESCENT)
        cell = _container_of(it, shapes)
        if cell is not None:
            groups.setdefault(cell, []).append(it)
    segments = _svg_segments(svg)
    out = []
    for cell in sorted(groups):
        items = groups[cell]
        _x0, y0, _x1, y1 = cell
        top = min(i["ink"][0] for i in items)
        bot = max(i["ink"][1] for i in items)
        if top < y0 or bot > y1:
            continue                      # 칸을 넘치는 글자 — '담긴 것'이 아니다
        block = bot - top
        # ★★ **무엇이 '칸'인지는 저자가 거기 넣은 글 전체로 정하고, 중앙인지는 독자가 보는
        #   상태로 잰다** (2026-08-04, 첫 구현이 여기서 빗나갔다). 가려지는 줄을 빼고 나면 한 줄만
        #   남아 높이비가 커지는데, 그것을 '패널'로 읽으면 **바로 그 어긋난 화면이 검사 밖**이 된다
        #   (`fig-p08-bourdon-stack` 실측: 두 줄이면 비 2.8 로 칸, `탱크` 한 줄이면 6.5 로 패널).
        #   자격은 전체로, 측정은 부분으로 — 둘을 갈라야 두 상태를 다 볼 수 있다.
        if block <= 0 or (y1 - y0) > BOX_CENTER_MAX_RATIO * block:
            continue                      # 패널이지 칸이 아니다 (위 주석이 정본)
        if _holds_drawing(cell, shapes, segments):
            continue                      # 그림이 함께 든 칸 — 글자는 그 그림을 가리킨다
        shown = [i for i in items if not (hide_reveal and i["hidden"])]
        if not shown:
            continue                      # 기본 화면에 아무 글자도 없는 칸
        top = min(i["ink"][0] for i in shown)
        bot = max(i["ink"][1] for i in shown)
        out.append((cell, shown,
                    (top, bot, ((top + bot) - (y0 + y1)) / 2.0,
                     max(i["fs"] for i in shown),
                     " / ".join(i["s"].strip()[:14] for i in shown[:3]))))
    return out


def figure_box_centering_x(svg, hide_reveal=False):
    """칸별 **가로** 어긋남 — (칸, 덩어리 폭, 왼 여백, 오른 여백, 어긋남, 최대 fs, 미리보기).

    ★★ **왜 이 자가 생겼나 (2026-08-13, 사용자 재지적).** C28 이 **세로만** 보고 있었다 —
      신고 문구가 전부 [사용자 발화 인용 생략] 다. 그래서 `기체`·`진공` 처럼 가로로
      치우친 글자는 **아무도 안 봤고**, 같은 지적이 되풀이됐다. 사용자: [사용자 발화 인용 생략] → **또 빠뜨린 것이 아니라 자가 반쪽이었다.**
    ★ 세로는 **잉크**로 재고(어센트·디센트가 글꼴마다 다르다) 가로는 **글자 상자**로 잰다 —
      가로에서는 상자 폭이 곧 잉크 폭에 가깝다.
    ★ **줄마다 x 앵커가 다른 칸은 대상이 아니다** — 왼쪽 정렬해 둔 목록을 가운데로 끌면
      그게 결함이다. 줄 중심이 1em 넘게 흩어져 있으면 «저자가 정렬해 놓은 것»으로 본다.
    """
    head = svg[svg.find("<svg"):svg.find(">") + 1]
    vb = _attr(head, "viewBox")
    if not vb:
        return []
    try:
        viewbox = [float(v) for v in vb.split()]
    except ValueError:
        return []
    rows = []
    for cell, shown, _vert in _box_cells(svg, viewbox, hide_reveal):
        x0, _y0, x1, _y1 = cell
        lefts = [i["box"][0] for i in shown]
        rights = [i["box"][2] for i in shown]
        fs = max(i["fs"] for i in shown)
        mids = [(l + r) / 2.0 for l, r in zip(lefts, rights)]
        if len(mids) > 1 and (max(mids) - min(mids)) > fs:
            continue                      # 줄마다 앵커가 다르다 — 저자가 정렬해 놓은 것이다
        left, right = min(lefts), max(rights)
        if left < x0 or right > x1:
            continue                      # 칸을 넘치는 글자 — '담긴 것'이 아니다
        rows.append((cell, right - left, left - x0, x1 - right,
                     ((left + right) - (x0 + x1)) / 2.0, fs,
                     " / ".join(i["s"].strip()[:14] for i in shown[:3])))
    return rows


def figure_box_center_x_hits(svg):
    """칸 안 덩어리가 칸의 **가로** 중앙에서 벗어난 자리 — (사유, 미리보기). 순수 함수."""
    hits, seen = [], set()
    states = [("", figure_box_centering_x(svg))]
    if "data-reveal" in svg:
        states.append(("기본 화면(조건 수치 가림)에서 ",
                       figure_box_centering_x(svg, hide_reveal=True)))
    for label, rows in states:
        for cell, _block, gap_l, gap_r, off, fs, preview in rows:
            if abs(off) <= BOX_CENTER_TOL_EM * fs:
                continue
            if (cell, round(off, 2)) in seen:
                continue
            seen.add((cell, round(off, 2)))
            hits.append((
                label
                + "칸 안 글자가 칸의 가로 중앙이 아니다 — 왼 %.1f vs 오른 %.1f (%s %.1fpx · 허용 %.1f). "
                "칸 x=%.0f~%.0f 의 중앙에 덩어리 중심을 맞출 것"
                % (gap_l, gap_r, "왼쪽으로" if off < 0 else "오른쪽으로", abs(off),
                   BOX_CENTER_TOL_EM * fs, cell[0], cell[2]),
                preview))
    return hits


def figure_box_center_hits(svg):
    """칸 안 덩어리가 칸의 세로 중앙에서 벗어난 자리 — (사유, 미리보기). 순수 함수.

    **두 상태를 다 본다** — 조건 수치를 펼친 정적 SVG 와, 독자가 처음 보는 가려진 상태.
    한쪽만 맞추면 반대쪽이 조용히 어긋난다(위 `figure_box_centering` 독스트링이 정본).
    """
    hits = []
    seen = set()
    states = [("", figure_box_centering(svg))]
    if "data-reveal" in svg:
        states.append(("기본 화면(조건 수치 가림)에서 ", figure_box_centering(svg, hide_reveal=True)))
    for label, rows in states:
        for cell, _block, gap_top, gap_bot, off, fs, preview in rows:
            if abs(off) <= BOX_CENTER_TOL_EM * fs:
                continue
            if (cell, round(off, 2)) in seen:
                continue                  # 두 상태가 같은 어긋남을 내면 한 번만 신고한다
            seen.add((cell, round(off, 2)))
            hits.append((
                label
                + "칸 안 글자가 칸의 세로 중앙이 아니다 — 위 %.1f vs 아래 %.1f (%s %.1fpx · 허용 %.1f). "
                "칸 y=%.0f~%.0f 의 중앙에 덩어리 중심을 맞출 것"
                % (gap_top, gap_bot, "위로" if off < 0 else "아래로", abs(off),
                   BOX_CENTER_TOL_EM * fs, cell[1], cell[3]),
                preview))
    return hits

# ★ 삽화 글자 크기는 절대 px이 아니라 **화면 실효 크기**로 잰다 (열린 날 2026-07-28).
#
# 사용자 지적 두 개가 상반돼 보였다 — [사용자 발화 인용 생략](문풀)과
# [사용자 발화 인용 생략](연습문제). **둘 다 맞았다.**
#
# 뷰어가 `.diagram-box svg{width:100%}` 로 SVG를 컨테이너 폭에 맞춰 스케일한다. 그러므로
# 화면에서 보이는 크기는 `font-size x (박스폭 / viewBox폭)` 이고, **SVG 안의 절대 px은
# 화면 크기와 아무 관계가 없다.** 예전 검사(`12px 미만` error · `16px 초과` warn)는
# 잴 수 없는 것을 재고 있었고, 그래서 [사용자 발화 인용 생략] 와 [사용자 발화 인용 생략] 가 동시에 참일 수 있었다.
#
# 실측(2026-07-28): 문풀 `fig-01-p01` 20.4px vs 연습문제 `fig-ch01-q09` 9.97px —
# 둘 다 12~16px 범위 안이라 예전 검사는 **한 건도 잡지 못했다**. 게다가 연습문제 박스만
# 460px이라 격차가 더 벌어져 있었다(뷰어에서 640px로 통일했다).
#
# 부작용 하나를 의도적으로 없앤다: 예전 절대 하한 12px은 **작은 viewBox 삽화에 큰 글자를
# 강요**했다(viewBox 320이면 12px이 화면 22.9px). 검사가 결함을 유도하던 자리다.
FIGURE_RENDER_WIDTH = 612.0     # .diagram-box max-width 640 - padding 14*2
DIMENSION_LINE_MAX_WIDTH = 1.5   # 치수선·치수보조선은 형상선(2~2.5)보다 가늘어야 구별된다

# ★ 파선이 허용되는 **역할** 목록 (신설 2026-07-30, ch02 이관 중 확장).
#
# 규칙의 요지는 [사용자 발화 인용 생략] 이지 [사용자 발화 인용 생략] 가 아니다.
# 처음에는 `dim`·`hidden-edge` 둘만 뒀는데, ch02 를 훑어 보니 **치수도 숨은선도 아닌**
# 정당한 파선이 세 종류 더 있었다 — 이걸 전부 실선으로 바꾸면 구분선이 진짜 외곽선처럼 보인다.
# 어휘가 모자라서 데이터를 틀리게 고칠 뻔한 것이므로, 완화가 아니라 **어휘를 채우는 것**이다.
#   dim/measure — 치수선·치수보조선. 파선이면 기존 L2 가 따로 잡는다(가는 실선이 규격).
#   hidden-edge — 가려진 형상. 파선이 맞는 유일한 '형상' 역할.
#   datum       — 기준면·중심선. 제도에서도 실선과 구별되는 선을 쓴다.
#   divider     — 패널·영역 구분선. 도형이 아니라 편집 요소다.
#   guide       — 투영선·대응선처럼 두 지점을 눈으로 잇는 보조선.
#   phantom     — '이전 위치'·가상 위치. 제도의 가상선이 맡는 자리라 파선이 **정본**이다
#                 (실선으로 그리면 지금 거기 물체가 있다는 뜻이 된다 — 틀린 그림).
#   axis        — **중심선**(1점 쇄선). 축·구멍의 중심을 가리키고 **형상을 가로지르는 것이 정상**이다
#                 (치수가 가장자리가 아니라 축을 잰다는 표시). 실선으로 그리면 원을 관통하는
#                 막대로 읽힌다 — 2026-08-23 사용자 3회차 지적이 정확히 그 자리였다
#                 (`checks_svg.centerline_style_issues` 주석이 정본).
# 새 역할을 추가할 때는 **왜 파선이어야 하는지**를 여기 한 줄로 남길 것.
# ★ 파선이 **정당한** 역할 (2026-07-30 분리). 이 다섯은 파선으로 그리는 것이 규격이다.
# `dim`·`measure` 는 여기 없다 — 치수 계열은 **가는 실선**이 규격이라, 파선이면 위반이고
# L2 가 따로 잡는다. 두 목록을 갈라 둔 이유: `audit_conventions.py` 의 [A] 감사가
# "파선인데 신고해야 하는가"를 물을 때 필요한 것은 **정당한 역할 목록**이기 때문이다.
# 예전에는 감사가 `hidden-edge` 하나만 알아서 datum·guide·divider·phantom 을 매번 신고했고,
# 그 11건이 영구 잡음으로 남아 있었다(실측 2026-07-30 ch02 10건·ch05 1건).
# **역할을 추가할 때는 이 목록에만 추가한다** — 감사와 빌드가 같은 것을 본다.
DASH_LEGIT_ROLES = ("hidden-edge", "datum", "divider", "guide", "phantom", "axis")
DASH_ROLES = ("dim", "measure") + DASH_LEGIT_ROLES
FIGURE_TEXT_MIN_PX = 13.0
FIGURE_TEXT_MAX_PX = 19.0

# ★ 화살표 크기 규격 — **화면 실효 px** (신설 2026-08-02). 근거는 전 챕터 실측이다:
#   ch01 화살촉 137개의 **중앙값 12.8**, 사용자가 좋다고 본 `fig-abs-gage-vacuum-bars` **13.6**,
#   [사용자 발화 인용 생략] 이라 지적한 `fig-state-postulate-plane` **19.1**.
#   → 중심 13.5, 허용 11~16. 19.1·20.4 는 걸리고 13.6 은 통과한다.
# 폭은 길이에 비례해야 삼각형 인상이 일정하다(실측 대부분 폭 = 길이).
# 꼬리는 사용자 지적 [사용자 발화 인용 생략] — 실측 `fig-adiabatic-vs-isothermal` 6.7px 로
#   **화살촉(13.3)의 절반**이었다. 머리보다 짧은 꼬리는 화살표로 안 읽힌다 → 1.5배를 하한으로.
# ★ 하한은 **11 → 8 로 낮췄다** (같은 날, 첫 적용에서 곧바로 드러났다).
#   11 로 잡으니 `fig-closed-open-isolated` 의 화살촉 12개가 8.4 → 13.5 로 커졌고,
#   그 삽화는 **✗ 표식을 화살표 위에 얹는 설계**라 커진 머리와 겹쳐 빌드가 깨졌다.
#   사용자가 지적한 것은 [사용자 발화 인용 생략](19.1)와 [사용자 발화 인용 생략] 였지 저 삽화가 아니다.
#   → **상한과 꼬리 비율이 이 규격의 본체**이고, 하한은 '보이지도 않는 머리'만 거른다.
#   (AGENTS 「검사가 결함을 유도하던 자리」 — 지적받지 않은 삽화를 흔드는 규격은 규격이 아니다.)
ARROW_HEAD_MIN_PX = 8.0
ARROW_HEAD_MAX_PX = 16.0
ARROW_HEAD_TARGET_PX = 13.5
ARROW_WIDTH_RATIO_MIN = 0.7
ARROW_WIDTH_RATIO_MAX = 1.3
# ★★★ **치수 화살촉은 방향 화살촉보다 가늘다 — 폭 비는 아래 상수 옆 주석이 정본이다.**
#   대상은 `class='dim'`·`id='dim-…'` 로 **저자가 선언한** 그룹 안의 화살촉뿐이다 —
#   이름으로 추측하지 않는다(태깅이 없으면 규격이 안 걸리는 것은 치수선 자체와 같은 규약).
#   왜 갈랐나: 치수 화살촉은 [사용자 발화 인용 생략] 를 가리키는 표식이라 잉크가 적을수록 좋고,
#   방향 화살촉은 [사용자 발화 인용 생략] 라는 뜻을 실어야 해서 면적이 필요하다. 한 밴드로 묶으면
#   둘 중 하나는 반드시 어색해진다 — 그게 사용자가 두 번 짚은 그 느낌이었다.
# 치수 라벨과 자기 치수선 사이의 **글자 상자** 하한. 일반 라벨(0.5em)과 다른 이유는
# 아래 F1 주석이 정본이다 — 제도에서 치수 문자는 치수선에 바짝 붙는다.
# ★ 값이 작아 보이는 이유: 이 자는 **글자 상자**로 재는데 상자는 디센더 자리만큼 잉크보다
#   아래로 내려간다. `ℓ`·숫자처럼 디센더가 없는 글자는 상자 0.10em 이 **잉크로는 0.3em** 이다.
#   (잉크로 재는 자로 바꾸는 것이 옳지만 그건 F1 전체를 손대는 일이라 따로 판정받는다.)
DIM_LABEL_GAP_MIN_EM = 0.10
# ★★ 폭 비 — **0.60 으로 정착했다 (2026-08-13, 네 번의 판정을 거쳤다).**
#   ⑴ 1.00 → 0.80(지적한 자리만) ⑵ [사용자 발화 인용 생략] → 관례 3:1 근거로 **0.35**, 전 챕터
#   ⑶ [사용자 발화 인용 생략] → [사용자 발화 인용 생략] → 0.80 복구 ⑷ [사용자 발화 인용 생략] → **0.60**
#   ★ 0.60 은 관례(0.33)와 원래 값(0.80) 사이에서 **사용자가 화면을 보고 고른 값**이다.
#   ★★ 값을 근거만 보고 되돌리지 말 것 — ⑵ 가 정확히 그 실패다. 관례는 종이·잉크의 자이고
#     이 자료는 화면이라, **관례는 출발점이고 판정은 눈이 한다.**
DIM_ARROW_WIDTH_RATIO_MIN = 0.50
DIM_ARROW_WIDTH_RATIO_MAX = 0.72
DIM_ARROW_WIDTH_RATIO_TARGET = 0.60
ARROW_TAIL_MIN_RATIO = 1.5

# ★ 본문 대비 하한 (신설 2026-07-30). 사용자 지적이 두 방향으로 왔다:
#   2026-07-29 [사용자 발화 인용 생략] → 캡션을 라벨의 0.85배로 일괄 축소
#   2026-07-30 [사용자 발화 인용 생략]
# **두 지적 다 맞다.** 어긋난 것은 위계가 아니라 **바닥**이었다.
# 실측(2026-07-30, 브라우저 getComputedStyle): 이론 본문 15.5px · 문제 본문 15px.
# 그런데 삽화 글자 규격의 하한은 13px이라, **삽화 라벨이 본문보다 작아도 규격을 통과**했다.
# ch01 실측 라벨 평균은 12.8~16.3px — 절반이 본문보다 작았다. '작게 느껴진다'가 아니라 작았다.
#
# 원칙: **삽화 라벨은 본문보다 작지 않다.** 캡션은 라벨의 0.85배이므로 15.5×0.85 ≈ 13.2 로
# 기존 하한 13과 어긋나지 않는다 — 두 규격이 동시에 성립하는 값으로 잡았다.
#
# 왜 에러가 아니라 경고인가: 하한을 올리면 ch02~05 삽화가 한꺼번에 규격 밖이 된다.
# 거기서 **에러를 내면 빌드가 통째로 멈춰 사용자가 검수를 못 한다.** 이관이 끝날 때까지
# 경고로 두어 빚을 보이게 하되(경고는 close 를 막는다) 진행은 막지 않는다.
# ★ 15.0 → 15.5 상향 (2026-07-30, 사용자 4회째 지적).
# 본문 실측이 **이론 15.5px · 문제 15px** 인데 하한을 15.0 으로 잡았더니, 라벨이 15.0~15.4 인
# 삽화가 '규격 통과'로 남았다 — 사용자는 그걸 계속 작다고 했다. 하한을 **본문 최대치**에 맞춘다.
# 하한은 '이 정도면 봐준다'가 아니라 '본문과 같은 크기'라는 뜻이어야 한다.
FIGURE_TEXT_BODY_PX = 15.5

# 캡션 판정 — `fix_figure_caption_tier.py` 와 **같은 규약**이어야 한다(갈리면 서로 다른 것을 잰다).
# 굵지 않고 한글 6음절 이상이면 캡션이다. 글자 수로만 재면 `0 K, -273.15°C` 가 캡션으로 잡힌다.
_HANGUL_RE = re.compile(r"[가-힣]")


_GLOSS_RE = re.compile(r"^\([A-Za-z][A-Za-z0-9 /·\-]*\)$")


def _is_caption_text(t):
    if str(t.get("weight", "")) == "700":
        return False                                   # 굵으면 제목이다
    body = (t.get("s", "") or "").strip()
    # ★ 원어 병기는 라벨의 **하위 단**이다 (신설 2026-07-30).
    # `경계` 아래 `(boundary)`, `주위` 아래 `(surroundings)` 처럼 괄호만으로 이루어진 라틴문자
    # 병기는 그 위 한글 용어를 보조하는 글자다 — 본문 크기를 강제하면 위계가 뒤집힌다.
    # 한글 음절 수로만 캡션을 판정하던 규칙의 구멍이었다(병기는 한글이 0음절이라 라벨로 잡혔다).
    # 범위를 좁게 잡는다: **괄호로 시작해 괄호로 끝나는 라틴문자 덩어리**만.
    if _GLOSS_RE.match(body):
        return True
    return len(_HANGUL_RE.findall(body)) >= 6


def _scaled_font_size(raw, parent):
    """`font-size` 한 값을 **부모 기준 SVG px** 로 푼다. 순수 함수.

    `%`·`em` 은 부모에 곱하고, 그 밖의 수치(`10`·`10px`)는 절대값이다. 못 읽으면 부모를 잇는다
    — 모르는 꼴을 0 이나 기본값으로 떨어뜨리면 **첨자가 통째로 규격 밖으로 잡힌다.**
    """
    if not raw:
        return parent
    raw = raw.strip()
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(%|em|rem|px|pt)?", raw)
    if not m:
        return parent
    value = float(m.group(1))
    unit = m.group(2)
    if unit == "%":
        return parent * value / 100.0
    if unit in ("em", "rem"):
        return parent * value
    if unit == "pt":
        return value * 4.0 / 3.0
    return value


def text_runs(t):
    """`<text>` 하나를 **글자 조각**으로 편다 — 조각마다 자기 실효 SVG font-size 를 단다.

    순수 함수 — 테스트가 직접 부른다. 돌려주는 각 조각은
    `s`(보이는 글자) · `fs`(실효 SVG px) · `depth`(0 이면 `<text>` 직속, 1 이상이면 tspan 안) ·
    `dy`(그 조각을 감싼 tspan 들의 **자기 dy 합**) · `own_dy`(가장 안쪽 tspan 의 dy).

    ★ **열린 날 2026-08-13 — 첨자 크기를 아무도 재지 않고 있었다.**
      사용자: [사용자 발화 인용 생략] 실측이 그대로였다 —
      `fig-q13-piston-spring-fbd` 는 viewBox 폭 380 이라 화면 배율이 612/380 = 1.61 이고,
      부모 `<text font-size='10'>` 은 실효 16.1px 로 규격(13~19)을 **통과**하는데
      `font-size='78%'` 첨자는 7.8 SVG px → 실효 **12.6px** 로 하한 미만이었다.
      `check_svg` 는 [사용자 발화 인용 생략] 고
      주석에 적어 두고 정말로 부모만 쟀다 — **빠뜨림이 아니라 빠뜨려도 통과되는 구조**다(규칙 7⑷).
      자를 넓혀 첨자도 같은 눈금(화면 실효 px)으로 재게 한다.

    `run_width` 와 **같은 토큰 순회**를 쓴다(둘이 갈라지면 폭과 크기가 다른 것을 잰다).
    """
    runs = []
    fs = float(t.get("fs") or 12.0)
    stack = []
    cur_fs, cur_dy, own_dy = fs, 0.0, 0.0
    for m in re.finditer(r"<[^>]+>|[^<]+", t.get("raw", "") or ""):
        token = m.group(0)
        if not token.startswith("<"):
            plain = (token.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))
            if plain.strip():
                runs.append({"s": plain, "fs": cur_fs, "depth": len(stack),
                             "dy": cur_dy, "own_dy": own_dy})
        elif token.startswith("</"):
            if stack:
                cur_fs, cur_dy, own_dy = stack.pop()
        elif not token.endswith("/>"):
            stack.append((cur_fs, cur_dy, own_dy))
            cur_fs = _scaled_font_size(_attr(token, "font-size"), cur_fs)
            try:
                own_dy = float(_attr(token, "dy", "0") or 0.0)
            except ValueError:
                own_dy = 0.0
            cur_dy += own_dy
    return runs


# ★ 첨자 하한 — **본문 하한과 따로 두되, 실측해 보니 거의 같은 값이 나왔다** (신설 2026-08-13).
#
# 물음은 둘이었다. ⓐ 첨자에 본문 하한 13px 을 그대로 씌워도 되나 ⓑ 아니면 첨자용 눈금을
# 따로 둬야 하나. **분포를 먼저 봤다**(전 챕터 tspan 조각 **347**개 · tspan 을 가진 삽화 **94**개):
#
#     하한 후보   걸리는 조각 / 삽화        비고
#     12.09px       15 / 3      = 15.5 × 0.78. 본문 바짜리 라벨의 78% 첨자
#     12.6px        70 / 27
#     12.7px        81 / 30
#     12.9px        91 / 34
#     13.0px        93 / 36     = 본문 하한 그대로
#
# ★ 판정 ⓐ — **따로 두어 아끼는 것이 삽화 3개뿐이다.** 12.9 와 13.0 의 차이가 조각 2개·삽화
#   2개라, [사용자 발화 인용 생략] 는 별도 눈금을 만들 값어치가 없다. 느슨한 쪽(12.09)은
#   사용자가 [사용자 발화 인용 생략] 고 지적한 `fig-q13-piston-spring-fbd` 의 **12.6px 을 통과시킨다** —
#   지적을 재현하지 못하는 하한은 하한이 아니다.
# ★ 판정 ⓑ — 그래도 **상수는 따로 둔다.** 값이 우연히 가까운 것이지 같은 근거가 아니기 때문이다.
#   본문 하한 13.0 은 *읽히는 최소 크기*이고, 이 값은 **두 기존 바를 곱해서 나온다**:
#       본문 바 `FIGURE_TEXT_BODY_PX` 15.5  ×  이 리포가 삽화 첨자에 쓰는 비율 0.83
#       (`SUPERSCRIPT_RATIO`, 산문 <sup> 실측에서 온 값) = **12.87 → 12.9**
#   즉 [사용자 발화 인용 생략] 다.
#   ★ 상수를 곱셈식으로 **쓰지 않고** 숫자로 박는다 — `SUPERSCRIPT_RATIO` 는 조판용이라
#     누가 바꾸면 이 자가 조용히 느슨해진다(자를 남의 상수에 매달지 않는다).
#
# ★★ **처방은 라벨 확대가 아니라 비율 상향이다.** 걸린 91 조각의 대부분은 부모 라벨이 규격
#   안(13~19)인데 78% 가 작아서 걸린다 — 78 → 83% 로 올리면 12.2~12.7 이 13.0~13.5 로 올라온다.
#   그러고도 남는 것은 **부모가 본문 바 15.5 미만인 삽화**뿐이고, 그건 이미 `FIGURE_TEXT_BODY_PX`
#   가 따로 신고하는 결함이다. 두 자가 같은 곳을 가리키므로 규격끼리 안 부딪힌다.
# ★ 그래서 **경고로 연다.** 34개 삽화를 한꺼번에 error 로 박으면 데이터를 쥔 세션의 빌드가
#   멈춘다(`MIDDOT_STRICT_CHAPTERS` 실사고와 같은 부류). 승격은 과목별·챕터별
#   (`data/<과목>/index.json` 의 `strictChapters.subtext_scale`)이고, 경고는 `close_report` 가
#   close 를 막으므로 묻히지 않는다.
FIGURE_SUBTEXT_MIN_PX = 12.9


def figure_text_scale_issues(fig_id, view_width, texts):
    """화면 실효 크기가 규격 밖인 글자를 신고한다. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    if not view_width:
        return out
    lo = FIGURE_TEXT_MIN_PX * view_width / FIGURE_RENDER_WIDTH
    hi = FIGURE_TEXT_MAX_PX * view_width / FIGURE_RENDER_WIDTH
    for t in texts:
        eff = t["fs"] * FIGURE_RENDER_WIDTH / view_width
        if eff < FIGURE_TEXT_MIN_PX or eff > FIGURE_TEXT_MAX_PX:
            out.append(
                fig_id + ": 글자 화면 실효 " + format(eff, ".1f") + "px — 규격 13~19px"
                + " (viewBox 폭 " + format(view_width, ".0f") + "이면 font-size "
                + format(lo, ".1f") + "~" + format(hi, ".1f") + ") — " + repr(t["s"][:20]))
    return out


def figure_subtext_scale_issues(fig_id, view_width, texts):
    """`<tspan>` 첨자의 화면 실효 크기를 잰다. 순수 함수 — 테스트가 직접 부른다.

    부모 `<text>` 는 `figure_text_scale_issues` 가 이미 본다. 여기는 **그 자가 못 보던 자리** —
    `font-size='78%'` 처럼 부모에 상대적인 크기라 부모가 규격을 통과해도 첨자는 뭉개질 수 있다.
    상한은 두지 않는다: 첨자가 부모보다 커지는 일은 데이터에 없고, 커진다면 그건 첨자가 아니라
    부모 크기 문제라 위 검사가 잡는다.
    """
    if not view_width:
        return []
    scale = FIGURE_RENDER_WIDTH / view_width
    # ★ **같은 크기의 첨자는 한 줄로 묶는다.** 한 삽화가 같은 비율을 열 번 쓰면 고칠 자리는
    #   하나인데 신고가 열 줄이 된다 — 빌드가 도는 자리마다 그만큼이 문맥에 다시 실린다
    #   (실행 규율 12: 비싼 것은 왕복 수가 아니라 출력의 크기다). 실측 91 조각 → 40 줄.
    groups = {}
    for t in texts:
        for run in text_runs(t):
            if run["depth"] == 0:
                continue                       # 부모 <text> 몫은 위 검사가 본다
            if run["fs"] * scale < FIGURE_SUBTEXT_MIN_PX:
                groups.setdefault(round(run["fs"], 4), []).append(run["s"].strip()[:20])
    out = []
    need = FIGURE_SUBTEXT_MIN_PX / scale
    for fs in sorted(groups):
        labels = sorted(set(groups[fs]))
        # ★ 소수 **두 자리**로 찍는다 — 첨자 크기는 부모 × 비율이라 값이 하한에 0.05px 차이로
        #   붙는 경우가 실제로 나온다(실측 3건). 한 자리로 찍으면 [사용자 발화 인용 생략] 처럼
        #   **검사가 고장 난 것처럼 읽힌다.**
        out.append(
            fig_id + ": 첨자 화면 실효 " + format(fs * scale, ".2f") + "px — 하한 "
            + format(FIGURE_SUBTEXT_MIN_PX, ".2f") + "px"
            + " (viewBox 폭 " + format(view_width, ".0f") + "이면 font-size "
            + format(need, ".2f") + " 이상, 지금 " + format(fs, ".2f") + ")"
            + " — " + str(len(groups[fs])) + "곳: " + ", ".join(repr(s) for s in labels[:6])
            + (" 외" if len(labels) > 6 else ""))
    return out


def figure_subtext_scale_hits(fig_id, svg):
    """SVG 한 장의 첨자 크기 위반. `check_content` 의 삽화 순회가 부른다(`…_hits` 규약).

    판정은 위 `figure_subtext_scale_issues` 하나뿐이다 — 여기서 다시 재면 자가 둘로 갈라진다.
    """
    head = svg[svg.find("<svg"):svg.find(">") + 1] if "<svg" in svg else ""
    vb = _attr(head, "viewBox")
    if not vb:
        return []                        # viewBox 없음은 `check_svg` 가 이미 신고한다
    try:
        view_width = float(vb.split()[2])
    except (IndexError, ValueError):
        return []
    return figure_subtext_scale_issues(fig_id, view_width, _svg_texts(svg))


# 뷰어가 삽화를 그리는 폭 — 화면 실효 크기를 재는 분모다(`figure_text_scale_issues` 와 같은 값).
VIEWER_FIGURE_WIDTH = 612.0
# 글자와 viewBox 가장자리 사이의 최소 여유(화면 실효 px). 치수 간격 4px 과 같은 눈금을 쓴다.
FIGURE_EDGE_MARGIN_PX = 4.0


def check_svg(fig_id, svg, errors, warnings, *, layout_strict=False, numeric_labels=None,
              halo_gap_strict=False, clearance_strict=False):
    out = errors if fig_id not in PENDING_FIG_FIXES else warnings
    vb = _attr(svg[svg.find("<svg"):svg.find(">") + 1], "viewBox")
    if not vb:
        out.append(fig_id + ": viewBox 없음")
        return
    vx, vy, vw, vh = [float(v) for v in vb.split()]
    texts = _svg_texts(svg)
    # 여기는 부모 `<text>` 만 본다. **첨자(`<tspan>`)는 `figure_subtext_scale_issues` 가 따로 잰다** —
    # 예전에는 이 자리에 [사용자 발화 인용 생략] 고
    # 적혀 있었는데, 그 문장이 곧 사각지대였다(경위는 `text_runs` 독스트링이 정본).
    # 첨자 쪽은 승격이 과목별이라 신고 통로가 갈린다 — 그래서 `checks_content` 의 삽화 순회에서 부른다.
    for issue in figure_text_scale_issues(fig_id, vw, texts):
        out.append(issue)
    boxes = [_text_bbox(t) for t in texts]
    for t, b in zip(texts, boxes):
        if b[0] < vx or b[1] < vy or b[2] > vx + vw or b[3] > vy + vh:
            out.append(fig_id + ": 글자 viewBox 이탈 — " + repr(t["s"][:20]))
    # ★★ **여유가 0이면 화면에서는 잘린다** (열린 날 2026-08-12, 사용자: [사용자 발화 인용 생략]).
    #   ★ 검사는 **이미 있었다** — 바로 위 「viewBox 이탈」이다. 그런데 그 자는 *넘었는가* 만
    #     보고 **딱 붙은 것은 통과**시킨다. 실측(브라우저 렌더): 그 캡션은 오른쪽 끝에 여유가
    #     사실상 0이라 이탈은 아니지만, 뷰어에서는 상자 테두리·반올림에 먹혀 잘려 보인다.
    #   판정 기준은 **화면 실효 px** 이다 — SVG 좌표는 viewBox 폭에 따라 뜻이 달라지므로
    #   글자 크기 검사(`figure_text_scale_issues`)와 같은 자(폭 612 기준)를 쓴다.
    edge = FIGURE_EDGE_MARGIN_PX * vw / VIEWER_FIGURE_WIDTH
    for t, b0 in zip(texts, boxes):
        if b0[0] < vx or b0[1] < vy or b0[2] > vx + vw or b0[3] > vy + vh:
            continue                      # 이미 이탈로 신고했다 — 두 번 세지 않는다
        b = _text_bbox(t, cjk_w=CJK_W_WORST)   # 잘림은 **최악 글꼴** 기준으로 본다
        gap = min(b[0] - vx, b[1] - vy, vx + vw - b[2], vy + vh - b[3])
        if gap < edge:
            out.append(fig_id + ": 글자가 viewBox 가장자리에 붙었다 — "
                       + repr(t["s"][:20]) + " · 여유 "
                       + format(gap * VIEWER_FIGURE_WIDTH / vw, ".1f")
                       + "px (화면 실효 " + format(FIGURE_EDGE_MARGIN_PX, ".0f")
                       + "px 이상 두어야 잘려 보이지 않는다)")
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if _rect_x_rect(boxes[i], boxes[j]):
                out.append(fig_id + ": 글자끼리 겹침 — " + repr(texts[i]["s"][:14]) + " x " + repr(texts[j]["s"][:14]))
    segs = _svg_segments(svg)
    # halo는 '선 위를 지나가도 읽힌다'는 예외일 뿐, 여백 규격의 면제가 아니다.
    # 2026-07-22: 여기서 halo 글자를 건너뛰는 바람에 paint-order가 붙은 라벨은
    # **여백 검사도 교차 검사도 받지 않았고**, 같은 겹침 지적이 4회 반복됐다
    # (fig-shaft-work-derivation '접선력 F'). 주석은 원래부터 이 규칙을 적고 있었는데
    # 코드가 반대로 되어 있었다 — 그래서 halo 예외는 아래 교차 검사에만 남긴다.
    # 분수선은 자기 분자·분모에게는 '선'이 아니다 — 그 둘 사이 간격은 조판이지 여백이 아니다.
    # 면제는 **같은 `<g class='frac'>` 안**에서만 성립한다(남의 라벨이 붙으면 그대로 걸린다).
    frac_bars = _fraction_bars(svg)
    # ★★ **치수 라벨은 자기 치수선에 붙는 것이 정상이다** (2026-08-13, 사용자 3회 지적).
    #   F1 의 0.5em 은 «라벨이 남의 선에 붙어 읽기 어렵다» 를 막는 자인데, 치수 라벨은
    #   그 반대다 — 제도에서 치수 문자는 치수선에 **바짝** 붙는다(그래서 이 리포에도
    #   「치수선 라벨은 0.94em(잉크)」 라는 **별도 규격**이 이미 있다).
    #   ★ 두 자가 서로 다른 것을 재고 있었다: 0.94em 은 **잉크**, F1 은 **글자 상자**다.
    #     글자 상자는 잉크보다 아래로 더 내려가므로(디센더 자리), 잉크로 0.94em 이어도
    #     상자로는 0.5em 을 못 넘는 자리가 생긴다 — 사용자가 «더 내려» 를 세 번 말한 이유다.
    #   ★ 완화가 아니라 **역할을 가른 것**이다. 대상은 `class='dim'`·`id='dim-…'` 안,
    #     즉 **저자가 치수라고 선언한** 글자뿐이고 나머지는 0.5em 그대로다
    #     (치수 화살촉에 별도 규격을 준 것과 같은 자리·같은 근거).
    dim_spans = [(s, e) for s, e, _b in _tagged_group_spans(svg, ("dim",))]
    for t, b in zip(texts, boxes):
        own = {seg for (gs, ge), seg in frac_bars if gs <= t["pos"] < ge}
        nearest = min((_segment_to_rect_distance(seg, b) for seg in segs if seg not in own),
                      default=None)
        in_dim = any(s <= t["pos"] < e for s, e in dim_spans)
        floor = (DIM_LABEL_GAP_MIN_EM if in_dim else .5)
        if nearest is not None and 0 < nearest < t["fs"] * floor:
            # halo 글자는 지금까지 이 검사를 아예 안 받았다. 한꺼번에 error로 올리면 기존
            # 챕터가 통째로 막히므로, 정리를 마친 챕터부터 halo_gap_strict 로 승격한다.
            hard = (layout_strict and (halo_gap_strict or not t["halo"])
                    and fig_id.split(" ")[0] not in PENDING_FIG_FIXES)
            (errors if hard else warnings).append(
                fig_id + ": [layout F1] text-to-line gap < %.2gem " % floor
                + ("(치수 라벨) " if in_dim else "") + repr(t["s"][:20]))
    for t, b in zip(texts, boxes):
        if t["halo"]:
            continue  # halo(paint-order:stroke) 적용 글자는 선 위에 있어도 읽힘 — 통과
        for s in segs:
            if _seg_x_rect(s, b):
                out.append(fig_id + ": 글자가 선/패스와 교차(halo 필요) — " + repr(t["s"][:20]))
                break
    for t, b in zip(texts, boxes):
        for shape in _svg_filled_shapes(svg, (vx, vy, vw, vh)):
            if not _rect_x_rect(b, shape):
                continue
            contained = shape[0] <= b[0] and shape[1] <= b[1] and shape[2] >= b[2] and shape[3] >= b[3]
            if not contained:
                out.append(fig_id + ": 글자가 도형 경계에 걸침 — " + repr(t["s"][:20]))
                break

    # z-order: 글자보다 나중에 그려진 불투명 도형이 글자를 덮는가 (겹침 지적 3회의 원인)
    for t, b in zip(texts, boxes):
        for sx0, sy0, sx1, sy1, spos in _svg_opaque_shapes_ordered(svg, (vx, vy, vw, vh)):
            if spos < t["pos"]:
                continue                                  # 글자보다 먼저 그려짐 = 배경
            ox = min(b[2], sx1) - max(b[0], sx0)
            oy = min(b[3], sy1) - max(b[1], sy0)
            if ox > 1 and oy > 1:
                out.append(fig_id + ": 글자가 뒤에 그려진 도형에 가려짐 — " + repr(t["s"][:20]))
                break

    # F4: 글자 상자를 선/패스가 지나간다. 위 '교차(halo 필요)' 검사와 대상은 같지만 halo 글자까지
    # 포함한다 — halo가 붙어 읽히더라도 '선이 지나간다'는 사실 자체는 남겨 두려는 경고다.
    #
    # 2026-07-26: 예전에는 전체를 any()로 접어 **어떤 글자인지 말하지 않았다.** 고칠 대상을
    # 특정할 수 없으니 이 경고는 '6-B 대기'로 무기한 방치됐다(ch02 fig-char-cases·fig-resonance가
    # 그 상태로 남아 있었다). 바로 위 두 검사(도형 경계 걸침 / 뒤 도형에 가려짐)는 처음부터
    # 글자를 찍고 있었다 — F4만 예외였다. 이름을 남기지 않는 경고는 고쳐지지 않는다.
    for t, b in zip(texts, boxes):
        if any(_seg_x_rect(seg, b) for seg in segs):
            warnings.append(
                fig_id + ": [layout F4] 글자 상자를 선이 지나감"
                + (" (halo 있음 — 의도한 것인지 확인)" if t["halo"] else " (halo 없음)")
                + " — " + repr(t["s"][:20]))
    # F6: 화살표-도형 관통·화살촉끼리 근접 (2026-07-22 신설 — 6회 반복 지적의 사각지대)
    for issue in _arrow_clearance_issues(svg, (vx, vy, vw, vh)):
        target = out if (clearance_strict and fig_id.split(" ")[0] not in PENDING_FIG_FIXES) \
            else warnings
        target.append(fig_id + ": [layout F6] " + issue)
    for issue in arc_arrowhead_issues(svg):
        target = out if (clearance_strict and fig_id.split(" ")[0] not in PENDING_FIG_FIXES) \
            else warnings
        target.append(fig_id + ": [layout F7] " + issue)
    values = _numeric_unit_labels(texts)
    if values and numeric_labels != "intentional":
        warnings.append(fig_id + ": [layout F5] numeric unit label without numericLabels:intentional "
                        + repr(values[0][:20]))

def _svg_path_signature(dstr):
    """Return SVG command letters and numeric arguments without interpreting geometry."""
    tokens = re.findall(r"[MLHVZCSQTAmlhvzcsqta]|-?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?", dstr, re.I)
    return [t for t in tokens if t.isalpha()], [t for t in tokens if not t.isalpha()]

# ── 지시선(leader) — AGENTS 삽화 표준 「지시선」 (열린 날 2026-08-06) ────────────
#
# 사용자: [사용자 발화 인용 생략]
#
# **관찰이 맞았다** — 이 리포의 삽화는 라벨을 대상 옆에 붙이는 방식뿐이고, 대상을 가리키는
# 선은 치수선(`class='dim'`) 밖에 없었다. 1:1 근접 배치가 기본인 것은 옳지만(지시선은 잉크와
# 교차를 늘린다), ⑴ 대상이 작아 옆에 글자를 못 놓을 때 ⑵ 설명 하나가 여러 대상을 가리킬 때
# ⑶ 겹쳐 있어 모호할 때는 지시선이 필요하다.
#
# ★ **왜 하나도 없었나 — 규격이 없어서다.** 화살표·치수선·라벨 여백에는 규격이 있는데
#   지시선 항목이 없었다. 규격이 없으면 그릴 때마다 갈라지므로 안 쓰는 쪽이 안전했던 셈이다.
#   그래서 규격을 두고 **태깅한 것만** 잰다(`class='dim'` 선례 — 태깅이 없으면 아무도 안 본다).
LEADER_MAX_WIDTH = 1.2        # 가는 실선. 형상선(2~2.5)과 굵기로 구별된다
LEADER_DOT_MAX_R = 3.0        # 대상 쪽 끝은 점 — 채운 화살촉을 쓰지 않는다(방향과 혼동된다)
LEADER_DOT_TOL = 2.5          # 끝점과 점이 이만큼 안이면 '붙었다'로 본다


def leader_spans(svg):
    return _tagged_group_spans(svg, ("leader",))


def in_leader(spans, pos):
    return any(start <= pos < end for start, end, _body in spans)


def _segments_cross(p, q):
    """두 선분이 끝점을 공유하지 않은 채 실제로 만나는가. 순수 함수."""
    def side(ax, ay, bx, by, cx, cy):
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

    d1 = side(p[0], p[1], p[2], p[3], q[0], q[1])
    d2 = side(p[0], p[1], p[2], p[3], q[2], q[3])
    d3 = side(q[0], q[1], q[2], q[3], p[0], p[1])
    d4 = side(q[0], q[1], q[2], q[3], p[2], p[3])
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


# ★ 축에는 양의 방향 화살표를 붙인다 — **규칙은 있었는데 자가 없었다**
#   (열린 날 2026-08-06, 사용자 지적).
#
# 사용자: [사용자 발화 인용 생략]
#
# AGENTS 삽화 표준은 [사용자 발화 인용 생략] 와
# [사용자 발화 인용 생략] 을 이미 못 박아 두었다. 그런데 **검사가 0개**였다.
# 규칙만 있고 자가 없으면 삽화마다 갈리고, 실제로 갈렸다 — 열역학 ch03 실측에서
# 축 이름을 선언한 삽화 4개 중 **2개**(`fig-pt-diagram` 3절 · `fig-quality-mixture` 4절)에
# 축 화살표가 없었다. **같은 절 안에서도 갈렸다** — 3절의 T-v·P-v 는 있고 P-T 는 없었다.
# [사용자 발화 인용 생략](C33 을 연 그 문장)의 재판이다.
#
# 판정: `class='axis-name'` 으로 **저자가 축 이름이라고 선언한** 글자마다, 그 앵커에서
#   2.0em 안에 채운 삼각형의 **첫 점**(이 리포는 화살촉의 꼭짓점을 `M` 으로 먼저 쓴다)이
#   있어야 한다. 태깅한 것만 재는 것은 `class='dim'`·`class='leader'` 와 같은 이유다 —
#   무엇이 축인지는 기하가 아니라 **마크업이 선언**한다.
# ※ 상한이 규격(1.0em)보다 훨씬 넉넉한 것은 일부러다. **이 자가 잡는 것은 "화살표가 아예
#   없다" 이지 "1.0em 에서 얼마나 벗어났나" 가 아니다.** 실측이 그 둘을 갈라야 한다고 말했다 —
#   진짜 결함은 14em(`fig-quality-mixture`)이거나 삼각형이 아예 없었고(`fig-pt-diagram`),
#   그 사이의 2.1~3.1em 은 화살표는 있는데 이름이 좀 먼 **다른 부류**다(열역학 ch04 실측 3건).
#   같은 자로 재면 [사용자 발화 인용 생략] 는 틀린 진단을 내게 되므로, 거리 규격은 별도로 다룬다.
AXIS_ARROW_MAX_EM = 3.5


# 축 이름과 화살촉 사이의 거리 규격 — AGENTS 「라벨의 기준 위치」: [사용자 발화 인용 생략] 위 `AXIS_ARROW_MAX_EM` 은 [사용자 발화 인용 생략]
# 를 잡는 자라 넉넉하고, **거리는 이 자가 따로 잰다** — 둘을 한 자로 묶으면 어느 쪽 결함인지
# 진단이 섞인다(2026-08-06 실측: ch04 3건이 화살표는 있는데 이름만 2.1~3.1em 떨어져 있었다).
AXIS_NAME_GAP_EM = 1.0
AXIS_NAME_GAP_TOL_EM = 0.5      # 이만큼 벗어나면 신고 (0.5~1.5em 통과)


def _triangle_apex(nums):
    """채운 삼각형의 **꼭짓점** — 가장 짧은 변의 맞은편 점. 순수 함수.

    ★ 열린 날 2026-08-06. 처음에는 [사용자 발화 인용 생략] 고 가정했는데
      **틀렸다.** 생성기가 뽑은 삽화(`M76 44 L71.5 54 L80.5 54 Z`)는 그렇지만, 손으로 그린
      것은 밑변을 먼저 쓴다(`M328 105 L340 110 L328 115 Z` — 꼭짓점은 **가운데** 점이다).
      그 가정으로 잰 거리가 실제와 달랐고, 그대로 라벨을 옮겼으면 엉뚱한 자리에 놓았을 것이다.
      화살촉은 이등변삼각형이므로 **밑변이 가장 짧다** — 표기 순서와 무관한 이 성질로 잡는다.
    """
    pts = [(float(nums[i]), float(nums[i + 1])) for i in range(0, 6, 2)]
    sides = [(_distance(pts[i], pts[(i + 1) % 3]), (i + 2) % 3) for i in range(3)]
    return pts[min(sides)[1]]


def _axis_name_gaps(svg):
    """(x, y, fs, 가장 가까운 화살촉까지 거리, 그 화살촉) — 두 자가 함께 쓰는 실측. 순수 함수."""
    apexes = []
    for m in re.finditer(r"<path([^>]*?)/?>", svg):
        attrs = m.group(1)
        fill = (_attr(attrs, "fill") or "").strip().lower()
        if not fill or fill == "none":
            continue
        dstr = _attr(attrs, "d", "")
        if not _is_triangle_path(dstr, closed=True):
            continue
        nums = re.findall(r"-?(?:\d+(?:\.\d*)?|\.\d+)", dstr)
        if len(nums) >= 6:
            apexes.append(_triangle_apex(nums))
    out = []
    for m in re.finditer(r"<text([^>]*)>", svg):
        attrs = m.group(1)
        if "axis-name" not in (_attr(attrs, "class") or ""):
            continue
        try:
            point = (float(_attr(attrs, "x", "0")), float(_attr(attrs, "y", "0")))
        except (TypeError, ValueError):
            continue
        own = _attr(attrs, "font-size")
        fs = (float(own) if own and re.fullmatch(r"\d+(?:\.\d*)?", own)
              else (_inherited_font_size(svg, m.start()) or 12.0))
        best = min(apexes, key=lambda p: _distance(point, p)) if apexes else None
        near = _distance(point, best) if best else None
        out.append((point[0], point[1], fs, near, best))
    return out


def axis_name_gap_issues(fig_id, svg):
    """축 이름이 화살촉에서 규격(1.0em)만큼 떨어져 있는가. 순수 함수 — 테스트가 부른다.

    ★ 화살표가 **없는** 것은 `axis_arrow_issues` 의 몫이다 — 여기서는 거리만 본다.
      한 자로 묶으면 [사용자 발화 인용 생략] 는 틀린 진단이 거리 결함에 붙는다.
    """
    out = []
    for x, y, fs, near, apex in _axis_name_gaps(svg):
        if near is None or near > AXIS_ARROW_MAX_EM * fs:
            continue                     # 화살표 자체가 없다 — 다른 자의 몫
        em = near / fs if fs else 0.0
        if abs(em - AXIS_NAME_GAP_EM) > AXIS_NAME_GAP_TOL_EM:
            # 화살촉 좌표를 함께 찍는다 — **어디로 옮겨야 하는지**를 말하지 않는 신고는
            # 사람이 좌표를 다시 뒤지게 만든다(AGENTS: 경고가 갈 길을 알려주지 않으면
            # 그 상태가 그대로 유지된다).
            out.append(fig_id + ": [축] 축 이름이 화살촉에서 %.1fem 떨어져 있다 "
                       "(이름 %.0f,%.0f · 화살촉 %.0f,%.0f · 규격 1.0em = %.0fpx · 허용 ±0.5em). "
                       "AGENTS 「라벨의 기준 위치」 — 두 축 모두 같은 값이어야 한다"
                       % (em, x, y, apex[0], apex[1], fs))
    return out


def axis_arrow_issues(fig_id, svg):
    """축 이름을 선언했는데 그 축에 방향 화살표가 없는 자리. 순수 함수 — 테스트가 부른다."""
    apexes = []
    for m in re.finditer(r"<path([^>]*?)/?>", svg):
        attrs = m.group(1)
        fill = (_attr(attrs, "fill") or "").strip().lower()
        if not fill or fill == "none":
            continue
        dstr = _attr(attrs, "d", "")
        if not _is_triangle_path(dstr, closed=True):
            continue
        nums = re.findall(r"-?(?:\d+(?:\.\d*)?|\.\d+)", dstr)
        if len(nums) >= 6:                  # 꼭짓점 = 가장 짧은 변의 맞은편(`_triangle_apex`)
            apexes.append(_triangle_apex(nums))
    out = []
    for m in re.finditer(r"<text([^>]*)>", svg):
        attrs = m.group(1)
        if "axis-name" not in (_attr(attrs, "class") or ""):
            continue
        try:
            point = (float(_attr(attrs, "x", "0")), float(_attr(attrs, "y", "0")))
        except (TypeError, ValueError):
            continue
        own = _attr(attrs, "font-size")
        fs = (float(own) if own and re.fullmatch(r"\d+(?:\.\d*)?", own)
              else (_inherited_font_size(svg, m.start()) or 12.0))
        near = min((_distance(point, p) for p in apexes), default=None)
        if near is None or near > AXIS_ARROW_MAX_EM * fs:
            out.append(
                fig_id + ": [축] 축 이름 옆에 방향 화살표가 없다 — "
                + repr(_attr(attrs, "x", "?")) + "," + repr(_attr(attrs, "y", "?"))
                + (" (가장 가까운 화살촉이 %.0fpx, 상한 %.0f)" % (near, AXIS_ARROW_MAX_EM * fs)
                   if near is not None else " (이 삽화에 채운 삼각형이 하나도 없다)")
                + ". AGENTS 삽화 표준: 축에는 양의 방향 화살표와 물리량 기호를 붙이고,"
                  " 축 이름은 화살촉 끝에서 1.0em 에 둔다")
    return out


# ── 화살촉 이음매 ──────────────────────────────────────────────────────────
# 열린 날 2026-08-07. 사용자: [사용자 발화 인용 생략] → 어느 삽화냐고 묻자 [사용자 발화 인용 생략]
#
# ★ 그 대답이 진단이다 — **한 삽화의 좌표 실수가 아니라 규격 자체가 만든 것**이다.
#   AGENTS 삽화 표준이 [사용자 발화 인용 생략] 을 못 박아 두어서, 모든 화살표에서
#   축선의 끝 좌표와 화살촉 밑변의 y 가 **정확히 같다**(실측 `fig-d-piston-balance`:
#   주황 축선 `y2=100` ↔ 밑변 `y=100`, 파랑 `146`↔`146`).
#   맞닿은 두 도형은 렌더러가 **따로** 안티에일리어싱하므로 경계 픽셀이 어느 쪽에서도
#   불투명해지지 못하고 배경이 실선처럼 비친다. 삽화는 컨테이너에 맞춰 정수가 아닌 배율로
#   그려지므로(예 612/380 = 1.611) 그 경계는 늘 픽셀 중간에 떨어진다 — 그래서 **전 삽화 공통**이다.
#
# ★★ 처방은 좌표를 옮기는 것이 아니라 **겹치는 것**이다. 화살촉에 자기 fill 과 같은 색의
#   가는 테두리를 두르면 도형이 사방으로 조금 커져 축선과 겹친다 — 겹친 자리는 두 도형이
#   같은 색이라 눈에 안 보이고, 이음매만 사라진다. 축선 끝 좌표를 건드리지 않으므로
#   [사용자 발화 인용 생략] 규격도 그대로 산다(둘은 충돌하지 않는다).
# ☞ `stroke-linejoin='round'` 가 필수다. 기본값 miter 로 두면 화살촉의 뾰족한 꼭짓점에서
#   테두리가 길게 삐져나와(마이터 스파이크) 촉이 바늘처럼 보인다.
ARROW_SEAM_STROKE = 0.75      # 화살촉을 자기 색으로 두르는 굵기(SVG px) — 사방 0.375px 확장


def _elements_with_effective_fill(svg):
    """(태그 전체, 속성 문자열, 유효 fill) — `<g fill='…'>` 상속을 반영한다. 순수 함수.

    화살촉은 `<g fill='#b5602c'><path …/></g>` 로 묶어 그리는 경우가 많아, path 자신의
    `fill` 만 보면 **절반을 놓친다**(z-order 검사가 같은 이유로 한 번 뚫린 적이 있다).
    """
    stack, out = [], []
    for m in re.finditer(r"<(/?)([A-Za-z]+)([^>]*?)(/?)>", svg):
        closing, tag, attrs, selfclose = m.groups()
        if tag == "g":
            if closing:
                if stack:
                    stack.pop()
            elif not selfclose:
                stack.append((_attr(attrs, "fill") or "").strip())
            continue
        if closing:
            continue
        eff = (_attr(attrs, "fill") or "").strip()
        if not eff:
            for f in reversed(stack):
                if f:
                    eff = f
                    break
        out.append((m.group(0), attrs, eff))
    return out


def arrowhead_seam_hits(svg):
    """자기 색 테두리가 없는 화살촉 (태그 전체, 유효 fill). 순수 함수 — 도구·검사가 함께 쓴다."""
    hits = []
    for whole, attrs, fill in _elements_with_effective_fill(svg):
        if not whole.startswith("<path"):
            continue
        if not fill or fill.lower() == "none":
            continue
        # 그라데이션·패턴 fill 은 건너뛴다 — 같은 `url(#…)` 을 stroke 에 주면 테두리가
        # 도형과 다른 색으로 칠해져(그라데이션의 좌표계가 stroke 에 다시 적용된다) 되레 띠가 생긴다.
        if fill.lower().startswith("url("):
            continue
        if not _is_triangle_path(_attr(attrs, "d", ""), closed=True):
            continue
        stroke = (_attr(attrs, "stroke") or "").strip().lower()
        if stroke and stroke != "none":
            continue                      # 이미 둘렀거나, 테두리를 의도한 도형이다
        hits.append((whole, fill))
    return hits


def arrowhead_seam_issues(fig_id, svg):
    """C38 — 화살촉에 자기 색 테두리가 없는 자리(위 주석이 정본). 순수 함수 — 테스트가 부른다."""
    return [
        fig_id + ": [화살촉] 자기 색 테두리가 없다 — 선 끝과 밑변이 같은 좌표라 렌더러가"
        " 둘을 따로 안티에일리어싱해 **접합부에 배경이 실선처럼 비친다**."
        " stroke=<fill> · stroke-width=%g · stroke-linejoin='round' 를 붙일 것"
        " (`python tools/fix_arrow_seam.py --apply`)" % ARROW_SEAM_STROKE
        for _ in arrowhead_seam_hits(svg)]


def centerline_style_issues(fig_id, svg):
    r"""**중심선은 1점 쇄선이다** — 실선이면 형상선으로 읽힌다. 순수 함수 — 테스트가 직접 부른다.

    ★★ **열린 날 2026-08-23, 사용자 3회차 지적**: [사용자 발화 인용 생략]
      `fig-two-cord-layout` 의 \(s_C\) 는 도르래의 **축**까지 재므로 그 선이 원을 가로지르는 것은
      제도에서 정상이다 — **문제는 그것이 실선이었다는 것**이다. 실선으로 그리면 원을 관통하는
      **막대**로 읽히고, 사용자가 본 것이 정확히 그것이다.

    ★ **완화가 아니다.** 「관통하지 마라」로 고치면 치수가 축이 아니라 **가장자리**를 재는 그림이
      되어 뜻이 틀린다(그래서 앞선 두 배치가 이 자리를 못 닫았다). 고칠 것은 **선의 종류**다.

    ★ 이 자리가 사각지대였던 경위: 중심선을 `dim` 그룹 안에 두면 `audit_figure_balance` 가
      «치수보조선이 도형에 닿았다» 로 신고해서 `class='axis'` 라는 새 태깅으로 뺐는데,
      **그 태깅을 보는 자가 하나도 없었다**(워크오더에 [사용자 발화 인용 생략] 라고 적힌 채 남았다).
      태깅으로 자를 피하면 그 자리는 «통과» 가 아니라 **아무도 안 보는 자리**가 된다.
    """
    issues = []
    for m in re.finditer(r"<(line|path)\b[^>]*class\s*=\s*['\"][^'\"]*\baxis\b[^'\"]*['\"][^>]*>",
                         svg):
        if "stroke-dasharray" not in m.group(0):
            issues.append(fig_id + ": [중심선] `class='axis'` 인데 실선이다 — 1점 쇄선"
                          "(`stroke-dasharray='12 3 2 3'`)으로 그릴 것. 실선이면 형상을 가로지르는"
                          " 순간 «관통하는 막대»로 읽힌다: " + m.group(0)[:80])
    return issues


# ★★ **마이터 가시** — 예각 꼭짓점에서 이음이 뾰족하게 튀어나오는 자리 (열린 날 2026-08-23).
#
#   사용자 지적: [사용자 발화 인용 생략] — 3차원 유체 요소
#   (`fig-hydrostatic-column`)의 비스듬한 면 두 곳이었다.
#
#   기하: SVG 기본 `stroke-linejoin` 은 `miter` 다. 끼인각 θ 인 꼭짓점에서 이음의 끝은
#   꼭짓점에서 `(w/2)/sin(θ/2)` 만큼 나가고, 둥근 이음이면 `w/2` 에서 멈춘다 —
#   **튀어나오는 길이는 그 차이**다. 렌더러는 `1/sin(θ/2)` 가 `stroke-miterlimit`(기본 4)을
#   넘을 때만 깎으므로, 그 아래의 예각은 **깎이지 않고 그대로 가시로 남는다.**
#
#   왜 자가 필요한가 — 이건 «눈으로 보면 보이는데 아무도 안 재던» 부류다. 좌표에서
#   계산되므로 사람이 볼 이유가 없다. 처방은 그 요소에 `stroke-linejoin='round'` 하나뿐이라
#   전수 교정 도구(`tools/fix_miter_join.py`)와 짝으로 둔다.
MITER_SPIKE_RATIO = 2.0
"""가시로 칠 뾰족함 `1/sin(θ/2)` — 굵기와 무관한 **모양**의 값이다.

★ **첫 판은 돌출 화면px 로 쟀는데 틀렸다**(같은 날 실측). 절대 길이로 재면 **굵은 선이 벌을
받는다** — 관 벽(15px)의 **직각** 모서리가 3.5px 튀어나온다고 걸렸는데, 그건 가시가 아니라
«ㄱ자 엘보» 이고 한 해 동안 아무도 지적한 적이 없다. 사용자가 짚은 것은 길이가 아니라
**바늘 같은 모양**이다. 그래서 굵기를 나눈 비로 잰다.

**고른 값이다**(실행 규율 16). 견준 셋: 직각 1.41(정상 모서리) · 실측 36° 3.24(가시) ·
실측 31° 3.74(사용자가 짚음). 그 사이를 가르는 2.0 은 θ ≈ 59° 이고, 45° 사면(2.61)은 걸린다 —
45°에서 이미 꼭짓점이 선폭의 2.6배로 나가므로 걸리는 것이 맞다.
"""
# 그래도 **안 보이는 것은 안 센다** — 비만 보면 머리카락 같은 선까지 걸린다.
# **고른 값이다**: 사용자가 짚은 31° 사례의 돌출이 2.25 화면px 였으므로 그 절반을 바닥으로 둔다.
MITER_SPIKE_SCREEN_PX = 1.0
MITER_DEFAULT_LIMIT = 4.0                # SVG 기본 stroke-miterlimit (이보다 뾰족하면 렌더러가 깎는다)


def _polyline_joins(tag, attrs):
    """그 요소의 꼭짓점 목록 `[(vx, vy, 들어온 방향, 나갈 방향)]`. 순수 함수.

    곡선은 `_path_polyline` 이 잘게 펴 주므로 이음각이 180°에 가까워 저절로 걸러진다 —
    가시는 **사람이 찍은 꼭짓점**에서만 난다.
    """
    if tag in ("polygon", "polyline"):
        nums = [float(x) for x in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", _attr(attrs, "points", ""))]
        pts = list(zip(nums[0::2], nums[1::2]))
        if tag == "polygon" and len(pts) > 2:
            pts = pts + [pts[0], pts[1]]
        segs = [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) for i in range(len(pts) - 1)]
    elif tag == "path":
        d = _attr(attrs, "d", "")
        segs = _path_polyline(d)
        # 닫힌 도형은 마지막 선분과 첫 선분 사이에도 꼭짓점이 있다 — 그 자리가 실제로 걸렸다.
        if segs and re.search(r"[Zz]", d) and _close(segs[-1][2], segs[0][0]) \
                and _close(segs[-1][3], segs[0][1]):
            segs = segs + [segs[0]]
    else:
        return []
    out = []
    for a, b in zip(segs, segs[1:]):
        if not (_close(a[2], b[0]) and _close(a[3], b[1])):
            continue                       # 붙어 있지 않으면 이음이 아니다(M 으로 건너뛴 자리)
        vin = (a[2] - a[0], a[3] - a[1])
        vout = (b[2] - b[0], b[3] - b[1])
        if not any(vin) or not any(vout):
            continue
        out.append((a[2], a[3], vin, vout))
    return out


def _close(a, b, tol=1e-6):
    return abs(a - b) <= tol


def miter_spike_hits(svg, view_width):
    """`[(요소 전체, 끼인각°, 돌출 화면 px)]`. 순수 함수 — 검사와 교정 도구가 함께 쓴다."""
    scale = screen_scale(view_width)       # SVG px × (1/scale) = 화면 실효 px
    hits = []
    for m in re.finditer(r"<(path|polygon|polyline)([^>]*?)/?>", svg):
        tag, attrs, whole = m.group(1), m.group(2), m.group(0)
        stroke = (_effective(svg, m.start(), attrs, "stroke") or "").strip().lower()
        if not stroke or stroke == "none":
            continue
        join = (_effective(svg, m.start(), attrs, "stroke-linejoin") or "miter").strip().lower()
        if join != "miter":
            continue
        try:
            width = float(_effective(svg, m.start(), attrs, "stroke-width") or 1.0)
            limit = float(_effective(svg, m.start(), attrs, "stroke-miterlimit")
                          or MITER_DEFAULT_LIMIT)
        except (TypeError, ValueError):
            continue
        if width <= 0:
            continue
        worst = None
        for _vx, _vy, vin, vout in _polyline_joins(tag, attrs):
            # 들어온 방향의 **반대**와 나갈 방향 사이가 끼인각이다.
            a1 = math.atan2(-vin[1], -vin[0])
            a2 = math.atan2(vout[1], vout[0])
            theta = abs(math.degrees(a2 - a1)) % 360.0
            if theta > 180.0:
                theta = 360.0 - theta
            half = math.sin(math.radians(theta) / 2.0)
            if half <= 1e-9 or 1.0 / half > limit:
                continue                   # 렌더러가 깎는다(bevel) — 가시가 안 남는다
            if 1.0 / half <= MITER_SPIKE_RATIO:
                continue                   # 모서리이지 가시가 아니다(직각·둔각)
            out_px = (width / 2.0) * (1.0 / half - 1.0) / scale
            if out_px > MITER_SPIKE_SCREEN_PX and (worst is None or out_px > worst[1]):
                worst = (theta, out_px)
        if worst:
            hits.append((whole, worst[0], worst[1]))
    return hits


def miter_spike_issues(fig_id, view_width, svg):
    """예각 꼭짓점에 남는 마이터 가시. 순수 함수 — 빌드·회귀가 함께 쓴다."""
    return [
        "%s: [마이터 가시] 끼인각 %.0f° 꼭짓점에서 이음이 %.1f 화면px 튀어나온다 —"
        " 기본 `stroke-linejoin` 이 miter 라 예각이 뾰족한 끝으로 남는다."
        " 그 요소에 stroke-linejoin='round' 를 줄 것"
        " (`python tools/fix_miter_join.py <챕터> --apply`)" % (fig_id, theta, out_px)
        for _whole, theta, out_px in miter_spike_hits(svg, view_width)]


def leader_line_issues(fig_id, svg):
    """지시선 규격 위반. 순수 함수 — 빌드·회귀가 함께 쓴다.

    잰다: ⑴ 굵기 상한 ⑵ 화살촉을 붙이지 않았는가 ⑶ 대상 쪽 끝에 점이 있는가
          ⑷ 갈래끼리 교차하지 않는가.
    **형상선과의 교차는 여기서 재지 않는다** — 글자를 지나가는 것은 F4 가 이미 잡고,
    도형선과의 교차는 '무엇이 형상선인가' 를 공통 코드가 알아야 해서 지금 자가 없다.
    그 판정은 렌더 육안 검수의 몫으로 남긴다(규칙 11: 미검증이면 미검증이라고 적는다).
    """
    out = []
    spans = leader_spans(svg)
    if not spans:
        return out
    circles = []
    for m in re.finditer(r"<circle([^>]*?)/?>", svg):
        a = m.group(1)
        try:
            circles.append((float(_attr(a, "cx", "0")), float(_attr(a, "cy", "0")),
                            float(_attr(a, "r", "0"))))
        except ValueError:
            continue
    strokes = []
    for start, end, _body in spans:
        chunk = svg[start:end]
        for m in re.finditer(r"<(path|line)([^>]*?)/?>", chunk):
            tag, a = m.group(1), m.group(2)
            width = _effective(svg, start + m.start(), a, "stroke-width")
            try:
                width = float(width)
            except (TypeError, ValueError):
                width = 0.0
            if width > LEADER_MAX_WIDTH + 1e-9:
                out.append(fig_id + ": [지시선] 굵기 %.1f > %g — 지시선은 가는 실선이다"
                           % (width, LEADER_MAX_WIDTH))
            if _attr(a, "marker-end") or _attr(a, "marker-start"):
                out.append(fig_id + ": [지시선] 화살촉이 붙었다 — 이 리포에서 채운 화살촉은"
                                    " '방향'의 뜻이라 혼동된다. 대상 쪽 끝은 점으로 찍을 것")
            dstr = (_attr(a, "d", "") if tag == "path" else
                    "M%s %s L%s %s" % (_attr(a, "x1", "0"), _attr(a, "y1", "0"),
                                       _attr(a, "x2", "0"), _attr(a, "y2", "0")))
            segs = _path_polyline(dstr)
            if not segs:
                continue
            strokes.append(segs)
            tipx, tipy = segs[-1][2], segs[-1][3]
            if not any(r <= LEADER_DOT_MAX_R
                       and _distance((cx, cy), (tipx, tipy)) <= LEADER_DOT_TOL
                       for cx, cy, r in circles):
                out.append(fig_id + ": [지시선] 대상 쪽 끝 (%.0f, %.0f) 에 점이 없다 — "
                           "반지름 %g 이하 <circle> 로 찍을 것" % (tipx, tipy, LEADER_DOT_MAX_R))
        if re.search(r"<path[^>]*\bd='M[^']*Z'", chunk):
            out.append(fig_id + ": [지시선] 그룹 안에 닫힌 삼각형(화살촉)이 있다")
    for i, a in enumerate(strokes):
        for b in strokes[i + 1:]:
            if any(_segments_cross(s, t) for s in a for t in b):
                out.append(fig_id + ": [지시선] 갈래끼리 교차한다 — 한 라벨에서 여러 갈래로"
                                    " 뻗을 때 갈래는 서로 만나지 않아야 한다")
                break
    return out


def _is_triangle_path(dstr, closed=None):
    commands, numbers = _svg_path_signature(dstr)
    if closed is True:
        return [c.upper() for c in commands] == ["M", "L", "L", "Z"] and len(numbers) == 6
    if closed is False:
        return [c.upper() for c in commands] == ["M", "L", "L"] and len(numbers) == 6
    return _is_triangle_path(dstr, True) or _is_triangle_path(dstr, False)

def _path_subpaths(dstr):
    return [part for part in re.split(r"(?=[Mm])", dstr) if part.strip()]

def _distance(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

def _path_endpoints(dstr):
    """Return segment endpoints for the simple SVG commands used by figures."""
    tokens = re.findall(r"[A-Za-z]|-?(?:\d+(?:\.\d*)?|\.\d+)", dstr)
    counts = {"M": 2, "L": 2, "H": 1, "V": 1, "A": 7, "Q": 4, "C": 6}
    result, current, command, index = [], (0.0, 0.0), None, 0
    while index < len(tokens):
        if tokens[index].isalpha():
            command = tokens[index]
            index += 1
            if command.upper() == "Z":
                continue
        upper = command.upper() if command else ""
        count = counts.get(upper)
        if count is None or index + count > len(tokens):
            break
        values = [float(value) for value in tokens[index:index + count]]
        index += count
        start = current
        if upper in ("M", "L"):
            end = (values[0], values[1])
        elif upper == "H":
            end = (values[0], current[1])
        elif upper == "V":
            end = (current[0], values[0])
        else:
            end = (values[-2], values[-1])
        if command.islower():
            end = (current[0] + end[0], current[1] + end[1])
        current = end
        if upper != "M":
            result.extend((start, end))
    return result

def _stroked_circles(svg):
    out = []
    for m in re.finditer(r"<circle([^>]*?)/?>", svg):
        a = m.group(1)
        if _attr(a, "stroke") in (None, "none"):
            continue
        try:
            out.append((float(_attr(a, "cx", "0")), float(_attr(a, "cy", "0")),
                        float(_attr(a, "r", "0"))))
        except (TypeError, ValueError):
            continue
    return out


def _circle_arc_tangent(start, end, radius, large_arc, sweep):
    """Return the SVG circular arc's unit tangent at its end point."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    chord = math.hypot(dx, dy)
    if not chord or chord > 2 * radius:
        return None
    mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
    h = math.sqrt(max(0.0, radius * radius - (chord / 2) ** 2))
    ux, uy = -dy / chord, dx / chord
    candidates = ((mx + h * ux, my + h * uy), (mx - h * ux, my - h * uy))
    for cx, cy in candidates:
        a0 = math.atan2(start[1] - cy, start[0] - cx)
        a1 = math.atan2(end[1] - cy, end[0] - cx)
        delta = a1 - a0
        if sweep and delta < 0:
            delta += 2 * math.pi
        if not sweep and delta > 0:
            delta -= 2 * math.pi
        if (abs(delta) > math.pi) != bool(large_arc):
            continue
        rx, ry = end[0] - cx, end[1] - cy
        tx, ty = ((-ry, rx) if sweep else (ry, -rx))
        length = math.hypot(tx, ty)
        return (tx / length, ty / length) if length else None
    return None


# ── 삽화 조각 생성기 ② · ③ — 각도 호+접선 화살촉 / 치수선 한 벌 (신설 2026-08-16) ──
#
# 왜 있나: `svg_fraction`(위)과 **같은 이유**다. 규격을 문서에만 적어 두면 삽화마다 손으로
# 좌표를 잡게 되고, **그 갈라짐 자체가 다음 지적이 된다** — 분수는 [사용자 발화 인용 생략](2026-07-28), 치수선은 [사용자 발화 인용 생략]
# (2026-07-31), 회전 화살표는 [사용자 발화 인용 생략](2026-07-25)로 각각 왔다.
# ★ 이 둘이 서야 AGENTS §4 의 수치(4px·10px·접선 방향)가 **코드로 내려간다** —
#   나루 `기록/AGENTS-삭감-목록.md` §4: [사용자 발화 인용 생략]
# ★★ **생성기는 자기 출력을 자기 자로 잰다.** 아래 둘이 찍은 조각은 `arc_arrowhead_issues`·
#   `dim_extension_rows` 가 **그대로 통과시켜야 한다**(회귀가 그것을 잠근다). 규격을 두 벌
#   적으면 «찍는 값»과 «재는 값»이 갈리는데, 이 리포가 반복해 겪은 부류가 정확히 그것이다.

# 뷰어 본문 폭. 화면 실효 px 환산의 기준이고 **글자 크기 규격과 같은 자**다
# (`figure_text_scale_issues` 의 13~19px 도 이 폭으로 환산한다).
VIEWER_WIDTH_PX = 612.0

# 치수 라벨이 자기 치수선에서 떨어지는 목표(글자 **상자** 기준). 하한(`DIM_LABEL_GAP_MIN_EM`)에
# 여유 0.02em 을 얹은 값 — 하한에 딱 맞추면 반올림 한 번에 다시 걸린다.
# ★ 정본을 여기 둔다: `fix_dim_label_gap.py`(전수 교정)와 `svg_dimension`(신규 생성)이 **같은
#   값을 써야** «새로 그린 것은 통과하는데 고친 것은 걸리는» 상태가 안 생긴다.
DIM_LABEL_GAP_TARGET_EM = DIM_LABEL_GAP_MIN_EM + 0.02

# 치수 계열(치수선·보조선)을 **그릴** 굵기. 상한은 `checks_content.DIM_EXTENSION_MAX_WIDTH`(1.5)
# 인데 거기 딱 맞추면 좌표 반올림 한 번에 걸리고, 형상선(2~2.5)과의 대비도 흐려진다.
DIM_EXT_WIDTH = 1.2

# 치수 라벨의 baseline 을 잡을 때 **상자 아래**로 내려가는 양. **같은 값을 다시 적지 않는다** —
# 정본은 위 `TEXT_BOX_DESCENT_RATIO`(= `_text_bbox` 가 쓰는 그 상자)다.
# ★ 여기는 원래 잉크 descent(`BOX_INK_DESCENT`)를 가리키고 있었고, **그것이 결함이었다**
#   (2026-08-25 첫 실사용): 간격 목표 `DIM_LABEL_GAP_TARGET_EM` 은 «상자 기준»인데 놓을 때만
#   잉크로 재서, 가로 치수 라벨의 **상자 아래가 치수선 밑으로 내려갔다**(F4 + 「글자가 선과 교차」).
#   세로 치수는 상자 옆면을 그대로 쓰고 있어 안 걸렸다 — 그쪽 형태에 맞춘 것이다.
TEXT_DESCENT_RATIO = TEXT_BOX_DESCENT_RATIO

# 글자의 **세로 중심**을 baseline 으로 옮기는 값. AGENTS 「세로 눈금축의 라벨」의 규약
# `baseline = 중심 + fs × 0.35` 그대로다 — 여기서 다시 정하면 같은 질문에 자가 둘이 된다
# (그 갈라짐이 실제로 0.08em 만큼 늘 통과하던 자리였다, 위 BOX_INK_ASCENT 주석).
TEXT_MID_RATIO = 0.35


def screen_scale(vb_width):
    """화면 실효 px → 그 삽화의 SVG px 배율. `viewBox` 폭이 넓을수록 크게 그려야 같아 보인다."""
    return float(vb_width) / VIEWER_WIDTH_PX


def _filled_head(tip_x, tip_y, ux, uy, length, ratio):
    """**밑변 중앙이 선 끝에 놓이는** 채운 삼각형. 꼭짓점이 아니라 밑변이 붙는다(§4 규격).

    `(ux, uy)` 는 향하는 방향의 단위벡터, `ratio` 는 밑변폭/길이.
    """
    apex = (tip_x + ux * length, tip_y + uy * length)
    half = length * ratio / 2.0
    nx, ny = -uy, ux
    return "M%.2f %.2f L%.2f %.2f L%.2f %.2f Z" % (
        apex[0], apex[1],
        tip_x + nx * half, tip_y + ny * half,
        tip_x - nx * half, tip_y - ny * half)


def _head_tag(d, fill):
    """채운 화살촉 태그 — **자기 색 테두리를 두른 채로** 낸다.

    ★ 열린 날 2026-08-25(생성기 첫 실사용). 테두리 없이 내면 `arrowhead_seam_issues` 가
      **바로 막아서**, 사람이 `fix_arrow_seam.py` 를 따로 돌려야 통과했다 — 그건 생성기를
      쓰는 뜻(사람이 좌표를 안 잡는다)을 깨뜨린다. **찍는 자가 처음부터 통과하게 낸다.**
    ★ 형태는 `fix_arrow_seam.seamed()` 가 이미 있는 삽화에 붙이는 것과 **같다** —
      `stroke=<fill>` · `stroke-width=ARROW_SEAM_STROKE` · `stroke-linejoin='round'`.
      두 자리가 갈리면 «새로 그린 것과 고친 것이 다른» 상태가 된다.
    """
    return ("<path d='%s' fill='%s' stroke='%s' stroke-width='%g' stroke-linejoin='round'/>"
            % (d, fill, fill, ARROW_SEAM_STROKE))


def svg_arc_arrow(cx, cy, r, a0, a1, vb_width=VIEWER_WIDTH_PX,
                  stroke="#3a4252", width=2.0):
    """각도 호 + **접선 화살촉**. 각은 도(°)이고 SVG 좌표계(y 아래)다.

    `a1` 은 **화살촉 꼭짓점이 닿는 각**이다 — 호는 그보다 화살촉 길이만큼 물러난 자리에서
    끝나고, 그 자리에 밑변이 놓인다.

    회전(축일 기기·사이클)은 글자 `↻` 를 쓰지 않고 이 형태로 그린다(§4 「시각 문법」).
    화살촉은 **호의 접선 방향**이어야 한다 — 끝점만 맞추면 삼각형이 호를 거슬러 볼 수 있고,
    그것이 2026-07-25 에 열린 결함이다(`arc_arrowhead_issues` 가 그 자다).

    ★★ **`a1` 의 뜻을 2026-08-25 에 바꿨다 — 「호가 끝나는 각」 → 「꼭짓점이 닿는 각」.**
      옛 판은 호를 `a1` 까지 긋고 그 자리에 **밑변**을 놓아, 꼭짓점이 `a1` 을 화살촉 길이만큼
      **지나** 그려졌다. 각도 호가 놓이는 자리는 두 기준선 사이(바닥선↔빗면)라 그 초과분이
      **바닥선·트랙을 뚫고 나오고**, 렌더에서 「아래로 누르는 힘」으로 읽힌다
      (동역학 `fig-ch16-q01`·`q02`·`q06` 실측 · 생성기 출력이라 그리는 사람이 못 고쳤다).
      `audit_figure_balance._tip_alignment_rows` 는 그것을 **11.03px 지나침**으로 이미 신고하고
      있었는데 잠금이 그 축을 안 봐서 초록이었다.
    ★ **판정은 «자가 옳고 생성기가 틀렸다»** 다. 이 리포의 화살표는 전부 «닿는 곳 = 꼭짓점»
      이고(2026-07-29 에 열린 그 자가 규격의 자다), 생성기 둘만 «닿는 곳 = 밑변» 으로 찍었다.
      자를 고치면 손으로 그린 삽화 전부의 규격이 뒤집힌다 — 고칠 자리는 생성기 쪽이다.
    ★ 물리는 각은 `atan(hl/r)` 이다(`hl/r` 이 아니다). 그래야 꼭짓점이 **정확히 각 `a1`** 에
      놓인다: 밑변 `r·e^{iφ}` 에 접선 `hl` 을 더하면 `e^{iφ}(r + i·s·hl)` 이고
      그 편각이 `φ + s·atan(hl/r)` 이므로 `φ = a1 − s·atan(hl/r)` 이면 정확히 `a1` 이다.
      꼭짓점의 반지름은 `√(r²+hl²)` 로 조금 커지는데, 각도 호의 기준선은 **꼭짓점에서 뻗은
      반직선**이라 반지름은 착지에 영향을 주지 않는다.
    """
    k = screen_scale(vb_width)
    hl = ARROW_HEAD_TARGET_PX * k
    sweep = 1 if a1 >= a0 else 0
    s = 1.0 if sweep else -1.0
    pull = math.degrees(math.atan2(hl, r))       # 호를 물릴 각
    a1b = a1 - s * pull                          # 밑변(= 호의 끝)이 놓이는 각
    if (a1b - a0) * s <= 0:
        raise ValueError(
            "호가 화살촉보다 짧다 — %.1f° 만 남는데 화살촉이 %.1f° 를 먹는다. "
            "r 을 키우거나 각을 넓혀라." % (abs(a1 - a0), pull))
    a0r, a1r = math.radians(a0), math.radians(a1b)
    large = 1 if abs(a1b - a0) > 180 else 0
    p0 = (cx + r * math.cos(a0r), cy + r * math.sin(a0r))
    p1 = (cx + r * math.cos(a1r), cy + r * math.sin(a1r))
    # 끝점의 접선. 각이 커지는 방향이면 (-sin, cos), 줄어드는 방향이면 그 반대다.
    ux, uy = -math.sin(a1r) * s, math.cos(a1r) * s
    out = ("<path d='M%.2f %.2f A%.2f %.2f 0 %d %d %.2f %.2f' fill='none' "
           "stroke='%s' stroke-width='%.2f' stroke-linecap='butt'/>"
           % (p0[0], p0[1], r, r, large, sweep, p1[0], p1[1], stroke, width))
    out += "\n" + _head_tag(_filled_head(p1[0], p1[1], ux, uy, hl, 1.0), stroke)
    return out, {"start": p0, "end": p1, "tangent": (ux, uy), "head_len": hl,
                 "tip": (p1[0] + ux * hl, p1[1] + uy * hl), "pullback_deg": s * pull}


def svg_dimension(axis, p1, p2, face, line_pos, fs, vb_width,
                  label="", stroke="#3a4252", fill="#2c3a44"):
    """치수선 **한 벌** — 보조선 둘 + 치수선 + 화살촉 둘 + 라벨.

    `axis='h'` 는 가로 치수(보조선이 세로), `'v'` 는 세로 치수다.
    `p1`·`p2` 는 **재는 두 면의 좌표**(가로면 x, 세로면 y), `face` 는 그 면이 있는 **외형선**의
    반대 축 좌표, `line_pos` 는 치수선이 놓일 자리다.

    규격은 전부 정본에서 가져온다 — 간격 `DIM_GAP_SCREEN_PX`(4) · 넘김
    `DIM_OVERSHOOT_SCREEN_PX`(10) · 라벨 `DIM_LABEL_GAP_TARGET_EM` · 화살촉 비율
    `DIM_ARROW_WIDTH_RATIO_TARGET`. **여기에 수를 다시 적지 않는다.**
    ★ 보조선은 도형에 **닿지 않는다**(간격) 그리고 치수선을 **지나 더 나간다**(넘김) —
      둘 다 사용자가 적합하다고 판정한 `fig-elastic-rod-work` 실측에서 온 값이다.
    ★ 라벨은 가로 치수면 **위 중앙**, 세로 치수면 **왼쪽**이고 **회전하지 않는다**(§4 의 의도적 반박).

    ★★ **꼭짓점이 재는 면에 닿는다 — 밑변이 아니다** (고친 날 2026-08-25, `svg_arc_arrow` 와 같은 부류).
      옛 판은 밑변을 `p1`·`p2` 에 놓아 **꼭짓점이 치수보조선을 화살촉 길이(11.03px)만큼 지나** 있었다.
      2026-07-29 에 사용자가 지적한 결함(치수 화살촉 8곳이 보조선을 **2px** 지나침)의 5배다.
      **그 자가 이것을 못 봤다** — `_is_panel_divider` 가 화살촉 삼각형을 「패널 내용」으로 세어
      떠 있는 치수보조선을 칸막이로 오인하고 후보에서 통째로 뺐다(같은 날 그 자도 고쳤다).
    ★ 밑변은 치수선을 따라 `hl` 안쪽에 놓고 **본선은 두 밑변을 잇는다** — `dim_shaft_overshoot_issues`
      의 «본선 끝 = 밑변 중앙» 이 그대로 산다. 두 규격은 이렇게만 동시에 성립한다.
    ★ **좁은 치수는 밖으로 돌린다**(정당한 제도 표기 · `dim_extension_rows` 주석의 그 형태).
      판정선은 「안쪽에 남는 본선이 `DIM_MAIN_MIN_LEN` 을 넘는가」다 — 그 하한 아래로 내려가면
      본선이 본선으로 인식되지 못해 축이 90° 뒤집힌다.
    """
    from .checks_content import (DIM_GAP_SCREEN_PX, DIM_OVERSHOOT_SCREEN_PX,  # 순환 임포트를 피해 지연
                                 DIM_MAIN_MIN_LEN)

    k = screen_scale(vb_width)
    gap, over = DIM_GAP_SCREEN_PX * k, DIM_OVERSHOOT_SCREEN_PX * k
    sign = 1.0 if line_pos >= face else -1.0
    ext0, ext1 = face + sign * gap, line_pos + sign * over
    hl = ARROW_HEAD_TARGET_PX * k
    lo, hi = (p1, p2) if p1 <= p2 else (p2, p1)
    inward = (hi - lo) - 2.0 * hl >= DIM_MAIN_MIN_LEN
    d = 1.0 if inward else -1.0        # 밑변이 놓이는 쪽(안/밖)
    b_lo, b_hi = lo + d * hl, hi - d * hl
    parts = []

    def line(x1, y1, x2, y2, w):
        return ("<line x1='%.2f' y1='%.2f' x2='%.2f' y2='%.2f' stroke='%s' "
                "stroke-width='%.2f' stroke-linecap='butt'/>" % (x1, y1, x2, y2, stroke, w))

    if axis == "h":
        parts.append(line(lo, ext0, lo, ext1, DIM_EXT_WIDTH))
        parts.append(line(hi, ext0, hi, ext1, DIM_EXT_WIDTH))
        parts.append(line(b_lo, line_pos, b_hi, line_pos, DIM_EXT_WIDTH))
        for x, ux in ((b_lo, -d), (b_hi, d)):
            parts.append(_head_tag(_filled_head(x, line_pos, ux, 0.0, hl,
                                                DIM_ARROW_WIDTH_RATIO_TARGET), stroke))
        if label:
            # 글자 **상자**의 아래가 치수선에서 목표만큼 떨어지게 baseline 을 잡는다.
            base = line_pos - fs * DIM_LABEL_GAP_TARGET_EM - fs * TEXT_DESCENT_RATIO
            parts.append("<text x='%.2f' y='%.2f' font-size='%.1f' fill='%s' "
                         "text-anchor='middle'>%s</text>"
                         % ((lo + hi) / 2.0, base, fs, fill, label))
    else:
        parts.append(line(ext0, lo, ext1, lo, DIM_EXT_WIDTH))
        parts.append(line(ext0, hi, ext1, hi, DIM_EXT_WIDTH))
        parts.append(line(line_pos, b_lo, line_pos, b_hi, DIM_EXT_WIDTH))
        for y, uy in ((b_lo, -d), (b_hi, d)):
            parts.append(_head_tag(_filled_head(line_pos, y, 0.0, uy, hl,
                                                DIM_ARROW_WIDTH_RATIO_TARGET), stroke))
        if label:
            parts.append("<text x='%.2f' y='%.2f' font-size='%.1f' fill='%s' "
                         "text-anchor='end'>%s</text>"
                         % (line_pos - fs * DIM_LABEL_GAP_TARGET_EM,
                            (lo + hi) / 2.0 + fs * TEXT_MID_RATIO, fs, fill, label))
    return ("<g class='dim'>\n  " + "\n  ".join(parts) + "\n</g>",
            {"gap": gap, "over": over, "scale": k, "head_len": hl})


def arc_arrowhead_issues(svg):
    """Check circular-arrow head attachment and tangent direction.

    Opened 2026-07-25: the cycle arrow's base midpoint touched the arc endpoint,
    but its triangle pointed against the tangent. Endpoint-only checks called it
    connected even though the rendered head visibly left the circular path.
    """
    number = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
    arc_re = re.compile(
        rf"M\s*({number})[ ,]({number})\s*A\s*({number})[ ,]({number})\s+0\s+([01])\s+([01])\s+"
        rf"({number})[ ,]({number})", re.I)
    triangle_re = re.compile(
        rf"M\s*({number})[ ,]({number})\s*L\s*({number})[ ,]({number})"
        rf"\s*L\s*({number})[ ,]({number})\s*Z", re.I)
    triangles = [
        [(float(m[i]), float(m[i + 1])) for i in (1, 3, 5)]
        for m in triangle_re.finditer(svg)
    ]
    issues = []
    for arc in arc_re.finditer(svg):
        start = (float(arc[1]), float(arc[2]))
        rx, ry = float(arc[3]), float(arc[4])
        if abs(rx - ry) > 0.01:
            continue
        end = (float(arc[7]), float(arc[8]))
        tangent = _circle_arc_tangent(start, end, rx, int(arc[5]), int(arc[6]))
        if tangent is None:
            continue
        best = None
        for pts in triangles:
            for a in range(3):
                for b in range(a + 1, 3):
                    tip_index = 3 - a - b
                    base = ((pts[a][0] + pts[b][0]) / 2, (pts[a][1] + pts[b][1]) / 2)
                    gap = _distance(base, end)
                    candidate = (gap, base, pts[tip_index])
                    if best is None or candidate[0] < best[0]:
                        best = candidate
        if best is None or best[0] > 24:
            continue
        gap, base, tip = best
        if gap > 1:
            issues.append("원형 화살표 밑변 중앙-원주 끝점 간격 %.1fpx" % gap)
            continue
        vx, vy = tip[0] - base[0], tip[1] - base[1]
        length = math.hypot(vx, vy)
        alignment = (vx * tangent[0] + vy * tangent[1]) / length if length else -1
        if alignment < .94:
            issues.append("원형 화살촉이 원주 접선과 어긋남(cos=%.2f)" % alignment)
    return issues


def _arrow_clearance_issues(svg, viewbox=None):
    """화살표가 도형 윤곽을 관통하거나 화살촉끼리 닿는 경우.

    2026-07-22, 같은 삽화 6회 지적의 마지막 두 번이 정확히 이 사각지대였다:
    기존 검사는 전부 '글자 대 선'이라 **화살표 대 도형, 화살표 대 화살표는 아무도
    안 봤다.** AGENTS 규격('서로 다른 화살표는 최소 폰트 크기만큼 띄운다')을 검사로 승격.

    ★ **도형 종류별로 따로 짜지 않는다** (2026-08-29, 사용자: [사용자 발화 인용 생략]). 채운 도형 목록은 `_svg_filled_shapes` 하나가
    낸다(rect·circle·ellipse를 이미 bbox로 통일해 둔 자리) — **새 도형이 생겨도 그 함수
    한 곳만 넓히면 여기는 그대로 통한다.** `viewbox`가 없으면(레거시 호출) 이 부분은
    건너뛴다 — svg 문자열만으로는 viewBox를 다시 파싱해야 해서다.
    """
    issues = []
    number = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
    triangle_re = re.compile(
        rf"M\s*({number})[ ,]({number})\s*L\s*({number})[ ,]({number})"
        rf"\s*L\s*({number})[ ,]({number})\s*Z", re.I)
    heads = []
    for match in triangle_re.finditer(svg):
        pts = [(float(match[i]), float(match[i + 1])) for i in (1, 3, 5)]
        if max(_distance(a, b) for a in pts for b in pts) > 32:
            continue
        heads.append(((sum(p[0] for p in pts) / 3, sum(p[1] for p in pts) / 3), pts))
    # ⑴ 화살촉끼리 — 중심 간 거리가 최소 폰트 크기(12px) 미만이면 시각적으로 닿는다
    #
    # ★ 예외: **꼭짓점을 공유하는 두 화살촉**은 붐비는 것이 아니라 하나의 도형이다
    #   (열린 날 2026-08-07). 사용자: [사용자 발화 인용 생략] — 옳은 지적이었다.
    #
    #   벡터 삼각형(\\(\\mathbf{u} + d\\mathbf{u} = \\mathbf{u}'\\))에서 변화량 벡터는 **정의상**
    #   원래 벡터의 끝에서 새 벡터의 끝까지 간다. 그러면 두 화살촉의 꼭짓점이 같은 점이 되고,
    #   촉이 90° 벌어져 있으면 중심 간 거리가 11.3px 라 이 검사가 막았다.
    #   그래서 실제로 **삽화를 물리적으로 틀리게 그렸다**(26px 앞에서 끊었다) —
    #   검사가 데이터를 이기면 안 되는 자리였다.
    #
    #   ★ 느슨하게 푸는 것이 아니다. **꼭짓점이 실제로 일치할 때만**(2px) 넘어간다 —
    #   어긋난 채 가까운 두 촉은 그대로 막힌다. 그것이 원래 이 검사가 잡으려던 것이다.
    #   잠금은 test_checks.py::test_shared_vertex_arrowheads_are_not_crowding.
    def _apex(pts):
        """세 꼭짓점 중 **촉 끝**(나머지 둘의 중점에서 가장 먼 점)."""
        best, best_d = pts[0], -1.0
        for k in range(3):
            others = [pts[m] for m in range(3) if m != k]
            mid = ((others[0][0] + others[1][0]) / 2, (others[0][1] + others[1][1]) / 2)
            d = _distance(pts[k], mid)
            if d > best_d:
                best, best_d = pts[k], d
        return best

    apexes = [_apex(pts) for _c, pts in heads]
    for i in range(len(heads)):
        for j in range(i + 1, len(heads)):
            if _distance(apexes[i], apexes[j]) <= 2:
                continue                      # 꼭짓점 공유 — 벡터 삼각형의 정상 형태
            d = _distance(heads[i][0], heads[j][0])
            if d < 12:
                issues.append("화살촉끼리 %.0fpx — 최소 폰트 크기(12px)만큼 띄울 것" % d)
    # ⑵ 화살촉이 채운 도형(사각형·원·타원 — 종류를 안 가린다)을 관통 — 흐름도 화살표가
    #   모서리를 넘어 안으로 들어간 자리(2026-08-29, 사용자: [사용자 발화 인용 생략]).
    #   꼭짓점(촉 끝)이 도형 bbox 안에 있는데 밑변 두 점 중 하나라도 밖에 있으면
    #   **경계를 가로질렀다**는 뜻이다 — 자유물체도처럼 화살표 전체(밑변까지)가 도형
    #   **안에서** 그려지는 정상 자리는 밑변까지 안에 있어 안 걸린다.
    if viewbox is not None:
        margin = 3.0
        for x0, y0, x1, y1 in _svg_filled_shapes(svg, viewbox):
            for (cx, cy), pts in heads:
                apex = _apex(pts)
                base = [p for p in pts if p != apex]
                apex_in = x0 + margin < apex[0] < x1 - margin and y0 + margin < apex[1] < y1 - margin
                if not apex_in:
                    continue
                base_out = any(not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1) for p in base)
                if base_out:
                    issues.append("화살촉이 도형 안으로 파고듦 — 꼭짓점(%.0f,%.0f)" % apex)
    # ⑶ 선분·화살촉이 stroked 원의 윤곽을 관통 — 한쪽 끝이 확실히 안, 다른 끝이 확실히
    #    밖이면 관통이다. 반지름선처럼 윤곽 '위에서 끝나는' 선은 잡지 않는다(±3px 톨러런스).
    for cx, cy, r in _stroked_circles(svg):
        if r < 20:
            continue                      # 중심점 표시용 소원은 제외
        for seg in _svg_segments(svg):
            d1 = _distance((seg[0], seg[1]), (cx, cy))
            d2 = _distance((seg[2], seg[3]), (cx, cy))
            if min(d1, d2) < 10:
                continue    # 허브(중심)에서 나가는 축·바늘은 원을 지나는 것이 설계다
            if (d1 < r - 3) != (d2 < r - 3) and max(d1, d2) > r + 3:
                issues.append("선분이 원(r=%.0f) 윤곽을 관통 — (%.0f,%.0f)→(%.0f,%.0f)"
                              % (r, seg[0], seg[1], seg[2], seg[3]))
        for _, pts in heads:
            ds = [_distance(p, (cx, cy)) for p in pts]
            if min(ds) < r - 3 and max(ds) > r + 3:
                issues.append("화살촉이 원(r=%.0f) 윤곽에 걸침" % r)
    return issues


def _arrowhead_connection_issues(svg):
    """Find stems that enter a small triangular arrowhead instead of ending at its base."""
    number = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
    triangle_re = re.compile(
        rf"M\s*({number})[ ,]({number})\s*L\s*({number})[ ,]({number})"
        rf"\s*L\s*({number})[ ,]({number})\s*Z", re.I
    )
    endpoints = []
    for match in re.finditer(r"<line\b([^>]*?)/?>", svg):
        attrs = match.group(1)
        if _attr(attrs, "stroke-dasharray") is not None:
            continue  # 치수보조선은 화살촉의 stem이 아니라 tip이 닿는 기준선이다.
        try:
            endpoints.extend(((float(_attr(attrs, "x1")), float(_attr(attrs, "y1"))),
                              (float(_attr(attrs, "x2")), float(_attr(attrs, "y2")))))
        except (TypeError, ValueError):
            continue
    leaders = leader_spans(svg)
    for match in re.finditer(r"<path\b([^>]*?)/?>", svg):
        attrs = match.group(1)
        if _attr(attrs, "stroke-dasharray") is not None:
            continue
        if in_leader(leaders, match.start()):
            continue        # 지시선은 화살촉의 stem 이 아니다 — 끝은 점으로 찍는다
        dstr = _attr(attrs, "d", "")
        if "Z" not in dstr.upper():
            endpoints.extend(_path_endpoints(dstr))

    issues = []
    for match in triangle_re.finditer(svg):
        points = [(float(match[i]), float(match[i + 1])) for i in (1, 3, 5)]
        pairs = ((0, 1), (0, 2), (1, 2))
        if max(_distance(points[a], points[b]) for a, b in pairs) > 32:
            continue
        base_pair = min(
            pairs,
            key=lambda pair: abs(
                _distance(points[next(iter({0, 1, 2} - set(pair)))], points[pair[0]])
                - _distance(points[next(iter({0, 1, 2} - set(pair)))], points[pair[1]])
            ),
        )
        tip_index = next(iter({0, 1, 2} - set(base_pair)))
        tip = points[tip_index]
        base = ((points[base_pair[0]][0] + points[base_pair[1]][0]) / 2,
                (points[base_pair[0]][1] + points[base_pair[1]][1]) / 2)
        axis_x, axis_y = tip[0] - base[0], tip[1] - base[1]
        axis_len2 = axis_x * axis_x + axis_y * axis_y
        if not axis_len2:
            continue
        candidates = []
        for point in endpoints:
            t = ((point[0] - base[0]) * axis_x + (point[1] - base[1]) * axis_y) / axis_len2
            projected = (base[0] + t * axis_x, base[1] + t * axis_y)
            perpendicular = _distance(point, projected)
            if perpendicular < 0.6 and -0.02 <= t <= 1.02:
                candidates.append((_distance(point, base), t))
        if candidates and min(candidates)[1] > 0.02:
            issues.append((base, tip))
    return issues

# ★ 화살표 크기 규격 (신설 2026-08-02, 사용자 지적 2건이 같은 뿌리였다).
#
#   [사용자 발화 인용 생략] (축 화살촉이 삽화마다 다르다)
#   [사용자 발화 인용 생략] (꼬리 하한)
#
# **없었다.** AGENTS 삽화 표준은 화살표의 *모양*(채운 삼각형)과 *연결점*(밑변 중앙)만 정하고
# **크기는 한 줄도 없었다.** 그래서 좌표로는 다들 `10 × 10` 을 쓰는데 viewBox 폭이 달라
# 화면에서는 **19.1px vs 13.6px** 로 갈렸다(실측: viewBox 320 vs 450).
# 글자(`figure_text_scale_issues`)와 치수(4/10)는 이미 **화면 실효 px** 로 통일했는데
# 화살표만 그 자 밖이었다 — 같은 자를 대면 끝나는 자리였다.
def _element_polylines(svg):
    """(엘리먼트별 선분 목록) — 꼬리 길이를 재려면 '어느 선의 일부인가'를 알아야 한다."""
    out = []
    for m in re.finditer(r"<line\b([^>]*?)/?>", svg):
        a = m.group(1)
        try:
            seg = tuple(float(_attr(a, k)) for k in ("x1", "y1", "x2", "y2"))
        except (TypeError, ValueError):
            continue
        out.append([seg])
    for m in re.finditer(r"<path\b([^>]*?)/?>", svg):
        a = m.group(1)
        dstr = _attr(a, "d", "")
        if not dstr or _is_triangle_path(dstr):
            continue                      # 화살촉 자신은 꼬리가 아니다
        segs = _path_polyline(dstr)
        if segs:
            out.append(segs)
    return out


def arrow_geometry(svg):
    """화살표들의 기하 — [{tip, base, length, width, tail}] (SVG px). 순수 함수(테스트가 부른다).

    `tail` 은 밑변 중앙에 끝이 닿은 선의 **전체 길이**(없으면 None).
    """
    number = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
    triangle_re = re.compile(
        rf"M\s*({number})[ ,]({number})\s*L\s*({number})[ ,]({number})"
        rf"\s*L\s*({number})[ ,]({number})\s*Z", re.I)
    elements = _element_polylines(svg)
    out = []
    for match in triangle_re.finditer(svg):
        points = [(float(match[i]), float(match[i + 1])) for i in (1, 3, 5)]
        pairs = ((0, 1), (0, 2), (1, 2))
        if max(_distance(points[a], points[b]) for a, b in pairs) > 40:
            continue                      # 삼각형이지만 화살촉이라기엔 크다
        base_pair = min(pairs, key=lambda pair: abs(
            _distance(points[next(iter({0, 1, 2} - set(pair)))], points[pair[0]])
            - _distance(points[next(iter({0, 1, 2} - set(pair)))], points[pair[1]])))
        tip = points[next(iter({0, 1, 2} - set(base_pair)))]
        base = ((points[base_pair[0]][0] + points[base_pair[1]][0]) / 2,
                (points[base_pair[0]][1] + points[base_pair[1]][1]) / 2)
        tail = None
        for segs in elements:
            ends = [(segs[0][0], segs[0][1]), (segs[-1][2], segs[-1][3])]
            if min(_distance(e, base) for e in ends) > 1.5:
                continue
            length = sum(_distance((s[0], s[1]), (s[2], s[3])) for s in segs)
            if tail is None or length > tail:
                tail = length
        out.append({
            "tip": tip, "base": base,
            "length": _distance(base, tip),
            "width": _distance(points[base_pair[0]], points[base_pair[1]]),
            "tail": tail,
            # 소스 위치 — 치수 그룹 안인지 가리는 데 쓴다(아래 `dim_arrow_positions`).
            "pos": match.start(),
        })
    return out


def dim_arrow_positions(svg):
    """치수 그룹(`class='dim'`·`id='dim-…'`) **안에 있는** 화살촉의 소스 위치 집합. 순수 함수.

    ★ 저자가 선언한 태그만 본다 — 이름으로 «이건 치수 같다» 고 추측하면 삽화마다 갈린다.
      태깅이 없으면 규격이 안 걸리는 것은 치수선 자체(`class='dim'`)와 같은 규약이다.
    """
    spans = [(s, e) for s, e, _b in _tagged_group_spans(svg, ("dim",))]
    return {a["pos"] for a in arrow_geometry(svg)
            if any(s <= a["pos"] < e for s, e in spans)}


def figure_arrow_scale_issues(fig_id, view_width, svg):
    """화살표 크기가 규격 밖인 자리. 순수 함수 — 빌드·감사·회귀가 함께 쓴다.

    글자와 **같은 자**(화면 실효 px)로 잰다. 그게 이 규격의 요점이다 —
    SVG 좌표로 `10 × 10` 을 똑같이 써도 viewBox 폭이 다르면 화면 크기가 1.4배 갈린다.
    """
    scale = FIGURE_RENDER_WIDTH / view_width if view_width else 1.0
    dims = dim_arrow_positions(svg)
    out = []
    for arrow in arrow_geometry(svg):
        length = arrow["length"] * scale
        width = arrow["width"] * scale
        is_dim = arrow["pos"] in dims
        lo, hi = ((DIM_ARROW_WIDTH_RATIO_MIN, DIM_ARROW_WIDTH_RATIO_MAX) if is_dim
                  else (ARROW_WIDTH_RATIO_MIN, ARROW_WIDTH_RATIO_MAX))
        where = "%s: %s화살표 끝점(%.0f,%.0f)" % (fig_id, "치수 " if is_dim else "",
                                              arrow["tip"][0], arrow["tip"][1])
        if not ARROW_HEAD_MIN_PX <= length <= ARROW_HEAD_MAX_PX:
            out.append(where + " — 화살촉 길이 %.1f (규격 %g~%g 화면 실효 px). "
                       "`python tools/fix_arrow_scale.py --apply` 가 맞춰 준다"
                       % (length, ARROW_HEAD_MIN_PX, ARROW_HEAD_MAX_PX))
        elif not lo <= (width / length if length else 0) <= hi:
            out.append(where + " — 화살촉 폭/길이 %.2f (규격 %g~%g%s). "
                       "`python tools/fix_arrow_scale.py --apply` 가 맞춰 준다"
                       % (width / length if length else 0, lo, hi,
                          " · 치수 화살촉은 제도 관례대로 가늘다" if is_dim else ""))
        tail = None if arrow["tail"] is None else arrow["tail"] * scale
        if tail is not None and tail < length * ARROW_TAIL_MIN_RATIO:
            # 꼬리는 **자동으로 늘리지 않는다** — 늘리면 다른 도형을 뚫을 수 있어서
            # 어디를 넓힐지는 사람이 정해야 한다(사용자: [사용자 발화 인용 생략]).
            out.append(where + " — 꼬리 %.1f < 화살촉 %.1f 의 %g배 (%.1f). "
                       "꼬리를 늘리거나 삽화를 키울 것 (머리보다 짧은 꼬리는 화살표로 안 읽힌다)"
                       % (tail, length, ARROW_TAIL_MIN_RATIO, length * ARROW_TAIL_MIN_RATIO))
    return out


def pipe_arrow_clearance_issues(fig_id, svg, margin=2.0):
    """이중 스트로크 관 안의 화살촉이 내부 폭보다 넓은 자리.

    관은 같은 경로를 굵은 외곽선과 가는 배경색 선으로 두 번 그린다. 이때 실제로
    비어 보이는 폭은 안쪽 선의 ``stroke-width``이고, 화살촉 폭보다 최소 ``margin``만큼
    넓어야 화살촉이 관 벽에 붙지 않는다. 그룹 상속을 직접 읽어, 숫자 하나를 고정한
    삽화 전용 검사가 되지 않게 한다.
    """
    layers = []
    for group in re.finditer(r"<g\b([^>]*)>(.*?)</g>", svg, re.S):
        width = _attr(group.group(1), "stroke-width")
        if width is None:
            continue
        try:
            width = float(width)
        except ValueError:
            continue
        paths = tuple(_attr(m.group(1), "d", "")
                      for m in re.finditer(r"<path\b([^>]*)/?>", group.group(2)))
        paths = tuple(p for p in paths if p)
        if paths:
            layers.append((width, paths))

    channels = []
    for i, (width_a, paths_a) in enumerate(layers):
        for width_b, paths_b in layers[i + 1:]:
            if paths_a != paths_b or width_a == width_b:
                continue
            channels.append((min(width_a, width_b), paths_a))

    out = []
    for inner_width, paths in channels:
        segments = [seg for dstr in paths for seg in _path_polyline(dstr)]
        for arrow in arrow_geometry(svg):
            tip, base = arrow["tip"], arrow["base"]
            on_channel = any(
                min(x1, x2) - 1 <= tip[0] <= max(x1, x2) + 1
                and min(y1, y2) - 1 <= tip[1] <= max(y1, y2) + 1
                and min(x1, x2) - 1 <= base[0] <= max(x1, x2) + 1
                and min(y1, y2) - 1 <= base[1] <= max(y1, y2) + 1
                for x1, y1, x2, y2 in segments
            )
            if on_channel and inner_width + 1e-9 < arrow["width"] + margin:
                out.append(
                    "%s: 관 내부 폭 %.1f < 화살촉 폭 %.1f + 여백 %.1f — "
                    "안쪽 스트로크를 넓히거나 화살촉을 줄일 것"
                    % (fig_id, inner_width, arrow["width"], margin)
                )
    return out


def _thick_curve_layer_count(svg):
    """이 SVG 안에서 '굵은 곡선 경로'가 몇 겹인지 센다. 순수 함수 — 테스트가 직접 부른다.

    열린 날 2026-07-29 — L5가 **표준을 지킨 삽화만 골라 때리고 있었다.**
    옛 조건은 `Q 명령 + 6 <= stroke-width <= 10`이었는데, 리포의 관 표준은
    *외곽 굵게 + 내부 배경색*(AGENTS 삽화 표준)이라 **올바른 이중 스트로크의 안쪽 층이
    정확히 그 6~10 구간에 들어온다.** 그래서
      - 안쪽을 10으로 그린 `fig-multifluid-manometer`는 **규격을 지켰는데 경고 2건**,
      - 안쪽을 12로 그린 같은 구조의 U자관은 **경고 0건**,
      - 정작 잡아야 할 *굵기 12짜리 단일선 U자관*은 상한 10에 걸려 **아예 못 잡는** 상태였다.
    즉 판정이 의도와 반대로 작동했다. 원인은 "빠뜨렸다"가 아니라 **굵기 구간으로 층수를 추정한 것**이다.

    고친 형태: 굵기 상한을 없애고(단일선은 굵어도 잡힌다), 대신 **층수를 직접 센다.**
    굵은 곡선 경로가 2겹 이상이면 이미 관 벽/내부로 분리된 것이므로 신고하지 않는다.
    """
    layers = 0
    for m in re.finditer(r"<path([^>]*?)/?>", svg):
        attrs = m.group(1)
        commands, _ = _svg_path_signature(_attr(attrs, "d", ""))
        if any(c.upper() == "Q" for c in commands) and float(_attr(attrs, "stroke-width", "0")) >= 6:
            layers += 1
    return layers


def check_figure_lint(fig_id, svg, errors, warnings, strict=False, geometry_strict=False):
    """Figure style lint from figure-lint.workorder.md.

    L1/L3 start in warning mode while existing chapters are audited. Once ch02/ch03
    are clean, callers can pass strict=True to promote only those two rules to errors.
    L2/L4/L5/L6 deliberately remain review warnings because intent is not reliably
    inferable from SVG geometry alone.
    """
    strict_out = errors if strict else warnings
    path_items = []
    thick_curve_layers = _thick_curve_layer_count(svg)
    leaders = leader_spans(svg)
    for m in re.finditer(r"<path([^>]*?)/?>", svg):
        attrs = m.group(1)
        dstr = _attr(attrs, "d", "")
        path_items.append((attrs, dstr))

        # L1: a two-sided arrowhead is an accidentally open triangle.
        # ★ 지시선은 예외다 — `M…L…L`(글자 옆 수평 stub → 한 번 꺾어 대상) 이 곧 규격 형태라
        #   여는 삼각형과 서명이 같다. 화살촉이 아니라는 것은 `class='leader'` 가 선언한다.
        # ★★ **진행 표시(`class='travel'`)도 예외다** (신설 2026-08-18, 사용자 판정).
        #   [사용자 발화 인용 생략]
        #   — 규격이 「방향은 채운 삼각형으로만」이라 이 자가 곧바로 신고하던 자리다.
        #   **완화가 아니라 뜻을 가른 것이다:** 채운 삼각형은 **선 끝**(여기서 끝난다 = 도착),
        #   열린 `>` 는 **선 중간**(이쪽으로 간다 = 진행). 모양 하나가 뜻 하나를 맡으므로
        #   「한 시각 요소는 한 물리량만」이 오히려 지켜진다 — 둘을 같은 모양으로 두면
        #   독자가 선 중간의 삼각형을 「여기가 끝인가」로 읽는다.
        #   ★ 선언이 있어야 예외다. 태그 없는 `M…L…L` 은 그대로 「닫다 만 화살촉」으로 신고된다.
        if (any(_is_triangle_path(part, closed=False) for part in _path_subpaths(dstr))
                and _attr(attrs, "fill") in (None, "none")
                and "travel" not in (_attr(attrs, "class") or "")
                and not in_leader(leaders, m.start())):
            strict_out.append(fig_id + ": [figure-lint L1] 열린 화살촉(M-L-L) — Z로 닫고 stroke 색으로 채울 것")

        # L5: a thick quadratic curve may be a U-tube fluid drawn as one heavy line.
        commands, _ = _svg_path_signature(dstr)
        stroke_width = float(_attr(attrs, "stroke-width", "0"))
        if (any(c.upper() == "Q" for c in commands) and stroke_width >= 6
                and thick_curve_layers == 1):
            warnings.append(fig_id + ": [figure-lint L5 후보] Q path + 굵은 단일 stroke — U자관이면 관 벽+내부 유체로 분리 검토")

        # L6: rounded thick strokes can look like detached floating bars.
        if stroke_width >= 5 and _attr(attrs, "stroke-linecap") == "round":
            warnings.append(fig_id + ": [figure-lint L6 후보] 굵은 round path — 연결부 이격 여부 검토")

    for m in re.finditer(r"<line([^>]*?)/?>", svg):
        attrs = m.group(1)
        stroke_width = float(_attr(attrs, "stroke-width", "0"))
        if stroke_width >= 5 and _attr(attrs, "stroke-linecap") == "round":
            warnings.append(fig_id + ": [figure-lint L6 후보] 굵은 round line — 연결부 이격 여부 검토")

    # L3/L4 apply to every <text>, including rotated labels that _svg_texts skips
    # because their bounding boxes cannot be estimated safely.
    plain_text_parts = []
    for text_match in re.finditer(r"<text[^>]*>(.*?)</text>", svg, re.S):
        text = re.sub(r"<[^>]+>", "", text_match.group(1))
        plain_text_parts.append(text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))
    plain_text = " ".join(plain_text_parts)
    for raw_subscript in re.findall(r"[A-Za-zρ]_[A-Za-z0-9]{1,4}", plain_text):
        strict_out.append(fig_id + ": [figure-lint L3] SVG raw 아래첨자 " + repr(raw_subscript)
                          + " — <tspan dy='2.5' font-size='78%'> 사용")

    filled_triangle_count = sum(
        sum(_is_triangle_path(part, closed=True) for part in _path_subpaths(dstr))
        for attrs, dstr in path_items if _attr(attrs, "fill") not in (None, "none")
    )
    has_double_arrow_path = any(
        sum(_is_triangle_path(part, closed=True) for part in _path_subpaths(dstr)) == 2
        and float(_attr(attrs, "stroke-width", "0")) <= 2.5
        for attrs, dstr in path_items if _attr(attrs, "fill") not in (None, "none")
    )
    has_filled_triangle = filled_triangle_count > 0
    for base, tip in _arrowhead_connection_issues(svg):
        if geometry_strict:
            errors.append(
            fig_id + ": [figure-lint G1] 화살표 선 끝이 화살촉 밑변 중앙을 지나침 "
            + "(base=" + repr(base) + ", tip=" + repr(tip) + ")"
            )
    if has_filled_triangle and any(ch in plain_text for ch in "↑↓"):
        warnings.append(fig_id + ": [figure-lint L4 후보] 채운 화살촉과 ↑/↓ 문자 혼용 — 감소 기호 예외 여부 검토")

    # L2 is only machine-detectable when the author tagged the group as a dimension.
    #
    # ★ 규격 변경 2026-07-29 (워크오더 ch01-review-batch 항목 8) — 옛 규칙은 '점선 보조선'을
    # 요구했으나 **제도 관례에서 치수선·치수보조선은 둘 다 가는 실선**이고 파선은 숨은선의 몫이다.
    # 사용자 지적: [사용자 발화 인용 생략] 그래서 dash를 요구하던 판정을 **금지로 뒤집고**,
    # 형상선과의 구별은 굵기로 강제한다.
    # 실측(2026-07-29): 태깅된 치수 그룹은 ch02에 3개뿐이었고 셋 다 파선이라 옛 검사를 **조용히
    # 통과**하고 있었다. 뒤집은 뒤 경고가 46→52로 는 것은 버그가 아니라 **그동안 안 보이던
    # 비적합이 드러난 것**이다. 나머지 치수 삽화는 태깅 자체가 없어 규격 검사를 받지 못한다.
    tagged_dimension = False
    for _start, _end, body in _tagged_group_spans(svg, ("dim", "measure")):
        tagged_dimension = True
        if "stroke-dasharray" in body:
            warnings.append(fig_id + ": [figure-lint L2] 치수 그룹에 파선 — 치수선·보조선은 둘 다 가는 실선이다(파선은 숨은선의 몫)")
        # ★ fill·stroke 는 **상속을 본다** (2026-07-30 보강, ch04 이관에서 드러났다).
        # `<g fill='#b5602c'><path d='…Z'/></g>` 처럼 그룹에 색을 걸면 요소 자신에는
        # fill 이 없어, 자기 속성만 보던 옛 판정은 **화살촉을 화살촉으로 못 봤다**
        # (fig-closed-energy-flow 가 규격을 다 지키고도 '구성 검토' 경고를 받았다).
        # 같은 부류를 이 파일이 이미 두 번 고쳤다 — font-size 상속(07-28)·dash 상속(07-30).
        thick = []
        for pm in re.finditer(r"<(?:path|line)([^>]*?)/?>", svg[_start:_end]):
            at, pos = pm.group(1), _start + pm.start()
            # 채운 도형(화살촉)의 stroke는 굵기 규격 대상이 아니다 — 선이 아니라 면을 살찌우는 값이다.
            if _effective(svg, pos, at, "fill", "none") != "none":
                continue
            width = float(_attr(at, "stroke-width", "0"))
            if width > DIMENSION_LINE_MAX_WIDTH:
                thick.append(width)
        if thick:
            warnings.append(fig_id + ": [figure-lint L2] 치수선이 굵다 " + repr(thick)
                            + " — 형상선과의 구별은 굵기로 한다(상한 "
                            + format(DIMENSION_LINE_MAX_WIDTH, "g") + ")")
        has_solid_body = any(
            _effective(svg, _start + pm.start(), pm.group(1), "stroke", "none") != "none"
            and not _effective(svg, _start + pm.start(), pm.group(1), "stroke-dasharray", "")
            for pm in re.finditer(r"<(?:path|line)([^>]*?)/?>", svg[_start:_end])
        )
        has_arrowhead = any(
            any(_is_triangle_path(part, closed=True)
                for part in _path_subpaths(_attr(pm.group(1), "d", "")))
            and _effective(svg, _start + pm.start(), pm.group(1), "fill", "none") != "none"
            for pm in re.finditer(r"<path([^>]*?)/?>", svg[_start:_end])
        )
        # ※ 여기 `<polygon>` 분기를 두지 않는다 (2026-07-30 판단, thermo 설계 채택).
        #   math 는 자를 넓히는 쪽(polygon 도 화살촉으로 인정)을 먼저 시도했는데, 그러면
        #   `_arrowhead_connection_issues`(G1) · `filled_triangle_count`(L4) 까지 **함수마다**
        #   가르쳐야 하고 하나라도 빠지면 그 자리만 조용히 꺼진다. 아래 L7 이 형식을 하나로
        #   못박으므로 판정 함수는 `<path d='…Z'/>` 하나만 알면 된다.
        if not has_solid_body or not has_arrowhead:
            warnings.append(fig_id + ": [figure-lint L2 후보] 치수 본선/채운 화살촉 구성 검토")
    if (not tagged_dimension and has_double_arrow_path
            and re.search(r"(?:\b\d+(?:\.\d+)?\s*(?:mm|cm|km|m|°)\b|(?:Δ?[xyzl])\s*=)", plain_text)):
        warnings.append(fig_id + ": [figure-lint L2 후보] 양방향 화살촉+치수 라벨 — 치수 그룹으로 태깅하고 가는 실선 규격을 확인할 것")

    # ★ 태깅 없는 가는 파선 (신설 2026-07-30). 위 L2 검사는 **태깅된 것만** 본다.
    #
    # ch01 실측(2026-07-30): 가는 파선 30곳이 **전부 태깅되지 않아** 규격 검사를 한 번도
    # 받지 않았다. 즉 '빌드가 조용하다'가 '규격을 지켰다'가 아니었고, 그 사이 사용자가
    # 같은 지적을 3회 했다([사용자 발화 인용 생략] 외 2건).
    # **원인은 빠뜨린 것이 아니라 태깅하지 않으면 검사를 안 받는 구조**다(AGENTS 규칙 7-⑷).
    #
    # 그래서 판정을 뒤집는다 — **파선을 쓰려면 역할을 태깅해야 한다.**
    #   치수 계열 → `dim`/`measure` (가는 실선이어야 하므로 파선이면 위에서 걸린다)
    #   숨은선   → `hidden-edge` (파선이 맞는 유일한 역할)
    # 태깅이 없으면 그 파선이 무슨 뜻인지 아무도 판정할 수 없다 — 사용자가 실제로 물었다:
    # [사용자 발화 인용 생략]
    dim_group_spans = [(s, e) for s, e, _ in _tagged_group_spans(svg, ("dim", "measure"))]
    for pm in re.finditer(r"<(?:line|path|polyline)\b([^>]*?)/?>", svg):
        attrs = pm.group(1)
        # ★ 상속을 본다 (2026-07-30 보강). 처음 구현은 요소 **자신의** 속성만 봤는데,
        # `<g stroke-dasharray='5 4'><line .../></g>` 처럼 그룹에 걸면 통째로 새어나갔다.
        # 실제로 fig-steady-flow-snapshots 의 시간 연결선이 그렇게 검사를 피했고,
        # 사용자가 [사용자 발화 인용 생략] 로 눈으로 먼저 잡았다 — 검사가 못 본 것을 사람이 봤다.
        dash = _effective(svg, pm.start(), attrs, "stroke-dasharray", "")
        if not dash or dash == "none":
            continue
        width = _effective(svg, pm.start(), attrs, "stroke-width", "0")
        try:
            if float(width or 0) > DIMENSION_LINE_MAX_WIDTH:
                continue                  # 형상선 굵기의 파선은 이 규격의 대상이 아니다
        except ValueError:
            pass
        role = (_effective(svg, pm.start(), attrs, "class", "") or "").lower()
        if any(mark in role for mark in DASH_ROLES):
            continue
        if any(s <= pm.start() < e for s, e in dim_group_spans):
            continue                      # 치수 그룹 안이면 위 L2 검사가 이미 본다
        warnings.append(
            fig_id + ": [figure-lint L2] 태깅 없는 가는 파선 — 역할을 밝힐 것"
            " (치수 계열은 class='dim', 숨은선은 class='hidden-edge')."
            " 치수선·치수보조선은 가는 실선이 규격이다: " + pm.group(0)[:64])

    # ★ `<polygon>` 은 이 파일의 어느 검사도 보지 않는다 (신설 2026-07-30, dynamics 실측).
    #
    # 이 파일의 도형 판정은 **전부 `<path d='…Z'/>` 를 전제**한다 — `_arrowhead_connection_issues`
    # (G1: 선 끝이 화살촉 밑변 중앙인가), `filled_triangle_count`(L4), 위 L2 의 `has_arrowhead`
    # 가 모두 그렇다. 실측: 이 파일 전체에 `polygon` 이라는 문자열이 **한 번도 없었다.**
    #
    # 그래서 `<polygon>` 으로 그린 화살촉은 **규격을 통과한 것이 아니라 검사를 받지 않은 것**이다.
    # dynamics ch12 의 화살촉 11개가 그 상태였고, 빌드는 조용했다. 드러난 경위도 전형적이다 —
    # 태깅된 치수 그룹에서 `has_arrowhead` 가 False 가 되는 바람에 [사용자 발화 인용 생략] 경고가 떴는데,
    # 그건 화살촉이 없어서가 아니라 **못 봐서**였다. path 로 바꾸자 경고가 사라지고 G1 이 처음으로
    # 실제 판정을 했다(통과). 즉 경고를 면제로 덮었으면 사각지대가 그대로 남았을 자리다.
    #
    # 어느 쪽을 고칠 것인가: 모든 판정 함수에 polygon 을 가르치는 것보다 **집 형식을 하나로**
    # 두는 편이 싸고 확실하다(SVG 로서는 동등하고 렌더 결과도 같다). 그래서 형식을 못박고,
    # 이 경고가 **다른 과목의 기존 polygon 도 지목**하게 둔다 — 실측 2026-07-30 기준
    # 공학수학 ch01 3건·ch02 2건이 같은 이유로 검사를 안 받고 있다.
    for pm in re.finditer(r"<polygon\b[^>]*>", svg):
        warnings.append(
            fig_id + ": [figure-lint L7] `<polygon>` 으로 그린 도형 — 채운 삼각형은"
            " `<path d='M… L… L… Z'/>` 로 그릴 것. 화살촉·치수 검사가 **path 만** 보므로"
            " polygon 은 규격을 통과하는 게 아니라 **검사를 안 받는다**: " + pm.group(0)[:60])

    # ★ 본문 대비 하한 (신설 2026-07-30) — `FIGURE_TEXT_BODY_PX` 주석이 경위의 정본이다.
    # 하한 13px 는 본문(15.5px)보다 낮아 **삽화 라벨이 본문보다 작아도 규격을 통과**했다.
    vb_lint = re.search(r"viewBox=['\"]\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)", svg)
    if vb_lint:
        view_w = float(vb_lint.group(1))
        small = []
        for t in _svg_texts(svg):
            if _is_caption_text(t):
                continue                     # 캡션은 라벨의 0.85배가 규격이라 대상이 아니다
            eff = t["fs"] * FIGURE_RENDER_WIDTH / view_w
            if eff < FIGURE_TEXT_BODY_PX - 0.05:
                small.append((round(eff, 1), (t["s"] or "").strip()[:18]))
        if small:
            worst = min(small)
            warnings.append(
                fig_id + ": [figure-lint L6] 라벨이 본문보다 작다 — 실효 "
                + format(worst[0], ".1f") + "px < 본문 " + format(FIGURE_TEXT_BODY_PX, "g")
                + "px ('" + worst[1] + "'" + (" 외 %d건" % (len(small) - 1) if len(small) > 1 else "")
                + "). 삽화 전체 배율을 올릴 것: tools/fix_figure_text_scale.py --floor")

_G_TOKEN = re.compile(r"<g\b[^>]*>|</g\s*>", re.I)


def svg_with_only(svg, keep):
    r"""`<g id=…>` 중 `keep` 에 없는 것을 통째로 지운 SVG. 순수 함수 — 테스트가 직접 부른다.

    ★★ **왜 필요한가** (열린 날 2026-08-19). 유도 슬라이드의 삽화는 **단계마다 다른 그림**이다.
      전부 켜진 SVG 는 **화면에 존재하지 않는 상태**인데, 자를 거기에 대면 두 방향으로 틀린다:
      ⑴ 같은 자리에 번갈아 놓인 조각(방향을 뒤집는 화살표·단계별 캡션)이 «겹침» 으로 잡히고
      ⑵ 반대로 **한 단계 안에서 실제로 겹치는 것**은 다른 단계의 조각에 가려 안 보인다.
      → 자를 대는 대상은 **그 단계에서 실제로 보이는 그림**이어야 한다.

    ★ 중첩 `<g>` 를 세어 균형을 맞춘다 — 정규식으로 `</g>` 를 짝짓지 않는다(안쪽 그룹을
      만나면 그대로 어긋난다).
    """
    keep, out, last, depth, drop_at = set(keep), [], 0, 0, None
    for m in _G_TOKEN.finditer(svg):
        tag = m.group(0)
        if tag.startswith("</"):
            depth -= 1
            if drop_at is not None and depth == drop_at:
                last, drop_at = m.end(), None
            continue
        # ★ **자기 닫는 `<g …/>` 는 깊이를 안 올린다** — 여는 태그로 세면 짝이 영영 안 와서
        #   그 뒤가 통째로 잘려 나간다(첫 판이 그렇게 틀렸고 회귀가 잡았다: 안 바뀐 그룹까지
        #   «바뀜» 으로 나왔다). 그릴 것이 없는 그룹이라 실제 삽화에도 흔하다.
        selfclose = tag.rstrip().endswith("/>")
        gid = _attr(tag, "id")
        if drop_at is None and gid and gid not in keep:
            out.append(svg[last:m.start()])
            if selfclose:
                last = m.end()
            else:
                drop_at = depth
        if not selfclose:
            depth += 1
    out.append(svg[last:])
    return "".join(out)


def _iter_diagrams(ch):
    for s in ch["theory"]["sections"]:
        for dg in s.get("diagrams") or []:
            yield dg
    for f in ch["derivation"]["formulas"]:
        for dg in f.get("diagrams") or []:
            yield dg
    for p in ch.get("practice") or []:
        for dg in p.get("diagrams") or []:
            yield dg
    for q in ch.get("problems") or []:
        for dg in q.get("diagrams") or []:
            yield dg

def _iter_answer_diagrams(ch):
    """Yield diagrams together with values inserted at runtime into answer slots."""
    for p in ch.get("practice") or []:
        slots = []
        for blank in p.get("blanks") or []:
            if blank.get("figureSlot"):
                slots.append({
                    "slot": blank["figureSlot"],
                    "value": _plain_math_text(blank.get("figureAnswer") or blank.get("answer", "")),
                })
        if slots:
            for dg in p.get("diagrams") or []:
                yield dg, slots
    for q in ch.get("problems") or []:
        slots = q.get("figureSlots") or []
        if slots:
            for dg in q.get("diagrams") or []:
                yield dg, slots

def answer_slot_reference_issues(ch):
    """선언된 답 슬롯 id가 그 문항의 삽화 SVG에 실제로 있는지 본다. 순수 함수 — 테스트가 직접 부른다.

    열린 날 2026-07-29 — `_svg_with_answer_slots()` 는 **id가 없으면 조용히 아무것도 안 한다.**
    그리고 호출부는 `if expanded != svg:` 로 감싸여 있어, 치환이 하나도 안 되면
    **답 변형 검사 자체를 통째로 건너뛴다.** 실패가 실패로 보이지 않는 구조였다.

    실측 피해: ch01 `q01·q04·q09` 의 슬롯이 선언만 된 채 SVG에 없었고, 값까지 문제를 개작하기
    전 것이 남아 있었다(q01 `2.40×10³ N` ← 실제 `2.45×10³ N`, q04·q09는 아예 무관한 값).
    **id만 고쳤다면 틀린 답 3개가 그대로 화면에 나갔을 것이다.** 값이 틀린 것은 사람이 봐야 알지만,
    **슬롯이 죽어 있다는 것은 기계가 볼 수 있다** — 그래서 여기서 막는다.
    """
    out = []

    def check(owner_id, slot_ids, diagrams):
        svgs = " ".join((dg.get("svg") or "") for dg in diagrams or [])
        for slot_id in slot_ids:
            if not slot_id:
                out.append(str(owner_id) + ": 답 슬롯 선언에 slot id가 비어 있다")
                continue
            if ("id='" + slot_id + "'") not in svgs and ('id="' + slot_id + '"') not in svgs:
                out.append(str(owner_id) + ": 선언된 답 슬롯 " + repr(slot_id)
                           + " 이 삽화 SVG에 없다 — 치환이 조용히 건너뛰어져 '?'가 그대로 남는다")

    for q in ch.get("problems") or []:
        slots = q.get("figureSlots") or []
        if slots:
            check(q.get("id"), [s.get("slot") for s in slots], q.get("diagrams"))
    for p in ch.get("practice") or []:
        slot_ids = [b.get("figureSlot") for b in p.get("blanks") or [] if b.get("figureSlot")]
        if slot_ids:
            check(p.get("id"), slot_ids, p.get("diagrams"))
    return out


def _svg_with_answer_slots(svg, slots):
    result = svg
    for slot in slots:
        slot_id = slot.get("slot")
        if not slot_id:
            continue
        pattern = re.compile(
            r"(<(?P<tag>tspan|text)\b(?=[^>]*\bid=(?:'" + re.escape(slot_id)
            + r"'|\"" + re.escape(slot_id) + r"\"))[^>]*>).*?(</(?P=tag)>)",
            re.S,
        )
        result = pattern.sub(
            lambda match: match.group(1) + html.escape(str(slot.get("value", ""))) + match.group(3),
            result,
        )
    return result
