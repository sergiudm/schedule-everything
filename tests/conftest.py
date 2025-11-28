"""Shared fixtures and helpers for schedule management tests."""

import sys
from pathlib import Path

import pytest

# Ensure src/ is importable so fixtures can configure modules before tests run
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


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


def _apply_test_paths(module):
    """Mirror src path constants on the provided module for deterministic tests."""
    setattr(module, "CONFIG_DIR", str(TEST_CONFIG_DIR))
    setattr(module, "SETTINGS_PATH", str(TEST_SETTINGS_PATH))
    setattr(module, "ODD_PATH", str(TEST_ODD_PATH))
    setattr(module, "EVEN_PATH", str(TEST_EVEN_PATH))
    setattr(module, "DDL_PATH", str(TEST_DDL_PATH))
    setattr(module, "HABIT_PATH", str(TEST_HABIT_PATH))
    setattr(module, "TASKS_PATH", str(TEST_TASKS_PATH))
    setattr(module, "TASK_LOG_PATH", str(TEST_TASK_LOG_PATH))
    setattr(module, "RECORD_PATH", str(TEST_RECORD_PATH))


@pytest.fixture(autouse=True)
def configure_test_environment(monkeypatch):
    """Ensure every test runs against the dedicated config directory."""
    monkeypatch.setenv("REMINDER_CONFIG_DIR", str(TEST_CONFIG_DIR))

    # Update both the package constants and the modules that imported them
    import schedule_management
    import schedule_management.reminder as reminder_module
    import schedule_management.reminder_macos as reminder_macos_module

    _apply_test_paths(schedule_management)
    _apply_test_paths(reminder_module)
    _apply_test_paths(reminder_macos_module)


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
