---
name: update-docs
description: Read the project first, then update README.md, README_zh.md, and documentation pages so docs stay consistent with current behavior.
---

# Update Project Documentation

Use this skill when a user asks to refresh docs, sync docs with code changes, or improve project documentation.

## Goal

Keep user-facing documentation accurate, coherent, and aligned across English and Chinese docs.

## Repository Context

Read these areas before editing docs:

- `README.md`
- `README_zh.md`
- `documentation/docs/`
- `documentation/i18n/zh/`
- `src/schedule_management/`
- `src/schedule_management/cli.py`
- `src/schedule_management/commands/`
- `pyproject.toml`
- `requirements.txt`

## Documentation Workflow

1. Read the project first.
- Inspect CLI entrypoints, command handlers, and current usage patterns.
- Check dependency and setup files for install/run instructions.
- Map existing docs structure before proposing edits.

2. Identify doc drift.
- Find mismatches between code behavior and docs.
- Note missing examples, outdated flags, or stale setup commands.
- Decide which files require synchronized updates.

3. Update English docs.
- Update `README.md` for setup, usage, and examples.
- Update relevant pages under `documentation/docs/`.
- Keep command examples copy-paste safe.

4. Update Chinese docs.
- Update `README_zh.md` to stay functionally aligned with `README.md`.
- Update translated documentation under `documentation/i18n/zh/` when corresponding English pages change.
- Preserve natural wording while keeping technical parity.

5. Verify coherence.
- Ensure command names, options, and examples match current code.
- Ensure links and referenced paths exist.
- Keep terminology consistent across README and docs pages.

## Validation Commands

```bash
uv run pytest tests/test_cli_commands.py -q
```

Optional docs site build check:

```bash
cd documentation
npm run build
```

## Quality Bar

- README and docs reflect current behavior.
- English and Chinese docs are aligned in meaning.
- Examples are accurate and runnable.
- No stale command syntax remains.
