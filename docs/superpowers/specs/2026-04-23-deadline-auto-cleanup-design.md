# Deadline Auto Cleanup Design

## Goal

Automatically remove deadline events once they are at least two days overdue, defined as `days_left <= -2`, so stale deadlines no longer appear in `rmd ddl` or trigger background urgent-deadline reminders.

## Current Behavior

Deadlines are stored as JSON entries with `event`, `deadline`, and `added` fields. The `rmd ddl` command loads and displays all entries sorted by date, including overdue entries. The background runner separately reads the same deadline JSON file and includes every deadline with `days_left <= 3` in urgent reminders, so old overdue events continue to alert indefinitely.

## Desired Behavior

When deadline data is loaded for listing or urgent reminder checks, entries with valid `YYYY-MM-DD` deadlines and `days_left <= -2` are removed from persisted storage. Entries that are overdue by one day remain visible and continue to be treated as urgent. Due-today and future deadlines keep the current display and reminder behavior.

Invalid or malformed deadline records are not deleted by this cleanup rule because they cannot be confidently classified as expired. Existing manual removal with `rmd ddl rm` remains unchanged.

## Architecture

Add focused cleanup helpers to the deadline command module and reuse them from the runner. The helper accepts loaded deadline dictionaries plus an optional current date for deterministic tests, filters expired entries, and returns both retained and removed entries. A second helper persists only when cleanup removed entries.

`rmd ddl` will load deadlines, prune expired entries, save the pruned list when needed, and then render the remaining table. The runner will perform the same cleanup before calculating urgent deadlines, stopping stale alerts even if the user never runs the CLI.

## Testing

Add deterministic tests that freeze the current date and verify:

- `rmd ddl` removes entries where `days_left <= -2`, keeps one-day-overdue entries, and saves the pruned list.
- `rmd ddl` still reports an empty state if cleanup removes all entries.
- The runner prunes stale overdue entries before urgent filtering and no longer returns removed events.
- Existing add, remove, sort, and urgency status behavior stays compatible.

## Documentation

Update deadline CLI docs and README summaries to state that deadlines are automatically removed once they are two or more days overdue.
