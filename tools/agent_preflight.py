# -*- coding: utf-8 -*-
"""Agent preflight for browser-blocked review work.

This is intentionally wired into build_site.py. A future agent does not need to
remember to run it: build, verify_workorder, and close_report all reach the same
entrypoint.

Opened 2026-07-24: AGENTS.md already said that SVG geometry must be reviewed via
render_figure_review.py PNG when localhost is blocked. The failure still recurred
because the rule was only read as prose, and non-SVG/browser-only residue was
reported together with already-verifiable SVG work.
"""
import os
import subprocess
import sys

from verify_workorder import browser_block_record_issues, section

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIT_STATUS_CMD = ["git", "-c", "core.quotepath=false", "status", "--short", "-uall"]
REQUIRED_AGENTS_MARKERS = (
    "tools/render_figure_review.py",
    "localhost 브라우저가 막혀도 이 비브라우저 PNG",
)
# ★★ 계약 본문이 AGENTS.md 에만 산다고 전제하면 「docs/ 이관」이 이 자를 죽인다 (2026-08-18).
#   실사고: 삽화 규격 절이 `docs/삽화-규격.md` 로 내려가면서 마커 둘이 AGENTS.md 에서 사라졌다.
#   **main 에는 과목이 없어 빌드를 안 돌리므로 아무도 못 봤고**, 과목 워크트리가 `git merge main`
#   한 순간 그 과목 빌드가 통째로 멈췄다(열역학 exit 1 — 데이터는 멀쩡한데 preflight 에서 죽는다).
#   즉 「이관」과 「그 절을 읽는 자」가 따로 놀았다. 내린 자리도 함께 보게 한다 —
#   절을 또 내리면 여기 한 줄을 더한다.
CONTRACT_FILES = ("CLAUDE.md", "docs/삽화-규격.md")


def read_contract_text(root=ROOT):
    """계약 마커가 살 수 있는 문서를 이어 붙인다. 없는 파일은 건너뛰되 전부 없으면 실패다."""
    texts = []
    for name in CONTRACT_FILES:
        try:
            texts.append(open(os.path.join(root, name), encoding="utf-8").read())
        except OSError:
            continue
    if not texts:
        raise OSError("계약 문서를 하나도 못 읽었다 — " + " · ".join(CONTRACT_FILES))
    return "\n".join(texts)


def changed_workorder_paths(root=ROOT):
    result = subprocess.run(
        GIT_STATUS_CMD, cwd=root, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    paths = []
    for line in (result.stdout or "").splitlines():
        path = line[3:].strip().strip('"').replace("\\", "/")
        if path.endswith(".workorder.md"):
            paths.append(path)
    return paths


def preflight_contract_issues(agents_text, workorders):
    """Return missing fallback contract and malformed browser-block records."""
    issues = []
    for marker in REQUIRED_AGENTS_MARKERS:
        if marker not in agents_text:
            issues.append(
                "SVG→PNG 계약 마커 누락(" + " · ".join(CONTRACT_FILES)
                + " 어디에도 없다) — " + marker
            )
    for path, text in workorders:
        progress = section(text, "진행 기록")
        for issue in browser_block_record_issues(progress):
            issues.append(path + ": " + issue)
    return issues


def run_preflight(root=ROOT, stream=None):
    stream = stream or sys.stdout
    try:
        agents_text = read_contract_text(root)
    except OSError as exc:
        print("[preflight FAIL] 계약 문서 읽기 실패 — " + str(exc), file=stream)
        return 1

    workorders = []
    for path in changed_workorder_paths(root):
        try:
            workorders.append((path, open(os.path.join(root, path), encoding="utf-8").read()))
        except OSError:
            continue
    issues = preflight_contract_issues(agents_text, workorders)
    if issues:
        print("[preflight FAIL] 브라우저 차단 대체 검증 계약 위반", file=stream)
        for issue in issues:
            print("  - " + issue, file=stream)
        return 1

    print(
        "[preflight OK] localhost 차단 시 SVG=PNG(view_image), "
        "정적 계약=빌드/회귀, viewport·scroll·글리프만 브라우저 전용 "
        f"(변경 워크오더 {len(workorders)}개 감사)",
        file=stream,
    )
    return 0


def main():
    return run_preflight()


if __name__ == "__main__":
    sys.exit(main())
