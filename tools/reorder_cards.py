# -*- coding: utf-8 -*-
"""컬렉션 안의 **카드 순서**를 바꾼다 — 표기를 보존한 채로.

    python tools/reorder_cards.py --chapter=ch02.json --collection=formulas \\
        --order=kinetic-energy,potential-energy,total-energy [--apply]

`--order` 에 적은 id 들이 **지금 차지하고 있는 자리들**을 그 순서로 다시 채운다.
적지 않은 카드는 자리가 그대로다 — 그래서 한 곳만 고쳐도 나머지 diff 가 생기지 않는다.

## 왜 도구인가 (2026-08-12)

사용자 지적(열역학 부류 4): *[발화 생략]*
**같은 부류가 과목마다 난다** — 카드 순서가 학습 순서와 어긋나는 것은 열역학 특유가 아니다.

손으로 옮기면 안 되는 이유는 셋이다:
  ⑴ 카드 하나가 40~90줄이라 **블록 경계를 눈으로 잡다가 중괄호가 어긋난다.**
  ⑵ `json.load` → `json.dump` 로 다시 쓰면 **파일 전체의 표기가 바뀌어** diff 가 통째로 뜨고
     이스케이프가 달라질 수 있다(`set_derivation_kind.py` 가 같은 이유로 텍스트를 보존한다).
  ⑶ 마지막 카드만 **쉼표가 없어서**, 옮기면 그 자리에서 JSON 이 깨진다.

그래서 **줄 단위로 블록을 떼어 옮기고 쉼표만 다시 붙인 뒤 재파싱으로 검증**한다.
검증에 실패하면 아무것도 쓰지 않는다.

★ **무엇을 바꿀지는 판정하지 않는다.** 학습 순서가 맞는지는 사람이 본다 — 이 도구는
  *그 판정을 안전하게 실행하는 손*이다(`fix_velocity_symbol` 이 판정을 안 하는 것과 같다).
"""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent


def data_root():
    """이 리포의 `data/<과목>` — 과목 이름을 코드에 박지 않는다(공통 도구 규칙).

    ★ 2026-09-14: 평탄화(2026-09-06)로 `data/` 아래 과목이 21개가 되자 「하나로 특정할 수
      없다」로 **어느 과목에서도 못 돌았다.** 과목은 다른 도구와 같은 `SUBJECT` 환경변수로
      지목한다. `--chapter` 에 `data/<과목>/chNN.json` 경로를 주면 이 함수를 안 거친다.
    """
    want = os.environ.get("SUBJECT", "").strip()
    if want:
        p = REPO / "data" / want
        return p if p.is_dir() else None
    roots = [p for p in (REPO / "data").iterdir() if p.is_dir()] if (REPO / "data").is_dir() else []
    return roots[0] if len(roots) == 1 else None


def blocks(lines, collection):
    """[(id, 시작줄, 끝줄)] — 그 컬렉션의 카드들. 순수 함수(테스트가 직접 부른다).

    카드는 **컬렉션 여는 줄보다 두 칸 더 들여쓴** `{` 로 열리고 같은 깊이의 `}` 로 닫힌다.

    ★ 2026-08-27: 들여쓰기가 4칸/6칸으로 박혀 있어 **최상위 컬렉션(`problems`·`practice`)을
      통째로 못 봤다.** 처음 쓴 자리가 `derivation.formulas`(4칸) 하나뿐이라 그 하나에 맞춰
      짠 것이고, `--collection=problems` 는 「그 컬렉션에 없는 id」로 떨어졌다 — **컬렉션이
      없다는 말과 카드가 없다는 말이 같은 문장으로 나온 자리**다. 이제 깊이는 파일에서 잰다.
    """
    start = key_indent = None
    for i, ln in enumerate(lines):
        if ln.strip() == '"%s": [' % collection:
            key_indent = len(ln) - len(ln.lstrip(" "))
            start = i + 1
            break
    if start is None:
        return []
    card_open = " " * (key_indent + 2) + "{"
    card_close = (" " * (key_indent + 2) + "},", " " * (key_indent + 2) + "}")
    coll_close = (" " * key_indent + "],", " " * key_indent + "]")
    out, depth, open_at, cid = [], 0, None, None
    for i in range(start, len(lines)):
        if depth == 0 and lines[i].rstrip() in coll_close:
            break
        if lines[i].rstrip() == card_open:
            depth, open_at, cid = 1, i, None
            continue
        if depth == 1 and cid is None and lines[i].lstrip().startswith('"id":'):
            cid = lines[i].split('"')[3]
        if depth == 1 and lines[i].rstrip() in card_close:
            out.append((cid, open_at, i))
            depth, open_at, cid = 0, None, None
    return out


def reorder(lines, collection, order):
    """새 lines 를 돌려준다. 순수 함수. 이름이 없으면 ValueError."""
    found = blocks(lines, collection)
    index = {cid: n for n, (cid, _, _) in enumerate(found)}
    missing = [c for c in order if c not in index]
    if missing:
        raise ValueError("그 컬렉션에 없는 id: " + ", ".join(missing))
    slots = sorted(index[c] for c in order)
    plan = dict(zip(slots, order))                     # 자리 → 그 자리에 올 카드
    body = []
    for n, (cid, a, b) in enumerate(found):
        pick = plan.get(n, cid)
        _, pa, pb = found[index[pick]]
        chunk = lines[pa:pb + 1]
        chunk[-1] = chunk[-1].rstrip().rstrip(",")
        body.append(chunk)
    # 마지막 카드만 쉼표가 없다 — 옮기고 나서 다시 붙인다.
    # ★ **줄바꿈을 반드시 되붙인다.** 처음엔 `rstrip()` 으로 개행까지 지운 뒤 쉼표만 붙였는데,
    #   그러면 파일에 쓸 때 `      },      {` 로 **두 카드가 한 줄로 붙는다.** JSON 으로는
    #   유효해서 빌드가 통과했고, 회귀 테스트도 **리스트를 봐서** 못 잡았다(리스트에서는 여전히
    #   두 원소다). 자를 파일 기준으로 보지 않으면 이런 것이 통과한다.
    for n, chunk in enumerate(body):
        chunk[-1] = chunk[-1] + ("," if n < len(body) - 1 else "") + "\n"
    out = list(lines[:found[0][1]])
    for chunk in body:
        out.extend(chunk)
    out.extend(lines[found[-1][2] + 1:])
    return out


def main():
    chapter = collection = None
    order, apply = [], "--apply" in sys.argv
    for arg in sys.argv[1:]:
        if arg.startswith("--chapter="):
            chapter = arg.split("=", 1)[1]
        elif arg.startswith("--collection="):
            collection = arg.split("=", 1)[1]
        elif arg.startswith("--order="):
            order = [s.strip() for s in arg.split("=", 1)[1].split(",") if s.strip()]
    if not (chapter and collection and len(order) >= 2):
        sys.exit("쓰는 법: --chapter=chNN.json --collection=formulas --order=id1,id2[,...] [--apply]")
    direct = REPO / chapter
    if direct.is_file():
        path = direct
    else:
        root = data_root()
        if root is None:
            sys.exit("data/ 아래 과목 폴더를 하나로 특정할 수 없다 — SUBJECT=<과목> 을 주거나"
                     " --chapter=data/<과목>/chNN.json 경로로 줄 것")
        path = root / chapter
    if not path.is_file():
        sys.exit("없는 파일: %s" % path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    before = [cid for cid, _, _ in blocks(lines, collection)]
    try:
        new = reorder(lines, collection, order)
    except ValueError as exc:
        sys.exit(str(exc))
    text = "".join(new)
    try:
        json.loads(text)                               # 검증 못 하면 아무것도 안 쓴다
    except ValueError as exc:
        sys.exit("[중단] 옮긴 결과가 JSON 이 아니다 — %s" % exc)
    after = [cid for cid, _, _ in blocks(new, collection)]
    moved = [(b, a) for b, a in zip(before, after) if b != a]
    for b, a in moved:
        print("  %-28s → %s" % (b, a))
    print("%s %s — 자리 %d곳 바뀜%s" % (chapter, collection, len(moved),
                                     "" if apply else "  (미리보기 — 쓰려면 --apply)"))
    if apply and moved:
        path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
