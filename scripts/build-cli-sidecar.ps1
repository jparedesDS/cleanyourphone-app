<#
.SYNOPSIS
    Build the pinned CleanYourPhone CLI as a frozen onedir sidecar.

.DESCRIPTION
    Clones the CLI at the requested tag into .build/cli-src, builds its wheel,
    installs it into an isolated .build/cli-venv, freezes a launcher with
    PyInstaller, and stages the result for the app build:

        resources/cli/cleanyourphone.exe   (plus the onedir files)
        resources/profiles/                 (the pinned profile catalog)

    The frozen sidecar is smoke-tested with --version and validate before the
    script succeeds. It is a console-subsystem program; the app launches every
    sidecar call with CREATE_NO_WINDOW so no console window flashes.

.PARAMETER CliVersion
    Git tag of the CLI to build. The app ships v0.3.2.

.PARAMETER Python
    Python executable used for pip, venv and PyInstaller. Defaults to "python".

.PARAMETER Force
    Re-clone the source even when the checkout already has the requested tag.
#>
[CmdletBinding()]
param(
    [string]$CliVersion = "v0.3.2",
    [string]$RepoUrl = "https://github.com/jparedesDS/cleanyourphone",
    [string]$Python = "python",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Build = Join-Path $Root ".build"
$Source = Join-Path $Build "cli-src"
$Venv = Join-Path $Build "cli-venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$SitePackages = Join-Path $Venv "Lib\site-packages"
$Wheels = Join-Path $Build "wheels"
$Launcher = Join-Path $Build "cli-launcher.py"
$Dist = Join-Path $Build "cli-dist"
$Work = Join-Path $Build "cli-work"
$SpecDir = Join-Path $Build "cli-spec"

$CliTarget = Join-Path $Root "resources\cli"
$ProfilesTarget = Join-Path $Root "resources\profiles"
$FrozenExe = Join-Path $CliTarget "cleanyourphone.exe"

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

New-Item -ItemType Directory -Force -Path $Build | Out-Null

# ---------------------------------------------------------------------------
# 1. Clone the pinned tag.
# ---------------------------------------------------------------------------
$reuseSource = $false
if (-not $Force -and (Test-Path (Join-Path $Source ".git"))) {
    $describeExit = 1
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $existingTag = (& git -C $Source describe --tags --exact-match 2>$null | Out-String).Trim()
        $describeExit = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
    if ($describeExit -eq 0 -and $existingTag -eq $CliVersion) {
        $reuseSource = $true
    }
}

if (-not $reuseSource) {
    Remove-IfPresent $Source
    Invoke-Native "Clone CleanYourPhone CLI at $CliVersion" "git" @(
        "clone", "--depth", "1", "--branch", $CliVersion, $RepoUrl, $Source
    )
}

$CliPackage = Join-Path $Source "tools\phone.py"
if (-not (Test-Path $CliPackage)) {
    throw "The CLI checkout at $Source does not look like CleanYourPhone (tools/phone.py is missing)."
}

# ---------------------------------------------------------------------------
# 2. Build the wheel and install it in a private venv.
# ---------------------------------------------------------------------------
Remove-IfPresent $Wheels
New-Item -ItemType Directory -Force -Path $Wheels | Out-Null
Invoke-Native "Build the CLI wheel" $Python @(
    "-m", "pip", "wheel", "--no-deps", "--wheel-dir", $Wheels, $Source
)

$wheel = Get-ChildItem -Path $Wheels -Filter "cleanyourphone-*.whl" |
    Sort-Object Name -Descending |
    Select-Object -First 1
if ($null -eq $wheel) {
    throw "pip did not produce a cleanyourphone wheel in $Wheels."
}

# Recreate the venv so a build cannot reuse a wheel installed for a different
# Python interpreter.
Remove-IfPresent $Venv
Invoke-Native "Create the sidecar build venv" $Python @("-m", "venv", $Venv)

Invoke-Native "Install the CLI wheel in the build venv" $VenvPython @(
    "-m", "pip", "install", "--disable-pip-version-check", "--force-reinstall", $wheel.FullName
)
if (-not (Test-Path $SitePackages)) {
    throw "The sidecar venv has no Lib/site-packages directory at $SitePackages."
}

# ---------------------------------------------------------------------------
# 3. Freeze the launcher.
# ---------------------------------------------------------------------------
$launcherText = @'
"""PyInstaller entry point for the pinned CleanYourPhone CLI sidecar."""

import sys

from cleanyourphone.phone import main


if __name__ == "__main__":
    sys.exit(main())
'@
[System.IO.File]::WriteAllText($Launcher, $launcherText, [System.Text.UTF8Encoding]::new($false))

Remove-IfPresent $Dist
Remove-IfPresent $Work
Remove-IfPresent $SpecDir
Invoke-Native "Freeze the CLI sidecar with PyInstaller" $Python @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onedir",
    "--name", "cleanyourphone",
    "--paths", $SitePackages,
    "--distpath", $Dist,
    "--workpath", $Work,
    "--specpath", $SpecDir,
    $Launcher
)

$builtExe = Join-Path $Dist "cleanyourphone\cleanyourphone.exe"
if (-not (Test-Path $builtExe)) {
    throw "PyInstaller completed but did not produce $builtExe."
}

# ---------------------------------------------------------------------------
# 4. Stage resources for the app and installer.
# ---------------------------------------------------------------------------
Remove-IfPresent $CliTarget
New-Item -ItemType Directory -Force -Path $CliTarget | Out-Null
Copy-Item -Path (Join-Path $Dist "cleanyourphone\*") -Destination $CliTarget -Recurse -Force

Remove-IfPresent $ProfilesTarget
Copy-Item -Path (Join-Path $Source "profiles") -Destination $ProfilesTarget -Recurse -Force

if (-not (Test-Path $FrozenExe)) {
    throw "The frozen sidecar was not staged at $FrozenExe."
}
if (-not (Test-Path (Join-Path $ProfilesTarget "schema.json"))) {
    throw "The profile catalog was not staged at $ProfilesTarget."
}

# ---------------------------------------------------------------------------
# 5. Smoke-test the exact executable that ships.
# ---------------------------------------------------------------------------
$previousProfiles = $env:CLEANYOURPHONE_PROFILES
try {
    $env:CLEANYOURPHONE_PROFILES = $ProfilesTarget

    $version = (& $FrozenExe "--version" | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "The frozen sidecar --version failed with exit code $LASTEXITCODE."
    }
    if ($version -ne "CleanYourPhone 0.3.2") {
        throw "Expected sidecar version 'CleanYourPhone 0.3.2', got '$version'."
    }

    $validation = (& $FrozenExe "validate" | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "The frozen sidecar validate failed with exit code $LASTEXITCODE.`n$validation"
    }
    if ($validation -notmatch 'OK: 156 profile\(s\) valid') {
        throw "Expected validate to report 156 profiles, got:`n$validation"
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

Write-Host ""
Write-Host "Sidecar ready."
Write-Host "  executable: $FrozenExe"
Write-Host "  profiles:   $ProfilesTarget"
Write-Host "  version:    $version"
Write-Host "  validate:   $($validation.Split("`n")[-1])"
