# OP(AI)UM — Architecture Overview

## Design Principles

1. **Separation of Concerns** — UI, AI, Core, and Config are independent modules
2. **Preview Before Execute** — All destructive operations show a preview
3. **Everything is Undoable** — Operations are journaled for reversal
4. **Graceful Degradation** — App works without AI key, admin privileges, or NTFS features
5. **Windows-Native** — Uses Win32 APIs for deep OS integration

---

## Module Dependency Graph

```
main.py → app.py → MainWindow
                      ├── ExplorerPanel → RecentParser, TrackingDB, FileScanner
                      ├── ChatPanel → AIEngine → FunctionRegistry → Tools
                      ├── HistoryPanel → UndoManager → UndoJournal
                      └── SettingsDialog → ConfigManager → CryptoManager
```

---

## Data Flow

### Recent Items
```
Windows Recent (.lnk files)
  → RecentParser (resolves .lnk targets)
    → LnkResolver (COM Shell API + pylnk3 fallback)
      → RecentItem models
        → CardGridView (grouped by TimeGroup)
```

### AI Operations
```
User message
  → ConversationManager (history)
    → AIEngine (OpenAI GPT function calling)
      → FunctionRegistry (tool dispatch)
        → BaseTool.preview() → ApprovalDialog
        → BaseTool.execute() → ToolResult
          → UndoJournal (operation record)
          → ToolResultWidget (display in chat)
```

### Folder Tracking
```
FolderMonitor (QTimer @ 30s)
  → USNJournalReader (NTFS changes)
  → TrackingDB (SQLite, file_id → path mapping)
    → Detects renames/moves by file_id
```

---

## Key Technologies

| Component | Technology |
|-----------|-----------|
| UI Framework | PySide6 (Qt 6) |
| AI Engine | OpenAI GPT-4 Function Calling |
| Speech | OpenAI Whisper / gpt-4o-transcribe |
| Password Hashing | Argon2id (time=3, memory=64MB) |
| Encryption | Fernet (AES-128-CBC) |
| Database | SQLite (WAL mode) |
| .lnk Resolution | COM Shell API (pythoncom) + pylnk3 |
| Filesystem | NTFS USN Journal, GetFileInformationByHandle |
| Packaging | PyInstaller + Inno Setup |

---

## Security Model

### Authentication
- User sets PIN (4-8 digits) or password (6+ chars) on first run
- Password hashed with Argon2id (time_cost=3, memory_cost=64MB, parallelism=4)
- Salt includes machine binding (hostname + username)
- Hash stored in `%APPDATA%/OPAIUM/auth.json`
- Lock screen appears on every launch

### API Key Storage
- Encrypted with Fernet (AES-128-CBC)
- Encryption key derived from PBKDF2(machine_id + app_salt)
- Stored in `%APPDATA%/OPAIUM/config.json` (encrypted)
- Never transmitted except to OpenAI API

### File Operations
- All destructive operations require explicit approval
- Operations logged to undo journal with source/dest paths
- Deletions go to Recycle Bin (recoverable)
