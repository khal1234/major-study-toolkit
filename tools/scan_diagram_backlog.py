# -*- coding: utf-8 -*-
"""noDiagramReason 중 '부모가 그릴' 계열(미완료 삽화 큐)만 골라 과목·챕터별로 나열한다.
git show로만 읽는다(워크트리 파일시스템을 안 연다). 일회성 조사용 — 판정은 하지 않는다."""
import subprocess
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = __file__.rsplit("tools", 1)[0]

SUBJECTS = {
    "appsolids": ("응용고체역학", ["00", "11", "12", "13", "14"]),
    "appthermo": ("응용열역학", ["00", "07", "08", "09", "10", "11", "12"]),
    "ee": ("전기전자공학기초 및 실험", ["%02d" % i for i in range(0, 16)] + ["91"]),
    "family": ("행복한 삶과 가족", ["00"]),
    "fluids": ("유체역학", ["%02d" % i for i in range(0, 9)]),
    "math2": ("공학수학 2", ["00", "07", "08", "09", "12", "17", "91"]),
    "mfg": ("기계공작법", ["00", "10", "11", "12", "13", "14", "15", "16", "17",
                         "19", "20", "21", "22", "23", "24", "25", "26"]),
    # 2-1(1학기) 과목 — 2026-09-05 사용자 지시로 추가(2-2 다 끝난 뒤 1학기꺼 돌리기)
    "thermo": ("열역학", ["00", "01", "02", "03", "04", "05", "06", "07", "08", "91", "92"]),
    "solids": ("고체역학", ["00", "01", "02", "03", "04", "05", "06", "07", "08",
                          "09", "10", "11", "12", "90", "91"]),
    "dynamics": ("동역학", ["00", "12", "13", "14", "15", "16", "17", "18", "19",
                          "91", "92", "93", "94", "95"]),
    "math": ("공학수학 1", ["00", "01", "02", "03", "04", "05", "06", "07", "08", "90", "91"]),
    "materials": ("기계재료", ["00", "01", "02", "03", "04", "05", "07", "08", "09",
                             "10", "11", "12", "13", "90", "91"]),
}

DEFER_MARKERS = ["부모가 그릴", "부모가 먼저", "부모가 그릴지"]

id_re = re.compile(r'"id":\s*"([^"]+)"')
reason_re = re.compile(r'"noDiagramReason":\s*"((?:[^"\\]|\\.)*)"')

total_hits = 0  # 누적 카운터 초기값 — 규격값이 아니라 집계 시작점
for branch, (folder, chapters) in SUBJECTS.items():
    for ch in chapters:
        path = f"data/{folder}/ch{ch}.json"
        r = subprocess.run(
            ["git", "-C", REPO, "show", f"{branch}:{path}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            continue
        text = r.stdout
        last_id = None
        for line in text.splitlines():
            m = id_re.search(line)
            if m:
                last_id = m.group(1)
            m2 = reason_re.search(line)
            if m2:
                reason = m2.group(1)
                if any(mk in reason for mk in DEFER_MARKERS):
                    total_hits += 1
                    snippet = reason[:70].replace("\\n", " ")
                    print(f"{branch}\tch{ch}\t{last_id}\t{snippet}")

print(f"--- 합계 {total_hits}건 ---", file=sys.stderr)
