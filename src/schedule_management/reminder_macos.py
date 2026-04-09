"""
Reminder macOS - Legacy compatibility module.

This module re-exports components from the new modular structure for
backward compatibility. New code should import directly from:
- schedule_management.config (ScheduleConfig, WeeklySchedule)
- schedule_management.runner (ScheduleRunner, main)
- schedule_management.popups (show_daily_summary, habit_tracking_popup)

DEPRECATED: Direct imports from reminder_macos.py are deprecated.
Migrate to the specific modules above.
"""

# =============================================================================
# Re-exports for backward compatibility
# =============================================================================

# Config classes
from schedule_management.config import (
    ScheduleConfig,
    WeeklySchedule,
    load_toml_file,
)

# Runner and main loop
from schedule_management.runner import (
    ScheduleRunner,
    try_auto_generate_reports,
    main,
)

# Popup functions
from schedule_management.popups import (
    show_daily_summary_popup as show_daily_summary,
    show_habit_tracking_popup as habit_tracking_popup,
)

__all__ = [
    # Config
    "ScheduleConfig",
    "WeeklySchedule",
    "load_toml_file",
    # Runner
    "ScheduleRunner",
    "try_auto_generate_reports",
    "main",
    # Popups
    "show_daily_summary",
    "habit_tracking_popup",
]


# Keep direct script execution working for installer-managed services that still
# invoke reminder_macos.py instead of the dedicated runner entry point.
if __name__ == "__main__":
    main()
