# -*- coding: utf-8 -*-
"""**이 자료만 보고 다음 과목이 열리는가** — 사슬이 끊긴 자리를 센다.

    python tools/audit_chain_selfsufficiency.py                # 전 과목
    python tools/audit_chain_selfsufficiency.py --only=<과목>  # 한 과목만
    python tools/audit_chain_selfsufficiency.py --fail-only    # 게이트에 걸리는 것만

★ **열린 날 2026-09-08 — 사용자가 이 자료의 목적을 못 박았다.** 정본은
  `docs/2026-09-08-기어가-맞물리게.md` 이고, 그 판정의 한 줄은 이렇다:

    "고체역학 내 html 개념과 문제를 풀 줄 알면 그다음 응용고체역학 html 도 개념 읽어보고
     유도 이해하면 문풀, 연습문제 이해되게. 그래서 **서로 기어가 맞물리게** 갔음 좋겠어."

  그때까지 완성도를 재던 자는 둘이었다 — 「교재의 어느 쪽을 안 읽었나」와 「교재를 베끼지
  않았나」. 둘 다 통과해도 **사슬은 끊겨 있을 수 있다.** 이 자가 그 셋째 축이다.

## 세 가지를 센다

⑴ **과목 간 다리** — 앞 학기 과목이 있는데 과목 간 링크(`[[과목폴더@chNN:앵커id|문구]]`)가
   한 건도 없는 과목. 학기는 `index.json` 의 `semester` 로 판정하므로 과목 이름을 안 박는다.
   `SUBJECT.md` 에서 「선수」가 든 줄을 함께 찍는다 — 사람이 볼 근거이고 이 자는 그 줄을
   해석하지 않는다(선언 형식이 과목마다 달라 해석하면 틀린다).

⑵ **없는 식을 가리키는 문항** — `problems[].relatedFormulas` 가 그 장에도, 같은 과목의
   **앞선 장**에도 없는 id 를 가리키는 경우. 독자가 이 자료 안에서 한 번도 만난 적 없는
   식을 쓰라는 뜻이라 사슬이 끊긴 것이 확실하다. **이것만 게이트다**(exit 1).

⑶ **아무도 안 쓰는 식** — 유도 카드는 있는데 그 장의 어떤 문항도 `relatedFormulas` 로
   가리키지 않는 경우. 개념만 있고 꺼내 쓰는 자리가 없다는 뜻이고, 그러면 다음 과목에서
   「읽었지만 못 쓴다」가 된다.

## ☐ 이 자가 못 보는 것 (첫 실행 전에 적는다 — 규칙 21)

- **되짚기 문단은 못 센다.** 링크 없이 산문으로만 되짚은 절을 「0건」으로 신고한다.
  ⑴ 의 0 은 「다리가 없다」가 아니라 **「기계가 볼 수 있는 다리가 없다」**이다.
- **끊긴 개념은 못 센다.** 문항이 쓰는 개념 가운데 이 자료에 없는 것을 찾으려면 글을 읽어야
  한다. ⑵ 는 그 가운데 **id 로 표시된 것**만 본다.
- **⑶ 의 0 이 좋은 것도 아니다.** 문항이 `relatedFormulas` 를 아예 안 적는 과목에서는 모든
  식이 「안 쓰이는 식」으로 나온다 — 그건 사슬이 아니라 **표기 습관**의 문제다. 그래서 ⑶ 은
  그 장에 `relatedFormulas` 를 쓰는 문항이 하나라도 있을 때만 센다.
- 학기가 같은 과목 사이는 순서가 없다(공통 규칙) — ⑴ 은 **앞 학기**만 본다.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import audit_content  # noqa: E402

# `[[과목폴더@chNN:앵커id|문구]]` — `@` 앞이 있는 것만 과목 간 링크다.
CROSS_LINK_RE = re.compile(r"\[\[([^\[\]@|]+)@(ch\d+):")
SEMESTER_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")


def semester_key(text):
    """'2-2' → (2, 2). 못 읽으면 None — 못 읽은 것을 0 으로 두면 가장 이른 학기가 된다."""
    m = SEMESTER_RE.match(text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def cross_links(text):
    """산문에서 과목 간 링크의 (과목폴더, chNN) 목록. 순수 함수 — 테스트가 직접 부른다."""
    return CROSS_LINK_RE.findall(text or "")


def formula_ids(data):
    """그 장의 유도 카드 id 집합."""
    cards = ((data.get("derivation") or {}).get("formulas")) or []
    return {c.get("id") for c in cards if isinstance(c, dict) and c.get("id")}


def problem_refs(data):
    """(문항 id, 그 문항이 가리키는 식 id) 쌍. `practice` 와 `problems` 둘 다 본다."""
    out = []
    for key in ("practice", "problems"):
        for item in (data.get(key) or []):
            if not isinstance(item, dict):
                continue
            for fid in (item.get("relatedFormulas") or []):
                out.append((item.get("id"), fid))
    return out


def dangling(refs, known):
    """가리키는데 없는 식 id. 순수 함수."""
    return [(qid, fid) for qid, fid in refs if fid not in known]


def unused(known, refs):
    """있는데 아무 문항도 안 가리키는 식 id. 순수 함수."""
    used = {fid for _qid, fid in refs}
    return sorted(fid for fid in known if fid not in used)


def read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def read_index(subject_dir):
    try:
        with open(os.path.join(subject_dir, "index.json"), encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (OSError, ValueError):
        return {}


def subject_semester(subject_dir):
    return semester_key(read_index(subject_dir).get("semester"))


def current_semester(data_root):
    """지금 듣는 학기 — `data/학기.json` 의 `current` 가 정본이다.

    ★ 왜 데이터가 갖나 (2026-09-09): 사용자가 세 번에 걸쳐 «2-2 과목을 먼저 처리해» 라고
    지적했는데, 이 자가 학기를 안 찍어서 목록을 위에서부터 집으면 **가나다순으로 2-1 과목이
    먼저 걸렸다**(실사고: 남은 18건 중 2-2 는 둘뿐인데 열역학 2-1 부터 손댔다). 순서를 사람의
    기억에 맡긴 것이 원인이라 파일로 옮겼다. 도구 소스에 학기를 박지 않는 이유는 AGENTS 의
    「공통 도구에 과목별 사실을 박지 않는다」와 같다 — 학기는 해마다 바뀐다.

    선언이 없으면 None 을 돌려주고, 그때 이 자는 **정렬하지 않는다**(조용히 다른 순서를
    만들지 않는다). 순수 함수는 아니지만 인자로 뿌리를 받아 테스트가 임시 폴더로 부를 수 있다.
    """
    try:
        with open(os.path.join(data_root, "학기.json"), encoding="utf-8") as fh:
            return semester_key((json.load(fh) or {}).get("current"))
    except (OSError, ValueError):
        return None


def semester_order(items, sem, now):
    """(과목, …) 튜플들을 **지금 학기 먼저**로 정렬한다. 순수 함수.

    `now` 가 None 이면 원래 순서를 그대로 돌려준다. 같은 무리 안에서는 들어온 순서를
    지킨다(안정 정렬) — 자가 낸 장 순서가 뒤집히면 사람이 대조를 못 한다.
    """
    if not now:
        return list(items)
    return sorted(items, key=lambda row: 0 if sem.get(row[0]) == now else 1)


def semester_tag(sem, subject):
    """목록 줄에 붙일 학기 표시. 선언이 없으면 빈 문자열."""
    got = sem.get(subject)
    return "%d-%d" % got if got else "?"


def bridge_waiver(index):
    """`chainBridgeWaiver` — **걸 다리가 없다**고 선언한 사유. 빈 문자열은 선언이 아니다.

    ★ 왜 데이터가 갖나 (2026-09-08): 이 자의 첫 실행이 낸 열둘 가운데 넷은 **선수과목이
      이 리포에 아예 없는** 과목이었다(선언상 선수 없음 · 물리학 · 교양). 그런 과목을
      목록에 계속 두면 경보 피로로 이 자가 죽는다. 사유를 적어야만 내려가고, 사유는
      그 과목 `index.json` 에 남아 다음 세션이 근거를 본다.
    """
    why = index.get("chainBridgeWaiver")
    return why.strip() if isinstance(why, str) and why.strip() else None


def prerequisite_lines(subject_dir):
    """`SUBJECT.md` 에서 「선수」가 든 줄. **해석하지 않고 그대로 보여 준다.**"""
    lines = read_text(os.path.join(subject_dir, "SUBJECT.md")).splitlines()
    return [l.strip() for l in lines if "선수" in l][:2]


def main(argv):
    only = None
    fail_only = "--fail-only" in argv
    for a in argv:
        if a.startswith("--only="):
            only = a.split("=", 1)[1]

    dirs = audit_content.subject_dirs()
    if audit_content.reject_unmatched_only(only, dirs):
        return 2
    sem = {os.path.basename(d): subject_semester(d) for d in dirs}
    earliest = min((s for s in sem.values() if s), default=None)

    bridgeless, dangles, orphans, waived, seen = [], [], [], [], 0
    for d in dirs:
        subject = os.path.basename(d)
        if only and only not in subject:
            continue
        chapters = sorted(f for f in os.listdir(d) if re.fullmatch(r"ch\d+\.json", f))
        known_so_far, links = set(), 0
        for name in chapters:
            raw = read_text(os.path.join(d, name))
            links += len(cross_links(raw))
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            seen += 1
            here = formula_ids(data)
            refs = problem_refs(data)
            for qid, fid in dangling(refs, known_so_far | here):
                dangles.append((subject, name[:-5], qid, fid))
            if refs:                       # 이 장이 relatedFormulas 를 쓰는 장일 때만 센다
                for fid in unused(here, refs):
                    orphans.append((subject, name[:-5], fid))
            known_so_far |= here
        mine = sem.get(subject)
        if links == 0 and mine and earliest and mine > earliest:
            why = bridge_waiver(read_index(d))
            if why:
                waived.append((subject, why))
            else:
                bridgeless.append((subject, mine, prerequisite_lines(d)))

    if dangles:
        print("[끊김] 문항이 **이 자료에 없는 식**을 가리킨다 — 독자는 그 식을 만난 적이 없다")
        for subject, ch, qid, fid in dangles:
            print("   %s %s · %s → %s" % (subject, ch, qid, fid))
    if not fail_only:
        if bridgeless:
            print("\n[다리 없음] 앞 학기 과목이 있는데 **과목 간 링크가 0건**인 과목")
            print("   ※ 산문으로만 되짚은 것은 이 자가 못 본다 — 0 은 「기계가 볼 다리가 없다」다")
            for subject, mine, why in bridgeless:
                print("   %s (%d-%d)" % (subject, mine[0], mine[1]))
                for line in why:
                    print("       근거로 볼 줄: " + line)
        if waived:
            print("\n  ※ 걸 다리가 없다고 선언한 과목 %d개 — `index.json` 의 chainBridgeWaiver:"
                  % len(waived))
            for subject, why in waived:
                print("     %s — %s" % (subject, why))
        if orphans:
            now = current_semester(audit_content.DATA)
            ordered = semester_order(orphans, sem, now)
            print("\n[안 쓰이는 식] 유도 카드는 있는데 그 장의 어떤 문항도 안 가리킨다")
            if now:
                mine = sum(1 for row in ordered if sem.get(row[0]) == now)
                print("   ※ **지금 학기(%d-%d) 것을 위로 올렸다** — %d건이고, 그 아래는 지난·다음"
                      " 학기다(`data/학기.json`)" % (now[0], now[1], mine))
            for subject, ch, fid in ordered[:40]:
                print("   [%s] %s %s · %s" % (semester_tag(sem, subject), subject, ch, fid))
            if len(ordered) > 40:
                print("   … 그리고 %d건 더" % (len(ordered) - 40))

    print("\n합계 — 훑은 장 %d개 · 끊김 %d건 · 다리 없는 과목 %d개(면제 %d개) · 안 쓰이는 식 %d건"
          % (seen, len(dangles), len(bridgeless), len(waived), len(orphans)))
    print("※ 게이트는 「끊김」 하나다 — 나머지 둘은 후보이고 판정은 사람이 한다")
    return 1 if dangles else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
