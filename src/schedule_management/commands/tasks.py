"""
Task Commands - CLI commands for task management.

This module provides CLI command handlers for managing tasks:
- add_task: Add a new task with priority
- delete_task: Remove one or more tasks
- show_tasks: Display all tasks in a formatted table

Tasks are stored in a JSON file with 'description' and 'priority' fields.
All actions are logged to the task log for history tracking.

Example Usage (via CLI):
    $ rmd add "Study math" 8        # Add task with priority 8
    $ rmd ls                         # List all tasks
    $ rmd rm 1                       # Delete task by ID
    $ rmd rm "Study math"            # Delete task by description
"""

import sys
from datetime import datetime
from typing import Any
from schedule_management.i18n import _t

try:
    from rich import box
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print(_t("Please install the 'rich' library: pip install rich"))
    sys.exit(1)

from schedule_management.data import (
    load_tasks,
    save_tasks,
    load_procrastinate_list,
    load_procrastinate_records,
    save_procrastinate_list,
    get_procrastinate_age_days,
    log_task_action,
)


# =============================================================================
# ADD TASK COMMAND
# =============================================================================


def add_task(args) -> int:
    """
    Handle the 'add' command - add a new task to the CLI-managed task list.

    If a task with the same description already exists, updates
    its priority instead of creating a duplicate.

    Args:
        args: Namespace with 'task' (description), 'priority' (int), and optional 'postpone' (int)

    Returns:
        0 on success, 1 on error

    Example:
        $ rmd add "Complete homework" 7 1
        ✅ Task 'Complete homework' added successfully with priority 7! (Daily urgent alarm postponed until 2026-05-27)
    """
    task_description = args.task
    priority = args.priority
    postpone = getattr(args, "postpone", None)

    # Validate priority
    if priority <= 0:
        print(_t("❌ Error: Priority must be a positive integer"))
        return 1

    # Validate postpone
    alarm_from = None
    if postpone is not None and isinstance(postpone, int):
        if postpone < 0:
            print(_t("❌ Error: Postpone days must be a non-negative integer"))
            return 1
        if postpone > 0:
            from datetime import timedelta
            alarm_from_date = datetime.now().date() + timedelta(days=postpone)
            alarm_from = alarm_from_date.isoformat()

    # Load existing tasks
    tasks = load_tasks()

    # Check for existing task with same description
    existing_task_index = None
    for i, task in enumerate(tasks):
        if task["description"] == task_description:
            existing_task_index = i
            break

    # Create new task
    new_task = {
        "description": task_description,
        "priority": priority,
    }
    if alarm_from:
        new_task["alarm_from"] = alarm_from

    # Update existing or add new
    if existing_task_index is not None:
        old_priority = tasks[existing_task_index]["priority"]
        tasks[existing_task_index] = new_task
        suffix = _t(" (Daily urgent alarm postponed until {alarm_from})").format(alarm_from=alarm_from) if alarm_from else ""
        action_msg = _t("✅ Task '{task_description}' updated! Priority changed from {old_priority} to {priority}").format(
            task_description=task_description, old_priority=old_priority, priority=priority
        ) + suffix

        # Log the update
        try:
            log_task_action("updated", new_task, {"old_priority": old_priority})
        except Exception as e:
            print(_t("⚠️  Warning: Could not log task update: {e}").format(e=e))
    else:
        tasks.append(new_task)
        suffix = _t(" (Daily urgent alarm postponed until {alarm_from})").format(alarm_from=alarm_from) if alarm_from else ""
        action_msg = _t("✅ Task '{task_description}' added successfully with priority {priority}!").format(
            task_description=task_description, priority=priority
        ) + suffix

        # Log the addition
        try:
            log_task_action("added", new_task)
        except Exception as e:
            print(_t("⚠️  Warning: Could not log task addition: {e}").format(e=e))

    # Save tasks
    try:
        save_tasks(tasks)
        print(action_msg)
        return 0
    except Exception as e:
        print(_t("❌ Error saving task: {e}").format(e=e))
        return 1


# =============================================================================
# DELETE TASK COMMAND
# =============================================================================


def delete_task(args) -> int:
    """
    Handle the 'rm' command - delete one or more tasks.

    Tasks can be identified by:
    - ID number (from 'rmd ls' output)
    - Exact description text

    Args:
        args: Namespace with 'tasks' (list of identifiers)

    Returns:
        0 on success, 1 if any deletions failed

    Example:
        $ rmd rm 1 2 3
        ✅ 3 sets of tasks deleted successfully

        $ rmd rm "Study math"
        ✅ Task 'Study math' deleted successfully!
    """
    task_identifiers = args.tasks

    # Load existing tasks
    tasks = load_tasks()
    procrastinate_list = load_procrastinate_list()
    procrastinate_updated = False

    if not tasks:
        print(_t("⚠️  No tasks found to delete"))
        return 1

    # Sort tasks into three sections (procrastinated -> current -> incoming)
    # ordered by priority descending in each section to match show_tasks display
    today = datetime.now().date()
    sorted_tasks = _sort_tasks_by_section_and_priority(tasks, today, procrastinate_list)

    total_deleted_count = 0
    all_errors = []
    successful_deletions = []

    for task_identifier in task_identifiers:
        # Try to parse as integer ID first
        try:
            task_id = int(task_identifier)

            # Validate ID range
            if task_id < 1 or task_id > len(sorted_tasks):
                error_msg = _t("❌ Invalid task ID: {task_id}. Please use a number between 1 and {length}").format(
                    task_id=task_id, length=len(sorted_tasks)
                )
                all_errors.append(error_msg)
                continue

            # Get task by ID (1-indexed)
            task_to_delete = sorted_tasks[task_id - 1]
            task_description = task_to_delete["description"]

            # Remove from original tasks list
            original_count = len(tasks)
            deleted_tasks = [t for t in tasks if t["description"] == task_description]
            tasks = [t for t in tasks if t["description"] != task_description]

        except ValueError:
            # Treat as string description
            task_description = task_identifier
            original_count = len(tasks)
            deleted_tasks = [t for t in tasks if t["description"] == task_description]
            tasks = [t for t in tasks if t["description"] != task_description]

        # Check if anything was deleted
        if len(tasks) == original_count:
            error_msg = _t("❌ Task '{task_description}' not found").format(
                task_description=task_description
            )
            all_errors.append(error_msg)
            continue

        # Log deletions
        try:
            for deleted_task in deleted_tasks:
                log_task_action("deleted", deleted_task)
        except Exception as e:
            print(_t("⚠️  Warning: Could not log task deletion: {e}").format(e=e))

        # Keep procrastinate list in sync with completed tasks
        for deleted_task in deleted_tasks:
            description = deleted_task.get("description")
            if isinstance(description, str) and description in procrastinate_list:
                procrastinate_list.discard(description)
                procrastinate_updated = True

        deleted_count = original_count - len(tasks)
        total_deleted_count += deleted_count

        if deleted_count == 1:
            successful_deletions.append(_t("Task '{task_description}'").format(task_description=task_description))
        else:
            successful_deletions.append(
                _t("{deleted_count} tasks with description '{task_description}'").format(
                    deleted_count=deleted_count, task_description=task_description
                )
            )

    # Print results
    for error in all_errors:
        print(error)

    if successful_deletions:
        try:
            save_tasks(tasks)
            if procrastinate_updated:
                save_procrastinate_list(procrastinate_list)
            if len(successful_deletions) == 1:
                print(_t("✅ {deletion} deleted successfully!").format(deletion=successful_deletions[0]))
            else:
                print(
                    _t("✅ {count} sets of tasks deleted successfully:").format(count=len(successful_deletions))
                )
                for deletion in successful_deletions:
                    print(f"   - {deletion}")
            return 0 if not all_errors else 1
        except Exception as e:
            print(_t("❌ Error saving tasks: {e}").format(e=e))
            return 1
    else:
        return 1


# =============================================================================
# SHOW TASKS COMMAND
# =============================================================================


def _format_procrastination_suffix(age_days: int | None) -> str:
    """Format procrastination age for the task list."""
    if age_days is None:
        return ""
    if age_days == 0:
        return _t(" (deferred today)")
    if age_days == 1:
        return _t(" (1 day overdue)")
    return _t(" ({age_days} days overdue)").format(age_days=age_days)


def _format_postpone_suffix(days_left: int) -> str:
    """Format postponement remaining days for the task list."""
    if days_left <= 0:
        return ""
    if days_left == 1:
        return _t(" (coming tomorrow)")
    return _t(" (coming in {days_left} days)").format(days_left=days_left)


def _sort_tasks_by_section_and_priority(
    tasks: list[dict], today: Any, procrastinate_list: set[str]
) -> list[dict]:
    """
    Sort tasks into three sections:
    1. Procrastinated tasks
    2. Current tasks
    3. Incoming (future postponed) tasks
    Within each section, tasks are ordered by priority (highest first).
    """
    def get_days_left(task) -> int:
        alarm_from = task.get("alarm_from")
        if alarm_from:
            try:
                alarm_from_date = datetime.strptime(alarm_from, "%Y-%m-%d").date()
                return (alarm_from_date - today).days
            except Exception:
                pass
        return 0

    def task_sort_key(task):
        days_left = get_days_left(task)
        is_postponed_future = days_left > 0
        is_procrastinated = (not is_postponed_future) and (task["description"] in procrastinate_list)

        if is_procrastinated:
            section = 0
        elif not is_postponed_future:
            section = 1
        else:
            section = 2

        return (section, -task["priority"])

    return sorted(tasks, key=task_sort_key)


def show_tasks(args) -> int:
    """
    Handle the 'ls' command - display all tasks in a formatted table.

    Shows tasks sorted by priority (highest first) with:
    - ID number for reference
    - Visual priority bar
    - Task description

    Args:
        args: Namespace (unused, for CLI compatibility)

    Returns:
        0 always (display operation)

    Example output:
        ╭──────────────────────────────────────╮
        │          Current Task List           │
        ├────┬──────────────────┬──────────────┤
        │ ID │ Priority         │ Description  │
        ├────┼──────────────────┼──────────────┤
        │  1 │ 🔴 ████████░░ (8) │ Study math   │
        │  2 │ 🟡 █████░░░░░ (5) │ Clean room   │
        ╰────┴──────────────────┴──────────────╯
    """
    tasks = load_tasks()
    procrastinate_records = load_procrastinate_records()
    procrastinate_list = set(procrastinate_records)
    today = datetime.now().date()

    console = Console()

    if not tasks:
        console.print("[bold yellow]" + _t("📋 No tasks found") + "[/bold yellow]")
        return 0

    # Sort tasks into three sections (procrastinated -> current -> incoming)
    # ordered by priority descending in each section
    sorted_tasks = _sort_tasks_by_section_and_priority(tasks, today, procrastinate_list)

    # Create table
    table = Table(
        title="[bold]" + _t("Current Task List") + "[/bold]",
        box=box.ROUNDED,
        header_style="bold cyan",
        expand=True,
    )

    table.add_column(_t("ID"), justify="right", style="dim", width=4)
    table.add_column(_t("Priority"), justify="left", width=18)
    table.add_column(_t("Description"), justify="left")

    for i, task in enumerate(sorted_tasks, 1):
        description = task["description"]
        priority = task["priority"]
        alarm_from = task.get("alarm_from")

        postpone_suffix = ""
        is_postponed_future = False
        if alarm_from:
            try:
                alarm_from_date = datetime.strptime(alarm_from, "%Y-%m-%d").date()
                days_left = (alarm_from_date - today).days
                if days_left > 0:
                    postpone_suffix = _format_postpone_suffix(days_left)
                    is_postponed_future = True
            except Exception:
                pass

        # Color based on priority level
        if priority >= 8:
            color = "red"
        elif priority >= 5:
            color = "yellow"
        else:
            color = "blue"

        # Visual priority bar (max 10 blocks for layout)
        filled = "█" * min(priority, 10)
        empty = "░" * (10 - min(priority, 10))

        prio_visual = f"[{color}]{filled}[dim]{empty}[/dim] ({priority})[/{color}]"
        if is_postponed_future:
            description_text = Text(
                f"💤 {description}{postpone_suffix}",
                style="italic dim",
            )
        elif description in procrastinate_list:
            age_days = get_procrastinate_age_days(
                procrastinate_records.get(description, {}).get("since"),
                today=today,
            )
            description_text = Text(
                f"⏳ {description}{_format_procrastination_suffix(age_days)}",
                style="italic dim",
            )
        else:
            description_text = Text(description)

        table.add_row(str(i), prio_visual, description_text)

    console.print(table)
    console.print("[dim]" + _t("Total tasks: {count}").format(count=len(tasks)) + "[/dim]", justify="right")

    return 0
