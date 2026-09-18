"""setup — 이 툴킷을 받은 뒤 한 번 돌리는 설치 도우미.

하는 일(고른 것만):
  --rules    system/rules/*.md  → ~/.claude/rules/   (Claude Code 가 매 세션 싣는 공통 판정선)
  --skills   system/skills/*    → ~/.claude/skills/  (범용 스킬 20개)
  --codex    system/rules/*.md  → ~/.codex/AGENTS.md 끝에 붙인다(Codex 전역 지침)
  --subject  첫 과목을 만든다   (data/<과목>/SUBJECT.md + 빌드 등록 + 교재 폴더를 settings 에 연결)

인자 없이 돌리면 **무엇을 할지 보여 주기만** 한다. 이미 있는 파일은 덮지 않는다 —
`--force` 를 주면 덮기 전에 `<이름>.bak` 으로 남긴다.

예:
  python setup.py --rules --skills
  python setup.py --subject 동역학 --slug dynamics --textbook-dir "D:/교재/동역학"
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
HOME = Path.home()


def place(src: Path, dst: Path, force: bool, dry: bool) -> str:
    if dst.exists() and not force:
        return f"  건너뜀(이미 있음) {dst}"
    if dry:
        return f"  놓을 것 {dst}"
    if dst.exists():
        bak = dst.with_name(dst.name + ".bak")
        if dst.is_dir():
            shutil.copytree(dst, bak, dirs_exist_ok=True)
        else:
            shutil.copy2(dst, bak)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)
    return f"  놓음 {dst}"


def rules(force: bool, dry: bool) -> None:
    print("[rules] ~/.claude/rules")
    for f in sorted((ROOT / "system/rules").glob("*.md")):
        print(place(f, HOME / ".claude/rules" / f.name, force, dry))


def skills(force: bool, dry: bool) -> None:
    print("[skills] ~/.claude/skills")
    for d in sorted(p for p in (ROOT / "system/skills").iterdir() if p.is_dir()):
        print(place(d, HOME / ".claude/skills" / d.name, force, dry))


def codex(dry: bool) -> None:
    dst = HOME / ".codex/AGENTS.md"
    body = "\n\n".join(f.read_text(encoding="utf-8") for f in sorted((ROOT / "system/rules").glob("*.md")))
    marker = "<!-- major-study-toolkit:rules -->"
    have = dst.read_text(encoding="utf-8") if dst.exists() else ""
    print("[codex]", dst)
    if marker in have:
        print("  건너뜀(이미 붙어 있음)")
        return
    if dry:
        print("  붙일 것: system/rules 전문")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(have + ("\n\n" if have else "") + marker + "\n" + body, encoding="utf-8")
    print("  붙임")


def subject(name: str, slug: str, port: int, book: str | None, textbook_dir: str | None, dry: bool) -> None:
    print(f"[subject] {name}")
    sub = ROOT / "data" / name / "SUBJECT.md"
    if sub.exists():
        print("  건너뜀(이미 있음)", sub)
    elif dry:
        print("  만들 것", sub)
    else:
        sub.parent.mkdir(parents=True, exist_ok=True)
        tpl = (ROOT / ".claude/SUBJECT.md.template").read_text(encoding="utf-8")
        sub.write_text(tpl.replace("<과목명>", name).replace("<과목>", name), encoding="utf-8")
        print("  만듦", sub, "— 교재·지문 언어 칸을 채운다")
    cmd = [sys.executable, str(ROOT / "tools/new_subject.py"), "register",
           "--subject", name, "--branch", slug, "--port", str(port)]
    if book:
        cmd += ["--pitfall-book", book]
    print("  빌드 등록:", " ".join(cmd[1:]))
    if not dry:
        subprocess.run(cmd, check=True, cwd=ROOT)
    if textbook_dir:
        sp = ROOT / ".claude/settings.json"
        s = json.loads(sp.read_text(encoding="utf-8"))
        p = s["permissions"]
        tb = str(Path(textbook_dir).resolve()).replace("\\", "/")
        p["additionalDirectories"] = [d for d in p.get("additionalDirectories", []) if not d.startswith("<")] + [tb]
        p["deny"] = [d for d in p["deny"] if "<교재" not in d] + [f"Edit({tb}/**)", f"Write({tb}/**)"]
        print(f"  교재 폴더 연결(읽기만): {tb}")
        if not dry:
            sp.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rules", action="store_true")
    ap.add_argument("--skills", action="store_true")
    ap.add_argument("--codex", action="store_true")
    ap.add_argument("--subject", help="과목 이름(한글 가능). 예: 동역학")
    ap.add_argument("--slug", help="과목의 영문 짧은 이름. 예: dynamics")
    ap.add_argument("--port", type=int, default=8801, help="로컬 미리보기 포트(과목마다 다르게)")
    ap.add_argument("--pitfall-book", help='pitfall 근거 접두어. 예: "Hibbeler 본문 경고"')
    ap.add_argument("--textbook-dir", help="교재 PDF 폴더 — 에이전트가 읽기만 하게 연결한다")
    ap.add_argument("--force", action="store_true", help="이미 있는 파일도 덮는다(.bak 을 남긴다)")
    a = ap.parse_args()
    dry = not (a.rules or a.skills or a.codex or a.subject)
    if dry:
        print("고른 것이 없어 보여 주기만 한다 — 실제로 하려면 --rules / --skills / --codex / --subject\n")
    if a.rules or dry:
        rules(a.force, dry)
    if a.skills or dry:
        skills(a.force, dry)
    if a.codex or dry:
        codex(dry)
    if a.subject:
        if not a.slug:
            ap.error("--subject 에는 --slug(영문 짧은 이름)가 함께 필요하다")
        subject(a.subject, a.slug, a.port, a.pitfall_book, a.textbook_dir, False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
