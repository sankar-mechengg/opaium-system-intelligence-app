"""
OP(AI)UM — Function Registry

Registers all AI-callable tool functions and generates
OpenAI function calling schema definitions. Acts as the
bridge between the AI model and the actual tool implementations.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from loguru import logger


class ToolDefinition:
    """A registered tool with its schema and implementation."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Any],
        is_destructive: bool = False,
        requires_confirmation: bool = False,
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.is_destructive = is_destructive
        self.requires_confirmation = requires_confirmation

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class FunctionRegistry:
    """
    Registry of all AI-callable tools.

    Tools are categorized as:
    - Safe: Execute immediately (count, list, size, analyze)
    - Destructive: Require user confirmation (rename, delete, move)
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Any],
        is_destructive: bool = False,
    ) -> None:
        """Register a tool function."""
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            is_destructive=is_destructive,
            requires_confirmation=is_destructive,
        )
        logger.debug(f"Registered tool: {name} (destructive={is_destructive})")

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI function schemas for all registered tools."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """
        Execute a registered tool.

        Args:
            name: Tool function name.
            arguments: Tool arguments.

        Returns:
            Tool result.

        Raises:
            ValueError: If tool not found.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")

        logger.info(f"Executing tool: {name}")
        return tool.handler(**arguments)

    def is_destructive(self, name: str) -> bool:
        """Check if a tool is destructive (requires confirmation)."""
        tool = self._tools.get(name)
        return tool.is_destructive if tool else False

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def register_all_tools(self) -> None:
        """
        Register all built-in AI tools.
        Called during AI engine initialization.
        """
        from src.ai.tools.file_counter import FileCounterTool
        from src.ai.tools.file_sizer import FileSizerTool
        from src.ai.tools.type_summarizer import TypeSummarizerTool
        from src.ai.tools.duplicate_finder import DuplicateFinderTool
        from src.ai.tools.large_file_finder import LargeFileFinderTool
        from src.ai.tools.empty_folder_cleaner import EmptyFolderCleanerTool
        from src.ai.tools.file_age_analyzer import FileAgeAnalyzerTool
        from src.ai.tools.file_renamer import FileRenamerTool
        from src.ai.tools.file_deleter import FileDeleterTool
        from src.ai.tools.file_mover import FileMoverTool
        from src.ai.tools.file_copier import FileCopierTool
        from src.ai.tools.smart_organizer import SmartOrganizerTool
        from src.ai.tools.date_organizer import DateOrganizerTool
        from src.ai.tools.folder_flattener import FolderFlattenerTool
        from src.ai.tools.regex_renamer import RegexRenamerTool
        from src.ai.tools.extension_changer import ExtensionChangerTool
        from src.ai.tools.metadata_reader import MetadataReaderTool
        from src.ai.tools.recycle_bin_tool import RecycleBinTool
        from src.ai.tools.startup_tool import StartupTool
        from src.ai.tools.disk_usage_tool import DiskUsageTool
        from src.ai.tools.folder_operations import FolderOperationsTool
        from src.ai.tools.file_content import FileContentTool

        # Instantiate and register all tools
        tool_classes = [
            FileCounterTool, FileSizerTool, TypeSummarizerTool,
            DuplicateFinderTool, LargeFileFinderTool, EmptyFolderCleanerTool,
            FileAgeAnalyzerTool, FileRenamerTool, FileDeleterTool,
            FileMoverTool, FileCopierTool, SmartOrganizerTool,
            DateOrganizerTool, FolderFlattenerTool, RegexRenamerTool,
            ExtensionChangerTool, MetadataReaderTool, RecycleBinTool,
            StartupTool, DiskUsageTool, FolderOperationsTool, FileContentTool,
        ]

        for tool_cls in tool_classes:
            tool = tool_cls()
            self.register(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
                handler=tool.execute,
                is_destructive=tool.is_destructive,
            )

        logger.info(f"Registered {self.tool_count} AI tools.")
