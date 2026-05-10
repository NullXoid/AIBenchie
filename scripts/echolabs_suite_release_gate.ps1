[CmdletBinding()]
param(
    [switch]$SkipWeb,
    [switch]$SkipAndroid,
    [switch]$SkipDesktop,
    [switch]$SkipBridge,
    [switch]$DesktopIncludeUi,
    [switch]$BridgeFull,
    [string]$ReportPath = "_validation\echolabs_suite_gate_latest.json",
    [string]$SuiteRoot = ""
)

$ErrorActionPreference = "Stop"

$aibenchieRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workspaceRoot = if ($SuiteRoot) {
    (Resolve-Path $SuiteRoot).Path
} elseif (Test-Path -LiteralPath (Join-Path $aibenchieRoot "..\NullXoid-live")) {
    (Resolve-Path (Join-Path $aibenchieRoot "..")).Path
} else {
    $aibenchieRoot
}
$results = [System.Collections.Generic.List[object]]::new()
$startedAt = (Get-Date).ToUniversalTime()
$resolvedReportPath = if ([System.IO.Path]::IsPathRooted($ReportPath)) {
    [System.IO.Path]::GetFullPath($ReportPath)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $workspaceRoot $ReportPath))
}

function Get-SuiteRelativePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,
        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    if ([System.IO.Path].GetMethods() | Where-Object { $_.Name -eq "GetRelativePath" }) {
        return [System.IO.Path]::GetRelativePath($BasePath, $TargetPath)
    }

    $baseUri = [System.Uri](([System.IO.Path]::GetFullPath($BasePath).TrimEnd('\') + '\'))
    $targetUri = [System.Uri]([System.IO.Path]::GetFullPath($TargetPath))
    return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($targetUri).ToString()).Replace('/', '\')
}

function Write-SuiteGateReport {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Verdict,
        [string]$FailedSurface = ""
    )

    $finishedAt = (Get-Date).ToUniversalTime()
    $reportDir = Split-Path -Parent $resolvedReportPath
    if ($reportDir -and -not (Test-Path -LiteralPath $reportDir)) {
        New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
    }

    $report = [ordered]@{
        schema = "echolabs.suite-release-gate.v1"
        verdict = $Verdict
        failed_surface = $FailedSurface
        started_at = $startedAt.ToString("o")
        finished_at = $finishedAt.ToString("o")
        duration_ms = [int]($finishedAt - $startedAt).TotalMilliseconds
        options = [ordered]@{
            skip_web = [bool]$SkipWeb
            skip_android = [bool]$SkipAndroid
            skip_desktop = [bool]$SkipDesktop
            skip_bridge = [bool]$SkipBridge
            desktop_include_ui = [bool]$DesktopIncludeUi
            bridge_full = [bool]$BridgeFull
        }
        surfaces = @($results)
    }

    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resolvedReportPath -Encoding UTF8
}

function Invoke-SuiteGate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Id,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Owner,
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string[]]$Arguments = @()
    )

    Write-Host ""
    Write-Host "[echolabs-suite-gate] $Name" -ForegroundColor Cyan
    $started = Get-Date
    Push-Location $WorkingDirectory
    try {
        & $Command @Arguments
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    $elapsed = [int]((Get-Date) - $started).TotalMilliseconds
    $ok = $exitCode -eq 0
    $commandText = (@($Command) + @($Arguments)) -join " "
    $relativeWorkingDirectory = Get-SuiteRelativePath -BasePath $workspaceRoot -TargetPath $WorkingDirectory
    $results.Add([pscustomobject]@{
        id = $Id
        name = $Name
        owner = $Owner
        status = if ($ok) { "PASS" } else { "FAIL" }
        duration_ms = $elapsed
        command = $commandText
        working_directory = $relativeWorkingDirectory
    }) | Out-Null

    if (-not $ok) {
        Write-Host "[echolabs-suite-gate] FAIL $Name ${elapsed}ms" -ForegroundColor Red
        Write-SuiteGateReport -Verdict "fail" -FailedSurface $Name
        Write-Host ""
        Write-Host "[echolabs-suite-gate] summary" -ForegroundColor Cyan
        foreach ($result in $results) {
            Write-Host "- $($result.status) $($result.name) $($result.duration_ms)ms"
        }
        exit $exitCode
    }

    Write-Host "[echolabs-suite-gate] PASS $Name ${elapsed}ms" -ForegroundColor Green
}

if (-not $SkipWeb) {
    Invoke-SuiteGate `
        -Id "echolabs_web" `
        -Name "EchoLabs web shell" `
        -Owner "EchoLabs / NullXoid Chat" `
        -WorkingDirectory (Join-Path $workspaceRoot "NullXoid-live") `
        -Command "npm" `
        -Arguments @("run", "release:gate")
}

if (-not $SkipAndroid) {
    Invoke-SuiteGate `
        -Id "nullxoid_android" `
        -Name "NullXoid Android" `
        -Owner "NullXoid Android" `
        -WorkingDirectory (Join-Path $workspaceRoot "NullXoidAndroid") `
        -Command ".\scripts\android_release_gate.ps1"
}

if (-not $SkipDesktop) {
    $desktopArgs = @()
    if ($DesktopIncludeUi) {
        $desktopArgs += "-IncludeUi"
    }
    Invoke-SuiteGate `
        -Id "nullxoid_desktop" `
        -Name "NullXoid Desktop" `
        -Owner "NullXoid Desktop / LV7" `
        -WorkingDirectory (Join-Path $workspaceRoot "AiAssistant") `
        -Command ".\scripts\desktop_release_gate.ps1" `
        -Arguments $desktopArgs
}

if (-not $SkipBridge) {
    $bridgeArgs = @()
    if ($BridgeFull) {
        $bridgeArgs += "-Full"
    }
    Invoke-SuiteGate `
        -Id "bridgeecho_nullbridge" `
        -Name "BridgeEcho / NullBridge backend" `
        -Owner "BridgeEcho" `
        -WorkingDirectory (Join-Path $workspaceRoot "NullBridge\backend") `
        -Command ".\scripts\nullbridge_release_gate.ps1" `
        -Arguments $bridgeArgs
}

Write-Host ""
Write-Host "[echolabs-suite-gate] summary" -ForegroundColor Cyan
foreach ($result in $results) {
    Write-Host "- $($result.status) $($result.name) $($result.duration_ms)ms"
}
Write-SuiteGateReport -Verdict "pass"
Write-Host "[echolabs-suite-gate] report $resolvedReportPath" -ForegroundColor Cyan
Write-Host "[echolabs-suite-gate] all checks passed" -ForegroundColor Green
