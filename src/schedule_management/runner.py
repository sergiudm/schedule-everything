"""
Schedule Runner - Main scheduling loop and event handling.

This module provides the ScheduleRunner class which is the core
runtime engine of the schedule management system. It:

- Monitors the current time and triggers events at scheduled times
- Handles time blocks (activities with duration) and time points
- Shows daily summary and habit tracking popups
- Checks for urgent tasks and deadlines
- Auto-generates weekly/monthly reports

The runner operates as a continuous loop, checking every 20 seconds
for events that need to be triggered.

Example Usage:
    >>> from schedule_management.runner import ScheduleRunner
    >>> from schedule_management.config import ScheduleConfig, WeeklySchedule
    >>>
    >>> config = ScheduleConfig('settings.toml')
    >>> weekly = WeeklySchedule('odd_weeks.toml', 'even_weeks.toml')
    >>> runner = ScheduleRunner(config, weekly)
    >>> runner.run()  # Starts the main loop (blocking)

Entry Point:
    This module is typically run via the reminder-runner command,
    which loads configuration and starts the runner.
"""

import json
import threading
import time
from datetime import datetime
from typing import Any

from schedule_management import (
    SETTINGS_PATH,
    DDL_PATH,
    TASKS_PATH,
)
from schedule_management.config import ScheduleConfig, WeeklySchedule
from schedule_management.time_utils import add_minutes_to_time, alarm
from schedule_management.platform import play_sound
from schedule_management.popups import (
    show_daily_summary_popup,
    show_habit_tracking_popup,
)
from schedule_management.report import auto_generate_reports


# =============================================================================
# AUTO REPORT GENERATION
# =============================================================================


def try_auto_generate_reports(settings_path: str) -> None:
    """
    Attempt to generate scheduled reports using settings.toml.

    Called at configured weekly/monthly review times. Generates
    reports if they don't already exist for the current period.

    Args:
        settings_path: Path to settings.toml file
    """
    try:
        generated = auto_generate_reports(settings_path)
        if generated:
            for span, pdf_path in generated.items():
                print(f"📊 Generated {span} report at {pdf_path}")
    except FileNotFoundError:
        print(f"⚠️  settings.toml not found for auto reports: {settings_path}")
    except Exception as exc:
        print(f"⚠️  Auto report generation skipped: {exc}")


# =============================================================================
# SCHEDULE RUNNER
# =============================================================================


class ScheduleRunner:
    """
    Main runtime engine for the schedule management system.

    The runner continuously monitors the clock and triggers:
    - Scheduled activities (time blocks with start/end alarms)
    - Point notifications (single-time reminders)
    - Daily summary popup
    - Habit tracking popup
    - Urgent task/deadline reminders
    - Report generation

    Attributes:
        config: ScheduleConfig instance with settings
        weekly_schedule: WeeklySchedule instance with schedules
        notified_today: Set of events already triggered today
        pending_end_alarms: Dict of end-time alarms to trigger

    Example:
        >>> runner = ScheduleRunner(config, weekly_schedule)
        >>> runner.run()  # Starts blocking main loop
    """

    def __init__(self, config: ScheduleConfig, weekly_schedule: WeeklySchedule):
        """
        Initialize the runner with configuration.

        Args:
            config: ScheduleConfig instance
            weekly_schedule: WeeklySchedule instance
        """
        self.config = config
        self.weekly_schedule = weekly_schedule
        self.notified_today = set()  # Events already handled today
        self.pending_end_alarms = {}  # {end_time_str: message}

    # =========================================================================
    # ALARM HANDLING
    # =========================================================================

    def _trigger_alarm(self, title: str, message: str, sound: str = None) -> None:
        """
        Trigger an alarm notification in a background thread.

        Args:
            title: Alarm title (for logging, not displayed)
            message: Message to show in the dialog
            sound: Optional sound name/path (defaults to config sound)
        """
        sound_file = sound if sound else self.config.sound_file

        # Handle short sound names (convert to full path)
        if sound and "/" not in sound and not sound.endswith(".aiff"):
            sound_file = f"/System/Library/Sounds/{sound}.aiff"

        # Run alarm in background thread to not block main loop
        threading.Thread(
            target=alarm,
            args=(
                title,
                message,
                sound_file,
                self.config.alarm_interval,
                self.config.max_alarm_duration,
            ),
            daemon=True,
        ).start()

    # =========================================================================
    # EVENT HANDLING
    # =========================================================================

    def _handle_event(self, time_str: str, event: Any) -> None:
        """
        Handle a scheduled event (time block or time point).

        Events can be:
        - String: Time block name or direct message
        - Dict: {'block': 'type', 'title': 'Custom Title'}

        Args:
            time_str: The scheduled time (HH:MM)
            event: Event definition (string or dict)
        """
        if isinstance(event, str):
            if event in self.config.time_blocks:
                # It's a time block (e.g., 'pomodoro')
                self._start_time_block(time_str, event, event)
            else:
                # It's a time_point key or direct message
                if event in self.config.time_points:
                    message = self.config.time_points[event]
                else:
                    message = event  # Use string as message directly
                self._trigger_alarm("提醒", message)
                self.notified_today.add(time_str)
        elif isinstance(event, dict) and "block" in event:
            # Dict with block type and optional title
            block_type = event["block"]
            title = event.get("title", block_type)
            if block_type in self.config.time_blocks:
                self._start_time_block(time_str, block_type, title)
            else:
                print(f"Warning: Unknown block type '{block_type}' at {time_str}")

    def _start_time_block(self, start_time: str, block_type: str, title: str) -> None:
        """
        Start a time block and schedule its end alarm.

        Shows a start notification and queues an end notification
        for when the block duration expires.

        Args:
            start_time: Start time (HH:MM)
            block_type: Block type name (for duration lookup)
            title: Display title for notifications
        """
        duration = self.config.time_blocks[block_type]
        end_time_str = add_minutes_to_time(start_time, duration)

        # Start notification
        start_message = f"{title} ⏱️ ({duration}min)"
        self._trigger_alarm("开始", start_message)
        self.notified_today.add(start_time)

        # Schedule end notification
        end_message = f"{title} 结束！休息一下 🎉"
        self.pending_end_alarms[end_time_str] = end_message

    # =========================================================================
    # URGENT TASKS & DEADLINES
    # =========================================================================

    def _get_unfinished_urgent_tasks(self) -> list[dict[str, Any]]:
        """
        Get high-priority tasks that are still pending.

        Returns:
            List of task dicts with priority > 7
        """
        try:
            with open(TASKS_PATH, "r", encoding="utf-8") as f:
                tasks = json.load(f)
            return [t for t in tasks if t.get("priority", 0) > 7]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _get_urgent_deadlines(self) -> list[dict[str, Any]]:
        """
        Get deadlines that are due within 3 days.

        Returns:
            List of deadline dicts with days_left <= 3, sorted by urgency
        """
        try:
            with open(DDL_PATH, "r", encoding="utf-8") as f:
                deadlines = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

        today = datetime.now().date()
        urgent: list[dict[str, Any]] = []

        for ddl in deadlines:
            if not isinstance(ddl, dict):
                continue
            event = ddl.get("event")
            deadline_str = ddl.get("deadline")
            if not event or not deadline_str:
                continue

            try:
                deadline_date = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            except Exception:
                continue

            days_left = (deadline_date - today).days
            if days_left <= 3:
                urgent.append(
                    {
                        "event": str(event),
                        "deadline": deadline_str,
                        "days_left": days_left,
                    }
                )

        # Sort by days left, then deadline, then event name
        urgent.sort(
            key=lambda d: (
                d.get("days_left", 0),
                d.get("deadline", ""),
                d.get("event", ""),
            )
        )
        return urgent

    def _check_urgent_tasks(self) -> None:
        """Show reminder for high-priority unfinished tasks."""
        urgent_tasks = self._get_unfinished_urgent_tasks()
        if urgent_tasks:
            task_descriptions = [
                f"{t.get('description', '未知任务')} (优先级: {t.get('priority', 0)})"
                for t in urgent_tasks
            ]
            message = "🚨 今日紧急任务提醒 🚨\n\n" + "\n".join(task_descriptions)
            self._trigger_alarm("Today's Urgent Tasks", message, sound="Glass")

    def _check_urgent_deadlines(self) -> None:
        """Show reminder for approaching deadlines."""
        urgent_deadlines = self._get_urgent_deadlines()
        if not urgent_deadlines:
            return

        lines: list[str] = []
        for ddl in urgent_deadlines:
            event = ddl.get("event", "未知事件")
            deadline_str = ddl.get("deadline", "")
            days_left = ddl.get("days_left", 0)

            if days_left < 0:
                lines.append(f"⚠️ {event} - {deadline_str} (已逾期 {-days_left} 天)")
            elif days_left == 0:
                lines.append(f"🔴 {event} - {deadline_str} (今天截止)")
            else:
                lines.append(f"🚨 {event} - {deadline_str} (剩余 {days_left} 天)")

        message = "📅 紧急DDL提醒\n\n" + "\n".join(lines)
        self._trigger_alarm("Urgent Deadlines", message, sound="Glass")

    # =========================================================================
    # MAIN LOOP
    # =========================================================================

    def run(self) -> None:
        """
        Start the main scheduling loop.

        Continuously monitors the clock and triggers events.
        This method runs forever until the process is terminated.

        The loop:
        1. Checks if daily summary time is reached
        2. Checks if habit prompt time is reached
        3. Checks urgent task/deadline times
        4. Checks weekly/monthly review times
        5. Triggers scheduled events from today's schedule
        6. Triggers pending end alarms
        7. Resets at midnight
        8. Sleeps 20 seconds before next check
        """
        while True:
            now = datetime.now()
            now_str = now.strftime("%H:%M")
            today_schedule = self.weekly_schedule.get_today_schedule(self.config)

            # -----------------------------------------------------------------
            # Daily Summary Time
            # -----------------------------------------------------------------
            daily_summary_key = f"daily_summary_{now_str}"
            if (
                now_str == self.config.daily_summary_time
                and daily_summary_key not in self.notified_today
                and not self.config.should_skip_today()
            ):
                threading.Thread(target=show_daily_summary_popup, daemon=True).start()
                self.notified_today.add(daily_summary_key)

            # -----------------------------------------------------------------
            # Habit Prompt Time
            # -----------------------------------------------------------------
            habit_prompt_time = self.config.habit_prompt_time
            habit_prompt_key = f"habit_prompt_{now.strftime('%Y-%m-%d')}"
            if (
                habit_prompt_time
                and now_str == habit_prompt_time
                and habit_prompt_key not in self.notified_today
                and not self.config.should_skip_today()
            ):
                threading.Thread(target=show_habit_tracking_popup, daemon=True).start()
                self.notified_today.add(habit_prompt_key)

            # -----------------------------------------------------------------
            # Urgent Tasks & Deadlines
            # -----------------------------------------------------------------
            if not self.config.should_skip_today():
                # Check urgent tasks
                for urgent_time in self.config.daily_urgent_times:
                    urgent_tasks_key = f"urgent_tasks_{urgent_time}"
                    if (
                        now_str == urgent_time
                        and urgent_tasks_key not in self.notified_today
                    ):
                        self._check_urgent_tasks()
                        self.notified_today.add(urgent_tasks_key)

                # Check urgent deadlines
                for urgent_time in self.config.ddl_urgent_times:
                    urgent_ddls_key = f"urgent_ddls_{urgent_time}"
                    if (
                        now_str == urgent_time
                        and urgent_ddls_key not in self.notified_today
                    ):
                        self._check_urgent_deadlines()
                        self.notified_today.add(urgent_ddls_key)

            # -----------------------------------------------------------------
            # Weekly Review
            # -----------------------------------------------------------------
            weekly_review_setting = self.config.weekly_review_time
            if weekly_review_setting:
                try:
                    parts = weekly_review_setting.split()
                    if len(parts) == 2:
                        day_of_week, review_time = parts
                        if (
                            now.strftime("%A").lower() == day_of_week.lower()
                            and now_str == review_time
                        ):
                            review_key = f"weekly_review_{now.strftime('%Y-%m-%d')}"
                            if review_key not in self.notified_today:
                                threading.Thread(
                                    target=try_auto_generate_reports,
                                    args=(SETTINGS_PATH,),
                                    daemon=True,
                                ).start()
                                self.notified_today.add(review_key)
                except Exception:
                    pass

            # -----------------------------------------------------------------
            # Monthly Review
            # -----------------------------------------------------------------
            monthly_review_setting = self.config.monthly_review_time
            if monthly_review_setting:
                try:
                    parts = monthly_review_setting.split()
                    if len(parts) == 2:
                        day_of_month, review_time = parts
                        if now.day == int(day_of_month) and now_str == review_time:
                            review_key = f"monthly_review_{now.strftime('%Y-%m')}"
                            if review_key not in self.notified_today:
                                threading.Thread(
                                    target=try_auto_generate_reports,
                                    args=(SETTINGS_PATH,),
                                    daemon=True,
                                ).start()
                                self.notified_today.add(review_key)
                except Exception:
                    pass

            # -----------------------------------------------------------------
            # Skip if no schedule today
            # -----------------------------------------------------------------
            if not today_schedule:
                time.sleep(20)
                continue

            # -----------------------------------------------------------------
            # Handle Start Events
            # -----------------------------------------------------------------
            if now_str in today_schedule and now_str not in self.notified_today:
                self._handle_event(now_str, today_schedule[now_str])

            # -----------------------------------------------------------------
            # Handle End Alarms
            # -----------------------------------------------------------------
            if (
                now_str in self.pending_end_alarms
                and now_str not in self.notified_today
            ):
                message = self.pending_end_alarms[now_str]
                self._trigger_alarm("结束提醒", message)
                self.notified_today.add(now_str)
                del self.pending_end_alarms[now_str]

            # -----------------------------------------------------------------
            # Midnight Reset
            # -----------------------------------------------------------------
            if now_str == "00:00":
                self.notified_today.clear()
                self.pending_end_alarms.clear()

            # Sleep before next check
            time.sleep(20)


# =============================================================================
# ENTRY POINT
# =============================================================================


def main() -> None:
    """
    Main entry point for the schedule runner.

    Loads configuration and starts the scheduling loop.
    This function runs forever until terminated.
    """
    from schedule_management import ODD_PATH, EVEN_PATH

    config = ScheduleConfig(SETTINGS_PATH)
    weekly = WeeklySchedule(ODD_PATH, EVEN_PATH)
    runner = ScheduleRunner(config, weekly)
    runner.run()


if __name__ == "__main__":
    main()
