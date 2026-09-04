#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""세션 기록에서 **앞에서 기다린 긴 도구 호출**을 센다 (읽기 전용, 신설 2026-08-21).

    python tools/audit_serial_waits.py [--sessions=N] [--min=60] [--project=조각]

## 왜 열렸나 — 사용자 지적 (전 프로젝트)

*"병렬로 돌리는 게 나은데 자꾸 백그라운드 1~2개로만 하거나 본인이 직접 작업하더라.
백그라운드 병렬로 한번에 하면 시간 단축될 텐데 **그거 판정하는 자가 없는 건가?**"*

**반쪽만 있었다.** `audit_tool_parallelism` 은 «한 응답에 몇 개를 묶었나»(묶음률)를 재는데,
그건 **초 단위 호출**의 왕복 낭비를 보는 자다. **분 단위 호출을 앞에서 기다렸는가**는
아무도 안 셌다 — 34분짜리를 포그라운드로 돌리면 그 시간 동안 다른 항목이 전부 멈춘다.

## 무엇을 재나

각 도구 호출의 소요 = 결과 기록 시각 − 호출 기록 시각. `--min`(기본 60초) 이상이면
**긴 호출**로 세고, 세션당 «긴 호출 수 · 합계 분 · 상위 명령»을 낸다.

## ★ 판정이 아니라 셈이다 — 목표 숫자로 쓰지 말 것

「전부 백그라운드로」가 답이 아니다: **다음 행동이 그 결과에 걸려 있으면** 기다리는 것이
맞다(묶음률의 *"의존까지 묶으면 틀린 일을 빠르게 한다"* 와 같은 규율). 이 자는
**후보 목록**을 낼 뿐이고 «독립이었나»는 사람이 명령을 보고 판정한다.
★ 백그라운드 호출 자체는 즉시 반환이라 여기 **안 잡힌다** — 잡힌 것은 전부 «기다린» 것이다.

판정선(사람용): **⑴ 1분 넘게 걸리고**(`runtime_note` 기록이 미리 말해 준다)
**⑵ 다음 행동이 그 결과를 안 쓰면** → 백그라운드로 돌리고 그 사이 다른 항목을 진행한다.
"""
import io
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJ = Path.home() / ".claude" / "projects"


def ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def measure(path, min_sec):
    calls = {}          # tool_use id → (시각, 명령 조각)
    waits = []          # (초, 명령 조각)
    for ln in io.open(path, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(ln)
        except Exception:
            continue
        t = ts(d.get("timestamp", ""))
        if t is None:
            continue
        msg = d.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict):
                continue
            if d.get("type") == "assistant" and c.get("type") == "tool_use":
                # 사람을 기다린 것은 도구 대기가 아니다 — 고칠 수 있는 대상만 센다
                if c.get("name") in ("AskUserQuestion", "ExitPlanMode"):
                    continue
                inp = c.get("input") or {}
                cmd = str(inp.get("command") or inp.get("script")
                          or c.get("name") or "")[:60]
                calls[c.get("id")] = (t, " ".join(cmd.split()))
            elif d.get("type") == "user" and c.get("type") == "tool_result":
                got = calls.pop(c.get("tool_use_id"), None)
                if got and t - got[0] >= min_sec:
                    waits.append((t - got[0], got[1]))
    return sorted(waits, reverse=True)


def main():
    n, min_sec, only = 5, 60, None
    for a in sys.argv[1:]:
        if a.startswith("--sessions="):
            n = int(a.split("=", 1)[1])
        elif a.startswith("--min="):
            min_sec = int(a.split("=", 1)[1])
        elif a.startswith("--project="):
            only = a.split("=", 1)[1]
    files = sorted(PROJ.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime,
                   reverse=True)
    if only:
        files = [f for f in files if only in f.parent.name]
    print("[앞에서 기다린 긴 호출] 최근 %d세션 · 하한 %d초 — **셈이지 판정이 아니다**"
          % (n, min_sec))
    for f in files[:n]:
        waits = measure(f, min_sec)
        proj = re.sub(r"^C--Users-Administrator-", "", f.parent.name)[-24:]
        if not waits:
            print("  %-26s 없음" % proj)
            continue
        total = sum(w for w, _ in waits)
        print("  %-26s %d건 · 합계 %.0f분" % (proj, len(waits), total / 60))
        for w, cmd in waits[:3]:
            print("      %5.1f분  %s" % (w / 60, cmd))
    print("  ※ «독립이었나» 는 사람이 명령을 보고 판정한다 — 의존을 백그라운드로 밀면"
          " 틀린 일을 빠르게 한다")
    return 0


if __name__ == "__main__":
    main()
