# -*- coding: utf-8 -*-
"""Shared constants and plain-text math helpers for the site builder."""
import re

BAD_CHARS = [chr(c) for c in (1, 7, 8, 11, 12)]
# renderMath(viewer.template.html)가 실제로 치환하는 명령의 레지스트리.
# 2026-07-26 확장: 수학 과목(ch02)에서 \lambda·\cos·\sqrt 등이 오탐됐다 — renderMath는
# 지원하고(tools/test_checks.py 'renderMath 심볼' 케이스로 검증) 이 목록만 낡아 있었다.
# 두 목록의 표류는 test_checks의 'LATEX_SUPPORTED ⊆ 템플릿 심볼' 케이스가 막는다.
LATEX_SUPPORTED = {
    "mathrm", "text", "vec", "frac", "Longrightarrow", "Rightarrow",
    "approx", "times", "cdot", "gamma", "pm", "sum", "rho", "Delta",
    "dot", "ddot", "pi", "eta", "int", "qquad", "quad", "left", "right",
    "kappa", "lambda", "mu", "nu", "omega", "theta", "alpha", "beta", "phi",
    "psi", "sigma", "tau", "varepsilon", "delta", "sin", "cos", "tan", "ln",
    "exp", "prime", "sqrt", "ne", "le", "ge", "to", "mp", "infty",
    "partial", "cdots", "ldots", "mathcal",
    # 2026-07-26 확장 2차: 인라인 수식 검사를 켜자 화면에 역슬래시째 찍히던 명령이 드러났다
    # (ch01 \equiv·\min·\tanh 11건, ch02 \sec 4건 — DOM textContent 실측).
    # renderMath에 심볼을 넣고 여기 등록한다. 순서: 템플릿 → 이 목록 → test_checks가 대조.
    # 2026-08-04 — 길이 기호 `\ell`. 본문 글꼴에서 `l` 은 잉크가 가장 적은 민무늬 세로획이라
    # 기호로 안 읽힌다(실측 `l` 84 vs `ℓ` 204). ℓ 은 본문·등폭 두 스택 모두에 실제 글리프가 있다.
    "ell",
    # 2026-08-07 — 대문자 `\Omega`. 동역학 16장 8절이 회전좌표계의 각속도를 Ω 로 쓰고
    # 물체의 각속도 ω 와 **일부러 다른 글자**로 둔다(교재 표기). 그 구별이 그 절의 요지다.
    "Omega",
    # 2026-08-14 — 대문자 `\Gamma`. 공학수학 ch05 가 감마함수를 쓰는데 어휘 밖이라 **날 유니코드
    # `Γ` 로 우회**해 왔다(실측 9곳, 전부 인라인 수식 안). 같은 수식에서 `\nu`·`\infty` 는 매크로인데
    # 감마만 유니코드라 표기가 한 줄 안에서 갈렸다. 글리프는 재고 넣었다 — 본문 스택에 실제 글리프
    # (폭 34.94, `L` 34.13 과 같은 자리) · 등폭 스택은 고정폭 37.5 로 폴백이 아니다.
    "Gamma",
    # 2026-08-13 — 순환적분 `\oint`. 열역학 ch07 의 클라우지우스 부등식(∮δQ/T ≤ 0)이
    # 이 장 전체의 출발점이라 기호 없이는 1절이 성립하지 않는다. 템플릿의 큰-연산자 줄이
    # *[발화 생략]* 고 자리를 열어 둔 그대로 넣었다.
    "oint",
    # 2026-08-06 — 벡터는 굵게(`\mathbf`). 교재(Hibbeler 15판 p.74 렌더 실측)가 벡터/스칼라를
    # **굵기**로 가르고 단위벡터에도 햇을 쓰지 않는다. 화살표(`\vec`)를 안 쓰는 이유는
    # `\dot`·`\ddot` 이 글자 위쪽을 이미 쓰기 때문이다 — 템플릿 renderMath 주석이 정본.
    # ★ `hat` 은 **일부러 빼 둔다.** 등록하지 않으면 데이터에 섞이는 순간 빌드가 막는다.
    "mathbf",
    # 2026-08-13 — `\hl{…}`: **짝지어 놓은 두 식에서 「여기가 다르다」를 색으로 짚는다**
    # (사용자: *[발화 생략]*).
    # 뜻은 **대조 하나뿐**이고 물리량이 아니다 — 시각 문법의 색 배정과 부딪히지 않게
    # 쓰는 카드가 그 뜻을 한 줄로 밝힌다. 치환 자리는 renderMath 에서 `\frac` **앞**이라
    # 아래 `check_latex_field` 의 `pre_frac` 매크로 목록에도 함께 있어야 한다.
    "hl",
    "equiv", "min", "max", "log", "lim",
    "sinh", "cosh", "tanh", "sec", "csc", "cot",
    "arcsin", "arccos", "arctan",
    # 2026-09-03 — 엑서지 `E`. Moran 교재가 엑서지를 에너지(이탤릭 E)와 다른 글꼴로 가른다.
    # ★★ **2026-09-08 정정 — `\mathfrak` 이 아니라 `\mathsf` 다.** 그때 사용자가 말한
    #   「고딕」은 한국어 조판의 **산세리프**인데 블랙레터(프락투어 𝔈)로 구현했다.
    #   교재 p.312 식 (7.1) 을 렌더해 확인했다: 엑서지 E 는 **업라이트 산세리프**다.
    #   `\mathbf` 과 같은 부류라 **그리는 글자를 따로 잠그지 않는다**(어떤 글자든 span 이 된다) —
    #   `\mathcal`·`\mathfrak` 이 글자 목록을 두던 이유는 그것들이 **글리프 치환**이라서였다.
    "mathsf",
    # 2026-09-08 — `\overline{…}`: 몰 기준 상태량(`R̄`·`h̄`). 결합문자를 안 쓰는 이유는
    # renderMath 주석이 정본이다. 치환 자리가 `\frac` 앞이라 `PRE_FRAC_MACROS` 에도 있어야 한다.
    "overline",
    # 2026-09-10 — 행렬식 환경 `\begin{vmatrix} … \end{vmatrix}`. 사용자 지적으로 열렸다:
    # *[발화 생략]*. 그전엔 **행렬 환경이 통째로 어휘 밖**이라 외적이 성분의
    # 출처 없이 결과부터 시작했다(부채 기록: `data/공학수학 1/ch08-build.workorder.md`).
    # ★ `begin`·`end` 는 **환경 이름을 안 보는 낱말**이라, 이 둘만 등록하면 `\begin{pmatrix}`
    #   처럼 **뷰어가 못 그리는 환경도 함께 통과한다.** 그래서 아래 `matrix_environment_issues`
    #   가 환경 이름을 따로 잠근다 — `\mathcal` 이 「명령은 지원인데 글자는 미지원」이던 것과
    #   같은 부류이고, 그때와 같은 처방(검사를 렌더러 쪽에 맞춘다)이다.
    "begin", "end",
}

# renderMath 가 실제로 그리는 **행렬 환경**. 템플릿의 치환이 정본이고 여기는 그 사본이다 —
# 늘리는 순서는 템플릿 → 이 집합 → 잠금 테스트, 반대로 하면 화면만 깨진 채 빌드가 초록이다.
MATRIX_ENVIRONMENTS = {"vmatrix"}


def matrix_environment_issues(where, s):
    """뷰어가 못 그리는 `\\begin{…}` 환경. 순수 함수 — `[사유, …]`.

    ★ **왜 `LATEX_SUPPORTED` 로 안 되나** — 그 집합은 `\\begin` 이라는 낱말만 보고
      중괄호 안의 환경 이름은 안 본다. `begin` 을 등록한 순간 `\\begin{pmatrix}` 도 통과하는데
      뷰어에는 그 치환이 없어 **역슬래시째 화면에 찍힌다.**
    """
    out = []
    for env in re.findall(r"\\begin\{([A-Za-z*]+)\}", s or ""):
        if env not in MATRIX_ENVIRONMENTS:
            out.append(where + ": renderMath 가 못 그리는 환경 \\begin{" + env + "} — 지금 그릴 수 있는 것은 "
                       + ", ".join(sorted(MATRIX_ENVIRONMENTS))
                       + " 뿐이다(템플릿 renderMath 의 치환을 먼저 늘리고 이 집합을 따라 옮길 것)")
    for env in re.findall(r"\\end\{([A-Za-z*]+)\}", s or ""):
        if env not in MATRIX_ENVIRONMENTS:
            out.append(where + ": renderMath 가 못 그리는 환경 \\end{" + env + "}")
    return out
# 과목 → 그 과목에서 쓸 수 있는 pitfall 출처 접두어들.
#
# ★ 2026-07-28: 접두어 **튜플**이던 것을 과목 매핑으로 바꿨다. 튜플일 때는 과목이 늘 때
#   한 줄 더하는 것을 사람이 기억해야 했고, 실제로 같은 날 등록된 다섯 과목 중 **기계재료와
#   고체역학이 빠진 채로** 통과했다. 빠뜨리면 그 과목은 pitfall 을 **하나도 못 쓰는데**
#   증상은 챕터를 다 쓰고 빌드를 돌린 뒤에야 나온다.
#   이제 test_checks.py::test_pitfall_source_prefixes 가 guard_bash.SUBJECT_BY_BRANCH 를
#   순회해 **등록된 과목이 전부 여기 있는지** 대조한다 — 새 과목이 생기면 그 즉시 깨진다.
#
#   값이 목록인 이유: 과목마다 1차 근거가 하나가 아니다. 기계재료는 **책이 아니라 강의노트가
#   1차 근거**라(materials 세션 확인) 둘 다 등록한다. 완화가 아니라 등록부 확장이다 —
#   규칙 2가 요구하는 것은 "출처가 있다"이지 특정 책 이름이 아니다.
#   `강의노트`에 '본문 경고'를 붙이지 않은 이유: 슬라이드는 쪽으로 가리키므로 실제 출처
#   문자열이 `강의노트1 p.15 (...)` 형태가 된다.
PITFALL_BOOK_BY_SUBJECT = {
    "열역학": ("Cengel 본문 경고",),
    "공학수학": ("Kreyszig 본문 경고",),
    "동역학": ("Hibbeler 본문 경고",),
    "기계재료": ("Callister 본문 경고", "강의노트"),
    "고체역학": ("Gere 본문 경고",),
    # ── 2-2 과목 (2026-08-15 등록). 저자는 **보유 파일 이름에서 확인한 것만** 적었다.
    "기계공작법": ("Kalpakjian 본문 경고",),
    "유체역학": ("Cengel 본문 경고",),          # Cengel·Cimbala 유체역학 4판
    "응용열역학": ("Moran 본문 경고",),
    "응용고체역학": ("Gere 본문 경고",),
    # ★ 전기전자는 보유 파일 이름에 **출판사(McGraw)만** 있어 저자를 몰랐다 — 확인 못 한 이름을
    #   적으면 그 문자열이 데이터의 «출처» 로 굳으므로(규칙 11) 비워 뒀던 자리다.
    #   **2026-08-15 에 책을 열어 확인했다**(`extract_textbook.py --pages 1-3`, 표제지 실측):
    #   *Principles and Applications of Electrical Engineering*, **Seventh Edition** ·
    #   **Giorgio Rizzoni**(The Ohio State University) · **James Kearns**(York College of
    #   Pennsylvania). 파일 이름의 `McGraw` 는 출판사였다.
    #   `강의노트` 를 함께 남기는 이유는 기계재료와 같다 — **「및 실험」 과목이라 실습 자료가
    #   1차 근거인 자리가 있다.** 빼는 판정은 그 과목 세션의 몫이고, 넣어 두는 것은 완화가
    #   아니라 등록부 확장이다(규칙 2가 요구하는 것은 «출처가 있다» 이지 특정 책이 아니다).
    "전기전자공학기초 및 실험": ("Rizzoni 본문 경고", "강의노트"),
    "공학수학 2": ("Zill 본문 경고",),
    # 교재가 없는 과목 — 사용자 판정 2026-08-15: *[발화 생략]*.
    "행복한 삶과 가족": ("강의노트",),
    "기계요소설계": ("Shigley 본문 경고",),
    "시스템제어": ("Nise 본문 경고",),
    "계측공학": ("Figliola 본문 경고",),
    "수치해석": ("Chapra 본문 경고",),
    "열전달": ("Incropera 본문 경고",),
    "응용유체역학": ("Munson 본문 경고",),
    "진동공학": ("Rao 본문 경고",),
    "스마트생산시스템": ("Groover 본문 경고",),
    "품질 및 신뢰성공학개론": ("Montgomery 본문 경고",),
}
PITFALL_SOURCE_PREFIXES = tuple(sorted(
    {prefix for prefixes in PITFALL_BOOK_BY_SUBJECT.values() for prefix in prefixes}
)) + ("오답로그 e", "사용자 제보")
VEC_COMBINING = "⃗"


def _plain_math_text(value):
    """Approximate renderMath(...).textContent for figure-slot geometry checks."""
    text = str(value)
    for macro in ("mathrm", "text"):
        text = re.sub(r"\\" + macro + r"\{([^{}]*)\}", r"\1", text)
    text = text.replace(r"\ ", " ")
    text = re.sub(r"\\[A-Za-z]+", "", text)
    return text.replace("{", "").replace("}", "")
