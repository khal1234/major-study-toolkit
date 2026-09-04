# -*- coding: utf-8 -*-
"""문항 하나를 **다른 챕터 파일로 통째로 옮긴다** — 줄 단위로.

열린 날 2026-08-27. 사용자 판정:

    *"중간고사 대비용이니까 2벌로 쪼개고 75분 x2 로 하면 될 것 같은데 그러면 시험에
    12~15장 에서 1개씩 나온다 치면 대비는 2개씩 할 수 있는거잖아"*

한 벌로 만든 모의고사가 제한 시간을 넘겨서 **문항을 덜어 새 챕터로 옮겨야** 했다.
이 부류는 한 번으로 안 끝난다 — 기말 모의고사도 같은 자리에 선다.

왜 `json.load` → `json.dump` 가 아니라 줄 단위인가 — 다시 덤프하면 파일 전체가 재포맷돼
diff 가 통째로 바뀐다. 검수가 변경점 하이라이트로 도는 리포에서 그건 그 자체로 사고다
(`drop_card_diagrams.py` · `drop_exam_steps.py` 가 같은 이유로 같은 형태다).
대신 쓴 뒤 `json.load` 로 유효성과 이사 여부를 실제로 확인한다(규칙 11).

    python tools/split_problems.py --from data/<과목>/chAA.json \\
           --to data/<과목>/chBB.json <옛id>[=<새id>] [<옛id>=<새id> ...] [--apply]

- `=<새id>` 를 주면 **그 블록 안의 옛 id 문자열을 전부** 새 id 로 바꾼다. 문항 id 뿐 아니라
  거기서 파생된 삽화 id(`fig-<문항id>-<이름>`)까지 한 번에 따라온다.
- 옮기는 **순서가 곧 붙는 순서**다. 자리를 다시 짜려면 `reorder_cards.py --collection=problems`.
- **무엇을 옮길지는 판정하지 않는다** — 사람이 id 로 준다. 원본 챕터의 문항을 전부 옮기려
  하면 거부한다(빈 시험지가 된다).
- 옮긴 뒤 사람이 할 것: `index.json` 등록 · `textbook-pdf-map.json` · 독자성 판정 키 ·
  검산 스크립트의 케이스 id · `sourceRef` 안의 옛 장 이름.
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROBLEM_OPEN = "    {"
PROBLEM_CLOSE = ("    },", "    }")
PROBLEMS_OPEN = '"problems": ['
PROBLEMS_CLOSE = ("  ],", "  ]")
ID_RE = re.compile(r'^\s*"id": "([^"]+)",\s*$')


def problems_span(lines, path):
    """`"problems": [` 줄과 그것을 닫는 줄의 index."""
    opens = [i for i, l in enumerate(lines) if l.strip().startswith(PROBLEMS_OPEN)]
    if len(opens) != 1:
        sys.exit("%s 의 problems 블록이 하나가 아니다 (%d건)"
                 % (os.path.basename(path), len(opens)))
    d = opens[0]
    if lines[d].strip() in ('"problems": [],', '"problems": []'):
        sys.exit("%s 의 problems 가 한 줄짜리 빈 배열이다 — 문항 하나를 손으로 넣고 나서 옮길 것"
                 % os.path.basename(path))
    closes = [i for i in range(d + 1, len(lines)) if lines[i].rstrip("\n") in PROBLEMS_CLOSE]
    if not closes:
        sys.exit("%s 의 problems 를 닫는 줄을 못 찾았다" % os.path.basename(path))
    return d, closes[0]


def block_starts(lines, d, c):
    """problems 배열 바로 아래 층의 여는 줄들 — 들여쓰기로 잡는다(중첩과 안 헷갈린다)."""
    return [i for i in range(d + 1, c) if lines[i].rstrip("\n") == PROBLEM_OPEN]


def problem_span(lines, d, c, pid, path):
    """문항 id 줄이 든 블록의 [여는 줄, 닫는 줄] — 끝은 들여쓰기로 잡는다.

    「다음 문항 id 까지」로 잡으면 마지막 문항에서 파일 끝까지 번진다
    (`drop_card_diagrams.card_span` 이 그 자리에서 한 번 깨졌다).
    """
    hits = [i for i in range(d + 1, c) if ID_RE.match(lines[i])
            and ID_RE.match(lines[i]).group(1) == pid]
    hits = [i for i in hits if lines[i - 1].rstrip("\n") == PROBLEM_OPEN]
    if len(hits) != 1:
        sys.exit("%s 안에서 문항 id '%s' 를 한 번에 못 찾았다 (%d건)"
                 % (os.path.basename(path), pid, len(hits)))
    s = hits[0] - 1
    ends = [i for i in range(s + 1, c + 1) if lines[i].rstrip("\n") in PROBLEM_CLOSE]
    if not ends:
        sys.exit("문항 '%s' 를 닫는 줄을 못 찾았다" % pid)
    return s, ends[0]


def normalize_tail(block):
    """블록의 마지막 줄에서 쉼표를 뗀다 — 붙이는 쪽에서 다시 붙인다."""
    out = list(block)
    out[-1] = "    }\n"
    return out


def rename_in(block, old, new):
    return [l.replace(old, new) for l in block]


def parse_targets(argv):
    targets = []
    for a in argv:
        if a.startswith("--"):
            continue
        old, _, new = a.partition("=")
        if not old:
            sys.exit("형식은 <옛id>[=<새id>] 다 — 받은 것: %r" % a)
        targets.append((old, new or old))
    return targets


def flag_value(argv, name):
    for i, a in enumerate(argv):
        if a == name:
            if i + 1 >= len(argv):
                sys.exit("%s 뒤에 경로가 없다" % name)
            return argv[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return None


def main(argv):
    src = flag_value(argv, "--from")
    dst = flag_value(argv, "--to")
    if not src or not dst:
        sys.exit(__doc__)
    skip = {src, dst, "--from", "--to"}
    targets = parse_targets([a for a in argv[1:] if a not in skip])
    if not targets:
        sys.exit("옮길 <옛id>[=<새id>] 를 하나 이상 줄 것")
    apply_it = "--apply" in argv

    with io.open(src, encoding="utf-8") as fh:
        src_lines = fh.readlines()
    with io.open(dst, encoding="utf-8") as fh:
        dst_lines = fh.readlines()

    sd, sc = problems_span(src_lines, src)
    if len(targets) >= len(block_starts(src_lines, sd, sc)):
        sys.exit("%s 의 문항을 전부 옮기려 한다 — 빈 시험지가 된다"
                 % os.path.basename(src))

    # ⑴ 옮길 블록을 먼저 다 뜬다(줄 번호가 안 밀린 상태에서)
    spans, blocks = [], []
    for old, new in targets:
        s, e = problem_span(src_lines, sd, sc, old, src)
        spans.append((s, e))
        block = normalize_tail(src_lines[s:e + 1])
        if new != old:
            block = rename_in(block, old, new)
        blocks.append(block)
        print("  %-12s → %-12s (%d줄)%s"
              % (old, new, e - s + 1, "" if new != old else "  [id 그대로]"))

    # ⑵ 원본에서 뒤에서부터 지운다
    for s, e in sorted(spans, reverse=True):
        del src_lines[s:e + 1]
    sd, sc = problems_span(src_lines, src)
    last = block_starts(src_lines, sd, sc)
    if not last:
        sys.exit("원본에 문항이 하나도 안 남는다")
    if src_lines[sc - 1].rstrip("\n") == "    },":
        src_lines[sc - 1] = "    }\n"

    # ⑶ 대상의 problems 끝에 붙인다
    dd, dc = problems_span(dst_lines, dst)
    if dst_lines[dc - 1].rstrip("\n") == "    }":
        dst_lines[dc - 1] = "    },\n"
    tail = []
    for n, block in enumerate(blocks):
        tail.extend(block)
        if n != len(blocks) - 1:
            tail[-1] = "    },\n"
    dst_lines[dc:dc] = tail

    if not apply_it:
        print("[미적용] %s → %s — 문항 %d개. 실제로 옮기려면 --apply"
              % (os.path.basename(src), os.path.basename(dst), len(targets)))
        return 0

    with io.open(src, "w", encoding="utf-8", newline="") as fh:
        fh.writelines(src_lines)
    with io.open(dst, "w", encoding="utf-8", newline="") as fh:
        fh.writelines(dst_lines)

    with io.open(src, encoding="utf-8") as fh:
        src_ch = json.load(fh)
    with io.open(dst, encoding="utf-8") as fh:
        dst_ch = json.load(fh)
    left = {q.get("id") for q in (src_ch.get("problems") or [])}
    came = {q.get("id") for q in (dst_ch.get("problems") or [])}
    for old, new in targets:
        if old in left:
            sys.exit("옮겼다고 했는데 원본에 남아 있다: %s" % old)
        if new not in came:
            sys.exit("옮겼다고 했는데 대상에 없다: %s" % new)
    print("[적용] %s(%d문항) → %s(%d문항) · JSON 유효"
          % (os.path.basename(src), len(src_ch.get("problems") or []),
             os.path.basename(dst), len(dst_ch.get("problems") or [])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
