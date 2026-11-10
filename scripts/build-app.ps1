<#
.SYNOPSIS
    Build the CleanYourPhone app, its CLI sidecar and the per-user installer.

.DESCRIPTION
    1. scripts/build-cli-sidecar.ps1 stages resources/cli and resources/profiles.
    2. PyInstaller builds dist/CleanYourPhone from packaging/cleanyourphone-app.spec.
    3. Both executables are smoke-tested.
    4. Inno Setup builds dist/CleanYourPhone-Setup-0.1.0.exe.

    Inno Setup 6 is required for the installer. If ISCC.exe is not installed the
    script fails with an explicit message after the app itself has been built;
    it never creates a placeholder installer.

.PARAMETER Python
    Python executable used for the sidecar and app builds. Defaults to "python".

.PARAMETER SkipSidecar
    Reuse resources/ from a previous sidecar build. CI uses this to keep the
    build steps separate.

.PARAMETER SkipInstaller
    Build and smoke-test the app but do not run Inno Setup. CI uses this before
    installing the compiler; the exact build-app.ps1 command builds everything.
#>
[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$SkipSidecar,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SidecarScript = Join-Path $PSScriptRoot "build-cli-sidecar.ps1"
$Spec = Join-Path $Root "packaging\cleanyourphone-app.spec"
$InstallerScript = Join-Path $Root "packaging\installer.iss"
$Dist = Join-Path $Root "dist"
$AppDist = Join-Path $Dist "CleanYourPhone"
$AppExe = Join-Path $AppDist "CleanYourPhone.exe"
$SidecarExe = Join-Path $AppDist "resources\cli\cleanyourphone.exe"
$DistProfiles = Join-Path $AppDist "resources\profiles"
$SetupExe = Join-Path $Dist "CleanYourPhone-Setup-0.1.0.exe"

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    Write-Host "==> $Description"
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $FilePath @Arguments
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE"
    }
}

function Remove-IfPresent {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Find-InnoCompiler {
    $candidates = New-Object System.Collections.Generic.List[string]

    $onPath = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($null -ne $onPath) {
        $candidates.Add($onPath.Source)
    }

    if (-not [string]::IsNullOrWhiteSpace($env:INNO_SETUP_ISCC)) {
        $candidates.Add($env:INNO_SETUP_ISCC)
    }
    if (-not [string]::IsNullOrWhiteSpace(${env:ProgramFiles(x86)})) {
        $candidates.Add((Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"))
    }
    if (-not [string]::IsNullOrWhiteSpace($env:ProgramFiles)) {
        $candidates.Add((Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"))
    }
    if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"))
    }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    return $null
}

# ---------------------------------------------------------------------------
# 1. Sidecar and profiles.
# ---------------------------------------------------------------------------
if ($SkipSidecar) {
    Write-Host "==> Reusing the staged sidecar and profiles"
    if (-not (Test-Path (Join-Path $Root "resources\cli\cleanyourphone.exe"))) {
        throw "-SkipSidecar was set but resources\cli\cleanyourphone.exe is missing. Run scripts/build-cli-sidecar.ps1 first."
    }
    if (-not (Test-Path (Join-Path $Root "resources\profiles\schema.json"))) {
        throw "-SkipSidecar was set but resources\profiles is missing. Run scripts/build-cli-sidecar.ps1 first."
    }
}
else {
    & $SidecarScript -Python $Python
}

# ---------------------------------------------------------------------------
# 2. Freeze the Qt app (onedir).
# ---------------------------------------------------------------------------
Remove-IfPresent $AppDist
$appWork = Join-Path $Root "build\pyinstaller-app"
Remove-IfPresent $appWork

Invoke-Native "Freeze the app with PyInstaller" $Python @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--distpath", $Dist,
    "--workpath", $appWork,
    $Spec
)

if (-not (Test-Path $AppExe)) {
    throw "PyInstaller completed but did not produce $AppExe."
}

# ---------------------------------------------------------------------------
# 3. Smoke-test the shipped executables.
# ---------------------------------------------------------------------------
$previousProfiles = $env:CLEANYOURPHONE_PROFILES
try {
    $env:CLEANYOURPHONE_PROFILES = $DistProfiles

    $sidecarVersion = (& $SidecarExe "--version" | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $sidecarVersion -ne "CleanYourPhone 0.3.1") {
        throw "Sidecar smoke test failed: expected 'CleanYourPhone 0.3.1', got '$sidecarVersion' (exit $LASTEXITCODE)."
    }

    $sidecarValidation = (& $SidecarExe "validate" | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $sidecarValidation -notmatch 'OK: 156 profile\(s\) valid') {
        throw "Sidecar validate smoke test failed (exit $LASTEXITCODE):`n$sidecarValidation"
    }
}
finally {
    if ($null -eq $previousProfiles) {
        Remove-Item Env:\CLEANYOURPHONE_PROFILES -ErrorAction SilentlyContinue
    }
    else {
        $env:CLEANYOURPHONE_PROFILES = $previousProfiles
    }
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "build") | Out-Null
$appVersionFile = Join-Path $Root "build\app-version.txt"
Remove-IfPresent $appVersionFile
$appProcess = Start-Process -FilePath $AppExe `
    -ArgumentList "--version" `
    -NoNewWindow `
    -Wait `
    -PassThru `
    -RedirectStandardOutput $appVersionFile
$appVersion = (Get-Content -LiteralPath $appVersionFile -Raw).Trim()
if ($appProcess.ExitCode -ne 0 -or $appVersion -ne "CleanYourPhone app 0.1.0") {
    throw "App smoke test failed: expected 'CleanYourPhone app 0.1.0', got '$appVersion' (exit $($appProcess.ExitCode))."
}

Write-Host "Smoke tests passed: $sidecarVersion / $appVersion"

# ---------------------------------------------------------------------------
# 4. Per-user installer.
# ---------------------------------------------------------------------------
if ($SkipInstaller) {
    Write-Host ""
    Write-Host "Installer skipped (-SkipInstaller). App ready at $AppExe."
    return
}

$iscc = Find-InnoCompiler
if ($null -eq $iscc) {
    throw @"
Inno Setup 6 compiler (ISCC.exe) was not found.
Install it and rerun this script:
    choco install innosetup -y
or download it from https://jrsoftware.org/isdl.php
The app itself was built successfully at:
    $AppExe
The installer script is ready at:
    $InstallerScript
No installer was created.
"@
}

Remove-IfPresent $SetupExe
Invoke-Native "Build the per-user installer" $iscc @("/Qp", $InstallerScript)

if (-not (Test-Path $SetupExe)) {
    throw "Inno Setup completed but did not produce $SetupExe."
}

$setupSizeMb = [math]::Round((Get-Item $SetupExe).Length / 1MB, 1)
Write-Host ""
Write-Host "Packaging complete."
Write-Host "  app:       $AppExe"
Write-Host "  sidecar:   $SidecarExe"
Write-Host "  installer: $SetupExe ($setupSizeMb MB)"
