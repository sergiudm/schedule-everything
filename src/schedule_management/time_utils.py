"""
Time Utilities - Time parsing, formatting, and manipulation functions.

This module provides utility functions for working with time values
in the schedule management system, including:
- Parsing time strings ('HH:MM') to datetime.time objects
- Converting time objects back to strings
- Adding/subtracting minutes from time strings
- Determining week parity (odd/even weeks)
- Repeating alarm functionality

These utilities are used throughout the application for schedule
processing and event timing.

Example Usage:
    >>> from schedule_management.time_utils import parse_time, get_week_parity
    >>> time_obj = parse_time('09:30')
    >>> parity = get_week_parity()  # Returns 'odd' or 'even'
"""

import time as time_module
from datetime import datetime, timedelta

from schedule_management.platform import play_sound, show_dialog


# =============================================================================
# WEEK PARITY
# =============================================================================


def get_week_parity() -> str:
    """
    Determine whether the current ISO week number is odd or even.

    Uses ISO calendar week numbering where weeks start on Monday
    and the first week of the year contains January 4th.

    Returns:
        str: 'odd' if the current week number is odd, 'even' if even

    Example:
        >>> parity = get_week_parity()
        >>> # Use different schedule based on odd/even week
        >>> schedule = odd_schedule if parity == 'odd' else even_schedule

    Note:
        This is useful for bi-weekly scheduling patterns (e.g., alternating
        class schedules, on-call rotations).
    """
    week_number = datetime.now().isocalendar().week
    return "odd" if week_number % 2 == 1 else "even"


# =============================================================================
# TIME PARSING AND FORMATTING
# =============================================================================


def parse_time(timestr: str) -> datetime.time:
    """
    Convert a time string in 'HH:MM' format to a datetime.time object.

    Args:
        timestr: Time string in 24-hour format (e.g., '09:30', '14:00')

    Returns:
        datetime.time: Time object representing the parsed time

    Raises:
        ValueError: If timestr is not in valid 'HH:MM' format

    Example:
        >>> t = parse_time('09:30')
        >>> t.hour, t.minute
        (9, 30)
    """
    return datetime.strptime(timestr, "%H:%M").time()


def time_to_str(t: datetime.time) -> str:
    """
    Convert a datetime.time object to a string in 'HH:MM' format.

    Args:
        t: A datetime.time object

    Returns:
        str: Time formatted as 'HH:MM' (24-hour format)

    Example:
        >>> from datetime import time
        >>> time_to_str(time(14, 30))
        '14:30'
    """
    return t.strftime("%H:%M")


def add_minutes_to_time(timestr: str, minutes: int) -> str:
    """
    Add a specified number of minutes to a time string.

    Args:
        timestr: Starting time in 'HH:MM' format
        minutes: Number of minutes to add (can be negative)

    Returns:
        str: Resulting time in 'HH:MM' format

    Example:
        >>> add_minutes_to_time('09:30', 25)
        '09:55'
        >>> add_minutes_to_time('23:45', 30)
        '00:15'

    Note:
        Handles day overflow (e.g., adding minutes past midnight).
    """
    dt = datetime.strptime(timestr, "%H:%M")
    new_dt = dt + timedelta(minutes=minutes)
    return new_dt.strftime("%H:%M")


# =============================================================================
# ALARM FUNCTIONALITY
# =============================================================================


def alarm(
    title: str,
    message: str,
    sound_file: str,
    alarm_interval: int,
    max_alarm_duration: int,
) -> None:
    """
    Trigger a repeating alarm until dismissed or timeout.

    Plays a sound and shows a dialog repeatedly until the user
    dismisses it or the maximum duration is reached.

    Args:
        title: Alarm title (currently unused, kept for API compatibility)
        message: Message to display in the alarm dialog
        sound_file: Path to the sound file to play
        alarm_interval: Seconds between alarm repetitions
        max_alarm_duration: Maximum total seconds to alarm before auto-stop

    Example:
        >>> alarm(
        ...     title='Break Time',
        ...     message='Time for a break!',
        ...     sound_file='/System/Library/Sounds/Ping.aiff',
        ...     alarm_interval=5,
        ...     max_alarm_duration=300
        ... )

    Note:
        The alarm stops when:
        1. User clicks '停止闹铃' (Stop Alarm) button
        2. max_alarm_duration seconds have elapsed
    """
    start_time = time_module.time()
    while True:
        play_sound(sound_file)
        button = show_dialog(message)
        if "停止闘铃" in button or "停止闹铃" in button:
            break
        if time_module.time() - start_time > max_alarm_duration:
            break
        time_module.sleep(alarm_interval)
