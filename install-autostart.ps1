# Registers youtube-search server as a Task Scheduler task that runs at login.
# Equivalent to the Mac LaunchAgent (com.james.youtube-search.plist).
# Run once from the project directory:
#   powershell -ExecutionPolicy Bypass -File install-autostart.ps1

$ErrorActionPreference = 'Stop'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python     = Join-Path $projectDir 'venv\Scripts\pythonw.exe'
$script     = Join-Path $projectDir 'server.py'
$logFile    = Join-Path $projectDir 'server.log'
$taskName   = 'YouTubeSearchServer'

if (-not (Test-Path $python)) {
    Write-Error "venv not found at $python — run setup.bat first."
    exit 1
}

$action  = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $projectDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# Remove existing task if present so this script is idempotent
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Limited -Description 'YouTube search local server (port 7799)'

Write-Host ""
Write-Host "Task '$taskName' registered. The server will start automatically at next login."
Write-Host "To start it right now without rebooting:"
Write-Host "   Start-ScheduledTask -TaskName '$taskName'"
Write-Host ""
Write-Host "To remove autostart:"
Write-Host "   Unregister-ScheduledTask -TaskName '$taskName'"
