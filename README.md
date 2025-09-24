# Schedule Management

[![CI](https://github.com/sergiudm/awesome-healthy-habits-for-developers/actions/workflows/tests.yml/badge.svg)](https://github.com/sergiudm/awesome-healthy-habits-for-developers/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

[🇨🇳 中文版本](README_zh.md)

This project provides a simple yet powerful way to manage your daily schedule and receive timely, persistent reminders on **macOS**. Built with Python, it leverages native macOS notifications and sounds to keep you on track with healthy habits, focused work sessions, and regular breaks.

> [!NOTE]  
> This tool is currently optimized for **macOS**. Support for Linux and Windows is planned for future releases.

---

## ✨ Features

- **Customizable Schedules**: Define your routine using intuitive TOML configuration files.
- **Dual Alerts**: Each reminder triggers both an **audible sound** and a **modal dialog**.
- **Persistent Notifications**: Alarms repeat until manually dismissed—perfect for staying accountable.
- **Smart Weekly Rotation**: Automatically alternates between **odd-week** and **even-week** schedules using ISO week numbering.
- **Flexible Event Types**:
  - **Time blocks** (e.g., Pomodoro sessions with start/end alerts)
  - **Time points** (one-time reminders)
  - **Common events** (apply to all days)
- **CLI Tool**: Easy-to-use command-line interface for managing and inspecting your schedule.
- **Auto-start via `launchd`**: Runs silently in the background after system boot.

---

## 📄 Why TOML?

While many schedule management and reminder tools exist—often with sleek interfaces and cloud sync—they typically rely on **graphical user interfaces (GUIs)** or **proprietary formats** that make automation, version control, and customization difficult.

By contrast, this tool embraces **declarative configuration via TOML** for several key reasons:

### ✅ Human-Readable & Simple  
TOML’s clean, minimal syntax is easy to read and write—even for non-programmers. No JSON brackets, no YAML indentation quirks. Just clear key-value pairs and sections.

### ✅ Version-Control Friendly  
Your schedule is code. Store it in Git, track changes over time, revert mistakes, or sync across machines with a simple `git pull`.

### ✅ Portable & Reproducible  
Want to share your ideal developer routine with a teammate? Just send your TOML files. They can replicate your entire schedule in seconds—no clicking through menus.

### ✅ Composable & Reusable  
Define a `pomodoro = 25` once in `settings.toml`, then reuse it across days and weeks. Need to adjust all work blocks from 25 to 30 minutes? Change one line—not dozens of calendar entries.

### ✅ No Vendor Lock-in  
Your data stays yours—no accounts, no subscriptions, no cloud dependency. Edit in any text editor, back up anywhere.

### 🤖 AI-Powered Flexibility  
With the help of modern **Large Language Models (LLMs)**, you can instantly convert almost any representation of your daily schedule into a valid TOML config—whether it’s a **Google Calendar export**, a **screenshot of your team’s shared timetable**, a **PDF agenda**, or even a **handwritten note**. Just paste the raw data or describe your routine in natural language, and an LLM can generate a structured, ready-to-use configuration in seconds.

--- 

## 🧠 How It Works

The core script, [`reminder_macos.py`](https://github.com/sergiudm/awesome-healthy-habits-for-developers/blob/main/schedule_management/src/reminder_macos.py), continuously monitors the system time and compares it against your configured schedule. When a scheduled event matches the current time, it triggers a notification.

The system supports:
- **Time blocks**: Activities with defined durations (e.g., 25-minute Pomodoro → start + end alerts).
- **Time points**: Instant reminders (e.g., “Go to bed!” at 22:45).
- **Weekly alternation**: Uses ISO calendar weeks to switch between `odd_weeks.toml` and `even_weeks.toml`.
- **Common section**: Events that repeat every day (e.g., nightly wind-down routine).

---

## ⚙️ Configuration

All configuration lives in the `config/` directory at the project root. Use the provided templates to get started.

### 1. Settings (`settings.toml`)

Configure global behavior, reusable time blocks, and reminder messages:

```toml
[settings]
sound_file = "/System/Library/Sounds/Ping.aiff"
alarm_interval = 5        # seconds between repeated alerts
max_alarm_duration = 300  # max alert duration (5 minutes)

[time_blocks]
pomodoro = 25
long_break = 40
meeting = 50
exercise = 30
lunch = 60
napping = 30

[time_points]
go_to_bed = "上床睡觉 😴 该休息了！"
summary_time = "今天的工作结束 🎉, 总结一下"
```

### 2. Weekly Schedules (`odd_weeks.toml` & `even_weeks.toml`)

Define your weekly rhythm using day-specific sections and a `[common]` fallback.

#### Supported Entry Types:

| Type | Example | Description |
|------|--------|-------------|
| **Time Block Reference** | `"09:00" = "pomodoro"` | Triggers start + end alerts (25 min) |
| **Time Point Reference** | `"22:45" = "go_to_bed"` | One-time reminder |
| **Direct Message** | `"12:00" = "Lunch time! 🍽️"` | Immediate alert with custom text |
| **Block with Title** | `"14:00" = { block = "meeting", title = "Team Standup" }` | Custom title for time block |

#### Example Schedule:

```toml
[monday]
"08:30" = "pomodoro"
"09:30" = "long_break"
"13:00" = { block = "meeting", title = "Sprint Planning" }

[common]  # Applies to all days
"19:30" = "pomodoro"
"21:00" = "summary_time"
"22:45" = "go_to_bed"
```

> [!WARNING]  
> **Avoid overlapping time blocks!** A 25-minute Pomodoro starting at `09:00` ends at `09:25`. Do not schedule another block between these times—overlaps may cause conflicting alerts.

---

## 🚀 Setup

1. **Initialize config files**:
   ```bash
   cp config/settings_template.toml config/settings.toml
   cp config/week_schedule_template.toml config/odd_weeks.toml
   cp config/week_schedule_template.toml config/even_weeks.toml
   ```

2. **Edit the TOML files** in `config/` to match your routine.

> [!IMPORTANT]  
> The system reads from:  
> - `config/settings.toml`  
> - `config/odd_weeks.toml`  
> - `config/even_weeks.toml`  
> Template files are for reference only.

---

## ▶️ Usage

### Manual Execution
```bash
uv run src/schedule_management/reminder_macos.py
```

### View Your Schedule
Generates a visual representation in `schedule_visualization/`:
```bash
uv run src/schedule_management/reminder_macos.py --view
```

---

## 🛠️ CLI Tool

After running the installer (`install.sh`), you’ll have access to the `reminder` command.

### Setup (Add to Shell Profile)
Add these lines to `~/.zshrc` or `~/.bash_profile`:

```bash
export PATH="$HOME/healthy_habits:$PATH"
export REMINDER_CONFIG_DIR="$HOME/healthy_habits/config"
alias reminder="$HOME/healthy_habits/reminder"
```

Then reload your shell:
```bash
source ~/.zshrc  # or source ~/.bash_profile
```

### Commands

| Command | Description |
|--------|-------------|
| `reminder update` | Reload config and restart the background service |
| `reminder view` | Generate schedule visualization |
| `reminder status` | Show next upcoming events |
| `reminder status -v` | Show full schedule with details |

---

## 📦 Deployment

### Option 1: Use the Installer (Recommended)
```bash
./install.sh
```
To uninstall:
```bash
rm -rf "$HOME/healthy_habits"
```

### Option 2: Manual `launchd` Setup

1. Create `~/Library/LaunchAgents/com.user.schedule_notify.plist`:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.user.schedule_notify</string>
       <key>ProgramArguments</key>
       <array>
           <string>/path/to/your/.venv/bin/python</string>
           <string>/path/to/awesome-healthy-habits/src/schedule_management/reminder_macos.py</string>
       </array>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
   </dict>
   </plist>
   ```

2. Load and start:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.user.schedule_notify.plist
   launchctl start com.user.schedule_notify
   ```

3. To stop:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.user.schedule_notify.plist
   ```

---

## 🗺️ Roadmap

- [x] Time point alarms  
- [x] Default schedule templates  
- [x] Schedule visualization  
- [x] Installation script  
- [x] Skip-day logic  
- [x] CLI tool  
- [ ] **Cross-platform support** (Linux & Windows)  
- [ ] **MCP integration** with Notion Calendar / Google Calendar  

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

> 💡 **Pro Tip**: Pair this with a digital wellness routine—hydrate, stretch, and take real breaks! Your future self will thank you.