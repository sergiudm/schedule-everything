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
    choose_multiple,
    ask_yes_no,
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
    def ddl_urgent_times(self) -> list[str]:
        return self.tasks.get("ddl_urgency", self.tasks.get("ddl_urgent", []))

    @property
    def habit_prompt_time(self) -> str:
        return self.tasks.get("habit_prompt", self.tasks.get("habit_tracking", ""))

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


def _habit_sort_key(habit_id: str) -> tuple[int, str]:
    if habit_id.isdigit():
        return (0, f"{int(habit_id):09d}")
    return (1, habit_id)


def _habit_question(description: str) -> str:
    text = str(description).strip()
    if not text:
        return "Did you complete this habit today?"
    if text.endswith("?"):
        return text
    if text.lower().startswith("did you "):
        return f"{text}?"
    if text[0].isalpha():
        text = text[0].lower() + text[1:]
    return f"Did you {text} today?"


def _load_habits() -> dict[str, str]:
    try:
        import tomllib

        with open(HABIT_PATH, "rb") as fp:
            data = tomllib.load(fp)
    except Exception:
        return {}

    habits_section = data.get("habits", data)
    habits: dict[str, str] = {}
    for key, value in habits_section.items():
        if isinstance(value, int):
            habits[str(value)] = str(key)
        else:
            habits[str(key)] = str(value)
    return habits


def _load_habit_records() -> list[dict[str, Any]]:
    record_path = Path(RECORD_PATH)
    if not record_path.exists():
        return []
    try:
        with open(record_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_habit_records(records: list[dict[str, Any]]) -> None:
    record_path = Path(RECORD_PATH)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    with open(record_path, "w", encoding="utf-8") as fp:
        json.dump(records, fp, indent=2, ensure_ascii=False)


def show_habit_tracking_popup(now: datetime | None = None) -> bool:
    """Prompt for today's habits one by one and save the record. Returns True if saved."""
    habits = _load_habits()
    if not habits:
        return False

    now_dt = now or datetime.now()
    today = now_dt.strftime("%Y-%m-%d")

    sorted_habits = sorted(habits.items(), key=lambda item: _habit_sort_key(item[0]))

    completed_ids = []
    total_habits = len(sorted_habits)
    cancelled = False

    for i, (habit_id, description) in enumerate(sorted_habits, 1):
        question = _habit_question(description)
        title = f"Habit Tracker ({i}/{total_habits})"

        result = ask_yes_no(question, title)

        if result is None:
            cancelled = True
            break

        if result:
            completed_ids.append(habit_id)

    # If user cancelled without tracking anything, don't save/overwrite
    if cancelled and not completed_ids:
        return False

    completed = {habit_id: habits[habit_id] for habit_id in completed_ids}

    records = _load_habit_records()
    existing_index = next(
        (i for i, r in enumerate(records) if r.get("date") == today), None
    )
    new_record = {
        "date": today,
        "completed": completed,
        "timestamp": now_dt.isoformat(),
    }

    if existing_index is None:
        records.append(new_record)
    else:
        records[existing_index] = new_record

    _save_habit_records(records)
    return True


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

    def _get_urgent_deadlines(self) -> list[dict[str, Any]]:
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

        urgent.sort(
            key=lambda d: (
                d.get("days_left", 0),
                d.get("deadline", ""),
                d.get("event", ""),
            )
        )
        return urgent

    def _check_urgent_tasks(self):
        urgent_tasks = self._get_unfinished_urgent_tasks()
        if urgent_tasks:
            task_descriptions = [
                f"{t.get('description', '未知任务')} (优先级: {t.get('priority', 0)})"
                for t in urgent_tasks
            ]
            message = (
                "🚨 今日紧急任务提醒 🚨\n\n" + "\n".join(task_descriptions)
            )
            self._trigger_alarm("Today's Urgent Tasks", message, sound="Glass")

    def _check_urgent_deadlines(self):
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

    def run(self):
        while True:
            now = datetime.now()
            now_str = now.strftime("%H:%M")
            today_schedule = self.weekly_schedule.get_today_schedule(self.config)
            # Handle daily summary time
            daily_summary_key = f"daily_summary_{now_str}"
            if (
                now_str == self.config.daily_summary_time
                and daily_summary_key not in self.notified_today
                and not self.config.should_skip_today()
            ):
                threading.Thread(target=show_daily_summary_popup, daemon=True).start()
                self.notified_today.add(daily_summary_key)

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

            # Handle daily urgent tasks check
            if not self.config.should_skip_today():
                for urgent_time in self.config.daily_urgent_times:
                    urgent_tasks_key = f"urgent_tasks_{urgent_time}"
                    if (
                        now_str == urgent_time
                        and urgent_tasks_key not in self.notified_today
                    ):
                        self._check_urgent_tasks()
                        self.notified_today.add(urgent_tasks_key)

                for urgent_time in self.config.ddl_urgent_times:
                    urgent_ddls_key = f"urgent_ddls_{urgent_time}"
                    if (
                        now_str == urgent_time
                        and urgent_ddls_key not in self.notified_today
                    ):
                        self._check_urgent_deadlines()
                        self.notified_today.add(urgent_ddls_key)

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
