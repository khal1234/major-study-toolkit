# -*- coding: utf-8 -*-
"""피드백 원장 **조회** — 「이거 전에도 났나」를 원장 전문을 읽지 않고 묻는다 (신설 2026-08-16).

    python 도구/feedback_lookup.py "<지적 요지>"
    python 도구/feedback_lookup.py "<지적 요지>" --top=8

**왜 이 도구인가** (사용자 제안 2026-08-16):

    *"feedback은 지적을 계속 누적시켜서 이거 이전에도 발생했나 안했나를 판별할 수 있게
    도와주는 장치 아닌가? 그러면 이걸 처음에 다 읽어오는 게 아니라 나루한테 보내던가 해서
    유사한 게 있는지만 체크하고 훅처럼. 유사한 게 있으면 그 부분만 확실히 있고 약간 좀
    다른 거라면 인스턴스 추가. 일치한다고 볼 만하다면 부류로 갱신"*

★★ **원장은 「복사하는 물건」이 아니라 「조회하는 자리」다.** 323KB 를 세션마다 읽는 것은
   불가능하고, 안 읽으면 원장이 있어도 재발을 못 가린다. 조회가 그 사이를 잇는다.
   → 그래서 이 원장은 **도입 대장의 항목이 아니다**(`adopt_ledger.shared_items` 가 뺀다).
   가져가는 것이 아니라 물어보는 것이라, «가져갔나» 라는 물음이 성립하지 않는다.

★ **세 갈래는 사람이 고른다** — 이 도구는 후보와 점수만 낸다.

    없음  → 새 부류. 원장에 행 신설
    유사  → **인스턴스 추가.** 기존 행에 붙인다
    일치  → **부류로 갱신.** 재발이므로 규칙 7⑷ 대로 «왜 또 났나 + 기계 방지» 까지 답한다

  셋째가 이 도구의 값어치 전부다. 지금 「재발인가」는 **사람의 기억**에 걸려 있는데,
  그건 세션이 갈리면 끊긴다. 점수를 판정으로 읽지 말 것 — 어휘만 겹치는 남남이 늘 섞인다
  (같은 판정선: `audit_conventions` [L] 절이 후보만 내고 판정을 사람에게 남기는 이유).

★ **트리거는 아직 반쪽이다.** 「지적을 받았을 때」는 관측 가능한 사건이 아니다(판단형).
  지금 닿는 선은 `audit_session_conduct` 가 커밋 때 세는 *「지적을 받았는데 원장·기억이
  안 움직였다」* 까지다. 완전 자동이 아니라는 것을 여기 밝혀 둔다.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LEDGER_NAME = "feedback-ledger.md"


def shared_root():
    """공용 시스템(나루)의 자리. 옛 이름 `Claude` 도 본다."""
    env = os.environ.get("CLAUDE_SHARED_SYSTEM")
    if env:
        return Path(env)
    for p in (Path.home() / "Documents" / "naru", Path.home() / "Documents" / "Claude"):
        if p.is_dir():
            return p
    return Path.home() / "Documents" / "naru"


def find_ledger():
    """원장을 **찾는다 — 경로를 코드에 박지 않는다.**

    ★★ **이식 첫날 이 자가 남의 리포에서 죽었다 (2026-08-16).** `기록/feedback-ledger.md`
      를 글자로 박아 뒀는데 전공정리는 그 원장이 `docs/` 에 있어 *"원장이 없다"* 로 끝났다.
      아침에 `check_narration` 이 `ROOT.parent` 로 겪은 것과 **같은 부류**다 —
      **이식할 때 경로 전제를 다시 안 잰 것.** 이 저장소는 처방을 이미 갖고 있었다
      (`scan_private.LEDGER_NAMES` — *"대장은 프로젝트마다 자리가 다르다. 찾아서 쓴다"*).

    ★ 찾는 순서가 곧 판정이다 — **정본이 먼저다.** 원장의 정본은 2026-08-16 부터 나루이고,
      다른 프로젝트가 이 자를 돌리는 목적은 *«프로젝트 사이 재발»* 을 보는 것이라
      자기 사본을 보면 뜻이 없다. 나루가 없는 기계에서만 자기 리포에서 찾는다.
    """
    cand = [shared_root() / "기록" / LEDGER_NAME]
    for base in (ROOT, ROOT / "기록", ROOT / "docs", ROOT / "out"):
        cand.append(base / LEDGER_NAME)
    for c in cand:
        if c.is_file():
            return c
    return None
# 행의 첫 칸은 날짜다. 표 머리·구분선과 산문을 이걸로 가른다.
# ★ 날짜 칸에 꼬리가 붙은 행도 읽는다 — «(등재 2026-08-16 …)» · «· **재발 2026-08-12**»
#   (2026-08-16 실사고: 이관된 행 넷이 조회기에 안 잡혀, AGENTS 가 가리키는 그 행을
#    「원장에 없다」고 읽었다. 날짜는 칸의 **앞**에 있으면 된다.)
ROW = re.compile(r"^\|\s*(20\d\d-\d\d-\d\d)[^|]*\|")
# 점수는 **글자 2-gram 겹침**이다. 한국어라 낱말 단위로 자르면 조사 때문에 안 맞는다.
# ★ 이 방식을 고른 이유는 이 저장소가 이미 쓰고 있어서다(`audit_conventions` [L]) —
#   같은 질문에 답하는 자가 둘이면 갈린다.
NGRAM = 2

# ★★ **원장은 한 형식이 아니다** (열린 날 2026-08-25 — 이 자의 **같은 부류 두 번째**).
#   앞부분은 표(2026-08-21 까지)이고 그 뒤는 **산문 절**(`## 날짜 — 제목`)이다.
#   이 자는 표만 읽어서 **08-22 이후 적힌 것이 통째로 안 보였다.** 실사고: 사용자가
#   *"누누이 얘기하잖아"* 라고 한 지적을 조회하니 **최고 0.35(불일치)** 가 나왔다 —
#   사용자는 재발이라는데 **기계는 초범으로 봤다.** 위 `ROW` 주석의 실사고
#   («이관된 행 넷이 안 잡혀 「원장에 없다」고 읽었다») 와 부류가 같다:
#   **자가 원장의 일부만 보면 「없다」가 「못 봤다」가 된다.**
#   ☐ 못 보는 것: 날짜 없는 `##` 절은 그대로 안 읽는다 — 그건 부류 행이 아니라 문서 구조다.
SEC = re.compile(r"^##\s+(20\d\d-\d\d-\d\d)\s*[^\w]*\s*(.*)$")


def grams(text):
    t = re.sub(r"[\s·|*`\[\]()]+", "", text)
    return {t[i:i + NGRAM] for i in range(len(t) - NGRAM + 1)}


def _sec_row(sec):
    """산문 절을 **표 행과 같은 모양**으로 — 인쇄부가 `cells[2]=지적 · [3]=부류` 를 쓴다.

    제목을 「지적」 자리에 두는 이유: 이 원장의 산문 절은 제목이 곧 그 사고의 요지다.
    """
    date, title, body = sec
    return (date, ["", "", title, " ".join(l.strip() for l in body if l.strip())])


def split_cells(line):
    """표 한 줄을 칸으로 가른다 — **백틱 안의 `|` 는 구분자가 아니다.** 순수 함수.

    ★ 열린 날 2026-08-06, 이 자의 첫 실행에서 스스로 걸렸다. 그냥 `line.split("|")` 로
      갈랐더니 `` `a | b` `` 처럼 백틱 안에 파이프가 든 행에서 열이 통째로 밀렸고,
      **이미 검사 이름을 지목하고 있는 행 3건이 '이름 없음'으로 신고**됐다.
      잔량 32건 중 상당수가 그 유령이었다 — 자가 틀리면 잔량이 부풀고, 부푼 잔량은
      갚을 순서를 잘못 세우게 한다.

    ★★ **전공정리 `tools/buildlib/ledger.py` 에서 그대로 옮겨 왔다 (2026-08-26).**
      같은 원장을 읽는 자가 둘인데 한쪽만 고치면 다음 미러에서 되돌아온다 —
      **두 자는 같은 판이어야 한다.** 이 원장은 표 행 258개 중 **220개**가 백틱 안에
      파이프를 갖고 있어서, 밀린 칸은 예외가 아니라 기본값이었다.
    """
    cells, buf, in_tick = [], [], False
    for ch in line:
        if ch == "`":
            in_tick = not in_tick
        if ch == "|" and not in_tick:
            cells.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    cells.append("".join(buf))
    return cells


def table_cells(line):
    """표 한 줄의 **칸만** — 바깥 `|` 가 만드는 빈 칸을 떼고 좌우 공백을 다듬는다."""
    cells = split_cells(line.strip())
    if cells and not cells[0].strip():
        cells = cells[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return [c.strip() for c in cells]


def rows(text):
    """`(날짜, 칸들)` 목록 — **표 행과 산문 절을 둘 다** 읽는다. 순수 함수."""
    out, sec = [], None
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            out.append((m.group(1), table_cells(line)))
            continue
        d = SEC.match(line)
        if d:
            if sec:
                out.append(_sec_row(sec))
            sec = (d.group(1), d.group(2).strip(), [])
            continue
        if line.startswith("#"):        # 날짜 없는 머리 — 절이 거기서 끝난다
            if sec:
                out.append(_sec_row(sec))
            sec = None
            continue
        if sec is not None:
            sec[2].append(line)
    if sec:
        out.append(_sec_row(sec))
    return out


def score(query_grams, cells):
    """겹친 2-gram 수 / 질의 2-gram 수. 0~1.

    ★ **행 길이로 나누지 않는다.** 이 원장의 행은 한 줄이 문단이라, 길이로 나누면
      **길게 적힌 행일수록 점수가 낮아진다** — 잘 적힌 행이 밀려나는 셈이다.
    """
    if not query_grams:
        return 0.0
    return len(query_grams & grams(" ".join(cells))) / float(len(query_grams))


def cut(text, n):
    text = re.sub(r"\s+", " ", re.sub(r"[*★`]", "", text)).strip()
    return text if len(text) <= n else text[:n - 1] + "…"


def selftest():
    """★ 붙임 2026-08-25 — 이 자에는 **대조군이 없었다.**

    「겹치는 행 없음」을 내는 자라 특히 위험하다: 원장의 일부만 읽어도 **깨끗한 0건과
    겉모습이 같다**(공용 「규칙/증거의-정직.md」 ⑴). 실제로 08-22 이후 절이 통째로
    안 읽히던 것을 **사용자 지적이 나서야** 알았다 — 그래서 양성 대조군이 핵심이다.
    """
    bad = 0

    def chk(desc, cond, got=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %-46s %s" % ("OK  " if cond else "**틀림**", desc, got))

    L = chr(10)
    text = ("| 날짜 | 누구 | 지적 | 부류 | a | b | 상태 |" + L +
            "| 2026-08-01 | x | 표에적힌지적 | 표부류 | | | 열림 |" + L + L +
            "## 2026-08-02 — 산문에적힌지적" + L + L +
            "- 본문에 오직여기만있는낱말 이 있다" + L + L +
            "## 날짜없는머리" + L +
            "이 절은 안 읽는다" + L)
    got = rows(text)
    chk("★ 양성 — **표와 산문을 둘 다** 읽는다 (한쪽만 읽으면 「없다」가 거짓이 된다)",
        len(got) == 2, "%d개" % len(got))
    chk("산문 절의 제목이 「지적」 자리에 온다",
        got[-1][1][2] == "산문에적힌지적" if len(got) == 2 else False, str(got[-1:]))
    chk("날짜 없는 `##` 절은 안 읽는다 (부류 행이 아니라 문서 구조다)",
        all("날짜없는머리" not in " ".join(c) for _, c in got))

    # ★ 이것이 실제로 터진 자리다 — 산문에만 있는 낱말로 조회했을 때 잡히는가.
    q = grams("오직여기만있는낱말")
    best = max(score(q, c) for _, c in got)
    chk("★ 양성 — **산문 본문**의 낱말로 조회해도 잡힌다 (2026-08-25 실사고)",
        best > 0, "%.2f" % best)
    q2 = grams("표에적힌지적")
    chk("음성 대조 — 표 행도 여전히 잡힌다 (산문을 붙이며 표를 깨지 않았나)",
        max(score(q2, c) for _, c in got) > 0)

    # ★ 백틱 안의 파이프 (이식 2026-08-26). 이 원장은 표 행 258개 중 220개가 백틱 안에
    #   파이프를 갖고 있어서, 여기가 밀리면 「지적」·「상태」 칸이 통째로 남의 칸을 가리킨다.
    tick = ("| 2026-08-03 | u | " + chr(96) + "a | b" + chr(96) +
            " 가 든 지적 | 부류 | 범위 | " + chr(96) + "기계" + chr(96) + " | 열림 |")
    cells = rows(tick)[0][1]
    chk("★ 백틱 안의 `|` 는 구분자가 아니다 — 칸이 안 밀린다",
        len(cells) == 7 and cells[-1] == "열림" and cells[2].endswith("가 든 지적"),
        "%d칸 · 상태=%s" % (len(cells), cells[-1] if cells else "—"))
    chk("음성 대조 — 그냥 `split(\"|\")` 였다면 8칸으로 밀렸다",
        len(tick.strip().strip("|").split("|")) == 8 and len(cells) == 7,
        "%d칸" % len(tick.strip().strip("|").split("|")))

    print()
    print("  ※ ☐ 이 자가 **못 보는 것**: 점수는 글자 2-gram 겹침이라 **뜻을 모른다.**")
    print("     낱말이 다르면 같은 부류도 0 이 나온다 — 「없음」은 사람이 다시 본다.")
    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="*", help="지적 요지")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        print("[자기 검정] 원장 조회")
        return selftest()

    query = " ".join(a.query).strip()
    if not query:
        sys.exit("무엇을 찾을지 적어야 한다: feedback_lookup.py \"<지적 요지>\"")
    ledger = find_ledger()
    if ledger is None:
        sys.exit("원장을 못 찾았다 — 정본은 나루의 `기록/%s` 다"
                 " (다른 자리에 있으면 `CLAUDE_SHARED_SYSTEM` 으로 알린다)" % LEDGER_NAME)

    found = rows(ledger.read_text(encoding="utf-8", errors="replace"))
    ranked = sorted(((score(grams(query), c), d, c) for d, c in found), reverse=True)
    hits = [(s, d, c) for s, d, c in ranked[:a.top] if s > 0]

    print("[원장 조회] \"%s\" — 행 %d개 중 상위 %d개  ※ **점수는 판정이 아니다**"
          % (cut(query, 40), len(found), len(hits)))
    if not hits:
        print("  · 겹치는 행 없음 → **새 부류**로 보고 행을 신설한다")
        return 0
    for s, date, cells in hits:
        지적 = cells[2] if len(cells) > 2 else ""
        부류 = cells[3] if len(cells) > 3 else ""
        상태 = cells[-1] if len(cells) > 6 else ""
        print("\n  %.2f  %s  [%s]" % (s, date, cut(상태, 20)))
        print("        지적 %s" % cut(지적, 100))
        print("        부류 %s" % cut(부류, 100))
    print("\n  → 세 갈래는 **사람이 고른다**: 없음(행 신설) · 유사(인스턴스 추가) ·"
          " 일치(**부류로 갱신** — 재발이라 기계 방지까지 답한다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
