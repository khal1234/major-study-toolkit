#!/usr/bin/env python
"""연습문제가 교재 원문을 그대로 옮겼는지 감사한다 (읽기 전용).

**왜 만들었나 (열린 날 2026-08-01, 사용자 지적).**
`sourceRef` 에 `Prob. 2-19C 재구성` 이라 적혀 있었지만 원문과 대조하니 **한 글자도 안 바뀐
복제**였다. 표본 4건이 전부 그랬다(q04·q10 은 100% 동일, q06 은 동사 하나, q02 는 도입부만).

**무엇이 새어나갔나.** 리포에는 관련 규칙이 **둘이나** 있다 —
규칙 3(교재 문장을 데이터에 그대로 복사하지 말 것)과 규칙 12⑷(연습문제는 숫자만 바꾼 것이
아니어야 한다). 그런데 **그것을 확인하는 기계가 0개**였고, `sourceRef` 의 '재구성'이라는
**자기보고가 검증을 대신하고 있었다.** 같은 날 아침에 찾은 출처 절 번호 오류와 같은 구조다.

**왜 원문을 저장하지 않고 해시로 하나.**
원문 텍스트를 리포에 넣으면 그 자체가 규칙 3 위반이고, 공개 배포 시 저작권 위험이 된다.
n-gram 을 SHA256 으로 접으면 **원문을 복원할 수 없으면서** "N 단어 연속 일치"는 검출된다.
지문 파일은 `.gitignore` 로 빠지며(크기 때문), 없으면 `--build` 로 다시 만든다.

    python tools/audit_problem_originality.py --build        # 지문 생성(교재 PDF 필요, 느림)
    python tools/audit_problem_originality.py                # 전 챕터 감사
    python tools/audit_problem_originality.py --chapter ch02.json

**이 도구는 빌드에 넣지 않았다.** 먼저 전수 규모를 재고, 그 결과를 보고 편입 여부를 정한다
(측정 전에 error 로 박으면 몇 건이 걸릴지 모르는 채 빌드를 세우게 된다).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from audit_content import CHAPTERS, DATA, load                          # noqa: E402
from extract_textbook import columns, find_pdf                          # noqa: E402
# 판정 로직은 **빌드와 같은 것**을 쓴다 — 여기 사본을 두면 도구와 빌드의 기준이 갈라진다.
from buildlib.checks_originality import (                               # noqa: E402
    COPY_WORDS, MIN_WORDS_PER_MB, NEAR_WORDS, SIZES, corpus_verdict,
    fingerprint_path, iter_prompts, load_sets, longest_run, longest_span,
    ngram_hashes, norm_words,
)

FP_DIR = os.path.join(DATA, ".textbook-fingerprint")

# ★ 과목별 매핑은 **그 과목 폴더**에서 읽는다 (2026-08-01 dynamics 실측 · 같은 날 사용자 지시로 폴백 제거).
#
# 사용자 지적 — 이 도구를 만들 때 특정 과목 이름을 하드코딩하지 말고 다른 과목도 쓸 수 있게 하라는 것(다른 과목 채팅에서도 같은 요청이 반복됨).
#
# 여기에는 **열역학 5챕터를 담은 `PDF_FOR` 폴백이 남아 있었다.** 폴백이 있으면
# ⑴ 공통 코드가 특정 과목을 계속 알고 있게 되고 ⑵ 다른 과목은 **매핑이 없다는 사실조차
# 드러나지 않은 채** '매핑 없음'으로 조용히 지나간다. 그래서 폴백을 없애고
# **모든 과목이 같은 방식(자기 폴더의 파일)으로만** 동작하게 한다 — 열역학도 예외가 아니다.
# 잠금장치: test_checks.py::test_originality_pdf_map_is_subject_local ·
#           test_tools_do_not_hardcode_a_subject
PDF_MAP_FILE = os.path.join(DATA, "textbook-pdf-map.json")


def pdf_fragment(chapter):
    """이 챕터가 대조할 교재 PDF 조각들의 **목록**. 오직 과목 폴더의 매핑에서만 온다(폴백 없음).

    ★ 매핑 값은 문자열 하나이거나 **목록**이다 (목록 2026-08-01 신설).
      **한 강의노트가 교재 여러 장에 걸치는 과목이 있다.** 기계재료 강의노트3의 표지는
      `Structures of Metals and Ceramics` 라 역서 **3장(결정질 고체) + 12장(세라믹)** 을
      함께 다루고, 강의노트7·8·12도 마찬가지다(`.claude/SUBJECT.md` 대응표 — 미리 아는
      재발이 4건이다). 값을 하나만 받으면 나머지 장은 **지문에 아예 안 들어가** 그 부분을
      베껴도 `정상` 으로 나온다 — 이 도구가 없애려던 '안 본 0건'이 도구 안에서 재현된다.
    """
    try:
        with open(PDF_MAP_FILE, encoding="utf-8") as fh:
            local = json.load(fh)
    except (OSError, ValueError):
        local = {}
    val = local.get(chapter)
    if isinstance(val, str):
        return [val]
    return list(val or [])

# ★ 지문은 「챕터의 것」이 아니라 **「교재 조각 집합의 것」**이다 (2026-08-25 실측).
#
# 실사고: 기계공작법은 장별 PDF가 없어 네 장이 **같은 212MB 전권**을 가리킨다. 그런데
# `--build` 가 장마다 처음부터 훑어, ⑴ 같은 지문을 네 번 만들고(ch10·ch11·ch12 의 sha256 이
# **완전히 같았다**) ⑵ 그 한 번이 7.6GB 까지 자라 남은 메모리 1.9GB 를 넘겼다.
# 다른 세션이 프로세스를 죽여야 했고 ch13 은 지문이 안 남았다.
#
# 두 자리를 고친다:
#   ⑴ **조각 집합이 같으면 지문을 복사한다** — `corpus-index.json` 이 챕터 → 해석된 PDF 경로
#      목록을 적어 둔다. 경로 목록이 정본이지 `source`(파일 이름)가 아니다 — 폴더가 다른 동명
#      파일이 있으면 이름만으로는 같은 말뭉치라고 못 한다.
#   ⑵ **pdfplumber 의 페이지 캐시를 장마다 비운다** — 초당 56MB 로 자란 것이 이 캐시다.
#      페이지 객체가 char 사전을 붙들고 있어 「나중에 지우겠지」가 성립하지 않는다.
#
# 잠금 test_checks.py::test_originality_fingerprint_is_shared_by_corpus.
CORPUS_INDEX = os.path.join(FP_DIR, "corpus-index.json")


def corpus_index():
    """챕터 → {paths, source, words}. 못 읽으면 빈 사전(있는 지문을 다시 만들 뿐이라 안전하다)."""
    try:
        with open(CORPUS_INDEX, encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (OSError, ValueError):
        return {}


def corpus_index_put(chapter, entry):
    idx = corpus_index()
    idx[chapter] = entry
    os.makedirs(FP_DIR, exist_ok=True)
    with open(CORPUS_INDEX, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(idx, fh, ensure_ascii=False, indent=1, sort_keys=True)


def corpus_bytes(paths):
    """교재 조각들의 바이트 합. **하나라도 못 재면 `None`** — 부분 합은 밀도를 부풀린다."""
    total = 0
    for p in (paths or []):
        try:
            total += os.path.getsize(p)
        except OSError:
            return None
    return total or None


def chapter_verdict(chapter):
    """`(판정, 밀도, 낱말수)` — 그 챕터 말뭉치가 교재와 **대조 가능한가**.

    지문·색인이 없으면 `("모름", None, None)`. 읽기만 한다.
    """
    ent = corpus_index().get(chapter) or {}
    words = ent.get("words")
    if words is None:
        return "모름", None, None
    verdict, density = corpus_verdict(words, corpus_bytes(ent.get("paths")))
    return verdict, density, words


def verdict_line(chapter):
    """감사·`--build` 가 함께 쓰는 한 줄. **「0건」과 「못 본 0」이 여기서 갈린다.**"""
    verdict, density, words = chapter_verdict(chapter)
    if verdict == "모름":
        return "[대조 가능성] 모름 — 말뭉치 색인이 없거나 교재 조각을 못 읽었다", verdict
    tail = "%.0f낱말/MB (문턱 %d · 말뭉치 %d낱말)" % (density, MIN_WORDS_PER_MB, words)
    if verdict == "못 봄":
        return ("[대조 가능성] **못 봄** — " + tail
                + " · 이 챕터의 「0건」은 «없다» 가 아니라 «못 봤다» 다"), verdict
    return "[대조 가능성] 대조됨 — " + tail, verdict


def shared_fingerprint(chapter, paths):
    """같은 조각 집합의 지문이 이미 있으면 그 챕터 이름. 없으면 None. 순수 조회."""
    for other, ent in sorted(corpus_index().items()):
        if other == chapter or list(ent.get("paths") or []) != list(paths):
            continue
        if os.path.exists(fingerprint_path(DATA, other)):
            return other
    return None


def has_prompts(chapter):
    """이 챕터에 대조할 지문이 있나. 순수 조회 — `--build` 의 실패 판정이 쓴다.

    ★ **「매핑 없음」이 정당한 자리가 있다** — 과목 개요(ch00)처럼 문항이 0건인 챕터다.
      그런 곳까지 실패로 내면 전 과목의 빌드가 멈춘다. 그래서 판정선을 **「잴 것이 있는데
      안 재고 있나」** 로 잡는다.
    """
    try:
        return any(True for _ in iter_prompts(load(os.path.splitext(chapter)[0])))
    except Exception:
        return False                      # 파일이 없거나 못 읽으면 이 자의 몫이 아니다


def build(chapter):
    """교재 PDF 전체를 훑어 n-gram 해시를 만든다. 원문은 저장하지 않는다.

    같은 PDF 조각 집합을 가리키는 챕터가 이미 지문을 만들었으면 **다시 훑지 않고 복사한다**
    (위 주석의 실사고). 훑을 때는 페이지마다 pdfplumber 캐시를 비워 메모리를 묶어 둔다.
    """
    import shutil
    import pdfplumber
    frags = pdf_fragment(chapter)
    if not frags:
        return None, "매핑 없음 — data/<과목>/textbook-pdf-map.json 에 " + chapter + " 항목을 넣을 것"
    paths = []
    for frag in frags:
        hits = find_pdf(frag)
        if len(hits) != 1:
            return None, ("PDF 후보 %d개 — %s" % (len(hits), frag))
        paths.append(hits[0])

    twin = shared_fingerprint(chapter, paths)
    if twin:
        ent = corpus_index()[twin]
        os.makedirs(FP_DIR, exist_ok=True)
        shutil.copyfile(fingerprint_path(DATA, twin), fingerprint_path(DATA, chapter))
        corpus_index_put(chapter, {"paths": list(paths), "source": ent.get("source", ""),
                                   "words": ent.get("words", 0)})
        return {"source": ent.get("source", ""), "words": ent.get("words", 0),
                "reused": twin}, None

    words = []
    for path in paths:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                for _tag, box in columns(page):
                    words += norm_words(page.crop(box).extract_text() or "")
                # 이 한 줄이 없으면 페이지마다 char 사전이 쌓여 전권 한 번에 수 GB 가 된다.
                flush = getattr(page, "flush_cache", None)
                if flush:
                    flush()
    data = {
        "source": " + ".join(os.path.basename(p) for p in paths),
        "words": len(words),
        "ngrams": {str(n): sorted(ngram_hashes(words, n)) for n in SIZES},
    }
    os.makedirs(FP_DIR, exist_ok=True)
    with open(fingerprint_path(DATA, chapter), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh)
    corpus_index_put(chapter, {"paths": list(paths), "source": data["source"],
                               "words": data["words"]})
    return data, None


def audit_chapter(chapter):
    """(id, 단어수, 최장연속, sourceRef 요약, 걸린 구간) 목록. 파일만 읽는다.

    마지막 칸은 **우리 문장에서 잘라낸 말**이다 — 교재 원문이 아니라 우리가 쓴 것이라
    출력해도 규칙 3에 걸리지 않고, 부분차용 판정에는 이게 없으면 아무것도 못 한다.
    """
    sets = load_sets(DATA, chapter)
    if sets is None:
        return None
    ch = load(os.path.splitext(chapter)[0])
    # 순회 범위는 **빌드와 같은 것**(`iter_prompts`)을 쓴다 — 도구가 더 좁게 보면
    # 도구의 "0건"이 빌드의 error 와 어긋나고, 사람은 도구 쪽을 믿는다.
    src_of = {str(it.get("id") or "?"): str(it.get("sourceRef") or "")
              for key in ("problems", "practice") for it in (ch.get(key) or [])}
    rows = []
    for pid, prompt in iter_prompts(ch):
        words = norm_words(prompt)
        run, at = longest_span(words, sets)
        rows.append((pid, len(words), run, src_of.get(pid, "")[:40],
                     " ".join(words[at:at + run])))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="교재 PDF에서 지문을 만든다(느림)")
    ap.add_argument("--chapter", default="", help="chNN.json 하나만")
    args = ap.parse_args()

    # ★ 순회 대상은 **이 과목에 실재하는 챕터**다 (2026-08-01 수정).
    #   예전에는 `sorted(PDF_FOR)` 를 돌았는데, 그 사전은 열역학 챕터만 담고 있어서
    #   다른 과목에서는 후보가 0개가 되고 감사가 `정상 0` 을 찍었다 — 통과처럼 보이지만
    #   **한 건도 안 본 것**이다. 이 도구가 잡으려는 것이 바로 '자기보고가 검증을 대신하는' 부류인데
    #   도구 자신이 같은 함정에 빠져 있었다.
    chapters = ([args.chapter] if args.chapter
                else [c + ".json" for c in CHAPTERS])

    if args.build:
        dead, blind = [], []
        for c in chapters:
            data, err = build(c)
            if err:
                print("[지문] %-11s %s" % (c, err))
                if not err.startswith("매핑 없음") or has_prompts(c):
                    dead.append((c, err))
                continue
            if data.get("reused"):
                print("[지문] %-11s %d단어 ← %s (%s 와 같은 교재 조각이라 복사했다)"
                      % (c, data["words"], data["source"], data["reused"]))
            else:
                print("[지문] %-11s %d단어 ← %s" % (c, data["words"], data["source"]))
            # ★ 지문을 **만들었다는 것**과 그 지문이 교재와 **대조된다는 것**은 다르다.
            #   여기서 갈라 놓지 않으면 다음 감사의 「0건」이 통과와 같은 얼굴로 나온다.
            line, verdict = verdict_line(c)
            print("           " + line)
            if verdict != "대조됨" and has_prompts(c):
                blind.append((c, line))
        if dead:
            print("\n★ 지문을 못 만든 챕터 %d개 — **이 과목의 「0건」은 「못 본 0」이다.**" % len(dead))
            for c, err in dead:
                print("   %-11s %s" % (c, err))
        if blind:
            print("\n★ 지문은 있는데 **교재와 대조가 안 되는** 챕터 %d개 — "
                  "**이 과목의 「0건」은 「못 본 0」이다.**" % len(blind))
            for c, line in blind:
                print("   %-11s %s" % (c, line))
            print("   원인은 정규화가 `[a-z0-9]+` 라 **한글이 교재 쪽에서도 지워지는 것**이다"
                  " — 문턱을 낮추는 것은 처방이 아니다(검사 완화).")
        return 1 if (dead or blind) else 0

    print("연속 일치 단어 수 — %d↑ 복제 의심 · %d↑ 부분 차용 (원문은 저장하지 않는다)"
          % (COPY_WORDS, NEAR_WORDS))
    total = {"copy": 0, "near": 0, "ok": 0}
    # ★ 「잰 0」과 「못 본 0」을 갈라 센다 — 합계 한 줄이 둘을 같은 얼굴로 내던 자리다.
    unseen = {"chapters": 0, "prompts": 0, "lines": []}
    measured = 0
    for c in chapters:
        rows = audit_chapter(c)
        if rows is None:
            print("\n-- %s : 지문 없음 — `--build` 를 먼저 돌릴 것" % c)
            continue
        measured += 1
        flagged = [r for r in rows if r[2] >= NEAR_WORDS]
        print("\n-- %s : %d문항 중 %d건 표시" % (c, len(rows), len(flagged)))
        line, verdict = verdict_line(c)
        print("   " + line)
        if verdict != "대조됨":
            unseen["chapters"] += 1
            unseen["prompts"] += len(rows)
            unseen["lines"].append("%-11s %s" % (c, line))
        for pid, nw, run, src, span in sorted(flagged, key=lambda r: -r[2]):
            tag = "복제의심" if run >= COPY_WORDS else "부분차용"
            ratio = (100.0 * run / nw) if nw else 0.0
            print("   %-8s %s  연속 %2d / 전체 %2d 단어 (%.0f%%)   %s"
                  % (pid, tag, run, nw, ratio, src))
            print("            걸린 말: \"%s\"" % span)
        for _pid, _nw, run, _src, _span in rows:
            total["copy" if run >= COPY_WORDS else "near" if run >= NEAR_WORDS else "ok"] += 1
    print("\n합계 — 복제의심 %d · 부분차용 %d · 정상 %d"
          % (total["copy"], total["near"], total["ok"]))
    if unseen["chapters"]:
        print("★ 그중 **%d문항(챕터 %d개)은 「못 본 0」이다** — 말뭉치가 그 교재와 대조되지 않는다."
              % (unseen["prompts"], unseen["chapters"]))
        for ln in unseen["lines"]:
            print("   " + ln)
        print("   → 이 수를 «복제 없음» 으로 읽지 말 것. 판정선과 근거는"
              " `buildlib/checks_originality.MIN_WORDS_PER_MB` 가 정본이다.")
    elif not measured:
        # ★ **이 자리를 내 처방이 스스로 밟았다** (2026-08-26, 붙이자마자 잡았다).
        #   챕터가 0개인 갈래(공통 정본 `main`)에서 «전부 대조됐다» 를 찍었다 — 「잰 0」과
        #   「잴 것이 없는 0」을 또 같은 얼굴로 낸 것이다. 안심시키는 줄일수록 **무엇을 근거로
        #   안심하는지**를 함께 적어야 한다.
        print("[해당 없음] 잰 챕터가 0개다 — 위 0 은 «복제가 없다» 가 아니라 «잴 것이 없다» 다.")
    else:
        print("★ 챕터 %d개의 말뭉치가 모두 교재와 대조된다 — 위 0 은 **잰 0** 이다." % measured)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
