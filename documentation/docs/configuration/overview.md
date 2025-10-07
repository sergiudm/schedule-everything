---
sidebar_position: 1
---

# Configuration Overview

Schedule Management uses TOML (Tom's Obvious, Minimal Language) configuration files to define your schedules and settings. This approach provides a human-readable, version-control-friendly way to manage your daily routine.

## Configuration File Structure

All configuration files are stored in the `config/` directory:

```
config/
├── settings.toml          # Global settings and reusable definitions
├── odd_weeks.toml         # Schedule for odd-numbered weeks (ISO week)
├── even_weeks.toml        # Schedule for even-numbered weeks (ISO week)
└── tasks.json            # Task list (auto-generated, do not edit manually)
```

## Configuration Files

### settings.toml
Contains global settings, reusable time blocks, and reminder messages. This is where you define:
- System settings (sound files, alert intervals)
- Reusable time block durations
- Time point reminder messages
- Task management settings

### Weekly Schedule Files (odd_weeks.toml & even_weeks.toml)
Define your weekly schedules with day-specific sections and a `[common]` section for events that apply to all days. The system automatically alternates between these files based on ISO week numbering.

### tasks.json
Automatically generated file that stores your task list. This file is managed by the CLI tool and should not be edited manually.

## Configuration Syntax

### Basic Time Entry
```toml
"HH:MM" = "event_name"
```

### Time Block with Custom Title
```toml
"HH:MM" = { block = "block_name", title = "Custom Title" }
```

### Direct Message
```toml
"HH:MM" = "Your custom message here"
```

## Best Practices

1. **Use Consistent Naming**: Keep time block and time point names consistent across your configuration files
2. **Avoid Overlapping Events**: Ensure time blocks don't overlap to prevent conflicting alerts
3. **Leverage the Common Section**: Use `[common]` for daily routines that repeat every day
4. **Version Control Your Configs**: Store your configuration files in Git to track changes
5. **Test Before Deploying**: Use `reminder status` and `reminder view` to verify your configuration

## Configuration Validation

The system performs basic validation on your configuration files:
- Checks for valid TOML syntax
- Validates time formats (HH:MM)
- Ensures referenced time blocks and time points exist in settings.toml
- Warns about potential overlapping events

## Next Steps

- Learn about [Settings Configuration](settings.md)
- Understand [Weekly Schedules](weekly-schedules.md)
- Explore [Configuration Templates](templates.md)