"""Register a classified user criticism before writing a workorder or editing content.

재는 것: 없음 — 접수 줄을 인박스에 쓰고, 같은 줄을 공용 폴더 피드백 원장(`기록/feedback-ledger.md`)에도 한 행 남긴다.
문턱과 근거: 부류·시스템은 `--machine` 이 필수다(자 이름 또는 「미정 · 무엇을 만들지」) — 커밋 게이트
  `feedback_lifecycle.machine_issues` 와 같은 판정선. 원장 행을 여기서 같이 쓰는 이유: 채팅 지적이 원장에 안
  적혀 다음 세션의 조회가 빈손이었다(사용자 2026-09-25, 재발 E29 — 09-19 지적이 뷰어 주석에만 있었다).
못 보는 것: 원장 폴더가 없으면(다른 기계) 인박스만 쓰고 그 사실을 찍는다 · 관찰 문장이 지적을 옳게 옮겼는지.

    python tools/feedback_intake.py <인박스> <ID> <단발|부류|시스템> <관찰> <범위> <원인> [--machine <자>]
"""
import argparse
import datetime as _dt
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from feedback_lifecycle import triage_issues, machine_issues, registry_ids  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _ledger_path():
    sys.path.insert(0, str(ROOT / ".claude" / "hooks"))
    try:
        from shared_sync_check import SHARED
    except Exception:  # noqa: BLE001
        return None
    path = Path(SHARED) / "기록" / "feedback-ledger.md"
    return path if path.is_file() else None


def ledger_row(inbox_rel, issue_id, classification, observation, scope, cause, machine):
    """원장 표의 한 행 — 열은 원장 53행 머리(날짜 · 제기 · 지적 · 부류 · 범위 · 기계 방지 · 상태)를 따른다."""
    today = _dt.date.today().isoformat()
    cell = lambda s: str(s).replace("|", "·").replace("\n", " ")  # noqa: E731
    return (f"| {today} | 사용자({cell(inbox_rel)})→{issue_id} | {cell(observation)} "
            f"| {classification} · 원인: {cell(cause)} | {cell(scope)} | {cell(machine or '—')} | 열림 |")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inbox', type=Path)
    parser.add_argument('id')
    parser.add_argument('classification', choices=['단발', '부류', '시스템'])
    parser.add_argument('observation')
    parser.add_argument('scope')
    parser.add_argument('cause')
    parser.add_argument('--machine', default='', help='자 이름(규칙 등록부 id) 또는 「미정 · 무엇을 만들지」 — 부류·시스템은 필수')
    parser.add_argument('--no-ledger', action='store_true', help='원장 행을 안 쓴다(테스트용)')
    args = parser.parse_args()
    inbox = (ROOT / args.inbox).resolve()
    try:
        relative = inbox.relative_to(ROOT).as_posix()
    except ValueError:
        parser.error('inbox must stay inside this repository')
    if relative != 'docs/받은것-인박스.md' and not re.fullmatch(
            r'data/[^/]+/ch\d{2}-review-inbox\.md', relative):
        parser.error('target must be a chapter or common feedback inbox')
    if not inbox.parent.is_dir():
        parser.error('subject directory does not exist')
    text = inbox.read_text(encoding='utf-8') if inbox.exists() else ''
    if re.search(rf'(?m)^\s*-\s*[☐☑△]\s+{re.escape(args.id)}(?:\s|\b)', text):
        parser.error('ID already appears in the inbox; reconcile that entry instead')
    line = (f'- ☐ {args.id} · {args.observation} | 분류={args.classification} '
            f'| 범위={args.scope} | 원인={args.cause}')
    if args.machine.strip():
        line += f' | 기계={args.machine.strip()}'
    problems = triage_issues([line]) + machine_issues([line], registry_ids(ROOT))
    if problems:
        parser.error('; '.join(problems))
    with inbox.open('a', encoding='utf-8') as stream:
        if not text:
            stream.write(f'# {relative} 사용자 지적 인박스\n')
        stream.write('\n' + line + '\n')
    print(f'registered {args.id} in {relative}')
    if args.no_ledger:
        return
    ledger = _ledger_path()
    if ledger is None:
        print('[알림] 공용 폴더 원장을 못 찾아 인박스에만 적었다 — 원장 행은 사람이 옮긴다')
        return
    with ledger.open('a', encoding='utf-8') as stream:
        stream.write(ledger_row(relative, args.id, args.classification, args.observation,
                                args.scope, args.cause, args.machine.strip()) + '\n')
    print(f'ledger row appended: {ledger}')


if __name__ == '__main__':
    main()
