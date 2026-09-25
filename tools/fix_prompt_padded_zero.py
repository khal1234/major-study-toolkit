"""문항 지문의 주어진 값에서 유효숫자용 끝자리 0 을 걷는다(`2.00 kg/s` → `2 kg/s`).

재는 것: `practice`·`problems` 의 `prompt`(문자열·{ko,en}) 안의 수. 후보 자는
  `audit_convention_drift.py --check=prompt-padded-zero` 이고 판정 문턱이 같다(`PROMPT_PADDED_NUM`).
문턱: 소수점 뒤가 0 으로 끝나는 수. 앞에 참조어(§·Fig·Table·Example·Problem·Eq·식·그림·표·예제·문제·절)가
  붙은 번호(`7.10`)는 값이 아니라 번호라 건드리지 않는다.
하는 일: 지문 · 그 문항 삽화의 글자(>…<, 좌표 속성은 안 건드린다) · 그 삽화 면제(`lintWaivers.target`)를
  함께 고치고 `changeNote` 를 잇는다(앞 사유는 지우지 않는다). 기록은 `write_chapter`(표기 보존).
  풀이틀·빈칸·답은 안 건드린다 — 유효숫자는 풀이·답의 몫이다.
못 보는 것: 교재 원문이 실제로 0 을 붙인 값 · 측정값의 유효숫자가 주제인 과목(그 과목은 경로에서 뺀다) ·
  `expectedOutput` 이 주어진 값을 되읊는 자리(빌드가 「수치가 지문에 없다」로 잡는다 — 사람이 고친다).

쓰는 법:
  python tools/fix_prompt_padded_zero.py "data/<과목>/chNN.json" …            # 셈만
  python tools/fix_prompt_padded_zero.py --apply "data/<과목>/chNN.json" …
"""
import argparse
import copy
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_convention_drift import PROMPT_PADDED_NUM  # noqa: E402
from buildlib.jsontext import write_chapter            # noqa: E402

REF_BEFORE = re.compile(r"(§|Fig\.?|Figure|Table|Example|Problem|Prob\.|Eq\.?|Sec\.?|Section|Chapter|"
                        r"식|그림|표|예제|문제|절|장)\s*\(?$")

NOTE = ("지적(2026-09-19, 부류 «지문 값의 유효숫자 끝자리 0») 지문의 주어진 값을 교재처럼 적었습니다"
        "(2.00 → 2) — 유효숫자는 풀이·답에서 다룹니다.")


def strip_zero(tok):
    t = tok.rstrip("0")
    return t[:-1] if t.endswith(".") else t


def fix_text(text):
    """지문 한 문자열에서 끝자리 0 을 걷는다. (새 문자열, 바꾼 토큰 목록)"""
    changed = []

    def sub(m):
        if REF_BEFORE.search(text[:m.start()][-12:]):
            return m.group(0)
        new = strip_zero(m.group(1))
        changed.append(m.group(1) + "→" + new)
        return new

    return PROMPT_PADDED_NUM.sub(sub, text), changed


def fix_item(item):
    """문항 하나를 제자리에서 고친다. (바꾼 토큰, 삽화에서 바꾼 토큰)"""
    p = item.get("prompt")
    toks = []
    if isinstance(p, str):
        item["prompt"], toks = fix_text(p)
    elif isinstance(p, dict):
        for k, v in p.items():
            if isinstance(v, str):
                p[k], c = fix_text(v)
                toks += c
    if not toks:
        return [], []
    olds = {t.split("→")[0] for t in toks}
    in_fig = set()

    def only_olds(mm):
        if mm.group(1) in olds:
            in_fig.add(mm.group(1))
            return strip_zero(mm.group(1))
        return mm.group(0)

    for d in item.get("diagrams") or []:
        if not isinstance(d, dict):
            continue
        if isinstance(d.get("svg"), str):
            d["svg"] = re.sub(r">([^<]*)<", lambda m: ">" + PROMPT_PADDED_NUM.sub(only_olds, m.group(1)) + "<", d["svg"])
        # 면제가 바뀐 라벨 글자를 쥐고 있으면 같이 옮긴다 — 안 옮기면 면제가 풀려 빌드가 close 를 막는다
        #   (2026-09-19 유체 ch03 '1.20 m' 실측)
        for w in d.get("lintWaivers") or []:
            if isinstance(w, dict) and isinstance(w.get("target"), str):
                w["target"] = PROMPT_PADDED_NUM.sub(only_olds, w["target"])
    old = item.get("changeNote")
    if not (isinstance(old, str) and NOTE in old):
        item["changeNote"] = (old + " · " + NOTE) if isinstance(old, str) and old.strip() else NOTE
    return sorted(set(toks)), sorted(in_fig)


def one(chapter, apply):
    if not os.path.exists(chapter):
        sys.exit("파일이 없다: " + chapter)
    with open(chapter, encoding="utf-8") as fh:
        before = json.load(fh)
    after = copy.deepcopy(before)
    n = 0
    for coll in ("practice", "problems"):
        for item in after.get(coll) or []:
            if not isinstance(item, dict):
                continue
            toks, in_fig = fix_item(item)
            if toks:
                n += 1
                print("  [고침] %s — %s%s" % (item.get("id"), ", ".join(toks),
                                             ("  [삽화도: %s]" % ", ".join(in_fig)) if in_fig else ""))
    if not n:
        return 0
    if not apply:
        print("합계 — 고칠 문항 %d (%s) · ※ --apply 를 주면 실제로 쓴다" % (n, chapter))
        return 0
    state, why = write_chapter(chapter, before, after)
    print("합계 — 고친 문항 %d (%s) · %s %s" % (n, chapter, state, why))
    return 1 if state == "skipped" else 0


def main():
    ap = argparse.ArgumentParser(description="지문 값의 유효숫자 끝자리 0 을 걷는다")
    ap.add_argument("chapters", nargs="+", help="data/<과목>/chNN.json (여럿 가능)")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다(없으면 셈만)")
    args = ap.parse_args()
    rc = 0
    for path in args.chapters:
        rc |= one(path, args.apply)
    return rc


if __name__ == "__main__":
    sys.exit(main())
