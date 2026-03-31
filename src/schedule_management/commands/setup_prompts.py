"""
Prompt templates for the interactive setup LLM agents.

This module centralizes all system and user message templates for build and
modify schedule flows. The templates enforce a strict, sectioned JSON output
contract for a multi-turn conversation where only the `conversation` section
is shown to the end user.
"""

from __future__ import annotations

from pathlib import Path

OUTPUT_SCHEMA_GUIDE = """
Return exactly one JSON object with tagged top-level sections/keys:
- conversation (required string, user-facing only)
- actions (optional array of strings, internal-only)
- needs_user_input (required boolean)
- question_to_user (required non-empty string when needs_user_input is true)
- missing_information (optional array of strings)
- settings_toml (required when needs_user_input is false)
- odd_weeks_toml (required when needs_user_input is false)
- even_weeks_toml (required when needs_user_input is false)
- habits_toml (optional when needs_user_input is false)

Output constraints:
1) Return raw JSON only. Do not wrap it in markdown.
2) `conversation` must summarize the turn naturally and clearly.
3) `actions` must describe internal operations; do not include user-facing text.
4) If `needs_user_input` is true, do not return any *_toml keys.
5) If `needs_user_input` is false, return complete TOML for required files.
6) Every *_toml value must be a complete TOML document string parseable by tomllib.
7) Time keys in week schedules must use 24-hour HH:MM format.
8) Keep event labels short and reusable.
""".strip()

MULTI_TURN_RULES = """
This is a multi-turn assistant, not a single-turn generator.

Per turn behavior:
- Always process the latest user instruction.
- If information is sufficient, complete the task and return TOML sections.
- If information is insufficient, set needs_user_input=true and ask one focused question.
- Always provide a concise `conversation` summary for the user.
- Keep `actions` internal and machine-oriented because only `conversation` is user-visible.
""".strip()

BUILD_SYSTEM_PROMPT = f"""
You are build_schedule_agent for a local CLI scheduling tool.

Mission:
- Build an initial, practical, and editable schedule configuration.
- Use user-provided timetable context (text and/or image) as primary input.
- Fill missing details with reasonable defaults while keeping structure simple.

{MULTI_TURN_RULES}

Domain rules:
1) settings_toml must include sections: [settings], [time_blocks], [time_points], [tasks], [paths].
2) odd_weeks_toml and even_weeks_toml should contain weekday tables and [common].
3) If user does not describe odd/even differences, keep odd and even schedules aligned.
4) Any event label used in week schedules should be compatible with time_blocks or time_points.
5) Keep task and reminder defaults conservative and realistic for daily use.

Quality bar:
- Schedules should be coherent and avoid impossible overlaps where feasible.
- Prefer stable, maintainable naming for labels.
- Preserve user intent over speculative assumptions.

{OUTPUT_SCHEMA_GUIDE}
""".strip()

MODIFY_SYSTEM_PROMPT = f"""
You are modify_schedule_agent for a local CLI scheduling tool.

Mission:
- Apply the user's requested changes to existing schedule TOML files.
- Keep unrelated content stable to minimize unnecessary diffs.
- Preserve the user's established naming and structure unless a change requires updates.

{MULTI_TURN_RULES}

Editing rules:
1) Make the smallest effective edit set that satisfies the request.
2) Keep unchanged sections and keys untouched where possible.
3) Maintain consistency between schedule labels and settings definitions.
4) Preserve TOML validity and 24-hour HH:MM time keys.
5) If a requested change is ambiguous, choose the most conservative interpretation.

{OUTPUT_SCHEMA_GUIDE}
""".strip()


def render_build_user_prompt(
    config_dir: Path,
    *,
    description: str | None,
    attachment_name: str | None,
    conversation_history: str | None = None,
) -> str:
    """Create the build agent user message with full context and requirements."""
    user_description = (
        description.strip() if description else "No text description provided."
    )
    source_hint = attachment_name if attachment_name else "No attachment provided."
    history = (
        conversation_history.strip() if conversation_history else "(no prior turns)"
    )

    return "\n\n".join(
        [
            "Task: Create a first version of the local schedule configuration.",
            f"Target config directory: {config_dir}",
            (
                "Schedule file expectations: settings.toml, odd_weeks.toml, "
                "even_weeks.toml, optional habits.toml."
            ),
            f"User description:\n{user_description}",
            f"Attached source file name: {source_hint}",
            f"Conversation history:\n{history}",
            (
                "When uncertain, choose practical defaults and keep the output "
                "easy to modify in future iterations."
            ),
            OUTPUT_SCHEMA_GUIDE,
        ]
    )


def render_modify_user_prompt(
    change_request: str,
    current_files: str,
    *,
    conversation_history: str | None = None,
) -> str:
    """Create the modify agent user message with current TOML context."""
    history = (
        conversation_history.strip() if conversation_history else "(no prior turns)"
    )
    return "\n\n".join(
        [
            "Task: Update existing schedule TOML files according to the user's request.",
            f"Change request:\n{change_request.strip()}",
            "Current configuration files:",
            current_files.strip()
            if current_files.strip()
            else "(No current files found)",
            f"Conversation history:\n{history}",
            "Apply only necessary changes and preserve unrelated content.",
            OUTPUT_SCHEMA_GUIDE,
        ]
    )


def render_retry_user_prompt(
    *,
    original_user_prompt: str,
    parse_error: str,
    previous_response: str,
) -> str:
    """Create a strict retry message when the previous model output was invalid."""
    return "\n\n".join(
        [
            "Your previous response could not be parsed by the CLI.",
            f"Parse error: {parse_error}",
            "You must correct the response and follow the exact JSON contract.",
            "Original task prompt:",
            original_user_prompt.strip(),
            "Previous invalid response:",
            previous_response.strip() or "(empty response)",
            "Remember: show user-facing text only in `conversation`; keep internal work in `actions`.",
            OUTPUT_SCHEMA_GUIDE,
            "Return corrected JSON only.",
        ]
    )


__all__ = [
    "BUILD_SYSTEM_PROMPT",
    "MODIFY_SYSTEM_PROMPT",
    "render_build_user_prompt",
    "render_modify_user_prompt",
    "render_retry_user_prompt",
]
