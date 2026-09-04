# -*- coding: utf-8 -*-
"""삽화 육안 검증용 미리보기 — 고른 삽화만 담은 단독 HTML을 만든다.

왜 필요한가: AGENTS.md 삽화 표준은 **렌더된 그림을 실제로 볼 것**을 요구하는데,
챕터 산출물(site/열역학/chNN.html)은 통째로 열면 문맥 비용이 크다. 여기서는
요청한 삽화만 뽑아 가벼운 페이지로 만들어 브라우저로 확인한다.

    python tools/preview_figures.py ch02 fig-two-ledgers fig-heat-modes
    python tools/preview_figures.py ch02                 # 그 챕터 전체

출력: tools/scratch/figpreview.html (gitignore 대상). 데이터는 읽기만 한다.
"""
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 과목 폴더를 박지 않는다 — fix_figure_label_gap 의 같은 주석 참조(2026-07-30 재발).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_content  # noqa: E402
DATA = audit_content.DATA
OUT = os.path.join(ROOT, "tools", "scratch", "figpreview.html")


def iter_diagrams(data):
    """챕터 안의 모든 삽화를 (소유자 id, 삽화) 로 흘린다."""
    theory = (data.get("theory") or {}).get("sections") or []
    derivation = (data.get("derivation") or {}).get("formulas") or []
    for items in (theory, derivation, data.get("practice") or [], data.get("problems") or []):
        for item in items:
            for fig in item.get("diagrams") or []:
                yield item.get("id", "?"), fig


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    chapter = sys.argv[1]
    wanted = set(sys.argv[2:])

    path = os.path.join(DATA, chapter + ".json")
    if not os.path.isfile(path):
        print("없는 챕터:", path)
        return 2
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    cards = []
    for owner, fig in iter_diagrams(data):
        if wanted and fig.get("id") not in wanted:
            continue
        cards.append(
            "<figure><figcaption><b>" + str(fig.get("id")) + "</b> — "
            + str(fig.get("title", "")) + " <span class='owner'>@" + owner + "</span>"
            "</figcaption>" + fig.get("svg", "") + "</figure>")

    missing = wanted - {fig.get("id") for _, fig in iter_diagrams(data)}
    if missing:
        print("찾지 못한 삽화:", ", ".join(sorted(missing)))

    html = ("<!doctype html><meta charset='utf-8'><title>figure preview</title>"
            "<style>body{background:#efe9dc;font-family:system-ui,sans-serif;margin:24px;}"
            "figure{margin:0 0 28px;background:#fff;padding:12px;border-radius:10px;}"
            "figcaption{font-size:13px;margin-bottom:8px;color:#333;}"
            ".owner{color:#888;font-weight:400;}svg{max-width:100%;height:auto;}</style>"
            + "".join(cards))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("삽화 " + str(len(cards)) + "건 → " + OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
