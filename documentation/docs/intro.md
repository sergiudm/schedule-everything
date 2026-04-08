---
sidebar_position: 1
---

# Introduction

**Schedule Everything** (晨钟暮鼓) is a robust, developer-centric scheduling tool designed to foster healthy habits, deep work sessions, and consistent routines through persistent local reminders.

The AI setup flow is profile-first: it reads or builds `profile.md` alongside
your schedule files, asks follow-up questions until that profile is usable for
planning, and then generates a schedule that defaults toward healthier timing
patterns when the user has not specified something explicitly.

## Demo

<div style={{display: 'flex', gap: '1rem', flexWrap: 'wrap'}}>
  <img src="img/rmd_add.gif" alt="Add Schedule" style={{flex: '1', minWidth: '300px', maxWidth: '48%'}} />
  <img src="img/rmd_view.gif" alt="View Schedule" style={{flex: '1', minWidth: '300px', maxWidth: '48%'}} />
</div>

## Philosophy

In an era of complex, cloud-based productivity suites, Schedule Everything takes a different approach: **simplicity, privacy, and control**.

We believe that your schedule should be:
*   **Owned by you**: Stored locally, not on a remote server.
*   **Versioned**: Treated like code, with history and diffs.
*   **Distraction-free**: Running silently in the background, alerting you only when necessary.
*   **Programmable**: Configured via simple text files, amenable to automation and scripting.

## Evidence-Informed Defaults

When `rmd setup` has to fill gaps, it uses general, population-level
defaults informed by sleep, movement, sedentary-behavior, and light-exposure
research:

*   protect enough sleep opportunity and avoid systematically compressing sleep
*   prefer regular sleep timing over large weekday/weekend swings
*   distribute weekly physical activity instead of clustering it into rare bursts
*   insert movement or recovery breaks during long desk-based work stretches
*   when the user has flexibility, place harder cognitive work and daylight exposure earlier in the day

These are heuristics rather than medical advice. Real user constraints, medical
instructions, disability needs, or shift-work realities should take priority.

Selected sources:

*   Watson et al., *Recommended Amount of Sleep for a Healthy Adult* ([AASM PDF](https://aasm.org/resources/pdf/pressroom/adult-sleep-duration-consensus.pdf))
*   Sletten et al., *The importance of sleep regularity* ([DOI](https://doi.org/10.1016/j.sleh.2023.07.016))
*   WHO, *Physical activity recommendations for adults* ([WHO](https://www.who.int/initiatives/behealthy/physical-activity))
*   Albulescu et al., *"Give me a break!"* ([PLOS ONE](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0272460))
*   Figueiro et al., *The impact of daytime light exposures on sleep and mood in office workers* ([DOI](https://doi.org/10.1016/j.sleh.2017.03.005))

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

At its heart, Schedule Everything is a lightweight daemon that monitors system time against your defined rules.

1.  **Load**: Reads `settings.toml` and the appropriate weekly schedule (`odd_weeks.toml` or `even_weeks.toml`).
2.  **Monitor**: Checks for event triggers every minute.
3.  **Alert**: When a time matches, it executes the configured alert strategy (sound + dialog).
4.  **Persist**: Alarms continue until explicitly acknowledged, preventing accidental dismissal.

## Getting Started

Ready to take control of your time?

*   **[Installation Guide](installation.md)**: Set up the environment and background service.
*   **[Quick Start](quick-start.md)**: Create your first schedule in minutes.
