# -*- coding: utf-8 -*-
"""문항·문풀의 **id ↔ 화면 번호** 표를 찍는다.

    python tools/screen_numbers.py                     # 전 챕터
    python tools/screen_numbers.py --chapter=ch02      # 한 챕터
    python tools/screen_numbers.py --id=ch02-q16       # 하나만 (역방향도 됨: --id=문항15)

**왜 있나 (열린 날 2026-08-05, 사용자 2회 연속 지적).**
*[발화 생략]* · *[발화 생략]*

뷰어는 배열 **순서대로** 1, 2, 3… 을 붙이는데 id 는 만들 때 붙인 이름이라 **중간이 빠지면
둘이 어긋난다.** 실측(열역학 ch02): 문항은 `q08` 이 없어 `q09` 부터 −1, 문풀은 `p02` 가 없어
`p03` 부터 −1 — **어긋나는 지점이 둘이고 값도 다르다.**

★ **이걸 기억으로 메우면 반드시 틀린다.** 실제로 두 번 연속 틀렸다: 한 번은 문풀 어긋남을
  몰라서(인계 메모에 문항 것만 적혀 있었다), 다음 번은 문항 규칙을 **적어 놓고도 적용을 빼먹어서**.
  두 번째가 중요하다 — *규칙을 아는 것과 매번 적용하는 것은 다른 일*이라, 메모를 더 잘 쓰는
  것으로는 안 닫힌다. 사람이 세지 않게 **표를 기계가 찍는다.**

과목을 모른다 — 브랜치에서 얻고 `data/<과목>/chNN.json` 을 순회한다(AGENTS 「공통 도구에
과목별 사실을 박지 않는다」).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.join(ROOT, "data")
CHAPTER_RE = re.compile(r"ch\d+\.json")

# 배열 이름 → 화면에서 부르는 이름. 뷰어가 이 두 컬렉션에만 번호를 붙인다.
SECTIONS = (("practice", "문풀"), ("problems", "문항"))


def screen_map(chapter):
    """챕터 dict → [(화면이름, id, 화면번호), …]. 순수 함수 — 테스트가 부른다.

    번호는 **배열 순서**다. id 안의 숫자를 쓰지 않는 것이 이 도구의 전부다.
    """
    out = []
    for key, label in SECTIONS:
        for i, item in enumerate(chapter.get(key) or []):
            out.append((label, item.get("id") or "?", i + 1))
    return out


def gaps(rows):
    """id 의 숫자와 화면 번호가 어긋나기 시작하는 지점 — (화면이름, 그 id, 차이)."""
    out, seen = [], set()
    for label, item_id, n in rows:
        m = re.search(r"(\d+)\s*$", item_id)
        if not m:
            continue
        diff = n - int(m.group(1))
        if diff != 0 and label not in seen:
            seen.add(label)
            out.append((label, item_id, diff))
    return out


def main():
    sys.path.insert(0, os.path.join(ROOT, ".claude", "hooks"))
    from guard_bash import subject_of_branch, _current_branch                # noqa: E402
    arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--subject=")), None)
    mine = arg or subject_of_branch(_current_branch(""))
    dirs = [n for n in sorted(os.listdir(DATA_ROOT))
            if mine and n.startswith(mine) and os.path.isdir(os.path.join(DATA_ROOT, n))]
    if not dirs:
        print("거부 — 이 브랜치의 과목 폴더를 찾지 못했다(과목=" + str(mine) + ").")
        return 2
    only_ch = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--chapter=")), None)
    only_id = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--id=")), None)
    data_dir = os.path.join(DATA_ROOT, dirs[0])

    for name in sorted(os.listdir(data_dir)):
        if not CHAPTER_RE.fullmatch(name):
            continue
        stem = os.path.splitext(name)[0]
        if only_ch and stem not in (only_ch, name):
            continue
        with open(os.path.join(data_dir, name), encoding="utf-8") as fh:
            chapter = json.load(fh)
        rows = screen_map(chapter)
        if only_id:
            rows = [r for r in rows if only_id == r[1] or only_id == r[0] + str(r[2])]
            if not rows:
                continue
        print("=" * 60)
        print(stem + "  —  " + dirs[0])
        off = gaps(screen_map(chapter))
        if off:
            for label, item_id, diff in off:
                print("  ⚠ %s 은 %s 부터 화면번호 = id %+d" % (label, item_id, diff))
        else:
            print("  (빠진 번호 없음 — id 숫자 = 화면 번호)")
        print("=" * 60)
        for label, item_id, n in rows:
            print("  %-4s %-14s →  %s %d번" % (label, item_id, label, n))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
