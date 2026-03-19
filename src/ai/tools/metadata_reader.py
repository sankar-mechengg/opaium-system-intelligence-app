"""
OP(AI)UM — File Metadata Reader Tool

Reads file metadata: image dimensions, file hashes,
creation dates, and other properties.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.utils.path_utils import PathUtils


class MetadataReaderTool(BaseTool):
    @property
    def name(self) -> str:
        return "read_metadata"

    @property
    def description(self) -> str:
        return (
            "Read detailed metadata for files: image dimensions, file sizes, "
            "creation/modification dates, and file hashes."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory path",
                },
                "include_hash": {
                    "type": "boolean",
                    "description": "Calculate MD5 hash for each file",
                    "default": False,
                },
                "extension": {
                    "type": "string",
                    "description": "Only read files with this extension",
                },
            },
            "required": ["path"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        path = kwargs.get("path", "")
        include_hash = kwargs.get("include_hash", False)
        extension = kwargs.get("extension", "")

        if not self._validate_path(path):
            return ToolResult(success=False, message=f"Path not accessible: {path}")

        if os.path.isfile(path):
            metadata = self._read_single(path, include_hash)
            return ToolResult(
                success=True,
                message=self._format_single(metadata),
                data=metadata,
            )

        # Directory: batch read
        files_meta = []
        for entry in os.scandir(path):
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
                if extension:
                    ext = Path(entry.name).suffix.lstrip(".").lower()
                    if ext != extension.lower().lstrip("."):
                        continue

                meta = self._read_single(entry.path, include_hash)
                files_meta.append(meta)
            except (OSError, PermissionError):
                continue

        if not files_meta:
            return ToolResult(success=True, message="No matching files found.", data=[])

        lines = [f"Metadata for {len(files_meta)} files in {Path(path).name}:"]
        for m in files_meta[:15]:
            line = f"  {m['name']}: {m['display_size']}"
            if m.get("dimensions"):
                line += f", {m['dimensions']}"
            lines.append(line)

        if len(files_meta) > 15:
            lines.append(f"  ... and {len(files_meta) - 15} more")

        return ToolResult(success=True, message="\n".join(lines), data=files_meta)

    def _read_single(self, fpath: str, include_hash: bool) -> dict:
        """Read metadata for a single file."""
        p = Path(fpath)
        stat = os.stat(fpath)
        ext = p.suffix.lstrip(".").lower()

        meta: dict[str, Any] = {
            "name": p.name,
            "path": fpath,
            "extension": ext,
            "size_bytes": stat.st_size,
            "display_size": PathUtils.format_size(stat.st_size),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
        }

        # Image dimensions
        if ext in ("png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff"):
            dims = self._get_image_dimensions(fpath)
            if dims:
                meta["dimensions"] = f"{dims[0]}x{dims[1]}"
                meta["width"] = dims[0]
                meta["height"] = dims[1]

        # Hash
        if include_hash:
            from src.core.file_scanner import FileScanner

            file_hash = FileScanner.get_file_hash(fpath)
            if file_hash:
                meta["md5"] = file_hash

        return meta

    def _get_image_dimensions(self, fpath: str) -> tuple[int, int] | None:
        """Get image dimensions using PIL."""
        try:
            from PIL import Image

            with Image.open(fpath) as img:
                return img.size
        except Exception:
            return None

    @staticmethod
    def _format_single(meta: dict) -> str:
        """Format single file metadata for display."""
        lines = [f"File: {meta['name']}"]
        lines.append(f"  Size: {meta['display_size']}")
        lines.append(f"  Created: {meta['created']}")
        lines.append(f"  Modified: {meta['modified']}")
        if meta.get("dimensions"):
            lines.append(f"  Dimensions: {meta['dimensions']}")
        if meta.get("md5"):
            lines.append(f"  MD5: {meta['md5']}")
        return "\n".join(lines)
