"""
Habit Commands - CLI commands for habit tracking.

This module provides CLI command handlers for habit tracking:
- track_habits: Record completed habits for today

Habits are configured in a TOML file and tracked daily in a JSON
records file. The tracking can be done via:
- GUI prompt dialogs (default on macOS)
- Command line arguments
- CLI fallback prompt

Example Usage (via CLI):
    $ rmd track              # Opens GUI prompt for habits
    $ rmd track 1 2 3        # Mark habits 1, 2, 3 as done
"""

import re
import sys
from datetime import date, datetime, timezone

from schedule_management.data import (
    load_habits,
    load_habit_records,
    save_habit_records,
)
from schedule_management.platform import choose_multiple, ask_yes_no


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# Regex to parse habit choice format from GUI: "[habit_id] description"
_HABIT_CHOICE_RE = re.compile(r"^\[(?P<habit_id>[^\]]+)\]\s+")


def _habit_sort_key(habit_id: str) -> tuple[int, str]:
    """
    Generate a sort key for habit IDs.

    Numeric IDs sort before string IDs, and numerically within groups.

    Args:
        habit_id: The habit ID to sort

    Returns:
        Tuple (type_order, padded_id) for sorting
    """
    if habit_id.isdigit():
        return (0, f"{int(habit_id):09d}")
    return (1, habit_id)


def _habit_question(description: str) -> str:
    """
    Convert a habit description into a yes/no question.

    Examples:
        'Exercise' -> 'Did you exercise today?'
        'Did you read?' -> 'Did you read?'
        'Meditate' -> 'Did you meditate today?'

    Args:
        description: The habit description

    Returns:
        A question string
    """
    text = description.strip()
    if not text:
        return "Did you complete this habit today?"
    if text.endswith("?"):
        return text
    if text.lower().startswith("did you "):
        return f"{text}?"
    if text[0].isalpha():
        text = text[0].lower() + text[1:]
    return f"Did you {text} today?"


def _prompt_completed_habits(habits: dict[str, str]) -> list[str] | None:
    """
    Prompt for completed habits using GUI Yes/No dialogs.

    Shows a dialog for each habit, asking if it was completed today.

    Args:
        habits: Dict mapping habit ID to description

    Returns:
        List of completed habit IDs, or None if cancelled
    """
    sorted_habits = sorted(habits.items(), key=lambda item: _habit_sort_key(item[0]))

    completed_ids: list[str] = []
    total_habits = len(sorted_habits)
    cancelled = False

    for i, (habit_id, description) in enumerate(sorted_habits, 1):
        question = _habit_question(description)
        title = f"Habit Tracker ({i}/{total_habits})"

        result = ask_yes_no(question, title)

        if result is None:
            # User clicked Stop
            cancelled = True
            break

        if result:
            completed_ids.append(habit_id)

    if cancelled and not completed_ids:
        return None

    return completed_ids


def _prompt_completed_habits_cli(habits: dict[str, str]) -> list[str] | None:
    """
    Prompt for completed habits using CLI input.

    Falls back to this when GUI is not available.

    Args:
        habits: Dict mapping habit ID to description

    Returns:
        List of completed habit IDs, or None if not a TTY
    """
    if not sys.stdin.isatty():
        return None

    print("Habits for today:")
    for habit_id, description in sorted(
        habits.items(), key=lambda item: _habit_sort_key(item[0])
    ):
        print(f"  [{habit_id}] {_habit_question(description)}")

    raw = input(
        "Enter completed habit IDs (space-separated), or press Enter for none: "
    ).strip()
    if not raw:
        return []
    return raw.split()


# =============================================================================
# TRACK HABITS COMMAND
# =============================================================================


def track_habits(args) -> int:
    """
    Handle the 'track' command - record completed habits for today.

    Workflow:
    1. If habit IDs provided as args, use those
    2. Otherwise, try GUI prompts
    3. Fall back to CLI input

    Args:
        args: Namespace with optional 'habit_ids' (list of IDs)

    Returns:
        0 on success, 1 on error or cancellation

    Example:
        $ rmd track           # Opens GUI prompt
        $ rmd track 1 2 3     # Mark habits 1, 2, 3 as done

        Output:
        ✅ Recorded habit tracking for 2024-07-15
        Completed habits today: 3
          [1] Exercise
          [2] Read 30 mins
          [3] Meditate
    """
    habit_ids = getattr(args, "habit_ids", None) or []

    # Load habits configuration
    habits = load_habits()

    if not habits:
        print("❌ Error: No habits configured. Please create config/habits.toml")
        return 1

    # Get habit IDs if not provided
    if not habit_ids:
        # Try GUI prompt first
        habit_ids = _prompt_completed_habits(habits)

        if habit_ids is None:
            # Fall back to CLI
            habit_ids = _prompt_completed_habits_cli(habits)

        if habit_ids is None:
            print(
                "❌ Could not open a habit prompt window. Provide habit IDs, e.g. `rmd track 1 2`."
            )
            return 1

    # Validate habit IDs
    invalid_ids = []
    valid_habits = []

    for habit_id in habit_ids:
        habit_id_str = str(habit_id)
        if habit_id_str in habits:
            valid_habits.append(habit_id_str)
        else:
            invalid_ids.append(habit_id)

    if invalid_ids:
        print(f"⚠️  Warning: Invalid habit IDs: {', '.join(map(str, invalid_ids))}")
        print(f"Available habits: {', '.join(sorted(habits.keys()))}")
        if not valid_habits:
            return 1

    # Get today's date
    today = date.today().isoformat()

    # Load existing records
    records = load_habit_records()

    # Check for existing record today
    existing_record_index = None
    for i, record in enumerate(records):
        if record.get("date") == today:
            existing_record_index = i
            break

    # Create record for today
    completed_habits = {habit_id: habits[habit_id] for habit_id in valid_habits}

    new_record = {
        "date": today,
        "completed": completed_habits,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Update or add record
    if existing_record_index is not None:
        old_completed = records[existing_record_index].get("completed", {})
        records[existing_record_index] = new_record
        print(f"✅ Updated habit record for {today}")
        print(f"Previously completed: {len(old_completed)} habits")
    else:
        records.append(new_record)
        print(f"✅ Recorded habit tracking for {today}")

    print(f"Completed habits today: {len(completed_habits)}")
    for habit_id in sorted(valid_habits, key=_habit_sort_key):
        print(f"  [{habit_id}] {habits[habit_id]}")

    # Save records
    try:
        save_habit_records(records)
        return 0
    except Exception as e:
        print(f"❌ Error saving habit records: {e}")
        return 1
