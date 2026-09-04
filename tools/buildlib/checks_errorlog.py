# -*- coding: utf-8 -*-
"""오답로그(`error_log.json`)의 정합성 검사.

**왜 만들었나 (열린 날 2026-08-01, 사용자 지적).**
사용자가 종이 풀이를 들고 물었다 — *"잠만 Cengel 내가 푼 게 안 남아있다고? 2장 풀어본 흔적이
나 종이 가지고 있는데 채점 받았던 것도 기억나고."* git 전체 이력을 봐도 ch02 항목은 한 번도
들어온 적이 없었다. 그런데 **그것이 '채점을 안 했다'는 뜻은 아니다** — `entries` 는 오답만
남기기 때문이다(16건 전부 wrong/partial, right 는 0건). 즉 파일에서
**'안 했다'와 '했는데 걸린 게 없다'가 똑같이 0건으로 보인다.**

그래서 `sessions`(채점했다는 사실 자체)를 도입했고, 이 검사가 그것을 **비어 있게 두지 못하게** 한다.
사용자 요청: *"허.. 3장부터는 남게 해줘"* (2026-08-01 승인 — `error_log.json` 은 빨강이라
사용자 승인 없이는 손대지 않는다).

**이 파일이 생기기 전까지 오답로그를 읽는 도구는 0개였다.** 빌드는 pitfall 의 출처가
`"오답로그 e"` 로 *시작하는지*만 보고 그 항목이 실재하는지는 보지 않았다 — 그래서
없는 번호를 인용해도 통과했다. 그 사각지대도 여기서 함께 닫는다.
"""
import json
import os

ERRORLOG_NAME = "error_log.json"
SESSION_REQUIRED = ("id", "date", "chapter", "scope", "graded", "logged", "entryIds")


def load_errorlog(data_dir):
    """오답로그. 없으면 None — 과목마다 있는 파일이 아니다(있는 과목만 검사한다)."""
    path = os.path.join(data_dir, ERRORLOG_NAME)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def errorlog_issues(log):
    """(errors, warnings). 순수 함수 — 테스트가 직접 부른다."""
    errors, warnings = [], []
    if not log:
        return errors, warnings
    entries = log.get("entries") or []
    sessions = log.get("sessions")
    if sessions is None:
        errors.append("error_log.json: 'sessions' 배열이 없다 — 채점했다는 사실을 남길 곳이 없으면"
                      " '안 했다'와 '했는데 오답이 없었다'를 구별할 수 없다 (2026-08-01 신설)")
        return errors, warnings

    ids = [str(e.get("id") or "") for e in entries]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errors.append("error_log.json: entry id 중복 — " + ", ".join(dup))

    claimed = {}
    for s in sessions:
        sid = str(s.get("id") or "?")
        missing = [k for k in SESSION_REQUIRED if k not in s]
        if missing:
            errors.append("error_log.json " + sid + ": 세션 필수 항목 누락 — " + ", ".join(missing))
            continue
        # graded 를 모른 채 남길 수 있는 것은 사후 복원뿐이다. 새 채점은 반드시 센다.
        if s.get("graded") is None and not s.get("reconstructed"):
            errors.append("error_log.json " + sid + ": graded 가 null 인데 reconstructed 가 아니다 —"
                          " 채점한 문항 수를 세서 적을 것 (0건 오답이어도 '몇 개를 봤는가'가 기록의 핵심이다)")
        # 사후 복원은 **무엇을 근거로 되살렸는지**가 함께 있어야 한다. 남은 entry 의 날짜에서
        # 되살린 것과 사용자 기억뿐인 것은 신뢰도가 다른데, 표시가 없으면 구별되지 않는다(규칙 11).
        if s.get("reconstructed") and s.get("basis") not in ("entry-dates", "user-recall"):
            errors.append("error_log.json " + sid + ": reconstructed 인데 basis 가 없다 —"
                          " 'entry-dates'(entry 날짜에서 되살림) 또는 'user-recall'(사용자 기억뿐) 중 하나를 적을 것")
        eids = list(s.get("entryIds") or [])
        if len(eids) != (s.get("logged") if isinstance(s.get("logged"), int) else -1):
            errors.append("error_log.json " + sid + ": logged(" + repr(s.get("logged"))
                          + ")와 entryIds 개수(" + str(len(eids)) + ")가 다르다")
        for eid in eids:
            if eid in claimed:
                errors.append("error_log.json: " + eid + " 를 두 세션이 가진다 — "
                              + claimed[eid] + ", " + sid)
            claimed[eid] = sid
            if eid not in ids:
                errors.append("error_log.json " + sid + ": 없는 entry 를 가리킨다 — " + eid)

    orphan = [i for i in ids if i and i not in claimed]
    if orphan:
        errors.append("error_log.json: 어느 세션에도 속하지 않은 entry — " + ", ".join(orphan)
                      + " → 그 채점이 언제 어느 범위였는지 sessions 에 남길 것")
    return errors, warnings


def pitfall_entry_reference_issues(ch, log):
    """pitfall 이 인용한 `오답로그 eNNN` 이 실제로 있는가. 순수 함수.

    빌드는 접두어만 봤다 — 없는 번호를 인용해도 통과했다(2026-08-01 실측: 검사 0개).
    """
    out = []
    if not log:
        return out
    ids = {str(e.get("id") or "") for e in (log.get("entries") or [])}
    owners = list((ch.get("theory") or {}).get("sections") or [])
    owners += list((ch.get("derivation") or {}).get("formulas") or [])
    for owner in owners:
        for p in (owner.get("pitfalls") or []):
            src = str(p.get("source") or "")
            if not src.startswith("오답로그 "):
                continue
            parts = src.split()
            eid = parts[1] if len(parts) > 1 else ""
            if eid not in ids:
                out.append("pitfall " + str(p.get("id") or "?") + ": 없는 오답로그를 인용한다 — "
                           + repr(src))
    return out
