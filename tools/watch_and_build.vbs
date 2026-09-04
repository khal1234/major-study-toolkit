' 템플릿 감시기 상시 실행용 런처 (창 없이 백그라운드) — serve_site.vbs 와 같은 패턴이다.
'
' 열린 이유(2026-09-02, 사용자): "백그라운드로 뜨는건 좀 불편한데 … 실제 작업 진행하는 것만
' 떴음 좋겠는데 저런 감시기같은거 말고". watch_and_build.py 를 Bash 도구의 백그라운드 실행으로
' 띄우면 그 셸이 살아 있는 동안 작업 목록에 계속 걸린다 — 실제로 진행 중인 작업이 아니라
' 상시 인프라인데도 같은 자리에 뜬다. serve_site.vbs 가 이미 로컬 서버를 이 문제 없이 띄우고
' 있으므로(WScript.Shell.Run 의 windowStyle=0·비동기 실행 — 호출한 프로세스와 완전히 분리된다),
' 같은 방식을 감시기에도 그대로 쓴다.
'
' 사용: cscript //nologo tools\watch_and_build.vbs
' 로그: tools\watch_and_build.log (watch_and_build.py 가 이어서 적는다)

Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")

toolsDir = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = fso.BuildPath(toolsDir, "watch_and_build.py")
logFile = fso.BuildPath(toolsDir, "watch_and_build-launch.log")

cmd = "cmd /c python """ & scriptPath & """ >> """ & logFile & """ 2>&1"
sh.Run cmd, 0, False
