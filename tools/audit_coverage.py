"""커버리지 감사 — 교재·강의자료에 있는 것이 우리 콘텐츠에 있나.

정본 설계는 `docs/2026-09-07-커버리지-감사-입력-실태.md` 다. 세 갈래를 낸다:

    ⓐ 교재에 있는데 우리에 없다      원서 기준의 구멍
    ⓑ 강의자료에만 있는데 우리에 없다  시험은 교수가 낸다 — 가장 값어치 있는 칸
    ⓒ 우리에만 있다                  자체 발굴(정상)인지 근거 없는 창작(절대 규칙 2)인지

    python tools/audit_coverage.py --only 기계공작법
    python tools/audit_coverage.py                 # coverage-sources.json 이 있는 과목 전부

**왜 열렸나.** 사용자가 기계공작법 ch10 을 책 없이 수업만 듣고 읽으며 여섯 건을 짚었고,
*[발화 생략]* 이라 했는데 **답할 근거가 리포에 없었다.**

**입력은 과목이 갖는다** — `data/<과목>/coverage-sources.json`(AGENTS 「공통 도구에 과목별
사실을 박지 않는다」). 그 파일이 없는 과목은 **대상이 아니지 실패가 아니다**(exit 0).

★★ **이 자는 후보만 낸다. 판정은 사람이 한다.**
교재에 있어도 수업 범위 밖인 절이 많고, 우리에만 있는 말이 곧 창작인 것도 아니다.
**그 판정은 채팅이 아니라 `coverage-sources.json` 의 `"판정"` 에 사유와 함께 적는다** —
장마다 `{"용어": "왜 안 고치나"}`. 가려진 개수는 계속 찍고, 후보에 더는 없는 판정은
「낡음」으로 되돌려 준다(판정이 조용히 썩는 것을 막는다).

★ **이 자가 못 보는 것**(규칙 21 — 새 자의 첫 출력은 자의 검정이다):

- **언어가 갈리는 자리.** 교재는 영문, 강의자료·우리 콘텐츠는 한국어다. 영문 용어는
  우리가 `주조(casting)` 꼴로 **괄호 병기**했을 때만 「있다」로 잡힌다. 병기 없이 한국어로만
  다룬 개념은 **ⓐ 후보로 잘못 뜬다** — 그래서 이 칸은 「없다」가 아니라 「병기가 없다」다.
- **뜻이 같은 다른 말.** 문자열 포함으로만 재므로 `수축공`/`shrinkage cavity` 같은 짝을 못 잇는다.
- **PDF 조판.** 2단 조판에서 단어 사이 공백이 사라진다(`Columnardendrite`). 그래서 양쪽 다
  **영숫자·한글만 남겨 정규화**해 견준다 — 띄어쓰기 차이는 자동으로 무시되지만,
  대신 짧은 말(정규화 5자 미만)은 오탐이 많아 아예 안 본다.
- **이미지 강의자료.** 텍스트가 안 나오는 PDF 는 `[텍스트 없음]` 으로 찍고 **훑은 것으로
  세지 않는다**. `extract_textbook --render` 로 사람이 읽어야 한다.
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import pdfplumber  # noqa: E402

from extract_textbook import find_pdf  # noqa: E402

SOURCES_NAME = "coverage-sources.json"

# 정규화 뒤 이보다 짧은 말은 안 본다 — `sprue`·`riser` 급 짧은 낱말은 다른 낱말 안에
# 우연히 들어가 「있다」로도, 조판이 붙여 놓은 덩어리 안에서 「없다」로도 쉽게 틀린다.
MIN_TERM = 5
# 이보다 긴 불릿은 낱말이 아니라 문장이다 — 문장은 같은 내용을 다른 말로 써도 안 맞으므로
# 「빠뜨렸나」를 잴 수 없다. 실측: 이 문턱이 없을 때 ⓑ 73건 중 대부분이 문장 조각이었다.
MAX_KEYWORD = 12
# 저자 전용 필드는 독자에게 안 보인다 — 여기 적힌 «§10.2.2 를 다시 열어 대조했다» 같은 글이
# 굵게 표시돼 있어 ⓒ 후보로 올라왔다. 변경점 판정이 이 필드들을 빼는 것과 같은 이유다.
AUTHOR_ONLY = ("changeNote", "sourceRef", "rationale", "source", "reviewNote")

HEADING_RE = re.compile(r"^\s*(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\s+(\S.*)$")
KEYTERMS_START = ("keyterms",)
KEYTERMS_STOP = ("bibliography", "summary", "references", "reviewquestions",
                 "qualitativeproblems", "quantitativeproblems", "problems")
# 한글(영문) 병기 — 강의자료가 정의하는 용어의 거의 전부가 이 꼴이다.
PAIR_RE = re.compile(r"([가-힣][가-힣A-Za-z0-9 ]{0,20})\(\s*([A-Za-z][A-Za-z \-]{2,30})\s*\)")
BULLET_RE = re.compile(r"^\s*[•·▪]\s*(\S.{1,22})\s*$")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def norm(text):
    """영숫자·한글만 남긴다 — 2단 조판이 지운 공백과 우리 띄어쓰기를 같은 자리에 놓는다."""
    return re.sub(r"[^0-9a-z가-힣]+", "", text.lower())


def pdf_lines(path, two_column):
    """줄을 모은다. 2단 조판이면 전폭과 좌/우 단을 모두 훑는다.

    `extract_textbook.chapter_outline` 과 같은 이유다 — 절 헤딩은 2단을 가로질러 조판돼
    단으로 crop 하면 잘리고, 본문·용어 목록은 단 안에 있어 전폭으로만 보면 좌우가 섞인다.

    ★ **단이 하나인 자료를 반으로 자르면 줄이 통째로 잘린 채 후보가 된다.** 첫 실행에서
    강의 슬라이드가 그랬다 — `용융 금속이 주형에 공급된 이후 주` 처럼 오른쪽이 잘린 조각이
    ⓑ 후보로 올라왔다. 그래서 단 수를 입력이 선언한다(교재는 2단, 슬라이드는 1단).
    """
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            x0, top, x1, bottom = page.bbox
            mid = (x0 + x1) / 2.0
            boxes = [page.bbox]
            if two_column:
                boxes += [(x0, top, mid, bottom), (mid, top, x1, bottom)]
            for box in boxes:
                out.extend((page.crop(box).extract_text() or "").splitlines())
    return out


def textbook_terms(lines, chapter_no):
    """절 제목과 장 끝 Key Terms 목록. 둘 다 교재가 「이 장의 핵심」이라고 스스로 표시한 것이다.

    ★ `chapter_no` 로 거른다. `N.M` 꼴은 **표의 숫자 칸**에도 그대로 나타나서
    `절 0.34  0.56 0.90 1.` · `절 14.72 g/cm 3` 같은 것이 절 후보로 올라왔다.
    이 장의 절은 앞자리가 반드시 장 번호이고, 그 한 줄이 표 잡음을 통째로 지운다.
    """
    terms = []
    # 절은 **번호마다 하나**여야 한다. 전폭·좌·우를 다 훑으므로 같은 제목이 잘린 채로도
    # 들어오고(`11.3.1 Evaporative-patternCasting(Lost-fo`), 정규화 문자열로 dedupe 하면
    # 잘린 것과 온전한 것이 서로 다른 후보가 돼 같은 절이 두 번 신고된다.
    sections = {}
    in_keys = False
    in_examples = False
    for line in lines:
        stripped = line.strip()
        flat = norm(stripped)
        m = HEADING_RE.match(stripped)
        if m:
            # 장 첫 쪽 목차는 절 목록 뒤에 `Example:` 을 두고 예제를 **같은 번호 꼴**로 잇는다.
            # 그걸 절로 세면 `10.1 SolidificationTimesforVariousShapes` 가 절 후보가 된다.
            same_chapter = m.group(1).split(".")[0] == str(chapter_no)
            if not in_examples and same_chapter:
                # 목차 줄은 제목 뒤에 쪽번호가 붙는다(`10.2 SolidificationofMetals282`).
                title = re.sub(r"\d+$", "", m.group(2)).strip()
                if len(norm(title)) >= MIN_TERM and title[:1].isupper():
                    prev = sections.get(m.group(1))
                    if prev is None or len(title) > len(prev):
                        sections[m.group(1)] = title
            continue
        in_examples = flat.startswith("example")
        if flat in KEYTERMS_START:
            in_keys = True
            continue
        if in_keys:
            if flat in KEYTERMS_STOP or not flat:
                in_keys = False
                continue
            # 용어 목록은 3단이라 한 줄에 둘 이상이 오는데 **단 사이가 한 칸일 때가 있다.**
            # 반대로 여러 낱말로 된 용어는 이 조판에서 이미 붙어 나온다(`Columnardendrite`).
            # 그러니 공백 하나로 갈라도 잃는 것이 없고, 안 가르면 `Casting Mushyzone` 처럼
            # 서로 다른 두 용어가 한 후보로 뭉쳐 둘 다 못 보게 된다.
            for piece in stripped.split():
                if len(norm(piece)) >= MIN_TERM and not re.search(r"[가-힣]", piece):
                    terms.append(("용어", piece.strip()))

    def order(num):
        return tuple(int(p) for p in num.split("."))

    head = [("절 " + num, sections[num]) for num in sorted(sections, key=order)]
    return head + dedupe(terms)


def lecture_terms(lines):
    """강의자료가 스스로 표시한 것 — 절 제목 · 한글(영문) 병기 · **짧은** 키워드 불릿.

    ★ 첫 실행에서 배운 것: 긴 불릿은 **문장**이라 후보로 못 쓴다. `용융 금속의 주형 투입`
    같은 줄은 우리 본문이 같은 내용을 다른 말로 이미 쓰고 있어도 문자열로는 절대 안 맞고,
    그래서 ⓑ 가 「빠뜨린 것」이 아니라 「문장이 다르다」로 가득 찬다. 낱말 길이로 자른다.
    """
    terms = []
    for line in lines:
        stripped = line.strip()
        m = HEADING_RE.match(stripped)
        if m and len(norm(m.group(2))) >= MIN_TERM:
            terms.append(("절 " + m.group(1), m.group(2).strip()))
            continue
        for ko, en in PAIR_RE.findall(stripped):
            if len(norm(ko)) >= 2:
                terms.append(("병기", ko.strip() + "(" + en.strip() + ")"))
        b = BULLET_RE.match(stripped)
        if b and MIN_TERM <= len(norm(b.group(1))) <= MAX_KEYWORD:
            terms.append(("항목", b.group(1).strip()))
    return dedupe(terms)


def dedupe(pairs):
    seen = set()
    out = []
    for kind, text in pairs:
        key = norm(text)
        if key in seen:
            continue
        seen.add(key)
        out.append((kind, text))
    return out


def walk_strings(node, out):
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for key, value in node.items():
            if key.startswith("_") or key in AUTHOR_ONLY:
                continue
            walk_strings(value, out)
    elif isinstance(node, list):
        for item in node:
            walk_strings(item, out)


def chapter_text(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out = []
    walk_strings(data, out)
    return "\n".join(out)


def our_terms(text):
    """우리 굵은 말 중 **교재와 대조할 수 있는 것**과, 대조 못 한 개수.

    ⓒ 의 함정: 우리 콘텐츠는 한국어이고 교재는 영문이라 한국어만으로 된 굵은 말은
    교재에 있어도 언제나 「우리에만 있다」로 나온다. 그건 발견이 아니라 자의 눈멀음이다.
    그래서 **영문을 품은 것만**(병기 `게이팅(gating)` 이거나 그 자체가 영문) 후보로 내고,
    나머지는 개수만 밝힌다 — 세지 않고 안 낸 것과 구별되게(규칙 11).
    """
    checkable, blind = [], 0
    seen = set()
    for raw in BOLD_RE.findall(text):
        item = raw.strip()
        if len(norm(item)) < MIN_TERM or len(norm(item)) > MAX_KEYWORD * 2:
            continue
        # 문장은 낱말이 아니다 — 마침표로 끝나거나 종결어미가 붙은 것은 강조 문구다.
        if item.endswith((".", "!", "?")) or re.search(r"(니다|습니다|해요|이다)$", item):
            continue
        key = norm(item)
        if key in seen:
            continue
        seen.add(key)
        m = re.search(r"[A-Za-z][A-Za-z \-']{2,}", item)
        if m:
            checkable.append(m.group(0).strip())
        else:
            blind += 1
    return checkable, blind


def chapter_raw(path):
    """파일 원문 그대로 — 저자 전용 필드까지 포함한다. 절 번호 인용을 세는 데만 쓴다."""
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def present(term, blob):
    """정규화한 덩어리 안에 있나. 병기 용어는 한글·영문 어느 쪽이 잡혀도 있는 것으로 본다.

    ★★ **복수형을 안 벗기면 없는 일을 만든다** (고친 날 2026-09-08). 교재 용어 목록은
      `High-speed steels`·`Lathes`처럼 **복수로** 적히는데 본문은 단수로 쓴다. 실측:
      ch22 는 이미 `**고속도강**(high-speed steel, HSS)` 이라고 **병기까지 해 두었는데도**
      후보로 떴다 — 자가 만든 헛일이다. 끝의 `s` 하나를 벗겨 한 번 더 본다.
    ☐ 여전히 못 보는 것: `-ies`·불규칙 복수, 그리고 붙어 버린 두 낱말의 가운데 토막.
    """
    inner = re.match(r"^(.*)\((.*)\)$", term)
    if inner:
        return (present(inner.group(1), blob) or present(inner.group(2), blob))
    key = norm(term)
    if key in blob:
        return True
    return len(key) > 4 and key.endswith("s") and key[:-1] in blob


def resolve(fragment):
    """PDF 조각 하나 → 경로 하나. 후보가 0개거나 2개 이상이면 그 사실을 그대로 돌려준다."""
    hits = find_pdf(fragment)
    if len(hits) == 1:
        return hits[0], ""
    if not hits:
        return None, "PDF 없음"
    return None, "후보 %d개 — 조각을 더 구체적으로" % len(hits)


def read_source(fragment, cache, two_column):
    """한 PDF 의 줄 목록. 같은 PDF 를 여러 장이 가리켜도 한 번만 연다."""
    key = (fragment, two_column)
    if key in cache:
        return cache[key]
    path, why = resolve(fragment)
    if path is None:
        cache[key] = (None, why)
        return cache[key]
    lines = pdf_lines(path, two_column)
    if not any(line.strip() for line in lines):
        cache[key] = (None, "텍스트 없음 — 이미지 PDF 다 (extract_textbook --render 로 사람이 읽는다)")
        return cache[key]
    cache[key] = (lines, "")
    return cache[key]


def audit_subject(subject_dir, limit=None):
    """한 과목의 ⓐⓑⓒ 후보. 돌려주는 것은 (행 목록, 훑은 장 수, 못 연 입력 목록)."""
    with open(os.path.join(subject_dir, SOURCES_NAME), encoding="utf-8") as fh:
        sources = json.load(fh)

    cache = {}
    rows = []
    scanned = 0
    skipped = []
    for name in sorted(sources):
        if name.startswith("_") or not re.fullmatch(r"ch\d{2}\.json", name):
            continue
        if limit and name[:4] not in limit:
            continue
        chapter_path = os.path.join(subject_dir, name)
        if not os.path.isfile(chapter_path):
            skipped.append((name, "챕터 파일이 없다"))
            continue
        entry = sources[name]
        reader = chapter_text(chapter_path)
        ours = norm(reader)
        raw = chapter_raw(chapter_path)

        book_terms, book_blob = [], ""
        frag = entry.get("textbook") or ""
        if frag:
            lines, why = read_source(frag, cache, True)
            if lines is None:
                skipped.append((name + " 교재", frag + " — " + why))
            else:
                book_terms = textbook_terms(lines, int(name[2:4]))
                book_blob = norm("\n".join(lines))

        lec_terms, lec_blob = [], ""
        for frag in entry.get("lecture") or []:
            lines, why = read_source(frag, cache, False)
            if lines is None:
                skipped.append((name + " 강의자료", frag + " — " + why))
                continue
            lec_terms += lecture_terms(lines)
            lec_blob += norm("\n".join(lines))
        lec_terms = dedupe(lec_terms)

        if not book_terms and not lec_terms:
            continue
        scanned += 1

        # ★★ **사용자 판정 2026-09-08 — 두 칸의 성격이 여기서 갈렸다.**
        #   ⑴ 미인용 절: *[발화 생략]* → 안 다룬 절은 **누락이 아니라 판단**이다.
        #      그래서 줄로 안 내고 **개수만** 찍는다. 세는 것을 멈추지는 않는다 — 범위가
        #      바뀌면 그 수가 움직이고, 그때 다시 열면 된다(규칙 11: 안 세면 「없다」와
        #      「안 봤다」가 같아진다).
        #   ⑵ 미등장 용어: *[발화 생략]* → 교재 Key Terms 690개를
        #      통째로 내면 대부분이 본문 어휘라 손댈 자리가 안 보인다. **그 장의 절 제목에
        #      들어 있는 용어**(그 장이 이름을 걸고 다루는 공정·장비)만 남긴다 — 시험이 묻는
        #      것이 그 이름이고, 나머지는 개수만 찍는다.
        # ★ **두 판정이 여기서 겹쳐진다.** 범위 밖 절은 판단이므로(⑴), 그 절의 용어도 대상이
        #   아니다 — 그래서 **인용한 절의 제목**만 기준으로 삼는다. 안 그러면 ⑴ 로 뺀 절
        #   (셸주조·슬러시·스퀴즈…)의 이름이 ⑵ 로 되돌아온다.
        cited_heads = [norm(t) for k, t in book_terms
                       if k.startswith("절 ") and k[2:] in raw]
        # ★★ **사람이 내린 판정은 파일에 둔다** (신설 2026-09-08). 위 두 판정을 통과한
        #   후보라도 「그 공정을 이 자료가 안 다룬다」는 판정이 붙을 수 있다 — 그건 병기
        #   구멍이 아니라 **콘텐츠 신설**이라 범위 판정에 걸린다. 판정을 채팅에만 두면
        #   다음 회차가 같은 열한 줄을 다시 판정한다(AGENTS 「기준선·판정은 파일에」).
        #   ☐ 지우지 않고 **센다** — 판정이 몇 개를 가렸는지 안 보이면 「없다」와
        #     「안 봤다」가 같아진다(규칙 11).
        judged = {norm(t): why for t, why in (entry.get("판정") or {}).items()}
        used = set()
        uncited, off_exam, ruled = 0, 0, 0
        for kind, term in book_terms:
            if kind.startswith("절 "):
                if kind[2:] in raw:
                    continue
                uncited += 1
                continue
            if present(term, ours):
                continue
            # ☐ 용어 목록은 3단 조판이라 **낱말 조각**이 섞인다(`operation,`·`processes.`·
            #   `materials,`). 문장부호로 끝나는 것은 용어가 아니다 — 그것까지 후보로 내면
            #   사람이 목록을 못 믿는다.
            if term.rstrip().endswith((",", ".", ";", ":")):
                off_exam += 1
                continue
            if not any(norm(term) in h for h in cited_heads):
                off_exam += 1
                continue
            if norm(term) in judged:
                used.add(norm(term))
                ruled += 1
                continue
            rows.append((name[:4], "ⓐ", kind, term + "  ← 다루는 절의 제목에 걸린 이름인데 본문에 없다"))
        if uncited:
            skipped.append((name + " ⓐ절",
                            "인용 안 한 절 %d개 — **범위 판단으로 본다**(사용자 2026-09-08 "
                            "«지금 범위 그대로 둔다»). 범위가 바뀌면 이 수가 움직인다" % uncited))
        if off_exam:
            skipped.append((name + " ⓐ용어",
                            "절 제목에 없는 교재 용어 %d개 — 본문 어휘라 병기 대상이 아니다"
                            "(사용자 2026-09-08 «시험에 나올 용어만»)" % off_exam))
        if ruled:
            skipped.append((name + " ⓐ판정",
                            "사람이 판정해 뺀 용어 %d개 — 사유는 %s 의 「판정」"
                            % (ruled, SOURCES_NAME)))
        stale = sorted(set(judged) - used)
        if stale:
            # 판정도 낡는다 — 병기를 채워 넣으면 그 판정은 아무것도 안 가리는데,
            # 안 찍으면 파일에 남은 줄이 여전히 유효한 것처럼 보인다.
            skipped.append((name + " ⓐ판정(낡음)",
                            "후보에 없는 판정 %d개 — 병기가 채워졌거나 절 인용이 바뀌었다. "
                            "지울 것: %s" % (len(stale), ", ".join(stale))))
        for kind, term in lec_terms:
            if present(term, ours) or present(term, book_blob):
                continue
            rows.append((name[:4], "ⓑ", kind, term))
        checkable, blind = our_terms(chapter_text(chapter_path))
        for text in checkable:
            if present(text, book_blob) or present(text, lec_blob):
                continue
            rows.append((name[:4], "ⓒ", "굵게", text))
        if blind:
            skipped.append((name + " ⓒ",
                            "영문 병기가 없어 대조 못 한 굵은 말 %d개 — 교재가 영문이라 "
                            "한국어만으로는 「우리에만 있다」를 판정할 수 없다" % blind))
    return rows, scanned, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="과목 폴더 이름 (없으면 입력이 있는 과목 전부)")
    ap.add_argument("--chapter", default="", help="쉼표로 구분한 chNN (없으면 전부)")
    ap.add_argument("--bucket", default="", help="ⓐ·ⓑ·ⓒ 중 하나만 본다 (a/b/c 로도 받는다)")
    ap.add_argument("--limit", type=int, default=25, help="칸마다 장당 몇 줄까지 찍나")
    args = ap.parse_args()

    base = os.path.join(ROOT, "data")
    names = [args.only] if args.only else sorted(os.listdir(base) if os.path.isdir(base) else [])
    want_bucket = {"a": "ⓐ", "b": "ⓑ", "c": "ⓒ"}.get(args.bucket.lower(), args.bucket)
    chapters = {c.strip() for c in args.chapter.split(",") if c.strip()}

    subjects = 0
    scanned_total = 0
    totals = {"ⓐ": 0, "ⓑ": 0, "ⓒ": 0}
    by_kind = {}
    for name in names:
        subject_dir = os.path.join(base, name)
        if not os.path.isfile(os.path.join(subject_dir, SOURCES_NAME)):
            continue
        subjects += 1
        rows, scanned, skipped = audit_subject(subject_dir, chapters)
        scanned_total += scanned
        print("\n-- %s --  훑은 장 %d개" % (name, scanned))
        for chapter, bucket, kind, term in rows:
            totals[bucket] += 1
            by_kind[bucket + ("절" if kind.startswith("절") else kind)] = \
                by_kind.get(bucket + ("절" if kind.startswith("절") else kind), 0) + 1
        shown = {}
        for chapter, bucket, kind, term in rows:
            if want_bucket and bucket != want_bucket:
                continue
            key = (chapter, bucket)
            shown[key] = shown.get(key, 0) + 1
            if shown[key] > args.limit:
                continue
            print("  [%s] %s %-7s %s" % (bucket, chapter, kind, term))
        for key, count in sorted(shown.items()):
            if count > args.limit:
                print("  … %s %s 외 %d건" % (key[0], key[1], count - args.limit))
        for what, why in skipped:
            print("  [입력 못 씀] %s — %s" % (what, why))

    print("\n합계 — ⓐ %d · ⓑ %d · ⓒ %d  · 훑은 과목 %d개 · 훑은 장 %d개"
          % (totals["ⓐ"], totals["ⓑ"], totals["ⓒ"], subjects, scanned_total))
    if by_kind:
        print("     갈래별 — " + " · ".join("%s %d" % (k, v) for k, v in sorted(by_kind.items())))
    print("※ 판정하지 않는다 — 교재에 있어도 수업 범위 밖인 절이 많고, ⓐ 는 「없다」가 아니라"
          " 「그 말이 그 꼴로 안 보인다」이다(독스트링 「이 자가 못 보는 것」).")
    if subjects == 0:
        print("\n입력을 선언한 과목이 없다 — data/<과목>/%s 를 만들 것." % SOURCES_NAME)
        return 0
    if scanned_total == 0:
        sys.stderr.write("입력은 선언됐는데 한 장도 못 훑었다 — PDF 조각이 안 맞는다.\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
