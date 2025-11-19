"""
Reminder CLI Tool - Command line interface for the schedule management system.

This tool provides commands to:
- Update configuration and restart the reminder service
- View schedule visualizations
- Check current status and next events
"""

import argparse
import json
from logging import config
from math import log
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.style import Style
    from rich import box
    from rich.align import Align
    from rich.layout import Layout
except ImportError:
    print("Please install the 'rich' library: pip install rich")
    sys.exit(1)

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


def get_config_dir() -> str:
    """Get config directory from settings.toml."""
    return os.getenv("REMINDER_CONFIG_DIR", "config")


def get_settings_path() -> str:
    """Get settings.toml path."""
    config_dir = get_config_dir()
    return f"{config_dir}/settings.toml"


def get_tasks_path() -> Path:
    """Get tasks JSON path from settings.toml with environment overrides."""
    config = ScheduleConfig(get_settings_path())

    def expand_path(path_value: str) -> Path:
        """Expand ~ and environment variables in the provided path."""
        return Path(os.path.expandvars(str(path_value))).expanduser()

    env_config_dir = os.getenv("REMINDER_CONFIG_DIR")
    if env_config_dir:
        base_dir = expand_path(env_config_dir)
    else:
        base_dir = expand_path(config.config_dir)

    tasks_path = expand_path(config.tasks_path)
    if tasks_path.is_absolute():
        return tasks_path

    # When tasks_path is relative, it should be relative to the config directory
    return base_dir / tasks_path


def get_log_path() -> str:
    """Get task log JSON path from settings.toml."""
    try:
        config = ScheduleConfig(get_settings_path())
        raw_path_str = os.path.expandvars(config.log_path)
        target_path = Path(raw_path_str).expanduser()
        final_path = Path(config.config_dir) / target_path
        return final_path
    except Exception as e:
        print(f"Error getting log path: {e}")
        default_path = Path.home() / ".schedule_management" / "task" / "tasks.log"
        env_path = os.getenv("REMINDER_LOG_PATH")
        return Path(env_path) if env_path else default_path


def get_config_paths() -> dict[str, Path]:
    """Get the paths to configuration files."""
    config_dir = get_config_dir()
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
    tasks_path = get_tasks_path()
    if not Path(tasks_path).exists():
        print("No tasks file found, starting with an empty task list.")
        return []

    try:
        with open(tasks_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print("Error loading tasks file, starting with an empty task list.")
        return []


def save_tasks(tasks: list[dict[str, Any]]) -> None:
    """Save tasks to the JSON file."""
    tasks_path = Path(get_tasks_path())

    # Ensure destination directory exists
    tasks_path.parent.mkdir(parents=True, exist_ok=True)

    with open(tasks_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)


def load_task_log() -> list[dict[str, Any]]:
    """Load task log from the JSON file."""
    log_path = get_log_path()
    if not log_path or not Path(log_path).exists():
        return []

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_task_log(log_entries: list[dict[str, Any]]) -> None:
    """Save task log to the JSON file."""
    log_path = get_log_path()
    if not log_path:
        return

    # Ensure directory exists for the log file
    log_dir = Path(log_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entries, f, indent=2, ensure_ascii=False)


def log_task_action(
    action: str, task: dict[str, Any], metadata: dict[str, Any] | None = None
) -> None:
    """Log a task action (added/updated/deleted) with timestamp."""
    log_path = get_log_path()
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
        table.add_row(str(i), prio_visual, f"{icon}  {description}")

    console.print(table)

    # Optional: Summary footer
    console.print(f"[dim]Total tasks: {len(tasks)}[/dim]", justify="right")

    return 0


def update_command(args):
    """Handle the 'update' command - reload configuration and restart service."""
    print("🔄 Updating reminder configuration...")

    config_dir = get_config_dir()
    config_paths = get_config_paths()

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
        settings_path = get_settings_path()
        config = ScheduleConfig(settings_path)
        # Build odd and even paths from config_dir
        odd_path = f"{config_dir}/odd_weeks.toml"
        even_path = f"{config_dir}/even_weeks.toml"
        weekly = WeeklySchedule(odd_path, even_path)
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
        config_dir = get_config_dir()
        settings_path = get_settings_path()
        config = ScheduleConfig(settings_path)
        # Build odd and even paths from config_dir
        odd_path = f"{config_dir}/odd_weeks.toml"
        even_path = f"{config_dir}/even_weeks.toml"
        weekly = WeeklySchedule(odd_path, even_path)
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
    config_dir = get_config_dir()
    settings_path = get_settings_path()
    config = ScheduleConfig(settings_path)
    # Build odd and even paths from config_dir
    odd_path = f"{config_dir}/odd_weeks.toml"
    even_path = f"{config_dir}/even_weeks.toml"
    weekly = WeeklySchedule(odd_path, even_path)

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
                        if "break" in name.lower():
                            name_styled = f"[italic dim]{name}[/italic dim]"
                            icon_type = "☕"
                        elif "pomodoro" in name.lower():
                            name_styled = name
                            icon_type = "🍅"
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


def main():
    """Main entry point for the CLI tool."""
    # Get config directory path for display
    config_dir = get_config_dir()
    config_dir_path = Path(config_dir).resolve()

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
