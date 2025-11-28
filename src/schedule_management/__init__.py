import os

# ANSI color codes
COLORS = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "CYAN": "\033[96m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m",
    "RESET": "\033[0m",
}

CONFIG_DIR = os.getenv("REMINDER_CONFIG_DIR")
SETTINGS_PATH = f"{CONFIG_DIR}/settings.toml"
ODD_PATH = f"{CONFIG_DIR}/odd_weeks.toml"
EVEN_PATH = f"{CONFIG_DIR}/even_weeks.toml"
DDL_PATH = f"{CONFIG_DIR}/ddl.json"
HABIT_PATH = f"{CONFIG_DIR}/habits.toml"
TASKS_PATH = f"{CONFIG_DIR}/tasks/tasks.json"
TASK_LOG_PATH = f"{CONFIG_DIR}/tasks/tasks.log"
RECORD_PATH = f"{CONFIG_DIR}/tasks/record.json"


__all__ = [
    "COLORS",
    "CONFIG_DIR",
    "SETTINGS_PATH",
    "ODD_PATH",
    "EVEN_PATH",
    "DDL_PATH",
    "HABIT_PATH",
    "TASKS_PATH",
    "TASK_LOG_PATH",
    "RECORD_PATH",
]
