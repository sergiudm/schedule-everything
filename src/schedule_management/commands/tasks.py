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

try:
    from rich import box
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Please install the 'rich' library: pip install rich")
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
        args: Namespace with 'task' (description) and 'priority' (int)

    Returns:
        0 on success, 1 on error

    Example:
        $ rmd add "Complete homework" 7
        ✅ Task 'Complete homework' added successfully with priority 7!
    """
    task_description = args.task
    priority = args.priority

    # Validate priority
    if priority <= 0:
        print("❌ Error: Priority must be a positive integer")
        return 1

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

    # Update existing or add new
    if existing_task_index is not None:
        old_priority = tasks[existing_task_index]["priority"]
        tasks[existing_task_index] = new_task
        action_msg = f"✅ Task '{task_description}' updated! Priority changed from {old_priority} to {priority}"

        # Log the update
        try:
            log_task_action("updated", new_task, {"old_priority": old_priority})
        except Exception as e:
            print(f"⚠️  Warning: Could not log task update: {e}")
    else:
        tasks.append(new_task)
        action_msg = (
            f"✅ Task '{task_description}' added successfully with priority {priority}!"
        )

        # Log the addition
        try:
            log_task_action("added", new_task)
        except Exception as e:
            print(f"⚠️  Warning: Could not log task addition: {e}")

    # Save tasks
    try:
        save_tasks(tasks)
        print(action_msg)
        return 0
    except Exception as e:
        print(f"❌ Error saving task: {e}")
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
        print("⚠️  No tasks found to delete")
        return 1

    # Sort tasks by priority (descending) to match show_tasks display
    sorted_tasks = sorted(tasks, key=lambda x: x["priority"], reverse=True)

    total_deleted_count = 0
    all_errors = []
    successful_deletions = []

    for task_identifier in task_identifiers:
        # Try to parse as integer ID first
        try:
            task_id = int(task_identifier)

            # Validate ID range
            if task_id < 1 or task_id > len(sorted_tasks):
                error_msg = f"❌ Invalid task ID: {task_id}. Please use a number between 1 and {len(sorted_tasks)}"
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
            error_msg = f"❌ Task '{task_description}' not found"
            all_errors.append(error_msg)
            continue

        # Log deletions
        try:
            for deleted_task in deleted_tasks:
                log_task_action("deleted", deleted_task)
        except Exception as e:
            print(f"⚠️  Warning: Could not log task deletion: {e}")

        # Keep procrastinate list in sync with completed tasks
        for deleted_task in deleted_tasks:
            description = deleted_task.get("description")
            if isinstance(description, str) and description in procrastinate_list:
                procrastinate_list.discard(description)
                procrastinate_updated = True

        deleted_count = original_count - len(tasks)
        total_deleted_count += deleted_count

        if deleted_count == 1:
            successful_deletions.append(f"Task '{task_description}'")
        else:
            successful_deletions.append(
                f"{deleted_count} tasks with description '{task_description}'"
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
                print(f"✅ {successful_deletions[0]} deleted successfully!")
            else:
                print(
                    f"✅ {len(successful_deletions)} sets of tasks deleted successfully:"
                )
                for deletion in successful_deletions:
                    print(f"   - {deletion}")
            return 0 if not all_errors else 1
        except Exception as e:
            print(f"❌ Error saving tasks: {e}")
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
        return " (deferred today)"
    if age_days == 1:
        return " (1 day)"
    return f" ({age_days} days)"


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
        console.print("[bold yellow]📋 No tasks found[/bold yellow]")
        return 0

    # Sort by priority (highest first)
    sorted_tasks = sorted(tasks, key=lambda x: x["priority"], reverse=True)

    # Create table
    table = Table(
        title="[bold]Current Task List[/bold]",
        box=box.ROUNDED,
        header_style="bold cyan",
        expand=True,
    )

    table.add_column("ID", justify="right", style="dim", width=4)
    table.add_column("Priority", justify="left", width=18)
    table.add_column("Description", justify="left")

    for i, task in enumerate(sorted_tasks, 1):
        description = task["description"]
        priority = task["priority"]

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
        if description in procrastinate_list:
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
    console.print(f"[dim]Total tasks: {len(tasks)}[/dim]", justify="right")

    return 0
