---
sidebar_position: 1
---

# Introduction

**Schedule Management** (晨钟暮鼓) is a robust, developer-centric scheduling tool designed to foster healthy habits, deep work sessions, and consistent routines through persistent local reminders.

## Demo

<div style={{display: 'flex', gap: '1rem', flexWrap: 'wrap'}}>
  <img src="/img/rmd_add.gif" alt="Add Schedule" style={{flex: '1', minWidth: '300px', maxWidth: '48%'}} />
  <img src="/img/rmd_view.gif" alt="View Schedule" style={{flex: '1', minWidth: '300px', maxWidth: '48%'}} />
</div>

## Philosophy

In an era of complex, cloud-based productivity suites, Schedule Management takes a different approach: **simplicity, privacy, and control**.

We believe that your schedule should be:
*   **Owned by you**: Stored locally, not on a remote server.
*   **Versioned**: Treated like code, with history and diffs.
*   **Distraction-free**: Running silently in the background, alerting you only when necessary.
*   **Programmable**: Configured via simple text files, amenable to automation and scripting.

## Core Capabilities

*   **Declarative Configuration**: Define your entire life's rhythm using intuitive TOML files.
*   **Dual-Mode Alerts**: Combines audible cues with persistent modal dialogs to ensure you never miss a beat.
*   **Smart Rotation**: Automatically switches between **odd** and **even** week schedules based on ISO week numbering, perfect for bi-weekly sprints or alternating routines.
*   **Flexible Event Architecture**:
    *   **Time Blocks**: Duration-based events (e.g., Pomodoro, meetings) with start and end triggers.
    *   **Time Points**: Instant, one-off reminders (e.g., "Hydrate", "Bedtime").
    *   **Common Routines**: Define daily habits once, apply them everywhere.
*   **CLI Power**: A comprehensive command-line interface for managing tasks, visualizing schedules, and controlling the daemon.
*   **System Integration**: Runs as a native background service (via `launchd` on macOS), ensuring reliability across reboots.

## Why TOML?

We chose TOML (Tom's Obvious, Minimal Language) over JSON, YAML, or proprietary GUI databases for specific reasons:

### 1. Human-Centric Syntax
TOML is designed to be read and written by humans. It avoids the bracket noise of JSON and the indentation ambiguity of YAML.

### 2. Infrastructure as Code
Your schedule is configuration. By storing it in text files, you can:
*   **Version Control**: Use Git to track how your routine evolves.
*   **Sync**: Share configs across machines using standard tools (rsync, git, Dropbox).
*   **Diff**: See exactly what changed between your old routine and your new one.

### 3. Composable Logic
Define a `pomodoro` block once in `settings.toml`, and reference it hundreds of times. Changing your focus duration from 25 to 50 minutes requires editing a single line, instantly propagating to your entire calendar.

### 4. AI-Ready
Text-based configuration is the native language of LLMs. You can paste a messy email, a screenshot, or a stream-of-consciousness thought into an AI model and ask it to "generate the TOML config for this."

## How It Works

At its heart, Schedule Management is a lightweight daemon that monitors system time against your defined rules.

1.  **Load**: Reads `settings.toml` and the appropriate weekly schedule (`odd_weeks.toml` or `even_weeks.toml`).
2.  **Monitor**: Checks for event triggers every minute.
3.  **Alert**: When a time matches, it executes the configured alert strategy (sound + dialog).
4.  **Persist**: Alarms continue until explicitly acknowledged, preventing accidental dismissal.

## Getting Started

Ready to take control of your time?

*   **[Installation Guide](installation.md)**: Set up the environment and background service.
*   **[Quick Start](quick-start.md)**: Create your first schedule in minutes.
