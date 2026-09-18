# -*- coding: utf-8 -*-
r"""본문이 **화면 배치를 말로 가리키는** 자리를 이름으로 바꾸거나 지운다.

    python tools/fix_screen_deixis.py                      # 미리보기
    python tools/fix_screen_deixis.py --apply
    python tools/fix_screen_deixis.py --only=<과목폴더>
    python tools/fix_screen_deixis.py --skip=data/<과목>/ch01.json --apply

열린 날 **2026-07-27**(공용 폴더 원장), 닫은 날 2026-09-09. 지적은 *[발화 생략]* 였고 부류로 «레이아웃이 바뀌면 즉시 틀리는
서술»이라 적혔는데, **재는 자도 고치는 자도 없어 44일간 [대기]** 였다. 그 사이 새 콘텐츠가
같은 문장을 계속 만들었다(2026-09-09 사용자: *[발화 생략]*).

찾는 자는 `audit_convention_drift.py --check=screen-deixis` 이고 **판정선의 정본은 그 파일의
블록 주석**이다. 여기는 처방만 둔다 — 판정 로직을 두 벌 두면 갈린다.

처방은 둘뿐이다(사용자 판정 2026-09-09):
  ⑴ 그 문장이 **정보를 안 주면 통째로 지운다** — `유도는 아래 카드에 있습니다.` 는 뷰어에
     유도 탭이 **언제나** 있으므로 한 글자도 알려 주지 않는다.
  ⑵ 정보를 주면 **이름으로 바꾼다** — `아래 유도 카드에서` → `유도 카드에서`.

★ **이 자가 안 건드리는 것:** 「같은 문단 바로 옆 블록」을 가리키는 `위 식`·`아래 표` 류.
  그것은 한 흐름 안이라 순서가 안 바뀌고, 찾는 자도 `[판정 필요]` 로만 낸다 — 기계가
  판정할 자리가 아니다. `svg` 안 글자도 안 본다(그림 안 좌표는 안 바뀐다).

☐ **사람이 봐야 하는 것:** 지운 문장이 **문단의 유일한 다리**였는지. 그래서 기본이
  미리보기이고 `--apply` 뒤에는 `git diff` 를 눈으로 본다.
"""
import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_content  # noqa: E402
from buildlib.jsontext import write_chapter  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 위치어 — 찾는 자의 `SD_SPATIAL` 에 순서말 둘을 더한 것이다. 이 자는 **고치는 꼴**만
# 다루므로 목록이 더 짧다(예: `우측`·`좌측`은 실측 0건이라 처방 대상이 아니다).
#
# ★ 앞에 `(?<![가-힣])` 가 **반드시** 있어야 한다 — 없으면 「그**다음 카드**」의 `다음` 만
#   잘라 `그유도 카드` 라는 없는 말을 만든다(설계 중에 실제로 만들었다). 낱말 한가운데를
#   자르는 이 사고는 찾는 자에서도 `왼쪽 절반` 으로 한 번 났다 — 같은 부류다.
_POS = r"(?<![가-힣])(?:바로\s*)?(?:아래|아랫|밑|다음|위의|위|윗|왼쪽|오른쪽)\s*(?:쪽\s*)?"

RULES = [
    # ⑴ 정보를 안 주는 순수 지시 문장 — 통째로 지운다.
    #    앞의 `[^.\n]{0,60}` 은 **그 문장의 앞머리**다(마침표·줄바꿈을 못 넘으므로 앞
    #    문장을 먹지 않는다). 뒤의 `[ ]*` 만 먹고 줄바꿈은 남긴다 — 문단 경계를 지우면
    #    삽화·수식 블록이 앞 문단에 달라붙는다.
    (re.compile(r"[^.\n]{0,60}유도는\s*" + _POS + r"카드에\s*있습니다\.[ ]*"), ""),
    (re.compile(r"[^.\n]{0,60}유도는\s*" + _POS + r"카드에\s*있고,\s*"), ""),
    # ⑵ 이름으로 바꾼다. 긴 꼴을 먼저 둔다 — `아래 유도 카드` 가 `아래 유도` 로 먼저
    #    걸리면 `유도 카드` 가 `유도  카드` 로 갈라진다.
    (re.compile(r"(?:유도는\s*)?" + _POS + r"카드\s*참고"), "유도 카드 참고"),
    (re.compile(_POS + r"유도\s*카드"), "유도 카드"),
    (re.compile(_POS + r"카드"), "유도 카드"),
    (re.compile(_POS + r"유도(?!\s*카드)"), "유도"),
    # ★ `영역`·`화면`·`패널` 은 **처방 대상이 아니다** — 찾는 자는 후보로 내지만
    #   이 자는 못 고친다. 실측 오탐: *[발화 생략]* — 선도 위의 **물리적 영역**이다. 고치면 뜻이 사라진다.
    #   찾는 자는 후보만 내니 오탐이 비용이 아니지만, 고치는 자의 오탐은 **훼손**이다.
    (re.compile(_POS + r"(그림|삽화|문풀|연습문제|탭)"), r"\1"),
    # ⑶ 바꾼 뒤 생기는 겹말만 다듬는다 — 「유도 카드에서 유도합니다」.
    (re.compile(r"유도 카드에서\s*유도합니다"), "유도 카드에서 세웁니다"),
]

# 삽화 안 글자와 저자 전용 필드는 안 본다(찾는 자의 `SD_SKIP_KEYS` 와 같은 뜻).
SKIP_KEYS = {"svg", "sourceRef", "rationale", "changeNote", "source", "reviewNote", "id"}


def convert(text):
    """산문 한 줄을 고친 결과. 순수 함수 — 테스트가 직접 부른다.

    ★ **문자열을 통째로 비우지 않는다.** 지시 문장 하나만 들어 있던 필드를 빈 문자열로
      만들면 빌드 검사가 아니라 **화면**이 깨진다. 그런 자리는 사람이 판정하도록 그냥 둔다.
    """
    if not isinstance(text, str) or "<svg" in text:
        return text
    out = text
    for rx, rep in RULES:
        out = rx.sub(rep, out)
    if out == text:
        return text
    out = re.sub(r"[ ]{2,}", " ", out)
    out = re.sub(r"[ ]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = out.lstrip(" ")
    return text if not out.strip() else out


def walk(node, key=None):
    """(고친 노드, 바꾼 문자열 수). `SKIP_KEYS` 아래로는 안 내려간다."""
    if isinstance(node, dict):
        n = 0
        for k, v in node.items():
            if k in SKIP_KEYS:
                continue
            node[k], c = walk(v, k)
            n += c
        return node, n
    if isinstance(node, list):
        n = 0
        for i, v in enumerate(node):
            node[i], c = walk(v, key)
            n += c
        return node, n
    if isinstance(node, str):
        new = convert(node)
        return new, (1 if new != node else 0)
    return node, 0


def main():
    ap = argparse.ArgumentParser(description="화면 배치를 가리키는 서술을 이름으로 바꾼다")
    ap.add_argument("--only", help="과목 폴더 이름 (data/ 아래 이름 그대로, 쉼표로 여럿)")
    ap.add_argument("--skip", default="",
                    help="건드리지 않을 챕터 경로 (쉼표로 여럿) — 다른 세션이 편집 중인 파일")
    ap.add_argument("--apply", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    only = {s.strip() for s in (args.only or "").split(",") if s.strip()}
    skip = {os.path.normcase(os.path.abspath(s.strip()))
            for s in args.skip.split(",") if s.strip()}

    print("처방 — ⑴ 정보 없는 지시 문장은 지운다 ⑵ 나머지는 이름으로 바꾼다")
    print("찾는 자 `audit_convention_drift.py --check=screen-deixis` 가 판정선의 정본이다\n")
    total, files, skipped = 0, 0, 0
    for folder in audit_content.subject_dirs():
        subject = os.path.basename(folder)
        if only and subject not in only:
            continue
        for name in sorted(n for n in os.listdir(folder)
                           if re.fullmatch(r"ch\d{2}\.json", n)):
            path = os.path.join(folder, name)
            if os.path.normcase(os.path.abspath(path)) in skip:
                skipped += 1
                print("  [건너뜀] %s %s — 다른 세션 몫" % (subject, name))
                continue
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("placeholder") is True:
                continue
            before = copy.deepcopy(data)
            data, n = walk(data)
            if not n:
                continue
            total += n
            files += 1
            print("  %-28s %-8s 문자열 %d개" % (subject, name, n))
            if args.apply:
                state, why = write_chapter(path, before, data)
                print("     [%s] %s" % (state, why or name))
    print("\n문자열 %d개 · 파일 %d개 · 건너뛴 파일 %d개%s"
          % (total, files, skipped,
             "" if args.apply else "  (미리보기 — --apply 로 반영)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
