---
sidebar_position: 2
---

# Schedule Management Commands

Commands for managing your schedule, viewing upcoming events, and controlling the reminder service.

## setup

Launch an interactive setup wizard that can configure your model provider credentials and then build or modify schedules with an OpenCode-powered assistant.

### Syntax
```bash
rmd setup
```

### What it does
- Prompts for model vendor/model id/api key if no valid model config is detected.
- Stores model settings in a separate TOML file (`~/.schedule_management/llm.toml`).
- Uses OpenCode (`opencode run`) as the setup-agent runtime.
- Checks whether a complete local schedule configuration already exists.
- Routes to either a build flow (new schedule) or a modify flow (existing schedule).
- Reads or writes `profile.md` in the same config directory as `settings.toml`.
- In build flow, iteratively refines the profile first, asks for timetable context when available, then produces a pure-text schedule summary before generating TOML.
- In modify flow, reads `profile.md` first so edits stay aligned with the user's long-term context.
- Uses evidence-informed defaults around sleep regularity, physical activity, movement breaks, and daytime light exposure when the user leaves details open.
- Only after you confirm the summary does it generate TOML configuration files.
- During build/modify turns, the OpenCode-backed agent can attach local files/images and reason over local context files when needed.
- Recommends `rmd view` and supports iterative adjustments.

## update

Reload the schedule configuration files (pulling from a remote Git repository if `.git` is present) and restart the background service.

### Syntax
```bash
rmd update
```

### Examples
```bash
# Basic update
rmd update
```

## status

Show upcoming events and current service status.
When `rmd sync` has produced an accepted overlay for today, pomodoro and
potato blocks show both the block type and the assigned task title.

### Syntax
```bash
rmd status [OPTIONS]
```

### Options
| Option | Description |
|--------|-------------|
| `-v, --verbose` | Show detailed schedule for today |

### Examples
```bash
# Show current status and next events
rmd status

# Show detailed today's schedule
rmd status -v
```

## sync

Generate today's pomodoro/potato task assignments from `tasks/tasks.json` with
an LLM, show a preview, and only save the overlay after you approve it.

### Syntax
```bash
rmd sync
```

### What it does
- Loads today's untitled pomodoro/potato blocks from the active schedule.
- Reads tasks from `tasks/tasks.json` and sorts them by priority.
- Uses the same OpenCode-backed model configuration flow as `rmd setup`.
- Shows a preview table before writing `synced_schedule.toml`.
- If you reject the preview, asks for a reason and regenerates using that feedback.
- Applies the accepted overlay only to the matching day, so base odd/even templates stay unchanged.

### Examples
```bash
# Generate and review today's focus-block assignments
rmd sync
```

## view

Generate a visual representation of your schedule as a PDF document. This command creates a multi-page PDF combining your Odd and Even week schedules and immediately opens it in your default PDF viewer on macOS.

### Syntax
```bash
rmd view
```

### Examples
```bash
# Generate and open schedule PDF visualization
rmd view
```

## edit

Open the TOML schedule configuration files directly in your default system editor.

### Syntax
```bash
rmd edit [FILE]
```

### Options
FILE choices: `settings`, `odd`, `even`, `deadlines`, `habits` (default is `settings` if omitted).

### Examples
```bash
# Edit settings (default)
rmd edit

# Edit odd weeks schedule
rmd edit odd

# Edit deadlines
rmd edit deadlines
```

## stop

Stop the reminder-runner background service.

### Syntax
```bash
rmd stop
```

## report

Generate a productivity report as a PDF document.

### Syntax
```bash
rmd report TYPE [OPTIONS]
```

### Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `TYPE` | string | `weekly` or `monthly` |

### Options
| Option | Description |
|--------|-------------|
| `-d, --date` | Target date in YYYY-MM-DD format (default: today) |
| `--days` | Number of days to include (default: 7) |

### Examples
```bash
# Generate report for last 7 days
rmd report weekly

# Generate a monthly report
rmd report monthly

# Generate report starting from a specific date
rmd report weekly -d 2024-02-01 --days 14
```
