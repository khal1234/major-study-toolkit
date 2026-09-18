# -*- coding: utf-8 -*-
"""피드백 원장에 **절 하나를 덧붙인다** (공용 폴더 `기록/feedback-ledger.md`).

    python tools/feedback_add.py <새 절이 든 파일>          # 세기만 한다
    python tools/feedback_add.py <새 절이 든 파일> --apply

★ **왜 도구인가 (열린 날 2026-09-07).** 원장은 331KB 라 `Read` 로 열 수 없고
  (`Edit` 는 먼저 읽어야 한다), `replace_doc_section.py` 는 **있는 절을 갈아끼우는**
  자라 마지막 절을 앵커로 써야 하는데 그 제목에 백틱이 들어 있으면
  `guard_bash` 가 명령 치환으로 보고 막는다(실측: 2026-09-07 그대로 막혔다).
  즉 «지적을 받으면 고치기 전에 원장에 한 줄» 이라는 규약이 **쓸 수 있는 경로 없이**
  서 있었다. 덧붙이기는 앵커가 필요 없다 — 그래서 이 자가 제일 단순한 답이다.

★ 경로는 `shared_sync_check.SHARED` 를 임포트해서 얻는다 — 환경변수를 존중하는
  유일한 자리이고, 손으로 적으면 다른 PC 에서 갈린다(CLAUDE.md 「공용 시스템」).

★ 검사는 둘뿐이다. ⑴ 새 절이 `## ` 로 시작하는가 ⑵ **같은 제목이 이미 있는가**
  (있으면 덧붙이기가 아니라 갱신이므로 `replace_doc_section.py` 로 보낸다).
  내용 판정은 하지 않는다 — 원장에 무엇을 적을지는 사람이 정한다.
"""
import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, ".claude", "hooks"))
from shared_sync_check import SHARED                                    # noqa: E402

LEDGER = os.path.join(str(SHARED), "기록", "feedback-ledger.md")


def heading_of(text):
    """새 절의 제목 줄. 순수 함수 — 회귀가 직접 부른다."""
    for line in text.splitlines():
        if line.startswith("## "):
            return line.rstrip()
    return None


def append_plan(ledger_text, section_text):
    """`(붙일 본문, 사유)` — 못 붙이면 본문이 None 이다. 순수 함수."""
    head = heading_of(section_text)
    if not head:
        return (None, "새 절에 `## ` 제목 줄이 없다 — 원장은 절 단위로 읽힌다.")
    if head in ledger_text:
        return (None, "같은 제목이 원장에 이미 있다 — 덧붙이기가 아니라 갱신이다.\n"
                      "  -> `python tools/replace_doc_section.py --file <원장> "
                      "--heading \"<제목>\" --from <파일> --apply`")
    body = section_text.strip("\n")
    joiner = "" if ledger_text.endswith("\n\n") else ("\n" if ledger_text.endswith("\n") else "\n\n")
    return (ledger_text + joiner + body + "\n", head)


def main():
    ap = argparse.ArgumentParser(description="피드백 원장에 절 하나를 덧붙인다")
    ap.add_argument("source", help="새 절이 든 파일(제목 줄 포함)")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다")
    ap.add_argument("--file", default=LEDGER, help="원장 경로(기본은 공용 폴더 원장)")
    a = ap.parse_args()

    with open(a.source, encoding="utf-8") as fh:
        section = fh.read()
    with open(a.file, encoding="utf-8") as fh:
        ledger = fh.read()

    new, why = append_plan(ledger, section)
    if new is None:
        print(why, file=sys.stderr)
        return 1
    if not a.apply:
        print("[미적용] 붙일 절: %s" % why)
        print("  원장 %d자 -> %d자 · `--apply` 로 실제로 쓴다" % (len(ledger), len(new)))
        return 0
    with open(a.file, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new)
    print("[적용] %s" % why)
    print("  %s (%d자)" % (a.file, len(new)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
