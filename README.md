# Schedule Management

[![CI](https://github.com/sergiudm/schedule_management/actions/workflows/tests.yml/badge.svg)](https://github.com/sergiudm/schedule_management/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/schedule-management.svg)](https://pypi.org/project/schedule-management)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

[中文版本](README_zh.md)

This project provides a simple yet powerful way to manage your daily schedule and receive timely, persistent reminders on your **local** machine. Built with Python, it leverages native system notifications and sounds to keep you on track with healthy habits, focused work sessions, and regular breaks.

> [!NOTE]  
> This tool is currently optimized for **macOS and Linux**. Windows support is planned for future releases.

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
- **Task Management**: Built-in task list with importance levels and smart duplicate handling.
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

The core script, [`reminder_macos.py`](https://github.com/sergiudm/schedule_management/blob/main/src/schedule_management/reminder_macos.py), continuously monitors the system time and compares it against your configured schedule. When a scheduled event matches the current time, it triggers a notification.

The system supports:
- **Time blocks**: Activities with defined durations (e.g., 25-minute Pomodoro → start + end alerts).
- **Time points**: Instant reminders (e.g., “Go to bed!” at 22:45).
- **Weekly alternation**: Uses ISO calendar weeks to switch between `odd_weeks.toml` and `even_weeks.toml`.
- **Common section**: Events that repeat every day (e.g., nightly wind-down routine).

---

## Quickstart
### Configuration

All configuration lives in the `config/` directory at the project root. Use the provided templates to get started.

> [!TIP]
> Check [here](https://github.com/sergiudm/schedule_management/blob/main/docs/prompt) to generate your schedule config in seconds. Just describe your routine, and an LLM can create a structured, ready-to-use configuration for you.

#### 1. Settings (`settings.toml`)

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

#### 2. Weekly Schedules (`odd_weeks.toml` & `even_weeks.toml`)

Define your weekly rhythm using day-specific sections and a `[common]` fallback.

##### Supported Entry Types:

| Type                     | Example                                                   | Description                          |
| ------------------------ | --------------------------------------------------------- | ------------------------------------ |
| **Time Block Reference** | `"09:00" = "pomodoro"`                                    | Triggers start + end alerts (25 min) |
| **Time Point Reference** | `"22:45" = "go_to_bed"`                                   | One-time reminder                    |
| **Direct Message**       | `"12:00" = "Lunch time! 🍽️"`                               | Immediate alert with custom text     |
| **Block with Title**     | `"14:00" = { block = "meeting", title = "Team Standup" }` | Custom title for time block          |

##### Example Schedule:

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

#### 🚀 Setup

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

### 📦 Deployment

```bash
./install.sh
```
> [!NOTE]
> You may need to run `launchctl load ~/Library/LaunchAgents/com.sergiudm.schedule_management.plist` according to the script output. And then run `launchctl list|grep schedule` to check if the service is running.

To uninstall:
```bash
launchctl unload ~/Library/LaunchAgents/com.sergiudm.schedule_management.plist
rm -rf "$HOME/schedule_management"
```

---

### 🛠️ CLI Tool

After running the installer (`install.sh`), you’ll have access to the `reminder` command.

#### Setup (Add to Shell Profile)
Add these lines to `~/.zshrc` or `~/.bash_profile`:

```bash
export PATH="$HOME/schedule_management:$PATH"
export REMINDER_CONFIG_DIR="$HOME/schedule_management/config"
alias reminder="$HOME/schedule_management/reminder"
```

Then reload your shell:
```bash
source ~/.zshrc  # or source ~/.bash_profile
```

#### Commands

##### Schedule Management
| Command              | Description                                      |
| -------------------- | ------------------------------------------------ |
| `reminder update`    | Reload config and restart the background service |
| `reminder view`      | Generate schedule visualization                  |
| `reminder status`    | Show next upcoming events                        |
| `reminder status -v` | Show full schedule with details                  |
| `reminder stop`      | Stop the alarm service                           |

##### Task Management
| Command                                      | Description                                                 |
| -------------------------------------------- | ----------------------------------------------------------- |
| `reminder add "task description" importance` | Add a new task or update existing one with importance level |
| `reminder rm "task description"`             | Delete a task by its description                            |
| `reminder rm task_id list`                   | Delete a task by its ID number from 'reminder ls'           |
| `reminder ls`                                | Show all tasks sorted by importance (highest first)         |

##### Deadline Management
| Command                          | Description                                                 |
| -------------------------------- | ----------------------------------------------------------- |
| `reminder ddl add "event" "M.D"` | Add a deadline event (e.g., "homework2" "7.4" for July 4th) |
| `reminder ddl rm "event"`        | Delete one or more deadline events                          |
| `reminder ddl`                   | Show all deadlines with days remaining and urgency status   |

##### Habit Tracking
| Command                          | Description                                                     |
| -------------------------------- | --------------------------------------------------------------- |
| `reminder track <id1> <id2> ...` | Mark habits as completed for today (e.g., `reminder track 1 2`) |

**Task Management Examples:**
```bash
# Add tasks with importance levels (higher number = more important)
reminder add "homework" 8
reminder add "groceries" 3
reminder add "call boss" 5

# Update existing task (replaces old importance level)
reminder add "homework" 10

# View all tasks sorted by importance
reminder ls

# Delete specific tasks
reminder rm "groceries" "homework"
reminder rm 2 4 5  # Remove task by its ID number from 'reminder ls'
```

> [!TIP]  
> **Task Management Features:**
> - **No Duplicates**: Adding a task with an existing name updates the importance level
> - **Smart Sorting**: Tasks are always displayed by importance (highest first)
> - **Persistent**: Tasks are stored in `config/tasks.json` and persist across CLI sessions
> - **Timestamps**: Each task includes creation/update time for reference

**Deadline Management Examples:**
```bash
# Add deadlines (M.D or MM.DD format)
reminder ddl add "homework2" "7.4"      # July 4th
reminder ddl add "project" "12.25"      # December 25th
reminder ddl add "exam" "3.15"          # March 15th

# Update existing deadline
reminder ddl add "homework2" "7.10"     # Changes deadline to July 10th

# Delete specific deadlines
reminder ddl rm "homework2"
reminder ddl rm "project" "exam"        # Delete multiple at once

# View all deadlines with status
reminder ddl
```

> [!TIP]  
> **Deadline Management Features:**
> - **Smart Date Handling**: Automatically determines year (current or next) based on whether date has passed
> - **Visual Urgency Indicators**: Color-coded status (🔴 URGENT ≤3 days, 🟡 SOON 4-7 days, 🟢 OK >7 days)
> - **Days Remaining**: Shows exact countdown to each deadline
> - **Persistent Storage**: Deadlines stored in `config/ddl.json`
> - **Overdue Detection**: Clearly marks deadlines that have passed

**Habit Tracking Examples:**
```bash
# First, define your habits in config/habits.toml:
# [habits]
# "go to sleep on time" = 1
# "exercise" = 2
# "drink 1.5L water" = 3

# Track completed habits (e.g., completed habits 1 and 2 today)
reminder track 1 2

# Track all habits
reminder track 1 2 3

# Track single habit
reminder track 2
```

> [!TIP]  
> **Habit Tracking Features:**
> - **Simple Recording**: Just list the habit IDs you completed today
> - **Daily Records**: Each day's completion is stored with a timestamp
> - **Flexible Configuration**: Define any habits you want in `config/habits.toml`
> - **Persistent Storage**: Records stored in location specified by `record_path` in settings
> - **Update Support**: Running track again on the same day updates the record

---

## 🗺️ Roadmap

- [x] Time point alarms
- [x] Default schedule templates
- [x] Schedule visualization
- [x] Installation script
- [x] Skip-day logic 
- [x] CLI tool
- [x] Task management system with importance levels
- [x] Deadline management system
- [x] Habit tracking system
- [x] Prompts for LLMs to create TOML configs
- [x] Daily summary before bedtime
- [x] Today's tasks overview
- [x] Self rewarding system
- [x] History analysis and weekly reports
- [ ] Language support
- [ ] Website for schedule sharing
- [ ] Better alarm UI
- [ ] **Windows support**

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

> 💡 **Pro Tip**: Pair this with a digital wellness routine—hydrate, stretch, and take real breaks! Your future self will thank you.