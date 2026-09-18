---
name: powershell-ansi-encoding
description: Use when writing or editing a .ps1 PowerShell script that contains non-ASCII text (Korean, other non-English characters). Windows PowerShell 5.1 reads a BOM-less .ps1 as ANSI, corrupting non-ASCII content.
---

# PowerShell 5.1의 BOM 없는 .ps1 인코딩 함정

출처: XSanity 세션 메모리 이관(2026-09-01) — XSanity와 무관한 순수 Windows/PowerShell
사실.

Windows PowerShell 5.1(기본 내장 버전, PowerShell 7과 다르다)은 **BOM이 없는
`.ps1` 파일을 시스템 기본 ANSI 코드페이지로 읽는다.** 그래서 UTF-8로 저장했는데
BOM을 안 붙이면, 한글 등 비-ASCII 문자가 깨진다.

체크: 지금 쓰거나 고치는 `.ps1`에 한글 등 비-ASCII 문자가 들어가는가? 그렇다면
**UTF-8 BOM**으로 저장한다(순수 ASCII만 있는 스크립트는 해당 없음). PowerShell 7
(`pwsh`)에서만 돌 것이 확실하면 이 문제가 없지만, 실행 환경이 5.1일 가능성이 있으면
BOM을 붙인다.
