[CmdletBinding()]
param(
    [switch]$SkipWeb,
    [switch]$SkipAndroid,
    [switch]$SkipDesktop,
    [switch]$SkipBridge,
    [switch]$SkipUniversalE2E,
    [switch]$SkipDeployPlan,
    [switch]$SkipDockerSupport,
    [switch]$SkipDistributionHygiene,
    [switch]$SkipRealDeviceUX,
    [switch]$AndroidRealDeviceUXPreflight,
    [switch]$GenerateAndroidRealDeviceUXProof,
    [switch]$AndroidRealDeviceUXSigninPassed,
    [switch]$AndroidRealDeviceUXChatPassed,
    [switch]$CaptureAndroidRealDeviceUXScreenshot,
    [switch]$DesktopIncludeUi,
    [switch]$BridgeFull,
    [string]$DeployPlanPath = ".suite\local\aibenchie\deploy-plan.json",
    [string]$RealDeviceUXProofPath = ".suite\local\aibenchie\android-real-device-ux.json",
    [string]$RealDeviceUXArtifactDir = ".suite\local\aibenchie\artifacts",
    [string]$RealDeviceUXAdb = "adb",
    [string]$RealDeviceUXAdbSerial = "",
    [string]$RealDeviceUXPackage = "com.nullxoid.android",
    [string]$RealDeviceUXBaseUrl = "https://api.echolabs.diy/nullxoid",
    [string]$RealDeviceUXRuntimeProvider = "",
    [string]$RealDeviceUXRuntimeModel = "",
    [string]$RealDeviceUXRuntimeEndpointLabel = "",
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
$universalE2EReportPath = [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $resolvedReportPath) "aibenchie_universal_e2e_latest.json"))
$webRepoPath = if (Test-Path -LiteralPath (Join-Path $workspaceRoot ".NullXoid")) {
    Join-Path $workspaceRoot ".NullXoid"
} else {
    Join-Path $workspaceRoot "NullXoid-live"
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
            skip_universal_e2e = [bool]$SkipUniversalE2E
            skip_deploy_plan = [bool]$SkipDeployPlan
            skip_docker_support = [bool]$SkipDockerSupport
            skip_distribution_hygiene = [bool]$SkipDistributionHygiene
            skip_real_device_ux = [bool]$SkipRealDeviceUX
            android_real_device_ux_preflight = [bool]$AndroidRealDeviceUXPreflight
            generate_android_real_device_ux_proof = [bool]$GenerateAndroidRealDeviceUXProof
            capture_android_real_device_ux_screenshot = [bool]$CaptureAndroidRealDeviceUXScreenshot
            desktop_include_ui = [bool]$DesktopIncludeUi
            bridge_full = [bool]$BridgeFull
        }
        surfaces = @($results)
    }

    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resolvedReportPath -Encoding UTF8
}

function Get-RedactedCommandText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string[]]$Arguments = @()
    )

    $parts = @($Command) + @($Arguments)
    $redacted = @()
    $redactNext = $false
    foreach ($part in $parts) {
        if ($redactNext) {
            $redacted += "<redacted>"
            $redactNext = $false
            continue
        }
        $redacted += $part
        if ($part -eq "--real-device-ux-adb-serial") {
            $redactNext = $true
        }
    }
    return $redacted -join " "
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
    $commandText = Get-RedactedCommandText -Command $Command -Arguments $Arguments
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
        -WorkingDirectory $webRepoPath `
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

if (-not $SkipUniversalE2E) {
    Invoke-SuiteGate `
        -Id "aibenchie_universal_e2e" `
        -Name "AIBenchie Universal API/UX E2E" `
        -Owner "AIBenchie" `
        -WorkingDirectory $aibenchieRoot `
        -Command "python" `
        -Arguments @(
            "aibenchie_local.py",
            "--universal-e2e",
            "--universal-e2e-manifest",
            "configs\echolabs_universal_e2e.json",
            "--universal-e2e-lane",
            "all",
            "--universal-e2e-output",
            $universalE2EReportPath,
            "--json"
        )
}

$resolvedDeployPlanPath = if ([System.IO.Path]::IsPathRooted($DeployPlanPath)) {
    [System.IO.Path]::GetFullPath($DeployPlanPath)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $aibenchieRoot $DeployPlanPath))
}

if ((-not $SkipDeployPlan) -and (Test-Path -LiteralPath $resolvedDeployPlanPath)) {
    Invoke-SuiteGate `
        -Id "aibenchie_deploy_plan" `
        -Name "AIBenchie deploy plan proof" `
        -Owner "AIBenchie" `
        -WorkingDirectory $aibenchieRoot `
        -Command "python" `
        -Arguments @(
            "aibenchie_local.py",
            "--verify-deploy-plan",
            "--deploy-plan",
            $resolvedDeployPlanPath,
            "--json"
        )
} elseif (-not $SkipDeployPlan) {
    Write-Host ""
    Write-Host "[echolabs-suite-gate] AIBenchie deploy plan proof skipped (no deploy plan at $resolvedDeployPlanPath)" -ForegroundColor DarkYellow
}

if (-not $SkipDockerSupport) {
    Invoke-SuiteGate `
        -Id "aibenchie_docker_support" `
        -Name "AIBenchie Docker support boundary" `
        -Owner "AIBenchie" `
        -WorkingDirectory $aibenchieRoot `
        -Command "python" `
        -Arguments @(
            "aibenchie_local.py",
            "--docker-support",
            "--json"
        )
}

$resolvedRealDeviceUXProofPath = if ([System.IO.Path]::IsPathRooted($RealDeviceUXProofPath)) {
    [System.IO.Path]::GetFullPath($RealDeviceUXProofPath)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $aibenchieRoot $RealDeviceUXProofPath))
}
$resolvedRealDeviceUXArtifactDir = if ([System.IO.Path]::IsPathRooted($RealDeviceUXArtifactDir)) {
    [System.IO.Path]::GetFullPath($RealDeviceUXArtifactDir)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $aibenchieRoot $RealDeviceUXArtifactDir))
}

if ((-not $SkipRealDeviceUX) -and ($AndroidRealDeviceUXPreflight -or $GenerateAndroidRealDeviceUXProof)) {
    $preflightArgs = @(
        "aibenchie_local.py",
        "--android-real-device-ux-preflight",
        "--real-device-ux-adb",
        $RealDeviceUXAdb,
        "--real-device-ux-package",
        $RealDeviceUXPackage,
        "--json"
    )
    if ($RealDeviceUXAdbSerial) {
        $preflightArgs += "--real-device-ux-adb-serial"
        $preflightArgs += $RealDeviceUXAdbSerial
    }

    Invoke-SuiteGate `
        -Id "aibenchie_android_real_device_ux_preflight" `
        -Name "AIBenchie Android real-device UX preflight" `
        -Owner "AIBenchie" `
        -WorkingDirectory $aibenchieRoot `
        -Command "python" `
        -Arguments $preflightArgs
}

if ((-not $SkipRealDeviceUX) -and $GenerateAndroidRealDeviceUXProof) {
    $androidProofArgs = @(
        "aibenchie_local.py",
        "--emit-android-real-device-ux-proof",
        "--real-device-ux-output",
        $resolvedRealDeviceUXProofPath,
        "--real-device-ux-adb",
        $RealDeviceUXAdb,
        "--real-device-ux-package",
        $RealDeviceUXPackage,
        "--real-device-ux-base-url",
        $RealDeviceUXBaseUrl,
        "--json"
    )
    if ($RealDeviceUXAdbSerial) {
        $androidProofArgs += "--real-device-ux-adb-serial"
        $androidProofArgs += $RealDeviceUXAdbSerial
    }
    if ($AndroidRealDeviceUXSigninPassed) {
        $androidProofArgs += "--real-device-ux-signin-passed"
    }
    if ($AndroidRealDeviceUXChatPassed) {
        $androidProofArgs += "--real-device-ux-chat-passed"
    }
    if ($RealDeviceUXRuntimeProvider) {
        $androidProofArgs += "--real-device-ux-runtime-provider"
        $androidProofArgs += $RealDeviceUXRuntimeProvider
    }
    if ($RealDeviceUXRuntimeModel) {
        $androidProofArgs += "--real-device-ux-runtime-model"
        $androidProofArgs += $RealDeviceUXRuntimeModel
    }
    if ($RealDeviceUXRuntimeEndpointLabel) {
        $androidProofArgs += "--real-device-ux-runtime-endpoint-label"
        $androidProofArgs += $RealDeviceUXRuntimeEndpointLabel
    }
    if ($CaptureAndroidRealDeviceUXScreenshot) {
        $androidProofArgs += "--real-device-ux-capture-screenshot"
        $androidProofArgs += "--real-device-ux-artifact-dir"
        $androidProofArgs += $resolvedRealDeviceUXArtifactDir
    }

    Invoke-SuiteGate `
        -Id "aibenchie_android_real_device_ux_proof_generation" `
        -Name "AIBenchie Android real-device UX proof generation" `
        -Owner "AIBenchie" `
        -WorkingDirectory $aibenchieRoot `
        -Command "python" `
        -Arguments $androidProofArgs
}

if ((-not $SkipRealDeviceUX) -and (Test-Path -LiteralPath $resolvedRealDeviceUXProofPath)) {
    Invoke-SuiteGate `
        -Id "aibenchie_real_device_ux" `
        -Name "AIBenchie real-device UX proof" `
        -Owner "AIBenchie" `
        -WorkingDirectory $aibenchieRoot `
        -Command "python" `
        -Arguments @(
            "aibenchie_local.py",
            "--real-device-ux-proof",
            $resolvedRealDeviceUXProofPath,
            "--json"
        )
} elseif (-not $SkipRealDeviceUX) {
    Write-Host ""
    Write-Host "[echolabs-suite-gate] AIBenchie real-device UX proof skipped (no proof at $resolvedRealDeviceUXProofPath)" -ForegroundColor DarkYellow
}

if (-not $SkipDistributionHygiene) {
    $distributionRoots = @(
        [ordered]@{ Id = "aibenchie_distribution_hygiene"; Name = "AIBenchie distribution hygiene"; Owner = "AIBenchie"; Path = $aibenchieRoot },
        [ordered]@{ Id = "web_distribution_hygiene"; Name = "EchoLabs web distribution hygiene"; Owner = "EchoLabs / NullXoid Chat"; Path = $webRepoPath },
        [ordered]@{ Id = "android_distribution_hygiene"; Name = "NullXoid Android distribution hygiene"; Owner = "NullXoid Android"; Path = (Join-Path $workspaceRoot "NullXoidAndroid") },
        [ordered]@{ Id = "desktop_distribution_hygiene"; Name = "NullXoid Desktop distribution hygiene"; Owner = "NullXoid Desktop / LV7"; Path = (Join-Path $workspaceRoot "AiAssistant") },
        [ordered]@{ Id = "nullbridge_distribution_hygiene"; Name = "BridgeEcho / NullBridge distribution hygiene"; Owner = "BridgeEcho"; Path = (Join-Path $workspaceRoot "NullBridge") },
        [ordered]@{ Id = "lv7_distribution_hygiene"; Name = "Lv-7 distribution hygiene"; Owner = "Lv-7"; Path = (Join-Path $workspaceRoot "Lv-7") }
    )

    foreach ($target in $distributionRoots) {
        if (-not (Test-Path -LiteralPath $target.Path)) {
            Write-Host ""
            Write-Host "[echolabs-suite-gate] $($target.Name) skipped (repo not found at $($target.Path))" -ForegroundColor DarkYellow
            continue
        }
        Invoke-SuiteGate `
            -Id $target.Id `
            -Name $target.Name `
            -Owner $target.Owner `
            -WorkingDirectory $aibenchieRoot `
            -Command "python" `
            -Arguments @(
                "aibenchie_local.py",
                "--distribution-hygiene",
                "--distribution-hygiene-root",
                $target.Path,
                "--json"
            )
    }
}

Write-Host ""
Write-Host "[echolabs-suite-gate] summary" -ForegroundColor Cyan
foreach ($result in $results) {
    Write-Host "- $($result.status) $($result.name) $($result.duration_ms)ms"
}
Write-SuiteGateReport -Verdict "pass"
Write-Host "[echolabs-suite-gate] report $resolvedReportPath" -ForegroundColor Cyan
Write-Host "[echolabs-suite-gate] all checks passed" -ForegroundColor Green
