"""이해도 체크·함정 카드에 **id 가 없는 자리**를 센다 (읽기 전용).

왜 열렸나 (2026-09-08): 겹침 게이트 [L] 은 판정을 `chNN::<왼쪽 id>::<오른쪽 id>` 로
키를 만들어 적는데, **카드에 id 가 없으면 그 키를 만들 수 없다.** 빌드는 그때
"판정을 적을 키를 만들 수 없으니 그 카드에 id 를 붙일 것"으로 멈춘다(기계요소설계 ch01
에서 실제로 걸렸다). 그런데 그 멈춤은 **문턱을 넘은 쌍이 생겼을 때만** 일어나므로,
id 가 없는 카드가 얼마나 있는지는 게이트로는 알 수 없다 — 이 자가 그것을 센다.

★ 이 자는 세기만 한다(실행 규율 17 이 말하는 「재는 자」). 마감을 막는 자리는 빌드의
겹침 게이트 그대로이고, 여기서 나온 수는 **어느 과목을 먼저 손볼지**를 고르는 데 쓴다.

  python tools/audit_card_ids.py            # 전 과목 요약
  python tools/audit_card_ids.py --only=기계재료   # 한 과목의 자리까지
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

# 카드가 사는 자리 — 절 안의 세 목록. 본문 문단은 id 를 갖지 않는 것이 정상이라 안 센다.
CARD_KEYS = ("pitfalls", "comprehensionChecks")


def walk_sections(node, path=()):
    """절처럼 생긴 dict(=CARD_KEYS 중 하나를 가진 것)를 전부 낸다."""
    if isinstance(node, dict):
        if any(k in node for k in CARD_KEYS):
            yield path, node
        for key, value in node.items():
            yield from walk_sections(value, path + (str(key),))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from walk_sections(item, path + (str(i),))


def scan(subject_dir):
    """(챕터, 절 id, 목록 이름, 몇 번째) 목록 — id 가 없는 카드만."""
    out = []
    for name in sorted(os.listdir(subject_dir)):
        if not re.fullmatch(r"ch\d+\.json", name):
            continue
        with open(os.path.join(subject_dir, name), encoding="utf-8") as fh:
            chapter = json.load(fh)
        for _, section in walk_sections(chapter):
            sec_id = section.get("id") or "?"
            for key in CARD_KEYS:
                for i, card in enumerate(section.get(key) or []):
                    if isinstance(card, dict) and not card.get("id"):
                        out.append((os.path.splitext(name)[0], sec_id, key, i))
    return out


def main():
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), None)
    rows = {}
    for subject in sorted(os.listdir(DATA)):
        sub_dir = os.path.join(DATA, subject)
        if not os.path.isdir(sub_dir):
            continue
        if only and subject != only:
            continue
        rows[subject] = scan(sub_dir)

    total = sum(len(v) for v in rows.values())
    print("=== id 없는 카드 — 순회한 과목 %d개 · 합계 %d건 ===" % (len(rows), total))
    print("  ※ id 가 없으면 겹침 게이트가 판정 키를 만들 수 없다(빌드가 그때 멈춘다).")
    for subject, found in sorted(rows.items(), key=lambda kv: -len(kv[1])):
        if not found:
            continue
        print("  %-24s %3d건" % (subject, len(found)))
        if only:
            for ch, sec, key, i in found:
                print("      %s  %-28s %s[%d]" % (ch, sec, key, i))
    if total == 0:
        print("  없음 — 모든 카드에 id 가 있다.")


if __name__ == "__main__":
    main()
