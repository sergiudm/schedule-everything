"""
Popup Dialogs - Daily summary and habit tracking popup functions.

This module provides popup dialog functionality for the schedule system:
- Daily task summary popup (shows completed tasks)
- Habit tracking popup (prompts for habit completion)

These popups are triggered at configured times by the ScheduleRunner
and use native OS dialogs to display information and collect input.

Example Usage:
    >>> from schedule_management.popups import show_daily_summary_popup
    >>> show_daily_summary_popup()  # Shows today's completed tasks

    >>> from schedule_management.popups import show_habit_tracking_popup
    >>> success = show_habit_tracking_popup()  # Prompts for habits
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from schedule_management import (
    SETTINGS_PATH,
    HABIT_PATH,
    TASK_LOG_PATH,
    RECORD_PATH,
)
from schedule_management.platform import play_sound, show_dialog, ask_yes_no


# =============================================================================
# TASK LOG LOADING
# =============================================================================


def load_task_log() -> list[dict[str, Any]]:
    """
    Load task action log from the JSON file.

    Returns:
        List of task log entries (may be empty if file not found)
    """
    try:
        with open(TASK_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def get_today_completed_tasks() -> list[dict[str, Any]]:
    """
    Get tasks that were completed (deleted) today.

    Scans the task log for 'deleted' actions with today's date.
    Deleted tasks are considered completed in this system.

    Returns:
        List of task info dicts with 'description' and 'priority'
    """
    task_log = load_task_log()
    today = datetime.now().strftime("%Y-%m-%d")

    completed_tasks = []
    for entry in task_log:
        if entry.get("action") == "deleted":
            try:
                timestamp = entry.get("timestamp", "")
                entry_date = timestamp.split("T")[0] if "T" in timestamp else ""
                if entry_date == today:
                    task_info = entry.get("task", {})
                    completed_tasks.append(task_info)
            except Exception:
                continue

    return completed_tasks


# =============================================================================
# DAILY SUMMARY POPUP
# =============================================================================


def show_daily_summary_popup() -> None:
    """
    Show a popup window with today's completed tasks.

    Displays a native dialog listing all tasks completed today,
    sorted by priority. If no tasks were completed, shows an
    encouraging message.

    The popup also plays a notification sound to get attention.

    Example output:
        📋 今日完成任务总结
        🎉 今天完成了 3 个任务：
        1. Write documentation (优先级: 8)
        2. Fix bug (优先级: 5)
        3. Code review (优先级: 3)
    """
    completed_tasks = get_today_completed_tasks()

    if not completed_tasks:
        summary_message = "📋 今日完成任务\n\n✨ 今天没有完成的任务哦，明天继续加油！"
    else:
        # Sort by priority (highest first)
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

    # Play notification sound
    try:
        from schedule_management.config import ScheduleConfig

        config = ScheduleConfig(SETTINGS_PATH)
        play_sound(config.sound_file)
    except Exception:
        pass  # Ignore sound errors

    # Show the dialog
    show_dialog(summary_message)


# =============================================================================
# HABIT TRACKING
# =============================================================================


def _habit_sort_key(habit_id: str) -> tuple[int, str]:
    """
    Generate a sort key for habit IDs.

    Numeric IDs sort before string IDs, and numerically within each group.

    Args:
        habit_id: The habit ID to generate a key for

    Returns:
        Tuple for sorting (type_order, padded_id)
    """
    if habit_id.isdigit():
        return (0, f"{int(habit_id):09d}")
    return (1, habit_id)


def _habit_question(description: str) -> str:
    """
    Convert a habit description into a yes/no question.

    Transforms descriptions into natural questions:
    - 'Exercise' -> 'Did you exercise today?'
    - 'Did you read?' -> 'Did you read?'
    - 'Meditate for 10 mins' -> 'Did you meditate for 10 mins today?'

    Args:
        description: The habit description

    Returns:
        A question string
    """
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
    """
    Load habits configuration from TOML file.

    Supports two formats:
    - {"habit_name": 1} -> {"1": "habit_name"}
    - {"1": "habit_name"} -> {"1": "habit_name"}

    Returns:
        Dict mapping habit ID to habit description
    """
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
    """
    Load habit tracking records from JSON file.

    Returns:
        List of daily habit records
    """
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
    """
    Save habit tracking records to JSON file.

    Args:
        records: List of daily habit records to save
    """
    record_path = Path(RECORD_PATH)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    with open(record_path, "w", encoding="utf-8") as fp:
        json.dump(records, fp, indent=2, ensure_ascii=False)


def show_habit_tracking_popup(now: datetime | None = None) -> bool:
    """
    Prompt for today's habits one by one and save the record.

    Shows a series of Yes/No dialogs for each configured habit,
    then saves the completed habits to the record file.

    Args:
        now: Optional datetime to use (defaults to current time)

    Returns:
        True if habits were tracked successfully, False if cancelled

    Example:
        >>> success = show_habit_tracking_popup()
        >>> if success:
        ...     print('Habits recorded!')
    """
    habits = _load_habits()
    if not habits:
        return False

    now_dt = now or datetime.now()
    today = now_dt.strftime("%Y-%m-%d")

    # Sort habits for consistent order
    sorted_habits = sorted(habits.items(), key=lambda item: _habit_sort_key(item[0]))

    completed_ids = []
    total_habits = len(sorted_habits)
    cancelled = False

    # Ask about each habit
    for i, (habit_id, description) in enumerate(sorted_habits, 1):
        question = _habit_question(description)
        title = f"Habit Tracker ({i}/{total_habits})"

        result = ask_yes_no(question, title)

        if result is None:
            # User clicked Stop/Cancel
            cancelled = True
            break

        if result:
            completed_ids.append(habit_id)

    # If cancelled without tracking anything, don't save
    if cancelled and not completed_ids:
        return False

    # Build completed habits dict
    completed = {habit_id: habits[habit_id] for habit_id in completed_ids}

    # Load existing records and update/add today's entry
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
