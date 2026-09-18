# -*- coding: utf-8 -*-
r"""«사람이 정해야 한다» 옆에 이미 열어볼 수 있는 출처가 있는데 안 열었는가 — 후보만 낸다.

    python tools/audit_deferred_to_user.py
    python tools/audit_deferred_to_user.py --fail-only

열린 날 2026-09-13. 공용 폴더 원장 2026-09-13 「「확인 필요」로 미룬 것이 노션 한 번 열면 끝나는
일이었다」가 이 도구를 요구했다 — 전전 과목 PDF 8개 중 4개의 주차를
`data/전기전자공학기초 및 실험/SUBJECT.md` 가 "장 대응은 사람이 정해야 한다"로 미뤄 뒀는데,
바로 위 줄에 노션 주소가 이미 적혀 있었다. 08-24 원장 항목(「판정은 받고 실행은 사용자에게
넘긴다」)의 더 좁은 하위형 — **판단형 구역(규칙 10 「노랑」) 선언이 «내가 안 열어본 것»의
도피처가 되는 자리**를 잡는다.

★ **이 도구는 판정하지 않는다.** 「사람이 정해야 한다」 옆에 출처가 있다고 전부 게으름은
  아니다 — 정말 취향·허가가 답인 자리도 있다(예: 배포 여부, 색 선택). 후보만 내고 사람이
  하나씩 「진짜 판단형」과 「안 열어본 것」을 가른다(`audit_convention_drift.py`와 같은 태도).
★ **무엇을 못 보나.** ⑴ 문자열 매칭이라 출처가 «근처에 있다»는 판정 안 됨(±3줄 창을
  넘는 참조는 못 본다) ⑵ 출처가 「이미 확인했다」고 본문이 밝혀도 문구만 같으면 다시 걸린다 —
  그래서 사람이 판정한 자리는 `--waive` 목록에 사유와 함께 적는다 ⑶ `docs/폐기된-규약.md`처럼
  **의도적으로 역사 기록인** 문서는 대상에서 뺀다(폐기 규약은 지금 다시 안 열어봐도 된다).
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")

# 사람에게 미루는 표현 — 넓히면 오탐이 늘어난다, 실측으로 늘린다.
DEFER_PHRASES = ("사람이 정해야 한다", "확인 필요", "판정 대기", "확인이 필요하다")

# 근처에 있으면 "열어볼 수 있었다"의 증거로 본다.
SOURCE_PATTERN = re.compile(r"https?://\S+|[^\s가-힣]+\.pdf", re.IGNORECASE)

WINDOW = 3  # 지적 줄 위아래로 볼 줄 수

# 사람이 「진짜 판단형이다」로 이미 가른 자리 — (파일 상대경로, 지적 줄이 포함하는 부분 문자열).
# 사유 없이 추가하지 않는다(CLAUDE.md 「고치기」 절 — 면제는 보류 넷 중 하나로만).
WAIVED = {
    # 예: ("data/기계공작법/SUBJECT.md", "시험 범위의 세부(장 안에서 빼는 절이 있는지)는 강의계획서에 없다"):
    #     "강의계획서 자체에 없는 정보라 열어볼 출처가 없다 — 수업에서 확인해야 하는 진짜 판단형.",
}


def _target_files():
    out = []
    if os.path.isdir(DATA):
        for sub in sorted(os.listdir(DATA)):
            p = os.path.join(DATA, sub, "SUBJECT.md")
            if os.path.isfile(p):
                out.append(p)
    if os.path.isdir(DOCS):
        for name in sorted(os.listdir(DOCS)):
            if name.endswith(".md") and "폐기" not in name:
                out.append(os.path.join(DOCS, name))
    return out


def scan_file(path):
    """이 파일에서 (줄번호, 지적 줄, 근처 출처 목록) 후보를 낸다."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    hits = []
    for i, line in enumerate(lines):
        if not any(p in line for p in DEFER_PHRASES):
            continue
        lo, hi = max(0, i - WINDOW), min(len(lines), i + WINDOW + 1)
        nearby = "\n".join(lines[lo:hi])
        sources = SOURCE_PATTERN.findall(nearby)
        if not sources:
            continue
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        if any(rel == wp and sub in line for (wp, sub) in WAIVED):
            continue
        hits.append((i + 1, line.strip(), sources))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fail-only", action="store_true",
                     help="후보가 있을 때만 exit 1(회귀·close_report 용)")
    args = ap.parse_args()

    total = 0
    files_seen = 0
    for path in _target_files():
        files_seen += 1
        hits = scan_file(path)
        if not hits:
            continue
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        print("-- %s --" % rel)
        for lineno, text, sources in hits:
            total += 1
            print("  [%d] %s" % (lineno, text[:100]))
            print("      옆 출처: %s" % ", ".join(sources[:2]))

    print("\n합계 — 후보 %d건 · 훑은 파일 %d개" % (total, files_seen))
    print("※ 판정하지 않는다 — 진짜 판단형(취향·허가)과 안 열어본 것은 사람이 가른다.")
    if not args.fail_only:
        return 0
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
