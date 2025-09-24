# Schedule Management

[![CI](https://github.com/sergiudm/awesome-healthy-habits-for-developers/actions/workflows/tests.yml/badge.svg)](https://github.com/sergiudm/awesome-healthy-habits-for-developers/actions/workflows/tests.yml)

This script provides a simple way to manage your daily schedule and receive reminders on macOS. It uses a Python script to trigger notifications based on a predefined schedule.

> [!NOTE]
> This script is designed for macOS. Support for other operating systems may be added in the future.

## Features

- **Customizable Schedule**: Easily define your own schedule and reminder messages in the `reminder_macos.py` script.
- **Audible and Visual Alerts**: Get both a sound notification and a dialog box for each reminder.
- **Persistent Reminders**: The alarm will repeat until you dismiss the dialog.
- **Automatic Execution**: Can be configured to run automatically on system startup using `launchd`.

## How It Works

The [`reminder_macos.py`](https://github.com/sergiudm/awesome-healthy-habits-for-developers/blob/main/schedule_management/src/reminder_macos.py) script reads your schedule from multiple TOML configuration files and runs in a loop, checking the current time and triggering alarms when scheduled events occur. The system supports:

- **Weekly alternation**: Automatically switches between odd and even week schedules
- **Time blocks**: Activities with start and end alarms (e.g., pomodoro sessions)
- **Time points**: One-time reminders
- **Common schedules**: Events that apply to all days of the week

## Configuration

The configuration system uses multiple TOML files for flexible schedule management:

### 1. Settings Configuration (`settings.toml`)

This file contains general settings, time blocks, and time points:

```toml
[settings]
sound_file = "/System/Library/Sounds/Ping.aiff"
alarm_interval = 5  # seconds between alarm repeats
max_alarm_duration = 300  # maximum alarm duration in seconds (5 minutes)

[time_blocks]
# Define reusable time blocks with duration in minutes
pomodoro = 25
long_break = 40
meeting = 50
exercise = 30
lunch = 60
napping = 30

[time_points]
# Define one-time reminders
go_to_bed = "上床睡觉 😴 该休息了！"
summary_time = "今天的工作结束 🎉, 总结一下"
```

### 2. Weekly Schedules (`odd_weeks.toml` and `even_weeks.toml`)

The system alternates between odd and even week schedules based on ISO calendar weeks. Each file can contain:

- **Day-specific sections**: `[monday]`, `[tuesday]`, etc.
- **Common section**: `[common]` - applies to all days
- **Time entries**: Use "HH:MM" format as keys

**Schedule Entry Types:**

1. **Time Block References** (triggers start and end alarms):
   ```toml
   "09:00" = "pomodoro"  # References time_blocks.pomodoro (25 min)
   ```

2. **Time Point References** (one-time reminders):
   ```toml
   "22:45" = "go_to_bed"  # References time_points.go_to_bed
   ```

3. **Direct Messages** (immediate display):
   ```toml
   "12:00" = "Lunch time! 🍽️"
   ```

4. **Block Objects** (custom titles for time blocks):
   ```toml
   "14:00" = { block = "meeting", title = "Team Standup" }
   ```

**Example schedule structure:**
```toml
[monday]
"08:30" = "pomodoro"
"09:00" = "pomodoro"
"09:30" = "long_break"
"13:00" = { block = "meeting", title = "Sprint Planning" }

[common]  # Applied to all days
"19:30" = "pomodoro"
"21:00" = "summary_time"
"22:45" = "go_to_bed"
```

## 3. Setup Instructions

Configuration files are now located in the top-level `config/` directory.

1. **Create your settings file**:
   ```bash
   cp config/settings_template.toml config/settings.toml
   ```

2. **Create your weekly schedules** (or modify existing ones):
   ```bash
   cp config/week_schedule_template.toml config/odd_weeks.toml
   cp config/week_schedule_template.toml config/even_weeks.toml
   ```

3. **Customize your schedules** by editing the TOML files in the `config/` directory to fit your needs.

> [!IMPORTANT]
> Template files are for reference only. The system reads from `config/settings.toml`, `config/odd_weeks.toml`, and `config/even_weeks.toml`.

> [!WARNING]
> **Avoid Overlapping Time Blocks**: Time blocks create both start and end alarms. Ensure that time blocks don't overlap, as this can cause conflicting notifications. For example, if you schedule a 25-minute pomodoro at "09:00", avoid scheduling another time block between "09:00" and "09:25".

### Manual Execution

You can run the script manually from your terminal:

```bash
uv run src/schedule_management/reminder_macos.py
```

### View Schedule
To view your schedule, you can pass `--view` flag:
```bash
uv run src/schedule_management/reminder_macos.py --view
```

Then you can check the output schedule in the `schedule_visualization` folder.

### Deployment

#### Deploying with the installation script
To deploy the script, you can use the provided installation script:
```bash
./install.sh
```

#### Deploying manually

To run the script automatically in the background, you can use [launchd](https://www.launchd.info/?lang=en), the standard way to manage daemons and agents on macOS. A sample `.plist` file is provided:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.schedule_notify</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/usrname/awesome-health-habits/.venv/bin/python</string>
        <string>/Users/usrname/awesome-health-habits/src/schedule_management/reminder_macos.py</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>
</dict>
</plist>

```

1.  **Edit the `.plist` file**: You will need to create a file like `com.user.schedule_notify.plist` in `~/Library/LaunchAgents/`. Make sure the `ProgramArguments` key points to the correct path of your python interpreter and the `reminder_macos.py` script.
2.  **Load the agent**:
    ```bash
    launchctl load ~/Library/LaunchAgents/com.user.schedule_notify.plist
    ```
3.  **Start the agent**:
    ```bash
    launchctl start com.user.schedule_notify
    ```

To stop the agent:

```bash
launchctl unload ~/Library/LaunchAgents/com.user.schedule_notify.plist
```

## Roadmap
- [x] Time point alarms
- [x] Default schedule
- [x] Schedule visualization
- [ ] Install script
- [x] Skip days
- [x] Add CLI tools
- [ ] Add support for Linux and Windows
- [ ] MCP to write schedule files based on Notion Calendar or Google Calendar