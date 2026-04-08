"""
Data Package - Data loading and persistence for the schedule management system.

This package provides functions to load and save various data files:
- Tasks: JSON file containing task list with priorities
- Task Log: JSON file tracking task actions (add/update/delete)
- Deadlines: JSON file containing deadline events
- Habits: TOML configuration and JSON records for habit tracking
"""

from schedule_management.data.loaders import (
    load_tasks,
    save_tasks,
    load_procrastinate_list,
    load_procrastinate_records,
    save_procrastinate_list,
    get_procrastinate_age_days,
    load_task_log,
    save_task_log,
    log_task_action,
    load_deadlines,
    save_deadlines,
    load_habits,
    load_habit_records,
    save_habit_records,
)

__all__ = [
    "load_tasks",
    "save_tasks",
    "load_procrastinate_list",
    "load_procrastinate_records",
    "save_procrastinate_list",
    "get_procrastinate_age_days",
    "load_task_log",
    "save_task_log",
    "log_task_action",
    "load_deadlines",
    "save_deadlines",
    "load_habits",
    "load_habit_records",
    "save_habit_records",
]
