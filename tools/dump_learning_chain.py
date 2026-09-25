"""장 JSON 의 학습 사슬 재료(절 · 유도 카드 · 문풀 · 문제 · 교재 문제)를 한 화면에 찍는다 — 읽기 전용.

재는 것: 대표 문제 → 기술 → 최초 이론 → 기본 예제 → 연습 → 독립 문제를 기존 ID 로 잇기 위한
재료(`docs/배치-작업.md` 「교수·교재 문제에서 거꾸로 확인하는 학습 연결」). 연결 자체는 판정하지 않는다.
못 보는 것: 교재 원문 · 교수 과제 · 강의자료(사람이 연다) · 화면 렌더.

    python tools/dump_learning_chain.py data/<과목>/chNN.json [...]
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def short(s, n):
    if isinstance(s, list):
        s = " / ".join(x if isinstance(x, str) else x.get("text", "") for x in s)
    return re.sub(r"\s+", " ", s or "")[:n]


def dump(path):
    d = json.load(open(path, encoding="utf-8"))
    print(f"\n===== {path} =====")
    th = d.get("theory", {})
    secs = th.get("sections", []) if isinstance(th, dict) else (th or [])
    print("절:", " | ".join(f"{s.get('id')}:{short(s.get('title'), 28)}" for s in secs))
    der = d.get("derivation", {})
    forms = der.get("formulas", []) if isinstance(der, dict) else []
    print("유도:", " | ".join(f"{f.get('id')}:{short(f.get('title') or f.get('name'), 28)}" for f in forms))
    print("formulaLearningPath:", len(d.get("formulaLearningPath") or []))
    for p in d.get("practice", []):
        print(f"  문풀 {p.get('id')} 절={p.get('section')} ramp={p.get('ramp')} {p.get('difficulty')} "
              f"rf={p.get('relatedFormulas') or ''} :: {short(p.get('prompt'), 110)}")
    for q in d.get("problems", []):
        print(f"  문제 {q.get('id')} 절={q.get('section')} {q.get('difficulty')} "
              f"rf={q.get('relatedFormulas') or ''} :: {short(q.get('prompt'), 110)}")
    tb = d.get("textbookProblems") or {}
    if tb:
        print("  교재 출처:", short(tb.get("source"), 300))
        for it in tb.get("items", []):
            extra = {k: it[k] for k in ("number", "section", "practiceLink", "linksTo") if it.get(k)}
            print(f"  교재 {it.get('id')} {extra or ''} :: {short(it.get('title') or it.get('topic'), 50)} "
                  f"|| {short(it.get('outline'), 120)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("사용: python tools/dump_learning_chain.py data/<과목>/chNN.json [...]")
    for a in sys.argv[1:]:
        dump(a)
