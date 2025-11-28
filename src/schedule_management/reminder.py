"""
Reminder CLI Tool - Command line interface for the schedule management system.

This tool provides commands to:
- Update configuration and restart the reminder service
- View schedule visualizations
- Check current status and next events
"""

import argparse
import json
import os
import subprocess
import sys
import time
import tomllib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from rich import box
    from rich.align import Align
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError:
    print("Please install the 'rich' library: pip install rich")
    sys.exit(1)

from schedule_management.reminder_macos import (
    ScheduleConfig,
    WeeklySchedule,
)

from schedule_management.utils import get_week_parity, parse_time, ScheduleVisualizer
from schedule_management.report import ReportGenerator
from schedule_management import (
    COLORS,
    CONFIG_DIR,
    SETTINGS_PATH,
    ODD_PATH,
    EVEN_PATH,
    DDL_PATH,
    HABIT_PATH,
    TASKS_PATH,
    TASK_LOG_PATH,
    RECORD_PATH,
)

def load_tasks() -> list[dict[str, Any]]:
    """Load tasks from the JSON file."""
    try:
        with open(TASKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print("Error loading tasks file, starting with an empty task list.")
        return []


def save_tasks(tasks: list[dict[str, Any]]) -> None:
    """Save tasks to the JSON file."""
    tasks_path = Path(TASKS_PATH)

    # Ensure destination directory exists
    tasks_path.parent.mkdir(parents=True, exist_ok=True)

    with open(tasks_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)


def load_task_log() -> list[dict[str, Any]]:
    """Load task log from the JSON file."""

    try:
        with open(TASK_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_task_log(log_entries: list[dict[str, Any]]) -> None:
    """Save task log to the JSON file."""
    log_path = Path(TASK_LOG_PATH)
    if not log_path:
        return

    # Ensure directory exists for the log file
    log_dir = log_path.parent
    log_dir.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entries, f, indent=2, ensure_ascii=False)


def load_deadlines() -> list[dict[str, Any]]:
    """Load deadlines from the JSON file."""
    try:
        with open(DDL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print("Error loading deadlines file, starting with an empty deadline list.")
        return []


def save_deadlines(deadlines: list[dict[str, Any]]) -> None:
    """Save deadlines to the JSON file."""
    ddl_path = Path(DDL_PATH)

    # Ensure destination directory exists
    ddl_path.parent.mkdir(parents=True, exist_ok=True)

    with open(ddl_path, "w", encoding="utf-8") as f:
        json.dump(deadlines, f, indent=2, ensure_ascii=False)


def load_habits() -> dict[str, str]:
    """Load habits from the TOML file."""
    try:
        with open(HABIT_PATH, "rb") as f:
            data = tomllib.load(f)
            # Check if data has a 'habits' section (nested structure)
            if "habits" in data:
                habits_data = data["habits"]
            else:
                habits_data = data

            # Convert to string keys for consistency
            habits = {}
            for key, value in habits_data.items():
                # Support both formats: "habit name" = 1 or 1 = "habit name"
                if isinstance(value, int):
                    habits[str(value)] = key
                else:
                    habits[str(key)] = str(value)
            return habits
    except Exception as e:
        print(f"Error loading habits file: {e}")
        return {}


def load_habit_records() -> list[dict[str, Any]]:
    """Load habit tracking records from the JSON file."""
    record_path = Path(RECORD_PATH)
    if not record_path.exists():
        return []

    try:
        with open(record_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_habit_records(records: list[dict[str, Any]]) -> None:
    """Save habit tracking records to the JSON file."""
    record_path = Path(RECORD_PATH)

    # Ensure destination directory exists
    record_path.parent.mkdir(parents=True, exist_ok=True)

    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def log_task_action(
    action: str, task: dict[str, Any], metadata: dict[str, Any] | None = None
) -> None:
    """Log a task action (added/updated/deleted) with timestamp."""
    log_path = Path(TASK_LOG_PATH)
    if not log_path:
        return

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "task": task.copy(),
    }

    if metadata:
        log_entry["metadata"] = metadata.copy()

    log_entries = load_task_log()
    log_entries.append(log_entry)
    save_task_log(log_entries)


def add_deadline(args):
    """Handle the 'ddl add' command - add a new deadline event."""
    event_name = args.event
    date_str = args.date

    # Parse the date - support both "M.D" and "MM.DD" formats
    try:
        # Split by dot
        parts = date_str.split(".")
        if len(parts) != 2:
            print("❌ Error: Date must be in format M.D or MM.DD (e.g., 7.4 or 07.04)")
            return 1

        month = int(parts[0])
        day = int(parts[1])

        # Validate month and day
        if not (1 <= month <= 12):
            print("❌ Error: Month must be between 1 and 12")
            return 1
        if not (1 <= day <= 31):
            print("❌ Error: Day must be between 1 and 31")
            return 1

        # Determine the year (current year or next year if the date has passed)
        current_date = datetime.now()
        current_year = current_date.year
        deadline_date = datetime(current_year, month, day)

        # If the deadline has already passed this year, use next year
        if deadline_date.date() < current_date.date():
            deadline_date = datetime(current_year + 1, month, day)

        # Format as ISO date string
        deadline_str = deadline_date.strftime("%Y-%m-%d")

    except ValueError as e:
        print(f"❌ Error: Invalid date format - {e}")
        return 1

    # Load existing deadlines
    deadlines = load_deadlines()

    # Check if event already exists
    existing_index = None
    for i, ddl in enumerate(deadlines):
        if ddl["event"] == event_name:
            existing_index = i
            break

    # Create new deadline entry
    new_deadline = {
        "event": event_name,
        "deadline": deadline_str,
        "added": datetime.now(timezone.utc).isoformat(),
    }

    # Replace existing or add new
    if existing_index is not None:
        old_date = deadlines[existing_index]["deadline"]
        deadlines[existing_index] = new_deadline
        action_msg = (
            f"✅ Deadline for '{event_name}' updated from {old_date} to {deadline_str}"
        )
    else:
        deadlines.append(new_deadline)
        action_msg = (
            f"✅ Deadline '{event_name}' added successfully for {deadline_str}!"
        )

    # Save deadlines
    try:
        save_deadlines(deadlines)
        print(action_msg)
        return 0
    except Exception as e:
        print(f"❌ Error saving deadline: {e}")
        return 1


def show_deadlines(args):
    """Handle the 'ddl' command - show all deadlines using Rich."""
    # Load existing deadlines
    deadlines = load_deadlines()

    console = Console()

    if not deadlines:
        console.print("[bold yellow]📅 No deadlines found[/bold yellow]")
        return 0

    # Sort deadlines by date (earliest first)
    sorted_deadlines = sorted(deadlines, key=lambda x: x["deadline"])

    # Create the table
    table = Table(
        title="[bold]Upcoming Deadlines[/bold]",
        box=box.ROUNDED,
        header_style="bold cyan",
        expand=True,
    )

    table.add_column("Event", justify="left", style="bold")
    table.add_column("Deadline", justify="left", width=15)
    table.add_column("Days Left", justify="right", width=12)
    table.add_column("Status", justify="center", width=10)

    current_date = datetime.now().date()

    for ddl in sorted_deadlines:
        event_name = ddl["event"]
        deadline_str = ddl["deadline"]

        # Parse deadline date
        deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()

        # Calculate days left
        days_left = (deadline_date - current_date).days

        # Initialize row style
        row_style = None

        # Determine color and status based on days left
        if days_left < 0:
            # Overdue logic: Dimmed row, hidden days count
            color = "dim"
            status = "⚠️ OVERDUE"
            days_text = ""
            row_style = "dim"
        elif days_left == 0:
            color = "red"
            status = "🔴 TODAY"
            days_text = f"[{color}]TODAY[/{color}]"
        elif days_left <= 3:
            color = "red"
            status = "🔴 URGENT"
            days_text = f"[{color}]{days_left} days[/{color}]"
        elif days_left <= 7:
            color = "yellow"
            status = "🟡 SOON"
            days_text = f"[{color}]{days_left} days[/{color}]"
        else:
            color = "green"
            status = "🟢 OK"
            days_text = f"[{color}]{days_left} days[/{color}]"

        # Format deadline date for display
        deadline_display = deadline_date.strftime("%b %d, %Y")

        # Add row with optional style override
        table.add_row(event_name, deadline_display, days_text, status, style=row_style)

    console.print(table)

    # Optional: Summary footer
    console.print(f"[dim]Total deadlines: {len(deadlines)}[/dim]", justify="right")

    return 0


def delete_deadline(args):
    """Handle the 'ddl rm' command - delete one or more deadlines."""
    event_identifiers = args.events

    # Load existing deadlines
    deadlines = load_deadlines()

    if not deadlines:
        print("⚠️  No deadlines found to delete")
        return 1

    total_deleted_count = 0
    all_errors = []
    successful_deletions = []

    for event_identifier in event_identifiers:
        event_name = event_identifier
        original_count = len(deadlines)
        deleted_deadlines = [ddl for ddl in deadlines if ddl["event"] == event_name]
        deadlines = [ddl for ddl in deadlines if ddl["event"] != event_name]

        if len(deadlines) == original_count:
            error_msg = f"❌ Deadline '{event_name}' not found"
            all_errors.append(error_msg)
            continue

        deleted_count = original_count - len(deadlines)
        total_deleted_count += deleted_count

        if deleted_count == 1:
            successful_deletions.append(f"Deadline '{event_name}'")
        else:
            successful_deletions.append(
                f"{deleted_count} deadlines with name '{event_name}'"
            )

    # Print results
    for error in all_errors:
        print(error)

    if successful_deletions:
        # Save updated deadlines
        try:
            save_deadlines(deadlines)
            if len(successful_deletions) == 1:
                print(f"✅ {successful_deletions[0]} deleted successfully!")
            else:
                print(
                    f"✅ {len(successful_deletions)} sets of deadlines deleted successfully:"
                )
                for deletion in successful_deletions:
                    print(f"   - {deletion}")
            return 0 if not all_errors else 1
        except Exception as e:
            print(f"❌ Error saving deadlines: {e}")
            return 1
    else:
        return 1


def track_habits(args):
    """Handle the 'track' command - record which habits were completed today."""
    habit_ids = args.habit_ids

    # Load habits configuration
    habits = load_habits()

    if not habits:
        print("❌ Error: No habits configured. Please create config/habits.toml")
        return 1

    # Validate habit IDs
    invalid_ids = []
    valid_habits = []

    for habit_id in habit_ids:
        habit_id_str = str(habit_id)
        if habit_id_str in habits:
            valid_habits.append(habit_id_str)
        else:
            invalid_ids.append(habit_id)

    if invalid_ids:
        print(f"⚠️  Warning: Invalid habit IDs: {', '.join(map(str, invalid_ids))}")
        print(f"Available habits: {', '.join(sorted(habits.keys()))}")
        if not valid_habits:
            return 1

    # Get today's date
    today = date.today().isoformat()

    # Load existing records
    records = load_habit_records()

    # Check if there's already a record for today
    existing_record_index = None
    for i, record in enumerate(records):
        if record.get("date") == today:
            existing_record_index = i
            break

    # Create record for today
    completed_habits = {habit_id: habits[habit_id] for habit_id in valid_habits}

    new_record = {
        "date": today,
        "completed": completed_habits,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Update or add record
    if existing_record_index is not None:
        old_completed = records[existing_record_index].get("completed", {})
        records[existing_record_index] = new_record
        print(f"✅ Updated habit record for {today}")
        print(f"Previously completed: {len(old_completed)} habits")
    else:
        records.append(new_record)
        print(f"✅ Recorded habit tracking for {today}")

    print(f"Completed habits today: {len(completed_habits)}")
    for habit_id in sorted(valid_habits):
        print(f"  [{habit_id}] {habits[habit_id]}")

    # Save records
    try:
        save_habit_records(records)
        return 0
    except Exception as e:
        print(f"❌ Error saving habit records: {e}")
        return 1


def add_task(args):
    """Handle the 'add' command - add a new task to reminder."""
    task_description = args.task
    priority = args.priority

    # Validate priority is positive
    if priority <= 0:
        print("❌ Error: Priority must be a positive integer")
        return 1

    # Load existing tasks
    tasks = load_tasks()

    # Check if task with same description already exists
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

    # Replace existing task or add new one
    if existing_task_index is not None:
        old_priority = tasks[existing_task_index]["priority"]
        tasks[existing_task_index] = new_task
        action_msg = f"✅ Task '{task_description}' updated! Priority changed from {old_priority} to {priority}"

        # Log task update
        try:
            log_task_action("updated", new_task, {"old_priority": old_priority})
        except Exception as e:
            print(f"⚠️  Warning: Could not log task update: {e}")
    else:
        tasks.append(new_task)
        action_msg = (
            f"✅ Task '{task_description}' added successfully with priority {priority}!"
        )

        # Log task addition
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


def delete_task(args):
    """Handle the 'rm' command - delete one or more tasks from reminder."""
    task_identifiers = args.tasks

    # Load existing tasks
    tasks = load_tasks()

    if not tasks:
        print("⚠️  No tasks found to delete")
        return 1

    # Sort tasks by priority (descending order) to match show_tasks display
    sorted_tasks = sorted(tasks, key=lambda x: x["priority"], reverse=True)

    total_deleted_count = 0
    all_errors = []
    successful_deletions = []

    for task_identifier in task_identifiers:
        # Try to parse as integer ID first
        try:
            task_id = int(task_identifier)
            # Check if ID is valid
            if task_id < 1 or task_id > len(sorted_tasks):
                error_msg = f"❌ Invalid task ID: {task_id}. Please use a number between 1 and {len(sorted_tasks)}"
                all_errors.append(error_msg)
                continue

            # Get task description by ID
            task_to_delete = sorted_tasks[task_id - 1]
            task_description = task_to_delete["description"]

            # Find and remove the task by description from original tasks list
            original_count = len(tasks)
            deleted_tasks = [
                task for task in tasks if task["description"] == task_description
            ]
            tasks = [task for task in tasks if task["description"] != task_description]

        except ValueError:
            # Treat as string description
            task_description = task_identifier
            original_count = len(tasks)
            deleted_tasks = [
                task for task in tasks if task["description"] == task_description
            ]
            tasks = [task for task in tasks if task["description"] != task_description]

        if len(tasks) == original_count:
            error_msg = f"❌ Task '{task_description}' not found"
            all_errors.append(error_msg)
            continue

        # Log task deletions
        try:
            for deleted_task in deleted_tasks:
                log_task_action("deleted", deleted_task)
        except Exception as e:
            print(f"⚠️  Warning: Could not log task deletion: {e}")

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
        # Save updated tasks
        try:
            save_tasks(tasks)
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


def show_tasks(args):
    """Handle the 'ls' command - show all tasks in reminder using Rich."""
    # Load existing tasks
    tasks = load_tasks()

    console = Console()

    if not tasks:
        console.print("[bold yellow]📋 No tasks found[/bold yellow]")
        return 0

    # Sort tasks by priority (descending order)
    sorted_tasks = sorted(tasks, key=lambda x: x["priority"], reverse=True)

    # Create the table
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

        # Determine color based on priority
        if priority >= 8:
            color = "red"
            icon = "🔴"
        elif priority >= 5:
            color = "yellow"
            icon = "🟡"
        else:
            color = "blue"
            icon = "🔵"

        # Create visual block bar
        # Capping visual bar at 10 blocks max for layout consistency
        filled = "█" * min(priority, 10)
        empty = "░" * (10 - min(priority, 10))

        # Combine bar and number
        prio_visual = f"[{color}]{filled}[dim]{empty}[/dim] ({priority})[/{color}]"

        # Add row
        table.add_row(str(i), prio_visual, f"{description}")

    console.print(table)

    # Optional: Summary footer
    console.print(f"[dim]Total tasks: {len(tasks)}[/dim]", justify="right")

    return 0


def update_command(args=None):
    """Handle the 'update' command - reload configuration and restart service."""
    print("🔄 Updating reminder configuration...")

    # Validate files exist
    missing_files = [
        Path(p) for p in [SETTINGS_PATH, ODD_PATH, EVEN_PATH] if not Path(p).exists()
    ]
    if missing_files:
        print("❌ Error: Missing configuration files:")
        for fp in missing_files:
            print(f"   - {fp}")
        return 1

    # Validate TOML structure using new classes
    try:
        print("📋 Validating configuration files...")
        config = ScheduleConfig(SETTINGS_PATH)
        # Build odd and even paths from config_dir
        weekly = WeeklySchedule(ODD_PATH, EVEN_PATH)
        # Trigger loading to validate
        _ = config.settings
        _ = weekly.odd_data
        _ = weekly.even_data
        print("✅ Configuration files are valid")
    except Exception as e:
        print(f"❌ Error: Invalid configuration - {e}")
        return 1

    # Restart LaunchAgent (macOS-specific)
    print("🔄 Restarting reminder service...")
    plist_path = (
        Path.home() / "Library" / "LaunchAgents" / "com.health.habits.reminder.plist"
    )
    try:
        subprocess.run(
            ["launchctl", "unload", str(plist_path)], capture_output=True, text=True
        )
        time.sleep(2)
        result = subprocess.run(
            ["launchctl", "load", str(plist_path)], capture_output=True, text=True
        )

        if result.returncode == 0:
            print("✅ Reminder service restarted successfully")
        else:
            print(f"⚠️  Warning: Could not restart LaunchAgent: {result.stderr.strip()}")
            print("   You may need to restart manually")
    except Exception as e:
        print(f"⚠️  Warning: Could not restart service automatically: {e}")
        print("   Configuration updated, but manual restart may be needed")

    print("✅ Update completed successfully!")
    return 0


def view_command(args):
    """Handle the 'view' command - generate and show schedule visualizations."""
    print("📊 Generating schedule visualizations...")

    try:
        config = ScheduleConfig(SETTINGS_PATH)
        weekly = WeeklySchedule(ODD_PATH, EVEN_PATH)
        visualizer = ScheduleVisualizer(config, weekly.odd_data, weekly.even_data)
        visualizer.visualize()

        print("\n📁 Visualization file generated:")
        # Open on macOS
        if sys.platform == "darwin":
            print("\n🖼️  Opening visualization...")
            try:
                import platform

                if platform.system() == "Windows":
                    desktop_path = Path.home() / "Desktop"
                else:
                    desktop_path = Path.home() / "Desktop"

                pdf_path = desktop_path / "schedule_visualization.pdf"
                subprocess.run(
                    ["open", str(pdf_path)],
                    check=False,
                )
            except Exception as e:
                print(f"⚠️  Could not open file: {e}")

        return 0

    except Exception as e:
        print(f"❌ Error generating visualizations: {e}")
        return 1


def get_today_schedule_for_status() -> tuple[dict[str, Any], str, bool]:
    """Helper to get today's schedule with metadata for status command."""
    config = ScheduleConfig(SETTINGS_PATH)
    weekly = WeeklySchedule(ODD_PATH, EVEN_PATH)
    is_skipped = config.should_skip_today()
    parity = get_week_parity()
    schedule = {} if is_skipped else weekly.get_today_schedule(config)

    return schedule, parity, is_skipped


def get_current_and_next_events(
    schedule: dict[str, Any],
) -> tuple[str | None, str | None, str | None]:
    """Get current and next scheduled events from today's schedule."""
    if not schedule:
        return None, None, None

    now = datetime.now()
    current_time = now.time()

    # Parse and sort scheduled times
    scheduled_times = []
    for time_str in schedule.keys():
        try:
            t = parse_time(time_str)
            scheduled_times.append((time_str, t))
        except ValueError:
            continue

    scheduled_times.sort(key=lambda x: x[1])

    current_event = None
    next_event = None
    time_to_next = None

    for time_str, scheduled_time in scheduled_times:
        event = schedule[time_str]
        if isinstance(event, str):
            event_name = event
        elif isinstance(event, dict) and "block" in event:
            event_name = event.get("title", event["block"])
        else:
            event_name = str(event)

        if scheduled_time <= current_time:
            current_event = f"{event_name} at {time_str}"
        else:
            next_event = f"{event_name} at {time_str}"
            # Calculate time difference
            today = date.today()
            event_dt = datetime.combine(today, scheduled_time)
            now_dt = datetime.combine(today, current_time)
            diff = event_dt - now_dt
            total_minutes = int(diff.total_seconds() // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            if hours > 0:
                time_to_next = f"{hours}h {minutes}m"
            else:
                time_to_next = f"{minutes}m"
            break

    return current_event, next_event, time_to_next


def stop_command(args):
    """Handle the 'stop' command - unload the LaunchAgent plist to stop the service."""
    print("🛑 Stopping reminder service...")

    plist_path = (
        Path.home()
        / "Library"
        / "LaunchAgents"
        / "com.sergiudm.schedule.management.reminder.plist"
    )

    try:
        result = subprocess.run(
            ["launchctl", "unload", plist_path], capture_output=True, text=True
        )

        if result.returncode == 0:
            print("✅ Reminder service stopped successfully")
            return 0
        else:
            print(f"❌ Error stopping service: {result.stderr.strip()}")
            return 1

    except Exception as e:
        print(f"❌ Error stopping reminder service: {e}")
        return 1


def status_command(args):
    """Handle the 'status' command - show status and schedule using Rich."""
    console = Console()

    try:
        schedule, parity, is_skipped = get_today_schedule_for_status()

        # --- 1. Header Section (Parity) ---
        parity_text = f"📅 {parity.title()} Week"
        parity_style = "bold magenta" if parity == "odd" else "bold cyan"

        # Clear screen for a fresh dashboard look (optional, remove if unwanted)
        # console.clear()

        console.print(Align.center(f"[{parity_style}]{parity_text}[/{parity_style}]"))

        if is_skipped:
            console.print(
                Panel(
                    Align.center("⏭️  Today is a skipped day - enjoy your time off!"),
                    style="yellow",
                    box=box.ROUNDED,
                )
            )
            return 0

        # --- 2. Status Panel (Current & Next Event) ---
        current_event, next_ev, time_until = get_current_and_next_events(schedule)

        status_lines = []

        # Current Event formatting
        if current_event:
            # Extract just the event name if possible, assuming format "Name at Time"
            # But keep it simple for now based on your return values
            status_lines.append(f"[bold green]🔔 NOW:[/bold green]  {current_event}")
        else:
            status_lines.append("[dim]🔕 No active event[/dim]")

        status_lines.append("")  # spacer

        # Next Event formatting
        if next_ev:
            time_str = f" (in {time_until})" if time_until else ""
            status_lines.append(
                f"[bold blue]⏰ NEXT:[/bold blue] {next_ev}[yellow]{time_str}[/yellow]"
            )
        else:
            status_lines.append("[dim]📭 No upcoming events[/dim]")

        # Create the dashboard panel
        status_content = "\n".join(status_lines)
        console.print(
            Panel(
                status_content,
                title="[bold]Status[/bold]",
                expand=False,
                border_style="green" if current_event else "dim",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )

        # --- 3. Verbose Schedule Table ---
        if args.verbose and schedule:
            console.print()  # Spacer

            # Sort and categorize events
            morning_events = []
            afternoon_events = []
            evening_events = []

            sorted_times = sorted(schedule.keys())

            for time_str in sorted_times:
                event = schedule[time_str]
                name = (
                    event.get("title", event["block"])
                    if isinstance(event, dict)
                    else str(event)
                )

                try:
                    hour = int(time_str.split(":")[0])
                    item = (time_str, name)
                    if 5 <= hour < 12:
                        morning_events.append(item)
                    elif 12 <= hour < 18:
                        afternoon_events.append(item)
                    else:
                        evening_events.append(item)
                except ValueError:
                    evening_events.append((time_str, name))

            # Build the Table
            table = Table(
                box=box.SIMPLE_HEAD, show_lines=False, header_style="bold", expand=True
            )

            table.add_column(
                "Time", justify="right", style="cyan", width=8, no_wrap=True
            )
            table.add_column("Activity", justify="left")

            # Helper to add sections
            def add_period_section(title, icon, events, color):
                if events:
                    # Add a section header row
                    table.add_section()
                    table.add_row(
                        f"[{color}]{icon}[/{color}]",
                        f"[bold {color}]{title}[/bold {color}]",
                    )

                    for time_str, name in events:
                        # Highlight Pomodoros or Breaks
                        if "break" in name.lower() or "napping" in name.lower():
                            name_styled = f"[italic dim]{name}[/italic dim]"
                            icon_type = "☕"
                        elif "pomodoro" in name.lower():
                            name_styled = f"[bold red]{name}[/bold red]"
                            icon_type = "🍅"
                        elif "potato" in name.lower():
                            name_styled = f"[bold yellow]{name}[/bold yellow]"
                            icon_type = "🥔"
                        elif "go_to_bed" in name.lower():
                            name_styled = f"[bold blue]{name}[/bold blue]"
                            icon_type = "🌙"
                        elif "summary_time" in name.lower():
                            name_styled = f"[bold magenta]{name}[/bold magenta]"
                            icon_type = "📝"
                        else:
                            name_styled = f"[bold]{name}[/bold]"
                            icon_type = "•"

                        table.add_row(time_str, f"{icon_type}  {name_styled}")

            add_period_section("Morning", "🌅", morning_events, "yellow")
            add_period_section("Afternoon", "☀️ ", afternoon_events, "orange1")
            add_period_section("Evening", "🌆", evening_events, "purple")

            console.print(table)
            console.print(
                f"[dim italic]Total events: {len(schedule)}[/dim italic]",
                justify="right",
            )

        return 0

    except Exception as e:
        console.print(f"[bold red]❌ Error checking status:[/bold red] {e}")
        return 1


def report_command(args):
    """Handle the 'report' command - generate weekly or monthly reports."""
    report_type = args.type

    print(f"📊 Generating {report_type} report...")

    try:
        # Load configuration
        config = ScheduleConfig(SETTINGS_PATH)

        # Get reports path from config or default
        reports_path = config.paths.get("reports_path", "~/Desktop/reports")

        # Initialize generator
        generator = ReportGenerator(reports_path)

        # Load data
        task_log = load_task_log()
        habit_records = load_habit_records()
        habits_config = load_habits()

        if report_type == "weekly":
            generator.generate_weekly_report(task_log, habit_records, habits_config)
        elif report_type == "monthly":
            generator.generate_monthly_report(task_log, habit_records, habits_config)

        # Open folder on macOS
        if sys.platform == "darwin":
            try:
                subprocess.run(
                    ["open", str(Path(os.path.expanduser(reports_path)))], check=False
                )
            except Exception:
                pass

        return 0

    except Exception as e:
        print(f"❌ Error generating report: {e}")
        return 1


def main():
    """Main entry point for the CLI tool."""
    # Get config directory path for display
    config_dir_path = Path(CONFIG_DIR).resolve()

    # Colored help text
    colored_description = f"{COLORS['BOLD']}{COLORS['CYAN']}Reminder CLI{COLORS['RESET']} - {COLORS['GREEN']}Manage your schedule management system{COLORS['RESET']}"

    colored_epilog = f"""
{COLORS["UNDERLINE"]}{COLORS["YELLOW"]}Configuration directory:{COLORS["RESET"]} {COLORS["BLUE"]}{config_dir_path}{COLORS["RESET"]}
        """

    parser = argparse.ArgumentParser(
        description=colored_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=colored_epilog,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add command
    add_parser = subparsers.add_parser(
        "add", help="Add a new task with description and priority level (1-10)"
    )
    add_parser.add_argument(
        "task", help="Description of the task (e.g., 'biology homework')"
    )
    add_parser.add_argument(
        "priority",
        type=int,
        help="Priority level (1-10, higher = more important)",
    )
    add_parser.set_defaults(func=add_task)

    # Delete command
    delete_parser = subparsers.add_parser(
        "rm", help="Delete one or more tasks by description or ID number"
    )
    delete_parser.add_argument(
        "tasks",
        nargs="+",
        help="One or more descriptions of tasks to delete or ID numbers (from 'reminder ls')",
    )
    delete_parser.set_defaults(func=delete_task)

    # Show command
    show_parser = subparsers.add_parser(
        "ls", help="Show all tasks sorted by importance"
    )
    show_parser.set_defaults(func=show_tasks)

    # Deadline command
    ddl_parser = subparsers.add_parser(
        "ddl", help="Manage deadlines (use 'ddl add' or just 'ddl' to list)"
    )
    ddl_subparsers = ddl_parser.add_subparsers(dest="ddl_command")

    # ddl add subcommand
    ddl_add_parser = ddl_subparsers.add_parser("add", help="Add a new deadline event")
    ddl_add_parser.add_argument("event", help="Name of the event (e.g., 'homework2')")
    ddl_add_parser.add_argument(
        "date",
        help="Deadline date in M.D or MM.DD format (e.g., '7.4' for July 4th)",
    )
    ddl_add_parser.set_defaults(func=add_deadline)

    # ddl rm subcommand
    ddl_rm_parser = ddl_subparsers.add_parser(
        "rm", help="Delete one or more deadline events"
    )
    ddl_rm_parser.add_argument(
        "events",
        nargs="+",
        help="One or more event names to delete (e.g., 'homework2' 'project')",
    )
    ddl_rm_parser.set_defaults(func=delete_deadline)

    # When 'ddl' is called without subcommand, show deadlines
    ddl_parser.set_defaults(func=show_deadlines)

    # Track command
    track_parser = subparsers.add_parser(
        "track", help="Track completed habits for today"
    )
    track_parser.add_argument(
        "habit_ids",
        nargs="+",
        help="One or more habit IDs to mark as completed (e.g., '1 2 3')",
    )
    track_parser.set_defaults(func=track_habits)

    update_parser = subparsers.add_parser(
        "update", help="Update configuration and restart service"
    )
    update_parser.set_defaults(func=update_command)

    view_parser = subparsers.add_parser("view", help="Generate schedule visualizations")
    view_parser.set_defaults(func=view_command)

    stop_parser = subparsers.add_parser("stop", help="Stop the reminder service")
    stop_parser.set_defaults(func=stop_command)

    status_parser = subparsers.add_parser(
        "status", help="Show current status and next events"
    )
    status_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed schedule"
    )
    status_parser.set_defaults(func=status_command)

    # Report command
    report_parser = subparsers.add_parser(
        "report", help="Generate weekly or monthly PDF reports"
    )
    report_parser.add_argument(
        "type", choices=["weekly", "monthly"], help="Type of report to generate"
    )
    report_parser.set_defaults(func=report_command)

    args = parser.parse_args()

    if not args.command:
        # Print colored help when no command is provided
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
