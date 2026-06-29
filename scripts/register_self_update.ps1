# Registers a Windows Scheduled Task that self-updates the traffic model.
#
# Runs scripts/auto_update.py every 3 hours: collects real TomTom data (hard-
# capped to the free daily budget), retrains, and the running API hot-reloads the
# new model. Safe to leave running - it can never exceed the free tier.
#
# Usage (from the project root, normal PowerShell - no admin needed):
#     powershell -ExecutionPolicy Bypass -File scripts\register_self_update.ps1
# Remove later with:
#     Unregister-ScheduledTask -TaskName "AustinTraffic-SelfUpdate" -Confirm:$false

$ProjectDir = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python).Source
$TaskName = "AustinTraffic-SelfUpdate"

if (-not $Python) { Write-Error "python not found on PATH"; exit 1 }

$action = New-ScheduledTaskAction -Execute $Python -Argument "scripts\auto_update.py" -WorkingDirectory $ProjectDir
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(2)) -RepetitionInterval (New-TimeSpan -Hours 3)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
$desc = "Austin traffic: collect real data + retrain (budget-capped)"

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description $desc -Force | Out-Null

$info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Output ("Registered '" + $TaskName + "' - runs every 3 hours (next: " + $info.NextRunTime + ").")
Write-Output ("Python:  " + $Python)
Write-Output ("Project: " + $ProjectDir)
Write-Output "Collects within the free daily budget and retrains; the API hot-reloads automatically."
