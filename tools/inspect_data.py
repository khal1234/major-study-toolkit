#!/usr/bin/env python
"""챕터 데이터·증기표 조회 (읽기 전용).

**왜 고정 도구인가 (2026-07-26 신설, 사용자 지적 3회).**
에이전트가 "챕터 구조가 어떻게 생겼더라"를 확인할 때마다 `python -c "..."` 를 새로 짰다.
그 형태는 `guard_bash.py`가 막아야 하는데 정규식이 줄 단위라 여러 줄짜리는 통과했고,
대신 **매번 승인 프롬프트가 떴다.** 사용자가 세 세션에 걸쳐 같은 지적을 했다:
"명령 1개로 좀 통일할 수 없어? 매번 이거 일일이 누르는 게 합리적이지 않다."

그래서 ⑴ 훅의 구멍을 막고 ⑵ 그 자리를 대신할 조회 창구를 여기 하나로 모았다.
`tools/` 안이라 guard가 자동 허용한다 — **프롬프트가 0이다.**
조회가 필요하면 새 스니펫을 짜지 말고 여기에 서브커맨드를 추가할 것.

    python tools/inspect_data.py                       # 챕터 목록과 한 줄 요약
    python tools/inspect_data.py ch01                  # 절·학습목표·컬렉션 개수
    python tools/inspect_data.py ch01 --problems       # 연습문제 표(난이도·삽화·슬롯)
    python tools/inspect_data.py ch01 --practice       # 문풀 표
    python tools/inspect_data.py ch01 --keys           # 최상위 키와 컬렉션별 필드 이름
    python tools/inspect_data.py ch01 --item ch01-q09  # 그 항목의 JSON 전체
    python tools/inspect_data.py ch01 --figures        # 삽화 id·제목·SVG 길이
    python tools/inspect_data.py ch01 --derivations    # 유도 카드의 단계 스키마와 본문
    python tools/inspect_data.py --steam satT 120      # 포화표(온도)
    python tools/inspect_data.py --steam satP 400      # 포화표(압력)
    python tools/inspect_data.py --steam sh 400 150    # 과열표 (P kPa, T °C)

**파일을 쓰지 않는다.** 인자로 받은 경로도 열지 않는다(대상은 이 워크트리로 고정).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 오류는 stderr 로 나간다 — 그쪽도 UTF-8 로 돌려놓지 않으면 **한글 오류만 깨진다**
# (2026-08-12, 동역학 세션 보고. 잠금 `test_checks.py::test_tool_errors_are_utf8`).
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from audit_content import CHAPTERS, DATA, load                          # noqa: E402

COLLECTIONS = ("theory", "derivation", "practice", "problems")


def _steam():
    path = os.path.join(DATA, "tables", "steam.json")
    if not os.path.isfile(path):
        sys.exit("이 워크트리에는 증기표가 없다: " + path)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _index_status():
    path = os.path.join(DATA, "index.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        idx = json.load(fh)
    return {e.get("file"): e.get("status") for e in idx.get("chapters") or []}


def _short(text, width=58):
    one = re.sub(r"\s+", " ", str(text or "")).strip()
    return one if len(one) <= width else one[:width - 1] + "…"


def overview():
    status = _index_status()
    print(f"데이터 폴더: {DATA}")
    print(f"{'챕터':<7}{'status':<8}{'제목':<34}이론/유도/문풀/문제")
    for ch in CHAPTERS:
        d = load(ch)
        counts = "/".join(str(len(_collection(d, c))) for c in COLLECTIONS)
        print(f"  {ch:<5}{status.get(ch + '.json', '?'):<8}"
              f"{_short(d.get('chapterTitle'), 32):<34}{counts}")


def _collection(d, name):
    if name == "theory":
        return d.get("theory", {}).get("sections") or []
    if name == "derivation":
        return d.get("derivation", {}).get("formulas") or []
    return d.get(name) or []


def summary(ch):
    d = load(ch)
    print(f"== {ch} · {d.get('chapterTitle')} (chapterNumber {d.get('chapterNumber')})")
    intro = d.get("chapterIntro")
    print("  도입부:", "있음" if intro else "없음",
          ("(" + ", ".join(k for k in ("summary", "question", "prerequisite", "nextLink")
                           if intro.get(k)) + ")") if intro else "")
    print("  절:")
    for s in _collection(d, "theory"):
        print(f"    {s.get('id'):<26}{_short(s.get('heading'), 46)}")
    print("  학습목표:")
    for lo in d.get("learningObjectives") or []:
        print(f"    {lo.get('id'):<6}{_short(lo.get('statement'), 84)}")
    for name in ("derivation", "practice", "problems"):
        print(f"  {name}: {len(_collection(d, name))}건")


def keys(ch):
    d = load(ch)
    print(f"== {ch} 최상위 키")
    for k in d:
        print("   ", k)
    for name in COLLECTIONS:
        items = _collection(d, name)
        if not items:
            continue
        fields = sorted({f for it in items if isinstance(it, dict) for f in it})
        print(f"  {name}[] 필드: {', '.join(fields)}")


def problems(ch):
    d = load(ch)
    print(f"== {ch} 연습문제 {len(_collection(d, 'problems'))}건")
    print(f"  {'id':<12}{'난이도':<14}{'삽화':<6}{'mode':<8}{'슬롯':<6}프롬프트")
    for q in _collection(d, "problems"):
        print(f"  {q.get('id', '?'):<12}{str(q.get('difficulty')):<14}"
              f"{len(q.get('diagrams') or []):<6}{str(q.get('figureMode') or '-'):<8}"
              f"{len(q.get('figureSlots') or []):<6}{_short(q.get('prompt'), 52)}")


def practice(ch):
    d = load(ch)
    print(f"== {ch} 문풀 {len(_collection(d, 'practice'))}건")
    print(f"  {'id':<14}{'stage':<15}{'난이도':<14}{'빈칸':<6}프롬프트")
    for p in _collection(d, "practice"):
        print(f"  {p.get('id', '?'):<14}{str(p.get('stage')):<15}"
              f"{str(p.get('difficulty')):<14}{len(p.get('blanks') or []):<6}"
              f"{_short(p.get('prompt'), 46)}")


def figures(ch):
    d = load(ch)
    print(f"== {ch} 삽화")
    print(f"  {'소유자':<14}{'삽화 id':<32}{'SVG자':<8}제목")
    for name in COLLECTIONS:
        for it in _collection(d, name):
            if not isinstance(it, dict):
                continue
            for dg in it.get("diagrams") or []:
                print(f"  {str(it.get('id')):<14}{str(dg.get('id')):<32}"
                      f"{len(dg.get('svg') or ''):<8}{_short(dg.get('title'), 44)}")


def derivations(ch):
    d = load(ch)
    formulas = _collection(d, "derivation")
    print(f"== {ch} 유도 카드 {len(formulas)}건")
    for f in formulas:
        print(f"\n[{f.get('id')}] {f.get('name') or f.get('title') or ''}")
        for i, step in enumerate(f.get("derivationSteps") or [], 1):
            if isinstance(step, dict):
                print(f"  {i}. [객체] {_short(step.get('text'), 100)}")
                for eq in step.get("equations") or []:
                    print("       = " + _short(eq, 100))
            else:
                print(f"  {i}. [문자열] {_short(step, 120)}")


def item(ch, wanted):
    d = load(ch)
    for name in COLLECTIONS:
        for it in _collection(d, name):
            if isinstance(it, dict) and it.get("id") == wanted:
                print(f"== {ch} / {name} / {wanted}")
                print(json.dumps(it, ensure_ascii=False, indent=2))
                return
    sys.exit(f"{ch}에 id가 {wanted!r}인 항목이 없다 (theory/derivation/practice/problems 순회)")


def steam(args):
    data = _steam()
    print(data.get("description", ""))
    if not args:
        sys.exit("사용: --steam satT <T°C> | satP <P kPa> | sh <P kPa> <T°C>")
    kind = args[0]
    if kind in ("satT", "satP"):
        table = data["saturation_T" if kind == "satT" else "saturation_P"]
        cols = table["columns"]
        target = float(args[1])
        for row in table["rows"]:
            if abs(row[0] - target) < 1e-9:
                for c, v in zip(cols, row):
                    print(f"   {c:<8}{v}")
                return
        sys.exit(f"{kind} 표에 {target} 행이 없다 — 보간이 필요한 값은 문제로 쓰지 않는다")
    if kind == "sh":
        p, t = float(args[1]), float(args[2])
        cols = data["superheated"]["columns"]
        for b in data["superheated"]["blocks"]:
            if abs(b["P"] - p) < 1e-9:
                for row in b["rows"]:
                    if abs(row[0] - t) < 1e-9:
                        for c, v in zip(cols, row):
                            print(f"   {c:<8}{v}")
                        return
                sys.exit(f"P = {p} kPa 블록에 T = {t}°C 행이 없다")
        sys.exit(f"과열표에 P = {p} kPa 블록이 없다")
    sys.exit(f"모르는 증기표 조회: {kind!r}")


# --- 유니코드 첨자 조사 (2026-07-26, math의 첨자 규칙 merge 사전 조사) -------------
# math가 올릴 예정인 검사: 수식 자리(\(…\)·latex 필드·derivationSteps equations)는
# 유니코드 첨자 전면 금지(숫자 포함), 산문 자리는 **문자 첨자만** 금지(m³·m/s² 허용).
# merge 전에 위반량을 세는 read-only 조사다 — 지도(migration) 규모 판단용.
LETTER_SCRIPTS = set("ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ")
ALL_SCRIPTS = LETTER_SCRIPTS | set("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
MATH_FIELD_KEYS = {"latex"}          # 값 전체가 LaTeX인 필드
MATH_SPAN = re.compile(r"\\\((.+?)\\\)", re.S)


def _iter_strings(node, trail="root", key=None):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "svg":                     # SVG는 검사 대상이 아니다
                continue
            yield from _iter_strings(v, trail + "/" + str(k), k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _iter_strings(v, trail + "[" + str(i) + "]", key)
    elif isinstance(node, str):
        yield trail, key, node


def scripts_report():
    print("유니코드 첨자 조사 — math 첨자 규칙 merge 사전 조사 (read-only)")
    total_a = total_b = 0
    for ch in CHAPTERS:
        d = load(ch)
        hits_a, hits_b = [], []
        for trail, key, s in _iter_strings(d):
            letters = [c for c in s if c in LETTER_SCRIPTS]
            if letters:
                hits_a.append((trail, "".join(letters), s))
            if key in MATH_FIELD_KEYS:
                bad = [c for c in s if c in ALL_SCRIPTS]
                if bad:
                    hits_b.append((trail, "".join(bad), s))
            else:
                for m in MATH_SPAN.finditer(s):
                    bad = [c for c in m.group(1) if c in ALL_SCRIPTS]
                    if bad:
                        hits_b.append((trail, "".join(bad), m.group(0)))
        print(f"\n== {ch}: (a) 문자 첨자 {sum(len(h[1]) for h in hits_a)}자/{len(hits_a)}곳"
              f" · (b) 수식 자리 첨자 {sum(len(h[1]) for h in hits_b)}자/{len(hits_b)}곳")
        for label, hits in (("a", hits_a), ("b", hits_b)):
            for trail, chars, snip in hits[:4]:
                one = re.sub(r"\s+", " ", snip).strip()
                print(f"   ({label}) {trail}  [{chars}]  {one[:76]}")
            if len(hits) > 4:
                print(f"   ({label}) … 외 {len(hits) - 4}곳")
        total_a += len(hits_a)
        total_b += len(hits_b)
    print(f"\n합계: (a) 문자 첨자 {total_a}곳 · (b) 수식 자리 첨자 {total_b}곳")
    print("(산문 속 숫자 첨자 m³·m/s² 는 세지 않았다 — 계속 허용되는 표기)")


def main(argv):
    args = argv[1:]
    if "--steam" in args:
        steam(args[args.index("--steam") + 1:])
        return 0
    if "--scripts" in args:
        scripts_report()
        return 0
    ch = next((a for a in args if a in CHAPTERS), None)
    if ch is None:
        overview()
        return 0
    if "--item" in args:
        item(ch, args[args.index("--item") + 1])
    elif "--problems" in args:
        problems(ch)
    elif "--practice" in args:
        practice(ch)
    elif "--figures" in args:
        figures(ch)
    elif "--derivations" in args:
        derivations(ch)
    elif "--keys" in args:
        keys(ch)
    else:
        summary(ch)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
