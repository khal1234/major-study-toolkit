# -*- coding: utf-8 -*-
"""회귀 테스트가 **조용히 줄어들었는지** 본다 (읽기 전용).

    python tools/audit_check_erosion.py            # 기준선과 대조
    python tools/audit_check_erosion.py --accept    # 지금 상태를 기준선으로 (의도적일 때만)

## 왜 (2026-08-12)

바깥 자료에서 온 지적인데 **우리에게 그대로 해당했다:**
[사용자 발화 인용 생략]

이 리포에는 **「검사 완화·우회는 빨강」(규칙 10)** 이 있는데 그건 **문장**이다.
실측(2026-08-12): 테스트 함수 **239개** · 판정 **2,230건**. 그중 하나를 지워도
**빌드도 회귀도 close_report 도 아무 말을 하지 않는다.** 규칙 7⑷ 의 판정선
([사용자 발화 인용 생략])에 정확히 걸리는 자리다.

## 무엇을 막나 — 「지우지 못하게」가 아니라 「지운 것이 보이게」

  ⑴ 테스트 **함수가 사라짐**
  ⑵ 함수는 남았는데 그 안의 **판정(`expect`) 수가 줄어듦** — 케이스만 빼는 쪽이 더 조용하다

★ **정당한 삭제를 금지하지 않는다.** 검사가 통합되거나 규격이 바뀌면 줄어드는 게 맞다.
  다만 그때는 `--accept` 로 기준선을 **명시적으로** 옮겨야 하고, 그 커밋이 diff 에 남는다.
  ★ 판정선은 「줄었나」가 아니라 **「줄인 것을 사람이 볼 수 있나」** 다.

★ **이 자를 늘리는 쪽으로 쓰지 않는다.** 판정 수는 품질이 아니라 *변화 감지용 지문*이다 —
  숫자를 목표로 삼으면 의미 없는 `expect` 를 채우게 된다(묶음률과 같은 함정).

## ★★ 이름을 바꾼 테스트를 「사라졌다」고 읽던 것 (신설 2026-08-13)

**실사고.** `test_review_cosmetic_fold` 를 `test_review_drill_fold_label` 로 **옮겼는데**
(「표기만 숨김」 토글이 사라져 그 토글을 잠그던 케이스를 「문풀·연습 숨김」 라벨을 잠그는
자리로 옮긴 것이다) 기준선은 옛 이름을 들고 있어서, **merge 하는 모든 과목이 있지도 않은
테스트 1건으로 close 가 막혔다.** 부류로 보면 **「이름이 곧 정체성」이라고 본 것**이 원인이고,
rename 은 이 자에게 언제나 **delete + add** 로 보이므로 그대로 두면 되풀이된다.

**처방 — 이름이 아니라 「그 테스트가 무엇을 잠그는가」로 잇는다.** 각 `expect` 의 **라벨**을
정규화해 지문(mark)으로 삼고, 사라진 이름의 지문이 **새로 나타난 이름** 안에 충분히 살아
있으면 `[이름 변경]` 으로 읽는다(close 를 막지 않는다). 그 뒤 **판정 수 비교는 그대로 돈다** —
이름을 다시 이어 준 것뿐이지 게이트를 무르게 한 것이 아니다. 그래서 *옮기면서 판정을 줄인*
경우는 여전히 `판정이 줄어든 테스트` 로 잡힌다.

### 왜 라벨인가 (실측 2026-08-13, 그 실사고 커밋 `b7e0e74` 대조)

| 지문 후보 | 그 rename 에서 살아남은 비율 | 판정 |
|---|---|---|
| **`expect` 라벨** | **8/15 = 53%** | 채택 |
| `expect` 조건 소스 | 3/15 = 20% | 기각 — 옮기면 **가리키는 대상 이름이 통째로 바뀐다**(`reviewHideCosmetic` → `reviewHideDrill`) |
| 독스트링 첫 줄 | — | 기각 — 오늘 하루에도 여러 독스트링이 고쳐졌다. 자주 고치는 것은 지문이 될 수 없다 |
| 파일 + 줄 번호 | — | 기각 — 위에 케이스 하나만 끼워 넣어도 전부 어긋난다 |

**rename 커밋에 `--accept` 를 강제하는 안은 기각했다** — 사람이 잊으면 그대로 새는 형태라
이 리포가 반복해 실패한 부류다(AGENTS 「방지장치의 트리거는 내가 반드시 하는 일에 건다」).
지금 처방의 트리거는 **자가 돌 때마다**이므로 잊을 자리가 없다.

### 겹침 기준 — **3건 이상 그리고 옛 판정의 40% 이상** (근거는 실측)

  · **위(오탐) 쪽:** 현재 테스트 263개의 **모든 쌍**을 재 보니 남남끼리 라벨을 공유하는 쌍은
    **35쌍뿐이고 최대 공유가 2건**이었다. 그래서 **절대 하한 3건**이면 관측된 잡음 위로 올라선다
    (비율만 쓰면 판정이 3건뿐인 작은 테스트가 남과 2건 겹쳐 67% 로 뜬다 — 하한이 그걸 막는다).
  · **아래(놓침) 쪽:** 실제 rename 이 **53%** 였다. 50% 로 잡으면 여유가 3%p 뿐이라
    라벨 하나만 더 다듬어도 다시 유령이 된다. **40%** 는 실측 아래로 여유를 두면서도
    하한 3건 덕분에 오탐 쪽 여유는 그대로다.
  · **양쪽으로 틀릴 수 있는 조항이라 회귀도 양쪽을 잠근다**(`test_checks_do_not_erode_silently`
    ⑺~⑿). 기준을 못 넘으면 **`사라진 테스트` 로 신고**되므로, 틀리는 방향은 언제나
    *더 시끄러운 쪽*이다 — 조용히 넘어가지 않는다.

★ **지문이 맞아도 판정이 줄면 막는다.** rename 을 알아보는 것과 침식을 봐주는 것은 다른 일이다.
"""
import ast
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
TESTS = REPO / "tools" / "test_checks.py"
BASELINE = REPO / "docs" / "check-inventory.json"
ALLOW = REPO / "docs" / "check-erosion-allow.txt"
DEF = re.compile(r"^def (test_\w+)\(")

MARK_LEN = 8            # sha1 앞 8자리. 지문 2,500개에서 충돌 확률 ~0.08%
MIN_SHARED = 3          # 남남끼리 관측된 최대 공유는 2건 (263개 전수)
MIN_RATIO = 0.40        # 실측된 실제 rename 은 53%
RENAME = "이름 변경"
BLOCKING = ("사라진 테스트", "판정이 줄어든 테스트")


def normalize_label(text):
    """지문으로 쓰기 위한 정규화 — **글자만** 남긴다.

    공백·따옴표·★·괄호가 떨어져 나가고, 이어서 **맨 앞의 케이스 번호**(`⑴`·`(3)`·`12.`)도
    떨어진다. 번호를 남기면 케이스를 하나 끼워 넣는 것만으로 그 아래 지문이 전부 어긋난다.

    ★ 앞의 번호를 따로 떼는 이유: `\\W` 는 `⑴`(유니코드 카테고리 No)을 **글자로 본다**
      — `str.isalnum()` 이 참이기 때문이다. 그래서 구두점만 지우는 것으로는 안 떨어진다.
    """
    body = re.sub(r"\W+", "", text, flags=re.UNICODE)
    cut = 0
    while cut < len(body) and unicodedata.category(body[cut]).startswith("N"):
        cut += 1
    return body[cut:].lower().lower()


def mark(text):
    return hashlib.sha1(normalize_label(text).encode("utf-8")).hexdigest()[:MARK_LEN]


def inventory(text):
    """{테스트 함수: 그 안의 판정 수}. 순수 함수 — 테스트가 직접 부른다.

    ★ 세는 방식을 바꾸지 않았다(글자 그대로 `expect(`). 지문을 얹으면서 세는 자까지
      바꾸면 **기준선의 숫자가 통째로 흔들려** 무엇이 진짜 줄었는지 알 수 없게 된다.
    """
    out, cur = {}, None
    for line in text.splitlines():
        m = DEF.match(line)
        if m:
            cur = m.group(1)
            out[cur] = 0
        elif line.startswith("def ") or line.startswith("if __name__"):
            cur = None                       # 테스트가 아닌 최상위 함수 — 세지 않는다
        elif cur:
            out[cur] += line.count("expect(")
    return out


def marks(text):
    """{테스트 함수: 정렬된 지문 목록}. 순수 함수.

    `expect(라벨, …)` 의 **첫 인자**만 본다. 문자열 리터럴이 아니면(변수·f-string·이어붙이기)
    그 식의 소스를 그대로 정규화한다 — 어차피 같은 자리로 옮겨 가면 같이 따라간다.
    파일이 파싱되지 않으면 **빈 dict** 를 돌려 옛 동작(이름만 보기)으로 내려앉는다.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
            continue
        found = set()
        for sub in ast.walk(node):
            if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == "expect" and sub.args):
                continue
            first = sub.args[0]
            found.add(mark(first.value
                           if isinstance(first, ast.Constant) and isinstance(first.value, str)
                           else ast.unparse(first)))
        out[node.name] = sorted(found)
    return out


def snapshot(text):
    """기준선에 쓰는 형태 — {이름: {"expects": n, "marks": "지문 지문 …"}}.

    지문을 **한 줄 문자열**로 둔다(목록으로 두면 판정 하나가 바뀔 때마다 diff 가 여러 줄로
    번진다 — 기준선은 사람이 읽고 넘기는 자리라 한 테스트 = 한 줄이 낫다).
    """
    counts, fingerprints = inventory(text), marks(text)
    return {name: {"expects": n, "marks": " ".join(fingerprints.get(name, []))}
            for name, n in counts.items()}


def entry(value):
    """기준선·현재 항목을 (판정 수, 지문 집합) 으로 편다.

    **옛 형식(정수)도 그대로 받는다** — 기준선을 아직 안 옮긴 과목에서 이 자가 터지면
    안 되고, 그때는 지문이 없으니 이름만 보던 옛 동작이 된다.
    """
    if isinstance(value, dict):
        return int(value.get("expects", 0)), set(str(value.get("marks", "")).split())
    return int(value), set()


def allowed():
    """{이름}. **사유 없는 줄은 예외로 안 친다** (orphan-checks-allow 선례)."""
    out = set()
    if not ALLOW.is_file():
        return out
    for line in ALLOW.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        name, _, why = line.partition("|")
        if name.strip() and why.strip():
            out.add(name.strip())
    return out


def best_match(gone_marks, fresh):
    """(이름, 겹친 건수) — 새로 나타난 이름 중 지문이 가장 많이 겹치는 것. 순수 함수."""
    best, shared = None, 0
    for name in sorted(fresh):
        n = len(gone_marks & fresh[name])
        if n > shared:
            best, shared = name, n
    return best, shared


def renames(now, before, allow):
    """{옛 이름: (새 이름, 겹친 건수, 옛 판정 수)}. 순수 함수.

    후보는 **기준선에 없던 이름**뿐이다 — 원래 있던 테스트가 남의 판정을 흡수한 것처럼
    보이면 안 된다. 여러 옛 이름이 한 새 이름으로 가는 것(합치기)은 막지 않는다.
    """
    fresh = {name: entry(v)[1] for name, v in now.items() if name not in before}
    fresh = {name: m for name, m in fresh.items() if m}
    out = {}
    for name in sorted(before):
        if name in now or name in allow:
            continue
        old_marks = entry(before[name])[1]
        if not old_marks:
            continue                          # 옛 형식 기준선 — 지문이 없으니 이을 수 없다
        cand, shared = best_match(old_marks, fresh)
        if cand and shared >= MIN_SHARED and shared / len(old_marks) >= MIN_RATIO:
            out[name] = (cand, shared, len(old_marks))
    return out


def erosion(now, before, allow):
    """[(부류, 이름, 설명)]. 순수 함수.

    `이름 변경` 행은 **알림**이다 — `BLOCKING` 에 없으므로 close 를 막지 않는다.
    다만 이어 준 뒤의 판정 수 비교는 그대로 돈다(옮기면서 줄였으면 잡힌다).
    """
    bad = []
    moved = renames(now, before, allow)
    for name in sorted(before):
        if name in allow:
            continue
        count, old_marks = entry(before[name])
        alias = name
        if name not in now:
            if name in moved:
                alias, shared, total = moved[name]
                bad.append((RENAME, name,
                            "→ %s (판정 %d/%d 겹침)" % (alias, shared, total)))
            else:
                detail = "기준선에는 있었다"
                if old_marks:
                    cand, shared = best_match(
                        old_marks, {n: entry(v)[1] for n, v in now.items() if n not in before})
                    if shared:
                        detail += " · 가장 가까운 새 테스트 %s 는 %d/%d 겹침(기준 %d건·%d%%)" % (
                            cand, shared, len(old_marks), MIN_SHARED, int(MIN_RATIO * 100))
                bad.append(("사라진 테스트", name, detail))
                continue
        if entry(now[alias])[0] < count:
            bad.append(("판정이 줄어든 테스트", alias,
                        "%d → %d" % (count, entry(now[alias])[0])))
    return bad


def main():
    if not TESTS.is_file():
        print("[해당 없음] tools/test_checks.py 가 없다")
        return 0
    text = TESTS.read_text(encoding="utf-8", errors="replace")
    now = snapshot(text)
    if "--accept" in sys.argv:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(now, ensure_ascii=False, indent=1,
                                       sort_keys=True) + "\n", encoding="utf-8")
        print("기준선 갱신 — 테스트 %d개 · 판정 %d건. **이 커밋이 곧 기록이다.**"
              % (len(now), sum(entry(v)[0] for v in now.values())))
        return 0
    if not BASELINE.is_file():
        print("기준선이 없다 — `python tools/audit_check_erosion.py --accept` 로 만들 것")
        return 0
    before = json.loads(BASELINE.read_text(encoding="utf-8"))
    rows = erosion(now, before, allowed())
    for kind, name, detail in rows:
        print("  %-18s %-52s %s" % ("[%s]" % kind if kind == RENAME else kind, name, detail))
    bad = [r for r in rows if r[0] in BLOCKING]
    # ★ 이름 변경은 **요약 줄에도** 적는다 — `close_report` 는 이 마지막 한 줄만 옮기므로,
    #   위에만 찍으면 거기서는 *조용히 통과한 것*과 구별되지 않는다(부류: 기록≠보고).
    moved = [r for r in rows if r[0] == RENAME]
    print("테스트 %d개 · 판정 %d건 — %s%s"
          % (len(now), sum(entry(v)[0] for v in now.values()),
             "%d건 줄었다" % len(bad) if bad else "줄어든 것 없음",
             " · 이름 변경 %d건(%s)" % (len(moved), ", ".join(
                 "%s %s" % (r[1], r[2]) for r in moved[:2])) if moved else ""))
    if bad:
        print("  -> 의도한 것이면 `--accept` 로 기준선을 옮기고 **그 커밋에 사유를 적을 것**.\n"
              "     영구 예외는 `docs/check-erosion-allow.txt` 에 `이름 | 사유` 로.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
