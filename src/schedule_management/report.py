import json
import os
import tomllib
import calendar
from datetime import datetime, timedelta, date, time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.patches as patches

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from schedule_management import (
    CONFIG_DIR,
    SETTINGS_PATH,
    HABIT_PATH,
    RECORD_PATH,
    TASK_LOG_PATH,
)

WEEKDAY_ALIASES = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


class ReportGenerator:
    """
    Generates PDF reports for weekly and monthly summaries of tasks and habits.
    """

    def __init__(self, reports_path: str):
        self.reports_path = Path(os.path.expanduser(reports_path))
        self.reports_path.mkdir(parents=True, exist_ok=True)

    def _get_week_range(self, target_date: date) -> tuple[date, date]:
        """Return start (Monday) and end (Sunday) of the week for the target date."""
        start = target_date - timedelta(days=target_date.weekday())
        end = start + timedelta(days=6)
        return start, end

    def _get_month_range(self, target_date: date) -> tuple[date, date]:
        """Return start and end of the month for the target date."""
        start = target_date.replace(day=1)
        _, last_day = calendar.monthrange(target_date.year, target_date.month)
        end = target_date.replace(day=last_day)
        return start, end

    def _filter_tasks(
        self, task_log: List[Dict], start_date: date, end_date: date
    ) -> List[Dict]:
        """Filter completed (deleted) tasks within the date range."""
        completed_tasks = []
        # Convert dates to datetime for comparison (start of day to end of day)
        start_dt = datetime.combine(start_date, datetime.min.time()).replace(
            tzinfo=None
        )
        end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=None)

        for entry in task_log:
            if entry.get("action") == "deleted":
                # Parse timestamp
                ts_str = entry.get("timestamp")
                if ts_str:
                    try:
                        # Handle ISO format with timezone
                        ts = datetime.fromisoformat(ts_str)
                        # Remove timezone for comparison if needed, or ensure both are aware
                        # Assuming simple comparison:
                        if ts.tzinfo:
                            ts = ts.replace(tzinfo=None)

                        if start_dt <= ts <= end_dt:
                            completed_tasks.append(entry)
                    except ValueError:
                        continue
        return completed_tasks

    def _filter_habits(
        self, habit_records: List[Dict], start_date: date, end_date: date
    ) -> Dict[str, Dict]:
        """
        Filter habit records within the date range.
        Returns a dict mapping date string (YYYY-MM-DD) to the record for that day.
        """
        filtered_records = {}
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        for record in habit_records:
            record_date = record.get("date")
            if record_date and start_str <= record_date <= end_str:
                filtered_records[record_date] = record
        return filtered_records

    def _weekly_report_path(self, start_date: date, end_date: date) -> Path:
        return (
            self.reports_path
            / f"weekly_report_{start_date:%Y%m%d}_{end_date:%Y%m%d}.pdf"
        )

    def _monthly_report_path(self, month_start: date) -> Path:
        return self.reports_path / f"monthly_report_{month_start:%Y%m}.pdf"

    @staticmethod
    def _parse_weekly_schedule(schedule_value: str) -> Tuple[int, time]:
        if not schedule_value:
            raise ValueError("Weekly schedule value is empty")

        parts = schedule_value.strip().split()
        if len(parts) != 2:
            raise ValueError(
                "Weekly schedule must look like 'sunday 20:00' (weekday + time)."
            )

        weekday_token, time_token = parts
        weekday_idx = WEEKDAY_ALIASES.get(weekday_token.lower())
        if weekday_idx is None:
            raise ValueError(f"Unknown weekday '{weekday_token}' in weekly schedule")

        try:
            schedule_time = datetime.strptime(time_token, "%H:%M").time()
        except ValueError as exc:
            raise ValueError(f"Invalid weekly review time '{time_token}'") from exc

        return weekday_idx, schedule_time

    @staticmethod
    def _parse_monthly_schedule(schedule_value: str) -> Tuple[int, time]:
        if not schedule_value:
            raise ValueError("Monthly schedule value is empty")

        parts = schedule_value.strip().split()
        if len(parts) != 2:
            raise ValueError(
                "Monthly schedule must look like '1 20:00' (day-of-month + time)."
            )

        day_token, time_token = parts
        try:
            day_number = int(day_token)
        except ValueError as exc:
            raise ValueError(f"Invalid day '{day_token}' in monthly schedule") from exc

        if not 1 <= day_number <= 31:
            raise ValueError("Monthly review day must be between 1 and 31")

        try:
            schedule_time = datetime.strptime(time_token, "%H:%M").time()
        except ValueError as exc:
            raise ValueError(f"Invalid monthly review time '{time_token}'") from exc

        return day_number, schedule_time

    @staticmethod
    def _last_weekly_occurrence(
        now: datetime, weekday_idx: int, schedule_time: time
    ) -> datetime:
        days_since_target = (now.weekday() - weekday_idx) % 7
        candidate_date = now.date() - timedelta(days=days_since_target)
        occurrence = datetime.combine(candidate_date, schedule_time)
        if occurrence > now:
            occurrence -= timedelta(days=7)
        return occurrence

    @staticmethod
    def _last_monthly_occurrence(
        now: datetime, day_number: int, schedule_time: time
    ) -> datetime:
        year, month = now.year, now.month
        day_in_month = min(day_number, calendar.monthrange(year, month)[1])
        candidate_date = date(year, month, day_in_month)
        occurrence = datetime.combine(candidate_date, schedule_time)
        if occurrence > now:
            month -= 1
            if month == 0:
                month = 12
                year -= 1
            day_in_month = min(day_number, calendar.monthrange(year, month)[1])
            occurrence = datetime.combine(
                date(year, month, day_in_month), schedule_time
            )
        return occurrence

    def generate_due_reports(
        self,
        task_schedule_config: Dict,
        task_log: List[Dict],
        habit_records: List[Dict],
        habits_config: Dict,
        now: Optional[datetime] = None,
    ) -> Dict[str, Path]:
        """Generate weekly/monthly reports that are due per settings.toml."""

        if not MATPLOTLIB_AVAILABLE:
            print(
                "❌ matplotlib is not available. Please install it: pip install matplotlib"
            )
            return {}

        now = now or datetime.now()
        generated: Dict[str, Path] = {}
        schedule = task_schedule_config or {}

        weekly_value = schedule.get("weekly_review")
        if weekly_value:
            try:
                weekday_idx, weekly_time = self._parse_weekly_schedule(weekly_value)
                last_occurrence = self._last_weekly_occurrence(
                    now, weekday_idx, weekly_time
                )
                week_start, week_end = self._get_week_range(last_occurrence.date())
                target_path = self._weekly_report_path(week_start, week_end)
                if not target_path.exists():
                    self.generate_weekly_report(
                        task_log,
                        habit_records,
                        habits_config,
                        target_date=week_end,
                    )
                    generated["weekly"] = target_path
            except ValueError as exc:
                print(f"⚠️  Skipping weekly auto-report: {exc}")

        monthly_value = schedule.get("monthly_review")
        if monthly_value:
            try:
                day_number, monthly_time = self._parse_monthly_schedule(monthly_value)
                last_occurrence = self._last_monthly_occurrence(
                    now, day_number, monthly_time
                )
                target_date = last_occurrence.date() - timedelta(days=1)
                month_start, _ = self._get_month_range(target_date)
                target_path = self._monthly_report_path(month_start)
                if not target_path.exists():
                    self.generate_monthly_report(
                        task_log,
                        habit_records,
                        habits_config,
                        target_date=target_date,
                    )
                    generated["monthly"] = target_path
            except ValueError as exc:
                print(f"⚠️  Skipping monthly auto-report: {exc}")

        return generated

    def generate_weekly_report(
        self,
        task_log: List[Dict],
        habit_records: List[Dict],
        habits_config: Dict,
        target_date: date = None,
    ):
        if not MATPLOTLIB_AVAILABLE:
            print(
                "❌ matplotlib is not available. Please install it: pip install matplotlib"
            )
            return

        if target_date is None:
            target_date = date.today()

        start_date, end_date = self._get_week_range(target_date)
        completed_tasks = self._filter_tasks(task_log, start_date, end_date)
        filtered_habits = self._filter_habits(habit_records, start_date, end_date)

        filename = f"weekly_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        filepath = self.reports_path / filename

        with PdfPages(filepath) as pdf:
            # Page 1: Summary & Habits
            self._create_weekly_summary_page(
                pdf,
                start_date,
                end_date,
                completed_tasks,
                filtered_habits,
                habits_config,
            )

            # Page 2: Tasks List
            if completed_tasks:
                self._create_tasks_list_page(
                    pdf, completed_tasks, "Weekly Completed Tasks"
                )

        print(f"✅ Weekly report generated: {filepath}")

    def generate_monthly_report(
        self,
        task_log: List[Dict],
        habit_records: List[Dict],
        habits_config: Dict,
        target_date: date = None,
    ):
        if not MATPLOTLIB_AVAILABLE:
            print(
                "❌ matplotlib is not available. Please install it: pip install matplotlib"
            )
            return

        if target_date is None:
            target_date = date.today()

        start_date, end_date = self._get_month_range(target_date)
        completed_tasks = self._filter_tasks(task_log, start_date, end_date)
        filtered_habits = self._filter_habits(habit_records, start_date, end_date)

        filename = f"monthly_report_{start_date.strftime('%Y%m')}.pdf"
        filepath = self.reports_path / filename

        with PdfPages(filepath) as pdf:
            # Page 1: Summary & Habits Heatmap
            self._create_monthly_summary_page(
                pdf,
                start_date,
                end_date,
                completed_tasks,
                filtered_habits,
                habits_config,
            )

            # Page 2+: Tasks List
            if completed_tasks:
                self._create_tasks_list_page(
                    pdf, completed_tasks, "Monthly Completed Tasks"
                )

        print(f"✅ Monthly report generated: {filepath}")

    def _create_weekly_summary_page(
        self, pdf, start_date, end_date, tasks, habits_data, habits_config
    ):
        fig = plt.figure(figsize=(11.69, 8.27))  # A4 Landscape

        # Title
        plt.text(
            0.5,
            0.95,
            f"Weekly Report: {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}",
            ha="center",
            va="center",
            fontsize=20,
            weight="bold",
        )

        # Summary Stats
        plt.text(0.2, 0.85, f"Tasks Completed: {len(tasks)}", ha="center", fontsize=14)

        # Calculate habit completion rate
        total_habit_slots = len(habits_config) * 7
        completed_count = sum(len(r.get("completed", {})) for r in habits_data.values())
        rate = (
            (completed_count / total_habit_slots * 100) if total_habit_slots > 0 else 0
        )
        plt.text(
            0.8, 0.85, f"Habit Completion Rate: {rate:.1f}%", ha="center", fontsize=14
        )

        # Habits Table
        # Create a table: Rows = Habits, Cols = Days (Mon-Sun)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        habit_ids = sorted(habits_config.keys())

        # Grid settings
        margin_x = 0.1
        table_width = 0.8
        table_height = 0.6
        row_height = table_height / (len(habit_ids) + 1)
        col_width = table_width / (len(days) + 1)  # +1 for habit name column

        ax = plt.gca()
        ax.axis("off")

        # Draw headers
        # Habit Name Header
        plt.text(margin_x + col_width / 2, 0.75, "Habit", ha="center", weight="bold")

        # Day Headers
        for i, day in enumerate(days):
            x = margin_x + col_width + (i * col_width) + col_width / 2
            plt.text(x, 0.75, day, ha="center", weight="bold")

            # Date subheader
            current_day = start_date + timedelta(days=i)
            plt.text(
                x,
                0.73,
                current_day.strftime("%d"),
                ha="center",
                fontsize=8,
                color="gray",
            )

        # Draw Rows
        for i, habit_id in enumerate(habit_ids):
            y = 0.75 - ((i + 1) * row_height) - row_height / 2
            habit_name = habits_config[habit_id]

            # Habit Name
            plt.text(
                margin_x + 0.01, y, habit_name, ha="left", va="center", fontsize=10
            )

            # Checkboxes
            for j in range(7):
                current_day = start_date + timedelta(days=j)
                date_str = current_day.isoformat()

                x = margin_x + col_width + (j * col_width) + col_width / 2

                # Check if completed
                is_completed = False
                if date_str in habits_data:
                    if habit_id in habits_data[date_str].get("completed", {}):
                        is_completed = True

                # Draw circle/check
                if is_completed:
                    circle = patches.Circle((x, y), 0.02, color="#2ecc71", alpha=0.6)
                    ax.add_patch(circle)
                    plt.text(
                        x,
                        y,
                        "✓",
                        ha="center",
                        va="center",
                        color="white",
                        weight="bold",
                    )
                else:
                    circle = patches.Circle((x, y), 0.02, color="#ecf0f1", alpha=1.0)
                    ax.add_patch(circle)

        # Draw grid lines
        # Horizontal
        for i in range(len(habit_ids) + 2):
            y = 0.75 + row_height / 2 - (i * row_height)
            plt.plot(
                [margin_x, margin_x + table_width],
                [y, y],
                color="#bdc3c7",
                linewidth=0.5,
            )

        pdf.savefig(fig)
        plt.close()

    def _create_monthly_summary_page(
        self, pdf, start_date, end_date, tasks, habits_data, habits_config
    ):
        fig = plt.figure(figsize=(11.69, 8.27))

        plt.text(
            0.5,
            0.95,
            f"Monthly Report: {start_date.strftime('%B %Y')}",
            ha="center",
            va="center",
            fontsize=20,
            weight="bold",
        )

        # Summary Stats
        plt.text(0.2, 0.88, f"Tasks Completed: {len(tasks)}", ha="center", fontsize=14)

        days_in_month = (end_date - start_date).days + 1
        total_habit_slots = len(habits_config) * days_in_month
        completed_count = sum(len(r.get("completed", {})) for r in habits_data.values())
        rate = (
            (completed_count / total_habit_slots * 100) if total_habit_slots > 0 else 0
        )
        plt.text(
            0.8, 0.88, f"Habit Completion Rate: {rate:.1f}%", ha="center", fontsize=14
        )

        # Habits Heatmap (Simplified as a grid)
        habit_ids = sorted(habits_config.keys())

        ax = plt.gca()
        ax.axis("off")

        # We will draw a row for each habit, and columns for days 1-31
        margin_x = 0.05
        chart_width = 0.9
        chart_height = 0.6

        row_height = chart_height / (len(habit_ids) + 1)
        col_width = chart_width / (days_in_month + 1)  # +1 for label

        # Draw Days Header
        for d in range(days_in_month):
            day_num = d + 1
            x = (
                margin_x + col_width * 4 + (d * col_width) + col_width / 2
            )  # Offset for label
            if day_num % 2 != 0:  # Show every other day to save space
                plt.text(x, 0.80, str(day_num), ha="center", fontsize=6)

        # Draw Rows
        for i, habit_id in enumerate(habit_ids):
            y = 0.80 - ((i + 1) * row_height) - row_height / 2
            habit_name = habits_config[habit_id]

            # Habit Name
            plt.text(margin_x, y, habit_name, ha="left", va="center", fontsize=8)

            # Day blocks
            for d in range(days_in_month):
                current_day = start_date + timedelta(days=d)
                date_str = current_day.isoformat()

                x = margin_x + col_width * 4 + (d * col_width)

                is_completed = False
                if date_str in habits_data:
                    if habit_id in habits_data[date_str].get("completed", {}):
                        is_completed = True

                color = "#2ecc71" if is_completed else "#ecf0f1"
                rect = patches.Rectangle(
                    (x, y - row_height / 2 + 0.005),
                    col_width - 0.002,
                    row_height - 0.01,
                    facecolor=color,
                )
                ax.add_patch(rect)

        pdf.savefig(fig)
        plt.close()

    def _create_tasks_list_page(self, pdf, tasks, title):
        # Pagination for tasks
        tasks_per_page = 20
        total_pages = (len(tasks) + tasks_per_page - 1) // tasks_per_page

        # Sort tasks by completion time (timestamp)
        sorted_tasks = sorted(tasks, key=lambda x: x.get("timestamp", ""), reverse=True)

        for page in range(total_pages):
            fig = plt.figure(figsize=(8.27, 11.69))  # A4 Portrait
            ax = plt.gca()
            ax.axis("off")

            plt.text(
                0.5,
                0.95,
                f"{title} (Page {page + 1}/{total_pages})",
                ha="center",
                va="center",
                fontsize=16,
                weight="bold",
            )

            start_idx = page * tasks_per_page
            end_idx = min(start_idx + tasks_per_page, len(sorted_tasks))
            page_tasks = sorted_tasks[start_idx:end_idx]

            y_start = 0.85
            line_height = 0.04

            # Header
            plt.text(0.1, y_start, "Date", weight="bold", fontsize=10)
            plt.text(0.3, y_start, "Task", weight="bold", fontsize=10)
            plt.text(0.8, y_start, "Priority", weight="bold", fontsize=10)

            plt.plot(
                [0.05, 0.95],
                [y_start - 0.01, y_start - 0.01],
                color="black",
                linewidth=1,
            )

            for i, task_entry in enumerate(page_tasks):
                y = y_start - 0.05 - (i * line_height)

                # Parse timestamp
                ts_str = task_entry.get("timestamp", "")
                try:
                    dt = datetime.fromisoformat(ts_str)
                    date_display = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    date_display = ts_str

                task_details = task_entry.get("task", {})
                desc = task_details.get("description", "Unknown")
                prio = task_details.get("priority", "-")

                plt.text(0.1, y, date_display, fontsize=9)
                plt.text(0.3, y, desc, fontsize=9)
                plt.text(0.8, y, str(prio), fontsize=9)

                # Light separator
                plt.plot(
                    [0.05, 0.95], [y - 0.01, y - 0.01], color="#ecf0f1", linewidth=0.5
                )

            pdf.savefig(fig)
            plt.close()


def _expand_path(raw_value: str, base_dir: Path) -> Path:
    expanded = Path(os.path.expandvars(str(raw_value))).expanduser()
    if expanded.is_absolute():
        return expanded
    return (base_dir / expanded).resolve()


def _load_settings(settings_file: Path) -> Dict:
    with open(settings_file, "rb") as fp:
        return tomllib.load(fp)


def _load_json_file(path: Path) -> List[Dict]:
    if not path.exists():
        print(f"⚠️  Data file not found: {path}")
        return []
    try:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        print(f"⚠️  Could not read {path}: {exc}")
        return []


def _load_habits_config(habits_path: Path) -> Dict[str, str]:
    if not habits_path.exists():
        print(f"⚠️  Habits configuration not found: {habits_path}")
        return {}
    try:
        with open(habits_path, "rb") as fp:
            data = tomllib.load(fp)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"⚠️  Could not load habits file {habits_path}: {exc}")
        return {}

    habits_section = data.get("habits", data)
    habits: Dict[str, str] = {}
    for key, value in habits_section.items():
        if isinstance(value, int):
            habits[str(value)] = str(key)
        else:
            habits[str(key)] = str(value)
    return habits


def auto_generate_reports(
    settings_path: Optional[str] = SETTINGS_PATH, now: Optional[datetime] = None
) -> Dict[str, Path]:
    """Auto-generate weekly/monthly reports using paths and schedule from settings.toml."""

    settings_data = _load_settings(settings_path)
    config_dir = CONFIG_DIR
    paths_section = settings_data.get("paths", {})

    reports_path = _expand_path(
        paths_section.get("reports_path", "~/Desktop/reports"), config_dir
    )

    task_log = _load_json_file(TASK_LOG_PATH)
    habit_records = _load_json_file(RECORD_PATH)
    habits_config = _load_habits_config(HABIT_PATH)

    generator = ReportGenerator(str(reports_path))
    return generator.generate_due_reports(
        settings_data.get("tasks", {}),
        task_log,
        habit_records,
        habits_config,
        now=now,
    )
