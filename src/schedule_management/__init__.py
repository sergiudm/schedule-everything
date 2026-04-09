from schedule_management.config_layout import DynamicPath, resolve_runtime_paths

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

CONFIG_DIR = DynamicPath(lambda: resolve_runtime_paths().active_config_dir)
SETTINGS_PATH = DynamicPath(lambda: resolve_runtime_paths().settings_path)
ODD_PATH = DynamicPath(lambda: resolve_runtime_paths().odd_path)
EVEN_PATH = DynamicPath(lambda: resolve_runtime_paths().even_path)
DDL_PATH = DynamicPath(lambda: resolve_runtime_paths().ddl_path)
HABIT_PATH = DynamicPath(lambda: resolve_runtime_paths().habit_path)
TASKS_PATH = DynamicPath(lambda: resolve_runtime_paths().tasks_path)
TASK_LOG_PATH = DynamicPath(lambda: resolve_runtime_paths().task_log_path)
RECORD_PATH = DynamicPath(lambda: resolve_runtime_paths().record_path)
PROCRASTINATE_PATH = DynamicPath(lambda: resolve_runtime_paths().procrastinate_path)


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
    "PROCRASTINATE_PATH",
]
