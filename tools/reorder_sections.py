#!/usr/bin/env python
"""이론 절의 **순서만** 바꾼다 — 내용은 한 글자도 건드리지 않는다.

왜 도구인가 (열린 날 2026-08-02):
    절 하나는 본문·삽화·이해도 체크가 붙은 수 KB 짜리 객체라 손으로 잘라 붙이면
    **조용히 한 글자가 어긋난다** — 그건 diff 로도 눈에 안 띈다. 그래서 순서 바꾸기만
    담당하는 도구를 둔다.

★ 이 도구를 **언제 쓰지 않는가** (정정 2026-08-02, 사용자):
    처음 이 자리에는 *[발화 생략]* 이라고
    적혀 있었다. **그 읽기가 틀렸다.** 사용자 원문: *[발화 생략]*

    - 순서 1:1 은 **위반이 아니라 신호**다(감사도 `[FAIL]` 이 아니라 `[blind spot]`).
    - **의존 관계가 순서를 정하는 곳은 바꾸지 않는 것이 옳다** — 힘을 정의하기 전에
      모멘트를 가르칠 수 없다.
    - **감사를 조용히 시키려고 절을 옮기지 말 것.** 독자만 손해를 보고 규칙의 목적
      (닮지 않게)과도 무관하다. 바꿀 이유가 없으면 **판정을 남기고 둔다.**
    - 재구성의 정본 형태는 **합치기·나누기·경계 옮기기**이고 순서 바꾸기는 가장 드물다.

    내용 수정(§ 번호 상호참조 고치기 등)은 이 도구가 하지 않는다 — 그건 사람이 판단할
    몫이고, 섞으면 무엇이 바뀌었는지 흐려진다.

쓰기 규율: 기본은 **보고만** 한다. `--apply` 를 줘야 파일을 쓴다.

    python tools/reorder_sections.py --chapter ch12.json --move sec-a --before sec-b
    python tools/reorder_sections.py --chapter ch12.json --move sec-a --after sec-b --apply

★ 유도 카드도 같은 도구로 옮긴다 — `--collection derivation` (신설 2026-08-02).
    사용자 지적: *[발화 생략]* — 옳다. 이론만 재배열하고
    유도를 두면 **두 탭이 서로 다른 이야기를 한다.** 실측(공학수학 ch01): 이론은
    변수분리 → 선형 → 완전미분 → 적분인자인데 유도는 교재 순서 그대로
    변수분리 → 완전미분 → 적분인자 → 선형이었고, 그 결과 이론 본문의
    *[발화 생략]* 가 유도 탭에서는 거짓이 됐다.
    이 도구가 이론만 다뤘던 것이 그 상태를 **손이 많이 가는 쪽**으로 만든 원인이다.

★ 옮긴 뒤 반드시 할 것 (이 도구는 못 한다):
    ⑴ 본문의 절 상호참조를 새 번호로 고친다 — 번호가 바뀌면 글이 거짓말을 한다
       (이 리포는 `[[chNN:sec-id|N절 제목]]` 내부 링크를 쓰고, 그 `N` 이 실제 순서와
        맞는지는 빌드 `theory_link_number_issues` 가 검사한다)
    ⑵ 옮긴 절이 **뒤 절의 내용을 전제하고 있지 않은지** 본다(앞으로 옮기면 전제가 깨진다)
    ⑶ **이론을 옮겼으면 유도도 같이 본다** — 위 실사고가 정확히 그 자리다
    ⑷ `python tools/build_site.py --all` · `python tools/audit_content.py`
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from audit_content import DATA  # noqa: E402


def move_section(sections, move_id, before_id=None, after_id=None):
    """순서를 바꾼 새 목록을 돌려준다. 순수 함수 — 테스트가 직접 부른다.

    같은 id 가 둘이면 곧바로 실패한다(어느 것을 옮길지 알 수 없다).
    """
    ids = [s.get("id") for s in sections]
    for target in (move_id, before_id or after_id):
        if ids.count(target) != 1:
            raise ValueError("절 id 를 하나로 특정할 수 없다: " + repr(target)
                             + " (발견 " + str(ids.count(target)) + "개)")
    if move_id == (before_id or after_id):
        raise ValueError("자기 자신을 기준으로 옮길 수 없다: " + repr(move_id))

    rest = [s for s in sections if s.get("id") != move_id]
    moving = sections[ids.index(move_id)]
    anchor = before_id or after_id
    at = [s.get("id") for s in rest].index(anchor)
    rest.insert(at if before_id else at + 1, moving)
    return rest


# 컬렉션 이름 → (JSON 상위 키, 목록 키). 유도를 나중에 덧붙인 것이 아니라
# **처음부터 같은 자리**로 다루기 위한 표다 — 갈라 두면 한쪽만 고치는 오늘의 결함이 반복된다.
COLLECTIONS = {"theory": ("theory", "sections"), "derivation": ("derivation", "formulas"),
               # ★ 2026-09-08 신설 — 사용자 판정으로 **연습문제는 쉬운 것부터** 놓게 됐다
               #   (*[발화 생략]*).
               #   문항은 최상위 리스트라 owner 가 없다. 화면 번호는 **위치**가 매기므로
               #   (뷰어 `'Q' + (i+1)`) 순서만 바꾸면 독자가 보는 번호가 따라 바뀌고,
               #   **id 는 그대로 둔다** — id 를 재번호하면 검산기 라벨 228곳과 다른 장의
               #   verbatim 슬롯까지 따라와야 하고, 하나만 어긋나도 검산이 엉뚱한 문항에 붙는다.
               "problems": (None, "problems"), "practice": (None, "practice")}


def main():
    ap = argparse.ArgumentParser(description="이론 절·유도 카드 순서 바꾸기 (내용은 안 건드린다)")
    ap.add_argument("--chapter", required=True, help="chNN.json")
    ap.add_argument("--collection", default="theory", choices=sorted(COLLECTIONS),
                    help="theory(기본) | derivation | problems | practice")
    ap.add_argument("--move", required=True, help="옮길 절·카드 id")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--before", help="이 절 **앞**으로")
    group.add_argument("--after", help="이 절 **뒤**로")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 쓴다")
    args = ap.parse_args()

    path = os.path.join(DATA, args.chapter)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    owner_key, list_key = COLLECTIONS[args.collection]
    sections = (data.get(list_key) if owner_key is None
                else (data.get(owner_key) or {}).get(list_key)) or []
    if not sections:
        print(args.collection + " 항목이 없다 — 아무것도 하지 않았다")
        return 1

    before = [s.get("id") for s in sections]
    reordered = move_section(sections, args.move, args.before, args.after)
    if owner_key is None:
        data[list_key] = reordered
    else:
        data[owner_key][list_key] = reordered
    after = [s.get("id") for s in reordered]

    print("[대상] " + path)
    for i, (b, a) in enumerate(zip(before, after), 1):
        mark = "   " if b == a else " ->"
        print(f"{mark} §{i:<2} {b:<28} → {a}")
    if before == after:
        print("\n순서가 그대로다 — 쓰지 않았다")
        return 0
    if not args.apply:
        print("\n(보고만 했다 — 쓰려면 --apply)")
        return 0

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("\n저장했다. ★ 본문의 §N 상호참조와 '앞 절 전제'를 직접 고칠 것 — 이 도구는 안 한다.")
    if owner_key is None:
        print("★ 문항은 화면 번호가 **위치**로 매겨진다 — Q 번호가 바뀌었고 id 는 그대로다."
              "\n   「앞 문항에서 본 것처럼」 같은 산문과 다른 장의 참조를 직접 볼 것.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
