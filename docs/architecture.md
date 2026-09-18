# OP(AI)UM — Architecture Overview

## Design Principles

1. **Separation of concerns** — UI, AI, core (filesystem), services, undo and config are independent packages.
2. **Enforced approval** — destructive AI tools are gated *in code* (executor level), never by prompt wording.
3. **Everything is journaled** — AI and Explorer changes are recorded and reversible from History.
4. **Graceful degradation** — the app works without an API key, without admin rights and without psutil/pywin32
   (features that need them simply report so).
5. **Windows-native** — DWM frame, Snap Layouts, Shell COM, Recycle Bin, registry, toasts, global hotkey.

---

## Module map

```
main.py                 entry point: logging, crash hook, single instance, QApplication
app.py                  OpAIUMApp: theme, first-run / lock screen, main window, tray, services
services/               update_checker, hotkey (RegisterHotKey), notifier (toasts), idle_monitor
ui/theme.py             ThemeManager: tokens -> base.qss, system theme following
ui/native_window.py     NativeFramelessMixin: WM_NCCALCSIZE / WM_NCHITTEST, DWM shadow & corners
ui/main_window.py       MainWindow: title bar, update banner, 4 panels, status bar, shortcuts
  ui/dashboard/         DashboardPanel: live stats (psutil), drives, folder sizes, activity, startup
  ui/explorer/          ExplorerPanel: toolbar+breadcrumb, tree, card grid / list view, preview
  ui/chat/              ChatPanel: streaming bubbles, tool cards, approval dialog, voice, sidebar
  ui/history/           HistoryPanel: journal rows with Undo
  ui/settings/          Appearance / General / AI / Security tabs
ai/ai_engine.py         AIEngine (QObject): background tool loop, signals to UI, approval broker
ai/openai_client.py     OpenAI-compatible client: streaming, tool-call delta assembly, model quirks
ai/tool_executor.py     PathGuard + approval gate + journal recording around FunctionRegistry
ai/safety.py            PathGuard (protected locations), ApprovalRequest / ApprovalBroker
ai/tools/               22 BaseTool implementations (preview() + execute())
core/                   recent_parser, directory_scanner, folder_monitor (watchdog), recycle_bin (COM),
                        disk_utils, startup_manager, system_stats, tracking_db
undo/                   operation_journal (SQLite), undo_manager, backup_store, auto_purge
config/                 constants (version from src/version.py), defaults (pydantic), crypto, config_manager
auth/                   auth_manager (Argon2id), auth_screen (progressive lockout), first_run_setup
```

---

## Data flow

### Explorer
```
Home view:   Windows Recent (.lnk) -> RecentParser -> RecentItem -> CardGridView (time groups)
Browse view: DirectoryScanner.scan(path) -> RecentItem -> CardGridView (Folders / Files) or FileListView
             DirectoryWatcher (watchdog) -> debounced refresh while a folder is open
Native ops:  rename / delete-to-bin / new folder -> OperationJournal -> History (undoable)
```

### AI turn
```
user text -> PromptBuilder (folder context) -> ConversationManager
  -> AIEngine (thread pool) -> OpenAIClient.chat_with_tool_loop (streaming)
       text deltas ------------------------> ChatPanel streaming bubble
       tool call -> ToolExecutorWithJournal
            PathGuard.find_protected()  -> refused if protected
            tool.preview()              -> ApprovalRequest -> ApprovalDialog (UI thread) -> resolve
            tool.execute()              -> ToolResult (+ OperationRecord -> journal id)
       tool result ---------------------> ToolCard (status, summary, Undo)
  -> transcript (assistant tool calls + tool results + answer) appended to memory
```

### Undo
```
HistoryPanel / ToolCard -> UndoManager.undo_by_id
  rename/move/organize  -> reverse moves
  delete                -> RecycleBinManager.restore (Shell.Application verb)
  write/append          -> BackupStore restore (copy taken before the change)
  create folder/file    -> remove
  clean empty folders   -> recreate
```

---

## Threading

- All filesystem scans, AI requests, update checks and dashboard snapshots run on `QThreadPool`
  (`utils/thread_pool.Worker`) and report back through Qt signals (queued to the UI thread).
- Approval is synchronous for the worker: it blocks on `ApprovalRequest.wait()` while the UI thread shows the
  dialog and calls `resolve()`.
- SQLite journals use one connection guarded by an `RLock` (`check_same_thread=False`).

---

## Key technologies

| Component | Technology |
|-----------|-----------|
| UI | PySide6 (Qt 6), Fusion base style + token QSS |
| Window chrome | Win32 `WM_NCCALCSIZE`/`WM_NCHITTEST`, `DwmExtendFrameIntoClientArea`, rounded corners |
| AI | OpenAI Chat Completions with tools (streaming); any OpenAI-compatible base URL |
| Speech | gpt-4o-transcribe / whisper-1 |
| Password hashing | Argon2id (time=3, memory=64 MB) |
| Encryption | Fernet, key = PBKDF2(machine id, local salt) |
| Storage | SQLite (WAL) for journal, tracking and conversations |
| Shell | pywin32 COM (`Shell.Application`, `IShellLink`), `send2trash` |
| Live stats | psutil |
| Packaging | PyInstaller → ZIP + WiX MSI (GitHub Releases), optional Inno Setup EXE |

---

## Security model

- **Lock** — optional PIN/password (Argon2id). Progressive lockout after 5 failures. Idle auto-lock and
  Ctrl+L. Forgotten credentials → documented full data reset (files are never touched).
- **API key** — encrypted with a machine-bound Fernet key in `%APPDATA%\OPAIUM\config.enc`; only sent to the
  configured provider.
- **File operations** — protected locations are refused outright; every destructive tool shows a real preview
  and needs explicit approval (setting-controlled); deletions go to the Recycle Bin; content is backed up before
  overwrite; everything is journaled.
