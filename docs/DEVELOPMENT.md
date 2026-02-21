# Development Guide

## Quick Start

### Standard Development Mode
```bash
python scripts/run_dev.py
```

### Auto-Restart on File Changes (Recommended!)
```bash
# Install watchdog first
pip install watchdog

# Run with auto-restart
python scripts/run_dev_watch.py
```

This will:
- ✅ Start the application
- 👀 Watch for changes in `src/` and `assets/`
- 🔄 Automatically restart when you save files
- 📝 Show which file triggered the restart

## Development Modes

### 1. Manual Restart (Basic)
**Script:** `scripts/run_dev.py`

**Pros:**
- Simple, no extra dependencies
- Full control over when to restart

**Cons:**
- Must manually stop and restart after changes
- Slower development cycle

**Usage:**
```bash
python scripts/run_dev.py
```

### 2. Auto-Restart (Recommended)
**Script:** `scripts/run_dev_watch.py`

**Pros:**
- ✅ Automatic restart on file save
- ✅ Fast development cycle
- ✅ Watches Python and QSS files
- ✅ Ignores temp files (`.pyc`, `.log`, etc.)

**Cons:**
- Requires `watchdog` package
- Full app restart (loses UI state)

**Usage:**
```bash
# First time: install watchdog
pip install watchdog

# Then run:
python scripts/run_dev_watch.py
```

**What it watches:**
- `src/**/*.py` - All Python source files
- `assets/**/*.qss` - Theme stylesheets

**What it ignores:**
- `.pyc`, `__pycache__`
- `.db`, `.db-journal`, `.log`, `.enc`
- `.git`, `.venv`, `node_modules`

### 3. Theme Hot-Reload (UI Only)
**Script:** `scripts/reload_theme.py`

For quick theme/stylesheet changes without full restart (future feature).

## File Change Detection

The auto-restart watcher triggers on:
- ✅ Python file changes (`.py`)
- ✅ Stylesheet changes (`.qss`)
- ❌ Database changes (ignored)
- ❌ Log files (ignored)
- ❌ Compiled Python (ignored)

## Tips for Effective Development

### 1. Use Auto-Restart for Code Changes
When working on functionality:
```bash
python scripts/run_dev_watch.py
```
Edit your code → Save → App restarts automatically!

### 2. Keep Terminal Visible
The auto-restart shows:
- Which file changed
- App startup logs
- Any errors

### 3. Quick Theme Tweaks
For theme-only changes:
1. Edit `assets/themes/light.qss` or `dark.qss`
2. Save
3. Auto-restart picks it up instantly

### 4. Test After Each Change
Since restart is automatic, you can:
1. Make a small change
2. Save
3. Test immediately
4. Repeat

## Debugging

### App Won't Start
Check the logs in the terminal output from `run_dev_watch.py`

### Too Many Restarts
If the app restarts too frequently:
- Check if you're editing ignored files
- Minimum delay is 1 second between restarts
- Adjust `restart_delay` in `run_dev_watch.py` if needed

### Restart Not Triggering
- Make sure you're editing files in `src/` or `assets/`
- Check file extension (only `.py` and `.qss`)
- Ensure `watchdog` is installed: `pip install watchdog`

## Development Workflow

**Typical workflow with auto-restart:**

```bash
# Terminal 1: Run with auto-restart
cd "I:\Projects\Opaium System Intelligence AI Tool\opaium-system-intelligence-app"
.venv\Scripts\activate
python scripts/run_dev_watch.py

# Terminal 2: Make changes
# Edit files in your IDE
# Save → App restarts automatically!
```

## Performance

**Restart Speed:**
- Cold start: ~3-5 seconds
- Auto-restart: ~2-3 seconds
- You see changes almost immediately

**Resource Usage:**
- Watchdog is lightweight (~5MB RAM)
- No noticeable performance impact

## Hot-Reload Limitations

**Why not true hot-reload?**
Qt/PySide6 applications can't easily hot-reload because:
- Qt objects can't be reloaded in-place
- UI state is lost on reload
- Signals/slots need reconnecting

**What we have instead:**
- Fast automatic restart
- Preserves config/database between restarts
- 2-3 second turnaround time

This is the industry-standard approach for Qt development and works very well in practice!

## Future Improvements

Potential enhancements:
- [ ] Hot-reload for stylesheets only (no restart)
- [ ] State preservation between restarts
- [ ] Selective reload (UI vs logic)
- [ ] Browser-based dev tools
