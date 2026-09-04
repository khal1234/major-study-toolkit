# -*- coding: utf-8 -*-
"""`tools/fix_*.py` 중 **빌드 lint도, `audit_convention_drift.py` 등록도 없는 것**을 센다.

    python tools/audit_fix_tool_coverage.py

열린 날 2026-08-29(같은 날 두 번째 도구). 원인 — 사용자 질문 [사용자 발화 인용 생략].

AGENTS 규칙 7 은 이미 [사용자 발화 인용 생략]고
적어 뒀지만 **그 규칙 자체를 지켰는지 재는 자가 없었다** — 글로 적은 규칙은 다음 세션이
기억하지 못하면 그냥 없는 것과 같다(AGENTS 실행 규율 17 "적어두는 것은 방지장치가 아니다").
실측(2026-08-29 전수 조사, `fix_*.py` 30개 중 인프라 도구 2개를 뺀 28개): 빌드
lint(`checks_content.py`·`checks_svg.py`)나 `audit_convention_drift.py` 어디에도 이름이
없는 것이 최소 7개 나왔다 — `fix_caption_block_gap`·`fix_dimension_lines`·
`fix_figure_label_gap`·`fix_figure_vertical_balance`·`fix_given_chip`·`fix_notation_split`·
`fix_polygon_to_path`. `fix_rate_dot` 은 같은 날 먼저 찾아 `audit_convention_drift.py` 에
등록해 이 목록에서 이미 빠졌다.

★ **이 도구는 판정하지 않는다.** "커버리지가 없다"가 곧 결함은 아니다 — 일부는 생성기가
애초에 규격대로만 찍어내 손으로 어길 방법이 없을 수 있고(그런 도구는 아래 `EXEMPT` 에
사유와 함께 올린다), 일부는 정말 드리프트 체크가 필요하다. 사람이 하나씩 본다.

★ **`git show`가 아니라 소스 파일을 직접 읽는다** — 이 도구가 재는 것은 콘텐츠가 아니라
**도구 등록부 자체의 정합성**이라 과목 데이터를 볼 필요가 없다(공용 코드는 main 워크트리
하나에만 있다).

새 `fix_*.py`를 만들 때: 이 도구가 그 도구를 "미확인"으로 찍으면, ⑴ 빌드 lint에 검사를
새로 넣거나 ⑵ `audit_convention_drift.py`에 드리프트 체크를 등록하거나 ⑶ 정말 필요 없으면
`EXEMPT`에 사유를 적는다. 셋 중 하나 없이 그냥 두지 않는다(AGENTS 규칙 7 「⑵⑶ 동시 신설」
의 기계 확인판).
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDLIB_DIR = os.path.join(TOOLS_DIR, "buildlib")

# 콘텐츠 표기·규격과 무관한 인프라 도구 — 애초에 대상이 아니다.
EXEMPT = {
    "fix_ps1_bom.py": "PowerShell 스크립트의 BOM 처리 — 콘텐츠 규격과 무관한 인프라 도구다",
    "fix_worktree_config.py": "워크트리 설정 파일 처리 — 콘텐츠 규격과 무관한 인프라 도구다",
}

# 파일명과 lint 검사 키 이름이 다른 경우 — 자동 유추(접미사 s 제거 등)로 못 잡는 것만 손으로 짝짓는다.
KEY_ALIAS = {
    "fix_numeric_product.py": "comma_product",
    "fix_symbol_product.py": "symbol_middot",
}


def fix_tool_names():
    return sorted(
        f for f in os.listdir(TOOLS_DIR)
        if f.startswith("fix_") and f.endswith(".py")
    )


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def buildlib_mentions(name):
    """checks_content.py·checks_svg.py 어디에든 이 도구 이름이 나오는가.

    ★ 파일명 그대로("fix_X.py")뿐 아니라 **그 도구가 처방하는 규칙의 키 이름**도 본다 —
    예를 들어 `fix_latex_brace_args.py` 는 소스에 그 파일명을 안 적고 `"latex_brace_arg"`
    라는 strictChapters 키로만 등록돼 있다. 파일명만 보면 이미 잠긴 규칙을 «미확인»으로
    오판한다(2026-08-29 첫 실행에서 4건이 이렇게 오탐이었다 — latex_brace_arg·comma_product
    ·symbol_middot·term_pairing).
    """
    for fn in ("checks_content.py", "checks_svg.py"):
        path = os.path.join(BUILDLIB_DIR, fn)
        if not os.path.isfile(path):
            continue
        text = read(path)
        if name in text:
            return fn
        key = KEY_ALIAS.get(name) or name[len("fix_"):-len(".py")]
        for candidate in (key, key.rstrip("s")):
            if '"' + candidate + '"' in text:
                return fn + " (규칙 키 " + candidate + ")"
    return None


def drift_registered(name):
    """audit_convention_drift.py 의 등록부(또는 그 근처 주석)에 이 도구가 있는가."""
    path = os.path.join(TOOLS_DIR, "audit_convention_drift.py")
    if not os.path.isfile(path):
        return False
    return name in read(path)


def main():
    unresolved = []
    for name in fix_tool_names():
        if name in EXEMPT:
            continue
        if buildlib_mentions(name):
            continue
        if drift_registered(name):
            continue
        unresolved.append(name)

    print("fix_*.py 커버리지 감사 — 빌드 lint 도 `audit_convention_drift.py` 등록도 없는 도구")
    print("(판정은 사람이 한다 — 이 자는 후보만 낸다)\n")

    if not unresolved:
        print("미확인 0건 — 등록된 fix_*.py 전부가 빌드 lint 나 드리프트 체크 중 하나를 갖고 있다.")
        return 0

    print("미확인 %d건:" % len(unresolved))
    for name in unresolved:
        print("  " + name)
    print("\n각각에 대해: ⑴ 빌드 lint 신설 ⑵ audit_convention_drift.py 드리프트 체크 등록 "
          "⑶ 정말 불필요하면 이 파일의 EXEMPT 에 사유와 함께 추가 — 셋 중 하나를 한다.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
