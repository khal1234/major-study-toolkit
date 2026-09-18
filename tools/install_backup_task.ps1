# 저장소 백업(tools/backup_bundle.py)을 **매일 자동 실행**되게 Windows 작업 스케줄러에 등록한다.
#
# 왜 만들었나 (2026-08-06, 사용자 지적): *[발화 생략]* — 확인해 보니 **안 걸려 있었다.**
# `backup_bundle.py` 첫 줄에 인용된 원래 요청이 *[발화 생략]* 인데,
# 만들어진 것은 **수동 도구 + close_report 의 알림**뿐이었다. 알림이 있으니 돌아가는 것처럼
# 보였고, 그래서 미이행이 오래 안 드러났다(AGENTS 규칙 7-⑷ — 사람의 성실성에 기대면 안 된다).
#
# ★★ **이 파일은 UTF-8 BOM 으로 저장한다 — 지우지 말 것.**
#   Windows PowerShell 5.1 은 BOM 이 없으면 .ps1 을 **ANSI(cp949)** 로 읽는다. 그러면 한글
#   주석·문자열이 깨져 파서가 따옴표를 못 닫고 `UnexpectedToken` 으로 죽는다
#   (2026-08-06 실사고 — 이 파일이 BOM 없이 저장돼 첫 실행이 통째로 실패했다).
#   AGENTS 「알려진 함정」의 *[발화 생략]* 와
#   같은 부류이고, 잠그는 것은 `test_checks.py::test_powershell_scripts_have_bom` 이다.
#
# ★ 왜 Claude 스케줄 작업이 아니라 **Windows 작업 스케줄러**인가:
#   백업은 채팅 세션이 떠 있는지와 무관하게 돌아야 한다. Claude 쪽 스케줄은 앱이 돌 때만 뜨고
#   토큰도 쓴다 — 파일 백업에는 맞지 않는다.
#
# ★ 무엇이 백업되나 (이 스크립트가 정하지 않는다. `backup_bundle.py` 가 정본):
#   `git bundle --all` 이라 **전 과목·전 브랜치 이력 전체** + 각 워크트리의 `.review-snapshot/`
#   과 `settings.local.json`. **커밋 안 된 작업은 안 들어간다** — 그래서 close_report 의
#   '마지막 백업' 알림은 **그대로 둔다**(자동화가 그 한계를 없애 주지는 않는다).
#
# 사용: powershell -ExecutionPolicy Bypass -File tools\install_backup_task.ps1
#       시각 바꾸기:  ... -File tools\install_backup_task.ps1 -At 20:30
#       제거:        ... -File tools\install_backup_task.ps1 -Uninstall
#
# 작업 이름은 ASCII 로 둔다 — 한글을 섞으면 인코딩이 깨져 알맹이가 빈 항목이 만들어진 전례가
# 있다(2026-07-22, install_startup.ps1 의 그 사고).

param([switch]$Uninstall, [string]$At = '03:30')

$ErrorActionPreference = 'Stop'
$TaskName = 'major-notes-backup'

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "uninstalled: $TaskName"
    } else {
        Write-Host 'nothing to uninstall'
    }
    return
}

$RepoRoot = Split-Path $PSScriptRoot -Parent
$script   = Join-Path $RepoRoot 'tools\backup_bundle.py'
if (-not (Test-Path -LiteralPath $script)) { throw "backup script not found: $script" }

# ★ `python` 을 이름으로 넘기지 않고 **설치 시점에 절대 경로로 굳힌다.**
#   작업 스케줄러는 로그온 셸의 PATH 를 그대로 쓰지 않아, 이름으로 두면 "됐다고 나오는데
#   실제로는 안 도는" 상태가 되기 쉽다 — 백업에서 그건 가장 나쁜 실패 방식이다.
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw 'python 을 PATH 에서 못 찾았다 - 파이썬을 먼저 설치·등록할 것' }

$action  = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $At
# StartWhenAvailable: PC 가 꺼져 있어 지나간 회차는 **다음에 켜질 때** 따라잡는다.
# DontStopIfGoingOnBatteries: 노트북에서 배터리라고 거르지 않는다.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description 'Major-notes repo backup (git bundle --all + review baselines)' | Out-Null

# ★ 등록됐다고 믿지 않고 **되읽어 확인한다** (install_startup.ps1 과 같은 규율 -
#   "Save() 는 실패해도 조용하다"). 여기서도 실패가 조용하면 백업이 없는 채로 몇 주가 간다.
$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $t) { throw 'register FAILED - task not found after register' }
$info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host "task   : $($t.TaskName)  ($($t.State))"
Write-Host "run    : $python `"$script`""
Write-Host "cwd    : $RepoRoot"
Write-Host "daily  : $At   next -> $($info.NextRunTime)"
Write-Host ''
Write-Host 'OK - 이제 지시하지 않아도 매일 돈다. 커밋 안 된 작업은 담기지 않으므로'
Write-Host '     close_report 의 「마지막 백업」 알림은 그대로 유지한다.'
