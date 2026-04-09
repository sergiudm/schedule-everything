"""
Interactive config helpers for the setup agent.

This module owns the persisted LLM settings file and the terminal prompts used
to create or validate it.
"""

from __future__ import annotations

import getpass
import json
import os
import stat
import sys
import termios
import tty
from pathlib import Path
from typing import Any

import tomllib
from rich.panel import Panel

from schedule_management.config_layout import resolve_active_config_dir
from schedule_management.commands.setup_agent.console import CONSOLE
from schedule_management.commands.setup_agent.models import LLMConfig

SUPPORTED_VENDORS: list[tuple[str, str]] = [
    ("openai", "OpenAI"),
    ("openai_compatible", "OpenAI compatible"),
    ("anthropic", "Anthropic"),
    ("gemini", "Gemini"),
]
SUPPORTED_VENDOR_SET = {item[0] for item in SUPPORTED_VENDORS}

REQUIRED_CONFIG_FILES = (
    "settings.toml",
    "odd_weeks.toml",
    "even_weeks.toml",
    "habits.toml",
)


def _resolve_config_dir() -> Path:
    return resolve_active_config_dir(create=True)


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
