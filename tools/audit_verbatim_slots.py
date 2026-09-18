# -*- coding: utf-8 -*-
"""「글자 그대로 옮겼다」고 선언한 문항이 정말 원본과 같은가.

    python tools/audit_verbatim_slots.py                # 전 과목
    python tools/audit_verbatim_slots.py --fail-only    # 어긋난 것만
    python tools/audit_verbatim_slots.py --diff=ch92-e01  # 그 슬롯이 **어디서** 갈렸는지

★ **열린 날 2026-09-08.** 모의고사 장(ch90·ch91·…)에는 **verbatim 슬롯**이 있다 — 원본 장의
  문항을 글자 그대로 옮겨 놓고 「이 배치가 원본을 안 건드렸다」를 스스로 증명하는 앵커다.
  그런데 `응용열역학 ch90-e03` 이 「글자 그대로 같다」고 선언해 놓고 원본과 **한 단어가 갈려
  있었다**(`자기착화` 대 `자발 착화`). **아무 검사도 그 선언을 안 보고 있었다** — 선언이
  산문에만 있었고, 산문은 스스로를 검사하지 않는다.
  앵커가 조용히 어긋나면 그 앵커는 「같다」를 증명하는 것이 아니라 **증명한다고 주장만** 한다.

★ **무엇을 재나.** `sourceRef` 가 `출처 층 **verbatim**. \\`<원본 id>\\`` 로 시작하는 문항을 찾아,
  같은 과목 폴더의 그 원본과 **핵심 네 필드**(`prompt`·`answer`·`solutionOutline`·`difficulty`)를
  글자 단위로 견준다. 네 필드는 24개 선언문이 **전부 공통으로** 주장하는 것이다.

★ **못 보는 것(규칙 21 — 자를 먼저 잰다):**
  · `relatedFormulas`·`diagrams` 는 **일부러 다른** 자리라 안 본다(참조가 깨지거나 시험지 면이
    영어여야 해서 갈라 둔 것이고, 그 사유는 각 `sourceRef` 가 적는다).
  · 선언을 **안 한** 복제는 못 본다. 이 자는 「선언과 실물이 맞나」만 재고 「선언했어야 하나」는 못 잰다.
  · 원본을 **같은 과목 폴더** 안에서만 찾는다. 과목을 건너간 복제는 「원본 없음」으로 신고한다.
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
import audit_content  # noqa: E402

# 선언문의 꼴 — 「출처 층 **verbatim**」 뒤 **첫 백틱 id** 가 원본이다.
VERBATIM_RE = re.compile(r"출처\s*층\s*\*\*verbatim\*\*.{0,40}?`([A-Za-z0-9_\-]+)`", re.S)
# 24개 선언문이 전부 공통으로 주장하는 네 필드.
CORE_FIELDS = ("prompt", "answer", "solutionOutline", "difficulty")
COLLECTIONS = ("problems", "practice")


def source_id(source_ref):
    """`sourceRef` 산문에서 원본 문항 id 를 뽑는다. 순수 함수 — 테스트가 직접 부른다."""
    m = VERBATIM_RE.search(source_ref or "")
    return m.group(1) if m else None


def chapter_of(item_id):
    """`ch09-q02` → `ch09`. 순수 함수."""
    return (item_id or "").split("-", 1)[0]


# ★ 첫 실행이 24개 중 14개를 어긋남으로 냈고, 그중 하나를 펴 보니 **자가 너무 엄했다**(규칙 21).
#   `ch91-e03` 의 유일한 차이는 본문 속 상호참조가 `ch11-q01` → `ch91-e01` 로 바뀐 것이었다.
#   사본이 자기 장 안의 짝을 가리키는 것은 **옳은 차이**다 — 원본 id 를 그대로 두면 시험지에서
#   존재하지 않는 문항을 가리킨다. verbatim 이 약속하는 것은 **같은 말**이지 같은 주소가 아니다.
#   그래서 견주기 전에 문항 id 를 자리표로 바꾼다.
#   ☐ 대가: 내용 차이가 **하필 id 하나뿐**인 경우도 같은 것으로 본다(그런 자리는 없다고 본다).
ITEM_ID_RE = re.compile(r"ch\d+-[A-Za-z]+\d+")


def normalize(value):
    """견주기 전에 문항 id 를 자리표로 바꾼다. 순수 함수 — 테스트가 직접 부른다."""
    return ITEM_ID_RE.sub("<문항id>", json.dumps(value, ensure_ascii=False, sort_keys=True))


def field_diff(copy_item, origin_item, fields=CORE_FIELDS):
    """어긋난 필드 이름 목록. 순수 함수 — 테스트가 직접 부른다.

    없는 필드는 **양쪽 다 없을 때만** 같은 것으로 본다(한쪽만 없으면 어긋난 것이다).
    """
    return [f for f in fields
            if normalize(copy_item.get(f, None)) != normalize(origin_item.get(f, None))]


def items_of(chapter):
    for coll in COLLECTIONS:
        for item in chapter.get(coll) or []:
            if isinstance(item, dict):
                yield item


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def first_text_gap(a, b, width=90):
    """두 값이 **처음 갈리는 자리**를 사람이 읽을 수 있게 낸다. 순수 함수.

    리스트(풀이 단계)면 몇 번째 항목이 갈렸는지, 문자열이면 몇 번째 글자부터 갈렸는지를 낸다.
    """
    if isinstance(a, list) and isinstance(b, list):
        for i in range(max(len(a), len(b))):
            x = a[i] if i < len(a) else "(없음)"
            y = b[i] if i < len(b) else "(없음)"
            if json.dumps(x, ensure_ascii=False, sort_keys=True) != \
               json.dumps(y, ensure_ascii=False, sort_keys=True):
                return ("%d번째 단계" % (i + 1),
                        json.dumps(x, ensure_ascii=False)[:width],
                        json.dumps(y, ensure_ascii=False)[:width])
        return ("길이만 다름", str(len(a)), str(len(b)))
    sa, sb = str(a), str(b)
    i = 0
    while i < min(len(sa), len(sb)) and sa[i] == sb[i]:
        i += 1
    return ("%d번째 글자" % (i + 1), sa[max(0, i - 20):i + width], sb[max(0, i - 20):i + width])


def scan(subject_dir):
    """(어긋남 목록, 훑은 슬롯 수). 어긋남 = (과목, 사본 id, 원본 id, 사유)."""
    files = sorted(f for f in os.listdir(subject_dir)
                   if re.fullmatch(r"ch\d+\.json", f))
    chapters = {}
    for name in files:
        try:
            chapters[name[:-5]] = load(os.path.join(subject_dir, name))
        except (ValueError, OSError) as exc:
            chapters[name[:-5]] = {"__error__": str(exc)}
    subject = os.path.basename(subject_dir)
    bad, seen = [], 0
    for ch_name, chapter in chapters.items():
        for item in items_of(chapter):
            origin_id = source_id(item.get("sourceRef", ""))
            if not origin_id:
                continue
            seen += 1
            origin_ch = chapters.get(chapter_of(origin_id))
            if origin_ch is None:
                bad.append((subject, ch_name + "::" + str(item.get("id")), origin_id,
                            "원본 장이 이 과목 폴더에 없다"))
                continue
            origin = next((x for x in items_of(origin_ch)
                           if x.get("id") == origin_id), None)
            if origin is None:
                bad.append((subject, ch_name + "::" + str(item.get("id")), origin_id,
                            "원본 문항 id 를 못 찾았다"))
                continue
            drift = field_diff(item, origin)
            if drift:
                bad.append((subject, ch_name + "::" + str(item.get("id")), origin_id,
                            "어긋난 필드 — " + ", ".join(drift)))
    return bad, seen


def show_diff(want):
    """`--diff=<사본 id>` — 그 슬롯의 어긋난 필드를 하나씩 펴서 보여 준다."""
    for d in audit_content.subject_dirs():
        files = sorted(f for f in os.listdir(d) if re.fullmatch(r"ch\d+\.json", f))
        chapters = {}
        for name in files:
            try:
                chapters[name[:-5]] = load(os.path.join(d, name))
            except (ValueError, OSError):
                continue
        for chapter in chapters.values():
            for item in items_of(chapter):
                if item.get("id") != want:
                    continue
                origin_id = source_id(item.get("sourceRef", ""))
                # ★ 같은 id 가 여러 과목에 있다(`ch91-e03` 은 두 과목에 다 있었다). verbatim 을
                #   **선언한** 쪽을 찾을 때까지 계속 돈다 — 첫 동명이인에서 멈추면 못 찾는다.
                if not origin_id:
                    continue
                origin_ch = chapters.get(chapter_of(origin_id))
                origin = next((x for x in items_of(origin_ch or {})
                               if x.get("id") == origin_id), None)
                if origin is None:
                    print("원본을 못 찾았다:", origin_id)
                    return 1
                print("%s ← %s" % (want, origin_id))
                for f in field_diff(item, origin):
                    where, mine, theirs = first_text_gap(item.get(f), origin.get(f))
                    print("  [%s] %s" % (f, where))
                    print("    사본: " + mine)
                    print("    원본: " + theirs)
                return 0
    print("그 id 를 못 찾았다:", want)
    return 1


def load_baseline(path):
    """이미 알고 있는 어긋남(빚) — `과목 | 사본위치 | 사유`. 순수 함수가 읽는 꼴은 아래 텍스트다.

    **사유가 빈 줄은 면제로 안 친다** — 사유 없이 끄는 것은 이 리포가 없애려는 「무기한 대기」다.
    """
    known = {}
    if not os.path.isfile(path):
        return known
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3 or not parts[2]:
                continue
            known[parts[0] + "::" + parts[1]] = parts[2]
    return known


BASELINE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "docs", "verbatim-슬롯-어긋남-기준선.txt")


def main(argv):
    for a in argv:
        if a.startswith("--diff="):
            return show_diff(a.split("=", 1)[1])
    fail_only = "--fail-only" in argv
    known = load_baseline(BASELINE)
    total_bad, total_seen, subjects = [], 0, 0
    for d in audit_content.subject_dirs():
        bad, seen = scan(d)
        if seen:
            subjects += 1
        total_bad += bad
        total_seen += seen
        if seen and not fail_only:
            print("[%s] verbatim 슬롯 %d개 · 어긋남 %d건" % (os.path.basename(d), seen, len(bad)))
    fresh = [b for b in total_bad if (b[0] + "::" + b[1]) not in known]
    old = [b for b in total_bad if (b[0] + "::" + b[1]) in known]
    for subject, where, origin_id, why in fresh:
        print("  [어긋남] %s %s ← %s : %s" % (subject, where, origin_id, why))
    # ★ 빚은 **보이게** 찍는다 — 숨기면 그 기준선이 도장이 된다.
    for subject, where, origin_id, _why in old:
        print("  [기준선·빚] %s %s ← %s : %s" % (subject, where, origin_id,
                                              known[subject + "::" + where]))
    # ★ 「0건」이 「안 봤다」와 구별되게 **훑은 수를 함께** 낸다(AGENTS 규칙 11).
    print("verbatim 슬롯 %d개 · 과목 %d개 · 새 어긋남 %d건 · 기준선의 빚 %d건"
          % (total_seen, subjects, len(fresh), len(old)))
    return 1 if fresh else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
