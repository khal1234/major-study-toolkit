r"""교재의 **예제(EXAMPLE)** 를 우리 챕터가 다뤘는지 훑는다 — 후보만 낸다.

## 왜 열렸나 (2026-09-08)

사용자 원칙: *[발화 생략]*.

**그때까지 이걸 재는 자가 없었다.** 삽화 쪽은 「있나」(`geometry-in-formula-only`)와
「제 일을 하나」(`figure-carries-the-symbols`)를 재기 시작했는데, **본문이 교재의 어느 개념을
통째로 안 다뤘나**는 아무도 안 봤다. `chNN.textbook-map.md` 는 **절 단위** 대조표라
예제 단위로는 안 걸린다.

계기가 된 실례: 어느 장이 「공기표준 해석」을 가르치면서 문항은 전부 냉공기표준(비열 일정)만
썼다. 교재는 같은 사이클을 두 판으로 푸는 예제를 두고 있는데 우리 쪽에는 그 판이 0개였다 —
그 장의 상태표를 만들어 놓고도 **쓰는 자리가 없었다.**

## 무엇을 재나

1. 교재 PDF 에서 `EXAMPLE <장>.<번호>` 표시와 **바로 다음 줄(제목)** 을 뽑는다.
2. 제목에서 **내용어**만 남긴다(Determining·Evaluating·Analyzing·the·of… 는 뺀다).
3. 그 낱말이 우리 챕터 JSON 어디에든 있는지 본다.

☐ **이 자가 못 보는 것 — 세 가지. 그래서 게이트가 아니라 후보다.**
  · **우리 본문은 한국어**다. 영문 낱말이 걸리는 자리는 `sourceRef`(교재 절 이름을 영문으로
    인용한다)와 **영문 문항 지문**뿐이다. 한국어로만 다룬 개념은 «없다» 로 잘못 나온다.
  · **범위 밖 예제**가 섞인다. 교재의 뒷절(압축성 유동 등)이 수업 범위가 아니면 «없다» 가 맞다.
  · 낱말이 **있다고 다뤘다는 뜻도 아니다** — 한 번 스쳐 지나가도 걸린다.
  · ★★ **넷째가 제일 크다 — 우리는 소재를 일부러 바꾼다.** 독자성 규칙 12⑵ 가
    *[발화 생략]* 이므로,
    교재 예제의 **소재 낱말**(gearbox·drying oven·cogeneration)은 **안 걸리는 것이 정상**이다.
    즉 이 자는 **우리가 지키는 규칙과 정면으로 부딪힌다** — 그래서 「절반 미만」 목록에는
    멀쩡한 자리가 섞이고, **판정에 쓸 수 있는 것은 「하나도 안 걸린」 쪽**이다.
    실측(2026-09-08): 어떤 장의 「엑서지 원가」 예제가 후보로 떴는데, 열어 보니 그 장에
    식 7.22 와 비용 계산이 **이미 있었다** — 소재(열펌프 대 다른 설비)만 달랐다.

## 쓰는 법

    python tools/audit_textbook_examples.py --only=<과목>
    python tools/audit_textbook_examples.py --only=<과목> --refresh   # 캐시를 다시 만든다

첫 실행은 PDF 를 통째로 훑어 느리다. 결과는 `data/<과목>/.textbook-examples.json` 에 캐시하고
다음부터는 그것을 읽는다(교재가 바뀌지 않는 한 다시 뽑을 이유가 없다).
"""

import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# 제목의 뼈대만 남긴다 — 이 낱말들은 어느 예제에나 있어서 「걸렸다」를 부풀린다.
TITLE_STOPWORDS = frozenset("""
a an the of for with and or in on to at from by is are as its use using
determining evaluating analyzing considering comparing exploring
calculating computing finding investigating examining assessing
example problem effect effects performance analysis analyses
""".split())
CACHE_NAME = ".textbook-examples.json"


def _chapter_number(stem):
    match = re.search(r"(\d+)", stem)
    return match.group(1) if match else None


def extract_examples(pdf_path):
    """PDF 전체에서 `EXAMPLE n.m` 과 다음 줄(제목)을 뽑는다."""
    import pdfplumber                                                   # noqa: E402
    import extract_textbook as et                                       # noqa: E402

    marker = re.compile(r"EXAMPLE\s+(\d+)\.(\d+)")
    found = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            for _side, box in et.columns(page):
                text = (page.crop(box).extract_text() or "")
                lines = text.splitlines()
                for index, line in enumerate(lines):
                    hit = marker.search(line)
                    if not hit:
                        continue
                    key = f"{hit.group(1)}.{hit.group(2)}"
                    # ★ **두 줄을 잇는다** (2026-09-08, 첫 실행이 자를 검정한 자리).
                    #   2단 조판이라 제목이 한 줄에 안 들어가고 잘린다 — 한 줄만 읽으면
                    #   «Determining the Effect of Back» 처럼 **주어가 사라진 제목**이 되고,
                    #   남은 낱말이 흔한 것 하나뿐이라 아무 데나 걸려 「다뤘다」로 통과한다.
                    tail = lines[index + 1:index + 3]
                    title = " ".join(part.strip() for part in tail).strip()
                    # 같은 예제가 여러 쪽에 걸쳐 인용된다 — **처음 나온 것**이 본문이다.
                    if key not in found:
                        found[key] = {"page": page_number, "title": title}
    return found


def load_examples(data_dir, pdf_fragment, refresh=False):
    cache = os.path.join(data_dir, CACHE_NAME)
    if os.path.isfile(cache) and not refresh:
        with open(cache, encoding="utf-8") as fh:
            return json.load(fh)
    import extract_textbook as et                                       # noqa: E402
    # ★ `find_pdf` 는 **후보 목록**을 돌려준다 — 매핑 규약이 「조각마다 정확히 1개」라
    #   둘 이상이면 그것부터 고칠 일이지 아무거나 골라 넘어갈 자리가 아니다.
    path = et.find_pdf(pdf_fragment)
    if isinstance(path, (list, tuple)):
        if len(path) != 1:
            raise RuntimeError(
                f"교재 후보가 {len(path)}개다 — 조각을 좁힐 것: {pdf_fragment!r}")
        path = path[0]
    print(f"  [훑는 중] {os.path.basename(path)} — 처음이라 오래 걸린다")
    found = extract_examples(path)
    with open(cache, "w", encoding="utf-8") as fh:
        json.dump(found, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return found


def title_keywords(title):
    words = re.findall(r"[A-Za-z][A-Za-z\-]+", title)
    return [w for w in words if len(w) > 3 and w.lower() not in TITLE_STOPWORDS]


def audit_subject(subject, refresh=False):
    data_dir = os.path.join(ROOT, "data", subject)
    map_path = os.path.join(data_dir, "textbook-pdf-map.json")
    if not os.path.isfile(map_path):
        print(f"[해당 없음] {subject} — `textbook-pdf-map.json` 이 없다 (교재 대조 대상이 아니다)")
        return 0
    with open(map_path, encoding="utf-8") as fh:
        pdf_map = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
    if not pdf_map:
        print(f"[해당 없음] {subject} — 매핑이 비어 있다")
        return 0

    fragment = next(iter(pdf_map.values()))
    if isinstance(fragment, list):
        fragment = fragment[0]
    examples = load_examples(data_dir, fragment, refresh=refresh)

    total, missing = 0, 0
    for chapter_file in sorted(pdf_map):
        stem = os.path.splitext(chapter_file)[0]
        number = _chapter_number(stem)
        if number is None:
            continue
        mine = [k for k in examples if k.split(".")[0] == str(int(number))]
        if not mine:
            continue
        path = os.path.join(data_dir, chapter_file)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            blob = fh.read().lower()
        rows = []
        for key in sorted(mine, key=lambda k: int(k.split(".")[1])):
            words = title_keywords(examples[key]["title"])
            hits = [w for w in words if w.lower() in blob]
            total += 1
            # ★ **문턱은 절반이다** (2026-09-08, 첫 실행이 자를 검정한 자리).
            #   처음엔 「하나도 안 걸릴 때」만 신고했더니, 제목에 남은 흔한 낱말 하나가
            #   엉뚱한 자리에 걸려 **실제로 안 다룬 예제가 통과했다**(압축성 유동 둘).
            #   절반으로 두면 흔한 낱말 하나로는 못 빠져나간다.
            if words and len(hits) * 2 < len(words):
                missing += 1
                rows.append((key, examples[key]["title"], words, hits))
        if rows:
            # ★ **0건과 「절반 미만」을 가른다** (2026-09-08, 두 번째 검정).
            #   제목을 두 줄로 이으면 **본문 첫 줄까지 딸려 온다**(«The wall of an industrial dr»).
            #   그 낱말은 예제의 소재이지 우리가 반드시 담아야 할 개념이 아니라서 분모를
            #   부풀리고 **멀쩡한 장을 후보로 만든다.** 잘린 제목과 본문을 기계가 못 가르므로
            #   비율만으로는 판정이 안 선다 — 대신 **하나도 안 걸린 것**을 따로 세운다.
            #   그쪽은 소재·개념·절 이름 어느 것도 우리 챕터에 없다는 뜻이라 신호가 세다.
            strong = [r for r in rows if not r[3]]
            weak = [r for r in rows if r[3]]
            if strong:
                print(f"\n-- {subject} / {stem} — ★ **하나도 안 걸린** 예제 {len(strong)}건 --")
                for key, title, words, _hits in strong:
                    print(f"     EXAMPLE {key} — {title[:64]}")
                    print(f"        찾은 낱말: {', '.join(words[:6])}")
            if weak:
                print(f"\n-- {subject} / {stem} — 절반 미만 {len(weak)}건 (분모에 본문 낱말이 섞인다) --")
                for key, title, words, hits in weak:
                    print(f"     EXAMPLE {key} — {title[:64]}")
                    print(f"        낱말 {len(hits)}/{len(words)} · 걸린 것 [{', '.join(hits)}]")
    print(f"\n합계 — {subject}: 예제 {total}개 중 **{missing}개**가 후보")
    print("※ 판정하지 않는다 — 한국어로만 다룬 것과 범위 밖 절이 섞인다(독스트링의 ☐ 셋).")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", required=True, help="과목 폴더 이름")
    parser.add_argument("--refresh", action="store_true", help="캐시를 다시 만든다")
    args = parser.parse_args()
    return audit_subject(args.only, refresh=args.refresh)


if __name__ == "__main__":
    raise SystemExit(main())
