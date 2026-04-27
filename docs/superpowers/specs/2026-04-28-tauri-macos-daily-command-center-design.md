# Tauri macOS Daily Command Center Design

## Goal

Build a standalone macOS app for Schedule Everything using Tauri. The app is a
daily command center: it shows today's schedule, tasks, deadlines, habits, and
sync state, and it lets the user perform daily planning modifications without
using the CLI for routine work.

The app must preserve the existing local-first Python behavior and CLI syntax.
It should wrap the current scheduling logic instead of duplicating rules in
Rust or TypeScript.

## Approved Direction

- Product scope: daily command center, not a full weekly schedule/config editor.
- Mutating scope: tasks, deadlines, habits, and the daily `sync` workflow.
- Sync behavior: generate a preview first, save only after explicit acceptance,
  and regenerate from user feedback when rejected.
- Layout: timeline first.
- Visual direction: Native Glass, meaning light, translucent, macOS-adjacent,
  compact, and restrained.
- Packaging: standalone `.app` with a bundled Python sidecar.

## Architecture

Add a Tauri 2 app alongside the Python package. The frontend will be a
Vite/TypeScript app. The Rust Tauri layer will expose typed commands to the
frontend and invoke a bundled Python sidecar for schedule operations.

The Python sidecar will be a small JSON bridge over existing
`schedule_management` modules. It should accept one command per invocation via
stdin or command arguments and return one JSON object on stdout. The bridge must
not print rich tables or interactive prompts. It should return structured data
or structured errors.

The release build will bundle the Python bridge as a Tauri sidecar binary. The
development path may call the bridge through `uv run`, but production must not
require the user to have the repo, Python environment, or `uv` installed.

## Python Bridge Commands

The bridge should provide a narrow API for the GUI:

- `status_snapshot`: return active config metadata, week parity, skip-day
  state, current event, next event, today's full schedule with any sync overlay,
  ranked tasks, upcoming deadlines, and habit state for today.
- `task_add`, `task_update`, `task_delete`: mutate task data using existing
  task storage and logging behavior.
- `deadline_add`, `deadline_update`, `deadline_delete`: mutate deadline data and
  preserve the existing overdue pruning behavior.
- `habit_mark`: mark selected habits complete for today.
- `sync_generate`: load today's unsynced focus blocks and tasks, call the
  existing LLM assignment logic, and return a preview plan plus rendered
  schedule data. The frontend keeps the proposed plan and feedback history for
  the active sync session.
- `sync_accept`: accept a previously generated plan payload and persist the
  sync overlay with `save_synced_schedule`.

Existing interactive sync internals should be refactored into reusable helper
functions where necessary, so the CLI can keep its prompt loop while the GUI can
drive the preview and acceptance states explicitly.

## UI Design

The main app window opens directly to the daily command center. It should use a
timeline-first layout:

- Header: active config, week parity, today's date, refresh control.
- Now / Next: current block, next block, countdown, and skip-day state.
- Today Timeline: full ordered schedule for today, including synced task titles.
- Work Queue: top tasks, urgent deadlines, and today's habit prompts.
- Quick Add: compact controls for adding tasks and deadlines.
- Sync Today: starts generation, shows a preview timeline, then offers Accept
  and Regenerate with feedback.

Native Glass styling should use translucent panels, subtle borders, restrained
color, and compact macOS-like controls. The UI should remain dense enough for
daily operational use, with no landing page or decorative marketing sections.

## Data Flow

All app actions follow the same path:

1. Frontend dispatches a typed action.
2. Tauri command validates input and calls the Python bridge sidecar.
3. Python bridge uses existing schedule-management modules and writes local
   files when the command is mutating.
4. Python bridge returns structured JSON.
5. Frontend refreshes the affected panels, usually by requesting a fresh
   `status_snapshot`.

Mutating actions should not rely on parsing human CLI output. The bridge owns
the conversion from Python objects and errors into the GUI contract.

## Error Handling And Safety

The app reads and writes the same active config and shared task files as the
CLI, including `REMINDER_CONFIG_DIR` support. If required config files are
missing or invalid, the UI shows a recoverable error state and offers safe
actions such as opening the config folder or instructing the user to run setup
in the terminal. It must not silently create or overwrite schedule config.

Adding or editing tasks and deadlines saves after validation. Deleting tasks or
deadlines asks for confirmation. Sync preview is never saved until the user
accepts it.

Long-running sync generation should show progress. LLM/config errors should
appear in a visible error panel with enough detail to act on, without dumping
raw tracebacks into the primary UI.

## Packaging

The standalone `.app` build should include:

- Tauri app bundle.
- Frontend static assets.
- Python sidecar binary built from the bridge and required runtime package code.
- Tauri sidecar configuration for the macOS target triples.

The initial implementation can support the local Apple Silicon development
target first, then document what is needed for universal or Intel builds.
macOS code signing and notarization are out of scope for the first local build,
but the docs should state that unsigned builds may show macOS warnings outside
the developer machine.

## Testing

Python tests should cover the bridge with deterministic fixtures:

- Snapshot response shape for normal days and skip days.
- Task add/update/delete behavior and task logging.
- Deadline add/update/delete behavior and overdue pruning.
- Habit marking behavior.
- Sync generation helpers with mocked LLM output.
- Sync accept persistence.
- Structured error responses for missing config and invalid input.

Frontend tests should cover data mapping and key UI states:

- Loading state.
- Missing/invalid config state.
- Normal daily timeline.
- Empty task/deadline/habit states.
- Sync generating, preview, regenerate feedback, accepted, and error states.

Build verification should include the existing Python test suite, frontend
tests, `npm run tauri dev`, and a macOS release build that confirms the sidecar
is bundled and callable.

## Documentation

Update README and Docusaurus docs with:

- macOS app overview.
- Development prerequisites.
- Development commands.
- Standalone build command.
- CLI versus GUI workflow notes.
- Sidecar packaging notes and current architecture limitations.

## Out Of Scope

- Full weekly schedule/config editor.
- Config profile setup wizard in the GUI.
- Service/admin actions such as `update`, `switch`, `stop`, or reminder reload.
- Code signing, notarization, App Store distribution, and automatic updates.
- Cross-platform desktop support beyond macOS.
