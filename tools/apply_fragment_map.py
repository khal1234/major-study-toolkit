# -*- coding: utf-8 -*-
"""**장 JSON 에 「옛 조각 → 새 조각」 목록을 문자열 치환으로 한꺼번에 넣는다** (열린 날 2026-09-18).

    python tools/apply_fragment_map.py "data/<과목>/chNN.json" --from <조각목록.json>          # 미리보기
    python tools/apply_fragment_map.py "data/<과목>/chNN.json" --from <조각목록.json> --apply

`조각목록.json` = `[["<옛 조각>", "<새 조각>"], …]`. 삽화 SVG 여러 장을 손보는 배치용이다 —
`Edit` 를 조각마다 부르면 왕복이 그만큼이고, 스크래치패드 스크립트는 가드가 막는다.

재는 것: 옛 조각이 파일에 **정확히 한 번** 있는가(0번·2번 이상이면 아무것도 안 쓰고 1) · 바꾼 뒤 JSON 이 파싱되는가.
못 보는 것: 새 조각이 그림으로 맞는지 — 렌더(`render_figure_review.py`)와 빌드가 본다. 정규식은 안 쓴다(데이터 함정).
"""
import argparse
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def apply_pairs(text, pairs):
    """[(옛, 새)] 를 차례로 치환. 옛 조각이 한 번이 아니면 ValueError — 순수 함수."""
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            raise ValueError("옛 조각이 %d번 있다: %s" % (n, old[:80]))
        text = text.replace(old, new)
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description="장 JSON 에 조각 치환 목록을 넣는다")
    ap.add_argument("chapter")
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", help="제자리 대신 이 경로에 쓴다(시험본 — 감사를 먼저 돌려 볼 때)")
    args = ap.parse_args(argv)
    with open(args.src, encoding="utf-8") as fh:
        pairs = json.load(fh)
    with open(args.chapter, encoding="utf-8") as fh:
        text = fh.read()
    try:
        out = apply_pairs(text, pairs)
        json.loads(out)
    except ValueError as exc:
        print("[실패] 아무것도 안 썼다 — " + str(exc)[:200], file=sys.stderr)
        return 1
    target = args.out or args.chapter
    print(("반영" if args.apply else "미리보기") + " — %s 조각 %d개" % (target, len(pairs)))
    if args.apply:
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
