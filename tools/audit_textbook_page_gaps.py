# -*- coding: utf-8 -*-
"""장이 **교재의 어느 쪽을 읽었는지**를 `sourceRef` 의 쪽 인용으로 재고, 가운데 구멍을 찾는다.

    python tools/audit_textbook_page_gaps.py                 # 전 과목
    python tools/audit_textbook_page_gaps.py --gap=8         # 문턱을 바꿔서
    python tools/audit_textbook_page_gaps.py --only=<과목>   # 한 과목만
    python tools/audit_textbook_page_gaps.py --all           # 구멍이 없는 장까지 전부 찍는다

★ **열린 날 2026-09-08 — 사용자가 수업 중에 잡았다.** 어느 장이 교재의 [발화 생략]를 한 번도 안 다루고 있었다. 그 장의 `sourceRef` 가 인용한 PDF 쪽을
  뽑아 보니 **345 다음이 356** 이었고, 그 사이 열 쪽을 열어 보니 정상상태 제어체적 엑서지
  수지와 비유동엑서지가 통째로 거기 있었다. **앞과 뒤는 읽고 가운데를 건너뛴 것**이다.
  사용자의 다음 물음이 이 자를 만든 이유다 — *[발화 생략]*.

★ **이 자가 재는 것은 「무엇을 안 다뤘나」가 아니라 「어디를 안 인용했나」다.** 둘은 다르다:
  · 인용 없이 다룬 절이 있을 수 있다(그래도 대조 흔적이 없다는 것은 그 자체로 볼 자리다).
  · 교재의 그 쪽이 예제·연습문제·사진이라 안 옮기는 것이 옳을 수도 있다.
  그래서 **후보만 낸다.** 판정은 그 쪽을 실제로 열어 보는 사람이 한다
  (`python tools/extract_textbook.py --pdf <조각> --pages a-b`).

★ **문턱은 고른 값이다.** 기본 8쪽 — 교재의 한 절이 대개 3~6쪽이라 그보다 넓은 구멍이라야
  **절 하나가 통째로** 숨을 수 있다. 실사고의 구멍은 11쪽이었고 그 안에 두 절이 들어 있었다.

★ **셋째 꼴을 2026-09-08 에 배웠다 — 「옆 장이 읽고 있는 쪽」**. 기계공작법 ch22 가
  655~659(교재 21장의 공구마모·테일러 수명식)를 배경으로 인용하고 자기 장(676~693)으로
  건너뛰어 **16쪽짜리 가짜 구멍**을 만들었다. 그 사이는 21장의 나머지이고 `ch21.json` 의
  몫이다. 그래서 구멍을 낼 때 **같은 과목의 다른 장이 그 쪽을 인용하는지** 먼저 본다 —
  절반 넘게 덮여 있으면 「구멍」이 아니라 「옆 장」으로 따로 낸다(덮인 비율을 함께 찍는다).

☐ 못 보는 것: 쪽을 아예 안 적은 장(그 장은 「인용 0」으로 따로 센다) · 장의 진짜 시작·끝 쪽
  (그건 PDF 를 열어야 안다 — 그래서 **양 끝의 누락은 못 잡고 가운데 구멍만 잡는다**) ·
  옆 장이 그 쪽을 **인용만 하고 안 다뤘을** 가능성(인용은 대조 흔적이지 보증이 아니다).
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

# `PDF p.341` · `PDF p.340-342` 두 꼴을 함께 받는다.
PAGE_RE = re.compile(r"PDF\s*p\.\s*(\d{1,4})(?:\s*[-–~]\s*(\d{1,4}))?")
DEFAULT_GAP = 8      # 구멍 문턱 [쪽] — 교재의 한 절이 대개 3~6쪽이라 그보다 넓어야 절이 통째로 숨는다
# ★ **첫 실행이 자를 재 줬다 (규칙 21).** 44건 중 큰 쪽 여남은은 전부 같은 꼴이었다 —
#   한 장이 **교재와 강의자료를**, 또는 **두 권을** 함께 인용하면 쪽 축이 섞여
#   「4쪽 다음이 283쪽」 같은 가짜 구멍이 생긴다. 장 하나의 쪽 폭은 교재에서 20~70쪽이므로
#   **폭이 이보다 훨씬 넓으면 한 축이 아니다.** 그 장들은 구멍으로 세지 않고 따로 모아 낸다.
DEFAULT_SPAN = 80
# 구멍 쪽의 절반 넘게를 **같은 과목의 다른 장**이 인용하면 그건 그 장의 몫이다.
# 절반으로 잡은 이유: 옆 장이 통째로 덮으면 1.0 에 가깝고, 진짜 구멍은 0 에 가깝다 —
# 실측(기계공작 ch22)의 가짜 구멍은 16쪽 중 16쪽이 ch21 의 것이었다.
SIBLING_COVER_MIN = 0.5


def sibling_cover(missing, others):
    """구멍 쪽 가운데 다른 장이 인용한 비율. 순수 함수 — 테스트가 직접 부른다."""
    if not missing:
        return 0.0
    return len(set(missing) & set(others)) / float(len(missing))


def pages_in(text):
    """산문에서 인용된 PDF 쪽 번호 집합. 순수 함수 — 테스트가 직접 부른다."""
    out = set()
    for a, b in PAGE_RE.findall(text or ""):
        lo = int(a)
        hi = int(b) if b else lo
        if hi < lo or hi - lo > 60:      # 뒤집힌 범위·오탐은 앞 값만 쓴다
            hi = lo
        out.update(range(lo, hi + 1))
    return out


def largest_gap(pages):
    """(구멍 크기, 앞 쪽, 뒤 쪽). 쪽이 둘 미만이면 (0, None, None). 순수 함수."""
    ordered = sorted(pages)
    best = (0, None, None)
    for lo, hi in zip(ordered, ordered[1:]):
        if hi - lo - 1 > best[0]:
            best = (hi - lo - 1, lo, hi)
    return best


def scan_chapter(path):
    """(쪽 집합, 가장 큰 구멍). `sourceRef` 만 본다 — 본문은 쪽을 안 적는다."""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    pages = set()
    try:
        data = json.loads(raw)
    except ValueError:
        return set(), (0, None, None)

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "sourceRef" and isinstance(v, str):
                    pages.update(pages_in(v))
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return pages, largest_gap(pages)


def main(argv):
    gap_min, span_max = DEFAULT_GAP, DEFAULT_SPAN
    only = None
    show_all = "--all" in argv
    for a in argv:
        if a.startswith("--gap="):
            gap_min = int(a.split("=", 1)[1])
        if a.startswith("--max-span="):
            span_max = int(a.split("=", 1)[1])
        if a.startswith("--only="):
            only = a.split("=", 1)[1]

    if audit_content.reject_unmatched_only(only, audit_content.subject_dirs()):
        return 2
    print("교재 쪽 인용의 가운데 구멍 (구멍 %d쪽 이상 · 쪽 폭 %d 이하 · 후보만 낸다)\n"
          % (gap_min, span_max))
    holes, mixed, silent, sibling, seen = [], [], [], [], 0
    for d in audit_content.subject_dirs():
        subject = os.path.basename(d)
        if only and only not in subject:
            continue
        names = sorted(f for f in os.listdir(d) if re.fullmatch(r"ch\d+\.json", f))
        by_chapter = {n: scan_chapter(os.path.join(d, n)) for n in names}
        for name in names:
            pages, (size, lo, hi) = by_chapter[name]
            seen += 1
            if not pages:
                silent.append((subject, name[:-5]))
                continue
            span = max(pages) - min(pages)
            if span > span_max:
                mixed.append((subject, name[:-5], min(pages), max(pages)))
                continue
            if size >= gap_min:
                others = set()
                for other, (other_pages, _) in by_chapter.items():
                    if other != name:
                        others |= other_pages
                cover = sibling_cover(range(lo + 1, hi), others)
                row = (subject, name[:-5], min(pages), max(pages), size, lo, hi, cover)
                # 딱 절반이면 **구멍 쪽에 남긴다** — 안 보이는 쪽으로 넘기는 실수가 더 비싸다.
                (sibling if cover > SIBLING_COVER_MIN else holes).append(row)
            elif show_all:
                print("  [ok] %s %s — %d~%d쪽 · 가장 큰 구멍 %d쪽"
                      % (subject, name[:-5], min(pages), max(pages), size))
    for subject, ch, lo_p, hi_p, size, lo, hi, cover in holes:
        print("  [구멍] %s %s — %d~%d쪽을 인용했는데 **%d 다음이 %d** 다 (%d쪽이 빈다%s)"
              % (subject, ch, lo_p, hi_p, lo, hi, size,
                 "" if cover == 0 else " · 그중 %.0f%%는 옆 장이 인용한다" % (cover * 100)))
    if sibling:
        print("\n  ※ 옆 장이 읽고 있는 쪽 %d개 — 구멍이 아니라 **그 장의 몫**이다:" % len(sibling))
        for subject, ch, _lo_p, _hi_p, size, lo, hi, cover in sibling:
            print("     %s %s — %d 다음이 %d (%d쪽) · 그 쪽의 %.0f%%를 같은 과목의 다른 장이 인용한다"
                  % (subject, ch, lo, hi, size, cover * 100))
    if mixed:
        print("\n  ※ 쪽 축이 섞여 못 재는 장 %d개 — 한 장이 두 출처(교재+강의자료 등)를 인용한다:"
              % len(mixed))
        print("     " + ", ".join("%s %s(%d~%d)" % m for m in mixed[:10])
              + (" …" if len(mixed) > 10 else ""))
    if silent:
        print("\n  ※ 쪽을 한 번도 안 적은 장 %d개 — 이 자로는 못 잰다(대조 흔적이 없다):"
              % len(silent))
        print("     " + ", ".join("%s %s" % s for s in silent[:12])
              + (" …" if len(silent) > 12 else ""))
    # ★ 「0건」이 「안 봤다」와 갈리게 훑은 수를 함께 낸다(AGENTS 규칙 11).
    print("\n합계 — 훑은 장 %d개 · 구멍 %d개 · 옆 장 몫 %d개 · 축이 섞인 장 %d개 · 인용 없는 장 %d개"
          % (seen, len(holes), len(sibling), len(mixed), len(silent)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
