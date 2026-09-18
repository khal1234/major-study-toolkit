# -*- coding: utf-8 -*-
"""피드백 원장(`docs/feedback-ledger.md`)을 기계가 읽는 자.

★ 열린 날 2026-08-06 — 사용자 지적:
  *[발화 생략]*

**맞다. 그리고 그날 실제로 터졌다.** C31(이해도 체크의 답에 뒤 장을 넣지 않는다)은 인박스에
*[발화 생략]* 로만 적혀 있었고, 그래서 인스턴스는 사라졌지만 **다시 써도 막는 것이
없었다.** 같은 상태의 항목이 그날 실측으로 **26곳**이었다(원장 6 · 인박스 18 · 워크오더 2).

AGENTS 는 이미 *[발화 생략]* 고 못 박아 두었다.
**문제는 그 문장을 아무도 검사하지 않는다는 것이다** — 사람이 지키기로 한 규율이라
안 지켜도 티가 안 난다. 그래서 원장 자체를 기계가 읽게 한다.

순수 함수만 둔다 — 테스트(`test_checks.py`)와 `close_report.py` 가 같은 판정을 공유한다.
두 벌로 쓰면 그게 곧 갈라짐이다(이 리포가 여러 번 겪은 형태).
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _shared_root():
    """공용 폴더(공용 시스템) 폴더 — 있으면 Path, 없거나 못 읽으면 `None`. 순수 함수가 아니라 IO다.

    ★ 열린 날 2026-09-01 — 공용 폴더가 **자기 자신을 대상으로 닫은** 첫 원장 행에서 드러났다
    (`도구/check_relay.py`, 기계 칸이 공용 폴더 자신을 가리킴). `source_blob` 이 이 리포의
    `tools/`·`.claude/hooks/` 만 훑어서, **실재하는 장치인데 유령으로 신고됐다.**
    공용 폴더 자신의 `도구/`·`훅/` 도 「실행 증거」 후보에 넣는다 — `.claude/hooks/shared_sync_check`
    의 `SHARED` 를 그대로 쓴다(둘 다 보고 환경변수를 존중하는 유일한 자리, CLAUDE.md 참조).
    """
    hooks = os.path.join(ROOT, ".claude", "hooks")
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    try:
        import shared_sync_check as _ssc
    except Exception:                      # noqa: BLE001 — 훅이 없어도 리포 소스는 그대로 훑는다
        return None
    return _ssc.SHARED if _ssc.SHARED.is_dir() else None


# 공용 폴더 자신을 대상으로 닫은 원장 행의 「기계」가 살 수 있는 곳 — `SOURCE_DIRS` 와 같은 형태이되
# `_shared_root()` 기준 상대경로다. 못 찾아도 조용히 빠진다(선택 확장이지 필수 조건이 아니다).
SHARED_SOURCE_DIRS = (("도구", (".py",)), ("훅", (".py",)))

# ★★ **여기가 얼어붙은 사본을 보고 있었다** (고친 날 2026-08-26).
#   `LEDGER` 에 `docs/feedback-ledger.md` 를 글자로 박아 뒀는데, 그 파일 **머리에**
#   *[발화 생략]* 가 적혀 있다.
#   같은 함수를 두 파일에 걸어 잰 실측: **사본(395줄) 0건 · 정본(863줄) 3건.**
#   그래서 `test_ledger_closed_rows_name_a_real_machine` 과 `close_report` 의 「승격 잔량」이
#   **둘 다 정본을 안 봐서 영원히 초록**이었다 — 폴백을 든 자가 *[발화 생략]* 를
#   *[발화 생략]* 으로 찍는, 이 리포가 `audit_problem_originality.PDF_FOR` 에서 이미 한 번 닫은 부류다.
# ★ **경로를 새로 적지 않는다.** `feedback_lookup.find_ledger()` 가 이미 «정본 먼저, 없으면
#   자기 리포» 순서를 갖고 있다(그 함수 독스트링이 그 판정의 정본이다). 두 벌로 적으면
#   그게 곧 갈라짐이고, 이 파일 머리말이 순수 함수만 두기로 한 이유와 같다.
FALLBACK_LEDGER = os.path.join(ROOT, "docs", "feedback-ledger.md")


def resolve_ledger():
    """`(경로, 정본인가)` — **둘째 값이 이 함수의 절반이다.**

    공용 폴더가 없는 배치에서는 사본으로 떨어져야 한다(그 기계에서 자가 죽으면 안 된다).
    그런데 **조용히 떨어지면 0건이 «없다» 로 읽힌다** — 그게 이 결함의 본체였다.
    그래서 부르는 자리가 «정본을 못 봤다» 를 찍을 수 있도록 사실을 함께 돌려준다.
    """
    try:
        tools = os.path.join(ROOT, "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        import feedback_lookup                                                  # noqa: E402
        found, shared = feedback_lookup.find_ledger(), feedback_lookup.shared_root()
    except Exception:                          # noqa: BLE001 — 조회기가 없어도 이 자는 돈다
        return FALLBACK_LEDGER, False
    if found is None:
        return FALLBACK_LEDGER, False
    path, base = os.path.abspath(str(found)), os.path.abspath(str(shared))
    try:
        canonical = os.path.commonpath([path, base]) == base
    except ValueError:                         # 드라이브가 다르면 공통 경로 자체가 없다
        canonical = False
    return path, canonical


LEDGER, LEDGER_IS_CANONICAL = resolve_ledger()


def ledger_source_note(text=None):
    """어느 원장을 **얼마나** 쟀는지. 정본을 못 봤으면 그 사실이 맨 앞에 온다.

    부르는 자리가 둘(`close_report` 의 「승격 잔량」·이 파일의 CLI)이라 문구를 한 자리에 둔다 —
    두 벌로 쓰면 한쪽만 고쳐지고, 그러면 다시 한쪽이 조용해진다.

    ★★ **`text` 를 주면 「분모」를 같이 낸다** (열린 날 2026-08-26). 부류 이름은 공용 폴더가
      세 프로젝트에서 13건을 세고 붙였다 — **«자가 자기 입력을 못 잡았는데, 그 사실이 결과에
      안 나온다».** 원인은 일곱 갈래로 다른데(선언이 빔 · 경로 불일치 · **형식의 절반만 읽음** ·
      정규식이 대상 언어를 못 자름 · 값 개명 · 필터 오류 · 플래그로 벙어리) **결과가 같다.**
      처방도 하나로 모인다: **자는 자기 분모를 같이 낸다. 분모가 0이거나 기대보다 작으면
      그건 판정이 아니라 미완이다.** 이 리포에 이미 그렇게 하는 자가 둘 있다 —
      `audit_problem_originality` 의 「대조 가능성」 줄 · `scan_private` 의 «실제로 읽은 파일 99개».
    """
    where = LEDGER
    if where.startswith(ROOT):
        where = os.path.relpath(where, ROOT).replace("\\", "/")
    if LEDGER_IS_CANONICAL:
        note = "원장 정본을 쟀다 — " + where
    else:
        note = ("★ **정본을 못 봤다** — 공용 폴더 「기록/feedback-ledger.md」 를 못 찾아 사본(%s)으로 "
                "쟀다. 이 수는 «없다» 가 아니라 «거기까지는 없다» 이다(규칙 11)." % where)
    if text is None:
        return note
    tables, sections, stated = ledger_counts(text)
    odd = odd_tick_lines(text)
    # ★ **백틱 홀수로 물러난 줄을 여기서 신고한다** (2026-08-26). 0 이어도 적는다 —
    #   안 적으면 「0줄」과 「아예 안 쟀다」가 화면에서 같아지고, 그게 이 파일이 세 번째로
    #   닫는 병이다. 고치는 것은 원장 주인의 몫이고 이 자는 **넘어지지 않고 보고**만 한다.
    out = note + ("\n   읽은 것 — 표 행 %d개 · 산문 절 %d개 (합계 %d) · 그중 상태를 적은 "
                  "산문 절 %d개 · 백틱 홀수로 생짜 split 한 줄 %d개"
                  % (tables, sections, tables + sections, stated, len(odd)))
    for i, ln in odd[:5]:
        out += "\n     ↳ %d행 — 짝 없는 백틱: %s" % (i, " ".join(ln.split())[:70])
    return out + "\n   " + source_note()

# 닫힘으로 볼 수 없는 말. 이 낱말이 `기계 방지` 칸의 **산문**에 있으면 아직 안 닫힌 것이다.
#
# ★ `후보` 는 뺐다 (2026-08-06, 첫 실행의 실측으로 정정). 이 리포는 *[발화 생략]* 처럼
#   **검사 이름 안에서도** 그 낱말을 쓰기 때문에, 후보를 실패 신호로 삼으면 이미 구현된 행이
#   무더기로 걸린다. 실제로 잔량이 부풀었다. 미완을 뜻하는 말은 `미구현`·`미정` 이다.
UNCLOSED_WORDS = ("미구현", "미정")
# 검사로 만들 수 없다고 **명시**한 행. AGENTS 규칙 11 은 *[발화 생략]* 를 허용하므로, 이렇게 적고 대체 조치를 남긴 행은 닫힌 것으로 본다.
# 조용히 비워 두는 것과 못 한다고 적는 것은 다르다 — 이 자가 가르려는 것이 정확히 그 차이다.
NOT_MECHANIZABLE = ("기계 판정 불가", "만들지 않았다", "만들지 않는다")
# ★ **부분 닫힘**은 닫힘이 아니다 (2026-08-06 실측으로 정정). 이 원장은 *[발화 생략]* 을 `부분 닫힘` 으로 정직하게 적어 왔는데, 상태 칸에 '닫힘' 글자가 들어 있어
#   완전 닫힘으로 읽혔다. **이미 정직하게 적은 행을 잡는 자는 정직을 벌하는 자다** —
#   그러면 다음 사람은 `부분 닫힘` 대신 그냥 `닫힘` 이라 적게 된다(자가 행동을 바꾼다).
PARTIAL_WORDS = ("부분 닫힘", "일부 닫힘", "인스턴스만")


# ★ **막을 결함이 없는 행에는 막을 장치를 요구하지 않는다** (2026-08-06 실측으로 신설).
#   원장에는 결함 기록만 있는 게 아니다 — 범위를 정한 행, 질문에 답한 행, 재보고 결과
#   *[발화 생략]* 로 닫은 행이 섞여 있다(실측 3건). 그런 행에 검사 이름을 요구하면
#   **없는 결함을 막는 장치를 지어내게 된다** — 이 자가 없애려는 '칸만 채우기' 그 자체다.
NO_DEFECT_WORDS = ("결함 아님", "결함이 아님", "(결정)", "질문 해소", "선택 대기")


def is_fully_closed(status):
    """상태 칸이 **완전 닫힘**이고 **결함 기록**인가. 순수 함수."""
    if any(w in status for w in NO_DEFECT_WORDS):
        return False
    return "닫힘" in status and not any(w in status for w in PARTIAL_WORDS)
_DATE = re.compile(r"^\s*20\d\d-\d\d-\d\d")
# 칸 안에서 이름으로 볼 것 — 백틱으로 감싼 식별자와 `C12` 같은 검사 번호.
_BACKTICK = re.compile(r"`([^`]+)`")
# ★ 이름으로 셀 것은 **밑줄이 든 식별자나 `.py` 파일명**뿐이다. 백틱은 단위·기호·JSON 키에도
#   쓰여서(`rpm`·`Z`·`plot`) 아무 백틱이나 이름으로 세면 **칸을 채웠다는 착각**만 준다 —
#   실측에서 `rpm` 이 '지목한 이름'으로 잡혀 이 자가 오탐을 냈다(2026-08-06).
_IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_.]*(?:_[A-Za-z0-9_.]+)+|[A-Za-z_][A-Za-z0-9_]*\.py")
_CHECK_NO = re.compile(r"\bC\d{1,2}\b")
# 이 날짜 **이후**에 닫은 행부터 이름을 요구한다. 그 전 행은 잔량이고 `pending_ledger_rows()`
# 가 센다 — 이 리포의 strict 승격 방식 그대로다(한꺼번에 error 로 박으면 되돌릴 근거도 없이
# 19행을 급하게 채우게 되고, 그건 이 검사가 없애려는 '칸만 채우기' 와 같은 짓이다).
LEDGER_STRICT_FROM = "2026-08-06"


def has_odd_ticks(line):
    """백틱 개수가 홀수인가 — **짝이 안 맞는 줄**. 순수 함수."""
    return line.count("`") % 2 == 1


def odd_tick_lines(text):
    """표 줄 중 백틱이 홀수인 것 `[(줄번호, 줄)]`. 순수 함수 — **이 자의 신고 창구**.

    `split_cells` 가 물러난 사실을 **삼키지 않기 위해** 있다. 조용히 물러나면
    「못 본 것을 통과로 찍는」 부류가 되고, 그건 이 파일이 이미 두 번 닫은 병이다
    (얼어붙은 사본 · 형식의 절반). 세는 자리는 `ledger_source_note` 의 분모 줄이다.
    """
    return [(i, ln) for i, ln in enumerate(text.splitlines(), 1)
            if ln.lstrip().startswith("|") and has_odd_ticks(ln)]


def split_cells(line):
    """표 한 줄을 칸으로 가른다 — **백틱 안의 `|` 는 구분자가 아니다.** 순수 함수.

    ★ 열린 날 2026-08-06, 이 자의 첫 실행에서 스스로 걸렸다. 그냥 `line.split("|")` 로
      갈랐더니 `` `a | b` `` 처럼 백틱 안에 파이프가 든 행에서 열이 통째로 밀렸고,
      **이미 검사 이름을 지목하고 있는 행 3건이 '이름 없음'으로 신고**됐다.
      잔량 32건 중 상당수가 그 유령이었다 — 자가 틀리면 잔량이 부풀고, 부푼 잔량은
      갚을 순서를 잘못 세우게 한다.

    ★★ **백틱이 홀수면 생짜 `split("|")` 로 물러난다** (고친 날 2026-08-26).
      **무엇이 새어나갔나:** 짝 없는 여는 백틱 하나가 있으면 `in_tick` 이 열린 채 줄이
      끝나고 **뒤의 파이프를 전부 삼킨다.** 실측(원장 2026-08-14 「발행 페이지에 개발
      주석이 통째로 실린다」 행): 파이프 다섯이 삼켜져 4칸이 됐고, `table_rows` 의
      「칸 5개 이상」 문턱에서 **그 행이 조용히 사라졌다** — 두 자가 258 대 257 로 갈린
      원인이 그것이다. 사라진 행은 위반이어도 위반으로 안 잡힌다.
    ★ **왜 「물러난다」가 맞나:** 백틱이 짝이 안 맞는 줄에서는 «백틱 안»이라는 개념 자체가
      성립하지 않는다. 성립하지 않는 규칙을 계속 적용하면 답이 틀리는 정도가 아니라
      **행이 통째로 없어진다.** 생짜 split 은 백틱 안의 파이프에서 칸이 밀릴 수 있지만,
      **밀린 행은 남아서 보이고 없어진 행은 안 보인다.**
    ☐ **못 하는 것:** 어느 백틱이 짝을 잃었는지는 이 자가 모른다. 그래서 고치지 않고
      `odd_tick_lines()` 로 **신고만** 한다 — 원장 본문은 그 원장의 주인이 판정한다.
    """
    if has_odd_ticks(line):
        return line.split("|")
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


def table_rows(text):
    """원장 **표**의 데이터 행을 (날짜, 기계 방지, 상태, 지적)으로 흘린다. 순수 함수.

    ★ 칸을 **뒤에서** 센다. 가운데 칸에는 코드·표가 들어가 구분자가 더 있을 수 있어서,
      앞에서 세면 행마다 어긋난다. 상태는 언제나 마지막 칸이고 기계 방지는 그 앞이다.
    """
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        parts = split_cells(line)
        if len(parts) < 5 or not _DATE.match(parts[1]):
            continue                      # 표제행·구분선·다른 표
        # 넷째 값은 **지적 요약**이다 — 잔량을 판정하려면 그 행이 무엇에 대한 것인지 알아야 한다.
        yield (parts[1].strip(), parts[-3].strip(), parts[-2].strip(),
               parts[3].strip() if len(parts) > 4 else "")


# ★★ **원장은 한 형식이 아니다** (열린 날 2026-08-26 — 이 자의 같은 부류 **두 번째**).
#   앞부분은 표(~2026-08-23)이고 그 뒤는 **산문 절**(`## 날짜 — 제목`)이다. 실측:
#   **표 행 258개 · 산문 절 20개**이고 산문 절은 **전부 판정 창(2026-08-06) 안**에 든다.
#   경로를 정본으로 돌린 그 배치가 «위반 0건» 을 찍었는데 그 0 은 **표만 본 수**였다 —
#   경로만 맞히고 형식의 절반을 못 읽는, 방금 고친 결함의 바로 옆자리다.
# ★ **절을 어디서 끊고 날짜·제목·본문을 어떻게 가르는지는 `feedback_lookup` 이 정본이다.**
#   여기서 다시 정하지 않는다 — `resolve_ledger` 가 경로를 그 자에게 맡긴 것과 같은 이유다.
#   ☐ 못 하는 것: `fl.rows()` 의 **표** 부분은 그래도 안 쓴다. 그쪽 결함(`line.split("|")` 이라
#     백틱 안의 `|` 에서 칸이 밀린다 — 이 파일 `split_cells` 가 2026-08-06 에 닫았다)은
#     **2026-08-26 에 그 자에게 이식해 닫혔지만**, 두 자가 세는 것이 아직 다르다:
#     그 자는 `ROW` 에 맞는 줄을 다 세고(**258**), 이 자는 **칸 5개 이상**만 센다(**257**).
#     갈리는 한 줄은 **백틱이 홀수인 행**(2026-08-14 「발행 페이지에 개발 주석이 통째로
#     실린다」) 하나다 — 안 닫힌 백틱 뒤로 `in_tick` 이 열린 채 끝나 파이프 다섯을 통째로
#     삼키고 4칸이 된다. **부류로 안 닫았다**: 처방이 둘이고(원장의 안 닫힌 백틱을 닫는다 /
#     홀수면 생짜 split 로 물러난다) 어느 쪽인지는 사람이 판정한다.
# 산문 절이 쓰는 칸 이름은 표와 같다(`**부류(원칙):**`·`**범위:**`·`**기계:**`).
_SEC_MACHINE = re.compile(r"\*\*기계[^*]{0,24}\*\*[:：]?\s*(.*?)(?=- \*\*|$)", re.S)
# 상태는 제목 끝의 대괄호 표시다 — `[닫힘]`·`[부분 닫힘]`·`[열림]`.
_SEC_STATUS = re.compile(r"\[([^\[\]]{0,24}(?:닫힘|열림)[^\[\]]{0,24})\]")


def section_rows(text):
    """**산문 절**을 표 행과 같은 (날짜, 기계 방지, 상태, 지적)으로. 순수 함수."""
    try:
        tools = os.path.join(ROOT, "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        import feedback_lookup                                                  # noqa: E402
        parsed = feedback_lookup.rows(text)
    except Exception:                      # noqa: BLE001 — 조회기가 없어도 표는 읽힌다
        return
    for date, cells in parsed:
        # 산문 절만 고른다. `_sec_row` 가 앞 두 칸을 비워 두므로 그것이 표식이다
        # (표 행은 첫 칸이 날짜라 절대 비지 않는다 — `ROW` 정규식이 그것을 요구한다).
        if len(cells) != 4 or cells[0] or cells[1]:
            continue
        title, body = cells[2], cells[3]
        status = _SEC_STATUS.search(title)
        machine = _SEC_MACHINE.search(body)
        yield (date, (machine.group(1).strip() if machine else ""),
               (status.group(1).strip() if status else ""), title)


def ledger_rows(text):
    """원장의 **모든** 항목 — 표 행 + 산문 절. 순수 함수."""
    for row in table_rows(text):
        yield row
    for row in section_rows(text):
        yield row


def ledger_counts(text):
    """`(표 행, 산문 절, 상태를 적은 산문 절)` — 자가 낼 **분모**. 순수 함수.

    셋째 값이 있는 이유: 산문 절은 상태 칸을 거의 안 적는다(실측 20개 중 1개). 상태가 없으면
    `is_fully_closed` 가 False 라 닫힘 검사가 안 걸리는데, 그것은 **「통과」가 아니라
    「판정 대상이 아님」**이다. 그 둘이 화면에서 같아 보이면 이 자가 고치려는 부류 그 자체다.
    """
    tables = sum(1 for _ in table_rows(text))
    secs = list(section_rows(text))
    return tables, len(secs), sum(1 for r in secs if r[2])


def closed_rows_without_machine(text, since=LEDGER_STRICT_FROM):
    """`닫힘` 인데 기계 방지 칸이 **말로만** 채워진 행. 순수 함수.

    판정 둘을 한 자로 본다 — 둘 다 '닫혔다고 적었지만 다음에 막을 것이 없다'는 같은 결함이다.
      ⑴ 칸에 `미정`·`후보` 가 있다 → 그건 계획이지 장치가 아니다.
      ⑵ 칸에 이름이 하나도 없다 → 무엇이 막는지 지목하지 못하면 확인할 방법이 없다.

    `since` 이전 행은 잔량이라 여기서 세지 않는다(`pending_ledger_rows()` 가 센다).
    """
    out = []
    for date, machine, status, topic in ledger_rows(text):
        if not is_fully_closed(status) or (since and date < since):
            continue
        # ★ 백틱 안은 **인용**이지 이 행의 상태 선언이 아니다. 검사 자신을 설명하는 행이
        #   `미정`·`후보` 를 인용하면서 스스로에게 걸렸다(2026-08-06 실측, 이 검사의 첫 실행).
        prose = _BACKTICK.sub(" ", machine)
        word = None if declared_unmechanizable(machine) else next(
            (w for w in UNCLOSED_WORDS if w in prose), None)
        if word:
            out.append((date, "'%s' 가 남아 있다 — 계획이지 장치가 아니다. "
                              "덜 닫혔으면 상태를 '부분 닫힘' 으로 적을 것" % word))
            continue
        if not points_at_something(machine):
            out.append((date, "기계 방지 칸이 아무것도 지목하지 않는다 — 검사·파일·설정을"
                              " 백틱으로 적거나, 못 만든다면 '%s' 라고 명시할 것"
                              % NOT_MECHANIZABLE[0]))
    return out


def points_at_something(cell):
    """이 칸이 **장치를 지목하는가**. 순수 함수.

    ★ 코드 식별자만 요구하면 정당한 장치가 무더기로 걸린다(2026-08-06 실측):
      `.gitignore` 차단 · `.sqrt-body{white-space:nowrap}` CSS 계약 ·
      `SUBJECT.md.template` 항목 신설 — 전부 기계인데 함수 이름이 아니다.
      그래서 **백틱으로 무엇이든 지목했는가**로 넓히고, 만들 수 없는 것은 그렇게 적게 한다.
    """
    return bool(_BACKTICK.findall(cell)) or declared_unmechanizable(cell)


def declared_unmechanizable(cell):
    """*"못 만든다"* 를 **적은** 칸인가. 순수 함수.

    조용히 비우는 것과 못 한다고 적는 것은 다르다 — 이 자가 가르려는 것이 정확히 그 차이다.
    근거를 달아 *[발화 생략]* 고 판정한 것도 여기 든다(실측 1건뿐이라 레지스트리를 세우지
    않기로 한 행이 있었다 — 그건 미완이 아니라 판정이다).
    """
    return any(w in cell for w in NOT_MECHANIZABLE)


def machine_names(cell):
    """기계 방지 칸이 지목한 이름들(백틱 식별자 + `C번호`). 순수 함수."""
    names = set(_CHECK_NO.findall(cell))
    for chunk in _BACKTICK.findall(cell):
        names.update(_IDENT.findall(chunk))
    return {n for n in names if n not in ("AGENTS", "md", "json", "py")}


# ★★ **자의 순회 범위** — 넓힌 날 2026-08-26. 「없다」를 찍던 자리가 사실은 「거기까지는
#   없다」였다(AGENTS 규칙 11). 옛 판은 `tools/` 만 훑어서 **훅 안의 이름은 영영 못 찾았다.**
#
# **넓힌 근거(표본을 세고 정했다 — 2026-08-26, 원장 정본 280항목):**
#   · 닫힌 행이 지목한 이름 **275개** 중 **8개가 `.claude/hooks/` 에 실재**한다
#     (`guard_bash.deny_reason`·`close_report`·`scan_private`·`shutdown_timer.py` …).
#     지금 통과하는 이유는 **그 글자가 `tools/` 에도 우연히 있어서**다(대개 `test_checks.py`
#     가 훅을 시험하며 이름을 적는다) — 맞는 답을 틀린 근거로 내고 있었다.
#   · 훅에만 있고 `tools/` 에는 글자로도 없는 이름은 **구조적으로 못 찾는다.**
#     실물: 2026-08-26 행이 지목한 훅 함수 하나(공용 폴더 `훅/gate_rerun_guard.py`).
#   · 훅은 이 리포의 **둘째 기계 면**이다 — AGENTS 실행 규율 5 는 거부 판정의 정본을
#     `guard_bash.deny_reason()` 으로, 규율 11 은 게이트 재실행 차단을
#     `.claude/hooks/gate_rerun_guard.py` 로 못 박는다. `check_floor` 도 「훅이 등록됐나」를
#     바닥 방어 일곱 항목 중 하나로 잰다(실측 훅 22개 등록).
#
# ★ **안 넓힌 것과 그 근거** — 넓힐수록 「이름이 우연히 어딘가에 있다」로 통과하기 쉬워진다:
#   · `docs/` — **넣으면 안 된다.** 실측: 닫힌 행이 지목한 이름 중 **16개가 docs/ 에만** 있다
#     (`checks_svg.fan_svg`·`strictChapters.section_ref`·`PDF_FOR_BY_SUBJECT` …). 전부
#     **산문에 적힌 이름**이라, docs/ 를 담으면 «문서에 적었다» 가 «장치가 있다» 로 통과한다.
#     그 16개는 지금 정직하게 빨개져야 하는 잔량이지 통과시킬 것이 아니다.
#   · `site/template/` — 템플릿의 CSS 계약도 장치이긴 하다(`points_at_something` 독스트링).
#     그러나 실측 **거기에만 사는 이름 0개**라 **넓힐 근거가 없다.** 생기면 그때 잰다.
#   · `data/` — 콘텐츠다. 기계가 아니다.
#
# ☐ **이 자가 못 보는 것 — 자기 자신이 분모 안에 있다.** 이 파일도 `tools/` 라서 여기에
#   이름을 **글자로 적으면 그 순간 「소스에 실재한다」가 된다.** 넓힌 날 실제로 그렇게 됐다:
#   위 실물 이름을 설명 주석에 적었더니 **빨갛던 행이 조용히 초록이 됐다** — 자가 자기 설명을
#   자기 증거로 쓴 것이다(AGENTS 규칙 21 ⑴). 그래서 **여기에도 회귀에도 그 이름을 글자로
#   안 적는다**(회귀는 시료를 런타임에 이어 붙인다). 근본 처방(주석·독스트링을 분모에서 빼기)은
#   오탐 범위를 먼저 재야 해서 이 배치에서 안 했다 — `docs/받은것-인박스.md` 3번에 열어 뒀다.
SOURCE_DIRS = (
    ("tools", (".py",)),
    (os.path.join(".claude", "hooks"), (".py",)),
)


def source_paths(root=None):
    """훑을 소스 파일 경로 목록. `source_blob` 과 분모가 **같은 자리에서** 나오게 가른다.

    ★ 이 리포(`SOURCE_DIRS`)에 더해 공용 폴더 자신(`SHARED_SOURCE_DIRS`)도 **선택적으로** 훑는다 —
    공용 폴더를 대상으로 닫은 원장 행이 공용 폴더 자신의 도구를 지목할 수 있어서다. `root` 를 명시로 준
    호출(테스트가 임시 폴더로 대체하는 자리)은 공용 폴더를 안 본다 — 그 자리는 이 리포의 스캔 범위
    자체를 시험하는 것이라 바깥 폴더가 섞이면 대조군이 아니게 된다.
    """
    base = root or ROOT
    out = []
    for rel, exts in SOURCE_DIRS:
        for dirpath, dirs, files in os.walk(os.path.join(base, rel)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            out.extend(os.path.join(dirpath, n) for n in sorted(files)
                       if n.endswith(exts))
    if root is None:
        shared = _shared_root()
        if shared is not None:
            for rel, exts in SHARED_SOURCE_DIRS:
                for dirpath, dirs, files in os.walk(os.path.join(str(shared), rel)):
                    dirs[:] = [d for d in dirs if d != "__pycache__"]
                    out.extend(os.path.join(dirpath, n) for n in sorted(files)
                               if n.endswith(exts))
    return out


class SourceIndex:
    """주석·독스트링을 제외한 실행 증거 인덱스.

    함수·클래스 이름은 정의만으로 장치가 되지 않는다. 다른 코드 위치에서 실제로 참조되거나
    호출돼야 `in` 판정이 참이다. C번호·설정 조각처럼 함수가 아닌 장치는 실행 문자열과 AST
    식별자에서 찾는다.
    """

    def __init__(self):
        self.function_defs = set()
        self.references = set()
        self.code_strings = []

    def __contains__(self, name):
        if name in self.function_defs:
            return name in self.references
        return name in self.references or any(name in text for text in self.code_strings)


class _SourceVisitor(ast.NodeVisitor):
    def __init__(self, index):
        self.index = index

    @staticmethod
    def _body_without_docstring(body):
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            return body[1:]
        return body

    def _visit_definition(self, node):
        self.index.function_defs.add(node.name)
        for dec in node.decorator_list:
            self.visit(dec)
        for stmt in self._body_without_docstring(node.body):
            self.visit(stmt)

    def visit_FunctionDef(self, node):
        self._visit_definition(node)

    def visit_AsyncFunctionDef(self, node):
        self._visit_definition(node)

    def visit_ClassDef(self, node):
        self._visit_definition(node)

    def visit_Name(self, node):
        self.index.references.add(node.id)

    def visit_Attribute(self, node):
        self.index.references.add(node.attr)
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self.index.code_strings.append(node.value)


def source_blob(root=None):
    """`SOURCE_DIRS` 아래 Python의 **실행 증거**. 주석·독스트링은 제외한다.

    ★ **분모는 `source_note()` 가 낸다** — 이 자가 무엇을 훑었는지 안 보이면
      「없다」와 「못 봤다」가 화면에서 같아진다. 부르는 자리는 그 줄을 함께 찍는다.
    """
    index = SourceIndex()
    for path in source_paths(root):
        try:
            # 파일 자체가 장치인 경우(`narration_due.py` 같은 훅)도 있다.
            index.references.add(os.path.basename(path))
            index.references.add(os.path.splitext(os.path.basename(path))[0])
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            visitor = _SourceVisitor(index)
            for stmt in _SourceVisitor._body_without_docstring(tree.body):
                visitor.visit(stmt)
        except (OSError, SyntaxError):
            continue
    return index


def source_note(root=None):
    """자가 내는 **자기 분모** — 「소스 N개 파일 · M바이트를 훑었다」.

    ★★ 오늘 승격된 부류다 — **«자가 자기 입력을 못 잡았는데 그 사실이 결과에 안 나온다».**
      이 함수가 고친 결함이 정확히 그 형태였다(범위 밖 이름을 「없다」로 찍었다).
      그래서 **폴더별로** 낸다: 한 폴더가 0개면 그 폴더가 통째로 빠진 것이고,
      그건 판정이 아니라 미완이다(합계만 내면 그 사실이 다시 묻힌다).
    """
    base = root or ROOT
    all_paths = source_paths(base)
    parts, files, size = [], 0, 0
    for rel, exts in SOURCE_DIRS:
        paths = [p for p in all_paths
                 if p.startswith(os.path.join(base, rel) + os.sep)]
        n = len(paths)
        b = sum(os.path.getsize(p) for p in paths if os.path.isfile(p))
        files, size = files + n, size + b
        mark = " **0개 — 이 폴더를 못 봤다**" if not n else ""
        parts.append("%s %d개%s" % (rel.replace("\\", "/") + "/", n, mark))
    if root is None:
        shared = _shared_root()
        if shared is not None:
            for rel, exts in SHARED_SOURCE_DIRS:
                paths = [p for p in all_paths
                         if p.startswith(os.path.join(str(shared), rel) + os.sep)]
                n = len(paths)
                b = sum(os.path.getsize(p) for p in paths if os.path.isfile(p))
                files, size = files + n, size + b
                mark = " **0개 — 이 폴더를 못 봤다**" if not n else ""
                parts.append("공용 폴더/%s %d개%s" % (rel, n, mark))
    return ("훑은 소스 — %s · 합계 %d개 파일 · %s바이트"
            % (" · ".join(parts), files, format(size, ",")))


def pending_ledger_rows(text, since=LEDGER_STRICT_FROM):
    """`since` **이전**에 닫혔는데 기계를 지목하지 않은 행 — 승격 잔량. 순수 함수."""
    return [(d, why) for d, why in closed_rows_without_machine(text, since=None)
            if d < since]


# 역사 원장은 당시 장치명을 보존한다. 장치를 정식으로 은퇴·대체한 경우에만 옛 이름을
# 현재 후계 장치로 해석한다. 문자열을 나눠 쓰는 것은 이 감사기 자신의 alias 선언이
# `source_blob()`의 실행 증거로 오인되지 않게 하기 위해서다.
RETIRED_MACHINE_SUCCESSORS = {
    "shut" + "down_timer.py": "wake" + "up_guard.py",
    "test_shut" + "down_timer_is_pushed_by_a_hook":
        "test_wake" + "up_guard_blocks_a_turn_without_a_wakeup",
}


def machine_is_live(name, blob):
    """현재 장치 또는 명시적으로 등록된 후계 장치가 실행 증거에 있는가."""
    if name in blob:
        return True
    successor = RETIRED_MACHINE_SUCCESSORS.get(name)
    return bool(successor and successor in blob)


def closed_rows_naming_nothing_real(text, blob, since=LEDGER_STRICT_FROM):
    """`닫힘` 인데 지목한 이름이 **소스에 하나도 없는** 행. 순수 함수.

    이름을 적어 두고 실제로는 안 만든 경우를 잡는다 — 칸을 채운 것과 장치가 있는 것은 다르다.
    """
    out = []
    for date, machine, status, topic in ledger_rows(text):
        if not is_fully_closed(status) or (since and date < since):
            continue
        names = machine_names(machine)
        if names and not any(machine_is_live(n, blob) for n in sorted(names)):
            out.append((date, "지목한 이름이 소스에 없다 — " + ", ".join(sorted(names)[:4])))
    return out


# 백틱을 안 씌웠을 뿐 이름은 적혀 있는 경우를 찾는 자. 잔량을 갚을 때 **무엇이 진짜
# 미구현이고 무엇이 표기 문제인지**를 갈라 준다 — 그 둘은 갚는 비용이 자릿수로 다르다.
_LOOSE_NAME = re.compile(r"\b(?:test_[a-z0-9_]+|[a-z][a-z0-9]*(?:_[a-z0-9]+)+"
                         r"(?:_issues|_hits|_py)?|C\d{1,2})\b")


def loose_names(cell, blob):
    """백틱 **밖**에 적혀 있고 소스에 실재하는 이름. 순수 함수."""
    prose = _BACKTICK.sub(" ", cell)
    return sorted({n for n in _LOOSE_NAME.findall(prose) if len(n) > 3 and n in blob})


def backlog_report(text, blob, since=LEDGER_STRICT_FROM):
    """잔량 행을 (날짜, 왜, 백틱 밖 이름 후보)로. 순수 함수 — CLI 와 테스트가 함께 쓴다.

    ★ 날짜로 묶지 않는다 — 같은 날 여러 건을 닫은 날이 많아서(2026-08-01 에 4행), 사전으로
      묶으면 뒤 행이 앞 행을 덮어 **잔량이 조용히 줄어든 것처럼** 보인다.
    """
    out = []
    for date, machine, status, topic in ledger_rows(text):
        if not is_fully_closed(status) or (since and date >= since):
            continue
        prose = _BACKTICK.sub(" ", machine)
        word = None if declared_unmechanizable(machine) else next(
            (w for w in UNCLOSED_WORDS if w in prose), None)
        if word:
            why = "미완 표시 '%s'" % word
        elif not points_at_something(machine):
            why = "아무것도 지목 안 함"
        else:
            continue
        out.append((date, why, loose_names(machine, blob), machine, topic))
    return out


def pending_candidates(root=None):
    """인박스·워크오더에 **'후보'로만 적힌** 항목 수 (파일별). 원장으로 승격될 대기열이다.

    `close_report.py` 가 이 수를 보고한다 — 26 에서 줄어드는 것이 눈에 보여야
    "언젠가 하겠다"가 아니라 잔량이 된다.
    """
    base = os.path.join(root or ROOT, "data")
    pat = re.compile(r"방지 후보|후보로만|기계 방지 후보")
    found = {}
    for dirpath, _dirs, files in os.walk(base):
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    hits = len(pat.findall(fh.read()))
            except OSError:
                continue
            if hits:
                found[os.path.relpath(path, root or ROOT)] = hits
    return found


def strict_report(text, blob, since=LEDGER_STRICT_FROM):
    """승격일 **이후** 위반 행을 (날짜, 왜, 백틱 밖 이름 후보, 칸, 지적)로. 순수 함수.

    `backlog_report` 와 판정은 같고 **기간만 반대쪽**이다 — 이쪽은 잔량이 아니라 위반이라
    `test_ledger_closed_rows_name_a_real_machine` 이 빨개진다. 갚을 때 «무엇이 걸렸나» 를
    보려면 그 회귀의 `repr` 말고 이 자를 쓴다(회귀는 이유만 주고 칸 내용을 안 준다).
    """
    out = []
    for date, machine, status, topic in ledger_rows(text):
        if not is_fully_closed(status) or (since and date < since):
            continue
        prose = _BACKTICK.sub(" ", machine)
        word = None if declared_unmechanizable(machine) else next(
            (w for w in UNCLOSED_WORDS if w in prose), None)
        if word:
            why = "미완 표시 '%s'" % word
        elif not points_at_something(machine):
            why = "아무것도 지목 안 함"
        else:
            continue
        out.append((date, why, loose_names(machine, blob), machine, topic))
    return out


def main():
    """잔량을 갚을 때 쓰는 진단 — `python tools/buildlib/ledger.py [--strict]`.

    행마다 **백틱 밖에 적혀 있고 소스에 실재하는 이름**을 함께 찍는다. 그 이름이 있으면
    그 행은 *검사가 없는 것이 아니라 지목을 안 한 것*이라 백틱만 씌우면 닫힌다 —
    진짜 미구현과 갚는 비용이 자릿수로 다르므로 갈라 보는 것이 먼저다.

    ★ `--strict` 는 **승격일 이후**(= 회귀가 실제로 막는 구간)를 찍는다. 기본 출력이
      승격 **이전** 잔량뿐이라, 회귀가 빨개졌을 때 «무엇이 걸렸나» 를 이 자에게 물을 수
      없었다(2026-08-26 — 정본을 보게 고친 날 3건이 드러났는데 CLI 가 0건을 찍었다).
    """
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    strict = "--strict" in sys.argv
    with open(LEDGER, encoding="utf-8") as fh:
        text = fh.read()
    print(ledger_source_note(text))       # ★ 분모를 먼저 낸다 — 판정은 그다음이다
    if strict:
        rows = strict_report(text, source_blob())
        print("승격일(%s) **이후** 위반 %d건 — 회귀가 막는 구간이다"
              % (LEDGER_STRICT_FROM, len(rows)))
        for date, why, names, cell, topic in rows:
            print("  %s  %-20s %s" % (date, why, ", ".join(names) or "—"))
            print("      지적: " + " ".join(topic.split())[:120])
            print("      칸  : " + " ".join(cell.split())[:200])
        return
    rows = backlog_report(text, source_blob())
    named = [r for r in rows if r[2]]
    print("원장 잔량 %d건 — 그중 **이름은 적혀 있고 백틱만 없는** 행 %d건"
          % (len(rows), len(named)))
    for date, why, names, cell, topic in rows:
        print("  %s  %-20s %s" % (date, why, ", ".join(names) or "—"))
        print("      지적: " + " ".join(topic.split())[:90])
        print("      칸  : " + " ".join(cell.split())[:90])
    inbox = pending_candidates()
    print("\n인박스·워크오더 '후보' %d건" % sum(inbox.values()))
    for path, hits in sorted(inbox.items()):
        print("  %s: %d건" % (path, hits))


if __name__ == "__main__":
    main()
