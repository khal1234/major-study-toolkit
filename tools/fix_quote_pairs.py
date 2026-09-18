# -*- coding: utf-8 -*-
r"""짝 안 맞는 따옴표(«…」·「…»)를 여는 쪽에 맞춰 닫는다 — 빌드 검사 C71 의 처방.

판정은 `checks_content.quote_pair_mismatches` 하나다(두 벌 두면 갈린다).
애매한 자리(인용 안의 인용·떠돌이 닫는 표시일 수 있는 것)는 고치지 않고 목록만 낸다.
순회는 장 JSON 의 모든 문자열 — 화면에 안 나가는 필드(sourceRef 등)도 짝은 맞춘다.
쓰기는 표기 보존 기록기(`write_chapter`)로만 한다.

    python tools/fix_quote_pairs.py                     # 미리보기(전 과목)
    python tools/fix_quote_pairs.py --only=<과목> --apply
"""
import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import audit_content                                                       # noqa: E402
from buildlib.checks_content import quote_pair_mismatches                  # noqa: E402
from buildlib.jsontext import write_chapter                                # noqa: E402


def fix_text(text):
    """(고친 문자열, 고친 수, 애매한 조각 목록). 순수 함수 — 테스트가 부른다."""
    fixed_n, ambiguous = 0, []
    out = text
    for start, end, fixed in sorted(quote_pair_mismatches(text), key=lambda h: -h[0]):
        if fixed is None:
            ambiguous.append(text[max(0, start - 15):end + 15])
            continue
        out = out[:start] + fixed + out[end:]
        fixed_n += 1
    return out, fixed_n, list(reversed(ambiguous))


def _walk(node, trail, stats):
    if isinstance(node, dict):
        for k in list(node):
            v = node[k]
            if isinstance(v, str):
                node[k] = _fix_one(v, trail + "/" + k, stats)
            else:
                _walk(v, trail + "/" + k, stats)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, str):
                node[i] = _fix_one(v, "%s[%d]" % (trail, i), stats)
            else:
                _walk(v, "%s[%d]" % (trail, i), stats)


def _fix_one(text, trail, stats):
    new, n, amb = fix_text(text)
    stats["fixed"] += n
    stats["ambiguous"].extend((trail, a) for a in amb)
    return new


def main(argv):
    apply_it = "--apply" in argv
    only = None
    for a in argv:
        if a.startswith("--only="):
            only = {s.strip() for s in a.split("=", 1)[1].split(",") if s.strip()}
        elif a != "--apply":
            sys.exit("모르는 인자: " + a + " — 쓰는 법은 독스트링")
    total, amb_total, scanned = 0, 0, 0
    for folder in audit_content.subject_dirs():
        subject = os.path.basename(folder)
        if only and subject not in only:
            continue
        scanned += 1
        for name in sorted(n for n in os.listdir(folder) if re.fullmatch(r"ch\d{2}\.json", n)):
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            before = copy.deepcopy(data)
            stats = {"fixed": 0, "ambiguous": []}
            _walk(data, "root", stats)
            for trail, snippet in stats["ambiguous"]:
                print("  [애매] %s %s %s  %r" % (subject, name, trail, snippet))
            amb_total += len(stats["ambiguous"])
            if not stats["fixed"]:
                continue
            total += stats["fixed"]
            print("  %s %s — %d건" % (subject, name, stats["fixed"]))
            if apply_it:
                state, why = write_chapter(path, before, data)
                if state != "written":
                    print("    [%s] %s" % (state, why))
    print("\n고칠 것 %d건 · 애매 %d건 · 훑은 과목 %d개%s"
          % (total, amb_total, scanned, "" if apply_it else " (미리보기 — --apply 로 반영)"))
    return 1 if scanned == 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
