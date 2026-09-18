# -*- coding: utf-8 -*-
r"""삽화 캡션이 **그림 밖을 말하는가** — 두 갈래를 세는 감사.

    python tools/audit_figure_caption_scope.py                     # 전 과목
    python tools/audit_figure_caption_scope.py --only=<과목폴더>
    python tools/audit_figure_caption_scope.py data/<과목>/ch02.json
    python tools/audit_figure_caption_scope.py --kind=b --gate     # (B)가 있으면 exit 1

열린 날 2026-09-09. 사용자가 전기전자 ch01 `fig-ee01-quantities` 의 캡션을 보고 두 말을 했다 —
*[발화 생략]* ·
*[발화 생략]*. 한 삽화의 두 결함이 아니라 **두 부류**다:

  (A) **라벨로 옮길 수 있는 것** — 캡션이 「이 기호는 무엇이다」를 말하는데 그 기호가 같은 SVG 안에
      `<text>` 로 있다. 라벨을 `q` → `전하 q` 로 고치면 그 줄이 통째로 사라진다.
  (B) **그림에 객체가 없는 것** — 캡션이 **양과 양을 잇는 규칙**을 말하는데 그 양이 그림에 없다.
      이론 본문·유도의 몫이지 삽화 캡션의 몫이 아니다.

★ **게이트는 (B)만이다.** (A)는 보고만 한다 — 라벨을 다시 쓰면 글자 폭이 바뀌어
  `audit_figure_balance` 의 배치(라벨 간격·중앙 정렬)가 깨진다. 사람이 옮기고 그 자를 다시 돌린다.

★ **캡션 판정을 색·크기로 하지 않는다.** 캡션색 `#6b7280` 으로만 찾으면 열역학·고체역학·기계재료가
  통째로 안 보인다(옛 팔레트가 `#2c3a44`·`#5a6472`·`#5b5f57`·`#6b6558`·`#4a4a44` 로 갈려 있고
  크기도 12~18.5 다). 리포가 이미 쓰는 선을 물려 쓴다 — `audit_figure_balance._hangul_count` /
  `CAPTION_HANGUL_MIN`(=6) 과 `buildlib.checks_svg._svg_texts`. **판정선: 한글 음절 ≥ 6 이고
  굵지 않은 `<text>`.** 수를 여기 다시 적지 않는다(두 자가 갈리면 그게 다음 오탐이다).

★★ **첫 두 실행이 자를 두 번 고쳤다 (규칙 21 — 첫 출력은 결론이 아니라 자의 검정이다).**
  ⑴ 신호에 `…가 …입니다` 를 넣었더니 한 장에서 7건 중 5건이 **그림에 그려진 것을 그대로 말하는
     정상 캡션**이었다. 한국어 평서문은 거의 다 그 꼴이라 그 패턴은 «문장인가»를 물은 것이다.
     → **산술 관계**만 신호로 남겼다.
  ⑵ 그래도 전 과목 132건이었고 대부분이 **범례**("점선 = 질량이 지나감")와 **그 문항의 값**
     ("환경 T₀ = 288 K")과 **주어진·구할 것 칩**("구할 값: … = ?")이었다. 셋 다 `=` 를 쓰지만
     일반 규칙이 아니라 **이 그림의 사실**이라 캡션이 제자리다. → `=` 신호에 세 가지 문턱을 걸었다
     (`_equation_signal` 이 정본).

☐ **이 자가 못 보는 것:**
  ⑴ **라벨 없이 도형으로만 그려진 양** — 화살표 길이가 곧 속도, 칠한 넓이가 곧 전하인 삽화에서는
     캡션이 정당한데도 (B)로 잡힌다. 글자가 아닌 것은 이 자에게 없는 것과 같다.
  ⑵ **`<g font-size>` 상속으로 쪼개진 라벨** — `_svg_texts` 는 `<tspan>` 은 합치지만 `<text>` 를
     여러 개로 나눠 쓴 라벨(`R` 과 `1` 을 따로 놓은 것)은 **두 글자로** 본다. 캡션이 `R₁` 을 말해도
     「그림에 없다」로 오판한다.
  ⑶ **`title`·`aria-label` 은 안 본다** — 그건 그려진 객체가 아니라 그림의 이름이다.
  ⑷ **뜻이 아니라 글자만 본다** — 캡션이 「저항」이라 쓰고 그림에 `R` 만 있으면 「없다」로 센다.
     그래서 (B)는 «캡션이 규칙을 말한다» 는 신호 쪽이 판정의 무게를 지고, 「그림에 없다」는
     **보조 문턱**이다.

제외 — 안 빼면 한 과목에서만 100건 넘게 오탐이 난다:
  ⓐ **좌표가 겹치는 단계 자막** — 유도 카드가 같은 `x`·`y` 에 6~8줄을 쌓아 한 줄씩 보여 준다.
  ⓑ `data-reveal` 이 붙은(또는 조상 `<g>` 에서 물려받은) 단계 텍스트 · `<g class='fig-note'>`.
  ⓒ 문제 삽화의 "직접 …보세요" 류 지시문.
  ⓓ **`derivation` 컬렉션의 삽화는 (B) 대상이 아니다** — 관계식을 말하는 것이 그 카드의 일이다.
     (B)의 처방이 «이론 본문·유도의 몫» 이므로, 유도 카드에서 그것은 제자리에 있는 것이다.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import audit_content                                                        # noqa: E402
from audit_figure_balance import (                                          # noqa: E402
    CAPTION_HANGUL_MIN, _hangul_count, iter_diagrams,
)
from buildlib.checks_svg import _attr, _effective, _svg_texts               # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# 같은 자리에 쌓인 단계 자막인가 — 좌표가 이만큼 안이면 「겹쳤다」로 본다.
STACK_TOL_PX = 1.5

# **관계 신호** — 이것이 없으면 (B) 후보로 올리지 않는다. 캡션이 그림에 없는 낱말을 쓰는 것
# 자체는 정상이다("직렬이라 …"). 문제는 캡션이 **양과 양을 잇는 규칙**을 말할 때다.
DEFINITION_SIGNALS = (
    ("비례", re.compile(r"비례|반비례")),
    ("나눔·곱", re.compile(r"나눈|나누면|나눠|곱한|곱하면|곱해")),
    ("거듭제곱", re.compile(r"제곱|세제곱|네제곱|제곱근")),
    ("배수", re.compile(r"(?:두|세|네|다섯|여러|몇|\d+)\s*배(?:이|입니다|가|로|씩|$|\s)")),
    ("합·차", re.compile(r"합이|더한 (?:것|값)|더하면|뺀 값|차가|차이가")),
    ("단위당", re.compile(r"단위\s*[가-힣]{1,4}당")),
)

# 문제 삽화의 지시문 — 캡션이 아니라 독자에게 시키는 말이다.
INSTRUCTION_RE = re.compile(r"보세요|해 보|풀어|그려 보|채워")

# `=` 왼쪽이 이런 말이면 **범례**다 — 그림의 무엇이 무엇을 뜻하는지 적은 것이라 캡션이 제자리다.
VISUAL_LHS = re.compile(
    r"(?:색|점선|실선|파선|빗금|진한|옅은|주황|파랑|회색|초록|빨강|노랑|보라|검정|하양"
    r"|막대|화살표|기울기|가로축|세로축|원|점|칸|면적|넓이|길이|높이|폭)[^=×÷]{0,8}[=]")

# 조사만 뗀다(어미는 안 뗀다 — 어간을 깎아 없는 말을 만든다).
PARTICLE_RE = re.compile(r"(에서는|으로는|에서|으로|에게|부터|까지|보다|처럼|이나|은|는|이|가"
                         r"|을|를|의|에|와|과|도|만|로|나)$")

# 어느 캡션에나 나오는 말은 「그림에 있나」를 물을 대상이 아니다.
NOUN_STOPWORDS = frozenset("""
그래서 그러면 그리고 하지만 여기서 이렇게 저렇게 이것 저것 그것 때문 경우 자리 부분 정도 만큼
자체 서로 각각 모두 전체 하나 둘씩 사이 방향 위치 크기 모양 상태 결과 이유 의미 관계 기준 조건
비교 확인 계산 사용 표시 아래 위쪽 왼쪽 오른쪽 가운데 안쪽 바깥 다음 먼저 나중 지금 실제 보통
언제 무엇 어디 얼마 우리 이번 이런 저런 그런 같은 다른 새로 다시 항상 절대 반드시 대부분
""".split())

# 기호 토큰 — 낱글자(라틴·그리스)에 아래첨자가 하나 붙을 수 있다.
SYMBOL_RE = re.compile(r"(?<![A-Za-zα-ωΑ-Ω])([A-Za-zα-ωΑ-Ω][₀-₉0-9]?)(?![A-Za-zα-ωΑ-Ω])")
# 단위·접속에 쓰여 기호가 아닌 낱글자.
SYMBOL_STOPWORDS = frozenset(("a", "A", "I", "s"))
HANGUL_RUN_RE = re.compile(r"[가-힣]{2,}")
# 어미 — 이걸로 끝나면 이름씨가 아니라 활용형이다(조사만 떼는 설계의 뒤처리).
VERB_TAIL = ("니다", "습니", "어요", "아요", "해요", "으면", "하면", "되면", "이고", "이며",
             "하고", "하며", "지만", "는데", "면서", "어서", "아서", "려면", "이다", "한다",
             "된다", "았다", "었다", "겠다", "나요", "까요", "라고", "이라", "같이", "거나",
             "든지", "도록", "는지", "은지", "는다", "니라", "해서", "해도", "하지", "되지",
             "지면", "리고", "라서", "므로", "니까", "해야", "되어", "이지", "지고", "리면")


def _is_caption(text):
    """설명 캡션인가 — 굵지 않고 한글 음절이 여러 개면 문장으로 본다.

    판정선은 `audit_figure_balance._is_caption` 과 같다. 다른 것은 굵기를 읽는 자리뿐이다 —
    거기는 태그의 리터럴 `font-weight='700'` 만 보는데, 여기서는 `_svg_texts` 가 이미 조상
    `<g>` 에서 물려받은 굵기까지 담아 준다(`weight`). 값(6)은 임포트한다.
    """
    if str(text.get("weight", "")).strip() in ("700", "800", "900", "bold", "bolder"):
        return False
    return _hangul_count(text["s"]) >= CAPTION_HANGUL_MIN


def _tag_at(svg, pos):
    return svg[pos:svg.find(">", pos) + 1]


def _fig_note_spans(svg):
    """`<g class='fig-note'>` 의 (시작, 끝) — 중첩을 세어 닫는다. 순수 함수."""
    out, stack = [], []
    for t in re.finditer(r"<g\b([^>]*?)(/?)>|</g\s*>", svg, re.S):
        if t.group(0).startswith("</"):
            if stack:
                start, attrs = stack.pop()
                marker = " ".join((_attr(attrs, "id", "") or "",
                                   _attr(attrs, "class", "") or "")).lower()
                if "fig-note" in marker:
                    out.append((start, t.end()))
        elif t.group(2) != "/":
            stack.append((t.start(), t.group(1)))
    return out


def _excluded(svg, text, others, notes):
    """제외할 셋 — 단계 자막(좌표 겹침) · `data-reveal`/`fig-note` · 지시문."""
    tag = _tag_at(svg, text["pos"])
    attrs = tag[len("<text"):-1]
    if _effective(svg, text["pos"], attrs, "data-reveal") is not None:
        return "data-reveal"
    if "fig-note" in (_attr(attrs, "class") or ""):
        return "fig-note"
    if any(s <= text["pos"] < e for s, e in notes):
        return "fig-note"
    if INSTRUCTION_RE.search(text["s"]):
        return "지시문"
    for other in others:
        if other is text:
            continue
        if (abs(other["x"] - text["x"]) <= STACK_TOL_PX
                and abs(other["y"] - text["y"]) <= STACK_TOL_PX):
            return "단계 자막(좌표 겹침)"
    return ""


def split_texts(svg):
    """(캡션 줄, 라벨) — 순수 함수. 테스트가 직접 부른다."""
    texts = _svg_texts(svg)
    notes = _fig_note_spans(svg)
    captions, labels = [], []
    for text in texts:
        if not text["s"].strip():
            continue
        if _is_caption(text):
            if not _excluded(svg, text, texts, notes):
                captions.append(text)
        else:
            labels.append(text)
    return captions, labels


def _drawn_blob(labels):
    return "".join(t["s"] for t in labels)


def _nouns(line):
    """캡션 줄의 **이름씨 후보**. 순수 함수.

    ★ 어미로 끝나는 조각은 뺀다 — 조사만 떼는 설계라 `비례해`·`갈리고`·`하나뿐입니다` 같은
      활용형이 「그림에 없는 것」 칸을 채워 신고를 못 읽게 만들었다(첫 실행 실측).
    ★ 조사를 뗀 꼴은 **비교에만** 쓰고 화면에는 원형을 찍는다 — `가속도`→`가속`, `넓이`→`넓`
      처럼 조사 규칙이 이름씨를 깎기 때문이다(둘 중 하나라도 그림에 있으면 「있다」).
    """
    out = []
    for run in HANGUL_RUN_RE.findall(line):
        if run.endswith(VERB_TAIL):
            continue
        stripped = PARTICLE_RE.sub("", run)
        if stripped.endswith(VERB_TAIL):
            continue
        forms = {run} | ({stripped} if len(stripped) >= 2 else set())
        if len(run) < 2 or run in NOUN_STOPWORDS or stripped in NOUN_STOPWORDS:
            continue
        out.append((run, forms))
    return out


def _symbols(line):
    return [s for s in SYMBOL_RE.findall(line) if s not in SYMBOL_STOPWORDS]


def _equation_signal(line):
    """`=`·`×`·`÷` 가 **일반 규칙**을 적은 것인가. 순수 함수 — 문턱 셋은 위 ★★ 가 정본.

    아닌 셋(캡션이 제자리인 것):
      · 물음표가 있다 → 「주어진 것·구할 것」 칩이다.
      · 모든 `=` 오른쪽이 수다 → 이 문항의 값이지 규칙이 아니다("환경 T₀ = 288 K").
      · `=` 왼쪽이 그림의 겉모습이다 → 범례다("점선 = 질량이 지나감").
    """
    if not re.search(r"[=×÷]", line):
        return None
    if "?" in line:
        return None
    if VISUAL_LHS.search(line):
        return None
    rhs = re.findall(r"[=×÷]\s*\(?\s*([^\s)]?)", line)
    if rhs and all(ch.isdigit() or ch in "-−±." for ch in rhs if ch):
        return None
    return "관계식(=×÷)"


def label_moves(caption, labels):
    """(A) — 이 캡션 줄이 이름을 붙여 주는 라벨과 **고칠 문장**. 순수 함수.

    판정선은 둘 다 참일 때다: ⑴ 라벨 문자열이 캡션 줄에 통째로 있다 ⑵ 그 자리 바로 옆에
    한글 이름이 붙어 있다(`전하 q` · `q 는 전하입니다`). ⑵가 없으면 그냥 그 기호를 언급한 문장이다.
    """
    out, seen = [], set()
    for label in labels:
        name = label["s"].strip()
        if not name or not re.search(r"[A-Za-zα-ωΑ-Ω0-9]", name) or name in seen:
            continue
        esc = re.escape(name)
        if not re.search(r"(?<![A-Za-zα-ωΑ-Ω0-9])" + esc + r"(?![A-Za-zα-ωΑ-Ω0-9])", caption):
            continue
        before = re.search(r"([가-힣]{2,6})\s*" + esc + r"(?![A-Za-zα-ωΑ-Ω0-9])", caption)
        after = re.search(esc + r"\s*(?:는|은|이|가)\s*([가-힣]{2,8})(?:입니다|이고|이며|다)",
                          caption)
        word = None
        if before and before.group(1) not in NOUN_STOPWORDS:
            word = before.group(1)
        elif after:
            word = PARTICLE_RE.sub("", after.group(1))
        if not word:
            continue
        seen.add(name)
        out.append((name, "라벨 %r → %r" % (name, word + " " + name)))
    return out


def outside_the_picture(caption, drawn):
    """(B) — 이 캡션 줄이 **그림에 없는** 양을 잇는 규칙을 말하는가. 순수 함수.

    돌려주는 것: (신호 이름, 그림에 없는 토큰들) 또는 (None, []).
    """
    signal = _equation_signal(caption)
    if not signal:
        signal = next((name for name, rx in DEFINITION_SIGNALS if rx.search(caption)), None)
    if not signal:
        return None, []
    missing = [run for run, forms in _nouns(caption) if not any(f in drawn for f in forms)]
    missing += [s for s in _symbols(caption) if s not in drawn]
    if not missing:
        return None, []
    return signal, missing


def _tagged_diagrams(data):
    """(컬렉션 이름, 삽화) — `derivation` 을 (B)에서 빼려면 출처를 알아야 한다."""
    for key, node in (data.items() if isinstance(data, dict) else []):
        for diagram in iter_diagrams(node):
            yield key, diagram


def scan_chapter(path):
    """한 챕터의 (A)·(B) 행. 행 = (fig_id, 캡션, 상세)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], [], 0
    a_rows, b_rows, seen = [], [], 0
    for coll, diagram in _tagged_diagrams(data):
        svg = diagram.get("svg") or ""
        if not svg:
            continue
        seen += 1
        fig_id = diagram.get("id") or "?"
        captions, labels = split_texts(svg)
        drawn = _drawn_blob(labels)
        for cap in captions:
            line = cap["s"].strip()
            for _name, fix in label_moves(line, labels):
                a_rows.append((fig_id, line, fix))
            if coll == "derivation":
                continue                      # 유도 카드에서 관계식은 제자리다(위 ⓓ)
            why, missing = outside_the_picture(line, drawn)
            if why:
                b_rows.append((fig_id, line,
                               "신호 %s · 그림에 없는 것 %s" % (why, ", ".join(missing[:6]))))
    return a_rows, b_rows, seen


def list_captions(path, wanted=None):
    """삽화마다 **캡션 줄과 라벨 수**를 그대로 찍는다 — 고치기 전후를 사람이 대조하는 자리.

    (B)를 지운 뒤 **캡션이 0줄이 되는 삽화**가 생기는지를 이걸로 본다. 0줄이 된 그림은
    캡션이 아니라 라벨을 손봐야 하는 자리라 자동으로 고치지 않는다(위 ★ (A) 주석과 같은 이유).
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for coll, diagram in _tagged_diagrams(data):
        svg = diagram.get("svg") or ""
        fig_id = diagram.get("id") or "?"
        if not svg or (wanted and fig_id not in wanted):
            continue
        captions, labels = split_texts(svg)
        print("%-40s [%s] 캡션 %d줄 · 라벨 %d개" % (fig_id, coll, len(captions), len(labels)))
        for cap in captions:
            print("     y=%-7.1f %s" % (cap["y"], cap["s"]))


def sweep(only=None, kind="both", limit=8):
    subjects = audit_content.subject_dirs()
    total_a = total_b = figs = chapters = scanned = 0
    for folder in subjects:
        subject = os.path.basename(folder)
        if only and subject not in only:
            continue
        scanned += 1
        subject_a, subject_b = [], []
        for name in sorted(n for n in os.listdir(folder)
                           if re.fullmatch(r"ch\d{2}\.json", n)):
            a_rows, b_rows, seen = scan_chapter(os.path.join(folder, name))
            chapters += 1
            figs += seen
            subject_a += [(name[:-5],) + r for r in a_rows]
            subject_b += [(name[:-5],) + r for r in b_rows]
        total_a += len(subject_a)
        total_b += len(subject_b)
        if not (subject_a or subject_b):
            continue
        print("-- %s -- (A) %d건 · (B) %d건" % (subject, len(subject_a), len(subject_b)))
        if kind in ("both", "a"):
            for ch, fig_id, line, fix in subject_a[:limit]:
                print("   [A] %s %s — %s" % (ch, fig_id, fix))
                print("       %s" % line[:70])
            if len(subject_a) > limit:
                print("   [A] ... 외 %d건" % (len(subject_a) - limit))
        if kind in ("both", "b"):
            for ch, fig_id, line, why in subject_b[:limit]:
                print("   [B] %s %s — %s" % (ch, fig_id, why))
                print("       %s" % line[:70])
            if len(subject_b) > limit:
                print("   [B] ... 외 %d건" % (len(subject_b) - limit))
        print()
    print("합계 — (A) %d건 · (B) %d건  · 훑은 과목 %d개 · 챕터 %d개 · 삽화 %d개"
          % (total_a, total_b, scanned, chapters, figs))
    if scanned == 0 or figs == 0:
        print("★ 한 삽화도 안 봤다 — 이 「0건」은 «없다»가 아니라 «못 봤다»이다.")
        return 1, total_b
    return 0, total_b


def main():
    parser = argparse.ArgumentParser(
        description="삽화 캡션이 그림 밖을 말하는가 — (A) 라벨로 옮길 것 / (B) 그림에 없는 것")
    parser.add_argument("chapter", nargs="?", help="챕터 JSON 경로(주면 그 장만)")
    parser.add_argument("--only", help="과목 폴더 이름(쉼표로 여럿)")
    parser.add_argument("--kind", choices=("a", "b", "both"), default="both")
    parser.add_argument("--limit", type=int, default=8, help="과목당 찍을 줄 수")
    parser.add_argument("--gate", action="store_true",
                        help="(B)가 하나라도 있으면 exit 1 — (A)는 게이트가 아니다")
    parser.add_argument("--captions", action="store_true",
                        help="판정하지 말고 삽화마다 캡션 줄·라벨 수를 그대로 찍는다")
    parser.add_argument("--id", dest="ids", action="append", help="특정 삽화만 (반복 가능)")
    args = parser.parse_args()
    only = {s.strip() for s in args.only.split(",")} if args.only else None

    if args.captions:
        if not args.chapter:
            parser.error("--captions 는 챕터 경로가 필요하다")
        list_captions(ROOT / args.chapter, set(args.ids) if args.ids else None)
        return 0

    if args.chapter:
        a_rows, b_rows, seen = scan_chapter(ROOT / args.chapter)
        for fig_id, line, fix in (a_rows if args.kind in ("both", "a") else []):
            print("[A] %s — %s\n    %s" % (fig_id, fix, line))
        for fig_id, line, why in (b_rows if args.kind in ("both", "b") else []):
            print("[B] %s — %s\n    %s" % (fig_id, why, line))
        print("합계 — (A) %d건 · (B) %d건 · 삽화 %d개" % (len(a_rows), len(b_rows), seen))
        return 1 if (args.gate and b_rows) else 0

    code, total_b = sweep(only, args.kind, args.limit)
    if code:
        return code
    return 1 if (args.gate and total_b) else 0


if __name__ == "__main__":
    sys.exit(main())
