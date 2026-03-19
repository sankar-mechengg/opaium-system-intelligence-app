# OP(AI)UM Installer

## MSI (WiX) — used for GitHub Releases

Tagged releases (`v*`) build an **MSI** in CI and attach it next to the ZIP.

### Local build (Windows)

1. Build the app: `python scripts/build.py`
2. Run (PowerShell):

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass -Force
   ./installer/wix/build_msi.ps1 -TagName "v1.0.0" -RepoRoot (Get-Location)
   ```

3. Output: `dist/OPAIUM-v1.0.0-windows.msi`

The script downloads [WiX Toolset 3.11](https://github.com/wixtoolset/wix3/releases) binaries into `%TEMP%` if `candle.exe` is not already there.

### What the MSI does

- Per-machine install under **Program Files** (`OPAIUM\`)
- **Start Menu** shortcut (all users)
- Major upgrade support (same `UpgradeCode`)

---

## EXE installer (Inno Setup) — optional

### Prerequisites
1. Build the app first: `python scripts/build.py`
2. Install [Inno Setup](https://jrsoftware.org/isinfo.php) (v6+)

### Steps
1. Open `opaium_setup.iss` in Inno Setup Compiler
2. Click **Build → Compile** (or press Ctrl+F9)
3. The installer will be output to `installer/output/OPAIUM_Setup_1.0.0.exe`

### What the Installer Does
- Installs OP(AI)UM to `C:\Program Files\OPAIUM\`
- Creates Start Menu shortcuts
- Optionally creates a Desktop shortcut
- Optionally registers for Windows startup
- Creates uninstaller entry in Windows Settings
- On uninstall, removes AppData folder
