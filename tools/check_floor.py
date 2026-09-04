#!/usr/bin/env python
"""저점 점검 — 이 프로젝트에 «바닥 방어»가 실제로 걸려 있는가 (2026-08-14 신설).

    python tools/check_floor.py .                # ★ **각 프로젝트가 자기 사본으로** 돌린다

★ **공용 폴더 경로로 남의 프로젝트에서 돌리는 형태는 안 통한다.** 이 계통의 가드가 **리포 밖
  스크립트 실행을 막기** 때문이고, 그건 일회성 감사 스크립트를 막으려고 있는 규칙이라
  «여기만» 뚫을 수 없다(2026-08-14 되돌려받은 지적). 사본을 돌리면 **덤**이 하나 더 붙는다 —
  사본이 없거나 낡았다는 것 자체가 «미러·도입이 안 돈다»는 신호다(`check_own_copy`).
  다른 프로젝트를 여기서 진단하는 것은 **읽기 권한이 있을 때의 예외**이지 기본형이 아니다.

**왜 이 도구인가.** 공용 시스템 폴더는 여태 «서랍»이었다 — 필요한 것을 **가져가라**고 두었는데,
가져갈지 말지를 매번 사람이 판정해야 했고 **가져가도 배선하지 않으면 안 돌았다.** 실제로 한
프로젝트가 그 폴더를 안 본 채 같은 실수를 반복했고, 그 사실이 **아무 데서도 안 걸렸다.**

★ **그래서 이 도구가 재는 것은 「문서가 있는가」가 아니라 「배선이 됐는가」다.**
  이 계통의 프로젝트들이 반복해 배운 것이 그 한 줄이다 — *등록 안 된 도구는 없는 것이고,
  호출자 없는 검사는 없는 것이며, 파일에 적었다고 보고한 것이 아니다.*

**고치지 않는다. 재기만 한다.** 무엇을 켤지는 사람이 보고 정한다 — 진단이 처방을 겸하면
「재 보니 이미 다 돼 있다」는 결론이 나올 수 없게 된다.

**도메인을 모른다.** 프로젝트 이름·폴더 구조·과목·기술 스택을 하나도 안 박았다. 박는 순간
그 프로젝트에서만 도는 도구가 되고, 그게 이 폴더가 없애려는 바로 그 병이다.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "dist", "build",
             "Songs", "Cache", ".worktrees", "site"}
LEDGER_HINTS = ("ledger", "원장", "inbox", "인박스", "backlog", "handoff", "인계",
                "workorder", "작업지시")
STALE_DAYS = 30
WAIVER_NAMES = ("저점-면제.txt", "floor-waivers.txt")


def find_waiver_ledger(root):
    """면제 대장을 **찾는다** — 경로를 코드에 박지 않는다.

    ★ 처음엔 `root` 바로 밑만 봤는데 그게 틀렸다. **이 계통의 예외 대장은 전부 한 칸
      아래 있다** — 공용은 `기록/개인정보-예외.txt`·`기록/orphan-checks-allow.txt`,
      XSanity 는 `out/`. `scan_private.find_ledger` 가 `*/이름` 까지 보는 이유가 그것이다.
      규약대로 둔 대장을 못 찾으면 **면제가 조용히 0건**이 되는데, 그건 이 기능이
      없애려던 바로 그 화면(「잊은 것」과 「일부러 안 켠 것」이 같아 보이는)이다.
    """
    base = Path(root)
    for name in WAIVER_NAMES:
        for hit in sorted(base.glob(name)) + sorted(base.glob("*/" + name)):
            if hit.is_file():
                return hit
    return None


def waivers(path):
    """`(면제, 사유없는줄)`. **사유 없는 줄은 면제로 안 친다 — 대신 「버렸다」고 말한다.**

    ★ 왜 필요한가 (2026-08-14, 실사고): 어떤 프로젝트가 훅을 **일부러 안 걸었고** 그 사유를
      도입 대장에 적어 두었는데(*"승인 프롬프트 가드를 안 걸어서 적을 사건이 없다"* ·
      *"9일 뒤 끝나는 개인 노트라 방지장치를 걸 대상이 없다"*) 이 자는 그걸 **✘ 로 찍었다.**
      「잊은 것」과 「일부러 안 켠 것」이 화면에서 같아 보이면, 그 신고는 곧 소음이 되고
      소음이 된 신고는 아무도 안 읽는다.
    ★ 판정선은 이 계통이 이미 쓰는 것과 같다 — `close_report` 의 `strictWaivers`,
      `개인정보-예외.txt`, `orphan-checks-allow.txt`: **사유가 있어야 면제**다.
    ★ **버린 줄을 돌려준다.** 조용히 버리면 적은 사람은 면제된 줄 알고 화면에는 ✘ 만 뜬다 —
      그건 «없는 것»과 «틀리게 적은 것»이 같아 보이는 자리라 위 사고와 같은 부류다.
    ★ **도입 대장에서 읽어 오지 않는다.** 대장이 묻는 것은 «그 파일을 가져갔나» 이고 여기가
      묻는 것은 «이 배선을 켰나» 라 **축이 다르다.** 남의 축의 사유를 끌어다 쓰면 그건
      기계가 의도를 짐작하는 것이고, 그 부류로 오늘 두 번 틀렸다.
    """
    out, reasonless = {}, []
    if path is None:
        return out, reasonless
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, why = line.partition("|")
        if not sep or not key.strip():
            continue
        if why.strip():
            out[key.strip()] = why.strip()
        else:
            reasonless.append(key.strip())
    return out, reasonless


# ── 재기 (순수 함수에 가깝게 — 판정과 출력은 아래에서 따로 한다) ──────────────

def walk(root, limit=20000):
    """훑을 파일과 **상한에 걸렸는가**. 큰 폴더에서 몇 분씩 걸리지 않게 상한을 둔다.

    ★ 잘렸는지를 **함께 돌려준다.** 조용히 자르면 «못 찾았다» 와 «없다» 가 같은 모양이 되고,
      그 출력은 «다 덮었다» 로 읽힌다 — 첫 실전에서 실제로 4,000개에 걸려 «테스트가 없다»
      «원장이 없다» 를 낼 뻔했다(2026-08-14).
    """
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            out.append(Path(base) / name)
            if len(out) >= limit:
                return out, True
    return out, False


def imports_in(text):
    """`@경로` 로 끌어오는 지침 파일들. 줄 맨 앞의 `@` 만 본다(본문 속 이메일은 아니다)."""
    found = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("@") and len(line) > 1:
            found.append(line[1:].split()[0])
    return found


def hook_commands(settings):
    """`(이벤트, 명령)` 목록. settings 구조가 달라도 죽지 않게 방어적으로 읽는다."""
    out = []
    for event, groups in (settings.get("hooks") or {}).items():
        for group in groups or []:
            for hook in (group or {}).get("hooks") or []:
                out.append((event, str(hook.get("command", ""))))
    return out


def referenced_paths(command, root):
    """명령 문자열 안에서 이 프로젝트 안의 파일을 가리키는 토큰."""
    hits = []
    for token in command.replace('"', " ").replace("'", " ").split():
        token = token.replace("$CLAUDE_PROJECT_DIR/", "").replace("\\", "/")
        if "/" in token and token.endswith((".py", ".sh", ".ps1", ".js")):
            hits.append(token)
    return [t for t in hits if (Path(root) / t).parent.is_dir()]


def git_lines(root, args):
    try:
        r = subprocess.run(["git", "-C", str(root)] + args, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.stdout.splitlines() if r.returncode == 0 else []
    except OSError:
        return []


def days_since(path):
    try:
        return (time.time() - path.stat().st_mtime) / 86400.0
    except OSError:
        return None


# ── 항목별 판정 ──────────────────────────────────────────────────────────────

def check_loaded(root):
    """⑴ 지침이 **로드되는가** — 파일이 있는가가 아니다."""
    entry = Path(root) / "CLAUDE.md"
    if not entry.is_file():
        return False, "CLAUDE.md 가 없다 — 세션이 이 프로젝트의 규칙을 하나도 안 읽는다"
    text = entry.read_text(encoding="utf-8", errors="replace")
    imported = imports_in(text)
    missing = [p for p in imported if not (Path(root) / p).is_file()]
    if missing:
        return False, "import 한 파일이 없다: " + ", ".join(missing)
    if not imported and len(text.splitlines()) < 20:
        return False, "CLAUDE.md 가 사실상 비어 있다(%d줄, import 0개)" % len(text.splitlines())
    return True, "CLAUDE.md %d줄 · import %d개 전부 실재" % (len(text.splitlines()), len(imported))


def check_adoption(root, shared):
    """⑵ 공용 시스템을 **항목별로 판정했는가** — 도입 «방식» 은 묻지 않는다.

    ★ **처음엔 «`CLAUDE.md` 가 공용 규칙을 `@import` 하는가» 로 쟀는데 그게 틀렸다.**
      그 자는 **도입 방식 하나만** 인정한다. 실제로 한 프로젝트는 필요한 절을 자기 규칙에
      **개별 이식**해 두고 대장에 사유까지 적어 두었는데 ✘ 가 나왔다(2026-08-14).
      질문은 «어떻게 가져갔나» 가 아니라 **«항목마다 판정했나»** 다 — 방식은 프로젝트가 정한다.

    ★ 그래서 자는 **공용의 도입 대장**(`기록/도입대장.csv`)을 읽는다. 판정 기준 셋:
      ⑴ 그 프로젝트 행이 아예 없다 → 절차를 시작조차 안 한 것 ⑵ **사유 없는 «안가져옴»** 이
      있다 → 그 대장 스스로 *"판정으로 안 친다"* 고 적어 둔 상태 ⑶ 빈 판정이 남았다 → 진행 중.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import adopt_ledger as al                                        # noqa: E402
    except ImportError:
        return None, "도입 대장 도우미를 못 읽었다(adopt_ledger.py)"
    path = al.ledger_path(shared)
    if not path.is_file():
        return None, "공용 도입 대장을 못 찾았다: %s" % path
    rows = al.parse(path.read_text(encoding="utf-8", errors="replace"))
    # 프로젝트 키도 **층 범위도** 그 도구 하나가 판정한다 — 여기서 다시 정하면 두 자가 갈린다
    # (워크트리를 쓰면 폴더 이름이 갈래마다 달라 같은 리포가 여러 프로젝트로 세어졌다).
    # ★ 2026-08-16 — `status_of` 가 `parked`(층 범위 밖 미판정)를 더해 **4개를 돌려주는데**
    #   여기가 3개로 풀고 있어 이 자가 `ValueError` 로 죽었다. 층을 배선한 쪽만 고치고
    #   읽는 쪽을 안 고친 것이다. 범위도 같이 맞춘다 — 안 그러면 «층이 높아 안 묻는 항목»
    #   까지 미판정으로 세어 층 선언이 아무 일도 안 하게 된다.
    tier, _why = al.declared_tier(root)
    items, _skipped = al.in_scope(al.shared_items(shared), al.tier_map(shared), tier)
    missing, unjudged, reasonless, _parked = al.status_of(
        rows, al.project_key(root), items)
    if len(missing) == len(items):
        return False, "이 프로젝트가 대장에 **한 줄도 없다** — 도입 절차를 시작한 적이 없다"
    if reasonless:
        return False, "사유 없는 «안가져옴» %d개 — 대장이 판정으로 안 친다: %s" % (
            len(reasonless), ", ".join(reasonless[:3]))
    if missing or unjudged:
        return None, "항목 %d개 중 미판정 %d개(행 없음 %d) — **사람이 채울 것**" % (
            len(items), len(unjudged) + len(missing), len(missing))
    return True, "공용 항목 %d개 전부 판정됨" % len(items)


def check_hooks(root):
    """⑶ 훅이 **등록**됐는가 — 파일만 있고 등록이 없으면 아무도 안 부른다.

    ★ 등록됐는데 파일이 없으면 더 나쁘다. 그 형태로 한 번 **Bash 가 전면 차단**된 적이 있다.
    ★ `settings.local.json` **도 본다** — 훅을 거기만 걸어 둔 프로젝트를 첫 실전에서
      «훅 0개» 로 낼 뻔했다(2026-08-14). 어느 파일에 걸었는지는 취향이고, 질문은 «걸렸나» 다.
    """
    paths = [Path(root) / ".claude" / "settings.json",
             Path(root) / ".claude" / "settings.local.json"]
    present = [p for p in paths if p.is_file()]
    if not present:
        return False, ".claude/settings*.json 이 없다 — 훅이 하나도 안 걸려 있다"
    commands = []
    for path in present:
        try:
            settings = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except ValueError as exc:
            return False, "%s 를 못 읽는다: %s" % (path.name, exc)
        commands.extend(hook_commands(settings))
    if not commands:
        return False, "%s 에 훅이 0개다" % " · ".join(p.name for p in present)
    broken = []
    for event, command in commands:
        for rel in referenced_paths(command, root):
            if not (Path(root) / rel).is_file():
                broken.append("%s→%s" % (event, rel))
    if broken:
        return False, "등록됐는데 파일이 없다: " + ", ".join(broken[:4])
    events = sorted({e for e, _c in commands})
    return True, "훅 %d개 · 이벤트 %s" % (len(commands), ", ".join(events))


def check_gate(root, files, truncated=False):
    """⑷ 회귀 게이트가 있고 **부르는 자리**가 있는가."""
    tests = [p for p in files if p.suffix == ".py" and p.name.startswith("test")]
    if not tests:
        if truncated:
            return None, "훑기가 상한에 걸려 **못 찾은 것과 없는 것을 구별할 수 없다** (--limit 를 올릴 것)"
        return False, "회귀 테스트 파일이 없다 — «고쳤다»를 증명할 수단이 없다"
    names = {p.stem for p in tests}
    callers = 0
    for path in files:
        if path.suffix not in (".py", ".md", ".json", ".ps1") or path in tests:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if any(n in text for n in names):
            callers += 1
    if callers == 0:
        return False, "테스트 %d개가 있는데 **아무도 안 부른다**" % len(tests)
    return True, "테스트 %d개 · 부르는 자리 %d곳" % (len(tests), callers)


def check_records(root, files, truncated=False):
    """⑸ 기록이 **살아 있는가** — 있는데 안 쓰면 없는 것이다."""
    ledgers = [p for p in files
               if p.suffix in (".md", ".txt", ".json")
               and any(h in p.name.lower() for h in LEDGER_HINTS)]
    if not ledgers:
        if truncated:
            return None, "훑기가 상한에 걸려 **못 찾은 것과 없는 것을 구별할 수 없다** (--limit 를 올릴 것)"
        return False, "원장·인박스·인계 문서가 하나도 없다"
    fresh = min((days_since(p) or 9e9) for p in ledgers)
    if fresh > STALE_DAYS:
        return False, "%d개 있는데 가장 최근 갱신이 %d일 전이다" % (len(ledgers), fresh)
    return True, "%d개 · 최근 갱신 %.1f일 전" % (len(ledgers), fresh)


def check_why_in_commits(root, sample=20):
    """⑸ 커밋에 **«왜»** 가 남는가.

    ★ 이 항목만 **판정하지 않고 숫자만** 낸다. 사유가 적혔는지는 기계가 못 읽는다 —
      길이나 기호로 재면 그 검사는 곧 도장이 되고, 도장이 된 검사는 아무것도 안 막는다.
      *이 프로젝트에서 오늘 한 일을 다음 세션이 알 수 있나* 는 사람이 커밋 목록을 보고 판단한다.
    """
    subjects = git_lines(root, ["log", "-%d" % sample, "--format=%s"])
    if not subjects:
        return None, "git 이력을 못 읽었다(리포가 아니거나 커밋이 없다)"
    wordy = [s for s in subjects if len(s) >= 25]
    return None, "최근 %d개 중 제목이 25자 이상인 것 %d개 — **사람이 볼 것**" % (
        len(subjects), len(wordy))


def check_own_copy(root, shared, files, truncated=False):
    """⑺ 이 프로젝트가 **자기 사본**을 갖고 있는가 (2026-08-14 신설).

    ★ 왜 사본이어야 하나: 이 계통의 가드는 **리포 밖 스크립트 실행을 막는다.** 일회성 감사
      스크립트를 막으려고 있는 규칙이라 «여기만» 뚫을 수 없다 — 그래서 *"공용 경로로 한 줄
      돌려 달라"* 는 지시는 애초에 안 통한다(2026-08-14, 그 지시를 냈다가 되돌려받았다).
    ★ **덤이 이 항목의 값어치다:** 사본이 없거나 낡았으면 **그 사실 자체가 «미러·도입이 안
      돈다»는 신호**다. 도입 대장은 «판정했나»를 묻지 «지금도 최신인가»는 못 묻는다.
    """
    mine = [p for p in files if p.name == Path(__file__).name]
    if not mine:
        # ★★ **상한에 걸린 훑기로 「없다」를 단정하지 않는다** (2026-08-16).
        #   XSanity 실측: 사본이 `_modding/scripts/` 에 **있는데** 20,000개 상한이 그 앞에서
        #   끊겨 이 항목만 ✘ 로 났다 — 그 리포의 유일한 ✘ 였고 **거짓이었다.**
        #   ⑷⑸ 는 이미 `truncated` 를 받아 `?` 로 내리는데 여기만 안 받고 있었다.
        #   *"범위를 확인하지 않은 0건은 '없다'가 아니다"*(규칙 11) — 이 파일 독스트링이
        #   인용하는 그 규칙을 이 함수가 어기고 있었다.
        if truncated:
            return None, ("훑기가 상한에 걸려 **못 찾은 것과 없는 것을 구별할 수 없다** "
                          "(--limit 를 올릴 것)")
        return False, "이 프로젝트에 자기 사본이 없다 — 공용 경로로 돌리는 건 가드가 막는다(도입/미러 확인)"
    theirs = shared / "도구" / Path(__file__).name
    if not theirs.is_file():
        return None, "공용 쪽 원본을 못 찾았다: %s" % theirs
    try:
        same = (mine[0].read_bytes().replace(b"\r\n", b"\n")
                == theirs.read_bytes().replace(b"\r\n", b"\n"))
    except OSError as exc:
        return None, "사본을 못 읽었다: %s" % exc
    rel = mine[0].relative_to(root).as_posix()
    if not same:
        return None, "사본이 공용과 다르다 — %s (낡았으면 미러·도입이 안 도는 것이다)" % rel
    return True, "자기 사본 있음 · 공용과 같음 — " + rel


def check_connected(root, shared):
    """⑹ 공용 시스템과 **연결된 적이 있는가.**

    ★ 이 항목이 이 도구를 만든 이유다. 「가져가라」고 둔 폴더를 한 번도 안 본 프로젝트는
      여기서만 드러난다 — 나머지 다섯 항목은 그 프로젝트가 자기 힘으로 쌓았을 수도 있다.
    """
    if not shared.is_dir():
        return None, "공용 폴더를 못 찾았다: %s (환경변수 CLAUDE_SHARED_SYSTEM 로 지정 가능)" % shared
    marks = [Path(root) / ".claude" / "hooks" / ".shared-system.lock",
             Path(root) / ".claude" / "shared-system.lock"]
    seen = [m for m in marks if m.is_file()]
    if not seen:
        return False, "이 프로젝트는 공용 시스템을 **한 번도 확인한 적이 없다**"
    log = shared / "변경일지.md"
    behind = ""
    if log.is_file():
        gap = (days_since(seen[0]) or 0) - (days_since(log) or 0)
        behind = " · 공용이 %.1f일 앞섬" % gap if gap > 1 else " · 최신"
    return True, "확인 표시 있음(%.1f일 전)%s" % (days_since(seen[0]) or 0, behind)


# ── 실행 ─────────────────────────────────────────────────────────────────────

def selftest():
    """★ 붙임 2026-08-25 — 이 자는 **막는 자인데 대조군이 없었다.**

    ☐ 못 보는 것: 여기서 재는 것은 **순수 함수 넷**이다. 「훅이 실제로 발화하나」·
      「게이트가 정말 도나」는 이 자가 아니라 그 훅 자신의 자가진단 몫이다 —
      이 자는 **배선을 본다**(파일이 있나 · 등록됐나 · 부르는 자리가 있나).
    """
    import tempfile
    bad = 0

    def chk(desc, cond, got=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %-46s %s" % ("OK  " if cond else "**틀림**", desc, got))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        p = root / "면제.txt"
        # ★ 「사유 없는 줄」은 **`|` 는 있고 사유가 빈 줄**이다 (2026-08-25 대조군에서 배웠다).
        #   `|` 가 아예 없는 줄은 형식이 깨진 것이라 조용히 빠진다 — 처음에 그걸 「버림」으로
        #   기대했다가 틀렸고, **틀린 것은 자가 아니라 내 시료였다.**
        p.write_text("# 주석\nhooks | 9일 뒤 끝나는 노트라 걸 대상이 없다\ngates |\n",
                     encoding="utf-8")
        keep, bare = waivers(p)
        chk("★ 사유 있는 줄만 면제 — 사유 빈 줄은 「버렸다」고 말한다",
            "hooks" in keep and bare == ["gates"],
            "면제=%s 버림=%s" % (sorted(keep), bare))

        chk("대장이 없으면(None) 면제 0 — 없는 것이 실패는 아니다",
            waivers(None) == ({}, []))

        # ★ `@아님` 도 import 다 — 확장자를 안 따진다. 처음에 2를 기대했다가 틀렸고,
        #   **자가 맞다**: 여기서 뽑는 것은 「import 줄인가」이고 «그 파일이 실재하나» 는
        #   아래 배선 판정이 따로 본다. 둘을 한 함수에 섞으면 이름이 거짓말을 한다.
        # ★ 시료에 골뱅이를 안 쓴다 — `개인정보-스캔`이 그것을 **이메일로 오인**했다
        #   (2026-08-25 마감에서 잡혔다 — 옛 시료가 «n 골뱅이 없는것.md» 였다). 자기 검정
        #   시료도 리포에 실리는
        #   글이라 다른 자의 눈에 걸린다. ★ 그래서 **주석에도 골뱅이를 안 쓴다** —
        #   고친 시료 옆에 옛 시료를 그대로 인용해 두어 2026-08-25 에 또 걸렸다.
        txt = "@규칙/가.md\n@규칙/나.md\n본문은 import 가 아니다\n"
        chk("`@` 로 시작하는 줄만 import 로 본다 (실재 여부는 딴 자리에서)",
            len(imports_in(txt)) == 2, str(imports_in(txt)))

        cmds = hook_commands({"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": 'python "$X/훅/a.py"'}]}]}})
        chk("훅 등록에서 명령을 뽑는다", len(cmds) == 1, str(cmds))
        chk("훅이 없으면 0개 — 「등록 안 함」이 보인다",
            hook_commands({"hooks": {}}) == [])

    print()
    print("  ※ ☐ 이 자는 **배선만 본다** — 「그 훅이 실제로 발화하나」는 못 본다.")
    print("     그건 각 훅의 자가진단 몫이다(XSanity `--hook-selftest` 선례).")
    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


DECL_DECL = re.compile(r'^DECL_NAME\s*=\s*["\']([^"\']+)["\']', re.M)


def check_declarations(root, files, truncated=False):
    """**선언을 읽어 도는 자의 선언 파일이 실제로 있는가** (2026-08-26 신설).

    ★★★ 왜 (나루 감사 5번) — *"선언 파일이 사라지면 조용히 초록."*
      `audit_stamps` 는 선언이 없으면 «해당 없음 0건» 으로 **exit 0**, `audit_gates` 도
      같은 구멍이다. 그리고 **그 존재를 묻는 자가 어디에도 없었다** — `check_floor` ·
      `check_orphan_checks` · `preflight()` · 훅 설정 넷 다 안 본다(2026-08-26 확인).
      즉 파일 하나를 지우면 감사 하나가 통째로 눈을 감고, 표에는 초록이 남는다.

    ★ **이름을 안 박는다.** 도구가 자기 모듈 상단에 `DECL_NAME = "..."` 로 이미
      선언하고 있으므로 **그걸 읽어** 찾는다 — 이 파일의 첫 규율(«도메인을 모른다»)을
      지키면서, 앞으로 생기는 선언-읽는 도구도 저절로 걸린다.
    """
    want, seen = {}, {p.name for p in files}
    for p in files:
        if p.suffix != ".py":
            continue
        try:
            m = DECL_DECL.search(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if m:
            want.setdefault(m.group(1), []).append(p.name)
    if not want:
        # ★★ **잘린 훑기에서 「없다」를 말하지 않는다** — 이 검사가 막으려는 바로 그
        #   부류(«조용히 초록»)를 자기가 저지르는 자리다. 규칙 2: 범위를 안 밝힌 0건은
        #   «없다» 가 아니라 «거기까지는 없다» 이다.
        if truncated:
            return None, ("훑기가 상한에 걸려 **선언을 읽는 자가 없는 것과 못 찾은 것을 "
                          "구별할 수 없다** (--limit 를 올릴 것)")
        return None, "선언을 읽어 도는 자가 없다 — 해당 없음"
    missing = sorted(n for n in want if n not in seen)
    if missing:
        return False, ("선언 파일이 없다: %s — 그 자는 «해당 없음»으로 **조용히 초록**이 된다 "
                       "(읽는 자: %s)"
                       % (", ".join(missing),
                          ", ".join(sorted(set(sum((want[n] for n in missing), []))))))
    return True, "선언 파일 %d개가 다 있다 (%s)" % (len(want), ", ".join(sorted(want)))


def main():
    if "--selftest" in sys.argv:
        print("[자기 검정] 바닥 방어 배선")
        return selftest()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    limit = 20000
    for flag in sys.argv[1:]:
        if flag.startswith("--limit="):
            limit = int(flag.split("=", 1)[1])
    root = Path(args[0] if args else ".").resolve()
    shared = Path(os.environ.get("CLAUDE_SHARED_SYSTEM")
                  or next((p for p in (Path.home() / "Documents" / "naru",
                                    Path.home() / "Documents" / "Claude")
                            if p.is_dir()), Path.home() / "Documents" / "naru"))
    if not root.is_dir():
        sys.exit("폴더가 아니다: %s" % root)

    files, truncated = walk(root, limit)
    rows = [
        ("loaded", "규칙이 로드되나", check_loaded(root)),
        ("adoption", "공용 시스템을 판정했나", check_adoption(root, shared)),
        ("hooks", "훅이 등록됐나", check_hooks(root)),
        ("gate", "회귀 게이트가 도나", check_gate(root, files, truncated)),
        ("records", "기록이 살아 있나", check_records(root, files, truncated)),
        ("declarations", "선언 파일이 살아 있나",
         check_declarations(root, files, truncated)),
        ("commits", "커밋에 «왜» 가 남나", check_why_in_commits(root)),
        ("connected", "공용 시스템과 이어졌나", check_connected(root, shared)),
        ("own_copy", "자기 사본으로 도나", check_own_copy(root, shared, files, truncated)),
    ]
    ledger = find_waiver_ledger(root)
    waived, reasonless = waivers(ledger)
    keys = [k for k, _l, _r in rows]

    print("[저점 점검] %s  (파일 %d개 훑음%s)"
          % (root, len(files), " · ★ 상한에 걸려 잘렸다" if truncated else ""))
    bad, excused = 0, []
    for key, label, (ok, detail) in rows:
        if ok is False and key in waived:
            # 「잊은 것」과 「일부러 안 켠 것」을 가른다 — 면제는 **보이게** 찍는다(숨기면 도장이 된다).
            excused.append((label, waived[key]))
            print("  — " + label + " — 면제: " + waived[key])
            continue
        mark = "  ? " if ok is None else ("  ✔ " if ok else "  ✘ ")
        if ok is False:
            bad += 1
        print(mark + label + " — " + detail)
    print("[저점 점검] ✘ %d건%s%s" % (
        bad,
        (" · 면제 %d건(사유 있음)" % len(excused)) if excused else "",
        " — 사람이 볼 항목 있음(?)" if any(
            ok is None for _k, _l, (ok, _d) in rows) else ""))

    # ── 면제 대장의 상태를 **말한다.** 조용한 대장은 있으나 마나다 ──────────────
    if ledger is None:
        print("  ※ 면제 대장 없음 — 일부러 안 켠 항목은 `%s` 에 `항목키 | 사유` 로 적는다"
              " (`기록/` 같은 한 칸 아래도 본다). **사유 없는 줄은 면제로 안 친다.** 키: %s"
              % (WAIVER_NAMES[0], ", ".join(keys)))
    else:
        # 「사유 있는 줄」과 위의 「면제 N건」은 **다른 수다** — 같은 이름을 주면 안 된다.
        # 적은 줄이 다 먹히는 게 아니다: 모르는 키이거나, 그 항목이 애초에 ✘ 가 아니었을 수 있다.
        print("  ※ 면제 대장: %s (사유 있는 줄 %d개 · 이번에 실제로 면제된 것 %d건)"
              % (ledger.relative_to(root).as_posix(), len(waived), len(excused)))
    if reasonless:
        # 조용히 버리면 적은 사람은 면제된 줄 알고 화면에는 ✘ 만 뜬다.
        print("  ※ ★ 사유 없는 줄 %d개는 **면제로 안 쳤다**: %s — 사유를 적어야 면제다"
              % (len(reasonless), ", ".join(reasonless[:4])))
    unknown = [k for k in waived if k not in keys]
    if unknown:
        # 「소비 안 되는 설정 키 = 거짓 설정」(규칙/방지장치-설계.md) — 적었는데 아무것도 안 면제한다.
        print("  ※ ★ 모르는 항목키 %d개는 **아무것도 면제하지 않는다**: %s — 쓸 수 있는 키: %s"
              % (len(unknown), ", ".join(unknown), ", ".join(keys)))
    print("  ※ 이 도구는 **고치지 않는다.** 무엇을 켤지는 위 항목을 보고 사람이 정한다.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
