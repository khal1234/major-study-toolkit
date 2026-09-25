"""Small commit-time link between new work orders, chapter edits and feedback inboxes.

This checks record keeping. It cannot decide whether a user's criticism is correct or
whether a fix actually closes it; that judgment stays in the chapter inbox.

재는 것(2026-09-25 추가): 부류·시스템 지적은 「자」 없이 못 닫는다 — ☐ 접수 줄에는 `기계=` 칸이 있어야 하고
  (`미정 · <무엇을 만들지>` 허용), ☑ 로 닫는 줄의 `기계=` 는 `docs/규칙-등록부.json` 의 id 여야 한다.
문턱과 근거: 등록부 id 여야 하는 이유는 소급 훑기(`audit_convention_drift`)와 사람 훑기 목록이 둘 다
  등록부에서 나오기 때문이다 — 등록 안 된 자는 다른 과목에 안 간다(사용자 2026-09-25 [발화 생략] · 재발 E29·E31·E35).
못 보는 것: 등록된 자가 실제로 그 지적을 재는지(이름만 빌린 것) · 단발로 분류해 빠져나가는 것(분류는 사람 몫).
"""
from pathlib import Path
import json
import re

CHAPTER = re.compile(r"^data/([^/]+)/ch(\d{2})\.json$")
SUBJECT_WORKORDER = re.compile(r"^data/([^/]+)/[^/]+\.workorder\.md$")
COMMON_WORKORDER = re.compile(r"^docs/[^/]+\.workorder\.md$")
LINK = re.compile(r"(?m)^Feedback-Inbox:\s*((?:data/[^\r\n#]+/ch\d{2}-review-inbox|docs/받은것-인박스)\.md)#([\w-]+)\s*$")
NEW_ISSUE = re.compile(r"^\s*-\s*☐\s+([\w-]+)\b")
CLOSED_ISSUE = re.compile(r"^\s*-\s*☑(?:\([^)]*\))?\s+([\w-]+)\b")
CLASS = re.compile(r"\|\s*분류=(단발|부류|시스템)\s*\|")
MACHINE = re.compile(r"\|\s*기계=([^|\r\n]+?)\s*(?:\||$)")
REGISTRY = "docs/규칙-등록부.json"


def triage_issues(added_lines: list[str]) -> list[str]:
    """New feedback must state its class, impact scope and causal mechanism."""
    problems = []
    for line in added_lines:
        match = NEW_ISSUE.search(line)
        if not match:
            continue
        if not CLASS.search(line) or not re.search(r"\|\s*범위=\S", line) or not re.search(r"\|\s*원인=\S", line):
            problems.append(f"{match.group(1)}: classify before editing: 분류=단발/부류/시스템 | 범위=... | 원인=...")
    return problems


def registry_ids(root: Path) -> set[str]:
    """규칙 등록부의 id 전부(machine·read·render 가리지 않는다). 파일이 없으면 빈 집합 — 그러면 ☑ 가 전부 막힌다(엄한 쪽)."""
    path = root / REGISTRY
    if not path.is_file():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = data.get("rules") if isinstance(data, dict) else data
    return {r.get("id") for r in (rules or []) if isinstance(r, dict) and r.get("id")}


def machine_issues(added_lines: list[str], ids: set[str]) -> list[str]:
    """부류·시스템 지적은 자 없이 못 닫는다. 접수(☐)는 `기계=` 칸이 있어야 하고, 닫음(☑)은 등록부 id 여야 한다."""
    problems = []
    for line in added_lines:
        cls = CLASS.search(line)
        if not cls or cls.group(1) == "단발":
            continue
        machine = MACHINE.search(line)
        value = machine.group(1).strip() if machine else ""
        new = NEW_ISSUE.search(line)
        if new and not value:
            problems.append(f"{new.group(1)}: 부류·시스템 접수에는 기계=<규칙 등록부 id | 미정 · 무엇을 만들지> 칸이 필요하다")
        closed = CLOSED_ISSUE.search(line)
        if closed and value not in ids:
            problems.append(f"{closed.group(1)}: 부류·시스템은 자 없이 못 닫는다 — 기계=<{REGISTRY} 의 id> "
                            f"(지금: {value or '없음'}). 자를 만들었으면 등록부에 올리고, 사람이 볼 것이면 how=read 로 등록한다")
    return problems


def linkage_issues(root: Path, changed: list[str], added: list[str]) -> list[str]:
    """Return specific records missing from this commit; do not mutate files."""
    issues = []
    changed_set = set(changed)
    for rel in added:
        match = SUBJECT_WORKORDER.fullmatch(rel)
        common = COMMON_WORKORDER.fullmatch(rel)
        if not match and not common:
            continue
        text = (root / rel).read_text(encoding="utf-8")
        refs = LINK.findall(text)
        if not refs:
            issues.append(f"{rel}: new workorder needs Feedback-Inbox: <chapter or common inbox>#ID")
            continue
        for inbox_rel, issue_id in refs:
            if match and not inbox_rel.startswith(f"data/{match.group(1)}/"):
                issues.append(f"{rel}: inbox subject differs: {inbox_rel}")
                continue
            if common and inbox_rel != "docs/받은것-인박스.md":
                issues.append(f"{rel}: common workorder must link common feedback inbox")
                continue
            inbox = root / inbox_rel
            row = next((line for line in inbox.read_text(encoding="utf-8").splitlines()
                        if re.match(rf"^\s*-\s*[☐☑△]\s+{re.escape(issue_id)}(?:\s|\b)", line)), "") if inbox.is_file() else ""
            if not row:
                issues.append(f"{rel}: {inbox_rel} has no status line for {issue_id}")
            elif triage_issues([row.replace('☑', '☐', 1).replace('△', '☐', 1)]):
                issues.append(f"{rel}: {issue_id} has no class/scope/cause decision in {inbox_rel}")
    for rel in changed:
        match = CHAPTER.fullmatch(rel)
        if not match:
            continue
        inbox_rel = f"data/{match.group(1)}/ch{match.group(2)}-review-inbox.md"
        inbox = root / inbox_rel
        if not inbox.is_file() or inbox_rel in changed_set:
            continue
        if re.search(r"(?m)^\s*-\s*☐\s+", inbox.read_text(encoding="utf-8")):
            issues.append(
                f"{rel}: open feedback exists; include {inbox_rel} in this commit "
                "with completed/partial/unrelated judgment, not an automatic checkmark"
            )
    return issues
