# Deadline Auto Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically remove deadline events once `days_left <= -2` so stale deadlines disappear from CLI listings and background reminders.

**Architecture:** Add focused cleanup helpers in `src/schedule_management/commands/deadlines.py` and reuse them from `src/schedule_management/runner.py`. The helpers keep cleanup deterministic by accepting an optional `today` date, and persist only when entries are actually removed.

**Tech Stack:** Python 3.12, pytest, existing `uv run pytest` workflow, Rich CLI rendering.

---

## File Structure

- Modify `src/schedule_management/commands/deadlines.py`: add cleanup helpers and call them before rendering `rmd ddl`.
- Modify `src/schedule_management/runner.py`: use deadline cleanup before urgent reminder filtering.
- Modify `tests/test_deadline_management.py`: add CLI cleanup regression tests.
- Modify `tests/test_reminder_logic.py`: add runner cleanup regression test.
- Modify `documentation/docs/cli/deadline-management.md`, `README.md`, and `README_zh.md`: document the automatic two-day overdue cleanup behavior.

### Task 1: CLI Deadline Cleanup

**Files:**
- Modify: `tests/test_deadline_management.py`
- Modify: `src/schedule_management/commands/deadlines.py`

- [ ] **Step 1: Write failing CLI cleanup tests**

```python
@patch("schedule_management.commands.deadlines.save_deadlines")
@patch("schedule_management.commands.deadlines.load_deadlines")
@patch("schedule_management.commands.deadlines.datetime")
def test_show_deadlines_auto_removes_two_day_overdue_entries(self, mock_datetime, mock_load, mock_save):
    mock_now = MagicMock()
    mock_now.date.return_value = datetime(2026, 4, 23).date()
    mock_datetime.now.return_value = mock_now
    mock_datetime.strptime.side_effect = datetime.strptime

    mock_load.return_value = [
        {"event": "remove", "deadline": "2026-04-21", "added": "2026-04-01T00:00:00Z"},
        {"event": "keep-overdue", "deadline": "2026-04-22", "added": "2026-04-01T00:00:00Z"},
        {"event": "keep-future", "deadline": "2026-04-25", "added": "2026-04-01T00:00:00Z"},
    ]

    with patch("schedule_management.commands.deadlines.Console") as mock_console_class:
        mock_console_class.return_value = MagicMock()
        result = reminder.show_deadlines(MagicMock())

    assert result == 0
    saved_deadlines = mock_save.call_args[0][0]
    assert [deadline["event"] for deadline in saved_deadlines] == [
        "keep-overdue",
        "keep-future",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_deadline_management.py::TestShowDeadlines::test_show_deadlines_auto_removes_two_day_overdue_entries -q`

Expected: FAIL because `save_deadlines` is not called and expired entries are not pruned.

- [ ] **Step 3: Implement minimal cleanup helpers and CLI call**

```python
def prune_expired_deadlines(
    deadlines: list[dict[str, Any]],
    today: date | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current_date = today or datetime.now().date()
    kept = []
    removed = []
    for ddl in deadlines:
        try:
            deadline_date = datetime.strptime(ddl["deadline"], "%Y-%m-%d").date()
        except Exception:
            kept.append(ddl)
            continue
        if (deadline_date - current_date).days <= -2:
            removed.append(ddl)
        else:
            kept.append(ddl)
    return kept, removed
```

Call it from `show_deadlines` immediately after loading deadlines, then save the kept list when `removed` is non-empty.

- [ ] **Step 4: Run CLI deadline tests**

Run: `uv run pytest tests/test_deadline_management.py -q`

Expected: PASS.

### Task 2: Runner Deadline Cleanup

**Files:**
- Modify: `tests/test_reminder_logic.py`
- Modify: `src/schedule_management/runner.py`

- [ ] **Step 1: Write failing runner cleanup test**

```python
def test_get_urgent_deadlines_prunes_two_day_overdue_entries(self, tmp_path, monkeypatch):
    import json
    from datetime import datetime, timedelta

    import schedule_management.runner as runner_module

    ddl_path = tmp_path / "ddl.json"
    monkeypatch.setattr(runner_module, "DDL_PATH", str(ddl_path))

    today = datetime.now().date()
    deadlines = [
        {"event": "remove", "deadline": (today - timedelta(days=2)).isoformat()},
        {"event": "keep-overdue", "deadline": (today - timedelta(days=1)).isoformat()},
        {"event": "today", "deadline": today.isoformat()},
    ]
    ddl_path.write_text(json.dumps(deadlines), encoding="utf-8")

    runner = ScheduleRunner.__new__(ScheduleRunner)
    urgent = runner._get_urgent_deadlines()

    assert [deadline["event"] for deadline in urgent] == ["keep-overdue", "today"]
    saved = json.loads(ddl_path.read_text(encoding="utf-8"))
    assert [deadline["event"] for deadline in saved] == ["keep-overdue", "today"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reminder_logic.py::TestUrgentDeadlines::test_get_urgent_deadlines_prunes_two_day_overdue_entries -q`

Expected: FAIL because the two-day overdue event is returned and remains in the JSON file.

- [ ] **Step 3: Reuse cleanup helper in runner**

Import the cleanup helper from `schedule_management.commands.deadlines`, call it after loading JSON, and write the pruned deadline list back to `DDL_PATH` when expired entries were removed.

- [ ] **Step 4: Run reminder tests**

Run: `uv run pytest tests/test_reminder_logic.py -q`

Expected: PASS.

### Task 3: Docs and Full Verification

**Files:**
- Modify: `documentation/docs/cli/deadline-management.md`
- Modify: `README.md`
- Modify: `README_zh.md`

- [ ] **Step 1: Update user-facing docs**

Document that deadlines are automatically removed once they are two or more days overdue, while one-day-overdue deadlines remain visible and urgent.

- [ ] **Step 2: Run targeted tests**

Run: `uv run pytest tests/test_deadline_management.py tests/test_reminder_logic.py -q`

Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -q`

Expected: PASS.
