# -*- coding: utf-8 -*-
r"""과목이 **규칙이 바뀌기 전에 쓴 콘텐츠**를 아직 안 고쳤는지 — 전 과목을 훑어 후보만 낸다.

    python tools/audit_convention_drift.py
    python tools/audit_convention_drift.py --only=<과목폴더>,<과목폴더>   # data/ 아래 이름 그대로
    python tools/audit_convention_drift.py --check=slide-mode

열린 날 2026-08-29. 원인 — 사용자 질문 *[발화 생략]*.
답은 «없었다»였다: `common_guard.py`는 공통 **파일**이 최신인지만 보고, 파일을 받은 뒤
**이미 써 둔 콘텐츠가 새 규칙에 맞는지**는 아무도 안 본다. 실사고 — 슬라이드모드 규격이
2026-08-18에 생겼는데 그 문서를 가리키는 줄은 2026-08-29 에야 AGENTS.md 에 들어갔고,
그 사이(8/18~8/29)에 만들어진 과목은 전부 구멍이 났다 — 한 과목이 그 첫 사례로 걸렸다.

★ **이 도구는 판정하지 않는다.** «figure 가 없다»가 곧 결함은 아니다 — 순수 대수 유도는
그림이 필요 없을 수 있다. 후보만 내고 사람이 챕터별로 본다(`audit_figure_balance.py`와 같은 태도).

★ **과목 이름을 박지 않는다.** 목록은 `audit_content.subject_dirs()` 가 `data/` 를 읽어 정한다
(AGENTS 「공통 도구에 과목별 사실을 박지 않는다」). 새 과목이 생기거나 없어져도 이 파일을 안 고친다.

★★ **2026-09-07 평탄화로 이 자가 통째로 죽어 있었다** — 옛 판은 `git worktree list` 에서 `main`
이 아닌 갈래를 세었고, 워크트리가 하나가 되자 그 목록이 비어 **한 과목도 안 보고 「0건」**을
찍었다. 그래서 합계에 **훑은 과목 수**를 함께 찍고, 0개면 exit 1 이다.
(옛 판이 `git show` 로만 읽던 이유는 «남의 워크트리의 반쯤 고친 상태를 정본으로 오인하지
않는다» 였는데, 워크트리가 하나뿐인 지금은 작업 트리가 곧 정본이라 그 위험 자체가 없다.)

체크 목록(늘어날 수 있다 — 함수 하나 = 검사 하나):
  1. slide-mode  — `kind:"derivation"` 카드에 `figure` 키가 있는가(정본 2026-08-18 슬라이드모드 사양)
  2. fig-width   — 삽화 viewBox 폭이 640인가(정본 위 문서의 「viewBox 폭은 640으로」절, 2026-08-29 실측)
  3. hand-arc    — 각도 호가 `svg_arc_arrow.py`를 거쳤는가(습관 휴리스틱, 정확성은 빌드가 이미 잠근다)
  3b. curve-facets — 점으로 흉내 낸 곡선이 **눈에 띄게 각져 있는가**(재는 자는
                   `tools/audit_curve_smoothness.py`, 2026-09-10 재지적으로 열렸다)
  4. rate-dot    — 산문에 완성형 '닷 붙은 글자'(ṁ·Ẇ 등)가 날것으로 남아 있는가
                   (`tools/fix_rate_dot.py` 의 `convert()` 를 그대로 불러 쓴다 — 판정 로직을
                   두 벌 두면 갈린다. 2026-08-07 에 열렸는데 **빌드 lint 가 없어** 새로 쓰는
                   콘텐츠가 오늘도 재발할 수 있다 — 이 체크가 유일한 방지선이다)
  5. deriv-jump  — 유도 단계가 대입을 원래 식 재인용 없이 건너뛰는가(공용 폴더 원장 2026-08-19,
                   thermo ch07에서 처음 접수 — "자꾸 원래 식을 보여준 후 거기서 대입한 식으로
                   보여주면 좋을걸 생략하네 좀 불친절한데"). 방아쇠 낱말(`대입하`·`첫 줄에 넣`·
                   `두 식을 이으`)만 훑고, **판정선(원래 식이 바로 위에 있는가)은 사람이 본다**
                   — 자동 강제하면 직전 단계 재인용까지 요구하는 오탐이 된다. 2026-09-05 appthermo
                   ch07·ch11 재발로 이 체크가 신설됐다(그전엔 grep 을 그때그때 손으로 돌렸다).

★ **넷째 체크는 다른 셋과 성격이 다르다** — slide-mode·fig-width·hand-arc 는 "습관·스타일"
후보만 내지만, rate-dot 은 `fix_rate_dot.py` 가 이미 "고친다"고 정의해 둔 정확한 변환이 있다
(순수 함수 `convert()`).

☐ **그래도 「판정 불필요」는 아니다 — 2026-09-07 실측으로 정정.** 그 자를 3건에 돌렸더니
  **2건이 반쯤 고쳐졌다**: ⑴ `ṁin = ṁout` → `\(\dot{m}\)in = \(\dot{m}\)out` (아래첨자가
  수식 **밖**에 남는다) ⑵ `mẍ+cẋ+kx=0` → `mẍ+c\(\dot{x}\)+kx=0` (`ẍ` 는 `convert()` 의
  대상이 아니라 **한 식이 반은 날것**으로 남는다). 그 자는 **낱글자 하나**만 안다.
  → `--apply` 뒤에는 반드시 `git diff` 로 **그 줄을 눈으로 본다.** 낱말 안에 아래첨자가
  붙어 있거나 그 심볼이 **식의 일부**면, 식 전체를 인라인 수식으로 감싸는 것이 맞다.

새 체크를 추가할 때: 함수 이름을 `check_<이름>`으로, `CHECKS` 딕셔너리에 등록, 리턴은
`[(subject, chapter, item_id, 한줄사유), ...]` 리스트 하나로 통일한다.
"""
import json
import math
import os
import re
import subprocess
import sys

import fix_rate_dot
import audit_curve_smoothness as curve_smoothness
import audit_figure_balance as figure_balance

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def git(*args):
    """★ `core.quotepath=false` 가 필수다 — 과목 폴더가 전부 한글이다 (audit_subject_progress 와 동일 사고)."""
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") if r.returncode == 0 else ""


def subjects():
    """과목 폴더 경로 전부. 이름을 박지 않는다 — `data/` 를 읽는 자가 하나뿐이어야 한다.

    ★★ **2026-09-07 평탄화로 이 자가 통째로 죽어 있었다.** 옛 판은 `git worktree list` 에서
      `main` 이 아닌 갈래를 세었는데, 워크트리가 하나가 되면서 **그 목록이 비어 0건을 찍었다.**
      «0건» 과 «한 과목도 안 봤다» 가 화면에서 같아지는, 이 리포가 반복해 닫은 부류다.
      → 갈래가 아니라 **작업 트리의 `data/`** 를 본다.
    """
    import audit_content                                                    # noqa: E402
    return audit_content.subject_dirs()


def chapter_files(folder):
    return sorted(n for n in os.listdir(folder) if re.fullmatch(r"ch\d{2}\.json", n))


def blob(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


VIEWBOX_RE = re.compile(r"viewBox=['\"]\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+[-\d.]+")


def check_slide_mode(chapter, chapter_name):
    hits = []
    for f in (chapter.get("derivation") or {}).get("formulas") or []:
        if f.get("kind") != "derivation":
            continue
        if "figure" not in f:
            hits.append((chapter_name, f.get("id", "?"), "슬라이드 figure 없음(구식 카드 후보)"))
    return hits


def check_fig_width(chapter, chapter_name):
    hits = []

    def scan(collection, owner_prefix):
        for item in collection or []:
            for d in item.get("diagrams") or []:
                svg = d.get("svg", "")
                m = VIEWBOX_RE.search(svg)
                if m and abs(float(m.group(1)) - 640) > 0.5:
                    hits.append((chapter_name, d.get("id", "?"),
                                 owner_prefix + " viewBox 폭 " + m.group(1) + " (640 아님)"))
            fig = item.get("figure")
            if isinstance(fig, dict):
                svg = fig.get("svg", "")
                m = VIEWBOX_RE.search(svg)
                if m and abs(float(m.group(1)) - 640) > 0.5:
                    hits.append((chapter_name, fig.get("id", "?"),
                                 owner_prefix + " 슬라이드 viewBox 폭 " + m.group(1) + " (640 아님)"))

    scan((chapter.get("theory") or {}).get("sections"), "theory")
    scan((chapter.get("derivation") or {}).get("formulas"), "derivation")
    scan(chapter.get("practice"), "practice")
    scan(chapter.get("problems"), "problems")
    return hits


# ── 3D(등축투영)를 써야 할 자리인데 평면으로 그렸나 ────────────────────────────
#
# ★ 규격은 이미 있다 — `docs/삽화-규격.md` 「3D(등축투영)를 쓰는 조건」:
#   *[발화 생략]*
#   그런데 **그 규격을 이미 쓴 삽화에 대고 재는 자가 없었다**(2026-09-07 사용자 지적:
#   *[발화 생략]*).
#   규칙 7 이 말하는 «⑵는 있는데 ⑶이 없다» 그 자리다 — 새 삽화만 규격을 지키고 옛 것은 방치됐다.
#
# ☐ **이 자가 못 하는 것 둘.** ⑴ 「이 그림이 3D 냐」는 기하 휴리스틱이다 — 등축 기울기
#   (|Δy/Δx| ≈ 0.4~0.75) 선분이 넷 이상이면 3D 로 본다. 원근·회전 도형은 놓칠 수 있다.
#   ⑵ 세 신호는 **낱말**로 잰다. 「단면적」이라 안 쓰고 그림만 그런 자리는 못 본다.
#   그래서 이 자도 후보만 낸다 — 셋 중 둘이 실제로 맞는지는 사람이 그림을 보고 정한다.
#
# ★★ **자가 자기 편 프리미티브를 못 봤다** (2026-09-07 첫 실사용에서 잡혔다).
#   `svg_iso.py` 로 다시 그린 삽화 둘이 **고친 뒤에도 후보에 그대로 남았다** — 기울기 휴리스틱은
#   기울어진 **직선분**만 세는데 ⑴ 누운 원통(`iso_tube`)은 옆선이 둘뿐이고 나머지가 원이며
#   ⑵ 축이 세로인 관(`iso_pipe`)은 옆선이 **수직**이라 기울어진 선분이 **0개**다.
#   그대로 두면 다음 세션이 이미 등축인 삽화를 다시 열어 같은 판정을 되풀이한다.
#   → 프리미티브가 스스로 찍는 **표식**(`class='iso-tube|iso-pipe|iso-box'`)을 먼저 본다.
#   완화가 아니라 **자에게 도형을 보여 주는 것**이다 — 그 class 는 생성기만 찍고, 손으로 붙이는
#   것은 검사 우회(규칙 10 빨강)다. 잠금 `test_iso_primitives_pass_their_own_rulers`.
ISO_PRIMITIVE_MARK = re.compile(r"class\s*=\s*['\"](?:iso-tube|iso-pipe|iso-box)['\"]")
ISO_SIGNALS = (
    ("단면적", re.compile(r"단면적|단면 넓이|A_\{?c\}?")),
    ("부피·체적", re.compile(r"부피|체적|dV_\{?ol\}?")),
    ("유동+단면", re.compile(r"(?=.*(?:유동|흐름|유량|흐릅|유속))(?=.*단면)", re.S)),
)
# 선분 기울기를 뽑는다 — `M x y L x y` · `x1 y1 x2 y2` 꼴 둘 다 본다.
_SEG_RE = re.compile(r"[ML]\s*(-?\d+(?:\.\d+)?)[ ,]+(-?\d+(?:\.\d+)?)")
ISO_SLOPE_LO, ISO_SLOPE_HI = 0.40, 0.75      # 등축 기울기 0.58 을 가운데 둔 띠
ISO_SEG_MIN = 4                              # 이만큼 있으면 「이미 3D」로 본다


def looks_isometric(svg):
    """등축투영으로 그려진 그림인가 — **휴리스틱**. 순수 함수, 테스트가 직접 부른다.

    공용 프리미티브가 찍은 표식이 있으면 기울기를 안 세고 바로 3D 로 본다(위 ★★).
    """
    if ISO_PRIMITIVE_MARK.search(svg or ""):
        return True
    pts = [(float(a), float(b)) for a, b in _SEG_RE.findall(svg or "")]
    tilted = 0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        dx, dy = x2 - x1, y2 - y1
        if abs(dx) < 1e-6:
            continue
        if ISO_SLOPE_LO <= abs(dy / dx) <= ISO_SLOPE_HI:
            tilted += 1
    return tilted >= ISO_SEG_MIN


def check_iso_3d(chapter, chapter_name):
    hits = []

    def scan(collection, owner):
        for item in collection or []:
            haystack = json.dumps(item, ensure_ascii=False)
            names = [n for n, rx in ISO_SIGNALS if rx.search(haystack)]
            if len(names) < 2:
                continue
            figs = list(item.get("diagrams") or [])
            fig = item.get("figure")
            if isinstance(fig, dict):
                figs.append(fig)
            if not figs:
                hits.append((chapter_name, item.get("id", "?"),
                             owner + " 3D 신호 " + str(len(names)) + "개(" + ", ".join(names)
                             + ")이나 삽화 없음 — 공간 관계를 그릴 필요가 있는지 판정할 후보"))
            for d in figs:
                if looks_isometric(d.get("svg", "")):
                    continue
                hits.append((chapter_name, d.get("id", "?"),
                             owner + " 평면인데 3D 신호 " + str(len(names))
                             + "개(" + ", ".join(names) + ") — 규격 「셋 중 둘」"))

    scan((chapter.get("theory") or {}).get("sections"), "theory")
    scan((chapter.get("derivation") or {}).get("formulas"), "derivation")
    scan(chapter.get("practice"), "practice")
    scan(chapter.get("problems"), "problems")
    return hits


HAND_ARC_RE = re.compile(r"[Aa]\s+[-\d.]")


def check_hand_drawn_arc(chapter, chapter_name):
    """각도 호를 `svg_arc_arrow.py` 없이 손으로 그렸을 가능성 — **정확성이 아니라 습관**을 잰다.

    정본 도구의 출력은 `A42.00 42.00 0 0 0 …`처럼 **`A` 뒤에 공백이 없다**(f-string 그대로
    이어붙인다). 손으로 쓴 arc 는 대개 `A 30 30 0 0 1 …`처럼 `A` 뒤에 공백이 있다 — 실사고
    (각도 25도를 손으로 잡았다가 화살촉에 다 먹혀 T자로 보였다, 2026-08-29)가 이 체크를 열었다.
    ★ 기하 정확성(접선 방향·화살촉 비례)은 `checks_svg.arc_arrowhead_issues`가 **이미 매 빌드
    때 잡는다** — 이 체크는 그것과 겹치지 않는다. 잡는 것은 "정확했는가"가 아니라
    "생성기를 거쳤는가"뿐이고, 손으로 써도 우연히 공백 없이 쓰면 못 잡는다(휴리스틱의 한계).
    """
    hits = []

    def scan(collection):
        for item in collection or []:
            for d in item.get("diagrams") or []:
                if HAND_ARC_RE.search(d.get("svg", "")):
                    hits.append((chapter_name, d.get("id", "?"),
                                 "각도 호에 A 뒤 공백 — svg_arc_arrow.py 미사용 후보"))
            fig = item.get("figure")
            if isinstance(fig, dict) and HAND_ARC_RE.search(fig.get("svg", "")):
                hits.append((chapter_name, fig.get("id", "?"),
                             "각도 호에 A 뒤 공백 — svg_arc_arrow.py 미사용 후보"))

    scan((chapter.get("theory") or {}).get("sections"))
    scan((chapter.get("derivation") or {}).get("formulas"))
    scan(chapter.get("practice"))
    scan(chapter.get("problems"))
    return hits


# 화살표 자루가 도형 외형선에 「얹혀 있다」고 볼 간격·각도. 둘 다 **고른 값**이다.
#
# ★★ 간격 2 — **탐지 문턱은 처방 간격이 아니다** (내린 날 2026-09-08, 표본 4 판정).
#   그전에는 8 이었다. 사용자가 고른 「8」은 **응력요소 밖에 놓을 때 얼마나 띄우나**(처방)
#   였는데, 그것을 「변 위에 얹혔나」를 **탐지**하는 문턱으로 그대로 썼다 — 다른 수다.
#   표본 4 에서 사용자는 **22(간격 0)만 결함**이라 했고, 안이냐 밖이냐는 의도가 정하며
#   τ 는 바깥이 기본이라고 판정했다.
#   실측이 그 판정을 뒷받침한다: 34건의 간격이 **0.0 · 6.0 · 6.8 · 7.0 · 8.0** 다섯 값뿐이고
#   **0 과 6 사이가 통째로 비어 있다.** 그래서 2 는 그 빈 구간 안이고, 좌표를 소수 한 자리로
#   적는 이 리포에서 «같은 선인데 반올림으로 어긋난 것»을 덮기에 넉넉하다.
#   → 처방 간격 10 은 `docs/삽화-규격.md` 에 그대로 있다. 둘을 다시 붙이지 말 것.
#
#   각도 12 — 전단 화살표는 변과 **정확히 나란하다**(0도). 수직응력 화살표·지시선은 변을
#   30도 이상으로 만난다. 12 는 그 사이에서 양쪽에 여유를 둔다.
ARROW_ON_OUTLINE_GAP = 2.0
# 각도 12 — **고른 값이다.** 전단 화살표는 변과 **정확히 나란하다**(0도)고, 수직응력
#   화살표·지시선은 변을 **30도 이상**으로 만난다(법선 방향이라 90도가 정상이다).
#   12 는 그 사이에서 양쪽에 여유를 두는 자리이고, 좌표 반올림으로 몇 도 흔들려도 안 뒤집힌다.
ARROW_ON_OUTLINE_ANGLE = 12.0
# ★ 처방은 **바깥으로 10** 이다. 문턱이 8 이라 8 로 그리면 경계에 걸린다.
#   ☐ **방향은 바깥이다** — 2026-09-08 에 안쪽으로 밀었다가 사용자가 물렸다
#   (*[발화 생략]*). 안쪽은 도형 채움과 겹쳐 화살표가 묻힌다.
ARROW_OFF_OUTLINE_PRESCRIBED = 10.0

_AO_TAG_RE = re.compile(r"<(line|path)\b([^>]*?)/?>")


def _ao_point_seg_dist(px, py, seg):
    x1, y1, x2, y2 = seg
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _ao_angle_deg(a, b):
    ax, ay, bx, by = a[2] - a[0], a[3] - a[1], b[2] - b[0], b[3] - b[1]
    na, nb = math.hypot(ax, ay), math.hypot(bx, by)
    if na == 0 or nb == 0:
        return 90.0
    c = abs(ax * bx + ay * by) / (na * nb)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def _ao_outline_segments(svg):
    """도형 외형선 — **테두리가 있는 닫힌 도형**의 변만. 화살촉 삼각형과 열린 선은 뺀다."""
    from buildlib import checks_svg as cs
    segs = []
    for m in re.finditer(r"<rect([^>]*?)/?>", svg):
        a = m.group(1)
        if cs._effective(svg, m.start(), a, "stroke") in (None, "none"):
            continue
        x, y = float(cs._attr(a, "x", "0")), float(cs._attr(a, "y", "0"))
        w, h = float(cs._attr(a, "width", "0")), float(cs._attr(a, "height", "0"))
        if w <= 0 or h <= 0:
            continue
        segs += [(x, y, x + w, y), (x + w, y, x + w, y + h),
                 (x + w, y + h, x, y + h), (x, y + h, x, y)]
    for m in re.finditer(r"<path([^>]*?)/?>", svg):
        a = m.group(1)
        d = cs._attr(a, "d", "")
        if not d or not re.search(r"[Zz]", d) or cs._is_triangle_path(d):
            continue
        # ★ **테두리가 없으면 외형선이 아니다** (고친 날 2026-09-08). 위 `<rect>` 가지는
        #   이 검사를 하는데 여기만 빠져 있었다 — 그래서 **칠만 한 도형**(외적 삽화의 평행사변형
        #   `fill-opacity` 판 같은 것)의 가장자리가 외형선으로 잡혔고, 그 위를 지나는 벡터
        #   화살표가 「얹힘」으로 신고됐다. 그 자리에는 **그려진 선이 없어 겹칠 것도 없다.**
        #   같은 부류의 판정이 두 가지에 다르게 들어 있던 자리다(규칙 7).
        if cs._effective(svg, m.start(), a, "stroke") in (None, "none"):
            continue
        poly = cs._path_polyline(d)
        if len(poly) >= 3:
            segs += poly
    return segs


# 화살촉 밑변의 가운데가 자루 끝에서 이만큼 안에 있어야 「그 자루의 화살촉」이다.
#   ★ **고른 값이다** (2026-09-08). 삽화 좌표는 소수 둘째 자리까지 적히므로 생성기가 정확히
#     맞춰 찍어도 반올림으로 0.01 쯤 흔들린다. 실측한 화살촉 다섯(안식각 N·f·W · 치수선 ·
#     `fig-vm-slice`)은 전부 **오차 0.00** 이었고, 1.5 는 그 위에 좌표를 손으로 다듬을 여지까지
#     둔 자리다. 화살촉 길이(13 안팎)보다는 확실히 작아야 다음 문단의 구별이 선다.
_AO_HEAD_TOUCH = 1.5


def _ao_arrow_shafts(svg):
    """화살표 자루 — `<line>` 바로 뒤에 화살촉 삼각형 `<path>` 가 오는 짝만 센다.

    ★★ **삼각형이라고 다 화살촉이 아니다** (좁힌 날 2026-09-08). 그전에는 「닫힌 삼각형
      `<path>` 가 바로 뒤에 오는가」만 봤는데, 그 조건은 **삼각형으로 그린 도형**에 그대로
      걸린다 — 동역학 `fig-ch92-e09-ramp` 의 신고가 그것이었다. 지면선(`<line>`) 다음에
      **경사면 쐐기**(`M110 110 L110 235 L250 235 Z`)가 오는데, 이 자는 그 쐐기를 화살촉으로,
      지면선을 자루로 읽었다. 그러고는 지면 위에 놓인 블록 `<rect>` 의 아랫변과 겹친다며
      신고했다 — **화살표가 아예 없는 그림**에서 낸 신고다.
    ★ 그래서 **붙어 있는가**를 함께 본다: 화살촉은 자루 **끝에 밑변을 대고** 있다. 크기로
      가르지 않은 이유는 「작은 삼각형 도형」이 여전히 통과하기 때문이고, 이 조건은 크기와
      무관하게 성립한다. 쐐기의 세 밑변 가운데((110,172.5)·(180,235)·(180,172.5))는 지면선의
      어느 끝(110,235)·(470,235)과도 안 맞는다.
    """
    from buildlib import checks_svg as cs
    tags = [(m.group(1), m.group(2), m.start()) for m in _AO_TAG_RE.finditer(svg)]
    out = []
    for i, (tag, attrs, pos) in enumerate(tags):
        if tag != "line" or i + 1 >= len(tags):
            continue
        ntag, nattrs, _ = tags[i + 1]
        if ntag != "path" or not cs._is_triangle_path(cs._attr(nattrs, "d", "")):
            continue
        shaft = tuple(float(cs._attr(attrs, k, "0")) for k in ("x1", "y1", "x2", "y2"))
        if not _ao_head_sits_on_shaft(shaft, cs._attr(nattrs, "d", "")):
            continue
        out.append((shaft, pos, cs._attr(attrs, "class", "")))
    return out


def _ao_head_sits_on_shaft(shaft, dstr):
    """화살촉의 밑변 가운데가 자루의 두 끝 중 하나에 닿아 있나.

    삼각형 `d` 는 이미 «`M L L [Z]` · 수 여섯» 으로 확인된 것만 들어온다
    (`checks_svg._is_triangle_path`) — 그래서 좌표를 그 여섯에서 바로 읽는다.
    """
    from buildlib import checks_svg as cs
    _cmds, nums = cs._svg_path_signature(dstr)
    if len(nums) != 6:
        return False
    pts = [(float(nums[0]), float(nums[1])),
           (float(nums[2]), float(nums[3])),
           (float(nums[4]), float(nums[5]))]
    ends = ((shaft[0], shaft[1]), (shaft[2], shaft[3]))
    for a in range(3):
        for b in range(a + 1, 3):
            mx = (pts[a][0] + pts[b][0]) / 2
            my = (pts[a][1] + pts[b][1]) / 2
            if any(math.hypot(mx - ex, my - ey) <= _AO_HEAD_TOUCH for ex, ey in ends):
                return True
    return False


# 자루에 이 역할이 붙어 있으면 「변을 따라 놓인 것」이 **의도**다 — 얹힘으로 세지 않는다.
#   ★ 왜 필요했나 (2026-09-08): 어느 과목 `fig-p05-gusset-splits` 의 신고 넷이 전부
#     **좌표축**이었다. 단면 2차 모멘트 그림에서 x·y 축은 도형의 아래·왼쪽 변에 **정의상**
#     겹친다 — 원점이 그 모서리이기 때문이다. 축을 변에서 띄우면 그림이 틀린다.
#   ★ 이름은 새로 만들지 않았다 — `checks_svg.DASH_LEGIT_ROLES` 에 이미 선언된 역할에서
#     「기준선」 성격의 것만 골랐다(같은 목록을 두 자가 나눠 갖지 않게 한다).
ARROW_ON_OUTLINE_SKIP_ROLES = ("dim", "measure", "guide", "axis", "datum")


def check_curve_facets(chapter, chapter_name):
    """곡선을 점으로 흉내 냈는데 **면이 눈에 띄게 각져 있다** (열린 날 2026-09-10).

    사용자 재지적: *[발화 생략]*.
    재는 자는 `tools/audit_curve_smoothness.py` 하나이고 여기서는 그것을 부르기만 한다 —
    ⑵ 도구를 만들고 ⑶ 여기 등록하지 않으면 **앞으로 그리는 것만 막고 이미 쓴 콘텐츠는
    방치된다**(규칙 7⑶). 실제로 그렇게 방치돼 같은 지적이 두 번 나왔다.

    문턱은 그 도구의 `DEFAULT_LIMIT`(볼록 깊이 1.0px = 선 두께의 절반)을 그대로 쓴다.
    """
    hits = []
    for fig in figure_balance.iter_diagrams(chapter):
        found = curve_smoothness.measure_svg(fig.get("svg") or "")
        if not found:
            continue
        depth, deg, npts, seg = max(found)
        if depth <= curve_smoothness.DEFAULT_LIMIT or fig.get(curve_smoothness.WAIVER_KEY):
            continue
        hits.append((chapter_name, fig.get("id", "?"),
                     "곡선이 각졌다 — 볼록 깊이 %.2fpx (%.1f° · %d점 · 선분 %.0fpx)"
                     % (depth, deg, npts, seg)))
    return hits


def check_arrow_on_outline(chapter, chapter_name):
    """화살표 자루가 도형 외형선 **위에** 그려졌는가 — 후보만 낸다.

    열린 날 2026-09-08. 사용자: *[발화 생략]* (`fig-11-stress-element` 의 전단 화살표
    둘이 회전 요소의 변과 **같은 좌표에서 시작**하고 있었다 — 선 위에 선을 겹쳐 그린 것이라
    화살표가 변에 먹혀 안 보였다).

    빌드가 왜 못 잡았나: F6(`_arrow_clearance_issues`)은 화살표가 도형을 **관통**하거나
    화살촉끼리 붙는 것을 보지, **변을 따라 나란히 얹힌 것**은 안 본다. 관통이 아니라
    포개짐이라 어느 자에도 안 걸렸다.

    ★ **판정은 사람이 한다.** 나란히 놓는 것이 옳은 자리도 있다(면을 따라 작용하는 것을
      그 면 위에 그리는 것은 교과서 관례다). 이 자가 말하는 것은 «겹쳐 그렸다» 하나이고,
      그것이 읽히는지는 렌더를 봐야 안다. 그래서 빌드 게이트가 아니라 후보 목록이다.

    ☐ **못 보는 것:** ⑴ 자루가 `<path>` 로 그려진 화살표(여기서는 `<line>`+삼각형 짝만 센다)
      ⑵ `transform` 이 걸린 조각 ⑶ 곡선 외형선(원·타원 둘레) 위에 얹힌 화살표.
    """
    from buildlib import checks_svg as cs
    hits = []

    def scan_svg(fig_id, svg):
        if not svg:
            return
        outline = _ao_outline_segments(svg)
        if not outline:
            return
        dim_spans = [(s, e) for s, e, _b
                     in cs._tagged_group_spans(svg, ARROW_ON_OUTLINE_SKIP_ROLES)]
        for shaft, pos, role in _ao_arrow_shafts(svg):
            if any(s <= pos < e for s, e in dim_spans):
                continue                       # 치수선·기준선은 일부러 변과 나란하다
            # ★ 역할이 `<g>` 가 아니라 **그 선 자신**에 붙기도 한다(class='guide').
            #   묶음만 보면 좌표축 넷이 그대로 신고됐다 — 둘 다 본다.
            if any(r in role.split() for r in ARROW_ON_OUTLINE_SKIP_ROLES):
                continue
            mx, my = (shaft[0] + shaft[2]) / 2, (shaft[1] + shaft[3]) / 2
            for seg in outline:
                gap = _ao_point_seg_dist(mx, my, seg)
                if gap > ARROW_ON_OUTLINE_GAP:
                    continue
                if _ao_angle_deg(shaft, seg) > ARROW_ON_OUTLINE_ANGLE:
                    continue
                # ★ **잰 값을 함께 낸다** (2026-09-08). 문턱을 옮길 때마다 「몇 건」만 보고
                #   골랐는데, 그 수로는 **어느 값에서 무엇이 빠지는지**를 알 수 없었다.
                #   실측 간격을 찍으면 문턱 후보를 목록에서 바로 읽을 수 있다(실행 규율 16).
                hits.append((chapter_name, fig_id,
                             "화살표 자루가 외형선에 얹힘 — 변에서 띄울 것 (간격 %.1f)" % gap))
                break

    def scan(collection):
        for item in collection or []:
            for d in item.get("diagrams") or []:
                scan_svg(d.get("id", "?"), d.get("svg", ""))
            fig = item.get("figure")
            if isinstance(fig, dict):
                scan_svg(fig.get("id", "?"), fig.get("svg", ""))

    scan((chapter.get("theory") or {}).get("sections"))
    scan((chapter.get("derivation") or {}).get("formulas"))
    scan(chapter.get("practice"))
    scan(chapter.get("problems"))
    return hits


def check_rate_dot(chapter, chapter_name):
    """산문에 완성형 닷 글자가 남아 있는가 — 판정 로직은 `fix_rate_dot.convert()` 그대로 재사용."""
    hits = []

    def scan(node, owner, item_id):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in fix_rate_dot.SKIP_KEYS:
                    continue
                scan(v, owner, item_id)
        elif isinstance(node, list):
            for v in node:
                scan(v, owner, item_id)
        elif isinstance(node, str):
            if fix_rate_dot.convert(node) != node:
                hits.append((chapter_name, item_id,
                             owner + " 필드에 닷 글자 날것 — fix_rate_dot.py 미적용 후보"))

    for item in (chapter.get("theory") or {}).get("sections") or []:
        scan(item, "theory", item.get("id", "?"))
    for item in (chapter.get("derivation") or {}).get("formulas") or []:
        scan(item, "derivation", item.get("id", "?"))
    for item in chapter.get("practice") or []:
        scan(item, "practice", item.get("id", "?"))
    for item in chapter.get("problems") or []:
        scan(item, "problems", item.get("id", "?"))
    return hits


# ★ 어간 `대입` 으로 잡는다 — `대입하면` 만 보던 옛 판은 **`대입합니다`·`대입해`·`대입한` 을
#   통째로 놓쳤다**(2026-09-07 실측: 기계공작법 ch15 를 고치며 어미만 바꿨는데 후보에서
#   사라졌다 — 결함이 고쳐져서가 아니라 자가 못 본 것이었다). 한글은 «대입」+「합니다」로
#   음절이 합쳐져 `대입하` 가 부분문자열이 아니다. 이 자의 설계는 「오탐 허용, 안 빠뜨림」이라
#   재현율 구멍이 문턱보다 나쁘다.
DERIV_JUMP_RE = re.compile(r"대입|첫 줄에 넣|두 식을 이으")


def check_derivation_jump(chapter, chapter_name):
    """유도 단계의 대입이 원래 식 재인용 없이 건너뛰는 후보 — 공용 폴더 원장 2026-08-19.

    판정선(«원래 식이 화면 바로 위에 있는가»)은 사람 몫이다. 이 자는 방아쇠 낱말만 훑어
    후보를 낸다 — 바로 위에 이미 보이는 정당한 경우까지 걸릴 수 있다(오탐 허용, 그 대신
    빠뜨리지 않는다).
    """
    hits = []
    for f in (chapter.get("derivation") or {}).get("formulas") or []:
        steps = f.get("derivationSteps") or []
        for i, st in enumerate(steps, 1):
            text = st.get("text") if isinstance(st, dict) else st
            if not (text and DERIV_JUMP_RE.search(text)):
                continue
            hits.append((chapter_name, str(f.get("id", "?")) + "/step" + str(i),
                         "대입 단계 후보 — 원래 식이 바로 위에 있는지 확인"
                         + _requote_note(steps, i) + _step_dump(steps, i)))
    return hits


# 순서 표지 — 본문이 **시간 순서를 주장**하는 자리의 방아쇠 낱말.
# 정본 판정선은 `docs/2026-09-07-삽화-동작-사양.md` 「판정선 — 언제 움직이나」이고,
# 이 자는 그 셋 중 ⑴ 만 기계로 훑는다(⑵ 슬라이드로 되나 · ⑶ 근거가 교재에 있나는 사람 몫).
#
# ★ 첫 판이 **0건이었고 그것은 「없다」가 아니라 「자가 못 봤다」였다**(규칙 21). 사양이
#   이름까지 든 자리(기계공작법 `ch10 sec-solidification` — *[발화 생략]* · *[발화 생략]*)를 자기가 못 잡았다. 원인은 활용형이었다:
#   `뻗어나가` 를 붙여 썼고 종결형(`나갑니다`)을 안 봤다. **자를 먼저 그 실례에 대 본다.**
MOTION_ORDER_RE = re.compile(
    r"(먼저[^.\n]{0,60}(그다음|그 다음|다음으로|이어서|그 뒤|마지막)"
    r"|차례로|순서대로"
    r"|(자라|뻗어|번져|퍼져|밀려|흘러)\s*(나가|나갑|나간|간다|갑니다|납니다)"
    r"|(안쪽|바깥쪽|중앙부|중심부|아래쪽|위쪽)으?로\s*(자라|뻗|번지|퍼지|밀리)"
    r"|시작해서[^.\n]{0,30}(향한|향합|퍼진|퍼집|자란|자랍)"
    r"|점점\s*[^.\n]{0,20}(자란|커진|줄어든|퍼진|길어진)"
    r")")


def check_motion_gap(chapter, chapter_name):
    """본문이 **시간 순서를 주장하는데** 그 절에 움직이는 그림도 단계 그림도 없는 자리.

    열린 날 2026-09-08. 사용자 지적이 뿌리다 — *[발화 생략]*.

    ★ **후보만 낸다.** 순서 표지가 있어도 그림이 필요 없는 절이 있다(계산 절차 나열이
    대표적이다). 그리고 사양의 판정선 ⑵ 는 **먼저 슬라이드로 되는지 묻는 것**이라,
    여기 걸린 것의 정답이 언제나 `motion` 인 것도 아니다.
    """
    hits = []
    for s in (chapter.get("theory") or {}).get("sections") or []:
        # ★ `content` 는 **문자열 하나**다(목록이 아니다). 첫 판이 목록으로 알고 돌아
        #   글자를 하나씩 이어 붙였고, 그래서 어떤 낱말도 안 맞아 0건이 나왔다 —
        #   앞의 「활용형」 정정과 **원인이 달랐다.** 두 번째 0건이 그것을 드러냈다.
        raw = s.get("content")
        text = raw if isinstance(raw, str) else " ".join(
            str(c) for c in (raw or []) if isinstance(c, str))
        m = MOTION_ORDER_RE.search(text)
        if not m:
            continue
        diagrams = s.get("diagrams") or []
        if any(isinstance(d, dict) and d.get("motion") for d in diagrams):
            continue
        why = ("삽화가 없다" if not diagrams
               else "삽화 %d개가 있으나 motion 도 단계 그림도 아니다" % len(diagrams))
        hits.append((chapter_name, s.get("id", "?"),
                     "본문이 순서를 주장하는데 " + why + " — 표지 " + repr(m.group(0)[:24])))
    return hits


# 기하학적 관계를 말하는 식의 방아쇠. 정본 판정선은 `docs/삽화-규격.md` 「넷째 신호」이고,
# 이 자는 그 표의 네 꼴 중 **기계로 볼 수 있는 것만** 훑는다.
#
# ★★ **첫 판은 285건이었고, 그것은 재는 것이 아니라 자를 재는 것이었다**(규칙 21).
#   두 가지를 넣었다가 뺐다 — 뺀 이유를 적어 둔다. 다시 넣으려는 사람이 먼저 읽을 자리다.
#
#   ⑴ **그리스 문자 단독**(`\theta`·`\beta`·`\alpha`·`\phi`)을 「각 기호」로 봤다. 실측하니
#      각이 아닌 자리가 압도적이었다 — 같은 글자가 성능계수·전류이득·상(phase) 이름·
#      열확산계수·함수 기호·황금비·온도차로 쓰인다. 기호만 보고는 못 가른다.
#      어느 과목의 어느 글자가 그랬는지는 `docs/삽화-규격.md` 「넷째 신호」의 실측 표가 정본이다
#      (여기 적으면 공통 도구가 과목을 알게 된다 — `test_tools_do_not_hardcode_a_subject`).
#   ⑵ **마주 보는 분수**를 「비가 결과를 뒤집는 식」으로 봤다. 걸린 것의 거의 전부가
#      **미분 표기**(`\frac{dy}{dx}`)이거나 **정의식**(`\frac{P}{A}`·`\frac{VQ}{Ib}`)이었다 —
#      규격이 「안 걸리는 것」으로 명시한 바로 그 꼴이다.
#
#   그래서 방아쇠를 **삼각함수 이름 하나**로 좁혔다. 사용자가 든 예(탄젠트)가 정확히 그 자리다.
#
# ★ 무엇을 안 보나(규칙 21):
#   · 「비가 결과를 뒤집는 식」과 「극값·부호가 바뀌는 자리」는 **안 본다**(위 ⑵의 대가다).
#     그 둘은 규격의 표에 남겨 두고 사람이 훑는다.
#   · 각을 **말로만** 설명하고 식이 없는 절은 못 본다 — 방아쇠가 식 쪽에 있다.
#   · 삽화가 있어도 **그 관계를 안 그린** 그림이면 통과시킨다(그림의 내용은 안 읽는다).
GEOMETRY_FORMULA_RE = re.compile(r"(\\tan|\\sin|\\cos|\\arctan|\\arcsin|\\arccos)")


def check_geometry_in_formula_only(chapter, chapter_name):
    r"""**기하학적 관계를 식으로만 두고 그림을 안 그린 자리** — 후보만 낸다.

    열린 날 2026-09-08. 사용자 지적이 뿌리다 — *[발화 생략]*.

    판정선은 「독자가 머릿속에서 그림으로 바꿔야 하는가」이고 그것은 사람 몫이다. 이 자는
    **각·삼각함수·비**가 든 식을 훑어 그 절이나 그 유도 카드에 삽화가 0 인 자리를 낸다.

    ☐ 오탐을 허용한다 — 빠뜨리지 않는 쪽을 고른다. 정의식이나 대입식이 걸리면 사람이 뺀다.
    """
    hits = []
    for s in (chapter.get("theory") or {}).get("sections") or []:
        if s.get("diagrams"):
            continue
        raw = s.get("content")
        text = raw if isinstance(raw, str) else " ".join(
            str(c) for c in (raw or []) if isinstance(c, str))
        m = GEOMETRY_FORMULA_RE.search(text)
        if not m:
            continue
        hits.append((chapter_name, s.get("id", "?"),
                     "기하 관계가 식으로만 있다(절에 삽화 0) — 방아쇠 "
                     + repr(m.group(0)[:20])))
    # 유도 카드도 같은 자로 본다 — 각을 정하는 식은 대개 거기 산다.
    for f in (chapter.get("derivation") or {}).get("formulas") or []:
        if f.get("diagrams"):
            continue
        blob = str(f.get("latex", ""))
        for st in f.get("derivationSteps") or []:
            if isinstance(st, dict):
                blob += " " + " ".join(str(e) for e in (st.get("equations") or []))
        m = GEOMETRY_FORMULA_RE.search(blob)
        if not m:
            continue
        hits.append((chapter_name, str(f.get("id", "?")),
                     "유도가 각·삼각함수를 쓰는데 카드에 그림이 없다 — 방아쇠 "
                     + repr(m.group(0)[:20])))
    return hits


# 삽화 글자에서 기호로 셀 만한 것 — 로마자 한두 글자, 그리스 문자, 아래첨자 0.
FIGURE_SYMBOL_RE = re.compile(r"[A-Za-z]|[α-ωΑ-Ω]|[₀-₉]")
# 식에서 뽑을 기호. 매크로 이름(`frac`·`left`)이 아니라 **낱글자**만 본다.
FORMULA_SYMBOL_RE = re.compile(r"(?<![\\A-Za-z])([A-Za-z])(?![A-Za-z])")
# 이 글자들은 세지 않는다 — 어느 식에나 있어서 「담겼다」를 부풀린다.
SYMBOL_STOPWORDS = frozenset("dexn")


def check_figure_carries_the_symbols(chapter, chapter_name):
    r"""**유도 카드에 그림은 있는데 그 식의 기호가 그림에 하나도 없는 자리** — 후보만 낸다.

    열린 날 2026-09-08. 사용자 지적이 뿌리다 — *[발화 생략]* ·
    *[발화 생략]* — 인용에서 과목 이름 하나를 뺐다. 전문은 `docs/삽화-규격.md` 「다섯째」에 있다.

    ★★ **기존 자들과 무엇이 다른가 — 「있나」가 아니라 「제 일을 하나」를 잰다.**
    `check_geometry_in_formula_only` 는 **삽화가 없는** 자리를 찾는다. 이 자는 **삽화가
    있는데도** 본문의 양을 하나도 안 담은 자리를 찾는다. 실사고와 과목별 실측은
    `docs/삽화-규격.md` 「다섯째」가 정본이다 — **공통 도구 소스에 과목 이름을 박지 않는다**
    (`test_tools_do_not_hardcode_a_subject`). 요지만: 어떤 엑서지 정의식 유도 카드가 삽화를
    갖고 있었는데 상자 둘과 화살표뿐이라 그 식의 주인공 기호가 **그림에 0회** 등장했고,
    그래서 스텝이 넘어가도 그림이 사실상 안 바뀌었다.

    ★★ **첫 판이 자기 결함을 못 잡았다 — 그래서 두 군데를 고쳤다** (규칙 21, 자의 검정).
    처음엔 ⑴ SVG 의 **모든** 글자를 「그려진 것」으로 세고 ⑵ 「하나도 없을 때」만 신고했다.
    그 자를 **이미 아는 결함**(옛 `fig-f-exergy-definition-composite`)에 대 보니 **안 걸렸다**:

      · 단계 설명 줄(`class='fig-note'`)이 «T dS 관계식을…» 처럼 기호를 도로 적어 준다 —
        캡션은 **그림이 아니라 글**인데 그것까지 세면 「글로 때운 삽화」가 통과한다.
      · 화살표 라벨 `ΔV` 하나 때문에 «0개는 아니다» 가 되어 통과했다. 여섯 중 하나였다.

    → ⑴ `fig-note` 는 **빼고 센다** ⑵ 문턱을 **절반**으로 둔다. 옛 판은 6 중 1 이라 걸리고,
      다시 그린 판은 6 중 5 라 안 걸린다. **아는 결함과 아는 정상 둘로 재 보고 고른 문턱이다.**

    ☐ **이 자가 여전히 못 보는 것:** 기호가 「몇 개 있나」만 세고 **그것이 뜻대로 그려졌나**는
    못 본다. `U` 라는 글자만 찍어 놓아도 통과한다. 그래서 게이트가 아니라 후보다 — 사람이 연다.
    """
    hits = []
    for f in (chapter.get("derivation") or {}).get("formulas") or []:
        figures = [d for d in (f.get("diagrams") or [])]
        if f.get("figure"):
            figures = figures + [f["figure"]]
        if not figures:
            continue                     # 그림이 없는 자리는 위 `geometry-in-formula-only` 몫
        drawn = ""
        for fig in figures:
            svg = str(fig.get("svg", ""))
            # 단계 설명 줄은 캡션이라 뺀다 — 위 ★★ 참고.
            svg = re.sub(r"<g[^>]*class='[^']*fig-note[^']*'[^>]*>.*?</g>", " ", svg)
            for chunk in re.findall(r">([^<>]+)<", svg):
                drawn += chunk
        wanted = set()
        for sym in FORMULA_SYMBOL_RE.findall(str(f.get("latex", ""))):
            if sym.lower() not in SYMBOL_STOPWORDS:
                wanted.add(sym)
        if len(wanted) < 3:
            continue                     # 기호가 둘뿐인 식은 그림이 담을 것도 적다
        shown = {s for s in wanted if s in drawn}
        if len(shown) * 2 >= len(wanted):
            continue
        hits.append((chapter_name, str(f.get("id", "?")),
                     "삽화가 식의 기호를 %d/%d 만 담았다 — 식이 쓰는 것 %s · 그림에 있는 것 %s"
                     % (len(shown), len(wanted),
                        repr("".join(sorted(wanted))[:12]),
                        repr("".join(sorted(shown))[:12]))))
    return hits


# 조사만 떼어 낸다 — 어미(`다`·`나`)는 안 뗀다(어간을 깎아 없는 말을 만든다).
PARTICLE_RE = re.compile(r"(에서는|으로는|에서|으로|에게|부터|까지|보다|처럼|이나|은|는|이|가"
                         r"|을|를|의|에|와|과|도|만|로|나)$")
# 정규화 뒤 이보다 짧은 말은 안 본다 — 두 글자 낱말은 다른 낱말 안에 우연히 들어간다.
TERM_MIN_LEN = 3
# 문풀·문제에 **이만큼 이상** 나온 말만 후보다. 한 번뿐인 말은 그 문항의 소재(사물 이름·
# 상황)일 때가 많고, 그건 본문이 도입할 대상이 아니다.
TERM_MIN_HITS = 2
# ★ 첫 실행이 **503건**이었고 대부분이 결함이 아니라 **활용형**이었다(규칙 21 — 자의 검정).
#   `곱하면`·`셉니다`·`넘으면`·`것이고` 같은 것이 「이론에 없는 말」로 올라왔다.
#   조사만 떼는 설계라 어미가 그대로 남은 것이고, 게다가 조사 `로` 를 떼다 `그러므로` 를
#   `그러므` 로 깎아 **없는 낱말**까지 만들었다. 걸러 내는 자 둘을 붙인다:
#   ⑴ 어미로 끝나는 것은 낱말이 아니다 ⑵ 조사 없이 **혼자 선 적이 한 번도 없는** 것은
#      내가 깎아서 만든 조각이다.
VERB_TAIL = ("니다", "습니", "어요", "아요", "해요", "으면", "하면", "되면", "이고", "이며",
             "하고", "하며", "지만", "는데", "면서", "어서", "아서", "려면", "이다", "한다",
             "된다", "았다", "었다", "겠다", "세요", "나요", "까요", "라고", "이라", "같이",
             "처럼", "만큼", "이나", "거나", "든지", "도록", "네요", "지요", "군요",
             "는지", "은지", "는다", "았다", "었다", "니라", "아니", "다")


def _norm_kr(text):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(text).lower())


def _walk_text(node, out, skip):
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for key, value in node.items():
            if key.startswith("_") or key in skip:
                continue
            _walk_text(value, out, skip)
    elif isinstance(node, list):
        for item in node:
            _walk_text(item, out, skip)


AUTHOR_ONLY = ("sourceRef", "rationale", "changeNote", "source", "reviewNote")


def _collection_text(chapter, names):
    out = []
    for name in names:
        _walk_text(chapter.get(name), out, AUTHOR_ONLY)
    return "\n".join(out)


CURRENT_FOLDER = []      # main() 이 과목마다 갈아 끼운다 — 이 검사만 읽는다
_ACCUM = {"folder": None, "theory": ""}


def _accumulate_theory(chapter, chapter_name):
    """이 과목에서 **여기까지 나온 이론 본문**을 이어 붙인다.

    순회기가 과목마다 챕터를 오름차순으로 한 번씩 부르므로 그대로 쌓기만 하면 된다.
    과목이 바뀌면 비운다 — 안 비우면 남의 과목 이론이 이 과목의 「도입했다」가 된다.
    """
    folder = CURRENT_FOLDER[0] if CURRENT_FOLDER else None
    if _ACCUM["folder"] != folder:
        _ACCUM["folder"], _ACCUM["theory"] = folder, ""
    _ACCUM["theory"] += _norm_kr(_collection_text(chapter, ("theory",)))


def check_term_not_introduced(chapter, chapter_name):
    """문풀·문제가 **이론 본문에 한 번도 안 나온 말**을 전제하는 자리.

    열린 날 2026-09-08. 뿌리는 기계공작법 ch10 인박스가 한 장에서 셋을 찾아낸 것이다 —
    액상선·고상선(⑵) · 주입 속도의 대가(⑶) · 레이놀즈 수(⑸). 셋이 같은 모양이라
    인스턴스가 아니라 부류다(규칙 7): **이론이 도입하지 않은 말을 뒤 컬렉션이 안다고 친다.**
    독자는 처음 보는 말의 문턱값을 빈칸으로 답하게 된다(「목표 독자」 절 위반).

    ★ **후보만 낸다.** 문항의 소재(사물 이름·상황·단위)는 본문이 도입할 대상이 아니고,
    같은 뜻을 다른 낱말로 쓴 자리도 여기 걸린다 — 이 자는 **글자**를 볼 뿐 뜻을 모른다.
    """
    # ★★ **모의고사·요약 장(`ch90` 이상)은 대상이 아니다** (2026-09-08, 세 번째 교정).
    #   실측: 공학수학 1 `ch91` 이 「고유값 6회」로 떴는데 그 장은 **중간고사 모의고사**다 —
    #   앞 장(ch01~ch04)에서 배운 말을 전제하는 것이 그 장의 목적이라 「이론이 도입 안 했다」가
    #   결함이 아니라 **설계**다. 실패가 아니라 대상이 아닌 것이므로 조용히 뺀다.
    if re.fullmatch(r"ch9\d", chapter_name.split()[-1] if chapter_name else ""):
        return []
    # ★★★ **묻는 것은 「이 장이 도입했나」가 아니라 「이 과목이 도입했나」다**
    #   (2026-09-08, 네 번째 교정). 실측: 유체역학 `ch06` 이 「질량유량 6회」로 떴는데
    #   그 말은 **`ch05` 가 23번 쓰며 도입해 둔 것**이다. 독자는 ch05 를 읽고 ch06 에 오므로
    #   결함이 아니다. 그래서 이 장까지의 **모든 앞 장 이론**을 합쳐서 본다 —
    #   인박스가 든 원래 셋(액상선·주입 속도·레이놀즈)은 **과목 전체에 없던** 말이라
    #   넓혀도 그대로 잡힌다.
    _accumulate_theory(chapter, chapter_name)
    theory = _ACCUM["theory"]
    later = _collection_text(chapter, ("practice", "problems"))
    if not theory or not later:
        return []

    counts = {}
    standalone = set()
    for run in re.findall(r"[가-힣]{3,12}", later):
        standalone.add(run)
        # 조사는 겹쳐 붙는다(`온도에서의`·`절반으로는`) — 안 줄어들 때까지 뗀다.
        stem = run
        for _ in range(3):
            shorter = PARTICLE_RE.sub("", stem)
            if shorter == stem or len(shorter) < TERM_MIN_LEN:
                break
            stem = shorter
        if len(stem) < TERM_MIN_LEN or stem == run:
            # ★★ **조사가 실제로 붙어 있던 것만 센다** (2026-09-08, 두 번째 교정).
            #   어미 목록으로 거르는 길은 한국어 활용에서 절대 안 닫힌다 — 213건에 여전히
            #   `되짚어`·`식으며`·`같아야`·`만들고`·`곱하기`·`아무리` 가 남았고, 하나 막으면
            #   다음 어미가 나온다. 뒤집는다: **명사는 조사를 달고 나온다.**
            #   ☐ 대신 잃는 것 — 표 칸처럼 조사 없이 홑으로만 쓰인 낱말은 못 본다.
            #     후보를 내는 자라 정확도를 택했고, 이 사실을 여기 적어 둔다.
            continue
        counts[stem] = counts.get(stem, 0) + 1

    hits = []
    for stem, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if n < TERM_MIN_HITS or _norm_kr(stem) in theory:
            continue
        if stem.endswith(VERB_TAIL):
            continue                      # 활용형이지 낱말이 아니다
        if stem not in standalone:
            continue                      # 조사를 떼다 내가 만든 조각이다
        hits.append((chapter_name, stem, "문풀·문제에 %d번 나오는데 이론 본문에 없다" % n))
    return hits


SHOW_STEPS = []          # `--steps` 가 켜면 [True] — 판정에 쓰는 값이 아니라 표시 스위치다


def _step_dump(steps, i):
    """`--steps` 일 때 **앞 단계와 이 단계의 식**을 그대로 붙인다.

    ★ 왜 (2026-09-07). 이 자의 판정선은 «원래 식이 바로 위에 있는가» 인데, 그걸 보려면
      후보마다 카드를 통째로 열어야 했다 — 후보 70건이면 왕복 70번이고 그 출력이 이 자의
      100배다(규율 12 「비싼 것은 도구 출력의 크기」). 판정에 필요한 것은 **식 두 묶음**뿐이다.
    """
    if not SHOW_STEPS:
        return ""
    prev = steps[i - 2] if i >= 2 else None
    cur = steps[i - 1]

    def eqs(st):
        if not isinstance(st, dict):
            return ["(없음)"]
        return [str(e) for e in (st.get("equations") or [])] or ["(없음)"]

    out = "\n           앞:  " + "\n                ".join(eqs(prev) if prev else ["(첫 단계)"])
    return out + "\n           이:  " + "\n                ".join(eqs(cur))


def _norm_eq(s):
    return "".join(str(s).split())


def _requote_note(steps, i):
    """그 단계가 **바로 앞 단계의 식을 다시 인용했나** — 라벨만 붙인다, 판정하지 않는다.

    ★ 왜 (2026-09-07 실측). 방아쇠 낱말이 「대입하」라서 유도 카드 대부분이 걸린다 —
      2-2 과목 8건을 손으로 본 결과 **결함 1 · 오탐 6 · 곁가지 1** 이었다. 오탐 허용은
      이 자의 설계(빠뜨리지 않는 쪽)이므로 문턱을 올리지 않는다. 대신 **사람이 건너뛸 수
      있는 것에 표를 붙여** 판정 비용을 줄인다 — 앞 단계 식이 이 단계 첫 줄에 그대로
      다시 나오면 「원래 식이 바로 위에 있는가」가 이미 참이다.
    """
    prev = steps[i - 2] if i >= 2 else None
    cur = steps[i - 1]
    if not isinstance(cur, dict) or not isinstance(prev, dict):
        return ""
    cur_eqs = [_norm_eq(e) for e in (cur.get("equations") or [])]
    prev_eqs = [_norm_eq(e) for e in (prev.get("equations") or [])]
    if not cur_eqs:
        return "  ← 이 단계에 식이 없다(대입식이 산문 안에만 있다)"
    if prev_eqs and any(c and any(c in p or p in c for p in prev_eqs) for c in cur_eqs[:1]):
        return "  ← [약함] 앞 단계 식을 그대로 다시 인용했다"
    return ""


def check_ox_length_tell(chapter, chapter_name):
    r"""**O/X 문항을 길이만 보고 맞힐 수 있는 자리** — 후보만 낸다.

    열린 날 2026-09-08. 어느 과목의 오픈북 시험 설계 정본(`data/<과목>/시험-설계-오픈북.md` §5)이
    *[발화 생략]* 를 요구하는데,
    그 규칙을 **아무도 재지 않고 있었다.** 첫 실측에서 한 모의고사 장이 참 117~194자 ·
    거짓 90~113자로 통째로 갈려 있었다(과목 이름은 여기 안 적는다 — 공통 도구다).

    ★ 판정선은 문턱이 아니라 **완전 분리**다. 지문 길이로 정렬했을 때 참 무리와 거짓 무리가
      한 지점에서 통째로 갈리면(둘의 구간이 안 겹치면) 그 시험지는 **길이만 보고 다 맞힐 수
      있다.** 문턱을 손으로 정하지 않아도 되고, 문항 수가 달라져도 뜻이 안 변한다.

    ☐ 못 보는 것: 겹치기만 하면 통과시키므로 «대체로 참이 길다» 는 못 잡는다. 그리고 길이
      말고 다른 단서(단정어 «항상·결코», 절 개수)는 안 본다 — 그 둘은 사람이 훑는다.
    """
    ox = [q for q in (chapter.get("problems") or [])
          if isinstance(q, dict) and isinstance(q.get("oxCorrect"), bool)]
    if len(ox) < 4:                       # 넷 미만이면 분리가 우연히 생긴다 — 대상이 아니다
        return []
    def body(q):
        return str(q.get("prompt", "")).replace("참입니까, 거짓입니까?", "").strip()
    yes = sorted(len(body(q)) for q in ox if q["oxCorrect"])
    no = sorted(len(body(q)) for q in ox if not q["oxCorrect"])
    if not yes or not no:
        return []
    if min(yes) > max(no) or min(no) > max(yes):
        longer = "참" if min(yes) > max(no) else "거짓"
        return [(chapter_name, "O/X %d문항" % len(ox),
                 "길이만 보고 다 맞힐 수 있다 — %s 쪽이 통째로 길다(참 %d~%d자 · 거짓 %d~%d자)"
                 % (longer, yes[0], yes[-1], no[0], no[-1]))]
    return []


def check_ox_phrase_tell(chapter, chapter_name):
    r"""**O/X 를 문형만 보고 맞힐 수 있는 자리** — 길이 단서의 사촌이다. 후보만 낸다.

    열린 날 2026-09-08. 길이 단서를 잡고 나서 같은 시험지의 **다른 시험지**를 읽다가 눈으로
    발견했다 — 열 문항 중 여덟이 「…입니다. 이 사실로부터 …라고 말할 수 있습니다」라는 한
    틀을 쓰고 그 여덟이 **전부 거짓**이었다. 나머지 둘은 그 틀을 안 쓰고 **둘 다 참**이었다.
    즉 문장 모양만 보고 열 문항을 다 맞힐 수 있었다.

    ★ 재는 법: 지문에서 길이 8 의 글자 조각을 모두 뽑아, **셋 이상의 문항에 공통으로 나오고
      그것을 가진 문항의 답이 전부 같으며, 안 가진 문항 중에 답이 다른 것이 있는** 조각을 낸다.
      마지막 조건이 「모든 문항에 있는 말」(「참입니까」·「입니다」)을 걸러 준다.

    ☐ 못 보는 것: 여덟 글자에 안 담기는 긴 틀, 그리고 **뜻은 같은데 글자가 다른** 바꿔쓰기.
      한 조각이라도 걸리면 사람이 그 틀 전체를 눈으로 본다 — 이 자는 실마리만 준다.
    """
    ox = [q for q in (chapter.get("problems") or [])
          if isinstance(q, dict) and isinstance(q.get("oxCorrect"), bool)]
    if len(ox) < 4:
        return []
    answers = {q.get("id"): q["oxCorrect"] for q in ox}
    if len(set(answers.values())) < 2:          # 한쪽뿐이면 어떤 조각이든 「예측」한다
        return []
    grams = {}
    for q in ox:
        text = str(q.get("prompt", ""))
        for g in {text[i:i + 8] for i in range(max(0, len(text) - 7))}:
            grams.setdefault(g, set()).add(q.get("id"))
    hits = []
    for g, owners in grams.items():
        if len(owners) < 3 or len(owners) == len(ox):
            continue
        inside = {answers[i] for i in owners}
        # ★ 첫 판은 「안 가진 쪽이 **전부** 반대 답」을 요구했다(`isdisjoint`). 그래서 실제로
        #   눈에 보이는 한쪽 단서를 놓쳤다 — 어느 시험지는 한 틀이 여섯 문항에 있고 그 여섯이
        #   전부 거짓인데, 틀을 안 쓴 넷에 거짓이 섞여 있어 통과했다. **틀을 보면 거짓을 찍어
        #   여섯을 다 맞히는데도** 자가 0건을 냈다. 조건을 「한쪽으로만 맞는 단서」로 낮춘다.
        if len(inside) == 1 and (not next(iter(inside))) in set(answers.values()):
            hits.append((len(owners), g))
    if not hits:
        return []
    hits.sort(reverse=True)
    n, g = hits[0]
    return [(chapter_name, "O/X %d문항" % len(ox),
             "문형만 보고 맞힐 수 있다 — %r 이 든 %d문항이 전부 같은 답이고 나머지는 반대다"
             " (같은 꼴 조각 %d개)" % (g, n, len(hits)))]


# ★ 한쪽 답이 이 몫을 넘으면 **찍기가 값을 한다.** +5/−5/0 채점에서 열 문항 중 여덟이 한쪽이면
#   전부 그쪽으로 찍어 (8−2)×5 = 30점, 만점 50점의 60 % 다. 일곱이면 20점(40 %)으로 절반 아래다.
#   그래서 문턱을 0.70 에 둔다 — 고른 값이고, 견준 것은 「찍기가 절반을 넘느냐」다.
OX_MAJORITY_MAX = 0.70


def check_ox_answer_balance(chapter, chapter_name):
    r"""**O/X 답이 한쪽으로 쏠려 「전부 같은 답」 찍기가 값을 하는 자리** — 후보만 낸다.

    열린 날 2026-09-08. 문형 단서를 쫓다가 더 단순한 것이 먼저 걸렸다 — 어느 시험지는
    열 문항 중 **여덟이 거짓**이라 지문을 한 줄도 안 읽고 전부 거짓으로 찍으면 60 % 를 받는다.
    문형이든 길이든 그 위에 얹히는 단서이고, 쏠림은 **바닥**이다.

    ☐ 못 보는 것: 문항 수가 적으면(넷~다섯) 3:2 도 0.60 이라 안 걸린다 — 그 크기에서는
      쏠림 자체가 뜻을 갖기 어렵다고 보고 넘긴다.
    """
    ox = [q for q in (chapter.get("problems") or [])
          if isinstance(q, dict) and isinstance(q.get("oxCorrect"), bool)]
    if len(ox) < 4:
        return []
    yes = sum(1 for q in ox if q["oxCorrect"])
    share = max(yes, len(ox) - yes) / len(ox)
    if share <= OX_MAJORITY_MAX:
        return []
    return [(chapter_name, "O/X %d문항" % len(ox),
             "답이 한쪽으로 쏠렸다 — 참 %d · 거짓 %d (%.0f %%, 상한 %.0f %%). 전부 한쪽으로 찍는 것이 값을 한다"
             % (yes, len(ox) - yes, share * 100, OX_MAJORITY_MAX * 100))]


# ── 글이 화면 배치를 가리킨다 ─────────────────────────────────────────────────
#
# 열린 날 **2026-07-27**(공용 폴더 원장). 지적은 *[발화 생략]* 였고, 부류로 «레이아웃이 바뀌면 즉시 틀리는 서술»이라고 적힌 채
# **[대기]** 로 44일을 있었다 — 기계 방지장치가 없어서 그동안 새 콘텐츠가 계속 같은 문장을
# 만들었다(2026-09-09 사용자: *[발화 생략]*). 이 검사가 그 자리를 닫는다.
#
# ★ 판정선 — **위치어로 다른 카드·탭·화면 영역을 가리키면 위반**이다.
#   · 위반: `아래 카드` · `위 카드` · `다음 카드` · `아래 유도` · `오른쪽 유도` · `아래 문풀`
#           · `아래 절에서` · 카드를 가리키는 `아래에 있습니다` · `바로 아래`
#   · 허용 ⑴ **이름으로 가리키기** — `유도에서 다룹니다` · `3절에서` · `[[chNN:앵커|문구]]`.
#     이름은 레이아웃이 바뀌어도 안 틀린다.
#   · 허용 ⑵ **한 삽화 SVG 안에서 그 그림의 패널을 가리키는 것**(`왼쪽 패널`) — 그림 안
#     좌표는 안 바뀐다. 그래서 `svg` 키는 아예 안 본다.
#   · 허용 ⑶ **같은 `content` 문자열 안에서 바로 다음에 오는 표·목록·식** — 본문은 한 흐름이라
#     순서가 안 바뀐다. 뒤에 실제로 그 블록이 붙어 있을 때만 봐준다.
#
# ★★ **애매하면 위반 쪽으로 센다.** 화이트리스트로 짜면 새 표현이 조용히 샌다(이 리포가
#   「모르는 필드는 세는 쪽이 기본값」으로 이미 닫은 부류다). 확신이 안 서는 것은 빼지 않고
#   사유에 `[판정 필요]` 를 붙여 목록에 남긴다.
#
# ☐ **이 자가 못 보는 것:** ⑴ 위치어 없이 배치를 전제하는 말(«옆에 나란히 놓인») ⑵ 영어
#   지문의 `below`·`above` ⑶ 삽화 안 글자(허용 ⑵의 대가다 — 그 안에서 **다른 카드**를
#   가리켜도 못 잡는다) ⑷ 조사 없이 홑으로 선 대상어(`아래 카드 참고` 꼴).
#
# ★★★ **첫 판은 재는 것이 아니라 자를 재는 것이었다**(규칙 21). 세 가지를 넣었다가 뺐거나
#   좁혔다 — 다시 넣으려는 사람이 먼저 읽을 자리다.
#
#   ⑴ **홑 동사꼴 `아래에 있다`·`위에 있다` 를 방아쇠로 넣었다가 뺐다.** 실측한 58건이
#      **전부 물리·기하 서술**이었다 — 「세 점이 한 직선 **위에 있으면**」·「무게중심이
#      부력중심보다 **아래에 있으면**」·「극점이 실수축 **왼쪽에 있는**」. 화면을 가리킨 것은
#      한 건도 없었다. → **대상어가 앞에 선 꼴**(`유도는 아래에 있습니다`)만 본다.
#   ⑵ **`다음 절`·`다음 단계` 를 위반으로 셌다가 뺐다.** 순서말은 화면 위치가 아니라 **읽는
#      차례**를 가리키므로 배치가 바뀌어도 안 틀린다. 실측 20여 건이 전부 그 꼴이었다.
#      → 순서말(`다음`·`이전`)은 **카드·탭류에만** 건다(`다음 카드` 는 여전히 위반이다).
#   ⑶ **`단계`·`내용`·`설명`·`문단`·`항목`·`박스` 를 대상어에서 뺐다.** 「상**위 단계**」·
#      「그 **위 단계**(국가 표준)」처럼 **계층**을 뜻하는 자리가 압도적이라 자가 뜻을 못 가른다.
SD_SPATIAL = r"아래|아랫|밑|위|윗|오른쪽|왼쪽|우측|좌측|상단|하단"
# ㉮ 카드·탭류 — 「거기로 가서 봐야 하는 것」. 순서말(`다음`)로 가리켜도 위반이다.
#   ★ `영역` 은 뺐다 — 실측 1건이 1건 다 오탐이었다(*[발화 생략]* 은 선도
#     위의 물리적 영역이다). 자를 재고 뺀 셋째 자리다.
SD_TARGET_CARD = r"카드|탭|유도|문풀|연습문제|화면|패널|그림|삽화"
# ㉯ 절 — 읽는 차례가 정해져 있어 **순서말은 정상**이고, **위치어만** 위반이다.
#   ★ `문제`·`문항` 은 뺐다 — 남은 실측 1건이 오탐이었다(*[발화 생략]* — 평면 **위**의 문제다). 자를 재고 뺀 넷째 자리다.
SD_TARGET_SECTION = r"절|섹션"
# ㉰ 본문 흐름 안 블록 — 위치어로 가리켜도 그 블록이 **같은 문자열 안 바로 옆**에 있으면
#    허용 ⑶ 이다. 못 찾으면 지우지 않고 `[판정 필요]` 로 남긴다.
SD_TARGET_FLOW = r"표|목록|식"
# 대상어 뒤에 와도 되는 것 — 조사이거나 한글이 아닌 것. 이게 없으면 `왼쪽 절반` 의 `절`,
# `상위 단계` 의 `위` 처럼 **낱말 한가운데**를 잘라 읽는다(첫 판의 실제 오탐이다).
SD_TAIL = r"(?=[^가-힣]|을|를|은|는|이|가|에|의|와|과|로|으|도|만|부|까|보|처|랑|$)"
# 위치어 앞이 한글이면 `상위`·`하위`·`범위`·`주위` 의 꼬리를 잡은 것이다.
SD_HEAD = r"(?<![가-힣])"
SD_RE = re.compile(
    SD_HEAD
    + r"(?:(?:바로\s*)?(?:" + SD_SPATIAL + r")\s*(?:쪽)?\s*(?:의\s*)?(?:"
    + SD_TARGET_CARD + r"|" + SD_TARGET_SECTION + r"|" + SD_TARGET_FLOW + r")" + SD_TAIL
    + r"|(?:다음|이전)\s*(?:의\s*)?(?:" + SD_TARGET_CARD + r")" + SD_TAIL
    + r"|(?:" + SD_TARGET_CARD + r"|증명|풀이)[는은이가도]?\s*(?:바로\s*)?(?:"
    + SD_SPATIAL + r")\s*(?:쪽)?(?:에|에서|에는)\s*"
    + r"(?:있|나옵|나온|나와|다룹|다뤘|정리|이어|보입|적어|적었|실려|실었))")
# 허용 ⑶ 을 인정할 「바로 옆 블록」 — 마크다운 표·목록·번호목록·디스플레이 수식.
SD_BLOCK_NEAR = re.compile(r"\n\s*(?:\||[-*+]\s|\d+\.\s|\$\$|\\\\\(|\\\()")
# 그 블록이 「바로」 옆인지 재는 창. **고른 값이다** — 한 문단(대략 150자)이 사이에 들어가면
# 「바로 옆」이라 부르기 어렵다고 보고 그 두 배를 창으로 잡았다.
SD_BLOCK_WINDOW = 300
# 뒤를 가리키는 말인가 앞을 가리키는 말인가 — 「위 식」은 **앞쪽**, 「아래 표」는 **뒤쪽**을
# 본다. 방향을 안 가리면 「위 표」가 뒤에 있는 남의 표를 근거로 통과한다.
SD_BACKWARD = re.compile(r"^(?:위|윗|상단|앞)")
# 삽화 안 글자는 허용 ⑵ 라 아예 안 본다. 저자 전용 필드는 독자에게 안 보인다.
SD_SKIP_KEYS = frozenset(("svg",)) | frozenset(AUTHOR_ONLY)
SD_FLOW_TAIL_RE = re.compile(r"(?:" + SD_TARGET_FLOW + r")$")


def screen_deixis_hits(text):
    """한 문자열에서 화면 배치를 가리키는 자리 — `(맞은 말, 판정필요인가)` 목록. 순수 함수.

    테스트가 이 함수를 직접 부른다(챕터 JSON 을 짓지 않고 문장 하나로 잴 수 있게).
    """
    text = text or ""
    out = []
    for m in SD_RE.finditer(text):
        flow_only = SD_FLOW_TAIL_RE.search(m.group(0))
        if flow_only:
            if SD_BACKWARD.search(m.group(0)):
                window = text[max(0, m.start() - SD_BLOCK_WINDOW):m.start()]
            else:
                window = text[m.end():m.end() + SD_BLOCK_WINDOW]
            if SD_BLOCK_NEAR.search(window):
                continue                    # 허용 ⑶ — 같은 흐름의 바로 옆 블록이다
        out.append((m.group(0), bool(flow_only)))
    return out


def check_screen_deixis(chapter, chapter_name):
    """본문이 **위치어로 다른 카드·탭·화면 영역을 가리키는** 자리 — 위 블록 주석이 정본."""
    hits = []

    def walk(node, owner, item_id, field):
        if isinstance(node, str):
            for phrase, needs_verdict in screen_deixis_hits(node):
                hits.append((chapter_name, str(item_id),
                             owner + "/" + field + " " + repr(phrase)
                             + " — 위치어가 화면 배치를 가리킨다(이름으로 바꾸거나 지운다)"
                             + ("  ← [판정 필요] 같은 문단의 표·목록일 수 있다"
                                if needs_verdict else "")))
        elif isinstance(node, dict):
            for k, v in node.items():
                if k in SD_SKIP_KEYS:
                    continue
                walk(v, owner, item_id, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, owner, item_id, field)

    for item in (chapter.get("theory") or {}).get("sections") or []:
        walk(item, "theory", item.get("id", "?"), "?")
    for item in (chapter.get("derivation") or {}).get("formulas") or []:
        walk(item, "derivation", item.get("id", "?"), "?")
    for item in chapter.get("practice") or []:
        walk(item, "practice", item.get("id", "?"), "?")
    for item in chapter.get("problems") or []:
        walk(item, "problems", item.get("id", "?"), "?")
    for key in ("intro", "overview", "summary", "objectives", "previousReview"):
        if key in chapter:
            walk(chapter[key], key, key, "?")
    return hits


_CORRESPONDENCE = re.compile(r"(?:는|은)\s+[^,.。]{1,20}(?:,|입니다)")
# 줄바꿈도 문장 경계로 본다 — 본문은 문단마다 줄을 바꾸고 한 문장이 줄을 안 넘는다.
# ★ 이걸 빼 뒀더니 디스플레이 수식 줄과 그 뒤의 「여기서 …」가 **한 문장으로 붙어**
#   아래 기호-풀이 제외가 통째로 안 걸렸다(2026-09-10 이 자의 두 번째 검정).
_SENTENCE_SPLIT = re.compile(r"(?<=니다)[.]|\n|(?<=\.)\s")
# 이미 블록인 줄 — 표·불릿·번호는 「산문에 이어 붙였다」의 대상이 아니다.
_ALREADY_A_BLOCK = re.compile(r"\s*(?:\||[-*]\s|⑴|⑵|⑶|⑷|⑸|\d+\.\s)")
# 「여기서 X는 …, Y는 …」 — 디스플레이 수식 뒤의 **기호 풀이**는 다른 갈래다.
# 유도 카드에서는 `variables` 사전이 이미 표로 렌더하고, 이론 본문의 그 관용구는
# 항목마다 한 낱말이라 표로 옮겨도 읽는 부담이 안 준다. 첫 실행에서 121건 중 40% 가까이가
# 이 꼴이었고, 섞어 두면 **진짜 후보가 묻힌다**(2026-09-10 이 자의 검정).
_SYMBOL_GLOSS = re.compile(r"^(?:\*\*)?여기서\b")


def check_prose_correspondence(chapter, chapter_name):
    r"""**대응 셋 이상을 한 문장에 이어 붙인 자리** — 표로 뺄 후보만 낸다.

    열린 날 2026-09-10. 사용자가 문풀 지문이 길어 «부담감 느껴서 안하게 된다» 고 한 뒤,
    이론 쪽에서도 같은 느낌이라며 공학수학 2 의 「직교·수직·법선」 카드를 함께 짚었다.

    ★ **길이로 재면 못 잡는다** — 이 자를 만들기 전에 먼저 재 봤다. 전 과목 pitfall `note`
      877건 중 200자를 넘는 것은 55건(약 6%)인데, **사용자가 짚은 그 카드는 170자로 한복판에
      있었다.** 즉 부담의 축은 길이가 아니라 **꼴**이다 — 「A는 X, B는 Y, C는 Z입니다」처럼
      대응 셋을 한 문장에 이어 붙이면 독자가 세 짝을 머리에 동시에 얹어야 한다. 같은 내용을
      2열 표로 옮기면 눈이 한 줄씩 짚는다(AGENTS 실행 규율 20 「표가 산문보다 싸다」).

    판정선: **한 문장 안에 «…는/은 …,» 꼴의 대응이 셋 이상**이면 후보.

    ☐ **사람이 판정한다 — 이 자는 세기만 한다.** 대응이 아니라 그냥 쉼표로 이어진 서술도
      걸린다(「전위는 위치의 값이라, …」 같은 꼴이 한 문장에 셋 모이면 오탐이다).
      표로 옮길지는 «세 짝이 서로 같은 틀인가» 로 사람이 가른다.
    ☐ 대상은 `content`·`note` 두 필드뿐이다. 문항 지문은 램프(C54)가 따로 본다.
    """
    hits = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("content", "note") and isinstance(v, str):
                    # ★ 표 줄은 빼고 센다 — **이미 표인 것**을 「표로 빼라」고 신고하던 자리다
                    #   (2026-09-10 이 자의 첫 실행에서 바로 걸렸다: 3건 중 1건이 그 오탐).
                    body = "\n".join(ln for ln in v.split("\n")
                                     if not _ALREADY_A_BLOCK.match(ln))
                    for sent in _SENTENCE_SPLIT.split(body):
                        if _SYMBOL_GLOSS.match(sent.strip()):
                            continue
                        n = len(_CORRESPONDENCE.findall(sent))
                        if n >= 3:
                            hits.append((chapter_name, k,
                                         "대응 %d 개가 한 문장에 있다 — 2열 표로 뺄 후보: %s"
                                         % (n, sent.strip()[:60])))
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(chapter)
    return hits


_TEXT_TAG = re.compile(r"<text\b")
# 문턱이 아니라 **관측선**이다 — 이 수를 넘으면 목록에 올려 사람이 본다.
# 12 로 잡은 근거: 사용자가 나쁜 예로 든 교재 슬라이드가 **20개 남짓**이고, 우리 쪽에서
# 사용자가 좋다고 본 그림(`fig-11-transform-slide` 한 프레임)이 **넷 안팎**이다.
# 그 사이를 절반으로 갈랐다. 첫 실측을 보고 옮긴다.
LABEL_CROWD_WATCH = 12


def check_label_crowding(chapter, chapter_name):
    r"""**한 그림에 라벨을 몰아넣은 자리** — 단계로 갈랐어야 할 후보만 낸다.

    열린 날 2026-09-10. 사용자가 **교재 슬라이드 한 장을 나쁜 예로 들고 왔다** — 모어원 하나에
    σ1·σ2·σx·σy·σaver·τxy·τx1y1·2θ·2θp1·β·A·B·D·D'·P1·P2·S1·S2 와 치수선 다섯이 **한꺼번에**
    올라가 있다. 원문:
    *[발화 생략]*.

    ★ **경보 피로와 같은 부류다.** 이 리포는 검사기에서 이미 그 교훈을 얻었다 — 한 번에 다
      켜면 사람이 아무것도 안 본다. 그림도 같다. 그래서 슬라이드 모드가 있는 것이고,
      **정적 삽화에도 같은 상한이 있어야 한다.**

    ☐ **문턱을 아직 안 정했다.** 먼저 분포를 본다(규율 17: 재는 자를 만들고 문턱을 같이
      정하되, 못 정하면 그 사실을 적어 둔다). 지금은 상위 후보만 나열한다.
    ☐ **이 자가 못 보는 것 — 슬라이드의 프레임.** `show` 로 갈라 놓은 그림은 화면에서 한
      단계에 일부만 뜨는데 이 자는 **전체 글자 수**를 센다. 그래서 슬라이드 삽화는 실제보다
      붐비게 나온다. 프레임별로 세려면 `show` 목록을 펴야 하고, 그건 빌드가 이미 하는 일이라
      옮겨 오기 전에는 여기서 흉내 내지 않는다.
    """
    hits = []

    def walk(node, owner):
        if isinstance(node, dict):
            fid = node.get("id")
            svg = node.get("svg")
            if isinstance(svg, str) and svg.lstrip().startswith("<svg"):
                n = len(_TEXT_TAG.findall(svg))
                if n >= LABEL_CROWD_WATCH:
                    hits.append((chapter_name, str(fid or owner),
                                 "글자 요소 %d개 — 단계로 가를 후보" % n))
            for k, v in node.items():
                walk(v, fid or owner)
        elif isinstance(node, list):
            for v in node:
                walk(v, owner)

    walk(chapter, chapter_name)
    return hits


_DRAW_VERB = re.compile(
    r"(?:그립니다|그린다|그어|긋습니다|긋는다|표시합니다|표시한다|잇습니다|잇는다"
    r"|찍습니다|찍는다|내립니다|내린다|이어 그린)")
# 관측선 — 한 자리에 작도 동작이 이만큼 있으면 그건 **작도 절차**다.
# 3 으로 잡은 근거: 사용자가 나쁜 예로 든 교재 슬라이드가 [발화 생략] **여섯**이고,
# 우리 본문에서 한두 번 나오는 것은 서술이지 절차가 아니다. 첫 실측을 보고 옮긴다.
DRAW_STEPS_WATCH = 3


def check_drawing_without_figure(chapter, chapter_name):
    r"""**「그리는 법」을 적어 놓고 그림이 없는 자리** — 후보만 낸다.

    열린 날 2026-09-10. 사용자가 교재 슬라이드 [발화 생략]를 두 번째
    나쁜 예로 들고 왔다 — *[발화 생략]*. 그 장은 축을 그리고 C·A·B 를 찍고 선을 잇고 원을 그리라고 여섯 줄로
    적어 두고 **그림을 한 장도 안 보여 준다.**

    ★ **앞 검사(`label-crowding`)와 한 쌍이다.** 하나는 한 프레임에 다 몰아넣은 것이고
      이쪽은 아예 안 그린 것이다. 둘 사이의 답이 슬라이드 모드 — **한 단계에 한 획**이다.

    판정선: 한 절·한 카드의 글에 작도 동작이 **셋 이상**인데 그 자리에 삽화가 없으면 후보.

    ☐ **이 자가 못 보는 것:** 「그린다」가 비유인 자리(«그래프를 머릿속에 그린다»)와,
      옆 절의 삽화가 이미 그 작도를 보여 주는 경우. 판정은 사람이 한다.
    """
    hits = []

    def has_figure(node):
        if node.get("figure"):
            return True
        return bool(node.get("diagrams"))

    def text_of(node):
        parts = []
        if isinstance(node.get("content"), str):
            parts.append(node["content"])
        for st in (node.get("derivationSteps") or []):
            if isinstance(st, dict) and isinstance(st.get("text"), str):
                parts.append(st["text"])
        return "\n".join(parts)

    def walk(node, owner):
        if isinstance(node, dict):
            body = text_of(node)
            if body:
                n = len(_DRAW_VERB.findall(body))
                if n >= DRAW_STEPS_WATCH and not has_figure(node):
                    hits.append((chapter_name, str(node.get("id") or owner),
                                 "작도 동작 %d개인데 삽화가 없다 — 한 단계에 한 획으로 그릴 후보" % n))
            for k, v in node.items():
                walk(v, node.get("id") or owner)
        elif isinstance(node, list):
            for v in node:
                walk(v, owner)

    walk(chapter, chapter_name)
    return hits


# 계산기를 부르는 자국 셋. **값이 틀렸는지가 아니라 손이 멈추는지**를 잰다.
#   ⑴ 손으로 값이 안 나오는 **각의 삼각함수** — 표나 계산기를 열어야 한다
#   ⑵ 소수의 유효숫자 셋 이상 — 0.6428 은 읽어 온 값, 2.25 는 손이 멈추는 곱이다(2026-09-17 넷→셋)
#   ⑶ 로그·지수 — 손으로 못 낸다
#
# ★★ **첫 실행이 이 세 정규식을 고쳤다 (규칙 21 — 첫 출력은 자의 검정이다).** 21과목 실측에서
#   나온 것 셋이 전부 오탐이었다:
#   ⑴ 「펜으로 안 되는 각 2도」 — `\cos 2\theta` 의 **계수 2** 를 각으로 읽었다. 각인지 아닌지는
#      **도 표시**(°·도·`^\circ`)가 가른다. → 도 표시를 요구한다.
#   ⑵ 「소수 넷째 자리 0.0200」 — 뒤에 붙은 0 까지 자릿수로 셌다. 0.02 는 펜으로 되는 수다.
#      → 뒤쪽 0 을 떼고 센다.
#   ⑶ 「근호」 — `\sqrt{4}` 는 펜으로 되고 `\sqrt{4.7}` 은 안 되는데 자국이 같다. 이 리포는
#      합응력·반지름에서 근호를 늘 쓰므로 그대로 두면 30건 넘게 울리고 그게 곧 경보 피로다.
#      → **근호는 트리거에서 뺀다.** 아래 「못 보는 것」에 적어 사람이 본다.
_CALC_ANGLE = re.compile(
    r"\\?(?:cos|sin|tan)\s*\{?\s*(\d{1,3}(?:\.\d+)?)\s*\}?\s*(?:°|도\b|\^\{?\\circ)")
_CALC_DECIMALS = re.compile(r"\d+\.\d+")
# 소수의 유효숫자(앞뒤 0 을 뗀 자릿수)가 이만큼이면 후보. 셋으로 고른 근거: 합격 20 mA × 100 s
# = 2(하나) · 불합격 0.025 × 90 = 2.25(셋, 사용자 지적 2026-09-16) 사이의 가장 낮은 칸이다.
CALC_SIG_DIGITS = 3
_CALC_FUNCS = re.compile(r"\\(?:log|ln|exp)\b|\^\{?\s*0?\.\d")
# 손으로 값이 나오는 각(도). 2θ 로 들어가는 자리까지 함께 본다.
PEN_ANGLES = {0, 30, 45, 60, 90, 120, 135, 150, 180, 270, 360}
# 문항이 이 키로 사유를 적으면 이 검사에서 빠진다(`lintWaivers` 안에 둔다).
CALC_WAIVER_KEY = "calculator-free-first-rung"
# 분모 — 본 basic 문항 수와 그중 면제로 빠진 수(main 이 합계 밑에 찍는다).
CALC_SEEN = {"basic": 0, "waived": 0}


def check_calculator_free_first_rung(chapter, chapter_name):
    r"""**1회차 딸깍 문항이 계산기 없이 펜으로 풀리는가** — 후보만 낸다.

    열린 날 2026-09-10. 사용자가 응용고체 수업에서 푼 교재 Example 11-6 을 좋은 예로 들고
    왔다 — *[발화 생략]*.
    그 예제는 θ 를 45도로 잡아 2θ 가 90도가 되고, 코사인 항이 통째로 사라져 뺄셈 두 번으로
    끝난다. 우리 쪽 같은 자리(`ch11-p01`)는 25도라 cos 50°·sin 50° 를 읽어 와야 했다.

    ★ **왜 이것이 1회차의 문제인가.** 1회차 딸깍은 「식을 아는가」를 묻는 자리다. 거기에
      계산기가 끼면 묻는 것이 「계산기를 두들기는가」로 바뀌고, 문풀에 손대는 문턱이 그만큼
      높아진다 — 램프 칸 1 을 만든 이유(*[발화 생략]*)와
      같은 부류다. 램프가 **지문의 부담**을 낮췄다면 이쪽은 **손의 부담**이다.

    판정선: `difficulty: basic` 인 문풀 항목의 풀이·답·힌트에 위 세 자국 중 하나라도 있으면 후보.
    소수 문턱은 유효숫자 **셋**(2026-09-17, 사용자 *[발화 생략]*) — 넷일 때
    전기전자 `ch01-p02` 의 0.025 × 90 = 2.25 가 새어 나갔다. 합격 대조 20 mA × 100 s = 2.
    셋이면 곱셈 하나로 나오는 0.0144 도 걸리는데, 그런 판정은 자를 넓히지 않고 면제 사유로 닫는다.

    ☐ **이 자가 못 보는 것:** ⑴ **정수끼리의** 안 깔끔한 곱셈·나눗셈(`287 × 53` 은 소수가
      없어 안 걸린다)과 풀이에 적히지 않은 중간 곱 — 소수 유효숫자 셋 이상인 값만 본다.
      **풀이틀·힌트·지문 안의 곱은 안 본다** — 유효숫자는 답 칸(blank `answer`·`expectedOutput`)
      에서만 센다(상수·표 값 오탐을 끊으려고 좁혔다). 답이 깔끔한데 중간 곱이 안 깔끔하면 샌다
      ⑵ 표를 열어야 하는 물성값(증기표·공기표) —
      그건 오픈북 훈련이라 일부러 두는 자리다 ⑶ **근호** — `\sqrt{4}` 와 `\sqrt{4.7}` 이
      같은 자국이라 트리거에서 뺐다(위 상수 주석) ⑷ 로그가 **계산이 아니라 주제**인 문항
      (복소 로그의 주계값 같은 자리). 판정은 사람이 하고, 판정한 것은 아래 면제로 닫는다.

    ★ **닫는 법** — 그 문항의 `lintWaivers` 에 사유와 함께 적는다:
      `"lintWaivers": {"calculator-free-first-rung": "표를 여는 것이 이 문항의 훈련이다"}`.
      사유가 빈 줄은 면제가 아니다(이 리포의 다른 면제와 같은 규율).
    """
    hits = []
    for item in (chapter.get("practice") or []):
        if not isinstance(item, dict) or item.get("difficulty") != "basic":
            continue
        CALC_SEEN["basic"] += 1
        # ★★ **판정을 데이터에 남긴다** (2026-09-10, 첫 전수 판정에서 39건 중 다수가 오탐이었다).
        #   자를 더 조이는 것으로는 안 닫히는 자리가 있다 — 표를 여는 것이 일부러 둔 훈련인
        #   문항, 곱셈 하나로 나오는 네 자리 수, 로그가 계산이 아니라 **주제**인 문항.
        #   그런 것을 매번 다시 판정하면 목록이 잡음에 덮여 진짜가 안 보인다(경보 피로).
        #   그래서 이미 있는 면제 장치(`lintWaivers`)를 그대로 쓴다 — **사유 없는 줄은 면제가
        #   아니고**, 닫은 사유가 데이터에 남아 다음 사람이 읽는다.
        waived = (item.get("lintWaivers") or {}).get(CALC_WAIVER_KEY)
        if isinstance(waived, str) and waived.strip():
            CALC_SEEN["waived"] += 1
            continue
        parts = [str(item.get("solutionTemplate") or "")]
        answers = [str(item.get("expectedOutput") or "")]
        for b in (item.get("blanks") or []):
            if isinstance(b, dict):
                parts += [str(b.get("hint") or ""), str(b.get("answer") or "")]
                answers.append(str(b.get("answer") or ""))
        body = "\n".join(parts)
        answer_text = "\n".join(answers)
        why = []
        odd = sorted({a for a in _CALC_ANGLE.findall(body)
                      if float(a) % 1 or int(float(a)) not in PEN_ANGLES})
        if odd:
            why.append("펜으로 안 되는 각 " + ", ".join(odd) + "도")
        # ★★ **소수 자릿수가 아니라 유효숫자로 센다** (셋째 교정 2026-09-10). 뒤에 붙은 0 을
        #   떼는 것만으로는 모자랐다 — `0.00160`(= 1.6 mm) 이 「소수 넷째 자리」로 걸렸는데,
        #   유효숫자로는 둘뿐이라 펜으로 나오는 수다. 앞뒤의 0 을 다 떼고 남는 자릿수가
        #   문턱 이상일 때만 후보로 본다(0.0016 은 둘이라 안 걸린다).
        # ★★ 문턱 넷 → 셋 (넷째 교정 2026-09-17). `ch01-p02` 의 0.025 × 90 = 2.25 가 넷 문턱과
        #   「소수 넷째 자리」 정규식 둘 다를 빠져나갔다 — 단위 환산 뒤 세 자리 곱은 손이 멈춘다.
        #   셋이면 0.0144 · 0.1152 같은 「곱셈 하나로 나오는」 수도 걸린다. 그건 자를 다시
        #   넓히지 않고 `lintWaivers` 사유로 닫는다(판정은 데이터에 남는다).
        # ★ 유효숫자는 **답 칸만** 본다(blank answer · expectedOutput, 2026-09-17 판정 세션).
        #   풀이틀·힌트까지 보던 셋 문턱 첫 재셈이 basic 457 중 168 — 9.81 · 273.15 같은 상수와
        #   표 값이 풀이틀에 살아서다. 각·로그 자국은 풀이틀에 사니 그대로 body 를 본다.
        deep = sorted({d for d in _CALC_DECIMALS.findall(answer_text)
                       if len(d.replace(".", "").strip("0")) >= CALC_SIG_DIGITS})[:3]
        if deep:
            why.append("유효숫자 셋 이상 " + ", ".join(deep))
        if _CALC_FUNCS.search(body):
            why.append("근호·지수·로그")
        if why:
            hits.append((chapter_name, str(item.get("id") or "?"),
                         "딸깍인데 계산기를 부른다 — " + " · ".join(why)))
    return hits


_CAP_TEXT_RE = re.compile(r"<text[^>]*>(.*?)</text>", re.S)
_CAP_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_CAP_PARTICLE = re.compile(r"(에서|으로|이면|든|은|는|이|가|을|를|과|와|의|도|로|에|만)$")
_SUB_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def _caption_stems(text):
    """낱말을 어간 2글자로 줄인 집합 — 조사·수식 표기·기호를 걷어 본문과 캡션을 같은 자로 잰다."""
    t = re.sub(r"\\\((.*?)\\\)", lambda m: re.sub(r"[\\{}_^]", "", m.group(1)), text)
    t = t.translate(_SUB_DIGITS)
    t = re.sub(r"<[^>]+>|&#\d+;|[*`「」『』()\[\]〈〉,.!?:;—–]", " ", t)
    out = set()
    for w in t.split():
        w = _CAP_PARTICLE.sub("", w)
        if len(w) >= 2:
            out.add(w[:2])
    return out


def check_caption_echo(chapter, chapter_name):
    """**삽화 캡션이 본문 문장을 되풀이하는** 자리 — 후보만 낸다.

    열린 날 2026-09-12. 사용자: *[발화 생략]*. 캡션은 **그림이 더하는 것**(어느 선이 무엇인지 ·
    화면 각도의 뜻)을 적는 자리이고, 본문 명제를 다시 적으면 같은 화면에서 세 번 읽힌다.
    잰다: 이론 절의 각 `<text>` 줄(12자 이상)을 어간 2글자 집합으로 만들어, 그 절 본문의 어느
    한 문장에 60% 이상 포함되면 후보(어간 4개 이상일 때만). 문턱은 아는 결함(공학수학 2 ch07
    평면 법선 삽화 78%·60%)과 아는 정상(같은 절 직선 삽화의 「O 는 아무 데나 잡은 원점」 0%)
    둘로 재 골랐다. 못 본다: 뜻은 같은데 낱말이 다른 되풀이 · 문풀·연습문제 삽화(본문이 없다).
    """
    hits = []
    for sec in (chapter.get("theory") or {}).get("sections") or []:
        sents = [(s, _caption_stems(s)) for s in _CAP_SENT_SPLIT.split(sec.get("content") or "")
                 if len(s) >= 12]
        for d in sec.get("diagrams") or []:
            for raw in _CAP_TEXT_RE.findall(d.get("svg") or ""):
                cap = re.sub(r"<[^>]+>", "", raw).strip()
                stems = _caption_stems(cap)
                if len(cap) < 12 or len(stems) < 4:
                    continue
                for sent, sb in sents:
                    score = len(stems & sb) / len(stems)
                    if score >= 0.6:
                        hits.append((chapter_name, d.get("id", "?"),
                                     "캡션 «" + cap[:36] + "» 이 본문 문장과 " + str(round(score * 100))
                                     + "% 겹친다 — 그림이 더하는 것만 남길 후보: «" + sent[:36] + "»"))
                        break
    return hits


_SENT_SPLIT = re.compile(r"(?<=[.!?다요])\s+|\\n")
_RATIO_WORD = re.compile(r"효율|성능계수|COP|비\s*\(|분율")
_AMOUNT_CMP = re.compile(r"(더 많이|더 크게|훨씬 많이)\s*(줄|늘|커|작아)")
_ASIDE = re.compile(r"마지막으로[^.。\n]{0,20}(덧붙|하나를? 붙|곁들|밖의 이야기)")


def _all_strings(node, owner, out):
    if isinstance(node, dict):
        oid = node.get("id") or owner
        for v in node.values():
            _all_strings(v, oid, out)
    elif isinstance(node, list):
        for v in node:
            _all_strings(v, owner, out)
    elif isinstance(node, str):
        out.append((owner, node))
    return out


def check_ratio_by_amount(chapter, chapter_name):
    """**비율인 양(효율·성능계수)의 오르내림을 절대량 비교로 판정한** 문장 — 후보만 낸다.

    열린 날 2026-09-13. 사용자가 가져온 외부 검토: 증기 동력 장 재생 사이클 절의 「일이 줄지만 보일러
    열이 더 많이 줄어 효율이 오른다」 — η = W/Q 에서 효율이 오르는 조건은 ΔW/ΔQ < η, 곧 **감소 비율**의
    비교다. η < 1 이라 입열이 더 많은 **양**만큼 줄어도 효율은 내려갈 수 있다.
    잰다: 한 문장에 효율류 낱말과 「더 많이/더 크게 + 줄·늘」이 함께 있고 「비율」이 없으면 후보.
    첫 실측(고치기 전) 6건이 한 과목 두 장에 몰렸고 전부 참 후보였다(원장 2026-09-13).
    못 본다: 「분모가 더 빨리 준다」 같은 다른 낱말 · 효율 낱말이 앞 문장에만 있는 경우.
    """
    hits = []
    for owner, s in _all_strings(chapter, chapter_name, []):
        for sent in _SENT_SPLIT.split(s):
            if _RATIO_WORD.search(sent) and _AMOUNT_CMP.search(sent) and "비율" not in sent:
                hits.append((chapter_name, str(owner),
                             "비율인 양을 절대량으로 견줬다 — 감소·증가 **비율**의 비교로 쓸 후보: «" + sent[:60] + "»"))
    return hits


def check_tacked_on_aside(chapter, chapter_name):
    """**절 끝에 「마지막으로 … 덧붙입니다」로 붙인 곁가지** — 후보만 낸다.

    열린 날 2026-09-13(같은 외부 검토 — 재생 절 끝의 열병합). 「한 절 한 질문」(content.md 목표
    독자) 위반의 겉 증상이다. 첫 실측 4건이 세 갈래로 갈렸다: 다른 질문 → 절로 뗌 · 다른 절의 되풀이 → 옮김 ·
    같은 질문의 연장 → 예고 문구만 걷음(원장 2026-09-13).
    못 본다: 예고 문구 없이 붙은 곁가지. 판정(뗄지·옮길지·문구만 걷을지)은 사람이 한다.
    """
    hits = []
    for owner, s in _all_strings(chapter, chapter_name, []):
        m = _ASIDE.search(s)
        if m:
            hits.append((chapter_name, str(owner),
                         "절 끝 곁가지 예고 «" + s[m.start():m.start() + 40] + "» — 같은 질문인지부터 판정할 후보"))
    return hits


def check_leader_lands_on_target(chapter, chapter_name):
    """지시선 끝이 이름 붙인 대상에 닿았나 — 후보만 낸다 (열린 날 2026-09-14).

    사용자 재지적: *[발화 생략]*
    (`fig-10-dendrite-growth` — 지시선 끝이 가지 끝과 떨어져 있거나 칸 테두리에 앉았다).
    재는 자는 `checks_svg.leader_target_issues` 하나이고 여기서는 부르기만 한다(규칙 7⑶).
    못 보는 것: `class='leader'` 로 태깅하지 않은 지시선 — 옛 삽화의 `<line>` 한 줄 지시선은
      이 자에 안 잡힌다. 태깅이 먼저다(규격 「지시선」).
    """
    from buildlib import checks_svg as cs
    hits = []
    for fig in figure_balance.iter_diagrams(chapter):
        fid = fig.get("id", "?")
        for msg in cs.leader_target_issues(fid, fig.get("svg") or ""):
            hits.append((chapter_name, fid, msg.split(": ", 1)[-1]))
    return hits


def check_section_example(chapter, chapter_name):
    """이론 절마다 절 예제(ramp 1 문풀)가 있나 — 빌드 C55 와 같은 판정을 전 과목에 돌린다(2026-09-14).

    빌드는 `strictChapters.section_example` 에 올린 장만 막는다. 이 자는 면제 과목까지 훑어
    **아직 못 맞춘 절이 몇 개인가**를 센다 — 면제 사유의 「이 줄을 지운다」가 언제 가능한지 재는 자리.
    """
    from buildlib.checks_content import section_example_issues
    return [(chapter_name, "theory", m) for m in section_example_issues(chapter)]


SECTION_FIT_MARGIN = 0.10   # 고른 값 — 지문 2-gram 의 10%p. 같은 장 이웃 절이 용어를 나눠 쓰므로 0 으로 두면 동점 근처가 다 올라온다. 전 과목 첫 실측 수는 원장 2026-09-14


def _hangul_bigrams(text):
    runs = re.findall(r"[가-힣]{2,}", str(text or ""))
    return {r[i:i + 2] for r in runs for i in range(len(r) - 1)}


def section_example_fit(chapter):
    """[(문항 id, 선언 절, 더 맞는 절, 선언 점수, 최고 점수)] — 순수 함수. 테스트가 직접 부른다.

    재는 것: `section` 을 단 문풀의 지문·빈칸 답 한글 2-gram 중 각 이론 절(표제+본문)에 든 비율.
      다른 절이 선언 절보다 `SECTION_FIT_MARGIN` 이상 높으면 후보.
    왜(2026-09-14 기계공작법 ch10 여섯째 지적 14 — 재발 2회): 「주입 속도」 예제가 3절에 달려 있었고,
      절-예제 짝이 맞는지를 재는 자가 없어 사람 눈에만 걸렸다.
    못 보는 것: 핵심어가 두 절에 고루 퍼진 문항(그때는 점수 차가 작아 안 올라온다 — 그 p07 이 그런 형태라
      이 자로는 못 잡혔을 수 있다) · 낱말이 아니라 개념으로만 이어지는 짝. 판정은 사람이 한다.
    """
    secs = [(s.get("id"), _hangul_bigrams(str(s.get("heading") or "") + " " + str(s.get("content") or "")))
            for s in ((chapter.get("theory") or {}).get("sections") or []) if s.get("id")]
    out = []
    for item in chapter.get("practice") or []:
        want = item.get("section")
        grams = _hangul_bigrams(str(item.get("prompt") or "") + " "
                                + " ".join(str(b.get("answer") or "") for b in item.get("blanks") or []))
        if not want or not grams or want not in dict(secs):
            continue
        score = {sid: len(grams & g) / float(len(grams)) for sid, g in secs}
        best = max(score, key=score.get)
        if best != want and score[best] - score[want] >= SECTION_FIT_MARGIN:
            out.append((item.get("id"), want, best, score[want], score[best]))
    return out


def check_section_example_fit(chapter, chapter_name):
    """문풀의 `section` 이 낱말로 더 가까운 다른 절을 두고 있나 — 후보만 낸다(`section_example_fit`)."""
    return [(chapter_name, pid, "선언 %s %.2f < %s %.2f — 절-예제 짝을 사람이 판정할 후보" % (want, a, best, b))
            for pid, want, best, a, b in section_example_fit(chapter)]


def check_template_echo(chapter, chapter_name):
    """풀이틀이 지문을 다시 묻나(빌드 C56) · 되읊나(후보) — 2026-09-14."""
    from buildlib.checks_content import template_echo_candidates, template_echo_issues
    return [(chapter_name, "practice", m)
            for m in template_echo_issues(chapter) + template_echo_candidates(chapter)]


def check_formula_learning_path(chapter, chapter_name):
    """식/방법 연결표의 부재는 검토 후보이며 콘텐츠 의미의 판정은 아니다."""
    from buildlib.checks_content import formula_learning_path_issues
    formulas = ((chapter.get("derivation") or {}).get("formulas") or [])
    items = (chapter.get("practice") or []) + (chapter.get("problems") or [])
    methods = any(i.get("relatedMethods") for i in items if isinstance(i, dict))
    if items and (formulas or methods) and "formulaLearningPath" not in chapter:
        return [(chapter_name, "theory", "공식 학습 연결표가 없다 — 사람 검토 뒤 formulaLearningPath 로 선언할 후보")]
    return [(chapter_name, "theory", m) for m in formula_learning_path_issues(chapter)]


def check_quote_pair(chapter, chapter_name):
    """짝 안 맞는 따옴표 — 판정은 빌드 C71 의 `quote_pair_issues` 그대로(2026-09-17)."""
    from buildlib.checks_content import quote_pair_issues                  # noqa: E402
    return [(chapter_name, "text", m) for m in quote_pair_issues(chapter)]


def check_literal_newline(chapter, chapter_name):
    """글자 그대로의 `\\n` — 판정은 빌드 C72 의 `literal_newline_issues` 그대로(2026-09-17)."""
    from buildlib.checks_content import literal_newline_issues             # noqa: E402
    return [(chapter_name, "text", m) for m in literal_newline_issues(chapter)]


def check_practice_prompt_language(chapter, chapter_name):
    """화면 「02 예제」·「04 연습」(`practice`)에 영문 지문이 남아 있나 — 후보를 낸다(2026-09-18).

    재는 것: `practice` 항목 `prompt` 의 언어. 자는 새로 만들지 않고 램프·C15 가 쓰는
      `prompt_shape` 를 그대로 부른다(세는 법이 두 벌이면 갈린다).
    문턱: 영문이면 후보 1건. 「05 문제」(`problems`)는 **대상이 아니다** — 시험에서 풀 문항이라
      과목 `promptLanguage` 를 그대로 따른다.
    못 보는 것: 한글 지문에 낀 영문 용어·문장(한글 음절이 하나라도 있으면 ko 로 센다) ·
      풀이틀·빈칸 답의 언어.
    """
    from buildlib.checks_content import prompt_shape                       # noqa: E402
    out = []
    for item in chapter.get("practice") or []:
        if not isinstance(item, dict):
            continue
        if prompt_shape(item.get("prompt"))[0] == "en":
            out.append((chapter_name, "practice[%s]" % (item.get("id") or "?"),
                        "예제·연습 지문이 영문이다 — 한글로 옮기고 `ramp` 1~2 ·"
                        " 항목 `\"promptLanguage\": \"ko\"` 를 단다"))
    return out


def check_expected_echo(chapter, chapter_name):
    """「최종 답」이 빈칸 답을 되읊기만 하나 — 후보(2026-09-18).

    재는 것: `expectedOutput` 의 숫자 토큰이 **전부** 그 문항 `blanks[].answer` 의 숫자 안에 있나.
      하나라도 새 수가 있으면 (a)(b) 를 모으거나 단위를 바꾼 것이라 대상이 아니다.
    문턱: 새 수 0개 + 숫자가 하나 이상. 숫자가 아예 없는 서술형 답은 안 본다(문장 비교가 필요하다).
    왜: 처방은 2026-09-14(여섯째 지적 5)에 이미 나왔고 뷰어는 «비면 안 그린다»까지 됐는데
      **데이터 소급을 안 해** 되읊는 문항이 그대로 남았다. 사용자 재지적 2026-09-18
      *[발화 생략]*.
    못 보는 것: 숫자 없는 서술형 답 · 같은 수를 단위만 바꿔 다시 적은 것(3.3 V ↔ 3300 mV) ·
      빈칸이 중간값이고 최종 답이 그 조합인데 수가 우연히 겹치는 경우(그때는 사람이 되돌린다).
    """
    num = re.compile(r"-?\d+(?:\.\d+)?")
    out = []
    for coll in ("practice", "problems"):
        for item in chapter.get(coll) or []:
            if not isinstance(item, dict):
                continue
            want = num.findall(str(item.get("expectedOutput") or ""))
            if not want:
                continue
            blanks = [b for b in (item.get("blanks") or []) if isinstance(b, dict)]
            have = set()
            for b in blanks:
                have.update(num.findall(str(b.get("answer") or "")))
            if not (have and all(n in have for n in want)):
                continue
            # ★ 두 등급으로 낸다 — 빈칸이 **하나**면 「최종 답」은 그 하나를 다시 적는 것이라
            #   문장을 읽을 것도 없다(확실). 빈칸이 여럿이면 (a)(b) 를 모으거나 조건을 덧붙인
            #   것일 수 있어 **사람이 문장을 읽는다**(2026-09-18 실측: 응용열 ch07 p02·p04 가 그랬다).
            sure = len(blanks) <= 1
            out.append((chapter_name, coll + "[" + str(item.get("id") or "?") + "]",
                        ("[확실 · 빈칸 1개] " if sure else "[판정 · 빈칸 %d개] " % len(blanks))
                        + "「최종 답」이 빈칸 답을 되읊는다 — `expectedOutput` 을 비우면"
                        " 뷰어가 그 줄과 잠금 문구를 둘 다 안 그린다"))
    return out


def check_formula_summary_card(chapter, chapter_name):
    """유도 카드는 있는데 「공식 정리」 카드(`kind: "summary"`)가 없나 — 후보(2026-09-18).

    재는 것: `derivation.formulas[].kind`. 유도가 하나라도 있고 정리가 하나도 없으면 후보 1건.
    왜: 사용자 지적(공수2 ch07 M1) *[발화 생략]*. 그 장에만 넣고 다른 장에 안 갔다(2026-09-18 재지적
      *[발화 생략]*) — 그래서 한 장의 수정이 아니라 자를 둔다.
    못 보는 것: 정리 카드가 **있는데 그 장의 식을 다 안 담은** 경우 · 요약 탭이 대신 담은 경우.
    """
    kinds = [f.get("kind") for f in ((chapter.get("derivation") or {}).get("formulas") or [])
             if isinstance(f, dict)]
    if "derivation" in kinds and "summary" not in kinds:
        return [(chapter_name, "derivation",
                 "유도 %d장뿐이고 공식 정리 카드가 없다 — 그 장의 식을 모은"
                 " `kind: \"summary\"` 카드를 유도 뒤에 둔다" % kinds.count("derivation"))]
    return []


def check_textbook_problems(chapter, chapter_name):
    """화면 「교재 문제」 탭이 비어 있나 — 후보(2026-09-18).

    재는 것: `textbookProblems.items` 의 길이. 비면 뷰어가 탭 자체를 숨긴다.
    왜: 탭은 2026-09-13 에 생겼는데 채운 장이 **공학수학 2 ch07 하나뿐**인 채로 남았다
      (`docs/viewer-change-log.txt` 68행 *[발화 생략]*). 사용자 재지적
      2026-09-18 *[발화 생략]*.
    못 보는 것: 교재 자체가 연습문제를 안 싣는 장(사유를 적을 자리가 과목 쪽에 없으므로 후보로
      올라오면 사람이 가른다) · 번호만 있고 풀이 뼈대가 빈 항목.
    """
    if not ((chapter.get("textbookProblems") or {}).get("items") or []):
        return [(chapter_name, "textbook", "「교재 문제」 탭이 비어 화면에 안 뜬다 —"
                 " 교재 연습문제 번호·답·풀이 뼈대를 채운다(원문은 옮기지 않는다)")]
    return []


FULL_LIST = False        # `--full` 이 켠다 — 화면 상한 12건을 푼다(고치려면 전체가 필요하다)

CHECKS = {
    "practice-prompt-language": check_practice_prompt_language,
    "expected-echo": check_expected_echo,
    "formula-summary-card": check_formula_summary_card,
    "textbook-problems": check_textbook_problems,
    "quote-pair": check_quote_pair,
    "literal-newline": check_literal_newline,
    "formula-learning-path": check_formula_learning_path,
    "leader-lands-on-target": check_leader_lands_on_target,
    "template-echo": check_template_echo,
    "section-example": check_section_example,
    "section-example-fit": check_section_example_fit,
    "ratio-by-amount": check_ratio_by_amount,
    "tacked-on-aside": check_tacked_on_aside,
    "caption-echo": check_caption_echo,
    "calculator-free-first-rung": check_calculator_free_first_rung,
    "drawing-without-figure": check_drawing_without_figure,
    "label-crowding": check_label_crowding,
    "prose-correspondence": check_prose_correspondence,
    "screen-deixis": check_screen_deixis,
    "ox-length-tell": check_ox_length_tell,
    "ox-phrase-tell": check_ox_phrase_tell,
    "ox-answer-balance": check_ox_answer_balance,
    "slide-mode": check_slide_mode,
    "fig-width": check_fig_width,
    "hand-arc": check_hand_drawn_arc,
    "curve-facets": check_curve_facets,
    "arrow-on-outline": check_arrow_on_outline,
    "iso-3d": check_iso_3d,
    "rate-dot": check_rate_dot,
    "deriv-jump": check_derivation_jump,
    "motion-gap": check_motion_gap,
    "term-not-introduced": check_term_not_introduced,
    "geometry-in-formula-only": check_geometry_in_formula_only,
    "figure-carries-the-symbols": check_figure_carries_the_symbols,
}


def main():
    only = None
    which = None
    # ★ **모르는 깃발은 조용히 버리지 않는다** (2026-09-07 실측). `--only 값`(공백 형태)을
    #   주면 `--only=` 접두만 보던 옛 판이 **필터를 통째로 무시하고 21과목을 훑었다** —
    #   화면은 정상이라 그게 한정된 결과인 줄 알았다. 이 리포가 「조용히 한쪽을 버리는
    #   플래그」로 이미 크게 다친 자리다(`--accept-review-only` 사고).
    args, i = sys.argv[1:], 0
    argv = []
    while i < len(args):
        a = args[i]
        if a in ("--only", "--check"):          # 공백 형태 — 다음 인자를 값으로 삼는다
            if i + 1 >= len(args):
                sys.exit(a + " 뒤에 값이 없다")
            argv.append(a + "=" + args[i + 1])
            i += 2
            continue
        argv.append(a)
        i += 1
    if "--steps" in argv:
        SHOW_STEPS.append(True)
        argv = [a for a in argv if a != "--steps"]
    global FULL_LIST
    if "--full" in argv:
        FULL_LIST = True
        argv = [a for a in argv if a != "--full"]
    unknown = [a for a in argv if not a.startswith(("--only=", "--check="))]
    if unknown:
        sys.exit("모르는 인자: " + " ".join(unknown)
                 + "\n쓰는 법 — --only=<과목>,<과목> · --check=<이름>,<이름> · --steps(식 함께 보기)")
    for flag in argv:
        if flag.startswith("--only="):
            only = {s.strip() for s in flag.split("=", 1)[1].split(",") if s.strip()}
        elif flag.startswith("--check="):
            which = {s.strip() for s in flag.split("=", 1)[1].split(",") if s.strip()}

    active = {k: v for k, v in CHECKS.items() if not which or k in which}
    if not active:
        sys.exit("알 수 없는 --check 값 — 후보: " + ", ".join(CHECKS))

    print("규칙 표류 후보 — " + ", ".join(active) + " (판정은 사람이, 이 자는 후보만 낸다)\n")

    total_by_check = {k: 0 for k in active}
    scanned = 0
    for folder in subjects():
        subject = os.path.basename(folder)
        if only and subject not in only:
            continue
        scanned += 1
        CURRENT_FOLDER[:] = [folder]     # term-not-introduced 가 과목 경계를 알아야 한다
        files = chapter_files(folder)
        subject_hits = {k: [] for k in active}
        for name in files:
            ch = blob(os.path.join(folder, name))
            if not ch or ch.get("placeholder") is True:
                continue
            chname = name.rsplit(".", 1)[0]
            for key, fn in active.items():
                subject_hits[key].extend(fn(ch, chname))

        any_hit = any(subject_hits.values())
        if not any_hit:
            continue
        print("-- " + subject + " --")
        for key in active:
            hits = subject_hits[key]
            total_by_check[key] += len(hits)
            if not hits:
                continue
            print("  [" + key + "] " + str(len(hits)) + "건")
            # ★ `--full` — 12건 상한을 푼다(2026-09-18). 상한은 훑어볼 때의 것이고, **고치려면
            #   목록 전체가 있어야 한다** — 12건만 보고 「그게 다」로 읽으면 규칙 11 의 그 함정이다.
            shown = hits if FULL_LIST else hits[:12]
            for chname, item_id, why in shown:
                print("     " + chname + " " + item_id + " — " + why)
            if len(hits) > len(shown):
                print("     ... 외 " + str(len(hits) - len(shown)) + "건 (`--full` 로 전부 본다)")
        print()

    # ★ **훑은 과목 수를 반드시 찍는다** — 0건과 «한 과목도 안 봤다»가 화면에서 같아지던 것이
    #   2026-09-07 에 이 자를 통째로 죽여 놓고도 초록으로 보이게 한 자리다(규칙 11).
    print("합계 — " + " · ".join(k + " " + str(v) + "건" for k, v in total_by_check.items())
          + "  · 훑은 과목 " + str(scanned) + "개")
    if CALC_WAIVER_KEY in active:
        # 분모 — 후보 수만으로는 「basic 을 몇 개 보고 그만큼인가」를 모른다.
        print("  " + CALC_WAIVER_KEY + " 분모 — basic 문항 " + str(CALC_SEEN["basic"])
              + "개 · 그중 면제 " + str(CALC_SEEN["waived"]) + "개")
    if scanned == 0:
        print("★ 훑은 과목이 0개다 — 이 「0건」은 «없다»가 아니라 «못 봤다»이다.")
        return 1
    print("※ 판정하지 않는다 — 순수 대수 유도처럼 그림이 필요 없는 카드도 있고, "
          "640 아닌 폭이 의도적인 삽화도 있을 수 있다. 후보를 사람이 챕터별로 본다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
