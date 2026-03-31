---
sidebar_position: 2
---

# Schedule Management Commands

Commands for managing your schedule, viewing upcoming events, and controlling the reminder service.

## setup

Launch an interactive setup wizard that can configure your model provider credentials and then build or modify schedules with an LLM assistant.

### Syntax
```bash
reminder setup
```

### What it does
- Prompts for model vendor/model id/api key if no valid model config is detected.
- Stores model settings in a separate TOML file (`~/.schedule_management/llm.toml`).
- Checks whether a complete local schedule configuration already exists.
- Routes to either a build flow (new schedule) or a modify flow (existing schedule).
- In build flow, asks for an image/file path describing your timetable, creates a first schedule version, then recommends `reminder view` and supports iterative adjustments.

## update

Reload the schedule configuration files (pulling from a remote Git repository if `.git` is present) and restart the background service.

### Syntax
```bash
reminder update
```

### Examples
```bash
# Basic update
reminder update
```

## status

Show upcoming events and current service status.

### Syntax
```bash
reminder status [OPTIONS]
```

### Options
| Option | Description |
|--------|-------------|
| `-v, --verbose` | Show detailed schedule for today |

### Examples
```bash
# Show current status and next events
reminder status

# Show detailed today's schedule
reminder status -v
```

## view

Generate a visual representation of your schedule as a PDF document. This command creates a multi-page PDF combining your Odd and Even week schedules and immediately opens it in your default PDF viewer on macOS.

### Syntax
```bash
reminder view
```

### Examples
```bash
# Generate and open schedule PDF visualization
reminder view
```

## edit

Open the TOML schedule configuration files directly in your default system editor.

### Syntax
```bash
reminder edit [FILE]
```

### Options
FILE choices: `settings`, `odd`, `even`, `deadlines`, `habits` (default is `settings` if omitted).

### Examples
```bash
# Edit settings (default)
reminder edit

# Edit odd weeks schedule
reminder edit odd

# Edit deadlines
reminder edit deadlines
```

## stop

Stop the reminder-runner background service.

### Syntax
```bash
reminder stop
```

## report

Generate a productivity report as a PDF document.

### Syntax
```bash
reminder report TYPE [OPTIONS]
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
reminder report weekly

# Generate a monthly report
reminder report monthly

# Generate report starting from a specific date
reminder report weekly -d 2024-02-01 --days 14
```
