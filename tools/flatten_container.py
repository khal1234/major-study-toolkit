# -*- coding: utf-8 -*-
"""평탄화 — `<컨테이너>/main/` 을 컨테이너 루트로 꺼낸다 (2026-09-07).

파일 이동만 한다. git 재배선(core.bare · worktree prune · index)은 이 스크립트 밖에서
사람이 부르는 명령으로 한다 — 되돌릴 수 없는 조작을 한 스크립트에 몰지 않는다.

★ 이 세션의 훅은 **옛 경로**(`main/.claude/hooks/…`)로 이미 배선돼 있다. 옮긴 뒤 그 파일이
  사라지면 python 이 exit 2 로 죽고, PreToolUse 훅의 exit 2 는 **도구 호출을 막는다** —
  이 세션이 통째로 잠긴다. 그래서 `main/` 아래에 **전달 스텁**을 남긴다. 스텁은
  `runpy.run_path(진짜, run_name="__main__")` 라서 진짜 파일이 자기 경로로 `__file__` 을
  받는다(훅들이 리포 루트를 `__file__` 로 계산하므로 사본·정션으로는 안 된다).
  스텁은 **다음 세션이 훅 발화를 눈으로 확인한 뒤 `main/` 을 통째로 지우면 끝난다.**

★ 그 거두는 일도 **이 도구가 한다** — `python tools/flatten_container.py --drop-stubs`
  (2026-09-07, 사용자 «메인 지우자»). 만든 자가 거두게 두는 이유는 둘이다:
  ⑴ `rm -rf` 는 settings 의 `deny` 다(범위를 손으로 적는 삭제를 이 리포는 금지한다)
  ⑵ **스텁이 아닌 파일이 하나라도 섞여 있으면 지우면 안 된다** — 사람이 눈으로 세는 대신
     전 파일이 스텁 표식을 갖는지 확인하고, 아니면 그 경로를 찍고 exit 1 로 멈춘다.
  실사고 예방: 이 폴더가 죽은 채 남아 **작업 스케줄러 등록이 그 경로를 가리키고 있었다**
  (2026-09-07, 로그온해도 8800 이 안 떴다 — `install_startup.ps1` 주석의 실측).
"""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"C:\Users\<사용자>\Documents\전공정리프로젝트"
MAIN = os.path.join(ROOT, "main")
BACKUP = os.path.dirname(os.path.abspath(__file__))
STUB_MARK = "전달 스텁 (2026-09-07 평탄화)"


def drop_stubs():
    """`main/` 을 지운다 — **전부 스텁일 때만.** (경로 목록, 지웠나)"""
    if not os.path.isdir(MAIN):
        print("[해당 없음] main/ 이 이미 없다 — 0건")
        return [], False
    intruders = []
    for base, _dirs, files in os.walk(MAIN):
        for f in files:
            p = os.path.join(base, f)
            try:
                with open(p, encoding="utf-8") as fh:
                    ok = STUB_MARK in fh.read(600)
            except (OSError, UnicodeDecodeError):
                ok = False
            if not ok:
                intruders.append(os.path.relpath(p, ROOT))
    if intruders:
        return intruders, False
    shutil.rmtree(MAIN)
    return [], True


if "--drop-stubs" in sys.argv:
    bad, done = drop_stubs()
    if bad:
        print("스텁이 아닌 파일이 %d개 있다 — 지우지 않았다. 사람이 볼 것:" % len(bad),
              file=sys.stderr)
        for p in bad[:20]:
            print("  " + p, file=sys.stderr)
        sys.exit(1)
    if done:
        print("[삭제] main/ — 전달 스텁만 있었다")
        print("       .gitignore 의 «/main/» 세 줄도 함께 지울 것(그 주석이 한시적이라 적혀 있다)")
    sys.exit(0)

moved, skipped = [], []


def merge_into(src_dir, dst_dir):
    """src_dir 의 항목을 dst_dir 로 옮긴다. 이름이 이미 있으면 건너뛴다(덮지 않는다)."""
    os.makedirs(dst_dir, exist_ok=True)
    for name in sorted(os.listdir(src_dir)):
        src, dst = os.path.join(src_dir, name), os.path.join(dst_dir, name)
        if os.path.exists(dst):
            skipped.append(os.path.relpath(src, ROOT) + " (루트에 같은 이름이 이미 있다)")
            continue
        shutil.move(src, dst)
        moved.append(os.path.relpath(dst, ROOT))


# ── 0. 되돌릴 수 없게 되기 전에 컨테이너 루트의 미추적 설정을 스크래치패드로 뜬다
for name in ("settings.json", "settings.local.json"):
    p = os.path.join(ROOT, ".claude", name)
    if os.path.isfile(p):
        shutil.copy2(p, os.path.join(BACKUP, "container-" + name))
        print("[백업] .claude/" + name)

# ── 1. 컨테이너의 파생 settings.json 을 치운다 (추적본이 그 자리에 온다)
derived = os.path.join(ROOT, ".claude", "settings.json")
if os.path.isfile(derived):
    with open(derived, encoding="utf-8") as fh:
        if "sync_common.mirror_container_root() 가 만든다" not in fh.read():
            sys.exit("컨테이너 .claude/settings.json 이 파생물 표식을 안 갖고 있다 — 손으로 볼 것")
    os.remove(derived)
    print("[삭제] 파생 .claude/settings.json (백업 있음)")

wt = os.path.join(ROOT, ".claude", "worktrees")
if os.path.isdir(wt) and not os.listdir(wt):
    os.rmdir(wt)
    print("[삭제] 빈 .claude/worktrees/")

# ── 2. main/.claude → 루트 .claude (루트의 settings.local.json 은 그대로 둔다: 상위집합)
merge_into(os.path.join(MAIN, ".claude"), os.path.join(ROOT, ".claude"))

# ── 3. main/.netlify → 루트 .netlify (Netlify 는 은퇴했다 · 생성물이라 겹치면 건너뛴다)
if os.path.isdir(os.path.join(MAIN, ".netlify")):
    merge_into(os.path.join(MAIN, ".netlify"), os.path.join(ROOT, ".netlify"))
    if not os.listdir(os.path.join(MAIN, ".netlify")):
        os.rmdir(os.path.join(MAIN, ".netlify"))

# ── 4. 나머지 전부 (main/.git 은 워크트리 포인터라 버린다)
for name in sorted(os.listdir(MAIN)):
    if name in (".claude", ".netlify"):
        continue
    src = os.path.join(MAIN, name)
    if name == ".git":
        (os.remove if os.path.isfile(src) else shutil.rmtree)(src)
        print("[삭제] main/.git (워크트리 포인터)")
        continue
    dst = os.path.join(ROOT, name)
    if os.path.exists(dst):
        skipped.append(name + " (루트에 같은 이름이 이미 있다)")
        continue
    shutil.move(src, dst)
    moved.append(name)

# ── 5. 이 세션용 전달 스텁 — 옛 settings.json 이 부르던 경로만
STUB = '''# -*- coding: utf-8 -*-
"""전달 스텁 (2026-09-07 평탄화) — 진짜 파일은 %s 다.

옛 세션의 settings.json 이 이 경로를 부르고 있어서 남긴다. **다음 세션이 훅 발화를 눈으로
확인한 뒤 `main/` 을 통째로 지우면 끝난다.**
"""
import os
import runpy

runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), %r),
               run_name="__main__")
'''

stub_targets = []
for sub in (os.path.join(".claude", "hooks"), "tools"):
    real_dir = os.path.join(ROOT, sub)
    if os.path.isdir(real_dir):
        stub_targets += [(sub, f) for f in sorted(os.listdir(real_dir)) if f.endswith(".py")]

for sub, fname in stub_targets:
    stub_dir = os.path.join(MAIN, sub)
    os.makedirs(stub_dir, exist_ok=True)
    up = os.path.join(*([".."] * (2 + sub.count(os.sep))))
    rel = os.path.join(up, sub, fname)
    with open(os.path.join(stub_dir, fname), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(STUB % (sub + "/" + fname, rel))
print("[스텁] %d개 — main/.claude/hooks · main/tools" % len(stub_targets))

# ── 6. 컨테이너 settings.local.json 의 `main/` 경로를 걷어낸다
loc = os.path.join(ROOT, ".claude", "settings.local.json")
if os.path.isfile(loc):
    with open(loc, encoding="utf-8") as fh:
        txt = fh.read()
    new = txt.replace("main/tools/", "tools/").replace("main/.claude/", ".claude/")
    if new != txt:
        with open(loc, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new)
        print("[고침] .claude/settings.local.json — main/ 접두 제거")

print("\n[옮김] %d개: %s" % (len(moved), ", ".join(moved[:40])))
if skipped:
    print("[건너뜀] " + " · ".join(skipped))
print("[남은 main/] " + ", ".join(sorted(os.listdir(MAIN))))
