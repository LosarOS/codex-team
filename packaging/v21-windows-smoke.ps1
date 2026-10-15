<# Read-only Windows acceptance evidence. Does not launch agents, modify Git or install tools.
   Run in PowerShell: .\packaging\v21-windows-smoke.ps1 -BaseUrl http://127.0.0.1:8765 -OutputPath .\windows-smoke.json
   A successful diagnostic report does not replace manual WebView2/DPI/package acceptance. #>
[CmdletBinding()]
param(
    [string]$BaseUrl,
    [string]$OutputPath = '.\v21-windows-smoke.json'
)
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'This acceptance diagnostic requires native Windows.'
}
$report = [ordered]@{
    capturedAtUtc = [DateTime]::UtcNow.ToString('o')
    nativeWindows = $true
    windowsVersion = [Environment]::OSVersion.VersionString
    process64Bit = [Environment]::Is64BitProcess
    powershellVersion = $PSVersionTable.PSVersion.ToString()
    webView2Versions = @()
    api = $null
    manualAcceptance = 'NOT VERIFIED: WebView2 interaction, DPI, installed and portable packages require manual checks.'
}
$clientRoots = @('HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients', 'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients', 'HKCU:\Software\Microsoft\EdgeUpdate\Clients')
foreach ($root in $clientRoots) {
    if (Test-Path -LiteralPath $root) {
        foreach ($client in Get-ChildItem -LiteralPath $root) {
            $properties = Get-ItemProperty -LiteralPath $client.PSPath
            if ($properties.name -like '*WebView2*') {
                $report.webView2Versions += [ordered]@{ name = $properties.name; version = $properties.pv }
            }
        }
    }
}
if ($BaseUrl) {
    $uri = [Uri]$BaseUrl
    if ($uri.Scheme -ne 'http' -or $uri.Host -notin @('127.0.0.1', 'localhost', '[::1]', '::1') -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) {
        throw 'BaseUrl must be an HTTP loopback address without credentials, query or fragment.'
    }
    $health = Invoke-RestMethod -Uri ($BaseUrl.TrimEnd('/') + '/health') -Method Get -TimeoutSec 10
    $report.api = [ordered]@{ health = $health; checkedAtUtc = [DateTime]::UtcNow.ToString('o') }
}
$report | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Output ('Evidence saved: ' + [IO.Path]::GetFullPath($OutputPath))
Write-Output $report.manualAcceptance
