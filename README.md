# OP(AI)UM — System Intelligence for Windows

**Omniscient Processor for Adaptive Intelligence & Unified Management**

OP(AI)UM is a Windows desktop app that puts a fast file explorer, a system dashboard and an AI assistant
that can *act* on your files into one premium, native-feeling window. Ask it in plain language to count,
find, organize, rename, move, clean up or read files — every destructive change is previewed first, and
everything it does can be undone.

> Version **2.0.0** · Windows 10/11 · MIT License

---

## Highlights

### 🗂️ Explorer
- **Home view** of recently used files and folders (from Windows Recent), grouped by time.
- **Real browsing**: tree with quick access & drives, clickable breadcrumbs, editable path (`Alt+D`),
  back / forward / up, search, type filters, sorting, grid or details view.
- **Native operations** — rename (`F2`), delete to Recycle Bin (`Del`), new folder (`Ctrl+Shift+N`), open with,
  properties — all journaled and undoable.
- **Live**: the open folder refreshes automatically when files change.
- **Preview panel** with image thumbnails, dates, sizes and one-click actions (open, reveal, copy path, ask AI).

### 🤖 AI assistant
- Streams answers live; shows each tool call as an inline card with status, summary and **Undo**.
- **22 tools**: count, sizes, type breakdown, duplicates, large / old files, metadata, disk usage, startup
  programs, Recycle Bin, rename (batch / regex / extensions), move, copy, delete, organize by type / date,
  flatten, clean empty folders, folder operations, read / write documents (TXT, MD, CSV, code, PDF, DOCX,
  PPTX, XLSX).
- **Enforced safety**: protected system locations are refused outright; destructive tools always show a
  real preview and need your approval (configurable); deletions go to the Recycle Bin; files are backed up
  before the AI overwrites them.
- **Any provider**: OpenAI (default `gpt-5.2`) or any OpenAI-compatible endpoint — Ollama, LM Studio,
  OpenRouter, Groq — via a base URL. Fetch the endpoint's model list and test the connection from Settings.
- Voice input (gpt-4o-transcribe / whisper-1) with a live level meter; conversation history with folder context.

### 📊 Dashboard
Live CPU, memory, uptime and process count; drive usage; largest user folders; recent activity;
startup programs; Recycle Bin and undo stats — plus one-click AI actions.

### ↩️ History
Every AI and Explorer change, newest first, with Undo (rename, move, organize, copy, delete → Recycle Bin
restore, write → content backup, folder / file creation, empty-folder cleanup).

### 🔒 Security & privacy
- Optional PIN / password lock (Argon2id) with idle auto-lock, `Ctrl+L`, progressive lockout and a documented
  reset path.
- API key encrypted with a machine-bound key; nothing leaves your PC except requests to your chosen provider.
- No telemetry. Update checks only read the public GitHub Releases feed (can be disabled).

### ✨ Premium feel
Native Windows 11 frameless window (snap layouts, shadow, rounded corners), a token-based design system
that follows the Windows light / dark theme, crisp SVG icons at any DPI, a global hotkey
(`Ctrl+Shift+Space`) to summon the window from anywhere, tray integration and Windows toasts.

---

## Install

Grab the latest release from **[GitHub Releases](https://github.com/sankar-mechengg/opaium-system-intelligence-app/releases)**:

| Asset | Use |
|-------|-----|
| `OPAIUM-v2.0.0-windows.msi` | Installer (Program Files, Start Menu, uninstall from Settings) |
| `OPAIUM-v2.0.0-windows.zip` | Portable — extract anywhere and run `OPAIUM.exe` |

First launch walks you through an optional lock and the AI provider. Add an OpenAI API key (or point OP(AI)UM
at a local server) in **Settings → AI** at any time.

Data lives in `%APPDATA%\OPAIUM` (settings, history, backups, logs). See
[docs/configuration.md](docs/configuration.md).

### From source

```bash
git clone https://github.com/sankar-mechengg/opaium-system-intelligence-app.git
cd opaium-system-intelligence-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/run_dev.py            # or scripts/run_dev_watch.py for auto-restart
```

Requirements: Python 3.11+, Windows 10/11.

---

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+1` … `Ctrl+4` | Dashboard / Explorer / AI Chat / History |
| `Ctrl+K` | Jump to the chat input |
| `Ctrl+F` / `Alt+D` | Search this view / edit the path |
| `Alt+←` `Alt+→` `Alt+↑` `Backspace` | Back / forward / up |
| `F2` / `Del` / `Ctrl+Shift+N` | Rename / delete to Recycle Bin / new folder |
| `F5` | Refresh |
| `Ctrl+Shift+Z` | Undo the last operation |
| `Ctrl+L` / `Ctrl+,` / `Ctrl+Q` | Lock / Settings / Quit |
| `Ctrl+Shift+Space` (global) | Show or hide OP(AI)UM from anywhere |

---

## Development

```bash
python scripts/lint.py --fix                       # ruff + mypy
python scripts/run_tests.py --verbose --coverage   # pytest
python scripts/build.py                            # PyInstaller → dist/OPAIUM
.\installer\wix\build_msi.ps1 -TagName "v2.0.0" -RepoRoot (Get-Location)   # MSI (WiX 3.11)
```

Pushing a tag like `v2.0.0` builds the ZIP and MSI on GitHub Actions and attaches them to a release.
The version is defined once in `src/version.py`.

Docs: [architecture](docs/architecture.md) · [configuration](docs/configuration.md) ·
[theming](docs/theming.md) · [adding tools](docs/adding_tools.md) · [AI capabilities](docs/AI_CAPABILITIES.md) ·
[development](docs/DEVELOPMENT.md) · [installer](installer/README.md) · [changelog](CHANGELOG.md)

---

## Project layout

```
src/
├── main.py, app.py        entry point and application controller
├── services/              update check, global hotkey, notifications, idle lock
├── ui/                    theme system, native window, dashboard, explorer, chat, history, settings
├── ai/                    engine, OpenAI-compatible client, safety gate, 22 tools
├── core/                  Recent parser, directory scanner, watcher, Recycle Bin, disks, stats
├── undo/                  journal, undo manager, content backups, auto-purge
├── config/                constants, defaults, encryption, config manager
└── auth/                  Argon2id auth, lock screen, first-run wizard
assets/                    icons (SVG set + logo), themes/base.qss
installer/                 WiX MSI, optional Inno Setup script
scripts/                   build, lint, tests, dev runners, icon generator
tests/                     pytest suite
```

---

## License

MIT — see [LICENSE](LICENSE).

Built by **Sankar Balasubramanian**.
