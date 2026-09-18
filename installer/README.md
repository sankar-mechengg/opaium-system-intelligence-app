# OP(AI)UM Installer

## MSI (WiX) — used for GitHub Releases

Tagged releases (`v*`) build an **MSI** in CI and attach it next to the ZIP.

### Local build (Windows)

1. Build the app: `python scripts/build.py`
2. Run (PowerShell):

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass -Force
   ./installer/wix/build_msi.ps1 -TagName "v2.0.0" -RepoRoot (Get-Location)
   ```

3. Output: `dist/OPAIUM-v2.0.0-windows.msi`

The script downloads [WiX Toolset 3.11](https://github.com/wixtoolset/wix3/releases) binaries into `%TEMP%` if `candle.exe` is not already there.

### What the MSI does

- Per-machine install under **Program Files** (`OPAIUM\`)
- **Start Menu** shortcut (all users)
- Major upgrade support (same `UpgradeCode`)
- **64-bit Windows only** (installs under `Program Files`, not `Program Files (x86)`)

### Double-click “flashes” and nothing seems to happen

This MSI does **not** ship a full WiX wizard UI (the package is large; a standard UI would complicate the build). Windows Installer may show only a **short** window while it works.

1. **UAC** — The package requires **elevation** (`perMachine`). If you dismiss the UAC prompt, the install will stop with no visible app.
2. **It may have succeeded** — Check **Start Menu → OP(AI)UM** and `C:\Program Files\OPAIUM\OPAIUM.exe`.
3. **Capture a log** — From PowerShell in the repo:

   ```powershell
   ./installer/wix/install_with_log.ps1
   ```

   Or manually:

   ```powershell
   msiexec /i "C:\path\to\OPAIUM-v2.0.0-windows.msi" /l*v "$env:TEMP\opaium-msi-install.log"
   ```

   Then open `%TEMP%\opaium-msi-install.log` and search for `Return value 3` / `error` if something failed.

---

## EXE installer (Inno Setup) — optional

### Prerequisites
1. Build the app first: `python scripts/build.py`
2. Install [Inno Setup](https://jrsoftware.org/isinfo.php) (v6+)

### Steps
1. Open `opaium_setup.iss` in Inno Setup Compiler
2. Click **Build → Compile** (or press Ctrl+F9)
3. The installer will be output to `installer/output/OPAIUM_Setup_2.0.0.exe`

### What the Installer Does
- Installs OP(AI)UM to `C:\Program Files\OPAIUM\`
- Creates Start Menu shortcuts
- Optionally creates a Desktop shortcut
- Optionally registers for Windows startup
- Creates uninstaller entry in Windows Settings
- On uninstall, removes AppData folder
