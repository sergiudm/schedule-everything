"""
Utility Functions - Legacy compatibility module.

This module re-exports utilities from the new modular structure for
backward compatibility. New code should import directly from:
- schedule_management.platform (platform detection, dialogs, sounds)
- schedule_management.time_utils (time parsing, week parity)
- schedule_management.visualizer (ScheduleVisualizer)

DEPRECATED: Direct imports from utils.py are deprecated.
Migrate to the specific modules above.
"""

# =============================================================================
# Re-exports for backward compatibility
# =============================================================================

# Platform utilities
from schedule_management.platform import (
    get_platform,
    play_sound,
    play_sound_macos,
    play_sound_linux,
    show_dialog,
    show_dialog_macos,
    show_dialog_linux,
    choose_multiple,
    ask_yes_no,
    ask_yes_no_macos,
)

# Time utilities
from schedule_management.time_utils import (
    get_week_parity,
    parse_time,
    time_to_str,
    add_minutes_to_time,
    alarm,
)

# Visualizer
from schedule_management.visualizer import ScheduleVisualizer, MATPLOTLIB_AVAILABLE

# Config loader (also available in config.py)
from schedule_management.config import load_toml_file

__all__ = [
    # Platform
    "get_platform",
    "play_sound",
    "play_sound_macos",
    "play_sound_linux",
    "show_dialog",
    "show_dialog_macos",
    "show_dialog_linux",
    "choose_multiple",
    "ask_yes_no",
    "ask_yes_no_macos",
    # Time
    "get_week_parity",
    "parse_time",
    "time_to_str",
    "add_minutes_to_time",
    "alarm",
    # Visualizer
    "ScheduleVisualizer",
    "MATPLOTLIB_AVAILABLE",
    # Config
    "load_toml_file",
]
