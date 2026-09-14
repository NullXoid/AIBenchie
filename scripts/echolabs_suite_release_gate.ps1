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
    [string]$SuiteRoot = "",
    [string]$WebRepository = "",
    [string]$AndroidRepository = "",
    [string]$DesktopRepository = "",
    [string]$BridgeRepository = "",
    [string]$Lv7Repository = ""
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
$webRepoCandidates = @(
    (Join-Path $workspaceRoot ".NullXoid"),
    (Join-Path $workspaceRoot "NullXoid-live")
)
$existingWebRepos = @($webRepoCandidates |
    Where-Object { Test-Path -LiteralPath (Join-Path $_ "package.json") } |
    Select-Object -Unique)
function Resolve-RepositoryInput {
    param([string]$ExplicitPath, [string]$DefaultPath)
    $selected = if ($ExplicitPath) { $ExplicitPath } else { $DefaultPath }
    if (-not [System.IO.Path]::IsPathRooted($selected)) {
        $selected = Join-Path $workspaceRoot $selected
    }
    return [System.IO.Path]::GetFullPath($selected)
}
$webDefault = if ($existingWebRepos.Count -eq 1) { $existingWebRepos[0] } else { Join-Path $workspaceRoot "NullXoid-live" }
$webRepoPath = Resolve-RepositoryInput $WebRepository $webDefault
$androidRepoPath = Resolve-RepositoryInput $AndroidRepository (Join-Path $workspaceRoot "NullXoidAndroid")
$desktopRepoPath = Resolve-RepositoryInput $DesktopRepository (Join-Path $workspaceRoot "AiAssistant")
$bridgeRepoPath = Resolve-RepositoryInput $BridgeRepository (Join-Path $workspaceRoot "NullBridge")
$lv7RepoPath = Resolve-RepositoryInput $Lv7Repository (Join-Path $workspaceRoot "Lv-7")

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
        coverage_complete = $Verdict -eq "pass"
        deployment_authorized = $false
        scope = "Selected gate execution only; requires pinned artifacts, current evidence and deployment authorization."
        repositories = [ordered]@{
            web = $webRepoPath
            android = $androidRepoPath
            desktop = $desktopRepoPath
            bridge = $bridgeRepoPath
            lv7 = $lv7RepoPath
            aibenchie = $aibenchieRoot
        }
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

function Add-UnfinishedGate {
    param([string]$Id, [string]$Status, [string]$Reason)
    $results.Add([pscustomobject]@{
        id = $Id
        name = $Id
        owner = "suite release"
        status = $Status
        reason = $Reason
        duration_ms = 0
    }) | Out-Null
}

function Stop-MissingPrerequisite {
    param([string]$Id, [string]$Reason)
    Add-UnfinishedGate $Id "BLOCKED" $Reason
    Write-SuiteGateReport -Verdict "blocked" -FailedSurface $Id
    Write-Host "[echolabs-suite-gate] BLOCKED ${Id}: $Reason" -ForegroundColor Red
    exit 2
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
    $entered = $false
    $exitCode = 1
    try {
        Push-Location $WorkingDirectory
        $entered = $true
        & $Command @Arguments
        $exitCode = $LASTEXITCODE
    } catch {
        # Report failure even when a checkout or gate command disappears.
        $exitCode = 1
    } finally {
        if ($entered) { Pop-Location }
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

Write-SuiteGateReport -Verdict "running"
$omitted = [ordered]@{
    echolabs_web = [bool]$SkipWeb
    nullxoid_android = [bool]$SkipAndroid
    nullxoid_desktop = [bool]$SkipDesktop
    bridgeecho_nullbridge = [bool]$SkipBridge
    aibenchie_universal_e2e = [bool]$SkipUniversalE2E
    aibenchie_deploy_plan = [bool]$SkipDeployPlan
    aibenchie_docker_support = [bool]$SkipDockerSupport
    aibenchie_distribution_hygiene = [bool]$SkipDistributionHygiene
    aibenchie_real_device_ux = [bool]$SkipRealDeviceUX
    desktop_ui = (-not $SkipDesktop) -and (-not $DesktopIncludeUi)
    bridge_full = (-not $SkipBridge) -and (-not $BridgeFull)
}
foreach ($gate in $omitted.GetEnumerator()) {
    if ($gate.Value) { Add-UnfinishedGate $gate.Key "SKIPPED" "Not run by this invocation; cannot qualify a complete release." }
}

$resolvedDeployPlanPath = [System.IO.Path]::GetFullPath($(if ([System.IO.Path]::IsPathRooted($DeployPlanPath)) { $DeployPlanPath } else { Join-Path $aibenchieRoot $DeployPlanPath }))
$resolvedRealDeviceUXProofPath = [System.IO.Path]::GetFullPath($(if ([System.IO.Path]::IsPathRooted($RealDeviceUXProofPath)) { $RealDeviceUXProofPath } else { Join-Path $aibenchieRoot $RealDeviceUXProofPath }))
if ((-not $SkipDeployPlan) -and (-not (Test-Path -LiteralPath $resolvedDeployPlanPath -PathType Leaf))) {
    Stop-MissingPrerequisite "aibenchie_deploy_plan" "Required deployment proof is missing."
}
if ((-not $SkipRealDeviceUX) -and (-not $GenerateAndroidRealDeviceUXProof) -and (-not (Test-Path -LiteralPath $resolvedRealDeviceUXProofPath -PathType Leaf))) {
    Stop-MissingPrerequisite "aibenchie_real_device_ux" "Required real-device proof is missing."
}
if ((-not $WebRepository) -and ($existingWebRepos.Count -gt 1) -and ((-not $SkipWeb) -or (-not $SkipDistributionHygiene))) {
    Stop-MissingPrerequisite "web_repository" "More than one web checkout exists; select -WebRepository explicitly."
}
$requiredRepos = @(
    @{ Id = "web_repository"; Path = $webRepoPath; Required = (-not $SkipWeb) -or (-not $SkipDistributionHygiene) },
    @{ Id = "android_repository"; Path = $androidRepoPath; Required = (-not $SkipAndroid) -or (-not $SkipDistributionHygiene) },
    @{ Id = "desktop_repository"; Path = $desktopRepoPath; Required = (-not $SkipDesktop) -or (-not $SkipDistributionHygiene) },
    @{ Id = "bridge_repository"; Path = $bridgeRepoPath; Required = (-not $SkipBridge) -or (-not $SkipDistributionHygiene) },
    @{ Id = "lv7_repository"; Path = $lv7RepoPath; Required = -not $SkipDistributionHygiene }
)
foreach ($repo in $requiredRepos) {
    if ($repo.Required -and (-not (Test-Path -LiteralPath $repo.Path -PathType Container))) {
        Stop-MissingPrerequisite $repo.Id "Selected repository directory is missing."
    }
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
        -WorkingDirectory $androidRepoPath `
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
        -WorkingDirectory $desktopRepoPath `
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
        -WorkingDirectory (Join-Path $bridgeRepoPath "backend") `
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
    Stop-MissingPrerequisite "aibenchie_deploy_plan" "Required deployment proof disappeared during the run."
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
    Stop-MissingPrerequisite "aibenchie_real_device_ux" "Required real-device proof was not produced or disappeared during the run."
}

if (-not $SkipDistributionHygiene) {
    $distributionRoots = @(
        [ordered]@{ Id = "aibenchie_distribution_hygiene"; Name = "AIBenchie distribution hygiene"; Owner = "AIBenchie"; Path = $aibenchieRoot },
        [ordered]@{ Id = "web_distribution_hygiene"; Name = "EchoLabs web distribution hygiene"; Owner = "EchoLabs / NullXoid Chat"; Path = $webRepoPath },
        [ordered]@{ Id = "android_distribution_hygiene"; Name = "NullXoid Android distribution hygiene"; Owner = "NullXoid Android"; Path = $androidRepoPath },
        [ordered]@{ Id = "desktop_distribution_hygiene"; Name = "NullXoid Desktop distribution hygiene"; Owner = "NullXoid Desktop / LV7"; Path = $desktopRepoPath },
        [ordered]@{ Id = "nullbridge_distribution_hygiene"; Name = "BridgeEcho / NullBridge distribution hygiene"; Owner = "BridgeEcho"; Path = $bridgeRepoPath },
        [ordered]@{ Id = "lv7_distribution_hygiene"; Name = "Lv-7 distribution hygiene"; Owner = "Lv-7"; Path = $lv7RepoPath }
    )

    foreach ($target in $distributionRoots) {
        if (-not (Test-Path -LiteralPath $target.Path)) {
            Stop-MissingPrerequisite $target.Id "Required repository disappeared during the run."
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
if (@($results | Where-Object { $_.status -ne "PASS" }).Count -gt 0 -or $results.Count -eq 0) {
    Write-SuiteGateReport -Verdict "incomplete"
    Write-Host "[echolabs-suite-gate] INCOMPLETE: selected checks finished, but required release coverage was skipped." -ForegroundColor DarkYellow
    exit 2
}
Write-SuiteGateReport -Verdict "pass"
Write-Host "[echolabs-suite-gate] report $resolvedReportPath" -ForegroundColor Cyan
Write-Host "[echolabs-suite-gate] selected checks passed; this report does not authorize deployment" -ForegroundColor Green
