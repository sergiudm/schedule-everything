# Implementation Plan: Sequential Habit Tracking

## Objective
Change the habit tracking mechanism from a single checklist ("pop all at once") to a sequential series of questions ("one by one"). Improve the UI to look "more descent" using native macOS dialogs with clear formatting.

## Analysis
- **Current Behavior**: Uses `choose from list` (via `choose_multiple` in `utils.py`) to show all habits in one window.
- **Target Behavior**: Iterate through habits and ask yes/no questions for each.
- **UI Improvement**: Use `display dialog` with the "note" icon (or similar) and distinct buttons for "Yes", "No", and "Stop".

## Proposed Changes

### 1. `src/schedule_management/utils.py`
- Add a new helper function `ask_yes_no(question: str, title: str) -> bool | None`.
- **macOS Implementation**:
  - Use `display dialog`.
  - **Prompt**: The habit question (e.g., "Did you read today?").
  - **Title**: "Habit Tracker (X/Y)" to show progress.
  - **Buttons**: `{"Stop", "No", "Yes"}`.
  - **Default Button**: "Yes".
  - **Cancel Button**: "Stop".
  - **Icon**: `note` (Standard, clean icon).
  - **Return**:
    - `True` for "Yes".
    - `False` for "No".
    - `None` for "Stop" (Cancel).

### 2. `src/schedule_management/reminder_macos.py`
- Modify `show_habit_tracking_popup(now)`:
  - Load habits and sort them.
  - Initialize `completed_ids = []`.
  - Iterate through the sorted habits.
  - For each habit:
    - Construct a progress title (e.g., "Habit 1 of 5").
    - Call `ask_yes_no` with the habit question.
    - If result is `True`: Add habit ID to `completed_ids`.
    - If result is `False`: Continue to next.
    - If result is `None` (Stop): Break the loop early (saving completed ones so far).
  - Save the record of completed habits.

### 3. `src/schedule_management/reminder.py`
- Modify `_prompt_completed_habits(habits)`:
  - Implement the same sequential logic as above to ensure the CLI command `reminder track` follows the same flow when in interactive mode.
  - Reuse the `ask_yes_no` utility.

## Code Mode Plan
1.  **Update `src/schedule_management/utils.py`**:
    - Add `ask_yes_no_macos`.
    - Update `ask_yes_no` dispatcher.

2.  **Update `src/schedule_management/reminder_macos.py`**:
    - Rewrite `show_habit_tracking_popup` to loop through habits using `ask_yes_no`.

3.  **Update `src/schedule_management/reminder.py`**:
    - Rewrite `_prompt_completed_habits` to use the sequential loop.

4.  **Verification**:
    - Verify that closing the dialog or clicking "Stop" cleanly exits.
    - Verify that "Yes" and "No" are recorded correctly.
