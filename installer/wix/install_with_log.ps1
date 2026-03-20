#Requires -Version 5.1
<#
.SYNOPSIS
  Run the MSI with verbose logging (use when double-click seems to do nothing).
.PARAMETER MsiPath
  Full path to the .msi. Default: ..\..\dist\OPAIUM-*-windows.msi (newest match).
#>
param([string] $MsiPath)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDist = Join-Path (Join-Path $here "..\..") "dist"

if (-not $MsiPath) {
    $candidates = Get-ChildItem -Path $repoDist -Filter "OPAIUM-*-windows.msi" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    if (-not $candidates) {
        throw "No MSI found under $repoDist. Pass -MsiPath 'C:\path\to\OPAIUM-v1.0.0-windows.msi' or build with build_msi.ps1."
    }
    $MsiPath = $candidates[0].FullName
}

$MsiPath = (Resolve-Path -LiteralPath $MsiPath).Path
$log = Join-Path $env:TEMP "opaium-msi-install.log"

Write-Host "MSI: $MsiPath"
Write-Host "Log: $log"
Write-Host ""

$proc = Start-Process -FilePath "msiexec.exe" -ArgumentList @("/i", $MsiPath, "/l*v", $log) -Wait -PassThru
Write-Host "msiexec exit code: $($proc.ExitCode)"
if ($proc.ExitCode -ne 0) {
    Write-Host "Open the log file for details (search for 'ReturnValue' or 'error')." -ForegroundColor Yellow
}
