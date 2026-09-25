# -*- coding: utf-8 -*-
r"""새 검사를 열 때 **아직 못 따라온 과목·챕터의 선언**을 한 번에 적는다 (신설 2026-09-10).

    python tools/declare_check_waiver.py --key=prompt_ramp --why="…" --except=<과목>,<과목>
    python tools/declare_check_waiver.py --key=prompt_ramp --pending=<과목> --chapters=ch08,ch09 --why="…"
    python tools/declare_check_waiver.py --key=formula_line_wide --pending-map="과목:ch01,ch02;과목2:ch05" --why="…"
    …위 셋 다 `--apply` 를 붙여야 실제로 쓴다(기본은 무엇이 바뀌는지만 본다).

★ **왜 열렸나.** AGENTS 「close 의 정의」가 *[발화 생략]* 로
  기본값을 뒤집었다. 옳은 기본값인데, 그 대가로 **검사를 하나 열 때마다 아직 못 따라온
  과목 전부의 `index.json` 에 사유를 적어야 한다**(2026-09-10 실측: 21과목 중 18). 손으로
  적으면 ⑴ 사유가 과목마다 달라지고 ⑵ 한둘을 빠뜨려 그 과목 빌드가 멈추고 ⑶ 「빠뜨렸다」와
  「일부러 안 적었다」가 구별되지 않는다.

★ **완화 도구가 아니다 — 선언 도구다.** 판정선 셋:
  ⑴ **사유(`--why`)가 없으면 아무것도 쓰지 않는다.** 사유 없는 면제는 면제가 아니다(AGENTS).
  ⑵ **이미 있는 선언을 덮지 않는다.** 남이 적어 둔 사유를 이 자가 갈아치우면 그 판정이 사라진다.
  ⑶ **지우지 않는다.** 면제를 걷는 것은 사람이 그 과목을 실제로 고칠 때 하는 일이다.

★ **`strictWaivers`(과목 통째)와 `pendingChapters`(그 과목의 일부 챕터)는 다른 뜻이다.**
  전자는 «이 과목은 이 검사를 안 켠다», 후자는 «켜는 중인데 이 챕터는 아직». `close_report`
  가 둘을 갈라 세므로, 곧 채울 것을 `strictWaivers` 에 적으면 그 빚이 안 보이게 된다.
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from audit_content import subject_dirs                                    # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ★★ **파일을 통째로 다시 직렬화하지 않는다 — 첫 판이 그렇게 만들었다가 되돌렸다** (2026-09-10).
#   `json.dump(indent=2)` 로 다시 쓰면 **손으로 한 줄에 적어 둔 배열이 전부 펴진다** —
#   실측: 한 과목에서 한 줄을 넣으려다 **354줄이 바뀌었다**(`"chapters": ["ch00.json"]` 같은
#   압축 표기가 8줄로). 요청한 것은 선언 한 줄인데 diff 가 통째로 바뀌면 ⑴ 리뷰가 불가능하고
#   ⑵ 변경점 판정이 그 과목을 「고쳤다」로 읽는다(AGENTS 「변경점 기준선」).
#   → **텍스트로 끼워 넣는다.** 나머지 바이트는 손대지 않고, 쓴 뒤 `json.loads` 로 되읽어
#     깨지지 않았는지 확인한다(못 읽으면 원문을 그대로 되돌린다).
_EMPTY = re.compile(r'("(?P<k>[A-Za-z_]+)":\s*)\{\s*\}')


def _insert_into_object(text, top_key, line):
    """`"top_key": {` 바로 뒤에 `line` 을 끼운다. 그 키가 없으면 객체째로 만들어 맨 끝에 붙인다.

    ★★ **빈 객체 `{}` 를 따로 다룬다 — 첫 판이 여기서 조용히 틀렸다** (2026-09-10).
      `"strictWaivers": {},` 한 줄짜리에 `"…": {` 로 붙는 앵커가 맞아떨어져, 새 줄이 그 **닫힌
      객체 바깥**(= 최상위)에 앉았다. 결과는 **문법적으로 멀쩡한 JSON** 이라 아래 `json.loads`
      가 통과시켰고, 그래서 다섯 과목이 면제를 선언한 줄 알았는데 빌드가 그대로 걸렸다.
      → 빈 객체는 **펴서** 넣는다. 그리고 문법이 아니라 **자리**를 확인한다(`save_text`).
    """
    m = None
    for hit in _EMPTY.finditer(text):
        if hit.group("k") == top_key:
            m = hit
            break
    if m:
        return (text[:m.start()] + m.group(1) + "{\n" + line.rstrip(",") + "\n  }"
                + text[m.end():])
    anchor = '"' + top_key + '": {'
    at = text.find(anchor)
    if at >= 0:
        eol = text.index("\n", at) + 1
        return text[:eol] + line + "\n" + text[eol:]
    close = text.rstrip().rfind("}")
    head = text[:close].rstrip()
    if head.endswith(","):
        head = head[:-1]
    return head + ",\n  \"" + top_key + "\": {\n" + line.rstrip(",") + "\n  }\n}\n"


def save_text(path, text, where, key):
    """쓰기 전에 **자리**를 확인한다 — 문법만 보면 「멀쩡한데 틀린 자리」를 못 잡는다.

    ★ 이 두 줄이 위 사고의 close 다(AGENTS 「close 의 정의」). `json.loads` 는 «깨졌나»만
      보고 «내가 넣으려던 곳에 들어갔나»는 안 본다 — 그 둘은 다른 질문이다.
    """
    data = json.loads(text)               # ⑴ 깨진 JSON 을 쓰지 않는다
    if key not in (data.get(where) or {}):  # ⑵ 넣으려던 자리에 실제로 들어갔나
        raise SystemExit("[안 씀] %s — %s 안에 %r 이 안 들어갔다. 이 파일의 모양을 사람이 볼 것"
                         % (path, where, key))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _chapter_files(spec):
    return [c.strip() if c.strip().endswith(".json") else c.strip() + ".json"
            for c in (spec or "").split(",") if c.strip()]


def pending_map(args):
    """{과목: [chNN.json…]} — `--pending`+`--chapters`(한 과목) 와 `--pending-map`(여러 과목) 을 한 표로.

    ★ `--pending-map` 은 2026-09-25 에 열렸다: 새 검사 하나(C75)가 17과목에 걸렸는데 한 과목씩 `--apply` 하면
      `bulk_apply_guard` 가 요구하는 「빈 트리」를 17번 만들어야 했다(병렬 세션 중엔 창이 거의 안 열린다).
      형식 `과목:ch01,ch02;과목2:ch05` — 과목 안 구분은 쉼표, 과목 사이는 세미콜론.
    """
    out = {}
    if args.pending:
        for s in args.pending.split(","):
            if s.strip():
                out[s.strip()] = _chapter_files(args.chapters)
    for entry in (getattr(args, "pending_map", "") or "").split(";"):
        if ":" not in entry:
            continue
        subject, chapters = entry.split(":", 1)
        if subject.strip():
            out.setdefault(subject.strip(), [])
            out[subject.strip()] += [c for c in _chapter_files(chapters) if c not in out[subject.strip()]]
    return out


def plan(args):
    """[(과목, 경로, 자리, 값, 사유)] — 순수에 가깝게. 무엇이 바뀌는지 먼저 낸다."""
    skip = {s.strip() for s in (args.exclude or "").split(",") if s.strip()}
    want = pending_map(args)
    rows = []
    for folder in subject_dirs(os.path.join(ROOT, "data")):
        subject = os.path.basename(folder)
        path = os.path.join(folder, "index.json")
        if not os.path.isfile(path):
            continue
        idx = load(path)
        if want:
            if subject not in want:
                continue
            have = (idx.get("pendingChapters") or {}).get(args.key) or []
            add = [c for c in want[subject] if c not in have]
            if add:
                rows.append((subject, path, "pendingChapters", add, args.why))
            continue
        if subject in skip:
            continue
        if args.key in (idx.get("strictWaivers") or {}):
            continue                       # ⑵ 이미 있는 선언은 덮지 않는다
        rows.append((subject, path, "strictWaivers", args.why, args.why))
    return rows


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--key", required=True, help="검사 키 (is_strict_chapter 의 list_name)")
    ap.add_argument("--why", required=True, help="사유 — 없으면 아무것도 쓰지 않는다")
    ap.add_argument("--except", dest="exclude", default="",
                    help="이 과목들은 건드리지 않는다(= 검사를 켤 과목)")
    ap.add_argument("--pending", default="", help="이 과목의 pendingChapters 에 적는다")
    ap.add_argument("--chapters", default="", help="--pending 과 함께 — chNN,chNN")
    ap.add_argument("--pending-map", dest="pending_map", default="",
                    help="여러 과목을 한 번에 — `과목:ch01,ch02;과목2:ch05`(pending_map 독스트링)")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not args.why.strip():
        sys.exit("--why 가 비었다 — 사유 없는 면제는 면제가 아니다")
    if args.pending and not args.chapters:
        sys.exit("--pending 에는 --chapters 가 필요하다")
    if args.pending_map and not pending_map(args):
        sys.exit("--pending-map 형식이 틀렸다 — `과목:ch01,ch02;과목2:ch05`")

    rows = plan(args)
    if not rows:
        print("[해당 없음] 새로 적을 선언이 없다 — 0건")
        return 0
    for subject, _, where, value, _ in rows:
        print("  " + subject + " · " + where + "." + args.key + " ← "
              + (", ".join(value) if isinstance(value, list) else "사유 한 줄"))
    if not args.apply:
        print("\n" + str(len(rows)) + "건 — 실제로 쓰려면 `--apply`")
        return 0
    for _, path, where, value, why in rows:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if where == "pendingChapters":
            have = (load(path).get("pendingChapters") or {}).get(args.key) or []
            merged = sorted(set(have) | set(value))
            line = ('    "%s": [%s],'
                    % (args.key, ", ".join(json.dumps(c, ensure_ascii=False) for c in merged)))
            if have:                       # 이미 있던 줄은 지우고 합친 줄로 갈아 끼운다
                text = "\n".join(l for l in text.split("\n")
                                 if not l.strip().startswith('"%s": [' % args.key))
        else:
            line = "    %s: %s," % (json.dumps(args.key, ensure_ascii=False),
                                    json.dumps(why, ensure_ascii=False))
        save_text(path, _insert_into_object(text, where, line), where, args.key)
    print("\n" + str(len(rows)) + "건 적었다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
