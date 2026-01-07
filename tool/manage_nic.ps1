<#
.EXAMPLE
    .\manage_nic.ps1 -Action Disable
.EXAMPLE
    .\manage_nic.ps1 -Action Enable
#>

param (
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("Enable", "Disable")]
    [string]$Action
)

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]$identity
$adminRole = [Security.Principal.WindowsBuiltInRole]"Administrator"

if (-not $principal.IsInRole($adminRole)) {
    Write-Warning "This script requires Administrator privileges. Please Run as Administrator."
    break
}

$adapters = Get-NetAdapter | Where-Object { $_.Status -ne "NotPresent" }

if ($adapters.Count -eq 0) {
    Write-Warning "No network adapters found."
    exit
}

Write-Host "--- Starting Operation: $Action All Adapters ---" -ForegroundColor Cyan

foreach ($nic in $adapters) {
    $currentStatus = $nic.Status
    Write-Host "Adapter: [$($nic.Name)] ($currentStatus)" -NoNewline

    if ($Action -eq "Disable") {
        if ($currentStatus -ne "Disabled") {
            Write-Host " -> Disabling..." -ForegroundColor Yellow
            Disable-NetAdapter -InputObject $nic -Confirm:$false
        } else {
            Write-Host " -> Already Disabled." -ForegroundColor DarkGray
        }
    }
    elseif ($Action -eq "Enable") {
        if ($currentStatus -eq "Disabled") {
            Write-Host " -> Enabling..." -ForegroundColor Green
            Enable-NetAdapter -InputObject $nic -Confirm:$false
        } else {
            Write-Host " -> Already Active." -ForegroundColor DarkGray
        }
    }
}

Write-Host "--- Operation Complete ---" -ForegroundColor Cyan
