# OP(AI)UM — Configuration Reference

## Location

```
%APPDATA%\OPAIUM\config.enc      encrypted JSON (Fernet, machine-bound key)
%APPDATA%\OPAIUM\.salt           local salt for the encryption key
```

The file is written atomically and re-created with defaults if it cannot be decrypted (a `.corrupt` backup is
kept). Settings are edited in-app (**Settings**, `Ctrl+,`); the schema below is what is stored.

## Schema (v2)

```json
{
  "config_version": 2,
  "first_run": false,
  "was_maximized": false,
  "appearance": {
    "theme": "system",            // system | light | dark
    "window_width": 1400, "window_height": 900, "window_x": null, "window_y": null,
    "show_hidden_folders": false,
    "card_width": 160, "card_height": 140,
    "explorer_view": "grid",      // grid | list
    "sort_field": "name",         // name | modified | size | type
    "sort_descending": false,
    "folders_first": true,
    "animations_enabled": true
  },
  "refresh": { "auto_refresh_enabled": true, "refresh_interval_seconds": 300 },
  "ai": {
    "api_key_encrypted": "…",
    "ai_model": "gpt-5.2-2025-12-11",
    "api_base_url": "",           // empty = api.openai.com; e.g. http://localhost:11434/v1 for Ollama
    "transcription_model": "gpt-4o-transcribe",
    "folder_depth_mode": "shallow",
    "max_conversation_history": 60,
    "request_timeout": 90,
    "streaming": true,
    "confirm_destructive": true,  // approval dialog before destructive tools
    "max_tool_rounds": 8,
    "voice_auto_send": false
  },
  "auth": {
    "password_type": "pin", "password_hash": "$argon2id$…", "is_configured": false,
    "idle_lock_minutes": 0,       // 0 = never
    "lock_on_minimize_to_tray": false
  },
  "startup": {
    "start_with_windows": false,  // registry Run key with --minimized
    "start_minimized": false,
    "minimize_to_tray": true,     // closing the window keeps the app in the tray
    "show_notifications": true,
    "global_hotkey_enabled": true,
    "global_hotkey": "Ctrl+Shift+Space"
  },
  "undo": { "purge_days": 2, "max_operations": 10000, "keep_content_backups": true },
  "updates": { "check_for_updates": true, "last_check_iso": "", "skipped_version": "" }
}
```

## Command line

| Flag | Effect |
|------|--------|
| `--minimized` | Start hidden in the tray (used by *Start with Windows*) |
| `--log-level LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPAIUM_LOG_LEVEL` | `INFO` | Loguru log level (overridden by `--log-level`) |
| `QT_QPA_PLATFORM` | — | `offscreen` for headless tests |

## Data files

| File | Purpose |
|------|---------|
| `config.enc` | All settings (encrypted) |
| `tracking.db` | NTFS file-id → path tracking for renamed Recent items |
| `undo_journal.db` | Operation history for Undo |
| `conversations.db` | Chat history |
| `backups/` | Copies of files taken before the AI overwrote them (pruned with the journal) |
| `cache/` | Tinted QSS icons per theme |
| `logs/` | `opaium_YYYY-MM-DD.log` (10 MB rotation, 7 days) and `errors.log` |

**Reset**: Settings → Security → *Delete all OP(AI)UM data*, or the *Forgot your PIN?* link on the lock screen,
removes everything above. Your own files are never touched.

## AI endpoints

| Preset | Base URL | Notes |
|--------|----------|-------|
| OpenAI | *(empty)* | Needs an API key |
| Ollama | `http://localhost:11434/v1` | Local, key optional, pick a tool-capable model |
| LM Studio | `http://localhost:1234/v1` | Local |
| OpenRouter | `https://openrouter.ai/api/v1` | Needs an OpenRouter key |
| Groq | `https://api.groq.com/openai/v1` | Needs a Groq key |

Reasoning models (`gpt-5*`, `o*`) reject custom sampling temperature; OP(AI)UM omits it automatically.
