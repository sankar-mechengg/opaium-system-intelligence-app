# OP(AI)UM — Configuration Reference

## Config File Location

```
%APPDATA%\OPAIUM\config.json
```

## Settings Structure

```json
{
  "appearance": {
    "theme": "dark",
    "card_width": 160,
    "card_height": 140,
    "show_hidden_folders": false
  },
  "ai": {
    "model": "gpt-4.1-mini",
    "speech_model": "gpt-4o-transcribe",
    "max_tokens": 2048,
    "temperature": 0.3,
    "api_key_encrypted": "gAAAAB..."
  },
  "refresh": {
    "auto_refresh_enabled": true,
    "auto_refresh_interval_min": 5
  },
  "startup": {
    "start_with_windows": true,
    "start_minimized": false,
    "minimize_to_tray": false,
    "close_to_tray": false
  },
  "undo": {
    "max_history": 100,
    "purge_after_days": 7
  },
  "auth": {
    "password_type": "pin",
    "password_hash": "$argon2id$..."
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPAIUM_ENV` | `production` | `development` enables debug logging |
| `OPAIUM_LOG_LEVEL` | `INFO` | Loguru log level |
| `OPAIUM_DATA_DIR` | `%APPDATA%/OPAIUM` | Override data directory |

## Data Files

| File | Location | Purpose |
|------|----------|---------|
| `config.json` | `%APPDATA%/OPAIUM/` | All settings |
| `auth.json` | `%APPDATA%/OPAIUM/` | Password hash |
| `tracking.db` | `%APPDATA%/OPAIUM/` | SQLite file tracking DB |
| `undo_journal.db` | `%APPDATA%/OPAIUM/` | SQLite undo history |
| `opaium.log` | `%APPDATA%/OPAIUM/logs/` | Application log |

## Model Options

### Chat Models
- `gpt-4.1` — Most capable, higher cost
- `gpt-4.1-mini` — Good balance (recommended)
- `gpt-4.1-nano` — Fastest, lowest cost
- `gpt-4o` — Previous generation
- `gpt-4o-mini` — Previous generation mini
- `o4-mini` — Reasoning model

### Speech Models
- `gpt-4o-transcribe` — Latest, most accurate
- `whisper-1` — Original Whisper model
