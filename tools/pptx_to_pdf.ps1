# PowerPoint 파일을 PDF 로 변환한다 (신설 2026-09-07).
#
#   powershell -ExecutionPolicy Bypass -File tools\pptx_to_pdf.ps1 -InputDir <폴더> -OutputDir <폴더>
#   ... -Only "이름1,이름2"      ← 파일 이름(확장자 포함)을 골라서만
#
# ★ 왜 도구인가 — 강의자료가 pptx 로 오고 태블릿·PDF 뷰어로 읽으려면 매번 변환이 필요하다.
#   `powershell -Command` 인라인은 가드가 막고(실행 규율 2·5), 막아야 하는 것이 맞다 —
#   COM 자동화는 실패하면 백그라운드에 PowerPoint 프로세스를 남기므로 종료 처리가 붙은
#   파일 하나로 두는 편이 안전하다.
#
# ★ **한글 경로는 인자로 받는다.** 이 파일 안에는 비ASCII 문자열 리터럴을 두지 않는다 —
#   Windows PowerShell 5.1 은 BOM 없는 .ps1 을 ANSI 로 읽어 한글을 깨뜨린다(공용 스킬
#   `powershell-ansi-encoding`). 주석의 한글은 판정에 안 쓰이므로 대상이 아니다.
#
# **사람이 판정하는 자리:** 어느 폴더의 무엇을 변환할지. 이 도구는 고르지 않는다.
param(
    [Parameter(Mandatory = $true)][string]$InputDir,
    [Parameter(Mandatory = $true)][string]$OutputDir,
    [string]$Filter = '*.pptx',
    [string]$Only = ''
)
$ErrorActionPreference = 'Stop'
$ppSaveAsPDF = 32

if (-not (Test-Path -LiteralPath $InputDir)) { throw "input folder not found: $InputDir" }
if (-not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    Write-Host "created: $OutputDir"
}

$files = Get-ChildItem -LiteralPath $InputDir -Filter $Filter -File
if ($Only) {
    $want = $Only.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $files = $files | Where-Object { $want -contains $_.Name }
}
if (-not $files) { Write-Host '[no match] 0'; exit 0 }

$app = New-Object -ComObject PowerPoint.Application
$done = 0
try {
    foreach ($f in $files) {
        $out = Join-Path $OutputDir ($f.BaseName + '.pdf')
        Write-Host ("converting : " + $f.Name + "  (" + [math]::Round($f.Length / 1MB, 2) + " MB)")
        # WithWindow = $false 로 창을 띄우지 않는다. ReadOnly 로 원본을 건드리지 않는다.
        $pres = $app.Presentations.Open($f.FullName, $true, $false, $false)
        try {
            $pres.SaveAs($out, $ppSaveAsPDF)
        } finally {
            $pres.Close()
        }
        $size = (Get-Item -LiteralPath $out).Length
        Write-Host ("  -> " + $out + "  (" + [math]::Round($size / 1MB, 2) + " MB)")
        $done++
    }
} finally {
    # ★ 실패해도 반드시 종료한다 — 안 그러면 보이지 않는 POWERPNT 프로세스가 남는다.
    $app.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
}
Write-Host ("[done] " + $done)
