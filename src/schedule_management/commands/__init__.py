"""
Commands Package - CLI command handlers for the schedule management system.

This package contains all CLI command implementations, organized by domain:
- tasks: Task management (add, delete, list)
- deadlines: Deadline management (add, delete, show)
- habits: Habit tracking commands
- status: Status and schedule viewing commands
- service: Service management (update, stop, report)
- setup: Interactive AI-assisted schedule setup
"""

from schedule_management.commands.tasks import add_task, delete_task, show_tasks
from schedule_management.commands.deadlines import (
    add_deadline,
    delete_deadline,
    show_deadlines,
)
from schedule_management.commands.habits import track_habits
from schedule_management.commands.status import status_command, view_command
from schedule_management.commands.service import (
    update_command,
    stop_command,
    report_command,
    edit_schedule_command,
)
from schedule_management.commands.setup import setup_command

__all__ = [
    # Task commands
    "add_task",
    "delete_task",
    "show_tasks",
    # Deadline commands
    "add_deadline",
    "delete_deadline",
    "show_deadlines",
    # Habit commands
    "track_habits",
    # Status commands
    "status_command",
    "view_command",
    # Service commands
    "update_command",
    "stop_command",
    "report_command",
    "edit_schedule_command",
    # Setup command
    "setup_command",
]
