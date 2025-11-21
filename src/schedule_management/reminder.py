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
    import matplotlib.patches as patches
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

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

from schedule_management.utils import get_week_parity, parse_time
from schedule_management.report import ReportGenerator


# --- VISUALIZER CLASS ---


class ScheduleVisualizer:
    """
    Handles the generation of beautiful PDF schedules using Matplotlib.
    """

    # Modern, vibrant pastel palette
    COLORS = {
        "pomodoro": "#FF6B6B",  # Soft Red
        "potato": "#EE5253",  # Deeper Red/Pink
        "long_break": "#1DD1A1",  # Bright Teal
        "short_break": "#48DBFB",  # Light Blue
        "napping": "#54A0FF",  # Blue
        "meeting": "#FF9F43",  # Orange
        "exercise": "#Feca57",  # Yellow
        "lunch": "#5F27CD",  # Deep Purple
        "summary_time": "#C8D6E5",  # Light Grey
        "go_to_bed": "#576574",  # Dark Grey
        "other": "#8395A7",  # Blue Grey
        "deep_work": "#0ABDE3",  # Cyan
    }

    # Text color for contrast (White for dark blocks, Dark Grey for light blocks)
    TEXT_COLORS = {
        "exercise": "#333333",  # Yellow needs dark text
        "summary_time": "#333333",
        "default": "#FFFFFF",
    }

    # Explicit durations in minutes for known activity types
    # This fixes the "thin line" issue for potato/pomodoro
    DEFAULT_DURATIONS = {
        "potato": 50,
        "pomodoro": 25,
        "long_break": 15,
        "short_break": 5,
        "lunch": 60,
        "napping": 20,
    }

    DAYS_ORDER = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    def __init__(self, config: ScheduleConfig, odd_schedule: dict, even_schedule: dict):
        self.config = config
        self.odd_schedule = odd_schedule
        self.even_schedule = even_schedule

    def _extract_activity_name(self, activity: Any) -> str:
        if isinstance(activity, str):
            return activity
        elif isinstance(activity, dict) and "block" in activity:
            return activity.get("title", activity["block"])
        else:
            return str(activity)

    def _get_activity_duration(self, activity_name: str) -> float:
        """
        Returns duration in HOURS.
        Checks config first, then manual defaults, then generic fallback.
        """
        # 1. Check Config
        if activity_name in self.config.time_blocks:
            return self.config.time_blocks[activity_name] / 60.0

        # 2. Check Manual Defaults (Case insensitive partial match)
        lower_name = activity_name.lower()
        for key, minutes in self.DEFAULT_DURATIONS.items():
            if key in lower_name:
                return minutes / 60.0

        # 3. Generic Fallback (0.5 hours = 30 mins) ensures visibility
        return 0.5

    def _get_color(self, activity_name: str) -> str:
        """Finds the best matching color."""
        lower_name = activity_name.lower()
        for key, color in self.COLORS.items():
            if key in lower_name:
                return color
        return self.COLORS["other"]

    def _get_text_color(self, activity_name: str) -> str:
        """Finds best text color based on background."""
        lower_name = activity_name.lower()
        for key, color in self.TEXT_COLORS.items():
            if key in lower_name:
                return color
        return self.TEXT_COLORS["default"]

    def _create_chart(self, ax, schedule_data: dict, title: str):
        if not MATPLOTLIB_AVAILABLE:
            return

        # Setup aesthetics
        ax.set_facecolor("#FFFFFF")  # Pure white background for clean look
        used_activities = set()

        # Draw Day Columns background (Alternating subtle grey)
        for i in range(0, len(self.DAYS_ORDER), 2):
            ax.axvspan(i - 0.5, i + 0.5, color="#F7F9FA", zorder=0)

        for day_idx, day in enumerate(self.DAYS_ORDER):
            day_schedule = {}
            if "common" in schedule_data:
                day_schedule.update(schedule_data["common"])
            if day in schedule_data:
                day_schedule.update(schedule_data[day])

            for time_str, activity in day_schedule.items():
                activity_name = self._extract_activity_name(activity)
                used_activities.add(activity_name)

                # Parse time
                time_parts = time_str.split(":")
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                time_decimal = hour + minute / 60.0

                # Calculate duration
                duration_hours = self._get_activity_duration(activity_name)

                # Get Colors
                bg_color = self._get_color(activity_name)
                txt_color = self._get_text_color(activity_name)

                # Draw Block
                rect_width = 0.85  # Slightly thinner for elegance
                rect_x = day_idx - (rect_width / 2)

                # Main colored block
                rect = patches.Rectangle(
                    (rect_x, time_decimal),
                    rect_width,
                    duration_hours,
                    linewidth=0,
                    facecolor=bg_color,
                    alpha=0.9,
                    zorder=2,
                )
                ax.add_patch(rect)

                # Optional: Left accent border for "depth"
                rect_accent = patches.Rectangle(
                    (rect_x, time_decimal),
                    0.04,  # Thin strip on left
                    duration_hours,
                    linewidth=0,
                    facecolor="black",
                    alpha=0.1,
                    zorder=3,
                )
                ax.add_patch(rect_accent)

                # ADD TEXT LABEL inside the block if it's big enough
                if duration_hours >= 0.3:  # Only if block > 18 mins
                    font_size = 8 if duration_hours > 0.5 else 6
                    # Clean up name for display (remove underscores)
                    display_name = activity_name.replace("_", " ").title()

                    # If it's very short, just show first letter or short code
                    if duration_hours < 0.4:
                        display_name = display_name[:3]

                    ax.text(
                        day_idx,
                        time_decimal + (duration_hours / 2),
                        display_name,
                        ha="center",
                        va="center",
                        color=txt_color,
                        fontsize=font_size,
                        fontweight="bold",
                        zorder=4,
                    )

        # Configure Axes
        ax.set_xlim(-0.5, len(self.DAYS_ORDER) - 0.5)
        ax.set_ylim(24, 6)  # 6 AM at top, Midnight at bottom

        # Top X Axis (Days)
        ax.set_xticks(range(len(self.DAYS_ORDER)))
        ax.set_xticklabels(
            [d.upper()[:3] for d in self.DAYS_ORDER],  # MON, TUE...
            fontsize=11,
            weight="bold",
            color="#57606f",
        )
        ax.tick_params(axis="x", pad=10)  # Move labels up slightly

        # Left Y Axis (Time)
        hour_ticks = list(range(6, 25))
        ax.set_yticks(hour_ticks)
        ax.set_yticklabels(
            [f"{h:02d}:00" for h in hour_ticks],
            fontsize=9,
            color="#a4b0be",
            family="monospace",
        )

        # Grid
        ax.grid(True, axis="y", linestyle=":", alpha=0.4, color="#dfe4ea", zorder=1)
        ax.grid(False, axis="x")

        # Clean Spines
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Add a subtle left spine for time anchor
        ax.axvline(-0.5, color="#dfe4ea", linewidth=1)

        # Title
        ax.set_title(
            title.upper(),
            fontsize=20,
            weight="heavy",
            pad=25,
            color="#2f3542",
            loc="left",
        )

        # Legend (only if we have untagged items or want summary)
        # Since we have inline labels, we can make the legend smaller or cleaner
        legend_elements = [
            patches.Patch(
                facecolor=self._get_color(act),
                label=act.replace("_", " ").title(),
                edgecolor="none",
            )
            for act in sorted(used_activities)
        ]

        if legend_elements:
            ax.legend(
                handles=legend_elements,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.08),  # Below chart
                ncol=min(len(used_activities), 6),
                frameon=False,
                fontsize=8,
            )

    def _calculate_weekly_stats(self, schedule_data: dict) -> dict[str, Any]:
        pomodoro_count = 0
        potato_count = 0
        work_hours = 0.0

        work_activities = {"pomodoro", "potato", "deep_work", "meeting"}

        for day in self.DAYS_ORDER:
            day_schedule = {}
            if "common" in schedule_data:
                day_schedule.update(schedule_data["common"])
            if day in schedule_data:
                day_schedule.update(schedule_data[day])

            for _, activity in day_schedule.items():
                activity_name = self._extract_activity_name(activity)

                # Use the unified duration logic
                duration_hours = self._get_activity_duration(activity_name)

                if "pomodoro" in activity_name.lower():
                    pomodoro_count += 1
                if "potato" in activity_name.lower():
                    potato_count += 1

                # Check if it's a work activity
                if (
                    activity_name in work_activities
                    or "pomodoro" in activity_name.lower()
                    or "potato" in activity_name.lower()
                ):
                    work_hours += duration_hours

        return {
            "pomodoro_count": pomodoro_count,
            "work_hours": work_hours,
            "potato_count": potato_count,
        }

    def _create_stats_page(self, ax, odd_stats: dict, even_stats: dict):
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        # Decorative background circle
        circle = patches.Circle((0.5, 0.5), 0.4, color="#F7F9FA", zorder=0)
        ax.add_patch(circle)

        # Title
        ax.text(
            0.5,
            0.92,
            "WEEKLY STATISTICS",
            ha="center",
            va="center",
            fontsize=22,
            weight="bold",
            color="#2f3542",
        )
        ax.plot([0.3, 0.7], [0.89, 0.89], color="#ff6b6b", linewidth=2)  # Underline

        def draw_stat_column(x_pos, title, stats, color_theme):
            # Header
            ax.text(
                x_pos,
                0.78,
                title,
                ha="center",
                fontsize=16,
                weight="bold",
                color=color_theme,
            )

            # Stat 1: Work Hours
            ax.text(
                x_pos,
                0.65,
                f"{stats['work_hours']:.1f}h",
                ha="center",
                fontsize=45,
                weight="heavy",
                color="#2f3542",
            )
            ax.text(
                x_pos,
                0.58,
                "Work Time",
                ha="center",
                fontsize=12,
                color="#a4b0be",
                weight="medium",
            )

            # Stat 2: Pomodoros
            ax.text(
                x_pos,
                0.45,
                f"{stats['pomodoro_count']}",
                ha="center",
                fontsize=45,
                weight="heavy",
                color="#2f3542",
            )
            ax.text(
                x_pos,
                0.38,
                "Pomodoros",
                ha="center",
                fontsize=12,
                color="#a4b0be",
                weight="medium",
            )

            # Stat 3: Potatoes
            ax.text(
                x_pos,
                0.25,
                f"{stats['potato_count']}",
                ha="center",
                fontsize=45,
                weight="heavy",
                color="#2f3542",
            )
            ax.text(
                x_pos,
                0.18,
                "Potatoes",
                ha="center",
                fontsize=12,
                color="#a4b0be",
                weight="medium",
            )

        draw_stat_column(0.25, "ODD WEEK", odd_stats, "#ff6b6b")
        draw_stat_column(0.75, "EVEN WEEK", even_stats, "#54a0ff")

        # Vertical Divider
        ax.plot([0.5, 0.5], [0.15, 0.8], color="#dfe4ea", linewidth=1, linestyle="--")

    def visualize(self):
        if not MATPLOTLIB_AVAILABLE:
            print(
                "❌ matplotlib is not available. Please install it: pip install matplotlib"
            )
            return

        import platform

        if platform.system() == "Windows":
            desktop_path = Path.home() / "Desktop"
        else:
            desktop_path = Path.home() / "Desktop"

        pdf_filename = desktop_path / "schedule_visualization.pdf"

        # Global font settings for cleaner look
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans"]

        with PdfPages(pdf_filename) as pdf:
            # Page 1: Odd Week
            fig1, ax1 = plt.subplots(figsize=(14, 9))  # 14x9 is a good landscape aspect
            self._create_chart(ax1, self.odd_schedule, "Odd Week Schedule")
            plt.tight_layout()
            pdf.savefig(fig1, dpi=300, bbox_inches="tight")
            plt.close(fig1)

            # Page 2: Even Week
            fig2, ax2 = plt.subplots(figsize=(14, 9))
            self._create_chart(ax2, self.even_schedule, "Even Week Schedule")
            plt.tight_layout()
            pdf.savefig(fig2, dpi=300, bbox_inches="tight")
            plt.close(fig2)

            # Page 3: Stats
            fig3 = plt.figure(figsize=(14, 9))
            ax3 = fig3.add_subplot(111)
            odd_stats = self._calculate_weekly_stats(self.odd_schedule)
            even_stats = self._calculate_weekly_stats(self.even_schedule)
            self._create_stats_page(ax3, odd_stats, even_stats)
            plt.tight_layout()
            pdf.savefig(fig3, dpi=300, bbox_inches="tight")
            plt.close(fig3)

        print(f"Schedule visualization saved as '{pdf_filename}'")
        print("\nSchedule visualization complete!")
        print("Generated file:")
        print("- schedule_visualization.pdf (on Desktop)")
        print("  - Page 1: Odd Week Schedule")
        print("  - Page 2: Even Week Schedule")
        print("  - Page 3: Statistics")


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


def get_ddl_path() -> Path:
    """Get deadline JSON path from config directory."""
    config_dir = get_config_dir()
    return Path(config_dir) / "ddl.json"


def get_habits_path() -> Path:
    """Get habits TOML path from config directory."""
    config_dir = get_config_dir()
    return Path(config_dir) / "habits.toml"


def get_record_path() -> Path:
    """Get habit tracking record JSON path from settings.toml."""
    try:
        config = ScheduleConfig(get_settings_path())
        raw_path_str = os.path.expandvars(config.record_path)
        target_path = Path(raw_path_str).expanduser()
        if target_path.is_absolute():
            return target_path
        # If relative, make it relative to config directory
        return Path(config.config_dir) / target_path
    except Exception as e:
        print(f"Error getting record path: {e}")
        default_path = Path.home() / ".schedule_management" / "task" / "record.json"
        env_path = os.getenv("REMINDER_RECORD_PATH")
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


def load_deadlines() -> list[dict[str, Any]]:
    """Load deadlines from the JSON file."""
    ddl_path = get_ddl_path()
    if not ddl_path.exists():
        print("No deadlines file found, starting with an empty deadline list.")
        return []

    try:
        with open(ddl_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print("Error loading deadlines file, starting with an empty deadline list.")
        return []


def save_deadlines(deadlines: list[dict[str, Any]]) -> None:
    """Save deadlines to the JSON file."""
    ddl_path = get_ddl_path()

    # Ensure destination directory exists
    ddl_path.parent.mkdir(parents=True, exist_ok=True)

    with open(ddl_path, "w", encoding="utf-8") as f:
        json.dump(deadlines, f, indent=2, ensure_ascii=False)


def load_habits() -> dict[str, str]:
    """Load habits from the TOML file."""
    habits_path = get_habits_path()
    if not habits_path.exists():
        print("No habits file found.")
        return {}

    try:
        with open(habits_path, "rb") as f:
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
    record_path = get_record_path()
    if not record_path.exists():
        return []

    try:
        with open(record_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_habit_records(records: list[dict[str, Any]]) -> None:
    """Save habit tracking records to the JSON file."""
    record_path = get_record_path()

    # Ensure destination directory exists
    record_path.parent.mkdir(parents=True, exist_ok=True)

    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


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

        # Determine color and status based on days left
        if days_left < 0:
            color = "red"
            status = "⚠️ OVERDUE"
            days_text = f"[{color}]{days_left} days[/{color}]"
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

        # Add row
        table.add_row(event_name, deadline_display, days_text, status)

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


def report_command(args):
    """Handle the 'report' command - generate weekly or monthly reports."""
    report_type = args.type

    print(f"📊 Generating {report_type} report...")

    try:
        # Load configuration
        settings_path = get_settings_path()
        config = ScheduleConfig(settings_path)

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
