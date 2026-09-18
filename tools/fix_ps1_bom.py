# -*- coding: utf-8 -*-
r"""한글이 든 `tools/*.ps1` 에 **UTF-8 BOM** 을 붙인다 (내용은 한 글자도 안 바꾼다).

    python tools/fix_ps1_bom.py            # 무엇이 바뀔지만 보여 준다
    python tools/fix_ps1_bom.py --apply

왜 필요한가 (열린 날 2026-08-06, 실사고):
  Windows PowerShell 5.1 은 BOM 이 없으면 `.ps1` 을 **ANSI(cp949)** 로 읽는다.
  UTF-8 한글은 글자당 3바이트인데 cp949 는 2바이트 단위로 끊으므로 **정렬이 어긋나** 어떤
  자리에서는 앞 바이트가 뒤따르는 ASCII 문자(`'`·`"`)를 삼킨다. 그러면 문자열이 안 닫히고
  파서가 죽는다 — 사용자가 본 *[발화 생략]* 가 그것이다.

★ **이것이 잠복형인 것이 이 부류의 핵심이다.** 삼켜지는 자리가 있어야 터지므로, 같은 조건의
  다른 파일(`install_startup.ps1`)은 **우연히 멀쩡히 돌고 있었다.** 즉 "돌아가니까 괜찮다" 가
  근거가 못 된다 — 한 줄만 고쳐도 정렬이 바뀌어 갑자기 죽을 수 있다. 그래서 인스턴스가 아니라
  **부류 전체**(비ASCII 가 든 모든 .ps1)를 한 번에 맞춘다(AGENTS 규칙 7).

★ 손으로 옮겨 적지 않는 이유: 배포 스크립트까지 포함된 파일들이라 전사 오타의 대가가 크다.
  이 도구는 **앞에 3바이트를 붙이기만** 하고 나머지 바이트는 건드리지 않는다.

잠그는 것: `test_checks.py::test_powershell_scripts_have_bom`.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BOM = b"\xef\xbb\xbf"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")


def needs_bom(raw):
    """비ASCII 가 들어 있는데 BOM 이 없으면 True. 순수 함수 — 테스트가 직접 부른다."""
    if raw.startswith(BOM):
        return False
    return any(b >= 0x80 for b in raw)


def main():
    apply_it = "--apply" in sys.argv
    changed = []
    for name in sorted(os.listdir(TOOLS)):
        if not name.lower().endswith(".ps1"):
            continue
        path = os.path.join(TOOLS, name)
        with open(path, "rb") as fh:
            raw = fh.read()
        if not needs_bom(raw):
            continue
        changed.append(name)
        if apply_it:
            with open(path, "wb") as fh:
                fh.write(BOM + raw)
    if not changed:
        print("BOM 이 필요한 .ps1 없음 — 전부 이미 맞다")
        return 0
    print(("[기록] " if apply_it else "[미리보기] ") + "BOM 추가 %d개" % len(changed))
    for name in changed:
        print("   " + name)
    if not apply_it:
        print("\n--apply 를 주면 실제로 쓴다 (내용은 안 바뀌고 앞 3바이트만 붙는다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
