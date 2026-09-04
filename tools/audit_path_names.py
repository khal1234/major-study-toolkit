# -*- coding: utf-8 -*-
"""**파일 이름**이 다른 OS 로 건너갈 때 깨지는지 훑는다 (읽기 전용).

    python tools/audit_path_names.py             # 이 리포의 git 추적 파일
    python tools/audit_path_names.py <폴더>       # 그 폴더의 모든 파일(공용 시스템 폴더 등)

왜 (2026-08-12) — 내 컴퓨터에서 잘 보이는 파일이 다른 컴퓨터에서도 같은 모양으로 보인다는 뜻은 아니라는 문제의식.
가져왔다 — 새 툴체인을 까는 비용이 이 검사의 값어치보다 크다.

**우리에게 실제로 닥치는 자리:** 공용 시스템 폴더를 공개하면 폴더 이름이 전부 한글이다
(`규칙/`·`훅/`·`도구/`·`기록/`). 한글은 **NFC 와 NFD 두 방식**으로 저장될 수 있고 화면에는
똑같이 보인다 — macOS 는 NFD 를 쓰므로, 그쪽에서 만든 커밋이 섞이면 **같아 보이는 두 폴더**가
생기고 Windows 에서 체크아웃이 깨진다. 파일 **내용**이 아니라 **이름** 때문에 터지는 부류라
지금까지 어떤 검사도 안 보고 있었다.

## 네 가지를 본다

  ⑴ **대소문자 충돌** — `Foo.md` 와 `foo.md`. Windows·macOS 기본 파일시스템은 둘을 같은
     이름으로 보므로 clone 하는 순간 하나가 사라진다.
  ⑵ **유니코드 정규화 충돌** — NFC 와 NFD 가 섞여 화면상 같은 이름이 둘이 된다.
  ⑶ **Windows 가 못 쓰는 이름** — `CON`·`PRN`·`NUL`·`COM1`… , 끝의 점·공백, `<>:"|?*`.
  ⑷ **보이지 않는 문자** — 폭 없는 공백·글자 방향 제어 문자. 눈으로는 절대 못 찾는다.

★ **자동으로 고치지 않는다.** 이름을 바꾸는 것은 링크·빌드 산출물·문서 참조를 함께 흔든다 —
  무엇을 어떻게 바꿀지는 사람이 정한다(원본 CLI 도 같은 판정을 했다).
"""
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
RESERVED = {"CON", "PRN", "AUX", "NUL", *("COM%d" % i for i in range(1, 10)),
            *("LPT%d" % i for i in range(1, 10))}
BAD_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
# 폭 없는 공백·BOM·글자 방향 제어. 이름에 섞이면 눈으로는 못 찾는다.
INVISIBLE = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")


def tracked_paths(root):
    """git 이 추적하는 경로. git 이 없거나 리포가 아니면 파일시스템을 훑는다."""
    try:
        # ★ `-z` 가 없으면 git 이 **비ASCII 경로를 따옴표로 감싸고 8진수로 escape** 한다
        #   (`core.quotepath` 기본값). 그러면 우리 경로가 전부 `"data/\354\227\264…"` 로 와서
        #   **따옴표 때문에 'Windows 금지 문자' 250건**이 뜬다 — 첫 실행에서 실제로 그랬다.
        #   자가 틀린 것이지 데이터가 틀린 게 아니었다.
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return [p for p in out.stdout.split("\0") if p.strip()]
    except Exception:
        pass
    return [p.relative_to(root).as_posix() for p in sorted(root.rglob("*"))
            if p.is_file() and ".git" not in p.parts]


def issues(paths):
    """[(부류, 설명)]. 순수 함수 — 테스트가 직접 부른다."""
    out = []
    by_lower = defaultdict(list)
    by_nfc = defaultdict(list)
    for p in paths:
        by_lower[p.lower()].append(p)
        by_nfc[unicodedata.normalize("NFC", p)].append(p)
    for key, group in sorted(by_lower.items()):
        if len(set(group)) > 1:
            out.append(("대소문자 충돌", " ↔ ".join(sorted(set(group)))))
    for key, group in sorted(by_nfc.items()):
        # 같은 NFC 인데 **원문 바이트가 다르면** 정규화가 섞인 것이다.
        if len(set(group)) > 1:
            out.append(("유니코드 정규화 충돌(NFC/NFD)", " ↔ ".join(sorted(set(group)))))
    for p in paths:
        for seg in p.split("/"):
            if not seg:
                continue
            stem = seg.split(".")[0].upper()
            if stem in RESERVED:
                out.append(("Windows 예약 이름", p))
            elif seg != seg.rstrip(" ."):
                out.append(("끝에 점·공백", p))
            elif BAD_CHARS.search(seg):
                out.append(("Windows 금지 문자", p))
            elif INVISIBLE.search(seg):
                out.append(("보이지 않는 문자", p))
    return out


def selftest():
    bad = 0

    def chk(desc, cond, got=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %-46s %s" % ("OK  " if cond else "**틀림**", desc, got))

    chk("양성 — 대소문자 충돌을 잡는다",
        any(k == "대소문자 충돌" for k, _ in issues(["a/Foo.md", "a/foo.md"])))
    chk("양성 — NFC/NFD 정규화 충돌을 잡는다",
        any(k == "유니코드 정규화 충돌(NFC/NFD)" for k, _ in
            issues(["a/가.md", "a/가.md"])))
    chk("양성 — Windows 예약 이름을 잡는다",
        any(k == "Windows 예약 이름" for k, _ in issues(["a/CON.txt"])))
    chk("양성 — 끝에 점·공백을 잡는다",
        any(k == "끝에 점·공백" for k, _ in issues(["a/foo. "])))
    chk("양성 — Windows 금지 문자를 잡는다",
        any(k == "Windows 금지 문자" for k, _ in issues(["a/f<o>o.md"])))
    chk("음성 — 정상 경로는 0건",
        issues(["규칙/커밋-푸시-규약.md", "도구/audit_path_names.py"]) == [])

    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        return selftest()
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO
    paths = tracked_paths(root)
    found = issues(paths)
    for kind, detail in found:
        print("  %-26s %s" % (kind, detail))
    print("경로 %d개 검사 — %d건%s" % (len(paths), len(found),
                                   "  — 다른 OS 로 건너가도 안전하다" if not found else ""))
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
