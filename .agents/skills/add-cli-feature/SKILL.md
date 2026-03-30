---
name: add-cli-feature
description: Add or extend a CLI feature in schedule_everything, including command wiring, tests, and docs updates.
---

# Add A New CLI Feature

Use this skill when a user asks to add, extend, or adjust command line functionality.

## Goal

Implement a CLI feature safely with minimal regressions, tests, and docs updates.

## Repository Context

Primary files and folders to inspect first:

- `src/schedule_management/cli.py`
- `src/schedule_management/commands/`
- `src/schedule_management/config.py`
- `tests/test_cli_commands.py`
- `tests/test_deadline_management.py`
- `documentation/docs/cli/`

## Implementation Workflow

1. Clarify the requested behavior.
- Confirm command name, arguments, options, defaults, and output format.
- Confirm whether behavior is additive or changes existing behavior.

2. Locate integration points.
- Find where commands are registered in the CLI entry layer.
- Reuse existing command modules and utilities where possible.
- Keep command naming consistent with existing style.

3. Implement the feature.
- Add or update command handler logic in the appropriate module.
- Add concise help text and argument validation.
- Preserve backward compatibility unless the user requested a breaking change.

4. Add or update tests.
- Cover success path and at least one invalid input path.
- Add regression tests when modifying existing behavior.
- Prefer extending existing CLI test files over creating scattered tests.

5. Update docs.
- Add command usage and examples to CLI docs.
- Update README snippets if the command is user-facing.

6. Verify locally.
- Run targeted tests first.
- Run full test suite when changes are broad.
- Use `uv` for Python commands and test execution.

## Validation Commands

```bash
uv run pytest tests/test_cli_commands.py -q
uv run pytest tests/test_deadline_management.py -q
uv run pytest -q
```

## Quality Bar

- The command has clear help text.
- Behavior is tested and deterministic.
- Existing CLI behavior is not accidentally broken.
- Documentation reflects the shipped command syntax.
