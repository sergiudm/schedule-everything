import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from schedule_management.utils import (
    add_minutes_to_time,
    alarm,
    get_week_parity,
    load_toml_file,
    play_sound,
    show_dialog,
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
        # Try to get log path from settings.toml first
        config_dir = os.getenv("REMINDER_CONFIG_DIR", "config")
        settings_path = f"{config_dir}/settings.toml"

        if Path(settings_path).exists():
            config = ScheduleConfig(settings_path)
            log_path = config.log_path
            # If path is relative, make it relative to config_dir
            log_path = Path(config.config_dir) / log_path
            # Expand ~ or $HOME if present
            if "~" in log_path or "$HOME" in log_path:
                log_path = Path(os.path.expandvars(log_path)).expanduser()
        else:
            # Fallback to environment variable
            log_path = os.getenv("REMINDER_LOG_PATH")
    except Exception:
        # Fallback to environment variable
        log_path = os.getenv("REMINDER_LOG_PATH")

    # If still no path, use default
    if not log_path:
        log_path = Path.home() / ".schedule_management" / "task" / "tasks.log"

    if not log_path.exists():
        print(f"Warning: Log file not found at {log_path}")
        return []

    try:
        with open(log_path, "r", encoding="utf-8") as f:
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
        # Try to get config from settings.toml first
        config_dir = os.getenv("REMINDER_CONFIG_DIR", "config")
        settings_path = f"{config_dir}/settings.toml"
        config = ScheduleConfig(settings_path)
        play_sound(config.sound_file)
    except Exception:
        pass  # Ignore sound errors

    show_dialog(summary_message)


class ScheduleRunner:
    def __init__(self, config: ScheduleConfig, weekly_schedule: WeeklySchedule):
        self.config = config
        self.weekly_schedule = weekly_schedule
        self.notified_today = set()
        self.pending_end_alarms = {}  # {end_time_str: message}

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
                alarm(
                    "提醒",
                    message,
                    self.config.sound_file,
                    self.config.alarm_interval,
                    self.config.max_alarm_duration,
                )
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
        alarm(
            "开始",
            start_message,
            self.config.sound_file,
            self.config.alarm_interval,
            self.config.max_alarm_duration,
        )
        self.notified_today.add(start_time)
        end_message = f"{title} 结束！休息一下 🎉"
        self.pending_end_alarms[end_time_str] = end_message

    def run(self):
        while True:
            now_str = datetime.now().strftime("%H:%M")
            today_schedule = self.weekly_schedule.get_today_schedule(self.config)

            # Handle daily summary time
            if (
                now_str == self.config.daily_summary_time
                and now_str not in self.notified_today
                and not self.config.should_skip_today()
            ):
                show_daily_summary_popup()
                self.notified_today.add(now_str)

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
                alarm(
                    "结束提醒",
                    message,
                    self.config.sound_file,
                    self.config.alarm_interval,
                    self.config.max_alarm_duration,
                )
                self.notified_today.add(now_str)
                del self.pending_end_alarms[now_str]

            # Reset at midnight
            if now_str == "00:00":
                self.notified_today.clear()
                self.pending_end_alarms.clear()

            time.sleep(20)


def main():
    try:
        # Try to get config from settings.toml first
        config = ScheduleConfig("config/settings.toml")
        config_dir = config.config_dir
        print(f"Using config directory from settings.toml: {config_dir}")
    except Exception:
        # Fallback to environment variable or default
        config_dir = os.getenv("REMINDER_CONFIG_DIR", "config")
        print(f"Using config directory: {config_dir}")

    settings_path = f"{config_dir}/settings.toml"
    odd_path = f"{config_dir}/odd_weeks.toml"
    even_path = f"{config_dir}/even_weeks.toml"

    config = ScheduleConfig(settings_path)
    weekly = WeeklySchedule(odd_path, even_path)
    runner = ScheduleRunner(config, weekly)
    runner.run()


if __name__ == "__main__":
    main()
