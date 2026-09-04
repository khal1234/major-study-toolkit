# -*- coding: utf-8 -*-
r"""독자에게 보이는 한국어 문장의 **종결어미를 존댓말(합쇼체)로** 바꾼다.

    python tools/fix_honorific.py --chapter=ch12.json --table   # 매핑표만 (사람이 검토)
    python tools/fix_honorific.py --chapter=ch12.json           # 바꿀 자리 미리보기
    python tools/fix_honorific.py --chapter=ch12.json --apply

왜 도구인가 (신설 2026-08-02) — 사용자 지적:
*"과목 공통적으로 말투에 대해 언급이 안되어있나? 가장 근본인 열역학 보면 알겠지만 ~입니다.
~습니다. 로 되어있고 이렇게 하라 했던걸로 알고 있어서. ~다. 로 하네 동역학은."*

★ **관행은 있었는데 문서가 없었다.** 그래서 새 과목이 평어로 써도 아무것도 걸리지 않았다
  (AGENTS·docs 전수 grep 에 말투 조항 0건). 실측 동역학 ch12: 평어 **547문장** · 존댓말 15문장 —
  **한 챕터 안에서도 이미 갈려 있었다.**

★ **손으로 고치면 안 되는 이유가 분명하다.** 종결 어절이 **230가지**다. 손으로 바꾸면
  `않는다→않습니다` 는 맞히고 `나온다→나옵니다` 는 틀리는 식으로 문장마다 갈라지는데,
  그 갈라짐이야말로 이 작업이 없애려는 결함이다.

**변환은 규칙이지 사전이 아니다** — 한글 음절을 자모로 분해해 활용한다:
    받침 어간 + 다      → 습니다      (있다→있습니다 · 같다→같습니다)
    무받침 어간 + 다     → ㅂ니다      (이다→입니다 · 아니다→아닙니다 · 크다→큽니다)
    무받침 어간 + ㄴ다   → ㅂ니다      (한다→합니다 · 나온다→나옵니다 · 틀린다→틀립니다)
    받침 어간 + 는다     → 습니다      (않는다→않습니다 · 얻는다→얻습니다)
    ~는가?             → ~나요?      (재는가→재나요)   ← 사용자 선택
    ~가/나/까?          → +요         (무엇인가→무엇인가요)
규칙이 못 다루는 어절은 **건드리지 않고 신고한다** — 사람이 판단한다(조용히 틀리는 것보다 낫다).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from audit_conventions import chapters                                  # noqa: E402
from buildlib.checks_content import (                                   # noqa: E402
    MOTIF_EXEMPT_KEYS, TONE_SKIP, is_polite_ending, mask_inline_math, tail_word,
    tone_core, tone_segments,
)
from buildlib.checks_svg import _svg_texts                              # noqa: E402
from buildlib.jsontext import write_chapter                             # noqa: E402

# ★ **처방의 순회 범위는 자의 순회 범위를 넘으면 안 된다** (열린 날 2026-08-02, 공학수학 실측).
#   검사(`tone_issues`)는 `iter_visible_texts` 로 도는데 그것이 `MOTIF_EXEMPT_KEYS`
#   (`supplementNotes`·`lintWaivers`·`sourcePages`…)를 뺀다. 이 도구는 `TONE_SKIP` 만 보고
#   **그 자리까지 존댓말로 바꿔 버렸다** — 삽화 면제 사유와 제작 메모가 그렇게 바뀌었다.
#   그 글은 AGENTS 「말투」의 **둘째 층(기록 문서 = 평어)** 이라 바꾸면 안 되는 자리이고,
#   검사가 안 보는 곳이라 **아무도 신고하지 않는다.** 자와 처방이 갈리면 늘 이렇게 샌다.
#
# ★★ **반대로 좁아서 샌 자리 — 삽화 캡션** (열린 날 2026-08-04, R-72).
#   `TONE_SKIP` 이 `/svg` 를 통째로 빼는 것은 **산문 규칙을 SVG 마크업에 그대로 적용할 수
#   없어서**인데, 이 도구가 그 목록을 그대로 쓰는 바람에 **캡션을 아예 순회하지 않았다.**
#   자(`figure_tone_issues`)는 `<text>` 안만 꺼내 같은 판정을 하고 있었으므로,
#   실측이 정확히 갈렸다 — `--table` 은 전 챕터 **바꾼 문장 0**, 빌드는 캡션 평어를
#   ch01 **11건** · ch02 **21건** 신고. 그래서 그 32곳을 **손으로** 고쳤다.
#   손으로 고치는 것이 이 도구가 없애려는 갈라짐 그 자체이므로(`--table` 독스트링),
#   아래 `convert_svg` 가 자와 **같은 추출 함수**(`_svg_texts`)로 캡션을 돌게 했다.
SKIP = TONE_SKIP + tuple("/" + key for key in sorted(MOTIF_EXEMPT_KEYS))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

_BASE, _JONG_N, _JONG_B = 0xAC00, 4, 17          # ㄴ 받침 · ㅂ 받침
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
# ★★ **어절을 고르는 자는 `checks_content.tail_word` 하나다** (옮긴 날 2026-08-12).
#   여기 사본(`(?P<w>[가-힣]+)(?P<tail>[^가-힣]*)$`)이 있을 때 **뒤에 뭐가 남았는지를 안 봐서**
#   두 과목이 같은 날 신고했다 — 고체역학 캡션 `둘 다 0` → **`둘 입니다 0`**(부사 `다` 를
#   종결어미로 읽었다) · 공학수학 표 `| … 중근이다 | … |` 의 셀만 바뀌어 **한 표 안에서
#   말투가 갈렸다.** 검사(C23)는 둘 다 조용했다 — 닻이 *알맹이의 끝*이기 때문이다.
#   판정 근거와 전말은 그 함수의 주석이 정본이다.
# ★ '이미 존댓말인가'는 **빌드와 같은 함수**(`is_polite_ending`)로 본다.
#   여기 `("니다", …)` 사본을 두었다가 `아니다` 가 `니다` 로 끝나서 **평어인데 건드리지 않는**
#   사고가 났다 — 감사도 같은 사본을 써서 0건을 찍었다(자를 두 벌 두면 반드시 갈라진다).
# 무받침 어간인데 **명사가 아닌** 서술어 — 어간 전체가 일치할 때만 쓴다.
# `아니다` 는 '이' 로 끝나지만 지정사가 아니라 형용사라 아래 '이→입니다' 규칙에 걸리면 안 된다.
_MU_PREDICATE = {"아니": "아닙니다", "크": "큽니다", "바쁘": "바쁩니다", "나쁘": "나쁩니다"}
# ★★ **`이` 로 끝나는 명사** — 그 `이` 는 지정사가 아니라 낱말의 일부다 (열린 날 2026-08-02).
#
#   `것이다 → 것입니다` 규칙이 `깊이다` 를 **`깊입니다`** 로 만들었다. 둘은 겉모양이 같다 —
#   [받침 음절] + `이` + `다`. 것(ㅅ)·때문(ㄴ) 과 깊(ㅍ)·길(ㄹ) 을 자모로는 못 가른다.
#   가르는 것은 **낱말**이다: `것/때문` 은 의존명사이고 `이다` 가 지정사인 반면,
#   `깊이/길이` 는 **형용사 어간 + 접미사 `-이`** 로 만들어진 명사라 지정사 `이` 가 줄어든 꼴이다.
#
#   ★ 왜 인스턴스로 닫으면 안 되나: 이 갈래는 **척도를 다루는 과목 전부에서 나온다**
#     (기계재료 `에너지 우물의 깊이다` · 고체역학 `단면의 넓이다` · 열역학 `관의 길이다`).
#     게다가 규칙이 `확신=True` 로 답해서 `--table` 의 '명사로 추측' 목록에도 안 떴다 —
#     **조용히 틀린 글이 나가는** 자리였다(규칙 11: 못 가르면 못 가른다고 말해야 한다).
#   목록은 한국어 형태론이지 과목 사실이 아니다 — 공통 도구에 두는 것이 맞다.
_I_FINAL_NOUNS = ("깊이", "길이", "넓이", "높이", "굽이", "먹이", "쓰임새", "차이", "사이")


def _decompose(ch):
    code = ord(ch) - _BASE
    if not 0 <= code < 11172:
        return None
    return code // 588, (code % 588) // 28, code % 28


def _compose(cho, jung, jong):
    return chr(_BASE + cho * 588 + jung * 28 + jong)


def to_polite(word, is_question):
    """평어 종결 어절 → (합쇼체, 확신). 규칙이 못 다루면 (None, _).

    `확신`이 False 면 **명사로 추측해 '입니다'를 붙인 것**이다 — 서술어였으면 틀린다
    (`돌아서다` → 옳게는 `돌아섭니다`인데 `돌아서입니다`가 된다). 그래서 조용히 넘기지 않고
    `--table` 이 따로 모아 보여 준다. 기계가 못 가르는 자리는 **못 가른다고 말해야 한다**(규칙 11).
    """
    if is_polite_ending(word):
        return None, True
    if is_question:
        if word.endswith("는가"):
            return word[:-2] + "나요", True
        if word.endswith(("가", "나", "까")):
            return word + "요", True
        return None, True
    # ★★ 서술형 **지시문**은 활용이 아니라 문형이 다르다 (넓힌 날 2026-08-02, 열역학 실측).
    #
    #   이해도 체크 지문 중 `설명하라`·`설명해보라`·`구성하라` 27건이 `~다` 로 끝나지 않아
    #   통째로 '규칙이 못 다룬 어절' 로만 쌓였다. 그런데 같은 카드의 나머지 지문 197건은
    #   규칙이 바꿔 준다 — **한쪽만 바뀌면 같은 카드 묶음 안에서 말투가 갈라진다.**
    #   그 갈라짐이 이 도구가 없애려는 결함 그 자체라, 여기서 함께 다룬다.
    #
    #   해요체로 맞추는 것은 이 도구의 기존 선택과 같다(`~는가?` → `~나요?`, 사용자 선택).
    #   합쇼체 `설명하십시오` 는 지시가 강해 학습 카드의 어조와 맞지 않는다.
    if word.endswith("해보라"):
        return word[:-3] + "해 보세요", True
    if word.endswith("하라"):
        return word[:-2] + "해 보세요", True
    if not word.endswith("다"):
        return None, True
    body = word[:-1]
    if not body:
        return "입니다", True            # 수식 뒤의 `\(…\)다` — 지정사 '이다'가 줄어든 꼴
    if body.endswith("는"):
        return body[:-1] + "습니다", True    # 받침 어간 + 는다
    parts = _decompose(body[-1])
    if parts is None:
        return None, True
    cho, jung, jong = parts
    if jong == _JONG_N:                  # 무받침 어간 + ㄴ다 → ㅂ니다 (한다→합니다·나온다→나옵니다)
        return body[:-1] + _compose(cho, jung, _JONG_B) + "니다", True
    if jong:
        return body + "습니다", True     # 받침 어간 + 다 (있다→있습니다·같다→같습니다)
    # ★★ 무받침 + 다 는 **두 가지가 섞여 있다** (2026-08-02, 매핑표 검토에서 잡았다).
    #   ⑴ 서술어 어간(크다·다르다·단순하다) → ㅂ니다
    #   ⑵ **명사 + 다** = 지정사 '이다'의 축약(음수다·가속도다·경우다) → 입니다
    #   처음엔 둘을 안 갈라 ⑵ 까지 활용해 `음수다→음숩니다`·`가속도다→가속돕니다` 를 만들었다.
    #   실측 이 챕터에서 ⑵ 가 23가지, ⑴ 이 5가지 — **명사 쪽이 기본값**이어야 한다.
    #   기본값을 잘못 잡으면 조용히 틀린 글이 나가므로, 이 갈래는 `--table` 로 매번 눈으로 본다.
    if body in _MU_PREDICATE:
        return _MU_PREDICATE[body], True
    if body.endswith("하"):
        return body[:-1] + "합니다", True    # 하다 계열 — 단순하다→단순합니다
    if body.endswith("르"):
        return body[:-1] + "릅니다", True    # 르 불규칙 — 다르다→다릅니다·고르다→고릅니다
    if body.endswith(_I_FINAL_NOUNS):
        return body + "입니다", False    # `이` 가 낱말의 일부 — 깊이다→깊이입니다 (사람이 확인)
    if body.endswith("이"):
        return body[:-1] + "입니다", True    # 지정사 — 것이다→것입니다·때문이다→때문입니다
    return body + "입니다", False        # 명사로 **추측** — 음수다→음수입니다 (사람이 확인)


def replacements(text):
    """[(원문 위치, 원래 어절, 바뀐 어절, 확신)] 과 못 바꾼 어절. 순수 함수 — 테스트가 직접 부른다.

    ★ **어디를 바꿀지 고르는 일**과 **글을 다시 만드는 일**을 갈라 둔다 (2026-08-04, R-72).
      삽화 SVG 는 같은 캡션이 `<tspan>` 사이에 흩어져 있어 통짜 치환을 할 수 없다 —
      `convert_svg` 가 이 좌표를 태그 밖 원문으로 되돌려 쓴다. 자를 두 벌 두지 않으려면
      **고르는 쪽이 하나**여야 한다(이 파일이 이미 두 번 데인 부류다).
    """
    changed, unknown, cur = [], [], 0
    # ★ **조각을 나누는 자는 검사와 같은 것 하나**(`tone_segments`)를 쓴다. 수식을 가린 판에서
    #   재므로 좌표는 원문과 1:1이고, 한글은 가려지지 않아 어절도 그대로다.
    #   ⑴ 가리지 않으면 수식 속 괄호 때문에 `…판정 정리다(\(W = 0\)이면 종속).` 의 꼬리를 못 벗기고
    #   ⑵ 괄호 안을 조각으로 안 세면 `…곱합니다 (…으로 뭉친다)` 의 평어를 못 본다.
    #   둘 다 **검사는 신고하는데 변환기는 못 고치는** 상태를 만든다(이미 한 번 닫은 부류다).
    masked = mask_inline_math(text)
    for start, end in tone_segments(text):
        sent = masked[start:end]
        lead = len(sent) - len(sent.lstrip())
        core = tone_core(sent)
        if not core or not sent.startswith(core, lead):
            core, lead = sent.rstrip(), 0
        # ★ **어절을 고르는 자도 하나다**(`tail_word`, 옮긴 날 2026-08-12) — 조각의 *끝*에 있는
        #   어절만 종결로 본다. 뒤에 낱말 글자나 표 칸막이 `|` 가 남아 있으면 그건 문장의 끝이
        #   아니다(`둘 다 0` 의 `다` · 표 셀의 `중근이다`). 위 `_SENT_SPLIT` 옆 주석이 정본이다.
        word, w_at = tail_word(core)
        if word is None:
            continue
        # ★ 물음표는 **수식을 가린 판**(`sent`)에서 센다 (열린 날 2026-08-02, 열역학 실측).
        #   `압력의 정의식은 \(P = \frac{F}{?}\) 이다.` 처럼 **빈칸을 `?` 로 쓴 수식**이 들어가면
        #   원문에서 세는 순간 의문문으로 오판하고, 의문문 갈래는 `~이다` 를 못 다뤄
        #   **문장 전체가 조용히 안 바뀐다.** 감사에는 그대로 남아 '고칠 수 없는 잔량' 처럼 보인다.
        #   위에서 `masked` 를 잘라 쓰므로 여기서 다시 가릴 필요는 없다 — 원문을 쓰면 안 된다는
        #   것이 요점이라 회귀(`test_reader_facing_prose_is_polite` ⑶-e)가 이 자리를 잠근다.
        # ★ `~은가` 도 의문형 어미다 (넓힌 날 2026-08-02, 열역학 실측).
        #   `주어진 T가 그 압력의 포화온도보다 낮은가` — **물음표 없이 쓴 형용사 의문문**이다.
        #   `는가`·`인가` 만 보던 자는 이걸 평서문으로 읽고 `~다` 갈래로 보내, 거기서도 못 다뤄
        #   **검사는 신고하는데 변환기는 못 고치는** 상태로 남겼다(이 파일이 이미 두 번 닫은 부류).
        #   `낮은가`·`높은가`·`같은가` 는 전부 형용사 어간 + `-(으)ㄴ가` 이고, 처방은 기존
        #   `~가/나/까 → +요` 규칙이 그대로 낸다(`낮은가` → `낮은가요`).
        is_q = "?" in sent or word.endswith(("는가", "인가", "은가"))
        new, sure = to_polite(word, is_q)
        if new is None:
            if not is_polite_ending(word):
                unknown.append(word)
            continue
        at = start + lead + w_at
        if at < cur:                       # 조각이 겹치면(괄호주석) 앞의 것을 살린다
            continue
        cur = at + len(word)
        changed.append((at, word, new, sure))
    return changed, unknown


def convert(text):
    """(바뀐 글, [(원래 어절, 바뀐 어절, 확신)], [못 바꾼 어절])."""
    spans, unknown = replacements(text)
    pieces, cur = [], 0
    for at, word, new, _sure in spans:
        pieces.append(text[cur:at])
        pieces.append(new)
        cur = at + len(word)
    pieces.append(text[cur:])
    return "".join(pieces), [(w, n, s) for _at, w, n, s in spans], unknown


_TAG = re.compile(r"<[^>]+>")


def strip_tags_map(inner):
    """`<text>` 안쪽 마크업에서 (태그를 뺀 글자, 각 글자의 원문 인덱스). 순수 함수.

    태그를 지운 문자열만으로는 **어디를 고쳐야 하는지 되돌릴 수 없다** — 아래첨자 `<tspan>` 이
    낀 캡션이 흔하므로 인덱스를 함께 들고 다닌다.
    """
    text, index, at = [], [], 0
    for m in _TAG.finditer(inner):
        for i in range(at, m.start()):
            text.append(inner[i])
            index.append(i)
        at = m.end()
    for i in range(at, len(inner)):
        text.append(inner[i])
        index.append(i)
    return "".join(text), index


def convert_svg(svg):
    """삽화 캡션(`<text>` 안)만 존댓말로. (바뀐 svg, [(원래, 바뀐, 확신)], [못 바꾼 어절]).

    ★ **자와 같은 범위만 본다.** `_svg_texts` 는 검사(`figure_tone_issues`)가 쓰는 바로 그
      함수라, `transform` 붙은 글자(bbox 추정 불가라 검사 제외)와 **굵은 제목**(표제와 같은
      부류라 말투를 묻지 않는다)이 자동으로 같이 빠진다. 처방이 자보다 넓으면 아무도
      신고하지 않는 곳을 조용히 고치게 된다 — 위 `SKIP` 주석의 그 사고다.

    ★ **못 하는 것은 하지 않고 신고한다.** ⑴ 엔티티(`&amp;`)가 든 캡션은 자가 디코드해서 보므로
      좌표가 어긋난다 ⑵ 어절 가운데를 태그가 가르면(`말합<tspan>니다</tspan>`) 통짜로 못 바꾼다.
      둘 다 사람이 본다 — 조용히 틀리는 것보다 낫다(규칙 11).

    ★ **바꾸면 글자 폭이 바뀐다.** 캡션 길이가 달라지면 라벨 여백·상하 균형·viewBox 이탈이
      함께 움직이므로, `--apply` 뒤에는 `audit_figure_balance.py` 와 빌드를 반드시 다시 돌린다.
    """
    out, changed, unknown = svg, [], []
    for item in reversed(_svg_texts(svg)):          # 뒤에서부터 — 앞쪽 좌표가 안 흔들린다
        if str(item.get("weight", "")).strip() in ("700", "bold"):
            continue
        elem = out[item["pos"]:item["end"]]
        head, tail = elem.find(">"), elem.rfind("</text>")
        if head < 0 or tail <= head:
            continue
        inner = elem[head + 1:tail]
        if "&" in inner:
            unknown.append(inner.strip()[:24])
            continue
        text, index = strip_tags_map(inner)
        spans, left = replacements(text)
        unknown.extend(left)
        if not spans:
            continue
        new_inner = inner
        for at, word, new, sure in reversed(spans):
            lo, hi = index[at], index[at + len(word) - 1]
            if hi - lo != len(word) - 1:            # 어절 가운데를 태그가 가른다
                unknown.append(word)
                continue
            new_inner = new_inner[:lo] + new + new_inner[hi + 1:]
            changed.append((word, new, sure))
        out = out[:item["pos"]] + elem[:head + 1] + new_inner + elem[tail:] + out[item["end"]:]
    return out, changed, unknown


def walk(node, path, log, unknown):
    if isinstance(node, dict):
        return {k: walk(v, path + "/" + str(k), log, unknown) for k, v in node.items()}
    if isinstance(node, list):
        return [walk(v, path + "[" + str(i) + "]", log, unknown)
                for i, v in enumerate(node)]
    if not isinstance(node, str):
        return node
    # ★ 삽화는 `SKIP`(`/svg`) 보다 **먼저** 본다 — 그 면제는 '산문 규칙을 마크업에 그대로
    #   적용할 수 없다'는 뜻이지 캡션을 안 봐도 된다는 뜻이 아니다(위 SKIP 주석, R-72).
    if path.endswith("/svg"):
        new, changed, left = convert_svg(node)
        log.extend((w, n, s, "svg") for w, n, s in changed)
        unknown.extend((path, w) for w in left)
        return new
    if any(k in path for k in SKIP):
        return node
    new, changed, left = convert(node)
    log.extend((w, n, s, "text") for w, n, s in changed)
    unknown.extend((path, w) for w in left)
    return new


def scope_error(argv):
    """`--apply` 에 범위가 없으면 사유. 순수 함수 — 테스트가 직접 부른다.

    ★ **열린 날 2026-08-05 — '어느 챕터를 썼는지 사후에 알 수 없다'.**
      2026-08-04 세션이 ch03·ch05 만 `--apply` 했다고 기록했는데 **ch04 도 변환돼 있었다.**
      다음 세션이 그것을 '미해결'로 넘겼고, 원인을 캐다가 `git stash` 로 워킹트리를
      되돌리려다 사용자가 막았다(원장 15번) — 커밋 안 된 세 챕터가 날아갈 뻔했다.

      **재현으로 밝힌 것**(2026-08-05): 임시 챕터 `ch99` 에 평어 한 문장을 두고 `--table` 만
      돌렸더니 *바꾼 문장 1* 을 보고하고 **파일은 그대로였다.** 즉 `--table` 은 쓰지 않는다
      (`if not apply_it: continue`). `--chapter=` 도 `chapters()` 가 스템을 정확히 대조한다.
      → **도구 결함이 아니다.** 남는 설명은 하나뿐이다 — 범위 없는 `--apply` 가 전 챕터를
      쓰고 지나갔고(그래야 ch04 만 조용히 바뀐다: ch01·ch02 는 이미 존댓말이라 무변화),
      그 실행이 기록에 남지 않았다.

    ★ 그래서 막을 것은 '실수'가 아니라 **범위가 안 적힌 채로도 쓸 수 있는 구조**다.
      `--apply` 에는 `--chapter=` 나 `--all` 중 하나를 요구하고, 실행 끝에 **쓴 챕터를
      한 줄로 모아 출력**한다. 그러면 무엇을 썼는지가 대화 로그에 남아 다음 세션이
      추측할 필요가 없다. (`--all` 은 여전히 전 챕터를 쓴다 — 금지가 아니라 **선언**이다.)
    """
    if "--apply" not in argv:
        return None
    if "--all" in argv or any(a.startswith("--chapter=") for a in argv):
        return None
    return ("--apply 에는 범위가 필요하다 — `--chapter=chNN.json` 으로 한 챕터를 쓰거나, "
            "전 챕터를 쓸 작정이면 `--all` 을 함께 준다. "
            "범위 없이 쓰면 무엇을 고쳤는지가 기록에 안 남는다(2026-08-04 ch04 사고).")


def main():
    why_not = scope_error(sys.argv)
    if why_not:
        print("[중단] " + why_not)
        return 2
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    apply_it, table = "--apply" in sys.argv, "--table" in sys.argv
    stem = os.path.splitext(only)[0] if only else None
    written = []

    for subject, ch, chapter in chapters(stem):
        log, unknown = [], []
        fixed = walk(chapter, "", log, unknown)
        print("\n=== %s %s ===" % (subject, ch))
        guessed = sorted({(o, n) for o, n, sure, _k in log if not sure})
        if table:
            seen = {o: n for o, n, _s, _k in log}
            counts = {}
            for o, _n, _s, _k in log:
                counts[o] = counts.get(o, 0) + 1
            for old in sorted(seen, key=lambda w: (-counts[w], w)):
                print("  %-14s → %s" % (old, seen[old]))
        # ★ 산문과 **삽화 캡션을 갈라 센다** — 자(빌드)도 둘을 다른 메시지로 신고하므로,
        #   이렇게 세야 *처방이 자와 같은 것을 보고 있는지* 를 숫자로 대조할 수 있다(R-72).
        n_svg = sum(1 for _o, _n, _s, kind in log if kind == "svg")
        print("  바꾼 문장 %d (산문 %d · 삽화 캡션 %d) · 종결 어절 %d가지"
              % (len(log), len(log) - n_svg, n_svg, len({o for o, _n, _s, _k in log})))
        if guessed:
            print("  ★ 명사로 **추측**해 '입니다'를 붙인 어절 %d가지 — 서술어였으면 틀린다:"
                  % len(guessed))
            print("      " + " · ".join("%s→%s" % (o, n) for o, n in guessed))
        if unknown:
            print("  ★ 규칙이 못 다룬 어절 %d건 — 사람이 본다:" % len(unknown))
            for path, w in unknown[:20]:
                print("      %-56s %s" % (path[:56], w))
        if not apply_it:
            continue

        # 표기는 건드리지 않고 **바뀐 문자열 값만** 갈아끼운다 — 왜 그래야 하는지와
        # 안전장치(재파싱 검증)는 `buildlib/jsontext.py` 독스트링이 정본이다.
        # 예전에는 표준 직렬화로 통째로 다시 써서, 손으로 한 줄에 적은 자리가
        # 하나라도 있으면 **그 챕터는 이 도구가 영영 못 건드렸다**(공학수학 ch02 337문장).
        ch_path = os.path.join(DATA, subject, ch + ".json")
        status, why = write_chapter(ch_path, chapter, fixed)
        if status == "written":
            print("  [기록] %s" % os.path.relpath(ch_path, ROOT))
            written.append("%s %s" % (subject, ch))
        elif status == "nochange":
            print("  [그대로] 바꿀 것이 없다")
        else:
            print("  [중단] 표기를 보존한 채로는 못 쓴다 — %s" % why)
    if apply_it:
        # ★ 쓴 챕터를 **한 줄로 모아** 남긴다 — 챕터별 [기록] 은 긴 출력에 묻힌다.
        #   묻히면 다음 세션이 '무엇을 썼나'를 추측하게 되고, 그것이 ch04 사고였다.
        print("\n[기록 요약] %s" % (" · ".join(written) if written else "없음"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
