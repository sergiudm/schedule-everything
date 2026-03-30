---
name: modify-cli-feature
description: Modify an existing CLI feature in schedule_everything, including behavior updates, compatibility checks, tests, and docs sync.
---

# Modify An Existing CLI Feature

Use this skill when a user asks to change existing CLI behavior, command options, defaults, output, or validation rules.

## Goal

Change CLI behavior intentionally while preserving compatibility where expected and preventing regressions.

## Repository Context

Primary files and folders to inspect first:

- `src/schedule_management/cli.py`
- `src/schedule_management/commands/`
- `src/schedule_management/config.py`
- `tests/test_cli_commands.py`
- `tests/test_deadline_management.py`
- `tests/test_report_generation.py`
- `documentation/docs/cli/`
- `README.md`

## Modification Workflow

1. Define the current and desired behavior.
- Identify current command syntax, defaults, and side effects.
- Confirm what must change and what must remain stable.
- Mark whether the change is backward compatible or breaking.

2. Find all impact points.
- Locate command registration and handler implementation.
- Locate shared helpers used by other commands.
- Locate tests and docs that encode old behavior.

3. Implement the behavior change.
- Update command parsing, option handling, and validation.
- Keep error messages consistent and actionable.
- Add migration guards or deprecation paths when needed.

4. Protect compatibility.
- If old syntax should still work, preserve it and add tests.
- If syntax is intentionally changed, fail with clear guidance.
- Avoid changing unrelated command behavior.

5. Update tests first-class.
- Add tests for the new expected behavior.
- Add regression tests for previously broken edge cases.
- Update or remove obsolete assertions only when behavior changed by design.

6. Synchronize docs.
- Update CLI documentation examples and option tables.
- Update README command snippets when user-facing behavior changed.
- Call out breaking changes explicitly.

7. Verify and sanity check.
- Run targeted tests for modified commands.
- Run broader tests if shared helpers were changed.
- Use `uv` for Python commands and test execution.

## Validation Commands

```bash
uv run pytest tests/test_cli_commands.py -q
uv run pytest tests/test_deadline_management.py -q
uv run pytest tests/test_report_generation.py -q
uv run pytest -q
```

## Quality Bar

- Modified behavior is explicitly defined and implemented.
- Backward compatibility expectations are documented and tested.
- Regressions are covered by tests.
- Docs and examples match shipped CLI behavior.
