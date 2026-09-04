# -*- coding: utf-8 -*-
"""챕터가 `status: "done"`인데 문풀(practice)·연습문제(problems)가 비어 있는가 (읽기 전용).

열린 날 2026-09-02 — 기계요소설계(medesign) 세션에서 13개 챕터의 **이론·유도만** 채우고
`practice`·`problems`는 전부 빈 배열(`[]`)로 둔 채, close_report·build_site가 초록이라는
이유로 "남은 거 없다"고 사용자에게 보고했다. 사용자 지적: [사용자 발화 인용 생략]

**무엇이 새어나갔나.** `build_site.py`와 `close_report.py`는 **이미 있는 데이터의 품질**만
잰다 — `practice: []`은 문법적으로 유효한 빈 배열이라 어떤 lint도 안 걸린다. `status: "done"`은
저자가 스스로 매기는 값이라, "이론만 끝내고 done을 찍는" 것을 막을 장치가 없었다. 그 결과
"빌드 통과 + 커밋됨"과 "이 챕터가 정말 끝났다"가 겉보기에 구별되지 않았다(AGENTS 규칙 11의
연장 — 근거를 댔지만 그 근거가 하려는 주장과 안 맞았다).

**이 도구가 하는 일.** `status: "done"`인 챕터마다 `practice`·`problems`가 비어 있는지 센다.
비어 있어도 실패로 찍지 않는 경우는 딱 하나 — `index.json`의 `contentWaivers`에 그 컬렉션·
그 챕터가 **사유와 함께** 선언되어 있을 때뿐이다(다른 강도 판정과 같은 자리 — `strictWaivers`
패턴을 그대로 따른다). 선언 없이 비어 있으면 [FAIL]이다.

    python tools/audit_chapter_completeness.py              # 전체
    python tools/audit_chapter_completeness.py --fail-only  # 실패만

**판정하지 않는다.** "문풀·연습문제를 지금 채워야 하는가"는 이 도구가 답할 문제가 아니다 —
정말로 이론만 먼저 쌓고 나중에 채우기로 했다면 `contentWaivers`에 사유를 적어 선언하면 된다.
이 도구가 막는 것은 **그 결정 자체가 없이 조용히 "완료"로 굳는 것**이다.

과목 이름을 하드코딩하지 않는다 — `audit_content.discover_data_dir()`를 그대로 쓴다(과목 =
워크트리이므로 이 리포에는 `data/` 아래 과목 폴더가 하나뿐이다). 절대 파일을 쓰지 않는다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_content import DATA  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COLLECTIONS = ("practice", "problems")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def waived_chapters(index_data, collection):
    """`contentWaivers.<collection>.chapters`에 적힌 파일명 집합. 선언 없으면 빈 집합."""
    waivers = index_data.get("contentWaivers") or {}
    entry = waivers.get(collection) or {}
    if not entry.get("reason"):
        return set()          # 사유 없는 선언은 선언이 아니다 (AGENTS strictWaivers와 같은 판정선)
    return set(entry.get("chapters") or [])


def main():
    fail_only = "--fail-only" in sys.argv
    index_path = os.path.join(DATA, "index.json")
    if not os.path.isdir(DATA) or not os.path.isfile(index_path):
        print("[해당 없음] 이 워크트리에 과목 데이터가 없다 — 0건")
        return 0

    index_data = load_json(index_path)
    chapters = index_data.get("chapters") or []
    waived = {c: waived_chapters(index_data, c) for c in COLLECTIONS}

    done_count = 0
    empty_unwaived = []   # (file, collection)
    empty_waived = []      # (file, collection, reason)

    for entry in chapters:
        if entry.get("status") != "done":
            continue
        file_name = entry.get("file")
        if not file_name:
            continue
        ch_path = os.path.join(DATA, file_name)
        if not os.path.isfile(ch_path):
            continue          # index.json이 아직 없는 파일을 가리키는 것은 다른 검사(build_site)의 몫
        done_count += 1
        ch_data = load_json(ch_path)
        for collection in COLLECTIONS:
            if ch_data.get(collection):
                continue      # 채워져 있다
            if file_name in waived[collection]:
                reason = (index_data.get("contentWaivers") or {}).get(collection, {}).get("reason", "")
                empty_waived.append((file_name, collection, reason))
            else:
                empty_unwaived.append((file_name, collection))

    if not fail_only:
        print(f"[요약] status=done 챕터 {done_count}개 확인")
        for file_name, collection, reason in empty_waived:
            print(f"  [면제] {file_name} {collection} 비어 있음 — {reason}")

    for file_name, collection in empty_unwaived:
        print(f"[FAIL] {file_name}: status=done인데 {collection}가 비어 있고 선언된 면제도 없다"
              f" — index.json의 contentWaivers.{collection}에 사유와 함께 적거나 채울 것")

    if empty_unwaived:
        return 1
    if not fail_only:
        print("[ok] status=done 챕터 중 미선언 빈 컬렉션 0건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
