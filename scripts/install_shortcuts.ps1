# Vocalis-Nexus Shortcut Installer
# Creates Desktop and Start Menu shortcuts with custom Cyber-Pet icon and Ctrl+Alt+V hotkey.
# Does NOT install background daemon or startup entries (100% on-demand).

$ErrorActionPreference = "Stop"

$PluginRoot = "$HOME\.gemini\config\plugins\vocalis-nexus-plugin"
$ToggleScript = "$PluginRoot\scripts\toggle.py"
$IconPath = "$PluginRoot\vocalis\ui\assets\vocalis.ico"

# Find pythonw.exe
$Pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $Pythonw) {
    $Pythonw = (Get-Command python.exe -ErrorAction Stop).Source
}

$WshShell = New-Object -ComObject WScript.Shell

# 1. Desktop Shortcut
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$DesktopShortcutPath = Join-Path $DesktopPath "Vocalis Sentinel.lnk"

$Shortcut = $WshShell.CreateShortcut($DesktopShortcutPath)
$Shortcut.TargetPath = $Pythonw
$Shortcut.Arguments = "`"$ToggleScript`""
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
$StartShortcut.Arguments = "`"$ToggleScript`""
$StartShortcut.WorkingDirectory = $PluginRoot
if (Test-Path $IconPath) {
    $StartShortcut.IconLocation = "$IconPath, 0"
}
$StartShortcut.Hotkey = "Ctrl+Alt+V"
$StartShortcut.Description = "Vocalis Sentinel Desktop Pet & Voice AI Assistant"
$StartShortcut.Save()

Write-Host "✅ Start Menu shortcut created: $StartShortcutPath" -ForegroundColor Green
Write-Host "🎉 You can now summon Vocalis anytime by double-clicking the Desktop icon or pressing Ctrl+Alt+V!" -ForegroundColor Cyan
