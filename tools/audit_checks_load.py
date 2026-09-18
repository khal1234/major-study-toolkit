# -*- coding: utf-8 -*-
"""이해도 점검(떠올리기·연결하기·설명하기)이 **한 절에 몇 개나 붙어 있는지** 센다 — 읽기 전용.

왜 있나 (열린 날 2026-07-31, 사용자 지적):
    *[발화 생략]*

    빌드에는 상한(`CHECKS_MAX_PER_SECTION`)만 있고 **분포를 보여 주는 자가 없었다.**
    상한 아래에서도 어떤 절은 5개, 어떤 절은 1개면 읽는 리듬이 절마다 달라진다 —
    사람이 세어 보기 전에는 그 편차가 보이지 않는다(라벨 간격에서 겪은 것과 같은 구조).

★ **답 길이도 여기서 잰다** (2026-08-13, 승격 잔량 ch01-review-inbox 「G」 를 갚으며).
    그 항목이 남긴 말: *[발화 생략]* 상한을 세우려면 **먼저 재야 한다** —
    자를 눈으로 고르면 전 챕터가 못 지키는 값이 나온다(라벨 여백 391건 중 91건 오탐의 전례).
    `--lengths` 가 단계별 분포와 **가장 긴 것 몇 개**를 찍는다.

사용:
    python tools/audit_checks_load.py            # 전 챕터
    python tools/audit_checks_load.py --chapter=ch02.json
    python tools/audit_checks_load.py --lengths  # 답 길이 분포 (상한을 정할 때)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from buildlib.checks_content import CHECKS_MAX_PER_SECTION, _iter_check_owners  # noqa: E402
import audit_content                                                            # noqa: E402

STAGES = ("recall", "connect", "explain")


def _report_lengths(names):
    """단계별 답 길이 분포. 상한을 **재고 나서** 정하기 위한 자다."""
    from buildlib.checks_content import check_answer_sentences          # noqa: E402
    per_stage = {s: [] for s in STAGES}
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for kind, item in _iter_check_owners(data):
            for check in item.get("comprehensionChecks") or []:
                stage = check.get("stage")
                if stage not in per_stage:
                    continue
                answer = str(check.get("answer") or "")
                per_stage[stage].append(
                    (check_answer_sentences(answer), len(answer),
                     "%s %s/%s" % (name[:4], item.get("id", "?"), check.get("id", "?"))))
    print("답 길이 분포 — 문장 수는 종결부호(`.`·`?`·`!`) 로 센다")
    for stage in STAGES:
        rows = sorted(per_stage[stage], reverse=True)
        if not rows:
            print("\n[%s] 0개" % stage)
            continue
        counts = [r[0] for r in rows]
        print("\n[%s] %d개 · 문장 수 평균 %.2f · 최대 %d"
              % (stage, len(rows), sum(counts) / len(counts), counts[0]))
        for n in sorted(set(counts)):
            print("   %d문장 : %d개" % (n, counts.count(n)))
        for sent, chars, where in rows[:5]:
            print("   [최장] %d문장 %d자 — %s" % (sent, chars, where))
    return 0


def main():
    ap = argparse.ArgumentParser(description="이해도 점검 분포 감사 (읽기 전용)")
    ap.add_argument("--chapter")
    ap.add_argument("--lengths", action="store_true",
                    help="답 길이 분포만 찍는다 (상한을 정할 때)")
    args = ap.parse_args()

    names = ([args.chapter] if args.chapter
             else [name + ".json" for name in audit_content.CHAPTERS])
    if args.lengths:
        return _report_lengths(names)
    print("상한 %d개/절 — 아래는 **분포**다(상한 아래여도 편차가 크면 절마다 리듬이 달라진다)"
          % CHECKS_MAX_PER_SECTION)
    for name in names:
        path = os.path.join(audit_content.DATA, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        rows = []
        for kind, item in _iter_check_owners(data):
            checks = item.get("comprehensionChecks") or []
            if not checks:
                continue
            per = {s: sum(1 for c in checks if c.get("stage") == s) for s in STAGES}
            rows.append((kind, item.get("id", "?"), len(checks), per))
        if not rows:
            continue
        total = sum(r[2] for r in rows)
        print("\n-- %s : 절·카드 %d곳에 %d개 (평균 %.1f)"
              % (name, len(rows), total, total / len(rows)))
        for kind, ident, n, per in sorted(rows, key=lambda r: -r[2]):
            mark = "  <-- 상한 초과" if n > CHECKS_MAX_PER_SECTION else ""
            print("   %-10s %-34s %d개 (떠올리기 %d · 연결 %d · 설명 %d)%s"
                  % (kind, ident, n, per["recall"], per["connect"], per["explain"], mark))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
