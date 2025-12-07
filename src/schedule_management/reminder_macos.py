import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from schedule_management.report import auto_generate_reports
from schedule_management.utils import (
    add_minutes_to_time,
    alarm,
    get_week_parity,
    load_toml_file,
    play_sound,
    show_dialog,
)

from schedule_management import (
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


class ScheduleConfig:
    def __init__(self, settings_path: str):
        config = load_toml_file(settings_path)
        self.settings = config.get("settings", {})
        self.time_blocks = config.get("time_blocks", {})
        self.time_points = config.get("time_points", {})
        self.tasks = config.get("tasks", {})
        self.paths = config.get("paths", {})

    @property
    def sound_file(self) -> str:
        return self.settings.get("sound_file", "/System/Library/Sounds/Ping.aiff")

    @property
    def alarm_interval(self) -> int:
        return self.settings.get("alarm_interval", 5)

    @property
    def max_alarm_duration(self) -> int:
        return self.settings.get("max_alarm_duration", 300)

    def should_skip_today(self) -> bool:
        skip_days = self.settings.get("skip_days", [])
        if not skip_days:
            return False
        current_weekday = datetime.now().strftime("%A").lower()
        return current_weekday in skip_days

    @property
    def daily_summary_time(self) -> str:
        return self.tasks.get("daily_summary", "22:00")

    @property
    def weekly_review_time(self) -> str:
        return self.tasks.get("weekly_review", "")

    @property
    def monthly_review_time(self) -> str:
        return self.tasks.get("monthly_review", "")

    @property
    def daily_urgent_times(self) -> list[str]:
        return self.tasks.get("daily_urgency", self.tasks.get("daily_urgent", []))

    @property
    def config_dir(self) -> str:
        return self.paths.get("config_dir", "config")

    @property
    def tasks_path(self) -> str:
        return self.paths.get("tasks_path", "tasks.json")

    @property
    def log_path(self) -> str:
        log_path = self.paths.get("log_path", "~/.schedule_management/task/tasks.log")
        # Expand ~ or $HOME if present
        if "~" in log_path or "$HOME" in log_path:
            return Path(log_path).expanduser()
        return log_path

    @property
    def record_path(self) -> str:
        return self.paths.get("record_path", "task/record.json")


class WeeklySchedule:
    def __init__(self, odd_path: str, even_path: str):
        self.odd_data = load_toml_file(odd_path)
        self.even_data = load_toml_file(even_path)

    def get_schedule_for_parity(self, parity: str) -> dict:
        return self.odd_data if parity == "odd" else self.even_data

    def get_today_schedule(self, config: ScheduleConfig) -> dict:
        if config.should_skip_today():
            return {}

        now = datetime.now()
        weekday = now.strftime("%A").lower()
        parity = get_week_parity()

        schedule_data = self.get_schedule_for_parity(parity)

        common = schedule_data.get("common", {})
        day_specific = schedule_data.get(weekday, {})
        return {**common, **day_specific}


def load_task_log() -> list[dict[str, Any]]:
    """Load task log from the JSON file."""

    try:
        with open(TASK_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def get_today_completed_tasks() -> list[dict[str, Any]]:
    """Get tasks that were completed (deleted) today."""
    task_log = load_task_log()
    today = datetime.now().strftime("%Y-%m-%d")

    completed_tasks = []
    for entry in task_log:
        if entry.get("action") == "deleted":
            # Parse timestamp and check if it's today
            try:
                timestamp = entry.get("timestamp", "")
                entry_date = timestamp.split("T")[0] if "T" in timestamp else ""
                if entry_date == today:
                    task_info = entry.get("task", {})
                    completed_tasks.append(task_info)
            except Exception:
                continue

    return completed_tasks


def show_daily_summary_popup():
    """Show a popup window with today's completed tasks."""
    completed_tasks = get_today_completed_tasks()

    if not completed_tasks:
        summary_message = "📋 今日完成任务\n\n✨ 今天没有完成的任务哦，明天继续加油！"
    else:
        # Sort tasks by priority (descending)
        sorted_tasks = sorted(
            completed_tasks, key=lambda x: x.get("priority", 0), reverse=True
        )

        task_lines = []
        for i, task in enumerate(sorted_tasks, 1):
            description = task.get("description", "未知任务")
            priority = task.get("priority", 0)
            task_lines.append(f"{i}. {description} (优先级: {priority})")

        summary_message = (
            f"📋 今日完成任务总结\n\n🎉 今天完成了 {len(sorted_tasks)} 个任务：\n\n"
            + "\n".join(task_lines)
        )

    # Play a sound and show the dialog
    try:
        config = ScheduleConfig(SETTINGS_PATH)
        play_sound(config.sound_file)
    except Exception:
        pass  # Ignore sound errors

    show_dialog(summary_message)


def try_auto_generate_reports(settings_path: str):
    """Generate scheduled reports once using settings.toml."""
    try:
        generated = auto_generate_reports(settings_path)
        if generated:
            for span, pdf_path in generated.items():
                print(f"📊 Generated {span} report at {pdf_path}")
    except FileNotFoundError:
        print(f"⚠️  settings.toml not found for auto reports: {settings_path}")
    except Exception as exc:
        print(f"⚠️  Auto report generation skipped: {exc}")


class ScheduleRunner:
    def __init__(self, config: ScheduleConfig, weekly_schedule: WeeklySchedule):
        self.config = config
        self.weekly_schedule = weekly_schedule
        self.notified_today = set()
        self.pending_end_alarms = {}  # {end_time_str: message}

    def _trigger_alarm(self, title: str, message: str, sound: str = None):
        sound_file = sound if sound else self.config.sound_file
        if sound and "/" not in sound and not sound.endswith(".aiff"):
            sound_file = f"/System/Library/Sounds/{sound}.aiff"

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

    def _handle_event(self, time_str: str, event: Any):
        if isinstance(event, str):
            if event in self.config.time_blocks:
                # It's a time block (e.g., "pomodoro")
                self._start_time_block(time_str, event, event)
            else:
                # It's either a time_point key OR a direct message
                if event in self.config.time_points:
                    message = self.config.time_points[event]
                else:
                    # Treat the string itself as the message
                    message = event
                self._trigger_alarm("提醒", message)
                self.notified_today.add(time_str)
        elif isinstance(event, dict) and "block" in event:
            block_type = event["block"]
            title = event.get("title", block_type)
            if block_type in self.config.time_blocks:
                self._start_time_block(time_str, block_type, title)
            else:
                print(f"Warning: Unknown block type '{block_type}' at {time_str}")

    def _start_time_block(self, start_time: str, block_type: str, title: str):
        duration = self.config.time_blocks[block_type]
        end_time_str = add_minutes_to_time(start_time, duration)
        start_message = f"{title} ⏱️ ({duration}min)"
        self._trigger_alarm("开始", start_message)
        self.notified_today.add(start_time)
        end_message = f"{title} 结束！休息一下 🎉"
        self.pending_end_alarms[end_time_str] = end_message

    def _get_unfinished_urgent_tasks(self) -> list[dict[str, Any]]:
        try:
            with open(TASKS_PATH, "r", encoding="utf-8") as f:
                tasks = json.load(f)
            # Filter for tasks that are unfinished (in tasks.json) AND urgency > 7
            return [t for t in tasks if t.get("priority", 0) > 7]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _check_urgent_tasks(self):
        urgent_tasks = self._get_unfinished_urgent_tasks()
        if urgent_tasks:
            count = len(urgent_tasks)
            message = f"🔥 {count} Urgent Tasks Pending!"
            self._trigger_alarm("Today's Urgent Tasks", message, sound="Glass")

    def run(self):
        while True:
            now = datetime.now()
            now_str = now.strftime("%H:%M")
            today_schedule = self.weekly_schedule.get_today_schedule(self.config)
            # Handle daily summary time
            if (
                now_str == self.config.daily_summary_time
                and now_str not in self.notified_today
                and not self.config.should_skip_today()
            ):
                threading.Thread(target=show_daily_summary_popup, daemon=True).start()
                self.notified_today.add(now_str)

            # Handle daily urgent tasks check
            if not self.config.should_skip_today():
                for urgent_time in self.config.daily_urgent_times:
                    if now_str == urgent_time and now_str not in self.notified_today:
                        self._check_urgent_tasks()
                        self.notified_today.add(now_str)

            # Handle weekly review time
            weekly_review_setting = self.config.weekly_review_time
            if weekly_review_setting:
                try:
                    # Parse the weekly review setting (format: "sunday 20:00")
                    parts = weekly_review_setting.split()
                    if len(parts) == 2:
                        day_of_week, review_time = parts
                        if (
                            now.strftime("%A").lower() == day_of_week.lower()
                            and now_str == review_time
                        ):
                            if (
                                f"weekly_review_{now.strftime('%Y-%m-%d')}"
                                not in self.notified_today
                            ):
                                threading.Thread(
                                    target=try_auto_generate_reports,
                                    args=(SETTINGS_PATH,),
                                    daemon=True,
                                ).start()
                                self.notified_today.add(
                                    f"weekly_review_{now.strftime('%Y-%m-%d')}"
                                )
                except Exception:
                    pass  # Ignore parsing errors

            # Handle monthly review time
            monthly_review_setting = self.config.monthly_review_time
            if monthly_review_setting:
                try:
                    # Parse the monthly review setting (format: "1 20:00")
                    parts = monthly_review_setting.split()
                    if len(parts) == 2:
                        day_of_month, review_time = parts
                        if now.day == int(day_of_month) and now_str == review_time:
                            if (
                                f"monthly_review_{now.strftime('%Y-%m')}"
                                not in self.notified_today
                            ):
                                threading.Thread(
                                    target=try_auto_generate_reports,
                                    args=(SETTINGS_PATH,),
                                    daemon=True,
                                ).start()
                                self.notified_today.add(
                                    f"monthly_review_{now.strftime('%Y-%m')}"
                                )
                except Exception:
                    pass  # Ignore parsing errors

            if not today_schedule:
                time.sleep(20)
                continue

            # Handle start events
            if now_str in today_schedule and now_str not in self.notified_today:
                self._handle_event(now_str, today_schedule[now_str])

            # Handle end alarms
            if (
                now_str in self.pending_end_alarms
                and now_str not in self.notified_today
            ):
                message = self.pending_end_alarms[now_str]
                self._trigger_alarm("结束提醒", message)
                self.notified_today.add(now_str)
                del self.pending_end_alarms[now_str]

            # Reset at midnight
            if now_str == "00:00":
                self.notified_today.clear()
                self.pending_end_alarms.clear()

            time.sleep(20)


def main():
    config = ScheduleConfig(SETTINGS_PATH)
    weekly = WeeklySchedule(ODD_PATH, EVEN_PATH)
    runner = ScheduleRunner(config, weekly)
    runner.run()


if __name__ == "__main__":
    main()
