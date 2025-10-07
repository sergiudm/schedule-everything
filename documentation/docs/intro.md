---
sidebar_position: 1
---

# Introduction

**Schedule Management** (晨钟暮鼓) is a powerful, TOML-based scheduling tool that provides persistent reminders and helps you maintain healthy habits, focused work sessions, and regular breaks.

## What is Schedule Management?

This project provides a simple yet powerful way to manage your daily schedule and receive timely, persistent reminders on your **local** machine. Built with Python, it leverages native system notifications and sounds to keep you on track with your routine.

> **Note**: This tool is currently optimized for **macOS and Linux**. Windows support is planned for future releases.

## Key Features

- **Customizable Schedules**: Define your routine using intuitive TOML configuration files
- **Dual Alerts**: Each reminder triggers both an **audible sound** and a **modal dialog**
- **Persistent Notifications**: Alarms repeat until manually dismissed—perfect for staying accountable
- **Smart Weekly Rotation**: Automatically alternates between **odd-week** and **even-week** schedules using ISO week numbering
- **Flexible Event Types**:
  - **Time blocks** (e.g., Pomodoro sessions with start/end alerts)
  - **Time points** (one-time reminders)
  - **Common events** (apply to all days)
- **CLI Tool**: Easy-to-use command-line interface for managing and inspecting your schedule
- **Task Management**: Built-in task list with importance levels and smart duplicate handling
- **Auto-start via `launchd`**: Runs silently in the background after system boot

## Why TOML?

While many schedule management tools exist, they typically rely on **graphical user interfaces (GUIs)** or **proprietary formats** that make automation, version control, and customization difficult.

By contrast, this tool embraces **declarative configuration via TOML** for several key reasons:

### ✅ Human-Readable & Simple
TOML's clean, minimal syntax is easy to read and write—even for non-programmers. No JSON brackets, no YAML indentation quirks. Just clear key-value pairs and sections.

### ✅ Version-Control Friendly
Your schedule is code. Store it in Git, track changes over time, revert mistakes, or sync across machines with a simple `git pull`.

### ✅ Portable & Reproducible
Want to share your ideal developer routine with a teammate? Just send your TOML files. They can replicate your entire schedule in seconds—no clicking through menus.

### ✅ Composable & Reusable
Define a `pomodoro = 25` once in `settings.toml`, then reuse it across days and weeks. Need to adjust all work blocks from 25 to 30 minutes? Change one line—not dozens of calendar entries.

### ✅ No Vendor Lock-in
Your data stays yours—no accounts, no subscriptions, no cloud dependency. Edit in any text editor, back up anywhere.

### 🤖 AI-Powered Flexibility
With the help of modern **Large Language Models (LLMs)**, you can instantly convert almost any representation of your daily schedule into a valid TOML config—whether it's a **Google Calendar export**, a **screenshot of your team's shared timetable**, a **PDF agenda**, or even a **handwritten note**.

## How It Works

The core script continuously monitors the system time and compares it against your configured schedule. When a scheduled event matches the current time, it triggers a notification.

The system supports:
- **Time blocks**: Activities with defined durations (e.g., 25-minute Pomodoro → start + end alerts)
- **Time points**: Instant reminders (e.g., "Go to bed!" at 22:45)
- **Weekly alternation**: Uses ISO calendar weeks to switch between `odd_weeks.toml` and `even_weeks.toml`
- **Common section**: Events that repeat every day (e.g., nightly wind-down routine)

## Next Steps

Ready to get started? Check out our [Installation Guide](installation.md) to set up Schedule Management on your system, or jump straight to the [Quick Start](quick-start.md) guide to configure your first schedule.
