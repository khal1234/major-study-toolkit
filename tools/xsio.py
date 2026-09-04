# -*- coding: utf-8 -*-
"""검사기 출력이 **어디서 돌려도 죽지 않게** 한다.

    from xsio import force_utf8
    force_utf8()

왜 이 파일이 생겼나 — 같은 부류가 두 번 났다
--------------------------------------------
윈도에서 파이썬 stdout 이 파이프·리다이렉트로 가면 인코딩이 **cp949** 가 된다.
그러면 한글은 넘어가도 `★` · `—` · `−` 같은 글자에서 `UnicodeEncodeError` 가 나고
**스크립트가 그 자리에서 죽는다.** 판정이 아니라 **판정기가** 죽는 것이다.

1. **2026-08-07** — `verify_workorder.py` 가 `SUPERSEDED` 줄에서 죽어 판정이 안 나왔다.
   그때 **그 파일 하나에만** `reconfigure` 를 넣었다. **부류로 고치지 않았다.**
2. **2026-08-08** — `close_report.py` 를 `> /dev/null` 로 돌리니 **exit 1**.
   새로 만든 게이트 6개가 전부 같은 구멍을 갖고 있었다. 하마터면
   *"다시 돌리니 되네"* 로 넘어갈 뻔했다 — 그 두 번째 실행에는 내가
   `PYTHONIOENCODING=utf-8` 을 붙여 놨었다.

구조적 원인
-----------
**출력이 콘솔로 갈 때만 잘 돌아간다.** 사람이 눈으로 보는 경로에서는 멀쩡하고,
자동화(파이프·리다이렉트·subprocess)에서만 죽는다. 그래서 만들 때는 안 걸리고
**게이트로 쓸 때 걸린다.**

기계적 방지장치
---------------
`test_checks.py` 의 `suite_console` 이 **`close_report.py` 의 `REGISTRY` 에 등록된 모든
스크립트**가 이 보호를 갖고 있는지 검사하고, 실제로 cp949 로 한 번 돌려 본다.
새 검사를 REGISTRY 에 넣으면서 이걸 빠뜨리면 **테스트가 먼저 잡는다.**
"""
from __future__ import annotations

import sys

MARKER = "force_utf8"          # 정적 검사가 찾는 이름
LEGACY = 'reconfigure(encoding="utf-8"'   # 옛 인라인 방식도 인정한다


def force_utf8() -> None:
    """stdout·stderr 를 utf-8 로 고정한다. 못 하면 조용히 넘어간다(판정에 영향 없음)."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")   # type: ignore[union-attr]
        except Exception:
            pass


# ── 삭제는 휴지통으로 (2026-08-12 사용자 지시) ────────────────────────────────
#
# 원본 지적: *"강제 삭제는 좀 그런데 삭제하더라도 휴지통으로 보내야지"*
#
# 계기: `vod_pipeline --sweep` 이 원본 VOD 5.9GB 를 `os.remove` 로 지웠고,
# 휴지통을 안 거쳐 **복구가 불가능**했다. 판독 결과는 살았지만 원본은 사라졌다.
#
# **되돌릴 수 있게 만드는 것이 초록의 조건이다**(CLAUDE.md 1절). 휴지통을 거치면
# 삭제가 되돌릴 수 있는 일이 되므로, 못 되돌리는 자료를 지우는 자리는 전부 이걸 쓴다.
# 캐시(`Cache/Songs` 등 재생성되는 것)는 그냥 `os.remove` 로 둬도 된다 — 구별해서 쓴다.
#
# 의존성을 안 늘리려고 윈도우 셸 API 를 ctypes 로 직접 부른다(send2trash 불필요).

def trash(path: str) -> bool:
    """파일·폴더를 **휴지통으로** 보낸다. 성공하면 True.

    윈도우가 아니거나 API 가 실패하면 **지우지 않고 False** 를 돌려준다 —
    「휴지통이 안 되니 그냥 지운다」는 이 함수가 하지 않는다. 그 판단은 부르는 쪽 몫이다.
    """
    import os as _os
    import sys as _sys

    if not _os.path.exists(path):
        return False
    if _sys.platform != "win32":
        return False

    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND),
                    ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR),
                    ("fFlags", ctypes.c_uint16),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p),
                    ("lpszProgressTitle", wintypes.LPCWSTR)]

    FO_DELETE = 3
    FOF_ALLOWUNDO = 0x0040          # ← 이것이 「휴지통으로」
    FOF_NOCONFIRMATION = 0x0010
    FOF_SILENT = 0x0004
    FOF_NOERRORUI = 0x0400

    op = SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = _os.path.abspath(path) + chr(0) * 2      # 이중 널 종료가 규약이다
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return rc == 0 and not _os.path.exists(path)
