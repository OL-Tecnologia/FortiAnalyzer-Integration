#Requires -Version 5.1
<#
.SYNOPSIS
    Compila a aplicacao completa (.exe). O ZIP nao e mais gerado.
#>
$ErrorActionPreference = "Stop"
& (Join-Path (Split-Path -Parent $PSScriptRoot) "install\build_app.ps1")
