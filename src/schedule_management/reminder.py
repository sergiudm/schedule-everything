#!/usr/bin/env python3
"""
Reminder CLI Tool - Command line interface for the schedule management system.

This tool provides commands to:
- Update configuration and restart the reminder service
- View schedule visualizations
- Check current status and next events
"""

import argparse
import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Import functions from the existing reminder_macos module
from schedule_management.reminder_macos import (
    load_settings,
    load_odd_week_schedule,
    load_even_week_schedule,
    get_today_schedule,
    get_week_parity,
    parse_time,
    visualize_schedule,
    should_skip_today,
)


def get_config_paths():
    """Get the paths to configuration files."""
    project_root = Path(__file__).parent.parent
    config_dir = project_root / "config"

    return {
        "settings": config_dir / "settings.toml",
        "odd_weeks": config_dir / "odd_weeks.toml",
        "even_weeks": config_dir / "even_weeks.toml",
    }


def update_command(args):
    """Handle the 'update' command - reload configuration and restart service."""
    print("🔄 Updating reminder configuration...")

    # Get configuration paths
    config_paths = get_config_paths()

    # Validate configuration files exist
    missing_files = []
    for name, path in config_paths.items():
        if not path.exists():
            missing_files.append(str(path))

    if missing_files:
        print("❌ Error: Missing configuration files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return 1

    # Try to reload configuration to validate it's valid
    try:
        print("📋 Validating configuration files...")
        settings, time_blocks, time_points = load_settings("settings.toml")
        odd_schedule = load_odd_week_schedule("odd_weeks.toml")
        even_schedule = load_even_week_schedule("even_weeks.toml")
        print("✅ Configuration files are valid")
    except Exception as e:
        print(f"❌ Error: Invalid configuration - {e}")
        return 1

    # Restart the reminder service
    print("🔄 Restarting reminder service...")
    try:
        # Stop the service if it's running
        result = subprocess.run(
            [
                "launchctl",
                "unload",
                "$HOME/Library/LaunchAgents/com.health.habits.reminder.plist",
            ],
            capture_output=True,
            text=True,
        )

        # Wait a moment
        time.sleep(2)

        # Start the service
        result = subprocess.run(
            [
                "launchctl",
                "load",
                "$HOME/Library/LaunchAgents/com.health.habits.reminder.plist",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("✅ Reminder service restarted successfully")
        else:
            print(f"⚠️  Warning: Could not restart LaunchAgent service: {result.stderr}")
            print("   You may need to restart the service manually")

    except Exception as e:
        print(f"⚠️  Warning: Could not restart service automatically: {e}")
        print(
            "   Configuration updated, but you may need to restart the service manually"
        )

    print("✅ Update completed successfully!")
    return 0


def view_command(args):
    """Handle the 'view' command - generate and show schedule visualizations."""
    print("📊 Generating schedule visualizations...")

    try:
        # Call the existing visualization function
        visualize_schedule()

        # Show the output paths
        print("\n📁 Visualization files generated:")
        print("   - schedule_visualization/odd_week_schedule.png")
        print("   - schedule_visualization/even_week_schedule.png")

        # Try to open the files if on macOS
        if sys.platform == "darwin":
            print("\n🖼️  Opening visualizations...")
            try:
                subprocess.run(["open", "schedule_visualization/odd_week_schedule.png"])
                subprocess.run(
                    ["open", "schedule_visualization/even_week_schedule.png"]
                )
            except Exception as e:
                print(f"⚠️  Could not open files automatically: {e}")

        return 0

    except Exception as e:
        print(f"❌ Error generating visualizations: {e}")
        return 1


def get_current_and_next_events():
    """Get current and next scheduled events."""
    try:
        # Get today's schedule
        today_schedule = get_today_schedule()

        if not today_schedule:
            return None, None, "No schedule for today (skipped day)"

        # Get current time
        now = datetime.now()
        current_time = now.time()
        current_time_str = now.strftime("%H:%M")

        # Parse all scheduled times for today
        scheduled_times = []
        for time_str in today_schedule.keys():
            try:
                scheduled_time = parse_time(time_str)
                scheduled_times.append((time_str, scheduled_time))
            except ValueError:
                continue

        # Sort by time
        scheduled_times.sort(key=lambda x: x[1])

        current_event = None
        next_event = None
        time_to_next = None

        # Find current and next events
        for i, (time_str, scheduled_time) in enumerate(scheduled_times):
            if scheduled_time <= current_time:
                # This event has passed or is happening now
                event = today_schedule[time_str]
                if isinstance(event, str):
                    current_event = f"{event} at {time_str}"
                elif isinstance(event, dict) and "block" in event:
                    title = event.get("title", event["block"])
                    current_event = f"{title} at {time_str}"
            else:
                # This is the next upcoming event
                event = today_schedule[time_str]
                if isinstance(event, str):
                    next_event = f"{event} at {time_str}"
                elif isinstance(event, dict) and "block" in event:
                    title = event.get("title", event["block"])
                    next_event = f"{title} at {time_str}"

                # Calculate time until next event
                time_diff = datetime.combine(
                    now.date(), scheduled_time
                ) - datetime.combine(now.date(), current_time)
                hours = time_diff.seconds // 3600
                minutes = (time_diff.seconds % 3600) // 60
                if hours > 0:
                    time_to_next = f"{hours}h {minutes}m"
                else:
                    time_to_next = f"{minutes}m"
                break

        return current_event, next_event, time_to_next

    except Exception as e:
        return None, None, f"Error: {e}"


def status_command(args):
    """Handle the 'status' command - show current status and next events."""
    print("📅 Checking reminder status...\n")

    try:
        # Get current week parity
        week_parity = get_week_parity()
        print(f"📊 Current week: {week_parity}")

        # Check if today is skipped
        settings, _, _ = load_settings("settings.toml")
        if should_skip_today(settings):
            print("⏭️  Today is a skipped day - no reminders scheduled")
            return 0

        # Get current and next events
        current_event, next_event, time_to_next = get_current_and_next_events()

        if current_event:
            print(f"🔔 Current event: {current_event}")
        else:
            print("🔕 No current event")

        if next_event and time_to_next:
            print(f"⏰ Next event: {next_event} (in {time_to_next})")
        elif next_event:
            print(f"⏰ Next event: {next_event}")
        else:
            print("📭 No more events scheduled for today")

        # Show today's full schedule if verbose
        if args.verbose:
            print("\n📋 Today's schedule:")
            today_schedule = get_today_schedule()
            if today_schedule:
                for time_str in sorted(today_schedule.keys()):
                    event = today_schedule[time_str]
                    if isinstance(event, str):
                        print(f"   {time_str}: {event}")
                    elif isinstance(event, dict) and "block" in event:
                        title = event.get("title", event["block"])
                        print(f"   {time_str}: {title}")

        return 0

    except Exception as e:
        print(f"❌ Error checking status: {e}")
        return 1


def main():
    """Main entry point for the CLI tool."""
    parser = argparse.ArgumentParser(
        description="Reminder CLI - Manage your schedule management system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  reminder update          # Update configuration and restart service
  reminder view            # Generate schedule visualizations
  reminder status          # Show current status and next events
  reminder status -v       # Show detailed status with full schedule
        """,
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Update command
    update_parser = subparsers.add_parser(
        "update", help="Update configuration and restart service"
    )
    update_parser.set_defaults(func=update_command)

    # View command
    view_parser = subparsers.add_parser("view", help="Generate schedule visualizations")
    view_parser.set_defaults(func=view_command)

    # Status command
    status_parser = subparsers.add_parser(
        "status", help="Show current status and next events"
    )
    status_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed schedule"
    )
    status_parser.set_defaults(func=status_command)

    # Parse arguments
    args = parser.parse_args()

    # If no command specified, show help
    if not args.command:
        parser.print_help()
        return 1

    # Execute the appropriate command
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
