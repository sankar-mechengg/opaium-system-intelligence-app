"""
OP(AI)UM — Prompt Builder

Constructs system prompts and injects folder/file context
for the AI chatbot. Manages the system prompt that defines
the AI's capabilities and behavior.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from loguru import logger

from src.config.constants import AppConstants


class PromptBuilder:
    """
    Builds system prompts and context messages for the AI.

    The system prompt defines:
    - AI's role and capabilities
    - Available tools and when to use them
    - Safety guidelines (always preview before destructive ops)
    - Context about the currently selected folder
    """

    SYSTEM_PROMPT = f"""You are OP(AI)UM — the Omniscient Processor for Adaptive Intelligence & Unified Management. You are an AI assistant embedded in a Windows file management application.

## Your Role
You help users manage their files and folders through natural language commands. You can count files, rename, move, copy, delete, organize, analyze disk usage, find duplicates, and more.

## How You Work
- When the user asks you to do something, you use the available tool functions to execute the operation.
- For NON-DESTRUCTIVE operations (counting files, showing sizes, listing contents, finding duplicates), execute immediately and report results.
- For DESTRUCTIVE operations (rename, delete, move, reorganize), ALWAYS show a preview/plan first and ask for confirmation before executing. Format the plan clearly.
- You have access to the user's filesystem through the provided tools. Use them to answer questions and perform operations.

## Important Safety Rules
1. NEVER delete files permanently — always use the recycle bin (send2trash).
2. ALWAYS show a plan before batch operations and wait for user approval.
3. If an operation could affect many files (>20), warn the user about the scope.
4. Preserve file integrity — never modify file contents, only filesystem operations.
5. For ambiguous requests, ask for clarification rather than guessing.

## Your Personality
- Be concise and direct. Don't over-explain.
- Use clear formatting — bullet points for file lists, tables for comparisons.
- If something fails, explain why and suggest alternatives.
- You're a power tool, not a chatbot. Focus on getting things done.

## Context
- App: {AppConstants.APP_NAME} v{AppConstants.APP_VERSION}
- Platform: Windows
- All file paths use Windows-style backslashes.
"""

    @staticmethod
    def build_system_prompt(
        selected_folder: Optional[str] = None,
        scan_mode: str = "shallow",
    ) -> str:
        """
        Build the full system prompt with optional folder context.

        Args:
            selected_folder: Currently selected folder path.
            scan_mode: 'shallow' or 'recursive'.

        Returns:
            Complete system prompt string.
        """
        prompt = PromptBuilder.SYSTEM_PROMPT

        if selected_folder and os.path.isdir(selected_folder):
            folder_info = PromptBuilder._get_folder_context(selected_folder, scan_mode)
            prompt += f"\n\n## Current Folder Context\n{folder_info}"

        return prompt

    @staticmethod
    def _get_folder_context(folder_path: str, scan_mode: str) -> str:
        """Generate context information about the selected folder."""
        path = Path(folder_path)
        lines = [
            f"- **Selected Folder**: `{folder_path}`",
            f"- **Folder Name**: {path.name}",
            f"- **Parent**: `{path.parent}`",
            f"- **Scan Mode**: {scan_mode} (user can toggle between shallow/recursive)",
        ]

        # Quick stats
        try:
            entries = list(os.scandir(folder_path))
            folders = sum(1 for e in entries if e.is_dir(follow_symlinks=False))
            files = sum(1 for e in entries if e.is_file(follow_symlinks=False))
            lines.append(f"- **Direct Contents**: {folders} folders, {files} files")
        except (OSError, PermissionError):
            lines.append("- **Direct Contents**: Unable to read")

        # Drive info
        try:
            drive = os.path.splitdrive(folder_path)[0]
            if drive:
                from src.utils.windows_api import WindowsAPI
                total, used, free = WindowsAPI.get_disk_free_space(drive)
                from src.utils.path_utils import PathUtils
                lines.append(
                    f"- **Drive {drive}**: {PathUtils.format_size(free)} free "
                    f"of {PathUtils.format_size(total)}"
                )
        except Exception:
            pass

        return "\n".join(lines)

    @staticmethod
    def build_user_message(
        user_text: str,
        selected_folder: Optional[str] = None,
        selected_files: Optional[list[str]] = None,
    ) -> str:
        """
        Build a user message with optional file selection context.

        Args:
            user_text: The user's message.
            selected_folder: Currently active folder.
            selected_files: List of selected file paths.

        Returns:
            Enriched user message.
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
    def build_tool_result_context(
        tool_name: str,
        result: dict,
        success: bool = True,
    ) -> str:
        """Format a tool result for display in the chat."""
        if not success:
            return f"Operation failed: {result.get('error', 'Unknown error')}"

        # Format based on tool type
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
        lines.append("\nApprove this operation? (yes/no)")
        return "\n".join(lines)
