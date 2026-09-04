' 로컬 뷰어 서버 상시 실행용 런처 (창 없이 백그라운드).
'
' pythonw를 쓰면 안 된다: 콘솔이 없어 sys.stderr가 None이 되고,
' http.server가 요청마다 찍는 접속 로그에서 예외가 나 응답 전에 핸들러가 죽는다
' (증상: ERR_EMPTY_RESPONSE). 그래서 일반 python을 쓰되 출력을 로그 파일로 돌리고,
' 창은 WScript.Shell.Run의 windowStyle=0 으로 숨긴다.
'
' ★ 포트는 워크트리 폴더 이름으로 정한다 (2026-07-26 신설).
'   과목 = 브랜치 = worktree 폴더이므로(AGENTS '과목 병렬 작업') 폴더가 곧 과목이다.
'   이 파일은 공통(main 정본)이라 브랜치마다 내용이 달라선 안 되고, 그래서 포트를
'   하드코딩하지 않는다 — 하드코딩하면 두 과목이 같은 8801을 다퉈 한쪽이 안 뜬다.
'       thermo(열역학) -> 8801 · math(공학수학 1) -> 8802 · 그 밖(main 등) -> 8800
'   과목 폴더 이름(한글)으로 판정하지 않는 이유: .vbs는 ANSI로 해석되므로 UTF-8로 저장된
'   한글 문자열 리터럴이 깨져 FolderExists가 늘 False가 된다. 비교 대상은 ASCII라야 안전하다.
'   (그래서 이 파일의 한글은 주석에만 둔다 — tools/test_checks.py가 검사한다.)
'   2026-08-23: 폴더 이름이 «열역학-thermo» 로 바뀌었다(고르는 화면에서 과목이 안 읽혀서).
'   한글이 폴더 이름에 **들어와도** 위 함정은 그대로다 — 그래서 마지막 '-' 뒤 조각만 비교한다.
'   포트를 직접 주려면: wscript serve_site.vbs 8803
'
' 접속: http://localhost:8801/열역학/ch01.html
'       http://localhost:8802/공학수학 1/ch01.html
' 로그: tools\serve_site-<포트>.log   (포트 충돌 등 실패 원인도 여기 남는다)

Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")

toolsDir = fso.GetParentFolderName(WScript.ScriptFullName)
repoDir  = fso.GetParentFolderName(toolsDir)
siteDir  = fso.BuildPath(repoDir, "site")

port = 0
If WScript.Arguments.Count > 0 Then
    If IsNumeric(WScript.Arguments(0)) Then port = CLng(WScript.Arguments(0))
End If

' ★ 폴더 이름은 «<한글표시>-<갈래>» 다 (2026-08-23). 판정은 **마지막 '-' 뒤 ASCII 토큰**으로
'   한다 — 한글 부분은 읽기만 하고 **비교하지 않으므로** 위에 적은 ANSI 함정에 안 걸린다.
'   «열역학-thermo» -> thermo · «main» -> main · 옛 이름 «thermo» 도 그대로 통한다.
'   같은 규칙의 정본은 tools/worktree_names.py (표류는 test_checks.py 가 막는다).
nameParts = Split(fso.GetFileName(repoDir), "-")
branchTag = LCase(nameParts(UBound(nameParts)))

If port = 0 Then
    Select Case branchTag
        Case "thermo"
            port = 8801
        Case "math"
            port = 8802
        Case "dynamics"
            port = 8803
        Case "materials"
            port = 8804
        Case "solids"
            port = 8805
        Case "mfg"
            port = 8806
        Case "fluids"
            port = 8807
        Case "appthermo"
            port = 8808
        Case "appsolids"
            port = 8809
        Case "ee"
            port = 8810
        Case "math2"
            port = 8811
        Case "family"
            port = 8812
        Case "medesign"
            port = 8813
        Case "sysctrl"
            port = 8814
        Case "instru"
            port = 8815
        Case "numeth"
            port = 8816
        Case "heat"
            port = 8817
        Case "appfluid"
            port = 8818
        Case "vib"
            port = 8819
        Case "smartmfg"
            port = 8820
        Case "quality"
            port = 8821
        Case Else
            port = 8800
    End Select
End If

logFile = fso.BuildPath(toolsDir, "serve_site-" & port & ".log")

cmd = "cmd /c python -m http.server " & port & " --directory """ & siteDir & """ >> """ & logFile & """ 2>&1"
sh.Run cmd, 0, False
