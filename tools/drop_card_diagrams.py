# -*- coding: utf-8 -*-
"""유도 카드에 딸린 `diagrams` 를 걷어낸다 — 슬라이드가 그 그림을 흡수했을 때.

열린 날 2026-08-23. 사용자 지적: *"같은거 위쪽에도 삽화가 있고 아래쪽에도 슬라이드
삽화가 있는데 내용은 같던데 그러면 하나만 하는게 낫지 않나"*. 유도 카드를 슬라이드로
옮길 때 기존 정지 그림을 「요약 그림」이라며 남겼는데, 화면에서는 **같은 그림이 위아래로
두 번** 나온다. 슬라이드의 마지막 단계가 곧 그 그림이라 남길 이유가 없다.

★ **무엇을 지울지는 이 도구가 판정하지 않는다.** 기존 그림이 슬라이드에 없는 내용을
가진 카드가 있다(선례: ch04 폴리트로픽의 n 값별 세 곡선 비교도 — 유지). 카드 id 를
사람이 골라 인자로 준다.

왜 `json.load` → `json.dump` 가 아니라 줄 단위인가 — 다시 덤프하면 파일 전체가 재포맷돼
diff 가 통째로 바뀐다. 검수가 변경점 하이라이트로 도는 리포에서 그건 그 자체로 사고다.
대신 쓴 뒤 `json.load` 로 유효성과 삭제 여부를 실제로 확인한다(규칙 11).

    python tools/drop_card_diagrams.py data/<과목>/chNN.json <카드id> [<카드id>...]
                                       [--note "<changeNote 에 붙일 한 줄>"] [--apply]

`--apply` 없이 돌리면 무엇이 지워질지만 찍는다(기본값이 안전한 쪽).
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CARD_CLOSE = ("      },", "      }")
DIAGRAMS_OPEN = '"diagrams": ['
# 마지막 키면 쉼표가 없다 — 둘 다 받는다(첫 실행이 이 자리에서 걸렸다).
DIAGRAMS_CLOSE = ("        ],", "        ]")


def card_span(lines, card_id):
    """카드 id 줄부터 그 카드를 닫는 줄까지.

    끝을 **들여쓰기**로 잡는다 — 「다음 카드 id 까지」로 잡았더니 마지막 카드에서 파일 끝까지
    번져 연습문제의 diagrams 까지 세었다(첫 실행 실측: 1건이어야 할 것이 27건).
    """
    starts = [i for i, l in enumerate(lines) if l.strip() == '"id": "%s",' % card_id]
    if len(starts) != 1:
        sys.exit("카드 id '%s' 를 한 번에 못 찾았다 (%d건)" % (card_id, len(starts)))
    s = starts[0]
    ends = [i for i in range(s + 1, len(lines)) if lines[i].rstrip("\n") in CARD_CLOSE]
    if not ends:
        sys.exit("카드 '%s' 를 닫는 줄을 못 찾았다" % card_id)
    return s, ends[0] + 1


def strip_one(lines, card_id, note):
    s, e = card_span(lines, card_id)

    if note:
        notes = [i for i in range(s, e) if lines[i].startswith('        "changeNote": "')]
        if len(notes) != 1:
            sys.exit("'%s' 의 changeNote 가 한 줄이 아니다 (%d건)" % (card_id, len(notes)))
        n = notes[0]
        if not lines[n].endswith('",\n'):
            sys.exit("'%s' 의 changeNote 가 여러 줄에 걸쳐 있다 — 손으로 고칠 것" % card_id)
        lines[n] = lines[n][:-3] + note + '",\n'

    opens = [i for i in range(s, e) if lines[i].strip() == DIAGRAMS_OPEN]
    if len(opens) != 1:
        sys.exit("'%s' 의 diagrams 블록이 하나가 아니다 (%d건)" % (card_id, len(opens)))
    d = opens[0]
    closes = [i for i in range(d + 1, e) if lines[i].rstrip("\n") in DIAGRAMS_CLOSE]
    if not closes:
        sys.exit("'%s' 의 diagrams 를 닫는 줄을 못 찾았다" % card_id)
    end = closes[0]

    fig_ids = [l.split('"')[3] for l in lines[d:end + 1] if l.strip().startswith('"id": "fig')]
    del lines[d:end + 1]

    # 마지막 키였으면 앞 줄의 쉼표를 뗀다(안 떼면 JSON 이 깨진다)
    if lines[d].strip() in ("},", "}") and lines[d - 1].rstrip("\n").endswith(","):
        lines[d - 1] = lines[d - 1].rstrip("\n")[:-1] + "\n"

    return end - d + 1, fig_ids


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    path = argv[1]
    card_ids, note, apply_it = [], "", False
    rest = argv[2:]
    i = 0
    while i < len(rest):
        if rest[i] == "--apply":
            apply_it = True
        elif rest[i] == "--note":
            i += 1
            note = rest[i]
        else:
            card_ids.append(rest[i])
        i += 1
    if not card_ids:
        sys.exit("걷어낼 카드 id 를 하나 이상 줄 것")

    with io.open(path, encoding="utf-8") as fh:
        lines = fh.readlines()

    total = 0
    for card_id in card_ids:
        n_lines, fig_ids = strip_one(lines, card_id, note)
        total += len(fig_ids)
        print("  %-28s 그림 %s (%d줄)" % (card_id, ", ".join(fig_ids) or "?", n_lines))

    if not apply_it:
        print("[미적용] %s — 카드 %d장 / 그림 %d장. 실제로 지우려면 --apply"
              % (os.path.basename(path), len(card_ids), total))
        return 0

    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.writelines(lines)
    with io.open(path, encoding="utf-8") as fh:
        ch = json.load(fh)
    left = [f["id"] for f in ch.get("derivation", {}).get("formulas", [])
            if f["id"] in card_ids and f.get("diagrams")]
    if left:
        sys.exit("지웠다고 했는데 남아 있다: %s" % ", ".join(left))
    print("[적용] %s — 카드 %d장 / 그림 %d장 걷어냄 · JSON 유효"
          % (os.path.basename(path), len(card_ids), total))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
