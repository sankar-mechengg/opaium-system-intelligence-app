"""
OP(AI)UM — Prompt Builder

Constructs system prompts and injects folder/file context
for the AI chatbot. Manages the system prompt that defines
the AI's capabilities and behavior.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from src.config.constants import AppConstants


class PromptBuilder:
    """
    Builds system prompts and context messages for the AI.

    The system prompt defines:
    - AI's role and capabilities
    - Available tools and when to use them
    - Safety guidelines (approval is enforced by the app, not by prose)
    - Context about the currently selected folder
    """

    SYSTEM_PROMPT = f"""You are OP(AI)UM — the Omniscient Processor for Adaptive Intelligence & Unified Management. You are the AI assistant embedded in a Windows system-intelligence and file-management application.

## Your Role
You help users understand and manage their files, folders, disks and startup programs through natural language. You act by calling tools.

## Your Capabilities
**Folder Operations:** create, delete (to Recycle Bin), move, copy, rename, scan and analyze folders.
**File Operations:** read (TXT, MD, CSV, code, TEX, PDF, DOCX, PPTX, XLSX), create/write/append (TXT, MD, CSV, code, TEX, DOCX, XLSX), delete to Recycle Bin, move, copy, rename, change extensions, batch operations.
**Analysis & Organization:** count files, sizes, type breakdowns, duplicates, large files, old files, empty folders, metadata, disk usage, startup programs, Recycle Bin status; organize by type/date/pattern, regex renaming, flatten folders.

## How You Work
- When the user asks you to do something, call the tool functions directly — do not describe what you would do, do it.
- NON-DESTRUCTIVE tools (count, size, list, read, find, analyze, disk usage, startup programs) run immediately.
- DESTRUCTIVE tools (rename, delete, move, copy, write, organize, flatten, clean) are intercepted by the app: before anything changes, the user sees a preview dialog listing the exact files affected with Approve/Cancel. You do NOT need to ask "shall I proceed?" in text — call the tool with precise arguments. If a tool result says the user cancelled, acknowledge briefly and offer alternatives.
- Prefer one well-targeted tool call over several vague ones. Always pass absolute Windows paths.
- Never call a destructive tool on a whole directory without narrowing it (filenames, extension, pattern, age...) unless the user explicitly asked for everything in that folder.
- The app refuses operations on protected system locations (Windows, Program Files, drive roots, the user profile root). Do not try to work around this.
- Every destructive result includes an operation_id; when the result is undoable, tell the user they can undo it from the chat or the History tab.

## Important Safety Rules
1. NEVER delete files permanently — deletions go to the Recycle Bin and can be restored.
2. If an operation could affect many files (>20), say so in one sentence before calling the tool.
3. For ambiguous requests (which folder? which files?), ask one short clarifying question instead of guessing.
4. Never invent file names or results — only report what tool results returned.

## Your Personality
- Concise and direct. Lead with the answer, then details.
- Use clear formatting — bullet points for file lists, tables for comparisons, code formatting for paths.
- If something fails, explain why in plain language and suggest the next step.
- You are a power tool, not a chatbot. Focus on getting things done.
- NEVER say "I don't have a function for that" — check all your available tools first.

## Context
- App: {AppConstants.APP_NAME} v{AppConstants.APP_VERSION}
- Platform: Windows
- All file paths use Windows-style backslashes.
"""

    @staticmethod
    def build_system_prompt(
        selected_folder: str | None = None,
        scan_mode: str = "shallow",
        confirm_destructive: bool = True,
    ) -> str:
        """
        Build the full system prompt with optional folder context.

        Args:
            selected_folder: Currently selected folder (or file) path.
            scan_mode: 'shallow' or 'recursive'.
            confirm_destructive: Whether the app shows approval dialogs.

        Returns:
            Complete system prompt string.
        """
        prompt = PromptBuilder.SYSTEM_PROMPT

        if not confirm_destructive:
            prompt += (
                "\n\n## Confirmation Mode\nThe user has turned OFF confirmation dialogs for destructive "
                "operations. Be extra careful: restate exactly what you are about to change in one line "
                "before calling a destructive tool, and never widen the scope beyond what was asked."
            )

        prompt += f"\n- Now: {datetime.now().strftime('%A, %d %B %Y %H:%M')}"

        if selected_folder and os.path.isdir(selected_folder):
            folder_info = PromptBuilder._get_folder_context(selected_folder, scan_mode)
            prompt += f"\n\n## Current Folder Context\n{folder_info}"
        elif selected_folder and os.path.isfile(selected_folder):
            prompt += (
                "\n\n## Current File Context\n"
                f"- **Selected File**: `{selected_folder}`\n"
                f"- **Parent Folder**: `{Path(selected_folder).parent}`"
            )

        return prompt

    @staticmethod
    def _get_folder_context(folder_path: str, scan_mode: str) -> str:
        """Generate context information about the selected folder."""
        path = Path(folder_path)
        lines = [
            f"- **Selected Folder**: `{folder_path}`",
            f"- **Folder Name**: {path.name or str(path)}",
            f"- **Parent**: `{path.parent}`",
            f"- **Scan Mode**: {scan_mode}",
        ]

        # Quick stats
        try:
            entries = list(os.scandir(folder_path))
            folders = sum(1 for e in entries if e.is_dir(follow_symlinks=False))
            files = sum(1 for e in entries if e.is_file(follow_symlinks=False))
            lines.append(f"- **Direct Contents**: {folders} folders, {files} files")
            names = sorted(e.name for e in entries)[:40]
            if names:
                lines.append(f"- **First entries**: {', '.join(names)}")
        except (OSError, PermissionError):
            lines.append("- **Direct Contents**: Unable to read")

        # Drive info
        try:
            drive = os.path.splitdrive(folder_path)[0]
            if drive:
                from src.utils.path_utils import PathUtils
                from src.utils.windows_api import WindowsAPI

                total, used, free = WindowsAPI.get_disk_free_space(drive)
                lines.append(
                    f"- **Drive {drive}**: {PathUtils.format_size(free)} free of {PathUtils.format_size(total)}"
                )
        except Exception:
            pass

        return "\n".join(lines)

    @staticmethod
    def build_user_message(
        user_text: str,
        selected_folder: str | None = None,
        selected_files: list[str] | None = None,
    ) -> str:
        """
        Build a user message with optional file selection context.
        """
        parts = []

        if selected_folder:
            parts.append(f"[Working in: {selected_folder}]")

        if selected_files:
            if len(selected_files) <= 10:
                file_list = ", ".join(Path(f).name for f in selected_files)
                parts.append(f"[Selected files: {file_list}]")
            else:
                parts.append(f"[{len(selected_files)} files selected]")

        parts.append(user_text)
        return "\n".join(parts)

    @staticmethod
    def strip_context_prefix(text: str) -> str:
        """Remove the [Working in: ...] / [Selected files: ...] prefixes for display."""
        lines = text.split("\n")
        while lines and lines[0].startswith("[") and lines[0].endswith("]"):
            lines.pop(0)
        return "\n".join(lines).strip() or text

    @staticmethod
    def build_tool_result_context(
        tool_name: str,
        result: dict,
        success: bool = True,
    ) -> str:
        """Format a tool result for display in the chat."""
        if not success:
            return f"Operation failed: {result.get('error', 'Unknown error')}"

        if "count" in tool_name or "summary" in tool_name:
            return PromptBuilder._format_count_result(result)
        elif "plan" in result:
            return PromptBuilder._format_plan(result)
        else:
            return str(result)

    @staticmethod
    def _format_count_result(result: dict) -> str:
        """Format file count/summary results."""
        lines = []
        for key, value in result.items():
            if key.startswith("_"):
                continue
            label = key.replace("_", " ").title()
            lines.append(f"- {label}: {value}")
        return "\n".join(lines)

    @staticmethod
    def _format_plan(result: dict) -> str:
        """Format an operation plan for user approval."""
        plan = result.get("plan", [])
        lines = ["**Proposed Operation:**\n"]
        for i, step in enumerate(plan, 1):
            lines.append(f"{i}. {step}")
        return "\n".join(lines)
