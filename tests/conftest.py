"""
Test configuration for the schedule management system tests.
This file defines test-specific paths that mirror the elegant path management
approach used in the src directory.
"""

import os
from pathlib import Path

# Define the test config directory
TEST_CONFIG_DIR = Path(__file__).parent / "config"

# Define test-specific paths that mirror the src structure
TEST_SETTINGS_PATH = TEST_CONFIG_DIR / "settings.toml"
TEST_ODD_PATH = TEST_CONFIG_DIR / "odd_weeks.toml"
TEST_EVEN_PATH = TEST_CONFIG_DIR / "even_weeks.toml"
TEST_DDL_PATH = TEST_CONFIG_DIR / "ddl.json"
TEST_HABIT_PATH = TEST_CONFIG_DIR / "habits.toml"
TEST_TASKS_PATH = TEST_CONFIG_DIR / "tasks" / "tasks.json"
TEST_TASK_LOG_PATH = TEST_CONFIG_DIR / "tasks" / "tasks.log"
TEST_RECORD_PATH = TEST_CONFIG_DIR / "tasks" / "record.json"

# Export all test paths for easy import in test files
__all__ = [
    "TEST_CONFIG_DIR",
    "TEST_SETTINGS_PATH",
    "TEST_ODD_PATH",
    "TEST_EVEN_PATH",
    "TEST_DDL_PATH",
    "TEST_HABIT_PATH",
    "TEST_TASKS_PATH",
    "TEST_TASK_LOG_PATH",
    "TEST_RECORD_PATH",
]
