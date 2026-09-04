"""저장소 전체를 **파일 하나**로 말아 백업한다 (2026-08-02 신설).

사용자: [사용자 발화 인용 생략]

★ **동기화 폴더 안에 작업 저장소를 두면 안 된다 — 충돌이 아니라 손상 위험이다.**
  Drive·OneDrive·Dropbox 는 파일 단위로 실시간 업로드하는데, git 은 작업할 때마다
  `.git/index`·`index.lock`·refs·packfile 을 계속 고쳐 쓴다. 동기화 클라이언트가 그 쓰기
  도중에 올리고, 충돌이 나면 **`.git/` 안에 사본 파일을 만들어 넣는다.** git 은 그걸
  쓰레기 ref/object 로 읽는다. 여기는 워크트리가 11개(=bare + 과목 6 + 임시)라 더 나쁘고,
  `site/<과목>/*.html` 은 빌드마다 통째로 다시 써서 감시 대상이 계속 흔들린다.
  → **폴더를 동기화하지 말고, 스냅샷 하나를 주기적으로 던져 넣는다.**

무엇이 들어가나:
  ⑴ `git bundle --all` — **모든 브랜치·태그의 전체 이력**이 파일 하나. 복원은 clone 한 줄.
  ⑵ **`.review-snapshot/`** — 검수 기준선. `.gitignore` 가 막고 있어 ⑴에 안 들어가는데,
     잃으면 변경점 하이라이트가 통째로 리셋된다(사용자가 '변경된 것만' 보는 방식이라 치명적).
  ⑶ 각 워크트리의 `.claude/settings.local.json` — 로컬 권한 설정.
  넣지 않는 것: `site/`(빌드 산출) · `review-artifacts/`(재생성) · 교재 지문(재생성) ·
  교재 PDF(애초에 리포 밖이고 `.gitignore` 가 막는다 — 그건 따로 관리할 몫이다).

★ **검증 없는 백업은 백업이 아니다.** 이 도구는 만든 bundle 을 실제로 **임시 clone 해 보고**
  브랜치 수가 원본과 같은지 대조한다. 통과하지 못하면 목적지에 아무것도 쓰지 않는다
  (AGENTS 규칙 11 — 판정은 명령으로 뒷받침한다).

쓰는 법:
    python tools/backup_bundle.py --set-dest "<백업 위치>/backup/<프로젝트>"
    python tools/backup_bundle.py                  # 위에서 정한 곳으로
    python tools/backup_bundle.py --dry-run        # 목적지에 쓰지 않고 검증까지만
    python tools/backup_bundle.py --keep 30        # 남길 세대 수 (기본 20)

목적지는 `backup-dest.txt`(리포 루트, `.gitignore` 대상)에 둔다 — **기계마다 다른 사실**이라
공통 코드에 박지 않는다(AGENTS 「공통 도구에 과목별·기계별 사실을 박지 않는다」).
"""
import argparse
import datetime
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# stderr 도 함께 — 안 하면 예외 역추적의 한글 경로가 cp949 로 깨져 나온다(실측).
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def rmtree(path):
    """★ Windows 에서 git 객체는 **읽기 전용**이라 그냥 rmtree 하면 남는다.

    `ignore_errors=True` 로 덮으면 조용히 실패하고, 다음 실행에서
    `destination path already exists` 로 터진다(실측 — 이 도구 첫 실행에서 그랬다).
    권한을 풀고 다시 지운다.
    """
    def force(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)
    if os.path.exists(path):
        shutil.rmtree(path, onexc=force)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST_FILE = os.path.join(ROOT, "backup-dest.txt")
STAGING = os.path.join(ROOT, ".backup-staging")
KEEP_DEFAULT = 20
# 파일 이름의 앞머리. 세대 정리가 **이 접두어를 가진 것만** 지우게 하는 안전장치이기도 하다 —
# 목적지 폴더에 사용자의 다른 파일이 있어도 건드리지 않는다.
PREFIX = "repo-backup-"
STAMP_RE = re.compile(re.escape(PREFIX) + r"\d{8}-\d{6}\.zip$")


def git(*args, cwd=None):
    """git 을 subprocess 로 돌린다 — 출력은 UTF-8 로 명시해 읽는다(Windows 기본은 cp949)."""
    out = subprocess.run(("git",) + args, cwd=cwd or ROOT, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError("git " + " ".join(args) + " 실패:\n" + (out.stderr or out.stdout))
    return out.stdout


def resolve_dest():
    """백업 목적지 — **저장소 전체가 하나로 공유한다.**

    ★ 열린 날 2026-08-02 (사용자: [사용자 발화 인용 생략]).
      처음엔 워크트리 루트의 `backup-dest.txt`(`.gitignore` 대상)에 뒀다. 그런데 이 백업은
      **저장소 전체**(모든 브랜치 + 모든 워크트리의 검수 기준선)를 담는다 — 즉 목적지는
      과목마다 다를 이유가 없는 값인데, 파일을 워크트리 안에 두는 바람에 **정한 과목에만 있고
      나머지 과목에서는 계속 '미설정'** 으로 떴다. 설정의 **범위**를 잘못 잡은 것이다.
      → git 의 로컬 설정에 둔다. 워크트리들은 `.bare/config` 를 **공유**하므로 한 번만 정하면 된다.
      (커밋되지 않으므로 기계별 값이라는 성질도 그대로다.)

    `backup-dest.txt` 는 **읽기만** 남긴다 — 예전에 정해 둔 기계가 조용히 망가지지 않게.
    """
    try:
        dest = git("config", "--get", "backup.dest").strip()
        if dest:
            return dest
    except RuntimeError:
        pass                              # 설정이 없으면 git 이 exit 1 — 정상 흐름이다
    if os.path.exists(DEST_FILE):
        with open(DEST_FILE, encoding="utf-8") as fh:
            return fh.read().strip() or None
    return None


def worktree_paths():
    """`git worktree list` 로 실제 워크트리 경로를 읽는다 — 과목 이름을 박지 않는다."""
    paths = []
    for line in git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            paths.append(line[len("worktree "):].strip())
    return paths


def dirty_worktrees():
    """★ **bundle 은 커밋만 담는다 — 커밋 안 된 작업은 백업되지 않는다.**

    이걸 안 알리면 '백업 성공' 을 보고 안심하는데 다른 과목 세션의 미커밋 작업이 통째로
    빠져 있을 수 있다. 백업이 못 담는 것을 **백업할 때 말해 주는 것**이 이 함수의 몫이다
    (막지는 않는다 — 커밋 여부는 그 과목 세션이 정할 일이다).
    """
    out = []
    for wt in worktree_paths():
        if not os.path.isdir(wt):
            continue
        try:
            changed = [l for l in git("status", "--porcelain", cwd=wt).splitlines() if l.strip()]
        except RuntimeError:
            continue
        if changed:
            out.append((os.path.basename(wt.rstrip("/\\")) or wt, len(changed)))
    return out


def collect_extras():
    """git 이 안 담는 것들 — (zip 안 경로, 실제 경로) 목록. 순수 수집만 한다."""
    extras = []
    for wt in worktree_paths():
        if not os.path.isdir(wt):
            continue
        label = os.path.basename(wt.rstrip("/\\")) or "root"
        data_dir = os.path.join(wt, "data")
        if os.path.isdir(data_dir):
            for subject in sorted(os.listdir(data_dir)):
                snap = os.path.join(data_dir, subject, ".review-snapshot")
                if not os.path.isdir(snap):
                    continue
                for fn in sorted(os.listdir(snap)):
                    src = os.path.join(snap, fn)
                    if os.path.isfile(src):
                        extras.append((
                            "/".join(("worktrees", label, "review-snapshot", subject, fn)), src))
        local = os.path.join(wt, ".claude", "settings.local.json")
        if os.path.isfile(local):
            extras.append(("/".join(("worktrees", label, "settings.local.json")), local))
    return extras


def verify_bundle(bundle, expect_heads):
    """★ 만든 bundle 을 **실제로 clone 해 본다.**

    `git bundle verify` 는 '적용 가능한가'만 본다. 우리가 알고 싶은 것은 *복원했을 때 브랜치가
    다 살아 있는가* 이므로 임시 clone 까지 간다 — 백업은 복원해 봐야 백업이다.
    """
    git("bundle", "verify", bundle)
    probe = os.path.join(STAGING, "verify-clone")
    rmtree(probe)
    git("clone", "--bare", "--quiet", bundle, probe)
    heads = [l.split()[-1] for l in git("branch", "-a", cwd=probe).splitlines() if l.strip()]
    rmtree(probe)
    missing = sorted(set(expect_heads) - {h.replace("remotes/origin/", "") for h in heads})
    return sorted(heads), missing


def prune(dest, keep):
    """접두어가 맞는 우리 백업만 세대 정리한다 — 남의 파일은 건드리지 않는다."""
    mine = sorted(f for f in os.listdir(dest) if STAMP_RE.search(f))
    dropped = mine[:-keep] if keep > 0 and len(mine) > keep else []
    for fn in dropped:
        os.remove(os.path.join(dest, fn))
    return len(mine) - len(dropped), dropped


def backup_files(dest):
    """목적지의 백업 zip 을 **최신순**으로. 이름 규약(PREFIX+타임스탬프)에 맞는 것만 본다."""
    if not dest or not os.path.isdir(dest):
        return []
    names = [n for n in os.listdir(dest) if STAMP_RE.search(n)]
    return [os.path.join(dest, n) for n in sorted(names, reverse=True)]


def snapshot_entries(zip_path):
    """zip 안의 (과목, 파일명, 엔트리 이름) — **이 워크트리의 라벨**에 해당하는 것만.

    ★ 이름을 UTF-8 로 읽는다. 이 도구가 쓸 때 Python 이 UTF-8 플래그를 세우므로 그대로 읽히지만,
      플래그가 없는 zip(다른 도구가 만든 것)은 cp437 로 디코드돼 한글이 깨진다 — 그 경우만 되돌린다.
      (AGENTS 「바깥에서 들어오는 텍스트는 무조건 UTF-8」의 zip 판이다.)
    """
    label = os.path.basename(ROOT.rstrip("/\\")) or "root"
    prefix = "worktrees/" + label + "/review-snapshot/"
    out = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename
            if not (info.flag_bits & 0x800):
                try:
                    name = name.encode("cp437").decode("utf-8")
                except (UnicodeDecodeError, UnicodeEncodeError):
                    pass
            if not name.startswith(prefix) or name.endswith("/"):
                continue
            rest = name[len(prefix):].split("/")
            if len(rest) == 2:
                out.append((rest[0], rest[1], info.filename))
    return out


def restore_snapshots(zip_path, dry_run=False, chapter=None):
    """백업 zip 에서 **이 워크트리 과목의 검수 기준선**을 되돌린다.

    ★ 왜 도구인가 (열린 날 2026-08-02 · 원장 23번). 기준선은 `.gitignore` 밖이라 **백업이
      유일한 사본**인데, 되돌리는 방법이 `unzip … -d <경로>` 라는 **셸 한 줄**뿐이었다.
      그건 ⑴ 매번 승인창을 띄우고 ⑵ 임의 경로에 쓰는 명령이라 규칙 9 의 경계를 셸에서 연다.
      여기서는 **쓰는 위치가 코드에 고정**돼 있다 — `data/<과목>/.review-snapshot/` 밖으로는 못 쓴다.

    실제로 이걸 만든 계기: `--accept-review-head` 가 `--accept-review-only` 를 조용히 무시해
    ch02 의 '아직 안 본 문풀 이후' 기준선까지 날아갔고, 되돌릴 길이 백업뿐이었다.
    """
    entries = snapshot_entries(zip_path)
    if chapter:
        # ★ 챕터를 한정할 수 있어야 한다 — 복원도 수락과 같은 위험을 진다.
        #   전체 복원은 **방금 정당하게 초기화한 다른 챕터의 기준선까지 되돌린다**
        #   (실측: ch02 를 되살리려다 사용자가 방금 초기화한 ch01 을 함께 되돌릴 뻔했다).
        entries = [e for e in entries if os.path.splitext(e[1])[0] == chapter]
    if not entries:
        print("이 워크트리(" + os.path.basename(ROOT) + ")의 기준선이 백업에 없다: "
              + os.path.basename(zip_path))
        return 1
    written = 0
    with zipfile.ZipFile(zip_path) as zf:
        for subject, filename, arcname in sorted(entries):
            data_dir = os.path.join(ROOT, "data", subject)
            if not os.path.isdir(data_dir):
                print("  건너뜀 — 이 워크트리에 없는 과목: " + subject)
                continue
            target = os.path.join(data_dir, ".review-snapshot", filename)
            payload = zf.read(arcname)
            same = (os.path.isfile(target)
                    and open(target, "rb").read() == payload)
            mark = "같음" if same else ("덮어씀" if os.path.isfile(target) else "새로 만듦")
            print(("  [dry-run] " if dry_run else "  ") + subject + "/" + filename
                  + " — " + mark)
            if dry_run or same:
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as fh:
                fh.write(payload)
            written += 1
    print(("복원할 파일 " if dry_run else "복원한 파일 ") + str(written if not dry_run
                                                          else len(entries)) + "개"
          + (" (dry-run — 쓰지 않았다)" if dry_run else ""))
    if not dry_run:
        print("확인: python tools/build_review.py --all  ← 하이라이트 수가 되돌아왔는지 본다")
    return 0


def main():
    ap = argparse.ArgumentParser(description="저장소 전체를 파일 하나로 백업한다")
    ap.add_argument("--set-dest", help="백업을 넣을 폴더를 기억시킨다(그리고 종료)")
    ap.add_argument("--dest", help="이번만 쓸 목적지 폴더")
    ap.add_argument("--keep", type=int, default=KEEP_DEFAULT, help="남길 세대 수 (기본 20)")
    ap.add_argument("--dry-run", action="store_true",
                    help="목적지에 쓰지 않고 만들기·검증까지만 한다")
    ap.add_argument("--restore-snapshots", action="store_true",
                    help="백업에서 이 워크트리 과목의 검수 기준선(.review-snapshot)을 되돌린다")
    ap.add_argument("--from", dest="from_zip",
                    help="복원에 쓸 백업 zip (기본: 목적지의 가장 최근 것)")
    ap.add_argument("--list", action="store_true", help="목적지의 백업 세대를 최신순으로 보여준다")
    ap.add_argument("--chapter", help="복원을 그 챕터에만 적용한다 (예: ch02)")
    args = ap.parse_args()

    if args.list or args.restore_snapshots:
        dest = args.dest or resolve_dest()
        files = backup_files(dest)
        if args.list:
            print("백업 목적지: " + str(dest))
            for path in files:
                print("  " + os.path.basename(path))
            print("총 " + str(len(files)) + "세대")
            return 0
        zip_path = args.from_zip or (files[0] if files else None)
        if not zip_path or not os.path.isfile(zip_path):
            print("복원할 백업을 못 찾았다. `--list` 로 세대를 보거나 `--from=<zip>` 을 줄 것.")
            return 1
        print("복원 원본: " + os.path.basename(zip_path))
        return restore_snapshots(zip_path, dry_run=args.dry_run, chapter=args.chapter)

    if args.set_dest:
        dest = os.path.abspath(os.path.expanduser(args.set_dest))
        # `--local` 은 워크트리들이 **공유하는** 설정(.bare/config)에 쓴다 —
        # 한 번 정하면 모든 과목 세션이 같은 값을 본다(resolve_dest 주석이 경위의 정본).
        git("config", "--local", "backup.dest", dest)
        print("목적지 기억함 → " + dest)
        print("(git 로컬 설정 `backup.dest` — 워크트리 공유이고 커밋되지 않는다.")
        print(" 모든 과목 세션이 같은 값을 보므로 과목마다 다시 정할 필요가 없다.)")
        return 0

    dest = args.dest or resolve_dest()
    if not dest and not args.dry_run:
        print("목적지가 없다. 먼저 한 번 정할 것:")
        print('  python tools/backup_bundle.py --set-dest "<드라이브 동기화 폴더>"')
        print("검증만 해 보려면 --dry-run.")
        return 1

    os.makedirs(STAGING, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = PREFIX + stamp + ".zip"
    bundle = os.path.join(STAGING, "repo.bundle")
    archive = os.path.join(STAGING, name)

    dirty = dirty_worktrees()
    if dirty:
        print("⚠ 미커밋 작업이 있는 워크트리 — **이 백업에 안 들어간다**(bundle 은 커밋만 담는다):")
        for label, n in dirty:
            print("    · " + label + " — " + str(n) + "개 파일")
        print("  그 과목 세션에서 커밋한 뒤 다시 돌리면 들어간다.")

    branches = [l.split()[-1] for l in git("branch", "--format=%(refname:short)").splitlines()
                if l.strip()]
    print("[1/4] bundle 만드는 중 — 브랜치 " + str(len(branches)) + "개")
    if os.path.exists(bundle):
        os.remove(bundle)
    git("bundle", "create", bundle, "--all")

    print("[2/4] 복원 검증 — 임시 clone 해서 브랜치가 다 살아 있는지 본다")
    heads, missing = verify_bundle(bundle, branches)
    if missing:
        print("  거부 — 복원본에 빠진 브랜치가 있다: " + ", ".join(missing))
        return 1
    print("  OK · 복원본 ref " + str(len(heads)) + "개 · 원본 브랜치 " + str(len(branches))
          + "개 전부 있음")

    extras = collect_extras()
    print("[3/4] zip 으로 묶는 중 — bundle + git 밖 파일 " + str(len(extras)) + "개")
    # ★ 개수만 찍으면 '무엇이 안 들어갔는지'를 아무도 모른다 — 검수 기준선이 통째로 빠져도
    #   숫자는 그럴듯하게 나온다(규칙 11). 그래서 목록을 실제로 보여 준다.
    for arcname, _src in extras:
        print("    · " + arcname)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(bundle, "repo.bundle")
        for arcname, src in extras:
            z.write(src, arcname)
        z.writestr("복원하는 법.txt",
                   "1) 이 zip 을 아무 데나 푼다\r\n"
                   "2) git clone repo.bundle <새 폴더>\r\n"
                   "   (모든 브랜치를 되살리려면: git clone --bare repo.bundle <새 폴더>.bare)\r\n"
                   "3) worktrees/<워크트리>/review-snapshot/<과목>/ 안의 파일들을\r\n"
                   "   그 워크트리의 data/<과목>/.review-snapshot/ 로 되돌린다 (검수 기준선).\r\n"
                   "4) settings.local.json 도 각 워크트리의 .claude/ 로 되돌린다.\r\n"
                   "\r\n"
                   "들어 있지 않은 것 — site/(빌드로 재생성) · review-artifacts/(재생성) ·\r\n"
                   "교재 지문(--build 로 재생성) · 교재 PDF(리포 밖, 따로 관리).\r\n")
    size_mb = os.path.getsize(archive) / 1024 / 1024
    print("  " + name + " · %.1f MB" % size_mb)

    if args.dry_run:
        print("[4/4] --dry-run 이라 목적지에 쓰지 않았다. 만든 것: " + archive)
        return 0

    dest = os.path.abspath(os.path.expanduser(dest))
    print("[4/4] 목적지로 복사 — " + dest)
    os.makedirs(dest, exist_ok=True)
    shutil.copy2(archive, os.path.join(dest, name))
    kept, dropped = prune(dest, args.keep)
    os.remove(archive)
    print("  완료 · 보관 " + str(kept) + "세대"
          + (" · 정리 " + str(len(dropped)) + "개" if dropped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
