# -*- coding: utf-8 -*-
"""**문풀·연습문제에 삽화가 없으면 왜 없나** (열린 날 2026-09-10).

    python tools/audit_item_figure_reasons.py                # 전 과목 (지금 학기 먼저)
    python tools/audit_item_figure_reasons.py --only=<과목>  # 한 과목만
    python tools/audit_item_figure_reasons.py --fail-only    # 게이트에 걸리는 것만

★ **왜 열렸나** — 사용자 2026-09-10: *[발화 생략]*.
  같은 지적이 네 번 넘게 반복됐다는 것이 요점이다 — **반복되는데 세는 자가 없었다.**

  구조적 원인이 분명하다. 이론 절에는 `audit_theory_figure_reasons.py` 가 게이트로 서 있고
  유도 카드도 그 자가 목록으로 낸다. 그런데 **문풀·연습문제 층에는 자가 없다.** 빌드가 보는
  것은 「`diagrams` 가 있으면 그 SVG 가 규격에 맞나」뿐이라, **아예 안 그린 문항은 검사를
  한 줄도 안 탄다.** 그래서 「그릴 수 없어서 뺐다」와 「안 그렸다」가 구별되지 않았고,
  지적이 인스턴스로만 처리돼 같은 말이 네 번 나왔다(규칙 7 위반이 재발하는 전형적 자리다).

## 무엇을 세나

⑴ **사유 없는 문항** — `diagrams` 가 비었는데 `noDiagramReason` 도 없다. **게이트다(exit 1).**
⑵ **사유가 있는 문항** — 목록으로만 낸다. 「없어도 되는 자리」인지는 사람이 읽어 판정한다.
⑶ **그리기로 판정한 자리** — 사유에 「아직 안 그렸습니다」가 적힌 문항. 게이트가 아니라 목록이다.
    이론 쪽 자와 같은 문구를 쓴다 — 낱말이 갈리면 두 자가 다른 것을 센다.
⑷ **대안 없는 기각** — 사유가 교재 재현·답 누출·과장을 드는데 「대안:」이 없다. **게이트다.**
    후보 하나를 막은 것은 그림이 필요 없다는 뜻이 아니다(2026-09-11, 응용고체 일곱).

## ☐ 이 자가 못 보는 것 (규칙 21)

- **사유가 타당한지 안 본다.** 「판단형이라 그릴 형상이 없다」가 정말 그런지는 사람이 읽는다 —
  실제로 이 지적이 나온 자리가 그것이다(평면응력 변환 문항에 「그릴 형상이 없다」가 적혀 있었다).
- **삽화가 제 일을 하는지 안 본다.** 그건 `audit_convention_drift --check=figure-carries-the-symbols`.
- **요약·모의고사 장(`ch90` 이상)은 안 본다** — 이론 쪽 자와 같은 경계다.
- **⑷ 는 「대안:」 낱말이 있는지만 센다** — 그 대안이 타당한지는 사람이 읽는다.
- **이론 절 사유(`noTheoryDiagramReason`)의 기각은 안 본다.** ⑷ 는 문항 층만 잰다.
- **비율을 안 본다.** 한 장에서 열 문항 중 하나만 그려도 ⑴ 은 0 이 된다. 그것이 ⑵ 를 목록으로
  남겨 두는 이유다.
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

ITEM_COLLECTIONS = ("practice", "problems")
REASON_KEYS = ("noDiagramReason", "noItemDiagramReason")
SUMMARY_CHAPTER_FROM = 90   # 이론 쪽 자와 같은 경계다 — 요약·모의고사 장은 안 본다
PENDING_MARK = "아직 안 그렸습니다"


def _filled(value):
    """빈 문자열과 공백은 사유가 아니다(사유 없는 면제를 막는 것과 같은 판정선)."""
    return isinstance(value, str) and value.strip() != ""


def items_of(data):
    """문풀·연습문제를 (컬렉션 이름, 문항) 쌍으로 늘어놓는다. 순수 함수."""
    out = []
    for coll in ITEM_COLLECTIONS:
        for item in data.get(coll) or []:
            if isinstance(item, dict):
                out.append((coll, item))
    return out


def item_reason(item):
    """문항에 적힌 사유 문자열. 없으면 빈 문자열. 순수 함수."""
    for key in REASON_KEYS:
        if _filled(item.get(key)):
            return item[key]
    return ""


def bare_items(data):
    """삽화도 사유도 없는 문항 id 목록. 순수 함수.

    챕터 수준 사유가 그 문항 id 를 담고 있으면 덮인 것으로 본다 — 이론 쪽 자와 같은 약속이라
    이미 쓴 사유를 다시 쓰게 하지 않는다.
    """
    blanket = " ".join(str(data.get(k)) for k in REASON_KEYS if _filled(data.get(k)))
    out = []
    for _coll, item in items_of(data):
        if item.get("diagrams"):
            continue
        if _filled(item_reason(item)):
            continue
        iid = item.get("id") or ""
        if iid and iid in blanket:
            continue
        out.append(iid or "(id 없음)")
    return out


def excused_items(data):
    """삽화는 없고 사유만 있는 문항 id 목록. 순수 함수."""
    return [item.get("id") or "(id 없음)"
            for _coll, item in items_of(data)
            if not item.get("diagrams") and _filled(item_reason(item))]


def pending_items(data):
    """사유에 「아직 안 그렸습니다」가 적힌 문항 id 목록. 순수 함수."""
    return [item.get("id") or "(id 없음)"
            for _coll, item in items_of(data)
            if PENDING_MARK in item_reason(item)]


# 기각 낱말이 있으면 「대안:」 표시가 있어야 한다 — 후보 하나를 막고 「그림 없음」으로 닫는 것을
# 막는 문턱. 대안이 타당한지는 안 본다. 「겹치」는 뺐다 — 첫 실행 9건 중 8건이 수식·배치 설명의
# 「겹친다」였다(교재와 겹친다는 기각은 「교재」가 잡는다).
REJECTION = re.compile(r"교재|Fig|표 E|누출|재현|과장")
ALT_MARK = "대안:"


def unweighed_rejections(data):
    """교재 재현·답 누출·과장으로 기각했는데 「대안:」이 없는 문항 id 목록. 순수 함수."""
    return [item.get("id") or "(id 없음)"
            for _coll, item in items_of(data)
            if not item.get("diagrams")
            and REJECTION.search(item_reason(item))
            and ALT_MARK not in item_reason(item)]


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

    bare, excused, pending, unweighed = [], [], [], []
    seen_items = 0
    drawn = 0
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
            pairs = items_of(data)
            if not pairs:
                continue
            seen_items += len(pairs)
            drawn += sum(1 for _c, it in pairs if it.get("diagrams"))
            miss = bare_items(data)
            if miss:
                bare.append((subject, name[:-5], len(miss), ", ".join(miss)))
            exc = excused_items(data)
            if exc:
                excused.append((subject, name[:-5], len(exc), ", ".join(exc)))
            pen = pending_items(data)
            if pen:
                pending.append((subject, name[:-5], len(pen), ", ".join(pen)))
            unw = unweighed_rejections(data)
            if unw:
                unweighed.append((subject, name[:-5], len(unw), ", ".join(unw)))

    if bare:
        total = sum(n for _s, _c, n, _i in bare)
        print("[사유 없는 문항] 삽화도 없고 사유도 없다 — **게이트다**")
        print("   ※ 그리거나, 왜 안 그리는지 `noDiagramReason` 에 적으면 내려간다")
        for subject, ch, n, ids in chain.semester_order(bare, sem, now)[:40]:
            print("   [%s] %s %s · %d개 — %s"
                  % (chain.semester_tag(sem, subject), subject, ch, n, ids))
        if len(bare) > 40:
            print("   … 그리고 %d장 더" % (len(bare) - 40))
        print("   합계 %d장 · %d문항" % (len(bare), total))
    if pending:
        total = sum(n for _s, _c, n, _i in pending)
        print("\n[그리기로 판정한 자리] 사유에 「%s」가 적힌 문항 — 목록이다" % PENDING_MARK)
        for subject, ch, n, ids in chain.semester_order(pending, sem, now)[:40]:
            print("   [%s] %s %s · %d개 — %s"
                  % (chain.semester_tag(sem, subject), subject, ch, n, ids))
        print("   합계 %d장 · %d문항" % (len(pending), total))
    if unweighed:
        total = sum(n for _s, _c, n, _i in unweighed)
        print("\n[대안 없는 기각] 교재 재현·답 누출·과장으로 기각했는데 「%s」이 없다 — **게이트다**"
              % ALT_MARK)
        print("   ※ 다른 도식을 검토했으면 그 결과를 「%s」 뒤에 적고, 안 했으면 검토한다" % ALT_MARK)
        for subject, ch, n, ids in chain.semester_order(unweighed, sem, now)[:40]:
            print("   [%s] %s %s · %d개 — %s"
                  % (chain.semester_tag(sem, subject), subject, ch, n, ids))
        print("   합계 %d장 · %d문항" % (len(unweighed), total))
    if excused and not fail_only:
        total = sum(n for _s, _c, n, _i in excused)
        print("\n[사유는 있다] 삽화 없이 사유만 적힌 문항 — **사유가 타당한지는 사람이 읽는다**")
        for subject, ch, n, ids in chain.semester_order(excused, sem, now)[:40]:
            print("   [%s] %s %s · %d개 — %s"
                  % (chain.semester_tag(sem, subject), subject, ch, n, ids))
        if len(excused) > 40:
            print("   … 그리고 %d장 더" % (len(excused) - 40))
        print("   합계 %d장 · %d문항" % (len(excused), total))

    print("\n합계 — 문항 %d개 · 삽화 있는 문항 %d개 · 사유 없는 문항 %d개 · 그리기로 판정 %d개"
          " · 대안 없는 기각 %d개"
          % (seen_items, drawn,
             sum(n for _s, _c, n, _i in bare),
             sum(n for _s, _c, n, _i in pending),
             sum(n for _s, _c, n, _i in unweighed)))
    print("※ 게이트는 「사유 없는 문항」과 「대안 없는 기각」 둘이다 — 사유의 타당성은 사람이 판정한다")
    return 1 if (bare or unweighed) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
