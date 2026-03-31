"""
Interactive setup command with LLM-assisted schedule generation/modification.

This module adds the `reminder setup` workflow:
- Ensure LLM provider credentials exist in a dedicated TOML file.
- Detect whether a complete schedule configuration already exists.
- Route to build or modify schedule agents.

The build agent asks for a timetable source path (image/text file), generates an
initial TOML configuration, suggests `reminder view`, then loops through
adjustments via the modify agent.
"""

from __future__ import annotations

import base64
import getpass
import json
import mimetypes
import os
import re
import stat
import sys
import termios
import tty
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import tomllib
from rich.console import Console
from rich.panel import Panel

from schedule_management.commands.setup_prompts import (
    BUILD_SYSTEM_PROMPT,
    MODIFY_SYSTEM_PROMPT,
    render_build_user_prompt,
    render_modify_user_prompt,
    render_retry_user_prompt,
)

SUPPORTED_VENDORS: list[tuple[str, str]] = [
    ("openai", "OpenAI"),
    ("openai_compatible", "OpenAI compatible"),
    ("anthropic", "Anthropic"),
    ("gemini", "Gemini"),
]
SUPPORTED_VENDOR_SET = {item[0] for item in SUPPORTED_VENDORS}
VALID_AGENT_PHASES = {"discovery", "summary", "final"}
MAX_TOOL_ROUNDS = 8

REQUIRED_CONFIG_FILES = (
    "settings.toml",
    "odd_weeks.toml",
    "even_weeks.toml",
    "habits.toml",
)

DEFAULT_HABITS_TOML = """[habits]\n# Example: 1 = \"Read for 20 minutes\"\n"""

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".tsv",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".py",
    ".ini",
    ".log",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

CONSOLE = Console()


@dataclass
class LLMConfig:
    vendor: str
    model: str
    api_key: str
    base_url: str | None = None


@dataclass
class SourceAttachment:
    path: Path
    mime_type: str
    text_content: str | None = None
    image_base64: str | None = None


@dataclass
class AgentTurn:
    phase: str
    conversation: str
    needs_user_input: bool
    question_to_user: str | None = None
    missing_information: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    schedule_summary: str | None = None
    bundle: dict[str, str] | None = None


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


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


def _resolve_config_dir() -> Path:
    config_dir = os.getenv("REMINDER_CONFIG_DIR") or "config"
    return Path(config_dir).expanduser().resolve()


def _resolve_llm_config_path() -> Path:
    override = os.getenv("REMINDER_LLM_CONFIG_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".schedule_management" / "llm.toml").resolve()


def _ask_yes_no(prompt: str, *, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            answer = (
                CONSOLE.input(f"[bold cyan]{prompt}[/] [bright_black]{suffix}[/]: ")
                .strip()
                .lower()
            )
        except EOFError:
            return default

        if answer == "":
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        CONSOLE.print("[bold yellow]Please answer with 'y' or 'n'.[/]")


def _prompt_non_empty(prompt: str, *, secret: bool = False) -> str:
    while True:
        try:
            if secret:
                CONSOLE.print(f"[bold cyan]{prompt}[/]")
                value = getpass.getpass(" > ")
            else:
                value = CONSOLE.input(f"[bold cyan]{prompt}[/]")
        except EOFError:
            value = ""
        value = value.strip()
        if value:
            return value
        CONSOLE.print("[bold yellow]This value cannot be empty.[/]")


def _interpret_confirmation(answer: str) -> bool | None:
    normalized = answer.strip().lower()
    if not normalized:
        return None

    affirmative = {
        "y",
        "yes",
        "ok",
        "okay",
        "approve",
        "approved",
        "confirm",
        "confirmed",
        "looks good",
        "good",
        "sounds good",
    }
    negative = {
        "n",
        "no",
        "reject",
        "rejected",
        "not yet",
        "needs changes",
        "change",
        "adjust",
    }

    if normalized in affirmative:
        return True
    if normalized in negative:
        return False
    return None


def _draw_vendor_menu(options: list[tuple[str, str]], index: int) -> None:
    if CONSOLE.is_terminal:
        CONSOLE.clear()
    CONSOLE.print("[bold cyan]Select model vendor[/]")
    CONSOLE.print("[bright_black]Use Up/Down (or j/k) and Enter[/]\n")
    for idx, (_, label) in enumerate(options):
        if idx == index:
            CONSOLE.print(f"[bold black on bright_cyan]> {label}[/]")
        else:
            CONSOLE.print(f"  [white]{label}[/]")


def _select_vendor_with_arrows(options: list[tuple[str, str]]) -> str | None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return None

    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    index = 0

    try:
        sys.stdout.write("\033[?25l")
        tty.setcbreak(fd)
        while True:
            _draw_vendor_menu(options, index)
            key = sys.stdin.read(1)

            if key in {"\r", "\n"}:
                return options[index][0]
            if key == "\x03":
                raise KeyboardInterrupt()
            if key == "\x1b":
                seq = sys.stdin.read(2)
                if seq == "[A":
                    index = (index - 1) % len(options)
                elif seq == "[B":
                    index = (index + 1) % len(options)
            elif key.lower() == "k":
                index = (index - 1) % len(options)
            elif key.lower() == "j":
                index = (index + 1) % len(options)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()


def _select_vendor_fallback(options: list[tuple[str, str]]) -> str:
    CONSOLE.print("[bold cyan]Select model vendor:[/]")
    for idx, (_, label) in enumerate(options, 1):
        CONSOLE.print(f"  [green]{idx}[/]. [white]{label}[/]")

    while True:
        choice = CONSOLE.input("[bold cyan]Enter number:[/] ").strip()
        try:
            value = int(choice)
        except ValueError:
            CONSOLE.print("[bold yellow]Please enter a valid number.[/]")
            continue

        if 1 <= value <= len(options):
            return options[value - 1][0]
        CONSOLE.print("[bold yellow]Choice out of range.[/]")


def _select_vendor() -> str:
    arrow_choice = _select_vendor_with_arrows(SUPPORTED_VENDORS)
    if arrow_choice:
        return arrow_choice
    return _select_vendor_fallback(SUPPORTED_VENDORS)


def _parse_llm_config(raw: dict[str, Any]) -> LLMConfig | None:
    vendor = str(raw.get("vendor", "")).strip().lower()
    model = str(raw.get("model", "")).strip()
    api_key = str(raw.get("api_key", "")).strip()
    base_url = raw.get("base_url")
    base_url_str = str(base_url).strip() if base_url is not None else None

    if vendor not in SUPPORTED_VENDOR_SET:
        return None
    if not model or not api_key:
        return None
    if vendor == "openai_compatible" and not base_url_str:
        return None

    if vendor != "openai_compatible":
        base_url_str = None

    return LLMConfig(
        vendor=vendor,
        model=model,
        api_key=api_key,
        base_url=base_url_str,
    )


def load_llm_config(path: Path) -> LLMConfig | None:
    if not path.exists():
        return None

    try:
        with open(path, "rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None

    if not isinstance(raw, dict):
        return None

    return _parse_llm_config(raw)


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def save_llm_config(path: Path, config: LLMConfig) -> None:
    lines = [
        f"vendor = {_toml_string(config.vendor)}",
        f"model = {_toml_string(config.model)}",
        f"api_key = {_toml_string(config.api_key)}",
    ]
    if config.base_url:
        lines.append(f"base_url = {_toml_string(config.base_url)}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def ensure_llm_config() -> LLMConfig:
    llm_path = _resolve_llm_config_path()
    existing = load_llm_config(llm_path)
    if existing:
        return existing

    CONSOLE.print(
        Panel.fit(
            "No valid LLM configuration detected. Please set it up now.",
            title="Setup",
            border_style="yellow",
        )
    )

    vendor = _select_vendor()
    model = _prompt_non_empty("Model ID: ")
    api_key = _prompt_non_empty("API key: ", secret=True)

    base_url = None
    if vendor == "openai_compatible":
        base_url = _prompt_non_empty("Base URL (for example: https://host/v1): ")

    config = LLMConfig(
        vendor=vendor,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )
    save_llm_config(llm_path, config)
    CONSOLE.print(f"[bold green]Saved LLM settings to[/] [cyan]{llm_path}[/]")
    return config


def has_completed_configuration(config_dir: Path) -> tuple[bool, str]:
    for file_name in REQUIRED_CONFIG_FILES:
        candidate = config_dir / file_name
        if not candidate.exists():
            return False, f"Missing {file_name}"

        try:
            with open(candidate, "rb") as handle:
                tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            return False, f"Invalid TOML in {file_name}: {exc}"

    return True, "ok"


def _normalize_openai_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")

    if normalized.endswith("/v1/chat/completions"):
        normalized = normalized[: -len("/chat/completions")]
    elif normalized.endswith("/chat/completions"):
        normalized = normalized[: -len("/chat/completions")]
    elif normalized.endswith("/v1/responses"):
        normalized = normalized[: -len("/responses")]
    elif normalized.endswith("/responses"):
        normalized = normalized[: -len("/responses")]

    if not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"
    return normalized


def _add_text_attachment(user_prompt: str, attachment: SourceAttachment | None) -> str:
    if not attachment or not attachment.text_content:
        return user_prompt

    return (
        f"{user_prompt}\n\n"
        f"Attached file content ({attachment.path.name}):\n"
        f"```\n{attachment.text_content}\n```"
    )


def _extract_openai_response_text(response: Any) -> str:
    direct_text = getattr(response, "output_text", None)
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    if isinstance(response, dict):
        dict_text = response.get("output_text")
        if isinstance(dict_text, str) and dict_text.strip():
            return dict_text.strip()

    output_items = getattr(response, "output", None)
    if output_items is None and isinstance(response, dict):
        output_items = response.get("output")

    if not isinstance(output_items, list):
        return ""

    chunks: list[str] = []
    for item in output_items:
        if isinstance(item, dict):
            content = item.get("content")
        else:
            content = getattr(item, "content", None)

        if not isinstance(content, list):
            continue

        for part in content:
            if isinstance(part, dict):
                part_type = part.get("type")
                text_value = part.get("text")
            else:
                part_type = getattr(part, "type", None)
                text_value = getattr(part, "text", None)

            if part_type in {"output_text", "text"} and isinstance(text_value, str):
                chunks.append(text_value)

    return "\n".join(chunks).strip()


def _extract_gemini_text(response: Any) -> str:
    direct_text = getattr(response, "text", None)
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    if isinstance(response, dict):
        dict_text = response.get("text")
        if isinstance(dict_text, str) and dict_text.strip():
            return dict_text.strip()

    candidates = getattr(response, "candidates", None)
    if candidates is None and isinstance(response, dict):
        candidates = response.get("candidates")

    if not isinstance(candidates, list):
        return ""

    chunks: list[str] = []

    for candidate in candidates:
        if isinstance(candidate, dict):
            content = candidate.get("content")
        else:
            content = getattr(candidate, "content", None)

        if content is None:
            continue

        if isinstance(content, dict):
            parts = content.get("parts")
        else:
            parts = getattr(content, "parts", None)

        if not isinstance(parts, list):
            continue

        for part in parts:
            if isinstance(part, dict):
                text_value = part.get("text")
            else:
                text_value = getattr(part, "text", None)
            if isinstance(text_value, str) and text_value:
                chunks.append(text_value)

    return "\n".join(chunks).strip()


def _coerce_tool_arguments(raw_args: Any) -> dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _extract_openai_tool_calls(response: Any) -> list[ToolCall]:
    output_items = getattr(response, "output", None)
    if output_items is None and isinstance(response, dict):
        output_items = response.get("output")

    if not isinstance(output_items, list):
        return []

    calls: list[ToolCall] = []
    for item in output_items:
        if isinstance(item, dict):
            item_type = item.get("type")
            call_id = item.get("call_id")
            name = item.get("name")
            arguments = item.get("arguments")
        else:
            item_type = getattr(item, "type", None)
            call_id = getattr(item, "call_id", None)
            name = getattr(item, "name", None)
            arguments = getattr(item, "arguments", None)

        if item_type != "function_call":
            continue
        if not isinstance(call_id, str) or not call_id.strip():
            continue
        if not isinstance(name, str) or not name.strip():
            continue

        calls.append(
            ToolCall(
                call_id=call_id,
                name=name,
                arguments=_coerce_tool_arguments(arguments),
            )
        )

    return calls


def _anthropic_block_to_dict(block: Any) -> dict[str, Any]:
    if isinstance(block, dict):
        return block

    block_type = getattr(block, "type", None)
    if block_type == "text":
        return {
            "type": "text",
            "text": getattr(block, "text", ""),
        }

    if block_type == "tool_use":
        return {
            "type": "tool_use",
            "id": getattr(block, "id", ""),
            "name": getattr(block, "name", ""),
            "input": getattr(block, "input", {}) or {},
        }

    return {
        "type": str(block_type or "unknown"),
    }


def _extract_anthropic_tool_calls(blocks: list[Any]) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for index, block in enumerate(blocks):
        if isinstance(block, dict):
            block_type = block.get("type")
            call_id = block.get("id")
            name = block.get("name")
            tool_input = block.get("input", {})
        else:
            block_type = getattr(block, "type", None)
            call_id = getattr(block, "id", None)
            name = getattr(block, "name", None)
            tool_input = getattr(block, "input", {})

        if block_type != "tool_use":
            continue
        if not isinstance(name, str) or not name.strip():
            continue

        normalized_call_id = (
            call_id if isinstance(call_id, str) and call_id.strip() else f"tool-{index}"
        )

        calls.append(
            ToolCall(
                call_id=normalized_call_id,
                name=name,
                arguments=_coerce_tool_arguments(tool_input),
            )
        )

    return calls


def _extract_gemini_function_calls(response: Any) -> list[ToolCall]:
    function_calls = getattr(response, "function_calls", None)
    if function_calls is None and isinstance(response, dict):
        function_calls = response.get("function_calls")

    if not isinstance(function_calls, list):
        return []

    calls: list[ToolCall] = []
    for index, item in enumerate(function_calls):
        if isinstance(item, dict):
            name = item.get("name")
            args = item.get("args")
            call_id = item.get("id")
        else:
            name = getattr(item, "name", None)
            args = getattr(item, "args", None)
            call_id = getattr(item, "id", None)

        if not isinstance(name, str) or not name.strip():
            continue

        normalized_call_id = (
            call_id if isinstance(call_id, str) and call_id.strip() else f"tool-{index}"
        )
        calls.append(
            ToolCall(
                call_id=normalized_call_id,
                name=name,
                arguments=_coerce_tool_arguments(args),
            )
        )

    return calls


def _build_local_file_tools(config_dir: Path) -> LocalFileTools:
    roots = [
        config_dir,
        Path.cwd(),
        Path.home(),
    ]
    return LocalFileTools(allowed_roots=roots)


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self._openai_client: Any | None = None
        self._anthropic_client: Any | None = None
        self._gemini_client: Any | None = None

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        attachment: SourceAttachment | None = None,
        on_text: Callable[[str], None] | None = None,
        file_tools: LocalFileTools | None = None,
        on_tool_activity: Callable[[str], None] | None = None,
    ) -> str:
        if self.config.vendor in {"openai", "openai_compatible"}:
            return self._openai_response(
                system_prompt,
                user_prompt,
                attachment,
                on_text=on_text,
                file_tools=file_tools,
                on_tool_activity=on_tool_activity,
            )

        if self.config.vendor == "anthropic":
            return self._anthropic_chat(
                system_prompt,
                user_prompt,
                attachment,
                on_text=on_text,
                file_tools=file_tools,
                on_tool_activity=on_tool_activity,
            )

        if self.config.vendor == "gemini":
            return self._gemini_chat(
                system_prompt,
                user_prompt,
                attachment,
                on_text=on_text,
                file_tools=file_tools,
                on_tool_activity=on_tool_activity,
            )

        raise RuntimeError(f"Unsupported vendor: {self.config.vendor}")

    def _get_openai_client(self) -> Any:
        if self._openai_client is not None:
            return self._openai_client

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI SDK is not installed. Run 'uv sync' to install dependencies."
            ) from exc

        kwargs: dict[str, Any] = {"api_key": self.config.api_key}

        if self.config.vendor == "openai_compatible":
            if not self.config.base_url:
                raise RuntimeError(
                    "Missing base_url for openai_compatible vendor in llm.toml"
                )
            kwargs["base_url"] = _normalize_openai_base_url(self.config.base_url)

        self._openai_client = OpenAI(**kwargs)
        return self._openai_client

    def _get_anthropic_client(self) -> Any:
        if self._anthropic_client is not None:
            return self._anthropic_client

        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError(
                "Anthropic SDK is not installed. Run 'uv sync' to install dependencies."
            ) from exc

        self._anthropic_client = Anthropic(api_key=self.config.api_key)
        return self._anthropic_client

    def _get_gemini_client(self) -> Any:
        if self._gemini_client is not None:
            return self._gemini_client

        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError(
                "Gemini SDK is not installed. Run 'uv sync' to install dependencies."
            ) from exc

        self._gemini_client = genai.Client(api_key=self.config.api_key)
        return self._gemini_client

    def _openai_response(
        self,
        system_prompt: str,
        user_prompt: str,
        attachment: SourceAttachment | None,
        *,
        on_text: Callable[[str], None] | None,
        file_tools: LocalFileTools | None,
        on_tool_activity: Callable[[str], None] | None,
    ) -> str:
        client = self._get_openai_client()
        user_prompt_with_text = _add_text_attachment(user_prompt, attachment)

        user_content: list[dict[str, Any]] = [
            {"type": "input_text", "text": user_prompt_with_text}
        ]
        if attachment and attachment.image_base64:
            image_url = f"data:{attachment.mime_type};base64,{attachment.image_base64}"
            user_content.append({"type": "input_image", "image_url": image_url})

        current_input: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": user_content,
            }
        ]
        previous_response_id: str | None = None
        tool_specs = file_tools.openai_tool_specs() if file_tools else None

        for _ in range(MAX_TOOL_ROUNDS):
            request_kwargs: dict[str, Any] = {
                "model": self.config.model,
                "temperature": 0.2,
                "instructions": system_prompt,
                "input": current_input,
            }
            if previous_response_id:
                request_kwargs["previous_response_id"] = previous_response_id
            if tool_specs:
                request_kwargs["tools"] = tool_specs

            streamed_chunks: list[str] = []
            with client.responses.stream(**request_kwargs) as stream:
                for event in stream:
                    if isinstance(event, dict):
                        event_type = event.get("type")
                        delta = event.get("delta")
                    else:
                        event_type = getattr(event, "type", None)
                        delta = getattr(event, "delta", None)

                    if event_type == "response.output_text.delta" and isinstance(
                        delta, str
                    ):
                        streamed_chunks.append(delta)
                        if on_text is not None:
                            on_text(delta)

                response = stream.get_final_response()

            tool_calls = _extract_openai_tool_calls(response) if file_tools else []
            if tool_calls and file_tools:
                tool_outputs: list[dict[str, str]] = []
                for call in tool_calls:
                    if on_tool_activity is not None:
                        on_tool_activity(f"Agent is operating files via {call.name}...")
                    result = file_tools.execute(call.name, call.arguments)
                    tool_outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": json.dumps(result, ensure_ascii=False),
                        }
                    )

                response_id = getattr(response, "id", None)
                if response_id is None and isinstance(response, dict):
                    response_id = response.get("id")
                if not isinstance(response_id, str) or not response_id.strip():
                    raise RuntimeError(
                        "OpenAI response for tool calls did not include response id"
                    )

                previous_response_id = response_id
                current_input = tool_outputs
                continue

            content = _extract_openai_response_text(response)
            if not content:
                content = "".join(streamed_chunks).strip()
            if content:
                return content

            raise RuntimeError(
                f"OpenAI response did not contain text content: {response}"
            )

        raise RuntimeError("OpenAI tool loop exceeded maximum rounds")

    def _anthropic_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        attachment: SourceAttachment | None,
        *,
        on_text: Callable[[str], None] | None,
        file_tools: LocalFileTools | None,
        on_tool_activity: Callable[[str], None] | None,
    ) -> str:
        client = self._get_anthropic_client()
        content: list[dict[str, Any]] = [
            {"type": "text", "text": _add_text_attachment(user_prompt, attachment)}
        ]

        if attachment and attachment.image_base64:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": attachment.mime_type,
                        "data": attachment.image_base64,
                    },
                }
            )

        messages: list[dict[str, Any]] = [{"role": "user", "content": content}]
        tool_specs = file_tools.anthropic_tool_specs() if file_tools else None

        for _ in range(MAX_TOOL_ROUNDS):
            request_kwargs: dict[str, Any] = {
                "model": self.config.model,
                "max_tokens": 1800,
                "temperature": 0.2,
                "system": system_prompt,
                "messages": messages,
            }
            if tool_specs:
                request_kwargs["tools"] = tool_specs

            streamed_chunks: list[str] = []
            with client.messages.stream(**request_kwargs) as stream:
                for delta in stream.text_stream:
                    if isinstance(delta, str) and delta:
                        streamed_chunks.append(delta)
                        if on_text is not None:
                            on_text(delta)

                final_message = stream.get_final_message()

            blocks = getattr(final_message, "content", None)
            if blocks is None and isinstance(final_message, dict):
                blocks = final_message.get("content")
            if not isinstance(blocks, list):
                raise RuntimeError(
                    f"Unexpected Anthropic response payload: {final_message}"
                )

            tool_calls = _extract_anthropic_tool_calls(blocks) if file_tools else []
            if tool_calls and file_tools:
                assistant_content = [
                    _anthropic_block_to_dict(block) for block in blocks
                ]
                tool_results: list[dict[str, Any]] = []

                for call in tool_calls:
                    if on_tool_activity is not None:
                        on_tool_activity(f"Agent is operating files via {call.name}...")
                    result = file_tools.execute(call.name, call.arguments)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": call.call_id,
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )

                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})
                continue

            combined = "".join(streamed_chunks).strip()
            if combined:
                return combined

            texts: list[str] = []
            for block in blocks:
                if isinstance(block, dict):
                    block_type = block.get("type")
                    text_value = block.get("text")
                else:
                    block_type = getattr(block, "type", None)
                    text_value = getattr(block, "text", None)

                if block_type == "text" and isinstance(text_value, str):
                    texts.append(text_value)

            if texts:
                return "\n".join(texts)

            raise RuntimeError(
                f"Anthropic response did not contain text: {final_message}"
            )

        raise RuntimeError("Anthropic tool loop exceeded maximum rounds")

    def _gemini_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        attachment: SourceAttachment | None,
        *,
        on_text: Callable[[str], None] | None,
        file_tools: LocalFileTools | None,
        on_tool_activity: Callable[[str], None] | None,
    ) -> str:
        try:
            from google.genai import types as genai_types
        except ImportError as exc:
            raise RuntimeError(
                "Gemini SDK is not installed. Run 'uv sync' to install dependencies."
            ) from exc

        client = self._get_gemini_client()

        parts: list[Any] = [
            genai_types.Part.from_text(
                text=_add_text_attachment(user_prompt, attachment)
            )
        ]

        if attachment and attachment.image_base64:
            try:
                image_bytes = base64.b64decode(attachment.image_base64.encode("ascii"))
            except Exception as exc:
                raise RuntimeError(
                    "Invalid image attachment for Gemini request"
                ) from exc

            parts.append(
                genai_types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=attachment.mime_type,
                )
            )

        tool_declarations = (
            file_tools.gemini_function_declarations(genai_types) if file_tools else []
        )
        contents: list[Any] = [genai_types.Content(role="user", parts=parts)]

        for _ in range(MAX_TOOL_ROUNDS):
            generate_config = genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
                tools=[genai_types.Tool(function_declarations=tool_declarations)]
                if tool_declarations
                else None,
            )

            response_stream = client.models.generate_content_stream(
                model=self.config.model,
                contents=contents,
                config=generate_config,
            )

            streamed_chunks: list[str] = []
            final_chunk: Any | None = None
            collected_calls: list[ToolCall] = []
            for chunk in response_stream:
                final_chunk = chunk
                chunk_text = getattr(chunk, "text", None)
                if chunk_text is None and isinstance(chunk, dict):
                    chunk_text = chunk.get("text")
                if isinstance(chunk_text, str) and chunk_text:
                    streamed_chunks.append(chunk_text)
                    if on_text is not None:
                        on_text(chunk_text)

                if file_tools:
                    for call in _extract_gemini_function_calls(chunk):
                        if all(
                            existing.call_id != call.call_id
                            for existing in collected_calls
                        ):
                            collected_calls.append(call)

            function_calls = collected_calls
            if not function_calls and file_tools and final_chunk is not None:
                function_calls = _extract_gemini_function_calls(final_chunk)
            if function_calls and file_tools:
                model_parts = [
                    genai_types.Part.from_function_call(
                        name=call.name,
                        args=call.arguments,
                    )
                    for call in function_calls
                ]
                contents.append(genai_types.Content(role="model", parts=model_parts))

                response_parts: list[Any] = []
                for call in function_calls:
                    if on_tool_activity is not None:
                        on_tool_activity(f"Agent is operating files via {call.name}...")
                    tool_result = file_tools.execute(call.name, call.arguments)
                    response_parts.append(
                        genai_types.Part.from_function_response(
                            name=call.name,
                            response=tool_result,
                        )
                    )

                contents.append(genai_types.Content(role="user", parts=response_parts))
                continue

            text = "".join(streamed_chunks).strip()
            if text:
                return text

            if final_chunk is not None:
                fallback = _extract_gemini_text(final_chunk)
                if fallback:
                    return fallback

            raise RuntimeError("Gemini response did not contain text")

        raise RuntimeError("Gemini tool loop exceeded maximum rounds")


def _extract_json_object(response_text: str) -> dict[str, Any] | None:
    candidates = [response_text.strip()]

    fenced_matches = re.findall(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        response_text,
        flags=re.DOTALL,
    )
    candidates.extend(match.strip() for match in fenced_matches)

    start = response_text.find("{")
    end = response_text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(response_text[start : end + 1].strip())

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    return None


def _parse_toml_bundle_from_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, str] | None, str | None]:
    key_mapping = {
        "settings_toml": "settings.toml",
        "odd_weeks_toml": "odd_weeks.toml",
        "even_weeks_toml": "even_weeks.toml",
    }

    has_any_toml_key = any(
        key in payload for key in (*key_mapping.keys(), "habits_toml")
    )
    if not has_any_toml_key:
        return None, None

    bundle: dict[str, str] = {}

    for payload_key, file_name in key_mapping.items():
        value = payload.get(payload_key)
        if not isinstance(value, str) or not value.strip():
            return None, f"missing or empty '{payload_key}'"

        try:
            tomllib.loads(value)
        except tomllib.TOMLDecodeError as exc:
            return None, f"invalid TOML in {payload_key}: {exc}"

        bundle[file_name] = value.rstrip() + "\n"

    habits_value = payload.get("habits_toml")
    if habits_value is not None:
        if not isinstance(habits_value, str) or not habits_value.strip():
            return None, "habits_toml must be a non-empty string when provided"
        try:
            tomllib.loads(habits_value)
        except tomllib.TOMLDecodeError as exc:
            return None, f"invalid TOML in habits_toml: {exc}"

        bundle["habits.toml"] = habits_value.rstrip() + "\n"

    return bundle, None


def _parse_agent_turn(response_text: str) -> tuple[AgentTurn | None, str | None]:
    payload = _extract_json_object(response_text)
    if payload is None:
        return None, "response was not valid JSON"

    conversation = payload.get("conversation")
    if not isinstance(conversation, str) or not conversation.strip():
        return None, "missing or empty 'conversation'"

    needs_user_input = payload.get("needs_user_input")
    if not isinstance(needs_user_input, bool):
        return None, "missing or invalid 'needs_user_input' (must be boolean)"

    phase_raw = payload.get("phase")
    if phase_raw is None:
        phase = "discovery" if needs_user_input else "final"
    else:
        if not isinstance(phase_raw, str):
            return None, "'phase' must be a string"
        phase = phase_raw.strip().lower()
        if phase not in VALID_AGENT_PHASES:
            return None, "'phase' must be one of: discovery, summary, final"

    question_to_user_raw = payload.get("question_to_user")
    question_to_user: str | None = None
    if question_to_user_raw is not None:
        if not isinstance(question_to_user_raw, str):
            return None, "'question_to_user' must be a string when provided"
        question_to_user = question_to_user_raw.strip() or None

    missing_information_raw = payload.get("missing_information", [])
    missing_information: list[str] = []
    if missing_information_raw is not None:
        if not isinstance(missing_information_raw, list):
            return None, "'missing_information' must be a list when provided"
        for item in missing_information_raw:
            if not isinstance(item, str) or not item.strip():
                return None, "'missing_information' must contain non-empty strings"
            missing_information.append(item.strip())

    actions_raw = payload.get("actions", [])
    actions: list[str] = []
    if actions_raw is not None:
        if not isinstance(actions_raw, list):
            return None, "'actions' must be a list when provided"
        for item in actions_raw:
            if not isinstance(item, str) or not item.strip():
                return None, "'actions' must contain non-empty strings"
            actions.append(item.strip())

    schedule_summary_raw = payload.get("schedule_summary")
    schedule_summary: str | None = None
    if schedule_summary_raw is not None:
        if not isinstance(schedule_summary_raw, str):
            return None, "'schedule_summary' must be a string when provided"
        schedule_summary = schedule_summary_raw.strip()
        if not schedule_summary:
            return None, "'schedule_summary' cannot be empty when provided"

    bundle, bundle_error = _parse_toml_bundle_from_payload(payload)
    if bundle_error:
        return None, bundle_error

    if phase == "final" and needs_user_input:
        return None, "phase=final requires needs_user_input=false"

    if phase in {"discovery", "summary"} and not needs_user_input:
        return None, "discovery/summary phases require needs_user_input=true"

    if phase == "summary" and not schedule_summary:
        return None, "phase=summary requires non-empty schedule_summary"

    if needs_user_input:
        if bundle is not None:
            return None, "needs_user_input=true must not include *_toml fields"
        if not question_to_user and not missing_information:
            return (
                None,
                "needs_user_input=true requires question_to_user or missing_information",
            )
    else:
        if bundle is None:
            return (
                None,
                "missing TOML payload: provide settings_toml/odd_weeks_toml/even_weeks_toml",
            )

    return (
        AgentTurn(
            phase=phase,
            conversation=conversation.strip(),
            needs_user_input=needs_user_input,
            question_to_user=question_to_user,
            missing_information=missing_information,
            actions=actions,
            schedule_summary=schedule_summary,
            bundle=bundle,
        ),
        None,
    )


def _request_agent_turn(
    client: LLMClient,
    system_prompt: str,
    user_prompt: str,
    *,
    attachment: SourceAttachment | None = None,
    turn_validator: Callable[[AgentTurn], str | None] | None = None,
    file_tools: LocalFileTools | None = None,
) -> tuple[AgentTurn | None, str | None]:
    base_prompt = user_prompt
    prompt = user_prompt
    last_error: str | None = None
    previous_response = ""

    for attempt in range(1, 4):
        try:
            with CONSOLE.status(
                f"[bold magenta]Agent is thinking and doing internal actions (attempt {attempt}/3)...[/]",
                spinner="dots",
            ) as status:
                response_text = client.generate(
                    system_prompt,
                    prompt,
                    attachment if attempt == 1 else None,
                    on_text=None,
                    file_tools=file_tools,
                    on_tool_activity=lambda detail: status.update(
                        f"[bold yellow]{detail}[/]"
                    ),
                )
        except Exception as exc:  # pragma: no cover - network/provider dependent
            return None, str(exc)

        turn, parse_error = _parse_agent_turn(response_text)
        if turn is not None:
            if turn_validator is not None:
                validation_error = turn_validator(turn)
                if validation_error is None:
                    return turn, None
                parse_error = validation_error
            else:
                return turn, None

        last_error = parse_error
        previous_response = response_text.strip()
        prompt = render_retry_user_prompt(
            original_user_prompt=base_prompt,
            parse_error=parse_error or "unknown parsing error",
            previous_response=previous_response,
        )

    return None, last_error


def _load_source_attachment(path: Path) -> tuple[SourceAttachment | None, str | None]:
    if not path.exists():
        return None, f"Path does not exist: {path}"
    if path.is_dir():
        return None, f"Expected a file path, but got directory: {path}"

    suffix = path.suffix.lower()
    mime_type, _ = mimetypes.guess_type(path.name)
    mime = mime_type or "application/octet-stream"

    if suffix in IMAGE_EXTENSIONS or mime.startswith("image/"):
        raw = path.read_bytes()
        encoded = base64.b64encode(raw).decode("ascii")
        return SourceAttachment(path=path, mime_type=mime, image_base64=encoded), None

    if suffix in TEXT_EXTENSIONS or mime.startswith("text/"):
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > 15000:
            content = content[:15000] + "\n... [truncated]"
        return SourceAttachment(
            path=path, mime_type="text/plain", text_content=content
        ), None

    # Attempt text fallback for unknown extensions.
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return (
            None,
            "Unsupported file type for setup agent. Use a text file or image file.",
        )

    if len(content) > 15000:
        content = content[:15000] + "\n... [truncated]"

    return SourceAttachment(
        path=path, mime_type="text/plain", text_content=content
    ), None


def _write_bundle(config_dir: Path, bundle: dict[str, str]) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    for file_name, content in bundle.items():
        target = config_dir / file_name
        target.write_text(content, encoding="utf-8")


def _render_current_files(config_dir: Path) -> str:
    sections: list[str] = []
    for file_name in (
        "settings.toml",
        "odd_weeks.toml",
        "even_weeks.toml",
        "habits.toml",
    ):
        path = config_dir / file_name
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        sections.append(f"[{file_name}]\n{content}")
    return "\n\n".join(sections)


def _render_conversation_message(message: str) -> None:
    text = message.strip()
    if not text:
        return
    CONSOLE.print(
        Panel.fit(
            text,
            title="Conversation",
            border_style="blue",
        )
    )


def _render_missing_information(items: list[str]) -> None:
    if not items:
        return
    CONSOLE.print("[bold yellow]I still need the following information:[/]")
    for item in items:
        CONSOLE.print(f"[yellow]- {item}[/]")


def _render_schedule_summary(summary: str) -> None:
    text = summary.strip()
    if not text:
        return
    CONSOLE.print(
        Panel.fit(
            text,
            title="Schedule Summary",
            border_style="magenta",
        )
    )


def _append_conversation_history(
    history: str,
    *,
    assistant_text: str,
    user_text: str,
) -> str:
    lines: list[str] = []
    if history.strip():
        lines.append(history.strip())
    lines.append(f"Assistant: {assistant_text.strip()}")
    lines.append(f"User: {user_text.strip()}")
    return "\n".join(lines).strip()


def _merge_request_with_details(base_text: str, details: list[str]) -> str:
    if not details:
        return base_text
    detail_lines = "\n".join(f"- {item}" for item in details)
    return (
        f"{base_text}\n\n"
        "Additional details provided by the user in follow-up turns:\n"
        f"{detail_lines}"
    )


def _collect_profile_context() -> str:
    CONSOLE.print(
        Panel.fit(
            "Before generating your schedule, I will ask a few quick profile questions.",
            title="Profile Intake",
            border_style="bright_blue",
        )
    )

    basic_info = _prompt_non_empty(
        "Basic information (student/worker, timezone, wake/sleep pattern). "
        "If unsure, type 'unknown': "
    )
    goals = _prompt_non_empty(
        "What are your main goals for this schedule (study/work/health/etc.)? "
    )
    habits = _prompt_non_empty(
        "What recurring habits should be included (exercise, reading, review)? "
    )
    preferences = _prompt_non_empty(
        "What are your scheduling preferences (morning focus, free evenings, break style)? "
    )
    constraints = _prompt_non_empty(
        "What hard constraints must be respected (fixed classes/meetings, commute, unavailable times)? "
    )

    return "\n".join(
        [
            f"- Basic information: {basic_info}",
            f"- Goals: {goals}",
            f"- Habits: {habits}",
            f"- Preferences: {preferences}",
            f"- Hard constraints: {constraints}",
        ]
    )


def modify_schedule_agent(llm_config: LLMConfig, config_dir: Path) -> int:
    client = LLMClient(llm_config)
    file_tools = _build_local_file_tools(config_dir)
    CONSOLE.print(
        Panel.fit(
            "Schedule modification assistant is ready.",
            title="Modify",
            border_style="cyan",
        )
    )

    while True:
        base_change_request = _prompt_non_empty(
            "What would you like to change in your schedule? "
        )
        follow_up_details: list[str] = []
        conversation_history = ""

        while True:
            current_files = _render_current_files(config_dir)
            change_request = _merge_request_with_details(
                base_change_request,
                follow_up_details,
            )
            user_prompt = render_modify_user_prompt(
                change_request=change_request,
                current_files=current_files,
                conversation_history=conversation_history,
            )

            turn, error = _request_agent_turn(
                client,
                MODIFY_SYSTEM_PROMPT,
                user_prompt,
                file_tools=file_tools,
            )
            if turn is None:
                CONSOLE.print(
                    f"[bold red]Could not update schedule from model response:[/] {error}"
                )
                return 1

            _render_conversation_message(turn.conversation)

            if turn.needs_user_input:
                _render_missing_information(turn.missing_information)
                follow_up_prompt = (
                    turn.question_to_user or "Please provide the missing information: "
                )
                user_answer = _prompt_non_empty(follow_up_prompt)
                follow_up_details.append(user_answer)
                conversation_history = _append_conversation_history(
                    conversation_history,
                    assistant_text=turn.conversation,
                    user_text=user_answer,
                )
                continue

            if turn.bundle is None:
                CONSOLE.print(
                    "[bold red]Model did not return schedule files for this turn.[/]"
                )
                return 1

            bundle = dict(turn.bundle)
            if (
                "habits.toml" not in bundle
                and not (config_dir / "habits.toml").exists()
            ):
                bundle["habits.toml"] = DEFAULT_HABITS_TOML

            with CONSOLE.status(
                "[bold green]Applying schedule updates...[/]",
                spinner="line",
            ):
                _write_bundle(config_dir, bundle)

            CONSOLE.print("[bold green]Schedule updated.[/]")
            CONSOLE.print("[bold cyan]Run reminder view to preview the result.[/]")
            break

        if not _ask_yes_no("Do you want to apply another adjustment?", default=False):
            return 0


def build_schedule_agent(llm_config: LLMConfig, config_dir: Path) -> int:
    client = LLMClient(llm_config)
    file_tools = _build_local_file_tools(config_dir)
    CONSOLE.print(
        Panel.fit(
            "Hello! I can help build your first schedule configuration.",
            title="Build",
            border_style="green",
        )
    )

    attachment: SourceAttachment | None = None
    description: str | None = None
    profile_context = _collect_profile_context()

    if _ask_yes_no(
        "Can you provide a path to an image/file describing your timetable?",
        default=True,
    ):
        source_path = _prompt_non_empty("Enter path: ")
        loaded, error = _load_source_attachment(Path(source_path).expanduser())
        if loaded is None:
            CONSOLE.print(f"[bold yellow]{error}[/]")
            description = _prompt_non_empty(
                "Please provide a short text description instead: "
            )
        else:
            attachment = loaded
    else:
        description = _prompt_non_empty(
            "Please describe your weekly timetable and constraints: "
        )

    follow_up_details: list[str] = []
    conversation_history = ""
    summary_presented = False
    summary_confirmed = False
    latest_summary: str | None = None

    while True:
        merged_description = description.strip() if description else ""
        if follow_up_details:
            detail_lines = "\n".join(f"- {item}" for item in follow_up_details)
            extra_block = (
                "Additional details provided by the user in follow-up turns:\n"
                f"{detail_lines}"
            )
            merged_description = (
                f"{merged_description}\n\n{extra_block}"
                if merged_description
                else extra_block
            )

        user_prompt = render_build_user_prompt(
            config_dir,
            description=merged_description or None,
            attachment_name=attachment.path.name if attachment else None,
            conversation_history=conversation_history,
            profile_context=profile_context,
            summary_presented=summary_presented,
            summary_confirmed=summary_confirmed,
            latest_summary=latest_summary,
        )

        def _build_turn_validator(turn: AgentTurn) -> str | None:
            if turn.phase == "final" and not summary_presented:
                return (
                    "Build flow violation: final configuration was returned before "
                    "a summary phase. Provide a pure-text summary first."
                )
            if turn.phase == "final" and not summary_confirmed:
                return (
                    "Build flow violation: final configuration was returned before "
                    "the user confirmed the schedule summary."
                )
            return None

        turn, error = _request_agent_turn(
            client,
            BUILD_SYSTEM_PROMPT,
            user_prompt,
            attachment=attachment,
            turn_validator=_build_turn_validator,
            file_tools=file_tools,
        )
        if turn is None:
            CONSOLE.print(
                f"[bold red]Could not build schedule from model response:[/] {error}"
            )
            return 1

        _render_conversation_message(turn.conversation)

        if turn.needs_user_input:
            if turn.phase == "summary" and turn.schedule_summary:
                latest_summary = turn.schedule_summary
                summary_presented = True
                _render_schedule_summary(turn.schedule_summary)

            _render_missing_information(turn.missing_information)
            follow_up_prompt = (
                turn.question_to_user or "Please provide the missing information: "
            )
            user_answer = _prompt_non_empty(follow_up_prompt)
            if turn.phase == "summary":
                confirmation = _interpret_confirmation(user_answer)
                if confirmation is True:
                    summary_confirmed = True
                elif confirmation is False:
                    summary_confirmed = False
            follow_up_details.append(user_answer)
            conversation_history = _append_conversation_history(
                conversation_history,
                assistant_text=turn.conversation,
                user_text=user_answer,
            )
            continue

        if turn.bundle is None:
            CONSOLE.print(
                "[bold red]Model did not return schedule files for this turn.[/]"
            )
            return 1

        bundle = dict(turn.bundle)
        if "habits.toml" not in bundle and not (config_dir / "habits.toml").exists():
            bundle["habits.toml"] = DEFAULT_HABITS_TOML

        with CONSOLE.status(
            "[bold green]Applying generated schedule...[/]",
            spinner="line",
        ):
            _write_bundle(config_dir, bundle)
        break

    CONSOLE.print("[bold green]Initial schedule created.[/]")
    CONSOLE.print("[bold cyan]Run reminder view to visualize your schedule.[/]")

    if _ask_yes_no("Do you need to adjust this plan now?", default=True):
        return modify_schedule_agent(llm_config, config_dir)

    return 0


def setup_command(args) -> int:
    del args  # command has no CLI flags yet

    try:
        llm_config = ensure_llm_config()
    except KeyboardInterrupt:
        CONSOLE.print("[bold yellow]Setup cancelled by user.[/]")
        return 1
    except Exception as exc:
        CONSOLE.print(f"[bold red]Failed to initialize LLM config:[/] {exc}")
        return 1

    config_dir = _resolve_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    is_complete, reason = has_completed_configuration(config_dir)

    if is_complete:
        CONSOLE.print(
            f"[bold green]Detected an existing completed configuration in[/] "
            f"[cyan]{config_dir}[/]."
        )
        if _ask_yes_no("Do you want to modify existing schedules?", default=False):
            return modify_schedule_agent(llm_config, config_dir)
        CONSOLE.print("[bright_black]No changes made.[/]")
        return 0

    CONSOLE.print(
        f"[bold yellow]No valid completed configuration detected[/] ({reason})."
    )
    if _ask_yes_no("Do you want to build a new schedule?", default=True):
        return build_schedule_agent(llm_config, config_dir)

    CONSOLE.print("[bright_black]No changes made.[/]")
    return 0


__all__ = [
    "LLMConfig",
    "has_completed_configuration",
    "load_llm_config",
    "save_llm_config",
    "ensure_llm_config",
    "build_schedule_agent",
    "modify_schedule_agent",
    "setup_command",
]
