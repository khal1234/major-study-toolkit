# -*- coding: utf-8 -*-
"""연습문제가 교재 원문을 옮겨 적은 것인지 검사한다 (규칙 3·규칙 12⑷).

**왜 빌드로 올렸나 (2026-08-01).** 이 검사는 원래 읽기 전용 도구
`tools/audit_problem_originality.py` 하나였다. 전수 규모를 먼저 재기 위해서였고
(측정 전에 error 로 박으면 몇 건이 걸릴지 모르는 채 빌드를 세운다), 그 측정이 끝났다 —
83문항 중 복제의심 13건을 재작성해 **0건**으로 만들었다. 이제 남은 위험은 *다시 들어오는 것*이고,
그건 사람의 성실성이 아니라 기계가 막아야 한다(AGENTS 「close의 정의」).

**판정 기준(연속 일치 단어 수)은 도구 시절 그대로다 — 걸리는 게 많다고 낮추지 않는다.**
  · 12단어 이상 = **복제 의심 → error.** 예외 없다(허용 목록도 두지 않는다).
  · 7~11단어 = **부분 차용 → 판정을 기록해야 통과한다.** `problem-originality-verdicts.json`
    에 그 문항의 `구간`(우리 문장에서 잘라낸 말)과 `근거`가 있어야 한다.
    "steady-flow" 같은 관용구까지 재작성을 강요하면 용어가 틀려지므로 자동 통과도, 자동 실패도
    답이 아니다 — **사람이 판정하고 그 판정이 파일에 남아 있는 상태**를 강제한다.

**지문이 없으면 검사하지 않고 그렇게 말한다.** n-gram 지문(`.textbook-fingerprint/`)은 교재 PDF
에서 만들고 `.gitignore` 로 빠진다. 없는 워크트리에서 error 를 내면 빌드가 통째로 막히므로,
건너뛰되 **건너뛰었다고 출력한다**(규칙 11 — 미검증을 검증된 것처럼 두지 않는다).

**원문은 어디에도 저장하지 않는다.** 비교는 SHA256 n-gram 해시로만 하고, 화면에 찍는 구간은
**우리 문장**에서 잘라낸 것이다(규칙 3).
"""
import hashlib
import json
import os
import re

# 판정 기준 — 연속 일치 단어 수. 원문 대조 4건의 실측에서 뽑았다(2026-08-01):
#   q04(완전 동일) 8단어 전부 · q10(완전 동일) 16단어 전부 · q06 12단어 · q02 21단어.
COPY_WORDS = 12     # 이 이상 연속 일치면 '옮겨 적었다'고 본다
NEAR_WORDS = 7      # 이 이상이면 부분 차용 — 사람이 판정하고 기록해야 한다

# 6 은 흔한 관용구도 걸린다("the total mechanical energy of the"), 15 는 명백한 복제다.
# 셋을 함께 재야 '부분 차용'과 '통째 복제'를 가를 수 있다.
SIZES = (6, 10, 15)

FP_DIRNAME = ".textbook-fingerprint"
VERDICT_NAME = "problem-originality-verdicts.json"

_WORD = re.compile(r"[a-z0-9]+")


def norm_words(text):
    """비교용 단어열. 대소문자·구두점·기호 차이를 지우고 **수치는 남긴다**
    (조건 수치가 같은 것이 복제 판단의 핵심 신호다).

    ☐ **이 자가 못 보는 것 — 한글은 여기서 통째로 사라진다.**
      `[a-z0-9]+` 에 한글 음절이 없어서, **교재 쪽과 문항 쪽 양쪽에서** 똑같이 삭제된다.
      그래서 한국어 교재를 쓰는 과목은 «한국어 문장을 통째로 옮겨 붙여도 0건» 이다
      (2026-08-25 대조군 실측: 역서 한 문단 35어절 복제 → 정상 / 같은 쪽의 라틴 조각 13개 →
      복제의심 13/13). **언어 «불일치» 가 아니라 한글이 양쪽에서 지워지는 것**이라
      한국어 지문을 썼어도 못 잡는다. 아래 `corpus_verdict` 가 그 사실을 화면에 드러낸다.
    """
    return _WORD.findall(str(text or "").lower())


# ── 대조 가능성 — 「잰 0」과 「못 본 0」을 가른다 (신설 2026-08-26) ────────────────
#
# **무엇이 새어나갔나.** 위 `norm_words` 가 한글을 지우므로 한국어 교재의 말뭉치는 라틴 조각
# 몇 천 개로 쪼그라들고, 영문 지문과 12개 연속으로 겹칠 일이 없어 **언제나 0** 이 나온다.
# 그 0 은 통과 화면과 글자 하나 다르지 않았다 — 이 리포가 네 번째로 밟은 부류다
# (`PDF_FOR` 폴백 · 죽은 폴더 이름 · `_is_panel_divider` · 그리고 이것).
#
# ★ **여기서 하는 일은 「못 본다」를 드러내는 것까지다.** 한국어 토큰화를 새로 만들지 않는다
#   (그건 전 갈래 지문 재생성 + 어절 문턱 재측정이 따르는 별개 작업이다).

# 말뭉치가 교재와 **실제로 대조되는지**의 판정선 — 교재 조각 1MB 당 남은 낱말 수.
#
# ★ **고른 값이다. 무엇과 무엇을 견줬나** (실측 2026-08-26, 7개 말뭉치):
#     한국어 역서 — 기계재료 ch01 1,071낱말/11.2MB = **96** · ch02 2,920/15.0 = **195** ·
#                   ch03 7,007/43.6 = **161** · ch05 8,843/51.6 = **171**
#     영문 스캔본 — 열역학 ch01 29,388/62.2MB = **473**
#     영문 텍스트 — 공학수학2 851,371/113.5MB = **7,500** · 전기전자 387,848/42.8MB = **9,068**
#   한국어 무리(96~195)와 영문 무리(473~9,068) 사이의 빈 구간에 세웠다.
# ★ **쪽수가 아니라 MB 를 분모로 쓴 이유:** 쪽수는 지문에 기록돼 있지 않아 지금 알려면 교재
#   PDF 를 다시 열어야 한다. 파일 크기는 `corpus-index.json` 의 `paths` 만으로 즉시 나온다 —
#   **지문 재생성 없이** 판정할 수 있는 유일한 축이다.
# ★ **틀리는 방향이 안전하다:** 해상도가 높은 스캔본은 MB 가 커져 「못 봄」쪽으로 기운다.
#   「못 봄」은 «이 0 을 못 믿는다» 는 뜻이지 «복제가 있다» 가 아니라서, 헛경보의 값이
#   놓친 복제보다 싸다. 반대로 문턱을 낮추면 이 자를 만든 이유가 사라진다.
MIN_WORDS_PER_MB = 300


def corpus_density(words, size_bytes):
    """교재 1MB 당 말뭉치 낱말 수. 못 재면 `None`. 순수 함수 — 테스트가 직접 부른다."""
    try:
        words = int(words)
        size_bytes = int(size_bytes)
    except (TypeError, ValueError):
        return None
    if size_bytes <= 0:
        return None
    return words / (size_bytes / 1048576.0)


def corpus_verdict(words, size_bytes):
    """`(판정, 밀도)` — 판정은 `"대조됨"` · `"못 봄"` · `"모름"` 셋 중 하나.

    **`"모름"` 을 `"대조됨"` 으로 접지 않는다** — 그러면 이 자가 고치려는 그 결함
    («안 본 것과 본 것의 출력이 같다»)을 자기 안에서 되풀이하는 것이다.
    """
    d = corpus_density(words, size_bytes)
    if d is None:
        return "모름", None
    return ("대조됨" if d >= MIN_WORDS_PER_MB else "못 봄"), d


def _h(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def ngram_hashes(words, n):
    return {_h(" ".join(words[i:i + n])) for i in range(len(words) - n + 1)}


def longest_span(words, sets):
    """교재와 연속으로 일치하는 최대 구간 `(길이, 시작 인덱스)`. 순수 함수 — 테스트가 직접 부른다.

    n-gram 이 이웃하면 그만큼 이어 붙는다: 인덱스가 연속인 묶음 길이 L 이면 L + n - 1 단어다.
    작은 n 에서 이미 긴 연속을 잡을 수 있으므로 모든 크기를 보고 최댓값을 쓴다.

    **시작 인덱스를 함께 돌려주는 이유**: 길이만으로는 '실제 차용'과 'mass flow rate 같은
    술어'를 가를 수 없다. 사람이 판정하려면 어느 말이 걸렸는지를 봐야 한다.
    """
    best, at = 0, 0
    for n in sorted(sets):
        if len(words) < n:
            continue
        book = sets[n]
        idx = [i for i in range(len(words) - n + 1)
               if _h(" ".join(words[i:i + n])) in book]
        if not idx:
            continue
        run = cur = 1
        start = head = idx[0]
        for a, b in zip(idx, idx[1:]):
            if b == a + 1:
                cur += 1
            else:
                cur, head = 1, b
            if cur > run:
                run, start = cur, head
        if run + n - 1 > best:
            best, at = run + n - 1, start
    return min(best, len(words)), at


def longest_run(words, sets):
    """교재와 연속으로 일치하는 최대 단어 수 (길이만)."""
    return longest_span(words, sets)[0]


# ★ 순회 범위 — 교재에서 옮겨질 수 있는 **문제 서술이 사는 모든 컬렉션** (2026-08-01 확장).
#
# 처음에는 `problems` 만 봤다. 그 상태로 "복제의심 0건"이라고 말할 수 있었지만,
# 그것은 *없다* 가 아니라 **거기까지는 없다** 였다(규칙 11). 실제로 `practice`(문풀) 의 prompt 도
# 같은 성격의 영문 문제 서술이고 같은 교재에서 왔다 — 검사 밖이라는 것 말고 다를 게 없었다.
# 검사를 만든 그 주에 범위를 안 넓히면, 다음에 이 사각지대를 발견하는 것은 사람의 눈이 된다.
PROMPT_COLLECTIONS = ("problems", "practice")


def iter_prompts(ch):
    """(id, prompt) — 검사 대상 서술 전부. 순수 함수(테스트가 범위를 직접 확인한다)."""
    for key in PROMPT_COLLECTIONS:
        for item in (ch.get(key) or []):
            yield str(item.get("id") or "?"), item.get("prompt")


def originality_issues(ch, sets, verdicts):
    """(errors, warnings). 순수 함수 — 파일을 읽지 않는다(테스트가 직접 부른다).

    sets 가 없으면(None) 아무 판정도 하지 않는다 — '지문이 없다'는 '깨끗하다'가 아니다.
    """
    errors, warnings = [], []
    if not sets:
        return errors, warnings
    # 판정 파일은 **과목 하나에 하나**라 다른 챕터의 항목도 들어 있다. 낡음 판정은
    # 반드시 *이 챕터의 문항*으로 좁혀야 한다 — 안 그러면 챕터마다 남의 항목을
    # '낡았다'고 신고한다(2026-08-01 첫 실행에서 경고 60여 건이 이 버그였다).
    mine = {pid for pid, _p in iter_prompts(ch)}
    seen = set()
    for pid, prompt in iter_prompts(ch):
        words = norm_words(prompt)
        run, at = longest_span(words, sets)
        span = " ".join(words[at:at + run])
        if run < NEAR_WORDS:
            continue
        seen.add(pid)
        if run >= COPY_WORDS:
            errors.append(
                pid + ": 교재 원문 복제 의심 — 연속 " + str(run) + "단어 일치 " + repr(span)
                + " → 소재·조건·묻는 것 중 최소 하나를 바꿔 다시 쓸 것 (규칙 12⑵⑷)."
                " 판정 기준을 낮추는 것은 검사 완화다")
            continue
        v = verdicts.get(pid)
        if not v:
            errors.append(
                pid + ": 부분 차용 미판정 — 연속 " + str(run) + "단어 일치 " + repr(span)
                + " → " + VERDICT_NAME + " 에 이 문항의 '구간'과 '근거'를 적을 것"
                " (관용구·술어면 그렇게 판정하고 근거를 남긴다. 판정 없이 통과시키지 않는다)")
        elif str(v.get("구간", "")) != span:
            errors.append(
                pid + ": 부분 차용 판정이 낡았다 — 기록된 구간은 " + repr(str(v.get("구간", "")))
                + " 인데 지금 걸린 말은 " + repr(span) + " 다. 문장이 바뀌었으니 다시 판정할 것")
        elif not str(v.get("근거", "")).strip():
            errors.append(pid + ": 부분 차용 판정에 근거가 비어 있다 — 왜 차용이 아닌지 한 줄로 적을 것")
    for pid in sorted((set(verdicts) & mine) - seen):
        warnings.append(pid + ": 부분 차용 판정이 남아 있지만 지금은 걸리지 않는다 — "
                        + VERDICT_NAME + " 에서 지울 것")
    return errors, warnings


# ── 파일 입출력 (위 순수 함수를 감싸는 얇은 층) ──────────────────────────────
def fingerprint_path(data_dir, chapter):
    return os.path.join(data_dir, FP_DIRNAME, os.path.splitext(chapter)[0] + ".json")


def load_sets(data_dir, chapter):
    """지문 n-gram 집합. 없으면 None — 호출자가 '건너뜀'으로 보고해야 한다."""
    path = fingerprint_path(data_dir, chapter)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {int(k): set(v) for k, v in data["ngrams"].items()}


def load_verdicts(data_dir):
    path = os.path.join(data_dir, VERDICT_NAME)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get("verdicts") or {}


def check_chapter_file(ch, ch_path):
    """(errors, warnings, skipped) — 빌드가 부르는 진입점."""
    if not any(True for _ in iter_prompts(ch)):
        return [], [], False        # 문제 서술이 없는 장(개요 등) — 검사할 것도 건너뛸 것도 없다
    data_dir = os.path.dirname(ch_path)
    sets = load_sets(data_dir, os.path.basename(ch_path))
    if sets is None:
        return [], [], True
    errors, warnings = originality_issues(ch, sets, load_verdicts(data_dir))
    return errors, warnings, False
