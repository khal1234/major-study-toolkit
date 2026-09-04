"""공개본에서 1인칭 원문 인용을 사실 서술로 바꾼다 — 매핑 파일로 한 번에.

**왜 도구인가.** 공용 시스템 폴더(`~/Documents/naru`)를 공개용으로 다듬으면서
`기록/feedback-ledger.md` 158곳 · `규칙/AGENTS.md` 103곳 = **261곳**의 인용을 바꿔야 했다.
`Edit` 를 인용마다 부르면 그 횟수만큼 승인이 뜨고(실행 규율 4), `sed` 로 몰면 인용에
`*`·`?`·`(`·`[` 가 잔뜩 들어 있어 **정규식 이스케이프가 곧 결함원**이 된다.
그래서 **글자 그대로의 치환**만 하는 도구를 둔다.

**게이트가 이 도구의 값어치다** — 각 `old` 가 파일에 **정확히 한 번** 나와야 한다.
0번이면 내가 옮겨 적다 틀린 것이고, 2번 이상이면 **엉뚱한 자리도 함께 바뀐다.**
하나라도 어긋나면 **아무것도 쓰지 않고** 전부 보고한다(부분 적용은 되돌리기가 더 비싸다).

    python tools/rewrite_quotes.py --target <파일> --map <매핑.json>          # 예행
    python tools/rewrite_quotes.py --target <파일> --map <매핑.json> --apply  # 반영
    python tools/rewrite_quotes.py --target <파일> --survey                   # 남은 인용 세기

매핑은 `[{"old": "...", "new": "..."}, ...]`.
같은 인용이 여러 행에 되풀이돼 **일부러 전부 바꿔야 할 때**만 `"expect": N` 을 적는다 —
기본값 1 을 그대로 두면 위 게이트가 걸리므로, 여러 번 바꾸는 것은 **선언해야 하는 예외**다.

★ `--survey` 의 수는 **`*"…"*` 꼴의 이탤릭 인용**만 센다. 그 밖의 인용부호(규칙 이름·
파일 안 문자열)는 바꿀 대상이 아니라서 세지 않는다 — **범위를 밝히지 않은 0건은
'없다'가 아니다**(AGENTS 규칙 11).
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 이탤릭 인용 `*"…"*` — 여는 표시가 `*"` 이고 닫는 표시가 `"*` 인 것만 센다.
QUOTE_RE = re.compile(r'\*"[^"]*"\*')


def survey(text):
    """남은 이탤릭 인용 목록(순서대로)."""
    return QUOTE_RE.findall(text)


def plan(text, pairs):
    """(적용된 텍스트, 문제 목록). 문제가 하나라도 있으면 텍스트는 원본 그대로."""
    problems = []
    for i, pair in enumerate(pairs, 1):
        old = pair.get("old", "")
        if not old:
            problems.append(f"{i}: `old` 가 비어 있다")
            continue
        want = pair.get("expect", 1)
        n = text.count(old)
        if n != want:
            head = old[:60].replace("\n", " ")
            problems.append(f"{i}: {n}번 나옴({want}번이어야 한다) — {head}…")
    if problems:
        return text, problems

    out = text
    for pair in pairs:
        out = out.replace(pair["old"], pair["new"], pair.get("expect", 1))
    return out, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="고칠 파일")
    ap.add_argument("--map", dest="mapping", help="치환 매핑 JSON")
    ap.add_argument("--survey", action="store_true", help="남은 이탤릭 인용만 센다")
    ap.add_argument("--list", action="store_true", help="--survey 와 함께: 인용 원문도 찍는다")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다")
    args = ap.parse_args()

    target = Path(args.target)
    if not target.exists():
        sys.exit(f"대상 파일이 없다: {target}")

    # ★ 폴더를 주면 전수 표를 찍는다 (열린 날 2026-08-12).
    #   열린 경위: 파일마다 따로 재고 그 수를 **손으로 옮겨 적었는데**, 잰 뒤에 한 곳을 더
    #   고치고도 옛 수를 최종 수치로 보고했다(같은 실수 2건 — 변경일지 12 vs 실제 14 ·
    #   원장 153 vs 152). 원인은 부주의가 아니라 **재는 시점과 보고하는 시점이 다른 구조**다.
    #   → 보고 직전에 이 한 줄로 전수를 다시 찍으면 옮겨 적을 자리가 사라진다.
    if target.is_dir():
        rows = sorted(
            p for p in target.rglob("*")
            if p.is_file() and p.suffix.lower() in {".md", ".py", ".txt", ".ps1"}
        )
        total = 0
        for p in rows:
            try:
                n = len(survey(p.read_text(encoding="utf-8")))
            except (UnicodeDecodeError, OSError):
                continue
            if n:
                print(f"  {n:4d}  {p.relative_to(target)}")
                total += n
        print(f"[남은 이탤릭 인용] 합계 {total}곳 — {target}")
        return 0

    text = target.read_text(encoding="utf-8")

    if args.survey or not args.mapping:
        found = survey(text)
        print(f"[남은 이탤릭 인용] {len(found)}곳 — {target}")
        if args.list:
            for i, q in enumerate(found, 1):
                print(f"  {i:3d}. {q}")
        return 0

    pairs = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
    before = len(survey(text))
    out, problems = plan(text, pairs)
    if problems:
        print(f"[중단] {len(problems)}건이 어긋나 아무것도 쓰지 않았다:")
        for p in problems:
            print("  " + p)
        return 1

    after = len(survey(out))
    if args.apply:
        # ★★ **줄바꿈을 바꾸지 않는다** (고침 2026-08-13, 두 세션이 독립으로 걸렸다).
        #   `Path.write_text` 는 윈도우에서 `\n` 을 `\r\n` 으로 바꾼다. 그래서 **한 줄만
        #   고쳐도 파일 전 줄이 다시 쓰이고**, diff 가 「전체 변경」이 된다.
        #   이 도구의 값어치가 *"각 old 가 정확히 한 번 나올 때만, 글자 그대로"* 인데
        #   결과 diff 가 통째로면 **무엇을 바꿨는지 사람이 볼 수 없다** — 오늘 하루 종일
        #   붙든 「변경점을 알아볼 수 있게」와 정확히 같은 자리다.
        #   (`core.autocrlf` 덕에 커밋 blob 은 LF 로 정규화되지만 **작업 트리는 남는다** —
        #   그 상태로 다른 도구가 읽으면 그쪽 diff 도 함께 오염된다.)
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(out)
        print(f"[반영] {len(pairs)}곳 치환 — 이탤릭 인용 {before} → {after}")
    else:
        print(f"[예행] {len(pairs)}곳 치환 가능 — 이탤릭 인용 {before} → {after} (--apply 로 반영)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
