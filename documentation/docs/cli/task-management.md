
---
sidebar_position: 3
---

# Task Management Commands

Commands for managing your personal task list with importance levels and smart duplicate handling.

## add

Add a new task or update an existing one with an importance level.

### Syntax
```bash
reminder add "TASK_DESCRIPTION" IMPORTANCE_LEVEL [OPTIONS]
```

### Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `TASK_DESCRIPTION` | string | Description of the task (quoted if contains spaces) |
| `IMPORTANCE_LEVEL` | integer | Importance level from 1-10 (higher = more important) |

### Options
| Option | Description |
|--------|-------------|
| `--due DATE` | Set due date (YYYY-MM-DD format) |
| `--category CATEGORY` | Assign task to a category |
| `--notes NOTES` | Add additional notes to the task |

### Examples
```bash
# Add basic task
reminder add "Complete project proposal" 8

# Add task with spaces in description
reminder add "Review pull request #123" 5

# Add high-priority task
reminder add "Call dentist" 9

# Add low-priority task
reminder add "Organize desk" 2

# Add task with due date
reminder add "Submit expense report" 7 --due 2024-01-20

# Add task with category and notes
reminder add "Prepare presentation" 8 --category work --notes "Include Q4 results"
```

### Smart Duplicate Handling
If you add a task with the same description as an existing task, it updates the importance level instead of creating a duplicate:

```bash
# Initial task
reminder add "Buy groceries" 3

# Update importance (no duplicate created)
reminder add "Buy groceries" 6

# Task list shows only one entry with importance 6
```

### Output
```
✓ Task added: "Complete project proposal" (importance: 8)
Task ID: 123
Created: 2024-01-15 09:30:00
```

## rm

Remove one or more tasks by description or ID.

### Syntax
```bash
reminder rm TASK_IDENTIFIER [TASK_IDENTIFIER...] [OPTIONS]
```

### Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `TASK_IDENTIFIER` | string/integer | Task description (quoted) or task ID number |

### Options
| Option | Description |
|--------|-------------|
| `--force` | Skip confirmation prompt |
| `--category CATEGORY` | Remove all tasks in a category |

### Examples
```bash
# Remove by description
reminder rm "Buy groceries"

# Remove multiple tasks by description
reminder rm "Call dentist" "Organize desk"

# Remove by task ID (from 'reminder ls' output)
reminder rm 123

# Remove multiple tasks by ID
reminder rm 123 124 125

# Remove all tasks in a category
reminder rm --category work

# Force removal without confirmation
reminder rm "Old task" --force
```

### Interactive Removal
When removing tasks, you'll see a confirmation prompt:

```
Remove task: "Buy groceries" (importance: 3)?
[y/N]: y
✓ Task removed: "Buy groceries"
```

### Output
```
✓ Task removed: "Complete project proposal"
✓ Task removed: "Call dentist"
2 tasks removed successfully
```

## ls

List all tasks sorted by importance (highest first).

### Syntax
```bash
reminder ls [OPTIONS]
```

### Options
| Option | Description |
|--------|-------------|
| `-v, --verbose` | Show detailed task information |
| `--category CATEGORY` | Show only tasks in specific category |
| `--importance MIN-MAX` | Filter by importance range (e.g., 5-8) |
| `--due-before DATE` | Show tasks due before specific date |
| `--due-after DATE` | Show tasks due after specific date |
| `--completed` | Include completed tasks |
| `--limit N` | Limit output to N tasks |
| `--format FORMAT` | Output format: text, json, csv |

### Examples
```bash
# Basic task list
reminder ls

# Detailed list with timestamps
reminder ls -v

# Show only work category
reminder ls --category work

# Show high-importance tasks (7-10)
reminder ls --importance 7-10

# Show tasks due this week
reminder ls --due-before 2024-01-22

# Show completed tasks
reminder ls --completed

# JSON output
reminder ls --format json

# Limit to 5 most important tasks
reminder ls --limit 5
```

### Sample Output
```
Task List (sorted by