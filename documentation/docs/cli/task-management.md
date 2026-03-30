---
sidebar_position: 3
---

# Task Management Commands

Commands for managing your personal task list with importance levels and smart duplicate handling.

## add

Add a new task or update an existing one with an importance level.

### Syntax
```bash
reminder add "TASK_DESCRIPTION" PRIORITY_LEVEL
```

### Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `TASK_DESCRIPTION` | string | Description of the task (quoted if contains spaces) |
| `PRIORITY_LEVEL` | integer | Priority level from 1-10 (higher = more important) |

### Examples
```bash
# Add basic task
reminder add "Complete project proposal" 8

# Add task with spaces in description
reminder add "Review pull request #123" 5

# Add high-priority task
reminder add "Call dentist" 9
```

### Smart Duplicate Handling
If you add a task with the same description as an existing task, it updates the priority level instead of creating a duplicate:

```bash
# Initial task
reminder add "Buy groceries" 3

# Update importance (no duplicate created)
reminder add "Buy groceries" 6
```

## rm

Remove one or more tasks by description or ID.

### Syntax
```bash
reminder rm TASK_IDENTIFIER [TASK_IDENTIFIER...]
```

### Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `TASK_IDENTIFIER` | string/integer | Task description (quoted) or task ID number (from `reminder ls`) |

### Examples
```bash
# Remove by description
reminder rm "Buy groceries"

# Remove multiple tasks by description
reminder rm "Call dentist" "Organize desk"

# Remove by task ID
reminder rm 1 2 3
```

## ls

List all tasks sorted by urgency and importance (highest first).

### Syntax
```bash
reminder ls
```

### Examples
```bash
# Basic task list
reminder ls
```

### Procrastinate Tag

When urgent reminders ask about high-priority tasks (priority 8-10) during a time point reminder, tasks you mark as **not completed** are recorded in a procrastinate list file:

- `tasks/procrastinate.json` under your `REMINDER_CONFIG_DIR`
- Entries are stored as task descriptions

In `reminder ls`, procrastinated tasks are shown with:

- A `⏳` prefix
- A dim/italic text style

When a procrastinated task is complete (`reminder rm`), it is automatically removed from `tasks/procrastinate.json`.

---

# Habit Management Commands

Commands for interacting with your configured daily habits.

## <a name="habits"></a>track

Log completed habits for today. Habits are loaded from `habits.toml`.

### Syntax
```bash
reminder track [HABIT_IDS...]
```

### Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `HABIT_IDS` | array of strings | (Optional) Space-separated list of Habit IDs to mark completed for today. |

### Examples
```bash
# Mark habits 1 and 2 as completed for today
reminder track 1 2

# Open an interactive prompt window to tick off habits
reminder track
```
