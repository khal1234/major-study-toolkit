# -*- coding: utf-8 -*-
"""사용자가 [발화 생략]고 말한 턴에 **기준선이 안 밀린 챕터**를 한 줄로 알린다.

열린 날 2026-08-18. 사용자: *[발화 생략]* — 같은 요청이 세 번째다.

★★ **왜 문서로는 안 닫혔나.** `AGENTS.md` 는 이미 *[발화 생략]* 고
  적고 있고 에이전트 메모리에도 *[발화 생략]* 가 있다. 그런데 둘 다
  **에이전트가 그 순간을 알아채는 것**에 기대고 있었다 — 「배치의 끝」은 관측 가능한 사건이
  아니라서(AGENTS 「방지장치의 트리거는 내가 반드시 하는 일에 건다」) 매번 건너뛰어졌다.

★ **관측 가능한 사건은 「배치의 끝」이 아니라 「사용자의 확인 발화」다.** 그건 이 훅이 실제로
  읽을 수 있다. 그래서 트리거를 그리로 옮긴다 — 규칙이 아니라 **자리**를 바꾼 것이다.

★ **막지 않는다. 센 것을 보여 줄 뿐이다.** 오탐 비용이 한 줄이라 게이트로 만들 이유가 없고,
  무엇을 확인했는지는 사람만 안다(에이전트가 「밀어도 되나」를 판정하면 그게 곧 삼키는 길이다).

★ **빌드를 돌리지 않는다** — 매 턴 도는 자리라 비싸면 안 된다. 기준선 스냅샷의 sha 와 지금
  HEAD 사이에 **그 챕터 파일을 건드린 커밋이 있는가**만 센다(`git log <sha>..HEAD -- <경로>`).
  그 수는 「앞으로 보이는 변경」과 같지 않다(변경점 판정은 빌드가 한다) — 그래서 문구도
  «N커밋 쌓였다» 이지 «N항목 보인다» 가 아니다. 과장하지 않는 것이 이 자의 몫이다.

잠금 `test_checks.py::test_review_baseline_reminder_reads_the_user_signal`.
"""
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ★ 「봤다」로 읽는 말. 넓게 잡는다 — 놓치는 쪽이 이 자가 열린 이유이고, 헛치는 값은 한 줄이다.
#   단 **요청형은 뺀다**(「확인해줘」·「봐줘」) — 그건 아직 안 본 것이다.
SEEN_RE = re.compile(
    r"(다\s*봤|확인\s*했|확인\s*완료|검수\s*했|검수\s*끝|봤어|봤다|괜찮네|괜찮아|"
    r"이상\s*없|문제\s*없|넘어가자|다음\s*장)")
ASKING_RE = re.compile(r"(확인\s*해|봐\s*줘|봐줄|검수\s*해)")


def read_payload():
    """훅 페이로드는 UTF-8 로 명시해 읽는다(Windows 기본 cp949 — AGENTS 알려진 함정)."""
    raw = sys.stdin.buffer.read() if not sys.stdin.isatty() else b""
    try:
        return json.loads(raw.decode("utf-8", "replace") or "{}")
    except Exception:
        return {}


def _git(args):
    p = subprocess.run(["git", "-c", "core.quotepath=false"] + args, cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.stdout if p.returncode == 0 else ""


def pending_chapters(root=ROOT):
    """[(챕터경로, 기준선 sha, 그 뒤 그 파일을 건드린 커밋 수)] — 0건이면 빈 목록.

    ★ **첫 판은 틀렸고 조용히 0건이었다** (2026-08-18, 규칙 11 「새 자의 첫 실행은 자를 재는 것」).
      `chNN.json` 스냅샷에서 `rev` 를 읽으려 했는데 그 파일은 **기준선 시점의 챕터 본문 사본**
      이라 그런 키가 없다. 기준선 sha 는 옆의 **`chNN.accepted.json` 의 `baselineRev`** 에 있다.
      키를 잘못 짚어도 출력이 「알릴 것 없음」과 같아서, 안 재 봤으면 그대로 나갔을 자리다.
    """
    out = []
    data = os.path.join(root, "data")
    if not os.path.isdir(data):
        return out
    for subject in sorted(os.listdir(data)):
        snap_dir = os.path.join(data, subject, ".review-snapshot")
        if not os.path.isdir(snap_dir):
            continue
        for name in sorted(os.listdir(snap_dir)):
            if not name.endswith(".accepted.json"):
                continue
            try:
                with open(os.path.join(snap_dir, name), encoding="utf-8") as fh:
                    doc = json.load(fh) or {}
            except Exception:
                continue
            revs = [str((v or {}).get("baselineRev") or "") for v in doc.values()
                    if isinstance(v, dict)]
            base = next((r for r in revs if r), "")
            if not base:
                continue
            rel = "data/" + subject + "/" + name.replace(".accepted.json", ".json")
            log = _git(["log", "--oneline", base + "..HEAD", "--", rel])
            n = len([ln for ln in log.splitlines() if ln.strip()])
            if n:
                out.append((rel, base[:7], n))
    # ★ 쌓인 커밋이 많은 것부터 — 방금 작업한 챕터가 위로 온다.
    #   첫 실측(2026-08-18, 열역학): **8건**인데 그중 일곱이 **1커밋짜리 묵은 것**이었고
    #   방금 만진 ch07 만 3커밋이었다. 정렬 없이 그대로 내면 목록이 잡음이 되고,
    #   **경보 피로는 검사기를 죽인다** — 이 리포가 반복해 적어 둔 그 실패다.
    out.sort(key=lambda r: -r[2])
    return out


def main():
    # ★ 묻는 자리를 따로 연다 — 평소 침묵이라 「없다」와 「못 읽었다」가 겉모습이 같다(규칙 11).
    #   첫 판이 키를 잘못 짚어 조용히 0건이었던 것이 이 깃발을 만든 이유다.
    if "--selftest" in sys.argv:
        due = pending_chapters()
        print("[자기점검] 기준선 스냅샷을 읽어 밀 것이 있나 — %d건" % len(due))
        for rel, base, n in due:
            print("  · %s — 기준선 %s 이후 커밋 %d개" % (rel, base, n))
        if not due:
            print("  (0건이 「스냅샷을 못 읽었다」가 아닌지 보려면 "
                  "data/<과목>/.review-snapshot/chNN.accepted.json 이 있는지 확인할 것)")
        return 0
    text = str(read_payload().get("prompt") or "")
    if not SEEN_RE.search(text) or ASKING_RE.search(text):
        return 0
    due = pending_chapters()
    if not due:
        return 0
    print("[기준선] 「봤다」로 읽힌다 — 기준선이 안 밀린 챕터가 있다(막지 않는다. 판정은 사람이 한다):")
    for rel, base, n in due[:6]:
        ch = os.path.basename(rel).replace(".json", "")
        print("  · %s — 기준선 %s 이후 그 파일을 건드린 커밋 %d개" % (ch, base, n))
    print("  ☞ 커밋 → 다시 빌드 → "
          "`python tools/build_site.py --all --quiet --accept-review-as-built "
          "--accept-review-chapter=<chNN>` (미커밋 상태로 빌드된 화면은 플래그로 못 푼다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
