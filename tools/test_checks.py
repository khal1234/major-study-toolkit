# -*- coding: utf-8 -*-
r"""회귀 테스트 — 이 저장소의 **starter**판이다. 손으로 쓴 콘텐츠가 없어도 도는 것만 골랐다.

★ 원본 프로젝트(전공정리)의 test_checks.py는 25,000줄이 넘었다 — 그건 그 프로젝트가
  실제로 만든 콘텐츠에 대한 회귀 이력이라, 이 참고용 저장소에는 옮기지 않았다
  (README·AGENTS.md 「뺀 것」참고). 그런데 파일을 통째로 빼면서 부작용이 생겼다:
  AGENTS.md의 「close의 정의」— *결함은 재현 케이스 + 고친 형태가 통과하는 케이스가
  test_checks.py에 들어가야 close다* — 가 이 저장소에서는 **실행할 대상이 없어 아무 뜻도
  없는 문장**이 돼 있었다. verify_workorder.py·close_report.py·verify_all.py는 이 파일이
  없으면 "[skip] 공개판에 없음"으로 조용히 넘어가도록 고쳐 놨는데, 그 침묵이 곧
  "이 저장소는 close 규율이 아예 안 도는 저장소"라는 뜻이었다.

★ 이 파일이 하는 일은 하나다 — **패턴을 보여준다.** 아래 각 테스트는 ⑴ 결함을 재현하는
  합성 입력과 ⑵ 고친 형태가 통과하는 입력을 나란히 둔다. 실제 콘텐츠(data/) 없이도
  buildlib의 순수 함수만으로 검증된다는 점이 핵심이다 — 새 프로젝트에서 결함을 하나
  고칠 때마다 이 파일에 같은 모양으로 케이스를 추가해 나가는 것이 이 저장소가 보여주려는
  방식이다(원본의 실제 이력은 못 옮겼지만 **골격**은 옮긴다).

사용:
    python tools/test_checks.py               # 전부 실행
    python tools/test_checks.py --fail-only    # 실패한 것만 출력
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

_RESULTS = []


def expect(desc, cond, extra=None):
    """판정 하나를 기록한다. 실패해도 멈추지 않는다 — 나머지도 마저 본다."""
    _RESULTS.append((desc, bool(cond), extra))


def test_math_slash_fraction_is_rejected():
    """열린 부류: 수식 안 슬래시 분수(`P/rho`) — 이 대화에서 재확인된 바로 그 결함.

    무엇이 새어나갔었나: 검사기가 챕터 JSON을 통해서만 도니, JSON 파이프라인 밖에서
    만든 콘텐츠(예: 독립 HTML 데모)는 애초에 이 함수를 거친 적이 없어 슬래시 분수가
    그대로 남았다. 이 케이스는 최소한 **함수 자체는 결함을 잡는다**는 것을 고정한다 —
    파이프라인 밖에서 도는 문제는 별개로, 함수 회귀는 여기서 막는다.
    """
    from buildlib.checks_content import slash_fraction_spans

    broken = r"x = F/k_1 + F/k_2"
    fixed = r"x = \frac{F}{k_1} + \frac{F}{k_2}"
    expect("슬래시 분수 'F/k_1' 이 잡힌다", len(slash_fraction_spans(broken)) >= 1,
           slash_fraction_spans(broken))
    expect("\\frac{}{} 로 고친 형태는 안 잡힌다", len(slash_fraction_spans(fixed)) == 0,
           slash_fraction_spans(fixed))
    # 지수·단위는 대상이 아니다(독스트링에 명시된 예외) — 오탐 방지 회귀.
    expect("지수 안 'y^{2/3}' 은 분수로 안 잡는다(오탐 방지)",
           len(slash_fraction_spans(r"y^{2/3}")) == 0)


def test_fix_math_slash_fraction_rewrite_is_conservative():
    r"""열린 부류: 처방이 애매한 자리를 잘못 고쳐 수식을 깨는 것.

    `\dot{m}/A` 같은 자리는 분자가 `\dot{m}` 인지 기계가 확신할 수 없다 — 그대로 감싸면
    백슬래시가 밖에 남아 수식이 깨진다. 이 케이스는 도구가 **확신 없으면 손대지 않고
    사람에게 넘긴다**는 계약을 고정한다.
    """
    from fix_math_slash_fraction import rewrite

    simple_out, simple_n, simple_manual = rewrite("F/k_1")
    expect("확실한 낱개 분수는 고친다", simple_out == r"\frac{F}{k_1}" and simple_n == 1,
           (simple_out, simple_n))

    tricky_out, tricky_n, tricky_manual = rewrite(r"\dot{m}/A")
    expect("백슬래시로 시작하는 분자는 기계가 손대지 않는다(사람에게 넘긴다)",
           tricky_n == 0 and len(tricky_manual) == 1, (tricky_out, tricky_n, tricky_manual))


def test_mathfrak_and_mathcal_registries_match_the_renderer():
    """열린 부류: 「검사기의 목록이 렌더러와 갈렸다」.

    `checks_content.py`의 `VIEWER_MATHCAL_LETTERS`·`VIEWER_MATHFRAK_LETTERS`는
    `site/template/viewer.template.html`의 `renderMath()`가 실제로 치환하는 글자와
    같아야 한다. 둘을 따로 손보면 검사기는 "이 글자 지원 안 됨"이라 신고하는데
    화면은 이미 그리고 있는(또는 그 반대) 상황이 난다 — 이 테스트가 그 갈림을 잠근다.
    """
    from buildlib.checks_content import VIEWER_MATHCAL_LETTERS, VIEWER_MATHFRAK_LETTERS

    tmpl_path = os.path.join(ROOT, "site", "template", "viewer.template.html")
    with open(tmpl_path, encoding="utf-8") as fh:
        src = fh.read()

    for letter in VIEWER_MATHCAL_LETTERS:
        expect("mathcal " + letter + " 이 렌더러에도 있다",
               ("\\mathcal{" + letter + "}") in src)
    for letter in VIEWER_MATHFRAK_LETTERS:
        expect("mathfrak " + letter + " 이 렌더러에도 있다",
               ("\\mathfrak{" + letter + "}") in src)


def test_guard_bash_blocks_command_substitution_but_allows_status():
    """열린 부류: 임의 명령 실행으로 이어지는 문법은 deny, 읽기 전용은 통과.

    `guard_bash.deny_reason()`이 이 저장소의 유일한 판정 지점이다(독스트링에 명시).
    ★ `git push --force` 류는 이 함수가 아니라 `.claude/settings.json`의 `deny`
      글롭 목록이 막는다 — 이 함수가 담당하는 것은 `cd` 접두·백틱/`$(…)` 명령 치환·
      `echo` 금지처럼 **문자열 자체에서 판정되는** 규칙들이다. 여기서 하나라도 새면
      AGENTS.md에 적힌 "임의 실행은 막는다"는 문장이 이 파일 밖에서는 산문이 된다.
    """
    from guard_bash import deny_reason

    expect("백틱 명령 치환은 막힌다",
           deny_reason('git commit -m "`whoami`"') is not None)
    expect("$(...) 명령 치환은 막힌다",
           deny_reason("git commit -m \"$(whoami)\"") is not None)
    expect("cd 로 시작하는 명령은 막힌다",
           deny_reason("cd tools && python build_site.py") is not None)
    expect("git status 는 안 막힌다(읽기 전용)",
           deny_reason("git status") is None)


def main():
    fail_only = "--fail-only" in sys.argv
    for fn in (test_math_slash_fraction_is_rejected,
               test_fix_math_slash_fraction_rewrite_is_conservative,
               test_mathfrak_and_mathcal_registries_match_the_renderer,
               test_guard_bash_blocks_command_substitution_but_allows_status):
        print("\n[" + fn.__name__ + "]")
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 — 회귀 스위트는 한 테스트가 죽어도 계속 돈다
            _RESULTS.append((fn.__name__ + " (예외)", False, repr(exc)))

    bad = 0
    for desc, ok, extra in _RESULTS:
        if ok and fail_only:
            continue
        bad += 0 if ok else 1
        line = "  " + ("[ok]  " if ok else "[FAIL]") + " " + desc
        if not ok and extra is not None:
            line += "  " + repr(extra)
        print(line)

    total = len(_RESULTS)
    print("\n%d/%d 케이스 통과" % (total - bad, total))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
