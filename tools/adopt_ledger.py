#!/usr/bin/env python
"""공용 시스템 **도입 대장** 도우미 (2026-08-14 신설).

    python tools/adopt_ledger.py [프로젝트 폴더] [--apply]

**왜 이 도구인가.** 공용 폴더에는 *무엇을 가져갈지*(`규칙/무엇을-가져갈까.md`)와
*가져갔는지*(`기록/도입대장.csv`) 가 **이미 있었다.** 빠진 것은 그 절차를 **시작시키는 자리**다 —
새 프로젝트가 열려도 아무 일도 안 일어나고, 사람이 [사용자 발화 인용 생략] 고 말해야만 시작됐다.
실측(2026-08-14): 대장에 올라 있는 프로젝트가 **한 개뿐**이었다.

★ **판정은 절대 기계가 안 한다.** 이 도구는 «판정할 자리»(빈 칸)를 만들고 **미판정을 세기만**
  한다. 기계가 «가져옴» 을 찍는 순간 그 대장은 도장이 되고, 도장이 된 대장은 아무것도 안 막는다.

★ **덧붙이기만 한다.** 기존 줄·주석·서식을 다시 쓰지 않는다 — 통째로 재작성하면 남이 적어 둔
  사유가 서식 변경에 묻힌다.

★ **도입 «방식» 은 묻지 않는다.** `@import` 든 필요한 절만 **개별 이식**이든 둘 다 정당하다.
  방식 하나만 인정하는 자가 실제로 오판을 냈다(그 경위는 `check_floor.check_adoption`).

★★ **묻는 범위는 「층」이 정한다 (2026-08-15 배선).** 리포 루트의 `프로젝트-층.txt` 선언을
  읽어 **그 층에 해당하는 항목만** 묻는다 — 정본은 `규칙/프로젝트-층.md`, 항목별 층은
  `기록/층-배정.txt`. 전에는 전부 물어서 **한 번 쓰고 버리는 작업도 스무 줄을 해명**해야
  했고, 그 소음이 곧 «이 대장은 안 읽는 것» 으로 가는 길이었다.
  실측: 층 0 을 선언하면 17개 → **3개**. 선언이 없거나 **네 물음의 답이 모자라면 전부 묻는다.**
"""
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HEADER = "프로젝트,항목,판정,사유"
LEDGER_NAME = "도입대장.csv"
# ★★ **`훅` 을 2026-08-16 에 넣었다.** 그전에는 («규칙», «기록») 뿐이라 **훅은 대장이 아예
#   안 물었다** — 나루가 `훅/gate_rerun_guard.py` 를 만들고 `층-배정.txt` 에 층 0 으로 적어
#   두었는데 **읽는 자가 없어 아무 프로젝트도 판정을 안 받았다.** 이 폴더가 남에게 대고
#   [사용자 발화 인용 생략] 이라고 지적한 바로 그 모양이었다.
# ★ 훅은 **가장 결과가 큰 항목**이다 — 규칙은 안 지켜도 조용하지만 훅은 실제로 막는다.
#   묻지 않으면 «받았는데 안 걸어서 안 도는» 상태가 영영 안 걸린다.
# ★ 소음은 층이 잡는다 — 넣으면서 기존 훅 여덟에 층 2 를 배정했다(`기록/층-배정.txt`).
# ★★★ **`도구` 를 2026-08-24 에 넣었다 — 훅이 2026-08-16 에 겪은 것과 같은 구멍이다.**
#   그전에는 («규칙», «기록», «훅») 뿐이라 **도구는 대장이 아예 안 물었다.** 하필
#   **「막는 자」가 전부 `도구/` 에 산다** — `check_narration` 을 Stop 훅에 걸어 놓고도
#   [사용자 발화 인용 생략] 는 지시를 **기계로 옮길 자리가 없었다**(2026-08-24).
#   증거: `층-배정.txt` 에 `도구/runtime_note.py`·`도구/audit_serial_waits.py` 두 줄이
#   **배정만 된 채 아무도 안 물어봤다** — 읽는 자가 없는 배정은 없는 것과 같다.
#   ★ 소음은 층이 잡는다 — 넣으면서 기존 도구 전부에 층을 배정했다(같은 배치, 위 선례와 같다).
ASK_FOLDERS = ("규칙", "기록", "훅", "도구")

# ── 층 (2026-08-15 배선) ────────────────────────────────────────────────────
#
# `규칙/프로젝트-층.md` 가 정본이다. 그 문서가 **사람이 읽는 자로만** 서 있으면
# 층 0 프로젝트도 여기서 스무 줄을 하나씩 해명하게 되고, **그 소음이 그 문서가
# 없애려던 것**이다(그 문서 §7 이 «아직 기계가 안 읽는다» 고 밝혀 둔 자리).
#
# ★ **층을 코드에 적지 않는다.** 항목 목록을 코드에 안 적는 것과 같은 이유다 —
#   규칙 파일이 하나 늘어난 날 이 도구만 옛 세상을 말하게 된다. 배정은 자료
#   (`기록/층-배정.txt`)가 갖고 코드는 읽기만 한다.
TIER_FILE = "프로젝트-층.txt"          # 각 프로젝트 루트에 두는 **선언**
TIER_MAP_NAME = "층-배정.txt"          # 공용 `기록/` 에 두는 **항목별 층**
FEEDBACK_NAME = "feedback-ledger.md"   # 복사가 아니라 **조회** 대상 — 아래 `shared_items` 참조
# 선언에 답이 있어야 하는 네 물음(`프로젝트-층.md` §2). 키의 일부만 맞으면 인정한다 —
# 글자 그대로를 요구하면 사람이 조금 달리 적었다고 선언이 통째로 무효가 된다.
TIER_ANSWER_KEYS = ("되돌릴", "남이 읽", "오래 사", "여럿이")


def ledger_path(shared):
    return Path(shared) / "기록" / LEDGER_NAME


def parse(text):
    """`(프로젝트, 항목, 판정, 사유)` 목록. 주석·헤더는 건너뛴다. 순수 함수 — 테스트 대상.

    사유에 쉼표가 들어갈 수 있으므로 **앞 세 칸만 끊는다**(`split(",", 3)`).
    """
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(HEADER.split(",")[0] + ","):
            if not line.startswith(HEADER.split(",")[0] + ","):
                continue
            if line == HEADER:
                continue
        parts = [p.strip() for p in line.split(",", 3)]
        while len(parts) < 4:
            parts.append("")
        if parts[0] and parts[1]:
            rows.append(tuple(parts[:4]))
    return rows


def project_key(root):
    """대장의 «프로젝트» 칸 — **리포 하나가 한 줄이어야 한다.**

    ★ 왜 폴더 이름이면 안 되나 (열린 날 2026-08-14, 실측). 이 계통은 갈래마다 **워크트리를
      따로 두는** 구조를 쓴다. 폴더 이름을 키로 잡으면 **같은 리포가 갈래 수만큼 다른
      프로젝트로 세어진다** — 실측: 한 리포가 여섯 줄 집합(thermo·math·dynamics·materials·
      solids·main)을 차지했고 같은 판정을 여섯 번 적게 됐다. 더 나쁜 것은 대장이 묻는 것
      («이 프로젝트가 판정했나»)의 답이 **갈래를 옮길 때마다 «아니오» 로 뒤집힌다**는 점이다 —
      그러면 `check_floor` 의 그 항목은 영원히 ✘ 를 내고, 상시 ✘ 는 곧 안 읽는 신호가 된다.
    ★ 판정선은 **git 공통 디렉터리(`--git-common-dir`)의 부모 폴더 이름** 하나다.
      · 워크트리든 본체든 값이 같다 — 그게 «같은 리포» 의 기계적 정의다(실측: main·thermo
        워크트리 둘 다 `…/전공정리프로젝트/.bare`).
      · **워크트리를 안 쓰는 보통 리포는 값이 안 바뀐다** — `<리포>/.git` 의 부모가 곧 리포
        폴더라 예전 키(폴더 이름)와 같다. 그래서 대장에 이미 있는 다른 프로젝트의 줄은
        **한 줄도 안 건드려진다**(이 변경의 안전 조건이다).
      · git 이 아니거나 못 읽으면 **폴더 이름으로 물러난다** — 이 도구는 git 을 전제하지 않는다.
    """
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"],
                             capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
    except OSError:
        return Path(root).name
    if out.returncode == 0 and (out.stdout or "").strip():
        common = Path(out.stdout.strip())
        if not common.is_absolute():
            common = Path(root) / common
        return common.resolve().parent.name or Path(root).name
    return Path(root).name


def needs_newline(path):
    """덧붙이기 전에 **개행 한 글자**가 필요한가. 순수에 가깝게 떼어 둔다 — 테스트가 직접 부른다.

    ★ 왜 함수인가 (열린 날 2026-08-14, 실사고): 대장 마지막 줄에 개행이 없는 상태로 이어
      붙였더니 **남의 프로젝트 행 뒤에 내 첫 행이 그대로 붙었다** —
      `…자리가 없다main,규칙/AGENTS.md,,`. 그러면 둘이 한꺼번에 망가진다:
      ⑴ 그 프로젝트의 «사유» 가 조용히 오염되고
      ⑵ 내 항목 하나는 행으로 안 세어져 **미판정으로도 안 잡힌다**(파서가 첫 칸을 남의
         프로젝트 이름으로 읽는다). 즉 «빠뜨린 것» 이 화면에서 «없는 것» 과 같아진다.
    ★ 없는 파일·빈 파일은 False 다 — 맨 앞에 빈 줄을 만들 이유가 없다.
    """
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            if not fh.tell():
                return False
            fh.seek(-1, os.SEEK_END)
            return fh.read(1) != b"\n"
    except OSError:
        return False


def shared_items(shared):
    """대장이 묻는 항목 = 공용 `규칙/`·`기록/` 아래 파일들.

    **목록을 코드에 적지 않는다** — 적으면 항목이 하나 늘어난 날 이 도구만 옛 세상을 말한다.

    ★★ **`기록/` 은 2026-08-14 에 넣었다.** 그전에는 `규칙/` 만 물었고, 그래서 **«규칙»은 넘어가고
      «데인 자국»(실사고 원장)은 안 넘어갔다.** 한 프로젝트가 `AGENTS.md` 를 «안가져옴» 으로
      판정하며 [사용자 발화 인용 생략] 고 적었는데, 그 지도는 **절 제목
      수준**이라 *언제 어떻게 데였나* 는 한 줄도 안 실린다. 그래서 규칙을 지키면서도 **이미 판
      구멍을 다시 팠다(과거에 겪은 실패를 최근에 그대로 반복한 사례).
      규칙만 옮기고 사고 기록을 안 옮기면 다음 프로젝트는 그 값을 처음부터 다시 치른다.

    ★ **대장 자신은 항목이 아니다** — 「도입대장을 가져갔는가」를 묻는 칸은 뜻이 없다.
      **층 배정표(`층-배정.txt`)도 같다** — 그건 이 도구가 읽는 자기 배선이지 가져갈 규칙이 아니다.

    ★★ **피드백 원장도 뺀다 (2026-08-16, 사용자 판정으로 정본이 나루로 왔다).**
      331KB 를 복사해 가는 물건이 아니라 **조회하는 자리**이기 때문이다
      (`도구/feedback_lookup.py` — [사용자 발화 인용 생략]).
      가져가는 것이 아니므로 «가져갔나» 라는 물음이 성립하지 않는다.
      ★ 이건 **묻는 항목을 줄이는 완화가 아니다** — 원장이 하던 일(재발 판별)은 조회가
        이어받고, 오히려 프로젝트 사이까지 넓어진다. 줄어드는 것은 **복사 판정**뿐이다.
    """
    out = []
    for folder in ASK_FOLDERS:
        base = Path(shared) / folder
        if not base.is_dir():
            continue
        out.extend(folder + "/" + p.name for p in base.iterdir()
                   if p.is_file()
                   and p.name not in (LEDGER_NAME, TIER_MAP_NAME, FEEDBACK_NAME))
    return sorted(out)


def declared_tier(root):
    """`(층, 왜 아닌가)` — 리포 루트의 `프로젝트-층.txt` 를 읽는다. 순수에 가깝게.

    ★ **네 물음의 답이 없으면 선언으로 안 친다.** 숫자만 적힌 선언은 «간단해서 0층» 과
      구별되지 않는데, 그 판단형이야말로 `프로젝트-층.md` §5 가 막으려는 뒷문이다.
      이 폴더가 예외 대장마다 거는 판정선과 같다 — *사유 없는 줄은 예외로 안 친다.*
    ★ 선언이 없으면 `None` 이고, 그때는 **전부 묻는다**(옛 행동 그대로). 모르면 엄한 쪽이다.
    """
    path = Path(root) / TIER_FILE
    if not path.is_file():
        return None, "선언 파일이 없다"
    tier, answered = None, 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = [p.strip() for p in line.split(":", 1)]
        if key == "층":
            digits = "".join(c for c in val if c.isdigit())
            tier = int(digits) if digits else None
        elif val and any(k in key for k in TIER_ANSWER_KEYS):
            answered += 1
    if tier is None:
        return None, "`층: N` 줄이 없다"
    if answered < len(TIER_ANSWER_KEYS):
        return None, ("네 물음의 답이 %d개뿐이라 선언으로 안 친다 (`프로젝트-층.md` §4)"
                      % answered)
    return tier, ""


def tier_map(shared):
    """`{항목: 층}` — 공용 `기록/층-배정.txt`. 형식은 `항목 | 층 | 사유`.

    ★ **사유 없는 줄은 배정으로 안 친다** — 배정이 없는 항목은 아래 `in_scope` 에서
      **묻는 쪽**으로 떨어진다. 대장을 잃거나 새 규칙이 배정 없이 들어온 날
      **자가 조용해지지 않게** 하는 것이 요점이다(엄한 쪽으로 넘어진다).
    """
    path = Path(shared) / "기록" / TIER_MAP_NAME
    out = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3 or not parts[2]:
            continue
        digits = "".join(c for c in parts[1] if c.isdigit())
        if parts[0] and digits:
            out[parts[0]] = int(digits)
    return out


def in_scope(items, tiers, my_tier):
    """`(물을 것, 층이 높아 안 묻는 것)`. 순수 함수.

    배정이 없는 항목은 **묻는 쪽**이다 — 새 규칙이 배정을 빠뜨린 채 들어와도 조용히
    사라지지 않게. 선언이 없으면(`my_tier is None`) 전부 묻는다.
    """
    if my_tier is None:
        return list(items), []
    keep, skipped = [], []
    for item in items:
        t = tiers.get(item)
        (skipped if t is not None and t > my_tier else keep).append(item)
    return keep, skipped


def status_of(rows, project, items):
    """`(없는 행, 미판정, 사유 없는 안가져옴, 범위 밖 미판정)`. 순수 함수 — 테스트 대상.

    ★ **범위 밖은 「없애지」 않고 따로 센다** (2026-08-15, 층 배선). 층을 낮게 선언하면
      전에 만들어 둔 상위 층 행이 화면에서 사라지는데, 그러면 «판정한 것» 과 «범위에서
      빠진 것» 이 같아 보인다 — 이 폴더가 반복해 잡아 온 그 형태다.
    """
    mine = [r for r in rows if r[0] == project]
    scope = set(items)
    have = {r[1] for r in mine}
    missing = [i for i in items if i not in have]
    unjudged = [r[1] for r in mine if not r[2] and r[1] in scope]
    reasonless = [r[1] for r in mine if r[2] == "안가져옴" and not r[3] and r[1] in scope]
    parked = [r[1] for r in mine if not r[2] and r[1] not in scope]
    return missing, unjudged, reasonless, parked


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = Path(args[0] if args else ".").resolve()
    shared = Path(os.environ.get("CLAUDE_SHARED_SYSTEM")
                  or next((p for p in (Path.home() / "Documents" / "naru",
                                    Path.home() / "Documents" / "Claude")
                            if p.is_dir()), Path.home() / "Documents" / "naru"))
    path = ledger_path(shared)
    if not path.is_file():
        sys.exit("대장이 없다: %s" % path)

    project = project_key(root)          # 폴더 이름이 아니라 «리포» — 사유는 그 함수의 독스트링
    tier, why = declared_tier(root)
    items, skipped = in_scope(shared_items(shared), tier_map(shared), tier)
    text = path.read_text(encoding="utf-8", errors="replace")
    rows = parse(text)
    missing, unjudged, reasonless, parked = status_of(rows, project, items)

    if tier is None:
        print("[도입 대장] %s — 공용 항목 %d개 (층 선언 없음: %s → **전부 묻는다**)"
              % (project, len(items), why))
        print("  · 층을 선언하면 그 층 것만 묻는다 — `%s` 에 네 물음의 답과 함께"
              " (`규칙/프로젝트-층.md`)" % TIER_FILE)
    else:
        print("[도입 대장] %s — **층 %d** · 물을 항목 %d개 (층이 높아 안 묻는 것 %d개)"
              % (project, tier, len(items), len(skipped)))
    if missing:
        print("  · 대장에 **행이 없는** 항목 %d개" % len(missing))
        for item in missing:
            print("      " + item)
    if unjudged:
        print("  · 행은 있는데 **판정이 빈** 항목 %d개: %s" % (len(unjudged), ", ".join(unjudged)))
    if reasonless:
        print("  · ★ **사유 없는 «안가져옴»** %d개 — 판정으로 안 친다: %s"
              % (len(reasonless), ", ".join(reasonless)))
    if parked:
        # ★ 「안 묻기로 한 것」을 화면에서 지우지 않는다 — 지우면 «판정한 것» 과 같아 보인다.
        print("  · (범위 밖·판정 비어 있음 %d개 — 층이 오르면 다시 물어야 한다: %s)"
              % (len(parked), ", ".join(parked)))
    if not (missing or unjudged or reasonless):
        print("  · 전부 판정됨")

    if "--apply" in flags and missing:
        # ★ 먼저 **파일이 개행으로 끝나는지** 본다 (열린 날 2026-08-14, 실사고).
        #   그냥 이어 붙였더니 대장 마지막 줄에 개행이 없어서 **남의 프로젝트 행 뒤에
        #   내 첫 행이 그대로 붙었다** — `…자리가 없다main,규칙/AGENTS.md,,` (knu-rl-2026 행).
        #   그러면 ⑴ 그 프로젝트의 «사유»가 조용히 오염되고 ⑵ 내 항목 하나는 행으로 안 세어져
        #   **미판정으로도 안 잡힌다**(파서가 `parts[0]` 를 그 프로젝트 이름으로 읽는다).
        #   덧붙이기만 하는 도구라 통째로 다시 쓰지 않는 것이 원칙이므로, **한 글자만 더 쓴다.**
        tail = "\n" if needs_newline(path) else ""
        with open(path, "a", encoding="utf-8", newline="") as fh:
            if tail:
                fh.write(tail)
            for item in missing:
                fh.write("%s,%s,,\n" % (project, item))
        print("[도입 대장] 빈 행 %d개를 덧붙였다 — **판정은 사람이 채운다**" % len(missing))
    elif missing:
        print("  (--apply 로 빈 행을 만든다. 판정은 기계가 절대 안 찍는다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
