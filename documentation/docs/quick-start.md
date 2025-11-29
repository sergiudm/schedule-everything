
---
sidebar_position: 3
---

# Quick Start

This guide will walk you through creating your first schedule and running the reminder service.

## What You'll Build

<div style={{display: 'flex', gap: '1rem', flexWrap: 'wrap'}}>
  <div style={{flex: '1', minWidth: '300px', maxWidth: '48%'}}>
    <img src="/img/rmd_add.gif" alt="Add Schedule" style={{width: '100%'}} />
    <p style={{textAlign: 'center', marginTop: '0.5rem'}}><em>Adding tasks via CLI</em></p>
  </div>
  <div style={{flex: '1', minWidth: '300px', maxWidth: '48%'}}>
    <img src="/img/rmd_view.gif" alt="View Schedule" style={{width: '100%'}} />
    <p style={{textAlign: 'center', marginTop: '0.5rem'}}><em>Viewing your schedule</em></p>
  </div>
</div>

## 1. Initialize Configuration

If you haven't already, create your configuration files from the provided templates.

```bash
# Create the config directory if it doesn't exist
mkdir -p ~/schedule_management/config

# Copy templates
cp config/settings_template.toml ~/schedule_management/config/settings.toml
cp config/week_schedule_template.toml ~/schedule_management/config/odd_weeks.toml
cp config/week_schedule_template.toml ~/schedule_management/config/even_weeks.toml
```

## 2. Define Your Building Blocks (`settings.toml`)

Open `~/schedule_management/config/settings.toml`. This file defines the *vocabulary* of your schedule—the reusable blocks and settings.

```toml
[settings]
sound_file = "/System/Library/Sounds/Ping.aiff"
alarm_interval = 5        # Repeat alert every 5 seconds
max_alarm_duration = 300  # Stop after 5 minutes

# Define reusable time blocks (duration in minutes)
[time_blocks]
pomodoro = 25
short_break = 5
long_break = 15
meeting = 60
lunch = 60

# Define reusable messages
[time_points]
bedtime = "Wind down and disconnect 😴"
standup = "Daily Standup Meeting 🗣️"
```

## 3. Build Your Schedule (`odd_weeks.toml`)

Open `~/schedule_management/config/odd_weeks.toml`. This is where you map time to action.

The file is organized by day of the week (`[monday]`, `[tuesday]`, etc.) and a `[common]` section for daily habits.

```toml
# Events that happen every day
[common]
"12:00" = "lunch"
"23:00" = "bedtime"

# Specific schedule for Monday
[monday]
"09:00" = "pomodoro"       # Starts at 09:00, ends at 09:25
"09:25" = "short_break"    # Starts at 09:25, ends at 09:30
"09:30" = "pomodoro"
"10:00" = { block = "meeting", title = "Weekly Planning" }

# ... add other days as needed
```

> **Tip**: The system automatically switches between `odd_weeks.toml` and `even_weeks.toml` based on the ISO week number. For a simple weekly schedule, just make them identical or symlink them.

## 4. Verify and Launch

Before letting it run in the background, verify your setup.

1.  **Check for Syntax Errors**:
    ```bash
    reminder status
    ```
    *If your config is valid, this will show the next upcoming event.*

2.  **Visualize the Day**:
    ```bash
    reminder view
    ```
    *This prints a timeline of your schedule to the terminal.*

3.  **Start/Restart the Service**:
    Apply your changes and restart the background daemon.
    ```bash
    reminder update
    ```

## 5. Managing Tasks (Optional)

Schedule Everything also includes a lightweight CLI task manager.

```bash
# Add tasks with an importance score (1-10)
reminder add "Fix critical bug" 10
reminder add "Email the team" 5

# List tasks (sorted by importance)
reminder ls

# Remove a task
reminder rm "Email the team"
```

## Next Steps

*   **[Configuration Reference](configuration/overview.md)**: Deep dive into all available settings.
*   **[Advanced Usage](advanced/weekly-rotation.md)**: Learn about complex rotation patterns.