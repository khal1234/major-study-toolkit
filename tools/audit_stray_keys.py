# -*- coding: utf-8 -*-
"""**아무도 안 읽는 데이터 키** — 이름이 어긋나 통째로 버려진 필드를 찾는다 (열린 날 2026-09-11).

    python tools/audit_stray_keys.py                 # 전 과목
    python tools/audit_stray_keys.py --only=<과목>
    python tools/audit_stray_keys.py --fail-only     # 신고만

★ **왜 열렸나 — 같은 부류 두 번째다.**
  ⑴ 2026-08-07: 유도 단계의 설명을 `text` 가 아니라 `description` 으로 적어 **47개 설명이
     화면에 안 나왔다.** 뷰어는 모르는 키를 조용히 무시한다.
  ⑵ 2026-09-11: 응용열역학 ch07 의 문풀 넷이 「안 그리는 사유」를 `noDiagramReason` 이 아니라
     **`figureAbsenceReason`** 으로 적어 두었다. 글은 성실하게 쓰여 있었는데 **게이트는 그
     네 문항을 「사유 없음」으로 계속 신고**했고, 빌드는 조용했다.

  두 번 다 원인이 같다: **키 이름은 자유라서, 틀려도 흔적이 안 남는다.** 값이 비면 눈에 띄지만
  이름이 어긋나면 아무 데도 안 나타난다.

## 자 — 「이 키를 읽는 코드가 있는가」

키 이름 문자열이 **`tools/**.py` 나 `site/template/*.html` 어디에도 없으면** 그 키는
아무도 안 읽는다. 이름으로 판정하므로 대소문자·오타를 그대로 잡는다.

☐ **이 자가 못 보는 것**(규칙 21)
- **동적으로 읽는 키는 모른다** — 코드가 `obj[name]` 으로 도는 자리에서는 이름이 소스에 없다.
  그래서 게이트가 아니라 **목록**이고, 정당한 것은 아래 `KNOWN_DYNAMIC` 에 사유와 함께 적는다.
- **읽히기는 하는데 뜻이 틀린 키**는 못 본다 — 이름이 맞으면 통과한다.
- SVG 문자열 안의 속성 이름은 키가 아니라 값이라 대상이 아니다.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import audit_content                                                    # noqa: E402

ROOT = os.path.dirname(HERE)

# 읽는 코드가 없어도 정당한 키 — 사유를 함께 적는다(적지 않으면 면제가 아니다).
KNOWN_DYNAMIC = {
    # (지금은 비어 있다 — 첫 실측 뒤에 사람이 채운다)
}


def _source_haystack():
    """키 이름을 찾을 소스 뭉치 — `tools/**.py` + 뷰어 템플릿."""
    parts = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, "tools")):
        for name in files:
            if not name.endswith(".py"):
                continue
            with open(os.path.join(base, name), encoding="utf-8", errors="replace") as fh:
                parts.append(fh.read())
    tpl = os.path.join(ROOT, "site", "template")
    if os.path.isdir(tpl):
        for name in os.listdir(tpl):
            if name.endswith((".html", ".js", ".css")):
                with open(os.path.join(tpl, name), encoding="utf-8", errors="replace") as fh:
                    parts.append(fh.read())
    return "\n".join(parts)


_IDENT = re.compile(r"[A-Za-z][A-Za-z0-9]*$")


def _walk_keys(node, out):
    """**스키마 자리의 키만** 센다 — 자유형 사전(기호 표·정답 표)은 안 내려간다.

    이 리포의 스키마 객체는 **배열의 원소**이거나 루트다(`theory[]`·`practice[]`·
    `diagrams[]`·`blanks[]` …). 반면 `A_1`·`C_{pk}` 처럼 **키 자체가 내용**인 사전이
    곳곳에 있어, 그대로 내려가면 목록이 기호로 뒤덮인다(첫 실측: 신고 900건 중 거의 전부).

    ☐ 못 보는 것: **사전 값으로 놓인 스키마 객체**(`intro`·`motion` 같은 것)의 키는 안 본다.
    """
    if isinstance(node, dict):
        for k, v in node.items():
            if _IDENT.match(k):
                out.setdefault(k, 0)
                out[k] += 1
            if isinstance(v, list):
                _walk_keys(v, out)
    elif isinstance(node, list):
        for v in node:
            if isinstance(v, dict):
                _walk_keys(v, out)
            elif isinstance(v, list):
                _walk_keys(v, out)


def duplicate_keys(text):
    """한 객체에 같은 키가 두 번 — **앞의 것이 조용히 버려진다**. 순수 함수(테스트가 부른다).

    ★ 열린 날 2026-09-11. 문항에 `diagrams` 를 새로 끼웠는데 그 아래에 옛 `"diagrams": []` 가
      남아 있었다. JSON 은 뒤엣것을 쓰므로 **새로 그린 삽화가 통째로 사라졌고**, 빌드도 lint 도
      조용했다(중복 키는 문법 위반이 아니다). 「아무도 안 읽는 키」와 같은 부류 — 값이 비면
      눈에 띄지만 **덮인 값은 아무 흔적도 안 남긴다.**
    """
    found = []

    def hook(pairs):
        seen = set()
        for key, _value in pairs:
            if key in seen:
                found.append(key)
            seen.add(key)
        return dict(pairs)

    json.loads(text, object_pairs_hook=hook)
    return found


def is_stray(key, haystack):
    """이 키를 읽는 코드가 소스 뭉치에 있는가 — 없으면 **아무도 안 읽는다**. 순수 함수."""
    if key in KNOWN_DYNAMIC:
        return False
    if re.search(r"[\"']" + re.escape(key) + r"[\"']", haystack):
        return False
    if re.search(r"\.\s*" + re.escape(key) + r"\b", haystack):         # JS 점 표기
        return False
    return True


def main(argv):
    only = None
    fail_only = False
    for arg in argv[1:]:
        if arg.startswith("--only="):
            only = arg.split("=", 1)[1]
        elif arg == "--fail-only":
            fail_only = True

    haystack = _source_haystack()
    dirs = audit_content.subject_dirs()
    if audit_content.reject_unmatched_only(only, dirs):
        return 2
    seen = {}                       # key -> {subject: {chapter: count}}
    dupes = []
    chapters = 0
    for d in dirs:
        subject = os.path.basename(d)
        if only and only not in subject:
            continue
        for name in sorted(f for f in os.listdir(d) if re.fullmatch(r"ch\d+\.json", f)):
            try:
                with open(os.path.join(d, name), encoding="utf-8") as fh:
                    text = fh.read()
                data = json.loads(text)
            except (OSError, ValueError):
                continue
            chapters += 1
            for key in duplicate_keys(text):
                dupes.append(subject + " " + name[:-5] + " — " + key)
            keys = {}
            _walk_keys(data, keys)
            for k, n in keys.items():
                seen.setdefault(k, {}).setdefault(subject, {})[name[:-5]] = n

    strays = [k for k in sorted(seen) if is_stray(k, haystack)]

    if strays:
        print("[아무도 안 읽는 키] 이름이 어긋나면 값이 통째로 버려진다 — **목록이다**")
        print("   ※ 동적으로 읽는 키는 이 자가 못 본다 — 정당한 것은 KNOWN_DYNAMIC 에 사유와 함께")
        for key in strays:
            where = []
            for subject in sorted(seen[key]):
                chs = ", ".join(sorted(seen[key][subject]))
                where.append(subject + " " + chs)
            print("   " + key + " — " + " · ".join(where))
    elif not fail_only:
        print("[없음] 모든 키를 읽는 코드가 있다")

    if dupes:
        print("[한 객체에 같은 키가 둘] 앞의 값이 조용히 버려진다 — **게이트다**")
        for row in dupes:
            print("   " + row)

    print("합계 — 훑은 장 " + str(chapters) + "개 · 서로 다른 키 " + str(len(seen))
          + "개 · 아무도 안 읽는 키 " + str(len(strays)) + "개 · 중복 키 " + str(len(dupes)) + "건")
    return 1 if dupes else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
