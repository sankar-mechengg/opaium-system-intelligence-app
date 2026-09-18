#Requires -Version 5.1
<#
.SYNOPSIS
  Build MSI from PyInstaller onedir (dist/OPAIUM) using WiX Toolset 3.11.

.PARAMETER TagName
  Git tag, e.g. v2.0.0 - used for output filename and MSI product version.

.PARAMETER RepoRoot
  Repository root (folder containing dist/OPAIUM).

.PARAMETER WixZipUrl
  WiX 3.11 binaries download URL (official GitHub release).
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $TagName,

    [Parameter(Mandatory = $true)]
    [string] $RepoRoot,

    [string] $WixZipUrl = "https://github.com/wixtoolset/wix3/releases/download/wix3112rtm/wix311-binaries.zip"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$distPath = Join-Path $RepoRoot "dist\OPAIUM"

if (-not (Test-Path (Join-Path $distPath "OPAIUM.exe"))) {
    throw "OPAIUM.exe not found under $distPath - run PyInstaller build first."
}

# WiX Product @Version must be numeric x.x.x.x
$m = [regex]::Match($TagName, 'v?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?')
if (-not $m.Success) {
    $productVersion = "2.0.0.0"
    Write-Warning "Tag '$TagName' not like v1.2.3 - using ProductVersion $productVersion"
} else {
    $b = if ($m.Groups[4].Success) { $m.Groups[4].Value } else { "0" }
    $productVersion = "$($m.Groups[1].Value).$($m.Groups[2].Value).$($m.Groups[3].Value).$b"
}

$wixRoot = Join-Path ([System.IO.Path]::GetTempPath()) "wix311-bin"
$candleExe = Join-Path $wixRoot "candle.exe"
if (-not (Test-Path $candleExe)) {
    Write-Host "Downloading WiX 3.11..."
    $zipPath = Join-Path ([System.IO.Path]::GetTempPath()) "wix311-binaries.zip"
    Invoke-WebRequest -Uri $WixZipUrl -OutFile $zipPath -UseBasicParsing
    if (Test-Path $wixRoot) {
        Remove-Item -LiteralPath $wixRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $wixRoot | Out-Null
    Expand-Archive -LiteralPath $zipPath -DestinationPath $wixRoot -Force
}

$wxsDir = Join-Path $RepoRoot "installer\wix"
$objDir = Join-Path $wxsDir "obj"
if (Test-Path $objDir) {
    Remove-Item -LiteralPath $objDir -Recurse -Force
}
New-Item -ItemType Directory -Path $objDir | Out-Null

$harvestWxs = Join-Path $wxsDir "Harvest.wxs"
if (Test-Path $harvestWxs) {
    Remove-Item -LiteralPath $harvestWxs -Force
}

$heatExe = Join-Path $wixRoot "heat.exe"
$distPathFull = $distPath

Write-Host "heat: harvesting $distPathFull"
# -sreg: skip COM self-registration scan on DLLs/EXE (avoids HEAT5150 noise; not needed for PyInstaller layout)
& $heatExe dir $distPathFull `
    -nologo -gg -sfrag -srd -sreg -platform x64 `
    -cg OPAIUMComponents `
    -dr INSTALLFOLDER `
    -var var.HarvestSource `
    -out $harvestWxs
if ($LASTEXITCODE -ne 0) {
    throw "heat.exe failed with exit code $LASTEXITCODE"
}

$productWxs = Join-Path $wxsDir "Product.wxs"
Write-Host "candle: ProductVersion=$productVersion"
# Candle requires -out to end with \ when compiling multiple sources (directory output).
# When PowerShell quotes a path with spaces, a trailing single \ before " becomes \" and breaks the argument (CNDL0117).
# End the path with \\ so the quoted form is correct (WiX documents this for paths like "C:\Out Directory\\").
$candleOutDir = $objDir.TrimEnd('\') + '\\'
$candleArgs = @(
    "-nologo"
    "-arch"
    "x64"
    "-out"
    $candleOutDir
    "-dHarvestSource=$distPathFull"
    "-dProductVersion=$productVersion"
    "-dLicenseRtf=$(Join-Path $wxsDir 'License.rtf')"
    $productWxs
    $harvestWxs
)
& (Join-Path $wixRoot "candle.exe") @candleArgs
if ($LASTEXITCODE -ne 0) {
    throw "candle.exe failed with exit code $LASTEXITCODE"
}

$msiName = "OPAIUM-$TagName-windows.msi"
$msiPath = Join-Path $RepoRoot "dist\$msiName"
Write-Host "light: $msiPath"
# Architecture is set at candle time (-arch x64); WiX 3 light.exe has no -arch (passing x64 would be treated as a source file).
$wixUIExt = Join-Path $wixRoot "WixUIExtension.dll"
& (Join-Path $wixRoot "light.exe") -nologo -sw1076 `
    -ext $wixUIExt `
    -out $msiPath `
    (Join-Path $objDir "Product.wixobj") `
    (Join-Path $objDir "Harvest.wixobj")
if ($LASTEXITCODE -ne 0) {
    throw "light.exe failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path $msiPath)) {
    throw "MSI not created at $msiPath"
}

Write-Host "[OK] MSI created: $msiPath"
