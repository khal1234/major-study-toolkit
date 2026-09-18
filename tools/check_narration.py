"""**진행 중계가 선을 넘었는가** — 이건 세는 자가 아니라 막는 자다.

왜 또 만드나 (같은 지적 4회차, 2026-08-15)
-------------------------------------------
*[발화 생략]*

이번 세션에서 실제로 있던 일:

  ⑴ 내가 **직접** `CLAUDE.md 6b-3` 「진행 중계를 쓰지 않는다」를 이 세션에 이식했다.
  ⑵ 공용에서 `audit_session_conduct.py` 를 가져와 배선했고, 그 자가 첫 실행에서
     **「대상이 안 적힌 예고 36건」** 을 잡았다.
  ⑶ 나는 그 숫자를 **「새 자가 값을 했다」는 성과로 보고**하고 계속 중계를 썼다.
  ⑷ 세션 끝 실측: **진행 중계 198회 · 19,834자.**

즉 **규칙도 있었고 계측도 있었는데 둘 다 안 막았다.** 둘 다 「읽는 것」이라서다.
이 저장소의 규율 그대로다 — *[발화 생략]*

왜 판단형 규칙이 안 먹히나
--------------------------
6b-3 은 문장마다 *[발화 생략]* 를 묻게 한다. 그런데 **그 순간에는
언제나 「사용자에게」로 답이 나온다** — 방금 내가 알아낸 것이라서 값있어 보인다.
판단이 필요한 선은 매번 통과된다. 그래서 **판단이 필요 없는 선**으로 바꾼다:

    도구 호출 사이에 산문을 쓰지 않는다. 최종 보고 하나만 쓴다.

하한을 어디에 두나 (근거)
-------------------------
「0회」를 그대로 게이트로 걸면 **사용자가 턴 도중에 물은 것에 답하는 것**까지 실패로
잡힌다(이번 세션에도 네 번 있었다). 그래서 **사용자 발화 1회당 1줄**을 선으로 둔다 —
그 한 줄이 곧 그 발화에 대한 최종 보고다. 실측 대비: 이번 세션은 사용자 발화 11회에
중계 198회로 **18배**다. 규율을 지킨 세션이 이 선에 걸릴 일은 없다.

    python 도구/check_narration.py            # 이 폴더의 배치
    python tools/check_narration.py           # 가져간 프로젝트의 배치

★★ **이 파일이 중계 판정의 정본이다 — 재는 자는 여기서 가져다 쓴다** (합침 2026-08-15).
   `audit_session_cost.py` 가 같은 것을 자기 코드로 또 세고 있었다. 둘 다 맞는 값을 내고
   있었지만 **판정선이 두 벌이면 갈린다** — 한쪽에서 「중계」의 뜻을 고치면 다른 쪽은
   조용히 옛 뜻으로 남는다(이 계통이 `slash_fraction_spans`·`check_answer_sentences` 에서
   이미 «세는 함수는 하나» 로 닫아 둔 부류다).
   → 판정은 `Tally` **한 클래스**에 있고, 두 도구가 그것을 먹인다.
   **역할은 그대로 둘이다:** 이 파일은 **막는 자**(`close_report` 가 부른다 · 넘으면 exit 1),
   `audit_session_cost` 는 **재는 자**(언제나 exit 0 · 자기 과거와의 추세). 게이트만 남기면
   «과거와 견주는» 축이 사라지고, 계측만 남기면 아무것도 안 막힌다 — 이미 겪은 일이다.

★★★ **Stop 훅에 걸었다 — 「막는 자」가 아무 문에도 안 걸려 있었다** (2026-08-24, 3회차).

    settings.json 의 Stop 훅:
        python "$CLAUDE_PROJECT_DIR/도구/check_narration.py" --last-turn

  *[발화 생략]* — **조항이 실려 있는데도** 재발했다(전공정리 ee 세션).
  실측하니 판정은 멀쩡한데 **받는 문이 없었다:** `commit.py` 는 `check=False` 로 부르고
  종료코드를 버리며(«커밋 결과를 뒤집지 않는다» 는 계약), `close_report` 는 세기만 하고,
  훅 여덟 중 이 자를 부르는 것이 **0개**였다. 공용 폴더 `.claude/settings.json` 이 이미 2026-08-16 에
  *[발화 생략]* 고 적어 뒀는데 그 줄이 여태 그대로였다.

  **왜 커밋·닫기로는 원리적으로 못 막나.** 중계는 **턴 안에서** 생기고 사용자가 그 자리에서
  읽는다 — 커밋 시점엔 이미 읽힌 뒤다. 「방지장치의 트리거는 반드시 하는 일에 건다」가 꼽은
  셋(**턴마다** · 커밋 · 빌드) 중 **턴마다**만 비어 있었다.

  판정선·못 보는 것은 `last_turn_verdict` 독스트링이 정본이다.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xsio import force_utf8

force_utf8()

ROOT = Path(__file__).resolve().parent.parent
SESSIONS = Path.home() / ".claude" / "projects"

# 사용자 발화 1회당 허용 중계 줄 수. 위 [발화 생략] 참조 —
# 그 한 줄이 곧 그 발화에 대한 최종 보고다.
MAX_PER_USER_TURN = 1.0
# 발화가 이보다 적으면 비율이 요동쳐 판정이 소음이 된다(`cost_brief` 와 같은 규율).
MIN_TURNS = 3

# ── 두 번째 잣대: **굵은 제목으로 시작하는가** (사용자 제안 2026-08-15) ──────
#
# *[발화 생략]*
#
# ★ 이게 **판단형 규칙을 셀 수 있게 만든다.** 「값어치 있나」는 매번 통과되지만
#   *[발화 생략]* 는 안 그렇다 — **행위 보고는 제목이 못 된다.**
#   「현재 판을 먼저 보존합니다」·「나머지를 봅니다」는 제목으로 쓸 수 없고,
#   「등록부가 오늘 할 것을 손으로 쓴 페이지로 적어 뒀다」는 제목이 된다.
#   즉 **제목을 못 붙이겠으면 그건 안 써도 되는 말**이다.
#
# 실측(2026-08-15 이 세션): 중계 151개 중 굵은 제목 시작 **14개(9%)** ·
# 최종 보고 27개 중 **19개(70%)**. 최종 보고는 이미 되고 있고 중계가 안 된다.
HEAD = re.compile(r"^\s*(#{1,4}\s+\S|\*\*[^*]{2,})")
# 실측 최종 보고가 70% 다. 거기서 한 단계 아래를 하한으로 둔다 — 0.60 자체에
# 뜻이 있는 것이 아니라 «제목이 안 붙는 말은 안 쓴다» 가 지켜지는지 보는 선이다.
MIN_HEAD_RATIO = 0.60

# ── 세 번째 잣대: **말투가 존댓말인가** (2026-08-28, XSanity 08-27·08-28 재발) ──────
#
# 원장 처방: "말투는 검사가 못 읽는다"(XSanity CLAUDE.md 567행)가 재발의 진짜 원인이었다.
# 실제로 샌 자리는 언제나 **이 파일이 이미 세는 그 중계 줄**이었다 — 0회여야 할 자리에
# 문장이 나올 때, 그 문장이 하필 영어거나 반말이었다. 그래서 새 자를 만들지 않고
# **이미 있는 관측 지점**(중계로 잡힌 텍스트)에 두 번째 잣대만 얹는다.
#
# 판정선(규칙 17 — 판단형이 아니라 셀 수 있는 형식으로):
#   ⑴ 그 줄에 알파벳 글자가 있고 한글 글자보다 많으면 위반(영어로 새는 것)
#   ⑵ 한글로 끝나는 문장인데 존댓말 종결어미가 아니라 평어 종결어미로 끝나면 위반
# 코드 조각(백틱 안)·파일 경로·명령어 줄은 먼저 걷어내고 남은 산문만 잰다.
# 재는 범위: 중계 + 최종 보고(공용 폴더 2026-09-11 이식). 최종 보고는 코드블록이 잦아 fenced 블록도 걷는다.
_FENCE = re.compile(r"```.*?```", re.S)
_CODE_SPAN = re.compile(r"`[^`]*`")
_HANGUL = re.compile(r"[가-힣]")
_ASCII_LETTER = re.compile(r"[A-Za-z]")
_POLITE_END = re.compile(r"(니다|세요|에요|나요|ㅂ시다|죠|가요|까요)[.!?～]*\s*$")
_CASUAL_END = re.compile(r"(다|야|어|음|봄|함|줌|짐)[.!?～]*\s*$")
# ── 네 번째 잣대: 「겠습니다」류 예고 종결 (2026-09-02, 사용자 재지적) ──────────
#
# *[발화 생략]* — CLAUDE.md 6b-3은
# 「…합니다·…겠습니다·…봅니다」로 끝나는 예고를 **통째로 금지**라고 적어 뒀는데, 이 파일의
# 말투 검사(`_POLITE_END`)는 "겠습니다"를 존댓말로만 보고 **통과**시켰다 — 예고인지 아닌지는
# 안 본다. 존댓말 여부와 예고 여부는 다른 축인데 한 축(말투)만 있고 다른 축(예고)이 없었다.
# ★ 판단형("이 말이 예고인가")이 아니라 형식으로 잡는다 — 어미 자체를 본다. 「하겠습니다」·
#   「보겠습니다」·「넣겠습니다」처럼 **미래형 어미 "겠"** 으로 끝나면, 그 문장이 실제로
#   이행됐는지와 무관하게 **그 자리에서 이미 규칙 위반**이다(할 거면 그냥 하면 된다는 것이
#   원칙이지, 예고가 나중에 지켜지면 괜찮다는 뜻이 아니다).
# ★ 「~수 있습니다」·「~할 수도 있습니다」처럼 **가능성을 말하는 겠**은 예고가 아니다 —
#   그래서 어미 바로 앞이 아니라 **문장 전체에 "수 있"이 없을 때만** 잡는다.
_FORECAST_END = re.compile(r"겠(습니다|어요|음|다)[.!?～]*\s*$")
_POSSIBILITY = re.compile(r"수\s*있")


def _prose_lines(text):
    """중계·최종 보고에서 코드블록·코드·경로를 걷어낸 산문 줄만 낸다. 빈 줄은 뺀다."""
    text = _FENCE.sub(" ", text)
    out = []
    for line in text.splitlines():
        line = _CODE_SPAN.sub(" ", line)
        line = line.strip(" -*>#·|")
        if line:
            out.append(line)
    return out


def tone_bad_count(text):
    """`(잰 줄 수, 위반 줄 수)`. 한글도 영어도 없는 줄(순수 기호·숫자)은 안 잰다."""
    total = bad = 0
    for line in _prose_lines(text):
        hangul = len(_HANGUL.findall(line))
        ascii_letters = len(_ASCII_LETTER.findall(line))
        if hangul == 0 and ascii_letters == 0:
            continue
        total += 1
        if ascii_letters > hangul:
            bad += 1
        elif _FORECAST_END.search(line) and not _POSSIBILITY.search(line):
            bad += 1
    return total, bad


def repo_root():
    """이 리포의 뿌리. **`git rev-parse --git-common-dir` 의 부모**를 쓴다 — 워크트리든
    본체든 같은 값이다. git 이 아니면 이 파일이 사는 폴더의 부모로 떨어진다.

    ★ **같은 질문에 답하는 자가 둘이면 갈리므로** 이 계통이 이미 쓰는 판정선과 같은 것을
      쓴다(`adopt_ledger.project_key` · `audit_session_cost.git_root`).
    """
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--git-common-dir"],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except OSError:
        return ROOT
    if r.returncode != 0 or not (r.stdout or "").strip():
        return ROOT
    common = Path(r.stdout.strip())
    if not common.is_absolute():
        common = ROOT / common
    return common.resolve().parent


def _norm(p):
    return str(p).replace("/", "\\").rstrip("\\").lower()


def is_ours(cwd, root):
    """그 세션이 **이 리포에서 열렸나.** 뿌리이거나 그 아래면 우리 것이다.

    ★★ **첫 판은 이 리포에서 한 번도 안 돌았다** (2026-08-15 실측 — 돌려 보니
      `세션 기록을 못 찾았다 — SKIP`). `ROOT.parent` 를 리포 뿌리로 삼고 있었는데
      그건 이 자가 태어난 곳(`_modding/scripts/`)의 배치에서만 맞는 값이다.
      여기서는 `도구/` 가 뿌리 바로 아래라 **뿌리의 부모**(`Documents`)를 찾고 있었고,
      거기서 열린 세션은 없으니 **언제나 SKIP** 이었다. 막는 자가 조용히 꺼져 있던 것이다 —
      *[발화 생략]*(바로 아래 `CWD_SCAN` 이 겪은 일과 같은 부류).
    ★ **워크트리를 담은 컨테이너 폴더에서 세션이 열리는 리포**는 뿌리가 한 칸 아래라 이
      규칙에 안 걸린다. 그건 그 리포가 **자기 사본에서** 넓힌다(전공정리가 그렇게 했다) —
      여기서 넓히면 남의 프로젝트 세션까지 끌어온다.
    """
    c, r = _norm(cwd), _norm(root)
    return c == r or c.startswith(r + "\\")


def latest_session(root):
    """이 리포에서 가장 최근에 쓴 세션 기록. **`cwd` 로 고른다** — 폴더 이름은
    한글을 뭉개서 다른 프로젝트와 섞인다(공용 `audit_session_cost` 가 겪은 일)."""
    best = None
    if not SESSIONS.is_dir():
        return None
    for d in SESSIONS.iterdir():
        for f in d.glob("*.jsonl") if d.is_dir() else []:
            if not is_ours(_cwd_of(f), root):
                continue
            if best is None or f.stat().st_mtime > best.stat().st_mtime:
                best = f
    return best


# 첫 줄에는 `cwd` 가 없다 — 몇 줄 훑어야 나온다. 첫 판이 첫 줄만 보고
# 「세션 기록을 못 찾았다」를 냈다(자가 못 보면 자료가 없는 것처럼 보인다).
CWD_SCAN = 40


def _cwd_of(path):
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= CWD_SCAN:
                    break
                try:
                    c = json.loads(line).get("cwd")
                except ValueError:
                    continue
                if c:
                    return str(c).replace("/", "\\").rstrip("\\")
    except OSError:
        pass
    return ""


def is_user_text(rec):
    """이 레코드가 **사람이 친 말**인가 — 도구 결과도 `type: "user"` 라 그것과 가른다.

    ★ **턴 경계를 찾는 자와 발화를 세는 자가 같은 판정을 써야 한다.** 둘로 두면
      「직전 턴」의 시작점과 「발화 1회」가 조용히 어긋난다(이 계통이 `Tally` 를 한 벌로
      묶어 둔 것과 같은 이유).
    """
    if rec.get("type") != "user":
        return False
    c = (rec.get("message") or {}).get("content")
    return isinstance(c, str) or (isinstance(c, list) and any(
        isinstance(b, dict) and b.get("type") == "text" for b in c))


class Tally:
    """**중계 판정의 정본.** 세션 기록의 레코드를 하나씩 `feed` 하고 `result()` 를 받는다.

    **중계 = 도구 호출이 딸린 응답에 들어간 말.** 도구가 안 붙은 응답의 글은
    최종 보고라 안 센다. 기록이 응답 하나를 텍스트/도구 레코드로 **쪼개** 두므로
    `requestId` 로 묶어야 한다 — 안 묶으면 **언제나 0회**가 나온다(공용에서 겪음).

    ★ **왜 클래스이고 왜 파일을 안 읽나.** 재는 자(`audit_session_cost`)는 한 번 훑으며
      열 가지를 세는데, 여기서 파일을 또 열면 같은 세션을 두 번 읽는다. 레코드를 먹이는
      형태라야 **판정은 한 벌**이면서 **읽기는 한 번**이다.
    """

    def __init__(self):
        self.users = 0
        self._said = {}
        self._hastool = set()

    def feed(self, rec):
        t = rec.get("type")
        if t == "user":
            if is_user_text(rec):
                self.users += 1
            return
        if t != "assistant":
            return
        key = rec.get("requestId") or rec.get("uuid")
        for b in ((rec.get("message") or {}).get("content") or []):
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and b.get("text", "").strip():
                self._said[key] = self._said.get(key, "") + b["text"]
            elif b.get("type") == "tool_use":
                self._hastool.add(key)

    def result(self):
        """`users` 사용자 발화 · `n`·`chars` 중계 · `final` 최종 보고 글자 ·
        `msgs`·`headed` 굵은 제목 비율의 분모·분자 · `tone_*` 는 중계+최종 보고 합,
        `relay_tone_*`·`final_tone_*` 는 가른 값."""
        relay = [v for k, v in self._said.items() if k in self._hastool]
        final = [v for k, v in self._said.items() if k not in self._hastool]
        allsaid = [v.strip() for v in self._said.values() if v.strip()]

        def tally_tone(vs):
            t = b = 0
            for v in vs:
                tt, bb = tone_bad_count(v)
                t += tt
                b += bb
            return t, b

        relay_tone_total, relay_tone_bad = tally_tone(relay)
        final_tone_total, final_tone_bad = tally_tone(final)
        return {
            "users": self.users,
            "n": len(relay),
            "chars": sum(len(v) for v in relay),
            "final": sum(len(v) for v in final),
            "msgs": len(allsaid),
            "headed": sum(1 for v in allsaid if HEAD.match(v)),
            "tone_total": relay_tone_total + final_tone_total,
            "tone_bad": relay_tone_bad + final_tone_bad,
            "relay_tone_total": relay_tone_total,
            "relay_tone_bad": relay_tone_bad,
            "final_tone_total": final_tone_total,
            "final_tone_bad": final_tone_bad,
        }


def records(path):
    """세션 파일의 레코드를 순서대로. 깨진 줄은 건너뛴다."""
    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            yield json.loads(line)
        except ValueError:
            continue


def count(path):
    """세션 파일 하나를 훑어 `Tally.result()` 를 낸다."""
    t = Tally()
    for rec in records(path):
        t.feed(rec)
    return t.result()


def turn_window(recs, completed=False):
    """직전 턴의 `(시작, 끝)` 인덱스. 순수 함수 — 테스트 대상.

    ★★ `completed=True` 는 **어시스턴트 기록이 실제로 있는** 마지막 턴을 고른다.
      `UserPromptSubmit` 훅은 **새 사용자 발화가 기록에 이미 들어간 뒤**에 설 수 있어서,
      그냥 «마지막 발화 이후» 로 잡으면 창이 비어 **언제나 0줄**이 나온다 — 자가 조용히
      꺼지고, **꺼진 자는 「깨끗하다」와 겉모습이 같다**(이 폴더가 반복해 잡아 온 그 형태).
      **기록 순서가 어느 쪽이든 같은 답을 내는 것**이 이 인자의 목적이다.
    """
    starts = [i for i, r in enumerate(recs) if is_user_text(r)]
    if not starts:
        return 0, len(recs)
    for k in range(len(starts) - 1, -1, -1):
        s = starts[k]
        e = starts[k + 1] if k + 1 < len(starts) else len(recs)
        if not completed or any(r.get("type") == "assistant" for r in recs[s:e]):
            return s, e
    return starts[-1], len(recs)


def count_last_turn(path, completed=False):
    """**직전 턴만** 센다 — 그 창의 레코드만 같은 `Tally` 에 먹인다.

    누적이 아니라 턴인 것이 요점이다. 누적값은 close 시점에 이미 확정이라
    «고치고 다시 돌리면 초록» 이 불가능하고, 못 지우는 빨간불은 게이트가 아니라 벽이다
    (2026-08-15 사용자 판정). **턴 단위면 [발화 생략]이 매 턴 새로 온다.**
    """
    recs = list(records(path))
    s, e = turn_window(recs, completed)
    t = Tally()
    for rec in recs[s:e]:
        t.feed(rec)
    return t.result()


def last_turn_verdict(path, completed=False, prefix=""):
    """Stop 훅의 자리 — **넘겼을 때만 한 줄**, 아니면 한 글자도 안 낸다
    (`open_items`·`cost_brief`·`shared_sync_check` 와 같은 규율).

    왜 이 자리가 열렸나 (2026-08-24, 같은 지적 3회차)
    ------------------------------------------------
    *[발화 생략]* — 조항이 **실려 있는데도** 재발했다(전공정리 ee 세션).
    실측하니 이 자는 판정을 제대로 하는데 **아무 문에도 안 걸려 있었다**:
    `commit.py` 는 `check=False` 로 부르고 종료코드를 버리며(계약상 그렇다),
    `close_report` 는 세기만 하고, 훅 여덟 중 부르는 것이 **0개**였다.
    중계는 **턴 안에서** 생기고 사용자가 그 자리에서 읽으므로 커밋·닫기 트리거로는
    원리적으로 못 막는다 — 「반드시 하는 일」 셋 중 **턴마다**만 비어 있었다.

    판정선을 어떻게 두나
    --------------------
    ★ **세션 판정과 같은 상수**(`MAX_PER_USER_TURN`)를 쓴다. 턴 하나에 사용자 발화는
      1회이므로 «발화당 상한» 이 곧 «이 턴에 몇 줄까지» 다 — 새 눈금을 만들지 않는다.
    ★ **제목 하한은 여기서 판정하지 않는다.** 표본이 한 턴이라 비율이 0% 아니면 100% 로
      튄다. 그건 판정이 아니라 소음이고, **소음은 검사기를 죽인다**(경보 피로).
      제목은 표본이 쌓이는 세션 판정이 계속 본다.

    ☐ 못 보는 것 — 정직하게 적는다
    ------------------------------
    - **이 자는 턴이 끝난 뒤에 선다.** 이미 나간 말을 되돌리지 못한다. 할 수 있는 것은
      **다음 턴을 0 으로 만드는 것** 하나다.
    - **멈춤을 막지 않는다(exit 0).** 「글이 많다」고 멈춤을 막으면 자가 더 쓰게 된다 —
      처방이 병을 키우는 자리라 일부러 안 막는다.
    - 훅 출력이 **다음 턴의 문맥에 들어가는지는 이 자가 보증하지 못한다.** 확실한 것은
      사용자 화면에 뜬다는 것뿐이다(그것이 이번 지적을 낸 채널이다).
    """
    r = count_last_turn(path, completed)
    n = r["n"]
    tone_total, tone_bad = r["tone_total"], r["tone_bad"]
    if n <= MAX_PER_USER_TURN and tone_bad == 0:
        return 0                      # ★ 평소에는 **한 글자도 안 낸다**
    if n > MAX_PER_USER_TURN:
        print("[진행 중계] %s턴에 %d줄 · %d자 — **상한은 턴당 %.0f줄이다.**"
              % (prefix or "방금 ", n, r["chars"], MAX_PER_USER_TURN))
        print("  「…합니다 · …겠습니다 · …봅니다」 예고와 「확인했습니다」 행위 보고는")
        print("  도구 호출 줄이 이미 보여 준다 — **이번 턴은 도구 호출 앞에 문장을 쓰지 않는다(0회).**")
    if tone_bad:
        print("[말투] %s중계+최종 보고 %d줄 중 %d줄이 영어·평어·예고체로 샜다 (중계 %d/%d · 최종 %d/%d)"
              " — **채팅은 존댓말, 예고는 금지다.**"
              % (prefix or "방금 ", tone_total, tone_bad,
                 r["relay_tone_bad"], r["relay_tone_total"],
                 r["final_tone_bad"], r["final_tone_total"]))
        print("  (규칙/말투.md · CLAUDE.md 「말투」·6b-3 절 — 「…겠습니다」로 끝나면 그 자리에서")
        print("  이미 위반이다(나중에 지켜져도 소용없다) — 도구 호출 사이 문장을 없애면 이 줄도 같이 없어진다)")
    return 0


def _rec_user(text="사람이 친 말"):
    return {"type": "user", "message": {"content": text}}


def _rec_toolresult():
    return {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}


def _rec_asst(rid, text, tool=True):
    c = [{"type": "text", "text": text}]
    if tool:
        c.append({"type": "tool_use", "name": "Bash", "input": {}})
    return {"type": "assistant", "requestId": rid, "message": {"content": c}}


def selftest():
    """★ 이 자는 **매 턴** 도는 막는 자인데 **대조군이 없었다** (붙임 2026-08-25).

    「문」이 실제로 열리고 닫히는지 아무도 안 봤다 — 공용 「규칙/증거의-정직.md」 ⑴ 이
    금지하는 자리다. `audit_gates --run-selftests` 가 이제 이것을 부른다.
    """
    bad = 0

    def chk(desc, cond, got=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %-44s %s" % ("OK  " if cond else "**틀림**", desc, got))

    chk("도구 결과는 사용자 발화가 아니다", not is_user_text(_rec_toolresult()))
    chk("사람이 친 말은 발화다", is_user_text(_rec_user()))

    t = Tally()
    for r in [_rec_user(), _rec_asst("r1", "가"), _rec_toolresult(),
              _rec_asst("r2", "최종 보고", tool=False)]:
        t.feed(r)
    res = t.result()
    chk("도구 딸린 말만 중계로 센다 (최종 보고는 뺀다)",
        res["n"] == 1 and res["users"] == 1, "n=%d users=%d" % (res["n"], res["users"]))

    chk("굵은 제목은 제목으로 인정한다", bool(HEAD.match("**무엇을 알게 됐나**")))
    chk("행위 보고는 제목이 아니다", not HEAD.match("나머지를 봅니다"))

    tt2, tb2 = tone_bad_count("Now let's regenerate and verify.")
    chk("영어 문장은 말투 위반", tt2 == 1 and tb2 == 1, "total=%d bad=%d" % (tt2, tb2))
    tt3, tb3 = tone_bad_count("확인했습니다.")
    chk("존댓말 종결은 통과", tt3 == 1 and tb3 == 0, "total=%d bad=%d" % (tt3, tb3))
    tt4, tb4 = tone_bad_count("이제 재생성하고 검증할게.")
    chk("친근한 존중체는 통과", tt4 == 1 and tb4 == 0, "total=%d bad=%d" % (tt4, tb4))
    tt5, tb5 = tone_bad_count("실행됨 명령 3개, `make_zone_map.py` +44 -10")
    chk("코드 걷어낸 뒤 남은 산문은 위반 아니면 통과", tb5 == 0, "total=%d bad=%d" % (tt5, tb5))
    tt6, tb6 = tone_bad_count("`check_narration.py`")
    chk("백틱 안 내용만 있는 줄은 안 잰다", tt6 == 0, "total=%d" % tt6)
    tt7, tb7 = tone_bad_count("다음 방지장치를 공용 폴더 원장에 넣겠습니다.")
    chk("「겠습니다」 예고 종결은 존댓말이어도 위반", tt7 == 1 and tb7 == 1, "total=%d bad=%d" % (tt7, tb7))
    tt8, tb8 = tone_bad_count("시간이 있으면 오늘 안에 끝낼 수 있습니다.")
    chk("「수 있습니다」는 가능성이지 예고가 아니다 — 통과", tt8 == 1 and tb8 == 0, "total=%d bad=%d" % (tt8, tb8))
    tt9, tb9 = tone_bad_count("한 줄입니다.\n```\ndef f():\n    return 1이다\n```\n또 한 줄입니다.")
    chk("fenced 코드블록 안 내용은 안 잰다", tt9 == 2 and tb9 == 0, "total=%d bad=%d" % (tt9, tb9))
    t2 = Tally()
    for r in [_rec_user(), _rec_asst("f1", "Final result is ready.", tool=False)]:
        t2.feed(r)
    res2 = t2.result()
    chk("최종 보고(도구 없는 응답)의 영어도 tone_bad 로 잡는다",
        res2["final_tone_bad"] == 1 and res2["relay_tone_bad"] == 0 and res2["tone_bad"] == 1,
        "final_bad=%d relay_bad=%d" % (res2["final_tone_bad"], res2["relay_tone_bad"]))

    recs = [_rec_user(), _rec_asst("a", "가"), _rec_toolresult(),
            _rec_asst("b", "나"), _rec_toolresult(), _rec_user("새 발화")]
    s, e = turn_window(recs, completed=False)
    chk("completed=False 는 마지막 발화 뒤 — 창이 비어 0줄", s == len(recs) - 1)
    s2, e2 = turn_window(recs, completed=True)
    tt = Tally()
    for r in recs[s2:e2]:
        tt.feed(r)
    chk("★ completed=True 는 어시스턴트가 있는 마지막 턴을 고른다",
        tt.result()["n"] == 2, "n=%d" % tt.result()["n"])

    print()
    print("  ※ ☐ 이 자가 **못 보는 것**: 「이 말이 값어치가 있나」는 안 본다 —")
    print("     세는 것은 **도구 호출이 딸린 응답에 글이 있나** 하나다.")
    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="세션 jsonl 을 직접 지정")
    # ★ `commit.py` 가 이 자를 `--quiet` 로 부른다 — 없어서 커밋마다 argparse 오류를 냈다
    #   (2026-08-16). **나빠진 것이 없으면 한 글자도 안 낸다** 는 훅·마감 검사의 공통 규율이고,
    #   그게 없으면 매 커밋에 두 줄이 붙어 곧 아무도 안 읽는다.
    ap.add_argument("--quiet", action="store_true",
                    help="넘긴 것이 없으면 침묵한다 (commit.py 가 쓴다)")
    # ★ Stop 훅이 이것으로 부른다 (2026-08-24). 누적이 아니라 **직전 턴만** 본다 —
    #   사유는 `last_turn_verdict` 독스트링이 정본이다.
    ap.add_argument("--selftest", action="store_true",
                    help="대조군으로 자를 먼저 잰다 (audit_gates 연쇄가 부른다)")
    ap.add_argument("--last-turn", action="store_true",
                    help="직전 턴만 판정한다 (Stop 훅) — 넘겼을 때만 한 줄, exit 0")
    a = ap.parse_args(argv)
    if a.selftest:
        print("[자기 검정] 진행 중계 판정기")
        return selftest()

    root = repo_root()
    p = Path(a.file) if a.file else latest_session(root)
    if a.last_turn:
        # ★ 훅은 **못 찾았을 때도 조용해야 한다.** 매 턴 「못 찾았다」가 뜨면 그것 자체가
        #   이 자가 잡으려는 그 소음이 된다. 자가 꺼진 채인지는 `--last-turn` 없이 돌려 본다.
        return last_turn_verdict(p) if p and p.exists() else 0
    if not p or not p.exists():
        # ★ **어디를 봤는지 함께 적는다.** 그냥 「못 찾았다」면 «세션이 없다» 와
        #   «자가 엉뚱한 데를 본다» 가 구별되지 않는다 — 실제로 그래서 몇 세션을 놓쳤다.
        print("세션 기록을 못 찾았다 — SKIP  (찾은 자리: cwd 가 %s 이거나 그 아래인 세션)"
              % root)
        return 0
    r = count(p)
    users, n, chars = r["users"], r["n"], r["chars"]
    msgs, headed = r["msgs"], r["headed"]
    if users < MIN_TURNS:
        print("사용자 발화 %d회 — 표본이 작아 판정하지 않는다 (하한 %d)"
              % (users, MIN_TURNS))
        return 0
    ratio = n / float(users)
    hr = headed / float(msgs) if msgs else 1.0
    tone_total, tone_bad = r["tone_total"], r["tone_bad"]
    tone_rate = tone_bad / float(tone_total) if tone_total else 0.0
    bad = []
    if ratio > MAX_PER_USER_TURN:
        bad.append("중계가 상한의 %.0f배" % (ratio / MAX_PER_USER_TURN))
    if hr < MIN_HEAD_RATIO:
        bad.append("제목 없이 시작한 말이 %.0f%%" % (100 * (1 - hr)))
    if tone_bad:
        bad.append("영어·평어·예고체로 샌 중계+최종 보고 %d/%d줄 (%.0f%%)" % (tone_bad, tone_total, 100 * tone_rate))
    if not (a.quiet and not bad):
        print("진행 중계 %d회 · %d자 / 사용자 발화 %d회  ->  발화당 %.1f (상한 %.1f)"
              % (n, chars, users, ratio, MAX_PER_USER_TURN))
        print("굵은 제목으로 시작 %d / %d (%.0f%%, 하한 %.0f%%)"
              % (headed, msgs, 100 * hr, 100 * MIN_HEAD_RATIO))
        print("존댓말로 끝난 중계+최종 보고 %d / %d (%.0f%% 위반, 중계 %d/%d · 최종 %d/%d)"
              % (tone_total - tone_bad, tone_total, 100 * tone_rate,
                 r["relay_tone_bad"], r["relay_tone_total"],
                 r["final_tone_bad"], r["final_tone_total"]))
    if not bad:
        if not a.quiet:
            print("OK   0 problem(s).")
        return 0
    print("\nFAIL — " + " · ".join(bad))
    print("  **첫 줄은 굵은 제목이어야 한다.** 제목을 못 붙이겠으면 그건 안 써도 되는 말이다 —")
    print("  「…합니다」·「…봅니다」 같은 행위 보고는 제목이 안 된다.")
    print("  (CLAUDE.md 6b-3 · 공용 `규칙/방지장치-설계.md` 16항)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
