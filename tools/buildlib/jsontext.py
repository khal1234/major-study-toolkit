# -*- coding: utf-8 -*-
r"""챕터 JSON 을 **원본 표기 그대로** 다시 쓴다 — 바뀐 문자열 값만 갈아끼운다.

    from buildlib.jsontext import write_chapter
    status, why = write_chapter(ch_path, chapter, fixed)   # 'written'·'nochange'·'skipped'

**왜 이 모듈이 있는가 (열린 날 2026-08-02 — 공학수학 ch00·ch02, 고체역학 ch00).**

`fix_honorific` · `fix_notation_split` 은 파싱한 챕터를 `json.dumps(indent=2)` 로 **통째로**
다시 썼다. 그래서 두 도구 모두 쓰기 직전에 *"왕복이 원본과 같은가"* 를 물었고, 다르면
아무것도 쓰지 않았다. 거부 **자체는 옳다** — 표기 하나 고치자고 파일이 재포맷되면
변경점 하이라이트가 통째로 잡음이 되기 때문이다(AGENTS 「기준선」).

문제는 **거부가 곧 그 챕터를 규격 밖으로 영영 빼놓는다**는 것이다. 손으로 한 줄에 적은

    "relatedSections": ["sec-what-course"],
    { "text": "…", "equations": ["…"] },

같은 자리가 있으면 왕복이 어긋나고, 그 챕터는 이 도구도 앞으로 올 다른 json 도구도
건드릴 수 없다. 실측: 공학수학 ch02 는 말투 **337문장**이 도구로는 손댈 수 없는 상태였고
(ch00 은 14문장), 고체역학도 같은 벽에 부딪혀 **진단 메시지만** 붙였다.
즉 두 과목이 각각 걸린 부류인데 처방이 없었다.

★ **원인은 "빠뜨렸다" 가 아니라 선택지가 둘뿐이었던 것이다** — 재포맷하거나(하이라이트를
버린다) 포기하거나(규격을 버린다). 그래서 **셋째 길**을 둔다: 바뀐 문자열 값만 원문
텍스트에서 **JSON 리터럴 단위로** 갈아끼운다. 표기는 한 글자도 움직이지 않는다.

**안전장치는 마지막 한 줄이다** — 갈아끼운 본문을 *다시 파싱해 의도한 객체와 같은지* 본다.
치환이 어긋날 수 있는 경우(원문 이스케이프가 `json.dumps` 와 다르다 · 같은 값이 여러 곳에
있다 · 어떤 값이 다른 값의 부분문자열이다)를 이 한 줄이 한꺼번에 막는다.
**같지 않으면 쓰지 않는다** — 조용히 어긋난 파일을 남기는 것이 이 부류에서 가장 나쁘다.
"""
import json

__all__ = ["string_edits", "rewrite_text", "write_chapter"]


def string_edits(before, after, out=None):
    """두 구조를 나란히 훑어 `{옛 문자열: 새 문자열}` 을 모은다. 순수 함수.

    구조(키 집합·리스트 길이)나 문자열 아닌 값이 바뀌면 `ValueError` — 이 모듈은
    **문자열 값 치환만** 표기 보존으로 처리할 수 있고, 그 밖은 할 수 없다고 말해야 한다.
    """
    if out is None:
        out = {}
    if isinstance(before, dict) and isinstance(after, dict):
        if set(before) != set(after):
            raise ValueError("키 집합이 다르다 — 표기 보존으로는 못 쓴다")
        for key in before:
            string_edits(before[key], after[key], out)
    elif isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            raise ValueError("리스트 길이가 다르다 — 표기 보존으로는 못 쓴다")
        for b, a in zip(before, after):
            string_edits(b, a, out)
    elif isinstance(before, str) and isinstance(after, str):
        if before != after:
            if out.get(before, after) != after:
                raise ValueError("같은 값이 두 가지로 바뀐다: %r" % before[:40])
            out[before] = after
    elif type(before) is not type(after) or before != after:
        raise ValueError("문자열이 아닌 값이 바뀌었다: %r → %r" % (before, after))
    return out


def rewrite_text(original, before, after):
    """(새 본문, 사유). **사유가 있으면 쓰지 않는다.** 순수 함수 — 테스트가 직접 부른다."""
    try:
        parsed = json.loads(original)
    except json.JSONDecodeError as exc:
        return None, "원본 json 을 못 읽는다: %s" % exc
    if parsed != before:
        return None, "넘겨받은 객체가 파일 내용과 다르다 — 사이에 파일이 바뀌었다"
    try:
        edits = string_edits(before, after)
    except ValueError as exc:
        return None, str(exc)
    if not edits:
        return original, None
    text = original
    # 긴 값부터 갈아끼운다 — 짧은 값이 긴 값의 부분문자열일 때 안쪽부터 건드리지 않게.
    # (그래도 마지막 재파싱 검증이 최종 관문이다. 이 정렬은 오탐을 줄일 뿐이다.)
    for old in sorted(edits, key=len, reverse=True):
        literal_old = json.dumps(old, ensure_ascii=False)
        literal_new = json.dumps(edits[old], ensure_ascii=False)
        if literal_old not in text:
            return None, ("원문에서 못 찾은 값이 있다(이스케이프 표기가 다르다): %r"
                          % old[:40])
        text = text.replace(literal_old, literal_new)
    try:
        roundtrip = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, "갈아끼운 뒤 json 이 깨졌다: %s" % exc
    if roundtrip != after:
        return None, "갈아끼운 결과가 의도한 내용과 다르다"
    return text, None


def write_chapter(ch_path, before, after):
    """표기를 보존한 채 기록한다. ('written'·'nochange'·'skipped', 설명).

    `newline=""` 로 읽고 쓴다 — 줄바꿈까지 원본 그대로 둔다. 이 도구가 표기를 안 건드린다는
    약속에는 줄바꿈도 포함된다(CRLF 파일이 조용히 LF 로 바뀌면 diff 가 통째로 뜬다).
    """
    with open(ch_path, encoding="utf-8", newline="") as fh:
        original = fh.read()
    text, why = rewrite_text(original, before, after)
    if why:
        return "skipped", why
    if text == original:
        return "nochange", ""
    with open(ch_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return "written", ""
