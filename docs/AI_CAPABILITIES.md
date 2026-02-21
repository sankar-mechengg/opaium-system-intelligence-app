# AI Capabilities - Complete Filesystem Control

The OP(AI)UM AI assistant has **FULL ROOT-LEVEL ACCESS** to the filesystem and can perform any operation you request.

## Overview

The AI is not limited in what it can do with files and folders. It has complete control over:
- Reading, writing, and modifying files
- Creating, deleting, moving, and copying folders
- Batch operations on any number of files/folders
- Content manipulation and organization

## Available Operations

### Folder Operations (`folder_operations`)

**Create Folders**
```
"Create a folder called ProjectX in D:\Work"
"Make a new folder at C:\Users\Me\Documents\2026\Reports"
```

**Delete Folders** (to Recycle Bin)
```
"Delete the empty folder I:\Testie"
"Remove the folder D:\OldProjects (including all contents)"
"Delete all empty folders in D:\Downloads"
```

**Move Folders**
```
"Move D:\TempFolder to E:\Archive"
"Move this folder to C:\Projects"
```

**Copy Folders**
```
"Copy D:\Project to E:\Backup\Project"
"Duplicate this folder to another location"
```

**Rename Folders**
```
"Rename this folder to 'CompletedProjects'"
"Change the folder name from 'temp' to 'Production'"
```

### File Content Operations (`file_content`)

**Read Files**
```
"Read the contents of config.txt"
"Show me what's in README.md"
"What does this file say?"
```

**Create Files**
```
"Create a file called notes.txt with the text 'Meeting at 3pm'"
"Make a new file D:\test.py with a hello world script"
```

**Write/Overwrite Files**
```
"Write 'New content here' to file.txt"
"Overwrite config.json with the default settings"
```

**Append to Files**
```
"Add 'New line' to the end of log.txt"
"Append today's notes to diary.txt"
```

### File Operations (Existing Tools)

**Delete Files** (`delete_files`)
```
"Delete all .tmp files in this folder"
"Remove files older than 30 days"
"Delete file.txt"
```

**Move Files** (`move_files`)
```
"Move all .pdf files to D:\PDFs"
"Move these files to Archive folder"
```

**Copy Files** (`copy_files`)
```
"Copy all images to E:\Backup"
"Duplicate important.docx"
```

**Rename Files** (`rename_files`, `regex_renamer`)
```
"Rename IMG001.jpg to Photo_2026.jpg"
"Add prefix 'BACKUP_' to all files"
"Replace spaces with underscores in all filenames"
```

### Analysis Tools

**Count & List** (`count_files`)
```
"How many files are in this folder?"
"List all .py files"
"Count files by extension"
```

**Size Analysis** (`file_sizer`, `disk_usage_tool`)
```
"What's the total size of this folder?"
"Show me disk space usage"
"Which files are taking up the most space?"
```

**Find Duplicates** (`duplicate_finder`)
```
"Find duplicate files"
"Show me duplicate photos"
```

**Find Large Files** (`large_file_finder`)
```
"Find files larger than 100MB"
"Show me the biggest files"
```

**Type Summary** (`type_summarizer`)
```
"What types of files are here?"
"Summarize files by extension"
```

**Empty Folders** (`clean_empty_folders`)
```
"Find all empty folders"
"Remove empty directories"
```

**File Age** (`file_age_analyzer`)
```
"Show oldest files"
"Find files modified this week"
```

### Organization Tools

**Smart Organizer** (`smart_organizer`)
```
"Organize files by type"
"Sort files into folders based on extension"
```

**Date Organizer** (`date_organizer`)
```
"Organize by date created"
"Sort photos by year/month"
```

**Flatten Folders** (`folder_flattener`)
```
"Flatten all nested folders"
"Bring all files to the top level"
```

**Extension Changer** (`extension_changer`)
```
"Change all .txt files to .md"
"Rename .jpeg to .jpg"
```

**Metadata Reader** (`metadata_reader`)
```
"Show me EXIF data for this photo"
"Read file metadata"
```

### System Tools

**Recycle Bin** (`recycle_bin_tool`)
```
"Empty the recycle bin"
"How many items are in the recycle bin?"
```

**Startup** (`startup_tool`)
```
"Show me startup programs"
"List what runs at startup"
```

## How It Works

### Safety Features

1. **Recycle Bin Protection**: All deletions go to the Recycle Bin, never permanent deletion
2. **Preview Before Action**: Destructive operations show a preview and require approval
3. **Batch Operation Warnings**: Large operations (>20 files) trigger warnings
4. **Error Recovery**: If something fails, the AI explains why and suggests alternatives

### Confirmation Flow

For destructive operations:

1. **User Request**: "Delete the folder I:\Testie"
2. **AI Preview**: Shows what will be deleted (size, contents, location)
3. **User Approval**: User reviews and approves
4. **Execution**: AI performs the operation
5. **Confirmation**: AI reports success/failure

### Non-Destructive Operations

These execute immediately without confirmation:
- Reading file contents
- Counting files
- Analyzing sizes
- Finding duplicates
- Listing contents
- Showing metadata

## Example Workflows

### Cleaning Up Downloads

**User**: "I need to clean up my downloads folder. Find and delete all files older than 90 days, but show me what you'll delete first."

**AI**: 
1. Uses `file_age_analyzer` to find old files
2. Shows preview with list of files and total size
3. Waits for approval
4. Uses `delete_files` to move them to Recycle Bin
5. Reports how many files were removed

### Organizing Photos

**User**: "Organize all photos in D:\Pictures by year and month"

**AI**:
1. Uses `date_organizer` to analyze photo dates
2. Shows proposed folder structure (2024/01/, 2024/02/, etc.)
3. Waits for approval
4. Creates folders and moves files
5. Reports success and new organization

### Creating Project Structure

**User**: "Create a project folder structure at D:\NewProject with src, tests, docs, and assets subfolders"

**AI**:
1. Uses `folder_operations` with operation "create" for each folder:
   - D:\NewProject
   - D:\NewProject\src
   - D:\NewProject\tests
   - D:\NewProject\docs
   - D:\NewProject\assets
2. Uses `file_content` to create initial files like README.md
3. Reports completion

### Backup Important Files

**User**: "Copy all .docx and .xlsx files from D:\Work to E:\Backup\$(date) and create a backup log"

**AI**:
1. Uses `copy_files` to copy matching files
2. Uses `folder_operations` to create date-stamped backup folder
3. Uses `file_content` to create backup_log.txt with list of backed up files
4. Reports backup completion with statistics

## Asking for Help

The AI understands natural language. Just tell it what you want:

**Instead of**: "Can you help me with..."
**Just say**: "Delete all empty folders"

**Instead of**: "Is it possible to..."
**Just say**: "Organize these files by type"

The AI will figure out which tools to use and how to accomplish your request.

## Error Handling

If something goes wrong:

**Permission Denied**
- AI will explain which folder/file had permission issues
- Suggests running as administrator if needed

**File in Use**
- AI reports which file is locked
- Suggests closing the application using the file

**Path Not Found**
- AI checks if path exists
- Suggests alternatives or asks for correct path

## Limitations

1. **Binary Files**: Can't read/edit binary files (images, executables) - only text files
2. **File Size**: Reading files is limited to 1MB by default (configurable)
3. **System Files**: Cannot modify Windows system files
4. **Permissions**: Respects Windows file permissions and UAC

## Power User Tips

1. **Chain Operations**: You can ask for multiple operations in one request
   - "Find all .log files, sort by size, and delete files larger than 10MB"

2. **Conditional Logic**: The AI understands conditions
   - "Delete .tmp files but keep ones modified today"

3. **Patterns**: Use wildcards and patterns
   - "Rename all files starting with 'IMG_' to 'Photo_'"

4. **Custom Context**: Right-click folders/files and use "Ask AI → Custom Question" for context-aware operations

5. **Batch Approvals**: For large operations, review the preview carefully before approving

## Trust & Safety

The AI is designed to be powerful but safe:
- ✅ Uses Recycle Bin instead of permanent deletion
- ✅ Shows previews before destructive actions
- ✅ Requires explicit approval for changes
- ✅ Logs all operations for review
- ✅ Preserves file integrity (no corruption)
- ✅ Warns about large-scale operations

**Remember**: You're in control. The AI won't do anything destructive without your approval.
