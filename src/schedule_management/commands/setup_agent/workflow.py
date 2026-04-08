"""
Interactive setup command with OpenCode-powered schedule generation.

This module now focuses on the high-level build and modify flows while helper
logic lives in dedicated setup-agent submodules.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from rich.panel import Panel

from schedule_management.commands.setup_agent.attachments import (
    _load_source_attachment,
    _resolve_source_path_input,
)
from schedule_management.commands.setup_agent.configuration import (
    _ask_yes_no,
    _interpret_confirmation,
    _prompt_non_empty,
    _resolve_config_dir,
    _resolve_llm_config_path,
    ensure_llm_config,
    has_completed_configuration,
    load_llm_config,
    save_llm_config,
)
from schedule_management.commands.setup_agent.console import CONSOLE
from schedule_management.commands.setup_agent.interaction import (
    _append_conversation_history,
    _merge_request_with_details,
    _render_conversation_message,
    _render_current_files,
    _render_missing_information,
    _render_schedule_summary,
)
from schedule_management.commands.setup_agent.models import (
    AgentTurn,
    LLMConfig,
    SourceAttachment,
    ToolCall,
)
from schedule_management.commands.setup_agent.prompts import (
    BUILD_SYSTEM_PROMPT,
    MODIFY_SYSTEM_PROMPT,
    render_build_user_prompt,
    render_modify_user_prompt,
)
from schedule_management.commands.setup_agent.profile_store import (
    _load_profile_markdown,
    _resolve_profile_path,
    _write_profile_markdown,
)
from schedule_management.commands.setup_agent.response_parser import (
    _parse_agent_turn,
    _request_agent_turn,
)
from schedule_management.commands.setup_agent.tools import LocalFileTools

DEFAULT_HABITS_TOML = """[habits]\n# Example: 1 = "Read for 20 minutes"\n"""


def _build_local_file_tools(config_dir: Path) -> LocalFileTools:
    roots = [
        config_dir,
        Path.cwd(),
        Path.home(),
    ]
    return LocalFileTools(allowed_roots=roots)


def _resolve_opencode_submodule_dir() -> Path:
    return (Path(__file__).resolve().parents[4] / "third_party" / "opencode").resolve()


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
        if attachment and attachment.image_base64:
            return (
                f"{user_prompt}\n\n"
                f"An image attachment is included ({attachment.path.name}). "
                "The runtime already passed this image via native vision input, "
                "so inspect the image directly and do not ask the user to "
                "manually transcribe its full content."
            )
        return user_prompt

    return (
        f"{user_prompt}\n\n"
        f"Attached file content ({attachment.path.name}):\n"
        f"```\n{attachment.text_content}\n```"
    )


class LLMClient:
    """OpenCode-backed runtime adapter for setup-agent turns."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @staticmethod
    def _resolve_opencode_bin() -> str:
        explicit = os.getenv("REMINDER_OPENCODE_BIN", "").strip()
        if explicit:
            return explicit

        discovered = shutil.which("opencode")
        if discovered:
            return discovered

        submodule_dir = _resolve_opencode_submodule_dir()
        if submodule_dir.exists():
            install_script = submodule_dir / "install"
            raise RuntimeError(
                "OpenCode CLI not found in PATH. Install it with "
                f"'{install_script}' or set REMINDER_OPENCODE_BIN."
            )

        raise RuntimeError(
            "OpenCode CLI not found in PATH and opencode submodule is missing. "
            "Run 'git submodule update --init --recursive third_party/opencode' "
            "or set REMINDER_OPENCODE_BIN."
        )

    def _resolve_model(self) -> str:
        model = self.config.model.strip()
        if not model:
            raise RuntimeError("Model is empty in llm.toml")

        if "/" in model:
            return model

        provider_prefix = {
            "openai": "openai",
            "openai_compatible": "openai",
            "anthropic": "anthropic",
            "gemini": "google",
        }.get(self.config.vendor)

        if provider_prefix is None:
            raise RuntimeError(f"Unsupported vendor: {self.config.vendor}")

        return f"{provider_prefix}/{model}"

    def _build_provider_environment(self) -> dict[str, str]:
        api_key = self.config.api_key.strip()
        if not api_key:
            raise RuntimeError("Missing API key in llm.toml")

        vendor = self.config.vendor
        env: dict[str, str] = {}

        if vendor in {"openai", "openai_compatible"}:
            env["OPENAI_API_KEY"] = api_key
            if vendor == "openai_compatible":
                if not self.config.base_url:
                    raise RuntimeError(
                        "Missing base_url for openai_compatible vendor in llm.toml"
                    )
                env["OPENAI_BASE_URL"] = _normalize_openai_base_url(
                    self.config.base_url
                )
            return env

        if vendor == "anthropic":
            env["ANTHROPIC_API_KEY"] = api_key
            return env

        if vendor == "gemini":
            env["GOOGLE_API_KEY"] = api_key
            env["GEMINI_API_KEY"] = api_key
            env["GOOGLE_GENERATIVE_AI_API_KEY"] = api_key
            return env

        raise RuntimeError(f"Unsupported vendor: {vendor}")

    @staticmethod
    def _compose_prompt(
        system_prompt: str,
        user_prompt: str,
        attachment: SourceAttachment | None,
    ) -> str:
        enriched_user = _add_text_attachment(user_prompt, attachment)
        return (
            "Follow the system instructions strictly for this single turn.\n"
            "<system>\n"
            f"{system_prompt.strip()}\n"
            "</system>\n\n"
            "<user>\n"
            f"{enriched_user.strip()}\n"
            "</user>\n\n"
            "Return only the final assistant response for this turn."
        )

    @staticmethod
    def _extract_opencode_error_message(error_payload: Any) -> str:
        if isinstance(error_payload, str):
            return error_payload.strip()

        if isinstance(error_payload, dict):
            data = error_payload.get("data")
            if isinstance(data, dict):
                message = data.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()

            message = error_payload.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()

            name = error_payload.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()

        return str(error_payload).strip()

    @classmethod
    def _parse_opencode_json_events(cls, stdout: str) -> tuple[str, str | None]:
        texts: list[str] = []
        errors: list[str] = []

        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(event, dict):
                continue

            event_type = event.get("type")
            if event_type == "text":
                part = event.get("part")
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
                continue

            if event_type == "error":
                message = cls._extract_opencode_error_message(event.get("error"))
                if message:
                    errors.append(message)

        rendered_text = "\n\n".join(texts).strip()
        rendered_error = "\n".join(errors).strip() or None
        return rendered_text, rendered_error

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        attachment: SourceAttachment | None = None,
        on_text: Callable[[str], None] | None = None,
        file_tools: LocalFileTools | None = None,
        on_tool_activity: Callable[[str], None] | None = None,
    ) -> str:
        command = [
            self._resolve_opencode_bin(),
            "run",
            "--model",
            self._resolve_model(),
            "--format",
            "json",
        ]
        if attachment is not None:
            command.extend(["--file", str(attachment.path)])

        command.append(self._compose_prompt(system_prompt, user_prompt, attachment))

        env = os.environ.copy()
        env.update(self._build_provider_environment())
        env.setdefault("OPENCODE_CLIENT", "schedule-management-setup")

        if on_tool_activity is not None:
            if file_tools is None:
                on_tool_activity("OpenCode agent is running...")
            else:
                on_tool_activity(
                    "OpenCode agent is running with built-in tooling support..."
                )

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        parsed_text, parsed_error = self._parse_opencode_json_events(stdout)

        if completed.returncode != 0:
            detail = (
                parsed_error
                or stderr
                or parsed_text
                or stdout
                or f"exit code {completed.returncode}"
            )
            raise RuntimeError(f"OpenCode CLI execution failed: {detail}")

        response_text = parsed_text
        if not response_text and parsed_error:
            raise RuntimeError(f"OpenCode CLI reported an error: {parsed_error}")

        if not response_text and stdout:
            response_text = stdout

        if not response_text and stderr:
            raise RuntimeError(f"OpenCode CLI stderr: {stderr}")

        if not response_text:
            raise RuntimeError("OpenCode CLI returned an empty response")

        if on_text is not None:
            on_text(response_text)

        return response_text


def _write_bundle(config_dir: Path, bundle: dict[str, str]) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    for file_name, content in bundle.items():
        target = config_dir / file_name
        target.write_text(content, encoding="utf-8")


def _persist_profile_draft(config_dir: Path, profile_markdown: str | None) -> str | None:
    if not profile_markdown:
        return None
    _write_profile_markdown(config_dir, profile_markdown)
    return profile_markdown.strip()


def _turn_requests_manual_image_transcription(turn: AgentTurn) -> bool:
    combined = " ".join(
        [
            turn.conversation,
            turn.question_to_user or "",
            " ".join(turn.missing_information),
        ]
    ).lower()

    if not combined:
        return False

    blindness_markers = (
        "cannot see image",
        "can't see image",
        "cannot see images",
        "can't see images",
        "cannot view image",
        "can't view image",
        "unable to see image",
        "unable to view image",
    )
    if any(marker in combined for marker in blindness_markers):
        return True

    manual_description_markers = (
        "describe the image",
        "describe changes from the image",
        "details from the image",
        "what is in the image",
        "transcribe the image",
        "type out the image",
    )
    if "image" not in combined:
        return False
    if not any(marker in combined for marker in manual_description_markers):
        return False

    quality_markers = (
        "blurry",
        "unclear",
        "low resolution",
        "cropped",
        "not legible",
        "hard to read",
    )
    return not any(marker in combined for marker in quality_markers)


def modify_schedule_agent(llm_config: LLMConfig, config_dir: Path) -> int:
    client = LLMClient(llm_config)
    file_tools = _build_local_file_tools(config_dir)
    current_profile = _load_profile_markdown(config_dir)
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
                profile_context=current_profile,
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
            updated_profile = _persist_profile_draft(
                config_dir,
                turn.profile_markdown,
            )
            if updated_profile is not None:
                current_profile = updated_profile

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
    current_profile = _load_profile_markdown(config_dir)
    CONSOLE.print(
        Panel.fit(
            "Hello! I can help build your first schedule configuration.",
            title="Build",
            border_style="green",
        )
    )
    if current_profile:
        CONSOLE.print(
            f"[bright_black]Loaded existing profile draft from "
            f"{_resolve_profile_path(config_dir)}.[/]"
        )
    else:
        CONSOLE.print(
            f"[bright_black]No profile draft found at {_resolve_profile_path(config_dir)}. "
            "The agent will build one with you first.[/]"
        )

    attachment: SourceAttachment | None = None
    description: str | None = None

    if _ask_yes_no(
        "Can you provide a path to an image/file describing your timetable?",
        default=True,
    ):
        source_path = _prompt_non_empty("Enter path: ")
        resolved_source_path = _resolve_source_path_input(source_path)
        loaded, error = _load_source_attachment(resolved_source_path)
        if loaded is None:
            CONSOLE.print(f"[bold yellow]{error}[/]")
            description = _prompt_non_empty(
                "Please provide a short text description instead: "
            )
        else:
            if resolved_source_path != Path(source_path).expanduser():
                CONSOLE.print(
                    "[bold cyan]Detected file in a common folder:[/] "
                    f"[cyan]{resolved_source_path}[/]"
                )
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
            profile_context=current_profile,
            summary_presented=summary_presented,
            summary_confirmed=summary_confirmed,
            latest_summary=latest_summary,
        )

        def _build_turn_validator(turn: AgentTurn) -> str | None:
            if (
                attachment is not None
                and attachment.image_base64 is not None
                and _turn_requests_manual_image_transcription(turn)
            ):
                return (
                    "Image is already attached through native vision input. "
                    "Do not claim you cannot see images or ask the user to "
                    "transcribe image details manually. Analyze the attachment "
                    "directly and only ask targeted clarifications if content "
                    "is ambiguous."
                )
            if turn.phase == "summary" and not turn.profile_markdown:
                return (
                    "Build flow violation: summary phase requires a complete "
                    "profile_markdown draft."
                )
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
            if turn.phase == "final" and not turn.profile_markdown:
                return (
                    "Build flow violation: final phase requires profile_markdown "
                    "together with the TOML files."
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
        updated_profile = _persist_profile_draft(
            config_dir,
            turn.profile_markdown,
        )
        if updated_profile is not None:
            current_profile = updated_profile

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
    "AgentTurn",
    "LLMClient",
    "LLMConfig",
    "LocalFileTools",
    "SourceAttachment",
    "ToolCall",
    "build_schedule_agent",
    "ensure_llm_config",
    "has_completed_configuration",
    "load_llm_config",
    "modify_schedule_agent",
    "save_llm_config",
    "setup_command",
]
