---
sidebar_position: 1
---

# Configuration Overview

Schedule Management uses **TOML** (Tom's Obvious, Minimal Language) for all configuration. This design choice ensures that your schedule is human-readable, easy to edit, and version-control friendly.

## Directory Structure

By default, the system looks for configuration in `~/schedule_management/config/`.

```
config/
├── settings.toml          # Global definitions (sounds, reusable blocks)
├── odd_weeks.toml         # Schedule for odd ISO weeks (1, 3, 5...)
├── even_weeks.toml        # Schedule for even ISO weeks (2, 4, 6...)
└── tasks.json             # Auto-generated task database (do not edit manually)
```

## The Three Pillars

### 1. Settings (`settings.toml`)
Think of this as your **dictionary**. You define what a "pomodoro" is, what sound to play, and what "bedtime" means. You don't schedule *when* things happen here, only *what* they are.

### 2. Schedules (`odd_weeks.toml` / `even_weeks.toml`)
Think of these as your **calendar**. You map specific times to the definitions you created in `settings.toml`.
*   **Odd Weeks**: Active during ISO weeks 1, 3, 5, etc.
*   **Even Weeks**: Active during ISO weeks 2, 4, 6, etc.

### 3. Tasks (`tasks.json`)
A simple JSON store for your todo list. Managed exclusively via the `reminder` CLI tool.

## Syntax Reference

### Defining an Event
The basic syntax is `"HH:MM" = "value"`.

| Type               | Syntax                                    | Example                                       |
| :----------------- | :---------------------------------------- | :-------------------------------------------- |
| **Reference**      | `"HH:MM" = "key"`                         | `"09:00" = "pomodoro"`                        |
| **Direct Message** | `"HH:MM" = "text"`                        | `"12:00" = "Lunch time! 🥗"`                   |
| **Custom Title**   | `"HH:MM" = { block="key", title="text" }` | `"14:00" = { block="meeting", title="Sync" }` |

### Sections
*   `[monday]` through `[sunday]`: Events specific to that day.
*   `[common]`: Events that occur on *every* day of the week (unless overridden).

## Validation & Safety

The system includes built-in checks to prevent common scheduling errors:
*   **Syntax Check**: Ensures valid TOML format.
*   **Reference Check**: Verifies that every scheduled "pomodoro" is actually defined in `settings.toml`.
*   **Overlap Detection**: Warns if you schedule a 60-minute meeting at 09:00 and another event at 09:30.

## Next Steps

*   **[Settings Reference](settings.md)**: Detailed guide to `settings.toml`.
*   **[Weekly Schedules](weekly-schedules.md)**: How to structure your week.
*   **[Templates](templates.md)**: Copy-pasteable examples.