# -*- coding: utf-8 -*-
"""**사용자가 본 장**을 과목 `index.json` 의 `reviewSeen` 에 적는다 (열린 날 2026-09-18).

    python tools/set_review_seen.py --list
    python tools/set_review_seen.py --subject "<과목 폴더>" --add chNN --why "<날짜 · 근거>"
    python tools/set_review_seen.py --init <{과목: {chNN|"*": 근거}}.json>

변경점 표시는 `reviewSeen` 에 있는 장에만 뜬다 — 선언 밖 장은 빌드가 기준선을 HEAD 로 유지한다
(`build_site.review_unseen`). 사용자가 어떤 장을 화면에서 지적하면 그 자리에서 `--add` 한다.
`"*"` 는 「그 과목 전 장을 봤다」(끝난 학기 과목).

재는 것: 없음 — 옮겨 적기만 한다. 근거 문장은 사람이 쓴다.
줄 단위로 고친다(다시 덤프하면 파일 전체가 diff 가 된다) — `reviewSeen` 은 한 줄짜리 객체로 둔다.
"""
import argparse
import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEN_LINE = re.compile(r'^(\s*)"reviewSeen":\s*(\{.*\}),?\s*$')
SUBJECT_LINE = re.compile(r'^(\s*)"subject":\s*"[^"]*",\s*$')


def index_path(subject):
    return os.path.join(ROOT, "data", subject, "index.json")


APPLY = False


def write_seen(subject, seen):
    """`reviewSeen` 한 줄을 바꾸거나 `"subject"` 줄 뒤에 끼운다. 깨지면 안 쓰고 1. `--apply` 없으면 미리보기."""
    path = index_path(subject)
    with open(path, encoding="utf-8") as fh:
        original = fh.read()
    lines = original.split("\n")
    body = json.dumps(seen, ensure_ascii=False, sort_keys=True)
    done = False
    for i, line in enumerate(lines):
        m = SEEN_LINE.match(line)
        if m:
            lines[i] = m.group(1) + '"reviewSeen": ' + body + ","
            done = True
            break
    if not done:
        for i, line in enumerate(lines):
            m = SUBJECT_LINE.match(line)
            if m:
                lines.insert(i + 1, m.group(1) + '"reviewSeen": ' + body + ",")
                done = True
                break
    if not done:
        print("[실패] %s — \"subject\" 줄을 못 찾았다" % subject, file=sys.stderr)
        return 1
    text = "\n".join(lines)
    try:
        json.loads(text)
    except ValueError as exc:
        print("[실패] %s — 고치고 나니 JSON 이 깨진다, 안 썼다: %s" % (subject, str(exc)[:120]),
              file=sys.stderr)
        return 1
    if APPLY:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    return 0


def read_seen(subject):
    with open(index_path(subject), encoding="utf-8") as fh:
        return json.load(fh).get("reviewSeen")


def main(argv=None):
    ap = argparse.ArgumentParser(description="사용자가 본 장을 reviewSeen 에 적는다")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--subject")
    ap.add_argument("--add")
    ap.add_argument("--why")
    ap.add_argument("--init")
    ap.add_argument("--apply", action="store_true", help="없으면 미리보기(파일을 안 쓴다)")
    args = ap.parse_args(argv)
    global APPLY
    APPLY = args.apply
    if not args.list and not APPLY:
        print("[미리보기] --apply 를 주면 쓴다")

    if args.list:
        for path in sorted(glob.glob(os.path.join(ROOT, "data", "*", "index.json"))):
            subject = os.path.basename(os.path.dirname(path))
            seen = read_seen(subject)
            print("%s: %s" % (subject, "선언 없음" if seen is None else ", ".join(sorted(seen)) or "(없음)"))
        return 0
    if args.init:
        with open(args.init, encoding="utf-8") as fh:
            bundle = json.load(fh)
        worst = 0
        for subject, seen in bundle.items():
            worst = max(worst, write_seen(subject, seen))
            print("  %s ← %s" % (subject, ", ".join(sorted(seen)) or "(없음)"))
        return worst
    if not (args.subject and args.add and args.why):
        ap.error("--list · --init · 또는 --subject --add --why 를 함께 줄 것")
    seen = read_seen(args.subject) or {}
    seen[args.add] = args.why
    code = write_seen(args.subject, seen)
    if not code:
        print("  %s ← %s (%s)" % (args.subject, args.add, args.why))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
