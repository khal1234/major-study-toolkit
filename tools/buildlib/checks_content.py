# -*- coding: utf-8 -*-
"""Chapter content-policy and cross-reference checks."""
import copy
import json
import math
import os
import re

from .checks_svg import (
    ANSWER_SLOT_GEOMETRY_STRICT_CHAPTERS,
    ARROW_CONNECTION_STRICT_CHAPTERS,
    DIMENSION_LINE_MAX_WIDTH,
    FIGURE_LINT_STRICT_CHAPTERS,
    FIGURE_RENDER_WIDTH,
    SVG_LAYOUT_STRICT_CHAPTERS,
    _attr,
    _distance,
    _effective,
    _is_triangle_path,
    arrowhead_seam_issues,
    centerline_style_issues,
    _iter_answer_diagrams,
    _iter_diagrams,
    _path_polyline,
    _path_subpaths,
    _point_to_segment_distance,
    _svg_segments,
    _svg_texts,
    _svg_with_answer_slots,
    svg_with_only,
    _tagged_group_spans,
    _text_bbox,
    answer_slot_reference_issues,
    arrow_geometry,
    check_figure_lint,
    check_svg,
    figure_arrow_scale_issues,
    figure_math_typesetting_hits,
    fan_shape_issues,
    figure_box_center_hits,
    figure_box_center_x_hits,
    figure_subtext_scale_hits,
    figure_text_grouping_hits,
    text_runs,
    in_leader,
    leader_line_issues,
    miter_spike_issues,
    pipe_arrow_clearance_issues,
    axis_arrow_issues,
    axis_name_gap_issues,
    leader_spans,
)
from .textutil import LATEX_SUPPORTED, PITFALL_SOURCE_PREFIXES, VEC_COMBINING

# 뷰어 `renderMath` 가 **실제로 그리는** `\mathcal{…}` 글자. 템플릿의 치환이 정본이고
# 여기는 그 사본이다 — 잠금 `test_checks.py::test_mathcal_letters_match_the_renderer`.
# 늘리는 순서는 **템플릿 먼저, 여기 나중**이다(반대로 하면 화면만 깨진 채 빌드가 초록이 된다).
VIEWER_MATHCAL_LETTERS = ("V",)
# ★ 2026-09-03 — `\mathcal` 과 같은 사정(위 주석 참고). 뷰어의 `\mathfrak{…}` 치환은
#   현재 `E`(엑서지, Moran 표기) 하나만 안다.
VIEWER_MATHFRAK_LETTERS = ("E",)

# 결정면·방향 지수를 감싸는 괄호. 여는 것과 닫는 것이 짝이어야 지수로 본다.
_INDEX_OPEN = "([{〈⟨"
_INDEX_CLOSE = ")]}〉⟩"


def _is_bracketed_index(text, start, end):
    """`text[start:end]` 가 **괄호로 감싸인 지수**인가. 순수 함수 — 회귀가 직접 부른다.

    밀러 지수 `(111)`·`[111]`·`{111}`·`〈111〉` 과 쉼표 판 `(1,1,0)` 을 「잰 값」과 가른다.
    잠금 `test_checks.py::test_crystal_indices_are_not_measurements`.
    """
    if start <= 0 or end >= len(text):
        return False                      # 양쪽에 괄호가 설 자리가 없다
    return text[start - 1] in _INDEX_OPEN and text[end] in _INDEX_CLOSE

# 뷰어 `renderMath` 가 `\frac` **보다 먼저** 치환하는 매크로. 먼저 치환되면 그 자리의
# 중괄호는 분수에 닿기 전에 사라지므로 「분수 인자 안 중첩 중괄호」로 세면 안 된다.
# 손으로 유지하다 **세 번 재발했다**(`mathcal` 2026-08-12 · `hl` 08-13 · `sqrt` 08-25) —
# 잠금 `test_checks.py::test_pre_frac_macros_match_the_renderer` 가 템플릿을 읽어 대조한다.
# ★ `ddot` 은 그 회귀가 **첫 실행에서 잡아 준 것**이다(2026-08-25) — 아무도 안 적어 뒀는데
#   렌더러는 이미 분수보다 먼저 치환하고 있었다. 자를 만들자마자 값을 한 건 냈다는 뜻이다.
PRE_FRAC_MACROS = ("mathrm", "text", "vec", "dot", "ddot", "mathbf", "mathcal", "mathfrak", "hl", "sqrt")
from .checks_originality import check_chapter_file as check_originality
from .checks_originality import PROMPT_COLLECTIONS
from .checks_errorlog import (
    errorlog_issues, load_errorlog, pitfall_entry_reference_issues,
)

# 오답로그 정합성을 이 빌드에서 이미 신고한 데이터 폴더 (챕터마다 중복 신고 방지).
_ERRORLOG_REPORTED = set()


# 글 밀도 — 삽화 없이 이어져도 되는 단락 수의 한계, 그리고 error로 올릴 챕터.
# 검수를 마친 챕터부터 strict로 올린다(SVG 검사와 같은 승격 방식).
DENSITY_MAX_GAP = 6
BOLD_MAX_PER_PARAGRAPH = 3
BOLD_MAX_PER_LINE = 2
# ★ 6 → 4 (2026-07-31, 사용자 승인). [사용자 발화 인용 생략]
# 실측 평균이 2.0~2.7인데 상한만 6이라 **한 절에 6개(떠올리기 5)** 인 곳이 다섯 군데 있었다 —
# 상한이 평균의 3배면 그건 한계가 아니라 방치다. 분포는 `tools/audit_checks_load.py` 가 낸다.
CHECKS_MAX_PER_SECTION = 4
PROSE_STYLE_STRICT_CHAPTERS = {"ch00.json", "ch01.json", "ch02.json", "ch03.json",
                               "ch04.json", "ch05.json", "ch06.json", "ch07.json",
                               "ch12.json"}
# ch02는 삽화 9건을 신설해 한계를 통과시킨 뒤 error로 승격했다(2026-07-22).
# ch01·ch03은 아직 위반이 남아 경고 상태다 — 각 챕터를 정리하는 커밋에서 여기에 추가할 것.
# 경고로 남겨두면 경고 더미에 묻혀 아무것도 막지 못한다.
DENSITY_STRICT_CHAPTERS = {"ch00.json", "ch01.json", "ch02.json", "ch03.json",
                           "ch04.json", "ch05.json", "ch06.json", "ch07.json",
                           "ch12.json"}
# halo 글자의 여백 검사(F1). 예외를 걷어내자 ch01에서 14건이 드러났다 — 그동안 어떤 겹침
# 검사도 받지 않던 라벨들이다. ch01·ch03을 정리하는 커밋에서 여기에 추가할 것.
HALO_GAP_STRICT_CHAPTERS = {"ch00.json", "ch01.json", "ch02.json", "ch03.json",
                            "ch04.json", "ch05.json", "ch06.json", "ch07.json",
                            "ch12.json"}
# 화살표-도형 관통·화살촉 근접(F6). ch01·ch03은 정리 커밋에서 추가할 것.
ARROW_CLEARANCE_STRICT_CHAPTERS = {"ch00.json", "ch01.json", "ch02.json", "ch03.json",
                                   "ch04.json", "ch05.json", "ch06.json", "ch07.json",
                                   "ch12.json"}
# ★ 2026-07-30 신설 C1·C3·C4·C5 의 승격 목록 (2026-07-30 승격).
#
# 이 넷은 신설 당시 **경고**로 열렸다 — ch01 을 정리한 뒤 ch02~05 소급이 끝나면 올린다는 계획이었다.
# 소급이 끝나 전 챕터 0건이 됐으므로 여기서 error 로 올린다.
# **경고인 채로 두면 아무것도 막지 못한다** — 경고는 close 를 막지 않고, 경고 더미에 묻힌다
# (`test_strict_promotion_covers_all_chapters` 가 열린 이유가 정확히 이것이다).
# C2(물음-답 단위)는 신설 때부터 error 였으므로 이 목록에 없다.
CONTENT_SPEC_STRICT_CHAPTERS = {"ch00.json", "ch01.json", "ch02.json", "ch03.json",
                                "ch04.json", "ch05.json", "ch06.json", "ch07.json",
                                "ch12.json"}


def textbook_motif_hits(text, motifs):
    """교재가 쓴 소재를 본문이 그대로 쓰고 있는가 (AGENTS.md 규칙 12⑵).

    2026-07-22: ch02 열 절이 Cengel의 '음료 캔·갓 구운 감자'를 그대로 쓰고 있었다.
    규칙 12는 문서에만 있었고 기계가 소재를 본 적이 없어서, 사람이 원문과 나란히 놓고
    읽어야만 발견됐다. 목록은 data/열역학/textbook-motifs.json 이 정본이다.
    """
    return [m for m in motifs if m.get("term") and m["term"] in text]


# ★ 2026-08-01 merge 정리 — 지문 언어 검사는 **`prompt_language_issues` 하나로 통일**했다.
#   같은 지적이 같은 날 네 과목에 갔고 dynamics 도 등록부(`PROBLEM_PROMPT_LANG_BY_SUBJECT`)를
#   만들었는데, 공통 코드에 과목 이름을 박는 형태라 main 판(과목이 `index.json` 으로 선언)이
#   옳다. 같은 것을 재는 자를 둘 두면 반드시 갈라지므로 이쪽을 걷어냈다.

# 소재 검사에서 제외할 키 — 독자에게 안 보이거나, 교재 소재 이름이 나오는 것이 정상인 곳
# (출처·편집 메모). 나머지는 전부 검사한다.
MOTIF_EXEMPT_KEYS = {"source", "sourceRef", "sourcePages", "supplementNotes", "href", "id",
                     "lintWaivers"}


# ★ 경고는 '무기한 대기' 상태를 가질 수 없다 (열린 날 2026-07-28).
#
# 사용자 지적: ch01 삽화 경고 28건이 전부 `[warn/6-B 대기]`였고, 맨눈으로 짚어 준 불편이
# 그 목록 안에 그대로 있었다. [사용자 발화 인용 생략]
#
# **왜 안 고쳐졌나 (재발).** 2026-07-26에 같은 부류를 [사용자 발화 인용 생략] 로 진단해
# F4가 글자 이름을 찍게 고쳤다. 이름은 남았는데 **그래도 안 고쳐졌다** — 진짜 원인은
# 이름이 아니라 **만료의 부재**였다. `close_report.py`가 `exit 0 · 경고 N건`을 출력하면서
# 상태를 `close`로 찍어, 경고를 세는 코드가 곧 경고를 통과시키는 코드였다.
#
# 그래서 상태를 둘로 줄인다 — **error 아니면 사유를 적은 명시 면제.**
# 면제는 데이터(`diagrams[].lintWaivers`)에 남고 close 리포트가 매번 출력하므로
# 유한하고 보인다. **새 삽화는 면제가 없으니 자동으로 error다** — 이번처럼 아무도 모르게
# 쌓이는 일이 구조적으로 불가능해진다.
def _waiver_map(ch):
    out = {}
    for dg in _iter_diagrams(ch):
        if dg.get("lintWaivers"):
            out[dg.get("id", "?")] = dg["lintWaivers"]
    # ★ 절(theory.sections) 자체에 걸리는 경고도 같은 면제를 받는다 (2026-08-29) — 과목 간
    #   딥링크 경고가 첫 소비자다. 그 경고는 다른 git 브랜치를 못 건너가 기계로 못 닫으니,
    #   저자가 `git show` 로 확인한 뒤 사유와 함께 여기서 닫는다(위 「경고는 무기한 대기를
    #   가질 수 없다」와 같은 장치 — 삽화만 있고 절에는 없어서 이 경고가 영원히 열려 있었다).
    for s in (ch.get("theory") or {}).get("sections") or []:
        if s.get("lintWaivers"):
            out["section " + str(s.get("id", "?"))] = s["lintWaivers"]
    return out


def split_waived_warnings(warnings, waivers):
    """경고를 (면제된 것, 남은 것)으로 가른다. 순수 함수 — 테스트가 직접 부른다.

    `reason`이 비어 있으면 면제로 치지 않는다. 사유 없이 끄는 것은 이 장치가
    없애려는 '6-B 대기'와 똑같기 때문이다.
    `check`·`target`은 생략 가능하며, 적으면 경고 문자열에 포함될 때만 맞는다.
    """
    waived, left = [], []
    for w in warnings:
        fig = w.split(":", 1)[0].replace("[답 표시]", "").strip()
        for wv in waivers.get(fig) or []:
            if not str(wv.get("reason", "")).strip():
                continue
            if wv.get("check") and wv["check"] not in w:
                continue
            if wv.get("target") and wv["target"] not in w:
                continue
            waived.append((w, wv["reason"]))
            break
        else:
            left.append(w)
    return waived, left


def iter_visible_texts(node, trail="root"):
    """챕터 JSON 안의 '독자에게 보이는 문자열' 전부를 (위치, 문자열)로 흘린다.

    열린 날: 2026-07-22 — 본문의 감자를 셔츠로 바꿨는데 comprehensionChecks.answer가
    "감자가 갖고 있는 것은…"으로 남았다. 소재 검사가 theory.sections의 content와
    diagrams만 순회했기 때문이다(순회 범위 사각지대, 같은 부류 3회째).

    범위를 '볼 컬렉션 목록'으로 적으면 새 필드가 생길 때마다 또 새어나간다. 그래서
    **제외 목록만 두고 나머지 전부**를 훑는 방향으로 뒤집었다(기본값을 안전한 쪽으로).
    """
    if isinstance(node, dict):
        label = node.get("id")
        for key, value in node.items():
            if key in MOTIF_EXEMPT_KEYS:
                continue
            child = trail + "/" + str(key)
            if label and key != "id":
                child = trail + "[" + str(label) + "]/" + str(key)
            for hit in iter_visible_texts(value, child):
                yield hit
    elif isinstance(node, list):
        for index, value in enumerate(node):
            for hit in iter_visible_texts(value, trail + "[" + str(index) + "]"):
                yield hit
    elif isinstance(node, str):
        yield trail, node


# ★ 수학 기호가 인라인 수식 **밖**에 평문으로 남은 것 (열린 날 2026-07-28).
#
# 사용자 지적(3차 검수): [사용자 발화 인용 생략] /
# [사용자 발화 인용 생략]
#
# **왜 기존 검사가 못 잡았나.** 캐럿 검사(`^`)와 유니코드 첨자 검사(`inline_math_issues`)는 있었지만
# 둘 다 **첨자**만 본다. `∂N/∂x`·`∫p dx`·`y ≡ 0`은 첨자가 하나도 없어서 **어느 검사에도 안 걸린다.**
# 즉 빠뜨린 게 아니라 *그 기호들을 아무도 안 보는 구조*였다(규칙 7-⑷).
#
# 판정은 캐럿 검사와 같은 방식이다 — `mask_inline_math`로 `\(…\)` 안을 지운 뒤 남은 곳만 본다.
# `latex`·`equations`처럼 **필드 전체가 LaTeX인 곳은 제외**한다(거기서는 `∂`가 정상 표기다).
PLAIN_MATH_MARKS = ("∂", "∫", "≡", "√")
MATH_NATIVE_KEYS = ("/latex", "/equations", "/svg", "/solutionTemplate")


# ★ C12. 첨자를 **아예 안 쓰고** 기호에 숫자를 붙여 쓴 자리 (열린 날 2026-08-01, 사용자 재지적).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# **왜 여러 세션을 살아남았나 — 기존 검사는 전부 `_` 나 `^` 가 *있는* 것만 본다.**
# `plain_math_issues` 는 `_{`·`^{` 를, 첨자 렌더 검사는 `P_atm` 꼴을 본다. 그런데
# `h3` 는 **처음부터 마크업이 없어서** 어느 검사에도 걸리지 않는다. 그래서 고칠 때마다
# `_` 가 붙은 것만 고쳐졌고 날것으로 쓴 것은 매번 그대로 남았다.
# 실측 ch01: 풀이·삽화의 첨자는 전부 정상(`<sub>` 91곳)인데 **문제문 한 곳만** `h3` 였다 —
# 영문 원문을 옮겨 적으면서 마크업을 안 붙인 자리다.
#
# 판정: **한 글자 물리량 기호 + 한 자리 숫자**가 낱말 경계 안에 홀로 있으면 첨자 누락이다.
#   · `h3` · `P1` · `T2` · `V1` → 위반 (`h₃` 나 `h_3` 로 쓸 것)
#   · `Fe3C`(두 글자 원소) · `10-3` · `m³` → 기호가 한 글자가 아니거나 숫자가 아니라 통과
#   · 단위·연도·`A4` 류는 아래 기호 집합에 없다 — 열역학에서 첨자를 받는 기호만 넣었다.
# ★ `L` 은 뺀다 — 물리량보다 **항목 번호**(`L2 후보`·`L항목`)로 쓰이는 빈도가 높아 오탐이 난다.
_RAW_SUBSCRIPT = re.compile(r"(?<![0-9A-Za-z가-힣])([hPTVvWQmAsDρ])([0-9])(?![0-9A-Za-z])")
# ★ `changeNote` 는 **과거 사용자 지적을 그대로 인용**하는 리뷰 메타라 `h1`·`P2` 가 들어 있는 것이
#   정상이다(원문을 고치면 기록이 아니게 된다). 독자 화면에도 안 나온다 — 그래서 이 검사만 제외한다.
_RAW_SUBSCRIPT_EXEMPT = ("/changeNote",)


# ★★ C46. 첨자에 **한글**을 쓴 자리 (열린 날 2026-08-13, 사용자 판정 뒤 신설).
#
# 사용자: [사용자 발화 인용 생략]
# 그날 `94352e3` 이 12곳을 영어로 바꿨다(`W_{화성}`→`W_{mars}` · `W_{작업자+카트}`→`W_{worker+cart}` ·
# `v_{표}`→`v_{table}`). **그런데 막는 검사가 없어서 다시 들어온다** — 「close 의 정의」가 말하는
# *데이터만 고친 상태*이고, 그건 그 인스턴스를 지운 것이지 close 가 아니다.
#
# **왜 한글이 문제인가.** 같은 날 정한 첨자 크기(산문 `.imath` 0.72em · 유도 `.fmath` 0.68em ·
# 삽화 78%)는 **라틴 문자 기준으로 고른 값**이다. 한글은 획이 많아 같은 px 에서 먼저 뭉개진다 —
# 삽화 글자에 화면 실효 13px 하한을 둔 것과 같은 자리다. 한글 첨자만 크게 하는 조판 규칙을
# 새로 만드는 길도 있었지만 **사용자 판정으로 접었다**: 이 자료의 첨자는 이미 거의 전부 영어라
# (`P_atm`·`m_in`·`c_p`·`T_H`·`h_g`) 예외 하나를 살리려 규칙을 늘리는 것보다 예외를 없애는 쪽이 맞다.
#
# **판정선.**
#   ⑴ `_{…}` 안에 한글 음절이 있으면 신고. 중괄호 한 겹 중첩(`_{\mathrm{표}}`)까지 본다.
#   ⑵ 중괄호 없이 `_` 바로 뒤가 한글이어도 신고(`v_표`).
#   ⑶ 둘 다 **`_` 앞에 밑글자가 있어야** 발동한다 — 빈칸 표기 `___BLANK_1___` 처럼 밑줄이
#      이어지거나 공백 뒤에 오는 `_` 는 첨자가 아니다. 그래서 앞 글자가 공백·밑줄이면 건너뛴다.
#      (이 조건이 없으면 문풀 템플릿이 통째로 걸린다 — 자가 데이터를 이기면 검사가 꺼진다.)
#   ⑷ 삽화는 `_` 를 안 쓰고 `<tspan>` 으로 조판하므로 **다른 판정**을 쓴다:
#      **아래로 내려간(`dy` 가 양수) 작아진(부모보다 font-size 가 작은) tspan** 안의 한글.
#      ★ 두 조건이 **함께**여야 한다. 위첨자를 편 뒤 붙는 **되돌림 tspan 은 dy 가 양수인데
#        크기는 100%** 라(`unicode_superscript` 가 뒤 글자를 그 안에 넣는다) dy 만 보면
#        그 안의 정상 한글이 통째로 오탐이 된다.
# **`changeNote` 는 뺀다** — 리뷰 메타라 *지적 원문*(`W_{작업자+카트}` 를 고쳤다)을 그대로 인용하는
# 것이 정상이고, 원문을 고치면 기록이 아니게 된다(`_RAW_SUBSCRIPT_EXEMPT` 와 같은 이유).
_HANGUL_CHAR_RE = re.compile(r"[가-힣]")
_BRACED_SUBSCRIPT_RE = re.compile(r"(?<![\s_])_(\{(?:[^{}]|\{[^{}]*\})*\})")
_BARE_HANGUL_SUBSCRIPT_RE = re.compile(r"(?<![\s_])_([가-힣]+)")
_HANGUL_SUBSCRIPT_EXEMPT = ("/changeNote",)


def hangul_subscript_issues(ch):
    """첨자에 한글을 쓴 자리. 순수 함수 — 테스트가 직접 부른다. 판정선은 위 주석이 정본."""
    out = []

    def report(where, token):
        out.append(where + ": 첨자에 한글을 썼다 — " + repr(token)
                   + " · 첨자 크기는 라틴 문자 기준으로 정한 값이라 한글은 같은 px 에서 먼저"
                   " 뭉개진다. 이 자료가 이미 쓰는 영문 표기로 바꿀 것"
                   " (예: `_{표}` → `_{table}`). 처음 보는 독자가 그 낱말을 모를 수 있으면"
                   " 그 첨자가 무엇을 가리키는지 본문·해설에 한 줄로 밝힐 것.")

    for where, blob in iter_visible_texts(ch):
        if any(k in where for k in _HANGUL_SUBSCRIPT_EXEMPT):
            continue
        if where.endswith("/svg"):
            # 삽화는 `_` 를 안 쓰고 `<tspan>` 으로 조판한다 — 판정이 다르다(위 주석 ⑷).
            # ★ 여기서 `_iter_diagrams` 를 부르지 않는다. 그 함수는 `ch["theory"]["sections"]`·
            #   `ch["derivation"]["formulas"]` 가 **있다고 전제**해서, 절 하나만 담은 조각을
            #   넘기는 테스트와 개요 장에서 `KeyError` 로 죽는다. 순회는 이미 여기 하나면 된다.
            for t in _svg_texts(blob):
                for run in text_runs(t):
                    if run["depth"] == 0 or run["own_dy"] <= 0 or run["fs"] >= t["fs"]:
                        continue
                    if _HANGUL_CHAR_RE.search(run["s"]):
                        report(where, run["s"].strip())
            continue
        for m in _BRACED_SUBSCRIPT_RE.finditer(blob):
            if _HANGUL_CHAR_RE.search(m.group(1)):
                report(where, m.group(0))
        for m in _BARE_HANGUL_SUBSCRIPT_RE.finditer(blob):
            report(where, m.group(0))
    # `variables` 의 **키**도 화면에 그려지는 수식이다 — 값만 훑으면 그 자리가 사각지대로 남는다
    # (`iter_math_blobs` 독스트링의 2026-08-12 사고). 키 hit 만 골라 온다: 키는 trail 이
    # `…{키}` 로 끝나는 유일한 갈래라 산문 스팬·`latex` 와 겹치지 않는다.
    for where, blob in iter_math_blobs(ch):
        if not where.endswith("}"):
            continue
        for m in _BRACED_SUBSCRIPT_RE.finditer(blob):
            if _HANGUL_CHAR_RE.search(m.group(1)):
                report(where, m.group(0))
        for m in _BARE_HANGUL_SUBSCRIPT_RE.finditer(blob):
            report(where, m.group(0))
    return out


def raw_subscript_issues(ch):
    """첨자 마크업 없이 `h3` 처럼 붙여 쓴 자리. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for where, blob in iter_visible_texts(ch):
        if any(k in where for k in MATH_NATIVE_KEYS + _RAW_SUBSCRIPT_EXEMPT):
            continue
        for m in _RAW_SUBSCRIPT.finditer(mask_inline_math(blob)):
            out.append(where + ": 첨자를 안 쓰고 붙여 썼다 — " + repr(m.group(0))
                       + " → 유니코드 첨자(`" + m.group(1) + "₃` 꼴)나 `"
                       + m.group(1) + "_" + m.group(2) + "` 로 쓸 것. "
                       "이 부류는 `_` 가 없어서 다른 첨자 검사에 **하나도 안 걸린다**: "
                       + repr(blob[:60]))
            break
    return out


# ★ 절 번호는 순서에서 나온다 — 링크 라벨의 숫자가 그 순서와 맞는가 (열린 날 2026-08-02).
#
# 사용자 지적: [사용자 발화 인용 생략] — 본문은 **교재 절 번호**로 앞 절을 가리키는데
# 정작 절 제목에는 번호가 없어서, 독자는 그 §1.3 이 이 문서의 어디인지 알 방법이 없었다.
#
# 처방(사용자 결정): 절 제목은 뷰어가 **순서로** 번호를 매기고(데이터에 박지 않는다),
# 본문은 `[[chNN:sec-id|N절 제목]]` 내부 링크로 간다.
# 그러면 남는 위험은 하나다 — **라벨의 `N` 과 실제 순서가 갈라지는 것.**
# 절을 재배열하면 조용히 어긋나고, 화면에는 틀린 번호가 그대로 찍힌다.
# 그래서 그 한 가지를 검사가 잡는다. `N절` 형태를 쓸 때만 발동하므로 다른 과목에는 영향이 없다.
_THEORY_LINK_RE = re.compile(r"\[\[(ch\d{2}):([A-Za-z0-9_-]+)\|\s*(\d+)절")


def exam_step_equation_issues(ch):
    """C51. 시험 모드의 **수치 답 칸**이 식 사슬을 함께 내는가. 순수 함수.

    열린 날 2026-08-26 — 사용자: [사용자 발화 인용 생략].

    ★★ **재발이다.** 나루 원장 2026-08-19(열역학 유도 공식 4): [사용자 발화 인용 생략]. 그때는 **데이터만 고치고
      자를 안 만들었다.** 그래서 2026-08-26 에 새 필드(`exam.steps[].why`)가 생기자마자 같은
      결함이 그대로 다시 났다 — 원인은 「빠뜨렸다」가 아니라 **빠뜨려도 통과되는 구조**다.

    판정선은 셀 수 있는 형태로 잡는다(실행 규율 17) — **원래 식 한 줄 + 값을 넣은 줄**이므로
    `equations` 가 **두 줄 이상**이어야 한다. 「지문이 준 값 그대로」인 칸도 정의식과 대입식
    두 줄로 적을 수 있으므로 예외를 두지 않는다.

    ★ `written`·`choice`·`ox`·`order`·`match` 칸은 대상이 아니다 — 수를 얻는 자리가 아니다.
    ★ 이 검사는 **`exam` 을 쓰는 장에서만 발동한다**(선언이 곧 opt-in) — 시험 모드가 없는
      과목의 빌드를 멈추지 않는다.
    """
    out = []
    for q in (ch.get("problems") or []):
        for i, st in enumerate(((q.get("exam") or {}).get("steps")) or []):
            if not isinstance(st, dict) or st.get("type") != "number":
                continue
            eqs = st.get("equations") or []
            if len(eqs) >= 2:
                continue
            out.append(
                "problems[" + str(q.get("id")) + "]/exam/steps[" + str(i) + "]["
                + str(st.get("id")) + "]: 수치 답 칸이 식 사슬을 안 낸다 — `equations` 가 "
                + str(len(eqs)) + "줄이다. **원래 식 한 줄과 값을 넣은 줄**을 함께 적을 것"
                " (결과만 적으면 그 값이 어디서 왔는지 독자가 되짚을 자리가 없다."
                " 나루 원장 2026-08-19 과 같은 부류다).")
    return out


def exam_figure_language_issues(ch):
    """C52. **시험 모드 장의 문항 삽화**에 한글이 남아 있나. 순수 함수.

    열린 날 2026-08-27 — 사용자: [사용자 발화 인용 생략].

    ★★ **재발이다.** 2026-08-26 에 [사용자 발화 인용 생략] 를 받고 지문과 칸 라벨만 영어로 고쳤다. 삽화는 같은 「문항 층」인데
      **자가 없어서** 한글로 남았다 — 원인은 「빠뜨렸다」가 아니라 **C15(지문 언어)가
      `prompt` 만 보고 `diagrams[].svg` 는 안 보는 구조**다. 그래서 이번엔 데이터만 고치지
      않고 이 검사를 함께 연다(「close 의 정의」).

    판정선은 **층**이다 — 문항이 소유한 삽화(`problems`·`practice`)만 본다. 그 면이 곧
    시험지이고, 그 시험이 영문 교재를 따라가기 때문이다. **이론 절의 삽화는 대상이 아니다** —
    모의고사 장의 이론 탭은 한국어 안내가 정본이다(사용자 2026-08-26: [사용자 발화 인용 생략]).

    ★ SVG 문자열을 **통째로** 본다. 텍스트 노드만 골라 세면 `<title>`·`aria-label` 처럼
      화면 밖에서 읽히는 자리가 샌다 — 이 리포의 SVG 는 id·클래스가 전부 ASCII 규약이라
      한글이 설 자리는 사람이 읽는 글자뿐이다.
    ★ 저자 전용 필드(`title`·`rationale`·`lintWaivers`)는 화면에 안 나가므로 안 본다
      (`renderDiagrams` 가 그리는 것은 `d.svg` 하나다).
    ★ **`examMode` 를 선언한 장에서만 발동한다**(선언이 곧 opt-in) — 시험 모드가 없는
      과목의 빌드를 멈추지 않는다.
    """
    if not ch.get("examMode"):
        return []
    out = []
    for coll in ("practice", "problems"):
        for q in (ch.get(coll) or []):
            if not isinstance(q, dict):
                continue
            for d in (q.get("diagrams") or []):
                if not isinstance(d, dict):
                    continue
                svg = d.get("svg") or ""
                hits = _HANGUL_CHAR_RE.findall(svg)
                if not hits:
                    continue
                sample = [s.strip() for s in re.findall(r"[^<>]*[가-힣][^<>]*", svg)][:3]
                out.append(
                    coll + "[" + str(q.get("id")) + "]/diagrams["
                    + str(d.get("id")) + "]: 시험 모드 장의 문항 삽화에 한글 "
                    + str(len(hits)) + "자 — **시험지 면은 영어다**(지문·칸 라벨과 같은 층)."
                    " 보기: " + " · ".join(s[:40] for s in sample))
    return out


# 요약 자리가 실어야 할 **등호 있는 식**의 바닥. 「고른 값」이다(실행 규율 16) — 동역학 여덟
# 장의 유도 카드 수가 2~5이고 그 중앙값이 셋이라, 한 장이 실제로 세우는 식의 수를 바닥으로
# 잡았다. 하나둘은 「언급」이지 「정리」가 아니고, 지적을 부른 실측이 열두 자리에 둘이었다.
# 이 수를 다시 만질 때는 그 근거를 다시 재고 여기 고쳐 적는다.
SUMMARY_MIN_FORMULAS = 3


def summary_formula_issues(ch):
    """C53. **요약 자리에 식이 있나.** 순수 함수.

    열린 날 2026-08-27 — 사용자: [사용자 발화 인용 생략]

    ★★ **실측이 지적을 그대로 뒷받침했다.** 동역학의 요약 자리 열둘(장별 요약 8 · 과목 요약 1 ·
      모의고사 3)에 든 글자가 12,269자인데 **등호가 있는 식은 둘뿐**이었다. 식은 전부 유도 탭의
      카드 25장에만 있고, 모의고사 세 장은 유도 카드가 0이라 **그 장 안에서 식에 닿을 길이
      아예 없었다.**

    ★ 원인은 「빠뜨렸다」가 아니다. 요약 절을 *「이론을 줄인 것」* 으로 정의했고 이론 본문이
      산문 중심이라, 줄이면 산문만 남는다. **요약이 「시험 직전에 여는 자리」라는 용도**를
      규격에 안 적어 둔 것이 구조다.

    문턱 3의 근거(실행 규율 16 — 「고른 값」) — 이 과목 여덟 장의 유도 카드 수가 2~5이고
    중앙값이 3이다. 식 한둘은 「언급」이지 「정리」가 아니므로 그 중앙값을 바닥으로 잡았다.
    3을 못 채우는 것이 옳은 장이 생기면 `strictWaivers` 에 사유와 함께 적는다.

    보는 자리는 둘이다 — ⑴ `chapterSummary: true` 절(장별 요약) ⑵ `examMode: true` 장의
    이론 절 전체(그 탭이 곧 범위 정리다). 둘 다 아닌 장은 0건이라 남의 빌드를 안 멈춘다.
    """
    targets = []
    sections = ((ch.get("theory") or {}).get("sections")) or []
    marked = [s for s in sections if isinstance(s, dict) and s.get("chapterSummary")]
    if marked:
        targets.append(("장별 요약 절", marked))
    elif ch.get("examMode"):
        targets.append(("모의고사 장의 정리 절", [s for s in sections if isinstance(s, dict)]))
    if not targets:
        return []
    out = []
    for where, secs in targets:
        found = []
        for s in secs:
            for body in re.findall(r"\\\((.*?)\\\)", s.get("content") or "", re.S):
                if "=" in body:
                    found.append(body.strip())
        if len(found) >= SUMMARY_MIN_FORMULAS:
            continue
        out.append(
            "theory.sections: " + where + "에 등호가 있는 식이 " + str(len(found))
            + "개다 — **최소 " + str(SUMMARY_MIN_FORMULAS) + "개**를 둘 것. 요약은 시험 직전에"
            " 여는 자리인데 산문만 있으면 그 자리에서 연습문제로 못 건너간다"
            " (식과 「언제 꺼내나」를 나란히 둔 표 한 벌이 규격이다).")
    return out


def chapter_summary_placement_issues(ch):
    """C50. 장별 요약 절(`chapterSummary: true`)은 **하나**이고 **맨 마지막**인가. 순수 함수.

    열린 날 2026-08-26 — 사용자: [사용자 발화 인용 생략] · [사용자 발화 인용 생략].

    새어나갈 뻔한 것: 요약은 데이터상 **이론 절**로 두고 뷰어가 화면만 「05 요약」 탭으로
    보낸다(새 최상위 컬렉션을 만들면 밀도·말투·용어·변경점 검사가 통째로 그 절을 안 본다).
    그런데 절 번호는 **순서에서 나온다** — 뷰어의 `theorySectionNo` 와 위쪽
    `theory_link_number_issues` 가 둘 다 `index + 1` 로 센다. 요약이 중간에 끼면 그 뒤 절의
    번호가 하나씩 밀리는데, **화면에서는 요약이 이론 탭에 없으므로** 독자가 세는 순서와
    자가 세는 순서가 갈린다. 맨 마지막으로 못 박으면 두 셈법이 구조적으로 같아진다.

    ★ 이 검사는 **데이터가 그 형태를 쓸 때만 발동한다** — `chapterSummary` 를 안 쓰는 과목은
      0건이라 남의 빌드를 멈추지 않는다(C8·C18 과 같은 설계).
    """
    sections = ((ch.get("theory") or {}).get("sections")) or []
    marked = [(i, s) for i, s in enumerate(sections)
              if isinstance(s, dict) and s.get("chapterSummary")]
    if not marked:
        return []
    out = []
    if len(marked) > 1:
        out.append("theory.sections: 장별 요약 절이 " + str(len(marked))
                   + "개다 — 한 장에 하나여야 한다(화면의 「요약」 탭 하나에 다 쏟아진다): "
                   + ", ".join(repr(s.get("id")) for _, s in marked))
    last = len(sections) - 1
    for i, s in marked:
        if i != last:
            out.append("theory.sections[" + str(i) + "]: 장별 요약 절 "
                       + repr(s.get("id")) + " 이 맨 마지막이 아니다("
                       + str(i + 1) + "/" + str(len(sections))
                       + "). 절 번호는 순서에서 나오는데 요약은 이론 탭에 안 보이므로,"
                       " 중간에 끼면 독자가 세는 번호와 링크 라벨의 번호가 갈린다.")
    return out


def theory_link_number_issues(ch, chapter_name=None):
    """`[[chNN:sec-id|N절 …]]` 의 N 이 그 절의 실제 순서와 같은가. 순수 함수."""
    sections = ((ch.get("theory") or {}).get("sections")) or []
    order = {s.get("id"): i + 1 for i, s in enumerate(sections)}
    out = []
    for where, blob in iter_visible_texts(ch):
        for m in _THEORY_LINK_RE.finditer(blob):
            target_ch, sec_id, label_no = m.group(1), m.group(2), int(m.group(3))
            # 다른 장으로 가는 링크는 그 장의 파일을 봐야 하므로 여기서 판정하지 않는다
            # (섣불리 통과시키는 것보다 '이 검사의 범위 밖'이라고 밝히는 편이 낫다 — 규칙 11).
            if chapter_name and target_ch != chapter_name:
                continue
            if sec_id not in order:
                continue        # 대상 존재 여부는 딥링크 검사가 본다
            if order[sec_id] != label_no:
                out.append(where + ": 링크 라벨의 절 번호가 실제 순서와 다르다 — "
                           + repr(m.group(0)) + " 인데 " + sec_id + " 는 "
                           + str(order[sec_id]) + "번째다. 절을 재배열하면 라벨도 함께 고칠 것"
                           " (제목 쪽 번호는 뷰어가 순서로 매기므로 자동으로 맞는다).")
    return out


# ★ 이론을 재배열했으면 유도도 같이 옮긴다 (열린 날 2026-08-02).
#
# 사용자 지적: [사용자 발화 인용 생략]
# 실측(공학수학 ch01): 이론은 변수분리 → 선형 → 완전미분 → 적분인자로 재배열했는데
# 유도는 **교재 순서 그대로** 변수분리 → 완전미분 → 적분인자 → 선형이었다.
# 그 결과 이론 본문의 [사용자 발화 인용 생략] 가
# 유도 탭에서는 **거짓**이 됐다 — 두 탭이 서로 다른 이야기를 한 것이다.
#
# **왜 아무도 못 봤나:** 두 순서를 이어 주는 것이 데이터에 **없었다.** 이론 절과 유도 카드는
# 서로를 모르는 남남이라, 한쪽만 옮겨도 어떤 검사에도 안 걸린다. 빠뜨림이 아니라
# *빠뜨려도 통과되는 구조*다. 그래서 유도에 `sectionRef`(그 카드가 속한 이론 절 id)를 두고,
# 유도 순서가 절 순서와 **어긋나지 않는지**(비내림차순)를 검사한다.
# `sectionRef` 가 없으면 판정하지 않는다 — 과목마다 도입 시점이 다르므로 **선언한 과목만** 잰다.
def derivation_section_order_issues(ch):
    """유도 카드 순서가 이론 절 순서를 거스르지 않는가. 순수 함수 — 테스트가 직접 부른다."""
    sections = ((ch.get("theory") or {}).get("sections")) or []
    order = {s.get("id"): i + 1 for i, s in enumerate(sections)}
    formulas = ((ch.get("derivation") or {}).get("formulas")) or []
    out, seen = [], []
    for f in formulas:
        ref = f.get("sectionRef")
        if not ref:
            continue
        if ref not in order:
            out.append("derivation[" + str(f.get("id")) + "]: sectionRef 가 가리키는 이론 절이 없다 — "
                       + repr(ref))
            continue
        seen.append((f.get("id"), ref, order[ref]))
    for (prev_id, _prev_ref, prev_no), (cur_id, cur_ref, cur_no) in zip(seen, seen[1:]):
        if cur_no < prev_no:
            out.append("derivation[" + str(cur_id) + "]: 유도 순서가 이론 절 순서를 거스른다 — "
                       + str(prev_id) + "(" + str(prev_no) + "절) 다음에 "
                       + str(cur_id) + "(" + str(cur_no) + "절)이 온다. "
                       "`python tools/reorder_sections.py --collection derivation` 으로 맞출 것.")
    return out


def plain_math_issues(ch):
    """인라인 수식 밖에 남은 수학 기호. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for where, blob in iter_visible_texts(ch):
        if any(k in where for k in MATH_NATIVE_KEYS):
            continue
        # 문풀 빈칸의 정답은 `solutionTemplate`(LaTeX)의 구멍에 그대로 꽂힌다 → 여기도 LaTeX 자리다.
        if "/blanks[" in where and where.endswith("/answer"):
            continue
        outside = mask_inline_math(blob)
        marks = sorted({c for c in PLAIN_MATH_MARKS if c in outside})
        # 중괄호 첨자(`y^{1-a}`·`y_{2}`)도 같은 부류다 — 기존 캐럿 검사는 **유도의 plain 필드만**
        # 보므로 체크 답·채점 키워드는 범위 밖이었다(사용자가 `y^{1-a}`로 지적한 자리).
        if re.search(r"[\^_]\{", outside):
            marks.append("^{ · _{")
        # ★ 중괄호 **없는** 캐럿 첨자 (열린 날 2026-08-02, 브라우저 DOM 실측).
        #   `x^m` 은 renderMath 를 타는 필드가 아니면 화면에 **캐럿째** 찍힌다.
        #   실측: ch02 이론 절 표제 `오일러-코시 방정식 — x^m 대입` 이 표제·목차·복습
        #   **3곳**에 그대로 나오고 있었다. 왜 아무도 못 봤나 —
        #   ⑴ 캐럿 검사는 `derivation` 의 plain 필드만 순회했고
        #   ⑵ 이 함수는 `^{` **중괄호꼴만** 봤다. 절 표제는 둘 다의 밖이다.
        #   빠뜨림이 아니라 **범위의 사각지대**이고, 고치는 자리는 데이터가 아니라 범위다
        #   (선례: 이해도 체크가 `theory.sections` 만 돌던 2026-07-21 건).
        if re.search(r"\^(?=[A-Za-z0-9(])", outside):
            marks.append("중괄호 없는 ^")
        if marks:
            out.append(where + ": 수학 기호가 인라인 수식 **밖**에 평문으로 있다 — "
                       + "·".join(marks) + " → 화면에 글자로 찍힌다. "
                       "\\(\\frac{∂M}{∂y}\\)처럼 \\(…\\) 안에 넣을 것: " + repr(blob[:60]))
    return out


# ★ 평문으로 쓴 **분수** (열린 날 2026-07-30 — 사용자 지적 4회째, 기계 방지가 없어서 또 났다).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# **왜 기존 검사가 못 잡았나.** `plain_math_issues` 는 `∂ ∫ ≡ √` 와 중괄호 첨자만 본다.
# `P = F/A`·`F₁/A₁`·`(F − mg)/m` 에는 그 기호가 하나도 없어서 **어느 검사에도 안 걸렸다.**
# 2026-07-30 인박스 V-11 에서 이미 [사용자 발화 인용 생략] 로 적어 두고 **넣지 않아서** 재발했다.
#
# **왜 `/` 전부를 잡지 않는가.** 단위(`m/s²`·`kJ/kg`·`N/m³`)도 `/` 를 쓴다. 그건 분수가 아니라
# 단위 기호라 세로 조판하면 오히려 틀린다. 그래서 **단위에는 거의 나타나지 않는 세 모양**만 본다:
#   ⑴ `/` 에 **괄호가 맞붙은 것** — `(F − mg)/m`, `(1 kg·m/s²)/(1 N)`
#   ⑵ `/` 양옆에 **아래첨자가 붙은 변수** — `F₁/A₁`, `m_w/m`, `P₂/P₁`
#   ⑶ **미분 표기** — `dP/dz`
# 셋 다 '양(quantity)의 비'이지 단위가 아니다. 좁게 잡는 대신 **오탐이 없다** —
# 넓게 잡아 오탐이 나면 다음 사람이 검사를 꺼 버리고, 그게 이 부류가 다시 사는 길이다.
_SUB = "₀₁₂₃₄₅₆₇₈₉"
_VAR = "A-Za-zρσγμ"
FRACTION_SHAPES = (
    # ⑴ 괄호 안에 **연산자**가 든 묶음 — `(F − mg)/m`, `(270 − 3×9.79)/3`
    #    괄호만으로 잡으면 단위 묶음 `kJ/(kmol·K)`·`W/(m²·°C)` 이 통째로 오탐이 된다.
    re.compile(r"\([^()]{0,48}[−+×][^()]{0,48}\)\s*/|/\s*\([^()]{0,48}[−+×][^()]{0,48}\)"),
    # ⑵⑶ 아래첨자가 붙은 변수 — 단위 기호에는 아래첨자가 없다
    re.compile(r"[" + _VAR + r"][" + _SUB + r"]\s*/|/\s*[" + _VAR + r"][" + _SUB + r"]"),
    re.compile(r"[" + _VAR + r"]_[A-Za-z0-9]+\s*/|/\s*[" + _VAR + r"]_[A-Za-z0-9]+"),
    # ⑷ 미분 표기
    re.compile(r"\b[d∂][A-Za-zρ]\s*/\s*[d∂][A-Za-zρ]\b"),
    # ⑸ 분모가 밀도항 — `P/(ρg)`·`ΔP/(ρ_Hg·g)`. ρ 는 단위 기호가 아니다
    re.compile(r"/\s*\([^()]*ρ[^()]*\)"),
)


# ★★ 인라인 수식 **안**의 슬래시 분수 (열린 날 2026-08-01 — 사용자 **재지적**).
#
# 사용자: [사용자 발화 인용 생략]
#
# **구조적 원인이 뼈아프다 — 앞 라운드의 처방이 이 라운드의 결함을 만들었다.**
# `plain_fraction_issues` 는 `mask_inline_math()` 로 수식을 **가린 뒤 바깥만** 본다. 그래서
# 2026-07-31 에 [사용자 발화 인용 생략] 로 48곳을 고쳤을 때, 옮겨진 글자는
# **검사가 아예 보지 않는 자리로 들어갔다.** `\(a^{2}/4\)` 는 화면에 여전히 슬래시가 보이는데
# 검사는 통과한다 — 검사가 **틀린 이동을 보상**하고 있었던 것이다.
# 규격(AGENTS 「분수는 글자로 쓰지 않는다」)은 처음부터 *화면에 슬래시가 보이면 위반*이었고,
# 그 규격을 재는 자만 수식 안쪽에 없었다.
#
# 통과시키는 것:
#   ⑴ 지수·아래첨자 안 — `y^{2/3}` 은 분수 조판 대상이 아니라 지수 표기다.
#   ⑵ **단위** — `kJ/kg`·`m/s` 는 나눗셈 조판이 아니라 단위 기호다(AGENTS 가 명시적으로 제외한다).
#      단위 목록은 과목 무관한 SI 기호만 둔다 — 특정 과목의 낱말을 넣으면 공통이 그 과목을 아는 셈이다.
_MATH_SPAN_RE = re.compile(r"\\\((.+?)\\\)", re.S)
_SUP_SUB_GROUP = re.compile(r"[\^_]\{[^{}]*\}")
_MATHRM_GROUP = re.compile(r"\\(?:mathrm|text|operatorname)\{[^{}]*\}")
# 첫 글자를 ASCII로 열거하면 화면상 같은 `∂u/∂T`·`Δh/Δt`·`ρ/μ`만 빠진다.
# Python의 유니코드 낱말 문자에 수학 기호 `∂`·`∆`를 보태 같은 화면 표기를 한 자로 본다.
_SLASH_ATOM = r"(?:[^\W\d_]|[0-9∂∆])(?:[\w∂∆\\^{}]*)"
_SLASH_FRAC = re.compile(r"(" + _SLASH_ATOM + r")\s*/\s*(" + _SLASH_ATOM + r")")
_UNICODE_PARTIAL_FRAC = re.compile(r"∂([A-Za-zΑ-Ωα-ω]+)\s*/\s*∂([A-Za-zΑ-Ωα-ω]+)")


def normalize_unicode_partial_fractions(text):
    """유니코드 편미분 슬래시를 정본 LaTeX 분수로 바꾼다."""
    return _UNICODE_PARTIAL_FRAC.sub(
        lambda m: r"\frac{\partial " + m.group(1) + r"}{\partial " + m.group(2) + "}",
        str(text or ""),
    )
# ★★ 단위 등록부는 **하나뿐이다** — `UNIT_BASES` + `_is_unit_token`(아래쪽에 정의).
#
# 열린 날 2026-08-02 (사용자 지적 **8회째**: [사용자 발화 인용 생략]).
# 여기에는 원래 `UNIT_TOKENS` 라는 **두 번째 등록부**가 있었다. 2026-08-01 에
# `math_slash_fraction_issues`(수식 **안**의 슬래시)를 새로 만들면서 목록을 새로 적었는데,
# 그 목록은 **2026-07-31 에 이미 걸러낸 애매한 기호들을 그대로 담고 있었다** —
# `g`·`mg`·`A`·`V`·`C`·`F`. 즉 산문에서는 잡히는 `F/A`·`mg/A` 가 `\(…\)` 안에서는
# 통과했다. 이 리포가 여러 번 닫은 **"자를 두 벌 두면 갈라진다"** 의 재발이고,
# 하필 *분수*라는 같은 부류에서 났다(2026-07-31 원장: 삽화 자와 산문 자가 갈렸던 그 자리).
#
# 그래서 목록을 지우고 두 검사가 **같은 함수**를 부르게 했다. 새 등록부를 만들지 말 것.


def _bare(token):
    """연산자 토큰에서 중괄호·지수를 걷어낸 알맹이."""
    return re.sub(r"[\^\{\}\\]", "", token or "")


def iter_math_blobs(ch):
    r"""화면에 **수식으로 그려지는** 문자열 전부를 (위치, LaTeX)로 흘린다.

    ★ 열린 날 2026-08-12 — `formula.variables` 의 **키**를 아무 검사도 보지 않았다.
      뷰어는 그 키를 `renderMath(k)` 로 그리는데(템플릿 3306행), `iter_visible_texts` 는
      dict 의 **값만** 흘린다. 그래서 ch05 `steady-flow-energy-balance` 의 변수 설명 키가
      `h + V^{2}/2 + gz` 로 **텍스트 분수**인 채 11회째 지적을 받고도 통과했다
      (사용자: [사용자 발화 인용 생략] — 분수 부류 11회째).
      **빠뜨림이 아니라 순회의 사각지대다** — 값만 훑는 한 몇 번을 고쳐도 다시 들어온다.

    세 갈래를 한 자리에 모은다. ⑴ 산문 안의 `\( … \)` 스팬 ⑵ 값 전체가 LaTeX 인 필드
    (`latex`·`equations`) ⑶ `variables` 의 키. 부르는 쪽은 셋을 구별할 필요가 없다.
    """
    def walk(node, trail, key=None):
        if isinstance(node, dict):
            if key == "variables":
                # ★ 여기가 사각지대였다 — 키가 곧 화면에 그려지는 수식이다.
                for k in node:
                    yield trail + "{" + str(k) + "}", str(k)
            for k, v in node.items():
                if k == "svg":          # SVG 는 LaTeX 가 아니다(인라인 수식이 렌더 안 된다)
                    continue
                for hit in walk(v, trail + "/" + str(k), k):
                    yield hit
        elif isinstance(node, list):
            for i, v in enumerate(node):
                for hit in walk(v, trail + "[" + str(i) + "]", key):
                    yield hit
        elif isinstance(node, str):
            if key in MATH_ONLY_KEYS:
                yield trail, node
            else:
                for span in _MATH_SPAN_RE.findall(node):
                    yield trail, span
    for hit in walk(ch, "root"):
        yield hit


def _blank_same_length(m):
    """가리되 **길이를 보존**한다 — 좌표가 원문과 1:1이어야 처방이 그 자리를 고칠 수 있다."""
    return " " * (m.end() - m.start())


def slash_fraction_spans(span):
    r"""수식 하나 안의 슬래시 분수 [(시작, 끝, 분자, 분모)] — 좌표는 **원문과 같다**. 순수 함수.

    ★ **자와 처방이 같은 함수를 쓰게 하려고 갈라냈다** (2026-08-12, 공학수학 세션 보고).
      [사용자 발화 인용 생략] — 손으로 고치면 과목마다 갈라지고, 그 갈라짐이 이 검사가 없애려는 결함이다.
      그렇다고 처방이 판정을 **다시 구현하면** 이 파일이 여러 번 겪은 그 사고가 난다
      (`declared_roles`·`tone_segments` 선례: 검사는 신고하는데 도구는 안 고치는 상태).
      그래서 **찾는 일은 여기 하나**이고, `tools/fix_math_slash_fraction.py` 는
      *어디까지 기계가 고쳐도 되는가* 만 판정한다.

    예전에는 가림표를 한 칸짜리 공백으로 눌러 길이가 달라졌다 — 신고만 할 때는 상관없지만
    고칠 자리를 짚을 수 없다.
    """
    probe = _MATHRM_GROUP.sub(_blank_same_length,
                              _SUP_SUB_GROUP.sub(_blank_same_length, span or ""))
    out = []
    for m in _SLASH_FRAC.finditer(probe):
        num, den = m.group(1), m.group(2)
        # 단위 판정은 산문·삽화와 **같은 함수**로 한다(위 주석 참조).
        if is_mathrm_unit(num) or is_mathrm_unit(den):
            continue                  # 로만체로 **선언한** 단위 — 이름을 안 본다
        if _is_unit_token(_bare(num)) or _is_unit_token(_bare(den)):
            continue                  # 단위 기호 — 나눗셈 조판이 아니다
        # ★ 슬래시 위치도 함께 준다. 가림표 안에도 `/` 가 있을 수 있어서(`x^{a/b}/3`)
        #   처방이 원문에서 다시 찾으면 **엉뚱한 슬래시를 가른다.** 찾은 자가 알려 줘야 한다.
        slash = probe.index("/", m.start(1) + len(num), m.end())
        out.append((m.start(), slash, m.end(), num, den))
    return out


def math_slash_fraction_issues(ch):
    """인라인 수식 안에서 `/` 로 쓴 분수. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for where, span in iter_math_blobs(ch):
        for _at, _slash, _end, num, den in slash_fraction_spans(span):
            out.append(
                where + ": 수식 안에서 분수를 슬래시로 썼다 — "
                + repr(_bare(num) + "/" + _bare(den))
                + " → `\\frac{…}{…}` 로 조판할 것 (화면에 슬래시가 보이면 위반이다."
                " 지수 안 `y^{2/3}` 과 단위 `kJ/kg` 는 대상이 아니다"
                " · `python tools/fix_math_slash_fraction.py --apply` 가 확실한 것만 고친다): "
                + repr(span[:60]))
    return out


# ★ 독자 환경 단정 (열린 날 2026-08-01 — 사용자 **재지적**).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# **원인은 빠뜨림이 아니다 — 승격에 브레이크가 없었다.** 이 리포는 *지적·사실 → 원장 → 규칙 승격*
# 을 미덕으로 삼는데, **무엇이 승격될 자격이 있는가**를 가르는 자리가 없었다. 그래서 사용자가
# 참고로 준 한 교수의 사정이 ⑴ 독자 본문(ch00 sec-exam 절 전체)과 ⑵ 공통 규칙(AGENTS 문제 설계 ⑸)
# 으로 **두 단계나** 올라갔다. 다른 교수 수업을 듣는 독자에게는 그대로 틀린 안내가 된다.
#
# 판정: 독자 환경을 가리키는 말이 **단정형**으로 나오면 걸린다. **조건부면 통과**한다 —
# 목적은 그 주제를 못 쓰게 하는 것이 아니라 *독자의 조건으로 단정하지 못하게* 하는 것이다.
#   ✗ "이 과목은 기말에 공식집을 줍니다"      ✓ "공식집을 주는 수업이라면 …"
#   ✗ "시험에 제공되는 공식은 …"              ✓ "확인된 한 사례에서는 …"
#
# ※ 낱말은 **과목 무관한 것만** 둔다(공학 과목이면 어디서나 쓰는 말). 특정 과목의 용어를 넣으면
#   이 파일이 그 과목을 아는 셈이 되어, 이 리포가 네 번 겪은 그 부류가 된다.
READER_ENV_TERMS = ("공식집", "요약표", "우리 수업", "이번 학기", "담당 교수", "우리 교수")
# 조건·출처 표지. 하나라도 같은 문단에 있으면 '단정'이 아니다.
READER_ENV_HEDGES = ("다면", "라면", "수업에 따라", "사례", "다를 수 있", "없을 수 있",
                     "여러분 수업", "확인된", "확인한", "안내를 정본", "경우에는", "수업마다")


def reader_environment_issues(ch):
    """독자의 수업 환경을 단정한 곳. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for where, blob in iter_visible_texts(ch):
        for para in re.split(r"\n\s*\n", str(blob or "")):
            hit = next((t for t in READER_ENV_TERMS if t in para), None)
            if not hit or any(h in para for h in READER_ENV_HEDGES):
                continue
            out.append(
                where + ": 독자의 수업 환경을 단정했다 — " + repr(hit)
                + " (이건 한 교수·한 학기의 사정이고 독자는 다를 수 있다."
                " 조건부로 쓸 것: '공식집을 주는 수업이라면 …', 목록은 '확인된 한 사례'로"
                " 명시. 제작 참고용 사실은 .claude/SUBJECT.md 에 둔다): " + repr(para[:60]))
    return out


# ★ C22. 우리 절을 가리킬 때 `§N` 대신 **`N절`** (열린 날 2026-08-02, 사용자 지적).
#
# 사용자: [사용자 발화 인용 생략] — 맞다. 뷰어가 목차·표제에 `N절 ` 을 붙이는데(템플릿의
# `(n ? n + '절 ' : '') + fmtText(s.heading)`) 본문 상호참조만 `§N` 이라, **독자는 화면에서
# 한 번도 본 적 없는 이름으로 안내받는다.** 실측 동역학 ch12 **26곳**.
#
# ★ 교재 절은 대상이 아니다. `Cengel §2.3` 처럼 **점이 붙은 번호**는 교재의 절 표기라
#   우리 목차와 무관하다 — 숫자 뒤에 `.숫자` 가 오면 통과시킨다. 출처 필드는 애초에
#   `MOTIF_EXEMPT_KEYS` 로 순회 밖이다(화면에 안 나간다).
#
# ★ 2026-08-02(같은 날 2차) — **역추적이 그 면제를 무력화하고 있었다** (고체역학 실측).
#   `§\s*\d+(?!\s*\.\s*\d)` 로는 `§12.4` 에서 엔진이 `\d+` 를 `12`→`1` 로 줄여 재시도하고,
#   그때 뒤가 `2` 라 `.숫자` 가 아니므로 **lookahead 가 통과해 `§1` 이 잡힌다.**
#   즉 **두 자리 장 번호를 쓰는 과목의 교재 절이 전부 오탐**이 된다(동역학 12~19장,
#   고체역학 §12.4). 하이픈 표기(`Cengel §2-3`)도 같은 이유로 `§2` 로 잡혔다.
#   → 숫자를 다 먹었는지(`(?!\d)`)를 먼저 못박아 역추적을 막고, 구분자에 `-` 도 넣는다.
_OUR_SECTION_MARK = re.compile(r"§\s*\d+(?!\d)(?!\s*[.\-]\s*\d)")


def section_ref_style_issues(ch):
    """우리 절을 `§N` 으로 가리킨 자리. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for where, blob in iter_visible_texts(ch):
        for m in _OUR_SECTION_MARK.finditer(blob):
            out.append(where + ": 우리 절은 `N절` 로 가리킨다 — " + repr(m.group(0))
                       + " → " + repr(m.group(0).replace("§", "").strip() + "절")
                       + " (뷰어가 목차·표제에 `N절` 을 붙인다. 교재 절 `§2.3` 은 대상 아님): "
                       + repr(blob[max(0, m.start() - 20):m.end() + 20]))
    return out


# ★ C23. 독자에게 말하는 글의 **말투** (열린 날 2026-08-02, 사용자 지적).
#
# 사용자: [사용자 발화 인용 생략]
#
# ★ **관행은 있었는데 문서가 없었다.** AGENTS·docs 전수 grep 에 말투 조항이 **0건**이었다.
#   규칙이 없으면 데이터가 마음대로 정한다 — `§N` 과 정확히 같은 부류이고, 이 리포에서
#   [사용자 발화 인용 생략] 의 세 번째다. 실측 동역학 ch12: 평어 **547문장** · 존댓말 15 —
#   **한 챕터 안에서도 이미 갈려 있었다.**
#
# 판정은 **문장 종결 위치**만 본다. 명사구 종결·영문 지문·채점 키워드는 말투를 물을 자리가 아니다.
# ★ 마침표와 공백 **사이의 마크업**을 구분자가 함께 먹는다 (2026-08-02, 육안 검수에서 잡았다).
#   `…둘은 갈라진다.** 선반 공구대가…` 처럼 굵게 표시가 문장 끝에 걸리면, `(?<=[.!?])\s+` 는
#   `.` 바로 뒤가 `*` 라 끊지 못하고 **다음 문장까지 한 덩어리**로 읽는다. 그러면 그 덩어리의
#   종결은 뒤 문장의 것이라, 안에 든 평어가 통째로 보이지 않는다(실제로 그렇게 남아 있었다).
# ★★ **줄표(`—`)도 문장 경계다** (2026-08-02, 사용자 지적: [사용자 발화 인용 생략]). 이 리포의 글은 `앞말 — 뒷말` 로 덧붙이는 문형을 자주 쓰는데, 줄표 **앞**이
#   이미 종결어미다. 문장 끝만 보던 자는 뒷말의 `~입니다` 만 읽고 통과시켰고,
#   그래서 **한 문장 안에 평어와 존댓말이 함께** 남았다(실측 34곳). 종결이 두 개면 둘 다 봐야 한다.
# ★★ **화살표(`→`) 앞도 같다** (2026-08-02, 기계재료 실측 — 줄표와 같은 부류다).
#   AGENTS 「콘텐츠 표기 규약」이 *변환·순서·대조는 화살표로 쓰라*고 권하는데, 그 왼쪽이
#   낱말이 아니라 **절**일 때가 많다(`방향이 어긋나면 결합이 끊긴다 → 매우 단단·취성`).
#   줄표만 경계로 보던 자는 그 절의 종결을 못 봤고, 그래서 **한 필드 안에 `맞닿는다 →` 와
#   `맞닿습니다 →` 가 나란히** 남아 있었다(ch03 실측 — 같은 줄이다).
#   왼쪽이 명사구·수식이면 판정이 `None` 이라 `A → B` 표기 자체는 영향을 받지 않는다.
# ★★ **공백을 둔 가운뎃점(` · `)도 같다** (열린 날 2026-08-04, ch01 `fig-closed-open-isolated`).
#   `점선 = 질량이 그 선을 지나간다 · 파랑 = 경계선을 가로지른다 · 회색 = 경계 앞에서 막힌다` 는
#   **한 조각으로 읽혀 끝의 `막힌다` 만** 판정된다. 마지막만 존댓말로 고치면 앞 두 절이 평어인 채
#   통과하고, 화면에는 한 줄 안에서 말투가 갈린 글이 남는다.
#   ★ 줄표(08-02)·괄호주석(08-02)·`~ㄹ 것`(08-04)에 이은 **같은 부류 4회째**다 — 뿌리는 하나,
#     이 자가 조각의 *끝만* 본다는 것. 그래서 이번에도 인스턴스가 아니라 **경계**를 고친다.
#   판정: **공백에 둘러싸인 것만** 경계로 센다. 붙여 쓴 가운뎃점은 나열이 아니라
#   ⑴ 단위 곱(`kg·m/s²`) ⑵ 2항목 병렬(`미분·적분`) 이라 절 경계가 아니다 — AGENTS 「표기 세부」가
#   [사용자 발화 인용 생략] 와 그 둘을 이미 갈라 놓았고, 여기서 같은 선을 쓴다.
#   나눠 놓고 보면 나열의 각 항이 명사구인 경우(`추가 3 · 수정 5 · 삭제 1`)는 판정이 `None` 이라
#   **조각을 더 잘게 나누는 것만으로 오탐이 늘지 않는다** — 좁히는 자가 아니라 넓히는 자다.
_SENT_SPLIT = re.compile(r"(?<=[.!?])[*_`)\]】」’\"']*\s+|\s+[—–→·]\s+|\n+")
# 평서형 `~다` 는 **모호하지 않다** — 이 자리에서 종결어미 말고 다른 것일 수 없다.
_PLAIN_DECL = re.compile(r"다[.!?]?$")
# ★★ 나머지 여섯은 **한 음절짜리 종결어미**라, 같은 글자로 끝나는 명사와 구별되지 않는다
#   (의문 가·까·나·냐 / 명령 라 / 청유 자). 실측(기계재료 2026-08-02) — 네 건이 평어로
#   신고됐는데 **넷 다 명사구**였다: `항복강도가`(주격조사) · `규칙적 배열 + 자유 전자` ·
#   `주황 = 원자가전자` · `…네 꼭짓점과 면심 하나`. 재료과학은 전자·원자·분자·격자·하나가
#   본문 낱말이라 이 자는 새 챕터마다 같은 오탐을 낸다(부류이지 인스턴스가 아니다).
#
#   ★ 왜 '문장이면 엄격, 조각이면 느슨'으로 가르지 않았나: **무엇이 문장인가를 이 자가 정한다.**
#     `_SENT_SPLIT` 이 줄표·화살표·줄바꿈에서 끊는 순간 조각의 오른쪽엔 마침표가 없고,
#     그 조각은 삽화 캡션과 똑같이 생겼다(`… 면심 하나 → \(4 × ¼ + 1 = 2\)개.` 의 왼쪽).
#     자를 두 벌 두면 **같은 글이 필드에 따라 다르게 판정**되므로 하나로 둔다.
#
#   판정: 이 여섯은 **문장부호가 붙어 있을 때만** 종결어미로 센다. 다만 수사의문
#   `~는가/은가/인가/던가` 는 물음표 없이도 종결이라 그대로 잡는다(변환기가 `~나요` 로 바꾼다).
#   평서형 `~다` 는 이 규칙 밖이다 — 위 `_PLAIN_DECL` 이 조건 없이 잡는다.
_PLAIN_SHORT = re.compile(r"(가|까|라|자|나|냐)[.!?]?$")
_PLAIN_ASK_TAIL = ("는가", "은가", "인가", "던가")
# ★★ **지시형 `~ㄹ 것` 은 종결어미가 아니라 의존명사 `것` 으로 끝난다** (열린 날 2026-08-04).
#   사용자: [사용자 발화 인용 생략]
#   맞다 — 그런데 이 자는 **0건**이라고 말하고 있었다(`audit_conventions [M]` 이 열역학
#   ch00~ch02 전부 `평어 종결 어절 0가지`). 위 세 판정이 전부 빗나가기 때문이다:
#   `_PLAIN_DECL`(`다$`)·`_PLAIN_SHORT`(한 음절 어미)·`_POLITE_TAIL` 중 무엇도 `것` 에 안 걸려
#   **명사구 종결로 조용히 통과**했다. 실측 grep 은 ch02 만 17곳이었다.
#
#   ★ 줄표(08-02)·괄호주석(08-02)에 이은 **같은 부류 3회째**다. 뿌리가 하나다 —
#     이 자는 문장의 *끝 모양*만 보므로, **종결어미가 아닌 형태로 끝나는 평어**는 매번 새로 샌다.
#     그래서 이번엔 인스턴스가 아니라 '어떤 형태가 남았나'를 먼저 물었다.
#
#   판정: `것` 바로 앞 음절의 **받침이 ㄹ** 이면 지시형이다(`볼 것`·`할 것`·`주의할 것`).
#   관형사형 어미 `-ㄹ` 이 붙은 자리이므로, 같은 글자로 끝나는 명사(`결과`·`목적`)와 겹치지 않는다.
#   오탐 여지: `먹을 것`(먹거리) 같은 **명사구**. 이 리포의 독자용 산문에는 나오지 않지만,
#   나오면 그 조각은 `것` 이 진짜 명사이므로 **문장 자체를 다시 쓰는 것이 옳다**(면제를 만들지 말 것).
_JONG_RIEUL = 8
#
#   ★★ **면제를 만들지 않았다** (2026-08-04 판단). 요건 나열의 굵은 표제
#     (`- **경계에 힘이 작용할 것** — 힘만 있고 …`)도 이 자에 걸린다. 마크업으로 표제를 가려
#     면제할 수도 있었지만 두 가지가 걸렸다: ⑴ `sentence_endings` 가 조각 앞의 `- **` 를 이미
#     벗겨서(`^[-*|>\s]+`) 마크업이 판정 시점에 남아 있지 않고 ⑵ 이 리포 원칙이
#     [사용자 발화 인용 생략] 다.
#     그래서 그 두 표제를 **명사구로 다시 썼다**(`경계에 작용하는 힘`·`움직이는 경계`).
# 조각의 **원문**이 문장부호로 끝났는가 — 뒤따르는 강조·괄호 표시는 넘겨서 본다.
_TERMINAL_PUNCT = re.compile(r"[.!?][*_`)\]】」’\"']*$")
_POLITE_TAIL = ("십시오", "세요", "어요", "아요", "나요", "가요", "까요", "시다", "니까")
_HANGUL_BASE, _JONG_BIEUP = 0xAC00, 17
# ★★ **문장 끝의 괄호주석이 종결어미를 가린다** (열린 날 2026-08-02, 공학수학 실측 20여 곳).
#   `한 점만 확인해도 충분하다(판정 정리).` 는 평어인데 자가 못 봤다 — 마지막 글자가 `)` 라
#   `_PLAIN_END` 가 안 걸리고, 그래서 `None`(명사구 종결)으로 **조용히 통과**했다.
#   같은 이유로 `…합니다(유도 탭).` 은 존댓말인데 존댓말로도 안 읽혔다. 즉 이 자는 괄호가
#   붙은 문장에 대해 **말투를 아예 묻지 않고 있었다** — 0건이 '없다'가 아니라 '안 봤다'였다.
#   가리는 것은 괄호이지 문장이 아니므로, 판정 전에 끝의 괄호주석을 벗긴다.
#   `(?<=[^\s(])` 가 필요한 이유: `(이것은 참이다)` 처럼 **문장 전체가 괄호**면 벗길 것이
#   아니라 괄호만 떼야 한다(통째로 벗기면 알맹이가 사라져 판정이 없어진다).
_TRAIL_PAREN = re.compile(r"(?<=[^\s(])\s*\([^()]*\)\s*$")
# ★ **연결어미로 끝난 조각은 문장이 아니다** (열린 날 2026-08-02, dynamics ch12).
#   `sentence_spans` 가 줄표를 문장 경계로 삼으면서(반존대를 잡으려고 넣은 규칙) 줄표 뒤의
#   **나열 조각**이 한 조각으로 떨어진다: `**물리적으로 묶여 있거나**(줄과 도르래) …보거나`.
#   그 조각의 끝 글자는 `나` 라 한 음절 종결어미 자(`_PLAIN_SHORT`)가 **평어로 읽었다** —
#   실제로는 종결어미가 아예 없는 조각이다. 종결이 없는 것에 말투를 물을 수는 없다.
#   ★ 같은 부류를 기계재료 세션이 [사용자 발화 인용 생략] 으로 좁혔는데
#   (`is_plain_ending`), 이 조각은 **원문이 마침표로 끝나서** 그 자에 걸리지 않는다.
#   둘은 상보적이라 함께 둔다 — 하나는 *부호가 있나*, 하나는 *종결어미가 있나* 를 본다.
#   ★ 이 자는 **좁히기만 한다** — 연결어미로 끝나면 그 뒤에 반드시 다른 절이 이어지므로,
#   진짜 평어 종결이 이 규칙에 가려질 수 없다.
_CONNECTIVE_END = re.compile(r"(거나|지만|면서|으며|며|아서|어서|려면|어야|아야|고|면)$")
# ★ **인용은 저자가 독자에게 하는 말이 아니다** (열린 날 2026-08-02, dynamics ch12 §7).
#   좌표계 신호어 목록이 문제 문장을 흉내 내 인용한다 —
#   `- "높이 h에서 수평으로 던진다", "위치가 …로 주어진다" → 직교`.
#   문제 지문은 평어로 적히므로 이 인용은 **평어가 맞다.** 자가 이걸 신고하면 두 가지가 함께 나빠진다:
#   ⑴ 규격을 지킨 글이 위반이 되고 ⑵ **변환기가 인용을 고쳐 쓴다**(`미끄러진다` → `미끄러집니다`).
#   ⑵ 가 더 나쁘다 — 남의 말을 바꿔 인용하는 것이고, 같은 목록의 `던진다`·`증가한다` 는
#   조각 중간이라 안 바뀌어 **한 목록 안에서 말투가 갈린다.**
#   그래서 판정이 아니라 **조각 만들기 단계**(`tone_segments`)에서 뺀다 — 검사와 변환기가
#   같은 함수를 부르므로 한 곳만 고치면 둘 다 따른다(자를 두 벌 두면 갈라진다).
_QUOTE_OPEN, _QUOTE_CLOSE = "\"'“‘「『", "\"'”’」』"


def _is_quoted(segment):
    """조각이 통째로 인용부호 안인가 — `"A", "B"` 처럼 인용을 나열한 것도 포함. 순수 함수.

    ★ 판정은 `tone_core` **앞**의 원문으로 한다. `tone_core` 는 꼬리에서 따옴표를 벗기므로
      알맹이로 물으면 닫는 따옴표가 이미 사라져 **언제나 거짓**이 된다(첫 구현이 그랬다).
    """
    body = (segment or "").lstrip("-*|> \t").rstrip().rstrip(".!?,·").rstrip()
    return len(body) > 1 and body[0] in _QUOTE_OPEN and body[-1] in _QUOTE_CLOSE


def tone_core(sentence):
    """말투를 판정할 알맹이 — 끝의 마침표·강조표시·괄호주석을 벗긴다. 순수 함수.

    **자는 하나여야 한다** — 존댓말 판정과 평어 판정이 서로 다른 꼬리를 벗기면,
    한쪽만 보이는 문장이 생긴다(그게 위 괄호주석 사고의 형태였다).
    """
    core = sentence.strip()
    # ★ **물음표는 남긴다.** 질문의 존댓말은 `~나요?` 라서(AGENTS 「말투」) 조각이 질문인지가
    #   판정을 바꾸는데, 그 신호는 `?` 하나뿐이다. 처음에 `.!?` 를 다 벗겼더니 조각에서
    #   물음표가 사라져 `유일한가?` 가 **질문으로 안 읽혔다**(변환기가 손도 못 댔다).
    for _ in range(4):                       # `…입니다(주석).**` 처럼 겹쳐 붙기도 한다
        prev = core
        core = core.rstrip(".!").rstrip("*_`】]」’\"'").rstrip()
        core = _TRAIL_PAREN.sub("", core).rstrip()
        core = core.rstrip("*_`)】]」’\"'")
        if core == prev:
            break
    return core


def is_polite_ending(sentence):
    """합쇼체로 끝나는가. 순수 함수 — 테스트가 직접 부른다.

    ★ **`니다` 로 끝난다고 존댓말이 아니다** (2026-08-02, 회귀 테스트가 잡았다).
      `아니다` 가 `니다` 로 끝나서 **평어인데 존댓말로 통과**했다 — 감사와 변환기가 같은
      사각지대를 공유해, 그 문장들은 안 바뀐 채 감사도 0건이었다.
      합쇼체는 `습니다` 이거나 **앞 음절에 받침 ㅂ이 있는 `니다`**(입니다·합니다·아닙니다)다.
    """
    core = tone_core(sentence).rstrip("?")
    if core.endswith(_POLITE_TAIL) or core.endswith("습니다"):
        return True
    if core.endswith("니다") and len(core) >= 3:
        code = ord(core[-3]) - _HANGUL_BASE
        return 0 <= code < 11172 and code % 28 == _JONG_BIEUP
    return False
_HAS_HANGUL = re.compile(r"[가-힣]")
# 말투를 물을 자리 — **독자에게 말하는 산문**. 표제·명사구 목록·출처·수식은 대상이 아니다.
TONE_SKIP = ("/keywords", "/gradingKeywords", "/svg", "/latex", "/equations", "/id",
             "/source", "/sourceRef", "/topic", "/stage", "/difficulty", "/href",
             "/heading", "/title", "/symbol",
             # ★ `/appliesTo` 를 **뺐다** (2026-08-02, dynamics). 표제·명사구와 함께 묶어
             #   두었는데 실제로는 **문장**이고 뷰어가 공식 **위에 본문으로** 그린다
             #   (`renderDerivCard` 가 fmtText 로 렌더 — AGENTS 가 그렇게 못 박아 뒀다).
             #   내가 말없이 좁혀 놓은 자리라, 본문을 존댓말로 바꾼 뒤에도 여기만 평어로 남았다
             #   (같은 배치의 `/svg` 와 같은 실수). 명사구로 끝나는 값은 판정이 `None` 이라
             #   어차피 안 걸리므로, 다른 과목이 명사구로 써 둔 자리는 영향을 받지 않는다.
             # ★ 보강 2026-08-02 (기계재료 실측) — **문장이 아니라 라벨·위치표인 자리.**
             #   이 절의 문서(AGENTS 「말투」)는 이미 [사용자 발화 인용 생략] 고 적었는데
             #   구현에 네 자리가 빠져 있었다. 특히 `anchorText` 는 **본문의 한 조각을 그대로 적어
             #   위치를 가리키는 값**이라, 존댓말을 요구하면 *본문과 글자가 달라져 앵커가 깨진다* —
             #   즉 규격을 지킬수록 빌드가 깨지는 자리였다(실측: ch03 `fig-ceramic-types`).
             #   `name`(용어·수식 이름)·`variables`(기호 설명)·`expectedOutput`(결과 표기)도 같다.
             "/anchorText", "/name", "/variables", "/expectedOutput",
             # ★ 화면에 안 나가는 **제작 메모**는 뺀다. `rationale`·`teachingTips`·
             #   `supplementNotes`·`lintWaivers` 는 뷰어가 렌더하지 않고(`changeNote` 만
             #   검수 모드 툴팁으로 뜬다), AGENTS 가 [사용자 발화 인용 생략] 로 이미
             #   분류한 글이다. 독자가 못 읽는 글의 말투를 묻는 것은 이 자의 범위 밖이다.
             #
             # ★★ **되돌린 것 — `/answer`·`/solutionOutline`·`/explanation`·`/hint`·`/pitfalls`**
             #   (넣은 날 2026-08-02 열역학 · 되돌린 날 2026-08-02 사용자 결정).
             #
             #   그 다섯 줄은 [사용자 발화 인용 생략] 를 근거로 들어왔는데,
             #   **AGENTS.md 에 그런 문장이 없다.** 그 표(AGENTS 「말투 — 세 층을 가른다」)는
             #   정반대로 `이론 본문·풀이·유도 설명·함정·힌트·학습목표·이해도 체크` 를 **존댓말
             #   층**으로 열거하고, 「말투를 묻지 않는 자리」에도 그 다섯은 없다(명사구 종결·표제·
             #   채점 키워드·키워드 칩·출처·영문 지문뿐이다).
             #
             #   ★ 부류: **검사 완화(규칙 10 빨강)가 정본 문서를 잘못 인용해 들어왔다.**
             #     신고가 500건씩 쏟아지면 *자가 틀렸다*고 의심하는 것이 옳은 반사신경이지만
             #     (실제로 이 파일에는 그렇게 고친 오탐이 여럿 있다), **그 판정의 근거는 정본에서
             #     찾아 인용해야 한다.** 여기서는 근거가 없는 채로 다섯 필드가 전 과목에서
             #     영영 검사 밖이 됐고, 그 사실을 아무도 신고하지 않는다 — 검사를 끄면
             #     그 자리는 조용해질 뿐 옳아지지 않는다.
             #
             #   그래서 되돌린다. 데이터가 평어인 과목은 `fix_honorific --apply` 로 전환하고,
             #   전환 전까지는 `index.json` 의 `strictChapters.tone` 을 켜지 않으면 경고로 남는다
             #   (승격은 과목별이라 남의 빌드를 멈추지 않는다).
             #
             # ★ 여기 넣지 **않은** 것: `derivationSteps`·`notes`·`comprehensionChecks/prompt`·
             #   `learningObjectives/statement`·`chapterIntro/*` 도 독자가 읽는 글이다.
             #   (`/note` 가 아니라 `/pitfalls` 로 적어야 하는 이유: `/note` 는 `/notes` 까지 삼켜
             #    유도 노트를 조용히 면제한다. 부분 문자열 매칭이라 접미어를 좁게 잡아야 한다.)
             "/rationale", "/changeNote", "/teachingTips", "/supplementNotes", "/lintWaivers",
             # ★ `/noDiagramReason` (2026-08-05, C32) — **화면에 안 나간다.** `rationale`·
             #   `changeNote` 와 같은 층인 *제작 판정 기록*이라 리포 규칙대로 평어로 적는다.
             #   빠뜨렸더니 새 필드 하나가 곧바로 17건을 신고했다 — 새 필드를 만들 때
             #   *독자가 읽는가*를 먼저 정해 이 목록에 넣고 말고를 결정할 것.
             "/noDiagramReason",
             # ★ `/noTheoryDiagramReason` (2026-08-06, C37) — 위와 같은 층의 제작 판정 기록이다.
             "/noTheoryDiagramReason",
             # ★★ `/diagramWhy` (2026-08-06, C35) — **같은 부류가 하루 만에 재발했다.**
             #   바로 위 `/noDiagramReason` 이 [사용자 발화 인용 생략] 이라고 적어 두었는데, 새 필드를 만들면서
             #   그 결정을 하지 않았고 곧바로 12건이 신고됐다(말투 10 · 가운데점 2).
             #   ★ 그래도 **설계는 제대로 작동했다** — 모르는 필드를 독자 노출로 보는 것이
             #     기본값이라 빠뜨리면 **조용히 새지 않고 빌드가 즉시 막는다.** 이 기본값을
             #     화이트리스트로 뒤집으면 반대로 *독자가 읽는 새 필드가 검사 밖으로 새므로*
             #     지금 방향이 옳다. 그래서 여기 추가 검사를 달지 않는다 — 고칠 것은
             #     기본값이 아니라 **새 필드를 만들 때 이 목록을 먼저 보는 절차**다.
             #   `diagramWhy` 는 복습 카드가 끌어온 삽화가 그 장의 범위에 맞는 이유를 적는
             #   **제작 판정 기록**이고 뷰어가 렌더하지 않는다.
             "/diagramWhy",
             # ★ 2차 보강 2026-08-02 — 둘 다 **산문이 아닌 자리**라 남긴다.
             #   `/chapterTitle` — 표제다. 위 줄의 `/title` 은 **대문자 T 라 걸리지 않는다**
             #     (부분 문자열 매칭이라 `"/title" in "/chapterTitle"` 은 False). 표제에 존댓말을
             #     요구하면 '열역학은 무엇을 하는 과목인가' 가 위반이 된다.
             #   `/solutionTemplate` — 문풀의 **빈칸 뼈대**다. `➜` 로 이어지는 수식 줄과
             #     `___BLANK_N___` 로만 이루어져 있어 `/equations` 와 같은 부류이지 산문이 아니다.
             #     ★ 들어올 때 적힌 사유([사용자 발화 인용 생략])는 위와 같은
             #     잘못된 인용이라 지웠다 — **면제는 남기되 근거를 바꾼다.** 실제로 산문 문장이
             #     들어가는 자리는 `solutionOutline[].text` 이고 그쪽은 검사 대상이다.
             "/chapterTitle", "/solutionTemplate")


def sentence_spans(text):
    """문장 (시작, 끝) 범위 — 수식을 가려서 자르되 좌표는 **원문과 같다**. 순수 함수.

    ★ 자르는 자는 **하나여야 한다.** `tools/fix_honorific.py` 가 사본을 갖고 있다가,
      마크업 처리를 checks 쪽만 고쳐서 **감사는 신고하는데 변환기는 안 고치는** 상태가 됐다
      (실측 17문장). 이 리포가 여러 번 닫은 부류를 같은 배치 안에서 되풀이했다.
    """
    masked, out, at = mask_inline_math(text), [], 0
    for piece in _SENT_SPLIT.split(masked):
        idx = masked.find(piece, at)
        if idx < 0:
            continue
        at = idx + len(piece)
        if piece.strip():
            out.append((idx, at))
    return out


def is_directive_ending(core):
    """지시형 `~ㄹ 것` 인가. 순수 함수 — 테스트가 직접 부른다.

    `것` 앞 음절의 받침이 **ㄹ** 이면 관형사형 어미 `-ㄹ` 이 붙은 지시형이다.
    판정 근거와 오탐 여지는 위 `_JONG_RIEUL` 주석이 정본이다.
    """
    m = re.search(r"([가-힣])\s*것$", core)
    if not m:
        return False
    return (ord(m.group(1)) - _HANGUL_BASE) % 28 == _JONG_RIEUL


def is_plain_ending(core, raw=None):
    """평어로 끝나는가. 순수 함수 — 테스트가 직접 부른다(위 `_PLAIN_SHORT` 주석이 정본).

    `core` 는 꼬리를 벗긴 알맹이(`tone_core`), `raw` 는 벗기기 **전**의 조각이다.
    둘 다 필요한 이유: 종결어미는 알맹이에서 읽어야 하는데, 한 음절 종결어미인지
    같은 글자로 끝난 명사인지는 **원문에 문장부호가 있었는가**로 가른다.
    """
    if _PLAIN_DECL.search(core):
        return True
    if core.endswith(_PLAIN_ASK_TAIL):
        return True                        # 수사의문 — 물음표가 없어도 종결이다
    if is_directive_ending(core):
        return True                        # `~ㄹ 것` — 지시형 (위 `_JONG_RIEUL` 주석이 정본)
    if not _PLAIN_SHORT.search(core):
        return False
    return bool(_TERMINAL_PUNCT.search((raw if raw is not None else core).strip()))


# ★★ **종결어미는 조각의 「끝」에 있다 — 마지막 한글 어절이 아니다** (열린 날 2026-08-12).
#
# 두 과목이 같은 날 각각 신고했다. 증상은 달라 보이지만 뿌리가 하나다:
#   ⑴ 고체역학 `fig-zero-force` 캡션 — **`둘 다 0`** 이 **`둘 입니다 0`** 이 됐다.
#      `다` 는 종결어미가 아니라 **부사**이고, 그 뒤에 `0` 이 더 있으니 문장 끝도 아니다.
#   ⑵ 공학수학 표 — `| … 중근이다 | … |` 의 셀만 바뀌어 **한 표 안에서 말투가 갈렸다**
#      (형제 셀 `차가 정수가 아니다` 는 조각 중간이라 안 바뀐다).
#
# ★ 자와 처방이 갈린 자리다. 검사(`_PLAIN_DECL` = `다[.!?]?$`)는 **알맹이의 끝**에 닻을
#   내리므로 둘 다 평어로 안 읽는다 — 그래서 **C23 은 조용한데 도구만 고쳤다.** 도구 쪽이
#   `[가-힣]+[^가-힣]*$` 로 *마지막 한글 어절*을 찾으면서 뒤에 뭐가 남았는지를 안 봤다.
#   이 리포가 여러 번 닫은 부류인데(`tone_segments`·`declared_roles`), 이번엔 **닻의 위치**가
#   갈린 것이라 같은 함수를 부르고 있어도 안 막혔다.
#
# 판정: 어절 뒤에 남은 것이 문장부호·강조뿐이면 종결이고, **낱말 글자(숫자·영문·한글)나
# 표 칸막이 `|` 가 남아 있으면 그 어절은 문장의 끝이 아니다.**
_TAIL_WORD = re.compile(r"(?P<w>[가-힣]+)(?P<tail>[^가-힣]*)$")
_TAIL_NOT_ENDING = re.compile(r"[0-9A-Za-z|]")


def tail_word(core):
    """조각의 **끝에 있는** 한글 어절과 그 시작 위치. 끝이 아니면 (None, -1). 순수 함수.

    `tools/fix_honorific.py` 가 '어디를 바꿀지' 를 이 함수로 고른다 — 위 주석이 정본이다.
    """
    m = _TAIL_WORD.search(core or "")
    if not m or _TAIL_NOT_ENDING.search(m.group("tail")):
        return None, -1
    return m.group("w"), m.start("w")


def tone_segments(text):
    """말투를 물을 조각들의 (시작, 끝) — 좌표는 **원문과 같다**. 순수 함수.

    조각은 문장이되, **끝의 괄호주석은 그 자체로 한 조각**이다. 괄호 안도 독자가 읽는
    글이라, 말투가 섞이면 화면에 그대로 보인다 —
    `…곱합니다 (좌변은 곱의 미분으로 뭉친다)` (열린 날 2026-08-02, 실측 14곳).
    괄호를 통째로 벗기기만 하면 **그 안이 영영 검사 밖**이 되므로, 벗긴 것을 버리지 않고
    따로 잰다.
    """
    masked, out = mask_inline_math(text), []
    for start, end in sentence_spans(text):
        body = masked[start:end]
        lead = len(body) - len(body.lstrip())
        body = body.strip()
        at = start + lead
        if _is_quoted(body):
            continue                       # 인용 — 저자가 독자에게 하는 말이 아니다
        core = tone_core(body)
        if not core or not body.startswith(core):
            out.append((at, at + len(body)))
            continue
        out.append((at, at + len(core)))
        rest = body[len(core):]
        opened, closed = rest.find("("), rest.rfind(")")
        if 0 <= opened < closed:
            out.append((at + len(core) + opened + 1, at + len(core) + closed))
    return out


def sentence_endings(text):
    """(문장, 'polite'·'plain'·None) 목록. 순수 함수 — 테스트가 직접 부른다."""
    masked, out = mask_inline_math(text), []
    for start, end in tone_segments(text):
        s = re.sub(r"^[-*|>\s]+", "", masked[start:end].strip()).strip()
        if not s or not _HAS_HANGUL.search(s):
            continue
        # 존댓말·평어 판정은 **같은 알맹이**로 본다(`tone_core`). 예전에는 존댓말 쪽만
        # 꼬리를 벗겨서, 괄호주석이 붙은 문장은 평어인데도 '명사구 종결'로 빠져나갔다.
        if is_polite_ending(s):
            out.append((s, "polite"))
        elif _CONNECTIVE_END.search(tone_core(s)):
            out.append((s, None))          # 종결어미가 없는 조각 — 뒤에 절이 이어진다
        elif is_plain_ending(tone_core(s), s):
            out.append((s, "plain"))
        else:
            out.append((s, None))          # 명사구 종결 등 — 말투를 물을 수 없다
    return out


def tone_issues(node, trail="root"):
    """독자에게 말하는 글인데 평어로 끝난 문장. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for where, blob in iter_visible_texts(node, trail):
        if any(k in where for k in TONE_SKIP):
            continue
        for sent, verdict in sentence_endings(blob):
            if verdict == "plain":
                out.append(where + ": 독자에게 말하는 글은 `~입니다`·`~습니다` 체로 쓴다 — "
                           + repr(sent[-34:])
                           + " (`python tools/fix_honorific.py --apply` 가 바꿔 준다)")
    out.extend(figure_tone_issues(node))
    return out


def figure_tone_issues(ch):
    """삽화 캡션의 말투. 순수 함수 — 테스트가 직접 부른다.

    ★ **삽화도 독자가 읽는 화면이다** (2026-08-02). `TONE_SKIP` 이 `/svg` 를 통째로 빼는 것은
      **산문 규칙을 SVG 마크업에 그대로 적용할 수 없어서**이지 말투를 안 봐도 된다는 뜻이 아니다.
      실제로 본문을 전부 존댓말로 바꾼 뒤 삽화 캡션 **10건**만 평어로 남아 한 화면에 두 말투가
      섞였다. `<text>` 안쪽만 꺼내 보면 같은 자를 그대로 쓸 수 있다 —
      짧은 라벨(`위치`·`속도`·`s`)은 명사구라 애초에 판정 대상이 아니다.
      **바꾸는 것은 사람이 한다** — 캡션 길이가 바뀌면 라벨 여백·상하 균형이 함께 움직인다.

    ★ **`<text>` 하나는 문장이 아니라 줄 조각이다** (2026-08-02, 기계재료 실측에서 정정).
      두 줄로 흘린 한 문장의 앞줄(`항복강도가`)이 그대로 한 덩어리로 들어온다 —
      한 음절 종결어미와 명사를 가르는 자는 `_PLAIN_SHORT` 주석이 정본이고, **산문과 공유한다**.
    """
    out = []
    # `_iter_diagrams` 는 제너레이터라 **뒤쪽 컬렉션에서 터지면 앞에서 낸 것까지 사라진다** —
    # `list(...)` 를 통째로 try 로 감쌌다가 실제로 그렇게 됐다(회귀가 잡았다).
    # 하나씩 모아 두면 조각 dict 에서도 이미 찾은 삽화는 살아남는다.
    diagrams = []
    try:
        for dg in _iter_diagrams(ch):
            diagrams.append(dg)
    except (KeyError, TypeError, AttributeError):
        pass                # 조각 dict — 테스트가 부분 구조로 부를 수 있다
    for dg in diagrams:
        for item in _svg_texts(dg.get("svg", "")):
            # 삽화 **제목**(굵은 글자)은 본문 표제와 같은 부류라 말투를 묻지 않는다
            # (`TONE_SKIP` 의 `/heading`·`/title` 과 같은 이유). 실측: `무엇이 주어졌는가?` 는
            # 그 절 표제를 그대로 옮긴 삽화 제목이라, 캡션 규칙을 적용하면 표제와 어긋난다.
            if str(item.get("weight", "")).strip() in ("700", "bold"):
                continue
            for sent, verdict in sentence_endings(item["s"]):
                if verdict == "plain":
                    out.append(str(dg.get("id", "?"))
                               + ": 삽화 캡션도 `~입니다`·`~습니다` 체로 쓴다 — "
                               + repr(sent[-34:])
                               + " (글자 폭이 바뀌므로 고친 뒤 `audit_figure_balance.py` 로 볼 것)")
    return out


def plain_fraction_issues(ch):
    """평문으로 조판한 분수. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for where, blob in iter_visible_texts(ch):
        if any(k in where for k in MATH_NATIVE_KEYS):
            continue
        # `changeNote` 는 **검수 이력**이지 학습 콘텐츠가 아니다 (2026-08-01). 사용자 지적을
        # 그대로 인용해 두는 자리라 `'7/62 에 T(온도)…'` 같은 **쪽 번호**가 들어가는데,
        # 그것을 분수로 조판하면 인용문을 고치는 일이 된다.
        if where.endswith("changeNote"):
            continue
        if "/blanks[" in where and where.endswith("/answer"):
            continue
        outside = mask_inline_math(blob)
        # ★ 2026-07-31 — 삽화 검사(C9)와 **같은 자**를 여기에도 붙인다.
        #   아래 네 모양(괄호+연산자·아래첨자·미분·ρ분모)은 `P/ρ`·`V²/2` 를 못 본다:
        #   첨자도 괄호도 없어서 어느 모양에도 안 걸렸다. 실측 — 삽화 9건을 고친 뒤
        #   같은 부류가 산문에 22곳 그대로 남아 있었다(사용자: [사용자 발화 인용 생략]).
        hit = text_fraction_hit(outside) or next(
            (m.group(0).strip() for rx in FRACTION_SHAPES
             for m in [rx.search(outside)] if m), None)
        if hit:
            out.append(where + ": 분수를 평문으로 썼다 — " + repr(hit)
                       + " → \\(\\frac{F_1}{A_1}\\) 처럼 인라인 수식으로 조판할 것"
                       " (단위 `m/s²`는 대상이 아니다): " + repr(blob[:60]))
    return out


# ★ C38. **프라임 도함수를 인라인 수식 밖에 썼다** (열린 날 2026-08-08, R-53).
#
# 뷰어의 프라임 변환(ASCII `'` → `′`)은 **`\(…\)` 안에서만** 돈다. 그래서 산문에 `y''` 라고
# 적으면 화면에 **곧은 따옴표 두 개**가 그대로 나오고, 바로 옆 수식은 `y′′` 로 조판돼
# **한 화면에서 같은 도함수가 두 모양**이 된다. 분수 검사(위)와 정확히 같은 부류다 —
# [사용자 발화 인용 생략]
# 실측 2026-08-08(공학수학): 렌더 DOM 에 남은 ASCII 아포스트로피 중 이 부류가 11곳이었고,
# 전부 `explanation`·`answer`·`note`·`variables`·`assumptions` 였다. 같은 챕터의
# `explanation` 89곳은 이미 인라인 수식을 쓰고 있었으므로 **평문 쪽이 예외**였다.
#
# ★★ 자를 좁게 잡는 이유 — 아포스트로피는 **영어 소유격**(`Euler's`)과 **인용부호**
#   (`'우변이 0'`)에도 쓰인다. 실측 66곳 중 12곳이 그쪽이었다. 넓게 잡으면 그 12곳까지
#   고치라고 하게 되는데 그건 남의 말을 고쳐 쓰는 일이다(말투 검사가 인용을 면제하는 것과
#   같은 이유). 그래서 **실측 오탐 0인 세 신호만** 쓴다:
#   ⑴ 아포스트로피가 **둘 이상 연속** — 소유격·인용부호는 그렇게 되지 않는다
#   ⑵ **라틴 문자** 뒤 아포스트로피 + **곧바로 한글** — `y'만`·`f'로`.
#      닫는 인용부호는 한글이나 숫자 뒤에 오므로(`'우변이 0'이고`) 라틴 문자 조건에서 빠진다
#   ⑶ 아포스트로피 뒤에 **수학 연산자**(`= + * / ^`) — `y'=1+y²`.
#      `-` 는 넣지 않는다(줄표·붙임표와 구별이 안 된다)
#   한 필드에 셋 중 하나만 걸려도 **그 필드 전체가 사람 눈에 들어온다.** 그래서 신호에
#   안 잡힌 단일 프라임(`y, y' 자리에`)도 같은 손질에서 함께 고쳐진다 — 자의 목적은
#   전수 열거가 아니라 *고칠 자리로 데려가는 것*이다(실측 11곳 중 9곳이 이 셋으로 잡힌다).
_PRIME_RUN = re.compile(r"[A-Za-z0-9]''+")
_PRIME_HANGUL = re.compile(r"[A-Za-z]'+[가-힣]")
_PRIME_OP = re.compile(r"[A-Za-z]'+\s*[=+*/^]")
# ★ 신호 ⑵ 의 유일한 오탐을 여기서 막는다 — **라틴 낱말로 끝나는 한글 인용구**.
#   실측 첫 실행에서 나왔다: `앞 카드의 '행 rank = 열 rank'가 전제입니다` 의 닫는 따옴표는
#   `k` 뒤 · `가` 앞이라 ⑵ 와 서명이 똑같다. 여는 따옴표의 **앞 글자**가 둘을 가른다 —
#   인용은 공백·문두·여는 괄호 뒤에서 열리고, 도함수의 프라임은 **글자 바로 뒤**에 붙는다.
#   그래서 `y'와 z'` 처럼 프라임 둘이 인용구로 오인되는 일도 구조적으로 없다.
_QUOTED_PHRASE = re.compile(r"(?:^|(?<=[\s(\[「『]))'[^']{1,80}'")


def plain_prime_issues(ch):
    """평문으로 쓴 프라임 도함수. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for where, blob in iter_visible_texts(ch):
        if any(k in where for k in MATH_NATIVE_KEYS):
            continue
        if where.endswith("changeNote") or where.endswith("rationale"):
            continue
        outside = _QUOTED_PHRASE.sub(
            lambda m: " " * len(m.group(0)), mask_inline_math(blob))
        hit = next((m.group(0) for rx in (_PRIME_RUN, _PRIME_HANGUL, _PRIME_OP)
                    for m in [rx.search(outside)] if m), None)
        if hit:
            out.append(where + ": 프라임 도함수를 평문으로 썼다 — " + repr(hit)
                       + " → \\(y''\\) 처럼 인라인 수식으로 감쌀 것"
                       " (영어 소유격 `Euler's`·인용부호는 대상이 아니다): "
                       + repr(blob[:60]))
    return out


# ★ C26. **쉼표가 곱을 먹었다** (열린 날 2026-08-04, R-41 — 사용자 지적).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# 맞다. `m g 𝓋` 인데 인수 사이에 **날 쉼표**가 들어가 나열처럼 읽힌다. 원인은 이 리포에
# **이미 문서화된 함정**이다 — AGENTS 「알려진 함정」: [사용자 발화 인용 생략] `m\,g\,𝓋` 에서 백슬래시가 사라지면 정확히 `m, g, 𝓋` 가 된다.
# 뷰어도 이 사실을 안다(`renderMath` 에 `\,`→공백, `{,}`→진짜 쉼표 변환이 따로 있다).
#
# **왜 지금까지 안 걸렸나 — 쉼표는 유효한 문자다.** 어떤 LaTeX 문법 검사도 신고하지 않는다.
# R-33(`½`)·R-44(자릿수 쉼표)와 **같은 형태**다: *그 자리에 있으면 안 되는데 문법적으로는 멀쩡한 것.*
#
# ★★ 오탐과 진짜를 가르는 조건이 **두 개**다. 느슨하게 잡으면 전 챕터 274건이 뜨는데
#   대부분 정당한 서술이라, 그대로 두면 이 검사는 첫날부터 장식이 된다. 실측으로 좁힌 기준:
#
#   ⑴ **등호 바로 뒤여야 한다.** `= m, g, …` 처럼 등호 다음에 오는 나열은 「식 자체」다.
#      반대로 `v, u, h를 어디서 가져오나`·`버리는 항은 q, w, Δpe이고`·`ρ, g, h를 곱해` 는
#      조사가 붙은 **명사구**라 대상이 아니다.
#      ★ `A = x, B = y` 형태(결과 두 개를 쉼표로 나열)도 여기서 걸러진다 — 등호 뒤가
#        수치로 시작하기 때문이다. 처음엔 '뒤가 등호인 나열'도 잡았는데 그쪽은
#        **실측 신고의 대부분이 오탐**이었다(`Q = 327 kJ, W_b = 93.3 kJ` 같은 답 나열).
#   ⑵ **쉼표 뒤에 공백이 있어야 한다.** 첨자 나열은 `Q_net,in`·`c_v,av` 처럼 **붙여** 쓴다.
#      공백을 요구하면 그 부류가 통째로 빠진다 — 면제 목록을 따로 관리하지 않아도 된다.
#   ⑶ **양 끝이 낱말이면 안 된다.** 기호는 한두 글자다. 경계를 안 박으면 영문 지문의
#      `… = ΔE_system, derive the relation …` 에서 `de` 를 기호로 읽는다(실측 오탐).
#   ⑷ **인수가 셋 이상이거나, 둘 뒤에 쉼표가 더 있어야 한다.** 둘뿐인 나열은 곱이 아니라
#      대등 나열인 경우가 많다 — `kg·m/s²=N, N/m²=Pa` 가 실측 오탐이었다(단위 관계 두 개).
# ★★ 닷 붙은 기호는 **합자 코드포인트**다 — `ṁ`(U+1E41)·`Ẇ`(U+1E86) 는 결합문자 조합이
#   아니라 한 글자다. 처음엔 `m`+U+0307 로 보고 결합문자 클래스만 넣었는데, 그래서
#   **`ΔĖ_mech = ṁ, g, z` 가 통째로 검사 밖이었다** — 동력·유량이 걸린 자리가 정확히
#   이 부류인데 그것만 빠지는 자였다. 라틴 확장 영역을 통째로 넣어 둘 다 받는다.
#   글자 클래스는 **이스케이프로** 적는다 — 소스에 날 결합문자를 두면 앞 글자에 붙어
#   눈으로는 멀쩡해 보이는데 클래스가 깨진다.
_SYM_LETTER = r"A-Za-zÀ-ɏḀ-ỿͰ-Ͽ∆∇"
_COMMA_SYM = (r"(?<![" + _SYM_LETTER + r"0-9_])[" + _SYM_LETTER + r"]"
              r"[̀-ͯ]?[" + _SYM_LETTER + r"]?"
              r"[₀-₉⁰-⁹]*"
              r"(?:_\{[^{}]*\}|_[A-Za-z0-9]+)?(?![" + _SYM_LETTER + r"])")
_COMMA_RUN = (_COMMA_SYM + r"(?:,\s+" + _COMMA_SYM + r"){2,}"
              r"|" + _COMMA_SYM + r",\s+" + _COMMA_SYM + r"(?=,)")
_COMMA_PRODUCT = re.compile(r"(?<==)\s*(" + _COMMA_RUN + r")")


def bare_comma_product_issues(ch):
    """식 자리에 날 쉼표로 이어 붙인 곱. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for where, blob in iter_visible_texts(ch):
        if where.endswith("changeNote") or "sourceRef" in where:
            continue                       # 검수 이력·출처는 학습 콘텐츠가 아니다
        outside = mask_inline_math(blob)   # `{,}` 로 명시한 진짜 쉼표는 수식 안이라 가려진다
        for m in _COMMA_PRODUCT.finditer(outside):
            hit = m.group(1).strip()
            out.append(where + ": 쉼표가 곱을 먹었다 — " + repr(hit)
                       + " 는 나열이 아니라 곱이다. 인라인 수식에서 `\\,`(가는 공백)나 `\\cdot`"
                       " 로 쓸 것 — 날 쉼표는 `\\,` 의 백슬래시가 깎였을 때 나오는 형태다: "
                       + repr(blob[:60]))
    return out


# ★ C27. **계산 단계를 가로로 이어 붙였다** (열린 날 2026-08-02 → 2026-08-04 승격, R-21·R-50).
#
# 사용자 원문: [사용자 발화 인용 생략] — **재발**이다.
#
# ★★ 규칙도 감사도 **이미 있었는데 0건을 찍고 있었다.** 두 겹으로 빗나가 있었다:
#   ⑴ **순회 범위** — `audit_conventions` 의 [H] 는 `practice[].blanks[].answer` **만** 봤다.
#      정작 가로 병기가 사는 `solutionTemplate`·`derivationSteps`·`formulas[].latex` 는 안 봤다.
#   ⑵ **판정 패턴** — `;\quad` 과 '등호 4개'만 찾았다. 실제로 쓰인 **`\qquad` 가 목록에 없었다**
#      (열역학 전 챕터 30곳). '빠뜨렸다'가 아니라 **빠뜨려도 통과되는 구조**다(규칙 7-⑷).
#   그래서 감사에 두지 않고 **빌드 검사로 올린다** — 감사만 두면 또 묻힌다.
#
# ★ 판정 기준은 사용자가 확정해 주었다 (2026-08-02):
#   [사용자 발화 인용 생략]
#   → 가로 이음(`\qquad`·`;\quad`) **양옆에 관계 기호(`=`·`⇒`·`≈`)가 둘 다 있으면** 계산 단계다.
#     관계 기호가 없는 조건 나열 줄은 통과한다. 즉 `\qquad` 를 일괄 금지하지 않는다.
#
# 처방(R-50, 사용자 지시 [사용자 발화 인용 생략]): 풀이·유도는 한 문자열에 설명과 식을
#   섞지 말고 **`{"text": …, "equations": […]}`** 로 가른다. 그러면 줄을 나누려고 `\qquad` 를
#   쓸 이유 자체가 사라진다(공학수학이 이미 그 구조다 — `git show math:…` 로 실측).
#   `formulas[].latex` 는 **배열**이 곧 여러 줄이다(`latex_lines` 가 정본).
#
# ★★ **2026-08-13 — 「계산 단계」와 「좌우 비교」를 가른다** (사용자 판정).
#
#   [사용자 발화 인용 생략]
#
#   경위: ch04 `cp-cv-relation` 의 네 관계식이 세로로 쌓여 답답하다는 지적이 있었다.
#   2026-08-12 에 두 식씩 `\qquad` 로 묶어 봤더니 이 검사가 걸렸고, 헤드라인만 풀려고
#   자를 좁혔더니 **`latex` 에서 이 검사가 통째로 꺼졌다**(가로 병기의 표시가 `\qquad` 뿐이라
#   그것을 봐주면 남는 판정이 없다). 그래서 되돌리고 사람의 판정을 받은 자리다.
#
#   ★ **처방은 「새 필드」가 아니라 「이미 있는 선언」이다.** 뷰어 `renderMathLines` 는
#     `latex` 안의 **중첩 배열**을 `.fmath-cols`/`.fmath-col` (점선으로 갈린 두 열)로 이미
#     그리고 있었다(2026-07-28 신설, 공학수학 ch01 적분인자 카드가 실사용 중). 즉
#     **평평한 배열 = 여러 줄 · 중첩 배열 = 나란한 열** 이라는 선언이 데이터에 이미 있었고,
#     이 검사만 그 선언을 몰랐다. 새 필드를 만들면 같은 뜻이 두 형식으로 갈린다.
#
#   ★ **`\qquad` 로는 애초에 안 됐다.** renderMath 는 `\qquad` 를 공백 세 칸으로 바꾸는데
#     `.fmath` 에는 `white-space:pre` 가 없어 HTML 이 그 공백을 **한 칸으로 접는다** —
#     헤드라인에서 `\qquad` 는 좌우 분리로 보이지도 않는다. 중첩 배열은 격자라 접히지 않는다.
#
#   ★★ **선언이 면제가 되지 않게 한다** — 열을 나란히 둘 수 있다는 것이 *계산을 가로로
#     늘어놓아도 된다*는 뜻은 아니다. 그래서 중첩 행에는 `compare_row_issues` 가 붙어
#     ⑴ 열마다 관계 기호가 있는가 ⑵ 뒤 열이 관계 기호로 **시작**하지 않는가(앞 열을 그대로
#     이어받는 형태) ⑶ 두 열의 **좌변이 같지 않은가**(같은 양을 다시 적은 것 = 수치 대입)를 본다.
#     한 열 **안**의 `\qquad` 는 선언과 무관하게 그대로 걸린다.
#
#   ★ **기계가 여기까지밖에 못 간다는 것을 적어 둔다.** 기호가 겹치는지로는 「정의」와
#     「대입」을 못 가른다 — `k = c_p/c_v` 와 `P_g = P + 1` 은 스캐너에게 같은 모양이다.
#     앞의 것은 새 양을 정의하는 나란한 관계식이고 뒤의 것은 앞 결과를 받아 쓰는 계산 단계인데,
#     그 차이는 **뜻**에 있다. 그래서 그 판정은 저자의 선언(중첩 배열)이 하고, 검사는
#     **선언과 부딪히는 모양**만 잡는다. 이 리포의 `kind`·`class='dim'`·`\mathrm{}` 와 같은 자리다.
_HJOIN = re.compile(r"\\qquad|;\s*\\quad")
_RELATION = re.compile(r"=|⇒|\\Rightarrow|≈|\\approx")
# 조각이 관계 기호로 **시작**하면 앞 조각의 결과를 그대로 이어받은 것이다 (`= 140 - 620`).
_LEADING_RELATION = re.compile(r"^\s*(?:=|⇒|≈|\\Rightarrow|\\approx|\\to|\\Leftrightarrow)")

# ★ C30. **문장을 수식으로 끝내고 마침표를 붙인 자리** (열린 날 2026-08-04, R-49).
#
# 사용자: [사용자 발화 인용 생략]
#
# 왜 어색한가 — 아래첨자가 작은 글자라 뒤의 마침표가 **첨자에 딸린 기호처럼** 보이고,
# 수식 글꼴과 본문 글꼴이 달라 그 점이 수식의 일부인지 문장부호인지 흐려진다.
#
# ★ **처방은 마침표를 빼는 것이 아니라 「수식으로 문장을 끝내지 않는 것」이다.**
#   문장이면 낱말로 끝맺고(`… \(\Delta E\) 입니다.`), 나열·라벨이면 마침표를 아예 뺀다.
#
# ★★ **R-19(말투)와 같은 뿌리다.** 수식으로 끝나는 문장은 말투 검사에게 **명사구 종결**로 보여
#   [사용자 발화 인용 생략] 며 통과한다. 즉 **어색한 마침표는 「존댓말이 빠진
#   자리」의 신호**이기도 하다 — 이 검사가 그 사각지대를 메운다.
_MATH_END_PUNCT = re.compile(r"\\\)\s*[.]")
# 같은 식을 평문으로 쓴 자리도 같은 화면 결함이다. 등호 양쪽에 기호가 있고 마지막 기호가
# 아래첨자를 가진 경우만 좁게 받는다 — 일반 산문의 마침표와 URL은 이 모양을 갖지 않는다.
_PLAIN_MATH_END_PUNCT = re.compile(
    r"(?:^|[\s:])(?:[A-Za-zΑ-Ωα-ω∆Δ](?:_\{[^{}]+\}|_[A-Za-z0-9]+)?)"
    r"\s*=\s*(?:[A-Za-zΑ-Ωα-ω∆Δ](?:_\{[^{}]+\}|_[A-Za-z0-9]+)?)\s*[.]"
)


def math_sentence_end_issues(ch):
    """수식으로 문장을 끝내고 마침표를 붙인 자리. 수식·평문 표기를 함께 본다."""
    out = []
    for where, blob in iter_visible_texts(ch):
        if any(k in where for k in MATH_NATIVE_KEYS) or where.endswith("changeNote"):
            continue
        for m in _MATH_END_PUNCT.finditer(blob):
            out.append(where + ": 문장을 수식으로 끝내고 마침표를 붙였다 — 낱말로 끝맺거나"
                       " (나열·라벨이면) 마침표를 뺄 것: "
                       + repr(blob[max(0, m.start() - 30):m.end() + 6]))
        outside = mask_inline_math(blob)
        for m in _PLAIN_MATH_END_PUNCT.finditer(outside):
            out.append(where + ": 평문으로 쓴 식 뒤에 마침표를 붙였다 — 식을 `\\(…\\)`로"
                       " 묶고 낱말로 끝맺거나 (나열·라벨이면) 마침표를 뺄 것: "
                       + repr(outside[max(0, m.start() - 20):m.end() + 6]))
    return out


_SPLIT_INLINE_SUBSCRIPT = re.compile(
    r"(?P<math>\\\([^\r\n]*?)(?P<close>\\\))_(?P<sub>\{[^{}]+\}|[A-Za-zΑ-Ωα-ω]+)"
)


def merge_split_inline_subscripts(text):
    r"""`\(x\)_in`을 `\(x_{in}\)`으로 합친다. 검사와 고치기가 같은 패턴을 쓴다."""
    def repl(m):
        sub = m.group("sub")
        if not sub.startswith("{"):
            sub = "{" + sub + "}"
        return m.group("math") + "_" + sub + m.group("close")
    return _SPLIT_INLINE_SUBSCRIPT.sub(repl, str(text or ""))


def split_inline_subscript_issues(ch):
    r"""인라인 수식의 첨자를 수식 밖 평문에 붙인 자리 (`\(m\)_in`)."""
    out = []
    for where, blob in iter_visible_texts(ch):
        if where.endswith("changeNote") or "sourceRef" in where:
            continue
        for m in _SPLIT_INLINE_SUBSCRIPT.finditer(str(blob or "")):
            out.append(where + ": 인라인 수식의 첨자가 수식 밖에 갈렸다 — `\\(x_{…}\\)`"
                       " 한 수식으로 묶을 것: " + repr(m.group(0)))
    return out


def _lhs_key(part):
    """관계 기호 **앞**의 좌변을 비교용으로 정규화한다 (공백·그룹 중괄호를 지운다).

    `c_{p} = …` 와 `c_p = …` 는 화면에서 같은 글자라 같은 좌변으로 봐야 한다.
    """
    head = _RELATION.split(part, 1)[0]
    return re.sub(r"[\s{}]", "", head)


def compare_row_issues(cols):
    r"""「좌우 비교」로 선언한 한 행(중첩 배열)이 **정말 비교인가**. 위반 사유 목록을 돌려준다.

    판정선은 C38 이 쓰는 것과 같다 — *앞에서 얻은 식을 받아 다음 식을 만드는 자리가 있는가*.
    다만 그 판정 전체를 기계가 할 수는 없으므로(위 C27 주석 마지막 항), 여기서는 **뜻을 몰라도
    확실한 세 모양**만 잡는다. 셋 다 「나란한 두 관계식」으로는 나올 수 없는 형태다.
    """
    reasons = []
    if len(cols) > 2:
        reasons.append("열이 %d 개다 — 뷰어 `.fmath-cols` 는 2열 격자라 셋째 열부터는"
                       " 점선 없이 아래로 접힌다" % len(cols))
    if any(not _RELATION.search(c) for c in cols):
        reasons.append("관계 기호가 없는 열이 있다(나란한 두 관계식이 아니다)")
    if any(_LEADING_RELATION.search(c) for c in cols[1:]):
        reasons.append("뒤 열이 관계 기호로 시작한다 — 앞 열의 결과를 그대로 이어받는 계산 단계다")
    keys = [_lhs_key(c) for c in cols if _RELATION.search(c)]
    dup = next((k for k in keys if k and keys.count(k) > 1), None)
    if dup:
        reasons.append("두 열의 좌변이 같다(같은 양을 다시 적은 것 — 수치 대입·재정리다): "
                       + repr(dup))
    return reasons


def horizontal_step_issues(ch):
    """계산 단계를 한 줄에 가로로 이어 붙인 자리. 순수 함수 — 테스트가 직접 부른다."""
    out = []

    def look(where, text):
        for line in str(text or "").split("\n"):
            parts = _HJOIN.split(line)
            if len(parts) < 2:
                continue
            # 관계 기호를 **둘 이상의 조각**이 갖고 있을 때만 계산 단계로 본다.
            if sum(1 for p in parts if _RELATION.search(p)) < 2:
                continue
            out.append(where + ": 계산 단계를 가로로 이어 붙였다 — 세로로 나눌 것"
                       " (풀이·유도는 `{\"text\": …, \"equations\": […]}`,"
                       " 공식은 `latex` 배열): " + repr(line[:70]))

    for formula in (ch.get("derivation") or {}).get("formulas") or []:
        fid = "formula " + str(formula.get("id"))
        for r, row in enumerate(latex_rows(formula.get("latex")), 1):
            # ★ 한 열 **안**의 가로 병기는 선언과 무관하게 그대로 걸린다 — 선언이 면제하는
            #   것은 *열 사이*뿐이다. 이 줄이 풀리면 `latex` 에서 C27 이 통째로 꺼진다
            #   (2026-08-12 에 실제로 그렇게 됐고 기존 회귀가 곧바로 깨져 드러났다).
            for col in row:
                look(fid + "/latex", col)
            if len(row) < 2:
                continue                      # 평평한 배열 = 여러 줄. 선언이 아니다
            for reason in compare_row_issues(row):
                out.append(fid + "/latex[행 " + str(r) + "]: 「좌우 비교」로 선언했는데(중첩"
                           " 배열) " + reason + " — 계산 단계는 세로로 나눌 것: "
                           + repr(" ∥ ".join(row)[:70]))
        for i, step in enumerate(formula.get("derivationSteps") or [], 1):
            look(fid + "/step[" + str(i) + "]", step_prose(step))
    for prob in ch.get("problems") or []:
        for i, step in enumerate(prob.get("solutionOutline") or [], 1):
            look("problem " + str(prob.get("id")) + "/solutionOutline[" + str(i) + "]",
                 step_prose(step))
    for pr in ch.get("practice") or []:
        look("practice " + str(pr.get("id")) + "/solutionTemplate", pr.get("solutionTemplate"))
        for b in pr.get("blanks") or []:
            look("practice " + str(pr.get("id")) + "/blanks[" + str(b.get("id")) + "]",
                 b.get("answer"))
    return out


# ★ C1. SI 접두어를 쓸 수 있는데 기본단위로 풀어 씀 (열린 날 2026-07-30 — 사용자 3회째 부류).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# **왜 두 번이나 놓쳤나 — 부류를 겉모습으로 정의했다.** 2026-07-30 에 같은 지적을 받고
# `4.12 × 10³ N → 4.12 kN` 5건을 고쳤는데, 그때 검색한 것은 **`× 10³` 라는 표기**였다.
# 같은 날 ch02~05 소급에서도 다시 `× 10[⁰-⁹⁻]` 로 grep 하고 "해당 없음"이라고 보고했다.
# `1511 N` 처럼 **그냥 큰 수로 적힌 것은 두 번 다 검색 밖**이었다 —
# 부류는 "표기"가 아니라 **"값이 10³ 이상인데 접두어가 없다"** 는 *조건*이었다.
# 조건을 검사로 옮기면 겉모습이 무엇이든 걸린다. 그게 이 함수가 존재하는 이유다.
#
# 통과시키는 것:
#   ⑴ 계산 도중의 값이 **같은 줄에서 접두어로 닫히는** 경우 — `222,200 J = 222 kJ`.
#      곱셈 재료까지 접두어로 바꾸면 검산이 어려워지므로 '끝을 접두어로 닫는' 형태는 정상이다.
#   ⑵ 관례가 기본단위인 것 — `1000 kg/m³` 를 `1 Mg/m³` 로 쓰지 않는다(kg 은 아래 목록에 없다).
SI_PREFIXABLE = ("N", "Pa", "J", "W")
_SI_BIG = re.compile(r"(?<![\d.])(?:\d{1,3}(?:,\d{3})+|\d{4,})(?:\.\d+)?\s*("
                     + "|".join(SI_PREFIXABLE) + r")\b")
# '= … k<단위>' 또는 '≈ … k<단위>' 가 뒤따르면 환산으로 닫은 것 — 통과.
# ★ `≈` 를 빠뜨렸다가 첫 실행에서 오탐이 절반이었다(2026-07-30): 이 리포의 풀이는
#   `= 2452.5 N ≈ 2.45 kN` 처럼 **근사 기호로 닫는다**. 등호만 보면 정상 서술을 결함으로 신고한다.
# 괄호 병기 `(8.44 kN/m³)` 는 닫음이 **아니다** — 그건 두 표기를 나란히 둔 것이라
# "어느 쪽이 정본인가"가 여전히 갈린다(W-47 이 그 지적이었다).
_SI_CLOSED = re.compile(r"[=≈→]\s*[^=≈→]{0,24}?[kMG](" + "|".join(SI_PREFIXABLE) + r")\b")


def si_prefix_issues(ch):
    """접두어를 안 쓴 큰 값. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for where, blob in iter_visible_texts(ch):
        for m in _SI_BIG.finditer(blob):
            tail = blob[m.end():m.end() + 40]
            if _SI_CLOSED.search(tail):
                continue                  # `= 222 kJ` 처럼 접두어로 닫았다
            out.append(where + ": SI 접두어를 안 썼다 — " + repr(m.group(0).strip())
                       + " → `1511 N`은 `1.511 kN`, `8440 N/m³`은 `8.44 kN/m³`."
                       " 계산 도중 값이면 그 줄 끝을 `= … kJ`처럼 접두어로 닫을 것: "
                       + repr(blob[max(0, m.start() - 20):m.end() + 20]))
    return out


# ★ C2. 물음의 단위와 답의 단위가 다르다 (열린 날 2026-07-30).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# **C1 과 짝이다.** 접두어 규칙을 답에만 적용하면 이 결함을 **대량으로 만들어낸다** —
# 물음은 `[N]` 인데 답은 `kN` 이 되기 때문이다. 그래서 두 검사를 같이 넣는다.
_BRACKET_UNIT = re.compile(r"\[([A-Za-z°µ][^\]]{0,12})\]")


def prompt_answer_unit_mismatch(problem):
    """문제가 물은 단위와 답의 단위가 어긋나면 사유 목록. 순수 함수 — 테스트가 부른다."""
    prompt = str(problem.get("prompt") or "")
    answer = str(problem.get("answer") or "") + " " + str(problem.get("expectedOutput") or "")
    if not prompt or not answer.strip():
        return []
    out = []
    for m in _BRACKET_UNIT.finditer(prompt):
        unit = m.group(1).strip()
        if not unit or unit[0] not in "NPJWkmg°µ":
            continue
        # ★ 뒤에 `/` 가 오면 **다른 단위**다 — `[N]` 을 찾는데 `8440 N/m³` 의 N 이 걸리면
        #   물음(`[N]`)과 답(`4.22 kN`)의 어긋남을 **놓친다**(2026-07-30 첫 실행에서 실제로 0건이 나왔다).
        whole = re.compile(r"(?<![A-Za-z])" + re.escape(unit) + r"(?![A-Za-z/])")
        if whole.search(answer):
            continue
        for pre in ("k", "M", "G", "m"):
            if re.search(r"(?<![A-Za-z])" + re.escape(pre + unit) + r"(?![A-Za-z/])", answer):
                out.append("물음은 '[" + unit + "]'인데 답은 '" + pre + unit + "'로 쓴다 — "
                           "둘 중 하나로 통일할 것(접두어 규칙을 답에만 적용하면 이 어긋남이 생긴다)")
                break
    return out


# ★ C15. 문항 지문의 언어가 과목이 선언한 것과 다르다 (열린 날 2026-08-01, 사용자 지적).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# **무엇이 새어나갔나 — 합의는 있었는데 규격 문서에 적힌 곳이 없었다.**
# 열역학 문항이 영문이라는 사실은 `docs/feedback-ledger.md`([사용자 발화 인용 생략])와
# `docs/portfolio-notes.md`([사용자 발화 인용 생략])에 **곁가지로만** 남아 있었다.
# 그래서 새 과목이 한글로 만들어도 빌드도 감사도 아무 말을 하지 않았고,
# 고체역학 ch01 8문항이 통째로 한글로 나갔다. 규칙 7⑷가 말하는
# [사용자 발화 인용 생략] 가 원인이지 사람의 부주의가 아니다.
#
# **판정은 지문에만 건다.** 풀이·해설·힌트·이해도 체크는 한국어가 정본이다 —
# 지문을 원서 언어로 두는 이유는 *결국 풀어야 할 교재 연습문제가 그 언어*라서이지
# 자료 전체를 영문화하려는 것이 아니다.
#
# **과목별 사실이므로 공통 코드가 알면 안 된다**(AGENTS 「공통 도구에 과목별 사실을 박지 않는다」).
# 선언은 `data/<과목>/index.json` 의 `promptLanguage` 가 갖는다. 폴백 기본값도 두지 않는다 —
# 기본값을 두면 선언하지 않은 과목이 *선언한 것처럼* 조용히 지나간다(그 함정의 선례가
# `audit_problem_originality.PDF_FOR` 다). 미선언은 **경고**로 남긴다: 여기서 error 로 박으면
# 아직 선언 안 한 다른 과목의 빌드를 merge 하는 순간 세운다.
_HANGUL_SYLLABLE = re.compile(r"[가-힣]")
PROMPT_LANGUAGES = ("en", "ko")


def prompt_language_issues(ch, declared):
    """(errors, warnings) — 지문 언어 판정. 순수 함수(테스트가 직접 부른다).

    ★ 항목별 `promptLanguage` 오버라이드 (신설 2026-09-03). 과목 전체는 원서 언어를 따르지만
    (`index.json`의 선언), **참/거짓(O/X) 판정형처럼 교재 문항이 아니라 저자가 직접 짓는
    문항**은 그 과목 학생이 실제로 마주치는 말(한국어 수업이면 한국어)로 적어야 뜻이 산다 —
    영어로 번역하면 «절이 여럿 섞인 문장에서 어디가 틀렸는지 잡는» 문제의 난이도 축 자체가
    바뀐다(번역 난이도가 섞여 버린다). 문항이 `"promptLanguage": "ko"|"en"` 을 스스로 선언하면
    과목 선언보다 그 값을 우선한다 — 선언이 없으면 지금까지처럼 과목 선언을 따른다.
    """
    errors, warnings = [], []
    if declared is None:
        warnings.append(
            "문항 지문 언어 미선언 — data/<과목>/index.json 에 \"promptLanguage\" 를 넣을 것"
            " ('en' = 원서가 영문이라 지문도 영문 · 'ko' = 보유 교재가 한국어 역서)."
            " 선언이 없으면 챕터마다 언어가 갈린다")
        return errors, warnings
    if declared not in PROMPT_LANGUAGES:
        errors.append("index.json promptLanguage 값이 " + repr(list(PROMPT_LANGUAGES))
                      + " 밖이다 — " + repr(declared))
        return errors, warnings
    for key in PROMPT_COLLECTIONS:
        for item in (ch.get(key) or []):
            pid = str(item.get("id") or "?")
            want = item.get("promptLanguage") or declared
            if want not in PROMPT_LANGUAGES:
                errors.append(pid + ": promptLanguage 값이 " + repr(list(PROMPT_LANGUAGES))
                              + " 밖이다 — " + repr(want))
                continue
            # 인라인 수식 안은 보지 않는다 — 거기엔 한글이 없고, 마스킹은 다른 산문 검사와 같은 처리다.
            text = mask_inline_math(str(item.get("prompt") or ""))
            ko = len(_HANGUL_SYLLABLE.findall(text))
            if want == "en" and ko:
                errors.append(
                    pid + ": 지문에 한글 " + str(ko) + "자 — "
                    + ("이 문항의 promptLanguage 는 'en' 이다" if item.get("promptLanguage")
                       else "이 과목의 지문 언어는 'en' 이다")
                    + " (풀이·해설·힌트·이해도 체크는 한국어가 맞다. 지문만 원서 언어로 쓴다)")
            elif want == "ko" and text.strip() and not ko:
                errors.append(
                    pid + ": 지문에 한글이 없다 — "
                    + ("이 문항의 promptLanguage 는 'ko' 이다" if item.get("promptLanguage")
                       else "이 과목의 지문 언어는 'ko' 이다"))
    return errors, warnings


def declared_prompt_language(ch_path):
    """이 챕터가 속한 과목의 지문 언어 선언. 없으면 None(공통 코드는 과목 이름을 모른다)."""
    idx = os.path.join(os.path.dirname(os.path.abspath(ch_path)), "index.json")
    try:
        with open(idx, encoding="utf-8") as fh:
            return json.load(fh).get("promptLanguage")
    except (OSError, ValueError):
        return None


# ★ C3. 답 소절 수와 삽화 답 슬롯 수가 다르다 (열린 날 2026-07-30).
#
# 사용자 원문: [사용자 발화 인용 생략] — ch01 실측 결과 답이 2개 이상인 문항 15개 중 **11개**가 그랬다.
#
# 삽화에 답 슬롯을 둔 것은 [사용자 발화 인용 생략] 는 약속이다. 일부만 있으면 나머지 답이
# 어디서 나오는지 알 수 없고, A안(조건 가림)과 겹치면 더 나빠진다.
# **서술형 소절은 세지 않는다** — [사용자 발화 인용 생략] 를 슬롯에 넣으면
# 삽화가 글판이 된다. 그래서 '숫자를 포함한 소절'만 센다.
_ANSWER_PART = re.compile(r"\((?:[a-z]|[가-힣])\)")
_SLOT_ID = re.compile(r"id='(slot-[^']+)'")


def numeric_answer_parts(answer):
    """답 문자열에서 **숫자를 포함한** 소절 수. 순수 함수 — 테스트가 부른다."""
    text = str(answer or "")
    if not text.strip():
        return 0
    parts = _ANSWER_PART.split(text)
    parts = [p for p in parts if p.strip()]
    if not parts:
        return 0
    return sum(1 for p in parts if re.search(r"\d", p))


def answer_slot_count_mismatch(problem):
    """수치 답 소절 수 > 삽화 슬롯 수이면 사유. 순수 함수 — 테스트가 부른다."""
    slots = set()
    for dg in problem.get("diagrams") or []:
        slots.update(_SLOT_ID.findall(str(dg.get("svg") or "")))
    if not slots:
        return []                          # 답 슬롯을 아예 안 쓰는 삽화는 이 규격의 대상이 아니다
    need = numeric_answer_parts(problem.get("answer"))
    if need <= len(slots):
        return []
    return ["수치 답 소절이 " + str(need) + "개인데 삽화 답 슬롯은 " + str(len(slots))
            + "개다 — 나머지 답이 어디서 나오는지 독자가 알 수 없다. "
            "수치 답은 전부 슬롯을 갖는다(서술형 소절은 세지 않는다): " + repr(sorted(slots))]


# ★ C4. 가림(A안)이 캡션으로 샌다 (열린 날 2026-07-30).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# `fig-p08-bourdon-stack` 은 `+ 145 kPa` 라벨에는 `data-reveal='1'` 을 붙였는데
# **바로 아래 캡션**에는 안 붙였다. 버튼을 안 눌러도 캡션이 83.5·145 를 다 알려준다.
# 내 실수의 유형이 분명하다 — A안을 **'라벨'에만** 적용하고 **설명 캡션을 안 봤다.**
# 라벨만 훑는 것은 규칙 7 이 금지한 '인스턴스만 고치기'와 같은 구조다.
#
# 기계로 판정할 수 있는 형태: **같은 숫자가 두 곳에 있는데 한쪽만 가려졌다.**
# 답 슬롯은 원본에 `?` 로 있으므로 여기 걸리지 않는다(런타임에 채워진다).
_SVG_TEXT_EL = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)
_SVG_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def iter_chapter_diagrams(node, trail="root"):
    """챕터 안의 모든 diagram 을 (위치, dict) 로 흘린다 — 컬렉션을 열거하지 않는다."""
    if isinstance(node, dict):
        for dg in node.get("diagrams") or []:
            if isinstance(dg, dict):
                yield str(dg.get("id") or trail), dg
        for key, value in node.items():
            if key != "diagrams":
                yield from iter_chapter_diagrams(value, trail + "/" + str(key))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from iter_chapter_diagrams(value, trail + "[" + str(i) + "]")


# ★ C13. **답 슬롯의 값이 같은 삽화에 이미 적혀 있다** (열린 날 2026-08-01, 사용자 지적).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# **왜 C4 가 못 봤나 — C4 는 `revealMode` 가 붙은 삽화만 본다.** q07 은 `figureMode: hint`라
# 그 검사가 **아예 돌지 않는다.** 즉 '가림'을 쓰는 삽화만 감시하고, 답 슬롯을 쓰는 삽화는
# 아무도 안 봤다. 답을 `?` 로 감춰 놓고 **그 값을 옆에 적어 두면** 감춘 의미가 없다.
#
# 판정 — 슬롯 값의 **수치 부분**이 삽화의 다른 글자에 있고, **문제문에는 없으면** 누수다.
#   · 문제문에 있는 수치는 *주어진 조건*이라 삽화에 적혀도 된다(q07 왼쪽의 `ΔT = 25`).
#   · 문제문에 없는데 삽화에 있으면 그건 **푼 결과**다(q07 오른쪽의 `45`).
# ★ C14. 답은 소문제 (a)(b)로 갈라 놓고 **풀이는 평면 나열**인 자리 (열린 날 2026-08-01).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# 뷰어는 `(a)` 로 시작하는 풀이 단계를 만나면 소문제 그룹으로 묶는다. 그런데 **데이터에 그 키가
# 없으면** 갈라 줄 근거가 없어 예전처럼 1~N 평면 나열로 남는다. 답에는 (a)(b)가 있는데
# 풀이에만 없으면 **읽는 사람이 어느 단계가 어느 소문제인지 세어 맞춰야 한다.**
# ★ 2026-08-01(같은 날 2차) — **이 검사와 뷰어가 둘 다 문자열 단계만 봤다.**
#   풀이 단계는 두 형태다: 문자열, 그리고 `{text, equations}`. 식이 붙는 단계는 후자인데
#   `renderOutline` 도 이 검사도 **객체 단계에서는 키를 찾지 않았다.** 그래서
#   ⑴ 화면은 예전처럼 평면 나열로 남고 ⑵ 검사는 `isinstance(s, str)` 필터에서 0건을 냈다.
#   실측: ch01 q06 은 `**(a)**` 를 본문에 적어 두고도 그룹이 안 갈렸고 검사도 조용했다.
#   즉 **고친 줄 알았던 부류가 절반만 닫혀 있었다** — 순회 범위 사고(규칙 11)의 재판이다.
#   `**(a)**` 형태를 함께 받는 이유: 저자가 소문제 표시를 굵게 쓰는 것이 이미 관행이고,
#   그것을 위반으로 몰면 데이터 표기를 바꾸는 일이 되지 판정이 나아지지 않는다.
# ★ 로마숫자 키도 받는다 (2026-08-07) — 정본은 뷰어의 `SUBQ_KEY`·`SUBQ_SPLIT` 이고
#   두 벌이 갈리면 *화면은 가르는데 검사는 못 세는* 상태가 된다(그 반대도 마찬가지).
#   경위는 뷰어 쪽 주석에 있다: 지문이 `(i)`·`(ii)` 인 문항은 답도 그렇게 적히는데
#   가르는 자가 `[a-e]` 만 알아서 한 줄로 뭉쳐 나왔다.
_SUBQ_KEY_HEAD = re.compile(r"^\*{0,2}\((?:[a-e]|iv|i{1,3}|v|종합|공통|정리)\)")
_SUBQ_KEY_ANY = re.compile(r"\((?:[a-e]|iv|i{1,3}|v)\)")


def step_head_text(step):
    """풀이 단계의 첫 글자열 — 문자열이면 그 자신, {text, equations}면 text. 순수 함수."""
    if isinstance(step, str):
        return step
    if isinstance(step, dict):
        return str(step.get("text") or "")
    return ""


def outline_subq_key_issues(ch):
    """답은 소문제로 갈렸는데 풀이에 키가 없는 자리. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for prob in (ch.get("problems") or []):
        answer = str(prob.get("answer") or "")
        steps = [s for s in map(step_head_text, prob.get("solutionOutline") or []) if s]
        # 답이 (a)·(b) 둘 이상으로 갈린 문제만 대상 — 소문제가 없으면 나눌 것도 없다.
        if len(_SUBQ_KEY_ANY.findall(answer)) < 2 or len(steps) < 3:
            continue
        if any(_SUBQ_KEY_HEAD.match(s) for s in steps):
            continue
        out.append(str(prob.get("id") or "?")
                   + ": 답은 소문제로 갈렸는데 **풀이에는 소문제 키가 없다** — "
                   "풀이 단계 앞에 `(a)`·`(b)`(소문제에 안 속하는 마무리는 `(종합)`)를 붙이면 "
                   "뷰어가 그룹으로 갈라 준다. 없으면 " + str(len(steps)) + "단계가 평면 나열로 남는다")
    return out


def _slot_num_variants(value):
    """슬롯 값에서 뽑은 수치와 **그 표기 변형**. (순수 함수)

    ★ 이것이 없으면 검사가 실제 결함을 못 잡는다 — 슬롯 값은 `45.0`(유효숫자 표기)인데
      삽화에는 `45` 로 적혀 있어 **문자열이 안 맞는다.** q07 이 정확히 그 형태였고,
      변형을 넣기 전 이 검사는 전 챕터 '0건'을 냈다. **양성 대조가 그 가짜 0건을 잡았다**
      (AGENTS 규칙 11 — 양성 대조 없는 0건은 근거가 아니다).
    """
    out = set()
    for num in _SVG_NUM.findall(value):
        out.add(num)
        plain = num.replace(",", "")
        try:
            f = float(plain)
        except ValueError:
            continue
        if f == int(f):
            out.add(str(int(f)))          # 45.0 → 45
    return out


def answer_slot_leak_issues(ch):
    """답 슬롯 값이 같은 삽화에 그대로 적혀 있는 자리. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for prob in (ch.get("problems") or []):
        slots = prob.get("figureSlots") or []
        if not slots:
            continue
        prompt_nums = set(_SVG_NUM.findall(str(prob.get("prompt") or "")))
        for dg in (prob.get("diagrams") or []):
            svg = str(dg.get("svg") or "")
            # 슬롯 자체(`<tspan id='slot-…'>?</tspan>`)는 지운 뒤에 본다.
            body = re.sub(r"<tspan\b[^>]*\bid='[^']*'[^>]*>.*?</tspan>", "", svg, flags=re.S)
            shown = " ".join(re.sub(r"<[^>]+>", " ", m.group(2))
                             for m in _SVG_TEXT_EL.finditer(body))
            for slot in slots:
                for num in _slot_num_variants(str(slot.get("value") or "")):
                    if len(num.replace(",", "").replace(".", "")) < 2:
                        continue          # 한 자리 수는 첨자·순번과 섞인다
                    if num in prompt_nums:
                        continue          # 문제문이 준 조건이면 삽화에 적혀도 된다
                    if re.search(r"(?<![0-9.])" + re.escape(num) + r"(?![0-9])", shown):
                        out.append(str(dg.get("id") or prob.get("id"))
                                   + ": 답 슬롯 값 " + repr(num) + " 가 **삽화에 이미 적혀 있다** — "
                                   "슬롯으로 감춘 값을 옆에 적어 두면 감춘 의미가 없다"
                                   " (문제문에 없는 수치 = 푼 결과다): " + repr(slot.get("value")))
    return out


# ★ C16. **'주어진 조건값'을 나타내는 신호가 둘이었다** (열린 날 2026-08-01, 사용자 지적).
# (번호 주의: C15 는 main 에서 '지문 언어'가 가져갔다 — merge 로 겹친 것을 여기서 비켰다.)
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# 규칙은 `data-reveal='1'`(가림 대상 = 주어진 조건) + `font-weight='700'` 둘을 **손으로 맞추는**
# 것이었다. 손으로 맞추는 규칙은 반드시 갈라진다 — 실측 48건 중 **20건이 어긋나** 있었다.
# 사용자가 든 사례(`m = 900 kg`)는 그중 하나일 뿐이고, 인스턴스를 고쳐 봐야 나머지 19건이 남는다.
#
# 사용자 판정(2026-08-01)으로 표시를 **칩**(뷰어 CSS, `data-reveal` 하나에서 자동으로 나온다)으로
# 옮겼다. 그러면 이 검사는 *옛 신호가 되살아나는 것*만 막으면 된다 — 굵기가 다시 붙으면
# 두 신호가 또 생기고, 그 순간 "기준을 모르겠다"가 재발한다.
def reveal_bold_issues(ch):
    """가림 대상(`data-reveal`)에 굵기가 남아 있는 자리. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for fig_id, dg in iter_chapter_diagrams(ch):
        for m in _SVG_TEXT_EL.finditer(str(dg.get("svg") or "")):
            attrs = m.group(1)
            if "data-reveal" in attrs and "font-weight='700'" in attrs:
                out.append(fig_id + ": 주어진 조건값에 **굵기와 칩 두 신호**가 겹쳤다 — "
                           "굵기는 *중요하다*는 뜻이라 *주어진 값이다*라는 분류에 쓰면 "
                           "구해야 할 값과 위계가 뒤집힌다. `font-weight='700'` 을 뺄 것"
                           " (칩은 뷰어가 data-reveal 에서 자동으로 그린다): "
                           + repr(re.sub(r"<[^>]+>", "", m.group(2))[:40]))
    return out


def reveal_leak_issues(ch):
    """가린 수치가 안 가려진 글자에 다시 나오는 자리. 순수 함수 — 테스트가 부른다."""
    out = []
    for fig_id, dg in iter_chapter_diagrams(ch):
        if not dg.get("revealMode"):
            continue
        svg = str(dg.get("svg") or "")
        hidden, shown = set(), []
        for m in _SVG_TEXT_EL.finditer(svg):
            inner = re.sub(r"<[^>]+>", "", m.group(2))
            if "data-reveal" in m.group(1):
                hidden.update(_SVG_NUM.findall(inner))
            else:
                shown.append(inner)
        for num in sorted(hidden):
            # 한 자리 수는 첨자·순번(h₁·상태 1)일 수 있어 오탐이 난다. 두 자리부터 본다.
            if len(num.replace(",", "").replace(".", "")) < 2:
                continue
            for text in shown:
                if num in text:
                    out.append(fig_id + ": 가린 수치 " + repr(num) + " 가 **안 가려진 글자**에 그대로 있다 — "
                               "가림이 새고 있다(A안은 라벨만이 아니라 **설명 캡션까지** 덮어야 한다): "
                               + repr(text.strip()[:44]))
                    break
    return out


# ★ C5. 치수보조선이 관·기둥의 **중심선**에서 시작한다 (열린 날 2026-07-30, 사용자 재지적).
#
# 사용자 원문: [사용자 발화 인용 생략]
# 그 전에 이미: [사용자 발화 인용 생략]
#
# **왜 규칙을 적고도 또 났나 — 검사가 없었다.** AGENTS 「치수선의 끝점은 재는 면의 *외형선*」은
# 2026-07-30 에 신설됐지만 그것을 보는 기계가 하나도 없었다.
# `audit_figure_balance` 의 「화살촉 끝점」은 *화살촉* 이 기준선에 닿는지만 보고,
# **보조선의 *시작점*이 중심선인지 외형선인지는 아무도 안 봤다.**
# 그래서 규칙은 문서에만 있고 데이터는 그대로였다 — 빠뜨려도 통과되는 구조였다.
#
# 판정: 치수 그룹 안의 **가는 선**(≤1.5) 끝점이 **굵은 stroke**(≥6 = 관·기둥)의 중심선 위에 있으면 위반.
# 외형선(중심 ± 굵기/2)에서 시작한 것은 통과한다 — 중심선만 콕 집어 잡으므로 오탐이 없다.
#
# ★ 치수 그룹을 찾는 자는 **하나**여야 한다 (열린 날 2026-07-30, 3회차).
#   예전에는 여기서만 쓰는 `DIM_GROUP_RE` 를 따로 갖고 있었고, class 쪽을 `\bdim\b` 로 잡았다.
#   그런데 빌드의 L2 검사는 `_tagged_group_spans(svg, ("dim","measure"))` 로 **부분문자열**을 본다.
#   그래서 `class='dimension'` 은 **L2 에는 보이고 C5 에는 안 보였다** — 실측:
#   `fig-p08-ramp` 의 z 치수 그룹이 정확히 그 형태이고, 보조선 시작점 검사를 한 번도 받은 적이 없다.
#   같은 대상을 두 자로 재면 반드시 갈라진다(`test_dash_role_registry_is_shared` 와 같은 부류).
#   중첩 `<g>` 를 세어 닫는 것도 그쪽이 이미 옳게 하고 있다 — 그래서 그 함수를 그대로 쓴다.
DIM_PIPE_MIN_WIDTH = 6.0     # 이보다 굵으면 관·기둥(형상)으로 본다
DIM_EXTENSION_MAX_WIDTH = 1.5  # 치수보조선 굵기 규격 상한
_CENTER_TOL = 0.6
# 이 절반두께를 넘으면 외형선을 따로 등록한다.
#
# ★ 3.0 → 1.0 (2026-08-02, 사용자 지적 [사용자 발화 인용 생략]). C5 의 관·기둥 기준(6)을 그대로 빌려 썼는데, **재는 면이 어디냐는
#   질문에는 '굵은 관이냐'가 아니라 '중심선과 외형선이 다르냐'가 기준이다.**
#   실측 `fig-barometer-manometer` 기압계 관: 굵기 5 → half 2.5 라 이 문턱 **바로 아래**여서
#   외형선이 등록되지 않았고, 그래서 검사는 보조선이 관 외형(142.5)에서 **0.9px** 떨어진 것을
#   중심선(140)까지 재어 **정확히 4.00** 으로 통과시켰다. 굵기 4~6 인 관·벽이 이 리포에 여럿이다.
_OUTLINE_MIN_HALF = 1.0


def _stroked_segments(svg):
    """(x1, y1, x2, y2, stroke-width). 굵기를 함께 내야 '관'과 '가는 선'을 가를 수 있다."""
    out = []
    for m in re.finditer(r"<(line|path)([^>]*?)/?>", svg):
        tag, attrs = m.group(1), m.group(2)
        try:
            width = float(_effective(svg, m.start(), attrs, "stroke-width", "0") or 0)
        except (TypeError, ValueError):
            width = 0.0
        if tag == "line":
            pts = [tuple(float(_attr(attrs, k, "0")) for k in ("x1", "y1", "x2", "y2"))]
        else:
            dstr = _attr(attrs, "d")
            # ★ 채운 화살촉의 **테두리는 선이 아니다** (2026-08-07).
            #   접합부 흰 이음매를 없애려고 화살촉에 자기 색 stroke 를 두른 뒤
            #   (`fix_arrow_seam.py`), 그 삼각형의 세 변이 여기서 **가는 실선 3개**로 잡혀
            #   C7(치수선 태깅 누락)이 멀쩡한 삽화 둘을 신고했다. 화살촉은 도형이고
            #   그 stroke 는 렌더링 보정이므로 '선'을 세는 자에서 뺀다.
            if _is_triangle_path(dstr or "", closed=True):
                continue
            pts = _path_polyline(dstr) if dstr else []
        for p in pts:
            out.append((p[0], p[1], p[2], p[3], width))
    return out


def _on_centerline(point, thick):
    """끝점이 굵은 선의 **중심선** 위인가 (외형선은 아니다)."""
    px, py = point
    x1, y1, x2, y2, _w = thick
    if abs(x1 - x2) < 0.5 and abs(px - x1) <= _CENTER_TOL:      # 수직 관
        return min(y1, y2) - 1 <= py <= max(y1, y2) + 1
    if abs(y1 - y2) < 0.5 and abs(py - y1) <= _CENTER_TOL:      # 수평 관
        return min(x1, x2) - 1 <= px <= max(x1, x2) + 1
    return False


def dim_extension_origin_issues(ch):
    """치수보조선이 관 중심선에서 시작한 자리. 순수 함수 — 테스트가 부른다."""
    out = []
    for fig_id, dg in iter_chapter_diagrams(ch):
        svg = str(dg.get("svg") or "")
        thick = [s for s in _stroked_segments(svg) if s[4] >= DIM_PIPE_MIN_WIDTH]
        if not thick:
            continue
        for start, end, _body in _tagged_group_spans(svg, ("dim", "measure")):
            # 본문만 넘기면 안 된다 — `<g stroke-width='1'>` 처럼 **그룹이 물려주는 굵기**를
            # `_effective` 가 못 찾아 굵기 0 이 되고, 그러면 보조선 판정이 통째로 꺼진다.
            for seg in _stroked_segments(svg[start:end]):
                if not (0 < seg[4] <= DIM_EXTENSION_MAX_WIDTH):
                    continue
                # `end` 를 다시 쓰지 않는다 — 바깥 루프의 그룹 끝 위치를 덮는다(잠재 버그).
                for pt in ((seg[0], seg[1]), (seg[2], seg[3])):
                    if any(_on_centerline(pt, t) for t in thick):
                        out.append(fig_id + ": 치수보조선이 관·기둥의 **중심선**에서 시작한다 — "
                                   "끝점 (%g, %g). 재는 것은 '중심에서 중심까지'가 아니라 "
                                   "**면에서 면까지**다. 외형선에서 살짝 띄워 시작할 것 "
                                   "(AGENTS 삽화 표준, 2026-07-30)" % pt)
                        break
    return out


# ★ C7. 치수선처럼 생겼는데 **치수 그룹 태깅이 없다** (열린 날 2026-07-30, 4회차 계획 → 5회차 신설).
#
# 이 부류가 남아 있던 구조적 이유는 단순하다 — **태깅 없는 치수선을 보는 검사가 0개였다.**
#   · C5(보조선 시작점)는 `<g class='dim'>` 안만 본다.
#   · L2(가는 실선·파선 금지)도 태깅된 그룹만 본다.
#   · L2 '후보' 경고는 **양방향 채운 화살촉**이 있을 때만 뜬다.
# 그래서 종단이 **눈금 틱**인 치수선은 셋 중 어느 것에도 걸리지 않는다.
# 실측(2026-07-30): `fig-spring-work-motion` 의 변위 치수가 끝점을 두 사각형의 **중심**에 두고
# 있었는데 빌드는 exit 0 이었다. 4건을 손으로 고쳐도 다섯 번째가 같은 틈으로 들어온다.
#
# 판정: 가는 선(≤1.5) 하나가 축에 나란하고, **양 끝점을 가로지르는 짧은 수직 틱**이 둘 다 있으면
# 치수선으로 본다. 그 선이 치수 그룹 밖에 있으면 신고한다.
#
# ★ 묶음 브래킷과 가르는 기준은 **'가로지르는가'** 다. 치수보조선은 본선을 양쪽으로 넘어가고,
#   `⌐‾‾⌐` 같은 grouping 브래킷의 끝은 **한쪽으로만** 꺾인다. 이 한 조건이 오탐을 없앤다
#   (`fig-deriv-enthalpy-promotion` 의 묶음 브래킷으로 확인).
DIM_TICK_MAX_LEN = 26.0        # 이보다 길면 틱이 아니라 형상선이다 (실측: 24px 캡이 있었다)
DIM_MAIN_MIN_LEN = 30.0        # 이보다 짧으면 치수 본선으로 보지 않는다
DIM_TICK_CROSS_MIN = 2.0       # 본선을 양쪽으로 이만큼씩 넘어가야 '가로지른다'
# ★ 본선 굵기 상한을 **규격(1.5)보다 넉넉히** 잡는다 (2026-07-30 6회차).
#   규격대로 1.5 로 막았더니 `fig-lifting-work` 의 Δz(본선 1.8)가 통째로 빠졌다 —
#   **굵은 것이 위반인데 굵어서 검사를 면제받는** 뒤집힌 구조였다. 후보 판정은 넓게 잡고,
#   굵기 위반 자체는 태깅 뒤 L2 가 본다.
DIM_MAIN_MAX_WIDTH = 2.4
# ★ 틱이 본선 **끝점에서 화살촉 길이만큼 밖**에 있어도 같은 치수다 (2026-07-30 6회차).
#   `fig-lifting-work` 는 본선이 y=72 에서 끝나고 화살촉이 62 까지 가며 **틱은 62 에 있다.**
#   끝점만 보면 그 틱을 못 찾아 '치수선이 아니다'로 빠진다. 실제로 그렇게 빠졌다.
DIM_TICK_ALONG_TOL = 12.0


def _strip_tagged_groups(svg, marks):
    """태깅된 그룹을 통째로 들어낸 나머지 — 그룹 **밖**만 보려는 검사가 쓴다."""
    out, last = [], 0
    for start, end, _body in _tagged_group_spans(svg, marks):
        out.append(svg[last:start])
        last = end
    out.append(svg[last:])
    return "".join(out)


def _dim_main_axis(seg):
    if abs(seg[1] - seg[3]) < 0.5 and abs(seg[0] - seg[2]) >= DIM_MAIN_MIN_LEN:
        return "h"
    if abs(seg[0] - seg[2]) < 0.5 and abs(seg[1] - seg[3]) >= DIM_MAIN_MIN_LEN:
        return "v"
    return None


def _crossing_tick(seg, point, axis):
    """`point` 를 **가로지르는** 짧은 수직 세그먼트인가 (치수보조선의 표식)."""
    x1, y1, x2, y2, width = seg
    if not (0 < width <= DIM_EXTENSION_MAX_WIDTH):
        return False
    if axis == "h":                                  # 본선이 수평 → 틱은 수직
        if abs(x1 - x2) >= 0.5 or abs(y1 - y2) > DIM_TICK_MAX_LEN:
            return False
        if abs(x1 - point[0]) > DIM_TICK_ALONG_TOL:  # 화살촉 길이만큼 밖에 있어도 같은 치수다
            return False
        lo, hi = min(y1, y2), max(y1, y2)
        return lo <= point[1] - DIM_TICK_CROSS_MIN and hi >= point[1] + DIM_TICK_CROSS_MIN
    if abs(y1 - y2) >= 0.5 or abs(x1 - x2) > DIM_TICK_MAX_LEN:
        return False
    if abs(y1 - point[1]) > DIM_TICK_ALONG_TOL:
        return False
    lo, hi = min(x1, x2), max(x1, x2)
    return lo <= point[0] - DIM_TICK_CROSS_MIN and hi >= point[0] + DIM_TICK_CROSS_MIN


# ★★ C7 확장 — **화살촉으로 끝나는** 치수선도 본다 (넓힌 날 2026-08-02).
#
#   첫 판은 종단이 **눈금 틱**인 치수선만 봤다. 그런데 AGENTS 삽화 표준이 요구하는 정상 형태는
#   [사용자 발화 인용 생략] 이다 — 즉 **규격을 지킨 치수선일수록 검사 밖**이었다.
#   틱 종단은 그 자체로 비규격이니, 첫 판은 사실상 '비규격인 것만 보는' 자였다.
#   (L2 후보 경고가 양방향 화살촉을 보긴 하지만 조건이 `not tagged_dimension` — 그 삽화에
#   태깅된 치수가 **하나라도 있으면** 나머지가 통째로 조용해진다.)
#
# ★ 오탐과 가르는 조건은 **굵기**다. 압력·힘 화살표는 형상선 굵기(2~2.5)로 그리고 치수선은
#   규격상 ≤1.5 다. 넓힌 첫 실행에서 `fig-multifluid-manometer` 의 압력 화살표가 치수선으로
#   잡혔던 것이 이 조건으로 갈린다. 여기서는 후보 판정도 **규격 굵기로 조인다** —
#   틱 종단 쪽(`DIM_MAIN_MAX_WIDTH` 2.4)과 다른 이유는, 틱은 그 자체가 치수 표식이라
#   굵어도 치수인 반면 **화살촉은 치수·힘·유동이 공유하는 기호**여서 굵기 말고는 단서가 없다.
DIM_ARROW_END_TOL = 2.0       # 본선 끝이 화살촉 밑변 중앙에서 이만큼 안이면 이어진 것으로 본다


def _arrow_terminated(main, arrows):
    """본선의 **양 끝이 모두** 바깥을 향한 화살촉 밑변에 닿아 있는가."""
    ends = ((main[0], main[1]), (main[2], main[3]))
    other = (ends[1], ends[0])
    for pt, far in zip(ends, other):
        hit = False
        for arrow in arrows:
            if _distance(pt, arrow["base"]) > DIM_ARROW_END_TOL:
                continue
            # 화살촉이 **바깥**(반대쪽 끝에서 멀어지는 쪽)을 가리켜야 치수선이다.
            # 안쪽을 가리키면 그건 무언가를 지목하는 지시선이다.
            if _distance(arrow["tip"], far) > _distance(arrow["base"], far):
                hit = True
                break
        if not hit:
            return False
    return True


def untagged_dimension_issues(ch):
    """치수 그룹 밖에 있는 '틱·화살촉 종단 치수선'. 순수 함수 — 테스트가 부른다."""
    out = []
    for fig_id, dg in iter_chapter_diagrams(ch):
        svg = str(dg.get("svg") or "")
        rest = _strip_tagged_groups(svg, ("dim", "measure"))
        segs = _stroked_segments(rest)
        thin = [s for s in segs if 0 < s[4] <= DIM_EXTENSION_MAX_WIDTH]        # 틱 후보
        mains = [s for s in segs if 0 < s[4] <= DIM_MAIN_MAX_WIDTH]           # 본선 후보
        arrows = arrow_geometry(rest)
        for main in mains:
            axis = _dim_main_axis(main)
            if not axis:
                continue
            ends = ((main[0], main[1]), (main[2], main[3]))
            by_tick = all(any(_crossing_tick(t, pt, axis) for t in thin if t is not main)
                          for pt in ends)
            by_arrow = (main[4] <= DIMENSION_LINE_MAX_WIDTH
                        and _arrow_terminated(main, arrows))
            if by_tick or by_arrow:
                out.append(fig_id + ": 치수선인데 치수 그룹 태깅이 없다 — "
                           "(%g, %g)-(%g, %g). 태깅이 없으면 규격 검사(가는 실선·보조선 시작점)가 "
                           "**하나도 돌지 않는다.** `<g class='dim'>` 으로 묶고 종단은 "
                           "눈금 틱이 아니라 **채운 화살촉**으로 할 것 (AGENTS 삽화 표준)"
                           % (main[0], main[1], main[2], main[3]))
                break                                # 삽화당 1건만 — 목록이 아니라 지목이 목적이다
    return out


# ★ C10. 치수보조선의 **간격**(물체에서 띄운 양)과 **넘김**(치수선을 지나 더 나간 양)
# (열린 날 2026-07-31 — 사용자 지적).
#
# 사용자 원문: [사용자 발화 인용 생략],
# [사용자 발화 인용 생략]
#
# **왜 또 났나 — 규격이 '방향'만 있고 '수치'가 없었다.** AGENTS 는 이미
#   ⑴ [사용자 발화 인용 생략] ⑵ [사용자 발화 인용 생략]
# 라고 적고 있었지만 **얼마나**가 없다. 그래서 삽화마다 사람이 눈으로 정했고 갈라졌다 —
# 실측(같은 viewBox 폭 500): 볼트 `간격 3 · 넘김 8`, 스프링 `간격 6 · 넘김 0`.
# [사용자 발화 인용 생략] 같은 서술은 검사가 될 수 없다. 이 부류는 라벨 여백(0.5em/1.0em)에서 이미
# 겪은 것과 같다 — **수치를 못박고 기계가 재기 시작하자 비로소 멈췄다.**
#
# 기준값의 근거: **사용자가 적합하다고 판정한 볼트 삽화**(`fig-elastic-rod-work`)를 그대로 쓴다.
# 배율 독립을 위해 화면 실효 px 로 환산한다(글자 크기 규격과 같은 방식) —
#   간격 3px × 612/500 = 3.7 → **4px**, 넘김 8px × 612/500 = 9.8 → **10px**.
# 제도 관례(KS/ISO: 간격 ~1mm, 넘김 ~2mm)와도 비율이 맞는다(넘김 ≈ 간격의 2.5배).
DIM_GAP_SCREEN_PX = 4.0        # 물체 외형선 → 보조선 시작
DIM_OVERSHOOT_SCREEN_PX = 10.0  # 치수선을 지나 더 나가는 양
DIM_GEOM_TOL_PX = 2.0          # 화면 실효 기준 허용 오차
_DIM_GAP_SEARCH_PX = 26.0      # 보조선 끝에서 물체를 찾는 거리(이보다 멀면 '재는 면이 없다')


_FILLED_PATH = re.compile(r"<path\b([^>]*)/?>")


def _filled_heads(body, svg=None, body_offset=0):
    """치수 그룹 안 **채운 화살촉**의 꼭짓점 목록 (순수 함수).

    쓰임이 둘이다 — ⑴ 본선을 고르는 기준(화살촉이 놓인 선이 본선이다)
    ⑵ 화살촉의 **변**을 보조선으로 오인하지 않게 걸러내는 것. 그룹이 `stroke-width` 를
    물려주면 채운 삼각형의 세 변이 전부 '가는 선'으로 잡혀 보조선 행세를 한다(실측).

    ★ `fill` 은 **상속을 본다** (열린 날 2026-08-01, math 실측).
      종전에는 요소 자신의 `fill` 속성만 읽었다. 그런데 이 리포의 치수 그룹은
      `<g class='dim' fill='#5a6472'>` 로 색을 **그룹에 한 번** 주고 화살촉은
      `<path d='…' stroke='none'/>` 로만 쓰는 형태가 흔하다 — 유효한 SVG이고 화면에도
      정상으로 그려진다. 그런데 검사는 `fill` 이 None 이라 화살촉을 **하나도 못 찾고**,
      바로 아래 `if not (mains and heads): continue` 에서 **그 치수 그룹을 통째로 건너뛴다.**

      증상이 지독한 이유: 감사가 `규격 이탈 0건 / 0건` 을 찍는다. 분자만 보면 통과처럼
      보이지만 **분모가 0** 이다 — '없다'가 아니라 '한 개도 안 봤다'이다(AGENTS 규칙 11).
      실측(공학수학 ch01 `fig-existence-rect`): 치수 그룹 3개 · 보조선 6개가 전부
      C10 검사 **밖**에 있었다. 같은 부류를 2026-07-30 에 `<polygon>` 화살촉으로 한 번
      겪었다 — *검사가 데이터의 정당한 표현형을 못 보는* 형태다.

      `_effective` 를 쓰므로 중첩 그룹(`<g fill><g stroke><path/></g></g>`)도 따라간다.
      `svg` 를 안 주면 종전대로 자기 속성만 본다(호출부가 위치를 못 줄 때의 보수적 기본값).
    """
    out = []
    for m in _FILLED_PATH.finditer(body):
        attrs = m.group(1)
        fill = (_effective(svg, body_offset + m.start(), m.group(0), "fill", "")
                if svg is not None else _attr(attrs, "fill"))
        if not fill or fill == "none":
            continue
        # ★ **subpath 마다 화살촉 하나다** (2026-08-01). 한 `<path>` 에 삼각형 둘을
        #   `M… Z M… Z` 로 담는 형태가 흔한데(치수선 양끝), `d` 전체의 숫자를 한 덩어리로 읽으면
        #   꼭짓점 6개의 **평균**이 나와 화살촉이 1개로 뭉친다. 그러면 ⑴ 축을 화살촉 배치로
        #   정하는 판정이 `len(centers) >= 2` 에서 꺼지고 ⑵ `_is_head_edge` 가 서로 다른
        #   삼각형의 꼭짓점 둘을 이어도 '변'으로 쳐서 멀쩡한 보조선을 지운다.
        #   실측 `fig-ch01-q11-situation` 이 정확히 이 형태였다.
        for chunk in re.split(r"(?=[Mm])", _attr(attrs, "d", "")):
            nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", chunk)]
            pts = list(zip(nums[0::2], nums[1::2]))
            if len(pts) >= 3:
                out.append(pts)
    return out


def _head_center(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _is_head_edge(seg, heads):
    """이 선분이 화살촉 삼각형의 변인가 (양 끝이 같은 삼각형의 꼭짓점이면 그렇다)."""
    for pts in heads:
        near_a = any(abs(seg[0] - x) < 0.6 and abs(seg[1] - y) < 0.6 for x, y in pts)
        near_b = any(abs(seg[2] - x) < 0.6 and abs(seg[3] - y) < 0.6 for x, y in pts)
        if near_a and near_b:
            return True
    return False


def _point_to_segment(point, seg):
    """점과 선분 사이 거리 (순수 함수)."""
    px, py = point
    x1, y1, x2, y2 = seg[:4]
    dx, dy = x2 - x1, y2 - y1
    span = dx * dx + dy * dy
    t = 0.0 if span == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / span))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _collinear_face(pos, ends, sign, limit):
    """**같은 직선 위**에 놓인 형상선의 끝까지 거리 (없으면 None). 순수 함수.

    ★ 열린 날 2026-08-05 (`fig-01-p04`, 사용자 [사용자 발화 인용 생략]).

    `_perpendicular_hits` 는 보조선을 **가로지르는** 선만 면으로 센다. 그래서 보조선과
    **같은 직선 위**에 있는 형상선은 광선이 '만나지' 않고 따라 달려 **보이지 않는다.**
    실측: 압력축의 눈금선(y=126, x 232~248)이 보조선(y=126)과 collinear 라, 자가 그것을
    건너뛰고 **그 너머의 세로축**을 면으로 잡아 엉뚱한 값(2.73)을 냈다. 눈에는 보조선이
    눈금선에 딱 붙어 보이는데 자는 통과시킨 것이다.

    같은 직선 위에서는 **선의 끝**이 곧 면이다 — 그 끝을 후보로 낸다.
    """
    cands = [(e - pos) * sign for e in ends]
    cands = [d for d in cands if 0 <= d <= limit]
    return min(cands) if cands else None


def _perpendicular_hits(point, axis, sign, segments, limit):
    """`point` 에서 `sign` 방향으로 만나는 **형상선**까지의 거리들 — 가까운 순.

    보조선은 재는 면에서 출발한다. 그 면이 어디인지는 '보조선을 그 방향으로 연장하면
    무엇에 부딪히는가'로 정한다 — 도형 종류(rect·path)를 열거하지 않으므로 새 도형에도 유효하다.

    ★ **끝점을 스치는 것도 면으로 센다 — 바꾸려다 되돌렸다** (2026-08-05, `fig-02-q03`).
      노면에서 뽑은 보조선의 '재는 면'을 이 함수가 **바퀴의 세로 접선**으로 잡는다(끝점을
      광선이 정확히 스친다). 스침을 빼 보았더니 **규격 이탈이 1건 → 3건**으로 늘어
      `fig-card-potential-datum`·`fig-02-q09` 의 판정이 바뀌었다 — 정상 삽화의 면 인식까지
      함께 흔든다는 뜻이라, 그 둘을 검증하기 전에는 넣지 않는다.
      (인스턴스는 데이터 쪽에서 닫았다: 도로 끝을 바퀴 끝에 맞춰 보조선이 도형 위를
       지나지 않게 했다. 도구 교정은 별도 배치.)
    """
    px, py = point
    out = []
    for x1, y1, x2, y2 in segments:
        dist = None
        if axis == "v":                       # 보조선이 수직 → 가로 형상선을 만난다
            if abs(y1 - y2) <= 0.5:
                if min(x1, x2) - 0.5 <= px <= max(x1, x2) + 0.5:
                    dist = (y1 - py) * sign
            elif abs(x1 - x2) <= 0.5 and abs(x1 - px) <= 0.5:
                dist = _collinear_face(py, (y1, y2), sign, limit)
        else:
            if abs(x1 - x2) <= 0.5:
                if min(y1, y2) - 0.5 <= py <= max(y1, y2) + 0.5:
                    dist = (x1 - px) * sign
            elif abs(y1 - y2) <= 0.5 and abs(y1 - py) <= 0.5:
                dist = _collinear_face(px, (x1, x2), sign, limit)
        if dist is not None and 0 <= dist <= limit:
            out.append(dist)
    return sorted(out)


def _perpendicular_hit(point, axis, sign, segments):
    """처음 만나는 형상선까지의 거리 (없으면 None)."""
    hits = _perpendicular_hits(point, axis, sign, segments, _DIM_GAP_SEARCH_PX)
    return hits[0] if hits else None


# 보조선이 재는 면을 **지나쳐 도형 안으로** 들어갔는지 볼 때 뒤쪽을 훑는 거리.
# 짧게 잡는다 — 멀리 있는 남의 도형까지 보면 정상 보조선이 신고된다.
_DIM_INSIDE_SEARCH_PX = 12.0


def _extension_starts_inside(point, axis, sign, segments, forward):
    """보조선 끝이 도형을 **파고들었는지** — 그렇다면 파고든 깊이(양수), 아니면 None.

    ★ 열린 날 2026-08-02 (사용자: [사용자 발화 인용 생략]).

    **결함 자체가 검사를 통과시키던 자리다.** 간격은 [사용자 발화 인용 생략]
    까지로 재는데, 굵은 관은 중심선도 면으로 등록돼 있어서 보조선이 **관 속에서** 시작하면
    바깥으로 나가다 중심선을 먼저 만나 **정확히 규격값**이 나온다.
    실측 `fig-barometer-manometer` U자관(관 굵기 18, 중심 340 · 외형 331/349):
    보조선이 x=343.4 에서 시작해 **관 벽 안**인데 간격이 4.00 으로 통과했다.

    그래서 **뒤쪽도 본다.** 뒤(치수선 쪽)에서 더 가까운 면을 만나면 그건 이미 지나쳐 온 면이다.
    """
    hits = _perpendicular_hits(point, axis, -sign, segments, _DIM_INSIDE_SEARCH_PX)
    if not hits:
        return None
    if forward is not None and forward <= hits[0]:
        return None                   # 앞쪽 면이 더 가깝다 = 정상적으로 면 밖에 있다
    # ★ **가장 먼** 면을 돌려준다. 관은 벽(외형선 2줄)과 유체(또 2줄)가 겹쳐 있어서
    #   가까운 면만 보면 *유체 가장자리*로 나가라는 처방이 되고, 그건 여전히 관 벽 속이다.
    #   실측 U자관(벽 331/349 · 유체 334/346): 가까운 면 346 → 벽 안, 먼 면 349 → 벽 밖.
    return hits[-1]


_DIM_CLUSTER_MARGIN = 25.0     # 화살촉·보조선이 본선 끝에서 이만큼 밖이어도 같은 치수다
_DIM_HEAD_ON_AXIS_TOL = 1.5    # 화살촉 무게중심이 본선 축에서 이만큼 안이면 그 본선의 것이다


def _dim_clusters(segs, heads):
    """한 치수 그룹 안의 **치수들** — [{axis, base, lo, hi, main}]. 순수 함수(테스트가 직접 부른다).

    치수 하나 = **화살촉 둘 이상이 한 축 위에 놓인 선**. 화살촉은 치수의 양 끝을 가리키므로
    그 배치가 곧 치수의 정체다(본선 길이로 고르면 좁은 치수에서 뒤집힌다 — 2026-08-01 선례).
    """
    centers = [_head_center(pts) for pts in heads]
    found, seen = [], set()
    for seg in segs:
        if abs(seg[1] - seg[3]) < 0.5:
            axis, base = "h", (seg[1] + seg[3]) / 2.0
            lo, hi = min(seg[0], seg[2]), max(seg[0], seg[2])
            along, across = [c[0] for c in centers], [c[1] for c in centers]
            # ★ 구간은 **꼭짓점까지** 잡는다 — 보조선은 화살촉 *끝*에 서 있지 무게중심에
            #   서 있지 않다. 무게중심 구간으로 자르면 정상 보조선이 통째로 빠진다
            #   (회귀 `좁은 치수` 가 그 형태다: 무게중심 126.7·173.3 인데 보조선은 100·200).
            spans = [(min(p[0] for p in pts), max(p[0] for p in pts)) for pts in heads]
        elif abs(seg[0] - seg[2]) < 0.5:
            axis, base = "v", (seg[0] + seg[2]) / 2.0
            lo, hi = min(seg[1], seg[3]), max(seg[1], seg[3])
            along, across = [c[1] for c in centers], [c[0] for c in centers]
            spans = [(min(p[1] for p in pts), max(p[1] for p in pts)) for pts in heads]
        else:
            continue
        idx = [i for i in range(len(centers))
               if abs(across[i] - base) <= _DIM_HEAD_ON_AXIS_TOL
               and lo - _DIM_CLUSTER_MARGIN <= along[i] <= hi + _DIM_CLUSTER_MARGIN]
        if len(idx) < 2:
            continue                      # 화살촉 하나로는 치수의 양 끝을 말할 수 없다
        key = (axis, round(base, 1), tuple(idx))
        if key in seen:
            continue                      # 본선을 두 조각으로 그린 경우 — 같은 치수다
        seen.add(key)
        found.append({"axis": axis, "base": base, "main": seg,
                      "lo": min(spans[i][0] for i in idx),
                      "hi": max(spans[i][1] for i in idx)})
    return found


_DIM_TEXT_RE = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)


def dim_label_rows(svg):
    """치수 하나마다 «치수선 · 그룹 안 라벨 · 그룹 밖 후보» 를 낸다. 순수 함수.

    ★ 검사(C25)와 처방(`tools/fix_dim_label.py`)이 **같은 자**를 쓰게 하려고 여기 둔다.
      자와 처방이 갈리면 조용히 샌다 — 이 리포는 `fix_honorific` 이 삽화 캡션을 안 돌던
      형태로 이미 겪었다(R-72, 2026-08-04).

    후보는 **치수 그룹 밖의 모든 글자**를 치수선까지의 거리로 정렬한 것이다. 고르는 것은
    사람이다 — 자동으로 가장 가까운 것을 라벨로 단정하면 캡션·상태 라벨을 끌고 들어온다.

    ★ 글자는 `checks_svg._svg_texts` 로 읽는다. 처음엔 여기서 따로 읽었는데 그 자가
      **`font-family='ui-monospace, …'` 가 붙은 글자를 통째로 놓쳤다** — 속성을 찾는 정규식에
      경계가 없어 `y=` 를 `font-fam**ily**='ui-monospace…'` 안에서 먼저 찾고 float 변환에
      실패해 그 글자를 버렸다. 실측 피해가 정확히 이 리포가 반복해 겪는 형태다:
      `fig-q16-hydraulic-lift`·`fig-ch01-q09-situation` 의 치수 라벨이 **후보 목록에 아예 없었고**
      검사는 조용히 '라벨 없음'만 찍었다. 자를 두 벌 두면 갈라진다 — 그래서 한 벌만 쓴다.
    """
    groups = _tagged_group_spans(svg, ("dim", "measure"))
    texts = [t for t in _svg_texts(svg) if t["s"].strip()]
    rows = []
    for start, end, body in groups:
        heads = _filled_heads(body, svg, svg.find(body, start))
        segs = [s for s in _stroked_segments(svg[start:end]) if not _is_head_edge(s, heads)]
        clusters = _dim_clusters(segs, heads)
        if not clusters:
            continue
        inside = [t for t in texts if start <= t["pos"] < end]
        outside = [t for t in texts
                   if not any(s <= t["pos"] < e for s, e, _b in groups)]
        for cl in clusters:
            cand = sorted(outside, key=lambda t: _point_to_segment((t["x"], t["y"]), cl["main"]))
            rows.append({"group": (start, end), "axis": cl["axis"], "base": cl["base"],
                         "lo": cl["lo"], "hi": cl["hi"], "main": cl["main"],
                         "mid": (cl["lo"] + cl["hi"]) / 2.0,
                         "inside": inside, "outside": cand})
    return rows


# ★ C34. **점선이 실선을 덮고 있는가** (열린 날 2026-08-02 R-23, **2026-08-05 재지적**).
#
# 사용자: [사용자 발화 인용 생략](08-02) →
#         [사용자 발화 인용 생략](08-05)
#
# ★★ **왜 또 났나 — 처방을 적어 두고 실행하지 않았다.** 08-02 에 인박스 R-23 이 좌표까지
#   실측해 [사용자 발화 인용 생략] 라고 처방을 써 두었는데, **그 배치가 그대로 안 돌았다.**
#   즉 이 부류의 실패는 '몰랐다'가 아니라 **'적어 두면 된다고 믿은 것'** 이다 —
#   인박스는 사람이 읽어야 실행되는 장치라, 안 읽히면 아무 일도 일어나지 않는다.
#   그래서 판정을 **빌드로 옮긴다**: 매 빌드가 스스로 신고하면 안 읽힐 수가 없다.
#
# ★ 판정: 점선 조각과 실선 조각이 ⑴ 거의 나란하고(2° 이내) ⑵ 수직 거리 1.5px 이내이며
#   ⑶ 겹치는 구간이 20px 을 넘으면 신고. 두 선이 **같은 것을 두 번 그린 것**이므로
#   하나는 지워야 한다(AGENTS 「파선은 숨은선의 몫」 — 보이는 실선 위에 겹칠 이유가 없다).
DASH_OVER_SOLID_MIN_OVERLAP = 20.0    # 이보다 짧게 스치는 것은 교차이지 '덮음'이 아니다
DASH_OVER_SOLID_MAX_OFFSET = 1.5      # 수직 거리 (SVG px)


def _dash_flagged_segments(svg):
    """(점선인가, 조각) 목록 — 획이 있는 line/path 만. 순수 함수.

    ★ 이름을 `_stroked_segments` 로 지었다가 **같은 모듈의 기존 함수를 덮어썼다**
      (2026-08-05). 그쪽은 `(x1,y1,x2,y2,굵기)` 5-튜플을 내는데 이쪽은 4-튜플이라
      치수 검사 6개가 `s[4]` 에서 IndexError 로 죽었다 — 파이썬은 재정의를 경고하지
      않으므로 **이름이 곧 계약**이다. 새 헬퍼를 넣을 때는 모듈 안 이름을 먼저 확인할 것.
    """
    out = []
    for m in re.finditer(r"<(?:line|path|polyline)\b([^>]*?)/?>", svg):
        attrs, pos = m.group(1), m.start()
        if _effective(svg, pos, attrs, "stroke", "none") in (None, "none"):
            continue
        if _effective(svg, pos, attrs, "fill", "none") not in (None, "none"):
            continue                  # 채운 도형(화살촉 등)은 선이 아니다
        # ★ **중심선은 이 검사의 대상이 아니다** (2026-08-23). C34 의 근거는 [사용자 발화 인용 생략] 인데, **중심선은 형상을 가로지르는 것이
        #   정상**이라 그 전제가 성립하지 않는다(축·구멍의 중심을 가리키는 표시다).
        #   빼지 않으면 규격대로 그린 그림이 «같은 것을 두 번 그렸다» 로 막힌다 — 실제로
        #   `class='axis'` 를 1점 쇄선으로 바꾼 순간 6건이 그렇게 걸렸다.
        if re.search(r"class\s*=\s*['\"][^'\"]*\baxis\b", attrs):
            continue
        dashed = bool((_effective(svg, pos, attrs, "stroke-dasharray", "") or "").strip()
                      not in ("", "none"))
        for seg in _svg_segments(m.group(0)):
            out.append((dashed, seg))
    return out


def dashed_over_solid_issues(svg):
    """점선이 실선을 덮은 자리. 순수 함수 — 테스트가 직접 부른다."""
    rows = _dash_flagged_segments(svg)
    dashed = [s for d, s in rows if d]
    solid = [s for d, s in rows if not d]
    out, seen = [], set()
    for dx1, dy1, dx2, dy2 in dashed:
        dlen = ((dx2 - dx1) ** 2 + (dy2 - dy1) ** 2) ** 0.5
        if dlen < DASH_OVER_SOLID_MIN_OVERLAP:
            continue
        ux, uy = (dx2 - dx1) / dlen, (dy2 - dy1) / dlen
        for sx1, sy1, sx2, sy2 in solid:
            slen = ((sx2 - sx1) ** 2 + (sy2 - sy1) ** 2) ** 0.5
            if slen < DASH_OVER_SOLID_MIN_OVERLAP:
                continue
            vx, vy = (sx2 - sx1) / slen, (sy2 - sy1) / slen
            if abs(ux * vx + uy * vy) < 0.9994:      # 2° 이내로 나란한가
                continue
            # ★ 나란한 두 선의 거리는 **수직 오프셋**으로 잰다 — 끝점 거리로 재면 안 된다.
            #   실선이 점선보다 길어 양쪽으로 삐져나오면 두 끝이 모두 멀어서, 정확히 겹친
            #   경우가 오히려 통과한다(이 검사를 처음 짤 때 실제로 그렇게 새어나갔다:
            #   지면선 82~636 vs 점선 126~570 → 끝점 거리 44·66 인데 오프셋은 0).
            if abs((sx1 - dx1) * uy - (sy1 - dy1) * ux) > DASH_OVER_SOLID_MAX_OFFSET:
                continue
            # 점선 축에 실선을 투영해 겹치는 길이를 잰다.
            t1 = (sx1 - dx1) * ux + (sy1 - dy1) * uy
            t2 = (sx2 - dx1) * ux + (sy2 - dy1) * uy
            lo, hi = max(0.0, min(t1, t2)), min(dlen, max(t1, t2))
            if hi - lo < DASH_OVER_SOLID_MIN_OVERLAP:
                continue
            key = (round(dx1), round(dy1), round(dx2), round(dy2))
            if key in seen:
                continue
            seen.add(key)
            out.append("점선이 실선을 %.0fpx 덮고 있다 — 점선 (%.4g,%.4g)-(%.4g,%.4g) 가 "
                       "실선 (%.4g,%.4g)-(%.4g,%.4g) 와 같은 자리다. 같은 것을 두 번 그린 "
                       "것이므로 하나를 지울 것(파선은 숨은선의 몫이라 보이는 실선 위에 "
                       "겹칠 이유가 없다)" % (hi - lo, dx1, dy1, dx2, dy2, sx1, sy1, sx2, sy2))
    return out


# ★ C33. **치수선이 자기 화살촉을 뚫고 나갔는가** (열린 날 2026-08-05, 사용자 ch01 문풀 4번).
#
# 사용자: [사용자 발화 인용 생략]
#
# ★ **AGENTS 삽화 표준이 이미 못 박은 규칙인데 검사가 하나도 없었다** —
#   [사용자 발화 인용 생략]
#   실측(`fig-01-p04`): 화살촉 밑변이 y=136 인데 치수선이 **y=118.16** 에서 시작해
#   꼭짓점(126)을 **7.84px 지나** 솟아 있었다. 빌드·감사 전부 통과였다.
#
# ★★ **원인 — 넘김 값이 엉뚱한 요소에 붙었다.** 118.16 = 126 − 7.84 이고 7.84 SVG px 는
#   이 삽화 배율에서 정확히 **넘김 10 화면 실효 px** 다. 넘김은 *치수보조선*이 치수선을
#   지나 더 나가는 양인데, 그것을 **치수 본선**에 적용한 것이다. 즉 규격을 몰라서가 아니라
#   **규격을 옆 요소에 붙여서** 생긴 결함이라, 사람이 다시 볼 때도 '값이 있으니 맞겠지'로 지나간다.
#
# ★ **왜 기존 자들이 못 봤나.** `arrow_geometry` 는 밑변에 **끝이 닿은** 선만 꼬리로 세므로,
#   밑변을 **지나쳐 버린** 선은 그냥 `꼬리 없음` 이 된다 — 그리고 `꼬리 없음` 은 곡선 위의
#   방향 표식·홀로 선 화살촉에서도 정상적으로 나오므로 그 자체로는 신고할 수 없다
#   (실측: ch01·ch02 의 `꼬리 없음` 8건 중 **진짜는 1건**, 나머지는 곡선 표식이었다).
#   그래서 판정을 **치수 그룹 안**으로 좁히고 축 방향 투영으로 잰다.
#
# ★ **각도 치수는 뺀다** — 호(arc) 위의 화살촉은 접선 방향이라 폴리라인 조각이 밑변을
#   정상적으로 지나간다. 여기서 안 빼면 멀쩡한 각도 치수가 전부 신고된다.
DIM_SHAFT_OVERSHOOT_TOL = 1.5    # 밑변을 이만큼 넘으면 신고 (SVG px — 좌표 반올림 여유)


def _untagged_shaft_body(svg):
    """**태깅 밖** 영역의 사본 — 치수·지시선 그룹과 곡선 path 를 공백으로 지운다.

    ★ 열린 날 2026-08-06, 사용자 재지적: [사용자 발화 인용 생략]

    ★ **의심이 맞았다.** 이 자는 `class='dim'` 그룹 **안만** 재고 있었다. ch03 4절의
      지렛대 막대는 치수선이 아니라 비율 막대라 태깅이 없었고, 그래서 1~2장에서 닫은
      규격이 3장에서 그대로 새어 나갔다 — **태깅 안 된 화살표는 어느 자도 보지 않았다.**
      '고쳤다'가 태깅된 것에만 해당했던 것이다.

    곡선이 든 path 는 여전히 뺀다 — 호 위의 접선 화살촉은 몸통이 밑변을 정상적으로
    지나가므로, 넣으면 멀쩡한 각도 치수·곡선 표식이 전부 신고된다(원 주석의 근거 그대로).
    지시선도 뺀다 — 끝을 점으로 찍는 것이 규격이라 화살촉이 아예 없다.
    """
    body = list(svg)
    for start, end, _b in (_tagged_group_spans(svg, ("dim", "measure"))
                           + _tagged_group_spans(svg, ("leader",))):
        for i in range(start, min(end, len(body))):
            body[i] = " "
    return re.sub(r"<path[^>]*\bd='[^']*[AaCcQqSsTt][^']*'[^>]*/?>", " ", "".join(body))


def dim_shaft_overshoot_issues(svg):
    """화살표 몸통이 자기 화살촉 밑변을 넘어 뻗은 자리. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    arrows = arrow_geometry(svg)
    if not arrows:
        return out
    regions = [(start, body) for start, _end, body
               in _tagged_group_spans(svg, ("dim", "measure"))]
    regions.append((0, _untagged_shaft_body(svg)))     # 태깅 밖도 잰다(위 주석이 정본)
    for start, body in regions:
        head = svg[start:svg.find(">", start) + 1].lower()
        if "angle" in head or re.search(r"\bA[\s\d.-]", body):
            continue                      # 각도 치수 — 호 위의 접선 화살촉은 대상이 아니다
        segs = _svg_segments(body)
        for arrow in arrows:
            bx, by = arrow["base"]
            tx, ty = arrow["tip"]
            span = arrow["length"]
            if span <= 0:
                continue
            ux, uy = (tx - bx) / span, (ty - by) / span
            # ★ **밑변에서 제대로 끝나는 몸통이 이미 있으면, 같은 축의 다른 선은 남의 도형이다**
            #   (2026-08-06, 태깅 밖으로 넓히며 실측). `fig-02-q12` 에서 교반기 봉이 화살표와
            #   같은 세로축에 있어 걸렸는데, 그 화살표의 진짜 몸통은 밑변에서 정확히 끝나 있었다.
            #   결함의 정의는 [사용자 발화 인용 생략] 이므로, 제대로 된 몸통이 있으면
            #   그 화살표는 결함이 아니다 — 그 위를 지나는 형상선까지 신고하면 오탐이 쏟아진다.
            #   ★ 몸통으로 인정하는 조건은 셋이다 — **축과 나란하고**, 한쪽 끝이 밑변에 닿고,
            #     나머지 끝이 꼬리 쪽(t < 0)이다. 나란함을 빼면 치수*보조*선의 끝점까지
            #     몸통으로 세어 원 회귀가 깨진다(보조선은 축과 직각이다 — 실측으로 드러났다).
            def _is_proper_shaft(seg):
                x1, y1, x2, y2 = seg
                dx, dy = x2 - x1, y2 - y1
                length = (dx * dx + dy * dy) ** 0.5
                if length < 1e-6 or abs((dx * ux + dy * uy) / length) < 0.98:
                    return False
                t1 = (x1 - bx) * ux + (y1 - by) * uy
                t2 = (x2 - bx) * ux + (y2 - by) * uy
                near, far = (t1, t2) if abs(t1) < abs(t2) else (t2, t1)
                return abs(near) <= DIM_SHAFT_OVERSHOOT_TOL and far < 0

            if any(_is_proper_shaft(s) for s in segs):
                continue
            for x1, y1, x2, y2 in segs:
                dx, dy = x2 - x1, y2 - y1
                seg_len = (dx * dx + dy * dy) ** 0.5
                if seg_len < 1e-6:
                    continue
                # 축과 나란한 선만 본다 — 비스듬히 지나가는 남의 선은 이 치수의 몸통이 아니다.
                if abs((dx * ux + dy * uy) / seg_len) < 0.98:
                    continue
                if _point_to_segment_distance(bx, by, x1, y1, x2, y2) > DIM_SHAFT_OVERSHOOT_TOL:
                    continue              # 이 화살촉의 몸통이 아니다
                # 밑변을 원점, 꼭짓점 방향을 +로 두고 투영한다. 몸통은 t ≤ 0 이어야 한다.
                over = max((x1 - bx) * ux + (y1 - by) * uy,
                           (x2 - bx) * ux + (y2 - by) * uy)
                if over > DIM_SHAFT_OVERSHOOT_TOL:
                    out.append("화살표 몸통이 자기 화살촉을 %.1fpx 뚫고 나갔다 — 선 끝은 삼각형 "
                               "밑변 중앙(%.4g,%.4g)이어야 한다(꼭짓점 아님). 넘김 10px 은 "
                               "치수*보조*선의 몫이지 본선의 몫이 아니다" % (over, bx, by))
                    break
    return out


def dim_label_placement_issues(svg):
    r"""치수 라벨이 **자기 치수선에** 붙어 있는가. 순수 함수 — 테스트가 직접 부른다.

    열린 날 2026-08-04. 사용자: [사용자 발화 인용 생략] ·
    [사용자 발화 인용 생략]

    ★★ **뿌리는 「라벨이 치수 그룹 밖에 있었다」이다.** 실측 — `fig-02-q02` 의 `z = 12 m` 와
      `fig-02-q03` 의 `Δz = 50 m` 는 둘 다 `<g id='dim-*'>` **바깥**에 있었다. 그래서 치수 규격을
      보는 검사(C10·C5)가 본선·보조선·화살촉만 재고 **라벨은 한 번도 안 봤다.**
      태깅이 없으면 검사를 안 받는다 — `untagged_dimension_issues` 와 같은 부류다.

    ★ 그래서 판정이 두 단이다:
      ⑴ 치수 그룹에 라벨이 **없으면** 그 자체를 신고한다(그룹 안으로 옮겨야 잴 수 있다)
      ⑵ 있으면 위치를 잰다 — 라벨의 세로(수직 치수) 또는 가로(수평 치수) 중심이 **치수 구간 안**인가,
        그리고 **수직 치수면 치수선 왼쪽**인가(AGENTS 삽화 표준의 문자 위치 규정).

    실측 어긋남: `z = 12 m` 는 치수선 중점(248,130)에서 **오른쪽 64·아래 54.5**,
    `Δz = 50 m` 는 중점(438,152)에서 **위로 89** 로 아예 치수 구간(94~210) 밖이었다.

    ★★ **수평 치수의 「위」는 일부러 재지 않는다 — 반박 기록** (2026-08-04, 부류5 착수 때 실측).
      AGENTS 삽화 표준은 [사용자 발화 인용 생략] 이라고 적고 있고, 실제로 전 챕터
      수평 치수 라벨 **8개 중 6개가 치수선 아래**에 있다. 그래서 처음엔 이것도 검사로
      승격하려 했는데, 좌표를 잡아 보고 **규격 쪽이 틀렸다**는 결론이 났다:

        라벨이 치수 구간보다 **넓으면** 치수선 위에 둘 자리가 자기 보조선뿐이다.
        실측 `fig-elastic-rod-work` — 구간 62px 에 라벨 `늘어난 길이 ΔL` 이 98px 이라
        위로 올리면 x=302·364 의 **자기 치수보조선 두 개를 글자가 가로지른다.**

      즉 리포의 실제 관례는 [사용자 발화 인용 생략] 이고 그게 맞다.
      한 줄짜리 규격이 못 다룬 경우라, 규격을 기계로 박으면 **더 나쁜 결함(라벨이 선을 가로지름)**
      을 만든다. 규칙도 검토 대상이다(AGENTS 규칙 12의 '강하게 반박하라') — 그래서 판정을
      넓히지 않고 여기에 근거를 남긴다. 지금 남은 실제 불일치는 `fig-continuum-vs-rarefied`
      한 장 안에서 λ 는 위, L 은 아래인 것 하나인데, 그건 **라벨 폭이 달라서 갈린 것**이라
      결함이 아니다.
    """
    out = []
    seen_groups = set()
    for row in dim_label_rows(svg):
        if not row["inside"]:
            if row["group"] in seen_groups:
                continue        # 그룹 하나당 한 번만 — 치수가 둘이어도 원인은 같다
            seen_groups.add(row["group"])
            out.append("치수 그룹에 라벨이 없다 — 라벨이 그룹 밖에 있으면 위치를 아무도 재지 않는다."
                       " 치수 문자를 `<g class='dim'>` 안으로 옮길 것")
            continue
        lo, hi, base, axis = row["lo"], row["hi"], row["base"], row["axis"]
        near = min(row["inside"],
                   key=lambda t: abs((t["y"] if axis == "v" else t["x"]) - row["mid"]))
        along = near["y"] if axis == "v" else near["x"]
        if not (lo <= along <= hi):
            out.append("치수 라벨이 치수 구간 밖이다 — %r 이 %s 치수(%.0f~%.0f)의 %.0f 에 있다."
                       " 치수선 중앙에 맞출 것"
                       % (near["s"][:24], "수직" if axis == "v" else "수평", lo, hi, along))
        if axis == "v" and near["x"] > base:
            out.append("수직 치수의 문자는 **치수선 왼쪽**이다 — %r 이 오른쪽(x=%.0f > %.0f)에 있다"
                       % (near["s"][:24], near["x"], base))
    return out


def _dedupe_extension_rows(rows):
    """한 보조선이 여러 치수에 걸렸으면 **자기 치수 하나만** 남긴다. 순수 함수.

    ★ 열린 날 2026-08-02 — 치수별 클러스터링을 넣자마자 나온 부작용. 보조선이 길면 같은 그룹의
      **두 치수**의 기준값을 모두 지날 수 있고, 그러면 한 치수는 위 끝을, 다른 치수는 아래 끝을
      '물체 쪽'으로 본다. 자동 수정 도구가 두 처방을 번갈아 적용해 **좌표가 왕복 진동**했다
      (실측 `fig-heating-value-trap`: 103.14 ↔ 110.16 무한 반복).

    판정: 보조선의 **치수선 쪽 끝**은 규격상 기준값을 겨우 10px 지난 자리다.
    그러니 `|near − base|` 가 가장 작은 짝이 진짜다.
    """
    best = {}
    for row in rows:
        key = tuple(row["seg"])
        score = abs(row["near"] - row["base"])
        if key not in best or score < best[key][0]:
            best[key] = (score, row)
    return [row for _score, row in best.values()]


def _dim_rows_for_cluster(cluster, segs, shape_segments, scale):
    """치수 하나에 딸린 보조선들의 (간격, 넘김). `dim_extension_rows` 의 몸통."""
    axis, base, main = cluster["axis"], cluster["base"], cluster["main"]
    ext_axis = "v" if axis == "h" else "h"
    rows = []
    for seg in segs:
        if seg is main or not (0 < seg[4] <= DIM_EXTENSION_MAX_WIDTH):
            continue
        if ext_axis == "v" and abs(seg[0] - seg[2]) > 0.5:
            continue
        if ext_axis == "h" and abs(seg[1] - seg[3]) > 0.5:
            continue
        # 같은 그룹의 **다른 치수**에 속한 보조선을 데려오지 않는다 — 이게 없으면 base 만 맞으면
        # 반대편 패널의 보조선까지 끌려온다(실측: L 치수의 보조선이 λ 치수에 붙었다).
        pos = seg[0] if ext_axis == "v" else seg[1]
        if not (cluster["lo"] - _DIM_CLUSTER_MARGIN <= pos <= cluster["hi"] + _DIM_CLUSTER_MARGIN):
            continue
        lo, hi = ((min(seg[1], seg[3]), max(seg[1], seg[3])) if ext_axis == "v"
                  else (min(seg[0], seg[2]), max(seg[0], seg[2])))
        if not (lo - _DIM_GAP_SEARCH_PX <= base <= hi + _DIM_GAP_SEARCH_PX):
            continue
        far, near = (lo, hi) if abs(lo - base) > abs(hi - base) else (hi, lo)
        sign = 1.0 if far > base else -1.0
        point = ((seg[0], far) if ext_axis == "v" else (far, seg[1]))
        gap = _perpendicular_hit(point, ext_axis, sign, shape_segments)
        inside = _extension_starts_inside(point, ext_axis, sign, shape_segments, gap)
        rows.append({
            "seg": seg[:4], "axis": ext_axis, "base": base, "sign": sign,
            "far": far, "near": near, "scale": scale,
            # 파고들었으면 **음수 간격**으로 낸다 — 0 을 쓰면 '면을 못 찾음'과 구별되지 않는다.
            "gap": (-inside * scale if inside is not None
                    else (None if gap is None else gap * scale)),
            "over": (near - base) * -sign * scale,
            "face": (far - inside * sign if inside is not None
                     else (None if gap is None else far + gap * sign)),
        })
    return rows


def dim_extension_rows(svg):
    """치수 그룹마다 (보조선, 간격, 넘김) 을 화면 실효 px 로 잰다. 순수 함수 — 감사·빌드 공용.

    반환: [(보조선 좌표, gap 또는 None, overshoot)] — gap 이 None 이면 '재는 면을 못 찾음'.
    """
    vb = _attr(svg[svg.find("<svg"):svg.find(">") + 1], "viewBox")
    if not vb:
        return []
    try:
        view_width = float(vb.split()[2])
    except (IndexError, ValueError):
        return []
    scale = FIGURE_RENDER_WIDTH / view_width if view_width else 1.0
    # 물체(형상선)는 **치수 그룹 밖의 모든 도형선**이다. 두 가지를 일부러 조심한다:
    #   ⑴ 굵기로 거르지 않는다 — 이 리포의 상자 외곽선은 1.5~1.6 이라 '가는 선 제외'로
    #      걸러 버리면 잴 면이 통째로 사라진다(실측).
    #   ⑵ `_stroked_segments` 가 아니라 `_svg_segments` 를 쓴다 — 앞의 것은 `<line>`·`<path>`
    #      만 보고 **`<rect>` 를 못 본다.** 재는 면의 대부분이 사각형이라 그대로 두면
    #      '간격 없음'만 잔뜩 나온다(첫 실행에서 실제로 그랬다).
    stripped = _strip_tagged_groups(svg, ("dim", "measure"))
    shape_segments = _svg_segments(stripped)
    # ★ 원도 재는 면이다 (열린 날 2026-08-02). `_svg_segments` 는 rect·line·path 만 본다.
    #   그래서 **입자 사이 거리**를 재는 치수(평균자유행로 λ)는 면을 못 찾고, 대신 저 뒤의
    #   상자 테두리를 면으로 잡아 `간격 20.7` 로 신고했다 — 정상 데이터를 신고하는 오탐이다
    #   (오탐이 쌓이면 다음 사람이 검사를 꺼 버린다). 축에 나란한 접선 네 줄로 등록한다.
    for m in re.finditer(r"<circle([^>]*?)/?>", stripped):
        a = m.group(1)
        try:
            cx, cy = float(_attr(a, "cx", "0")), float(_attr(a, "cy", "0"))
            r = float(_attr(a, "r", "0"))
        except (TypeError, ValueError):
            continue
        if r <= 0:
            continue
        shape_segments.extend([(cx - r, cy - r, cx + r, cy - r),
                               (cx - r, cy + r, cx + r, cy + r),
                               (cx - r, cy - r, cx - r, cy + r),
                               (cx + r, cy - r, cx + r, cy + r)])
    # ★ 굵은 stroke(관·기둥)의 재는 면은 **중심선이 아니라 외형선**이다 (열린 날 2026-08-01).
    #
    #   **무엇이 새어나갔나.** `_svg_segments` 는 굵기를 모르고 중심선만 낸다. 그대로 두면
    #   C10 이 **중심선까지의 거리**를 간격으로 재는데, C5 는 **중심선에서 시작하면 위반**이라 한다 —
    #   두 검사가 정반대를 요구해 **데이터가 어느 쪽도 만족할 수 없는 상태**가 된다.
    #   실측 `fig-ch01-q11-situation`(관 굵기 14, 중심 275 · 외형 282): AGENTS 「치수선의 끝점은
    #   재는 면의 외형선」대로 282 에서 4px 띄워 뽑은 보조선이 **간격 12.6 으로 신고**됐고,
    #   신고대로 278 로 당기면 이번엔 관을 파고들어 사용자가 지적한 그 결함으로 되돌아간다.
    #   → 굵은 선은 외형선 **두 줄**을 형상선으로 등록한다. 중심선도 남겨 둔다(C5 가 그걸 봐야 한다).
    for seg in _stroked_segments(stripped):
        half = seg[4] / 2.0
        if half < _OUTLINE_MIN_HALF:
            continue
        if abs(seg[1] - seg[3]) < 0.5:                       # 수평 — 외형선은 위·아래
            shape_segments.extend([(seg[0], seg[1] - half, seg[2], seg[3] - half),
                                   (seg[0], seg[1] + half, seg[2], seg[3] + half)])
        elif abs(seg[0] - seg[2]) < 0.5:                     # 수직 — 외형선은 좌·우
            shape_segments.extend([(seg[0] - half, seg[1], seg[2] - half, seg[3]),
                                   (seg[0] + half, seg[1], seg[2] + half, seg[3])])
    rows = []
    for start, end, body in _tagged_group_spans(svg, ("dim", "measure")):
        # body 의 절대 위치를 함께 넘긴다 — `fill` 상속을 보려면 svg 안 위치가 있어야 한다.
        heads = _filled_heads(body, svg, svg.find(body, start))
        segs = [s for s in _stroked_segments(svg[start:end]) if not _is_head_edge(s, heads)]
        mains = [s for s in segs if _dim_main_axis(s)]
        if not (mains and heads):
            continue
        # ★ 한 그룹에 치수가 여럿이면 **치수마다** 잰다 (열린 날 2026-08-02, 사용자 지적:
        #   [사용자 발화 인용 생략]).
        #
        #   아래 옛 코드는 그룹당 본선을 **하나만** 골랐다. 그러면 그 본선의 기준값(base)을
        #   지나지 않는 보조선이 `이 본선과 짝이 아닌 선` 으로 **조용히 버려진다.**
        #   실측 `fig-continuum-vs-rarefied`: 한 `<g class='dim'>` 안에 치수가 4개(L 2개 base=209 ·
        #   λ 2개 base=161)인데 base=209 를 고른 순간 **λ 보조선 4개가 통째로 검사 밖**이 됐다.
        #   그래서 L 4건은 규격이 정확한데 λ 4건은 넘김 −3 인 채로 살아남았다 —
        #   *검사에 등장하지 않는 것과 통과하는 것이 출력에서 구별되지 않는다*(이 리포의 단골 부류).
        #
        #   화살촉은 치수의 **양 끝**을 가리키므로, 화살촉을 (축, 기준값)으로 묶으면 곧 치수 하나다.
        clusters = _dim_clusters(segs, heads)
        if clusters:
            group_rows = []
            for cluster in clusters:
                group_rows.extend(_dim_rows_for_cluster(cluster, segs, shape_segments, scale))
            rows.extend(_dedupe_extension_rows(group_rows))
            continue
        # ★ 본선은 '가장 긴 선'이 아니라 **화살촉이 놓인 선**이다. 길이로 고르면 보조선이
        #   본선보다 길 때(볼트 삽화: 보조선 61 vs 본선 38) 통째로 뒤집힌다.
        centers = [_head_center(pts) for pts in heads]
        main = min(mains, key=lambda s: sum(_point_to_segment(h, s) for h in centers))
        axis = _dim_main_axis(main)           # 본선이 수평이면 보조선은 수직이다
        base = main[1] if axis == "h" else main[0]
        # ★ 화살촉 둘은 치수의 **양 끝**을 가리킨다 — 그 둘을 잇는 방향이 곧 치수 방향이다.
        #   그래서 본선을 못 고른 경우에도 축만은 화살촉으로 정할 수 있다. (열린 날 2026-08-01)
        #
        #   **무엇이 새어나갔나.** 좁은 치수는 화살촉을 바깥으로 돌리고 본선을 두 밑변 *사이*에만
        #   긋는다(정당한 제도 표기). 그러면 본선이 짧아져 `DIM_MAIN_MIN_LEN`(30) 하한에 걸려
        #   **본선으로 인식되지 못하고**, 빈 자리를 보조선이 차지해 축이 90° 뒤집힌다.
        #   그 상태에서는 **진짜 본선이 보조선으로 신고된다** — 신고대로 늘리면 화살촉을 뚫는다.
        #   실측 `fig-ch01-q11-situation`: 본선 10px → `넘김 -12.2` 로 빌드 실패(사용자 재지적으로
        #   태깅을 붙이자 비로소 드러났다. 태깅 전에는 검사가 아예 안 돌아 **결함이 둘 다 숨어 있었다**).
        #
        #   화살촉이 둘 이상이고 한 축 위에 있으면 그 배치를 **본선보다 우선해서** 믿는다.
        #   정상 삽화는 두 판정이 일치하므로 값이 바뀌지 않는다(전 챕터 실측으로 확인).
        if len(centers) >= 2:
            xs = [c[0] for c in centers]
            ys = [c[1] for c in centers]
            turned = False
            if max(xs) - min(xs) < _CENTER_TOL <= max(ys) - min(ys):
                axis, base, turned = "v", sum(xs) / len(xs), axis != "v"
            elif max(ys) - min(ys) < _CENTER_TOL <= max(xs) - min(xs):
                axis, base, turned = "h", sum(ys) / len(ys), axis != "h"
            if turned:
                # 축을 돌렸으면 **본선도 그 축의 선으로 다시 고른다.** 안 그러면 옛 축에서 고른
                # 보조선이 `main` 자리에 남아 `seg is main` 으로 **후보에서 조용히 빠진다**
                # (픽스처에서 보조선 2개 중 1개만 나왔다 — 놓친 쪽은 검사를 아예 안 받는다).
                parallel = [s for s in segs if (abs(s[0] - s[2]) < 0.5 if axis == "v"
                                                else abs(s[1] - s[3]) < 0.5)]
                main = (min(parallel, key=lambda s: sum(_point_to_segment(h, s) for h in centers))
                        if parallel else None)
        ext_axis = "v" if axis == "h" else "h"
        for seg in segs:
            if seg is main or not (0 < seg[4] <= DIM_EXTENSION_MAX_WIDTH):
                continue
            if ext_axis == "v" and abs(seg[0] - seg[2]) > 0.5:
                continue
            if ext_axis == "h" and abs(seg[1] - seg[3]) > 0.5:
                continue
            lo, hi = ((min(seg[1], seg[3]), max(seg[1], seg[3])) if ext_axis == "v"
                      else (min(seg[0], seg[2]), max(seg[0], seg[2])))
            if not (lo - _DIM_GAP_SEARCH_PX <= base <= hi + _DIM_GAP_SEARCH_PX):
                continue                      # 이 본선과 짝이 아닌 선
            # 본선에서 먼 쪽 끝이 '물체 쪽', 가까운 쪽 끝이 '넘김 쪽'이다.
            far, near = (lo, hi) if abs(lo - base) > abs(hi - base) else (hi, lo)
            sign = 1.0 if far > base else -1.0        # 본선에서 물체로 향하는 방향
            point = ((seg[0], far) if ext_axis == "v" else (far, seg[1]))
            gap = _perpendicular_hit(point, ext_axis, sign, shape_segments)
            rows.append({
                "seg": seg[:4], "axis": ext_axis, "base": base, "sign": sign,
                "far": far, "near": near, "scale": scale,
                "gap": None if gap is None else gap * scale,
                "over": (near - base) * -sign * scale,
                "face": None if gap is None else far + gap * sign,
            })
    return rows


# 보조선은 재는 면에서 치수선까지 잇는 **짧은** 선이다. 이보다 길면 기준선·형상선일 수 있어
# 자동 수정 도구가 건드리지 않는다(실측: `fig-p05-barometer` 의 180px 액면 기준선이 이 부류다).
DIM_EXTENSION_MAX_LEN = 80.0


# ★ C11. 첨자를 되돌리는 `<tspan dy>` 가 **비어 있다** (열린 날 2026-07-31 — 사용자 지적).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# **무엇이 새어나갔나.** 아래첨자는 `<tspan dy='2.5'>in</tspan>` 로 내리고
# `<tspan dy='-2.5'></tspan>` 로 되돌리는 관용구를 쓰는데, **되돌리는 tspan 이 비어 있으면
# 브라우저가 그 dy 를 적용하지 않는다** — dy 는 *글리프마다* 적용되는데 글리프가 없기 때문이다.
# 그래서 첨자 뒤의 글자가 내려간 채로 남고, 첨자가 둘이면 두 배로 내려간다.
# 화면에서는 [사용자 발화 인용 생략] 로 보인다 — 사용자가 본 그대로다.
#
# **왜 아무 검사도 못 봤나.** 이 결함은 **좌표가 아니라 렌더 규칙**이다. 데이터의 y 는 하나뿐이라
# bbox·여백·겹침 검사는 전부 통과한다. 검수 래스터(fitz)는 첨자를 원래 뭉개 그려서
# 육안으로도 구별이 안 됐다(AGENTS 가 이미 적어 둔 fitz 한계가 여기서는 **결함을 가렸다**).
#
# 고친 형태: **되돌리는 tspan 안에 뒤따르는 글자를 넣는다** — `<tspan dy='-2.5'> - E</tspan>`.
# 리포의 다른 삽화(`fig-d-piston-balance`)가 이미 그 형태다. 두 관용구가 섞여 있었다.
_EMPTY_RESET = re.compile(r"<tspan\b[^>]*\bdy='(-[\d.]+)'[^>]*>\s*</tspan>(?=\s*[^<\s])")


def empty_dy_reset_issues(ch):
    """첨자를 되돌리는 빈 `<tspan dy>` 뒤에 글자가 이어지는 자리. 순수 함수 — 테스트가 부른다."""
    out = []
    for where, blob in iter_visible_texts(ch):
        if "<text" not in blob:
            continue
        for inner in _SVG_TEXT_INNER.findall(blob):
            if _EMPTY_RESET.search(inner):
                out.append(where + ": 첨자를 되돌리는 `<tspan dy>` 가 비어 있다 — "
                           "브라우저는 글리프가 없는 tspan 의 dy 를 적용하지 않아 "
                           "**뒤따르는 글자가 내려간 채로 남는다**. 되돌리는 tspan 안에 "
                           "다음 글자를 넣을 것(`<tspan dy='-2.5'> - E</tspan>`) — "
                           "`python tools/fix_tspan_reset.py --apply`: "
                           + repr(_TAG.sub("", inner)[:40]))
    return out


def dim_extension_geometry_issues(ch):
    """간격·넘김이 규격 밖인 치수보조선. 순수 함수 — 테스트가 직접 부른다.

    건드릴 수 없는 두 부류는 검사도 하지 않는다(그래야 신고가 '고칠 수 있는 것'만 남는다):
      · 길이 80px 초과 — 기준선·형상선일 수 있어 도구·검사 모두 판단을 사람에게 넘긴다
      · 재는 면을 못 찾은 보조선 — **간격만** 면제한다. 넘김은 치수선만 있으면 정해지므로 본다.
    """
    out = []
    for fig_id, dg in iter_chapter_diagrams(ch):
        svg = str(dg.get("svg") or "")
        for row in dim_extension_rows(svg):
            seg = row["seg"]
            length = abs(seg[3] - seg[1]) if row["axis"] == "v" else abs(seg[2] - seg[0])
            if length > DIM_EXTENSION_MAX_LEN:
                continue
            bad = []
            if row["gap"] is not None and abs(row["gap"] - DIM_GAP_SCREEN_PX) > DIM_GEOM_TOL_PX:
                bad.append("간격 %.1f (규격 %g)" % (row["gap"], DIM_GAP_SCREEN_PX))
            if abs(row["over"] - DIM_OVERSHOOT_SCREEN_PX) > DIM_GEOM_TOL_PX:
                bad.append("넘김 %.1f (규격 %g)" % (row["over"], DIM_OVERSHOOT_SCREEN_PX))
            if bad:
                out.append(fig_id + ": 치수보조선 규격 밖 — " + " · ".join(bad)
                           + " · 화면 실효 px, 보조선 (%g,%g)-(%g,%g). "
                           "`python tools/fix_dim_extension.py --apply` 가 맞춰 준다"
                           % (seg[0], seg[1], seg[2], seg[3]))
    return out


def dim_extension_fixes(svg):
    """규격에 맞춘 보조선 좌표 (옛 좌표, 새 좌표) 목록. 순수 함수 — 도구·테스트가 부른다.

    고치는 것은 **양 끝점뿐**이다: 물체 쪽 끝은 `면 + 간격`, 반대쪽 끝은 `치수선 + 넘김`.
    면을 못 찾았거나(`gap is None`) 너무 긴 선은 건드리지 않는다 — 규격이 아니라 판단이 필요한 자리다.
    """
    out = []
    for row in dim_extension_rows(svg):
        seg, scale, sign = row["seg"], row["scale"], row["sign"]
        length = abs(seg[3] - seg[1]) if row["axis"] == "v" else abs(seg[2] - seg[0])
        if length > DIM_EXTENSION_MAX_LEN:
            continue
        # ★ 재는 면을 못 찾아도 **넘김은 고칠 수 있다** — 넘김은 치수선만 있으면 정해진다.
        #   면이 없다고 통째로 건너뛰면 `넘김 -12.75`(치수선에 닿지도 못한 보조선) 같은
        #   진짜 결함이 그대로 남는다. 물체 쪽 끝만 그대로 둔다.
        want_far = (row["far"] if row["gap"] is None
                    else row["face"] - DIM_GAP_SCREEN_PX / scale * sign)
        want_near = row["base"] - DIM_OVERSHOOT_SCREEN_PX / scale * sign
        # ★ **규격 안이면 건드리지 않는다.** 0.05px 차이로도 옮기게 두면 사용자가 적합하다고
        #   판정한 삽화(볼트)까지 매번 좌표가 흔들린다 — 검수 하이라이트만 늘고 얻는 것이 없다.
        gap_ok = (row["gap"] is None
                  or abs(row["gap"] - DIM_GAP_SCREEN_PX) <= DIM_GEOM_TOL_PX)
        if gap_ok and abs(row["over"] - DIM_OVERSHOOT_SCREEN_PX) <= DIM_GEOM_TOL_PX:
            continue
        if row["axis"] == "v":
            new = (seg[0], want_far, seg[2], want_near)
            old = (seg[0], row["far"], seg[2], row["near"])
        else:
            new = (want_far, seg[1], want_near, seg[3])
            old = (row["far"], seg[1], row["near"], seg[3])
        out.append((old, new))
    return out


# ★ C6. 지렛대 규칙 삽화의 건도 라벨이 좌우 반대다 (열린 날 2026-07-30, 렌더 육안 검수에서 발견).
#
# `fig-quality-mixture` 가 v_f 쪽 구간을 `1 − x (액체 질량분율)`, v_g 쪽을 `x (증기 질량분율)`
# 로 적고 있었다. **물리적으로 반대다** — v = v_f + x·v_fg 이므로
# x = (v − v_f)/(v_g − v_f) 이고, 이는 **v_f 쪽 구간의 길이 비**다.
#
# ★ 왜 아무도 못 잡았나 — 이 결함은 어떤 기존 검사에도 걸리지 않는다.
# 좌표는 정상이고 겹침도 없고 여백도 맞는다. **틀린 것은 뜻이지 기하가 아니다.**
# 게다가 같은 챕터의 본문([사용자 발화 인용 생략])과 `fig-ch03-p01`(건도 0.6 = 좌측
# 구간)은 **처음부터 옳았다** — 즉 삽화 하나만 어긋나 있었는데도 빌드가 통과했다.
# 기하만 보는 검사로는 '본문과 삽화가 서로 다른 말을 하는' 부류를 영영 못 본다.
#
# 판정: 한 삽화 안에 증기·액체 질량분율 라벨이 둘 다 있으면, **증기 쪽이 왼쪽(v_f 쪽)**이어야 한다.
# 전제 — 이 리포의 T-v·P-v 선도는 예외 없이 v 가 오른쪽으로 증가한다(전 챕터 실측).
# 그 전제가 깨지는 선도를 만들면 이 검사부터 고칠 것.
_QUALITY_VAPOR_LABEL = re.compile(r"<text[^>]*\bx='([\d.]+)'[^>]*>([^<]*증기 질량분율[^<]*)</text>")
_QUALITY_LIQUID_LABEL = re.compile(r"<text[^>]*\bx='([\d.]+)'[^>]*>([^<]*액체 질량분율[^<]*)</text>")


_ANY_XLINK = re.compile(r"\[\[ch(\d{2}):")


def _all_strings(node):
    """챕터 JSON 안의 모든 문자열. 순회 범위를 필드 목록으로 못박지 않기 위한 것이다."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _all_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _all_strings(value)


def forward_link_issues(ch):
    """**뒷 장을 가리키는 내부 링크.** 아직 안 배운 데로 보내면 '예습 지시'가 된다.

    열린 날 2026-07-30 — 사용자 지적: [사용자 발화 인용 생략], 그리고 [사용자 발화 인용 생략].

    ★ **재발이다.** 같은 판정을 이미 0장에 대해 받았고(SUBJECT.md 「0장의 링크 규칙」,
      2026-07-30) 그 근거는 [사용자 발화 인용 생략]
      이었다. 그때 **0장만 고치고 규칙을 1장 이후로 넓히지 않아** 같은 것이 ch01 에 남았다.
      부류가 아니라 인스턴스만 고친 전형적인 실패다(AGENTS 규칙 7).

    ★ 구조적 원인은 **순회 범위**다. 기존 딥링크 검사(`xlink_pat`)는 `theory.sections` 의
      `content` 만 돌았는데 이 링크는 `nextLink` 에 있었다 — 어느 검사도 그 필드를 보지 않았다.
      그래서 이 검사는 필드 목록을 쓰지 않고 **챕터 JSON 안의 모든 문자열**을 훑는다.
      '빠뜨렸다'가 아니라 *빠뜨려도 통과되는 구조*가 원인이다(규칙 7 ⑷).

    순수 함수 — 테스트가 직접 부른다(`test_forward_link_is_rejected`).
    """
    try:
        here = int(ch.get("chapterNumber"))
    except (TypeError, ValueError):
        return []
    out = []
    for text in _all_strings(ch):
        for m in _ANY_XLINK.finditer(text):
            target = int(m.group(1))
            if target > here:
                out.append("ch%02d → ch%02d 로 가는 내부 링크: 아직 안 배운 장이라 "
                           "'예습 지시'로 읽힌다. 장 이름은 **글자로만** 적을 것 "
                           "(링크는 앞 장에서 배운 것을 되짚을 때만)." % (here, target))
    return out


# ★ C31. 이해도 체크의 **답 자리**에 학생이 낼 수 없는 것을 넣지 않는다
#   (열린 날 2026-08-06, 사용자 **재지적**).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# ★ **재발이다.** 같은 판정을 이미 받았다 — `<과목>/chNN-review-inbox.md` 에 기록된
#   [사용자 발화 인용 생략](답이 장 번호)에 대해
#   [사용자 발화 인용 생략] 로 결함 판정을 냈다.
#   그때 **기계 방지를 '후보'로만 적고 구현하지 않았다.** 인스턴스는 사라졌지만 같은 것을
#   다시 써도 막는 것이 없었고, 실제로 다음 배치에서 새로 쓴 카드에 또 들어갔다.
#   '빠뜨렸다'가 아니라 **빠뜨려도 통과되는 구조**가 원인이다(AGENTS 규칙 7-⑷).
#
# 판정선은 **앞 장이냐 뒤 장이냐**다 — 규격을 '장 번호 금지'로 잡으면 정당한 인출까지 막는다.
#   ✓ 앞 장 — `"4장에서 배운 성질로 설명해 보세요"` 는 **배운 것**을 되짚는 정당한 질문이다.
#   ✗ 뒤 장 — `"6장에서 다룹니다"` 는 학생이 낼 수 없는 **편성 정보**이고 채점할 수도 없다.
#
# 자리도 가른다. 학생이 **답을 내야 하는 필드**만 본다(`prompt`·`answer`·`gradingKeywords`).
# `explanation` 은 답한 **뒤** 보는 해설이라 '뒤 장에서 다룬다'는 안내가 정당하다 —
# 본문·유도 단계·`notes` 도 같은 이유로 대상이 아니다(거기서는 안내가 독자에게 쓸모가 있다).
_CHAPTER_AHEAD = re.compile(r"(\d{1,2})\s*장(?=[에으로의과와까부터,.\s]|$)")
_TOC_BLANK = re.compile(r"(?:_{2,}\s*[장절]|몇\s*[장절]|어느\s*[장절])")
CHECK_ANSWER_FIELDS = ("prompt", "answer", "gradingKeywords")


def _check_answer_field(trail):
    """이해도 체크에서 **학생이 답을 내야 하는** 필드인가. 리스트 첨자를 떼고 본다."""
    if "/comprehensionChecks[" not in trail:
        return None
    field = re.sub(r"\[\d+\]$", "", trail.rsplit("/", 1)[-1])
    return field if field in CHECK_ANSWER_FIELDS else None


def review_diagram_needs_reason(ref):
    """C35 — 복습 카드가 **삽화를 끌어오면** 사유를 적었는가 (신설 2026-08-06).

    열린 날 2026-08-06 · 사용자 지적: [사용자 발화 인용 생략].

    새어나간 것 — ch04 §1 의 복습 카드가 ch02 의 `fig-energy-balance-ledger`(질량 통로가
    그려진 **검사체적** 장부 그림)를 끌어왔다. 4장은 **밀폐계로 범위를 좁히는 장**이라
    그 장이 하려는 말의 **반례 그림이 첫 화면**에 있었는데, 아무 검사도 걸리지 않았다.

    ★ '그 삽화가 이 장의 범위에 맞는가'는 **장의 범위를 알아야 하는 판정**이라 기계가 직접
      볼 수 없다. 그래서 기계는 **사람이 판정한 흔적**을 대신 강제한다 — 비우는 것이 기본이고
      넣는 쪽이 근거를 댄다. 선례: 삽화 `### 사양`(verify_workorder 3-D)·
      `card-overlap-verdicts.json` — 판정할 수 없는 자리에서는 판정의 기록을 요구한다.
    """
    return bool(ref.get("diagramIds") or []) and not str(ref.get("diagramWhy") or "").strip()


def check_answer_scope_issues(ch):
    """이해도 체크의 답 자리에 든 '아직 안 배운 장'·'목차를 묻는 빈칸'.

    순수 함수 — 테스트가 직접 부른다(`test_check_answer_stays_in_scope`).
    """
    try:
        here = int(ch.get("chapterNumber"))
    except (TypeError, ValueError):
        here = None
    out = []
    for trail, text in iter_visible_texts(ch):
        field = _check_answer_field(trail)
        if not field:
            continue
        if here is not None:
            for m in _CHAPTER_AHEAD.finditer(text):
                if int(m.group(1)) > here:
                    out.append(
                        trail + ": 이해도 체크의 답 자리에 **아직 안 배운 장**을 넣었다 — "
                        + repr(m.group(0)) + " (학생이 생각해서 낼 수 있는 것이 아니라 자료의"
                        " 편성 정보다. 채점 대상이 될 수 없으니 이 절에서 답할 수 있는 것만"
                        " 남길 것. 안내가 필요하면 본문이나 explanation 에 둔다): "
                        + repr(text[:60]))
        if _TOC_BLANK.search(text):
            out.append(
                trail + ": 이해도 체크가 **자료의 목차**를 묻는다 — "
                + repr(_TOC_BLANK.search(text).group(0))
                + " (몇 장·몇 절에서 배우나는 학습 내용이 아니고 맞혀도 이해가 늘지 않는다."
                " 그 자리의 물리를 묻도록 바꿀 것): " + repr(text[:60]))
    return out


# ★ C9. **삽화(SVG) 안에서** 분수를 텍스트로 조판했다 (열린 날 2026-07-30 — 같은 부류 3회차 재발).
#
# 사용자 원문: [사용자 발화 인용 생략]
# 앞선 두 번은 인박스의 `W-9. 분수를 또 텍스트로 — 몇 번째인지 모를 반복`,
# `V-11. 분수를 텍스트로 쓴 것 — 반복 부류`.
#
# **구조적 원인 — 산문 검사가 SVG를 명시적으로 제외한다.** `plain_fraction_issues` 는
# `MATH_NATIVE_KEYS` 에 `/svg` 를 넣어 **삽화 글자를 통째로 건너뛴다.** 그건 그 검사에서는
# 옳다(SVG 안에 `\(…\)` 를 넣을 수 없으니 같은 처방을 낼 수 없다). 그러나 그 결과
# **삽화의 분수를 보는 검사가 0개**가 됐고, 지적받은 인스턴스만 고치는 일이 세 번 반복됐다.
# '빠뜨렸다'가 아니라 *빠뜨려도 통과되는 구조*가 원인이다(AGENTS 규칙 7-⑷).
#
# **검사를 그동안 못 만든 이유도 실측으로 드러났다** — 슬래시의 대부분이 **단위**라
# 순진하게 잡으면 오탐이 쏟아진다(전 챕터 실측 30건 중 27건이 단위). 그래서 미뤄졌고
# 미뤄진 채 세 번 돌아왔다. 가르는 자를 아래처럼 못박으면 미룰 이유가 없어진다.
#
# 판정 — 슬래시 **왼쪽이 기호**(단위 등록부에 없는 것)이고 **오른쪽이 기호나 숫자**면 분수다.
#   · `P/ρ` · `F/a` · `PV / RT` · `V²/2` → 분수(위반)
#   · `9.81 m/s²` · `1000 kg/m³` · `kJ/(kmol·K)` · `[kN/m³]` → 왼쪽이 단위 → 통과
#   · `켈빈 / 섭씨` · `2 h/일` → 한글이 끼면 나눗셈이 아니라 **구분자**다 → 통과
#   · 앞에 수치가 붙은 것(`45 m/s`)은 등록부에 없는 단위여도 통과 — 이중 안전망.
#
# ★ 인박스가 적어 둔 기준은 "**양쪽 다** 기호"였지만, 그대로 쓰면 `V²/2`(분모가 숫자)가
#   빠진다. 사용자가 지적한 것은 [사용자 발화 인용 생략] 이고 `V²/2` 의 분모도 글자다 —
#   기준을 좁게 적은 쪽이 부류를 덜 덮은 것이라 넓혔다. 실측: 좁은 기준 3건 → 넓힌 기준 6건,
#   늘어난 3건은 전부 진짜 분수였다(오탐 0).
#
# 고치는 법은 **`python tools/svg_fraction.py`** 가 찍어 주는 조각을 쓴다. 손으로 좌표를
# 잡으면 삽화마다 분수선 굵기·중심선이 갈라지고, 그 갈라짐이 다음 지적이 된다.
_SVG_TEXT_INNER = re.compile(r"<text\b[^>]*>(.*?)</text>", re.S)
_TAG = re.compile(r"<[^>]+>")
_HANGUL = re.compile(r"[가-힣ㄱ-ㅎㅏ-ㅣ]")
_COMBINING = re.compile(r"[̀-ͯ]")
_LETTERS = re.compile(r"[^\W\d_]+")
# 첨자·도(°)·구두점은 낱말을 가르지 않는다 — `m³` 는 여전히 `m`(단위)이고 `V₁` 은 `V`(기호)다.
_NOT_LETTER = str.maketrans("", "", "⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉°.,''")
# 슬래시 양옆의 '한 낱말'을 자르는 구분자 — 연산자·괄호·구두점.
# ★ **자릿수 쉼표는 구분자가 아니다** (2026-08-04, R-44 · 분수 부류 11회째).
#   사용자: [사용자 발화 인용 생략]
#   쉼표를 무조건 구분자로 보면 `586,400` 이 `400` 으로 잘리고, 그러면 **앞에 남은 `586,` 을
#   수치 안전망(`_NUM_BEFORE`)이 '수치가 앞에 붙었으니 단위다'로 읽어** 통째로 빠져나간다.
#   R-9(숫자÷숫자)를 닫은 뒤에도 같은 챕터에서 또 난 이유가 이것이다 — 인스턴스가 아니라
#   **자의 형태 인식**이 좁았다. 숫자 사이의 쉼표만 낱말 안에 남긴다(`m, g` 는 그대로 구분자다).
_SIDE_WORD = (r"(?:[^\s=,;:+×·()\[\]{}<>−\-–—…→⟹≈≡≥≤]|(?<=\d),(?=\d))+")
_LEFT_WORD = re.compile(_SIDE_WORD + r"\s?$")
_RIGHT_WORD = re.compile(r"^\s?(" + _SIDE_WORD + r")")
_NUM_BEFORE = re.compile(r"\d[\d.,]*\s*$")
# 유니코드 **분수 문자** — 이것만 막는다. 위첨자·아래첨자는 AGENTS 가 쓰라고 한 표기라 대상이 아니다.
#   U+00BC~BE `¼ ½ ¾` · U+2150~215F `⅐ ⅑ ⅒ ⅓ ⅔ ⅕…⅞`
_VULGAR_FRACTION = re.compile(r"[¼-¾⅐-⅟]")
# 단위 등록부. **애매한 것은 일부러 뺐다** — V(볼트/부피)·A(암페어/면적)·T(테슬라/온도)·
# R(뢴트겐/기체상수)·F(패럿/힘) 는 이 리포에서 물리량 기호로만 쓰인다. 등록부에 넣으면
# `F/a` 같은 진짜 분수가 조용히 통과한다(안전한 쪽 = 못 알아본 단위는 위 수치 안전망이 받는다).
# ★ `g`(그램)를 뺐다 (2026-07-31). 넣어 두면 `mg`(밀리그램)가 단위가 되어 **`mg/A`**
#   (무게를 면적으로 나눈 진짜 분수, 피스톤 힘평형)가 통째로 빠진다 — ch01 에서 4곳이 그렇게
#   샜다. 빼도 손해가 없다: `kJ/kg`·`kg/m³`·`g/cm³` 는 **반대쪽이 단위**라 그쪽에서 걸러지고,
#   `500 g/L` 같은 표기는 앞의 수치 안전망이 받는다.
# ★ `K`(켈빈)도 뺐다 (2026-08-02, 사용자 지적 8회째). `g` 를 뺀 것과 **완전히 같은 이유**다 —
#   존재·유일성 정리의 상계 상수 `K`(\(|f| \le K\))가 켈빈으로 읽혀 **`b/K` 6곳이 통째로
#   빠졌다**(본문 2 · 이해도 체크 2 · 삽화 2). 한 문장 안에 `\(\frac{b}{K}\)` 와 `b/K` 가
#   나란히 있었는데도 검사는 조용했다. 빼도 손해가 없다: `kJ/kg·K`·`J/K` 는 **반대쪽이 단위**라
#   그쪽에서 걸러지고, `300 K` 는 앞의 수치 안전망(`_NUM_BEFORE`)이 받는다.
#   ★ 남는 위험은 정직하게 적어 둔다 — 이 등록부는 여전히 **이름으로** 판정하므로
#   `C`(적분상수)·`N`(법선력)·`W`(일)·`L`(길이) 처럼 한 글자 기호와 겹치는 단위가 더 있다.
#   근본 해법은 단위를 `\mathrm{}` 로 조판해 **로만체/이탤릭으로 가르는 것**이고(SI 관례와도 같다),
#   그건 전 과목 표기 마이그레이션이라 별건으로 남긴다(원장 「아직 기계로 막지 못하는 부류」).
UNIT_BASES = frozenset(("m", "s", "N", "J", "W", "Pa", "L", "mol", "h", "min",
                        "bar", "atm", "rad", "Hz", "C", "Btu", "lbm", "ft", "psi", "hp"))
# ★ `d`(데시)를 접두어에서 뺐다 (2026-08-02, 동역학). `g`·`K` 를 뺀 것과 **같은 부류**이고,
#   이번에는 한 글자 기호가 아니라 **연산자**와 겹쳤다: `d` + 단위 = 미분이다.
#   `ds`(데시초)·`dW`(데시와트)·`dh`(데시시간)·`dm`(데시미터)·`dN`·`dJ`·`dL` 이 전부
#   등록부를 통과했고, 그래서 **`ds/dt` 같은 평문 미분이 분수 검사에서 통째로 빠졌다** —
#   `_is_unit_token` 이 참이면 세 검사(산문·수식 안·삽화)가 나란히 건너뛴다.
#   동역학은 `ds`·`dv`·`dt` 가 기본 문법인 과목이라 이 구멍이 정면으로 걸린다(실측: 12장
#   본문·유도·문풀에 `a\,ds = v\,dv` 계열이 22곳).
#   빼도 손해가 없다 — 앞의 두 선례와 같은 논리다: 진짜 데시 단위(`dm³/s`·`dL/min`)는
#   **반대쪽이 단위**라 그쪽에서 걸러지고, `500 dL` 은 앞의 수치 안전망(`_NUM_BEFORE`)이 받는다.
#   ★ 곁가지로 `tools/fix_unit_notation.py` 가 `ds` 22곳을 **자동 감싸기 대상**으로 찍고 있었다.
#   `--apply` 를 돌렸으면 미분이 `\mathrm{ds}`(로만체 단위)로 바뀌어 데이터가 망가진다 —
#   도구가 이 등록부를 그대로 쓰므로 여기 한 곳을 고치면 그 함정도 같이 닫힌다.
# ★★ **슬래시에서만 애매한 단위** (신설 2026-08-06 — 가운데점 검사 C36 이 열었다).
#   위 등록부에서 `g`·`K`·`A`·`V`·`F` 가 빠진 이유는 [사용자 발화 인용 생략] 가 아니라
#   **슬래시 문맥에서 물리량과 구별되지 않아서**다(`F/A` 는 힘/면적이지 패럿/암페어가 아니다).
#   즉 그 판정은 등록부의 성질이 아니라 **연산자의 성질**이었는데, 목록에서 통째로 빼는
#   방식이라 다른 연산자에서도 단위가 아닌 것이 되어 버렸다.
#   ★ 가운데점에서는 애매하지 않다 — `kg·K`·`N·m` 은 누가 봐도 단위의 곱이다. 그래서
#     문맥별로 무엇을 더 볼지를 여기서 가른다: **슬래시는 `UNIT_BASES` 만, 가운데점은 둘 다.**
#     목록을 복제하는 것이 아니라 **하나를 문맥으로 나누는 것**이라 자가 갈리지 않는다
#     (등록부가 둘로 갈렸던 2026-08-02 사고의 처방을 지킨다).
#   ★ 분수 검사 쪽 동작은 **한 글자도 바뀌지 않는다** — 그쪽은 계속 `UNIT_BASES` 만 본다.
#   ★ `Ω`(옴)를 여기 넣었다 (2026-08-06, 기계재료가 열었다). 저항률의 단위 `Ω·m` 이
#     **누가 봐도 단위의 곱인데** 등록부에 없어 C36 이 전수 신고했다(ch01 문풀·연습·유도 7곳).
#     `UNIT_BASES` 가 아니라 이쪽에 두는 이유는 위 설계 그대로다 — 슬래시에서는 `Ω` 가
#     각속도·입체각과 겹칠 수 있어 분수 검사의 동작을 **한 글자도 바꾸지 않는 쪽**을 고른다.
#     가운데점에서는 애매하지 않다: 반대쪽도 단위여야 면제되므로 `Ω·m`·`Ω·s` 만 통과하고
#     `Ω·r`(각속도 × 반지름)은 그대로 걸린다.
UNIT_BASES_AMBIGUOUS_IN_SLASH = frozenset(("g", "K", "A", "V", "F", "Ω"))
UNIT_PREFIXES = "kMGmμcn"
# 수학 함수 이름 — 3글자여도 낱말이 아니라 기호다(`A/cos θ` 는 분수다).
MATH_FUNCS = frozenset(("sin", "cos", "tan", "cot", "sec", "csc", "ln", "log", "exp"))
# ★ 미분 `dX` 는 단위도 낱말도 아니라 **기호**다 (2026-08-02, 위 `d` 접두어 제거와 한 짝).
#   접두어에서 `d` 를 빼자 `ds` 가 이번에는 *2글자 소문자 = 낱말*(`in/out`·`LHV/HHV` 를
#   거르려고 둔 갈래)로 떨어져 **여전히 통과했다.** 등록부 한 곳만 고치고 끝냈으면
#   `math_slash_fraction_issues`(수식 안)만 닫히고 산문·삽화는 그대로 새는, 자가 갈린 상태가 된다.
#   `dm³/s`·`dL/min` 은 **반대쪽이 단위**라 여전히 통과한다(쌍 판정이 받는다).
_DIFFERENTIAL = re.compile(r"^d[A-Za-zα-ωΑ-Ω]$")


# ★★ 단위 판정 방식 — 과목이 고른다 (신설 2026-08-02, 평문 분수 8회째의 근본 처방).
#
#   "names"  (기본) — 이름으로 판정한다. 지금까지의 동작이고, **선언하지 않은 과목은
#                     동작이 한 글자도 안 바뀐다.** 전역 승격이 남의 과목 빌드를 멈춘
#                     2026-08-02 사고를 되풀이하지 않기 위한 기본값이다.
#   "mathrm"        — `\mathrm{}` 로 표시한 것만 단위로 본다(SI 조판 관례: 단위는 로만체,
#                     변수는 이탤릭). 이름 판정을 끄므로 `K`·`C`·`N`·`W` 가 물리량 기호로
#                     쓰인 자리가 **더 이상 단위로 오인되지 않는다.**
#
# 선언은 `data/<과목>/index.json` 의 `unitNotation`. 전환 조사·자동 감싸기는
# `tools/fix_unit_notation.py`. 공통 코드는 어느 과목이 무엇을 골랐는지 모른다.
UNIT_NOTATION_MODES = ("names", "mathrm")
_unit_notation = "names"


def set_unit_notation(mode):
    """이 챕터를 검사하는 동안의 단위 판정 방식을 정한다. `lint_chapter` 가 부른다."""
    global _unit_notation
    if mode not in UNIT_NOTATION_MODES:
        raise ValueError("unitNotation 은 " + " / ".join(UNIT_NOTATION_MODES)
                         + " 중 하나여야 한다: " + repr(mode))
    _unit_notation = mode


def unit_notation_of(ch_path):
    """그 과목의 `index.json` 이 선언한 방식. 없으면 기본값 `names`."""
    idx = os.path.join(os.path.dirname(ch_path), "index.json")
    if not os.path.isfile(idx):
        return "names"
    try:
        with open(idx, encoding="utf-8") as fh:
            return json.load(fh).get("unitNotation") or "names"
    except (OSError, json.JSONDecodeError):
        return "names"


def is_mathrm_unit(word):
    r"""`\mathrm{...}` 로 표시된 단위인가 — 두 방식 모두에서 참이다."""
    return "\\mathrm{" in (word or "")


def _is_unit_token(token):
    if _unit_notation == "mathrm":
        # 이름으로는 판정하지 않는다. 단위는 `\mathrm{}` 로 표시되고,
        # 그 판정은 호출부(`fraction_side_kind`·`math_slash_fraction_issues`)가 먼저 한다.
        return False
    if token in UNIT_BASES:
        return True
    return len(token) > 1 and token[0] in UNIT_PREFIXES and token[1:] in UNIT_BASES


def fraction_side_kind(word):
    """슬래시 한쪽이 무엇인가 — `hangul`/`number`/`unit`/`word`/`symbol`. 순수 함수(테스트 대상).

    ★ `word`(낱말)는 산문으로 넓히면서 생긴 갈래다 (2026-07-31). 삽화 글자에는 거의 없지만
      산문에는 **낱말 쌍 슬래시**가 흔하다 — `in/out 첨자` · `intensive/extensive` ·
      `LHV/HHV` · `isothermal/isobaric`. 이건 나눗셈이 아니라 **또는**이라는 뜻이라
      분수로 조판하면 오히려 틀린다. 실측: 산문 45건 중 12건이 이 부류였다.

    가르는 자 — **물리량 기호는 짧다.**
      · 글자 토큰이 3글자 이상이면 낱말·약어다(`out`·`LHV`·`extensive`).
      · 2글자인데 전부 소문자면 낱말이다(`in`·`cv`). 한 글자 소문자는 기호다(`v`·`t`·`a`).
      · 단, `_` 첨자·결합문자·수학 함수 이름은 길어도 기호다(`ṁ_steam`·`cos`).
    """
    if not word:
        return "number"                       # 비어 있으면 판단 근거가 없다 → 통과 쪽
    # ★★ **괄호 묶음도 한쪽이다** (2026-08-13, 분수 부류 **12회째** — 아래 `text_fraction_hit` 주석이 정본).
    #   `(𝒱₂² - 𝒱₁²)/2` 의 왼쪽은 낱말이 아니라 **묶음**이다. 묶음을 못 읽으면 이 자는
    #   [사용자 발화 인용 생략] 며 손을 떼고, 그 자리를 대신 보던 것이 모양 열거뿐이었다.
    if word.startswith("(") and word.endswith(")"):
        return _bracket_group_kind(word[1:-1])
    if is_mathrm_unit(word):
        return "unit"                         # 저자가 로만체로 **선언한** 단위 — 이름을 안 본다
    if _HANGUL.search(word):
        return "hangul"
    if _COMBINING.search(word):
        return "symbol"                       # ṁ·V̇ 처럼 점이 붙은 것은 단위가 아니라 물리량이다
    # ★ 첨자를 **떼고** 글자를 센다. 떼지 않으면 `m³` 가 등록부에 없는 낱말이 되어
    #   `m³/s`(단위)가 분수로 신고된다 — 오탐 하나가 검사를 죽인다.
    tokens = _LETTERS.findall(word.translate(_NOT_LETTER))
    if not tokens:
        return "number"
    if all(_is_unit_token(t) for t in tokens):
        return "unit"
    if all(_DIFFERENTIAL.match(t) for t in tokens):
        return "symbol"                       # `ds`·`dt`·`dθ` — 미분이지 낱말이 아니다
    if "_" in word or any(t.lower() in MATH_FUNCS for t in tokens):
        return "symbol"                       # `ṁ_steam` · `A/cos θ`
    longest = max(len(t) for t in tokens)
    if longest > 2 or (longest == 2 and word.islower()):
        return "word"
    return "symbol"


# ★ 묶음 안을 낱말로 자르는 구분자 — 연산자·쉼표·공백. 괄호는 이미 벗겨진 뒤다.
#   `·` 를 여기 넣는 이유: `1 kg·m/s²` 를 `kg`·`m`·`s²` 로 갈라야 **단위 묶음**으로 읽힌다.
_GROUP_SPLIT = re.compile(r"[\s+\-−–—×÷*/·,;=<>≤≥]+")


def _bracket_group_kind(inner):
    """괄호 묶음 하나가 무엇인가 — 안쪽 낱말들의 판정을 합친다 (순수 함수).

    합치는 순서가 곧 안전 순서다: 한글이 섞이면 조판 대상이 아니고(`(단열 과정)/…`),
    물리량 기호가 하나라도 있으면 그 묶음은 **양(quantity)** 이다. 낱말·단위·수치만으로
    이루어진 묶음은 단위 묶음(`(1 kg·m/s²)`)이라 나눗셈 조판이 아니다.
    """
    kinds = [fraction_side_kind(w.strip("()")) for w in _GROUP_SPLIT.split(inner) if w.strip("()")]
    for kind in ("hangul", "symbol", "word", "unit"):
        if kind in kinds:
            return kind
    return "number"


def _bracket_before(before):
    """슬래시 **왼쪽**에 맞붙은 괄호 묶음 `(...)`, 없으면 빈 문자열 (순수 함수)."""
    s = before.rstrip()
    if not s.endswith(")"):
        return ""
    depth = 0
    for i in range(len(s) - 1, -1, -1):
        if s[i] == ")":
            depth += 1
        elif s[i] == "(":
            depth -= 1
            if depth == 0:
                return s[i:]
    return ""


def _bracket_after(after):
    """슬래시 **오른쪽**에 맞붙은 괄호 묶음 `(...)`, 없으면 빈 문자열 (순수 함수)."""
    s = after.lstrip()
    if not s.startswith("("):
        return ""
    depth = 0
    for i, c in enumerate(s):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return s[:i + 1]
    return ""


_PARTICLE = re.compile(r"^([^가-힣]+)[가-힣]+$")


def _strip_particle(word):
    """`A를`·`ρ와` 처럼 기호에 붙은 **조사**를 떼어 낸다 (순수 함수).

    산문으로 넓히면서 드러난 사각지대다(2026-07-31). `mg/A를 얻는다` 의 오른쪽은 `A를` 이고,
    한글이 섞였다는 이유로 '구분자'로 분류돼 통째로 빠졌다 — 실제로는 분수인데 **한국어라서**
    검사 밖이었다. 낱말 전체가 한글이면(`섭씨`·`일`) 그대로 두어 구분자 판정을 살린다.
    """
    m = _PARTICLE.match(word or "")
    return m.group(1) if m else word


def text_fraction_hit(text):
    """`P/ρ`·`V²/2` 처럼 **글자로 쓴 분수**면 `'왼쪽/오른쪽'`, 아니면 None (순수 함수).

    ★ 삽화와 산문이 **같은 자**를 쓴다 (2026-07-31 확장). 처음에는 삽화 전용으로 만들었는데,
      같은 부류가 산문에도 그대로 있었다(실측 `P/ρ`·`V²/2` 등). 판정을 두 벌 두면 반드시
      갈라진다 — 이 리포에서 이미 캡션 자·치수 그룹 자가 그렇게 갈렸다.
      처방만 다르다: 삽화는 `tools/svg_fraction.py`, 산문은 `\\(\\frac{}{}\\)`.

    ★★ **유니코드 분수 문자도 여기서 잡는다** (2026-08-04, R-33 · 분수 부류 10회째).
      사용자: [사용자 발화 인용 생략]
      아홉 번의 분수 정리를 살아남은 이유가 **자의 형태 인식**이었다 — 산문·수식·삽화의 세 검사가
      전부 `/` 를 찾는데 `½`(U+00BD)는 **슬래시가 없는 한 글자**라 셋 다 통과했다.
      게다가 글리프가 그럴듯해서 사람 검수도 지나쳤다. '빠뜨렸다'가 아니라 **빠뜨려도
      통과되는 구조**다(규칙 7-⑷).
      ★ 유니코드를 통째로 막으면 안 된다 — AGENTS 는 평문 필드에 위첨자(`m³`·`V₂²`)를
      **쓰라고** 한다. 금지 대상은 **분수 문자만**이고, 분수 사선(U+2044)은 슬래시로 취급한다.

    ★★★ **괄호 분자** (열린 날 2026-08-13 · 분수 부류 **12회째**).
      사용자: [사용자 발화 인용 생략] — 화면(ch02 유도 `variables`): `운동에너지 변화 (kJ) = m(𝒱₂² - 𝒱₁²)/2`.

      **순회는 멀쩡했다 — 이 자가 그 자리에서 손을 뗐다.** `_SIDE_WORD` 는 괄호를 구분자로
      보므로 분자가 `)` 로 끝나면 왼쪽 낱말이 **빈 문자열**이 되고, 2026-08-01 에 넣은
      [사용자 발화 인용 생략] 가 거기서 판정을 포기했다. 그 자리를 대신 보던 것은
      `FRACTION_SHAPES` ⑴ 하나뿐인데, 그 모양은 빼기를 **유니코드 `−` 로만** 알아서
      데이터가 ASCII `-` 를 쓴 순간 어느 자도 그 문자열을 보지 않았다(실측: 그 값을 넣고
      빌드하면 통과한다). 즉 **판정의 사각지대를 「모양 열거」가 메우고 있었고, 열거는
      빠뜨려도 통과된다** — 규칙 7-⑷ 가 말하는 *빠뜨려도 통과되는 구조* 다.

      그래서 손을 떼는 대신 **묶음을 한쪽으로 읽는다**(`_bracket_group_kind`). 2026-08-01 의
      오탐(`(1 kg·m/s²)/(1 N)`)은 그대로 통과한다 — 묶음 안이 전부 단위·수치라 `unit` 이다.
      **연산자에 기대지 않으므로** `-`·`−`·`×` 중 무엇을 쓰든 같은 판정이 나온다.
    """
    vulgar = _VULGAR_FRACTION.search(text)
    if vulgar:
        return vulgar.group(0)
    for pos, ch_at in enumerate(text):
        if ch_at not in "/⁄":
            continue
        before, after = text[:pos], text[pos + 1:]
        lm = _LEFT_WORD.search(before)
        rm = _RIGHT_WORD.search(after)
        left = _strip_particle(lm.group(0).strip() if lm else "")
        right = _strip_particle(rm.group(1) if rm else "")
        # ★ 낱말이 안 잘리면 **맞붙은 괄호 묶음**을 그쪽 한쪽으로 삼는다 (2026-08-13, 위 주석).
        left = left or _bracket_before(before)
        right = right or _bracket_after(after)
        # ★ 그래도 한쪽이 비어 있으면 분수가 아니다 (2026-08-01). 빈 문자열은 글자가 없어
        #   `fraction_side_kind` 가 `"number"` 로 판정하는데, 숫자 쌍을 허용한 뒤로는 그게 오탐이 됐다.
        if not left or not right:
            continue
        if _NUM_BEFORE.search(before[:lm.start()] if lm else before):
            continue                      # `9.81 m/s²` — 수치가 앞에 붙으면 단위다
        lk, rk = fraction_side_kind(left), fraction_side_kind(right)
        # ★ 2026-08-01 — 왼쪽에 `number` 를 허용한다. 예전에는 여기서 `lk not in ("symbol","word")`
        #   로 잘라 **왼쪽이 숫자면 아래 쌍 판정에 닿지도 못했다**(`8.5² / 2`). 단위를 거르는 일은
        #   위의 `_NUM_BEFORE`(수치가 앞에 붙으면 단위)가 이미 하므로, 여기서는 통과시키고
        #   **무엇이 분수인가는 아래 쌍 규칙 한 곳에서만** 정한다 — 조건이 두 군데로 갈리면
        #   이번처럼 한쪽만 고쳐도 안 걸린다.
        if lk not in ("symbol", "word", "number") or rk not in ("symbol", "word", "number"):
            continue
        # ★ 판정은 **쌍**으로 한다 (2026-07-31, 두 번째 조정).
        #   한쪽씩 보면 `mg/A`(mg 는 두 글자 소문자 = 낱말꼴)가 빠지고, 낱말 쪽을 허용하면
        #   `in/out` 이 들어온다. 실제 기준은 [사용자 발화 인용 생략] 다 —
        #   낱말 쌍(`in/out`·`LHV/HHV`)은 나눗셈이 아니라 '또는'이라 분수로 조판하면 틀린다.
        #
        # ★ 2026-08-01 — **숫자 ÷ 숫자를 여기에 더한다** (사용자 4회째 지적:
        #   [사용자 발화 인용 생략]).
        #   위 조건만으로는 **양쪽이 다 숫자면 통째로 빠졌다** — `8.5² / 2`·`80000/3600`·`890/1059.5`
        #   가 전부 검사 밖이었다. 낱말 쌍을 거르려고 넣은 조건에 숫자 분수가 같이 걸려 나간 것이다.
        #   `9.81 m/s²` 같은 단위는 위쪽 `_NUM_BEFORE` 가 이미 걸러내므로 여기까지 오지 않는다.
        if "symbol" not in (lk, rk) and (lk, rk) != ("number", "number"):
            continue
        return left + "/" + right
    return None


# ★ 아래첨자 tspan — `dy` 가 **양수**인 것만 첨자로 본다 (신설 2026-08-01).
#   기준선으로 되돌리는 런은 `dy='-4'` 라 여기 걸리지 않는다. 그 런에는 본문이 들어가므로
#   함께 지우면 진짜 분수를 놓친다.
_SUBSCRIPT_TSPAN = re.compile(
    r"<tspan[^>]*\bdy\s*=\s*['\"]\s*\+?\d[^'\"]*['\"][^>]*>.*?</tspan>", re.S)


def _fraction_hit_in(text):
    """분수 판정 하나로 묶기 — 산문 검사와 **같은 자**를 쓴다(갈리면 둘이 다른 것을 잰다)."""
    return text_fraction_hit(text) or next(
        (m.group(0).strip() for rx in FRACTION_SHAPES
         for m in [rx.search(text)] if m), None)


def svg_text_fraction_issues(ch):
    r"""삽화 글자 안에 평문으로 조판된 분수. 순수 함수 — 테스트가 직접 부른다.

    ★ **아래첨자 안의 슬래시는 나눗셈이 아니다** (2026-08-01, 동역학 ch12 에서 열림).
      상대운동의 표준 표기 `v_{B/A}`('A 에서 본 B')를 삽화에 적으면
      `<text>v<tspan dy='4'>B/A</tspan></text>` 가 되는데, 이 검사는 tspan 을 펴서 보므로
      `vB/A` 를 분수로 읽어 **정상 표기를 신고**했다. 2026-08-01 `_filled_heads`(치수 화살촉)와
      같은 부류다 — *검사가 데이터의 정당한 표현형을 못 본다.*

      그래서 판정을 두 번 한다: 첨자를 편 글(진짜 분수를 놓치지 않으려고)과 **첨자 내용을 지운
      본문**. 둘 다에서 걸릴 때만 신고한다. 슬래시가 첨자 안에만 있으면 통과다.
      **완화가 아니라 정정이라는 것은 회귀가 잠근다** — `V²/2`·`P/ρ` 는 여전히 걸리고,
      첨자와 본문에 걸친 `v<tspan>x</tspan>/2` 도 걸린다.
    """
    out = []
    for where, blob in iter_visible_texts(ch):
        if "<text" not in blob:
            continue
        for inner in _SVG_TEXT_INNER.findall(blob):
            text = _TAG.sub("", inner)        # <tspan> 첨자까지 펴서 본다
            # 괄호+연산자·미분 같은 나머지 모양은 산문 검사와 **같은 자**로 본다.
            hit = _fraction_hit_in(text)
            # 첨자를 **빈 문자열**로 지운다(공백이 아니라) — 공백을 남기면 `v_x/2` 처럼
            # 첨자 뒤에 이어지는 진짜 분수가 좌변과 끊어져 빠져나간다(회귀가 이 케이스를 잠근다).
            if hit and not _fraction_hit_in(_TAG.sub("", _SUBSCRIPT_TSPAN.sub("", inner))):
                hit = None                    # 슬래시가 아래첨자 안에만 있었다 — 첨자 표기다
            if hit:
                out.append(where + ": 삽화 안에서 분수를 글자로 썼다 — " + repr(hit)
                           + " → 분자·분수선·분모로 조판할 것. "
                           "`python tools/svg_fraction.py --cx … --axis … --num … --den … "
                           "--fs …` 가 조각을 찍어 준다 (단위 `m/s²`는 대상이 아니다): "
                           + repr(text.strip()[:44]))
    return out


def lever_rule_label_side_issues(ch):
    """건도 라벨이 지렛대 규칙과 반대 쪽에 붙은 자리. 순수 함수 — 테스트가 부른다."""
    out = []
    for fig_id, dg in iter_chapter_diagrams(ch):
        svg = str(dg.get("svg") or "")
        vapor = _QUALITY_VAPOR_LABEL.search(svg)
        liquid = _QUALITY_LIQUID_LABEL.search(svg)
        if not (vapor and liquid):
            continue
        if float(vapor.group(1)) > float(liquid.group(1)):
            out.append(fig_id + ": 건도 라벨이 좌우 반대다 — 증기 질량분율 x 는 "
                       "**v_f 쪽(왼쪽) 구간**이다. v = v_f + x·v_fg 이므로 "
                       "x = (v − v_f)/(v_g − v_f) 이고 그것이 왼쪽 구간의 길이 비다 "
                       "(AGENTS 규칙 4 — 수치·관계는 독립 검산). 증기 x=%g, 액체 x=%g"
                       % (float(vapor.group(1)), float(liquid.group(1))))
    return out


# ★ C18·C19. 선도(축이 있는 그래프)의 **물리적 형태**를 보는 검사 (열린 날 2026-08-02).
#
# 사용자 원문: [사용자 발화 인용 생략] ·
#   [사용자 발화 인용 생략] ·
#   [사용자 발화 인용 생략] · [사용자 발화 인용 생략]
#
# **무엇이 새어나갔나 (ch03 좌표 실측).**
#   · T-v 정압선이 과열증기에서 **내려간다** — 열을 줄수록 온도가 떨어진다는 그림이었다.
#   · P-v 정온선이 압축액에서 **올라간다** — v 가 느는데 압력이 오른다.
#   · 상변화 수평선이 포화액선에서 57px 안쪽에서 시작해 포화증기선 39px 앞에서 끝난다.
#     *상변화는 포화액에서 포화증기까지 일어난다* 는 그 그림의 요지가 그림에서 부정된다.
#
# ★ 왜 기존 검사가 하나도 못 봤나 — 삽화 검사는 전부 **기하·조판**(겹침 F1·F4·F6 · 여백 ·
#   글자 크기 · 화살촉 · 치수선 C10)이라 '이 곡선이 물리적으로 가능한가'는 본 적이 없다.
#   좌표는 정상이고 겹침도 없고 여백도 맞는다 — **틀린 것은 뜻이지 기하가 아니다**(C6 과 같은 뿌리).
#   AGENTS 「아직 기계로 막지 못하는 부류」에 [사용자 발화 인용 생략] 으로 적혀 있던,
#   **알려진 사각지대**였다.
#
# ★ 그러나 과목 지식을 검사에 박지 않는다(AGENTS 「공통 도구에 과목별 사실을 박지 않는다」).
#   [사용자 발화 인용 생략] 은 열역학 사실이라 공통 코드가 알면 안 된다. 그래서
#   **불변식은 데이터가 선언하고, 검사는 선언과 좌표가 맞는지만 본다:**
#
#     <path data-shape='rising'  …>   x 가 늘 때 화면 y 가 늘지 않는다(값이 증가)
#     <path data-shape='falling' …>   x 가 늘 때 화면 y 가 줄지 않는다(값이 감소)
#     <path data-shape='free'    …>   불변식 없음 — 돔·상경계처럼 사람이 판단하는 곡선
#     <path … data-flat-on='<id>'>    수평 구간의 **양 끝**이 그 id 곡선 위에 있어야 한다
#                                     (닿을 곡선이 없으면 `none`)
#
#   선언이 없으면 통과가 아니라 **신고**다(기본값을 안전한 쪽으로 뒤집기). 다른 과목의
#   v-t 선도·응력-변형률 선도도 같은 어휘를 그대로 쓴다 — 과목 이름이 코드에 없다.
#
# 승격은 과목별로 한다 — `data/<과목>/index.json` 의 `strictChapters.plot`.
# 공통 목록을 비워 두는 이유는 `subject_strict_chapters` 독스트링에 있다: 파일명 기준 승격은
# 남의 과목 빌드를 멈춘다(이 어휘를 아직 안 붙인 과목이 곧바로 error 더미를 받는다).
# **이름 규약:** `<KEY>_STRICT_CHAPTERS` ↔ index.json 의 `strictChapters.<key>` —
# `test_strict_promotion_covers_all_chapters` 가 그 규약으로 둘을 맞춰 본다.
PLOT_STRICT_CHAPTERS = set()
# 화살표 크기 규격(`checks_svg.ARROW_HEAD_*`)의 승격 목록 — 공통은 비워 둔다(같은 이유).
ARROW_STRICT_CHAPTERS = set()
# 삽화 없는 문항의 사유 선언(C32) 승격 목록 — 공통은 비워 둔다(같은 이유).
NO_DIAGRAM_STRICT_CHAPTERS = set()


# ★ 「언제 삽화를 넣나」의 기준 — 사용자 승인 2026-08-04 ([사용자 발화 인용 생략]).
#   ⑴ 기하·배치가 조건인 문항(경사·높이차·경계 위치·연결 순서) → **필수**
#   ⑵ 비교가 논점인 문항(두 상태·두 계) → **필수**
#   ⑶ 정의·분류만 묻는 문항(열이냐 일이냐, 부호 규약) → **선택**(계 경계를 그려야 하면 필수)
#   ⑷ 수치 대입만 하는 문항 → **불필요**
#   기계는 ⑴~⑷ 를 못 읽는다. 그래서 **판정 자체가 아니라 판정이 기록됐는지**를 강제한다 —
#   `verify_workorder.py` 3-D 가 삽화 사양에 대해 하는 일과 같은 형태다.
NO_DIAGRAM_MIN_LEN = 8      # 한 줄짜리 알리바이("불필요")를 사유로 치지 않는다


# ★ C37 — **이론에 삽화가 한 장도 없는 챕터** (열린 날 2026-08-06, 동역학 ch13).
#
# 무엇이 새어나갔나: `ef3dfe2` 가 ch13 이론 8절 + 유도 2를 세웠는데 `"diagrams"` 키가
# 파일 전체에 **0개**였다(같은 과목 ch12 는 11개). 그런데 **빌드가 통과했다.**
#
# 왜 통과했나 — 이 리포에는 *삽화를 어떻게 그리나* 의 검사가 서른 개 넘게 있는데
# *이론에 삽화가 있기는 한가* 를 보는 자가 하나도 없었다. 밀도 검사(DENSITY_MAX_GAP)가
# 그 자리를 지키는 줄 알기 쉬우나, 목록·표를 flow-break 로 인정하므로 **절마다 불릿만
# 있으면 삽화 0장으로도 통과한다.** 문항 쪽에는 C32(`noDiagramReason`)가 있는데
# 이론 쪽에는 대응물이 없었다 — 같은 부류의 반쪽만 닫혀 있었던 셈이다.
#
# 판정은 C32 와 같은 형태다: 기계는 *어느 절에 그림이 필요한지* 못 읽으므로
# **판정이 기록됐는지**만 강제한다. 그림이 정말 필요 없는 챕터(과목 개요 등)는
# 챕터 최상위에 `noTheoryDiagramReason` 을 적어 닫는다.
THEORY_FIGURE_MIN_SECTIONS = 3   # 절이 둘 이하면 아직 뼈대라 묻지 않는다
NO_THEORY_DIAGRAM_MIN_LEN = 8    # 한 줄짜리 알리바이("불필요")를 사유로 치지 않는다


def theory_figure_presence_issues(ch):
    """이론 전체에 삽화가 0장인데 사유 선언도 없는 챕터. 순수 함수 — 빌드·회귀가 함께 쓴다."""
    sections = ((ch.get("theory") or {}).get("sections") or [])
    if len(sections) < THEORY_FIGURE_MIN_SECTIONS:
        return []
    if any(s.get("diagrams") for s in sections):
        return []
    reason = str(ch.get("noTheoryDiagramReason") or "").strip()
    where = "theory: 절 " + str(len(sections)) + "개인데 삽화가 0장"
    if not reason:
        return [where + " — `noTheoryDiagramReason` 이 없다. 의도인지 누락인지 "
                "구별할 수 없다(밀도 검사는 목록·표를 flow-break 로 세므로 이 자리를 "
                "안 지킨다). 그림이 필요 없는 챕터면 그 이유를 챕터 최상위에 적을 것"]
    if len(reason) < NO_THEORY_DIAGRAM_MIN_LEN:
        return [where + ": `noTheoryDiagramReason` 이 너무 짧다 (%d자) — "
                "왜 이론에 그림이 필요 없는지 적을 것" % len(reason)]
    return []


def no_diagram_reason_issues(ch):
    """삽화도 없고 없는 이유도 없는 문항. 순수 함수 — 빌드·회귀가 함께 쓴다."""
    out = []
    for prob in (ch.get("problems") or []):
        if prob.get("diagrams"):
            continue
        reason = str(prob.get("noDiagramReason") or "").strip()
        where = "problems[" + str(prob.get("id", "?")) + "]"
        if not reason:
            out.append(where + ": 삽화가 없는데 `noDiagramReason` 이 없다 — "
                       "의도인지 누락인지 구별할 수 없다. 기준 ⑴기하·배치 ⑵비교 는 **필수**, "
                       "⑶정의·분류 는 선택, ⑷수치 대입만 은 불필요")
        elif len(reason) < NO_DIAGRAM_MIN_LEN:
            out.append(where + ": `noDiagramReason` 이 너무 짧다 (%d자) — "
                       "어느 기준에 해당하는지 적을 것" % len(reason))
    return out


def _figure_view_width(svg):
    """viewBox 폭 — 화면 실효 px 로 환산하는 자. 못 읽으면 0(검사가 스스로 비활성)."""
    head = svg[svg.find("<svg"):svg.find(">") + 1]
    vb = _attr(head, "viewBox")
    try:
        return float(vb.split()[2])
    except (AttributeError, IndexError, ValueError):
        return 0.0
PLOT_AXIS_MIN_LEN = 80.0        # 이보다 짧은 L자는 축으로 보지 않는다
PLOT_LABEL_OUT_TOL = 1.5        # 축선에 걸친 라벨은 신고하지 않는다(완전히 밖인 것만 본다)
PLOT_CURVE_MIN_SPAN = 0.30      # 그림 폭의 이 비율 이상을 지나가면 '선도 곡선'으로 본다
PLOT_MONOTONE_TOL = 1.2         # 베지에를 펴는 오차만큼은 되돌아가도 봐준다
PLOT_FLAT_DY = 0.6              # 이보다 평평한 구간이 '수평 구간'
PLOT_FLAT_MIN_LEN = 20.0        # 그보다 짧으면 수평 '구간'이 아니라 잔떨림이다
PLOT_ON_CURVE_TOL = 4.0         # 끝점이 곡선 위라고 볼 거리
# 축 밖에 있어야 **정상**인 글자 — `class` 로 선언한다(<g> 상속도 본다).
#   axis-name  축 이름(`T`·`P (kPa)`)            — 화살촉 끝 바깥이 규격이다
#   tick       눈금 라벨(`417`·`0.2`·`V₁ = …`)   — AGENTS 「라벨의 기준 위치」가 축 바깥을 규정한다
#   fig-note   그림 밑 캡션·부속 도해의 글자
PLOT_TEXT_OUTSIDE_CLASSES = ("axis-name", "tick", "fig-note")
PLOT_SHAPE_VALUES = ("rising", "falling", "free")


def _plot_axes(svg):
    """L자 축에서 (그림영역 사각형, 축 path 위치). 없으면 (None, None). 순수 함수.

    사각형은 `(x0, y_top, x1, y_bottom)` — 세로축 위끝과 가로축 오른끝이 경계다.
    닫힌 사각형(4변)은 축이 아니므로 선분 3개까지만 본다.

    ★ **채운 도형은 축이 아니다** (2026-08-13, 고체역학 ch11 쐐기 삽화에서 열림).
    직각 쐐기 `M180 70 L180 190 L340 190 Z` 는 닫히면서 선분이 셋이고 그중 하나가
    세로·하나가 가로라 **L자 축과 서명이 완전히 같다.** 그래서 자유물체도 하나가
    통째로 「선도」로 오인돼 축 밖 라벨·곡선 형태 선언 신고가 쏟아졌다.
    축선은 언제나 **획만 있고 칠이 없다** — 저자가 `fill` 로 선언한 것을 읽어 가른다
    (`class='dim'`·`\\mathrm{}` 와 같은 처방: 이름으로 추측하지 않고 선언을 본다).
    `fill` 을 안 적은 path 는 예전 그대로 판정한다 — 열린 축 path 가 그 형태다.
    """
    for m in re.finditer(r"<path([^>]*?)/?>", svg):
        dstr = _attr(m.group(1), "d")
        if not dstr:
            continue
        fill = _effective(svg, m.start(), m.group(1), "fill")
        if fill is not None and str(fill).strip().lower() not in ("", "none", "transparent"):
            continue
        segs = [s for s in _path_polyline(dstr)
                if _distance((s[0], s[1]), (s[2], s[3])) > 1]
        if not 2 <= len(segs) <= 3:
            continue
        vert = [s for s in segs
                if abs(s[2] - s[0]) < 0.5 and abs(s[3] - s[1]) >= PLOT_AXIS_MIN_LEN]
        horiz = [s for s in segs
                 if abs(s[3] - s[1]) < 0.5 and abs(s[2] - s[0]) >= PLOT_AXIS_MIN_LEN]
        if len(vert) != 1 or len(horiz) != 1:
            continue
        v, h = vert[0], horiz[0]
        corner_x, corner_y = v[0], max(v[1], v[3])          # 세로축의 아래 끝 = 원점
        if abs(h[1] - corner_y) > 1.5 or abs(min(h[0], h[2]) - corner_x) > 1.5:
            continue                                        # 두 축이 원점에서 만나야 한다
        return (corner_x, min(v[1], v[3]), max(h[0], h[2]), corner_y), m.start()
    return None, None


def plot_axes_rect(svg):
    """그림 영역 사각형만 돌려준다 — 테스트·도구가 부르는 얼굴."""
    return _plot_axes(svg)[0]


def _text_class(svg, pos, attrs):
    return str(_effective(svg, pos, attrs, "class", "") or "")


def plot_label_outside_issues(ch):
    """축 사각형 **밖**으로 나간 데이터 라벨. 순수 함수 — 테스트가 직접 부른다.

    축 이름(`T`·`v`)과 그림 밑 캡션은 밖에 있는 것이 정상이라 `class` 로 선언해 면제한다.
    면제를 선언으로 만든 이유: 자동으로 봐주면(짧은 글자·축 끝 근처 등) 진짜 결함이
    같은 규칙으로 빠져나간다 — `압축액` 은 세 글자였고 축 바로 왼쪽에 있었다.
    """
    out = []
    for fig_id, dg in iter_chapter_diagrams(ch):
        svg = str(dg.get("svg") or "")
        rect = plot_axes_rect(svg)
        if not rect:
            continue
        x0, y_top, x1, y_bottom = rect
        attrs_at = {m.start(): m.group(1) for m in re.finditer(r"<text([^>]*)>", svg)}
        for it in _svg_texts(svg):
            cls = _text_class(svg, it["pos"], attrs_at.get(it["pos"], ""))
            if any(mark in cls for mark in PLOT_TEXT_OUTSIDE_CLASSES):
                continue
            bx0, by0, bx1, by1 = _text_bbox(it)
            tol = PLOT_LABEL_OUT_TOL
            side = ("세로축 왼쪽" if bx1 < x0 - tol else
                    "가로축 오른쪽 끝 밖" if bx0 > x1 + tol else
                    "세로축 위끝 밖" if by1 < y_top - tol else
                    "가로축 아래" if by0 > y_bottom + tol else None)
            if side:
                out.append(fig_id + ": 데이터 라벨이 " + side + "에 있다 — "
                           + repr(it["s"][:20]) + " (글자 상자 x %.0f~%.0f · y %.0f~%.0f, "
                           "그림 영역 x %.0f~%.0f · y %.0f~%.0f). 영역 이름·곡선 이름은 "
                           "축 안에 둘 것. 축 이름·캡션이면 class='axis-name'·'fig-note' 로 "
                           "선언한다" % (bx0, bx1, by0, by1, x0, x1, y_top, y_bottom))
    return out


def _polyline_points(segs):
    """선분 목록을 점 목록으로. 왼→오른쪽으로 읽도록 방향을 맞춘다."""
    pts = [(segs[0][0], segs[0][1])] + [(s[2], s[3]) for s in segs]
    if pts[-1][0] < pts[0][0]:
        pts.reverse()
    return pts


def _flat_runs(pts):
    """수평 구간 [(시작점, 끝점)] — 화면 y 가 거의 같은 채로 이어지는 구간."""
    runs, start = [], 0
    for i in range(1, len(pts)):
        flat = abs(pts[i][1] - pts[i - 1][1]) <= PLOT_FLAT_DY
        if not flat:
            if i - 1 > start:
                runs.append((pts[start], pts[i - 1]))
            start = i
    if len(pts) - 1 > start:
        runs.append((pts[start], pts[-1]))
    return [(a, b) for a, b in runs if abs(b[0] - a[0]) >= PLOT_FLAT_MIN_LEN]


def plot_curve_shape_issues(ch):
    """선도 곡선의 선언(`data-shape`·`data-flat-on`)과 좌표가 어긋난 자리. 순수 함수.

    검사 대상은 **축이 있는 삽화의, 그림 폭 30% 이상을 지나가는 획(stroke) 곡선**이다.
    채우기만 한 path(음영)와 화살촉처럼 짧은 조각은 대상이 아니다.
    """
    out = []
    for fig_id, dg in iter_chapter_diagrams(ch):
        svg = str(dg.get("svg") or "")
        rect, axis_pos = _plot_axes(svg)
        if not rect:
            continue
        x0, y_top, x1, y_bottom = rect
        curves, by_id = [], {}
        # ★ `<line>` 도 곡선이다. 처음에는 path 만 봤는데, 그러면 지렛대 규칙 삽화의
        #   **수평선이 검사 밖**이었다 — 그 선의 두 끝이 포화선에 닿아야 한다는 것이
        #   정확히 이 검사가 막으려는 부류인데, 마크업이 <line> 이라는 이유로 빠져나갔다.
        elements = [(m.start(), m.group(1), _path_polyline(_attr(m.group(1), "d") or ""))
                    for m in re.finditer(r"<path([^>]*?)/?>", svg)]
        elements += [(m.start(), m.group(1),
                      [tuple(float(_attr(m.group(1), k, "0"))
                             for k in ("x1", "y1", "x2", "y2"))])
                     for m in re.finditer(r"<line([^>]*?)/?>", svg)]
        leaders = leader_spans(svg)
        for pos, attrs, segs in sorted(elements):
            if not segs:
                continue
            pid = _attr(attrs, "id")
            if pid:
                by_id[pid] = segs
            if pos == axis_pos:
                continue
            if in_leader(leaders, pos):
                continue        # 지시선은 선도 곡선이 아니다 — 규격은 `leader_line_issues`
            if _effective(svg, pos, attrs, "stroke") in (None, "none"):
                continue                       # 획이 없는 음영·화살촉은 곡선이 아니다
            xs = [s[0] for s in segs] + [s[2] for s in segs]
            ys = [s[1] for s in segs] + [s[3] for s in segs]
            # 그림 영역 **밖에** 통째로 있는 선(밑에 붙인 막대 도해·밑줄)은 선도 곡선이 아니다.
            if (max(xs) < x0 or min(xs) > x1 or max(ys) < y_top or min(ys) > y_bottom):
                continue
            # 가로로 짧아도 **세로로 길면** 선도 곡선이다(P-T 융해선은 거의 수직이다).
            span = max((max(xs) - min(xs)) / max(1.0, x1 - x0),
                       (max(ys) - min(ys)) / max(1.0, y_bottom - y_top))
            if span < PLOT_CURVE_MIN_SPAN:
                continue
            curves.append((attrs, segs))
        for attrs, segs in curves:
            where = fig_id + ": " + repr(_attr(attrs, "id") or (_attr(attrs, "d") or "")[:28]
                                         or "line (%.0f,%.0f)-(%.0f,%.0f)" % segs[0])
            shape = _attr(attrs, "data-shape")
            if shape not in PLOT_SHAPE_VALUES:
                out.append(where + " — 선도 곡선인데 형태 선언이 없다. "
                           "data-shape='rising|falling|free' 를 붙일 것 "
                           "(rising = x 가 늘 때 값이 증가, falling = 감소, "
                           "free = 불변식 없음)")
                continue
            # 여러 조각(M 이 둘 이상)인 path 는 점을 이어 붙일 수 없다 — 조각 사이를 이으면
            # 있지도 않은 되돌아감이 생긴다. 형태를 재려면 곡선마다 path 를 나눠야 한다.
            if len(_path_subpaths(_attr(attrs, "d") or "M")) > 1:
                if shape != "free":
                    out.append(where + " — 한 path 에 곡선이 여러 조각이라 형태를 잴 수 없다. "
                               "곡선마다 path 를 나눌 것 (잴 필요가 없으면 data-shape='free')")
                continue
            pts = _polyline_points(segs)
            if shape != "free":
                worst, at = 0.0, None
                for a, b in zip(pts, pts[1:]):
                    back = (b[1] - a[1]) if shape == "rising" else (a[1] - b[1])
                    if back > worst:
                        worst, at = back, (a, b)
                if worst > PLOT_MONOTONE_TOL:
                    out.append(where + " — data-shape='%s' 인데 좌표가 반대다: "
                               "(%.0f,%.0f)→(%.0f,%.0f) 에서 화면 y 가 %.1f px %s "
                               "(%s 곡선은 x 가 늘 때 %s)"
                               % (shape, at[0][0], at[0][1], at[1][0], at[1][1], worst,
                                  "늘었다" if shape == "rising" else "줄었다",
                                  shape, "값이 증가해야" if shape == "rising"
                                  else "값이 감소해야"))
            runs = _flat_runs(pts)
            target = _attr(attrs, "data-flat-on")
            if not runs:
                continue
            if target is None:
                out.append(where + " — 수평 구간이 있는데 어디에 닿아야 하는지 선언이 없다. "
                           "data-flat-on='<곡선 id>' (닿을 곡선이 없으면 'none')")
                continue
            if target == "none":
                continue
            if target not in by_id:
                out.append(where + " — data-flat-on='%s' 인데 그 id 의 path 가 없다" % target)
                continue
            for a, b in runs:
                for pt in (a, b):
                    gap = min(_point_to_segment_distance(pt[0], pt[1], *s)
                              for s in by_id[target])
                    if gap > PLOT_ON_CURVE_TOL:
                        out.append(where + " — 수평 구간의 끝점 (%.0f,%.0f) 이 "
                                   "'%s' 곡선에서 %.0f px 떨어져 있다 (허용 %g). "
                                   "구간이 그 곡선에서 시작해 그 곡선에서 끝나야 한다"
                                   % (pt[0], pt[1], target, gap, PLOT_ON_CURVE_TOL))
    return out


# ★ C33·C34 — `data-shape='free'` 는 **검사 면제가 아니라 판정 대기**다 (열린 날 2026-08-06).
#
# 사용자: [사용자 발화 인용 생략]
#
# **이번 재발의 정확한 구멍.** C19 를 만들 때 돔·상경계처럼 단조성이 없는 곡선을 `free` 로
# 열어 두고 주석에 [사용자 발화 인용 생략] 이라 적었다. 그런데 **그 판단을
# 했는지 아무도 묻지 않는다.** 그래서 포화 돔은 2026-08-02 에도, 그 뒤로도 아무 기록 없이
# 통과했다 — 실제로는 좌 145 : 우 180px 로 거의 대칭이었는데(물은 120°C 에서 1 : 435) 검사는
# 조용했고, 결국 **사용자가 발견해야만 드러나는 구조**가 그대로 남아 있었다.
#
# 고친 형태는 이 리포가 이미 쓰는 것이다(`problem-originality-verdicts.json`·
# `card-overlap-verdicts.json`): **판정을 파일에 남겨야 닫힌다.**
#
#     data/<과목>/figure-shape-verdicts.json
#     { "verdicts": { "<삽화 id>::<곡선 id>": {"by": …, "date": …, "basis": …} } }
#
# 과목 지식(*어떤 형상이 옳은가*)은 그 파일이 갖고 공통 코드는 **기록의 존재만** 본다 —
# C18·C19 가 불변식을 데이터에 맡긴 것과 같은 분업이다.
#
# 그리고 판정이 *글로만* 남으면 다음 사람이 좌표를 고쳐도 기록은 그대로다. 그래서
# **선언한 비율을 좌표로 되잰다**(C34): `data-apex-ratio`(꼭짓점이 그림 폭의 몇 지점인가)와
# `data-leg-ratio`(오른쪽 다리 폭 ÷ 왼쪽 다리 폭). 둘 다 좌표만 재면 나오는 값이라
# 공통 검사가 할 수 있고, *얼마여야 하는가* 는 데이터가 선언한다.
SHAPE_VERDICT_FIELDS = ("by", "date", "basis")
APEX_RATIO_TOL = 0.03
LEG_RATIO_TOL = 0.45


def figure_shape_verdicts(ch_path):
    """`data/<과목>/figure-shape-verdicts.json` 의 판정 기록. 없으면 빈 사전."""
    path = os.path.join(os.path.dirname(ch_path), "figure-shape-verdicts.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return (json.load(fh).get("verdicts") or {})
    except (OSError, ValueError, AttributeError):
        return {}


def _free_curve_geometry(segs):
    """(꼭짓점 비율의 분자·분모, 좌 다리 폭, 우 다리 폭) — 화면 좌표만으로 잰다."""
    pts = _polyline_points(segs)
    apex = min(pts, key=lambda q: q[1])
    xs = [q[0] for q in pts]
    return apex[0], min(xs), max(xs)


def plot_shape_declaration_issues(ch, ch_path):
    """`free` 곡선의 판정 기록(C33)과 선언한 형상 비율(C34). 순수 함수는 아니다 —
    과목 폴더의 판정 파일을 읽는다(`card_overlap_verdicts` 와 같은 방식)."""
    out = []
    verdicts = figure_shape_verdicts(ch_path)
    for fig_id, dg in iter_chapter_diagrams(ch):
        svg = str(dg.get("svg") or "")
        rect, axis_pos = _plot_axes(svg)
        if not rect:
            continue
        x0, _y_top, x1, _y_bottom = rect
        leaders = leader_spans(svg)
        for m in re.finditer(r"<path([^>]*?)/?>", svg):
            attrs = m.group(1)
            if _attr(attrs, "data-shape") != "free" or in_leader(leaders, m.start()):
                continue
            if m.start() == axis_pos:
                continue        # 축 자체는 곡선이 아니다
            # 여러 조각으로 된 path 는 C19 도 형태를 재지 않는다(조각 사이를 이으면 없는
            # 되돌아감이 생긴다). 잴 수 없는 것에 판정을 요구하면 id 만 늘고 기록은 빈다.
            if len(_path_subpaths(_attr(attrs, "d") or "M")) > 1:
                continue
            pid = _attr(attrs, "id") or ""
            # ★ 변경점 리뷰 빌드는 같은 삽화를 `review-chNN-` 접두어로 한 벌 더 만든다.
            #   접두어를 그대로 열쇠에 쓰면 **판정을 두 벌 적어야** 하고, 하나는 반드시 잊는다.
            key = re.sub(r"^review-ch\d+-", "", fig_id) + "::" + pid
            where = fig_id + ": " + repr(pid or (_attr(attrs, "d") or "")[:24])
            # ★ **포화 돔은 형상 비율을 선언해야 한다** (열린 날 2026-08-06, 사용자 지적
            #   두 번째: [사용자 발화 인용 생략]). 3절 선도 셋은 물성에서 생성해 `data-apex-ratio` 를 선언하고
            #   아래 C34 가 실측과 대조하는데, 4절 `qm-dome` 은 **선언이 아예 없어서**
            #   손으로 그린 좌우 대칭 베지어가 그대로 통과했다 — 검사가 있는데 그 검사를
            #   **발동시키는 선언이 없으면 없는 것과 같다**(`class='dim'`·`leader` 와 같은 형태).
            #   판정은 id 로 한다: 이 리포의 포화 돔은 예외 없이 `…-dome` 이다.
            if pid.endswith("-dome") and _attr(attrs, "data-apex-ratio") is None:
                out.append(where + " — 포화 돔인데 data-apex-ratio 선언이 없다. 선언이 없으면"
                                   " 형상 대조(C34)가 아예 발동하지 않아 손으로 그린 돔이"
                                   " 그대로 통과한다. 생성기로 뽑고 실측 비율을 적을 것")
            if not pid:
                out.append(where + " — data-shape='free' 인데 id 가 없다. 판정을 기록할 수 "
                                   "없으므로 id 를 붙일 것")
            else:
                rec = verdicts.get(key)
                if not isinstance(rec, dict):
                    out.append(where + " — data-shape='free' 는 검사 면제가 아니라 **판정 "
                               "대기**다. data/<과목>/figure-shape-verdicts.json 에 "
                               + repr(key) + " 를 " + "·".join(SHAPE_VERDICT_FIELDS)
                               + " 와 함께 적을 것")
                else:
                    miss = [f for f in SHAPE_VERDICT_FIELDS if not str(rec.get(f) or "").strip()]
                    if miss:
                        out.append(where + " — 판정 기록에 " + "·".join(miss) + " 가 비었다")
            segs = _path_polyline(_attr(attrs, "d") or "")
            if not segs:
                continue
            apex_x, min_x, max_x = _free_curve_geometry(segs)
            declared_apex = _attr(attrs, "data-apex-ratio")
            if declared_apex is not None:
                actual = (apex_x - x0) / max(1.0, x1 - x0)
                if abs(actual - float(declared_apex)) > APEX_RATIO_TOL:
                    out.append(where + " — data-apex-ratio='%s' 인데 실측 %.3f "
                               "(허용 ±%g). 꼭짓점 x=%.1f · 그림 영역 %.0f~%.0f"
                               % (declared_apex, actual, APEX_RATIO_TOL, apex_x, x0, x1))
            declared_leg = _attr(attrs, "data-leg-ratio")
            if declared_leg is not None and apex_x - min_x > 1.0:
                actual = (max_x - apex_x) / (apex_x - min_x)
                if abs(actual - float(declared_leg)) > LEG_RATIO_TOL:
                    out.append(where + " — data-leg-ratio='%s' 인데 실측 %.2f (허용 ±%g). "
                               "좌 다리 %.1fpx · 우 다리 %.1fpx"
                               % (declared_leg, actual, LEG_RATIO_TOL,
                                  apex_x - min_x, max_x - apex_x))
    return out


def xlink_fragment(target_id, target_child):
    """데이터의 [[chNN:target/child]]가 만들어내는 해시 조각 — 뷰어 fmtOne과 같은 규칙."""
    if target_id.startswith("fig-"):
        return target_id
    return target_id + "-" + target_child if target_child else "theory-" + target_id


# ★ 요약본은 근거가 아니다 (열린 날 2026-07-28, 사용자 지적).
#
# 사용자 원문: [사용자 발화 인용 생략]
#
# **무엇이 새어나갔나.** 과목 자료 폴더에는 사용자가 만든 **장별 요약 이미지**가 있다
# (기계재료 `N장 요약.png` · 동역학 `N장 요약.jpg`). 읽기 쉽고 구조가 정리돼 있어서
# 1차 근거처럼 쓰기 쉬운데, **그것은 학습자 본인의 정리물이라 틀릴 수 있다.**
# 실제로 기계재료 ch01 `sec-selection` 은 강의노트에 없는 '재료 선택 3기준'을
# 요약본에서 가져다 쓰고, sourceRef 에는 확인하지도 않은 교재 절을 적었다(규칙 11 위반).
# (뒤늦게 책을 열어보니 3기준 자체는 맞았다 — 그러나 **맞았다는 것과 확인했다는 것은 다르다.**)
#
# **왜 문서로는 못 막나.** 규칙 2는 "교재 대조 또는 오답로그·사용자 제보가 근거여야 한다"고만
# 하고, 요약본이 어느 쪽인지 말하지 않는다. 그래서 성실하게 적어도 통과한다.
# → 요약본을 **단서**로 쓰는 것은 허용하되, **혼자서는 출처가 될 수 없게** 기계로 강제한다.
SUMMARY_HINT = "요약"
# 1차 근거로 인정하는 것: 수업 자료(강의노트·ppt·슬라이드)와 교재(책 이름은 pitfall 등록부 재사용).
PRIMARY_SOURCE_HINTS = ("강의노트", "슬라이드", "ppt", "교재", "본문", "p.", "쪽",
                        "오답로그", "사용자 제보", "자작")


def summary_only_source(ref):
    """출처가 **요약본에만** 기대고 있으면 사유 문자열, 아니면 None (순수 함수 — 테스트 대상).

    `1장 요약` 처럼 요약본을 언급하면서 1차 근거(강의노트 쪽·교재 쪽 등)를 함께 대지 않으면 잡는다.
    """
    text = str(ref or "")
    if SUMMARY_HINT not in text:
        return None
    if any(h in text for h in PRIMARY_SOURCE_HINTS):
        return None
    return ("출처가 요약본뿐이다 — 요약본은 학습자 본인의 정리물이라 근거가 아니다. "
            "강의노트 쪽수나 교재 쪽수로 **직접 확인한 근거**를 함께 적을 것 (AGENTS 규칙 2·11): "
            + repr(text[:60]))


def iter_source_refs(ch):
    """챕터 안의 (위치, sourceRef) 를 전 컬렉션에서 흘린다.

    **컬렉션을 열거하지 않는다** — theory 만 순회하다 유도 11건을 놓친 선례(2026-07-21)와
    같은 사각지대를 만들지 않기 위해, 트리 전체를 훑어 `sourceRef` 키를 찾는다.
    """
    def walk(node, trail):
        if isinstance(node, dict):
            label = node.get("id") or trail
            for key, value in node.items():
                if key == "sourceRef" and isinstance(value, str):
                    yield str(label), value
                else:
                    for hit in walk(value, str(label) + "/" + str(key)):
                        yield hit
        elif isinstance(node, list):
            for i, value in enumerate(node):
                for hit in walk(value, trail + "[" + str(i) + "]"):
                    yield hit
    return walk(ch, "root")


def viewer_deep_link_pattern(template_src):
    """뷰어가 인식하는 딥링크 해시 정규식을 템플릿 소스에서 읽어온다.

    열린 날: 2026-07-23 — 딥링크 앵커를 fig-*로 넓혔는데 뷰어의 착지 핸들러는
    'theory-'로 시작하는 해시만 알고 있었다. ch02의 챕터 간 링크 5건 중 4건이
    **탭 전환도 스크롤도 복귀 칩도 없이** 그냥 열리기만 했고, 빌드는 통과했다.

    새어나간 이유: 앵커 형식이 데이터·빌드·뷰어 세 곳에 각각 적혀 있었고,
    셋이 어긋나는지 아무도 대조하지 않았다. 그래서 뷰어를 **정본**으로 삼아
    빌드가 그 정규식을 직접 읽어 대조한다(마커: DEEP_LINK_HASH).
    """
    m = re.search(r"DEEP_LINK_HASH\s*=\s*/(.+?)/\s*;", template_src)
    return re.compile(m.group(1)) if m else None


# ★★ C45. 화면에서 **첨자로 안 내려가는 첨자** (열린 날 2026-08-13).
#
# 사용자: 문항 조건에 **`𝒱_out`** 이 **밑줄째** 나온다.
#
# **규칙도 검사도 있었는데 이 자리를 아무도 안 봤다.** AGENTS 「알려진 함정」이
# [사용자 발화 인용 생략]
# 라고 못 박고, `lint_chapter` 의 `scan_subscripts` 가 그 등록부를 강제한다. 그런데 그 검사는
# **필드만** 묻는다 — [사용자 발화 인용 생략] 가 참이면 거기서 **손을 뗀다.**
# 화면이 첨자를 실제로 내리는 조건은 필드만이 아니라 **밑글자**이기도 하다: 산문 렌더러는
# 밑글자를 `[Δ∆]?[A-Za-zα-ωΑ-Ω]` 로 받는데, 2026-08-12 에 속도 기호를 필기체로 옮기면서
# 데이터에 들어온 `𝒱`(U+1D4B1)는 **BMP 밖**이라 그 문자류에 없다. 그래서 등록된 필드에
# 얌전히 들어 있는데도 밑줄이 날것으로 남는다.
#
# ★ 이것은 같은 날 닫은 **괄호 분수와 같은 부류**다 — 자가 [사용자 발화 인용 생략] 라고
#   손을 떼는 조건이 **화면의 실제 조건과 어긋나** 있었다. 분수는 「한쪽이 비면 통과」,
#   이쪽은 「등록된 필드면 통과」였다.
#
# ★ 그래서 문자류를 여기 **복사하지 않는다.** 뷰어의 그 정규식을 **읽어 와서 그대로 돌린다**
#   (선례 `viewer_deep_link_pattern`). 두 곳에 적으면 반드시 갈라지고, 뷰어가 astral 을 받게
#   고쳐지는 날 이 검사는 **아무것도 안 고쳐도** 같이 따라간다.
_TPL_PROSE_SUBSCRIPT = re.compile(
    r"\.replace\(/(\([^()]*\)_[^/]*)/g,\s*'<span class=\"sym\">\$1<sub>\$2</sub>")
# 첨자로 **보이는** 것 전부. 뷰어가 소비하고 남은 자리만 보므로 넓게 잡아도 오탐이 안 된다.
_ANY_SUBSCRIPT = re.compile(r"(\S)_(\{[^{}\s]{1,24}\}|[A-Za-z0-9α-ωΑ-Ω]{1,12})")
# 화면에 안 나가는 식별자·편집 메모. 여기의 `_` 는 첨자가 아니라 이름의 일부다.
SUBSCRIPT_RENDER_EXEMPT = ("/id", "/href", "/source", "/sourceRef", "/sourcePages",
                           "/supplementNotes", "/changeNote", "/answerVerifier")


def viewer_prose_subscript_patterns(template_src):
    """산문 렌더러가 **실제로** 첨자로 내리는 꼴 [정규식] — 정본은 뷰어 템플릿이다."""
    out = []
    for body in _TPL_PROSE_SUBSCRIPT.findall(template_src or ""):
        try:
            out.append(re.compile(body))
        except re.error:
            continue                      # JS 전용 문법이면 건너뛴다(대조가 목적이지 파서가 아니다)
    return out


def unrendered_subscript_issues(ch, patterns):
    """뷰어가 첨자로 못 내리는 `X_sub`. 순수 함수 — 테스트가 직접 부른다.

    `patterns` 는 `viewer_prose_subscript_patterns()` 가 템플릿에서 읽어 온 것이다.
    빈 목록이면 **통과가 아니라 신고**다 — 정본을 못 읽었다는 것은 *검사가 없다*는 뜻이고,
    그 상태를 조용히 통과시키면 이 검사의 0건이 '없다'가 아니라 '안 봤다'가 된다(규칙 11).
    """
    if not patterns:
        return ["뷰어 템플릿에서 산문 첨자 정규식을 찾지 못했다 — 첨자 렌더 검사를 못 한다"
                " (`viewer_prose_subscript_patterns` 의 마커가 템플릿에서 바뀌었는지 볼 것)"]
    out = []
    for where, blob in iter_visible_texts(ch):
        if any(k in where for k in MATH_NATIVE_KEYS):
            continue                      # 필드 전체가 LaTeX — renderMath 가 따로 본다
        if any(where.endswith(k) for k in SUBSCRIPT_RENDER_EXEMPT):
            continue
        text = mask_inline_math(str(blob or ""))
        for rx in patterns:               # 뷰어가 첨자로 바꿀 자리를 **그대로 소비**시킨다
            text = rx.sub(" ", text)
        for m in _ANY_SUBSCRIPT.finditer(text):
            out.append(
                where + ": 밑글자가 화면에서 첨자를 못 받는다 — " + repr(m.group(0))
                + " → 밑줄이 날것으로 찍힌다. 산문 렌더러가 받는 밑글자는 뷰어 정규식이"
                " 정본이다(BMP 글자). 비-BMP 글리프(`𝒱` 등)는 산문에 넣지 말고"
                " 인라인 수식 `\\(\\mathcal{V}_{out}\\)` 으로 쓸 것: " + repr(str(blob)[:60]))
    return out


def xlink_landing_issue(label, target_id, target_child, section_ids, sections_by_id):
    """절 id 링크가 삽화 있는 절의 맨 위로 착지하면 더 좁은 앵커 목록을 돌려준다.

    2026-07-22, 같은 지적 2회 — '정상유동 과정'을 눌렀는데 절 맨 위가 보였다.
    표시 문구에 '절'이라고 밝힌 링크는 절로 가겠다고 예고한 것이므로 통과.
    """
    if target_id not in section_ids or target_child or "절" in label:
        return None
    finer = [d.get("id") for d in
             (sections_by_id.get(target_id) or {}).get("diagrams") or []]
    return finer or None


# 문풀 카드의 stage — **뷰어 템플릿의 stageMeta 키와 반드시 일치해야 한다.**
# 어긋나면 그 카드는 열리는 순간 죽는다(stageMeta[stage]가 undefined → sm.cls에서 TypeError).
# 두 곳이 갈라지는 것을 tools/test_checks.py 가 감시한다.
PRACTICE_STAGES = ("single_blank", "multi_blank", "process_fill", "assembly")

# C49 — 이해도 점검 답의 문장 수 상한. 호출부 주석이 경위의 정본이다.
#   ★ 값의 근거는 **실측 분포의 꼬리 바깥**이다.
#     `python tools/audit_checks_load.py --lengths` (열역학 240개, 2026-08-13):
#
#       떠올리기 131개 — 1문장 120 · 2문장 11 · 최대 2      → 상한 2 (지금 전부 통과)
#       연결하기  98개 — 1문장 2 · 2문장 51 · 3문장 43 ·
#                        4문장 1 · 6문장 1 · 최대 6         → 상한 3 (꼬리 2건이 걸린다)
#       설명하기  11개 — 3문장 3 · 4문장 7 · 5문장 1        → 상한 4 (꼬리 1건이 걸린다)
#
#   ★★ **추정으로 적었다가 재서 고쳤다.** 처음에 「떠올리기 95% · 연결하기 1~2문장 93%」로
#     적었는데 실측은 91.6% 와 54% 였다 — 연결하기는 3문장이 절반 가까이다. 값 자체는 안 바뀌었지만
#     **근거가 틀린 채로 남을 뻔했다**(AGENTS 규칙 11: 수량 주장은 스크립트 출력에서 온 것이어야 한다).
#   ★ 상한은 «지금 거의 다 지키는 것보다 한 칸 느슨한 값»이다 — 만들자마자 무더기로 걸리면
#     다음 사람이 검사를 끈다(라벨 여백 자에서 391건 중 91건이 오탐이던 전례).
CHECK_ANSWER_MAX_SENTENCES = {"recall": 2, "connect": 3, "explain": 4}

# 종결부호로 문장을 센다. **소수점과 줄임표는 세지 않는다** — `0.5` 를 두 문장으로 읽으면
# 자가 숫자에 반응하게 되고, 그건 길이와 아무 상관이 없다.
_SENTENCE_END = re.compile(r"[.?!](?=\s|$)")


def check_answer_sentences(answer):
    """이해도 점검 답의 문장 수. 순수 함수 — 빌드 검사와 `audit_checks_load` 가 함께 쓴다.

    ★ 두 곳이 같은 함수를 부르는 것이 요점이다. 세는 법을 각자 적으면 «자가 재는 것»과
      «사람이 보는 분포»가 갈라져, 상한을 고를 때 쓴 근거가 검사에는 적용되지 않는다.
    """
    text = str(answer or "").strip()
    if not text:
        return 0
    text = re.sub(r"(?<=\d)\.(?=\d)", "", text)          # 소수점
    text = text.replace("...", "").replace("…", "")       # 줄임표
    n = len(_SENTENCE_END.findall(text))
    return max(n, 1)                                      # 종결부호가 없어도 한 문장이다

# 문제·문풀의 difficulty — **뷰어 템플릿의 diffLabel 키와 반드시 일치해야 한다.**
# stage와 같은 부류인데 stage만 막고 있었다: 어긋나면 죽지는 않지만 배지에 영어 원문이
# 그대로 찍히고 `.badge.diff-<값>` CSS 규칙이 없어 색도 빠진다.
# 열린 날 2026-07-26 — thermo와 math **두 과목이 같은 날 각자 이 결함을 발견**했고,
# 각자 반대 어휘로 통일해 main에서 충돌했다(thermo: advanced / math: discriminating).
#
# **`advanced`로 확정한 근거 (thermo 2026-07-26, merge 충돌 해소):**
# ⑴ AGENTS '문제 설계' 절이 백틱 `advanced`로 쓰고 있다(AGENTS.md:511).
# ⑵ basic/intermediate와 짝이 맞는다.
#
# ※ 정정 (math 2026-07-26, merge 수용 시점) — 원래 근거에는 셋째 항목이 있었다:
#   [사용자 발화 인용 생략]
#   **둘 다 사실이 아니라 지웠다.** math가 커밋 4647276에서 그 하드코딩을 이미 제거해
#   `PROBLEM_DIFFICULTIES`를 import하도록 고쳤고, thermo도 그 수정을 그대로 유지했다
#   (같은 커밋의 `test_problem_difficulty_vocabulary`가 "목표 비중이 어휘 문자열을
#   하드코딩하지 않는다"를 단언한다). 등록부가 단일화된 뒤로는 **어느 이름을 쓰든 감사가
#   따라오므로** 그 항목은 어휘 선택의 근거가 될 수 없다. 선택은 ⑴⑵만으로 서 있다.
#   (규칙 11 — 근거가 코드와 어긋나면 다음 세션이 그것을 사실로 읽는다.)
# → **math 데이터는 `discriminating`을 쓰므로 마이그레이션이 필요하다.** 아래 오류 메시지가
#    그 방법을 직접 안내한다(값만 치환하지 말고 AGENTS 유형 축 A/B/C로 재분류할 것).
PROBLEM_DIFFICULTIES = ("basic", "intermediate", "advanced")
# 옛 이름 — thermo 쪽 코드가 이 이름으로 부르고 있었다. 사본을 만들지 않으려고 별칭만 둔다.
DIFFICULTY_TIERS = PROBLEM_DIFFICULTIES

# 챕터 도입부 — AGENTS '과목 개요와 챕터 도입부'(2026-07-26 신설, 전 과목 적용).
# 뷰어는 chapterIntro가 없으면 조용히 아무것도 그리지 않는다(기존 챕터를 안 깨려는 설계).
# 그 조용함이 곧 사각지대다 — 규칙이 생겨도 빠뜨린 챕터를 아무것도 지적하지 않는다.
# 그래서 index.json에서 status가 done인 챕터에 한해 존재와 필수 항목을 강제한다.
CHAPTER_INTRO_ROWS = ("question", "prerequisite", "nextLink")

# 조사·연결어는 어휘가 아니다. 떼어내지 않으면 '에너지의'와 '에너지'가 다른 낱말이 된다.
_XLINK_JOSA =("으로", "에서", "이고", "은", "는", "이", "가", "을", "를", "의", "에", "도", "와", "과", "로")
_XLINK_STOP = {"이고", "이다", "있는", "있다", "하는", "되는", "되면", "이면", "면서", "에서",
               "으로", "경우", "같은", "그리고", "때는", "여기", "이것", "그것"}


def xlink_tokens(text):
    """표시 문구·착지 본문에서 비교할 어휘 토큰을 뽑는다(2글자 이상만)."""
    out = set()
    for run in re.findall(r"[가-힣]+", text):
        word = run
        for _ in range(2):
            for josa in _XLINK_JOSA:
                if len(word) > len(josa) + 1 and word.endswith(josa):
                    word = word[:-len(josa)]
                    break
            else:
                break
        if len(word) >= 2 and word not in _XLINK_STOP:
            out.add(word)
    for run in re.findall(r"[A-Za-z]{2,}", text):
        out.add(run)
    return out


def xlink_topic_issue(label, landing_text, threshold=0.5):
    """표시 문구가 말하는 개념이 착지 화면에 실제로 있는가 — 없으면 빠진 토큰을 돌려준다.

    열린 날: 2026-07-24. 새어나간 것 — ch02의 '에너지의 단위는 kJ이고 … 동력의 단위는
    kW = kJ/s' 링크가 **단위가 한 글자도 없는** 낙하 PE/KE 삽화로 착지하고 있었다.
    기존 검사는 ⑴ 대상이 존재하는가 ⑵ 뷰어가 해시를 받는가 ⑶ 절 맨 위로 떨어지지 않는가
    셋만 봤다. **문구와 착지 내용이 서로 무관해도 통과하는 구조**였고, 사람이 눌러봐야만
    드러났다. 어휘 겹침이 절반에 못 미치면 사람이 확인하도록 띄운다.
    """
    wanted = xlink_tokens(label)
    if not wanted:
        return None
    missing = sorted(t for t in wanted if t not in landing_text)
    if len(wanted) - len(missing) >= threshold * len(wanted):
        return None
    return missing


def xlink_landing_text(target, target_id, target_child):
    """딥링크를 눌렀을 때 독자 화면에 실제로 뜨는 글을 모은다.

    정의 앵커는 그 단락부터 3단락까지 — 브라우저 실측(2026-07-24)에서 다음 단락이
    뷰포트 371px에 보였다. 삽화는 제목과 SVG 안 글자(독자가 읽는 것)만 쓰고
    rationale(저자 메모)은 넣지 않는다.

    ★ 2026-08-02 — **절 제목(heading)을 포함한다.** 종전에는 `content` 만 봤는데,
    절로 착지하면 화면 맨 위에 뜨는 것이 바로 그 제목이다(`.theory-h`, scroll-margin-top
    108px 이 헤더 아래로 밀어 준다). 제목을 빼고 재면 *독자가 실제로 보는 글의 일부를
    안 보는 것*이라 오탐이 난다 — 실측: `[[ch02:sec-const-coeff|3절 상수계수 제차 ODE]]`
    가 반려됐는데, 그 세 낱말은 **그 절의 제목 그 자체**였다.
    이 자리는 절 번호·제목을 라벨로 쓰는 관례(2026-08-02 사용자 결정)로 바뀌면서
    비로소 드러났다 — 라벨이 본문 낱말에서 오던 때는 티가 안 났다.
    """
    sections = (target.get("theory") or {}).get("sections") or []
    section = next((x for x in sections if x.get("id") == target_id), None)
    if section is not None:
        heading = str(section.get("heading", ""))
        paragraphs = re.split(r"\n{2,}", section.get("content", ""))
        if target_child:
            anchor = next((d.get("anchorText", "") for d in section.get("definitions") or []
                           if d.get("id") == target_child), "")
            idx, _ = resolve_anchor_text(paragraphs, anchor) if anchor else (None, None)
            if idx:
                return heading + "\n" + "\n".join(paragraphs[idx - 1:idx + 2])
        return heading + "\n" + section.get("content", "")
    diagram = next((d for d in _iter_diagrams(target) if d.get("id") == target_id), None)
    if diagram is None:
        return ""
    svg_text = " ".join(re.findall(r">([^<>]+)<", diagram.get("svg", "")))
    return diagram.get("title", "") + " " + svg_text


def xlink_target_valid(target, target_id, target_child):
    """Validate a deep-link target, including a definition owned by the target section."""
    sections = (target.get("theory") or {}).get("sections") or []
    section_ids = {section.get("id") for section in sections}
    if target_child:
        section = next((item for item in sections if item.get("id") == target_id), None)
        definition_ids = {definition.get("id") for definition in (section or {}).get("definitions") or []}
        return section is not None and target_child in definition_ids
    diagram_ids = {diagram.get("id") for diagram in _iter_diagrams(target)}
    return target_id in section_ids or target_id in diagram_ids


def resolve_anchor_text(paragraphs, anchor):
    """anchorText(단락 앞부분 문자열) → afterParagraph(1-based). 실패하면 (None, 사유).

    왜 필요한가: 삽화를 **단락 번호**로 묶으면 본문을 한 단락 고칠 때마다 뒤의 삽화가
    전부 밀린다. 번호는 '범위 안'이기만 하면 빌드가 통과시키므로 조용히 어긋난다.
    실제로 ch02 재편 때 8건, 표기 정리 때 5건이 같은 이유로 밀렸다(2026-07-22).
    본문 표식에 묶으면 본문이 움직여도 삽화가 따라간다.
    """
    key = anchor.strip()
    hits = [i for i, p in enumerate(paragraphs, 1) if p.strip().startswith(key)]
    if len(hits) == 1:
        return hits[0], None
    if not hits:
        return None, "anchorText가 어느 단락과도 맞지 않음 — " + repr(key[:30])
    return None, "anchorText가 " + str(len(hits)) + "개 단락과 맞음(모호) — " + repr(key[:30])


def mask_inline_math(text):
    r"""인라인 수식 `\( … \)` 자리를 같은 길이의 공백으로 덮은 사본.

    **산문 규칙을 LaTeX 자리에 적용하면 안 된다** — 이 파일에서 두 번 실제로 샜다:
    ⑴ 별표 강조 검사가 `F^{*}(y)`를 강조로 오인 ⑵ 캐럿 금지 검사가 `\(e^{-h}\)`를 위반으로 판정.
    ⑵는 특히 나빴다 — 캐럿을 금지당하면 유니코드 위첨자로 되돌리게 되고, 그게 바로
    `inline_math_issues`가 잡으려는 결함이라 **두 검사가 서로를 강요하는 교착**이 된다.
    길이를 보존하는 이유: 위치·단락 구조를 쓰는 검사가 같은 좌표를 유지해야 하기 때문이다.
    """
    return INLINE_MATH_RE.sub(lambda m: " " * len(m.group(0)), text)


def prose_style_problems(text):
    """본문 표기 규칙 위반을 (사유, 걸린 문자열)로 돌려준다.

    2026-07-22 지적: ⑴ `*강조*` 별표를 쓰지 말 것 ⑵ `##` 헤딩·`>` 인용은 뷰어가 렌더하지
    않아 화면에 날것으로 나온다 ⑶ 굵게가 설명 문장까지 번져 '진짜 중요한 용어만'이라는
    합의가 깨졌다. 셋 다 사람이 눈으로 세던 것이라 매번 새로 샜다.
    """
    out = []
    # ⑴ 단일 별표 강조 (**굵게**는 통과)
    #    ★ 인라인 수식 안은 보지 않는다 — 거기 별표는 강조가 아니라 **수학 기호**다
    #    (`F^{*}(y)`·`R^{*}` 같은 교재 표기. 2026-07-27 실측: 적분인자의 y쪽 갈래를
    #    본문에 쓰자마자 이 검사가 오탐을 냈다). 산문 규칙을 LaTeX 자리에 들이대면
    #    안 된다는 것이 이 파일에서 반복된 부류다 — 아래 캐럿 검사도 같은 이유로 마스킹한다.
    for m in re.finditer(r"(?<!\*)\*(?!\*)([^*\n]{1,40})\*(?!\*)", mask_inline_math(text)):
        out.append(("별표 강조 금지 — 굵게(**)나 평문으로", m.group(0)))
    for line in text.split("\n"):
        s = line.strip()
        # ⑵ 뷰어가 렌더하지 않는 마크다운
        if s.startswith("#"):
            out.append(("뷰어가 헤딩을 렌더하지 않음 — 절을 나누거나 평문으로", s[:40]))
        if s.startswith(">"):
            out.append(("뷰어가 인용을 렌더하지 않음 — 평문으로", s[:40]))
    # ⑶ 굵게 남용. 불릿·표는 줄마다 용어 하나를 굵게 하는 것이 정상이므로 줄 단위로 센다
    #    (단락 단위로 세면 잘 만든 용어 목록이 걸린다 — 검사가 아니라 오탐이다).
    def bolds(s):
        return len(re.findall(r"\*\*[^*\n]+\*\*", s))

    for para in split_paragraphs(text):
        lines = [l for l in para.split("\n") if l.strip()]
        itemized = lines and all(re.match(r"^\s*(-\s+|\|)", l) for l in lines)
        if itemized:
            for line in lines:
                if bolds(line) > BOLD_MAX_PER_LINE:
                    out.append(("한 줄에 굵게 " + str(bolds(line)) + "개 — 용어 하나만",
                                line.strip()[:40]))
        elif bolds(para) >= BOLD_MAX_PER_PARAGRAPH:
            out.append(("한 단락에 굵게 " + str(bolds(para)) + "개 — 진짜 중요한 용어만 남길 것",
                        para.strip()[:40]))
    # ⑷ 목록으로 렌더되지 않는 대시 줄 (열린 날 2026-07-28, 고체역학 ch00 렌더 검수에서 발견)
    #    뷰어 fmtBlock은 **블록의 모든 줄이 대시로 시작하고 2줄 이상**일 때만 목록으로 만든다.
    #    그래서 항목이 하나뿐이거나 산문 줄이 섞이면 목록이 아니라 그냥 문단이 되고,
    #    화면에 `- `가 **날것으로 남는다**. 저자는 목록을 쓴 줄 알고, 빌드는 통과시킨다.
    #    flow_break_paragraphs가 같은 규칙(len>1 and all)을 이미 알고 있었는데
    #    그것은 '흐름을 끊는가'만 셌지 **안 끊긴 대시가 어떻게 보이는지**는 아무도 안 봤다.
    #    ⑵(헤딩·인용)와 같은 부류다 — 뷰어가 렌더하지 않는 마크다운이 날것으로 새는 것.
    for para in split_paragraphs(text):
        lines = block_lines(para)
        kind = classify_block(lines)
        # 번호 목록도 같은 함정이다 (넓힌 날 2026-08-06) — 항목이 하나뿐이거나 산문 줄이
        # 섞이면 `<ol>` 이 되지 않고 `1. ` 이 화면에 날것으로 남는다. 대시와 규칙이 같다.
        for marker, want, name, shown in ((BLOCK_LIST_RE, "list", "대시", "- "),
                                          (BLOCK_OLIST_RE, "olist", "번호", "1. ")):
            marked = [l for l in lines if marker.match(l)]
            if marked and kind != want:
                out.append((name + " 줄이 목록으로 렌더되지 않음(화면에 '" + shown
                            + "'가 날것으로 남는다) — 항목을 2개 이상으로 만들거나 "
                            "문장으로 풀 것", marked[0].strip()[:40]))
    return out


def split_paragraphs(content):
    """뷰어(renderTheoryBody)와 **같은 규칙**으로 단락을 자른다.

    한쪽이 "\\n\\n", 다른 쪽이 /\\n{2,}/ 이면 빈 줄 3개 이상에서 개수가 갈리고,
    빌드는 통과하는데 뷰어는 삽화를 본문 끝으로 미는 침묵한 오배치가 생긴다.
    두 곳이 어긋나지 않도록 여기 한 군데로 모은다 (tools/test_checks.py가 감시).
    """
    return re.split(r"\n{2,}", content)


# ★ 블록의 종류를 판정하는 자 — **한 곳에만 둔다** (모은 날 2026-08-06).
#   같은 규칙이 파이썬 세 곳(`flow_break_paragraphs`·`swallowed_newline_blocks`·
#   `prose_style` ⑷)에 복사돼 있었고 뷰어 `fmtBlock` 까지 넷이었다. 형태를 하나 늘릴 때마다
#   넷을 고쳐야 하고 하나만 빠뜨리면 **화면과 검사가 갈린다** — 이 파일이 이미 여러 번 겪은
#   부류다(분수 자·치수 라벨 자·캡션 판정 자가 전부 그랬다).
#   JS 쪽 사본은 없앨 수 없으므로 `test_viewer_block_forms_match` 가 두 벌을 대조한다.
BLOCK_LIST_RE = re.compile(r"^\s*-\s+")
BLOCK_OLIST_RE = re.compile(r"^\s*\d+\.\s+")
BLOCK_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")
BLOCK_TABLE_RULE_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
BLOCK_MATH_RE = re.compile(r"^\s*\\\(.*\\\)\s*$")


def block_lines(block):
    """빈 줄을 걷어낸 줄 목록 — 뷰어 `fmtBlock` 첫 줄과 같은 전처리."""
    return [ln for ln in str(block).split("\n") if ln.strip()]


def classify_block(lines):
    """줄 목록 → `'table'|'list'|'olist'|'math'|'prose'`. 뷰어와 **같은 순서·같은 조건**.

    · 목록·번호 목록은 항목이 **2개 이상**이어야 목록이 된다 — 하나뿐이면 뷰어가 문단으로
      렌더해 화면에 `- `·`1. ` 이 날것으로 남는다(그 자리는 `prose_style` ⑷ 가 신고한다).
    · **수식 블록은 한 줄만으로도 성립한다.** 홀로 선 식 하나가 가장 흔한 경우이고,
      줄 전체가 인라인 수식뿐이라 산문과 헷갈릴 여지가 없다.
    """
    if not lines:
        return "prose"
    if (len(lines) > 2 and all(BLOCK_TABLE_RE.match(ln) for ln in lines)
            and BLOCK_TABLE_RULE_RE.match(lines[1])):
        return "table"
    if len(lines) > 1 and all(BLOCK_LIST_RE.match(ln) for ln in lines):
        return "list"
    if len(lines) > 1 and all(BLOCK_OLIST_RE.match(ln) for ln in lines):
        return "olist"
    if all(BLOCK_MATH_RE.match(ln) for ln in lines):
        return "math"
    return "prose"


def density_worst_gap(n_paras, anchored):
    """삽화 없이 이어지는 최장 단락 수. anchored = 흐름을 끊는 단락 번호(1-based)."""
    gap = worst = 0
    for i in range(1, n_paras + 1):
        gap = 0 if i in anchored else gap + 1
        worst = max(worst, gap)
    return worst


def flow_break_paragraphs(paragraphs):
    """불릿 목록·파이프 표 블록의 1-based 인덱스 — 삽화처럼 흐름을 끊는다.

    사용자 관점(2026-07-27): 글 밀도는 '연속 텍스트가 너무 많이 이어질 때' 문제이고,
    목록·표는 흐름을 바꿔주는 flow-break이므로 '벽글' 연속을 삽화와 똑같이 리셋한다.
    판정은 뷰어 fmtBlock(isList/isTable)과 같은 규칙 — 어긋나면 화면과 검사가 갈린다.
    """
    return {i for i, block in enumerate(paragraphs, 1)
            if classify_block(block_lines(block)) != "prose"}


def swallowed_newline_blocks(text):
    r"""뷰어가 **조용히 삼키는** 줄바꿈을 찾는다. (열린 날 2026-07-29)

    fmtText는 `\n{2,}` 로만 블록을 나누고, 블록 **안**의 단일 `\n` 은 fmtBlock이
    목록(`- `)이나 파이프 표로 판정하지 못하면 그대로 `<p>` 안에 남는다 —
    HTML에서 공백으로 접히므로 **줄이 바뀌지 않는다.**
    즉 저자가 줄을 바꾸려고 넣은 `\n` 이 아무 일도 하지 않는다.

    실사고(이 검사가 열린 이유): 인박스 44번 [사용자 발화 인용 생략] 를 고치며 ch01 유도 4곳에 `안내 문구:\n\(식\)` 을 넣었는데, 화면에서는
    한 줄로 이어져 **고쳐지지 않은 채 검수를 통과했다.** 데이터만 보면 고쳐진 것처럼
    보이는 것이 이 부류가 무서운 점이다 — 그래서 눈이 아니라 검사가 봐야 한다.

    판정은 뷰어 fmtBlock과 **같은 규칙**으로 한다(어긋나면 화면과 검사가 갈린다).
    """
    bad = []
    for block in split_paragraphs(str(text or "")):
        lines = block_lines(block)
        if len(lines) >= 2 and classify_block(lines) == "prose":
            bad.append(block)
    return bad


def iter_line_break_fields(ch):
    r"""줄바꿈 의도가 살아 있어야 하는 fmtText 필드 — 이론 본문·유도 단계·풀이 단계.

    `iter_prose_fields` 와 일부러 나눠 둔다: 저쪽은 별표·대시 같은 **표기** 검사용이라
    순회 범위가 다르고, 특히 `derivationSteps` 의 설명 문장이 저쪽에는 없다
    (44번 결함이 바로 그 자리에서 났다).
    """
    for section in (ch.get("theory") or {}).get("sections") or []:
        yield "section " + str(section.get("id")), section.get("content", "") or ""
    for formula in (ch.get("derivation") or {}).get("formulas") or []:
        for i, step in enumerate(formula.get("derivationSteps") or [], 1):
            yield ("formula " + str(formula.get("id")) + "/step[" + str(i) + "]",
                   step_prose(step))
    for prob in ch.get("problems") or []:
        for i, step in enumerate(prob.get("solutionOutline") or [], 1):
            yield ("problem " + str(prob.get("id")) + "/solutionOutline[" + str(i) + "]",
                   step_prose(step))


def iter_prose_fields(ch):
    """저자가 쓴 산문이 사는 **이론 본문 밖의** 모든 자리를 (위치, 글)로 돌려준다.

    열린 날 2026-07-24 — `*이상적인 역학 장치로…*` 별표 강조가 화면에 날것으로 나왔다.
    같은 지적이 이전에도 있었는데 재발했다. 새어나간 이유: 표기 검사(prose_style_problems)를
    `theory.sections[].content` **하나에만** 걸어 두어서, `pitfalls[].note`에 든 별표는
    아무도 보지 않았다. 이해도 체크가 이론만 순회해 유도 11건을 놓친 것(2026-07-21)과 같은 부류다.

    **표기 규칙을 새로 만들면 반드시 이 함수를 통해 전 컬렉션을 돌 것.**
    """
    theory = (ch.get("theory") or {}).get("sections") or []
    derivation = (ch.get("derivation") or {}).get("formulas") or []
    for section in theory:
        for pit in section.get("pitfalls") or []:
            yield "section " + str(section.get("id")) + " pitfall " + str(pit.get("id")), pit.get("note", "")
    for formula in derivation:
        yield "formula " + str(formula.get("id")) + " notes", formula.get("notes", "") or ""
        for pit in formula.get("pitfalls") or []:
            yield "formula " + str(formula.get("id")) + " pitfall " + str(pit.get("id")), pit.get("note", "")
    for kind, item in _iter_check_owners(ch):
        for chk in item.get("comprehensionChecks") or []:
            for field in ("prompt", "answer", "explanation"):
                yield kind + " " + str(item.get("id")) + " " + str(chk.get("id")) + "/" + field, chk.get(field, "") or ""
    for prob in ch.get("problems") or []:
        yield "problem " + str(prob.get("id")) + "/answer", prob.get("answer", "") or ""
        for i, step in enumerate(prob.get("solutionOutline") or [], 1):
            # 설명 문장만 산문 검사에 넘긴다 — equations는 LaTeX라 별도로 check_latex_field가 본다.
            yield "problem " + str(prob.get("id")) + "/solutionOutline[" + str(i) + "]", step_prose(step)


def step_prose(step):
    """유도·풀이 한 단계의 **설명 문장**. (스키마 확장 2026-07-26)

    단계는 두 형태를 받는다:
      ⑴ `"설명 문장"`                                    ← 기존
      ⑵ `{"text": "설명", "equations": ["식", "식"]}`     ← 신설. 식을 **독립 줄**로 세운다.

    왜 갈라야 하나 — 기존 검사들은 원소가 문자열이라고 가정한다(캐럿 금지·표기 검사 등).
    dict가 그대로 흘러가면 검사가 **조용히 무너진다.** 그리고 `equations`는 LaTeX라
    캐럿(`^`)이 정상이므로 산문 검사에 섞으면 오탐이 된다. 그래서 접근자를 둘로 나눈다.
    """
    if isinstance(step, dict):
        return str(step.get("text") or "")
    return str(step or "")


def step_equations(step):
    """유도·풀이 한 단계의 **독립 식 줄** 목록. 문자열 단계면 빈 목록."""
    if isinstance(step, dict):
        return [str(e) for e in (step.get("equations") or []) if str(e).strip()]
    return []


def latex_rows(value):
    r"""`latex` 필드를 **행 → 열** 로 편다. 중첩 배열이 곧 「좌우 비교」 선언이다.

    ★★ **열린 날 2026-08-13.** 뷰어 `renderMathLines` 는 2026-07-28 부터 `latex` 안의
    **중첩 배열**을 `.fmath-cols`/`.fmath-col`(점선으로 갈린 두 열)로 그려 왔는데,
    **이 접근자는 그 형식을 몰랐다** — `str(["A", "B"])` 가 그대로 흘러
    검사들이 `"['A', 'B']"` 라는 **파이썬 repr** 을 식으로 알고 검사하고 있었다.
    실사용 중이다 — 공학수학 ch01 의 적분인자 카드(802행)가
    2행 × 2열이라, 그 네 식은 지금껏 `check_latex_field` 를 **한 번도 제대로 통과한 적이 없다**
    (repr 을 검사했으니 통과도 실패도 무의미했다).

    화면이 그리는 형식을 자가 모르면 그 자리는 사각지대가 된다 — `iter_math_blobs`(variables 키)
    와 같은 부류다. 그래서 **행/열 구조를 아는 접근자**를 정본으로 두고 `latex_lines` 는
    그것을 펴서 쓴다. 두 벌로 적으면 갈라진다.

    배열을 받는 이유(2026-07-26): 절차형 유도(변수분리·완전 판정)는 '결과 공식 한 줄'이
    존재하지 않는데 기존 스키마가 한 줄을 강요해 `A ⇒ B`를 가로로 붙이게 만들었다(사용자 지적).
    """
    if isinstance(value, list):
        return [[str(c) for c in row] if isinstance(row, list) else [str(row)]
                for row in value]
    return [[str(value or "")]]


def latex_lines(value):
    """`latex` 필드의 모든 식 줄 — 문자열이면 한 줄, 배열이면 여러 줄, 중첩이면 열까지 편다.

    **행 구조가 필요한 검사는 `latex_rows` 를 직접 쓴다**(C27 의 좌우 비교 판정).
    """
    return [col for row in latex_rows(value) for col in row]


def _iter_check_owners(ch):
    """Yield (kind, item) for every place a comprehensionChecks list may live.

    이해도 체크는 이론뿐 아니라 유도·문풀·연습문제에도 붙는다. 검사·감사는 반드시
    이 함수를 통해 전 컬렉션을 돌 것 (이론만 순회하다 유도 결함을 놓친 이력이 있다).
    """
    for s in (ch.get("theory") or {}).get("sections") or []:
        yield "section", s
    for f in (ch.get("derivation") or {}).get("formulas") or []:
        yield "formula", f
    for p in ch.get("practice") or []:
        yield "practice", p
    for q in ch.get("problems") or []:
        yield "problem", q

def resolve_review_prerequisites(ch, ch_path):
    """Resolve cross-chapter review links and transclude referenced source diagrams."""
    chapter_dir = os.path.dirname(ch_path)
    source_cache = {}
    for section in (ch.get("theory") or {}).get("sections") or []:
        for ref in section.get("reviewPrerequisites") or []:
            chapter_number = ref.get("chapterNumber")
            section_id = ref.get("sectionId")
            if not isinstance(chapter_number, int) or not section_id:
                raise ValueError(ch_path + ": invalid reviewPrerequisites reference")
            source_path = os.path.join(chapter_dir, "ch" + str(chapter_number).zfill(2) + ".json")
            if source_path not in source_cache:
                if not os.path.isfile(source_path):
                    raise ValueError(ch_path + ": review source missing: " + source_path)
                source_cache[source_path] = json.load(open(source_path, encoding="utf-8"))
            source = source_cache[source_path]
            source_sections = {
                item.get("id"): item for item in (source.get("theory") or {}).get("sections") or []
            }
            if section_id not in source_sections:
                raise ValueError(ch_path + ": review section missing: " + section_id)
            ref["href"] = "ch" + str(chapter_number).zfill(2) + ".html#theory-" + section_id
            diagrams = {dg.get("id"): dg for dg in _iter_diagrams(source)}
            resolved = []
            for diagram_id in ref.get("diagramIds") or []:
                if diagram_id not in diagrams:
                    raise ValueError(ch_path + ": review diagram missing: " + diagram_id)
                diagram = copy.deepcopy(diagrams[diagram_id])
                diagram["id"] = "review-ch" + str(chapter_number).zfill(2) + "-" + diagram_id
                resolved.append(diagram)
            ref["diagrams"] = resolved
    return ch

def check_latex_field(where, s, errors):
    for cmd in re.findall(r"\\([A-Za-z]+)", s):
        if cmd not in LATEX_SUPPORTED:
            errors.append(where + ": renderMath 미지원 명령 \\" + cmd)
    # ★ `\mathcal` 은 **명령이 지원되는 것과 글자가 그려지는 것이 다르다** (2026-08-25, math2 실측).
    #   `LATEX_SUPPORTED` 에 `mathcal` 이 있어 여기까지는 통과하는데, 뷰어의 `renderMath` 는
    #   **`\mathcal{V}` 한 개만** 치환한다. 그래서 `\mathcal{L}` 은 역슬래시째 화면에 찍힌다 —
    #   빌드가 초록인 채로 독자 화면만 깨지는 자리라 **검사를 렌더러 쪽에 맞춘다**(엄한 쪽).
    #   글자를 늘리려면 템플릿의 치환을 먼저 늘리고 이 집합을 따라 옮긴다 — 순서가 반대면
    #   같은 사고가 그대로 되살아난다. 잠금 `test_mathcal_letters_match_the_renderer`.
    for match in re.finditer(r"\\mathcal\{([^{}]*)\}", s):
        if match.group(1) not in VIEWER_MATHCAL_LETTERS:
            errors.append(
                where + ": 뷰어가 못 그리는 `\\mathcal{" + match.group(1) + "}` — "
                "지금 그려지는 글자는 " + ", ".join(sorted(VIEWER_MATHCAL_LETTERS))
                + " 뿐이다(역슬래시째 화면에 찍힌다). 말로 풀어 쓰거나 다른 기호를 쓸 것")
    # ★ `\mathfrak` 도 같은 사정이다 (2026-09-03) — 위 `\mathcal` 주석이 정본.
    for match in re.finditer(r"\\mathfrak\{([^{}]*)\}", s):
        if match.group(1) not in VIEWER_MATHFRAK_LETTERS:
            errors.append(
                where + ": 뷰어가 못 그리는 `\\mathfrak{" + match.group(1) + "}` — "
                "지금 그려지는 글자는 " + ", ".join(sorted(VIEWER_MATHFRAK_LETTERS))
                + " 뿐이다(역슬래시째 화면에 찍힌다). 말로 풀어 쓰거나 다른 기호를 쓸 것")
    if re.search(r"\\(mathrm|text|vec|mathbf)\{[^{}]*\{", s):
        errors.append(where + ": 단일 인자 매크로 안 중첩 중괄호 — 정규식 변환 실패함")
    # renderMath는 이 전처리를 분수보다 먼저 수행한다. 그 뒤에도 중첩 중괄호가
    # 남은 분수만 실제 미렌더 위험으로 본다.
    # ★ `mathbf` 도 여기 있어야 한다 (2026-08-06) — 벡터를 분수 안에 쓰면
    #   (`\frac{d\mathbf{r}}{dt}`) 겉보기에는 중첩 중괄호지만, renderMath 가 `\mathbf` 를
    #   **분수보다 먼저** HTML 로 바꾸므로 실제로는 중괄호가 남지 않는다. 빼 두면
    #   정상 표기가 통째로 막힌다 — 벡터의 시간 미분은 이 과목에서 피할 수 없는 형태다.
    pre_frac = s
    # ★ `mathcal` 을 2026-08-12 에 더했다 — 렌더러에서 `\mathcal{V}` 치환을 `\frac` **앞**으로
    #   옮겼으므로 이 자도 같이 옮겨야 한다. 안 옮기면 화면은 멀쩡한데 빌드만 막는다.
    # ★ `hl` 을 2026-08-13 에 더했다 — 「짝과 다른 부분」 강조도 `\frac` **앞**에서 치환된다.
    #   안 더하면 `\frac{\hl{k}R}{k - 1}` 처럼 **화면은 멀쩡한데 빌드만 막는다**(`mathcal` 선례).
    # ★ `sqrt` 을 2026-08-25 에 더했다 — **세 번째 재발**이다(`mathcal` 08-12 · `hl` 08-13).
    #   `\frac{1}{\sqrt{n}}` 이 **화면은 멀쩡한데 빌드만 막았다**(math2 ch12 실측).
    #   재발이 셋이면 원인은 「빠뜨렸다」가 아니라 **이 목록을 손으로 유지하는 구조**다 —
    #   그래서 이번엔 항목만 더하지 않고 회귀를 붙였다:
    #   `test_checks.py::test_pre_frac_macros_match_the_renderer` 가 **뷰어 템플릿을 읽어**
    #   `\frac` 보다 먼저 치환되는 매크로가 전부 여기 있는지 대조한다. 다음 번엔 자가 먼저 운다.
    for macro in PRE_FRAC_MACROS:
        pre_frac = re.sub(r"\\" + macro + r"\{([^{}]*)\}", r"\1", pre_frac)
    pre_frac = re.sub(r"_\{([^{}]*)\}", r"\1", pre_frac)
    pre_frac = re.sub(r"_([A-Za-z0-9])", r"\1", pre_frac)
    pre_frac = re.sub(r"\^\{([^{}]*)\}", r"\1", pre_frac)
    pre_frac = re.sub(r"\^([A-Za-z0-9])", r"\1", pre_frac)
    if re.search(r"\\frac\{[^{}]*\{|\\frac\{[^{}]*\}\{[^{}]*\{", pre_frac):
        errors.append(where + ": 분수 인자 안 중첩 중괄호 — renderMath 변환 누락 위험")
    without_blank_markers = re.sub(r"___BLANK_\d+___", "", s)
    for match in re.finditer(r"_[A-Za-z]{2,}", without_blank_markers):
        errors.append(where + ": 중괄호 없는 여러 글자 아래첨자 " + repr(match.group(0)) + " — _{...}로 표기할 것")

def chapter_status(ch, ch_path):
    """index.json이 이 챕터에 매긴 status ('done'/'todo'…). 못 찾으면 None."""
    index_path = os.path.join(os.path.dirname(ch_path), "index.json")
    if not os.path.isfile(index_path):
        return None
    with open(index_path, encoding="utf-8") as fh:
        index = json.load(fh)
    base = os.path.basename(ch_path)
    for entry in index.get("chapters") or []:
        if entry.get("file") == base:
            return entry.get("status")
    return None


def chapter_intro_issues(ch, ch_path):
    """완성(done) 챕터에 도입부가 있고 필수 항목이 채워졌는지.

    판정을 lint_chapter 밖에 두는 이유는 guard_bash와 같다 — 안에 묻으면 테스트가 못 본다.
    """
    if chapter_status(ch, ch_path) != "done":
        return []
    intro = ch.get("chapterIntro")
    if not isinstance(intro, dict) or not intro:
        return ["chapterIntro 없음 — done 챕터는 '이 장이 답하는 질문/선수 지식/다음 장 연결'을 "
                "먼저 줘야 한다(AGENTS '과목 개요와 챕터 도입부')"]
    missing = [k for k in CHAPTER_INTRO_ROWS
               if not isinstance(intro.get(k), str) or not intro[k].strip()]
    if missing:
        return ["chapterIntro 항목 누락 — " + ", ".join(missing)]
    return []


INLINE_MATH_RE = re.compile(r"\\\((.+?)\\\)", re.S)

# ★ 유니코드 위·아래첨자 (열린 날 2026-07-26 · 검사 승격 2026-07-27, 인박스 항목 6)
#
# 사용자 실측: [사용자 발화 인용 생략]
# 문자 위첨자(ᵃ ʰ ˣ)는 숫자(² ³)와 달리 대부분의 본문 폰트에서 글리프가 없거나 점처럼 뭉갠다.
#
# **구조적 원인 — 빠뜨림이 아니라 낡은 규칙이 유도한 결함이다.** AGENTS 함정 목록이
# [사용자 발화 인용 생략] 라고 지시했는데, 그 규칙은
# 인라인 수식 `\(…\)`이 plain 필드 **안으로** 들어오기 전에 쓰인 것이다. 그 뒤로 `\(e⁻ʰ\)`처럼
# **LaTeX 자리에 유니코드를 박는 것이 규칙을 지키는 것처럼** 보이게 됐다.
#
# 그래서 규칙을 둘로 가른다.
#   ⑴ 수식 자리(`\(…\)` 안 · `latex` · 단계의 `equations`)  → 유니코드 첨자 **전면 금지**. `^{}`·`_{}`로.
#   ⑵ 산문 자리                                            → **문자** 첨자만 금지(인라인 수식으로).
#      숫자 위첨자(`m³`, `m/s²`)는 폰트가 제대로 그리므로 산문에서 계속 허용한다.
UNI_SUPSUB_LETTERS = "ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ"
UNI_SUPSUB_ANY = UNI_SUPSUB_LETTERS + "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎"
# 값 전체가 LaTeX인 필드 — `\(…\)` 표시가 없어도 수식 자리다.
MATH_ONLY_KEYS = {"latex", "equations"}
# 독자 화면에 안 나가는 편집 메모·식별자. 여기의 유니코드는 렌더 품질과 무관하다.
UNI_SUPSUB_EXEMPT_KEYS = {"id", "sourceRef", "source", "href", "sourcePages", "supplementNotes"}


# ★ C17. 3항목 이상 나열은 쉼표 (신설 2026-08-02, 사용자 결정).
#
# 사용자 지적: [사용자 발화 인용 생략] → 선택지 넷을 제시해 **쉼표**를 골랐다.
# `s·v·a` → `s, v, a`. **2항목 가운데점(`미분·적분`)은 그대로 둔다** — 사용자가 명시했다.
#
# **판정 범위를 좁게 잡는다: 공백 없이 붙은 가운데점이 한 덩어리에 둘 이상일 때만.**
#   · 잡는다: `s·v·a` · `위치·변위·이동거리` · `직교·n-t·극`
#   · 안 잡는다: `미분·적분`(2항목) · `추가 3 · 수정 5 · 삭제 1`(공백을 둔 구분자) ·
#               `1 kg·m/s²`(단위 곱은 점이 하나다)
# 단위 곱이 셋 이상 이어지는 표기(`N·m·s`)는 **지금 전 과목 데이터에 없다.** 0건인 것을 미리
# 예외로 만들면 그 예외가 나중에 진짜 위반을 덮으므로, 나오면 그때 만든다.
#
# **왜 과목별 승격 목록인가 (규칙 11 — 세고 나서 정했다).** `git grep` 실측:
# 열역학 116줄 · 공학수학 22줄이 걸린다. 여기서 error 로 박으면 **그 두 과목 빌드가 즉시 멈춰
# 사용자가 검수를 못 한다.** 그래서 정리를 끝낸 챕터만 error 로 올리고 나머지는 경고로 둔다.
# 경고는 `close_report` 의 '경고 잔량'이 close 를 막으므로 묻히지 않는다 — 각 과목이 자기
# 챕터를 정리하고 여기 파일명을 추가하는 방식이다(`PROSE_STYLE_STRICT_CHAPTERS` 와 같은 관례).
MIDDOT_RUN_RE = re.compile(r"[^\s·,]+·[^\s·,]+·[^\s·,]+")
MIDDOT_EXEMPT_KEYS = {"sourceRef", "id"}      # 화면에 안 나가는 자리
# 공학수학은 2026-08-02 에 22줄을 정리해 0건이 되었으므로 세 챕터를 함께 올린다
# (경고로 두면 다음 문장이 그 더미에 묻힌다 — C1~C5 의 교훈).
# ★★ **이 목록의 키는 파일명뿐이라 과목이 겹친다** — 같은 날(2026-08-02) 실사고가 났다.
#   공학수학이 자기 ch00~ch02 를 올리자 **열역학 ch00~ch02 가 함께 error 로 승격돼
#   빌드가 깨졌다**(열역학엔 아직 127건이 남아 있었다). 기계재료가 같은 벽에 부딪혀
#   `subject_strict_chapters()` 를 만들었다 — **과목별 진도는 그 과목 폴더가 갖는다.**
#   → 새 승격은 여기 넣지 말고 `data/<과목>/index.json` 의 `strictChapters` 에 선언할 것.
#     (열역학 ch03~ch05 가 그렇게 들어가 있다.)
MIDDOT_STRICT_CHAPTERS = {"ch12.json", "ch00.json", "ch01.json", "ch02.json",
                          "ch06.json", "ch07.json"}


def subject_strict_chapters(ch_path, list_name):
    """이 과목이 **자기 폴더에서** 추가로 승격한 챕터들 (`data/<과목>/index.json`).

    ★ 열린 날 2026-08-02 (기계재료 실측). 승격 목록이 **파일명 기준**이라
    `ch01.json` 하나를 올리면 **모든 과목의 ch01** 이 동시에 error 가 된다. 그런데 정리 진도는
    과목마다 다르다 — 기계재료가 가운데점 39건을 정리하고 ch01~ch03 을 올리려 하자
    `git grep` 실측으로 **열역학 ch01·ch02·ch03 의 23·39·20줄**이 곧바로 error 가 되는 상황이었다.
    (그 부류는 그 과목이 아직 정리하지 않았다. 남의 빌드를 멈추게 하는 승격은 승격이 아니다.)

    그래서 **과목별 진도는 그 과목 폴더가 갖는다** — `promptLanguage`·`textbook-pdf-map.json` 과
    같은 방식이다. 공통 코드에는 과목 이름이 들어가지 않는다(AGENTS 「공통 도구에 과목별
    사실을 박지 않는다」). 선언 형식:

        "strictChapters": { "middot": ["ch01.json", "ch02.json"] }

    빈 값·파일 없음이면 빈 집합이라 **기존 동작 그대로**다(폴백이 과목을 알지 않는다).
    """
    try:
        with open(os.path.join(os.path.dirname(ch_path), "index.json"), encoding="utf-8") as fh:
            declared = (json.load(fh).get("strictChapters") or {}).get(list_name) or []
    except (OSError, ValueError, AttributeError):
        return set()
    return {str(x) for x in declared}


def subject_pending_chapters(ch_path, list_name):
    """그 과목이 **아직 못 올린다고 명시한** 챕터들 (`index.json` 의 `pendingChapters`).

    ★ 열린 날 2026-08-02. 새 규격(화살표 크기)을 만들면 그 순간 전 챕터가 미승격이 되는데,
      `test_strict_promotion_covers_all_chapters` 는 *모든 챕터가 모든 목록에* 있기를 요구한다.
      공용 `STRICT_PENDING_CHAPTERS` 에 챕터를 넣으면 **다른 규격의 승격까지 함께 풀린다** —
      보류가 규격 하나가 아니라 챕터 전체에 걸리기 때문이다.
      그래서 보류도 **규격별·과목별**로 적는다. 형식은 `strictChapters` 와 같다:

        "pendingChapters": { "arrow": ["ch01.json"] }

    '보류'와 '망각'을 가르는 것이 이 선언의 목적이다(그 테스트 독스트링이 정본).
    """
    try:
        with open(os.path.join(os.path.dirname(ch_path), "index.json"), encoding="utf-8") as fh:
            declared = (json.load(fh).get("pendingChapters") or {}).get(list_name) or []
    except (OSError, ValueError, AttributeError):
        return set()
    return {str(x) for x in declared}


def subject_strict_list_names(ch_path):
    """이 과목이 `index.json` 에 **이름을 올린 규격 전부** (strict + pending 키의 합집합).

    ★ 열린 날 2026-08-07. 문제는 승격 레지스트리가 두 벌이라는 것이 아니라,
    **새 챕터 자동 잠금(`test_strict_promotion_covers_all_chapters`)이 한 벌만 덮고 있던 것**이다.
    2026-08-02 이후 신설된 규격은 **공통 목록을 두지 않는 것이 정책**이라
    (남의 과목 빌드를 멈추지 않으려고 — `subject_strict_chapters` 독스트링), 그 규격 전부가
    자동 잠금 밖에 있었다. 실측 2026-08-07: **열역학 15키 중 11 · 동역학 28키 중 24가 순회 밖.**
    그 검사가 막으려던 상황(새 챕터가 조용히 경고로만 남는 것)이 절반 이상에서 그대로였다.

    pending 키도 넣는 이유: 못 올렸다고 **선언한** 규격도 챕터가 늘면 따라와야 한다.
    선언만 해 두고 새 챕터를 빠뜨리면 그건 '보류'가 아니라 '망각'이다.
    """
    try:
        with open(os.path.join(os.path.dirname(ch_path), "index.json"), encoding="utf-8") as fh:
            data = json.load(fh) or {}
    except (OSError, ValueError, AttributeError):
        return set()
    return strict_list_names_in(data)


def strict_list_names_in(data):
    """선언 dict 에서 규격 이름만 뽑는다 — **파일 I/O 없는 순수 함수**(테스트가 직접 부른다).

    판정을 파일 읽기와 갈라 두는 이유: 실데이터가 전부 통과하는 상태에서는 회귀 단언이
    **공허하게 참**이 된다(선언을 못 읽어도 '빠진 것 없음' 이 나온다). 재현 케이스를 쓰려면
    판정만 따로 부를 수 있어야 한다.
    """
    names = set()
    for field in ("strictChapters", "pendingChapters"):
        names |= {str(k) for k in ((data or {}).get(field) or {})}
    return names


LEGACY_OPTIN_LIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "docs", "검사-기본값-기준선.txt")
_LEGACY_OPTIN_CACHE = {}


def legacy_optin_keys(path=LEGACY_OPTIN_LIST):
    """2026-08-15 «기본값 뒤집기» 시점에 **이미 있던** 검사 키. 그 파일이 정본이다.

    ★ 파일이 없으면 **빈 집합**이다 — 즉 «전부 새 키» 로 보아 기본 error 가 된다.
      반대로 두면(못 읽으면 전부 opt-in) **대장을 잃은 날 검사가 통째로 조용해진다** —
      이 리포가 반복해 겪은 침묵의 부류라, 못 읽을 때는 **엄한 쪽**으로 넘어진다.
    """
    if path not in _LEGACY_OPTIN_CACHE:
        keys = set()
        try:
            with open(path, encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.strip()
                    if line and not line.startswith("#"):
                        keys.add(line)
        except OSError:
            keys = set()
        _LEGACY_OPTIN_CACHE[path] = keys
    return _LEGACY_OPTIN_CACHE[path]


def subject_strict_waivers(ch_path):
    """그 과목이 «안 켜는 이유» 를 적은 자리 — `index.json` 의 `strictWaivers` (`{키: 사유}`).

    **사유 없는 줄은 면제로 안 친다** — `orphan-checks-allow.txt`·`저점-면제.txt` 와 같은 규율.
    그래야 «잊은 것» 과 «일부러 안 켠 것» 이 갈린다.
    """
    try:
        with open(os.path.join(os.path.dirname(ch_path), "index.json"), encoding="utf-8") as fh:
            declared = (json.load(fh) or {}).get("strictWaivers") or {}
    except (OSError, ValueError, AttributeError):
        return set()
    return {str(k) for k, v in declared.items() if str(v or "").strip()}


def is_strict_chapter(ch_path, names, list_name):
    """이 챕터에서 그 검사가 **error 인가**.

    ★★ **기본값을 뒤집었다 (2026-08-15, 사용자 지적).**
      [사용자 발화 인용 생략] —
      승격이 과목별 선언이라 검사 하나를 만들면 **과목 수만큼 선언을 적어야** 켜졌고,
      빠뜨린 과목은 **경고조차 없이 조용히 꺼진 채** 남았다(실측: 과목당 선언 키 39~51개).

      그래서 **새로 만드는 검사는 전 과목·전 챕터에서 기본 error** 다. 안 켜려면 그 과목이
      `strictWaivers` 에 **사유와 함께** 적는다.

    ★ **옛 키는 그대로 opt-in 이다** — `docs/검사-기본값-기준선.txt` 에 적힌 36개.
      과목마다 밀린 정리분이 다르고, **남의 빌드를 멈추는 승격은 승격이 아니다**
      (2026-08-02 실사고: 한 과목이 ch01~ch03 을 올리자 다른 과목 빌드가 깨졌다).
    """
    base = os.path.basename(ch_path)
    if base in (set(names) | subject_strict_chapters(ch_path, list_name)):
        return True
    if list_name in legacy_optin_keys():
        return False                      # 옛 키 — 선언해야 켜진다(예전 그대로)
    if base in subject_pending_chapters(ch_path, list_name):
        return False                      # 보류를 «선언» 했다 — 망각과 가른다
    return list_name not in subject_strict_waivers(ch_path)


# ★ 홑글자 `l` 은 길이 기호로 쓰지 않는다 — `ℓ`(`\ell`) 를 쓴다 (열린 날 2026-08-04).
#   사용자: [사용자 발화 인용 생략]. 실측이 그대로였다 —
#   본문 글꼴(Pretendard)에서 잉크 픽셀이 `l` **84** · `I` 112 · `1` 136 · `ℓ` **204** 로,
#   `l` 이 **모든 글자 중 가장 적은 민무늬 세로획**이고 폭도 `i` 와 같다(8.71). 기호로 안 읽힌다.
#   ★ `ℓ` 은 본문·등폭 두 스택 모두에 **실제 글리프**가 있다(등폭 폭 25.78 = 다른 글자와 동일).
#     반면 스크립트 v(U+1D4CB)는 두 스택 다 폭 32.57 로 튀어 **폴백**이라 채택하지 않았다.
#
#   판정: 앞뒤가 글자가 아닌 홑 `l`. 앞의 `\` 를 제외해 LaTeX 명령(`\left`·`\log`·`\lambda`·
#   `\ell` 자신)이 걸리지 않게 한다. 뒤에 `_`(첨자)가 와도 기호이므로 신고한다.
#   SVG 는 `<text>` 안만 본다 — path 명령의 `l`(상대 lineto)까지 잡으면 오탐이 쏟아진다.
_BARE_ELL = re.compile(r"(?<![A-Za-z\\])l(?![A-Za-z])")


def bare_ell_issues(node, trail="root", key=None):
    """길이 기호로 쓰인 홑글자 `l`. 순수 함수 — 테스트가 직접 부른다.

    순회는 스키마를 열거하지 않고 JSON 을 통째로 내려간다(`middot_list_issues` 와 같은 이유).
    """
    issues = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "svg":
                for txt in re.findall(r"<text\b[^>]*>(.*?)</text>", str(v), re.S):
                    for m in _BARE_ELL.finditer(re.sub(r"<[^>]*>", "", txt)):
                        issues.append(trail + "/svg: 홑글자 `l` 을 길이 기호로 썼다 — "
                                      + repr(txt[:40]) + " → `ℓ` 로 쓸 것")
                continue
            issues.extend(bare_ell_issues(v, trail + "/" + str(k), k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            issues.extend(bare_ell_issues(v, trail + "[" + str(i) + "]", key))
    elif isinstance(node, str):
        for m in _BARE_ELL.finditer(node):
            issues.append(trail + ": 홑글자 `l` 을 길이 기호로 썼다 — "
                          + repr(node[max(0, m.start() - 18):m.start() + 18])
                          + " → `ℓ`(산문·SVG) · `\\ell`(수식) 로 쓸 것")
    return issues


# ★ C36 — **기호 사이의 가운데점** (신설 2026-08-06).
#   사용자 지적: [사용자 발화 인용 생략] 전수해 보니 **한 글자에 세 가지 뜻이 겹쳐 있었다**:
#     ⑴ 물리량의 곱   `P·A` · `x·v_fg` · `g·Δz`
#     ⑵ 단위의 곱     `kJ/(kg·K)` · `kg·m/s²`     ← 이것만 정당하다
#     ⑶ 물리량 나열   `P_R·T_R` · `ke·pe` · `u·h`  ← **곱으로 읽힌다**
#   ⑶ 이 가장 위험하다 — 사용자가 식 나열에 대해 이미 같은 지적을 했다([사용자 발화 인용 생략], AGENTS 「표기 세부」). 그 지적은 **식 나열**만
#   닫았고 **기호 나열·기호 곱**은 열린 채였다.
#   ★ 규격: **물리량끼리는 곱이면 붙여 쓰고, 나열이면 쉼표. 가운데점은 단위의 곱에만.**
#   ★★ **2026-08-13 에 「공백(병치)」에서 「붙여 쓰기」로 뒤집혔다** — 사용자:
#     [사용자 발화 인용 생략]
#     규칙은 한 줄로 설명돼야 한다: **기호끼리의 곱은 붙이고, 연산자는 띄운다.**
#     그래서 이항 연산자(`+ - = < >`) 좌우와 **미분자 `d` 앞**(`P\,dV` — `d` 는 연산자다)의
#     공백은 남는다. 옛 문구를 남겨 두면 다음 세션이 처방을 보고 되돌리므로 함께 고쳤다.
#   ★ 판정은 **양옆이 둘 다 단위 토큰인가** 하나뿐이다. 곱인지 나열인지는 기계가 모르므로
#     처방을 둘 다 적어 사람이 고르게 한다 — 여기서 하나를 찍으면 나열이 곱으로 바뀐다.
#   ★★ 단위 판정은 **`UNIT_BASES` + `UNIT_PREFIXES` 하나뿐이다.** 처음에 여기에 목록을
#   새로 적었다가 `test_math_slash_fraction`(2026-08-02, 사용자 8회째 지적으로 열린 것)에
#   **곧바로 걸렸다** — 그 회귀가 [사용자 발화 인용 생략] 를 지키고 있다.
#   자를 두 벌 두면 갈라진다는 것을 이 리포가 이미 분수에서 겪었고, 그 교훈이 나를 막았다.
#   ★ `_is_unit_token` 을 그대로 부르지 않는 이유: 그 함수는 `_unit_notation == "mathrm"` 일 때
#     **항상 False** 를 돌려준다(그 모드에서는 호출부가 `\mathrm{}` 표시로 먼저 판정하기 때문).
#     이 검사는 산문·라벨의 날 텍스트를 보므로 그 게이트를 타면 단위가 전부 위반이 된다.
#     그래서 **판정 로직만 같은 등록부로 다시 쓴다** — 목록을 복제하는 것이 아니다.
def _middot_side_is_unit(token):
    bases = UNIT_BASES | UNIT_BASES_AMBIGUOUS_IN_SLASH      # 문맥이 가운데점이라 둘 다 본다
    return token in bases or (
        len(token) > 1 and token[0] in UNIT_PREFIXES and token[1:] in bases)



# ★ 토큰에 `{`·`}` 를 넣지 않는다 — 넣었더니 `\mathrm{kg·m}` 의 왼쪽이 `mathrm{kg` 로 잡혀
#   **단위의 곱이 오탐으로 신고**됐다(첫 실행 실측). 중괄호를 빼면 `kg` 만 남아 통과한다.
#   오늘 배운 것: *자가 낸 수치도 의심할 것* — 60건을 그대로 믿었으면 LaTeX 단위를 고쳤을 것이다.
SYMBOL_MIDDOT_RE = re.compile(
    r"([A-Za-zΑ-Ωα-ω][A-Za-z0-9_^]*)·([A-Za-zΑ-Ωα-ω][A-Za-z0-9_^]*)")

# ★★ 같은 점이 **LaTeX 로 적히면** 위 정규식이 못 본다 (2026-08-06, 데이터 전수 중 발견).
#   `\(v = v_f + x \cdot v_{fg}\)` 는 화면에서 `v = v_f + x·v_fg` 로 **똑같이** 그려지는데,
#   글자가 `\cdot` 이라 날 `·` 만 보는 자에게는 없는 것과 같았다. 실제로 산문 쪽 `x·v_fg` 를
#   전부 `x v_fg` 로 고친 뒤에도 **디스플레이 수식만 점을 달고 남아** 한 절 안에서 갈렸다 —
#   사용자가 처음 든 지적("어떤건 붙이고 어떤건 공백") 그 자체다.
#   ★ 판정은 **`\mathrm{}`(로만체) 안인가** 하나뿐이다. 이 리포는 단위를 언제나 로만체로 조판하므로
#     (`\mathrm{N \cdot m}` · `\mathrm{W/(m^2 \cdot °C)}`) 그 밖의 `\cdot` 은 물리량의 곱이다.
#     날 텍스트 쪽 판정(`UNIT_BASES`)을 여기 다시 쓰지 않는다 — 수식에는 이미 로만체라는
#     **저자가 선언한 표시**가 있어서, 이름으로 다시 추측하면 자가 둘로 갈린다.
#   ★ `\cdots`(줄임표)는 곱이 아니다 — 부분 문자열로 세면 그것까지 신고한다.
#     열역학 데이터에는 없어서 빌드가 조용했지만, 그 침묵은 *다른 과목에서 터질 것*을 뜻한다
#     (공통 도구가 한 과목에서만 도는 것을 확인하고 닫는 것이 이 리포의 반복 사고다).
#   ★★ **중첩 중괄호를 넘어야 한다** (열린 날 2026-08-25, 유체역학 ch01 에서 실측 7건).
#     첫 형태는 `\{[^{}]*\}` 라 **한 겹만** 봤다. 그런데 단위는 거의 언제나 지수를 달고,
#     지수는 중괄호다 — `\mathrm{kg/(m \cdot s^{2})}` 의 `^{2}` 에서 마스크가 끊겨
#     **로만체 안의 단위 곱이 「물리량의 곱」으로 신고**됐다. 열역학은 `\mathrm{N \cdot m}`
#     처럼 지수 없는 단위뿐이라 조용했다 — 바로 위 주석이 예고한 [사용자 발화 인용 생략] 다.
#     ★ 데이터를 고치는 쪽으로 가면 안 되는 자리다: 신고된 7건은 **전부 규격대로 쓴 것**이라
#       고치면 규격이 틀어진다(ee 의 `&#8722;` 8글자 오산과 같은 부류 — 자를 고친다).
#     한 겹 중첩까지 본다. 두 겹(`\mathrm{a^{b^{c}}}`)은 단위 표기에 안 나온다.
_LATEX_ROMAN_GROUP = re.compile(
    r"\\(?:mathrm|text|operatorname)\s*\{(?:[^{}]|\{[^{}]*\})*\}")
# ★★ **벡터의 내적에서 점은 곱이 아니라 연산자다** (열린 날 2026-08-07, 고체역학 §3 투영).
#   위 판정("로만체 밖의 `\cdot` 은 물리량의 곱")은 **열역학에 내적이 없어서** 성립했다.
#   벡터를 쓰는 과목에서 `\vec{F} \cdot \vec{n}` 을 병치로 고치면 뜻이 달라진다 —
#   `\vec{F}\vec{n}` 은 내적이 아니다. 처방을 따르면 데이터가 틀리게 되는 자리라 면제한다.
#   ★ `\cdots`(줄임표)를 열어 준 것과 **같은 부류**다: 한 과목에서만 돌려 보고 닫으면
#     다음 과목에서 터진다. 그 주석이 스스로 예고한 일이 실제로 일어났다.
#   ★★ **미분 기호가 앞에 붙은 벡터도 벡터다** (넓힘 2026-08-07, 동역학 §14.1 에서 실측).
#     처음 형태는 양쪽 피연산자가 **곧바로** `\vec{}`·`\mathbf{}` 로 시작할 때만 면제했는데,
#     일의 정의는 `\mathbf{F} \cdot d\mathbf{r}` 이라 오른쪽이 `d` 로 시작한다. 그래서
#     면제에 걸리지 않았다 — 미소 변위는 벡터가 아니라고 말하는 셈이다.
_VEC = r"(?:\\mathrm\s*\{?d\}?\s*|[dδ∂]\s*)?\\(?:vec|hat|mathbf|boldsymbol)\s*\{[^{}]*\}"
_LATEX_VECTOR_DOT = re.compile(_VEC + r"\s*\\cdot\s*" + _VEC)
_LATEX_CDOT = re.compile(r"\\cdot(?![A-Za-z])")


def latex_cdot_hits(text):
    """`\\mathrm{}` **밖**에 있는 `\\cdot` 의 개수. 순수 함수 — 테스트가 직접 부른다.

    로만체(단위)와 **벡터 사이의 내적**은 세지 않는다 — 둘 다 점이 표기의 일부다.
    """
    masked = _LATEX_ROMAN_GROUP.sub(" ", text)
    return len(_LATEX_CDOT.findall(_LATEX_VECTOR_DOT.sub(" ", masked)))


# ★ 처방을 **자와 같은 파일에** 둔다 (2026-08-07). 위 검사가 신고만 하고 고치는 쪽이 없으면
#   과목마다 손으로 고치게 되고, 손으로 고치면 `\,` 과 `\times` 가 삽화·풀이마다 갈린다 —
#   그 갈림이 이 검사가 없애려던 결함([사용자 발화 인용 생략])과 같은 부류다.
#   판정선 하나: **숫자가 한쪽에라도 닿으면 `\times`, 그 밖은 병치(`\,`)**.
#   왜 숫자만 예외인가 — 병치는 '이어 쓰면 곱'이라는 관례인데 `2 0` 이나 `3 3C` 는 그 관례가
#   깨진다(한 수로 읽힌다). 기호끼리는 `e^{-2x} e^{x}` 처럼 이어 써도 읽히므로 병치가 맞다.
_CDOT_NUM_BEFORE = re.compile(r"[0-9]\s*$")
_CDOT_NUM_AFTER = re.compile(r"^\s*[0-9]")


def latex_cdot_fix(text):
    """`\\cdot` 을 병치/`\\times` 로 바꾼 글과 바뀐 자리 미리보기. 순수 함수 — 테스트가 직접 부른다.

    `\\mathrm{}`(단위) 안은 건드리지 않는다 — 거기서는 가운데점이 규격이다.
    """
    if not isinstance(text, str) or "\\cdot" not in text:
        return text, []
    # 로만체 구간을 같은 길이의 가림막으로 덮어 **오프셋을 유지**한다(마스킹 자리에서 재판정 금지).
    masked = _LATEX_ROMAN_GROUP.sub(lambda m: " " * len(m.group(0)), text)
    # ★★ **자가 안 세는 것은 처방도 고치면 안 된다** (열린 날 2026-08-07, 동역학에서 실측).
    #   `latex_cdot_hits` 는 벡터 내적을 면제하는데 이 함수는 안 했다. 그래서 검사는 **0건**인데
    #   `tools/fix_cdot.py` 는 같은 자리를 1건으로 보고했고, `--apply` 했으면
    #   `\mathbf{F}\cdot d\mathbf{r}` 이 `\mathbf{F}\,d\mathbf{r}` 로 바뀌어 **내적이 곱이 됐다.**
    #   ★ 이 리포가 반복해 닫은 부류의 **뒤집힌 얼굴**이다 — 늘 '자는 신고하는데 처방이 없다'
    #     쪽이었고, 이번은 '자는 통과시키는데 처방이 고친다' 쪽이다. 어느 쪽이든 원인은 하나:
    #     **판정이 두 곳에 있다.** 그래서 같은 가림막을 여기서도 쓴다.
    masked = _LATEX_VECTOR_DOT.sub(lambda m: " " * len(m.group(0)), masked)
    out, hits, pos = [], [], 0
    for m in _LATEX_CDOT.finditer(masked):
        before, after = text[pos:m.start()], text[m.end():]
        numeric = bool(_CDOT_NUM_BEFORE.search(before) or _CDOT_NUM_AFTER.match(after))
        out.append(before)
        out.append(" \\times " if numeric else "\\,")
        hits.append("…" + text[max(0, m.start() - 22):m.end() + 18].strip() + "…")
        pos = m.end()
    out.append(text[pos:])
    fixed = "".join(out)
    # 바꾼 자리 주변의 공백이 겹칠 수 있다 — `a \times  b` 처럼 두 칸이 남지 않게 정리한다.
    fixed = re.sub(r"\\times\s+", "\\\\times ", fixed)
    fixed = re.sub(r"\s+\\times", " \\\\times", fixed)
    fixed = re.sub(r"\\,\s+", "\\\\,", fixed)
    return fixed, hits


def symbol_middot_issues(node, trail="root", key=None):
    """C36 — 기호 사이의 가운데점. 순수 함수 — 테스트가 직접 부른다.

    순회는 `middot_list_issues` 와 같은 이유로 스키마를 열거하지 않고 JSON 을 통째로 내려간다.
    면제 키도 같은 것을 쓴다(`sourceRef` 의 `(p.108)·Moran §3.2` 는 출처 나열이지 곱이 아니다).
    날 `·` 과 LaTeX `\\cdot` 을 **한 검사에서** 본다 — 화면에 그려지는 것이 같은 점이라
    자를 둘로 나누면 한쪽만 고쳐 놓고 닫았다고 하게 된다.
    """
    issues = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k in MIDDOT_EXEMPT_KEYS:
                continue
            issues.extend(symbol_middot_issues(v, trail + "/" + str(k), k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            issues.extend(symbol_middot_issues(v, trail + "[" + str(i) + "]", key))
    elif isinstance(node, str):
        for m in SYMBOL_MIDDOT_RE.finditer(node):
            if _middot_side_is_unit(m.group(1)) and _middot_side_is_unit(m.group(2)):
                continue                      # 단위의 곱 — 가운데점이 맞는 유일한 자리
            issues.append(
                trail + ": 기호 사이의 가운데점 — " + repr(m.group(0))
                + " → **곱이면 붙여 쓰고**(PAds), **나열이면 쉼표**(P_R, T_R)."
                + " 가운데점은 단위의 곱에만 쓴다 (kJ/(kg·K))")
        for _ in range(latex_cdot_hits(node)):
            issues.append(
                trail + ": 수식의 `\\cdot` — 화면에는 산문의 `·` 와 똑같은 점으로 그려진다."
                + " 물리량의 곱은 병치로 쓸 것 (`x \\cdot v_{fg}` → `x v_{fg}`)."
                + " 단위의 곱은 로만체 안에 둔다 (`\\mathrm{N \\cdot m}`)")
    return issues


# ── C37 문항 수치 ───────────────────────────────────────────────────────────
# 한 자리 정수는 상태점 라벨(1, 2)·소문제 번호라 수치로 세지 않는다.
# 그것까지 세면 P-V 선도가 전부 신고되어 진짜 어긋남이 묻힌다.
_PROBLEM_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_TEXT_ELEMENT = re.compile(r"<text\b.*?</text>", re.S)
_ANY_TAG = re.compile(r"<[^>]*>")


def problem_numbers(text):
    """문자열에서 비교할 만한 수치만 뽑는다. 순수 함수 — 테스트가 직접 부른다."""
    out = set()
    for raw in _PROBLEM_NUM.findall(text or ""):
        tok = raw.replace(",", "")
        try:
            val = float(tok)
        except ValueError:
            continue
        if "." not in tok and val < 10:
            continue                            # 상태점·소문제 라벨
        out.add(f"{val:.10g}")                   # 0.0620 과 0.062 를 같게 본다
    return out


def _svg_shown_numbers(svg):
    """SVG 의 **글자**에 실제로 보이는 수치. 좌표·굵기는 대상이 아니다."""
    shown = [_ANY_TAG.sub("", c) for c in _TEXT_ELEMENT.findall(svg or "")]
    return problem_numbers(" ".join(shown))


def _item_numbers(item):
    """이 문항이 지문·풀이·답·해설에서 '알고 있는' 수치 전부."""
    parts = []
    for k in ("prompt", "solutionTemplate", "answer", "hint", "expectedOutput"):
        v = item.get(k)
        if isinstance(v, str):
            parts.append(v)
    outline = item.get("solutionOutline")
    if isinstance(outline, list):
        parts += [s for s in outline if isinstance(s, str)]
    elif isinstance(outline, str):
        parts.append(outline)
    for blank in item.get("blanks") or []:
        if isinstance(blank, dict):
            parts += [blank.get(k) or "" for k in ("answer", "explanation", "hint")]
    return problem_numbers(" ".join(p for p in parts if isinstance(p, str)))


def problem_number_issues(ch):
    """C37 — 문항의 조건 수치가 삽화·정답과 어긋난 자리. 순수 함수 — 테스트가 직접 부른다.

    열린 날 2026-08-07. **무엇이 새어나갔나:** 열역학 `ch04-p01` 의 지문은
    `P = 320 kPa, V₁ = 0.015, V₂ = 0.062 m³`(답 15.0 kJ)인데 `expectedOutput` 은
    `6.00 kJ` 였고 삽화는 `200 kPa · 0.02 · 0.05` 를 그리고 있었다. **지문의 숫자만
    나중에 바뀌고 답과 삽화가 따라오지 않은 것**이다. 독자는 지문과 다른 조건이 그려진
    그림을 보고 푼다 — 답이 안 맞는 이유를 자기 계산에서 찾게 된다.

    빌드가 통과시킨 이유는 단순하다: 세 자리(지문·답·삽화)가 **서로를 전혀 안 본다.**
    각각은 문법적으로 멀쩡한 문자열이라 어느 검사에도 걸리지 않았다.

    ★ 자를 좁게 잡았다 — **'삽화가 문항 수치를 하나도 안 그린다'** 일 때만 신고한다.
      처음에는 '문항에 없는 값이 삽화에 있으면' 으로 넓게 잡았는데 실측 7건 중 **5건이
      오탐**이었다: `fig-ch01-q04-situation` 의 `나머지 55%` 는 45% 의 나머지이고,
      `fig-ch01-q07-situation` 의 `10·20·30·40` 은 온도 눈금이다. 둘 다 삽화가 만들어 낸
      정당한 수치다. 오탐이 다수인 검사는 읽히지 않게 되므로(라벨 여백 자 391건 중 91건
      오탐 선례) 교집합이 **빈** 경우로 좁혔다.
    ☞ 그래서 조건 셋 중 하나만 바꾸고 삽화를 안 고친 경우는 못 잡는다. 그건
      `tools/audit_problem_numbers.py` 가 `[참고]` 로 따로 낸다 — 검사는 확실한 것만 막고
      애매한 것은 감사가 사람에게 넘긴다.
    """
    issues = []
    for coll in ("practice", "problems"):
        for item in ch.get(coll) or []:
            if not isinstance(item, dict):
                continue
            pid = item.get("id", "?")
            known = _item_numbers(item)

            exp = item.get("expectedOutput")
            if isinstance(exp, str) and exp:
                # expectedOutput 자신은 known 에 들어 있으므로 나머지와 대조한다.
                rest = _item_numbers({k: v for k, v in item.items()
                                      if k != "expectedOutput"})
                stray = sorted(problem_numbers(exp) - rest)
                if stray and rest:
                    issues.append(
                        coll + "/" + pid + ": expectedOutput 의 수치 "
                        + ", ".join(stray) + " 가 지문·풀이·정답 어디에도 없다"
                        + " — 조건을 바꾸고 정답 줄을 안 고쳤는지 볼 것")

            for fig in item.get("diagrams") or []:
                if not isinstance(fig, dict):
                    continue
                if fig.get("numericLabels") != "intentional":
                    continue
                shown = _svg_shown_numbers(fig.get("svg", ""))
                if shown and known and not (shown & known):
                    issues.append(
                        coll + "/" + pid + "/" + fig.get("id", "?")
                        + ": 조건 수치를 박은 삽화인데 문항의 수치를 **하나도** 안 그린다"
                        + " (삽화 " + ", ".join(sorted(shown)[:6])
                        + " / 문항 " + ", ".join(sorted(known)[:6]) + ")"
                        + " — 지문을 바꾸고 삽화를 안 고쳤는지 볼 것")
    return issues


def middot_list_issues(node, trail="root", key=None):
    """가운데점으로 3항목 이상을 나열한 자리. 순수 함수 — 테스트가 직접 부른다.

    순회는 스키마를 열거하지 않고 JSON 을 통째로 내려간다(`inline_math_issues` 와 같은 이유 —
    필드 목록을 손으로 적으면 새 필드가 생길 때 사각지대가 다시 열린다).
    """
    issues = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k in MIDDOT_EXEMPT_KEYS:
                continue
            issues.extend(middot_list_issues(v, trail + "/" + str(k), k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            issues.extend(middot_list_issues(v, trail + "[" + str(i) + "]", key))
    elif isinstance(node, str):
        for m in MIDDOT_RUN_RE.finditer(node):
            issues.append(trail + ": 가운데점으로 3항목 이상을 나열했다 — " + repr(m.group(0))
                          + " → 쉼표로 나열할 것 (2항목 가운데점은 그대로 둔다)")
    return issues


# ★ C40. **수식 바로 뒤의 줄표는 콜론** (신설 2026-08-07, 동역학 ch12 9절에서 열림).
#
#   사용자: [사용자 발화 인용 생략]. **같은 메시지에서** 절 제목의 줄표
#   ([사용자 발화 인용 생략])는 [사용자 발화 인용 생략] 라고 못 박았다 —
#   즉 문제는 줄표가 아니라 **줄표가 놓인 자리**다.
#   ★ 왜 그 자리에서만 불편한가: 바로 앞에 `= -\dot{\theta}\,\mathbf{u}_r` 처럼 **진짜
#     마이너스**가 있으면, 눈은 같은 높이·같은 굵기의 짧은 가로줄을 하나 더 보고 **연산자로
#     읽는다.** 산문 뒤라면 그렇게 읽힐 여지가 없다. 판정선은 [사용자 발화 인용 생략] 하나다.
#   ★ **새 규격이 아니다.** 이 문형은 `수식(레이블) → 설명(값)` 이고, AGENTS 표기 세부가
#     [사용자 발화 인용 생략] 이라고 이미 정해 두었다. 수식 뒤라는 이유로
#     아무도 그 자를 대지 않았을 뿐이다 — 실측 동역학 3챕터 11곳.
#   ★ 콜론 뒤 공백까지 함께 본다. 줄표를 콜론으로 바꾸면서 공백을 빠뜨리기 쉬운데
#     (실제로 한 번 그렇게 났다) AGENTS 는 [사용자 발화 인용 생략] 이라고 정해 두었다.
#   처방은 `python tools/fix_math_label_dash.py --apply` — 손으로 고치면 일부가 남는다.
#   ★ **양옆 공백을 요구한다 — 붙여 쓴 줄표는 합성어다.** 실측에서 걸린 오탐이
#     `\(F\cos\theta\)–s 곡선`(가로축 이름 둘을 이은 말)이었다. 거기서 콜론으로 바꾸면
#     [사용자 발화 인용 생략] 이 되어 뜻이 사라진다. 레이블 구분자는 언제나 띄어 쓰므로
#     공백이 판정선이 된다 — 자를 넓게 잡아 처방을 돌리면 **멀쩡한 말을 고친다.**
MATH_LABEL_DASH_RE = re.compile(r"\\\)[ \t]+[–—][ \t]+")
MATH_LABEL_COLON_RE = re.compile(r"\\\):(?=\S)")


# 화면에 안 나가는 제작 메모·식별자. 말투 검사(C23)가 이미 같은 판정을 하고 있으므로
# **같은 목록을 쓴다** — 두 자가 서로 다른 답을 내면 한쪽은 반드시 사각지대가 된다.
MATH_LABEL_EXEMPT_KEYS = {"id", "sourceRef", "source", "sourcePages", "href", "svg",
                          "rationale", "changeNote", "teachingTips", "supplementNotes",
                          "lintWaivers", "noDiagramReason"}


def _label_snip(text, i, j, pad=20):
    return "…" + text[max(0, i - pad):j + pad].replace("\n", "\\n") + "…"


def math_label_dash_hits(text):
    r"""수식 끝 `\)` 뒤에 줄표가 붙었거나 콜론 뒤 공백이 없는 자리. 순수 함수."""
    out = []
    for rx in (MATH_LABEL_DASH_RE, MATH_LABEL_COLON_RE):
        for m in rx.finditer(text):
            out.append(_label_snip(text, m.start(), m.end()))
    return out


def math_label_dash_fix(text):
    r"""`\\) – 설명` → `\\): 설명`. (고친 문자열, 바뀐 자리 목록) 을 돌려준다.

    검사(`math_label_dash_hits`)와 **같은 정규식**을 쓴다 — 자와 처방이 갈리면
    감사는 0건인데 화면은 그대로인 상태가 만들어진다(이 리포가 반복해 만난 형태다).
    """
    hits = math_label_dash_hits(text)
    if not hits:
        return text, []
    fixed = MATH_LABEL_DASH_RE.sub("\\\\): ", text)
    fixed = MATH_LABEL_COLON_RE.sub("\\\\): ", fixed)
    return fixed, hits


def math_label_dash_issues(node, trail="root", key=None):
    """C40 — 트리를 통째로 내려간다(`middot_list_issues` 와 같은 이유)."""
    issues = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k in MATH_LABEL_EXEMPT_KEYS:      # 화면에 안 나가는 제작 메모는 대상이 아니다
                continue
            issues.extend(math_label_dash_issues(v, trail + "/" + str(k), k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            issues.extend(math_label_dash_issues(v, trail + "[" + str(i) + "]", key))
    elif isinstance(node, str):
        for snip in math_label_dash_hits(node):
            issues.append(trail + ": 수식 뒤의 줄표는 마이너스로 읽힌다 — " + snip
                          + " → `\\): ` 로 (python tools/fix_math_label_dash.py --apply)")
    return issues


# ★ C41. **용어 한영 병기** (신설 2026-08-07, 동역학 ch13 에서 열림).
#
#   사용자: [사용자 발화 인용 생략]
#   ★★ **실측 — 시스템으로 안 올라와 있었다.** 빌드에 병기 검사가 하나도 없었고,
#     `audit_content` §5 「한영 병기 용어」는 *이미 병기된 것*을 세어 링크 후보로 보여줄 뿐
#     **빠진 것을 찾지 않는다.** 즉 열역학이 지켜 온 것은 규칙이 아니라 **습관**이었고,
#     습관은 과목이 바뀌면 끊긴다 — 정확히 이번 일이다(동역학 ch14 는 병기가 **0건**이었다).
#   ★ 목록은 **과목이 갖는다**(`data/<과목>/terms.json`). 공통 코드가 용어를 알면 다른 과목이
#     못 쓴다(AGENTS 「공통 도구에 과목별 사실을 박지 않는다」). 파일이 없으면 그 과목은
#     아직 선언하지 않은 것이라 검사가 돌지 않는다 — **폴백 목록을 두지 않는다.**
#   ★ 판정은 **그 챕터 안의 첫 등장**이다. 앞 장에서 병기했더라도 그 장부터 읽는 독자가 있고,
#     이 리포의 기본 독자는 [사용자 발화 인용 생략] 이다(AGENTS 「목표 독자」).
#   ★ 제목·표제·키워드에서는 찾지 않는다. 거기는 짧은 이름표라 괄호를 넣을 자리가 아니고,
#     첫 등장을 거기서 세면 본문 병기가 **있는데도** 어긋난 것으로 잡힌다.
TERM_SEARCH_EXEMPT_KEYS = {"heading", "title", "chapterTitle", "keywords", "label", "name",
                           "anchorText", "gradingKeywords", "topic", "appliesTo"}


def _term_prose(node, key=None, out=None):
    """용어의 첫 등장을 찾을 **본문 산문**만 문서 순서대로 모은다."""
    if out is None:
        out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k in MATH_LABEL_EXEMPT_KEYS or k in TERM_SEARCH_EXEMPT_KEYS:
                continue
            _term_prose(v, k, out)
    elif isinstance(node, list):
        for v in node:
            _term_prose(v, key, out)
    elif isinstance(node, str):
        out.append(node)
    return out


# ★ C42. **분수 안의 분수는 뷰어가 못 그린다** (신설 2026-08-07, 동역학 ch13 8절).
#
#   사용자: [사용자 발화 인용 생략] — 화면에 `tan ψ = \fracr` 이라는
#   **날 LaTeX 이 찍혀 있었다.** 데이터는 멀쩡했다(`\tan\psi = \frac{r}{\frac{dr}{d\theta}}`).
#   ★★ **범인은 렌더러다.** `renderMath` 의 분수 규칙이 `\\frac\{([^{}]*)\}\{([^{}]*)\}` 라
#     **인자 안에 중괄호를 하나도 허용하지 않는다.** 그래서 안쪽 분수만 매치되고 바깥 `\frac` 은
#     글자로 남는다. 브라우저 실측으로 확인했다(아래 넷은 전부 정상 — 오직 중첩만 깨진다):
#       `\frac{v^{2}}{\rho}` · `\frac{\dot{r}}{2}` · `\frac{\sqrt{2}}{3}` · `\frac{\mathbf{u}_r}{2}`
#     이유는 위/아래첨자·근호·굵은 글자가 **분수보다 먼저** 치환돼 그때는 중괄호가 이미 없기
#     때문이다. 즉 금지할 것은 '중괄호'가 아니라 **`\frac` 안의 `\frac`** 하나다.
#   ★ **전 과목 error 다** — C38·C39 와 같이 *뷰어가 그 값을 그릴 수 있는가*의 계약이라
#     승격 목록을 두지 않는다. 이 부류(뷰어가 못 읽는 값을 아무도 안 보는 것)로 열린 것이
#     `solutionOutline`(2026-08-04) · `name`(2026-08-06) · `chapterTitle`·`description`
#     (2026-08-07) 에 이어 **다섯 번째**다.
#   처방: 한 겹으로 편다. `\frac{r}{\frac{dr}{d\theta}}` → `\frac{r\,d\theta}{dr}`.
def _brace_group_end(text, i):
    """text[i] 가 `{` 면 짝이 맞는 `}` 다음 위치를, 아니면 None 을 돌려준다."""
    if i >= len(text) or text[i] != "{":
        return None
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return j + 1
    return None


def nested_frac_hits(text):
    r"""`\frac` 의 인자 안에 또 `\frac` 이 든 자리. 순수 함수 — 테스트가 직접 부른다."""
    out, k = [], 0
    while True:
        k = text.find("\\frac", k)
        if k < 0:
            return out
        num_end = _brace_group_end(text, k + 5)
        den_end = _brace_group_end(text, num_end) if num_end else None
        if den_end and "\\frac" in text[k + 5:den_end]:
            out.append(text[k:den_end])
        k += 5


def nested_frac_issues(node, trail="root", key=None):
    """C42 — 트리를 통째로 내려간다(`inline_math_issues` 와 같은 이유)."""
    issues = []
    if isinstance(node, dict):
        for k, v in node.items():
            issues.extend(nested_frac_issues(v, trail + "/" + str(k), k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            issues.extend(nested_frac_issues(v, trail + "[" + str(i) + "]", key))
    elif isinstance(node, str):
        for hit in nested_frac_hits(node):
            issues.append(trail + ": 분수 안의 분수는 renderMath 가 못 그린다 — " + repr(hit)
                          + " → 한 겹으로 펼 것 (`\\frac{a}{\\frac{b}{c}}` = `\\frac{a c}{b}`)")
    return issues


def subject_terms(ch_path):
    """`data/<과목>/terms.json` 의 병기 목록. 없으면 빈 dict (선언 안 한 과목)."""
    return _terms_section(ch_path, "terms")


def _terms_raw(ch_path, key):
    path = os.path.join(os.path.dirname(ch_path), "terms.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get(key)


def _terms_section(ch_path, key):
    got = _terms_raw(ch_path, key)
    return got if isinstance(got, dict) else {}


def _terms_list(ch_path, key):
    got = _terms_raw(ch_path, key)
    return tuple(got) if isinstance(got, list) else ()


# ★★ C44. **한 글자가 두 물리량을 뜻할 때 어느 쪽이 어느 표기인가** (신설 2026-08-12, 부류 2·12).
#
#   사용자: [사용자 발화 인용 생략] — 2026-08-08 판정(부피를 필기체)을
#   뒤집은 것이다. 논거가 더 강하다: `v`(비체적)와 `V`(부피)는 **대소문자가 곧 「비(比)」의 표시**라
#   그 쌍을 깨면 안 된다.
#
#   ★★ **무엇이 새어나갔나 — 표기 결정이 「지키는 사람의 기억」에만 있었다.**
#     2026-08-08 결정은 `terms.json` 의 `_how` 에 **산문으로** 적혔고 검사가 없었다. 그래서
#     ⑴ 실제로 옮긴 것은 **ch05 한 챕터뿐**이고 ⑵ 나머지 챕터는 옛 표기 그대로였는데
#     **빌드가 아무 말도 안 했다.** 결정을 뒤집은 지금도 같은 구조면 또 한 챕터만 바뀐다.
#
#   ★ 판정 근거는 **저자 선언**이다 — `variables` 의 값이 무슨 물리량인지 말하고 있고,
#     `terms.json` 의 `symbols` 가 그 물리량의 표기를 말한다. 둘을 대조하면 기계가 판정할 수 있다.
#     식·산문 속의 `V` 가 부피인지 속도인지는 **기계가 모른다** — 그건 사람과
#     `tools/fix_velocity_symbol.py` 의 확정 패턴이 맡는다(그 도구 독스트링이 정본).
#   ★ 목록은 **과목이 갖는다**. `symbols` 가 없는 과목에서는 검사가 돌지 않는다 —
#     폴백을 두지 않는다(AGENTS 「공통 도구에 과목별 사실을 박지 않는다」).
#   ★ 선언으로 세는 자리는 **단위 괄호 바로 앞의 한글 낱말** 하나다. 값 아무 데나 나오는
#     낱말을 세면 [사용자 발화 인용 생략] 이 부피 선언으로 잡힌다 — 실제 데이터에 있다.
#     `가속도` 처럼 역할 이름을 품은 남의 낱말은 과목이 `symbolNotRoles` 에 적어 뺀다.
_ROLE_WORD = re.compile(r"([가-힣]+)\s*\(")


def _symbol_base(token):
    """`V_{1}`·`\\dot{V}`·`\\mathcal{V},\\ ` → 밑기호. 첨자·점·공백 표기를 벗긴다."""
    t = token.strip().strip(",").replace("\\ ", "").strip()
    t = re.sub(r"\\dot\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"[_^]\{[^{}]*\}", "", t)
    t = re.sub(r"[_^].", "", t)
    return t.strip()


def declared_roles(variables, symbols, not_roles=()):
    """[(키 조각, 역할)] — `variables` 가 선언한 것. 순수 함수.

    ★ **이 함수가 유일한 자다.** C44 와 `tools/fix_velocity_symbol.py` 가 둘 다 여기를 부른다 —
      한때 도구가 같은 판정을 복사해 갖고 있었고, 그래서 검사만 고쳤을 때
      `"V_{1}, V_{2}"` 를 **검사는 신고하는데 도구는 안 옮기는** 상태가 실제로 났다.
    """
    skip = set(not_roles)
    wanted = set(symbols)
    out = []
    for key, val in (variables or {}).items():
        words = [w for w in _ROLE_WORD.findall(str(val)) if w not in skip]
        roles = []
        for w in words:
            # 역할 이름으로 **끝나는** 낱말만 선언으로 본다(`평균속도` ○ · `가속도` 는 위에서 뺀다).
            hit = [r for r in wanted if w.endswith(r)]
            roles.append(max(hit, key=len) if hit else None)
        keys = [k for k in str(key).split(",") if k.strip()]
        if len(keys) != len(roles):
            # ★ 한 뜻을 여러 첨자가 나눠 쓰는 자리는 짝이 안 맞아도 판정할 수 있다 —
            #   `"V_{1}, V_{2}": "(처음, 나중) 속도 (m/s)"` 가 그렇다(실측 ch02·ch05).
            #   조건은 **기호가 더 많을 때**뿐이다. 반대로 뜻이 더 많으면 그건 한 항목이
            #   남의 기호까지 설명하는 것이라 붙이면 안 된다 — 실측 ch04:
            #   `"m": "질량 (kg), v는 비체적 (m³/kg)"` 가 `m` 을 비체적으로 잡았다(오탐).
            only = [r for r in roles if r]
            if (len(keys) > len(roles) and len(only) == 1
                    and len({_symbol_base(k) for k in keys}) == 1):
                roles = only * len(keys)
            else:
                continue          # 그 밖에는 어느 기호가 어느 뜻인지 기계가 모른다
        for k, role in zip(keys, roles):
            if role:
                out.append((k, role))
    return out


# ★★ C45. **산문·삽화에서 역할 낱말 바로 뒤에 오는 기호** (신설 2026-08-12).
#
#   ★ 왜 C44 만으로는 부족한가 — C44 는 `variables` **선언만** 본다. 그래서 산문이나 삽화가
#     [사용자 발화 인용 생략] 라고 적어도 아무 말이 없다. 실제로 그 상태가 났다: 2026-08-12 에
#     속도를 필기체로 옮기며 카드 단위로 치환했는데, **선언이 없는 산문 두 자리**가 부피를
#     속도 기호로 적은 채 남았고 **사람 눈으로만** 발견됐다(ch05 이론 3절 · 그 절의 삽화).
#   ★ 판정선은 **저자가 낱말로 뜻을 밝혀 둔 자리**다. `부피 𝒱` 처럼 역할 낱말 바로 뒤에
#     기호가 오면 그 기호가 무엇을 뜻하는지 저자가 스스로 말한 것이다 — 기계가 문맥을
#     추측하지 않아도 된다. 그 밖의 자리(맨 `V`)는 여전히 사람과 도구의 몫이다.
#   ★ **알려진 기호가 왔을 때만 판정한다.** `속도 성분`·`부피 변화` 처럼 낱말이 이어지면
#     대상이 아니다. 이 한 줄이 오탐을 거의 없앤다.
_ROLE_THEN_SYMBOL = re.compile(r"([가-힣]+)\s{0,2}(?:\\\(\s*)?"
                               r"(\\[A-Za-z]+\{[A-Za-z]\}|[^\s가-힣()\[\]{}<>,.·—:;=+\\])")


def symbol_role_word_issues(ch, symbols, not_roles=(), glyphs=None):
    """C45 — 역할 낱말 옆의 기호가 그 역할의 표기인가. 순수 함수 — 테스트가 직접 부른다."""
    if not symbols:
        return []
    glyphs = glyphs or {}
    to_macro = {g: m for m, g in glyphs.items()}
    known = {_symbol_base(s) for s in symbols.values()}
    skip = set(not_roles)
    issues = []
    for where, text in iter_visible_texts(ch):
        for word, token in _ROLE_THEN_SYMBOL.findall(str(text)):
            if word in skip:
                continue
            hit = [r for r in symbols if word.endswith(r)]
            if not hit:
                continue
            role = max(hit, key=len)
            got = _symbol_base(to_macro.get(token, token))
            if got not in known or got == _symbol_base(symbols[role]):
                continue          # 기호가 아니거나 맞게 적혔다
            issues.append(where + ": '" + word + " " + token + "' — 이 과목에서 " + role
                          + "는 `" + symbols[role] + "` 로 적는다. 저자가 낱말로 뜻을 밝힌"
                          " 자리라 기호가 어긋난 것이 분명하다 (terms.json 의 symbols 가 정본)")
    return issues


# ★★ C46 — **한 항목 안에서 같은 형태가 두 표기로 갈린 자리** (열린 날 2026-08-12).
#
# 사용자가 검수하며 같은 부류를 여섯 번 짚었다: [사용자 발화 인용 생략] · [사용자 발화 인용 생략] · [사용자 발화 인용 생략] · [사용자 발화 인용 생략].
#
# ★ **왜 C44·C45 가 이걸 못 봤나 — 둘 다 「저자가 선언한 자리」만 본다.**
#   C44 는 `variables` 선언을, C45 는 역할 낱말 바로 뒤를 본다. 그런데 실제 누락은
#   **선언이 없는 자리**(문풀·힌트·답 슬롯 옆·삽화 라벨·칩)에 몰려 있었다. 자가 못 보는
#   자리는 도구도 안 옮기므로(둘이 같은 함수를 쓴다) 매 회차 그대로 남는다.
#
# ★ **이 자는 과목 사실을 몰라도 된다.** 판정은 [사용자 발화 인용 생략] 하나다. 실측 사례:
#     ch05 유도 4  — `latex` 는 `\mathcal{V}^{2}` 인데 `variables` 키만 `V^{2}`
#     ch05 5.5 삽화 — 한 삽화 안에 `𝒱₁` 과 `V₁` 이 함께 있다
#   즉 **저자가 이미 한 자리에서 답을 적어 두었으므로** 기계가 문맥을 추측할 필요가 없다.
#
# ※ 오탐 여지는 남는다 — 같은 꼬리를 쓰는 **다른 물리량**이 한 항목에 있을 때다
#   (`V₁` 이 상태 1의 부피, `𝒱₁` 이 상태 1의 속도). 그래서 이 자는 **신고까지만** 하고
#   도구는 목록으로 낸다. 0건이던 자리에 목록이 생기는 것이 이 검사의 목적이다.
_SYMBOL_TAIL = r"(?:[_^]\{[^{}]*\}|[_^][A-Za-z0-9]|[\u2080-\u2089\u00b2\u00b3\u00b9\u2070\u2074-\u2079]+)*"


def symbol_masked(text, symbols, glyphs=None):
    """선언된 표기(`\\mathcal{V}`·`\\dot{V}`·글리프)를 **길이를 지키며** 가린 사본. 순수 함수.

    좌표가 원문과 1:1이라 처방이 같은 자리를 그대로 고칠 수 있다(`mask_inline_math` 와 같은 처방).
    """
    # ★ **맨 글자 표기는 가리지 않는다.** `symbols` 에는 `부피: V` 처럼 장식 없는 선언도 있어서,
    #   그것까지 가리면 **찾으려던 맨 `V` 가 통째로 사라져 검사가 0건이 된다**(실측 2026-08-12 —
    #   가리기를 넣자마자 전 챕터가 조용해졌다. 0건이 '없다'가 아니라 '안 봤다'였던 그 모양이다).
    forms = [f for f in (set(symbols.values()) | set((glyphs or {}).values()))
             if not (len(f) == 1 and f.isascii())]
    out = str(text)
    for form in sorted(forms, key=len, reverse=True):
        out = out.replace(form, "\x00" * len(form))
    return out


def symbol_split_hits(item, symbols, glyphs=None):
    """[(맨 표기, 선언 표기, 꼬리)] — 한 항목 안에서 갈린 자리. 순수 함수."""
    if not symbols:
        return []
    glyphs = glyphs or {}
    text = "\n".join(_item_strings(item))
    out = []
    for role, want in symbols.items():
        letter = _symbol_base(want)
        bare = re.sub(r"\\[A-Za-z]+\{([A-Za-z])\}", r"\1", letter)
        if bare == letter:
            continue                  # 맨 글자 그대로 쓰는 역할(부피 `V`)은 갈릴 것이 없다
        forms = [f for f in (letter, glyphs.get(want)) if f]
        right = set()
        for form in forms:
            right.update(re.findall("(?:" + re.escape(form) + ")(" + _SYMBOL_TAIL + ")", text))
        if not right:
            continue                  # 이 항목에는 선언 표기가 없다 — 갈릴 짝이 없다
        # ★ **선언된 표기를 먼저 가린다.** 안 가리면 `\mathcal{V}`·`\dot{V}` 안의 맨 `V` 를
        #   맨 표기로 잘못 세고, 고치는 쪽은 `\dot{V}` 를 `\dot{𝒱}`(체적유량 → 속도)로
        #   **망가뜨린다.** 앞 글자만 보는 lookbehind 로는 `\frac{V^{2}}` 의 `{` 와
        #   `\mathcal{V}` 의 `{` 를 구별할 수 없다 — 그래서 가리는 쪽으로 푼다.
        masked = symbol_masked(text, symbols, glyphs)
        wrong = re.findall(r"(?<![A-Za-z])" + re.escape(bare) + "(" + _SYMBOL_TAIL + ")", masked)
        # ★★ **꼬리가 빈 자리는 갈림으로 세지 않는다** (좁힌 날 2026-08-12 — 첫 실행에서
        #   실제로 데이터를 망가뜨렸다). 맨 글자 하나(`V`)는 꼬리라는 단서가 없어 **무엇이든
        #   될 수 있다** — ch02 연습 2번의 `V = 40 m³/s`(체적유량)를 속도 필기체로 바꿨고,
        #   기호 안내 절의 부피도 같은 이유로 걸렸다. 첨자·지수가 붙어 **형태가 같을 때만**
        #   저자가 같은 자리에 답을 적어 둔 것으로 볼 수 있다.
        for tail in sorted(t for t in (set(wrong) & right) if t):
            out.append((bare + tail, want + tail, role))
    return out


def _item_strings(node):
    """항목 안의 화면에 나가는 문자열 — 삽화는 `<text>` 안만. 순수 함수."""
    if isinstance(node, dict):
        for key, val in node.items():
            if key == "svg":
                for piece in _svg_text_bodies(str(val)):
                    yield piece
            elif key == "variables" and isinstance(val, dict):
                # ★ **키도 화면에 그려지는 수식이다** — 실제로 ch05 유도 4번은 `latex` 는
                #   `\mathcal{V}^{2}` 인데 **키만** `V^{2}` 라 화면의 칩에서 갈렸다.
                #   값만 훑으면 그 자리가 영영 안 보인다(`iter_math_blobs` 가 닫은 그 사각지대).
                for vk, vv in val.items():
                    yield str(vk)
                    yield str(vv)
            elif key not in ("changeNote", "rationale", "sourceRef", "id"):
                for piece in _item_strings(val):
                    yield piece
    elif isinstance(node, list):
        for val in node:
            for piece in _item_strings(val):
                yield piece
    elif isinstance(node, str):
        yield node


def _svg_text_bodies(svg):
    for match in re.finditer(r"<text\b[^>]*>(.*?)</text>", svg or "", re.S):
        yield re.sub(r"<[^>]+>", "", match.group(1))


def symbol_split_issues(ch, symbols, glyphs=None):
    """C46 — 한 항목 안에서 같은 형태가 두 표기로 갈렸는가. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    for kind, item in _iter_check_owners(ch):
        # ★ **기호 표기 자체를 설명하는 항목은 예외다** (열린 날 2026-08-12, 첫 실행에서 났다).
        #   ch02 기호 안내 절은 [사용자 발화 인용 생략] 처럼
        #   **두 표기가 함께 있어야 말이 되는** 자리다. 갈림 규칙만 보면 위반으로 읽히고,
        #   실제로 처방이 그 절의 부피를 필기체로 바꿔 버렸다(C45 가 곧바로 신고했다).
        #   자동 판정으로 가르려다 규칙을 더 흐리게 만들기보다 **저자가 선언**하게 한다 —
        #   이 리포의 처방 방식 그대로다(`kind`·`class='dim'`·`strictChapters`).
        if item.get("symbolLiteral"):
            continue
        for bad, good, role in symbol_split_hits(item, symbols, glyphs):
            out.append(kind + " " + str(item.get("id")) + ": `" + bad + "` 와 `" + good
                       + "` 가 한 항목 안에 함께 있다 — 저자가 같은 자리에서 " + role
                       + "를 두 표기로 적었다. 선언된 표기로 맞출 것"
                       " (`python tools/fix_velocity_symbol.py --split` 이 목록을 낸다)")
    return out


def symbol_role_issues(ch, symbols, not_roles=()):
    """C44 — `variables` 의 선언과 과목이 정한 표기가 맞는가. 순수 함수 — 테스트가 직접 부른다."""
    if not symbols:
        return []
    issues = []
    for f in ((ch.get("derivation") or {}).get("formulas") or []):
        for k, role in declared_roles(f.get("variables"), symbols, not_roles):
            got, want = _symbol_base(k), _symbol_base(symbols[role])
            if got and got != want:
                issues.append("derivation " + str(f.get("id")) + ".variables[" + repr(k.strip())
                              + "]: 이 과목에서 " + role + "는 `" + symbols[role] + "` 로 적는다 — "
                              "지금 `" + got + "` 다. 키와 함께 이 카드의 식·산문·삽화의 같은"
                              " 기호도 옮길 것 (data/<과목>/terms.json 의 symbols 가 정본)")
    return issues


def _is_hangul(chunk):
    return bool(chunk) and "가" <= chunk <= "힣"


def term_pairing_issues(ch, terms):
    """C41 — 선언한 용어의 그 챕터 첫 등장에 원어가 붙어 있는가. 순수 함수.

    ★ 세 가지를 실측으로 좁혔다(첫 실행 33건 중 상당수가 오탐이었다).
      ⑴ **이론 본문만 본다.** 학습목표·챕터 도입부는 본문이 정의하기 **전에** 용어를 부르는
        요약이라, 거기를 첫 등장으로 세면 [사용자 발화 인용 생략] 는 이상한 요구가 된다.
        AGENTS 도 [사용자 발화 인용 생략] 이라고 적어 두었다.
      ⑵ **앞 글자가 한글이면 그 자리는 건너뛴다.** `구동력` 안의 `동력` 을 첫 등장으로 잡아
        [사용자 발화 인용 생략] 을 신고했다 — 낱말의 조각은 그 용어가 아니다.
      ⑶ **괄호 안에 함께 든 형태도 통과시킨다.** `b축(종법선, binormal)` 은 병기가 되어 있는데
        *바로 뒤*만 보면 못 찾는다. 그래서 **뒤쪽 짧은 창**에 원어가 있으면 통과다.
        선언한 원어와 글자까지 같은지는 다투지 않는다(줄여 쓴 형태도 통과다) —
        막으려는 결함은 *원어가 아예 없는 것*이다.
    """
    if not terms:
        return []
    prose = "\n".join(_term_prose(ch.get("theory") or {}))
    issues = []
    for ko in sorted(terms):
        en = terms[ko]
        i, found = -1, False
        while True:
            i = prose.find(ko, i + 1)
            if i < 0:
                break
            if _is_hangul(prose[i - 1:i]):        # ⑵ 더 긴 낱말의 조각이다
                continue
            found = True
            break
        if not found:
            continue                              # 이 챕터가 안 쓰는 용어다
        window = prose[max(0, i - 2):i + len(ko) + len(en) + 10]
        if en.lower() in window.lower():
            continue
        issues.append("theory: '" + ko + "' 의 첫 등장에 원어가 없다 — "
                      + repr(prose[max(0, i - 18):i + len(ko) + 12])
                      + " → `" + ko + "(" + en + ")` 로 (data/<과목>/terms.json 선언)")
    return issues


# renderMath(뷰어 템플릿)의 위/아래첨자 변환이 **실제로 매치하는** 형태.
# `\sqrt`·`\int_{}^{}` 와 같은 '한 단계 중첩 허용' 패턴이고, 템플릿과 이 상수가
# 갈라지지 않도록 `test_checks.py::test_supsub_nesting_is_shared` 가 템플릿 소스를 직접 읽어 잠근다.
SUPSUB_RENDERABLE_RE = re.compile(r"[\^_]\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")


def inline_math_issues(node, trail="root", key=None):
    r"""본문·풀이 안의 인라인 수식 `\( … \)`을 renderMath 어휘로 검사한다.

    열린 날 2026-07-26 — `check_latex_field`가 formula.latex · variables 키 ·
    practice.solutionTemplate · blanks[].answer **네 곳에만** 걸려 있었다. 이론 본문·유도 단계·
    문제 풀이·이해도 체크의 인라인 수식은 한 번도 검사받은 적이 없다. 그래서 renderMath가
    모르는 명령이 화면에 역슬래시째 찍혀도 빌드가 통과시켰다 — ch01 `\equiv` 5 · `\min` 1 ·
    `\tanh` 5, ch02 `\sec` 4 (브라우저 DOM textContent 실측). '빠뜨렸다'가 아니라
    **빠뜨려도 통과되는 구조**였다.

    순회는 스키마를 열거하지 않고 JSON을 통째로 내려간다. 필드 목록을 손으로 적으면
    새 필드가 생길 때마다 같은 사각지대가 다시 열린다(fmttext_fields 등록부의 전례).
    """
    issues = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "svg":          # SVG는 LaTeX가 아니다
                continue
            issues.extend(inline_math_issues(v, trail + "/" + str(k), k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            issues.extend(inline_math_issues(v, trail + "[" + str(i) + "]", key))
    elif isinstance(node, str):
        for span in INLINE_MATH_RE.finditer(node):
            for cmd in re.findall(r"\\([A-Za-z]+)", span.group(1)):
                if cmd not in LATEX_SUPPORTED:
                    issues.append(trail + ": 인라인 수식에 renderMath 미지원 명령 \\" + cmd
                                  + " — 화면에 역슬래시째 찍힌다. 템플릿 renderMath에 심볼을 "
                                  "넣고 LATEX_SUPPORTED에 등록할 것")
        # ★ 첨자 인자 안의 중첩 중괄호 (열린 날 2026-07-27, 브라우저 DOM 실측으로 발견).
        #   renderMath의 위/아래첨자 변환은 `^\{([^{}]*)\}` — **중첩을 허용하지 않는다.**
        #   그래서 `e^{\int R^{*}\,dy}`는 안쪽 `{*}` 때문에 매치에 실패하고
        #   화면에 **캐럿이 날것으로** 찍힌다(실측: `e^∫ R* dy`). `\frac`·`\mathrm`에는
        #   이미 같은 검사가 있는데 `^`·`_`만 빠져 있었다 — 빠뜨림이 아니라 **검사의 사각지대**다.
        #
        #   ★ 2026-08-02 정정 — 그때의 처방(`\exp(…)`로 우회)이 표기를 갈라놓았다.
        #   실측: ch01 `e^{` 75 vs `\exp` 12 · ch02 96 vs 19, 게다가 적분인자 절 한 문단 안에
        #   `F(x) = \exp(∫R dx)` 와 `F = e^{\int p\,dx}` 가 공존했다(사용자 지적:
        #   [사용자 발화 인용 생략]). 데이터를 렌더러에 맞추는 대신 **렌더러를 고쳤다** —
        #   renderMath의 첨자 변환을 `\sqrt`·`\int_{}^{}` 와 같은 한 단계 중첩 허용 패턴으로.
        #   그래서 이 검사의 판정 기준도 "중첩이 있는가"가 아니라
        #   **"renderMath의 정규식이 여기서 매치하는가"**(SUPSUB_RENDERABLE_RE)로 바꾼다.
        #   두 단계 이상 중첩·미닫힘은 계속 error다. 검사 완화가 아니라 **자를 렌더러의
        #   실제 능력에 맞춘 것**이고, 어긋나면 test_supsub_nesting_is_shared가 잡는다.
        for m in re.finditer(r"[\^_]\{", node):
            if SUPSUB_RENDERABLE_RE.match(node, m.start()):
                continue
            issues.append(trail + ": 첨자 인자를 renderMath가 변환하지 못한다 — 중괄호가"
                          " 두 단계 이상 중첩됐거나 닫히지 않았다. 캐럿이 화면에 그대로 찍힌다: "
                          + repr(node[m.start():m.start() + 24]))

        # 유니코드 위·아래첨자 — 수식 자리와 산문 자리를 갈라 판정한다(위 주석의 ⑴·⑵).
        math_only = key in MATH_ONLY_KEYS
        math_part = node if math_only else "".join(m.group(1) for m in INLINE_MATH_RE.finditer(node))
        prose_part = "" if math_only else INLINE_MATH_RE.sub(" ", node)
        in_math = sorted({c for c in math_part if c in UNI_SUPSUB_ANY})
        if in_math:
            issues.append(trail + ": 수식 자리에 유니코드 첨자 " + "".join(in_math)
                          + " — 여기는 LaTeX라 ^{…}·_{…}로 써야 <sup>로 렌더된다: "
                          + repr(node[:60]))
        if key not in UNI_SUPSUB_EXEMPT_KEYS:
            in_prose = sorted({c for c in prose_part if c in UNI_SUPSUB_LETTERS})
            if in_prose:
                issues.append(trail + ": 산문에 문자 위·아래첨자 " + "".join(in_prose)
                              + " — 본문 폰트가 점처럼 뭉갠다. 인라인 수식 \\(y^{a}\\)로 쓸 것"
                              " (숫자 첨자 m³는 계속 허용): " + repr(node[:60]))
    return issues


# ★ C39. 인자를 중괄호로 감싸지 않은 매크로 (신설 2026-08-12 — 인박스 부류 1 「수식 렌더 깨짐」).
#
# 사용자 실측 증상: ch01 유도 1/13 이 `\vec F=m\vec a` 를 **LaTeX 원문 그대로** 화면에 찍고,
# ch02 유도 4/15 에 `\dot` 이 노출됐다. 원인은 renderMath 가 **중괄호 형태만** 치환하기
# 때문이다 — `/\\dot\{([^{}]*)\}/` 는 `\dot m` 에 매치되지 않아 매크로 이름이 글자로 남는다.
#
# **빠뜨림이 아니라 빠뜨려도 통과되는 구조였다.** `check_latex_field` 는 *미지원 명령*과
# *중첩 중괄호*만 봤고, `inline_math_issues` 는 *어휘*와 *첨자 중첩*만 봤다. 즉 등록된 명령을
# **문법에 안 맞게** 쓴 것은 두 검사 사이로 그대로 빠져나갔다(실측 열역학 19곳).
#
# ★ 승격은 과목별이다(`strictChapters.latex_brace_arg`). 다른 과목 데이터를 아직 안 봤고,
#   전 과목 error 로 박으면 남의 빌드가 멈춘다(2026-08-02 `middot` 사고와 같은 형태).
#   경고여도 `close_report` 가 close 를 막으므로 묻히지 않는다.
ARG_MACROS = ("frac", "sqrt", "vec", "ddot", "dot", "hat",
              "mathbf", "mathcal", "mathrm", "text")
ARG_MACRO_RE = re.compile(r"\\(" + "|".join(ARG_MACROS) + r")(?![A-Za-z])[ ]*(.?)")


def brace_arg_macro_hits(s):
    r"""인자를 `{}` 로 감싸지 않은 매크로 이름과 그 자리의 조각. 순수 함수 — 테스트가 직접 부른다.

    판정은 하나뿐이다: **매크로 이름 다음(공백을 건너뛴 뒤) 글자가 `{` 인가.**
    renderMath 의 정규식이 요구하는 것이 정확히 그것이라, 다른 기준을 쓰면 자가 갈라진다.
    """
    hits = []
    for m in ARG_MACRO_RE.finditer(s):
        if m.group(2) == "{":
            continue
        hits.append((m.group(1), s[m.start():m.start() + 24]))
    return hits


def brace_arg_macro_issues(node, trail="root", key=None):
    r"""C39 — 위 주석이 정본. 순회는 스키마를 열거하지 않고 JSON 을 통째로 내려간다.

    문자열 전체를 본다(`\( … \)` 안만 보지 않는다). `equations`·`latex`·`solutionTemplate`
    처럼 값 전체가 LaTeX 인 필드가 여럿이고, 필드 목록을 손으로 적으면 새 필드가 생길 때마다
    같은 사각지대가 다시 열린다. 산문에 `\dot` 같은 글자열이 우연히 들어갈 일은 없다.
    """
    issues = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "svg":          # SVG 는 LaTeX 가 아니다 (인라인 수식이 렌더되지 않는다)
                continue
            issues.extend(brace_arg_macro_issues(v, trail + "/" + str(k), k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            issues.extend(brace_arg_macro_issues(v, trail + "[" + str(i) + "]", key))
    elif isinstance(node, str):
        for name, snip in brace_arg_macro_hits(node):
            issues.append(trail + ": 인자를 중괄호로 감싸지 않은 매크로 \\" + name
                          + " — renderMath 는 \\" + name + "{…} 형태만 치환하므로 화면에"
                          " 매크로 이름이 글자로 남는다. \\" + name + "{x} 로 쓸 것: "
                          + repr(snip))
    return issues


def outline_shape_issues(ch):
    r"""`solutionOutline` 이 뷰어가 받는 모양인가. 순수 함수 — 테스트가 직접 부른다.

    ★★ **열린 날 2026-08-04 (동역학). 연습문제 탭이 3일간 통째로 비어 있었다.**

    뷰어 `renderOutline(steps)` 는 `(steps || []).forEach` 로 시작한다 — **배열 전용**이다.
    그런데 동역학 ch12 는 10문항 중 9개가 **문자열**이었고, 그래서 `renderProblems()` 가
    첫 문항에서 `TypeError: forEach is not a function` 으로 죽어
    `probList.innerHTML` 이 **아예 대입되지 않았다**(카드 0개, 화면 공백).

    ★ 원인은 데이터가 아니라 **계약을 보는 자가 없던 것**이다. 실측:
      · 문자열 풀이가 들어간 날 2026-07-28 (`git log -S ch12-q01`)
      · `renderOutline` 이 배열을 요구하기 시작한 날 2026-08-01 (`sync common from thermo`)
      즉 **공통 동기화가 남의 과목 화면을 깨뜨렸고 빌드·회귀·감사 어디에도 안 걸렸다.**
      데이터 린트는 내용만 봤고(말투·분수·기호), *뷰어가 그 값을 렌더할 수 있는가* 는 아무도 안 봤다.

    ★ 왜 사람도 못 봤나 — 그 챕터의 연습문제는 **아직 검수 전**이었다(`.claude/SUBJECT.md`).
      검수가 늦은 자리일수록 기계가 봐야 한다는 것이 이 검사의 존재 이유다.

    전 과목 **error** 다. 취향 규격이 아니라 **런타임 계약**이라서다 — 문자열로 둔 과목은
    지금 이 순간 그 탭이 비어 있다. 경고로 두면 '비어 있는 화면'이 경고 더미에 묻힌다.
    """
    issues = []
    for q in ch.get("problems") or []:
        outline = q.get("solutionOutline")
        if outline is None:
            continue
        where = "problem " + str(q.get("id"))
        if not isinstance(outline, list):
            issues.append(where + ": solutionOutline 은 **배열**이어야 한다 — 뷰어"
                          " `renderOutline` 이 forEach 로 도므로 문자열이면 연습문제 탭이"
                          " 통째로 빈다(TypeError). 계산 단계는 줄로 나누고, 식이 있으면"
                          ' {"text": …, "equations": [ … ]} 로 적을 것: ' + repr(str(outline)[:40]))
            continue
        for i, st in enumerate(outline):
            if isinstance(st, str):
                continue
            if isinstance(st, dict) and ("text" in st or "equations" in st):
                if not isinstance(st.get("equations", []), list):
                    issues.append(where + "/solutionOutline[" + str(i)
                                  + "]: equations 는 배열이어야 한다")
                continue
            issues.append(where + "/solutionOutline[" + str(i) + "]: 단계는 문자열이거나"
                          ' {"text": …, "equations": [ … ]} 여야 한다: ' + repr(str(st)[:40]))
    return issues


# 유도 카드가 **가드 없이** 읽는 필드. 없으면 `String(undefined)` 가 화면에 `undefined` 로 찍히거나
# (`esc`·`fmtText`) 아예 TypeError 로 카드가 죽는다(`.map`·`Object.keys`).
# 정본은 `site/template/viewer.template.html` 의 `renderDerivCard` 이고,
# `test_checks.py::test_derivation_card_fields_match_viewer` 가 두 벌을 대조한다.
DERIV_TEXT_FIELDS = ("topic", "name", "notes")        # esc()·fmtText() 로 바로 들어간다
DERIV_LIST_FIELDS = ("derivationSteps", "assumptions")  # .map() 을 부른다
DERIV_DICT_FIELDS = ("variables",)                      # Object.keys() 를 부른다


def chapter_title_agreement_issues(ch, ch_path):
    """챕터 제목이 `index.json` 과 `chNN.json` 에서 같은가. 순수 함수에 가깝다(파일 하나를 읽는다).

    ★ **열린 날 2026-08-07 (동역학 ch13).** 사용자: [사용자 발화 인용 생략]

    실측하니 지적한 것보다 넓었다 — **제목이 두 파일에 각각 있고 아무도 대조하지 않았다.**

      · `index.json`  → 홈·과목 트리·챕터 이동 버튼이 읽는다
      · `chNN.json`   → 챕터 화면의 제목과 브라우저 탭 제목이 읽는다

    동역학 실측: ch12 는 `index` 에만 영문 병기가 있고, ch14 도 그랬다. ch13 은 **양쪽 다 없었다.**
    즉 **같은 챕터가 홈에서와 챕터 화면에서 다른 이름으로 나오고 있었다.**

    ★ 왜 안 걸렸나 — 두 값 모두 *형식*은 멀쩡하다(문자열이고 비어 있지도 않다).
      갈라졌다는 것은 **둘을 나란히 놓아야만** 보이는데, 그 자를 아무도 안 들었다.
      `derivation_shape_issues`(C38) 와 같은 부류다: 화면에 나가는 값을 보는 자가 없던 자리.

    ★ 영문 병기를 **강제하지는 않는다.** 그건 과목의 선택이다(열역학은 전 챕터가 국문 단독).
      이 검사가 요구하는 것은 **두 곳이 같을 것** 하나뿐이라 그 선택을 침범하지 않는다.

    전 과목 **error** 다 — 실측상 열역학은 이미 전 챕터가 일치한다(어기고 있던 과목이 없다).
    """
    index_path = os.path.join(os.path.dirname(ch_path), "index.json")
    if not os.path.isfile(index_path):
        return []
    try:
        with open(index_path, encoding="utf-8") as fh:
            index = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []
    fname = os.path.basename(ch_path)
    entry = next((c for c in (index.get("chapters") or []) if c.get("file") == fname), None)
    if entry is None:
        return []
    here = str(ch.get("chapterTitle") or "")
    there = str(entry.get("chapterTitle") or "")
    if here == there:
        return []
    return ["chapterTitle 이 index.json 과 다르다 — 홈·목차는 %r 로, 챕터 화면과 탭 제목은 %r 로"
            " 보여 준다. 같은 챕터가 두 이름으로 나가므로 한쪽으로 맞출 것"
            " (영문 병기 여부는 과목이 정한다 — 이 검사는 **일치**만 본다)" % (there, here)]


def derivation_shape_issues(ch):
    r"""유도 카드가 뷰어가 받는 모양인가. 순수 함수 — 테스트가 직접 부른다.

    ★★ **열린 날 2026-08-06 (동역학). 유도 카드 제목이 화면에 `undefined` 로 찍혀 있었다.**

    사용자: [사용자 발화 인용 생략]

    뷰어 `renderDerivCard` 는 `fmtText(f.name)` 과 `fmtText(f.notes)` 를 **가드 없이** 부른다.
    `fmtText` 는 첫 줄이 `String(raw)` 라 `undefined` 가 그대로 문자열 `"undefined"` 가 된다
    (`renderMath` 는 같은 자리에 널 가드가 있는데 `fmtText` 에는 없다 — 한 파일 안에서 갈렸다).
    동역학 데이터는 `name` 대신 **`title`** 로 적혀 있었고(열역학은 `name`), ch13 은 `notes` 도 없었다.
    실측: ch12 유도 4장 × 1곳 + ch13 유도 2장 × 2곳 = **8곳**.

    ★★ **이것은 재발이다.** 바로 위 `outline_shape_issues` 가 2026-08-04 에 같은 부류로 열렸다 —
      [사용자 발화 인용 생략]
      그때 닫은 것은 **`solutionOutline` 한 필드**였고, 나머지 필드는 그대로 열려 있었다.
      즉 인스턴스만 닫고 부류를 안 닫은 것이다(AGENTS 규칙 7).
      → 이번에는 **유도 카드가 읽는 필드 전부**를 계약으로 박는다.

    ★ 왜 사람도 못 봤나 — `chapter-schema-notes.md` 가 `title` 이라고 적어 두었다.
      그 문서 스스로 [사용자 발화 인용 생략] 라고 밝혀 두었는데, **빌드는 통과했다** — 아무도 안 보는 필드였기 때문이다.

    전 과목 **error** 다. 취향 규격이 아니라 **런타임 계약**이라서다.
    """
    issues = []
    for f in ((ch.get("derivation") or {}).get("formulas") or []):
        where = "derivation " + str(f.get("id"))
        for key in DERIV_TEXT_FIELDS:
            val = f.get(key)
            if val is None:
                issues.append(where + ": `" + key + "` 가 없다 — 뷰어 renderDerivCard 가 가드 없이"
                              " 읽으므로 화면에 `undefined` 가 그대로 찍힌다."
                              # ★ 여기에 **과목 이름을 적지 않는다** (2026-08-07, 회귀가 잡았다).
                              #   처음 문구는 [사용자 발화 인용 생략] 였는데, 그러면 공통 코드가
                              #   한 과목을 아는 셈이고 `test_tools_do_not_hardcode_a_subject` 에 걸린다.
                              #   갈 길은 **필드 이름 자체**로 말할 수 있다 — 과목을 들 이유가 없다.
                              + (" 필드 이름은 `name` 이다 — `title` 로 적었다면 키를 바꿀 것"
                                 if key == "name" else ""))
            elif not isinstance(val, str):
                issues.append(where + ": `" + key + "` 는 문자열이어야 한다 — 배열이면 화면에"
                              " 쉼표가 그대로 찍힌다: " + repr(str(val)[:40]))
        if f.get("appliesTo") is not None and not isinstance(f.get("appliesTo"), str):
            issues.append(where + ": `appliesTo` 는 문자열이어야 한다 — 뷰어가 fmtText 로"
                          " 바로 넘기므로 배열이면 항목이 쉼표로 이어 붙는다: "
                          + repr(str(f.get("appliesTo"))[:40]))
        for key in DERIV_LIST_FIELDS:
            if not isinstance(f.get(key), list):
                issues.append(where + ": `" + key + "` 는 배열이어야 한다 — 뷰어가 .map 을"
                              " 부르므로 없거나 다른 타입이면 유도 탭이 통째로 빈다(TypeError)")
        for key in DERIV_DICT_FIELDS:
            if not isinstance(f.get(key), dict):
                issues.append(where + ": `" + key + "` 는 객체여야 한다 — 뷰어가 Object.keys 를"
                              " 부르므로 없으면 유도 탭이 통째로 빈다(TypeError)")
        # ★★ **단계의 설명 키** (2026-08-07 에 넓혔다 — 같은 부류 네 번째).
        #
        # 사용자: [사용자 발화 인용 생략] → **설명이 적은 것이 아니라
        # 화면에 아예 안 나오고 있었다.** 뷰어 `renderStep` 은 `st.text` 를 읽는데
        # 동역학 ch12·ch14 는 `description` 으로 적혀 있었다(ch13 만 `text`).
        # 실측: **ch12 31개 · ch14 16개, 총 47개 설명이 통째로 버려지고 있었다.**
        #
        # ★ 왜 안 걸렸나 — 위 필드 검사는 **공식 수준**만 봤다. 단계는 자유형 객체라
        #   아무 키나 넣어도 통과했고, 뷰어는 모르는 키를 **조용히 무시**한다.
        #   빈 문자열이면 눈에 띄지만 **키 이름이 다르면 아무 흔적도 안 남는다.**
        # ★★ 2026-08-12 — 카드의 **종류**가 단계의 모양을 정한다(AGENTS 「유도 탭의 카드는
        #   두 종류다」). 선언이 없으면 종전대로 **유도**로 본다 — 선언은 opt-in 이라
        #   아직 안 가른 과목의 빌드는 오늘과 똑같이 돈다.
        kind = f.get("kind")
        if kind is not None and kind not in ("derivation", "summary"):
            issues.append(where + ": `kind` 는 `derivation` 또는 `summary` 여야 한다 — "
                          + repr(kind) + " (AGENTS 「유도 탭의 카드는 두 종류다」)")
            kind = None
        is_summary = kind == "summary"
        for i, st in enumerate(f.get("derivationSteps") or []):
            if not isinstance(st, dict):
                # ★★ 2026-08-08 V-15 — 문자열 단계 자체는 순수 설명이면 허용하지만, 식을
                # 산문 안에 끼워 넣으면 독립 수식 줄을 만들 수 없다. 뷰어는 이미 객체형
                # {text, equations} 을 지원했는데 검사·규칙이 없어 원조 과목만 옛 형식으로
                # 남았다. `=` 류와 대표 LaTeX 명령을 함께 보는 이유는 `\(…\)` 없이
                # `Δu = c_v ΔT` 로 적은 실제 데이터도 같은 결함이었기 때문이다.
                #
                # ★ 2026-08-12 — **공식 정리 카드에서는 그 자리가 정답이다.** 「A는 B로
                #   정의한다」한 줄짜리를 설명/식으로 갈라 놓은 것이 부류 3 의 지적이었다.
                #   다만 면제되는 것은 **인라인 수식**뿐이다 — 날 텍스트 `ρ = m/V` 는
                #   공식 정리에서도 그대로 결함이라 계속 신고한다(자를 두 개 두지 않는다).
                raw = str(st or "")
                if is_summary:
                    bare = mask_inline_math(raw)
                    if re.search(r"(?:=|≈|≅|\\(?:frac|int|sum|sqrt|partial)\b)", bare):
                        issues.append(where + "/derivationSteps[" + str(i) + "]: 공식 정리 카드의"
                                      " 식은 **인라인 수식** `\\(…\\)` 으로 쓴다 — 날 텍스트로"
                                      " 적으면 조판이 본문과 갈린다: " + repr(bare[:40]))
                elif ("\\(" in raw or "\\[" in raw
                        or re.search(r"(?:=|≈|≅|\\(?:frac|int|sum|sqrt|partial)\b)", raw)):
                    issues.append(where + "/derivationSteps[" + str(i) + "]: 식이 문자열 산문 안에"
                                  " 있다 — 단계를 `{text, equations}` 객체로 바꾸고 식은"
                                  " `equations`의 독립 줄에 둘 것"
                                  " (이 카드가 「공식 정리」라면 `kind: \"summary\"` 를 선언할 것)")
                continue                      # 순수 설명 문자열은 그대로 렌더된다
            if is_summary:
                issues.append(where + "/derivationSteps[" + str(i) + "]: 이 카드는"
                              " `kind: \"summary\"`(공식 정리)인데 단계가 `{text, equations}`"
                              " 객체다 — 문자열 한 줄 + 인라인 수식으로 적을 것"
                              " (앞 식을 받아 다음 식을 만드는 자리가 있으면 `kind` 를"
                              " `derivation` 으로 되돌릴 것)")
                continue
            trail = where + "/derivationSteps[" + str(i) + "]"
            if "text" not in st:
                other = next((k for k in ("description", "desc", "note", "body") if k in st), None)
                issues.append(trail + ": 단계 설명은 `text` 로 적는다 — 뷰어 renderStep 이"
                              " 그 키만 읽으므로 다른 이름으로 두면 **설명이 화면에서 통째로"
                              " 사라진다**(빈 문자열과 달리 흔적도 안 남는다)"
                              + (" · 지금 `%s` 로 적혀 있다" % other if other else ""))
            if not isinstance(st.get("equations", []), list):
                issues.append(trail + ": `equations` 는 배열이어야 한다")
    return issues


def derivation_kind_declaration_issues(ch):
    r"""C43 — 유도 카드가 자기 **종류**를 선언했는가. 순수 함수 — 테스트가 직접 부른다.

    ★★ **열린 날 2026-08-12 (열역학 인박스 부류 3).** 사용자(ch01 유도 4/13·5/13):
    [사용자 발화 인용 생략]

    **원인은 조항이 대상을 안 정한 것이다.** 2026-08-08 에 들어온 [사용자 발화 인용 생략] 는 **어떤 카드가 그 대상인지**를 말하지 않았고, 그래서 「밀도는 단위 부피당
    질량이다」한 줄짜리 정의까지 전부 `{text, equations}` 로 갈렸다.

    ★ 위 `derivation_shape_issues` 는 **선언이 있을 때** 모양이 맞는지만 본다. 그것만으로는
      **아무도 선언하지 않으면 전부 옛날처럼 지나간다** — 판정을 강제하는 자가 따로 있어야 한다.
      그 자리가 여기다. 승격한 챕터에서는 **카드마다 `kind` 를 적어야** 통과한다.

    승격은 과목별·챕터별이다(`index.json` 의 `strictChapters.derivation_kind`).
    가르지 않은 과목·챕터에서는 경고로만 뜬다 — 전 과목 error 로 박으면 남의 빌드가 멈춘다
    (2026-08-02 사고와 같은 형태). 경고는 `close_report` 가 close 를 막으므로 묻히지 않는다.
    """
    issues = []
    for f in ((ch.get("derivation") or {}).get("formulas") or []):
        if f.get("kind") in ("derivation", "summary"):
            continue
        issues.append("derivation " + str(f.get("id")) + ": 카드 종류를 선언하지 않았다 — "
                      "`kind` 에 `derivation`(앞 식을 받아 다음 식을 만든다) 또는 "
                      "`summary`(「A는 B로 정의한다」의 나열)를 적을 것 "
                      "(AGENTS 「유도 탭의 카드는 두 종류다」)")
    return issues


SLIDE_ID_RE = re.compile(r"""\bid\s*=\s*['"]([^'"]+)['"]""")


def slide_card_figures(ch):
    """카드 슬라이드의 **원본 한 장**(단계로 안 쪼갠 것). 순수 함수.

    단계 조각을 쓰는 자(`slide_step_figures`)와 갈라 둔다 — 겹침·가림은 «지금 화면에 뭐가
    보이나» 에 달렸지만 **기하(꼭짓점 각도·좌표)는 단계와 무관**하다. 기하만 보는 자에게
    조각을 먹이면 같은 꼭짓점이 단계 수만큼 신고돼 무엇이 몇 개인지 셀 수 없게 된다.
    슬라이드가 어디 사는지는 여기와 `slide_step_figures` 두 곳뿐이고 둘 다 이 파일에 있다.

    ★ **원본 dict 를 그대로 준다**(사본이 아니다). 교정 도구가 `dg["svg"] = …` 로 고칠 수
      있어야 «어디 사는지» 를 세 번째로 적지 않는다 — `_iter_diagrams` 와 같은 계약이다.
    """
    out = []
    for f in ((ch.get("derivation") or {}).get("formulas") or []):
        fig = f.get("figure")
        if isinstance(fig, dict) and str(fig.get("svg") or "").strip():
            out.append(fig)
    return out


def slide_step_figures(ch):
    r"""슬라이드 카드의 **단계별 그림**을 삽화 검사에 먹일 꼴로 돌려준다. 순수 함수.

    ★★ **열린 날 2026-08-19 — 이 자리가 통째로 사각지대였다.** 삽화 검사는 `_iter_diagrams`
      가 흘리는 것만 보는데 그 함수는 `diagrams` 만 훑는다. 그래서 카드의 `figure`(슬라이드
      삽화)는 **어느 자도 안 대고 있었다** — 실제로 글자끼리 겹친 삽화가 빌드를 통과했고
      브라우저에서야 드러났다(규칙 11: 범위를 확인 안 한 0건은 「없다」가 아니다).

    ★ **전부 켠 SVG 를 재지 않는다** — 그건 화면에 존재하지 않는 상태다. 슬라이드는 단계마다
      다른 그림이라 ⑴ 번갈아 놓인 조각이 겹침으로 잡히고 ⑵ 한 단계 안의 진짜 겹침은 다른
      단계의 조각에 가려 안 보인다. 그래서 **단계마다 보이는 것만 남겨** 한 장씩 잰다.

    ★ 어느 단계에서도 이름이 안 불린 그룹은 **늘 보이는 것**이라 모든 단계에 남긴다 —
      뷰어가 그렇게 그린다(부르지 않은 id 는 손대지 않는다). 두 곳이 다른 규칙을 쓰면 갈라진다.
    """
    out = []
    for f in ((ch.get("derivation") or {}).get("formulas") or []):
        fig = f.get("figure") or {}
        svg = str(fig.get("svg") or "")
        steps = f.get("derivationSteps") or []
        named = set()
        for st in steps:
            if isinstance(st, dict):
                named.update(st.get("show") or [])
        if not svg.strip() or not named:
            continue
        always = set(SLIDE_ID_RE.findall(svg)) - named
        base = str(fig.get("id") or f.get("id") or "?")
        for i, st in enumerate(steps):
            show = st.get("show") if isinstance(st, dict) else None
            piece = svg if not show else svg_with_only(svg, set(show) | always)
            step_fig = {"id": base + " [단계 " + str(i + 1) + "]", "svg": piece}
            # ★ 선언 키는 단계 조각으로 **함께 내려간다** (2026-08-19). 이 dict 만 검사가 보므로
            #   여기서 떨구면 카드 figure 의 `numericLabels`·`lintWaivers` 는 **선언할 길 자체가
            #   없다** — F5 가 단계마다 뜨는데 끌 자리가 없는 상태로 실측됐다(ch01 단위 삽화 3장).
            for key in ("numericLabels", "lintWaivers"):
                if key in fig:
                    step_fig[key] = fig[key]
            out.append(step_fig)
    return out


def derivation_slide_issues(ch):
    r"""C50 — 유도 슬라이드의 **삽화 한 벌 계약**. 순수 함수 — 테스트가 직접 부른다.

    ★★ **열린 날 2026-08-18.** 사용자: [사용자 발화 인용 생략] · 뒤이어
    [사용자 발화 인용 생략]

    ★ **막는 문제는 없었고 순서가 있었다.** 빌드업 슬라이드를 옛 스키마(단계마다 SVG 를 통째로
      박는 형태)로 만들면 **거의 같은 SVG 를 N 벌 복제**하게 되고, 나중에 색·글자·규격을 고칠 때
      **한 벌만 고쳐져 같은 그림이 슬라이드마다 달라 보인다**(ch06 에서 «재사용 = 복제 = 갈라짐»
      으로 닫은 판정). 그래서 구조를 먼저 바꾼다 —
      **카드에 `figure` 한 벌 + 단계는 보일 그룹 id 목록(`show`)만.**

    ★★ **이 검사가 없으면 그 구조가 스스로 무너진다.** ⑴ 단계에 `svg` 를 다시 넣으면 복제가
      돌아오고 ⑵ `show` 가 없는 id 를 가리키면 **그 단계에서 아무것도 안 보이는데 빌드는 통과한다**
      — 화면에서만 드러나는 침묵이라 규칙 11 이 말하는 「미검증과 검증이 겉모습이 같은」 자리다.

    ★ **선언이 곧 opt-in 이다** — `figure` 도 `show` 도 없는 카드는 이 검사가 통째로 지나간다.
      그래서 전 과목 error 로 두어도 남의 빌드가 안 멈춘다(C38 과 같은 근거 — 계약을 어긴 카드는
      지금 이 순간 그 화면이 비어 있다).

    ★ **`show` 는 「그 단계에서 보일 것 전부」다(절대 목록).** 차집합으로 적으면 중간 단계를
      고칠 때 뒤가 전부 어긋난다 — 그 규약은 사양(`docs/2026-08-18-슬라이드모드-튜토리얼-사양.md`)
      이 정본이고, 여기서는 **누적 여부를 강제하지 않는다**(무엇을 감출지는 저자의 판단이다).
    """
    issues = []
    for f in ((ch.get("derivation") or {}).get("formulas") or []):
        where = "derivation " + str(f.get("id"))
        fig = f.get("figure")
        steps = f.get("derivationSteps") or []
        # ★★ **이름은 `derivationSteps` 하나다** (좁힘 2026-08-18, 뷰어 층을 세우다 드러났다).
        #   처음엔 `steps` 도 받았는데 **이 파이프라인에서 그 이름을 읽는 자가 하나도 없다** —
        #   C38·수식 검사·변경점 마크·뷰어가 전부 `derivationSteps` 다. 즉 `steps` 로 적으면
        #   **이 검사만 통과하고 화면에는 아무 일도 안 일어난다**(그 침묵이 이 검사가 막으려던
        #   바로 그것이다). 완화가 아니라 좁힘이고, 잘못 적은 것은 아래에서 신고한다.
        stray = f.get("steps")
        if isinstance(stray, list) and stray:
            issues.append(where + ": 단계는 `derivationSteps` 에 적는다 — `steps` 는 "
                          "이 파이프라인에서 아무도 안 읽어 **화면에 그대로 안 나온다**")
        uses_show = any(isinstance(st, dict) and "show" in st for st in steps)
        if fig is None and not uses_show:
            continue                      # 선언이 없다 — 이 카드는 이 검사의 대상이 아니다
        if uses_show and not isinstance(fig, dict):
            issues.append(where + ": 단계가 `show` 를 쓰는데 카드에 `figure` 가 없다 — "
                          "슬라이드는 **카드에 삽화 한 벌**을 두고 단계가 그 그룹만 고른다")
            continue
        svg = str((fig or {}).get("svg") or "")
        if not svg.strip():
            issues.append(where + "/figure: `svg` 가 비었다 — 삽화 한 벌이 이 자리에 있어야 한다")
            continue
        have = set(SLIDE_ID_RE.findall(svg))
        for i, st in enumerate(steps):
            if not isinstance(st, dict):
                continue
            trail = where + "/steps[" + str(i) + "]"
            if "svg" in st or "diagrams" in st:
                issues.append(trail + ": 단계에 삽화를 다시 넣지 않는다 — 그 순간 **거의 같은 SVG "
                              "여러 벌**이 되고, 나중에 한 벌만 고쳐져 같은 그림이 슬라이드마다 "
                              "달라 보인다. 보일 것은 `show` 로 고른다")
                continue
            if "show" not in st:
                continue
            show = st.get("show")
            if not isinstance(show, list) or any(not isinstance(x, str) for x in show):
                issues.append(trail + ": `show` 는 그룹 id 문자열의 배열이어야 한다")
                continue
            for gid in show:
                if gid not in have:
                    issues.append(trail + ": `show` 가 삽화에 없는 그룹을 가리킨다 — "
                                  + repr(gid) + " (그 단계는 화면에서 **아무것도 안 보이는데** "
                                  "빌드는 통과한다. `figure.svg` 안의 `id=` 와 글자 그대로 맞출 것)")
    return issues


def difficulty_issues(ch):
    """difficulty가 뷰어 diffLabel 어휘 안인지 — 벗어나면 배지에 영어가 그대로 찍힌다."""
    issues = []
    for coll, label in (("practice", "practice"), ("problems", "problem")):
        for item in ch.get(coll) or []:
            if item.get("difficulty") not in PROBLEM_DIFFICULTIES:
                issues.append(label + " " + str(item.get("id")) + ": 뷰어가 모르는 difficulty — "
                              + repr(item.get("difficulty")) + " (허용: "
                              + ", ".join(PROBLEM_DIFFICULTIES) + ")"
                              + ("  ※ 'discriminating'은 2026-07-26에 'advanced'로 통일했다. "
                                 "값만 바꾸지 말고 AGENTS 유형 축(A 기본형/B 변형/C 판단)으로 "
                                 "다시 판정할 것 — 변별이 아닌 것은 intermediate로 내린다."
                                 if item.get("difficulty") == "discriminating" else ""))
    return issues


def follow_up_issues(ch):
    """`followUp` — 「답을 맞힌 직후 곧바로 떠오르는 질문」에 그 자리에서 답하는 칸.

    열린 날 2026-08-14. 사용자: [사용자 발화 인용 생략]

    ★ **왜 `explanation` 을 안 쓰나.** connect·explain 은 `explanation` 을 가질 수 없다 —
      ch02 에서 **답**을 explanation 으로 미룬 회귀를 막으려고 **필드가 있는지**만 보는 조항이다.
      여기 들어갈 것은 답이 아니라 **답을 맞힌 뒤에 생기는 다음 질문**이라 다른 물건인데,
      같은 필드를 나눠 쓰면 그 금지가 흔들린다. 그래서 **이름을 갈랐다**
      (사용자 승인 2026-08-14 「C로 해봐」 — 조항을 좁히는 안 대신 새 필드를 골랐다).

    ★ **경계: 「그래서 만약에 ~라면」 은 여기서 답하지 않는다.** 그건 독자가 스스로 파고들
      자리이고, 자료가 그것까지 먹으면 재미가 사라진다. 자료는 **한 단계**만 맡는다.

    ★ **길이 상한을 두지 않았다.** 재 본 적이 없기 때문이다 — 이 리포는 상한을 세우기 전에
      분포부터 잰다(`audit_checks_load --lengths` 선례). 쌓이면 그때 재고 정한다.

    순수 함수다 — `lint_chapter` 와 테스트가 **같은 판정**을 쓴다. 안에 두면 테스트가 못 본다.
    """
    out = []
    for _owner_kind, _item in _iter_check_owners(ch):
        for check in _item.get("comprehensionChecks") or []:
            if "followUp" not in check:
                continue
            follow = check.get("followUp")
            owner = (_owner_kind + " " + str(_item.get("id", "?"))
                     + " check " + str(check.get("id", "?")))
            if not isinstance(follow, str) or not follow.strip():
                out.append(owner + ": followUp 이 비어 있다 — 쓸 말이 없으면 필드를 두지 말 것")
                continue
            if check.get("stage") not in ("connect", "explain"):
                out.append(owner + ": followUp 은 연결하기·설명하기에만 둔다 — "
                                   "떠올리기(recall)는 `explanation` 이 이미 그 자리다")
            if check.get("explanation"):
                out.append(owner + ": explanation 과 followUp 을 함께 두지 말 것 — "
                                   "둘이 같은 자리를 다투면 어느 쪽이 「답의 보충」인지 갈린다")
    return out


def lint_chapter(ch, ch_path):
    errors, warnings = [], []
    # 단위 판정 방식은 **과목이 선언**한다(위 UNIT_NOTATION_MODES 주석). 챕터마다 다시 읽어
    # 두는 이유: 한 빌드가 여러 과목을 도는데 모듈 전역이라 이월되면 남의 과목에 새 판정이 샌다.
    set_unit_notation(unit_notation_of(ch_path))
    raw = json.dumps(ch, ensure_ascii=False)
    figure_lint_strict = is_strict_chapter(ch_path, FIGURE_LINT_STRICT_CHAPTERS, "figure_lint")
    arrow_connection_strict = is_strict_chapter(ch_path, ARROW_CONNECTION_STRICT_CHAPTERS,
                                                "arrow_connection")
    density_strict = is_strict_chapter(ch_path, DENSITY_STRICT_CHAPTERS, "density")
    prose_strict = is_strict_chapter(ch_path, PROSE_STYLE_STRICT_CHAPTERS, "prose_style")
    motif_path = os.path.join(os.path.dirname(ch_path), "textbook-motifs.json")
    motifs = []
    if os.path.isfile(motif_path):
        with open(motif_path, encoding="utf-8") as fh:
            motifs = json.load(fh).get("motifs") or []


    # 교재 소재(규칙 12⑵) — 챕터 전역을 훑는다. 이론 본문·삽화만 보던 탓에
    # comprehensionChecks.answer에 '감자'가 살아남았다(2026-07-22, iter_visible_texts 참조).
    for where, blob in iter_visible_texts(ch):
        for m in textbook_motif_hits(blob, motifs):
            (errors if prose_strict else warnings).append(
                where + ": 교재 소재를 그대로 씀 — '" + m["term"] + "' ("
                + m.get("source", "") + "). 대안: " + m.get("alternatives", "자체 발굴"))

    # theory sourceRef는 derivation.formulas[].sourceRef와 같은 문자열 형식이다.
    # 빈 문자열은 출처 입력 전의 명시적 상태로 허용하되 다른 타입은 조용히 통과시키지 않는다.
    for section in ch["theory"]["sections"]:
        if "sourceRef" in section and not isinstance(section["sourceRef"], str):
            errors.append("section " + section.get("id", "?") + ": sourceRef는 문자열이어야 함")
    for owner, ref in iter_source_refs(ch):
        bad = summary_only_source(ref)
        if bad:
            errors.append(owner + ": " + bad)

    # derivation topic은 스테퍼에서 연속된 묶음으로 표시한다.
    finished_topics = set()
    current_topic = None
    for f in ch["derivation"]["formulas"]:
        topic = f.get("topic")
        if not isinstance(topic, str) or not topic.strip():
            errors.append("formula " + f["id"] + ": derivation topic 누락 또는 빈 값")
            continue
        if topic != current_topic:
            if current_topic is not None:
                finished_topics.add(current_topic)
            if topic in finished_topics:
                errors.append("topic 블록이 끊김 — " + repr(topic))
            current_topic = topic

    if VEC_COMBINING in raw:
        errors.append("결합문자 U+20D7 존재 — Windows 폰트에서 깨짐, \\vec{} 또는 말로 풀 것")

    # latex 필드 렌더 가능성
    for f in ch["derivation"]["formulas"]:
        for line in latex_lines(f.get("latex", "")):
            check_latex_field("formula " + f["id"] + ".latex", line, errors)
        # 신설 필드(2026-07-26): 단계 안의 독립 식 줄도 LaTeX라 같은 검사를 받아야 한다.
        for i, st in enumerate(f.get("derivationSteps") or [], 1):
            for eq in step_equations(st):
                check_latex_field("formula " + f["id"] + ".derivationSteps[" + str(i) + "] 식",
                                  eq, errors)
        for k in f.get("variables", {}):
            check_latex_field("formula " + f["id"] + ".variables key", k, errors)
    for prob in ch.get("problems") or []:
        for i, st in enumerate(prob.get("solutionOutline") or [], 1):
            for eq in step_equations(st):
                check_latex_field("problem " + str(prob.get("id"))
                                  + ".solutionOutline[" + str(i) + "] 식", eq, errors)
    for p in ch.get("practice") or []:
        # 뷰어 stageMeta에 없는 stage는 카드가 열리는 순간 TypeError로 죽는다.
        # 열린 날 2026-07-26 — ch03이 'multi_blank'를 쓰는데 뷰어 표에 그 키가 없어
        # 문풀 5개 중 3개가 실제로 깨져 있었다. 런타임에서야 드러나는 결함이므로
        # 데이터가 뷰어의 어휘를 벗어나는 것을 빌드에서 막는다.
        if p.get("stage") not in PRACTICE_STAGES:
            errors.append("practice " + p["id"] + ": 뷰어가 모르는 stage — "
                          + repr(p.get("stage")) + " (허용: " + ", ".join(PRACTICE_STAGES) + ")")
        check_latex_field("practice " + p["id"] + ".solutionTemplate", p.get("solutionTemplate", ""), errors)
        for b in p.get("blanks") or []:
            check_latex_field("practice " + p["id"] + " blank " + b["id"], b.get("answer", ""), errors)
            if b.get("figureSlot"):
                svg = "".join(d.get("svg", "") for d in p.get("diagrams") or [])
                if "id='" + b["figureSlot"] + "'" not in svg and 'id="' + b["figureSlot"] + '"' not in svg:
                    errors.append("practice " + p["id"] + " blank " + b["id"] + ": figureSlot SVG id 없음")

    errors.extend(inline_math_issues(ch))
    errors.extend(difficulty_issues(ch))
    # 뷰어가 렌더할 수 있는 모양인가 — 런타임 계약이라 전 과목 error(위 주석이 정본).
    errors.extend(outline_shape_issues(ch))

    # 챕터 도입부 — status가 done인 챕터에만 요구한다(제작 중 챕터를 막지 않으려고).
    errors.extend(chapter_intro_issues(ch, ch_path))

    # plain 필드 표기 규약: **인라인 수식 밖**의 캐럿 금지.
    #
    # ★ 2026-07-27 개정 — 예전 규칙은 "plain 필드에 캐럿이 있으면 유니코드 위첨자로 바꾸라"였다.
    #   그 규칙이 `inline_math_issues`의 새 규칙과 정면으로 충돌한다: `\(e^{-h}\)`의 캐럿을
    #   금지당하면 `\(e⁻ʰ\)`로 되돌리게 되고, 그건 폰트가 뭉개는 바로 그 결함이다.
    #   **두 검사가 서로를 강요하는 교착**이었고, 실제로 이 결함을 유도한 것이 이 규칙이다
    #   (인박스 항목 6의 '구조적 원인'). 그래서 대상을 수식 밖 산문으로 좁힌다 —
    #   `y^2` 같은 날것 캐럿은 여전히 잡히고, `\(y^{2}\)`는 정상이 된다.
    for f in ch["derivation"]["formulas"]:
        plain = list(f.get("variables", {}).values()) + list(f.get("assumptions") or []) \
            + [f.get("notes", "")]
        # 단계는 **설명 문장만** 캐럿 검사 대상이다 — equations는 LaTeX라 `^`가 정상 표기다.
        plain += [step_prose(st) for st in f.get("derivationSteps") or []]
        for s in plain:
            if "^" in mask_inline_math(s):
                errors.append("formula " + f["id"] + ": 인라인 수식 **밖**에 캐럿 잔존 — "
                              "\\(…\\)로 감싸거나 숫자 위첨자로: " + repr(s[:40]))

    # 캐럿과 같은 부류인데 **첨자가 아닌** 기호들(∂ ∫ ≡ √)은 위 검사가 못 본다 → 챕터 전역으로 훑는다.
    (errors if prose_strict else warnings).extend(plain_math_issues(ch))
    # ★ 2026-07-31 **error 로 승격**. 예전에는 "ch01 이관이 끝날 때까지"라며 경고로 뒀는데,
    #   그 상태가 오래가면서 `V²/2`·`P/ρ` 처럼 **검사가 보지도 못하는 모양**이 그 옆에 쌓였다.
    #   이번에 자를 삽화 검사(C9)와 통일하고 전 챕터 48곳을 인라인 수식으로 옮겨 0건이 되었으므로
    #   경고로 남길 이유가 없다 — 경고로 두면 다음 것이 또 그 더미에 묻힌다(C1~C5 의 교훈).
    errors.extend(plain_fraction_issues(ch))
    # C38. 프라임 도함수를 인라인 수식 밖에 썼다 (2026-08-08, R-53 — 위 주석이 정본).
    # 승격은 과목별이다 — 다른 과목 데이터는 아직 안 봤고, 전 과목 error 로 박으면
    # 남의 빌드가 멈춘다(2026-08-02 사고와 같은 형태).
    (errors if is_strict_chapter(ch_path, (), "plain_prime")
     else warnings).extend(plain_prime_issues(ch))
    # C39. 인자를 중괄호로 감싸지 않은 매크로 (2026-08-12, 부류 1 — 위 주석이 정본).
    (errors if is_strict_chapter(ch_path, (), "latex_brace_arg")
     else warnings).extend(brace_arg_macro_issues(ch))
    # C26. 쉼표가 곱을 먹었다 (2026-08-04, R-41 — 위 `bare_comma_product_issues` 주석이 정본).
    # 승격은 과목별이다. 열역학 ch04·ch05 에 아직 남아 있고(이번 배치 범위 밖), 다른 과목도
    # 안 봤다 — 전 과목 error 로 박으면 남의 빌드가 멈춘다(2026-08-02 사고와 같은 형태).
    (errors if is_strict_chapter(ch_path, (), "comma_product")
     else warnings).extend(bare_comma_product_issues(ch))
    # C27. 계산 단계를 가로로 이어 붙였다 (2026-08-04, R-21·R-50 — 위 주석이 정본).
    (errors if is_strict_chapter(ch_path, (), "horizontal_step")
     else warnings).extend(horizontal_step_issues(ch))
    # C30. 문장을 수식으로 끝내고 마침표를 붙였다 (2026-08-04, R-49 — 위 주석이 정본).
    (errors if is_strict_chapter(ch_path, (), "math_sentence_end")
     else warnings).extend(math_sentence_end_issues(ch))
    # C18·C19 — 절 번호 링크 라벨 / 유도-이론 순서 (2026-08-02).
    # 둘 다 **데이터가 그 형태를 쓸 때만** 발동한다(`N절` 라벨 · `sectionRef`).
    # 그래서 아직 도입하지 않은 과목의 빌드를 깨뜨리지 않는다 — strict 승격 목록이
    # 과목을 넘나들며 남의 빌드를 멈춘 2026-08-02 사고를 되풀이하지 않기 위한 설계다.
    errors.extend(theory_link_number_issues(ch, os.path.splitext(os.path.basename(ch_path))[0]))
    # C50 — 장별 요약 절의 자리(위 함수 독스트링이 정본). 선언한 장에서만 발동한다.
    errors.extend(chapter_summary_placement_issues(ch))
    # C51 — 시험 수치 답 칸의 식 사슬(위 함수 독스트링이 정본). `exam` 을 쓰는 장에서만.
    errors.extend(exam_step_equation_issues(ch))
    # C52 — 시험 모드 장의 문항 삽화는 영어다(위 함수 독스트링이 정본). `examMode` 장에서만.
    errors.extend(exam_figure_language_issues(ch))
    # C53 — 요약 자리에 식이 있나(위 함수 독스트링이 정본). 요약·시험 모드 장에서만.
    errors.extend(summary_formula_issues(ch))
    errors.extend(derivation_section_order_issues(ch))
    errors.extend(reader_environment_issues(ch))
    errors.extend(math_slash_fraction_issues(ch))
    errors.extend(split_inline_subscript_issues(ch))
    # ★ 2026-07-30 신설 C1·C3·C4·C5 — 소급이 끝나 전 챕터 0건이 되었으므로 **error 로 승격**했다.
    # 승격 목록은 CONTENT_SPEC_STRICT_CHAPTERS 가 정본이고,
    # `test_strict_promotion_covers_all_chapters` 가 새 챕터의 누락을 자동으로 잡는다.
    content_spec_strict = is_strict_chapter(ch_path, CONTENT_SPEC_STRICT_CHAPTERS, "content_spec")
    spec_out = errors if content_spec_strict else warnings
    spec_out.extend(si_prefix_issues(ch))
    spec_out.extend(reveal_leak_issues(ch))
    spec_out.extend(dim_extension_origin_issues(ch))
    spec_out.extend(lever_rule_label_side_issues(ch))
    # C8 — 뒷 장으로 가는 내부 링크. 신설 즉시 ch01 의 nextLink 1건을 잡았고 같은 커밋에서
    # 고쳐 0건이 됐으므로 strict 여부와 무관하게 error 로 둔다(0건인 규격은 완화할 이유가 없다).
    errors.extend(forward_link_issues(ch))
    # C31 — 이해도 체크의 답 자리에 든 '아직 안 배운 장'·목차 빈칸(위 주석이 정본).
    # 승격은 과목별이다. C8 과 달리 전 과목 error 로 박지 않는 이유는 **다른 과목 데이터를
    # 아직 안 봤기 때문**이다 — 남의 빌드를 멈추는 2026-08-02 사고를 되풀이하지 않는다.
    (errors if is_strict_chapter(ch_path, (), "check_answer_scope")
     else warnings).extend(check_answer_scope_issues(ch))
    # C17 — 가운데점 3항목 나열. 승격 목록에 든 챕터만 error, 나머지는 경고(위 주석 참조).
    (errors if is_strict_chapter(ch_path, MIDDOT_STRICT_CHAPTERS, "middot")
     else warnings).extend(middot_list_issues(ch))
    # C40 — 수식 뒤 줄표. 기본 목록을 두지 않는다: 과목이 `index.json` 의
    # `strictChapters.math_label_dash` 로 선언한다(공통에 과목 사실을 박지 않는다).
    (errors if is_strict_chapter(ch_path, set(), "math_label_dash")
     else warnings).extend(math_label_dash_issues(ch))
    # C36 — 기호 사이의 가운데점(위 `symbol_middot_issues` 주석이 정본).
    # 승격은 과목별 선언뿐 — **공통 목록을 두지 않는다**(C20·C21~C23 과 같은 이유:
    # 공통 목록을 만들면 아직 정리하지 않은 과목의 회귀가 통째로 실패한다).
    (errors if is_strict_chapter(ch_path, (), "symbol_middot")
     else warnings).extend(symbol_middot_issues(ch))
    # C37 — 문항 수치가 삽화·정답과 어긋난 자리(위 `problem_number_issues` 주석이 정본).
    # 승격은 과목별 선언뿐 — 공통 목록을 두지 않는다(C36 과 같은 이유).
    (errors if is_strict_chapter(ch_path, (), "problem_numbers")
     else warnings).extend(problem_number_issues(ch))
    # C24 — 홑글자 `l` 을 길이 기호로 쓴 자리(위 `_BARE_ELL` 주석이 정본).
    # 승격 방식은 C21~C23 과 같다(공통 목록 없음) — 다른 과목 데이터에도 `l` 이 남아 있을 수
    # 있어 전 과목 error 로 박으면 그 빌드가 멈춘다.
    (errors if is_strict_chapter(ch_path, (), "bare_ell")
     else warnings).extend(bare_ell_issues(ch))
    # C22 — 우리 절을 `§N` 으로 가리킨 자리. 승격은 C20·C21 과 같은 방식(공통 목록 없음):
    # 다른 과목 데이터에도 `§N` 이 남아 있을 수 있으므로 전 과목 error 로 박으면 그 빌드가 멈춘다.
    (errors if is_strict_chapter(ch_path, (), "section_ref")
     else warnings).extend(section_ref_style_issues(ch))
    # C23 — 말투. 승격 방식은 C20~C22 와 같다(공통 목록 없음): 다른 과목 데이터는 아직
    # 평어일 수 있어 전 과목 error 로 박으면 그 빌드가 멈춘다.
    (errors if is_strict_chapter(ch_path, (), "tone")
     else warnings).extend(tone_issues(ch))
    # C9 — 삽화 안의 텍스트 분수. 같은 부류가 세 번 재발했고, 그때마다 지적받은 인스턴스만
    # 고쳤다. 산문 쪽(`plain_fraction_issues`)은 이관이 끝날 때까지 경고지만 이쪽은
    # **처음부터 error** 다 — 신고된 6건을 같은 커밋에서 고쳐 0건으로 만들었으므로,
    # 경고로 두면 그저 경고 더미에 묻힌다(C1~C5 의 교훈).
    errors.extend(svg_text_fraction_issues(ch))
    # C7 은 신설 즉시 3건을 잡았고(ch01 1 · ch02 2) 그 3건을 같은 커밋에서 고쳐 0건이 됐으므로
    # **경고를 거치지 않고 바로 승격**한다. 경고로 남기면 경고 더미에 묻힌다(C1~C5 의 교훈).
    spec_out.extend(untagged_dimension_issues(ch))
    # C10 — 치수보조선의 간격·넘김. 신설 즉시 34건을 잡았고 `fix_dim_extension.py` 로 같은
    # 커밋에서 0건으로 만들었으므로 error 다. 규격을 수치로 못박지 않으면 삽화마다 갈라진다.
    errors.extend(dim_extension_geometry_issues(ch))
    # C11 — 빈 dy 되돌림 tspan. 신설 즉시 44곳을 잡았고 같은 커밋에서 0건이 됐다.
    # 이 결함은 좌표가 아니라 **렌더 규칙**이라 기존 기하 검사가 하나도 못 봤다.
    errors.extend(empty_dy_reset_issues(ch))
    # C12 — 첨자를 아예 안 쓴 `h3` 꼴. 다른 첨자 검사는 전부 `_`·`^` 가 **있는** 것만 봐서
    # 이 부류는 여러 세션을 그대로 살아남았다(사용자 재지적 2026-08-01).
    errors.extend(raw_subscript_issues(ch))
    # C46 — 첨자에 한글. **지금 데이터가 0건이라 곧바로 error 로 연다**(0건일 때 켜는 것이
    # 이 리포의 정석이다 — 경고로 열면 다시 들어온 것이 경고 더미에 묻힌다).
    # 판정선과 사용자 원문은 위 `hangul_subscript_issues` 주석이 정본.
    errors.extend(hangul_subscript_issues(ch))
    # C13 — 답 슬롯 값이 삽화에 이미 적혀 있다. C4(가림 누수)는 `revealMode` 삽화만 보므로
    # `figureMode: hint` 인 문항은 **아무 검사도 없었다**(사용자가 q07 에서 찾아냈다).
    errors.extend(answer_slot_leak_issues(ch))
    # C14 — 답은 소문제로 갈렸는데 풀이는 평면 나열. 뷰어가 갈라 줄 근거(키)가 데이터에 없으면
    # 표시 단계에서 아무리 잘 만들어도 예전 그대로 나온다(사용자 지적 2026-08-01).
    errors.extend(outline_subq_key_issues(ch))
    # C16 — 주어진 조건값의 신호가 둘(칩 + 굵기). 이행 커밋에서 30곳을 0건으로 만들었으므로
    # 경고를 거치지 않고 바로 error 다. 경고로 두면 손으로 맞추던 시절이 조용히 되돌아온다.
    errors.extend(reveal_bold_issues(ch))
    # ★ 화살표 크기 — **선언한 챕터에만 error, 그 밖에는 아무 말도 하지 않는다.**
    #   경고 상태를 만들지 않는 이유: 이 리포는 경고를 폐지했고(close_report 가 잔량을 막는다),
    #   지금 열역학의 미적용분이 수십 건이라 경고로 내보내면 그 더미에 새 결함이 묻힌다.
    #   적용은 삽화 배치를 건드리는 일이라 별도 배치로 돈다(2026-08-02 사용자 판단: 70건 백로그와 같이).
    # ★ C32 — 삽화가 없으면 **없는 이유를 선언**하게 한다 (2026-08-05, 인박스 R-48).
    #   사용자: [사용자 발화 인용 생략] → **답할 근거가 없다는 것이 결함이었다.**
    #   규격은 *어떻게 그릴지*만 정하고 *언제 넣어야 하는지*를 안 정해서, 유무가 그때그때
    #   정해졌고 **안 넣은 이유가 아무 데도 없었다** — 의도인지 누락인지 구별할 방법이 없다.
    #   이 리포가 이미 쓰는 형태로 닫는다(`pendingChapters`·`lintWaivers`·`*-verdicts.json`):
    #   **판정을 파일에 남겨야 감사가 닫힌다.**
    if is_strict_chapter(ch_path, NO_DIAGRAM_STRICT_CHAPTERS, "no_diagram"):
        errors.extend(no_diagram_reason_issues(ch))
    # ★ C37 — 이론에 삽화가 한 장도 없는 챕터(위 `theory_figure_presence_issues` 주석이 정본).
    #   승격은 **과목별**이다 — 공통 목록을 만들면 `test_strict_promotion_covers_all_chapters`
    #   가 모든 과목의 실재 챕터를 요구해, 아직 삽화를 안 붙인 과목의 빌드가 즉시 멈춘다.
    if is_strict_chapter(ch_path, (), "theory_figures"):
        errors.extend(theory_figure_presence_issues(ch))
    # C38 — 유도 카드의 런타임 계약(위 `derivation_shape_issues` 주석이 정본).
    # `outline_shape_issues` 와 같이 **전 과목 error** 다. 승격 목록을 두지 않는 이유도 같다 —
    # 계약을 어긴 과목은 지금 이 순간 그 화면에 `undefined` 가 찍혀 있거나 탭이 비어 있다.
    errors.extend(derivation_shape_issues(ch))
    # C43 — 유도 카드가 자기 종류를 선언했는가(위 `derivation_kind_declaration_issues` 가 정본).
    # 승격은 과목별·챕터별이다 — 아직 안 가른 과목·챕터에서는 경고로 뜬다.
    (errors if is_strict_chapter(ch_path, (), "derivation_kind")
     else warnings).extend(derivation_kind_declaration_issues(ch))
    # C50 — 유도 슬라이드의 「삽화 한 벌」 계약(위 `derivation_slide_issues` 주석이 정본).
    # **전 과목 error 이되 선언이 곧 opt-in 이다** — `figure`·`show` 가 없는 카드는 통째로
    # 지나가므로 남의 빌드가 안 멈춘다. 선언한 카드는 어기는 순간 그 화면이 비어 있다(C38 과 같은 근거).
    errors.extend(derivation_slide_issues(ch))
    # C39 — 챕터 제목이 두 파일에서 갈라졌는가(위 `chapter_title_agreement_issues` 주석이 정본).
    # C38 과 같이 **전 과목 error** 다 — 화면에 나가는 값의 계약이라 승격 목록을 두지 않는다.
    errors.extend(chapter_title_agreement_issues(ch, ch_path))
    # C42 — 분수 안의 분수. **전 과목 error**(렌더 계약이라 승격 목록을 두지 않는다).
    errors.extend(nested_frac_issues(ch))
    # C44 — 기호와 물리량이 과목이 정한 표기와 맞는가(위 `symbol_role_issues` 주석이 정본).
    # `terms.json` 에 `symbols` 를 선언한 과목에서만 돈다 — 선언이 곧 opt-in 이라 승격 목록이 없다.
    # 제외 낱말에 **폴백을 두지 않는다** — 빠뜨리면 `가속도` 가 `속도` 선언으로 잡혀
    # 그 과목 빌드가 즉시 시끄러워진다. 조용히 지나가는 쪽이 아니라 바로 드러나는 쪽이다.
    # 승격은 과목별·챕터별이다(`strictChapters.symbol_role`) — 표기를 옮기는 데이터 작업이
    # 여러 회차에 걸치므로, 옮긴 챕터부터 error 로 올린다. 안 올린 챕터는 경고로 뜨고
    # 경고는 `close_report` 가 close 를 막으므로 묻히지 않는다.
    (errors if is_strict_chapter(ch_path, (), "symbol_role")
     else warnings).extend(symbol_role_issues(ch, _terms_section(ch_path, "symbols"),
                                              _terms_list(ch_path, "symbolNotRoles")))
    # C45 — 산문·삽화에서 역할 낱말 옆의 기호(위 `symbol_role_word_issues` 주석이 정본).
    # C44 와 같은 승격 목록을 쓴다 — 같은 규격의 두 자리라 따로 놀면 한쪽만 켜진다.
    (errors if is_strict_chapter(ch_path, (), "symbol_role")
     else warnings).extend(symbol_role_word_issues(ch, _terms_section(ch_path, "symbols"),
                                                   _terms_list(ch_path, "symbolNotRoles"),
                                                   _terms_section(ch_path, "symbolGlyphs")))
    # C46 — 한 항목 안에서 같은 형태가 두 표기로 갈렸는가(위 `symbol_split_issues` 주석이 정본).
    # C44·C45 와 같은 승격 목록을 쓴다 — 같은 규격의 세 자리라 따로 놀면 한쪽만 켜진다.
    (errors if is_strict_chapter(ch_path, (), "symbol_role")
     else warnings).extend(symbol_split_issues(ch, _terms_section(ch_path, "symbols"),
                                               _terms_section(ch_path, "symbolGlyphs")))
    # C41 — 용어 한영 병기. 목록은 그 과목 폴더가 갖는다(`terms.json`). 파일이 없으면
    # 그 과목은 아직 선언하지 않은 것이라 아무것도 안 본다 — 폴백 목록을 두지 않는다.
    (errors if is_strict_chapter(ch_path, set(), "term_pairing")
     else warnings).extend(term_pairing_issues(ch, subject_terms(ch_path)))
    if is_strict_chapter(ch_path, ARROW_STRICT_CHAPTERS, "arrow"):
        for fig_id, dg in iter_chapter_diagrams(ch):
            svg = str(dg.get("svg") or "")
            errors.extend(figure_arrow_scale_issues(fig_id, _figure_view_width(svg), svg))
    # 관의 안쪽 폭과 화살촉은 같은 SVG 좌표계에서 직접 비교할 수 있으므로 전 과목 error다.
    # 여기를 경고로 두면 '화살표가 벽에 붙어도 빌드는 통과'하는 원래 구조가 되살아난다.
    for fig_id, dg in iter_chapter_diagrams(ch):
        errors.extend(pipe_arrow_clearance_issues(fig_id, str(dg.get("svg") or "")))
    # 마이터 가시 — **전 과목 error 다**(AGENTS 「close의 정의」: 새 검사의 기본값).
    # 과목 선언을 태우지 않는 이유는 좌표만으로 판정되기 때문이다 — 어느 과목이든 같은 기하이고,
    # 처방도 `stroke-linejoin='round'` 하나뿐이라 `tools/fix_miter_join.py` 로 한 번에 닫힌다.
    # ★ 순회에 **슬라이드 원본 한 장**을 더한다. `_iter_diagrams` 는 `diagrams` 만 흘리는데
    #   정작 이 결함이 처음 잡힌 곳이 슬라이드였다 — 그것만 보면 「0건」이 아니라 「한 건도 안 본 것」이다.
    #   단계 조각(`slide_step_figures`)이 아니라 원본을 먹인다: 기하는 어느 단계가 보이든 같고,
    #   조각으로 넣으면 같은 꼭짓점이 단계 수만큼 신고된다.
    for dg in list(_iter_diagrams(ch)) + slide_card_figures(ch):
        svg = str(dg.get("svg") or "")
        errors.extend(miter_spike_issues(str(dg.get("id") or "?"),
                                         _figure_view_width(svg), svg))
    # C18·C19 — 선도의 라벨 위치와 곡선 형태. 승격은 **과목별**이다(위 상수 주석 참조):
    # 선언 어휘(`data-shape`)를 아직 안 붙인 과목의 빌드를 멈추게 하지 않는다.
    # C33·C34(`free` 판정 기록·형상 비율)와 지시선 규격도 같은 승격을 탄다 — 셋 다
    # '선도를 어떻게 그리나' 의 규격이라 진도를 따로 두면 어느 것이 남았는지 알 수 없다.
    (errors if is_strict_chapter(ch_path, PLOT_STRICT_CHAPTERS, "plot")
     else warnings).extend(
        plot_label_outside_issues(ch) + plot_curve_shape_issues(ch)
        + plot_shape_declaration_issues(ch, ch_path)
        + [m for fid, dg in iter_chapter_diagrams(ch)
           for m in leader_line_issues(fid, str(dg.get("svg") or ""))]
        # 축 방향 화살표 — 규칙만 있고 자가 없어 삽화마다 갈렸다(위 checks_svg 주석이 정본).
        + [m for fid, dg in iter_chapter_diagrams(ch)
           for m in axis_arrow_issues(fid, str(dg.get("svg") or ""))])
    # 중심선은 1점 쇄선이다(위 `checks_svg.centerline_style_issues` 주석이 정본).
    # ★ **전 과목 error 로 둔다** — `class='axis'` 는 이 규격을 아는 삽화만 쓰는 태깅이라
    #   안 쓰는 과목에는 대상이 0건이다(실측 2026-08-23: thermo·math·solids·materials 0건).
    #   즉 «선언이 곧 opt-in» 이라 남의 빌드를 멈추지 않는다(C50 과 같은 근거).
    errors.extend([m for fid, dg in iter_chapter_diagrams(ch)
                   for m in centerline_style_issues(fid, str(dg.get("svg") or ""))])
    # C38 — 화살촉 접합부의 흰 이음매(위 `checks_svg.arrowhead_seam_issues` 주석이 정본).
    # 승격은 과목별 선언뿐 — 공통 목록을 두지 않는다(C36·C37 과 같은 이유: 다른 과목 삽화는
    # 아직 `fix_arrow_seam` 을 안 돌렸고, 전 과목 error 로 박으면 그 빌드가 통째로 멈춘다).
    (errors if is_strict_chapter(ch_path, (), "arrow_seam") else warnings).extend(
        [m for fid, dg in iter_chapter_diagrams(ch)
         for m in arrowhead_seam_issues(fid, str(dg.get("svg") or ""))])
    # 축 이름–화살촉 **거리**(1.0em). 화살표 유무와 갈라 잰다 — 한 자로 묶으면 '화살표가
    # 없다'는 틀린 진단이 거리 결함에 붙는다. 승격은 과목별(다른 과목은 아직 실측 전).
    (errors if is_strict_chapter(ch_path, (), "axis_gap") else warnings).extend(
        m for fid, dg in iter_chapter_diagrams(ch)
        for m in axis_name_gap_issues(fid, str(dg.get("svg") or "")))
    for prob in (ch.get("problems") or []):
        where = "problems[" + str(prob.get("id", "?")) + "]"
        spec_out.extend(where + ": " + m for m in answer_slot_count_mismatch(prob))

    # pitfalls 스키마: source 필수 + 허용 3종
    def check_pits(owner, pits):
        for pit in pits or []:
            if not all(k in pit for k in ("id", "note", "source")):
                errors.append(owner + ": pitfall 필드 누락 (id/note/source)")
            elif not pit["source"].startswith(PITFALL_SOURCE_PREFIXES):
                errors.append(owner + ": pitfall source 형식 위반 — " + repr(pit["source"]))
    # 이해도 체크 개수 상한 — 한 절에 너무 많으면 읽는 흐름이 끊겨 오히려 역효과다
    # (2026-07-22 지적: sec-stored-energy 12개). 진짜 중요한 것만 남긴다.
    for kind, item in _iter_check_owners(ch):
        n = len(item.get("comprehensionChecks") or [])
        if n > CHECKS_MAX_PER_SECTION:
            (errors if prose_strict else warnings).append(
                kind + " " + item.get("id", "?") + ": 이해도 체크 " + str(n) + "개 (한계 "
                + str(CHECKS_MAX_PER_SECTION) + ") — 진짜 중요한 것만 남길 것")
    for s in ch["theory"]["sections"]:
        check_pits("section " + s["id"], s.get("pitfalls"))
    for f in ch["derivation"]["formulas"]:
        check_pits("formula " + f["id"], f.get("pitfalls"))

    # ★ 오답로그 정합성 (2026-08-01 신설) — 이 파일을 읽는 도구가 여태 0개였다.
    # 접두어만 보던 탓에 **없는 번호를 인용해도 통과**했고, 더 큰 구멍은 `entries` 가
    # 오답만 남아 '채점을 안 했다'와 '했는데 걸린 게 없다'가 구별되지 않았다는 것이다.
    # 전말은 checks_errorlog 모듈 독스트링.
    _elog = load_errorlog(os.path.dirname(ch_path))
    if _elog is not None:
        for msg in pitfall_entry_reference_issues(ch, _elog):
            errors.append(msg)
        # 로그 자체의 정합성은 챕터와 무관하므로 **빌드 한 번에 한 번만** 신고한다.
        # (챕터마다 내면 같은 줄이 6번 찍힌다 — 면제 목록이 그렇게 부풀었던 전례가 있다.)
        _dir = os.path.dirname(ch_path)
        if _dir not in _ERRORLOG_REPORTED:
            _ERRORLOG_REPORTED.add(_dir)
            _e, _w = errorlog_issues(_elog)
            errors.extend(_e)
            warnings.extend(_w)

    # C50 — 이해도 점검은 단계를 **`stage`** 로 선언한다 (열린 날 2026-08-13, 고체역학 실측 202곳).
    #   ★ **선언이 없어도 아무 데서도 안 걸리던 자리다.** 고체역학은 전 챕터가 단계를 `type` 으로
    #     적고 있었는데 뷰어는 `c.stage` 를 읽는다 — 브라우저 실측 결과 배지에 문자 그대로
    #     **`undefined`** 가 찍히고 있었다(ch11 13개 전부). 화면이 그런데도 빌드는 통과했다.
    #   ★★ 조용히 꺼진 것이 배지만이 아니다. `stage` 를 키로 쓰는 검사 셋(답 길이 C49 ·
    #     연결하기/설명하기 답 누락 · 답 칸에 채점 키워드) 이 **한 과목에서 통째로 안 돌았다.**
    #     「미선언이면 검사가 아예 안 돈다」는 opt-in 침묵과 같은 부류인데, 이쪽은 선언 자리가
    #     `index.json` 이 아니라 **데이터 안**이라 `close_report` 의 침묵 점검에도 안 잡혔다.
    #   → 그래서 키 이름 자체를 검사한다. 오타·다른 이름은 **error** 다(경고면 또 묻힌다).
    for _owner_kind, _item in _iter_check_owners(ch):
        for check in _item.get("comprehensionChecks") or []:
            if str(check.get("stage") or "").strip() in CHECK_ANSWER_MAX_SENTENCES:
                continue
            where = (_owner_kind + " " + str(_item.get("id", "?"))
                     + " check " + str(check.get("id", "?")))
            if str(check.get("type") or "").strip() in CHECK_ANSWER_MAX_SENTENCES:
                errors.append(where + ": 이해도 점검의 단계를 `type` 으로 적었다 — 키 이름은 "
                              "`stage` 다. 뷰어가 `c.stage` 를 읽으므로 배지에 `undefined` 가 "
                              "찍히고 답 길이·답 누락 검사도 통째로 건너뛴다")
            else:
                errors.append(where + ": 이해도 점검에 `stage` 선언이 없다 — "
                              + " · ".join(sorted(CHECK_ANSWER_MAX_SENTENCES)) + " 중 하나여야 한다")

    # C49 — 이해도 점검의 답 길이 상한 (열린 날 2026-08-13, 승격 잔량 ch01 「G」 를 갚으며).
    #   그 항목이 남긴 말: [사용자 발화 인용 생략]
    #   ★ 자를 눈으로 고르지 않았다 — `audit_checks_load.py --lengths` 로 먼저 쟀다.
    #     실측(2026-08-13 · 열역학 240개): 떠올리기 1문장 **95%** · 연결하기 1~2문장 **93%** ·
    #     설명하기 최대 4문장. 상한은 **그 분포의 꼬리 바깥**에 둔다(아래 상수 옆 주석).
    #   ★★ 단계마다 값이 다른 이유는 **용도가 다르기 때문**이다. 떠올리기는 «한 줄로 튀어나와야»
    #     인출이고, 설명하기는 근거를 이어 붙이는 자리라 같은 자로 재면 한쪽이 반드시 틀어진다.
    for _owner_kind, _item in _iter_check_owners(ch):
        for check in _item.get("comprehensionChecks") or []:
            cap = CHECK_ANSWER_MAX_SENTENCES.get(check.get("stage"))
            if not cap:
                continue
            n = check_answer_sentences(str(check.get("answer") or ""))
            if n > cap:
                where = (_owner_kind + " " + str(_item.get("id", "?"))
                         + " check " + str(check.get("id", "?")))
                msg = (where + ": " + str(check.get("stage")) + " 답이 " + str(n)
                       + "문장이다 (상한 " + str(cap) + ") — 이 단계는 "
                       "**한 번에 인출되는 길이**여야 한다. 근거를 더 달고 싶으면 답을 늘리지 말고 "
                       "`gradingKeywords` 로 옮길 것")
                if is_strict_chapter(ch_path, (), "check_answer_length"):
                    errors.append(msg)
                else:
                    warnings.append(msg)

    # 누적 품질 계약: 연결하기/설명하기는 문제 → 완전한 답 → 채점 키워드 순서다.
    # ch02에서 답 칸에 키워드 목록을 넣고 실제 답을 explanation으로 미룬 회귀를 막는다.
    # ★ 이론뿐 아니라 유도·문풀·연습문제까지 전부 본다 — 이론만 보던 탓에 ch02 유도 11건이
    #   같은 결함을 그대로 통과했다(2026-07-21). 체크가 붙을 수 있는 곳은 모두 순회할 것.
    for _owner_kind, _item in _iter_check_owners(ch):
        for check in _item.get("comprehensionChecks") or []:
            if check.get("stage") not in ("connect", "explain"):
                continue
            owner = _owner_kind + " " + str(_item.get("id", "?")) + " check " + check.get("id", "?")
            answer = str(check.get("answer", "")).strip()
            if not answer:
                errors.append(owner + ": 연결하기/설명하기 answer 누락")
            if answer.startswith("채점 키워드"):
                errors.append(owner + ": answer에 채점 키워드 목록을 대신 넣음")
            if re.match(r"^(그래서|따라서|그러므로)\b", answer):
                errors.append(owner + ": answer가 앞 문맥 없는 접속어로 시작함")
            if not check.get("gradingKeywords"):
                errors.append(owner + ": gradingKeywords 누락")
            if check.get("explanation"):
                errors.append(owner + ": 완전한 답을 explanation으로 분리하지 말고 answer에 둘 것"
                                      " — 답이 아니라 **답 뒤에 떠오르는 다음 질문**이면 `followUp` 에 둔다")

    errors.extend(follow_up_issues(ch))

    # 본문 인라인 딥링크 [[chNN:section-id|라벨]]의 대상이 실제로 있는지 검사한다.
    # 대상 절 이름이 바뀌면 조용히 죽은 링크가 되므로 빌드에서 잡는다.
    xlink_pat = re.compile(r"\[\[(ch\d{2}):([A-Za-z0-9_-]+)(?:/([A-Za-z0-9_-]+))?\|([^\]]+)\]\]")
    # 과목 간 딥링크 [[과목폴더@chNN:sec-id|라벨]] (2026-08-29). 대상이 다른 git 브랜치에 있어
    # 이 빌드는 건너가 검증하지 못한다(과목 = 브랜치 경계, AGENTS 「과목 병렬 작업」) — 형식만
    # 확인하고 존재 여부는 저자가 `git show <브랜치>:data/<과목>/chNN.json` 로 손수 확인해야
    # 한다는 경고를 낸다. error 로 올리지 않는 이유: 못 보는 것을 못 본다고 하는 것과 틀렸다고
    # 하는 것은 다르다(AGENTS 규칙 11 「미검증」).
    cross_xlink_pat = re.compile(
        r"\[\[([^@\[\]]+)@(ch\d{2}):([A-Za-z0-9_-]+)(?:/([A-Za-z0-9_-]+))?\|([^\]]+)\]\]")
    chapter_dir = os.path.dirname(ch_path)
    # 뷰어가 이 앵커를 실제로 받아 착지시키는지 — 정본은 템플릿의 DEEP_LINK_HASH다.
    template_path = os.path.join(os.path.dirname(os.path.dirname(chapter_dir)),
                                 "site", "template", "viewer.template.html")
    deep_link_re, prose_sub_res = None, []
    if os.path.isfile(template_path):
        with open(template_path, encoding="utf-8") as fh:
            _template_src = fh.read()
        deep_link_re = viewer_deep_link_pattern(_template_src)
        prose_sub_res = viewer_prose_subscript_patterns(_template_src)
    if deep_link_re is None:
        errors.append("뷰어 템플릿에서 DEEP_LINK_HASH를 찾지 못함 — 딥링크 착지 검사를 못 한다")
    # C45 — 밑글자가 화면에서 첨자를 못 받는 자리(위 `unrendered_subscript_issues` 주석이 정본).
    # 승격은 과목별 선언뿐 — 공통 목록을 두지 않는다(C36·C22·C23 과 같은 이유: 다른 과목
    # 데이터에도 같은 글자가 남아 있을 수 있어 전 과목 error 로 박으면 그 빌드가 멈춘다).
    (errors if is_strict_chapter(ch_path, (), "subscript_render")
     else warnings).extend(unrendered_subscript_issues(ch, prose_sub_res))
    for s in ch["theory"]["sections"]:
        for m in cross_xlink_pat.finditer(s.get("content", "")):
            subj, target_ch, target_id = m.group(1), m.group(2), m.group(3)
            warnings.append("section " + s["id"] + ": 과목 간 딥링크 — " + subj + "@" + target_ch
                            + ":" + target_id + " 존재 여부는 이 빌드가 검사하지 못한다"
                            " (git show 로 손수 확인할 것)")
        for m in xlink_pat.finditer(s.get("content", "")):
            target_ch, target_id, target_child, label = m.group(1), m.group(2), m.group(3), m.group(4)
            target_path = os.path.join(chapter_dir, target_ch + ".json")
            if not os.path.isfile(target_path):
                errors.append("section " + s["id"] + ": 딥링크 대상 챕터 없음 — " + target_ch)
                continue
            with open(target_path, encoding="utf-8") as fh:
                target = json.load(fh)
            section_ids = {x.get("id") for x in (target.get("theory") or {}).get("sections") or []}
            valid = xlink_target_valid(target, target_id, target_child)
            # ★ 뷰어가 이 해시를 실제로 착지시키는가 — 대상이 존재해도 뷰어가 못 받으면 죽은 링크다.
            if valid and deep_link_re is not None:
                fragment = xlink_fragment(target_id, target_child)
                if not deep_link_re.match("#" + fragment):
                    errors.append("section " + s["id"] + ": 딥링크 앵커를 뷰어가 인식 못 함 — #"
                                  + fragment + " (DEEP_LINK_HASH와 대조)")
            # ★ 착지점 검사 — 판정은 xlink_landing_issue(테스트 대상)에 있다.
            if valid:
                by_id = {x.get("id"): x for x in (target.get("theory") or {}).get("sections") or []}
                finer = xlink_landing_issue(label, target_id, target_child, section_ids, by_id)
                if finer:
                    (errors if prose_strict else warnings).append(
                        "section " + s["id"] + ": 딥링크가 절 맨 위로 착지함 — " + repr(label[:24])
                        + " → 더 좁은 앵커를 쓸 것(" + ", ".join(finer[:3])
                        + ") 또는 표시 문구에 '절'이라고 밝힐 것")
                # ★ 문구↔착지 내용 대조 — 판정은 xlink_topic_issue(테스트 대상)에 있다.
                missing = xlink_topic_issue(label, xlink_landing_text(target, target_id, target_child))
                if missing:
                    (errors if prose_strict else warnings).append(
                        "section " + s["id"] + ": 딥링크 문구가 착지 내용과 어긋남 — " + repr(label[:28])
                        + " → 착지 화면에 없는 말: " + ", ".join(missing[:5]))
            if not valid:
                errors.append("section " + s["id"] + ": 딥링크 대상 절 없음 — "
                              + target_ch + ":" + target_id + ("/" + target_child if target_child else "") + " (" + label + ")")

    # 삽화가 있는 문제는 공개 정책을 반드시 명시한다 (기본값에 기대면 판단을 건너뛰게 된다).
    # given = 삽화가 본문에 없는 정보(배치·연결·기하)를 담아 문제 해석에 필수인 경우,
    # hint  = 모델링 자체가 학습 목표라 접어 두는 경우. 2026-07-21 사용자 지적으로 도입.
    for q in ch.get("problems") or []:
        if not q.get("diagrams"):
            continue
        mode = q.get("figureMode")
        if mode not in ("given", "hint"):
            errors.append(q["id"] + ": figureMode 미선언 — 'given'(해석에 필수) 또는 'hint'(모델링 연습) 중 하나를 명시할 것")

    # ★ 물음의 단위 ↔ 답의 단위 (2026-07-21 신설 → **2026-07-30 방향 반전**).
    #
    # 원래 이 검사는 [사용자 발화 인용 생략] 이었다 — 프롬프트가 `[N]` 이면 답도 `N` 으로 쓰고
    # 접두어는 괄호 병기로만 두라는 규칙이었다. **그것이 W-46 의 진짜 원인이었다.**
    # 사용자가 [사용자 발화 인용 생략] 라고 지적한 자리들이
    # 바로 이 검사가 **지키고 있던** 형태다. 즉 데이터가 게을러서 남은 게 아니라
    # **검사가 기본단위를 강제**하고 있었다(2026-07-30 실측: `8440 N/m³ (8.44 kN/m³)` 형태가 그 산물).
    #
    # 사용자 결정은 반대다 — **접두어가 정본**이고, 그러면 바뀌어야 하는 것은 **프롬프트의 `[단위]`** 다.
    # 그래서 규칙을 "어느 쪽을 앞세우라" 가 아니라 **"양쪽이 같아야 한다"** 로 바꾼다(대칭).
    # 어느 쪽으로 맞출지는 사람이 정한다 — 검사는 어긋남만 신고한다.
    for q in ch.get("problems") or []:
        for msg in prompt_answer_unit_mismatch(q):
            errors.append(str(q.get("id", "?")) + ": " + msg)

    # 최종답 유효숫자: 선두 유효숫자가 1이면 4자리, 그 외는 3자리.
    # (선두 1은 자릿수당 상대정밀도가 낮아 한 자리를 더 남긴다.)
    # 오탐을 막기 위해 아래는 검사 대상에서 뺀다 — 41건 시험에서 오탐 0건인 조합이다:
    #   · 정수인데 끝자리가 0 (21,600 / 8440 / 700) — 유효숫자가 모호하고 문제의 주어진 값인 경우가 많다
    #   · 숫자 바로 뒤가 한글 (2배, 3가지) — 산문 속 수이지 답이 아니다
    #   · 유효숫자 1자리 — 지시·개수
    #
    # ★★ **이 검사는 「잰 값」이 있는 과목의 것이다 (2026-08-25, 공학수학 실측).**
    #   유효숫자는 **측정 정밀도의 표기**다. 순수수학 과목의 답은 전부 **정확한 정수·유리수**라
    #   정밀도라는 개념이 아예 없고, 그런 과목에서는 이 규칙이 **데이터를 틀리게 만든다** —
    #   특성다항식 계수 `24` 를 `24.0` 으로 적으라는 요구가 된다.
    #   ★ 그리고 여기서도 **우연히 갈렸다**: 「정수인데 끝자리 0」 면제가 `70`·`30`·`210` 을
    #     살리고 `63`·`15`·`13`·`24`·`36` 만 걸었다(실측 9건). 규칙이 판정한 적 없는데
    #     결과의 절반이 맞아 보이는 모양이라 같은 날 밀러 지수와 나란히 드러났다.
    #   → 과목이 `index.json` 의 `strictWaivers.answer_sigfig` 에 **사유와 함께** 끌 수 있게 한다.
    #     기본은 여전히 error 다(옛 키가 아니므로 선언 없이 켜진 채다) — 끄는 쪽이 사유를 적는다.
    sigfig_subjects = (ch.get("problems") or []) if is_strict_chapter(
        ch_path, (), "answer_sigfig") else []
    for q in sigfig_subjects:
        answer = str(q.get("answer", ""))
        for m in re.finditer(r"(?<![\d.,])(\d[\d,]*(?:\.\d+)?)(.?)", answer):
            token, nxt = m.group(1), m.group(2)
            if "가" <= nxt <= "힣":
                continue
            # ★ 결정면·방향 지수는 「잰 값」이 아니다 (2026-08-25, materials 실측).
            #   `(111)`·`[111]`·`{111}`·`〈111〉` 의 111 을 유효숫자 규칙에 걸면 `111.0` 이
            #   되는데 **그건 명백히 틀린 데이터다** — 밀러 지수에는 정밀도라는 것이 없다.
            #   ★ 더 나쁜 것은 **우연히 갈렸다는 점**이다: 옛 면제 조항 「소수점 없이 0 으로
            #     끝남」 덕에 `(110)`·`(100)` 은 조용히 빠지고 **`111` 만 걸렸다.** 규칙이
            #     그것을 판정한 적이 없는데 결과만 반쯤 맞아 보였다.
            #   판정선은 **괄호 안의 정수 묶음**이다(쉼표 구분 `(1,1,0)` 도 같은 표기).
            #   소수점이 있으면 지수가 아니므로 그대로 잰다.
            if "." not in token and _is_bracketed_index(answer, m.start(), m.start() + len(token)):
                continue
            raw = token.replace(",", "")
            if "." not in raw and raw.endswith("0"):
                continue
            if "." in raw:
                digits = len(raw.lstrip("0").replace(".", "").lstrip("0"))
            else:
                digits = len(raw.lstrip("0"))
            if digits < 2:
                continue
            lead = raw.lstrip("0.").lstrip("0")[:1]
            need = 4 if lead == "1" else 3
            if digits != need:
                errors.append(q["id"] + ": 최종답 유효숫자 — " + repr(token) + "은 "
                              + str(digits) + "자리인데 선두가 " + lead + "이므로 "
                              + str(need) + "자리여야 한다")

    # 아래첨자(X_sub)는 뷰어의 fmtText를 거치는 필드에만 쓸 수 있다.
    # esc()로 렌더되는 필드에 넣으면 화면에 'dE_system/dt'처럼 날것으로 나온다
    # (2026-07-21 assumptions에서 실제 발생 — 과거에 prompt만 고치고 이 필드를 놓쳤다).
    # 새 필드에 아래첨자를 쓰려면 먼저 뷰어에서 fmtText로 렌더한 뒤 여기 등록할 것.
    subscript_pat = re.compile(r"[A-Za-zγρΔ]_(?:\{[^}]+\}|[A-Za-z0-9]+)")
    # exempt_keys는 하위까지 전파된다 (sourcePages처럼 dict 안에 편집 메모가 들어가는 경우).
    # ★ `equations` 는 `latex` 와 **같은 부류**다 — 필드 전체가 LaTeX 이고 뷰어가
    #   `renderMathLines` → `renderMath` 로 그리므로 `_{}` 가 정상 표기다(2026-08-26 추가).
    #   그전에는 `solutionOutline` 이 등록부에 있어 그 아래 `equations` 만 우연히 통과했고,
    #   같은 필드가 다른 부모(`exam.steps`) 밑에 생기자 곧바로 막혔다 — 부모에 기대던 자리다.
    exempt_keys = {"svg", "latex", "equations", "id", "sourceRef", "source", "stage", "topic",
                   "difficulty", "href", "sourcePages", "supplementNotes"}
    fmttext_fields = {
        "content", "prompt", "answer", "explanation", "gradingKeywords", "note", "notes",
        # followUp(2026-08-14 신설): 뷰어 renderChecks 가 fmtText(c.followUp) 로 렌더한다.
        "followUp",
        "hint", "statement", "label", "english", "value", "assumptions", "derivationSteps",
        "solutionOutline", "solutionTemplate", "title", "heading", "rationale", "keywords",
        "variables",  # dict — 값이 fmtText로 렌더된다
        # expectedOutput: 뷰어 renderPracCard가 fmtText(p.expectedOutput)로 렌더한다(확인 2026-07-26).
        # 등록이 빠져 있어 최종 답에 아래첨자를 못 쓰고 있었다 — 검사가 틀린 게 아니라 등록부가 낡았다.
        "expectedOutput",
        # 챕터 도입부(2026-07-26): summary·question·prerequisite·nextLink 전부 fmtText 경로다.
        "chapterIntro",
        # appliesTo(2026-07-26 신설): "이런 형태일 때 이 방법을 쓴다"를 공식보다 **위**에 렌더한다.
        # 뷰어 renderDerivCard가 fmtText로 그리므로 아래첨자·인라인 수식이 통한다.
        "appliesTo",
        # 시험 모드(2026-08-26 신설): 뷰어 `examStepBody` 가 선택지·짝짓기 왼쪽을 fmtText 로 그린다.
        # ★ 이 자리에 아래첨자가 실제로 필요하다 — 「③ 무엇을 세우나」의 보기가 곧 식이라
        #   `v = v_{0} + at` 처럼 첨자가 든 후보를 나란히 놓아야 고르는 일이 성립한다.
        #   `right`(짝짓기 오른쪽)는 esc() 로 그리므로 **일부러 뺐다** — 거기 첨자를 쓰면 날것으로 나온다.
        "options", "left",
        # symbol(2026-07-30 신설, W-44): `givenSubResults` 를 3열 그리드로 갈 때
        # 설명과 분리한 기호 열이다. 뷰어 renderPracCard 가 `fmtText(sr.symbol)` 로 그린다.
        # ★ 새 필드를 만들면 **여기 등록**해야 아래첨자를 쓸 수 있다 —
        # 등록을 잊으면 검사가 "미렌더 필드"로 막는다(그게 이 등록부의 목적이다).
        "symbol",
    }

    def scan_subscripts(node, key=None, trail="root", rendered=False):
        # rendered=True면 상위 필드가 이미 fmtText 경로라, 그 아래 문자열은 전부 렌더된다
        # (예: variables는 dict이고 값들이 fmtText로 렌더된다 — 키 이름에 속지 말 것).
        if isinstance(node, dict):
            for k, v in node.items():
                if k in exempt_keys:
                    continue
                scan_subscripts(v, k, trail + "/" + str(k), rendered or k in fmttext_fields)
        elif isinstance(node, list):
            for v in node:
                scan_subscripts(v, key, trail, rendered)
        elif isinstance(node, str):
            if rendered or key in exempt_keys or key is None:
                return
            if key in fmttext_fields:
                return
            if subscript_pat.search(node):
                errors.append(trail + ": 아래첨자가 미렌더 필드에 있음 — "
                              "fmtText로 렌더하도록 뷰어를 고치고 fmttext_fields에 등록할 것 "
                              + repr(node[:60]))

    scan_subscripts(ch)

    # relatedFormulas 참조 무결성 (practice에도 추가됨)
    fids = {f["id"] for f in ch["derivation"]["formulas"]}
    for coll in ("practice", "problems"):
        for item in ch.get(coll) or []:
            for fid in item.get("relatedFormulas") or []:
                if fid not in fids:
                    errors.append(coll + " " + item["id"] + ": relatedFormulas 미해결 id " + fid)

    # 별표 강조는 뷰어가 렌더하지 않아 화면에 날것으로 나온다 — 이론 본문만이 아니라
    # 산문이 사는 모든 자리에서 막는다(2026-07-24 재발, iter_prose_fields 주석 참조).
    # 굵게 개수·헤딩 규칙은 목록형 필드에서 오탐이 크므로 이론 본문에만 건다.
    for owner, text in iter_prose_fields(ch):
        for why, snippet in prose_style_problems(text):
            # 대시 줄도 함께 본다(2026-07-28) — 별표와 같은 부류로, 뷰어가 목록으로 만들지
            # 못한 대시가 화면에 날것으로 남는다. 판정이 명확해 목록형 필드에서도 오탐이 없다.
            if "별표" not in why and "대시" not in why:
                continue
            (errors if prose_strict else warnings).append(owner + ": " + why + " — " + repr(snippet))

    # 조용히 삼켜지는 줄바꿈 — 전말은 swallowed_newline_blocks 독스트링.
    # 데이터에는 `\n`이 있는데 화면은 한 줄로 이어져, '고쳤다'가 거짓이 되는 부류다.
    for owner, text in iter_line_break_fields(ch):
        for block in swallowed_newline_blocks(text):
            (errors if prose_strict else warnings).append(
                owner + ": 블록 안 단일 개행은 화면에서 공백으로 접힌다 —"
                " 빈 줄(\\n\\n)로 나누거나 목록(`- `)으로 쓸 것 — " + repr(block[:70]))

    # 누적 품질 계약: 긴 이론 절은 의미 단위 단락으로 나누고 삽화를 해당 단락 뒤에 둔다.
    for s in ch["theory"]["sections"]:
        # 뷰어(renderTheoryBody)는 /\n{2,}/로 자른다. 여기서 "\n\n"로 자르면 빈 줄이
        # 3개 이상일 때 단락을 더 세어, 빌드는 통과하는데 뷰어는 삽화를 본문 끝으로 미는
        # 침묵한 오배치가 생긴다. 분할 규칙을 뷰어와 같게 맞춘다.
        paragraphs = split_paragraphs(s["content"])
        n_paras = len(paragraphs)
        for why, snippet in prose_style_problems(s["content"]):
            (errors if prose_strict else warnings).append(
                "section " + s["id"] + ": " + why + " — " + repr(snippet))
        if n_paras == 1 and len(s["content"]) > 800:
            errors.append("section " + s["id"] + ": 800자 초과 벽글 — 의미 단위 단락으로 나눌 것")
        # 글 밀도: 삽화 없이 단락만 길게 이어지면 읽다가 지친다(사용자 지적 2회 — 2026-07-21·07-22).
        # '삽화를 넣었는가'가 아니라 '어디에 넣었는가'가 문제이므로 최장 공백 구간으로 잰다.
        # anchorText가 있으면 그것이 정본이다 — afterParagraph는 여기서 다시 계산해 덮어쓴다.
        for dg in s.get("diagrams") or []:
            if not dg.get("anchorText"):
                continue
            idx, why = resolve_anchor_text(paragraphs, dg["anchorText"])
            if idx is None:
                errors.append("section " + s["id"] + " " + dg.get("id", "?") + ": " + why)
            else:
                dg["afterParagraph"] = idx
        definition_ids = set()
        for definition in s.get("definitions") or []:
            did = definition.get("id")
            anchor_text = definition.get("anchorText")
            if not did:
                errors.append("section " + s["id"] + ": definition id 누락")
            elif did in definition_ids:
                errors.append("section " + s["id"] + ": definition id 중복 — " + did)
            else:
                definition_ids.add(did)
            if not anchor_text:
                errors.append("section " + s["id"] + " definition " + str(did or "?")
                              + ": anchorText 누락")
                continue
            idx, why = resolve_anchor_text(paragraphs, anchor_text)
            if idx is None:
                errors.append("section " + s["id"] + " definition " + str(did or "?") + ": " + why)
            else:
                definition["afterParagraph"] = idx
        anchored = {dg.get("afterParagraph") for dg in s.get("diagrams") or []}
        anchored |= {r.get("afterParagraph") for r in s.get("reviewPrerequisites") or []}
        anchored |= flow_break_paragraphs(paragraphs)  # 목록·표는 삽화처럼 흐름을 끊는다
        worst = density_worst_gap(n_paras, anchored)
        if worst >= DENSITY_MAX_GAP:
            msg = ("section " + s["id"] + ": 삽화 없이 이어지는 단락이 " + str(worst)
                   + "개 (한계 " + str(DENSITY_MAX_GAP) + ") — 그 구간에 삽화를 넣거나 앵커를 옮길 것")
            (errors if density_strict else warnings).append(msg)
        for dg in s.get("diagrams") or []:
            a = dg.get("afterParagraph")
            if not (isinstance(a, int) and 1 <= a <= n_paras):
                errors.append("section " + s["id"] + " " + dg.get("id", "?")
                              + ": afterParagraph=" + repr(a) + " (단락 " + str(n_paras) + "개)")
        for definition in s.get("definitions") or []:
            a = definition.get("afterParagraph")
            if not (isinstance(a, int) and 1 <= a <= n_paras):
                errors.append("section " + s["id"] + " definition " + str(definition.get("id", "?"))
                              + ": afterParagraph=" + repr(a) + " (단락 " + str(n_paras) + "개)")
        # 복습 링크의 인라인 앵커도 같은 규칙 (앵커 없으면 절 상단 블록 — 허용)
        for ref in s.get("reviewPrerequisites") or []:
            a = ref.get("afterParagraph")
            if a is not None and not (isinstance(a, int) and 1 <= a <= n_paras):
                errors.append("section " + s["id"] + " review '" + str(ref.get("label", "?"))
                              + "': afterParagraph=" + repr(a) + " (단락 " + str(n_paras) + "개)")
            # ★ C35 — 복습 카드가 **끌어오는 삽화**에는 사유를 요구한다 (신설 2026-08-06).
            #   실사고: ch04 §1 의 복습 카드가 ch02 의 `fig-energy-balance-ledger`(질량 통로가
            #   그려진 **검사체적** 장부 그림)를 끌어왔다. 4장은 **밀폐계로 범위를 좁히는 장**이라
            #   그 장이 하려는 말의 **반례 그림이 첫 화면**에 있었다. 사용자 지적(2026-08-06):
            #   "4.1절 피스톤 얘기하고 있는데 피스톤 삽화가 아니라 이전에 개방계 에너지식 삽화
            #    가지고 온건 불합리해보이는데".
            #   ★ '그 삽화가 이 장의 범위에 맞는가'는 **장의 범위를 알아야 하는 판정**이라 기계가
            #     직접 볼 수 없다. 그래서 기계는 **사람이 판정한 흔적**을 대신 강제한다 —
            #     `diagramIds` 가 비어 있지 않으면 `diagramWhy` 한 줄이 있어야 한다.
            #     **비우는 것이 기본이고 넣는 쪽이 근거를 댄다**(복습 카드가 되짚을 것은 대개
            #     개념·식이고, 그건 `label`·`english` 가 이미 담고 있다).
            #   선례: 삽화 `### 사양`(verify_workorder 3-D)·`card-overlap-verdicts.json` —
            #   **기계가 판정할 수 없는 자리에서는 판정의 기록을 요구한다**가 이 리포의 형태다.
            if review_diagram_needs_reason(ref):
                errors.append(
                    "section " + s["id"] + " review '" + str(ref.get("label", "?"))
                    + "': diagramIds 가 있으면 diagramWhy 로 **그 삽화가 이 장의 범위에 맞는"
                    + " 이유**를 적어야 한다 (복습 카드는 삽화 없이 링크만 두는 것이 기본이다)")

    # SVG 기하 검사 (체크15 v2)
    layout_strict = is_strict_chapter(ch_path, SVG_LAYOUT_STRICT_CHAPTERS, "svg_layout")
    halo_gap_strict = is_strict_chapter(ch_path, HALO_GAP_STRICT_CHAPTERS, "halo_gap")
    clearance_strict = is_strict_chapter(ch_path, ARROW_CLEARANCE_STRICT_CHAPTERS,
                                         "arrow_clearance")
    # ★ C20 에는 **공통 승격 목록을 두지 않는다** (2026-08-02). 승격은 오직 과목이
    #   `data/<과목>/index.json` 의 `strictChapters.figure_math` 로 선언한다.
    #   왜 — 공통 목록(`*_STRICT_CHAPTERS`)을 새로 만들면 `test_strict_promotion_covers_all_chapters`
    #   가 **모든 과목의 실재 챕터**를 그 목록에 요구하고, 그 순간 아직 정리하지 않은 과목의
    #   회귀 테스트가 통째로 실패한다(열역학에는 좌표가 박힌 옛 조판이 남아 있다 — 피드백 원장
    #   2026-08-02 '잔여 6곳'). 정리 전 과목에는 **경고**로 남고, 경고는 `close_report` 가
    #   close 를 막으므로 묻히지 않는다 — C17(가운데점)에서 이미 검증된 경로다.
    figure_math_strict = is_strict_chapter(ch_path, (), "figure_math")
    for dg in list(_iter_diagrams(ch)) + slide_step_figures(ch):
        check_svg(dg.get("id", "?"), dg.get("svg", ""), errors, warnings,
                  layout_strict=layout_strict, numeric_labels=dg.get("numericLabels"),
                  halo_gap_strict=halo_gap_strict, clearance_strict=clearance_strict)
        check_figure_lint(dg.get("id", "?"), dg.get("svg", ""), errors, warnings,
                          strict=figure_lint_strict,
                          geometry_strict=arrow_connection_strict)
        # C20. 삽화 수식이 **지금 생성기가 찍는 조판**과 어긋난 자리.
        # (C18·C19 는 같은 날 thermo 가 연 선도 검사다 — 번호를 겹치지 않게 20 으로 둔다.)
        # 판정은 `checks_svg.figure_math_typesetting_hits` 하나뿐이고 `tools/audit_conventions.py`
        # 의 [I] 절도 같은 함수를 부른다 — 사본을 두면 감사 0건과 빌드 error 가 동시에 난다.
        # 승격은 과목별이다(`data/<과목>/index.json` 의 `strictChapters.figure_math`) —
        # 열역학에는 좌표가 박힌 옛 조판이 아직 남아 있어 전 과목 error 로 박으면 그 빌드가 멈춘다
        # (2026-08-02 `MIDDOT_STRICT_CHAPTERS` 실사고와 같은 부류).
        for why, preview in figure_math_typesetting_hits(dg.get("svg", "")):
            (errors if figure_math_strict else warnings).append(
                dg.get("id", "?") + ": 삽화 수식 조판이 산문과 다르다 — " + why
                + " · `python tools/svg_fraction.py` 가 찍는 조각으로 바꿀 것: " + repr(preview))
        # C21. **간격이 묶음을 만든다** — 색으로 묶어 놓고 간격이 그것을 부정한 자리.
        # 승격 방식은 C20 과 같다(공통 목록 없음 — 위 주석이 정본).
        for why, preview in figure_text_grouping_hits(dg.get("svg", "")):
            (errors if figure_math_strict else warnings).append(
                dg.get("id", "?") + ": 글줄 묶음과 간격이 어긋난다 — " + why
                + " (AGENTS: 블록 간 1.5em · 제목–부제 0.5em): " + repr(preview))
        # C47. 첨자(`<tspan>`)의 화면 실효 크기 — **부모 `<text>` 만 재던 사각지대**.
        # 열린 경위와 하한(12.9px)의 근거는 `checks_svg.FIGURE_SUBTEXT_MIN_PX` 주석이 정본이다.
        # 승격은 과목별·챕터별(`strictChapters.subtext_scale`) — 열역학만 봐도 삽화 34개가
        # 걸려서 전 과목 error 로 박으면 그 빌드가 통째로 멈춘다(C20 주석의 그 부류).
        for why in figure_subtext_scale_hits(dg.get("id", "?"), dg.get("svg", "") or ""):
            (errors if is_strict_chapter(ch_path, (), "subtext_scale")
             else warnings).append(why)
        # C34. 점선이 실선을 덮었는가(위 `dashed_over_solid_issues` 주석이 정본).
        for why in dashed_over_solid_issues(dg.get("svg", "")):
            (errors if is_strict_chapter(ch_path, (), "dash_over_solid")
             else warnings).append(dg.get("id", "?") + ": " + why)
        # C33. 치수선이 자기 화살촉을 뚫고 나갔는가(위 `dim_shaft_overshoot_issues` 주석이 정본).
        # 승격은 과목별 — 다른 과목은 아직 실측하지 않았다(이 자를 연 과목만 error 로 올린다).
        for why in dim_shaft_overshoot_issues(dg.get("svg", "")):
            (errors if is_strict_chapter(ch_path, (), "dim_shaft")
             else warnings).append(dg.get("id", "?") + ": " + why)
        # C25. 치수 라벨이 자기 치수선에 붙어 있는가(위 `dim_label_placement_issues` 주석이 정본).
        # 승격은 과목별 — 다른 과목에도 그룹 밖 라벨이 남아 있어 전 과목 error 로 박으면 그 빌드가 멈춘다.
        for why in dim_label_placement_issues(dg.get("svg", "")):
            (errors if is_strict_chapter(ch_path, (), "dim_label")
             else warnings).append(dg.get("id", "?") + ": " + why)
        # C28. **칸 안 글자 덩어리가 칸의 세로 중앙인가** (2026-08-04, R-74 —
        # `checks_svg.figure_box_center_hits` 위 주석이 정본). 승격은 과목별(`box_center`).
        for why, preview in figure_box_center_hits(dg.get("svg", "")):
            (errors if is_strict_chapter(ch_path, (), "box_center")
             else warnings).append(dg.get("id", "?") + ": " + why + ": " + repr(preview))
        # C48. **가로도 본다** (2026-08-13). C28 이 세로만 재고 있어서 가로로 치우친 글자는
        # 아무도 안 봤고, 같은 지적이 되풀이됐다(`figure_box_centering_x` 주석이 정본).
        # 승격은 같은 키(`box_center`)를 쓴다 — 한 규격의 두 축이라 따로 켜고 끌 이유가 없다.
        for why, preview in figure_box_center_x_hits(dg.get("svg", "")):
            (errors if is_strict_chapter(ch_path, (), "box_center")
             else warnings).append(dg.get("id", "?") + ": " + why + ": " + repr(preview))
        # C29. **같은 사물은 같은 조각으로 그린다** (2026-08-04, R-39 — 위 `fan_shape_issues`
        # 주석이 정본). 태그를 단 조각만 대조하므로 **전 과목에서 곧바로 error 로 둔다** —
        # `data-fan` 이 없는 삽화는 애초에 대상이 아니라 남의 빌드를 멈추지 않는다.
        errors.extend(dg.get("id", "?") + ": " + why
                      for why in fan_shape_issues(dg.get("svg", "")))

    # 정답을 펼치면 '?'가 긴 수치·단위로 바뀐다. 원본 SVG만 검사하면 이때 생기는
    # 글자-외형선 겹침과 viewBox 이탈을 놓치므로 런타임과 같은 확장 상태도 검사한다.
    # ★ 참조 무결성이 먼저다 — 슬롯 id가 SVG에 없으면 아래 치환이 조용히 아무것도 안 하고,
    # `if expanded != svg:` 때문에 답 변형 검사까지 통째로 건너뛴다(2026-07-29에 실측된 사고).
    errors.extend(answer_slot_reference_issues(ch))
    answer_geometry_strict = is_strict_chapter(ch_path, ANSWER_SLOT_GEOMETRY_STRICT_CHAPTERS,
                                               "answer_slot_geometry")
    for dg, slots in _iter_answer_diagrams(ch):
        svg = dg.get("svg", "")
        expanded = _svg_with_answer_slots(svg, slots)
        if expanded != svg:
            geometry_output = errors if answer_geometry_strict else warnings
            check_svg(dg.get("id", "?") + " [답 표시]", expanded, geometry_output, warnings,
                      layout_strict=layout_strict, numeric_labels=dg.get("numericLabels"),
                  halo_gap_strict=halo_gap_strict, clearance_strict=clearance_strict)

    # 경고는 error 아니면 명시 면제뿐이다 — '대기' 상태는 없앴다(위 주석 참조).
    #
    # ★ 다만 `errors.extend(unwaived)`는 **삽화 배치(워크오더 항목 4~10)가 끝난 뒤** 켠다.
    # 구현 도중 실측해 보니 남은 경고가 붙은 삽화 중 `fig-temp-scale-ladder`·
    # `fig-abs-gage-vacuum-bars`·`fig-card-pascal-lift`는 **사용자가 직접 불편하다고 짚은 것들**이었다.
    # 즉 이 경고들은 '확인만 하면 되는 것'이 아니라 **아직 안 고친 진짜 결함**이다.
    # 여기서 면제로 덮으면 이 장치가 없애려던 바로 그 실패(진짜 불편이 warn 뒤에 숨는 것)를
    # 그대로 재현한다. 그래서 지금은 남겨 두고 **`close_report.py`가 경고 잔량을 blocker로 세운다** —
    # 잊고 넘어가는 경로는 이미 막혔고, 남은 것은 고치는 일뿐이다.
    # 배치가 끝나 잔량이 0이 되는 순간 아래 한 줄의 주석을 풀면 되돌아올 길이 닫힌다.
    # ★ 교재 원문 복제 (규칙 3·12⑷) — 2026-08-01 도구에서 빌드로 승격.
    # 12단어 이상 연속 일치는 error, 7~11단어는 판정 기록이 있어야 통과한다.
    # 지문(.textbook-fingerprint/)이 없는 워크트리에서는 검사할 수 없으므로 **건너뛰었다고 말한다** —
    # 조용히 통과시키면 '검사했는데 0건'과 구별되지 않는다(규칙 11).
    # ★ 지문 언어 (C15) — 선언은 과목 폴더의 index.json 이 갖는다. 위 함수 주석이 정본.
    lang_errors, lang_warnings = prompt_language_issues(ch, declared_prompt_language(ch_path))
    errors.extend(lang_errors)
    warnings.extend(lang_warnings)

    orig_errors, orig_warnings, orig_skipped = check_originality(ch, ch_path)
    if orig_skipped:
        print("  [건너뜀] 독자성 검사 — 교재 지문 없음"
              " (`python tools/audit_problem_originality.py --build` 로 생성, 교재 PDF 필요)")
    errors.extend(orig_errors)
    warnings.extend(orig_warnings)

    waived, unwaived = split_waived_warnings(warnings, _waiver_map(ch))
    # ★ `--quiet` — **면제 줄은 이미 판정이 끝난 것**이라 매 빌드마다 다시 읽을 이유가 없다.
    #   신설 이유(2026-08-12, 사용자: [사용자 발화 인용 생략]): 루프 회차마다
    #   이 덤프가 출력의 대부분을 차지해, 실제 작업에 쓸 여유를 그만큼 갉아먹고 있었다.
    #   **실패·미해결 경고는 조용해지지 않는다** — 그건 아직 판정이 안 끝난 것이라서다.
    import sys as _sys
    if "--quiet" not in _sys.argv:
        for w, reason in waived:
            print("  [면제]", w, "← 사유:", reason)
    elif waived:
        print("  [면제] %d건 (사유 있음 — 보려면 --quiet 없이)" % len(waived))
    for w in unwaived:
        print("  [warn/미해결·close 차단]", w)
    # errors.extend(unwaived)   # ← 삽화 배치 완료 시 활성화 (test_warning_waivers가 이 줄을 감시)
    # ★ strict 승격이 기존 lintWaivers 를 무력화하던 결함 (2026-08-30).
    #   위 주석("상태를 둘로 줄인다 — error 아니면 사유를 적은 명시 면제")의 설계 의도대로,
    #   면제는 warning 뿐 아니라 error 로 올라온 뒤에도 그대로 유효해야 한다. `is_strict_chapter`
    #   승격은 "새 위반을 잡는다"는 뜻이지 "이미 사유를 적어 둔 면제를 지운다"는 뜻이 아니다.
    #   실사고: 열역학 ch02 `fig-flow-mech-three-parts` — C21(색 묶음)이 강체 정렬 제약 때문에
    #   구조적으로 통과할 수 없어 저자가 사유를 적어 뒀는데, figure_math strict 승격 뒤
    #   그 사유가 하나도 안 읽히고 빌드가 멈췄다.
    waived_errors, errors = split_waived_warnings(errors, _waiver_map(ch))
    if "--quiet" not in _sys.argv:
        for e, reason in waived_errors:
            print("  [면제·error]", e, "← 사유:", reason)
    elif waived_errors:
        print("  [면제·error] %d건 (사유 있음 — 보려면 --quiet 없이)" % len(waived_errors))
    if errors:
        for e in errors:
            print("  [FAIL]", e)
        raise ValueError(ch_path + ": data lint failed (" + str(len(errors)) + " errors)")
