"""
Local file tooling for the setup agent.

The model-facing tool surface is intentionally narrow and rooted to a small
set of allowed directories.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class LocalFileTools:
    """Safe local file tools exposed to model tool/function calling."""

    def __init__(self, *, allowed_roots: list[Path] | None = None):
        roots = allowed_roots or [Path.cwd(), Path.home()]
        normalized_roots: list[Path] = []
        for root in roots:
            resolved = root.expanduser().resolve()
            if resolved not in normalized_roots:
                normalized_roots.append(resolved)
        self.allowed_roots = normalized_roots

    def _resolve_user_path(self, raw_path: str) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("path must be a non-empty string")

        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        else:
            path = path.resolve()

        if not any(path == root or root in path.parents for root in self.allowed_roots):
            allowed = ", ".join(str(item) for item in self.allowed_roots)
            raise PermissionError(
                f"path is outside allowed roots: {path} (allowed: {allowed})"
            )

        return path

    @staticmethod
    def _coerce_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(parsed, maximum))

    def _list_directory(self, args: dict[str, Any]) -> dict[str, Any]:
        target = self._resolve_user_path(str(args.get("path", ".")))
        if not target.exists():
            raise FileNotFoundError(f"directory does not exist: {target}")
        if not target.is_dir():
            raise NotADirectoryError(f"path is not a directory: {target}")

        include_hidden = bool(args.get("include_hidden", False))
        max_entries = self._coerce_int(
            args.get("max_entries"),
            default=200,
            minimum=1,
            maximum=500,
        )

        entries = []
        for item in sorted(target.iterdir(), key=lambda value: value.name.lower()):
            if not include_hidden and item.name.startswith("."):
                continue
            entry = {
                "name": item.name,
                "path": str(item),
                "type": "directory" if item.is_dir() else "file",
            }
            if item.is_file():
                try:
                    entry["size"] = item.stat().st_size
                except OSError:
                    entry["size"] = None
            entries.append(entry)
            if len(entries) >= max_entries:
                break

        return {
            "ok": True,
            "path": str(target),
            "entries": entries,
        }

    def _read_file(self, args: dict[str, Any]) -> dict[str, Any]:
        target = self._resolve_user_path(str(args.get("path", "")))
        if not target.exists():
            raise FileNotFoundError(f"file does not exist: {target}")
        if not target.is_file():
            raise IsADirectoryError(f"path is not a file: {target}")

        content = target.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        total_lines = len(lines)

        start_line = self._coerce_int(
            args.get("start_line"),
            default=1,
            minimum=1,
            maximum=max(total_lines, 1),
        )
        end_line = self._coerce_int(
            args.get("end_line"),
            default=start_line + 199,
            minimum=start_line,
            maximum=max(total_lines, 1),
        )
        max_chars = self._coerce_int(
            args.get("max_chars"),
            default=20000,
            minimum=500,
            maximum=100000,
        )

        if total_lines == 0:
            selected = ""
        else:
            selected_lines = lines[start_line - 1 : end_line]
            selected = "\n".join(selected_lines)

        truncated = False
        if len(selected) > max_chars:
            selected = selected[:max_chars]
            truncated = True

        return {
            "ok": True,
            "path": str(target),
            "start_line": start_line,
            "end_line": end_line,
            "total_lines": total_lines,
            "truncated": truncated,
            "content": selected,
        }

    def _write_file(self, args: dict[str, Any]) -> dict[str, Any]:
        target = self._resolve_user_path(str(args.get("path", "")))
        content = args.get("content")
        if not isinstance(content, str):
            raise ValueError("content must be a string")

        create_parents = bool(args.get("create_parents", True))
        if create_parents:
            target.parent.mkdir(parents=True, exist_ok=True)

        target.write_text(content, encoding="utf-8")
        return {
            "ok": True,
            "path": str(target),
            "bytes_written": len(content.encode("utf-8")),
        }

    def _replace_in_file(self, args: dict[str, Any]) -> dict[str, Any]:
        target = self._resolve_user_path(str(args.get("path", "")))
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"file does not exist: {target}")

        old_text = args.get("old_text")
        new_text = args.get("new_text")
        if not isinstance(old_text, str) or not old_text:
            raise ValueError("old_text must be a non-empty string")
        if not isinstance(new_text, str):
            raise ValueError("new_text must be a string")

        count = self._coerce_int(
            args.get("count"),
            default=1,
            minimum=0,
            maximum=1000,
        )

        source = target.read_text(encoding="utf-8", errors="replace")
        total_matches = source.count(old_text)
        if total_matches == 0:
            return {
                "ok": False,
                "path": str(target),
                "error": "old_text not found",
            }

        if count == 0:
            updated = source.replace(old_text, new_text)
            replacements = total_matches
        else:
            updated = source.replace(old_text, new_text, count)
            replacements = min(total_matches, count)

        target.write_text(updated, encoding="utf-8")
        return {
            "ok": True,
            "path": str(target),
            "replacements": replacements,
        }

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "list_directory": self._list_directory,
            "read_file": self._read_file,
            "write_file": self._write_file,
            "replace_in_file": self._replace_in_file,
        }

        handler = handlers.get(name)
        if handler is None:
            return {
                "ok": False,
                "error": f"unknown tool: {name}",
            }

        try:
            return handler(arguments)
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
            }

    @staticmethod
    def _tool_parameter_schemas() -> dict[str, dict[str, Any]]:
        return {
            "list_directory": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to inspect.",
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Whether to include dotfiles.",
                    },
                    "max_entries": {
                        "type": "integer",
                        "description": "Maximum entries to return.",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            "read_file": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read.",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "1-based start line.",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "1-based inclusive end line.",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters in returned content.",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            "write_file": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full file content to write.",
                    },
                    "create_parents": {
                        "type": "boolean",
                        "description": "Create parent directories if needed.",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            "replace_in_file": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to edit.",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Exact text to replace.",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Replacement text.",
                    },
                    "count": {
                        "type": "integer",
                        "description": "How many matches to replace. 0 means all.",
                    },
                },
                "required": ["path", "old_text", "new_text"],
                "additionalProperties": False,
            },
        }

    def openai_tool_specs(self) -> list[dict[str, Any]]:
        schemas = self._tool_parameter_schemas()
        return [
            {
                "type": "function",
                "name": "list_directory",
                "description": "List files and folders in a local directory.",
                "parameters": schemas["list_directory"],
            },
            {
                "type": "function",
                "name": "read_file",
                "description": "Read text content from a local file.",
                "parameters": schemas["read_file"],
            },
            {
                "type": "function",
                "name": "write_file",
                "description": "Write full text content to a local file.",
                "parameters": schemas["write_file"],
            },
            {
                "type": "function",
                "name": "replace_in_file",
                "description": "Replace exact text in a local file.",
                "parameters": schemas["replace_in_file"],
            },
        ]

    def anthropic_tool_specs(self) -> list[dict[str, Any]]:
        schemas = self._tool_parameter_schemas()
        return [
            {
                "name": "list_directory",
                "description": "List files and folders in a local directory.",
                "input_schema": schemas["list_directory"],
            },
            {
                "name": "read_file",
                "description": "Read text content from a local file.",
                "input_schema": schemas["read_file"],
            },
            {
                "name": "write_file",
                "description": "Write full text content to a local file.",
                "input_schema": schemas["write_file"],
            },
            {
                "name": "replace_in_file",
                "description": "Replace exact text in a local file.",
                "input_schema": schemas["replace_in_file"],
            },
        ]

    def gemini_function_declarations(self, genai_types: Any) -> list[Any]:
        schemas = self._tool_parameter_schemas()
        return [
            genai_types.FunctionDeclaration(
                name="list_directory",
                description="List files and folders in a local directory.",
                parameters_json_schema=schemas["list_directory"],
            ),
            genai_types.FunctionDeclaration(
                name="read_file",
                description="Read text content from a local file.",
                parameters_json_schema=schemas["read_file"],
            ),
            genai_types.FunctionDeclaration(
                name="write_file",
                description="Write full text content to a local file.",
                parameters_json_schema=schemas["write_file"],
            ),
            genai_types.FunctionDeclaration(
                name="replace_in_file",
                description="Replace exact text in a local file.",
                parameters_json_schema=schemas["replace_in_file"],
            ),
        ]
