# -*- coding: utf-8 -*-
"""**이론 절에 삽화가 없으면 사유가 적혀 있나** (열린 날 2026-09-09).

    python tools/audit_theory_figure_reasons.py                # 전 과목 (지금 학기 먼저)
    python tools/audit_theory_figure_reasons.py --only=<과목>  # 한 과목만
    python tools/audit_theory_figure_reasons.py --fail-only    # 게이트에 걸리는 것만

★ **왜 열렸나** — 사용자가 하루에 세 과목에서 같은 말을 했다:
  *[발화 생략]* ·
  *[발화 생략]* · *[발화 생략]*
  세 과목에 걸쳐 있으므로 **한 과목의 사정이 아니다.**

  더 나쁜 것은 **판정이 아예 없었다**는 점이다. 문항 층에는 `noDiagramReason` 이 촘촘히 붙어
  있는데 **이론 절에는 그 자리가 없어**, 「없어도 되는 절이라 뺐다」와 「그냥 안 그렸다」가
  구별이 안 됐다. 실사고: 유체역학 인박스가 *[발화 생략]* 이라고
  적었는데 그 6 건은 **문항 층의 `noDiagramReason`** 이었다 — 낱말이 달라 다른 것을 세었다.

## 무엇을 세나

⑴ **사유 없는 빈 장** — 이론 절이 있는데 **삽화가 0 개**이고 `noTheoryDiagramReason` 도 없는 장.
⑵ **미판정 절** — 그 절에 삽화도 없고 사유도 없는 절. **⑴ 과 ⑵ 가 둘 다 게이트다**(exit 1).
⑶ **밀도** — 절 수 대비 이론 삽화 수. 후보로만 낸다. 낮다고 결함이 아니다(표로 끝나는 절도 있다).
⑷ **그리기로 판정한 자리** — 사유에 「아직 안 그렸습니다」가 적힌 장. **게이트가 아니라 목록이다.**

## ★ ⑷ 는 「판정이 곧 은폐」가 되는 것을 막는 자다 (2026-09-09)

절 단위 판정을 쓰다 보면 사유의 절반은 「안 그린다」가 아니라 **「그려야 하는데 아직 안
그렸다」**가 된다. 그런데 ⑵ 의 눈으로는 둘이 똑같다 — 사유가 적혔으므로 **그 절은 목록에서
사라진다.** 그러면 「그려야 한다」고 스스로 적어 놓은 자리가 아무 데도 안 남고, 다음 세션은
그것을 찾을 방법이 없다. 그래서 그 문구를 **표시로 약속하고 따로 센다.**

세는 단위는 **절이 아니라 장**이다. 한 사유가 여러 절을 한꺼번에 다루므로 절 수를 문자열에서
세면 틀린 수가 나온다 — 「어디를 열면 되나」만 정확하면 이 목록은 제 일을 한다.

## ★ 판정을 「장」에서 「절」로 내렸다 — 사용자 판정 2026-09-09 *[발화 생략]*

첫 판은 **장 단위**였고, 그래서 삽화가 두 장만 있어도 그 장은 통과했다. 사용자가 응용고체
`ch13`(절 13 · 이론 삽화 2)을 보고 *[발화 생략]*
라고 물었다 — **그 장은 게이트를 통과하고 있었다.** 장 단위 눈금이 못 보는 자리가 그것이다.

절 단위로 내리면서도 **이미 쓴 사유는 그대로 인정한다**: 챕터 최상위 사유 문자열이 그 절 id 를
담고 있으면 그 절은 판정된 것으로 본다(기존 사유가 «⑴ `sec-no-slip` — …» 꼴로 절을 짚는다).
그래서 소급 비용이 「다시 쓰기」가 아니라 「절 id 를 빠뜨린 것만 채우기」가 된다.

반대 의견도 적어 둔다 — **경보 피로**다. 승격 시점 밀도 후보가 161장이라 한꺼번에 빨강이 되고,
그러면 검사기가 죽는다는 것이 에이전트의 제안이었다(2-2 먼저, 3-1 나중). 사용자가 그것을 듣고
동시 승격을 골랐으므로 그대로 켠다. 이 문단은 나중에 「왜 이렇게 아팠나」를 묻는 사람을 위한 것이다.

## ☐ 이 자가 못 보는 것 (규칙 21)

- **사유가 타당한지 안 본다.** 한 글자만 적어도 내려간다. 「무엇이 적혔나」는 사람이 읽는다.
- **삽화가 제 일을 하는지 안 본다.** 그건 `audit_convention_drift --check=figure-carries-the-symbols`
  의 몫이고, 이 자는 **있나 없나**만 본다.
- **절 id 를 안 적은 챕터 사유는 그 절을 못 덮는다.** 사유는 있는데 절을 안 짚으면 신고된다 —
  그것이 이 승격이 노리는 자리이지 결함이 아니다.
- **요약·모의고사 장(`ch90` 이상)은 안 본다.** 첫 실행이 만든 예외다 — 아래 상수 참조.
- **⑷ 는 문자열 약속이다.** 「아직 안 그렸습니다」 말고 다른 말로 적으면 이 자는 못 본다.
  그래서 ⑷ 의 0 은 「그릴 것이 없다」가 아니라 **「그 말로 적은 것이 없다」**이다.
- **⑸ 는 `kind == "derivation"` 인 카드만 본다.** 공식 정리 카드는 순회에 없다 — 그쪽에
  그림이 없다는 사실은 이 자의 0 에 안 들어온다.

## 첫 실행 실측 (2026-09-09)

요약 장을 걷어낸 뒤 **사유 없는 빈 장 30개**, 그리고 그 30이 **두 과목에 통째로 몰린다** —
수치해석 18장 · 시스템제어 12장. 둘 다 3-1 이고, **한 과목이 한 장도 안 그린 것**이라
「이 장을 안 그렸다」가 아니라 **「이 과목은 이론 삽화를 쓰지 않는다」**가 맞는 서술이다.
그렇다면 필요한 것은 삽화가 아니라 **그 과목의 방침을 한 번 적는 것**이고, 이 자의 게이트가
요구하는 것도 정확히 그것이다.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import audit_content                                                    # noqa: E402
import audit_chain_selfsufficiency as chain                             # noqa: E402

REASON_KEYS = ("noTheoryDiagramReason", "noDiagramReason")

# 요약·모의고사 장은 이 자의 대상이 아니다.
# ★ **첫 실행이 이 상수를 만들었다 (규칙 21).** 42건 가운데 12건이 `ch90`~`ch92` 였고 전부
#   「이론 절 2개 · 삽화 0」 이었다 — 그 둘은 요약 블록이지 배우는 절이 아니다. 요약에 삽화가
#   없다고 사유를 적으라 하면 **똑같은 사유 열두 줄**이 생기고, 그러면 이 자의 목록이 잡음으로
#   덮여 진짜(수치해석·시스템제어가 통째로 비어 있는 것)가 안 보인다.
#   이 리포는 `ch90` 이상을 요약·모의고사로 쓴다(고체역학 ch90·ch91, 열역학 ch90~ch92, …).
SUMMARY_CHAPTER_FROM = 90

# 「그려야 하는데 아직 안 그렸다」고 스스로 적은 자리를 찾는 표시. 사유가 이 말을 담으면
# ⑵ 에서는 내려가지만 ⑷ 의 목록에는 남는다 — 판정이 곧 은폐가 되는 것을 막는 자리다.
PENDING_MARK = "아직 안 그렸습니다"

# ⑹ 절 단위 「그리기로 판정했는데 그 절에 삽화가 0」 (열린 날 2026-09-13).
# ★ 왜 — ⑷ 는 문자열 약속이라 응용열역학 ch08 이 「다섯 다 아직 안 그렸다는 뜻입니다」로 적은
#   순간 목록에서 빠졌다. Grep 「안 그렸」은 71장인데 ⑷ 는 2장만 찍었다. 게다가 ⑷ 는 장 단위라
#   그 뒤 실제로 그렸는지를 안 본다. 그래서 문구가 아니라 **사유가 짚은 절 id × 그 절 삽화 수**로 잰다.
# 판정선: 사유 문장에서 그 절 id 바로 앞에 놓인 표시가 「그린다」 쪽이면 그리기 판정이다.
DRAW_MARKS = ("그려야", "그림 쪽", "그릴 절", "그릴 후보")
DRAW_HEADERS = ("그려야 하는 절", "그려야 했던 절", "그림 쪽", "그릴 절")
NO_DRAW_MARKS = ("안 그려도", "그리지 않아도", "없어도 되", "안 그린다", "안 그립니다", "그리지 않는다",
                 "그리지 않습니다", "그릴 필요가 없", "그릴 것이 없", "안 그릴")
# ★ 첫 실행 둘이 고친 것(규칙 21):
#   ⑴ 「네 절 다 안 그립니다」의 「그립니다」를 그리기 표시로 읽었다 → 「그립니다」는 표시에서 뺐다
#      (「각 장의 형상은 그 장이 그립니다」처럼 남의 일을 말하는 자리에도 나온다).
#   ⑵ 절 id 앞의 가장 가까운 표시만 보면 앞 절 괄호 속 낱말에 끌려갔다 → **그 절 id 뒤의 제 몫 문장**
#      (다음 절 id 전까지)을 먼저 보고, 거기 표시가 없을 때만 앞쪽 머리말을 본다.
#   ⑶ `sec-scope` 가 `sec-scope-and-use` 안에서 잡혔다 → id 는 앞뒤가 낱말 문자·하이픈이 아닐 때만 인정한다.
# 게이트는 래칫이다 — 첫 실측의 절 목록을 기준선으로 두고 **새로 생긴 것만** 막는다.
# 한꺼번에 빨강이면 경보 피로로 자가 죽는다(2026-09-09 이 파일 머리의 반대 의견). 줄어드는 것은 자유다.
PENDING_BASELINE = os.path.join(os.path.dirname(HERE), "docs", "그리기-판정-기준선.txt")


def theory_sections(data):
    """이론 절 목록. `theory` 가 dict(`sections`)든 list 든 같은 꼴로 돌려준다."""
    theory = data.get("theory")
    if isinstance(theory, dict):
        return [s for s in (theory.get("sections") or []) if isinstance(s, dict)]
    if isinstance(theory, list):
        return [s for s in theory if isinstance(s, dict)]
    return []


def figure_count(sections):
    """이론 절이 가진 삽화 수. 순수 함수."""
    return sum(len(s.get("diagrams") or []) for s in sections)


def _filled(value):
    """빈 문자열과 공백은 사유가 아니다(사유 없는 면제를 막는 것과 같은 판정선)."""
    return isinstance(value, str) and value.strip() != ""


def has_reason(data, sections):
    """사유가 어디든 적혀 있나 — 챕터 수준이든 절 수준이든. 순수 함수."""
    if any(_filled(data.get(k)) for k in REASON_KEYS):
        return True
    return any(_filled(s.get(k)) for s in sections for k in REASON_KEYS)


def chapter_reason_text(data):
    """챕터 수준에 적힌 사유를 한 덩어리로. 절 id 가 여기 있으면 그 절은 판정된 것이다."""
    return " ".join(str(data.get(k)) for k in REASON_KEYS if _filled(data.get(k)))


def uncovered_sections(data, sections):
    """삽화도 사유도 없는 절의 id 목록. 순수 함수.

    한 절이 「덮였다」로 보는 길은 셋이다 —
    ⑴ 그 절에 삽화가 있다 ⑵ 그 절에 사유 키가 채워져 있다
    ⑶ **챕터 수준 사유가 그 절 id 를 담고 있다**(이미 쓴 사유를 그대로 인정하는 자리다).
    """
    blanket = chapter_reason_text(data)
    out = []
    for s in sections:
        if s.get("diagrams"):
            continue
        if any(_filled(s.get(k)) for k in REASON_KEYS):
            continue
        sid = s.get("id") or ""
        if sid and sid in blanket:
            continue
        out.append(sid or "(id 없음)")
    return out


def pending_draw(data, sections):
    """「그려야 하는데 아직 안 그렸다」고 적힌 장인가. 순수 함수.

    챕터 사유든 절 사유든 어디에 적혀 있어도 잡는다 — 적는 자리를 규정하면 규정한 자리에만
    적히고, 그러면 다른 자리에 적은 것이 조용히 사라진다.
    """
    if PENDING_MARK in chapter_reason_text(data):
        return True
    return any(PENDING_MARK in str(s.get(k))
               for s in sections for k in REASON_KEYS if _filled(s.get(k)))


def pending_sections(data, sections):
    """그리기로 판정됐는데 삽화가 0 인 절 id 목록. 순수 함수.

    ☐ 못 보는 것: 표시 낱말이 DRAW_MARKS·NO_DRAW_MARKS 밖이면 판정 쪽을 모른다(그때는 안 센다).
      절 사유 키에 적힌 판정은 그 절 자신의 것으로 본다.
    """
    blanket = chapter_reason_text(data)
    all_ids = [s.get("id") for s in sections if s.get("id")]

    def id_re(i):
        return re.compile(r"(?<![\w-])" + re.escape(i) + r"(?![\w-])")

    any_id = re.compile("|".join(r"(?<![\w-])" + re.escape(i) + r"(?![\w-])" for i in all_ids)) if all_ids else None

    def last_end(text, marks):
        return max((text.rfind(k) + len(k) for k in marks if k in text), default=-1)

    def decide(text, m):
        nxt = any_id.search(text, m.end()) if any_id else None
        clause = text[m.end():nxt.start() if nxt else len(text)]
        # 제 몫 문장은 다음 굵은 머리말(`**그려야 했던 절**`)·☞ 요약 앞에서 끝난다.
        # 단 제 몫 문장 자체가 굵게 시작하면(`— **그려야 한다.**`) 그 굵음은 건너뛴다.
        body = clause.lstrip("` —–-:(")
        skip = len(clause) - len(body)
        if body.startswith("**"):
            close = body.find("**", 2)
            skip += close + 2 if close >= 0 else 0
        cuts = [p for p in (clause.find("**", skip), clause.find("☞", skip)) if p >= 0]
        if cuts:
            clause = clause[:min(cuts)]
        d, n = last_end(clause, DRAW_MARKS), last_end(clause, NO_DRAW_MARKS)
        if d >= 0 or n >= 0:
            return d > n
        # 제 몫 문장에 표시가 없으면 **머리말**만 본다 — 앞 절의 「그려야 합니다」가 번호 목록을 타고
        # 새면 안 된다(넷째 검정: 공학수학 2 ch15 `sec-pairs` 가 앞 `sec-integral` 의 판정에 끌려갔다).
        before = text[:m.start()]
        return last_end(before, DRAW_HEADERS) > last_end(before, NO_DRAW_MARKS)

    out = []
    for s in sections:
        if s.get("diagrams"):
            continue
        sid = s.get("id") or ""
        if not sid:
            continue
        own = " ".join(str(s.get(k)) for k in REASON_KEYS if _filled(s.get(k)))
        texts = [sid + " " + own] if own else []
        if id_re(sid).search(blanket):
            texts.append(blanket)
        if any(decide(t, m) for t in texts for m in id_re(sid).finditer(t)):
            out.append(sid)
    return out


def read_pending_baseline():
    try:
        with open(PENDING_BASELINE, encoding="utf-8") as fh:
            return {ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")}
    except OSError:
        return set()


# ── 유도 카드 (열린 날 2026-09-09) ────────────────────────────────────────────
# ★ **왜 뒤늦게 붙나** — 사용자가 *[발화 생략]*
#   라고 물었을 때, 이 자는 그 장을 **초록으로 찍고 있었다.** 이론 절만 세고 유도 카드는
#   순회에 넣지도 않았기 때문이다. 「이론 삽화」라는 이름이 그 사각지대를 가렸다 —
#   유도는 **식이 걸어가는 자리**라 그림이 없으면 독자가 머릿속에서 대신 걸어야 한다.
# 사유 키는 이론 절과 대칭으로 둔다. 카드 수준·챕터 수준 어디에 적어도 인정한다.
DERIVATION_REASON_KEYS = ("noDerivationDiagramReason",) + REASON_KEYS


def derivation_cards(data):
    """유도 카드 목록 — `kind == "derivation"` 인 것만.

    **공식 정리 카드(`kind` 가 그 밖)는 대상이 아니다.** 정리 카드는 식을 늘어놓는 자리라
    그릴 걸음이 없다 — 둘을 같이 세면 「그릴 수 없는 것」이 목록의 절반을 채운다.
    """
    der = data.get("derivation")
    if isinstance(der, dict):
        items = der.get("formulas") or []
    elif isinstance(der, list):
        items = der
    else:
        return []
    return [f for f in items
            if isinstance(f, dict) and f.get("kind") == "derivation"]


def card_has_figure(card):
    """카드가 그림을 지녔나. 순수 함수.

    슬라이드 모드는 **그림 한 벌을 카드에 두고 단계가 `show` 로 고를 뿐**이라
    (`docs/2026-08-18-슬라이드모드-튜토리얼-사양.md`), 두 모드를 따로 셀 필요가 없다.
    단계에 그림을 박은 옛 형태도 함께 본다 — 못 보면 「없다」로 잘못 신고한다.
    """
    fig = card.get("figure")
    if isinstance(fig, dict) and _filled(fig.get("svg")):
        return True
    for st in card.get("derivationSteps") or []:
        sf = st.get("figure") if isinstance(st, dict) else None
        if isinstance(sf, dict) and _filled(sf.get("svg")):
            return True
    return False


def uncovered_derivations(data, cards):
    """그림도 사유도 없는 유도 카드의 id 목록. 순수 함수.

    덮이는 길은 이론 절과 같은 셋이다 — 그림이 있다 · 카드에 사유가 있다 ·
    챕터 사유가 그 카드 id 를 담는다.
    """
    blanket = " ".join(str(data.get(k)) for k in DERIVATION_REASON_KEYS
                       if _filled(data.get(k)))
    out = []
    for c in cards:
        if card_has_figure(c):
            continue
        if any(_filled(c.get(k)) for k in DERIVATION_REASON_KEYS):
            continue
        cid = c.get("id") or ""
        if cid and cid in blanket:
            continue
        out.append(cid or "(id 없음)")
    return out


def main(argv):
    only = None
    fail_only = "--fail-only" in argv
    for a in argv:
        if a.startswith("--only="):
            only = a.split("=", 1)[1]

    dirs = audit_content.subject_dirs()
    if audit_content.reject_unmatched_only(only, dirs):
        return 2
    sem = {os.path.basename(d): chain.subject_semester(d) for d in dirs}
    now = chain.current_semester(audit_content.DATA)

    blanks, thin, open_secs, pending, seen = [], [], [], [], 0
    pend_secs = []
    accept = "--accept-pending-baseline" in argv
    open_ders, der_seen = [], 0
    for d in dirs:
        subject = os.path.basename(d)
        if only and only not in subject:
            continue
        for name in sorted(f for f in os.listdir(d)
                           if re.fullmatch(r"ch\d+\.json", f)):
            if int(name[2:-5]) >= SUMMARY_CHAPTER_FROM:
                continue
            try:
                with open(os.path.join(d, name), encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                continue
            cards = derivation_cards(data)
            der_seen += len(cards)
            missing_der = uncovered_derivations(data, cards)
            if missing_der:
                open_ders.append((subject, name[:-5], len(missing_der),
                                  ", ".join(missing_der)))
            sections = theory_sections(data)
            if not sections:
                continue
            seen += 1
            figs = figure_count(sections)
            if figs == 0 and not has_reason(data, sections):
                blanks.append((subject, name[:-5], len(sections)))
            elif figs < len(sections):
                thin.append((subject, name[:-5], len(sections), figs))
            if pending_draw(data, sections):
                pending.append((subject, name[:-5], len(sections), figs))
            for sid in pending_sections(data, sections):
                pend_secs.append((subject, name[:-5], sid))
            missing = uncovered_sections(data, sections)
            if missing:
                # ★ 이름을 다 찍는다. 넷만 찍었더니 **사유를 쓰려면 나머지를 따로 찾아야 했다**
                #   (2026-09-09 실측: 기계공작법 17장 96절을 판정하려는데 이름이 68개 모자랐다).
                #   목록의 값어치는 「몇 개인가」가 아니라 「어느 절인가」에 있다.
                open_secs.append((subject, name[:-5], len(missing), ", ".join(missing)))

    if "--pending-only" in argv:
        blanks_shown, open_shown = blanks, open_secs
        blanks, open_secs, pending, open_ders, thin = [], [], [], [], []
    if blanks:
        print("[사유 없는 빈 장] 이론 절은 있는데 삽화가 0 개이고 사유도 안 적혔다")
        print("   ※ 사유를 적으면 내려간다 — **그리라는 뜻이 아니라 판정을 남기라는 뜻이다**")
        for subject, ch, n in chain.semester_order(blanks, sem, now):
            print("   [%s] %s %s · 이론 절 %d개 · 삽화 0"
                  % (chain.semester_tag(sem, subject), subject, ch, n))
    if open_secs:
        total_secs = sum(n for _s, _c, n, _ids in open_secs)
        print("\n[미판정 절] 그 절에 삽화도 없고 사유도 없다 — **절마다 판정을 남긴다**")
        print("   ※ 챕터 사유에 그 절 id 를 적으면 내려간다(이미 쓴 사유는 그대로 인정된다)")
        for subject, ch, n, ids in chain.semester_order(open_secs, sem, now)[:40]:
            print("   [%s] %s %s · 절 %d개 — %s"
                  % (chain.semester_tag(sem, subject), subject, ch, n, ids))
        if len(open_secs) > 40:
            print("   … 그리고 %d장 더" % (len(open_secs) - 40))
        print("   합계 %d장 · %d절" % (len(open_secs), total_secs))
    if pending:
        print("\n[그리기로 판정한 자리] 사유에 「%s」가 적힌 장 — **게이트가 아니라 목록이다**"
              % PENDING_MARK)
        print("   ※ 어느 절인지는 그 장의 사유가 이름으로 적어 두었다. 열어서 읽는다")
        for subject, ch, n, figs in chain.semester_order(pending, sem, now):
            print("   [%s] %s %s · 절 %d · 이론 삽화 %d"
                  % (chain.semester_tag(sem, subject), subject, ch, n, figs))
    if open_ders:
        total_ders = sum(n for _s, _c, n, _i in open_ders)
        print("\n[유도 카드에 그림도 사유도 없다] 유도는 식이 걸어가는 자리다")
        print("   ※ 아직 **목록이다**(게이트 아님) — 첫 실측 뒤에 문턱을 정한다")
        for subject, ch, n, ids in chain.semester_order(open_ders, sem, now)[:40]:
            print("   [%s] %s %s · 카드 %d개 — %s"
                  % (chain.semester_tag(sem, subject), subject, ch, n, ids))
        if len(open_ders) > 40:
            print("   … 그리고 %d장 더" % (len(open_ders) - 40))
        print("   합계 %d장 · %d카드 (유도 카드 전체 %d개)"
              % (len(open_ders), total_ders, der_seen))
    if thin and not fail_only:
        print("\n[밀도] 절 수보다 이론 삽화가 적은 장 — 후보다(표로 끝나는 절도 있다)")
        for subject, ch, n, figs in chain.semester_order(thin, sem, now)[:40]:
            print("   [%s] %s %s · 절 %d · 삽화 %d"
                  % (chain.semester_tag(sem, subject), subject, ch, n, figs))
        if len(thin) > 40:
            print("   … 그리고 %d건 더" % (len(thin) - 40))

    keys = ["%s/%s/%s" % t for t in pend_secs]
    base = read_pending_baseline()
    new_pending = [k for k in keys if k not in base]
    if accept and not only:
        with open(PENDING_BASELINE, "w", encoding="utf-8") as fh:
            fh.write("# 그리기로 판정했는데 삽화가 0 인 절 — audit_theory_figure_reasons ⑹ 래칫 기준선\n")
            fh.write("# 줄이 줄어드는 것은 자유다. 늘리려면 사람이 --accept-pending-baseline 로 옮긴다\n")
            fh.writelines(k + "\n" for k in sorted(keys))
        base, new_pending = set(keys), []
    if pend_secs:
        by_ch = {}
        for subject, ch, sid in pend_secs:
            by_ch.setdefault((subject, ch), []).append(sid)
        rows = [(s, c, len(v), ", ".join(v)) for (s, c), v in by_ch.items()]
        print("\n[그리기로 판정했는데 삽화 0 인 절] 사유가 그 절을 「그린다」 쪽에 적었다")
        for subject, ch, n, ids in chain.semester_order(rows, sem, now):
            print("   [%s] %s %s · 절 %d개 — %s"
                  % (chain.semester_tag(sem, subject), subject, ch, n, ids))
        print("   합계 %d장 · %d절 · 기준선 밖(새로 생김) %d절" % (len(rows), len(pend_secs), len(new_pending)))
        for k in new_pending[:20]:
            print("   [새로 생김] " + k)
        if len(new_pending) > 20:
            print("   … 새로 생김 %d절 더" % (len(new_pending) - 20))
    if "--pending-only" in argv:
        blanks, open_secs = blanks_shown, open_shown

    print("\n합계 — 이론이 있는 장 %d개 · 사유 없는 빈 장 %d개 · 미판정 절 %d개 · 밀도 후보 %d개 · 그리기로 판정한 장 %d개 · 그리기 판정 미이행 절 %d개"
          % (seen, len(blanks), sum(n for _s, _c, n, _i in open_secs), len(thin), len(pending), len(pend_secs)))
    print("※ 게이트는 「사유 없는 빈 장」·「미판정 절」·「기준선 밖 그리기 미이행 절」 셋이다 — 밀도는 후보이고 판정은 사람이 한다")
    return 1 if (blanks or open_secs or new_pending) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
