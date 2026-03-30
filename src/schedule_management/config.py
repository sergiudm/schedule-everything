"""
Schedule Configuration - Configuration loading and management.

This module provides classes for loading and managing schedule configuration:
- ScheduleConfig: Main settings from settings.toml (time blocks, paths, etc.)
- WeeklySchedule: Odd/even week schedules from TOML files

The schedule system uses separate configuration files:
- settings.toml: Global settings, time block durations, paths
- odd_weeks.toml: Schedule for odd-numbered ISO weeks
- even_weeks.toml: Schedule for even-numbered ISO weeks

Example Usage:
    >>> from schedule_management.config import ScheduleConfig, WeeklySchedule
    >>>
    >>> config = ScheduleConfig('~/.config/reminder/settings.toml')
    >>> print(config.sound_file)  # Get notification sound
    >>> print(config.time_blocks)  # {'pomodoro': 25, 'long_break': 15, ...}
    >>>
    >>> weekly = WeeklySchedule('odd_weeks.toml', 'even_weeks.toml')
    >>> today_schedule = weekly.get_today_schedule(config)
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import tomllib


# =============================================================================
# TOML FILE LOADING
# =============================================================================


def load_toml_file(file_path: str) -> dict[str, Any]:
    """
    Load and parse a TOML configuration file.

    Args:
        file_path: Path to the TOML file

    Returns:
        Dictionary containing the parsed TOML data

    Raises:
        FileNotFoundError: If the file doesn't exist
        tomllib.TOMLDecodeError: If the TOML syntax is invalid
    """
    with open(file_path, "rb") as f:
        return tomllib.load(f)


# =============================================================================
# SCHEDULE CONFIGURATION
# =============================================================================


class ScheduleConfig:
    """
    Main configuration class for the schedule management system.

    Loads settings from a TOML file and provides typed access to:
    - General settings (sound file, alarm intervals, skip days)
    - Time blocks (activity durations like pomodoro, breaks)
    - Time points (single-moment notifications)
    - Task scheduling (daily summary, reviews)
    - File paths (tasks, logs, reports)

    Attributes:
        settings: General configuration dict
        time_blocks: Dict mapping block names to durations (minutes)
        time_points: Dict mapping point names to messages
        tasks: Task scheduling configuration
        paths: File path configuration

    Example:
        >>> config = ScheduleConfig('/path/to/settings.toml')
        >>> config.should_skip_today()  # Check if today is a skip day
        False
        >>> config.time_blocks['pomodoro']  # Get pomodoro duration
        25
    """

    def __init__(self, settings_path: str):
        """
        Initialize configuration from a TOML file.

        Args:
            settings_path: Path to settings.toml file
        """
        config = load_toml_file(settings_path)
        self.settings = config.get("settings", {})
        self.time_blocks = config.get("time_blocks", {})
        self.time_points = config.get("time_points", {})
        self.tasks = config.get("tasks", {})
        self.paths = config.get("paths", {})

    # =========================================================================
    # SOUND & ALARM SETTINGS
    # =========================================================================

    @property
    def sound_file(self) -> str:
        """
        Path to the notification sound file.

        Returns:
            Sound file path (default: macOS Ping sound)
        """
        return self.settings.get("sound_file", "/System/Library/Sounds/Ping.aiff")

    @property
    def alarm_interval(self) -> int:
        """
        Seconds between alarm repetitions when not dismissed.

        Returns:
            Interval in seconds (default: 5)
        """
        return self.settings.get("alarm_interval", 5)

    @property
    def max_alarm_duration(self) -> int:
        """
        Maximum seconds to repeat alarm before auto-stop.

        Returns:
            Duration in seconds (default: 300 = 5 minutes)
        """
        return self.settings.get("max_alarm_duration", 300)

    # =========================================================================
    # SKIP DAYS
    # =========================================================================

    def should_skip_today(self) -> bool:
        """
        Check if today should skip all scheduled reminders.

        Uses the 'skip_days' setting to determine if today
        (by weekday name) is configured as a rest day.

        Returns:
            True if today should be skipped, False otherwise

        Example:
            >>> # If settings.toml has: skip_days = ["saturday", "sunday"]
            >>> config.should_skip_today()  # On Saturday
            True
        """
        skip_days = self.settings.get("skip_days", [])
        if not skip_days:
            return False
        current_weekday = datetime.now().strftime("%A").lower()
        return current_weekday in skip_days

    # =========================================================================
    # TASK SCHEDULING
    # =========================================================================

    @property
    def daily_summary_time(self) -> str:
        """
        Time to show daily task summary popup (HH:MM format).

        Returns:
            Time string (default: '22:00')
        """
        return self.tasks.get("daily_summary", "22:00")

    @property
    def weekly_review_time(self) -> str:
        """
        Weekly review schedule (format: 'weekday HH:MM', e.g., 'sunday 20:00').

        Returns:
            Schedule string or empty string if not configured
        """
        return self.tasks.get("weekly_review", "")

    @property
    def monthly_review_time(self) -> str:
        """
        Monthly review schedule (format: 'day HH:MM', e.g., '1 20:00').

        Returns:
            Schedule string or empty string if not configured
        """
        return self.tasks.get("monthly_review", "")

    @property
    def daily_urgent_times(self) -> list[str]:
        """
        Times to show urgent task reminders (list of HH:MM strings).

        Returns:
            List of time strings
        """
        return self.tasks.get("daily_urgency", self.tasks.get("daily_urgent", []))

    @property
    def ddl_urgent_times(self) -> list[str]:
        """
        Times to show deadline reminders (list of HH:MM strings).

        Returns:
            List of time strings
        """
        return self.tasks.get("ddl_urgency", self.tasks.get("ddl_urgent", []))

    @property
    def habit_prompt_time(self) -> str:
        """
        Time to show habit tracking prompt (HH:MM format).

        Returns:
            Time string or empty string if not configured
        """
        return self.tasks.get("habit_prompt", self.tasks.get("habit_tracking", ""))

    # =========================================================================
    # FILE PATHS
    # =========================================================================

    @property
    def config_dir(self) -> str:
        """
        Configuration directory path.

        Returns:
            Directory path (default: 'config')
        """
        return self.paths.get("config_dir", "config")

    @property
    def tasks_path(self) -> str:
        """
        Path to tasks JSON file.

        Returns:
            File path (default: 'tasks.json')
        """
        return self.paths.get("tasks_path", "tasks.json")

    @property
    def log_path(self) -> str:
        """
        Path to task log file, with ~ expansion.

        Returns:
            Expanded file path
        """
        log_path = self.paths.get("log_path", "~/.schedule_management/task/tasks.log")
        if "~" in log_path or "$HOME" in log_path:
            return Path(log_path).expanduser()
        return log_path

    @property
    def record_path(self) -> str:
        """
        Path to habit tracking records file.

        Returns:
            File path (default: 'task/record.json')
        """
        return self.paths.get("record_path", "task/record.json")


# =============================================================================
# WEEKLY SCHEDULE
# =============================================================================


class WeeklySchedule:
    """
    Manages odd and even week schedules.

    The schedule system uses alternating schedules based on ISO week number:
    - Odd weeks use odd_data
    - Even weeks use even_data

    Each schedule file contains:
    - 'common': Events that occur every day
    - Day-specific sections (monday, tuesday, etc.)

    Attributes:
        odd_data: Schedule dict for odd weeks
        even_data: Schedule dict for even weeks

    Example:
        >>> weekly = WeeklySchedule('odd_weeks.toml', 'even_weeks.toml')
        >>> schedule = weekly.get_today_schedule(config)
        >>> for time, event in schedule.items():
        ...     print(f'{time}: {event}')
    """

    def __init__(self, odd_path: str, even_path: str):
        """
        Load odd and even week schedules from TOML files.

        Args:
            odd_path: Path to odd weeks TOML file
            even_path: Path to even weeks TOML file
        """
        self.odd_data = load_toml_file(odd_path)
        self.even_data = load_toml_file(even_path)

    def get_schedule_for_parity(self, parity: str) -> dict:
        """
        Get the full schedule data for a given week parity.

        Args:
            parity: Either 'odd' or 'even'

        Returns:
            Schedule dictionary for that parity
        """
        return self.odd_data if parity == "odd" else self.even_data

    def get_today_schedule(self, config: ScheduleConfig) -> dict:
        """
        Get today's merged schedule (common + day-specific).

        Combines the 'common' schedule with today's day-specific
        schedule, respecting skip days from config.

        Args:
            config: ScheduleConfig instance to check skip days

        Returns:
            Dict mapping time strings to events, or empty dict if skipped

        Example:
            >>> schedule = weekly.get_today_schedule(config)
            >>> # On a Monday in an odd week:
            >>> schedule['09:00']  # Returns event at 9 AM
        """
        # Check if today should be skipped
        if config.should_skip_today():
            return {}

        # Determine current day and week parity
        now = datetime.now()
        weekday = now.strftime("%A").lower()

        # Import here to avoid circular dependency
        from schedule_management.time_utils import get_week_parity

        parity = get_week_parity()

        # Get schedule for current week parity
        schedule_data = self.get_schedule_for_parity(parity)

        # Merge common schedule with day-specific overrides
        common = schedule_data.get("common", {})
        day_specific = schedule_data.get(weekday, {})
        return {**common, **day_specific}
