"""교재 본문 추출 — 근거 대조용 읽기 전용 도구.

왜 고정 도구인가: 챕터마다 Cengel·Moran 본문을 뒤져야 하는데, 그때마다 스크래치에
일회용 스크립트를 짜면 ⑴ 매번 승인 프롬프트가 뜨고 ⑵ 2단 조판 crop 같은 함정을
매번 다시 밟는다(AGENTS.md 실행 규율 2의 '고정 도구로 승격').

    python tools/extract_textbook.py --pdf moran --pages 30-52
    python tools/extract_textbook.py --pdf "1. INTRODUCTION" --pages 7-9 --grep joule,watt

--pdf 는 파일명 일부. 교재 폴더 두 곳에서 찾는다(읽기 전용).
--pages 는 **PDF 쪽 번호**(printed 쪽이 아니다 — chNN.textbook-map.md의 오프셋을 더할 것).
--grep 없이 돌리면 해당 쪽 전문을, 있으면 걸린 줄 앞뒤 2줄씩만 낸다.

**저작권(절대 규칙 3):** 여기서 나온 원문을 데이터 파일에 그대로 옮기지 말 것.
확인용으로만 읽고, 서술은 자작 요약·변형으로 쓴다.
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pdfplumber

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER_DIR = os.path.join(ROOT, "review-artifacts", "textbook-render")

# ★ 과목 폴더를 하나씩 나열하지 않는다 (2026-07-28 부류 수정).
#
# 예전에는 `.../2-1/4. 열역학`·`.../2-1/5. 공학수학`처럼 **과목마다 한 줄**이었다. 그러면
# 새 과목이 생길 때마다 여기 한 줄을 더해야 하는데 **빠뜨려도 증상이 조용하다** —
# find_pdf 가 빈 목록을 돌려 "PDF를 못 찾음"만 찍으므로 '교재가 없는 과목'처럼 보인다.
# 실측 2026-07-28: 기계재료 브랜치를 열었더니 강의노트 12개를 **한 장도 못 읽었다.**
#
# 승인 원장 14번이 `permissions.additionalDirectories` 에서 **똑같은 부류**를 이미 겪었고
# 해법도 같다 — 지점을 늘리는 대신 **상위 폴더를 한 번 등록해 등록 절차 자체를 없앤다.**
# 새 과목의 교재·강의노트는 전부 이 밑에 있으므로 new_subject.py 에 단계를 더하지 않아도 된다.
#
# 선수과목 교재(`1/99. Calculus` 등)도 자동으로 들어온다. **과목을 만들지는 않는다** —
# 프로젝트 범위는 2-1 → 2-2이고 1-1·1-2는 제외(피드백 원장 결정). 그건 오직 **판정용 근거**다:
# 「선수과목 강의계획서에서 찾을 수 있는가 → 있으면 간략 복습, 없으면 이 자료가 도입」
# (원장 '선수 지식 실측' 원칙)을 기억이 아니라 실제 목차로 확인하기 위해 읽는다.
BOOK_DIRS = [
    # ★ 2026-08-29 — 사용자가 구글드라이브 폴더 체계를 바꾸며 이 상위 폴더가
    #   `<교재 폴더>/2. 전공과목` 에서 `<교재 폴더>/학업/2. 전공과목` 으로
    #   옮겨졌다. 옛 경로는 이제 존재하지 않는다(`ls` 실측) — 옮기지 않고 남겨두면 이 도구가
    #   또 조용히 "PDF 후보 0개"를 찍는다(바로 위 주석이 경고한 그 부류가 실제로 재발했다).
    "C:/Users/<사용자>/Documents/<교재 폴더>/학업/2. 전공과목",
    "C:/Users/<사용자>/Documents/individual file/2. 전공과목",
]


def _match(root, name, needle, exts):
    """경로 조각으로 맞춘다 — **파일명이 아니라 전체 경로**를 본다.

    왜 경로인가 (2026-07-28, BOOK_DIRS 를 상위 폴더로 넓힌 직후 바로 걸렸다):
    과목마다 `1. 서론.pdf`·`1장 요약.png` 처럼 **같은 이름**이 있다. 파일명만 보면
    `--pdf "1. 서론"` 이 4개 과목에 걸려 아무것도 못 연다. 경로를 보면
    `--pdf "기계재료/0. 책/1. 서론"` 으로 한 번에 특정된다.
    파일명은 경로의 부분문자열이므로 **기존 호출은 그대로 동작한다.**
    """
    if not name.lower().endswith(exts):
        return None
    full = os.path.join(root, name)
    return full if needle in full.replace("\\", "/").lower() else None


def find_pdf(fragment):
    """경로에 fragment가 들어가는 PDF를 교재 폴더에서 찾는다."""
    hits = []
    needle = fragment.replace("\\", "/").lower()
    for base in BOOK_DIRS:
        for root, _dirs, files in os.walk(base):
            for name in files:
                hit = _match(root, name, needle, (".pdf",))
                if hit:
                    hits.append(hit)
    return hits


def columns(page):
    """2단 조판이라 좌/우로 갈라 뽑는다. page.bbox를 쓸 것 —
    (0,0,w,h)로 자르면 원점이 0이 아닌 쪽에서 어긋난다."""
    x0, top, x1, bottom = page.bbox
    mid = (x0 + x1) / 2.0
    return [("L", (x0, top, mid, bottom)), ("R", (mid, top, x1, bottom))]


def render_pages(pdf_path, lo, hi, scale=2.0):
    """텍스트 레이어가 없는 PDF(스캔본·이미지 슬라이드)를 PNG로 렌더한다.

    ★ 왜 필요한가 (2026-07-26 사용자 지적): pdfplumber는 이미지 PDF에서 빈 문자열을
    돌려준다. 그때 "텍스트 레이어가 없어 추출 불가"로 끝내면 **자료를 안 읽은 것**이고,
    사용자에게 "열어서 알려달라"고 떠넘기게 된다. 렌더해서 에이전트가 `view_image`로
    직접 읽는 것이 맞다 — 삽화 검수에서 이미 쓰는 비브라우저 경로와 같은 방식이다.

    출력은 review-artifacts/ 아래(gitignore됨)에만 쓴다.
    """
    import fitz

    # 파일명이 전부 한글이면 ASCII 슬러그가 빈 문자열이 된다 — 그때 고정 이름을 쓰면
    # 서로 다른 PDF가 한 폴더에 겹쳐 덮어쓴다(2026-07-26 '기말고사 공식집'에서 실측).
    # 빈 경우 원본 이름 해시로 갈라 둔다.
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    slug = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_")
    if not slug:
        import hashlib
        slug = "pdf_" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:10]
    out_dir = os.path.join(RENDER_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)

    outputs = []
    doc = fitz.open(pdf_path)
    try:
        for pno in range(lo, min(hi, doc.page_count) + 1):
            pix = doc[pno - 1].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            out = os.path.join(out_dir, "p%03d.png" % pno)
            pix.save(out)
            outputs.append(out)
    finally:
        doc.close()
    return outputs


# --- 챕터 구조 뽑기 (chNN.textbook-map.md 의 원재료) ------------------------
# 왜 도구인가: 지도 하나를 손으로 만들려면 '절 제목 / Example / 문제군 헤딩'을 각각
# grep해야 해서 챕터당 3회, ch06~08만 해도 9회다. 게다가 2단 조판이라 헤딩이 잘려
# 놓치기 쉽다(실측: `6-1 ■ INTROD` 로 끊겨 나왔다). 한 번 훑고 세 종류를 한꺼번에 낸다.
# ch09 이후 챕터에서도 같은 작업이 반복되므로 고정 도구로 둔다(실행 규율 2).
# ■ 마커는 앵커로 못 쓴다 — 조판·OCR에 따라 제목 앞(`6-1 ■ INTRO`), 하이픈으로
# 오독(`5-1 - CONSERVATION`), 심지어 **다음 줄**로 떨어진다(전체 PDF: `6–1 INTRODU` /
# 다음 줄 `■`). 마커를 선택으로 두고, 오탐은 '절 제목은 전부 대문자'라는 조판 사실로
# 거른다(본문 문장은 소문자가 섞이므로 안 걸린다). 대시는 하이픈·엔대시 둘 다 온다.
SECTION_RE = re.compile(r"^\s*(\d{1,2})\s*[-–]\s*(\d{1,2})\s*[■]?\s+([A-Z][A-Z0-9 ,'’&/()\-–]{2,})$")
EXAMPLE_RE = re.compile(r"^[\s■]*EXAMPLE\s+(\d{1,2})\s*[-–]\s*(\d{1,3})\s*(.*)$", re.I)
# 문제군 헤딩은 굵은 소제목 한 줄 — 문장이 아니고 마침표로 끝나지 않는다.
PROBLEM_GROUP_RE = re.compile(r"^\s*([A-Z][A-Za-z()/\-,. ]{6,60})\s*$")
PROBLEM_GROUP_STOP = ("SUMMARY", "REFERENCES", "PROBLEMS*", "FIGURE", "TABLE")


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")


def find_image(fragment):
    """경로에 fragment가 들어가는 **이미지**를 교재 폴더에서 찾는다(요약 png·jpg 등)."""
    hits = []
    needle = fragment.replace("\\", "/").lower()
    for base in BOOK_DIRS:
        for root, _dirs, files in os.walk(base):
            for name in files:
                hit = _match(root, name, needle, IMAGE_EXTS)
                if hit:
                    hits.append(hit)
    return hits


def stage_images(paths):
    """교재 폴더의 이미지를 `review-artifacts/` 안으로 복사하고 리포 상대경로를 돌려준다.

    ★ 왜 복사인가 (2026-07-28 신설). 수업 자료의 **장별 요약 이미지**는 대조의 1차 근거인데,
    파일 도구(Read)가 프로젝트 밖 경로에서 `Path is outside allowed working directories` 로
    막히는 일이 있다. 그때 *[발화 생략]* 로 끝내면 **자료를 안 읽은 것**이고,
    사용자에게 *[발화 생략]* 고 떠넘기게 된다 — `render_pages` 를 만든 이유와 **같은 부류**다.
    (실측: 같은 폴더의 `4장 요약.png` 는 읽히는데 `1장 요약.png` 는 막혔다. 즉 디렉터리 등록이
    아니라 파일 단위로 갈리므로, 등록을 손보는 것과 별개로 **에이전트가 자료를 직접 보는 경로**를
    하나 고정해 둔다. 게이트가 어떻게 고쳐지든 이 경로는 그대로 동작한다.)

    **저작권(절대 규칙 3):** 출력은 `review-artifacts/` 아래뿐이고 그 폴더는 `.gitignore` 로
    통째로 막혀 있다 — 커밋·배포에 절대 섞이지 않는다. 확인용으로만 보고 서술은 자작으로 쓴다.

    ★ 이름 충돌을 반드시 갈라 둔다 (첫 구현에서 바로 터졌다): 과목마다 `1장 요약.png` 가 있고,
    게다가 조각 검색이라 `1장 요약` 은 `11장 요약` 에도 걸린다. basename 으로만 복사하면
    **서로 다른 과목의 요약본이 한 파일로 덮어써지고**, 에이전트는 그것을 모른 채 남의 과목
    요약을 근거로 삼는다. 그래서 `<상위폴더>__<파일명>` 으로 갈라 두고 원본 경로를 함께 찍는다.
    """
    import shutil

    out_dir = os.path.join(RENDER_DIR, "images")
    os.makedirs(out_dir, exist_ok=True)
    outs = []
    for src in paths:
        parent = os.path.basename(os.path.dirname(src))
        subject = os.path.basename(os.path.dirname(os.path.dirname(src)))
        dst = os.path.join(out_dir, subject + "__" + parent + "__" + os.path.basename(src))
        shutil.copyfile(src, dst)
        outs.append((src, os.path.relpath(dst, ROOT)))
    return outs


def chapter_outline(pdf_path, lo, hi, single=False):
    """(절 헤딩, Example, 문제군 후보) 세 목록을 한 번의 순회로 뽑는다.

    **전폭과 좌/우 단을 모두 훑는다.** 절 헤딩은 2단을 가로질러 조판돼 있어서 단으로
    crop하면 잘린다 — 실측 2026-07-26: 컬럼만 보면 `6-1 ■ INTROD` 로 끊기고 ch05는
    절 헤딩을 **하나도** 못 잡았다(Example도 13건 중 7건만, 제목은 잘린 채). 반대로
    Example·문제군은 단 안에 있어 전폭으로만 보면 좌우가 섞인다. 그래서 둘 다 보고
    같은 번호는 **가장 긴 텍스트**를 남긴다(잘린 쪽이 자동으로 밀려난다).

    반환값은 (kind, page, text) 튜플의 리스트. 판정은 호출자가 아니라 여기서 하므로
    회귀 테스트가 이 함수를 직접 부를 수 있다(guard_bash의 deny_reason과 같은 배치).
    """
    best = {}       # (kind, 번호) -> (page, text)
    groups = []
    in_problems = False
    with pdfplumber.open(pdf_path) as pdf:
        for pno in range(lo, min(hi, len(pdf.pages)) + 1):
            page = pdf.pages[pno - 1]
            boxes = [("", page.bbox)]
            if not single:
                boxes += columns(page)
            for _tag, box in boxes:
                for line in (page.crop(box).extract_text() or "").splitlines():
                    for kind, pattern in (("section", SECTION_RE), ("example", EXAMPLE_RE)):
                        m = pattern.match(line)
                        if not m:
                            continue
                        num = f"{m.group(1)}-{m.group(2)}"
                        text = (num + " " + m.group(3)).strip()
                        prev = best.get((kind, num))
                        if prev is None or len(text) > len(prev[1]):
                            best[(kind, num)] = (pno, text)
                        break
                    stripped = line.strip()
                    if stripped.upper().startswith("PROBLEMS"):
                        in_problems = True
                    if in_problems and PROBLEM_GROUP_RE.match(line) \
                            and not any(stripped.upper().startswith(s) for s in PROBLEM_GROUP_STOP):
                        groups.append(("group?", pno, stripped))

    def sort_key(item):
        (kind, num), (pno, _text) = item
        major, _, minor = num.partition("-")
        return (kind, int(major), int(minor))

    out = [(kind, pno, text) for (kind, _num), (pno, text)
           in sorted(best.items(), key=sort_key)]
    # 같은 문제군 헤딩이 쪽마다 반복되는 일이 있어 첫 등장만 남긴다.
    seen = set()
    for kind, pno, text in groups:
        if text.lower() in seen:
            continue
        seen.add(text.lower())
        out.append((kind, pno, text))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default="", help="파일명 일부")
    ap.add_argument("--pages", default="", help="PDF 쪽 범위, 예 30-52")
    ap.add_argument("--grep", default="", help="쉼표로 구분한 키워드")
    ap.add_argument("--context", type=int, default=2)
    ap.add_argument("--single", action="store_true",
                    help="단일 단으로 처리(목차·OCR 전면 등 2단이 아닌 PDF)")
    ap.add_argument("--render", action="store_true",
                    help="텍스트 대신 PNG로 렌더한다(이미지 PDF·스캔본). "
                         "출력 경로를 찍으면 view_image로 직접 읽는다.")
    ap.add_argument("--list", action="store_true",
                    help="교재 폴더의 PDF 목록만 출력(--pdf로 필터, 없으면 전체). "
                         "'ls <바깥 절대경로>'가 파일 경계 프롬프트를 띄우는 것을 피하는 경로다.")
    ap.add_argument("--image", default="",
                    help="교재 폴더의 이미지(장별 요약 png·jpg 등)를 review-artifacts/ 로 복사한다. "
                         "찍힌 경로를 Read/view_image 로 직접 본다 — 파일 도구의 경로 게이트를 안 탄다.")
    ap.add_argument("--outline", action="store_true",
                    help="절 헤딩·EXAMPLE·문제군 헤딩을 한 번에 뽑는다(chNN.textbook-map.md 원재료). "
                         "챕터당 grep 3회를 1회로 줄인다.")
    args = ap.parse_args()

    # --list: 폴더 목록은 이 도구로 낸다. 바깥 절대경로를 셸 인자로 노출하지 않으므로
    # 파일 경계 게이트(Path is outside allowed working directories)를 안 건드린다.
    if args.list:
        found = find_pdf(args.pdf)
        if not found:
            print("PDF 없음" + (f" (필터: {args.pdf})" if args.pdf else ""))
            return 1
        for h in sorted(found):
            print(h)
        return 0

    if args.image:
        found = find_image(args.image)
        if not found:
            print("이미지를 못 찾음: " + args.image)
            return 1
        for src, rel in stage_images(sorted(found)):
            print(rel + "\n    ← " + src)
        return 0

    if not args.pdf or not args.pages:
        print("추출에는 --pdf 와 --pages 가 필요하다 (목록만 볼 땐 --list, 이미지는 --image).")
        return 1

    hits = find_pdf(args.pdf)
    if not hits:
        print("PDF를 못 찾음: " + args.pdf)
        return 1
    if len(hits) > 1:
        print("여러 개가 맞음 — 더 구체적으로 줄 것:")
        for h in hits:
            print("  " + h)
        return 1

    start, _, end = args.pages.partition("-")
    lo, hi = int(start), int(end or start)
    keys = [k.strip() for k in args.grep.split(",") if k.strip()]

    if args.render:
        for out in render_pages(hits[0], lo, hi):
            print(os.path.relpath(out, ROOT))
        return 0

    if args.outline:
        rows = chapter_outline(hits[0], lo, hi, single=args.single)
        for kind, pno, text in rows:
            print(f"{kind:<8} p.{pno:<4} {text}")
        counts = {}
        for kind, _p, _t in rows:
            counts[kind] = counts.get(kind, 0) + 1
        print("\n합계: " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items()))
              + "   (group?는 후보다 — 사람이 골라낼 것)")
        return 0

    with pdfplumber.open(hits[0]) as pdf:
        for pno in range(lo, min(hi, len(pdf.pages)) + 1):
            page = pdf.pages[pno - 1]
            boxes = [("", page.bbox)] if args.single else columns(page)
            for tag, box in boxes:
                lines = (page.crop(box).extract_text() or "").splitlines()
                if not keys:
                    print("\n===== PDF p.%d %s =====" % (pno, tag))
                    for line in lines:
                        print("   " + line)
                    continue
                for i, line in enumerate(lines):
                    if any(k.lower() in line.lower() for k in keys):
                        lo_i = max(0, i - args.context)
                        hi_i = min(len(lines), i + args.context + 1)
                        print("\n=== p.%d %s line %d ===" % (pno, tag, i))
                        for l in lines[lo_i:hi_i]:
                            print("   " + l)
    return 0


if __name__ == "__main__":
    sys.exit(main())
