r"""장 JSON 을 요약 쓰기용으로 짧게 편다 — 절 제목·첫 문장, 유도 카드의 짧은 칸, 함정.

    python tools/chapter_digest.py data/<과목>/chNN.json [...] [--chars=260]

재는 것: 없음(읽기 전용 발췌). 장 끝 요약(`chapterSummary`)을 쓸 때 장 JSON 을 통째로 읽지 않게 한다
(실행 규율 12 — 큰 출력은 뒤 왕복마다 다시 실린다).
못 보는 것: 문풀·연습문제·삽화 — 요약의 재료는 이론·유도·함정이다. 발췌는 판정이 아니다.
"""

import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SKIP_KEYS = ("changeNote", "sourceRef", "anchorText")


def digest(d, chars):
    """장 dict → 줄 목록. 순수 함수."""
    out = ["top keys: " + ", ".join(d.keys())]
    secs = (d.get("theory") or {}).get("sections") or []
    out.append("-- theory %d" % len(secs))
    for s in secs:
        body = re.sub(r"\s+", " ", s.get("content") or "")
        mark = " [요약]" if s.get("chapterSummary") else ""
        out.append("  · %s%s | %s | %s" % (s.get("id"), mark, s.get("heading"), body[:chars]))
    formulas = (d.get("derivation") or {}).get("formulas") or []
    out.append("-- derivation %d" % len(formulas))
    for f in formulas:
        short = {k: v for k, v in f.items()
                 if isinstance(v, str) and k not in SKIP_KEYS and len(v) <= chars}
        out.append("  · " + json.dumps(short, ensure_ascii=False))
    pits = d.get("pitfalls") or []
    out.append("-- pitfalls %d" % len(pits))
    for p in pits:
        short = {k: v for k, v in p.items()
                 if isinstance(v, str) and k not in SKIP_KEYS and k != "source" and len(v) <= chars}
        out.append("  · " + json.dumps(short, ensure_ascii=False))
    return out


def main():
    chars = 260
    paths = []
    for a in sys.argv[1:]:
        if a.startswith("--chars="):
            chars = int(a.split("=", 1)[1])
        else:
            paths.append(a)
    if not paths:
        sys.exit("장 경로를 하나 이상 줄 것 — data/<과목>/chNN.json")
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        print("=" * 12, p, "—", d.get("title") or d.get("chapterTitle") or "")
        print("\n".join(digest(d, chars)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
