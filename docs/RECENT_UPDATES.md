# Recent Updates - February 21, 2026

## 1. Refresh Button Functionality ✅

**Status:** Already working correctly

The refresh button rescans the Windows Recent folder and displays any newly accessed files or folders. This functionality was already implemented and working as expected.

**How it works:**
- When clicked, it calls `refresh_data()` which runs `_load_data()` in a background thread
- `_load_data()` uses `RecentParser` to scan Windows Recent folder for new `.lnk` files
- New items are automatically added to the display
- Items are also tracked in the database for rename resolution

## 2. Taskbar Icon Fix ✅

**Issue:** Windows taskbar was showing the Python icon instead of the Opaium logo

**Solution:**
1. Created `scripts/convert_icon.py` to convert the PNG logo to ICO format
2. Generated `assets/icons/opaium_logo_nobg.ico` with multiple sizes (16x16, 32x32, 48x48, 256x256)
3. Updated `src/main.py` to:
   - Prefer `.ico` file over `.png` for Windows compatibility
   - Set Windows App User Model ID for taskbar icon separation
   - Use `ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID()` for proper Windows taskbar icon display

**Files Changed:**
- `src/main.py` - Enhanced icon loading logic and added Windows-specific taskbar handling
- `scripts/convert_icon.py` - New utility script to convert PNG to ICO
- `assets/icons/opaium_logo_nobg.ico` - New multi-resolution icon file

**Result:** The taskbar will now show the Opaium logo instead of the generic Python icon.

## 3. Custom AI Questions ✅

**Feature:** Added "Custom Question..." option to the "Ask AI" context menu

**Implementation:**
- Added a separator followed by "Custom Question..." at the bottom of both folder and file AI menus
- When clicked, opens an input dialog where users can type any custom question
- The custom question is then sent to the AI chat with the selected file/folder as context

**Files Changed:**
- `src/ui/widgets/context_menu.py`:
  - Added `QInputDialog` import
  - Added "Custom Question..." menu items to both `build_folder_menu()` and `build_file_menu()`
  - Added `_ask_custom_question()` method to handle the input dialog

**User Experience:**
1. Right-click on any file or folder
2. Hover over "Ask AI..."
3. At the bottom, click "Custom Question..."
4. Enter your custom question in the dialog
5. Click OK - the question is sent to AI chat with the file/folder context

**Example Custom Questions:**
- "What programming languages are used in this project?"
- "Can you find any TODO comments in this folder?"
- "What's the oldest file in here?"
- "Suggest ways to organize this folder better"

## Testing Instructions

1. **Restart the app** to see the new taskbar icon
2. **Open some new files/folders** in Windows Explorer, then click the Refresh button in the app to verify they appear
3. **Right-click on a folder** in the Recent view, go to "Ask AI..." → "Custom Question..." and try asking a custom question

## Notes

- The icon fix requires the `.ico` file to exist (already created by running `convert_icon.py`)
- Custom questions work with both files and folders
- The AI receives context about which file/folder you're asking about
- All three features are now fully implemented and ready to test
