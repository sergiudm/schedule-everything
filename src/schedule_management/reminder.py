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
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from schedule_management.reminder_macos import (
    ScheduleConfig,
    ScheduleVisualizer,
    WeeklySchedule,
)
from schedule_management.utils import get_week_parity, parse_time

# ANSI color codes
COLORS = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "CYAN": "\033[96m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m",
    "RESET": "\033[0m",
}

CONFIG_DIR = os.getenv("REMINDER_CONFIG_DIR")
SETTINGS_PATH = f"{CONFIG_DIR}/settings.toml"
ODD_PATH = f"{CONFIG_DIR}/odd_weeks.toml"
EVEN_PATH = f"{CONFIG_DIR}/even_weeks.toml"
TASKS_PATH = os.getenv("REMINDER_TASKS_PATH")
LOG_PATH = os.getenv("REMINDER_LOG_PATH")


def get_config_paths(config_dir: str = "config") -> dict[str, Path]:
    """Get the paths to configuration files."""
    base_dir = Path(config_dir)
    if not base_dir.is_dir():
        raise ValueError(f"Directory not found: {base_dir}")
    return {
        "settings": base_dir / "settings.toml",
        "odd_weeks": base_dir / "odd_weeks.toml",
        "even_weeks": base_dir / "even_weeks.toml",
    }


def load_tasks() -> list[dict[str, Any]]:
    """Load tasks from the JSON file."""
    if not os.path.exists(TASKS_PATH):
        return []

    try:
        with open(TASKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_tasks(tasks: list[dict[str, Any]]) -> None:
    """Save tasks to the JSON file."""
    # Ensure config directory exists
    os.makedirs(CONFIG_DIR, exist_ok=True)

    with open(TASKS_PATH, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)


def load_task_log() -> list[dict[str, Any]]:
    """Load task log from the JSON file."""
    if not LOG_PATH or not os.path.exists(LOG_PATH):
        return []

    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_task_log(log_entries: list[dict[str, Any]]) -> None:
    """Save task log to the JSON file."""
    if not LOG_PATH:
        return

    # Ensure config directory exists
    os.makedirs(CONFIG_DIR, exist_ok=True)

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log_entries, f, indent=2, ensure_ascii=False)


def log_task_action(
    action: str, task: dict[str, Any], metadata: dict[str, Any] | None = None
) -> None:
    """Log a task action (added/updated/deleted) with timestamp."""
    if not LOG_PATH:
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
    """Handle the 'ls' command - show all tasks in reminder."""
    # Load existing tasks
    tasks = load_tasks()

    if not tasks:
        print("📋 No tasks found")
        return 0

    # Sort tasks by priority (descending order - higher priority first)
    sorted_tasks = sorted(tasks, key=lambda x: x["priority"], reverse=True)

    # Determine max description length for formatting
    max_desc_len = (
        max(len(task["description"]) for task in sorted_tasks) if sorted_tasks else 20
    )
    max_desc_len = min(max_desc_len, 50)  # Limit max width

    for i, task in enumerate(sorted_tasks, 1):
        description = task["description"]
        priority = task["priority"]

        # Create visual priority indicator
        priority_bar = (
            "█" * priority + "░" * (10 - min(priority, 10))
            if priority <= 10
            else "█" * 10
        )
        priority_display = f"{priority_bar} ({priority})"

        # Color coding based on priority (using ANSI escape codes)
        if priority >= 8:
            color = COLORS["RED"]  # Red for high priority
            icon = "🔴"
        elif priority >= 5:
            color = COLORS["YELLOW"]  # Yellow for medium priority
            icon = "🟡"
        else:
            color = COLORS["BLUE"]  # Blue for low priority
            icon = "🔵"

        reset_color = COLORS["RESET"]

        print(f"{icon} {color}{i:2d}. {description:<{max_desc_len}} {reset_color}")
        print(f"     Priority: {priority_display}")
        print("     " + "-" * (max_desc_len + 20))
        print()

    return 0


def update_command(args):
    """Handle the 'update' command - reload configuration and restart service."""
    print("🔄 Updating reminder configuration...")

    config_paths = get_config_paths(CONFIG_DIR)

    # Validate files exist
    missing_files = [str(p) for p in config_paths.values() if not p.exists()]
    if missing_files:
        print("❌ Error: Missing configuration files:")
        for fp in missing_files:
            print(f"   - {fp}")
        return 1

    # Validate TOML structure using new classes
    try:
        print("📋 Validating configuration files...")
        config = ScheduleConfig(SETTINGS_PATH)
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
    plist_path = "$HOME/Library/LaunchAgents/com.health.habits.reminder.plist"
    try:
        subprocess.run(
            ["launchctl", "unload", plist_path], capture_output=True, text=True
        )
        time.sleep(2)
        result = subprocess.run(
            ["launchctl", "load", plist_path], capture_output=True, text=True
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
                    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
                else:
                    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")

                pdf_path = os.path.join(desktop_path, "schedule_visualization.pdf")
                subprocess.run(
                    ["open", pdf_path],
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
        "$HOME/Library/LaunchAgents/com.sergiudm.schedule.management.reminder.plist"
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


def status_command(args: argparse.Namespace):
    """Handle the 'status' command - show current status and next events."""

    try:
        schedule, parity, is_skipped = get_today_schedule_for_status()

        # Display week information
        parity_icon = "📅 Odd Week" if parity == "odd" else "📅 Even Week"
        print(f"📊 {parity_icon}")

        if is_skipped:
            print("⏭️  Today is a skipped day - no reminders scheduled")
            print("\n" + "=" * 50)
            return 0

        current, next_ev, time_until = get_current_and_next_events(schedule)

        # Display current and next events in a structured way
        print("\n" + "🎯" + "=" * 23 + " EVENTS " + "=" * 23 + "🎯")

        if current:
            print(f"🔔 Current event: {current}")
        else:
            print("🔕 No current event")

        if next_ev:
            if time_until:
                print(f"⏰ Next event: {next_ev} (in {time_until})")
            else:
                print(f"⏰ Next event: {next_ev}")
        else:
            print("📭 No more events scheduled for today")

        if args.verbose:
            print("\n" + "📋" + "=" * 21 + " SCHEDULE " + "=" * 21 + "📋")
            print(f"Total events for today: {len(schedule)}")
            print()

            if schedule:
                # Group events by time of day
                morning_events = []
                afternoon_events = []
                evening_events = []

                for time_str in sorted(schedule.keys()):
                    event = schedule[time_str]
                    if isinstance(event, str):
                        name = event
                    elif isinstance(event, dict) and "block" in event:
                        name = event.get("title", event["block"])
                    else:
                        name = str(event)

                    # Parse time to categorize events
                    try:
                        hour = int(time_str.split(":")[0])
                        event_data = (time_str, name)

                        if 5 <= hour < 12:
                            morning_events.append(event_data)
                        elif 12 <= hour < 18:
                            afternoon_events.append(event_data)
                        else:
                            evening_events.append(event_data)
                    except ValueError:
                        # If time parsing fails, add to general list
                        evening_events.append((time_str, name))

                # Define time period names and icons
                time_periods = [
                    ("🌅 MORNING (5:00-11:59)", morning_events),
                    ("☀️  AFTERNOON (12:00-17:59)", afternoon_events),
                    ("🌆 EVENING (18:00-23:59)", evening_events),
                ]

                # Print events by time period
                for period_name, events in time_periods:
                    if events:
                        print(f"\n{period_name}")
                        print("-" * len(period_name))
                        for time_str, name in events:
                            # Determine event type icon
                            event_icon = (
                                "⏱️"
                                if "pomodoro" in name.lower() or "break" in name.lower()
                                else "📅"
                            )
                            print(f"   {event_icon} {time_str}: {name}")
                        print()

        return 0

    except Exception as e:
        print(f"❌ Error checking status: {e}")
        return 1


def main():
    """Main entry point for the CLI tool."""
    # Get config directory path for display
    config_dir_path = os.path.abspath(CONFIG_DIR)

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
