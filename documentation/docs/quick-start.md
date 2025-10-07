
---
sidebar_position: 3
---

# Quick Start

This guide will help you get Schedule Management up and running quickly with a basic configuration.

## Step 1: Initialize Configuration Files

After installation, you need to set up your configuration files:

```bash
# Copy the template files
cp config/settings_template.toml config/settings.toml
cp config/week_schedule_template.toml config/odd_weeks.toml
cp config/week_schedule_template.toml config/even_weeks.toml
```

## Step 2: Configure Basic Settings

Edit `config/settings.toml` to set up your basic configuration:

```toml
[settings]
sound_file = "/System/Library/Sounds/Ping.aiff"  # Path to your preferred sound file
alarm_interval = 5        # seconds between repeated alerts
max_alarm_duration = 300  # max alert duration (5 minutes)

[time_blocks]
pomodoro = 25      # 25-minute work sessions
long_break = 40    # 40-minute breaks
meeting = 50       # 50-minute meetings
exercise = 30      # 30-minute exercise sessions
lunch = 60         # 1-hour lunch break
napping = 30       # 30-minute naps

[time_points]
go_to_bed = "Time to wind down and get ready for bed 😴"
summary_time = "Great work today! Time to summarize your accomplishments 🎉"
```

## Step 3: Create Your Weekly Schedule

Edit `config/odd_weeks.toml` (and optionally `config/even_weeks.toml` for alternating schedules):

```toml
[monday]
"08:30" = "pomodoro"
"09:30" = "long_break"
"10:30" = "pomodoro"
"11:30" = "long_break"
"13:00" = { block = "meeting", title = "Team Standup" }
"14:00" = "pomodoro"

[tuesday]
"08:30" = "pomodoro"
"09:30" = "long_break"
"10:30" = "pomodoro"

[wednesday]
"08:30" = "pomodoro"
"09:30" = "long_break"

[thursday]
"08:30" = "pomodoro"
"09:30" = "long_break"

[friday]
"08:30" = "pomodoro"
"09:30" = "long_break"
"15:00" = { block = "meeting", title = "Weekly Review" }

[common]  # Applies to all days
"12:00" = "lunch"
"19:30" = "pomodoro"
"21:00" = "summary_time"
"22:45" = "go_to_bed"
```

## Step 4: Test Your Configuration

Before starting the service, test your configuration:

```bash
# Check the next upcoming events
reminder status

# View your full schedule with details
reminder status -v

# Generate a visual representation of your schedule
reminder view
```

## Step 5: Start the Service

Once you're satisfied with your configuration, start the service:

```bash
# Update and restart the service
reminder update

# Check if the service is running
launchctl list | grep schedule
```

## Step 6: Add Tasks (Optional)

You can also manage tasks with importance levels:

```bash
# Add tasks with importance levels (higher number = more important)
reminder add "Complete project proposal" 8
reminder add "Review code changes" 5
reminder add "Buy groceries" 3

# View all tasks sorted by importance
reminder ls

# Delete a task
reminder rm "Buy groceries"
```

## Understanding Event Types

### Time Blocks
Time blocks have durations and trigger both start and end notifications:
```toml
"09:00" = "pomodoro"  # Triggers at 09:00 and 09:25 (25 minutes later)
```

### Time Points
Time points are one-time reminders:
```toml
"22:45" = "go_to_bed"  # Triggers once at 22:45
```

### Direct Messages
You can also write custom messages directly:
```toml
"15:00" = "Time for your daily standup meeting!"
```

### Blocks with Custom Titles
Add custom titles to time blocks:
```toml
"14:00" = { block = "meeting", title = "Client Presentation" }
```

## Important Notes

- **Avoid overlapping time blocks**: A 25-minute Pomodoro starting at 09:00 ends at 09:25.