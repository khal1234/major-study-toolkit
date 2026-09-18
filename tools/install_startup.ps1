# 로컬 서버(tools/serve_site.vbs)를 로그온 시 자동 실행되게 등록한다.
#
# 왜 스크립트 파일인가: 한글 경로를 셸 명령줄로 넘기면 인코딩이 깨져
# 알맹이가 빈 .lnk가 만들어진다(2026-07-22 실사고, 부팅 후 서버가 안 떴다).
# 여기서는 경로를 리터럴로 쓰지 않고 $PSScriptRoot에서 런타임에 얻는다.
#
# ★ 등록 대상은 **리포 하나**다 (2026-09-07 평탄화). 과목 = 브랜치 = worktree 였을 때는
#   과목 수만큼 등록해야 했지만, 한 트리로 합친 뒤에는 서버 하나가 전 과목을 낸다.
#   이름 LocalServer-main · 포트 8800 · 접속 http://localhost:8800/<과목>/chNN.html
#
# 사용: powershell -ExecutionPolicy Bypass -File tools\install_startup.ps1 -All   ← 권장
#       제거는 ... -File tools\install_startup.ps1 -AsTask -All -Uninstall
#
# ★ -All 을 넣은 이유 (2026-07-28, 사용자 지적: *[발화 생략]*).
#   이 스크립트는 **워크트리 하나씩** 등록하는 구조였다. 그래서 과목이 늘 때마다 사람이
#   다시 실행해야 하는데 **아무것도 그것을 알려주지 않았다** — 실측하니 과목 5개 중 2개만
#   등록돼 있었고(dynamics·materials·solids 누락), 8803~8805 는 로그온해도 뜨지 않았다.
#   빠뜨려도 증상이 조용한 부류라(주소를 쳐야 알게 된다) 사람의 성실성에 기대면 안 된다.
#   → `-All` 은 **아래 포트 맵에 있는 과목 전부**를 훑어 현재 상태로 맞춘다(멱등).
#   포트 맵은 `new_subject.py add_startup_port` 가 새 과목 등록 때 자동으로 채운다.

# ★ -AsTask 를 넣은 이유 (2026-08-06, 사용자: *[발화 생략]* → 실측하니 **등록은 5개 다 돼 있었고 지금은 잘 돈다**. 즉 안 뜬 게
#   아니라 **아직** 안 떠 있었다).
#   원인: 시작프로그램 **폴더** 항목은 Explorer 가 데스크톱을 띄운 뒤 **일부러 늦게** 순차
#   실행한다. 그런데 같은 폴더에 `Brave.lnk` 가 있어 브라우저가 이전 탭을 복원하는 시점이
#   파이썬 서버가 포트를 잡는 시점보다 빠를 수 있다 → 그 탭만 ERR_CONNECTION_REFUSED.
#   **사람이 새로고침으로 때우는 것은 조치가 아니다**(매 부팅마다 재발한다).
#   → 작업 스케줄러의 '로그온 시' 트리거는 그 지연을 받지 않는다. 그래서 등록 자리를 옮긴다.
#   ★★ 옮길 때 **폴더 바로가기를 반드시 지운다.** 둘 다 남으면 같은 포트로 두 번 떠서
#      나중 것이 'Address already in use' 로 죽는다 — 로그에만 남고 화면에는 안 보이는
#      부류라, 다음 사람이 '왜 로그에 에러가 있지'로 시간을 쓴다.
#
# 사용: powershell -ExecutionPolicy Bypass -File tools\install_startup.ps1 -AsTask -All   ← 권장
#       되돌리기(작업 삭제):  ... -File tools\install_startup.ps1 -AsTask -All -Uninstall

param([switch]$Uninstall, [switch]$All, [switch]$AsTask, [string]$RepoRoot)

$ErrorActionPreference = 'Stop'
$startup = [Environment]::GetFolderPath('Startup')

# ★★ 포트는 하나다 — 8800 (2026-09-06 구조 이전). 과목마다 워크트리가 따로였을 때는 서버도
#    과목 수만큼 떠야 했고(각 site\ 에 자기 과목만 있었다) 그래서 이 맵이 21줄이었다.
#    브랜치를 main 하나로 합친 뒤에는 **서버 하나가 전 과목을 낸다.**
$PortMap = @{ 'main' = 8800 }
# ★ 'main'(전공정리 홈, 포트 8800)은 애초부터 이 맵에 없었다(2026-09-02 실측 — schtasks 에 홈 항목이
#   0개, 사용자가 [발화 생략]로 지적). 폴더 이름이 «main»(하이픈 없음)이라
#   $tag 도 그대로 'main' 이 되므로, 이 한 줄만 있으면 아래 -All 루프가 다른 과목과 똑같이 찾아낸다 —
#   $All 루프를 손대지 않아도 된다(그 루프는 이미 PortMap 의 키만 보고 도는 구조였다).

# ★★ 훑을 형제가 없다 (2026-09-07 평탄화). 옛 판은 «컨테이너/{main, 열역학-thermo, …}» 를
#    전제로 **저장소 폴더의 형제**를 훑었다. 리포가 컨테이너 자리로 올라오면서 그 부모는
#    `Documents` 가 됐고, PortMap 키 'main' 과 맞는 폴더가 거기 없어 `-All` 이 **등록 0개**로
#    끝났다 — 출력은 «skip: main (워크트리 없음)» 한 줄이라 통과와 구별이 안 됐다.
#    실측(2026-09-07): `LocalServer-main` 이 껍데기만 남은 «…\전공정리프로젝트\main\tools\
#    serve_site.vbs» 를 가리킨 채 Last Result 1(그 폴더엔 `site\` 가 없다), 옛 워크트리
#    20개는 폴더가 사라져 0x8007010B. 로그온해도 8800 이 안 뜬 원인이 **포트가 아니라 경로**다.
#    → 대상은 **이 스크립트가 들어 있는 리포 하나**다. 폴더 이름을 읽지 않으므로 한글 이름
#      («전공정리프로젝트») 도 ANSI 함정·ASCII 뭉개기에 안 걸린다.
if ($All) {
    & $PSCommandPath -RepoRoot (Split-Path $PSScriptRoot -Parent) -AsTask:$AsTask -Uninstall:$Uninstall

    # 옛 구조가 남긴 등록을 걷어낸다. 판정은 **대상 vbs 가 실제로 있는가** 하나다 —
    # 이름을 열거하면 다음 개편 때 또 빠뜨린다(열거는 빠뜨려도 통과되고 접두/실존은 아니다).
    # 남기면 매 로그온마다 조용히 실패하고, 폴더가 되살아나면 8800 을 다투기까지 한다.
    $killed = 0
    foreach ($t in (Get-ScheduledTask -TaskName 'LocalServer-*' -ErrorAction SilentlyContinue)) {
        $target = ($t.Actions[0].Arguments -replace '"', '').Trim()
        if ($target -match '^(.*serve_site\.vbs)') { $target = $matches[1] } else { continue }
        if (Test-Path -LiteralPath $target) { continue }
        Write-Host "removing dead task: $($t.TaskName) -> $target"
        Unregister-ScheduledTask -TaskName $t.TaskName -Confirm:$false
        $killed++
    }
    Write-Host ""
    Write-Host "[all] 죽은 등록 $killed 개 제거 — 로그온하면 http://localhost:8800/ 이 뜬다."
    return
}

if (-not $RepoRoot) { $RepoRoot = Split-Path $PSScriptRoot -Parent }
$RepoRoot = (Resolve-Path $RepoRoot).Path
$vbs      = Join-Path $RepoRoot 'tools\serve_site.vbs'

# ★ 태그를 **폴더 이름에서 뽑지 않는다** (2026-09-07 평탄화).
#   브랜치=워크트리=폴더 였을 때는 폴더 이름이 갈래를 알려 줬다(«열역학-thermo» → thermo).
#   지금은 리포가 하나뿐이고 그 이름이 한글(«전공정리프로젝트») 이라, 옛 규칙을 그대로 돌리면
#   ASCII 뭉개기가 «____________» 을 만들어 **이미 등록돼 있는 이름과 어긋난다.**
#   등록 이름은 밖에 나가 있는 것을 그대로 쓴다 — LocalServer-main · local-server-main.lnk.
$tag = 'main'
$lnk = Join-Path $startup "local-server-$tag.lnk"

# ★★ 포트를 **인자로 넘긴다** (2026-08-23). 런처도 폴더 이름으로 포트를 정할 줄 알지만,
#    그 판정은 각 워크트리가 가진 **자기 사본**이 한다 — 공통이 main 에서 각 갈래로 merge 되기
#    전까지는 옛 사본이 돌고, 새 폴더 이름(«열역학-thermo»)을 못 읽어 전부 8800 으로 떨어진다.
#    실측(폴더를 옮긴 직후): 과목 12개가 한 포트를 다퉈 하나만 뜨고 나머지는 조용히 죽었다.
#    등록하는 쪽은 포트를 이미 알고 있다 — 알고 있는 것을 넘기면 런처 판정에 안 기댄다.
$port = if ($PortMap.ContainsKey($tag.ToLower())) { $PortMap[$tag.ToLower()] } else { 8800 }

$shell = New-Object -ComObject WScript.Shell

# ★ 우리 바로가기만 정리한다. 예전 코드는 '이름이 비ASCII면 무조건 삭제'였는데,
#   그건 남의 바로가기까지 지울 수 있는 과잉 규칙이었다. 여기서는 대상이
#   serve_site.vbs 인 것만 보고, ⑴ 가리키는 파일이 사라진 것(폴더 구조가 바뀌면
#   이렇게 남는다 — 2026-07-26 실사고: 전공정리프로젝트\tools\serve_site.vbs 를 못 찾음)
#   ⑵ 같은 워크트리를 가리키는 예전 고정 이름(thermo-local-server.lnk)만 지운다.
Get-ChildItem $startup -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object {
    $s = $shell.CreateShortcut($_.FullName)
    if ($s.Arguments -notmatch 'serve_site\.vbs') { return }
    # 인자에 포트가 붙어 있다(위 ★★). 경로만 떼어내지 않으면 Test-Path 가 늘 실패해
    # **우리가 방금 만든 바로가기를 우리가 지운다**.
    $target = ($s.Arguments -replace '"', '').Trim()
    if ($target -match '^(.*serve_site\.vbs)') { $target = $matches[1] }
    $stale  = -not (Test-Path -LiteralPath $target)
    if ($stale -or ($_.Name -eq 'thermo-local-server.lnk' -and $target -eq $vbs)) {
        Write-Host "removing stale shortcut: $($_.Name) -> $target"
        Remove-Item $_.FullName -Force
    }
}

# ── 작업 스케줄러 경로 (-AsTask) ──────────────────────────────────────
# 폴더 바로가기와 **같은 일을 하는 두 등록**이므로 반드시 하나만 남긴다(위 ★★ 참조).
$taskName = "LocalServer-$tag"
if ($AsTask) {
    if (Test-Path $lnk) {
        Remove-Item $lnk -Force
        Write-Host "removed startup shortcut: $lnk   (작업으로 옮기므로 폴더 등록은 지운다)"
    }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    if ($Uninstall) { Write-Host "uninstalled task: $taskName"; return }
    if (-not (Test-Path $vbs)) { throw "launcher not found: $vbs" }

    $action  = New-ScheduledTaskAction -Execute (Join-Path $env:SystemRoot 'System32\wscript.exe') `
                                       -Argument ('"' + $vbs + '" ' + $port) -WorkingDirectory $RepoRoot
    # ★ -RandomDelay·-Delay 를 주지 않는다. **지연을 피하는 것이 이 트리거를 쓰는 이유**다.
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    # 서버는 계속 떠 있어야 하므로 실행 시간 제한을 없앤다(기본 3일이면 조용히 죽는다).
    $set     = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                                            -StartWhenAvailable -MultipleInstances IgnoreNew `
                                            -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $set `
        -Description "로컬 뷰어 서버 ($tag, 포트 $port) - tools/serve_site.vbs" | Out-Null

    # 등록됐는지 되읽어 확인한다 (Register 는 실패해도 조용할 수 있다 — .lnk 때와 같은 이유)
    if (-not (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)) {
        throw "task registration FAILED: $taskName"
    }
    Write-Host "task   : $taskName"
    Write-Host "action : wscript.exe ""$vbs"""
    Write-Host "port   : $port"
    Write-Host 'OK (scheduled task)'
    return
}

if ($Uninstall) {
    if (Test-Path $lnk) { Remove-Item $lnk -Force; Write-Host "uninstalled: $lnk" } else { Write-Host 'nothing to uninstall' }
    return
}

if (-not (Test-Path $vbs)) { throw "launcher not found: $vbs" }

$sc = $shell.CreateShortcut($lnk)
$sc.TargetPath       = Join-Path $env:SystemRoot 'System32\wscript.exe'
$sc.Arguments        = '"' + $vbs + '" ' + $port
$sc.WorkingDirectory = $RepoRoot
$sc.WindowStyle      = 7
$sc.Save()

# 저장된 내용을 되읽어 검증한다 (Save()는 실패해도 조용하다)
$v = $shell.CreateShortcut($lnk)
Write-Host "lnk    : $lnk"
Write-Host "target : $($v.TargetPath)"
Write-Host "args   : $($v.Arguments)"
Write-Host "port   : $port"
if (-not $v.TargetPath -or -not $v.Arguments) { throw 'shortcut is empty - install FAILED' }
Write-Host 'OK'
