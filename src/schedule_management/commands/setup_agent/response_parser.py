"""
Response parsing and retry logic for setup-agent turns.

The setup agent must return a constrained JSON payload; this module validates
that contract and retries with corrective feedback when needed.
"""

from __future__ import annotations

import json
import re
import tomllib
from typing import Any, Callable

from schedule_management.commands.setup_agent.console import CONSOLE
from schedule_management.commands.setup_agent.models import AgentTurn, SourceAttachment
from schedule_management.commands.setup_agent.prompts import render_retry_user_prompt
from schedule_management.commands.setup_agent.tools import LocalFileTools

VALID_AGENT_PHASES = {"discovery", "summary", "final"}


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

    profile_markdown_raw = payload.get("profile_markdown")
    profile_markdown: str | None = None
    if profile_markdown_raw is not None:
        if not isinstance(profile_markdown_raw, str):
            return None, "'profile_markdown' must be a string when provided"
        profile_markdown = profile_markdown_raw.strip()
        if not profile_markdown:
            return None, "'profile_markdown' cannot be empty when provided"

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
            profile_markdown=profile_markdown,
            question_to_user=question_to_user,
            missing_information=missing_information,
            actions=actions,
            schedule_summary=schedule_summary,
            bundle=bundle,
        ),
        None,
    )


def _request_agent_turn(
    client: Any,
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
                    attachment,
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
