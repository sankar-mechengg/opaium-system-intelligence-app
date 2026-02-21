# OP(AI)UM Installer

## Building the Installer

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
