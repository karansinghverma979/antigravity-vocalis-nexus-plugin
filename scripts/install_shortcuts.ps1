param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$PluginRoot = "$HOME\.gemini\config\plugins\vocalis-nexus-plugin"
$DaemonScript = "$PluginRoot\scripts\vocalis_daemon.py"
$IconPath = "$PluginRoot\vocalis\ui\assets\vocalis.ico"

# Resolve Desktop paths (including OneDrive redirection)
$DesktopPaths = @(
    [Environment]::GetFolderPath('Desktop'),
    "$HOME\OneDrive\Desktop",
    "$HOME\Desktop"
) | Select-Object -Unique

$StartMenuPath = [Environment]::GetFolderPath('Programs')

if ($Uninstall) {
    foreach ($dp in $DesktopPaths) {
        $p = Join-Path $dp "Vocalis Sentinel.lnk"
        if (Test-Path $p) {
            Remove-Item -Path $p -Force -ErrorAction SilentlyContinue
            Write-Host "🗑️ Removed desktop shortcut: $p" -ForegroundColor Yellow
        }
    }
    $sp = Join-Path $StartMenuPath "Vocalis Sentinel.lnk"
    if (Test-Path $sp) {
        Remove-Item -Path $sp -Force -ErrorAction SilentlyContinue
        Write-Host "🗑️ Removed Start Menu shortcut: $sp" -ForegroundColor Yellow
    }
    Write-Host "✅ All shortcuts uninstalled successfully." -ForegroundColor Green
    exit 0
}

$WshShell = New-Object -ComObject WScript.Shell

# 1. Desktop Shortcut
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$DesktopShortcutPath = Join-Path $DesktopPath "Vocalis Sentinel.lnk"

$Shortcut = $WshShell.CreateShortcut($DesktopShortcutPath)
$Shortcut.TargetPath = $Pythonw
$Shortcut.Arguments = "`"$DaemonScript`""
$Shortcut.WorkingDirectory = $PluginRoot
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = "$IconPath, 0"
}
$Shortcut.Hotkey = "Ctrl+Alt+V"
$Shortcut.Description = "Vocalis Sentinel Desktop Pet & Voice AI Assistant"
$Shortcut.Save()

Write-Host "✅ Desktop shortcut created: $DesktopShortcutPath (Hotkey: Ctrl+Alt+V)" -ForegroundColor Green

# 2. Start Menu Programs Shortcut
$StartMenuPath = [Environment]::GetFolderPath('Programs')
$StartShortcutPath = Join-Path $StartMenuPath "Vocalis Sentinel.lnk"

$StartShortcut = $WshShell.CreateShortcut($StartShortcutPath)
$StartShortcut.TargetPath = $Pythonw
$StartShortcut.Arguments = "`"$DaemonScript`""
$StartShortcut.WorkingDirectory = $PluginRoot
if (Test-Path $IconPath) {
    $StartShortcut.IconLocation = "$IconPath, 0"
}
$StartShortcut.Hotkey = "Ctrl+Alt+V"
$StartShortcut.Description = "Vocalis Sentinel Desktop Pet & Voice AI Assistant"
$StartShortcut.Save()

Write-Host "✅ Start Menu shortcut created: $StartShortcutPath" -ForegroundColor Green
Write-Host "🎉 You can now summon Vocalis anytime by double-clicking the Desktop icon or pressing Ctrl+Alt+V!" -ForegroundColor Cyan
