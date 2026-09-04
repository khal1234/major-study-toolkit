"""교재 PDF를 장별로 쪼갠다 — 태블릿 필기 앱에서 통째 PDF가 버벅이는 문제 대응(2026-08-31).

    python tools/split_textbook_pdf.py outline <파일명 조각>
    python tools/split_textbook_pdf.py split <파일명 조각> --ranges "ch07=331-388,ch08=389-448" --out <하위폴더>
    python tools/split_textbook_pdf.py copyout <하위폴더> --to "<교재 폴더 안의 절대경로>"
    python tools/split_textbook_pdf.py rename "<교재 폴더 안의 절대경로>" "<새 이름>"

`outline`은 PDF에 박힌 책갈피(목차)를 쪽 번호와 함께 낸다 — 장이 시작하는 실제 쪽을 찾는 데 쓴다.
책갈피가 없으면 「없음」을 찍는다(그때는 `extract_textbook.py --pages a-b`로 목차 쪽을 직접 봐야 한다).

`split`은 `--ranges`에 적은 **PDF 쪽 번호**(표지가 1쪽) 구간대로 새 PDF 파일을 만든다.
산출물은 `review-artifacts/textbook-split/<--out>/`에 쓴다 — `.gitignore` 대상이라 커밋되지 않는다
(절대 규칙 3: 교재 원문을 리포에 저장하지 않는다 — 장 단위 PDF는 원문 그 자체라 여기 안 둔다).

`copyout`은 이미 쪼갠 산출물을 **사용자가 지정한 리포 밖 경로**(태블릿과 동기화되는 교재 폴더 등)로
복사한다. AGENTS 규칙 9(쓰기는 리포·스크래치패드뿐)의 예외 — **사용자가 그 자리에서 직접 지시했을
때만** 쓴다(공용 규칙 「나루에서만 다른 것」과 같은 예외 형태). `--to`는 존재해야 하고, 없는 폴더를
새로 만들지 않는다(엉뚱한 경로에 새 폴더가 조용히 생기는 것을 막는다 — 상위까지는 사용자가 이미
갖고 있는 교재 폴더여야 한다는 뜻).

`--pdf` 조각 검색은 `extract_textbook.find_pdf`를 그대로 쓴다 — 교재 폴더 탐색 로직을 두 벌로 안 둔다.

`rename`은 교재 폴더 안의 폴더 이름을 바꾼다(예: 과목 앞 번호를 통일할 때). `copyout`과 같은
안전판 — **마지막 한 칸만** 바꾸고, 목적지 이름이 이미 있으면 거부한다(덮어쓰기 금지). 이것도
AGENTS 규칙 9의 예외이며 사용자가 그 자리에서 직접 지시했을 때만 쓴다.
"""
import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_textbook import find_pdf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(ROOT, "review-artifacts", "textbook-split")


def resolve_one(fragment):
    hits = find_pdf(fragment)
    if not hits:
        sys.exit("PDF를 못 찾음: " + fragment)
    if len(hits) > 1:
        sys.exit("후보가 %d개 — 조각을 더 좁힐 것:\n  %s" % (len(hits), "\n  ".join(hits)))
    return hits[0]


def cmd_outline(args):
    from pypdf import PdfReader

    path = resolve_one(args.pdf)
    reader = PdfReader(path)
    print("파일: " + path)
    print("총 쪽수: " + str(len(reader.pages)))
    outline = reader.outline
    if not outline:
        print("책갈피 없음 — extract_textbook.py --pages a-b 로 목차 쪽을 직접 볼 것")
        return
    _walk(outline, reader)


def _walk(items, reader, depth=0):
    for it in items:
        if isinstance(it, list):
            _walk(it, reader, depth + 1)
            continue
        if depth > args_depth[0]:
            continue
        try:
            page_num = reader.get_destination_page_number(it) + 1
        except Exception:
            page_num = "?"
        print("%s%s\t%s" % ("  " * depth, page_num, it.title))


args_depth = [1]  # _walk가 참조하는 깊이 상한 — cmd_outline에서 argparse 값으로 덮어쓴다


def parse_ranges(text):
    """`"name=start-end,name2=start2-end2"` → `[(name, start, end)]`. 순수 함수."""
    out = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, _, span = chunk.partition("=")
        lo, _, hi = span.partition("-")
        out.append((name.strip(), int(lo), int(hi)))
    return out


def cmd_split(args):
    from pypdf import PdfReader, PdfWriter

    path = resolve_one(args.pdf)
    reader = PdfReader(path)
    total = len(reader.pages)
    ranges = parse_ranges(args.ranges)
    if not ranges:
        sys.exit("--ranges 가 비었다")
    bad = [(n, lo, hi) for n, lo, hi in ranges if lo < 1 or hi > total or lo > hi]
    if bad:
        sys.exit("범위가 총 쪽수(%d)를 벗어남: %s" % (total, bad))

    out_dir = os.path.join(OUT_ROOT, args.out)
    os.makedirs(out_dir, exist_ok=True)
    made = []
    for name, lo, hi in ranges:
        writer = PdfWriter()
        for i in range(lo - 1, hi):
            writer.add_page(reader.pages[i])
        dest = os.path.join(out_dir, name + ".pdf")
        with open(dest, "wb") as fh:
            writer.write(fh)
        made.append((dest, hi - lo + 1))

    print("원본: " + path + " (" + str(total) + "쪽)")
    for dest, n in made:
        print("  %-60s %d쪽" % (dest, n))
    print("→ " + out_dir)


def cmd_copyout(args):
    import shutil

    src = os.path.join(OUT_ROOT, args.folder)
    if not os.path.isdir(src):
        sys.exit("없음: " + src + " — 먼저 split 을 돌릴 것")
    # ★ 마지막 한 칸만 새로 만든다 — 부모까지는 사용자가 이미 갖고 있는 교재 폴더여야 한다.
    #   부모가 없으면 엉뚱한 경로에 폴더 트리를 통째로 새로 만들 위험이 있어 그건 거부한다.
    parent = os.path.dirname(os.path.normpath(args.to))
    if not os.path.isdir(args.to):
        if not os.path.isdir(parent):
            sys.exit("대상의 상위 폴더가 없다(새로 안 만든다): " + parent)
        os.makedirs(args.to)
    made = []
    for name in sorted(os.listdir(src)):
        # ★ .txt(목차)도 함께 나른다(2026-09-01) — 태블릿에서 장 번호만 보고는 무슨 장인지
        #   몰라 매번 강의계획서를 다시 열어야 했다. `split` 은 안 만든다 — 저자가
        #   `목차.txt` 를 이 폴더에 직접 두면 여기서 함께 실려 간다(선택적, 없어도 통과).
        if not (name.lower().endswith(".pdf") or name == "목차.txt"):
            continue
        dest = os.path.join(args.to, name)
        shutil.copyfile(os.path.join(src, name), dest)
        made.append(dest)
    if not made:
        sys.exit("복사할 PDF가 없다: " + src)
    print("원본: " + src)
    for dest in made:
        print("  " + dest)
    print("→ " + str(len(made)) + "개 복사됨")


def cmd_rename(args):
    # ★ 리포 밖 이름 바꾸기(2026-09-01) — copyout 과 같은 안전판이다: **마지막 한 칸만** 바꾼다.
    #   대상의 부모 폴더가 실재해야 하고(엉뚱한 트리를 새로 만들지 않는다), 목적지 이름이
    #   이미 있으면 거부한다(덮어쓰기로 남의 폴더를 삼키지 않는다). 사용자가 그 자리에서
    #   직접 지시했을 때만 쓰는 규칙 9 예외 — copyout 과 같은 근거다.
    src = args.path
    if not os.path.isdir(src):
        sys.exit("폴더가 아니거나 없음: " + src)
    parent = os.path.dirname(os.path.normpath(src))
    dest = os.path.join(parent, args.to)
    if os.path.exists(dest):
        sys.exit("이미 있음(안 덮어씀): " + dest)
    os.rename(src, dest)
    print(src + "\n→ " + dest)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_outline = sub.add_parser("outline")
    p_outline.add_argument("pdf")
    p_outline.add_argument("--depth", type=int, default=1)

    p_split = sub.add_parser("split")
    p_split.add_argument("pdf")
    p_split.add_argument("--ranges", required=True)
    p_split.add_argument("--out", required=True)

    p_copyout = sub.add_parser("copyout")
    p_copyout.add_argument("folder")
    p_copyout.add_argument("--to", required=True)

    p_rename = sub.add_parser("rename")
    p_rename.add_argument("path")
    p_rename.add_argument("to")

    args = ap.parse_args()
    if args.cmd == "outline":
        args_depth[0] = args.depth
        cmd_outline(args)
    elif args.cmd == "split":
        cmd_split(args)
    elif args.cmd == "copyout":
        cmd_copyout(args)
    else:
        cmd_rename(args)


if __name__ == "__main__":
    main()
