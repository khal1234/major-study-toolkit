# -*- coding: utf-8 -*-
"""**지난 세션에서 답을 못 받고 끝난 사용자 발화**를 세션 시작에 한 줄 알린다 (신설 2026-08-17).

    settings.json 의 SessionStart 훅으로 건다:
        python tools/audit_dropped_input.py
    사람이 볼 때:  python tools/audit_dropped_input.py --status [--all]
    자기 점검:     python tools/audit_dropped_input.py --selftest

## 왜 열렸나

공용 폴더 `/insights` 154세션이 잡은 원장 2026-08-16 행 — **주간 한도로 사용자 피드백 ~15건이
통째로 죽었다.** 처방은 *[발화 생략]* 였는데 그건
**습관이라 기계가 안 막는다**(규칙 7⑷ — 성실성에 기댄 방지장치). 사용자 판정 2026-08-17:
*[발화 생략]* → **아니다. 그건 사용자가 질
몫이 아니다**(실행 규율 1: *[발화 생략]*). 그래서 사용자 쪽을 안 바꾸고 이쪽에 자를 세운다.

## ★★ 새 수집기가 아니라 「읽는 자」다

**사용자 발화는 이미 전부 남아 있다** — 세션 기록(`~/.claude/projects/**/*.jsonl`)이 그것이고,
`audit_session_cost`·`check_narration`·`/insights` 가 전부 그 파일을 읽어서 돈다.
즉 잃은 것은 «기록» 이 아니라 **«다음 세션이 그것을 안 읽는 것»** 이다.
자료를 또 모으면 두 벌이 되고, 이 저장소는 두 벌이 갈리는 것을 반복해 겪었다.

## ★ 판정선은 하나 — 「말했는데 그 뒤에 답이 없다」

*[발화 생략]* 는 **묻지 않는다.** 그건 판단형이라 실행 규율 17 이 금지하고, 공용 폴더도 같은
이유로 «기계로는 못 막는다» 고 적었다. 대신 **관측 가능한 것 하나**만 본다 —
어시스턴트 발화(글이든 도구 호출이든)가 **하나도 뒤따르지 않은 사용자 발화.**
그것이 «턴이 중간에 죽었다» 의 관측 가능한 형태다. 무엇인지는 **사람이 읽고 판정한다.**

## ★ 스스로 꺼진다 — 상태 파일이 없다

가장 새 세션 하나만 본다. 그 세션이 제대로 끝났으면 침묵하므로, 옮겨 적고 나면 다음 세션엔
안 뜬다. 「봤다」를 적는 대장을 따로 두지 않는 이유다(대장이 늘면 그 대장도 낡는다).

## 못 보는 것 (정직하게 남긴다)

- **두 세션 전에 끊긴 것은 안 본다.** 가장 새 것 하나만 보기 때문이다. 넓히면 이미 처리한
  것을 계속 다시 띄우게 되고(상태가 필요해지고), 그 소음이 곧 이 알림을 죽인다.
- **하네스 봉투를 `<` 로 시작하는지로 거른다**(`<system-reminder>`·`<command-name>`…).
  사용자가 `<` 로 시작하는 말을 하면 놓친다 — 한 방향으로만 약하다(놓칠 뿐 지어내지 않는다).
- **말한 것이 실제로 처리됐는지는 안 본다.** 답이 있었으면 통과시킨다 — 답하고 안 한 것은
  `audit_session_conduct` 의 「예고하고 안 한 것」이 세는 자리다(두 벌로 만들지 않는다).
"""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 고른 값 — 화면에 붙일 조각의 길이·개수. 전문은 세션 기록에 그대로 있으므로 여기서는
# **알아볼 수 있을 만큼**이면 된다(사람이 «아 그거» 하면 그 줄은 제 일을 다 한 것이다).
# 늘리면 세션 시작에 실리는 양이 늘어 `cost_brief`·`shared_sync_check` 의 규율과 어긋난다.
SNIPPET = 160
# 고른 값 — 화면에 붙일 개수. 한 턴이 죽어서 남는 발화는 실측상 한둘이고, 이보다 많으면
# **세션 시작 알림이 아니라 목록**이 된다. 넘치면 개수를 말하고 `--all` 로 문을 연다.
MAX_SHOWN = 5


def user_text(content):
    """사용자가 **친** 글. 도구 결과·하네스 봉투는 발화가 아니다."""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_result":
                return ""              # 도구 결과가 섞인 줄은 통째로 발화가 아니다
            if block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        text = "\n".join(parts)
    else:
        return ""
    text = text.strip()
    if not text or text.startswith("<"):
        return ""                      # 하네스 봉투 — 사람이 친 것이 아니다
    return text


def answered(content):
    """어시스턴트가 **무언가 했나** — 글이든 도구 호출이든."""
    if not isinstance(content, list):
        return bool(content)
    return any(isinstance(b, dict) and b.get("type") in ("text", "tool_use")
               for b in content)


def classify(rec):
    """`("user", 사용자가 친 글)` · `("assistant", 무언가 했나)` · `(None, None)`.

    ★★ **읽는 자를 하나로 둔다** (2026-08-17, 이 자를 짓자마자 밟았다). 첫 판은 `dropped()`
      만 `role` 을 보고 `--status` 의 세는 줄은 **안 봐서, 내 발화 14건을 「사용자 발화」로
      셌다**(실측 20건 중 14). 숫자만 틀린 것이 아니라 **재는 자와 도는 자가 다른 것을 본
      것**이고, 오늘 `gate_rerun_guard` 에서 고친 것과 **같은 부류**다.
      → 두 자리가 이 함수 하나만 부른다. 조건을 두 곳에 적으면 반드시 갈라진다.
    """
    if rec.get("isMeta"):
        return None, None
    msg = rec.get("message") or {}
    role = msg.get("role") or rec.get("type")
    content = msg.get("content")
    if role == "assistant":
        return "assistant", answered(content)
    if role == "user":
        return "user", user_text(content)
    return None, None


def utterances(records):
    """사용자가 친 글만 순서대로. `classify` 하나에 기댄다."""
    out = []
    for rec in records:
        role, value = classify(rec)
        if role == "user" and value:
            out.append(value)
    return out


def dropped(records):
    """마지막 어시스턴트 응답 **뒤에 남은** 사용자 발화들. 순수 함수 — 테스트가 직접 부른다.

    ★ 판정은 전부 여기 둔다(`main()` 에 쓰면 잠금장치가 못 본다) — `guard_bash.deny_reason`
      과 같은 규율이다.
    """
    tail = []
    for rec in records:
        role, value = classify(rec)
        if role == "assistant":
            if value:
                tail = []              # 응답이 왔다 — 앞의 것은 다 받은 것이다
        elif role == "user" and value:
            tail.append(value)
    return tail


def key(cwd):
    """`audit_session_cost.real_name` 과 같은 꼴 — 경로 뒤 두 조각."""
    parts = [p.rstrip(":\\/") for p in Path(cwd).parts if p.strip(":\\/")]
    return "/".join(parts[-2:]) if len(parts) > 1 else str(cwd)


# 고른 값 — **묻는 자리**(`--status`·`--all`)가 훑는 세션 수. 알리는 자리는 그대로 1개다.
# 근거: `/clear` 는 새 세션 파일을 만들 수 있어서, 끊긴 말이 든 파일이 **가장 새 것이 아니게**
# 된다(2026-08-17 사용자 한도 실측을 준비하며 드러난 자리). 3은 [발화 생략]
# 을 덮는 최소치다. 사람이 부르는 자리라 소음이 문제가 안 되고, 그래서 알리는 자리는 안 넓힌다.
LOOKBACK = 3


def recent_sessions(project_key, limit=1):
    """이 프로젝트의 **새 것부터** 세션 파일들. 없으면 빈 목록.

    ★ 프로젝트를 폴더가 아니라 기록 안의 `cwd` 로 가른다 — 그 판정은 `audit_session_cost`
      가 정본이고 여기서 다시 짜지 않는다(한글 경로가 같은 슬러그로 뭉개져 두 프로젝트가
      한 폴더를 쓰는 실사고가 있었다).
    ★★ **알리는 자리는 `limit=1`, 묻는 자리는 `LOOKBACK`.** 넓힌 채로 알리면 이미 처리한
      옛 세션의 꼬리를 **영원히 다시 띄운다**(상태 파일이 없으니 꺼질 길이 없다) — 그래서
      *스스로 꺼진다* 는 성질을 지키려고 두 자리를 갈랐다.
    """
    try:
        from audit_session_cost import sessions_by_project
        groups = sessions_by_project(limit)
    except Exception:
        return []
    return list(groups.get(project_key) or [])


def newest_session(project_key):
    """알리는 자리가 쓰는 것 — 가장 새 세션 파일 하나. 없으면 `None`."""
    files = recent_sessions(project_key, 1)
    return files[0] if files else None


def load(path):
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return out


def status(argv):
    """**침묵이 「없다」인지 「못 읽었다」인지 가른다.** 사람이 부르는 자리다.

    ★★ 왜 있나 (2026-08-17, 이 자를 짓자마자): 첫 실행이 **침묵**이었는데 그것이 «답 못 받은
      말이 없다» 인지 «세션 파일을 못 찾았다» 인지 **출력이 같았다.** 규칙 11 이 못 박은
      *[발화 생략]* 이고, 이 세션이 하루 종일 잡은
      「빈손 초록」과 같은 모양이다. 평소 침묵은 그대로 두고 **묻는 자리를 따로 연다.**
    ★ 그리고 이 자리가 곧바로 값을 했다 — 첫 `--status` 가 **20건**을 내서 세어 보니
      14건이 내 발화였다(`classify` 독스트링).
    """
    k = key(os.getcwd())
    print("[답 못 받은 말 — 자를 잰다] %s" % k)
    paths = recent_sessions(k, LOOKBACK)
    if not paths:
        print("  ✘ **세션 기록을 못 찾았다** — 이 자는 아무것도 못 본다")
        print("      `python tools/audit_session_cost.py --all` 로 프로젝트 이름을 확인할 것")
        return 1
    total = 0
    for i, path in enumerate(paths):
        records = load(path)
        said = utterances(records)
        tail = dropped(records)
        total += len(tail)
        print("  %s %s — 레코드 %d줄 · 발화 %d건 · **답 못 받은 말 %d건**%s"
              % ("·" if tail else "✔", os.path.basename(str(path)),
                 len(records), len(said), len(tail),
                 "  ← 가장 새 것" if i == 0 else ""))
        if not records:
            print("      ? **0줄이다** — 지금 막 시작한 세션이면 정상이고, 아니면 못 읽은 것이다")
        if "--all" in argv:
            for t in tail:
                print("      | %s" % " ".join(t.split())[:100])
    print("  ※ 알리는 자리는 **가장 새 것 하나**만 본다 — 여기서만 %d개를 훑는다"
          % len(paths))
    print("  ※ 합계 %d건" % total)
    return 0


def main(argv):
    if "--status" in argv:
        return status(argv)
    path = newest_session(key(os.getcwd()))
    if not path:
        return 0                       # 기록이 없는 환경에서는 조용히 아무것도 안 한다
    tail = dropped(load(path))
    if not tail:
        return 0                       # ★ 평소에는 **한 글자도 안 낸다**
    show = tail if "--all" in argv else tail[-MAX_SHOWN:]
    print("[지난 세션] 답을 못 받고 끝난 말이 %d건 있다 — **먼저 인박스로 옮긴다**"
          % len(tail))
    for text in show:
        one = " ".join(text.split())
        print("  · %s%s" % (one[:SNIPPET], "…" if len(one) > SNIPPET else ""))
    if len(show) < len(tail):
        print("  · … 그 밖 %d건 (`--all` 로 전부)" % (len(tail) - len(show)))
    print("  ※ 무엇인지는 **사람이 판정한다** — 이 자는 «답이 없었다» 만 본다."
          " 전문은 세션 기록에 그대로 있다")
    return 0


def _u(text):
    return {"message": {"role": "user", "content": text}}


def _a(*blocks):
    return {"message": {"role": "assistant", "content": [dict(b) for b in blocks]}}


def selftest():
    ok = True
    T = {"type": "text", "text": "답"}
    U = {"type": "tool_use", "name": "Bash", "input": {}}
    cases = [
        ("답을 받은 말은 안 남는다", [_u("고쳐줘"), _a(T)], []),
        ("도구만 돌아도 답으로 친다", [_u("고쳐줘"), _a(U)], []),
        ("답 없이 끝난 말이 남는다", [_u("고쳐줘")], ["고쳐줘"]),
        ("마지막 응답 뒤의 것만 남는다",
         [_u("첫째"), _a(T), _u("둘째"), _u("셋째")], ["둘째", "셋째"]),
        ("빈 응답은 응답이 아니다", [_u("고쳐줘"), _a()], ["고쳐줘"]),
        # ★ 도구 결과는 role=user 로 오지만 **사용자 발화가 아니다**
        ("도구 결과는 발화가 아니다",
         [_u("고쳐줘"), _a(U),
          {"message": {"role": "user",
                       "content": [{"type": "tool_result", "content": "ok"}]}}], []),
        ("system-reminder 는 발화가 아니다",
         [_a(T), _u("<system-reminder>훅 출력</system-reminder>")], []),
        ("isMeta 줄은 안 본다", [_a(T), dict(_u("메타"), isMeta=True)], []),
        ("블록 목록으로 온 발화도 읽는다",
         [_a(T), {"message": {"role": "user",
                              "content": [{"type": "text", "text": "블록 발화"}]}}],
         ["블록 발화"]),
    ]
    for why, records, want in cases:
        got = dropped(records)
        bad = got != want
        ok = ok and not bad
        print("%s %-32s %s" % ("✘" if bad else "✔", why, got))

    # ★★ **재는 자와 도는 자가 같은 것을 보나** — 실사고를 그대로 잠근다(2026-08-17).
    #   `--status` 만 role 을 안 봐서 어시스턴트 글 14건을 사용자 발화로 셌다.
    mixed = [_u("사람이 친 말"), _a(T), _a(U),
             {"message": {"role": "user",
                          "content": [{"type": "tool_result", "content": "ok"}]}}]
    got = utterances(mixed)
    bad = got != ["사람이 친 말"]
    ok = ok and not bad
    print("%s %-32s %s" % ("✘" if bad else "✔",
                           "어시스턴트 글은 발화로 안 센다", got))

    print("\n%s" % ("OK   0 problem(s)." if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main(sys.argv))
