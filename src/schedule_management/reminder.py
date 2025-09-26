"""
Reminder CLI Tool - Command line interface for the schedule management system.

This tool provides commands to:
- Update configuration and restart the reminder service
- View schedule visualizations
- Check current status and next events
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from schedule_management.reminder_macos import (
    ScheduleConfig,
    ScheduleVisualizer,
    WeeklySchedule,
)
from schedule_management.utils import get_week_parity, parse_time

CONFIG_DIR = os.getenv("REMINDER_CONFIG_DIR", "config")
SETTINGS_PATH = f"{CONFIG_DIR}/settings.toml"
ODD_PATH = f"{CONFIG_DIR}/odd_weeks.toml"
EVEN_PATH = f"{CONFIG_DIR}/even_weeks.toml"


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

        print("\n📁 Visualization files generated:")
        print("   - schedule_visualization/odd_week_schedule.png")
        print("   - schedule_visualization/even_week_schedule.png")

        # Open on macOS
        if sys.platform == "darwin":
            print("\n🖼️  Opening visualizations...")
            try:
                subprocess.run(
                    ["open", "schedule_visualization/odd_week_schedule.png"],
                    check=False,
                )
                subprocess.run(
                    ["open", "schedule_visualization/even_week_schedule.png"],
                    check=False,
                )
            except Exception as e:
                print(f"⚠️  Could not open files: {e}")

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
    current_time_str = now.strftime("%H:%M")

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


def status_command(args: argparse.Namespace):
    """Handle the 'status' command - show current status and next events."""
    print("📅 Checking reminder status...\n")

    try:
        schedule, parity, is_skipped = get_today_schedule_for_status()
        print(f"📊 Current week: {parity}")

        if is_skipped:
            print("⏭️  Today is a skipped day - no reminders scheduled")
            return 0

        current, next_ev, time_until = get_current_and_next_events(schedule)

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
            print("\n📋 Today's schedule:")
            if schedule:
                for time_str in sorted(schedule.keys()):
                    event = schedule[time_str]
                    if isinstance(event, str):
                        name = event
                    elif isinstance(event, dict) and "block" in event:
                        name = event.get("title", event["block"])
                    else:
                        name = str(event)
                    print(f"   {time_str}: {name}")

        return 0

    except Exception as e:
        print(f"❌ Error checking status: {e}")
        return 1


def main():
    """Main entry point for the CLI tool."""
    # Get config directory path for display
    config_dir_path = os.path.abspath(CONFIG_DIR)

    parser = argparse.ArgumentParser(
        description="Reminder CLI - Manage your schedule management system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Configuration directory: {config_dir_path}

Examples:
  reminder update          # Update configuration and restart service
  reminder view            # Generate schedule visualizations
  reminder status          # Show current status and next events
  reminder status -v       # Show detailed status with full schedule
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    update_parser = subparsers.add_parser(
        "update", help="Update configuration and restart service"
    )
    update_parser.set_defaults(func=update_command)

    view_parser = subparsers.add_parser("view", help="Generate schedule visualizations")
    view_parser.set_defaults(func=view_command)

    status_parser = subparsers.add_parser(
        "status", help="Show current status and next events"
    )
    status_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed schedule"
    )
    status_parser.set_defaults(func=status_command)

    args = parser.parse_args()

    if not args.command:
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
