# -*- coding: utf-8 -*-
r"""홑글자 `l` 을 `\ell` 로 — **숫자 첨자가 붙은 길이 기호만** 기계가 고친다 (신설 2026-09-07).

    python tools/fix_bare_ell.py --subject=수치해석            # 훑어만 본다
    python tools/fix_bare_ell.py --subject=수치해석 --apply
    python tools/for_each_subject.py fix_bare_ell.py --apply   # 전 과목

★ **왜 도구인가.** `checks_content.bare_ell_issues`(C-bare_ell)는 2026-08-04 부터 돌았는데
  **처방 도구가 없었다** — 그래서 신고가 쌓이기만 했다(2026-09-07 실측 53건). 같은 부류의
  다른 검사는 전부 `fix_*` 짝이 있다(`audit_fix_tool_coverage.py` 가 그 짝을 센다).

★★ **기계가 고치는 것은 `l_<숫자>` 하나뿐이다.** 판정선은 *[발화 생략]* 다:

  | 모양 | 누가 | 왜 |
  |---|---|---|
  | `l_1` · `l_2` | **기계** | 숫자 첨자가 붙은 홑 `l` 은 길이 기호 말고 될 것이 없다 |
  | `x_l`(짝 `x_u` 있음) | 아무도 | 하한 첨자다 — 검사 자신이 이미 예외로 판정한다 |
  | 홀로 선 `l` | **사람** | 길이일 수도, 이름이 `l` 인 변수일 수도 있다. 찍어만 준다 |

  ★ 첨자는 **LaTeX 자리에만** 나온다(평문 필드는 유니코드 아래첨자가 규격이다). 그래서
    `\ell` 로 바꾸는 것이 안전하다 — 평문 필드였다면 `ℓ` 여야 하는데 그 자리엔 `_` 가 없다.

**사람이 판정하는 자리:** 「홀로 선 `l`」 목록. 이 도구는 그것을 **고치지 않는다.**
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import audit_content                                                      # noqa: E402
from buildlib.checks_content import bare_ell_issues                       # noqa: E402

# 숫자 첨자가 붙은 홑 `l` — 앞뒤가 글자가 아니고 앞의 `\` 도 아니다(`\ell_1` 을 다시 안 잡는다).
NUMBERED = re.compile(r"(?<![A-Za-z\\])l(_\d)")


def fix_text(text):
    """`(고친 텍스트, 바꾼 개수)`. 순수 함수 — 테스트가 직접 부른다."""
    new, n = NUMBERED.subn(r"\\\\ell\1", text)
    return new, n


def main():
    apply_changes = "--apply" in sys.argv
    subject = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--subject=")), None)
    data = os.path.join(ROOT, "data", subject) if subject else audit_content.DATA
    if not os.path.isdir(data):
        print("[해당 없음] 그런 과목 폴더가 없다: " + str(subject))
        return 0

    total, touched, manual = 0, [], []
    for name in sorted(os.listdir(data)):
        if not re.fullmatch(r"ch\d+\.json", name):
            continue
        path = os.path.join(data, name)
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        new, n = fix_text(src)
        # ★ **쓰기 전에 파싱한다** (AGENTS 「JSON 주입: 정규식 replace 금지」의 취지).
        #   이 치환은 `l_1` → `\\ell_1` 뿐이라 이스케이프를 깨지 않지만, «안 깨진다» 는
        #   주장은 파서가 해야 한다 — 깨진 파일을 쓰고 나면 되돌릴 자리가 없다.
        try:
            parsed = json.loads(new)
        except ValueError as e:
            print("  %s — 치환 뒤 JSON 이 깨진다. 건드리지 않았다: %s" % (name, e),
                  file=sys.stderr)
            continue
        if n:
            total += n
            touched.append((name, n))
            if apply_changes:
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(new)
        # 남는 것은 사람 몫이다 — 고친 뒤 상태로 센다.
        left = bare_ell_issues(parsed)
        if left:
            manual.append((name, len(left), left[0]))

    print("[대상] data/" + os.path.basename(data))
    for name, n in touched:
        print("  %s — `l_<숫자>` %d곳" % (name, n))
    print("합계 — 기계가 고칠 수 있는 것 %d곳%s" % (total, " (적용함)" if apply_changes else ""))
    if manual:
        print("\n★ 사람이 판정할 자리 — 홀로 선 `l`(길이인가, 이름이 l 인 변수인가):")
        for name, n, first in manual:
            print("  %s — %d건 · 예: %s" % (name, n, first))
    return 0


if __name__ == "__main__":
    sys.exit(main())
