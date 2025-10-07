
---
sidebar_position: 2
---

# Schedule Management Commands

Commands for managing your schedule, viewing upcoming events, and controlling the reminder service.

## update

Reload configuration files and restart the background service.

### Syntax
```bash
reminder update [OPTIONS]
```

### Options
| Option | Description |
|--------|-------------|
| `--force` | Force restart even if configuration hasn't changed |
| `--no-restart` | Reload config without restarting the service |

### Examples
```bash
# Basic update
reminder update

# Force update and restart
reminder update --force

# Reload config without restarting
reminder update --no-restart

# Update with custom config directory
reminder update --config-dir /custom/path/config
```

### Output
```
✓ Configuration loaded successfully
✓ Service restarted
✓ Next event: 09:00 - Pomodoro session
```

## view

Generate a visual representation of your schedule.

### Syntax
```bash
reminder view [OPTIONS]
```

### Options
| Option | Description |
|--------|-------------|
| `--week` | Show the full week schedule |
| `--day DATE` | Show schedule for specific date (YYYY-MM-DD) |
| `--format FORMAT` | Output format: text, json, csv |
| `--output FILE` | Save output to file |

### Examples
```bash
# View today's schedule
reminder view

# View full week
reminder view --week

# View specific day
reminder view --day 2024-01-15

# Export as JSON
reminder view --format json --output schedule.json

# View with custom config
reminder view --config-dir /custom/path/config
```

### Sample Output
```
Schedule for Monday, January 15, 2024
=====================================

08:30 │ ████████████████████████████████████████████████████████████████ │ Pomodoro (25 min)
09:00 │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ Long Break (40 min)
09:45 │ ████████████████████████████████████████████████████████████████ │ Pomodoro (25 min)
10:15 │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ Long Break (40 min)
11:00 │ ████████████████████████████████████████████████████████████████ │ Pomodoro (25 min)
11:30 │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ Long Break (40 min)
12:15 │ ████████████████████████████████████████████████████████████████ │ Lunch (60 min)
13:15 │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ Team Standup (15 min)
13:30 │ ████████████████████████████████████████████████████████████████ │ Pomodoro (25 min)
14:00 │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ Long Break (40 min)
14:45 │ ████████████████████████████████████████████████████████████████ │ Pomodoro (25 min)
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
| `-v, --verbose` | Show detailed schedule information |
| `--next N` | Show next N events (default: 5) |
| `--format FORMAT` | Output format: text, json |
| `--timezone TZ` | Show times in specific timezone |

### Examples
```bash
# Basic status
reminder status

# Detailed status
reminder status -v

# Show next 10 events
reminder status --next 10

# JSON output
reminder status --format json

# Show in different timezone
reminder status --timezone America/New_York
```

### Sample Output
```
Service Status: Running ✓
Configuration: Loaded ✓
Next Event: Pomodoro session in 15 minutes (09:00)

Upcoming Events:
09:00  - Pomodoro session (25 min)
09:30  - Long break (40 min)
10:15  - Pomodoro session (25 min)
10:45  - Long break (40 min)
11:30  - Team standup meeting (15 min)
```

### Verbose Output
```
Service Status: Running ✓
PID: 12345
Uptime: 2 hours 