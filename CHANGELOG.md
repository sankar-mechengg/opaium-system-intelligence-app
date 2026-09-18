# Changelog

All notable changes to OP(AI)UM are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses semantic versioning.

## [2.0.0] — 2026-09-18

A ground-up hardening and redesign: safe AI actions, a real file browser, a system dashboard,
a native Windows 11 window and a token-based design system.

### Added
- **Dashboard tab** — live CPU / memory / uptime / processes (psutil), drive usage, largest user folders,
  recent activity, startup programs, Recycle Bin and undo stats, one-click AI actions.
- **Explorer browsing** — tree navigation opens folders in-app; breadcrumbs with editable path (`Alt+D`),
  back / forward / up history, sort (name / date / size / type), grid or details view, per-view search and
  type filters, keyboard navigation, empty states.
- **Native file operations** — rename (`F2`), delete to Recycle Bin (`Del`), new folder (`Ctrl+Shift+N`),
  open with, properties, right-click background menu; all journaled and undoable from History.
- **Live folder watching** (watchdog) — the open folder refreshes when files change.
- **Preview panel** — image thumbnails, modified / created dates, quick actions (open, reveal, copy, ask AI).
- **AI safety gate** — destructive tools are intercepted in the executor: protected system locations are
  refused; every destructive call shows the tool's real preview in an approval dialog; optional
  per-session trust; a *Confirm destructive operations* setting.
- **Streaming chat** — answers stream live; tool calls appear as inline cards with status, summary and
  one-click Undo; Stop button; Up-arrow prompt recall; copy message.
- **Any OpenAI-compatible provider** — base URL presets (Ollama, LM Studio, OpenRouter, Groq), editable
  model, *Fetch models* and *Save & test connection* in Settings.
- **Undo for more operations** — Recycle Bin restore via Shell COM (files and folders), content backups
  before write / append, copy-folder, clean-empty-folders (recreate), correct labels for folder operations.
- **Security** — lock is optional (first-run can skip); *Lock now* (`Ctrl+L`, tray); idle auto-lock;
  progressive lockout instead of disabling the app; documented reset path for forgotten credentials.
- **Native Windows 11 window** — DWM shadow, rounded corners, Snap Layouts / Win+Arrow, edge resizing,
  maximize-button snap flyout, native minimize / restore animations.
- **Design system** — single `base.qss` template with light / dark token palettes, *Follow Windows*
  theme mode with live switching, 69 crisp SVG icons tinted per theme, theme-aware custom widgets,
  bottom-right toasts.
- **Global hotkey** (`Ctrl+Shift+Space`, configurable) to summon or hide the window from anywhere.
- **Windows toasts** while hidden in the tray (respects the notifications setting).
- **Update check** against GitHub Releases (daily, can be disabled, skip-version) with an in-app banner.
- **Window geometry persistence**, status bar, `Ctrl+1…4` tab shortcuts, `Ctrl+Shift+Z` undo-last.
- **Crash handler** — unhandled exceptions are logged and shown instead of silently closing the app.
- `--minimized` and `--log-level` command-line flags; *Start minimized* setting.
- `CHANGELOG.md`, rewritten README and docs, `requirements-dev.txt`, `scripts/generate_icons.py`,
  `tests/test_safety.py`.

### Changed
- Version is defined once in `src/version.py` (read by the app, `pyproject.toml`, the build script and the
  Inno Setup script).
- `Start with Windows` now defaults to **off** and registers with `--minimized`; turning it off removes the
  registry entry.
- Settings apply live: API key / model / endpoint re-initialize the AI engine, the refresh interval restarts
  the timer, card size and view settings re-render the explorer, the hotkey re-registers.
- GPT-5 / o-series models no longer receive a custom temperature (they reject it).
- Tool results are kept in conversation memory so the model remembers what it found on earlier turns.
- Recycle Bin tool gains a `list` action and journals `empty`.
- Auto-purge of the undo journal is scheduled at startup and also prunes content backups.
- `requirements.txt` is runtime-only; dev / packaging tools moved to `requirements-dev.txt`.
- Explorer cards use elided names and shared icon caches.

### Fixed
- Auto-refresh timer called a method that did not exist, so it never refreshed.
- Explorer never refreshed after AI operations and success toasts never fired.
- Double-clicking a card opened the item twice; context-menu *Delete* did nothing; clicking a tree folder did nothing.
- Saving an API key required a restart; card size and refresh interval settings were never applied;
  `Start with Windows = off` never unregistered.
- Approval was a regex on the model's prose and could be bypassed; `delete_files` on a bare directory could
  delete every file in it without confirmation.
- Folder operations were journaled with the wrong type; write / append / delete were marked non-undoable.
- Voice recording stop blocked the UI for up to 5 s; temporary WAV files were never removed.
- Journal SQLite connection was shared across threads without a lock; purge compared local time with UTC.
- Frozen builds looked for assets in the wrong directory on PyInstaller ≥ 6.

### Removed
- Dead modules: USN journal reader, legacy `.lnk` resolver, timer-based folder monitor, resize grips,
  unused tool-result widget, legacy `dark.qss` / `light.qss`, session-notes docs.

## [1.0.1] — 2026-02

- MSI license UI, publisher metadata, tray / minimize fixes, history panel, single-instance guard.

## [1.0.0] — 2026-02

- Initial release: Recent-items explorer, AI chat with 21 tools, undo journal, PIN lock, light / dark themes.
