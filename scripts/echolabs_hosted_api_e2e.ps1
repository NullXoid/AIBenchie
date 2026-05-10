[CmdletBinding()]
param(
    [string]$BackendUrl = "https://api.echolabs.diy/nullxoid",
    [string]$ReportPath = "_validation\aibenchie_hosted_api_e2e_latest.json"
)

$ErrorActionPreference = "Stop"

$aibenchieRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workspaceRoot = if (Test-Path -LiteralPath (Join-Path $aibenchieRoot "..\NullXoid-live")) {
    (Resolve-Path (Join-Path $aibenchieRoot "..")).Path
} else {
    $aibenchieRoot
}
$resolvedReportPath = if ([System.IO.Path]::IsPathRooted($ReportPath)) {
    [System.IO.Path]::GetFullPath($ReportPath)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $workspaceRoot $ReportPath))
}

$reportDir = Split-Path -Parent $resolvedReportPath
if ($reportDir -and -not (Test-Path -LiteralPath $reportDir)) {
    New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
}

$previousBackendUrl = $env:AIBENCHIE_BACKEND_URL
$env:AIBENCHIE_BACKEND_URL = $BackendUrl
try {
    Push-Location $aibenchieRoot
    try {
        python aibenchie_local.py `
            --universal-e2e `
            --universal-e2e-manifest configs\echolabs_universal_e2e.json `
            --universal-e2e-lane api `
            --universal-e2e-output $resolvedReportPath `
            --json
        exit $LASTEXITCODE
    } finally {
        Pop-Location
    }
} finally {
    if ($null -eq $previousBackendUrl) {
        Remove-Item Env:\AIBENCHIE_BACKEND_URL -ErrorAction SilentlyContinue
    } else {
        $env:AIBENCHIE_BACKEND_URL = $previousBackendUrl
    }
}
