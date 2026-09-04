# -*- coding: utf-8 -*-
"""**근거 없는 「확정」 도장을 막는다** — 공용 「규칙/증거의-정직.md」 ⑶ 의 자.

    python 도구/audit_stamps.py            # 판정 (넘으면 exit 1)
    python 도구/audit_stamps.py --selftest # 자를 먼저 잰다 (양성·음성 대조군)
    python 도구/audit_stamps.py --quiet    # 걸린 게 없으면 침묵

왜 또 만드나 (2026-08-25, 같은 날 두 번째 판)
---------------------------------------------
첫 판은 **`exit 0` 이었다.** 실행 규율 17 이 글자 그대로 금지한 것이다 —
*"항상 exit 0 인 진단자만 있으면 숫자가 나와도 아무 일도 안 일어난다 →
「이 수가 얼마를 넘으면 마감이 막히나」를 같이 정한다."*
규칙을 쓴 손으로 그 규칙을 어겼고, 그래서 이 자는 하루도 못 가 이미 뚫려 있었다.

계기는 XSanity 아케이드 존 지도다 — **관측 6칸으로 62칸 전부에 「확정」을 찍었다.**
사용자가 검수에서 찾았고, 그게 곧 *"잘 된 걸 확인하는 게 아니라 잘 안 된 걸 확인하고 있다"* 다.

판정선 — **뺄셈 하나**
----------------------
「확정」을 내는 행은 그것을 만든 **관측을 같은 행에서** 가리켜야 한다.
못 가리키면 그 행은 **「예측」이지 확정이 아니다.**

    막는 선: 근거 없는 확정 **1칸이라도 있으면 exit 1.**

★ 0 을 선으로 두는 이유는 엄해서가 아니라 **중간값이 뜻이 없어서**다. 「확정 90%」 같은
  것은 없다 — 한 칸이 근거 없이 확정이면 **읽는 사람은 그 칸을 다시 안 본다.**

무엇을 안 재나 — **적어 두는 것이 이 자의 절반이다**
--------------------------------------------------
- **옳은가는 안 본다.** 근거가 붙어 있어도 그 근거가 틀릴 수 있다. 이 자가 보증하는 것은
  «근거를 가리키고 있나» 하나다(그 이상을 적으면 과잉 주장이다).
- **근거의 「분포」는 세되 막지 않는다.** 한 값이 N행을 덮으면 그 N행은 **한 번 관측한 것**이다
  (실측: XSanity `arcade_zone_final_merged` 632행 중 한 관측창이 81행을 덮었다).
  그런데 정당한 경우가 있다 — 한 화면에 여러 곡이 같이 보이면 같은 시각이 붙는다.
  **얼마를 넘으면 막을지 정할 수 없으므로 막지 않고 찍기만 한다**(규율 17 의 뒷문장:
  *"정할 수 없으면 아직 판정에 못 쓴다는 뜻이고 그 사실을 적어 둔다"*). 사람이 본다.
- ★★ **근거 칸이 아예 없는 파일은 이 자가 못 본다.** 실측(XSanity 뉴튠즈):
  정본 `arcade_dedicated_order.csv` 는 칸이 `존이름,종류,번호,곡` 뿐이라
  **「확인함」과 「안 함」이 구조상 같은 모양**이다. 그래서 선언에 적힌 파일에 근거 칸이
  없으면 **그 자체를 실패로 낸다** — 조용히 건너뛰면 그게 곧 「자가 못 본 0건」이다.

선언은 자료가 갖는다 — 코드에 파일 이름을 안 적는다
-----------------------------------------------------
프로젝트마다 칸 이름이 다르므로 **`기록/도장-감사.txt` 가 정본**이다(`게이트-목록.txt` ·
`월간-점검.txt` 와 같은 배치). 한 줄에 하나:

    <경로> | <도장칸> | <확정으로 치는 값들, 쉼표> | <근거칸들, 쉼표>

    out/arcade_zone_final_merged.csv | 확정도 | 정확,시각확정 | VOD시각,판독

- `#` 은 주석. **사유 없는 줄은 선언으로 안 친다.**

★★ 「선언이 없다」와 「대상이 없다」를 가른다 (고친 날 2026-08-26)
---------------------------------------------------------------
옛 조항은 *"선언 파일이 없으면 「해당 없음」으로 exit 0"* 이었고, 그 결과 이 리포에서
**이 자는 한 번도 잰 적 없이 초록**이었다 — `close_report` 는 그 exit 0 을 그대로
「근거 없는 확정 0칸」으로 찍었다. `check_floor` 가 그것을 신고했다(2026-08-26):
*"선언 파일이 없다: 도장-감사.txt — 그 자는 «해당 없음»으로 **조용히 초록**이 된다"*.

사용자 판정(2026-08-25, 나루 `기록/도장-감사.txt` 머리에 인용돼 있다):
*"「볼 것이 없어서 초록」을 빨강으로 본다"* · *"그렇게 해줘"*.

    선언 파일이 **없으면 exit 1**(미완이다 — 「대상 없음」과 구별이 안 된다).
    대상이 없으면 **그렇다고 적어서** 닫는다:  `없음 | <왜 이 리포엔 도장 칸이 없나>`

- **사유 없는 「없음」은 판정으로 안 친다** — 이 리포의 다른 대장과 같은 규율이다.
- 「없음」 줄은 **4칸 선언 셈에 안 섞인다**(`parse_decl` 이 형식으로 이미 거른다).
- ☐ 못 보는 것: 「없음」이 **옳은지**는 이 자가 모른다. 표를 새로 만들고도 그 줄을
  안 고치면 그 표는 영영 안 재진다. **표를 만드는 자리에서 선언을 같이 고친다.**
"""
import argparse
import csv
import io
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECL_NAME = "도장-감사.txt"


def decl_path(root):
    for folder in ("기록", "docs", "_log"):
        p = os.path.join(root, folder, DECL_NAME)
        if os.path.isfile(p):
            return p
    return None


NONE_MARK = "없음"


def none_reason(text):
    """`없음 | <사유>` 줄의 사유. 없으면 `None`. 순수 함수 — 테스트 대상.

    사유가 비면 판정으로 안 친다 — 「대상 없음」은 **판단**이므로 근거가 붙어야 한다.
    """
    for ln in text.splitlines():
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) == 2 and parts[0] == NONE_MARK and parts[1]:
            return parts[1]
    return None


def parse_decl(text):
    """`(경로, 도장칸, 확정값들, 근거칸들)` 목록. 순수 함수 — 테스트 대상."""
    out = []
    for ln in text.splitlines():
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) != 4 or not all(parts):
            continue                      # 형식이 깨진 줄은 선언으로 안 친다
        path, stamp, vals, evid = parts
        out.append((path, stamp,
                    [v.strip() for v in vals.split(",") if v.strip()],
                    [e.strip() for e in evid.split(",") if e.strip()]))
    return out


def read_rows(path):
    with io.open(path, encoding="utf-8-sig", errors="replace", newline="") as fh:
        lines = [l for l in fh if not l.lstrip().startswith("#") and l.strip()]
    if not lines:
        return [], []
    r = csv.DictReader(io.StringIO("".join(lines)))
    return (r.fieldnames or []), list(r)


def audit_one(cols, rows, stamp, vals, evid):
    """`(확정수, 근거없음, 최다반복, 서로다른값, 없는칸)`. 순수 함수 — 테스트 대상."""
    missing = [c for c in ([stamp] + evid) if c not in cols]
    if missing:
        return 0, 0, 0, 0, missing
    conf = [r for r in rows if str(r.get(stamp) or "").strip() in vals]
    unbacked = [r for r in conf
                if not any(str(r.get(c) or "").strip() for c in evid)]
    seen = Counter()
    for r in conf:
        key = " | ".join(str(r.get(c) or "").strip() for c in evid)
        if key.strip(" |"):
            seen[key] += 1
    top = seen.most_common(1)[0][1] if seen else 0
    return len(conf), len(unbacked), top, len(seen), []


def card_verdict_files(root):
    """발견 기반 `data/*/card-overlap-verdicts.json` 목록. 과목 이름을 알지 않는다."""
    data = os.path.join(root, "data")
    if not os.path.isdir(data):
        return []
    out = []
    for subject in sorted(os.scandir(data), key=lambda e: e.name):
        path = os.path.join(subject.path, "card-overlap-verdicts.json")
        if subject.is_dir() and os.path.isfile(path):
            out.append(path)
    return out


def audit_card_verdicts(root):
    """`(파일들, 판정수, 빈 근거 목록, 읽기 오류)`.

    판정값은 과거 문자열 형식과 현재 `{by,date,basis}` 형식을 함께 받되, 근거는 문자열
    자체 또는 `basis`가 비어 있지 않아야 한다. 근거 내용의 옳고 그름은 사람이 본다.
    """
    files = card_verdict_files(root)
    total, empty, errors = 0, [], []
    for path in files:
        try:
            with io.open(path, encoding="utf-8", errors="strict") as fh:
                data = json.load(fh)
            verdicts = data.get("verdicts") if isinstance(data, dict) else None
            if not isinstance(verdicts, dict):
                errors.append((path, "`verdicts` 객체가 없다"))
                continue
            total += len(verdicts)
            for key, value in verdicts.items():
                basis = value.get("basis") if isinstance(value, dict) else value
                if not str(basis or "").strip():
                    empty.append((path, str(key)))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append((path, type(exc).__name__))
    return files, total, empty, errors


# ── 자기 검정 — **이 자의 첫 두 판이 틀렸다. 그래서 이게 붙는다** ────────────────
SELFTEST = [
    # (설명, 칸, 행, 도장칸, 확정값, 근거칸, 근거없음이 몇이어야 하나)
    ("양성 — 근거 없이 확정 3칸",
     ["확정도", "VOD시각"],
     [{"확정도": "정확", "VOD시각": ""}, {"확정도": "정확", "VOD시각": ""},
      {"확정도": "정확", "VOD시각": ""}, {"확정도": "정확", "VOD시각": "12:30"}],
     "확정도", ["정확"], ["VOD시각"], 3),
    ("음성 — 전부 근거 있음",
     ["확정도", "VOD시각"],
     [{"확정도": "정확", "VOD시각": "1:00"}, {"확정도": "정확", "VOD시각": "2:00"}],
     "확정도", ["정확"], ["VOD시각"], 0),
    ("음성 — 확정이 아닌 행은 안 센다",
     ["확정도", "VOD시각"],
     [{"확정도": "예측", "VOD시각": ""}, {"확정도": "미확인", "VOD시각": ""}],
     "확정도", ["정확"], ["VOD시각"], 0),
    ("★ 도장 값이 안 맞으면 0이 나온다 — 첫 판이 여기서 틀렸다",
     ["확정도", "VOD시각"],
     [{"확정도": "정확", "VOD시각": ""}],
     "확정도", ["확정"], ["VOD시각"], 0),          # 「확정」으로 찾으면 「정확」을 못 본다
]


def selftest():
    bad = 0
    print("[자기 검정] 이 자가 무엇을 보고 무엇을 못 보나")
    for desc, cols, rows, stamp, vals, evid, want in SELFTEST:
        _, unbacked, _, _, missing = audit_one(cols, rows, stamp, vals, evid)
        ok = (not missing) and unbacked == want
        bad += 0 if ok else 1
        print("  %s %-46s 근거없음 %d (기대 %d)"
              % ("OK  " if ok else "**틀림**", desc, unbacked, want))

    _, _, _, _, missing = audit_one(["곡"], [{"곡": "x"}], "확정도", ["정확"], ["VOD시각"])
    ok = bool(missing)
    bad += 0 if ok else 1
    print("  %s %-46s 없는칸 %s"
          % ("OK  " if ok else "**틀림**", "★ 근거 칸이 없는 파일은 실패로 낸다", missing))

    # ★★ 「대상 없음」 판정을 읽는 자에 **대조군**. 이 자가 한 번도 잰 적 없이 초록이던
    #   자리를 닫는 조항이라, 양성만 두면 «사유 없는 없음» 도 통과해 그 구멍이 그대로 남는다.
    nl = "\n"
    for desc, decl, want in [
        ("★ 양성 — `없음 | 사유` 를 판정으로 읽는다",
         "없음 | 도장 칸을 가진 표가 이 리포엔 없다", "도장 칸을 가진 표가 이 리포엔 없다"),
        ("★ 음성 — **사유 없는 「없음」은 판정이 아니다**", "없음 |", None),
        ("음성 — 낱말 `없음` 하나만 있는 줄도 아니다", "없음", None),
        ("음성 — 주석 뒤의 것은 안 읽는다", "# 없음 | 나중에 쓴다", None),
        ("선언 줄과 섞여 있어도 읽는다",
         "a.csv | 판정 | 예 | 사유" + nl + "없음 | 그래도 적어 둔다", "그래도 적어 둔다"),
    ]:
        got = none_reason(decl)
        ok = got == want
        bad += 0 if ok else 1
        print("  %s %-46s %r" % ("OK  " if ok else "**틀림**", desc, got))
    ok = len(parse_decl("a.csv | 판정 | 예 | 사유" + nl + "없음 | x")) == 1
    bad += 0 if ok else 1
    print("  %s %-46s" % ("OK  " if ok else "**틀림**", "「없음」 줄이 4칸 선언 셈에 안 섞인다"))

    print("\n  ※ 넷째 줄이 이 자의 사각지대다 — **도장 값을 잘못 선언하면 「0칸」이 나온다.**")
    print("     그 0 은 «없다» 가 아니라 «자가 못 봤다» 이므로, 선언을 고칠 때 이 줄을 본다.")
    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=ROOT)
    ap.add_argument("--quiet", action="store_true", help="걸린 게 없으면 침묵")
    ap.add_argument("--selftest", action="store_true", help="대조군으로 자를 먼저 잰다")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    root = os.path.abspath(a.root)
    dp = decl_path(root)
    if not dp:
        # ★ **선언이 없는 것은 「대상 없음」이 아니라 미완이다** (2026-08-26).
        #   옛 판은 여기서 exit 0 을 냈고, 그래서 이 자는 한 번도 잰 적 없이 초록이었다.
        print("[도장 감사] **선언이 없다 — 미완이다** (「대상 없음」과 구별이 안 된다)",
              file=sys.stderr)
        print("  `docs/%s` 에 한 줄씩:" % DECL_NAME, file=sys.stderr)
        print("    <경로> | <도장칸> | <확정으로 치는 값들> | <근거칸들>", file=sys.stderr)
        print("  대상이 없으면 그렇다고 **사유와 함께** 적어 닫는다:", file=sys.stderr)
        print("    %s | <왜 이 리포에는 도장 칸을 가진 표가 없나>" % NONE_MARK, file=sys.stderr)
        return 1

    text = io.open(dp, encoding="utf-8", errors="replace").read()
    decls = parse_decl(text)
    why_none = none_reason(text)
    verdict_files, verdict_count, empty_verdicts, verdict_errors = audit_card_verdicts(root)
    print("[JSON 판정 대장] 발견 파일 %d개 · 판정 %d개 · 빈 근거 %d개"
          % (len(verdict_files), verdict_count, len(empty_verdicts)))
    for path, key in empty_verdicts[:12]:
        print("  **빈 근거** %s :: %s" % (os.path.relpath(path, root), key))
    for path, why in verdict_errors:
        print("  **읽기 실패** %s — %s" % (os.path.relpath(path, root), why), file=sys.stderr)
    json_fail = bool(empty_verdicts or verdict_errors)

    if not decls and why_none and not verdict_files:
        # ★ **이 한 줄은 `--quiet` 여도 찍는다** (2026-08-26). `--quiet` 는 «걸린 게 없으면
        #   침묵» 인데, 「대상 없음」은 걸린 게 없는 것이 아니라 **볼 것이 없다는 판정**이다.
        #   침묵하면 부르는 자(`close_report`)가 그 exit 0 을 「근거 없는 확정 0칸」으로 찍고,
        #   그러면 이 배치가 없앤 «본 적 없는데 초록» 이 보고 층에서 그대로 되살아난다.
        print("[도장 감사] **대상 없음으로 판정됨** — %s" % why_none)
        if not a.quiet:
            print("  선언: %s" % dp)
            print("  ※ 「없음」이 **옳은지**는 이 자가 모른다. 도장 칸을 가진 표를 새로 만들면"
                  " 그 자리에서 이 선언을 같이 고친다.")
        return 1 if json_fail else 0   # 판정이 적혀 있으므로 exit 0 — 「선언 없음」과 다르다
    if not decls and why_none and verdict_files:
        # CSV 대상 없음 선언과 별개로 발견된 JSON 판정 대장은 실제로 검사했다.
        if json_fail:
            print("FAIL — JSON 판정 대장에 빈 근거 또는 읽기 실패가 있다.", file=sys.stderr)
        return 1 if json_fail else 0
    if not decls:
        print("[도장 감사] 선언 파일은 있는데 **성립하는 줄이 0개다** — 형식을 본다: %s" % dp,
              file=sys.stderr)
        return 1                      # 빈 선언을 통과로 읽으면 그게 조용한 구멍이다

    rows_out, fail = [], int(json_fail)
    for path, stamp, vals, evid in decls:
        full = path if os.path.isabs(path) else os.path.join(root, path)
        if not os.path.isfile(full):
            rows_out.append((path, "**파일 없음**", 0, 0, 0, 0))
            fail += 1
            continue
        cols, rows = read_rows(full)
        conf, unbacked, top, distinct, missing = audit_one(cols, rows, stamp, vals, evid)
        if missing:
            rows_out.append((path, "**칸 없음: " + ",".join(missing) + "**", 0, 0, 0, 0))
            fail += 1
            continue
        rows_out.append((path, "", len(rows), conf, unbacked, top))
        fail += 1 if unbacked else 0

    if a.quiet and not fail:
        return 0
    print("[도장 감사] 근거 없는 「확정」 — 공용 `규칙/증거의-정직.md` ⑶")
    print("%-44s %6s %6s %9s %8s" % ("파일", "전체", "확정", "근거없음", "최다반복"))
    for path, note, total, conf, unbacked, top in rows_out:
        if note:
            print("%-44s %s" % (path[:44], note))
            continue
        mark = "  ← **막는다**" if unbacked else ""
        print("%-44s %6d %6d %9d %8d%s" % (path[:44], total, conf, unbacked, top, mark))
    print()
    print("  ※ **최다반복** 은 한 근거값이 덮는 행 수다 — 크면 «한 번 관측한 것»이라는 뜻이지만")
    print("     한 화면에 여러 개가 같이 보이는 정당한 경우가 있어 **막지 않고 찍기만 한다.**")
    if fail:
        print("\nFAIL — 근거 없는 확정이 있다. **그 행은 「예측」이지 확정이 아니다.**",
              file=sys.stderr)
        print("  표시를 바꾸거나, 관측을 붙이거나, 내보내지 않는다 — 셋 중 하나다.",
              file=sys.stderr)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
