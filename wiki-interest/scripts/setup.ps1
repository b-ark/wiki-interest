<#
.SYNOPSIS
    Prepare a reproducible environment for the wiki-interest skill on Windows.
.DESCRIPTION
    Installs uv if it is missing, then syncs the locked dependencies (runtime only).
    Safe to run repeatedly.
.PARAMETER Dev
    Also install the development dependency group (tests, linters).
#>
param([switch]$Dev)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found; installing it with the official installer (https://astral.sh/uv)..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
}

if ($Dev) { uv sync } else { uv sync --no-dev }

Write-Host "Environment ready. Try: uv run scripts/run.py --help"
