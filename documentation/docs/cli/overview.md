---
sidebar_position: 1
---

# CLI Overview

Schedule Everything provides a comprehensive command-line interface (CLI) for managing your schedules, tasks, and system configuration. The CLI tool is automatically installed when you run the installation script.

## Accessing the CLI

After installation, the `reminder` command should be available in your terminal. If not, ensure you've added the following to your shell profile:

```bash
export PATH="$HOME/schedule_management:$PATH"
export REMINDER_CONFIG_DIR="$HOME/schedule_management/config"
alias reminder="$HOME/schedule_management/reminder"
```

Then reload your shell:
```bash
source ~/.zshrc  # or source ~/.bash_profile
```

## Command Categories

The CLI commands are organized into three main categories:

### Schedule Management
Commands for managing your schedule and service:
- [`reminder update`](schedule-management.md#update) - Reload config and restart service
- [`reminder view`](schedule-management.md#view) - Generate schedule visualization
- [`reminder status`](schedule-management.md#status) - Show upcoming events
- [`reminder stop`](schedule-management.md#stop) - Stop the alarm service

### Task Management
Commands for managing your task list:
- [`reminder add`](task-management.md#add) - Add or update tasks
- [`reminder rm`](task-management.md#remove) - Remove tasks
- [`reminder ls`](task-management.md#list) - List all tasks

### Deadline Management
Commands for managing event deadlines:
- [`reminder ddl add`](deadline-management.md#add) - Add or update deadlines
- [`reminder ddl rm`](deadline-management.md#remove) - Remove deadlines
- [`reminder ddl`](deadline-management.md#list) - List all deadlines with urgency status

### System Commands
- [`reminder --help`](overview.md#help) - Show help information
- [`reminder --version`](overview.md#version) - Show version information

## Global Options

Most commands support these global options:

| Option              | Description                            |
| ------------------- | -------------------------------------- |
| `-h, --help`        | Show help message for the command      |
| `-v, --verbose`     | Enable verbose output                  |
| `-q, --quiet`       | Suppress non-error output              |
| `--config-dir PATH` | Specify custom configuration directory |

## Configuration Directory

By default, the CLI looks for configuration files in:
- `~/schedule_management/config/` (macOS/Linux)

You can override this by setting the `REMINDER_CONFIG_DIR` environment variable or using the `--config-dir` option.

## Error Handling

The CLI provides clear error messages for common issues:

```bash
# Configuration file not found
Error: settings.toml not found in /Users/username/schedule_management/config/

# Invalid TOML syntax
Error: Invalid TOML syntax in odd_weeks.toml: Expected '=' at line 5

# Service not running
Warning: Schedule management service is not running. Run 'reminder update' to start it.
```

## Exit Codes

The CLI returns standard exit codes:
- `0` - Success
- `1` - General error
- `2` - Configuration error
- `3` - Service error

## Examples

### Basic Usage
```bash
# Check service status
reminder status

# Add a high-priority task
reminder add "Complete project proposal" 9

# View your schedule
reminder view

# Stop the service
reminder stop
```

### Advanced Usage
```bash
# Update with custom config directory
reminder update --config-dir /custom/path/config

# List tasks with verbose output
reminder ls -v

# Remove multiple tasks
reminder rm "Task 1" "Task 2" "Task 3"
```

## Integration with Other Tools

The CLI can be integrated with other tools and scripts:

```bash
# Use in shell scripts
#!/bin/bash
if reminder status | grep -q "No upcoming events"; then
    echo "Schedule is clear"
fi

# Pipe to other commands
reminder ls | grep "urgent" | wc -l

# Use with cron for automated tasks
0 9 * * * /Users/username/schedule_management/reminder status >> ~/schedule.log
```

## Troubleshooting CLI Issues

### Command Not Found
If you get `command not found: reminder`:
1. Check that the installation completed successfully
2. Verify the PATH includes the installation directory
3. Ensure your shell profile is sourced

### Permission Denied
If you get `Permission denied` errors:
```bash
chmod +x ~/schedule_management/reminder
```

### Configuration Errors
If commands fail with configuration errors:
1. Check that all required files exist in the config directory
2. Validate TOML syntax using an online validator
3. Ensure file permissions are correct

## Next Steps

- Learn about [Schedule Management Commands](schedule-management.md)
- Explore [Task Management Commands](task-management.md)
- See Configuration and Settings for detailed syntax