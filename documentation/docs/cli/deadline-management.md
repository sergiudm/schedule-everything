---
sidebar_position: 4
---

# Deadline Management Commands

Commands for managing event deadlines with automatic date handling and visual urgency indicators.

## ddl add

Add a new deadline or update an existing one.

### Syntax
```bash
reminder ddl add "EVENT_NAME" "M.D" [OPTIONS]
```

### Parameters
| Parameter        | Type   | Description                                                |
| ---------------- | ------ | ---------------------------------------------------------- |
| `EVENT_NAME`     | string | Name of the event (quoted if contains spaces)              |
| `M.D` or `MM.DD` | string | Deadline date in month.day format (e.g., "7.4" or "07.04") |

### Examples
```bash
# Add basic deadline
reminder ddl add "homework2" "7.4"

# Add deadline with full date
reminder ddl add "project submission" "12.25"

# Add deadline for next year (if date already passed this year)
reminder ddl add "exam" "3.15"

# Update existing deadline
reminder ddl add "homework2" "7.10"
```

### Smart Date Handling
The system automatically determines the correct year:
- If the date hasn't occurred yet this year → uses current year
- If the date has already passed this year → uses next year

Example on November 22, 2025:
```bash
# These use 2025 (not yet passed)
reminder ddl add "final exam" "12.15"

# These use 2026 (already passed)
reminder ddl add "spring project" "3.20"
```

### Duplicate Handling
If you add a deadline with the same event name as an existing one, it updates the date instead of creating a duplicate:

```bash
# Initial deadline
reminder ddl add "homework2" "7.4"

# Update date (no duplicate created)
reminder ddl add "homework2" "7.10"
```

### Output
```
✅ Deadline 'homework2' added successfully for 2026-07-04!
```

Or when updating:
```
✅ Deadline for 'homework2' updated from 2026-07-04 to 2026-07-10
```

## ddl rm

Remove one or more deadline events.

### Syntax
```bash
reminder ddl rm "EVENT_NAME" [EVENT_NAME...] [OPTIONS]
```

### Parameters
| Parameter    | Type   | Description                                             |
| ------------ | ------ | ------------------------------------------------------- |
| `EVENT_NAME` | string | Name of the event to delete (quoted if contains spaces) |

### Options
| Option    | Description                                   |
| --------- | --------------------------------------------- |
| `--force` | Skip confirmation prompt (future enhancement) |

### Examples
```bash
# Remove single deadline
reminder ddl rm "homework2"

# Remove multiple deadlines at once
reminder ddl rm "homework2" "project submission" "exam"

# Remove deadline with spaces in name
reminder ddl rm "final project presentation"
```

### Output
```
✅ Deadline 'homework2' deleted successfully!
```

When deleting multiple deadlines:
```
✅ 3 sets of deadlines deleted successfully:
   - Deadline 'homework2'
   - Deadline 'project submission'
   - Deadline 'exam'
```

### Error Handling

If a deadline doesn't exist:
```bash
$ reminder ddl rm "nonexistent"
❌ Deadline 'nonexistent' not found
```

When some deletions fail:
```bash
$ reminder ddl rm "homework2" "nonexistent" "exam"
❌ Deadline 'nonexistent' not found
✅ 2 sets of deadlines deleted successfully:
   - Deadline 'homework2'
   - Deadline 'exam'
```

### Best Practices
- Always verify the event name by running `reminder ddl` first
- Use quotes around event names that contain spaces
- Delete multiple deadlines in one command for efficiency

## ddl

List all deadlines sorted by date with urgency indicators.

### Syntax
```bash
reminder ddl [OPTIONS]
```

### Options
| Option            | Description                                   |
| ----------------- | --------------------------------------------- |
| `-v, --verbose`   | Show additional details (creation time, etc.) |
| `--format FORMAT` | Output format: table (default), json, csv     |

### Examples
```bash
# Basic deadline list
reminder ddl

# Detailed list with metadata
reminder ddl -v

# JSON output for scripting
reminder ddl --format json
```

### Sample Output
```
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Event                 ┃ Deadline      ┃ Days Left  ┃ Status   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━┩
│ homework2             │ Jul 04, 2026  │ 2 days     │ 🔴 URGENT│
│ project submission    │ Dec 25, 2025  │ 33 days    │ 🟢 OK    │
│ exam                  │ Mar 15, 2026  │ 113 days   │ 🟢 OK    │
└───────────────────────┴───────────────┴────────────┴──────────┘

Total deadlines: 3
```

### Urgency Status Legend

| Status    | Color  | Criteria | Description       |
| --------- | ------ | -------- | ----------------- |
| 🔴 TODAY   | Red    | 0 days   | Deadline is today |
| 🔴 URGENT  | Red    | 1-3 days | Extremely urgent  |
| 🟡 SOON    | Yellow | 4-7 days | Due within a week |
| 🟢 OK      | Green  | 8+ days  | Plenty of time    |
| ⚠️ OVERDUE | Red    | Negative | Past deadline     |

### Filtering and Sorting

The deadline list is automatically:
- **Sorted by date**: Earliest deadlines appear first
- **Color-coded**: Visual urgency indicators
- **Calculated**: Shows exact days remaining

### Storage

Deadlines are stored in `config/ddl.json` in the following format:
```json
[
  {
    "event": "homework2",
    "deadline": "2026-07-04",
    "added": "2025-11-22T10:30:00Z"
  }
]
```

## Best Practices

### Date Format Tips
- Use simple format: `"7.4"` instead of `"07.04"` (both work)
- Don't include the year - it's calculated automatically
- Use quotes around the date to avoid shell interpretation

### Organization Tips
- Use clear, descriptive event names
- Add deadlines as soon as you learn about them
- Check `reminder ddl` regularly (consider adding to your daily routine)
- Update dates immediately if they change

### Integration with Tasks
Deadlines complement the task system:
- Use **tasks** for ongoing work with importance levels
- Use **deadlines** for time-sensitive events with fixed dates

Example workflow:
```bash
# Add deadline
reminder ddl add "project proposal" "12.15"

# Add related task
reminder add "draft project proposal" 8

# As deadline approaches, increase task importance
reminder add "draft project proposal" 10
```

## Error Handling

### Invalid Date Format
```bash
$ reminder ddl add "test" "2025-07-04"
❌ Error: Date must be in format M.D or MM.DD (e.g., 7.4 or 07.04)
```

### Invalid Month or Day
```bash
$ reminder ddl add "test" "13.40"
❌ Error: Month must be between 1 and 12
```

### Missing Arguments
```bash
$ reminder ddl add "test"
❌ Error: Missing required argument: date
Usage: reminder ddl add "EVENT_NAME" "M.D"
```

## Advanced Usage

### JSON Output for Scripting
```bash
# Get urgent deadlines (JSON)
reminder ddl --format json | jq '.[] | select(.days_left <= 3)'

# Count overdue deadlines
reminder ddl --format json | jq '[.[] | select(.days_left < 0)] | length'
```

### Integration with Calendar Apps
```bash
# Export deadlines to calendar format
reminder ddl --format json | python convert_to_ics.py > deadlines.ics
```

### Automated Reminders
Add to your shell profile or cron:
```bash
# Show deadlines on terminal startup
reminder ddl | grep URGENT

# Daily deadline check (add to crontab)
0 9 * * * reminder ddl | grep -E "URGENT|SOON" && notify-send "Upcoming Deadlines"
```

## Troubleshooting

### Deadlines Not Showing
1. Check that `config/ddl.json` exists
2. Verify JSON format is valid: `cat config/ddl.json | jq`
3. Ensure dates are in ISO format (YYYY-MM-DD) in the file

### Wrong Year Calculation
The year is determined when you add the deadline based on current date:
- If you add "3.15" on November 22, 2025 → uses 2026 (already passed)
- To force current year, manually edit `config/ddl.json`

### Permission Issues
Ensure write access to config directory:
```bash
chmod 644 config/ddl.json
```

## Next Steps

- Learn about [Task Management Commands](task-management.md)
- Explore [Schedule Management Commands](schedule-management.md)
- See [CLI Overview](overview.md) for all available commands
