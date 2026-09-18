' 로컬 뷰어 서버 상시 실행용 런처 (창 없이 백그라운드).
'
' pythonw를 쓰면 안 된다: 콘솔이 없어 sys.stderr가 None이 되고,
' http.server가 요청마다 찍는 접속 로그에서 예외가 나 응답 전에 핸들러가 죽는다
' (증상: ERR_EMPTY_RESPONSE). 그래서 일반 python을 쓰되 출력을 로그 파일로 돌리고,
' 창은 WScript.Shell.Run의 windowStyle=0 으로 숨긴다.
'
' ★ 포트는 하나다 — 8800 (2026-09-06 구조 이전).
'   옛 판(2026-07-26~2026-09-06)은 워크트리 폴더 이름으로 과목마다 다른 포트를 골랐다.
'   근거는 «과목 = 브랜치 = worktree» 였고, 각 워크트리의 site\ 에 자기 과목만 있어서
'   서버 하나로는 다른 과목을 못 냈기 때문이다. 브랜치를 합친 뒤로는 그 이유가 사라졌다.
'   포트를 직접 주려면: wscript serve_site.vbs 8803
'
' 접속: http://localhost:8800/열역학/ch01.html
'       http://localhost:8800/기계공작법/ch10.html
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
' ★★ 포트를 나누던 표를 없앴다 (2026-09-06 구조 이전).
'   나눈 이유는 «과목마다 워크트리가 따로라 그 site\ 에 자기 과목만 있다» 였다 —
'   서버 하나로는 다른 과목 파일을 낼 수가 없었다. 21개 브랜치를 main 하나로 합친 지금은
'   site\ 안에 전 과목이 함께 있어 **서버 하나가 전부 낸다.** 과목 간 링크도 상대경로로
'   그냥 걸린다(포트 치환이 필요 없다).
'   접속: http://localhost:8800/<과목>/chNN.html
If port = 0 Then port = 8800

logFile = fso.BuildPath(toolsDir, "serve_site-" & port & ".log")

cmd = "cmd /c python -m http.server " & port & " --directory """ & siteDir & """ >> """ & logFile & """ 2>&1"
sh.Run cmd, 0, False
