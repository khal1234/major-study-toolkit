#!/usr/bin/env python
"""삽화 팔레트의 색 하나를 전 챕터에서 갈아끼운다 — 글자 그대로만 바꾼다.

    python tools/recolor_figures.py --map "#f7f4ec=#f0f3ec" [--map ...] [--apply]

## 왜 도구인가 (2026-08-13 신설)

색을 고르는 과정은 **한 번으로 안 끝난다**(영상 논지: *[발화 생략]*).
그런데 삽화 색은 `data/<과목>/chNN.json` 안의 SVG 에 **글자 그대로** 박혀 있어서, 한 번
갈아끼울 때마다 파일 일곱 개를 손으로 고쳐야 했다. 그러면 **반복이 불가능하다.**

- **`--show`(기본)로 먼저 센다.** 어느 챕터에 몇 곳인지 보고 나서 `--apply` 한다.
- **글자 그대로만 바꾼다** — 정규식이 아니다. `fill='#f7f4ec'` 도 `stroke='#f7f4ec'`(halo)도
  같은 값이면 함께 바뀐다. **그게 맞다** — halo 는 종이색이어야 글자를 지워 주기 때문이다.
- **대소문자를 가린다.** 이 리포의 색은 전부 소문자다. 섞이면 그 자리가 안 바뀐 채 남으므로
  대문자 표기를 만나면 **세어서 보고**한다(조용히 놓치지 않는다).
- **과목을 박지 않는다** — 순회는 `audit_content.CHAPTERS` 로 그 워크트리에 실재하는 챕터만.

★ 팔레트 자체를 여기 적지 않는다. **무엇을 무엇으로 바꿀지는 부르는 쪽이 정한다** —
  색은 사람이 고르는 것이라(사용자 판정 2026-08-13) 도구가 값을 알면 그 판정이 코드로 굳는다.
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import audit_content                                                    # noqa: E402

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def parse_pairs(items):
    """`--map "#aaa111=#bbb222"` 들을 (전, 후) 목록으로. 순수 함수 — 테스트가 직접 부른다."""
    pairs, bad = [], []
    for raw in items or []:
        if raw.count("=") != 1:
            bad.append(raw + " (형식은 «#전=#후»)")
            continue
        old, new = raw.split("=")
        old, new = old.strip(), new.strip()
        if not HEX.match(old) or not HEX.match(new):
            bad.append(raw + " (여섯 자리 hex 이어야 한다)")
            continue
        if old.lower() != old or new.lower() != new:
            bad.append(raw + " (이 리포의 색은 소문자로 적는다)")
            continue
        pairs.append((old, new))
    return pairs, bad


def swap(text, pairs):
    """(고친 글, {전: 건수}). 순수 함수.

    ★ **한 번에 다 바꾼다.** 하나씩 순서대로 바꾸면 `A→B` 뒤에 `B→C` 가 오는 순간
      원래 A 였던 것까지 C 가 된다(팔레트를 돌려 쓰는 자리에서 실제로 일어난다).
    """
    counts = {old: 0 for old, _ in pairs}
    if not pairs:
        return text, counts
    lookup = {old: new for old, new in pairs}
    pattern = re.compile("|".join(re.escape(old) for old, _ in pairs))

    def sub(m):
        counts[m.group(0)] += 1
        return lookup[m.group(0)]
    return pattern.sub(sub, text), counts


def main():
    ap = argparse.ArgumentParser(description="삽화 색을 전 챕터에서 갈아끼운다")
    ap.add_argument("--map", action="append", metavar="#전=#후",
                    help="바꿀 색 쌍. 여러 번 줄 수 있다")
    ap.add_argument("--chapter", help="chNN.json 하나만")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    pairs, bad = parse_pairs(args.map)
    if bad:
        for b in bad:
            print("거부 — " + b)
        return 2
    if not pairs:
        print('usage: python tools/recolor_figures.py --map "#f7f4ec=#f0f3ec" [--apply]')
        return 2

    names = ([args.chapter] if args.chapter
             else [n + ".json" for n in audit_content.CHAPTERS])
    total = {old: 0 for old, _ in pairs}
    upper = 0
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        upper += len(re.findall(r"#[0-9a-f]*[A-F][0-9a-fA-F]*\b", text))
        fixed, counts = swap(text, pairs)
        hit = sum(counts.values())
        if not hit:
            continue
        for k, v in counts.items():
            total[k] += v
        print("=== %s — %d곳  (%s)" % (name, hit,
              " · ".join("%s %d" % (k, v) for k, v in counts.items() if v)))
        if args.apply:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(fixed)
            print("  [written] " + name)
    print("\n합계 — " + " · ".join("%s → %s %d곳" % (o, n, total[o]) for o, n in pairs)
          + ("" if args.apply else "  (--apply 를 붙여야 쓴다)"))
    if upper:
        print("★ 대문자로 적힌 색 %d곳이 있다 — 이 도구는 글자 그대로만 보므로 "
              "그 자리는 안 바뀐다. 먼저 소문자로 통일할 것." % upper)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
