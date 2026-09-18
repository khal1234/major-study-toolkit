# -*- coding: utf-8 -*-
"""시험 모드 문항에서 **채점 칸(step)** 을 걷어내고 남은 칸의 번호를 다시 매긴다.

열린 날 2026-08-26. 사용자 지적(화면 사진과 함께):

    *[발화 생략]*

★ **무엇이 새어나갔나.** 담당 교수의 배점 근거(*[발화 생략]*)를
  **문항 구조**로 옮긴 것이 잘못이었다. 시각·조건·식을 3지선다로 늘어놓으면 학생은 그 셋을
  **알아보기(recognition)** 로 고르는데, 시험이 재려는 것은 그 셋을 **스스로 세우는 능력**이다.
  즉 배점 규칙을 문항으로 번역하는 순간 **평가 대상이 사라진다.** 배점은 «채점할 때» 쓰는
  자이지 «물을 때» 쓰는 자가 아니다.

  → 판정 A(사용자 선택 2026-08-26): **화면은 답만 묻는다.** 시각·조건·식은 채점 의뢰문의
    배점 규칙으로만 남아 손풀이를 채팅 AI 가 그 기준으로 매긴다. O/X·정의·객관식은 그 자체가
    시험 유형이므로 **독립 문항으로 남긴다** — 이 도구는 그 판정을 **하지 않는다.**

★ **무엇을 지울지는 이 도구가 판정하지 않는다.** 같은 `choice` 라도 「어느 식을 쓰나」(떠먹임)와
  「틀린 줄을 찾으세요」(오류 찾기 문항)는 성격이 정반대다. 사람이 문항·칸 id 를 골라 인자로 준다.

왜 `json.load` → `json.dump` 가 아니라 줄 단위인가 — 다시 덤프하면 파일 전체가 재포맷돼
diff 가 통째로 바뀐다. 검수가 변경점 하이라이트로 도는 리포에서 그건 그 자체로 사고다
(`drop_card_diagrams.py` 가 같은 이유로 같은 형태다). 대신 쓴 뒤 `json.load` 로 유효성과
삭제 여부를 실제로 확인한다(규칙 11).

    python tools/drop_exam_steps.py data/<과목>/chNN.json \
           <문항id>:<칸id>[,<칸id>...] [<문항id>:<칸id>...] [--apply]

`--apply` 없이 돌리면 무엇이 지워지고 번호가 어떻게 다시 매겨지는지만 찍는다(기본값이 안전한 쪽).
번호는 남은 칸에 **1부터 순서대로** 다시 붙는다 — `"label": "N · …"` 꼴만 건드리고 나머지 라벨은
그대로 둔다(번호 규약을 안 쓰는 과목이 있을 수 있다).
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROBLEM_CLOSE = ("      },", "      }")
STEPS_OPEN = '"steps": ['
STEPS_CLOSE = ("        ],", "        ]")
STEP_OPEN = "          {"
STEP_CLOSE = ("          },", "          }")
LABEL_RE = re.compile(r'^(\s*"label": ")(\d+)( · )')


def problem_span(lines, problem_id):
    """문항 id 줄부터 그 문항을 닫는 줄까지 — 끝은 **들여쓰기**로 잡는다.

    「다음 문항 id 까지」로 잡으면 마지막 문항에서 파일 끝까지 번진다
    (`drop_card_diagrams.card_span` 이 그 자리에서 한 번 깨졌다).
    """
    starts = [i for i, l in enumerate(lines) if l.strip() == '"id": "%s",' % problem_id]
    if len(starts) != 1:
        sys.exit("문항 id '%s' 를 한 번에 못 찾았다 (%d건)" % (problem_id, len(starts)))
    s = starts[0]
    ends = [i for i in range(s + 1, len(lines)) if lines[i].rstrip("\n") in PROBLEM_CLOSE]
    if not ends:
        sys.exit("문항 '%s' 를 닫는 줄을 못 찾았다" % problem_id)
    return s, ends[0] + 1


def steps_span(lines, s, e, problem_id):
    opens = [i for i in range(s, e) if lines[i].strip().startswith(STEPS_OPEN)]
    if len(opens) != 1:
        sys.exit("'%s' 의 steps 블록이 하나가 아니다 (%d건)" % (problem_id, len(opens)))
    d = opens[0]
    closes = [i for i in range(d + 1, e) if lines[i].rstrip("\n") in STEPS_CLOSE]
    if not closes:
        sys.exit("'%s' 의 steps 를 닫는 줄을 못 찾았다" % problem_id)
    return d, closes[0]


def step_span(lines, d, end, problem_id, step_id):
    hits = [i for i in range(d + 1, end)
            if lines[i].strip() == '"id": "%s",' % step_id]
    if len(hits) != 1:
        sys.exit("'%s' 안에서 칸 id '%s' 를 한 번에 못 찾았다 (%d건)"
                 % (problem_id, step_id, len(hits)))
    i = hits[0]
    if lines[i - 1].rstrip("\n") != STEP_OPEN:
        sys.exit("'%s/%s' 의 여는 줄이 규격과 다르다 — 손으로 고칠 것" % (problem_id, step_id))
    closes = [j for j in range(i, end) if lines[j].rstrip("\n") in STEP_CLOSE]
    if not closes:
        sys.exit("'%s/%s' 를 닫는 줄을 못 찾았다" % (problem_id, step_id))
    return i - 1, closes[0]


def renumber(lines, d, end):
    """남은 칸의 `"label": "N · …"` 를 1부터 다시 매긴다. 그 꼴이 아니면 안 건드린다."""
    n, changed = 0, []
    for i in range(d + 1, end):
        m = LABEL_RE.match(lines[i])
        if not m:
            continue
        n += 1
        if m.group(2) != str(n):
            changed.append((m.group(2), str(n)))
            lines[i] = LABEL_RE.sub(lambda mm: mm.group(1) + str(n) + mm.group(3),
                                    lines[i], count=1)
    return changed


def strip_one(lines, problem_id, step_ids):
    s, e = problem_span(lines, problem_id)
    d, end = steps_span(lines, s, e, problem_id)
    # 뒤에서부터 지운다 — 앞에서 지우면 뒤 칸의 줄 번호가 밀린다
    spans = sorted((step_span(lines, d, end, problem_id, sid) for sid in step_ids),
                   reverse=True)
    dropped = 0
    for a, b in spans:
        was_last = lines[b].rstrip("\n") == "          }"
        del lines[a:b + 1]
        dropped += b - a + 1
        end -= b - a + 1
        # 마지막 원소였으면 새 마지막의 쉼표를 뗀다(안 떼면 JSON 이 깨진다)
        if was_last and lines[a - 1].rstrip("\n") == "          },":
            lines[a - 1] = "          }\n"
    left = sum(1 for i in range(d + 1, end) if lines[i].rstrip("\n") == STEP_OPEN)
    if not left:
        sys.exit("'%s' 의 칸을 전부 지우려 한다 — 채점할 것이 없는 문항이 된다" % problem_id)
    return dropped, left, renumber(lines, d, end)


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    path = argv[1]
    apply_it = "--apply" in argv[2:]
    targets = []
    for a in argv[2:]:
        if a == "--apply":
            continue
        if ":" not in a:
            sys.exit("형식은 <문항id>:<칸id>[,<칸id>...] 다 — 받은 것: %r" % a)
        pid, sids = a.split(":", 1)
        targets.append((pid, [x for x in sids.split(",") if x]))
    if not targets:
        sys.exit("걷어낼 <문항id>:<칸id> 를 하나 이상 줄 것")

    with io.open(path, encoding="utf-8") as fh:
        lines = fh.readlines()

    total = 0
    for pid, sids in targets:
        dropped, left, renumbered = strip_one(lines, pid, sids)
        total += len(sids)
        print("  %-12s 칸 %s 걷어냄 (%d줄) · 남은 칸 %d · 번호 고침 %s"
              % (pid, ", ".join(sids), dropped, left,
                 ", ".join(a + "→" + b for a, b in renumbered) or "없음"))

    if not apply_it:
        print("[미적용] %s — 문항 %d개 / 칸 %d개. 실제로 지우려면 --apply"
              % (os.path.basename(path), len(targets), total))
        return 0

    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.writelines(lines)
    with io.open(path, encoding="utf-8") as fh:
        ch = json.load(fh)
    by_id = {q.get("id"): q for q in (ch.get("problems") or [])}
    for pid, sids in targets:
        have = {st.get("id") for st in ((by_id.get(pid) or {}).get("exam") or {}).get("steps", [])}
        still = [x for x in sids if x in have]
        if still:
            sys.exit("지웠다고 했는데 남아 있다: %s/%s" % (pid, ", ".join(still)))
    print("[적용] %s — 문항 %d개 / 칸 %d개 걷어냄 · JSON 유효"
          % (os.path.basename(path), len(targets), total))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
