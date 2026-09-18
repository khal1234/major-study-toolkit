#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Stop 훅 — **턴이 끝날 때 「남은 것」을 스스로 낸다** (신설 2026-08-16).

    settings.json 의 Stop 훅으로 건다(이 리포의 자리):
        python "$CLAUDE_PROJECT_DIR/.claude/hooks/open_items.py"

## 왜 열렸나 — 사용자 지적 (전 프로젝트)

*[발화 생략]*

★ **묻는 시점이 정확히 반대다.** 도중에는 묻고(방해), 끝났을 때는 안 알린다(사람이 묻게 된다).

## ★ 규칙은 이미 있다 — 그래서 문서로는 못 고친다

`AGENTS.md` 실행 규율 8 은 배치 끝 보고의 최소 항목을 이미 못 박았다:
**⑴ 판정이 필요했던 것 ⑵ 확인하실 자리 ⑶ 남은 것.** 그런데 안 지켜진다.

**부작위는 관측이 안 되기 때문이다.** 도중에 «할까요»를 물으면 화면에 남지만,
끝나고 **안 알린 것**은 아무 흔적이 없다 — 사람이 물어봐야만 드러난다.
그래서 이 조항은 세는 자도 막는 자도 세울 수 없었다.

→ **자리를 바꾼다.** 「기억해서 적는다」를 「파일에서 읽어 낸다」로 옮기면 관측 가능해진다.

## ★ 트리거는 「반드시 하는 일」에 건다

이 계통이 정본으로 인정한 «반드시 하는 일»은 셋이다 — **턴마다 보고를 쓴다 · 커밋한다 ·
빌드를 돌린다**(`AGENTS.md`). 그중 **턴마다** 도는 자리가 `Stop` 훅이다
(종료 타이머를 «루프 회차 끝»에서 이리로 옮긴 선례가 있다).

## 무엇을 세나 — **인박스만 본다**

`받은것-인박스.md`·`review-inbox.md` 류에서 **열림**으로 표시된 항목. 지적 원장은 **안 본다** —
거기 「열림」은 *기계 방지가 아직 없다* 는 뜻이지 *사용자가 답을 기다린다* 는 뜻이 아니다.
둘을 섞으면 60줄이 매 턴 뜨고, 그러면 아무도 안 읽는다.

## 평소에는 한 글자도 안 낸다

열린 항목이 0이면 침묵한다(`cost_brief`·`shared_sync_check` 와 같은 규율).
**닫으면 사라지므로 스스로 꺼진다** — 남겨 두면 계속 보이는 것이 이 자의 값어치다.

☐ 못 보는 것: 사용자가 방금 말한 것을 **자가 인박스에 안 옮겼으면** 여기 안 잡힌다.
  그건 이 자가 아니라 «받은 것은 작업 전에 먼저 적는다» 규율이 답할 자리다.
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))


def _fallback_root(here=HERE):
    """`CLAUDE_PROJECT_DIR` 이 없을 때(손으로 돌릴 때) 훑을 뿌리.

    ★ 공용 폴더 판본은 훅 폴더의 부모(`공용 폴더/훅/..`)를 썼는데, 이 리포에서는 그 자리가
      `main/.claude` 라 **아무것도 못 찾고 조용히 0건**을 낸다 — 「꺼진 자」와
      「깨끗한 세션」이 겉모습이 같아지는 그 부류다(전공정리 이식 2026-08-25).
      그래서 `tools/`(또는 `도구/`)를 가진 **가장 가까운 조상**을 뿌리로 본다.
    """
    cur = here
    for _ in range(5):
        for name in ("tools", "도구"):
            if os.path.isdir(os.path.join(cur, name)):
                return cur
        nxt = os.path.dirname(cur)
        if nxt == cur:
            break
        cur = nxt
    return os.path.dirname(here)


ROOT = _fallback_root()
NAMES = re.compile(r"(인박스|inbox)", re.I)
OPEN = re.compile(r"\*\*상태:\s*열림\*\*|·\s*\*\*열림\*\*|\bOPEN\b")
CLOSED = re.compile(r"닫힘|CLOSED")
TITLE = re.compile(r"^#{1,4}\s*(.+?)\s*$")


def inbox_files(root):
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
        if base[len(root):].count(os.sep) > 2:
            dirs[:] = []
            continue
        for n in names:
            if n.endswith((".md", ".txt")) and NAMES.search(n):
                out.append(os.path.join(base, n))
    return sorted(out)


def open_items(text):
    """열린 항목의 제목들. 제목 줄에 표시가 있는 것만 센다."""
    out = []
    for line in text.splitlines():
        if line.startswith("|") and OPEN.search(line):
            # 표 행(공용 폴더 2026-09-11 이식) — 번호 · 요지만 낸다
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2:
                out.append(" ".join(f"{cells[0]} {cells[1]}".split())[:70])
            continue
        if not line.startswith("#"):
            continue
        if OPEN.search(line) and not CLOSED.search(line):
            m = TITLE.match(line)
            if m:
                t = re.sub(r"\*\*|`|·\s*상태:\s*열림|상태:\s*열림|·\s*열림", "", m.group(1))
                out.append(" ".join(t.split())[:70])
    return out


def main():
    root = os.environ.get("CLAUDE_PROJECT_DIR") or ROOT
    found = []
    for p in inbox_files(root):
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                items = open_items(fh.read())
        except OSError:
            continue
        for it in items:
            found.append((os.path.relpath(p, root), it))
    if not found:
        return 0                      # ★ 평소에는 **한 글자도 안 낸다**
    print("[남은 것] 인박스에 열린 항목 %d개 — **끝났으면 사람이 묻기 전에 내가 낸다**"
          % len(found))
    for where, it in found[:8]:
        print("  · %s   (%s)" % (it, where))
    if len(found) > 8:
        print("  … 외 %d개" % (len(found) - 8))
    return 0


if __name__ == "__main__":
    sys.exit(main())
