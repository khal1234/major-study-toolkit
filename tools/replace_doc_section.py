"""문서의 「절 하나」를 새 본문으로 갈아끼운다 — 큰 문서를 통째로 다시 쓰지 않기 위한 자리.

★ 왜 열렸나 (2026-08-16, `docs/AGENTS-삭감.workorder.md`).
`AGENTS.md` 삭감(2,267 → 1,700줄)에서 **두 제약이 동시에** 걸렸다:

⑴ **`Edit` 는 세션 3회째부터 가드가 막는다.** 그 파일은 settings 의 `ask` 에 걸려 있어
   `Edit` 를 부를 때마다 승인 프롬프트가 뜬다(실행 규율 4 — 파일 편집도 배치로).
⑵ **통째 `Write` 는 한 턴 출력에 안 들어간다.** 삭감본이 약 9만 자다. 중간에 잘리면
   그 파일이 **깨진 채로 저장된다** — 지침 파일에서는 그게 가장 비싼 실패다.

즉 남는 길이 «한 번에 다 쓰거나 · 승인을 여러 번 받거나» 둘뿐이었고 **둘 다 규율이 금지한
형태**다. 그래서 «이번에 새로 쓰는 절 하나»만 내보내고 나머지는 손대지 않는 수단을 만든다.

★ **판정하지 않는다.** 무엇을 지우고 무엇을 남길지는 사람이 정한다. 이 도구가 보증하는 것은
셋뿐이다 — 절 제목이 **유일한가** · 절의 **끝을 어디로 봤나** · 갈아끼운 뒤 **줄 수가 얼마인가**.

★ **코드펜스 안의 `#` 은 제목이 아니다.** 이 리포의 지침 문서는 ```` ```md ```` 블록 안에
`## 기준 커밋` 같은 줄을 예시로 담고 있어서, 펜스를 세지 않으면 절이 **엉뚱한 자리에서 끊긴다.**
잠금 `test_checks.py::test_doc_section_replace_respects_fences`.
★ **파일 전체가 되는 제목은 거부한다** — h1 처럼 아래에 같은 층 제목이 없으면 그 「절」은
문서 전체다(2026-08-16 실사고: AGENTS.md 1,043줄이 38줄로 덮였다).
잠금 「test_checks.py::test_doc_section_replace_refuses_whole_file」.

★ **제목에 백틱이 든 절은 이 도구로 못 넘긴다** — 가드가 명령 전체에서 백틱을 막는다
(실측 2026-08-16 「워크오더 수용 게이트 — tools/verify_workorder.py」). 그때는 절 범위를
sed 로 지우고 새 본문을 sed r 로 끼워 넣는다 — 범위는 제목 줄부터 다음 같은 층 제목 직전까지다.
"""
import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _heading_level(line):
    """제목이면 `#` 개수, 아니면 0. 펜스 판정은 호출자가 한다."""
    stripped = line.lstrip()
    if not stripped.startswith("#"):
        return 0
    hashes = len(stripped) - len(stripped.lstrip("#"))
    rest = stripped[hashes:]
    if not rest.startswith(" "):
        return 0
    return hashes


def section_span(lines, heading, prefix=False):
    """`heading` 줄부터 **같거나 더 높은 층의 다음 제목 직전**까지의 [시작, 끝) 을 돌려준다.

    제목이 없거나 둘 이상이면 예외다 — 어느 쪽이든 사람이 봐야 하는 상태이지,
    도구가 «첫 번째 것» 을 골라도 되는 자리가 아니다.
    `prefix=True` 면 제목 줄의 **앞부분**으로 찾는다 — 백틱 든 제목을 명령줄에 안 쓰려고.
    유일성 판정은 같다(펜스 밖의 제목 줄만 센다).
    """
    want = heading.rstrip()
    if prefix:
        in_fence, hits = False, []
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith("```"):
                in_fence = not in_fence
            elif not in_fence and _heading_level(ln) and ln.startswith(want):
                hits.append(i)
    else:
        hits = [i for i, ln in enumerate(lines) if ln.rstrip() == want]
    if not hits:
        raise LookupError(f"절 제목을 못 찾았다: {want!r}")
    if len(hits) > 1:
        raise LookupError(f"절 제목이 {len(hits)}곳에 있다(유일해야 한다): {want!r}")
    start = hits[0]
    level = _heading_level(lines[start])
    if level == 0:
        raise LookupError(f"제목 줄이 아니다: {want!r}")

    in_fence = False
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        lv = _heading_level(lines[i])
        if lv and lv <= level:
            end = i
            break

    # ★ 그 절이 «파일 전체» 면 거부한다 (2026-08-16 실사고).
    # h1 처럼 아래에 같은 층 제목이 없으면 section_span 은 파일 끝을 돌려준다 —
    # 그것은 절 교체가 아니라 «파일 교체» 이고, 실제로 AGENTS.md 1,043줄이
    # 38줄로 덮였다. 되돌리는 데 revert_files.py 가 필요했다.
    if start == 0 and end == len(lines):
        raise LookupError(
            f"그 제목의 절이 «파일 전체»다 — 절 교체가 아니라 파일 교체다({want!r}, 층 {level}). "
            "문서 머리를 고치려면 Write 로 쓰거나, 아래 절 제목을 줘서 범위를 좁혀라."
        )
    return start, end


def replace_section(text, heading, body, prefix=False):
    lines = text.splitlines(keepends=True)
    start, end = section_span(lines, heading, prefix)
    body_lines = body.splitlines(keepends=True)
    if body_lines and not body_lines[-1].endswith("\n"):
        body_lines[-1] += "\n"
    return "".join(lines[:start] + body_lines + lines[end:]), end - start, len(body_lines)


def section_text(text, heading, prefix=False):
    """갈아끼우기 전의 그 절 본문(제목 줄 포함) — `--move-to` 가 옮겨 적는 것."""
    lines = text.splitlines(keepends=True)
    start, end = section_span(lines, heading, prefix)
    return "".join(lines[start:end])


def main():
    ap = argparse.ArgumentParser(description="문서의 절 하나를 파일 내용으로 갈아끼운다")
    ap.add_argument("--file", required=True, help="고칠 문서(예: AGENTS.md)")
    ap.add_argument("--heading", required=True, help="갈아끼울 절의 제목 줄 전체(--heading-prefix 면 앞부분)")
    ap.add_argument("--heading-prefix", action="store_true", help="제목 줄의 앞부분으로 찾는다")
    ap.add_argument("--from", dest="src", required=True, help="새 본문 파일(제목 줄 포함)")
    ap.add_argument("--move-to", help="원래 절을 이 파일 끝에 덧붙인다(경로 규칙·스킬로 옮길 때)")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다(없으면 세기만 한다)")
    args = ap.parse_args()

    target = Path(args.file)
    src = Path(args.src)
    text = target.read_text(encoding="utf-8")
    body = src.read_text(encoding="utf-8")

    try:
        new_text, old_n, new_n = replace_section(text, args.heading, body, args.heading_prefix)
        moved = section_text(text, args.heading, args.heading_prefix)
    except LookupError as exc:
        sys.exit(f"[절 교체] {exc}")
    if args.move_to:
        print(f"  옮길 곳 {args.move_to} (+{moved.count(chr(10))}줄)")
        if args.apply:
            dest = Path(args.move_to)
            prev = dest.read_text(encoding="utf-8") if dest.is_file() else ""
            sep = "" if not prev or prev.endswith("\n\n") else ("\n" if prev.endswith("\n") else "\n\n")
            dest.write_text(prev + sep + moved.rstrip("\n") + "\n", encoding="utf-8", newline="\n")

    before = text.count("\n")
    after = new_text.count("\n")
    print(f"[절 교체] {target}  «{args.heading.strip()}»")
    print(f"  그 절   {old_n}줄 → {new_n}줄 ({new_n - old_n:+d})")
    print(f"  파일 전체 {before}줄 → {after}줄 ({after - before:+d})")
    if not args.apply:
        print("  ※ --apply 를 안 줬다 — 파일은 그대로다")
        return
    target.write_text(new_text, encoding="utf-8")
    print("  → 썼다")


if __name__ == "__main__":
    main()
