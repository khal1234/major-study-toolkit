# -*- coding: utf-8 -*-
"""상호작용 점검 — **말한 것과 한 것이 맞는가** (읽기 전용 · 신설 2026-08-15).

    python tools/audit_session_conduct.py             # 이 프로젝트, 최근 세션 1개
    python tools/audit_session_conduct.py --sessions=3
    python tools/audit_session_conduct.py --quiet     # 걸린 게 없으면 한 줄도 안 낸다(커밋용)

**왜 이 자인가** (2026-08-15 사용자 지적):

    *[발화 생략]*

  재 보니 안 들어갔다. `close_report` 가 재는 여덟 가지는 **전부 리포 산출물**이다 —
  빌드·경고·회귀·등록·침식·개인정보·승격·미커밋. 그런데 이 리포 규칙의 절반은
  **상호작용**에 관한 것이다(판정을 파일에 남길 것 · 예고한 것을 조용히 안 하지 말 것 ·
  미검증을 검증된 것처럼 쓰지 말 것 · 지적은 원장에 먼저). AGENTS 도 그 자리를
  *[발화 생략]* 고 적어 두었다.
  **세션 기록(JSONL)이 있으니 이제는 읽을 수 있다** — `audit_session_cost` 가 이미 그 파일을 읽는다.

★ **판정이 아니라 셈이다.** 사람이 볼 목록을 내고 **고치지도 막지도 않는다**(언제나 exit 0) —
  `check_floor`·`audit_session_cost` 와 같은 규율이다. 진단이 처방을 겸하면 «재 보니 다 됐다»
  는 결론이 나올 수 없다.
★ **언제 도나 (사용자 질문: «마지막 Close만? 중간엔?»).** 셋 다 아니고 **커밋**이다 —
  이 리포에서 반드시 하는 일이고, 무엇보다 *«이걸 했다»고 주장하는 자리*라 예고·미검증과
  짝이 맞다(「트리거는 내가 반드시 하는 일에 건다」). 그래서 `commit.py` 가 `--quiet` 로
  부르고, 전체 목록은 `close_report` 가 낸다. **평소에는 한 줄도 안 낸다.**

**무엇을 재나 — 셋.**

  ⑴ **예고하고 안 한 것.** *[발화 생략]* 처럼 적어 놓고 그 뒤 아무 도구 호출에도
     그 대상이 안 나온 것. 대상은 예고 문장에서 **파일명·도구명**으로 잡는다 — 그런 낱말이
     없는 예고는 기계가 이행을 못 재므로 **[사람]** 으로만 낸다(억지로 판정하지 않는다).
  ⑵ **`미검증` 이라 적고 그대로 둔 것.** 규칙 11 은 «명령을 댈 수 없으면 미검증이라 밝혀라»
     인데, 밝힌 뒤 그대로 세션이 끝나면 그 항목은 **열린 채로 잊힌다.**
  ⑶ **지적을 받고 원장·기억이 안 움직인 세션.** 사용자 발화가 여럿인데
     `docs/feedback-ledger.md`·기억 폴더를 한 번도 안 건드렸으면 신고한다.
  ⑷ **완료 선언 → 사용자가 재차 캐물음 → 원인·방지 없는 시인** (2026-09-05 신설).
     사용자가 원하는 것은 재확인 자체가 필요 없는 것이지, 재확인 뒤 답을 잘 하는 게
     아니다 — 그건 이 자로 못 잡는다(«완료 선언이 맞았나»는 판단형, 프로젝트마다
     다른 실물 검사가 있어야 한다). 이 자가 잡는 것은 그보다 좁다: **일단 재확인을
     당했는데도** 다음 답에 원인·방지가 둘 다 없는 것.

**안 재는 것(밝혀 둔다).** «사용자 판정을 커밋 메시지에 인용했는가» 는 재지 않는다 —
인용 여부를 문자열로 판정하려 하면 *따옴표를 넣기만 하면 통과하는* 도장이 된다.
그건 사람이 볼 자리다.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import audit_session_cost as cost                                        # noqa: E402
from check_narration import is_user_text                                 # noqa: E402

# 예고로 읽는 말 — «앞으로 하겠다»는 뜻이 분명한 것만. 넓히면 평서문이 전부 걸린다.
# ★ 동사를 열거하지 않는다 — 처음엔 `하겠|판정하겠|보겠` 를 나열했는데 **`고치겠습니다` 가
#   빠졌고**, 그 바람에 회귀 케이스가 «예고를 못 찾아» 빈 결과로 **공허하게 통과**했다
#   (규칙 11: 새 자의 첫 출력은 «자를 재는 것»). 한국어의 약속 표지는 어미 `-겠-` 하나다.
PROMISE_RE = re.compile(r"[가-힣]{1,8}겠(습니다|어요|음)")
# 예고의 «대상» — 파일명·도구명. 이것이 있어야 이행을 기계로 잴 수 있다.
TARGET_RE = re.compile(r"[\w가-힣./-]+\.(?:py|md|json|txt|html|vbs|ps1)")
# ★ 「미검증」은 **낱말이 아니라 자리**로 잡는다 (첫 실행에서 8건 중 다수가 오탐이었다).
#   그 낱말을 *설명하는* 문장(«미검증으로 남겼는지», «미검증이라 적고»)과 실제 **판정 표시**를
#   가르지 않으면, 이 자는 자기 규칙을 설명한 문서까지 신고한다 — 소음이 된 신고는 안 읽힌다.
# ★ 2026-09-11 (XSanity 신고) — 따옴표 안의 「미검증」은 판정이 아니라 **그 낱말의 언급**이다.
#   결함을 설명하는 줄까지 잡혀 1건이 3건으로 늘었다 — 여는/닫는 따옴표·백틱이 붙으면 뺀다.
UNVERIFIED_RE = re.compile(r"(?<![「『\"'`])미검증(?![」』\"'`]|을|를|이라|으로|이라고|\s*여부)")
# 판정이 적히는 자리 — 표 셀이거나 항목 줄. 산문 한복판의 언급은 세지 않는다.
# ★ `*` 는 자리 표시가 아니라 **굵게**다 — 넣었더니 굵은 문장이 전부 판정으로 잡혔다(2차 오탐).
VERDICT_SLOT_RE = re.compile(r"^\s*([|·]|-\s)|\s\|\s")
# 프롬프트 요령 블록(번호로 시작하는 조언)은 예고가 아니다.
ADVICE_RE = re.compile(r"^\s*\d+\.\s")
LEDGER_HINTS = ("feedback-ledger", "memory", "MEMORY.md", "인박스", "review-inbox")
# ── 규칙 문서가 자랐는데 원장이 안 움직였다 (2026-08-16 신설) ──────────────────
#
# 실측이 이 항목을 열었다: **`AGENTS.md` 안의 사용자 인용 114건 중 원장에도 있는 것은
# 18건(하한 16%)뿐**이었다. 원장은 *[발화 생략]* 이라고
# 규정하는데, 실제로는 **지적이 대기열을 건너뛰고 규칙 문서로 직행**했다.
# 그래서 어느 쪽도 완전하지 않다 — 원장만 보면 96건을 못 보고, 규칙 문서만 보면
# 원장의 나머지를 못 본다.
#
# ★ **「지적을 받았나」는 안 센다 — 그건 판단형이다.** 대신 **결과**를 센다:
#   *규칙 문서가 자랐는데 원장이 안 움직였다.* 둘 다 도구 호출로 관측된다.
# ★ **판정이 아니라 물음이다.** 규칙은 지적 말고 설계 판단에서도 나온다 — 그때는 원장에
#   적을 것이 없는 게 맞다. 이 자는 «이게 지적에서 왔나» 를 **사람에게 되묻는다.**
#
# ★★ **첫 실행이 이 자의 결함을 둘 잡았다 (2026-08-16)** — 「새 자의 첫 출력은 재는 것이
#   아니라 자를 재는 것」의 실례라 둘 다 적어 둔다.
#   ⑴ `file_path` 가 든 호출을 전부 셌는데 **`Read` 도 `file_path` 를 쓴다** — 읽기만 한
#      문서가 «고쳤다» 로 잡혔다. → 편집 표식(`old_string`·`new_string`·`content`)을 함께 요구한다.
#   ⑵ 그러고도 **글 안에 그 이름을 적기만 해도** 잡혔다(이 문서들을 인용하는 규칙을 쓰는
#      중이었다). → **경로만 본다**(`file_path` 값). 통째로 훑으면 «말한 것»과 «고친 것»이 섞인다.
RULE_HINTS = ("AGENTS.md", "CLAUDE.md", "규칙/")
EDIT_MARKS = ("old_string", "new_string", '"content"')
# ── 빈손으로 묻기 (2026-08-15 신설 · `규칙/물어야-할-때.md`) ────────────────────
#
# 사용자 지적: *[발화 생략]*
#
# ★ **판정선을 형식으로 내렸다.** 「좋은 물음인가」는 판단형이라 매번 통과되지만
#   (`방지장치-설계.md` 16항) *«이 응답에 `제안:` 이 있나»* 는 기계가 센다.
#   그래서 규약이 표지를 글자로 못 박고, 이 자는 그 글자만 본다.
# ★ **물음으로 «끝나는» 응답만 센다.** 산문 한복판의 물음(«왜 이 규칙이 필요한가?»)까지
#   세면 자기 문서를 설명한 보고가 전부 걸린다 — 위 `UNVERIFIED_RE` 가 겪은 오탐과 같은 부류.
#   사용자가 말한 실패는 **[발화 생략]** 라, 끝자리가 곧 그 자리다.
ASK_END_RE = re.compile(r"[?？]\s*$")
PROPOSAL_RE = re.compile(r"\*\*제안[:：]")
# ── 자기부정 어구를 쓰고도 안 묻는다 (2026-08-31 신설 · Skill ②의 훅 확장) ────────
#
# 원장 2026-08-27: *[발화 생략]* 라고 자기 출력에
# 써 놓고도 그대로 진행해 잘못된 배정을 했다. **자기 문장 안의 확신 부족 신호가 곧
# 물어야 한다는 신호**인데, 그 신호를 스스로 못 읽었다. 위 `barehanded_asks` 와 자리는
# 같지만(응답 하나를 보는 결정적 판정) 조건이 다르다 — 저건 "물음표로 안 끝났나",
# 이건 "확신 부족 어구가 있는데 물음이 없나".
# ★ 좁게 잡는다 — 어구를 넓히면 "확신 못 하지만 이렇게 진행합니다" 류의 정당한 자기
#   서술(근거를 대며 낮은 확신을 밝히는 것 자체는 「단정을-낮춘다」가 권장하는 미덕이다)
#   까지 걸린다. 그래서 **근거 부재를 직접 자백하는 좁은 표현**만 잡는다.
HEDGE_RE = re.compile(r"근거가\s*없|확신(이|을)?\s*못|확실하지\s*않|확실치\s*않|"
                       r"판단이\s*안\s*서|다른\s*자리가\s*없어서|잘\s*모르겠")
# ── 완료 선언 → 재차 캐물음 → 원인·방지 없는 시인 (2026-09-05 신설) ────────────
#
# 실사고(다른 프로젝트 세션, 사용자가 그대로 옮겨 보여줌): [발화 생략] 를 사용자가 반복해서 물어야만 세션이 그제서야 "아 아니네요" 를 인정했고,
# 인정한 뒤에도 **왜 놓쳤고 다음에 뭘 바꿀지**는 안 냈다 — `규칙/위반은-원인부터-
# 밝히고-고친다.md`(오늘 신설)가 정확히 겨눈 그 자리다. 그 규칙 자체는 "판단형이라
# 세는 자 없음"으로 만들었는데, **"판단형이라 못 잰다"가 "아무것도 못 잰다"와 같지
# 않다** — "잘 설명했는가"는 판단형이지만 "①완료를 선언했다②사용자가 의심해서
# 재차 물었다③그런데도 원인·방지 표지가 다음 응답에 없다"는 문자열로 센다.
# ★ **③까지 걸려야 신고한다.** ①②만으로는 "사용자가 다시 확인한 것" 자체를 나무라는
#   꼴이 된다(그건 사용자의 정당한 권리다) — 신고 대상은 어디까지나 **그 다음 응답이
#   원인·방지 없이 시인만 하는 것**이다.
COMPLETION_RE = re.compile(r"끝났습니다|완료(됐|되었|입니다)|다\s*됐|더\s*할\s*일\s*없|"
                            r"남은\s*(것|일)[은는:]?\s*없|작업\s*끝")
# ★ 2026-09-11 — 「맞아」는 물음표가 있어야 캐물음이다. 「판독맞아」(확인해 준 말)가 이틀 내내 누적으로 떴다.
REASK_RE = re.compile(r"진짜|정말|확실|더\s*없|맞아\?|다\s*한\s*거|다한거|"
                       r"더\s*남은")
CAUSE_RE = re.compile(r"왜|원인|이유")
PREVENT_RE = re.compile(r"방지|안\s*그러|다음부터|재발|막을|고칩니다|고치겠")


def texts_and_tools(records):
    """`(assistant 글 조각, 도구 입력 문자열, user 발화 수)` — 순수 함수(레코드 목록만 본다)."""
    said, used, users = [], [], 0
    for rec in records:
        msg = rec.get("message") or {}
        role = msg.get("role") or rec.get("type")
        content = msg.get("content")
        if role == "user" and isinstance(content, str):
            users += 1
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and role == "assistant":
                said.append(str(block.get("text") or ""))
            elif block.get("type") == "tool_use":
                used.append(json.dumps(block.get("input") or {}, ensure_ascii=False))
            elif block.get("type") == "tool_result" and role == "user":
                pass                       # 도구 결과는 사용자 발화가 아니다
    return said, used, users


def promises(said, used):
    """`(미이행 후보, 사람이 볼 것)`. 순수 함수 — 테스트가 직접 부른다.

    ★ 이행 판정은 **대상 낱말이 그 뒤 도구 입력에 나왔는가** 하나다. 약한 자지만
      *한 방향으로만* 약하다 — 대상이 안 나온 것을 «했다» 고 하지는 않는다.
    """
    later = "\n".join(used)
    # ★ 대상은 **basename 으로 맞춘다** (첫 실행 오탐): 예고는 `main/tools/build_site.py` 처럼
    #   경로·백틱을 달고 적히는데 도구 입력에는 절대경로나 다른 접두어로 나온다. 접두어를 그대로
    #   비교하면 **실제로 한 일을 «안 했다» 고 신고한다** — 이 자에서 가장 비싼 실패다.
    open_, human = [], []
    for chunk in said:
        for line in chunk.splitlines():
            if ADVICE_RE.match(line) or not PROMISE_RE.search(line):
                continue
            targets = [os.path.basename(t) for t in TARGET_RE.findall(line)]
            if not targets:
                human.append(line.strip()[:90])
            elif not any(t in later for t in targets):
                open_.append(line.strip()[:90])
    return open_, human


# ★ 2026-09-11 (XSanity 신고) — 누적 「미검증」이 **해소를 몰랐다.** 뒤에서 확인을 끝내고 보고해도
#   그 줄이 매 턴 「반드시 옮길 것」으로 떠 이미 참이 아닌 말을 되풀이하게 했다(경보 피로).
#   해소 = ⑴ 뒤 조각에 `(검증됨: …)` 표식 ⑵ 뒤 조각이 그 줄의 대상 낱말(2자 이상 · 흔한 낱말 제외)
#   하나 이상과 해소 낱말을 **같은 줄에** 담았다. 넘어지는 쪽: 대상 낱말이 우연히 겹치면 해소로 친다
#   — 그래도 「이미 끝난 것을 매 턴 되풀이」보다 싸다고 봤다.
RESOLVED_MARK_RE = re.compile(r"\(검증됨\s*:")
RESOLVE_WORD_RE = re.compile(r"확인했|확인 완료|검증됨|검증했|떴습니다|떠 있|통과했|재 보니|실측")
_COMMON = {"미검증", "확인", "검증", "것은", "것을", "있습니다", "없습니다", "합니다", "했습니다", "지금", "이번"}


def _targets(line):
    return {w for w in re.findall(r"[가-힣A-Za-z0-9_.\-]{2,}", line) if w not in _COMMON}


def unverified(said):
    """`미검증` 이라 적힌 줄 중 **뒤에서 해소되지 않은 것.** 순수 함수."""
    out = []
    for i, chunk in enumerate(said):
        for line in chunk.splitlines():
            if not (UNVERIFIED_RE.search(line) and VERDICT_SLOT_RE.search(line)):
                continue
            tg = _targets(UNVERIFIED_RE.sub("", line))
            later = [l for c in said[i + 1:] for l in c.splitlines()]
            if any(RESOLVED_MARK_RE.search(l) for l in later) or any(
                    RESOLVE_WORD_RE.search(l) and not UNVERIFIED_RE.search(l) and tg & _targets(l)
                    for l in later):
                continue
            out.append(line.strip()[:90])
    return out


# ── 「남은 일」 표지 (XSanity 2026-08-30 신설 → 2026-09-07 공용으로 올림) ──────
# 규칙 「남은-일은-물으며-끝낸다」는 있었는데 **「잘 지켰나」가 판단형이라 매번 통과**됐다.
# `**제안:**` 과 같은 부류로 형식을 내린다 — 「`남은 일` 이라는 글자가 있나」는 기계가 센다.
LEFTOVER_RE = re.compile(r"남은\s*일")


def leftover_missing(said, used):
    """도구를 실제로 쓴 턴인데, 마지막 글 조각에 「남은 일」 표지가 없다. 순수 함수.

    ★ **도구를 안 쓴 턴은 안 잰다** — 순수 대화(질문에 바로 답하는 등)까지
      「남은 일」을 요구하면 매 답변이 걸려 소음이 된다. 이 표지는 **일을 한 뒤**
      마무리하는 자리에서만 뜻이 있다.
    ★ **마지막 글 조각만 본다** — 중간 글은 아직 마무리하는 자리가 아니다.
    """
    if not used or not said:
        return None
    last = said[-1].strip()
    if not last or LEFTOVER_RE.search(last):
        return None
    lines = [ln for ln in last.splitlines() if ln.strip()]
    return lines[-1].strip()[:90] if lines else None


def barehanded_asks(said):
    """**물음으로 끝나는데 `제안:` 이 없는 응답.** 순수 함수.

    이 자는 «물었다» 를 나무라지 않는다 — 되돌릴 수 없는 자리에서는 물어야 한다
    (`규칙/커밋-푸시-규약.md` §3). 세는 것은 **빈손으로 물었나** 하나다.
    """
    out = []
    for chunk in said:
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        if not lines or not ASK_END_RE.search(lines[-1].strip()):
            continue
        if PROPOSAL_RE.search(chunk):
            continue
        out.append(lines[-1].strip()[:90])
    return out


def self_hedge_unasked(said):
    """**확신 부족 어구를 쓰고도 그 응답이 물음으로 안 끝난다.** 순수 함수.

    `barehanded_asks` 와 짝 — 저건 "빈손으로 물었나", 이건 "물었어야 하는데 안 물었나"다.
    """
    out = []
    for chunk in said:
        m = HEDGE_RE.search(chunk)
        if not m:
            continue
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        if lines and ASK_END_RE.search(lines[-1].strip()):
            continue                                   # 이미 물었다 — 안 걸림
        for line in chunk.splitlines():
            if HEDGE_RE.search(line):
                out.append(line.strip()[:90])
                break
    return out


def turns(records):
    """`(사용자 발화, 그 다음 assistant 가 낸 글 이어붙임)` 목록 — 순서대로. 순수 함수.

    `texts_and_tools` 와 다르다 — 그 자는 창 전체를 뭉쳐 세서 **턴 경계를 지운다.**
    이 자는 «몇 턴 전에 뭐라 했고 몇 턴 뒤에 뭐라 했나» 를 봐야 하는 판정
    (`completion_reask_cycle`) 을 위해 경계를 **보존한다.**
    """
    out = []
    cur_user, buf = None, []
    for rec in records:
        if is_user_text(rec):
            if cur_user is not None:
                out.append((cur_user, "\n".join(buf)))
            c = (rec.get("message") or {}).get("content")
            cur_user = c if isinstance(c, str) else "\n".join(
                b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
            buf = []
            continue
        if rec.get("type") != "assistant":
            continue
        for b in ((rec.get("message") or {}).get("content") or []):
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip():
                buf.append(b["text"])
    if cur_user is not None:
        out.append((cur_user, "\n".join(buf)))
    return out


def completion_reask_cycle(turn_list):
    """**완료를 선언했는데 사용자가 재차 캐물었고, 그런데도 다음 답이 원인·방지 없이
    시인만 한다.** 순수 함수 — `turns()` 의 출력을 받는다.

    ①②만으로는 안 잡는다 — 사용자가 재확인하는 것 자체는 나무랄 일이 아니다.
    **③(다음 응답에 원인·방지 표지가 둘 다 없다)까지 있어야** 신고한다.
    """
    out = []
    for i in range(len(turn_list) - 1):
        _, reply_i = turn_list[i]
        user_next, reply_next = turn_list[i + 1]
        if not COMPLETION_RE.search(reply_i):
            continue
        if not REASK_RE.search(user_next):
            continue
        if CAUSE_RE.search(reply_next) and PREVENT_RE.search(reply_next):
            continue                       # 원인·방지 둘 다 있다 — 안 걸림
        out.append(user_next.strip().splitlines()[0][:90] if user_next.strip() else "")
    return out


# ── (이 리포 전용) 완료 선언 전에 산출물을 재생성했나 (2026-09-06 신설) ──────
#
# `/insights` 리포트 실측(2026-09-06): 이 프로젝트의 가장 큰 마찰이 "완료를
# 선언했는데 사용자가 보는 site/ HTML은 실제로 안 바뀌어 있었다[발화 생략]이 세션이 실제로 무엇을 불렀나"를 본다** — 세션
#   밖에서(다른 터미널 등) 미리 빌드해 둔 경우까지는 이 자가 못 본다. 그런
#   자리까지 잡으려면 파일 mtime을 실제로 재야 하는데, 그건 이 리포의 다중
#   워크트리 구조상 어느 site/ 산출물이 어느 data/ 조각과 짝인지 일반화해
#   말하기 어려워 **세션 행동 관찰**로 좁혔다(세는 자이지 판정자가 아니다).
DATA_EDIT_RE = re.compile(r'(?<![A-Za-z])data[/\\]')
BUILD_CMD_RE = re.compile(r"build_site\.py|close_report\.py")


def unbuilt_completion(records):
    """`data/**` 편집 뒤 재빌드 없이 완료를 선언한 자리. 순수 함수 — 테스트 대상."""
    out = []
    dirty = False
    for rec in records:
        if rec.get("type") != "assistant":
            continue
        for b in ((rec.get("message") or {}).get("content") or []):
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                inp = json.dumps(b.get("input") or {}, ensure_ascii=False)
                if BUILD_CMD_RE.search(inp):
                    dirty = False
                elif DATA_EDIT_RE.search(inp):
                    dirty = True
            elif b.get("type") == "text" and b.get("text", "").strip():
                if dirty and COMPLETION_RE.search(b["text"]):
                    out.append(b["text"].strip().splitlines()[0][:90])
                    dirty = False           # 한 번 신고했으면 래치 — 같은 더러움 재신고 안 함
    return out


def ledger_touched(used):
    """원장·기억을 한 번이라도 건드렸나. 순수 함수."""
    blob = "\n".join(used)
    return any(h in blob for h in LEDGER_HINTS)


def rules_touched(used):
    """**규칙 문서를 고친 자리들.** 순수 함수.

    ★ 두 가지를 함께 요구한다(위 주석의 첫 실행 오탐 둘) — **편집 표식**이 있어야 하고
      (`Read` 도 `file_path` 를 쓴다), 이름은 **경로에서만** 찾는다(글 안의 언급은 «고친
      것»이 아니다). 경로 구분자는 눕혀서 본다 — 윈도의 역슬래시와 posix 의 `/` 를 안 가른다.
    """
    out = []
    for blob in used:
        if not any(k in blob for k in EDIT_MARKS):
            continue
        try:
            path = str((json.loads(blob) or {}).get("file_path") or "")
        except ValueError:
            continue
        path = path.replace("\\", "/")
        for hint in RULE_HINTS:
            if hint in path and hint not in out:
                out.append(hint)
    return out


def audit(records):
    """세션 하나의 판정 묶음. 순수 함수 — 파일 I/O 없이 테스트가 직접 부른다."""
    records = list(records)
    said, used, users = texts_and_tools(records)
    open_, human = promises(said, used)
    return {
        "users": users,
        "open_promises": open_,
        "promise_human": human,
        "unverified": unverified(said),
        "barehanded": barehanded_asks(said),
        "self_hedge": self_hedge_unasked(said),
        "completion_cycles": completion_reask_cycle(turns(records)),
        "unbuilt_completion": unbuilt_completion(records),
        "ledger_touched": ledger_touched(used),
        "rules_touched": rules_touched(used),
        "leftover_missing": leftover_missing(said, used),
    }


def load(paths):
    recs = []
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            recs.append(json.loads(line))
                        except ValueError:
                            continue
        except OSError:
            continue
    return recs


def _asst(text):
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "text", "text": text}]}}


def _tool(inp):
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "name": "Bash", "input": inp}]}}


def selftest():
    """★ 붙임 2026-08-25 — 이 자는 **커밋마다 도는데 대조군이 없었다.**

    ☐ 그리고 이 자는 **언제나 exit 0** 이다(세는 자다). 그 사실이 곧
      「문 아님」으로 `audit_gates` 에 뜬다 — 대조군이 붙어도 그건 안 바뀐다.
      **막을지 말지는 사람이 정한다**(실행 규율 17: 상한을 못 정하면 판정에 못 쓴다).
    """
    bad = 0

    def chk(desc, cond, got=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %-46s %s" % ("OK  " if cond else "**틀림**", desc, got))

    said, used, users = texts_and_tools([
        _asst("가"), _tool({"command": "python 도구/check_floor.py ."}),
        {"type": "user", "message": {"role": "user", "content": "사람 말"}},
    ])
    chk("assistant 글·도구 입력·발화를 가른다",
        said == ["가"] and len(used) == 1 and users == 1,
        "said=%d used=%d users=%d" % (len(said), len(used), users))

    said2, used2, _ = texts_and_tools([
        _asst("`도구/check_floor.py` 를 돌리겠습니다"),
        _tool({"command": "python C:/x/도구/check_floor.py ."})])
    open_, human = promises(said2, used2)
    chk("★ 예고한 대상이 뒤 도구에 나오면 이행으로 본다 (basename 으로 맞춘다)",
        not open_, str(open_))

    said3, used3, _ = texts_and_tools([_asst("`도구/없는것.py` 를 돌리겠습니다")])
    open3, _ = promises(said3, used3)
    chk("양성 — 예고만 하고 안 한 것은 잡는다", len(open3) == 1, str(open3))

    chk("양성 — 빈손으로 묻는 것은 잡는다",
        len(barehanded_asks(["이렇게 할까요?"])) == 1)
    # ★ 이 줄이 **대조군의 값어치**를 보여 준다 (2026-08-25). 처음엔 평문 `제안:` 으로
    #   썼다가 틀렸는데, **틀린 것은 자가 아니라 내 시료였다** — `PROPOSAL_RE` 는
    #   `**제안:**` 처럼 **굵은** 형식을 요구한다(규칙 18 이 정한 형식이다).
    #   대조군이 없었으면 «자가 이상하다» 로 넘어갔을 자리다.
    chk("양성 — 도구를 썼는데 「남은 일」 표지가 없으면 잡는다",
        leftover_missing(["커밋했습니다."], [{}]) is not None)
    chk("음성 — 도구를 안 썼으면 안 잡는다(순수 대화)",
        leftover_missing(["커밋했습니다."], []) is None)
    chk("음성 — 「남은 일」 표지가 있으면 안 잡는다",
        leftover_missing(["**남은 일:** 없음."], [{}]) is None)

    chk("음성 — `**제안:**` 이 있으면 빈손이 아니다",
        not barehanded_asks(["**제안:** A 로 갑니다\n이렇게 할까요?"]))

    def u(text):
        return {"type": "user", "message": {"role": "user", "content": text}}

    cyc_hit = turns([
        u("작업해줘"), _asst("작업 끝났습니다."),
        u("진짜? 더 없어?"), _asst("맞습니다, 놓쳤습니다. 다시 보겠습니다."),
    ])
    chk("★★ 양성 — 완료 선언→재차 캐물음→원인·방지 없는 시인을 잡는다 (실사고 2026-09-05, PIU)",
        len(completion_reask_cycle(cyc_hit)) == 1, str(completion_reask_cycle(cyc_hit)))

    cyc_ok = turns([
        u("작업해줘"), _asst("작업 끝났습니다."),
        u("진짜? 더 없어?"),
        _asst("맞습니다, 놓쳤습니다 — 훅이 0회라고 했는데 확인 없이 넘긴 게 원인입니다. "
              "다음부터는 훅 메시지를 먼저 확인하고 안 그러기로 합니다."),
    ])
    chk("음성 — 원인·방지가 둘 다 있으면 안 걸린다", not completion_reask_cycle(cyc_ok))

    cyc_noreask = turns([
        u("작업해줘"), _asst("작업 끝났습니다."),
        u("고마워"), _asst("네."),
    ])
    chk("음성 — 완료 선언 뒤에도 재차 캐묻지 않으면 안 걸린다(사용자를 나무라지 않는다)",
        not completion_reask_cycle(cyc_noreask))

    def _edit(path):
        return {"type": "assistant", "message": {"role": "assistant",
                "content": [{"type": "tool_use", "name": "Edit",
                             "input": {"file_path": path}}]}}

    def _bash(cmd):
        return {"type": "assistant", "message": {"role": "assistant",
                "content": [{"type": "tool_use", "name": "Bash",
                             "input": {"command": cmd}}]}}

    ub_hit = [_edit("data/thermo/ch01.json"), _asst("ch01 수정 끝났습니다.")]
    chk("★★ 양성(전공정리 전용) — data/ 편집 뒤 재빌드 없이 완료를 선언하면 잡는다"
        " (/insights 2026-09-06 최다 마찰 재현)",
        len(unbuilt_completion(ub_hit)) == 1, str(unbuilt_completion(ub_hit)))

    ub_ok = [_edit("data/thermo/ch01.json"),
             _bash("python tools/build_site.py --all"),
             _asst("ch01 수정하고 빌드까지 끝났습니다.")]
    chk("음성 — data/ 편집 뒤 build_site.py 를 불렀으면 안 걸린다",
        not unbuilt_completion(ub_ok))

    ub_noedit = [_bash("python tools/check_narration.py"), _asst("확인 끝났습니다.")]
    chk("음성 — data/ 를 안 건드렸으면 완료 선언만으로는 안 걸린다",
        not unbuilt_completion(ub_noedit))

    ub_norecomplete = [_edit("tools/build_site.py"), _asst("도구 코드 수정 끝났습니다.")]
    chk("음성 — data/ 가 아니라 도구 코드를 고친 것은 대상이 아니다",
        not unbuilt_completion(ub_norecomplete))

    ub_metadata = [_edit("site/metadata/index.json"), _asst("메타데이터 수정 끝났습니다.")]
    chk("음성 — 「metadata/」처럼 data 를 낱말 일부로 포함한 경로는 오탐 아니다",
        not unbuilt_completion(ub_metadata))
    uv_open = ["- 새 스킬 4개가 목록에 뜨는지: 미검증"]
    chk("미검증 — 뒤에서 해소 안 되면 남는다", len(unverified(uv_open + ["다른 이야기입니다."])) == 1)
    chk("미검증 — 뒤에서 같은 대상 + 「떴습니다」면 해소", not unverified(uv_open + ["스킬 4개가 목록에 떴습니다."]))
    chk("미검증 — `(검증됨: …)` 표식이면 해소", not unverified(uv_open + ["(검증됨: 목록 확인)"]))
    chk("미검증 — 따옴표 안의 언급은 판정이 아니다", not unverified(["- 「미검증」 경보가 풀리지 않던 문제: 고쳤다"]))

    chk("★ 양성 — 확신 부족 어구를 쓰고 안 물으면 잡는다 (실사고 2026-08-27)",
        len(self_hedge_unasked(["근거가 있어서가 아니라 다른 자리가 없어서다."])) == 1)
    chk("음성 — 확신 부족 어구가 있어도 그 응답이 물음으로 끝나면 안 걸린다",
        not self_hedge_unasked(["확신이 없는데, 이렇게 진행할까요?"]))
    chk("음성 — 확신 부족 어구 자체가 없으면 안 걸린다",
        not self_hedge_unasked(["이건 A 로 하겠습니다."]))

    # ★ 2026-08-31 — `last_turn_verdict` 가 barehanded 도 턴 단위로 잡는지 (실사고 회귀).
    import io
    import contextlib
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "fake.jsonl"
        with p.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "user", "message": {"role": "user",
                     "content": "질문"}}) + "\n")
            fh.write(json.dumps({"type": "assistant", "message": {"role": "assistant",
                     "content": [{"type": "text", "text": "이렇게 할까요?"}]}}) + "\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            last_turn_verdict([p])
        chk("★ 양성 — 지난 턴이 빈손으로 물었으면 last_turn_verdict 가 낸다 (실사고 회귀)",
            "빈손으로 물었다" in buf.getvalue())

        p2 = Path(td) / "fake2.jsonl"
        with p2.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "user", "message": {"role": "user",
                     "content": "질문"}}) + "\n")
            fh.write(json.dumps({"type": "assistant", "message": {"role": "assistant",
                     "content": [{"type": "text", "text": "**제안:** A 로 갑니다."}]}}) + "\n")
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            last_turn_verdict([p2])
        chk("음성 대조 — `**제안:**` 이 있으면 last_turn_verdict 도 조용하다",
            buf2.getvalue() == "")

    print()
    print("  ※ ☐ **이 자는 안 막는다(언제나 exit 0)** — 세는 자다. 대조군이 붙어도")
    print("     그건 안 바뀌고, `audit_gates` 에 「문 아님」으로 계속 뜬다.")
    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def last_turn_verdict(files):
    """Stop/다음 턴 시작 자리 — **넘겼을 때만 한 줄**, 아니면 한 글자도 안 낸다
    (`check_narration.last_turn_verdict` 와 같은 규율). XSanity 이식(2026-08-28).

    ★ **2026-08-31 — 「나머지는 커밋 시점」 결정을 `barehanded` 하나에 한해 뒤집는다.**
      당초 이유("누적 표본이 있어야 소음 없이 판정된다")는 `open_promises`·`unverified`·
      `users>=5` 처럼 **통계적** 판정에는 맞다. 하지만 `barehanded_asks` 는 애초에
      **응답 하나**를 보는 결정적 판정이다(물음으로 끝나는데 `**제안:**` 이 없다 — 참/거짓,
      쌓을 표본이 필요 없다). 그런데도 commit 시점에만 재서, **커밋이 한참 뒤에나(또는
      이 세션처럼 안) 나는 긴 대화에서는 턴 안에서 아무도 못 봤다** — `narration_due` 가
      `check_narration` 에 대해 이미 고친 바로 그 문제(2026-08-24 재발)를 이 판정만
      비껴갔던 것. 실사고: 같은 날 이 판정 자신이 가리키는 08-25 «커밋할까요?» 항목의
      부류가, 이 훅이 없어서 08-31 에 다른 문구("변경일지에 남겨둘까요?")로 다시 났다.
    """
    try:
        from check_narration import records, turn_window
    except ImportError:
        return 0
    if not files:
        return 0
    p = max(files, key=lambda f: f.stat().st_mtime)
    recs = list(records(p))
    s, e = turn_window(recs, completed=True)
    r = audit(recs[s:e])
    # ★★ **누적 판정을 여기서도 낸다** (2026-09-02, 사용자: *[발화 생략]*).
    #   `open_promises`·`unverified`·「지적 있는데 원장 안 움직임」은 위 주석(2026-08-31)이
    #   "통계적 판정이라 표본이 쌓여야 소음 없다"는 이유로 commit 시점(quiet 모드)에만
    #   재고 있었다. 그런데 이 세션에서 실제로 일어난 일은 **커밋이 여러 번 있었고 그때마다
    #   신고도 났는데, 그 콘솔 출력을 사람이 보는 채팅으로 옮기지 않았다** — 재는 자와
    #   규칙(CLAUDE.md 「안 한 것과 사유」)은 이미 있었고 안 지킨 건 습관이었다. 훅은 내
    #   채팅 문장을 대신 못 쓰므로 "매번 새로 쓰게 강제"는 원리적으로 불가능하지만,
    #   **매 턴 끝에 다시 보여주면** 커밋 없이 지나가는 턴에서도 놓치지 않는다 — 상시
    #   신호로 바꾸는 것이 이 자가 실제로 할 수 있는 최선이다. 소음 방지로 표본 하한은
    #   그대로 두되(`users>=5`), 값이 있으면 **턴마다** 보여준다.
    full = audit(recs)
    cum_hits = []
    if full["open_promises"]:
        cum_hits.append(("누적 — 예고하고 안 한 것", full["open_promises"]))
    if full["unverified"]:
        cum_hits.append(("누적 — 미검증이라 적고 둔 것", full["unverified"]))
    if full["completion_cycles"]:
        cum_hits.append(("누적 — 완료 선언 뒤 재차 캐물려서야 시인, 원인·방지 없음",
                         full["completion_cycles"]))
    # ★ 2026-09-11 — 이 판정은 docstring 대로 **전공정리 전용**(`data/` → `build_site.py`)인데 어디서나 돌아,
    #   빌드가 없는 공용 폴더에서 `data/` 낱말만 스쳐도 매 턴 「반드시 옮길 것」을 냈다. 빌드 도구가 있는 곳만.
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    has_build = os.path.isfile(os.path.join(root, "tools", "build_site.py"))
    if full["unbuilt_completion"] and has_build:
        cum_hits.append(("누적 — data/ 고친 뒤 재빌드 없이 완료를 선언했다",
                         full["unbuilt_completion"]))
    if full["users"] >= 5 and not full["ledger_touched"]:
        cum_hits.append(("누적 — 지적을 받았는데 원장·기억이 안 움직였다",
                         ["사용자 발화 %d회 · feedback-ledger·기억 편집 0회" % full["users"]]))
    if cum_hits:
        print("[상호작용] **다음 응답에 반드시 옮길 것 — 여기 있다고 채팅에 자동으로 안 옮겨진다**")
        for label, lines in cum_hits:
            print("  · " + label + " " + str(len(lines)) + "건")
            for line in lines[:3]:
                print("      " + line)
    if r["rules_touched"] and not r["ledger_touched"]:
        print("[상호작용] 규칙 문서를 고쳤는데(%s) 원장은 이번 턴에 그대로였다."
              % ", ".join(r["rules_touched"]))
        print("  지적에서 왔다면 feedback-ledger 에 먼저 한 줄 — 설계 판단이면 적을 것 없음(사람 판정).")
    if r["barehanded"]:
        print("[상호작용] 지난 턴이 빈손으로 물었다 — 이미 실린 규칙에 답이 있는 건 아닌지 먼저 본다:")
        for line in r["barehanded"][:2]:
            print("    " + line)
        print("  물어야 한다면 `**제안:**` 형식으로(규칙/물어야-할-때.md).")
    if r["self_hedge"]:
        print("[상호작용] 지난 턴에 확신 부족 어구를 쓰고도 안 물었다 — 그 자체가 물어야 한다는 신호다:")
        for line in r["self_hedge"][:2]:
            print("    " + line)
    if r["leftover_missing"]:
        print("[상호작용] 도구를 쓴 턴이 「남은 일」 표지 없이 끝났다: %r"
              % r["leftover_missing"])
        print("  덩어리가 끝나면 남은 일 유무를 `**남은 일:**` 로 적는다.")
    return 0


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    if "--selftest" in flags:
        print("[자기 검정] 세션 품행 감사기")
        return selftest()
    if "--last-turn" in flags:
        folder = cost.find_dir(os.getcwd())
        if folder is None:
            return 0
        return last_turn_verdict(sorted(Path(folder).glob("*.jsonl"),
                                         key=lambda p: p.stat().st_mtime))
    quiet = "--quiet" in flags
    n = 1
    for f in flags:
        if f.startswith("--sessions="):
            try:
                n = max(1, int(f.split("=", 1)[1]))
            except ValueError:
                n = 1
    folder = cost.find_dir(os.getcwd())
    if folder is None:
        if not quiet:
            print("[상호작용] 이 프로젝트의 세션 기록을 못 찾았다 — 건너뛴다.")
        return 0
    files = sorted(Path(folder).glob("*.jsonl"), key=lambda p: p.stat().st_mtime)[-n:]
    r = audit(load(files))

    hits = []
    if r["open_promises"]:
        hits.append(("예고하고 안 한 것", r["open_promises"]))
    if r["unverified"]:
        hits.append(("미검증이라 적고 둔 것", r["unverified"]))
    if r["barehanded"]:
        hits.append(("빈손으로 물은 것 — 물음으로 끝나는데 `**제안:**` 이 없다",
                     r["barehanded"]))
    if r["self_hedge"]:
        hits.append(("확신 부족 어구를 쓰고도 안 물은 것 — 그 자체가 물어야 한다는 신호다",
                     r["self_hedge"]))
    if r["users"] >= 5 and not r["ledger_touched"]:
        hits.append(("지적을 받았는데 원장·기억이 안 움직였다",
                     ["사용자 발화 %d회 · feedback-ledger·기억 편집 0회" % r["users"]]))
    if r["rules_touched"] and not r["ledger_touched"]:
        hits.append(("규칙 문서가 자랐는데 원장이 안 움직였다 — **이게 지적에서 왔나?**",
                     ["고친 자리: " + ", ".join(r["rules_touched"]),
                      "지적에서 왔다면 원장에 먼저 한 줄이 있어야 한다 —"
                      " `python 도구/feedback_lookup.py \"<지적 요지>\"` 로 재발부터 본다",
                      "설계 판단에서 왔다면 적을 것이 없는 게 맞다 — **판정은 사람이 한다**"]))
    if not hits:
        if not quiet:
            print("[상호작용] 걸린 것 없음 (예고 미이행 0 · 미검증 0 · 원장 갱신 있음)")
        return 0

    print("[상호작용] **판정이 아니라 셈이다 — 사람이 본다**")
    for label, lines in hits:
        print("  · " + label + " " + str(len(lines)) + "건")
        for line in lines[:4]:
            print("      " + line)
    if r["promise_human"] and not quiet:
        print("  · [사람] 대상이 안 적힌 예고 " + str(len(r["promise_human"])) + "건 — 기계가 이행을 못 잰다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
