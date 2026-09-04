# 로컬 서버(tools/serve_site.vbs)를 로그온 시 자동 실행되게 등록한다.
#
# 왜 스크립트 파일인가: 한글 경로를 셸 명령줄로 넘기면 인코딩이 깨져
# 알맹이가 빈 .lnk가 만들어진다(2026-07-22 실사고, 부팅 후 서버가 안 떴다).
# 여기서는 경로를 리터럴로 쓰지 않고 $PSScriptRoot에서 런타임에 얻는다.
#
# ★ 워크트리마다 따로 등록한다 (2026-07-26 개편). 과목 = 브랜치 = worktree 폴더라
#   바로가기 이름도 폴더 이름으로 가른다(local-server-<폴더>.lnk).
#   이름이 하나뿐이면 나중에 등록한 과목이 앞 과목을 덮어써 한쪽이 영영 안 뜬다.
#   포트는 serve_site.vbs가 폴더 이름으로 정한다: thermo 8801 · math 8802.
#
# 사용: powershell -ExecutionPolicy Bypass -File tools\install_startup.ps1 -All   ← 권장
#       한 워크트리만: ... -File tools\install_startup.ps1 [-RepoRoot C:\...\전공정리프로젝트\thermo]
#       제거는        ... -File tools\install_startup.ps1 -Uninstall  [-RepoRoot ...]
#
# ★ -All 을 넣은 이유 (2026-07-28, 사용자 지적: *"실행프로그램 목록에 없고 8801~02 만 있는 것 같은데"*).
#   이 스크립트는 **워크트리 하나씩** 등록하는 구조였다. 그래서 과목이 늘 때마다 사람이
#   다시 실행해야 하는데 **아무것도 그것을 알려주지 않았다** — 실측하니 과목 5개 중 2개만
#   등록돼 있었고(dynamics·materials·solids 누락), 8803~8805 는 로그온해도 뜨지 않았다.
#   빠뜨려도 증상이 조용한 부류라(주소를 쳐야 알게 된다) 사람의 성실성에 기대면 안 된다.
#   → `-All` 은 **아래 포트 맵에 있는 과목 전부**를 훑어 현재 상태로 맞춘다(멱등).
#   포트 맵은 `new_subject.py add_startup_port` 가 새 과목 등록 때 자동으로 채운다.

# -AsTask 를 넣은 이유(2026-08-06) — 자동 시작 등록이 실제로 됐는지 확인이 필요했던 사례(등록 자체는 돼 있었고, 아직 안 떠 있던 것뿐이었다).
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

# 표시용 포트 맵 — 실제 판정은 serve_site.vbs 가 한다(두 목록의 표류는 test_checks.py 가 막는다).
$PortMap = @{ 'quality' = 8821; 'smartmfg' = 8820; 'vib' = 8819; 'appfluid' = 8818; 'heat' = 8817; 'numeth' = 8816; 'instru' = 8815; 'sysctrl' = 8814; 'medesign' = 8813; 'family' = 8812; 'math2' = 8811; 'ee' = 8810; 'appsolids' = 8809; 'appthermo' = 8808; 'fluids' = 8807; 'mfg' = 8806; 'thermo' = 8801; 'math' = 8802; 'dynamics' = 8803; 'materials' = 8804; 'solids' = 8805; 'main' = 8800 }
# ★ 'main'(전공정리 홈, 포트 8800)은 애초부터 이 맵에 없었다(2026-09-02 실측 — schtasks 에 홈 항목이
#   0개, 사용자가 "왜 직접 켜야해? 자동 켜지게 했잖아"로 지적). 폴더 이름이 «main»(하이픈 없음)이라
#   $tag 도 그대로 'main' 이 되므로, 이 한 줄만 있으면 아래 -All 루프가 다른 과목과 똑같이 찾아낸다 —
#   $All 루프를 손대지 않아도 된다(그 루프는 이미 PortMap 의 키만 보고 도는 구조였다).

if ($All) {
    # 워크트리는 저장소 폴더의 형제다. git 출력을 파싱하지 않고 파일 시스템으로 찾는다 —
    # 한글 경로가 섞여 있어 git 표준출력 인코딩에 기대면 깨진다(이 리포의 알려진 함정).
    #
    # ★ 폴더 이름을 **짐작하지 않는다** (2026-08-23). 폴더가 «열역학-thermo» 로 바뀌었으므로
    #   `Join-Path $parent 'thermo'` 는 전부 «워크트리 없음» 으로 조용히 빠진다 — 증상이
    #   조용한 부류(2026-07-28 등록 누락과 같은 모양)라 훑어서 찾는다.
    #   갈래는 마지막 '-' 뒤 ASCII 토큰 (정본: tools/worktree_names.py).
    $parent = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    $done = 0
    $seen = @{}
    foreach ($dir in (Get-ChildItem -LiteralPath $parent -Directory | Sort-Object Name)) {
        $tag = ($dir.Name -split '-')[-1].ToLower()
        if (-not $PortMap.ContainsKey($tag)) { continue }
        if ($seen.ContainsKey($tag)) {
            Write-Host "skip   : $($dir.Name) (갈래 $tag 는 이미 등록했다)"
            continue
        }
        if (-not (Test-Path -LiteralPath (Join-Path $dir.FullName 'tools\serve_site.vbs'))) {
            Write-Host "skip   : $($dir.Name) (런처 없음)"
            continue
        }
        $seen[$tag] = $true
        & $PSCommandPath -RepoRoot $dir.FullName -AsTask:$AsTask -Uninstall:$Uninstall
        $done++
    }
    foreach ($name in ($PortMap.Keys | Sort-Object)) {
        if (-not $seen.ContainsKey($name)) { Write-Host "skip   : $name (워크트리 없음)" }
    }
    Write-Host ""
    Write-Host "[all] 등록 완료 $done 개 — 로그온하면 전부 자동 실행된다."
    return
}

if (-not $RepoRoot) { $RepoRoot = Split-Path $PSScriptRoot -Parent }
$RepoRoot = (Resolve-Path $RepoRoot).Path
$vbs      = Join-Path $RepoRoot 'tools\serve_site.vbs'

# 바로가기 이름은 워크트리의 **갈래**로 (ASCII만 — 인코딩 사고 방지).
# 폴더가 «열역학-thermo» 라도 태그는 `thermo` 다. 한글을 '_' 로 뭉개면
# «____-thermo» 같은 이름이 되고, 폴더 표시를 바꿀 때마다 옛 등록이 남는다.
$tag = ((Split-Path $RepoRoot -Leaf) -split '-')[-1] -replace '[^A-Za-z0-9_]', '_'
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
