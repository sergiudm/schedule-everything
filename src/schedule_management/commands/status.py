"""
Status Commands - CLI commands for viewing schedule status.

This module provides CLI command handlers for schedule information:
- status_command: Show current status, next event, and today's schedule
- view_command: Generate PDF visualization of schedules

These commands help users understand their current schedule state
without modifying any data.

Example Usage (via CLI):
    $ reminder status          # Show current event and next upcoming
    $ reminder status -v       # Show full day schedule
    $ reminder view            # Generate schedule PDF
"""

import subprocess
import sys
from datetime import date, datetime, timedelta
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

from schedule_management import SETTINGS_PATH, ODD_PATH, EVEN_PATH
from schedule_management.config import ScheduleConfig, WeeklySchedule
from schedule_management.synced_schedule import (
    apply_synced_schedule,
    format_event_label,
    get_event_block_name,
)
from schedule_management.time_utils import get_week_parity, parse_time
from schedule_management.visualizer import ScheduleVisualizer


# =============================================================================
# SCHEDULE HELPERS
# =============================================================================


def get_today_schedule_for_status(
    apply_sync: bool = True,
) -> tuple[dict[str, Any], str, bool, ScheduleConfig]:
    """
    Get today's schedule with metadata for the status command.

    Returns:
        Tuple of (schedule_dict, parity, is_skipped, config)
        - schedule_dict: Today's merged schedule (empty if skipped)
        - parity: 'odd' or 'even' week
        - is_skipped: True if today is a skip day
        - config: ScheduleConfig instance
    """
    config = ScheduleConfig(SETTINGS_PATH)
    weekly = WeeklySchedule(ODD_PATH, EVEN_PATH)
    is_skipped = config.should_skip_today()
    parity = get_week_parity()
    schedule = {} if is_skipped else weekly.get_today_schedule(config)
    if apply_sync and schedule:
        weekday = date.today().strftime("%A").lower()
        schedule = apply_synced_schedule(
            schedule,
            target_date=date.today(),
            parity=parity,
            weekday=weekday,
        )

    return schedule, parity, is_skipped, config


def get_current_and_next_events(
    schedule: dict[str, Any],
    config: ScheduleConfig | None = None,
) -> tuple[str | None, str | None, str | None]:
    """
    Get current and next scheduled events from today's schedule.

    "Current" includes events that are actively happening now:
    - Time blocks are active for their configured duration
    - Time points/messages are active for 1 minute (the trigger minute)

    Args:
        schedule: Today's schedule dict (time -> event)
        config: Optional ScheduleConfig for duration lookup

    Returns:
        Tuple of (current_event, next_event, time_to_next)
        - current_event: Description of active event, or None
        - next_event: Description of next event, or None
        - time_to_next: Human-readable time until next event

    Example:
        >>> current, next_ev, time_until = get_current_and_next_events(schedule)
        >>> print(f"Now: {current}, Next: {next_ev} (in {time_until})")
    """
    if not schedule:
        return None, None, None

    now = datetime.now()
    current_time = now.time()
    today = date.today()
    now_dt = datetime.combine(today, current_time)

    def get_event_duration_minutes(event: Any) -> int:
        """Get event duration in minutes."""
        if config is None:
            return 1

        if isinstance(event, str):
            if event in config.time_blocks:
                return int(config.time_blocks[event])
            return 1

        if isinstance(event, dict) and "block" in event:
            block_type = event["block"]
            if block_type in config.time_blocks:
                return int(config.time_blocks[block_type])
            return 1

        return 1

    # Parse and sort scheduled times
    scheduled_times: list[tuple[str, datetime]] = []
    for time_str in schedule.keys():
        try:
            scheduled_time = parse_time(time_str)
            scheduled_times.append((time_str, datetime.combine(today, scheduled_time)))
        except ValueError:
            continue

    scheduled_times.sort(key=lambda x: x[1])

    current_event = None
    next_event = None
    time_to_next = None

    for time_str, start_dt in scheduled_times:
        event = schedule[time_str]

        event_name = format_event_label(event)
        duration_minutes = get_event_duration_minutes(event)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        # Check if this event is currently active
        if start_dt <= now_dt < end_dt:
            current_event = f"{event_name} at {time_str}"

        # Check if this is the next upcoming event
        if start_dt > now_dt and next_event is None:
            next_event = f"{event_name} at {time_str}"

            # Calculate time until next event
            diff = start_dt - now_dt
            total_minutes = int(diff.total_seconds() // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60

            if hours > 0:
                time_to_next = f"{hours}h {minutes}m"
            else:
                time_to_next = f"{minutes}m"

    return current_event, next_event, time_to_next


# =============================================================================
# STATUS COMMAND
# =============================================================================


def status_command(args) -> int:
    """
    Handle the 'status' command - show current status and schedule.

    Displays:
    - Week parity (odd/even)
    - Current active event (if any)
    - Next upcoming event with countdown
    - Full day schedule (if -v/--verbose flag)

    Args:
        args: Namespace with 'verbose' (bool) flag

    Returns:
        0 on success, 1 on error

    Example output:
        📅 Odd Week
        ╭─────────────────────────────────╮
        │           Status                │
        │                                 │
        │ 🔔 NOW:  Pomodoro at 09:00      │
        │                                 │
        │ ⏰ NEXT: Short Break at 09:25   │
        │          (in 15m)               │
        ╰─────────────────────────────────╯
    """
    console = Console()

    try:
        schedule, parity, is_skipped, config = get_today_schedule_for_status()

        # Header: Week parity
        parity_text = f"📅 {parity.title()} Week"
        parity_style = "bold magenta" if parity == "odd" else "bold cyan"
        console.print(Align.center(f"[{parity_style}]{parity_text}[/{parity_style}]"))

        # Handle skip days
        if is_skipped:
            console.print(
                Panel(
                    Align.center("⏭️  Today is a skipped day - enjoy your time off!"),
                    style="yellow",
                    box=box.ROUNDED,
                )
            )
            return 0

        # Get current and next events
        current_event, next_ev, time_until = get_current_and_next_events(
            schedule, config
        )

        # Build status content
        status_lines = []

        if current_event:
            status_lines.append(f"[bold green]🔔 NOW:[/bold green]  {current_event}")
        else:
            status_lines.append("[bold yellow]🟡 IDLE[/bold yellow]")

        status_lines.append("")  # Spacer

        if next_ev:
            time_str = f" (in {time_until})" if time_until else ""
            status_lines.append(
                f"[bold blue]⏰ NEXT:[/bold blue] {next_ev}[yellow]{time_str}[/yellow]"
            )
        else:
            status_lines.append("[dim]📭 No upcoming events[/dim]")

        # Show status panel
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

        # Verbose: show full schedule
        if args.verbose and schedule:
            console.print()  # Spacer

            # Categorize events by time of day
            morning_events = []
            afternoon_events = []
            evening_events = []

            sorted_times = sorted(schedule.keys())

            for time_str in sorted_times:
                event = schedule[time_str]
                name = format_event_label(event)
                block_name = get_event_block_name(event) or name

                try:
                    hour = int(time_str.split(":")[0])
                    item = (time_str, name, block_name)
                    if 5 <= hour < 12:
                        morning_events.append(item)
                    elif 12 <= hour < 18:
                        afternoon_events.append(item)
                    else:
                        evening_events.append(item)
                except ValueError:
                    evening_events.append((time_str, name, block_name))

            # Build schedule table
            table = Table(
                box=box.SIMPLE_HEAD,
                show_lines=False,
                header_style="bold",
                expand=True,
            )

            table.add_column(
                "Time", justify="right", style="cyan", width=8, no_wrap=True
            )
            table.add_column("Activity", justify="left")

            def add_period_section(title: str, icon: str, events: list, color: str):
                """Add a time-of-day section to the table."""
                if events:
                    table.add_section()
                    table.add_row(
                        f"[{color}]{icon}[/{color}]",
                        f"[bold {color}]{title}[/bold {color}]",
                    )

                    for time_str, name, block_name in events:
                        # Style based on activity type
                        block_name_lower = block_name.lower()
                        if (
                            "break" in block_name_lower
                            or "break" in name.lower()
                            or "napping" in block_name_lower
                        ):
                            name_styled = f"[italic dim]{name}[/italic dim]"
                            icon_type = "☕"
                        elif "pomodoro" in block_name_lower:
                            name_styled = f"[bold red]{name}[/bold red]"
                            icon_type = "🍅"
                        elif "potato" in block_name_lower:
                            name_styled = f"[bold yellow]{name}[/bold yellow]"
                            icon_type = "🥔"
                        elif "go_to_bed" in block_name_lower:
                            name_styled = f"[bold blue]{name}[/bold blue]"
                            icon_type = "🌙"
                        elif "summary_time" in block_name_lower:
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


# =============================================================================
# VIEW COMMAND
# =============================================================================


def view_command(args) -> int:
    """
    Handle the 'view' command - generate schedule visualization PDF.

    Creates a multi-page PDF on the Desktop with:
    - Odd week schedule
    - Even week schedule
    - Weekly statistics

    Automatically opens the PDF on macOS.

    Args:
        args: Namespace (unused, for CLI compatibility)

    Returns:
        0 on success, 1 on error

    Example:
        $ reminder view
        📊 Generating schedule visualizations...
        📁 Visualization file generated:
        🖼️  Opening visualization...
    """
    print("📊 Generating schedule visualizations...")

    try:
        config = ScheduleConfig(SETTINGS_PATH)
        weekly = WeeklySchedule(ODD_PATH, EVEN_PATH)
        visualizer = ScheduleVisualizer(config, weekly.odd_data, weekly.even_data)
        visualizer.visualize()

        print("\n📁 Visualization file generated:")

        # Open PDF on macOS
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
