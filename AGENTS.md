# AGENTS.md

## Project Overview

- Project: schedule_everything
- Language: Python (requires Python 3.12+)
- Package root: src/schedule_management
- Main CLI command: reminder
- CLI routing: src/schedule_management/cli.py
- Command handlers: src/schedule_management/commands/

## Working Rules

- Keep changes focused and minimal.
- Do not break existing CLI syntax unless explicitly requested.
- When changing CLI behavior, update tests and docs in the same change.
- Prefer additive, backward-compatible changes.
- Keep imports and constants consistent with the existing module layout.
- For all Python-related setup and commands, use `uv`.

## Local Setup

1. Create and activate a virtual environment with `uv`.
  - `uv venv .venv`
  - `source .venv/bin/activate`
2. Install runtime dependencies:
  - `uv pip install -r requirements.txt`
3. Install test dependencies:
  - `uv pip install -r requirements-test.txt`
4. Optional editable install:
  - `uv pip install -e .`

## Validation Commands

- Full test suite:
  - `uv run pytest -q`
- CLI-focused tests:
  - `uv run pytest tests/test_cli_commands.py -q`
- Deadline logic tests:
  - `uv run pytest tests/test_deadline_management.py -q`
- Reminder logic tests:
  - `uv run pytest tests/test_reminder_logic.py -q`
- Report tests:
  - `uv run pytest tests/test_report_generation.py -q`

## Files To Check For CLI Changes

- src/schedule_management/cli.py
- src/schedule_management/commands/
- tests/test_cli_commands.py
- documentation/docs/cli/
- README.md

## Config Notes

- Runtime config examples are under config/.
- Test fixtures and deterministic config live under tests/config/.
- If behavior depends on current time/date, add deterministic tests.

## Documentation Expectations

- Update CLI docs when command syntax, flags, or output changes.
- Keep examples aligned with actual command behavior.

## Existing Workspace Skills

- .agents/skills/add-cli-feature/SKILL.md
- .agents/skills/modify-cli-feature/SKILL.md
- .agents/skills/update-docs/SKILL.md

Use these skills when implementing or modifying CLI functionality, and when synchronizing docs across README and documentation pages.