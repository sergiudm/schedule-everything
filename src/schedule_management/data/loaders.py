"""
Data Loaders - Functions for loading and saving data files.

This module provides functions for persistent storage operations:
- Tasks: JSON file with task list and priorities
- Task Log: JSON file tracking all task actions
- Deadlines: JSON file with deadline events
- Habits: TOML config and JSON records

All functions handle file errors gracefully and ensure parent
directories exist before writing.

Example Usage:
    >>> from schedule_management.data import load_tasks, save_tasks
    >>>
    >>> tasks = load_tasks()
    >>> tasks.append({'description': 'New task', 'priority': 5})
    >>> save_tasks(tasks)
"""

import json
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schedule_management import (
    TASKS_PATH,
    TASK_LOG_PATH,
    DDL_PATH,
    HABIT_PATH,
    RECORD_PATH,
)


# =============================================================================
# TASK MANAGEMENT
# =============================================================================


def load_tasks() -> list[dict[str, Any]]:
    """
    Load tasks from the JSON file.

    Returns:
        List of task dictionaries with 'description' and 'priority' keys.
        Returns empty list if file not found or invalid.

    Example:
        >>> tasks = load_tasks()
        >>> for task in tasks:
        ...     print(f"{task['description']} (priority: {task['priority']})")
    """
    try:
        with open(TASKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print("Error loading tasks file, starting with an empty task list.")
        return []


def save_tasks(tasks: list[dict[str, Any]]) -> None:
    """
    Save tasks to the JSON file.

    Creates parent directories if they don't exist.

    Args:
        tasks: List of task dictionaries to save

    Example:
        >>> tasks = [{'description': 'Study', 'priority': 8}]
        >>> save_tasks(tasks)
    """
    tasks_path = Path(TASKS_PATH)
    tasks_path.parent.mkdir(parents=True, exist_ok=True)

    with open(tasks_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)


# =============================================================================
# TASK LOG MANAGEMENT
# =============================================================================


def load_task_log() -> list[dict[str, Any]]:
    """
    Load task action log from the JSON file.

    The log tracks all task operations (added, updated, deleted)
    with timestamps for history and reporting.

    Returns:
        List of log entry dictionaries.
        Returns empty list if file not found or invalid.
    """
    try:
        with open(TASK_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_task_log(log_entries: list[dict[str, Any]]) -> None:
    """
    Save task action log to the JSON file.

    Creates parent directories if they don't exist.

    Args:
        log_entries: List of log entry dictionaries to save
    """
    log_path = Path(TASK_LOG_PATH)
    if not log_path:
        return

    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entries, f, indent=2, ensure_ascii=False)


def log_task_action(
    action: str, task: dict[str, Any], metadata: dict[str, Any] | None = None
) -> None:
    """
    Log a task action (added/updated/deleted) with timestamp.

    Appends a new entry to the task log with the action type,
    task details, and ISO timestamp.

    Args:
        action: Action type ('added', 'updated', 'deleted')
        task: Task dictionary that was affected
        metadata: Optional additional data (e.g., old_priority)

    Example:
        >>> task = {'description': 'Study', 'priority': 8}
        >>> log_task_action('added', task)
        >>> log_task_action('updated', task, {'old_priority': 5})
    """
    log_path = Path(TASK_LOG_PATH)
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


# =============================================================================
# DEADLINE MANAGEMENT
# =============================================================================


def load_deadlines() -> list[dict[str, Any]]:
    """
    Load deadlines from the JSON file.

    Returns:
        List of deadline dictionaries with 'event', 'deadline',
        and 'added' keys. Returns empty list if file not found.

    Example:
        >>> deadlines = load_deadlines()
        >>> for ddl in deadlines:
        ...     print(f"{ddl['event']}: {ddl['deadline']}")
    """
    try:
        with open(DDL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print("Error loading deadlines file, starting with an empty deadline list.")
        return []


def save_deadlines(deadlines: list[dict[str, Any]]) -> None:
    """
    Save deadlines to the JSON file.

    Creates parent directories if they don't exist.

    Args:
        deadlines: List of deadline dictionaries to save
    """
    ddl_path = Path(DDL_PATH)
    ddl_path.parent.mkdir(parents=True, exist_ok=True)

    with open(ddl_path, "w", encoding="utf-8") as f:
        json.dump(deadlines, f, indent=2, ensure_ascii=False)


# =============================================================================
# HABIT MANAGEMENT
# =============================================================================


def load_habits() -> dict[str, str]:
    """
    Load habits configuration from the TOML file.

    Supports two TOML formats:
    - {"exercise": 1} -> {"1": "exercise"}
    - {"1": "exercise"} -> {"1": "exercise"}

    Returns:
        Dict mapping habit ID (string) to habit description.
        Returns empty dict if file not found or invalid.

    Example:
        >>> habits = load_habits()
        >>> habits
        {'1': 'Exercise', '2': 'Read 30 mins', '3': 'Meditate'}
    """
    try:
        with open(HABIT_PATH, "rb") as f:
            data = tomllib.load(f)

            # Check for nested 'habits' section
            if "habits" in data:
                habits_data = data["habits"]
            else:
                habits_data = data

            # Normalize to string keys
            habits = {}
            for key, value in habits_data.items():
                # Support both formats
                if isinstance(value, int):
                    habits[str(value)] = key
                else:
                    habits[str(key)] = str(value)
            return habits
    except Exception as e:
        print(f"Error loading habits file: {e}")
        return {}


def load_habit_records() -> list[dict[str, Any]]:
    """
    Load habit tracking records from the JSON file.

    Returns:
        List of daily record dictionaries with 'date', 'completed',
        and 'timestamp' keys. Returns empty list if file not found.

    Example:
        >>> records = load_habit_records()
        >>> for record in records:
        ...     print(f"{record['date']}: {len(record['completed'])} habits")
    """
    record_path = Path(RECORD_PATH)
    if not record_path.exists():
        return []

    try:
        with open(record_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_habit_records(records: list[dict[str, Any]]) -> None:
    """
    Save habit tracking records to the JSON file.

    Creates parent directories if they don't exist.

    Args:
        records: List of daily record dictionaries to save
    """
    record_path = Path(RECORD_PATH)
    record_path.parent.mkdir(parents=True, exist_ok=True)

    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
