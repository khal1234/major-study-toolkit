#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""긴 명령의 실행 시간을 **재고 · 남기고 · 다음번에 미리 말한다** (신설 2026-08-18).

    python tools/runtime_note.py -- python tools/close_report.py
    python tools/runtime_note.py --list

앞에 붙이기만 하면 된다 — ⑴ 기록이 있으면 **시작 전에** *"지난 실행 34분"* 을 찍고
⑵ 명령을 그대로 돌리고 ⑶ 걸린 시간을 `실행시간.csv` 에 한 줄 남긴다(도구 옆 `기록/` 이나
`docs/` 를 찾아 쓴다 — 자리는 프로젝트마다 다르다).

## 왜 열렸나 — 사용자 지적 (전 프로젝트)

*"작업 돌리면 얼마나 걸릴 것 같다 예상 시간을 안주네. 얼추 작업을 돌려봐서 견적
나오는 것도 있고 안나와도 예측은 해볼만한게 있을텐데."*

견적의 근거는 **기록된 지난 실행**뿐이다(«수치에는 근거를 붙인다» — 근거 없는 견적은
도장이다). 그런데 아무도 실행 시간을 **안 남기니** 근거가 생길 수 없었다.
XSanity 실사고가 그 값을 보여 준다: `close_report` 가 34분 걸리는 것을 **아무도 몰라서**
넷을 나란히 띄웠다. 지난 실행이 「34분」이라고 적혀 있었으면 두 번째를 안 띄웠다.

- **판정하지 않는다.** 오래 걸린다고 안 막는다 — 아는 것을 말할 뿐이다.
- **견적은 마지막 실행 그대로다.** 평균·추세는 안 낸다 — 게이트 수가 바뀌면 평균이
  거짓말을 한다. 마지막 값 + 그 날짜면 읽는 쪽이 스스로 판정한다.
- 기록 형식: `이름,날짜,초,exit코드`. **손으로 고치지 않는다.**
"""
import csv
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_NAME = "실행시간.csv"


def record_path():
    for d in ("기록", "docs", "."):
        p = os.path.join(ROOT, d)
        if os.path.isdir(p):
            return os.path.join(p, CSV_NAME)
    return os.path.join(ROOT, CSV_NAME)


def key_of(argv):
    """명령의 이름 — 스크립트 파일명이 있으면 그것, 없으면 첫 토큰."""
    for tok in argv:
        base = os.path.basename(tok)
        if base.endswith((".py", ".ps1", ".sh", ".js")):
            return base
    return os.path.basename(argv[0]) if argv else "?"


def last_run(key):
    try:
        with io.open(record_path(), encoding="utf-8") as fh:
            rows = [r for r in csv.reader(fh)
                    if r and not r[0].startswith("#") and r[0] == key]
    except OSError:
        return None
    return rows[-1] if rows else None


def human(sec):
    sec = float(sec)
    if sec < 90:
        return "%.0f초" % sec
    return "%.0f분" % (sec / 60)


def main():
    if "--list" in sys.argv:
        try:
            print(io.open(record_path(), encoding="utf-8").read().rstrip())
        except OSError:
            print("기록이 아직 없다: %s" % record_path())
        return 0
    if "--" not in sys.argv:
        print(__doc__.split("\n\n")[0])
        return 2
    argv = sys.argv[sys.argv.index("--") + 1:]
    if not argv:
        return 2
    key = key_of(argv)
    prev = last_run(key)
    if prev:
        print("[예상] %s — 지난 실행 %s (%s, exit %s)"
              % (key, human(prev[2]), prev[1], prev[3]), flush=True)
    else:
        print("[예상] %s — 기록 없음 · 이번이 첫 근거가 된다" % key, flush=True)
    t0 = time.time()
    try:
        rc = subprocess.run(argv).returncode
    except FileNotFoundError as exc:
        print("실행 불가: %s" % exc)
        return 127
    took = time.time() - t0
    p = record_path()
    new = not os.path.isfile(p)
    try:
        with io.open(p, "a", encoding="utf-8", newline="") as fh:
            if new:
                fh.write("# 생성물이다 — 손으로 고치지 않는다. runtime_note.py 가 쓴다.\n")
                fh.write("# 이름,날짜,초,exit코드 — 견적은 «마지막 실행 그대로» 다(평균은 거짓말한다)\n")
            csv.writer(fh).writerow([key, time.strftime("%Y-%m-%d"), "%.0f" % took, rc])
    except OSError:
        pass
    print("[실측] %s — %s (exit %d) · 기록: %s"
          % (key, human(took), rc, os.path.relpath(p, ROOT)))
    return rc


if __name__ == "__main__":
    sys.exit(main())
