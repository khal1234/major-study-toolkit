# -*- coding: utf-8 -*-
"""공용 시스템(`Documents/naru`)이 바뀌었는지 **해시로만** 확인해 한 줄로 알린다.

    settings.json 의 SessionStart 훅으로 건다:
        python .claude/hooks/shared_sync_check.py

왜 이 형태인가 (2026-08-12, 사용자: *[발화 생략]*):

  ★ **평소 비용이 0이어야 확인을 매 세션 돌릴 수 있다.** 그래서 내용을 읽지 않고 **해시만**
    비교하고, **달라진 것이 없으면 아무것도 출력하지 않는다.** 달라졌을 때만 한 줄 —
    그 줄을 본 세션이 `변경일지.md` 의 해당 줄만 읽고 가져올지 판정한다.
  ★ **자동 복사는 하지 않는다.** 프로젝트마다 경로·이름·구조가 달라 덮어쓰면 깨진다.
    이 훅은 *알리는 것*까지만 하고 판정은 사람·에이전트가 한다.
  ★ **주기 제한을 두지 않는다.** 비용이 0이라 매 세션 돌려도 되고, 그래야 올린 다음 세션에
    바로 알려진다(주 1회로 묶으면 그만큼 늦게 안다).

lock 파일(`.claude/hooks/.shared-system.lock`)은 **프로젝트마다 따로** 갖는다 — 가져간 시점이 다르다.

★ **자리를 2026-08-14 에 옮겼다: `.claude/` 밑 → `.claude/hooks/` 밑 + dot 접두.**
  옛 자리는 **추적되는 파일**이라 미러가 돌 때마다 작업 트리가 더러워졌고, 그러면
  「기준선 이동은 깨끗한 트리에서만」 게이트가 매번 걸린다. 게다가 이건 **워크트리 로컬 상태**라
  브랜치에 실려 다닐 것이 아니다. `.gitignore` 에 이름을 하나 더 **열거하지 않고** 옮긴 이유는
  그 파일 50~57행에 적힌 그대로다 — *[발화 생략]* 이라서 훅이 로그를
  하나 더 만들 때마다 샜고, 그래서 **기본값을 안전한 쪽으로 뒤집어** `/.claude/hooks/.*` 로
  막아 두었다. 그 뒤집힌 기본값 안으로 들어가는 것이 맞다.
공용 폴더가 없는 환경(다른 PC)에서는 **조용히 아무것도 안 한다.**
"""
import hashlib
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SHARED = Path(os.environ.get("CLAUDE_SHARED_SYSTEM")
              or next((p for p in (Path.home() / "Documents" / "naru",
                                    Path.home() / "Documents" / "Claude")
                            if p.is_dir()), Path.home() / "Documents" / "naru"))
LOCK = Path(__file__).resolve().parent / ".shared-system.lock"   # dot 접두 = 이미 무시되는 자리
# 해시를 뜰 대상. 산출물·캐시는 세지 않는다.
SUFFIXES = (".md", ".py", ".ps1", ".txt", ".json")
SKIP_DIRS = {"__pycache__", ".git"}
MANDATORY_LIST = "기록/필수-반영-목록.txt"   # SHARED 기준 상대경로 — 아래 load_mandatory() 가 읽는다


def load_mandatory():
    """{경로: 사유} — 「무조건 판정해야 하는」 파일 대장. 못 읽으면 빈 dict(전부 선택 취급).

    ★ **필수 = 자동 복사가 아니다** (2026-08-30, 공용 폴더 원안). 자동 복사는 여전히
      안 한다 — 프로젝트마다 구조가 달라 덮으면 깨진다는 이 파일의 원래 원칙 그대로다.
      필수가 바꾸는 것은 **한 줄 알림에서 "선택, 판정할 것"으로 묻히던 것을 "필수, 판정을
      미루면 안 된다"로 분리해 보여주는 것** — 알리는 자는 여전히 알리기만 한다.
    """
    p = SHARED / MANDATORY_LIST
    if not p.is_file():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        path, reason = line.split("|", 1)
        out[path.strip()] = reason.strip()
    return out


def fingerprint(root):
    """{상대경로: 해시 앞 12자}. 순수 함수 — 테스트가 직접 부른다."""
    out = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        out[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    return out


def digest(data):
    """파일 내용 → 지문 12자.

    `tools/sync_common.py` 의 미러가 **이 함수를 그대로 가져다 쓴다** — 지문 방식이 두 벌이면
    같은 파일을 두고 lock 이 서로 다른 것을 가리켜 「공용 쪽이 바뀌었나」 판정이 통째로
    거짓말이 된다(이 리포가 여러 번 겪은 «같은 질문에 답하는 자가 둘» 부류).
    """
    return hashlib.sha256(data).hexdigest()[:12]


def diff(now, before):
    """(새로 생긴 것, 바뀐 것, 사라진 것). 순수 함수."""
    added = [k for k in now if k not in before]
    changed = [k for k in now if k in before and now[k] != before[k]]
    gone = [k for k in before if k not in now]
    return added, changed, gone


CHANGELOG = "변경일지.md"


def changelog_lines(path, limit=3):
    """`변경일지.md` 에서 그 파일 이름을 말하는 줄(최신부터 limit 개). 없으면 빈 목록.

    사라진 파일은 개명이 대부분이라(2026-09-11 `사용자가-병목이다` → `확인하기-편하게-만든다`)
    그 줄이 곧 판정 재료다. 재는 것: 파일 이름(basename) 부분 일치. 못 보는 것: 이름을 안 적고
    «규칙 하나 개명» 이라고만 쓴 줄.
    """
    p = SHARED / CHANGELOG
    if not p.is_file():
        return []
    name = Path(path).name
    hits = [ln.strip() for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()
            if name in ln and ln.lstrip().startswith("|")]
    return hits[:limit]


def _brief(line, width=200):
    return line if len(line) <= width else line[:width] + " …"


def load_lock():
    """lock 에 적힌 «지난번에 본 상태». 못 읽으면 빈 dict.

    세 자리(`main`·`accept`·`show_list`)가 같은 것을 읽는다 — 따로 적으면 갈라진다
    (이 리포가 「같은 질문에 답하는 자가 둘」이라 부르는 부류).
    """
    if not LOCK.is_file():
        return {}
    try:
        return json.loads(LOCK.read_text(encoding="utf-8")).get("files") or {}
    except ValueError:
        return {}


def main():
    now = fingerprint(SHARED)
    if not now:
        return 0                      # 공용 폴더가 없는 환경 — 조용히 넘어간다
    before = load_lock()
    added, changed, gone = diff(now, before)
    if not LOCK.is_file():
        # 첫 실행 — 지금 상태를 기준으로 삼고 알리지 않는다(전부 '새것' 으로 뜨면 소음이다).
        LOCK.write_text(json.dumps({"files": now}, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
        return 0
    if not (added or changed or gone):
        return 0                      # ★ 평소: 출력 0
    # ★ 사라진 것도 첫 줄에 낸다 (2026-09-13). 전에는 `--list` 에만 있어 세션이 «가져올 것» 만 보고
    #   개명(2026-09-11 사용자가-병목이다 → 확인하기-편하게-만든다)을 이틀 지나쳤다 — 옛 이름을 가리키는
    #   대장 행이 남았다. 개명은 판정 대상이라 변경일지 줄을 여기서 바로 붙인다.
    for path in gone:
        lines = changelog_lines(path, limit=1)
        print("[공용 시스템 · 사라짐] %s — %s" % (
            path, _brief(lines[0]) if lines else "변경일지에 그 이름이 없다 — `--list` 뒤 `--accept <경로> --reason <사유>`"))
    if not (added or changed):
        return 0
    names = [*(f"+{k}" for k in added), *changed]
    mandatory = load_mandatory()
    must = [n for n in names if n.lstrip("+") in mandatory]
    optional = [n for n in names if n.lstrip("+") not in mandatory]
    # ★★ 자리 이름을 **글자로 박지 않는다 — 방금 찾아간 그 폴더를 그대로 찍는다** (2026-08-15).
    #   전에는 `Documents/Claude` 가 문구에 박혀 있었는데, 폴더가 `naru` 로 개명된 뒤에도
    #   **기계만 두 이름을 다 보고 문구는 옛 이름을 가리켰다** — 알림을 받은 세션이 **없는
    #   경로를 열어 보게 된다.** 인스턴스가 아니라 부류로 닫는다: 이름이 또 바뀌어도
    #   `SHARED` 가 이미 답을 알고 있으니 **문구가 다시 낡을 자리가 없다.**
    if must:
        # ★ 필수는 5개로 안 자른다 — 목록이 짧게 유지되도록 설계됐다(사람이 손으로 관리).
        detail = ", ".join("%s(%s)" % (n.lstrip("+"), mandatory[n.lstrip("+")]) for n in must)
        print("[공용 시스템 · 필수] %d건 — 판정을 미루지 말 것: %s"
              % (len(must), detail))
    if optional:
        print("[공용 시스템] 변경 %d건 — %s%s · `%s/변경일지.md` 의 그 줄만 읽고"
              " 가져올지 판정할 것 (전체 목록 `--list` · 가져왔으면 `--accept <경로…>` 로 표시)"
              % (len(optional), ", ".join(optional[:5]),
                 " …" if len(optional) > 5 else "", SHARED.as_posix()))
    return 0


def show_list():
    """`--list` — **잘리지 않은** 전체 목록. 판정하는 세션이 부른다.

    ★ 왜 따로 두나 (2026-08-15): 위 한 줄은 **다섯 개에서 자른다**(`names[:5]`). 평소 비용을
    0 에 가깝게 두려는 것이라 그 자름 자체는 옳다. 그런데 자른 뒤 «전체를 볼 길»이 없어서
    판정하는 세션이 **나머지를 눈으로 추측**하게 됐다 — 규칙 11 이 「조용히 잘린 순회」라 부르는
    그 형태다(*[발화 생략]*).
    → 자르는 쪽은 그대로 두고 **여는 문**을 만든다. 부르는 자리는 위 한 줄이 스스로 광고한다.
    ★ 사라진 것(`gone`)도 함께 낸다 — 한 줄 알림은 «가져올 것»만 세느라 그것을 빼는데,
      판정하는 자리에서는 «공용에서 없어졌다» 도 판정 대상이다.
    """
    now = fingerprint(SHARED)
    if not now:
        print("[공용 시스템] 공용 폴더가 없다: " + str(SHARED))
        return 0
    added, changed, gone = diff(now, load_lock())
    for label, names in (("새로 생김", added), ("바뀜", changed), ("공용에서 사라짐", gone)):
        print("[%s] %d건" % (label, len(names)))
        for name in names:
            print("  " + name)
            if label == "공용에서 사라짐":
                for ln in changelog_lines(name):
                    print("      변경일지: " + _brief(ln))
    return 0


def accept(only=None, reason=None):
    """가져오기를 마쳤을 때 lock 을 지금 상태로 민다 — `python … --accept [경로…] [--reason <사유>]`.

    ★ **경로를 주면 그것만 민다 (2026-08-14).** 통째로 미는 길만 있으면, 한 파일을 확인했을 뿐인데
    **아직 판정 안 한 파일까지 «확인함» 이 된다** — 그다음 미러가 그것들을 조용히 덮는다.
    확인은 파일 단위로 하는 일이라 표시도 파일 단위여야 한다.
    ★ **사라진 경로는 판정 없이 못 닫는다 (2026-09-13, 정정 같은 날).** 전에는 «공용 폴더에 없는
      경로는 건너뛴다» 로 lock 에 남긴 채 통과했고, 세션은 변경일지를 안 읽고도 accept 를 마쳤다고
      믿었다. 이제 사라진 경로는 ⑴ 변경일지에 그 이름을 말하는 줄이 있거나 ⑵ `--reason` 이 있어야
      lock 에서 빠진다. 둘 다 없으면 exit 1.
      ★★ **이 판정은 `only` 를 줬을 때만 돌고 있었다(같은 날 실사고, Codex 검증으로 발견).**
      인자 없는 전체 accept 는 `now` 를 그대로 lock 에 덮어써 사라진 경로 검사 자체를 안 탔다 —
      "사라진 경로는 판정 없이 못 닫는다"는 보호가 정작 가장 흔한 진입점(인자 없는 accept)에서는
      성립하지 않았다. 그래서 `only` 유무와 무관하게 **lock 과 now 의 합집합**을 순회해 같은 판정을
      거친다 — 경로별/전체 두 진입점이 같은 삭제 fixture 에서 같은 결과를 내야 한다.
      재는 것: 이름 일치 여부. 못 보는 것: 그 줄을 세션이 실제로 읽었는가.
    """
    now = fingerprint(SHARED)
    keep = load_lock()
    paths = only if only else sorted(set(keep) | set(now))
    refused = []
    skipped = []
    for path in paths:
        if path in now:
            keep[path] = now[path]
        elif path in keep:                       # 공용에서 사라진 것 — 판정이 붙어야 닫힌다
            lines = changelog_lines(path)
            if lines or reason:
                del keep[path]
                print("[공용 시스템] 사라진 경로를 닫는다: %s — %s"
                      % (path, _brief(lines[0]) if lines else "사유: " + str(reason)))
            else:
                refused.append(path)
        else:
            skipped.append(path)
    if skipped:
        print("[공용 시스템] lock 에도 공용 폴더에도 없는 경로는 건너뛴다: " + ", ".join(skipped))
    if refused:
        print("[공용 시스템] 사라진 경로인데 변경일지에 그 이름이 없다 — 판정을 `--reason <사유>` 로 붙일 것: "
              + ", ".join(refused))
        return 1
    LOCK.write_text(json.dumps({"files": keep}, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    print("[공용 시스템] 확인 완료로 표시했다" +
          (" — " + str(len(only)) + "개만" if only else " — 다음 세션부터 이 상태가 기준이다"))
    return 0


if __name__ == "__main__":
    if "--accept" in sys.argv:
        argv = sys.argv[1:]
        reason = None
        if "--reason" in argv:
            i = argv.index("--reason")
            reason = argv[i + 1] if i + 1 < len(argv) else None
            argv = argv[:i] + argv[i + 2:]
        paths = [a for a in argv if not a.startswith("--")]
        raise SystemExit(accept(paths or None, reason))
    if "--list" in sys.argv:
        raise SystemExit(show_list())
    raise SystemExit(main())
