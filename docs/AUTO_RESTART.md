# Auto-Restart Development Mode 🔄

## Quick Start

```bash
# Install watchdog (first time only)
pip install watchdog

# Run with auto-restart
python scripts/run_dev_watch.py
```

## What You'll See

```
==============================================================
  OP(AI)UM — Development Mode with Auto-Restart
==============================================================
  Root: I:\Projects\...\opaium-system-intelligence-app
  Python: 3.13.7

  👀 Watching for changes...
  💡 Press Ctrl+C to stop
==============================================================

[App starts normally...]

[When you save a file:]
============================================================
📝 File changed: src/ui/chat/chat_panel.py
🔄 Restarting application...
============================================================

[App restarts automatically!]
```

## How It Works

1. **Starts your app** normally
2. **Watches for file changes** in:
   - `src/**/*.py` (all Python files)
   - `assets/**/*.qss` (theme stylesheets)
3. **Automatically restarts** when you save
4. **Ignores** temp files (`.pyc`, `.log`, etc.)

## Benefits

✅ **Instant feedback** - See your changes in 2-3 seconds  
✅ **No manual restart** - Just save and test  
✅ **Full app reload** - Ensures clean state  
✅ **Smart filtering** - Only watches relevant files  

## Tips

### Make Small Changes
Since restart is fast, you can work iteratively:
1. Make a small change
2. Save
3. Test immediately
4. Repeat

### Keep Terminal Visible
Watch for:
- Which file triggered restart
- App startup messages
- Any errors

### Edit and Save
Just work normally in your IDE - the watcher handles everything!

## Stopping

Press `Ctrl+C` in the terminal to stop both the watcher and app.

## Troubleshooting

### Watcher not installed
```
pip install watchdog
```

### Too many restarts
Minimum delay is 1 second. If you're saving too fast, only the last save triggers restart.

### Restart not happening
- Check you're editing files in `src/` or `assets/`
- Only `.py` and `.qss` files trigger restart
- Make sure the file saved successfully

## Alternative: Manual Mode

If you prefer manual control:
```bash
python scripts/run_dev.py
```

Then restart manually when needed.
