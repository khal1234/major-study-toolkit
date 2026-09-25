# Probe: can this PowerShell see and run the desktop app's claude.exe? (2026-09-24, headless login troubleshooting)
# Measures: PS version, language mode, exe path exists, Get-Command result, `--version` exit code, `auth status`.
# Cannot see: why an interactive shell differs from a spawned one (profile, elevation) - compare two runs by eye.
# The desktop app is an MSIX package: inside the app %APPDATA%\Claude is virtualized, outside it only the
# Packages\Claude_*\LocalCache\Roaming path exists (2026-09-24). Search both.
$exe = @(
    "$env:APPDATA\Claude\claude-code\*\claude.exe",
    "$env:LOCALAPPDATA\Packages\Claude_*\LocalCache\Roaming\Claude\claude-code\*\claude.exe"
) | ForEach-Object { Get-ChildItem $_ -ErrorAction SilentlyContinue } |
    Sort-Object { [version]$_.Directory.Name } | Select-Object -Last 1 -ExpandProperty FullName
Write-Output ("PSVersion      : " + $PSVersionTable.PSVersion)
Write-Output ("LanguageMode   : " + $ExecutionContext.SessionState.LanguageMode)
Write-Output ("ExecutionPolicy: " + (Get-ExecutionPolicy))
Write-Output ("APPDATA        : " + $env:APPDATA)
Write-Output ("exe            : " + $exe)
Write-Output ("Test-Path      : " + (Test-Path $exe))
$cmd = Get-Command $exe -ErrorAction SilentlyContinue
Write-Output ("Get-Command    : " + $(if ($cmd) { $cmd.CommandType } else { "(null)" }))
try {
    $v = & $exe --version 2>&1
    Write-Output ("--version      : " + $v + " (exit " + $LASTEXITCODE + ")")
} catch {
    Write-Output ("--version      : FAILED - " + $_.Exception.Message)
}
try {
    $s = & $exe auth status 2>&1
    Write-Output ("auth status    : " + ($s -join " "))
} catch {
    Write-Output ("auth status    : FAILED - " + $_.Exception.Message)
}
