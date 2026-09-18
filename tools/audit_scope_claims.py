# -*- coding: utf-8 -*-
"""**「전수」라 쓰고 부분만 했나** — 범위 주장에 그 범위를 낸 명령이 붙어 있나.

    python 도구/audit_scope_claims.py            # 판정 (근거 없는 주장이 있으면 exit 1)
    python 도구/audit_scope_claims.py --selftest # 대조군으로 자를 먼저 잰다
    python 도구/audit_scope_claims.py --quiet

왜 이 자가 필요한가 (2026-08-25, 24시간에 두 번)
------------------------------------------------
  · XSanity 가 관측 6칸으로 62칸에 「확정」을 찍은 것을 **잡고 나서**, 처방으로
    **3채널만** 재판독하겠다고 냈다. 8월 14일 작업이 그 셋만이 아닌데 「전수」라고 썼다.
  · 내가 unlazy 를 보고 *[발화 생략]* 고 답했다. **아무 명령도 안 돌린 채**였고,
    그날 밤 그 항목들이 전부 반쪽으로 드러났다.

unlazy 가 말한 두 실패 중 **두 번째**다 — *어려운 부분을 조용히 빼고 요약엔 안 적는다.*
첫 번째(「다 했다고 보고」)는 `audit_stamps` 가 자료 쪽에서 잡는데, 이쪽은 **말** 쪽이라
아무 자도 안 봤다.

판정선 — **주장 하나에 명령 하나**
----------------------------------
범위를 주장하는 말(`전수` · `전부` · `모두` · `전 챕터` · `모든 …`)이 나오면,
**그 응답이 도구를 부른 응답이어야 한다.** 안 불렀으면 그 수는 어디서 왔는지가 없다.

    막는 선: 근거 없는 범위 주장 **1건이라도 있으면 exit 1.**

★ 「도구를 불렀나」로 잡는 이유는 **셀 수 있어서**다(규율 17). *[발화 생략]* 는
  판단형이라 물으면 언제나 «충분하다» 가 나온다 — 이 폴더가 「진행 중계」에서 겪은 그것이다.

☐ 못 보는 것 — 적어 두는 것이 이 자의 절반이다
-----------------------------------------------
- **명령을 불렀다고 그 명령이 그 범위를 낸 것은 아니다.** 엉뚱한 것을 돌리고 「전수」라
  써도 통과한다. 이 자가 보증하는 것은 «맨손으로 주장하지 않았다» 하나다.
- **인용·계획은 주장이 아니다.** *[발화 생략]* 는 앞으로의 말이라 뺀다(어미로 가른다).
- 사용자 발화는 안 센다. 범위를 요구하는 것은 사용자의 자유다.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# 범위를 **다 덮었다**고 말하는 표현. 「일부」·「중 N건」 같은 한정어는 아래에서 뺀다.
SCOPE = re.compile(r"(전수|전부|모두|전\s*챕터|전\s*과목|전\s*프로젝트|모든\s+\S+|빠짐없이|남김없이)")
# ★★ **범위 낱말만으로는 주장이 아니다** (2026-08-25, 첫 판이 45건 중 37건을 잘못 잡았다).
#   한국어에서 「전부·모두」는 부사로 흔히 쓴다 — *[발화 생략]* ·
#   *[발화 생략]* 는 **서술**이지 «내가 다 했다» 가 아니다. 첫 판은 그것을
#   전부 세어 **자가 소음이 됐다**(소음은 검사기를 죽인다).
#   → **내가 한 일의 완료**를 말하는 자리에서만 센다. 범위 낱말 **과** 완료 동사가 같은
#     절에 있어야 한다. 이 좁힘의 대가는 「했다」를 안 붙인 주장을 놓치는 것이고,
#     **가드는 모를 때 통과시킨다**(놓치는 쪽이 소음보다 싸다).
DONE = re.compile(r"(확인했|검사했|감사했|판독했|훑었|살폈|고쳤|닫았|끝냈|마쳤|"
                  r"통과했|점검했|반영했|처리했|세웠|걸었|배선했|이식했|옮겼)")
# 앞으로 할 말은 주장이 아니다 — 어미로 가른다.
FUTURE = re.compile(r"(하겠|할 것|할게|하려|합니다\s*$|예정|계획)")
# 스스로 한정한 말은 「다 덮었다」가 아니다.
HEDGE = re.compile(r"(일부|중 일부|만 |못 |안 |미검증|예측|추정|아직)")


def is_user_text(rec):
    if rec.get("type") != "user":
        return False
    c = (rec.get("message") or {}).get("content")
    return isinstance(c, str) or (isinstance(c, list) and any(
        isinstance(b, dict) and b.get("type") == "text" for b in c))


def claims_in(recs):
    """`(주장 문장, 그 턴이 도구를 불렀나)` 목록. 순수 함수 — 테스트 대상.

    ★★ **창은 「응답」이 아니라 「턴」이다** (2026-08-25, 첫 마감에서 드러났다).
      처음엔 `requestId` 로 묶었는데 **최종 보고는 도구를 안 부른다** — 그래서
      *[발화 생략]* 로 닫는 보고가 **언제나** 맨손으로 잡혔다.
      그건 오탐이 아니라 **구조적 오탐**이고, 그런 자는 곧 무시된다(경보 피로).
      → 사용자 발화 하나에서 다음 발화까지를 한 턴으로 보고, **그 턴 안에서
        도구를 한 번이라도 불렀으면** 맨손이 아니다. 실제 작업이 그 단위로 일어난다.
    ☐ 그 대가: 턴 앞머리에서 엉뚱한 명령을 돌리고 끝에 「전수」라 써도 통과한다.
      보증은 여전히 «맨손이 아니다» 하나다.
    """
    said, hastool = {}, set()
    turn = 0
    for rec in recs:
        if is_user_text(rec):
            turn += 1
            continue
        if rec.get("type") != "assistant":
            continue
        key = turn
        for b in ((rec.get("message") or {}).get("content") or []):
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and b.get("text", "").strip():
                said[key] = said.get(key, "") + b["text"]
            elif b.get("type") == "tool_use":
                hastool.add(key)
    out = []
    for key, text in said.items():
        for line in re.split(r"[.!?\n]|다\.", text):
            line = line.strip()
            if not line or not SCOPE.search(line):
                continue
            if not DONE.search(line):          # 범위 낱말만 있고 완료가 없으면 서술이다
                continue
            if FUTURE.search(line) or HEDGE.search(line):
                continue
            out.append((line[:90], key in hastool))
    return out


def records(path):
    for line in path.open(encoding="utf-8", errors="replace"):
        try:
            yield json.loads(line)
        except ValueError:
            continue


def latest_session(root):
    base = Path.home() / ".claude" / "projects"
    if not base.is_dir():
        return None
    want = str(root).replace("/", "\\").rstrip("\\").lower()
    best = None
    for d in base.iterdir():
        for f in (d.glob("*.jsonl") if d.is_dir() else []):
            cwd = ""
            try:
                with f.open(encoding="utf-8", errors="replace") as fh:
                    for i, ln in enumerate(fh):
                        if i >= 40:
                            break
                        try:
                            c = json.loads(ln).get("cwd")
                        except ValueError:
                            continue
                        if c:
                            cwd = str(c).replace("/", "\\").rstrip("\\").lower()
                            break
            except OSError:
                continue
            if cwd == want or cwd.startswith(want + "\\"):
                if best is None or f.stat().st_mtime > best.stat().st_mtime:
                    best = f
    return best


SELFTEST = [
    ("양성 — 맨손으로 「전수」", [{"type": "assistant", "requestId": "r1", "message": {
        "content": [{"type": "text", "text": "전수로 확인했다"}]}}], 1),
    ("음성 — 같은 응답이 도구를 불렀다", [{"type": "assistant", "requestId": "r2", "message": {
        "content": [{"type": "text", "text": "전수로 확인했다"},
                    {"type": "tool_use", "name": "Bash", "input": {}}]}}], 0),
    ("음성 — 앞으로 하겠다는 말은 주장이 아니다", [{"type": "assistant", "requestId": "r3", "message": {
        "content": [{"type": "text", "text": "전수로 재판독하겠다"}]}}], 0),
    ("음성 — 스스로 한정한 말", [{"type": "assistant", "requestId": "r4", "message": {
        "content": [{"type": "text", "text": "전부는 아니고 일부만 봤다"}]}}], 0),
    ("음성 — 범위 낱말이 없다", [{"type": "assistant", "requestId": "r5", "message": {
        "content": [{"type": "text", "text": "세 건을 고쳤다"}]}}], 0),
]


def selftest():
    bad = 0
    print("[자기 검정] 범위 주장 감사기")
    for desc, recs, want in SELFTEST:
        got = sum(1 for _, backed in claims_in(recs) if not backed)
        ok = got == want
        bad += 0 if ok else 1
        print("  %s %-40s 근거없는 주장 %d (기대 %d)"
              % ("OK  " if ok else "**틀림**", desc, got, want))
    print()
    print("  ※ ☐ 이 자가 **못 보는 것**: 도구를 불렀다고 **그 범위를 낸 것은 아니다.**")
    print("     엉뚱한 것을 돌리고 「전수」라 써도 통과한다 — 보증은 «맨손이 아니다» 하나다.")
    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=str(ROOT))
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    root = Path(a.root).resolve()
    p = latest_session(root)
    if not p or not p.exists():
        if not a.quiet:
            print("[범위 주장] 세션 기록을 못 찾았다 — SKIP (찾은 자리: cwd 가 %s 이거나 그 아래)"
                  % root)
        return 0
    claims = claims_in(list(records(p)))
    bare = [c for c, backed in claims if not backed]
    if a.quiet and not bare:
        return 0
    print("[범위 주장] 「전수·전부·모두」에 그 범위를 낸 명령이 붙어 있나")
    print("  주장 %d건 · 그중 **맨손 %d건**" % (len(claims), len(bare)))
    for c in bare[:8]:
        print("    · " + c)
    if len(bare) > 8:
        print("    … 외 %d건" % (len(bare) - 8))
    if bare:
        print("\nFAIL — 범위를 주장했는데 **그 범위를 낸 명령이 없다.**", file=sys.stderr)
        print("  그 수는 어디서 왔는지가 없다 — 세거나, 범위를 좁혀 쓰거나, 둘 중 하나다.",
              file=sys.stderr)
        return 1
    if not a.quiet:
        print("  맨손 주장 없음.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
