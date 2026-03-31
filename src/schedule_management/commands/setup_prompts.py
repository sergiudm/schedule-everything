"""Compatibility facade for setup-agent prompt templates."""

from schedule_management.commands.setup_agent.prompts import (
    BUILD_SYSTEM_PROMPT,
    MODIFY_SYSTEM_PROMPT,
    render_build_user_prompt,
    render_modify_user_prompt,
    render_retry_user_prompt,
)

__all__ = [
    "BUILD_SYSTEM_PROMPT",
    "MODIFY_SYSTEM_PROMPT",
    "render_build_user_prompt",
    "render_modify_user_prompt",
    "render_retry_user_prompt",
]
