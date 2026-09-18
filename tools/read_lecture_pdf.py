# -*- coding: utf-8 -*-
"""**강의 슬라이드 PDF 를 읽는다** — 교재 폴더 밖(스크래치패드)에 받은 것 전용 (열린 날 2026-09-10).

    python tools/read_lecture_pdf.py <pdf경로> --text --pages 1-20
    python tools/read_lecture_pdf.py <pdf경로> --render --pages 1-6

★ **왜 열렸나** — 전기전자공학기초 및 실험의 강의자료는 교재가 아니라 **노션에 붙은 주차별
  PDF** 다(2026-09-10 사용자 허락으로 내려받았다). `extract_textbook.py` 는 **교재 폴더**를
  훑도록 만들어져 그 파일을 못 본다. 슬라이드는 2단 조판도 아니라 그 자의 열 분리도 안 맞는다.

## 무엇을 하나

- `--text` — 쪽마다 글자를 뽑는다. 슬라이드라 쪽당 글자가 적어 한 번에 여러 쪽을 본다.
- `--render` — `review-artifacts/lecture-pdf/<이름>-pNNN.png` 로 찍는다. **그림이 본체인
  쪽**(회로도·파형)은 글자만 뽑으면 통째로 사라지므로 이쪽을 쓴다.

## ☐ 이 자가 못 보는 것 (규칙 21)

- **저작권 판정을 안 한다.** 뽑은 글을 데이터에 그대로 옮기면 절대 규칙 3 위반이다 —
  이 자는 읽기용이고, 콘텐츠는 **자작 요약·변형**으로 다시 쓴다.
- **스캔 PDF 의 글자를 못 뽑는다**(OCR 이 없다). 글이 비면 `--render` 로 눈으로 본다.
- **어디에 두어야 하나를 안 본다.** 받은 PDF 는 리포에 커밋하지 않는다(스크래치패드에 둔다).
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "review-artifacts", "lecture-pdf")
RENDER_ZOOM = 1.6           # 슬라이드 글자가 읽히는 최소 배율 — 1.0 은 잔글씨가 뭉갠다


def parse_pages(text, total):
    """`3` · `1-20` 을 0-기반 쪽 목록으로. 순수 함수."""
    if not text:
        return list(range(total))
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", text.strip())
    if not m:
        raise ValueError("쪽 범위는 `3` 이나 `1-20` 꼴이어야 한다")
    lo = int(m.group(1))
    hi = int(m.group(2) or m.group(1))
    return [p - 1 for p in range(lo, hi + 1) if 1 <= p <= total]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--pages")
    ap.add_argument("--text", action="store_true")
    ap.add_argument("--render", action="store_true")
    args = ap.parse_args(argv)

    try:
        import fitz                                             # PyMuPDF
    except ImportError:
        sys.exit("거부 — PyMuPDF 가 없다. `render_figure_review.py` 와 같은 의존이다.")
    if not os.path.exists(args.pdf):
        sys.exit("거부 — 파일이 없다: %s" % args.pdf)

    doc = fitz.open(args.pdf)
    pages = parse_pages(args.pages, doc.page_count)
    print("[%s] 전체 %d쪽 · 이번에 보는 것 %d쪽"
          % (os.path.basename(args.pdf), doc.page_count, len(pages)))

    if args.render:
        os.makedirs(OUT, exist_ok=True)
        stem = re.sub(r"[^\w.-]", "_", os.path.splitext(os.path.basename(args.pdf))[0])
        for p in pages:
            pix = doc[p].get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM))
            path = os.path.join(OUT, "%s-p%03d.png" % (stem, p + 1))
            pix.save(path)
            print("  %s" % os.path.relpath(path, ROOT))
        return 0

    for p in pages:
        text = (doc[p].get_text() or "").strip()
        print("\n--- p%d ---" % (p + 1))
        print(text if text else "(글자 없음 — 그림뿐인 쪽이다. `--render` 로 볼 것)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
