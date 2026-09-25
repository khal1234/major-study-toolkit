# 헤드리스 회차 하나 — docs/headless-queue.md 맨 위 ☐ 하나를 claude -p 로 돌리고 로그를 outputs/headless/ 에 남긴다.
# 설계 정본 docs/2026-09-24-insights-후속-설계.md §4. UTF-8 BOM 으로 저장한다(PowerShell 5.1 은 BOM 없으면 ANSI 로 읽는다).
# 플래그는 claude 2.1.280 --help 로 확인(2026-09-24). --max-turns 는 그 판에 없어 뺐다 — 회차 상한은 [사람] 판정 대기.
# 못 보는 것: 회차가 성공했는지 — 성공 기준 넷은 사람이 로그·git log·인계.md 로 본다.
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location "C:\Users\<사용자>\Documents\전공정리프로젝트"

# claude 가 PATH 에 없으면 데스크톱 앱이 싣는 판 중 가장 새것을 쓴다(판 폴더 이름이 업데이트마다 바뀐다).
# ★ 앱은 MSIX 패키지라 AppData 가 가상화된다 — 앱이 띄운 프로세스는 %APPDATA%\Claude\... 로 보지만
#   사용자 셸·Task Scheduler 는 그 폴더가 [발화 생략](2026-09-24 실측). 실제 자리는
#   %LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude-code\<판>\claude.exe 이고 둘 다 훑는다.
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) {
    $claude = @(
        "$env:APPDATA\Claude\claude-code\*\claude.exe",
        "$env:LOCALAPPDATA\Packages\Claude_*\LocalCache\Roaming\Claude\claude-code\*\claude.exe"
    ) | ForEach-Object { Get-ChildItem $_ -ErrorAction SilentlyContinue } |
        Sort-Object { [version]$_.Directory.Name } | Select-Object -Last 1 -ExpandProperty FullName
}
if (-not $claude) { throw "claude 실행 파일을 못 찾았다 — PATH · %APPDATA%\Claude\claude-code · %LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude-code" }

New-Item -ItemType Directory -Force "outputs\headless" | Out-Null
$ts = Get-Date -Format yyyyMMdd_HHmm
$prompt = Get-Content "docs\headless-prompt.txt" -Raw -Encoding UTF8

# --permission-prompts none: 승인창이 뜰 자리는 자동 거절한다(훅·설정 편집은 못 하는 것이 맞다).
# vercel 은 allowedTools 에 넣지 않는다(CLAUDE.md 절대 규칙 6).
& $claude -p $prompt --model claude-opus-5-5 --output-format json --permission-prompts none `
    --allowedTools "Read,Grep,Glob,Edit,Write,Bash(python tools/*),Bash(git *)" |
    Out-File "outputs\headless\$ts.json" -Encoding utf8

# claude -p 는 실패해도 exit 0 을 낸다(첫 회차 2026-09-24 실측: OAuth 만료 → is_error:true, exit 0).
# 결과 JSON 의 is_error 를 보고 exit 1 로 뒤집는다 — 스케줄러가 실패를 알 수 있어야 한다.
$log = Get-Content "outputs\headless\$ts.json" -Raw -Encoding UTF8
$res = $null
try { $res = $log | ConvertFrom-Json } catch { }
if (-not $res -or $res.is_error) {
    Write-Output ("[헤드리스] 실패 — " + $(if ($res) { $res.result } else { "결과 JSON 을 못 읽었다" }))
    exit 1
}
Write-Output ("[헤드리스] 끝 — 턴 " + $res.num_turns + " · 로그 outputs\headless\$ts.json")
