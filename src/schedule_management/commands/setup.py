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
    ) -> str:
        if self.config.vendor in {"openai", "openai_compatible"}:
            return self._openai_response(
                system_prompt,
                user_prompt,
                attachment,
                on_text=on_text,
            )

        if self.config.vendor == "anthropic":
            return self._anthropic_chat(
                system_prompt,
                user_prompt,
                attachment,
                on_text=on_text,
            )

        if self.config.vendor == "gemini":
            return self._gemini_chat(
                system_prompt,
                user_prompt,
                attachment,
                on_text=on_text,
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
    ) -> str:
        client = self._get_openai_client()
        user_prompt_with_text = _add_text_attachment(user_prompt, attachment)

        user_content: list[dict[str, Any]] = [
            {"type": "input_text", "text": user_prompt_with_text}
        ]
        if attachment and attachment.image_base64:
            image_url = f"data:{attachment.mime_type};base64,{attachment.image_base64}"
            user_content.append({"type": "input_image", "image_url": image_url})

        streamed_chunks: list[str] = []
        with client.responses.stream(
            model=self.config.model,
            temperature=0.2,
            instructions=system_prompt,
            input=[
                {
                    "role": "user",
                    "content": user_content,
                }
            ],
        ) as stream:
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

        content = _extract_openai_response_text(response)
        if not content:
            content = "".join(streamed_chunks).strip()
        if not content:
            raise RuntimeError(
                f"OpenAI response did not contain text content: {response}"
            )
        return content

    def _anthropic_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        attachment: SourceAttachment | None,
        *,
        on_text: Callable[[str], None] | None,
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

        streamed_chunks: list[str] = []
        with client.messages.stream(
            model=self.config.model,
            max_tokens=1800,
            temperature=0.2,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        ) as stream:
            for delta in stream.text_stream:
                if isinstance(delta, str) and delta:
                    streamed_chunks.append(delta)
                    if on_text is not None:
                        on_text(delta)

            final_message = stream.get_final_message()

        combined = "".join(streamed_chunks).strip()
        if combined:
            return combined

        blocks = getattr(final_message, "content", None)
        if blocks is None and isinstance(final_message, dict):
            blocks = final_message.get("content")

        if not isinstance(blocks, list):
            raise RuntimeError(
                f"Unexpected Anthropic response payload: {final_message}"
            )

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

        if not texts:
            raise RuntimeError(
                f"Anthropic response did not contain text: {final_message}"
            )
        return "\n".join(texts)

    def _gemini_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        attachment: SourceAttachment | None,
        *,
        on_text: Callable[[str], None] | None,
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

        response_stream = client.models.generate_content_stream(
            model=self.config.model,
            contents=[genai_types.Content(role="user", parts=parts)],
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
            ),
        )

        streamed_chunks: list[str] = []
        for chunk in response_stream:
            chunk_text = getattr(chunk, "text", None)
            if chunk_text is None and isinstance(chunk, dict):
                chunk_text = chunk.get("text")
            if not isinstance(chunk_text, str) or not chunk_text:
                continue
            streamed_chunks.append(chunk_text)
            if on_text is not None:
                on_text(chunk_text)

        text = "".join(streamed_chunks).strip()
        if not text:
            raise RuntimeError("Gemini response did not contain text")
        return text


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
            ):
                response_text = client.generate(
                    system_prompt,
                    prompt,
                    attachment if attempt == 1 else None,
                    on_text=None,
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
