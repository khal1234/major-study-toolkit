#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stop 훅 — 공용 시스템(공용 폴더) 변경 알림이 이번 세션에서 「가져왔다/안 가져왔다」로
처리됐다고 채팅에 남았는지 확인한다 (신설 2026-09-01).

    settings.json 의 Stop 훅으로 건다:
        python "$CLAUDE_PROJECT_DIR/훅/sync_disposition_due.py"

## 왜 열렸나

`shared_sync_check.py`는 SessionStart에 「공용이 바뀌었다」를 한 줄만 알리고 끝이다.
그 알림을 본 세션이 판정을 하고도 채팅에 남기지 않으면, 사용자는 **누락된 건지
의도적으로 스킵한 건지 구별할 수 없다**(2026-09-01 사용자: *[발화 생략]*).

## 판정선

⑴ 지금 공용과 lock 사이에 diff(added/changed)가 있는가 — `shared_sync_check`와
   **같은 함수**(`fingerprint`·`load_lock`·`diff`)를 그대로 가져다 쓴다(재사용 —
   판정이 둘로 갈리면 서로 다른 답을 낸다, `reuse-before-rebuild` 규율).
⑵ 이 세션의 assistant 발화 중 **처리 결과를 밝힌 문장**(가져옴/가져왔다/반영·
   보류/스킵/안 가져왔다 계열 키워드)이 하나라도 있는가.

⑴이 참이고 ⑵가 거짓이면 한 줄 귀띔한다. ⑵가 한 번 참이 되면 그 세션 동안은
다시 안 뜬다(같은 사실을 반복 알리면 소음이 된다 — `ask_due`·`narration_due`와
같은 규율).

☐ 못 보는 것
- **글자만 본다.** "가져왔다"류 낱말이 다른 맥락(예: 사용자가 먼저 물어본 것을
  그대로 인용)에 쓰여도 해소로 오판할 수 있다.
- **`--accept` 호출 여부와는 무관하다.** lock을 실제로 밀지 않아도 disposition
  문장만 있으면 조용해진다 — 이 훅은 "말했는가"만 보지 "실제로 반영했는가"는
  `shared_sync_check --list`가 여전히 사람 몫이다.
- **여러 미러 알림이 겹치면 하나로 뭉뚱그려 본다.** 알림이 두 번 떴어도 disposition
  문장 하나면 둘 다 처리됐다고 본다 — 세분화하려면 각 항목을 이름으로 짚어야 하는데
  그건 사람이 채팅에서 이미 하는 일이다.
"""
import os
import re
import sys

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_root(start):
    """프로젝트 뿌리를 찾는다 — **훅이 사는 깊이가 프로젝트마다 다르다**
    (2026-09-01 실측: 공용 폴더는 `<뿌리>/훅/`, 전공정리·잡탕용·knu-bot·토익·XSanity는
    `<뿌리>/.claude/hooks/`나 `<뿌리>/_modding/scripts/`처럼 두 단 이상 깊다).
    `dirname()`을 고정 횟수로 부르면 얕은 리포에서만 맞는다 — 대신 `.git`이나
    `CLAUDE.md`가 있는 조상 폴더를 찾아 올라간다(최대 5단, 못 찾으면 두 단 위로 폴백).
    """
    p = start
    for _ in range(5):
        if os.path.exists(os.path.join(p, ".git")) or os.path.isfile(os.path.join(p, "CLAUDE.md")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return os.path.dirname(os.path.dirname(start))          # 폴백 — 옛 가정(두 단)


ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or _find_root(HOOKS_DIR)

# ★ `check_narration.py`가 사는 자리도 프로젝트마다 다르다 — 공용 폴더는 `도구/`,
#   전공정리는 `tools/`, XSanity는 `_modding/scripts/`, 잡탕용·knu-bot·토익은
#   훅과 **같은 폴더**(`.claude/hooks/`). 후보를 전부 시도한다 — 없는 경로는 건너뛴다.
for _cand in ("도구", "tools", os.path.join("_modding", "scripts")):
    _d = os.path.join(ROOT, _cand)
    if os.path.isdir(_d):
        sys.path.insert(0, _d)
sys.path.insert(0, HOOKS_DIR)

try:
    from check_narration import records, latest_session, repo_root
except ImportError:
    def main():
        return 0
else:
    try:
        import shared_sync_check as ssc
    except ImportError:
        def main():
            return 0
    else:
        DISPOSITION_RE = re.compile(
            r"가져왔|가져옴|반영했|반영함|안\s*가져|안가져|보류|스킵|건너뛰|미룸"
        )

        def _assistant_text(rec):
            if rec.get("type") != "assistant":
                return ""
            c = (rec.get("message") or {}).get("content")
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return "\n".join(b.get("text", "") for b in c
                                 if isinstance(b, dict) and b.get("type") == "text")
            return ""

        def disposition_stated(recs):
            return any(DISPOSITION_RE.search(_assistant_text(r)) for r in recs)

        def main():
            try:
                now = ssc.fingerprint(ssc.SHARED)
                if not now or not ssc.LOCK.is_file():
                    return 0
                added, changed, _gone = ssc.diff(now, ssc.load_lock())
                if not (added or changed):
                    return 0
                root = repo_root()
                p = latest_session(root)
                if not p or not p.exists():
                    return 0
                recs = list(records(p))
                if disposition_stated(recs):
                    return 0
            except Exception:                       # noqa: BLE001 — 절대 세션을 막지 않는다
                return 0

            print("[공용 시스템] 이번 세션에 공용 폴더 변경 알림이 떴는데 아직 "
                  "「가져왔다」/「안 가져왔다(사유)」가 채팅에 안 남았다 — "
                  "이번 응답 끝에 한 줄 남길 것")
            return 0


def selftest():
    bad = 0

    def chk(desc, cond):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %s" % ("OK  " if cond else "**틀림**", desc))

    chk("음성 — diff 없는데 assistant 발화 없어도 disposition_stated 는 문제 삼지 않는다"
        "(호출부에서 diff 먼저 본다)", True)
    positive = [{"type": "assistant",
                "message": {"content": [{"type": "text", "text": "공용 폴더 변경 가져왔습니다"}]}}]
    negative = [{"type": "assistant",
                "message": {"content": [{"type": "text", "text": "다른 얘기만 했습니다"}]}}]
    mixed_role = [{"type": "user",
                  "message": {"content": "가져왔다고 사용자가 먼저 말한 경우"}}]
    chk("양성 — assistant 가 「가져왔습니다」라고 하면 처리로 본다",
        disposition_stated(positive))
    chk("음성 — 관련 낱말이 없으면 처리로 안 본다", not disposition_stated(negative))
    chk("음성 — user 발화의 낱말은 안 센다(assistant 만 본다)",
        not disposition_stated(mixed_role))
    skip_variant = [{"type": "assistant",
                     "message": {"content": [{"type": "text",
                                              "text": "이번엔 스킵했습니다 — 사유는 …"}]}}]
    chk("양성 — 「스킵했다」류도 처리(안 가져오기로 판정)로 본다",
        disposition_stated(skip_variant))

    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    sys.exit(main())
