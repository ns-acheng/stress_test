<#
.EXAMPLE
    .\manage-nic.ps1 -Action Disable
.EXAMPLE
    .\manage-nic.ps1 -Action Enable
#>

param (
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("Enable", "Disable")]
    [string]$Action
)

# Self-elevation check to ensure script runs as Administrator
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script requires Administrator privileges. Please Run as Administrator."
    break
}

# Get all adapters that are actually present (excludes drivers for hardware not currently plugged in)
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
        # Only try to disable if it is currently Up or Disconnected (but enabled)
        if ($currentStatus -ne "Disabled") {
            Write-Host " -> Disabling..." -ForegroundColor Yellow
            Disable-NetAdapter -InputObject $nic -Confirm:$false
        } else {
            Write-Host " -> Already Disabled." -ForegroundColor DarkGray
        }
    }
    elseif ($Action -eq "Enable") {
        # Only try to enable if it is currently Disabled
        if ($currentStatus -eq "Disabled") {
            Write-Host " -> Enabling..." -ForegroundColor Green
            Enable-NetAdapter -InputObject $nic -Confirm:$false
        } else {
            Write-Host " -> Already Active." -ForegroundColor DarkGray
        }
    }
}

Write-Host "--- Operation Complete ---" -ForegroundColor Cyan