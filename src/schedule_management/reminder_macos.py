import time
import os
import json
from datetime import datetime, timezone
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
from typing import Any, Optional
from schedule_management.utils import (
    load_toml_file,
    alarm,
    get_week_parity,
    add_minutes_to_time,
    show_dialog,
    play_sound,
)


class ScheduleConfig:
    def __init__(self, settings_path: str):
        config = load_toml_file(settings_path)
        self.settings = config.get("settings", {})
        self.time_blocks = config.get("time_blocks", {})
        self.time_points = config.get("time_points", {})
        self.tasks = config.get("tasks", {})

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


class ScheduleVisualizer:
    COLORS = {
        "pomodoro": "#FF6B6B",
        "long_break": "#4ECDC4",
        "napping": "#45B7D1",
        "meeting": "#96CEB4",
        "exercise": "#FFEAA7",
        "lunch": "#DDA0DD",
        "summary_time": "#FFB347",
        "go_to_bed": "#9370DB",
        "other": "#D3D3D3",
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

    def _create_chart(self, ax, schedule_data: dict, title: str):
        used_activities = set()

        for day_idx, day in enumerate(self.DAYS_ORDER):
            day_schedule = {}
            if "common" in schedule_data:
                day_schedule.update(schedule_data["common"])
            if day in schedule_data:
                day_schedule.update(schedule_data[day])

            for time_str, activity in day_schedule.items():
                activity_name = self._extract_activity_name(activity)
                used_activities.add(activity_name)

                time_parts = time_str.split(":")
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                time_decimal = hour + minute / 60.0

                if activity_name in self.config.time_blocks:
                    duration_minutes = self.config.time_blocks[activity_name]
                    duration_hours = duration_minutes / 60.0
                    end_time = time_decimal + duration_hours
                    label = f"{activity_name}\n{time_str}\n({duration_minutes}min)"
                elif activity_name in self.config.time_points:
                    duration_hours = 0.1
                    end_time = time_decimal + duration_hours
                    label = f"{activity_name}\n{time_str}"
                else:
                    duration_hours = 0.1
                    end_time = time_decimal + duration_hours
                    label = f"{activity_name}\n{time_str}"

                color = self.COLORS.get(activity_name, self.COLORS["other"])
                rect = patches.Rectangle(
                    (day_idx, time_decimal),
                    0.8,
                    duration_hours,
                    linewidth=1,
                    edgecolor="black",
                    facecolor=color,
                    alpha=0.7,
                )
                ax.add_patch(rect)

                ax.text(
                    day_idx + 0.4,
                    time_decimal + duration_hours / 2,
                    label,
                    ha="center",
                    va="center",
                    fontsize=8,
                    weight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8),
                )

        ax.set_xlim(-0.5, len(self.DAYS_ORDER) - 0.5)
        ax.set_ylim(24, 6)
        ax.set_xticks(range(len(self.DAYS_ORDER)))
        ax.set_xticklabels([d.capitalize() for d in self.DAYS_ORDER])

        hour_ticks = list(range(6, 25))
        ax.set_yticks(hour_ticks)
        ax.set_yticklabels([f"{h:02d}:00" for h in hour_ticks])
        ax.grid(True, alpha=0.3)
        ax.set_title(title, fontsize=16, weight="bold", pad=20)
        ax.set_xlabel("Days of the Week", fontsize=12, weight="bold")
        ax.set_ylabel("Time of Day", fontsize=12, weight="bold")

        legend_elements = [
            patches.Patch(color=self.COLORS.get(act, self.COLORS["other"]), label=act)
            for act in sorted(used_activities)
        ]
        ax.legend(handles=legend_elements, loc="center left", bbox_to_anchor=(1, 0.5))

    def visualize(self):
        import platform

        if platform.system() == "Windows":
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        else:
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")

        pdf_filename = os.path.join(desktop_path, "schedule_visualization.pdf")

        with PdfPages(pdf_filename) as pdf:
            # Create first page: Odd Week Schedule
            fig1, ax1 = plt.subplots(figsize=(16, 10))
            self._create_chart(ax1, self.odd_schedule, "Odd Week Schedule")
            plt.tight_layout()
            pdf.savefig(fig1, dpi=300, bbox_inches="tight")
            plt.close(fig1)

            # Create second page: Even Week Schedule
            fig2, ax2 = plt.subplots(figsize=(16, 10))
            self._create_chart(ax2, self.even_schedule, "Even Week Schedule")
            plt.tight_layout()
            pdf.savefig(fig2, dpi=300, bbox_inches="tight")
            plt.close(fig2)

        print(f"Schedule visualization saved as '{pdf_filename}'")
        print("\nSchedule visualization complete!")
        print("Generated file:")
        print("- schedule_visualization.pdf (on Desktop)")
        print("  - Page 1: Odd Week Schedule")
        print("  - Page 2: Even Week Schedule")


def load_task_log() -> list[dict[str, Any]]:
    """Load task log from the JSON file."""
    log_path = os.getenv("REMINDER_LOG_PATH")
    if not log_path or not os.path.exists(log_path):
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
    sound_file = os.getenv("REMINDER_CONFIG_DIR", "config") + "/settings.toml"
    try:
        config = ScheduleConfig(sound_file)
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
    import sys

    config_dir = os.getenv("REMINDER_CONFIG_DIR", "config")
    print(f"Using config directory: {config_dir}")
    settings_path = f"{config_dir}/settings.toml"
    odd_path = f"{config_dir}/odd_weeks.toml"
    even_path = f"{config_dir}/even_weeks.toml"

    config = ScheduleConfig(settings_path)
    weekly = WeeklySchedule(odd_path, even_path)
    if len(sys.argv) > 1 and sys.argv[1] == "--view":
        visualizer = ScheduleVisualizer(config, weekly.odd_data, weekly.even_data)
        visualizer.visualize()
    else:
        runner = ScheduleRunner(config, weekly)
        runner.run()


if __name__ == "__main__":
    main()
