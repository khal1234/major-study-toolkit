# -*- coding: utf-8 -*-
"""과목별 진도를 한 표로 — **커밋된 상태로만** 읽는다 (읽기 전용).

    python tools/audit_subject_progress.py            # 챕터 status 만 (빠르다)
    python tools/audit_subject_progress.py --cards    # 이론·유도·문풀·연습 개수까지
    python tools/audit_subject_progress.py --only=thermo,math

열린 날 2026-08-15. 사용자 질문 *[발화 생략]* 에 답할 자가 없었다.
`inspect_data.py` 는 **자기 워크트리 하나**만 보고, `verify_all.py` 는 «아직 서는가»(건강)를
보지 «얼마나 왔나»(진도)를 안 본다. 그래서 물을 때마다 갈래마다 손으로 뒤지게 된다.

★ **`git show <갈래>:<경로>` 로만 읽는다** — 남의 워크트리 폴더를 파일시스템으로 열지 않는다.
  그쪽 세션이 작업 중이면 **반쯤 고친 상태를 정본으로 오인**한다(AGENTS 「다른 과목은 읽어도
  된다 — 단 커밋으로 읽는다」). 그래서 이 도구의 수는 언제나 «마지막 커밋 기준」이고, 그
  사실을 머리글에 찍는다.

★ **과목 이름을 박지 않는다.** 갈래 목록은 `git worktree list`, 과목 폴더는 `git ls-tree` 로
  찾는다 — 새 과목이 생기면 아무것도 안 해도 표에 뜬다(AGENTS 「공통 도구에 과목별 사실을
  박지 않는다」 · 폴백을 두면 그 과목만 알고 나머지는 조용히 빠진다).

★ **판정하지 않는다.** «done 이 몇 개면 좋다» 는 이 도구가 정할 것이 아니다. 세어서 나란히
  놓기만 하고 무엇을 다음에 할지는 사람이 본다(`check_floor` 가 커밋 항목을 판정하지 않는 것과
  같은 이유 — 판정을 넣는 순간 그 수가 목표가 되고, 목표가 된 수는 채워진다).
"""
import json
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 콘텐츠가 없는 갈래 — 여기에 과목을 적지 않는다. 「데이터 폴더가 없다」로 저절로 갈린다.
CARD_KEYS = (("theory", "sections"), ("derivation", "formulas"),
             ("practice", None), ("problems", None))


def git(*args):
    """★ `core.quotepath=false` 가 **필수다** — 이 리포는 과목 폴더가 전부 한글이다.

    기본값이면 `git ls-tree` 가 비ASCII 이름을 **8진 이스케이프로 감싸** 돌려준다
    (`"\\354\\240\\204…"`). 그대로 쓰면 이어지는 `git show <갈래>:<경로>` 가 전부 빗나가
    **모든 과목이 「index.json 없음」으로 뜨는데 그게 사실처럼 보인다** — 실측으로 잡았다
    (첫 실행에서 12과목 전부 그렇게 났다). 「범위를 안 밝힌 0건」과 같은 부류다.
    """
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") if r.returncode == 0 else ""


def subjects(rev="HEAD"):
    """`data/<과목>/` **전부**. 이름을 코드에 박지 않고 트리에서 찾는다.

    ★★ **2026-09-07 — 이 자는 죽어 있었다.** 옛 판은 `git worktree list` 로 갈래를 세고
      갈래마다 **첫 과목 하나**만 봤다(«과목 = 브랜치 = 워크트리» 전제). 21과목을 한 트리로
      합친 뒤 갈래가 `main` 하나뿐이라 목록이 비었고, 도구는 **죽지 않고 빈 표를 냈다** —
      인계 문서가 잡은 셋(`discover_data_dir`·`audit_convention_drift`·`backup_bundle`)과
      **같은 부류의 넷째**다. 회귀는 그때 `subject_dir()`(첫 과목 하나)만 재고 있어서 초록이었다.
      → 이제 전 과목을 돌려주고, **훑은 과목 수를 화면에 찍으며 0이면 exit 1** 이다.
    ★ 숨김 폴더(`.textbook-fingerprint` 등)는 과목이 아니다.
    """
    out = []
    for line in git("ls-tree", "--name-only", rev, "data/").splitlines():
        name = line.strip().rstrip("/")
        if name and name != "data" and not name.split("/")[-1].startswith("."):
            out.append(name)
    return sorted(out)


def blob(branch, path):
    text = git("show", branch + ":" + path)
    try:
        return json.loads(text) if text.strip() else None
    except ValueError:
        return None


def count_cards(branch, folder, files):
    """이론·유도·문풀·연습 **항목 수**. 챕터마다 blob 을 한 번씩 읽으므로 `--cards` 에서만."""
    total = [0, 0, 0, 0]
    for name in files:
        ch = blob(branch, folder + "/" + name)
        if not ch:
            continue
        for i, (key, sub) in enumerate(CARD_KEYS):
            node = ch.get(key)
            if sub:
                node = (node or {}).get(sub)
            total[i] += len(node or [])
    return total


def main():
    want_cards = "--cards" in sys.argv
    only = None
    for flag in sys.argv[1:]:
        if flag.startswith("--only="):
            only = {s.strip() for s in flag.split("=", 1)[1].split(",") if s.strip()}

    rows = []
    folders = subjects()
    for folder in folders:
        name = folder.split("/")[-1]
        if only and name not in only:
            continue
        index = blob("HEAD", folder + "/index.json")
        if index is None:
            rows.append((name, None, "index.json 없음·못 읽음"))
            continue
        chapters = index.get("chapters") or []
        status = {}
        for c in chapters:
            status[str(c.get("status") or "?")] = status.get(str(c.get("status") or "?"), 0) + 1
        cards = None
        if want_cards:
            names = [n.split("/")[-1] for n in
                     git("ls-tree", "--name-only", "HEAD", folder + "/").splitlines()
                     if n.strip().endswith(".json") and "/ch" in n]
            cards = count_cards("HEAD", folder, sorted(names))
        rows.append((name, (len(chapters), status), cards))

    head = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    print("과목 진도 — **마지막 커밋 기준**이다 (`git show HEAD:` 로 읽는다)")
    print("          지금 갈래: %s · 미커밋 변경은 이 표에 안 보인다" % head)
    print("          훑은 과목 %d개%s\n"
          % (len(folders), (" · 표시 %d개" % len(rows)) if only else ""))
    cols = "%-22s %5s %5s %5s" % ("과목", "챕터", "done", "그 외")
    if want_cards:
        cols += " %6s %5s %5s %5s" % ("이론", "유도", "문풀", "연습")
    print(cols)
    print("-" * (len(cols) + 8))

    for subject, chap, cards in rows:
        if chap is None:
            print("%-22s   —  (%s)" % (subject, cards))
            continue
        total, status = chap
        done = status.get("done", 0)
        line = "%-22s %5d %5d %5d" % (subject, total, done, total - done)
        if want_cards and isinstance(cards, list):
            line += " %6d %5d %5d %5d" % tuple(cards)
        print(line)

    if not want_cards:
        print("\n(`--cards` 를 붙이면 이론·유도·문풀·연습 개수까지 센다 — 챕터를 다 읽어 느리다)")
    print("※ 이 도구는 **판정하지 않는다.** 다음에 무엇을 할지는 위 수를 보고 사람이 정한다.")
    # ★ 「범위를 안 밝힌 0건」을 막는다 — 한 과목도 못 읽었으면 그건 진도가 아니라 고장이다.
    if not folders:
        print("\n[고장] data/ 아래 과목을 하나도 못 읽었다 — 빈 표를 진도로 읽지 말 것.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
