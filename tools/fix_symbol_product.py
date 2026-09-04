# -*- coding: utf-8 -*-
r"""기호끼리의 곱은 붙이고, 이항 연산자는 띄운다 — 한 문자열에서 **함께** 고친다.

    python tools/fix_symbol_product.py                 # 무엇을 바꿀지 보여준다 (기본)
    python tools/fix_symbol_product.py --chapter=ch04.json
    python tools/fix_symbol_product.py --summary       # 건수만
    python tools/fix_symbol_product.py --apply         # 실제로 쓴다

## 왜 도구인가 — **세 과목이 각자 손으로 했고 각자 다른 데서 걸렸다** (열린 날 2026-08-13)

사용자 판정으로 곱 표기가 **「공백(병치)」에서 「붙여 쓰기」로 뒤집혔다**:
*"`PAℓ` 이건 붙이고 `A ℓ` 띄우는 게 왜 이렇게 불편하지. **나는 걍 다 붙일래.**"*
규칙은 한 줄이다 — **기호끼리의 곱은 붙이고, 연산자는 띄운다.**

그 하루에 세 과목이 각자 일회용 스크립트를 짜서 돌렸고 **각자 다른 것에 걸렸다**:

| 과목 | 무엇에 걸렸나 |
|---|---|
| 열역학 | `\(…\)` **밖 산문의 곱**을 아예 안 봤다 — `m R ΔT`·`m c_p ΔT`·`m c_v ΔT` 가 남았다 |
| 고체역학 | `GM_e m` → `GM_em` 이 되어 **`_em` 이 두 글자 첨자**로 읽혔다(26곳) · 문서에 없는 연산자(`\times`·`\cdot`)까지 띄웠다 · `(345.6,\ -295.8)` 의 **쉼표 뒤 부호**를 이항 연산자로 봤다 · `\int_A^B q(x)` 의 **큰 연산자 뒤**를 곱으로 봤다 · `\int y^2 dA` 의 **미분자**를 못 알아봤다 · `\frac{N_i L_i}{…}` 의 **중괄호 안**을 안 훑었다 |
| 기계재료 | `V_C N_A` → `V_CN_A` 로 **14건이 한꺼번에** 빌드에 걸렸다 |

**손으로 하면 갈라지고, 그 갈라짐이 이 규격이 없애려는 것**이다(`fix_cdot` 이 닫은 부류와
같은 모양). 그래서 고정 도구로 승격한다 — `fix_dim_extension`·`fix_honorific` 선례.

## ★ 판정과 처방이 **한 함수**에 있다 — `rewrite()`

찾는 자와 고치는 자가 갈리면 **자는 0건인데 화면은 그대로**이거나 그 반대가 된다
(`latex_cdot_hits` ↔ `latex_cdot_fix` 가 벡터 내적에서 갈렸던 자리, 2026-08-07).
여기서는 `rewrite()` 하나가 **후보를 만들고 · 예외를 판정하고 · 바꾼 글자까지** 돌려준다.
`--show`(기본)와 `--apply` 는 **같은 호출의 두 얼굴**이라 보여준 것과 쓰는 것이 다를 수 없다.

## ★★ 예외는 **열거가 아니라 부류**다

열거로 메우면 새 함수 이름·새 매크로가 늘 때마다 샌다(이 리포가 같은 날 세 번 닫은 부류).
그래서 판정선을 **토큰의 머리 하나**로 모았다:

  · **기호 토큰**은 ⑴ 홑글자(라틴·그리스·수학 알파벳·ℓ) ⑵ **글자꼴 매크로**(그리스 낱자 ·
    `\dot{}`·`\vec{}`·`\mathcal{}` 류) 뿐이다.
  · **그 밖의 매크로는 전부 기호가 아니다** — `\ln`·`\sin`·`\int`·`\sum`·`\frac`·`\operatorname`
    은 물론 **내일 생길 이름도** 자동으로 걸러진다. 함수 이름 목록을 두지 않는 이유가 이것이다.
    (실측 2026-08-13 열역학: 함수 이름 26건 중 15건이 인자와 공백으로 떨어져 있다 —
     `\sin 45°`·`\ln V_1`·`\ln 0.3`. `\lnV_1` 은 빌드가 잡지만 `\cosθr` 은 **빌드를 통과하고
     뜻만 틀린다.**)
  · **큰 연산자 예외를 따로 두지 않는다.** `\int_A^B q` 가 안 걸리는 것은 `\int` 이 기호가
    아니어서다. 고체역학 세션이 이걸 **따로** 막았다가 `\mu_s N` 까지 막았다 — 그들 표현대로
    *"첨자 붙은 매크로를 큰 연산자와 같이 묶어 버린 실수"*. **판정이 두 곳에 있으면 어긋난다.**
  · 첨자·지수(`_{…}`·`^{…}`)와 로만체(`\mathrm{}`·`\text{}`)는 **토큰의 일부**이거나
    **불투명 덩어리**라 애초에 후보가 만들어지지 않는다. `T_{absolute\,zero}`·`10^{-3}`·
    `\mathrm{kJ/(kg\cdot K)}` 를 이름으로 다시 알아볼 필요가 없다.
  · **중괄호 안은 재귀로 훑는다** — `\frac{N_i L_i}{…}` 의 분자가 그 자리다(위 표의 마지막 줄).

**부류로 못 가르는 셋만 `[사람]` 으로 낸다**(보여주되 안 고친다):
  ⑴ **나열인지 곱인지 가릴 근거가 없는 것** — `\(q\,r\,s\)`(결정학 점 좌표)처럼 꾸밈 없는
     홑글자만 늘어선 자리. 곱으로 바꾸면 **뜻이 달라진다.** *곱인지 나열인지는 기계가 모른다*
     (AGENTS C36 이 같은 이유로 처방을 둘 다 적는다).
  ⑵ **함수 인자 뒤** — `\cos θ\,r` 을 붙이면 인자가 `θ` 에서 `θr` 로 **조용히** 바뀐다.
     ★ 여기만은 매크로 **이름**으로 못 가른다. 조판만 보면 `\ln V_1 R` 과 `\approx c_p T` 의
     모양이 같아서(둘 다 *매크로 + 홑토큰*), 위험한 쪽만 고르려면 결국 **함수 이름 목록**이
     필요해진다 — 그 목록이 새 함수에서 새는 바로 그 열거다. 그래서 반대로 **모든 비-기호
     매크로 뒤의 첫 틈**을 `[사람]` 으로 돌린다. 틀려도 *보여주기만* 하므로 값이 안 든다.
     (TeX 이 인자로 먹는 것은 **다음 한 토큰**뿐이라 첫 틈 하나면 족하다 — `\cos θ r s` 의
      `r s` 는 이미 인자 밖이다.)
  ⑶ 모호한 자리 — 수식 안에서 숫자끼리 붙은 `-`(범위인가 뺄셈인가) ·
     `variables` 의 **키**(키를 바꾸면 JSON 키 집합이 달라져 `write_chapter` 가 거부한다).

## ★★★ 붙이기 전에 **첨자를 중괄호로 감싼다**

`V_C N_A` 를 그냥 붙이면 `V_CN_A` 가 되어 **`_CN` 이 두 글자 첨자로 읽힌다**(뷰어의 산문
렌더러가 `_([A-Za-z0-9α-ωΑ-Ω]+)` 로 욕심껏 먹는다). **화면은 같아 보이고 빌드만 안다** —
그래서 사람이 매번 빌드를 깨고 배웠다(고체역학 26곳 · 기계재료 14곳, **두 과목이 독립으로**).
이 도구는 붙일 때 왼쪽 토큰의 **중괄호 없는 꼬리 첨자·지수를 먼저 감싼다**(`V_{C}N_A`).

## 그 밖에 손대지 않는 것

  · **미분자 `d`** — `\int P\,dV`. `PdV` 는 `P·d·V` 로 읽힌다. `d` 는 곱하는 기호가 아니라 연산자다.
  · **`Δ`·`∂`·`∇`·`δ` 앞** — `P ΔV`·`g Δz`. 산문에서 붙이면 `c_vΔT` 의 `Δ` 까지 첨자로 먹힌다
    (뷰어 첨자 정규식이 그리스 낱자를 첨자 글자로 받는다).
  · **수-단위**(`100\,kPa`)·**첨자 안 낱말 구분**(`T_{absolute\,zero}`) — 곱이 아니다.
    숫자는 어느 쪽에 있어도 기호 토큰이 아니라 후보가 안 된다.
  · **낱말** — 라틴 글자가 둘 이상 이어지면 낱말이다(`kg`·`and`·`ODE`). 그래서 영문 지문의
    `A rigid tank` 도 `2 kg` 도 안 걸린다. 단 뒤에 `_`·`^` 가 붙으면 낱말이 아니라 식이다(`GM_e`).
  · **저자 전용 필드** — `changeNote`·`sourceRef`·`rationale`(뷰어를 훑어 잡은 등록부
    `AUTHOR_ONLY_FIELDS`)와 편집 메모·식별자(`UNI_SUPSUB_EXEMPT_KEYS`).
    **명단을 새로 만들지 않는다** — 두 벌을 두면 갈라진다.
  · **이항 연산자는 명시 목록뿐**: `+ - = < > \ne \le \ge`(와 유니코드 `− ≠ ≤ ≥`).
    `\times`·`\cdot`·`\approx`·`\to`·`\pm` 는 **문서에 없다.** 고체역학이 이걸 넓혔다가
    `\vec{F}\cdot\vec{n}` 과 `6.673\times10^{-11}` 을 벌려 놓았다.
  · **산문에서 양옆이 다 붙은 `-`·`<`·`>`** — `P-V 선도`·`과정 1-2`·`ch01-ch02` 는 합성어·라벨이다.
    (`checks_content` 의 줄표 판정이 같은 근거로 양옆 공백을 요구한다.)
  · **삽화(SVG)** 는 `<text>`·`<tspan>` 의 **글자 내용만** 본다. 좌표·`path` 의 `V`·`L` 을
    기호로 오인하는 사고를 구조적으로 막는다. 삽화에서는 **곱만 붙이고 연산자는 건드리지 않는다**
    — 글자 폭이 바뀌면 라벨 여백이 흔들려서, 고친 뒤 `audit_figure_balance.py` 를 다시 돌린다.

무엇이 걸리고 무엇이 안 걸리는지는 `test_checks.py::test_symbol_product_join_and_operator_spacing`
이 **위 표의 줄마다 한 케이스씩** 잠근다.
"""
import argparse
import copy
import json
import os
import re
import sys
from collections import namedtuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import audit_content                                                    # noqa: E402
from buildlib.checks_content import (MATH_NATIVE_KEYS,                  # noqa: E402
                                     UNI_SUPSUB_EXEMPT_KEYS)
from buildlib.jsontext import write_chapter                             # noqa: E402
from buildlib.review import AUTHOR_ONLY_FIELDS                          # noqa: E402

# ── 등록부 ──────────────────────────────────────────────────────────────────
# 독자 화면에 안 나가는 자리. **새 명단을 만들지 않는다** — 뷰어를 훑어 잡은 저자 전용 필드
# 등록부와 편집 메모·식별자 등록부를 합친다. 어느 쪽에도 없는 것만 아래 셋을 더한다.
EXEMPT_KEYS = (frozenset(AUTHOR_ONLY_FIELDS) | frozenset(UNI_SUPSUB_EXEMPT_KEYS)
               | frozenset({"reviewNote", "reviewClass", "lintWaivers"}))

# ★ 「이 필드는 통째로 LaTeX 인가」 — **빌드가 쓰는 그 등록부를 그대로 쓴다**
#   (열린 날 2026-08-13). 처음엔 `MATH_ONLY_KEYS`(`latex`·`equations`) 를 썼는데,
#   빌드의 평문-수식 검사는 `MATH_NATIVE_KEYS` 로 **`solutionTemplate` 까지** LaTeX 로 친다.
#   두 자가 갈리자 문풀 뼈대(`P_1 = 100\ \mathrm{kPa}` 같은 줄)가 **산문으로 판정**돼,
#   붙일 수 있는 곱이 [사람] 으로 밀렸다 — 판정이 두 곳에 있으면 반드시 어긋난다.
#   `svg` 는 여기서 빼고 아래 `svg=` 갈래가 따로 맡는다(글자만 보고 연산자는 안 건드린다).
MATH_KEYS = frozenset(k.lstrip("/") for k in MATH_NATIVE_KEYS) - {"svg"}

GREEK_MACROS = frozenset("""
    alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa
    lambda mu nu xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega
    Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega
""".split())
# 글자꼴 매크로 — 인자 하나를 받아 **한 글자처럼** 그려지는 것들.
# `mathrm`·`text`·`operatorname` 은 **넣지 않는다**: 그건 단위·낱말이라 곱의 피연산자가 아니다.
ACCENT_MACROS = frozenset("""
    dot ddot vec hat bar tilde overline widehat widetilde
    mathcal mathbf mathbb mathfrak boldsymbol mathit
""".split())
LETTERISH_MACROS = frozenset(("ell", "hbar", "imath", "jmath", "aleph", "infty"))
OPAQUE_MACROS = frozenset(("mathrm", "text", "textrm", "textit", "textbf",
                           "mathsf", "operatorname", "mbox"))
# 이항 연산자는 **문서에 적힌 것만**. 넓히면 `\cdot`·`\times` 가 벌어진다(고체역학 실측).
REL_MACROS = frozenset(("ne", "neq", "le", "leq", "ge", "geq"))
OP_CHARS = "=<>+-−≠≤≥"
SIGNY = "+-−"
# 미분·증분처럼 **연산자 노릇을 하는 머리글자**. 오른쪽에 오면 붙이지 않는다.
OPERATOR_PREFIX_CHARS = "Δ∆δ∂∇"
OPERATOR_PREFIX_MACROS = frozenset(("Delta", "delta", "partial", "nabla"))

_MACRO = re.compile(r"\\[A-Za-z]+")
_MATH_SPAN = re.compile(r"\\\((.*?)\\\)", re.S)
_SVG_TEXT = re.compile(r"(<(?:text|tspan)\b[^>]*>)([^<>]*)(</(?:text|tspan)>)")
# ★ `~` 는 넣지 않는다 — LaTeX 에서는 묶음 공백이지만 이 자료의 산문에서는 **범위 표시**다
#   (`3~5`·`ch01~ch06`). 틈으로 보면 산문에서 없는 곱을 만든다.
_SPACE_MACRO = re.compile(r"\\[,;: ]")
_MACRO_TAIL = re.compile(r"\\[A-Za-z]+$")

WHY_LIST = "나열인지 곱인지 가릴 근거가 없다 (꾸밈 없는 홑글자만 늘어서 있다)"
WHY_ARG = "함수 인자 뒤일 수 있다 (붙이면 인자 범위가 바뀐다)"
WHY_RANGE = "숫자끼리 붙은 `-` — 범위인지 뺄셈인지 기계가 모른다"
WHY_VARKEY = "`variables` 의 키다 — 키를 바꾸면 JSON 키 집합이 달라져 write_chapter 가 거부한다"
# ★ 산문·삽화에는 중괄호를 넣을 수 없다 (열린 날 2026-08-13, 열역학 빌드 8건).
#   붙이려면 왼쪽 첨자를 감싸야 하는데(`P_gas A` → `P_{gas}A`), 감싼 글자를 **수식 밖**에
#   두면 화면에 `_{` 가 그대로 찍힌다 — 빌드 검사가 그것을 error 로 막는다.
#   그렇다고 안 감싸고 붙이면 첨자가 오른쪽 글자까지 먹는다(`P_gasA`). **둘 다 안 되므로
#   산문에서는 붙이지 않는다** — 붙이려면 그 자리를 통째로 `\(…\)` 로 옮겨야 하고,
#   그건 조판을 바꾸는 일이라 기계가 할 판단이 아니다.
WHY_PROSE_BRACE = "산문·삽화라 첨자를 중괄호로 감쌀 수 없다 (붙이려면 그 자리를 인라인 수식으로 옮겨야 한다)"
# ★★ 「프라임 앞」의 모양 — 2026-08-13 문서가 **공학수학 세션 몫**으로 남긴 판정이다.
#   브라우저 실측(뷰어 renderMath 를 그대로 호출):
#       u'\,x → `u′ x`    ·  u'x → **`u'x`**(ASCII 아포스트로피로 남는다)
#       y_2'\,y_3'' → `y₂′ y₃′′`  ·  y_2'y_3'' → **`y₂'y₃′′`**(한 식 안에서 두 모양)
#   프라임 변환의 전방탐색이 `[(),_<|}]` 와 `\s|$|[=+\-*/^]` 뿐이라 **뒤에 글자가 오면 안 받는다.**
#   그래서 붙이는 순간 규격이 없애려는 「한 화면 두 표기」가 생긴다 → **붙이지 않는다.**
#   ★ 프라임이 **오른쪽**에 오는 것(`n' A`)은 이 규칙과 무관하다 — 왼쪽 꼬리만 본다.
WHY_PRIME = ("왼쪽이 프라임으로 끝난다 — 붙이면 렌더러가 프라임을 못 받아 ASCII 아포스트로피로 남는다"
             " (실측: `u'x` → `u'x` · `u'\\,x` → `u′ x`)")
# 저자가 **넓은 간격**으로 갈라 놓은 자리는 곱이 아니라 나열이다 — 행렬의 열이 그렇다
# (`[\,\mathbf{x}_1\ \ \mathbf{x}_2\,]`). `\quad` 와 같은 부류인데 모양만 다르다.
WHY_WIDE_GAP = "저자가 넓은 간격으로 갈라 놓았다 — 행렬의 열 나열이지 곱이 아니다"

Hit = namedtuple("Hit", "kind auto before after why context")


def _sym_char(ch):
    """글자 하나가 **기호로 그려지는 글자**인가. 한글·한자는 아니다."""
    if not ch:
        return False
    o = ord(ch)
    return (("A" <= ch <= "Z") or ("a" <= ch <= "z")
            or 0x0370 <= o <= 0x03FF                 # 그리스
            or 0x1E00 <= o <= 0x1EFF                 # 점 찍힌 라틴 (ṁ·Ẇ)
            or 0x1D400 <= o <= 0x1D7CB               # 수학 알파벳 (𝒱)
            or ch == "ℓ")


class Item(object):
    """한 조각. kind ∈ gap·tok·macro·group·op·num·other."""

    __slots__ = ("kind", "text", "name", "inner", "head", "decorated",
                 "macro_tail", "tail_unbraced")

    def __init__(self, kind, text, name=None, inner=None, head="",
                 decorated=False, macro_tail=False, tail_unbraced=None):
        self.kind = kind
        self.text = text
        self.name = name                 # 매크로 이름 (macro·tok)
        self.inner = inner               # (안쪽 items, 안쪽 시작, 안쪽 끝) — group
        self.head = head                 # 첫 글자 (tok)
        self.decorated = decorated       # 첨자·매크로·비 ASCII — "식이다" 의 증거
        self.macro_tail = macro_tail     # 매크로 **이름**으로 끝난다 (`\rho`)
        self.tail_unbraced = tail_unbraced   # 중괄호 없는 꼬리 첨자의 **토큰 안** 위치


def _read_group(s, i):
    """`s[i] == '{'` 이면 짝 맞는 `}` **다음** 위치. 안 닫혔으면 None."""
    if i >= len(s) or s[i] != "{":
        return None
    depth = 0
    while i < len(s):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


# 산문 렌더러(`fmtText`)가 중괄호 없는 첨자로 먹는 범위 — 그 정규식을 그대로 옮긴 것이다.
_PROSE_SUB = re.compile(r"[A-Za-z0-9Α-Ωα-ω]+(?:,[a-z]+)*")


def _read_suffixes(s, i, base, greedy=False):
    """`_{…}`·`^2`·`'` 를 삼킨다 → (끝, 꾸밈 있나, **토큰 안** 꼬리 첨자 위치).

    ★ **기호 토큰·매크로·숫자가 같은 함수를 쓴다.** 첨자를 삼키지 않으면 `\\int_A^B q` 의
      `B` 가 홀로 남아 곱의 왼쪽이 되고(고체역학 오검출), `6.673\\times10^{-11}` 의 `-11` 이
      이항 연산자가 된다. 판정을 자리마다 새로 쓰면 이렇게 어긋난다.

    ★★ `greedy` 는 **뷰어의 두 렌더러가 다르기 때문**이다(추측이 아니라 정규식 실측):
      · 수식 `renderMath` — `_([A-Za-z0-9])` 로 **한 글자만** 내린다.
      · 산문 `fmtText`   — `_([A-Za-z0-9α-ωΑ-Ω]+(?:,[a-z]+)*)` 로 **욕심껏** 먹는다.
      그래서 산문의 `ρ_Hg g h_3` 을 한 글자 규칙으로 읽으면 `ρ_H`·`g`·`g` 가 되어
      **없는 곱(`g g`)을 만든다**(실측 ch01 problems[11] 4곳). 같은 이유로 산문에서
      `V_C N_A` 를 그냥 붙이면 `_CN` 이 통째로 첨자가 된다 — 감싸야 하는 근거가 이것이다.
    """
    decorated, tail = False, None
    while i < len(s):
        if s[i] in "_^":
            end = _read_group(s, i + 1)
            if end is not None:
                i, decorated, tail = end, True, None
                continue
            m = _MACRO.match(s, i + 1)
            if m:
                i, decorated, tail = m.end(), True, None
                continue
            run = _PROSE_SUB.match(s, i + 1) if greedy else None
            if run:
                tail = i - base
                i, decorated = run.end(), True
                continue
            if i + 1 < len(s) and s[i + 1].isascii() and s[i + 1].isalnum():
                tail = i - base                     # 토큰 시작을 기준으로 잡는다
                i, decorated = i + 2, True
                continue
            break
        if s[i] == "'":
            i, decorated, tail = i + 1, True, None
            continue
        break
    return i, decorated, tail


def _is_word(s, i):
    """`s[i]` 에서 시작하는 **라틴 글자 뭉치가 낱말인가** (기호가 아닌가).

    ★ **산문에서만 묻는다.** 수식 안에서는 이어 쓴 라틴 글자가 낱말이 아니라 **이미 붙인 곱**
      (`gh`·`mRT`)이고, 낱말·단위는 `\\mathrm{}`·`\\text{}` 안에 있어 이미 불투명하다.
      수식에서도 낱말로 보면 `\\rho\\,gh` 를 못 고친다 — 오른쪽이 통째로 낱말이 되기 때문이다
      (열역학이 이 17곳을 손으로 고쳤다). 미분자 `dV` 는 낱말이라서가 아니라 **`d` 라서** 막힌다.

    둘 이상 이어진 라틴 글자는 낱말이다 — `kg`·`and`·`ODE`. 그래서 영문 지문의
    `A rigid tank` 도 `2 kg` 도 후보가 되지 않는다.
    ★ 단 뒤에 `_`·`^` 가 붙으면 낱말이 아니라 식이다(`GM_e`) — 그때는 낱자로 쪼개 읽는다.
      프라임(`'`)은 **홑글자일 때만** 식으로 본다(`y'`). 안 그러면 `student's` 가 식이 된다.
    """
    j = i
    while j < len(s) and (("A" <= s[j] <= "Z") or ("a" <= s[j] <= "z")):
        j += 1
    if j - i < 2:
        return False
    return not (j < len(s) and s[j] in "_^")


def _lex(s, greedy=False):
    """문자열 하나를 조각 목록으로. 중괄호 안은 **재귀로** 다시 훑는다.

    `greedy` = 산문(수식 밖). 첨자 범위와 **줄표 판정**이 거기서 갈린다.
    """
    items, i, n = [], 0, len(s)
    while i < n:
        ch = s[i]
        # ── 공백류 (붙일 수 있는 틈) ─────────────────────────────────────
        if ch.isspace() or _SPACE_MACRO.match(s, i):
            j = i
            while j < n:
                mm = _SPACE_MACRO.match(s, j)
                if s[j].isspace():
                    j += 1
                elif mm:
                    j = mm.end()
                else:
                    break
            items.append(Item("gap", s[i:j]))
            i = j
            continue
        # ── 매크로 ────────────────────────────────────────────────────
        m = _MACRO.match(s, i)
        if m:
            name = m.group(0)[1:]
            j = m.end()
            if name in REL_MACROS:
                items.append(Item("op", m.group(0), name=name))
                i = j
                continue
            if name in OPAQUE_MACROS:
                k = j
                while k < n and s[k].isspace():
                    k += 1
                end = _read_group(s, k)
                items.append(Item("other", s[i:end if end else j]))
                i = end if end else j
                continue
            if name in ACCENT_MACROS:
                k = j
                while k < n and s[k].isspace():
                    k += 1
                end = _read_group(s, k)
                if end is not None:
                    j2, _dec, tail = _read_suffixes(s, end, i, greedy)
                    items.append(Item("tok", s[i:j2], name=name, head="\\",
                                      decorated=True, tail_unbraced=tail))
                    i = j2
                    continue
            if name in GREEK_MACROS or name in LETTERISH_MACROS or name in ACCENT_MACROS:
                j2, _dec, tail = _read_suffixes(s, j, i, greedy)
                items.append(Item("tok", s[i:j2], name=name, head="\\",
                                  decorated=True, macro_tail=(j2 == j),
                                  tail_unbraced=tail))
                i = j2
                continue
            # ★ 그 밖의 매크로는 **전부** 기호가 아니다 — 함수 이름 목록을 두지 않는 이유다.
            j2, _dec, _tail = _read_suffixes(s, j, i, greedy)
            items.append(Item("macro", s[i:j2], name=name))
            i = j2
            continue
        # ── 중괄호 덩어리 ──────────────────────────────────────────────
        if ch == "{":
            end = _read_group(s, i)
            if end is not None:
                j2, _dec, _tail = _read_suffixes(s, end, i, greedy)
                items.append(Item("group", s[i:j2],
                                  inner=(_lex(s[i + 1:end - 1], greedy), 1, end - 1 - i)))
                i = j2
                continue
        # ── 연산자 ────────────────────────────────────────────────────
        if ch in OP_CHARS:
            # ★★ **산문에서 양옆이 다 붙은 줄표·부등호는 연산자가 아니다** — `A U-tube`·
            #   `P-V 선도`·`과정 1-2`. 판정을 여기 **한 곳**에 둔다: 여기서 안 걸러 두면
            #   *띄우지는 않으면서 곱의 증거로는 세는* 상태가 되어, `A U-tube manometer` 의
            #   `A U` 가 붙었다(실측 ch01 practice[5]·problems[10] 2곳).
            glued = (greedy and ch in SIGNY + "<>"
                     and i and not s[i - 1].isspace()
                     and i + 1 < n and not s[i + 1].isspace())
            items.append(Item("other" if glued else "op", ch))
            i += 1
            continue
        # ── 숫자 (지수까지 삼킨다) ──────────────────────────────────────
        if ch.isdigit():
            j = i
            while j < n and (s[j].isdigit()
                             or (s[j] == "." and j + 1 < n and s[j + 1].isdigit())):
                j += 1
            j, _dec, _tail = _read_suffixes(s, j, i, greedy)
            items.append(Item("num", s[i:j]))
            i = j
            continue
        # ── 기호 글자 ─────────────────────────────────────────────────
        if _sym_char(ch):
            if greedy and ("A" <= ch <= "Z" or "a" <= ch <= "z") and _is_word(s, i):
                j = i
                while j < n and (("A" <= s[j] <= "Z") or ("a" <= s[j] <= "z")):
                    j += 1
                items.append(Item("other", s[i:j]))
                i = j
                continue
            j2, dec, tail = _read_suffixes(s, i + 1, i, greedy)
            items.append(Item("tok", s[i:j2], head=ch, tail_unbraced=tail,
                              decorated=dec or not ch.isascii()))
            i = j2
            continue
        items.append(Item("other", ch))
        i += 1
    return items


def _brace_tail(tok):
    """중괄호 없는 꼬리 첨자를 감싼 글자 — `V_C` → `V_{C}`. 없으면 원문 그대로.

    붙이기 전에 반드시 거친다. 안 거치면 `V_CN_A` 의 `_CN` 이 **두 글자 첨자**로 읽힌다
    (고체역학 `GM_e m` 26곳 · 기계재료 `V_C N_A` 14곳 — 두 과목이 독립으로 걸린 자리).
    """
    if tok.tail_unbraced is None:
        return tok.text
    k = tok.tail_unbraced
    return tok.text[:k + 1] + "{" + tok.text[k + 1:] + "}"


def _joinable_right(tok):
    """오른쪽 토큰이 곱의 피연산자인가 — 미분자·증분 기호는 아니다.

    `d` 는 곱하는 기호가 아니라 연산자라 `P\\,dV` 의 공백은 남는다(`PdV` 는 `P·d·V` 로 읽힌다).
    `dV` 처럼 **붙여 쓴** 미분자는 낱말로 읽혀 애초에 토큰이 아니다 — 여기 오는 것은
    `\\int y^2 d A` 처럼 띄어 쓴 자리뿐이다.
    """
    if tok.text == "d":
        return False
    if tok.head and tok.head in OPERATOR_PREFIX_CHARS:
        return False
    return tok.name not in OPERATOR_PREFIX_MACROS


def _chains(items):
    """토큰이 틈으로 이어진 마디들 → [(시작, 끝, 증거 있나, 함수 인자 뒤인가)]."""
    out, i, n = [], 0, len(items)
    while i < n:
        if items[i].kind not in ("tok", "gap"):
            i += 1
            continue
        j = i
        while j < n and items[j].kind in ("tok", "gap"):
            j += 1
        toks = [it for it in items[i:j] if it.kind == "tok"]
        if toks:
            before = items[i - 1] if i else None
            after = items[j] if j < n else None
            # ★ **식이라는 증거** — 꾸민 토큰(첨자·매크로·그리스)이 있거나 연산자가 붙어 있다.
            #   증거가 없으면 `\(q\,r\,s\)`(점 좌표)와 구별할 방법이 없다.
            evidence = (any(t.decorated for t in toks)
                        or (before is not None and before.kind == "op")
                        or (after is not None and after.kind == "op"))
            after_macro = before is not None and before.kind == "macro"
            out.append((i, j, evidence, after_macro))
        i = j
    return out


def _op_is_binary(items, k):
    """`+ -` 가 이항 연산자인가, 아니면 부호인가."""
    j = k - 1
    while j >= 0 and items[j].kind == "gap":
        j -= 1
    if j < 0:
        return False
    prev = items[j]
    if prev.kind in ("tok", "num", "group"):
        return True
    # `(345.6,\ -295.8)` — 쉼표 뒤는 부호다. 여는 괄호·연산자 뒤도 마찬가지.
    return prev.kind == "other" and prev.text.endswith((")", "]"))


def _rewrite_items(items, math, svg, hits, context):
    """조각 목록을 고쳐 글자로 되돌린다 — **판정과 처방이 여기 하나에 있다.**"""
    plan = {}                                  # id(item) → 새 글자
    wrap = set()                               # 첨자를 감쌀 토큰

    # ⑴ 중괄호 안을 먼저 (재귀) — `\frac{N_i L_i}{…}` 의 분자가 그 자리다.
    for it in items:
        if it.kind == "group" and it.inner:
            inner_items, a, b = it.inner
            fixed = _rewrite_items(inner_items, math, svg, hits, context)
            if fixed != it.text[a:b]:
                plan[id(it)] = it.text[:a] + fixed + it.text[b:]

    # ⑵ 곱 — 토큰 사이의 틈
    for start, end, evidence, after_macro in _chains(items):
        first_gap = True
        for k in range(start, end):
            it = items[k]
            if it.kind != "gap" or k == start or k + 1 >= end:
                continue
            left, right = items[k - 1], items[k + 1]
            if left.kind != "tok" or right.kind != "tok":
                continue
            if "\n" in it.text or "\\quad" in it.text or "\\qquad" in it.text:
                continue                       # 줄바꿈·의도한 넓은 간격은 틈이 아니다
            if not _joinable_right(right):
                continue                       # 미분자·증분 — 조용히 둔다(예외는 신고하지 않는다)
            if it.text.count("\\ ") >= 2:
                hits.append(Hit("곱", False, left.text + it.text + right.text, "",
                                WHY_WIDE_GAP, context))
                continue                       # `\ \ ` — 저자가 갈라 놓은 나열이다
            if left.text.endswith("'"):
                hits.append(Hit("곱", False, left.text + it.text + right.text, "",
                                WHY_PRIME, context))
                continue                       # 프라임 앞 — 위 WHY_PRIME 주석이 정본
            at_arg = after_macro and first_gap
            first_gap = False
            # 처방 — **매크로 이름 뒤에는 보통 공백 한 칸을 남긴다.** 지우면 `\rhoA` 라는
            # 다른 명령이 되고, `\,` 로 두면 화면에서 얇은 공백만큼 벌어진다.
            # ★ 매크로 이름 뒤 공백은 **이름을 끊기 위한 것**이라, 오른쪽이 백슬래시로 시작하면
            #   필요 없다 — `\rho\mathcal{V}` 는 이미 갈린다. 그런데도 남기면 **화면에 여백이
            #   보인다**(2026-08-13 사용자 지적: *"여긴 왜 로우랑 V 사이 여백 있지?"*).
            #   renderMath 가 먹는 것은 *글자꼴 기호 뒤 + 피연산자가 따라올 때*뿐이고
            #   매크로가 따라오는 자리는 그 규칙 밖이다.
            glue = (" " if _MACRO_TAIL.search(left.text)
                    and not right.text.startswith("\\") else "")
            if it.text == glue:
                continue                       # 이미 맞다 — 판정할 것이 없다
            pair = left.text + it.text + right.text
            if at_arg or not evidence:
                hits.append(Hit("곱", False, pair, "",
                                WHY_ARG if at_arg else WHY_LIST, context))
                continue
            head = right.text[:1]
            needs_brace = (left.tail_unbraced is not None
                           and (head.isalnum() or _sym_char(head)))
            if needs_brace and not math:
                hits.append(Hit("곱", False, pair, "", WHY_PROSE_BRACE, context))
                continue
            if needs_brace:
                wrap.add(id(left))
            new_left = _brace_tail(left) if id(left) in wrap else left.text
            plan[id(it)] = glue
            hits.append(Hit("곱", True, pair, new_left + glue + right.text, "", context))

    # ⑶ 연산자 — 삽화에서는 건드리지 않는다(글자 폭이 바뀌면 라벨 여백이 흔들린다)
    if not svg:
        for k, it in enumerate(items):
            if it.kind != "op":
                continue
            before = items[k - 1] if k else None
            after = items[k + 1] if k + 1 < len(items) else None
            if before is None or after is None:
                continue                       # 줄 처음·끝은 이어지는 식이다
            lgap = before if before.kind == "gap" else None
            rgap = after if after.kind == "gap" else None
            if (lgap and "\n" in lgap.text) or (rgap and "\n" in rgap.text):
                continue
            lhs = items[k - 2] if lgap and k >= 2 else before
            rhs = items[k + 2] if rgap and k + 2 < len(items) else after
            if lhs is None or rhs is None or lhs.kind == "gap" or rhs.kind == "gap":
                continue
            if it.text in SIGNY and not _op_is_binary(items, k):
                continue                       # 부호다 — `-273.15`·`(345.6,\ -295.8)`
            # (산문에서 양옆이 붙은 줄표·부등호는 **어휘 단계에서** 이미 연산자가 아니다.)
            if not lgap and not rgap:
                if it.text in SIGNY and lhs.kind == "num" and rhs.kind == "num":
                    hits.append(Hit("연산자", False, it.text, "", WHY_RANGE, context))
                    continue
            if (lgap.text if lgap else "") == " " and (rgap.text if rgap else "") == " ":
                continue                       # 이미 맞다
            before_txt = (lgap.text if lgap else "") + it.text + (rgap.text if rgap else "")
            if lgap:
                plan[id(lgap)] = " "
            else:
                plan[id(it)] = " " + it.text
            if not rgap:
                plan[id(it)] = plan.get(id(it), it.text) + " "
            else:
                plan[id(rgap)] = " "
            hits.append(Hit("연산자", True, before_txt, " " + it.text + " ", "", context))

    out = []
    for it in items:
        if id(it) in wrap:
            out.append(_brace_tail(it))
        else:
            out.append(plan.get(id(it), it.text))
    return "".join(out)


def _one(text, math, svg):
    if not text:
        return text, []
    hits = []
    context = re.sub(r"\s+", " ", text).strip()
    return _rewrite_items(_lex(text, greedy=not math), math, svg, hits, context[:80]), hits


def rewrite(text, math=False, svg=False):
    r"""**판정과 처방이 함께 있는 하나의 함수** → (고친 글, [Hit]).

    `math` 는 값 전체가 LaTeX 인 필드(`latex`·`equations`), `svg` 는 삽화.
    산문은 `\(…\)` 안팎을 갈라 처리한다 — 판정선이 다르기 때문이다(붙여 쓴 줄표).
    `auto=False` 인 Hit 는 **보여주기만 하고 고치지 않는다.**
    """
    if not isinstance(text, str) or not text:
        return text, []
    if svg:
        hits = []

        def body(m):
            fixed, hs = _one(m.group(2), False, True)
            hits.extend(hs)
            return m.group(1) + fixed + m.group(3)
        return _SVG_TEXT.sub(body, text), hits
    if math:
        return _one(text, True, False)
    out, hits, pos = [], [], 0
    for m in _MATH_SPAN.finditer(text):
        seg, hs = _one(text[pos:m.start()], False, False)
        out.append(seg)
        hits.extend(hs)
        inner, hs = _one(m.group(1), True, False)
        out.append("\\(" + inner + "\\)")
        hits.extend(hs)
        pos = m.end()
    seg, hs = _one(text[pos:], False, False)
    out.append(seg)
    hits.extend(hs)
    return "".join(out), hits


def walk(node, key, trail, found, apply_):
    """챕터를 통째로 내려간다 — 스키마를 열거하지 않는다(새 필드가 조용히 빠지지 않게)."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in EXEMPT_KEYS:
                out[k] = v
                continue
            if key == "variables" and isinstance(k, str):
                # 키도 화면에 그려지는 수식이다(`iter_math_blobs` 가 같은 이유로 본다).
                _fixed, hs = rewrite(k, math=True)
                for h in hs:
                    found.append((trail + "{" + k + "}",
                                  h._replace(auto=False, why=WHY_VARKEY)))
            out[k] = walk(v, k, trail + "/" + str(k), found, apply_)
        return out
    if isinstance(node, list):
        return [walk(v, key, trail + "[" + str(i) + "]", found, apply_)
                for i, v in enumerate(node)]
    if isinstance(node, str):
        # 문풀 빈칸의 정답은 `solutionTemplate` 의 구멍에 그대로 꽂힌다 → 거기도 LaTeX 자리다
        # (빌드 `plain_math_issues` 가 같은 이유로 같은 판정을 한다).
        math = key in MATH_KEYS or (key == "answer" and "blanks[" in trail)
        fixed, hs = rewrite(node, math=math, svg=(key == "svg"))
        for h in hs:
            found.append((trail, h))
        return fixed if apply_ else node
    return node


def main():
    ap = argparse.ArgumentParser(
        description="기호끼리의 곱은 붙이고 이항 연산자는 띄운다 (기본은 미리보기)")
    ap.add_argument("--chapter", help="chNN.json 하나만")
    ap.add_argument("--show", action="store_true", help="기본값 — 걸린 자리를 문맥과 함께")
    ap.add_argument("--summary", action="store_true", help="건수만")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    ap.add_argument("--limit", type=int, default=40, help="챕터당 출력 줄 수 (기본 40)")
    args = ap.parse_args()

    print("규격: 기호끼리의 곱은 붙이고, 이항 연산자(+ - = < > \\ne \\le \\ge)는 띄운다")
    print("[사람] 은 보여주기만 한다 — 나열/곱을 기계가 가를 수 없거나 함수 인자 뒤인 자리다")
    names = ([args.chapter] if args.chapter
             else [n + ".json" for n in audit_content.CHAPTERS])
    tot_join = tot_op = tot_human = 0
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        before = copy.deepcopy(data)
        found = []
        after = walk(data, None, "root", found, args.apply)
        join = [(t, h) for t, h in found if h.auto and h.kind == "곱"]
        ops = [(t, h) for t, h in found if h.auto and h.kind == "연산자"]
        human = [(t, h) for t, h in found if not h.auto]
        tot_join += len(join)
        tot_op += len(ops)
        tot_human += len(human)
        if not found:
            continue
        print("=== %s — 곱 %d곳 · 연산자 %d곳 · [사람] %d곳"
              % (name, len(join), len(ops), len(human)))
        if not args.summary:
            shown = 0
            for trail, h in join + ops + human:
                if shown >= args.limit:
                    print("    … 외 %d곳 (--limit 로 늘린다)" % (len(found) - shown))
                    break
                shown += 1
                if h.auto:
                    print("  [%s] %s → %s   %s"
                          % (h.kind, h.before.replace("\n", " "), h.after, trail))
                else:
                    print("  [사람] %s   %s" % (h.before.replace("\n", " "), h.why))
                    print("         ⟨%s⟩  %s" % (h.context, trail))
        if args.apply and (join or ops):
            state, why = write_chapter(path, before, after)
            print("  [%s] %s" % (state, why or name))
    print("\n합계 — 곱 %d곳 · 연산자 %d곳 · [사람] %d곳%s"
          % (tot_join, tot_op, tot_human,
             "" if args.apply else "  (--apply 를 붙여야 쓴다)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
