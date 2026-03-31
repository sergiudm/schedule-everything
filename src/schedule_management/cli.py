"""
CLI - Command-line interface entry point for Schedule Everything.

This module provides the main CLI entry point that routes user commands
to their appropriate handlers. It uses argparse to parse commands and
delegates to the various command modules.

Architecture:
    cli.py (this file)
    ├── commands/tasks.py     - add, rm, ls commands
    ├── commands/deadlines.py - ddl add, rm, show commands
    ├── commands/habits.py    - track command
    ├── commands/status.py    - status, view commands
    ├── commands/service.py   - update, stop, report commands
    └── commands/setup.py     - setup command

Entry Points:
    - `reminder`: The main CLI command (defined in pyproject.toml)
    - `reminder-runner`: The background service (in runner.py)

Example Usage:
    $ reminder                  # Show help
    $ reminder add "task" 5     # Add task with priority 5
    $ reminder ls               # List all tasks
    $ reminder ddl add hw 12.15 # Add deadline for Dec 15
    $ reminder status           # Show current status
    $ reminder status -v        # Show verbose schedule

Module Dependencies:
    - schedule_management.commands.tasks
    - schedule_management.commands.deadlines
    - schedule_management.commands.habits
    - schedule_management.commands.status
    - schedule_management.commands.service
    - schedule_management.commands.setup
"""

import argparse
import os
import sys
from pathlib import Path

import schedule_management
from schedule_management import COLORS

# Import command handlers from organized modules
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


# =============================================================================
# ARGUMENT PARSER SETUP
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser for the CLI.

    Returns:
        Configured ArgumentParser with all subcommands registered.

    Structure:
        reminder
        ├── add <task> <priority>       - Add new task
        ├── rm <tasks...>               - Remove tasks
        ├── ls                          - List tasks
        ├── ddl                         - Deadline management
        │   ├── add <event> <date>      - Add deadline
        │   └── rm <events...>          - Remove deadlines
        ├── track [habit_ids...]        - Track habits
        ├── status [-v]                 - Show current status
        ├── view                        - Generate PDF visualization
        ├── update                      - Update config from git
        ├── stop                        - Stop reminder service
        ├── report <type>               - Generate report
        ├── edit <file>                 - Edit config file
        └── setup                       - Interactive schedule setup
    """
    # Resolve config directory at runtime so test fixtures and env overrides apply.
    config_dir = (
        schedule_management.CONFIG_DIR or os.getenv("REMINDER_CONFIG_DIR") or "config"
    )
    config_dir_path = Path(config_dir).expanduser().resolve()

    # Build colored help text
    colored_description = (
        f"{COLORS['BOLD']}{COLORS['CYAN']}Reminder CLI{COLORS['RESET']} - "
        f"{COLORS['GREEN']}Manage your schedule management system{COLORS['RESET']}"
    )

    colored_epilog = f"""
{COLORS["UNDERLINE"]}{COLORS["YELLOW"]}Configuration directory:{COLORS["RESET"]} {COLORS["BLUE"]}{config_dir_path}{COLORS["RESET"]}
    """

    # Create main parser
    parser = argparse.ArgumentParser(
        prog="reminder",
        description=colored_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=colored_epilog,
    )

    # Create subparsers container
    subparsers = parser.add_subparsers(
        dest="command",
        title="Available commands",
        metavar="<command>",
    )

    # -------------------------------------------------------------------------
    # Task Management Commands
    # -------------------------------------------------------------------------

    # add - Add new task
    add_parser = subparsers.add_parser(
        "add",
        help="Add a new task with description and priority level (1-10)",
        description="Add a task to your task list with a priority level.",
    )
    add_parser.add_argument(
        "task",
        help="Description of the task (e.g., 'biology homework')",
    )
    add_parser.add_argument(
        "priority",
        type=int,
        choices=range(1, 11),
        metavar="PRIORITY",
        help="Priority level 1-10 (higher = more important)",
    )
    add_parser.set_defaults(func=add_task)

    # rm - Delete tasks
    delete_parser = subparsers.add_parser(
        "rm",
        help="Delete one or more tasks by description or ID",
        description="Remove tasks from your task list.",
    )
    delete_parser.add_argument(
        "tasks",
        nargs="+",
        help="Task descriptions or ID numbers from 'reminder ls'",
    )
    delete_parser.set_defaults(func=delete_task)

    # ls - List tasks
    show_parser = subparsers.add_parser(
        "ls",
        help="Show all tasks sorted by importance",
        description="Display your task list sorted by priority.",
    )
    show_parser.set_defaults(func=show_tasks)

    # -------------------------------------------------------------------------
    # Deadline Management Commands
    # -------------------------------------------------------------------------

    # ddl - Deadline management (with subcommands)
    ddl_parser = subparsers.add_parser(
        "ddl",
        help="Manage deadlines (use 'ddl add' or just 'ddl' to list)",
        description="Deadline management. Without subcommand, shows all deadlines.",
    )
    ddl_subparsers = ddl_parser.add_subparsers(
        dest="ddl_command",
        title="Deadline commands",
    )

    # ddl add
    ddl_add_parser = ddl_subparsers.add_parser(
        "add",
        help="Add a new deadline event",
        description="Add a deadline with name and due date.",
    )
    ddl_add_parser.add_argument(
        "event",
        help="Name of the event (e.g., 'homework2')",
    )
    ddl_add_parser.add_argument(
        "date",
        help="Due date in M.D or MM.DD format (e.g., '7.4' for July 4th)",
    )
    ddl_add_parser.set_defaults(func=add_deadline)

    # ddl rm
    ddl_rm_parser = ddl_subparsers.add_parser(
        "rm",
        help="Delete one or more deadline events",
        description="Remove deadlines by their event names.",
    )
    ddl_rm_parser.add_argument(
        "events",
        nargs="+",
        help="Event names to delete (e.g., 'homework2' 'project')",
    )
    ddl_rm_parser.set_defaults(func=delete_deadline)

    # Default: show deadlines when 'ddl' called without subcommand
    ddl_parser.set_defaults(func=show_deadlines)

    # -------------------------------------------------------------------------
    # Habit Tracking Commands
    # -------------------------------------------------------------------------

    # track - Track habits
    track_parser = subparsers.add_parser(
        "track",
        help="Track completed habits for today",
        description="Mark habits as completed. Opens interactive prompt if no IDs given.",
    )
    track_parser.add_argument(
        "habit_ids",
        nargs="*",
        help="Optional habit IDs to mark complete (e.g., '1 2 3')",
    )
    track_parser.set_defaults(func=track_habits)

    # -------------------------------------------------------------------------
    # Status and Visualization Commands
    # -------------------------------------------------------------------------

    # status - Show current status
    status_parser = subparsers.add_parser(
        "status",
        help="Show current status and next events",
        description="Display current event, next scheduled event, and optionally full schedule.",
    )
    status_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed schedule for today",
    )
    status_parser.set_defaults(func=status_command)

    # view - Generate PDF visualization
    view_parser = subparsers.add_parser(
        "view",
        help="Generate schedule visualizations",
        description="Create a multi-page PDF visualization of your schedules.",
    )
    view_parser.set_defaults(func=view_command)

    # -------------------------------------------------------------------------
    # Service Management Commands
    # -------------------------------------------------------------------------

    # update - Update config from git
    update_parser = subparsers.add_parser(
        "update",
        help="Update configuration from git repository",
        description="Pull latest schedule files from remote git repository.",
    )
    update_parser.set_defaults(func=update_command)

    # stop - Stop reminder service
    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop the reminder service",
        description="Stop the running reminder-runner background service.",
    )
    stop_parser.set_defaults(func=stop_command)

    # report - Generate report
    report_parser = subparsers.add_parser(
        "report",
        help="Generate weekly or monthly PDF reports",
        description="Generate a productivity report for a specified time period.",
    )
    report_parser.add_argument(
        "type",
        choices=["weekly", "monthly"],
        help="Type of report to generate",
    )
    report_parser.add_argument(
        "-d",
        "--date",
        help="Target date in YYYY-MM-DD format (default: today)",
    )
    report_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to include (default: 7)",
    )
    report_parser.set_defaults(func=report_command)

    # edit - Edit config file
    edit_parser = subparsers.add_parser(
        "edit",
        help="Edit schedule configuration files",
        description="Open a configuration file in your editor.",
    )
    edit_parser.add_argument(
        "file",
        choices=["settings", "odd", "even", "deadlines", "ddl", "habits"],
        nargs="?",
        default="settings",
        help="File to edit (default: settings)",
    )
    edit_parser.set_defaults(func=edit_schedule_command)

    # setup - Interactive LLM-assisted setup
    setup_parser = subparsers.add_parser(
        "setup",
        help="Interactive setup with LLM-assisted schedule generation",
        description=(
            "Configure model credentials and build or modify schedules "
            "through an interactive wizard."
        ),
    )
    setup_parser.set_defaults(func=setup_command)

    return parser


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main() -> int:
    """
    Main entry point for the reminder CLI.

    Parses command-line arguments and dispatches to the appropriate
    command handler. Shows help if no command is provided.

    Returns:
        Exit code (0 for success, 1 for error)

    Exit Codes:
        0 - Success
        1 - Error or no command provided

    Examples:
        >>> main()  # With sys.argv = ['reminder', 'ls']
        # Displays task list
        0

        >>> main()  # With sys.argv = ['reminder']
        # Displays help text
        1
    """
    parser = create_parser()
    args = parser.parse_args()

    # Show help if no command provided
    if not args.command:
        parser.print_help()
        return 1

    # Execute the command handler
    try:
        result = args.func(args)
        return result if isinstance(result, int) else 0

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        return 1

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        # For debugging, uncomment:
        # import traceback
        # traceback.print_exc()
        return 1


# =============================================================================
# SCRIPT EXECUTION
# =============================================================================

if __name__ == "__main__":
    sys.exit(main())
