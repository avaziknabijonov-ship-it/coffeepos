# Run once on the Windows computer where CoffeePOS and Python 3.12 are installed.
# This creates a daily backup at 23:00 using Windows Task Scheduler.
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$batch = Join-Path $PSScriptRoot 'backup_windows.bat'
if (-not (Test-Path (Join-Path $project 'coffeepos.db'))) { throw 'coffeepos.db not found. No task created.' }
if (-not (Test-Path $batch)) { throw 'backup_windows.bat not found.' }
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c "' + $batch + '"') -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Daily -At '23:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName 'CoffeePOS Daily Backup' -Action $action -Trigger $trigger -Settings $settings -Description 'Daily verified backup of CoffeePOS SQLite database' -Force
Write-Host 'Scheduled daily CoffeePOS backup at 23:00. Test scripts/backup_windows.bat manually first.'
