"""LLM setup agent package for the `reminder setup` command."""

from schedule_management.commands.setup_agent.models import (
    AgentTurn,
    LLMConfig,
    SourceAttachment,
    ToolCall,
)
from schedule_management.commands.setup_agent.tools import LocalFileTools
from schedule_management.commands.setup_agent.workflow import (
    LLMClient,
    build_schedule_agent,
    modify_schedule_agent,
)

__all__ = [
    "LLMConfig",
    "SourceAttachment",
    "AgentTurn",
    "ToolCall",
    "LocalFileTools",
    "LLMClient",
    "build_schedule_agent",
    "modify_schedule_agent",
]
