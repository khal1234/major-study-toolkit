# -*- coding: utf-8 -*-
"""**이 리포가 세션 시작에 싣는 지침의 총량**을 잰다 — 래칫 (신설 2026-08-16).

★ 범위를 이름에 박아 둔다(2026-09-12, Codex 검토 F07): 소계는 **프로젝트 정적 지침**뿐이다.
  사용자 층(`~/.claude/rules`)도 매 세션 실리지만 리포 밖이라 래칫에 안 넣고 참고로만 찍는다
  (`user_layer_files`). 「실제로 로드된 문맥」은 또 다른 수이고 이 자는 그것을 못 잰다.

    python 도구/audit_guide_size.py [프로젝트]      # 지금 크기와 기준선 대비 증감
    python 도구/audit_guide_size.py . --accept       # 지금 크기를 기준선으로 받는다

**왜 이 자인가** (사용자 물음 2026-08-16): *[발화 생략]*

★★ **재 보니 확 늘어난 순간이 없었다.** 전공정리 `AGENTS.md` 실측 —
   하루 130~260줄씩 **매일** 자라 143KB(8/12) → 214KB(8/16)가 됐고, 총 2,228줄 중
   **933줄(42%)이 닷새 만에** 쓰였다. 8월 커밋 중 60줄을 넘는 추가는 **하나도 없다** —
   각각은 다 정당해 보이고, **합만 아무도 안 봤다.**

★ **그래서 이 자의 일은 「합을 보이게 하는 것」 하나다.**
  - **판정하지 않는다 · 막지 않는다 · 언제나 exit 0.** 지침이 자라는 데는 정당한 이유가
    있고(실사고가 규칙이 된다), 상한을 근거 없이 박으면 그게 15항이 금지한 그것이다.
  - **래칫이다** — 기준선보다 늘면 신고하고 줄면 조용하다. `audit_magic_numbers` 와 같은 형태.
  - ★ **문서 안에 손으로 적은 크기는 반드시 낡는다.** 실제로 `AGENTS.md` 는 자기를
    *[발화 생략]* 라고 적은 채 214KB 가 돼 있었다(8/12에 재고 아무도 다시 안 쟀다).
    **그 줄을 지우고 이 자를 가리키는 것**이 이 도구가 있는 두 번째 이유다.

★ **한 파일이 아니라 「실리는 것 전부」를 잰다.** `CLAUDE.md` 가 `@AGENTS.md` 처럼
  import 하는 것까지 따라가 합을 낸다 — 물음이 *[발화 생략]* 이기 때문이다.
  import 없이 `docs/` 에 둔 것은 **안 실리므로 안 센다**(그게 「올릴 자격」이 시키는 배치다).

★ **토큰은 이 자가 못 잰다.** 줄·글자·바이트는 잰 값이고, 토큰은 `messages.count_tokens`
  가 정본이다. 한글은 한 글자가 3바이트라 **바이트로 보면 부풀어 보인다** — 글자로 본다.
"""
import argparse
import datetime
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT_MARK = "CLAUDE.md"
BASELINE_NAMES = ("지침-크기-기준선.txt",)
# `@경로` 한 줄이 곧 import 다. 인용부호·백틱 안의 것은 세지 않는다(문서가 자기를 설명한다).
IMPORT = re.compile(r"^@(\S+)\s*$")


def baseline_path(root):
    """기준선을 **찾는다** — 리포 뿌리와 한 칸 아래. 경로를 코드에 박지 않는다
    (`scan_private.LEDGER_NAMES` · `audit_session_cost.gate_bases` 와 같은 규약)."""
    for name in BASELINE_NAMES:
        for cand in [root / name] + sorted(root.glob("*/" + name)):
            if cand.is_file():
                return cand
    return root / "기록" / BASELINE_NAMES[0]


def loaded_files(root):
    """`CLAUDE.md` 와 그것이 import 하는 것들. 순수에 가깝게 — 테스트가 직접 부른다.

    ★ **한 겹만 따라간다.** import 의 import 까지 재귀하면 순환에 걸리고, 이 계통은
      실제로 한 겹만 쓴다(`CLAUDE.md` → `AGENTS.md`·`SUBJECT.md`).
    """
    head = root / ROOT_MARK
    if not head.is_file():
        return []
    out = [head]
    for line in head.read_text(encoding="utf-8", errors="replace").splitlines():
        m = IMPORT.match(line.strip())
        if not m:
            continue
        target = (root / m.group(1)).resolve()
        if target.is_file() and target not in out:
            out.append(target)
    return out


def scoped_files(root):
    """`.claude/rules/**/*.md` 와 `.claude/skills/*/SKILL.md` → [(이름, 경로, 종류)].

    종류: `상시`(규칙인데 `paths:` 없음 — 세션 시작에 실린다) · `경로`(그 파일을 Read 할 때) ·
    `스킬`(부를 때 본문이 실린다). 이름은 `.claude/` 아래 상대경로라 `SKILL.md` 끼리 안 겹친다.
    못 보는 것: 스킬 description 은 매 세션 실리는데 이 자는 파일 전체를 한 줄로 센다.
    """
    base = root / ".claude"
    out = []
    if (base / "rules").is_dir():
        for p in sorted((base / "rules").rglob("*.md")):
            head = p.read_text(encoding="utf-8", errors="replace")
            front = head.split("\n---", 1)[0] if head.startswith("---") else ""
            kind = "경로" if re.search(r"(?m)^paths\s*:", front) else "상시"
            out.append((p.relative_to(base).as_posix(), p, kind))
    if (base / "skills").is_dir():
        for p in sorted((base / "skills").glob("*/SKILL.md")):
            out.append((p.relative_to(base).as_posix(), p, "스킬"))
    return out


def user_layer_files():
    """사용자 층(`~/.claude/rules/*.md`) → [(이름, 크기)]. 없으면 빈 목록.

    ★ **소계에도 래칫에도 안 넣는다 — 보이기만 한다**(2026-09-12, Codex 검토 F07).
      이 파일들은 매 세션 실리는데 이 자는 프로젝트 것만 세면서 출력 머리에
      *[발화 생략]* 이라고 적어, 읽는 사람이 그 수를 전체로 읽었다.
      **기준선에 넣지 않는 이유**: 리포가 고칠 수 없는 남의 파일이라(규칙 5) 래칫에 넣으면
      우리가 안 건드린 변경으로 기준선이 깨진다. 읽기만 한다 — 쓰지 않는다.
    못 보는 것: 메모리 색인 · 스킬 description · 하네스가 붙이는 문맥.
    """
    base = Path.home() / ".claude" / "rules"
    if not base.is_dir():
        return []
    return [("~/.claude/rules/" + p.name, measure(p)) for p in sorted(base.glob("*.md"))]


def measure(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "lines": len(text.splitlines()),
        "chars": len(text),
        "bytes": len(text.encode("utf-8")),
    }


def read_baseline(path):
    """`{이름: 줄수}`. `이름 | 줄 | 잰 날` 형식. 사유 칸은 요구하지 않는다 —
    ★ 이건 **예외 대장이 아니라 기준선**이다(`수치-근거-기준선.txt` 와 같은 판정)."""
    out = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and parts[1].isdigit():
            out[parts[0]] = int(parts[1])
    return out


HEADER_MARKS = ("세션에 실리는 지침의 크기 기준선", "형식: <파일 이름>", "래칫이다")


def kept_notes(path):
    """기준선 파일에서 **사람이 손으로 적은 주석**만 돌려준다 — 세 줄짜리 머리말은 뺀다.

    `--accept` 는 파일을 통째로 다시 쓴다. 그래서 *[발화 생략]* 같은
    판정을 적어 두면 다음 `--accept` 가 말없이 지웠다(2026-08-23). 사유가 사라지면
    같은 줄이 다시 들어오는 것을 아무도 못 막는다.
    """
    if not path.is_file():
        return []
    out = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        if line.startswith("#") and not any(mark in line for mark in HEADER_MARKS):
            out.append(line)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", default=".")
    ap.add_argument("--accept", action="store_true", help="지금 크기를 기준선으로 받는다")
    ap.add_argument("--accept-new", action="store_true",
                    help="기준선에 **없던 파일**까지 넣는다(갈래 고유 지침이 섞이는 자리라 손을 받는다)")
    a = ap.parse_args()
    today = datetime.date.today().isoformat()

    root = Path(a.project).resolve()
    files = loaded_files(root)
    if not files:
        print("[지침 크기] %s — `CLAUDE.md` 가 없다. 세션에 실리는 지침이 0이다" % root.name)
        return 0

    base_path = baseline_path(root)
    base = read_baseline(base_path)
    total = {"lines": 0, "chars": 0, "bytes": 0}
    rows, grown = [], []

    entries = [(f.name, f, "시작") for f in files] + scoped_files(root)
    kinds = {}
    for name, f, kind in entries:
        m = measure(f)
        kinds[name] = kind
        if kind in ("시작", "상시"):
            for k in total:
                total[k] += m[k]
        was = base.get(name)
        delta = "" if was is None else ("  기준선 %d → **+%d**" % (was, m["lines"] - was)
                                        if m["lines"] > was else
                                        "  기준선 %d (그대로)" % was if m["lines"] == was else
                                        "  기준선 %d → %d (줄었다)" % (was, m["lines"]))
        if was is not None and m["lines"] > was:
            grown.append((name, was, m["lines"]))
        rows.append((name, m, delta if was is not None else "  (기준선 없음)"))

    always = [r for r in rows if kinds[r[0]] in ("시작", "상시")]
    print("[지침 크기] %s — **프로젝트** 정적 지침 %d개" % (root.name, len(always)))
    for name, m, delta in always:
        print("  %-22s %6d줄 · %7d글자 · %4dKB%s"
              % (name, m["lines"], m["chars"], m["bytes"] // 1024, delta))
    print("  %-22s %6d줄 · %7d글자 · %4dKB"
          % ("소계(프로젝트)", total["lines"], total["chars"], total["bytes"] // 1024))
    scoped = [r for r in rows if kinds[r[0]] not in ("시작", "상시")]
    if scoped:
        print("  조건부로 실리는 것 %d개 (소계에 안 넣는다)" % len(scoped))
        for name, m, delta in scoped:
            print("  %-32s %s %5d줄%s" % (name, kinds[name], m["lines"], delta))
    for name, m in user_layer_files():
        print("  %-32s %s %5d줄 · %6d글자" % (name, "사용자층", m["lines"], m["chars"]))
    print("  ※ 위 소계는 **이 리포가 고칠 수 있는 것**만이다 — 사용자 층(`~/.claude/rules`)도")
    print("     매 세션 실리지만 리포 밖이라 래칫에 넣지 않는다(규칙 5). 못 세는 것: 메모리 색인 ·")
    print("     스킬 description · 하네스 문맥. 토큰은 `messages.count_tokens` 가 정본이다")

    if a.accept:
        # ★★ **파일 집합이 바뀌면 덮기 전에 보여 준다** (2026-08-16, 전공정리 되먹임).
        #   기준선은 **한 파일**인데 실리는 지침은 **선 자리마다 다르다** — 갈래(브랜치)별
        #   지침이 있는 리포에서 갈래 안에서 `--accept` 하면, 그 갈래에만 있는 파일이
        #   **공통 기준선에 섞여 다른 갈래를 덮는다.** 기계가 「이건 갈래 고유다」를 알 길은
        #   없으므로(그걸 알면 공통 도구에 그 리포 사실을 박는 것이다) **집합의 변화만**
        #   찍고 판정은 사람에게 남긴다.
        added = [n for n, _, _ in rows if n not in base]
        gone = [n for n in base if n not in {n2 for n2, _, _ in rows}]
        # ★★ **찍고 나서 그대로 쓰던 자리다** (2026-08-23, 전공정리 실측). 위 경고를 낸
        #   바로 다음 줄에서 새 파일을 기준선에 **넣어 버렸다** — 열역학 갈래에서 한 번
        #   `--accept` 하니 `SUBJECT.md | 46` 이 공통 기준선에 박혔고, 그 파일은 갈래마다
        #   내용이 달라 다른 과목이 받으면 남의 값으로 재게 된다. 재는 자만 있고 막는 자가
        #   없으면 숫자가 나와도 아무 일도 안 일어난다(AGENTS 실행 규율 17).
        #   → **기존 항목의 갱신은 그냥 하고, 「집합에 넣는 것」만 사람 손을 받는다.**
        write_rows = rows if (a.accept_new or not base) else [r for r in rows if r[0] in base]
        if base and (added or gone):
            print("\n  ★ 기준선의 **파일 집합이 바뀐다** — 받기 전에 볼 것")
            for n in added:
                print("      + %s  (전에 없던 것%s)"
                      % (n, "" if a.accept_new else " — **이번에는 안 넣었다**"))
            for n in gone:
                print("      - %s  (이번에 안 실렸다%s)"
                      % (n, "" if a.accept_new else " — 줄은 그대로 둔다"))
            print("      갈래마다 다른 지침이 섞였다면 **공통 자리에 기준선을 두지 말 것** —"
                  " 한 갈래의 값이 다른 갈래를 덮는다")
            if not a.accept_new:
                print("      정말 공통에 넣을 것이면 `--accept --accept-new`")
        for n in base:                       # 안 실린 것의 줄은 지우지 않는다(다른 갈래의 것일 수 있다)
            if n not in {n2 for n2, _, _ in write_rows}:
                write_rows = write_rows + [(n, {"lines": base[n]}, "")]
        # ★ 주석은 **열기 전에** 읽는다 — `open(…, "w")` 가 파일을 먼저 비우므로 블록
        #   안에서 읽으면 빈 파일을 읽고 사유가 그대로 날아간다(2026-08-23 실측: 한 번 날렸다).
        notes = kept_notes(base_path)
        base_path.parent.mkdir(parents=True, exist_ok=True)
        with open(base_path, "w", encoding="utf-8", newline="") as fh:
            fh.write("# 세션에 실리는 지침의 크기 기준선 — `도구/audit_guide_size.py` 가 읽는다.\n")
            fh.write("# 형식: <파일 이름> | <줄> | <잰 날>\n")
            fh.write("# ★ 래칫이다 — 늘면 신고하고 줄면 조용하다. **막지는 않는다.**\n")
            for note in notes:                   # 사람이 적어 둔 사유를 덮어쓰지 않는다
                fh.write(note + "\n")
            for name, m, _ in sorted(write_rows):
                fh.write("%s | %d | %s\n" % (name, m["lines"], today))
        print("\n[기준선] %s 에 %d개를 받았다" % (base_path, len(write_rows)))
        return 0

    if grown:
        print("\n  ★ 기준선보다 자란 것 %d개 — **판정은 사람이 한다**" % len(grown))
        for name, was, now in grown:
            print("      %-22s %d → %d줄 (+%d)" % (name, was, now, now - was))
        print("  자란 것이 정당하면 `--accept` 로 기준선을 옮긴다."
              " 정당하지 않으면 **실리지 않는 자리**(`docs/**`·독스트링)로 옮긴다.")
    elif base:
        print("\n  · 기준선 이하 — 자란 것 없음")
    else:
        print("\n  · 기준선이 없다 — `--accept` 로 지금 크기를 받아 두면 다음부터 증감이 보인다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
